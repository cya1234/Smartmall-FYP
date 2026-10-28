"""Generate a realistic daily price history for every catalogue product.

This is the "historical price feed" the forecasting models consume. It is
deterministic (seeded per product id) so the demo is reproducible, and it
contains genuine calendar structure:

  * a slow inflationary trend
  * a small weekend discount
  * the Hong Kong / Greater China sale calendar -- 雙十一, Black Friday,
    Cyber Monday, Christmas, New Year, Lunar New Year, summer sale, Mid-Autumn

Output: data/price-history.json   { productId: { currency, points: [{ds, price}] } }

Run:  .venv\\Scripts\\python.exe tools\\build_price_history.py
"""
import json
import os
import random
from datetime import date, timedelta

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PRODUCTS = os.path.join(ROOT, "data", "products.json")
OUT = os.path.join(ROOT, "data", "price-history.json")

DAYS = 800  # ~26 months: satisfies Prophet's 730-day guidance for yearly seasonality


def nth_weekday(year, month, weekday, n):
    """n-th weekday (0=Mon) of a month -> date."""
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + timedelta(days=offset + 7 * (n - 1))


def black_friday(year):
    """Friday after the 4th Thursday of November."""
    thanksgiving = nth_weekday(year, 11, 3, 4)
    return thanksgiving + timedelta(days=1)


def event_windows(years):
    """(label, anchor date, days before, days after, fractional price change)."""
    out = []
    for y in years:
        out += [
            ("double11", date(y, 11, 11), 2, 1, -0.18),
            ("black-friday", black_friday(y), 1, 3, -0.15),
            ("cyber-monday", black_friday(y) + timedelta(days=3), 0, 1, -0.12),
            ("christmas", date(y, 12, 25), 3, 2, -0.10),
            ("new-year", date(y, 1, 1), 1, 1, -0.08),
            ("summer-sale", date(y, 7, 1), 0, 9, -0.10),
            ("mid-autumn", date(y, 9, 20), 2, 2, -0.08),
        ]
    # Lunar New Year moves each year.
    out += [
        ("lunar-new-year", date(2024, 2, 10), 3, 3, -0.12),
        ("lunar-new-year", date(2025, 1, 29), 3, 3, -0.12),
        ("lunar-new-year", date(2026, 2, 17), 3, 3, -0.12),
    ]
    return out


def build_series(product, end_date):
    rng = random.Random(product["id"])
    base = float(product["price"])
    start = end_date - timedelta(days=DAYS - 1)

    windows = event_windows(range(start.year, end_date.year + 1))

    # Not every SKU joins every promotion -- otherwise every product would share
    # an identical price curve and every advisory would say the same thing.
    # Participation and promo depth are *product traits* (a brand either joins
    # 雙十一 every year or it does not), not a fresh coin flip per year, which is
    # both realistic and something a model can actually learn.
    participation = {
        "double11": 0.72, "black-friday": 0.60, "cyber-monday": 0.45,
        "christmas": 0.50, "new-year": 0.40, "summer-sale": 0.55,
        "mid-autumn": 0.38, "lunar-new-year": 0.52,
    }
    joined = {k: rng.random() < p for k, p in participation.items()}
    depth_factor = {k: 0.65 + rng.random() * 0.55 for k in participation}

    # Which days carry a sale, and how deep.
    effect = {}
    for label, anchor, before, after, pct in windows:
        if not joined.get(label, False):
            continue
        depth = pct * depth_factor.get(label, 1.0)
        for k in range(-before, after + 1):
            d = anchor + timedelta(days=k)
            # deepest on the anchor day, tapering to the edges
            taper = 1.0 if k == 0 else (0.75 if abs(k) == 1 else 0.45)
            effect[d] = min(effect.get(d, 0.0), depth * taper)

    points = []
    for i in range(DAYS):
        d = start + timedelta(days=i)
        # slow inflation plus a gentle wave so the trend is not a straight line
        trend = 1.0 + 0.00013 * i
        wave = 1.0 + 0.012 * ((i % 180) / 180.0)
        # weekend shoppers see slightly better prices
        weekend = 0.994 if d.weekday() >= 5 else 1.0
        promo = 1.0 + effect.get(d, 0.0)
        noise = 1.0 + rng.gauss(0.0, 0.004)
        price = base * trend * wave * weekend * promo * noise
        points.append({"ds": d.isoformat(), "price": round(price, 2)})

    # Scale so the final point equals the catalogue price exactly.
    scale = base / points[-1]["price"]
    for p in points:
        p["price"] = round(p["price"] * scale, 2)
    return points


def main():
    with open(PRODUCTS, encoding="utf-8") as fh:
        products = json.load(fh)

    end_date = date.today()
    data = {}
    for p in products:
        pts = build_series(p, end_date)
        data[p["id"]] = {"currency": p["currency"], "points": pts}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)

    total = sum(len(v["points"]) for v in data.values())
    print(f"  products : {len(data)}")
    print(f"  points   : {total} daily observations ({DAYS} days each)")
    print(f"  range    : {data[next(iter(data))]['points'][0]['ds']} .. {end_date.isoformat()}")

    sample = data.get("p007") or data[next(iter(data))]
    around = [p for p in sample["points"] if p["ds"][5:7] == "11"][:14]
    print("  sample (November, p007):")
    for p in around[:14]:
        print(f"    {p['ds']}  {p['price']}")

    with open(OUT, "rb") as fh:
        print(f"  wrote {OUT} ({os.path.getsize(OUT)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
