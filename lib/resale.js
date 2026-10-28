// lib/resale.js
// One-click second-hand consignment — closes the buy → wear → resell loop.
//
// The "AI" drafts the listing (title, description, tags, price) from the
// product's own attributes plus wear history, then publishes it to the
// marketplace where another shopper can buy it. Production would generate the
// copy with an LLM and price it with a demand model; the draft/listing contract
// stays the same.
import { getProduct, getProfile, getWardrobe, seededRandom } from './store.js';

const CONDITION = {
  like_new: { label: '近全新', label_en: 'Like new', factor: 0.76 },
  good: { label: '良好', label_en: 'Good', factor: 0.56 },
  fair: { label: '尚可', label_en: 'Fair', factor: 0.4 },
  worn: { label: '明顯使用', label_en: 'Well worn', factor: 0.26 },
};

// Category demand multiplier (winter gear peaks in season, etc.)
const DEMAND = {
  'Winter & Snow': 1.14,
  Footwear: 1.05,
  Accessories: 1.02,
  Apparel: 0.98,
  Electronics: 1.08,
  Beauty: 0.82,
  Home: 0.9,
};

const ECO = {
  Apparel: { co2: 10.5, water: 2400 },
  'Winter & Snow': { co2: 14.2, water: 2100 },
  Footwear: { co2: 13.1, water: 1700 },
  Accessories: { co2: 6.4, water: 700 },
  Electronics: { co2: 42.0, water: 320 },
  Beauty: { co2: 3.1, water: 180 },
  Home: { co2: 8.8, water: 600 },
};

function priceFor(product, condition, monthsOwned, rand) {
  const cf = (CONDITION[condition] || CONDITION.good).factor;
  const years = Math.max(0, monthsOwned) / 12;
  const ageFactor = Math.max(0.55, 1 - years * 0.13);
  const demand = DEMAND[product.category] || 1;
  const raw = product.price * cf * ageFactor * demand;
  // Charm pricing: round to the nearest whole unit ending in 0/5/9.
  const rounded = Math.max(2, Math.round(raw));
  const ends = [0, 5, 9];
  const candidates = ends.map((e) => Math.round(rounded / 10) * 10 + e).filter((v) => v > 0);
  return candidates.reduce((best, v) => (Math.abs(v - raw) < Math.abs(best - raw) ? v : best), candidates[0]);
}

export function draftListing({ productId, condition = 'good', monthsOwned = 6, wears = null, note = '', lang = 'zh' }) {
  const product = getProduct(productId);
  if (!product) return null;
  const rand = seededRandom(`resale-${productId}-${condition}`);
  const zh = lang !== 'en';
  const cond = CONDITION[condition] || CONDITION.good;
  const price = priceFor(product, condition, monthsOwned, rand);
  const eco = ECO[product.category] || ECO.Apparel;

  const wearNote = wears != null ? wears : Math.max(3, Math.round(monthsOwned * 1.8));
  const title = zh
    ? `【二手】${product.name_zh}｜${cond.label}｜${product.colorName}`
    : `[Pre-owned] ${product.name} — ${cond.label_en}, ${product.colorName}`;

  const descZh = [
    `品牌：${product.brand}`,
    `顏色：${product.colorName}　材質：${product.material}`,
    `購入約 ${monthsOwned} 個月，實際穿著約 ${wearNote} 次，${cond.label}。`,
    note ? `賣家補充：${note}` : `保存良好，已送專業清洗消毒。`,
    `原價 HK$${Math.round(product.price * 7.8).toLocaleString()}，現售 HK$${Math.round(price * 7.8).toLocaleString()}。`,
    `適合：${product.occasion.slice(0, 3).join('、')}。`,
    `♻️ 這筆交易預估可減少 ${eco.co2.toFixed(1)} kg CO₂e 與 ${eco.water.toLocaleString()} L 用水。`,
  ].join('\n');

  const descEn = [
    `Brand: ${product.brand}`,
    `Colour: ${product.colorName}   Material: ${product.material}`,
    `Owned about ${monthsOwned} months, worn roughly ${wearNote} times. Condition: ${cond.label_en}.`,
    note ? `Seller note: ${note}` : 'Kept in great shape, professionally cleaned and sanitised.',
    `Original US$${product.price.toFixed(2)} — now US$${price.toFixed(2)}.`,
    `Great for: ${product.occasion.slice(0, 3).join(', ')}.`,
    `♻️ Estimated saving: ${eco.co2.toFixed(1)} kg CO2e and ${eco.water.toLocaleString()} L of water.`,
  ].join('\n');

  const tags = [
    product.category,
    product.subcategory,
    product.colorName,
    product.material,
    ...product.style.slice(0, 2),
    cond.label,
  ];

  const range = {
    low: Math.max(2, Math.round(price * 0.88)),
    high: Math.round(price * 1.16),
  };

  return {
    productId,
    product: { id: product.id, name: product.name, name_zh: product.name_zh, emoji: product.emoji, color: product.color, brand: product.brand, price: product.price, image: product.image || null },
    title,
    description: descEn,
    description_zh: descZh,
    price,
    originalPrice: product.price,
    discountPct: Math.round((1 - price / product.price) * 100),
    priceRange: range,
    condition,
    conditionLabel: { zh: cond.label, en: cond.label_en },
    monthsOwned,
    wears: wearNote,
    tags,
    eco: { co2: eco.co2, water: eco.water },
    suggestedDurationDays: Math.round(6 + rand() * 12),
    demandNote: zh
      ? `${product.category === 'Winter & Snow' ? '冬季裝備需求正旺，' : ''}同類商品平均 ${Math.round(5 + rand() * 9)} 天內售出。`
      : `${product.category === 'Winter & Snow' ? 'Winter gear is in demand — ' : ''}similar items sell in about ${Math.round(5 + rand() * 9)} days.`,
  };
}

// --- Marketplace store -----------------------------------------------------
let seq = 1000;
const listings = [];

function addListing(listing) {
  listings.unshift(listing);
  return listing;
}

// Seed the marketplace with other members' listings so it feels alive.
function seed() {
  const seeds = [
    { productId: 'p007', condition: 'good', monthsOwned: 14, seller: { name: '阿欣', name_en: 'Yan', avatar: '👩', rating: 4.9 } },
    { productId: 'p017', condition: 'like_new', monthsOwned: 5, seller: { name: 'Kelvin', name_en: 'Kelvin', avatar: '🧑‍💼', rating: 4.7 } },
    { productId: 'p014', condition: 'fair', monthsOwned: 18, seller: { name: '小美', name_en: 'Mei', avatar: '👧', rating: 4.8 } },
    { productId: 'p039', condition: 'like_new', monthsOwned: 3, seller: { name: '滑雪阿伯', name_en: 'Snow Uncle', avatar: '🧔', rating: 5.0 } },
    { productId: 'p029', condition: 'good', monthsOwned: 8, seller: { name: 'Wing', name_en: 'Wing', avatar: '🧑', rating: 4.6 } },
  ];
  for (const s of seeds) {
    const draft = draftListing({ productId: s.productId, condition: s.condition, monthsOwned: s.monthsOwned, lang: 'zh' });
    if (!draft) continue;
    seq += 1;
    addListing({
      id: `R-${seq}`,
      ...draft,
      seller: s.seller,
      status: 'active',
      views: 40 + Math.floor(Math.random() * 260),
      watchers: 2 + Math.floor(Math.random() * 18),
      listedAt: new Date(Date.now() - (2 + Math.floor(Math.random() * 20)) * 86400000).toISOString(),
      aiGenerated: false,
      mine: false,
    });
  }
  // The shopper already has one item listed, so the loop is visible on load.
  const own = draftListing({ productId: 'p010', condition: 'fair', monthsOwned: 11, lang: 'zh' });
  if (own) {
    seq += 1;
    addListing({
      id: `R-${seq}`,
      ...own,
      seller: { name: getProfile().user.name, name_en: getProfile().user.name_en, avatar: getProfile().user.avatar, rating: 4.9 },
      status: 'active',
      views: 62,
      watchers: 7,
      listedAt: new Date(Date.now() - 6 * 86400000).toISOString(),
      aiGenerated: true,
      mine: true,
    });
  }
}
seed();

export function getListings() {
  return listings;
}

export function publishListing({ productId, condition, monthsOwned, wears, note, price, lang = 'zh' }) {
  const draft = draftListing({ productId, condition, monthsOwned, wears, note, lang });
  if (!draft) return null;
  seq += 1;
  const profile = getProfile();
  return addListing({
    id: `R-${seq}`,
    ...draft,
    price: price != null ? price : draft.price,
    seller: { name: profile.user.name, name_en: profile.user.name_en, avatar: profile.user.avatar, rating: 4.9 },
    status: 'active',
    views: 0,
    watchers: 0,
    listedAt: new Date().toISOString(),
    aiGenerated: true,
    mine: true,
  });
}

export function buyListing(id) {
  const l = listings.find((x) => x.id === id);
  if (!l || l.status !== 'active') return null;
  l.status = 'sold';
  l.soldAt = new Date().toISOString();
  return l;
}

// Wardrobe items eligible for consignment (not already listed).
export function consignableItems() {
  const listed = new Set(listings.filter((l) => l.mine && l.status === 'active').map((l) => l.productId));
  return getWardrobe()
    .filter((w) => !listed.has(w.productId))
    .map((w) => {
      const draft = draftListing({ productId: w.productId, condition: w.condition, monthsOwned: w.monthsAgo, wears: w.wears, lang: 'zh' });
      return { ...w, draft };
    });
}

export function ecoSummary() {
  const mine = listings.filter((l) => l.mine);
  const sold = mine.filter((l) => l.status === 'sold');
  const pool = sold.length ? sold : mine;
  return {
    itemsRecirculated: mine.length,
    itemsSold: sold.length,
    co2Saved: Math.round(pool.reduce((s, l) => s + l.eco.co2, 0) * 10) / 10,
    waterSaved: pool.reduce((s, l) => s + l.eco.water, 0),
    earnings: Math.round(mine.reduce((s, l) => s + l.price, 0) * 100) / 100,
  };
}

export function conditionOptions(lang = 'zh') {
  const zh = lang !== 'en';
  return Object.entries(CONDITION).map(([k, v]) => ({ value: k, label: zh ? v.label : v.label_en, factor: v.factor }));
}
