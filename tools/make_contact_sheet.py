"""Build a contact sheet of the product photos for a quick visual QA pass."""
import glob
import json
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PUBLIC = os.path.join(ROOT, "public")
PRODUCTS = os.path.join(ROOT, "data", "products.json")
OUT = os.path.join(ROOT, ".cache", "contact-sheet.jpg")

COLS = 6
CELL_W, CELL_H = 150, 210
LABEL_H = 22


def main():
    with open(PRODUCTS, encoding="utf-8") as fh:
        products = json.load(fh)
    withimg = [p for p in products if p.get("image")]
    rows = (len(withimg) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * CELL_W, rows * (CELL_H + LABEL_H)), "white")
    draw = ImageDraw.Draw(sheet)

    for i, p in enumerate(withimg):
        path = os.path.join(PUBLIC, p["image"].lstrip("/").replace("/", os.sep))
        if not os.path.exists(path):
            continue
        im = Image.open(path).convert("RGB")
        im.thumbnail((CELL_W - 8, CELL_H - 8), Image.LANCZOS)
        cx = (i % COLS) * CELL_W + (CELL_W - im.width) // 2
        cy = (i // COLS) * (CELL_H + LABEL_H) + (CELL_H - im.height) // 2
        sheet.paste(im, (cx, cy))
        draw.text(((i % COLS) * CELL_W + 6, (i // COLS) * (CELL_H + LABEL_H) + CELL_H + 4),
                  f"{p['id']} {p['name'][:18]}", fill="black")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    sheet.save(OUT, quality=88)
    print(f"  wrote {OUT}  ({sheet.width}x{sheet.height}, {len(withimg)} photos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
