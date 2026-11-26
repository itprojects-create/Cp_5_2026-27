"""
pipeline_runner.py — one shared "mirror CryptoHGNN's pipeline stages" runner,
parameterised by model class + config, used by all three method run.py
entry points (src/pipelines/cryptohgnn/run.py, src/pipelines/fusion_hgnn/
run.py, src/pipelines/coca/run.py) so every method:

  1. loads the Juliet-derived interproc graphs via CryptoHGNN's own loader
     (src/common/data.py -> External_scanner.safe_io.safe_load_graph),
  2. uses the identical pre-assigned train/val/test split and the identical
     seed (src/common/data.SEED),
  3. builds the method's model,
  4. trains with the shared loop in src/common/trainer.py,
  5. runs inference on the test split and saves raw per-sample predictions,
  6. renders the shared HTML report (src/common/html_report.py),

exactly mirroring the stage order documented in
docs/CRYPTOHGNN_PIPELINE_MAP.md.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict

import yaml

from src.common import html_report, metrics as metrics_mod
from src.common.data import SEED, challenge_samples, load_all_samples, set_global_seed, split_samples, to_pyg_list
from src.common.resource_tracking import timed
from src.common.trainer import fit, predict, save_predictions_csv

REPO_ROOT = Path(__file__).resolve().parents[2]
logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
logger = logging.getLogger("common.pipeline_runner")


def load_config(config_path: Path) -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def import_class(dotted_path: str):
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def run_method(config_path: Path, method_key: str, epochs_override: int | None = None) -> Dict[str, Any]:
    """Runs the full pipeline for one method and returns its comparison row.

    method_key: short slug used for file naming, e.g. "cryptohgnn",
    "fusion_hgnn", "coca".
    """
    cfg = load_config(config_path)
    set_global_seed(SEED)

    logger.info("[%s] Stage 1/5 — loading Juliet-derived graphs (CryptoHGNN's loader)", method_key)
    with timed() as t_parse:
        samples = load_all_samples()
        train, val, test = split_samples(samples)
    logger.info(
        "[%s] loaded train=%d val=%d test=%d graphs in %.2fs",
        method_key, len(train), len(val), len(test), t_parse.elapsed,
    )

    challenge = challenge_samples(samples)
    train_g, val_g, test_g = to_pyg_list(train), to_pyg_list(val), to_pyg_list(test)

    logger.info("[%s] Stage 2/5 — building model", method_key)
    model_cfg = cfg["model"]
    arch_cfg = cfg["architecture"]
    model_cls = import_class(model_cfg["class"])
    model = model_cls(**arch_cfg)

    logger.info("[%s] Stage 3/5 — training", method_key)
    train_cfg = cfg["training"]
    epochs = epochs_override if epochs_override is not None else train_cfg["epochs"]
    log_csv = REPO_ROOT / "results" / "tables" / f"{method_key}_training_log.csv"
    checkpoint_path = REPO_ROOT / "models" / "checkpoints" / f"{method_key}_best.pt"

    resource_report = fit(
        model=model,
        train_graphs=train_g,
        val_graphs=val_g,
        epochs=epochs,
        batch_size=train_cfg["batch_size"],
        lr=train_cfg["learning_rate"],
        weight_decay=train_cfg["weight_decay"],
        patience=train_cfg["patience"],
        log_csv_path=log_csv,
        checkpoint_path=checkpoint_path,
    )

    status_csv = REPO_ROOT / "results" / "tables" / f"{method_key}_training_status.csv"
    status = resource_report.status_dict()
    with open(status_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(status))
        writer.writeheader()
        writer.writerow(status)
    if status["diverged"]:
        logger.warning("[%s] training DIVERGED (non-finite val loss); results are not valid.", method_key)

    logger.info("[%s] Stage 4/5 — inference on test split, saving raw predictions", method_key)
    pred_rows, inference_time = predict(model, test)
    resource_report.inference_time_s = inference_time
    resource_report.total_time_s = resource_report.train_time_s + resource_report.inference_time_s

    pred_csv = REPO_ROOT / "results" / "predictions" / f"{method_key}_test_predictions.csv"
    save_predictions_csv(pred_rows, pred_csv)

    y_true = [r["true_label"] for r in pred_rows]
    y_pred = [r["pred_label"] for r in pred_rows]
    main_metrics = metrics_mod.compute_main_metrics(y_true, y_pred)
    per_cwe = metrics_mod.per_cwe_metrics(pred_rows)

    challenge_rows, _ = predict(model, challenge)
    save_predictions_csv(
        challenge_rows, REPO_ROOT / "results" / "predictions" / f"{method_key}_challenge_predictions.csv"
    )
    challenge_metrics = metrics_mod.compute_main_metrics(
        [r["true_label"] for r in challenge_rows], [r["pred_label"] for r in challenge_rows]
    )
    _write_metrics_csv(
        REPO_ROOT / "results" / "tables" / f"{method_key}_challenge_metrics.csv",
        method_key, challenge_metrics, resource_report.to_dict(),
    )

    metrics_csv = REPO_ROOT / "results" / "tables" / f"{method_key}_metrics.csv"
    _write_metrics_csv(metrics_csv, method_key, main_metrics, resource_report.to_dict())

    logger.info("[%s] Stage 5/5 — rendering HTML visualizations", method_key)
    _render_figures(method_key, model_cfg["name"], train, val, test, main_metrics, per_cwe, resource_report.to_dict())

    row = {
        "model": model_cfg["name"],
        **{k: round(v, 4) for k, v in main_metrics.items() if k in (
            "accuracy", "precision", "recall", "f1_score", "fp_rate", "fn_rate"
        )},
        **resource_report.to_dict(),
    }
    logger.info("[%s] done. row=%s", method_key, json.dumps(row))
    return row


def _write_metrics_csv(out_path: Path, method_key: str, main_metrics: Dict[str, float], resources: Dict[str, float]) -> None:
    import csv

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "model", "accuracy", "precision", "recall", "f1_score", "fp_rate", "fn_rate",
        "train_time_s", "inference_time_s", "total_time_s", "peak_memory_mb",
    ]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({
            "model": method_key,
            **{k: round(main_metrics[k], 4) for k in ("accuracy", "precision", "recall", "f1_score", "fp_rate", "fn_rate")},
            **{k: resources.get(k, 0.0) for k in ("train_time_s", "inference_time_s", "total_time_s", "peak_memory_mb")},
        })


def _render_figures(method_key, display_name, train, val, test, main_metrics, per_cwe, resources) -> None:
    from collections import Counter

    out_path = REPO_ROOT / "results" / "figures" / f"{method_key}_report.html"

    def label_counts(ss):
        c = Counter("vulnerable" if s.label == 1 else "not_vulnerable" for s in ss)
        return {"not_vulnerable": c.get("not_vulnerable", 0), "vulnerable": c.get("vulnerable", 0)}

    figs = [
        html_report.class_distribution_figure(label_counts(train), "Train Split"),
        html_report.class_distribution_figure(label_counts(test), "Test Split"),
        html_report.confusion_matrix_figure(
            tp=int(main_metrics["n_tp"]), tn=int(main_metrics["n_tn"]),
            fp=int(main_metrics["n_fp"]), fn=int(main_metrics["n_fn"]),
        ),
        html_report.prediction_results_figure(main_metrics),
        html_report.per_cwe_figure(per_cwe),
        html_report.resource_usage_figure(resources),
    ]
    html_report.render_report(
        out_path,
        title=f"{display_name} — Juliet Scan Report",
        heading=f"{display_name}: Comparative Evaluation Report",
        subtitle=(
            f"Juliet test suite · binary vulnerable/not-vulnerable · "
            f"seed={SEED} · test n={len(test)}"
        ),
        figures=figs,
    )
