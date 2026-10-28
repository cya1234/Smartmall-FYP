"""First real CatVTON run: sample person + sample garment + heuristic mask.

We deliberately avoid the repo's AutoMasker because it imports detectron2 (used by
DensePose), which is painful on Windows. Instead we build a soft elliptical
region-of-interest mask from the garment type. That is a genuine quality
trade-off -- a learned mask follows the body silhouette -- so this script prints
what it did so the result can be judged honestly.

Run:  .venv\\Scripts\\python.exe tools/test_catvton.py
"""
import os
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".cache", "hf"))
VENDOR = os.path.join(ROOT, "ai-service", "vendor", "CatVTON")
sys.path.insert(0, VENDOR)

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

BASE = os.path.join(ROOT, "data", "models", "sd15-inpainting-fp16")
SAMPLE = os.path.join(VENDOR, "resource", "demo", "example", "condition")
OUT_DIR = os.path.join(ROOT, ".cache", "tryon")

W, H = 768, 1024
STEPS = 30
GUIDANCE = 2.5

# Ellipse per garment type: (cx, cy, rx, ry) as fractions of the image.
# Calibrated against the repo's sample photos: the head occupies roughly the top
# quarter, so the upper-body region must start below the chin or the model has to
# invent a face inside the mask (it cannot, and leaves a grey blob).
REGIONS = {
    "upper": (0.50, 0.56, 0.27, 0.29),   # shoulders -> hips
    "lower": (0.50, 0.82, 0.24, 0.18),   # waist -> ankles
    "overall": (0.50, 0.60, 0.30, 0.38),
}


def heuristic_mask(cloth_type, size):
    """Soft elliptical region of interest, drawn at the *original* photo size.

    The pipeline asserts image.size == mask.size before it crops both, so the
    mask has to be built in the source image's coordinate space.
    """
    cx, cy, rx, ry = REGIONS.get(cloth_type, REGIONS["upper"])
    w, h = size
    box = ((cx - rx) * w, (cy - ry) * h, (cx + rx) * w, (cy + ry) * h)
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).ellipse(box, fill=255)
    return m.filter(ImageFilter.GaussianBlur(9))


def main():
    import torch
    from model.pipeline import CatVTONPipeline

    if not os.path.exists(BASE):
        print("  base model missing - run tools/prepare_catvton_base.py first")
        return 1

    print("  loading CatVTON (MaskFree / mix-48k-1024) ...", flush=True)
    t0 = time.time()
    pipe = CatVTONPipeline(
        base_ckpt=BASE,
        attn_ckpt="zhengchong/CatVTON-MaskFree",
        attn_ckpt_version="mix",
        weight_dtype=torch.float16,
        device="cuda",
        skip_safety_check=True,
        use_tf32=True,
    )
    print(f"  loaded in {time.time()-t0:.1f}s", flush=True)
    if torch.cuda.is_available():
        print(f"  vram after load: {torch.cuda.memory_allocated()/2**30:.2f} GiB", flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)

    person_path = os.path.join(SAMPLE, "person", "baumu30483223c3_1719437121402_2-0._QL90_UX564_V12524t6_.jpg")
    # Default to a catalogue garment. Using the repo's own sample garment is
    # useless as a test: the sample person already wears that exact piece, so a
    # correct-looking output proves nothing about transfer.
    garment_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, "public", "assets", "products", "p004.jpg")
    out_name = sys.argv[2] if len(sys.argv) > 2 else "catvton-upper.png"
    for p in (person_path, garment_path):
        if not os.path.exists(p):
            print(f"  missing: {p}")
            return 1

    person = Image.open(person_path).convert("RGB")
    garment = Image.open(garment_path).convert("RGB")
    mask = heuristic_mask("upper", person.size)
    print(f"  person {person.size}  garment {garment.size}  mask {mask.size} (heuristic ellipse)", flush=True)

    t0 = time.time()
    result = pipe(
        image=person,
        condition_image=garment,
        mask=mask,
        num_inference_steps=STEPS,
        guidance_scale=GUIDANCE,
        height=H,
        width=W,
        generator=torch.Generator(device="cuda").manual_seed(42),
    )
    took = time.time() - t0
    img = result[0] if isinstance(result, (tuple, list)) else result
    out = os.path.join(OUT_DIR, out_name)
    img.save(out)
    print(f"  generated in {took:.1f}s -> {out}  ({img.size[0]}x{img.size[1]})", flush=True)
    if torch.cuda.is_available():
        print(f"  peak vram: {torch.cuda.max_memory_allocated()/2**30:.2f} GiB", flush=True)

    person.save(os.path.join(OUT_DIR, "input-person.png"))
    garment.save(os.path.join(OUT_DIR, "input-garment.png"))
    mask.convert("RGB").save(os.path.join(OUT_DIR, "input-mask.png"))
    print("  side-by-side inputs saved next to the output")
    return 0


if __name__ == "__main__":
    sys.exit(main())
