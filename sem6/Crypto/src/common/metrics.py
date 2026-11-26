"""
metrics.py — shared binary classification metrics.

Used identically by all three compared methods (CryptoHGNN, FusionHGNN, CoCa)
so numbers are comparable. Implements the exact formulas in CLAUDE.md §5.
Returns 0.0 (never NaN) when a denominator is zero, and logs a warning.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Sequence

logger = logging.getLogger("common.metrics")


def _safe_div(numerator: float, denominator: float, name: str) -> float:
    if denominator == 0:
        logger.warning("Metric %s has zero denominator; returning 0.0", name)
        return 0.0
    return numerator / denominator


def confusion_counts(y_true: Sequence[int], y_pred: Sequence[int]) -> Dict[str, int]:
    """Binary confusion matrix counts. Positive class = 1 (vulnerable)."""
    tp = tn = fp = fn = 0
    for t, p in zip(y_true, y_pred):
        if p == 1 and t == 1:
            tp += 1
        elif p == 0 and t == 0:
            tn += 1
        elif p == 1 and t == 0:
            fp += 1
        elif p == 0 and t == 1:
            fn += 1
    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn}


def compute_main_metrics(y_true: Sequence[int], y_pred: Sequence[int]) -> Dict[str, float]:
    """Compute accuracy, precision, recall, f1_score, fp_rate, fn_rate per CLAUDE.md §5."""
    c = confusion_counts(y_true, y_pred)
    tp, tn, fp, fn = c["tp"], c["tn"], c["fp"], c["fn"]
    total = tp + tn + fp + fn

    accuracy = _safe_div(tp + tn, total, "accuracy")
    precision = _safe_div(tp, tp + fp, "precision")
    recall = _safe_div(tp, tp + fn, "recall")
    f1_score = _safe_div(2 * precision * recall, precision + recall, "f1_score")
    fp_rate = _safe_div(fp, fp + tn, "fp_rate")
    fn_rate = _safe_div(fn, fn + tp, "fn_rate")

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1_score,
        "fp_rate": fp_rate,
        "fn_rate": fn_rate,
        **{f"n_{k}": v for k, v in c.items()},
    }


def per_cwe_metrics(rows: List[dict]) -> Dict[str, Dict[str, float]]:
    """rows: list of {"cwe": str, "true_label": int, "pred_label": int}.
    Returns per-CWE accuracy/precision/recall/f1 computed with the same
    formulas as compute_main_metrics."""
    by_cwe: Dict[str, List[dict]] = {}
    for r in rows:
        by_cwe.setdefault(r["cwe"], []).append(r)

    out: Dict[str, Dict[str, float]] = {}
    for cwe, items in by_cwe.items():
        y_true = [it["true_label"] for it in items]
        y_pred = [it["pred_label"] for it in items]
        out[cwe] = compute_main_metrics(y_true, y_pred)
        out[cwe]["n_samples"] = len(items)
    return out
