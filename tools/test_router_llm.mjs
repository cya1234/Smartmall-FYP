// tools/test_router_llm.mjs
// Verifies the LLM router's contract without needing a real model.
//
// A real model is not required (and is not available on this machine), so the test
// runs against tools/mock_llm_server.py and checks the parts that must hold whatever
// the model says:
//
//   1. a valid classification becomes a plan identical in shape to the rule router
//   2. money and size never come from the model
//   3. garbage, unknown intents, timeouts and HTTP errors all fall back to rules
//   4. the router is off unless explicitly enabled
//
// Run:  node tools/test_router_llm.mjs [mockPort]
import assert from 'node:assert';

const MOCK = `http://127.0.0.1:${process.argv[2] || 11434}/v1`;
let pass = 0;
const fails = [];

function check(name, fn) {
  return Promise.resolve()
    .then(fn)
    .then(() => { pass++; console.log(`  PASS  ${name}`); })
    .catch((err) => { fails.push(name); console.log(`  FAIL  ${name}\n        ${err.message}`); });
}

/** Reload the module so env changes take effect, as a fresh process would. */
async function loadRouter(env) {
  for (const k of ['ASSISTANT_LLM', 'LLM_URL', 'LLM_MODEL', 'LLM_TIMEOUT_MS']) delete process.env[k];
  Object.assign(process.env, env);
  const url = new URL(`../lib/agent/llmRouter.js?t=${Date.now()}`, import.meta.url);
  return import(url.href);
}

const base = { ASSISTANT_LLM: '1', LLM_URL: MOCK, LLM_TIMEOUT_MS: '2500' };

console.log('== a valid answer becomes a plan ==');
const llm = await loadRouter({ ...base, LLM_MODEL: 'mock-normal' });

await check('classifies a price question', async () => {
  const r = await llm.routeWithLLM('呢件羽絨幾時最平', 'zh');
  assert.ok(r, 'expected a plan, got null');
  assert.equal(r.source, 'llm');
  assert.deepEqual(r.intents, ['price_timing']);
  assert.deepEqual(r.plan.map((s) => s.tool), ['search_products', 'forecast_price']);
});

await check('plan shape matches the rule router', async () => {
  const { route } = await import('../lib/agent/router.js');
  const a = route('呢件羽絨幾時最平', 'zh');
  const b = await llm.routeWithLLM('呢件羽絨幾時最平', 'zh');
  assert.deepEqual(b.plan.map((s) => s.tool), a.plan.map((s) => s.tool));
  assert.deepEqual(b.plan.map((s) => s.id), a.plan.map((s) => s.id));
});

await check('English sizing question routes to size', async () => {
  const r = await llm.routeWithLLM('does the linen shirt run small', 'en');
  assert.ok(r);
  assert.ok(r.intents.includes('size'));
  assert.ok(r.plan.map((s) => s.tool).includes('size_advice'));
});

console.log('\n== the model never supplies numbers ==');
await check('budget comes from extractEntities, not the model', async () => {
  const r = await llm.routeWithLLM('幫我配一套，預算800蚊左右', 'zh');
  assert.ok(r);
  // 800 HKD -> ~102.56 USD by the deterministic extractor
  assert.ok(r.entities.budget > 90 && r.entities.budget < 110, `budget=${r.entities.budget}`);
  const outfit = r.plan.find((s) => s.tool === 'build_outfit');
  assert.ok(outfit, 'expected build_outfit');
  assert.ok(outfit.params.budget > 90, 'budget must flow through from the extractor');
});

await check('size comes from extractEntities', async () => {
  const r = await llm.routeWithLLM('我穿 M 碼，呢件合身嗎', 'zh');
  assert.ok(r);
  assert.equal(r.entities.size, 'M');
  const size = r.plan.find((s) => s.tool === 'size_advice');
  assert.ok(size && size.params.size === 'M', 'size must reach the tool');
});

console.log('\n== every failure falls back to rules ==');
for (const [mode, label] of [
  ['mock-garbage', 'prose instead of JSON'],
  ['mock-unknown_intent', 'identifiers outside the allowlist'],
  ['mock-slow', 'a timeout'],
  ['mock-error', 'an HTTP 500'],
]) {
  const mod = await loadRouter({ ...base, LLM_MODEL: mode, LLM_TIMEOUT_MS: '1200' });
  await check(`${label} -> null (caller falls back)`, async () => {
    const r = await mod.routeWithLLM('呢件羽絨幾時最平', 'zh');
    assert.equal(r, null, `expected null, got ${JSON.stringify(r && r.intents)}`);
  });
}

await check('the rule router still answers when the model is down', async () => {
  const { route } = await import('../lib/agent/router.js');
  const r = route('呢件羽絨幾時最平', 'zh');
  assert.equal(r.source, 'rules');
  assert.deepEqual(r.intents, ['price_timing']);
  assert.ok(r.plan.length >= 2);
});

console.log('\n== off unless explicitly enabled ==');
await check('ASSISTANT_LLM unset -> no LLM call, rules only', async () => {
  const mod = await loadRouter({ LLM_URL: MOCK, LLM_MODEL: 'mock-normal' });
  const r = await mod.routeWithLLM('呢件羽絨幾時最平', 'zh');
  assert.equal(r, null);
  const h = await mod.llmHealth();
  assert.equal(h.enabled, false);
});

await check('ASSISTANT_LLM=1 -> health probe reports the model', async () => {
  const mod = await loadRouter({ ...base, LLM_MODEL: 'mock-normal' });
  const h = await mod.llmHealth({ force: true });
  assert.equal(h.enabled, true);
  assert.equal(h.ok, true, 'mock /v1/models should answer');
});

await check('unreachable endpoint is reported, not thrown', async () => {
  const mod = await loadRouter({ ASSISTANT_LLM: '1', LLM_URL: 'http://127.0.0.1:9/v1', LLM_TIMEOUT_MS: '800' });
  const h = await mod.llmHealth({ force: true });
  assert.equal(h.ok, false);
  assert.equal(await mod.routeWithLLM('呢件羽絨幾時最平', 'zh'), null);
});

console.log(`\n  ${pass} passed, ${fails.length} failed`);
if (fails.length) {
  console.log(`  FAILURES: ${fails.join(', ')}`);
  process.exit(1);
}
