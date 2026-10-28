// js/views/stores.js — physical store locator + per-store stock (O2O).
import { getJSON } from '../api.js';
import { esc, t, isZh, fmtPrice } from '../ui.js';

const mapsUrl = (s) =>
  `https://www.google.com/maps/dir/?api=1&destination=${s.lat},${s.lng}`;

export async function render(root, ctx) {
  root.innerHTML = `<section class="container"><div class="card">${esc(t('common.loading'))}</div></section>`;

  let data;
  try {
    data = await getJSON('/api/stores');
  } catch {
    root.innerHTML = `<section class="container"><div class="card">${esc(t('common.retry'))}</div></section>`;
    return;
  }

  const stores = data.stores;
  const districts = [...new Set(stores.map((s) => (isZh() ? s.district_zh : s.district_en)))];
  let activeDistrict = '';
  let origin = null;

  root.innerHTML = `
    <section class="container">
      <div class="page-head">
        <div>
          <h1 class="section-title">🏬 ${esc(isZh() ? '門市據點' : 'Our stores')}</h1>
          <p class="section-sub" style="margin-bottom:0">${esc(isZh()
            ? `${stores.length} 間門市 · 線上缺貨時可查看門市現貨並直接導航前往`
            : `${stores.length} stores · check live stock and get directions when an item is sold out online`)}</p>
        </div>
        <button class="btn btn-ghost" id="geo-btn">📍 ${esc(isZh() ? '使用我的位置' : 'Use my location')}</button>
      </div>

      <div class="pickup-strip">
        <span>🛍️ <strong>${esc(isZh() ? '即日門市取貨' : 'Same-day pickup')}</strong>
          ${esc(isZh() ? '下午 6 點前下單，當日可取' : 'order before 6 pm')}</span>
        <span>🕒 ${esc(isZh() ? '取貨保留 3 天' : 'held 3 days')}</span>
        <span>💳 ${esc(isZh() ? '門市可用八達通 / PayMe / 轉數快' : 'Octopus / PayMe / FPS accepted in store')}</span>
      </div>

      <div class="chips" id="district-chips" style="margin:16px 0">
        <button class="chip ${activeDistrict === '' ? 'active' : ''}" data-d="">${esc(isZh() ? '全部地區' : 'All districts')}</button>
        ${districts.map((d) => `<button class="chip" data-d="${esc(d)}">${esc(d)}</button>`).join('')}
      </div>

      <div class="store-grid" id="store-grid"></div>

      <div class="card" style="margin-top:22px">
        <h3 style="margin-top:0">🔍 ${esc(isZh() ? '查詢門市現貨' : 'Check store stock')}</h3>
        <p class="muted small">${esc(isZh()
          ? '選一件商品，看看哪幾間門市有現貨。線上顯示缺貨時，這裡就是你的後備方案。'
          : 'Pick a product to see which stores have it on hand.')}</p>
        <div class="searchbar" style="margin-top:10px">
          <select class="input" id="stock-pick" style="max-width:460px">
            ${ctx.products.map((p) => `<option value="${p.id}">${p.emoji} ${esc(isZh() ? (p.name_zh || p.name) : p.name)} — ${fmtPrice(p.price)}</option>`).join('')}
          </select>
        </div>
        <div id="stock-result" style="margin-top:16px"></div>
      </div>
    </section>
  `;

  const grid = root.querySelector('#store-grid');
  const chips = root.querySelector('#district-chips');
  const stockPick = root.querySelector('#stock-pick');
  const stockResult = root.querySelector('#stock-result');

  function paint() {
    const list = activeDistrict
      ? stores.filter((s) => (isZh() ? s.district_zh : s.district_en) === activeDistrict)
      : stores;

    grid.innerHTML = list.map((s) => {
      const name = isZh() ? s.name_zh : s.name_en;
      const addr = isZh() ? s.address_zh : s.address_en;
      const mtr = isZh() ? s.mtr_zh : s.mtr_en;
      return `<article class="store-card ${s.flagship ? 'flagship' : ''}">
        <div class="store-top">
          <div>
            <h3>${esc(name)}</h3>
            <span class="badge badge-info">${esc(isZh() ? s.district_zh : s.district_en)}</span>
            ${s.flagship ? `<span class="badge badge-good">${esc(isZh() ? '旗艦店' : 'Flagship')}</span>` : ''}
          </div>
          ${s.distanceKm != null ? `<span class="store-dist">${s.distanceKm < 1 ? `${Math.round(s.distanceKm * 1000)} m` : `${s.distanceKm} km`}</span>` : ''}
        </div>
        <p class="store-addr">${esc(addr)}</p>
        <p class="store-mtr">🚇 ${esc(mtr)}</p>
        <p class="store-meta">🕒 ${esc(s.hours)} · 📞 ${esc(s.phone)}</p>
        <a class="btn btn-ghost btn-sm" href="${mapsUrl(s)}" target="_blank" rel="noopener">
          🧭 ${esc(isZh() ? '導航前往' : 'Directions')}
        </a>
      </article>`;
    }).join('');
  }

  chips.addEventListener('click', (e) => {
    const b = e.target.closest('[data-d]');
    if (!b) return;
    activeDistrict = b.dataset.d;
    chips.querySelectorAll('.chip').forEach((c) => c.classList.toggle('active', c === b));
    paint();
  });

  root.querySelector('#geo-btn').addEventListener('click', (e) => {
    const btn = e.currentTarget;
    if (!navigator.geolocation) return;
    btn.disabled = true;
    btn.textContent = isZh() ? '定位中…' : 'Locating…';
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        origin = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        try {
          const sorted = await getJSON(`/api/stores`);
          // Re-sort locally by distance so we do not need a second product call.
          const withDist = sorted.stores.map((s) => ({ ...s, distanceKm: haversine(origin, s) }))
            .sort((a, b) => a.distanceKm - b.distanceKm);
          stores.length = 0;
          stores.push(...withDist);
          paint();
          btn.textContent = isZh() ? '✓ 已按距離排序' : '✓ Sorted by distance';
        } catch {
          btn.textContent = isZh() ? '定位失敗' : 'Location failed';
        }
      },
      () => {
        btn.disabled = false;
        btn.textContent = isZh() ? '📍 使用我的位置' : '📍 Use my location';
      },
      { timeout: 8000 },
    );
  });

  async function loadStock(id) {
    stockResult.innerHTML = `<div class="muted small">${esc(t('common.loading'))}</div>`;
    try {
      const q = origin ? `?lat=${origin.lat}&lng=${origin.lng}` : '';
      const a = await getJSON(`/api/stores/stock/${encodeURIComponent(id)}${q}`);
      const list = a.stores.filter((s) => s.qty > 0);
      const status = a.onlineInStock
        ? `<span class="badge badge-good">${esc(isZh() ? `線上仲有 ${a.onlineStock} 件` : `${a.onlineStock} in stock online`)}</span>`
        : `<span class="badge badge-wait">${esc(isZh() ? '線上缺貨' : 'Sold out online')}</span>`;

      stockResult.innerHTML = `
        <div class="row-between" style="margin-bottom:12px">
          <div>${status}
            <span class="muted small" style="margin-left:8px">${esc(isZh()
              ? `${list.length} 間門市有貨，共 ${a.totalStoreQty} 件`
              : `${list.length} stores · ${a.totalStoreQty} units`)}</span>
          </div>
        </div>
        ${list.length ? `<div class="stock-list">
          ${list.map((s) => `<div class="stock-row">
            <div>
              <strong>${esc(isZh() ? s.name_zh : s.name_en)}</strong>
              <span class="muted small">· ${esc(isZh() ? s.district_zh : s.district_en)}</span>
              ${s.distanceKm != null ? `<span class="muted small">· ${s.distanceKm} km</span>` : ''}
              <div class="muted small">🚇 ${esc(isZh() ? s.mtr_zh : s.mtr_en)}</div>
            </div>
            <div class="stock-right">
              <span class="qty ${s.qty <= 2 ? 'low' : ''}">${s.qty}</span>
              <a class="btn btn-ghost btn-sm" href="${mapsUrl(s)}" target="_blank" rel="noopener">🧭</a>
            </div>
          </div>`).join('')}
        </div>` : `<p class="muted small">${esc(isZh() ? '所有門市暫時缺貨，可設定到貨通知。' : 'No store stock right now — you can request a restock alert.')}</p>`}
      `;
    } catch {
      stockResult.innerHTML = `<div class="muted small">${esc(t('common.retry'))}</div>`;
    }
  }

  stockPick.addEventListener('change', () => loadStock(stockPick.value));
  paint();
  await loadStock(stockPick.value);
}

function haversine(a, b) {
  const R = 6371;
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return Math.round(2 * R * Math.asin(Math.sqrt(h)) * 10) / 10;
}
