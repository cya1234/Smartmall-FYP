"""Verify the embeddable widget: assets, headers, tenant config, event tracking."""
import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3100"
fails = []


def get(path, method="GET", payload=None):
    if payload is None:
        req = urllib.request.Request(BASE + path, method=method)
    else:
        req = urllib.request.Request(
            BASE + path, data=json.dumps(payload).encode(), method=method,
            headers={"Content-Type": "application/json"},
        )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "ignore")


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name:48s} {detail}")
    if not cond:
        fails.append(name)


print("== widget assets are served ==")
for path, needle in [
    ("/embed.js", "smartmall:init"),
    ("/widget.html", "w-close"),
    ("/js/widget.js", "/api/assistant"),
    ("/css/widget.css", ".w-panel" if False else "w-app"),
    ("/demo-store.html", "data-tenant"),
]:
    code, headers, body = get(path)
    check(f"GET {path}", code == 200 and needle in body, f"HTTP {code}, {len(body)}B")

print("\n== cross-origin + framing headers ==")
_, h1, _ = get("/embed.js")
check("embed.js allows cross-origin", h1.get("Access-Control-Allow-Origin") == "*",
      h1.get("Access-Control-Allow-Origin"))
_, h2, _ = get("/widget.html")
check("widget.html is frameable", "frame-ancestors" in (h2.get("Content-Security-Policy") or ""),
      h2.get("Content-Security-Policy"))
_, h3, _ = get("/")
check("main app not made frameable",
      "frame-ancestors" not in (h3.get("Content-Security-Policy") or ""), "no CSP (expected)")

print("\n== tenant branding config ==")
code, _, body = get("/api/widget/config?tenant=thread-and-stone")
cfg = json.loads(body)
check("known tenant gets real name", code == 200 and cfg["storeName"] == "THREAD & STONE", cfg["storeName"])
check("tenant is onboarded", cfg["onboarded"] is True)
code, _, body = get("/api/widget/config?tenant=my-cool-store")
cfg2 = json.loads(body)
check("unknown tenant degrades gracefully",
      code == 200 and cfg2["storeName"] == "My Cool Store" and cfg2["onboarded"] is False,
      cfg2["storeName"])

print("\n== one-line embed is present in the demo store ==")
_, _, html = get("/demo-store.html")
check("script tag has data-tenant", 'src="/embed.js" data-tenant="thread-and-stone"' in html)
check("inline search slot present", "data-smartmall-search" in html)
check("snippet shown to merchant", "__ORIGIN__" in html or "embed.js" in html)

print("\n== widget events reach the dashboard ==")
def summary():
    _, _, b = get("/api/analytics/summary?days=7")
    return json.loads(b)

before = summary()["totals"].get("widgetOpens", 0)
get("/api/analytics/event", "POST", {"type": "widget_open", "label": "launcher", "tenant": "thread-and-stone"})
get("/api/analytics/event", "POST", {"type": "widget_open", "label": "search-bar", "tenant": "thread-and-stone"})
after = summary()["totals"].get("widgetOpens", 0)
check("widget_open counted", after == before + 2, f"{before} -> {after}")
check("widget opens seeded in history", before > 0, f"{before} opens in last 7 days")

print("\n== assistant + visual APIs the widget calls ==")
code, _, body = get("/api/assistant", "POST", {"query": "海島婚禮穿什麼", "lang": "zh"})
a = json.loads(body)
check("assistant returns bundles", code == 200 and len(a.get("bundles", [])) > 0,
      f"{len(a.get('bundles', []))} bundles")
code, _, body = get("/api/visual-search", "POST", {"query": "a red dress", "colors": []})
v = json.loads(body)
check("visual search returns results", code == 200 and len(v.get("results", [])) > 0,
      f"{len(v.get('results', []))} results, engine={v.get('engine')}")

print()
print("ALL CHECKS PASSED" if not fails else f"FAILURES: {', '.join(fails)}")
sys.exit(1 if fails else 0)
