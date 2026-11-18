"""End-to-end test for the score A/B experiment.

The experiment compares a personalised outfit score against a general-taste score, with
click-through after seeing a score as the dependent variable. What has to be true for
that comparison to mean anything:

  1. both numbers exist for the same photo (otherwise the arms see different inputs)
  2. views and actions are counted per arm, not lumped together
  3. the click-through rate is actions/views, and it is not reported when there are
     no views (0/0 is unknown, not 0 %)
  4. it refuses to call the result conclusive before there is a sample

Run: python tools/test_experiment_e2e.py [base_url]
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
fails = []


def call(path, payload=None, method=None, timeout=90):
    if payload is None:
        req = urllib.request.Request(BASE + path, method=method or "GET")
    else:
        req = urllib.request.Request(
            BASE + path, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method=method or "POST",
        )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8", "ignore") or "{}")


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name:52s} {detail}")
    if not cond:
        fails.append(name)


def track(type_, label, value=None):
    return call("/api/analytics/event", {"type": type_, "label": label, "value": value})


print("== both scores exist for the same photo ==")
path = os.path.join(ROOT, "public", "assets", "products", "p004.jpg")
with open(path, "rb") as fh:
    img = "data:image/jpeg;base64," + base64.b64encode(fh.read()).decode()
code, r = call("/api/aesthetic/score?lang=zh", {"image": img})
check("score endpoint answers", code == 200 and isinstance(r.get("score"), int), f"HTTP {code}")
check("personal score present", isinstance(r.get("score"), int), r.get("score"))
check("public score present", isinstance(r.get("publicScore"), int), r.get("publicScore"))
check("the two numbers differ", r.get("score") != r.get("publicScore"),
      f"personal {r.get('score')} vs public {r.get('publicScore')}")
check("public subscores are reported", isinstance(r.get("publicSubscores"), dict),
      r.get("publicSubscores"))

print("\n== counting per arm ==")
before = call("/api/experiment")[1]["arms"]

for arm, views, actions in (("personal", 3, 2), ("public", 4, 1), ("both", 1, 0)):
    for _ in range(views):
        track("aes_view", arm, 70)
    for _ in range(actions):
        track("aes_action", arm, 70)

after = call("/api/experiment")[1]
arms = after["arms"]


def delta(key, field):
    return arms[key][field] - (before.get(key, {}).get(field) or 0)


check("personal views counted", delta("personal", "views") == 3, delta("personal", "views"))
check("personal actions counted", delta("personal", "actions") == 2, delta("personal", "actions"))
check("public views counted", delta("public", "views") == 4, delta("public", "views"))
check("public actions counted", delta("public", "actions") == 1, delta("public", "actions"))
check("arms are counted separately, not pooled",
      arms["personal"]["views"] != arms["public"]["views"] or delta("personal", "views") != delta("public", "views"))

print("\n== the rate is computed correctly ==")
p = arms["personal"]
expected = round(p["actions"] / p["views"] * 1000) / 10 if p["views"] else None
check("ctr equals actions / views", p["ctr"] == expected, f"{p['actions']}/{p['views']} -> {p['ctr']}")
check("ctr is a percentage", p["ctr"] is None or 0 <= p["ctr"] <= 100, p["ctr"])
check("mean score is reported", p["meanScore"] is None or isinstance(p["meanScore"], int), p["meanScore"])

print("\n== it refuses to overclaim ==")
# Do not assert "conclusive is false": after enough test runs the sample really does
# pass 30 and the flag correctly flips. Assert the rule instead, so the check holds
# whether the experiment is empty or saturated.
enough = arms["personal"]["views"] >= 30 and arms["public"]["views"] >= 30
check("conclusive matches the 30-per-arm rule", after["conclusive"] == enough,
      f"personal={arms['personal']['views']} public={arms['public']['views']} -> {after['conclusive']}")
note = after.get("note") or ""
check("the note always says the metric is a proxy", "proxy metric" in note, note)
if enough:
    check("a full sample is still labelled a proxy", "revenue" in note, note)
else:
    check("a small sample is called not meaningful", "not yet meaningful" in note, note)
check("a lift is either null or a number",
      after["liftPersonalVsPublic"] is None or isinstance(after["liftPersonalVsPublic"], (int, float)),
      after["liftPersonalVsPublic"])

print("\n== an unknown arm cannot pollute the summary ==")
track("aes_view", "not-an-arm", 50)
post = call("/api/experiment")[1]["arms"]
check("bogus arm is ignored", "not-an-arm" not in post, sorted(post.keys()))

print()
print("ALL CHECKS PASSED" if not fails else f"FAILURES: {', '.join(fails)}")
sys.exit(1 if fails else 0)
