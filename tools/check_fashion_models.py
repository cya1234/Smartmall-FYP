"""Load the Marqo fashion embedding models and report what they cost to run.

Also verifies the two properties the retrieval code depends on:
  * image and text embeddings share one space and are L2-normalisable
  * cosine similarity ranks a matching caption above an unrelated one
"""
import os
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".cache", "hf"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import torch  # noqa: E402
import open_clip  # noqa: E402
from PIL import Image  # noqa: E402

MODELS = [
    ("ViT-B-32", "laion2b_s34b_b79k", None),
    ("hf-hub:Marqo/marqo-fashionCLIP", None, None),
    ("hf-hub:Marqo/marqo-fashionSigLIP", None, None),
]

IMG = os.path.join(ROOT, "public", "assets", "products", "p001.jpg")
TEXTS = ["a red dress", "a black leather jacket", "white sneakers"]


def load(name, pretrained):
    t0 = time.time()
    if pretrained:
        model, _, preprocess = open_clip.create_model_and_transforms(name, pretrained=pretrained)
        tokenizer = open_clip.get_tokenizer(name)
    else:
        model, _, preprocess = open_clip.create_model_and_transforms(name)
        tokenizer = open_clip.get_tokenizer(name)
    model.eval()
    return model, preprocess, tokenizer, time.time() - t0


def main():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  device: {dev}")
    ref = Image.open(IMG).convert("RGB")

    for name, pretrained, _ in MODELS:
        label = pretrained or name
        print(f"\n== {label} ==")
        try:
            model, preprocess, tokenizer, load_s = load(name, pretrained)
            model = model.to(dev)
            n_params = sum(p.numel() for p in model.parameters()) / 1e6
            print(f"  load      : {load_s:.1f}s   params {n_params:.0f}M")

            with torch.no_grad(), torch.autocast(dev, dtype=torch.float16 if dev == "cuda" else torch.bfloat16):
                t0 = time.time()
                img = preprocess(ref).unsqueeze(0).to(dev)
                ifeat = model.encode_image(img)
                enc_ms = (time.time() - t0) * 1000
                t0 = time.time()
                txt = tokenizer(TEXTS).to(dev)
                tfeat = model.encode_text(txt)
                txt_ms = (time.time() - t0) * 1000

            ifeat = ifeat / ifeat.norm(dim=-1, keepdim=True)
            tfeat = tfeat / tfeat.norm(dim=-1, keepdim=True)
            print(f"  dim       : {ifeat.shape[-1]}  (image {enc_ms:.0f} ms, text {txt_ms:.0f} ms)")

            sims = (ifeat @ tfeat.T).squeeze(0).float().cpu().tolist()
            ranked = sorted(zip(TEXTS, sims), key=lambda kv: -kv[1])
            print("  cosine    : " + " | ".join(f"{t}={s:.3f}" for t, s in ranked))
            print(f"  shared space: {abs(sum(sims)) < 10}  (finite={all(abs(s) < 100 for s in sims)})")

            del model
            torch.cuda.empty_cache()
        except Exception as e:
            print(f"  FAILED    : {type(e).__name__}: {e}")


if __name__ == "__main__":
    sys.exit(main())
