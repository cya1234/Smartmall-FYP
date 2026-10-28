"""Build the retrieval evaluation set.

Every entry pairs a Traditional-Chinese query with its English translation and
the product(s) it should return, so we can report Recall@K per language. That
matters because Marqo's fashion models are trained on English catalogue
metadata, and the site is Chinese-first -- the gap is itself a finding.

Only products that actually have a photo can be retrieved, so entries pointing at
emoji-only products are dropped.

Run:  .venv\\Scripts\\python.exe tools/build_eval_set.py
"""
import json
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PRODUCTS = os.path.join(ROOT, "data", "products.json")
OUT_DIR = os.path.join(ROOT, "data", "eval")
OUT = os.path.join(OUT_DIR, "queries.json")

# (zh query, en query, targets, type, difficulty)
PAIRS = [
    # ---- single-attribute, distinctive ----
    ("亞麻連身裙", "linen dress", ["p001"], "attribute", "easy"),
    ("絲質連身裙", "silk slip dress", ["p002"], "attribute", "easy"),
    ("熱帶印花長洋裝", "tropical print maxi dress", ["p003"], "attribute", "easy"),
    ("亞麻襯衫", "linen shirt", ["p004"], "attribute", "easy"),
    ("牛津襯衫", "oxford shirt", ["p005"], "attribute", "easy"),
    ("喀什米爾毛衣", "cashmere sweater", ["p006"], "attribute", "easy"),
    ("羽絨外套", "down puffer jacket", ["p007"], "attribute", "easy"),
    ("羊毛西裝外套", "wool blazer", ["p009"], "attribute", "easy"),
    ("卡其長褲", "khaki chinos", ["p010"], "attribute", "easy"),
    ("修身牛仔褲", "slim fit jeans", ["p011"], "attribute", "easy"),
    ("亞麻寬褲", "wide leg linen trousers", ["p012"], "attribute", "easy"),
    ("真皮樂福鞋", "leather loafers", ["p013"], "attribute", "easy"),
    ("白色波鞋", "white sneakers", ["p014"], "attribute", "easy"),
    ("越野跑鞋", "trail running shoes", ["p015"], "attribute", "easy"),
    ("綁帶涼鞋", "strappy heeled sandals", ["p016"], "attribute", "easy"),
    ("切爾西短靴", "chelsea boots", ["p017"], "attribute", "easy"),
    ("真皮托特包", "leather tote bag", ["p019"], "attribute", "easy"),
    ("緞面手拿包", "satin evening clutch", ["p020"], "attribute", "easy"),
    ("指針腕錶", "analogue wristwatch", ["p021"], "attribute", "easy"),
    ("飛行員太陽眼鏡", "aviator sunglasses", ["p022"], "attribute", "easy"),
    ("印花絲巾", "printed silk scarf", ["p023"], "attribute", "easy"),

    # ---- beauty / home / electronics ----
    ("防曬乳 SPF50", "SPF50 sunscreen", ["p024"], "attribute", "easy"),
    ("霧面唇膏", "matte lipstick set", ["p025"], "attribute", "easy"),
    ("保濕精華液", "hydrating face serum", ["p026"], "attribute", "easy"),
    ("智慧運動手錶", "smart sports watch", ["p030"], "attribute", "easy"),

    # ---- winter / snow ----
    ("滑雪外套", "ski jacket", ["p031"], "attribute", "easy"),
    ("防水雪褲", "waterproof ski pants", ["p032"], "attribute", "easy"),
    ("滑雪護目鏡", "ski goggles", ["p033"], "attribute", "easy"),
    ("滑雪手套", "ski gloves", ["p034"], "attribute", "easy"),
    ("排汗保暖內層衣", "thermal base layer top", ["p035"], "attribute", "easy"),
    ("美麗諾滑雪襪", "merino wool ski socks", ["p037"], "attribute", "easy"),
    ("保暖頸圍", "fleece neck gaiter", ["p038"], "attribute", "easy"),
    ("刷毛中層衣", "fleece midlayer jacket", ["p039"], "attribute", "easy"),
    ("防水雪靴", "waterproof snow boots", ["p040"], "attribute", "easy"),

    # ---- colour-only (harder: colour must beat category) ----
    ("黑色西裝外套", "black tailored jacket", ["p009"], "colour", "medium"),
    ("藍色滑雪外套", "blue ski jacket", ["p031"], "colour", "medium"),
    ("白色皮鞋", "white leather shoes", ["p014"], "colour", "medium"),
    ("金色涼鞋", "gold sandals", ["p016"], "colour", "medium"),

    # ---- composition / material ----
    ("羊毛材質的禦寒單品", "wool winter warm piece", ["p006", "p009", "p037"], "material", "hard"),
    ("防水材質的滑雪裝備", "waterproof snow gear", ["p031", "p032", "p034"], "material", "hard"),
    ("絲質的正式配件", "silk formal accessory", ["p023"], "material", "medium"),

    # ---- occasion / intent (the real semantic gap) ----
    ("去海島婚禮穿什麼", "what to wear to a beach wedding", ["p001", "p002", "p003"], "occasion", "hard"),
    ("滑雪要帶什麼", "what to bring on a ski trip", ["p031", "p032", "p033", "p034"], "occasion", "hard"),
    ("上班面試造型", "job interview outfit", ["p004", "p005", "p009", "p010"], "occasion", "hard"),
    ("夏天去海邊", "summer day at the beach", ["p003", "p016"], "occasion", "hard"),
    ("冬天保暖配件", "winter warm accessories", ["p037", "p038"], "occasion", "hard"),
    ("情人節禮物", "valentines day gift", ["p020", "p023", "p025"], "occasion", "hard"),
]


def main():
    with open(PRODUCTS, encoding="utf-8") as fh:
        products = json.load(fh)
    have_image = {p["id"] for p in products if p.get("image")}
    by_id = {p["id"]: p for p in products}

    queries, dropped = [], []
    n = 0
    for zh, en, targets, qtype, diff in PAIRS:
        usable = [t for t in targets if t in have_image]
        if not usable:
            dropped.append((zh, targets))
            continue
        for lang, text in (("zh", zh), ("en", en)):
            n += 1
            queries.append({
                "id": f"q{n:03d}",
                "lang": lang,
                "query": text,
                "targets": usable,
                "type": qtype,
                "difficulty": diff,
                "pairId": f"p{(n + 1) // 2:03d}",
            })

    doc = {
        "version": 1,
        "catalogueSize": len(products),
        "retrievable": len(have_image),
        "note": (
            "Only products with a real photo can be retrieved; emoji-only entries are "
            "excluded from the ground truth so the metric is not penalised for a missing asset."
        ),
        "counts": {
            "queries": len(queries),
            "pairs": len({q["pairId"] for q in queries}),
            "byLanguage": {
                lang: sum(1 for q in queries if q["lang"] == lang) for lang in ("zh", "en")
            },
            "byType": {},
            "byDifficulty": {},
        },
        "queries": queries,
    }
    for q in queries:
        doc["counts"]["byType"][q["type"]] = doc["counts"]["byType"].get(q["type"], 0) + 1
        doc["counts"]["byDifficulty"][q["difficulty"]] = \
            doc["counts"]["byDifficulty"].get(q["difficulty"], 0) + 1

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)

    print(f"  retrievable products : {len(have_image)} / {len(products)}")
    print(f"  query pairs          : {doc['counts']['pairs']}")
    print(f"  queries total        : {len(queries)}  (zh {doc['counts']['byLanguage']['zh']}, "
          f"en {doc['counts']['byLanguage']['en']})")
    print(f"  by type              : {doc['counts']['byType']}")
    print(f"  by difficulty        : {doc['counts']['byDifficulty']}")
    if dropped:
        print(f"  dropped (no image)   : {[(z, t) for z, t in dropped]}")
    print(f"  wrote {OUT}")


if __name__ == "__main__":
    main()
