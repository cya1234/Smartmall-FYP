// js/views/aesthetic.js — Fashion AesRec score for today's outfit.
//
// Upload a photo, get a 0-100 score plus the three signals behind it. The point is
// that the number is decomposable: you can see which part helped and which hurt,
// rather than being told "8/10, trust me".
import { getJSON, postJSON } from '../api.js';
import { esc, t, isZh, toast, mediaInner } from '../ui.js';

const RING_R = 52;
const RING_C = 2 * Math.PI * RING_R;

function ring(score, label) {
  const filled = (Math.max(0, Math.min(100, score)) / 100) * RING_C;
  const colour = score >= 78 ? '#3DD68C' : score >= 64 ? '#8B7BFF' : score >= 50 ? '#F5B54A' : '#FF6B6B';
  return `<svg viewBox="0 0 120 120" width="140" height="140" style="display:block;margin:0 auto">
    <circle cx="60" cy="60" r="${RING_R}" fill="none" stroke="var(--surface-2)" stroke-width="11" />
    <circle cx="60" cy="60" r="${RING_R}" fill="none" stroke="${colour}" stroke-width="11"
      stroke-linecap="round" stroke-dasharray="${filled.toFixed(1)} ${RING_C.toFixed(1)}"
      transform="rotate(-90 60 60)" style="transition:stroke-dasharray .8s cubic-bezier(.2,.8,.2,1)" />
    <text x="60" y="58" text-anchor="middle" font-size="26" font-weight="800" fill="var(--ink)">${score}</text>
    <text x="60" y="76" text-anchor="middle" font-size="9" fill="var(--muted)">${esc(label)}</text>
  </svg>`;
}

function bar(label, value) {
  const colour = value >= 70 ? '#3DD68C' : value >= 45 ? '#8B7BFF' : '#F5B54A';
  return `<div style="margin-bottom:12px">
    <div class="row-between" style="margin-bottom:4px">
      <span class="small">${esc(label)}</span>
      <span class="small" style="font-variant-numeric:tabular-nums"><strong>${value}</strong>/100</span>
    </div>
    <div style="height:7px;border-radius:99px;background:var(--surface-2);overflow:hidden">
      <div style="height:100%;width:${Math.max(2, Math.min(100, value))}%;border-radius:99px;
                  background:${colour};transition:width .7s cubic-bezier(.2,.8,.2,1)"></div>
    </div>
  </div>`;
}

export async function render(root, ctx) {
  const state = { phase: 'idle', result: null, preview: null, error: null };

  function paint() {
    if (state.phase === 'loading') {
      root.innerHTML = `<section class="container" style="max-width:820px">
        <div class="card">${esc(t('common.loading'))}</div></section>`;
      return;
    }

    const r = state.result;

    root.innerHTML = `<section class="container" style="max-width:820px">
      <h1 class="section-title">📸 ${esc(t('aes.title'))}</h1>
      <p class="section-sub">${esc(t('aes.sub'))}</p>

      <div class="card">
        <div style="display:flex;gap:18px;flex-wrap:wrap;align-items:center">
          <div style="flex:0 0 150px;height:190px;border-radius:14px;overflow:hidden;
                      background:var(--surface-2);display:flex;align-items:center;justify-content:center">
            ${state.preview
              ? `<img src="${state.preview}" alt="" style="width:100%;height:100%;object-fit:cover" />`
              : `<span style="font-size:2.4rem">📷</span>`}
          </div>
          <div style="flex:1;min-width:220px">
            <button class="btn btn-primary" id="aes-pick">
              ${esc(state.preview ? t('aes.change') : t('aes.upload'))}
            </button>
            <input type="file" id="aes-file" accept="image/*" class="hidden" />
            <p class="muted small" style="margin:10px 0 0">${esc(t('aes.hint'))}</p>
          </div>
        </div>
      </div>

      ${state.phase === 'error' ? `
        <div class="card" style="margin-top:16px">
          <strong>${esc(t('aes.offline'))}</strong>
          <p class="muted small" style="margin:6px 0 0">${esc(state.error || '')}</p>
        </div>` : ''}

      ${state.phase === 'scoring' ? `
        <div class="card" style="margin-top:16px;text-align:center;padding:30px">
          <div style="font-size:2rem">🔍</div>
          <p class="muted" style="margin:8px 0 0">${esc(t('aes.scoring'))}</p>
        </div>` : ''}

      ${r ? `
        <div class="card" style="margin-top:16px">
          <div style="display:flex;gap:22px;flex-wrap:wrap;align-items:center">
            <div style="flex:0 0 auto">${ring(r.score, r.verdictLabel)}</div>
            <div style="flex:1;min-width:230px">
              ${bar(t('aes.style'), r.subscores.style)}
              ${bar(t('aes.coverage'), r.subscores.coverage)}
              ${bar(t('aes.palette'), r.subscores.palette)}
            </div>
          </div>

          <div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--line)">
            <ul style="margin:0;padding-left:18px">
              ${r.reasons.map((x) => `<li class="small" style="margin-bottom:5px">
                ${esc(t('aes.r.' + x.key))}
                <span class="muted">(${x.value})</span>
              </li>`).join('')}
            </ul>
          </div>

          ${(r.detail.closestOwned || []).length ? `
            <div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--line)">
              <strong class="small">${esc(t('aes.closest'))}</strong>
              <div style="display:flex;gap:12px;margin-top:10px;flex-wrap:wrap">
                ${r.detail.closestOwned.map((c) => `<div style="width:78px;text-align:center">
                  <div style="height:78px;border-radius:10px;background:var(--surface-2);
                              display:flex;align-items:center;justify-content:center;overflow:hidden">
                    ${mediaInner(c, '1.6rem')}
                  </div>
                  <span class="muted" style="font-size:0.7rem;display:block;margin-top:4px">
                    ${Math.round(c.similarity * 100)}%
                  </span>
                </div>`).join('')}
              </div>
            </div>` : ''}

          <p class="muted small" style="margin:16px 0 0;font-size:0.75rem">
            ${esc(t('aes.caveat'))} · ${esc(r.judge)} · ${r.tookMs}ms
          </p>
        </div>` : ''}
    </section>`;

    const file = root.querySelector('#aes-file');
    const pick = root.querySelector('#aes-pick');
    if (pick) pick.addEventListener('click', () => file.click());
    if (file) file.addEventListener('change', () => {
      if (file.files.length) score(file.files[0]);
    });
  }

  function score(fileObj) {
    if (!fileObj.type.startsWith('image/')) {
      toast(isZh() ? '請選擇圖片檔' : 'Please choose an image');
      return;
    }
    const reader = new FileReader();
    reader.onload = async (e) => {
      state.preview = e.target.result;
      state.phase = 'scoring';
      state.result = null;
      paint();
      try {
        const r = await postJSON(`/api/aesthetic/score?lang=${isZh() ? 'zh' : 'en'}`, {
          image: e.target.result,
        });
        if (!r || r.online === false) throw new Error(r?.reason || 'offline');
        state.result = r;
        state.phase = 'idle';
      } catch (err) {
        state.phase = 'error';
        state.error = String(err.message || err);
      }
      paint();
    };
    reader.readAsDataURL(fileObj);
  }

  paint();

  // Tell the user up front if the scoring service is not running.
  try {
    const s = await getJSON('/api/aesthetic/status');
    if (!s.online) {
      state.phase = 'error';
      state.error = t('aes.offlineHint');
      paint();
    }
  } catch { /* leave the page usable */ }
}
