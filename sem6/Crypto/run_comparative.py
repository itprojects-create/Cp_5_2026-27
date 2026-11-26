#!/usr/bin/env python3
"""
run_comparative.py — top-level runner executing all three methods in
sequence and producing results/tables/comparison.csv, per CLAUDE.md Phase 2
("Add one top-level runner that executes all methods in sequence").

Usage:
    python run_comparative.py [--epochs N]

A fresh run with the same --epochs value and the fixed seed
(src/common/data.SEED) reproduces the same numbers (acceptance checklist
item: "A fresh run of the top-level runner reproduces the same numbers").
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from glob import glob
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.pipeline_runner import run_method  # noqa: E402

COMPARISON_COLUMNS = [
    "model", "accuracy", "precision", "recall", "f1_score", "fp_rate", "fn_rate",
    "train_time_s", "inference_time_s", "total_time_s", "peak_memory_mb",
]


def create_pipeline(paper_pdf: str) -> Dict[str, Any]:
    """Maps a COMPARISON_PAPER/*.pdf to its method config + key, per
    CLAUDE.md's illustrative execution() sketch. Method identification was
    done by reading the PDFs in docs/papers/."""
    name = Path(paper_pdf).stem.lower()
    if "coca" in name:
        return {"method_key": "coca", "config": REPO_ROOT / "configs" / "coca_config.yaml"}
    # Base_paper.pdf -> "A Novel Method for Vulnerability Detection Based on
    # Fusion and Hyperbolic Neural Network Graphs" (FusionHGNN baseline).
    return {"method_key": "fusion_hgnn", "config": REPO_ROOT / "configs" / "fusion_hgnn_config.yaml"}


def generate_results(pipeline: Dict[str, Any], epochs_override: int | None) -> Dict[str, Any]:
    return run_method(pipeline["config"], method_key=pipeline["method_key"], epochs_override=epochs_override)


def evaluate(results: List[Dict[str, Any]], cryptohgnn_row: Dict[str, Any]) -> Path:
    all_rows = [cryptohgnn_row] + results
    out_path = REPO_ROOT / "results" / "tables" / "comparison.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COMPARISON_COLUMNS)
        writer.writeheader()
        for row in all_rows:
            writer.writerow({k: row.get(k, "") for k in COMPARISON_COLUMNS})
    return out_path


def execution(params: Dict[str, Any]) -> Path:
    """Mirrors the execution() sketch in CLAUDE.md Phase 2 verbatim in
    structure (papers -> pipelines -> results -> evaluate), extended with
    the CryptoHGNN baseline row and real config/epoch wiring."""
    papers = sorted(glob(str(REPO_ROOT / "COMPARISON_PAPER" / "*.pdf")))
    pipelines = [create_pipeline(p) for p in papers]

    epochs_override = params.get("epochs")

    t0 = time.time()
    print("=== Stage 1/3 — CryptoHGNN baseline (read-only reuse, re-run for fresh predictions) ===")
    from src.pipelines.cryptohgnn.run import main as _unused  # ensure module importable; not invoked directly
    from src.common.pipeline_runner import load_config

    cryptohgnn_cfg_path = REPO_ROOT / "configs" / "cryptohgnn_config.yaml"
    import yaml

    cfg = load_config(cryptohgnn_cfg_path)
    cfg["architecture"]["num_classes"] = 2  # binary comparison override; file on disk untouched
    patched_path = REPO_ROOT / "configs" / "_cryptohgnn_binary_runtime.yaml"
    with open(patched_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f)
    cryptohgnn_row = run_method(patched_path, method_key="cryptohgnn", epochs_override=epochs_override)

    print("=== Stage 2/3 — FusionHGNN + CoCa pipelines ===")
    results = [generate_results(pl, epochs_override) for pl in pipelines]

    print("=== Stage 3/3 — Evaluation / comparison.csv ===")
    out_path = evaluate(results, cryptohgnn_row)
    print(f"Comparison table written to {out_path} (total wall time {time.time() - t0:.1f}s)")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CryptoHGNN + FusionHGNN + CoCa and produce comparison.csv")
    parser.add_argument("--epochs", type=int, default=None, help="Override all methods' training epochs.")
    args = parser.parse_args()
    execution({"epochs": args.epochs})


if __name__ == "__main__":
    main()
