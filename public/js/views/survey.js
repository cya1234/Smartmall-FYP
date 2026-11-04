// js/views/survey.js — preference survey that pays for information.
//
// The shopper answers a few pairwise questions ("which would you wear?") and earns
// a fixed HK$1-10 coupon. The amount scales with how much the answers actually
// taught the recommendation model: pairs it was unsure about are worth more.
import { postJSON } from '../api.js';
import { esc, t, isZh, toast } from '../ui.js';
import { sessionId, rememberCoupon } from '../exitIntent.js';

const QUESTIONS = 3;

const money = (hkd) => (isZh()
  ? `HK$${hkd}`
  : `US$${(hkd / 7.8).toFixed(2)}`);

function itemCard(item, side) {
  return `<button class="survey-pick" data-side="${side}"
      style="padding:0;border:1px solid var(--line);border-radius:16px;overflow:hidden;
             background:var(--surface);cursor:pointer;text-align:left;display:flex;flex-direction:column">
    <span style="display:flex;align-items:center;justify-content:center;height:230px;background:var(--surface-2)">
      ${item.image
        ? `<img src="${esc(item.image)}" alt="" style="width:100%;height:100%;object-fit:contain" />`
        : `<span style="font-size:3rem">${item.emoji || '🛍️'}</span>`}
    </span>
    <span style="padding:12px 14px 14px">
      <strong style="font-size:0.95rem">${esc(isZh() ? (item.name_zh || item.name) : item.name)}</strong>
      <span class="muted small" style="display:block;margin-top:4px">
        ${esc(item.colorName || '')}${item.material ? ' · ' + esc(item.material) : ''}
      </span>
    </span>
  </button>`;
}

export async function render(root, ctx) {
  const state = { phase: 'loading', data: null, index: 0, answers: 0, result: null, error: null };

  const pairsStyle = 'display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-top:20px';
  const vsStyle = 'text-align:center;color:var(--muted);font-size:0.8rem;align-self:center';

  function paint() {
    const d = state.data;

    if (state.phase === 'loading') {
      root.innerHTML = `<section class="container" style="max-width:760px">
        <div class="card">${esc(t('common.loading'))}</div></section>`;
      return;
    }

    if (state.phase === 'error') {
      root.innerHTML = `<section class="container" style="max-width:760px">
        <div class="card">${esc(t('survey.error'))}
          <div style="margin-top:12px"><button class="btn btn-primary" data-retry>${esc(t('common.retry'))}</button></div>
        </div></section>`;
      root.querySelector('[data-retry]').addEventListener('click', start);
      return;
    }

    if (state.phase === 'done') {
      const r = state.result;
      const learned = r.learned || {};
      root.innerHTML = `<section class="container" style="max-width:760px">
        <div class="card" style="text-align:center;padding:34px 24px">
          <div style="font-size:3rem">🎉</div>
          <h1 class="section-title" style="margin:10px 0 6px">${esc(t('survey.rewardTitle'))}</h1>
          <p class="muted" style="margin:0 0 18px">${esc(t('survey.rewardSub'))}</p>
          <div style="display:inline-flex;align-items:center;gap:12px;padding:12px 20px;
                      border:1px dashed var(--brand);border-radius:14px;background:var(--brand-soft)">
            <strong style="font-family:ui-monospace,Consolas,monospace;font-size:1.15rem;color:var(--brand)">
              ${esc(r.coupon.code)}
            </strong>
            <span class="badge badge-good">${esc(money(r.coupon.amountHkd))}</span>
          </div>
          <p class="muted small" style="margin:16px 0 0">${esc(t('survey.rewardApplied'))}</p>
          <div style="margin-top:20px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap">
            <button class="btn btn-primary" data-shop>${esc(t('survey.goShop'))}</button>
            <button class="btn btn-ghost" data-again>${esc(t('survey.again'))}</button>
          </div>
          ${(learned.topCategories || []).length ? `
            <div style="margin-top:26px;text-align:left;border-top:1px solid var(--line);padding-top:18px">
              <strong style="font-size:0.95rem">${esc(t('survey.learnedTitle'))}</strong>
              <p class="muted small" style="margin:6px 0 10px">${esc(t('survey.learnedSub'))}</p>
              <div class="chips">
                ${learned.topCategories.map((c) => `<span class="chip active">${esc(c)}</span>`).join('')}
                ${(learned.topColours || []).map((c) => `<span class="chip">${esc(c)}</span>`).join('')}
              </div>
              <p class="muted small" style="margin:12px 0 0">
                ${esc(t('survey.comparisons'))}: ${learned.comparisons || 0}
              </p>
            </div>` : ''}
        </div>
      </section>`;

      root.querySelector('[data-shop]').addEventListener('click', () => ctx.navigate('/shop'));
      root.querySelector('[data-again]').addEventListener('click', start);
      return;
    }

    // ---- question ----
    const q = d.questions[state.index];
    const step = state.index + 1;
    root.innerHTML = `<section class="container" style="max-width:760px">
      <h1 class="section-title">${esc(t('survey.title'))}</h1>
      <p class="section-sub">${esc(t('survey.sub'))}</p>

      <div class="row-between" style="margin-bottom:6px">
        <span class="badge badge-info">${esc(t('survey.progress'))} ${step} / ${d.total}</span>
        <span class="muted small">${esc(t('survey.earn'))} ${esc(money(10))}</span>
      </div>
      <div class="confidence-bar" style="margin-bottom:4px">
        <div class="confidence-fill" style="width:${Math.round((step - 1) / d.total * 100)}%"></div>
      </div>

      <div class="card" style="margin-top:18px">
        <h3 style="margin:0 0 2px;text-align:center">${esc(t('survey.question'))}</h3>
        <p class="muted small" style="margin:0;text-align:center">${esc(t('survey.questionSub'))}</p>
        <div style="${pairsStyle}">
          ${itemCard(q.left, 'left')}
          <div style="${vsStyle}">${esc(t('survey.or'))}</div>
          ${itemCard(q.right, 'right')}
        </div>
        <div style="text-align:center;margin-top:16px">
          <button class="btn btn-ghost btn-sm" data-skip>${esc(t('survey.skip'))}</button>
        </div>
      </div>
    </section>`;

    root.querySelectorAll('[data-side]').forEach((b) =>
      b.addEventListener('click', () => pick(b.dataset.side)));
    root.querySelector('[data-skip]')
      .addEventListener('click', () => ctx.navigate('/shop'));
  }

  async function pick(side) {
    const q = state.data.questions[state.index];
    try {
      await postJSON('/api/survey/answer', {
        sessionId: state.data.sessionId,
        questionId: q.id,
        choice: side,
        session: sessionId(),
      });
    } catch {
      // A failed answer should not block the flow; move on regardless.
    }
    state.answers += 1;
    state.index += 1;

    if (state.index >= state.data.total) {
      await settle();
    } else {
      paint();
    }
  }

  async function settle() {
    state.phase = 'loading';
    paint();
    try {
      const r = await postJSON('/api/survey/finish', {
        sessionId: state.data.sessionId,
        session: sessionId(),
      });
      if (!r.ok) throw new Error(r.error || 'finish failed');
      rememberCoupon({
        code: r.coupon.code,
        kind: 'amount',
        amountHkd: r.coupon.amountHkd,
        claimedAt: new Date().toISOString(),
      });
      state.result = r;
      state.phase = 'done';
    } catch {
      state.phase = 'error';
      toast(t('survey.error'));
    }
    paint();
  }

  async function start() {
    state.phase = 'loading';
    state.index = 0;
    state.answers = 0;
    state.result = null;
    paint();
    try {
      const d = await postJSON('/api/survey/start', {
        lang: isZh() ? 'zh' : 'en',
        n: QUESTIONS,
        session: sessionId(),
      });
      if (!d.questions || !d.questions.length) throw new Error('no questions');
      state.data = d;
      state.phase = 'question';
    } catch {
      state.phase = 'error';
    }
    paint();
  }

  await start();
}
