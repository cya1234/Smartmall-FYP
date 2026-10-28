"""Build the English interim report (DOCX).

Numbers come from tools/eval_retrieval.py, tools/eval_forecast.py,
tools/eval_assistant.py and the seven test suites.

Run:  <bundled python> tools/build_interim_report_en.py
"""
import os
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Cm, RGBColor

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "Interim Report - SmartMall.docx")

LATIN = "Calibri"
CJK = "Microsoft JhengHei"
ACCENT = RGBColor(0x3B, 0x2F, 0xB8)


def set_fonts(rpr):
    rfonts = rpr.rFonts
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), CJK)
    rfonts.set(qn("w:ascii"), LATIN)
    rfonts.set(qn("w:hAnsi"), LATIN)


def setup(doc):
    for name in ("Normal", "Heading 1", "Heading 2", "Heading 3", "Title"):
        try:
            st = doc.styles[name]
        except KeyError:
            continue
        st.font.name = LATIN
        if st.element.rPr is None:
            st.element.get_or_add_rPr()
        set_fonts(st.element.rPr)
    doc.styles["Normal"].font.size = Pt(11)
    doc.styles["Normal"].paragraph_format.space_after = Pt(8)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.25
    for name, size in (("Heading 1", 16), ("Heading 2", 13), ("Title", 26)):
        try:
            doc.styles[name].font.size = Pt(size)
            doc.styles[name].font.color.rgb = ACCENT
        except KeyError:
            pass
    for s in doc.sections:
        s.top_margin = Cm(2.2)
        s.bottom_margin = Cm(2.2)
        s.left_margin = Cm(2.4)
        s.right_margin = Cm(2.4)


def h1(doc, text):
    p = doc.add_heading(text, level=1)
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(6)
    return p


def h2(doc, text):
    p = doc.add_heading(text, level=2)
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    return p


def body(doc, text):
    return doc.add_paragraph(text)


def bullet(doc, text):
    p = doc.add_paragraph(text, style="List Bullet")
    p.paragraph_format.left_indent = Cm(0.75)
    p.paragraph_format.space_after = Pt(3)
    return p


def table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        r = cell.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(9.5)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v))
            r.font.size = Pt(9.5)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def caption(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


def main():
    doc = Document()
    setup(doc)

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("SmartMall: An AI-Driven E-Commerce Platform")
    r.bold = True
    r.font.size = Pt(24)
    r.font.color.rgb = ACCENT

    s = doc.add_paragraph()
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rs = s.add_run("Interim Progress Report")
    rs.font.size = Pt(15)
    rs.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    m = doc.add_paragraph()
    m.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rm = m.add_run("28 October 2026")
    rm.font.size = Pt(10)
    rm.font.color.rgb = RGBColor(0x77, 0x77, 0x77)
    doc.add_paragraph()

    # ---- abstract
    h1(doc, "Abstract")
    body(doc, "This project builds SmartMall, an AI-driven fashion e-commerce platform aimed at small "
              "and medium-sized apparel retailers in Hong Kong. Rather than a demonstration of AI "
              "features, the emphasis is on making four capabilities measurable, degradable and "
              "independently replaceable: multimodal visual search, time-series price forecasting, "
              "virtual try-on, and a tool-calling shopping assistant.")
    body(doc, "At the interim stage the system integrates 12 functional modules, 4 independent "
              "inference services and 135 automated checks. Three capabilities carry quantitative "
              "evaluation. Visual search reaches Recall@5 of 100% on a 94-query bilingual set, up "
              "from 84.0% with the previous backbone. Price forecasting achieves a MAPE of 0.34% on "
              "40 products under a holdout protocol, against 1.25% for a linear baseline and 0.50% "
              "for a naive one. The assistant scores 100% on tool selection, factual traceability and "
              "containment across 15 bilingual questions.")
    body(doc, "The report also records three findings that changed the design: a vendor-claimed "
              "+57% retrieval improvement that did not transfer to Chinese queries, a shared sale "
              "calendar that made every forecast advisory identical, and the fact that the most "
              "publicised try-on model has never released its weights.")

    # ---- introduction
    h1(doc, "1  Introduction")
    h2(doc, "1.1  Background")
    body(doc, "Return rates in fashion e-commerce are consistently higher than in other categories, "
              "largely because shoppers cannot judge cut, fabric and drape before purchase. Meanwhile "
              "large platforms have already optimised logistics, payment and price. Any new entrant "
              "positioned on 'faster, cheaper, more choice' is competing on the dimensions where the "
              "incumbent is strongest.")
    h2(doc, "1.2  Problem Statement")
    body(doc, "The project asks whether a system built for local independent retailers can offer "
              "value that a large platform structurally cannot. Our answer is to reduce buying the "
              "wrong item rather than to reduce price.")
    h2(doc, "1.3  Objectives and Scope")
    bullet(doc, "Build a working system rather than a UI demonstration; every AI capability must be "
                "measurable.")
    bullet(doc, "Every AI service must be independently switchable and degrade gracefully without "
                "affecting the rest of the site.")
    bullet(doc, "Ground the product in Hong Kong: Traditional Chinese and Cantonese phrasing, HKD, "
                "local payment and pickup, and physical store stock.")

    # ---- related work
    h1(doc, "2  Related Work")
    h2(doc, "2.1  Cross-modal Retrieval")
    body(doc, "CLIP maps images and text into a shared embedding space through contrastive learning, "
              "forming the basis of image-to-image and text-to-image search. FashionCLIP later "
              "fine-tuned the model on fashion vocabulary. Marqo's Generalized Contrastive Learning "
              "optimises seven facets simultaneously (description, title, colour, detail, category, "
              "keyword, material) and reports up to +57% recall@1 over FashionCLIP2.0 across seven "
              "public fashion datasets. We tested that claim independently; results appear in "
              "Section 5.1.")
    h2(doc, "2.2  Virtual Try-On")
    body(doc, "Virtual try-on has moved from GANs to diffusion models: TryOnDiffusion (CVPR 2023) "
              "introduced a dual-UNet formulation; OOTDiffusion (CVPR 2024) improved garment detail "
              "with an outfitting UNet; IDM-VTON (ECCV 2024) added dual encoders for fidelity; "
              "CatVTON (ICLR 2025) argued that simple concatenation suffices, using 899M total "
              "parameters with only 49.6M trained and fitting inference within 8 GB at 1024x768; "
              "OmniVTON (ICCV 2025) proposed a training-free universal framework supporting multiple "
              "people in one scene. Alibaba's OutfitAnyone is well known but has never released its "
              "weights, and its public demo accepts garment images only with preset person models, "
              "so it cannot serve as this project's backend.")
    h2(doc, "2.3  Price Forecasting")
    body(doc, "Retail price seasonality is driven mainly by the promotional calendar rather than by "
              "weather. Prophet models a series additively with interpretable trend, seasonality and "
              "holiday components, which suits series with explicit event structure.")
    h2(doc, "2.4  Tool-Calling Assistants")
    body(doc, "Allowing a language model to state product facts freely produces hallucination. The "
              "practical pattern in commerce is to let the model choose a tool and phrase the result "
              "while every fact originates from the tool call. This project adopts that architecture.")

    # ---- architecture
    h1(doc, "3  System Architecture")
    h2(doc, "3.1  Layering")
    body(doc, "The system is layered in four parts: a vanilla JavaScript single-page front end with "
              "no build step; a zero-dependency Node.js HTTP server; an inference layer of three "
              "independent Python services communicating over fixed JSON contracts; and a data layer "
              "containing the catalogue, price history, store data and a SQLite event store.")
    body(doc, "The purpose of this layering is that any AI service can be replaced or switched off "
              "without affecting the transaction path. Each layer has an explicit fallback.")
    h2(doc, "3.2  Services")
    table(doc, ["Service", "Port", "Technology", "Primary endpoints"],
          [["Web application", "3000", "Node.js built-in modules", "products, cart, agent, analytics"],
           ["Visual search", "8001", "Marqo-FashionSigLIP + FAISS", "/search, /embed, /health"],
           ["Price forecast", "8002", "Meta Prophet 1.5.0", "/forecast/:id, /eval"],
           ["Virtual try-on", "8003", "CatVTON MaskFree + diffusers", "/tryon, /health"]],
          widths=[3.4, 1.4, 5.8, 5.6])
    caption(doc, "Table 1: Four services and their ports. Each can be started or stopped independently.")
    h2(doc, "3.3  Degradation")
    body(doc, "When a capability is switched off the system falls back to a usable alternative rather "
              "than failing:")
    table(doc, ["Capability", "Behaviour when the service is offline"],
          [["Visual search", "Falls back to a colour heuristic and still returns results"],
           ["Price forecast", "Falls back to a linear trend model with the same response shape"],
           ["Virtual try-on", "Falls back to a colour overlay preview that still shows product data"],
           ["Assistant", "Falls back to template replies whose facts come from the same tools"]],
          widths=[3.6, 12.6])
    caption(doc, "Table 2: Degradation strategy. No single service failure makes the site unusable.")

    # ---- modules
    h1(doc, "4  Implemented Modules")
    body(doc, "Twelve functional modules are implemented. Five are driven by real models; the rest "
              "are rule-based or simulated but expose the same fixed contracts and can be replaced.")
    table(doc, ["#", "Module", "Status", "Description"],
          [["1", "Style Box", "Rule-based", "Assembles a complete kit for an occasion and budget"],
           ["2", "Style Advisor", "Tool-calling", "7 tools; answers quote tool facts only"],
           ["3", "Image Search", "Real model", "Marqo-FashionSigLIP with Chinese query normalisation"],
           ["4", "Price Trends", "Real model", "Meta Prophet with sale calendar as holiday regressors"],
           ["5", "Virtual Try-On", "Real model", "CatVTON MaskFree on local GPU"],
           ["6", "Store Stock", "Real data", "8 Hong Kong stores, cross-store stock, map directions"],
           ["7", "Merchant Dashboard", "Real data", "SQLite event store: search, retention, conversion"],
           ["8", "Embeddable Widget", "Complete", "One script tag, iframe panel, multi-tenant branding"],
           ["9", "Price Agent", "Simulated", "Seven-marketplace comparison and negotiation"],
           ["10", "Resale", "Rule-based", "Automatic listing copy and price suggestion"],
           ["11", "Memory & Profile", "Real data", "Wardrobe, size, style and return history"],
           ["12", "Return Prediction", "Rule-based", "Defect classification and return form generation"]],
          widths=[1.0, 3.9, 2.3, 9.2])
    caption(doc, "Table 3: Functional modules and implementation status.")

    # ---- evaluation
    h1(doc, "5  Evaluation")
    body(doc, "All three evaluations are reproducible programs in tools/, with results stored as "
              "JSON in data/eval/.")

    h2(doc, "5.1  Visual Search")
    body(doc, "We built a bilingual evaluation set: 47 Chinese/English query pairs (94 queries) "
              "covering attribute, colour, material and occasion categories at three difficulty "
              "levels. Retrieval is over the 34 products that have real photography.")
    table(doc, ["Model", "Recall@1", "Recall@5", "MRR", "Chinese R@5", "English R@5"],
          [["ViT-B-32 / laion2b (original)", "45.7%", "84.0%", "0.637", "70.2%", "97.9%"],
           ["Marqo-FashionCLIP", "41.5%", "78.7%", "0.576", "61.7%", "95.7%"],
           ["Marqo-FashionSigLIP", "39.4%", "58.5%", "0.499", "17.0%", "100.0%"]],
          widths=[5.4, 2.2, 2.2, 1.8, 2.2, 2.2])
    caption(doc, "Table 4: Retrieval with raw queries (94 queries).")
    body(doc, "This contradicts the vendor's report: adopting the fashion-tuned model made overall "
              "performance worse. Marqo-FashionSigLIP reaches 100% on English queries but only 17% "
              "on Chinese, where random performance is about 15%. A direct probe showed three "
              "entirely different Chinese queries producing identical embeddings and identical "
              "rankings, indicating the tokenizer collapses CJK input rather than encoding it.")
    body(doc, "We therefore added a lightweight Chinese query normalisation step: a 120-term "
              "fashion glossary translates the query into English terminology before encoding.")
    table(doc, ["Model", "Recall@1", "Recall@5", "MRR", "Chinese R@5"],
          [["ViT-B-32 / laion2b", "58.5%", "97.9%", "0.764", "97.9%"],
           ["Marqo-FashionCLIP", "64.9%", "95.7%", "0.781", "95.7%"],
           ["Marqo-FashionSigLIP (deployed)", "73.4%", "100.0%", "0.850", "100.0%"]],
          widths=[5.4, 2.4, 2.4, 2.0, 2.4])
    caption(doc, "Table 5: Retrieval with query normalisation.")
    body(doc, "Conclusion: the bottleneck is language alignment, not the vision model. The deployed "
              "configuration raises Recall@1 from 45.7% to 73.4% and Recall@5 from 84.0% to 100%. "
              "Caveat: the glossary overlaps with catalogue vocabulary, so these figures are an "
              "optimistic lexicon baseline. The human-paired English queries (100%) represent the "
              "ceiling. A production system should replace the glossary with a language model and "
              "re-measure with the same harness.")

    h2(doc, "5.2  Price Forecasting")
    body(doc, "We generated 800 days of daily prices for 40 products (32,000 observations) with a "
              "slow inflationary trend, a weekend effect, noise, and the Hong Kong and Greater China "
              "promotional calendar. Promotional participation and discount depth are product-level "
              "traits rather than yearly coin flips; with per-year randomness the model cannot learn "
              "an effect and accuracy collapses to the naive baseline.")
    body(doc, "Evaluation holds out the last 30 days of each series, trains on the remainder and "
              "scores on the holdout.")
    table(doc, ["Model", "MAE", "RMSE", "MAPE", "Median MAPE", "Products won"],
          [["Prophet (deployed)", "0.28", "0.35", "0.34%", "0.33%", "38 / 40"],
           ["Linear trend baseline", "1.10", "1.17", "1.25%", "0.70%", "0"],
           ["Naive baseline (carry last price)", "0.39", "0.47", "0.50%", "0.46%", "2"]],
          widths=[4.6, 1.8, 1.8, 2.0, 2.2, 2.4])
    caption(doc, "Table 6: Holdout comparison across 40 products.")
    body(doc, "One methodological change mattered. Prophet's default yearly seasonality is a Fourier "
              "term that smears a one-day promotion across the whole month: for 11 November it "
              "predicted a 4.2% dip against an actual 18%. Supplying the promotional calendar as "
              "explicit holiday regressors produced a forecast of USD 156.5 for that date, 17.2% "
              "below the current price, with automatic recovery on the following days.")
    body(doc, "To be explicit: the price series is synthetic and the sale dates are known to the "
              "model, so the margin over baseline is an upper bound. The defensible claim is that "
              "modelling the promotional calendar beats ignoring it, not that the error is 0.34% on "
              "real data.")

    h2(doc, "5.3  Tool-Calling Assistant")
    body(doc, "The architecture is route, plan, execute, facts, compose. Tools emit pre-formatted "
              "facts such as totalDisplay, onlineStock and dropPct, and the composer performs no "
              "arithmetic, so no path exists from prose to an invented number. This is a structural "
              "guarantee rather than a prompt-level constraint.")
    table(doc, ["Metric", "Result", "Meaning"],
          [["Tool accuracy", "15 / 15 (100%)", "The correct tool was selected"],
           ["Grounding", "15 / 15 (100%)", "Every number appears in a tool fact"],
           ["Containment", "15 / 15 (100%)", "Answered without the template fallback"]],
          widths=[3.8, 4.4, 7.8])
    caption(doc, "Table 7: Assistant evaluation over 15 bilingual questions.")
    body(doc, "Limitation: 15 questions is a smoke test, not a benchmark, and the router is rule "
              "based, so unfamiliar phrasing will miss. The tool layer and composer are deliberately "
              "separated from the router so that replacing it with a language model leaves everything "
              "else unchanged.")

    h2(doc, "5.4  Try-On Performance")
    table(doc, ["Item", "Value"],
          [["Model", "CatVTON MaskFree, mix-48k-1024"],
           ["Resolution", "768 x 1024"],
           ["Generation time", "21 s (20 steps) / 31 s (30 steps)"],
           ["Peak memory", "3.57 GiB on an RTX 4070 (12 GB)"],
           ["Model load", "3.6 s"]],
          widths=[4.0, 12.0])
    caption(doc, "Table 8: Local inference performance.")

    # ---- localisation
    h1(doc, "6  Localisation and Differentiation")
    h2(doc, "6.1  Localisation")
    bullet(doc, "Eight stores (Mong Kok, Causeway Bay, Tsim Sha Tsui, Sha Tin, Tsuen Wan, Kwun Tong, "
                "Central, Yuen Long) with MTR exits, opening hours, phone numbers and coordinates.")
    bullet(doc, "Delivery: SF Express station or locker, home delivery, and same-day store pickup for "
                "orders placed before 6 pm.")
    bullet(doc, "Payment: Octopus O! ePay, PayMe, FPS, AlipayHK, WeChat Pay HK and credit card.")
    bullet(doc, "Bilingual interface with HKD pricing.")
    h2(doc, "6.2  Differentiation")
    body(doc, "The customer is not the shopper but the local retailer being squeezed by large "
              "platforms. On that framing, deeper penetration by those platforms increases demand for "
              "this system. Four structural differences follow:")
    table(doc, ["Difference", "Why a large platform cannot do it"],
          [["Willing to advise 'wait for the drop'", "Platform revenue is tied to GMV, so it will not "
                                                     "advise against its own short-term interest"],
           ["Cross-merchant return intelligence", "Aggregating merchant return data is commercially "
                                                  "infeasible for a marketplace, but feasible for a "
                                                  "neutral third party"],
           ["A size passport that works across shops", "A platform does not expose its size data to "
                                                       "individual merchants"],
           ["Privacy localisation", "The model runs on a local GPU, so body photos need not be "
                                    "uploaded to a third party"]],
          widths=[4.8, 11.4])
    caption(doc, "Table 9: Four structural differences.")

    # ---- progress
    h1(doc, "7  Progress")
    table(doc, ["Stage", "Work", "Status"],
          [["Meeting 1", "Site foundation and ten functional modules", "Complete"],
           ["Meeting 2", "Contextual assistant, visual search, price forecast", "Complete"],
           ["Meeting 3", "B2B SaaS layer: merchant dashboard, embeddable widget, exit intent", "Complete"],
           ["Interim", "Real models: CatVTON, Prophet, FashionSigLIP, tool-calling agent", "Complete"],
           ["Next", "Shop the Look (detect and crop), Try-Off for resale listings", "Planned"],
           ["Next", "User study: measured return-rate effect and usability testing", "Planned"]],
          widths=[3.0, 9.6, 3.2])
    caption(doc, "Table 10: Progress against the agreed milestones.")

    # ---- risks
    h1(doc, "8  Remaining Work and Risks")
    h2(doc, "8.1  Remaining Work")
    bullet(doc, "Shop the Look: detect and crop individual garments, then retrieve each one.")
    bullet(doc, "Try-Off: recover a clean product image from a worn-garment photo to remove the "
                "friction of photographing items for resale.")
    bullet(doc, "Replace the assistant router with a language model and expand the evaluation set "
                "beyond 100 questions.")
    bullet(doc, "User study with local boutiques to test whether the return rate actually falls.")
    h2(doc, "8.2  Risks")
    table(doc, ["Risk", "Impact", "Mitigation"],
          [["Synthetic data makes evaluation optimistic", "Persuasiveness of conclusions",
            "State the upper bound explicitly and cross-check on a public dataset"],
           ["CatVTON licence is non-commercial", "Commercial use is blocked",
            "Acceptable for the FYP; a commercial product needs a differently licensed model"],
           ["Try-on latency of 20-30 s", "User experience",
            "Progress feedback and a server-side queue"],
           ["Rule-based router coverage", "Assistant comprehension",
            "Tools and router are separated, so the router can be swapped for a model"],
           ["Cold start for size prediction", "No history for new users",
            "Fall back to body measurements and brand size charts"]],
          widths=[4.6, 4.4, 7.0])
    caption(doc, "Table 11: Principal risks and mitigations.")

    # ---- conclusion
    h1(doc, "9  Conclusion")
    body(doc, "At the interim stage the project has validated three layers. Technically, four AI "
              "capabilities run on real models and are measurable. Engineering-wise, four services "
              "deploy independently, each with a fallback, and pass 135 automated checks. "
              "Scientifically, three defensible findings emerged: two negative results (a vendor "
              "retrieval gain that does not transfer to Chinese, and a shared sale calendar that "
              "removes all variation from advisories) and one architectural fact (the most "
              "publicised try-on model has not released its weights).")
    body(doc, "Each finding changed the design, and together they form the contribution: on the "
              "Chinese query set defined here, adding query-language normalisation mattered far more "
              "than choosing a stronger vision model. The next stage moves from technical validation "
              "towards value validation, through Shop the Look and a user study.")

    # ---- references
    h1(doc, "References")
    refs = [
        "Radford, A. et al. (2021). Learning Transferable Visual Models From Natural Language "
        "Supervision. ICML.",
        "Marqo (2025). Marqo Fashion Embedding Models: Marqo-FashionCLIP and Marqo-FashionSigLIP. "
        "https://marqo.ai/blog/search-model-for-fashion",
        "Zheng, C. et al. (2024). CatVTON: Concatenation Is All You Need for Virtual Try-On with "
        "Diffusion Models. ICLR 2025. arXiv:2407.15886.",
        "Yang, Z. et al. (2025). OmniVTON: Training-Free Universal Virtual Try-On. ICCV 2025. "
        "arXiv:2507.15037.",
        "Sun, K. et al. (2024). OutfitAnyone: Ultra-high Quality Virtual Try-On for Any Clothing and "
        "Any Person. arXiv:2407.16224.",
        "Taylor, S. J. & Letham, B. (2018). Forecasting at Scale. The American Statistician, 72(1), "
        "37-45.",
        "Cheng, W.-H. et al. (2021). Fashion Meets Computer Vision: A Survey. ACM Computing Surveys, "
        "54(4), Article 72. DOI: 10.1145/3447239.",
        "Klingenberg, B. (2016). Making Fashion Recommendations with Human-in-the-loop Machine "
        "Learning. KDD 2016.",
    ]
    for i, ref in enumerate(refs, 1):
        p = doc.add_paragraph(f"[{i}]  {ref}")
        p.paragraph_format.left_indent = Cm(0.9)
        p.paragraph_format.first_line_indent = Cm(-0.9)
        p.paragraph_format.space_after = Pt(4)
        for r in p.runs:
            r.font.size = Pt(9.5)

    doc.save(OUT)
    print(f"  saved {OUT}")
    return OUT


if __name__ == "__main__":
    main()
