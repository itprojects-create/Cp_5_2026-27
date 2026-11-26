"""Builds the fix-aware (guard) feature table for the same pairs, in the same order, as build_pairs.

Writes results/pairs/guard_features.csv (pair_id, side, then guard_features.FEATURES). pair_id values match results/pairs/features.csv.
Usage: python -m vulnpairs guard [limit]
"""
import csv
import json
import sys
import time

from .build_pairs import select_pairs
from ..features.guard_features import FEATURES, guard_features
from ..paths import RESULTS


def main(limit: int = 0) -> None:
    pairs, zf, _ = select_pairs()
    kept, t0 = 0, time.time()
    with open(RESULTS / "guard_features.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["pair_id", "side"] + FEATURES)
        for i, (x, pb, pa, fam, ids) in enumerate(pairs):
            gb, ga = json.loads(zf.read(pb)), json.loads(zf.read(pa))
            if not (3 <= len(gb["nodes"]) <= 5000 and 3 <= len(ga["nodes"]) <= 5000):
                continue
            for side, g in (("before", gb), ("after", ga)):
                f = guard_features(g)
                w.writerow([kept, side] + [f[c] for c in FEATURES])
            kept += 1
            if kept % 200 == 0:
                print(kept, round(time.time() - t0), "s", flush=True)
            if limit and kept >= limit:
                break
    print("pairs", kept)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
