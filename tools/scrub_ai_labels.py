"""One-off label scrub: replace AI-technology branding with benefit language.

Each entry is (old, new); every replacement is counted so the run is auditable.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / "public" / "js" / "i18n.js"

MAPPING = [
    # ---- Chinese ----
    ("'footer.note': 'FYP 展示網站 — AI 服務為模擬實作，可替換為真實模型。'",
     "'footer.note': 'FYP 示範網站 · 部分服務以模擬資料呈現'"),
    ("'feat.blindbox.t': 'AI 買手盲盒'", "'feat.blindbox.t': '造型盒'"),
    ("說出預算與情境，AI 直接生成整套裝備組合與搭配理由。", "說出預算與情境，直接生成整套裝備組合與搭配理由。"),
    ("'feat.tryon.t': 'AI 虛擬試穿'", "'feat.tryon.t': '虛擬試穿'"),
    ("，AI 代理代你批量詢價議價。", "，代理代你批量詢價議價。"),
    ("'feat.resale.d': 'AI 自動生成描述與定價，一鍵上架形成買賣循環。'",
     "'feat.resale.d': '自動生成描述與定價，一鍵上架形成買賣循環。'"),
    ("退貨時 AI 看圖判斷瑕疵。", "退貨時看圖判斷瑕疵。"),
    ("'bb.title': '🎁 AI 買手盲盒'", "'bb.title': '🎁 造型盒'"),
    ("說出你的情境與預算，AI 直接幫你配好整套裝備", "說出你的情境與預算，直接幫你配好整套裝備"),
    ("'bb.generating': 'AI 正在為你搭配…'", "'bb.generating': '正在為你搭配…'"),
    ("'pa.sub': 'AI 代理掃描各平台公開售價", "'pa.sub': '代理會掃描各平台公開售價"),
    ("'pa.run': '啟動 AI 代理'", "'pa.run': '啟動代理'"),
    ("'pa.negotiation': 'AI 議價對話'", "'pa.negotiation': '議價對話'"),
    ("'pa.agent': 'AI 代理'", "'pa.agent': '代理'"),
    ("'rs.sub': '不想穿的衣服，AI 自動生成商品描述與建議售價",
     "'rs.sub': '不想穿的衣服，自動生成商品描述與建議售價"),
    ("'rs.draft': 'AI 生成刊登草稿'", "'rs.draft': '生成刊登草稿'"),
    ("'rs.drafting': 'AI 正在撰寫描述與定價…'", "'rs.drafting': '正在撰寫描述與定價…'"),
    ("'mem.sub': 'AI 記住你買過什麼", "'mem.sub': '系統記住你買過什麼"),
    ("'mem.insights': 'AI 觀察到的你'", "'mem.insights': '我們觀察到的你'"),
    ("'sp.sub': 'AI 引導你拍照", "'sp.sub': '系統引導你拍照"),
    ("'sp.step3': '上傳瑕疵照片（AI 檢測）'", "'sp.step3': '上傳瑕疵照片（自動檢測）'"),
    ("'sp.uploadHint': 'AI 會分析亮度", "'sp.uploadHint': '系統會分析亮度"),
    ("'sp.analysing': 'AI 正在檢測瑕疵…'", "'sp.analysing': '正在檢測瑕疵…'"),
    ("'sp.detected': 'AI 檢測結果'", "'sp.detected': '檢測結果'"),
    ("'sp.handled': 'AI 處理案件'", "'sp.handled': '系統處理案件'"),
    ("'vs.engine': 'AI 引擎'", "'vs.engine': '搜尋引擎'"),
    ("'vs.offline': 'AI 服務離線，已自動改用顏色比對'", "'vs.offline': '影像服務離線，已自動改用顏色比對'"),
    # ---- English ----
    ("'footer.note': 'FYP demo — AI services are simulated and swappable for real models.'",
     "'footer.note': 'FYP demo · some services use simulated data'"),
    ("'feat.blindbox.t': 'AI Blind Box'", "'feat.blindbox.t': 'Style Box'"),
    ("Cross-platform comparison, auto coupons and AI bulk negotiation.",
     "Cross-platform comparison, auto coupons and bulk negotiation."),
    ("'feat.resale.d': 'AI writes the listing and price",
     "'feat.resale.d': 'Writes the listing and price"),
    ("'bb.title': '🎁 AI Buyer Blind Box'", "'bb.title': '🎁 Style Box'"),
    ("State your scenario and budget — the AI assembles the entire kit for you.",
     "State your scenario and budget — we assemble the entire kit for you."),
    ("'bb.generating': 'The AI is styling your kit…'", "'bb.generating': 'Styling your kit…'"),
    ("'pa.negotiation': 'AI negotiation transcript'", "'pa.negotiation': 'Negotiation transcript'"),
    ("'pa.agent': 'AI agent'", "'pa.agent': 'Agent'"),
    ("'rs.sub': 'The AI writes the listing and suggests a price",
     "'rs.sub': 'We write the listing and suggest a price"),
    ("'rs.draft': 'Generate AI draft'", "'rs.draft': 'Generate draft'"),
    ("'rs.drafting': 'AI is writing the listing…'", "'rs.drafting': 'Writing the listing…'"),
    ("'mem.sub': 'The AI remembers your purchases", "'mem.sub': 'We remember your purchases"),
    ("'mem.insights': 'What the AI has learned about you'", "'mem.insights': 'What we have learned about you'"),
    ("'sp.sub': 'The AI guides your photos", "'sp.sub': 'We guide your photos"),
    ("'sp.step3': 'Upload photos (AI inspection)'", "'sp.step3': 'Upload photos (auto inspection)'"),
    ("'sp.uploadHint': 'The AI analyses brightness", "'sp.uploadHint': 'We analyse brightness"),
    ("'sp.analysing': 'AI is inspecting the photo…'", "'sp.analysing': 'Inspecting the photo…'"),
    ("'sp.detected': 'AI inspection result'", "'sp.detected': 'Inspection result'"),
    ("'sp.handled': 'Cases handled by AI'", "'sp.handled': 'Cases handled automatically'"),
    ("'vs.engine': 'AI engine'", "'vs.engine': 'Search engine'"),
    ("'vs.offline': 'AI service offline — using the colour heuristic'",
     "'vs.offline': 'Image service offline — using the colour heuristic'"),
]


def main():
    text = TARGET.read_text(encoding="utf-8")
    before = text
    applied, missed = 0, []
    for old, new in MAPPING:
        if old in text:
            text = text.replace(old, new)
            applied += 1
        else:
            missed.append(old[:60])

    TARGET.write_text(text, encoding="utf-8")

    remaining = [
        (i + 1, ln.strip())
        for i, ln in enumerate(text.splitlines())
        if "AI" in ln and not ln.strip().startswith("//")
    ]
    print(f"  replacements applied : {applied}/{len(MAPPING)}")
    if missed:
        print("  not found (check manually):")
        for m in missed:
            print(f"    - {m}")
    print(f"  lines still containing 'AI': {len(remaining)}")
    for n, ln in remaining[:12]:
        print(f"    {n}: {ln[:100]}")
    print(f"  changed: {before != text}")


if __name__ == "__main__":
    sys.exit(main())
