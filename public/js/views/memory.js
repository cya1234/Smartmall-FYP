// js/views/memory.js — Feature 5: long-term memory & personal profile.
import { getJSON } from '../api.js';
import { esc, fmtPrice, hexA, pName, t, isZh, mediaInner } from '../ui.js';

const SLOT_LABEL = {
  top: { zh: '上身', en: 'Top' }, dress: { zh: '連身裙', en: 'Dress' },
  midlayer: { zh: '中層', en: 'Mid layer' }, outerwear: { zh: '外套', en: 'Outerwear' },
  bottom: { zh: '下身', en: 'Bottoms' }, footwear: { zh: '鞋履', en: 'Footwear' },
  bag: { zh: '包款', en: 'Bag' }, accessory: { zh: '配飾', en: 'Accessory' },
  headwear: { zh: '帽款', en: 'Headwear' }, eyewear: { zh: '眼鏡', en: 'Eyewear' },
  neckwear: { zh: '頸部', en: 'Neckwear' }, gloves: { zh: '手套', en: 'Gloves' },
  socks: { zh: '襪子', en: 'Socks' }, baselayer: { zh: '內層', en: 'Base layer' },
  beauty: { zh: '美妝', en: 'Beauty' }, gear: { zh: '科技配件', en: 'Gear' },
};

const ALL_SLOTS = Object.keys(SLOT_LABEL);

export async function render(root, ctx) {
  root.innerHTML = `<section class="container"><div class="card">${esc(t('common.loading'))}</div></section>`;

  let p;
  try {
    p = await getJSON(`/api/profile?lang=${isZh() ? 'zh' : 'en'}`);
  } catch {
    root.innerHTML = `<section class="container"><div class="card">${esc(t('common.retry'))}</div></section>`;
    return;
  }

  const u = p.user;
  const b = u.body;
  const coverage = new Set(p.coverage || []);

  root.innerHTML = `
    <section class="container">
      <h1 class="section-title">${esc(t('mem.title'))}</h1>
      <p class="section-sub">${esc(t('mem.sub'))}</p>

      <div class="mem-layout">
        <div>
          <div class="card avatar-block">
            <div class="av">${u.avatar}</div>
            <div class="nm">${esc(isZh() ? u.name : u.name_en)}</div>
            <div class="muted small">${esc(u.city)} · ${esc(u.tier)} · ${esc(u.memberSince)}</div>
          </div>

          <div class="card">
            <h3>${esc(t('mem.body'))}</h3>
            <div class="measure-grid">
              ${measure(t('mem.height'), `${b.height} cm`)}
              ${measure(t('mem.weight'), `${b.weight} kg`)}
              ${measure(t('mem.chest'), `${b.chest} cm`)}
              ${measure(t('mem.waist'), `${b.waist} cm`)}
              ${measure(t('mem.hips'), `${b.hips} cm`)}
              ${measure(t('mem.shoulder'), `${b.shoulder} cm`)}
            </div>
            <div class="divider"></div>
            <h3 style="font-size:0.95rem">${esc(t('mem.sizes'))}</h3>
            <div class="chip-row">
              <span class="tag-chip">${esc(t('mem.top'))} ${esc(u.sizes.top)}</span>
              <span class="tag-chip">${esc(t('mem.bottom'))} ${esc(u.sizes.bottom)}</span>
              <span class="tag-chip">${esc(t('mem.shoe'))} ${esc(u.sizes.shoe)}</span>
              <span class="tag-chip">🧢 ${u.sizes.headCircumference} cm</span>
            </div>
            <div class="divider"></div>
            <h3 style="font-size:0.95rem">${esc(t('mem.style'))}</h3>
            <div class="chip-row">${u.stylePreferences.map((s) => `<span class="tag-chip">${esc(s)}</span>`).join('')}</div>
            <div style="margin-top:14px">
              <div class="muted small" style="margin-bottom:6px">${esc(t('mem.colors'))}</div>
              <div class="chip-row">
                ${u.favoriteColors.map((c) => `<span class="tag-chip like">${esc(c)}</span>`).join('')}
                ${u.dislikedColors.map((c) => `<span class="tag-chip avoid">${esc(c)}</span>`).join('')}
              </div>
            </div>
            <div class="divider"></div>
            <div class="muted small">${esc(t('mem.budget'))}: <b>${fmtPrice(u.budgetRange.min)} – ${fmtPrice(u.budgetRange.max)}</b></div>
          </div>

          <div class="card">
            <h3>${esc(t('mem.coverage'))}</h3>
            <div class="coverage-grid">
              ${ALL_SLOTS.map((s) => `<span class="cov-pill ${coverage.has(s) ? 'on' : ''}">${coverage.has(s) ? '✓ ' : ''}${esc(isZh() ? SLOT_LABEL[s].zh : SLOT_LABEL[s].en)}</span>`).join('')}
            </div>
          </div>
        </div>

        <div>
          <div class="card">
            <h3>🧠 ${esc(t('mem.insights'))}</h3>
            <div class="stack" style="margin-top:14px">
              ${p.insights.map((i) => `
                <div class="insight">
                  <div class="ih"><span>${i.icon}</span><span>${esc(i.title)}</span></div>
                  <div class="ib">${esc(i.detail)}</div>
                  <div class="conf-mini"><i style="width:${Math.round(i.confidence * 100)}%"></i></div>
                </div>`).join('')}
            </div>
          </div>

          <div class="card">
            <h3>👕 ${esc(t('mem.wardrobe'))} <span class="muted small">(${p.wardrobe.length})</span></h3>
            ${p.wardrobe.map((w) => `
              <div class="wardrobe-item">
                <div class="we" style="background:linear-gradient(135deg, ${hexA(w.color, 0.14)}, ${hexA(w.color, 0.3)})">${mediaInner(w, '1.7rem')}</div>
                <div>
                  <div class="wn">${esc(isZh() ? w.name_zh || w.name : w.name)}</div>
                  <div class="wm">${esc(isZh() ? w.purchasedLabel : w.purchasedLabel_en)} · ${w.size} · ${w.wears} ${esc(t('mem.wears'))}</div>
                </div>
                <div class="wr">
                  <span class="tag-chip">${esc(w.condition)}</span>
                </div>
              </div>`).join('')}
          </div>

          <div class="card">
            <h3>📦 ${esc(t('mem.returns'))} <span class="muted small">(${p.returns.length})</span></h3>
            <div class="stack" style="margin-top:10px">
              ${p.returns.map((r) => `
                <div class="insight" style="border-left-color:var(--warn)">
                  <div class="ih"><span>↩️</span><span>${esc(isZh() ? r.name_zh || r.name : r.name)}</span>
                    <span class="badge badge-warn" style="margin-left:auto">${esc(r.reasonLabel)}</span></div>
                  <div class="ib">${esc(r.note)}<br /><span class="muted small">${esc(isZh() ? r.purchasedLabel : r.purchasedLabel_en)} · ${esc(r.size)}</span></div>
                </div>`).join('')}
            </div>
          </div>

          <div class="card">
            <h3>🕘 ${esc(t('mem.searches'))} / ${esc(t('mem.views'))}</h3>
            <div class="chip-row" style="margin-bottom:14px">
              ${p.searchHistory.map((s) => `<span class="tag-chip">🔍 ${esc(s.query)}</span>`).join('')}
            </div>
            <div class="chip-row">
              ${p.recentViews.map((v) => `<span class="tag-chip" data-id="${esc(v.id)}" style="cursor:pointer">${v.emoji} ${esc(isZh() ? v.name_zh || v.name : v.name)}</span>`).join('')}
            </div>
          </div>
        </div>
      </div>
    </section>
  `;

  root.querySelectorAll('[data-id]').forEach((el) =>
    el.addEventListener('click', () => ctx.navigate(`/product/${el.dataset.id}`)));
}

function measure(k, v) {
  return `<div class="measure"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`;
}
