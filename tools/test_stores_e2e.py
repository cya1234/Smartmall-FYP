"""End-to-end test for the O2O store module (store list, stock, distance, pickup)."""
import json
import math
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
fails = []


def get(path, timeout=30):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "ignore") or "{}")
        except Exception:
            return e.code, {}


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name:52s} {detail}")
    if not cond:
        fails.append(name)


print("== store list ==")
code, d = get("/api/stores")
stores = d.get("stores", [])
check("returns 8 stores", code == 200 and len(stores) == 8, f"{len(stores)}")
check("has pickup policy", bool(d.get("pickup", {}).get("sameDay")),
      d.get("pickup", {}).get("sameDay"))

required = ["id", "name_zh", "name_en", "district_zh", "district_en", "address_zh",
            "address_en", "mtr_zh", "mtr_en", "hours", "phone", "lat", "lng"]
missing = [f for f in required if not stores or f not in stores[0]]
check("store schema complete", not missing, f"missing={missing}")

hkk = all(22.1 <= s["lat"] <= 22.6 and 113.8 <= s["lng"] <= 114.5 for s in stores)
check("all coordinates inside Hong Kong", hkk, "lat 22.1-22.6, lng 113.8-114.5")

districts = [s["district_zh"] for s in stores]
check("districts cover island + kowloon + NT", len(set(districts)) == 8, ", ".join(districts))
check("every store offers pickup", all(s["pickup"] for s in stores))

print("\n== stock for one product ==")
code, a = get("/api/stores/stock/p007")
check("returns availability", code == 200 and a.get("productId") == "p007")
check("status is consistent with online stock",
      (a["status"] == "online") == (a["onlineStock"] > 0), f"status={a['status']}")
check("storeCount matches stores with qty > 0",
      a["storeCount"] == len([s for s in a["stores"] if s["qty"] > 0]),
      f"{a['storeCount']} of {len(a['stores'])}")
check("totalQty = online + store units",
      a["totalQty"] == a["onlineStock"] + a["totalStoreQty"],
      f"{a['totalQty']} = {a['onlineStock']} + {a['totalStoreQty']}")
check("no store exceeds 5 units", max(s["qty"] for s in a["stores"]) <= 5)

print("\n== the O2O rescue case exists in the catalogue ==")
code, products = get("/api/products")
rescued = []
for p in products[:40]:
    _, s = get(f"/api/stores/stock/{p['id']}")
    if not s.get("onlineInStock") and s.get("storeCount", 0) > 0:
        rescued.append((p["id"], s["storeCount"]))
check("some products are online-sold-out but in stores", len(rescued) >= 3,
      ", ".join(f"{i}({n})" for i, n in rescued[:5]))

print("\n== distance sorting with a shopper position ==")
# A point near Mong Kok should rank the Mong Kok store first.
code, near = get("/api/stores/stock/p007?lat=22.3193&lng=114.1694")
dists = [s.get("distanceKm") for s in near["stores"]]
check("distances are attached", all(v is not None for v in dists), f"{len(dists)} values")
check("sorted ascending by distance", dists == sorted(dists), f"first={dists[0]} km")
check("nearest store is Mong Kok", near["stores"][0]["id"] == "mk", near["stores"][0]["name_zh"])
check("nearest distance is ~0", dists[0] < 0.5, f"{dists[0]} km")

print("\n== validation ==")
code, _ = get("/api/stores/stock/does-not-exist")
check("404 for unknown product", code == 404, f"HTTP {code}")
code, one = get("/api/stores/one/cwb")
check("single store lookup", code == 200 and one.get("district_zh") == "銅鑼灣", one.get("name_zh"))
code, _ = get("/api/stores/one/nope")
check("404 for unknown store", code == 404, f"HTTP {code}")

print("\n== distance maths sanity ==")
# Central to Tsim Sha Tsui is roughly 2.5-3.5 km in a straight line.
code, tst = get("/api/stores/stock/p007?lat=22.2820&lng=114.1590")
by_id = {s["id"]: s for s in tst["stores"]}
d = by_id["tst"]["distanceKm"]
check("Central -> TST between 2 and 4 km", 2.0 < d < 4.0, f"{d} km")
check("Central -> Central is ~0", by_id["ctr"]["distanceKm"] < 0.3, f"{by_id['ctr']['distanceKm']} km")

print()
print("ALL CHECKS PASSED" if not fails else f"FAILURES: {', '.join(fails)}")
sys.exit(1 if fails else 0)
