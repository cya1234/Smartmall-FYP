// js/views/blindbox.js — Feature 1: AI buyer blind box (scenario kit).
import { getJSON, postJSON } from '../api.js';
import { esc, fmtPrice, toast, hexA, pName, t, isZh, currency, mediaInner } from '../ui.js';
import { addToCart } from '../cart.js';

export async function render(root, ctx) {
  let scenarios = [];
  try {
    scenarios = (await getJSON('/api/blindbox/scenarios')).scenarios;
  } catch { /* fall back to free text */ }

  const sample = isZh()
    ? '預算 2000 元，下個月去北海道滑雪，需要一套裝備'
    : 'Budget 2000, skiing in Hokkaido next month, I need a full set of gear';

  root.innerHTML = `
    <section class="container">
      <h1 class="section-title">${esc(t('bb.title'))}</h1>
      <p class="section-sub">${esc(t('bb.sub'))}</p>

      <div class="bb-layout">
        <div class="card bb-form">
          <div class="bb-field">
            <label for="bb-query">${esc(t('bb.query'))}</label>
            <textarea class="input" id="bb-query" rows="3" placeholder="${esc(t('bb.queryPh'))}">${esc(sample)}</textarea>
          </div>

          <div class="bb-field">
            <label>${esc(t('bb.scenario'))}</label>
            <div class="bb-scenarios" id="bb-scenarios">
              <button class="bb-scenario active" data-sc="">${esc(t('bb.auto'))}</button>
              ${scenarios.map((s) => `<button class="bb-scenario" data-sc="${s.id}"><span class="e">${s.emoji}</span>${esc(isZh() ? s.label_zh : s.label)}</button>`).join('')}
            </div>
          </div>

          <div class="bb-field">
            <label for="bb-budget">${esc(t('bb.budget'))} (${currency().symbol})</label>
            <input class="input" id="bb-budget" type="number" min="0" step="100" value="2000" />
          </div>

          <div class="bb-field">
            <label class="toggle-row"><input type="checkbox" id="bb-wardrobe" checked /> ${esc(t('bb.useWardrobe'))}</label>
          </div>

          <button class="btn btn-primary btn-block" id="bb-go">${esc(t('bb.generate'))}</button>
        </div>

        <div id="bb-result">
          <div class="card box-reveal">
            <div class="box">🎁</div>
            <p class="muted" style="margin-top:14px">${esc(t('bb.sub'))}</p>
          </div>
        </div>
      </div>
    </section>
  `;

  let scenarioId = '';
  root.querySelectorAll('#bb-scenarios .bb-scenario').forEach((b) =>
    b.addEventListener('click', () => {
      root.querySelectorAll('#bb-scenarios .bb-scenario').forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      scenarioId = b.dataset.sc;
    }));

  const result = root.querySelector('#bb-result');

  root.querySelector('#bb-go').addEventListener('click', async () => {
    const query = root.querySelector('#bb-query').value.trim();
    const budget = Number(root.querySelector('#bb-budget').value);
    const useWardrobe = root.querySelector('#bb-wardrobe').checked;
    if (!query && !scenarioId) { toast(t('bb.empty')); return; }

    // Mysterious "box opening" beat before the reveal.
    result.innerHTML = `<div class="card box-reveal"><div class="box">🎁</div><p class="muted" style="margin-top:14px">${esc(t('bb.generating'))}</p></div>`;
    try {
      const res = await postJSON('/api/blindbox', {
        query, scenarioId: scenarioId || null,
        budget: Number.isFinite(budget) ? budget : null,
        lang: isZh() ? 'zh' : 'en', useWardrobe,
      });
      ctx.state.blindboxResult = res;
      setTimeout(() => renderResult(result, res, ctx), 650);
    } catch {
      result.innerHTML = `<div class="card">${esc(t('common.retry'))}</div>`;
    }
  });

  // Restore a previous result after a language switch.
  if (ctx.state.blindboxResult) renderResult(result, ctx.state.blindboxResult, ctx);
}

function renderResult(host, res, ctx) {
  const overBudget = res.budgetRemaining != null && res.budgetRemaining < 0;
  const items = res.items || [];
  const newItems = items.filter((i) => !i.owned);

  host.innerHTML = `
    <div class="card">
      <div class="row-between">
        <div>
          <h3 style="margin:0">${res.scenario.emoji} ${esc(isZh() ? res.scenario.label_zh : res.scenario.label)}</h3>
          <p class="muted small" style="margin:4px 0 0">${esc(isZh() ? res.scenario.blurb_zh : res.scenario.blurb)}</p>
        </div>
        <span class="badge badge-info">${items.length} ${esc(t('common.items'))}</span>
      </div>

      <div class="bb-summary" style="margin-top:18px">
        <div class="stat ${res.coverage === 100 ? 'good' : 'warn'}">
          <div class="k">${esc(t('bb.coverage'))}</div><div class="v">${res.coverage}%</div>
        </div>
        <div class="stat">
          <div class="k">${esc(t('bb.newTotal'))}</div><div class="v">${fmtPrice(res.total)}</div>
        </div>
        ${res.ownedValue > 0 ? `<div class="stat good">
          <div class="k">${esc(t('bb.ownedValue'))}</div><div class="v">−${fmtPrice(res.ownedValue)}</div>
        </div>` : ''}
        ${res.budgetRemaining != null ? `<div class="stat ${overBudget ? 'warn' : 'good'}">
          <div class="k">${esc(overBudget ? t('bb.overBudget') : t('bb.budgetLeft'))}</div>
          <div class="v">${fmtPrice(Math.abs(res.budgetRemaining))}</div>
        </div>` : ''}
      </div>

      <p class="small" style="color:var(--ink-2);line-height:1.6">${esc(res.rationale)}</p>

      ${res.missing && res.missing.length ? `<div class="divider"></div>
        <div class="badge badge-warn" style="margin-bottom:8px">⚠️ ${esc(t('bb.missing'))}: ${res.missing.map((m) => esc(isZh() ? m.label_zh : m.label)).join('、')}</div>
        <div class="muted small">${esc(t('bb.minBudget'))}: <b class="hl">${fmtPrice(res.minEssential)}</b></div>` : ''}

      <div class="divider"></div>
      <div class="set-grid">
        ${items.map((i) => `
          <div class="set-item ${i.owned ? 'is-owned' : ''}" data-id="${esc(i.product.id)}" style="cursor:pointer">
            ${i.owned ? `<span class="owned-flag">${esc(t('common.owned'))}</span>` : ''}
            <div class="thumb" style="background:linear-gradient(135deg, ${hexA(i.product.color, 0.14)}, ${hexA(i.product.color, 0.3)})">${mediaInner(i.product, '2.6rem')}</div>
            <div class="body">
              <div class="role">${esc(isZh() ? (i.role_zh || i.role) : i.role)}</div>
              <div class="nm">${esc(pName(i.product))}</div>
              <div class="pr">${i.owned
                ? `<span class="owned-strike">${fmtPrice(i.product.price)}</span>`
                : fmtPrice(i.product.price)}</div>
              <div class="note">${esc(i.note)}</div>
            </div>
          </div>`).join('')}
      </div>

      <div class="row-between" style="margin-top:18px">
        <span class="muted small">${newItems.length} ${esc(t('common.items'))} · ${fmtPrice(res.total)}</span>
        <button class="btn btn-primary" id="bb-add">🛒 ${esc(t('common.addAll'))}</button>
      </div>
    </div>

    <div class="card">
      <h3>${esc(t('bb.tiers'))}</h3>
      <div class="tier-grid">
        ${res.tiers.map((tr) => `
          <div class="tier ${tr.id === 'complete' ? 'recommended' : ''}">
            <div class="tn">${esc(tr.name)}</div>
            <div class="tp">${fmtPrice(tr.total)}</div>
            <div class="td">${esc(tr.note)} · ${tr.count} ${esc(t('common.items'))}</div>
            <div class="tf"><span class="badge ${tr.fitsBudget ? 'badge-good' : 'badge-warn'}">${tr.fitsBudget ? esc(t('bb.fits')) : esc(t('bb.over'))}</span></div>
          </div>`).join('')}
      </div>
    </div>
  `;

  host.querySelectorAll('.set-item').forEach((el) =>
    el.addEventListener('click', () => ctx.navigate(`/product/${el.dataset.id}`)));
  host.querySelector('#bb-add').addEventListener('click', () => {
    newItems.forEach((i) => addToCart(i.product.id, 1));
    toast(`${newItems.length} ${t('common.items')} → ${t('nav.cart')}`);
  });
}
