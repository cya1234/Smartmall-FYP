"""Build the CLIP embedding index for the SmartMall catalog.

Encodes every product photo with CLIP (image tower) and writes a FAISS
inner-product index plus a metadata sidecar. Text queries are encoded with the
matching CLIP text tower at query time, which is the standard CLIP zero-shot
retrieval setup.

Run:  .venv\\Scripts\\python.exe tools\\build_clip_index.py
"""
import json
import os
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".cache", "hf"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

PRODUCTS = os.path.join(ROOT, "data", "products.json")
PUBLIC = os.path.join(ROOT, "public")
DATA = os.path.join(ROOT, "data")
INDEX_PATH = os.path.join(DATA, "clip-index.faiss")
META_PATH = os.path.join(DATA, "clip-index-meta.json")

MODEL = os.environ.get("CLIP_MODEL", "hf-hub:Marqo/marqo-fashionSigLIP")
_raw_pretrained = os.environ.get("CLIP_PRETRAINED", "").strip()
PRETRAINED = None if (MODEL.startswith("hf-hub:") or _raw_pretrained.lower() in ("", "none")) else _raw_pretrained


def main():
    import numpy as np
    import torch
    import open_clip
    import faiss
    from PIL import Image

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  device {device}" + (f" ({torch.cuda.get_device_name(0)})" if device == "cuda" else ""))

    with open(PRODUCTS, encoding="utf-8") as fh:
        products = json.load(fh)

    # Only products that actually have a photo can be indexed visually.
    indexable = []
    for p in products:
        rel = p.get("image")
        if not rel:
            continue
        path = os.path.join(PUBLIC, rel.lstrip("/").replace("/", os.sep))
        if os.path.exists(path):
            indexable.append((p, path))
    print(f"  {len(indexable)} / {len(products)} products have a photo")

    print(f"  loading {MODEL} / {PRETRAINED} ...")
    t = time.time()
    model, _, preprocess = open_clip.create_model_and_transforms(MODEL, pretrained=PRETRAINED, device=device)
    model.eval()
    # hf-hub checkpoints wrap the vision tower in a TimmModel, which does not
    # expose output_dim -- probe the real embedding size instead.
    try:
        dim = model.visual.output_dim
    except AttributeError:
        with torch.no_grad():
            probe = preprocess(Image.new("RGB", (224, 224))).unsqueeze(0).to(device)
            dim = int(model.encode_image(probe).shape[-1])
    print(f"  loaded in {time.time() - t:.1f}s, embedding dim {dim}")

    # Warm up CUDA so the first real batch is not penalised by kernel compilation.
    with torch.no_grad():
        warm = torch.zeros(1, 3, 224, 224, device=device)
        model.encode_image(warm)
    if device == "cuda":
        torch.cuda.synchronize()

    t = time.time()
    vecs = []
    with torch.no_grad():
        for p, path in indexable:
            im = Image.open(path).convert("RGB")
            x = preprocess(im).unsqueeze(0).to(device)
            f = model.encode_image(x)
            f = f / f.norm(dim=-1, keepdim=True)
            vecs.append(f.squeeze(0).cpu().numpy().astype("float32"))
    if device == "cuda":
        torch.cuda.synchronize()
    elapsed = time.time() - t
    print(f"  encoded {len(vecs)} images in {elapsed:.2f}s ({elapsed/max(1,len(vecs))*1000:.0f} ms/image)")

    mat = np.vstack(vecs)
    faiss.normalize_L2(mat)
    index = faiss.IndexFlatIP(dim)
    index.add(mat)
    faiss.write_index(index, INDEX_PATH)
    print(f"  wrote {INDEX_PATH} ({index.ntotal} vectors)")

    meta = {
        "model": MODEL,
        "pretrained": PRETRAINED,
        "dim": dim,
        "device": device,
        "builtAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "count": len(indexable),
        "entries": [
            {
                "position": i,
                "id": p["id"],
                "name": p["name"],
                "name_zh": p.get("name_zh"),
                "image": p["image"],
                "category": p["category"],
                "subcategory": p["subcategory"],
                "colorName": p["colorName"],
                "material": p["material"],
                "emoji": p["emoji"],
            }
            for i, (p, _) in enumerate(indexable)
        ],
        "notIndexed": [
            {"id": p["id"], "name": p["name"], "reason": "no photo"}
            for p in products if not p.get("image")
        ],
    }
    with open(META_PATH, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    print(f"  wrote {META_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
