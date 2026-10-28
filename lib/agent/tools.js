// lib/agent/tools.js
// The tool layer the assistant is allowed to call.
//
// Design rule: a tool returns *facts* — small labelled values — and the answer
// composer may only quote numbers that appear in `facts`. That is what makes the
// assistant immune to invented prices, stock counts or dates: there is no path
// from the language model (or the rule engine) to a number that did not come
// from the catalogue, the forecast model or the store database.
import { getProducts, getProduct } from '../store.js';
import { forecastProduct } from '../forecast.js';
import { availability, getStores, pickupInfo } from '../stores.js';
import { predictReturnRisk } from '../returnPredict.js';
import { buildBlindBox, detectScenario } from '../blindbox.js';
import { getMemoryContext } from '../memory.js';

const norm = (s) => String(s || '').toLowerCase();

function haystack(p) {
  return norm([
    p.name, p.name_zh, p.brand, p.category, p.subcategory, p.colorName, p.material,
    (p.tags || []).join(' '), p.description_zh, p.description,
  ].join(' '));
}

/**
 * Term extraction that works for Chinese as well as English.
 *
 * Chinese is written without spaces, so whitespace tokenisation turns a whole
 * sentence like "滑雪外套會唔會減價" into one unmatchable token. We therefore keep
 * latin words and add CJK character bigrams, which is crude but matches garment
 * vocabulary (外套, 連身, 亞麻) well enough at this catalogue size.
 */
function terms(query) {
  const latin = norm(query).split(/[\s,，、。?？!！/]+/).filter((t) => /[a-z0-9]/.test(t) && t.length > 1);
  const cjk = (String(query).match(/[\u4e00-\u9fff]+/g) || []).join('');
  const bigrams = [];
  for (let i = 0; i < cjk.length - 1; i++) bigrams.push(cjk.slice(i, i + 2));
  return [...new Set([...latin, ...bigrams])];
}

/** Bilingual keyword search with a light field weighting. */
export function searchProducts({ query = '', category = null, maxPrice = null, limit = 6 } = {}) {
  const tokens = terms(query);
  const scored = [];
  for (const p of getProducts()) {
    if (category && norm(p.category) !== norm(category)) continue;
    if (maxPrice != null && p.price > maxPrice) continue;
    const hay = haystack(p);
    const nameHay = `${norm(p.name_zh)} ${norm(p.name)}`;
    let score = 0;
    for (const t of tokens) {
      if (!t) continue;
      if (nameHay.includes(t)) score += 6;
      else if (norm(p.category).includes(t) || norm(p.subcategory).includes(t)) score += 4;
      else if (norm(p.colorName).includes(t) || norm(p.material).includes(t)) score += 3;
      else if (hay.includes(t)) score += 1;
    }
    if (score > 0) scored.push({ product: p, score });
  }
  scored.sort((a, b) => b.score - a.score || b.product.rating - a.product.rating);
  return scored.slice(0, limit);
}

function money(p, lang) {
  const rate = lang === 'en' ? 1 : 7.8;
  const sym = lang === 'en' ? 'US$' : 'HK$';
  const v = p.price * rate;
  return `${sym}${v.toLocaleString(lang === 'en' ? 'en-US' : 'zh-HK', { maximumFractionDigits: 0 })}`;
}

const pname = (p, lang) => (lang === 'en' ? (p.name || p.name_zh) : (p.name_zh || p.name));

export const TOOL_SPECS = {
  search_products: {
    description: 'Find products matching a free-text query, optionally by category or budget.',
    params: ['query', 'category', 'maxPrice', 'limit'],
  },
  check_store_stock: {
    description: 'Online stock plus per-store stock and pickup guidance for one product.',
    params: ['productId', 'lat', 'lng'],
  },
  forecast_price: {
    description: '30-day Prophet price forecast and a Buy Now / Wait recommendation.',
    params: ['productId', 'horizon'],
  },
  size_advice: {
    description: 'Return-risk based size recommendation for one product.',
    params: ['productId', 'size'],
  },
  build_outfit: {
    description: 'Assemble a complete outfit for a scenario and budget.',
    params: ['query', 'budget'],
  },
  list_stores: {
    description: 'All physical stores, optionally filtered by district.',
    params: ['district'],
  },
  recall_wardrobe: {
    description: 'What the shopper already owns, so a look can be built around it.',
    params: ['limit'],
  },
};

/**
 * Execute one tool.
 * @returns {Promise<{tool:string, ok:boolean, data:any, facts:Array<{label:string,value:string}>, ms:number}>}
 */
export async function runTool(name, params = {}, ctx = {}) {
  const { lang = 'zh' } = ctx;
  const started = Date.now();
  const facts = [];
  let data = null;

  switch (name) {
    case 'search_products': {
      const hits = searchProducts(params);
      data = hits.map((h) => ({ ...h.product, _score: h.score }));
      if (hits.length) {
        facts.push({ label: 'matches', value: String(hits.length) });
        facts.push({ label: 'top', value: pname(hits[0].product, lang) });
        facts.push({ label: 'topPrice', value: money(hits[0].product, lang) });
        facts.push({ label: 'topRating', value: String(hits[0].product.rating) });
      } else {
        facts.push({ label: 'matches', value: '0' });
      }
      break;
    }

    case 'check_store_stock': {
      const a = availability(params.productId, params.lat != null && params.lng != null
        ? { lat: params.lat, lng: params.lng } : null);
      data = a;
      facts.push({ label: 'onlineStock', value: String(a.onlineStock) });
      facts.push({ label: 'storeCount', value: String(a.storeCount) });
      facts.push({ label: 'totalStoreQty', value: String(a.totalStoreQty) });
      facts.push({ label: 'status', value: a.status });
      const best = a.stores.filter((s) => s.qty > 0).slice(0, 3);
      if (best.length) {
        facts.push({
          label: 'stores',
          value: best.map((s) => `${lang === 'en' ? s.name_en : s.name_zh}(${s.qty})`).join('、'),
        });
        facts.push({ label: 'nearestStore', value: lang === 'en' ? best[0].name_en : best[0].name_zh });
        facts.push({ label: 'nearestMtr', value: lang === 'en' ? best[0].mtr_en : best[0].mtr_zh });
      }
      const pk = pickupInfo();
      facts.push({ label: 'pickup', value: lang === 'en' ? pk.sameDay_en : pk.sameDay });
      break;
    }

    case 'forecast_price': {
      const f = await forecastProduct(params.productId, { horizon: params.horizon || 30 });
      data = f;
      if (f) {
        facts.push({ label: 'current', value: f.current });
        facts.push({ label: 'action', value: f.advisory.action });
        facts.push({ label: 'dropPct', value: String(f.advisory.expectedDropPct) });
        facts.push({ label: 'confidence', value: f.advisory.confidence });
        facts.push({ label: 'engine', value: f.engine || 'linear' });
        facts.push({ label: 'horizonDays', value: String(f.horizonDays || 30) });
        for (const ev of (f.events || []).slice(0, 2)) {
          facts.push({
            label: `event:${ev.name}`,
            value: `${ev.label} ${ev.daysAway}d ${ev.predictedPrice} (-${ev.dropPct}%)`,
          });
        }
      }
      break;
    }

    case 'size_advice': {
      const r = predictReturnRisk(params.productId, params.size || null, lang);
      data = r;
      if (r) {
        facts.push({ label: 'recommendedSize', value: r.recommendedSize || r.size || '—' });
        facts.push({ label: 'riskLevel', value: r.riskLevel || r.level || '—' });
        if (r.riskPct != null) facts.push({ label: 'returnRiskPct', value: String(r.riskPct) });
        if (r.note_zh || r.note) facts.push({ label: 'note', value: lang === 'en' ? r.note : r.note_zh });
      }
      break;
    }

    case 'build_outfit': {
      const scenario = detectScenario(params.query || '');
      const box = buildBlindBox({
        query: params.query || '',
        scenarioId: scenario?.id || null,
        budget: params.budget || null,
        lang,
      });
      data = box;
      if (box) {
        // All money is emitted pre-formatted in the display currency, so the
        // composer never does arithmetic and every number it prints is a fact.
        const usd = (v) => {
          const rate = lang === 'en' ? 1 : 7.8;
          const sym = lang === 'en' ? 'US$' : 'HK$';
          return `${sym}${Math.round(v * rate).toLocaleString(lang === 'en' ? 'en-US' : 'zh-HK')}`;
        };
        facts.push({ label: 'items', value: String((box.items || []).length) });
        if (box.total != null) {
          facts.push({ label: 'total', value: String(box.total) });
          facts.push({ label: 'totalDisplay', value: usd(box.total) });
        }
        if (box.scenario) facts.push({ label: 'scenario', value: box.scenario.title_zh || box.scenario.title || '' });
        // The minimum cost of a complete kit matters: when the shopper's budget is
        // below it the honest answer is "your budget is short", not a one-item look.
        if (box.minEssential != null) {
          facts.push({ label: 'minEssential', value: String(box.minEssential) });
          facts.push({ label: 'minEssentialDisplay', value: usd(box.minEssential) });
        }
        if (Array.isArray(box.missing)) facts.push({ label: 'missing', value: String(box.missing.length) });
        if (box.coverage != null) facts.push({ label: 'coverage', value: String(box.coverage) });
        if (params.budget != null) {
          facts.push({ label: 'budget', value: String(params.budget) });
          facts.push({ label: 'budgetDisplay', value: usd(params.budget) });
          facts.push({
            label: 'shortfall',
            value: box.minEssential != null && box.minEssential > params.budget ? 'yes' : 'no',
          });
        }
      }
      break;
    }

    case 'list_stores': {
      const all = getStores();
      const filtered = params.district
        ? all.filter((s) => norm(s.district_zh).includes(norm(params.district))
          || norm(s.district_en).includes(norm(params.district)))
        : all;
      data = filtered;
      facts.push({ label: 'storeCount', value: String(filtered.length) });
      facts.push({
        label: 'districts',
        value: filtered.map((s) => (lang === 'en' ? s.district_en : s.district_zh)).join('、'),
      });
      break;
    }

    case 'recall_wardrobe': {
      const ctx = getMemoryContext();
      const items = (ctx.wardrobe || []).slice(0, params.limit || 6);
      data = items;
      facts.push({ label: 'ownedCount', value: String(items.length) });
      if (items.length) {
        const first = items[0];
        facts.push({ label: 'recent', value: lang === 'en' ? (first.name || first.name_zh) : (first.name_zh || first.name) });
        facts.push({ label: 'recentMonths', value: String(first.monthsAgo) });
        facts.push({ label: 'recentSize', value: String(first.size || '—') });
      }
      break;
    }

    default:
      return { tool: name, ok: false, data: null, facts: [], ms: 0, error: 'unknown tool' };
  }

  return { tool: name, ok: data != null, data, facts, ms: Date.now() - started };
}

export { getProduct };
