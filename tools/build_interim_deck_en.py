"""Build the English interim deck, reusing the layout helpers from the Chinese one.

Run:  <bundled python> tools/build_interim_deck_en.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from pptx.util import Pt                          # noqa: E402
from pptx.enum.text import PP_ALIGN               # noqa: E402
from pptx.dml.color import RGBColor               # noqa: E402

import build_ideas_deck as B                      # noqa: E402
import build_interim_deck as D                    # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, ".."))
SRC = os.path.join(os.path.dirname(ROOT), "簡報1 (1).pptx")
DST = os.path.join(ROOT, "Deck - Interim Progress Report.pptx")

TEXT, MUTED, HL = B.TEXT, B.MUTED, B.HL
PANEL, GREEN, LEAD = B.PANEL, B.GREEN_DK, B.LEAD
RED = RGBColor(0xE5, 0x48, 0x4D)

table = D.table
big_stat = D.big_stat


def build():
    prs = B.Presentation(SRC)
    B.clear_slides(prs)
    # 1 cover
    s = B.new_slide(prs, ("標題投影片", "Title Slide"))
    for ph in s.placeholders:
        ph.text_frame.text = ""
    B.para(s.shapes.title.text_frame, [("SmartMall", True, TEXT)], size=46, first=True,
           align=PP_ALIGN.CENTER)
    B.para(s.shapes.title.text_frame, [("AI-Driven E-Commerce · Interim Progress Report", False, HL)],
           size=22, align=PP_ALIGN.CENTER, space_before=8)
    sub = s.placeholders[1]
    sub.text_frame.text = ""
    B.para(sub.text_frame, [("28 October 2026", False, MUTED)], size=15, first=True,
           align=PP_ALIGN.CENTER)

    # 2 summary
    s = B.new_slide(prs)
    B.add_header(s, "The project in one page", chip="SUMMARY")
    for i, (v, lab, c) in enumerate([("4", "independent AI services", HL),
                                     ("12", "functional modules", TEXT),
                                     ("135", "automated checks passing", GREEN),
                                     ("3", "quantified evaluations", LEAD)]):
        big_stat(s, 0.8 + i * 3.0, 1.9, 2.8, v, lab, color=c, value_size=52)
    B.para(B.body_box(s, top=3.3, height=2.3, vcenter=True),
           [("Three AI capabilities have before/after numbers. Two negative results changed the "
             "design.", False, MUTED)], size=16, first=True, align=PP_ALIGN.CENTER)
    B.add_callout(s, [("Not an AI demo site — every capability is measurable, degradable and "
                       "replaceable.", False, TEXT)])

    # 3 problem
    s = B.new_slide(prs)
    B.add_header(s, "The real cost in fashion e-commerce is returns, not traffic", chip="WHY")
    B.add_card(s, 0.95, 1.75, 5.4, 2.5, "What shoppers face",
               ["Cannot judge cut, fabric or drape", "Sizes are guesswork", "Returns are a hassle"],
               fill=PANEL, bar=RED)
    B.add_card(s, 6.6, 1.75, 5.4, 2.5, "What platforms own",
               ["Price, selection, logistics already solved", "Competing on 'cheaper/faster' loses",
                "The moat is being filled in"], fill=PANEL, bar=MUTED)
    B.para(B.body_box(s, top=4.4, height=1.2, vcenter=True),
           [("So we do not compete on price. We compete on buying the right thing.", False, MUTED)],
           size=15, first=True, align=PP_ALIGN.CENTER)

    # 4 answer
    s = B.new_slide(prs)
    B.add_header(s, "Our answer: help shoppers buy right, not buy more", chip="POSITION")
    B.para(B.body_box(s, top=1.7, height=1.0),
           [("Taobao finds you the cheapest version.  ", False, MUTED),
            ("We make sure you keep it.", True, HL)],
           size=26, first=True, align=PP_ALIGN.CENTER)
    B.add_card(s, 0.95, 3.0, 5.4, 2.4, "Customer: local independent retailers",
               ["Squeezed by the large platforms", "Cannot build AI in-house",
                "Need fewer returns and higher basket"], fill=B.PANEL_GRN, bar=GREEN)
    B.add_card(s, 6.6, 3.0, 5.4, 2.4, "Delivery: B2B SaaS",
               ["One script tag on an existing store", "Merchant dashboard for the numbers",
                "Per-tenant isolation"], fill=PANEL, bar=LEAD)
    B.add_callout(s, [("The deeper platforms penetrate, the more local shops need this — a tailwind, "
                       "not a headwind.", False, TEXT)])

    # 5 architecture
    s = B.new_slide(prs)
    B.add_header(s, "Architecture: four services, each degradable", chip="ARCHITECTURE")
    table(s, 0.95, 1.85, 11.4, ["Service", "Port", "Technology", "If offline"],
          [["Web app", "3000", "Node.js, zero dependencies", "—"],
           ["Visual search", "8001", "Marqo-FashionSigLIP + FAISS", "colour heuristic"],
           ["Price forecast", "8002", "Meta Prophet", "linear trend"],
           ["Virtual try-on", "8003", "CatVTON on local GPU", "overlay preview"],
           ["Assistant", "3000", "Tool calling, 7 tools", "template replies"]],
          col_w=[2.2, 1.0, 5.6, 3.2], size=13, row_h=0.56)
    B.add_callout(s, [("Switch any AI service off and the site still works. That is a design goal, "
                       "not a side effect.", False, TEXT)])

    # 6 result 1
    s = B.new_slide(prs)
    B.add_header(s, "Result 1: image search (94 bilingual queries)", chip="RESULT")
    table(s, 0.95, 1.85, 11.4, ["Model", "R@1", "R@5", "Chinese R@5", "English R@5"],
          [["Original CLIP", "45.7%", "84.0%", "70.2%", "97.9%"],
           ["Marqo-FashionCLIP", "41.5%", "78.7%", "61.7%", "95.7%"],
           ["Marqo-FashionSigLIP (raw)", "39.4%", "58.5%", "17.0%", "100.0%"],
           ["+ Chinese normalisation (deployed)", "73.4%", "100.0%", "100.0%", "100.0%"]],
          col_w=[5.0, 1.5, 1.5, 1.7, 1.7], size=13, row_h=0.56)
    B.add_callout(s, [("A stronger model made it worse — the problem is language, not the model.",
                       True, HL)])

    # 7 the finding
    s = B.new_slide(prs)
    B.add_header(s, "Key finding: Chinese was never encoded", chip="FINDING")
    big_stat(s, 1.0, 1.8, 3.4, "17%", "Chinese Recall@5 (random ≈ 15%)", color=RED, value_size=56)
    big_stat(s, 5.0, 1.8, 3.4, "100%", "English Recall@5", color=GREEN, value_size=56)
    big_stat(s, 9.0, 1.8, 3.4, "+83", "points gained after normalisation", color=HL, value_size=56)
    B.para(B.body_box(s, top=3.4, height=2.3, vcenter=True),
           [("Three completely different Chinese queries (ski jacket / ski goggles / leather loafers) ",
             False, MUTED),
            ("produced identical embeddings and identical rankings.", True, TEXT),
            (" The tokenizer collapses CJK input instead of encoding it.", False, MUTED)],
           size=15, first=True, align=PP_ALIGN.CENTER, space_after=4)
    B.add_callout(s, [("The fix was not a better model — it was translating the query first.",
                       False, TEXT)])

    # 8 result 2
    s = B.new_slide(prs)
    B.add_header(s, "Result 2: price forecasting (40 products, 30-day holdout)", chip="RESULT")
    table(s, 0.95, 1.85, 7.2, ["Model", "MAE", "MAPE", "Won"],
          [["Prophet (deployed)", "0.28", "0.34%", "38/40"],
           ["Linear trend", "1.10", "1.25%", "0"],
           ["Naive (last price)", "0.39", "0.50%", "2"]],
          col_w=[3.4, 1.2, 1.3, 1.3], size=13, row_h=0.56)
    B.add_card(s, 8.5, 1.85, 3.85, 2.6, "On 11 November",
               ["Forecast 189 → 156.5", "A 17.2% drop", "Recovers the next day"],
               fill=B.PANEL_AMB, bar=HL, title_size=15, item_size=13)
    B.add_callout(s, [("Modelling the sale calendar as holidays is what captures a one-day dip; "
                       "yearly seasonality smears it.", False, TEXT)])

    # 9 result 3
    s = B.new_slide(prs)
    B.add_header(s, "Result 3: virtual try-on (local GPU, not simulated)", chip="RESULT")
    for i, (v, lab, c) in enumerate([("3.57", "GiB peak memory", GREEN),
                                     ("21s", "per try-on (20 steps)", HL),
                                     ("768×1024", "output resolution", TEXT)]):
        big_stat(s, 0.9 + i * 3.9, 1.8, 3.6, v, lab, color=c, value_size=44)
    B.para(B.body_box(s, top=3.3, height=2.3, vcenter=True),
           [("We chose CatVTON (ICLR 2025) over Outfit Anyone: ", True, TEXT),
            ("the latter has never released its weights, and its public demo accepts garments only "
             "with preset people.", False, MUTED)],
           size=15, first=True, align=PP_ALIGN.CENTER, space_after=6)
    B.add_callout(s, [("Face, hair and trousers are preserved; only the garment is replaced.",
                       False, TEXT)])

    # 10 result 4
    s = B.new_slide(prs)
    B.add_header(s, "Result 4: the assistant does things, not just chat", chip="RESULT")
    for i, (v, lab) in enumerate([("100%", "tool accuracy"),
                                  ("100%", "grounded answers"),
                                  ("100%", "containment")]):
        big_stat(s, 0.9 + i * 3.9, 1.8, 3.6, v, lab, color=GREEN, value_size=52)
    B.para(B.body_box(s, top=3.3, height=2.3, vcenter=True),
           [("Route → tools → facts → compose.", False, TEXT),
            (" Tools emit pre-formatted numbers and the composer does no arithmetic, so hallucinated "
             "figures are structurally impossible.", False, MUTED)],
           size=15, first=True, align=PP_ALIGN.CENTER, space_after=6)
    B.add_callout(s, [("\"Will the ski jacket get cheaper?\" → calls Prophet → quotes the 11.6% drop "
                       "and the sale date.", False, TEXT)])

    # 11 result 5
    s = B.new_slide(prs)
    B.add_header(s, "Result 5: Hong Kong localisation and store traffic", chip="RESULT")
    B.add_card(s, 0.95, 1.75, 5.4, 3.3, "Eight stores, real addresses",
               ["Mong Kok, Causeway Bay, Tsim Sha Tsui, Sha Tin", "Tsuen Wan, Kwun Tong, Central, Yuen Long",
                "MTR exits and opening hours", "Sold out online → which store has it + directions"],
               fill=PANEL, bar=LEAD, item_size=13)
    B.add_card(s, 6.6, 1.75, 5.4, 3.3, "Payment and pickup",
               ["Octopus O! ePay, PayMe, FPS", "AlipayHK, WeChat Pay HK", "SF station / locker, home delivery",
                "Store pickup: order before 6 pm, same day"], fill=B.PANEL_GRN, bar=GREEN, item_size=13)
    B.add_callout(s, [("Six products are out of stock online but on a store shelf — the local rescue "
                       "scenario.", False, TEXT)])

    # 12 differentiation
    s = B.new_slide(prs)
    B.add_header(s, "Four things a large platform structurally cannot do", chip="STRATEGY")
    table(s, 0.95, 1.85, 11.4, ["Difference", "Why the platform cannot"],
          [["Willing to say \"wait for the drop\"", "Platform revenue is tied to GMV, so it will not "
                                                    "advise against its own interest"],
           ["Cross-merchant return intelligence", "Aggregating merchant returns is commercially "
                                                  "infeasible for a marketplace"],
           ["A size passport across shops", "Platforms do not open size data to individual merchants"],
           ["Privacy localisation", "Model runs on a local GPU; body photos never leave the machine"]],
          col_w=[4.4, 7.0], size=13, row_h=0.6)
    B.add_callout(s, [("These are not feature differences. They are objective-function differences.",
                       True, HL)])

    # 13 progress
    s = B.new_slide(prs)
    B.add_header(s, "Progress: every commitment from the three meetings is done", chip="PROGRESS")
    table(s, 0.95, 1.85, 11.4, ["Stage", "Work", "Status"],
          [["Meeting 1", "Site foundation and ten modules", "Done"],
           ["Meeting 2", "Assistant, visual search, price forecast", "Done"],
           ["Meeting 3", "Merchant dashboard, embeddable widget, exit intent", "Done"],
           ["Interim", "Real models: try-on, forecast, retrieval, assistant", "Done"],
           ["Next", "Shop the Look, Try-Off, user study", "Planned"]],
          col_w=[2.4, 6.8, 1.8], size=13, row_h=0.56)
    B.add_callout(s, [("Five AI capabilities moved from simulated to real models, all measurable.",
                       False, TEXT)])

    # 14 next
    s = B.new_slide(prs)
    B.add_header(s, "Next steps and risks", chip="NEXT")
    B.add_card(s, 0.95, 1.75, 5.4, 3.2, "Next",
               ["Shop the Look: detect, crop, retrieve", "Try-Off: clean resale photos",
                "Model-based assistant routing", "User study on return rates"],
               fill=B.PANEL_GRN, bar=GREEN, item_size=13)
    B.add_card(s, 6.6, 1.75, 5.4, 3.2, "Risks, stated plainly",
               ["Synthetic data flatters the numbers", "CatVTON licence is non-commercial",
                "Try-on latency of 20-30 s", "Rule-based routing has limited coverage"],
               fill=B.PANEL_AMB, bar=HL, item_size=13)
    B.add_callout(s, [("The value of the work is the negative result and the correction, not the "
                       "number of models used.", False, TEXT)])

    # 15 close
    s = B.new_slide(prs, ("標題投影片", "Title Slide"))
    for ph in s.placeholders:
        ph.text_frame.text = ""
    B.para(s.shapes.title.text_frame, [("Discussion", True, TEXT)], size=46, first=True,
           align=PP_ALIGN.CENTER)
    sub = s.placeholders[1]
    sub.text_frame.text = ""
    for i, line in enumerate([
        "1.  Should the contribution be framed as integration or as modelling?",
        "2.  Which comes first: Shop the Look, or the user study?",
        "3.  How should synthetic-data results be presented without overclaiming?",
    ]):
        B.para(sub.text_frame, [(line, False, RGBColor(0xDD, 0xE3, 0xEE))], size=19,
               first=(i == 0), align=PP_ALIGN.CENTER, space_after=14)

    # The source theme applies all-caps to the title style. Chinese has no case so
    # it never showed; English titles look shouted. Turn it off on every run.
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    run._r.get_or_add_rPr().set("cap", "none")

    prs.save(DST)
    print(f"  saved {DST}")
    return DST


if __name__ == "__main__":
    build()
