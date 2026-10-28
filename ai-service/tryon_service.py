"""SmartMall virtual try-on service (CatVTON, mask-free variant).

Pair:  CatVTONPix2PixPipeline (from the official HF Space source)
     + zhengchong/CatVTON-MaskFree attention weights ("mix-48k-1024")
     + timbrooks/instruct-pix2pix as the 8-channel base.

Why this pairing: the GitHub repo's CatVTONPipeline needs an agnostic mask that
normally comes from DensePose + SCHP, i.e. detectron2, which is a poor fit on
Windows. The MaskFree checkpoints instead pair with the pix2pix pipeline, which
simply concatenates the person and garment latents and needs no mask at all.

Measured on an RTX 4070 (12 GB): ~30 s for 30 steps at 768x1024, peak 3.6 GiB.

Endpoints
    GET  /health
    POST /tryon   {person: <base64 or dataURL>, garment: <base64 or dataURL>,
                   steps?: int, seed?: int}
                  -> {image: "data:image/png;base64,...", width, height, tookMs}

Run:  .venv\\Scripts\\python.exe ai-service/tryon_service.py --port 8003
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

SPACE = os.path.join(ROOT, "ai-service", "vendor", "catvton_space")
sys.path.insert(0, SPACE)

BASE_CKPT = os.environ.get(
    "TRYON_BASE", os.path.join(ROOT, "data", "models", "instruct-pix2pix-fp16"))
ATTN_CKPT = os.environ.get("TRYON_ATTN", "zhengchong/CatVTON-MaskFree")
ATTN_VERSION = os.environ.get("TRYON_ATTN_VERSION", "mix-48k-1024")
WIDTH = int(os.environ.get("TRYON_WIDTH", 768))
HEIGHT = int(os.environ.get("TRYON_HEIGHT", 1024))
DEFAULT_STEPS = int(os.environ.get("TRYON_STEPS", 30))
MAX_BODY = 16 * 1024 * 1024

_state = {"ready": False, "error": None, "pipe": None, "torch": None}
_lock = threading.Lock()


def load():
    import torch
    from model.pipeline import CatVTONPix2PixPipeline

    if not os.path.exists(BASE_CKPT):
        raise FileNotFoundError(
            f"{BASE_CKPT} missing - run tools/prepare_catvton_base.py first")

    t0 = time.time()
    pipe = CatVTONPix2PixPipeline(
        base_ckpt=BASE_CKPT,
        attn_ckpt=ATTN_CKPT,
        attn_ckpt_version=ATTN_VERSION,
        weight_dtype=torch.float16,
        device="cuda",
        skip_safety_check=True,
        use_tf32=True,
    )
    _state.update(pipe=pipe, torch=torch, ready=True)
    vram = torch.cuda.memory_allocated() / 2**30 if torch.cuda.is_available() else 0
    print(f"  model    CatVTON MaskFree / {ATTN_VERSION}", flush=True)
    print(f"  loaded   {time.time()-t0:.1f}s   vram {vram:.2f} GiB", flush=True)


def _decode(value):
    """Accept a data URL or bare base64 and return a PIL image."""
    from PIL import Image
    if not value:
        raise ValueError("missing image")
    if value.startswith("data:"):
        _, _, value = value.partition(",")
    raw = base64.b64decode(value, validate=False)
    img = Image.open(io.BytesIO(raw))
    return img.convert("RGB")


def fit_to_target(img, tw=WIDTH, th=HEIGHT):
    """Pad the photo to the model's aspect ratio instead of cropping it.

    CatVTON's pipeline calls resize_and_crop(), which centre-crops to 3:4. A
    portrait phone photo is taller than that, so cropping removes the same number
    of pixels from the top and the bottom -- and the top of a portrait is the
    head. We therefore pad to 3:4 ourselves first, so the pipeline's crop becomes
    a no-op and the whole person survives. The padding is a blurred, cover-scaled
    copy of the photo, which reads as an intentional backdrop rather than a band
    of flat colour.
    """
    from PIL import ImageFilter
    target = tw / th
    w, h = img.size
    if abs(w / h - target) < 0.005:
        return img

    if w / h < target:                      # too tall -> pad the sides
        new_w, new_h = int(round(h * target)), h
    else:                                   # too wide -> pad top and bottom
        new_w, new_h = w, int(round(w / target))

    scale = max(new_w / w, new_h / h)
    backdrop = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    bx = (backdrop.width - new_w) // 2
    by = (backdrop.height - new_h) // 2
    backdrop = backdrop.crop((bx, by, bx + new_w, by + new_h))
    backdrop = backdrop.filter(ImageFilter.GaussianBlur(28))

    backdrop.paste(img, ((new_w - w) // 2, (new_h - h) // 2))
    return backdrop


def _encode(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def tryon(person, garment, steps=DEFAULT_STEPS, seed=42):
    torch = _state["torch"]
    pipe = _state["pipe"]
    steps = max(10, min(60, int(steps)))

    # Pad rather than crop, so the shopper's head is never cut off.
    person = fit_to_target(person, WIDTH, HEIGHT)

    with _lock:                     # one GPU job at a time
        t0 = time.time()
        out = pipe(
            image=person,
            condition_image=garment,
            num_inference_steps=steps,
            guidance_scale=2.5,
            height=HEIGHT,
            width=WIDTH,
            generator=torch.Generator(device="cuda").manual_seed(int(seed)),
        )[0]
        took = time.time() - t0
    return out, took


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.rstrip("/") == "/health":
            torch = _state.get("torch")
            gpu = None
            vram = None
            if torch is not None and torch.cuda.is_available():
                gpu = torch.cuda.get_device_name(0)
                vram = round(torch.cuda.memory_allocated() / 2**30, 2)
            return self._send(200, {
                "ok": _state["ready"],
                "engine": "catvton-maskfree",
                "attn": ATTN_VERSION,
                "base": os.path.basename(BASE_CKPT),
                "resolution": f"{WIDTH}x{HEIGHT}",
                "defaultSteps": DEFAULT_STEPS,
                "device": "cuda",
                "gpu": gpu,
                "vramGiB": vram,
                "error": _state.get("error"),
            })
        self._send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        if path.rstrip("/") != "/tryon":
            return self._send(404, {"error": "not found"})
        if not _state["ready"]:
            return self._send(503, {"ok": False, "error": _state.get("error") or "loading"})

        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY:
                return self._send(413, {"error": f"body must be 1..{MAX_BODY} bytes"})
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            person = _decode(body.get("person"))
            garment = _decode(body.get("garment"))
            if person.size[0] < 64 or person.size[1] < 64:
                return self._send(400, {"error": "person image too small"})

            img, took = tryon(person, garment, body.get("steps", DEFAULT_STEPS), body.get("seed", 42))
            return self._send(200, {
                "ok": True,
                "engine": "catvton-maskfree",
                "width": img.size[0],
                "height": img.size[1],
                "steps": int(body.get("steps", DEFAULT_STEPS)),
                "tookMs": int(took * 1000),
                "image": _encode(img),
            })
        except Exception as e:
            traceback.print_exc()
            return self._send(400, {"ok": False, "error": str(e)[:200]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("TRYON_PORT", 8003)))
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    print("  loading CatVTON ...", flush=True)
    try:
        load()
    except Exception as e:
        _state["error"] = str(e)
        print(f"  FAILED: {e}", flush=True)
        return 1
    print(f"  ready - listening on http://{args.host}:{args.port}\n", flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
