"""End-to-end test for the Prophet price-forecasting integration.

Exercises the public API (Node -> lib/forecast.js -> Prophet service) and checks
that the model, the sale-calendar events, the advisory and the holdout
comparison all agree with each other.
"""
import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
fails = []


def get(path, timeout=90):
    req = urllib.request.Request(BASE + path)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "ignore") or "{}")
        except Exception:
            return e.code, {}


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name:50s} {detail}")
    if not cond:
        fails.append(name)


print("== service status ==")
code, st = get("/api/forecast/status")
check("Prophet service online", code == 200 and st.get("online") is True,
      f"v{st.get('version')} {st.get('products')} products, {st.get('observations')} obs")
check("catalogue loaded fully", st.get("products") == 40, st.get("products"))
check("30-day horizon", st.get("horizonDays") == 30, st.get("horizonDays"))

print("\n== a forecast that should say WAIT (upcoming sale) ==")
code, f = get("/api/forecast/p007")
check("engine is prophet", f.get("engine") == "prophet", f.get("engineLabel"))
check("has uncertainty band", all(p.get("lower") is not None for p in f.get("forecast", [])),
      "lower/upper present")
check("has 30 forecast points", len(f.get("forecast", [])) == 30, len(f.get("forecast", [])))
check("history series present", len(f.get("history", [])) >= 100, len(f.get("history", [])))
check("advisory waits", f["advisory"]["action"] == "wait", f["advisory"]["headline_zh"])
check("drop is material", f["advisory"]["expectedDropPct"] >= 4, f"{f['advisory']['expectedDropPct']}%")
check("double-11 detected ahead", any(e["name"] == "double11" for e in f.get("events", [])),
      ", ".join(f"{e['label']} ({e['daysAway']}d)" for e in f.get("events", [])))
check("event price below current",
      all(e["predictedPrice"] < f["current"] for e in f.get("events", []) if e["dropPct"] > 0),
      f"current {f['current']}")

print("\n== holdout comparison attached ==")
comp = f.get("comparison") or {}
check("three models scored", len(comp.get("models", [])) == 3,
      ", ".join(m["name"] for m in comp.get("models", [])))
check("metrics are numbers", all(isinstance(m.get("mape"), (int, float)) for m in comp.get("models", [])),
      " | ".join(f"{m['name']} {m['mape']}%" for m in comp.get("models", [])))
check("a best model is named", comp.get("best") in [m["name"] for m in comp.get("models", [])],
      comp.get("best"))

print("\n== advisory variety across the catalogue (not all identical) ==")
actions = {}
drops = []
code, products = get("/api/products", timeout=30)
ids = [p["id"] for p in products] if isinstance(products, list) else []
for pid in ids:
    code, ff = get(f"/api/forecast/{pid}?horizon=30")
    if code != 200:
        continue
    actions.setdefault(ff["advisory"]["action"], []).append(pid)
    drops.append(ff["advisory"]["expectedDropPct"])
print(f"    {len(ids)} products: " + json.dumps({k: len(v) for k, v in actions.items()}))
print(f"    projected drop range: {min(drops):.1f}% .. {max(drops):.1f}%")
check("more than one advisory outcome exists", len(actions) >= 2,
      f"{len(actions)} distinct outcomes")
check("a meaningful minority says 'buy'", len(actions.get("buy", [])) >= 3,
      f"{len(actions.get('buy', []))} buy advisories")
check("drops vary by product", (max(drops) - min(drops)) > 5,
      f"{max(drops) - min(drops):.1f} pp spread")

print("\n== catalogue-wide evaluation ==")
code, ev = get("/api/forecast-eval", timeout=30)
check("eval available", code == 200 and "aggregate" in ev, f"{ev.get('productsEvaluated')} products")
agg = {a["name"]: a for a in ev.get("aggregate", [])}
if "Prophet" in agg and "Linear trend" in agg:
    check("Prophet beats the linear baseline",
          agg["Prophet"]["mape"] < agg["Linear trend"]["mape"],
          f"{agg['Prophet']['mape']}% vs {agg['Linear trend']['mape']}%")
    check("Prophet wins most products",
          ev.get("wins", {}).get("Prophet", 0) >= ev.get("productsEvaluated", 40) * 0.8,
          f"{ev.get('wins', {}).get('Prophet')}/{ev.get('productsEvaluated')}")
check("synthetic-data caveat recorded", bool(ev.get("note")), "note present")

print("\n== unknown product ==")
code, _ = get("/api/forecast/does-not-exist")
check("404 for unknown id", code == 404, f"HTTP {code}")

print()
print("ALL CHECKS PASSED" if not fails else f"FAILURES: {', '.join(fails)}")
sys.exit(1 if fails else 0)
