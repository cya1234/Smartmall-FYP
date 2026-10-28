"""Resumable fetch of the Marqo open_clip checkpoints.

The bulk download stalled part-way, so we fetch the two files open_clip actually
needs, one at a time, and retry on failure. hf_hub_download resumes from the
existing .incomplete file, so re-running this is safe and cheap.
"""
import os
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".cache", "hf"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from huggingface_hub import hf_hub_download  # noqa: E402

TARGETS = [
    ("Marqo/marqo-fashionSigLIP", ["open_clip_config.json", "open_clip_model.safetensors"]),
    ("Marqo/marqo-fashionCLIP", ["open_clip_config.json", "open_clip_model.safetensors"]),
]


def fetch(repo, filename, attempts=6):
    for i in range(1, attempts + 1):
        try:
            path = hf_hub_download(repo_id=repo, filename=filename)
            size = os.path.getsize(path) / 1e6
            print(f"    ok   {filename}  {size:.0f} MB", flush=True)
            return path
        except Exception as e:
            print(f"    retry {i}/{attempts} {filename}: {type(e).__name__}: {str(e)[:120]}", flush=True)
            time.sleep(3 * i)
    return None


def main():
    ok = True
    for repo, files in TARGETS:
        print(f"\n  {repo}", flush=True)
        for f in files:
            if not fetch(repo, f):
                ok = False
    print("\n  ALL FETCHED" if ok else "\n  SOME FILES FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
