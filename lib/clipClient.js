// lib/clipClient.js
// Thin client for the Python CLIP inference service (ai-service/visual_search_service.py).
//
// The AI service is a separate process on purpose: the web tier keeps working
// when it is down, and lib/visualSearch.js falls back to the colour heuristic.
// Override the address with VISUAL_SEARCH_URL.
const BASE = (process.env.VISUAL_SEARCH_URL || 'http://127.0.0.1:8001').replace(/\/$/, '');

let healthCache = { at: 0, value: null };
const HEALTH_TTL_MS = 5000;

async function post(path, payload, timeoutMs) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!res.ok) throw new Error(`ai-service ${res.status}`);
  return res.json();
}

// Probe the service, caching the result briefly so we do not hit it per request.
export async function clipHealth({ force = false } = {}) {
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

export async function clipSearch({ text = null, image = null, k = 12, textWeight = null } = {}) {
  const payload = { k };
  if (text) payload.text = text;
  if (image) payload.image = image;
  if (textWeight != null) payload.textWeight = textWeight;
  return post('/search', payload, 30000);
}

export function clipBaseUrl() {
  return BASE;
}

// Map a raw cosine similarity onto a readable 0-100 "match" figure. The band
// differs by backbone: CLIP-style models put correct matches around 0.20-0.35,
// while SigLIP (sigmoid objective) compresses everything into roughly
// -0.06..0.09 with the median slightly negative. Measured on this catalogue:
// SigLIP p50 = -0.016, p90 = 0.036, p99 = 0.094. The lower bound sits just
// below the median so that weak-but-correct occasion queries (e.g.
// "去海島婚禮穿什麼") are not rounded down to 1%.
export function scoreToPercent(score, dim = 512) {
  const [LO, HI] = dim >= 768 ? [-0.02, 0.08] : [0.10, 0.35];
  const pct = ((score - LO) / (HI - LO)) * 100;
  return Math.max(1, Math.min(99, Math.round(pct)));
}
