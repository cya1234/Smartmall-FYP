// js/cart.js — client-side cart persisted in localStorage (keys are product ids).
import { track } from './exitIntent.js';

const KEY = 'smartmall-cart-v1';

export function getCart() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || {};
  } catch {
    return {};
  }
}

function save(cart) {
  localStorage.setItem(KEY, JSON.stringify(cart));
  updateBadge();
}

export function addToCart(id, qty = 1) {
  const c = getCart();
  c[id] = (c[id] || 0) + qty;
  save(c);
  // Feeds the merchant dashboard's add-to-cart rate.
  try { track('add_to_cart', id, qty); } catch { /* analytics is best-effort */ }
}

export function setQty(id, qty) {
  const c = getCart();
  if (qty <= 0) delete c[id];
  else c[id] = qty;
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
  return Object.values(getCart()).reduce((a, b) => a + b, 0);
}

export function cartLines() {
  return Object.entries(getCart()).map(([id, qty]) => ({ id, qty }));
}

export function updateBadge() {
  const el = document.getElementById('cart-count');
  if (el) el.textContent = String(cartCount());
}
