// js/views/product.js — product detail + return-risk prediction + price forecast.
import { getJSON } from '../api.js';
import { fmtPrice, toast, hexA, pName, pDesc, esc, t, isZh, mediaInner } from '../ui.js';
import { addToCart } from '../cart.js';
import { track } from '../exitIntent.js';
import { renderPriceChart } from '../chart.js';

export async function render(root, ctx, id) {
  const p = ctx.products.find((x) => x.id === id);
  if (!p) {
    root.innerHTML = `<div class="container"><div class="card">Not found.</div></div>`;
    return;
  }
  try { track('product_view', p.id); } catch { /* analytics is best-effort */ }

  const attrs = [
    `${p.colorName}`,
    `${p.material}`,
    ...p.style,
    ...p.occasion,
    ...p.climate,
    ...p.season,
  ];

  root.innerHTML = `
    <section class="container">
      <button class="btn btn-ghost btn-sm" data-back>← ${esc(t('common.back'))}</button>
      <div class="detail-grid" style="margin-top:16px">
        <div class="detail-hero ${p.image ? 'has-photo' : ''}" style="background:linear-gradient(135deg, ${hexA(p.color, 0.14)}, ${hexA(p.color, 0.3)})">${mediaInner(p, '8rem')}</div>
        <div class="detail-info">
          <div class="product-brand">${esc(p.brand)}</div>
          <h1>${esc(pName(p))}</h1>
          <div class="rating">★ ${p.rating} · ${p.reviews} ${esc(t('pp.reviews'))} · <span class="color-dot" style="background:${p.color}"></span>${esc(p.colorName)}</div>
          <div class="price-big">${fmtPrice(p.price)}</div>
          <p class="muted">${esc(pDesc(p))}</p>
          <div class="attr-row">${attrs.map((a) => `<span class="pill">${esc(a)}</span>`).join('')}</div>
          <div class="attr-row" style="margin-top:20px">
            <div class="qa-row"><span>${esc(t('pp.qty'))}</span>
              <div class="qty">
                <button data-qty="-1">−</button><span id="qty-val">1</span><button data-qty="1">+</button>
              </div>
            </div>
            <button class="btn btn-primary" data-add>${esc(t('pp.addCart'))}</button>
            <button class="btn btn-accent" data-tryon>${esc(t('pp.tryOn'))}</button>
          </div>
        </div>
      </div>

      <div class="card" style="margin-top:20px" id="risk-card">
        <h3>🎯 ${esc(t('rr.title'))}</h3>
        <p class="muted small">${esc(t('rr.sub'))}</p>
        <div id="risk-body"><div class="empty">${esc(t('common.loading'))}</div></div>
      </div>

      <div class="card" style="margin-top:20px">
        <h3>${esc(t('pp.priceIntel'))}</h3>
        <p class="muted small">${esc(t('pp.priceIntelSub'))}</p>
        <div class="forecast-layout">
          <div class="chart-card" id="price-chart"><div class="empty">${esc(t('common.loading'))}</div></div>
          <div id="forecast-panel"><div class="empty">${esc(t('common.loading'))}</div></div>
        </div>
      </div>

      <div class="card" style="margin-top:20px">
        <div class="row-between">
          <h3 style="margin:0">🏬 ${esc(isZh() ? '門市現貨' : 'Store stock')}</h3>
          <a class="btn btn-ghost btn-sm" href="#/stores">${esc(isZh() ? '全部門市' : 'All stores')} →</a>
        </div>
        <div id="store-body" style="margin-top:14px"><div class="empty">${esc(t('common.loading'))}</div></div>
      </div>
    </section>
  `;

  let qty = 1;
  const qtyVal = root.querySelector('#qty-val');
  root.querySelector('[data-back]').addEventListener('click', () => history.back());
  root.querySelector('[data-add]').addEventListener('click', () => {
    addToCart(p.id, qty);
    toast(`${pName(p)} → ${t('nav.cart')}`);
  });
  root.querySelector('[data-tryon]').addEventListener('click', () => {
    ctx.state.tryonProduct = p.id;
    ctx.navigate('/tryon');
  });
  root.querySelectorAll('[data-qty]').forEach((b) =>
    b.addEventListener('click', () => {
      qty = Math.max(1, Math.min(9, qty + Number(b.dataset.qty)));
      qtyVal.textContent = qty;
    }));

  // ---- Return-risk prediction --------------------------------------------
  const riskBody = root.querySelector('#risk-body');
  let chosenSize = null;

  async function loadRisk(size) {
    riskBody.innerHTML = `<div class="empty">${esc(t('common.loading'))}</div>`;
    try {
      const r = await getJSON(`/api/return-risk/${p.id}?lang=${isZh() ? 'zh' : 'en'}${size ? `&size=${encodeURIComponent(size)}` : ''}`);
      renderRisk(riskBody, r, loadRisk);
    } catch {
      riskBody.innerHTML = `<div class="empty">${esc(t('common.retry'))}</div>`;
    }
  }
  loadRisk(null);

  // ---- Price forecast -----------------------------------------------------
  try {
    const f = await getJSON(`/api/forecast/${p.id}`);
    renderPriceChart(root.querySelector('#price-chart'), f.history, f.forecast);
    root.querySelector('#price-chart').innerHTML += `
      <div class="legend">
        <span><span class="dot" style="background:#8B7BFF"></span>${esc(t('pp.history'))}</span>
        <span><span class="dot" style="background:#FF8A66"></span>${esc(t('pp.forecast'))}</span>
      </div>`;
    renderAdvisory(root.querySelector('#forecast-panel'), f);
  } catch {
    root.querySelector('#price-chart').innerHTML = `<div class="empty">${esc(t('common.retry'))}</div>`;
  }

  // ---- Store stock (O2O) ---------------------------------------------------
  loadStoreStock(root.querySelector('#store-body'), p.id);
}

async function loadStoreStock(host, productId) {
  if (!host) return;
  try {
    const a = await getJSON(`/api/stores/stock/${encodeURIComponent(productId)}`);
    const withStock = a.stores.filter((s) => s.qty > 0).slice(0, 4);
    const online = a.onlineInStock
      ? `<span class="badge badge-good">${esc(isZh() ? `線上現貨 ${a.onlineStock} 件` : `${a.onlineStock} online`)}</span>`
      : `<span class="badge badge-wait">${esc(isZh() ? '線上缺貨' : 'Sold out online')}</span>`;

    host.innerHTML = `
      <div style="margin-bottom:12px">${online}
        <span class="muted small" style="margin-left:8px">${esc(isZh()
          ? `${a.storeCount} 間門市有貨 · 合共 ${a.totalStoreQty} 件`
          : `${a.storeCount} stores · ${a.totalStoreQty} units`)}</span>
      </div>
      ${withStock.length ? `<div class="stock-list">
        ${withStock.map((s) => `<div class="stock-row">
          <div>
            <strong>${esc(isZh() ? s.name_zh : s.name_en)}</strong>
            <span class="muted small">· ${esc(isZh() ? s.district_zh : s.district_en)}</span>
            <div class="muted small">🚇 ${esc(isZh() ? s.mtr_zh : s.mtr_en)} · 🕒 ${esc(s.hours)}</div>
          </div>
          <div class="stock-right">
            <span class="qty ${s.qty <= 2 ? 'low' : ''}">${s.qty}</span>
            <a class="btn btn-ghost btn-sm" target="_blank" rel="noopener"
               href="https://www.google.com/maps/dir/?api=1&destination=${s.lat},${s.lng}">🧭</a>
          </div>
        </div>`).join('')}
      </div>
      <p class="muted small" style="margin:12px 0 0">🛍️ ${esc(isZh()
        ? '即日門市取貨：下午 6 點前下單，當日可取，保留 3 天。'
        : 'Same-day pickup: order before 6 pm, held for 3 days.')}</p>`
      : `<p class="muted small">${esc(isZh() ? '所有門市暫時缺貨。' : 'No store stock right now.')}</p>`}`;
  } catch {
    host.innerHTML = `<div class="muted small">${esc(t('common.retry'))}</div>`;
  }
}

function renderRisk(host, r, reload) {
  const levelClass = `risk-${r.riskLevel}`;
  const levelLabel = t(`rr.${r.riskLevel}`);
  const runsLabel = r.runs === 'small' ? t('rr.runsSmall') : r.runs === 'large' ? t('rr.runsLarge') : t('rr.runsTrue');

  host.innerHTML = `
    <div class="risk-card ${levelClass}">
      <div class="risk-ring">
        <div class="risk-num">${r.riskScore}%</div>
        <div>
          <div class="badge ${r.riskLevel === 'low' ? 'badge-good' : r.riskLevel === 'medium' ? 'badge-warn' : 'badge-wait'}">${esc(t('rr.risk'))}: ${esc(levelLabel)}</div>
          <div class="muted small" style="margin-top:6px">${esc(t('common.confidence'))} ${Math.round(r.confidence * 100)}% · ${esc(r.bodyNote)}</div>
        </div>
      </div>
      <div class="risk-bar"><i style="width:${r.riskScore}%"></i></div>

      <div class="divider"></div>
      <div class="row-between">
        <div>
          <div class="muted small">${esc(t('rr.usual'))} · ${esc(runsLabel)}</div>
          <div style="font-weight:800;font-size:1.05rem">${esc(r.usualSize)} → <span class="hl">${esc(r.recommendedSize)}</span></div>
        </div>
        <span class="badge badge-good">${esc(t('rr.ifFollowed'))} ${r.riskIfFollowed}%</span>
      </div>

      <div class="size-pick">
        ${['XS', 'S', 'M', 'L', 'XL', 'XXL'].map((s) => `<button class="size-btn ${s === r.recommendedSize ? 'rec' : ''} ${s === r.chosenSize ? 'active' : ''}" data-size="${s}">${s}${s === r.recommendedSize ? ' ✓' : ''}</button>`).join('')}
      </div>

      <p class="small" style="margin-top:14px;color:var(--ink-2);line-height:1.6">💡 ${esc(r.advice)}</p>
    </div>
  `;

  host.querySelectorAll('[data-size]').forEach((b) =>
    b.addEventListener('click', () => reload(b.dataset.size)));
}

function renderAdvisory(panel, f) {
  const { advisory } = f;
  const isBuy = advisory.action === 'buy';
  const headline = isZh() ? (advisory.headline_zh || advisory.headline) : advisory.headline;
  const reasoning = isZh() ? (advisory.reasoning_zh || advisory.reasoning) : advisory.reasoning;
  const conf = isZh() ? (advisory.confidence_zh || advisory.confidence) : advisory.confidence;
  panel.innerHTML = `
    <div class="advisory-box ${isBuy ? 'buy' : 'wait'}">
      <span class="badge ${isBuy ? 'badge-buy' : 'badge-wait'}">${isBuy ? '🟢 ' : '🟡 '}${esc(headline)}</span>
      <p style="margin-top:12px">${esc(reasoning)}</p>
    </div>
    <div class="card" style="margin-top:14px; padding:16px">
      <div class="summary-line"><span>${esc(t('pp.current'))}</span><strong>${fmtPrice(f.current)}</strong></div>
      <div class="summary-line"><span>${esc(t('pp.trend'))}</span><strong>${f.trend.weeklyChangePct > 0 ? '+' : ''}${f.trend.weeklyChangePct}%</strong></div>
      ${advisory.action === 'wait' ? `<div class="summary-line"><span>${esc(t('pp.projected'))}</span><strong>−${advisory.expectedDropPct}%</strong></div>` : ''}
      <div style="margin-top:10px">
        <div class="summary-line" style="padding-bottom:4px"><span>${esc(t('common.confidence'))}</span><strong>${esc(conf)}</strong></div>
        <div class="confidence-bar"><div class="confidence-fill" style="width:${Math.round(advisory.confidenceScore * 100)}%"></div></div>
      </div>
      ${(f.events && f.events.length) ? `
        <div class="divider"></div>
        <div class="small" style="color:var(--ink-2)">
          🗓️ ${esc(isZh() ? '下一個購物節' : 'Next sale')}：<strong>${esc(f.events[0].label)}</strong>
          ${f.events[0].daysAway}${esc(isZh() ? ' 天後' : 'd')} ·
          ${esc(isZh() ? '預測' : 'est.')} ${fmtPrice(f.events[0].predictedPrice)}
          <span class="badge badge-wait">−${f.events[0].dropPct}%</span>
        </div>` : ''}
      <p class="muted small" style="margin:10px 0 0">
        ${esc(isZh() ? '模型：' : 'Engine: ')}${esc(f.engineLabel || f.engine || '')}
      </p>
      <button class="btn btn-primary btn-block" style="margin-top:16px" data-buy>${esc(t('pp.addCart'))}</button>
    </div>
  `;
  panel.querySelector('[data-buy]').addEventListener('click', () => {
    addToCart(f.productId, 1);
    toast(t('nav.cart'));
  });
}
