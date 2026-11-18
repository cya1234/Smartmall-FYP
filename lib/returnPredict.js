// lib/returnPredict.js
// Return-reason prediction & size advisor.
//
// Before purchase, combines the shopper's body data and past return records
// with the garment's own fit profile (runs small/large, fabric stretch) to
// predict return probability and recommend a size — the "this runs large, size
// down to cut your return odds" advisory. A production deployment would train a
// gradient-boosted or neural model on order-level data; the input features and
// the output contract (risk + recommended size + reasons) stay the same.
import { getProduct, getProfile } from './store.js';
import { garmentClass, getSizeTendency } from './memory.js';

const TOP_LADDER = ['XS', 'S', 'M', 'L', 'XL', 'XXL'];
const BOTTOM_LADDER = ['XS', 'S', 'M', 'L', 'XL', 'XXL'];
// Hats, gloves, socks: a short ladder, because XS-XXL on a beanie is nonsense.
const SMALL_LADDER = ['S', 'M', 'L', 'XL'];

// Footwear is sized the Hong Kong way: the EU/Asian number is what shops here quote,
// with the foot length in cm as the thing you actually measure. UK and US are shown
// only as approximations, because they differ between men's and women's lasts and a
// single unisex table would be wrong for half the catalogue.
// Sources: Charles & Keith HK ("Asian/European sizing") and the HK sneaker charts.
const HK_SHOE_SIZES = [
  { label: '36', cm: 22.7, uk: '3.5' },
  { label: '37', cm: 23.3, uk: '4' },
  { label: '38', cm: 24.0, uk: '5' },
  { label: '39', cm: 24.6, uk: '6' },
  { label: '40', cm: 25.3, uk: '6.5' },
  { label: '41', cm: 25.9, uk: '7.5' },
  { label: '42', cm: 26.6, uk: '8' },
  { label: '43', cm: 27.2, uk: '9' },
  { label: '44', cm: 27.9, uk: '9.5' },
  { label: '45', cm: 28.5, uk: '10.5' },
  { label: '46', cm: 29.2, uk: '11' },
];
const SHOE_LADDER = HK_SHOE_SIZES.map((s) => s.label);

// Categories that never have a size. Electronics is hardware; Home and Beauty are
// not garments. A size selector on a pair of earbuds is a bug, not a feature.
const NEVER_SIZEABLE_CATEGORIES = new Set(['Electronics', 'Home', 'Beauty']);

// Subcategories inside Apparel/Accessories that do have a size.
const SIZEABLE_SUBCATEGORIES = new Set([
  'Shirt', 'Sweater', 'Jacket', 'Blazer', 'Dress', 'Ski Jacket', 'Base Layer', 'Fleece',
  'Trousers', 'Ski Pants',
  'Shoes', 'Sandals', 'Boots', 'Snow Boots',
  'Hat', 'Beanie', 'Gloves', 'Socks', 'Neck Gaiter',
]);

/** Does this product have a size to choose at all? */
export function isSizeable(product) {
  if (!product) return false;
  if (NEVER_SIZEABLE_CATEGORIES.has(product.category)) return false;
  return SIZEABLE_SUBCATEGORIES.has(product.subcategory);
}

function ladderFor(cls) {
  if (cls === 'footwear') return SHOE_LADDER;
  if (cls === 'bottom') return BOTTOM_LADDER;
  if (cls === 'headwear' || cls === 'accessory') return SMALL_LADDER;
  return TOP_LADDER;
}

/** Per-size detail for the picker: the label plus, for shoes, cm and the UK equivalent. */
function sizesFor(cls) {
  if (cls === 'footwear') {
    return HK_SHOE_SIZES.map((s) => ({ label: s.label, cm: s.cm, uk: s.uk }));
  }
  return ladderFor(cls).map((label) => ({ label }));
}

function sizeNoteFor(cls, zh) {
  if (cls === 'footwear') {
    return zh
      ? '香港慣用歐碼（EU／亞洲碼），量腳長（cm）對照選碼。'
      : 'Sized the Hong Kong way — the EU/Asian number shops here quote. Measure your foot in cm to pick.';
  }
  if (cls === 'headwear' || cls === 'accessory') {
    return zh ? '單一碼數，選 S–XL。' : 'Single sizing, S–XL.';
  }
  return zh ? '標準尺碼。' : 'Standard sizing.';
}

function usualSizeFor(cls, profile) {
  const raw = cls === 'footwear' ? profile.user.sizes.shoe
    : cls === 'bottom' ? profile.user.sizes.bottom
      : profile.user.sizes.top;
  // Older profiles stored "EU 41"; the ladder is now just the number.
  return String(raw || '').replace(/^EU\s*/i, '');
}

export function predictReturnRisk(productId, chosenSize = null, lang = 'zh') {
  const product = getProduct(productId);
  if (!product) return null;

  const profile = getProfile();
  const { tendency, evidence } = getSizeTendency();
  const cls = garmentClass(product.subcategory);
  const fit = product.fit || { runs: 'true', stretch: 'none' };
  const zh = lang !== 'en';

  // Products with no size get their own answer: showing a size picker on a pair of
  // earbuds (or pretending to recommend one) is worse than saying "one size".
  if (!isSizeable(product)) {
    const risk = Math.max(3, Math.min(92, Math.round(product.returnRate || 6)));
    return {
      productId,
      product: {
        id: product.id, name: product.name, name_zh: product.name_zh,
        emoji: product.emoji, color: product.color,
      },
      sizeClass: 'none',
      sizeable: false,
      sizes: [],
      usualSize: null,
      recommendedSize: null,
      chosenSize: null,
      riskScore: risk,
      riskIfFollowed: risk,
      riskLevel: risk < 12 ? 'low' : risk < 25 ? 'medium' : 'high',
      factors: [{ key: 'no_size', weight: 0 }],
      advice: zh
        ? '這件是單一規格，不需要選尺碼。'
        : 'One specification, no size to choose.',
      bodyNote: '',
      stretch: fit.stretch || 'none',
      runs: 'n/a',
      confidence: 0.9,
    };
  }

  const ladder = ladderFor(cls);
  const sizes = sizesFor(cls);
  const sizeNote = sizeNoteFor(cls, zh);
  const usual = usualSizeFor(cls, profile);
  const baseIdx = Math.max(0, ladder.indexOf(usual));
  const chosen = chosenSize && ladder.includes(chosenSize) ? chosenSize : usual;

  const factors = [];

  // --- Size recommendation -------------------------------------------------
  // The garment's own fit profile dominates; learned history only reinforces it
  // (or overrides it when the shopper's record is strong).
  const productDelta = fit.runs === 'small' ? 1 : fit.runs === 'large' ? -1 : 0;
  if (fit.runs === 'small') factors.push({ key: 'runs_small', weight: 1 });
  if (fit.runs === 'large') factors.push({ key: 'runs_large', weight: 1 });

  const userTend = tendency[cls] || 0;
  const learnedDelta = userTend >= 2 ? 0.5 : userTend <= -1 ? -0.5 : 0;
  const reinforces = learnedDelta !== 0 && Math.sign(learnedDelta) === Math.sign(productDelta);
  const strongHistory = Math.abs(userTend) >= 3;
  const applyLearned = learnedDelta !== 0 && (reinforces || strongHistory);
  if (applyLearned) factors.push({ key: learnedDelta > 0 ? 'learned_size_up' : 'learned_size_down', weight: 0.5 });

  let delta = productDelta + (applyLearned ? learnedDelta : 0);
  if (fit.stretch === 'high') { delta *= 0.5; factors.push({ key: 'forgiving_fabric', weight: 0 }); }

  // Never move more than one size from the shopper's usual.
  const step = Math.sign(delta) * Math.min(1, Math.max(0, Math.round(Math.abs(delta))));
  const recIdx = Math.min(ladder.length - 1, Math.max(0, baseIdx + step));
  const recommendedSize = ladder[recIdx];

  // --- Risk model ----------------------------------------------------------
  let risk = product.returnRate;

  if (recommendedSize !== chosen) {
    risk += 16;
    factors.push({ key: 'size_mismatch', weight: 16 });
  }
  if (fit.runs === 'small' && userTend > 0) { risk += 7; factors.push({ key: 'small_and_burned', weight: 7 }); }
  if (fit.runs === 'large' && userTend < 0) { risk += 6; factors.push({ key: 'large_and_burned', weight: 6 }); }
  if (fit.stretch === 'none' && fit.runs !== 'true') { risk += 5; factors.push({ key: 'no_stretch', weight: 5 }); }

  // Same brand returned before?
  const brandReturn = evidence[cls]?.find((e) => e.product.brand === product.brand);
  if (brandReturn) { risk += 6; factors.push({ key: 'brand_history', weight: 6 }); }

  // Colour the shopper dislikes.
  if ((profile.user.dislikedColors || []).includes(product.colorName)) {
    risk += 5;
    factors.push({ key: 'colour_mismatch', weight: 5 });
  }

  risk = Math.max(3, Math.min(92, Math.round(risk)));

  // Risk if the shopper follows the recommendation.
  const riskIfFollowed = Math.max(3, Math.round(risk - (recommendedSize !== chosen ? 15 : 0)
    - (fit.runs !== 'true' && userTend !== 0 ? 5 : 0)));

  const level = risk < 12 ? 'low' : risk < 25 ? 'medium' : 'high';

  // --- Advice --------------------------------------------------------------
  const sizeWord = { small: zh ? '偏小' : 'runs small', large: zh ? '偏大' : 'runs large', true: zh ? '正常' : 'true to size' }[fit.runs];
  let advice;
  if (recommendedSize !== chosen) {
    const dir = step > 0 ? (zh ? '大一號' : 'one size up') : (zh ? '小一號' : 'one size down');
    advice = zh
      ? `這件版型${sizeWord}${userTend !== 0 ? '，加上你過去的退貨紀錄' : ''}，建議選${dir}（${recommendedSize}），可將預估退貨機率由 ${risk}% 降至約 ${riskIfFollowed}%。`
      : `This runs ${fit.runs === 'large' ? 'large' : 'small'}${userTend !== 0 ? ' and your return history agrees' : ''}. Size ${dir} (${recommendedSize}) to cut the predicted return risk from ${risk}% to about ${riskIfFollowed}%.`;
  } else if (fit.runs === 'true') {
    advice = zh
      ? `這件版型正常${fit.stretch === 'high' ? '且布料有彈性' : ''}，你平常的 ${usual} 號即可，預估退貨機率僅 ${risk}%。`
      : `True to size${fit.stretch === 'high' ? ' with a stretchy fabric' : ''}. Your usual ${usual} is right — predicted return risk is only ${risk}%.`;
  } else {
    advice = zh
      ? `這件版型${sizeWord}，但你的身型與穿著習慣適合 ${recommendedSize} 號，預估退貨機率 ${risk}%。`
      : `This runs ${fit.runs}, but ${recommendedSize} suits your measurements. Predicted return risk ${risk}%.`;
  }

  // Body-data summary used in the explanation.
  const bodyNote = zh
    ? `依你的身高 ${profile.user.body.height}cm / 體重 ${profile.user.body.weight}kg / 胸圍 ${profile.user.body.chest}cm 推算`
    : `Estimated from your height ${profile.user.body.height}cm, weight ${profile.user.body.weight}kg, chest ${profile.user.body.chest}cm`;

  return {
    productId,
    product: { id: product.id, name: product.name, name_zh: product.name_zh, emoji: product.emoji, color: product.color },
    sizeClass: cls,
    sizeable: true,
    sizes,
    sizeNote,
    usualSize: usual,
    recommendedSize,
    chosenSize: chosen,
    riskScore: risk,
    riskIfFollowed,
    riskLevel: level,
    factors,
    advice,
    bodyNote,
    stretch: fit.stretch,
    runs: fit.runs,
    confidence: Math.min(0.94, 0.62 + Math.min(0.28, (evidence[cls]?.length || 0) * 0.09)),
  };
}

export function predictCartRisk(items = [], lang = 'zh') {
  const results = items
    .map((it) => predictReturnRisk(it.productId, it.size, lang))
    .filter(Boolean);
  if (!results.length) return { items: [], overall: null };
  const top = results.slice().sort((a, b) => b.riskScore - a.riskScore)[0];
  const avg = Math.round(results.reduce((s, r) => s + r.riskScore, 0) / results.length);
  return {
    items: results,
    overall: {
      averageRisk: avg,
      level: avg < 12 ? 'low' : avg < 25 ? 'medium' : 'high',
      highestRiskItem: top,
      adviceCount: results.filter((r) => r.recommendedSize !== r.chosenSize).length,
    },
  };
}
