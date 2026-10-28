// js/views/dashboard.js — B2B merchant dashboard (search volume, exit-intent
// retention, coupon usage, conversion). Data comes from lib/analytics.js.
import { getJSON } from '../api.js';
import { esc, t, isZh } from '../ui.js';

const RANGES = [7, 14, 30];

export async function render(root, ctx) {
  const days = ctx.state.dashDays || 7;

  root.innerHTML = `<section class="container"><div class="card">${esc(t('common.loading'))}</div></section>`;

  let data;
  try {
    data = await getJSON(`/api/analytics/summary?days=${days}`);
  } catch {
    root.innerHTML = `<section class="container"><div class="card">${esc(t('common.retry'))}</div></section>`;
    return;
  }
  const coupons = await getJSON('/api/analytics/coupons').then((r) => r.coupons).catch(() => []);
  const events = await getJSON('/api/analytics/events?limit=12').then((r) => r.events).catch(() => []);

  const T = data.totals;
  const R = data.rates;
  const f = data.funnels.exitIntent;
  const maxFunnel = Math.max(1, f[0].count);
  const label = (k) => (isZh() ? zhLabels[k] : enLabels[k]);

  const zhLabels = {
    shown: '彈出挽留', claimed: '領取優惠券', applied: '實際使用', checkout: '完成結帳',
  };
  const enLabels = {
    shown: 'Prompt shown', claimed: 'Coupon claimed', applied: 'Coupon used', checkout: 'Checked out',
  };

  root.innerHTML = `
    <section class="container">
      <div class="row-between">
        <div>
          <h1 class="section-title">📊 ${esc(isZh() ? '商戶後台' : 'Merchant Dashboard')}</h1>
          <p class="section-sub" style="margin-bottom:0">
            ${esc(isZh() ? '導購成效總覽 — 搜尋、挽留與轉化' : 'Storefront performance — search, retention, conversion')}
          </p>
        </div>
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <a class="btn btn-ghost btn-sm" href="/demo-store.html" target="_blank" rel="noopener">
            🧩 ${esc(isZh() ? '嵌入示範商家網站' : 'View embed demo')}
          </a>
          <div class="chips">
            ${RANGES.map((d) => `<button class="chip ${d === days ? 'active' : ''}" data-days="${d}">
              ${esc(isZh() ? `近 ${d} 天` : `Last ${d} days`)}</button>`).join('')}
          </div>
        </div>
      </div>

      <div class="tenant-bar">
        <span class="tenant-dot"></span>
        <strong>${esc(data.tenant)}</strong>
        <span class="sep">·</span>
        <span>${esc(isZh() ? 'B2B 租戶' : 'B2B tenant')}</span>
        <span class="sep">·</span>
        <span class="muted">${esc(isZh()
          ? '歷史為示範數據，你現在的搜尋與點擊會即時累加'
          : 'History is demo data; your own searches and clicks add live events')}</span>
      </div>

      <div class="dash-stats">
        ${statCard(isZh() ? '搜尋次數' : 'Searches', T.searches,
          isZh() ? `關鍵字 ${T.keywordSearches} · 視覺 ${T.visualSearches} · 助手 ${T.assistantQueries}`
                 : `keyword ${T.keywordSearches} · visual ${T.visualSearches} · assistant ${T.assistantQueries}`)}
        ${statCard(isZh() ? '訪客數' : 'Sessions', T.sessions,
          isZh() ? `商品瀏覽 ${T.productViews}` : `${T.productViews} product views`)}
        ${statCard(isZh() ? '挽留成功率' : 'Retention rate', `${R.retentionRate}%`,
          isZh() ? `${T.exitClaimed} 人領券 / ${T.exitShown} 次彈出` : `${T.exitClaimed} claimed / ${T.exitShown} shown`,
          R.retentionRate >= 5 ? 'good' : 'warn')}
        ${statCard(isZh() ? '轉化率' : 'Conversion rate', `${R.conversionRate}%`,
          isZh() ? `${T.checkout} 張訂單` : `${T.checkout} orders`, R.conversionRate >= 4 ? 'good' : 'warn')}
        ${statCard(isZh() ? '嵌入 Widget 開啟' : 'Widget opens', T.widgetOpens ?? 0,
          isZh() ? '來自商家網站的 launcher / 搜尋欄' : 'launcher / search bar on merchant sites')}
      </div>

      <div class="dash-grid">
        <div class="card">
          <h3>${esc(isZh() ? '每日搜尋量' : 'Daily search volume')}</h3>
          <p class="muted small" style="margin-top:-6px">
            ${esc(isZh() ? '藍色＝搜尋次數，綠色＝完成結帳' : 'Blue = searches, green = checkouts')}
          </p>
          <div id="dash-chart"></div>
        </div>

        <div class="card">
          <h3>${esc(isZh() ? '退出挽留漏斗' : 'Exit-intent funnel')}</h3>
          <p class="muted small" style="margin-top:-6px">
            ${esc(isZh() ? '從彈出到成交，每一層的流失都看得見' : 'From prompt to order — losses at every step')}
          </p>
          <div class="funnel">
            ${f.map((s, i) => {
              const pct = Math.round((s.count / maxFunnel) * 100);
              const drop = i > 0 && f[i - 1].count > 0
                ? Math.round((s.count / f[i - 1].count) * 100) : null;
              return `<div class="funnel-row">
                <div class="funnel-label">${esc(label(s.stage))}</div>
                <div class="funnel-bar"><i style="width:${Math.max(2, pct)}%"></i></div>
                <div class="funnel-num">${s.count}${drop != null ? `<span class="muted small"> (${drop}%)</span>` : ''}</div>
              </div>`;
            }).join('')}
          </div>
          <div class="divider"></div>
          <div class="row-between small">
            <span class="muted">${esc(isZh() ? '優惠券使用率' : 'Coupon use rate')}</span>
            <strong>${R.couponApplyRate}%</strong>
          </div>
          <div class="row-between small">
            <span class="muted">${esc(isZh() ? '加入購物車率' : 'Add-to-cart rate')}</span>
            <strong>${R.cartRate}%</strong>
          </div>
        </div>
      </div>

      <div class="dash-grid">
        <div class="card">
          <h3>${esc(isZh() ? '熱門搜尋' : 'Top searches')}</h3>
          ${data.topSearches.length
            ? `<div class="stack" style="gap:8px">${data.topSearches.map((s) => `
                <div class="row-between small">
                  <span>🔍 ${esc(s.term)}</span><strong>${s.n}</strong>
                </div>`).join('')}</div>`
            : `<p class="muted small">${esc(isZh() ? '還沒有搜尋紀錄' : 'No searches yet')}</p>`}
        </div>

        <div class="card">
          <h3>${esc(isZh() ? '優惠券' : 'Coupons')}</h3>
          ${coupons.length
            ? `<div class="table-scroll"><table class="offer-table" style="min-width:0">
                <thead><tr>
                  <th>${esc(isZh() ? '代碼' : 'Code')}</th>
                  <th>${esc(isZh() ? '折扣' : 'Discount')}</th>
                  <th>${esc(isZh() ? '狀態' : 'Status')}</th>
                </tr></thead>
                <tbody>${coupons.slice(0, 8).map((c) => `
                  <tr>
                    <td class="coupon-code">${esc(c.code)}</td>
                    <td>${c.discountPct}%</td>
                    <td><span class="badge ${c.status === 'applied' ? 'badge-good' : 'badge-info'}">
                      ${esc(c.status === 'applied' ? (isZh() ? '已使用' : 'Used') : (isZh() ? '已發出' : 'Issued'))}
                    </span></td>
                  </tr>`).join('')}</tbody>
              </table></div>`
            : `<p class="muted small">${esc(isZh() ? '尚未發出優惠券' : 'No coupons issued yet')}</p>`}
        </div>
      </div>

      <div class="card">
        <h3>${esc(isZh() ? '即時事件' : 'Live events')}</h3>
        <div class="table-scroll">
          <table class="offer-table" style="min-width:520px">
            <thead><tr>
              <th>${esc(isZh() ? '時間' : 'Time')}</th>
              <th>${esc(isZh() ? '事件' : 'Event')}</th>
              <th>${esc(isZh() ? '內容' : 'Detail')}</th>
            </tr></thead>
            <tbody>
              ${events.map((e) => `<tr>
                <td class="muted mono">${esc(new Date(e.createdAt).toLocaleString(isZh() ? 'zh-HK' : 'en-US', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }))}</td>
                <td><span class="badge badge-info">${esc(e.type)}</span></td>
                <td class="muted">${esc(e.label || '—')}</td>
              </tr>`).join('') || `<tr><td colspan="3" class="muted">${esc(isZh() ? '尚無事件' : 'No events')}</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  `;

  drawChart(root.querySelector('#dash-chart'), data.daily);
  root.querySelectorAll('[data-days]').forEach((b) =>
    b.addEventListener('click', () => {
      ctx.state.dashDays = Number(b.dataset.days);
      render(root, ctx);
    }));
}

function statCard(label, value, sub, tone = '') {
  return `<div class="dash-stat ${tone}">
    <div class="k">${esc(label)}</div>
    <div class="v">${esc(String(value))}</div>
    <div class="s">${esc(sub)}</div>
  </div>`;
}

// Grouped bar chart: searches (accent) vs checkouts (green).
function drawChart(host, daily) {
  const W = 640;
  const H = 220;
  const padL = 34;
  const padR = 8;
  const padT = 12;
  const padB = 26;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const max = Math.max(1, ...daily.map((d) => Math.max(d.searches, d.checkout)));
  const slot = innerW / daily.length;
  const barW = Math.max(3, Math.min(14, slot / 3.2));

  let grid = '';
  for (let i = 0; i <= 3; i++) {
    const y = padT + (innerH * i) / 3;
    const v = Math.round(max - (max * i) / 3);
    grid += `<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="rgba(255,255,255,0.09)" stroke-width="1"/>`;
    grid += `<text x="${padL - 7}" y="${y + 4}" text-anchor="end" font-size="10" fill="#9AA3B2">${v}</text>`;
  }

  const bars = daily.map((d, i) => {
    const cx = padL + slot * i + slot / 2;
    const hS = (d.searches / max) * innerH;
    const hC = (d.checkout / max) * innerH;
    return `
      <rect x="${cx - barW - 1.5}" y="${padT + innerH - hS}" width="${barW}" height="${Math.max(1, hS)}" rx="2" fill="#8B7BFF"/>
      <rect x="${cx + 1.5}" y="${padT + innerH - hC}" width="${barW}" height="${Math.max(1, hC)}" rx="2" fill="#3DD68C"/>
      <text x="${cx}" y="${H - 9}" text-anchor="middle" font-size="10" fill="#9AA3B2">${d.label}</text>`;
  }).join('');

  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img"
    aria-label="Daily searches and checkouts">${grid}${bars}</svg>`;
}
