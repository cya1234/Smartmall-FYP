"""Draw clean flat illustrations for the products that had no photo.

Six items in the catalogue shipped without an image and fell back to an emoji. There
is no internet access from this machine to fetch photographs, so these are drawn
rather than downloaded — deliberately, and they are labelled as illustrations in the
README rather than passed off as product photography.

Style matches the existing cut-outs: 525x700, pure white background, soft shadow.
Rendered at 4x and downsampled so the edges are anti-aliased.

    python tools/draw_missing_product_images.py
"""
import json
import os
import re

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT_DIR = os.path.join(ROOT, "public", "assets", "products")
PRODUCTS = os.path.join(ROOT, "data", "products.json")

W, H = 525, 700
SS = 4                      # supersample factor
BG = (255, 255, 255)


def canvas():
    img = Image.new("RGB", (W * SS, H * SS), BG)
    return img, ImageDraw.Draw(img)


def finish(img, name):
    out = img.resize((W, H), Image.LANCZOS)
    path = os.path.join(OUT_DIR, name)
    out.save(path, "PNG", optimize=True)
    return path


def shadow(img, box, alpha=38):
    """Soft ellipse shadow under the object."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = [v * SS for v in box]
    d.ellipse([x0, y0, x1, y1], fill=(20, 24, 32, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(10 * SS))
    img.paste(Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"), (0, 0))


def S(*vals):
    return [v * SS for v in vals]


# --------------------------------------------------------------- p008 jacket --
def denim_jacket():
    img, d = canvas()
    base, dark, light, thread = (62, 81, 117), (49, 64, 92), (86, 110, 148), (201, 162, 39)

    shadow(img, (150, 600, 400, 640), 40)
    d = ImageDraw.Draw(img)

    # sleeves, angled outward from the shoulder seam
    d.polygon(S(196, 236, 158, 268, 138, 508, 182, 516, 200, 330), fill=dark)
    d.polygon(S(329, 236, 367, 268, 387, 508, 343, 516, 325, 330), fill=dark)
    # torso
    d.polygon(S(196, 230, 329, 230, 337, 540, 188, 540), fill=base)
    # yoke across the shoulders
    d.polygon(S(196, 230, 329, 230, 322, 272, 203, 272), fill=dark)
    # front opening: a V at the neck, then a placket down the middle
    d.polygon(S(248, 230, 277, 230, 268, 300, 257, 300), fill=light)
    d.polygon(S(255, 300, 270, 300, 272, 540, 253, 540), fill=light)
    # collar: two flaps lying on the shoulders, pointing down and inward
    d.polygon(S(248, 232, 206, 242, 236, 296, 252, 268), fill=light)
    d.polygon(S(277, 232, 319, 242, 289, 296, 273, 268), fill=light)
    d.line(S(248, 232, 236, 296), fill=dark, width=SS)
    d.line(S(277, 232, 289, 296), fill=dark, width=SS)
    # chest pockets
    for x in (204, 283):
        d.rounded_rectangle(S(x, 306, x + 42, 360), radius=4 * SS, fill=dark)
        d.polygon(S(x, 306, x + 42, 306, x + 42, 320, x, 320), fill=light)
    # stitching
    for y in range(330, 520, 26):
        d.line(S(200, y, 246, y), fill=thread, width=max(1, SS))
        d.line(S(279, y, 325, y), fill=thread, width=max(1, SS))
    # buttons
    for y in (306, 364, 422, 480):
        d.ellipse(S(257, y, 268, y + 11), fill=thread)
    # hem band
    d.rectangle(S(188, 512, 337, 540), fill=dark)
    return finish(img, "p008.png")


# ------------------------------------------------------------------ p018 hat --
def straw_hat():
    img, d = canvas()
    straw, dark, band = (217, 179, 107), (184, 146, 76), (122, 91, 51)

    shadow(img, (120, 470, 405, 520), 42)
    d = ImageDraw.Draw(img)

    # crown
    d.pieslice(S(168, 268, 357, 476), 180, 360, fill=straw)
    d.rectangle(S(168, 372, 357, 452), fill=straw)
    # brim
    d.ellipse(S(58, 398, 467, 508), fill=straw)
    d.ellipse(S(58, 398, 467, 508), outline=dark, width=2 * SS)
    # band
    d.rectangle(S(170, 396, 355, 424), fill=band)
    d.ellipse(S(58, 420, 467, 486), fill=straw)
    # woven rings on the brim
    for i, ins in enumerate((14, 40, 66, 92)):
        d.ellipse(S(58 + ins, 420 + ins * 0.28, 467 - ins, 486 - ins * 0.28),
                  outline=dark, width=max(1, SS))
    # crown weave: arcs kept inside the crown silhouette
    for y in range(296, 392, 16):
        half = 94 * (1 - ((y - 296) / 120) ** 2) ** 0.5
        d.arc(S(262 - half, y - 44, 262 + half, y + 44), 200, 340,
              fill=dark, width=max(1, SS))
    return finish(img, "p018.png")


# -------------------------------------------------------------- p027 diffuser --
def diffuser():
    img, d = canvas()
    bone, shade, reed, mist = (239, 233, 222), (217, 208, 192), (176, 138, 94), (200, 214, 220)

    shadow(img, (185, 560, 340, 600), 40)
    d = ImageDraw.Draw(img)

    # reeds
    for dx, top in ((-34, 150), (-16, 122), (4, 132), (24, 112), (40, 152)):
        d.line(S(262 + dx * 0.35, 356, 262 + dx, top), fill=reed, width=3 * SS)
    # neck
    d.rounded_rectangle(S(242, 336, 282, 372), radius=6 * SS, fill=shade)
    # body
    d.rounded_rectangle(S(206, 366, 318, 556), radius=26 * SS, fill=bone)
    d.ellipse(S(206, 520, 318, 580), fill=bone)
    # shading on the right side
    d.rounded_rectangle(S(286, 372, 318, 552), radius=16 * SS, fill=shade)
    # inset line
    d.line(S(214, 410, 310, 410), fill=shade, width=2 * SS)
    # mist
    for cx, cy, r in ((150, 210, 14), (128, 246, 9), (176, 190, 7)):
        d.ellipse(S(cx - r, cy - r, cx + r, cy + r), fill=mist)
    return finish(img, "p027.png")


# -------------------------------------------------------------- p028 dinnerware
def dinnerware():
    img, d = canvas()
    sage, shade, lit = (156, 174, 151), (126, 145, 121), (185, 199, 180)

    shadow(img, (140, 540, 390, 585), 40)
    d = ImageDraw.Draw(img)

    # two plates
    d.ellipse(S(96, 452, 429, 548), fill=sage)
    d.ellipse(S(96, 452, 429, 548), outline=shade, width=2 * SS)
    d.ellipse(S(140, 470, 385, 526), outline=lit, width=2 * SS)
    d.ellipse(S(120, 372, 405, 462), fill=sage)
    d.ellipse(S(120, 372, 405, 462), outline=shade, width=2 * SS)
    d.ellipse(S(160, 390, 365, 442), outline=lit, width=2 * SS)
    # bowl on top
    d.ellipse(S(178, 292, 347, 352), fill=lit)
    d.pieslice(S(178, 300, 347, 430), 0, 180, fill=sage)
    d.ellipse(S(178, 292, 347, 352), outline=shade, width=2 * SS)
    d.arc(S(196, 322, 329, 400), 20, 160, fill=shade, width=max(1, SS))
    return finish(img, "p028.png")


# ----------------------------------------------------------------- p029 earbuds
def earbuds():
    img, d = canvas()
    dark, mid, lit = (38, 40, 45), (78, 84, 95), (140, 149, 160)

    shadow(img, (120, 560, 405, 604), 40)
    d = ImageDraw.Draw(img)

    # closed charging case with a lid seam
    d.rounded_rectangle(S(140, 316, 385, 486), radius=36 * SS, fill=dark)
    d.rounded_rectangle(S(140, 316, 385, 400), radius=36 * SS, fill=mid)
    d.line(S(148, 400, 377, 400), fill=(22, 24, 28), width=2 * SS)
    d.rounded_rectangle(S(230, 430, 295, 444), radius=7 * SS, fill=(30, 32, 36))
    d.ellipse(S(256, 460, 270, 474), fill=(96, 208, 160))

    # one earbud resting in front, drawn on its own layer so it can be rotated.
    # A capsule plus a nozzle reads as an earbud; a circle with a light centre
    # reads as a face, which is what the first attempt looked like.
    bud = Image.new("RGBA", (150 * SS, 150 * SS), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bud)
    bd.rounded_rectangle([20 * SS, 56 * SS, 116 * SS, 104 * SS], radius=24 * SS, fill=mid + (255,))
    bd.ellipse([92 * SS, 58 * SS, 132 * SS, 102 * SS], fill=lit + (255,))
    bd.ellipse([8 * SS, 58 * SS, 54 * SS, 102 * SS], fill=mid + (255,))
    for angle, pos in ((-18, (176, 522)), (14, (300, 540))):
        r = bud.rotate(angle, resample=Image.BICUBIC, expand=False)
        img.paste(r, (pos[0] * SS - 75 * SS, pos[1] * SS - 75 * SS), r)
    return finish(img, "p029.png")


# ----------------------------------------------------------------- p036 beanie
def beanie():
    img, d = canvas()
    rust, dark, rib = (168, 90, 60), (139, 69, 43), (147, 72, 47)

    shadow(img, (150, 555, 385, 598), 40)
    d = ImageDraw.Draw(img)

    # crown
    d.pieslice(S(140, 240, 385, 520), 180, 360, fill=rust)
    d.rectangle(S(140, 380, 385, 470), fill=rust)
    # cuff
    d.rounded_rectangle(S(132, 448, 393, 548), radius=22 * SS, fill=dark)
    # ribbing
    for x in range(146, 390, 20):
        d.line(S(x, 456, x, 540), fill=rib, width=2 * SS)
    # knit: vertical ribs converging gently toward the crown. Horizontal arcs read
    # as wood grain, which is what the previous attempt looked like.
    for x in range(158, 378, 23):
        top_x = 262 + (x - 262) * 0.28
        d.line(S(x, 470, top_x, 262), fill=rib, width=max(1, int(SS * 1.4)))
    # fold highlight
    d.arc(S(140, 452, 385, 540), 200, 340, fill=rib, width=2 * SS)
    return finish(img, "p036.png")


# ---------------------------------------------------------------------- main --
DRAWERS = {
    "p008": denim_jacket,
    "p018": straw_hat,
    "p027": diffuser,
    "p028": dinnerware,
    "p029": earbuds,
    "p036": beanie,
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for pid, fn in DRAWERS.items():
        path = fn()
        print(f"  drew {pid} -> {os.path.basename(path)} "
              f"({os.path.getsize(path) // 1024} KB)")

    # Point the catalogue at the new files. Done by regex so the rest of the JSON
    # keeps its exact formatting and the diff stays readable.
    with open(PRODUCTS, encoding="utf-8") as fh:
        text = fh.read()

    changed = 0
    for pid in DRAWERS:
        pattern = re.compile(r'("id":\s*"%s",\s*)' % re.escape(pid))
        if not pattern.search(text):
            print(f"  ! could not find {pid} in products.json")
            continue
        # drop any pre-existing empty image field, then insert the new one
        text = re.sub(r'("id":\s*"%s",\s*)"image":\s*"[^"]*",\s*' % re.escape(pid),
                      r'\1', text)
        text = re.sub(r'("id":\s*"%s",\s*)"illustration":\s*true,\s*' % re.escape(pid),
                      r'\1', text)
        # `illustration` keeps these out of the CLIP index: they sit in a different
        # part of the embedding space from studio photographs and steal top-1 results.
        text = pattern.sub(
            r'\1"image": "/assets/products/%s.png", "illustration": true, ' % pid,
            text, count=1)
        changed += 1

    with open(PRODUCTS, "w", encoding="utf-8") as fh:
        fh.write(text)

    data = json.loads(text)
    still = [p["id"] for p in data if not p.get("image")]
    print(f"\n  updated {changed} products")
    print(f"  products still without an image: {len(still)}" + (f" {still}" if still else ""))


if __name__ == "__main__":
    main()
