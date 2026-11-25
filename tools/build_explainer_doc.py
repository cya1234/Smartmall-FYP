"""Build the explainer document: the survey, the outfit score, and the style-bias fix.

Written as a standalone deliverable so it can be regenerated and handed to a supervisor
without the rest of the repository.

    .venv\\Scripts\\python.exe tools\\build_explainer_doc.py
"""
import os
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT_DIR = os.path.join(ROOT, "reports")
ACCENT = RGBColor(0x1F, 0x4E, 0x79)
GREY = RGBColor(0x77, 0x77, 0x77)


def h1(doc, text):
    p = doc.add_heading(text, level=1)
    for r in p.runs:
        r.font.color.rgb = ACCENT


def h2(doc, text):
    p = doc.add_heading(text, level=2)
    for r in p.runs:
        r.font.color.rgb = ACCENT


def body(doc, text, size=10.5, bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    return p


def bullet(doc, text):
    p = doc.add_paragraph(text, style="List Bullet")
    for r in p.runs:
        r.font.size = Pt(10.5)


def code(doc, text):
    for line in text.strip("\n").splitlines():
        p = doc.add_paragraph()
        r = p.add_run(line)
        r.font.name = "Consolas"
        r.font.size = Pt(9)
        p.paragraph_format.left_indent = Pt(14)
        p.paragraph_format.space_after = Pt(0)


def table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, htext in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(htext)
        run.bold = True
        run.font.size = Pt(9.5)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(val))
            run.font.size = Pt(9.5)


def build():
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    title = doc.add_heading("SmartMall 說明文件", level=0)
    for r in title.runs:
        r.font.color.rgb = ACCENT
    sub = doc.add_paragraph()
    r = sub.add_run("進站問卷 · 穿搭評分（AesRec）· 小眾風格偏見的發現與修正")
    r.font.size = Pt(12)
    r.font.color.rgb = GREY
    p = doc.add_paragraph()
    r = p.add_run("這份文件用簡單的句子說明三件事怎麼做，以及為甚麼要這樣做。"
                  "每個數字都是實際量測的結果，不是估計。")
    r.font.size = Pt(10)

    # =========================================================== 一、問卷
    h1(doc, "一、進站問卷：十分鐘讓網站認識你")

    h2(doc, "1.1 它在做甚麼")
    body(doc, "第一次進來的人，網站對他一無所知。沒有購買紀錄、沒有點擊紀錄，"
              "所以推薦只能靠「大部分人都喜歡甚麼」—— 這對小眾口味的人很不利。")
    body(doc, "問卷的目的，就是用十條問題換取最基本的認識，讓第一次的搜尋結果就有針對性。")

    h2(doc, "1.2 十條問題分別是甚麼")
    table(doc, ["#", "問題", "選項形式"], [
        ["1", "你主要想逛甚麼？", "分類，可多選"],
        ["2", "你喜歡哪種風格？", "六種風格，可多選"],
        ["3", "你平常的預算？", "四段價位，單選"],
        ["4", "你會在哪裡穿？", "六種場合，可多選"],
        ["5", "你喜歡的顏色？", "九種顏色，可多選"],
        ["6", "盡量不要的顏色？", "九種顏色，可多選"],
        ["7–9", "三組「你更喜歡哪一件？」", "真實商品圖片，二選一"],
        ["10", "你偏好甚麼材質？", "六種材質，可多選"],
    ])

    h2(doc, "1.3 答案如何改變推薦")
    body(doc, "每件商品的搜尋分數，最後會乘上一個「個人化倍率」。這個倍率由三部分組成：")
    table(doc, ["來源", "作用範圍", "最大影響"], [
        ["問卷答案（分類／風格／顏色）", "每一件商品", "±25%"],
        ["問卷的兩兩比較", "每一件商品（已評分的）", "另外計算"],
        ["你常點擊的分類", "整個分類", "最多 +20%"],
    ])
    body(doc, "問卷部分的細節是這樣加分的：")
    bullet(doc, "你選的分類 → 該分類商品 +1.0")
    bullet(doc, "你選的風格 → 符合的商品 +0.5")
    bullet(doc, "你喜歡的顏色 → 符合的商品 +0.5")
    bullet(doc, "你「盡量不要」的顏色 → 符合的商品 −1.0")
    body(doc, "加總後限制在 −1 到 +1.5 之間，再換算成倍率：")
    code(doc, "個人化倍率 = 1 + 0.25 × affinity")
    body(doc, "所以最極端的情況是 +1.5 → 倍率 1.375，也就是排序分數提高約 37%。"
              "但這只是「同一個搜尋條件下的微調」，不會蓋過搜尋本身找到的東西。")

    p = doc.add_paragraph()
    r = p.add_run("實測例子（搜尋「black」）：")
    r.bold = True
    table(doc, ["情況", "排序結果"], [
        ["沒有任何偏好", "p034 → p009 → p029"],
        ["告訴系統你想要電子產品", "p029 → p034 → p009（耳機由第三變第一）"],
        ["告訴系統你想要服飾", "p009 → p034 → p029"],
    ])

    h2(doc, "1.4 一件要誠實說明的事")
    body(doc, "問卷收集了六類資料，但目前只有三類真的影響排序：分類、風格、顏色。"
              "「場合」「材質」和「三組兩兩比較」有存下來，但暫時沒有參與推薦計算。")
    body(doc, "這是刻意的取捨：先把可靠的做到底，而不是把每個欄位都硬塞進公式，"
              "變成一個講不清為甚麼的混合分數。")

    h2(doc, "1.5 寫這份文件時發現並修好的一個錯誤")
    body(doc, "檢查程式時發現：風格的加分從來沒有生效過。")
    body(doc, "原因是商品資料裡的「風格」是一個清單（例如 [\"Minimal\"]），"
              "但程式拿使用者的選擇去比對時，是拿字串直接比清單 —— 兩者永遠不會相等。")
    body(doc, "修正後，風格的 +0.5 才會真正計算。這件事也提醒了一點："
              "「使用者填了問卷」和「系統真的用了問卷」是兩件不同的事，必須分開驗證。")

    # =========================================================== 二、AesRec
    h1(doc, "二、穿搭評分（AesRec）：怎麼給一套衣服打分數")

    h2(doc, "2.1 三個分數相加")
    body(doc, "上傳一張穿搭照片，系統給一個 0–100 的分數。這個分數不是單一模型吐出來的，"
              "而是三個部分加權相加：")
    table(doc, ["部分", "權重", "在問甚麼"], [
        ["風格吻合", "65%", "這套衣服像不像你平常穿的？"],
        ["完整度", "25%", "該穿的都穿了嗎？"],
        ["配色", "10%", "顏色之間有沒有關係？"],
    ])

    h2(doc, "2.2 風格吻合：跟「你自己的衣櫃」比")
    body(doc, "多數穿搭評分系統是拿照片去跟一個「大眾審美」比。那對小眾風格的人不公平。")
    body(doc, "這裡的做法是：把你的照片和你衣櫃裡每一件衣服都轉成同一個座標系統裡的點，"
              "然後看你的照片離你衣櫃的「中心」有多近。")
    body(doc, "所以同一個人穿同一套衣服，分數是穩定的；但兩個不同的人穿同一套衣服，"
              "分數可能不同 —— 因為它衡量的不是「好看」，而是「像不像你」。")

    h2(doc, "2.3 完整度：從你的衣櫃推導")
    body(doc, "做法是：用文字去問模型「這張圖裡有沒有上衣？有沒有褲子？有沒有鞋？」")
    body(doc, "但「完整」的標準不是固定的。系統會先看你衣櫃裡買過哪幾類衣服，"
              "只要求你實際會穿的類別。例如一個從不買鞋的人，不會因為照片裡沒有鞋而被扣分。")
    body(doc, "另外，連身裙同時算「上衣」和「下身」。否則一件式的洋裝會被判定為「少了褲子」。")

    h2(doc, "2.4 配色：判斷「有沒有章法」")
    body(doc, "先把照片的顏色歸納成幾個主要色相，然後問：這些色相之間有沒有一個共同的家族？")
    table(doc, ["情況", "判定", "分數"], [
        ["單一色相／全部是中性色", "monochrome / neutral", "100"],
        ["兩個色相", "two-tone（黑配紅這類經典組合也算）", "95"],
        ["三個以上但落在 90 度內", "analogous（同一色系）", "94–100"],
        ["三個以上且散落整圈", "scattered（看不出共同色系）", "20–92"],
    ])
    body(doc, "關鍵差別：霓虹色系（粉→紅→橙→黃）得 95 分，"
              "而隨機散落的六個顏色仍然是 20 分。問的不是「幾種顏色」，而是「有沒有關係」。")

    h2(doc, "2.5 為甚麼是這三個權重")
    body(doc, "風格吻合 65%，因為它是唯一「個人化」的部分，也是最難被取代的。")
    body(doc, "配色只有 10%，因為它是三個部分裡唯一帶有「內建審美偏好」的 —— "
              "它假設有章法比雜亂好。這是一個價值判斷，所以刻意給它最小的權重。")

    # =========================================================== 三、偏見
    h1(doc, "三、小眾風格的偏見：發現、量測、修正")

    h2(doc, "3.1 原本的規則")
    body(doc, "最初的配色規則只有兩行：")
    code(doc, "顏色種類 > 3  → 每多一種扣 16 分\n中性色比例 < 12% → 再扣 12 分")
    body(doc, "看起來合理，但它其實在說「極簡才好看」。")

    h2(doc, "3.2 為甚麼這是一條有偏見的規則")
    body(doc, "重金屬、杀马特、原宿風格的配色，必然超過三種顏色、中性色必然偏低。"
              "所以這些風格在結構上一定被扣分 —— 不是因為它們不好看，而是因為規則假設了「少顏色才好」。")
    body(doc, "這不是模型的問題，是規則的問題。而規則是我們寫的，所以要我們自己負責。")

    h2(doc, "3.3 量它的時候，發現兩個真正的錯誤")
    body(doc, "寫了一支工具去量「六種風格在舊規則和新規則下的分數」。"
              "量出來之後，發現比偏見更嚴重的兩個問題：")
    table(doc, ["錯誤", "後果"], [
        ["亮度 V > 0.95 被當成「中性色」",
         "所有全亮的顏色被當成中性色丟棄。霓虹粉的最大值是 255，亮度就是 1.0，所以它的色相從未被計算"],
        ["色相叢集用算術平均",
         "跨紅色的叢集（330 度和 0 度）平均成 165 度，也就是相反的色相。一件霓虹系穿搭被判成「散落」"],
    ])
    body(doc, "第一個錯誤的意思是：系統不是「討厭霓虹色」，而是根本看不見霓虹色。")

    h2(doc, "3.4 改成判斷「結構」而不是「克制」")
    body(doc, "新的規則只看配色有沒有內在邏輯，不看用了多少顏色。"
              "同一色系、互補色、兩個顏色的經典組合，全部保留高分；"
              "只有「看不出任何共同色系」的配色才會被扣分。")

    h2(doc, "3.5 實測結果")
    body(doc, "六種風格，衣服完全相同，只改變顏色：")
    table(doc, ["風格", "顏色數", "判定", "舊規則", "新規則"], [
        ["極簡（中性色）", "0", "neutral", "97.3", "100"],
        ["街頭（深色＋一個重點色）", "1", "monochrome", "100", "100"],
        ["重金屬（黑＋暗紅）", "2", "two-tone", "100", "95"],
        ["極繁，但有章法（霓虹色系）", "2", "two-tone", "100", "95"],
        ["極繁，散落（隨機色相）", "3", "scattered", "100", "20"],
        ["正式（海軍藍＋灰＋白）", "1", "monochrome", "100", "100"],
    ])
    body(doc, "這裡有一個比偏見更值得注意的發現：舊規則下六種風格全部分落在 2.7 分以內。")
    body(doc, "也就是說，那條規則不是「有偏見」，而是「幾乎沒有鑑別力」——"
              "它的門檻從來沒有觸發過。一個佔 20% 權重卻分辨不出任何東西的訊號，本身就是缺陷。")

    h2(doc, "3.6 還剩下的價值判斷，沒有隱藏")
    body(doc, "修完之後，「有章法比雜亂好」仍然是一個價值判斷。所以做了三件事：")
    bullet(doc, "配色權重由 20% 降到 10%，風格吻合提高到 65%")
    bullet(doc, "權重只是程式裡的一個數字，可以直接改")
    bullet(doc, "在文件與報告裡寫明這個判斷，而不是假裝它是客觀事實")

    # =========================================================== 四、總結
    h1(doc, "四、一句話總結")
    body(doc, "問卷解決的是「第一次見面時的無知」，穿搭評分解決的是「用甚麼標準衡量」，"
              "而偏見修正解決的是「我們原本的標準錯了，而且錯得看不出來」。")
    body(doc, "三件事共同的教訓是：任何「看起來合理」的規則，都應該被量一次再相信。")

    # =========================================================== 五、重現
    h1(doc, "五、怎麼重現這些結果")
    table(doc, ["想做甚麼", "指令或檔案"], [
        ["重跑偏見量測", "python tools/eval_aesthetic_bias.py http://127.0.0.1:8001"],
        ["看六種風格的產生方式", "tools/eval_aesthetic_bias.py"],
        ["穿搭評分的實作", "ai-service/visual_search_service.py 的 /aesthetic"],
        ["問卷與推薦的實作", "lib/userState.js（問卷）／lib/agent/tools.js（排序）"],
        ["問卷效果的測試", "node tools/test_onboarding_rank.mjs"],
    ])

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("這份文件由 tools/build_explainer_doc.py 生成")
    r.font.size = Pt(8.5)
    r.font.color.rgb = GREY

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "說明文件：問卷、穿搭評分與風格偏見.docx")
    doc.save(path)
    return path


if __name__ == "__main__":
    out = build()
    print(f"  saved: {out}")
    print(f"  size : {os.path.getsize(out) / 1024:.0f} KB")
    sys.exit(0)
