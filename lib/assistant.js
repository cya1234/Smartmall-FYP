// lib/assistant.js
// Contextual shopping assistant (LLM + RAG style).
//
// Parses a natural-language query into a structured shopping intent, retrieves
// matching products from the catalog, and assembles scenario-based product
// bundles. This is the seam where a real LLM + retrieval-augmented-generation
// pipeline would be wired in: the parse -> retrieve -> bundle -> explain flow
// and its JSON contract stay the same, only the "understand" and "generate"
// steps would be replaced by model calls.
import { getProducts, getProfile } from './store.js';
import { findWardrobeMatches, buildMemoryNote, getSizeTendency } from './memory.js';

// ---------------------------------------------------------------------------
// Intent dictionaries (English + Traditional Chinese keywords)
// ---------------------------------------------------------------------------
const OCCASION_MAP = [
  ['wedding', 'Wedding'],
  ['婚禮', 'Wedding'],
  ['party', 'Party'],
  ['派對', 'Party'],
  ['celebration', 'Party'],
  ['office', 'Office'],
  ['上班', 'Office'],
  ['work', 'Office'],
  ['business', 'Business'],
  ['商務', 'Business'],
  ['interview', 'Interview'],
  ['面試', 'Interview'],
  ['job interview', 'Interview'],
  ['date', 'Date'],
  ['約會', 'Date'],
  ['casual', 'Casual'],
  ['休閒', 'Casual'],
  ['everyday', 'Casual'],
  ['formal', 'Formal'],
  ['正式', 'Formal'],
  ['black tie', 'Formal'],
  ['gym', 'Gym'],
  ['健身', 'Gym'],
  ['滑雪', 'Ski'],
  ['snowboard', 'Ski'],
  ['登山', 'Hiking'],
  ['hiking', 'Hiking'],
  ['workout', 'Gym'],
  ['fitness', 'Gym'],
  ['hiking', 'Hiking'],
  ['hike', 'Hiking'],
  ['trail', 'Hiking'],
  ['outdoor', 'Outdoor'],
  ['vacation', 'Vacation'],
  ['holiday', 'Vacation'],
  ['travel', 'Travel'],
  ['trip', 'Travel'],
  ['dinner', 'Dinner'],
  ['evening', 'Dinner'],
];

const CLIMATE_MAP = [
  ['tropical', 'Tropical'],
  ['熱帶', 'Tropical'],
  ['hot', 'Tropical'],
  ['humid', 'Tropical'],
  ['beach', 'Tropical'],
  ['海島', 'Tropical'],
  ['海灘', 'Tropical'],
  ['summer heat', 'Tropical'],
  ['cold', 'Cold'],
  ['寒冷', 'Cold'],
  ['freezing', 'Freezing'],
  ['零下', 'Freezing'],
  ['snow', 'Freezing'],
  ['雪', 'Freezing'],
  ['winter', 'Cold'],
  ['cool', 'Cool'],
  ['chilly', 'Cool'],
  ['autumn', 'Cool'],
  ['fall', 'Cool'],
  ['warm', 'Warm'],
  ['mild', 'Mild'],
  ['rainy', 'Rainy'],
  ['rain', 'Rainy'],
];

const SEASON_MAP = [
  ['summer', 'Summer'],
  ['夏天', 'Summer'],
  ['夏季', 'Summer'],
  ['winter', 'Winter'],
  ['冬天', 'Winter'],
  ['冬季', 'Winter'],
  ['spring', 'Spring'],
  ['春天', 'Spring'],
  ['autumn', 'Autumn'],
  ['秋天', 'Autumn'],
  ['fall', 'Autumn'],
];

const STYLE_MAP = [
  ['elegant', 'Elegant'],
  ['優雅', 'Elegant'],
  ['casual', 'Casual'],
  ['休閒', 'Casual'],
  ['sporty', 'Sporty'],
  ['運動', 'Sporty'],
  ['minimal', 'Minimal'],
  ['極簡', 'Minimal'],
  ['minimalist', 'Minimal'],
  ['classic', 'Classic'],
  ['經典', 'Classic'],
  ['bohemian', 'Bohemian'],
  ['boho', 'Bohemian'],
  ['glamorous', 'Glamorous'],
  ['glam', 'Glamorous'],
  ['cozy', 'Cozy'],
  ['保暖', 'Cozy'],
  ['professional', 'Professional'],
  ['feminine', 'Feminine'],
  ['breezy', 'Breezy'],
];

const MATERIAL_MAP = [
  ['linen', 'Linen'],
  ['silk', 'Silk'],
  ['cotton', 'Cotton'],
  ['wool', 'Wool'],
  ['cashmere', 'Cashmere'],
  ['denim', 'Denim'],
  ['leather', 'Leather'],
];

const COLOR_MAP = [
  ['white', 'White'],
  ['black', 'Black'],
  ['blue', 'Blue'],
  ['red', 'Red'],
  ['pink', 'Pink'],
  ['green', 'Green'],
  ['gold', 'Gold'],
  ['silver', 'Silver'],
  ['beige', 'Beige'],
  ['brown', 'Brown'],
  ['navy', 'Navy'],
  ['coral', 'Coral'],
  ['emerald', 'Emerald'],
  ['crimson', 'Crimson'],
  ['tan', 'Tan'],
  ['sage', 'Sage'],
  ['burgundy', 'Burgundy'],
  ['cream', 'Cream'],
];

const GENDER_MAP = [
  ['women', 'Women'],
  ['woman', 'Women'],
  ['ladies', 'Women'],
  ['female', 'Women'],
  ['men', 'Men'],
  ['man', 'Men'],
  ['male', 'Men'],
];

// Functional slots. A product declares which slots it can fill via `slots`.
const SLOT_GROUPS = [
  { key: 'top', label: 'Top', label_zh: '上身', slot: 'top' },
  { key: 'dress', label: 'Dress', label_zh: '連身裙', slot: 'dress' },
  { key: 'midlayer', label: 'Mid layer', label_zh: '中層', slot: 'midlayer' },
  { key: 'outerwear', label: 'Outerwear', label_zh: '外套', slot: 'outerwear' },
  { key: 'bottom', label: 'Bottoms', label_zh: '下身', slot: 'bottom' },
  { key: 'footwear', label: 'Footwear', label_zh: '鞋履', slot: 'footwear' },
  { key: 'bag', label: 'Bag', label_zh: '包款', slot: 'bag' },
  { key: 'accessory', label: 'Accessory', label_zh: '配飾', slot: 'accessory' },
  { key: 'headwear', label: 'Headwear', label_zh: '帽款', slot: 'headwear' },
  { key: 'eyewear', label: 'Eyewear', label_zh: '眼鏡', slot: 'eyewear' },
  { key: 'neckwear', label: 'Neckwear', label_zh: '頸部保暖', slot: 'neckwear' },
  { key: 'gloves', label: 'Gloves', label_zh: '手套', slot: 'gloves' },
  { key: 'socks', label: 'Socks', label_zh: '襪子', slot: 'socks' },
  { key: 'baselayer', label: 'Base layer', label_zh: '內層', slot: 'baselayer' },
  { key: 'beauty', label: 'Beauty', label_zh: '美妝保養', slot: 'beauty' },
  { key: 'gear', label: 'Gear', label_zh: '科技配件', slot: 'gear' },
];

function groupFor(slotKey) {
  return SLOT_GROUPS.find((g) => g.key === slotKey) || null;
}

function fillsSlot(product, group) {
  return (product.slots || []).includes(group.slot);
}

function parseIntent(query) {
  const q = ` ${query.toLowerCase()} `;
  const intent = { occasion: [], climate: [], season: [], style: [], material: [], color: [], gender: [], budget: null, minPrice: null, categories: [] };

  for (const [kw, val] of OCCASION_MAP) if (q.includes(kw) && !intent.occasion.includes(val)) intent.occasion.push(val);
  for (const [kw, val] of CLIMATE_MAP) if (q.includes(kw) && !intent.climate.includes(val)) intent.climate.push(val);
  for (const [kw, val] of SEASON_MAP) if (q.includes(kw) && !intent.season.includes(val)) intent.season.push(val);
  for (const [kw, val] of STYLE_MAP) if (q.includes(kw) && !intent.style.includes(val)) intent.style.push(val);
  for (const [kw, val] of MATERIAL_MAP) if (q.includes(kw) && !intent.material.includes(val)) intent.material.push(val);
  for (const [kw, val] of COLOR_MAP) if (q.includes(kw) && !intent.color.includes(val)) intent.color.push(val);
  for (const [kw, val] of GENDER_MAP) if (q.includes(kw) && !intent.gender.includes(val)) intent.gender.push(val);

  // Budget: "under $X", "預算 2000", "below $X", "cheap", "affordable", "luxury".
  const under = query.match(/(?:under|below|less than|max|預算|budget of)\s*\$?\s*(\d[\d,]*)/i);
  if (under) intent.budget = Number(under[1].replace(/,/g, ''));
  else if (/\b(cheap|affordable|budget)\b/i.test(query) || /便宜|平價|小資/.test(query)) intent.budget = 75;
  if (/\b(luxury|premium|high[- ]end)\b/i.test(query) || /奢華|高級|頂級/.test(query)) intent.minPrice = 120;

  // Category hints for tag matching.
  const categoryKeywords = [
    'dress', 'shirt', 'sweater', 'jacket', 'blazer', 'pants', 'trousers', 'jeans',
    'shoes', 'sneakers', 'boots', 'sandals', 'loafers', 'bag', 'tote', 'clutch',
    'hat', 'watch', 'sunglasses', 'scarf', 'sunscreen', 'skincare', 'makeup',
    'lipstick', 'serum', 'diffuser', 'dinnerware', 'earbuds', 'headphones', 'fitness',
    'goggles', 'gloves', 'beanie', 'socks', 'ski', 'snow',
    '連身裙', '襯衫', '毛衣', '外套', '西裝', '長褲', '牛仔褲', '鞋', '靴', '涼鞋',
    '包', '帽', '錶', '手錶', '太陽眼鏡', '圍巾', '防曬', '保養', '化妝', '精華',
    '耳機', '手錶', '滑雪', '雪褲', '護目鏡', '手套', '雪襪', '毛帽', '內層',
  ];
  for (const kw of categoryKeywords) if (q.includes(kw) && !intent.categories.includes(kw)) intent.categories.push(kw);

  // Personalisation: fall back to the shopper's own profile gender so we never
  // recommend gendered items that don't fit them. Unisex items always pass.
  if (!intent.gender.length) {
    const g = getProfile().user.gender;
    if (g) { intent.gender = [g]; intent.genderFromProfile = true; }
  }

  return intent;
}

function intentSummary(intent, lang = 'zh') {
  const zh = lang !== 'en';
  const L = {
    occasion: zh ? '場合' : 'occasion',
    climate: zh ? '氣候' : 'climate',
    season: zh ? '季節' : 'season',
    style: zh ? '風格' : 'style',
    material: zh ? '材質' : 'material',
    color: zh ? '顏色' : 'colour',
    forWho: zh ? '對象' : 'for',
    budget: zh ? '預算' : 'budget',
    premium: zh ? '價位' : 'price tier',
  };
  const parts = [];
  if (intent.occasion.length) parts.push(`${L.occasion}: ${intent.occasion.join('、')}`);
  if (intent.climate.length) parts.push(`${L.climate}: ${intent.climate.join('、')}`);
  if (intent.season.length) parts.push(`${L.season}: ${intent.season.join('、')}`);
  if (intent.style.length) parts.push(`${L.style}: ${intent.style.join('、')}`);
  if (intent.material.length) parts.push(`${L.material}: ${intent.material.join('、')}`);
  if (intent.color.length) parts.push(`${L.color}: ${intent.color.join('、')}`);
  if (intent.gender.length && !intent.genderFromProfile) parts.push(`${L.forWho}: ${intent.gender.join('/')}`);
  if (intent.budget != null) parts.push(`${L.budget}: ${zh ? 'HK$' : 'US$'}${intent.budget}${zh ? ' 以內' : ' or less'}`);
  if (intent.minPrice != null) parts.push(`${L.premium}: ${zh ? 'HK$' : 'US$'}${intent.minPrice}+`);
  return parts;
}

function countShared(a, b) {
  return (a || []).filter((x) => (b || []).includes(x)).length;
}

function scoreProduct(product, intent) {
  let score = 0;
  const reasons = [];
  const add = (n, r) => { score += n; if (r) reasons.push(r); };

  const occ = countShared(intent.occasion, product.occasion);
  if (occ) add(3 * occ, 'matches your occasion');
  const cli = countShared(intent.climate, product.climate);
  if (cli) add(2 * cli, 'suits the climate');
  const sea = countShared(intent.season, product.season);
  if (sea) add(1.5 * sea, 'in-season');
  const sty = countShared(intent.style, product.style);
  if (sty) add(1.5 * sty, 'matches your style');
  if (intent.material.some((m) => product.material.toLowerCase().includes(m.toLowerCase()))) add(2, 'matches material');
  if (intent.color.some((c) => product.colorName.toLowerCase().includes(c.toLowerCase()))) add(2, 'matches colour');
  if (intent.gender.length && product.gender !== 'Unisex' && !intent.gender.includes(product.gender)) add(-2, null);
  if (intent.gender.includes(product.gender)) add(1, 'right fit');

  const haystack = `${product.name} ${product.description} ${product.tags.join(' ')} ${product.subcategory} ${product.category}`.toLowerCase();
  for (const kw of intent.categories) if (haystack.includes(kw)) add(2.2, `mentions "${kw}"`);
  if (intent.categories.length === 0 && intent.occasion.length === 0 && intent.climate.length === 0) {
    // Bare keyword search fallback.
    const tokens = intent._tokens || [];
    for (const t of tokens) if (t.length > 2 && haystack.includes(t)) add(1.5, `mentions "${t}"`);
  }

  return { score, reasons };
}

function applyFilters(product, intent) {
  if (intent.budget != null && product.price > intent.budget) return false;
  if (intent.minPrice != null && product.price < intent.minPrice) return false;
  if (intent.gender.length && product.gender !== 'Unisex' && !intent.gender.includes(product.gender)) return false;
  return true;
}

function compatibility(a, b) {
  let c = 0;
  if ((a.occasion || []).some((x) => (b.occasion || []).includes(x))) c += 2;
  if ((a.climate || []).some((x) => (b.climate || []).includes(x))) c += 2;
  if ((a.season || []).some((x) => (b.season || []).includes(x))) c += 1.5;
  if ((a.style || []).some((x) => (b.style || []).includes(x))) c += 1;
  return c;
}

// Identify which slot the bundle's anchor occupies (prefers a clothing slot).
function slotFor(product) {
  const order = ['dress', 'outerwear', 'midlayer', 'top', 'bottom', 'footwear', 'bag', 'eyewear', 'headwear', 'neckwear', 'accessory', 'gear', 'beauty'];
  const owned = (product.slots || []);
  for (const k of order) if (owned.includes(k)) return k;
  return null;
}

function completeBundle(anchor, scored, intent, chosen, wardrobeMatches = [], lang = 'zh', anchorOwned = null) {
  const anchorSlot = slotFor(anchor);
  let slots;
  if (anchorSlot === 'dress') slots = ['footwear', 'bag', 'eyewear', 'beauty'];
  else if (anchorSlot === 'top') slots = ['bottom', 'footwear', 'midlayer', 'bag', 'accessory'];
  else if (anchorSlot === 'midlayer') slots = ['bottom', 'footwear', 'outerwear', 'neckwear'];
  else if (anchorSlot === 'outerwear') slots = ['bottom', 'footwear', 'midlayer', 'headwear'];
  else if (anchorSlot === 'bottom') slots = ['top', 'footwear', 'outerwear', 'accessory'];
  else if (anchorSlot === 'footwear') slots = ['bottom', 'top', 'bag', 'accessory'];
  else if (anchorSlot === 'bag') slots = ['footwear', 'top', 'beauty'];
  else slots = ['footwear', 'top', 'accessory', 'beauty'];

  // Warm-weather anchors should not be paired with an insulating layer.
  const warm = (anchor.climate || []).some((c) => ['Tropical', 'Warm'].includes(c))
    && !(anchor.climate || []).some((c) => ['Cold', 'Freezing'].includes(c));
  if (warm) slots = slots.filter((s) => s !== 'midlayer' && s !== 'outerwear');

  const items = [{
    product: anchor,
    role: anchorSlot || anchor.subcategory,
    role_zh: groupFor(anchorSlot)?.label_zh || anchor.subcategory,
    note: anchorOwned
      ? (lang === 'en'
          ? `You already own this (bought ${anchorOwned.entry.purchasedLabel_en}) — I built the rest of the look around it.`
          : `你已經有這件了（${anchorOwned.entry.purchasedLabel}購入），我以它為基礎搭配其餘單品。`)
      : anchor._reason,
    owned: !!anchorOwned,
    price: anchorOwned ? 0 : anchor.price,
    ownedLabel: anchorOwned?.entry.purchasedLabel,
    ownedLabel_en: anchorOwned?.entry.purchasedLabel_en,
  }];
  const used = new Set(chosen);

  for (const slotKey of slots) {
    const group = groupFor(slotKey);
    if (!group) continue;

    // Long-term memory: reuse what the shopper already owns before selling them
    // the same slot again.
    const owned = wardrobeMatches.find(
      (m) => fillsSlot(m.product, group) && !used.has(m.product.id),
    );
    if (owned) {
      used.add(owned.product.id);
      items.push({
        product: owned.product,
        role: slotKey,
        role_zh: group.label_zh,
        note: lang === 'en'
          ? `Already in your wardrobe (bought ${owned.entry.purchasedLabel_en}) — no need to buy again.`
          : `你已經有這件了（${owned.entry.purchasedLabel}購入），不需要重複購買。`,
        owned: true,
        price: 0,
        ownedLabel: owned.entry.purchasedLabel,
        ownedLabel_en: owned.entry.purchasedLabel_en,
      });
      continue;
    }

    const candidates = scored
      .filter(
        ({ product }) =>
          fillsSlot(product, group) &&
          !used.has(product.id) &&
          countShared(anchor.occasion, product.occasion) > 0,
      )
      .sort((x, y) => (y.score + compatibility(anchor, y.product)) - (x.score + compatibility(anchor, x.product)));
    const best = candidates[0];
    if (best) {
      items.push({ product: best.product, role: slotKey, role_zh: group.label_zh, note: best._reason, owned: false, price: best.product.price });
      used.add(best.product.id);
    }
  }
  return items;
}

export function runAssistantLegacy(query, lang = 'zh') {
  const intent = parseIntent(query);
  intent._tokens = query.toLowerCase().split(/[^a-z0-9$\u4e00-\u9fff]+/).filter((t) => t.length > 1);

  const products = getProducts();
  const scored = products
    .filter((p) => applyFilters(p, intent))
    .map((p) => {
      const { score, reasons } = scoreProduct(p, intent);
      return { product: p, score, _reason: reasons[0] || null };
    })
    .sort((a, b) => b.score - a.score);

  // Long-term memory: pieces the shopper already owns that fit this brief.
  const wardrobeMatches = findWardrobeMatches({
    occasion: intent.occasion,
    climate: intent.climate,
    season: intent.season,
    style: intent.style,
  });

  // ---- Build bundles ------------------------------------------------------
  const bundles = [];
  const anchorsUsed = new Set();

  const makeBundle = (items, anchorProduct, ownedAnchor) => {
    const owneds = items.filter((i) => i.owned);
    const newOnes = items.filter((i) => !i.owned);
    const total = Math.round(newOnes.reduce((s, i) => s + i.price, 0) * 100) / 100;
    const ownedValue = Math.round(owneds.reduce((s, i) => s + i.product.price, 0) * 100) / 100;
    const label = lang === 'en' ? (anchorProduct.name) : (anchorProduct.name_zh || anchorProduct.name);
    return {
      title: ownedAnchor
        ? (lang === 'en' ? `Around your ${label} — ${items.length} pieces` : `以你的「${label}」為基礎｜${items.length} 件搭配`)
        : (lang === 'en' ? `${label} ${items.length}-piece set` : `${label}｜${items.length} 件套裝`),
      scenario: intentSummary(intent, lang),
      items,
      total,
      ownedValue,
      ownedCount: owneds.length,
      fromWardrobe: !!ownedAnchor,
      currency: anchorProduct.currency,
    };
  };

  // Memory-first: if the shopper already owns a strong match for this brief,
  // build the look around it rather than selling a whole new set.
  for (const wm of wardrobeMatches) {
    if (bundles.length >= 1) break;
    if (wm.score < 2) continue;
    const items = completeBundle(wm.product, scored, intent, new Set([wm.product.id]), wardrobeMatches, lang, wm);
    if (items.length < 2) continue;
    anchorsUsed.add(wm.product.slots?.[0] || wm.product.subcategory);
    bundles.push(makeBundle(items, wm.product, true));
  }

  // Then catalog-anchored options, each on a distinct slot.
  // Prefer clothing anchors so the alternatives read as outfits rather than a
  // bag or a lipstick driving the whole look.
  const ANCHOR_PRIORITY = ['dress', 'outerwear', 'top', 'midlayer', 'bottom', 'footwear', 'bag', 'headwear', 'eyewear', 'neckwear', 'accessory', 'gear', 'beauty'];
  const anchorRank = (p) => {
    const s = p.slots || [];
    for (let i = 0; i < ANCHOR_PRIORITY.length; i++) if (s.includes(ANCHOR_PRIORITY[i])) return i;
    return ANCHOR_PRIORITY.length;
  };
  const anchorPool = scored
    .filter((s) => s.score > 0)
    .slice()
    .sort((a, b) => anchorRank(a.product) - anchorRank(b.product) || b.score - a.score);

  for (const top of anchorPool) {
    if (bundles.length >= 3) break;
    const anchorKey = top.product.slots?.[0] || top.product.subcategory;
    if (anchorsUsed.has(anchorKey)) continue;
    anchorsUsed.add(anchorKey);
    const items = completeBundle(top.product, scored, intent, new Set([top.product.id]), wardrobeMatches, lang);
    if (items.length < 2) continue;
    bundles.push(makeBundle(items, top.product, false));
  }

  const ownedPickIds = new Set();
  for (const b of bundles) for (const i of b.items) if (i.owned) ownedPickIds.add(i.product.id);
  const ownedPicks = wardrobeMatches.filter((m) => ownedPickIds.has(m.product.id));
  const memoryNote = buildMemoryNote(ownedPicks, lang);

  const summary = intentSummary(intent, lang);
  const answer = buildAnswer(query, summary, bundles, scored.length, lang, memoryNote);

  return {
    query,
    lang,
    understood: summary,
    answer,
    memoryNote,
    memoryUsed: ownedPicks.map((m) => ({
      productId: m.product.id,
      name: m.product.name,
      name_zh: m.product.name_zh,
      emoji: m.product.emoji,
      color: m.product.color,
      boughtLabel: m.entry.purchasedLabel,
      boughtLabel_en: m.entry.purchasedLabel_en,
      monthsAgo: m.entry.monthsAgo,
    })),
    sizeAdvice: sizeAdviceNote(lang),
    bundles,
    matchCount: scored.filter((s) => s.score > 0).length,
    alternatives: scored.slice(0, 6).map((s) => ({ id: s.product.id, name: s.product.name, name_zh: s.product.name_zh, score: Math.round(s.score * 100) / 100, reason: s._reason })),
  };
}

// A short proactive sizing warning, drawn from the return-history model.
function sizeAdviceNote(lang = 'zh') {
  const { tendency } = getSizeTendency();
  if (lang === 'en') {
    if (tendency.top > 0) return 'Heads up: you have returned tops for being too small before — I flagged items that run small.';
    if (tendency.bottom < 0) return 'Heads up: you prefer a trimmer cut in bottoms — I flagged items that run large.';
    return null;
  }
  if (tendency.top > 0) return '提醒你：你過去有幾次上身衣物因尺寸太小退貨，我已標註版型偏小的單品。';
  if (tendency.bottom < 0) return '提醒你：你偏好較合身的下身剪裁，我已標註版型偏大的單品。';
  return null;
}

function buildAnswer(query, summary, bundles, matchCount, lang = 'zh', memoryNote = null) {
  const zh = lang !== 'en';
  if (matchCount === 0 || bundles.length === 0) {
    return zh
      ? `我在商品庫裡找不到足夠符合「${query}」的單品。可以試著描述場合（例如「海島婚禮」、「北海道滑雪」）或想要的風格。`
      : `I couldn't find enough matches for "${query}". Try describing an occasion (e.g. "island wedding", "Hokkaido ski trip") or a look you have in mind.`;
  }
  const understood = summary.length
    ? (zh ? `我理解到：${summary.join(' · ')}。` : `I understood: ${summary.join(' · ')}.`)
    : (zh ? '這是我為你整理的組合。' : `Here's what I put together.`);
  const bundleNote = bundles.length > 1
    ? (zh ? `我準備了 ${bundles.length} 套搭配，每套的單品都是為了同一個情境挑選的。` : `I assembled ${bundles.length} curated bundles — each item was chosen to work together for the same scenario.`)
    : (zh ? '我為你整理了一套搭配。' : 'I assembled a curated bundle for you.');
  const mem = memoryNote ? ` ${memoryNote}` : '';
  return `${understood} ${bundleNote}${mem}`;
}

// ---------------------------------------------------------------------------
// Tool-calling agent (the deployed path).
//
// The agent routes the query to tools, runs them, and composes an answer that may
// only quote the facts those tools returned. The template assistant above is kept
// as a fallback, so a router failure degrades to something rather than nothing.
// ---------------------------------------------------------------------------
export async function runAssistant(query, lang = 'zh') {
  try {
    const { runAgent } = await import('./agent/index.js');
    const res = await runAgent(query, lang);
    if (res && res.answer) return res;
  } catch (err) {
    console.warn('  agent failed, falling back to templates:', err.message);
  }
  const legacy = runAssistantLegacy(query, lang);
  return { ...legacy, engine: 'template-fallback', tools: [], citations: [] };
}
