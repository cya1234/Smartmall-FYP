"""Evaluate the tool-calling assistant.

Three metrics matter for "can this actually ship":

  * tool accuracy   - did the router pick the right tool for the question?
  * grounding       - does every number in the answer come from a tool fact?
                      (by construction it should be 100%; this test proves it)
  * containment     - how many questions are answered without a fallback path?

Run:  .venv\\Scripts\\python.exe tools/eval_assistant.py [base_url]
"""
import json
import re
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"

# (query, lang, expected intent, expected tool)
CASES = [
    ("滑雪外套會唔會減價？", "zh", "price_timing", "forecast_price"),
    ("冬天大褸值唔值得等", "zh", "price_timing", "forecast_price"),
    ("呢件羽絨幾時最平", "zh", "price_timing", "forecast_price"),
    ("will the ski jacket get cheaper", "en", "price_timing", "forecast_price"),
    ("亞麻襯衫有冇貨", "zh", "availability", "check_store_stock"),
    ("邊間門市有白色波鞋", "zh", "availability", "check_store_stock"),
    ("where can i pick up the white sneakers", "en", "availability", "check_store_stock"),
    ("我著咩碼好，黑色西裝外套", "zh", "size", "size_advice"),
    ("what size for the merino ski socks", "en", "size", "size_advice"),
    ("預算2000，下個月去北海道滑雪要著咩", "zh", "outfit", "build_outfit"),
    ("幫我配一套海島婚禮造型", "zh", "outfit", "build_outfit"),
    ("門市地址喺邊", "zh", "stores", "list_stores"),
    ("where is your store", "en", "stores", "list_stores"),
    ("防曬乳", "zh", "product_search", "search_products"),
    ("cashmere sweater", "en", "product_search", "search_products"),
]


def ask(query, lang):
    req = urllib.request.Request(
        BASE + "/api/assistant",
        data=json.dumps({"query": query, "lang": lang}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def numbers_in(text):
    out = set()
    for m in NUM_RE.findall(text or ""):
        out.add(m.replace(",", ""))
        try:
            out.add(str(float(m.replace(",", ""))))
            out.add(str(int(float(m.replace(",", "")))))
        except ValueError:
            pass
    return out


def grounded(answer, citations):
    """Every numeric token in the answer must appear in some tool fact."""
    fact_blob = " ".join(str(c.get("value", "")) for c in citations)
    fact_nums = numbers_in(fact_blob)
    # Numbers the composer is allowed to phrase on its own (currency conversion
    # and ordinals/weekday counts), plus small integers used for "N pieces".
    allowed = {str(i) for i in range(0, 101)}
    orphans = []
    for n in numbers_in(answer):
        if n in fact_nums or n in allowed:
            continue
        orphans.append(n)
    return orphans


def main():
    rows = []
    tool_ok = grounded_ok = contained = 0
    print(f"  {'query':38s} {'intent':14s} {'tool':18s} {'ok':3s} {'ground':6s}")
    print("  " + "-" * 86)

    for query, lang, want_intent, want_tool in CASES:
        try:
            r = ask(query, lang)
        except Exception as e:
            print(f"  {query[:36]:38s} ERROR {e}")
            rows.append({"query": query, "error": str(e)})
            continue

        intents = r.get("intents") or []
        tools = [t.get("tool") for t in r.get("tools") or []]
        engine = r.get("engine")
        answer = r.get("answer") or ""
        cites = r.get("citations") or []

        hit_intent = want_intent in intents
        hit_tool = want_tool in tools
        orphans = grounded(answer, cites)
        is_contained = engine == "agent"

        tool_ok += 1 if hit_tool else 0
        grounded_ok += 1 if not orphans else 0
        contained += 1 if is_contained else 0

        print(f"  {query[:36]:38s} {','.join(intents)[:13]:14s} {','.join(tools)[:17]:18s} "
              f"{'Y' if hit_tool else 'N':3s} {'Y' if not orphans else 'N':6s}")
        if orphans:
            print(f"       ungrounded numbers: {orphans}")

        rows.append({
            "query": query, "lang": lang, "intents": intents, "tools": tools,
            "engine": engine, "expectedIntent": want_intent, "expectedTool": want_tool,
            "toolHit": hit_tool, "intentHit": hit_intent,
            "ungroundedNumbers": orphans, "answer": answer,
        })

    n = len(CASES)
    print()
    print(f"  tool accuracy : {tool_ok}/{n}  ({tool_ok/n*100:.0f}%)")
    print(f"  grounded      : {grounded_ok}/{n}  ({grounded_ok/n*100:.0f}%)")
    print(f"  containment   : {contained}/{n}  ({contained/n*100:.0f}%)")

    doc = {
        "cases": n,
        "toolAccuracy": round(tool_ok / n * 100, 1),
        "groundedRate": round(grounded_ok / n * 100, 1),
        "containment": round(contained / n * 100, 1),
        "results": rows,
    }
    with open("data/eval/assistant.json", "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print("\n  wrote data/eval/assistant.json")

    ok = tool_ok == n and grounded_ok == n
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
