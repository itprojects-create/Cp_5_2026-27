"""Per-family patch-pair study. Fixed in advance (nothing is tuned on these results):
- folds: project (repo) groups, balanced by pair count, seed 42; a pair's two sides are always in the same fold; fold k = test, rest = train
- model: gradient boosting (sklearn GradientBoostingClassifier: 300 trees, depth 3, learning rate 0.05, subsample 0.8), seeds 42-46
- decision threshold 0.5 on the predicted probability; scores are averaged over the five seeds
- metrics on all out-of-fold graphs of the family: accuracy, precision, recall, F1, AUC; pair-ranking accuracy = share of pairs whose vulnerable
  version scores above its own fixed version (ties count half); 95% intervals resample whole repos (1,000 resamples, seed 0)
- control: logistic regression on log(node count) only, same folds
Writes results/pairs/results.json and results/tables/pairs_results.csv
Usage: python -m vulnpairs train
"""
import csv
import json
import random
from collections import defaultdict

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from ..features.graph_features import FEATURES
from ..paths import RESULTS, TABLES

SEEDS, FOLDS, B, THR = [42, 43, 44, 45, 46], 5, 1000, 0.5
FAMS = ["memory", "integer", "resource", "crypto"]


def load():
    rows = list(csv.DictReader(open(RESULTS / "features.csv", encoding="utf-8")))
    return rows


def metrics(y, p, thr=THR):
    pred = (p > thr).astype(int)
    tp, fp = int(((pred == 1) & (y == 1)).sum()), int(((pred == 1) & (y == 0)).sum())
    fn, tn = int(((pred == 0) & (y == 1)).sum()), int(((pred == 0) & (y == 0)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {"accuracy": (tp + tn) / len(y), "precision": prec, "recall": rec, "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
            "auc": float(roc_auc_score(y, p)) if len(set(y)) == 2 else float("nan")}


def rank_acc(sb, sa):
    return float(((sb > sa) + 0.5 * (sb == sa)).mean())


def assign_folds(count):
    names = sorted(count)
    random.Random(42).shuffle(names)
    names.sort(key=lambda n: -count[n])
    load_, fold = [0] * FOLDS, {}
    for n in names:
        k = min(range(FOLDS), key=lambda i: (load_[i], i))
        fold[n] = k
        load_[k] += count[n]
    return fold


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    rows = load()
    res = {"settings": {"seeds": SEEDS, "folds": FOLDS, "threshold": THR, "bootstrap": B}, "families": {}}
    for fam in FAMS:
        sel = [r for r in rows if fam in r["families"].split("|")]
        pid = sorted({int(r["pair_id"]) for r in sel})
        row_of = defaultdict(dict)
        for r in sel:
            row_of[int(r["pair_id"])][r["side"]] = r
        repo = {i: row_of[i]["before"]["repo"] for i in pid}
        fold_of = assign_folds({n: sum(1 for i in pid if repo[i] == n) for n in set(repo.values())})
        X = {s: np.array([[float(row_of[i][s][c]) for c in FEATURES] for i in pid]) for s in ("before", "after")}
        Xa = np.vstack([X["before"], X["after"]])
        ya = np.r_[np.ones(len(pid)), np.zeros(len(pid))].astype(int)
        fold = np.array([fold_of[repo[i]] for i in pid])
        fa = np.r_[fold, fold]
        size = np.log(Xa[:, FEATURES.index("nodes")])[:, None]
        P = np.zeros((len(SEEDS), len(ya)))
        imp = np.zeros(len(FEATURES))
        S = np.zeros(len(ya))
        for k in range(FOLDS):
            tr, te = fa != k, fa == k
            S[te] = LogisticRegression().fit(size[tr], ya[tr]).predict_proba(size[te])[:, 1]
            for si, seed in enumerate(SEEDS):
                m = GradientBoostingClassifier(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=seed)
                m.fit(Xa[tr], ya[tr])
                P[si, te] = m.predict_proba(Xa[te])[:, 1]
                imp += m.feature_importances_ / (FOLDS * len(SEEDS))
        p = P.mean(axis=0)
        n = len(pid)
        pt = {"model": {**metrics(ya, p), "pair_rank": rank_acc(p[:n], p[n:])}, "size_only": {**metrics(ya, S), "pair_rank": rank_acc(S[:n], S[n:])}}
        repos = sorted(set(repo.values()))
        idx = defaultdict(list)
        for j, i in enumerate(pid):
            idx[repo[i]].append(j)
        rng = np.random.default_rng(0)
        boots = {m: defaultdict(list) for m in pt}
        for _ in range(B):
            js = np.concatenate([idx[repos[q]] for q in rng.integers(0, len(repos), len(repos))])
            both = np.r_[js, js + n]
            for name, sc in (("model", p), ("size_only", S)):
                if len(set(ya[both])) < 2:
                    continue
                for k_, v in {**metrics(ya[both], sc[both]), "pair_rank": rank_acc(sc[js], sc[js + n])}.items():
                    boots[name][k_].append(v)
        ci = {m: {k_: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k_, v in boots[m].items()} for m in boots}
        top = sorted(zip(FEATURES, imp), key=lambda t: -t[1])[:8]
        res["families"][fam] = {"pairs": n, "repos": len(repos), "point": pt, "ci95": ci, "top_features": [[a, float(b)] for a, b in top]}
        print(fam, n, "pairs", len(repos), "repos | model", {k_: round(v, 3) for k_, v in pt["model"].items()}, "| size-only rank", round(pt["size_only"]["pair_rank"], 3), flush=True)
    (RESULTS / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    with open(TABLES / "pairs_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["family", "pairs", "repos", "model", "metric", "value", "lo", "hi"])
        for fam, e in res["families"].items():
            for m in ("model", "size_only"):
                for k_, v in e["point"][m].items():
                    w.writerow([fam, e["pairs"], e["repos"], m, k_, f"{v:.3f}", f"{e['ci95'][m][k_][0]:.3f}", f"{e['ci95'][m][k_][1]:.3f}"])


if __name__ == "__main__":
    main()
