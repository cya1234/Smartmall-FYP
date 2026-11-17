# SmartMall — Setup

An AI-driven fashion e-commerce platform built for small Hong Kong apparel
retailers. Twelve functional modules sit behind four independently deployable AI
services. Every service can be switched off and the site still works.

- **Visual search** — Marqo-FashionSigLIP + FAISS, Chinese queries normalised to
  English fashion terms first
- **Price forecast** — Meta Prophet, with the sale calendar as holiday regressors
- **Virtual try-on** — CatVTON mask-free variant, runs locally on the GPU
- **Assistant** — a tool-calling agent whose answers may only quote tool facts

---

## Requirements

| | Needed for | Notes |
|---|---|---|
| **Node.js 22+** | the web server | no npm packages; built-in modules only |
| **Python 3.11** | the AI services | `python-docx` / `python-pptx` are only needed to rebuild the documents |
| **NVIDIA GPU, 8 GB+** | try-on, and fast visual search | everything degrades to CPU or heuristics without one |

Model weights are **not** in this repository — they are 7 GB and GitHub rejects
files over 100 MB. They download on first run; see [Models](#models).

---

## Quick start (site only, no AI)

```bash
git clone <your-repo-url> SmartMall
cd SmartMall
node server.js
```

Open <http://localhost:3000>. You get the full storefront, cart, merchant
dashboard, store locator and embeds. Visual search falls back to a colour
heuristic, forecasting to a linear trend, and try-on to a colour overlay.

---

## Full setup (with the AI services)

### 1. Python environment

```powershell
py -3.11 -m venv --system-site-packages .venv
```

`--system-site-packages` is deliberate: it lets the venv inherit a CUDA build of
PyTorch that is already installed. Without it, pip resolves `torch` from PyPI and
you get the **CPU** wheel.

```powershell
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install open_clip_torch faiss-cpu prophet diffusers accelerate transformers
```

> ⚠️ **Check this immediately after installing anything:**
> ```powershell
> .venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
> ```
> If it prints a `+cpu` build, run:
> ```powershell
> .venv\Scripts\python.exe -m pip uninstall torch torchvision
> ```
> and re-check. `diffusers` in particular pulls a CPU torch wheel that silently
> shadows the CUDA one.

### 2. Models

```powershell
# Try-on base (downloads and hard-links an fp16 snapshot; ~2 GB)
.venv\Scripts\python.exe tools\prepare_catvton_base.py

# Visual-search index (downloads Marqo-FashionSigLIP; ~800 MB)
.venv\Scripts\python.exe tools\build_clip_index.py
```

Both cache into `.cache/hf`, which is git-ignored.

To avoid re-downloading, set `HF_HOME` once:

```powershell
setx HF_HOME "%CD%\.cache\hf"
```

### 3. Run

```powershell
.\start-with-ai.bat
```

This opens four windows (CLIP, Prophet, CatVTON, web) and waits for the models
before starting the site. Keep them open.

Or start each service by hand:

```powershell
.venv\Scripts\python.exe ai-service\visual_search_service.py --port 8001
.venv\Scripts\python.exe ai-service\forecast_service.py      --port 8002
.venv\Scripts\python.exe ai-service\tryon_service.py         --port 8003
node server.js
```

| Service | Port | First-load time |
|---|---|---|
| Web | 3000 | instant |
| Visual search | 8001 | ~5 s |
| Price forecast | 8002 | ~2 s |
| Virtual try-on | 8003 | ~15 s |

### 4. Optional: regenerate the demo data

`data/price-history.json` and `data/analytics.db` are committed and already
seeded, so you do not need these to run the site. They reproduce the evaluation
numbers:

```powershell
.venv\Scripts\python.exe tools\build_price_history.py   # 40 products x 800 days
.venv\Scripts\python.exe tools\eval_forecast.py         # holdout comparison
```

---

## Models

| Model | Source | Size | Used by |
|---|---|---|---|
| `Marqo/marqo-fashionSigLIP` | Hugging Face, Apache 2.0 | 813 MB | visual search |
| `zhengchong/CatVTON-MaskFree` | Hugging Face, **CC BY-NC-SA 4.0** | 396 MB | try-on |
| `timbrooks/instruct-pix2pix` | Hugging Face | ~2 GB fp16 | try-on base (8-channel UNet) |
| `stabilityai/sd-vae-ft-mse` | Hugging Face | ~330 MB | try-on VAE |

⚠️ **The CatVTON licence is non-commercial.** Fine for coursework and research;
a commercial deployment needs a differently licensed model.

---

## Verifying an install

Seven suites, 135 checks, no test framework required:

```powershell
$env:PY = ".venv\Scripts\python.exe"
foreach ($t in "site_regression","visual_e2e","stores_e2e","forecast_e2e",
               "analytics_e2e","widget_e2e","tryon_e2e") {
  & $env:PY "tools\test_$t.py" "http://127.0.0.1:3000"
}
```

Suites that depend on a stopped service skip or degrade rather than fail, so a
partial install still reports honestly.

Reproducing the three evaluation tables:

```powershell
.venv\Scripts\python.exe tools\eval_retrieval.py   # Recall@K, 94 bilingual queries
.venv\Scripts\python.exe tools\eval_forecast.py    # Prophet vs two baselines
.venv\Scripts\python.exe tools\eval_assistant.py   # tool accuracy / grounding
```

Results land in `data/eval/`.

---

## Sharing the demo

The AI services need a GPU, so the site cannot run on GitHub Pages or a free
static host. Three workable options:

**A. Tailscale — reach this PC from anywhere, privately** (best if the PC can stay on):

```powershell
winget install tailscale.tailscale
tailscale up            # sign in, then note the 100.x.y.z address
```

Install Tailscale on the Mac or phone too, and open `http://100.x.y.z:3000` from
anywhere. The traffic is private to your tailnet — no public URL, no authentication
to bolt on. The PC must stay awake; set it not to sleep.

For a URL you can open from a device *without* Tailscale (a friend's phone, the
campus PC), use **Tailscale Funnel** instead — it publishes one port to the public
internet over HTTPS:

```powershell
tailscale funnel 3000
# -> https://<machine>.<tailnet>.ts.net
```

Funnel is public: run `tailscale funnel off` when the demo ends.

**B. Tunnel to your own machine** (no Tailscale account, public URL):

```powershell
winget install Cloudflare.cloudflared
cloudflared tunnel --url http://localhost:3000
```

You get a public HTTPS URL that reflects whatever is running locally, so code
changes take effect on refresh. Caveats: your machine must stay awake, the free
quick-tunnel URL changes on restart, and there is no authentication — do not
publish the URL widely.

**C. Deploy the web tier only.** Render/Railway can run `node server.js`, which
gives you the storefront and the merchant dashboard but **not** try-on, visual
search or forecasting, because none of them run without a GPU. That removes the
three things worth demonstrating, so it is not recommended for a demo.

### Moving the project to a Mac

The repository is ~22 MB; the 6.7 GB of model weights are deliberately not in it and
are re-downloaded on the new machine.

```bash
git clone https://github.com/cya1234/Smartmall-FYP.git SmartMall
cd SmartMall
bash setup-mac.sh      # venv, dependencies, models, and an MPS check
bash start-all.sh
```

`setup-mac.sh` installs an unpinned `torch`/`torchvision` because the macOS arm64
wheel is the one with MPS support — pinning the CUDA build used on Windows would fail
on a Mac. `ai-service/device_util.py` then picks CUDA, MPS or CPU at runtime, so the
same code runs on both machines.

Expect the Mac to be slower at exactly one thing: try-on takes roughly 50–90 s per
image on an M-series chip versus ~22 s on the RTX 4070. Everything else is fast.

macOS needs two extras the Windows machine did not:

```bash
brew install python@3.11     # if python3 is missing or too old
brew install cmdstan         # Prophet will not start without it
```

If `setup-mac.sh` reports `mps=False`, try-on still runs but on CPU (minutes per
image); check that you are on an Apple Silicon build of Python (`python3 -c "import
platform; print(platform.machine())"` should print `arm64`).

---

## Layout

```
server.js                  Node HTTP server, zero dependencies
lib/                       domain logic (one file per capability)
  agent/                   tool-calling assistant: tools, router, orchestrator
  analytics.js             SQLite event store for the merchant dashboard
  forecast.js              Prophet client with a linear fallback
  stores.js                O2O stock and distance
  tryon.js                 CatVTON client with an overlay fallback
ai-service/                Python inference services + vendored CatVTON source
public/                    vanilla-JS SPA, no build step
data/                      catalogue, price history, stores, evaluation results
tools/                     evaluation harnesses, model prep, document builders
```

## Known gotchas

| Symptom | Cause | Fix |
|---|---|---|
| `torch.cuda.is_available()` is False | a CPU torch wheel shadowed the CUDA one | `pip uninstall torch torchvision`, re-check |
| Try-on returns `unexpected channels: 9 vs 8` | wrong base model | the mask-free pipeline needs `timbrooks/instruct-pix2pix` (8-channel), not SD-inpainting (9-channel) |
| Try-on cuts off the head | CatVTON centre-crops to 3:4 | already fixed: the service pads to 3:4 before inference; upload a waist-up photo for best results |
| Visual search ignores Chinese | the fashion encoders are English-aligned | already fixed: `data/fashion-glossary.json` normalises the query |
| Hugging Face download stalls | connection reset | re-run the tool; `hf_hub_download` resumes |
