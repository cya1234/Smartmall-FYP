// js/closetPhoto.js
// Remember the shopper's try-on photo so a garment can be tried on in one click.
//
// localStorage is only ~5 MB, so a phone photo is downscaled to 720 px on the
// long edge and re-encoded as JPEG before it is stored (~120 KB instead of 4 MB).
// The photo never leaves the browser: the try-on request sends it directly to the
// local service, and nothing is persisted on the server.
const KEY = 'smartmall-closet-photo';
const MAX_SIDE = 720;
const QUALITY = 0.82;

export function loadPhoto() {
  try {
    return localStorage.getItem(KEY) || null;
  } catch {
    return null;
  }
}

export function savePhoto(dataUrl) {
  try {
    localStorage.setItem(KEY, dataUrl);
    return true;
  } catch {
    // Quota exceeded or private mode: the feature still works for this page view.
    return false;
  }
}

export function clearPhoto() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

/** Draw an <img> onto a canvas and return a compressed data URL. */
export function toStorableDataUrl(img, maxSide = MAX_SIDE, quality = QUALITY) {
  const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(img.width * scale));
  canvas.height = Math.max(1, Math.round(img.height * scale));
  const c = canvas.getContext('2d');
  c.fillStyle = '#ffffff';
  c.fillRect(0, 0, canvas.width, canvas.height);
  c.drawImage(img, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/jpeg', quality);
}

/** Read a File, downscale it, store it, and hand the data URL back. */
export function storeFile(file) {
  return new Promise((resolve, reject) => {
    if (!file || !file.type.startsWith('image/')) {
      reject(new Error('not an image'));
      return;
    }
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('read failed'));
    reader.onload = (e) => {
      const img = new Image();
      img.onerror = () => reject(new Error('decode failed'));
      img.onload = () => {
        const url = toStorableDataUrl(img);
        savePhoto(url);
        resolve(url);
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
}
