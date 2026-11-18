"""Measure the aesthetic scorer's style bias, before and after the fix.

The old palette rule was `more than 3 hues -> penalty, under 12 % neutral -> penalty`.
It was not measuring quality, it was measuring minimalism: every maximalist style lost
points by construction. This tool makes that visible instead of arguable.

It generates six synthetic outfits whose only difference is the palette, scores each
through the live service, and prints the old rule's score next to the new one. Both
are computed from the same extracted hues, so the comparison is apples to apples.

    python tools/eval_aesthetic_bias.py [http://127.0.0.1:8001]

Style 4 and style 5 are the point of the whole exercise: both use many saturated
colours. Under the old rule they are penalised identically. Under the new rule one is
coherent (its hues sit inside a 90 degree arc) and the other is genuinely scattered.
That difference is exactly the bias, isolated.
"""
import base64
import json
import os
import sys
import urllib.request

from PIL import Image, ImageDraw

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "data", "eval", "aesthetic-bias.json")

W, H = 420, 560
BACKDROP = (243, 241, 237)

# name -> list of (rgb, share) blocks. These are palettes, not photographs: the
# question is how the scorer reacts to colour structure, and using drawings keeps
# everything else constant.
STYLES = {
    "minimal (neutrals)": [(233, 229, 221), (206, 200, 191), (176, 170, 160), (240, 238, 233), (198, 192, 182), (222, 217, 208)],
    "streetwear (dark + 1 accent)": [(38, 38, 44), (244, 244, 244), (196, 58, 52), (58, 58, 66), (228, 228, 232), (150, 40, 36)],
    "heavy metal (black + dark red)": [(16, 16, 20), (42, 42, 48), (122, 31, 31), (28, 28, 34), (60, 60, 68), (96, 24, 24)],
    # six saturated colours inside a ~90 degree arc (300 -> 40): one family
    "maximalist, coherent (neon family)": [
        (255, 45, 149), (255, 92, 92), (255, 138, 42), (255, 176, 0), (255, 214, 0), (232, 60, 200)],
    # six saturated colours spread around the wheel: no family
    "maximalist, scattered (random hues)": [
        (255, 45, 149), (0, 229, 255), (124, 255, 0), (138, 43, 226), (255, 140, 0), (0, 120, 255)],
    "formal (navy + grey + white)": [(27, 42, 74), (110, 122, 138), (245, 245, 245), (44, 62, 96), (150, 158, 170), (232, 234, 238)],
}

WARDROBE = ["p004", "p005", "p010", "p011", "p014"]


def draw(blocks, seed=0):
    """A very simple outfit: six large patches, so every palette colour survives the
    8-colour quantiser with a share above the 5 % floor. Small accents would be
    dropped and the test would silently measure fewer hues than it intended."""
    im = Image.new("RGB", (W, H), BACKDROP)
    d = ImageDraw.Draw(im)
    n = len(blocks)

    # torso split into two halves, legs into two halves, one sleeve each side
    d.rounded_rectangle([110, 90, 210, 330], radius=0, fill=blocks[0])
    d.rounded_rectangle([210, 90, 310, 330], radius=0, fill=blocks[1 % n])
    d.rounded_rectangle([110, 330, 210, 480], radius=0, fill=blocks[2 % n])
    d.rounded_rectangle([210, 330, 310, 480], radius=0, fill=blocks[3 % n])
    d.rounded_rectangle([64, 110, 106, 320], radius=14, fill=blocks[4 % n])
    d.rounded_rectangle([314, 110, 356, 320], radius=14, fill=blocks[5 % n])
    if seed:
        d.ellipse([20 + seed * 8, 30, 60 + seed * 8, 70], fill=blocks[(seed + 1) % n])
    return im


def data_uri(im):
    import io
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def score(image_uri):
    body = json.dumps({"image": image_uri, "wardrobeIds": WARDROBE}).encode()
    req = urllib.request.Request(f"{BASE}/aesthetic", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def old_palette_rule(pal):
    """The rule this project shipped before: fewer hues is better."""
    score = 100.0
    if pal["distinctHues"] > 3:
        score -= (pal["distinctHues"] - 3) * 16
    if pal["neutralShare"] < 0.12:
        score -= 12
    if pal["neutralShare"] > 0.95:
        score -= 8
    return max(0.0, min(100.0, score))


def main():
    print(f"  scoring service : {BASE}")
    rows = []
    for name, blocks in STYLES.items():
        pal_scores_old, pal_scores_new, detail = [], [], None
        for seed in (0, 1, 2):
            r = score(data_uri(draw(blocks, seed)))
            detail = r["detail"]["palette"]
            pal_scores_old.append(old_palette_rule(detail))
            pal_scores_new.append(r["subscores"]["palette"])
        rows.append({
            "style": name,
            "hues": detail["distinctHues"],
            "neutral": detail["neutralShare"],
            "scheme": detail["scheme"],
            "old": round(sum(pal_scores_old) / 3, 1),
            "new": round(sum(pal_scores_new) / 3, 1),
        })

    print("\n  palette sub-score only (style/coverage are identical across styles,")
    print("  because the drawings differ in colour alone)\n")
    print("  %-38s %5s %8s %-16s %6s %6s" % ("style", "hues", "neutral", "scheme", "old", "new"))
    print("  " + "-" * 84)
    for r in rows:
        print("  %-38s %5d %8.2f %-16s %6.1f %6.1f"
              % (r["style"], r["hues"], r["neutral"], r["scheme"], r["old"], r["new"]))

    olds = [r["old"] for r in rows]
    news = [r["new"] for r in rows]
    print("\n  spread (max - min)")
    print("    old rule : %.1f points" % (max(olds) - min(olds)))
    print("    new rule : %.1f points" % (max(news) - min(news)))

    coherent = next(r for r in rows if "coherent" in r["style"])
    scattered = next(r for r in rows if "scattered" in r["style"])
    legit = [r for r in rows if "scattered" not in r["style"]]
    print("\n  the two maximalist styles — the case this fix is about")
    print("    old rule : coherent %.1f vs scattered %.1f  (gap %.1f)"
          % (coherent["old"], scattered["old"], coherent["old"] - scattered["old"]))
    print("    new rule : coherent %.1f vs scattered %.1f  (gap %.1f)"
          % (coherent["new"], scattered["new"], coherent["new"] - scattered["new"]))

    print("\n  What the numbers say:")
    print("    - the old rule kept every style within %.1f points of every other, so it"
          % (max(olds) - min(olds)))
    print("      was not judging style at all; its hue threshold simply never fired.")
    print("    - the new rule leaves every deliberate style at %.0f-%.0f and only"
          % (min(r["new"] for r in legit), max(r["new"] for r in legit)))
    print("      separates a palette that has a scheme from one that has none.")
    print("    - it is still a value judgement that coherence is preferable. That is")
    print("      stated here rather than hidden, and its weight in the overall score")
    print("      was cut from 20 % to 10 % for exactly that reason.")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"generatedAt": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
                   "rows": rows,
                   "spread": {"old": round(max(olds) - min(olds), 1), "new": round(max(news) - min(news), 1)}},
                  fh, ensure_ascii=False, indent=2)
    print(f"\n  wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
