"""SmartMall price-forecasting service (Meta Prophet).

A stdlib HTTP service that holds the 800-day price history, fits a Prophet model
per product (lazily, then caches it) and returns a forecast plus a buying
advisory. It also reports a holdout comparison against two baselines so the
accuracy claims are measurable rather than asserted.

Method note: retail seasonality here is driven by the *sale calendar* (雙十一,
Black Friday, Christmas, Lunar New Year…). Those are supplied to Prophet as
explicit holiday regressors instead of being left to a Fourier yearly term --
sharper, and it generalises to the flagged future dates.

Endpoints
    GET /health
    GET /forecast/:productId?horizon=30
    GET /eval                      aggregate model comparison (tools/eval_forecast.py)

Run:  .venv\\Scripts\\python.exe ai-service/forecast_service.py --port 8002
"""
import argparse
import json
import math
import os
import sys
import threading
import time
import traceback
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("MPLCONFIGDIR", os.path.join(ROOT, ".cache", "mpl"))

HISTORY_PATH = os.path.join(ROOT, "data", "price-history.json")
EVAL_PATH = os.path.join(ROOT, "data", "forecast-eval.json")

CHART_DAYS = 120   # daily points sent to the front-end chart
HORIZON = 30       # default forecast horizon
DROP_THRESHOLD = 4.0

# Sale calendar used both in the generator and here. (name, month-day, lower, upper)
SALES = [
    ("double11", "11-11", 2, 1, "雙十一 Double 11"),
    ("black-friday", "11-27", 1, 3, "黑色星期五 Black Friday"),
    ("christmas", "12-25", 3, 2, "聖誕節 Christmas"),
    ("new-year", "01-01", 1, 1, "新年 New Year"),
    ("summer-sale", "07-01", 0, 9, "夏季特賣 Summer sale"),
    ("mid-autumn", "09-20", 2, 2, "中秋 Mid-Autumn"),
]

_state = {"ready": False, "error": None}
_lock = threading.Lock()
_history = {}
_cache = {}
_horizons = {}
_holidays = None


def _holiday_frame():
    """Bag of explicit sale dates spanning history and the forecast horizon."""
    global _holidays
    if _holidays is not None:
        return _holidays
    import pandas as pd

    years = range(2024, date.today().year + 2)
    rows = []
    for name, md, lo, hi, _label in SALES:
        for y in years:
            rows.append({"holiday": name, "ds": pd.Timestamp(f"{y}-{md}"),
                         "lower_window": -lo, "upper_window": hi})
    # Lunar New Year moves; list the known dates explicitly.
    for y, md in [(2024, "02-10"), (2025, "01-29"), (2026, "02-17"), (2027, "02-06")]:
        rows.append({"holiday": "lunar-new-year", "ds": pd.Timestamp(f"{y}-{md}"),
                     "lower_window": -3, "upper_window": 3})
    _holidays = pd.DataFrame(rows).drop_duplicates(subset=["holiday", "ds"])
    return _holidays


def load():
    global _history
    if not os.path.exists(HISTORY_PATH):
        raise FileNotFoundError(f"{HISTORY_PATH} missing - run tools/build_price_history.py")
    with open(HISTORY_PATH, encoding="utf-8") as fh:
        _history = json.load(fh)
    _state["ready"] = True
    print(f"  history   {len(_history)} products, "
          f"{sum(len(v['points']) for v in _history.values())} daily observations", flush=True)


def _frame(product_id):
    import pandas as pd
    pts = _history[product_id]["points"]
    df = pd.DataFrame(pts)
    df["ds"] = pd.to_datetime(df["ds"])
    df = df.rename(columns={"price": "y"})
    return df


def _fit(df, holidays):
    from prophet import Prophet
    m = Prophet(
        holidays=holidays,
        yearly_seasonality="auto",
        weekly_seasonality=True,
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
        seasonality_prior_scale=10,
        holidays_prior_scale=10,
        interval_width=0.8,
    )
    m.fit(df)
    return m


def _linear_baseline(train, steps):
    """Plain OLS on a time index -- the model the site shipped before Prophet."""
    n = len(train)
    xs = list(range(n))
    ys = [float(v) for v in train["y"].values]
    mx = sum(xs) / n
    my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs) or 1
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    intercept = my - slope * mx
    return [intercept + slope * (n + i) for i in range(steps)]


def _metrics(actual, predicted):
    n = min(len(actual), len(predicted))
    if n == 0:
        return {"mae": None, "rmse": None, "mape": None}
    ae = [abs(actual[i] - predicted[i]) for i in range(n)]
    se = [(actual[i] - predicted[i]) ** 2 for i in range(n)]
    pe = [abs(actual[i] - predicted[i]) / actual[i] * 100 for i in range(n) if actual[i]]
    return {
        "mae": round(sum(ae) / n, 2),
        "rmse": round(math.sqrt(sum(se) / n), 2),
        "mape": round(sum(pe) / len(pe), 2) if pe else None,
    }


def _holdout_comparison(df, holdout_days=30):
    """Fit on everything but the last N days, then score three models."""
    train = df.iloc[:-holdout_days]
    test = df.iloc[-holdout_days:]
    actual = [float(v) for v in test["y"].values]

    holidays = _holiday_frame()
    forecast = []

    # Prophet
    m = _fit(train, holidays)
    fc = m.predict(m.make_future_dataframe(periods=holdout_days)).tail(holdout_days)
    forecast.append(("Prophet", _metrics(actual, [float(v) for v in fc["yhat"].values])))

    # Baseline: linear trend
    recent = train.tail(60)
    forecast.append(("Linear trend", _metrics(actual, _linear_baseline(recent, holdout_days))))

    # Baseline: naive (carry last price)
    last = float(train["y"].iloc[-1])
    forecast.append(("Naive (last price)", _metrics(actual, [last] * holdout_days)))

    best = min(forecast, key=lambda kv: kv[1]["mape"] if kv[1]["mape"] else 1e9)
    return {
        "holdoutDays": holdout_days,
        "models": [{"name": n, **m} for n, m in forecast],
        "best": best[0],
    }


def _upcoming_events(forecast_df, current):
    """Sales inside the horizon, with the price Prophet expects that day."""
    out = []
    today = date.today()
    by_date = {r["ds"].date(): r for _, r in forecast_df.iterrows()}
    for name, md, lo, hi, label in SALES:
        for y in (today.year, today.year + 1):
            try:
                anchor = datetime.strptime(f"{y}-{md}", "%Y-%m-%d").date()
            except ValueError:
                continue
            if not (today < anchor <= today + timedelta(days=len(forecast_df))):
                continue
            row = by_date.get(anchor)
            if row is None:
                continue
            predicted = float(row["yhat"])
            out.append({
                "name": name,
                "label": label,
                "date": anchor.isoformat(),
                "daysAway": (anchor - today).days,
                "predictedPrice": round(predicted, 2),
                "dropPct": round((current - predicted) / current * 100, 1),
            })
    return sorted(out, key=lambda e: e["daysAway"])


def forecast(product_id, horizon=HORIZON, with_comparison=True):
    with _lock:
        key = (product_id, horizon, with_comparison)
        if key in _cache:
            cached = dict(_cache[key])
            cached["cached"] = True
            return cached

        df = _frame(product_id)
        current = float(df["y"].iloc[-1])
        t0 = time.time()
        model = _fit(df, _holiday_frame())
        fc = model.predict(model.make_future_dataframe(periods=horizon)).tail(horizon)
        fit_seconds = round(time.time() - t0, 2)

        points = []
        for _, r in fc.iterrows():
            points.append({
                "t": int(r["ds"].timestamp() * 1000),
                "date": r["ds"].date().isoformat(),
                "price": round(float(r["yhat"]), 2),
                "lower": round(float(r["yhat_lower"]), 2),
                "upper": round(float(r["yhat_upper"]), 2),
            })

        prices = [p["price"] for p in points]
        lo = min(prices)
        hi = max(prices)
        expected_drop = (current - lo) / current * 100
        expected_rise = (hi - current) / current * 100

        # Trend from the first to the last forecast point.
        trend_pct = (prices[-1] - prices[0]) / prices[0] * 100 if prices else 0

        # Confidence from the width of Prophet's own 80% interval.
        widths = [(p["upper"] - p["lower"]) / p["price"] for p in points if p["price"]]
        rel_width = sum(widths) / len(widths) if widths else 1
        conf_score = max(0.3, min(0.95, 1.0 - rel_width * 2.2))
        confidence = "High" if conf_score > 0.66 else "Medium" if conf_score > 0.5 else "Low"

        events = _upcoming_events(fc, current)

        if expected_drop >= DROP_THRESHOLD:
            action = "wait"
            headline = "Wait for a Price Drop"
            headline_zh = "建議等降價"
            nearest = events[0] if events else None
            when = f"（{nearest['label']}，{nearest['daysAway']} 天後）" if nearest else ""
            when_en = f" (around {nearest['date']})" if nearest else ""
            reasoning = (f"Prophet projects this item's price could fall about {expected_drop:.1f}% "
                         f"to ~${lo:.2f} within {horizon} days{when_en}. Waiting is likely to pay off.")
            reasoning_zh = (f"Prophet 預測未來 {horizon} 天內價格可能下跌約 {expected_drop:.1f}%，"
                            f"最低約 ${lo:.2f}{when}。現在買很可能買貴，建議再等一下。")
        elif trend_pct >= 2:
            action = "buy"
            headline = "Buy Now"
            headline_zh = "建議現在買"
            reasoning = (f"The projected trend is upward (≈+{trend_pct:.1f}% over {horizon} days). "
                         f"Buying now locks in today's price.")
            reasoning_zh = f"預測未來 {horizon} 天整體趨勢向上（約 +{trend_pct:.1f}%），現在購入可鎖定目前價格。"
        else:
            action = "buy"
            headline = "Buy Now — Price Is Stable"
            headline_zh = "建議現在買 — 價格平穩"
            reasoning = (f"No meaningful drop is projected in the next {horizon} days "
                         f"(trend {trend_pct:+.1f}%), so waiting is unlikely to help.")
            reasoning_zh = f"未來 {horizon} 天沒有明顯降價訊號（趨勢 {trend_pct:+.1f}%），繼續等通常省不到錢。"

        # Chart series: recent daily history.
        hist = df.tail(CHART_DAYS)
        history = [{"t": int(r["ds"].timestamp() * 1000), "price": round(float(r["y"]), 2)}
                   for _, r in hist.iterrows()]

        result = {
            "engine": "prophet",
            "engineLabel": "Meta Prophet + sale-calendar regressors",
            "productId": product_id,
            "current": round(current, 2),
            "currency": _history[product_id]["currency"],
            "horizonDays": horizon,
            "fitSeconds": fit_seconds,
            "trend": {
                "direction": "falling" if trend_pct < -1 else "rising" if trend_pct > 1 else "stable",
                "weeklyChangePct": round(trend_pct / (horizon / 7), 2),
                "horizonChangePct": round(trend_pct, 2),
            },
            "history": history,
            "forecast": points,
            "events": events,
            "advisory": {
                "action": action,
                "headline": headline,
                "headline_zh": headline_zh,
                "reasoning": reasoning,
                "reasoning_zh": reasoning_zh,
                "expectedDropPct": round(expected_drop, 1),
                "expectedRisePct": round(expected_rise, 1),
                "confidence": confidence,
                "confidenceScore": round(conf_score, 2),
            },
            "cached": False,
        }

        if with_comparison:
            try:
                result["comparison"] = _holdout_comparison(df)
            except Exception as e:  # never fail the whole forecast for metrics
                result["comparison"] = {"error": str(e)[:120]}

        _cache[key] = result
        return result


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parts = [p for p in self.path.split("?")[0].split("/") if p]
        query = {}
        if "?" in self.path:
            for kv in self.path.split("?", 1)[1].split("&"):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    query[k] = v

        if not _state["ready"]:
            return self._send(503, {"ok": False, "error": _state.get("error")})

        if parts and parts[0] == "health":
            return self._send(200, {
                "ok": True,
                "engine": "prophet",
                "version": _prophet_version(),
                "products": len(_history),
                "observations": sum(len(v["points"]) for v in _history.values()),
                "horizonDays": HORIZON,
                "cachedModels": len({k[0] for k in _cache}),
            })

        if parts and parts[0] == "eval":
            if os.path.exists(EVAL_PATH):
                with open(EVAL_PATH, encoding="utf-8") as fh:
                    return self._send(200, json.load(fh))
            return self._send(404, {"error": "run tools/eval_forecast.py first"})

        if len(parts) >= 2 and parts[0] == "forecast":
            pid = parts[1]
            if pid not in _history:
                return self._send(404, {"error": "product not found"})
            horizon = int(query.get("horizon", HORIZON))
            horizon = max(7, min(90, horizon))
            try:
                return self._send(200, forecast(pid, horizon, query.get("comparison") != "0"))
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {"error": str(e)})

        self._send(404, {"error": "not found"})


def _prophet_version():
    try:
        import prophet
        return getattr(prophet, "__version__", "?")
    except Exception:
        return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("FORECAST_PORT", 8002)))
    ap.add_argument("--host", default=os.environ.get("FORECAST_HOST", "127.0.0.1"))
    args = ap.parse_args()

    print("  loading price history ...", flush=True)
    t = time.time()
    try:
        load()
    except Exception as e:
        _state["error"] = str(e)
        print(f"  FAILED: {e}", flush=True)
        return 1

    print(f"  ready in {time.time()-t:.1f}s - listening on http://{args.host}:{args.port}\n", flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
