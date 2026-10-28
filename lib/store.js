// lib/store.js
// Catalog + user-profile store.
//
// Loads the product catalog (with deterministic price history) and the demo
// user profile that powers the long-term-memory, return-prediction and
// personalisation features. Everything is held in memory, so runtime changes
// (profile edits, resale listings, polls) persist for the life of the server.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA = join(__dirname, '..', 'data');
const PRODUCTS_PATH = join(DATA, 'products.json');
const PROFILE_PATH = join(DATA, 'profile.json');

// Deterministic PRNG (mulberry32) so generated data is reproducible.
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function hashString(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function seededRandom(key) {
  return mulberry32(hashString(key));
}

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;
const MONTH_MS = 30 * 24 * 60 * 60 * 1000;

// --- Price history ---------------------------------------------------------
function generatePriceHistory(product) {
  const rand = mulberry32(hashString(product.id));
  const pick = rand();
  let trend; // weekly drift fraction
  let noise;
  if (pick < 0.35) {
    trend = -0.018; // declining: forecast will suggest "wait for a drop"
    noise = 0.012;
  } else if (pick < 0.6) {
    trend = 0.016; // rising: "buy now"
    noise = 0.012;
  } else if (pick < 0.85) {
    trend = 0.0015; // flat/stable
    noise = 0.006;
  } else {
    trend = 0.0; // volatile
    noise = 0.035;
  }

  const weeks = 12;
  const raw = [product.price];
  // Build forward from a synthetic start, then scale so the final point equals current price.
  for (let i = 1; i < weeks; i++) {
    const step = trend + (rand() - 0.5) * 2 * noise;
    raw.push(raw[i - 1] * (1 + step));
  }
  const scale = product.price / raw[raw.length - 1];
  const now = Date.now();
  return raw.map((p, i) => ({
    t: now - (weeks - 1 - i) * WEEK_MS,
    price: Math.round(p * scale * 100) / 100,
  }));
}

// --- Catalog ---------------------------------------------------------------
function loadProducts() {
  const products = JSON.parse(readFileSync(PRODUCTS_PATH, 'utf8'));
  return products.map((p) => ({
    ...p,
    priceHistory: generatePriceHistory(p),
    slots: p.slots || [],
    fit: p.fit || { runs: 'true', stretch: 'none' },
    returnRate: p.returnRate ?? 10,
  }));
}

export const products = loadProducts();
export const byId = new Map(products.map((p) => [p.id, p]));

export function getProducts() {
  return products;
}

export function getProduct(id) {
  return byId.get(id) || null;
}

// --- User profile ----------------------------------------------------------
function loadProfile() {
  const raw = JSON.parse(readFileSync(PROFILE_PATH, 'utf8'));
  const now = Date.now();

  const expand = (entry) => {
    const product = byId.get(entry.productId) || null;
    const monthsAgo = entry.monthsAgo ?? 0;
    return {
      ...entry,
      product,
      purchasedAt: new Date(now - monthsAgo * MONTH_MS).toISOString(),
      purchasedLabel: monthsAgo === 0 ? '本月' : `${monthsAgo} 個月前`,
      purchasedLabel_en: monthsAgo === 0 ? 'this month' : `${monthsAgo} month${monthsAgo > 1 ? 's' : ''} ago`,
    };
  };

  return {
    ...raw,
    wardrobe: raw.wardrobe.map(expand),
    returns: raw.returns.map(expand),
    searchHistory: (raw.searchHistory || []).map(expand),
  };
}

export const profile = loadProfile();

export function getProfile() {
  return profile;
}

export function getWardrobe() {
  return profile.wardrobe.filter((w) => w.product);
}

export function getReturns() {
  return profile.returns.filter((r) => r.product);
}

export function updateProfile(patch) {
  if (patch.sizes) Object.assign(profile.user.sizes, patch.sizes);
  if (patch.body) Object.assign(profile.user.body, patch.body);
  if (patch.fitPreference) profile.user.fitPreference = patch.fitPreference;
  if (patch.stylePreferences) profile.user.stylePreferences = patch.stylePreferences;
  if (patch.favoriteColors) profile.user.favoriteColors = patch.favoriteColors;
  if (patch.dislikedColors) profile.user.dislikedColors = patch.dislikedColors;
  return profile;
}

// --- Currency --------------------------------------------------------------
// Base prices are stored in USD; the UI converts for display.
export const CURRENCIES = {
  USD: { code: 'USD', symbol: 'US$', rate: 1 },
  HKD: { code: 'HKD', symbol: 'HK$', rate: 7.8 },
};

export function currencyFor(lang) {
  return lang === 'en' ? CURRENCIES.USD : CURRENCIES.HKD;
}

export function convert(usdAmount, code = 'HKD') {
  const c = CURRENCIES[code] || CURRENCIES.HKD;
  return Math.round(usdAmount * c.rate * 100) / 100;
}
