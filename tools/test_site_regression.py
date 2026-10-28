"""Full-site regression check after the CLIP integration."""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:3000"
fails = []


def get(path):
    return json.load(urllib.request.urlopen(BASE + path, timeout=30))


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=60))


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name:40s} {detail}")
    if not cond:
        fails.append(name)


print("== core ==")
check("health", get("/api/health").get("ok") is True)
products = get("/api/products")
check("catalog", len(products) == 40, f"{len(products)} products")
check("zh search", len(get("/api/products?q=%E6%BB%91%E9%9B%AA")) > 0, "滑雪")

print("\n== original AI modules still work ==")
bb = post("/api/blindbox", {"query": "預算 2000，下個月去北海道滑雪，需要一套裝備", "budget": 2000, "lang": "zh"})
check("blind box", bb["scenario"]["id"] == "ski", f"{len(bb['items'])} items, {bb['coverage']}% coverage")
a = post("/api/assistant", {"query": "我下個月要去海島婚禮，穿什麼好？", "lang": "zh"})
check("assistant memory", len(a.get("memoryUsed", [])) > 0, a["bundles"][0]["title"][:34])
pa = post("/api/price-agent", {"productIds": ["p031", "p032"], "lang": "zh"})
check("price agent", pa["summary"]["negotiatedTotal"] < pa["summary"]["originalTotal"],
      f"{pa['summary']['originalTotal']} -> {pa['summary']['negotiatedTotal']}")
rs = post("/api/resale/draft", {"productId": "p010", "condition": "fair", "monthsOwned": 11})
check("resale draft", rs["price"] > 0, f"price {rs['price']}")
soc = post("/api/social/polls", {"productId": "p031", "groupId": "bff"})
soc2 = post(f"/api/social/polls/{soc['id']}/simulate", {})
check("social voting", soc2["tally"]["total"] == 5, soc2["verdict"]["zh"][:26])
pr = get("/api/profile?lang=zh")
check("profile/memory", len(pr["insights"]) > 0 and len(pr["wardrobe"]) > 0,
      f"{len(pr['insights'])} insights, {len(pr['wardrobe'])} wardrobe")
r1 = get("/api/return-risk/p032?lang=zh")
check("return prediction", r1["recommendedSize"] != r1["usualSize"], f"{r1['usualSize']}->{r1['recommendedSize']}")
s = post("/api/support/session", {"productId": "p004", "reason": "defect"})
an = post("/api/support/analyze", {"sessionId": s["id"], "lang": "zh",
                                   "features": {"brightness": 0.42, "edgeDensity": 0.09,
                                                "colourVariance": 0.21, "darkSpotRatio": 0.14, "saturation": 0.35}})
form = post("/api/support/submit", {"sessionId": s["id"], "lang": "zh"})
check("smart support", form["rma"].startswith("RMA-"), f"{an['label_zh']} -> {form['rma']}")
fc = get("/api/forecast/p031")
check("forecast", fc["advisory"]["headline_zh"] is not None, fc["advisory"]["headline_zh"])
# Try-on is now a real CatVTON call: without a photo it reports needs-photo
# (or unavailable if the service is down); the overlay fallback still works.
tr = post("/api/tryon", {"productId": "p031"})
tn = tr.get("status")
check("try-on", tn in ("needs-photo", "unavailable", "synthesized"),
      f"status={tn} engine={tr.get('engine')}")

print("\n== new CLIP visual search ==")
st = get("/api/visual-search/status")
clip_on = st.get("online") is True
if clip_on:
    check("clip online", True, f"{st.get('model')} on {st.get('gpu')}, {st.get('indexed')} indexed")
    vs = post("/api/visual-search", {"query": "a blue ski jacket"})
    check("clip retrieval", vs.get("engine") == "clip" and vs["results"][0]["id"] in ("p031", "p007"),
          f"top={vs['results'][0]['id']} {vs.get('tookMs')}ms")
else:
    # CLIP is stopped on purpose (it holds ~640 MiB of VRAM). The site must
    # still answer visual search from the colour fallback.
    vs = post("/api/visual-search", {"query": "a blue ski jacket"})
    check("clip offline -> colour fallback", vs.get("engine") == "colour" and len(vs["results"]) > 0,
          f"engine={vs.get('engine')}, {len(vs['results'])} results")
    print("       (start ai-service/visual_search_service.py to test real CLIP retrieval)")

print("\n== product photos ==")
withimg = [p for p in products if p.get("image")]
raw = urllib.request.urlopen(BASE + withimg[0]["image"], timeout=20).read()
check("photos served", raw[:2] == b"\xff\xd8" and len(raw) > 5000, f"{len(withimg)} photos, {len(raw)//1024}KB")
missing = [p["id"] for p in products if not p.get("image")]
check("emoji fallback for unmatchable items", len(missing) == 6, ",".join(missing))

print(f"\n  {'ALL SITE CHECKS PASSED' if not fails else 'FAILURES: ' + ', '.join(fails)}")
sys.exit(1 if fails else 0)
