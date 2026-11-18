// lib/aesthetic.js
// Fashion AesRec score: "is today's outfit beautiful, and is it *you*?"
//
// The scoring runs in the CLIP service because that is where the fashion encoder
// already lives — the same embedding space the visual search uses. Two of the three
// signals are therefore grounded in the shopper's own wardrobe rather than a generic
// taste model:
//
//   style    cosine between the outfit photo and the centroid of the items they
//            actually bought — this is the "matches your regular style" half
//   coverage how complete the look is (top / bottom / shoes, plus outerwear)
//   palette  hue spread and neutral balance, read from the pixels
//
// A VLM judge (StyleTailor's "VLM Artist") would add Design / Fitness / Coherence /
// Mood sub-scores, but a 7B vision model does not fit beside CatVTON on a 12 GB card,
// and an unvalidated LLM score is a vibe, not a benchmark. The deterministic judge is
// reproducible and can be checked against human ratings; see tools/eval_aesthetic.py.
import { getMemoryContext } from './memory.js';
import { getProducts } from './store.js';

const BASE = process.env.VISUAL_SEARCH_URL || 'http://127.0.0.1:8001';
const TIMEOUT_MS = 60000;

export async function aestheticStatus() {
  try {
    const res = await fetch(`${BASE}/health`, { signal: AbortSignal.timeout(4000) });
    if (!res.ok) return { online: false };
    const j = await res.json();
    return { online: true, model: j.model, device: j.device, indexed: j.indexed };
  } catch {
    return { online: false };
  }
}

const VERDICT_TEXT = {
  excellent: { zh: '很襯你', en: 'Really suits you' },
  good: { zh: '不錯', en: 'Works well' },
  fair: { zh: '尚可', en: 'Fair' },
  adjust: { zh: '可以再調整', en: 'Needs adjusting' },
};

export function verdictLabel(verdict, lang = 'zh') {
  const v = VERDICT_TEXT[verdict] || VERDICT_TEXT.fair;
  return lang === 'zh' ? v.zh : v.en;
}

/** Score one outfit photo. Returns {online:false} when the service is down. */
export async function scoreOutfit(imageB64, { lang = 'zh' } = {}) {
  const ctx = getMemoryContext();
  const wardrobeIds = (ctx.wardrobe || []).map((w) => w.productId).filter(Boolean);

  let body;
  try {
    const res = await fetch(`${BASE}/aesthetic`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: imageB64, wardrobeIds }),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!res.ok) return { online: false, reason: `http_${res.status}` };
    body = await res.json();
  } catch (err) {
    return { online: false, reason: err.name === 'TimeoutError' ? 'timeout' : 'offline' };
  }
  if (!body || body.error) return { online: false, reason: body?.error || 'bad_response' };

  // Attach human-readable names for the owned items the outfit is closest to.
  const products = getProducts();
  const byId = new Map(products.map((p) => [p.id, p]));
  const closest = (body.detail?.closestOwned || []).map((c) => {
    const p = byId.get(c.id);
    return {
      id: c.id,
      similarity: c.similarity,
      name: p ? p.name : c.id,
      name_zh: p ? p.name_zh || p.name : c.id,
      image: p ? p.image || null : null,
      emoji: p ? p.emoji || '🛍️' : '🛍️',
    };
  });

  // Reasons are generated here, not in the model, so every claim points at a number.
  const reasons = [];
  const s = body.subscores || {};
  if (s.style >= 70) reasons.push({ kind: 'good', key: 'style.high', value: s.style });
  else if (s.style < 45) reasons.push({ kind: 'warn', key: 'style.low', value: s.style });
  else reasons.push({ kind: 'neutral', key: 'style.mid', value: s.style });

  if (s.coverage >= 66) reasons.push({ kind: 'good', key: 'coverage.full', value: s.coverage });
  else reasons.push({ kind: 'warn', key: 'coverage.partial', value: s.coverage });

  if (s.palette >= 70) reasons.push({ kind: 'good', key: 'palette.good', value: s.palette });
  else reasons.push({ kind: 'warn', key: 'palette.scattered', value: s.palette });

  return {
    online: true,
    score: body.score,
    // A second number measured against a generic taste anchor instead of the
    // shopper's wardrobe. The A/B experiment compares these two.
    publicScore: body.publicScore,
    publicSubscores: body.publicSubscores,
    verdict: body.verdict,
    verdictLabel: verdictLabel(body.verdict, lang),
    subscores: body.subscores,
    detail: { ...body.detail, closestOwned: closest },
    weights: body.weights,
    reasons,
    judge: body.judge,
    tookMs: body.tookMs,
  };
}
