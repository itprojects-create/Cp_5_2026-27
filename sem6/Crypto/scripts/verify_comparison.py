#!/usr/bin/env python3
"""
verify_comparison.py — acceptance-checklist helper: recompute metrics from
results/predictions/<method>_test_predictions.csv and confirm they match
results/tables/comparison.csv exactly (CLAUDE.md acceptance checklist:
"Metrics are recomputed from the saved prediction files and match the CSV").
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common import metrics as metrics_mod

METHOD_KEY_TO_MODEL = {"cryptohgnn": "CryptoHGNN", "fusion_hgnn": "FusionHGNN", "coca": "Coca"}


def main() -> int:
    comparison_path = REPO_ROOT / "results" / "tables" / "comparison.csv"
    with open(comparison_path, newline="", encoding="utf-8") as f:
        comparison_rows = {row["model"]: row for row in csv.DictReader(f)}

    ok = True
    for method_key, model_name in METHOD_KEY_TO_MODEL.items():
        pred_path = REPO_ROOT / "results" / "predictions" / f"{method_key}_test_predictions.csv"
        with open(pred_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        y_true = [int(r["true_label"]) for r in rows]
        y_pred = [int(r["pred_label"]) for r in rows]
        recomputed = metrics_mod.compute_main_metrics(y_true, y_pred)

        row = comparison_rows.get(model_name)
        if row is None:
            print(f"[FAIL] {model_name}: no row in comparison.csv")
            ok = False
            continue

        for key in ("accuracy", "precision", "recall", "f1_score", "fp_rate", "fn_rate"):
            expected = round(recomputed[key], 4)
            actual = round(float(row[key]), 4)
            if abs(expected - actual) > 1e-4:
                print(f"[FAIL] {model_name}.{key}: recomputed={expected} csv={actual}")
                ok = False
        print(f"[OK]   {model_name}: {len(rows)} predictions match comparison.csv")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
