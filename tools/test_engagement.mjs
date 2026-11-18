// tools/test_engagement.mjs
// The click-attention nudge: bounds, monotonicity, and the neutral case.
//
// The interesting properties are not "it returns a number" but that it can never do
// much: no amount of clicking may exceed +20 %, and a product with no history must be
// untouched, or every search would drift away from what the query asked for.
import assert from 'node:assert';
import { boostFor, attentionBoost } from '../lib/engagement.js';

let pass = 0;
const fails = [];

async function check(name, fn) {
  try {
    await fn();
    pass++;
    console.log(`  PASS  ${name}`);
  } catch (err) {
    fails.push(name);
    console.log(`  FAIL  ${name}\n        ${err.message}`);
  }
}

console.log('== the curve ==');
await check('zero attention is exactly neutral', () => {
  assert.equal(boostFor(0), 1);
  assert.equal(boostFor(null), 1);
  assert.equal(boostFor(-5), 1);
});

await check('never exceeds +20%', () => {
  for (const s of [1, 10, 100, 1e6]) {
    assert.ok(boostFor(s) <= 1.2 + 1e-9, `score ${s} gave ${boostFor(s)}`);
  }
});

await check('monotonic in attention', () => {
  let prev = 0;
  for (const s of [0, 1, 2, 5, 10, 20, 50]) {
    const b = boostFor(s);
    assert.ok(b >= prev - 1e-12, `not monotonic at ${s}`);
    prev = b;
  }
});

await check('a little attention is a little boost', () => {
  const b = boostFor(4);
  assert.ok(b > 1 && b < 1.1, `expected a mild boost, got ${b}`);
});

console.log('\n== the product-level wrapper ==');
await check('a product without a category is untouched', () => {
  assert.equal(attentionBoost(null), 1);
  assert.equal(attentionBoost({}), 1);
});

await check('unknown category is untouched', () => {
  // No such category can accumulate attention, so this must stay neutral.
  const b = attentionBoost({ category: '__not-a-real-category__' });
  assert.equal(b, 1);
});

await check('a real category stays inside the bound', () => {
  const b = attentionBoost({ category: 'Apparel' });
  assert.ok(b >= 1 && b <= 1.2 + 1e-9, `got ${b}`);
});

console.log(`\n  ${pass} passed, ${fails.length} failed`);
if (fails.length) {
  console.log(`  FAILURES: ${fails.join(', ')}`);
  process.exit(1);
}
