// js/views/cart.js — shopping cart view (return-risk prediction + exit-intent coupon).
import { getCart, setQty, removeFromCart, clearCart, cartLines, updateBadge } from '../cart.js';
import { fmtPrice, emptyState, toast, pName, esc, t, isZh, mediaInner } from '../ui.js';
import { postJSON } from '../api.js';
import { getClaimedCoupon, track } from '../exitIntent.js';

// Remembered across re-renders so changing the delivery option feels instant.
let cartDelivery = 'sf';

export async function render(root, ctx) {
  const lines = cartLines()
    .map((l) => ({ ...l, product: ctx.products.find((p) => p.id === l.id) }))
    .filter((l) => l.product);

  if (!lines.length) {
    root.innerHTML = `<section class="container">${emptyState('🛒', isZh() ? '購物車是空的' : 'Your cart is empty', isZh() ? '試試造型盒，一次幫你配好整套。' : 'Try the Style Box to assemble a full kit.')}<div style="text-align:center;margin-top:10px"><button class="btn btn-primary" data-shop>${esc(t('nav.shop'))}</button></div></section>`;
    root.querySelector('[data-shop]').addEventListener('click', () => ctx.navigate('/shop'));
    return;
  }

  const coupon = getClaimedCoupon();
  const subtotal = lines.reduce((s, l) => s + l.product.price * l.qty, 0);
  const discount = coupon ? Math.round(subtotal * (coupon.discountPct / 100) * 100) / 100 : 0;
  const net = Math.max(0, subtotal - discount);

  // Hong Kong delivery options (fees stored in USD, shown in the active currency).
  const DELIVERY = [
    { id: 'sf', zh: '順豐站 / 智能櫃', en: 'SF station / locker', fee: 3.85, freeOver: 77, eta: isZh() ? '1–2 個工作日' : '1–2 working days' },
    { id: 'home', zh: '送貨上門', en: 'Home delivery', fee: 6.4, freeOver: 110, eta: isZh() ? '1–3 個工作日' : '1–3 working days' },
    { id: 'pickup', zh: '門市自取', en: 'Store pickup', fee: 0, freeOver: 0, eta: isZh() ? '即日（下午 6 點前下單）' : 'Same day (before 6 pm)' },
  ];
  const chosen = DELIVERY.find((d) => d.id === cartDelivery) || DELIVERY[0];
  const shipping = chosen.freeOver && net >= chosen.freeOver ? 0 : chosen.fee;
  const total = net + shipping;

  const PAYMENTS = [
    ['八達通 O! ePay', 'Octopus O! ePay'],
    ['PayMe', 'PayMe'],
    ['轉數快 FPS', 'FPS'],
    ['AlipayHK', 'AlipayHK'],
    ['WeChat Pay HK', 'WeChat Pay HK'],
    ['信用卡', 'Credit card'],
  ];

  root.innerHTML = `
    <section class="container" style="max-width:900px">
      <h1 class="section-title">${esc(t('nav.cart'))}</h1>

      <div class="card" id="risk-summary"></div>

      <div class="card">
        ${lines.map((l) => `
          <div class="cart-row">
            <div class="cart-thumb">${mediaInner(l.product, '2.2rem')}</div>
            <div class="cart-info">
              <div class="nm">${esc(pName(l.product))}</div>
              <div class="pr">${fmtPrice(l.product.price)} × ${l.qty}</div>
            </div>
            <div class="qty">
              <button data-dec="${l.id}">−</button><span>${l.qty}</span><button data-inc="${l.id}">+</button>
            </div>
            <strong>${fmtPrice(l.product.price * l.qty)}</strong>
            <button class="btn btn-ghost btn-sm" data-rm="${l.id}" title="Remove">✕</button>
          </div>`).join('')}

        <div class="delivery-pick">
          <div class="muted small" style="margin-bottom:8px">${esc(isZh() ? '取貨方式' : 'Delivery')}</div>
          ${DELIVERY.map((d) => `
            <label class="delivery-opt ${d.id === chosen.id ? 'active' : ''}">
              <input type="radio" name="delivery" value="${d.id}" ${d.id === chosen.id ? 'checked' : ''} />
              <span class="d-label">${esc(isZh() ? d.zh : d.en)}</span>
              <span class="d-eta">${esc(d.eta)}</span>
              <span class="d-fee">${d.fee === 0 ? esc(isZh() ? '免費' : 'Free')
                : (d.freeOver && net >= d.freeOver ? esc(isZh() ? '免運' : 'Free')
                  : fmtPrice(d.fee))}</span>
            </label>`).join('')}
        </div>

        <div style="padding-top:8px">
          <div class="summary-line"><span>${esc(t('common.subtotal'))}</span><span>${fmtPrice(subtotal)}</span></div>
          ${coupon ? `<div class="coupon-apply">
            <span>🎟️ ${esc(isZh() ? '優惠券已套用' : 'Coupon applied')} <span class="code">${esc(coupon.code)}</span></span>
            <strong>−${fmtPrice(discount)} (−${coupon.discountPct}%)</strong>
          </div>` : ''}
          <div class="summary-line"><span>${esc(t('common.shipping'))} · ${esc(isZh() ? chosen.zh : chosen.en)}</span><span>${shipping === 0 ? esc(t('common.free')) : fmtPrice(shipping)}</span></div>
          <div class="summary-line total"><span>${esc(t('common.total'))}</span><span>${fmtPrice(total)}</span></div>

          <div class="pay-row">
            <span class="muted small">${esc(isZh() ? '付款方式' : 'Payment')}</span>
            <div class="pay-chips">
              ${PAYMENTS.map(([zh, en], i) => `<span class="pay-chip ${i === 0 ? 'active' : ''}">${esc(isZh() ? zh : en)}</span>`).join('')}
            </div>
          </div>

          <div class="searchbar" style="margin-top:16px">
            <button class="btn btn-primary btn-block" id="checkout">${esc(t('common.checkout'))} →</button>
            <button class="btn btn-ghost" id="clear">${esc(t('common.clear'))}</button>
          </div>
        </div>
      </div>
    </section>
  `;

  root.querySelectorAll('input[name="delivery"]').forEach((r) =>
    r.addEventListener('change', () => {
      cartDelivery = r.value;
      render(root, ctx);
    }));

  // ---- Return-risk prediction for the whole basket ------------------------
  const riskHost = root.querySelector('#risk-summary');
  riskHost.innerHTML = `<div class="empty">${esc(t('common.loading'))}</div>`;
  try {
    const r = await postJSON('/api/return-risk/cart', {
      items: lines.map((l) => ({ productId: l.id })),
      lang: isZh() ? 'zh' : 'en',
    });
    const o = r.overall;
    riskHost.innerHTML = `
      <div class="row-between">
        <h3 style="margin:0">🎯 ${esc(t('rr.riskInCart'))}</h3>
        <span class="badge ${o.level === 'low' ? 'badge-good' : o.level === 'medium' ? 'badge-warn' : 'badge-wait'}">
          ${o.averageRisk}% · ${esc(t(`rr.${o.level}`))}
        </span>
      </div>
      <p class="muted small" style="margin-top:8px">
        ${o.adviceCount > 0 ? `⚠️ ${o.adviceCount} ${esc(t('rr.adviceCount'))}` : `✓ ${esc(isZh() ? '所有單品尺碼建議與你的身型相符' : 'All sizes match your measurements')}`}
      </p>
      <div class="stack" style="margin-top:12px">
        ${r.items.filter((i) => i.recommendedSize !== i.chosenSize).map((i) => `
          <div class="risk-factor">
            <span>${i.product.emoji} ${esc(isZh() ? i.product.name_zh || i.product.name : i.product.name)}</span>
            <span><span class="muted">${esc(i.chosenSize)}</span> → <b class="hl">${esc(i.recommendedSize)}</b>
              <span class="muted small">(−${i.riskScore - i.riskIfFollowed}%)</span></span>
          </div>`).join('')}
      </div>`;
  } catch {
    riskHost.innerHTML = `<div class="muted small">${esc(t('common.retry'))}</div>`;
  }

  root.querySelectorAll('[data-inc]').forEach((b) => b.addEventListener('click', () => { setQty(b.dataset.inc, (getCart()[b.dataset.inc] || 0) + 1); render(root, ctx); }));
  root.querySelectorAll('[data-dec]').forEach((b) => b.addEventListener('click', () => { setQty(b.dataset.dec, (getCart()[b.dataset.dec] || 1) - 1); render(root, ctx); }));
  root.querySelectorAll('[data-rm]').forEach((b) => b.addEventListener('click', () => { removeFromCart(b.dataset.rm); render(root, ctx); }));
  root.querySelector('#clear').addEventListener('click', () => { clearCart(); render(root, ctx); });
  root.querySelector('#checkout').addEventListener('click', async () => {
    // Record the conversion, and burn the coupon if one was in play.
    track('checkout', null, total);
    if (coupon?.code) {
      try { await postJSON('/api/analytics/coupon/apply', { code: coupon.code }); } catch { /* non-fatal */ }
    }
    clearCart();
    try { localStorage.removeItem('smartmall-coupon'); } catch { /* ignore */ }
    updateBadge();
    root.innerHTML = `<section class="container">${emptyState('✅', isZh() ? '訂單已成立！' : 'Order placed!', isZh() ? '這是展示用結帳流程，未進行實際付款。' : 'Demo checkout — no payment was processed.')}<div style="text-align:center;margin-top:10px"><button class="btn btn-primary" data-home>${esc(t('nav.home'))}</button></div></section>`;
    root.querySelector('[data-home]').addEventListener('click', () => ctx.navigate('/'));
  });
}
