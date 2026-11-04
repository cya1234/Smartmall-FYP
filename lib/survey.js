// lib/survey.js
// Preference survey that pays for information.
//
// The shopper answers a few pairwise questions ("which of these two would you
// wear?"), and the reward is a fixed cash coupon of HK$1-10. The twist is that the
// amount is not flat: it scales with how much the answer actually taught us. Pairs
// where the model is already confident are worth little; pairs it cannot separate
// are worth the most. That is uncertainty sampling with a price signal.
//
// Learning model: Bradley-Terry. Each product carries a latent appeal score; the
// probability that A beats B is sigmoid(s_A - s_B), and each answer nudges the two
// scores apart. This follows the pairwise + rating-system approach used for fashion
// aesthetics in Hirakawa et al. (SIGGRAPH Asia 2024), which found pairwise
// comparisons far more reliable than asking a model (or a person) for an absolute
// score.
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { getProducts } from './store.js';
import { getMemoryContext } from './memory.js';
import { issueCoupon, trackEvent } from './analytics.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, '..', 'data');
const STATE_PATH = process.env.SURVEY_STATE || join(DATA_DIR, 'preferences.json');

const LEARNING_RATE = 0.35;
const MAX_AMOUNT_HKD = 10;
const MIN_AMOUNT_HKD = 1;
const QUESTIONS_PER_SESSION = 3;

// Sessions are short-lived; keeping them in memory avoids persisting half-finished
// surveys. Restarting the server simply means starting the survey again.
const sessions = new Map();

// ------------------------------------------------------------------ state ---
function blankState() {
  return { scores: {}, counts: {}, history: [] };
}

function loadState() {
  try {
    if (!existsSync(STATE_PATH)) return blankState();
    const raw = JSON.parse(readFileSync(STATE_PATH, 'utf8'));
    return {
      scores: raw.scores || {},
      counts: raw.counts || {},
      history: Array.isArray(raw.history) ? raw.history : [],
    };
  } catch {
    return blankState();
  }
}

let state = loadState();
let dirty = false;
let flushTimer = null;

function saveState() {
  dirty = true;
  if (flushTimer) return;
  // Batch writes: the survey is a burst of a few answers, not a stream.
  flushTimer = setTimeout(() => {
    flushTimer = null;
    if (!dirty) return;
    dirty = false;
    try {
      mkdirSync(DATA_DIR, { recursive: true });
      writeFileSync(STATE_PATH, JSON.stringify(state, null, 1), 'utf8');
    } catch (err) {
      console.warn('  survey: could not persist preferences —', err.message);
    }
  }, 250);
}

const score = (id) => state.scores[id] || 0;
const count = (id) => state.counts[id] || 0;

// -------------------------------------------------------------- statistics --
/** P(i preferred over j) under Bradley-Terry. */
function winProb(si, sj) {
  return 1 / (1 + Math.exp(-(si - sj)));
}

/**
 * How much an answer to this pair would teach us. High when the model is unsure
 * (scores close together) and when both items have been seen rarely.
 */
function uncertainty(i, j) {
  const gap = Math.abs(score(i) - score(j));
  const seen = count(i) + count(j);
  const closeness = 1 / (1 + gap * 2.5);
  const novelty = 1 / Math.sqrt(1 + seen);
  // Occasional randomness keeps the survey from asking the same pair forever.
  return closeness * novelty + Math.random() * 0.12;
}

function applyAnswer(winner, loser) {
  const sw = score(winner);
  const sl = score(loser);
  const p = winProb(sw, sl);
  const delta = LEARNING_RATE * (1 - p);
  state.scores[winner] = Math.round((sw + delta) * 1000) / 1000;
  state.scores[loser] = Math.round((sl - delta) * 1000) / 1000;
  state.counts[winner] = count(winner) + 1;
  state.counts[loser] = count(loser) + 1;
  state.history.push({ at: new Date().toISOString(), winner, loser, p: Math.round(p * 1000) / 1000 });
  if (state.history.length > 2000) state.history.splice(0, state.history.length - 2000);
  saveState();
}

// ------------------------------------------------------------- candidate ---
/**
 * Products the shopper is plausibly interested in: categories they already own or
 * have browsed, preferring ones with a photograph (the survey needs an image).
 */
function relevantProducts() {
  const all = getProducts().filter((p) => p.image);
  let ctx = null;
  try { ctx = getMemoryContext(); } catch { ctx = null; }

  const ownedIds = new Set((ctx?.wardrobe || []).map((w) => w.productId));
  const categories = new Set(
    (ctx?.wardrobe || []).map((w) => w.product?.category).filter(Boolean),
  );
  for (const id of ctx?.recentViews || []) {
    const p = all.find((x) => x.id === id);
    if (p) categories.add(p.category);
  }

  let candidates = all.filter((p) => categories.has(p.category));
  // Too few to build pairs: fall back to the whole catalogue rather than fail.
  if (candidates.length < 6) candidates = all;
  return { candidates, ownedIds };
}

function buildQuestion(candidates) {
  const byCategory = new Map();
  for (const p of candidates) {
    if (!byCategory.has(p.category)) byCategory.set(p.category, []);
    byCategory.get(p.category).push(p);
  }
  // Same-category pairs are more informative for style: they isolate taste from
  // category need. Fall back to any pair if a category is too small.
  const pools = [...byCategory.values()].filter((g) => g.length >= 2);

  let best = null;
  for (const pool of pools.length ? pools : [candidates]) {
    for (let a = 0; a < pool.length; a++) {
      for (let b = a + 1; b < pool.length; b++) {
        const u = uncertainty(pool[a].id, pool[b].id);
        if (!best || u > best.u) best = { u, left: pool[a], right: pool[b] };
      }
    }
  }
  if (!best) return null;

  const question = {
    id: randomUUID(),
    left: card(best.left),
    right: card(best.right),
    infoGain: Math.round(best.u * 1000) / 1000,
  };
  // Randomise side so position does not leak a preference (position bias).
  if (Math.random() < 0.5) [question.left, question.right] = [question.right, question.left];
  return question;
}

function card(p) {
  return {
    id: p.id,
    name: p.name,
    name_zh: p.name_zh,
    image: p.image || null,
    emoji: p.emoji || '🛍️',
    category: p.category,
    price: p.price,
    colorName: p.colorName,
    material: p.material,
  };
}

// ---------------------------------------------------------------- public ---
export function startSession({ lang = 'zh', n = QUESTIONS_PER_SESSION, session = null } = {}) {
  const { candidates } = relevantProducts();
  const total = Math.max(1, Math.min(6, n));
  const questions = [];
  const usedPairs = new Set();

  for (let i = 0; i < total; i++) {
    let q = null;
    for (let attempt = 0; attempt < 6; attempt++) {
      q = buildQuestion(candidates);
      if (!q) break;
      const key = [q.left.id, q.right.id].sort().join('|');
      if (!usedPairs.has(key)) { usedPairs.add(key); break; }
      q = null;
    }
    if (!q) break;
    questions.push(q);
  }

  const id = randomUUID();
  sessions.set(id, {
    id, session, lang, created: new Date().toISOString(),
    questions, answers: [], usedPairs,
  });

  trackEvent({ session, type: 'survey_started', label: id, value: questions.length });

  return {
    sessionId: id,
    total: questions.length,
    questions: questions.map((q) => ({
      id: q.id, left: q.left, right: q.right, infoGain: q.infoGain,
    })),
  };
}

export function answer({ sessionId, questionId, choice, session = null } = {}) {
  const s = sessions.get(sessionId);
  if (!s) return { ok: false, error: 'session_not_found' };

  const q = s.questions.find((x) => x.id === questionId);
  if (!q) return { ok: false, error: 'question_not_found' };
  if (s.answers.some((a) => a.questionId === questionId)) {
    return { ok: false, error: 'already_answered' };
  }

  const winner = choice === 'left' ? q.left.id : q.right.id;
  const loser = choice === 'left' ? q.right.id : q.left.id;
  applyAnswer(winner, loser);

  s.answers.push({ questionId, choice, winner, loser, infoGain: q.infoGain, at: new Date().toISOString() });
  trackEvent({
    session: session || s.session, type: 'survey_answer',
    label: `${winner}>${loser}`, value: q.infoGain,
  });

  return { ok: true, answered: s.answers.length, total: s.questions.length };
}

/**
 * Reward = HK$1 base plus up to HK$9, driven by two things:
 *   1. how uncertain the answered pairs were (the model's own difficulty)
 *   2. how much the model already knew (novelty decays with total comparisons)
 *
 * Without the second term every session pays the maximum, because a brand-new
 * shopper is maximally informative by definition — which made the whole $1-10
 * range collapse to $10 in testing.
 */
export function quoteReward(s) {
  if (!s.answers.length) return MIN_AMOUNT_HKD;
  const totalInfo = s.answers.reduce((n, a) => n + (a.infoGain || 0), 0);
  const avg = totalInfo / s.answers.length;
  const infoShare = Math.max(0, Math.min(1, avg / 1.05));
  const novelty = 1 / (1 + state.history.length / 25);
  const share = 0.35 + 0.65 * infoShare * novelty;   // floor ~35 %, ceiling 100 %
  return Math.round(MIN_AMOUNT_HKD + (MAX_AMOUNT_HKD - MIN_AMOUNT_HKD) * share);
}

export function finish({ sessionId, session = null } = {}) {
  const s = sessions.get(sessionId);
  if (!s) return { ok: false, error: 'session_not_found' };
  if (!s.answers.length) return { ok: false, error: 'no_answers' };

  if (s.coupon) return { ok: true, coupon: s.coupon, duplicate: true };

  const amountHkd = quoteReward(s);
  const coupon = issueCoupon({
    session: session || s.session,
    kind: 'amount',
    amountHkd,
    discountPct: 0,
    source: 'preference-survey',
  });
  s.coupon = coupon;
  s.finishedAt = new Date().toISOString();

  trackEvent({
    session: session || s.session, type: 'survey_completed',
    label: coupon.code, value: amountHkd,
    meta: { answers: s.answers.length, avgInfo: Math.round((s.answers.reduce((n, a) => n + (a.infoGain || 0), 0) / s.answers.length) * 1000) / 1000 },
  });

  return { ok: true, coupon, learned: profileSummary() };
}

/** What the model believes the shopper likes, strongest first. */
export function profileSummary(limit = 6) {
  const all = getProducts();
  const ranked = all
    .map((p) => ({ p, s: score(p.id), n: count(p.id) }))
    .filter((r) => r.n > 0)
    .sort((a, b) => b.s - a.s);

  const favourites = ranked.slice(0, limit).map((r) => ({
    id: r.p.id,
    name: r.p.name,
    name_zh: r.p.name_zh,
    image: r.p.image || null,
    score: r.s,
    comparisons: r.n,
  }));

  const categories = {};
  for (const r of ranked) categories[r.p.category] = (categories[r.p.category] || 0) + r.s;
  const topCategories = Object.entries(categories)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([name]) => name);

  const colours = {};
  for (const r of ranked.slice(0, 10)) {
    if (r.p.colorName) colours[r.p.colorName] = (colours[r.p.colorName] || 0) + 1;
  }

  return {
    comparisons: state.history.length,
    favourites,
    topCategories,
    topColours: Object.entries(colours).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([c]) => c),
  };
}

/**
 * A multiplier for search ranking, centred on 1.0 so items the shopper has not
 * rated are neither penalised nor boosted.
 */
export function preferenceBoost(productId) {
  const n = count(productId);
  if (!n) return 1;
  const s = score(productId);
  return Math.max(0.75, Math.min(1.35, 1 + Math.tanh(s) * 0.35));
}

export function resetPreferences() {
  state = blankState();
  saveState();
  return { ok: true };
}
