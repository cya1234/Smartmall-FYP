// lib/stores.js
// Physical-store stock and pickup guidance (the O2O module).
//
// Online stock and per-store stock are derived deterministically from the
// product/store id, so the demo is reproducible without shipping a separate
// inventory database. In production both numbers come from the merchant's POS /
// warehouse feed; only this file changes.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const STORES = JSON.parse(readFileSync(join(__dirname, '..', 'data', 'stores.json'), 'utf8'));

function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

// ~18% of SKUs are out of stock in the online warehouse, which is exactly the
// situation the O2O module exists to rescue.
export function onlineStock(productId) {
  const raw = hash(`${productId}:online`) % 100;
  if (raw < 18) return 0;
  return (hash(`${productId}:online:qty`) % 15) + 1;
}

export function storeStock(storeId, productId) {
  const h = hash(`${productId}:${storeId}`);
  return h % 100 < 55 ? (h % 5) + 1 : 0;
}

export function getStores() {
  return STORES.map((s) => ({ ...s }));
}

export function getStore(storeId) {
  return STORES.find((s) => s.id === storeId) || null;
}

// Haversine distance in km.
export function distanceKm(a, b) {
  const R = 6371;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return Math.round(2 * R * Math.asin(Math.sqrt(h)) * 10) / 10;
}

/**
 * Full availability picture for one product.
 * @param {string} productId
 * @param {{lat?:number,lng?:number}} [origin] shopper position, if known
 */
export function availability(productId, origin = null) {
  const stores = STORES.map((s) => {
    const qty = storeStock(s.id, productId);
    const row = {
      id: s.id,
      name_zh: s.name_zh,
      name_en: s.name_en,
      district_zh: s.district_zh,
      district_en: s.district_en,
      address_zh: s.address_zh,
      address_en: s.address_en,
      mtr_zh: s.mtr_zh,
      mtr_en: s.mtr_en,
      hours: s.hours,
      phone: s.phone,
      lat: s.lat,
      lng: s.lng,
      pickup: s.pickup,
      flagship: s.flagship,
      qty,
    };
    if (origin && Number.isFinite(origin.lat) && Number.isFinite(origin.lng)) {
      row.distanceKm = distanceKm(origin, s);
    }
    return row;
  });

  if (origin) stores.sort((a, b) => (a.distanceKm ?? 1e9) - (b.distanceKm ?? 1e9));

  const inStock = stores.filter((s) => s.qty > 0);
  const online = onlineStock(productId);

  return {
    productId,
    onlineStock: online,
    onlineInStock: online > 0,
    storeCount: inStock.length,
    totalStoreQty: inStock.reduce((n, s) => n + s.qty, 0),
    totalQty: online + inStock.reduce((n, s) => n + s.qty, 0),
    // The headline the storefront shows.
    status: online > 0 ? 'online' : inStock.length ? 'store-only' : 'sold-out',
    stores,
  };
}

export function pickupInfo() {
  return {
    cutoffHour: 18,
    sameDay: '即日門市取貨（下午 6 點前下單）',
    sameDay_en: 'Same-day store pickup (order before 6 pm)',
    holdDays: 3,
    holdDays_zh: '取貨保留 3 天',
    holdDays_en: 'Held for 3 days',
    freeThreshold: 0,
  };
}
