"""Build the one-hour code-reading guide for SmartMall.

Audience: the author, a week later, or a supervisor who wants to understand what
was built without reading 6,500 lines. Every number and file size below was
measured from the repository.

Run:  <bundled python> tools/build_code_guide.py
"""
import os
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Cm, RGBColor

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "程式導讀 - 一小時讀懂 SmartMall.docx")

LATIN = "Calibri"
MONO = "Consolas"
CJK = "Microsoft JhengHei"
ACCENT = RGBColor(0x35, 0x2C, 0xA8)
CODE_BG = "F4F4F7"
BOX_BG = "EEF3FF"


def set_fonts(rpr):
    rf = rpr.rFonts
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    rf.set(qn("w:eastAsia"), CJK)
    rf.set(qn("w:ascii"), LATIN)
    rf.set(qn("w:hAnsi"), LATIN)


def shade(paragraph, fill):
    pPr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    pPr.append(shd)


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
    doc.styles["Normal"].font.size = Pt(10)
    doc.styles["Normal"].paragraph_format.space_after = Pt(5)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.22
    for name, size in (("Heading 1", 15), ("Heading 2", 12.5), ("Title", 24)):
        try:
            doc.styles[name].font.size = Pt(size)
            doc.styles[name].font.color.rgb = ACCENT
        except KeyError:
            pass
    for s in doc.sections:
        s.top_margin = Cm(2.0)
        s.bottom_margin = Cm(2.0)
        s.left_margin = Cm(2.2)
        s.right_margin = Cm(2.2)


def h1(doc, text):
    p = doc.add_heading(text, level=1)
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(5)
    return p


def h2(doc, text):
    p = doc.add_heading(text, level=2)
    p.paragraph_format.space_before = Pt(9)
    p.paragraph_format.space_after = Pt(3)
    return p


def body(doc, text, bold_lead=None):
    p = doc.add_paragraph()
    if bold_lead:
        r = p.add_run(bold_lead)
        r.bold = True
    p.add_run(text)
    return p


def bullet(doc, text, bold_lead=None):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Cm(0.7)
    p.paragraph_format.space_after = Pt(2)
    if bold_lead:
        r = p.add_run(bold_lead)
        r.bold = True
    p.add_run(text)
    return p


def code(doc, text, size=8.5):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.4)
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.1
    shade(p, CODE_BG)
    for i, line in enumerate(text.rstrip("\n").split("\n")):
        if i:
            p.add_run().add_break()
        r = p.add_run(line)
        r.font.name = MONO
        r.font.size = Pt(size)
        r.font.color.rgb = RGBColor(0x22, 0x22, 0x2A)
    return p


def callout(doc, text, bold_lead="重點： "):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.3)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(7)
    shade(p, BOX_BG)
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), "18")
    left.set(qn("w:space"), "6")
    left.set(qn("w:color"), "352CA8")
    bdr.append(left)
    pPr.append(bdr)
    if bold_lead:
        r = p.add_run(bold_lead)
        r.bold = True
        r.font.color.rgb = ACCENT
    p.add_run(text)
    return p


def table(doc, headers, rows, widths=None, size=8.8):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, htxt in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(htxt)
        r.bold = True
        r.font.size = Pt(size)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v))
            r.font.size = Pt(size)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return t


def main():
    doc = Document()
    setup(doc)

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("SmartMall 程式導讀")
    r.bold = True
    r.font.size = Pt(24)
    r.font.color.rgb = ACCENT
    s = doc.add_paragraph()
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rs = s.add_run("一小時讀懂：做了什麼、怎麼做到、程式碼在哪裡、每段在做什麼")
    rs.font.size = Pt(13)
    rs.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
    doc.add_paragraph()

    # ---------------------------------------------------------------- how to read
    h1(doc, "0  怎麼讀這份文件")
    body(doc, "這份文件假設你一小時後要能回答三個問題：這個系統做了什麼、關鍵技術怎麼實現、"
              "某個功能要去哪個檔案改。全文約 6,500 行程式碼的摘要，不需要先讀程式碼。")
    table(doc, ["時間", "路線", "讀哪幾節"],
          [["15 分鐘", "只看骨架", "第 1 節（系統是什麼）+ 第 2 節（檔案地圖）"],
           ["35 分鐘", "理解四項 AI 能力", "第 3 節的 3.1 至 3.4 + 第 4 節的困難總表"],
           ["60 分鐘", "完整讀完", "全部，包含第 4 節的困難、第 7 節的改動指引、第 9 節的最新進展"]],
          widths=[2.2, 4.2, 9.2])
    callout(doc, "全部程式碼約 6,500 行，但真正承載技術含量的是其中約 900 行 —— 三個 Python 服務的"
                 "模型呼叫，加上助手的事實層。其餘是店面、資料與介面。")

    # ---------------------------------------------------------------- what
    h1(doc, "1  這個系統是什麼")

    h2(doc, "1.1  一句話")
    body(doc, "一個面向香港中小型服飾零售商的 AI 電商系統：客人描述場合就有整套搭配、上傳照片就找到同款、"
              "買之前知道價格會不會跌、線上缺貨時知道哪間門市有、下單前就提醒你這個尺碼可能不合。")

    h2(doc, "1.2  為什麼要分成四個服務")
    body(doc, "這是整個專案最重要的架構決定。四個服務各自獨立啟動，其中三個會載入機器學習模型。")
    table(doc, ["服務", "埠", "技術", "載入時間", "關掉會怎樣"],
          [["網站", "3000", "Node.js 內建模組", "即時", "（這是主體）"],
           ["視覺搜尋", "8001", "Marqo-FashionSigLIP + FAISS", "約 5 秒", "退回顏色比對"],
           ["價格預測", "8002", "Meta Prophet", "約 2 秒", "退回線性趨勢"],
           ["虛擬試穿", "8003", "CatVTON（GPU）", "約 15 秒", "退回顏色疊加預覽"]],
          widths=[2.8, 1.2, 6.2, 2.2, 4.2])
    callout(doc, "任何一個 AI 服務關掉，網站都還能用。這不是巧合，是設計目標 —— 每個功能都有明確的降級路徑。"
                 "這也是為什麼示範時不怕某個服務啟動失敗。")

    h2(doc, "1.3  一次搜尋的資料流")
    body(doc, "以「上傳照片找同款」為例，資料經過四層：")
    code(doc, """瀏覽器  ──POST /api/visual-search──▶  server.js（路由）
                                            │
                                            ▼
                                  lib/visualSearch.js（決策：CLIP 還是顏色）
                                            │
                                            ▼ HTTP
                          ai-service/visual_search_service.py（模型）
                                            │
                        ① 中文查詢 → 英文術語（詞彙表）
                        ② 圖片 + 文字 → CLIP 向量，加權融合
                        ③ FAISS 內積檢索
                                            │
                                            ▼ 回傳 id + 相似度
                            lib/clipClient.js（分數換算成 0-100%）
                                            │
                                            ▼
                                  前端 productCard 顯示""")
    body(doc, "四層的分工是：Node 只做路由與 I/O、lib 決定用哪個模型、Python 跑模型、前端只負責畫。")

    # ---------------------------------------------------------------- file map
    h1(doc, "2  檔案地圖：每個檔案在做什麼")

    h2(doc, "2.1  後端核心")
    table(doc, ["檔案", "行數", "職責", "什麼時候會讀它"],
          [["server.js", "472", "HTTP 路由、靜態檔、20+ 個 API 端點", "加 API、改路由"],
           ["lib/store.js", "144", "商品目錄、個人檔案、幣別換算", "改商品資料結構"],
           ["lib/analytics.js", "274", "SQLite 事件庫、優惠券、商戶後台統計", "改後台指標"],
           ["lib/memory.js", "215", "衣櫃、退貨紀錄、長期偏好", "改記憶邏輯"],
           ["lib/blindbox.js", "421", "依場合與預算組整套裝備", "改造型盒"],
           ["lib/assistant.js", "503", "舊版模板助手（現在是備援）", "只在 agent 失敗時跑"]],
          widths=[3.4, 1.1, 7.4, 4.6])

    h2(doc, "2.2  四個 AI 能力對應的檔案")
    table(doc, ["能力", "Node 端", "Python 端", "模型"],
          [["視覺搜尋", "visualSearch.js (120)\nclipClient.js (54)", "visual_search_service.py (257)", "Marqo-FashionSigLIP"],
           ["價格預測", "forecast.js (142)\nprophetClient.js (41)", "forecast_service.py (339)", "Meta Prophet"],
           ["虛擬試穿", "tryon.js (111)", "tryon_service.py (198)", "CatVTON MaskFree"],
           ["助手", "agent/tools.js (244)\nagent/router.js (121)\nagent/index.js (230)", "（無）", "規則式路由 + 7 個工具"]],
          widths=[2.6, 4.6, 4.6, 4.2])

    h2(doc, "2.3  其餘模組")
    table(doc, ["檔案", "行數", "做什麼"],
          [["lib/stores.js", "105", "八間門市、跨店庫存、haversine 距離"],
           ["lib/returnPredict.js", "133", "依身型與退貨史預測退貨風險、建議尺碼"],
           ["lib/support.js", "242", "退貨流程、瑕疵分類、退貨單"],
           ["lib/priceAgent.js", "173", "七平台比價與議價對話（模擬）"],
           ["lib/resale.js", "214", "二手刊登描述與定價"],
           ["lib/social.js", "193", "好友私密投票"],
           ["lib/clipClient.js", "54", "CLIP 服務的 HTTP 客戶端 + 分數校準"]],
          widths=[3.6, 1.2, 11.8])

    h2(doc, "2.4  前端")
    table(doc, ["檔案", "行數", "做什麼"],
          [["public/js/app.js", "131", "SPA 路由、頁首搜尋、初始化"],
           ["public/js/i18n.js", "630", "全站中英文字典（最大的一個檔，內容是字串）"],
           ["public/js/views/*.js", "2,507（15 檔）", "每個頁面一個檔"],
           ["public/js/widget.js", "245", "嵌入式面板（iframe 內執行）"],
           ["public/js/chart.js", "88", "手寫 SVG 折線圖（含信賴區間）"],
           ["public/js/exitIntent.js", "154", "離開意圖偵測與優惠券"],
           ["public/css/styles.css", "791", "全部樣式，深色主題在 :root"]],
          widths=[4.4, 2.6, 9.6])
    callout(doc, "i18n.js 佔 630 行但幾乎都是字串，不是邏輯。讀程式時可以整檔跳過。",
            bold_lead="提醒： ")

    h2(doc, "2.5  工具與測試")
    body(doc, "tools/ 目錄有 36 個檔案，分成三類：")
    bullet(doc, "評估：eval_retrieval.py、eval_forecast.py、eval_assistant.py —— 產生論文裡的三張表")
    bullet(doc, "測試：test_site_regression.py 等 7 個套件，共 135 項檢查")
    bullet(doc, "產生器：build_price_history.py、prepare_catvton_base.py、build_interim_report.py —— 產生資料與文件")

    # ---------------------------------------------------------------- deep dives
    h1(doc, "3  五個核心技術，怎麼做到的")

    h2(doc, "3.1  視覺搜尋：真正的發現是「中文沒被編碼」")
    body(doc, "直覺做法是「換一個更強的時尚模型」。我們實測後發現這是錯的。")
    body(doc, "先建立 94 條中英雙語查詢（47 對）作為評測集，然後比較三個模型：")
    table(doc, ["模型", "Recall@1", "Recall@5", "中文 R@5", "英文 R@5"],
          [["原本的 CLIP（ViT-B-32）", "45.7%", "84.0%", "70.2%", "97.9%"],
           ["Marqo-FashionCLIP", "41.5%", "78.7%", "61.7%", "95.7%"],
           ["Marqo-FashionSigLIP", "39.4%", "58.5%", "17.0%", "100.0%"]],
          widths=[5.4, 2.4, 2.4, 2.4, 2.4])
    body(doc, "三個不同中文查詢（滑雪外套／滑雪護目鏡／真皮樂福鞋）產生完全相同的向量與排序。"
              "分詞器把中日韓文字壓成同一序列 —— 等於沒有讀進去。而同一模型在英文上是 100%。")
    body(doc, "所以修法不是換模型，是在編碼前先把中文查詢轉成英文時尚術語：")
    code(doc, """# ai-service/visual_search_service.py
def translate_query(text):
    # 以 120 條詞彙表做最長匹配替換
    # 「滑雪外套」→「ski jacket」；「亞麻」→「linen」
    ...
    return translated or text

def encode_text(text):
    text = translate_query(text)          # ← 關鍵的一行
    tok = _state["tokenizer"]([text]).to(_state["device"])
    f = _state["model"].encode_text(tok)
    return f / f.norm(dim=-1, keepdim=True)""")
    body(doc, "加上這一行之後：Recall@1 45.7% → 73.4%，Recall@5 84.0% → 100.0%。")
    callout(doc, "論文的價值就在這裡：廠商宣稱的 +57% 在這份中文查詢集上不成立，"
                 "而真正的瓶頸是語言對齊，不是視覺模型。")

    h2(doc, "3.2  價格預測：把促銷日曆當成節日回歸量")
    body(doc, "Prophet 預設的年度季節性是傅立葉級數，會把「單日」促銷抹平到整個月。"
              "以雙十一為例，預設設定只預測下跌 4.2%，實際是 18%。")
    body(doc, "解法是把促銷日當成明確的節日（holidays 參數），讓每一天有自己的係數：")
    code(doc, """# ai-service/forecast_service.py
SALES = [
    ("double11",    "11-11", 2, 1, "雙十一 Double 11"),
    ("black-friday","11-27", 1, 3, "黑色星期五 Black Friday"),
    ("christmas",   "12-25", 3, 2, "聖誕節 Christmas"),
    ...
]
# 每一天送入 Prophet 成為一個 dummy regressor
rows.append({"holiday": name, "ds": pd.Timestamp(f"{y}-{md}"),
             "lower_window": -lo, "upper_window": hi})

m = Prophet(holidays=pd.DataFrame(rows), ...)""")
    body(doc, "結果：40 件商品留出法比較，MAE 0.28、MAPE 0.34%，勝過線性基準（1.25%）"
              "與樸素基準（0.50%），40 件中勝出 38 件。")
    body(doc, "誠實的限制：價格序列是合成的，且促銷日期對模型已知，所以這是上限值。"
              "可主張的是「建模促銷日曆優於忽略它」，不是「真實資料上誤差 0.34%」。")

    h2(doc, "3.3  虛擬試穿：兩個坑")
    body(doc, "第一個坑：最知名的 Outfit Anyone 權重沒有開源，官方展示只允許上傳衣服、人像為預設，"
              "做不到「客人上傳自己的照片」。改用 CatVTON（ICLR 2025）。")
    body(doc, "第二個坑：CatVTON 的 GitHub repo 需要 agnostic mask（要 detectron2），"
              "而在 Windows 上裝不起來。正解是使用 Hugging Face Space 原始碼裡的 "
              "CatVTONPix2PixPipeline —— 它把人物與衣服的 latent 直接拼接，完全不需要 mask。")
    body(doc, "另外要注意 base model 的通道數：pix2pix 版需要 8 通道（instruct-pix2pix），"
              "用一般的 SD-inpainting（9 通道）會報 expected 9 channels, but got 8。")
    body(doc, "第三個坑是使用者實際遇到的：臉被切掉。原因是 pipeline 的 resize_and_crop 會置中裁切到 3:4，"
              "而直式手機照片比 3:4 高，上下各被裁掉一段，上面那一段就是頭。修法是先補邊：")
    code(doc, """# ai-service/tryon_service.py
def fit_to_target(img, tw=WIDTH, th=HEIGHT):
    # 先把照片補成 3:4，pipeline 的裁切就變成空操作
    if w / h < target:                    # 太高 → 補左右
        new_w, new_h = int(round(h * target)), h
    ...
    backdrop = backdrop.filter(ImageFilter.GaussianBlur(28))   # 模糊背景
    backdrop.paste(img, ((new_w - w) // 2, (new_h - h) // 2))  # 人像置中
    return backdrop""")
    body(doc, "效能：768×1024、20 步約 21 秒、峰值記憶體 3.57 GiB（RTX 4070 12 GB）。")

    h2(doc, "3.4  助手：讓幻覺在結構上不可能")
    body(doc, "一般做法是叫語言模型回答商品問題，它會編造價格。這專案的做法是讓模型只負責選擇工具與措辭，"
              "所有數字來自工具：")
    code(doc, """問題 ──▶ 路由（規則式） ──▶ 工具計劃 ──▶ 執行 ──▶ 事實 ──▶ 組句 ──▶ 答案

工具回傳的是「已格式化的數字」：
  facts.push({ label: 'totalDisplay', value: 'HK$889' })
  facts.push({ label: 'onlineStock',  value: '8' })
  facts.push({ label: 'dropPct',      value: '11.6' })

組句器只讀這些事實，完全不做算術運算。
→ 文字與虛構數字之間沒有路徑。""")
    body(doc, "七個工具：search_products、check_store_stock、forecast_price、size_advice、"
              "build_outfit、recall_wardrobe、list_stores。")
    body(doc, "多工具串接靠一個佔位符：路由先產生 search_products，把結果的 top id 代入後續工具的 "
              "$find.top。")
    code(doc, """// lib/agent/index.js
if (params.productId === '$find.top') {
  if (!findTopId) { /* 沒有商品就跳過，不猜 */ }
  params.productId = findTopId;
}""")
    body(doc, "評估：15 條中英問題，工具選擇 15/15、事實可追溯 15/15、自助完成 15/15。")

    h2(doc, "3.5  商戶後台：用 Node 內建 SQLite，零依賴")
    body(doc, "不引入 npm 套件，直接用 Node 的 node:sqlite。事件表與優惠券表：")
    code(doc, """// lib/analytics.js
CREATE TABLE events (
  id INTEGER PRIMARY KEY, tenant TEXT, session TEXT,
  type TEXT, label TEXT, value REAL, meta TEXT, createdAt TEXT
);
CREATE TABLE coupons (
  code TEXT PRIMARY KEY, tenant TEXT, discountPct REAL,
  status TEXT, issuedAt TEXT, appliedAt TEXT
);""")
    body(doc, "後台的每個指標都是一條 SQL 聚合：搜尋次數、訪客數、挽留成功率（領券／彈出）、轉化率。"
              "資料庫首次啟動會 seed 七天的示範資料，所以後台不會是空的。")

    # ---------------------------------------------------------------- troubles
    h1(doc, "4  遇到的困難與怎麼解決的")
    body(doc, "這一節記錄實際卡住的地方。多數不是「模型不夠好」，而是環境、資料結構與假設錯誤。"
              "先看總表，再看 4.2 的三個教訓。")

    h2(doc, "4.1  問題總表")
    table(doc, ["問題", "症狀", "根因", "解法（動到的檔案）"],
          [["pip 安裝卡死", "628 秒 CPU、零下載", "沙箱禁止寫入 workspace 以外的 site-packages",
            "改用 workspace venv + uv（.venv/）"],
           ["CUDA torch 被換掉", "torch.cuda.is_available() = False",
            "uv 安裝時解析到 CPU 版 torch，覆蓋 2.10.0+cu128",
            "uv pip uninstall torch；每次裝完都檢查（曾發生兩次）"],
           ["中文檢索幾乎失效", "中文 R@5 只有 17%（隨機約 15%）",
            "分詞器把 CJK 壓成同一序列，三個不同查詢得到相同向量",
            "加入 zh→en 時尚詞彙表（data/fashion-glossary.json）"],
           ["雙十一預測不出來", "預測只跌 4.2%，實際 18%",
            "Prophet 年度季節性用傅立葉級數，把單日促銷抹平",
            "改用 holidays 參數（forecast_service.py 的 SALES）"],
           ["Prophet 輸給樸素基準", "MAPE 0.37% → 0.61%",
            "促銷參與改成「每年隨機」，效應逐年翻轉，模型無法學習",
            "參與度改為商品固有屬性（build_price_history.py）"],
           ["所有商品建議都一樣", "40 件全部「建議等降價」",
            "所有商品共用同一份促銷日曆",
            "加入商品層級的參與率與折扣深度"],
           ["試穿模型無法使用", "無法上傳人像",
            "Outfit Anyone 權重從未開源，官方展示只收衣服",
            "改用 CatVTON（ICLR 2025）"],
           ["CatVTON 裝不起來", "匯入失敗 / 缺 detectron2",
            "GitHub repo 的 pipeline 需要 agnostic mask",
            "改用 HF Space 原始碼的 CatVTONPix2PixPipeline（無需 mask）"],
           ["通道數不符", "expected 9 channels, but got 8",
            "pix2pix pipeline 要 8 通道 base，誤用 9 通道的 SD-inpainting",
            "改用 timbrooks/instruct-pix2pix"],
           ["fp16 權重載入失敗", "找不到 diffusion_pytorch_model.safetensors",
            "pipeline 呼叫時沒帶 variant=\"fp16\"，只下載了 fp16 檔",
            "建 local snapshot 把 fp16 檔改成標準檔名（硬連結，不佔空間）"],
           ["試穿把臉切掉", "看不到臉／頭頂被裁",
            "resize_and_crop 置中裁切到 3:4，直式照片上下各被裁",
            "推論前先補邊（tryon_service.py 的 fit_to_target）"],
           ["造型盒配錯品類", "滑雪情境配出牛仔外套",
            "只按預算取最便宜，沒有相關性門檻",
            "加入 score ≥ max(2.5, top×0.5) 的門檻（blindbox.js）"],
           ["瑕疵分類永遠回傳褪色", "所有照片都判「褪色」",
            "絕對閾值對不同光線的照片不成立",
            "改為與乾淨照片的「超額量」相對比較（support.js）"],
           ["助手聽不懂中文", "整句被當成一個 token，永遠 0 結果",
            "中文沒有空格，whitespace 分詞失效",
            "改用 CJK 二元組切詞（lib/agent/tools.js）"],
           ["助手弄丟記憶功能", "回歸測試失敗：不再提及衣櫃",
            "改寫成 agent 時漏掉舊版行為",
            "補上 recall_wardrobe 工具（tools.js + index.js）"],
           ["答案出現「無依據」數字", "HK$889 被判為非事實",
            "組句器自己做幣別換算（×7.8）",
            "把換算搬進工具，只輸出已格式化的事實"],
           ["簡報文字看不見", "深色底上深色字",
            "沿用來源範本主題色",
            "整份改為淺色文字 + 黃色重點"],
           ["英文簡報標題全大寫", "RESULT 1: IMAGE SEARCH",
            "範本 title style 帶 cap=\"all\"，中文沒有大小寫所以從未發現",
            "對每個 run 設 cap=\"none\""],
           ["模型權重會撐爆 GitHub", "push 會失敗",
            "data/models 有 4 GB，且未被 .gitignore 排除",
            "加入 data/models/ 與 *.safetensors 規則"]],
          widths=[3.4, 3.6, 5.0, 5.2], size=8.2)

    h2(doc, "4.2  三個值得記住的教訓")

    body(doc, "① 症狀出現在 A，根因常在 B。", bold_lead=None)
    body(doc, "「中文搜尋很爛」看起來是模型問題，換更強的模型反而更差（84% → 58.5%）。"
              "真正的原因要一個探針才看得出來：")
    code(doc, """# 三個完全不同的查詢，向量竟然一樣
for q in ['滑雪外套', '滑雪護目鏡', '真皮樂福鞋']:
    print(model.encode_text(q))     # 幾乎完全相同

# 而同一模型在英文上是 100%
print(model.encode_text('ski jacket'))""")
    body(doc, "沒有這個探針，就會一直在「換模型」的方向上燒時間。"
              "教訓：先確認「輸入有沒有被正確讀進去」，再討論模型好壞。")

    body(doc, "② 環境問題比程式問題更花時間。", bold_lead=None)
    body(doc, "同一件事發生兩次：安裝 open_clip 與 diffusers 時，套件管理器都自動把 CUDA 版 torch "
              "換成 CPU 版。程式碼完全沒問題，但整個推論層變成龜速或直接失敗。")
    code(doc, """.venv\\Scripts\\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
# 2.14.1+cpu False        ← 壞了
# 2.10.0+cu128 True       ← 修好後

# 修法
.venv\\Scripts\\python.exe -m pip uninstall torch torchvision""")
    callout(doc, "現在每次安裝任何套件後，第一件事就是跑上面那行檢查。這一條已寫進 SETUP.md。")

    body(doc, "③ 回歸測試會抓到你以為不重要的東西。", bold_lead=None)
    body(doc, "把助手改寫成工具呼叫架構後，所有新功能都通過，但舊的回歸測試失敗了 —— "
              "它記得「以你三個月前買的亞麻襯衫為基礎」。這是專案的差異化功能之一，"
              "在改寫時被無聲地丟掉了。")
    body(doc, "修法不是刪掉那個測試，而是把記憶做成一個工具（recall_wardrobe），讓新架構也能用到它。"
              "教訓：測試失敗時，先問「是不是真的掉了功能」，再問「測試是不是過時了」。")

    body(doc, "還有一個無法解決的限制，必須誠實記錄：這台機器無法啟動 headless Chrome"
              "（sandbox 阻擋 crashpad），所以整個專案的網頁外觀都沒有經過視覺驗證，"
              "只能靠「零個亮色背景、語法正確、135 項測試通過」來間接確認。")

    # ---------------------------------------------------------------- frontend
    h1(doc, "5  前端怎麼運作")
    body(doc, "沒有框架、沒有建置步驟。瀏覽器直接載入 ES module。")
    table(doc, ["機制", "在哪裡", "怎麼做"],
          [["路由", "app.js 的 render()", "監聽 hashchange，用 switch 分派到 views/*.js"],
           ["雙語", "i18n.js", "t(key) 查字典；切換語言時重畫整頁"],
           ["圖表", "chart.js", "手寫 SVG 折線，含 Prophet 的 80% 信賴區間陰影"],
           ["深色主題", "styles.css 的 :root", "改 CSS 變數即可全站生效"],
           ["動畫", "styles.css 末段", "路由淡入、卡片交錯、hover 上移，並尊重 prefers-reduced-motion"]],
          widths=[2.6, 4.4, 9.6])

    # ---------------------------------------------------------------- verify
    h1(doc, "6  怎麼驗證它還能跑")
    code(doc, """# 七個套件、135 項檢查
foreach ($t in "site_regression","visual_e2e","stores_e2e","forecast_e2e",
               "analytics_e2e","widget_e2e","tryon_e2e") {
  .venv\\Scripts\\python.exe "tools\\test_$t.py" "http://127.0.0.1:3000"
}

# 重現論文的三張表
.venv\\Scripts\\python.exe tools\\eval_retrieval.py
.venv\\Scripts\\python.exe tools\\eval_forecast.py
.venv\\Scripts\\python.exe tools\\eval_assistant.py""")
    body(doc, "服務沒開時，相依的測試會跳過或降級而不是失敗 —— 所以部分安裝也能誠實回報。")

    # ---------------------------------------------------------------- how to change
    h1(doc, "7  我要改 X，該動哪裡")
    table(doc, ["我想改…", "動這個檔案", "注意"],
          [["商品資料", "data/products.json", "改了要重建索引：tools/build_clip_index.py"],
           ["任何中英文文案", "public/js/i18n.js", "zh 與 en 兩塊都要加"],
           ["顏色 / 間距 / 圓角", "public/css/styles.css 的 :root", "改變數即可全站生效"],
           ["某個頁面的版面", "public/js/views/<頁面>.js", "一個檔案一個頁面"],
           ["加一個新頁面", "views/ 新增檔 + app.js 的 switch + i18n", "三處都要改"],
           ["視覺搜尋的模型", "ai-service/visual_search_service.py 的 MODEL", "換模型必須重建索引"],
           ["價格預測的邏輯", "ai-service/forecast_service.py 的 SALES / _fit", "改完看 eval_forecast"],
           ["助手的理解能力", "lib/agent/router.js 的關鍵詞", "工具與組句不用動"],
           ["助手能回答的事實", "lib/agent/tools.js", "新增工具要同時加 facts"],
           ["門市資料", "data/stores.json", "庫存由 lib/stores.js 依 id 決定"]],
          widths=[3.6, 6.4, 6.6])

    # ---------------------------------------------------------------- glossary
    h1(doc, "8  名詞表")
    table(doc, ["名詞", "一句話解釋"],
          [["CLIP", "把圖片與文字映射到同一個向量空間的模型，所以可以用文字找圖片"],
           ["FAISS", "Facebook 的向量檢索庫；本專案用 IndexFlatIP 做精確餘弦搜尋"],
           ["Recall@K", "前 K 個結果中包含正確答案的比例，越高越好"],
           ["MRR", "正確答案排名的倒數平均，衡量「排得多前面」"],
           ["留出法 (holdout)", "藏起最後一段資料不訓練，只用來評分，避免自我感覺良好"],
           ["MAE / MAPE", "平均絕對誤差 / 平均絕對百分比誤差，越小越準"],
           ["holiday regressor", "把特定日期當成特徵，讓模型學到「這天會特別」"],
           ["降級 (degradation)", "服務失效時退回一個仍可用的替代方案，而不是報錯"],
           ["事實 (facts)", "工具回傳的結構化數字，組句器只能引用這些"],
           ["O2O", "線上到線下：線上缺貨時引導到實體門市"],
           ["FFP / 事實可追溯率", "答案中的每個數字都能對應到某次工具呼叫"]]  ,
          widths=[3.4, 13.2])

    # ---------------------------------------------------------------- update
    h1(doc, "9  中期報告之後新增的部分")
    body(doc, "第 1 至 8 節是在中期報告那個時間點寫的。這一節記錄之後新增的東西 —— "
              "三個功能、Mac 支援、部署，以及過程中挖出來的六個 bug。")

    h2(doc, "9.1  三個新功能")

    table(doc, ["功能", "網址", "解決什麼問題", "核心機制"],
          [["虛擬衣櫃", "#/closet", "買過的衣服買完就消失在網站裡",
            "衣櫃商品一鍵試穿；照片壓到 720px 存在瀏覽器，不上傳"],
           ["偏好問卷＋抽獎轉盤", "#/survey", "冷啟動：不知道新客人的品味",
            "三題兩兩比較 → Bradley-Terry 學習 → 轉盤發 HK$1–10 券"],
           ["穿搭評分 AesRec", "#/aesthetic", "「這套襯唔襯我」沒有人能回答",
            "衣櫃向量比對 + 品類偵測 + 配色分析 → 0–100 分並附理由"]],
          widths=[3.0, 1.8, 5.0, 7.0])

    body(doc, "三個功能共用同一條主線：用客人自己的資料取代通用模型。"
              "衣櫃用他買過的衣服、問卷用他做的選擇、評分用他衣櫃的向量中心。")

    h2(doc, "9.2  怎麼做的")

    body(doc, "① 虛擬衣櫃：把「照片」留在瀏覽器")
    code(doc, """// public/js/closetPhoto.js
// localStorage 只有約 5 MB，手機照片 4 MB 存不進去
const scale = Math.min(1, 720 / Math.max(img.width, img.height));
canvas.toDataURL('image/jpeg', 0.82);   // 約 120 KB

// 試穿頁進來時自動還原，所以「一鍵試穿」是真的只有一次點擊
const saved = loadPhoto();
if (saved) { /* 無提示地載入，不跳 toast */ }""")
    body(doc, "關鍵決定是照片不上傳伺服器。試穿時直接送給本機的 CatVTON，"
              "衣櫃頁也寫明這件事 —— 這正好支撐「私隱本地化」那個差異化論點。")

    body(doc, "② 偏好問卷：用「比較」而不是「評分」，並按資訊價值付錢")
    code(doc, """// lib/survey.js
// Bradley-Terry：A 勝 B 的機率 = sigmoid(s_A - s_B)
const p = 1 / (1 + Math.exp(-(score(winner) - score(loser))));
const delta = 0.35 * (1 - p);
state.scores[winner] += delta;
state.scores[loser]  -= delta;

// 選題：模型最分不清、又最少被比較的那一對最有價值
uncertainty = closeness(1/(1+gap*2.5)) * novelty(1/sqrt(1+seen)) + noise""")
    body(doc, "報價有兩項：這一組答案有多不確定，以及模型已經知道多少。"
              "只算前一項的話每個新客人都拿滿分 HK$10 —— 這是我實際踩到的 bug（見 9.3）。")

    body(doc, "③ 抽獎轉盤：結果由伺服器決定，機率公開")
    code(doc, """// lib/survey.js — 前端只負責動畫，拿到的是伺服器算好的 index
let r = (randomInt(0, 1_000_000) / 1_000_000) * total;   // 加權抽樣
// 答得越有用，權重從小獎移向大獎
weights = [20-boost, 22-boost, 20-boost, 16, 10+, 6+, 3+, 3]""")
    body(doc, "這一條是設計原則，不是技術細節：瀏覽器不能改結果，"
              "而且輪盤下方列出每一格的實際百分比。不公開機率的抽獎就是暗黑模式。")

    body(doc, "④ 穿搭評分：把「襯唔襯你」拆成可計算的三項")
    code(doc, """# ai-service/visual_search_service.py
style    = cos(照片向量, 衣櫃向量中心)        # 與你平日的風格有多近
coverage = 偵測到的品類（上衣/下身/鞋/外套）    # 是否為完整搭配
palette  = 主色相數量 + 中性色比例             # 配色是否協調
score    = 0.55*style + 0.25*coverage + 0.20*palette""")
    body(doc, "刻意不用 LLM 打分。7B 視覺模型塞不進同一張 12 GB 顯示卡（CatVTON 已佔 3.6 GB），"
              "而未經人類驗證的 LLM 分數是「感覺」不是 benchmark。這版每個分數都能重算、能追責。")

    h2(doc, "9.3  這一輪遇到的困難")

    table(doc, ["問題", "症狀", "根因", "解法"],
          [["問卷券污染挽留率", "挽留率 155.6%、漏斗反轉",
            "兩個活動都寫 coupon_issued，漏斗把全部領券算進來",
            "按事件 meta 的 source 過濾；調研券另立指標"],
           ["漏斗出現 206%", "領取 16、使用 33",
            "分子算全部已用券，分母只算 exit-intent",
            "已用數改從券表自己算；結帳不是子集，移出漏斗"],
           ["現金券顯示 0%", "CASH8-PGWAL · 0%",
            "表格只讀 discountPct，固定金額券是 amountHkd",
            "依 kind 分支顯示 HK$8 或 10%"],
           ["獎勵永遠 HK$10", "每組問卷都拿上限",
            "全新客人的資訊量必然最大，報價曲線飽和",
            "加入 novelty 衰減：知道得越多，下一個答案越不值錢"],
           ["整頁變透明", "衣櫃頁 95% 看不見",
            "animation 用 fill-mode both，非同步重繪後停在 opacity 0",
            "路由轉場改 none；網格子元素只動 transform"],
           ["問卷只出 1 題", "偶爾題數不足",
            "某品類只有 2 件 → 只有一種配對，重抽 6 次後放棄",
            "選題時直接排除已問過的配對"],
           ["評分永遠 75 分", "兩張不同照片同分",
            "假設 SigLIP 圖文相似度約 0.22、圖像約 0–0.6；實測是 0.03 與 0.6–0.8",
            "重新量測兩個尺度並校準"],
           ["示範後台過一週就空", "只剩 10 次搜尋",
            "seed 資料寫在安裝當下，一週後掉出 7 天視窗",
            "視窗內沒有 seed 就只刪 seed 列、重新鋪"]],
          widths=[3.2, 3.4, 4.6, 5.4], size=8.2)

    body(doc, "還有一個不是程式的問題：沙箱的 ACL 執行器暫存目錄被刪，"
              "所有指令回報 --temp is not an existing directory，整輪無法執行任何東西。"
              "重啟 DSH 才恢復，期間只能寫檔不能驗證。")

    body(doc, "另一個：headless Chrome 在這台機器起不來（platform_channel.cc Check failed: 存取被拒），"
              "因為沙箱的受限權杖讓 Chrome 無法為子程序建立 IPC 通道。解法是不在沙箱裡跑："
              "由使用者在自己的終端執行 tools/shots.ps1 截圖，我再讀 PNG。")

    h2(doc, "9.4  第一次真正「看見」網站")

    body(doc, "在此之前，所有介面都只有結構驗證（零亮色背景、語法正確、測試通過）。"
              "tools/shots.ps1 讓截圖成為可能之後，第一次看到就抓到一個測試永遠抓不到的問題：")
    code(doc, """問卷頁：兩張卡片變成上下堆疊，「或者」浮在空白中間
根因：grid-template-columns: repeat(auto-fit, minmax(220px, 1fr))
      卡片內寬 670px，3 × 220 + 2 × 16 = 692 > 670 → 只放得下 2 欄
解法：改成固定 2 欄，把「或者」做成絕對定位的中央徽章""")
    callout(doc, "測試能證明「有沒有壞」，證明不了「看不看得見」。"
                 "透明、堆疊、跑版都通過了 185 項檢查。")

    h2(doc, "9.5  目前的規模")

    table(doc, ["項目", "中期報告時", "現在"],
          [["Python 服務", "3", "3（新增 /aesthetic 端點）"],
           ["頁面", "12", "15"],
           ["自動化檢查", "135 項 / 7 套件", "185 項 / 9 套件"],
           ["文件", "報告 + 簡報", "另加程式導讀、DEPLOY.md、DEMO.md"],
           ["硬體", "Windows + RTX 4070", "同一台，但程式碼已支援 Apple Silicon"]],
          widths=[4.0, 5.4, 7.2])

    # ---------------------------------------------------------------- llm router
    h1(doc, "10  LLM 路由：把模型放在最小的位置上")
    body(doc, "規則式路由遇到沒見過的說法就會漏。自然的想法是「接一個 LLM」，"
              "但接在哪裡決定了它會不會毁掉整個系統的可信度。")

    h2(doc, "10.1  模型只做一件事：判斷意圖")

    code(doc, """question ──▶ LLM 判斷意圖 ─┐
                                   ├─▶ buildPlan() ──▶ 工具 ──▶ 事實 ──▶ 組句 ──▶ 答案
        規則判斷意圖 ─┘     （共用）                        （完全不變）""")

    body(doc, "關鍵是兩個路由器呼叫同一個 buildPlan() 與 extractEntities()。"
              "所以比較的對象是「分類器」，不是兩份各自寫的規劃邏輯 —— 這讓評估有意義。")

    callout(doc, "模型永遠看不到商品目錄、不會產生價格／尺碼／庫存／工具參數，也不會寫答案。"
                 "金額與尺碼由 extractEntities() 從客人的原話讀出來。")

    h2(doc, "10.2  為什麼只做分類")

    body(doc, "這不只是潔癖，是算力與可信度的雙重約束。我在這台機器上實測：")

    table(doc, ["狀態", "已用 VRAM", "剩餘"],
          [["只有桌面程式", "2018 MiB", "—"],
           ["CLIP + CatVTON（無 LLM）", "5672 MiB", "約 6.6 GB"],
           ["+ qwen2.5:3b（1.9 GB）", "7541 MiB", "約 4.7 GB"],
           ["+ qwen2.5:7b（4.7 GB）", "11565 MiB", "約 0.7 GB（幾乎沒有）"]],
          widths=[5.6, 4.2, 5.0])

    body(doc, "最後一列就是答案：7B 載入得進去，但試穿會因為記憶體見底而逾時。"
              "不是「跑得慢」，是「跑不完」。")

    h2(doc, "10.2b  實測結果：模型變大，準確率才變好，但代價是共存")

    table(doc, ["路由器", "意圖準確率", "工具準確率", "延遲", "能否與試穿共存"],
          [["規則式（無模型）", "93.3%", "100%", "0.1 ms", "可以，22.5 秒"],
           ["qwen2.5:3b", "93.3%", "93.3%", "135 ms", "可以，22.5 秒"],
           ["qwen2.5:7b", "100%", "100%", "158 ms", "不可以，逾時"]],
          widths=[4.4, 2.8, 2.8, 2.2, 4.0])

    callout(doc, "3B 只跟規則打平（意圖），工具選擇反而更差；7B 才是真的 100%，"
                 "但代價是不能同時做試穿。這是實測，不是推測。")

    body(doc, "還有一個意外的發現：提示詞比模型大小更重要。3B 的第一版提示詞只有 86.7%，"
              "加入粵語提示與「有預算不等於問價」的規則之後升到 93.3% —— 換模型完全沒動。")

    body(doc, "公平的告誡：規則式路由器就是對著這 15 題開發的，所以它的 93.3% 偏樂觀，"
              "這組既是測試集也是開發集。LLM 則完全沒見過這些題目。"
              "更大的留出集是下一步，tools/eval_router.py 就是跑那個的工具。")

    h2(doc, "10.3  降級契約：四種失敗都退回規則")

    table(doc, ["失敗", "行為"],
          [["沒有模型／連不上", "退回規則，答案完全一樣"],
           ["逾時（預設 2.5 秒）", "退回規則"],
           ["回傳不是 JSON", "退回規則"],
           ["意圖不在白名單", "丟棄該意圖；全部無效則退回規則"]],
          widths=[6.0, 9.0])

    body(doc, "實測：LLM 開啟但端點不存在時，15 題全部退回規則，"
              "意圖準確率與工具準確率跟純規則完全相同，延遲只多 0.5 ms。"
              "所以「打開這個功能」在沒有模型時沒有任何代價。")

    h2(doc, "10.4  怎麼驗證（不需要真的模型）")

    code(doc, """python tools/mock_llm_server.py --port 11434   # 假的 OpenAI 相容服務
node tools/test_router_llm.mjs 11434          # 13 項契約測試

python tools/eval_router.py                   # 15 題，比較兩個路由器""")

    body(doc, "mock 可以扮演四種失敗（垃圾輸出、未知意圖、逾時、HTTP 500），"
              "所以整條路徑與降級行為都能在沒有 GPU、沒有模型的情況下測完。")

    body(doc, "誠實的現況：3B 與 7B 都已經實測（見 10.2b）。剩下的缺口是"
              "「留出集」—— 現在的 15 題同時是規則式路由器的開發集，"
              "所以那個 93.3% 偏樂觀，需要一組規則式沒見過的題目才算公平比較。")

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("— 完 —")
    r.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    doc.save(OUT)
    print(f"  saved {OUT}")
    return OUT


if __name__ == "__main__":
    main()
