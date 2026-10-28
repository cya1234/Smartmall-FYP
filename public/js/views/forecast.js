// js/views/forecast.js — price forecasting explorer (Prophet + baseline comparison).
import { getJSON } from '../api.js';
import { fmtPrice, esc, pName, t, isZh } from '../ui.js';
import { renderPriceChart } from '../chart.js';

export async function render(root, ctx) {
  const status = await getJSON('/api/forecast/status').catch(() => ({ online: false }));
  const evalDoc = await getJSON('/api/forecast-eval').catch(() => null);

  root.innerHTML = `
    <section class="container">
      <h1 class="section-title">📈 ${esc(t('nav.forecast'))}</h1>
      <p class="section-sub">${esc(isZh()
        ? '以 Meta Prophet 建立時間序列模型，把購物節（雙十一、黑五、聖誕）當作節日回歸量，預測未來走勢並給出「現在買」或「等降價」的建議。'
        : 'A Meta Prophet time-series model that treats the sale calendar as holiday regressors, projecting the trend and advising Buy Now vs. Wait.')}</p>

      <div class="engine-bar ${status.online ? '' : 'offline'}">
        <span>${status.online ? '🟢' : '🟡'} ${esc(status.online
          ? (isZh() ? 'Prophet 服務運作中' : 'Prophet service online')
          : (isZh() ? 'Prophet 服務離線，已改用線性回歸' : 'Prophet offline — using linear regression'))}</span>
        ${status.online ? `
          <span class="sep">·</span><span>Prophet ${esc(status.version || '')}</span>
          <span class="sep">·</span><span>${status.products} ${esc(isZh() ? '件商品' : 'products')}</span>
          <span class="sep">·</span><span>${Number(status.observations || 0).toLocaleString()} ${esc(isZh() ? '筆每日觀測' : 'daily observations')}</span>
          <span class="sep">·</span><span>${esc(isZh() ? '預測' : 'horizon')} ${status.horizonDays}${esc(isZh() ? ' 天' : 'd')}</span>
        ` : `<span class="sep">·</span><span>${esc(status.url || '')}</span>`}
      </div>

      <div class="card">
        <label class="muted small" for="fc-pick">${esc(isZh() ? '選擇商品' : 'Choose a product')}</label>
        <div class="searchbar" style="margin-top:6px">
          <select class="input" id="fc-pick" style="max-width:460px">
            ${ctx.products.map((p) => `<option value="${p.id}">${p.emoji} ${esc(pName(p))} — ${fmtPrice(p.price)}</option>`).join('')}
          </select>
        </div>
        <div class="forecast-layout" style="margin-top:18px">
          <div class="chart-card" id="fc-chart"><div class="empty">${esc(t('common.loading'))}</div></div>
          <div id="fc-panel"><div class="empty">${esc(t('common.loading'))}</div></div>
        </div>
      </div>

      <div id="fc-eval"></div>
    </section>
  `;

  const select = root.querySelector('#fc-pick');
  const chartEl = root.querySelector('#fc-chart');
  const panel = root.querySelector('#fc-panel');

  async function load(id) {
    chartEl.innerHTML = `<div class="empty">${esc(t('common.loading'))}</div>`;
    panel.innerHTML = `<div class="empty">${esc(t('common.loading'))}</div>`;
    try {
      const f = await getJSON(`/api/forecast/${id}`);
      renderPriceChart(chartEl, f.history, f.forecast);
      chartEl.innerHTML += `
        <div class="legend">
          <span><span class="dot" style="background:#8B7BFF"></span>${esc(t('pp.history'))}</span>
          <span><span class="dot" style="background:#FF8A66"></span>${esc(t('pp.forecast'))}</span>
          ${f.engine === 'prophet' ? `<span><span class="dot" style="background:rgba(255,122,89,.3)"></span>${esc(isZh() ? '80% 信賴區間' : '80% interval')}</span>` : ''}
        </div>`;
      panel.innerHTML = advisoryHTML(f);
    } catch {
      chartEl.innerHTML = `<div class="empty">${esc(t('common.retry'))}</div>`;
    }
  }

  select.addEventListener('change', () => load(select.value));
  await load(select.value);
  renderEval(root.querySelector('#fc-eval'), evalDoc);
}

function advisoryHTML(f) {
  const { advisory } = f;
  const isBuy = advisory.action === 'buy';
  const headline = isZh() ? (advisory.headline_zh || advisory.headline) : advisory.headline;
  const reasoning = isZh() ? (advisory.reasoning_zh || advisory.reasoning) : advisory.reasoning;
  const conf = isZh() ? (advisory.confidence_zh || advisory.confidence) : advisory.confidence;

  return `
    <div class="advisory-box ${isBuy ? 'buy' : 'wait'}">
      <span class="badge ${isBuy ? 'badge-buy' : 'badge-wait'}">${isBuy ? '🟢 ' : '🟡 '}${esc(headline)}</span>
      <p style="margin-top:12px">${esc(reasoning)}</p>
    </div>

    <div class="card" style="margin-top:14px; padding:16px">
      <div class="summary-line"><span>${esc(t('pp.current'))}</span><strong>${fmtPrice(f.current)}</strong></div>
      ${f.trend.horizonChangePct != null ? `<div class="summary-line"><span>${esc(isZh() ? `${f.horizonDays} 天趨勢` : `${f.horizonDays}-day trend`)}</span><strong>${f.trend.horizonChangePct > 0 ? '+' : ''}${f.trend.horizonChangePct}%</strong></div>` : `<div class="summary-line"><span>${esc(t('pp.trend'))}</span><strong>${f.trend.weeklyChangePct > 0 ? '+' : ''}${f.trend.weeklyChangePct}%</strong></div>`}
      ${advisory.action === 'wait' ? `<div class="summary-line"><span>${esc(t('pp.projected'))}</span><strong>−${advisory.expectedDropPct}%</strong></div>` : ''}
      <div style="margin-top:10px">
        <div class="summary-line" style="padding-bottom:4px"><span>${esc(t('common.confidence'))}</span><strong>${esc(conf)}</strong></div>
        <div class="confidence-bar"><div class="confidence-fill" style="width:${Math.round(advisory.confidenceScore * 100)}%"></div></div>
      </div>
    </div>

    ${(f.events && f.events.length) ? `<div class="card" style="margin-top:14px; padding:16px">
      <h3 style="font-size:0.95rem;margin:0 0 10px">🗓️ ${esc(isZh() ? '窗口內的購物節' : 'Sales in the window')}</h3>
      ${f.events.map((e) => `
        <div class="summary-line">
          <span>${esc(e.label)} <span class="muted small">${e.daysAway}${esc(isZh() ? ' 天後' : 'd')}</span></span>
          <span><strong>${fmtPrice(e.predictedPrice)}</strong> <span class="badge badge-wait">−${e.dropPct}%</span></span>
        </div>`).join('')}
    </div>` : ''}

    ${f.comparison && f.comparison.models ? comparisonHTML(f.comparison) : ''}

    <p class="muted small" style="margin-top:14px">
      ${esc(isZh() ? '模型：' : 'Engine: ')}<strong>${esc(f.engineLabel)}</strong>
      ${f.fitSeconds != null ? ` · ${esc(isZh() ? '擬合' : 'fit')} ${f.fitSeconds}s` : ''}
    </p>
  `;
}

function comparisonHTML(comp) {
  return `<div class="card" style="margin-top:14px; padding:16px">
    <h3 style="font-size:0.95rem;margin:0 0 4px">🧪 ${esc(isZh() ? '留出法比較（最近 30 天）' : 'Holdout comparison (last 30 days)')}</h3>
    <p class="muted small" style="margin:0 0 10px">${esc(isZh() ? '同一份資料、同一段留出期，比較三種模型' : 'Same data, same holdout window, three models')}</p>
    <div class="table-scroll"><table class="offer-table" style="min-width:0">
      <thead><tr>
        <th>${esc(isZh() ? '模型' : 'Model')}</th>
        <th>MAE</th><th>RMSE</th><th>MAPE</th>
      </tr></thead>
      <tbody>
        ${comp.models.map((m) => `<tr class="${m.name === comp.best ? 'best' : ''}">
          <td>${esc(m.name)}${m.name === comp.best ? ' 🏆' : ''}</td>
          <td class="mono">${m.mae ?? '—'}</td>
          <td class="mono">${m.rmse ?? '—'}</td>
          <td class="mono">${m.mape != null ? m.mape + '%' : '—'}</td>
        </tr>`).join('')}
      </tbody>
    </table></div>
  </div>`;
}

function renderEval(host, doc) {
  if (!host) return;
  if (!doc || !doc.aggregate) {
    host.innerHTML = `<div class="card" style="margin-top:18px">
      <h3>🧪 ${esc(isZh() ? '全站模型比較' : 'Catalogue-wide comparison')}</h3>
      <p class="muted small">${esc(isZh()
        ? '執行 tools/eval_forecast.py 後，這裡會顯示 40 件商品的平均誤差比較。'
        : 'Run tools/eval_forecast.py to populate the 40-product average error comparison here.')}</p>
    </div>`;
    return;
  }
  const zh = isZh();
  host.innerHTML = `<div class="card" style="margin-top:18px">
    <div class="row-between">
      <h3 style="margin:0">🧪 ${esc(zh ? '全站模型比較' : 'Catalogue-wide comparison')}</h3>
      <span class="badge badge-info">${doc.productsEvaluated} ${esc(zh ? '件商品' : 'products')}</span>
    </div>
    <p class="muted small" style="margin:6px 0 12px">
      ${esc(zh ? `每件商品留出最後 ${doc.holdoutDays} 天不訓練，再用來評分。` : `The last ${doc.holdoutDays} days of each product are held out and used to score each model.`)}
    </p>
    <div class="table-scroll"><table class="offer-table" style="min-width:520px">
      <thead><tr>
        <th>${esc(zh ? '模型' : 'Model')}</th><th>MAE</th><th>RMSE</th>
        <th>MAPE</th><th>${esc(zh ? '中位數 MAPE' : 'median MAPE')}</th>
        <th>${esc(zh ? '勝出商品數' : 'Wins')}</th>
      </tr></thead>
      <tbody>
        ${doc.aggregate.map((a) => `<tr class="${a.name === 'Prophet' ? 'best' : ''}">
          <td>${esc(a.name)}${a.name === 'Prophet' ? ' 🏆' : ''}</td>
          <td class="mono">${a.mae}</td>
          <td class="mono">${a.rmse}</td>
          <td class="mono">${a.mape}%</td>
          <td class="mono">${a.mapeMedian}%</td>
          <td class="mono">${doc.wins?.[a.name] ?? '—'} / ${doc.productsEvaluated}</td>
        </tr>`).join('')}
      </tbody>
    </table></div>
    <p class="muted small" style="margin-top:12px">⚠️ ${esc(zh
      ? '資料為合成價格序列，且購物節日期對 Prophet 已知，因此與線性基準的差距是上限值；真實零售資料會更吵雜。'
      : 'The price feed is synthetic and its sale calendar is known to Prophet, so the gap over the linear baseline is an upper bound.')}</p>
  </div>`;
}
