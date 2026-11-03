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
