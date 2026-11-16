"""Compare the two assistant routers on the same labelled question set.

Both routers share buildPlan() and extractEntities(), so the only thing being
measured is intent classification — which is exactly the part an LLM replaces.

    python tools/eval_router.py [base_url]

Reads the 15 labelled cases already used by tools/eval_assistant.py, asks the
server for a plan under each router (no tools are executed), and reports:

    intent accuracy   the classified intents match the expected set
    tool accuracy     the expected tool appears in the plan
    fallback rate     how often the llm router gave up and used rules
    latency           per-question planning time
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CASES = os.path.join(ROOT, "data", "eval", "assistant.json")
OUT = os.path.join(ROOT, "data", "eval", "router.json")


def get(path, timeout=60):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def plan_for(query, lang, router):
    qs = urllib.parse.urlencode({"q": query, "lang": lang, "router": router})
    return get(f"/api/assistant/route?{qs}")


def load_cases():
    with open(CASES, encoding="utf-8") as fh:
        doc = json.load(fh)
    cases = []
    for row in doc["results"]:
        expected = row.get("expectedIntent")
        if isinstance(expected, str):
            expected = [expected]
        cases.append({
            "query": row["query"],
            "lang": row.get("lang", "zh"),
            "expectedIntents": sorted(expected or []),
            "expectedTool": row.get("expectedTool"),
        })
    return cases


def score(cases, router):
    rows = []
    for c in cases:
        try:
            p = plan_for(c["query"], c["lang"], router)
        except Exception as err:                     # noqa: BLE001
            rows.append({**c, "error": str(err), "intentHit": False, "toolHit": False})
            continue
        got = sorted(p.get("intents") or [])
        rows.append({
            **c,
            "intents": got,
            "tools": p.get("tools") or [],
            "source": p.get("source"),
            "latencyMs": p.get("latencyMs"),
            "intentHit": got == c["expectedIntents"],
            "toolHit": c["expectedTool"] in (p.get("tools") or []),
        })
    n = len(rows) or 1
    lat = [r["latencyMs"] for r in rows if r.get("latencyMs") is not None]
    return {
        "router": router,
        "cases": len(rows),
        "intentAccuracy": round(100 * sum(r["intentHit"] for r in rows) / n, 1),
        "toolAccuracy": round(100 * sum(r["toolHit"] for r in rows) / n, 1),
        "fellBack": sum(1 for r in rows if r.get("source") == "rules"),
        "meanLatencyMs": round(sum(lat) / len(lat), 1) if lat else None,
        "rows": rows,
    }


def main():
    cases = load_cases()
    print(f"  {len(cases)} labelled questions\n")

    health = get("/api/assistant/llm")
    print(f"  LLM configured : {health.get('enabled')}  reachable : {health.get('ok')}")
    print(f"  model          : {health.get('model')}\n")

    t0 = time.time()
    rules = score(cases, "rules")
    llm = score(cases, "llm")

    print("  router   intent   tool   fell back   mean latency")
    print("  " + "-" * 52)
    for r in (rules, llm):
        print(f"  {r['router']:<8} {r['intentAccuracy']:5.1f}%  {r['toolAccuracy']:5.1f}%"
              f"   {r['fellBack']:>6}      {r['meanLatencyMs']} ms")

    diff = llm["intentAccuracy"] - rules["intentAccuracy"]
    print(f"\n  delta (llm - rules): {diff:+.1f} pp")

    # Honesty guard: tools/mock_llm_server.py is a keyword stub. Numbers from it say
    # nothing about how a real model performs, only that the harness runs.
    if str(health.get("model") or "").startswith("mock-"):
        print("  NOTE: this run used the scripted mock (tools/mock_llm_server.py),")
        print("        not a real model. The numbers prove the harness and the")
        print("        fallback path work; they say nothing about model quality.")

    # A model that is enabled but unreachable silently degrades to the rule router.
    # Saying so is more useful than reporting two identical columns.
    if health.get("enabled") and not health.get("ok"):
        print("  NOTE: the llm router is not reachable, so its column is the rule")
        print("        router's numbers. Start a model and re-run for a real comparison.")
    if llm["fellBack"] and llm["fellBack"] == len(cases) and health.get("ok"):
        print("  NOTE: every question fell back to rules - check the model output.")

    out = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "llm": {"enabled": health.get("enabled"), "ok": health.get("ok"), "model": health.get("model")},
        "rules": rules,
        "llmRouter": llm,
        "deltaIntent": round(diff, 1),
        "tookMs": round((time.time() - t0) * 1000),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(f"\n  wrote {os.path.relpath(OUT, ROOT)}")

    misses = [r for r in llm["rows"] if not r["intentHit"]]
    if misses:
        print(f"\n  llm misses ({len(misses)}):")
        for m in misses[:6]:
            print(f"    {m['query'][:38]:<38} want={m['expectedIntents']} got={m.get('intents')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
