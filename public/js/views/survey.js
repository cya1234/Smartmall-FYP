// js/views/survey.js — preference survey + prize wheel.
//
// Flow: three pairwise questions -> the server quotes what the answers were worth
// -> a wheel decides the actual prize. The outcome is chosen on the server; the
// client only animates to the index it is told, so the draw cannot be cheated from
// the browser. The odds are shown to the shopper, because a reward that pretends
// to be random but is not would be a dark pattern.
import { postJSON } from '../api.js';
import { esc, t, isZh, toast } from '../ui.js';
import { sessionId, rememberCoupon } from '../exitIntent.js';

const QUESTIONS = 3;
const SEG_COLOURS = ['#8B7BFF', '#5AC8FA', '#3DD68C', '#F5B54A',
  '#FF8A66', '#FF6B6B', '#B18CFF', '#7A8397'];
const CX = 100;
const CY = 100;
const R = 94;

const money = (hkd) => (isZh() ? `HK$${hkd}` : `US$${(hkd / 7.8).toFixed(2)}`);

function polar(r, deg) {
  const rad = ((deg - 90) * Math.PI) / 180;
  return { x: CX + r * Math.cos(rad), y: CY + r * Math.sin(rad) };
}

function sectorPath(a0, a1) {
  const p0 = polar(R, a0);
  const p1 = polar(R, a1);
  const large = a1 - a0 > 180 ? 1 : 0;
  return `M ${CX} ${CY} L ${p0.x.toFixed(2)} ${p0.y.toFixed(2)} `
    + `A ${R} ${R} 0 ${large} 1 ${p1.x.toFixed(2)} ${p1.y.toFixed(2)} Z`;
}

/** Draw the wheel once; labels stay upright so they read at any rotation. */
function wheelSvg(segments) {
  const step = 360 / segments.length;
  const sectors = segments.map((s, i) => {
    const a0 = i * step;
    const a1 = a0 + step;
    const mid = a0 + step / 2;
    const pos = polar(62, mid);
    const label = s.again
      ? (isZh() ? '再轉' : 'AGAIN')
      : money(s.hkd);
    return `<path d="${sectorPath(a0, a1)}" fill="${SEG_COLOURS[i % SEG_COLOURS.length]}"
              stroke="rgba(0,0,0,0.18)" stroke-width="0.8" />
            <text x="${pos.x.toFixed(1)}" y="${(pos.y + 3).toFixed(1)}" text-anchor="middle"
              font-size="${s.again ? 7.5 : 9.5}" font-weight="700" fill="#fff"
              style="letter-spacing:-0.2px">${esc(label)}</text>`;
  }).join('');
  return `<svg viewBox="0 0 200 200" width="100%" height="100%" aria-hidden="true">
    <circle cx="${CX}" cy="${CY}" r="${R + 3}" fill="none" stroke="var(--line)" stroke-width="2" />
    ${sectors}
    <circle cx="${CX}" cy="${CY}" r="13" fill="var(--surface)" stroke="var(--line)" stroke-width="2" />
    <text x="${CX}" y="${CY + 3.5}" text-anchor="middle" font-size="10" font-weight="800"
      fill="var(--ink)">SM</text>
  </svg>`;
}

function itemCard(item, side) {
  return `<button data-side="${side}"
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
  const state = {
    phase: 'loading', data: null, index: 0, finish: null,
    spin: null, angle: 0, busy: false, error: null,
  };

  const pairsStyle = 'display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-top:20px';

  // ---------------------------------------------------------------- paint ---
  function paint() {
    if (state.phase === 'loading') {
      root.innerHTML = `<section class="container" style="max-width:760px">
        <div class="card">${esc(t('common.loading'))}</div></section>`;
      return;
    }

    if (state.phase === 'error') {
      root.innerHTML = `<section class="container" style="max-width:760px">
        <div class="card">${esc(t('survey.error'))}
          <div style="margin-top:12px">
            <button class="btn btn-primary" data-retry>${esc(t('common.retry'))}</button>
          </div>
        </div></section>`;
      root.querySelector('[data-retry]').addEventListener('click', start);
      return;
    }

    if (state.phase === 'wheel') paintWheel();
    else if (state.phase === 'done') paintDone();
    else paintQuestion();
  }

  // ------------------------------------------------------------ the wheel ---
  function paintWheel() {
    const f = state.finish;
    const odds = (f.odds || []).filter((o) => !o.again);
    root.innerHTML = `<section class="container" style="max-width:760px">
      <h1 class="section-title">🎡 ${esc(t('survey.wheelTitle'))}</h1>
      <p class="section-sub">${esc(t('survey.wheelSub'))}</p>

      <div class="card" style="padding:22px 18px">
        <div style="display:flex;justify-content:center;margin-bottom:6px">
          <span class="badge badge-info">${esc(t('survey.quoteLine'))} ${esc(money(f.quoteHkd))}</span>
        </div>

        <div style="position:relative;width:min(300px,72vw);margin:0 auto">
          <div style="position:absolute;left:50%;top:-6px;transform:translateX(-50%);
                      font-size:1.1rem;color:var(--brand);z-index:2;filter:drop-shadow(0 2px 3px rgba(0,0,0,.4))">▼</div>
          <div id="wheel" style="transform:rotate(${state.angle}deg);transition:none;
               aspect-ratio:1;width:100%;filter:drop-shadow(0 12px 30px rgba(0,0,0,.35))">
            ${wheelSvg(f.segments || [])}
          </div>
        </div>

        <div style="text-align:center;margin-top:18px">
          <button class="btn btn-primary" id="spin" style="min-width:190px"
            ${state.busy || state.spinsUsed >= 2 ? 'disabled' : ''}>
            ${state.busy ? esc(t('survey.spinning')) : esc(t('survey.spin'))}
          </button>
        </div>

        <details style="margin-top:16px">
          <summary class="muted small" style="cursor:pointer">${esc(t('survey.odds'))}</summary>
          <div class="muted small" style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px 14px">
            ${odds.map((o) => `<span>${esc(money(o.hkd))} · ${o.pct}%</span>`).join('')}
          </div>
        </details>
      </div>
    </section>`;

    const btn = root.querySelector('#spin');
    if (btn) btn.addEventListener('click', () => doSpin());
  }

  async function doSpin() {
    if (state.busy) return;
    state.busy = true;
    paint();

    let res;
    try {
      res = await postJSON('/api/survey/spin', {
        sessionId: state.data.sessionId, session: sessionId(),
      });
      if (!res.ok) throw new Error(res.error);
    } catch {
      state.busy = false;
      paint();
      toast(t('survey.error'));
      return;
    }

    state.spinsUsed = (state.spinsUsed || 0) + 1;

    // Animate to the server-chosen segment. Adding whole turns makes it feel like a
    // real spin; a small jitter avoids landing dead-centre every time.
    const seg = (res.segments || state.finish.segments || []).length
      ? (state.finish.segments || []).length
      : 8;
    const step = 360 / seg;
    const target = state.angle + 360 * 5 - (res.index * step + step / 2) - (state.angle % 360)
      + (Math.random() * 12 - 6);
    const wheel = root.querySelector('#wheel');
    if (wheel) {
      wheel.style.transition = 'transform 4.1s cubic-bezier(0.15, 0.9, 0.15, 1)';
      wheel.style.transform = `rotate(${target}deg)`;
    }
    state.angle = target;

    setTimeout(() => {
      state.busy = false;
      state.spin = res;
      state.phase = 'done';
      if (res.coupon) {
        rememberCoupon({
          code: res.coupon.code,
          kind: 'amount',
          amountHkd: res.coupon.amountHkd,
          claimedAt: new Date().toISOString(),
        });
      }
      paint();
    }, 4300);
  }

  // ------------------------------------------------------------- the prize --
  function paintDone() {
    const r = state.spin;
    const learned = (state.finish && state.finish.learned) || {};
    const again = r && r.again;

    root.innerHTML = `<section class="container" style="max-width:760px">
      <div class="card" style="text-align:center;padding:34px 24px">
        <div style="font-size:3rem">${again ? '🔁' : '🎉'}</div>
        <h1 class="section-title" style="margin:10px 0 6px">
          ${esc(again ? t('survey.againSeg') : t('survey.rewardTitle'))}
        </h1>
        <p class="muted" style="margin:0 0 16px">
          ${esc(again ? t('survey.againSub') : t('survey.rewardSub'))}
        </p>

        ${again ? `
          <button class="btn btn-primary" data-spin-again>${esc(t('survey.spin'))}</button>
        ` : `
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
        `}
      </div>

      ${(learned.topCategories || []).length ? `
        <div class="card" style="margin-top:16px">
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
    </section>`;

    const shop = root.querySelector('[data-shop]');
    if (shop) shop.addEventListener('click', () => ctx.navigate('/shop'));
    const againBtn = root.querySelector('[data-again]');
    if (againBtn) againBtn.addEventListener('click', start);
    const spinAgain = root.querySelector('[data-spin-again]');
    if (spinAgain) {
      spinAgain.addEventListener('click', () => {
        state.phase = 'wheel';
        paint();
      });
    }
  }

  // ------------------------------------------------------------ questions ---
  function paintQuestion() {
    const d = state.data;
    const q = d.questions[state.index];
    const step = state.index + 1;

    root.innerHTML = `<section class="container" style="max-width:760px">
      <h1 class="section-title">${esc(t('survey.title'))}</h1>
      <p class="section-sub">${esc(t('survey.sub'))}</p>

      <div class="row-between" style="margin-bottom:6px">
        <span class="badge badge-info">${esc(t('survey.progress'))} ${step} / ${d.total}</span>
        <span class="muted small">🎡 ${esc(t('survey.earn'))} ${esc(money(12))}</span>
      </div>
      <div class="confidence-bar" style="margin-bottom:4px">
        <div class="confidence-fill" style="width:${Math.round((step - 1) / d.total * 100)}%"></div>
      </div>

      <div class="card" style="margin-top:18px">
        <h3 style="margin:0 0 2px;text-align:center">${esc(t('survey.question'))}</h3>
        <p class="muted small" style="margin:0;text-align:center">${esc(t('survey.questionSub'))}</p>
        <div style="${pairsStyle}">
          ${itemCard(q.left, 'left')}
          <div style="text-align:center;color:var(--muted);font-size:0.8rem;align-self:center">
            ${esc(t('survey.or'))}
          </div>
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
      // A failed answer must not block the flow; move on regardless.
    }
    state.index += 1;
    if (state.index >= state.data.total) await settle();
    else paint();
  }

  async function settle() {
    state.phase = 'loading';
    paint();
    try {
      const f = await postJSON('/api/survey/finish', {
        sessionId: state.data.sessionId, session: sessionId(),
      });
      if (!f.ok) throw new Error(f.error);
      state.finish = f;
      state.phase = 'wheel';
    } catch {
      state.phase = 'error';
    }
    paint();
  }

  async function start() {
    state.phase = 'loading';
    state.index = 0;
    state.finish = null;
    state.spin = null;
    state.spinsUsed = 0;
    state.angle = 0;
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
