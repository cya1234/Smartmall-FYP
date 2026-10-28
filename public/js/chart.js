// js/chart.js — dependency-free SVG line chart for price history + forecast.
import { currency, isZh } from './i18n.js';

export function renderPriceChart(container, history, forecast, options = {}) {
  const W = options.width || 640;
  const H = options.height || 260;
  const padL = 62;
  const padR = 18;
  const padT = 18;
  const padB = 34;

  // Server prices are in USD; convert to the active display currency.
  const cur = currency();
  const r = cur.rate;
  const sym = cur.symbol;

  const hist = history.map((h) => h.price * r);
  const fore = (forecast || []).map((f) => f.price * r);
  const all = hist.concat(fore);
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || 1;
  const pad = span * 0.18;
  const lo = Math.max(0, min - pad);
  const hi = max + pad;

  const total = hist.length + fore.length - 1; // forecast[0] conceptually continues from last hist
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const x = (i) => padL + (i / total) * innerW;
  const y = (v) => padT + (1 - (v - lo) / (hi - lo)) * innerH;

  const nHist = hist.length;
  const histPts = hist.map((v, i) => [x(i), y(v)]);
  // Forecast line starts from the last history point for continuity.
  const forePts = [[x(nHist - 1), y(hist[nHist - 1])]].concat(
    fore.map((v, i) => [x(nHist + i), y(v)]),
  );

  const polyline = (pts) => pts.map((p) => p.join(',')).join(' ');
  const area = (pts, baseY) =>
    `${pts[0][0]},${baseY} ` + pts.map((p) => p.join(',')).join(' ') + ` ${pts[pts.length - 1][0]},${baseY}`;

  // Prophet returns an 80% interval; draw it as a shaded band behind the line.
  let band = '';
  if (forecast && forecast.length && forecast.every((f) => f.lower != null && f.upper != null)) {
    const up = [[x(nHist - 1), y(hist[nHist - 1])]].concat(
      forecast.map((f, i) => [x(nHist + i), y(f.upper * r)]));
    const dn = [[x(nHist - 1), y(hist[nHist - 1])]].concat(
      forecast.map((f, i) => [x(nHist + i), y(f.lower * r)]));
    band = `<polygon points="${polyline(up)} ${polyline(dn.reverse())}" fill="rgba(255,138,102,0.18)" stroke="none"/>`;
  }

  // Y gridlines + labels
  let grid = '';
  let yLabels = '';
  const ticks = 4;
  for (let i = 0; i <= ticks; i++) {
    const v = lo + ((hi - lo) * i) / ticks;
    const yy = y(v);
    grid += `<line x1="${padL}" y1="${yy}" x2="${W - padR}" y2="${yy}" stroke="rgba(255,255,255,0.08)" stroke-width="1"/>`;
    yLabels += `<text x="${padL - 8}" y="${yy + 4}" text-anchor="end" font-size="11" fill="#9AA3B2">${sym}${v.toFixed(0)}</text>`;
  }

  // X date labels (4 evenly spaced)
  let xLabels = '';
  const dates = history.concat(forecast || []);
  const labelIdx = [0, Math.floor(total / 3), Math.floor((2 * total) / 3), total];
  for (const i of labelIdx) {
    const idx = Math.min(i, dates.length - 1);
    const d = new Date(dates[idx].t);
    const text = d.toLocaleDateString(isZh() ? 'zh-HK' : 'en-US', { month: 'short', day: 'numeric' });
    xLabels += `<text x="${x(i)}" y="${H - 10}" text-anchor="middle" font-size="11" fill="#9AA3B2">${text}</text>`;
  }

  // Marker for "now" (last history point).
  const nowX = x(nHist - 1);
  const nowY = y(hist[nHist - 1]);
  const nowMarker = `<line x1="${nowX}" y1="${padT}" x2="${nowX}" y2="${H - padB}" stroke="rgba(255,255,255,0.26)" stroke-width="1" stroke-dasharray="3 3"/><text x="${nowX}" y="${padT - 4}" text-anchor="middle" font-size="10" fill="#9AA3B2" font-weight="700">NOW</text>`;

  const svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img" aria-label="Price trend chart">
    <defs>
      <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#8B7BFF" stop-opacity="0.28"/>
        <stop offset="100%" stop-color="#8B7BFF" stop-opacity="0"/>
      </linearGradient>
    </defs>
    ${grid}
    ${yLabels}
    <polygon points="${area(histPts, H - padB)}" fill="url(#areaGrad)"/>
    ${band}
    <polyline points="${polyline(histPts)}" fill="none" stroke="#8B7BFF" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
    <polyline points="${polyline(forePts)}" fill="none" stroke="#FF8A66" stroke-width="2.5" stroke-dasharray="6 5" stroke-linejoin="round" stroke-linecap="round"/>
    <circle cx="${nowX}" cy="${nowY}" r="4.5" fill="#8B7BFF" stroke="#0A0C11" stroke-width="2"/>
    ${nowMarker}
    ${xLabels}
  </svg>`;

  container.innerHTML = svg;
}
