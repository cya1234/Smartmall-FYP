// js/api.js — tiny fetch helpers for the REST API.

/**
 * Turn a failed response into an Error that still carries what the server said.
 *
 * The server always answers errors as {"error":"email_taken"} with a 4xx status. The
 * status alone is not enough to tell the user anything useful, so the error key is
 * lifted into the message and the rest of the body is kept on `.detail`.
 */
async function failure(r) {
  let detail = null;
  try {
    detail = await r.json();
  } catch {
    // A proxy error page or an empty body is not JSON; fall back to the status alone.
    detail = null;
  }
  const err = new Error(detail?.error || `Request failed (${r.status})`);
  err.status = r.status;
  err.detail = detail;
  return err;
}

/**
 * Parse a response body as JSON, or fail with something a human can read.
 * A 200 response that is actually an HTML page (SPA fallback, proxy error) would
 * otherwise surface as a bare SyntaxError with no URL or status attached.
 */
async function parseJson(r) {
  try {
    return await r.json();
  } catch {
    const err = new Error(`Expected JSON from ${r.url} but got HTTP ${r.status}`);
    err.status = r.status;
    throw err;
  }
}

export async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw await failure(r);
  return parseJson(r);
}

export async function postJSON(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw await failure(r);
  return parseJson(r);
}
