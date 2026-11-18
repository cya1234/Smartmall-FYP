// lib/userState.js
// Everything the site learns about a shopper that is not the fixed demo profile:
// the onboarding answers and the real search history.
//
// Partitioned per account so sharing a demo does not mix two people's preferences.
//'guest' is a real partition, not a fallback: browsing without logging in still
// records history, it just lands on the shared guest record.
//
// Kept separate from data/profile.json on purpose. That file is read-only demo data
// (store.js mutates its in-memory copy but never writes it), so anything that must
// survive a restart lives here instead.
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, '..', 'data');
const PATH = process.env.USER_STATE_PATH || join(DATA_DIR, 'user-state.json');

const MAX_HISTORY = 300;
export const GUEST = 'guest';

function blankAccount() {
  return { onboarding: null, onboardedAt: null, history: [] };
}

function load() {
  try {
    if (!existsSync(PATH)) return { accounts: {} };
    const raw = JSON.parse(readFileSync(PATH, 'utf8'));
    // Older files stored one shopper at the top level. Treat that as the guest.
    if (!raw.accounts && (raw.history || raw.onboarding || raw.onboardedAt)) {
      return { accounts: { [GUEST]: { onboarding: raw.onboarding || null, onboardedAt: raw.onboardedAt || null, history: Array.isArray(raw.history) ? raw.history : [] } } };
    }
    return { accounts: raw.accounts && typeof raw.accounts === 'object' ? raw.accounts : {} };
  } catch {
    return { accounts: {} };
  }
}

let state = load();
let dirty = false;
let timer = null;

function save() {
  dirty = true;
  if (timer) return;
  timer = setTimeout(() => {
    timer = null;
    if (!dirty) return;
    dirty = false;
    try {
      mkdirSync(DATA_DIR, { recursive: true });
      writeFileSync(PATH, JSON.stringify(state, null, 1), 'utf8');
    } catch (err) {
      console.warn('  user-state: could not persist —', err.message);
    }
  }, 250);
}

function acct(key) {
  const id = String(key || GUEST);
  if (!state.accounts[id]) state.accounts[id] = blankAccount();
  const a = state.accounts[id];
  if (!Array.isArray(a.history)) a.history = [];
  return a;
}

// ------------------------------------------------------------------ onboarding

/**
 * Store the answers from the welcome survey.
 * Only the keys the survey actually asks about are kept, so a malformed body cannot
 * write arbitrary structure into the file.
 */
export function saveOnboarding(input = {}, account = GUEST) {
  const takeList = (v, max = 12) => (Array.isArray(v) ? v.filter((x) => typeof x === 'string').slice(0, max) : []);
  const takeNum = (v, lo, hi) => {
    const n = Number(v);
    return Number.isFinite(n) ? Math.max(lo, Math.min(hi, n)) : null;
  };

  const answers = {
    categories: takeList(input.categories),
    styles: takeList(input.styles),
    colours: takeList(input.colours),
    avoidColours: takeList(input.avoidColours),
    occasions: takeList(input.occasions),
    materials: takeList(input.materials),
    budget: {
      min: takeNum(input.budget?.min, 0, 100000),
      max: takeNum(input.budget?.max, 0, 100000),
    },
    pairs: Array.isArray(input.pairs)
      ? input.pairs
        .filter((p) => p && typeof p.winner === 'string' && typeof p.loser === 'string')
        .slice(0, 8)
      : [],
  };

  const a = acct(account);
  a.onboarding = answers;
  a.onboardedAt = new Date().toISOString();
  save();
  return answers;
}

export function getOnboarding(account = GUEST) {
  return acct(account).onboarding;
}

export function hasOnboarded(account = GUEST) {
  return Boolean(acct(account).onboardedAt);
}

/**
 * How much this shopper leans toward a catalogue category, 0..1.
 * Used to nudge ranking without overriding what the query actually asks for.
 */
export function categoryAffinity(category, account = GUEST) {
  const ob = acct(account).onboarding;
  if (!ob || !ob.categories?.length || !category) return 0;
  return ob.categories.includes(category) ? 1 : 0;
}

/** Same idea one level down; "Jacket" over "Shirt" is a real preference. */
export function subcategoryAffinity(product, account = GUEST) {
  const ob = acct(account).onboarding;
  if (!ob || !product) return 0;
  let hit = 0;
  if (ob.categories?.includes(product.category)) hit += 1;
  if (ob.styles?.length && product.style && ob.styles.includes(product.style)) hit += 0.5;
  if (ob.colours?.includes(product.colorName)) hit += 0.5;
  if (ob.avoidColours?.includes(product.colorName)) hit -= 1;
  return Math.max(-1, Math.min(1.5, hit));
}

// --------------------------------------------------------------------- history

/**
 * Record a search. Text, assistant and visual searches all come through here so the
 * "what people look for" view is one list rather than three.
 */
export function recordSearch({ kind = 'text', query = '', lang = 'zh', results = null, productId = null } = {}, account = GUEST) {
  const q = String(query || '').trim().slice(0, 120);
  if (!q && !productId) return null;
  const a = acct(account);
  const entry = {
    at: new Date().toISOString(),
    kind,
    query: q,
    lang,
    results: Number.isFinite(results) ? results : null,
    productId,
  };
  a.history.push(entry);
  if (a.history.length > MAX_HISTORY) a.history.splice(0, a.history.length - MAX_HISTORY);
  save();
  return entry;
}

const norm = (s) => String(s || '').toLowerCase().trim();

/** Recent queries (deduplicated, newest first) and the most repeated terms. */
export function getHistory({ days = 30, limit = 12 } = {}, account = GUEST) {
  const since = Date.now() - days * 86400000;
  const recent = acct(account).history.filter((h) => new Date(h.at).getTime() >= since);

  const seen = new Set();
  const recentQueries = [];
  for (let i = recent.length - 1; i >= 0 && recentQueries.length < limit; i--) {
    const key = norm(recent[i].query);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    recentQueries.push(recent[i]);
  }

  const counts = new Map();
  for (const h of recent) {
    const key = norm(h.query);
    if (!key) continue;
    const row = counts.get(key) || { query: h.query, count: 0, lastKind: h.kind };
    row.count += 1;
    row.lastKind = h.kind;
    counts.set(key, row);
  }
  const top = [...counts.values()].sort((a, b) => b.count - a.count).slice(0, limit);

  return {
    total: recent.length,
    byKind: recent.reduce((acc, h) => {
      acc[h.kind] = (acc[h.kind] || 0) + 1;
      return acc;
    }, {}),
    recentQueries,
    top,
    days,
  };
}

export function clearHistory(account = GUEST) {
  acct(account).history = [];
  save();
  return { ok: true };
}

export function resetAll(account = GUEST) {
  state.accounts[String(account || GUEST)] = blankAccount();
  save();
  return { ok: true };
}

/** Which accounts exist in the file — used by the auth tests, not by the UI. */
export function accountKeys() {
  return Object.keys(state.accounts);
}

export { PATH as USER_STATE_PATH };
