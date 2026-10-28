// js/views/priceagent.js — Feature 2: cross-platform price comparison + negotiation.
import { postJSON } from '../api.js';
import { esc, fmtPrice, toast, hexA, pName, t, isZh } from '../ui.js';
import { getCart, cartLines } from '../cart.js';

export function render(root, ctx) {
  root.innerHTML = `
    <section class="container">
      <h1 class="section-title">${esc(t('pa.title'))}</h1>
      <p class="section-sub">${esc(t('pa.sub'))}</p>

      <div class="card">
        <div class="row-between">
          <h3 style="margin:0">${esc(t('pa.pickItems'))}</h3>
          <button class="btn btn-ghost btn-sm" id="pa-cart">${esc(t('pa.fromCart'))}</button>
        </div>
        <div class="chips" style="margin-top:14px" id="pa-picker">
          ${ctx.products.map((p) => `<button class="chip" data-id="${p.id}" title="${esc(pName(p))}">${p.emoji} ${esc(pName(p))}</button>`).join('')}
        </div>
        <div class="row-between" style="margin-top:16px">
          <span class="muted small" id="pa-count">0 ${esc(t('common.items'))}</span>
          <button class="btn btn-primary" id="pa-go" disabled>${esc(t('pa.run'))}</button>
        </div>
      </div>

      <div id="pa-result" style="margin-top:18px"></div>
    </section>
  `;

  const selected = new Set();
  const picker = root.querySelector('#pa-picker');
  const count = root.querySelector('#pa-count');
  const go = root.querySelector('#pa-go');

  const sync = () => {
    count.textContent = `${selected.size} ${t('common.items')}`;
    go.disabled = selected.size === 0;
  };

  picker.querySelectorAll('.chip').forEach((c) =>
    c.addEventListener('click', () => {
      const id = c.dataset.id;
      if (selected.has(id)) { selected.delete(id); c.classList.remove('active'); }
      else { selected.add(id); c.classList.add('active'); }
      sync();
    }));

  root.querySelector('#pa-cart').addEventListener('click', () => {
    const ids = cartLines().map((l) => l.id);
    if (!ids.length) { toast(isZh() ? '購物車是空的' : 'Your cart is empty'); return; }
    selected.clear();
    picker.querySelectorAll('.chip').forEach((c) => {
      const on = ids.includes(c.dataset.id);
      c.classList.toggle('active', on);
      if (on) selected.add(c.dataset.id);
    });
    sync();
  });

  const result = root.querySelector('#pa-result');

  go.addEventListener('click', async () => {
    result.innerHTML = `<div class="card box-reveal"><div class="box">🔎</div><p class="muted" style="margin-top:14px">${esc(t('pa.running'))}</p></div>`;
    try {
      const res = await postJSON('/api/price-agent', {
        productIds: [...selected],
        lang: isZh() ? 'zh' : 'en',
      });
      setTimeout(() => renderResult(result, res), 600);
    } catch {
      result.innerHTML = `<div class="card">${esc(t('common.retry'))}</div>`;
    }
  });
}

function renderResult(host, res) {
  const s = res.summary;
  const n = res.negotiation;

  host.innerHTML = `
    <div class="card">
      <div class="pa-summary">
        <div class="stat"><div class="k">${esc(t('pa.platforms'))}</div><div class="v">${s.platformsScanned}</div></div>
        <div class="stat"><div class="k">${esc(t('pa.listings'))}</div><div class="v">${s.listingsCompared}</div></div>
        <div class="stat"><div class="k">${esc(t('pa.coupons'))}</div><div class="v">${s.couponsClaimed}</div></div>
        <div class="stat"><div class="k">${esc(t('pa.original'))}</div><div class="v">${fmtPrice(s.originalTotal)}</div></div>
        <div class="stat good"><div class="k">${esc(t('pa.best'))}</div><div class="v">${fmtPrice(s.bestTotal)}</div></div>
        <div class="stat good"><div class="k">${esc(t('pa.final'))}</div><div class="v">${fmtPrice(s.negotiatedTotal)}</div></div>
        <div class="stat good"><div class="k">${esc(t('pa.saved'))}</div><div class="v">−${fmtPrice(s.totalSavings)} (${s.savingsPct}%)</div></div>
      </div>

      <p class="muted small">🔒 ${esc(res.compliance)}</p>
    </div>

    ${res.items.map((it) => `
      <div class="card">
        <div class="row-between">
          <h3 style="margin:0">${it.product.emoji} ${esc(isZh() ? it.product.name_zh : it.product.name)}</h3>
          <span class="badge badge-good">${esc(t('common.savings'))} ${fmtPrice(it.savings.amount)} (${it.savings.pct}%)</span>
        </div>
        <div class="table-scroll" style="margin-top:12px">
          <table class="offer-table">
            <thead><tr>
              <th>${esc(t('pa.platforms'))}</th><th>${esc(t('common.original'))}</th>
              <th>${esc(t('pa.ship'))}</th><th>${esc(t('pa.coupon'))}</th>
              <th>${esc(t('pa.landed'))}</th><th>${esc(t('pa.delivery'))}</th>
            </tr></thead>
            <tbody>
              ${it.offers.map((o, idx) => `
                <tr class="${idx === 0 ? 'best' : ''}">
                  <td><span class="plat"><span class="plat-dot" style="background:${o.platform.color}"></span>${esc(isZh() ? o.platform.name : o.platform.name_en)}${o.platform.official ? ` <span class="plat-flag">官方</span>` : ''}</span></td>
                  <td class="mono">${fmtPrice(o.price)}</td>
                  <td class="mono">${o.shipping === 0 ? esc(t('common.free')) : fmtPrice(o.shipping)}</td>
                  <td>${o.coupon ? `<span class="coupon-code">${esc(o.coupon.code)}</span> <span class="muted small">−${fmtPrice(o.coupon.discount)}</span>` : '<span class="muted">—</span>'}</td>
                  <td class="mono"><b>${fmtPrice(o.finalPrice)}</b>${idx === 0 ? ` <span class="plat-flag">${esc(t('pa.bestTag'))}</span>` : ''}</td>
                  <td class="muted">${o.deliveryDays} ${esc(t('pa.days'))}</td>
                </tr>`).join('')}
            </tbody>
          </table>
        </div>
      </div>`).join('')}

    <div class="card">
      <h3>💬 ${esc(t('pa.negotiation'))} — ${esc(isZh() ? n.seller.name : n.seller.name_en)}</h3>
      <div class="nego-thread">
        ${n.transcript.map((line) => `
          <div class="nego-line ${line.role}">
            <span class="who">${line.role === 'agent' ? '🤖 ' + esc(t('pa.agent')) : '🏪 ' + esc(t('pa.seller'))}</span>
            ${esc(line.text)}
          </div>`).join('')}
      </div>
      <div class="divider"></div>
      <div class="bb-summary">
        <div class="stat"><div class="k">${esc(t('common.original'))}</div><div class="v">${fmtPrice(n.listPrice)}</div></div>
        <div class="stat good"><div class="k">${esc(t('pa.final'))}</div><div class="v">${fmtPrice(n.finalPrice)}</div></div>
        <div class="stat good"><div class="k">${esc(t('common.savings'))}</div><div class="v">−${n.discountPct}%</div></div>
      </div>
      <div style="margin-top:12px">${n.perks.map((p) => `<span class="perk">✓ ${esc(isZh() ? p.zh : p.en)}</span>`).join('')}</div>
    </div>

    ${res.coupons.length ? `<div class="card">
      <h3>🎟️ ${esc(t('pa.couponWallet'))}</h3>
      <div class="stack">
        ${res.coupons.map((c) => `
          <div class="coupon-card">
            <div>
              <div><b>${esc(isZh() ? c.productName_zh || c.productName : c.productName)}</b> · ${esc(isZh() ? c.platform.name : c.platform.name_en)}</div>
              <div class="muted small">${esc(isZh() ? c.coupon.label : c.coupon.label_en)}</div>
            </div>
            <div style="text-align:right">
              <div class="coupon-code">${esc(c.coupon.code)}</div>
              <div class="small" style="color:var(--good);font-weight:700">−${fmtPrice(c.coupon.discount)}</div>
            </div>
          </div>`).join('')}
      </div>
    </div>` : ''}
  `;
}
