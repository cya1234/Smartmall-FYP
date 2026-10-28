#!/usr/bin/env python3
"""Augment the SmartMall catalog.

Adds, for every product:
  - name_zh / description_zh   (Traditional Chinese UI)
  - slots[]                    (functional slot used by the scenario bundler)
  - fit {runs, stretch}        (used by the return-reason predictor)
  - returnRate                 (base return rate %, e-commerce benchmark)

and appends the winter / snow-sports range required by the
"Hokkaido ski trip, budget HK$2,000" blind-box scenario.

Idempotent: re-running replaces previously injected fields.
Run:  python tools/augment_catalog.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTS = os.path.join(ROOT, "data", "products.json")

# id -> (name_zh, description_zh, slots, runs, stretch, returnRate)
EXTRA = {
    "p001": ("亞麻綁帶連身裙", "透氣的亞麻綁帶連身裙，腰間綁帶修飾身形，適合炎熱氣候的戶外婚禮與花園派對。", ["dress"], "true", "low", 14),
    "p002": ("絲質吊帶連身裙", "垂墜感極佳的絲質吊帶裙，適合晚宴與約會場合的經典之選。", ["dress"], "small", "low", 18),
    "p003": ("熱帶印花長洋裝", "鮮豔熱帶印花的飄逸長洋裝，為度假晚宴與戶外慶典而生。", ["dress"], "large", "low", 16),
    "p004": ("亞麻寬鬆襯衫", "寬鬆剪裁的亞麻襯衫，在潮濕悶熱的天氣依然清爽透氣，是暖帶氣候的衣櫥必備。", ["top"], "large", "none", 15),
    "p005": ("牛津紡襯衫", "挺立的牛津紡布料，從辦公室到下班小酌都輕鬆駕馭。", ["top"], "true", "none", 11),
    "p006": ("喀什米爾圓領毛衣", "極致柔軟的喀什米爾圓領毛衣，寒冷天氣的奢華保暖層。", ["midlayer", "top"], "small", "low", 19),
    "p007": ("輕量羽絨外套", "可收納的羽絨外套配防潑水外層，為冬季通勤與登山行程而生。", ["outerwear"], "true", "none", 12),
    "p008": ("復古牛仔外套", "經典水洗牛仔外套，幾乎可搭配任何造型，越穿越有味道。", ["outerwear", "midlayer"], "true", "none", 13),
    "p009": ("羊毛剪裁西裝外套", "俐落剪裁的羊毛西裝外套，面試與會議場合的瞬間專業感。", ["outerwear", "top"], "small", "none", 21),
    "p010": ("彈性卡其長褲", "舒適彈性卡其褲配修身錐形剪裁，介於休閒與正式之間的可靠選擇。", ["bottom"], "true", "high", 10),
    "p011": ("修身牛仔褲", "深靛藍水洗的修身彈性牛仔褲，百搭的日常基礎款。", ["bottom"], "true", "high", 17),
    "p012": ("亞麻寬褲", "飄逸的亞麻寬褲，在熱帶高溫中保持涼爽與俐落。", ["bottom"], "large", "none", 20),
    "p013": ("真皮樂福鞋", "手工收邊的真皮樂福鞋配緩震鞋墊，長時間行走也舒適。", ["footwear"], "true", "none", 15),
    "p014": ("經典白皮球鞋", "簡約白色真皮球鞋，怎麼搭都好看，日常首選。", ["footwear"], "true", "none", 9),
    "p015": ("越野跑鞋", "抓地透氣的越野跑鞋配緩震中底，山徑與跑步機都適用。", ["footwear"], "small", "low", 11),
    "p016": ("綁帶粗跟涼鞋", "金色綁帶配好走的粗跟，派對造型不必犧牲舒適。", ["footwear"], "true", "low", 12),
    "p017": ("切爾西短靴", "俐落的真皮切爾西短靴配側邊鬆緊帶，冷天造型輕鬆搞定。", ["footwear"], "true", "none", 14),
    "p018": ("寬簷草帽", "寬簷草帽提供絕佳遮陽效果，一秒切換度假氛圍。", ["headwear", "accessory"], "true", "none", 8),
    "p019": ("立體真皮托特包", "附筆電夾層的立體真皮托特包，通勤與商務都俐落有型。", ["bag"], "true", "none", 10),
    "p020": ("緞面晚宴手拿包", "閃耀的緞面手拿包，恰好裝下必需品，為晚間造型畫龍點睛。", ["bag"], "true", "none", 12),
    "p021": ("經典指針腕錶", "藍寶石鏡面的簡約不鏽鋼腕錶，低調奢華的日常配件。", ["accessory"], "true", "none", 7),
    "p022": ("飛行員太陽眼鏡", "偏光 UV400 飛行員太陽眼鏡，經典框型適合豔陽天。", ["eyewear", "accessory"], "true", "none", 9),
    "p023": ("印花絲巾", "手捲邊的印花絲巾，一條就能提升整體造型質感。", ["neckwear", "accessory"], "true", "none", 11),
    "p024": ("廣譜 SPF50 防曬乳", "輕盈、海洋友善的 SPF50 防曬乳，擦上後幾乎隱形，豔陽氣候的日常防護。", ["beauty"], "true", "none", 6),
    "p025": ("絲絨霧面唇膏三件組", "三支長效絲絨霧面唇膏，從日間裸色到晚間緋紅一次擁有。", ["beauty"], "true", "none", 8),
    "p026": ("保濕精華液", "玻尿酸精華液為肌膚大量補水，打造健康光澤的每日一步。", ["beauty"], "true", "none", 5),
    "p027": ("陶瓷香氛擴香機", "霧面陶瓷外殼的超音波擴香機，為任何空間帶來柔光與香氣。", ["home"], "true", "none", 7),
    "p028": ("石陶餐具組", "16 件式灰綠釉石陶餐具組，讓宴客也成為一種美感。", ["home"], "true", "none", 9),
    "p029": ("真無線藍牙耳機", "抗汗真無線耳機，主動降噪並提供 30 小時續航。", ["gear"], "true", "none", 6),
    "p030": ("智慧運動手錶", "GPS 運動手錶，支援心率追蹤、睡眠分析與 10 天續航。", ["gear", "accessory"], "true", "none", 8),
}

# --- Winter / snow-sports range (appended) -----------------------------------
NEW = [
    {
        "id": "p031", "name": "Alpine Shell Ski Jacket", "name_zh": "高山防水滑雪外套",
        "brand": "Northward", "category": "Winter & Snow", "subcategory": "Ski Jacket",
        "price": 118.0, "currency": "USD", "color": "#1f4e79", "colorName": "Deep Blue",
        "material": "Waterproof Shell", "style": ["Sporty", "Functional"],
        "occasion": ["Ski", "Outdoor", "Travel"], "season": ["Winter"], "climate": ["Freezing", "Cold"],
        "gender": "Unisex", "emoji": "🎿", "rating": 4.7, "reviews": 96,
        "description": "A 20K waterproof, windproof shell with taped seams and a helmet-compatible hood — built for powder days.",
        "description_zh": "20K 防水防風外殼配壓膠接縫與可戴頭盔的連帽設計，專為粉雪日打造。",
        "tags": ["ski", "snowboard", "jacket", "waterproof", "winter", "cold", "hokkaido", "shell", "unisex"],
        "slots": ["outerwear"], "fit": {"runs": "true", "stretch": "none"}, "returnRate": 9,
    },
    {
        "id": "p032", "name": "Insulated Snow Pants", "name_zh": "保暖防水雪褲",
        "brand": "Northward", "category": "Winter & Snow", "subcategory": "Ski Pants",
        "price": 76.0, "currency": "USD", "color": "#2b2f3a", "colorName": "Graphite",
        "material": "Waterproof Shell / Fleece", "style": ["Sporty", "Functional"],
        "occasion": ["Ski", "Outdoor"], "season": ["Winter"], "climate": ["Freezing", "Cold"],
        "gender": "Unisex", "emoji": "🏂", "rating": 4.6, "reviews": 74,
        "description": "Fully seam-sealed snow pants with light insulation, reinforced cuffs and boot gaiters.",
        "description_zh": "全壓膠防水雪褲配輕量保暖層、耐磨褲腳與雪裙設計。",
        "tags": ["ski", "snowboard", "pants", "waterproof", "winter", "cold", "hokkaido", "unisex"],
        "slots": ["bottom"], "fit": {"runs": "large", "stretch": "low"}, "returnRate": 13,
    },
    {
        "id": "p033", "name": "Anti-Fog Ski Goggles", "name_zh": "防霧滑雪護目鏡",
        "brand": "Alpine Co", "category": "Winter & Snow", "subcategory": "Goggles",
        "price": 42.0, "currency": "USD", "color": "#e8a33d", "colorName": "Amber Lens",
        "material": "Polycarbonate", "style": ["Sporty", "Functional"],
        "occasion": ["Ski", "Outdoor"], "season": ["Winter"], "climate": ["Freezing", "Cold"],
        "gender": "Unisex", "emoji": "🥽", "rating": 4.5, "reviews": 61,
        "description": "Dual-layer anti-fog lenses with 100% UV protection and OTG fit over prescription glasses.",
        "description_zh": "雙層防霧鏡片、100% 抗 UV，可佩戴於近視眼鏡外（OTG）。",
        "tags": ["goggles", "ski", "snow", "anti-fog", "uv", "winter", "hokkaido", "unisex"],
        "slots": ["eyewear"], "fit": {"runs": "true", "stretch": "none"}, "returnRate": 7,
    },
    {
        "id": "p034", "name": "Waterproof Ski Gloves", "name_zh": "防水滑雪手套",
        "brand": "Alpine Co", "category": "Winter & Snow", "subcategory": "Gloves",
        "price": 24.0, "currency": "USD", "color": "#141821", "colorName": "Black",
        "material": "Waterproof Shell / Thinsulate", "style": ["Sporty", "Functional"],
        "occasion": ["Ski", "Outdoor"], "season": ["Winter"], "climate": ["Freezing", "Cold"],
        "gender": "Unisex", "emoji": "🧤", "rating": 4.4, "reviews": 88,
        "description": "Waterproof breathable ski gloves with Thinsulate insulation and touchscreen fingertips.",
        "description_zh": "防水透氣滑雪手套，內置 Thinsulate 保暖層，指尖支援觸控螢幕。",
        "tags": ["gloves", "ski", "waterproof", "winter", "cold", "hokkaido", "unisex"],
        "slots": ["gloves"], "fit": {"runs": "small", "stretch": "low"}, "returnRate": 8,
    },
    {
        "id": "p035", "name": "Thermal Base Layer Set", "name_zh": "排汗保暖內層衣",
        "brand": "Stride", "category": "Winter & Snow", "subcategory": "Base Layer",
        "price": 34.0, "currency": "USD", "color": "#6b7280", "colorName": "Slate",
        "material": "Merino Blend", "style": ["Functional", "Minimal"],
        "occasion": ["Ski", "Outdoor", "Hiking"], "season": ["Winter"], "climate": ["Freezing", "Cold"],
        "gender": "Unisex", "emoji": "🧥", "rating": 4.6, "reviews": 112,
        "description": "Merino-blend thermal top and bottom that wick moisture and stay warm even when damp.",
        "description_zh": "美麗諾混紡保暖內層上衣與長褲，排汗快乾、潮濕時仍能保暖。",
        "tags": ["base layer", "thermal", "merino", "ski", "winter", "cold", "hokkaido", "unisex"],
        "slots": ["baselayer"], "fit": {"runs": "small", "stretch": "high"}, "returnRate": 6,
    },
    {
        "id": "p036", "name": "Merino Knit Beanie", "name_zh": "美麗諾羊毛毛帽",
        "brand": "Meridian", "category": "Winter & Snow", "subcategory": "Beanie",
        "price": 13.0, "currency": "USD", "color": "#8c4a3f", "colorName": "Rust",
        "material": "Merino Wool", "style": ["Cozy", "Minimal"],
        "occasion": ["Ski", "Outdoor", "Casual"], "season": ["Winter"], "climate": ["Freezing", "Cold"],
        "gender": "Unisex", "emoji": "🧢", "rating": 4.7, "reviews": 143,
        "description": "A soft merino beanie with a double-layer band that covers the ears on chairlift rides.",
        "description_zh": "柔軟美麗諾羊毛毛帽，雙層帽緣完整包覆耳朵，纜車上也暖呼呼。",
        "tags": ["beanie", "hat", "merino", "winter", "cold", "ski", "hokkaido", "unisex"],
        "slots": ["headwear"], "fit": {"runs": "true", "stretch": "high"}, "returnRate": 5,
    },
    {
        "id": "p037", "name": "Merino Ski Socks", "name_zh": "美麗諾滑雪襪",
        "brand": "Stride", "category": "Winter & Snow", "subcategory": "Socks",
        "price": 10.0, "currency": "USD", "color": "#4b5563", "colorName": "Charcoal",
        "material": "Merino Wool", "style": ["Functional"],
        "occasion": ["Ski", "Outdoor", "Hiking"], "season": ["Winter"], "climate": ["Freezing", "Cold"],
        "gender": "Unisex", "emoji": "🧦", "rating": 4.5, "reviews": 97,
        "description": "Cushioned merino ski socks with targeted padding at the shin and heel.",
        "description_zh": "加厚緩震美麗諾滑雪襪，小腿與腳跟加強防護。",
        "tags": ["socks", "ski", "merino", "winter", "cold", "hokkaido", "unisex"],
        "slots": ["socks"], "fit": {"runs": "true", "stretch": "high"}, "returnRate": 4,
    },
    {
        "id": "p038", "name": "Winter Neck Gaiter", "name_zh": "保暖頸圍",
        "brand": "Alpine Co", "category": "Winter & Snow", "subcategory": "Neck Gaiter",
        "price": 12.0, "currency": "USD", "color": "#374151", "colorName": "Slate Grey",
        "material": "Fleece", "style": ["Functional"],
        "occasion": ["Ski", "Outdoor"], "season": ["Winter"], "climate": ["Freezing", "Cold"],
        "gender": "Unisex", "emoji": "🧣", "rating": 4.4, "reviews": 55,
        "description": "A fleece-lined neck gaiter that seals out wind and spindrift.",
        "description_zh": "刷毛內裡保暖頸圍，有效阻擋寒風與雪粉。",
        "tags": ["gaiter", "neck", "fleece", "winter", "cold", "ski", "hokkaido", "unisex"],
        "slots": ["neckwear"], "fit": {"runs": "true", "stretch": "high"}, "returnRate": 5,
    },
    {
        "id": "p039", "name": "Fleece Midlayer Pullover", "name_zh": "刷毛保暖中層衣",
        "brand": "Northward", "category": "Winter & Snow", "subcategory": "Fleece",
        "price": 48.0, "currency": "USD", "color": "#5b6b52", "colorName": "Moss",
        "material": "Recycled Fleece", "style": ["Cozy", "Functional"],
        "occasion": ["Ski", "Outdoor", "Casual"], "season": ["Winter", "Autumn"], "climate": ["Freezing", "Cold", "Cool"],
        "gender": "Unisex", "emoji": "🧶", "rating": 4.6, "reviews": 78,
        "description": "A grid-fleece midlayer that breathes on the climb and insulates on the descent.",
        "description_zh": "格紋刷毛中層衣，上坡透氣、下坡保暖，滑雪穿搭的關鍵一層。",
        "tags": ["fleece", "midlayer", "ski", "winter", "cold", "hokkaido", "unisex"],
        "slots": ["midlayer"], "fit": {"runs": "true", "stretch": "low"}, "returnRate": 8,
    },
    {
        "id": "p040", "name": "Waterproof Snow Boots", "name_zh": "防水雪靴",
        "brand": "Stride", "category": "Winter & Snow", "subcategory": "Snow Boots",
        "price": 92.0, "currency": "USD", "color": "#3f3a33", "colorName": "Brown",
        "material": "Leather / Rubber", "style": ["Functional", "Classic"],
        "occasion": ["Ski", "Outdoor", "Travel"], "season": ["Winter"], "climate": ["Freezing", "Cold"],
        "gender": "Unisex", "emoji": "🥾", "rating": 4.6, "reviews": 84,
        "description": "Insulated waterproof snow boots with a high-traction lug sole for icy streets.",
        "description_zh": "防水保暖雪靴配高抓地力鞋底，結冰路面也走得穩。",
        "tags": ["boots", "snow", "waterproof", "winter", "cold", "hokkaido", "unisex"],
        "slots": ["footwear"], "fit": {"runs": "small", "stretch": "none"}, "returnRate": 14,
    },
]


def main():
    with open(PRODUCTS, encoding="utf-8") as fh:
        products = json.load(fh)

    # Drop any previously appended snow range so the script is idempotent.
    products = [p for p in products if p["id"] not in {n["id"] for n in NEW}]

    for p in products:
        extra = EXTRA.get(p["id"])
        if not extra:
            print(f"  ! no extras for {p['id']}")
            continue
        name_zh, desc_zh, slots, runs, stretch, rr = extra
        p["name_zh"] = name_zh
        p["description_zh"] = desc_zh
        p["slots"] = slots
        p["fit"] = {"runs": runs, "stretch": stretch}
        p["returnRate"] = rr

    products.extend(NEW)

    with open(PRODUCTS, "w", encoding="utf-8") as fh:
        json.dump(products, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    zh = sum(1 for p in products if p.get("name_zh"))
    print(f"catalog: {len(products)} products ({zh} with zh names)")


if __name__ == "__main__":
    main()
