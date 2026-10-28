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
const SHOE_LADDER = ['EU 39', 'EU 40', 'EU 41', 'EU 42', 'EU 43', 'EU 44', 'EU 45'];

function ladderFor(cls) {
  if (cls === 'footwear') return SHOE_LADDER;
  if (cls === 'bottom') return BOTTOM_LADDER;
  return TOP_LADDER;
}

function usualSizeFor(cls, profile) {
  if (cls === 'footwear') return profile.user.sizes.shoe;
  if (cls === 'bottom') return profile.user.sizes.bottom;
  return profile.user.sizes.top;
}

export function predictReturnRisk(productId, chosenSize = null, lang = 'zh') {
  const product = getProduct(productId);
  if (!product) return null;

  const profile = getProfile();
  const { tendency, evidence } = getSizeTendency();
  const cls = garmentClass(product.subcategory);
  const fit = product.fit || { runs: 'true', stretch: 'none' };
  const ladder = ladderFor(cls);
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
  const zh = lang !== 'en';
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
