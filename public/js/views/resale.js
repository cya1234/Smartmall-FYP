// js/views/resale.js — Feature 3: one-click second-hand consignment.
import { getJSON, postJSON } from '../api.js';
import { esc, fmtPrice, toast, hexA, pName, t, isZh, mediaInner } from '../ui.js';

export async function render(root, ctx) {
  root.innerHTML = `<section class="container"><div class="card">${esc(t('common.loading'))}</div></section>`;

  let data;
  try {
    data = await getJSON('/api/resale');
  } catch {
    root.innerHTML = `<section class="container"><div class="card">${esc(t('common.retry'))}</div></section>`;
    return;
  }
  const { listings, eco } = data;

  let consignable = { items: [], conditions: [] };
  try { consignable = await getJSON('/api/resale/consignable'); } catch { /* ignore */ }

  const conditions = consignable.conditions || [];

  root.innerHTML = `
    <section class="container">
      <h1 class="section-title">${esc(t('rs.title'))}</h1>
      <p class="section-sub">${esc(t('rs.sub'))}</p>

      <div class="card" style="margin-bottom:18px">
        <h3>${esc(t('rs.ecoTitle'))}</h3>
        <div class="eco-strip">
          <span class="eco-pill">♻️ ${esc(t('rs.recirculated'))}: ${eco.itemsRecirculated}</span>
          <span class="eco-pill">🌱 ${esc(t('rs.co2'))}: ${eco.co2Saved} kg</span>
          <span class="eco-pill">💧 ${esc(t('rs.water'))}: ${eco.waterSaved.toLocaleString()} L</span>
          <span class="eco-pill">💰 ${esc(t('rs.earnings'))}: ${fmtPrice(eco.earnings)}</span>
        </div>
      </div>

      <div class="rs-layout">
        <div class="card">
          <h3>${esc(t('rs.myWardrobe'))}</h3>
          <p class="muted small">${esc(t('rs.pick'))}</p>
          <div id="rs-picks" style="margin-top:12px">
            ${consignable.items.map((w) => `
              <div class="wardrobe-pick" data-id="${esc(w.productId)}">
                <span class="we">${w.product.emoji}</span>
                <div style="flex:1">
                  <div class="wn">${esc(pName(w.product))}</div>
                  <div class="wm">${w.purchasedLabel} · ${w.wears} ${esc(t('mem.wears'))} · ${esc(w.condition)}</div>
                </div>
                <div class="muted small">${fmtPrice(w.product.price)}</div>
              </div>`).join('') || `<div class="muted small">—</div>`}
          </div>

          <div class="bb-field" style="margin-top:16px">
            <label for="rs-cond">${esc(t('rs.condition'))}</label>
            <select class="input" id="rs-cond">
              ${conditions.map((c) => `<option value="${c.value}">${esc(c.label)}</option>`).join('')}
            </select>
          </div>
          <div class="bb-field">
            <label for="rs-months">${esc(t('rs.monthsOwned'))}</label>
            <input class="input" id="rs-months" type="number" min="1" max="60" value="6" />
          </div>
          <div class="bb-field">
            <label for="rs-note">${esc(t('rs.note'))}</label>
            <input class="input" id="rs-note" placeholder="e.g. 少穿，保存良好" />
          </div>
          <button class="btn btn-primary btn-block" id="rs-draft" disabled>${esc(t('rs.draft'))}</button>
        </div>

        <div>
          <div id="rs-draftbox"></div>
          <div class="card" style="margin-top:18px">
            <h3>🏬 ${esc(t('rs.market'))}</h3>
            <div class="listing-grid" style="margin-top:12px">
              ${listings.map(listingCard).join('')}
            </div>
          </div>
        </div>
      </div>
    </section>
  `;

  let picked = null;
  root.querySelectorAll('.wardrobe-pick').forEach((el) =>
    el.addEventListener('click', () => {
      root.querySelectorAll('.wardrobe-pick').forEach((x) => x.classList.remove('active'));
      el.classList.add('active');
      picked = el.dataset.id;
      root.querySelector('#rs-draft').disabled = false;
    }));

  const draftBox = root.querySelector('#rs-draftbox');

  root.querySelector('#rs-draft').addEventListener('click', async () => {
    if (!picked) return;
    draftBox.innerHTML = `<div class="card box-reveal"><div class="box">📝</div><p class="muted" style="margin-top:14px">${esc(t('rs.drafting'))}</p></div>`;
    try {
      const draft = await postJSON('/api/resale/draft', {
        productId: picked,
        condition: root.querySelector('#rs-cond').value,
        monthsOwned: Number(root.querySelector('#rs-months').value) || 6,
        note: root.querySelector('#rs-note').value.trim(),
        lang: isZh() ? 'zh' : 'en',
      });
      renderDraft(draftBox, draft, root, ctx);
    } catch {
      draftBox.innerHTML = `<div class="card">${esc(t('common.retry'))}</div>`;
    }
  });

  root.querySelectorAll('[data-buy]').forEach((b) =>
    b.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        await postJSON(`/api/resale/${b.dataset.buy}/buy`, {});
        toast(isZh() ? '已購買！形成買賣循環 ♻️' : 'Purchased — the loop closes ♻️');
        render(root, ctx);
      } catch { toast(t('common.retry')); }
    }));
}

function listingCard(l) {
  return `<div class="listing ${l.status === 'sold' ? 'sold' : ''}">
    <div class="thumb" style="background:linear-gradient(135deg, ${hexA(l.product.color, 0.14)}, ${hexA(l.product.color, 0.3)})">
      ${l.mine ? `<span class="mine-flag">${esc(t('rs.mine'))}</span>` : ''}
      <span class="cond-flag">${esc(isZh() ? l.conditionLabel.zh : l.conditionLabel.en)}</span>
      ${mediaInner(l.product, '3rem')}
    </div>
    <div class="body">
      <div class="ti">${esc(isZh() ? (l.title.includes('｜') ? l.title : l.product.name_zh || l.title) : l.title)}</div>
      <div class="seller">${l.seller.avatar} ${esc(isZh() ? l.seller.name : (l.seller.name_en || l.seller.name))} ★ ${l.seller.rating} · ${l.views} ${esc(t('rs.views'))}</div>
      <div class="price-row">
        <span class="p">${fmtPrice(l.price)}</span>
        <span class="op">${fmtPrice(l.originalPrice)}</span>
        <span class="off">−${l.discountPct}%</span>
      </div>
      ${l.status === 'sold'
        ? `<button class="btn btn-ghost btn-sm btn-block" disabled>${esc(t('rs.sold'))}</button>`
        : `<button class="btn btn-primary btn-sm btn-block" data-buy="${esc(l.id)}">${esc(t('rs.buy'))}</button>`}
    </div>
  </div>`;
}

function renderDraft(host, d, root, ctx) {
  host.innerHTML = `
    <div class="card">
      <div class="row-between">
        <h3 style="margin:0">✨ ${esc(isZh() ? '刊登草稿' : 'Listing draft')}</h3>
        <span class="badge badge-info">${esc(d.conditionLabel.zh)}</span>
      </div>

      <div class="bb-summary" style="margin-top:16px">
        <div class="stat good"><div class="k">${esc(t('rs.suggestedPrice'))}</div><div class="v">${fmtPrice(d.price)}</div></div>
        <div class="stat"><div class="k">${esc(t('rs.priceRange'))}</div><div class="v">${fmtPrice(d.priceRange.low)}–${fmtPrice(d.priceRange.high)}</div></div>
        <div class="stat"><div class="k">${esc(t('rs.discount'))}</div><div class="v">−${d.discountPct}%</div></div>
      </div>

      <div class="set-item" style="flex-direction:row;align-items:center;gap:14px;padding:12px">
        <div class="thumb" style="width:64px;height:64px;border-radius:12px;font-size:2rem;background:linear-gradient(135deg, ${hexA(d.product.color, 0.14)}, ${hexA(d.product.color, 0.3)})">${mediaInner(d.product, '2rem')}</div>
        <div class="body" style="padding:0">
          <div class="nm">${esc(d.title)}</div>
          <div class="muted small">${esc(d.brand)} · ${esc(d.conditionLabel.zh)} · ${d.monthsOwned} ${esc(t('rs.monthsOwned'))}</div>
        </div>
      </div>

      <div class="divider"></div>
      <div style="white-space:pre-wrap;font-size:0.88rem;line-height:1.65;color:var(--ink-2)">${esc(isZh() ? d.description_zh : d.description)}</div>

      <div class="divider"></div>
      <div class="muted small" style="margin-bottom:8px">${esc(t('rs.tags'))}</div>
      <div class="chip-row">${d.tags.map((tg) => `<span class="tag-chip">${esc(tg)}</span>`).join('')}</div>

      <div class="eco-strip" style="margin-top:14px">
        <span class="eco-pill">🌱 ${esc(t('rs.co2'))}: ${d.eco.co2} kg</span>
        <span class="eco-pill">💧 ${esc(t('rs.water'))}: ${d.eco.water.toLocaleString()} L</span>
      </div>
      <p class="muted small" style="margin-top:10px">📈 ${esc(d.demandNote)}</p>

      <button class="btn btn-accent btn-block" style="margin-top:16px" id="rs-pub">${esc(t('rs.publish'))}</button>
    </div>
  `;

  host.querySelector('#rs-pub').addEventListener('click', async () => {
    try {
      await postJSON('/api/resale', {
        productId: d.productId,
        condition: d.condition,
        monthsOwned: d.monthsOwned,
        note: '',
        price: d.price,
        lang: isZh() ? 'zh' : 'en',
      });
      toast(isZh() ? '已上架二手專區！' : 'Published to the resale marketplace!');
      render(root, ctx);
    } catch { toast(t('common.retry')); }
  });
}
