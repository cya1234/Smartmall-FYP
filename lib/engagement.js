// lib/engagement.js
// Turn the shopper's clicks into a ranking nudge.
//
// The welcome survey says what someone *claims* to like; this says what they actually
// open. Both feed the same place — the product search score — but they answer
// different questions, so they are kept separate rather than merged into one number.
//
// Category level, not product level, on purpose. A single extra view of one jacket is
// noise; "this shopper keeps opening outerwear" is a pattern. It also avoids a
// rich-get-richer loop where the top-ranked item is clicked because it is top-ranked.
import { engagementSummary } from './analytics.js';

const TTL_MS = 60000;
const WEIGHT = 0.20;      // how much attention can move a product, at most ±20 %
const SCALE = 8;          // attention needed to get halfway to that ceiling

let cache = { at: 0, data: null };

function summary({ force = false } = {}) {
  const now = Date.now();
  if (!force && cache.data && now - cache.at < TTL_MS) return cache.data;
  try {
    cache = { at: now, data: engagementSummary({ days: 30 }) };
  } catch {
    cache = { at: now, data: { byCategory: [], byProduct: [], totals: {}, days: 30 } };
  }
  return cache.data;
}

/**
 * The curve on its own, so it can be tested without a database.
 * 0 attention -> exactly 1; monotonic; never exceeds 1 + WEIGHT.
 */
export function boostFor(score) {
  const n = Number(score) || 0;
  if (n <= 0) return 1;
  return 1 + WEIGHT * Math.tanh(n / SCALE);
}

/**
 * Multiplier for a product's search score, centred on 1.
 * tanh keeps it bounded, so no amount of clicking can bury everything else.
 */
export function attentionBoost(product) {
  if (!product || !product.category) return 1;
  const row = summary().byCategory.find((c) => c.category === product.category);
  return row ? boostFor(row.score) : 1;
}

/** What the shopper has been looking at, for the 我的 page. */
export function attention({ limit = 4 } = {}) {
  const s = summary();
  return {
    days: s.days,
    dominant: s.byCategory.length
      ? {
        category: s.byCategory[0].category,
        share: s.byCategory[0].score / s.byCategory.reduce((n, c) => n + c.score, 0),
      }
      : null,
    categories: s.byCategory.slice(0, limit),
    products: s.byProduct.slice(0, limit),
    totals: s.totals,
  };
}

export function resetCache() {
  cache = { at: 0, data: null };
}
