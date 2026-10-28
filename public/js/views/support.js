// js/views/support.js — Feature 7: smart customer service (guided returns).
import { getJSON, postJSON } from '../api.js';
import { esc, fmtPrice, toast, hexA, pName, t, isZh, mediaInner } from '../ui.js';

// Extract image features the defect classifier can reason over.
function extractFeatures(img) {
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const c = canvas.getContext('2d');
  c.drawImage(img, 0, 0, size, size);
  const { data } = c.getImageData(0, 0, size, size);

  let sumL = 0, sumS = 0, dark = 0, n = 0;
  const lums = [];
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i], g = data[i + 1], b = data[i + 2];
    const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    sumL += lum;
    sumS += mx === 0 ? 0 : (mx - mn) / mx;
    if (lum < 50) dark++;
    lums.push(lum);
    n++;
  }
  let edges = 0, pairs = 0;
  for (let y = 0; y < size; y++) {
    for (let x = 1; x < size; x++) {
      const i = (y * size + x) * 4;
      const j = (y * size + x - 1) * 4;
      const d = Math.abs(data[i] - data[j]) + Math.abs(data[i + 1] - data[j + 1]) + Math.abs(data[i + 2] - data[j + 2]);
      if (d > 90) edges++;
      pairs++;
    }
  }
  const mean = sumL / n;
  const varr = lums.reduce((a, v) => a + (v - mean) ** 2, 0) / n;

  return {
    brightness: Math.round((sumL / n / 255) * 1000) / 1000,
    saturation: Math.round((sumS / n) * 1000) / 1000,
    darkSpotRatio: Math.round((dark / n) * 1000) / 1000,
    edgeDensity: Math.round((edges / pairs) * 1000) / 1000,
    colourVariance: Math.round(Math.min(1, Math.sqrt(varr) / 128) * 1000) / 1000,
    samples: n,
  };
}

export async function render(root, ctx) {
  root.innerHTML = `<section class="container"><div class="card">${esc(t('common.loading'))}</div></section>`;

  const [profile, stats, reasonsRes] = await Promise.all([
    getJSON(`/api/profile?lang=${isZh() ? 'zh' : 'en'}`).catch(() => ({ wardrobe: [] })),
    getJSON(`/api/support/stats?lang=${isZh() ? 'zh' : 'en'}`).catch(() => ({ stats: {}, forms: [] })),
    getJSON('/api/support/reasons').catch(() => ({ reasons: [] })),
  ]);

  const wardrobe = (profile.wardrobe || []).slice(0, 6);
  const reasons = reasonsRes.reasons || [];
  const st = stats.stats || {};

  root.innerHTML = `
    <section class="container">
      <h1 class="section-title">${esc(t('sp.title'))}</h1>
      <p class="section-sub">${esc(t('sp.sub'))}</p>

      <div class="card" style="margin-bottom:18px">
        <div class="pa-summary" style="margin:0">
          <div class="stat"><div class="k">${esc(t('sp.handled'))}</div><div class="v">${st.sessionsHandled ?? 0}</div></div>
          <div class="stat"><div class="k">${esc(t('sp.forms'))}</div><div class="v">${st.formsGenerated ?? 0}</div></div>
          <div class="stat good"><div class="k">${esc(t('sp.avgTime'))}</div><div class="v">${st.avgResolutionMinutes ?? '—'} ${esc(t('sp.minutes'))}</div></div>
        </div>
      </div>

      <div class="steps-bar" id="sp-steps"></div>
      <div id="sp-body"></div>
    </section>
  `;

  const stepsEl = root.querySelector('#sp-steps');
  const body = root.querySelector('#sp-body');

  const steps = [
    { id: 'order', label: t('sp.step1') },
    { id: 'reason', label: t('sp.step2') },
    { id: 'photo', label: t('sp.step3') },
    { id: 'form', label: t('sp.step4') },
  ];

  const stState = { step: 0, productId: ctx.state.supportProduct || (wardrobe[0] && wardrobe[0].productId), reason: reasons[0]?.id || 'defect', session: null, features: null, analysis: null, form: null };

  function drawSteps() {
    stepsEl.innerHTML = steps.map((s, i) =>
      `<div class="step-chip ${i < stState.step ? 'done' : i === stState.step ? 'active' : ''}">
        <span class="n">${i < stState.step ? '✓' : i + 1}</span>${esc(s.label)}
      </div>`).join('');
  }

  function renderStep() {
    drawSteps();
    if (stState.step === 0) renderPickProduct();
    else if (stState.step === 1) renderReason();
    else if (stState.step === 2) renderPhoto();
    else renderForm();
  }

  // ---- Step 1: pick item --------------------------------------------------
  function renderPickProduct() {
    body.innerHTML = `
      <div class="card">
        <h3>${esc(t('sp.pickProduct'))}</h3>
        <div class="set-grid" style="margin-top:14px">
          ${wardrobe.map((w) => `
            <div class="set-item ${w.productId === stState.productId ? 'is-owned' : ''}" data-pid="${esc(w.productId)}" style="cursor:pointer">
              <div class="thumb" style="background:linear-gradient(135deg, ${hexA(w.product.color, 0.14)}, ${hexA(w.product.color, 0.3)})">${mediaInner(w.product, '2.6rem')}</div>
              <div class="body">
                <div class="nm">${esc(pName(w.product))}</div>
                <div class="pr">${fmtPrice(w.product.price)}</div>
                <div class="note">${esc(isZh() ? w.purchasedLabel : w.purchasedLabel_en)} · ${esc(w.size)}</div>
              </div>
            </div>`).join('')}
        </div>
        <div class="row-between" style="margin-top:16px">
          <span class="muted small" id="sp-sel">${esc(t('sp.pickProduct'))}</span>
          <button class="btn btn-primary" id="sp-next" ${stState.productId ? '' : 'disabled'}>${esc(t('common.apply'))}</button>
        </div>
      </div>`;

    body.querySelectorAll('[data-pid]').forEach((el) =>
      el.addEventListener('click', () => {
        stState.productId = el.dataset.pid;
        body.querySelectorAll('[data-pid]').forEach((x) => x.classList.toggle('is-owned', x === el));
        body.querySelector('#sp-next').disabled = false;
      }));
    body.querySelector('#sp-next').addEventListener('click', () => { stState.step = 1; renderStep(); });
  }

  // ---- Step 2: reason -----------------------------------------------------
  function renderReason() {
    body.innerHTML = `
      <div class="card">
        <h3>${esc(t('sp.reason'))}</h3>
        <div class="chips" style="margin-top:14px">
          ${reasons.map((r) => `<button class="chip ${r.id === stState.reason ? 'active' : ''}" data-r="${r.id}">${esc(isZh() ? r.zh : r.en)}</button>`).join('')}
        </div>
        <div class="row-between" style="margin-top:18px">
          <button class="btn btn-ghost" id="sp-back">← ${esc(t('common.back'))}</button>
          <button class="btn btn-primary" id="sp-next">${esc(t('common.apply'))}</button>
        </div>
      </div>`;
    body.querySelectorAll('[data-r]').forEach((b) =>
      b.addEventListener('click', () => {
        stState.reason = b.dataset.r;
        body.querySelectorAll('[data-r]').forEach((x) => x.classList.toggle('active', x === b));
      }));
    body.querySelector('#sp-back').addEventListener('click', () => { stState.step = 0; renderStep(); });
    body.querySelector('#sp-next').addEventListener('click', async () => { await startSession(); });
  }

  async function startSession() {
    try {
      stState.session = await postJSON('/api/support/session', {
        productId: stState.productId, reason: stState.reason,
      });
      stState.step = 2;
      renderStep();
    } catch { toast(t('common.retry')); }
  }

  // ---- Step 3: photo + AI inspection -------------------------------------
  function renderPhoto() {
    body.innerHTML = `
      <div class="card">
        <h3>${esc(t('sp.upload'))}</h3>
        <p class="muted small">${esc(t('sp.uploadHint'))}</p>
        <div class="dropzone" id="sp-drop" style="margin-top:14px">
          <div class="big">📷</div>
          <p><strong>${esc(t('sp.upload'))}</strong></p>
          <input type="file" id="sp-file" accept="image/*" class="hidden" />
        </div>
        <div class="preview-strip" id="sp-preview"></div>
        <div id="sp-analysis" style="margin-top:16px"></div>
      </div>`;

    const drop = body.querySelector('#sp-drop');
    const file = body.querySelector('#sp-file');
    const preview = body.querySelector('#sp-preview');
    const analysis = body.querySelector('#sp-analysis');

    drop.addEventListener('click', () => file.click());
    file.addEventListener('change', () => { if (file.files.length) handle(file.files[0]); });
    drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('drag'); });
    drop.addEventListener('dragleave', () => drop.classList.remove('drag'));
    drop.addEventListener('drop', (e) => {
      e.preventDefault(); drop.classList.remove('drag');
      if (e.dataTransfer.files.length) handle(e.dataTransfer.files[0]);
    });

    function handle(f) {
      if (!f.type.startsWith('image/')) { toast(isZh() ? '請選擇圖片檔' : 'Please choose an image'); return; }
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = async () => {
          preview.innerHTML = `<img src="${e.target.result}" alt="preview" />`;
          stState.features = extractFeatures(img);
          analysis.innerHTML = `<div class="card box-reveal" style="padding:24px"><span class="spinner dark" style="width:24px;height:24px"></span><p class="muted">${esc(t('sp.analysing'))}</p></div>`;
          try {
            const res = await postJSON('/api/support/analyze', {
              sessionId: stState.session.id, features: stState.features,
              lang: isZh() ? 'zh' : 'en',
            });
            stState.analysis = res;
            setTimeout(() => renderAnalysis(analysis), 700);
          } catch { analysis.innerHTML = `<div class="card">${esc(t('common.retry'))}</div>`; }
        };
        img.src = e.target.result;
      };
      reader.readAsDataURL(f);
    }

    function renderAnalysis(host) {
      const a = stState.analysis;
      const maxScore = a.evidence[0]?.score || 1;
      host.innerHTML = `
        <div class="defect-box">
          <div class="row-between">
            <h3 style="margin:0">🔍 ${esc(t('sp.detected'))}</h3>
            <span class="badge ${a.detected ? 'badge-warn' : 'badge-good'}">${esc(t('sp.confidence'))} ${Math.round(a.confidence * 100)}%</span>
          </div>
          <p style="margin:10px 0 4px;font-weight:800;font-size:1.05rem">${esc(isZh() ? a.label_zh : a.label)}</p>
          <p class="muted small" style="margin:0 0 12px">${esc(isZh() ? a.cause_zh : a.cause)}</p>
          <div class="divider"></div>
          <div class="muted small" style="margin-bottom:8px">${esc(t('sp.cause'))} / ${esc(t('sp.resolution'))}</div>
          ${a.evidence.slice(0, 4).map((e) => `
            <div class="evidence-row">
              <span class="en">${esc(e.defect)}</span>
              <span class="eb"><i style="width:${Math.round((e.score / maxScore) * 100)}%"></i></span>
              <span class="mono small">${e.score}</span>
            </div>`).join('')}
          <p class="small" style="margin-top:12px;color:var(--ink-2)">${esc(a.guidance)}</p>
        </div>
        <div class="row-between" style="margin-top:16px">
          <button class="btn btn-ghost" id="sp-back">← ${esc(t('common.back'))}</button>
          <button class="btn btn-primary" id="sp-submit">${esc(t('sp.submit'))}</button>
        </div>`;
      host.querySelector('#sp-back').addEventListener('click', () => { stState.step = 1; renderStep(); });
      host.querySelector('#sp-submit').addEventListener('click', submit);
    }
  }

  async function submit() {
    try {
      stState.form = await postJSON('/api/support/submit', {
        sessionId: stState.session.id,
        defect: stState.analysis?.defect || null,
        note: '',
        lang: isZh() ? 'zh' : 'en',
      });
      stState.step = 3;
      renderStep();
    } catch { toast(t('common.retry')); }
  }

  // ---- Step 4: return form -----------------------------------------------
  function renderForm() {
    const f = stState.form;
    const pickup = new Date(f.pickup.date).toLocaleString(isZh() ? 'zh-HK' : 'en-US', { month: 'short', day: 'numeric' });
    body.innerHTML = `
      <div class="card">
        <div class="row-between">
          <h3 style="margin:0">✅ ${esc(t('sp.form'))}</h3>
          <span class="badge badge-good">${esc(isZh() ? '已核准' : 'Approved')}</span>
        </div>
        <div class="form-grid" style="margin-top:16px">
          <div class="form-field"><div class="k">${esc(t('sp.rma'))}</div><div class="v rma-code">${esc(f.rma)}</div></div>
          <div class="form-field"><div class="k">${esc(t('sp.refund'))}</div><div class="v">${fmtPrice(f.refund.amount)}</div></div>
          <div class="form-field"><div class="k">${esc(t('sp.method'))}</div><div class="v">${esc(f.refund.method)}</div></div>
          <div class="form-field"><div class="k">${esc(t('sp.pickup'))}</div><div class="v">${esc(pickup)} · ${esc(f.pickup.window)}</div></div>
          <div class="form-field"><div class="k">${esc(t('sp.carrier'))}</div><div class="v">${esc(f.pickup.carrier)}</div></div>
          <div class="form-field"><div class="k">${esc(t('sp.detected'))}</div><div class="v">${esc(isZh() ? f.defect.label_zh : f.defect.label)}</div></div>
        </div>
        <div class="divider"></div>
        <p style="font-weight:600;color:var(--good)">${esc(f.message)}</p>
        <div class="divider"></div>
        <h3 style="font-size:0.95rem">${esc(t('sp.timeline'))}</h3>
        <div class="timeline">
          ${f.timeline.map((x) => `
            <div class="tl-item">
              <span class="tl-dot ${x.done ? 'done' : ''}">${x.done ? '✓' : '·'}</span>
              <span class="tl-text">${esc(isZh() ? x.zh : x.en)}</span>
            </div>`).join('')}
        </div>
        <button class="btn btn-ghost btn-block" style="margin-top:18px" id="sp-again">${esc(t('sp.newCase'))}</button>
      </div>`;
    body.querySelector('#sp-again').addEventListener('click', () => {
      stState.step = 0; stState.session = null; stState.analysis = null; stState.form = null; stState.features = null;
      renderStep();
    });
  }

  renderStep();
}
