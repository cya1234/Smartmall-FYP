// js/views/visual.js — multimodal visual search (CLIP + FAISS, colour fallback).
import { getJSON, postJSON } from '../api.js';
import { productCard, emptyState, toast, esc, t, isZh } from '../ui.js';
import { track } from '../exitIntent.js';

const MAX_SIDE = 512; // downscale uploads before sending to the model

function toHex(v) {
  return Math.round(v).toString(16).padStart(2, '0');
}

// Dominant colours are still computed: they are shown to the user and they
// drive the colour-heuristic fallback when the CLIP service is offline.
function extractDominantColors(img, n = 3) {
  const size = 48;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const c = canvas.getContext('2d');
  c.drawImage(img, 0, 0, size, size);
  const data = c.getImageData(0, 0, size, size).data;
  const buckets = new Map();
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] < 128) continue;
    const key = ((data[i] >> 5) << 6) | ((data[i + 1] >> 5) << 3) | (data[i + 2] >> 5);
    const b = buckets.get(key) || { n: 0, r: 0, g: 0, b: 0 };
    b.n += 1; b.r += data[i]; b.g += data[i + 1]; b.b += data[i + 2];
    buckets.set(key, b);
  }
  return [...buckets.values()]
    .sort((a, b) => b.n - a.n)
    .slice(0, n)
    .map((x) => ({ hex: `#${toHex(x.r / x.n)}${toHex(x.g / x.n)}${toHex(x.b / x.n)}`, weight: x.n }));
}

function downscale(img, maxSide = MAX_SIDE) {
  const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(img.width * scale));
  canvas.height = Math.max(1, Math.round(img.height * scale));
  canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/jpeg', 0.85);
}

const EXAMPLES_ZH = ['紅色洋裝', '白色球鞋', '黑色太陽眼鏡', '藍色滑雪外套', '米色長褲'];
const EXAMPLES_EN = ['a red dress', 'white sneakers', 'black sunglasses', 'a blue ski jacket', 'beige trousers'];

export async function render(root, ctx) {
  const status = await getJSON('/api/visual-search/status').catch(() => ({ online: false }));
  const examples = isZh() ? EXAMPLES_ZH : EXAMPLES_EN;

  root.innerHTML = `
    <section class="container">
      <h1 class="section-title">🔍 ${esc(t('nav.visual'))}</h1>
      <p class="section-sub">${esc(isZh()
        ? '上傳一張圖片，並可加上文字條件 — 「同款但要亞麻材質」、「改得更正式」。圖片與文字會融合成單一查詢向量，在 CLIP 向量空間中檢索。'
        : 'Upload an image and optionally add a text modifier — “same colour, but linen”, “make it more formal”. Image and text fuse into one query vector for CLIP retrieval.')}</p>

      <div class="engine-bar ${status.online ? '' : 'offline'}">
        <span>${status.online ? '🟢' : '🟡'} ${esc(status.online ? t('vs.online') : t('vs.offline'))}</span>
        ${status.online ? `
          <span class="sep">·</span><span>${esc(t('vs.model'))} ${esc(status.model)}/${esc(status.pretrained)}</span>
          <span class="sep">·</span><span>${esc(t('vs.device'))} ${esc(status.gpu || status.device)}</span>
          <span class="sep">·</span><span>${esc(t('vs.indexed'))} ${status.indexed}</span>
        ` : `<span class="sep">·</span><span>${esc(status.url || '')}</span>`}
      </div>

      <div class="tryon-layout">
        <div>
          <div class="dropzone" id="dropzone">
            <div class="big">🖼️</div>
            <p><strong>${esc(isZh() ? '把圖片拖到這裡' : 'Drop an image here')}</strong>${esc(isZh() ? '，或點擊選擇檔案' : ' or click to browse')}</p>
            <p class="small">${esc(isZh() ? '系統會用 CLIP 抽取視覺特徵，找出語意相似的商品。' : 'CLIP extracts visual features to find semantically similar products.')}</p>
            <input type="file" id="file-input" accept="image/*" class="hidden" />
          </div>
          <div class="preview-strip" id="preview"></div>
          <div class="swatch-row" id="swatches"></div>
          <div class="searchbar" style="margin-top:16px">
            <input class="input" id="vis-text" placeholder="${esc(isZh() ? '選填文字條件，例如「亞麻」、「正式」、「婚禮」' : 'Optional text modifier, e.g. “linen”, “formal”, “for a wedding”')}" />
            <button class="btn btn-primary" id="vis-search">${esc(t('common.search'))}</button>
          </div>
          <div class="suggestion-row" style="margin-top:12px">
            <span class="muted small" style="align-self:center">${esc(t('vs.examples'))}:</span>
            ${examples.map((e) => `<button class="suggestion" data-ex="${esc(e)}">${esc(e)}</button>`).join('')}
          </div>
        </div>
        <div class="card">
          <h3>${esc(isZh() ? '運作原理' : 'How it works')}</h3>
          <p class="muted" style="font-size:0.9rem">${esc(isZh()
            ? '圖片由 CLIP 影像編碼器轉成 512 維向量；文字條件由文字編碼器轉成同一空間的向量。兩者以加權平均融合成單一查詢向量，再用 FAISS 做內積檢索（等同餘弦相似度）。'
            : 'The CLIP image encoder maps your photo to a 512-d vector; the text encoder maps your modifier into the same space. They are fused by weighted average into one query vector, then FAISS runs an inner-product (cosine) lookup.')}</p>
          <div class="divider"></div>
          <div class="muted small">${esc(isZh()
            ? '若影像服務未啟動，系統會自動退回顏色比對，網站不會中斷。'
            : 'If the image service is down the site falls back to colour matching automatically, so it never breaks.')}</div>
        </div>
      </div>
      <div class="grid" id="vis-results" style="margin-top:24px"></div>
    </section>
  `;

  const dropzone = root.querySelector('#dropzone');
  const fileInput = root.querySelector('#file-input');
  const preview = root.querySelector('#preview');
  const swatches = root.querySelector('#swatches');
  const searchBtn = root.querySelector('#vis-search');
  const textInput = root.querySelector('#vis-text');
  const results = root.querySelector('#vis-results');
  let colors = [];
  let imageData = null;

  dropzone.addEventListener('click', () => fileInput.click());
  dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('drag'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag');
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', () => { if (fileInput.files.length) handleFile(fileInput.files[0]); });

  function handleFile(file) {
    if (!file.type.startsWith('image/')) { toast(isZh() ? '請選擇圖片檔' : 'Please choose an image'); return; }
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        preview.innerHTML = `<img src="${e.target.result}" alt="preview" />`;
        colors = extractDominantColors(img);
        imageData = downscale(img);
        swatches.innerHTML = `<span class="small muted">${esc(isZh() ? '偵測到的顏色' : 'Detected colours')}:</span>`
          + colors.map((c) => `<span class="swatch" style="background:${c.hex}" title="${c.hex}"></span>`).join('')
          + `<span class="small muted">${colors.map((c) => c.hex).join(', ')}</span>`;
        toast(t('vs.analysed'));
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }

  root.querySelectorAll('[data-ex]').forEach((b) =>
    b.addEventListener('click', () => { textInput.value = b.dataset.ex; run(); }));

  async function run() {
    const query = textInput.value.trim();
    if (!imageData && !query) { toast(t('vs.needInput')); return; }

    searchBtn.disabled = true;
    searchBtn.innerHTML = `<span class="spinner"></span> ${esc(t('common.search'))}…`;
    results.innerHTML = '';
    try {
      const res = await postJSON('/api/visual-search', { colors, query, image: imageData });
      try { track('search', 'visual', res.results?.length ?? 0); } catch { /* best-effort */ }
      renderResults(results, res, ctx);
    } catch {
      toast(t('common.retry'));
    } finally {
      searchBtn.disabled = false;
      searchBtn.textContent = t('common.search');
    }
  }

  searchBtn.addEventListener('click', run);
  textInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') run(); });
}

function renderResults(host, res, ctx) {
  const modeLabel = res.mode === 'image+text' ? t('vs.mode.both')
    : res.mode === 'image' ? t('vs.mode.image') : t('vs.mode.text');

  const bar = `<div class="engine-bar ${res.engine === 'clip' ? '' : 'offline'}" style="grid-column:1/-1">
    <span>${res.engine === 'clip' ? '🧠' : '🎨'} ${esc(res.engineLabel)}</span>
    <span class="sep">·</span><span>${esc(modeLabel)}</span>
    ${res.tookMs != null ? `<span class="sep">·</span><span>${esc(t('vs.latency'))} ${res.tookMs} ms</span>` : ''}
    ${res.textWeight != null ? `<span class="sep">·</span><span>${esc(t('vs.fusion'))} ${res.textWeight}</span>` : ''}
    ${res.imageSize ? `<span class="sep">·</span><span>${res.imageSize[0]}×${res.imageSize[1]} px</span>` : ''}
  </div>`;

  if (!res.results.length) {
    host.innerHTML = bar + `<div style="grid-column:1/-1">${emptyState('🔎', isZh() ? '沒有符合的商品' : 'No matches', isZh() ? '換一張圖片或調整文字條件。' : 'Try another image or text modifier.')}</div>`;
    return;
  }

  const items = res.results.map((r) => ctx.products.find((p) => p.id === r.id)).filter(Boolean);
  host.innerHTML = bar + items.map((p) => {
    const r = res.results.find((x) => x.id === p.id);
    return `<div style="position:relative">${productCard(p)}
      <div style="position:absolute;top:8px;right:8px;background:rgba(91,75,240,0.92);color:#fff;font-size:0.7rem;font-weight:700;padding:3px 8px;border-radius:8px">
        ${r.matchPercent}% ${esc(t('vs.match'))}</div>
      <div class="muted small" style="padding:6px 2px 0;font-variant-numeric:tabular-nums">
        #${r.rank} · cosine ${r.similarity.toFixed(3)}</div>
    </div>`;
  }).join('');

  host.querySelectorAll('.product-card').forEach((el) =>
    el.addEventListener('click', () => ctx.navigate(`/product/${el.dataset.id}`)));
}
