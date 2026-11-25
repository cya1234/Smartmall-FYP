"""Offline benchmark: does personalisation beat the baselines, and how many survey
questions is it worth asking?

Why a simulation rather than a live test: there are no real users yet. That must be
stated in any report that quotes these numbers. What the simulation *can* establish is
whether the ranking machinery works and where the returns from extra questions flatten
out — questions that a live test would take weeks to answer.

The generative model, stated plainly so it can be argued with:

  * every synthetic shopper has a stable latent taste over category, style, colour,
    occasion and price band, plus a small idiosyncratic liking for individual products
  * a product's true utility to that shopper is a weighted sum of those attribute
    matches, plus the idiosyncratic term, plus noise
  * survey answers are noisy observations of that taste: each answer names the right
    preference with probability ``reliability``, and the rest are wrong picks
  * the estimator only ever sees the answers — never the latent taste

So the chain is: taste -> (noisy) answers -> estimate -> ranking, and the ranking is
scored against the ranking that the true taste would produce. More questions means more
attributes observed, which means a better estimate, until it stops mattering.

    python tools/bench_personalisation.py
    python tools/bench_personalisation.py --users 500 --seeds 7
"""
import argparse
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PRODUCTS = os.path.join(ROOT, "data", "products.json")
OUT_JSON = os.path.join(ROOT, "data", "eval", "personalisation-bench.json")
OUT_PNG = os.path.join(ROOT, "reports", "bench-personalisation.png")

# How much each attribute matters to a shopper's satisfaction.
IMPORTANCE = {"category": 0.38, "style": 0.24, "colorName": 0.16,
              "occasion": 0.10, "price": 0.07, "rating": 0.05}

# Which attributes each version of the survey reveals. The 10-question survey is the one
# that actually ships; the longer versions are hypothetical and exist to answer "would
# asking more help?".
SURVEY_ATTRIBUTES = {
    5: ["category"],
    10: ["category", "style", "colorName"],
    15: ["category", "style", "colorName", "occasion"],
    20: ["category", "style", "colorName", "occasion", "price"],
    25: ["category", "style", "colorName", "occasion", "price", "rating"],
}
# How often an answer actually reflects the shopper's taste. Longer surveys include more
# pairwise comparisons, which are less ambiguous, so reliability rises slightly.
SURVEY_RELIABILITY = {5: 0.62, 10: 0.70, 15: 0.76, 20: 0.82, 25: 0.86}


def load_products():
    with open(PRODUCTS, encoding="utf-8") as fh:
        return json.load(fh)


def value_of(product, attr):
    """The attribute value(s) a product has, as a list of strings."""
    if attr == "price":
        usd = float(product.get("price") or 0)
        if usd < 40:
            return ["budget"]
        if usd < 120:
            return ["mid"]
        if usd < 300:
            return ["premium"]
        return ["luxury"]
    if attr == "rating":
        r = float(product.get("rating") or 0)
        return ["high"] if r >= 4.6 else (["mid"] if r >= 4.3 else ["low"])
    v = product.get(attr)
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)] if v is not None else []


def attribute_domain(products, attr):
    domain = set()
    for p in products:
        domain.update(value_of(p, attr))
    return sorted(domain)


def make_user(rng, domains):
    """A latent taste: a weight per attribute value, plus idiosyncratic product likes."""
    taste = {}
    for attr, domain in domains.items():
        # Dirichlet gives a few strong preferences and a long tail, which is realistic.
        w = rng.dirichlet(np.ones(len(domain)) * 0.7)
        taste[attr] = dict(zip(domain, w))
    return taste


def true_utility(user, product, idio):
    """Ground truth: how much this shopper would actually like this product."""
    score = 0.0
    for attr, importance in IMPORTANCE.items():
        vals = value_of(product, attr)
        if not vals:
            continue
        # average the attribute weight over the values the product carries
        score += importance * float(np.mean([user[attr].get(v, 0.0) for v in vals]))
    score += idio.get(product["id"], 0.0) * 0.08
    return score


def ask_survey(user, attrs, reliability, rng, domains):
    """What the shopper actually tells us: a noisy view of their taste.

    For each attribute asked about, the answer names the true top value with probability
    `reliability`; otherwise it names a random value. Attributes not asked are unknown.
    """
    answers = {}
    for attr in attrs:
        domain = domains[attr]
        truth = max(domain, key=lambda v: user[attr].get(v, 0.0))
        if rng.random() < reliability:
            answers[attr] = truth
        else:
            answers[attr] = domain[int(rng.integers(0, len(domain)))]
    return answers


def estimate_score(answers, product, weighted=False):
    """Rank a product from what the survey revealed.

    Two variants, because they answer different questions:

      weighted=False   every answered attribute counts equally — this is close to what
                       the site currently does, and the benchmark shows its weakness
      weighted=True    each match is scaled by how much that attribute actually matters
                       to satisfaction, which is what the estimator *should* do

    Reporting both separates two things that are easy to confuse: whether the survey
    information is useful at all, and whether this code uses it well.
    """
    score = 0.0
    for attr, chosen in answers.items():
        w = IMPORTANCE[attr] if weighted else 1.0
        if attr == "price":
            bands = {"budget": (0, 40), "mid": (40, 120), "premium": (120, 300), "luxury": (300, 10 ** 9)}
            lo, hi = bands.get(chosen, (0, 10 ** 9))
            price = float(product.get("price") or 0)
            score += w if lo <= price < hi else 0.0
        elif attr == "rating":
            r = float(product.get("rating") or 0)
            ok = ((chosen == "high" and r >= 4.6) or (chosen == "mid" and 4.3 <= r < 4.6)
                  or (chosen == "low" and r < 4.3))
            score += w if ok else 0.0
        else:
            vals = value_of(product, attr)
            score += w if chosen in vals else 0.0
    return score


def ndcg(ranked_ids, gains, k=5):
    """Normalised discounted cumulative gain against the ground-truth ordering."""
    ranked = [gains.get(pid, 0.0) for pid in ranked_ids[:k]]
    best = sorted(gains.values(), reverse=True)[:k]
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(ranked))
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(best))
    return dcg / idcg if idcg > 0 else 0.0


def hit_rate(ranked_ids, truth_order, k=3):
    return 1.0 if set(ranked_ids[:k]) & set(truth_order[:k]) else 0.0


def category_entropy(ranked_ids, by_id):
    counts = {}
    for pid in ranked_ids:
        c = by_id[pid]["category"]
        counts[c] = counts.get(c, 0) + 1
    total = sum(counts.values()) or 1
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def run(products, users=300, seeds=5, k=5):
    domains = {attr: attribute_domain(products, attr) for attr in IMPORTANCE}
    by_id = {p["id"]: p for p in products}
    ids = [p["id"] for p in products]

    # Baselines that need no personalisation are computed once.
    popularity = sorted(ids, key=lambda i: -(
        float(by_id[i].get("reviews") or 0) * max(1.0, float(by_id[i].get("rating") or 0))
    ))
    by_rating = sorted(ids, key=lambda i: -float(by_id[i].get("rating") or 0))

    questions = sorted(SURVEY_ATTRIBUTES)
    variants = ("naive", "weighted")
    results = {q: {v: {"ndcg5": [], "hit3": [], "entropy": []} for v in variants} for q in questions}
    baseline = {"random": {"ndcg5": [], "hit3": [], "entropy": []},
                "popularity": {"ndcg5": [], "hit3": [], "entropy": []},
                "rating": {"ndcg5": [], "hit3": [], "entropy": []},
                "category_filter": {"ndcg5": [], "hit3": [], "entropy": []}}

    for seed in range(seeds):
        rng = np.random.default_rng(1000 + seed)
        for _ in range(users):
            user = make_user(rng, domains)
            idio = {pid: float(rng.normal(0, 1)) for pid in ids}

            utilities = {pid: true_utility(user, by_id[pid], idio) for pid in ids}
            lo = min(utilities.values())
            span = (max(utilities.values()) - lo) or 1.0
            gains = {pid: (u - lo) / span for pid, u in utilities.items()}
            truth_order = sorted(ids, key=lambda i: -utilities[i])

            # ---- baselines
            pick = int(rng.integers(0, len(ids)))
            shuffled = ids[:]
            rng.shuffle(shuffled)
            for name, order in (("random", shuffled), ("popularity", popularity), ("rating", by_rating)):
                baseline[name]["ndcg5"].append(ndcg(order, gains, k))
                baseline[name]["hit3"].append(hit_rate(order, truth_order, 3))
                baseline[name]["entropy"].append(category_entropy(order[:k], by_id))

            # category filter: the honest version of "just show them the category they
            # picked". It uses the same noisy survey answer everyone else gets, not the
            # shopper's hidden taste — using the truth here would be an oracle baseline
            # and would flatter it against the personalised methods.
            noisy_cat = ask_survey(user, ["category"], SURVEY_RELIABILITY[10], rng, domains)["category"]
            filtered = [i for i in popularity if by_id[i]["category"] == noisy_cat] or popularity
            baseline["category_filter"]["ndcg5"].append(ndcg(filtered, gains, k))
            baseline["category_filter"]["hit3"].append(hit_rate(filtered, truth_order, 3))
            baseline["category_filter"]["entropy"].append(category_entropy(filtered[:k], by_id))

            # ---- personalised, for each survey length and each estimator
            for q in questions:
                answers = ask_survey(user, SURVEY_ATTRIBUTES[q], SURVEY_RELIABILITY[q], rng, domains)
                for variant, weighted in (("naive", False), ("weighted", True)):
                    scored = sorted(ids, key=lambda i: -estimate_score(answers, by_id[i], weighted))
                    out = results[q][variant]
                    out["ndcg5"].append(ndcg(scored, gains, k))
                    out["hit3"].append(hit_rate(scored, truth_order, 3))
                    out["entropy"].append(category_entropy(scored[:k], by_id))

    def summarise(block):
        return {m: {"mean": float(np.mean(v)), "std": float(np.std(v)), "n": len(v)}
                for m, v in block.items()}

    return {
        "k": k,
        "users": users,
        "seeds": seeds,
        "samples_per_config": users * seeds,
        "products": len(products),
        "baselines": {name: summarise(b) for name, b in baseline.items()},
        "survey_lengths": {
            str(q): {v: summarise(block) for v, block in per_variant.items()}
            for q, per_variant in results.items()
        },
        "notes": [
            "Synthetic users with a stated generative model; not live user data.",
            "Gain is the shopper's true utility, min-max normalised per user.",
            "Survey answers are noisy observations of that utility (reliability 0.62-0.86).",
            "naive = every answered attribute weighted equally (what the site does now).",
            "weighted = attributes weighted by how much they actually affect satisfaction.",
        ],
    }


def plot(res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    qs = [int(q) for q in res["survey_lengths"]]
    series = {
        "naive": ("#B03A2B", "equal weights (current code)"),
        "weighted": ("#1F4E79", "importance-weighted (proposed)"),
    }

    fig, ax = plt.subplots(figsize=(9.5, 5.2), dpi=130)
    for name, (colour, label) in series.items():
        vals = [res["survey_lengths"][str(q)][name]["ndcg5"]["mean"] for q in qs]
        # Standard error, not standard deviation: the question is how precisely the mean
        # is known, and per-sample spread would swamp the differences being compared.
        errs = [res["survey_lengths"][str(q)][name]["ndcg5"]["std"] /
                math.sqrt(max(1, res["survey_lengths"][str(q)][name]["ndcg5"]["n"]))
                for q in qs]
        ax.errorbar(qs, vals, yerr=errs, marker="o", linewidth=2.2, capsize=4,
                    color=colour, label=label)

    colours = {"popularity": "#C77D00", "rating": "#8E44AD",
               "random": "#888888", "category_filter": "#6B8E23"}
    for name, v in res["baselines"].items():
        ax.axhline(v["ndcg5"]["mean"], linestyle="--", linewidth=1.3,
                   color=colours.get(name, "#999"),
                   label=f"baseline: {name} ({v['ndcg5']['mean']:.3f})")

    ax.set_xlabel("Survey questions asked")
    ax.set_ylabel("NDCG@5  (higher is better)")
    ax.set_title("Personalisation vs baselines, and how many questions are worth asking")
    ax.set_xticks(qs)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    fig.savefig(OUT_PNG)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=300)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    products = load_products()
    res = run(products, users=args.users, seeds=args.seeds, k=args.k)

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    plot(res)

    print(f"  samples per configuration: {res['samples_per_config']}")
    print("")
    print("  Baselines")
    for name, v in res["baselines"].items():
        print(f"    {name:<16} NDCG@{res['k']}={v['ndcg5']['mean']:.4f}  "
              f"Hit@3={v['hit3']['mean']:.3f}  entropy={v['entropy']['mean']:.2f}")
    print("")
    print("  Personalised, by survey length")
    print(f"    {'questions':>10}  {'naive':>8}  {'weighted':>9}  {'hit@3(w)':>9}  {'entropy(w)':>10}")
    for q in sorted(res["survey_lengths"], key=int):
        block = res["survey_lengths"][q]
        print(f"    {q:>10}  {block['naive']['ndcg5']['mean']:>8.4f}  "
              f"{block['weighted']['ndcg5']['mean']:>9.4f}  "
              f"{block['weighted']['hit3']['mean']:>9.3f}  "
              f"{block['weighted']['entropy']['mean']:>10.2f}")
    print("")
    print(f"  wrote {OUT_JSON}")
    print(f"  wrote {OUT_PNG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
