// js/experiment.js — which arm of the score comparison this browser is in.
//
// Sticky per browser so a visitor contributes to one arm rather than all three. The
// assignment is reported to the server with each event; the server never decides it,
// because with no accounts there is nothing to randomise on.
const KEY = 'smartmall-ab-score-v1';
export const ARMS = ['personal', 'public', 'both'];

function assign() {
  // Equal thirds, chosen once.
  const pick = ARMS[Math.floor(Math.random() * ARMS.length)];
  try { localStorage.setItem(KEY, pick); } catch { /* private mode: session-only */ }
  return pick;
}

export function arm() {
  try {
    const stored = localStorage.getItem(KEY);
    if (ARMS.includes(stored)) return stored;
  } catch { /* fall through and assign a session arm */ }
  return assign();
}

/** Force an arm, for demos and for the test harness. */
export function setArm(value) {
  if (!ARMS.includes(value)) return arm();
  try { localStorage.setItem(KEY, value); } catch { /* ignore */ }
  return value;
}
