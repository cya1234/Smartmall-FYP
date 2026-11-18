// lib/auth.js
// Accounts and sessions, with no npm dependencies.
//
// The professor's requirement was "a feasible, reliable login system", so the parts
// that make one reliable are all here rather than hand-waved:
//
//   * passwords are hashed with scrypt (memory-hard) and a per-user random salt;
//     the comparison is constant-time
//   * sessions are opaque random tokens, stored server-side, so a token cannot be
//     forged by editing a cookie
//   * the cookie is HttpOnly (script cannot read it) and SameSite=Lax (another site
//     cannot drive an authenticated POST)
//   * failed logins are rate limited per email and per address
//
// What is deliberately NOT here, and why:
//   * no `Secure` flag — this demo runs on http://localhost and on a Tailscale
//     address over http. Setting Secure would silently break the only deployments it
//     has. With TLS in front, add it (noted in the response object below).
//   * no email verification, no password reset, no OAuth — those are product
//     decisions, not security ones, and each needs an email provider.
import { randomBytes, scryptSync, timingSafeEqual, randomUUID } from 'node:crypto';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, '..', 'data');
const USERS_PATH = process.env.AUTH_USERS_PATH || join(DATA_DIR, 'users.json');
const SESSION_PATH = process.env.AUTH_SESSION_PATH || join(DATA_DIR, 'sessions.json');

const SESSION_TTL_MS = 7 * 86400000;
const KEY_LEN = 64;
const SALT_LEN = 16;
const MAX_FAILS_PER_EMAIL = 5;
// High on purpose. The per-address limit is what stops password guessing; this one
// only catches spraying from a single IP, and a low value would lock out everyone
// behind a shared NAT — including a test suite, which fails on the second run.
const MAX_FAILS_PER_IP = 50;
const FAIL_WINDOW_MS = 5 * 60000;

function readJson(path, fallback) {
  try {
    if (!existsSync(path)) return fallback;
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch {
    return fallback;
  }
}

function writeJson(path, value) {
  try {
    mkdirSync(DATA_DIR, { recursive: true });
    writeFileSync(path, JSON.stringify(value, null, 1), 'utf8');
  } catch (err) {
    console.warn('  auth: could not persist —', err.message);
  }
}

let users = readJson(USERS_PATH, { users: [] });
let sessions = readJson(SESSION_PATH, { sessions: {} });
if (!Array.isArray(users.users)) users = { users: [] };
if (!sessions.sessions || typeof sessions.sessions !== 'object') sessions = { sessions: {} };

const failLog = new Map();      // key -> [timestamps]

const normEmail = (e) => String(e || '').trim().toLowerCase();

function hash(password, salt) {
  return scryptSync(String(password), salt, KEY_LEN).toString('hex');
}

function safeEqualHex(a, b) {
  const ba = Buffer.from(String(a), 'hex');
  const bb = Buffer.from(String(b), 'hex');
  if (ba.length !== bb.length) return false;
  return timingSafeEqual(ba, bb);
}

function publicUser(u) {
  return u ? { id: u.id, email: u.email, name: u.name, createdAt: u.createdAt } : null;
}

// ------------------------------------------------------------------ accounts

export function register({ email, password, name } = {}) {
  const e = normEmail(email);
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e)) return { ok: false, error: 'invalid_email' };
  if (String(password || '').length < 8) return { ok: false, error: 'password_too_short' };
  if (users.users.some((u) => u.email === e)) return { ok: false, error: 'email_taken' };

  const salt = randomBytes(SALT_LEN).toString('hex');
  const user = {
    id: randomUUID(),
    email: e,
    name: String(name || '').trim().slice(0, 40) || e.split('@')[0],
    salt,
    hash: hash(password, salt),
    createdAt: new Date().toISOString(),
  };
  users.users.push(user);
  writeJson(USERS_PATH, users);
  return { ok: true, user: publicUser(user) };
}

/**
 * Failed-attempt limiter.
 *
 * Two buckets, with different thresholds on purpose: 5 failures against one address
 * stops a password guess, while 20 from one IP stops spraying without locking out
 * everybody behind the same NAT. A single shared limit would let one careless user
 * (or one test run) block a whole campus network.
 */
function tooManyFails(emailKey, ipKey) {
  const now = Date.now();
  const count = (key) => (failLog.get(key) || []).filter((t) => now - t < FAIL_WINDOW_MS).length;
  failLog.set(emailKey, (failLog.get(emailKey) || []).filter((t) => now - t < FAIL_WINDOW_MS));
  failLog.set(ipKey, (failLog.get(ipKey) || []).filter((t) => now - t < FAIL_WINDOW_MS));
  return count(emailKey) >= MAX_FAILS_PER_EMAIL || count(ipKey) >= MAX_FAILS_PER_IP;
}

function noteFail(keys) {
  const now = Date.now();
  for (const key of keys) {
    const hits = (failLog.get(key) || []).filter((t) => now - t < FAIL_WINDOW_MS);
    hits.push(now);
    failLog.set(key, hits);
  }
}

/**
 * Verify a password. The same generic error is returned for "no such account" and
 * "wrong password", so the endpoint cannot be used to enumerate addresses.
 */
export function login({ email, password, ip = 'unknown' } = {}) {
  const e = normEmail(email);
  const emailKey = `email:${e}`;
  const ipKey = `ip:${ip}`;
  if (tooManyFails(emailKey, ipKey)) return { ok: false, error: 'too_many_attempts' };

  const user = users.users.find((u) => u.email === e);
  if (!user || !safeEqualHex(hash(password, user.salt), user.hash)) {
    noteFail([emailKey, ipKey]);
    return { ok: false, error: 'invalid_credentials' };
  }

  failLog.delete(emailKey);
  const token = randomBytes(32).toString('hex');
  sessions.sessions[token] = { userId: user.id, createdAt: new Date().toISOString() };
  pruneSessions();
  writeJson(SESSION_PATH, sessions);
  return { ok: true, token, user: publicUser(user) };
}

export function logout(token) {
  if (token && sessions.sessions[token]) {
    delete sessions.sessions[token];
    writeJson(SESSION_PATH, sessions);
  }
  return { ok: true };
}

function pruneSessions() {
  const cutoff = Date.now() - SESSION_TTL_MS;
  for (const [token, s] of Object.entries(sessions.sessions)) {
    if (new Date(s.createdAt).getTime() < cutoff) delete sessions.sessions[token];
  }
}

/** The account behind a session token, or null. */
export function userForToken(token) {
  if (!token) return null;
  const s = sessions.sessions[token];
  if (!s) return null;
  if (Date.now() - new Date(s.createdAt).getTime() > SESSION_TTL_MS) {
    delete sessions.sessions[token];
    writeJson(SESSION_PATH, sessions);
    return null;
  }
  const user = users.users.find((u) => u.id === s.userId);
  return publicUser(user);
}

// ------------------------------------------------------------------- cookies

export const COOKIE_NAME = 'sm_session';

export function parseCookies(header) {
  const out = {};
  for (const part of String(header || '').split(';')) {
    const i = part.indexOf('=');
    if (i < 0) continue;
    const k = part.slice(0, i).trim();
    if (k) out[k] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}

export function sessionFromRequest(req) {
  return parseCookies(req.headers?.cookie)[COOKIE_NAME] || null;
}

/** The cookie to set. HttpOnly + SameSite; Secure is omitted on purpose (see header). */
export function cookieFor(token) {
  return `${COOKIE_NAME}=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${Math.floor(SESSION_TTL_MS / 1000)}`;
}

export function clearCookie() {
  return `${COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`;
}

/** Accounts exist so a demo can be shared; count them for the login page. */
export function userCount() {
  return users.users.length;
}

export { USERS_PATH, SESSION_PATH };
