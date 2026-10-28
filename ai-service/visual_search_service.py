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

    device = "cuda" if torch.cuda.is_available() else "cpu"
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

    _state.update({
        "ready": True, "torch": torch, "np": np, "model": model, "preprocess": preprocess,
        "tokenizer": tokenizer, "index": index, "meta": meta, "device": device,
        "dim": index.d,
    })
    print(f"  model   {MODEL} / {PRETRAINED}", flush=True)
    print(f"  device  {device}" + (f" ({torch.cuda.get_device_name(0)})" if device == "cuda" else ""), flush=True)
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
                "gpu": _state["torch"].cuda.get_device_name(0) if _state["device"] == "cuda" else None,
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
