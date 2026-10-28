"""Isolate why CatVTON leaves a flat grey patch: compare three masks on one pair.

If a fully-white mask also yields grey, the denoiser is not producing content at
all. If only the elliptical mask does, the mask geometry is the problem.
"""
import os
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".cache", "hf"))
VENDOR = os.path.join(ROOT, "ai-service", "vendor", "CatVTON")
sys.path.insert(0, VENDOR)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

BASE = os.path.join(ROOT, "data", "models", "sd15-inpainting-fp16")
OUT = os.path.join(ROOT, ".cache", "tryon")
W, H, STEPS, GUID = 768, 1024, 30, 2.5

PERSON = os.path.join(VENDOR, "resource", "demo", "example", "condition", "person",
                      "baumu30483223c3_1719437121402_2-0._QL90_UX564_V12524t6_.jpg")
GARMENT = os.path.join(ROOT, "public", "assets", "products", "p004.jpg")


def mask_white(size):
    return Image.new("L", size, 255)


def mask_square(size):
    w, h = size
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rectangle((0.40 * w, 0.30 * h, 0.60 * w, 0.50 * h), fill=255)
    return m


def mask_ellipse(size):
    w, h = size
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).ellipse((0.23 * w, 0.27 * h, 0.77 * w, 0.85 * h), fill=255)
    return m.filter(ImageFilter.GaussianBlur(9))


def main():
    import torch
    from model.pipeline import CatVTONPipeline

    person = Image.open(PERSON).convert("RGB")
    garment = Image.open(GARMENT).convert("RGB")

    print("  loading ...", flush=True)
    pipe = CatVTONPipeline(base_ckpt=BASE, attn_ckpt="zhengchong/CatVTON-MaskFree",
                           attn_ckpt_version="mix", weight_dtype=torch.float16,
                           device="cuda", skip_safety_check=True, use_tf32=True)
    os.makedirs(OUT, exist_ok=True)

    cases = [("white", mask_white), ("square", mask_square), ("ellipse", mask_ellipse)]
    for name, fn in cases:
        mask = fn(person.size)
        t0 = time.time()
        img = pipe(image=person, condition_image=garment, mask=mask,
                   num_inference_steps=STEPS, guidance_scale=GUID, height=H, width=W,
                   generator=torch.Generator(device="cuda").manual_seed(7))[0]
        path = os.path.join(OUT, f"diag-{name}.png")
        img.save(path)

        # How much of the output is flat grey inside the masked area?
        arr = np.asarray(img.convert("RGB")).astype(int)
        grey = np.all(np.abs(arr - arr.mean(axis=(0, 1))) < 6, axis=2)
        frac_grey = grey.mean() * 100
        print(f"  {name:8s} {time.time()-t0:5.1f}s  flat-grey {frac_grey:5.1f}%  -> {os.path.basename(path)}",
              flush=True)

    print("  done")


if __name__ == "__main__":
    sys.exit(main())
