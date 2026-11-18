"""End-to-end test for the Fashion AesRec score.

The score must be decomposable and grounded: every sub-score has to come from a
measurable signal, and the style half has to be measured against the shopper's own
wardrobe rather than a generic taste model.
"""
import base64
import json
import os
import sys
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
    print(f"  {'PASS' if cond else 'FAIL'}  {name:46s} {detail}")
    if not cond:
        fails.append(name)


def data_uri(rel):
    # Served URLs look like /assets/products/p004.jpg but live under public/.
    rel = rel.replace("/", os.sep).lstrip("\\")
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        path = os.path.join(ROOT, "public", rel)
    with open(path, "rb") as fh:
        return "data:image/jpeg;base64," + base64.b64encode(fh.read()).decode()


print("== service status ==")
code, st = call("/api/aesthetic/status")
check("scoring service online", code == 200 and st.get("online") is True, st.get("model"))
check("same encoder as visual search", "SigLIP" in (st.get("model") or "") or "clip" in (st.get("model") or "").lower(),
      st.get("model"))

print("\n== score one outfit photo ==")
img = data_uri("/assets/products/p004.jpg")
code, r = call("/api/aesthetic/score?lang=zh", {"image": img})
check("score returned", code == 200 and isinstance(r.get("score"), int), f"HTTP {code}")
if not r.get("score") and r.get("score") != 0:
    print("   body:", json.dumps(r)[:300])

score = r.get("score")
check("score inside 0-100", isinstance(score, int) and 0 <= score <= 100, score)
subs = r.get("subscores") or {}
check("three sub-scores present",
      set(subs) == {"style", "coverage", "palette"}, ", ".join(subs))
check("every sub-score in 0-100",
      all(isinstance(v, int) and 0 <= v <= 100 for v in subs.values()),
      " ".join(f"{k}={v}" for k, v in subs.items()))

# The overall must be the published weighted sum, not a separate opaque number.
w = r.get("weights") or {}
expected = round(w.get("style", 0) * subs.get("style", 0)
                 + w.get("coverage", 0) * subs.get("coverage", 0)
                 + w.get("palette", 0) * subs.get("palette", 0))
check("overall equals the weighted sum", abs(expected - score) <= 1,
      f"recomputed {expected} vs reported {score}")
check("weights sum to 1.0", abs(sum(w.values()) - 1.0) < 0.01, w)
# Pins the fairness decision: palette is the only component carrying a built-in
# aesthetic prior, so it is deliberately the smallest weight.
check("palette carries the smallest weight", w.get("palette", 1) <= 0.10 and w.get("style", 0) >= 0.60, w)

print("\n== fairness: the palette judges structure, not restraint ==")
detail = r.get("detail") or {}
pal = detail.get("palette") or {}
check("palette reports a scheme", pal.get("scheme") in
      ("neutral", "monochrome", "two-tone", "complementary", "analogous", "analogous-wide", "scattered"),
      pal.get("scheme"))
check("palette exposes hue centres", isinstance(pal.get("hueCentres"), list), pal.get("hueCentres"))
check("coverage is derived from the wardrobe", isinstance(detail.get("requiredCategories"), list) and
      len(detail.get("requiredCategories")) > 0, detail.get("requiredCategories"))
check("verdict label localised", r.get("verdictLabel") in ("很襯你", "不錯", "尚可", "可以再調整"),
      r.get("verdictLabel"))
check("judge is named", bool(r.get("judge")), r.get("judge"))

print("\n== the style half is grounded in the wardrobe ==")
detail = r.get("detail") or {}
check("wardrobe items were used", (detail.get("wardrobeUsed") or 0) > 0,
      f"{detail.get('wardrobeUsed')} owned items")
closest = detail.get("closestOwned") or []
check("closest owned items named", len(closest) > 0 and all(c.get("name") for c in closest),
      ", ".join(c.get("id", "?") for c in closest))
check("similarity is a cosine", all(-1.01 <= (c.get("similarity") or 0) <= 1.01 for c in closest),
      closest[0].get("similarity") if closest else "")
check("reasons reference numbers", len(r.get("reasons") or []) == 3,
      ", ".join(x.get("key", "") for x in r.get("reasons") or []))

print("\n== a second photo gives a different, plausible score ==")
img2 = data_uri("/assets/products/p007.jpg")
code2, r2 = call("/api/aesthetic/score?lang=zh", {"image": img2})
check("second photo scores", code2 == 200 and isinstance(r2.get("score"), int), r2.get("score"))
check("scores are not constant", r2.get("score") != score,
      f"p004={score} p007={r2.get('score')}")
check("palette detail present in both",
      bool((r2.get("detail") or {}).get("palette", {}).get("colours")),
      str((r2.get("detail") or {}).get("palette", {}).get("distinctHues")) + " hues")

print("\n== input validation ==")
code3, bad = call("/api/aesthetic/score", {})
check("missing image rejected", code3 == 400, bad.get("error"))

print()
print("ALL CHECKS PASSED" if not fails else f"FAILURES: {', '.join(fails)}")
sys.exit(1 if fails else 0)
