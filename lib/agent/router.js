// lib/agent/router.js
// Deterministic intent router: query -> plan of tool calls.
//
// This is the piece an LLM would replace. Everything downstream (tools, facts,
// answer composition) stays identical whether the plan came from these rules or
// from a model, which is what makes the grounding guarantee independent of the
// router. Set ASSISTANT_LLM=1 to hand routing to a model later.

const norm = (s) => String(s || '').toLowerCase();

const INTENTS = [
  {
    id: 'price_timing',
    // "should I wait for a sale" — the highest-value question the site can answer
    zh: ['會唔會減', '會減價', '減價', '跌價', '值得等', '等唔等', '幾時買', '幾時最平', '平啲', '便宜'],
    en: ['price drop', 'get cheaper', 'cheaper', 'worth waiting', 'wait for', 'buy now or wait',
      'forecast', 'discount', 'best time to buy', 'go down in price', 'price'],
    needsProduct: true,
  },
  {
    id: 'availability',
    zh: ['有冇貨', '有貨', '缺貨', '斷貨', '現貨', '邊間', '分店', '門市', '取貨', '自取', '幾時到'],
    en: ['in stock', 'out of stock', 'available', 'which store', 'pickup', 'pick up',
      'collect', 'stock', 'do you have'],
    needsProduct: true,
  },
  {
    id: 'size',
    zh: ['咩碼', '乜碼', '幾多碼', '尺碼', '碼數', '大細', '合身', '偏大', '偏細'],
    en: ['what size', 'which size', 'size', 'fit', 'runs small', 'runs large'],
    needsProduct: true,
  },
  {
    id: 'outfit',
    // Deliberately excludes bare occasion nouns (婚禮/滑雪/旅行): "滑雪外套會唔會
    // 減價" is a price question, not a request to build a look. Only an explicit
    // "what should I wear / put a look together" cue triggers this intent.
    zh: ['穿咩', '著咩', '穿什麼', '穿甚麼', '著什麼', '該穿', '怎麼穿',
      '配搭', '搭配', '襯咩', '點襯', '造型', '場合', '幫我配', '整套', '推介'],
    en: ['what to wear', 'what should i wear', 'outfit', 'look for', 'style for',
      'put together', 'pair with', 'suggest a look'],
    needsProduct: false,
  },
  {
    id: 'stores',
    zh: ['門市喺邊', '門市地址', '分店地址', '邊度有門市', '營業時間'],
    en: ['store address', 'where is your store', 'opening hours', 'store list'],
    needsProduct: false,
  },
];

const SIZE_RE = /\b(xxs|xs|s|m|l|xl|xxl|2xl)\b/i;
const BUDGET_RE = /(?:預算|budget|under|below|within|about|大約|左右)\D{0,8}(\d{2,6})|(\d{3,6})\s*(?:蚊|元|hkd|hk\$|usd|\$)?/i;

export function extractEntities(query, lang = 'zh') {
  const q = norm(query);
  const entities = { size: null, budget: null };

  const sizeMatch = query.match(SIZE_RE);
  if (sizeMatch) entities.size = sizeMatch[1].toUpperCase();

  // Chinese size words
  if (/中碼/.test(query)) entities.size = 'M';
  if (/大碼/.test(query)) entities.size = 'L';
  if (/細碼|小碼/.test(query)) entities.size = 'S';

  const budgetMatch = query.match(BUDGET_RE);
  if (budgetMatch) {
    const raw = Number(budgetMatch[1] || budgetMatch[2]);
    if (Number.isFinite(raw) && raw >= 50 && raw <= 100000) {
      // The catalogue stores USD; shoppers in zh think in HKD.
      entities.budget = lang === 'en' ? raw : Math.round((raw / 7.8) * 100) / 100;
      entities.budgetRaw = raw;
    }
  }
  return entities;
}

/**
 * @returns {{intents:string[], entities:object, plan:Array<{tool:string,params:object,id:string}>}}
 */
export function route(query, lang = 'zh') {
  const q = norm(query);
  const intents = [];
  for (const intent of INTENTS) {
    const words = lang === 'en' ? intent.en : [...intent.zh, ...intent.en];
    if (words.some((w) => q.includes(norm(w)))) intents.push(intent.id);
  }
  const entities = extractEntities(query, lang);

  // "我著咩碼好" contains the outfit cue 著咩 but is really a sizing question.
  // A size intent wins unless the query also asks to style a look.
  if (intents.includes('size') && intents.includes('outfit')
      && !/配搭|搭配|造型|場合|整套|outfit|look/.test(q)) {
    intents.splice(intents.indexOf('outfit'), 1);
  }

  // A bare product lookup is the fallback intent.
  if (!intents.length) intents.push('product_search');

  // Budget/scenario language alone means "build me a look".
  if (entities.budget != null && !intents.includes('outfit') && intents.length === 1
      && intents[0] === 'product_search') {
    intents.push('outfit');
  }

  const plan = [];
  const productIntents = intents.filter((i) => INTENTS.find((x) => x.id === i)?.needsProduct);

  if (productIntents.length) {
    // Resolve the product once, then let the product-specific tools use it.
    plan.push({ tool: 'search_products', params: { query, maxPrice: entities.budget, limit: 4 }, id: 'find' });
    for (const intent of productIntents) {
      const tool = intent === 'price_timing' ? 'forecast_price'
        : intent === 'availability' ? 'check_store_stock'
          : 'size_advice';
      plan.push({ tool, params: { productId: '$find.top', size: entities.size }, id: intent });
    }
  }

  if (intents.includes('outfit')) {
    // Recall what they already own first, so the look is built around it rather
    // than selling a whole new wardrobe.
    plan.push({ tool: 'recall_wardrobe', params: { limit: 6 }, id: 'memory' });
    plan.push({ tool: 'build_outfit', params: { query, budget: entities.budget }, id: 'outfit' });
  }
  if (intents.includes('stores')) {
    plan.push({ tool: 'list_stores', params: { district: null }, id: 'stores' });
  }
  if (intents.includes('product_search') && !plan.length) {
    plan.push({ tool: 'search_products', params: { query, maxPrice: entities.budget, limit: 6 }, id: 'find' });
  }

  return { intents, entities, plan };
}

export { INTENTS };
