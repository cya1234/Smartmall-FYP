// js/views/home.js
import { productCard, esc, t } from '../ui.js';

const FEATURES = [
  { key: 'blindbox', route: 'blindbox', emoji: '🎁', accent: true },
  { key: 'assistant', route: 'assistant', emoji: '👗' },
  { key: 'visual', route: 'visual', emoji: '🔍' },
  { key: 'forecast', route: 'forecast', emoji: '📈' },
  { key: 'stores', route: 'stores', emoji: '🏬' },
  { key: 'tryon', route: 'tryon', emoji: '🧥' },
  { key: 'price', route: 'priceagent', emoji: '🤝' },
  { key: 'resale', route: 'resale', emoji: '♻️' },
  { key: 'memory', route: 'memory', emoji: '⭐' },
  { key: 'support', route: 'support', emoji: '💬' },
];

export function render(root, ctx) {
  // The welcome survey is offered, never forced: a shopper can browse first and
  // answer later, and the banner simply stops appearing once it has been filled in.
  let onboarded = true;
  try { onboarded = localStorage.getItem('smartmall-onboarded') === '1'; } catch { onboarded = true; }

  const featured = [...ctx.products]
    .sort((a, b) => b.rating * Math.log(b.reviews + 1) - a.rating * Math.log(a.reviews + 1))
    .slice(0, 8);
  const categories = [...new Set(ctx.products.map((p) => p.category))];

  root.innerHTML = `
    ${onboarded ? '' : `
    <section class="container" style="padding-bottom:0">
      <div class="card" style="display:flex;gap:14px;align-items:center;flex-wrap:wrap;border-color:var(--brand)">
        <div style="flex:1;min-width:220px">
          <strong>${esc(isZh() ? '👋 第一次來？' : '👋 First time here?')}</strong>
          <p class="muted small" style="margin:4px 0 0">${esc(isZh()
            ? '回答 10 條問題，推薦會立刻按你的口味排序。'
            : 'Ten questions and the recommendations reorder around your taste.')}</p>
        </div>
        <button class="btn btn-primary" data-go="welcome">${esc(isZh() ? '開始（2 分鐘）' : 'Start (2 min)')}</button>
      </div>
    </section>`}
    <section class="hero">
      <div class="hero-inner">
        <div>
          <h1>${esc(t('home.hero.title'))} <span class="grad">${esc(t('home.hero.titleAccent'))}</span></h1>
          <p>${esc(t('home.hero.sub'))}</p>
          <div class="hero-cta">
            <button class="btn btn-primary" data-go="blindbox">${esc(t('home.hero.cta1'))}</button>
            <button class="btn btn-ghost" data-go="assistant">${esc(t('home.hero.cta2'))}</button>
          </div>
        </div>
        <div class="hero-cards">
          ${FEATURES.slice(0, 4).map((f) => `
            <div class="hero-card" data-go="${f.route}" style="cursor:pointer">
              <div class="emoji">${f.emoji}</div>
              <h3>${esc(t(`feat.${f.key}.t`))}</h3>
              <p>${esc(t(`feat.${f.key}.d`))}</p>
            </div>`).join('')}
        </div>
      </div>
    </section>

    <section class="container">
      <h2 class="section-title">${esc(t('home.features'))}</h2>
      <p class="section-sub">${esc(t('home.feature.sub'))}</p>
      <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(260px,1fr))">
        ${FEATURES.map((f) => `
          <article class="hero-card" data-go="${f.route}" style="cursor:pointer;${f.accent ? 'border-color:var(--brand);box-shadow:0 0 0 3px var(--brand-soft)' : ''}">
            <div class="emoji">${f.emoji}</div>
            <h3>${esc(t(`feat.${f.key}.t`))}</h3>
            <p style="color:var(--ink-2)">${esc(t(`feat.${f.key}.d`))}</p>
          </article>`).join('')}
      </div>
    </section>

    <section class="container">
      <h2 class="section-title">${esc(t('home.featured'))}</h2>
      <p class="section-sub">${esc(t('home.featured.sub'))}</p>
      <div class="grid">${featured.map(productCard).join('')}</div>
    </section>

    <section class="container">
      <h2 class="section-title">${esc(t('home.categories'))}</h2>
      <p class="section-sub">${esc(t('home.categories.sub'))}</p>
      <div class="chips">
        ${categories.map((c) => `<button class="chip" data-cat="${esc(c)}">${esc(c)}</button>`).join('')}
      </div>
    </section>
  `;

  root.querySelectorAll('[data-go]').forEach((b) =>
    b.addEventListener('click', () => ctx.navigate(`/${b.dataset.go}`)));
  root.querySelectorAll('.product-card').forEach((el) =>
    el.addEventListener('click', () => ctx.navigate(`/product/${el.dataset.id}`)));
  root.querySelectorAll('[data-cat]').forEach((b) =>
    b.addEventListener('click', () => {
      ctx.state.shopCategory = b.dataset.cat;
      ctx.state.shopQuery = '';
      ctx.navigate('/shop');
    }));
}
