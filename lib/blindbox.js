// lib/blindbox.js
// AI buyer "blind box" — scenario-based complete-set bundling.
//
// Input:  a natural-language scenario + a budget.
// Output: a complete, coordinated set of items that covers every functional
//         slot the scenario needs, each with a styling reason, filled in
//         necessity order and trimmed to fit the budget.
//
// This is the seam for an LLM planner: a production build would ask a model to
// choose the slot plan and write the rationale; the request/response contract
// (slots, items, tiers, gaps) is unchanged.
import { getProducts, getProfile, convert } from './store.js';
import { findWardrobeMatches } from './memory.js';

// ---------------------------------------------------------------------------
// Scenario catalogue
// ---------------------------------------------------------------------------
export const SCENARIOS = {
  ski: {
    id: 'ski', emoji: '🎿',
    label: 'Snow Sports', label_zh: '滑雪套裝',
    blurb: 'Hokkaido powder, sub-zero windchill and long chairlift rides.',
    blurb_zh: '北海道粉雪、零下低溫與強風，需要完整的三層穿搭。',
    keywords: ['ski', 'snowboard', 'snow', 'hokkaido', 'powder', 'alpine', '滑雪', '雪', '北海道', '單板', '雙板', '雪地'],
    occasion: ['Ski', 'Outdoor'], climate: ['Freezing', 'Cold'], season: ['Winter'],
    slots: [
      { key: 'outerwear', any: ['outerwear'], label: 'Snow jacket', label_zh: '防水滑雪外套', essential: true },
      { key: 'bottom', any: ['bottom'], label: 'Snow pants', label_zh: '防水雪褲', essential: true },
      { key: 'eyewear', any: ['eyewear'], label: 'Goggles', label_zh: '防霧護目鏡', essential: true },
      { key: 'baselayer', any: ['baselayer'], label: 'Thermal base layer', label_zh: '排汗保暖內層', essential: true },
      { key: 'gloves', any: ['gloves'], label: 'Ski gloves', label_zh: '防水手套', essential: false },
      { key: 'headwear', any: ['headwear'], label: 'Beanie', label_zh: '保暖毛帽', essential: false },
      { key: 'socks', any: ['socks'], label: 'Ski socks', label_zh: '滑雪襪', essential: false },
      { key: 'neckwear', any: ['neckwear'], label: 'Neck gaiter', label_zh: '保暖頸圍', essential: false },
    ],
  },
  island_wedding: {
    id: 'island_wedding', emoji: '🏝️',
    label: 'Island Wedding', label_zh: '海島婚禮',
    blurb: 'Tropical ceremony, humid air, photos at golden hour.',
    blurb_zh: '熱帶氣候的戶外婚禮，悶熱潮濕、需要透氣又要上鏡。',
    keywords: ['island wedding', 'beach wedding', 'destination wedding', 'tropical wedding', '海島婚禮', '海邊婚禮', '戶外婚禮', '婚禮'],
    occasion: ['Wedding', 'Outdoor', 'Party'], climate: ['Tropical', 'Warm'], season: ['Summer', 'Spring'],
    slots: [
      { key: 'top', any: ['top', 'dress'], label: 'Top or dress', label_zh: '上身 / 連身裙', essential: true },
      { key: 'bottom', any: ['bottom'], label: 'Trousers', label_zh: '長褲 / 下身', essential: true },
      { key: 'footwear', any: ['footwear'], label: 'Footwear', label_zh: '鞋履', essential: true },
      { key: 'eyewear', any: ['eyewear'], label: 'Sunglasses', label_zh: '太陽眼鏡', essential: false },
      { key: 'bag', any: ['bag'], label: 'Bag', label_zh: '包款', essential: false },
      { key: 'beauty', any: ['beauty'], label: 'Sun care', label_zh: '防曬 / 保養', essential: false },
    ],
  },
  business: {
    id: 'business', emoji: '💼',
    label: 'Business & Interviews', label_zh: '商務與面試',
    blurb: 'Office, interviews and client meetings.',
    blurb_zh: '辦公室、面試與客戶會議的專業造型。',
    keywords: ['business', 'interview', 'office', 'work', 'meeting', 'smart casual', '商務', '面試', '上班', '開會', '正式'],
    occasion: ['Business', 'Office', 'Interview'], climate: ['Mild'], season: ['Spring', 'Autumn', 'Winter'],
    slots: [
      { key: 'top', any: ['top'], label: 'Shirt', label_zh: '襯衫', essential: true },
      { key: 'bottom', any: ['bottom'], label: 'Trousers', label_zh: '長褲', essential: true },
      { key: 'footwear', any: ['footwear'], label: 'Smart shoes', label_zh: '正式鞋履', essential: true },
      { key: 'outerwear', any: ['outerwear'], label: 'Blazer or jacket', label_zh: '西裝外套', essential: false },
      { key: 'bag', any: ['bag'], label: 'Work bag', label_zh: '公事包', essential: false },
      { key: 'accessory', any: ['accessory'], label: 'Watch', label_zh: '腕錶', essential: false },
    ],
  },
  winter_city: {
    id: 'winter_city', emoji: '❄️',
    label: 'City Winter', label_zh: '城市冬日',
    blurb: 'Cold-weather layering for city streets.',
    blurb_zh: '城市街頭的冷天多層次穿搭。',
    keywords: ['winter', 'cold', 'layering', 'snowy city', '冬日', '冬天', '寒冷', '保暖', '洋蔥式'],
    occasion: ['Casual', 'Outdoor', 'Office'], climate: ['Cold', 'Freezing', 'Cool'], season: ['Winter'],
    slots: [
      { key: 'outerwear', any: ['outerwear'], label: 'Outer layer', label_zh: '外套', essential: true },
      { key: 'midlayer', any: ['midlayer'], label: 'Mid layer', label_zh: '中層保暖', essential: true },
      { key: 'bottom', any: ['bottom'], label: 'Trousers', label_zh: '長褲', essential: true },
      { key: 'footwear', any: ['footwear'], label: 'Boots', label_zh: '靴款', essential: true },
      { key: 'neckwear', any: ['neckwear'], label: 'Scarf or gaiter', label_zh: '圍巾 / 頸圍', essential: false },
      { key: 'headwear', any: ['headwear'], label: 'Hat', label_zh: '帽子', essential: false },
    ],
  },
  hiking: {
    id: 'hiking', emoji: '🥾',
    label: 'Hiking & Trail', label_zh: '登山健行',
    blurb: 'Changing weather, uneven ground, long days out.',
    blurb_zh: '多變天氣與崎嶇地形，需要機能性裝備。',
    keywords: ['hiking', 'hike', 'trail', 'trek', 'mountain', 'camping', '登山', '健行', '行山', '露營', '山'],
    occasion: ['Hiking', 'Outdoor'], climate: ['Mild', 'Cool'], season: ['Spring', 'Autumn', 'Summer'],
    slots: [
      { key: 'outerwear', any: ['outerwear'], label: 'Shell jacket', label_zh: '機能外套', essential: true },
      { key: 'bottom', any: ['bottom'], label: 'Trail trousers', label_zh: '機能長褲', essential: true },
      { key: 'footwear', any: ['footwear'], label: 'Trail shoes', label_zh: '越野鞋', essential: true },
      { key: 'headwear', any: ['headwear'], label: 'Hat', label_zh: '遮陽帽', essential: false },
      { key: 'gear', any: ['gear'], label: 'Gear', label_zh: '配件裝備', essential: false },
      { key: 'beauty', any: ['beauty'], label: 'Sun care', label_zh: '防曬', essential: false },
    ],
  },
  gym: {
    id: 'gym', emoji: '🏋️',
    label: 'Gym & Training', label_zh: '健身訓練',
    blurb: 'Sweat-friendly kit with tracking and audio.',
    blurb_zh: '透氣排汗的訓練裝備，加上追蹤與音樂。',
    keywords: ['gym', 'workout', 'training', 'fitness', 'running', '健身', '運動', '跑步', '重訓', '訓練'],
    occasion: ['Gym', 'Outdoor'], climate: ['Mild', 'Warm'], season: ['Spring', 'Summer', 'Autumn'],
    slots: [
      { key: 'top', any: ['top'], label: 'Training top', label_zh: '運動上衣', essential: true },
      { key: 'bottom', any: ['bottom'], label: 'Training bottoms', label_zh: '運動褲', essential: true },
      { key: 'footwear', any: ['footwear'], label: 'Trainers', label_zh: '訓練鞋', essential: true },
      { key: 'gear', any: ['gear'], label: 'Earbuds or watch', label_zh: '耳機 / 手錶', essential: false },
    ],
  },
  beach: {
    id: 'beach', emoji: '🏖️',
    label: 'Beach Holiday', label_zh: '海灘度假',
    blurb: 'Sun, salt water and long lunches.',
    blurb_zh: '陽光、海水與悠閒的午餐時光。',
    keywords: ['beach', 'vacation', 'holiday', 'resort', 'seaside', '海灘', '度假', '沙灘', '海邊', '小島'],
    occasion: ['Vacation', 'Outdoor', 'Casual'], climate: ['Tropical', 'Warm'], season: ['Summer'],
    slots: [
      { key: 'top', any: ['top', 'dress'], label: 'Top or dress', label_zh: '上身 / 連身裙', essential: true },
      { key: 'bottom', any: ['bottom'], label: 'Shorts or trousers', label_zh: '下身', essential: true },
      { key: 'footwear', any: ['footwear'], label: 'Sandals', label_zh: '涼鞋', essential: true },
      { key: 'eyewear', any: ['eyewear'], label: 'Sunglasses', label_zh: '太陽眼鏡', essential: false },
      { key: 'headwear', any: ['headwear'], label: 'Sun hat', label_zh: '遮陽帽', essential: false },
      { key: 'beauty', any: ['beauty'], label: 'SPF', label_zh: '防曬', essential: false },
    ],
  },
  date: {
    id: 'date', emoji: '🍷',
    label: 'Date Night', label_zh: '約會夜晚',
    blurb: 'Dinner and drinks, polished but relaxed.',
    blurb_zh: '晚餐與小酌，精緻但不拘謹。',
    keywords: ['date', 'dinner', 'evening', 'night out', 'anniversary', '約會', '晚餐', '夜晚', '紀念日'],
    occasion: ['Date', 'Dinner', 'Party'], climate: ['Mild', 'Warm'], season: ['Spring', 'Summer', 'Autumn'],
    slots: [
      { key: 'top', any: ['top', 'dress'], label: 'Top or dress', label_zh: '上身 / 連身裙', essential: true },
      { key: 'bottom', any: ['bottom'], label: 'Bottoms', label_zh: '下身', essential: true },
      { key: 'footwear', any: ['footwear'], label: 'Footwear', label_zh: '鞋履', essential: true },
      { key: 'beauty', any: ['beauty'], label: 'Beauty', label_zh: '美妝', essential: false },
      { key: 'accessory', any: ['accessory'], label: 'Accessory', label_zh: '配飾', essential: false },
      { key: 'bag', any: ['bag'], label: 'Bag', label_zh: '包款', essential: false },
    ],
  },
};

const SLOT_LABELS_ZH = {
  top: '上身', midlayer: '中層', outerwear: '外套', bottom: '下身', dress: '連身裙',
  footwear: '鞋履', bag: '包款', accessory: '配飾', headwear: '帽款', eyewear: '眼鏡',
  neckwear: '頸部保暖', gloves: '手套', socks: '襪子', baselayer: '內層', beauty: '美妝保養',
  gear: '科技配件', home: '居家',
};

export function detectScenario(query = '') {
  const q = ` ${query.toLowerCase()} `;
  let best = null;
  let bestHits = 0;
  for (const sc of Object.values(SCENARIOS)) {
    const hits = sc.keywords.filter((k) => q.includes(k.toLowerCase())).length;
    if (hits > bestHits) { bestHits = hits; best = sc; }
  }
  return best;
}

// ---------------------------------------------------------------------------
// Scoring
// ---------------------------------------------------------------------------
function scoreProduct(p, scenario, profile) {
  let score = 0;
  const reasons = [];
  const shared = (a, b) => (a || []).filter((x) => (b || []).includes(x)).length;

  const occ = shared(scenario.occasion, p.occasion);
  if (occ) { score += 3 * occ; reasons.push({ key: 'occasion' }); }
  const cli = shared(scenario.climate, p.climate);
  if (cli) { score += 2 * cli; reasons.push({ key: 'climate' }); }
  const sea = shared(scenario.season, p.season);
  if (sea) { score += 1.5 * sea; reasons.push({ key: 'season' }); }

  const sty = shared(profile.user.stylePreferences, p.style);
  if (sty) { score += 1.5 * sty; reasons.push({ key: 'style' }); }

  if ((profile.user.favoriteColors || []).includes(p.colorName)) { score += 1.2; reasons.push({ key: 'colour_like' }); }
  if ((profile.user.dislikedColors || []).includes(p.colorName)) { score -= 2.5; reasons.push({ key: 'colour_dislike' }); }
  if ((profile.user.preferredBrands || []).includes(p.brand)) { score += 0.6; reasons.push({ key: 'brand' }); }

  // Soft personalisation: prefer the shopper's own gender fit without excluding
  // unisex or well-matched alternatives.
  const g = profile.user.gender;
  if (g && p.gender !== 'Unisex' && p.gender !== g) { score -= 2.2; reasons.push({ key: 'gender_soft' }); }

  score += (p.rating - 4) * 1.2;
  return { score, reasons: reasons.map((r) => r.key) };
}

function candidatesFor(slot, scenario, profile) {
  const g = profile.user.gender;
  const scored = getProducts()
    .filter((p) => (p.slots || []).some((s) => slot.any.includes(s)))
    // Respect the shopper's own gender: skip gendered items that don't fit.
    .filter((p) => !g || p.gender === 'Unisex' || p.gender === g)
    .map((p) => {
      const { score, reasons } = scoreProduct(p, scenario, profile);
      return { product: p, score, reasons };
    })
    .filter((c) => c.score > 0)
    .sort((a, b) => b.score - a.score || a.product.price - b.product.price);

  if (!scored.length) return scored;
  // Relevance gate: only keep items that genuinely belong to this slot in this
  // scenario. Without it a denim jacket would compete for "ski outerwear"
  // simply because both carry the Outdoor tag.
  const gate = Math.max(2.5, scored[0].score * 0.5);
  return scored.filter((c) => c.score >= gate);
}

function cheapestOf(slot, scenario, profile) {
  const c = candidatesFor(slot, scenario, profile);
  if (!c.length) return null;
  return c.reduce((min, x) => (x.product.price < min.product.price ? x : min), c[0]);
}

// ---------------------------------------------------------------------------
// Set assembly
// ---------------------------------------------------------------------------
function reasonText(entry, scenario, slot, lang) {
  const p = entry.product;
  const zh = lang !== 'en';
  const bits = [];
  if (entry.reasons.includes('occasion')) bits.push(zh ? `符合「${scenario.label_zh}」場合` : `right for ${scenario.label}`);
  if (entry.reasons.includes('climate')) bits.push(zh ? '對應當地氣候需求' : 'handles the climate');
  if (entry.reasons.includes('season')) bits.push(zh ? '當季單品' : 'in season');
  if (entry.reasons.includes('style')) bits.push(zh ? `符合你偏好的 ${(p.style || [])[0]} 風格` : `matches your ${(p.style || [])[0]} style`);
  if (entry.reasons.includes('colour_like')) bits.push(zh ? `是你喜歡的${p.colorName}` : `in a colour you like`);
  if (!bits.length) bits.push(zh ? `${p.material}材質、好搭配` : `${p.material.toLowerCase()}, easy to pair`);
  const role = zh ? slot.label_zh : slot.label;
  return zh ? `${role}｜${bits.join('，')}。` : `${role} — ${bits.join(', ')}.`;
}

export function buildBlindBox({ query = '', scenarioId = null, budget = null, lang = 'zh', useWardrobe = true } = {}) {
  const profile = getProfile();
  const scenario = (scenarioId && SCENARIOS[scenarioId]) || detectScenario(query) || SCENARIOS.winter_city;

  // Budget is entered in the display currency; convert to base USD for maths.
  const budgetUsd = budget == null ? null : budget / (lang === 'en' ? 1 : 7.8);

  // Owned items that fit this scenario (long-term memory).
  const ownedMatches = useWardrobe
    ? findWardrobeMatches({
        occasion: scenario.occasion,
        climate: scenario.climate,
        season: scenario.season,
        style: profile.user.stylePreferences,
      })
    : [];

  const usedProducts = new Set();
  const items = [];
  const gaps = [];
  let remaining = budgetUsd;

  const essentials = scenario.slots.filter((s) => s.essential);
  const optionals = scenario.slots.filter((s) => !s.essential);

  const pick = (slot, { reserve = 0, allowOverBudget = false } = {}) => {
    // Candidates available for this slot right now.
    const cands = candidatesFor(slot, scenario, profile).filter((c) => !usedProducts.has(c.product.id));
    const bestScore = cands.length ? cands[0].score : 0;
    // Quality gate: an owned item may only stand in for a slot when it is
    // genuinely suited to the scenario — otherwise a denim jacket would end up
    // "covering" ski outerwear just because both are tagged Outdoor.
    const gate = Math.max(2.5, bestScore * 0.55);

    // Wardrobe first: never re-sell the shopper something they own.
    const owned = ownedMatches.find(
      (m) =>
        (m.product.slots || []).some((s) => slot.any.includes(s)) &&
        !usedProducts.has(m.product.id) &&
        scoreProduct(m.product, scenario, profile).score >= gate,
    );
    if (owned) {
      usedProducts.add(owned.product.id);
      items.push({
        product: owned.product, slot: slot.key, role: slot.label, role_zh: slot.label_zh,
        owned: true, price: 0, note: reasonText({ product: owned.product, reasons: ['style'] }, scenario, slot, lang),
        ownedLabel: owned.entry.purchasedLabel, ownedLabel_en: owned.entry.purchasedLabel_en,
      });
      return true;
    }

    if (!cands.length) return false;

    let affordable = cands;
    if (remaining != null && !allowOverBudget) {
      affordable = cands.filter((c) => c.product.price <= remaining - reserve);
      if (!affordable.length) {
        // Relax the reservation but keep quality first: take the best-scoring
        // item that the remaining budget can still cover.
        const fitting = cands.filter((c) => c.product.price <= remaining);
        if (fitting.length) affordable = fitting;
        else {
          const cheapest = cands.reduce((m, x) => (x.product.price < m.product.price ? x : m), cands[0]);
          gaps.push({ slot: slot.key, label: slot.label, label_zh: slot.label_zh, needed: cheapest.product.price });
          return false;
        }
      }
    }

    const best = affordable[0];
    usedProducts.add(best.product.id);
    if (remaining != null) remaining = Math.round((remaining - best.product.price) * 100) / 100;
    items.push({
      product: best.product, slot: slot.key, role: slot.label, role_zh: slot.label_zh,
      owned: false, price: best.product.price, note: reasonText(best, scenario, slot, lang),
    });
    return true;
  };

  // 1. Essentials, reserving budget for the essential slots still to come.
  essentials.forEach((slot, i) => {
    const reserve = essentials
      .slice(i + 1)
      .reduce((sum, s) => {
        const c = cheapestOf(s, scenario, profile);
        return sum + (c ? c.product.price : 0);
      }, 0);
    pick(slot, { reserve });
  });

  // 2. Optionals while budget remains.
  for (const slot of optionals) pick(slot);

  // ---- Totals -------------------------------------------------------------
  const newItems = items.filter((i) => !i.owned);
  const ownedItems = items.filter((i) => i.owned);
  const total = Math.round(newItems.reduce((s, i) => s + i.product.price, 0) * 100) / 100;
  const ownedValue = Math.round(ownedItems.reduce((s, i) => s + i.product.price, 0) * 100) / 100;
  const essentialSlotsCovered = essentials.filter((s) => items.some((i) => i.slot === s.key)).length;

  // ---- Minimum viable budget ---------------------------------------------
  let minEssential = 0;
  const minItems = [];
  for (const slot of essentials) {
    const c = cheapestOf(slot, scenario, profile);
    const gate = Math.max(2.5, (c?.score || 0) * 0.55);
    const owned = ownedMatches.find(
      (m) =>
        (m.product.slots || []).some((s) => slot.any.includes(s)) &&
        !minItems.some((mi) => mi.product.id === m.product.id) &&
        scoreProduct(m.product, scenario, profile).score >= gate,
    );
    if (owned) { minItems.push({ product: owned.product, owned: true, price: 0 }); continue; }
    if (c && !minItems.some((mi) => mi.product.id === c.product.id)) {
      minItems.push({ product: c.product, owned: false, price: c.product.price });
      minEssential += c.product.price;
    }
  }
  minEssential = Math.round(minEssential * 100) / 100;

  const budgetRemaining = budgetUsd == null ? null : Math.round((budgetUsd - total) * 100) / 100;

  // ---- Rationale (LLM seam) ----------------------------------------------
  const zh = lang !== 'en';
  const coverage = essentials.length ? Math.round((essentialSlotsCovered / essentials.length) * 100) : 100;
  const missing = essentials.filter((s) => !items.some((i) => i.slot === s.key));
  let rationale;
  if (zh) {
    rationale = `針對「${scenario.label_zh}」，我依必要性排序組出 ${items.length} 件套裝（必要單品覆蓋率 ${coverage}%）。`;
    if (ownedItems.length) rationale += `其中 ${ownedItems.length} 件來自你的衣櫥，不需重複購買。`;
    if (missing.length) rationale += `預算內仍缺少：${missing.map((m) => m.label_zh).join('、')}，建議至少準備 HK$${Math.round(minEssential * 7.8).toLocaleString()} 才能補齊必要裝備。`;
    else if (budgetRemaining != null && budgetRemaining > 0) rationale += `總計在預算內，尚餘 HK$${Math.round(budgetRemaining * 7.8).toLocaleString()}。`;
  } else {
    rationale = `For ${scenario.label}, I assembled ${items.length} pieces in necessity order (${coverage}% essential coverage).`;
    if (ownedItems.length) rationale += ` ${ownedItems.length} come from your wardrobe, so you don't re-buy them.`;
    if (missing.length) rationale += ` Still missing within budget: ${missing.map((m) => m.label).join(', ')}. A minimum of US$${minEssential.toFixed(0)} covers the essentials.`;
    else if (budgetRemaining != null && budgetRemaining > 0) rationale += ` It fits the budget with US$${budgetRemaining.toFixed(2)} to spare.`;
  }

  return {
    scenario: { id: scenario.id, emoji: scenario.emoji, label: scenario.label, label_zh: scenario.label_zh, blurb: scenario.blurb, blurb_zh: scenario.blurb_zh },
    budget: budgetUsd == null ? null : { input: budget, currency: lang === 'en' ? 'USD' : 'HKD' },
    items,
    total,
    ownedValue,
    savings: ownedValue,
    budgetRemaining,
    minEssential,
    coverage,
    missing: missing.map((m) => ({ slot: m.key, label: m.label, label_zh: m.label_zh })),
    gaps,
    rationale,
    tiers: buildTiers(scenario, profile, budgetUsd, lang, ownedMatches),
  };
}

// Essentials / complete / premium views of the same scenario.
function buildTiers(scenario, profile, budgetUsd, lang, ownedMatches) {
  const zh = lang !== 'en';
  const essentials = scenario.slots.filter((s) => s.essential);
  const all = scenario.slots;
  const used = new Set();

  const assemble = (slots, mode) => {
    const out = [];
    for (const slot of slots) {
      const cands = candidatesFor(slot, scenario, profile).filter((c) => !out.some((o) => o.product.id === c.product.id));
      const gate = Math.max(2.5, (cands[0]?.score || 0) * 0.55);
      const owned = ownedMatches.find(
        (m) =>
          (m.product.slots || []).some((s) => slot.any.includes(s)) &&
          !out.some((o) => o.product.id === m.product.id) &&
          scoreProduct(m.product, scenario, profile).score >= gate,
      );
      if (owned) {
        out.push({ product: owned.product, owned: true, slot: slot.key });
        continue;
      }
      if (!cands.length) continue;
      const pick = mode === 'premium'
        ? cands.slice().sort((a, b) => b.product.price - a.product.price)[0]
        : cands.reduce((m, x) => (x.product.price < m.product.price ? x : m), cands[0]);
      out.push({ product: pick.product, owned: false, slot: slot.key });
    }
    const total = out.filter((o) => !o.owned).reduce((s, o) => s + o.product.price, 0);
    return { items: out, total: Math.round(total * 100) / 100, count: out.length };
  };

  const rate = zh ? 7.8 : 1;
  const essentialSet = assemble(essentials, 'cheap');
  const completeSet = assemble(all, 'cheap');
  const premiumSet = assemble(all, 'premium');

  return [
    {
      id: 'essentials', name: zh ? '精簡必備' : 'Essentials', total: essentialSet.total,
      displayTotal: Math.round(essentialSet.total * rate), count: essentialSet.count,
      fitsBudget: budgetUsd == null || essentialSet.total <= budgetUsd,
      note: zh ? '只買真正必要的三件核心裝備' : 'Only the core pieces you truly need',
    },
    {
      id: 'complete', name: zh ? '完整套裝' : 'Complete set', total: completeSet.total,
      displayTotal: Math.round(completeSet.total * rate), count: completeSet.count,
      fitsBudget: budgetUsd == null || completeSet.total <= budgetUsd,
      note: zh ? '涵蓋全部必要單品與推薦配件' : 'Every essential plus the recommended extras',
    },
    {
      id: 'premium', name: zh ? '升級款式' : 'Premium picks', total: premiumSet.total,
      displayTotal: Math.round(premiumSet.total * rate), count: premiumSet.count,
      fitsBudget: budgetUsd == null || premiumSet.total <= budgetUsd,
      note: zh ? '以最高評價款式升級材質與規格' : 'Upgraded materials and specs',
    },
  ];
}
