"""Verify that CLIP + FAISS work on this machine's GPU.

Loads a CLIP model through open_clip, embeds one image and a few text prompts,
and reports cosine similarities plus timing. Also smoke-tests a FAISS index.

Run:  .venv\\Scripts\\python.exe tools\\check_clip.py
"""
import os
import sys
import time

# Keep every cache inside the workspace (the sandbox blocks writes elsewhere).
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".cache", "hf"))
os.environ.setdefault("TORCH_HOME", os.path.join(ROOT, ".cache", "torch"))

MODEL = os.environ.get("CLIP_MODEL", "ViT-B-32")
PRETRAINED = os.environ.get("CLIP_PRETRAINED", "laion2b_s34b_b79k")


def main():
    t0 = time.time()
    import torch
    print(f"  torch          {torch.__version__}  cuda={torch.cuda.is_available()}")
    if not torch.cuda.is_available():
        print("  !! CUDA not available - visual search would be very slow")
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    if dev == "cuda":
        print(f"  device         {torch.cuda.get_device_name(0)}")

    import open_clip
    import faiss
    from PIL import Image
    print(f"  open_clip      {getattr(open_clip, '__version__', '?')}")
    print(f"  faiss          {faiss.__version__}  gpus={faiss.get_num_gpus()}")

    print(f"\n  loading {MODEL} / {PRETRAINED} (first run downloads weights) ...")
    t = time.time()
    model, _, preprocess = open_clip.create_model_and_transforms(MODEL, pretrained=PRETRAINED, device=dev)
    tokenizer = open_clip.get_tokenizer(MODEL)
    model.eval()
    print(f"  loaded in {time.time() - t:.1f}s  ({time.time() - t0:.1f}s total)")

    # A synthetic "red garment" image is enough to prove the pipeline runs.
    img = Image.new("RGB", (224, 224), (190, 40, 45))
    with torch.no_grad():
        x = preprocess(img).unsqueeze(0).to(dev)
        t = time.time()
        img_feat = model.encode_image(x)
        img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)
        img_ms = (time.time() - t) * 1000

        texts = [
            "a red dress",
            "a photo of a blue car",
            "a red jacket",
            "a pair of black shoes",
        ]
        tok = tokenizer(texts).to(dev)
        t = time.time()
        txt_feat = model.encode_text(tok)
        txt_feat = txt_feat / txt_feat.norm(dim=-1, keepdim=True)
        txt_ms = (time.time() - t) * 1000

    print(f"\n  encode_image   {img_ms:.1f} ms")
    print(f"  encode_text    {txt_ms:.1f} ms for {len(texts)} prompts")
    print(f"  embedding dim  {img_feat.shape[-1]}")

    sims = (img_feat @ txt_feat.T).squeeze(0).tolist()
    print("\n  similarity of a RED image to:")
    for s, txt in sorted(zip(sims, texts), reverse=True):
        print(f"    {s:+.4f}  {txt}")

    # FAISS round-trip
    import numpy as np
    d = img_feat.shape[-1]
    index = faiss.IndexFlatIP(d)
    vecs = np.vstack([
        img_feat.cpu().numpy(),
        np.roll(img_feat.cpu().numpy(), 1),
        txt_feat.cpu().numpy(),
    ]).astype("float32")
    faiss.normalize_L2(vecs)
    index.add(vecs)
    D, I = index.search(img_feat.cpu().numpy().astype("float32"), 3)
    print(f"\n  faiss index    {index.ntotal} vectors, top-3 ids {I[0].tolist()} scores {[round(float(x),3) for x in D[0]]}")

    ok = bool(sims[texts.index("a red dress")] > sims[texts.index("a photo of a blue car")])
    print(f"\n  RESULT: red image matches 'a red dress' above 'a blue car' -> {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
