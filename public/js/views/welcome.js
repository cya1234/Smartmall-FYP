// js/views/welcome.js — the ten-question welcome survey.
//
// Purpose is cold start: before anything is clicked there is nothing to personalise
// on, so this gives category, style, palette and three pairwise comparisons in one
// sitting. The pairs reuse the same winner/loser shape the preference survey already
// learns from, so the answers are usable immediately rather than needing their own
// model.
import { postJSON } from '../api.js';
import { esc, t, isZh, toast, mediaInner } from '../ui.js';

const CATEGORIES = ['Apparel', 'Footwear', 'Accessories', 'Winter & Snow', 'Home', 'Electronics'];
const STYLES = ['Minimal', 'Smart Casual', 'Classic', 'Street', 'Sporty', 'Bold'];
const COLOURS = ['Black', 'White', 'Navy', 'Beige', 'Grey', 'Green', 'Rust', 'Coral', 'Pink'];
const OCCASIONS = ['Work', 'Weekend', 'Travel', 'Party', 'Sport', 'Home'];
const MATERIALS = ['Linen', 'Cotton', 'Wool', 'Denim', 'Leather', 'Technical'];
const BUDGETS = [
  { key: 'low', zh: 'HK$300 以下', en: 'Under HK$300', min: 0, max: 300 },
  { key: 'mid', zh: 'HK$300–800', en: 'HK$300–800', min: 300, max: 800 },
  { key: 'high', zh: 'HK$800–1,500', en: 'HK$800–1,500', min: 800, max: 1500 },
  { key: 'top', zh: 'HK$1,500 以上', en: 'HK$1,500+', min: 1500, max: 5000 },
];

export async function render(root, ctx) {
  const state = {
    step: 0,
    categories: new Set(),
    styles: new Set(),
    colours: new Set(),
    avoidColours: new Set(),
    occasions: new Set(),
    materials: new Set(),
    budget: 'mid',
    pairs: [],
    busy: false,
  };

  // Three comparisons drawn from products that actually exist, spread across
  // categories so the answers are informative rather than three jackets.
  const pool = (ctx.products || []).filter((p) => p.image);
  const picks = [];
  const usedCats = new Set();
  for (const p of pool) {
    if (picks.length >= 6) break;
    if (usedCats.has(p.category)) continue;
    usedCats.add(p.category);
    picks.push(p);
  }
  for (const p of pool) {
    if (picks.length >= 6) break;
    if (!picks.includes(p)) picks.push(p);
  }
  const pairs = [];
  for (let i = 0; i + 1 < picks.length && pairs.length < 3; i += 2) {
    pairs.push([picks[i], picks[i + 1]]);
  }

  const chip = (label, active, dataAttr) =>
    `<button class="chip ${active ? 'active' : ''}" ${dataAttr}>${esc(label)}</button>`;

  function paint() {
    const l = (zh, en) => (isZh() ? zh : en);

    root.innerHTML = `<section class="container" style="max-width:820px">
      <h1 class="section-title">👋 ${esc(l('十條問題，讓我們更懂你', 'Ten questions so we know what you like'))}</h1>
      <p class="section-sub">${esc(l(
        '答案只用來調整推薦排序，兩分鐘可以填完，也可以之後再補。',
        'Your answers only reorder recommendations. Two minutes, and you can redo them any time.',
      ))}</p>

      <div class="card">
        <h3 style="margin:0 0 2px">1. ${esc(l('你主要想逛什麼？', 'What are you mostly shopping for?'))}</h3>
        <p class="muted small" style="margin:0 0 10px">${esc(l('可選多項', 'pick any'))}</p>
        <div class="chips">${CATEGORIES.map((c) => chip(c, state.categories.has(c), `data-cat="${esc(c)}"`)).join('')}</div>
      </div>

      <div class="card">
        <h3 style="margin:0 0 2px">2. ${esc(l('你喜歡哪種風格？', 'Which styles do you like?'))}</h3>
        <div class="chips" style="margin-top:10px">${STYLES.map((s) => chip(s, state.styles.has(s), `data-style="${esc(s)}"`)).join('')}</div>
      </div>

      <div class="card">
        <h3 style="margin:0 0 2px">3. ${esc(l('你平常的預算？', 'Your usual budget?'))}</h3>
        <div class="chips" style="margin-top:10px">${BUDGETS.map((b) => chip(isZh() ? b.zh : b.en, state.budget === b.key, `data-budget="${b.key}"`)).join('')}</div>
      </div>

      <div class="card">
        <h3 style="margin:0 0 2px">4. ${esc(l('你會在哪裡穿？', 'Where do you wear it?'))}</h3>
        <div class="chips" style="margin-top:10px">${OCCASIONS.map((o) => chip(o, state.occasions.has(o), `data-occ="${esc(o)}"`)).join('')}</div>
      </div>

      <div class="card">
        <h3 style="margin:0 0 2px">5. ${esc(l('你喜歡的顏色？', 'Colours you like?'))}</h3>
        <div class="chips" style="margin-top:10px">${COLOURS.map((c) => chip(c, state.colours.has(c), `data-col="${esc(c)}"`)).join('')}</div>
      </div>

      <div class="card">
        <h3 style="margin:0 0 2px">6. ${esc(l('盡量不要的顏色？', 'Colours to avoid?'))}</h3>
        <div class="chips" style="margin-top:10px">${COLOURS.map((c) => chip(c, state.avoidColours.has(c), `data-avoid="${esc(c)}"`)).join('')}</div>
      </div>

      ${pairs.map((pair, i) => `
      <div class="card">
        <h3 style="margin:0 0 2px">${7 + i}. ${esc(l('你更喜歡哪一件？', 'Which would you rather wear?'))}</h3>
        <div style="position:relative;display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:12px">
          ${pair.map((p, side) => `
            <button data-pair="${i}" data-side="${side}"
              style="padding:0;border:1px solid var(--line);border-radius:14px;overflow:hidden;
                     background:var(--surface);cursor:pointer;display:flex;flex-direction:column;text-align:left">
              <span style="height:190px;background:#fff;display:flex;align-items:center;justify-content:center;padding:8px">
                <img src="${esc(p.image)}" alt="" style="width:100%;height:100%;object-fit:contain" />
              </span>
              <span style="padding:10px 12px 12px">
                <strong style="font-size:0.9rem">${esc(isZh() ? (p.name_zh || p.name) : p.name)}</strong>
                <span class="muted small" style="display:block;margin-top:2px">${esc(p.colorName || '')}</span>
              </span>
            </button>`).join('')}
        </div>
      </div>`).join('')}

      <div class="card">
        <h3 style="margin:0 0 2px">10. ${esc(l('你偏好什麼材質？', 'Preferred materials?'))}</h3>
        <div class="chips" style="margin-top:10px">${MATERIALS.map((m) => chip(m, state.materials.has(m), `data-mat="${esc(m)}"`)).join('')}</div>
      </div>

      <div style="display:flex;gap:10px;margin:18px 0 40px;flex-wrap:wrap">
        <button class="btn btn-primary" id="w-save" ${state.busy ? 'disabled' : ''} style="flex:1;min-width:200px">
          ${esc(state.busy ? l('儲存中…', 'Saving…') : l('完成，開始逛', 'Done — start browsing'))}
        </button>
        <button class="btn btn-ghost" id="w-skip">${esc(l('稍後再填', 'Later'))}</button>
      </div>
    </section>`;

    const bindChip = (attr, set) => root.querySelectorAll(`[${attr}]`).forEach((b) =>
      b.addEventListener('click', () => {
        const v = b.getAttribute(attr);
        if (set.has(v)) set.delete(v);
        else set.add(v);
        paint();
      }));
    bindChip('data-cat', state.categories);
    bindChip('data-style', state.styles);
    bindChip('data-col', state.colours);
    bindChip('data-avoid', state.avoidColours);
    bindChip('data-occ', state.occasions);
    bindChip('data-mat', state.materials);

    root.querySelectorAll('[data-budget]').forEach((b) => b.addEventListener('click', () => {
      state.budget = b.getAttribute('data-budget');
      paint();
    }));

    root.querySelectorAll('[data-pair]').forEach((b) => b.addEventListener('click', () => {
      const i = Number(b.getAttribute('data-pair'));
      const side = Number(b.getAttribute('data-side'));
      const [a, bb] = pairs[i];
      const winner = side === 0 ? a : bb;
      const loser = side === 0 ? bb : a;
      state.pairs = state.pairs.filter((p) => p.key !== `pair${i}`);
      state.pairs.push({ key: `pair${i}`, winner: winner.id, loser: loser.id });
      b.style.borderColor = 'var(--brand)';
      toast(isZh() ? `已記錄：${winner.name_zh || winner.name}` : `Noted: ${winner.name}`);
    }));

    root.querySelector('#w-skip').addEventListener('click', () => ctx.navigate('/'));
    root.querySelector('#w-save').addEventListener('click', save);
  }

  async function save() {
    if (state.busy) return;
    state.busy = true;
    paint();
    const band = BUDGETS.find((b) => b.key === state.budget) || BUDGETS[1];
    try {
      await postJSON('/api/onboarding', {
        categories: [...state.categories],
        styles: [...state.styles],
        colours: [...state.colours],
        avoidColours: [...state.avoidColours],
        occasions: [...state.occasions],
        materials: [...state.materials],
        budget: { min: band.min, max: band.max },
        pairs: state.pairs.map(({ winner, loser }) => ({ winner, loser })),
      });
      try { localStorage.setItem('smartmall-onboarded', '1'); } catch { /* ignore */ }
      state.busy = false;
      toast(isZh() ? '已套用你的偏好' : 'Preferences applied');
      ctx.navigate('/');
    } catch {
      state.busy = false;
      paint();
      toast(isZh() ? '儲存失敗，請再試一次' : 'Could not save — try again');
    }
  }

  paint();
}
