// lib/forecast.js
// Intelligent price forecasting service (time-series predictive analytics).
//
// Primary path: the Python Prophet service (ai-service/forecast_service.py),
// which models the retail sale calendar (雙十一, Black Friday, Christmas…) as
// explicit holiday regressors and returns a forecast plus a holdout comparison.
//
// Fallback path: the original in-process linear-regression trend model, used
// when the Prophet service is unreachable so the feature degrades rather than
// breaking. Both paths return the same JSON shape, tagged with `engine`.
import { getProduct } from './store.js';
import { prophetHealth, prophetForecast, prophetBaseUrl } from './prophetClient.js';

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

function linearRegression(points) {
  const n = points.length;
  const xs = points.map((_, i) => i);
  const ys = points.map((p) => p.price);
  const sumX = xs.reduce((a, b) => a + b, 0);
  const sumY = ys.reduce((a, b) => a + b, 0);
  const sumXY = xs.reduce((a, x, i) => a + x * ys[i], 0);
  const sumXX = xs.reduce((a, x) => a + x * x, 0);
  const denom = n * sumXX - sumX * sumX;
  if (denom === 0) return { slope: 0, intercept: sumY / n, r2: 0 };
  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;

  const meanY = sumY / n;
  const ssTot = ys.reduce((a, y) => a + (y - meanY) ** 2, 0);
  const ssRes = ys.reduce((a, y, i) => a + (y - (slope * xs[i] + intercept)) ** 2, 0);
  const r2 = ssTot === 0 ? 0 : 1 - ssRes / ssTot;
  return { slope, intercept, r2 };
}

// Public entry point: try Prophet, fall back to the linear model.
export async function forecastProduct(id, { horizon = 30 } = {}) {
  const health = await prophetHealth();
  if (health) {
    try {
      const res = await prophetForecast(id, { horizon });
      if (res && res.productId) return res;
    } catch {
      // fall through to the in-process model
    }
  }
  return linearForecast(id);
}

export function linearForecast(id) {
  const product = getProduct(id);
  if (!product) return null;

  const history = product.priceHistory;
  const last = history[history.length - 1];
  const current = last.price;
  const lastT = last.t;

  // Fit the trend on the most recent 8 weeks (more reactive to current momentum).
  const recent = history.slice(-8);
  const { slope, intercept, r2 } = linearRegression(recent);

  // Project the next 4 weeks.
  const n = history.length;
  const forecast = [];
  for (let i = 1; i <= 4; i++) {
    const predicted = intercept + slope * (n - 8 + recent.length - 1 + i);
    forecast.push({
      t: lastT + i * WEEK_MS,
      price: Math.max(1, Math.round(predicted * 100) / 100),
    });
  }

  const minForecast = Math.min(...forecast.map((f) => f.price));
  const expectedDropPct = ((current - minForecast) / current) * 100;
  const volatility = recent.reduce(
    (acc, p, i, a) => (i === 0 ? acc : acc + Math.abs(p.price - a[i - 1].price)),
    0,
  ) / Math.max(1, recent.length - 1);

  // Advisory heuristics (bilingual output).
  const DROP_THRESHOLD = 4; // percent
  let action;
  let headline;
  let headline_zh;
  let reasoning;
  let reasoning_zh;
  if (expectedDropPct >= DROP_THRESHOLD) {
    action = 'wait';
    headline = 'Wait for a Price Drop';
    headline_zh = '建議等降價';
    reasoning = `Our model projects this item's price could fall ~${expectedDropPct.toFixed(
      1,
    )}% (to about $${minForecast.toFixed(
      2,
    )}) over the next few weeks. Holding off may save you money.`;
    reasoning_zh = `模型預測這個商品在未來幾週可能下跌約 ${expectedDropPct.toFixed(
      1,
    )}%（最低約 $${minForecast.toFixed(2)}）。再等一下可能更划算。`;
  } else if (slope > 0.005) {
    action = 'buy';
    headline = 'Buy Now';
    headline_zh = '建議現在買';
    reasoning = `Prices are trending upward (≈+${(slope * 100).toFixed(
      1,
    )}%/week). Purchasing now locks in the current price before it rises.`;
    reasoning_zh = `價格呈現上升趨勢（每週約 +${(slope * 100).toFixed(
      1,
    )}%），現在購入可鎖定目前價格，避免之後漲價。`;
  } else {
    action = 'buy';
    headline = 'Buy Now — Price Is Stable';
    headline_zh = '建議現在買 — 價格穩定';
    reasoning =
      'The price has been stable with no meaningful drop projected, so waiting is unlikely to save you money.';
    reasoning_zh = '價格一直很穩定，也沒有明顯的降價訊號，繼續等待通常省不到錢。';
  }

  // Confidence: combine regression fit quality with how noisy the series is.
  const fitScore = Math.max(0, Math.min(1, r2));
  const noisePenalty = Math.max(0, Math.min(1, volatility / (current * 0.02)));
  const confidenceScore = Math.max(0.3, Math.min(0.95, fitScore * 0.8 + (1 - noisePenalty) * 0.2));
  const confidence =
    confidenceScore > 0.66 ? 'High' : confidenceScore > 0.5 ? 'Medium' : 'Low';

  const trendDirection = slope < -0.002 ? 'falling' : slope > 0.002 ? 'rising' : 'stable';

  return {
    engine: 'linear',
    engineLabel: 'Linear trend (Prophet service offline)',
    serviceUrl: prophetBaseUrl(),
    productId: id,
    current,
    currency: product.currency,
    horizonDays: 28,
    trend: {
      direction: trendDirection,
      weeklyChangePct: Math.round(slope * 10000) / 100,
    },
    history: history.map((h) => ({ t: h.t, price: h.price })),
    forecast,
    events: [],
    advisory: {
      action, // 'buy' | 'wait'
      headline,
      headline_zh,
      reasoning,
      reasoning_zh,
      expectedDropPct: Math.round(expectedDropPct * 10) / 10,
      confidence,
      confidence_zh: confidence === 'High' ? '高' : confidence === 'Medium' ? '中' : '低',
      confidenceScore: Math.round(confidenceScore * 100) / 100,
    },
  };
}
