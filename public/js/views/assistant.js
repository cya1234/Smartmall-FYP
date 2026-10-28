// js/views/assistant.js — contextual shopping assistant chat (memory-aware).
import { postJSON } from '../api.js';
import { esc, fmtPrice, hexA, pName, t, isZh, mediaInner } from '../ui.js';
import { addToCart } from '../cart.js';
import { track } from '../exitIntent.js';

const SUGGESTIONS_ZH = [
  '我下個月要去海島婚禮，穿什麼好？',
  '預算 2000 元，去北海道滑雪要買什麼？',
  'Cozy winter layering for cold weather',
  'A gym-ready set with wireless earbuds and a fitness watch',
];
const SUGGESTIONS_EN = [
  'Island wedding next month — what should I wear?',
  'Budget 2000, what do I need for a Hokkaido ski trip?',
  'Cozy winter layering for cold weather',
  'A gym-ready set with wireless earbuds and a fitness watch',
];

export function render(root, ctx) {
  const suggestions = isZh() ? SUGGESTIONS_ZH : SUGGESTIONS_EN;

  root.innerHTML = `
    <section class="container" style="max-width:940px">
      <h1 class="section-title">🤖 ${esc(t('feat.assistant.t'))}</h1>
      <p class="section-sub">${esc(t('feat.assistant.d'))}</p>
      <div class="card chat-wrap">
        <div class="chat-log" id="chat-log"></div>
        <div class="suggestion-row" id="suggestions">
          ${suggestions.map((s) => `<button class="suggestion" data-s="${esc(s)}">${esc(s)}</button>`).join('')}
        </div>
        <form class="chat-input-row" id="chat-form">
          <input class="input" id="chat-input" placeholder="${esc(isZh() ? '例如：我下個月要去海島婚禮，穿什麼好？' : 'e.g. Island wedding next month — what should I wear?')}" autocomplete="off" />
          <button class="btn btn-primary" type="submit">${esc(t('common.search'))}</button>
        </form>
      </div>
    </section>
  `;

  const log = root.querySelector('#chat-log');
  const form = root.querySelector('#chat-form');
  const input = root.querySelector('#chat-input');

  const welcome = isZh()
    ? '你好，我是 SmartMall 的購物助手 👋\n我不只理解情境，還記得你買過什麼、你的尺碼與風格。試著描述一個場合，例如「我下個月要去海島婚禮，穿什麼好？」，我會以你衣櫥裡已有的單品為基礎來搭配。'
    : "Hi, I'm your SmartMall assistant 👋\nI understand scenarios and I remember what you own, your size and your style. Try describing an occasion — I'll build the look around pieces already in your wardrobe.";
  appendMsg(log, 'ai', welcome);

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    input.value = '';
    appendMsg(log, 'user', q);
    const typing = appendTyping(log);
    try {
      const res = await postJSON('/api/assistant', { query: q, lang: isZh() ? 'zh' : 'en' });
      try { track('search', 'assistant', res.bundles?.length ?? 0); } catch { /* best-effort */ }
      typing.remove();
      appendMsg(log, 'ai', res.answer);
      renderMemoryStrip(log, res);
      renderBundles(log, res.bundles, ctx);
    } catch {
      typing.remove();
      appendMsg(log, 'ai', t('common.retry'));
    }
  });

  root.querySelectorAll('[data-s]').forEach((b) =>
    b.addEventListener('click', () => {
      input.value = b.dataset.s;
      form.dispatchEvent(new Event('submit'));
    }));
}

function appendMsg(log, who, text) {
  const div = document.createElement('div');
  div.className = `msg ${who}`;
  div.innerHTML = `<span class="label">${who === 'ai' ? (isZh() ? '搭配顧問' : 'Style advisor') : (isZh() ? '你' : 'You')}</span>${esc(text)}`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

function appendTyping(log) {
  const div = document.createElement('div');
  div.className = 'msg ai';
  div.innerHTML = `<span class="label">${isZh() ? '搭配顧問' : 'Style advisor'}</span><span class="typing"><span></span><span></span><span></span></span>`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

// Show what long-term memory contributed (and any proactive sizing advice).
function renderMemoryStrip(log, res) {
  const bits = [];
  if (res.memoryUsed && res.memoryUsed.length) {
    bits.push(`<div style="font-weight:800;margin-bottom:6px">🧠 ${esc(t('as.memoryUsed'))}</div>` +
      res.memoryUsed.map((m) => `
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
          <span>${m.emoji}</span>
          <span>${esc(isZh() ? m.name_zh || m.name : m.name)}</span>
          <span class="badge badge-owned">${esc(isZh() ? m.boughtLabel : m.boughtLabel_en)}</span>
        </div>`).join(''));
  }
  if (res.sizeAdvice) {
    bits.push(`<div style="margin-top:10px">📏 <b>${esc(t('as.sizeAdvice'))}</b>：${esc(res.sizeAdvice)}</div>`);
  }
  if (!bits.length) return;
  const div = document.createElement('div');
  div.className = 'msg ai';
  div.style.maxWidth = '96%';
  div.innerHTML = `<span class="label">${esc(t('as.memoryUsed'))}</span>${bits.join('')}`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function renderBundles(log, bundles, ctx) {
  if (!bundles || !bundles.length) return;
  const wrap = document.createElement('div');
  wrap.className = 'msg ai';
  wrap.style.maxWidth = '96%';
  wrap.innerHTML = `<span class="label">${esc(isZh() ? '為你整理的搭配' : 'Curated bundles')}</span>` + bundles.map(bundleHTML).join('');
  log.appendChild(wrap);
  log.scrollTop = log.scrollHeight;

  wrap.querySelectorAll('.bundle-item').forEach((el) =>
    el.addEventListener('click', () => ctx.navigate(`/product/${el.dataset.id}`)));
  wrap.querySelectorAll('[data-add-all]').forEach((btn) =>
    btn.addEventListener('click', () => {
      const ids = btn.dataset.addAll.split(',').filter(Boolean);
      ids.forEach((id) => addToCart(id, 1));
      ctx.toast(`${ids.length} ${t('common.items')} → ${t('nav.cart')}`);
    }));
}

function bundleHTML(bundle) {
  const toBuy = bundle.items.filter((i) => !i.owned);
  return `<div class="bundle" style="margin-top:14px;${bundle.fromWardrobe ? 'border-color:var(--brand)' : ''}">
    <div class="bundle-head">
      <span class="t">${esc(bundle.title)}</span>
      <span class="badge ${bundle.ownedCount ? 'badge-owned' : 'badge-info'}">
        ${bundle.items.length} ${esc(t('common.items'))}${bundle.ownedCount ? ` · ${bundle.ownedCount} ${esc(t('common.owned'))}` : ''}
      </span>
    </div>
    <div class="bundle-items">
      ${bundle.items.map((it) => `
        <div class="bundle-item" data-id="${esc(it.product.id)}" title="${esc(it.note || '')}">
          <div class="thumb" style="background:linear-gradient(135deg, ${hexA(it.product.color, 0.14)}, ${hexA(it.product.color, 0.3)});position:relative">
            ${mediaInner(it.product, '2.4rem')}
            ${it.owned ? `<span class="owned-flag" style="top:6px;right:6px;font-size:0.6rem">${esc(t('common.owned'))}</span>` : ''}
          </div>
          <div class="nm">${esc(pName(it.product))}</div>
          <div class="pr">${it.owned
            ? `<span class="owned-strike">${fmtPrice(it.product.price)}</span>`
            : fmtPrice(it.product.price)}</div>
        </div>`).join('')}
    </div>
    <div class="bundle-foot">
      <span class="muted small">
        ${bundle.ownedValue > 0
          ? `${esc(t('as.ownedSave'))} ${fmtPrice(bundle.ownedValue)} · `
          : ''}${esc(t('bb.newTotal'))}
      </span>
      <span><strong>${fmtPrice(bundle.total)}</strong>
      ${toBuy.length ? `<button class="btn btn-sm btn-primary" style="margin-left:10px" data-add-all="${toBuy.map((i) => i.product.id).join(',')}">${esc(t('common.addAll'))}</button>` : ''}</span>
    </div>
  </div>`;
}
