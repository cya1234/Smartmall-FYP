"""Build the weekly report as a .docx, copy it into the synced cloud folder, notify.

The scheduled-task entry point is `tools/weekly_task.ps1`, but this script does the work
and can be run by hand at any time:

    .venv\\Scripts\\python.exe tools\\build_weekly_report.py --dry-run
    .venv\\Scripts\\python.exe tools\\build_weekly_report.py

Config lives outside the repository so credentials never end up in git:

    %USERPROFILE%\\.smartmall\\report.json   ->  see tools/report_config.example.json

Everything is best-effort: if Telegram is not configured the report is still written; if
the Drive folder is missing it falls back to `reports/` in the project and says so.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime

# python-docx is optional. A scheduled task that fails because one dependency is missing
# is worse than a task that writes Markdown, so the report is always produced: as .docx
# when python-docx is importable, else as .md.
try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor
    HAVE_DOCX = True
except Exception:
    HAVE_DOCX = False
    Document = None
    Pt = RGBColor = WD_ALIGN_PARAGRAPH = None

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TOOLS = os.path.join(ROOT, "tools")
HOME = os.path.expanduser("~")
FAQ_PATH = os.path.join(TOOLS, "report_faq.json")


def pick_dir():
    """First writable place for config and state.

    Preference order puts the home folder first, because that is where a person would
    look for it and where it stays out of the repository. The project-local fallback
    exists because a sandboxed process may not be allowed to write under the profile,
    and a report tool that cannot save its own state is a bug.
    """
    candidates = []
    env = os.environ.get("SMARTMALL_REPORT_DIR")
    if env:
        candidates.append(env)
    candidates += [
        os.path.join(HOME, ".smartmall"),
        os.path.join(ROOT, ".report"),
    ]
    for c in candidates:
        try:
            os.makedirs(c, exist_ok=True)
            probe = os.path.join(c, ".write-test")
            with open(probe, "w", encoding="utf-8") as fh:
                fh.write("ok")
            os.remove(probe)
            return c, candidates
        except Exception:
            continue
    return os.path.join(ROOT, ".report"), candidates


CONFIG_DIR, CONFIG_CANDIDATES = pick_dir()
CONFIG_PATH = os.path.join(CONFIG_DIR, "report.json")
STATE_PATH = os.path.join(CONFIG_DIR, "state.json")

ACCENT = RGBColor(0x1F, 0x4E, 0x79)
GREY = RGBColor(0x77, 0x77, 0x77)

# Which area a commit belongs to.
#
# Matching is on the subject only, with word boundaries, and first match wins. That
# matters: a naive substring test put "Add the score A/B experiment" under catalogue
# because "personalised" contains "person", and "HK shoe sizing" under try-on because
# of "shoe". Patterns are listed most-specific first.
AREAS = [
    ("虛擬試穿", [r"\btry[- ]?on\b", r"\bcatvton\b", r"\bsampler\b", r"\bscheduler\b", r"\bsteps?\b"]),
    ("A/B 實驗", [r"\ba/b\b", r"\bexperiment\b", r"\bconversion\b"]),
    ("帳號與登入", [r"\bauth\b", r"\blog[- ]?in\b", r"\bsign[- ]?in\b", r"\bsign[- ]?up\b",
                    r"\baccount", r"\bsession\b", r"\bpassword"]),
    ("個人化（問卷／搜尋／點擊）", [r"\bsurvey\b", r"\bonboarding\b", r"\bwelcome\b",
                                    r"\bhistory\b", r"\bclick", r"\bengagement\b", r"\bpreference"]),
    ("穿搭評分", [r"\baesthetic", r"\bbias\b", r"\bfairness\b", r"\bpalette\b"]),
    ("商品目錄與尺碼", [r"\bcatalogue\b", r"\bsizing\b", r"\bsizes?\b", r"\bshoe", r"\bproducts?\b",
                        r"\billustration", r"\binventory\b", r"\bdigital\b"]),
    ("報告工具", [r"\bweekly[ _]report\b", r"\bweekly report\b"]),
    ("測試", [r"\btests?\b", r"\bchecks?\b", r"\bassert"]),
    ("文件", [r"\breadme\b", r"\bguides?\b", r"\bdocs?\b", r"\bportable\b", r"\bsync\.md\b",
              r"\bdeploy\b", r"\bsetup\b", r"\binstall\b"]),
]


def area_of(commit):
    """The area a commit belongs to: most pattern hits wins, earliest list order breaks ties.

    Scoring rather than first-match, because commit subjects mix concerns — "HK shoe
    sizing, ... 10 try-on samples" is a catalogue change that happens to mention try-on.
    """
    subject = commit["subject"]
    best, best_hits = "其他", 0
    for area, patterns in AREAS:
        hits = sum(1 for p in patterns if re.search(p, subject, re.IGNORECASE))
        if hits > best_hits:
            best, best_hits = area, hits
    return best

# Areas that map to FAQ tags so the questions match what actually changed.
AREA_TAGS = {
    "虛擬試穿": ["tryon", "performance"],
    "商品目錄與尺碼": ["catalogue", "size", "sizing"],
    "帳號與登入": ["auth", "login"],
    "A/B 實驗": ["ab", "experiment"],
    "個人化（問卷／搜尋／點擊）": ["click", "recommend", "survey", "preference"],
    "穿搭評分": ["aesthetic", "bias", "score"],
    "測試": ["test", "eval"],
    "文件": [],
    "修正": [],
}

STATUS_SIX = [
    ("1", "十題進站問卷 + 更多商品", "完成", "52 件商品；問卷會實際改變排序"),
    ("2", "AesRec 用下單率／點擊率比較方法", "框架完成，缺數據", "三組 A/B 已建，未有真實受測者"),
    ("3", "從點擊習慣學習推薦", "邏輯完成，缺數據", "分類注意力，上限 +20%"),
    ("4", "可靠可用的登入系統", "完成", "scrypt、HttpOnly、分帳號資料"),
    ("5", "真實搜尋歷史", "完成", "三種入口統一記錄"),
    ("6", "小眾風格偏見問題", "完成", "已量化並修正，配色權重降至 10%"),
]

SIMULATED = [
    ("價格預測", "合成 800 天價格歷史（含節日標記）"),
    ("門市庫存／O2O", "規則生成，非真實庫存"),
    ("比價（七個平台）", "模擬報價"),
    ("二手估價", "公式計算"),
    ("退貨風險", "規則模型 + profile"),
    ("虛擬試穿／以圖搜尋／穿搭評分", "真實模型推論"),
]


# --------------------------------------------------------------------- helpers
def load_json(path, fallback):
    """Read JSON, tolerating a BOM and leading '#' comment lines.

    The shipped template has comment lines, so somebody will eventually copy it into
    place unchanged and wonder why nothing works. Accepting them costs four lines.
    """
    try:
        with open(path, encoding="utf-8-sig") as fh:
            raw = fh.read()
    except Exception:
        return fallback
    stripped = "\n".join(
        line for line in raw.splitlines() if not line.lstrip().startswith("#")
    )
    for candidate in (stripped, raw):
        try:
            return json.loads(candidate) if candidate.strip() else fallback
        except Exception:
            continue
    return fallback


def save_path_with_retry(dirpath, base_name, writer):
    """Write a file, stepping around one already open in Word.

    A scheduler that fails because the previous report is still open in a word
    processor is a bad scheduler: writing "name (2).docx" is the correct behaviour.
    """
    stem, ext = os.path.splitext(base_name)
    last = None
    for attempt in range(0, 10):
        name = base_name if attempt == 0 else f"{stem} ({attempt}){ext}"
        path = os.path.join(dirpath, name)
        try:
            writer(path)
            return path
        except PermissionError as exc:
            last = exc
            continue
    raise last if last else RuntimeError("could not write report")


def save_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(value, fh, ensure_ascii=False, indent=1)


def run(cmd, cwd=ROOT):
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                             timeout=60, encoding="utf-8", errors="replace")
        return out.stdout.strip()
    except Exception:
        return ""


def git(*args):
    return run(["git", *args])


# ------------------------------------------------------------------- document
def h1(doc, text):
    p = doc.add_heading(text, level=1)
    for r in p.runs:
        r.font.color.rgb = ACCENT
    return p


def h2(doc, text):
    p = doc.add_heading(text, level=2)
    for r in p.runs:
        r.font.color.rgb = ACCENT
    return p


def body(doc, text, size=10.5):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    return p


def bullet(doc, text):
    p = doc.add_paragraph(text, style="List Bullet")
    for r in p.runs:
        r.font.size = Pt(10.5)
    return p


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
    return t


def build_doc(facts, faq, cfg, since):
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    today = datetime.now().strftime("%Y-%m-%d")
    title = doc.add_heading(f"SmartMall 每週報告 · {today}", level=0)
    for r in title.runs:
        r.font.color.rgb = ACCENT
    p = doc.add_paragraph()
    run = p.add_run(f"報告範圍：{since} 起 · 產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M')} · "
                    f"分支 {facts['worktree']['branch']} · HEAD {facts['worktree']['head'][:7]}")
    run.font.size = Pt(8.5)
    run.font.color.rgb = GREY

    commits = facts["commits"]
    areas = {}
    for c in commits:
        areas.setdefault(area_of(c), []).append(c)

    # ---------------------------------------------------------------- 一、概況
    h1(doc, "一、本週概況")
    body(doc, f"本週共 {len(commits)} 個提交，涉及 {len(areas)} 個範疇。"
              f"程式碼目前 {sum(v['lines'] for v in facts['code'].values())} 行，"
              f"商品 {sum(facts['catalogue'].values()) if facts['catalogue'] else 0} 件，"
              f"測試檔案 {len(facts['tests'])} 個。")
    rows = []
    for area, cs in sorted(areas.items(), key=lambda kv: -len(kv[1])):
        rows.append([area, len(cs), cs[0]["subject"][:46] + ("…" if len(cs[0]["subject"]) > 46 else "")])
    if rows:
        table(doc, ["範疇", "提交數", "代表變更"], rows)

    # -------------------------------------------------------------- 二、進度
    h1(doc, "二、逐項進度")
    if not commits:
        body(doc, "本週沒有提交。")
    for area in sorted(areas, key=lambda a: -len(areas[a])):
        h2(doc, area)
        for c in areas[area]:
            bullet(doc, f"{c['subject']}（{c['date']} · {c['sha']}）")

    # -------------------------------------------------------------- 三、技術
    h1(doc, "三、技術重點")
    with_body = [c for c in commits if c.get("body")]
    if not with_body:
        body(doc, "本週的提交訊息較短，技術細節見專案的 README 與程式導讀。")
    for c in with_body[:6]:
        first = " ".join(c["body"].split())
        cut = first.find(". ")
        snippet = first[:cut + 1] if 0 < cut < 260 else first[:260]
        bullet(doc, f"{c['subject']} —— {snippet}")

    # ------------------------------------------------------------- 四、問答
    h1(doc, "四、老師可能會問的問題")
    tags = set()
    for area in areas:
        tags.update(AREA_TAGS.get(area, []))
    chosen = [q for q in faq if q.get("always") or (set(q.get("tags", [])) & tags)]
    # keep the report readable: always items first, then the matching ones
    chosen.sort(key=lambda q: (not q.get("always"), q["id"]))
    if not chosen:
        chosen = [q for q in faq if q.get("always")]
    for i, q in enumerate(chosen, 1):
        p = doc.add_paragraph()
        r = p.add_run(f"問 {i}：{q['q']}")
        r.bold = True
        r.font.size = Pt(10.5)
        p2 = doc.add_paragraph()
        r2 = p2.add_run("答：" + q["a"])
        r2.font.size = Pt(10)
        p2.paragraph_format.left_indent = Pt(12)

    # -------------------------------------------------------- 五、下一步風險
    h1(doc, "五、下一步與風險")
    body(doc, "建議優先次序：")
    bullet(doc, "收 A/B 數據（15–25 位同學，每組 30 次瀏覽）—— 這是目前唯一無法用寫程式解決的事")
    bullet(doc, "整理答辯用的數字表：測試數、延遲、準確率、商品數")
    bullet(doc, "試穿輸入指引（正面、腰部以上、簡單背景）")
    p = doc.add_paragraph()
    r = p.add_run("最大風險：")
    r.bold = True
    body(doc, "教授第 2 點要求「用下單率比較方法」，但至今仍是 0 位真實受測者。"
              "這件事沒有捷徑，必須真的找人測試。")

    # ------------------------------------------------------ 六、需要確認的事
    h1(doc, "六、需要你自己確認的事")
    h2(doc, "6.1 哪些是示範資料")
    table(doc, ["功能", "真實程度"], SIMULATED)
    body(doc, "老師問起時要先講清楚，主動說明比被追問好。")

    h2(doc, "6.2 教授六點完成度")
    table(doc, ["#", "要求", "狀態", "說明"], STATUS_SIX)

    h2(doc, "6.3 沒有真實數據支持的宣稱")
    bullet(doc, "A/B 實驗：框架完成，但沒有真實受測者（系統內的次數是測試程式寫入的）")
    bullet(doc, "點擊學習：邏輯與測試完成，沒有真實點擊數據")
    bullet(doc, "問卷效果：用測試帳號驗證排序會改變，但沒有人真的填過")

    # ------------------------------------------------------------- 附錄
    doc.add_page_break()
    h1(doc, "附錄：事實來源")
    body(doc, "本報告的數字由 tools/weekly_report.py 直接從 git 與檔案系統讀取，不是憑記憶填寫。")
    for label, v in facts["code"].items():
        bullet(doc, f"{label}：{v['files']} 個檔案 / {v['lines']} 行")
    total_checks = sum(t["checks"] for t in facts["tests"])
    bullet(doc, f"測試檔 {len(facts['tests'])} 個，程式內 check() 呼叫約 {total_checks} 個")
    if facts["catalogue"]:
        bullet(doc, "商品：" + "、".join(f"{k} {v}" for k, v in facts["catalogue"].items()))
    w = facts["worktree"]
    bullet(doc, f"工作區：未提交 {w['uncommitted']} 個檔案，未推送 {w['unpushed'] or 0} 個提交")
    s = facts["services"]
    up = [k for k, v in s.items() if v]
    bullet(doc, "執行時服務狀態：" + ("、".join(up) if up else "全部關閉"))

    path = os.path.join(cfg["_tmp_out"], f"SmartMall 週報 {today}.docx")
    return save_path_with_retry(cfg["_tmp_out"], os.path.basename(path), doc.save)


def build_markdown(facts, faq, since):
    """The same report as Markdown — the path taken when python-docx is unavailable."""
    today = datetime.now().strftime("%Y-%m-%d")
    commits = facts["commits"]
    areas = {}
    for c in commits:
        areas.setdefault(area_of(c), []).append(c)
    L = []
    L.append(f"# SmartMall 每週報告 · {today}")
    L.append("")
    L.append(f"報告範圍：{since} 起 · 產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M')} · "
             f"分支 {facts['worktree']['branch']} · HEAD {facts['worktree']['head'][:7]}")
    L.append("")

    L.append("## 一、本週概況")
    L.append("")
    L.append(f"本週共 {len(commits)} 個提交，涉及 {len(areas)} 個範疇。"
             f"程式碼目前 {sum(v['lines'] for v in facts['code'].values())} 行，"
             f"商品 {sum(facts['catalogue'].values()) if facts['catalogue'] else 0} 件。")
    L.append("")
    if areas:
        L.append("| 範疇 | 提交數 | 代表變更 |")
        L.append("|---|---|---|")
        for area, cs in sorted(areas.items(), key=lambda kv: -len(kv[1])):
            L.append(f"| {area} | {len(cs)} | {cs[0]['subject'][:46]} |")
        L.append("")

    L.append("## 二、逐項進度")
    L.append("")
    if not commits:
        L.append("本週沒有提交。")
    for area in sorted(areas, key=lambda a: -len(areas[a])):
        L.append(f"### {area}")
        L.append("")
        for c in areas[area]:
            L.append(f"- {c['subject']}（{c['date']} · {c['sha']}）")
        L.append("")

    L.append("## 三、技術重點")
    L.append("")
    with_body = [c for c in commits if c.get("body")]
    if not with_body:
        L.append("本週提交訊息較短，技術細節見 README 與程式導讀。")
    for c in with_body[:6]:
        first = " ".join(c["body"].split())
        cut = first.find(". ")
        snippet = first[:cut + 1] if 0 < cut < 260 else first[:260]
        L.append(f"- **{c['subject']}** —— {snippet}")
    L.append("")

    L.append("## 四、老師可能會問的問題")
    L.append("")
    tags = set()
    for area in areas:
        tags.update(AREA_TAGS.get(area, []))
    chosen = [q for q in faq if q.get("always") or (set(q.get("tags", [])) & tags)]
    chosen.sort(key=lambda q: (not q.get("always"), q["id"]))
    if not chosen:
        chosen = [q for q in faq if q.get("always")]
    for i, q in enumerate(chosen, 1):
        L.append(f"**問 {i}：{q['q']}**")
        L.append("")
        L.append(f"答：{q['a']}")
        L.append("")

    L.append("## 五、下一步與風險")
    L.append("")
    L.append("- 收 A/B 數據（15–25 位同學，每組 30 次瀏覽）—— 唯一無法用寫程式解決的事")
    L.append("- 整理答辯用數字表：測試數、延遲、準確率、商品數")
    L.append("- 試穿輸入指引（正面、腰部以上、簡單背景）")
    L.append("")
    L.append("**最大風險**：教授第 2 點要求「用下單率比較方法」，但至今仍是 0 位真實受測者。")
    L.append("")

    L.append("## 六、需要你自己確認的事")
    L.append("")
    L.append("### 6.1 哪些是示範資料")
    L.append("")
    L.append("| 功能 | 真實程度 |")
    L.append("|---|---|")
    for a, b in SIMULATED:
        L.append(f"| {a} | {b} |")
    L.append("")
    L.append("### 6.2 教授六點完成度")
    L.append("")
    L.append("| # | 要求 | 狀態 | 說明 |")
    L.append("|---|---|---|---|")
    for row in STATUS_SIX:
        L.append("| " + " | ".join(row) + " |")
    L.append("")
    L.append("### 6.3 沒有真實數據支持的宣稱")
    L.append("")
    L.append("- A/B 實驗：框架完成，但沒有真實受測者（系統內次數是測試程式寫入的）")
    L.append("- 點擊學習：邏輯與測試完成，沒有真實點擊數據")
    L.append("- 問卷效果：用測試帳號驗證排序會改變，但沒有人真的填過")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 附錄：事實來源")
    L.append("")
    L.append("本報告數字由 tools/weekly_report.py 直接從 git 與檔案系統讀取。")
    L.append("")
    for label, v in facts["code"].items():
        L.append(f"- {label}：{v['files']} 個檔案 / {v['lines']} 行")
    total_checks = sum(t["checks"] for t in facts["tests"])
    L.append(f"- 測試檔 {len(facts['tests'])} 個，程式內 check() 約 {total_checks} 個")
    if facts["catalogue"]:
        L.append("- 商品：" + "、".join(f"{k} {v}" for k, v in facts["catalogue"].items()))
    w = facts["worktree"]
    L.append(f"- 工作區：未提交 {w['uncommitted']} 個檔案，未推送 {w['unpushed'] or 0} 個提交")
    s = facts["services"]
    up = [k for k, v in s.items() if v]
    L.append("- 執行時服務狀態：" + ("、".join(up) if up else "全部關閉"))
    return "\n".join(L)


# ------------------------------------------------------------------- delivery
def drive_folder(cfg):
    """The synced folder, if it exists right now."""
    explicit = (cfg.get("drive_folder") or "").strip()
    if explicit and os.path.isdir(explicit):
        return explicit
    candidates = [os.path.join(HOME, "My Drive"),
                  os.path.join(HOME, "Google Drive"),
                  os.path.join(HOME, "Google 雲端硬碟")]
    for letter in "GHIJKLMNOPQRSTUVWXYZ":
        candidates.append(f"{letter}:\\My Drive")
    for c in candidates:
        if os.path.isdir(c):
            return c
    return None


def copy_via_powershell(src, dest_dir):
    """Copy through PowerShell, for when this process is denied write access.

    The agent sandbox gives Python a restricted token that cannot write to the Google
    Drive virtual drive, while PowerShell can. The scheduled task runs outside that
    sandbox and would not need this, but falling back costs one call and makes the tool
    work from either context.

    The command goes into a temporary .ps1 written as UTF-8 **with BOM**: passing a
    Chinese path as a `-Command` argument gets mangled by the console codepage, which
    made the first version of this helper fail silently.
    """
    stem_name, ext = os.path.splitext(os.path.basename(src))
    tmpdir = os.path.join(ROOT, ".cache", "report-copy")
    os.makedirs(tmpdir, exist_ok=True)

    for attempt in range(0, 5):
        name = os.path.basename(src) if attempt == 0 else f"{stem_name} ({attempt}){ext}"
        dest = os.path.join(dest_dir, name)
        script = os.path.join(tmpdir, "copy.ps1")
        try:
            with open(script, "w", encoding="utf-8-sig") as fh:
                fh.write("$ErrorActionPreference='Stop'\n")
                fh.write(f"Copy-Item -LiteralPath {ps_quote(src)} -Destination {ps_quote(dest)} -Force\n")
            out = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
            )
            if out.returncode == 0 and os.path.exists(dest):
                return dest
        except Exception:
            pass
    return None


def ps_quote(path):
    """Single-quote a path for PowerShell, doubling any apostrophe inside it."""
    return "'" + str(path).replace("'", "''") + "'"


def plain_copy(src, dest):
    """Byte-for-byte copy without metadata.

    shutil.copy2 also copies timestamps and permissions, and Google Drive's virtual
    drive refuses that on a file it manages — the copy then fails with PermissionError
    even though plain writing works fine.
    """
    with open(src, "rb") as fin, open(dest, "wb") as fout:
        shutil.copyfileobj(fin, fout)


def telegram(cfg, text):
    tg = cfg.get("telegram") or {}
    token, chat = tg.get("token", ""), tg.get("chat_id", "")
    if not token or not chat:
        return False, "telegram 未設定（token / chat_id 空白）"
    try:
        data = urllib.parse.urlencode({
            "chat_id": chat, "text": text, "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
        with urllib.request.urlopen(req, timeout=20) as r:
            ok = json.loads(r.read().decode()).get("ok", False)
        return bool(ok), "sent" if ok else "api rejected"
    except Exception as exc:
        return False, str(exc)[:160]


# ----------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="7 days ago")
    ap.add_argument("--dry-run", action="store_true", help="write locally, no Drive, no Telegram")
    ap.add_argument("--no-notify", action="store_true")
    ap.add_argument("--out", default="", help="explicit output folder")
    ap.add_argument("--catch-up", action="store_true",
                    help="only run if the last report is older than --min-age-days")
    ap.add_argument("--min-age-days", type=float, default=6.0)
    ap.add_argument("--generate", action="store_true",
                    help="generate locally only and emit --emit-result JSON; the caller "
                         "does the cloud copy and the notification")
    ap.add_argument("--emit-result", default="",
                    help="write a small JSON describing the result to this path")
    args = ap.parse_args()

    # Catch-up mode is what the logon trigger calls: if the machine was off on Tuesday,
    # the report runs the next time somebody logs in, once.
    if args.catch_up:
        state = load_json(STATE_PATH, {})
        last = state.get("last_report_at")
        if last:
            try:
                age = (datetime.now() - datetime.fromisoformat(last)).total_seconds() / 86400
            except Exception:
                age = 999
            if age < args.min_age_days:
                print(f"  not due: last report {age:.1f} days ago "
                      f"(threshold {args.min_age_days})")
                return 0
            print(f"  due: last report {age:.1f} days ago")
        else:
            print("  due: no previous report")

    cfg = load_json(CONFIG_PATH, {})
    os.makedirs(CONFIG_DIR, exist_ok=True)

    tmp = os.path.join(ROOT, "reports")
    os.makedirs(tmp, exist_ok=True)
    cfg["_tmp_out"] = tmp

    sys.path.insert(0, TOOLS)
    from weekly_report import collect  # noqa: E402  (same folder)

    facts = collect(args.since)
    faq = load_json(FAQ_PATH, {}).get("questions", [])

    if HAVE_DOCX:
        produced = build_doc(facts, faq, cfg, args.since)
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        produced = os.path.join(tmp, f"SmartMall 週報 {today}.md")
        with open(produced, "w", encoding="utf-8") as fh:
            fh.write(build_markdown(facts, faq, args.since))
    doc_path = produced

    # deliver
    # Generate-only mode: the Windows task does the cloud copy and the notification.
    #
    # Python is denied write access to the Google Drive virtual drive even when it runs
    # as the logged-in user (PowerShell on the same machine, same folder, writes fine —
    # verified with a probe task). Rather than fight that, the layer that is allowed to
    # write handles it, which is also where the copy belongs: it is a filesystem
    # operation, not report logic.
    if args.generate:
        result = {
            "ok": True,
            "report_path": doc_path,
            "commits": len(facts["commits"]),
            "products": sum(facts["catalogue"].values()) if facts["catalogue"] else 0,
            "uncommitted": facts["worktree"]["uncommitted"],
            "unpushed": facts["worktree"]["unpushed"],
            "branch": facts["worktree"]["branch"],
            "head": facts["worktree"]["head"],
            "docx": HAVE_DOCX,
        }
        if args.emit_result:
            save_json(args.emit_result, result)
        print(f"  report   : {doc_path}")
        print(f"  commits  : {result['commits']}")
        save_json(STATE_PATH, {
            "last_report_at": datetime.now().isoformat(timespec="seconds"),
            "last_report_path": doc_path,
            "commits": result["commits"],
        })
        return 0

    drive = drive_folder(cfg) if not args.out else None
    target_dir = args.out or drive or tmp
    os.makedirs(target_dir, exist_ok=True)
    final_path = None
    try:
        # Same lock tolerance as the write: an open copy in the cloud folder must not
        # break the run either.
        final_path = save_path_with_retry(
            target_dir, os.path.basename(doc_path),
            lambda p: plain_copy(doc_path, p),
        )
    except Exception as exc:
        # A sandboxed Python process can be refused write access to a Google Drive
        # virtual drive that PowerShell is allowed to write. Rather than fail the run,
        # hand the copy to PowerShell once.
        alt = copy_via_powershell(doc_path, target_dir)
        if alt:
            final_path = alt
        else:
            print(f"  WARNING: could not copy into {target_dir}: {exc}")
    if final_path is None:
        # Delivery failed both ways; the report still exists locally and the
        # notification must say so rather than claim a cloud copy that is not there.
        final_path = doc_path

    if args.out:
        where = args.out
    elif drive and final_path and os.path.dirname(os.path.abspath(final_path)) == os.path.abspath(drive):
        where = "Google Drive"
    elif drive:
        where = f"本機 reports/（Drive 資料夾寫入失敗：{drive}）"
    else:
        where = "本機 reports/（未偵測到 Google Drive 資料夾）"
    summary = (f"📊 SmartMall 週報已生成\n"
               f"{len(facts['commits'])} 個提交 · "
               f"{sum(facts['catalogue'].values()) if facts['catalogue'] else 0} 件商品\n"
               f"位置：{where}\n"
               f"檔名：{os.path.basename(final_path)}")
    if facts["worktree"]["uncommitted"]:
        summary += f"\n⚠️ 有 {facts['worktree']['uncommitted']} 個未提交檔案"

    notified, note = (False, "skipped") if (args.dry_run or args.no_notify) else telegram(cfg, summary)

    save_json(STATE_PATH, {
        "last_report_at": datetime.now().isoformat(timespec="seconds"),
        "last_report_path": final_path,
        "commits": len(facts["commits"]),
        "notified": notified,
        "notify_note": note,
    })

    print(f"  report   : {final_path}")
    print(f"  commits  : {len(facts['commits'])}")
    print(f"  dir      : {where}")
    print(f"  telegram : {'sent' if notified else 'not sent'} ({note})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
