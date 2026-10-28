// js/ui.js — shared rendering helpers (i18n + currency aware).
import { t, bi, money, currency, isZh } from './i18n.js';

export function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export const fmtPrice = (usd) => money(usd);

// "#rrggbb" -> "rgba(r,g,b,a)"
export function hexA(hex, alpha) {
  const h = (hex || '#888888').replace('#', '');
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export function toast(msg) {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 2400);
}

export const pName = (p) => (p ? bi(p, 'name') : '');
export const pDesc = (p) => (p ? bi(p, 'description') : '');

// Product imagery: real CLIP-indexed photo when we have one, emoji otherwise.
export function mediaInner(p, fallbackFont = '2.6rem') {
  return p && p.image
    ? `<img class="prod-img" src="${esc(p.image)}" alt="${esc(pName(p))}" loading="lazy" />`
    : `<span style="font-size:${fallbackFont}">${p ? p.emoji : ''}</span>`;
}

export function thumbHTML(p, size = '4rem') {
  return `<div class="product-thumb ${p.image ? 'has-photo' : ''}" style="background:linear-gradient(135deg, ${hexA(p.color, 0.14)}, ${hexA(p.color, 0.3)})">
    <span class="badge-cat">${esc(p.subcategory)}</span>
    ${mediaInner(p, size)}
  </div>`;
}

export function productCard(p) {
  return `<article class="product-card" data-id="${esc(p.id)}" role="link" tabindex="0" aria-label="${esc(pName(p))}">
    ${thumbHTML(p)}
    <div class="product-body">
      <div class="product-brand">${esc(p.brand)}</div>
      <div class="product-name">${esc(pName(p))}</div>
      <div class="product-meta">
        <span class="price">${fmtPrice(p.price)}</span>
        <span class="rating">★ ${p.rating}</span>
      </div>
    </div>
  </article>`;
}

export function spinner(dark = false) {
  return `<span class="spinner${dark ? ' dark' : ''}"></span>`;
}

export function emptyState(emoji, title, sub) {
  return `<div class="empty"><div class="e">${emoji}</div><h3>${esc(title)}</h3><p>${esc(sub)}</p></div>`;
}

// Compact tile used by bundles, kits and listings.
export function itemTile({ product, roleLabel, note, owned, priceLabel, badge, clickable }) {
  return `<div class="set-item ${owned ? 'is-owned' : ''}" ${clickable ? `data-id="${esc(product.id)}"` : ''} style="${clickable ? 'cursor:pointer' : ''}">
    ${owned
      ? `<span class="owned-flag">${esc(t('common.owned'))}</span>`
      : (badge ? `<span class="owned-flag" style="background:var(--brand)">${esc(badge)}</span>` : '')}
    <div class="thumb" style="background:linear-gradient(135deg, ${hexA(product.color, 0.14)}, ${hexA(product.color, 0.3)})">${mediaInner(product, '2.6rem')}</div>
    <div class="body">
      ${roleLabel ? `<div class="role">${esc(roleLabel)}</div>` : ''}
      <div class="nm">${esc(pName(product))}</div>
      <div class="pr">${owned
        ? `<span class="owned-strike">${fmtPrice(product.price)}</span> <span style="color:var(--good)">${esc(t('common.owned'))}</span>`
        : (priceLabel || fmtPrice(product.price))}</div>
      ${note ? `<div class="note">${esc(note)}</div>` : ''}
    </div>
  </div>`;
}

export function agoLabel(monthsAgo) {
  if (monthsAgo === 0) return t('mem.thisMonth');
  return isZh() ? `${monthsAgo} ${t('mem.monthsAgo')}` : `${monthsAgo} ${t('mem.monthsAgo')}`;
}

export { t, bi, money, currency, isZh };
