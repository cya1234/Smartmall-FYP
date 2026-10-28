"""End-to-end test for CatVTON virtual try-on.

Checks the degradation ladder as well as the happy path:
  service online -> needs-photo (no upload) -> real synthesis (with upload)
"""
import base64
import json
import os
import sys
import urllib.request

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
SAMPLE_PERSON = os.path.join(
    ROOT, "ai-service", "vendor", "CatVTON", "resource", "demo", "example",
    "condition", "person", "baumu30483223c3_1719437121402_2-0._QL90_UX564_V12524t6_.jpg")
fails = []


def call(path, payload=None, timeout=300):
    if payload is None:
        req = urllib.request.Request(BASE + path)
    else:
        req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8", "ignore") or "{}")


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name:44s} {detail}")
    if not cond:
        fails.append(name)


print("== service ==")
code, st = call("/api/tryon/status", timeout=30)
online = st.get("online") is True
check("try-on status reachable", code == 200, f"online={online}")
if online:
    check("engine is catvton", st.get("engine") == "catvton-maskfree", st.get("engine"))
    check("mask-free weights", st.get("attn") == "mix-48k-1024", st.get("attn"))
    check("resolution reported", st.get("resolution") == "768x1024", st.get("resolution"))
    check("runs on GPU", st.get("device") == "cuda", st.get("gpu"))

print("\n== degradation ladder ==")
code, r = call("/api/tryon", {"productId": "p004"}, timeout=60)
check("no photo -> needs-photo" if online else "offline -> unavailable",
      r.get("status") == ("needs-photo" if online else "unavailable"), r.get("status"))
check("always returns product metadata", bool(r.get("product", {}).get("id")), r.get("product", {}).get("id"))

code, r = call("/api/tryon", {"productId": "nope"}, timeout=30)
check("unknown product -> 404", code == 404, f"HTTP {code}")

print("\n== real synthesis ==")
if not os.path.exists(SAMPLE_PERSON):
    print("  SKIP  sample person photo not present")
elif not online:
    print("  SKIP  service offline")
else:
    photo = "data:image/jpeg;base64," + base64.b64encode(open(SAMPLE_PERSON, "rb").read()).decode()
    code, r = call("/api/tryon", {"productId": "p004", "photo": photo, "steps": 20})
    check("returns 200", code == 200, f"HTTP {code}")
    check("status synthesized", r.get("status") == "synthesized", r.get("status"))
    check("engine catvton", r.get("engine") == "catvton", r.get("engine"))
    img = r.get("image", "")
    check("image is a png data url", img.startswith("data:image/png;base64,"), img[:30])
    raw = base64.b64decode(img.split(",", 1)[1]) if img.startswith("data:") else b""
    check("png magic bytes", raw[:8] == b"\x89PNG\r\n\x1a\n", f"{len(raw)//1024} KB")
    check("correct dimensions", (r.get("width"), r.get("height")) == (768, 1024),
          f"{r.get('width')}x{r.get('height')}")
    check("reports elapsed time", isinstance(r.get("tookMs"), int) and r["tookMs"] > 0,
          f"{r.get('tookMs')} ms")
    out = os.path.join(ROOT, ".cache", "tryon", "e2e-out.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "wb").write(raw)
    print(f"       saved {out}")

print()
print("ALL CHECKS PASSED" if not fails else f"FAILURES: {', '.join(fails)}")
sys.exit(1 if fails else 0)
