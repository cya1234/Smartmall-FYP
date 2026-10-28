// lib/tryon.js
// Virtual try-on. Primary path: the CatVTON service (ai-service/tryon_service.py,
// port 8003) synthesises the garment onto the shopper's photo. Fallback: the
// original metadata response, which the client renders as a coloured overlay so
// the feature degrades instead of disappearing.
import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { getProduct } from './store.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = join(__dirname, '..', 'public');
const BASE = (process.env.TRYON_URL || 'http://127.0.0.1:8003').replace(/\/$/, '');

let healthCache = { at: 0, value: null };
const HEALTH_TTL_MS = 5000;

export async function tryOnStatus({ force = false } = {}) {
  const now = Date.now();
  if (!force && healthCache.value && now - healthCache.at < HEALTH_TTL_MS) return healthCache.value;
  try {
    const res = await fetch(`${BASE}/health`, { signal: AbortSignal.timeout(2500) });
    const json = await res.json();
    healthCache = { at: now, value: json.ok ? json : null };
  } catch {
    healthCache = { at: now, value: null };
  }
  return healthCache.value;
}

function productMeta(product) {
  return {
    id: product.id,
    name: product.name,
    name_zh: product.name_zh,
    emoji: product.emoji,
    color: product.color,
    colorName: product.colorName,
    material: product.material,
    category: product.category,
    subcategory: product.subcategory,
    image: product.image || null,
  };
}

async function garmentBase64(product) {
  if (!product.image) return null;
  const file = join(PUBLIC_DIR, product.image.replace(/^\//, ''));
  if (!existsSync(file)) return null;
  const buf = await readFile(file);
  return `data:image/jpeg;base64,${buf.toString('base64')}`;
}

/**
 * @param {{productId:string, photo?:string, steps?:number, seed?:number}} args
 *   `photo` is a data URL produced by the client's file input.
 */
export async function runTryOn({ productId, photo, steps = 30, seed = 42 } = {}) {
  const product = getProduct(productId);
  if (!product) return { error: 'product not found' };

  const meta = productMeta(product);
  const health = await tryOnStatus();
  if (!health) {
    return {
      product: meta,
      status: 'unavailable',
      engine: 'overlay',
      note: 'Try-on service is offline; the client falls back to a colour overlay preview.',
    };
  }
  if (!photo) {
    return {
      product: meta,
      status: 'needs-photo',
      engine: 'catvton',
      note: 'Upload a photo to synthesise the try-on.',
    };
  }

  const garment = await garmentBase64(product);
  if (!garment) {
    return {
      product: meta,
      status: 'unavailable',
      engine: 'overlay',
      note: 'This product has no garment photo to transfer.',
    };
  }

  const res = await fetch(`${BASE}/tryon`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ person: photo, garment, steps, seed }),
    signal: AbortSignal.timeout(180000),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    return {
      product: meta,
      status: 'error',
      engine: 'catvton',
      note: `try-on service returned ${res.status}`,
      detail: text.slice(0, 200),
    };
  }
  const out = await res.json();
  return {
    product: meta,
    status: 'synthesized',
    engine: 'catvton',
    engineLabel: 'CatVTON (mask-free)',
    width: out.width,
    height: out.height,
    tookMs: out.tookMs,
    steps: out.steps,
    image: out.image,
  };
}
