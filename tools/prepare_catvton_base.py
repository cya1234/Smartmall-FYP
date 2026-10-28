"""Materialise an fp16-only SD1.5-inpainting snapshot with standard filenames.

CatVTON's pipeline calls `UNet2DConditionModel.from_pretrained(base_ckpt,
subfolder="unet")` with **no** `variant` argument, so it looks for
`diffusion_pytorch_model.safetensors`. The Hugging Face repo only ships fp16
variants under `*.fp16.safetensors`, and downloading the fp32 set as well would
cost another ~4.2 GB for weights we immediately cast to fp16 anyway.

So we build a local directory whose files are hard links (no extra disk) to the
fp16 blobs but named the way diffusers expects. Everything stays inside the
workspace and nothing is duplicated.

Run:  .venv\\Scripts\\python.exe tools/prepare_catvton_base.py
"""
import json
import os
import shutil
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".cache", "hf"))

OUT_ROOT = os.path.join(ROOT, "data", "models")

# CatVTON needs one base; the mask-free (pix2pix) variant needs a different one
# because its UNet takes 8 latent channels instead of the inpainting model's 9.
BASES = [
    ("runwayml/stable-diffusion-inpainting", "sd15-inpainting-fp16"),
    ("timbrooks/instruct-pix2pix", "instruct-pix2pix-fp16"),
]

# (source relative path, destination relative path)
FILES = [
    ("unet/config.json", "unet/config.json"),
    ("unet/diffusion_pytorch_model.fp16.safetensors", "unet/diffusion_pytorch_model.safetensors"),
    ("vae/config.json", "vae/config.json"),
    ("vae/diffusion_pytorch_model.fp16.safetensors", "vae/diffusion_pytorch_model.safetensors"),
    ("text_encoder/config.json", "text_encoder/config.json"),
    ("text_encoder/model.fp16.safetensors", "text_encoder/model.safetensors"),
    ("scheduler/scheduler_config.json", "scheduler/scheduler_config.json"),
    ("tokenizer/merges.txt", "tokenizer/merges.txt"),
    ("tokenizer/special_tokens_map.json", "tokenizer/special_tokens_map.json"),
    ("tokenizer/tokenizer_config.json", "tokenizer/tokenizer_config.json"),
    ("tokenizer/vocab.json", "tokenizer/vocab.json"),
]

MODEL_INDEX = {
    "_class_name": "StableDiffusionInpaintPipeline",
    "_diffusers_version": "0.42.1",
    "scheduler": ["diffusers", "DDIMScheduler"],
    "text_encoder": ["transformers", "CLIPTextModel"],
    "tokenizer": ["transformers", "CLIPTokenizer"],
    "unet": ["diffusers", "UNet2DConditionModel"],
    "vae": ["diffusers", "AutoencoderKL"],
}
def link_or_copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        return "exists"
    try:
        os.link(src, dst)          # same volume: zero extra bytes
        return "hardlink"
    except OSError:
        shutil.copy2(src, dst)     # fallback
        return "copy"


def build(repo, out_name):
    from huggingface_hub import snapshot_download

    out = os.path.join(OUT_ROOT, out_name)
    src_dir = snapshot_download(
        repo,
        allow_patterns=[f for f, _ in FILES],
        ignore_patterns=["*.bin", "safety_checker/**", "*.onnx", "*.ckpt"],
    )
    print(f"  snapshot : {src_dir}")

    made = {}
    for src_rel, dst_rel in FILES:
        src = os.path.join(src_dir, src_rel)
        dst = os.path.join(out, dst_rel)
        if not os.path.exists(src):
            print(f"  MISSING  {src_rel}")
            return False
        made[dst_rel] = link_or_copy(src, dst)

    with open(os.path.join(out, "model_index.json"), "w", encoding="utf-8") as fh:
        json.dump(MODEL_INDEX, fh, indent=1)

    counts = {}
    for v in made.values():
        counts[v] = counts.get(v, 0) + 1
    print(f"  built    : {out}")
    print(f"  files    : {counts}")

    # Verify diffusers can load each component without a variant argument.
    import torch
    from diffusers import AutoencoderKL, DDIMScheduler, UNet2DConditionModel
    from transformers import CLIPTextModel

    for name, loader in [("unet", UNet2DConditionModel), ("vae", AutoencoderKL)]:
        m = loader.from_pretrained(out, subfolder=name, torch_dtype=torch.float16)
        n = sum(p.numel() for p in m.parameters()) / 1e6
        extra = ""
        if name == "unet":
            extra = f"  in_channels={m.config.in_channels}"
        print(f"  load {name:12s} ok  {n:.0f}M params{extra}")
        del m
    te = CLIPTextModel.from_pretrained(out, subfolder="text_encoder", torch_dtype=torch.float16)
    print(f"  load text_encoder ok  {sum(p.numel() for p in te.parameters())/1e6:.0f}M params")
    DDIMScheduler.from_pretrained(out, subfolder="scheduler")
    print("  load scheduler    ok")
    return True


def main():
    ok = True
    for repo, out_name in BASES:
        print(f"\n== {repo} ==")
        if not build(repo, out_name):
            ok = False
    print("\n  ALL BASES READY" if ok else "\n  SOME BASES FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
