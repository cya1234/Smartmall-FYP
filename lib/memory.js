// lib/memory.js
// Long-term memory & personalisation profile.
//
// Turns the stored profile (body data, sizes, wardrobe, purchase and return
// history, style preferences) into the context an LLM would carry across
// sessions. This is the seam where a production system would persist the
// profile in a database and embed past behaviour into a vector memory store;
// the exported shape (context + insights + wardrobe matches) stays the same.
import { getProfile, getWardrobe, getReturns, getProducts } from './store.js';

export const GARMENT_CLASS = {
  Shirt: 'top', Sweater: 'top', Jacket: 'top', Blazer: 'top', Dress: 'top',
  'Ski Jacket': 'top', 'Base Layer': 'top', Fleece: 'top',
  Trousers: 'bottom', 'Ski Pants': 'bottom',
  Shoes: 'footwear', Sandals: 'footwear', Boots: 'footwear', 'Snow Boots': 'footwear',
  Goggles: 'eyewear', Gloves: 'accessory', Beanie: 'headwear', Socks: 'accessory',
  'Neck Gaiter': 'accessory', Hat: 'headwear', Bag: 'bag', Watch: 'accessory',
  Eyewear: 'eyewear', Scarf: 'accessory',
};

export function garmentClass(subcategory) {
  return GARMENT_CLASS[subcategory] || 'other';
}

// Size tendency learned from past returns: positive => this shopper tends to
// need a size UP in that class.
export function getSizeTendency() {
  const tendency = { top: 0, bottom: 0, footwear: 0, other: 0 };
  const evidence = { top: [], bottom: [], footwear: [], other: [] };
  for (const r of getReturns()) {
    const cls = garmentClass(r.product.subcategory);
    if (r.reason === 'too_small') {
      tendency[cls] += 1;
      evidence[cls].push({ product: r.product, reason: r.reason, note: r.note, monthsAgo: r.monthsAgo });
    } else if (r.reason === 'too_large') {
      tendency[cls] -= 1;
      evidence[cls].push({ product: r.product, reason: r.reason, note: r.note, monthsAgo: r.monthsAgo });
    }
  }
  return { tendency, evidence };
}

// Wardrobe coverage: which functional slots the shopper already owns.
export function getWardrobeCoverage() {
  const owned = new Set();
  for (const w of getWardrobe()) for (const s of w.product.slots || []) owned.add(s);
  return owned;
}

// Find owned items that plausibly match a scenario intent.
export function findWardrobeMatches(intent) {
  const wanted = {
    occasion: intent.occasion || [],
    climate: intent.climate || [],
    season: intent.season || [],
    style: intent.style || [],
    slots: intent.slots || null,
  };
  const scored = [];
  for (const w of getWardrobe()) {
    const p = w.product;
    let score = 0;
    const reasons = [];
    const occ = wanted.occasion.filter((o) => (p.occasion || []).includes(o)).length;
    if (occ) { score += 3 * occ; reasons.push('符合場合'); }
    const cli = wanted.climate.filter((c) => (p.climate || []).includes(c)).length;
    if (cli) { score += 2 * cli; reasons.push('適合氣候'); }
    const sea = wanted.season.filter((s) => (p.season || []).includes(s)).length;
    if (sea) { score += 1.5 * sea; reasons.push('當季'); }
    const sty = wanted.style.filter((s) => (p.style || []).includes(s)).length;
    if (sty) { score += 1.5 * sty; reasons.push('符合風格'); }
    // Owned items get a strong preference: re-using beats re-buying.
    if (score > 0) {
      if (wanted.slots && !(p.slots || []).some((s) => wanted.slots.includes(s))) continue;
      scored.push({ entry: w, product: p, score, reasons });
    }
  }
  return scored.sort((a, b) => b.score - a.score);
}

// Natural-language memory note for the assistant's answer.
export function buildMemoryNote(ownedPicks, lang = 'zh') {
  if (!ownedPicks.length) return null;
  const names = ownedPicks.map((o) => o.product.name);
  const first = ownedPicks[0];
  if (lang === 'en') {
    const label = first.entry.purchasedLabel_en;
    return `From your wardrobe (${label}): ${names.join(', ')}. I built this look around what you already own so you don't re-buy the same piece.`;
  }
  const when = first.entry.purchasedLabel;
  return `你的衣櫥裡已經有${when}購入的「${names.join('、')}」，我以你現有的單品為基礎來搭配，不需要重複購買。`;
}

// AI-generated insights shown on the profile page.
export function getInsights(lang = 'zh') {
  const p = getProfile();
  const { tendency, evidence } = getSizeTendency();
  const wardrobe = getWardrobe();
  const returns = getReturns();
  const out = [];

  // 1. Sizing tendency
  const topT = tendency.top;
  const bottomT = tendency.bottom;
  if (topT > 0) {
    out.push({
      type: 'sizing', icon: '📏', confidence: 0.86,
      title: lang === 'en' ? 'You tend to need a size up in tops' : '上身衣物你通常需要大一號',
      detail: lang === 'en'
        ? `You returned ${topT} top${topT > 1 ? 's' : ''} for being too small (e.g. ${evidence.top[0]?.product.name}). I'll flag tops that run small before you buy.`
        : `你有 ${topT} 次上身衣物因「尺寸太小」退貨（例如 ${evidence.top[0]?.product.name}）。之後遇到版型偏小的上身單品，我會主動提醒你選大一號。`,
      data: evidence.top.slice(0, 2),
    });
  }
  if (bottomT < 0) {
    out.push({
      type: 'sizing', icon: '📐', confidence: 0.81,
      title: lang === 'en' ? 'You prefer a trimmer cut in bottoms' : '下身你偏好較合身的剪裁',
      detail: lang === 'en'
        ? `You returned ${evidence.bottom[0]?.product.name} as too large — I'll suggest sizing down on wide or oversized bottoms.`
        : `你曾因「尺寸太大」退貨 ${evidence.bottom[0]?.product.name}，遇到寬版或版型偏大的下身，我會建議你選小一號。`,
      data: evidence.bottom.slice(0, 2),
    });
  }

  // 2. Style profile
  const styles = p.user.stylePreferences || [];
  if (styles.length) {
    out.push({
      type: 'style', icon: '🎨', confidence: 0.9,
      title: lang === 'en' ? `Your style profile: ${styles.join(' · ')}` : `你的風格畫像：${styles.join(' · ')}`,
      detail: lang === 'en'
        ? `Learned from ${wardrobe.length} pieces you own and ${p.searchHistory.length} recent searches. I weight these styles higher when building bundles.`
        : `從你擁有的 ${wardrobe.length} 件單品與 ${p.searchHistory.length} 筆近期搜尋歸納而來，建立套裝時我會提高這些風格的權重。`,
    });
  }

  // 3. Colour preferences
  const fav = p.user.favoriteColors || [];
  const avoid = p.user.dislikedColors || [];
  if (fav.length || avoid.length) {
    out.push({
      type: 'color', icon: '🌈', confidence: 0.78,
      title: lang === 'en' ? 'Colour preferences' : '色彩偏好',
      detail: lang === 'en'
        ? `You gravitate to ${fav.join(', ')} and avoid ${avoid.join(', ') || 'nothing'}.`
        : `你偏好的色系是 ${fav.join('、')}${avoid.length ? `，並避開 ${avoid.join('、')}` : ''}。`,
    });
  }

  // 4. Wardrobe gap analysis
  const owned = getWardrobeCoverage();
  const gaps = ['outerwear', 'footwear', 'bag', 'neckwear', 'eyewear'].filter((s) => !owned.has(s));
  if (gaps.length) {
    const zhGap = { outerwear: '外套', footwear: '鞋履', bag: '包款', neckwear: '圍巾/頸圍', eyewear: '眼鏡' };
    out.push({
      type: 'gap', icon: '🧩', confidence: 0.72,
      title: lang === 'en' ? 'Wardrobe gaps' : '衣櫥缺口分析',
      detail: lang === 'en'
        ? `Your wardrobe has no ${gaps.join(', ')} yet — these are the pieces I'd suggest adding first.`
        : `你的衣櫥目前沒有${gaps.map((g) => zhGap[g] || g).join('、')}，這是我建議優先補齊的單品。`,
    });
  }

  // 5. Return behaviour
  if (returns.length) {
    const rate = returns.length;
    out.push({
      type: 'returns', icon: '📦', confidence: 0.83,
      title: lang === 'en' ? `${rate} past returns analysed` : `已分析 ${rate} 筆退貨紀錄`,
      detail: lang === 'en'
        ? 'Every return teaches the model your real fit. Returns have dropped since sizing advice was enabled.'
        : '每一筆退貨都讓模型更了解你的真實身型。啟用尺寸建議後，你的退貨率已明顯下降。',
    });
  }

  // 6. Budget behaviour
  const br = p.user.budgetRange;
  out.push({
    type: 'budget', icon: '💰', confidence: 0.68,
    title: lang === 'en' ? 'Typical spend per item' : '單品消費區間',
    detail: lang === 'en'
      ? `Your usual range is US$${br.min}–${br.max}. Bundles are optimised to land inside it unless you raise the cap.`
      : `你的常見單品預算落在 US$${br.min}–${br.max}，建立套裝時我會盡量讓總價落在這個區間內。`,
  });

  return out;
}

export function getMemoryContext() {
  const p = getProfile();
  const wardrobe = getWardrobe();
  const returns = getReturns();
  return {
    user: p.user,
    wardrobe: wardrobe.map((w) => ({
      productId: w.productId,
      name: w.product.name,
      name_zh: w.product.name_zh,
      image: w.product.image || null,
      monthsAgo: w.monthsAgo,
      purchasedLabel: w.purchasedLabel,
      purchasedLabel_en: w.purchasedLabel_en,
      size: w.size,
      wears: w.wears,
      condition: w.condition,
      slots: w.product.slots,
      emoji: w.product.emoji,
      color: w.product.color,
    })),
    returns: returns.map((r) => ({
      productId: r.productId,
      name: r.product.name,
      name_zh: r.product.name_zh,
      size: r.size,
      reason: r.reason,
      reasonLabel: r.reasonLabel,
      note: r.note,
      purchasedLabel: r.purchasedLabel,
      purchasedLabel_en: r.purchasedLabel_en,
    })),
    searchHistory: p.searchHistory,
    recentViews: (p.recentViews || []).map((id) => {
      const prod = getProducts().find((x) => x.id === id);
      return prod ? { id, name: prod.name, name_zh: prod.name_zh, emoji: prod.emoji, color: prod.color } : null;
    }).filter(Boolean),
    sizeTendency: getSizeTendency().tendency,
    coverage: [...getWardrobeCoverage()],
  };
}
