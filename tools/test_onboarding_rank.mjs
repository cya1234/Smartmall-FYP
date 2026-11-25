// tools/test_onboarding_rank.mjs
// The welcome survey has to actually change the ranking, not just be stored.
//
// A real bug this catches: product.style is a list, but the affinity check compared it
// with === against the shopper's chosen style, so the +0.5 style bonus never fired and
// a third of the survey did nothing.
import assert from 'node:assert';
import { saveOnboarding, subcategoryAffinity, resetAll } from '../lib/userState.js';

let pass = 0;
const fails = [];
const ACCT = 'test-onboarding-rank';

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

console.log('== nothing chosen means no influence ==');
await check('a fresh account is neutral', () => {
  resetAll(ACCT);
  assert.equal(subcategoryAffinity({ category: 'Apparel', style: ['Bold'], colorName: 'Coral' }, ACCT), 0);
});

console.log('\n== each answer adds weight ==');
saveOnboarding({
  categories: ['Electronics'],
  styles: ['Minimal'],
  colours: ['Graphite'],
  avoidColours: ['Coral'],
  occasions: ['Work'],
  materials: ['Linen'],
}, ACCT);

await check('matching category adds 1', () => {
  assert.equal(subcategoryAffinity({ category: 'Electronics' }, ACCT), 1);
});

await check('a matching style adds 0.63 (this is the bug that was fixed)', () => {
  const a = subcategoryAffinity({ category: 'Other', style: ['Minimal'] }, ACCT);
  assert.equal(a, 0.63, `expected 0.63 for a style match, got ${a}`);
});

await check('style held as a plain string still matches', () => {
  const a = subcategoryAffinity({ category: 'Other', style: 'Minimal' }, ACCT);
  assert.equal(a, 0.63, `got ${a}`);
});

await check('a different style adds nothing', () => {
  assert.equal(subcategoryAffinity({ category: 'Other', style: ['Bold'] }, ACCT), 0);
});

await check('matching colour adds 0.42', () => {
  assert.equal(subcategoryAffinity({ category: 'Other', colorName: 'Graphite' }, ACCT), 0.42);
});

await check('an avoided colour subtracts 1', () => {
  assert.equal(subcategoryAffinity({ category: 'Other', colorName: 'Coral' }, ACCT), -1);
});

await check('everything matching is capped at 1.5', () => {
  const a = subcategoryAffinity({ category: 'Electronics', style: ['Minimal'], colorName: 'Graphite' }, ACCT);
  assert.equal(a, 1.5, `got ${a}`);
});

await check('a wrong answer still cannot push below -1', () => {
  const a = subcategoryAffinity({ category: 'Home', style: ['Bold'], colorName: 'Coral' }, ACCT);
  assert.equal(a, -1, `got ${a}`);
});

console.log('\n== the multiplier the search uses ==');
await check('1 + 0.25 * affinity stays inside 0..1.4', () => {
  for (const aff of [-1, 0, 0.5, 1, 1.5]) {
    const mult = 1 + 0.25 * aff;
    assert.ok(mult >= 0.75 && mult <= 1.4, `affinity ${aff} -> ${mult}`);
  }
});

resetAll(ACCT);
console.log(`\n  ${pass} passed, ${fails.length} failed`);
if (fails.length) {
  console.log(`  FAILURES: ${fails.join(', ')}`);
  process.exit(1);
}
