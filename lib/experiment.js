// lib/experiment.js
// The A/B experiment behind the outfit score: does showing a *personalised* score
// convert better than showing a *general taste* score?
//
//   arm 'personal'  the score measured against the shopper's own wardrobe
//   arm 'public'    the score measured against a generic "does this look good" anchor
//   arm 'both'      both numbers side by side, personal first
//
// The primary metric is click-through after seeing a score, not purchases. That is a
// proxy and it is stated as one: a demo site cannot collect real orders, but a view
// followed by a click is measurable per visitor and reaches a usable sample far faster
// than checkout ever would.
//
// Assignment is per browser and sticky. It is not server-side randomisation: with no
// accounts there is nothing to randomise on, and re-rolling every visit would make
// each visitor contribute to both arms.
import { trackEvent, eventCountsByLabel } from './analytics.js';

export const ARMS = ['personal', 'public', 'both'];

/** Deterministic-enough pick, weighted equally. */
export function pickArm(seed) {
  const n = Math.abs(Math.round(Number(seed) || 0)) % ARMS.length;
  return ARMS[n];
}

/** Counts per arm and the click-through rate after a score was shown. */
export function experimentSummary({ days = 30 } = {}) {
  const since = new Date(Date.now() - days * 86400000).toISOString();
  const rows = eventCountsByLabel({
    types: ['aes_view', 'aes_action'], since, sumValue: true,
  });

  const arms = {};
  for (const arm of ARMS) arms[arm] = { views: 0, actions: 0, ctr: null, meanScore: null, _sum: 0 };

  for (const r of rows) {
    const arm = arms[r.label];
    if (!arm) continue;
    if (r.type === 'aes_view') {
      arm.views += r.n;
      arm._sum += r.total_score || 0;
    } else {
      arm.actions += r.n;
    }
  }

  for (const arm of ARMS) {
    const a = arms[arm];
    a.ctr = a.views ? Math.round((a.actions / a.views) * 1000) / 10 : null;
    a.meanScore = a.views ? Math.round(a._sum / a.views) : null;
    delete a._sum;
  }

  const p = arms.personal;
  const q = arms.public;
  const lift = (p.ctr != null && q.ctr != null) ? Math.round((p.ctr - q.ctr) * 10) / 10 : null;
  const enough = p.views >= 30 && q.views >= 30;

  return {
    days,
    arms,
    liftPersonalVsPublic: lift,
    conclusive: enough,
    note: enough
      ? 'At least 30 views per arm. Still a proxy metric, not revenue.'
      : 'Under 30 views per arm — the comparison is not yet meaningful.',
  };
}

/** Record one arm's event; a thin wrapper so callers do not repeat the meta shape. */
export function recordArmEvent({ arm, type, score = null, session = null }) {
  if (!ARMS.includes(arm)) return null;
  return trackEvent({
    session,
    type,
    label: arm,
    value: Number.isFinite(score) ? score : null,
    meta: { arm, score: Number.isFinite(score) ? score : null },
  });
}
