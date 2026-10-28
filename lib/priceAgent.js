// lib/priceAgent.js
// Automated cross-platform price comparison & negotiation agent.
//
// Scans simulated marketplace listings for a basket, surfaces the best landed
// price, auto-claims available coupons, then runs a (simulated) bulk inquiry /
// haggling dialogue with the winning seller.
//
// Compliance: the agent only reads publicly listed prices and negotiates
// through channels the marketplace sanctions — it never scrapes private data or
// bypasses platform rules. A production build would replace the simulated
// listings with licensed marketplace APIs / affiliate feeds and the dialogue
// with a real LLM-driven negotiation policy.
import { getProduct } from './store.js';
import { seededRandom } from './store.js';

export const PLATFORMS = [
  { id: 'shopee', name: '蝦皮購物', name_en: 'Shopee', color: '#ee4d2d', bias: -0.06, ship: 0, shipBase: 0, couponChance: 0.75, delivery: [3, 6], rating: 4.3, official: false },
  { id: 'momo', name: 'momo購物網', name_en: 'momo', color: '#d4007f', bias: 0.015, ship: 1.5, shipBase: 2.5, couponChance: 0.6, delivery: [1, 3], rating: 4.5, official: false },
  { id: 'pchome', name: 'PChome 24h', name_en: 'PChome 24h', color: '#0057b8', bias: 0.045, ship: 0, shipBase: 0, couponChance: 0.35, delivery: [1, 2], rating: 4.6, official: false },
  { id: 'yahoo', name: 'Yahoo奇摩購物', name_en: 'Yahoo Shopping', color: '#6001d2', bias: 0.03, ship: 1.2, shipBase: 2.0, couponChance: 0.55, delivery: [2, 4], rating: 4.4, official: false },
  { id: 'ruten', name: '露天拍賣', name_en: 'Ruten', color: '#e8a33d', bias: -0.1, ship: 1.8, shipBase: 3.0, couponChance: 0.2, delivery: [4, 9], rating: 4.0, official: false },
  { id: 'official', name: '品牌官方旗艦店', name_en: 'Brand Official Store', color: '#0f766e', bias: 0.075, ship: 0, shipBase: 0, couponChance: 0.45, delivery: [2, 4], rating: 4.8, official: true },
  { id: 'amazonjp', name: 'Amazon JP', name_en: 'Amazon JP', color: '#ff9900', bias: 0.05, ship: 4.5, shipBase: 6.0, couponChance: 0.25, delivery: [5, 12], rating: 4.7, official: false },
];

const COUPON_POOL = [
  { code: 'NEW150', label: '新客折 HK$150', label_en: 'New member HK$150 off', discountPct: 0.08 },
  { code: 'SHIP0', label: '免運券', label_en: 'Free shipping', discountPct: 0.04 },
  { code: 'SEASON12', label: '季節限定 12% off', label_en: 'Seasonal 12% off', discountPct: 0.12 },
  { code: 'BULK200', label: '滿額折 HK$200', label_en: 'Spend HK$200, save more', discountPct: 0.1 },
  { code: 'APP5', label: 'App 下單 5% off', label_en: 'App order 5% off', discountPct: 0.05 },
  { code: 'WINTER8', label: '冬季裝備 8% off', label_en: 'Winter gear 8% off', discountPct: 0.08 },
];

function buildOffers(product, lang = 'zh') {
  const rand = seededRandom(`offers-${product.id}`);
  return PLATFORMS.map((plat) => {
    const noise = (rand() - 0.5) * 0.07;
    const price = Math.round(product.price * (1 + plat.bias + noise) * 100) / 100;
    const shipping = Math.round((plat.shipBase + (rand() < 0.4 ? plat.ship : 0)) * 100) / 100;

    let coupon = null;
    if (rand() < plat.couponChance) {
      const c = COUPON_POOL[Math.floor(rand() * COUPON_POOL.length)];
      const discount = Math.round(price * c.discountPct * 100) / 100;
      coupon = { ...c, discount, claimable: true };
    }

    const finalPrice = Math.round((price + shipping - (coupon ? coupon.discount : 0)) * 100) / 100;
    const deliveryDays = plat.delivery[0] + Math.floor(rand() * (plat.delivery[1] - plat.delivery[0] + 1));
    const rating = Math.round((plat.rating + (rand() - 0.5) * 0.4) * 10) / 10;

    return {
      platform: { id: plat.id, name: plat.name, name_en: plat.name_en, color: plat.color, official: plat.official },
      price,
      shipping,
      coupon,
      finalPrice,
      deliveryDays,
      rating,
      stock: rand() < 0.9 ? (rand() < 0.3 ? 'low' : 'in') : 'out',
      inStock: true,
    };
  }).map((o) => ({ ...o, inStock: o.stock !== 'out' }))
    .sort((a, b) => a.finalPrice - b.finalPrice);
}

function negotiate({ product, bestOffer, rank, lang = 'zh' }) {
  const zh = lang !== 'en';
  const rand = seededRandom(`nego-${product.id}`);
  const round2 = (n) => Math.round(n * 100) / 100;

  const bulkDiscountPct = 0.045 + rand() * 0.05; // 4.5% - 9.5%
  const freeShip = rand() < 0.65;
  const gift = rand() < 0.4;

  const listPrice = bestOffer.price;
  const negotiated = round2(listPrice * (1 - bulkDiscountPct));
  const shippingWaived = freeShip ? bestOffer.shipping : 0;
  const couponKept = bestOffer.coupon ? bestOffer.coupon.discount : 0;
  const finalPrice = round2(Math.max(0.01, negotiated + bestOffer.shipping - shippingWaived - couponKept));

  const sellerName = bestOffer.platform.name;
  const transcript = zh
    ? [
        { role: 'agent', text: `你好，我是 SmartMall 的採購代理。我想一次購買「${product.name_zh}」等 ${rank} 件裝備，請問有批量優惠嗎？` },
        { role: 'seller', text: `您好！這批貨目前是 ${sellerName} 出貨，滿額可以給您 ${Math.round(bulkDiscountPct * 100)}% 折扣。` },
        { role: 'agent', text: `了解。如果我們今天下單、並使用平台的新客／季節券，是否能再免運？我們之後還有其他團購需求。` },
        { role: 'seller', text: freeShip
            ? '可以，這單我幫您吸收運費。' + (gift ? '另外再送一個原廠收納袋。' : '')
            : '運費部分我沒辦法全免，但我可以再折一點給您。' },
        { role: 'agent', text: '成交，麻煩幫我保留庫存，我現在就送出訂單。' },
        { role: 'seller', text: '已為您保留，訂單成立後 24 小時內出貨，謝謝！' },
      ]
    : [
        { role: 'agent', text: `Hi, I'm SmartMall's buying agent. I'd like to order ${rank} items including the "${product.name}". Do you offer a bulk price?` },
        { role: 'seller', text: `Hello! This ships from ${sellerName}. For an order this size I can apply ${Math.round(bulkDiscountPct * 100)}% off.` },
        { role: 'agent', text: `Understood. If we order today and use the platform coupon, could you also waive shipping? We have more group orders coming.` },
        { role: 'seller', text: freeShip
            ? 'Sure, I will cover the shipping on this one.' + (gift ? ' I will add a branded storage pouch as well.' : '')
            : 'I cannot waive shipping entirely, but I can take a little more off the price.' },
        { role: 'agent', text: 'Deal. Please hold the stock — I am placing the order now.' },
        { role: 'seller', text: 'Reserved for you. It ships within 24 hours of the order being confirmed. Thank you!' },
      ];

  const perks = [];
  if (freeShip) perks.push({ zh: '免運費', en: 'Free shipping' });
  if (gift) perks.push({ zh: '贈品：原廠收納袋', en: 'Free branded pouch' });
  if (bestOffer.coupon) perks.push({ zh: `優惠券 ${bestOffer.coupon.code}`, en: `Coupon ${bestOffer.coupon.code}` });
  perks.push({ zh: '保留庫存 24 小時', en: 'Stock held for 24 hours' });

  return {
    seller: bestOffer.platform,
    transcript,
    listPrice,
    negotiatedPrice: negotiated,
    shippingWaived,
    couponApplied: couponKept,
    finalPrice,
    discount: round2(listPrice - negotiated),
    discountPct: Math.round(bulkDiscountPct * 1000) / 10,
    perks,
  };
}

export function runPriceAgent({ productIds = [], lang = 'zh' } = {}) {
  const products = productIds.map(getProduct).filter(Boolean);
  if (!products.length) return { error: 'no products' };

  const items = products.map((product) => {
    const offers = buildOffers(product, lang);
    const inStockOffers = offers.filter((o) => o.inStock);
    const best = inStockOffers[0] || offers[0];
    const worst = offers[offers.length - 1];
    const savings = Math.round((worst.finalPrice - best.finalPrice) * 100) / 100;
    return {
      product,
      offers,
      best,
      savings: { amount: savings, pct: Math.round((savings / worst.finalPrice) * 1000) / 10 },
    };
  });

  // Negotiate the basket as a whole, anchored on the highest-value item.
  const anchor = items.slice().sort((a, b) => b.product.price - a.product.price)[0];
  const nego = negotiate({ product: anchor.product, bestOffer: anchor.best, rank: items.length, lang });

  const couponsClaimed = [];
  for (const it of items) {
    const withCoupon = it.offers.filter((o) => o.coupon);
    if (withCoupon.length) {
      couponsClaimed.push({
        productId: it.product.id, productName: it.product.name, productName_zh: it.product.name_zh,
        platform: withCoupon[0].platform, coupon: withCoupon[0].coupon,
      });
    }
  }

  const originalTotal = Math.round(items.reduce((s, it) => s + it.product.price, 0) * 100) / 100;
  const bestTotal = Math.round(items.reduce((s, it) => s + it.best.finalPrice, 0) * 100) / 100;
  // Apply the negotiated basket discount across every item.
  const negotiatedTotal = Math.round(bestTotal * (1 - nego.discountPct / 100) * 100) / 100;
  const totalSavings = Math.round((originalTotal - negotiatedTotal) * 100) / 100;

  const zh = lang !== 'en';
  return {
    items: items.map((it) => ({
      productId: it.product.id,
      product: { id: it.product.id, name: it.product.name, name_zh: it.product.name_zh, emoji: it.product.emoji, color: it.product.color, price: it.product.price, subcategory: it.product.subcategory },
      offers: it.offers,
      best: it.best,
      savings: it.savings,
    })),
    negotiation: nego,
    coupons: couponsClaimed,
    summary: {
      itemCount: items.length,
      platformsScanned: PLATFORMS.length,
      listingsCompared: items.length * PLATFORMS.length,
      couponsClaimed: couponsClaimed.length,
      originalTotal,
      bestTotal,
      negotiatedTotal,
      totalSavings,
      savingsPct: Math.round((totalSavings / originalTotal) * 1000) / 10,
    },
    compliance: zh
      ? '代理僅讀取各平台公開標價，並透過平台允許的詢價／議價管道進行，不涉及爬取非公開資料或規避平台規則。'
      : 'The agent only reads publicly listed prices and negotiates through marketplace-sanctioned channels. It does not scrape private data or bypass platform rules.',
  };
}
