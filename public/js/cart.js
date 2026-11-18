// js/cart.js — client-side cart persisted in localStorage.
//
// Shape: { productId: { qty, size } }. Older carts stored a bare number, so every
// read normalises; nothing needs a migration step.
//
// The size lives here because the product page lets the shopper pick one and the
// prediction is only meaningful if that choice survives into the cart — without it
// the site showed the recommended size and silently discarded the real one.
import { track } from './exitIntent.js';

const KEY = 'smartmall-cart-v1';

function normalise(raw) {
  const out = {};
  for (const [id, v] of Object.entries(raw || {})) {
    if (typeof v === 'number') out[id] = { qty: v, size: null };
    else if (v && typeof v === 'object') {
      const qty = Number(v.qty) || 0;
      if (qty > 0) out[id] = { qty, size: v.size || null };
    }
  }
  return out;
}

export function getCart() {
  try {
    return normalise(JSON.parse(localStorage.getItem(KEY)));
  } catch {
    return {};
  }
}

function save(cart) {
  localStorage.setItem(KEY, JSON.stringify(cart));
  updateBadge();
}

export function addToCart(id, qty = 1, size = null) {
  const c = getCart();
  const line = c[id] || { qty: 0, size: null };
  // Adding the same product again keeps whichever size was chosen last.
  c[id] = { qty: line.qty + qty, size: size || line.size || null };
  save(c);
  // Feeds the merchant dashboard's add-to-cart rate.
  try { track('add_to_cart', id, qty); } catch { /* analytics is best-effort */ }
}

export function setQty(id, qty) {
  const c = getCart();
  if (qty <= 0) delete c[id];
  else c[id] = { qty, size: c[id]?.size || null };
  save(c);
}

export function setSize(id, size) {
  const c = getCart();
  if (!c[id]) return;
  c[id] = { qty: c[id].qty, size };
  save(c);
}

export function removeFromCart(id) {
  const c = getCart();
  delete c[id];
  save(c);
}

export function clearCart() {
  save({});
}

export function cartCount() {
  return Object.values(getCart()).reduce((a, l) => a + l.qty, 0);
}

export function cartQty(id) {
  return getCart()[id]?.qty || 0;
}

export function cartLines() {
  return Object.entries(getCart()).map(([id, l]) => ({ id, qty: l.qty, size: l.size }));
}

export function updateBadge() {
  const el = document.getElementById('cart-count');
  if (el) el.textContent = String(cartCount());
}
