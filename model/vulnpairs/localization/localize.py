"""Statement-level localisation: given a function known to be vulnerable, rank its lines by how likely each is a vulnerable line.

Labels: a line of func_before is positive when the fix deleted or changed it (diff_line_info.deleted_lines, whitespace-normalised).
Only functions with at least one such line are used. Candidate lines are all lines except blank, brace-only and comment-only lines
(the same candidates for every method and for the random baseline). The task is ranking inside one function, so function size, project
and patch direction cannot help.

Labels use the unified diff positions: lines the fix removed or rewrote ("changed"); for fixes that only insert code, the line that follows
the inserted block ("add_only"). Methods compared (all fixed before running, no tuning on test folds):
  random        analytic expectation for a random order of the candidate lines
  rule          catalogue rule: lines with a security-API call first, then lines with more calls
  token_lr      logistic regression on hashed line tokens
  hand_hgb      gradient boosting on hand-made counts of the line and its neighbours, including "identifiers never checked earlier"
  full          gradient boosting on the hand-made counts plus the out-of-fold token_lr score
Metrics per function: hit@1, hit@3, hit@5 (a true line among the top n), MRR of the first true line; line-level precision, recall, F1
and accuracy when the top 5 lines of every function are flagged. 95% intervals resample whole repos (1,000 resamples, seed 0).
Project-grouped 5-fold CV as in train_eval.
Writes results/localize/results.json and results/tables/localize_results.csv
Usage: python -m vulnpairs localize
"""
import ast
import csv
import json
import re
from collections import Counter, defaultdict

import numpy as np
import scipy.sparse as sp
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import LogisticRegression

from ..pairs.build_pairs import EXTRA_FAMILIES, select_pairs
from ..features.catalogue import lookup
from ..paths import RESULTS, TABLES
from ..pairs.train_eval import FAMS, FOLDS, assign_folds

OUT = RESULTS.parent / "localize"
B, TOP = 1000, 5
IDENT = re.compile(r"[A-Za-z_]\w*")
CALL = re.compile(r"([A-Za-z_]\w*)\s*\(")
KEYWORDS = {"if", "while", "for", "switch", "return", "sizeof", "else", "do", "case"}
TYPE_WORDS = {"int", "char", "short", "long", "unsigned", "signed", "void", "float", "double", "const", "static", "struct", "size_t", "ssize_t",
              "uint8_t", "uint16_t", "uint32_t", "uint64_t", "int8_t", "int16_t", "int32_t", "int64_t", "bool", "NULL", "true", "false", "else",
              "break", "continue", "goto", "default"}
COND_START = re.compile(r"\s*(\}\s*else\s+)?(if|while|for|switch)\b")
DECL = re.compile(r"\s*(const\s+|static\s+|unsigned\s+|struct\s+)*[A-Za-z_]\w*[\s\*]+[A-Za-z_]\w*\s*(=|;|\[)")
CAST = re.compile(r"\(\s*(unsigned|signed|int|long|char|short|size_t|u?int\d+_t|void)\b[^)]*\)\s*\w")
ARITH = re.compile(r"[+\-*/%]|<<|>>")
COMPARE = re.compile(r"<=|>=|==|!=|<|>")
ASSIGN = re.compile(r"(?<![=!<>])=(?!=)")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def candidate(line: str) -> bool:
    t = line.strip()
    return bool(re.sub(r"[{}\s;]", "", t)) and not t.startswith(("//", "/*", "*", "#"))


def hand(line: str, i: int, n: int, depth: int) -> list:
    calls = [c for c in CALL.findall(line) if c not in KEYWORDS]
    roles = [(lookup(c) or (None,))[0] for c in calls]
    crypto = sum(1 for r in roles if r and r.startswith("crypto"))
    s = line.strip()
    return [i / max(n - 1, 1), len(s), depth, roles.count("alloc"), roles.count("free"), roles.count("copy"), roles.count("format"),
            roles.count("input"), crypto, len(calls), s.count("["), s.count("*"), s.count("->") + s.count("."),
            len(ARITH.findall(s)), len(COMPARE.findall(s)), s.count("&&") + s.count("||") + s.count("!"),
            1 if ASSIGN.search(s) else 0, 1 if s.startswith("if") or s.startswith("} else if") else 0,
            1 if re.match(r"(for|while|do)\b", s) else 0, 1 if s.startswith("return") else 0, 1 if s.startswith("goto") or " goto " in s else 0,
            len(re.findall(r"\b\d+\b|\"", s)), len(CAST.findall(s)), s.count("sizeof"), 1 if re.match(r"[\w\s]+\*\s*\w+\s*(=|;)", s) else 0]


def extra_rows(lines: list) -> np.ndarray:
    """Per-line counts about identifiers and earlier checks (one row per line of the whole function)."""
    cond_idx = [i for i, l in enumerate(lines) if COND_START.match(l) or "?" in l or "assert" in l]
    cond_set = set(cond_idx)
    seen, cond_ids, rows = set(), set(), []
    for i, l in enumerate(lines):
        calls = set(CALL.findall(l))
        ids = set(IDENT.findall(l)) - calls - TYPE_WORDS - KEYWORDS
        prev_c = [j for j in cond_idx if j < i]
        next_c = [j for j in cond_idx if j > i]
        rows.append([len(ids), len(ids - cond_ids), len(ids & cond_ids), len(ids - seen),
                     1 if DECL.match(l) and not l.strip().startswith("return") else 0,
                     min(i - prev_c[-1], 50) if prev_c else 50, min(next_c[0] - i, 50) if next_c else 50, 1 if i in cond_set else 0])
        seen |= ids
        if i in cond_set:
            cond_ids |= ids
    return np.array(rows, dtype=float)


HUNK = re.compile(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@")


def parse_diff(diff: str):
    """Unified diff of func_before -> func_after. Returns (deleted, anchors): 0-based line indices of func_before.
    deleted = lines the fix removed or rewrote; anchors = for a pure insertion, the line that follows the inserted block."""
    deleted, anchors, bl, pending = [], [], 0, False
    for ln in diff.split("\n"):
        if ln.startswith("---") or ln.startswith("+++"):
            continue
        m = HUNK.match(ln)
        if m:
            bl, pending = int(m.group(1)), False
        elif ln.startswith("-"):
            deleted.append(bl - 1)
            bl, pending = bl + 1, False
        elif ln.startswith("+"):
            pending = True
        else:
            if pending:
                anchors.append(bl - 1)
            bl, pending = bl + 1, False
    return deleted, anchors


def build(extra=False):
    pairs, _, _ = select_pairs(extra)
    funcs, stat = [], Counter()
    for x, pb, pa, fam, ids in pairs:
        stat["pairs"] += 1
        lines = x["func_before"].split("\n")
        deleted, anchors = parse_diff(x.get("diff_func") or "")
        keep = [i for i, l in enumerate(lines) if candidate(l)]
        where = {i: j for j, i in enumerate(keep)}

        def to_candidate(i):
            """Index in keep of line i, or of the next candidate line after it (the previous one when none follows)."""
            if i in where:
                return where[i]
            after = [j for j, k in enumerate(keep) if k > i]
            return after[0] if after else (len(keep) - 1 if keep else None)

        marks = {to_candidate(i) for i in deleted if 0 <= i < len(lines)}
        stratum = "changed"
        if not marks - {None}:
            marks = {to_candidate(i) for i in anchors if 0 <= i < len(lines)}
            stratum = "add_only"
        marks -= {None}
        pos = [j in marks for j in range(len(keep))]
        if not marks or len(keep) < 4 or len(keep) > 600:
            stat["unusable"] += 1
            continue
        stat[stratum] += 1
        depth, rows = 0, []
        for i, l in enumerate(lines):
            if l.strip().startswith("}"):
                depth = max(depth - l.count("}"), 0)
            rows.append(hand(l, i, len(lines), depth))
            depth = max(depth + l.count("{") - (0 if l.strip().startswith("}") else l.count("}")), 0)
        h = np.hstack([np.array(rows, dtype=float), extra_rows(lines)])[keep]
        funcs.append({"repo": pb.split("/")[0], "families": fam, "lines": [lines[i].strip() for i in keep], "y": np.array(pos, dtype=int), "hand": h,
                      "stratum": stratum})
        stat["kept"] += 1
    return funcs, stat


def neighbours(h):
    prev, nxt = np.vstack([np.zeros((1, h.shape[1])), h[:-1]]), np.vstack([h[1:], np.zeros((1, h.shape[1]))])
    return np.hstack([h, prev, nxt])


def hit_random(L, k, n):
    n = min(n, L)
    return 1.0 - np.prod([(L - k - j) / (L - j) for j in range(n)]) if L - k >= n else 1.0


def random_ifa(L, k):
    """Expected number of non-vulnerable lines inspected before the first true line under a random order."""
    return (L - k) / (k + 1)


def line_type(line: str) -> str:
    """Coarse kind of the first labelled line, for the error analysis."""
    s = line.strip()
    if COND_START.match(s) or "?" in s:
        return "condition"
    if any(c not in KEYWORDS for c in CALL.findall(s)):
        return "call"
    if ASSIGN.search(s) or DECL.match(s):
        return "assignment_or_declaration"
    return "other"


def random_mrr(L, k):
    """Expected 1/rank of the first true line when the L lines are ordered at random and k of them are true."""
    total, none_before = 0.0, 1.0
    for j in range(1, L - k + 2):
        total += (1.0 / j) * none_before * k / (L - j + 1)
        none_before *= (L - k - (j - 1)) / (L - (j - 1))
    return total


def per_function(score, y):
    order = np.argsort(-score, kind="stable")
    first = int(np.where(y[order] == 1)[0][0]) + 1
    return {"hit1": float(first <= 1), "hit3": float(first <= 3), "hit5": float(first <= 5), "hit10": float(first <= 10), "mrr": 1.0 / first,
            "ifa": float(first - 1), "tp": int(y[order][:TOP].sum()), "flag": min(TOP, len(y)), "pos": int(y.sum()), "n": len(y)}


def summarise(recs, rnd):
    tp, flag, pos, n = (sum(r[k] for r in recs) for k in ("tp", "flag", "pos", "n"))
    fn = pos - tp
    tn = n - flag - fn
    prec, rec = tp / flag if flag else 0.0, tp / pos if pos else 0.0
    out = {k: float(np.mean([r[k] for r in recs])) for k in ("hit1", "hit3", "hit5", "hit10", "mrr", "ifa")}
    out.update({"precision": prec, "recall": rec, "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0, "accuracy": (tp + tn) / n})
    out.update({f"random_{k}": float(np.mean([r[k] for r in rnd])) for k in ("hit1", "hit3", "hit5", "hit10", "mrr", "ifa")})
    return out


def fit_token_lr(X, y):
    return LogisticRegression(C=0.5, max_iter=100, class_weight="balanced").fit(X, y)


def main(extra=False) -> None:
    """extra=False: the four main families -> results.json. extra=True: the exploratory families -> results_extra.json."""
    OUT.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    fams = list(EXTRA_FAMILIES) if extra else FAMS
    out_json, out_csv = ("results_extra.json", "localize_extra.csv") if extra else ("results.json", "localize_results.csv")
    funcs, stat = build(extra)
    print(dict(stat), flush=True)
    hv = HashingVectorizer(n_features=2 ** 16, token_pattern=r"[A-Za-z_]\w*|[^\sA-Za-z_0-9]{1,2}", alternate_sign=False, norm="l2", lowercase=False)
    res = {"stats": dict(stat), "families": {}}
    methods = ["rule", "token_lr", "hand_hgb", "full", "full_no_extra", "full_no_context"]
    NH, NE = 25, 8
    cols_all = np.arange(3 * (NH + NE))
    cols_no_extra = np.array([c for c in cols_all if c % (NH + NE) < NH])
    cols_no_context = np.arange(NH + NE)
    hgb = dict(max_iter=200, learning_rate=0.05, max_depth=4, class_weight="balanced", random_state=42)
    for fam in fams:
        fs = [f for f in funcs if fam in f["families"]]
        repos = sorted({f["repo"] for f in fs})
        fold_of = assign_folds(Counter(f["repo"] for f in fs))
        fold = np.array([fold_of[f["repo"]] for f in fs])
        inner_of = {r: j % 3 for j, r in enumerate(repos)}
        feats = [neighbours(f["hand"]) for f in fs]
        tok = [hv.transform(f["lines"]) for f in fs]
        score = {m: [None] * len(fs) for m in methods}
        for k in range(FOLDS):
            tr = [i for i in range(len(fs)) if fold[i] != k]
            te = [i for i in range(len(fs)) if fold[i] == k]
            ytr = np.concatenate([fs[i]["y"] for i in tr])
            Ttr = sp.vstack([tok[i] for i in tr]).tocsr()
            grp = np.concatenate([np.full(len(fs[i]["y"]), inner_of[fs[i]["repo"]]) for i in tr])
            oof = np.zeros(len(ytr))
            for g in range(3):
                oof[grp == g] = fit_token_lr(Ttr[grp != g], ytr[grp != g]).decision_function(Ttr[grp == g])
            lr = fit_token_lr(Ttr, ytr)
            Ftr = np.vstack([feats[i] for i in tr])
            m_hand = HistGradientBoostingClassifier(**hgb).fit(Ftr, ytr)
            m_full = HistGradientBoostingClassifier(**hgb).fit(np.hstack([Ftr, oof[:, None]]), ytr)
            m_noex = HistGradientBoostingClassifier(**hgb).fit(np.hstack([Ftr[:, cols_no_extra], oof[:, None]]), ytr)
            m_noctx = HistGradientBoostingClassifier(**hgb).fit(np.hstack([Ftr[:, cols_no_context], oof[:, None]]), ytr)
            for i in te:
                t = lr.decision_function(tok[i])
                score["token_lr"][i] = t
                score["hand_hgb"][i] = m_hand.decision_function(feats[i])
                score["full"][i] = m_full.decision_function(np.hstack([feats[i], t[:, None]]))
                score["full_no_extra"][i] = m_noex.decision_function(np.hstack([feats[i][:, cols_no_extra], t[:, None]]))
                score["full_no_context"][i] = m_noctx.decision_function(np.hstack([feats[i][:, cols_no_context], t[:, None]]))
            print(fam, "fold", k, flush=True)
        for i, f in enumerate(fs):
            score["rule"][i] = f["hand"][:, 3:9].sum(axis=1) + 1e-3 * f["hand"][:, 9]
        recs = {m: [per_function(score[m][i], fs[i]["y"]) for i in range(len(fs))] for m in methods}
        rnd = [{**{k: hit_random(r["n"], r["pos"], n) for k, n in (("hit1", 1), ("hit3", 3), ("hit5", 5), ("hit10", 10))},
                "mrr": random_mrr(r["n"], r["pos"]), "ifa": random_ifa(r["n"], r["pos"])} for r in recs["full"]]
        idx = defaultdict(list)
        for i, f in enumerate(fs):
            idx[f["repo"]].append(i)
        rng = np.random.default_rng(0)
        boots = {m: defaultdict(list) for m in methods}
        for _ in range(B):
            js = np.concatenate([idx[repos[q]] for q in rng.integers(0, len(repos), len(repos))])
            for m in methods:
                for k, v in summarise([recs[m][j] for j in js], [rnd[j] for j in js]).items():
                    boots[m][k].append(v)
        out = {"functions": len(fs), "repos": len(repos), "mean_lines": float(np.mean([len(f["y"]) for f in fs])),
               "mean_true_lines": float(np.mean([f["y"].sum() for f in fs])), "methods": {}}
        for m in methods:
            out["methods"][m] = {"point": summarise(recs[m], rnd),
                                 "ci95": {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in boots[m].items()}}
        out["strata"] = {st: {m: summarise([recs[m][i] for i in range(len(fs)) if fs[i]["stratum"] == st],
                                           [rnd[i] for i in range(len(fs)) if fs[i]["stratum"] == st]) for m in ("rule", "full")}
                         for st in ("changed", "add_only")}
        out["strata_counts"] = {st: sum(1 for f in fs if f["stratum"] == st) for st in ("changed", "add_only")}
        by_type = defaultdict(list)
        for i, f in enumerate(fs):
            by_type[line_type(f["lines"][int(np.argmax(f["y"]))])].append(i)
        out["by_line_type"] = {t: {"functions": len(ix), **summarise([recs["full"][i] for i in ix], [rnd[i] for i in ix])} for t, ix in by_type.items()}
        res["families"][fam] = out
        print(fam, len(fs), "functions, mean lines", round(out["mean_lines"], 1), "| random hit5", round(out["methods"]["full"]["point"]["random_hit5"], 3), flush=True)
        for m in methods:
            print("  ", m, {k: round(v, 3) for k, v in out["methods"][m]["point"].items() if not k.startswith("random")}, flush=True)
        (OUT / out_json).write_text(json.dumps(res, indent=1), encoding="utf-8")
    with open(TABLES / out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["family", "functions", "repos", "method", "metric", "value", "lo", "hi"])
        for fam, e in res["families"].items():
            for m, v in e["methods"].items():
                for k, x in v["point"].items():
                    lo, hi = v["ci95"].get(k, [float("nan")] * 2)
                    w.writerow([fam, e["functions"], e["repos"], m, k, f"{x:.3f}", f"{lo:.3f}", f"{hi:.3f}"])
            r = e["methods"]["full"]["point"]
            for st, v in e["strata"].items():
                for m, pt in v.items():
                    for k, x in pt.items():
                        w.writerow([fam, e["strata_counts"][st], "", f"{m}@{st}", k, f"{x:.3f}", "", ""])
            for tname, v in e["by_line_type"].items():
                for k, x in v.items():
                    w.writerow([fam, v["functions"], "", f"full@first_label_{tname}", k, f"{x:.3f}", "", ""])
            for k in ("hit1", "hit3", "hit5", "hit10", "mrr", "ifa"):
                w.writerow([fam, e["functions"], e["repos"], "random", k, f"{r['random_' + k]:.3f}", "", ""])


if __name__ == "__main__":
    main()
