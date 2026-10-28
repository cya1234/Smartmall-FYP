// js/exitIntent.js — exit-intent detection + coupon offer.
//
// Desktop: fires when the pointer leaves the viewport through the top edge,
// which is the strongest signal a visitor is about to leave.
// Touch devices (iPad): there is no pointer, so we use an idle timer on the
// product / cart views instead, plus the browser back gesture where possible.
//
// Every step is recorded as an analytics event so the merchant dashboard can
// report a real "AI 挽留成功率" instead of a made-up number.
import { postJSON, getJSON } from './api.js';
import { esc, t, isZh, toast } from './ui.js';

const SESSION_KEY = 'smartmall-session';
const SHOWN_KEY = 'smartmall-exit-shown';
const COUPON_KEY = 'smartmall-coupon';
const IDLE_MS = 25000;

export function sessionId() {
  let s = null;
  try { s = localStorage.getItem(SESSION_KEY); } catch { /* private mode */ }
  if (!s) {
    s = `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    try { localStorage.setItem(SESSION_KEY, s); } catch { /* ignore */ }
  }
  return s;
}

export function track(type, label = null, value = null, meta = null) {
  postJSON('/api/analytics/event', { type, label, value, meta, session: sessionId() }).catch(() => {});
}

export function getClaimedCoupon() {
  try {
    const raw = localStorage.getItem(COUPON_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function saveCoupon(c) {
  try { localStorage.setItem(COUPON_KEY, JSON.stringify(c)); } catch { /* ignore */ }
}

function alreadyShown() {
  try { return sessionStorage.getItem(SHOWN_KEY) === '1'; } catch { return false; }
}

function markShown() {
  try { sessionStorage.setItem(SHOWN_KEY, '1'); } catch { /* ignore */ }
}

const onRelevantPage = () =>
  location.hash.startsWith('#/product/') || location.hash === '#/cart';

const isTouch = () =>
  window.matchMedia && window.matchMedia('(pointer: coarse)').matches;

// ---------------------------------------------------------------- modal ----
function buildModal({ discountPct, onClaim, onDismiss }) {
  const wrap = document.createElement('div');
  wrap.className = 'exit-modal';
  wrap.innerHTML = `
    <div class="exit-backdrop"></div>
    <div class="exit-card" role="dialog" aria-modal="true" aria-labelledby="exit-title">
      <button class="exit-close" aria-label="${esc(t('common.close'))}">✕</button>
      <div class="exit-emoji">🎁</div>
      <h3 id="exit-title">${esc(isZh() ? '等等，先別走！' : 'Wait — before you go!')}</h3>
      <p>${esc(isZh()
        ? `留下來，這張 ${discountPct}% 折扣券直接送給你。`
        : `Here is a ${discountPct}% off coupon, on the house.`)}</p>
      <div class="exit-actions">
        <button class="btn btn-accent" data-claim>${esc(isZh() ? `領取 ${discountPct}% 優惠券` : `Claim ${discountPct}% off`)}</button>
        <button class="btn btn-ghost" data-dismiss>${esc(isZh() ? '不用了，謝謝' : 'No thanks')}</button>
      </div>
      <div class="exit-code-row hidden" data-codewrap>
        <span class="exit-code" data-code></span>
        <button class="btn btn-ghost btn-sm" data-copy>${esc(isZh() ? '複製' : 'Copy')}</button>
      </div>
      <p class="exit-note">${esc(isZh() ? '結帳時自動套用 · 24 小時內有效' : 'Applied automatically at checkout · valid 24h')}</p>
    </div>`;
  document.body.appendChild(wrap);
  requestAnimationFrame(() => wrap.classList.add('show'));

  const close = () => {
    wrap.classList.remove('show');
    setTimeout(() => wrap.remove(), 220);
  };

  wrap.querySelector('.exit-backdrop').addEventListener('click', () => { onDismiss(); close(); });
  wrap.querySelector('.exit-close').addEventListener('click', () => { onDismiss(); close(); });
  wrap.querySelector('[data-dismiss]').addEventListener('click', () => { onDismiss(); close(); });

  wrap.querySelector('[data-claim]').addEventListener('click', async (e) => {
    e.currentTarget.disabled = true;
    try {
      const res = await postJSON('/api/analytics/coupon', {
        discountPct, source: 'exit-intent', session: sessionId(),
      });
      saveCoupon({ code: res.code, discountPct: res.discountPct, claimedAt: new Date().toISOString() });
      const codeEl = wrap.querySelector('[data-code]');
      codeEl.textContent = res.code;
      wrap.querySelector('[data-codewrap]').classList.remove('hidden');
      wrap.querySelector('[data-claim]').textContent = isZh() ? '已領取 ✓' : 'Claimed ✓';
      wrap.querySelector('[data-claim]').classList.remove('btn-accent');
      wrap.querySelector('[data-claim]').classList.add('btn-ghost');
      toast(isZh() ? '優惠券已套用，回購物車結帳即享折扣' : 'Coupon applied — use it at checkout');
    } catch {
      toast(t('common.retry'));
      e.currentTarget.disabled = false;
    }
  });

  wrap.querySelector('[data-copy]').addEventListener('click', () => {
    const code = wrap.querySelector('[data-code]').textContent;
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(code).then(() => toast(isZh() ? '已複製' : 'Copied'));
    } else {
      toast(code);
    }
  });

  return { close };
}

// -------------------------------------------------------------- trigger ----
export function initExitIntent(ctx) {
  let idleTimer = null;

  function fire(reason) {
    if (alreadyShown() || getClaimedCoupon() || !onRelevantPage()) return;
    markShown();
    track('exit_intent_shown', reason, 10);

    buildModal({
      discountPct: 10,
      onClaim: () => {},
      onDismiss: () => track('exit_intent_dismissed', reason),
    });
  }

  // Desktop: pointer escapes through the top of the viewport.
  document.addEventListener('mouseout', (e) => {
    if (e.relatedTarget || e.clientY > 8) return;
    fire('mouse-out');
  });

  // Touch (iPad): idle on a product/cart page.
  function armIdle() {
    clearTimeout(idleTimer);
    if (!isTouch() || !onRelevantPage() || alreadyShown() || getClaimedCoupon()) return;
    idleTimer = setTimeout(() => fire('idle-touch'), IDLE_MS);
  }

  ['click', 'touchstart', 'scroll', 'keydown'].forEach((evt) =>
    window.addEventListener(evt, () => { if (isTouch()) armIdle(); }, { passive: true }));

  window.addEventListener('hashchange', () => {
    armIdle();
  });

  armIdle();
  return { fire, armIdle };
}

// Re-validate a stored coupon against the server (e.g. after a server restart).
export async function refreshCoupon() {
  const c = getClaimedCoupon();
  if (!c || !c.code) return null;
  try {
    const res = await getJSON(`/api/analytics/coupon/${encodeURIComponent(c.code)}`);
    if (!res.valid) {
      try { localStorage.removeItem(COUPON_KEY); } catch { /* ignore */ }
      return null;
    }
    return { ...c, ...res.coupon };
  } catch {
    return c;
  }
}
