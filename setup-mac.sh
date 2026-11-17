#!/usr/bin/env bash
# Set up SmartMall on macOS (Apple Silicon or Intel), from a fresh clone.
#
#   git clone https://github.com/cya1234/Smartmall-FYP.git SmartMall
#   cd SmartMall && bash setup-mac.sh
#
# It creates .venv, installs the dependencies, downloads the 6.7 GB of models, and
# checks that PyTorch can see the Apple GPU. Run it once; afterwards start-all.sh is
# all you need.
#
# What it does NOT do: install Homebrew, Xcode command line tools, or cmdstan. See the
# notes it prints at the end if Prophet is missing.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT="$PWD"

say() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
ok()  { printf '   \033[32mOK\033[0m  %s\n' "$*"; }
warn(){ printf '   \033[33m!!\033[0m  %s\n' "$*"; }
bad() { printf '   \033[31mFAIL\033[0m %s\n' "$*"; }

say "1. This machine"
if [[ "$(uname -s)" != "Darwin" ]]; then
  bad "this script is for macOS; on Linux use bootstrap-pod.sh or install manually"
  exit 1
fi
ARCH="$(uname -m)"
echo "   macOS $(sw_vers -productVersion) on ${ARCH}"
[[ "$ARCH" == "arm64" ]] && ok "Apple Silicon — the GPU backend is MPS" \
                         || warn "Intel Mac — no GPU acceleration, try-on will be slow or CPU-only"

say "2. Python"
PY="$(command -v python3 || true)"
if [[ -z "$PY" ]]; then
  bad "python3 not found. Install it with: brew install python@3.11"
  exit 1
fi
echo "   $($PY --version) at $PY"
"$PY" - <<'STOP' || { bad "Python 3.10+ is required"; exit 1; }
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
STOP
ok "version is new enough"

say "3. Virtual environment"
if [[ ! -x .venv/bin/python ]]; then
  "$PY" -m venv .venv || { bad "could not create .venv"; exit 1; }
fi
VPY="$ROOT/.venv/bin/python"
"$VPY" -m pip install --quiet --upgrade pip
ok "venv at .venv"

say "4. PyTorch (this is the big one, ~2 GB)"
# Deliberately unpinned: the wheel must match the platform, and PyPI's macOS arm64
# build already carries MPS. Pinning the CUDA version used on Windows would fail here.
if ! "$VPY" -m pip install --quiet torch torchvision; then
  bad "torch install failed"; exit 1
fi
if "$VPY" - <<'STOP'
import sys, torch
mps = getattr(torch.backends, "mps", None)
avail = bool(mps and mps.is_available())
print(f"   torch {torch.__version__}  mps={avail}")
raise SystemExit(0 if avail else 1)
STOP
then
  ok "PyTorch can see the Apple GPU"
else
  warn "MPS is not available — everything still runs, but try-on will fall back to CPU"
fi

say "5. The rest of the dependencies"
# torch and torchvision are stripped out: they are already installed and must not be
# re-resolved, which is exactly how the CUDA build got silently replaced on Windows.
grep -viE '^\s*(torch|torchvision)\s*==' requirements.txt > .venv/.requirements-mac.txt
if ! "$VPY" -m pip install --quiet -r .venv/.requirements-mac.txt; then
  bad "dependency install failed — read the output above"
  exit 1
fi
ok "dependencies installed"

say "6. Models (~6.7 GB, one time)"
export HF_HOME="$ROOT/.cache/hf"
echo "   CLIP/SigLIP + image index ..."
"$VPY" tools/build_clip_index.py || bad "index build failed"
echo "   CatVTON base weights ..."
"$VPY" tools/prepare_catvton_base.py || bad "CatVTON base failed"

say "7. Prophet needs cmdstan"
if "$VPY" -c "import cmdstanpy, os, sys; sys.exit(0 if os.path.exists(cmdstanpy.cmdstan_path() or '') else 1)" 2>/dev/null; then
  ok "cmdstan found — price forecasting will work"
else
  warn "cmdstan not installed: the forecast service will not start"
  echo "      brew install cmdstan"
  echo "      # or: $VPY -c \"import cmdstanpy; cmdstanpy.install_cmdstan()\"  (needs Xcode CLT)"
fi

say "Ready"
cat <<'TXT'
   Start everything:   bash start-all.sh
   Then open:          http://localhost:3000
   Optional LLM:       ollama pull qwen2.5:3b-instruct
                       ASSISTANT_LLM=1 bash start-all.sh

   Expectation setting: an M-series Mac runs the try-on in roughly 50-90 s per
   image versus ~22 s on the RTX 4070. Everything else — search, forecast,
   ratings, survey, dashboard — is fast.
TXT
