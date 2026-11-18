"""SmartMall visual-search inference service (CLIP + FAISS).

A small stdlib-only HTTP service that holds the CLIP model and the FAISS index
in memory and answers search requests. It is deliberately a separate process
from the Node web server: the FYP proposal's architecture decouples ordinary web
operations from high-dimensional AI inference, so the web tier can keep serving
even when this service is down (lib/visualSearch.js falls back to the colour
heuristic).

Endpoints
    GET  /health          -> service + index status
    POST /search          -> {"text": str, "image": b64, "k": int}
                             returns ranked product ids with cosine scores
    POST /embed           -> {"text"|"image": ...} -> raw unit vector

Query fusion follows the proposal's "unified query embedding": when both an
image and a text modifier are supplied, the two unit vectors are combined with
a weight before the FAISS lookup.

Run:  .venv\\Scripts\\python.exe ai-service/visual_search_service.py --port 8001
"""
import argparse
import base64
import io
import json
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".cache", "hf"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

INDEX_PATH = os.path.join(ROOT, "data", "clip-index.faiss")
META_PATH = os.path.join(ROOT, "data", "clip-index-meta.json")
MODEL = os.environ.get("CLIP_MODEL", "hf-hub:Marqo/marqo-fashionSigLIP")
# hf-hub checkpoints ship their own config, so a pretrained tag must not be passed.
_raw_pretrained = os.environ.get("CLIP_PRETRAINED", "").strip()
PRETRAINED = None if (MODEL.startswith("hf-hub:") or _raw_pretrained.lower() in ("", "none")) else _raw_pretrained

MAX_BODY = 12 * 1024 * 1024  # 12 MB
TEXT_WEIGHT = 0.55           # weight of the text modifier when fusing

_state = {"ready": False, "error": None}
_lock = threading.Lock()


def load():
    import numpy as np
    import torch
    import open_clip
    import faiss

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from device_util import pick_device, device_name, memory_gb, enable_mps_fallback
    enable_mps_fallback()

    device = pick_device(torch)
    model, _, preprocess = open_clip.create_model_and_transforms(MODEL, pretrained=PRETRAINED, device=device)
    model.eval()
    tokenizer = open_clip.get_tokenizer(MODEL)

    if not os.path.exists(INDEX_PATH):
        raise FileNotFoundError(f"index not found at {INDEX_PATH} - run tools/build_clip_index.py")

    index = faiss.read_index(INDEX_PATH)
    with open(META_PATH, encoding="utf-8") as fh:
        meta = json.load(fh)

    # Warm up so the first user request is not slowed by kernel compilation.
    with torch.no_grad():
        model.encode_image(torch.zeros(1, 3, 224, 224, device=device))
        model.encode_text(tokenizer(["warmup"]).to(device))
    if device == "cuda":
        torch.cuda.synchronize()
    elif device == "mps":
        torch.mps.synchronize()

    _state.update({
        "ready": True, "torch": torch, "np": np, "model": model, "preprocess": preprocess,
        "tokenizer": tokenizer, "index": index, "meta": meta, "device": device,
        "dim": index.d,
    })
    print(f"  model   {MODEL} / {PRETRAINED}", flush=True)
    print(f"  device  {device} ({device_name(torch, device) or 'n/a'})", flush=True)
    print(f"  index   {index.ntotal} vectors, dim {index.d}, built {meta.get('builtAt')}", flush=True)


GLOSSARY_PATH = os.path.join(ROOT, "data", "fashion-glossary.json")
_glossary = None


def _glossary_pairs():
    """Traditional-Chinese -> English fashion vocabulary, longest term first."""
    global _glossary
    if _glossary is None:
        try:
            with open(GLOSSARY_PATH, encoding="utf-8") as fh:
                doc = json.load(fh)
            flat = {}
            for group in doc.values():
                if isinstance(group, dict):
                    flat.update(group)
            _glossary = sorted(flat.items(), key=lambda kv: -len(kv[0]))
        except Exception as e:
            print(f"  glossary unavailable ({e}) - queries will not be translated", flush=True)
            _glossary = []
    return _glossary


def translate_query(text):
    """Normalise a Chinese query into the English fashion vocabulary the
    encoders are aligned to.

    This is the single highest-impact change in the whole retrieval path: the
    fashion-tuned encoders are trained on English catalogue metadata, so raw
    Chinese input lands almost orthogonally to the image space. Measured on the
    94-query bilingual set (data/eval/results.json), Chinese Recall@5 goes
    17.0% -> 95.7% for Marqo-FashionSigLIP and 70.2% -> 93.6% for the previous
    laion ViT-B-32 backbone.
    """
    pairs = _glossary_pairs()
    if not pairs:
        return text
    out, i = [], 0
    while i < len(text):
        for zh, en in pairs:
            if text.startswith(zh, i):
                out.append(" " + en + " ")
                i += len(zh)
                break
        else:
            out.append(text[i])
            i += 1
    translated = " ".join("".join(out).split())
    return translated or text


def encode_text(text):
    torch = _state["torch"]
    text = translate_query(text)
    with torch.no_grad():
        tok = _state["tokenizer"]([text]).to(_state["device"])
        f = _state["model"].encode_text(tok)
        f = f / f.norm(dim=-1, keepdim=True)
    return f[0].cpu().numpy().astype("float32")


def encode_image(b64):
    from PIL import Image
    torch = _state["torch"]
    raw = base64.b64decode(b64.split(",")[-1])
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    with torch.no_grad():
        x = _state["preprocess"](im).unsqueeze(0).to(_state["device"])
        f = _state["model"].encode_image(x)
        f = f / f.norm(dim=-1, keepdim=True)
    return f[0].cpu().numpy().astype("float32"), im.size


def search(text=None, image=None, k=12, text_weight=TEXT_WEIGHT):
    np = _state["np"]
    faiss = __import__("faiss")
    parts = []
    mode = []
    img_size = None

    if image:
        v, img_size = encode_image(image)
        parts.append(("image", v))
        mode.append("image")
    if text:
        parts.append(("text", encode_text(text)))
        mode.append("text")

    if not parts:
        return {"error": "provide text and/or image"}

    if len(parts) == 1:
        q = parts[0][1]
    else:
        # Unified query embedding: weighted fusion of the two unit vectors.
        img = next(v for n, v in parts if n == "image")
        txt = next(v for n, v in parts if n == "text")
        w = float(text_weight)
        q = img * (1.0 - w) + txt * w
        n = np.linalg.norm(q)
        if n > 0:
            q = q / n

    q = q.reshape(1, -1).astype("float32")
    faiss.normalize_L2(q)
    scores, idx = _state["index"].search(q, min(k, _state["index"].ntotal))

    entries = _state["meta"]["entries"]
    results = []
    for s, i in zip(scores[0], idx[0]):
        if i < 0:
            continue
        e = entries[i]
        results.append({
            "id": e["id"], "position": int(i),
            "score": round(float(s), 4),
            "name": e["name"], "image": e["image"],
        })
    return {
        "mode": "+".join(mode),
        "fusion": "weighted-average" if len(parts) > 1 else "single-tower",
        "textWeight": text_weight if len(parts) > 1 else None,
        "imageSize": list(img_size) if img_size else None,
        "results": results,
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # keep stdout for meaningful events only

    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            if not _state["ready"]:
                return self._send(503, {"ok": False, "error": _state.get("error")})
            m = _state["meta"]
            return self._send(200, {
                "ok": True,
                "model": MODEL,
                "pretrained": PRETRAINED,
                "device": _state["device"],
                "gpu": (_state["torch"] is not None and _state.get("device") in ("cuda", "mps")
                        and __import__("device_util").device_name(_state["torch"], _state["device"])) or None,
                "indexed": _state["index"].ntotal,
                "dim": _state["dim"],
                "builtAt": m.get("builtAt"),
                "notIndexed": len(m.get("notIndexed", [])),
            })
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not _state["ready"]:
            return self._send(503, {"ok": False, "error": _state.get("error")})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self._send(413, {"error": "payload too large"})
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw or b"{}")

            if self.path.startswith("/search"):
                with _lock:
                    t = time.time()
                    out = search(
                        text=(body.get("text") or "").strip() or None,
                        image=body.get("image") or None,
                        k=int(body.get("k") or 12),
                        text_weight=float(body.get("textWeight") or TEXT_WEIGHT),
                    )
                    out["tookMs"] = round((time.time() - t) * 1000, 1)
                return self._send(200, out)

            if self.path.startswith("/aesthetic"):
                with _lock:
                    t = time.time()
                    out = aesthetic(body.get("image") or "", body.get("wardrobeIds") or [])
                    out["tookMs"] = round((time.time() - t) * 1000, 1)
                return self._send(200, out)

            if self.path.startswith("/embed"):
                np = _state["np"]
                if body.get("image"):
                    with _lock:
                        v, _ = encode_image(body["image"])
                    return self._send(200, {"vector": [round(float(x), 6) for x in v[:16]], "dim": int(v.shape[0])})
                with _lock:
                    v = encode_text(body.get("text") or "test")
                return self._send(200, {"vector": [round(float(x), 6) for x in v[:16]], "dim": int(v.shape[0])})

            self._send(404, {"error": "not found"})
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": str(e)})


# ------------------------------------------------------------ aesthetic score --
# "Does this outfit suit you?" is a two-part question: does it match the shopper's
# usual style, and is it a well-formed look. The style half is measured against the
# wardrobe's own CLIP centroid — the same embedding space the visual search uses, so
# the score is grounded in the shopper's actual purchases rather than a generic
# taste model. The composition half is measured with colour statistics and category
# anchors.
#
# This is deliberately NOT an LLM judge. StyleTailor (AAAI 2026) shows what a
# VLM-Artist judge adds, but a 7B vision model does not fit on the same 12 GB card
# as CatVTON, and an unvalidated LLM score is a vibe rather than a benchmark. The
# four sub-scores below are reproducible and cheap; /aesthetic/vlm is the plug point
# for a judge backend when one is available.
CATEGORY_PROMPTS = {
    "top": ["a shirt", "a t-shirt", "a sweater", "a blouse", "a knit top"],
    "bottom": ["trousers", "jeans", "a skirt", "shorts"],
    "shoes": ["shoes", "sneakers", "boots", "loafers"],
    "outerwear": ["a coat", "a jacket", "a blazer"],
    "accessory": ["a bag", "sunglasses", "a hat", "a scarf"],
}
CATEGORY_THRESHOLD = 0.03   # SigLIP 768-d image/text cosines live around -0.02..0.08

# Image/image cosines for garments sit far higher than the text pair — related items
# land around 0.6-0.8. The mapping below is calibrated on that band so a wardrobe
# staple scores in the high 80s rather than pinning at 100.
STYLE_LO, STYLE_HI = 0.40, 0.85


def _category_hits(vec):
    """Which garment categories this photo looks like, via text anchors."""
    np = _state["np"]
    present = {}
    for cat, prompts in CATEGORY_PROMPTS.items():
        best = 0.0
        for p in prompts:
            t = encode_text(p)
            best = max(best, float(np.dot(vec, t)))
        present[cat] = round(best, 4)
    hits = [c for c, v in present.items() if v >= CATEGORY_THRESHOLD]
    return hits, present


def _palette(b64):
    """Dominant colours, their hue centres, and the neutral share."""
    import colorsys
    from PIL import Image
    raw = base64.b64decode(b64.split(",")[-1])
    im = Image.open(io.BytesIO(raw)).convert("RGB").resize((96, 96))
    q = im.quantize(colors=8, method=Image.Quantize.MEDIANCUT).convert("RGB")
    cols = sorted(q.getcolors(96 * 96) or [], reverse=True)
    total = sum(c for c, _ in cols) or 1

    hues, neutral, top = [], 0.0, []
    for cnt, rgb in cols:
        share = cnt / total
        r, g, b = rgb
        top.append({"hex": "#%02x%02x%02x" % (r, g, b), "share": round(share, 3)})
        if share < 0.05:
            continue
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        # Neutral = low saturation or near-black. The old test also treated V > 0.95
        # as neutral, which swallowed every fully bright colour: a neon pink has
        # max(r,g,b) = 255, so V = 1.0, so it was counted as "neutral" and its hue
        # never reached the palette at all. White has low saturation, so S alone is
        # enough to catch it.
        if s < 0.18 or v < 0.12:
            neutral += share
        else:
            hues.append(h * 360)

    clusters = []
    for h in sorted(hues):
        if clusters and h - clusters[-1][-1] <= 30:
            clusters[-1].append(h)
        else:
            clusters.append([h])
    if len(clusters) > 1 and (360 - clusters[-1][-1] + clusters[0][0]) <= 30:
        clusters = clusters[:-1] + [clusters[0] + clusters[-1]]

    # Circular mean, not arithmetic: hues straddling red average out to the wrong
    # side of the wheel. 330 and 0 average to 165 arithmetically (the opposite hue)
    # and to 345 circularly, which is the whole difference between "a neon family"
    # and "scattered".
    import math
    centres = []
    for c in clusters:
        sv = sum(math.sin(math.radians(h)) for h in c)
        cv = sum(math.cos(math.radians(h)) for h in c)
        centres.append(round(math.degrees(math.atan2(sv, cv)) % 360, 1))
    return {
        "distinctHues": len(clusters),
        "hueCentres": centres,
        "neutralShare": round(neutral, 3),
        "colours": top[:5],
    }


def _palette_coherence(pal):
    """Does the palette read as a deliberate scheme, whatever the taste?

    The old rule was `more than 3 hues -> penalty, under 12 % neutral -> penalty`.
    That is not a measure of quality, it is a measure of minimalism: it marks down
    maximalist styles (shamazhite, heavy metal, harajuku) by construction, which is a
    bias, not an aesthetic judgement. This version scores STRUCTURE instead:

        all hues inside a 90 degree arc   -> analogous, coherent
        two clusters about opposite       -> complementary, coherent
        many hues with no structure       -> scattered, penalised

    A neon outfit built on one colour family now scores the same as a beige one; a
    genuinely random mix of six unrelated hues still scores low, for everyone.
    """
    centres = sorted(pal.get("hueCentres") or [])
    n = len(centres)
    if n == 0:
        return 100.0, "neutral"
    if n == 1:
        return 100.0, "monochrome"
    if n == 2:
        # Two colours is never chaos: black + red (heavy metal) and navy + grey are
        # both deliberate. Penalising a two-tone look would be exactly the bias this
        # change exists to remove.
        gaps2 = [centres[1] - centres[0], 360 - centres[1] + centres[0]]
        arc2 = 360 - max(gaps2)
        return 95.0, ("complementary" if 150 <= arc2 <= 210 else "two-tone")

    gaps = [centres[i + 1] - centres[i] for i in range(n - 1)]
    gaps.append(360 - centres[-1] + centres[0])
    arc = 360 - max(gaps)                      # narrowest arc holding every hue

    if arc <= 60:
        return 100.0, "analogous"
    if arc <= 90:
        return 94.0, "analogous-wide"
    # Three or more clusters spread wide: no discernible scheme.
    penalty = (arc - 90) * 0.55 + (n - 2) * 6
    return max(20.0, 92.0 - penalty), "scattered"


def aesthetic(b64, wardrobe_ids=None):
    np = _state["np"]
    vec, size = encode_image(b64)

    # ---- style match: cosine to the wardrobe centroid --------------------
    wardrobe_ids = [str(x) for x in (wardrobe_ids or [])]
    entries = _state["meta"]["entries"]
    row_of = {}
    for i, e in enumerate(entries):
        row_of[str(e.get("id"))] = i

    cents = []
    for pid in wardrobe_ids:
        r = row_of.get(pid)
        if r is None:
            continue
        try:
            v = np.asarray(_state["index"].reconstruct(r), dtype="float32")
        except Exception:
            continue
        n = np.linalg.norm(v)
        if n > 0:
            cents.append(v / n)

    if cents:
        centroid = np.mean(cents, axis=0)
        centroid = centroid / (np.linalg.norm(centroid) or 1.0)
        sim = float(np.dot(vec, centroid))
        style = max(0.0, min(100.0, (sim - STYLE_LO) / (STYLE_HI - STYLE_LO) * 100.0))
        per_item = sorted(
            ((float(np.dot(vec, c)), pid) for c, pid in zip(cents, [p for p in wardrobe_ids if p in row_of])),
            reverse=True,
        )[:3]
    else:
        sim, style, per_item = None, 0.0, []

    # ---- composition: what counts as complete *for this shopper* ---------
    # The three-slot rule (top + bottom + shoes) is a Western default. Learn which
    # slots this shopper actually wears from their own wardrobe instead: someone who
    # never buys shoes should not be marked down for wearing none. A dress satisfies
    # both top and bottom, because requiring a separate top would penalise one-piece
    # garments. Outerwear is never required — a summer outfit has none.
    hits, anchor_scores = _category_hits(vec)
    SUBCAT_GROUP = {
        "top": {"shirt", "t-shirt", "sweater", "blouse", "knit", "hoodie", "dress"},
        "bottom": {"trousers", "jeans", "skirt", "shorts"},
        "shoes": {"shoes", "sneakers", "boots", "loafers", "sandals", "slippers"},
        "outerwear": {"jacket", "coat", "blazer", "puffer", "fleece"},
        "dress": {"dress"},
    }
    owned_groups = set()
    for pid in wardrobe_ids:
        r = row_of.get(pid)
        if r is None:
            continue
        sub = str(entries[r].get("subcategory") or "").lower()
        for group, words in SUBCAT_GROUP.items():
            if any(w in sub for w in words):
                owned_groups.add(group)
                break

    required = [g for g in ("top", "bottom", "shoes") if g in owned_groups]
    if not required:
        required = ["top", "bottom", "shoes"]      # no usable wardrobe history
    # A dress covers a full look on its own.
    has_dress = "dress" in hits
    satisfied = sum(
        1 for g in required
        if g in hits or (has_dress and g in ("top", "bottom"))
    )
    coverage = satisfied / len(required) * 100
    if "outerwear" in hits:
        coverage = min(100.0, coverage + 10)

    # ---- palette: structure, not restraint ------------------------------
    pal = _palette(b64)
    palette, scheme = _palette_coherence(pal)

    # Palette carries the least weight of the three on purpose: style match is
    # measured against the shopper's own wardrobe (so it is personal), coverage is
    # their own definition of a complete look, but "do these colours work" retains a
    # value judgement no matter how it is worded. Keeping it at 10 % limits how much
    # a maximalist palette can cost, without removing the signal entirely.
    overall = round(0.65 * style + 0.25 * coverage + 0.10 * palette)

    if overall >= 78:
        verdict = "excellent"
    elif overall >= 64:
        verdict = "good"
    elif overall >= 50:
        verdict = "fair"
    else:
        verdict = "adjust"

    return {
        "score": overall,
        "verdict": verdict,
        "subscores": {
            "style": round(style),
            "coverage": round(coverage),
            "palette": round(palette),
        },
        "detail": {
            "styleSimilarity": None if sim is None else round(sim, 4),
            "wardrobeUsed": len(cents),
            "closestOwned": [{"id": pid, "similarity": round(s, 4)} for s, pid in per_item],
            "categories": hits,
            "requiredCategories": required,
            "wardrobeGroups": sorted(owned_groups),
            "anchors": anchor_scores,
            "palette": {**pal, "scheme": scheme},
            "imageSize": list(size),
        },
        "weights": {"style": 0.65, "coverage": 0.25, "palette": 0.10},
        "judge": "deterministic-clip",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("VISUAL_SEARCH_PORT", 8001)))
    ap.add_argument("--host", default=os.environ.get("VISUAL_SEARCH_HOST", "127.0.0.1"))
    args = ap.parse_args()

    print("  loading CLIP + FAISS ...", flush=True)
    t = time.time()
    try:
        load()
    except Exception as e:
        _state["error"] = str(e)
        print(f"  FAILED to load: {e}", flush=True)
        traceback.print_exc()
        return 1

    print(f"  ready in {time.time()-t:.1f}s - listening on http://{args.host}:{args.port}\n", flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
