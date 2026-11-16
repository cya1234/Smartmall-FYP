// lib/agent/llmRouter.js
// Optional LLM classifier in front of the deterministic router.
//
// Scope is deliberately narrow: the model is asked to do exactly one thing — decide
// which intents a question expresses. It never sees the product catalogue, never
// produces a price, a size, a stock count or a tool argument, and never writes the
// answer. Entities still come from extractEntities() and the plan still comes from
// buildPlan(), so switching the router cannot make the assistant hallucinate.
//
// That narrowness is also what makes a small local model viable: classification is a
// few dozen output tokens, so a 1.5B-3B model is enough and fits beside CatVTON.
//
// Configure with environment variables:
//   ASSISTANT_LLM=1                          enable
//   LLM_URL=http://127.0.0.1:11434/v1        OpenAI-compatible base (Ollama or any)
//   LLM_MODEL=qwen2.5:3b-instruct
//   LLM_TIMEOUT_MS=2500
// With ASSISTANT_LLM unset everything behaves exactly as before.
import { ALLOWED_INTENTS, buildPlan, extractEntities } from './router.js';

const INTENT_HELP = `
price_timing  — whether to buy now or wait for a discount ("will it get cheaper")
availability  — stock, which store has it, pickup
size          — sizing, fit, runs small/large
outfit        — build or suggest a look for an occasion
stores        — store addresses, opening hours
product_search — a plain product lookup, no other intent applies
`.trim();

const SYSTEM = `You classify shopping questions for a Hong Kong apparel shop.
Questions are in English, Traditional Chinese, or Cantonese.
Return ONLY a JSON object: {"intents": ["..."]}
Use one or more of these exact identifiers:
${INTENT_HELP}
Rules:
- Never invent identifiers outside the list.
- Only an explicit question about timing or waiting ("will it drop", "should I wait",
  "幾時最平", "等唔等", "會唔會減價") is price_timing. A budget on its own is not.
- "which store has X", "邊間門市有", "有冇貨", "where can I pick up" are availability.
- "what should I wear", "著咩", "穿咩", "要著咩", "配搭" are outfit, even with a budget.
- "what size", "合身", "咩碼", "does it run small" are size.
- Store addresses and opening hours are stores.
- If nothing fits, answer product_search.
Output JSON only, no prose, no code fences.`;

const config = () => ({
  enabled: process.env.ASSISTANT_LLM === '1' || process.env.ASSISTANT_LLM === 'true',
  url: (process.env.LLM_URL || 'http://127.0.0.1:11434/v1').replace(/\/$/, ''),
  model: process.env.LLM_MODEL || 'qwen2.5:3b-instruct',
  timeoutMs: Number(process.env.LLM_TIMEOUT_MS) || 2500,
});

export function llmConfig() {
  const c = config();
  return { ...c, url: c.url };
}

/** Cheap cached health probe so a missing model costs one failed call, not every call. */
let health = { at: 0, ok: false };
const HEALTH_TTL = 15000;

export async function llmHealth({ force = false } = {}) {
  const c = config();
  if (!c.enabled) return { enabled: false, ok: false, model: c.model, url: c.url };
  const now = Date.now();
  if (!force && now - health.at < HEALTH_TTL) {
    return { enabled: true, ok: health.ok, model: c.model, url: c.url, cached: true };
  }
  try {
    const res = await fetch(`${c.url}/models`, { signal: AbortSignal.timeout(1500) });
    health = { at: now, ok: res.ok };
  } catch {
    health = { at: now, ok: false };
  }
  return { enabled: true, ok: health.ok, model: c.model, url: c.url };
}

/**
 * Load the model into memory ahead of the first question.
 *
 * Measured on an RTX 4070 with qwen2.5:3b-instruct: the first completion takes about
 * 53 s because the weights are being loaded, and every one after that takes ~114 ms.
 * With the 2.5 s classification timeout, that first question would always fall back
 * to the rule router — so call this at startup and the first real question is fast.
 */
export async function warmLLM({ timeoutMs = 180000 } = {}) {
  const c = config();
  if (!c.enabled) return { warmed: false, reason: 'disabled' };
  const t0 = Date.now();
  try {
    const res = await fetch(`${c.url}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: c.model,
        max_tokens: 1,
        keep_alive: '30m',
        messages: [{ role: 'user', content: 'hi' }],
      }),
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!res.ok) return { warmed: false, reason: `http_${res.status}` };
    return { warmed: true, ms: Date.now() - t0, model: c.model };
  } catch (err) {
    return { warmed: false, reason: err.name === 'TimeoutError' ? 'timeout' : 'unreachable', ms: Date.now() - t0 };
  }
}

/** Pull the first JSON object out of whatever the model returned. */function extractJson(text) {
  if (!text) return null;
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const body = fenced ? fenced[1] : text;
  const start = body.indexOf('{');
  const end = body.lastIndexOf('}');
  if (start < 0 || end <= start) return null;
  try {
    return JSON.parse(body.slice(start, end + 1));
  } catch {
    return null;
  }
}

/**
 * Ask the model for intents.
 * Returns {intents, latenciesMs, raw} or null — null always means "fall back to rules".
 */
export async function classifyWithLLM(query, lang = 'zh') {
  const c = config();
  if (!c.enabled) return null;

  const t0 = Date.now();
  let payload;
  try {
    const res = await fetch(`${c.url}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: c.model,
        temperature: 0,
        max_tokens: 64,
        messages: [
          { role: 'system', content: SYSTEM },
          { role: 'user', content: `${lang === 'zh' ? 'zh' : 'en'}: ${query}` },
        ],
        // Ollama unloads an idle model after 5 minutes; keeping it resident turns the
        // second request from 53 s into 114 ms. Ignored by servers that do not know it.
        keep_alive: '30m',
      }),
      signal: AbortSignal.timeout(c.timeoutMs),
    });
    if (!res.ok) return null;
    payload = await res.json();
  } catch {
    // Timeout, connection refused, malformed body — all mean the same thing.
    return null;
  }

  const text = payload?.choices?.[0]?.message?.content;
  const parsed = extractJson(text);
  if (!parsed || !Array.isArray(parsed.intents)) return null;

  // Strict validation: anything the model invents is dropped, not guessed at.
  const intents = [];
  for (const raw of parsed.intents) {
    const id = String(raw || '').trim().toLowerCase();
    if (ALLOWED_INTENTS.includes(id) && !intents.includes(id)) intents.push(id);
  }
  if (!intents.length) return null;

  return { intents, model: c.model, latencyMs: Date.now() - t0, raw: text };
}

/**
 * Full LLM routing. Returns a plan shaped exactly like route(), or null to fall back.
 */
export async function routeWithLLM(query, lang = 'zh') {
  const classified = await classifyWithLLM(query, lang);
  if (!classified) return null;

  const entities = extractEntities(query, lang);   // numbers stay deterministic
  let intents = classified.intents;

  // Same guard the rule router applies: a sizing question that happens to contain
  // "what should I wear" is still a sizing question.
  if (intents.includes('size') && intents.includes('outfit')
      && !/配搭|搭配|造型|場合|整套|outfit|look/i.test(query)) {
    intents = intents.filter((i) => i !== 'outfit');
  }
  if (entities.budget != null && !intents.includes('outfit')
      && intents.length === 1 && intents[0] === 'product_search') {
    intents = [...intents, 'outfit'];
  }

  return {
    intents,
    entities,
    plan: buildPlan(intents, entities, query),
    source: 'llm',
    router: { model: classified.model, latencyMs: classified.latencyMs },
  };
}
