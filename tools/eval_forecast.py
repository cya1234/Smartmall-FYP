"""Evaluate the forecasting models across the whole catalogue.

For every product: hold out the last 30 days, fit on the rest, and score
Prophet / linear trend / naive. Writes data/forecast-eval.json, which the site
and the report can read without re-running any models.

Run:  .venv\\Scripts\\python.exe tools/eval_forecast.py
"""
import json
import os
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "ai-service"))
os.environ.setdefault("MPLCONFIGDIR", os.path.join(ROOT, ".cache", "mpl"))

OUT = os.path.join(ROOT, "data", "forecast-eval.json")


def main():
    import warnings
    warnings.filterwarnings("ignore")

    import forecast_service as svc

    svc.load()
    ids = sorted(svc._history.keys())
    print(f"  evaluating {len(ids)} products (holdout 30 days) ...", flush=True)

    per_product = []
    t0 = time.time()
    for i, pid in enumerate(ids, 1):
        try:
            df = svc._frame(pid)
            comp = svc._holdout_comparison(df)
            per_product.append({"id": pid, **comp})
        except Exception as e:
            per_product.append({"id": pid, "error": str(e)[:120]})
        if i % 10 == 0:
            print(f"    {i}/{len(ids)}  ({time.time()-t0:.0f}s)", flush=True)

    ok = [p for p in per_product if "models" in p]
    names = ["Prophet", "Linear trend", "Naive (last price)"]
    aggregate = []
    for name in names:
        vals = []
        for p in ok:
            m = next((x for x in p["models"] if x["name"] == name), None)
            if m and m.get("mape") is not None:
                vals.append(m)
        if not vals:
            continue
        aggregate.append({
            "name": name,
            "products": len(vals),
            "mae": round(sum(v["mae"] for v in vals) / len(vals), 2),
            "rmse": round(sum(v["rmse"] for v in vals) / len(vals), 2),
            "mape": round(sum(v["mape"] for v in vals) / len(vals), 2),
            "mapeMedian": round(sorted(v["mape"] for v in vals)[len(vals) // 2], 2),
        })

    wins = {n: sum(1 for p in ok if p.get("best") == n) for n in names}

    doc = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "holdoutDays": 30,
        "productsEvaluated": len(ok),
        "aggregate": aggregate,
        "wins": wins,
        "note": (
            "Measured on the synthetic price feed in data/price-history.json, whose sale "
            "calendar is known to the Prophet model. The gap over the linear baseline is "
            "therefore an upper bound; real retail data would be noisier."
        ),
        "perProduct": per_product,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)

    print()
    print(f"  {'model':22s} {'MAE':>8s} {'RMSE':>8s} {'MAPE%':>8s} {'median%':>8s}")
    for a in aggregate:
        print(f"  {a['name']:22s} {a['mae']:8.2f} {a['rmse']:8.2f} {a['mape']:8.2f} {a['mapeMedian']:8.2f}")
    print()
    print("  wins:", wins)
    print(f"  wrote {OUT} ({os.path.getsize(OUT)/1024:.1f} KB) in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
