// server.js
// SmartMall — AI-Driven E-Commerce Platform.
// Zero-dependency Node.js HTTP server (built-in http module).
//
// Architecture note (from the FYP proposal): standard web operations (catalog,
// cart, static hosting) are deliberately decoupled from the AI inference
// services (assistant, visual search, forecasting, try-on), which live in
// lib/*.js behind stable JSON contracts so real models can be swapped in later.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { networkInterfaces } from 'node:os';
import { fileURLToPath } from 'node:url';
import { dirname, join, extname, normalize } from 'node:path';

import { getProducts, getProduct, getProfile, updateProfile, currencyFor } from './lib/store.js';
import { runAssistant } from './lib/assistant.js';
import { runVisualSearch, visualSearchStatus } from './lib/visualSearch.js';
import { forecastProduct } from './lib/forecast.js';
import { prophetHealth, prophetEval, prophetBaseUrl } from './lib/prophetClient.js';
import { getStores, getStore, availability, pickupInfo } from './lib/stores.js';
import {
  startSession as startSurvey, answer as answerSurvey, finish as finishSurvey,
  spin as spinSurvey, profileSummary, resetPreferences as resetSurvey,
} from './lib/survey.js';
import { scoreOutfit, aestheticStatus } from './lib/aesthetic.js';
import { runTryOn, tryOnStatus } from './lib/tryon.js';
import { buildBlindBox, detectScenario, SCENARIOS } from './lib/blindbox.js';
import { runPriceAgent, PLATFORMS } from './lib/priceAgent.js';
import { draftListing, publishListing, getListings, buyListing, consignableItems, ecoSummary, conditionOptions } from './lib/resale.js';
import { createPoll, getPolls, getPoll, simulateVotes, castVote, GROUPS, socialImpact } from './lib/social.js';
import { getMemoryContext, getInsights, getWardrobeCoverage } from './lib/memory.js';
import { predictReturnRisk, predictCartRisk } from './lib/returnPredict.js';
import { route as routeQuery } from './lib/agent/router.js';
import { routeWithLLM, llmHealth, warmLLM } from './lib/agent/llmRouter.js';
import {
  recordSearch, getHistory, clearHistory, saveOnboarding, getOnboarding, hasOnboarded,
} from './lib/userState.js';
import { startSession, analyzePhoto, submitReturn, getReturns as getReturnForms, returnStats, RETURN_REASONS } from './lib/support.js';
import {
  trackEvent, issueCoupon, applyCoupon, getCoupon, getSummary, getRecentEvents, getCoupons,
  seedIfEmpty, refreshSeedIfStale, resetAnalytics, DEMO_TENANT,
} from './lib/analytics.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = join(__dirname, 'public');
const PORT = Number(process.env.PORT) || 3000;

// Lay down demo history so the merchant dashboard is never empty, and refresh it
// when the seeded window has aged out (otherwise the dashboard empties after a
// few days because the demo rows fall outside the 7-day reporting window).
try {
  const seedResult = refreshSeedIfStale();
  if (seedResult.seeded) {
    console.log(`  analytics: ${seedResult.refreshed ? 'refreshed' : 'seeded'} `
      + `${seedResult.events} demo events (${seedResult.days} days)`);
  }
} catch (err) {
  console.warn('  analytics: seeding skipped —', err.message);
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
};

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store',
  });
  res.end(body);
}

async function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (chunk) => {
      data += chunk;
      // Query photos are sent base64-encoded; allow plenty of headroom.
      if (data.length > 14 * 1024 * 1024) {
        reject(new Error('payload too large'));
        req.destroy();
      }
    });
    req.on('end', () => resolve(data));
    req.on('error', reject);
  });
}

async function serveStatic(req, res, pathname) {
  // Prevent path traversal.
  const rel = normalize(pathname).replace(/^(\.\.[/\\])+/, '');
  let filePath = join(PUBLIC_DIR, rel);
  if (!filePath.startsWith(PUBLIC_DIR)) {
    res.writeHead(403).end('Forbidden');
    return;
  }
  if (!existsSync(filePath) || rel === '' || rel.endsWith('/')) filePath = join(PUBLIC_DIR, 'index.html');

  try {
    const data = await readFile(filePath);
    const ext = extname(filePath).toLowerCase();
    const headers = { 'Content-Type': MIME[ext] || 'application/octet-stream', 'Cache-Control': 'no-store' };
    // The embeddable widget is loaded from the merchant's own origin.
    if (rel.endsWith('embed.js')) headers['Access-Control-Allow-Origin'] = '*';
    // widget.html must be frameable by any merchant store. In production this
    // would be an allow-list of onboarded tenant domains.
    if (rel.endsWith('widget.html')) headers['Content-Security-Policy'] = "frame-ancestors *";
    res.writeHead(200, headers);
    res.end(data);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain' }).end('Not found');
  }
}

async function handleApi(req, res, pathname) {
  const method = req.method || 'GET';
  const parts = pathname.split('/').filter(Boolean); // e.g. ['api','products','p001']

  // GET /api/health
  if (parts[1] === 'health') return sendJson(res, 200, { ok: true, service: 'SmartMall' });

  // GET /api/products, /api/products/:id
  if (parts[1] === 'products') {
    if (parts[2]) {
      const p = getProduct(parts[2]);
      return p ? sendJson(res, 200, p) : sendJson(res, 404, { error: 'not found' });
    }
    const q = (new URL(req.url, 'http://localhost').searchParams.get('q') || '').toLowerCase();
    let list = getProducts();
    if (q) {
      list = list.filter((p) =>
        `${p.name} ${p.name_zh || ''} ${p.brand} ${p.category} ${p.subcategory} ${p.colorName} ${p.tags.join(' ')} ${p.description_zh || ''}`
          .toLowerCase()
          .includes(q),
      );
      // Only real queries are recorded. The shop renders the whole catalogue on load,
      // and recording that would bury the searches under one entry per page view.
      recordSearch({ kind: 'text', query: q, lang: 'zh', results: list.length });
    }
    return sendJson(res, 200, list);
  }

  // GET /api/forecast/status — is the Prophet service up?
  if (parts[1] === 'forecast' && parts[2] === 'status') {
    const h = await prophetHealth();
    return sendJson(res, 200, h
      ? { online: true, engine: 'prophet', ...h, url: prophetBaseUrl() }
      : { online: false, engine: 'linear', url: prophetBaseUrl() });
  }

  // GET /api/forecast/:id — Prophet first, linear model as fallback
  if (parts[1] === 'forecast' && parts[2]) {
    const u = new URL(req.url, 'http://localhost');
    const horizon = Math.min(90, Math.max(7, Number(u.searchParams.get('horizon')) || 30));
    const f = await forecastProduct(parts[2], { horizon });
    return f ? sendJson(res, 200, f) : sendJson(res, 404, { error: 'not found' });
  }

  // GET /api/forecast-eval — catalogue-wide holdout comparison
  if (parts[1] === 'forecast-eval' && method === 'GET') {
    const live = await prophetEval();
    if (live) return sendJson(res, 200, live);
    try {
      const raw = await readFile(join(__dirname, 'data', 'forecast-eval.json'), 'utf8');
      return sendJson(res, 200, JSON.parse(raw));
    } catch {
      return sendJson(res, 404, { error: 'no evaluation available' });
    }
  }

  // POST /api/assistant
  if (parts[1] === 'assistant' && method === 'POST') {
    const body = JSON.parse((await readBody(req)) || '{}');
    if (!body.query || typeof body.query !== 'string') return sendJson(res, 400, { error: 'query required' });
    const answer = await runAssistant(body.query, body.lang || 'zh');
    recordSearch({
      kind: 'assistant',
      query: body.query,
      lang: body.lang || 'zh',
      results: (answer.alternatives || []).length,
    });
    return sendJson(res, 200, answer);
  }

  // GET /api/assistant/route?q=...&lang=..&router=rules|llm
  // Planning only — no tools run. tools/eval_router.py scores both routers on the
  // same questions without paying for the tool calls.
  if (parts[1] === 'assistant' && parts[2] === 'route' && method === 'GET') {
    const url = new URL(req.url, 'http://localhost');
    const q = (url.searchParams.get('q') || '').trim();
    if (!q) return sendJson(res, 400, { error: 'q required' });
    const lang = url.searchParams.get('lang') === 'en' ? 'en' : 'zh';
    const which = url.searchParams.get('router') || 'rules';
    const t0 = Date.now();
    const fromLLM = which === 'llm' ? await routeWithLLM(q, lang) : null;
    const routed = fromLLM || routeQuery(q, lang);
    return sendJson(res, 200, {
      query: q,
      lang,
      requested: which,
      source: routed.source || 'rules',
      intents: routed.intents,
      tools: routed.plan.map((s) => s.tool),
      latencyMs: Date.now() - t0,
      router: routed.router || null,
    });
  }

  // GET /api/assistant/llm — is a local model configured and reachable?
  if (parts[1] === 'assistant' && parts[2] === 'llm' && method === 'GET') {
    return sendJson(res, 200, await llmHealth());
  }

  // POST /api/visual-search
  if (parts[1] === 'visual-search' && method === 'POST') {
    const body = JSON.parse((await readBody(req)) || '{}');
    const result = await runVisualSearch({
      colors: body.colors || [],
      query: body.query || '',
      image: body.image || null,
      limit: body.limit ? Number(body.limit) : 12,
    });
    // An image-only search still counts as a search, recorded as "(image)" so the
    // history shows that the shopper looked without inventing a text query.
    if (body.query || body.image) {
      recordSearch({
        kind: 'visual',
        query: body.query || '(image)',
        lang: body.lang || 'zh',
        results: (result.results || []).length,
      });
    }
    return sendJson(res, 200, result);
  }

  // ---- Search history and onboarding ---------------------------------------
  if (parts[1] === 'history') {
    if (method === 'POST' && parts[2] === 'clear') {
      return sendJson(res, 200, clearHistory());
    }
    const url = new URL(req.url, 'http://localhost');
    return sendJson(res, 200, getHistory({
      days: Number(url.searchParams.get('days')) || 30,
      limit: Number(url.searchParams.get('limit')) || 12,
    }));
  }

  if (parts[1] === 'onboarding') {
    if (method === 'POST') {
      const body = JSON.parse((await readBody(req)) || '{}');
      const answers = saveOnboarding(body);
      trackEvent({ type: 'onboarding_completed', label: 'welcome', value: answers.categories.length,
        meta: { styles: answers.styles, pairs: answers.pairs.length } });
      return sendJson(res, 200, { ok: true, onboarding: answers });
    }
    return sendJson(res, 200, { onboarded: hasOnboarded(), onboarding: getOnboarding() });
  }

  // GET /api/visual-search/status — is the CLIP service up?
  if (parts[1] === 'visual-search' && parts[2] === 'status') {
    return sendJson(res, 200, await visualSearchStatus());
  }

  // POST /api/tryon  — CatVTON synthesis (falls back to the overlay preview)
  if (parts[1] === 'tryon' && parts[2] === 'status') {
    const h = await tryOnStatus();
    return sendJson(res, 200, h
      ? { online: true, ...h }
      : { online: false, engine: 'overlay', url: process.env.TRYON_URL || 'http://127.0.0.1:8003' });
  }
  if (parts[1] === 'tryon' && method === 'POST') {
    const body = JSON.parse((await readBody(req)) || '{}');
    const result = await runTryOn({
      productId: body.productId,
      photo: body.photo || null,
      steps: Number(body.steps) || 30,
    });
    return sendJson(res, result.error ? 404 : 200, result);
  }

  // ---- Feature 1: AI scenario blind box ----------------------------------
  if (parts[1] === 'blindbox') {
    if (parts[2] === 'scenarios') {
      return sendJson(res, 200, {
        scenarios: Object.values(SCENARIOS).map((s) => ({
          id: s.id, emoji: s.emoji, label: s.label, label_zh: s.label_zh, blurb: s.blurb, blurb_zh: s.blurb_zh,
        })),
      });
    }
    if (method === 'POST') {
      const body = JSON.parse((await readBody(req)) || '{}');
      const result = buildBlindBox({
        query: body.query || '',
        scenarioId: body.scenarioId || null,
        budget: body.budget != null ? Number(body.budget) : null,
        lang: body.lang || 'zh',
        useWardrobe: body.useWardrobe !== false,
      });
      return sendJson(res, 200, result);
    }
  }

  // ---- Feature 2: cross-platform price agent ------------------------------
  if (parts[1] === 'price-agent') {
    if (parts[2] === 'platforms') return sendJson(res, 200, { platforms: PLATFORMS });
    if (method === 'POST') {
      const body = JSON.parse((await readBody(req)) || '{}');
      return sendJson(res, 200, runPriceAgent({ productIds: body.productIds || [], lang: body.lang || 'zh' }));
    }
  }

  // ---- Feature 3: second-hand consignment ---------------------------------
  if (parts[1] === 'resale') {
    if (parts[2] === 'consignable') return sendJson(res, 200, { items: consignableItems(), conditions: conditionOptions() });
    if (parts[2] === 'meta') return sendJson(res, 200, { conditions: conditionOptions(), eco: ecoSummary() });
    if (parts[2] === 'draft' && method === 'POST') {
      const body = JSON.parse((await readBody(req)) || '{}');
      const draft = draftListing({
        productId: body.productId, condition: body.condition || 'good',
        monthsOwned: body.monthsOwned != null ? Number(body.monthsOwned) : 6,
        wears: body.wears != null ? Number(body.wears) : null,
        note: body.note || '', lang: body.lang || 'zh',
      });
      return draft ? sendJson(res, 200, draft) : sendJson(res, 404, { error: 'product not found' });
    }
    if (parts[2] && parts[3] === 'buy' && method === 'POST') {
      const l = buyListing(parts[2]);
      return l ? sendJson(res, 200, l) : sendJson(res, 404, { error: 'listing not available' });
    }
    if (method === 'POST') {
      const body = JSON.parse((await readBody(req)) || '{}');
      const l = publishListing({
        productId: body.productId, condition: body.condition || 'good',
        monthsOwned: body.monthsOwned != null ? Number(body.monthsOwned) : 6,
        wears: body.wears != null ? Number(body.wears) : null,
        note: body.note || '', price: body.price != null ? Number(body.price) : null,
        lang: body.lang || 'zh',
      });
      return l ? sendJson(res, 200, l) : sendJson(res, 404, { error: 'product not found' });
    }
    return sendJson(res, 200, { listings: getListings(), eco: ecoSummary() });
  }

  // ---- Feature 4: private try-on voting -----------------------------------
  if (parts[1] === 'social') {
    if (parts[2] === 'groups') return sendJson(res, 200, { groups: GROUPS, impact: socialImpact() });
    if (parts[2] === 'polls') {
      if (parts[3] && parts[4] === 'simulate' && method === 'POST') {
        const body = JSON.parse((await readBody(req)) || '{}');
        const p = simulateVotes(parts[3], body.count != null ? Number(body.count) : null);
        return p ? sendJson(res, 200, p) : sendJson(res, 404, { error: 'poll not found' });
      }
      if (parts[3] && parts[4] === 'vote' && method === 'POST') {
        const body = JSON.parse((await readBody(req)) || '{}');
        const p = castVote(parts[3], { vote: body.vote, comment: body.comment || '', voterId: body.voterId || 'me' });
        return p ? sendJson(res, 200, p) : sendJson(res, 404, { error: 'poll not found' });
      }
      if (method === 'POST') {
        const body = JSON.parse((await readBody(req)) || '{}');
        const p = createPoll({
          productId: body.productId, groupId: body.groupId || 'bff',
          note: body.note || '', imageAttached: !!body.imageAttached,
        });
        return p ? sendJson(res, 200, p) : sendJson(res, 404, { error: 'product not found' });
      }
      return sendJson(res, 200, { polls: getPolls(), impact: socialImpact() });
    }
    if (parts[2] && method === 'GET') {
      const p = getPoll(parts[2]);
      return p ? sendJson(res, 200, p) : sendJson(res, 404, { error: 'poll not found' });
    }
  }

  // ---- Feature 5: long-term memory & personal profile ---------------------
  if (parts[1] === 'profile') {
    if (method === 'PATCH' || method === 'POST') {
      const body = JSON.parse((await readBody(req)) || '{}');
      updateProfile(body);
    }
    const url = new URL(req.url, 'http://localhost');
    const lang = url.searchParams.get('lang') || 'zh';
    return sendJson(res, 200, {
      ...getMemoryContext(),
      insights: getInsights(lang),
      coverage: [...getWardrobeCoverage()],
      currency: currencyFor(lang),
    });
  }

  if (parts[1] === 'memory' && parts[2] === 'insights') {
    const url = new URL(req.url, 'http://localhost');
    return sendJson(res, 200, { insights: getInsights(url.searchParams.get('lang') || 'zh') });
  }

  // ---- Feature 6: return-reason prediction --------------------------------
  if (parts[1] === 'return-risk') {
    const url = new URL(req.url, 'http://localhost');
    const lang = url.searchParams.get('lang') || 'zh';
    if (parts[2] === 'cart' && method === 'POST') {
      const body = JSON.parse((await readBody(req)) || '{}');
      return sendJson(res, 200, predictCartRisk(body.items || [], lang));
    }
    if (parts[2]) {
      const size = url.searchParams.get('size');
      const r = predictReturnRisk(parts[2], size, lang);
      return r ? sendJson(res, 200, r) : sendJson(res, 404, { error: 'not found' });
    }
  }

  // ---- Feature 7: smart customer service (returns) ------------------------
  if (parts[1] === 'support') {
    if (parts[2] === 'reasons') return sendJson(res, 200, { reasons: RETURN_REASONS });
    if (parts[2] === 'stats') {
      const url = new URL(req.url, 'http://localhost');
      return sendJson(res, 200, { stats: returnStats(url.searchParams.get('lang') || 'zh'), forms: getReturnForms() });
    }
    if (parts[2] === 'session' && method === 'POST') {
      const body = JSON.parse((await readBody(req)) || '{}');
      const s = startSession({ productId: body.productId, reason: body.reason || 'defect', orderId: body.orderId || null });
      return s ? sendJson(res, 200, s) : sendJson(res, 404, { error: 'product not found' });
    }
    if (parts[2] === 'analyze' && method === 'POST') {
      const body = JSON.parse((await readBody(req)) || '{}');
      const r = analyzePhoto({ sessionId: body.sessionId, features: body.features || {}, lang: body.lang || 'zh' });
      return r ? sendJson(res, 200, r) : sendJson(res, 404, { error: 'session not found' });
    }
    if (parts[2] === 'submit' && method === 'POST') {
      const body = JSON.parse((await readBody(req)) || '{}');
      const r = submitReturn({
        sessionId: body.sessionId, defect: body.defect || null, reason: body.reason || null,
        note: body.note || '', lang: body.lang || 'zh',
      });
      return r ? sendJson(res, 200, r) : sendJson(res, 404, { error: 'session not found' });
    }
  }

  // ---- Merchant analytics + exit-intent coupons ---------------------------
  // Powers the B2B merchant dashboard (3rd meeting): search volume, exit-intent
  // retention rate, coupon usage and conversion.
  if (parts[1] === 'analytics') {
    const url = new URL(req.url, 'http://localhost');
    const tenant = url.searchParams.get('tenant') || DEMO_TENANT;

    if (parts[2] === 'summary' && method === 'GET') {
      const days = Math.min(90, Math.max(1, Number(url.searchParams.get('days')) || 7));
      return sendJson(res, 200, getSummary({ tenant, days }));
    }

    if (parts[2] === 'events' && method === 'GET') {
      const limit = Number(url.searchParams.get('limit')) || 25;
      return sendJson(res, 200, { events: getRecentEvents({ tenant, limit }) });
    }

    if (parts[2] === 'coupons' && method === 'GET') {
      return sendJson(res, 200, { coupons: getCoupons({ tenant }) });
    }

    if (parts[2] === 'reset' && method === 'POST') {
      return sendJson(res, 200, resetAnalytics({ tenant }));
    }

    if (parts[2] === 'event' && method === 'POST') {
      const body = JSON.parse((await readBody(req)) || '{}');
      if (!body.type) return sendJson(res, 400, { error: 'type required' });
      if (Array.isArray(body.events)) {
        for (const e of body.events) trackEvent({ tenant, session: e.session || body.session || null, type: e.type, label: e.label, value: e.value, meta: e.meta });
      } else {
        trackEvent({
          tenant, session: body.session || null, type: body.type,
          label: body.label == null ? null : body.label,
          value: body.value == null ? null : Number(body.value),
          meta: body.meta || null,
        });
      }
      return sendJson(res, 200, { ok: true });
    }

    // POST /api/analytics/coupon            -> issue a new coupon
    // POST /api/analytics/coupon/apply      -> mark it used
    // GET  /api/analytics/coupon/:code      -> validate one
    if (parts[2] === 'coupon') {
      if (parts[3] === 'apply' && method === 'POST') {
        const body = JSON.parse((await readBody(req)) || '{}');
        if (!body.code) return sendJson(res, 400, { error: 'code required' });
        const r = applyCoupon(String(body.code).trim().toUpperCase(), { tenant, session: body.session || null });
        return sendJson(res, r.ok ? 200 : 404, r);
      }
      if (method === 'POST') {
        const body = JSON.parse((await readBody(req)) || '{}');
        const pct = Math.min(50, Math.max(1, Number(body.discountPct) || 10));
        return sendJson(res, 200, issueCoupon({
          tenant, session: body.session || null, discountPct: pct,
          source: body.source || 'exit-intent',
        }));
      }
      if (parts[3] && method === 'GET') {
        const c = getCoupon(String(parts[3]).toUpperCase(), { tenant });
        return c ? sendJson(res, 200, { valid: true, coupon: c }) : sendJson(res, 404, { valid: false });
      }
    }
  }

  // ---- Embeddable widget: per-tenant branding ------------------------------
  if (parts[1] === 'widget' && parts[2] === 'config') {
    const url = new URL(req.url, 'http://localhost');
    const tenant = url.searchParams.get('tenant') || DEMO_TENANT;
    const known = {
      'smartmall-demo': 'SmartMall',
      'thread-and-stone': 'THREAD & STONE',
    };
    return sendJson(res, 200, {
      tenant,
      // Unknown tenants get a readable default rather than an error, so the
      // script tag never fails on an unregistered store during a demo.
      storeName: known[tenant] || tenant.replace(/[-_]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      onboarded: Boolean(known[tenant]),
      features: ['assistant', 'visual-search'],
    });
  }

  // ---- O2O: physical store stock and pickup ------------------------------
  if (parts[1] === 'stores') {
    if (!parts[2]) {
      return sendJson(res, 200, { stores: getStores(), pickup: pickupInfo() });
    }
    if (parts[2] === 'stock' && parts[3]) {
      if (!getProduct(parts[3])) return sendJson(res, 404, { error: 'product not found' });
      const url = new URL(req.url, 'http://localhost');
      const lat = Number(url.searchParams.get('lat'));
      const lng = Number(url.searchParams.get('lng'));
      const origin = Number.isFinite(lat) && Number.isFinite(lng) && (lat || lng)
        ? { lat, lng } : null;
      return sendJson(res, 200, availability(parts[3], origin));
    }
    if (parts[2] === 'one' && parts[3]) {
      const s = getStore(parts[3]);
      return s ? sendJson(res, 200, s) : sendJson(res, 404, { error: 'not found' });
    }
  }

  // ---- Preference survey: pay for information -----------------------------
  // A few pairwise questions ("which would you wear?") reward a HK$1-10 coupon
  // whose value scales with how much the answers actually taught the model.
  if (parts[1] === 'survey') {
    if (method === 'GET' && parts[2] === 'profile') {
      return sendJson(res, 200, profileSummary());
    }
    if (method === 'POST' && parts[2] === 'start') {
      const body = JSON.parse((await readBody(req)) || '{}');
      return sendJson(res, 200, startSurvey({
        lang: body.lang || 'zh',
        n: Number(body.n) || 3,
        session: body.session || null,
      }));
    }
    if (method === 'POST' && parts[2] === 'answer') {
      const body = JSON.parse((await readBody(req)) || '{}');
      const r = answerSurvey({
        sessionId: body.sessionId, questionId: body.questionId,
        choice: body.choice, session: body.session || null,
      });
      return sendJson(res, r.ok ? 200 : 400, r);
    }
    if (method === 'POST' && parts[2] === 'finish') {
      const body = JSON.parse((await readBody(req)) || '{}');
      const r = finishSurvey({ sessionId: body.sessionId, session: body.session || null });
      return sendJson(res, r.ok ? 200 : 400, r);
    }
    if (method === 'POST' && parts[2] === 'spin') {
      const body = JSON.parse((await readBody(req)) || '{}');
      const r = spinSurvey({ sessionId: body.sessionId, session: body.session || null });
      return sendJson(res, r.ok ? 200 : 400, r);
    }
    if (method === 'POST' && parts[2] === 'reset') {
      return sendJson(res, 200, resetSurvey());
    }
  }

  // ---- Fashion AesRec score: does today's outfit suit this shopper? --------
  if (parts[1] === 'aesthetic') {
    if (method === 'GET' && parts[2] === 'status') {
      return sendJson(res, 200, await aestheticStatus());
    }
    if (method === 'POST' && parts[2] === 'score') {
      const body = JSON.parse((await readBody(req)) || '{}');
      if (!body.image) return sendJson(res, 400, { error: 'image required' });
      const url = new URL(req.url, 'http://localhost');
      const out = await scoreOutfit(body.image, { lang: url.searchParams.get('lang') || 'zh' });
      return sendJson(res, out.online ? 200 : 503, out);
    }
  }

  return sendJson(res, 404, { error: 'unknown endpoint' });
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const pathname = url.pathname;

  if (pathname.startsWith('/api/')) {
    try {
      await handleApi(req, res, pathname);
    } catch (err) {
      sendJson(res, 500, { error: err.message || 'server error' });
    }
    return;
  }

  await serveStatic(req, res, pathname === '/' ? '/index.html' : pathname);
});

// Bind to every interface by default so phones and friends on the same network
// (or on a VPN such as Tailscale) can reach the demo. Override with HOST=127.0.0.1
// to keep it local-only.
const HOST = process.env.HOST || '0.0.0.0';

server.listen(PORT, HOST, () => {
  const urls = [{ label: 'Local', url: `http://localhost:${PORT}` }];
  const nets = networkInterfaces();
  for (const [name, addrs] of Object.entries(nets)) {
    for (const a of addrs || []) {
      if (a.family !== 'IPv4' || a.internal) continue;
      const isVpn = /tailscale|wireguard|zerotier|nordlynx/i.test(name);
      const isVirtual = /vEthernet|Hyper-V|VirtualBox|VMware|Loopback|WSL|Bluetooth|Direct/i.test(name);
      urls.push({
        label: isVpn ? `${name} (VPN — works anywhere)` : isVirtual ? `${name} (virtual — skip)` : `${name} (same Wi-Fi)`,
        url: `http://${a.address}:${PORT}`,
        virtual: isVirtual,
      });
    }
  }

  console.log('\n  SmartMall is running');
  console.log(`  Bound to ${HOST}:${PORT}\n`);

  // Load the local model now rather than on the first question: a cold completion
  // takes ~53 s, which would exceed the classification timeout and silently fall
  // back. Fire-and-forget so startup is never blocked by a slow model.
  if (process.env.ASSISTANT_LLM === '1' || process.env.ASSISTANT_LLM === 'true') {
    warmLLM().then((r) => {
      console.log(r.warmed
        ? `  llm      ${r.model} warm in ${(r.ms / 1000).toFixed(1)}s`
        : `  llm      warmup skipped (${r.reason}) — the rule router will answer`);
    });
  }
  for (const u of urls) console.log(`  ${u.label.padEnd(34)} ${u.url}`);
  console.log('\n  Share a "same Wi-Fi" URL with friends on your network, or the');
  console.log('  Tailscale URL with friends who have joined your tailnet.');
  console.log('\n  Windows may ask to allow Node.js through the firewall the first time.');
  console.log('  Press Ctrl+C to stop\n');
});
