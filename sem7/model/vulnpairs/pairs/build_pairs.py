"""Builds the patch-pair feature table from the full MegaVul release.

A pair is one vulnerable function (func_before, label 1) and the same function after the fix (func, label 0), from the same commit.
Both sides come from the same project and are nearly the same size, which removes the size and project shortcuts a random clean
function allows. Each graph is turned into a feature vector (graph_features.features); no graph is stored.

Selection (fixed before any model is trained): vulnerable records with graphs for both sides; each side 3-5000 nodes; duplicate
before-versions removed (whitespace-normalised hash); CWE family from the record's CWE tags (families in FAMILIES, a record may belong to
several).
Writes results/pairs/features.csv (one row per graph) and results/pairs/build_report.json.
Usage: python -m vulnpairs build
"""
import ast
import csv
import hashlib
import json
import re
import zipfile
from collections import Counter

from ..features.graph_features import FEATURES, features
from ..paths import DATA, RESULTS

FAMILIES = {
    "memory": {"119", "120", "121", "122", "124", "125", "126", "127", "131", "415", "416", "476", "787", "401", "772", "590", "761", "763", "788"},
    "integer": {"189", "190", "191", "192", "193", "194", "195", "197", "681", "369"},
    "resource": {"400", "770", "834", "835", "674", "789", "1333", "407", "399"},
    "crypto": {"310", "320", "321", "323", "324", "325", "326", "327", "328", "330", "331", "335", "337", "338", "347", "295", "319"},
}
# Exploratory families, defined from CWE availability before any model was run on them (plan/PROTOCOL.md, Part C).
# Used only by `python -m vulnpairs explore`; the four families above are untouched.
EXTRA_FAMILIES = {
    "input_validation": {"20", "1284", "129", "22", "74", "77", "78", "79", "89", "134"},
    "concurrency": {"362", "367", "667", "364", "366", "413"},
    "info_exposure": {"200", "201", "203", "209", "212", "532"},
    "access_control": {"264", "284", "269", "287", "862", "863", "732", "276", "59", "254"},
    "robustness": {"617", "754", "252", "755", "665", "908", "909", "404", "459"},
}


def norm(code: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", code).strip().encode("utf-8")).hexdigest()


def select_pairs(extra=False):
    """Vulnerable records with graphs on both sides, de-duplicated, with a CWE family. Returns (pairs, zipfile, report counter).
    extra=True also tags the exploratory families (EXTRA_FAMILIES) and keeps records that belong only to those."""
    groups = {**FAMILIES, **(EXTRA_FAMILIES if extra else {})}
    data = json.load(open(DATA / "megavul_simple.json", encoding="utf-8"))
    zf = zipfile.ZipFile(DATA / "megavul_graph.zip")
    names = set(zf.namelist())
    seen, pairs, rep = set(), [], Counter()
    for x in data:
        if str(x["is_vul"]).lower() != "true":
            continue
        rep["vulnerable_records"] += 1
        pb, pa = x["func_graph_path_before"], x["func_graph_path"]
        if pb in (None, "None") or pa in (None, "None") or pb not in names or pa not in names:
            rep["no_graph_pair"] += 1
            continue
        h = norm(x["func_before"])
        if h in seen:
            rep["duplicate_before"] += 1
            continue
        seen.add(h)
        cw = x["cwe_ids"]
        cw = ast.literal_eval(cw) if isinstance(cw, str) else cw
        ids = {c.replace("CWE-", "") for c in cw}
        fam = [k for k, s in groups.items() if ids & s]
        if not fam:
            rep["no_family"] += 1
            continue
        pairs.append((x, pb, pa, fam, sorted(ids)))
    return pairs, zf, rep


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    pairs, zf, rep = select_pairs()
    print("candidate pairs", len(pairs), dict(rep), flush=True)
    cols = ["pair_id", "side", "label", "repo", "families", "cwe"] + FEATURES
    kept, fam_n = 0, Counter()
    with open(RESULTS / "features.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for i, (x, pb, pa, fam, ids) in enumerate(pairs):
            gb, ga = json.loads(zf.read(pb)), json.loads(zf.read(pa))
            if not (3 <= len(gb["nodes"]) <= 5000 and 3 <= len(ga["nodes"]) <= 5000):
                rep["size_filter"] += 1
                continue
            for side, label, g in (("before", 1, gb), ("after", 0, ga)):
                f = features(g)
                w.writerow([kept, side, label, pb.split("/")[0], "|".join(fam), "|".join(ids)] + [f[c] for c in FEATURES])
            kept += 1
            for k in fam:
                fam_n[k] += 1
            if i % 1000 == 0:
                print(i, kept, flush=True)
    rep["pairs_kept"] = kept
    rep["per_family_pairs"] = dict(fam_n)
    (RESULTS / "build_report.json").write_text(json.dumps(dict(rep), indent=1), encoding="utf-8")
    print(json.dumps(dict(rep)))


if __name__ == "__main__":
    main()
