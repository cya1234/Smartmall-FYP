// tools/test_api_client.mjs
// Exercises the browser's own fetch helpers against the running server.
//
// The bug this exists for: postJSON used to throw `Request failed (400)` and discard
// the server's {"error":"email_taken"}, so the sign-up form could only ever say
// "Sign-in failed" — the user was told the wrong thing, and nothing in the UI could
// tell them what to fix.
//
// Run: node tools/test_api_client.mjs [base_url]
import { postJSON, getJSON } from '../public/js/api.js';

const BASE = process.argv[2] || 'http://127.0.0.1:3000';
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

function eq(actual, expected, what) {
  if (actual !== expected) throw new Error(`${what}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
}

async function err(promise) {
  try {
    await promise;
  } catch (e) {
    return e;
  }
  throw new Error('expected a rejection, but the call resolved');
}

const stamp = Date.now();
const email = `apitest+${stamp}@example.com`;

console.log('== a successful call still resolves ==');
await check('register resolves with a user', async () => {
  const r = await postJSON(`${BASE}/api/auth/register`, {
    email, password: 'test-password-1', name: 'ApiTest',
  });
  eq(r.ok, true, 'ok');
  eq(r.user.email, email, 'email');
});

console.log('\n== the server\'s error key survives ==');
await check('duplicate email surfaces email_taken', async () => {
  const e = await err(postJSON(`${BASE}/api/auth/register`, { email, password: 'test-password-1' }));
  eq(e.message, 'email_taken', 'message');
  eq(e.status, 400, 'status');
  eq(e.detail?.error, 'email_taken', 'detail.error');
});

await check('short password surfaces password_too_short', async () => {
  const e = await err(postJSON(`${BASE}/api/auth/register`, { email: `x+${stamp}@example.com`, password: 'abc' }));
  eq(e.message, 'password_too_short', 'message');
});

await check('bad email surfaces invalid_email', async () => {
  const e = await err(postJSON(`${BASE}/api/auth/register`, { email: 'nope', password: 'test-password-1' }));
  eq(e.message, 'invalid_email', 'message');
});

await check('wrong password surfaces invalid_credentials', async () => {
  const e = await err(postJSON(`${BASE}/api/auth/login`, { email, password: 'definitely-wrong' }));
  eq(e.message, 'invalid_credentials', 'message');
  eq(e.status, 401, 'status');
});

console.log('\n== getJSON behaves the same way ==');
await check('a 404 keeps its status', async () => {
  const e = await err(getJSON(`${BASE}/api/products/does-not-exist`));
  eq(e.status, 404, 'status');
  eq(e.message, 'not found', 'message');
});

await check('a successful GET resolves', async () => {
  const r = await getJSON(`${BASE}/api/products`);
  if (!Array.isArray(r) || !r.length) throw new Error('expected a non-empty array');
});

await check('a non-JSON failure does not explode', async () => {
  // A static file that does not exist returns HTML, not JSON: the helper must still
  // produce a usable error rather than a JSON parse crash.
  const e = await err(getJSON(`${BASE}/no-such-page.html`));
  if (!e.status) throw new Error('error lost its status');
});

console.log(`\n  ${pass} passed, ${fails.length} failed`);
if (fails.length) {
  console.log(`  FAILURES: ${fails.join(', ')}`);
  process.exit(1);
}
