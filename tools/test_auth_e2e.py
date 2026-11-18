"""End-to-end test for accounts and per-account state.

What has to be true for the login to count as reliable, rather than merely present:

  1. passwords are never stored or returned in the clear
  2. a session works from the cookie alone and stops working after logout
  3. two accounts do not see each other's search history or onboarding answers
  4. bad credentials are refused, and refused with the same message whether or not the
     address exists (otherwise the endpoint enumerates accounts)
  5. repeated failures are rate limited
  6. browsing without an account still works

Run: python tools/test_auth_e2e.py [base_url]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
fails = []
stamp = str(int(time.time()))


def call(path, payload=None, cookie=None, method=None, timeout=30):
    headers = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=headers, method=method or ("POST" if payload is not None else "GET"),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "ignore")
            return r.status, (json.loads(body) if body else {}), r.headers.get("Set-Cookie")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        return e.code, (json.loads(body) if body else {}), e.headers.get("Set-Cookie")


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name:52s} {detail}")
    if not cond:
        fails.append(name)


def new_cookie(set_cookie):
    return (set_cookie or "").split(";")[0]


print("== registering ==")
email_a = f"alice+{stamp}@example.com"
email_b = f"bob+{stamp}@example.com"
code, r, sc = call("/api/auth/register", {"email": email_a, "password": "correct-horse-1", "name": "Alice"})
check("register succeeds", code == 200 and r.get("ok") is True, f"HTTP {code}")
cookie_a = new_cookie(sc)
check("a session cookie is set", cookie_a.startswith("sm_session="), cookie_a[:20])
check("HttpOnly is set", "HttpOnly" in (sc or ""), sc or "")
check("SameSite is set", "SameSite=Lax" in (sc or ""), "")
check("no password in the response", "password" not in json.dumps(r).lower() and "hash" not in json.dumps(r).lower())

code, r2, _ = call("/api/auth/register", {"email": email_a, "password": "another-pass-1"})
check("the same email cannot register twice", code == 400 and r2.get("error") == "email_taken", r2.get("error"))

code, r3, _ = call("/api/auth/register", {"email": f"x+{stamp}@example.com", "password": "short"})
check("a short password is refused", code == 400 and r3.get("error") == "password_too_short", r3.get("error"))

code, r4, _ = call("/api/auth/register", {"email": "not-an-email", "password": "correct-horse-1"})
check("a bad email is refused", code == 400 and r4.get("error") == "invalid_email", r4.get("error"))

print("\n== the session identifies the account ==")
code, me, _ = call("/api/auth/me", cookie=cookie_a)
check("me returns the account", code == 200 and (me.get("user") or {}).get("name") == "Alice",
      (me.get("user") or {}).get("email"))
code, anon, _ = call("/api/auth/me")
check("no cookie means no account", code == 200 and anon.get("user") is None, anon.get("user"))

print("\n== passwords are hashed on disk ==")
users_path = os.path.join(ROOT, "data", "users.json")
with open(users_path, encoding="utf-8") as fh:
    raw = fh.read()
check("users.json does not contain the password", "correct-horse-1" not in raw)
check("users.json stores a salt and a hash", '"salt"' in raw and '"hash"' in raw)

print("\n== two accounts do not share state ==")
call("/api/onboarding", {"categories": ["Electronics"], "styles": ["Minimal"]}, cookie=cookie_a)
call("/api/assistant", {"query": "alice secret query", "lang": "zh"}, cookie=cookie_a)

code, r, sc = call("/api/auth/register", {"email": email_b, "password": "correct-horse-2", "name": "Bob"})
cookie_b = new_cookie(sc)
check("second account registers", code == 200 and cookie_b != cookie_a)

_, a_on, _ = call("/api/onboarding", cookie=cookie_a)
_, b_on, _ = call("/api/onboarding", cookie=cookie_b)
a_cats = (a_on.get("onboarding") or {}).get("categories") or []
# A second account has no answers at all, which is null, not an empty list.
b_cats = (b_on.get("onboarding") or {}).get("categories") or []
check("onboarding does not leak across accounts",
      a_cats == ["Electronics"] and b_cats == [],
      f"a={a_cats} b={b_cats}")

_, a_hist, _ = call("/api/history", cookie=cookie_a)
_, b_hist, _ = call("/api/history", cookie=cookie_b)
check("search history does not leak across accounts",
      any("alice secret" in q["query"] for q in a_hist.get("recentQueries", []))
      and not any("alice secret" in q["query"] for q in b_hist.get("recentQueries", [])),
      f"a={a_hist.get('total')} b={b_hist.get('total')}")

print("\n== wrong credentials ==")
code, bad1, _ = call("/api/auth/login", {"email": email_a, "password": "wrong-password"})
code2, bad2, _ = call("/api/auth/login", {"email": f"nobody+{stamp}@example.com", "password": "wrong-password"})
check("a wrong password is refused", code == 401, code)
check("an unknown address is refused the same way",
      code == code2 and bad1.get("error") == bad2.get("error"),
      f"{bad1.get('error')} vs {bad2.get('error')}")

print("\n== rate limiting ==")
limited = False
for _ in range(6):
    code, r, _ = call("/api/auth/login", {"email": email_b, "password": "wrong-password"})
    if code == 429:
        limited = True
        break
check("repeated failures are throttled", limited, f"last HTTP {code}")

print("\n== logout ==")
code, r, sc = call("/api/auth/logout", {}, cookie=cookie_a)
check("logout answers", code == 200 and r.get("ok") is True)
check("the cookie is cleared", "Max-Age=0" in (sc or ""), (sc or "")[:60])
# The old token stays valid server-side only if it was not removed; a cleared cookie is
# what a browser sees, so check the token itself was invalidated.
code, me, _ = call("/api/auth/me", cookie=cookie_a)
check("the old session no longer identifies anyone", (me.get("user") or None) is None,
      me.get("user"))

print("\n== logged out still works ==")
code, products, _ = call("/api/products")
check("the catalogue is public", code == 200 and len(products) > 0, f"{len(products)} products")
code, hist, _ = call("/api/history")
check("guest history exists as its own bucket", code == 200 and "total" in hist, hist.get("total"))

print()
print("ALL CHECKS PASSED" if not fails else f"FAILURES: {', '.join(fails)}")
sys.exit(1 if fails else 0)
