"""Mask-free CatVTON: person + garment, no region mask at all.

The GitHub repo's CatVTONPipeline needs an agnostic mask, which normally comes
from DensePose + SCHP (detectron2). The MaskFree weights instead pair with
`CatVTONPix2PixPipeline`, which concatenates the person and garment latents
horizontally and needs no mask -- so we can skip detectron2 entirely.

That pipeline lives in the Hugging Face Space source (fetched by
tools/fetch_catvton_space.py), not in the GitHub repo.

Run:  .venv\\Scripts\\python.exe tools\\test_catvton_p2p.py [garment.jpg] [out.png]
"""
import os
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".cache", "hf"))

SPACE = os.path.join(ROOT, "ai-service", "vendor", "catvton_space")
REPO = os.path.join(ROOT, "ai-service", "vendor", "CatVTON")
sys.path.insert(0, SPACE)

from PIL import Image  # noqa: E402

BASE = os.path.join(ROOT, "data", "models", "instruct-pix2pix-fp16")
OUT = os.path.join(ROOT, ".cache", "tryon")
W, H = 768, 1024

PERSON = os.path.join(REPO, "resource", "demo", "example", "condition", "person",
                      "baumu30483223c3_1719437121402_2-0._QL90_UX564_V12524t6_.jpg")


def main():
    import torch
    from model.pipeline import CatVTONPix2PixPipeline

    garment_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, "public", "assets", "products", "p004.jpg")
    out_name = sys.argv[2] if len(sys.argv) > 2 else "p2p.png"
    steps = int(os.environ.get("STEPS", 30))

    for p in (PERSON, garment_path, BASE):
        if not os.path.exists(p):
            print(f"  missing: {p}")
            return 1

    print("  loading CatVTONPix2Pix (MaskFree / mix-48k-1024) ...", flush=True)
    t0 = time.time()
    pipe = CatVTONPix2PixPipeline(
        base_ckpt=BASE,
        attn_ckpt="zhengchong/CatVTON-MaskFree",
        attn_ckpt_version="mix-48k-1024",
        weight_dtype=torch.float16,
        device="cuda",
        skip_safety_check=True,
        use_tf32=True,
    )
    print(f"  loaded in {time.time()-t0:.1f}s", flush=True)

    person = Image.open(PERSON).convert("RGB")
    garment = Image.open(garment_path).convert("RGB")
    print(f"  person {person.size}  garment {garment.size}  steps {steps}", flush=True)

    t0 = time.time()
    img = pipe(
        image=person,
        condition_image=garment,
        num_inference_steps=steps,
        guidance_scale=2.5,
        height=H,
        width=W,
        generator=torch.Generator(device="cuda").manual_seed(42),
    )[0]
    took = time.time() - t0

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, out_name)
    img.save(path)
    print(f"  generated in {took:.1f}s -> {path}", flush=True)
    if torch.cuda.is_available():
        print(f"  peak vram {torch.cuda.max_memory_allocated()/2**30:.2f} GiB", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
