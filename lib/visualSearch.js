// lib/visualSearch.js
// Multimodal visual search engine.
//
// Primary path: CLIP + FAISS. A query image (and/or a text modifier) is encoded
// into CLIP's shared 512-d space and matched against the product-photo index by
// cosine similarity. When both an image and text are supplied the two unit
// vectors are fused into a single unified query embedding, which is exactly the
// "feature fusion" step described in the project proposal.
//
// Fallback path: if the Python inference service is unreachable the original
// colour-distance heuristic runs instead, so the feature degrades rather than
// breaking. Swap in any other cross-modal encoder by changing only this file.
import { getProducts } from './store.js';
import { clipHealth, clipSearch, clipBaseUrl, scoreToPercent } from './clipClient.js';

// --- colour-heuristic fallback --------------------------------------------
function hexToRgb(hex) {
  const h = hex.replace('#', '');
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
  return [parseInt(full.slice(0, 2), 16), parseInt(full.slice(2, 4), 16), parseInt(full.slice(4, 6), 16)];
}

function colorDistance(hexA, hexB) {
  const [r1, g1, b1] = hexToRgb(hexA);
  const [r2, g2, b2] = hexToRgb(hexB);
  return Math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2);
}

const MAX_DIST = Math.sqrt(3 * 255 * 255);

function textScore(product, query) {
  const q = (query || '').toLowerCase().trim();
  if (!q) return 0;
  let s = 0;
  const hay = `${product.name} ${product.name_zh || ''} ${product.description} ${product.tags.join(' ')} ${product.subcategory} ${product.category} ${product.colorName} ${product.material}`.toLowerCase();
  const tokens = q.split(/[^a-z0-9\u4e00-\u9fff]+/).filter((t) => t.length > 1);
  for (const t of tokens) if (hay.includes(t)) s += 1.6;
  if (hay.includes(q)) s += 3;
  return s;
}

function colourSearch({ colors, query, limit }) {
  const hasColors = Array.isArray(colors) && colors.length > 0;
  const q = (query || '').toLowerCase();

  const ranked = getProducts()
    .map((product) => {
      let colorSim = 0;
      if (hasColors) {
        const distances = colors.map((c) => colorDistance(c.hex || c, product.color));
        colorSim = 1 - Math.min(...distances) / MAX_DIST;
      }
      const tScore = textScore(product, q);
      const score = hasColors ? colorSim + tScore * 0.25 : tScore;
      const reasons = [];
      if (hasColors && colorSim > 0.62) reasons.push('colour_close');
      if (tScore > 0) reasons.push('text_match');
      return { product, score, colorSim, reasons };
    })
    .sort((a, b) => b.score - a.score);

  return ranked.slice(0, limit).map((r) => ({
    id: r.product.id,
    similarity: Math.round(r.colorSim * 100) / 100,
    matchPercent: Math.round(r.colorSim * 100),
    colorSimilarity: Math.round(r.colorSim * 100) / 100,
    reasons: r.reasons,
  }));
}

// --- main entry point ------------------------------------------------------
export async function runVisualSearch({ colors = [], query = '', image = null, limit = 12 } = {}) {
  const productIds = new Set(getProducts().map((p) => p.id));
  const health = image || query ? await clipHealth() : null;

  if (health) {
    try {
      const res = await clipSearch({ text: query || null, image: image || null, k: Math.max(limit, 12) });
      const results = (res.results || [])
        .filter((r) => productIds.has(r.id))
        .slice(0, limit)
        .map((r, i) => ({
          id: r.id,
          rank: i + 1,
          similarity: r.score,
          matchPercent: scoreToPercent(r.score, health.dim || 512),
          reasons: [
            res.mode.includes('image') ? 'visual_similarity' : 'text_semantics',
            ...(res.mode === 'image+text' ? ['fused_query'] : []),
          ],
        }));

      if (results.length) {
        return {
          engine: 'clip',
          engineLabel: `CLIP ${health.model} · FAISS`,
          model: health.model,
          pretrained: health.pretrained,
          device: health.device,
          gpu: health.gpu,
          indexed: health.indexed,
          mode: res.mode,
          fusion: res.fusion,
          textWeight: res.textWeight,
          imageSize: res.imageSize,
          tookMs: res.tookMs,
          colors: colors.map((c) => (typeof c === 'string' ? { hex: c } : c)),
          query,
          results,
        };
      }
    } catch (err) {
      // fall through to the heuristic
    }
  }

  return {
    engine: 'colour',
    engineLabel: 'Colour heuristic (AI service offline)',
    serviceUrl: clipBaseUrl(),
    colors: colors.map((c) => (typeof c === 'string' ? { hex: c } : c)),
    query,
    results: colourSearch({ colors, query, limit }),
  };
}

export async function visualSearchStatus() {
  const h = await clipHealth();
  return h
    ? { online: true, ...h, url: clipBaseUrl() }
    : { online: false, url: clipBaseUrl() };
}
