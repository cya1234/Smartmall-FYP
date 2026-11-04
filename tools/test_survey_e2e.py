"""End-to-end test for the preference survey and its cash coupons.

Checks the four promises of the feature:
  1. a session returns pairwise questions that actually involve the shopper's taste
  2. answers update the Bradley-Terry scores
  3. finishing issues a fixed-amount coupon whose value tracks information gain
  4. the coupon is a valid cash coupon the cart can apply
"""
import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
fails = []


def call(path, payload=None, method=None, timeout=30):
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
    print(f"  {'PASS' if cond else 'FAIL'}  {name:46s} {detail}")
    if not cond:
        fails.append(name)


print("== start a session ==")
code, s = call("/api/survey/start", {"lang": "zh", "n": 3, "session": "e2e-survey"})
qs = s.get("questions", [])
check("returns questions", code == 200 and len(qs) == 3, f"{len(qs)} questions")
check("session id issued", bool(s.get("sessionId")))

if qs:
    q = qs[0]
    check("each question has two sides", bool(q.get("left", {}).get("id") and q.get("right", {}).get("id")),
          f"{q['left']['id']} vs {q['right']['id']}")
    check("sides are different products", q["left"]["id"] != q["right"]["id"])
    check("cards carry an image or emoji",
          bool(q["left"].get("image") or q["left"].get("emoji")))
    same_cat = all(x["left"]["category"] == x["right"]["category"] for x in qs)
    check("pairs compare within a category", same_cat,
          ", ".join(f"{x['left']['category']}" for x in qs))
    check("information gain is attached", all(isinstance(x.get("infoGain"), (int, float)) for x in qs),
          f"first = {qs[0].get('infoGain')}")

print("\n== answer all of them ==")
before = call("/api/survey/profile")[1]
answered = 0
for q in qs:
    code, r = call("/api/survey/answer", {
        "sessionId": s["sessionId"], "questionId": q["id"],
        "choice": "left", "session": "e2e-survey",
    })
    if code == 200 and r.get("ok"):
        answered += 1
check("all answers accepted", answered == len(qs), f"{answered}/{len(qs)}")

code, dup = call("/api/survey/answer", {
    "sessionId": s["sessionId"], "questionId": qs[0]["id"], "choice": "right",
})
check("duplicate answer rejected", code == 400 and dup.get("error") == "already_answered", dup.get("error"))

after = call("/api/survey/profile")[1]
check("comparison count increased", after["comparisons"] == before["comparisons"] + len(qs),
      f"{before['comparisons']} -> {after['comparisons']}")
check("learned categories reported", len(after.get("topCategories", [])) > 0,
      ", ".join(after.get("topCategories", [])))
check("favourites have scores", all(isinstance(f.get("score"), (int, float)) for f in after.get("favourites", [])),
      f"{len(after.get('favourites', []))} items")

print("\n== claim the reward ==")
code, f = call("/api/survey/finish", {"sessionId": s["sessionId"], "session": "e2e-survey"})
coupon = f.get("coupon") or {}
check("coupon issued", code == 200 and f.get("ok") is True, coupon.get("code"))
check("kind is a cash amount", coupon.get("kind") == "amount", coupon.get("kind"))
amount = coupon.get("amountHkd")
check("amount is HK$1-10", isinstance(amount, (int, float)) and 1 <= amount <= 10, f"HK${amount}")
check("code reflects the value", str(coupon.get("code", "")).startswith("CASH"), coupon.get("code"))
check("learned summary returned", bool(f.get("learned", {}).get("topCategories")))

code, again = call("/api/survey/finish", {"sessionId": s["sessionId"], "session": "e2e-survey"})
check("finishing twice is idempotent",
      code == 200 and again.get("duplicate") is True and again["coupon"]["code"] == coupon["code"])

print("\n== the coupon is real ==")
code, v = call(f"/api/analytics/coupon/{coupon['code']}")
check("coupon validates", code == 200 and v.get("coupon", {}).get("kind") == "amount",
      v.get("coupon", {}).get("status"))

code, r = call("/api/survey/answer", {"sessionId": "does-not-exist", "questionId": "x", "choice": "left"})
check("unknown session rejected", code == 400, r.get("error"))

print("\n== the reward decays as the model learns ==")
code, s2 = call("/api/survey/start", {"lang": "zh", "n": 3, "session": "e2e-survey"})
for q2 in s2.get("questions", []):
    call("/api/survey/answer", {
        "sessionId": s2["sessionId"], "questionId": q2["id"],
        "choice": "right", "session": "e2e-survey",
    })
code, f2 = call("/api/survey/finish", {"sessionId": s2["sessionId"], "session": "e2e-survey"})
second = (f2.get("coupon") or {}).get("amountHkd")
check("second session pays no more than the first", isinstance(second, (int, float)) and second <= amount,
      f"first HK${amount} -> second HK${second}")
check("reward stays inside the advertised range", 1 <= (second or 0) <= 10, f"HK${second}")

print()
print("ALL CHECKS PASSED" if not fails else f"FAILURES: {', '.join(fails)}")
sys.exit(1 if fails else 0)
