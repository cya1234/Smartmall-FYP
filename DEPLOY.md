# Showing SmartMall away from this PC

The site is four processes on one machine. To present it somewhere else you have to
decide which of the two things you need: **the real models**, or **just the site**.

| | Option A — GPU pod | Option B — free Node host | Option C — static snapshot | Option D — tunnel home |
|---|---|---|---|---|
| Real AI (CatVTON, SigLIP, Prophet) | ✅ | ❌ fallbacks only | ❌ pre-computed | ✅ |
| Needs this PC on | ❌ | ❌ | ❌ | ✅ |
| Works offline / on iPad | ❌ | ❌ | ✅ | ❌ |
| Cost per demo | ~US$0.30–0.70 | free | free | free |
| Setup time | ~20 min first time | ~10 min | ~15 min | ~2 min |

**Short answer:** if the professor must see real virtual try-on, use **A**. If the PC
can stay switched on at home, **D** is free and identical to local. **B** is for
"send a friend a link". **C** is for a tablet with no internet.

---

## Option D — tunnel from home (only if the PC can stay on)

Cheapest way to get the real thing. One command, no accounts:

```powershell
# in the SmartMall folder
cloudflared tunnel --url http://localhost:3000
```

It prints a `https://something.trycloudflare.com` URL that works anywhere. The URL
changes every restart. Close the window to revoke it. The site is only reachable
while both the tunnel and `start-with-ai.bat` are running.

Do not leave this up unattended: there is no password. Add one, or use Option A.

---

## Option A — a GPU pod (real AI, no PC at home)

Rent by the hour, present, then destroy. On RunPod pick a **RTX 4090** community
pod with a PyTorch template (~US$0.34–0.69/hr); on Vast.ai the same card is often
US$0.15–0.30/hr. A 30-minute demo costs well under a dollar.

```bash
# 1. get the code
git clone https://github.com/<you>/SmartMall.git && cd SmartMall

# 2. python deps (the template already has a CUDA-matched torch)
pip install -r requirements.txt
python -c "import torch; print(torch.cuda.is_available())"   # must print True

# 3. models — 6.7 GB, one time. On RunPod attach a network volume at /workspace so
#    you only download once, then re-use it on every future pod.
python - <<'PY'
import os
os.environ["HF_HOME"] = os.path.abspath(".cache/hf")
from huggingface_hub import snapshot_download
snapshot_download("Marqo/marqo-fashionSigLIP")
snapshot_download("timbrooks/instruct-pix2pix", allow_patterns=["*fp16*", "*.json", "tokenizer/*"])
PY
python tools/prepare_catvton_base.py     # places the CatVTON weights

# 4. run everything
bash start-all.sh
```

Then expose port 3000: RunPod gives you a **Connect → HTTP service** URL for the
port directly, which is the simplest path because it terminates TLS for you.

Notes:
- `HOST` already defaults to `0.0.0.0`, so the server is reachable from outside.
- `start-all.sh --no-tryon` starts without CatVTON when you only need the shop.
- Destroy the pod when finished — billing is per second while it exists.

---

## Option B — free Node host (no AI, but always online)

The Node layer has zero dependencies, so it deploys instantly to Render, Railway or
Fly. Every AI feature has an explicit fallback, so the site stays fully usable:

| Feature | Without the AI service |
|---|---|
| Visual search | colour heuristic instead of CLIP |
| Price forecast | linear trend instead of Prophet |
| Virtual try-on | colour overlay preview instead of CatVTON |
| Aesthetic score | returns 503, the page says the service is offline |

Render free tier spins down after ~15 minutes idle, so the first request during a
demo takes ~50 seconds. Use the cheapest paid tier (~US$7/mo) for a real demo.

```
Build command : (none)
Start command : node server.js
Environment   : PORT is provided by the host
```

---

## Option C — a static snapshot (offline, iPad, no server)

Not built yet. Would need `tools/export_demo.js` to call every API once and freeze
the responses into a JSON bundle, plus a demo flag in `public/js/api.js` that reads
from that bundle instead of the network. Try-on and aesthetic scoring could then
only show pre-generated results for fixed sample photos, clearly labelled.

Worth it only if you need to demonstrate where there is no internet at all.

---

## Before any demo — a 2-minute check

```bash
curl -s localhost:3000/api/visual-search/status   # expect "online":true
curl -s localhost:3000/api/forecast/status        # expect "online":true
curl -s localhost:3000/api/tryon/status           # expect "online":true
curl -s localhost:3000/api/aesthetic/status       # expect "online":true
```

If any says `online:false`, that feature will silently fall back — the site will
still work, but do not claim the model is running. Check `.cache/logs/` for why.

Then do **one throwaway try-on** before the meeting: the first generation loads the
pipeline and takes ~15 s longer than the rest.
