// js/widget.js — logic for the embeddable panel (runs inside the iframe).
// Talks to the same-origin SmartMall APIs and reports events to analytics with
// the tenant id supplied by embed.js.
const params = new URLSearchParams(location.search);
const ORIGIN = location.origin;
let TENANT = params.get('tenant') || 'smartmall-demo';
let LANG = params.get('lang') === 'en' ? 'en' : 'zh';
let STORE = 'SmartMall';
const SESSION = `w-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;

const $ = (id) => document.getElementById(id);
const zh = () => LANG === 'zh';
const money = (usd) => {
  const rate = zh() ? 7.8 : 1;
  const sym = zh() ? 'HK$' : 'US$';
  const v = usd * rate;
  return `${sym}${v.toLocaleString(zh() ? 'zh-HK' : 'en-US', {
    minimumFractionDigits: v >= 100 ? 0 : 2, maximumFractionDigits: v >= 100 ? 0 : 2,
  })}`;
};
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

let products = [];

// ---------------------------------------------------------------- plumbing --
async function api(path, body) {
  const res = await fetch(ORIGIN + path, body
    ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
    : undefined);
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return res.json();
}

function track(type, label, value, meta) {
  fetch(ORIGIN + '/api/analytics/event', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type, label, value, meta: meta || null, tenant: TENANT, session: SESSION }),
    keepalive: true,
  }).catch(() => {});
}

const productById = (id) => products.find((p) => p.id === id);
const pName = (p) => (zh() ? (p.name_zh || p.name) : (p.name || p.name_zh));

function openProduct(id) {
  track('product_view', id, null, { source: 'widget' });
  window.open(`${ORIGIN}/#/product/${id}`, '_blank', 'noopener');
}

// ---------------------------------------------------------------- chat UI ---
function addMsg(who, text) {
  const log = $('w-log');
  const div = document.createElement('div');
  div.className = `w-msg ${who}`;
  div.innerHTML = `<span class="w-label">${who === 'bot' ? esc(STORE) + (zh() ? ' 購物顧問' : ' advisor') : (zh() ? '你' : 'You')}</span>${esc(text)}`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

function addTyping() {
  const log = $('w-log');
  const div = document.createElement('div');
  div.className = 'w-msg bot';
  div.innerHTML = `<span class="w-label">${esc(STORE)}${zh() ? ' 購物顧問' : ' advisor'}</span><span class="w-typing"><span></span><span></span><span></span></span>`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

function addProducts(host, items) {
  const wrap = document.createElement('div');
  wrap.className = 'w-cards';
  wrap.innerHTML = items.map((it) => {
    const p = it.product || it;
    const media = p.image
      ? `<img src="${esc(p.image)}" alt="${esc(pName(p))}" loading="lazy" />`
      : `<span class="ph">${p.emoji || '🛍️'}</span>`;
    return `<button class="w-card" data-pid="${esc(p.id)}">
      ${media}
      <span>
        <span class="nm">${esc(pName(p))}</span><br />
        <span class="pr">${money(p.price)}${it.owned ? ` · <span style="color:var(--w-good)">${zh() ? '已有' : 'owned'}</span>` : ''}</span>
      </span>
    </button>`;
  }).join('');
  wrap.querySelectorAll('[data-pid]').forEach((el) =>
    el.addEventListener('click', () => openProduct(el.dataset.pid)));
  host.appendChild(wrap);
  return wrap;
}

async function ask(q) {
  const log = $('w-log');
  addMsg('user', q);
  const typing = addTyping();
  try {
    const res = await api('/api/assistant', { query: q, lang: LANG });
    typing.remove();
    const msg = addMsg('bot', res.answer);
    const bundle = (res.bundles || [])[0];
    if (bundle?.items?.length) {
      const items = bundle.items.slice(0, 4);
      addProducts(msg, items);
      const line = document.createElement('div');
      line.className = 'w-msg bot';
      line.style.background = 'transparent';
      line.style.padding = '2px 0 0';
      line.innerHTML = `<span style="font-size:0.74rem;color:var(--w-ink-2)">${esc(bundle.title)} · ${money(bundle.total)}</span>`;
      log.appendChild(line);
    }
    log.scrollTop = log.scrollHeight;
    track('search', 'assistant', (res.bundles || []).length, { source: 'widget', query: q });
  } catch {
    typing.remove();
    addMsg('bot', zh() ? '暫時連不上服務，請再試一次。' : 'The service is unavailable — please try again.');
  }
}

// -------------------------------------------------------------- visual UI --
function toHex(v) { return Math.round(v).toString(16).padStart(2, '0'); }

function dominantColors(img, n = 3) {
  const size = 40;
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d');
  ctx.drawImage(img, 0, 0, size, size);
  const data = ctx.getImageData(0, 0, size, size).data;
  const buckets = new Map();
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] < 128) continue;
    const key = ((data[i] >> 5) << 6) | ((data[i + 1] >> 5) << 3) | (data[i + 2] >> 5);
    const b = buckets.get(key) || { n: 0, r: 0, g: 0, b: 0 };
    b.n++; b.r += data[i]; b.g += data[i + 1]; b.b += data[i + 2];
    buckets.set(key, b);
  }
  return [...buckets.values()].sort((a, b) => b.n - a.n).slice(0, n)
    .map((x) => ({ hex: `#${toHex(x.r / x.n)}${toHex(x.g / x.n)}${toHex(x.b / x.n)}` }));
}

function downscale(img, maxSide = 512) {
  const s = Math.min(1, maxSide / Math.max(img.width, img.height));
  const c = document.createElement('canvas');
  c.width = Math.max(1, Math.round(img.width * s));
  c.height = Math.max(1, Math.round(img.height * s));
  c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL('image/jpeg', 0.85);
}

async function visualSearch(file) {
  const grid = $('w-grid');
  const reader = new FileReader();
  reader.onload = (e) => {
    const img = new Image();
    img.onload = async () => {
      $('w-preview').innerHTML = `<img src="${e.target.result}" alt="preview" />`;
      grid.innerHTML = `<div class="w-empty">${zh() ? '搜尋中…' : 'Searching…'}</div>`;
      try {
        const res = await api('/api/visual-search', {
          colors: dominantColors(img), query: '', image: downscale(img), limit: 6,
        });
        const hits = (res.results || []).slice(0, 6)
          .map((r) => ({ ...productById(r.id), _pct: r.matchPercent }))
          .filter((p) => p && p.id);
        grid.innerHTML = hits.map((p) => `
          <div class="w-tile" data-pid="${esc(p.id)}">
            <span class="pct">${p._pct}%</span>
            <div class="thumb" style="background:linear-gradient(135deg,#f4f5fa,#eceef7)">
              ${p.image ? `<img src="${esc(p.image)}" alt="${esc(pName(p))}" loading="lazy" />` : p.emoji}
            </div>
            <div class="meta"><div class="nm">${esc(pName(p))}</div><div class="pr">${money(p.price)}</div></div>
          </div>`).join('') || `<div class="w-empty">${zh() ? '沒有找到相似商品' : 'No matches'}</div>`;
        grid.querySelectorAll('[data-pid]').forEach((el) =>
          el.addEventListener('click', () => openProduct(el.dataset.pid)));
        track('search', 'visual', hits.length, { source: 'widget' });
      } catch {
        grid.innerHTML = `<div class="w-empty">${zh() ? '搜尋失敗' : 'Search failed'}</div>`;
      }
    };
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
}

// ------------------------------------------------------------------- init ---
function setStore(name) {
  STORE = name || STORE;
  $('w-store').textContent = STORE;
  $('w-sub').textContent = zh() ? '購物顧問' : 'Shopping advisor';
}

function welcome() {
  const log = $('w-log');
  if (log.childElementCount) return;
  addMsg('bot', zh()
    ? `你好！我是 ${STORE} 的購物顧問。告訴我場合或需求，我幫你配好整套。`
    : `Hi! I'm ${STORE}'s shopping advisor. Tell me an occasion and I'll build the look.`);

  const sugg = $('w-sugg');
  const list = zh()
    ? ['海島婚禮穿什麼？', '滑雪裝備', '商務面試造型']
    : ['Island wedding outfit', 'Ski gear', 'Business interview look'];
  sugg.innerHTML = list.map((s) => `<button class="w-chip">${esc(s)}</button>`).join('');
  sugg.querySelectorAll('.w-chip').forEach((b) =>
    b.addEventListener('click', () => ask(b.textContent)));
}

async function boot() {
  try {
    products = await api('/api/products');
  } catch { products = []; }

  const q = params.get('q');
  welcome();
  if (q) ask(q);

  // Tabs
  document.querySelectorAll('.w-tab').forEach((tab) =>
    tab.addEventListener('click', () => {
      document.querySelectorAll('.w-tab').forEach((t) => t.classList.remove('active'));
      document.querySelectorAll('.w-pane').forEach((p) => p.classList.remove('active'));
      tab.classList.add('active');
      $('w-pane-' + tab.dataset.tab).classList.add('active');
    }));

  // Chat form
  $('w-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const input = $('w-q');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    ask(text);
  });

  // Visual search
  const drop = $('w-drop');
  const file = $('w-file');
  drop.addEventListener('click', () => file.click());
  file.addEventListener('change', () => { if (file.files.length) visualSearch(file.files[0]); });
  drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.style.borderColor = 'var(--w-brand)'; });
  drop.addEventListener('dragleave', () => { drop.style.borderColor = ''; });
  drop.addEventListener('drop', (e) => {
    e.preventDefault();
    drop.style.borderColor = '';
    if (e.dataTransfer.files.length) visualSearch(e.dataTransfer.files[0]);
  });

  // Close
  const embedded = window.parent && window.parent !== window;
  if (!embedded) $('w-close').style.display = 'none';
  $('w-close').addEventListener('click', () => {
    if (embedded) window.parent.postMessage({ type: 'smartmall:close' }, '*');
  });

  // Handshake with the host page.
  if (embedded) window.parent.postMessage({ type: 'smartmall:ready' }, '*');
}

window.addEventListener('message', (e) => {
  const d = e.data || {};
  if (d.type !== 'smartmall:init') return;
  if (d.tenant) TENANT = d.tenant;
  if (d.lang) LANG = d.lang === 'en' ? 'en' : 'zh';
  setStore(d.storeName);
  if (d.query) ask(d.query);
});

boot();
