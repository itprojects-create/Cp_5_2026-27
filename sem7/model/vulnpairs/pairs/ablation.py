"""Feature-group ablation with the fix-aware (guard) features. Same folds, model, threshold and metrics as train_eval.

Feature groups: size, node (node-type counts), edge (edge-type counts), ops (operator groups), roles (security-API roles and call totals),
guard (guard_features). Sets compared per family: each group alone, the original set (all but guard), guard alone, all groups,
and all groups minus one group. One seed (42) for the sweep; the 'all' and 'guard' sets are repeated with the five seeds of train_eval.
Metrics: AUC, F1, accuracy, precision, recall at threshold 0.5, pair-ranking accuracy, and pair-ranking accuracy on size-tied pairs
(node counts within 2%), where patch size direction cannot help. 95% intervals resample whole repos (500 resamples, seed 0).
Writes results/pairs/ablation.json and results/tables/ablation.csv
Usage: python -m vulnpairs ablate
"""
import csv
import json
from collections import defaultdict

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from ..features import guard_features
from ..features.graph_features import FEATURES as OLD
from ..paths import RESULTS, TABLES
from .train_eval import FAMS, FOLDS, SEEDS, assign_folds, metrics, rank_acc

B = 500
GROUPS = {
    "size": [c for c in OLD if c in ("nodes", "edges", "log_nodes")],
    "node": [c for c in OLD if c.startswith("n_")],
    "edge": [c for c in OLD if c.startswith("e_")],
    "ops": [c for c in OLD if c.startswith("op_")],
    "roles": [c for c in OLD if c.startswith(("call_", "arg_", "calls_"))],
    "guard": list(guard_features.FEATURES),
}
SETS = {f"only_{g}": [g] for g in GROUPS}
SETS["original"] = [g for g in GROUPS if g != "guard"]
SETS["guard+size"] = ["guard", "size"]
SETS["all"] = list(GROUPS)
SETS.update({f"all_minus_{g}": [x for x in GROUPS if x != g] for g in GROUPS})
REPEATED = ("original", "guard+size", "all", "only_guard")


def table():
    old = {(r["pair_id"], r["side"]): r for r in csv.DictReader(open(RESULTS / "features.csv", encoding="utf-8"))}
    new = {(r["pair_id"], r["side"]): r for r in csv.DictReader(open(RESULTS / "guard_features.csv", encoding="utf-8"))}
    assert old.keys() == new.keys()
    return old, new


def run_set(Xa, ya, fa, seeds):
    P = np.zeros((len(seeds), len(ya)))
    for k in range(FOLDS):
        tr, te = fa != k, fa == k
        for si, seed in enumerate(seeds):
            m = GradientBoostingClassifier(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=seed)
            m.fit(Xa[tr], ya[tr])
            P[si, te] = m.predict_proba(Xa[te])[:, 1]
    return P.mean(axis=0)


def summarise(p, ya, n, tied, idx, repos, rng):
    pt = {**metrics(ya, p), "pair_rank": rank_acc(p[:n], p[n:]), "pair_rank_tied": rank_acc(p[:n][tied], p[n:][tied]) if tied.any() else float("nan")}
    boots = defaultdict(list)
    for _ in range(B):
        js = np.concatenate([idx[repos[q]] for q in rng.integers(0, len(repos), len(repos))])
        both = np.r_[js, js + n]
        if len(set(ya[both])) < 2:
            continue
        for k, v in {**metrics(ya[both], p[both]), "pair_rank": rank_acc(p[js], p[js + n])}.items():
            boots[k].append(v)
    return pt, {k: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k, v in boots.items()}


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    old, new = table()
    out = {"groups": {g: len(c) for g, c in GROUPS.items()}, "families": {}}
    for fam in FAMS:
        pid = sorted({int(k[0]) for k, r in old.items() if fam in r["families"].split("|")})
        repo = {i: old[(str(i), "before")]["repo"] for i in pid}
        fold_of = assign_folds({n: sum(1 for i in pid if repo[i] == n) for n in set(repo.values())})
        n = len(pid)

        def mat(cols):
            rows = []
            for side in ("before", "after"):
                for i in pid:
                    k = (str(i), side)
                    rows.append([float(old[k][c]) if c in old[k] else float(new[k][c]) for c in cols])
            return np.array(rows)

        ya = np.r_[np.ones(n), np.zeros(n)].astype(int)
        fold = np.array([fold_of[repo[i]] for i in pid])
        fa = np.r_[fold, fold]
        nodes = mat(["nodes"])[:, 0]
        tied = np.abs(nodes[:n] - nodes[n:]) <= 0.02 * np.maximum(nodes[:n], nodes[n:])
        size = np.log(nodes)[:, None]
        S = np.zeros(len(ya))
        for k in range(FOLDS):
            tr, te = fa != k, fa == k
            S[te] = LogisticRegression().fit(size[tr], ya[tr]).predict_proba(size[te])[:, 1]
        repos = sorted(set(repo.values()))
        idx = defaultdict(list)
        for j, i in enumerate(pid):
            idx[repo[i]].append(j)
        res = {"pairs": n, "repos": len(repos), "size_tied_pairs": int(tied.sum()), "sets": {}}
        pt, ci = summarise(S, ya, n, tied, idx, repos, np.random.default_rng(0))
        res["sets"]["size_control"] = {"point": pt, "ci95": ci, "seeds": 0}
        for name, groups in SETS.items():
            cols = [c for g in groups for c in GROUPS[g]]
            seeds = SEEDS if name in REPEATED else SEEDS[:1]
            p = run_set(mat(cols), ya, fa, seeds)
            pt, ci = summarise(p, ya, n, tied, idx, repos, np.random.default_rng(0))
            res["sets"][name] = {"point": pt, "ci95": ci, "seeds": len(seeds), "features": len(cols)}
            print(fam, name, {k: round(v, 3) for k, v in pt.items()}, flush=True)
        out["families"][fam] = res
        (RESULTS / "ablation.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    with open(TABLES / "ablation.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["family", "pairs", "set", "seeds", "metric", "value", "lo", "hi"])
        for fam, e in out["families"].items():
            for s, v in e["sets"].items():
                for k, x in v["point"].items():
                    lo, hi = v["ci95"].get(k, [float("nan")] * 2)
                    w.writerow([fam, e["pairs"], s, v["seeds"], k, f"{x:.3f}", f"{lo:.3f}", f"{hi:.3f}"])


if __name__ == "__main__":
    main()
