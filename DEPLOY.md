# Showing SmartMall away from home

The constraint that decides everything: **the PC at home will not be running**, because
you may not remember to leave it on. So any option that depends on it is out.

That leaves two shapes:

| | **Option A — a pod you stop, not destroy** | **Option B — free Node host** |
|---|---|---|
| Real AI (CatVTON, SigLIP, Prophet) | ✅ | ❌ fallbacks only |
| Needs the PC at home | ❌ | ❌ |
| Start it from your phone | ✅ one tap | always on |
| Stable URL across demos | ✅ while the pod exists | ✅ |
| Cost | ~US$2/mo idle + ~US$0.50 per demo | free |

**Recommendation: Option A.** It is the only one that shows the real virtual try-on,
and it is the one that keeps working when you forgot to prepare anything at home.

---

## Option A — a pod you stop, not destroy

The trick is that a **stopped** pod keeps its disk, its pod id, and therefore its
public URL. So you install everything once, then each demo is: open the RunPod app →
start the pod → wait ~60 s → open the same URL you used last time.

### One-time setup (~25 minutes, at home on this PC is fine)

1. Create a **network volume** (20 GB is plenty: ~7 GB of models plus the repo) and
   a pod with an **RTX 4090** and a PyTorch template, both in the same region.
2. Open the pod's web terminal and run:

```bash
export VOLUME=/workspace              # wherever the volume is mounted
export SMARTMALL_REPO=https://github.com/<you>/SmartMall.git
bash -c "$(curl -fsSL https://raw.githubusercontent.com/<you>/SmartMall/main/bootstrap-pod.sh)"
```

If you would rather not depend on that URL, clone first and run it locally:

```bash
git clone "$SMARTMALL_REPO" /workspace/SmartMall
cd /workspace/SmartMall && bash bootstrap-pod.sh
```

`bootstrap-pod.sh` verifies the GPU, installs the pinned dependencies, **checks that
torch can see CUDA** (the failure that cost hours on Windows), downloads the 6.7 GB of
models onto the volume, and prepares the CatVTON base. It stops with a clear error
rather than letting you demo a site that silently falls back.

3. In the pod settings, expose **HTTP port 3000**. RunPod gives you
   `https://<pod-id>-3000.proxy.runpod.net` — this is your demo URL.
4. Run the site once, check the four status endpoints, then **stop the pod**.

### Every demo after that

1. On your phone, open the RunPod app or site → **Start** the pod.
2. Wait about a minute (the container boots; models load on first request).
3. Open the saved URL, run one throwaway try-on to warm the pipeline.
4. Present. When finished, **Stop** the pod — never Terminate, or the volume's pod id
   goes with it and the URL changes.

While the pod is stopped the URL returns a gateway error. That is expected; it comes
back the moment the pod is running again.

### Cost, honestly

- Volume storage: 20 GB ≈ **US$2/month** whether running or stopped.
- Compute: RTX 4090 community ≈ **US$0.34–0.69/hr**. A 45-minute demo ≈ **US$0.30–0.50**.
- Forgetting to stop it for a day is the expensive mistake: ~US$12. Set a reminder.

### If you would rather not manage a pod

Rent from **Vast.ai** instead (same card, often US$0.15–0.30/hr). It has no phone app,
so start the instance from the browser; URLs are stable per instance while it is not
destroyed.

---

## Option B — free Node host (no AI, but always online)

Use this as a **backup link**, not as the main demo: it works everywhere, instantly,
with no pod to start, but the models are absent.

The Node layer has zero dependencies, so it deploys straight to Render, Railway or Fly.
Every AI feature has an explicit fallback:

| Feature | Without the AI service |
|---|---|
| Visual search | colour heuristic instead of CLIP |
| Price forecast | linear trend instead of Prophet |
| Virtual try-on | colour overlay preview instead of CatVTON |
| Aesthetic score | returns 503; the page says the service is offline |

Render's free tier sleeps after ~15 minutes idle, so the first hit during a demo takes
~50 s. Use the cheapest paid tier (~US$7/mo) if it matters.

```
Build command : (none)
Start command : node server.js
```

This is also the safe thing to send to a friend: it cannot break, because there is no
GPU to be missing.

---

## Option C — a static snapshot (offline, iPad, no internet at all)

Not built. Would need `tools/export_demo.js` to call every API once and freeze the
responses into a JSON bundle, plus a demo flag in `public/js/api.js`. Try-on and
aesthetic scoring could then only replay pre-generated results for fixed sample
photos, clearly labelled as such.

Only worth it if the demo location has no usable network.

---

## Before any demo — a 2-minute check

```bash
curl -s localhost:3000/api/visual-search/status   # expect "online":true
curl -s localhost:3000/api/forecast/status        # expect "online":true
curl -s localhost:3000/api/tryon/status           # expect "online":true
curl -s localhost:3000/api/aesthetic/status       # expect "online":true
```

If any says `online:false` the feature is silently falling back. The site still works,
but do not claim the model is running — check `.cache/logs/` for the reason.

Then do **one throwaway try-on**: the first generation loads the pipeline and takes
~15 s longer than every later one.
