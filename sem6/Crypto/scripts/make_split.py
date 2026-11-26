"""
make_split.py: Builds the leakage-free train/val/test split used by the
comparative evaluation (CryptoHGNN, FusionHGNN, CoCa).

Reads datasets/juliet_groups.json and datasets/interproc_stats.csv (both
read-only here) and writes data/splits/juliet_grouped_split.csv.

Rules
-----
* Only the assignment of graphs to splits changes. No graph, label, or
  manifest entry is added, removed, or edited.
* The 600 Juliet graphs are split 70/15/15, stratified by CWE.
* Graphs are split as whole "components": two graphs share a component when
  they come from the same Juliet testcase (bad/good pair) or have an
  identical graph hash. A component never straddles two splits, so no test
  graph is a duplicate, or the twin, of a training graph.
* The 55 hand-written cases (manifest context == "full") are not part of
  train/val/test. They are tagged "challenge" and reported separately.

Usage:  python scripts/make_split.py [--seed 42]
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import random
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MANIFEST = BASE_DIR / "datasets" / "juliet_groups.json"
STATS_CSV = BASE_DIR / "datasets" / "interproc_stats.csv"
OUT_CSV = BASE_DIR / "data" / "splits" / "juliet_grouped_split.csv"

RATIOS = {"train": 0.70, "val": 0.15, "test": 0.15}


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b) -> None:
        self.parent[self.find(a)] = self.find(b)


def build_split(seed: int) -> list[dict]:
    groups = json.loads(MANIFEST.read_text(encoding="utf-8"))
    with open(STATS_CSV, "r", encoding="utf-8") as f:
        sha = {r["group_id"]: r["sha256"] for r in csv.DictReader(f)}

    juliet = [g for g in groups if g["context"] != "full"]
    challenge = [g for g in groups if g["context"] == "full"]

    uf = _UnionFind()
    for g in juliet:
        uf.union(("group", g["group_id"]), ("base", g["base_group"]))
        uf.union(("group", g["group_id"]), ("sha", sha[g["group_id"]]))

    components: dict = collections.defaultdict(list)
    for g in juliet:
        components[uf.find(("group", g["group_id"]))].append(g)

    by_cwe: dict = collections.defaultdict(list)
    for members in components.values():
        cwes = {m["cwe"] for m in members}
        if len(cwes) != 1:
            raise RuntimeError(f"Component spans several CWEs: {sorted(cwes)}")
        by_cwe[cwes.pop()].append(members)

    rng = random.Random(seed)
    rows: list[dict] = []
    for cwe in sorted(by_cwe):
        comps = sorted(by_cwe[cwe], key=lambda ms: min(m["group_id"] for m in ms))
        rng.shuffle(comps)
        # Largest components first, so the big ones land where there is room.
        comps.sort(key=len, reverse=True)
        total = sum(len(c) for c in comps)
        filled = {s: 0 for s in RATIOS}
        for comp_index, comp in enumerate(comps):
            # Send the component to the split furthest below its target share.
            split = min(RATIOS, key=lambda s: (filled[s] + len(comp)) / (RATIOS[s] * total))
            filled[split] += len(comp)
            for m in comp:
                rows.append(
                    {
                        "group_id": m["group_id"],
                        "cwe": cwe,
                        "label": m["label"],
                        "split": split,
                        "component": f"{cwe}_{comp_index:03d}",
                    }
                )

    for g in challenge:
        rows.append(
            {
                "group_id": g["group_id"],
                "cwe": g["cwe"],
                "label": g["label"],
                "split": "challenge",
                "component": "manual",
            }
        )
    rows.sort(key=lambda r: r["group_id"])
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rows = build_split(args.seed)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["group_id", "cwe", "label", "split", "component"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT_CSV} (seed={args.seed})")
    table: dict = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        table[r["split"]][(r["cwe"], int(r["label"]))] += 1
    for split in ("train", "val", "test", "challenge"):
        c = table[split]
        n = sum(c.values())
        vuln = sum(v for (_, label), v in c.items() if label == 1)
        per_cwe = collections.Counter()
        for (cwe, _), v in c.items():
            per_cwe[cwe] += v
        print(f"  {split:9s} n={n:3d} vuln={vuln:3d} clean={n - vuln:3d}  {dict(sorted(per_cwe.items()))}")


if __name__ == "__main__":
    main()
