// js/app.js — SPA router + bootstrap (bilingual).
import { getJSON } from './api.js';
import { toast } from './ui.js';
import { updateBadge } from './cart.js';
import { t, getLang, setLang, onLangChange } from './i18n.js';

import { render as home } from './views/home.js';
import { render as shop } from './views/shop.js';
import { render as product } from './views/product.js';
import { render as blindbox } from './views/blindbox.js';
import { render as assistant } from './views/assistant.js';
import { render as visual } from './views/visual.js';
import { render as forecast } from './views/forecast.js';
import { render as tryon } from './views/tryon.js';
import { render as priceagent } from './views/priceagent.js';
import { render as resale } from './views/resale.js';
import { render as memory } from './views/memory.js';
import { render as support } from './views/support.js';
import { render as dashboard } from './views/dashboard.js';
import { render as stores } from './views/stores.js';
import { render as cart } from './views/cart.js';
import { initExitIntent } from './exitIntent.js';

const app = document.getElementById('app');
const state = {
  shopCategory: '', shopQuery: '', shopBudget: '',
  tryonProduct: null, lastPoll: null,
  blindboxResult: null, resaleProduct: null, supportProduct: null,
  dashDays: 7,
};

const ctx = {
  products: [],
  state,
  navigate: (path) => { location.hash = path; },
  toast,
  lang: () => getLang(),
};

function parseRoute() {
  const hash = location.hash.replace(/^#/, '') || '/';
  const parts = hash.split('/').filter(Boolean);
  return { path: parts[0] || '', param: parts[1] || null };
}

function setActiveNav(route) {
  const map = {
    '': '', shop: 'shop', assistant: 'assistant', visual: 'visual', forecast: 'forecast',
    tryon: 'tryon', cart: 'cart', product: 'shop', blindbox: 'blindbox',
    priceagent: 'priceagent', resale: 'resale', memory: 'memory', support: 'support',
    dashboard: 'dashboard', stores: 'stores',
  };
  const active = map[route] ?? '';
  document.querySelectorAll('.main-nav a[data-nav]').forEach((a) => {
    a.classList.toggle('active', a.dataset.route === active);
  });
}

// Translate the static shell nodes ([data-i18n]).
function applyStaticI18n() {
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  const toggle = document.getElementById('lang-toggle');
  if (toggle) toggle.textContent = getLang() === 'zh' ? 'EN' : '繁中';
  const search = document.getElementById('topsearch-input');
  if (search) {
    search.placeholder = getLang() === 'zh'
      ? '搜尋商品、品牌或場合…'
      : 'Search products, brands or occasions…';
  }
  document.documentElement.lang = getLang() === 'zh' ? 'zh-Hant' : 'en';
}

async function render() {
  const { path, param } = parseRoute();
  setActiveNav(path);
  applyStaticI18n();
  window.scrollTo({ top: 0 });

  switch (path) {
    case '': home(app, ctx); break;
    case 'shop': shop(app, ctx); break;
    case 'product': await product(app, ctx, param); break;
    case 'blindbox': blindbox(app, ctx); break;
    case 'assistant': assistant(app, ctx); break;
    case 'visual': visual(app, ctx); break;
    case 'forecast': await forecast(app, ctx); break;
    case 'tryon': tryon(app, ctx); break;
    case 'priceagent': priceagent(app, ctx); break;
    case 'resale': resale(app, ctx); break;
    case 'memory': memory(app, ctx); break;
    case 'support': support(app, ctx); break;
    case 'dashboard': await dashboard(app, ctx); break;
    case 'stores': await stores(app, ctx); break;
    case 'cart': cart(app, ctx); break;
    default:
      app.innerHTML = `<div class="container"><div class="empty"><div class="e">404</div><h3>Page not found</h3></div></div>`;
  }
}

// Header search: submits into the shop view; the camera icon opens image search.
function wireHeaderSearch() {
  const form = document.getElementById('topsearch');
  const input = document.getElementById('topsearch-input');
  const cam = document.getElementById('topsearch-cam');
  if (!form || !input) return;

  const go = () => {
    ctx.state.shopQuery = input.value.trim();
    ctx.state.shopCategory = '';
    if (location.hash === '#/shop') render();
    else ctx.navigate('/shop');
  };

  form.addEventListener('submit', (e) => { e.preventDefault(); go(); });
  if (cam) cam.addEventListener('click', () => ctx.navigate('/visual'));
}

async function boot() {
  try {
    ctx.products = await getJSON('/api/products');
  } catch {
    toast('Could not load catalog — is the server running?');
  }
  updateBadge();
  applyStaticI18n();
  wireHeaderSearch();
  render();
  window.addEventListener('hashchange', render);

  document.getElementById('lang-toggle').addEventListener('click', () => {
    setLang(getLang() === 'zh' ? 'en' : 'zh');
  });
  onLangChange(() => render());

  const toggle = document.getElementById('nav-toggle');
  const nav = document.querySelector('.main-nav');
  toggle.addEventListener('click', () => nav.classList.toggle('open'));
  document.querySelectorAll('.main-nav a').forEach((a) =>
    a.addEventListener('click', () => nav.classList.remove('open')));

  // Exit-intent coupon offer (records analytics for the merchant dashboard).
  initExitIntent(ctx);
}

boot();
