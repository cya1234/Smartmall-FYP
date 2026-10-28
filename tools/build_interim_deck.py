"""Build the interim-progress deck (PPTX) on the same dark theme as 簡報1/簡報2.

Design brief: "easy to understand". One idea per slide, large numbers, and a
single takeaway line at the bottom. All figures come from the evaluation runs in
tools/eval_*.py.

Run:  <bundled python> tools/build_interim_deck.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from pptx.util import Inches, Pt                       # noqa: E402
from pptx.dml.color import RGBColor                    # noqa: E402
from pptx.enum.text import PP_ALIGN                    # noqa: E402

import build_ideas_deck as B                           # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, ".."))
SRC = os.path.join(os.path.dirname(ROOT), "簡報1 (1).pptx")
DST = os.path.join(ROOT, "簡報3 - 中期進度報告.pptx")

TEXT = B.TEXT
MUTED = B.MUTED
HL = B.HL
PANEL = B.PANEL
GREEN = B.GREEN_DK
LEAD = B.LEAD


def table(slide, left, top, width, headers, rows, col_w=None, size=12, row_h=0.62):
    """Dark-theme table: panel fill, white text, highlighted first column."""
    n_rows, n_cols = len(rows) + 1, len(headers)
    height = Inches(row_h * n_rows)
    shape = slide.shapes.add_table(n_rows, n_cols, Inches(left), Inches(top),
                                   Inches(width), height)
    tbl = shape.table
    if col_w:
        total = sum(col_w)
        for i, w in enumerate(col_w):
            tbl.columns[i].width = Inches(width * w / total)

    for r in range(n_rows):
        tbl.rows[r].height = Inches(row_h)
        values = headers if r == 0 else rows[r - 1]
        for c in range(n_cols):
            cell = tbl.cell(r, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = PANEL if r else RGBColor(0x2E, 0x34, 0x3D)
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER
            run = p.add_run()
            run.text = str(values[c])
            run.font.size = Pt(size)
            run.font.bold = (r == 0) or (c == 0)
            run.font.color.rgb = HL if r == 0 else (
                TEXT if (r == 1 and c == 0) else (LEAD if c == 0 else TEXT))
    return tbl


def big_stat(slide, left, top, width, value, label, color=HL, value_size=44):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(1.0))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = value
    r.font.size = Pt(value_size)
    r.font.bold = True
    r.font.color.rgb = color
    p2 = tf.add_paragraph()
    p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run()
    r2.text = label
    r2.font.size = Pt(12)
    r2.font.color.rgb = MUTED
    return box


# ------------------------------------------------------------------ slides ---
def build():
    prs = B.Presentation(SRC)
    B.clear_slides(prs)

    # 1 ---- cover ---------------------------------------------------------
    s = B.new_slide(prs, ("標題投影片", "Title Slide"))
    for ph in s.placeholders:
        ph.text_frame.text = ""
    try:
        s.shapes.title.text_frame.text = ""
        B.para(s.shapes.title.text_frame, [("SmartMall", True, TEXT)], size=46,
               first=True, align=PP_ALIGN.CENTER)
        B.para(s.shapes.title.text_frame, [("AI 驅動電商平台 · 中期進度報告", False, HL)],
               size=24, align=PP_ALIGN.CENTER, space_before=8)
        sub = s.placeholders[1]
        sub.text_frame.text = ""
        B.para(sub.text_frame, [("2026 年 10 月 28 日", False, MUTED)], size=15,
               first=True, align=PP_ALIGN.CENTER)
    except (KeyError, IndexError):
        pass

    # 2 ---- one page summary ---------------------------------------------
    s = B.new_slide(prs)
    B.add_header(s, "一頁看懂", chip="SUMMARY")
    stats = [
        ("4", "獨立 AI 推論服務", HL),
        ("12", "功能模組", TEXT),
        ("135", "項自動化測試通過", GREEN),
        ("3", "張量化評估表", LEAD),
    ]
    for i, (v, lab, c) in enumerate(stats):
        big_stat(s, 0.8 + i * 3.0, 1.9, 2.8, v, lab, color=c, value_size=52)
    B.add_callout(s, [("重點：", True, MUTED),
                      ("不是做一個 AI 示範網站，而是把每項能力做到可量測、可降級、可替換。", False, TEXT)])
    B.para(B.body_box(s, top=3.3, height=2.3, vcenter=True),
           [("三項 AI 能力都有前後對比數據，兩項負面結果改變了系統設計。", False, MUTED)],
           size=16, first=True, align=PP_ALIGN.CENTER)

    # 3 ---- the problem ---------------------------------------------------
    s = B.new_slide(prs)
    B.add_header(s, "問題：時尚電商最大的成本不是流量，是退貨", chip="WHY")
    B.add_card(s, 0.95, 1.75, 5.4, 2.5, "消費者的困境",
               ["看不到實際版型與材質", "尺碼靠猜，買錯就退", "退貨流程麻煩，體驗變差"],
               fill=PANEL, bar=RGBColor(0xE5, 0x48, 0x4D))
    B.add_card(s, 6.6, 1.75, 5.4, 2.5, "大型平台的優勢",
               ["價格、選擇、物流已做到極致", "跟它比「更快更平」必輸", "護城河正在被填平"],
               fill=PANEL, bar=MUTED)
    B.add_callout(s, [("所以我們不比價格，比「買對」。", True, HL)])
    B.para(B.body_box(s, top=2.55, height=0.5),
           [("時尚品類退貨率長期高於其他類別，主因是購買前無法判斷。", False, MUTED)],
           size=14, first=True, align=PP_ALIGN.CENTER)

    # 4 ---- our answer ----------------------------------------------------
    s = B.new_slide(prs)
    B.add_header(s, "我們的答案：讓客人買對，而不是買多", chip="POSITION")
    B.para(B.body_box(s, top=1.7, height=1.0),
           [("淘寶幫你找到最便宜的同款；", False, MUTED),
            ("SmartMall 幫你買對，而且不必退。", True, HL)],
           size=26, first=True, align=PP_ALIGN.CENTER)
    B.add_card(s, 0.95, 3.0, 5.4, 2.4, "目標客戶：本地中小型零售商",
               ["被大型平台擠壓的一群", "沒有能力自建 AI", "需要「少退貨、高客單」"],
               fill=B.PANEL_GRN, bar=GREEN)
    B.add_card(s, 6.6, 3.0, 5.4, 2.4, "交付形式：B2B SaaS",
               ["一行 script 嵌入既有網店", "商戶後台看成效", "按租戶隔離資料"],
               fill=PANEL, bar=LEAD)
    B.add_callout(s, [("平台越深入本地市場，小店越需要這套工具 —— 這是順風，不是逆風。", False, TEXT)])

    # 5 ---- architecture --------------------------------------------------
    s = B.new_slide(prs)
    B.add_header(s, "系統架構：四個服務，各自可降級", chip="ARCHITECTURE")
    table(s, 0.95, 1.85, 11.4,
          ["服務", "埠", "技術", "離線時"],
          [["網站", "3000", "Node.js 零依賴", "—"],
           ["視覺搜尋", "8001", "Marqo-FashionSigLIP + FAISS", "退回顏色比對"],
           ["價格預測", "8002", "Meta Prophet", "退回線性趨勢"],
           ["虛擬試穿", "8003", "CatVTON（本機 GPU）", "退回疊加預覽"],
           ["助手", "3000", "工具呼叫，7 個工具", "退回模板回覆"]],
          col_w=[2.2, 1.0, 5.6, 3.2], size=12, row_h=0.52)
    B.add_callout(s, [("任何一個 AI 服務關掉，網站都仍然可用 —— 這是設計目標，不是副作用。", False, TEXT)])

    # 6 ---- result 1: visual search --------------------------------------
    s = B.new_slide(prs)
    B.add_header(s, "成果 1：以圖搜尋（94 條中英雙語查詢）", chip="RESULT")
    table(s, 0.95, 1.85, 11.4,
          ["模型", "R@1", "R@5", "中文 R@5", "英文 R@5"],
          [["原本的 CLIP", "45.7%", "84.0%", "70.2%", "97.9%"],
           ["Marqo-FashionCLIP", "41.5%", "78.7%", "61.7%", "95.7%"],
           ["Marqo-FashionSigLIP（原始）", "39.4%", "58.5%", "17.0%", "100.0%"],
           ["＋中文查詢正規化（採用）", "73.4%", "100.0%", "100.0%", "100.0%"]],
          col_w=[5.0, 1.5, 1.5, 1.7, 1.7], size=12, row_h=0.5)
    B.add_callout(s, [("換更強的模型反而變差 —— 問題不在模型，在語言。", True, HL)])

    # 7 ---- the finding ---------------------------------------------------
    s = B.new_slide(prs)
    B.add_header(s, "關鍵發現：中文根本沒有被編碼", chip="FINDING")
    big_stat(s, 1.0, 1.8, 3.4, "17%", "中文 Recall@5（隨機約 15%）", color=RGBColor(0xE5, 0x48, 0x4D), value_size=56)
    big_stat(s, 5.0, 1.8, 3.4, "100%", "英文 Recall@5", color=GREEN, value_size=56)
    big_stat(s, 9.0, 1.8, 3.4, "+83", "加上正規化後的提升（百分點）", color=HL, value_size=56)
    B.para(B.body_box(s, top=3.4, height=2.3, vcenter=True),
           [("三個完全不同的中文查詢（滑雪外套／滑雪護目鏡／真皮樂福鞋）", False, MUTED),
            ("產生一模一樣的向量與排序。", True, TEXT),
            ("分詞器把中日韓文字壓成同一序列，等於沒有讀進去。", False, MUTED)],
           size=15, first=True, align=PP_ALIGN.CENTER, space_after=4)
    B.add_callout(s, [("修法不是換模型，是把中文查詢先轉成英文時尚術語。", False, TEXT)])

    # 8 ---- result 2: forecasting ----------------------------------------
    s = B.new_slide(prs)
    B.add_header(s, "成果 2：價格預測（40 件商品 · 留出 30 天）", chip="RESULT")
    table(s, 0.95, 1.85, 7.2,
          ["模型", "MAE", "MAPE", "勝出"],
          [["Prophet（採用）", "0.28", "0.34%", "38/40"],
           ["線性趨勢", "1.10", "1.25%", "0"],
           ["樸素（沿用現價）", "0.39", "0.50%", "2"]],
          col_w=[3.4, 1.2, 1.3, 1.3], size=12, row_h=0.5)
    B.add_card(s, 8.5, 1.7, 3.85, 2.6, "雙十一那天",
               ["預測由 189 跌至 156.5", "跌幅 17.2%", "前後日自動回升"], fill=B.PANEL_AMB, bar=HL,
               title_size=15, item_size=13)
    B.add_callout(s, [("把促銷日曆當節日回歸量，單日跌幅才抓得住；年度季節性會把它抹平。", False, TEXT)])

    # 9 ---- result 3: try-on ---------------------------------------------
    s = B.new_slide(prs)
    B.add_header(s, "成果 3：虛擬試穿（本機 GPU，非模擬）", chip="RESULT")
    for i, (v, lab, c) in enumerate([("3.57", "GiB 峰值記憶體", GREEN),
                                     ("21s", "生成時間（20 步）", HL),
                                     ("768×1024", "輸出解析度", TEXT)]):
        big_stat(s, 0.9 + i * 3.9, 1.8, 3.6, v, lab, color=c, value_size=44)
    B.para(B.body_box(s, top=3.3, height=2.3, vcenter=True),
           [("選用 CatVTON（ICLR 2025）而非 Outfit Anyone：", True, TEXT),
            ("後者權重未開源，官方展示亦只允許上傳衣物、人像為預設。", False, MUTED)],
           size=15, first=True, align=PP_ALIGN.CENTER, space_after=6)
    B.add_callout(s, [("臉、頭髮、褲子完整保留，只有衣服被替換。", False, TEXT)])

    # 10 --- result 4: assistant ------------------------------------------
    s = B.new_slide(prs)
    B.add_header(s, "成果 4：助手會做事，不只是聊天", chip="RESULT")
    for i, (v, lab, c) in enumerate([("100%", "工具選擇準確率", GREEN),
                                     ("100%", "事實可追溯率", GREEN),
                                     ("100%", "自助完成率", GREEN)]):
        big_stat(s, 0.9 + i * 3.9, 1.8, 3.6, v, lab, color=c, value_size=52)
    B.para(B.body_box(s, top=3.3, height=2.3, vcenter=True),
           [("架構：問題 → 路由 → 工具 → 事實 → 組句。", False, TEXT),
            ("工具輸出已格式化的數字，組句器完全不做算術 —— 所以幻覺在結構上不可能。", False, MUTED)],
           size=15, first=True, align=PP_ALIGN.CENTER, space_after=6)
    B.add_callout(s, [("「滑雪外套會唔會減價？」→ 呼叫 Prophet → 引用 11.6% 跌幅與雙十一日期。", False, TEXT)])

    # 11 --- result 5: O2O + HK -------------------------------------------
    s = B.new_slide(prs)
    B.add_header(s, "成果 5：香港本地化與門市導流", chip="RESULT")
    B.add_card(s, 0.95, 1.7, 5.4, 3.3, "八間門市 · 真實格式",
               ["旺角、銅鑼灣、尖沙咀、沙田", "荃灣、觀塘、中環、元朗", "含港鐵出口與營業時間",
                "線上缺貨 → 顯示哪間有現貨 + 導航"],
               fill=PANEL, bar=LEAD)
    B.add_card(s, 6.6, 1.7, 5.4, 3.3, "支付與取貨",
               ["八達通 O! ePay、PayMe、轉數快", "AlipayHK、WeChat Pay HK", "順豐站／智能櫃、送貨上門",
                "門市自取：下午 6 點前即日取"],
               fill=B.PANEL_GRN, bar=GREEN)
    B.add_callout(s, [("六件商品線上缺貨但門市有現貨 —— 這就是本地零售的救援場景。", False, TEXT)])

    # 12 --- differentiation ----------------------------------------------
    s = B.new_slide(prs)
    B.add_header(s, "差異化：四件大型平台結構上做不到的事", chip="STRATEGY")
    table(s, 0.95, 1.85, 11.4,
          ["差異", "為何平台做不到"],
          [["敢建議「等降價」", "平台收入與成交額掛鉤，不會給出違反自身利益的建議"],
           ["跨商戶退貨情報", "平台彙總商家退貨資料在商業關係上不可行"],
           ["尺寸護照（跨商戶通用）", "平台的尺碼資料不會開放給個別商家"],
           ["私隱本地化", "模型在本機 GPU 執行，身材照片不需上傳第三方"]],
          col_w=[4.2, 7.2], size=12, row_h=0.62)
    B.add_callout(s, [("這些不是功能差異，是「目標函數」的差異。", True, HL)])

    # 13 --- progress ------------------------------------------------------
    s = B.new_slide(prs)
    B.add_header(s, "進度：三次會議的承諾都已完成", chip="PROGRESS")
    table(s, 0.95, 1.85, 11.4,
          ["階段", "工作", "狀態"],
          [["第一次會議", "網站基礎與十個功能模組", "已完成"],
           ["第二次會議", "情境助手、視覺搜尋、價格預測", "已完成"],
           ["第三次會議", "商戶後台、嵌入元件、退出挽留", "已完成"],
           ["中期", "真實模型替換：試穿、預測、檢索、助手", "已完成"],
           ["下一階段", "Shop the Look、Try-Off、使用者研究", "待進行"]],
          col_w=[2.6, 6.6, 2.0], size=12, row_h=0.55)
    B.add_callout(s, [("五項 AI 能力由「模擬」轉為「真實模型」，全部可量測。", False, TEXT)])

    # 14 --- next ----------------------------------------------------------
    s = B.new_slide(prs)
    B.add_header(s, "下一步與風險", chip="NEXT")
    B.add_card(s, 0.95, 1.7, 5.4, 3.2, "接下來做",
               ["Shop the Look：偵測裁切後逐件檢索", "Try-Off：二手刊登自動去背",
                "助手路由改用語言模型", "使用者研究：驗證退貨率下降"],
               fill=B.PANEL_GRN, bar=GREEN)
    B.add_card(s, 6.6, 1.7, 5.4, 3.2, "風險與老實話",
               ["資料為合成，評估偏樂觀", "CatVTON 授權非商業", "試穿延遲 20–30 秒",
                "規則式路由覆蓋率有限"],
               fill=B.PANEL_AMB, bar=HL)
    B.add_callout(s, [("論文的價值在於「負面結果 + 修正」，而不是「用了很多模型」。", False, TEXT)])

    # 15 --- close ---------------------------------------------------------
    s = B.new_slide(prs, ("標題投影片", "Title Slide"))
    for ph in s.placeholders:
        ph.text_frame.text = ""
    try:
        B.para(s.shapes.title.text_frame, [("討論", True, TEXT)], size=46,
               first=True, align=PP_ALIGN.CENTER)
        sub = s.placeholders[1]
        sub.text_frame.text = ""
        for i, line in enumerate([
            "1.  研究貢獻應定位在「整合」還是「模型」？",
            "2.  Shop the Look 與使用者研究，優先做哪一項？",
            "3.  合成資料的評估結果，如何在論文中誠實呈現？",
        ]):
            B.para(sub.text_frame, [(line, False, RGBColor(0xDD, 0xE3, 0xEE))], size=19,
                   first=(i == 0), align=PP_ALIGN.CENTER, space_after=14)
    except (KeyError, IndexError):
        pass

    prs.save(DST)
    print(f"  saved {DST}  ({len(prs.slides.__iter__.__self__._sldIdLst)} slides)")
    return DST


if __name__ == "__main__":
    build()
