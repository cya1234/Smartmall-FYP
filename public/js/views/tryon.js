// js/views/tryon.js — virtual try-on (simulated diffusion) + private friend voting.
import { postJSON, getJSON } from '../api.js';
import { toast, hexA, esc, pName, t, isZh, mediaInner } from '../ui.js';

export function render(root, ctx) {
  const garments = ctx.products.filter((p) => ['Dress', 'Shirt', 'Sweater', 'Jacket', 'Ski Jacket', 'Fleece', 'Trousers', 'Ski Pants'].includes(p.subcategory));
  const initial = ctx.state.tryonProduct && ctx.products.find((p) => p.id === ctx.state.tryonProduct)
    ? ctx.state.tryonProduct
    : garments[0]?.id;

  root.innerHTML = `
    <section class="container">
      <h1 class="section-title">${esc(t('feat.tryon.t'))}</h1>
      <p class="section-sub">${esc(t('feat.tryon.d'))} · ${esc(t('sv.sub'))}</p>

      <div class="tryon-layout">
        <div>
          <div class="canvas-stage" id="stage">
            <canvas id="tryon-canvas" class="hidden"></canvas>
            <img id="tryon-result" class="hidden" alt=""
                 style="border-radius:inherit" />
            <div class="placeholder" id="stage-placeholder">
              <div style="font-size:3rem">🧍</div>
              <p><strong>${esc(t('sp.upload'))}</strong></p>
              <p class="muted small">${esc(isZh() ? "建議：正面、腰部以上半身、光線均勻" : "Tip: front-facing, waist-up, even lighting" )}</p>
              <button class="btn btn-ghost" id="upload-btn">📷 ${esc(t('sp.upload'))}</button>
              <input type="file" id="photo-input" accept="image/*" class="hidden" />
            </div>
            <div class="placeholder hidden" id="stage-loading" style="position:absolute;inset:0;background:rgba(255,255,255,0.88);display:flex;flex-direction:column;align-items:center;justify-content:center">
              <span class="spinner dark" style="width:28px;height:28px"></span>
              <p class="muted">${esc(t('common.loading'))}</p>
            </div>
          </div>
          <div class="muted small" id="tryon-note" style="margin-top:10px"></div>

          <div class="card" style="margin-top:16px">
            <h3 style="margin-top:0">${esc(t('sv.title'))}</h3>
            <div class="privacy-bar">🔒 ${esc(t('sv.onlyFriends'))}</div>
            <div class="chips" id="sv-groups"></div>
            <button class="btn btn-accent btn-block" id="sv-share" style="margin-top:14px">${esc(t('sv.share'))}</button>
          </div>
        </div>

        <div>
          <h3 style="margin:0 0 12px">${esc(t('sv.selectGarment'))}</h3>
          <div class="garment-list" style="grid-template-columns:1fr 1fr">
            ${garments.map((g) => `<div class="garment ${g.id === initial ? 'active' : ''}" data-id="${g.id}">
              <div class="g-emoji">${mediaInner(g, '1.7rem')}</div>
              <div class="g-name">${esc(pName(g))}</div>
              <div class="muted small">${esc(g.colorName)}</div>
            </div>`).join('')}
          </div>
        </div>
      </div>

      <div id="sv-poll" style="margin-top:20px"></div>
    </section>
  `;

  const canvas = root.querySelector('#tryon-canvas');
  const placeholder = root.querySelector('#stage-placeholder');
  const loading = root.querySelector('#stage-loading');
  const note = root.querySelector('#tryon-note');
  const resultImg = root.querySelector('#tryon-result');
  const photoInput = root.querySelector('#photo-input');
  const pollHost = root.querySelector('#sv-poll');

  let photo = null;
  let garment = garments.find((g) => g.id === initial) || garments[0];
  let groupId = 'bff';
  let groups = [];

  // ---- Group picker -------------------------------------------------------
  getJSON('/api/social/groups').then((d) => {
    groups = d.groups;
    root.querySelector('#sv-groups').innerHTML = groups.map((g) => `
      <button class="chip ${g.id === groupId ? 'active' : ''}" data-g="${g.id}">
        ${g.emoji} ${esc(isZh() ? g.name_zh : g.name)} · ${g.members.length} ${esc(t('sv.members'))}
      </button>`).join('');
    root.querySelectorAll('[data-g]').forEach((b) =>
      b.addEventListener('click', () => {
        groupId = b.dataset.g;
        root.querySelectorAll('[data-g]').forEach((x) => x.classList.toggle('active', x === b));
      }));
  }).catch(() => {});

  root.querySelector('#upload-btn').addEventListener('click', () => photoInput.click());
  photoInput.addEventListener('change', () => { if (photoInput.files.length) loadPhoto(photoInput.files[0]); });

  function loadPhoto(file) {
    if (!file.type.startsWith('image/')) { toast(isZh() ? '請選擇圖片檔' : 'Please choose an image'); return; }
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        photo = img;
        placeholder.classList.add('hidden');
        // A new photo invalidates any previous CatVTON result.
        resultImg.classList.add('hidden');
        resultImg.removeAttribute('src');
        canvas.classList.remove('hidden');
        drawPreview();
        toast(isZh() ? '照片已載入，選擇服飾即可試穿' : 'Photo loaded — pick a garment');
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }

  function drawPreview() {
    if (!photo || !garment) return;
    const maxW = 460;
    const scale = Math.min(1, maxW / photo.width);
    canvas.width = photo.width * scale;
    canvas.height = photo.height * scale;
    const c = canvas.getContext('2d');
    c.clearRect(0, 0, canvas.width, canvas.height);
    c.drawImage(photo, 0, 0, canvas.width, canvas.height);

    const cx = canvas.width / 2;
    const cy = canvas.height * 0.58;
    const r = Math.min(canvas.width, canvas.height) * 0.34;
    c.save();
    c.globalCompositeOperation = 'overlay';
    const grad = c.createRadialGradient(cx, cy, r * 0.15, cx, cy, r);
    grad.addColorStop(0, hexA(garment.color, 0.9));
    grad.addColorStop(1, hexA(garment.color, 0.15));
    c.fillStyle = grad;
    c.beginPath();
    c.ellipse(cx, cy, r, r * 1.15, 0, 0, Math.PI * 2);
    c.fill();
    c.restore();

    c.fillStyle = 'rgba(20,22,34,0.78)';
    const label = `  ${garment.emoji} ${pName(garment)}  `;
    c.font = '600 13px system-ui, sans-serif';
    const w = c.measureText(label).width + 8;
    c.beginPath();
    if (c.roundRect) c.roundRect(12, canvas.height - 42, w, 30, 9); else c.rect(12, canvas.height - 42, w, 30);
    c.fill();
    c.fillStyle = '#fff';
    c.textBaseline = 'middle';
    c.fillText(label, 16, canvas.height - 27);
  }

  async function synthesize() {
    if (!photo) { toast(isZh() ? '請先上傳照片' : 'Upload a photo first'); return; }
    loading.classList.remove('hidden');
    const label = loading.querySelector('p');
    const started = Date.now();
    try {
      const photoData = photo.src;   // the data URL loaded from the file input
      const tick = setInterval(() => {
        const s = Math.round((Date.now() - started) / 1000);
        if (label) {
          label.textContent = isZh()
            ? `正在用 CatVTON 生成試穿效果… ${s}s（首次載入較慢）`
            : `Synthesising with CatVTON… ${s}s (first run is slower)`;
        }
      }, 1000);

      const res = await postJSON('/api/tryon', { productId: garment.id, photo: photoData, steps: 30 });
      clearInterval(tick);

      if (res.engine === 'catvton' && res.image) {
        // Real synthesis: show the generated photo instead of drawing an overlay.
        canvas.classList.add('hidden');
        placeholder.classList.add('hidden');
        resultImg.src = res.image;
        resultImg.classList.remove('hidden');
        note.textContent = `${res.product.name_zh || res.product.name} · CatVTON · ${(res.tookMs / 1000).toFixed(1)}s`;
        return;
      }
      note.textContent = `${res.product.colorName} · ${res.product.material} · ${res.note || ''}`;
      drawPreview();
    } catch {
      toast(t('common.retry'));
    } finally {
      loading.classList.add('hidden');
    }
  }

  root.querySelectorAll('.garment').forEach((el) =>
    el.addEventListener('click', () => {
      root.querySelectorAll('.garment').forEach((x) => x.classList.remove('active'));
      el.classList.add('active');
      garment = garments.find((g) => g.id === el.dataset.id);
      ctx.state.tryonProduct = garment.id;
      if (photo) synthesize();
    }));

  // ---- Share to private group --------------------------------------------
  root.querySelector('#sv-share').addEventListener('click', async () => {
    if (!photo) { toast(t('sv.selectGarment')); return; }
    pollHost.innerHTML = `<div class="card box-reveal"><div class="box">📤</div><p class="muted">${esc(t('sv.sharing'))}</p></div>`;
    try {
      const poll = await postJSON('/api/social/polls', {
        productId: garment.id, groupId, imageAttached: true, note: '',
      });
      ctx.state.lastPoll = poll;
      setTimeout(() => renderPoll(pollHost, poll, ctx), 500);
    } catch {
      pollHost.innerHTML = `<div class="card">${esc(t('common.retry'))}</div>`;
    }
  });
}

export function renderPoll(host, poll, ctx) {
  const { tally, verdict } = poll;
  const pct = (n) => (tally.total ? Math.round((n / tally.total) * 100) : 0);

  host.innerHTML = `
    <div class="poll-card">
      <div class="row-between">
        <h3 style="margin:0">${poll.group.emoji} ${esc(isZh() ? poll.group.name_zh : poll.group.name)}</h3>
        <span class="badge badge-info">${tally.total} ${esc(t('sv.votes'))} / ${poll.group.memberCount}</span>
      </div>
      <div class="privacy-bar" style="margin-top:12px">🔒 ${esc(t('sv.onlyFriends'))}</div>

      <div class="row-between">
        <div style="display:flex;align-items:center;gap:10px">
          <span style="font-size:1.8rem">${poll.product.emoji}</span>
          <div>
            <div style="font-weight:700">${esc(isZh() ? poll.product.name_zh : poll.product.name)}</div>
            <div class="muted small">${esc(isZh() ? '由你分享' : 'Shared by you')}</div>
          </div>
        </div>
        <button class="btn btn-ghost btn-sm" id="sv-sim">${esc(t('sv.simulate'))}</button>
      </div>

      ${tally.total ? `
        <div class="vote-bar">
          <span class="vote-love" style="width:${pct(tally.love)}%"></span>
          <span class="vote-ok" style="width:${pct(tally.ok)}%"></span>
          <span class="vote-no" style="width:${pct(tally.no)}%"></span>
        </div>
        <div class="vote-legend">
          <span>🟢 ${esc(t('sv.love'))} <b>${tally.love}</b> (${pct(tally.love)}%)</span>
          <span>🟡 ${esc(t('sv.ok'))} <b>${tally.ok}</b> (${pct(tally.ok)}%)</span>
          <span>🔴 ${esc(t('sv.no'))} <b>${tally.no}</b> (${pct(tally.no)}%)</span>
        </div>

        <div class="verdict-box ${verdict.key}">
          <div style="font-weight:800">${esc(isZh() ? verdict.zh : verdict.en)}</div>
          <p class="small" style="margin:6px 0 0;color:var(--ink-2)">${esc(isZh() ? verdict.advice_zh : verdict.advice_en)}</p>
        </div>

        <h4 style="margin:16px 0 4px;font-size:0.92rem">${esc(t('sv.comments'))}</h4>
        ${poll.votes.map((v) => `
          <div class="friend-row">
            <span class="av">${v.avatar}</span>
            <div class="fm">
              <div class="fn">${esc(isZh() ? v.name : (v.name_en || v.name))}</div>
              <div class="fc">${esc(isZh() ? v.comment.zh : v.comment.en)}</div>
            </div>
            <span class="vote-tag vt-${v.vote}">${esc(v.vote === 'love' ? t('sv.love') : v.vote === 'ok' ? t('sv.ok') : t('sv.no'))}</span>
          </div>`).join('')}
      ` : `<p class="muted">${esc(t('sv.waiting'))}</p>`}
    </div>
  `;

  host.querySelector('#sv-sim').addEventListener('click', async () => {
    try {
      const updated = await postJSON(`/api/social/polls/${poll.id}/simulate`, {});
      ctx.state.lastPoll = updated;
      renderPoll(host, updated, ctx);
    } catch { toast(t('common.retry')); }
  });
}
