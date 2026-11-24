"""Repair .report/report.json into valid JSON, keeping any values already filled in.

The file that shipped as the template had `#` comment lines for guidance, which makes it
invalid JSON the moment it is used as the real config. This reads whatever is there,
pulls out the telegram token and chat id even from the broken file, and rewrites a clean
document.
"""
import io
import json
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PATH = os.path.join(ROOT, ".report", "report.json")

CLEAN = {
    "telegram": {"token": "", "chat_id": ""},
    "drive_folder": "",
    "ollama": {"enabled": False, "model": "qwen2.5:3b-instruct"},
}


def main():
    os.makedirs(os.path.dirname(PATH), exist_ok=True)

    token = ""
    chat = ""
    drive = ""
    if os.path.exists(PATH):
        raw = io.open(PATH, encoding="utf-8-sig", errors="replace").read()
        # Try strict JSON first.
        try:
            data = json.loads(raw)
            tg = data.get("telegram") or {}
            token = str(tg.get("token") or "")
            chat = str(tg.get("chat_id") or "")
            drive = str(data.get("drive_folder") or "")
        except Exception:
            # Fall back to scraping the values out of a commented or malformed file.
            m = re.search(r'"token"\s*:\s*"([^"]*)"', raw)
            if m:
                token = m.group(1)
            m = re.search(r'"chat_id"\s*:\s*"?([0-9\-]+)"?', raw)
            if m:
                chat = m.group(1)
            m = re.search(r'"drive_folder"\s*:\s*"([^"]*)"', raw)
            if m:
                drive = m.group(1).replace("\\\\", "\\")

    clean = {
        "telegram": {"token": token, "chat_id": chat},
        "drive_folder": drive,
        "ollama": CLEAN["ollama"],
    }
    with io.open(PATH, "w", encoding="utf-8") as fh:
        json.dump(clean, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    # Validate what we just wrote.
    json.loads(io.open(PATH, encoding="utf-8").read())
    filled = []
    if token:
        filled.append(f"token({len(token)} 字元)")
    if chat:
        filled.append("chat_id")
    if drive:
        filled.append("drive_folder")
    print(f"  path   : {PATH}")
    print(f"  valid  : yes")
    print(f"  filled : {', '.join(filled) if filled else '全部空白 —— 需要填入 token 和 chat_id'}")
    if not token or not chat:
        print("")
        print("  下一步：用記事本打開上面那個檔案，填入你的 Telegram token 和 chat_id。")
        print("  取得方法見 SETUP_WEEKLY_REPORT.md 的「第二步」和「第三步」。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
