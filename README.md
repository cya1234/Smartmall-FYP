# SmartMall — AI-Driven E-Commerce Platform

A full-stack, bilingual (繁體中文 / English) web application built from the **FYP Initial
Proposal** (Chiu Cheuk Nam · Wong Pui Lam) and the accompanying 簡報. It replaces passive,
keyword-based shopping with contextual, multimodal AI across **ten modules**.

Open the site and every AI capability is reachable from the top navigation.

## The ten AI modules

| # | Module | What it does | Code |
|---|---|---|---|
| 1 | **造型盒** — Scenario blind box | Give a budget + scenario ("預算 2000，下個月去北海道滑雪"). The AI assembles a *complete* kit in necessity order, trimmed to the budget, with a styling reason per item and three price tiers. | `lib/blindbox.js` · `public/js/views/blindbox.js` |
| 2 | **情境購物助手** — Contextual assistant | LLM+RAG-style parse → retrieve → bundle → explain. | `lib/assistant.js` · `views/assistant.js` |
| 3 | **多模態視覺搜尋** — Visual search | **Marqo-FashionSigLIP + FAISS**, with Chinese queries normalised to English fashion terms first. A photo and/or text modifier is encoded and fused into one unified query embedding, then matched by cosine similarity. Evaluated on a 94-query bilingual set: **Recall@5 97.9 %** (from 84.0 % on the previous backbone). Falls back to a colour heuristic if the service is offline. Reached from the camera icon in the header search bar. | `ai-service/visual_search_service.py` · `lib/visualSearch.js` |
| 4 | **價格趨勢預測** — Price forecasting | **Real Meta Prophet**, with the HK/Greater-China sale calendar as explicit holiday regressors. Returns a 30-day forecast with an 80% interval, a Buy Now / Wait advisory and a holdout comparison against two baselines. Falls back to a linear trend if the service is offline. | `ai-service/forecast_service.py` · `lib/forecast.js` |
| 5 | **門市現貨與導航** — O2O store pickup | 8 real Hong Kong districts with MTR exits and trading hours. Shows cross-store stock when an item is sold out online, same-day pickup, and one-tap Google Maps directions. | `lib/stores.js` · `views/stores.js` |
| 6 | **虛擬試穿** — Virtual try-on | Diffusion-style garment synthesis onto your photo (simulated). | `lib/tryon.js` · `views/tryon.js` |
| 7 | **跨平台比價與議價** — Price agent | Scans 7 marketplaces, auto-claims coupons, then negotiates a bulk price with the seller in a live transcript. | `lib/priceAgent.js` · `views/priceagent.js` |
| 8 | **二手流轉一鍵託管** — Resale consignment | AI writes the listing + prices it, one click publishes it, another shopper can buy it — closing the buy→wear→resell loop with eco metrics. | `lib/resale.js` · `views/resale.js` |
| 9 | **私密試穿投票** — Private friend voting | Share a try-on to a friends-only group; friends vote and comment; a verdict is produced. Friends-only, 24h expiry, never indexed. | `lib/social.js` · `views/tryon.js` |
| 10 | **記憶與個人化畫像** — Long-term memory | Remembers purchases, sizes, style, budget and returns. Ask "去海島婚禮穿什麼" and it builds the look **around the linen shirt you bought 3 months ago** instead of selling a whole new set. | `lib/memory.js` · `views/memory.js` |
| 11 | **退貨預測 + 智慧客服** — Return prediction & support | Predicts return risk from body data + return history and recommends a size *before* you buy; on return, guides your photos, detects the defect and drafts the return form. | `lib/returnPredict.js`, `lib/support.js` · `views/support.js` |
| 12 | **商戶後台** — Merchant analytics | Search volume, exit-intent retention, coupon usage and conversion, backed by a SQLite event store. | `lib/analytics.js` · `views/dashboard.js` |

### Information architecture

The top navigation is deliberately five items — 首頁 · 商店 · 搭配顧問 · 門市 · 我的 — the same
shape as a real storefront. Image search lives on the camera icon inside the header search bar,
and the remaining tools (trial room, price trends, resale, support, merchant dashboard) sit in
the footer and the home feature grid instead of competing for nav space.

## Run it

Requires Node.js 18+. **The website itself has zero npm dependencies and no build step.**

```bash
node server.js      # or: npm start
```

Open **http://localhost:3000** (set `PORT` to change). On Windows you can also double-click
`start.bat`.

### Optional: the real CLIP visual search

Visual search runs a **real CLIP model on your GPU** when the Python inference service is up.
Without it the site still works — `lib/visualSearch.js` falls back to the colour heuristic and
the UI shows an "AI service offline" banner.

```bash
# one-time setup (creates .venv inside the project, reuses your CUDA PyTorch)
py -3.11 -m venv --system-site-packages .venv
.cache\uv\uv.exe pip install --python .venv\Scripts\python.exe open_clip_torch faiss-cpu pyarrow

# build the image index (downloads product photos + embeds them)
.venv\Scripts\python.exe tools\pick_product_images.py
.venv\Scripts\python.exe tools\build_clip_index.py

# run the inference service
.venv\Scripts\python.exe ai-service\visual_search_service.py --port 8001
```

Then open **Visual Search**, drop in a photo and search. Verified on an RTX 4070:
**19 ms per image embed**, **8–24 ms per query**, 36 products indexed.

> Why a separate process? It is the proposal's own architecture — ordinary web operations are
> decoupled from high-dimensional inference, so the shop keeps serving if the model tier goes
> down. `VISUAL_SEARCH_URL` points the Node tier at a different host/port.

Toggle **EN / 繁中** in the top bar. The Chinese UI prices in **HK$** and the English UI in
**US$** (`lib/store.js` → `CURRENCIES`; base prices are stored in USD).

## Sharing with friends

The server binds to `0.0.0.0`, so it is reachable on every network interface, and it prints the
usable URLs on startup (`HOST=127.0.0.1` keeps it local-only).

**Same Wi-Fi.** Send friends the "(same Wi-Fi)" URL, e.g. `http://192.168.0.190:3000`. If they
cannot connect, Windows Firewall is blocking the port — run this once in an **Administrator**
PowerShell:

```powershell
New-NetFirewallRule -DisplayName "SmartMall 3000" -Direction Inbound -Protocol TCP -LocalPort 3000 -Action Allow
```

Remove it later with `Remove-NetFirewallRule -DisplayName "SmartMall 3000"`.

**Tailscale (works from anywhere).** Invite your friends to your tailnet, then share the
`100.x.x.x` URL. No port forwarding, and traffic is encrypted.

**Public link.** If your friends should not install anything, expose the port with a tunnel:

```bash
cloudflared tunnel --url http://localhost:3000    # or: ngrok http 3000
```

That prints a public https URL anyone can open. Only do this while you actually want the demo
public — there is no authentication in front of it.

**Deploy.** Because there are zero dependencies and `npm start` is the entry point, this drops
onto Render / Railway / Fly.io unchanged. Free tiers sleep when idle, and the in-memory state
(resale listings, polls, return forms) resets on restart.

> Keep the server window open while friends are using the site. Everyone connected shares the
> **same demo profile** (`data/profile.json`), so resale listings and friend-vote polls are
> common to all visitors. Carts live in each browser's `localStorage`, so those stay individual.

## Demos worth trying

1. **Blind box** → leave the prefilled `預算 2000 元，下個月去北海道滑雪` and generate.
   The AI returns a ski jacket + snow pants + goggles + beanie inside HK$2,000 and tells you
   the thermal base layer falls outside the budget, with the minimum budget needed.
2. **Assistant** → ask `我下個月要去海島婚禮，穿什麼好？`. The first bundle is built around the
   linen shirt already in your wardrobe (marked 已有, priced at zero) with matching chinos.
3. **Price agent** → select items (or "compare my cart") and launch. Watch the negotiation.
4. **Resale** → pick a wardrobe item, generate the AI draft, publish it, then buy it back in
   the marketplace below.
5. **Try-on** → upload any photo, pick a garment, then share to 閨蜜團 and simulate replies.
6. **Support** → the defect classifier reacts to the actual photo you upload (brightness, edge
   density, colour variance, dark-spot ratio).
7. **My profile** → the AI insights are computed from the seeded wardrobe/return history.

## Architecture

```
SmartMall/
├── server.js               # zero-dependency Node HTTP server: static hosting + REST API
├── data/
│   ├── products.json       # 40 products: bilingual copy, slots, fit profile, return rate
│   └── profile.json        # demo shopper: body data, wardrobe, orders, returns, searches
├── lib/                    # AI service layer — decoupled from web ops (per the proposal)
│   ├── store.js            # catalog + profile + currency + deterministic price history
│   ├── memory.js           # long-term profile, size tendency, wardrobe matching, insights
│   ├── assistant.js        # intent → retrieval → memory-aware bundles → explanation
│   ├── blindbox.js         # scenario slot plans, budget trimming, tiers, rationale
│   ├── priceAgent.js       # platform offers, coupons, negotiation transcript
│   ├── resale.js           # listing generation + marketplace store + eco accounting
│   ├── social.js           # private groups, polls, voting, verdicts
│   ├── returnPredict.js    # size advisor + return-risk model
│   ├── support.js          # guided return sessions + photo defect classification
│   ├── visualSearch.js     # CLIP-first ranking, colour + text fusion fallback
│   ├── forecast.js         # Prophet client with linear-regression fallback
│   ├── prophetClient.js    # HTTP client for the Prophet service
│   ├── analytics.js        # SQLite event store: search, exit-intent, coupons
│   ├── stores.js           # O2O: per-store stock, haversine distance, pickup
│   └── tryon.js            # garment metadata / synthesis seam
├── tools/
│   └── augment_catalog.py  # regenerates the bilingual/fit metadata in products.json
└── public/                 # vanilla-JS SPA (no framework, no build)
    ├── index.html
    ├── css/styles.css
    └── js/  (app.js router · i18n.js · ui.js · cart.js · chart.js · api.js · views/*)
```

### REST API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/products`, `/api/products/:id` | catalog (bilingual search via `?q=`) |
| GET | `/api/stores` · `/api/stores/stock/:id?lat=&lng=` · `/api/stores/one/:id` | store list, cross-store stock, distance-sorted |
| GET | `/api/forecast/:id?horizon=` · `/api/forecast/status` | Prophet forecast + advisory (+ service status) |
| GET | `/api/forecast-eval` | catalogue-wide holdout comparison of three models |
| POST | `/api/analytics/event` · GET `/api/analytics/summary?days=` | merchant dashboard metrics |
| POST | `/api/analytics/coupon` · `/api/analytics/coupon/apply` | exit-intent coupon issue / redeem |
| GET | `/api/widget/config?tenant=` | per-tenant branding for the embeddable widget |
| POST | `/api/assistant` | `{query, lang}` → memory-aware bundles |
| POST | `/api/visual-search` | `{colors[], query}` |
| POST | `/api/tryon` | `{productId}` |
| GET | `/api/blindbox/scenarios` · POST `/api/blindbox` | scenario kit generation |
| GET | `/api/price-agent/platforms` · POST `/api/price-agent` | comparison + negotiation |
| GET/POST | `/api/resale`, `/api/resale/draft`, `/api/resale/consignable`, `/api/resale/:id/buy` | consignment + marketplace |
| GET/POST | `/api/social/groups`, `/api/social/polls`, `/api/social/polls/:id/{simulate,vote}` | private voting |
| GET/PATCH | `/api/profile`, `/api/memory/insights` | long-term memory |
| GET | `/api/return-risk/:id?size=` · POST `/api/return-risk/cart` | size advisor |
| POST | `/api/support/{session,analyze,submit}` · GET `/api/support/{reasons,stats}` | smart returns |

## The visual search stack (implemented)

| Layer | Choice | Notes |
|---|---|---|
| Model | **`Marqo/marqo-fashionSigLIP`** (768-d) via `open_clip_torch` | 203M params, Apache 2.0. Chosen on measured recall, not on the vendor's benchmark — see below |
| Query normalisation | **zh → en fashion glossary** (`data/fashion-glossary.json`) | the highest-impact change in the pipeline; without it the fashion encoders are unusable for Chinese |
| Index | FAISS `IndexFlatIP`, 768-d, L2-normalised | exact cosine search — at 36–100k vectors a flat index is optimal; move to IVF/HNSW beyond that |
| Fusion | weighted average of the image and text unit vectors | the proposal's "unified query embedding"; weight is `TEXT_WEIGHT` (0.55) or per-request `textWeight` |
| Images | Myntra "Fashion Product Images" | 34/40 catalog items have a photo; the 6 that could not be matched faithfully keep an emoji placeholder rather than a misleading photo |

### Why the query is translated before it is embedded

Marqo's models are trained on **English** catalogue metadata. This site is Chinese-first, so the
language is not a detail — it is the whole problem. Measured on a 94-query bilingual set
(47 Chinese/English pairs, `tools/build_eval_set.py`, `tools/eval_retrieval.py`,
results in `data/eval/results.json`):

**Raw queries** — Recall@5 over 34 catalogue photos:

| Model | R@1 | R@5 | MRR | zh R@5 | en R@5 |
|---|---|---|---|---|---|
| ViT-B-32 / laion2b (previous) | 45.7 % | **84.0 %** | 0.637 | 70.2 % | 97.9 % |
| Marqo-FashionCLIP | 41.5 % | 78.7 % | 0.576 | 61.7 % | 95.7 % |
| Marqo-FashionSigLIP | 39.4 % | 58.5 % | 0.499 | **17.0 %** | **100.0 %** |

Two things jump out. First, **swapping to the fashion-tuned model made things worse**, contradicting
the vendor's "+57 % recall@1" claim — that number is measured on English text/image benchmarks and
does not transfer to a Chinese query set. Second, Marqo-FashionSigLIP is **perfect in English (100 %
Recall@5) and near-chance in Chinese (17 %, where random is ~15 %)**. A direct probe showed why: every
Chinese query produces the *same* text embedding (identical scores and identical rankings for
「滑雪外套」, 「滑雪護目鏡」 and 「真皮樂福鞋」), so the tokenizer is collapsing CJK input rather than
encoding it.

So the bottleneck is language alignment, not vision. Pushing Chinese through a small zh→en fashion
glossary before embedding:

**Translated queries**:

| Model | R@1 | R@5 | MRR | zh R@5 | gain vs raw |
|---|---|---|---|---|---|
| ViT-B-32 / laion2b | 58.5 % | 97.9 % | 0.764 | 97.9 % | +27.7 |
| Marqo-FashionCLIP | 64.9 % | 95.7 % | 0.781 | 95.7 % | +34.0 |
| **Marqo-FashionSigLIP** | **73.4 %** | **100.0 %** | **0.850** | 100.0 % | **+83.0** |

The shipped configuration is therefore **Marqo-FashionSigLIP + glossary**: Recall@1 goes from 45.7 %
to 73.4 % and Recall@5 from 84.0 % to 100.0 % versus the previous backbone. Difficulty breakdown in
translated mode: easy 100 %, medium 100 %, hard 100 %.

Caveat, stated plainly: the glossary overlaps with the catalogue vocabulary, so the translated
numbers are an **optimistic lexicon baseline**, not an upper bound — the human-paired English
queries (100 % for SigLIP) are the ceiling. A production system should replace the glossary with an
LLM translator and keep this harness to measure it.

Measured on this machine (RTX 4070, 12 GB): model load 3.1 s, **15 ms per image embedding**,
**5–9 ms per query**. `tools/check_fashion_models.py` and `tools/test_visual_e2e.py` reproduce those
numbers.

## The forecasting stack (implemented)

`ai-service/forecast_service.py` (port 8002) fits **Meta Prophet** per product on an
800-day daily price feed and returns a forecast, a buying advisory and a holdout
comparison. `lib/forecast.js` calls it and falls back to the original linear-trend model
when it is offline, so the page never breaks.

| Layer | Choice | Notes |
|---|---|---|
| Model | Prophet 1.5.0 (cmdstan backend) | per-product fit ≈ 0.3–0.5 s, cached after the first request |
| Seasonality | sale calendar as **explicit holiday regressors** | 雙十一, Black Friday, Cyber Monday, Christmas, New Year, Lunar New Year, summer sale, Mid-Autumn. A Fourier yearly term smears a one-day event across the month and *misses* the dip; holiday dummies nail it |
| Uncertainty | Prophet's own 80 % interval | drawn as a band on the chart; its width also drives the confidence score |
| Data | `data/price-history.json` — 40 products × 800 days = 32 000 observations | synthetic but structured: trend, weekend effect, per-product promo participation, noise |
| Evaluation | holdout of the last 30 days, three models | `tools/eval_forecast.py` → `data/forecast-eval.json` |

Catalogue-wide holdout results (40 products, last 30 days withheld):

| Model | MAE | RMSE | MAPE | median MAPE | wins |
|---|---|---|---|---|---|
| **Prophet** | **0.28** | **0.35** | **0.34 %** | 0.33 % | **38 / 40** |
| Linear trend | 1.10 | 1.17 | 1.25 % | 0.70 % | 0 |
| Naive (last price) | 0.39 | 0.47 | 0.50 % | 0.46 % | 2 |

⚠️ The price feed is synthetic and its sale calendar is known to the model, so the gap over
the linear baseline is an **upper bound** — real retail data is noisier. The honest claim is
"modelling the sale calendar beats ignoring it", not "0.34 % error on real data".

Because not every SKU joins every promotion (participation is a product trait), the
advisories are not uniform: right now **33 products advise waiting** for the 11 Nov drop and
**7 advise buying now**.

## The try-on stack (implemented)

`ai-service/tryon_service.py` (port 8003) runs **CatVTON's mask-free variant** on the local GPU and
returns a synthesised photo. `lib/tryon.js` calls it and falls back to the original colour-overlay
preview when the service is down or the product has no garment photo.

| Layer | Choice | Notes |
|---|---|---|
| Model | `zhengchong/CatVTON-MaskFree`, `mix-48k-1024` | ICLR 2025, arXiv 2407.15886; 899 M params |
| Pipeline | `CatVTONPix2PixPipeline` | from the official HF Space source, not the GitHub repo |
| Base | `timbrooks/instruct-pix2pix` | **8-channel** UNet; the inpainting base is 9-channel and will not load |
| Resolution | 768 × 1024, 30 steps, guidance 2.5 | configurable via `TRYON_*` env vars |
| Licence | CC BY-NC-SA 4.0 | non-commercial — fine for an FYP, a blocker for a product |

Measured on this machine (RTX 4070, 12 GB): model load 3.6 s, **21 s at 20 steps / 31 s at 30 steps**,
**peak 3.57 GiB VRAM**. `tools/test_catvton_p2p.py` and `tools/test_tryon_e2e.py` reproduce those
numbers.

### Why the mask-free variant

The repo's `CatVTONPipeline` needs an *agnostic mask* — the region of the photo to regenerate — which
upstream produces with DensePose + SCHP, i.e. **detectron2**, which is a poor fit on Windows. The
MaskFree checkpoints instead pair with `CatVTONPix2PixPipeline`, which simply concatenates the person
and garment latents along the width and needs **no mask at all**. That removed the entire
detectron2 / human-parsing dependency chain.

Two things cost real time to discover and are worth recording:

1. **Outfit Anyone cannot be the backend.** Its weights were never released — the GitHub repo is a
   client that calls the Hugging Face Space, and that Space only accepts *garment* uploads; the person
   is one of their preset models ([README](https://github.com/HumanAIGC/OutfitAnyone),
   [Space](https://huggingface.co/spaces/HumanAIGC/OutfitAnyone)). You cannot run it locally or put a
   customer's own photo through it.
2. **The base model must match the pipeline's channel count.** `CatVTONPix2PixPipeline` feeds an
   8-channel UNet; pointing it at the 9-channel SD1.5-inpainting base fails with
   `expected input to have 9 channels, but got 8`.

`uv` also silently replaced the CUDA build of PyTorch with a CPU wheel when installing `diffusers`
(`torch 2.10.0+cu128` → `2.14.1+cpu`); `uv pip uninstall torch` restores the inherited build. Check
`torch.cuda.is_available()` after any dependency install.

## The assistant (tool-calling agent)

The assistant is not a chatbot. It routes a question to **tools**, runs them, and composes an answer
that may only quote the facts those tools returned — so every price, stock count, size and sale date
is traceable to a call. This is what "can it actually ship" depends on.

```
query ──▶ router ──▶ plan of tool calls ──▶ tools ──▶ facts ──▶ composer ──▶ answer + citations
```

| Piece | File | Notes |
|---|---|---|
| Tools | `lib/agent/tools.js` | `search_products`, `check_store_stock`, `forecast_price`, `size_advice`, `build_outfit`, `recall_wardrobe`, `list_stores` |
| Router | `lib/agent/router.js` | deterministic intent + entity extraction (size, budget). This is the only piece an LLM would replace |
| Orchestrator | `lib/agent/index.js` | executes the plan, substitutes `$find.top` to chain tools, composes from facts |
| Fallback | `lib/assistant.js` | template assistant, used only if the agent throws |

**Grounding by construction.** Tools emit pre-formatted facts (`totalDisplay`, `onlineStock`,
`dropPct`, …) and the composer performs no arithmetic, so there is no path from prose to an invented
number. Chinese-aware search is required because Chinese has no spaces: queries are tokenised into
CJK bigrams, otherwise a whole sentence collapses to one unmatchable term.

Evaluation (`tools/eval_assistant.py`, 15 bilingual questions, `data/eval/assistant.json`):

| Metric | Result | Meaning |
|---|---|---|
| Tool accuracy | **15/15** | the right tool was chosen for the question |
| Groundedness | **15/15** | every number in the answer appears in a tool fact |
| Containment | **15/15** | answered without falling back to the template path |

The honest caveat: 15 hand-written questions is a smoke test, not a benchmark. The router is rule
based, so an unfamiliar phrasing misses — the fix is an LLM router behind the same tool contract,
which is why the tools and composer are kept separate from it.

### The optional LLM router

`lib/agent/llmRouter.js` puts a local model in front of the deterministic router. **It replaces one
thing only: intent classification.** The model never sees the catalogue, never produces a price, a
size, a stock count or a tool argument, and never writes the answer.

```
question ──▶ LLM classifies intents ─┐
                                     ├─▶ buildPlan() ──▶ tools ──▶ facts ──▶ composer ──▶ answer
            rules classify intents ──┘        (shared)                          (unchanged)
```

Both routers call the same `buildPlan()` and the same `extractEntities()`, so money and size stay
deterministic and the comparison between them measures the classifier rather than two independently
written planners. Off by default; when it is off, slow, unreachable, or returns anything invalid,
the rule router answers exactly as before.

| Variable | Default | Meaning |
|---|---|---|
| `ASSISTANT_LLM` | unset (off) | set to `1` to enable |
| `LLM_URL` | `http://127.0.0.1:11434/v1` | any OpenAI-compatible base (Ollama works) |
| `LLM_MODEL` | `qwen2.5:3b-instruct` | |
| `LLM_TIMEOUT_MS` | `2500` | exceed it and the rules take over |

Why a small model is enough: classification is a few dozen output tokens, so the model can stay
small — and it has to, because it shares one 12 GB card with CatVTON. Anything that had to *write*
the answer would need a model that does not fit.

```bash
ollama pull qwen2.5:3b-instruct          # 1.9 GB

ASSISTANT_LLM=1 LLM_MODEL=qwen2.5:3b-instruct node server.js
curl -s localhost:3000/api/assistant/llm # is the model reachable?
python tools/eval_router.py              # both routers, same 15 questions
```

**Measured on an RTX 4070 (12 GB).** Both routers scored on the same 15 labelled questions
(`data/eval/router-3b.json`, `router-7b.json`):

| Router | Intent acc. | Tool acc. | Latency | VRAM (all services loaded) | Try-on alongside |
|---|---|---|---|---|---|
| rules (no model) | 93.3% | **100%** | 0.1 ms | — | yes, 22.5 s |
| + qwen2.5:3b (1.9 GB) | 93.3% | 93.3% | 135 ms | **7541 MiB** | **yes, 22.5 s** |
| + qwen2.5:7b (4.7 GB) | **100%** | **100%** | 158 ms | **11565 MiB** | **no — times out** |

Read that table carefully, because it is the opposite of the usual "add an LLM and everything
improves" story:

- **The 3B ties the rules on intent** and is *worse* on tool selection. It fixes the one question the
  rules miss (`門市地址喺邊` → `stores`) and misses one the rules get (`邊間門市有白色波鞋` →
  `stores` instead of `availability`). Net: no gain, 135 ms slower.
- **The 7B is genuinely better** — 100% on both — and **cannot be used with the try-on**: with both
  loaded the GPU sits at 11565 of 12282 MiB and generation no longer finishes inside the client
  timeout. It loads; it cannot work.
- **Prompt tuning mattered more than model size.** The first 3B prompt scored 86.7%; adding explicit
  Cantonese cues and the rule "a budget alone is not a `price_timing` question" took it to 93.3%
  with no model change.

The fair caveat: the rule router was *developed* against these 15 questions, so its 93.3% is
optimistic — the set is a dev set as much as a test set. The LLM saw none of them. A larger held-out
set is the next step, and `tools/eval_router.py` is what would run it.

Practical conclusion: keep the rules as the default. Offer the 3B as an opt-in for phrasings the
rules miss, and treat the 7B as a "try-on disabled" mode — the accuracy is real, the coexistence is
not.

Tests that need no model (`tools/mock_llm_server.py` plays every failure mode):

```bash
python tools/mock_llm_server.py --port 11434 &
node tools/test_router_llm.mjs 11434               # 13 checks
```

## The outfit score, and whether it is biased

`#/aesthetic` scores a photo of today's outfit out of 100 in three parts:

| Part | Weight | Measured against |
|---|---|---|
| Style match | 0.65 | the centroid of the shopper's **own wardrobe** |
| Completeness | 0.25 | the slots that shopper actually wears (learned from their wardrobe) |
| Colour harmony | 0.10 | whether the hues form a scheme |

**The honest answer to "does this mark down alternative styles?" is: it did.** The
original colour rule was

```python
if distinctHues > 3:      score -= (n - 3) * 16
if neutralShare < 0.12:   score -= 12
```

which is not a measure of quality, it is a measure of minimalism. Heavy metal,
shamazhite and harajuku looks lose points by construction.

Measuring it (`python tools/eval_aesthetic_bias.py`) turned up two further bugs that
made it worse:

- **`V > 0.95` was treated as neutral**, so every fully bright colour was discarded
  before its hue was ever counted. A neon pink has `max(r,g,b) = 255`, therefore
  `V = 1.0`, therefore it vanished. Black-and-red scored fine; a neon family did not.
- **Hue cluster centres were averaged arithmetically**, so a cluster straddling red
  (330° and 0°) averaged to 165° — the opposite hue. One outfit read as "scattered"
  for a rounding reason.

Both are fixed, and the rule now judges **structure rather than restraint**:

| Style (same garments, colour only differs) | Hues | Scheme | Old score | New score |
|---|---|---|---|---|
| minimal, neutrals | 0 | neutral | 97.3 | 100 |
| streetwear, dark + 1 accent | 1 | monochrome | 100 | 100 |
| heavy metal, black + dark red | 2 | two-tone | 100 | **95** |
| maximalist, **coherent** neon family | 2 | two-tone | 100 | **95** |
| maximalist, **scattered** random hues | 3 | scattered | 100 | **20** |
| formal, navy + grey + white | 1 | monochrome | 100 | 100 |

Two things to read out of that table, and the second one matters more:

1. Every deliberate style now lands at 95–100; only a palette with no scheme is
   marked down. A neon outfit built on one colour family scores the same as a beige
   one.
2. **The old rule was not biased so much as blind.** It kept every style within 2.7
   points of every other — its hue threshold simply never fired, because quantising
   an outfit to 8 colours rarely leaves more than three. The bias was real in the
   code and almost absent in the effect, which is its own kind of defect: a signal
   that costs 20 % of the score and distinguishes nothing.

What remains is stated rather than hidden: preferring a coherent palette over a
chaotic one is still a value judgement, so its weight was cut from 20 % to 10 % and
the style term raised to 65 %. If you disagree with the judgement, `the weight is
one number in `ai-service/visual_search_service.py``.

Completeness changed too: it used to require top + bottom + shoes unconditionally.
It now reads which categories the shopper actually buys and requires only those, and
a dress satisfies both top and bottom — otherwise a one-piece garment would be marked
down for not being a separate top and bottom.

## Cold start: the welcome survey and real search history

Nothing can be personalised before the first click, so `#/welcome` asks ten questions
once — categories, styles, budget, occasions, colours to avoid, three pairwise picks
and materials. It is **offered** on the home page, never forced: a shopper can browse
first and answer later, and the banner disappears once it is done.

The answers go to `data/user-state.json`, not `data/profile.json`. That distinction
matters: `store.js` mutates the profile in memory but never writes it, so anything that
must survive a restart lives in `user-state.json` instead.

The survey is not just stored — it reorders results. `search_products` multiplies its
score by `1 + 0.25 × affinity`, computed from the chosen categories, styles and colours
(minus anything in "avoid"). Measured on the probe query `black`:

```
no preference      -> p034  p009  p029
Electronics        -> p029  p034  p009     (the earbuds move to first)
Apparel            -> p009  p034  p029
```

Searches are recorded from all three entry points — the catalogue (`/api/products?q=`),
the assistant, and visual search — into one list, so "what people look for" is a single
answer rather than three. An image-only search is recorded as `(image)` rather than
inventing a text query. The 我的 page shows the recent queries and the ones that keep
coming back, and each is clickable.

```bash
curl -s localhost:3000/api/history          # recent + top terms + counts by kind
curl -s localhost:3000/api/onboarding       # what the shopper chose
python tools/test_userstate_e2e.py          # 24 checks
```

The endpoint sanitises what it accepts — lists truncated, non-strings dropped, budget
clamped, incomplete pairs discarded — so a malformed request cannot write arbitrary
structure into the state file. The test asserts all four.

### Learning from clicks, not just answers

The survey records what a shopper *claims* to like. `product_view` and `add_to_cart`
events record what they actually open, and those already land in the analytics SQLite,
so `lib/engagement.js` derives a **category-level** attention score from them:

```
attention(category) = views + 3 × add-to-cart        (last 30 days)
boost               = 1 + 0.20 × tanh(attention / 8)
```

Category level rather than product level on purpose: one extra view of one jacket is
noise, while "this shopper keeps opening outerwear" is a pattern — and per-product
boosting starts a rich-get-richer loop where the top item is clicked because it is on
top.

The curve is bounded and monotonic: no amount of clicking can exceed +20 %, and a
product with no history is untouched, so a search never drifts far from what the query
asked for. `tools/test_engagement.mjs` asserts exactly those three properties.

Three nudges now multiply the search score, and each is separately attributable:

| Signal | Source | Effect |
|---|---|---|
| `preferenceBoost` | pairwise survey answers | per product, ±35 % |
| `subcategoryAffinity` | welcome survey | category / style / colour, up to +25 % |
| `attentionBoost` | views and carts | per category, up to +20 % |

`GET /api/engagement` exposes the result, and the 我的 page shows it plainly —
"👀 你最近常看 Apparel · 44" with a note that those categories get a small nudge. That
matters: a personalisation the shopper cannot see is indistinguishable from a bug.

### The A/B experiment: does a personalised score convert better?

The professor's question was whether the score *changes behaviour*, not whether it is
accurate. That needs two numbers and a way to compare them, so the aesthetic endpoint
returns both:

| Number | Measured against | Weighted from |
|---|---|---|
| `score` | the shopper's **own wardrobe** | style 0.65 / coverage 0.25 / palette 0.10 |
| `publicScore` | a **generic taste anchor** ("a stylish outfit", averaged over three prompts) | same weights, generic style term |

Each browser is assigned one arm, sticky, equal thirds (`js/experiment.js`):

- **personal** — sees the wardrobe-relative score (the current behaviour)
- **public** — sees the general-taste score, labelled 大衆審美
- **both** — sees the personal number large and the public one beneath it

The dependent variable is **click-through after seeing a score**, from a "browse using
this score" button. That is a proxy and it is labelled one: a demo cannot collect real
orders, but a view followed by a click is measurable per visitor and reaches a usable
sample far faster than checkout ever would.

```bash
curl -s localhost:3000/api/experiment
python tools/test_experiment_e2e.py     # 18 checks
```

Sample currently: **0 views per arm**, so the summary says so rather than printing a
percentage:

```
personal: {"views": 0, "actions": 0, "ctr": null}
note: "Under 30 views per arm — the comparison is not yet meaningful."
```

That refusal is deliberate. `conclusive` only becomes true at 30 views per arm, and even
then the note says the metric is a proxy rather than revenue. A percentage over four
visitors is worse than no percentage, because it invites a conclusion the data cannot
support.

To see it work, open `#/aesthetic`, upload a photo, press "browse using this score", and
re-read `/api/experiment`.

## Accounts (optional)

Browsing works signed out. An account only decides **whose** preferences and history
are recorded, so two people sharing a demo do not end up with one blended profile.

```
#/login   register or sign in        GET  /api/auth/me
                                    POST /api/auth/register | /login | /logout
```

What makes it defensible rather than a toy, with no npm dependencies:

| Concern | How |
|---|---|
| Password storage | `scrypt` with a per-user 16-byte salt, 64-byte key |
| Comparison | `timingSafeEqual`, so a wrong password cannot be timed |
| Session | 32 random bytes, stored server-side — a cookie cannot be forged |
| Cookie | `HttpOnly` (script cannot read it), `SameSite=Lax` (no cross-site POST) |
| Enumeration | same `invalid_credentials` for unknown address and wrong password |
| Brute force | 5 failures per address, 50 per IP, per 5 minutes |

`user-state.json` is partitioned by account (`guest` is a real bucket, so signed-out
browsing still records history). The auth test asserts that a second account sees none
of the first's onboarding answers or searches.

**Deliberately not included:** email verification, password reset, OAuth, and the
cookie's `Secure` flag — that last one because this demo runs over `http` on localhost
and on a Tailscale address, so setting it would silently break the only deployments it
has. Put TLS in front and add it.

`python tools/test_auth_e2e.py` — 25 checks, including that the password never appears
in `users.json`.

## Collecting the experiment data

`EXPERIMENT.md` is the operational guide: how many testers, how to avoid the five
mistakes that invalidate the numbers, the sample-size table, a reporting template, and
how to reset between rounds. Short version:

- one browser per tester (the arm is sticky in `localStorage`)
- ~15–25 people, target 30–50 views per arm
- do not tell them which button to press
- decide the sample size **before** looking at the result

## Swapping in real AI

The proposal's key idea — *decoupling standard web operations from high-dimensional AI
inference services* — is encoded directly in the code. Every module is a stable seam with a
fixed input/output contract; only the internals change:

- **Visual search** ✅ *done* — CLIP + FAISS in `ai-service/`, behind `lib/visualSearch.js`.
- **Assistant / blind box** ✅ *mostly done* — the assistant is now a tool-calling agent
  (`lib/agent/`) whose answers may only quote tool facts. What remains is replacing the rule-based
  router with an LLM call; the tools and composer do not change.
- **Forecasting** ✅ *done* — Meta Prophet in `ai-service/forecast_service.py`, behind
  `lib/forecast.js` (linear trend retained as the offline fallback). See below.
- **Price agent** → replace simulated listings with licensed marketplace/affiliate APIs and
  the scripted dialogue with an LLM negotiation policy.
- **Resale** → generate the copy with an LLM and price it with a demand model.
- **Return prediction** → train a gradient-boosted / neural model on order-level data; the
  `{riskScore, recommendedSize, factors, advice}` output is unchanged.
- **Support vision** → send the photo to a defect-classification CNN instead of the
  client-extracted feature vector.
- **Try-on** → swap the canvas overlay for a diffusion model (VITON-HD / inpainting).

## Notes and limitations

- Product imagery is emoji + colour gradients; all AI behaviour is a deterministic simulation
  so the demo runs fully offline with no API keys.
- `data/profile.json` is a seeded demo shopper (male, Hong Kong, size M). Prices are stored in
  USD and converted for display, which is why a `HK$2,000` budget is ~US$256.
- Listings, polls and return forms are held in memory and reset when the server restarts.
- Compliance: the price agent only reads publicly listed prices and negotiates through
  marketplace-sanctioned channels; the voting module is friends-only, expiring and unindexed.
