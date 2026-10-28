"""Convert the site to a dark theme and add motion.

Strategy: the stylesheet is almost entirely driven by the `:root` custom
properties, so most components flip automatically. What does not flip is the
~20 rules that hard-code a white background and the handful of light "tint"
gradients. Those are rewritten explicitly, then any remaining high-lightness
colour is reported so a second pass can catch stragglers.

Run:  python tools/dark_theme.py [--check]
"""
import re
import sys

PATH = "public/css/styles.css"

ROOT_BLOCK = """:root {
  /* dark palette */
  --bg: #0A0C11;
  --surface: #12151D;
  --surface-2: #191D27;
  --ink: #F3F5F9;
  --ink-2: #AEB6C6;
  --muted: #79828F;
  --line: #242A36;
  --brand: #8B7BFF;
  --brand-2: #A995FF;
  --brand-soft: #221E42;
  --accent: #FF8A66;
  --good: #3DD68C;
  --warn: #F5B54A;
  --bad: #FF6B6B;
  --glass: rgba(10, 12, 17, 0.72);
  --radius: 16px;
  --radius-sm: 10px;
  --shadow: 0 20px 50px rgba(0, 0, 0, 0.55);
  --shadow-sm: 0 2px 14px rgba(0, 0, 0, 0.4);
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}"""

# White backgrounds become themed surfaces.
BG_RULES = [
    (r"background:\s*#fff\b", "background: var(--surface)"),
    (r"background:\s*#ffffff\b", "background: var(--surface)"),
    (r"background:\s*white\b", "background: var(--surface)"),
]

# Light tints that assume a white page.
TINT_RULES = [
    ("linear-gradient(180deg, #ffffff, var(--bg))",
     "linear-gradient(180deg, #151922, var(--bg))"),
    ("background: linear-gradient(180deg, #f6fbf7, #fff); border-color: #cfe9d8;",
     "background: linear-gradient(180deg, #14251B, var(--surface)); border-color: #2A4A38;"),
    (".offer-table tr.best { background: #f4fbf6; }",
     ".offer-table tr.best { background: #14251B; }"),
    ("background: linear-gradient(180deg, #f7fdf9, #fff);",
     "background: linear-gradient(180deg, #14251B, var(--surface));"),
    ("border-color: #cfe9d8; background: linear-gradient(180deg, #f7fdf9, #fff);",
     "border-color: #2A4A38; background: linear-gradient(180deg, #14251B, var(--surface));"),
    ("border-color: #f4e2c0; background: linear-gradient(180deg, #fffdf7, #fff);",
     "border-color: #4A3A1E; background: linear-gradient(180deg, #241E12, var(--surface));"),
    ("background: #f4fbf6; border: 1px dashed #cfe9d8;",
     "background: #14251B; border: 1px dashed #2A4A38;"),
    ("background: linear-gradient(135deg, #f7f5ff, #ffffff);",
     "background: linear-gradient(135deg, #191423, var(--surface));"),
    (".delivery-opt.active { border-color: var(--brand); background: #f8f7ff; }",
     ".delivery-opt.active { border-color: var(--brand); background: #1E1A38; }"),
    ("background: rgba(255, 255, 255, 0.85);", "background: var(--glass);"),
    ("background: rgba(255,255,255,0.85);", "background: rgba(18, 21, 29, 0.86);"),
    ("background: rgba(255,255,255,0.9);", "background: rgba(18, 21, 29, 0.9);"),
    ("background: #eaf7ef; border-radius: 9px;", "background: #16301F; border-radius: 9px;"),
    ("color: #fff; background: #fdf4e3;", "color: #fff; background: #2E2412;"),
    (".qty.low { color: #b3730c; background: #fdf4e3; }",
     ".qty.low { color: #F5B54A; background: #2E2412; }"),
    (".exit-close:hover { background: #e7e9f1; }",
     ".exit-close:hover { background: var(--surface-2); }"),
    ("border-color: #c9c3ff;", "border-color: var(--brand);"),
    ("border-color: #d9d3ff;", "border-color: var(--brand);"),
    ("background: #ece9ff; border-color: #d9d3ff; color: var(--brand);",
     "background: var(--brand-soft); border-color: var(--brand); color: var(--brand-2);"),
]

# Pale pastel fills referenced directly by badges and advisory boxes.
COLOR_MAP = {
    "#e5f7ee": "#14301F",   # pale green fill
    "#eafaf1": "#14301F",
    "#eef7f0": "#14291C",
    "#fdf3e2": "#2E2412",   # pale amber fill
    "#fdecec": "#2E1A1C",   # pale red fill
    "#f3f0ff": "#1F1B3A",   # pale lavender fill
    "#cfe9d8": "#2A4A38",   # pale green border
    "#f4e2c0": "#4A3A1E",   # pale amber border
    "#c07c10": "#F5B54A",   # dark amber text
    "#1f7a45": "#3DD68C",   # dark green text
    "#4b3fd0": "#A995FF",   # dark lavender text
    "#b3730c": "#F5B54A",
}

MOTION = """
/* =========================================================================
   Motion & depth (dark theme)
   ========================================================================= */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: none; }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes pulseGlow {
  0%, 100% { opacity: 0.55; }
  50%      { opacity: 0.9; }
}

body {
  background-image:
    radial-gradient(900px 520px at 12% -10%, rgba(139, 123, 255, 0.16), transparent 62%),
    radial-gradient(760px 480px at 92% 4%, rgba(255, 138, 102, 0.10), transparent 58%);
  background-repeat: no-repeat;
  background-attachment: fixed;
}

/* Route transitions: the SPA replaces #app's contents on every navigation. */
#app > section {
  animation: fadeUp 0.34s cubic-bezier(0.22, 0.8, 0.3, 1) both;
}

/* Cards lift slightly, never jump. */
.card, .hero-card, .garment, .store-card, .tier, .listing, .poll-card,
.risk-card, .insight, .product-card {
  transition: transform 0.22s cubic-bezier(0.22, 0.8, 0.3, 1),
              box-shadow 0.22s ease, border-color 0.22s ease,
              background-color 0.22s ease;
}
.card:hover, .hero-card:hover, .store-card:hover, .tier:hover,
.listing:hover, .product-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow);
  border-color: #31394a;
}

/* Grid children fade in with a small stagger. */
.grid > *, .store-grid > *, .garment-list > * {
  animation: fadeUp 0.4s cubic-bezier(0.22, 0.8, 0.3, 1) both;
}
.grid > *:nth-child(1), .store-grid > *:nth-child(1) { animation-delay: 0.02s; }
.grid > *:nth-child(2), .store-grid > *:nth-child(2) { animation-delay: 0.05s; }
.grid > *:nth-child(3), .store-grid > *:nth-child(3) { animation-delay: 0.08s; }
.grid > *:nth-child(4), .store-grid > *:nth-child(4) { animation-delay: 0.11s; }
.grid > *:nth-child(5), .store-grid > *:nth-child(5) { animation-delay: 0.14s; }
.grid > *:nth-child(6), .store-grid > *:nth-child(6) { animation-delay: 0.17s; }
.grid > *:nth-child(n+7) { animation-delay: 0.2s; }

.btn, .chip, .pay-chip, .main-nav a, .size-btn, .w-tab, .delivery-opt {
  transition: transform 0.14s ease, background 0.18s ease,
              border-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
}
.btn:active { transform: translateY(1px) scale(0.995); }

/* Primary actions get a soft brand glow on hover. */
.btn-primary:hover, .btn-accent:hover {
  box-shadow: 0 10px 26px rgba(139, 123, 255, 0.34);
}
.btn-primary:hover { background: var(--brand-2); }

input, select, textarea {
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}
input:focus, select:focus, textarea:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(139, 123, 255, 0.18);
  outline: none;
}

.topbar {
  background: var(--glass);
  backdrop-filter: saturate(160%) blur(16px);
  border-bottom: 1px solid var(--line);
}

.footer { background: var(--surface); }

/* Scrollbar in the dark theme. */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: #2a3140; border-radius: 6px; }
::-webkit-scrollbar-thumb:hover { background: #3a4356; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
}
"""


def lightness(hexcol):
    h = hexcol.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


def main():
    check_only = "--check" in sys.argv
    with open(PATH, encoding="utf-8") as fh:
        css = fh.read()

    original = css
    counts = {}

    if not check_only:
        css = re.sub(r":root\s*\{.*?\}", ROOT_BLOCK, css, count=1, flags=re.S)
        counts["root"] = 1

        for pattern, repl in BG_RULES:
            css, n = re.subn(pattern, repl, css)
            counts[f"bg:{pattern}"] = n

        for old, new in TINT_RULES:
            n = css.count(old)
            if n:
                css = css.replace(old, new)
            counts[f"tint:{old[:34]}"] = n

        for old, new in COLOR_MAP.items():
            n = len(re.findall(re.escape(old), css, flags=re.I))
            if n:
                css = re.sub(re.escape(old), new, css, flags=re.I)
            counts[f"colour:{old}"] = n

        if "Motion & depth (dark theme)" not in css:
            css = css.rstrip() + "\n" + MOTION

    # Report any remaining light backgrounds / near-white fills.
    suspects = []
    for m in re.finditer(r"(?:background(?:-color)?|fill)\s*:\s*(#[0-9a-fA-F]{3,8})", css):
        lum = lightness(m.group(1))
        if lum is not None and lum > 0.82:
            line_no = css[:m.start()].count("\n") + 1
            suspects.append((line_no, m.group(1)))

    print(f"  file      : {PATH}  ({len(original)/1024:.1f} KB -> {len(css)/1024:.1f} KB)")
    total = sum(v for k, v in counts.items() if k != "root")
    print(f"  rewrites  : {total} across {len([k for k, v in counts.items() if v])} rules")
    print(f"  still-light backgrounds: {len(suspects)}")
    for line_no, col in suspects[:15]:
        snippet = css.splitlines()[line_no - 1].strip()[:88]
        print(f"    line {line_no:4d}  {col}  {snippet}")

    if check_only:
        return 0 if not suspects else 1

    with open(PATH, "w", encoding="utf-8") as fh:
        fh.write(css)
    print("  written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
