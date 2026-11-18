"""End-to-end test for the search history and the onboarding survey.

The two things worth protecting: searches are actually recorded (one list, three
kinds of search), and the onboarding endpoint cannot be used to write arbitrary
structure into the state file.

Run: python tools/test_userstate_e2e.py [base_url]
"""
import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
fails = []


def call(path, payload=None, method=None, timeout=60):
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


print("== searches are recorded ==")
before = call("/api/history")[1]["total"]

call("/api/assistant", {"query": "e2e 測試查詢一", "lang": "zh"})
after_assistant = call("/api/history")[1]
check("assistant search recorded", after_assistant["total"] == before + 1,
      f"{before} -> {after_assistant['total']}")
check("recorded as kind=assistant", after_assistant["byKind"].get("assistant", 0) >= 1,
      after_assistant["byKind"])

call("/api/products?q=e2etext")
after_text = call("/api/history")[1]
check("catalogue search recorded", after_text["total"] == after_assistant["total"] + 1,
      f"{after_text['total']} total")
check("recorded as kind=text", after_text["byKind"].get("text", 0) >= 1, after_text["byKind"])

call("/api/visual-search", {"query": "e2e visual", "colors": [], "limit": 4})
after_visual = call("/api/history")[1]
check("visual search recorded", after_visual["byKind"].get("visual", 0) >= 1,
      after_visual["byKind"])

# An image-only search has no text; it must still show up rather than vanish.
call("/api/visual-search", {"image": "data:image/png;base64,iVBORw0KGgo=", "colors": [], "limit": 2})
kinds = call("/api/history")[1]["byKind"]
check("image-only search still counted", kinds.get("visual", 0) >= 2, kinds)

recent = call("/api/history?limit=5")[1]["recentQueries"]
check("recent list is newest first",
      [r["at"] for r in recent] == sorted((r["at"] for r in recent), reverse=True),
      [r["query"] for r in recent[:3]])
check("recent list has no duplicates",
      len({r["query"].lower() for r in recent}) == len(recent))

print("\n== onboarding is sanitised, not trusted ==")
junk = {
    "categories": ["Apparel"] * 50,
    "styles": "not-a-list",
    "colours": [1, 2, {"x": 1}, "Navy"],
    "budget": {"min": -999, "max": "abc"},
    "pairs": [{"winner": "p004"}, {"winner": "p004", "loser": "p007"}, "nope"],
}
code, saved = call("/api/onboarding", junk)
o = saved.get("onboarding") or {}
check("onboarding accepted", code == 200 and saved.get("ok") is True)
check("long lists truncated", len(o.get("categories") or []) <= 12, len(o.get("categories") or []))
check("non-list dropped", o.get("styles") == [], o.get("styles"))
check("non-string entries removed", o.get("colours") == ["Navy"], o.get("colours"))
check("budget clamped or null", (o.get("budget") or {}).get("min") in (0, None),
      o.get("budget"))
check("incomplete pairs dropped", len(o.get("pairs") or []) == 1, o.get("pairs"))

code, state = call("/api/onboarding")
check("state reports onboarded", state.get("onboarded") is True, state.get("onboarded"))
check("answers round-trip", (state.get("onboarding") or {}).get("colours") == ["Navy"],
      (state.get("onboarding") or {}).get("colours"))

print("\n== a real answer set ==")
code, saved2 = call("/api/onboarding", {
    "categories": ["Electronics", "Apparel"],
    "styles": ["Minimal"],
    "colours": ["Navy", "Black"],
    "avoidColours": ["Coral"],
    "occasions": ["Work"],
    "materials": ["Linen"],
    "budget": {"min": 300, "max": 1200},
    "pairs": [{"winner": "p004", "loser": "p007"}],
})
o2 = saved2.get("onboarding") or {}
check("categories stored", o2.get("categories") == ["Electronics", "Apparel"], o2.get("categories"))
check("occasions stored", o2.get("occasions") == ["Work"], o2.get("occasions"))
check("budget stored", o2.get("budget") == {"min": 300, "max": 1200}, o2.get("budget"))

print("\n== onboarding actually changes the ranking ==")
# The point of the survey is not to store answers, it is to reorder results. "black"
# spans categories (streetwear, a watch, earbuds), so a category preference must move
# the matching item up rather than merely being recorded.
def alternatives(query="black"):
    _, r = call("/api/assistant", {"query": query, "lang": "zh"})
    return [a["id"] for a in (r.get("alternatives") or [])]

call("/api/onboarding", {"categories": [], "styles": [], "colours": [], "avoidColours": []})
base = alternatives()
call("/api/onboarding", {"categories": ["Electronics"], "styles": [], "colours": [], "avoidColours": []})
elec = alternatives()
check("results are returned for the probe query", len(base) >= 2 and "p029" in base,
      f"base={base}")
check("an electronics preference moves the earbuds up",
      "p029" in elec and elec.index("p029") < base.index("p029"),
      f"{base} -> {elec}")

print("\n== click attention is exposed and bounded ==")
code, att = call("/api/engagement")
check("engagement endpoint answers", code == 200 and isinstance(att.get("categories"), list),
      f"{len(att.get('categories') or [])} categories")
cats = att.get("categories") or []
check("categories are sorted by attention",
      [c["score"] for c in cats] == sorted((c["score"] for c in cats), reverse=True),
      [c["score"] for c in cats])
check("counts are non-negative", all(c["views"] >= 0 and c["carts"] >= 0 for c in cats))
check("totals are reported", isinstance(att.get("totals"), dict) and att["totals"].get("views", -1) >= 0,
      att.get("totals"))

print("\n== clearing ==")
code, cleared = call("/api/history/clear", {})
check("history cleared", code == 200 and call("/api/history")[1]["total"] == 0,
      call("/api/history")[1]["total"])
check("onboarding survives a history clear",
      call("/api/onboarding")[1].get("onboarded") is True)

# Leave the demo profile neutral so the next visitor is not stuck with the probe's
# answers; the test does not need them any more.
call("/api/onboarding", {"categories": [], "styles": [], "colours": [], "avoidColours": []})

print()
print("ALL CHECKS PASSED" if not fails else f"FAILURES: {', '.join(fails)}")
sys.exit(1 if fails else 0)
