"""Build a new SmartMall deck (Ideas & Open Questions) in the style of 簡報1 (1).pptx.

Starts from the existing file so the theme, fonts, master and 16:9 geometry are
inherited exactly, clears the old slides, and writes a new deck.

Run:
  python build_ideas_deck.py "<source.pptx>" "<output.pptx>"
"""
import re
import sys
import zipfile

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

# ---------------------------------------------------------------- palette ---
# The source template is a dark theme: near-black (#17191C) with a halftone dot
# pattern, white text and yellow highlights. Everything below is tuned for that
# dark background so text stays legible.
TEXT = RGBColor(0xFF, 0xFF, 0xFF)        # primary body text (white)
LEAD = RGBColor(0xBF, 0xD4, 0xF5)        # bold lead-in labels (light blue)
MUTED = RGBColor(0xA6, 0xAE, 0xBD)       # secondary text
RULE = RGBColor(0x8A, 0xB0, 0xEC)        # accent rule / card accents
CHIP_BG = RGBColor(0x3A, 0x5F, 0xA8)     # section chip fill
HL = RGBColor(0xFF, 0xE9, 0x4D)          # yellow highlight, as in the source
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

PANEL = RGBColor(0x20, 0x24, 0x2A)       # dark card fill
PANEL_LINE = RGBColor(0x3A, 0x41, 0x4C)
PANEL_AMB = RGBColor(0x2C, 0x28, 0x1A)   # callout fill (warm)
PANEL_GRN = RGBColor(0x1A, 0x28, 0x20)

# Aliases kept so the slide definitions below read naturally.
INK = TEXT
ACCENT = RULE
ACCENT_DK = LEAD
ACCENT_LT = PANEL
AMBER_LT = PANEL_AMB
AMBER_DK = RGBColor(0xF2, 0xC1, 0x4E)    # amber text / callout accent
GREEN_LT = PANEL_GRN
GREEN_DK = RGBColor(0x7F, 0xD3, 0xA6)    # green text

FONT = None  # inherit from theme


def detect_theme_accent(path):
    """Pull accent1 out of theme1.xml so accents match the source deck."""
    try:
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if re.match(r"ppt/theme/theme\d+\.xml$", n)]
            if not names:
                return None
            xml = z.read(sorted(names)[0]).decode("utf-8", "ignore")
            m = re.search(r"<a:accent1>\s*<a:srgbClr val=\"([0-9A-Fa-f]{6})\"", xml)
            if m:
                h = m.group(1)
                return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- helpers ---
def clear_slides(prs):
    sld_id_lst = prs.slides._sldIdLst
    for sld_id in list(sld_id_lst):
        r_id = sld_id.get(qn("r:id"))
        prs.part.drop_rel(r_id)
        sld_id_lst.remove(sld_id)


def find_layout(prs, *candidates):
    for name in candidates:
        for lay in prs.slide_layouts:
            if lay.name.strip() == name:
                return lay
    return prs.slide_layouts[-1]


def set_run(r, text, size=None, bold=None, color=None, italic=None):
    r.text = text
    f = r.font
    if FONT:
        f.name = FONT
    if size is not None:
        f.size = Pt(size)
    if bold is not None:
        f.bold = bold
    if italic is not None:
        f.italic = italic
    if color is not None:
        f.color.rgb = color


def para(tf, segments, size=18, level=0, space_before=0, space_after=6,
         align=PP_ALIGN.LEFT, bullet=False, first=False):
    """segments: str or list of (text, bold, color) tuples."""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.level = level
    p.alignment = align
    p.space_before = Pt(space_before)
    p.space_after = Pt(space_after)
    if isinstance(segments, str):
        segments = [(segments, False, INK)]
    for text, bold, color in segments:
        r = p.add_run()
        set_run(r, text, size=size, bold=bold, color=color if color is not None else INK)
    if bullet:
        pPr = p._pPr if p._pPr is not None else p._p.get_or_add_pPr()
        pPr.set("marL", str(Emu(Inches(0.28))))
        pPr.set("indent", str(-Emu(Inches(0.28))))
        for tag in ("a:buNone", "a:buChar", "a:buAutoNum"):
            for el in pPr.findall(qn(tag)):
                pPr.remove(el)
        bu = pPr.makeelement(qn("a:buChar"), {"char": "•"})
        pPr.append(bu)
    return p


def add_header(slide, title, chip=None, chip_color=None, title_size=30):
    """Centered bold title + a thin accent rule, echoing the source deck."""
    title_ph = slide.shapes.title
    if title_ph is not None:
        tf = title_ph.text_frame
        tf.word_wrap = True
        tf.text = ""
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        p.vertical_anchor = MSO_ANCHOR.MIDDLE
        r = p.add_run()
        set_run(r, title, size=title_size, bold=True, color=INK)
        title_ph.top = Inches(0.38)
        title_ph.height = Inches(0.95)
        title_ph.left = Inches(1.0)
        title_ph.width = Inches(11.33)
        rule_top = Inches(1.36)
    else:
        box = slide.shapes.add_textbox(Inches(1.0), Inches(0.38), Inches(11.33), Inches(0.95))
        tf = box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        set_run(r, title, size=title_size, bold=True, color=INK)
        rule_top = Inches(1.36)

    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(5.42), rule_top, Inches(2.5), Pt(2.5))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    bar.shadow.inherit = False

    if chip:
        cw = Inches(1.55)
        ch = Inches(0.34)
        chip_shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.0), Inches(0.44), cw, ch)
        chip_shape.fill.solid()
        chip_shape.fill.fore_color.rgb = chip_color or CHIP_BG
        chip_shape.line.fill.background()
        chip_shape.shadow.inherit = False
        ctf = chip_shape.text_frame
        ctf.word_wrap = False
        cp = ctf.paragraphs[0]
        cp.alignment = PP_ALIGN.CENTER
        cr = cp.add_run()
        set_run(cr, chip, size=11, bold=True, color=WHITE)
        ctf.vertical_anchor = MSO_ANCHOR.MIDDLE
    return slide


def body_box(slide, left=0.95, top=1.62, width=11.43, height=5.3, vcenter=False):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE if vcenter else MSO_ANCHOR.TOP
    return tf


def add_callout(slide, segments, left=0.95, top=5.95, width=11.43, height=0.72,
                fill=AMBER_LT, bar=AMBER_DK, size=15):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top),
                                 Inches(width), Inches(height))
    box.fill.solid()
    box.fill.fore_color.rgb = fill
    box.line.fill.background()
    box.shadow.inherit = False
    box.adjustments[0] = 0.08
    accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top),
                                    Pt(4), Inches(height))
    accent.fill.solid()
    accent.fill.fore_color.rgb = bar
    accent.line.fill.background()
    accent.shadow.inherit = False

    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.18)
    tf.margin_right = Inches(0.14)
    tf.margin_top = Inches(0.04)
    tf.margin_bottom = Inches(0.04)
    p = tf.paragraphs[0]
    if isinstance(segments, str):
        segments = [(segments, True, bar)]
    for text, bold, color in segments:
        r = p.add_run()
        set_run(r, text, size=size, bold=bold, color=color or INK)
    return box


def add_card(slide, left, top, width, height, title, items, fill=ACCENT_LT,
             bar=ACCENT, title_size=15, item_size=14, subtitle=None, title_color=None):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top),
                                  Inches(width), Inches(height))
    card.fill.solid()
    card.fill.fore_color.rgb = fill
    card.line.color.rgb = bar
    card.line.width = Pt(1)
    card.shadow.inherit = False
    card.adjustments[0] = 0.06
    tf = card.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.2)
    tf.margin_top = Inches(0.14)
    tf.margin_right = Inches(0.16)
    para(tf, [(title, True, title_color or bar)], size=title_size, first=True, space_after=3)
    if subtitle:
        para(tf, [(subtitle, False, MUTED)], size=12, space_after=10)
    for it in items:
        para(tf, it if isinstance(it, list) else [(it, False, INK)],
             size=item_size, space_after=5, bullet=True)
    return card


def new_slide(prs, layout_name=("只有標題", "Title Only")):
    lay = find_layout(prs, *layout_name)
    return prs.slides.add_slide(lay)


# ------------------------------------------------------------------ slides --
def build(src, dst):
    # The source theme is dark, so the palette above is used as-is rather than
    # derived from the theme's accent1 (a dark blue that would vanish).
    prs = Presentation(src)
    clear_slides(prs)

    # ---- S1 title ----
    lay = find_layout(prs, "標題投影片", "Title Slide")
    s = prs.slides.add_slide(lay)
    title_ph = s.shapes.title
    title_ph.left, title_ph.top = Inches(1.2), Inches(2.05)
    title_ph.width, title_ph.height = Inches(10.9), Inches(1.5)
    tf = title_ph.text_frame
    tf.word_wrap = True
    tf.text = ""
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    set_run(r, "SmartMall", size=54, bold=True, color=INK)

    sub = s.placeholders[1]
    sub.left, sub.top = Inches(1.2), Inches(3.55)
    sub.width, sub.height = Inches(10.9), Inches(1.5)
    stf = sub.text_frame
    stf.word_wrap = True
    stf.text = ""
    p = stf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    set_run(r, "Ideas & Open Questions", size=28, bold=True, color=ACCENT_DK)
    p2 = stf.add_paragraph()
    p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run()
    set_run(r2, "第二次會議 · Second Meeting", size=18, color=MUTED)

    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(5.42), Inches(3.32), Inches(2.5), Pt(3))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    bar.shadow.inherit = False

    # ---- S2 agenda ----
    s = new_slide(prs)
    add_header(s, "今日議程 · Agenda")
    tf = body_box(s, top=1.72)
    agenda = [
        ("一", "目前進度回顧", "3 分鐘 · 我們已經有什麼"),
        ("二", "七個新想法", "可以走得更遠的方向"),
        ("三", "六個待定問題", "需要你決定方向"),
        ("四", "下一步與時間表", "把決定變成行動"),
    ]
    for i, (num, head, sub2) in enumerate(agenda):
        para(tf, [(f"{num}、 ", True, ACCENT), (head, True, INK), ("   ", False, INK), (sub2, False, MUTED)],
             size=19, space_after=13, first=(i == 0), bullet=False)
    add_callout(s, [("目標：", True, AMBER_DK),
                    ("在繼續動手之前，先把「範圍」與「貢獻」定清楚。", False, INK)])

    # ---- S3 recap ----
    s = new_slide(prs)
    add_header(s, "目前進度 · Where We Are")
    add_card(s, 0.95, 1.62, 5.55, 3.30, "✅ 已真正運行", [
        [("完整電商網站：", True, GREEN_DK), ("10 個 AI 模組、雙語、購物車", False, INK)],
        [("CLIP + FAISS 視覺搜尋：", True, GREEN_DK), ("RTX 4070 實跑", False, INK)],
        [("效能：", True, GREEN_DK), ("19 ms/圖嵌入、8–24 ms/查詢", False, INK)],
        [("準確度：", True, GREEN_DK), ("10/10 文字查詢命中正確商品", False, INK)],
    ], fill=GREEN_LT, bar=GREEN_DK, item_size=14, subtitle="不是簡報，是可以打開來按的網站")
    add_card(s, 6.83, 1.62, 5.55, 3.30, "🧩 仍是模擬", [
        "購物助手 / 買手盲盒",
        "全網比價與議價",
        "二手流轉 / 好友投票",
        "記憶畫像 / 退貨預測 / 智慧客服",
        [("但都有明確的", False, INK), ("「換模型接口」", True, ACCENT_DK)],
    ], fill=ACCENT_LT, bar=ACCENT, item_size=14, subtitle="介面已完成，模型尚未接上")
    add_callout(s, [("關鍵取捨：", True, AMBER_DK),
                    ("模擬 vs 真模型，界線要劃在哪裡？（見 Q4）", False, INK)])

    # ---- S4 section: ideas ----
    lay = find_layout(prs, "章節標題", "Section Header")
    s = prs.slides.add_slide(lay)
    s.shapes.title.text_frame.text = ""
    tp = s.shapes.title.text_frame.paragraphs[0]
    tp.alignment = PP_ALIGN.CENTER
    r = tp.add_run()
    set_run(r, "Part 1 · 新想法", size=44, bold=True, color=INK)
    sub = s.placeholders[1]
    sub.text_frame.text = ""
    sp = sub.text_frame.paragraphs[0]
    sp.alignment = PP_ALIGN.CENTER
    r = sp.add_run()
    set_run(r, "七個可以走得更遠的方向", size=22, color=MUTED)

    # ---- idea slides ----
    ideas = [
        ("IDEA 1", "換上時尚專用 CLIP，並做成 Benchmark", [
            [("現況：", True, ACCENT_DK), ("通用 CLIP（ViT-B-32），零樣本檢索 10/10 命中", False, INK)],
            [("想法：", True, ACCENT_DK), ("換成 ", False, INK), ("FashionCLIP / marqo-fashionSigLIP", True, HL), ("，用同一組 query 比較", False, INK)],
            [("原因：", True, ACCENT_DK), ("文獻指出時尚的「語意差距」最大，通用模型對材質、剪裁不敏感", False, INK)],
            [("交付物：", True, ACCENT_DK), ("一張 benchmark 表（通用 vs 時尚，相同資料集與指標）", False, INK)],
            [("下一步：", True, ACCENT_DK), ("先跑現有 34 件，再擴到 200 件看結果是否穩定", False, INK)],
        ], [("低成本、高學術回報", True, AMBER_DK), (" —— 只要換模型權重，不必重寫系統。", False, INK)]),

        ("IDEA 2", "Human-in-the-loop 才是真正的差異化", [
            [("文獻（KDD 2016, Stitch Fix）：", True, ACCENT_DK), ("系統價值 = ", False, INK), ("h + m + hm", True, HL), ("（人 + 機器 + 互動）", False, INK)],
            [("我們的對應：", True, ACCENT_DK), ("好友投票＝購買前的人類訊號；退貨紀錄＝購買後的人類訊號", False, INK)],
            [("想法：", True, ACCENT_DK), ("把人類回饋接進排序模型，形成閉環", False, INK)],
            [("為什麼：", True, ACCENT_DK), ("文獻自認「真實場景仍不及人類」——這正是切入點", False, INK)],
            [("風險：", True, ACCENT_DK), ("需要足夠回饋量；短期可用問卷模擬朋友投票", False, INK)],
        ], [("「AI 建議 → 人類決定 → 回饋再訓練」", True, AMBER_DK), (" 可以成為論文的貢獻。", False, INK)]),

        ("IDEA 3", "多模態 RAG：把兩個模組縫起來", [
            [("現況：", True, ACCENT_DK), ("文字助手與視覺搜尋是兩條獨立管線", False, INK)],
            [("想法：", True, ACCENT_DK), ("把 CLIP 向量也放進 RAG 的檢索庫", False, INK)],
            [("情境：", True, ACCENT_DK), ("「跟我上傳的這件外套同色系，但正式一點」→ 一次查詢完成", False, INK)],
            [("技術：", True, ACCENT_DK), ("統一查詢向量（已實作）＋ Chroma 向量庫（免 Docker）", False, INK)],
            [("成本：", True, ACCENT_DK), ("純 pip 安裝，查詢延遲預計 +20 ms 以內", False, INK)],
        ], [("把「搜圖」與「問答」", True, AMBER_DK), (" 合成同一個能力，而不是兩個功能。", False, INK)]),

        ("IDEA 4", "生成式虛擬試穿：值得投入嗎？", [
            [("文獻：", True, ACCENT_DK), ("synthesis 三大任務 —— 風格轉換、姿勢轉換、布料模擬", False, INK)],
            [("現況：", True, ACCENT_DK), ("canvas 疊色（誠實標註為模擬）", False, INK)],
            [("想法：", True, ACCENT_DK), ("換成 diffusion（IDM-VTON / CatVTON）", False, INK)],
            [("風險：", True, ACCENT_DK), ("RTX 4070 只有 12GB，主流方案多建議 16GB 以上", False, INK)],
            [("折衷：", True, ACCENT_DK), ("保留 2D 合成，並用好友投票補足說服力", False, INK)],
        ], [("問題：", True, AMBER_DK), ("要投入這個風險，還是把現有模擬做到很精緻？", False, INK)]),

        ("IDEA 5", "資料策略：文獻指出的真正瓶頸", [
            [("文獻結論：", True, ACCENT_DK), ("標註成本高、資料集小、真實分佈差異大", False, INK)],
            [("已做：", True, ACCENT_DK), ("從公開資料集取真實商品照（34/40），建立 CLIP 索引", False, INK)],
            [("想法一：", True, ACCENT_DK), ("價格預測用合成序列（雙 11、聖誕季節性），並明確標註", False, INK)],
            [("想法二：", True, ACCENT_DK), ("建立固定的評測集，讓所有模型版本都能比較", False, INK)],
            [("原則：", True, ACCENT_DK), ("合成資料必須在論文明確標註，不能假裝是真實交易紀錄", False, INK)],
        ], [("論文用一整節談資料策略", True, AMBER_DK), ("，比假裝有真實資料更受評審欣賞。", False, INK)]),

        ("IDEA 6", "商業模式與線上線下結合", [
            [("訂閱制：", True, ACCENT_DK), ("AI 無限造型、盲盒組合", False, INK)],
            [("B2B：", True, ACCENT_DK), ("把比價、退貨預測賣給小型賣家", False, INK)],
            [("佣金：", True, ACCENT_DK), ("議價代理為使用者省下的金額抽成", False, INK)],
            [("線下：", True, ACCENT_DK), ("比價時同時顯示附近門市庫存與距離（location-oriented recommendation）", False, INK)],
            [("問題：", True, ACCENT_DK), ("哪一個模式最適合當 FYP demo 的主線？", False, INK)],
        ], [("文獻案例：", True, AMBER_DK), (" Stitch Fix 訂閱制、Sephora 以降退貨率為策略。", False, INK)]),
    ]

    for chip, title, bullets, callout in ideas:
        s = new_slide(prs)
        add_header(s, title, chip=chip, title_size=29)
        tf = body_box(s, top=1.60, height=4.20, vcenter=True)
        for i, seg in enumerate(bullets):
            para(tf, seg, size=19, space_after=19, first=(i == 0), bullet=True)
        add_callout(s, callout, top=6.02, height=0.76, size=15)

    # ---- S11 section: questions ----
    s = prs.slides.add_slide(find_layout(prs, "章節標題", "Section Header"))
    s.shapes.title.text_frame.text = ""
    tp = s.shapes.title.text_frame.paragraphs[0]
    tp.alignment = PP_ALIGN.CENTER
    r = tp.add_run()
    set_run(r, "Part 2 · 待討論問題", size=44, bold=True, color=INK)
    sub = s.placeholders[1]
    sub.text_frame.text = ""
    sp = sub.text_frame.paragraphs[0]
    sp.alignment = PP_ALIGN.CENTER
    r = sp.add_run()
    set_run(r, "六個需要你決定方向的問題", size=22, color=MUTED)

    # ---- S12 Q1 ----
    s = new_slide(prs)
    add_header(s, "Q1 · 研究貢獻要定位在哪裡？", chip="QUESTION 1", title_size=29)
    tf = body_box(s, top=1.66, height=3.4)
    opts = [
        [("(A) 工程整合：", True, ACCENT_DK), ("把多個 AI 模組整合成一個可用的電商平台", False, INK)],
        [("(B) 模型方法：", True, ACCENT_DK), ("改進單一演算法（檢索 / 推薦 / 預測）", False, INK)],
        [("(C) 使用者研究：", True, ACCENT_DK), ("人類回饋如何改善推薦品質", False, INK)],
    ]
    for i, seg in enumerate(opts):
        para(tf, seg, size=18, space_after=14, first=(i == 0), bullet=True)
    add_card(s, 0.95, 4.35, 11.43, 1.35, "我們的傾向",
             [[("以 A + C 為主軸，B 用 benchmark 比較補足", True, ACCENT_DK)]],
             fill=ACCENT_LT, bar=ACCENT, title_size=14, item_size=15)
    add_callout(s, [("想問：", True, AMBER_DK),
                    ("這樣的定位，在評分與答辯上站得住腳嗎？", False, INK)], top=6.0, height=0.75)

    # ---- S13 Q2 ----
    s = new_slide(prs)
    add_header(s, "Q2 · Benchmark 要怎麼做才具說服力？", chip="QUESTION 2", title_size=29)
    tf = body_box(s, top=1.60, height=4.15, vcenter=True)
    rows = [
        [("資料集：", True, ACCENT_DK), ("DeepFashion / PolyVore / LIP / 自建固定評測集？", False, INK)],
        [("指標：", True, ACCENT_DK), ("文字→商品 top-k、AUC（相容性）、MAPE（預測）？", False, INK)],
        [("Baseline：", True, ACCENT_DK), ("通用 CLIP、關鍵字搜尋、傳統協同過濾", False, INK)],
        [("嚴謹度：", True, ACCENT_DK), ("固定隨機種子、固定 query 集，結果可重現", False, INK)],
    ]
    for i, seg in enumerate(rows):
        para(tf, seg, size=19, space_after=20, first=(i == 0), bullet=True)
    add_callout(s, [("想問：", True, AMBER_DK),
                    ("是否一定要做使用者研究（問卷 / A/B）才算完整？", False, INK)], top=6.02, height=0.76)

    # ---- S14 Q3 ----
    s = new_slide(prs)
    add_header(s, "Q3 · 範圍要不要砍？", chip="QUESTION 3", title_size=29)
    add_card(s, 0.95, 1.62, 3.6, 3.35, "必做（核心）",
             [[("視覺搜尋", False, INK)], [("購物助手 / 買手盲盒", False, INK)], [("價格預測", False, INK)]],
             fill=GREEN_LT, bar=GREEN_DK, item_size=15, subtitle="沒有它就不算完成專案")
    add_card(s, 4.86, 1.62, 3.6, 3.35, "加分",
             [[("全網比價與議價", False, INK)], [("二手流轉", False, INK)],
              [("記憶畫像", False, INK)], [("退貨預測", False, INK)]],
             fill=ACCENT_LT, bar=ACCENT, item_size=15, subtitle="時間夠才做，能提高分數")
    add_card(s, 8.77, 1.62, 3.6, 3.35, "Stretch",
             [[("生成式虛擬試穿", False, INK)], [("好友投票", False, INK)]],
             fill=AMBER_LT, bar=AMBER_DK, item_size=15, subtitle="風險高，先評估再說")
    add_callout(s, [("想問：", True, AMBER_DK),
                    ("你希望「每個模組都能 demo」，還是「三個做到很深」？", False, INK)],
                top=5.72, height=0.78)

    # ---- S15 Q4-Q6 ----
    s = new_slide(prs)
    add_header(s, "Q4–Q6 · 三個較小的決定", chip="QUESTIONS 4–6", title_size=29)
    tf = body_box(s, top=1.60, height=4.40, vcenter=True)
    small_q = [
        [("Q4 真模型 vs 模擬：", True, ACCENT_DK), ("哪些必須真的跑？", False, INK)],
        [("　 建議：", False, MUTED), ("視覺搜尋與價格預測真跑，其餘保留清楚接口", False, MUTED)],
        [("Q5 評估指標：", True, ACCENT_DK), ("除準確度外，要不要量退貨率下降、轉換率？", False, INK)],
        [("　 前提：", False, MUTED), ("需要真實使用者或問卷，成本較高", False, MUTED)],
        [("Q6 合規邊界：", True, ACCENT_DK), ("比價代理的爬取與議價到哪裡為止？", False, INK)],
        [("　 目前：", False, MUTED), ("只讀公開標價、只走平台允許的管道", False, MUTED)],
    ]
    for i, seg in enumerate(small_q):
        para(tf, seg, size=18, space_after=14, first=(i == 0),
             bullet=(seg[0][0].startswith("Q")))

    # ---- S16 next steps ----
    s = new_slide(prs)
    add_header(s, "下一步與時間表 · Next Steps", chip="ROADMAP", title_size=29)
    tf = body_box(s, top=1.66, height=3.5)
    steps = [
        [("本週：", True, ACCENT_DK), ("換上 FashionCLIP，產出通用 vs 時尚的 benchmark 表", False, INK)],
        [("下週：", True, ACCENT_DK), ("Prophet 價格預測，附線性回歸 baseline 對照", False, INK)],
        [("之後：", True, ACCENT_DK), ("把 CLIP 接入 RAG；撰寫「資料策略」一節", False, INK)],
        [("最後：", True, ACCENT_DK), ("整理成論文架構：四支柱對應我們十個模組", False, INK)],
    ]
    for i, seg in enumerate(steps):
        para(tf, seg, size=18, space_after=12, first=(i == 0), bullet=True)
    add_callout(s, [("需要你今天決定：", True, AMBER_DK),
                    ("範圍（Q3）、貢獻定位（Q1）、benchmark 設計（Q2）", False, INK)],
                top=5.85, height=0.8)

    # ---- S17 closing ----
    lay = find_layout(prs, "標題投影片", "Title Slide")
    s = prs.slides.add_slide(lay)
    title_ph = s.shapes.title
    title_ph.left, title_ph.top = Inches(1.2), Inches(2.35)
    title_ph.width, title_ph.height = Inches(10.9), Inches(1.3)
    tf = title_ph.text_frame
    tf.word_wrap = True
    tf.text = ""
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    set_run(r, "討論時間", size=50, bold=True, color=INK)

    sub = s.placeholders[1]
    sub.left, sub.top = Inches(1.2), Inches(3.85)
    sub.width, sub.height = Inches(10.9), Inches(2.6)
    stf = sub.text_frame
    stf.word_wrap = True
    stf.text = ""
    for i, line in enumerate([
        "1.  研究貢獻要定位在「整合」還是「模型」？",
        "2.  範圍要收斂到三個核心，還是維持十個模組？",
        "3.  要不要做使用者研究來驗證退貨率下降？",
    ]):
        p = stf.paragraphs[0] if i == 0 else stf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        p.space_after = Pt(14)
        r = p.add_run()
        set_run(r, line, size=20, color=RGBColor(0xDD, 0xE3, 0xEE))

    prs.save(dst)
    return dst


if __name__ == "__main__":
    src = sys.argv[1]
    dst = sys.argv[2]
    out = build(src, dst)
    print(f"saved {out}")
