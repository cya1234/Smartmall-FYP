"""Add the digital-product and computer-accessory range, with drawn illustrations.

The catalogue had two electronics items, which made the category look like an
afterthought and made "search for earbuds" return one result. This adds twelve more and
draws their images, because there is no internet access here to fetch photographs and a
flat illustration is honest about being an illustration.

Style matches the rest of the catalogue: 525x700, white background, soft shadow.
Rendered at 4x and downsampled so edges are anti-aliased.

Idempotent: products are keyed by id, so re-running updates them instead of duplicating.

    python tools/add_tech_products.py            # add data + draw images
    python tools/add_tech_products.py --data-only
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT_DIR = os.path.join(ROOT, "public", "assets", "products")
PRODUCTS = os.path.join(ROOT, "data", "products.json")

W, H = 525, 700
SS = 4
BG = (255, 255, 255)

INK = (31, 35, 40)
INK_2 = (58, 64, 72)
SILVER = (201, 206, 214)
SILVER_2 = (178, 184, 194)
NAVY = (43, 58, 85)
WHITE = (247, 248, 250)
WHITE_EDGE = (214, 218, 225)

# --------------------------------------------------------------------- products
ITEMS = [
    {
        "id": "p041", "name": "Over-Ear Headphones ANC", "name_zh": "主動降噪頭戴耳機",
        "brand": "Aurel", "subcategory": "Audio", "price": 149, "color": "#1F2328",
        "colorName": "Black", "material": "Recycled plastic, memory foam",
        "style": "Minimal", "emoji": "🎧", "rating": 4.7, "reviews": 412, "returnRate": 7,
        "description": "Over-ear headphones with adaptive noise cancelling, 40-hour battery and memory-foam cups.",
        "description_zh": "頭戴式主動降噪耳機，40 小時續航，記憶棉耳墊。",
        "tags": ["headphones", "耳機", "降噪", "耳筒", "audio", "tech", "anc", "wireless"],
        "slots": ["gear"], "draw": "headphones", "credit": "Headphones / Black",
    },
    {
        "id": "p042", "name": "Noise-Cancelling Earbuds", "name_zh": "入耳式降噪耳機",
        "brand": "Aurel", "subcategory": "Audio", "price": 89, "color": "#3A4048",
        "colorName": "Graphite", "material": "ABS, silicone",
        "style": "Minimal", "emoji": "🎵", "rating": 4.5, "reviews": 986, "returnRate": 9,
        "description": "Compact earbuds with a charging case, transparency mode and 28-hour total playback.",
        "description_zh": "小巧入耳式耳機，附充電盒，支援通透模式，總續航 28 小時。",
        "tags": ["earbuds", "耳機", "藍牙", "audio", "tech", "wireless", "in-ear"],
        "slots": ["gear"], "draw": "earbuds", "credit": "Audio / Graphite",
    },
    {
        "id": "p043", "name": "Portable Bluetooth Speaker", "name_zh": "便攜藍牙音響",
        "brand": "Aurel", "subcategory": "Speaker", "price": 69, "color": "#2B3A55",
        "colorName": "Navy", "material": "Fabric mesh, rubber",
        "style": "Sporty", "emoji": "🔊", "rating": 4.4, "reviews": 233, "returnRate": 8,
        "description": "Palm-sized speaker with IPX7 waterproofing and 18 hours of playback.",
        "description_zh": "掌上型藍牙音響，IPX7 防水，18 小時播放。",
        "tags": ["speaker", "音響", "喇叭", "bluetooth", "audio", "tech", "outdoor"],
        "slots": ["gear"], "draw": "speaker", "credit": "Audio / Navy",
    },
    {
        "id": "p044", "name": "Smartwatch Sport", "name_zh": "運動智慧手錶",
        "brand": "Aurel", "subcategory": "Wearable", "price": 199, "color": "#1F2328",
        "colorName": "Black", "material": "Aluminium, fluoroelastomer",
        "style": "Sporty", "emoji": "⌚", "rating": 4.6, "reviews": 521, "returnRate": 8,
        "description": "GPS sports watch with heart-rate zones, 40+ workout modes and a 12-day battery.",
        "description_zh": "GPS 運動手錶，支援心率區間、40+ 運動模式，12 天續航。",
        "tags": ["smartwatch", "手錶", "手環", "gps", "fitness", "tech", "wearable", "sporty"],
        "slots": ["gear", "accessory"], "draw": "watch", "credit": "Watches / Black",
    },
    {
        "id": "p045", "name": "Power Bank 20000mAh", "name_zh": "20000mAh 行動電源",
        "brand": "Voltcraft", "subcategory": "Power", "price": 39, "color": "#F1F2F4",
        "colorName": "White", "material": "Polycarbonate",
        "style": "Minimal", "emoji": "🔋", "rating": 4.5, "reviews": 1744, "returnRate": 6,
        "description": "20000mAh with 65W USB-C output — enough for a laptop and two phones.",
        "description_zh": "20000mAh，65W USB-C 輸出，可同時為筆電與兩部手機充電。",
        "tags": ["power bank", "行動電源", "充電", "usb-c", "tech", "travel", "charger"],
        "slots": [], "draw": "powerbank", "credit": "Accessories / White",
    },
    {
        "id": "p046", "name": "Mechanical Keyboard TKL", "name_zh": "87 鍵機械鍵盤",
        "brand": "Voltcraft", "subcategory": "Computer", "price": 99, "color": "#3A4048",
        "colorName": "Graphite", "material": "Aluminium, PBT",
        "style": "Minimal", "emoji": "⌨️", "rating": 4.7, "reviews": 806, "returnRate": 7,
        "description": "Tenkeyless mechanical keyboard, hot-swappable switches and bluetooth for three devices.",
        "description_zh": "87 鍵機械鍵盤，熱插拔軸，藍牙可連接三部裝置。",
        "tags": ["keyboard", "鍵盤", "機械鍵盤", "computer", "tech", "desk", "wireless"],
        "slots": [], "draw": "keyboard", "credit": "Computer / Graphite",
    },
    {
        "id": "p047", "name": "Wireless Mouse", "name_zh": "無線滑鼠",
        "brand": "Voltcraft", "subcategory": "Computer", "price": 45, "color": "#F1F2F4",
        "colorName": "White", "material": "ABS",
        "style": "Minimal", "emoji": "🖱️", "rating": 4.4, "reviews": 1320, "returnRate": 9,
        "description": "Silent-click wireless mouse with a 4000 DPI sensor and 18-month battery life.",
        "description_zh": "靜音無線滑鼠，4000 DPI 感應器，電池可用 18 個月。",
        "tags": ["mouse", "滑鼠", "computer", "tech", "desk", "wireless", "silent"],
        "slots": [], "draw": "mouse", "credit": "Computer / White",
    },
    {
        "id": "p048", "name": "USB-C 7-in-1 Hub", "name_zh": "USB-C 七合一擴充器",
        "brand": "Voltcraft", "subcategory": "Computer", "price": 55, "color": "#9AA1AC",
        "colorName": "Space Grey", "material": "Aluminium",
        "style": "Minimal", "emoji": "🔌", "rating": 4.6, "reviews": 642, "returnRate": 8,
        "description": "HDMI 4K, two USB-A, SD, microSD, USB-C PD and ethernet in one aluminium bar.",
        "description_zh": "HDMI 4K、兩個 USB-A、SD、microSD、USB-C PD 與網絡孔，一條鋁製擴充器。",
        "tags": ["hub", "擴充器", "usb-c", "hdmi", "computer", "tech", "adapter"],
        "slots": [], "draw": "hub", "credit": "Computer / Grey",
    },
    {
        "id": "p049", "name": "Aluminium Laptop Stand", "name_zh": "鋁合金筆電支架",
        "brand": "Voltcraft", "subcategory": "Computer", "price": 35, "color": "#C9CED6",
        "colorName": "Silver", "material": "Aluminium",
        "style": "Minimal", "emoji": "💻", "rating": 4.3, "reviews": 388, "returnRate": 10,
        "description": "Foldable stand that lifts a laptop to eye level and folds flat for a bag.",
        "description_zh": "可摺疊支架，把筆電抬到視線高度，收起來可放進背包。",
        "tags": ["stand", "支架", "筆電", "laptop", "computer", "tech", "desk"],
        "slots": [], "draw": "stand", "credit": "Computer / Silver",
    },
    {
        "id": "p050", "name": "1080p Streaming Webcam", "name_zh": "1080p 直播攝影機",
        "brand": "Voltcraft", "subcategory": "Computer", "price": 59, "color": "#1F2328",
        "colorName": "Black", "material": "ABS",
        "style": "Minimal", "emoji": "📷", "rating": 4.2, "reviews": 274, "returnRate": 11,
        "description": "1080p60 webcam with dual microphones, auto light correction and a privacy shutter.",
        "description_zh": "1080p60 攝影機，雙麥克風、自動補光，附隱私遮蓋。",
        "tags": ["webcam", "攝影機", "鏡頭", "streaming", "computer", "tech", "meeting"],
        "slots": [], "draw": "webcam", "credit": "Computer / Black",
    },
    {
        "id": "p051", "name": "Portable SSD 1TB", "name_zh": "1TB 便攜固態硬碟",
        "brand": "Voltcraft", "subcategory": "Computer", "price": 119, "color": "#2B3A55",
        "colorName": "Navy", "material": "Aluminium",
        "style": "Minimal", "emoji": "💾", "rating": 4.8, "reviews": 953, "returnRate": 5,
        "description": "1TB USB-C SSD, 1050 MB/s, shock resistant and small enough for a pocket.",
        "description_zh": "1TB USB-C 固態硬碟，1050 MB/s，防震，可放入口袋。",
        "tags": ["ssd", "硬碟", "儲存", "usb-c", "computer", "tech", "portable"],
        "slots": [], "draw": "ssd", "credit": "Computer / Navy",
    },
    {
        "id": "p052", "name": '27" 4K Monitor', "name_zh": "27 吋 4K 顯示器",
        "brand": "Voltcraft", "subcategory": "Computer", "price": 299, "color": "#1F2328",
        "colorName": "Black", "material": "Aluminium, glass",
        "style": "Minimal", "emoji": "🖥️", "rating": 4.6, "reviews": 431, "returnRate": 6,
        "description": "27-inch 4K IPS panel with 99% sRGB and a single-cable USB-C connection.",
        "description_zh": "27 吋 4K IPS 面板，99% sRGB，USB-C 單線連接。",
        "tags": ["monitor", "螢幕", "顯示器", "4k", "computer", "tech", "display"],
        "slots": [], "draw": "monitor", "credit": "Computer / Black",
    },
]


# ---------------------------------------------------------------------- drawing
def canvas():
    img = Image.new("RGB", (W * SS, H * SS), BG)
    return img, ImageDraw.Draw(img)


def S(*vals):
    return [v * SS for v in vals]


def finish(img, name):
    out = img.resize((W, H), Image.LANCZOS)
    path = os.path.join(OUT_DIR, name)
    out.save(path, "PNG", optimize=True)
    return path


def shadow(img, box, alpha=40):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse(S(*box), fill=(20, 24, 32, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(10 * SS))
    img.paste(Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"), (0, 0))


def rr(d, box, r, fill, outline=None, width=0):
    d.rounded_rectangle(S(*box), radius=r * SS, fill=fill, outline=outline, width=width * SS)


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(c, other, t):
    return tuple(round(c[i] * (1 - t) + other[i] * t) for i in range(3))


def draw_headphones(c):
    img, d = canvas()
    dark, mid = c, mix(c, (255, 255, 255), 0.18)
    shadow(img, (120, 590, 405, 645), 44)
    # headband: thick arc
    d.arc(S(150, 150, 375, 380), start=185, end=355, fill=dark, width=34 * SS)
    d.arc(S(150, 150, 375, 380), start=185, end=355, fill=mid, width=18 * SS)
    for x0 in (128, 337):
        rr(d, (x0, 268, x0 + 60, 300), 12, dark)
        rr(d, (x0 - 4, 296, x0 + 64, 470), 26, dark)
        rr(d, (x0 + 8, 312, x0 + 52, 452), 20, mid)
    return finish(img, f"{ID}.png")


def draw_earbuds(c):
    img, d = canvas()
    dark, light = c, mix(c, (255, 255, 255), 0.25)
    shadow(img, (140, 560, 390, 610), 40)
    rr(d, (120, 330, 405, 585), 40, dark)
    rr(d, (136, 346, 389, 420), 26, light)      # open lid
    for i, x0 in enumerate((175, 300)):
        rr(d, (x0, 400, x0 + 52, 470), 22, (245, 246, 248))
        rr(d, (x0 + 12, 352, x0 + 40, 412), 14, (232, 234, 238))
    rr(d, (222, 520, 302, 540), 10, mix(dark, (255, 255, 255), 0.35))
    return finish(img, f"{ID}.png")


def draw_speaker(c):
    img, d = canvas()
    shadow(img, (150, 585, 375, 635), 40)
    rr(d, (150, 250, 375, 590), 46, c)
    for row in range(7):
        for col in range(6):
            x = 190 + col * 26
            y = 300 + row * 30
            d.ellipse(S(x, y, x + 12, y + 12), fill=mix(c, (255, 255, 255), 0.22))
    rr(d, (196, 520, 329, 556), 16, mix(c, (0, 0, 0), 0.22))
    return finish(img, f"{ID}.png")


def draw_watch(c):
    img, d = canvas()
    shadow(img, (170, 600, 355, 645), 40)
    rr(d, (197, 130, 328, 300), 26, mix(c, (255, 255, 255), 0.12))
    rr(d, (197, 470, 328, 620), 26, mix(c, (255, 255, 255), 0.12))
    rr(d, (150, 268, 375, 505), 40, c)
    rr(d, (170, 288, 355, 485), 32, (245, 246, 249))
    d.ellipse(S(228, 340, 297, 409), fill=mix(c, (0, 0, 0), 0.15))
    d.line(S(262, 345, 262, 380), fill=(255, 255, 255), width=6 * SS)
    rr(d, (340, 360, 366, 408), 10, mix(c, (0, 0, 0), 0.3))
    return finish(img, f"{ID}.png")


def draw_powerbank(c):
    img, d = canvas()
    shadow(img, (140, 580, 385, 625), 36)
    rr(d, (140, 250, 385, 585), 30, c, WHITE_EDGE, 3)
    for i in range(4):
        d.ellipse(S(172 + i * 22, 285, 186 + i * 22, 299), fill=(120, 200, 140))
    rr(d, (176, 500, 236, 530), 8, (210, 214, 220))
    rr(d, (250, 500, 320, 530), 8, (210, 214, 220))
    d.line(S(196, 515, 216, 515), fill=(90, 95, 102), width=4 * SS)
    return finish(img, f"{ID}.png")


def draw_keyboard(c):
    img, d = canvas()
    shadow(img, (105, 545, 420, 585), 36)
    rr(d, (95, 300, 430, 540), 22, c)
    key = mix(c, (255, 255, 255), 0.16)
    for row in range(4):
        for col in range(12):
            x = 115 + col * 26
            y = 322 + row * 40
            rr(d, (x, y, x + 22, y + 32), 5, key)
    rr(d, (200, 482, 325, 514), 6, key)         # space bar
    return finish(img, f"{ID}.png")


def draw_mouse(c):
    img, d = canvas()
    shadow(img, (165, 560, 360, 605), 36)
    rr(d, (165, 260, 360, 570), 92, c, WHITE_EDGE, 3)
    d.line(S(262, 262, 262, 360), fill=WHITE_EDGE, width=3 * SS)
    rr(d, (248, 292, 278, 340), 12, (190, 195, 204))
    return finish(img, f"{ID}.png")


def draw_hub(c):
    img, d = canvas()
    shadow(img, (85, 512, 440, 552), 34)
    # A short braided cable leaving the left end, then a flat aluminium bar with ports.
    d.line(S(60, 420, 110, 420), fill=mix(c, (0, 0, 0), 0.35), width=12 * SS)
    rr(d, (44, 402, 84, 438), 8, mix(c, (0, 0, 0), 0.45))
    rr(d, (110, 340, 460, 500), 22, c)
    d.line(S(110, 372, 460, 372), fill=mix(c, (255, 255, 255), 0.22), width=3 * SS)
    for x0 in (140, 196, 252, 308):
        rr(d, (x0, 404, x0 + 40, 444), 6, mix(c, (0, 0, 0), 0.3))
    rr(d, (378, 400, 440, 448), 8, mix(c, (0, 0, 0), 0.2))
    return finish(img, f"{ID}.png")


def draw_stand(c):
    img, d = canvas()
    shadow(img, (120, 570, 415, 615), 34)
    # A-frame: two angled legs meeting a raised platform.
    d.polygon(S(150, 560, 196, 560, 262, 300, 236, 300), fill=c)
    d.polygon(S(385, 560, 339, 560, 273, 300, 299, 300), fill=mix(c, (0, 0, 0), 0.16))
    rr(d, (236, 292, 299, 320), 8, mix(c, (255, 255, 255), 0.22))
    rr(d, (140, 540, 396, 572), 14, mix(c, (0, 0, 0), 0.28))
    for x0 in (160, 250, 340):
        rr(d, (x0, 552, x0 + 46, 562), 4, mix(c, (0, 0, 0), 0.55))
    return finish(img, f"{ID}.png")


def draw_webcam(c):
    img, d = canvas()
    shadow(img, (170, 555, 355, 595), 34)
    rr(d, (150, 220, 375, 430), 40, c)
    d.ellipse(S(215, 275, 310, 370), fill=mix(c, (0, 0, 0), 0.35))
    d.ellipse(S(237, 297, 288, 348), fill=(70, 90, 130))
    d.ellipse(S(248, 308, 272, 332), fill=(150, 190, 240))
    rr(d, (238, 430, 288, 500), 10, mix(c, (255, 255, 255), 0.15))
    rr(d, (190, 496, 336, 552), 18, mix(c, (0, 0, 0), 0.2))
    return finish(img, f"{ID}.png")


def draw_ssd(c):
    img, d = canvas()
    shadow(img, (150, 555, 375, 595), 34)
    rr(d, (150, 270, 375, 545), 26, c)
    rr(d, (172, 292, 353, 380), 14, mix(c, (255, 255, 255), 0.24))
    d.line(S(262, 545, 262, 620), fill=mix(c, (0, 0, 0), 0.3), width=9 * SS)
    rr(d, (246, 610, 278, 640), 6, mix(c, (255, 255, 255), 0.2))
    return finish(img, f"{ID}.png")


def draw_monitor(c):
    img, d = canvas()
    shadow(img, (105, 605, 420, 645), 36)
    rr(d, (95, 150, 430, 480), 14, mix(c, (255, 255, 255), 0.1))
    rr(d, (112, 166, 413, 462), 8, (238, 241, 246))
    rr(d, (200, 500, 325, 590), 10, mix(c, (255, 255, 255), 0.16))
    rr(d, (150, 585, 375, 612), 10, mix(c, (0, 0, 0), 0.2))
    return finish(img, f"{ID}.png")


DRAW = {
    "headphones": draw_headphones, "earbuds": draw_earbuds, "speaker": draw_speaker,
    "watch": draw_watch, "powerbank": draw_powerbank, "keyboard": draw_keyboard,
    "mouse": draw_mouse, "hub": draw_hub, "stand": draw_stand, "webcam": draw_webcam,
    "ssd": draw_ssd, "monitor": draw_monitor,
}


def main():
    data_only = "--data-only" in sys.argv
    os.makedirs(OUT_DIR, exist_ok=True)
    products = json.load(open(PRODUCTS, encoding="utf-8"))
    by_id = {p["id"]: p for p in products}

    added = 0
    for item in ITEMS:
        global ID
        ID = item["id"]
        rec = {
            "id": item["id"], "name": item["name"], "brand": item["brand"],
            "category": "Electronics", "subcategory": item["subcategory"],
            "price": item["price"], "currency": "USD",
            "color": item["color"], "colorName": item["colorName"],
            "material": item["material"],
            # Every other product stores style as a list; a bare string renders as
            # one tag per letter ("M i n i m a l") in the tag row.
            "style": [item["style"]],
            "occasion": ["Casual", "Work", "Travel"],
            "season": ["Spring", "Summer", "Autumn", "Winter"],
            "climate": ["Mild", "Warm", "Cool", "Cold"],
            "gender": "Unisex", "emoji": item["emoji"],
            "rating": item["rating"], "reviews": item["reviews"],
            "description": item["description"], "description_zh": item["description_zh"],
            "tags": item["tags"], "name_zh": item["name_zh"],
            "slots": item["slots"],
            "fit": {"runs": "true", "stretch": "none"},
            "returnRate": item["returnRate"],
            "image": f"/assets/products/{item['id']}.png",
            "imageCredit": f"{item['credit']} (illustration)",
        }
        if item["id"] in by_id:
            by_id[item["id"]].update(rec)
        else:
            products.append(rec)
            added += 1

        if not data_only:
            path = DRAW[item["draw"]](hexrgb(item["color"]))
            print(f"  drew {os.path.basename(path)}")

    json.dump(products, open(PRODUCTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n  {added} added, {len(products)} products total")
    print(f"  electronics: {sum(1 for p in products if p['category'] == 'Electronics')}")


if __name__ == "__main__":
    main()
