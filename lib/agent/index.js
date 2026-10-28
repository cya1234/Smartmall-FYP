// lib/agent/index.js
// The orchestrator: route -> run tools -> compose an answer that may only quote
// facts the tools returned.
//
// Why this matters: the previous assistant composed sentences from templates and
// could drift from the catalogue. Here the composer receives a `facts` map and
// nothing else, so every price, stock count, size and date in the answer is
// traceable to a tool call. `tools[]` is returned to the client so the UI (and a
// grader) can audit what happened.
import { route } from './router.js';
import { runTool, searchProducts } from './tools.js';
import { getProduct } from '../store.js';

const pname = (p, lang) => (lang === 'en' ? (p.name || p.name_zh) : (p.name_zh || p.name));

function money(p, lang) {
  const rate = lang === 'en' ? 1 : 7.8;
  const sym = lang === 'en' ? 'US$' : 'HK$';
  return `${sym}${(p.price * rate).toLocaleString(lang === 'en' ? 'en-US' : 'zh-HK', { maximumFractionDigits: 0 })}`;
}

function factMap(steps) {
  const map = {};
  for (const s of steps) for (const f of s.facts) map[`${s.id}.${f.label}`] = f.value;
  return map;
}

function compose({ intents, entities, steps, lang }) {
  const f = factMap(steps);
  const sentences = [];
  const t = (zh, en) => (lang === 'en' ? en : zh);

  // A product-dependent tool that never ran because the query named no product.
  const needsClarification = (id) => steps.some((s) => s.id === id && s.error === 'no product');
  const askWhich = () => t('你指的是哪一件商品？講個名或類別我就可以幫你查。',
    'Which product do you mean? Name it or give me a category and I will look it up.');

  const find = steps.find((s) => s.id === 'find');
  const topProduct = find?.ok && find.data?.length ? find.data[0] : null;

  if (intents.includes('product_search') && find) {
    if (!find.data?.length) {
      sentences.push(t('找不到符合的商品，試試換個關鍵字或放寬預算。',
        'No products matched. Try a different keyword or a wider budget.'));
    } else {
      sentences.push(t(
        `找到 ${f['find.matches']} 件相關商品，最接近的是「${f['find.top']}」，${f['find.topPrice']}，評分 ${f['find.topRating']}。`,
        `Found ${f['find.matches']} matches. Closest is "${f['find.top']}" at ${f['find.topPrice']}, rated ${f['find.topRating']}.`));
    }
  }

  if (intents.includes('price_timing') && steps.find((s) => s.id === 'price_timing')) {
    const s = steps.find((x) => x.id === 'price_timing');
    if (needsClarification('price_timing')) {
      sentences.push(askWhich());
    } else if (!s.ok) {
      sentences.push(t('暫時計不到價格走勢。', 'I could not compute a price forecast right now.'));
    } else {
      const action = f['price_timing.action'];
      const drop = Number(f['price_timing.dropPct']);
      const horizon = f['price_timing.horizonDays'];
      const eventKey = Object.keys(f).find((k) => k.startsWith('price_timing.event:'));
      const event = eventKey ? f[eventKey] : null;
      if (action === 'wait' && drop > 0) {
        sentences.push(t(
          `價格方面：建議等。未來 ${horizon} 天內預計下跌約 ${drop}%，信心 ${f['price_timing.confidence']}${event ? `；最近的購物節是 ${event}` : ''}。現在買很可能買貴。`,
          `On price: wait. The model expects roughly a ${drop}% drop within ${horizon} days (confidence ${f['price_timing.confidence']})${event ? `, closest sale ${event}` : ''}. Buying now likely overpays.`));
      } else {
        sentences.push(t(
          `價格方面：建議現在買。未來 ${horizon} 天沒有明顯降價訊號（信心 ${f['price_timing.confidence']}），等下去通常省不到錢。`,
          `On price: buy now. No meaningful drop is projected over ${horizon} days (confidence ${f['price_timing.confidence']}), so waiting is unlikely to help.`));
      }
      sentences.push(t(`（模型：${f['price_timing.engine'] === 'prophet' ? 'Meta Prophet' : '線性回歸'}）`,
        `(engine: ${f['price_timing.engine'] === 'prophet' ? 'Meta Prophet' : 'linear regression'})`));
    }
  }

  if (intents.includes('availability')) {
    const s = steps.find((x) => x.id === 'availability');
    if (needsClarification('availability')) {
      sentences.push(askWhich());
    } else if (!s.ok) {
      sentences.push(t('暫時查不到庫存。', 'Stock lookup is unavailable right now.'));
    } else if (f['availability.status'] === 'online') {
      sentences.push(t(
        `庫存方面：線上仲有 ${f['availability.onlineStock']} 件，另外 ${f['availability.storeCount']} 間門市共 ${f['availability.totalStoreQty']} 件。最近是${f['availability.nearestStore']}（${f['availability.nearestMtr']}）。${f['availability.pickup']}。`,
        `Stock: ${f['availability.onlineStock']} left online, plus ${f['availability.totalStoreQty']} units across ${f['availability.storeCount']} stores. Nearest is ${f['availability.nearestStore']} (${f['availability.nearestMtr']}). ${f['availability.pickup']}.`));
    } else if (Number(f['availability.storeCount']) > 0) {
      sentences.push(t(
        `線上缺貨，但 ${f['availability.storeCount']} 間門市有現貨（共 ${f['availability.totalStoreQty']} 件）：${f['availability.stores']}。最近是${f['availability.nearestStore']}（${f['availability.nearestMtr']}），${f['availability.pickup']}，我幫你導航過去就可以。`,
        `Sold out online, but ${f['availability.storeCount']} stores have it (${f['availability.totalStoreQty']} units): ${f['availability.stores']}. Nearest is ${f['availability.nearestStore']} (${f['availability.nearestMtr']}). ${f['availability.pickup']}.`));
    } else {
      sentences.push(t('線上和門市都暫時缺貨。', 'Out of stock online and in store.'));
    }
  }

  if (intents.includes('size')) {
    const s = steps.find((x) => x.id === 'size');
    if (needsClarification('size')) {
      sentences.push(askWhich());
    } else if (!s.ok) {
      sentences.push(t('暫時算不到尺碼建議。', 'I could not compute a size recommendation.'));
    } else {
      sentences.push(t(
        `尺碼方面：建議 ${f['size.recommendedSize']}，退貨風險 ${f['size.riskLevel']}${f['size.returnRiskPct'] ? `（約 ${f['size.returnRiskPct']}%）` : ''}。`,
        `On sizing: ${f['size.recommendedSize']}, return risk ${f['size.riskLevel']}${f['size.returnRiskPct'] ? ` (~${f['size.returnRiskPct']}%)` : ''}.`));
      if (f['size.note']) sentences.push(f['size.note']);
    }
  }

  if (intents.includes('outfit')) {
    const s = steps.find((x) => x.id === 'outfit');
    if (!s.ok || !s.data) {
      sentences.push(t('暫時配不到整套，試試描述得更具體。', 'I could not assemble a look — try describing the occasion more concretely.'));
    } else {
      const items = Number(f['outfit.items']);
      if (f['outfit.shortfall'] === 'yes') {
        sentences.push(t(
          `全副裝備最少要 ${f['outfit.minEssentialDisplay']}，你的預算 ${f['outfit.budgetDisplay']} 差一點，所以先配了 ${items} 件（${f['outfit.totalDisplay']}），還欠 ${f['outfit.missing']} 類單品。要提高預算，或者我可以先做最必要的幾件。`,
          `A complete kit needs at least ${f['outfit.minEssentialDisplay']}; your budget of ${f['outfit.budgetDisplay']} is short, so I picked ${items} item(s) (${f['outfit.totalDisplay']}) and ${f['outfit.missing']} categories are still missing. Raise the budget, or I can prioritise the essentials.`));
      } else {
        sentences.push(t(
          `為你配了 ${items} 件${f['outfit.scenario'] ? `（${f['outfit.scenario']}）` : ''}，合共 ${f['outfit.totalDisplay']}。`,
          `I put together ${items} pieces${f['outfit.scenario'] ? ` for ${f['outfit.scenario']}` : ''}, totalling ${f['outfit.totalDisplay']}.`));
      }
    }
  }

  if (intents.includes('stores')) {
    const s = steps.find((x) => x.id === 'stores');
    if (s.ok) {
      sentences.push(t(
        `我們有 ${f['stores.storeCount']} 間門市：${f['stores.districts']}。全都可以即日取貨。`,
        `We have ${f['stores.storeCount']} stores: ${f['stores.districts']}. Same-day pickup at all of them.`));
    }
  }

  if (topProduct && !intents.includes('product_search')) {
    sentences.unshift(t(`我睇緊「${pname(topProduct, lang)}」（${money(topProduct, lang)}）。`,
      `Looking at "${pname(topProduct, lang)}" (${money(topProduct, lang)}).`));
  }

  // Wardrobe recall: the differentiator is "build around what you own".
  if (intents.includes('outfit') && Number(f['memory.ownedCount']) > 0) {
    sentences.unshift(t(
      `你衣櫃已經有「${f['memory.recent']}」（${f['memory.recentMonths']} 個月前買），我會以它為基礎來配。`,
      `You already own "${f['memory.recent']}" (bought ${f['memory.recentMonths']} months ago), so I built the look around it.`));
  }

  return sentences.join(lang === 'en' ? ' ' : '');
}

/** Build the UI bundle shape from the agent's tool output. */
function buildBundles({ intents, steps, lang }) {
  const outfit = steps.find((s) => s.id === 'outfit');
  if (intents.includes('outfit') && outfit?.ok && outfit.data?.items?.length) {
    return [{
      title: lang === 'en' ? 'Complete look' : '整套配搭',
      title_zh: '整套配搭',
      items: outfit.data.items.map((it) => ({
        product: it.product || it,
        owned: Boolean(it.owned),
        role: it.role || null,
      })),
      total: outfit.data.total,
    }];
  }
  const find = steps.find((s) => s.id === 'find');
  if (find?.ok && find.data?.length) {
    return [{
      title: lang === 'en' ? 'Closest matches' : '最接近的選擇',
      title_zh: '最接近的選擇',
      items: find.data.slice(0, 6).map((p) => ({ product: p, owned: false })),
      total: find.data.slice(0, 6).reduce((n, p) => n + p.price, 0),
    }];
  }
  return [];
}

export async function runAgent(query, lang = 'zh') {
  const started = Date.now();
  const { intents, entities, plan } = route(query, lang);

  const steps = [];
  let findTopId = null;

  for (const step of plan) {
    const params = { ...step.params };
    if (params.productId === '$find.top') {
      if (!findTopId) {
        // Nothing resolved: skip the dependent tool rather than guessing.
        steps.push({ id: step.id, tool: step.tool, ok: false, data: null, facts: [], ms: 0, error: 'no product' });
        continue;
      }
      params.productId = findTopId;
    }
    const res = await runTool(step.tool, params, { lang });
    steps.push({ id: step.id, ...res });
    if (step.id === 'find' && res.ok && res.data?.length) {
      findTopId = res.data[0].id;
      // Attach the resolved product id so the UI can deep-link.
      step.resolvedProductId = findTopId;
    }
  }

  const answer = compose({ intents, entities, steps, lang });
  const bundles = buildBundles({ intents, steps, lang });
  const citations = steps.flatMap((s) => s.facts.map((f) => ({ step: s.id, tool: s.tool, ...f })));
  const top = findTopId ? getProduct(findTopId) : null;

  return {
    query,
    lang,
    engine: 'agent',
    intents,
    entities,
    understood: intents.join(' + '),
    answer,
    bundles,
    matchCount: steps.find((s) => s.id === 'find')?.data?.length || 0,
    alternatives: (steps.find((s) => s.id === 'find')?.data || []).slice(0, 6).map((p) => ({
      id: p.id, name: p.name, name_zh: p.name_zh, score: p._score, reason: null,
    })),
    resolvedProduct: top ? { id: top.id, name: pname(top, lang), image: top.image || null, price: top.price } : null,
    tools: steps.map((s) => ({
      id: s.id,
      tool: s.tool,
      ok: s.ok,
      ms: s.ms,
      factCount: s.facts.length,
      error: s.error || null,
    })),
    citations,
    grounded: true,
    tookMs: Date.now() - started,
    // Wardrobe items used, so the existing UI can render its memory strip.
    memoryUsed: (steps.find((s) => s.id === 'memory')?.data || []).slice(0, 3).map((w) => ({
      productId: w.productId,
      name: w.name,
      name_zh: w.name_zh,
      emoji: w.emoji || '🧺',
      color: w.color || '#cccccc',
      boughtLabel: w.purchasedLabel,
      boughtLabel_en: w.purchasedLabel_en,
      monthsAgo: w.monthsAgo,
    })),
    memoryNote: null,
    sizeAdvice: null,
  };
}

export { searchProducts };
