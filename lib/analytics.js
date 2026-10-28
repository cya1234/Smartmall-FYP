// lib/analytics.js
// Merchant analytics store for the B2B dashboard (3rd meeting: "Merchant
// Dashboard — AI retention rate, search counts, conversion data").
//
// Uses Node's built-in SQLite (node:sqlite) so the project keeps its
// zero-npm-dependency property. In production this would be MySQL/Postgres with
// a tenant_id leading every index; the schema and query shapes are already
// tenant-scoped so the swap is mechanical.
import { DatabaseSync } from 'node:sqlite';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdirSync } from 'node:fs';
import { seededRandom } from './store.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, '..', 'data');
const DB_PATH = process.env.ANALYTICS_DB || join(DATA_DIR, 'analytics.db');

export const DEMO_TENANT = 'smartmall-demo';

mkdirSync(DATA_DIR, { recursive: true });
const db = new DatabaseSync(DB_PATH);

db.exec(`
  PRAGMA journal_mode = WAL;
  CREATE TABLE IF NOT EXISTS events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant    TEXT NOT NULL DEFAULT 'smartmall-demo',
    session   TEXT,
    type      TEXT NOT NULL,
    label     TEXT,
    value     REAL,
    meta      TEXT,
    createdAt TEXT NOT NULL
  );
  CREATE INDEX IF NOT EXISTS idx_events_tenant_time ON events (tenant, createdAt);
  CREATE INDEX IF NOT EXISTS idx_events_type ON events (type);

  CREATE TABLE IF NOT EXISTS coupons (
    code        TEXT PRIMARY KEY,
    tenant      TEXT NOT NULL,
    session     TEXT,
    discountPct REAL NOT NULL,
    status      TEXT NOT NULL DEFAULT 'issued',
    source      TEXT,
    issuedAt    TEXT NOT NULL,
    appliedAt   TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_coupons_tenant ON coupons (tenant);
`);

const nowIso = () => new Date().toISOString();
const dayKey = (iso) => iso.slice(0, 10);

// ---------------------------------------------------------------- writes ---
export function trackEvent({ tenant = DEMO_TENANT, session = null, type, label = null, value = null, meta = null }) {
  if (!type) throw new Error('type required');
  db.prepare(
    `INSERT INTO events (tenant, session, type, label, value, meta, createdAt)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
  ).run(tenant, session, String(type), label == null ? null : String(label), value, meta ? JSON.stringify(meta) : null, nowIso());
  return { ok: true };
}

export function trackMany(rows) {
  for (const r of rows) trackEvent(r);
  return { ok: true, count: rows.length };
}

const CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

export function issueCoupon({ tenant = DEMO_TENANT, session = null, discountPct = 10, source = 'exit-intent' }) {
  let code;
  for (let attempt = 0; attempt < 12; attempt++) {
    let tail = '';
    for (let i = 0; i < 5; i++) tail += CODE_ALPHABET[Math.floor(Math.random() * CODE_ALPHABET.length)];
    code = `SAVE${discountPct}-${tail}`;
    const exists = db.prepare('SELECT 1 FROM coupons WHERE code = ?').get(code);
    if (!exists) break;
    code = null;
  }
  if (!code) throw new Error('could not allocate coupon code');

  db.prepare(
    `INSERT INTO coupons (code, tenant, session, discountPct, status, source, issuedAt)
     VALUES (?, ?, ?, ?, 'issued', ?, ?)`,
  ).run(code, tenant, session, discountPct, source, nowIso());

  trackEvent({ tenant, session, type: 'coupon_issued', label: code, value: discountPct, meta: { source } });
  return { code, discountPct, expiresInHours: 24 };
}

export function applyCoupon(code, { tenant = DEMO_TENANT, session = null } = {}) {
  const row = db.prepare('SELECT * FROM coupons WHERE code = ? AND tenant = ?').get(code, tenant);
  if (!row) return { ok: false, error: 'not_found' };
  if (row.status === 'applied') return { ok: true, alreadyApplied: true, coupon: row };

  db.prepare(`UPDATE coupons SET status = 'applied', appliedAt = ? WHERE code = ?`).run(nowIso(), code);
  trackEvent({ tenant, session, type: 'coupon_applied', label: code, value: row.discountPct });
  return { ok: true, alreadyApplied: false, coupon: { ...row, status: 'applied' } };
}

export function getCoupon(code, { tenant = DEMO_TENANT } = {}) {
  return db.prepare('SELECT * FROM coupons WHERE code = ? AND tenant = ?').get(code, tenant) || null;
}

// ---------------------------------------------------------------- reads ----
function countFor(type, since, tenant, label = null) {
  const sql = label
    ? `SELECT COUNT(*) AS n FROM events WHERE tenant = ? AND type = ? AND label = ? AND createdAt >= ?`
    : `SELECT COUNT(*) AS n FROM events WHERE tenant = ? AND type = ? AND createdAt >= ?`;
  const args = label ? [tenant, type, label, since] : [tenant, type, since];
  return db.prepare(sql).get(...args).n;
}

export function getSummary({ tenant = DEMO_TENANT, days = 7 } = {}) {
  const since = new Date(Date.now() - days * 86400000).toISOString();

  const sessions = db
    .prepare(`SELECT COUNT(DISTINCT session) AS n FROM events WHERE tenant = ? AND createdAt >= ? AND session IS NOT NULL`)
    .get(tenant, since).n;

  const searches = countFor('search', since, tenant);
  const visualSearches = countFor('search', since, tenant, 'visual');
  const assistantQueries = countFor('search', since, tenant, 'assistant');
  // Everything that is not a visual/assistant query is a typed keyword search.
  const keywordSearches = Math.max(0, searches - visualSearches - assistantQueries);
  const productViews = countFor('product_view', since, tenant);
  const addToCart = countFor('add_to_cart', since, tenant);
  const checkout = countFor('checkout', since, tenant);
  const exitShown = countFor('exit_intent_shown', since, tenant);
  const exitDismissed = countFor('exit_intent_dismissed', since, tenant);
  const exitClaimed = countFor('coupon_issued', since, tenant);
  const couponsApplied = countFor('coupon_applied', since, tenant);
  const widgetOpens = countFor('widget_open', since, tenant);

  const pct = (a, b) => (b > 0 ? Math.round((a / b) * 1000) / 10 : 0);

  // Daily series for the chart.
  const dailyRows = db
    .prepare(
      `SELECT substr(createdAt, 1, 10) AS day,
              SUM(CASE WHEN type = 'search' THEN 1 ELSE 0 END) AS searches,
              SUM(CASE WHEN type = 'exit_intent_shown' THEN 1 ELSE 0 END) AS exitShown,
              SUM(CASE WHEN type = 'coupon_issued' THEN 1 ELSE 0 END) AS claimed,
              SUM(CASE WHEN type = 'checkout' THEN 1 ELSE 0 END) AS checkout
       FROM events WHERE tenant = ? AND createdAt >= ?
       GROUP BY day ORDER BY day`,
    )
    .all(tenant, since);

  const byDay = new Map(dailyRows.map((r) => [r.day, r]));
  const daily = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000);
    const key = d.toISOString().slice(0, 10);
    const r = byDay.get(key) || { searches: 0, exitShown: 0, claimed: 0, checkout: 0 };
    daily.push({
      date: key,
      label: `${d.getMonth() + 1}/${d.getDate()}`,
      searches: Number(r.searches) || 0,
      exitShown: Number(r.exitShown) || 0,
      claimed: Number(r.claimed) || 0,
      checkout: Number(r.checkout) || 0,
    });
  }

  // Top query terms come from the assistant / keyword searches.
  const topSearches = db
    .prepare(
      `SELECT label AS term, COUNT(*) AS n FROM events
       WHERE tenant = ? AND createdAt >= ? AND type = 'search' AND label NOT IN ('keyword','visual','assistant')
       GROUP BY label ORDER BY n DESC LIMIT 6`,
    )
    .all(tenant, since);

  return {
    tenant,
    days,
    generatedAt: nowIso(),
    totals: {
      sessions, searches, keywordSearches, visualSearches, assistantQueries,
      productViews, addToCart, checkout, exitShown, exitDismissed, exitClaimed, couponsApplied,
      widgetOpens,
    },
    rates: {
      retentionRate: pct(exitClaimed, exitShown),
      exitDismissRate: pct(exitDismissed, exitShown),
      couponApplyRate: pct(couponsApplied, exitClaimed),
      conversionRate: pct(checkout, sessions),
      cartRate: pct(addToCart, productViews),
    },
    funnels: {
      exitIntent: [
        { stage: 'shown', count: exitShown },
        { stage: 'claimed', count: exitClaimed },
        { stage: 'applied', count: couponsApplied },
        { stage: 'checkout', count: checkout },
      ],
    },
    daily,
    topSearches,
  };
}

export function getRecentEvents({ tenant = DEMO_TENANT, limit = 25 } = {}) {
  return db
    .prepare(
      `SELECT id, session, type, label, value, createdAt FROM events
       WHERE tenant = ? ORDER BY id DESC LIMIT ?`,
    )
    .all(tenant, Math.min(200, Math.max(1, limit)));
}

export function getCoupons({ tenant = DEMO_TENANT, limit = 20 } = {}) {
  return db
    .prepare(`SELECT code, discountPct, status, source, issuedAt, appliedAt FROM coupons WHERE tenant = ? ORDER BY issuedAt DESC LIMIT ?`)
    .all(tenant, Math.min(200, Math.max(1, limit)));
}

export function resetAnalytics({ tenant = DEMO_TENANT } = {}) {
  db.prepare('DELETE FROM events WHERE tenant = ?').run(tenant);
  db.prepare('DELETE FROM coupons WHERE tenant = ?').run(tenant);
  seeded = false;
  return { ok: true };
}

// ---------------------------------------------------------------- seeding --
// A brand-new database makes a dashboard look broken, so on first run we lay
// down plausible history. Seeded rows are tagged {seed:true} and the dashboard
// states plainly that history is demo data and live events accumulate on top.
let seeded = false;

export function seedIfEmpty({ tenant = DEMO_TENANT, days = 7 } = {}) {
  if (seeded) return { seeded: false, reason: 'already-checked' };
  const n = db.prepare('SELECT COUNT(*) AS n FROM events WHERE tenant = ?').get(tenant).n;
  if (n > 0) {
    seeded = true;
    return { seeded: false, reason: 'has-data', existing: n };
  }

  const rand = seededRandom('analytics-seed-v1');
  const between = (a, b) => Math.floor(a + rand() * (b - a + 1));
  const terms = [
    '海島婚禮 穿搭', '滑雪 裝備', '亞麻 襯衫', '牛仔外套', '白色球鞋',
    'a red dress', 'winter jacket', 'office outfit', 'wide leg trousers', '防曬',
  ];

  const insert = db.prepare(
    `INSERT INTO events (tenant, session, type, label, value, meta, createdAt)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
  );
  db.exec('BEGIN');
  try {
    for (let d = days - 1; d >= 0; d--) {
      const base = new Date(Date.now() - d * 86400000);
      // Weekend traffic is a little higher — keeps the chart from being flat.
      const weekend = [0, 6].includes(base.getDay()) ? 1.18 : 1;
      const scale = (v) => Math.round(v * weekend);

      // Model real sessions so conversion rate is meaningful (checkout/sessions).
      const sessionIds = Array.from({ length: scale(between(160, 240)) }, (_, i) => `seed-${d}-s${i}`);
      const pickSession = () => sessionIds[Math.floor(rand() * sessionIds.length)];

      const counts = {
        product_view: scale(between(120, 240)),
        search_keyword: scale(between(34, 70)),
        search_visual: scale(between(9, 24)),
        search_assistant: scale(between(6, 18)),
        add_to_cart: scale(between(24, 55)),
        checkout: scale(between(7, 19)),
        exit_intent_shown: scale(between(30, 62)),
        exit_intent_dismissed: scale(between(20, 45)),
        coupon_issued: scale(between(2, 5)),
        coupon_applied: scale(between(1, 3)),
        widget_open: scale(between(8, 26)),
      };

      const at = (h) => {
        const t = new Date(base);
        t.setHours(8 + Math.floor(h), Math.floor(rand() * 60), Math.floor(rand() * 60), 0);
        return t.toISOString();
      };

      let h = 0;
      const push = (type, label, value) =>
        insert.run(tenant, pickSession(), type, label, value, '{"seed":true}', at(h++ % 12));

      for (let i = 0; i < counts.product_view; i++) push('product_view', null, null);
      for (let i = 0; i < counts.search_keyword; i++) push('search', terms[Math.floor(rand() * terms.length)], null);
      for (let i = 0; i < counts.search_visual; i++) push('search', 'visual', null);
      for (let i = 0; i < counts.search_assistant; i++) push('search', 'assistant', null);
      for (let i = 0; i < counts.add_to_cart; i++) push('add_to_cart', null, null);
      for (let i = 0; i < counts.checkout; i++) push('checkout', null, null);
      for (let i = 0; i < counts.exit_intent_shown; i++) push('exit_intent_shown', null, 10);
      for (let i = 0; i < counts.exit_intent_dismissed; i++) push('exit_intent_dismissed', null, null);
      for (let i = 0; i < counts.coupon_issued; i++) push('coupon_issued', `SAVE10-SEED${d}${i}`, 10);
      for (let i = 0; i < counts.coupon_applied; i++) push('coupon_applied', `SAVE10-SEED${d}${i}`, 10);
      for (let i = 0; i < counts.widget_open; i++) push('widget_open', i % 3 === 0 ? 'search-bar' : 'launcher', null);
    }
    db.exec('COMMIT');
  } catch (e) {
    db.exec('ROLLBACK');
    throw e;
  }

  seeded = true;
  const total = db.prepare('SELECT COUNT(*) AS n FROM events WHERE tenant = ?').get(tenant).n;
  return { seeded: true, events: total, days };
}

export { db as analyticsDb, DB_PATH };
