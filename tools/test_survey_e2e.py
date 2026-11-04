"""End-to-end test for the preference survey and its prize wheel.

Checks the promises of the feature:
  1. a session returns pairwise questions about the shopper's own categories
  2. answers update the Bradley-Terry scores
  3. finish quotes what the answers were worth but issues nothing
  4. the wheel decides the prize, on the server, and the odds are published
  5. the reward decays as the model learns
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


def run_session(tag, choice="left"):
    """Start, answer everything, finish. Returns (session_id, finish_body)."""
    _, s = call("/api/survey/start", {"lang": "zh", "n": 3, "session": tag})
    for q in s.get("questions", []):
        call("/api/survey/answer", {
            "sessionId": s["sessionId"], "questionId": q["id"],
            "choice": choice, "session": tag,
        })
    _, f = call("/api/survey/finish", {"sessionId": s["sessionId"], "session": tag})
    return s["sessionId"], f


print("== start a session ==")
code, s = call("/api/survey/start", {"lang": "zh", "n": 3, "session": "e2e-survey"})
qs = s.get("questions", [])
check("returns questions", code == 200 and len(qs) == 3, f"{len(qs)} questions")
check("session id issued", bool(s.get("sessionId")))

if qs:
    q = qs[0]
    check("each question has two sides",
          bool(q.get("left", {}).get("id") and q.get("right", {}).get("id")),
          f"{q['left']['id']} vs {q['right']['id']}")
    check("sides are different products", q["left"]["id"] != q["right"]["id"])
    check("cards carry an image or emoji", bool(q["left"].get("image") or q["left"].get("emoji")))
    check("pairs compare within a category",
          all(x["left"]["category"] == x["right"]["category"] for x in qs),
          ", ".join(x["left"]["category"] for x in qs))
    check("information gain is attached",
          all(isinstance(x.get("infoGain"), (int, float)) for x in qs),
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
check("duplicate answer rejected", code == 400 and dup.get("error") == "already_answered",
      dup.get("error"))

after = call("/api/survey/profile")[1]
check("comparison count increased", after["comparisons"] == before["comparisons"] + len(qs),
      f"{before['comparisons']} -> {after['comparisons']}")
check("learned categories reported", len(after.get("topCategories", [])) > 0,
      ", ".join(after.get("topCategories", [])))

print("\n== finish quotes the answers, and issues nothing yet ==")
code, f = call("/api/survey/finish", {"sessionId": s["sessionId"], "session": "e2e-survey"})
check("finish succeeds", code == 200 and f.get("ok") is True)
check("a quote is returned", isinstance(f.get("quoteHkd"), (int, float)),
      f"HK${f.get('quoteHkd')}")
check("quote inside HK$1-12", 1 <= f.get("quoteHkd", 0) <= 12)
check("no coupon before the spin", f.get("coupon") in (None, {}), f.get("coupon"))
check("eight wheel segments", len(f.get("segments") or []) == 8,
      f"{len(f.get('segments') or [])}")
odds = f.get("odds") or []
check("odds are published", len(odds) == 8 and abs(sum(o["pct"] for o in odds) - 100) < 2,
      f"sum = {round(sum(o['pct'] for o in odds), 1)}%")
check("spins available", f.get("spinsLeft") == 2, f.get("spinsLeft"))

print("\n== the wheel decides the prize ==")
code, sp = call("/api/survey/spin", {"sessionId": s["sessionId"], "session": "e2e-survey"})
check("spin accepted", code == 200 and sp.get("ok") is True)

# The "again" segment is legitimate; take the second spin when it lands.
if (sp.get("segment") or {}).get("again"):
    check("'again' segment refills a spin", sp.get("spinsLeft", 0) >= 1, sp.get("spinsLeft"))
    code, sp = call("/api/survey/spin", {"sessionId": s["sessionId"], "session": "e2e-survey"})
    check("second spin accepted", code == 200 and sp.get("ok") is True)

seg = sp.get("segment") or {}
coupon = sp.get("coupon") or {}
check("index is inside the wheel", 0 <= sp.get("index", -1) < 8, sp.get("index"))
check("prize is a cash coupon", coupon.get("kind") == "amount", coupon.get("code"))
check("prize matches the landed segment", coupon.get("amountHkd") == seg.get("hkd"),
      f"segment HK${seg.get('hkd')} vs coupon HK${coupon.get('amountHkd')}")
check("code encodes the value", str(coupon.get("code", "")).startswith("CASH"), coupon.get("code"))

print("\n== spin limits ==")
code, again = call("/api/survey/spin", {"sessionId": s["sessionId"], "session": "e2e-survey"})
check("no free re-spins once the prize is paid",
      code == 400 or again.get("duplicate") is True, f"HTTP {code} {again.get('error','')}")
if again.get("coupon"):
    check("re-spin does not mint a second coupon", again["coupon"]["code"] == coupon["code"])

print("\n== the coupon is real ==")
code, v = call(f"/api/analytics/coupon/{coupon['code']}")
check("coupon validates", code == 200 and v.get("coupon", {}).get("kind") == "amount",
      v.get("coupon", {}).get("status"))

code, r = call("/api/survey/answer", {"sessionId": "nope", "questionId": "x", "choice": "left"})
check("unknown session rejected", code == 400, r.get("error"))

print("\n== the quote decays as the model learns ==")
sid2, f2 = run_session("e2e-survey-2", choice="right")
second = f2.get("quoteHkd")
check("second session quotes no more than the first",
      isinstance(second, (int, float)) and second <= f.get("quoteHkd", 0),
      f"first HK${f.get('quoteHkd')} -> second HK${second}")
check("second quote stays in range", 1 <= (second or 0) <= 12, f"HK${second}")

print()
print("ALL CHECKS PASSED" if not fails else f"FAILURES: {', '.join(fails)}")
sys.exit(1 if fails else 0)
