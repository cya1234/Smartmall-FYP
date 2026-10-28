"""Pick a real product photo for each SmartMall catalog item.

Pages the HuggingFace datasets-server /rows endpoint (the /filter index is not
available for this dataset) to collect high-resolution product photos, matches
them to our catalog by garment type + colour, downloads them into
public/assets/products/, and records the path on each product.

Source dataset: benitomartin/fashion-product-images-small-900x1200
(metadata + imagery derived from the Myntra "Fashion Product Images" dataset).

Run:  .venv\\Scripts\\python.exe tools\\pick_product_images.py
"""
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PRODUCTS = os.path.join(ROOT, "data", "products.json")
OUTDIR = os.path.join(ROOT, "public", "assets", "products")
DS = "benitomartin/fashion-product-images-small-900x1200"
Q = urllib.parse.quote(DS)

# Garment types worth pulling from the dataset.
NEEDED = {
    "Dresses", "Shirts", "Tshirts", "Tops", "Sweaters", "Sweatshirts", "Jackets",
    "Rain Jacket", "Trousers", "Track Pants", "Jeans", "Shorts", "Leggings",
    "Casual Shoes", "Sports Shoes", "Formal Shoes", "Sandals", "Flip Flops",
    "Booties", "Heels", "Caps", "Hat", "Handbags", "Clutches", "Backpacks",
    "Wallets", "Watches", "Sunglasses", "Gloves", "Socks", "Mufflers", "Scarves",
    "Innerwear Vests", "Perfume and Body Mist", "Lipstick", "Deodorant",
}

# our subcategory -> (dataset article types in priority order)
SUBCAT_MAP = {
    "Dress": ["Dresses"],
    "Shirt": ["Shirts", "Tshirts"],
    "Sweater": ["Sweaters"],
    "Jacket": ["Jackets", "Rain Jacket"],
    "Ski Jacket": ["Jackets", "Rain Jacket"],
    "Fleece": ["Sweatshirts", "Jackets"],
    "Base Layer": ["Innerwear Vests", "Sweatshirts"],
    "Trousers": ["Trousers", "Track Pants", "Jeans"],
    "Ski Pants": ["Track Pants", "Trousers"],
    "Shoes": ["Casual Shoes", "Sports Shoes", "Formal Shoes"],
    "Sandals": ["Sandals", "Flip Flops"],
    "Boots": ["Booties", "Casual Shoes"],
    "Snow Boots": ["Booties", "Casual Shoes"],
    "Hat": ["Caps", "Hat"],
    "Beanie": ["Caps"],
    "Bag": ["Handbags", "Clutches", "Backpacks"],
    "Watch": ["Watches"],
    "Wearable": ["Watches"],
    "Eyewear": ["Sunglasses"],
    "Goggles": ["Sunglasses"],
    "Scarf": ["Mufflers", "Scarves"],
    "Neck Gaiter": ["Mufflers", "Scarves"],
    "Gloves": ["Gloves"],
    "Socks": ["Socks"],
    "Skincare": ["Perfume and Body Mist"],
    "Makeup": ["Lipstick"],
}

# our colour name -> acceptable dataset baseColours
COLOUR_MAP = {
    "Blush Pink": ["Pink", "Beige"],
    "Emerald": ["Green"],
    "Coral": ["Orange", "Pink", "Red"],
    "Off White": ["White", "Cream", "Beige"],
    "Sky Blue": ["Blue", "White"],
    "Charcoal": ["Grey", "Black"],
    "Navy": ["Navy Blue", "Blue"],
    "Indigo": ["Blue", "Navy Blue"],
    "Black": ["Black"],
    "Beige": ["Beige", "Cream", "Khaki"],
    "Sand": ["Beige", "Cream"],
    "Brown": ["Brown"],
    "White": ["White"],
    "Forest Green": ["Green", "Olive"],
    "Gold": ["Gold", "Yellow", "Beige"],
    "Gold Frame": ["Gold", "Brown"],
    "Tan": ["Brown", "Beige"],
    "Natural Straw": ["Beige", "Cream", "Brown"],
    "Camel": ["Brown", "Beige"],
    "Silver": ["Silver", "Grey"],
    "Burgundy": ["Maroon", "Red"],
    "Cream": ["Cream", "Beige", "White"],
    "Crimson": ["Red", "Maroon"],
    "Aqua": ["Blue", "Green"],
    "Bone White": ["White", "Cream"],
    "Sage": ["Green", "Grey", "Olive"],
    "Matte Black": ["Black"],
    "Graphite": ["Grey", "Black"],
    "Deep Blue": ["Blue", "Navy Blue"],
    "Amber Lens": ["Orange", "Yellow", "Gold"],
    "Slate": ["Grey"],
    "Slate Grey": ["Grey"],
    "Rust": ["Orange", "Brown", "Maroon"],
    "Moss": ["Green", "Olive"],
}

GENDER_MAP = {"Men": {"Men"}, "Women": {"Women"}, "Unisex": {"Men", "Women", "Unisex"}}

# Products the dataset simply cannot illustrate faithfully (no sun hats, no
# beanies, no denim jackets in this catalogue, and its "Trousers" label includes
# shorts). They keep the emoji placeholder rather than show a misleading photo.
NO_PHOTO = {"p018", "p008", "p036"}

# Manual corrections where the automatic type+colour match picked the wrong
# garment. Keeps the demo honest: a "denim jacket" must not show a floral top.
OVERRIDES = {
    "p008": {"types": ["Jackets"], "colours": ["Blue", "Navy Blue"]},        # denim jacket
    "p011": {"types": ["Jeans"], "colours": ["Blue", "Navy Blue", "Black"]},  # jeans, not trousers
    "p016": {"types": ["Sandals"], "colours": ["Beige", "Brown", "Gold"]},    # flat sandals
    "p017": {"types": ["Booties", "Formal Shoes"], "colours": ["Brown", "Black"]},  # boots
    "p010": {"types": ["Trousers", "Track Pants"], "colours": ["Beige", "Khaki"]},
    "p036": {"types": ["Caps"], "colours": ["Blue", "Grey", "Black"]},       # knitted beanie
}

UA = {"User-Agent": "smartmall-fyp"}


def get_json(url, tries=3):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.load(urllib.request.urlopen(req, timeout=60))
        except Exception as e:
            if a == tries - 1:
                raise
            time.sleep(1.5 * (a + 1))


def collect_candidates(target_per_type=22, max_rows=14000, page=100):
    """Page /rows and bucket rows by articleType until each type has enough."""
    buckets = {}
    off = 0
    seen_types = set()
    while off < max_rows:
        url = (
            f"https://datasets-server.huggingface.co/rows?dataset={Q}"
            f"&config=default&split=train&offset={off}&length={page}"
        )
        try:
            d = get_json(url)
        except Exception as e:
            print(f"    page {off} failed: {str(e)[:90]}")
            break
        rows = d.get("rows", [])
        if not rows:
            break
        for r in rows:
            row = r["row"]
            t = row.get("articleType")
            seen_types.add(t)
            if t not in NEEDED:
                continue
            b = buckets.setdefault(t, [])
            if len(b) < target_per_type:
                b.append({
                    "articleType": t,
                    "baseColour": row.get("baseColour"),
                    "gender": row.get("gender"),
                    "name": row.get("productDisplayName"),
                    "src": (row.get("image") or {}).get("src"),
                })
        off += page
        ready = sum(1 for k in NEEDED if len(buckets.get(k, [])) >= target_per_type)
        if off % 2000 == 0:
            print(f"    scanned {off} rows, {ready}/{len(NEEDED)} types filled", flush=True)
        if ready >= len(NEEDED & seen_types) and len(buckets) >= len(NEEDED & seen_types) and off >= 3000:
            break
    return buckets, seen_types


def score(cand, article_types, colours, genders):
    s = 0
    if cand["articleType"] == article_types[0]:
        s += 100
    elif cand["articleType"] in article_types:
        s += 70
    else:
        return -1
    if cand["baseColour"] in colours[:1]:
        s += 40
    elif cand["baseColour"] in colours:
        s += 26
    if cand["gender"] in genders:
        s += 12
    if not cand.get("src"):
        return -1
    return s


def download(src, dest, max_side=700):
    req = urllib.request.Request(src, headers=UA)
    raw = urllib.request.urlopen(req, timeout=90).read()
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    if max(w, h) > max_side:
        sc = max_side / max(w, h)
        im = im.resize((max(1, int(w * sc)), max(1, int(h * sc))), Image.LANCZOS)
    im.save(dest, "JPEG", quality=88, optimize=True)
    return im.size, len(raw)


def main():
    only = set(sys.argv[1].split(",")) if len(sys.argv) > 1 else None
    if only:
        print(f"  re-picking only: {sorted(only)}")

    os.makedirs(OUTDIR, exist_ok=True)
    with open(PRODUCTS, encoding="utf-8") as fh:
        products = json.load(fh)

    # Clear out products that must not have a photo.
    for p in products:
        if p["id"] in NO_PHOTO and p.get("image"):
            path = os.path.join(OUTDIR, f"{p['id']}.jpg")
            if os.path.exists(path):
                os.remove(path)
            p.pop("image", None)
            p.pop("imageCredit", None)
            print(f"    cleared photo for {p['id']} (no faithful match available)")

    print("  scanning dataset via datasets-server ...")
    buckets, seen_types = collect_candidates()
    print(f"    collected {sum(len(v) for v in buckets.values())} candidates across {len(buckets)} types")
    missing = sorted(NEEDED - set(buckets))
    if missing:
        print(f"    types with no candidates: {missing}")

    # Reuse existing assignments so a targeted re-run does not re-download
    # everything; products already carrying a photo are locked in.
    used_src = set()
    matched, skipped = [], []

    for p in products:
        pid = p["id"]
        if pid in NO_PHOTO:
            skipped.append((pid, p["name"], "excluded (no faithful photo in dataset)"))
            continue
        if pid not in (only or set()) and p.get("image"):
            matched.append((pid, p["name"], "kept existing"))
            continue

        ov = OVERRIDES.get(pid, {})
        sub = p.get("subcategory")
        types = ov.get("types") or SUBCAT_MAP.get(sub)
        if not types:
            skipped.append((pid, p["name"], f"no mapping for subcategory '{sub}'"))
            continue
        colours = ov.get("colours") or COLOUR_MAP.get(p.get("colorName"), [])
        genders = GENDER_MAP.get(p.get("gender"), {"Men", "Women", "Unisex"})

        pool = []
        for t in types:
            pool.extend(buckets.get(t, []))
        ranked = sorted(
            ((score(c, types, colours, genders), c) for c in pool),
            key=lambda x: -x[0],
        )
        pick = next((c for s, c in ranked if s > 0 and c["src"] not in used_src), None)
        if not pick:
            skipped.append((pid, p["name"], f"no candidate for {types}"))
            continue

        used_src.add(pick["src"])
        dest = os.path.join(OUTDIR, f"{pid}.jpg")
        try:
            size, raw_len = download(pick["src"], dest)
        except Exception as e:
            skipped.append((pid, p["name"], f"download failed: {str(e)[:60]}"))
            continue

        p["image"] = f"/assets/products/{pid}.jpg"
        p["imageCredit"] = f"{pick['articleType']} / {pick['baseColour']}"
        matched.append((pid, p["name"], f"{pick['articleType']}/{pick['baseColour']} {size[0]}x{size[1]} {raw_len//1024}KB"))

    with open(PRODUCTS, "w", encoding="utf-8") as fh:
        json.dump(products, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"\n  matched {len(matched)} products:")
    for pid, name, info in matched:
        print(f"    {pid}  {name[:32]:34s} {info}")
    if skipped:
        print(f"\n  skipped {len(skipped)} (keep emoji placeholder):")
        for pid, name, why in skipped:
            print(f"    {pid}  {name[:32]:34s} {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
