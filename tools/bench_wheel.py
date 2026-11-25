"""Wheel economics: what does the spin actually cost, and when does it pay for itself?

The wheel is not a decoration — it is the incentive that makes somebody finish the
survey. So the question a supervisor will ask is the economic one: how much does a
completed survey cost, and what has to be true for that to be worth paying?

This script answers both from the shipped configuration rather than from opinion:

  * expected payout per spin, including the "spin again" segment, which is a geometric
    series rather than a simple average
  * the same figure at the top of the weight-shift range, i.e. what a well-answered
    survey costs
  * the break-even conversion lift for a range of product margins

    python tools/bench_wheel.py
"""
import json
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT_JSON = os.path.join(ROOT, "data", "eval", "wheel-economics.json")
OUT_PNG = os.path.join(ROOT, "reports", "bench-wheel.png")

# Mirrors lib/survey.js — kept as data here so the analysis does not need the Node runtime.
SEGMENTS = [
    {"id": "s1", "hkd": 1},
    {"id": "s2", "hkd": 2},
    {"id": "s3", "hkd": 3},
    {"id": "s5", "hkd": 5},
    {"id": "s8", "hkd": 8},
    {"id": "s10", "hkd": 10},
    {"id": "s12", "hkd": 12},
    {"id": "again", "again": True},
]


def wheel_weights(share):
    boost = max(0.0, min(1.0, share)) * 10
    raw = [
        max(4, 20 - boost),
        max(4, 22 - boost),
        max(4, 20 - boost),
        16,
        10 + boost * 0.45,
        6 + boost * 0.3,
        3 + boost * 0.2,
        3,
    ]
    return [round(w * 10) / 10 for w in raw]


def expected_payout(share):
    """Expected HKD paid out by one spin *attempt*, including re-spins.

    A re-spin is a fresh draw, so the total is the per-spin cash expectation divided by
    the chance of not landing on "again": E = C / (1 - p_again).
    """
    weights = wheel_weights(share)
    total = sum(weights)
    cash = sum(w * seg.get("hkd", 0) for w, seg in zip(weights, SEGMENTS))
    per_spin = cash / total
    again_w = sum(w for w, seg in zip(weights, SEGMENTS) if seg.get("again"))
    p_again = again_w / total
    return {
        "share": round(share, 2),
        "weights": weights,
        "cashPerSpin": round(per_spin, 3),
        "pAgain": round(p_again, 4),
        "expectedTotal": round(per_spin / (1 - p_again), 3),
        "expectedSpins": round(1 / (1 - p_again), 3),
    }


def break_even(margin_hkd, cost_hkd):
    """Conversion lift needed for the coupon cost to pay for itself.

    One extra sale at this margin covers cost/margin surveys; expressed as the absolute
    lift in conversion rate that must come from showing a coupon.
    """
    surveys_per_sale = margin_hkd / cost_hkd
    return {
        "margin": margin_hkd,
        "surveysPerExtraSale": round(surveys_per_sale, 1),
        "requiredLiftPct": round(100 / surveys_per_sale, 2),
    }


def main():
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    rows = [expected_payout(s / 10) for s in range(0, 11)]
    cheapest = rows[0]
    dearest = rows[-1]

    margins = [80, 150, 200, 300, 500]
    breaks = [break_even(m, dearest["expectedTotal"]) for m in margins]

    result = {
        "segments": SEGMENTS,
        "curve": rows,
        "atZeroShare": cheapest,
        "atFullShare": dearest,
        "breakEven": breaks,
        "notes": [
            "Costs are coupons paid out, not revenue lost: a coupon only costs margin if it is redeemed.",
            "The benchmark's information value is separate — see data/eval/personalisation-bench.json.",
            "Two spins per session are allowed, so per-session cost is up to twice these figures.",
        ],
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        shares = [r["share"] for r in rows]
        cash = [r["cashPerSpin"] for r in rows]
        total = [r["expectedTotal"] for r in rows]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6), dpi=130)

        ax1.plot(shares, cash, marker="o", color="#1F4E79", linewidth=2, label="cash per spin")
        ax1.plot(shares, total, marker="s", color="#C0392B", linewidth=2,
                 label="total incl. re-spins")
        ax1.set_xlabel("Answer quality (share of the wheel's favour, 0-1)")
        ax1.set_ylabel("Expected payout (HKD)")
        ax1.set_title("What a completed survey costs")
        ax1.grid(alpha=0.25)
        ax1.legend(fontsize=9)

        ax1b = ax1.twinx()
        ax1b.plot(shares, [r["expectedSpins"] for r in rows], linestyle=":", color="#888")
        ax1b.set_ylabel("Expected spins (dotted)", color="#888")
        ax1b.tick_params(axis="y", colors="#888")

        ax2.plot([b["margin"] for b in breaks], [b["requiredLiftPct"] for b in breaks],
                 marker="o", color="#6B8E23", linewidth=2)
        for b in breaks:
            ax2.annotate(f"{b['requiredLiftPct']}%", (b["margin"], b["requiredLiftPct"]),
                         textcoords="offset points", xytext=(0, 8), fontsize=8, ha="center")
        ax2.set_xlabel("Product margin (HKD)")
        ax2.set_ylabel("Conversion lift needed (percentage points)")
        ax2.set_title("Break-even: how much extra conversion must the coupon buy?")
        ax2.grid(alpha=0.25)

        fig.tight_layout()
        os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
        fig.savefig(OUT_PNG)
        plt.close(fig)
    except Exception as exc:
        print(f"  (chart skipped: {exc})")

    print(f"  no answers  : HK${cheapest['expectedTotal']:.2f} per attempt "
          f"({cheapest['expectedSpins']:.2f} spins)")
    print(f"  good answers: HK${dearest['expectedTotal']:.2f} per attempt "
          f"({dearest['expectedSpins']:.2f} spins)")
    print("")
    print("  break-even conversion lift:")
    for b in breaks:
        print(f"    margin HK${b['margin']:>3}  ->  1 extra sale per "
              f"{b['surveysPerExtraSale']:>5.1f} surveys  =  +{b['requiredLiftPct']:.2f} pp")
    print("")
    print(f"  wrote {OUT_JSON}")
    print(f"  wrote {OUT_PNG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
