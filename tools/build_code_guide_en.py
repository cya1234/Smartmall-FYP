"""Build the English edition of the one-hour code-reading guide.

Reuses the layout helpers from the Chinese builder so both editions look the same.

Run:  <bundled python> tools/build_code_guide_en.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_code_guide as Z                       # noqa: E402
from docx import Document                          # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH      # noqa: E402
from docx.shared import Pt, RGBColor               # noqa: E402

OUT = os.path.join(Z.ROOT, "Code Guide - SmartMall.docx")

h1, h2, body, bullet = Z.h1, Z.h2, Z.body, Z.bullet
code, table, setup = Z.code, Z.table, Z.setup
ACCENT = Z.ACCENT


def callout(doc, text, bold_lead="Key point: "):
    """The Chinese builder defaults the label to 重點, so override it here."""
    return Z.callout(doc, text, bold_lead)


def main():
    doc = Document()
    setup(doc)

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("SmartMall — Code Guide")
    r.bold = True
    r.font.size = Pt(24)
    r.font.color.rgb = ACCENT
    s = doc.add_paragraph()
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rs = s.add_run("One hour to understand what was built, how it works, and what each file does")
    rs.font.size = Pt(13)
    rs.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
    doc.add_paragraph()

    # -------------------------------------------------------- 0 how to read
    h1(doc, "0  How to read this")
    body(doc, "This guide assumes you have one hour and need to answer three questions afterwards: "
              "what does the system do, how are the difficult parts actually implemented, and where "
              "do I edit something. It summarises about 6,500 lines of code, so you do not need to "
              "open the source first.")
    table(doc, ["Time", "Route", "What to read"],
          [["15 min", "Skeleton only", "Section 1 (what it is) + Section 2 (the file map)"],
           ["35 min", "Understand the four AI capabilities", "Sections 3.1 to 3.4, plus the problem table in 4.1"],
           ["60 min", "Everything", "All of it, including Section 4 (difficulties) and Section 7 (where to change things)"]],
          widths=[2.0, 4.2, 9.4])
    callout(doc, "The repository is roughly 6,500 lines, but only about 900 of them carry the "
                 "technical substance: the model calls in the three Python services, and the fact "
                 "layer in the assistant. The rest is storefront, data and interface.")

    # -------------------------------------------------------- 1 what
    h1(doc, "1  What the system is")

    h2(doc, "1.1  In one sentence")
    body(doc, "An AI e-commerce system for small Hong Kong apparel retailers: describe an occasion and "
              "get a complete outfit, upload a photo and find the same garment, know whether the price "
              "will drop before you buy, see which store has it when the site is sold out, and be "
              "warned that a size probably will not fit.")

    h2(doc, "1.2  Why four services")
    body(doc, "This is the most important architectural decision in the project. Four services start "
              "independently, and three of them load a machine-learning model.")
    table(doc, ["Service", "Port", "Technology", "Load time", "If it is off"],
          [["Web", "3000", "Node.js built-in modules", "instant", "(this is the product)"],
           ["Visual search", "8001", "Marqo-FashionSigLIP + FAISS", "~5 s", "colour heuristic"],
           ["Price forecast", "8002", "Meta Prophet", "~2 s", "linear trend"],
           ["Virtual try-on", "8003", "CatVTON (GPU)", "~15 s", "colour overlay preview"]],
          widths=[2.8, 1.2, 6.2, 2.2, 4.2])
    callout(doc, "Switch any AI service off and the site still works. That is a design goal, not a "
                 "coincidence — every capability has an explicit fallback. It is also why a failed "
                 "model load during a demo is survivable.")

    h2(doc, "1.3  Data flow of one search")
    body(doc, "Taking \"upload a photo and find the same garment\" as the example, data passes through "
              "four layers:")
    code(doc, """browser  ──POST /api/visual-search──▶  server.js          (routing)
                                            │
                                            ▼
                                  lib/visualSearch.js          (decide: CLIP or colour)
                                            │
                                            ▼ HTTP
                          ai-service/visual_search_service.py  (the model)
                                            │
                        1. Chinese query  → English fashion terms (glossary)
                        2. image + text   → CLIP vectors, weighted fusion
                        3. FAISS          → inner-product search
                                            │
                                            ▼ ids + similarities
                            lib/clipClient.js                  (score → 0-100 %)
                                            │
                                            ▼
                                  productCard renders it""")
    body(doc, "The division is: Node does routing and I/O only, lib decides which model to use, "
              "Python runs the model, and the front end only draws.")

    # -------------------------------------------------------- 2 file map
    h1(doc, "2  The file map: what every file does")

    h2(doc, "2.1  Backend core")
    table(doc, ["File", "Lines", "Responsibility", "When you read it"],
          [["server.js", "472", "HTTP routing, static files, 20+ API endpoints", "adding an API"],
           ["lib/store.js", "144", "Catalogue, profile, currency conversion", "changing product shape"],
           ["lib/analytics.js", "274", "SQLite event store, coupons, dashboard metrics", "changing metrics"],
           ["lib/memory.js", "215", "Wardrobe, return history, long-term preferences", "changing memory"],
           ["lib/blindbox.js", "421", "Assembles a full kit from an occasion and budget", "changing Style Box"],
           ["lib/assistant.js", "503", "Old template assistant (now a fallback)", "only runs if the agent dies"]],
          widths=[3.4, 1.1, 7.4, 4.6])

    h2(doc, "2.2  The four AI capabilities")
    table(doc, ["Capability", "Node side", "Python side", "Model"],
          [["Visual search", "visualSearch.js (120)\nclipClient.js (54)", "visual_search_service.py (257)", "Marqo-FashionSigLIP"],
           ["Price forecast", "forecast.js (142)\nprophetClient.js (41)", "forecast_service.py (339)", "Meta Prophet"],
           ["Virtual try-on", "tryon.js (111)", "tryon_service.py (198)", "CatVTON MaskFree"],
           ["Assistant", "agent/tools.js (244)\nagent/router.js (121)\nagent/index.js (230)", "(none)", "rule-based router + 7 tools"]],
          widths=[2.6, 4.6, 4.6, 4.2])

    h2(doc, "2.3  The remaining modules")
    table(doc, ["File", "Lines", "What it does"],
          [["lib/stores.js", "105", "Eight stores, cross-store stock, haversine distance"],
           ["lib/returnPredict.js", "133", "Return-risk prediction and size recommendation"],
           ["lib/support.js", "242", "Returns flow, defect classification, return form"],
           ["lib/priceAgent.js", "173", "Seven-marketplace comparison and negotiation (simulated)"],
           ["lib/resale.js", "214", "Second-hand listing copy and pricing"],
           ["lib/social.js", "193", "Private friend voting"],
           ["lib/clipClient.js", "54", "HTTP client for the CLIP service plus score calibration"]],
          widths=[3.6, 1.2, 11.8])

    h2(doc, "2.4  Front end")
    table(doc, ["File", "Lines", "What it does"],
          [["public/js/app.js", "131", "SPA routing, header search, boot"],
           ["public/js/i18n.js", "630", "The whole bilingual dictionary (mostly strings)"],
           ["public/js/views/*.js", "2,507 (15 files)", "One file per page"],
           ["public/js/widget.js", "245", "Embeddable panel, runs inside the iframe"],
           ["public/js/chart.js", "88", "Hand-written SVG line chart with a confidence band"],
           ["public/js/exitIntent.js", "154", "Exit-intent detection and coupon issue"],
           ["public/css/styles.css", "791", "All styling; the dark theme lives in :root"]],
          widths=[4.4, 2.6, 9.6])
    callout(doc, "i18n.js is 630 lines but almost entirely strings, not logic. Skip the whole file "
                 "when reading code.", bold_lead="Note: ")

    h2(doc, "2.5  Tools and tests")
    body(doc, "tools/ holds 36 files in three groups:")
    bullet(doc, "Evaluation: eval_retrieval.py, eval_forecast.py, eval_assistant.py — they produce the "
                "three tables in the report")
    bullet(doc, "Tests: seven suites, 135 checks in total")
    bullet(doc, "Generators: build_price_history.py, prepare_catvton_base.py, build_interim_report.py — "
                "they produce data and documents")

    # -------------------------------------------------------- 3 deep dives
    h1(doc, "3  Five core technologies, and how they actually work")

    h2(doc, "3.1  Visual search: the real finding was that Chinese was never encoded")
    body(doc, "The intuitive move is to adopt a stronger fashion model. Measurement showed that this "
              "makes things worse.")
    body(doc, "We first built a 94-query bilingual set (47 Chinese/English pairs) and compared three "
              "models:")
    table(doc, ["Model", "Recall@1", "Recall@5", "Chinese R@5", "English R@5"],
          [["Original CLIP (ViT-B-32)", "45.7%", "84.0%", "70.2%", "97.9%"],
           ["Marqo-FashionCLIP", "41.5%", "78.7%", "61.7%", "95.7%"],
           ["Marqo-FashionSigLIP", "39.4%", "58.5%", "17.0%", "100.0%"]],
          widths=[5.4, 2.4, 2.4, 2.4, 2.4])
    body(doc, "Three completely different Chinese queries (ski jacket, ski goggles, leather loafers) "
              "produced identical embeddings and identical rankings. The tokenizer collapses CJK input "
              "into one sequence — it is not being read at all. The same model scores 100% in English.")
    body(doc, "So the fix was not a new model. It was translating the query into English fashion "
              "terminology before encoding:")
    code(doc, """# ai-service/visual_search_service.py
def translate_query(text):
    # longest-match substitution over a 120-term glossary
    # "滑雪外套" -> "ski jacket";  "亞麻" -> "linen"
    ...
    return translated or text

def encode_text(text):
    text = translate_query(text)          # <- the one line that mattered
    tok = _state["tokenizer"]([text]).to(_state["device"])
    f = _state["model"].encode_text(tok)
    return f / f.norm(dim=-1, keepdim=True)""")
    body(doc, "With that line: Recall@1 45.7% to 73.4%, Recall@5 84.0% to 100.0%.")
    callout(doc, "This is where the contribution sits: the vendor's claimed +57% does not hold on this "
                 "Chinese query set, and the real bottleneck is language alignment rather than vision.")

    h2(doc, "3.2  Price forecasting: treat the sale calendar as holiday regressors")
    body(doc, "Prophet's default yearly seasonality is a Fourier series, which smears a one-day "
              "promotion across a whole month. For 11 November it predicted a 4.2% dip against an "
              "actual 18%.")
    body(doc, "The fix is to declare each sale date as an explicit holiday so it gets its own "
              "coefficient:")
    code(doc, """# ai-service/forecast_service.py
SALES = [
    ("double11",    "11-11", 2, 1, "Double 11"),
    ("black-friday","11-27", 1, 3, "Black Friday"),
    ("christmas",   "12-25", 3, 2, "Christmas"),
    ...
]
# each day becomes a dummy regressor in Prophet
rows.append({"holiday": name, "ds": pd.Timestamp(f"{y}-{md}"),
             "lower_window": -lo, "upper_window": hi})

m = Prophet(holidays=pd.DataFrame(rows), ...)""")
    body(doc, "Result: across 40 products under a 30-day holdout, MAE 0.28 and MAPE 0.34%, beating a "
              "linear baseline (1.25%) and a naive one (0.50%), winning 38 of 40 products.")
    body(doc, "Honest limitation: the price series is synthetic and the sale dates are known to the "
              "model, so this is an upper bound. The defensible claim is that modelling the sale "
              "calendar beats ignoring it, not that the error is 0.34% on real data.")

    h2(doc, "3.3  Virtual try-on: three traps")
    body(doc, "Trap one: the best-known model, Outfit Anyone, has never released its weights, and its "
              "public demo accepts garment images only with preset people. It cannot put a customer's "
              "own photo on a product. We used CatVTON (ICLR 2025) instead.")
    body(doc, "Trap two: CatVTON's GitHub repository needs an agnostic mask, which upstream produces "
              "with detectron2 — painful on Windows. The answer is the CatVTONPix2PixPipeline from the "
              "Hugging Face Space source, which concatenates the person and garment latents and needs "
              "no mask at all.")
    body(doc, "Also mind the base model's channel count: the pix2pix pipeline needs 8 channels "
              "(instruct-pix2pix). Pointing it at SD-inpainting (9 channels) fails with "
              "expected 9 channels, but got 8.")
    body(doc, "Trap three is the one a user actually hit: the face was cut off. The pipeline's "
              "resize_and_crop centre-crops to 3:4, so a portrait phone photo loses the same amount "
              "from the top and the bottom — and the top is the head. The fix is to pad before "
              "inference:")
    code(doc, """# ai-service/tryon_service.py
def fit_to_target(img, tw=WIDTH, th=HEIGHT):
    # pad to 3:4 first, so the pipeline's crop becomes a no-op
    if w / h < target:                    # too tall -> pad the sides
        new_w, new_h = int(round(h * target)), h
    ...
    backdrop = backdrop.filter(ImageFilter.GaussianBlur(28))   # blurred backdrop
    backdrop.paste(img, ((new_w - w) // 2, (new_h - h) // 2))  # person centred
    return backdrop""")
    body(doc, "Performance: 768x1024, about 21 s at 20 steps, 3.57 GiB peak memory on an RTX 4070 "
              "(12 GB).")

    h2(doc, "3.4  The assistant: making hallucination structurally impossible")
    body(doc, "The usual approach asks a language model to answer product questions, and it invents "
              "prices. Here the model only chooses a tool and phrases the result; every number comes "
              "from a tool call:")
    code(doc, """question -> route (rules) -> plan -> execute -> facts -> compose -> answer

tools return already-formatted numbers:
  facts.push({ label: 'totalDisplay', value: 'HK$889' })
  facts.push({ label: 'onlineStock',  value: '8' })
  facts.push({ label: 'dropPct',      value: '11.6' })

the composer only reads those facts and does no arithmetic at all.
-> there is no path from prose to an invented number.""")
    body(doc, "Seven tools: search_products, check_store_stock, forecast_price, size_advice, "
              "build_outfit, recall_wardrobe, list_stores.")
    body(doc, "Chaining uses one placeholder: routing emits search_products first, then substitutes "
              "the top id into the next tool's $find.top.")
    code(doc, """// lib/agent/index.js
if (params.productId === '$find.top') {
  if (!findTopId) { /* skip rather than guess */ }
  params.productId = findTopId;
}""")
    body(doc, "Evaluation: 15 bilingual questions, 15/15 tool selection, 15/15 grounding, "
              "15/15 containment.")

    h2(doc, "3.5  Merchant dashboard: Node's built-in SQLite, zero dependencies")
    body(doc, "No npm package; node:sqlite directly. Two tables:")
    code(doc, """// lib/analytics.js
CREATE TABLE events (
  id INTEGER PRIMARY KEY, tenant TEXT, session TEXT,
  type TEXT, label TEXT, value REAL, meta TEXT, createdAt TEXT
);
CREATE TABLE coupons (
  code TEXT PRIMARY KEY, tenant TEXT, discountPct REAL,
  status TEXT, issuedAt TEXT, appliedAt TEXT
);""")
    body(doc, "Every dashboard metric is one SQL aggregate: searches, sessions, retention (claimed "
              "over shown) and conversion. The database seeds seven days of demo history on first "
              "boot so the dashboard is never empty.")

    # -------------------------------------------------------- 4 difficulties
    h1(doc, "4  Difficulties, and how they were solved")
    body(doc, "This section records where the work actually got stuck. Most of it was not the model "
              "being insufficient — it was environment, data shape and wrong assumptions. Read the "
              "table first, then the three lessons in 4.2.")

    h2(doc, "4.1  The full list")
    table(doc, ["Problem", "Symptom", "Root cause", "Fix (file)"],
          [["pip install hung", "628 s of CPU, zero downloads",
            "the sandbox forbids writes outside the workspace",
            "workspace venv + uv (.venv/)"],
           ["CUDA torch replaced", "torch.cuda.is_available() = False",
            "the installer resolved a CPU wheel over 2.10.0+cu128",
            "uv pip uninstall torch; check after every install (happened twice)"],
           ["Chinese retrieval nearly dead", "Chinese R@5 17% (random ≈ 15%)",
            "the tokenizer collapses CJK into one sequence; three queries gave the same vector",
            "zh→en fashion glossary (data/fashion-glossary.json)"],
           ["11 November not predicted", "forecast dipped 4.2% against an actual 18%",
            "Prophet's Fourier yearly term smears a one-day promotion",
            "explicit holidays (SALES in forecast_service.py)"],
           ["Prophet lost to the naive baseline", "MAPE 0.37% → 0.61%",
            "promotional participation was randomised per year, so the effect flipped annually",
            "make participation a product trait (build_price_history.py)"],
           ["Every product gave the same advice", "all 40 said \"wait for the drop\"",
            "one shared sale calendar for the whole catalogue",
            "per-product participation and discount depth"],
           ["Try-on model unusable", "cannot upload a person",
            "Outfit Anyone never released weights; its demo accepts garments only",
            "switched to CatVTON (ICLR 2025)"],
           ["CatVTON would not install", "import failure / detectron2 missing",
            "the GitHub pipeline needs an agnostic mask",
            "CatVTONPix2PixPipeline from the HF Space source (no mask)"],
           ["Channel count mismatch", "expected 9 channels, but got 8",
            "the pix2pix pipeline needs an 8-channel base, not SD-inpainting",
            "timbrooks/instruct-pix2pix"],
           ["fp16 weights not found", "diffusion_pytorch_model.safetensors missing",
            "the pipeline loads without variant=\"fp16\" but only fp16 files were downloaded",
            "build a local snapshot with standard names (hard links, no extra disk)"],
           ["Try-on cut off the face", "no face / top of head cropped",
            "resize_and_crop centre-crops to 3:4 on a taller portrait",
            "pad before inference (fit_to_target in tryon_service.py)"],
           ["Style Box picked the wrong category", "a denim jacket for a ski trip",
            "it took the cheapest option with no relevance gate",
            "score ≥ max(2.5, top×0.5) gate (blindbox.js)"],
           ["Defect classifier always said \"faded\"", "every photo classified as fading",
            "absolute thresholds do not survive different lighting",
            "compare against the excess over a clean photo (support.js)"],
           ["Assistant could not read Chinese", "the whole sentence became one token, always 0 results",
            "Chinese has no spaces, so whitespace tokenisation fails",
            "CJK bigram tokenisation (lib/agent/tools.js)"],
           ["Assistant silently lost memory", "a regression test failed: the wardrobe was gone",
            "rewriting as an agent dropped the old behaviour",
            "added recall_wardrobe (tools.js + index.js)"],
           ["Answers contained \"ungrounded\" numbers", "HK$889 flagged as not a fact",
            "the composer did the currency conversion itself (×7.8)",
            "move the conversion into the tool; emit formatted facts only"],
           ["Slide text invisible", "dark text on a dark template",
            "the source theme's palette was kept",
            "invert to light text with yellow highlights"],
           ["English deck shouted", "RESULT 1: IMAGE SEARCH",
            "the template title style sets cap=\"all\"; Chinese has no case so it never showed",
            "set cap=\"none\" on every run"],
           ["Model weights would break the push", "git push fails",
            "data/models was 4 GB and not ignored",
            "add data/models/ and *.safetensors to .gitignore"]],
          widths=[3.4, 3.6, 5.0, 5.2], size=8.2)

    h2(doc, "4.2  Three lessons worth keeping")

    body(doc, "① The symptom shows up in one place; the cause usually lives in another.")
    body(doc, "\"Chinese search is bad\" looks like a model problem, yet a stronger model made it "
              "worse (84% to 58.5%). The real cause needed a probe to see:")
    code(doc, """# three completely different queries, the same vector
for q in ['滑雪外套', '滑雪護目鏡', '真皮樂福鞋']:
    print(model.encode_text(q))     # essentially identical

# while the same model scores 100% in English
print(model.encode_text('ski jacket'))""")
    body(doc, "Without that probe, weeks go into swapping models. The lesson: confirm the input is "
              "being read correctly before discussing model quality.")

    body(doc, "② Environment problems cost more time than code problems.")
    body(doc, "The same thing happened twice: installing open_clip and again installing diffusers, "
              "the package manager silently replaced the CUDA build of PyTorch with a CPU wheel. The "
              "code was fine; the whole inference layer became slow or failed outright.")
    code(doc, """.venv\\Scripts\\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
# 2.14.1+cpu False        <- broken
# 2.10.0+cu128 True       <- fixed

# the repair
.venv\\Scripts\\python.exe -m pip uninstall torch torchvision""")
    callout(doc, "Now every install is followed by that one-line check. It is written into SETUP.md.")

    body(doc, "③ Regression tests catch the things you thought did not matter.")
    body(doc, "After rewriting the assistant as a tool-calling agent, every new feature passed but an "
              "old regression test failed — it expected \"built around the linen shirt you bought "
              "three months ago\". That was one of the project's differentiators, dropped silently "
              "during the rewrite.")
    body(doc, "The fix was not to delete the test but to make memory a tool (recall_wardrobe) so the "
              "new architecture could still use it. The lesson: when a test fails, first ask whether "
              "a feature was really lost, and only then whether the test is out of date.")

    body(doc, "One limitation could not be solved and is recorded honestly: this machine cannot start "
              "headless Chrome (the sandbox blocks crashpad), so no page of the site was ever visually "
              "verified. It is confirmed only indirectly — zero light backgrounds, valid syntax, and "
              "135 passing checks.")

    # -------------------------------------------------------- 5 frontend
    h1(doc, "5  How the front end works")
    body(doc, "No framework, no build step. The browser loads ES modules directly.")
    table(doc, ["Mechanism", "Where", "How"],
          [["Routing", "render() in app.js", "listens to hashchange, switches to views/*.js"],
           ["Bilingual", "i18n.js", "t(key) looks up a dictionary; switching language redraws"],
           ["Charts", "chart.js", "hand-written SVG polyline with Prophet's 80% band"],
           ["Dark theme", ":root in styles.css", "change the CSS variables and it applies everywhere"],
           ["Motion", "end of styles.css", "route fade-in, staggered cards, hover lift, and prefers-reduced-motion"]],
          widths=[2.6, 4.4, 9.6])

    # -------------------------------------------------------- 6 verify
    h1(doc, "6  How to verify it still works")
    code(doc, """# seven suites, 135 checks
foreach ($t in "site_regression","visual_e2e","stores_e2e","forecast_e2e",
               "analytics_e2e","widget_e2e","tryon_e2e") {
  .venv\\Scripts\\python.exe "tools\\test_$t.py" "http://127.0.0.1:3000"
}

# reproduce the three tables in the report
.venv\\Scripts\\python.exe tools\\eval_retrieval.py
.venv\\Scripts\\python.exe tools\\eval_forecast.py
.venv\\Scripts\\python.exe tools\\eval_assistant.py""")
    body(doc, "When a service is down, the dependent tests skip or degrade rather than fail, so a "
              "partial install still reports honestly.")

    # -------------------------------------------------------- 7 change
    h1(doc, "7  I want to change X — where do I edit")
    table(doc, ["I want to change…", "Edit this", "Watch out"],
          [["Product data", "data/products.json", "rebuild the index afterwards: tools/build_clip_index.py"],
           ["Any copy, Chinese or English", "public/js/i18n.js", "add to both the zh and en blocks"],
           ["Colours / spacing / radii", ":root in public/css/styles.css", "changing a variable applies site-wide"],
           ["The layout of one page", "public/js/views/<page>.js", "one file per page"],
           ["Add a new page", "new file in views/ + the switch in app.js + i18n", "three places"],
           ["The visual-search model", "MODEL in ai-service/visual_search_service.py", "you must rebuild the index"],
           ["Forecast behaviour", "SALES / _fit in ai-service/forecast_service.py", "then run eval_forecast"],
           ["What the assistant understands", "keywords in lib/agent/router.js", "tools and composer stay unchanged"],
           ["What the assistant can answer", "lib/agent/tools.js", "new tools must emit facts"],
           ["Store data", "data/stores.json", "stock is derived from ids in lib/stores.js"]],
          widths=[3.8, 6.4, 6.4])

    # -------------------------------------------------------- 8 glossary
    h1(doc, "8  Glossary")
    table(doc, ["Term", "One-line explanation"],
          [["CLIP", "A model that maps images and text into one vector space, so text can find images"],
           ["FAISS", "Facebook's vector search library; this project uses IndexFlatIP for exact cosine search"],
           ["Recall@K", "The share of queries whose correct answer is in the top K"],
           ["MRR", "Mean reciprocal rank — how high the correct answer ranks"],
           ["Holdout", "Keep the last slice of data out of training and score only on it"],
           ["MAE / MAPE", "Mean absolute error / mean absolute percentage error; lower is better"],
           ["Holiday regressor", "A per-date feature so the model can learn \"that day is special\""],
           ["Degradation", "Falling back to something usable when a service fails, rather than erroring"],
           ["Facts", "The structured numbers a tool returns; the composer may only quote these"],
           ["O2O", "Online-to-offline: route an online dead end to a physical store"],
           ["Grounding", "Every number in an answer traces back to a tool call"]],
          widths=[3.4, 13.2])

    # -------------------------------------------------------- 9 update
    h1(doc, "9  What was added after the interim report")
    body(doc, "Sections 1 to 8 were written at the interim point. This section records "
              "what came after: three features, Mac support, deployment, and the six bugs "
              "that turned up along the way.")

    h2(doc, "9.1  Three new features")

    table(doc, ["Feature", "URL", "The problem it solves", "Core mechanism"],
          [["Virtual closet", "#/closet", "What you bought disappears from the site",
            "One-click try-on of owned items; the photo is downscaled to 720 px and kept in the browser, never uploaded"],
           ["Preference survey + prize wheel", "#/survey", "Cold start: nothing is known about a new shopper",
            "Three pairwise questions → Bradley-Terry learning → a wheel pays a HK$1–10 coupon"],
           ["Fashion AesRec score", "#/aesthetic", "\"Does this suit me?\" had no answer",
            "Wardrobe vector comparison + category detection + colour analysis → 0–100 with reasons"]],
          widths=[3.0, 1.8, 5.0, 7.0])

    body(doc, "All three share one idea: replace a generic model with the shopper's own data. "
              "The closet uses what they bought, the survey uses the choices they made, and the "
              "score uses the centroid of their wardrobe.")

    h2(doc, "9.2  How they work")

    body(doc, "① Virtual closet: keep the photo in the browser")
    code(doc, """// public/js/closetPhoto.js
// localStorage is about 5 MB; a phone photo is 4 MB and will not fit
const scale = Math.min(1, 720 / Math.max(img.width, img.height));
canvas.toDataURL('image/jpeg', 0.82);   // about 120 KB

// the try-on page restores it on mount, so "one-click" really is one click
const saved = loadPhoto();
if (saved) { /* load silently, no toast */ }""")
    body(doc, "The decision that matters is that the photo is never uploaded. It goes straight "
              "to the local CatVTON process, and the closet page says so — which is what makes "
              "the privacy argument concrete rather than a slogan.")

    body(doc, "② Preference survey: compare, do not rate — and pay for information")
    code(doc, """// lib/survey.js
// Bradley-Terry: P(A beats B) = sigmoid(s_A - s_B)
const p = 1 / (1 + Math.exp(-(score(winner) - score(loser))));
const delta = 0.35 * (1 - p);
state.scores[winner] += delta;
state.scores[loser]  -= delta;

// pick the pair the model is least sure about and has seen least
uncertainty = closeness(1/(1+gap*2.5)) * novelty(1/sqrt(1+seen)) + noise""")
    body(doc, "The quote has two terms: how uncertain this set of answers was, and how much the "
              "model already knew. Using only the first term paid every new shopper the maximum — "
              "a bug I actually hit (see 9.3).")

    body(doc, "③ Prize wheel: the server decides, the odds are published")
    code(doc, """// lib/survey.js — the client only animates; it is told the index
let r = (randomInt(0, 1_000_000) / 1_000_000) * total;   // weighted draw
// better answers shift weight from the small prizes to the big ones
weights = [20-boost, 22-boost, 20-boost, 16, 10+, 6+, 3+, 3]""")
    body(doc, "This is a design principle, not a detail: the browser cannot change the outcome, "
              "and the wheel lists the real percentage of every segment. A draw with hidden odds "
              "is a dark pattern.")

    body(doc, "④ Aesthetic score: split \"does it suit me\" into three measurable parts")
    code(doc, """# ai-service/visual_search_service.py
style    = cos(photo, wardrobe centroid)      # how close to your usual style
coverage = categories detected (top/bottom/shoes/outer)   # is it a complete look
palette  = distinct hue count + neutral share # does the colour work
score    = 0.55*style + 0.25*coverage + 0.20*palette""")
    body(doc, "Deliberately not an LLM score. A 7B vision model does not fit on the same 12 GB "
              "card as CatVTON (already 3.6 GB), and an unvalidated LLM score is a vibe rather "
              "than a benchmark. Every number here can be recomputed and traced.")

    h2(doc, "9.3  Difficulties from this stretch")

    table(doc, ["Problem", "Symptom", "Root cause", "Fix"],
          [["Survey coupons polluted retention", "155.6% retention, funnel inverted",
            "both campaigns wrote coupon_issued; the funnel counted every claim",
            "filter by the source in event metadata; survey coupons get their own metric"],
           ["Funnel showed 206%", "claimed 16, applied 33",
            "numerator counted every applied coupon, denominator only exit-intent",
            "compute applied from the coupon rows; checkout is not a subset, so it left the funnel"],
           ["Cash coupons showed 0%", "CASH8-PGWAL · 0%",
            "the table only read discountPct; cash coupons use amountHkd",
            "branch on kind to show HK$8 or 10%"],
           ["Reward was always HK$10", "every session hit the ceiling",
            "a brand-new shopper is maximally informative, so the curve saturated",
            "add novelty decay: the more the model knows, the less the next answer is worth"],
           ["Whole page turned invisible", "closet page 95% transparent",
            "animation used fill-mode both; an async re-render restarted it at opacity 0",
            "fill-mode none for route transitions; transform-only for grid children"],
           ["Survey returned one question", "occasional short sessions",
            "a category with two items offers one pair; the retry loop gave up",
            "exclude already-asked pairs at selection time"],
           ["Aesthetic score was always 75", "two different photos, same score",
            "assumed SigLIP text cosines of 0.22 and image cosines of 0–0.6; measured 0.03 and 0.6–0.8",
            "re-measured both scales and recalibrated"],
           ["Demo dashboard emptied after a week", "10 searches left",
            "seeded history was written at install time and aged out of the 7-day window",
            "if no seeded row is inside the window, delete the seeded rows and lay down a fresh one"]],
          widths=[3.2, 3.4, 4.6, 5.4], size=8.2)

    body(doc, "One problem was not about code: the sandbox's ACL runner lost its temp directory, "
              "so every command returned --temp is not an existing directory and nothing could be "
              "run for a whole turn. Only files could be written; nothing could be verified.")

    body(doc, "Another: headless Chrome cannot start on this machine "
              "(platform_channel.cc Check failed: access denied), because the sandbox's restricted "
              "token blocks the IPC channels Chrome needs for its child processes. The workaround is "
              "to run it outside the sandbox: the user runs tools/shots.ps1 in their own terminal "
              "and I read the resulting PNGs.")

    h2(doc, "9.4  Seeing the site for the first time")

    body(doc, "Until then every screen had only been verified structurally: no light backgrounds, "
              "valid syntax, passing tests. Once tools/shots.ps1 made screenshots possible, the first "
              "look found something no test could ever catch:")
    code(doc, """survey page: the two cards stacked vertically, "or" floating in empty space
cause:  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr))
        inner width 670px; 3 x 220 + 2 x 16 = 692 > 670 -> only two columns fit
fix:    fixed two columns, with "or" as an absolutely centred badge""")
    callout(doc, "A test can prove something is not broken; it cannot prove something is visible. "
                 "Transparency, stacking and broken layout all passed 185 checks.")

    h2(doc, "9.5  Size, now")

    table(doc, ["", "At the interim report", "Now"],
          [["Python services", "3", "3 (plus an /aesthetic endpoint)"],
           ["Pages", "12", "15"],
           ["Automated checks", "135 across 7 suites", "185 across 9 suites"],
           ["Documents", "report + deck", "plus the code guide, DEPLOY.md, DEMO.md"],
           ["Hardware", "Windows + RTX 4070", "same, but the code now supports Apple Silicon"]],
          widths=[4.0, 5.4, 7.2])

    # -------------------------------------------------------- 10 llm router
    h1(doc, "10  The LLM router: put the model where it does least harm")
    body(doc, "The rule router misses phrasings it has never seen. The obvious fix is "
              "\"add an LLM\" — but *where* you add it decides whether the system stays "
              "trustworthy.")

    h2(doc, "10.1  The model does one thing: classify intent")

    code(doc, """question ──▶ LLM classifies intents ─┐
                                            ├─▶ buildPlan() ──▶ tools ──▶ facts ──▶ composer
            rules classify intents ─┘   (shared)                        (unchanged)""")

    body(doc, "Both routers call the same buildPlan() and the same extractEntities(), so the "
              "comparison measures the classifier rather than two independently written "
              "planners. That is what makes the evaluation mean something.")

    callout(doc, "The model never sees the catalogue, never produces a price, a size, a stock "
                 "count or a tool argument, and never writes the answer. Money and size are "
                 "read from the shopper's own words by extractEntities().")

    h2(doc, "10.2  Why classification only")

    body(doc, "Not fastidiousness — a hard constraint on both compute and trust. Measured on "
              "this machine:")

    table(doc, ["State", "VRAM used", "Left over"],
          [["Desktop apps only", "2018 MiB", "—"],
           ["CLIP + CatVTON (no LLM)", "5672 MiB", "about 6.6 GB"],
           ["+ qwen2.5:3b (1.9 GB)", "7541 MiB", "about 4.7 GB"],
           ["+ qwen2.5:7b (4.7 GB)", "11565 MiB", "about 0.7 GB"]],
          widths=[5.6, 4.2, 5.0])

    body(doc, "The last row is the answer: the 7B loads, but try-on then times out because the "
              "card runs out of memory. Not \"slower\" — it does not finish.")

    h2(doc, "10.2b  Measured: bigger model, better accuracy, worse coexistence")

    table(doc, ["Router", "Intent", "Tool", "Latency", "Works with try-on?"],
          [["rules (no model)", "93.3%", "100%", "0.1 ms", "yes, 22.5 s"],
           ["qwen2.5:3b", "93.3%", "93.3%", "135 ms", "yes, 22.5 s"],
           ["qwen2.5:7b", "100%", "100%", "158 ms", "no — times out"]],
          widths=[4.4, 2.8, 2.8, 2.2, 4.0])

    callout(doc, "The 3B only ties the rules on intent and is worse on tool selection; the 7B is "
                 "genuinely 100% but cannot run alongside the try-on. Measured, not estimated.")

    body(doc, "An unexpected finding: the prompt mattered more than model size. The first 3B "
              "prompt scored 86.7%; adding Cantonese cues and the rule \"a budget alone is not a "
              "price question\" took it to 93.3% with the same model.")

    body(doc, "Fair warning: the rule router was developed against these same 15 questions, so its "
              "93.3% is optimistic — the set is a dev set as much as a test set. The LLM saw none "
              "of them. A larger held-out set is the next step, and tools/eval_router.py is what "
              "would run it.")

    h2(doc, "10.3  The fallback contract: four failures, all back to rules")

    table(doc, ["Failure", "Behaviour"],
          [["No model / unreachable", "falls back to rules; the answer is identical"],
           ["Timeout (2.5 s default)", "falls back to rules"],
           ["Response is not JSON", "falls back to rules"],
           ["Intent not in the allowlist", "that intent is dropped; if none survive, fall back"]],
          widths=[6.0, 9.0])

    body(doc, "Measured: with the LLM enabled but the endpoint missing, all 15 questions fell "
              "back, intent and tool accuracy were identical to the rule router, and latency "
              "rose by 0.5 ms. Turning the feature on costs nothing when no model exists.")

    h2(doc, "10.4  Verifying it without a model")

    code(doc, """python tools/mock_llm_server.py --port 11434   # scripted OpenAI-compatible server
node tools/test_router_llm.mjs 11434          # 13 contract checks

python tools/eval_router.py                   # 15 questions, both routers""")

    body(doc, "The mock can play four failure modes (prose instead of JSON, unknown intents, a "
              "timeout, an HTTP 500), so the whole path and its degradation are testable with no "
              "GPU and no model.")

    body(doc, "Honest status: both models have now been measured (10.2b). What is still missing is "
              "a held-out set — these 15 questions are the rule router's dev set too, so its 93.3% "
              "is optimistic and the comparison is not yet fair.")

    # -------------------------------------------------------- 11 fairness
    h1(doc, "11  Bias: does the score punish alternative styles?")
    body(doc, "This was the sharpest question in the discussion. The honest answer is "
              "yes, the original rule did — and measuring it turned up two outright bugs.")

    h2(doc, "11.1  What the old rule got wrong")

    code(doc, """# old
if distinctHues > 3:      palette -= (n - 3) * 16
if neutralShare < 0.12:   palette -= 12""")

    body(doc, "That is not an aesthetic, it is minimalism. Heavy metal, shamazhite and "
              "harajuku looks exceed three hues and fall under 12 % neutrals by "
              "construction, so the rule marked them down for what they are.")

    body(doc, "Measuring it exposed two worse problems:")

    table(doc, ["Bug", "Effect"],
          [["V > 0.95 was treated as neutral",
            "every fully bright colour was discarded. A neon pink has max(r,g,b)=255, so V=1.0, so its hue never existed"],
           ["cluster centres averaged arithmetically",
            "a cluster straddling red (330 and 0) averaged to 165 — the opposite hue"]],
          widths=[5.6, 9.4])

    h2(doc, "11.2  Judge structure instead of restraint")

    table(doc, ["Palette", "Verdict", "Score"],
          [["one hue / all neutral", "monochrome / neutral", "100"],
           ["two hues", "two-tone (black + red is a classic)", "95"],
           ["three or more inside a 90 degree arc", "analogous (one family)", "94-100"],
           ["three or more spread around the wheel", "scattered (no family)", "20-92"]],
          widths=[5.4, 6.6, 3.0])

    body(doc, "The difference that matters: a neon family (pink to red to orange to "
              "yellow) now scores 95, while six randomly scattered hues still score 20. "
              "The question is no longer how many colours, but whether they have a scheme.")

    h2(doc, "11.3  Measured: six styles, same garments, colour only")

    table(doc, ["Style", "Hues", "Verdict", "Old", "New"],
          [["minimal (neutrals)", "0", "neutral", "97.3", "100"],
           ["streetwear (dark + one accent)", "1", "monochrome", "100", "100"],
           ["heavy metal (black + dark red)", "2", "two-tone", "100", "95"],
           ["maximalist, coherent neon family", "2", "two-tone", "100", "95"],
           ["maximalist, scattered random hues", "3", "scattered", "100", "20"],
           ["formal (navy + grey + white)", "1", "monochrome", "100", "100"]],
          widths=[6.0, 2.0, 3.6, 2.4, 2.4])

    callout(doc, "Every style sat within 2.7 points of every other under the old rule: "
                 "it was not biased so much as blind. A signal worth 20 % of the score "
                 "that distinguishes nothing is a defect on its own.")

    h2(doc, "11.4  The value judgement that remains, stated not hidden")

    body(doc, "Preferring a coherent palette over a chaotic one is still a judgement, so:")

    bullet(doc, "palette weight cut from 20 % to 10 %, style raised to 65 %")
    bullet(doc, "the weight is one number in visual_search_service.py, easy to disagree with")
    bullet(doc, "completeness is derived from the wardrobe: someone who never buys shoes is "
                "not marked down for wearing none, and a dress satisfies both top and bottom")

    body(doc, "Reproduce it with tools/eval_aesthetic_bias.py, which draws the six styles "
              "and scores them under both rules.")

    # -------------------------------------------------------- 12 performance
    h1(doc, "12  Performance: the try-on is 20 steps, not 12, and why")
    body(doc, "This section is a correction. An earlier revision claimed DPM-Solver++ at "
              "12 steps matched DDIM at 20 and cut the time by 61 %. That was wrong, and "
              "the shape of the mistake is more useful than the original claim.")

    h2(doc, "12.1  Measure where the time goes")
    body(doc, "Same person, same garment, only the step count changed:")

    table(doc, ["Steps", "DDIM (original)", "Per step"],
          [["12", "12.9 s", "1.05 s"],
           ["20", "20.4 s", "1.02 s"],
           ["30", "29.7 s", "0.99 s"]],
          widths=[3.0, 5.0, 4.0])

    callout(doc, "Cost = about 4 s of fixed VAE encode/decode + about 1 s per step. "
                 "Halving the steps therefore saves only half of the step time; the "
                 "fixed 4 s never leaves.")

    body(doc, "The measurement also turned up that the site was running 30 steps, not the "
              "20 the docs claimed. The real starting point was 32.5 s.")

    h2(doc, "12.2  A swallowed error: the sampler swap never happened")
    body(doc, "The intent was to replace DDIM with DPM-Solver++ and keep the quality in "
              "fewer steps. The code read pipe.scheduler and replaced it.")
    body(doc, "CatVTON's pipeline stores its sampler at noise_scheduler, not at the "
              "diffusers-standard .scheduler. The line raised AttributeError, the "
              "try/except swallowed it, and the pipeline kept running DDIM.")
    body(doc, "So every recorded DPM++ measurement was really DDIM. With the swap actually "
              "working, the two are the same speed:")

    table(doc, ["Steps", "DDIM", "DPM-Solver++"],
          [["12", "12.9 s", "12.9 s"],
           ["20", "20.4 s", "20.2 s"]],
          widths=[3.0, 4.4, 6.0])

    callout(doc, "Cost per step is identical, so DPM-Solver++ buys no speed here. The "
                 "original 60 % came entirely from cutting 30 steps to 12, nothing else.")

    h2(doc, "12.3  Checked by looking: 12 steps is not enough")
    body(doc, "Compared on a real model photo rather than the clean demo portrait:")

    table(doc, ["Setting", "Time", "Quality"],
          [["DDIM 12 steps", "12.9 s", "clear residue where the old garment was"],
           ["DDIM 20 steps", "20.4 s", "clean"],
           ["DDIM 30 steps", "29.7 s", "no visible gain over 20"]],
          widths=[4.4, 3.4, 6.4])

    body(doc, "The shipped default is therefore 20 steps with DDIM: a third faster than "
              "the original 30, and the setting whose output was actually inspected.")
    body(doc, "Why the mistake survived so long: it was tested on the vendor's demo "
              "portrait, which is clean, front-facing and standard. That input looks fine "
              "even at 8 steps. Real shoppers upload their own photos.")

    h2(doc, "12.4  Why fine-tuning is not the answer")
    body(doc, "Expecting fine-tuning to make inference faster is a common mistake. "
              "Fine-tuning changes what the model draws, not how much work a step is.")

    bullet(doc, "fine-tuning: changes style or quality, leaves timing roughly unchanged")
    bullet(doc, "step distillation (LCM / Turbo / DMD2): the only training-based speedup, "
                "a research project on its own, and it costs quality")
    bullet(doc, "sampler + fewer steps: free, and already worth 60 %")

    callout(doc, "The lesson is not 'do not optimise'. It is 'do not validate on an input "
                 "that is too easy'.")

    h2(doc, "12.5  What else could work")

    table(doc, ["Method", "Expected", "Effort", "Risk"],
          [["fp8 quantisation", "another ~25 %", "medium", "4070 is Ada, fp8 is supported"],
           ["DeepCache", "1.5-2x", "medium", "needs pipeline internals"],
           ["lower resolution", "~35 %", "low", "visible quality loss"],
           ["step distillation", "4-8 steps", "high", "training, quality loss"]],
          widths=[4.4, 3.0, 2.0, 5.0])

    body(doc, "20 s is acceptable for a demo. Going lower costs quality, and the time is "
              "better spent collecting the A/B data.")

    h2(doc, "12.6  Keeping it from regressing")
    body(doc, "Two assertions guard the fast path:")

    bullet(doc, "the response must report steps = 20, so any change to the step count fails")
    bullet(doc, "the run must finish within 30 s")

    body(doc, "DDIM is the default; TRYON_SCHEDULER=dpm opts into DPM-Solver++ for anyone "
              "who wants to re-measure it.")

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("— end —")
    r.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    doc.save(OUT)
    print(f"  saved {OUT}")
    return OUT


if __name__ == "__main__":
    main()
