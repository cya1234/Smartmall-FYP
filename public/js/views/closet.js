// js/views/closet.js — the shopper's virtual closet.
//
// Everything the customer has bought appears here as a garment they can try on
// again at any time. The photo is uploaded once and remembered in the browser, so
// a second try-on is a single click rather than a repeat of the whole flow.
import { getJSON } from '../api.js';
import { esc, t, isZh, mediaInner, toast } from '../ui.js';
import { loadPhoto, clearPhoto, storeFile } from '../closetPhoto.js';

const CONDITION_KEY = { good: 'closet.condGood', fair: 'closet.condFair', worn: 'closet.condWorn' };

export async function render(root, ctx) {
  root.innerHTML = `<section class="container"><div class="card">${esc(t('common.loading'))}</div></section>`;

  let data;
  try {
    data = await getJSON('/api/profile');
  } catch {
    root.innerHTML = `<section class="container"><div class="card">${esc(t('common.retry'))}</div></section>`;
    return;
  }

  const owned = (data.wardrobe || [])
    .map((w) => ({ ...w, product: ctx.products.find((p) => p.id === w.productId) || null }))
    .filter((w) => w.product);

  const photo = loadPhoto();

  root.innerHTML = `
    <section class="container">
      <div class="page-head">
        <div>
          <h1 class="section-title">🚪 ${esc(t('closet.title'))}</h1>
          <p class="section-sub" style="margin-bottom:0">${esc(t('closet.sub'))}</p>
        </div>
        <button class="btn ${photo ? 'btn-ghost' : 'btn-primary'}" id="closet-photo">
          📷 ${esc(photo ? t('closet.changePhoto') : t('closet.addPhoto'))}
        </button>
        <input type="file" id="closet-file" accept="image/*" class="hidden" />
      </div>

      <div class="pickup-strip">
        <span>👕 <strong>${owned.length}</strong> ${esc(t('closet.owned'))}</span>
        <span>${photo ? '✅ ' + esc(t('closet.photoReady')) : '🖼️ ' + esc(t('closet.photoMissing'))}</span>
        <span>${esc(t('closet.hint'))}</span>
      </div>

      ${photo ? `
      <div class="card" style="margin-top:16px;display:flex;gap:16px;align-items:center;flex-wrap:wrap">
        <img src="${photo}" alt="" style="width:84px;height:104px;object-fit:cover;border-radius:12px;border:1px solid var(--line)" />
        <div style="flex:1;min-width:200px">
          <strong>${esc(t('closet.photoTitle'))}</strong>
          <p class="muted small" style="margin:4px 0 0">${esc(t('closet.photoNote'))}</p>
          <button class="btn btn-ghost btn-sm" id="closet-clear" style="margin-top:8px">${esc(t('closet.removePhoto'))}</button>
        </div>
      </div>` : ''}

      <div class="grid" style="margin-top:18px;grid-template-columns:repeat(auto-fill,minmax(210px,1fr))">
        ${owned.map((w) => {
          const p = w.product;
          const cond = CONDITION_KEY[w.condition] || 'closet.condGood';
          return `<article class="hero-card" style="padding:14px;cursor:default">
            <div style="height:150px;border-radius:12px;background:var(--surface-2);display:flex;align-items:center;justify-content:center;overflow:hidden">
              ${mediaInner(p, '2.6rem')}
            </div>
            <h3 style="margin:10px 0 2px;font-size:0.98rem">${esc(isZh() ? (p.name_zh || p.name) : p.name)}</h3>
            <p class="muted small" style="margin:0 0 8px">
              ${esc(w.size || '—')} · ${w.monthsAgo} ${esc(t('closet.monthsAgo'))}
            </p>
            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px">
              <span class="badge ${w.condition === 'fair' || w.condition === 'worn' ? 'badge-warn' : 'badge-good'}">
                ${esc(t(cond))}
              </span>
              <span class="badge badge-info">${w.wears || 0} ${esc(t('closet.wore'))}</span>
            </div>
            <div style="display:flex;gap:8px">
              <button class="btn btn-primary btn-sm" data-try="${esc(p.id)}" style="flex:1">
                ${esc(t('closet.tryOn'))}
              </button>
              <button class="btn btn-ghost btn-sm" data-open="${esc(p.id)}">${esc(t('closet.detail'))}</button>
            </div>
          </article>`;
        }).join('')}
      </div>

      ${owned.length ? '' : `<div class="card" style="margin-top:18px">${esc(t('closet.empty'))}</div>`}
    </section>
  `;

  const fileInput = root.querySelector('#closet-file');

  root.querySelector('#closet-photo').addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', async () => {
    if (!fileInput.files.length) return;
    try {
      await storeFile(fileInput.files[0]);
      toast(isZh() ? '照片已儲存，之後一鍵就能試穿' : 'Photo saved — try on in one click');
      render(root, ctx);
    } catch {
      toast(isZh() ? '請選擇圖片檔' : 'Please choose an image');
    }
  });

  const clearBtn = root.querySelector('#closet-clear');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      clearPhoto();
      toast(isZh() ? '已移除照片' : 'Photo removed');
      render(root, ctx);
    });
  }

  root.querySelectorAll('[data-try]').forEach((b) =>
    b.addEventListener('click', () => {
      ctx.state.tryonProduct = b.dataset.try;
      ctx.navigate('/tryon');
    }));

  root.querySelectorAll('[data-open]').forEach((b) =>
    b.addEventListener('click', () => ctx.navigate(`/product/${b.dataset.open}`)));
}
