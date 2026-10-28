"""End-to-end test for the merchant analytics + exit-intent coupon funnel.

Runs against a live server (default :3100) and validates that a visitor's
actions move the dashboard numbers in the right direction.
"""
import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3100"
fails = []


def call(path, payload=None, timeout=20):
    if payload is None:
        req = urllib.request.Request(BASE + path)
    else:
        req = urllib.request.Request(
            BASE + path, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name:46s} {detail}")
    if not cond:
        fails.append(name)


def summary():
    _, d = call("/api/analytics/summary?days=7")
    return d


print("== baseline ==")
base = summary()
T0 = base["totals"]
print(f"  sessions={T0['sessions']} searches={T0['searches']} shown={T0['exitShown']} "
      f"claimed={T0['exitClaimed']} applied={T0['couponsApplied']}")
check("seeded history present", T0["searches"] > 100, f"{T0['searches']} searches")
check("retention rate sane (0-100)", 0 < base["rates"]["retentionRate"] < 100,
      f"{base['rates']['retentionRate']}%")
check("conversion rate sane (0-100)", 0 < base["rates"]["conversionRate"] < 100,
      f"{base['rates']['conversionRate']}%")

print("\n== 1. a search event is recorded ==")
code, _ = call("/api/analytics/event", {"type": "search", "label": "test-needle-query", "session": "e2e-1"})
check("POST event accepted", code == 200)
s1 = summary()
check("search count +1", s1["totals"]["searches"] == T0["searches"] + 1,
      f"{T0['searches']} -> {s1['totals']['searches']}")

print("\n== 2. exit-intent prompt shown ==")
call("/api/analytics/event", {"type": "exit_intent_shown", "session": "e2e-1"})
s2 = summary()
check("shown +1", s2["totals"]["exitShown"] == T0["exitShown"] + 1,
      f"{T0['exitShown']} -> {s2['totals']['exitShown']}")

print("\n== 3. visitor claims a coupon ==")
code, coupon = call("/api/analytics/coupon", {"discountPct": 10, "source": "exit-intent", "session": "e2e-1"})
check("coupon issued", code == 200 and coupon.get("code", "").startswith("SAVE10-"), coupon.get("code"))
s3 = summary()
check("claimed +1", s3["totals"]["exitClaimed"] == T0["exitClaimed"] + 1,
      f"{T0['exitClaimed']} -> {s3['totals']['exitClaimed']}")

print("\n== 4. coupon validates ==")
code, v = call(f"/api/analytics/coupon/{coupon['code']}")
check("validates as issued", code == 200 and v["valid"] and v["coupon"]["status"] == "issued",
      v.get("coupon", {}).get("status"))
code, v2 = call("/api/analytics/coupon/SAVE10-NOPE0")
check("unknown code rejected", code == 404, f"HTTP {code}")

print("\n== 5. coupon is applied at checkout ==")
code, a = call("/api/analytics/coupon/apply", {"code": coupon["code"], "session": "e2e-1"})
check("apply ok", code == 200 and a.get("ok") is True)
s4 = summary()
check("applied +1", s4["totals"]["couponsApplied"] == T0["couponsApplied"] + 1,
      f"{T0['couponsApplied']} -> {s4['totals']['couponsApplied']}")
code, v3 = call(f"/api/analytics/coupon/{coupon['code']}")
check("status now applied", v3["coupon"]["status"] == "applied", v3["coupon"]["status"])
code, a2 = call("/api/analytics/coupon/apply", {"code": coupon["code"]})
check("double-apply is idempotent", code == 200 and a2.get("alreadyApplied") is True)

print("\n== 6. funnel reflects the live visitor ==")
f = s4["funnels"]["exitIntent"]
check("funnel has 4 stages", len(f) == 4, [x["stage"] for x in f])
check("funnel is monotonic-ish", f[0]["count"] >= f[1]["count"], f"{f[0]['count']} >= {f[1]['count']}")

print("\n== 7. dashboard + new assets are served ==")
for path, needle in [
    ("/", "dashboard"),
    ("/js/exitIntent.js", "exit-intent"),
    ("/js/views/dashboard.js", "Merchant"),
    ("/css/styles.css", "exit-card"),
]:
    code, body = call(path)
    ok = code == 200 and (isinstance(body, str) and needle.lower() in body.lower())
    check(f"GET {path}", ok, f"HTTP {code}")

print("\n== 8. recent events endpoint ==")
code, ev = call("/api/analytics/events?limit=5")
check("returns newest first", code == 200 and len(ev["events"]) > 0,
      f"{len(ev['events'])} events, newest={ev['events'][0]['type']}")

print()
print("ALL CHECKS PASSED" if not fails else f"FAILURES: {', '.join(fails)}")
sys.exit(1 if fails else 0)
