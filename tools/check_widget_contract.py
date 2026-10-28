"""Static contract check: every element id the widget JS touches must exist in
widget.html, and every w-* class used must be defined in widget.css."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
html = (ROOT / "public" / "widget.html").read_text(encoding="utf-8")
js = (ROOT / "public" / "js" / "widget.js").read_text(encoding="utf-8")
css = (ROOT / "public" / "css" / "widget.css").read_text(encoding="utf-8")

fails = []

html_ids = set(re.findall(r'id="([\w-]+)"', html))
js_ids = set(re.findall(r"\$\('([\w-]+)'\)", js))
tabs = re.findall(r'data-tab="(\w+)"', html)
js_ids |= {f"w-pane-{t}" for t in tabs}

missing = sorted(js_ids - html_ids)
print(f"  ids in html      : {len(html_ids)}")
print(f"  ids used by js   : {len(js_ids)}")
print(f"  missing in html  : {missing if missing else 'none'}")
if missing:
    fails.append("missing ids")

# classes referenced anywhere (html attributes + js template strings)
used = set()
for m in re.findall(r'class="([^"]+)"', html):
    used.update(m.split())
for m in re.findall(r'class=\\?"([\w\- ]+)"', js):
    used.update(m.split())
for m in re.findall(r"className = '([\w\- ]+)'", js):
    used.update(m.split())
widget_classes = {c for c in used if c.startswith("w-")}

undefined = sorted(c for c in widget_classes if f".{c}" not in css)
print(f"  w-* classes used : {len(widget_classes)}")
print(f"  undefined in css : {undefined if undefined else 'none'}")
if undefined:
    fails.append("undefined classes")

# embed.js must expose the handshake the panel replies to
embed = (ROOT / "public" / "embed.js").read_text(encoding="utf-8")
for msg in ["smartmall:ready", "smartmall:init", "smartmall:close"]:
    ok = msg in embed and msg in js
    print(f"  handshake {msg:18s} embed={msg in embed} panel={msg in js}")
    if not ok:
        fails.append(f"handshake {msg}")

print()
print("DOM CONTRACT OK" if not fails else f"FAILURES: {fails}")
