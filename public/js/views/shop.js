// js/views/shop.js — browse / search / filter the catalog.
import { productCard, emptyState, esc, t, isZh, money, currency } from '../ui.js';
import { track } from '../exitIntent.js';

export function render(root, ctx) {
  const categories = [...new Set(ctx.products.map((p) => p.category))];
  const sortOptions = [
    ['featured', isZh() ? '推薦排序' : 'Featured'],
    ['price-asc', isZh() ? '價格：低 → 高' : 'Price: Low → High'],
    ['price-desc', isZh() ? '價格：高 → 低' : 'Price: High → Low'],
    ['rating', isZh() ? '評價最高' : 'Top rated'],
  ];
  // Budget bands are stored in USD; labels render in the active currency.
  const bands = [
    { id: 'low', max: 75, label: `< ${money(75)}` },
    { id: 'mid', min: 75, max: 150, label: `${money(75)}–${money(150)}` },
    { id: 'high', min: 150, label: `> ${money(150)}` },
  ];

  root.innerHTML = `
    <section class="container">
      <h1 class="section-title">${esc(t('nav.shop'))}</h1>
      <p class="section-sub">${esc(isZh() ? '關鍵字搜尋加上篩選，找不到就描述一下場合，我們幫你配。' : 'Keyword search with filters — or describe an occasion and we will pick for you.')}</p>

      <div class="searchbar">
        <input class="input" id="shop-q" type="search" placeholder="${esc(isZh() ? '搜尋商品，例如「亞麻襯衫」、「滑雪外套」…' : 'Search products, e.g. “linen shirt”, “ski jacket”…')}" value="${esc(ctx.state.shopQuery || '')}" />
        <select class="input" id="shop-sort" style="max-width:210px">
          ${sortOptions.map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join('')}
        </select>
      </div>

      <div class="chips" style="margin:16px 0">
        <button class="chip ${!ctx.state.shopCategory ? 'active' : ''}" data-cat="">${esc(isZh() ? '全部' : 'All')}</button>
        ${categories.map((c) => `<button class="chip ${ctx.state.shopCategory === c ? 'active' : ''}" data-cat="${esc(c)}">${esc(c)}</button>`).join('')}
      </div>

      <div class="chips" style="margin:0 0 20px">
        ${bands.map((b) => `<button class="chip ${ctx.state.shopBudget === b.id ? 'active' : ''}" data-band="${b.id}">${b.label}</button>`).join('')}
      </div>

      <div class="grid" id="shop-grid"></div>
    </section>
  `;

  const grid = root.querySelector('#shop-grid');
  const qInput = root.querySelector('#shop-q');
  const sortSel = root.querySelector('#shop-sort');

  function apply() {
    let list = [...ctx.products];
    const q = (qInput.value || '').trim().toLowerCase();
    const cat = ctx.state.shopCategory;
    const band = bands.find((b) => b.id === ctx.state.shopBudget);

    if (q) {
      list = list.filter((p) => {
        const hay = `${p.name} ${p.name_zh || ''} ${p.brand} ${p.category} ${p.subcategory} ${p.colorName} ${p.material} ${p.tags.join(' ')} ${p.description_zh || ''}`.toLowerCase();
        return hay.includes(q);
      });
      // Record one event per distinct query (not per keystroke).
      if (q.length >= 2 && q !== lastTrackedQuery) {
        lastTrackedQuery = q;
        track('search', qInput.value.trim());
      }
    }
    if (cat) list = list.filter((p) => p.category === cat);
    if (band) {
      if (band.min != null) list = list.filter((p) => p.price >= band.min);
      if (band.max != null) list = list.filter((p) => p.price <= band.max);
    }

    const sort = sortSel.value;
    if (sort === 'price-asc') list.sort((a, b) => a.price - b.price);
    else if (sort === 'price-desc') list.sort((a, b) => b.price - a.price);
    else if (sort === 'rating') list.sort((a, b) => b.rating - a.rating);

    grid.innerHTML = list.length
      ? list.map(productCard).join('')
      : emptyState('🔎', isZh() ? '沒有符合的商品' : 'No matches', isZh() ? '換個關鍵字或清除篩選條件。' : 'Try a different keyword or clear the filters.');
    grid.querySelectorAll('.product-card').forEach((el) =>
      el.addEventListener('click', () => ctx.navigate(`/product/${el.dataset.id}`)));
  }

  let timer;
  let lastTrackedQuery = '';
  qInput.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(apply, 180); });
  sortSel.addEventListener('change', apply);
  root.querySelectorAll('[data-cat]').forEach((b) =>
    b.addEventListener('click', () => {
      ctx.state.shopCategory = b.dataset.cat || '';
      root.querySelectorAll('[data-cat]').forEach((x) => x.classList.toggle('active', x === b));
      apply();
    }));
  root.querySelectorAll('[data-band]').forEach((b) =>
    b.addEventListener('click', () => {
      ctx.state.shopBudget = ctx.state.shopBudget === b.dataset.band ? '' : b.dataset.band;
      root.querySelectorAll('[data-band]').forEach((x) => x.classList.toggle('active', x.dataset.band === ctx.state.shopBudget));
      apply();
    }));

  apply();
}
