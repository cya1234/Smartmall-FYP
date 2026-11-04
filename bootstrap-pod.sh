#!/usr/bin/env bash
# One-time setup for a GPU pod (RunPod / Vast.ai / any Ubuntu + CUDA box).
#
# Run this ONCE inside the pod, with the repo cloned onto the persistent volume:
#
#   export VOLUME=/workspace            # the network volume mount
#   bash bootstrap-pod.sh
#
# After this, every future demo is: start the pod -> bash start-all.sh -> open the URL.
# No models are re-downloaded because they live on the volume, not the container disk.
set -uo pipefail

VOLUME="${VOLUME:-/workspace}"
ROOT="${SMARTMALL_DIR:-$VOLUME/SmartMall}"
REPO="${SMARTMALL_REPO:-}"

say() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
ok()  { printf '   \033[32mOK\033[0m  %s\n' "$*"; }
bad() { printf '   \033[31mFAIL\033[0m %s\n' "$*"; }

say "1. GPU check"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | sed 's/^/   /'
else
  bad "nvidia-smi not found - this is not a GPU box, CatVTON will not run"
fi

say "2. Keep the code on the volume"
mkdir -p "$VOLUME"
if [[ ! -d "$ROOT/.git" ]]; then
  if [[ -z "$REPO" ]]; then
    bad "repo not found at $ROOT and SMARTMALL_REPO is not set"
    echo "   export SMARTMALL_REPO=https://github.com/<you>/SmartMall.git"
    echo "   then re-run this script"
    exit 1
  fi
  git clone "$REPO" "$ROOT"
fi
cd "$ROOT"
ok "code at $ROOT"

say "3. Python dependencies"
python -m pip install --quiet --upgrade pip
if ! python -m pip install --quiet -r requirements.txt; then
  bad "dependency install failed - see the output above"
  exit 1
fi
ok "requirements installed"

say "4. Verify the CUDA build of torch"
# This is the failure that bit us twice on Windows: a dependency resolver quietly
# swapping the CUDA wheel for a CPU one. Everything still imports, it is just 50x
# slower and CatVTON eventually fails on a device mismatch.
if python - <<'PY'
import sys, torch
print(f"   torch {torch.__version__}  cuda={torch.cuda.is_available()}")
sys.exit(0 if torch.cuda.is_available() else 1)
PY
then ok "torch sees the GPU"
else
  bad "torch cannot see the GPU - every AI feature will fall back, and try-on will not run"
  echo "   fix: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124"
  exit 1
fi

say "5. Models (about 6.7 GB, once)"
export HF_HOME="$ROOT/.cache/hf"
python - <<'PY'
import os, sys
os.environ.setdefault("HF_HOME", os.path.abspath(".cache/hf"))
from huggingface_hub import snapshot_download
for repo, patterns in [
    ("Marqo/marqo-fashionSigLIP", None),
    ("timbrooks/instruct-pix2pix", ["*fp16*", "*.json", "tokenizer/*", "scheduler/*"]),
]:
    print(f"   fetching {repo} ...", flush=True)
    snapshot_download(repo, allow_patterns=patterns)
print("   done")
PY
python tools/prepare_catvton_base.py || bad "CatVTON base preparation failed - run it again to see why"
ok "models ready"

say "6. Optional: CLIP index"
# The index is committed, so this normally is not needed. Rebuild only if the
# catalogue changed.
if [[ ! -f data/clip-index.faiss ]]; then
  echo "   index missing - rebuilding"
  python tools/build_clip_index.py
fi
ok "index present"

say "Ready"
cat <<'TXT'
   Start the demo:      bash start-all.sh
   Public URL:          RunPod -> Connect -> HTTP service on port 3000
   Stop when finished:  stop the pod (do NOT terminate it) so the
                        volume, torch and models survive to the next demo.

   Warming up costs ~40 s (CatVTON pipeline load). Open the site once,
   run one throwaway try-on, then present.
TXT
