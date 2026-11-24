"""Collect the facts a weekly project report needs.

The point is that every report starts from the repository rather than from memory: what
changed since the last report, what the codebase actually contains now, which assertions
exist, and whether anything is left uncommitted.

    python tools/weekly_report.py                 # last 7 days
    python tools/weekly_report.py --since "14 days ago"
    python tools/weekly_report.py --markdown      # ready to paste into a chat

Exit code is always 0: a report that cannot reach the running services should still
report the rest rather than fail.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BASE = "http://127.0.0.1:3000"


def git(*args):
    try:
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
        return out.stdout.strip()
    except Exception:
        return ""


def commits_since(since):
    """One entry per commit, message body folded into the subject."""
    raw = git("log", f"--since={since}", "--pretty=format:%h\x1f%ad\x1f%s\x1f%b\x1e", "--date=short")
    if not raw:
        return []
    out = []
    for chunk in raw.split("\x1e"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split("\x1f")
        if len(parts) < 3:
            continue
        sha, date, subject = parts[0], parts[1], parts[2]
        body = parts[3] if len(parts) > 3 else ""
        out.append({"sha": sha, "date": date, "subject": subject, "body": body.strip()})
    return out


def code_stats():
    """Rough size of the project, by kind of file."""
    kinds = {
        "server / lib (js)": ["server.js", "lib"],
        "front-end (js)": ["public/js"],
        "styles (css)": ["public/css"],
        "ai services (py)": ["ai-service"],
        "tools (py/js)": ["tools"],
    }
    result = {}
    for label, targets in kinds.items():
        total = 0
        files = 0
        for t in targets:
            p = os.path.join(ROOT, t)
            if os.path.isfile(p):
                total += sum(1 for _ in open(p, encoding="utf-8", errors="ignore"))
                files += 1
            elif os.path.isdir(p):
                for dirpath, dirnames, filenames in os.walk(p):
                    dirnames[:] = [d for d in dirnames if d not in
                                   ("vendor", "node_modules", "__pycache__", "models")]
                    for fn in filenames:
                        if fn.endswith((".js", ".py", ".css")):
                            try:
                                with open(os.path.join(dirpath, fn), encoding="utf-8",
                                          errors="ignore") as fh:
                                    total += sum(1 for _ in fh)
                                files += 1
                            except OSError:
                                pass
        if files:
            result[label] = {"files": files, "lines": total}
    return result


def test_inventory():
    """Which test files exist, and how many checks each claims to make."""
    out = []
    tools = os.path.join(ROOT, "tools")
    for fn in sorted(os.listdir(tools)):
        if not fn.startswith("test_"):
            continue
        path = os.path.join(tools, fn)
        try:
            src = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        checks = len(re.findall(r"\bcheck\(", src))
        out.append({"file": fn, "checks": checks})
    return out


def services():
    """Which AI services answer right now. Report-only; never raises."""
    state = {"web": False, "visual": False, "forecast": False, "tryon": False}
    probes = {
        "web": f"{BASE}/api/health",
        "visual": f"{BASE}/api/visual-search/status",
        "forecast": f"{BASE}/api/forecast/status",
        "tryon": f"{BASE}/api/tryon/status",
    }
    for key, url in probes.items():
        try:
            with urllib.request.urlopen(url, timeout=4) as r:
                state[key] = r.status == 200
        except Exception:
            state[key] = False
    return state


def catalogue():
    """Product count by category, straight from the data file."""
    path = os.path.join(ROOT, "data", "products.json")
    try:
        products = json.load(open(path, encoding="utf-8"))
    except Exception:
        return {}
    counts = {}
    for p in products:
        counts[p.get("category", "?")] = counts.get(p.get("category", "?"), 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def worktree():
    dirty = git("status", "--porcelain")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    ahead = git("rev-list", "--count", "origin/main..HEAD") if git("remote") else ""
    return {
        "branch": branch,
        "uncommitted": len([l for l in dirty.splitlines() if l.strip()]),
        "unpushed": ahead,
        "head": git("log", "-1", "--pretty=%h %s"),
    }


def collect(since):
    return {
        "generated": datetime.now(timezone.utc).astimezone().isoformat(timespec="minutes"),
        "since": since,
        "worktree": worktree(),
        "commits": commits_since(since),
        "code": code_stats(),
        "tests": test_inventory(),
        "services": services(),
        "catalogue": catalogue(),
    }


def as_markdown(rep):
    L = []
    L.append(f"## 每週進度報告 · {rep['generated'][:10]}")
    L.append("")
    w = rep["worktree"]
    L.append(f"- 分支 `{w['branch']}` · HEAD `{w['head']}`")
    L.append(f"- 未提交：{w['uncommitted']} 個檔案 · 未推送：{w['unpushed'] or 0} 個 commit")
    L.append("")

    L.append(f"### 本週提交（{len(rep['commits'])} 個，自 {rep['since']}）")
    if not rep["commits"]:
        L.append("_這段時間沒有提交。_")
    for c in rep["commits"]:
        L.append(f"- `{c['sha']}` {c['subject']}")
    L.append("")

    L.append("### 目前規模")
    for k, v in rep["code"].items():
        L.append(f"- {k}：{v['files']} 個檔案 / {v['lines']} 行")
    if rep["catalogue"]:
        L.append(f"- 商品：{sum(rep['catalogue'].values())} 件 " +
                 "（" + "、".join(f"{k} {v}" for k, v in rep["catalogue"].items()) + "）")
    L.append("")

    total_checks = sum(t["checks"] for t in rep["tests"])
    L.append(f"### 測試（{len(rep['tests'])} 個檔案，約 {total_checks} 項檢查）")
    for t in rep["tests"]:
        L.append(f"- {t['file']}（{t['checks']}）")
    L.append("")

    s = rep["services"]
    up = [k for k, v in s.items() if v]
    L.append("### 服務狀態")
    L.append("- 運行中：" + ("、".join(up) if up else "全部已關閉"))
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="7 days ago")
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = collect(args.since)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    elif args.markdown:
        print(as_markdown(rep))
    else:
        print(as_markdown(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
