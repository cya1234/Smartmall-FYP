"""Evaluate the CLIP visual-search service with a set of text queries.

Prints the top matches per query so retrieval quality can be eyeballed, and
checks a few assertions where the correct answer is unambiguous.

Run:  .venv\\Scripts\\python.exe tools\\test_clip_search.py
"""
import json
import sys
import urllib.request

URL = "http://127.0.0.1:8001/search"

QUERIES = [
    ("a red dress", ["p003", "p002", "p001"]),
    ("white sneakers", ["p014"]),
    ("a blue ski jacket", ["p031", "p007", "p008"]),
    ("black sunglasses", ["p033", "p022"]),
    ("a leather handbag", ["p019", "p020"]),
    ("grey wool sweater", ["p006"]),
    ("beige trousers", ["p010", "p012"]),
    ("silver wristwatch", ["p021", "p030"]),
    ("winter hat", ["p036", "p018"]),
    ("striped shirt", ["p004", "p005"]),
]


def search(text, k=5):
    body = json.dumps({"text": text, "k": k}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def main():
    ok = 0
    for text, expect in QUERIES:
        try:
            r = search(text)
        except Exception as e:
            print(f"  {text!r}: FAILED {e}")
            continue
        hits = [x["id"] for x in r["results"]]
        top = f"{r['results'][0]['id']} ({r['results'][0]['score']:+.3f})"
        good = hits[0] in expect or any(h in expect for h in hits[:3])
        ok += 1 if good else 0
        print(f"  {'PASS' if good else 'MISS'}  {text:22s} -> {top:20s} top5={hits}  {r['tookMs']}ms")
    print(f"\n  {ok}/{len(QUERIES)} queries put an expected product in the top 3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
