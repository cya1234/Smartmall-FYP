// lib/prophetClient.js
// Client for the Python Prophet forecasting service (ai-service/forecast_service.py).
//
// Kept as a separate process, like the CLIP service: the web tier keeps working
// when it is down, and lib/forecast.js falls back to the in-process linear model.
// Override the address with FORECAST_URL.
const BASE = (process.env.FORECAST_URL || 'http://127.0.0.1:8002').replace(/\/$/, '');

let healthCache = { at: 0, value: null };
const HEALTH_TTL_MS = 5000;

export async function prophetHealth({ force = false } = {}) {
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

export async function prophetForecast(productId, { horizon = 30 } = {}) {
  const res = await fetch(`${BASE}/forecast/${encodeURIComponent(productId)}?horizon=${horizon}`, {
    signal: AbortSignal.timeout(30000),
  });
  if (!res.ok) throw new Error(`forecast-service ${res.status}`);
  return res.json();
}

export async function prophetEval() {
  try {
    const res = await fetch(`${BASE}/eval`, { signal: AbortSignal.timeout(8000) });
    if (res.status === 404) return null;
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export function prophetBaseUrl() {
  return BASE;
}
