"""Evaluate fashion retrieval models against the bilingual query set.

For each model: embed the 34 product photos once, then rank queries by cosine
similarity in the shared image-text space. Reports Recall@1/5/10 and MRR
overall, per language, per query type and per difficulty.

It also runs every model a second time with the Chinese queries pushed through a
rule-based zh->en fashion glossary. That isolates *why* Chinese retrieval is
weak: if the glossary closes the gap, the bottleneck is the text encoder's
language coverage, not the vision backbone.

Run:  .venv\\Scripts\\python.exe tools/eval_retrieval.py
      .venv\\Scripts\\python.exe tools/eval_retrieval.py --models marqo-fashionSigLIP
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".cache", "hf"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

QUERIES = os.path.join(ROOT, "data", "eval", "queries.json")
PRODUCTS = os.path.join(ROOT, "data", "products.json")
GLOSSARY = os.path.join(ROOT, "data", "fashion-glossary.json")
OUT = os.path.join(ROOT, "data", "eval", "results.json")

MODELS = {
    "clip-vitb32-laion2b": ("ViT-B-32", "laion2b_s34b_b79k", "ViT-B-32 / laion2b (current)"),
    "marqo-fashionCLIP": ("hf-hub:Marqo/marqo-fashionCLIP", None, "Marqo-FashionCLIP"),
    "marqo-fashionSigLIP": ("hf-hub:Marqo/marqo-fashionSigLIP", None, "Marqo-FashionSigLIP"),
}

_glossary = None


def load_glossary():
    global _glossary
    if _glossary is None:
        with open(GLOSSARY, encoding="utf-8") as fh:
            doc = json.load(fh)
        flat = {}
        for group in doc.values():
            if isinstance(group, dict):
                flat.update(group)
        _glossary = sorted(flat.items(), key=lambda kv: -len(kv[0]))  # longest first
    return _glossary


def translate_zh(text):
    """Greedy longest-match substitution into English fashion vocabulary."""
    gl = load_glossary()
    out, i = [], 0
    while i < len(text):
        for zh, en in gl:
            if text.startswith(zh, i):
                out.append(" " + en + " ")
                i += len(zh)
                break
        else:
            out.append(text[i])
            i += 1
    return " ".join("".join(out).split())


def load_model(name, pretrained):
    import open_clip
    if pretrained:
        model, _, preprocess = open_clip.create_model_and_transforms(name, pretrained=pretrained)
    else:
        model, _, preprocess = open_clip.create_model_and_transforms(name)
    tokenizer = open_clip.get_tokenizer(name)
    model.eval()
    return model, preprocess, tokenizer


def run_model(spec_key, products, queries, dev):
    """Return {'raw': {...}, 'translated': {...}} with a ranking per mode."""
    import torch
    from PIL import Image

    name, pretrained, label = MODELS[spec_key]
    t0 = time.time()
    model, preprocess, tokenizer = load_model(name, pretrained)
    model = model.to(dev)
    load_s = time.time() - t0

    batch = torch.stack([
        preprocess(Image.open(os.path.join(ROOT, "public", p["image"].lstrip("/"))).convert("RGB"))
        for p in products
    ])
    raw_texts = [q["query"] for q in queries]
    tr_texts = [translate_zh(q["query"]) or q["query"] if q["lang"] == "zh" else q["query"]
                for q in queries]

    t0 = time.time()
    with torch.no_grad(), torch.autocast(dev, dtype=torch.float16):
        ifeat = model.encode_image(batch.to(dev))
        ifeat = ifeat / ifeat.norm(dim=-1, keepdim=True)
        raw_f = model.encode_text(tokenizer(raw_texts).to(dev))
        raw_f = raw_f / raw_f.norm(dim=-1, keepdim=True)
        tr_f = model.encode_text(tokenizer(tr_texts).to(dev))
        tr_f = tr_f / tr_f.norm(dim=-1, keepdim=True)
    enc_s = time.time() - t0

    meta = {
        "label": label,
        "dim": int(ifeat.shape[-1]),
        "paramsM": round(sum(p.numel() for p in model.parameters()) / 1e6),
        "loadSeconds": round(load_s, 1),
        "encodeSeconds": round(enc_s, 1),
        "perQueryMs": round(enc_s / (len(queries) * 2) * 1000, 1),
        "translations": {q["query"]: t for q, t in zip(queries, tr_texts) if q["lang"] == "zh"},
    }

    def rank(text_feats):
        sims = (text_feats @ ifeat.T).float().cpu()
        out = []
        for i in range(sims.shape[0]):
            out.append([products[j]["id"] for j in torch.argsort(sims[i], descending=True).tolist()])
        return out

    raw_rank, tr_rank = rank(raw_f), rank(tr_f)
    del model
    torch.cuda.empty_cache()
    return meta, raw_rank, tr_rank


def score(queries, ranking, subset=None):
    idx = list(range(len(queries))) if subset is None else subset
    if not idx:
        return None
    hits = {1: 0, 5: 0, 10: 0}
    rr = 0.0
    for i in idx:
        targets = set(queries[i]["targets"])
        first = next((r + 1 for r, pid in enumerate(ranking[i]) if pid in targets), None)
        for k in hits:
            if first is not None and first <= k:
                hits[k] += 1
        rr += 1.0 / first if first else 0.0
    n = len(idx)
    return {
        "n": n,
        "recall@1": round(hits[1] / n * 100, 1),
        "recall@5": round(hits[5] / n * 100, 1),
        "recall@10": round(hits[10] / n * 100, 1),
        "mrr": round(rr / n, 3),
    }


def summarise(queries, ranking):
    by_lang = {lang: score(queries, ranking, [i for i, q in enumerate(queries) if q["lang"] == lang])
               for lang in ("zh", "en")}
    by_type, by_diff = {}, {}
    for i, q in enumerate(queries):
        by_type.setdefault(q["type"], []).append(i)
        by_diff.setdefault(q["difficulty"], []).append(i)
    fails = []
    for i, q in enumerate(queries):
        targets = set(q["targets"])
        first = next((r + 1 for r, pid in enumerate(ranking[i]) if pid in targets), None)
        if first is None or first > 5:
            fails.append({"query": q["query"], "lang": q["lang"], "type": q["type"],
                          "rank": first, "top1": ranking[i][0]})
    return {
        "overall": score(queries, ranking),
        "byLanguage": by_lang,
        "byType": {k: score(queries, ranking, v) for k, v in by_type.items()},
        "byDifficulty": {k: score(queries, ranking, v) for k, v in by_diff.items()},
        "failures": fails[:12],
        "failCount": len(fails),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(MODELS.keys()))
    args = ap.parse_args()
    wanted = [m.strip() for m in args.models.split(",") if m.strip() in MODELS]

    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"

    with open(QUERIES, encoding="utf-8") as fh:
        qdoc = json.load(fh)
    queries = qdoc["queries"]
    with open(PRODUCTS, encoding="utf-8") as fh:
        products = [p for p in json.load(fh) if p.get("image")]

    print(f"  device    : {dev}")
    print(f"  catalogue : {len(products)} retrievable products")
    print(f"  queries   : {len(queries)} ({qdoc['counts']['byLanguage']})")
    print()

    results = {}
    for key in wanted:
        print(f"  running {MODELS[key][2]} ...", flush=True)
        try:
            meta, raw_rank, tr_rank = run_model(key, products, queries, dev)
        except Exception as e:
            print(f"    FAILED: {type(e).__name__}: {e}")
            continue
        results[key] = {**meta, "raw": summarise(queries, raw_rank),
                        "translated": summarise(queries, tr_rank)}
        print(f"    raw R@5 {results[key]['raw']['overall']['recall@5']}%  "
              f"translated R@5 {results[key]['translated']['overall']['recall@5']}%")

    if not results:
        print("  no model produced results")
        return 1

    def line(label, s, width=30):
        o = s["overall"]
        return (f"  {label[:width]:{width}s} {o['recall@1']:5.1f}% {o['recall@5']:5.1f}% "
                f"{o['recall@10']:6.1f}% {o['mrr']:6.3f}")

    for mode in ("raw", "translated"):
        title = "RAW QUERIES" if mode == "raw" else "CHINESE QUERIES TRANSLATED zh->en (glossary)"
        print()
        print(f"  === {title} ===")
        print(f"  {'model':30s} {'R@1':>6s} {'R@5':>6s} {'R@10':>7s} {'MRR':>6s}")
        print("  " + "-" * 58)
        for key, r in results.items():
            print(line(r["label"], r[mode]))

    print()
    print("  === CHINESE vs ENGLISH (Recall@5) ===")
    print(f"  {'model':30s} {'zh raw':>8s} {'zh trans':>9s} {'en':>7s} {'zh gain':>9s}")
    print("  " + "-" * 68)
    for key, r in results.items():
        zr = r["raw"]["byLanguage"]["zh"]["recall@5"]
        zt = r["translated"]["byLanguage"]["zh"]["recall@5"]
        en = r["raw"]["byLanguage"]["en"]["recall@5"]
        print(f"  {r['label'][:30]:30s} {zr:7.1f}% {zt:8.1f}% {en:6.1f}% {zt - zr:+8.1f}")

    print()
    print("  === by difficulty (Recall@5, translated mode) ===")
    print(f"  {'model':30s} {'easy':>8s} {'medium':>8s} {'hard':>8s}")
    print("  " + "-" * 58)
    for key, r in results.items():
        d = r["translated"]["byDifficulty"]
        print(f"  {r['label'][:30]:30s} "
              f"{d.get('easy', {}).get('recall@5', 0):7.1f}% "
              f"{d.get('medium', {}).get('recall@5', 0):7.1f}% "
              f"{d.get('hard', {}).get('recall@5', 0):7.1f}%")

    best = max(results.items(), key=lambda kv: kv[1]["translated"]["overall"]["recall@5"])
    print()
    print(f"  best (translated): {best[1]['label']} "
          f"{best[1]['translated']['overall']['recall@5']}% Recall@5")
    print("  sample translations:")
    for zh, en in list(best[1]["translations"].items())[:8]:
        print(f"    {zh}  ->  {en}")

    doc = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "device": dev,
        "catalogueSize": len(products),
        "queryCount": len(queries),
        "queriesByLanguage": qdoc["counts"]["byLanguage"],
        "metric": "Recall@K and MRR over cosine similarity in the shared image-text space",
        "translationNote": ("Rule-based zh->en fashion glossary. It overlaps with the catalogue "
                            "vocabulary, so the translated numbers are an optimistic lexicon "
                            "baseline rather than an upper bound; the human-paired English "
                            "queries give the ceiling."),
        "models": results,
        "bestTranslated": best[0],
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print(f"\n  wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
