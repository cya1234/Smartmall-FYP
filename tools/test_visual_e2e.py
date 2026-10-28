"""End-to-end test of the wired-in visual search through the Node API.

Exercises the public HTTP surface (not the Python service directly) so it
validates the whole chain: Node route -> lib/visualSearch.js -> CLIP service ->
FAISS, plus the colour fallback and the product-image wiring.

Run:  .venv\\Scripts\\python.exe tools\\test_visual_e2e.py
"""
import base64
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:3000"


def get(path):
    return json.load(urllib.request.urlopen(BASE + path, timeout=30))


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=60))


def main():
    fails = []

    def check(name, cond, detail=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {name:44s} {detail}")
        if not cond:
            fails.append(name)

    print("== service status ==")
    st = get("/api/visual-search/status")
    check("CLIP service online", st.get("online") is True, f"{st.get('model')} on {st.get('gpu')}")
    check("index populated", (st.get("indexed") or 0) >= 30, f"{st.get('indexed')} products indexed")

    print("\n== product photos wired into the catalog ==")
    products = get("/api/products")
    with_photo = [p for p in products if p.get("image")]
    check("products have photos", len(with_photo) >= 30, f"{len(with_photo)}/{len(products)}")
    img_path = with_photo[0]["image"]
    raw = urllib.request.urlopen(BASE + img_path, timeout=30).read()
    check("photo served over HTTP", len(raw) > 5000 and raw[:2] == b"\xff\xd8", f"{img_path} {len(raw)//1024}KB")

    print("\n== text -> product search through the API ==")
    for q, expect in [
        ("a red dress", "p003"),
        ("white sneakers", "p014"),
        ("black sunglasses", "p022"),
        ("beige trousers", "p012"),
    ]:
        r = post("/api/visual-search", {"query": q})
        top = [x["id"] for x in r["results"][:3]]
        check(f"text query {q!r}", expect in top, f"engine={r.get('engine')} top3={top} {r.get('tookMs')}ms")

    print("\n== image -> product search (real photo uploaded as the query) ==")
    query_img = base64.b64encode(raw).decode()
    r = post("/api/visual-search", {"image": query_img})
    top = [x["id"] for x in r["results"][:3]]
    check("image query returns the same product first",
          top and top[0] == with_photo[0]["id"],
          f"query={with_photo[0]['id']} top3={top} engine={r.get('engine')}")
    check("image mode reported", r.get("mode") == "image", f"mode={r.get('mode')} fusion={r.get('fusion')}")

    print("\n== fused image + text query (unified query embedding) ==")
    r2 = post("/api/visual-search", {"image": query_img, "query": "linen"})
    check("fusion reported", r2.get("mode") == "image+text", f"fusion={r2.get('fusion')} textWeight={r2.get('textWeight')}")
    check("fused query returns results", len(r2.get("results", [])) > 0, f"{len(r2.get('results', []))} results")
    # The fused query must differ from the pure-image ranking.
    check("fusion changes the ranking",
          [x["id"] for x in r2["results"]] != [x["id"] for x in r["results"]],
          "rankings differ")

    print("\n== match percentages present ==")
    r3 = post("/api/visual-search", {"query": "a blue ski jacket"})
    check("matchPercent on each result",
          all(isinstance(x.get("matchPercent"), int) for x in r3["results"]),
          f"top={r3['results'][0]['matchPercent']}% cosine={r3['results'][0]['similarity']}")

    print(f"\n  {'ALL CHECKS PASSED' if not fails else 'FAILURES: ' + ', '.join(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
