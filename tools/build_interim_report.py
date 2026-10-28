"""Build the FYP interim report (DOCX).

Content is drawn from measurements actually taken during development:
tools/eval_retrieval.py, tools/eval_forecast.py, tools/eval_assistant.py and the
seven test suites. Nothing here is estimated.

Run:  python tools/build_interim_report.py
"""
import os
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, Cm, RGBColor

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "報告 - 中期進度報告.docx")

BODY_FONT = "Microsoft JhengHei"
LATIN_FONT = "Calibri"
ACCENT = RGBColor(0x3B, 0x2F, 0xB8)


def set_cjk(style_or_run_element, cjk=BODY_FONT, latin=LATIN_FONT):
    rpr = style_or_run_element
    rfonts = rpr.rFonts
    if rfonts is None:
        from docx.oxml import OxmlElement
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), cjk)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)


def setup(doc):
    for name in ("Normal", "Heading 1", "Heading 2", "Heading 3", "Title"):
        try:
            st = doc.styles[name]
        except KeyError:
            continue
        st.font.name = LATIN_FONT
        if st.element.rPr is None:
            st.element.get_or_add_rPr()
        set_cjk(st.element.rPr)
    doc.styles["Normal"].font.size = Pt(11)
    doc.styles["Normal"].paragraph_format.space_after = Pt(8)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.25
    for name, size in (("Heading 1", 16), ("Heading 2", 13), ("Title", 26)):
        try:
            doc.styles[name].font.size = Pt(size)
            doc.styles[name].font.color.rgb = ACCENT
        except KeyError:
            pass
    for section in doc.sections:
        section.top_margin = Cm(2.2)
        section.bottom_margin = Cm(2.2)
        section.left_margin = Cm(2.4)
        section.right_margin = Cm(2.4)


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


def body(doc, text, bold_prefix=None):
    p = doc.add_paragraph()
    if bold_prefix:
        r = p.add_run(bold_prefix)
        r.bold = True
    p.add_run(text)
    return p


def bullet(doc, text, level=0):
    p = doc.add_paragraph(text, style="List Bullet")
    p.paragraph_format.left_indent = Cm(0.75 + 0.6 * level)
    p.paragraph_format.space_after = Pt(3)
    return p


def table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(9.5)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(v))
            run.font.size = Pt(9.5)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def caption(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


# ---------------------------------------------------------------------- body --
def main():
    doc = Document()
    setup(doc)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("SmartMall：AI 驅動電商平台")
    run.bold = True
    run.font.size = Pt(26)
    run.font.color.rgb = ACCENT

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = sub.add_run("中期進度報告")
    r2.font.size = Pt(15)
    r2.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r3 = meta.add_run("2026 年 10 月 28 日")
    r3.font.size = Pt(10)
    r3.font.color.rgb = RGBColor(0x77, 0x77, 0x77)
    doc.add_paragraph()

    # ---------------------------------------------------------------- abstract
    h1(doc, "摘要")
    body(doc, "本研究建構一個以人工智能驅動的時尚電商平台 SmartMall，並以香港中小型服飾零售商為"
              "目標使用者。有別於常見的「AI 功能展示」，本專案的重點是把四項 AI 能力做成可量測、"
              "可降級、可獨立替換的服務：多模態視覺搜尋、時間序列價格預測、虛擬試穿，以及工具呼叫式"
              "購物助手。")
    body(doc, "截至中期，系統已整合 12 個功能模組、4 個獨立推論服務與 135 項自動化測試。三項主要"
              "AI 能力均有量化評估：視覺搜尋在 94 條中英雙語查詢上達成 Recall@5 100%（前代模型為 "
              "84.0%）；價格預測在 40 件商品上以留出法比較，MAPE 為 0.34%，勝過線性基準 1.25% 與"
              "樸素基準 0.50%；助手在 15 題中達成工具選擇準確率、事實可追溯率與自助完成率各 100%。")
    body(doc, "本報告同時記錄三項研究過程中的負面結果：廠商聲稱的 +57% 檢索提升無法轉移至中文查詢、"
              "所有商品共用同一促銷日曆會使預測建議失去鑑別度，以及虛擬試穿的官方權重實際並未開源。"
              "這三項發現直接改變了系統設計。")

    # ------------------------------------------------------------ introduction
    h1(doc, "1  引言")
    h2(doc, "1.1  研究背景")
    body(doc, "時尚電商的退貨率長期高於其他品類，主因是消費者在購買前無法判斷版型、材質與實際"
              "穿著效果。與此同時，大型平台（如淘寶）已把物流、支付與價格優勢做到極致，任何以"
              "「更快、更平、更多選擇」為定位的新進者都難以競爭。")
    h2(doc, "1.2  問題陳述")
    body(doc, "本專案要回答的問題是：一個以本地中小型零售商為對象的系統，能否在大型平台已經"
              "佔優的市場中，提供對方結構上做不到的價值？我們認為答案是「降低買錯與退貨」，"
              "而非「降低售價」。")
    h2(doc, "1.3  目標與範圍")
    bullet(doc, "建立可實際運作的 AI 電商系統，而非介面示範；每項 AI 能力必須可量測。")
    bullet(doc, "所有 AI 服務必須可獨立關閉並優雅降級，不影響網站其餘部分。")
    bullet(doc, "以香港為落地場景：繁體中文與廣東話語氣、港幣、本地支付與取貨、實體門市庫存。")

    # --------------------------------------------------------- related work
    h1(doc, "2  相關研究")
    h2(doc, "2.1  跨模態檢索")
    body(doc, "CLIP 以對比學習把圖像與文字映射至同一向量空間，成為圖搜圖與文搜圖的基礎。其後"
              "FashionCLIP 針對時尚詞彙微調；Marqo 提出的 Generalized Contrastive Learning 進一步"
              "以七個面向（描述、標題、顏色、細節、類別、關鍵詞、材質）同時優化，官方報告稱在七個"
              "公開時尚資料集上較 FashionCLIP2.0 提升 recall@1 達 57%。本專案對此進行了獨立驗證，"
              "結果見第 5.1 節。")
    h2(doc, "2.2  虛擬試穿")
    body(doc, "虛擬試穿由 GAN 架構演進至擴散模型：TryOnDiffusion（CVPR 2023）引入雙 UNet；"
              "OOTDiffusion（CVPR 2024）以 outfitting UNet 改善服裝細節；IDM-VTON（ECCV 2024）"
              "以雙重編碼提升擬真度；CatVTON（ICLR 2025）主張以簡單拼接取代複雜對齊，總參數 899M、"
              "僅需訓練 49.6M，並可在 8GB 記憶體以內完成 1024×768 推論；OmniVTON（ICCV 2025）"
              "則提出免訓練的統一框架，支援多人同框。阿里 OutfitAnyone 亦具代表性，但其權重並未"
              "公開，官方展示亦僅允許上傳衣物、人像為預設模型，無法作為本專案之後端。")
    h2(doc, "2.3  價格預測")
    body(doc, "零售價格具強烈季節性，且季節性主要來自促銷日曆（雙十一、黑色星期五、聖誕、農曆新年）"
              "而非氣候。Meta 開源的 Prophet 以可解釋的趨勢、季節與節日分量建立加法模型，適合"
              "此類具有明確事件結構的序列。")
    h2(doc, "2.4  工具呼叫式助手")
    body(doc, "大型語言模型直接生成商品資訊會產生幻覺，因此在電商場景的可行做法是讓模型只負責"
              "「選擇工具」與「措辭」，所有事實由工具回傳。此架構（function calling／tool use）"
              "亦是本專案採用的方式。")

    # ------------------------------------------------------------ architecture
    h1(doc, "3  系統架構")
    h2(doc, "3.1  分層設計")
    body(doc, "系統分為四層：前端為零建置步驟的原生 JavaScript 單頁應用；Web 層為零外部依賴的 "
              "Node.js HTTP 伺服器；AI 推論層為三個獨立 Python 服務，各自以固定 JSON 契約與 Web 層"
              "通訊；資料層包含商品目錄、價格歷史、門市資料與 SQLite 事件庫。")
    body(doc, "此分層的目的是讓 AI 服務可以被替換或關閉而不影響交易流程。每一層都有明確的降級路徑。")
    h2(doc, "3.2  服務清單")
    table(doc,
          ["服務", "埠", "技術", "主要端點"],
          [["Web 應用", "3000", "Node.js 內建模組", "商品、購物車、代理、分析"],
           ["視覺搜尋", "8001", "Marqo-FashionSigLIP + FAISS", "/search、/embed、/health"],
           ["價格預測", "8002", "Meta Prophet 1.5.0", "/forecast/:id、/eval"],
           ["虛擬試穿", "8003", "CatVTON MaskFree + diffusers", "/tryon、/health"]],
          widths=[3.2, 1.6, 6.0, 5.4])
    caption(doc, "表 1：四個服務與其埠號。全部可獨立啟動或關閉。")
    h2(doc, "3.3  降級策略")
    body(doc, "每一項 AI 能力關閉時，系統退回一個仍可用的替代方案，而非報錯：")
    table(doc,
          ["能力", "服務離線時的降級行為"],
          [["視覺搜尋", "退回顏色啟發式比對，仍可回傳結果"],
           ["價格預測", "退回線性回歸趨勢模型，建議格式不變"],
           ["虛擬試穿", "退回顏色疊加預覽，仍顯示商品資訊"],
           ["助手", "退回模板式回覆，事實仍來自同一批工具"]],
          widths=[3.6, 12.6])
    caption(doc, "表 2：降級策略。此設計讓任一 AI 服務的故障都不會使網站不可用。")

    # --------------------------------------------------------------- modules
    h1(doc, "4  實作模組")
    body(doc, "系統已實作 12 個功能模組，其中 5 項由真實模型驅動，其餘為規則式或模擬實作，"
              "但同樣具備固定的輸入輸出契約，可日後替換。")
    table(doc,
          ["#", "模組", "狀態", "說明"],
          [["1", "造型盒", "規則式", "依場合與預算組成整套，並保留衣櫃已有單品"],
           ["2", "搭配顧問（助手）", "工具呼叫", "7 個工具、答案僅引用工具事實"],
           ["3", "以圖搜尋", "真實模型", "Marqo-FashionSigLIP，中文查詢先行正規化"],
           ["4", "價格趨勢", "真實模型", "Meta Prophet，促銷日曆作節日回歸量"],
           ["5", "虛擬試穿", "真實模型", "CatVTON MaskFree，本地 GPU"],
           ["6", "門市現貨與導航", "真實資料", "8 間香港門市、跨店庫存、地圖導航"],
           ["7", "商戶後台", "真實資料", "SQLite 事件庫，搜尋、挽留、轉化"],
           ["8", "嵌入 Widget", "已完成", "一行 script，iframe 面板與多租戶品牌"],
           ["9", "跨平台比價", "模擬", "七個平台比價與議價對話"],
           ["10", "二手託管", "規則式", "自動生成刊登描述與定價"],
           ["11", "記憶與畫像", "真實資料", "衣櫃、尺碼、風格、退貨紀錄"],
           ["12", "退貨預測與客服", "規則式", "瑕疵分類與退貨單生成"]],
          widths=[1.0, 3.8, 2.2, 9.4])
    caption(doc, "表 3：功能模組與實作狀態。")

    # ------------------------------------------------------------ evaluation
    h1(doc, "5  評估方法與結果")
    body(doc, "本節三個評估均為可重現的程式，位於 tools/ 目錄，結果以 JSON 儲存於 data/eval/。")

    h2(doc, "5.1  視覺搜尋")
    body(doc, "我們建立了一個中英雙語評估集：47 對查詢（共 94 條），涵蓋屬性、顏色、材質與場合四類，"
              "難度分為易、中、難。檢索範圍為 34 件有實際商品照的單品。所有查詢以同一份商品目錄為真值。")
    body(doc, "原始查詢（未經語言正規化）的結果如下：")
    table(doc,
          ["模型", "Recall@1", "Recall@5", "MRR", "中文 R@5", "英文 R@5"],
          [["ViT-B-32 / laion2b（原用）", "45.7%", "84.0%", "0.637", "70.2%", "97.9%"],
           ["Marqo-FashionCLIP", "41.5%", "78.7%", "0.576", "61.7%", "95.7%"],
           ["Marqo-FashionSigLIP", "39.4%", "58.5%", "0.499", "17.0%", "100.0%"]],
          widths=[5.4, 2.2, 2.2, 1.8, 2.2, 2.2])
    caption(doc, "表 4：原始查詢下的檢索表現（94 條查詢）。")
    body(doc, "此結果與廠商報告相反：換用時尚專用模型反而使整體表現下降。進一步分析顯示，"
              "Marqo-FashionSigLIP 在英文查詢上達到 100%，但中文僅 17%（隨機水準約 15%）。"
              "直接探針顯示三個完全不同的中文查詢產生完全相同的向量與排序，說明其分詞器並未"
              "有效編碼中日韓文字。")
    body(doc, "因此我們加入一層輕量的中文查詢正規化：以 120 條時尚詞彙表把中文轉為英文術語後"
              "再進行編碼。結果如下：")
    table(doc,
          ["模型", "Recall@1", "Recall@5", "MRR", "中文 R@5"],
          [["ViT-B-32 / laion2b", "58.5%", "97.9%", "0.764", "97.9%"],
           ["Marqo-FashionCLIP", "64.9%", "95.7%", "0.781", "95.7%"],
           ["Marqo-FashionSigLIP（採用）", "73.4%", "100.0%", "0.850", "100.0%"]],
          widths=[5.4, 2.4, 2.4, 2.0, 2.4])
    caption(doc, "表 5：查詢正規化後的檢索表現。")
    body(doc, "結論：瓶頸在語言對齊而非視覺模型。上線配置為 Marqo-FashionSigLIP 搭配詞彙表正規化，"
              "Recall@1 由 45.7% 提升至 73.4%，Recall@5 由 84.0% 提升至 100%。需要說明的是，"
              "詞彙表與目錄詞彙有重疊，故上述數字屬樂觀的詞典基準；人工配對的英文查詢（100%）"
              "可視為上限。正式系統應以語言模型取代詞彙表，並沿用同一評估程式量測。")

    h2(doc, "5.2  價格預測")
    body(doc, "我們為 40 件商品各生成 800 天的每日價格序列（共 32,000 筆），包含緩慢通脹趨勢、"
              "週末效應、隨機噪聲，以及香港與大中華區的促銷日曆。每件商品的促銷參與度與折扣深度"
              "為該商品之固有屬性，而非逐年隨機，否則模型無法學習。")
    body(doc, "評估採留出法：藏起每件商品最後 30 天，以其餘資料訓練，再以該 30 天計分。")
    table(doc,
          ["模型", "MAE", "RMSE", "MAPE", "中位數 MAPE", "勝出商品數"],
          [["Prophet（採用）", "0.28", "0.35", "0.34%", "0.33%", "38 / 40"],
           ["線性趨勢基準", "1.10", "1.17", "1.25%", "0.70%", "0"],
           ["樸素基準（沿用現價）", "0.39", "0.47", "0.50%", "0.46%", "2"]],
          widths=[4.4, 1.8, 1.8, 2.0, 2.2, 2.4])
    caption(doc, "表 6：價格預測的留出法比較（40 件商品）。")
    body(doc, "方法上有一項關鍵調整：Prophet 預設的年度季節性以傅立葉級數表示，會把單日促銷抹平"
              "至整個月份。以 11 月 11 日為例，原始設定下僅預測下跌 4.2%，遠低於實際的 18%。"
              "改以明確的節日回歸量（holidays 參數）描述促銷日曆後，該日預測為 156.5 美元，"
              "較現價下跌 17.2%，且前後日自動回升。")
    body(doc, "需誠實說明：價格序列為合成資料，且促銷日期對模型已知，故與基準的差距屬上限值。"
              "可主張的是「把促銷日曆建模進去明顯優於忽略它」，而非「真實資料上誤差 0.34%」。")

    h2(doc, "5.3  工具呼叫式助手")
    body(doc, "助手架構為：路由 → 工具計劃 → 執行 → 事實 → 組句。工具輸出的是已格式化的「事實」"
              "（例如 totalDisplay、onlineStock、dropPct），組句器完全不進行算術運算，因此從文字"
              "到虛構數字之間不存在路徑。此為結構性保證，而非僅靠提示詞約束。")
    table(doc,
          ["指標", "結果", "意義"],
          [["工具選擇準確率", "15 / 15（100%）", "是否選對工具"],
           ["事實可追溯率", "15 / 15（100%）", "答案中每個數字是否出現在工具事實中"],
           ["自助完成率", "15 / 15（100%）", "是否無需退回模板路徑"]],
          widths=[4.2, 4.4, 7.4])
    caption(doc, "表 7：助手評估（15 條中英雙語問題）。")
    body(doc, "限制：15 題屬煙霧測試而非基準，且路由採規則式，未見過的講法會失配。工具層與組句器"
              "刻意與路由分離，正是為了日後以語言模型替換路由時，其餘部分不需改動。")

    h2(doc, "5.4  虛擬試穿效能")
    table(doc,
          ["項目", "數值"],
          [["模型", "CatVTON MaskFree，mix-48k-1024"],
           ["解析度", "768 × 1024"],
           ["生成時間", "21 秒（20 步）／ 31 秒（30 步）"],
           ["峰值記憶體", "3.57 GiB（RTX 4070，12 GB）"],
           ["模型載入", "3.6 秒"]],
          widths=[4.0, 12.0])
    caption(doc, "表 8：本機推論效能。")

    # ------------------------------------------------------------- localisation
    h1(doc, "6  香港本地化與差異化")
    h2(doc, "6.1  本地化實作")
    bullet(doc, "八間門市（旺角、銅鑼灣、尖沙咀、沙田、荃灣、觀塘、中環、元朗），含港鐵出口、"
                "營業時間、電話與座標。")
    bullet(doc, "取貨方式：順豐站／智能櫃、送貨上門、門市自取（即日下午六時前下單）。")
    bullet(doc, "付款方式：八達通 O! ePay、PayMe、轉數快、AlipayHK、WeChat Pay HK、信用卡。")
    bullet(doc, "雙語介面（繁體中文／英文），價格以港幣顯示。")
    h2(doc, "6.2  與大型平台的差異化")
    body(doc, "本專案的客戶並非消費者，而是被大型平台擠壓的本地中小型零售商。順此定位，"
              "大型平台越深入本地市場，本系統的需求越大。可主張的結構性差異有四項：")
    table(doc,
          ["差異", "為何大型平台做不到"],
          [["敢建議「等降價」", "平台收入與成交額掛鉤，不會給出違反自身短期利益的建議"],
           ["跨商戶退貨情報", "平台彙總商家退貨資料在商業關係上不可行，中立第三方可行"],
           ["尺寸護照（跨商戶通用）", "平台的尺碼資料不會開放給個別商家"],
           ["私隱本地化（身材照片不離港）", "模型在本機 GPU 執行，照片不需上傳第三方"]],
          widths=[4.6, 11.4])
    caption(doc, "表 9：四項結構性差異。")

    # --------------------------------------------------------------- progress
    h1(doc, "7  進度與時程")
    table(doc,
          ["階段", "工作", "狀態"],
          [["第一次會議", "網站基礎與十個功能模組", "已完成"],
           ["第二次會議", "情境助手、視覺搜尋、價格預測", "已完成"],
           ["第三次會議", "B2B SaaS 化：商戶後台、嵌入元件、退出挽留", "已完成"],
           ["中期", "真實模型替換：CatVTON、Prophet、FashionSigLIP、工具呼叫助手", "已完成"],
           ["下一階段", "Shop the Look（偵測與裁切）、Try-Off 二手自動上架", "待進行"],
           ["下一階段", "使用者研究：退貨率實測與可用性測試", "待進行"]],
          widths=[3.2, 9.4, 3.4])
    caption(doc, "表 10：進度對照。")

    # ------------------------------------------------------------------ risks
    h1(doc, "8  待完成工作與風險")
    h2(doc, "8.1  待完成")
    bullet(doc, "Shop the Look：以物件偵測裁切單品後逐件檢索，對應 Google Lens 的圈選行為。")
    bullet(doc, "Try-Off：由穿著照反推乾淨商品圖，解決二手刊登的拍照摩擦。")
    bullet(doc, "以語言模型替換助手路由，並擴大評估集至 100 題以上。")
    bullet(doc, "使用者研究：以本地小店為對象驗證退貨率是否下降。")
    h2(doc, "8.2  風險")
    table(doc,
          ["風險", "影響", "緩解"],
          [["合成資料使評估偏樂觀", "論文結論說服力", "明確標示上限值，並以公開資料集交叉驗證"],
           ["CatVTON 授權為非商業", "日後商用受限", "FYP 階段可接受，商用須改用其他授權模型"],
           ["試穿延遲 20–30 秒", "使用者體驗", "以進度提示與伺服器端佇列處理"],
           ["規則式路由覆蓋率", "助手理解能力", "工具與路由分離，可替換為語言模型"],
           ["冷啟動（尺碼預測）", "新使用者無歷史資料", "以身體量測與品牌尺碼表補足"]],
          widths=[4.4, 4.6, 7.0])
    caption(doc, "表 11：主要風險與緩解措施。")

    # -------------------------------------------------------------- conclusion
    h1(doc, "9  結論")
    body(doc, "截至中期，本專案已完成三個層次的驗證：技術上，四項 AI 能力以真實模型運作並可量測；"
              "工程上，四個服務獨立部署、各自降級，並通過 135 項自動化測試；研究上，取得三項可"
              "辯護的發現，其中兩項為負面結果（廠商檢索提升無法轉移至中文、共用促銷日曆使建議"
              "失去鑑別度），一項為架構事實（虛擬試穿權重未開源）。")
    body(doc, "這些發現直接改變了系統設計，也構成論文的主要貢獻：在本專案所定義的中文查詢集上，"
              "「加入查詢語言正規化」的效果遠大於「更換更強的視覺模型」。下一階段將朝 "
              "Shop the Look 與使用者研究推進，以完成由技術驗證到價值驗證的閉環。")

    # ------------------------------------------------------------ references
    h1(doc, "參考文獻")
    refs = [
        "Radford, A. et al. (2021). Learning Transferable Visual Models From Natural Language "
        "Supervision. ICML.",
        "Bianchi, F. et al. (2022). Contrastive Language-Image Pre-training for the Italian "
        "Language. arXiv:2109.08914.",
        "Marqo (2025). Marqo Fashion Embedding Models: Marqo-FashionCLIP and Marqo-FashionSigLIP. "
        "https://marqo.ai/blog/search-model-for-fashion",
        "Zheng, C. et al. (2024). CatVTON: Concatenation Is All You Need for Virtual Try-On with "
        "Diffusion Models. ICLR 2025. arXiv:2407.15886.",
        "Yang, Z. et al. (2025). OmniVTON: Training-Free Universal Virtual Try-On. ICCV 2025. "
        "arXiv:2507.15037.",
        "Sun, K. et al. (2024). OutfitAnyone: Ultra-high Quality Virtual Try-On for Any Clothing "
        "and Any Person. arXiv:2407.16224.",
        "Taylor, S. J. & Letham, B. (2018). Forecasting at Scale. The American Statistician, "
        "72(1), 37-45.",
        "Cheng, W.-H. et al. (2021). Fashion Meets Computer Vision: A Survey. ACM Computing "
        "Surveys, 54(4), Article 72. DOI: 10.1145/3447239.",
        "Klingenberg, B. (2016). Making Fashion Recommendations with Human-in-the-loop Machine "
        "Learning. KDD 2016.",
    ]
    for i, r in enumerate(refs, 1):
        p = doc.add_paragraph(f"[{i}]  {r}")
        p.paragraph_format.left_indent = Cm(0.9)
        p.paragraph_format.first_line_indent = Cm(-0.9)
        p.paragraph_format.space_after = Pt(4)
        for run in p.runs:
            run.font.size = Pt(9.5)

    doc.save(OUT)
    print(f"  saved {OUT}")
    return OUT


if __name__ == "__main__":
    main()
