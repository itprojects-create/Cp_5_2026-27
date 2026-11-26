"""
evaluate.py: Computes main evaluation metrics (Accuracy, Precision, Recall, F1, FPR, FNR, Runtime)
across all 4 CryptoFlow models on the held-out test split.
Outputs results to results/main_results.csv.
"""

import csv
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import torch
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader

base_dir = Path(__file__).resolve().parent.parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from models.gnns.generic_gnn import GenericGNN
from models.gnns.crypto_gnn import CryptoGNN
from models.gnns.generic_hgnn import GenericHGNN
from models.gnns.crypto_hgnn import CryptoHGNN

from External_scanner.safe_io import safe_load_graph


def load_test_data(base_path: Path) -> List[Data]:
    stats_csv = base_path / "datasets" / "interproc_stats.csv"
    graphs_dir = base_path / "datasets" / "interproc_graphs"

    if not stats_csv.exists():
        stats_csv = base_path / "datasets" / "dataset_stats.csv"
        graphs_dir = base_path / "datasets" / "graphs"

    test_graphs: List[Data] = []
    if not stats_csv.exists():
        return test_graphs

    with open(stats_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("split", "").lower() == "test":
                gid = row.get("group_id") or row.get("graph_file", "").replace(".pt", "")
                if not gid or gid == "N/A":
                    continue
                fname = f"{gid}.pt" if not gid.endswith(".pt") else gid
                pt_path = graphs_dir / fname
                if pt_path.exists():
                    test_graphs.append(safe_load_graph(str(pt_path)))
    return test_graphs


def evaluate_model(model: torch.nn.Module, test_graphs: List[Data]) -> Dict[str, float]:
    model.eval()
    loader = DataLoader(test_graphs, batch_size=1, shuffle=False)

    tp, tn, fp, fn = 0, 0, 0, 0
    t0 = time.time()

    with torch.no_grad():
        for batch in loader:
            out = model(batch)
            pred = out.argmax(dim=-1).item()
            actual = batch.y.item()

            if pred == 1 and actual == 1:
                tp += 1
            elif pred == 0 and actual == 0:
                tn += 1
            elif pred == 1 and actual == 0:
                fp += 1
            elif pred == 0 and actual == 1:
                fn += 1

    total_time = time.time() - t0
    runtime_per_file = total_time / max(1, len(test_graphs))

    total = tp + tn + fp + fn
    accuracy = (tp + tn) / max(1, total)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = (2 * precision * recall) / max(1e-6, precision + recall)
    fp_rate = fp / max(1, fp + tn)
    fn_rate = fn / max(1, fn + tp)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fp_rate": fp_rate,
        "fn_rate": fn_rate,
        "runtime": runtime_per_file,
    }


def run_main_evaluation():
    test_graphs = load_test_data(base_dir)
    print(f"Loaded {len(test_graphs)} test graphs for evaluation.")

    results_dir = base_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir = base_dir / "models" / "checkpoints"

    models_info = [
        ("GenericGNN", GenericGNN(), checkpoints_dir / "generic_gnn_best.pt"),
        ("CryptoGNN", CryptoGNN(), checkpoints_dir / "crypto_gnn_best.pt"),
        ("GenericHGNN", GenericHGNN(), checkpoints_dir / "generic_hgnn_best.pt"),
        ("CryptoHGNN", CryptoHGNN(), checkpoints_dir / "crypto_hgnn_best.pt"),
    ]

    out_csv = results_dir / "main_results.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["model_name", "accuracy", "precision", "recall", "f1", "fp_rate", "fn_rate", "runtime"])

        for model_name, model, ckpt_path in models_info:
            if ckpt_path.exists():
                try:
                    model.load_state_dict(torch.load(ckpt_path, weights_only=True))
                except Exception as e:
                    print(f"Warning loading checkpoint for {model_name}: {e}")

            metrics = evaluate_model(model, test_graphs)
            print(
                f"{model_name:<12} | Acc: {metrics['accuracy']:.4f} | Prec: {metrics['precision']:.4f} | Rec: {metrics['recall']:.4f} | F1: {metrics['f1']:.4f} | FPR: {metrics['fp_rate']:.4f} | FNR: {metrics['fn_rate']:.4f} | Time: {metrics['runtime']*1000:.2f}ms"
            )
            writer.writerow([
                model_name,
                f"{metrics['accuracy']:.4f}",
                f"{metrics['precision']:.4f}",
                f"{metrics['recall']:.4f}",
                f"{metrics['f1']:.4f}",
                f"{metrics['fp_rate']:.4f}",
                f"{metrics['fn_rate']:.4f}",
                f"{metrics['runtime']:.6f}",
            ])

    print(f"Main evaluation results saved to {out_csv}")


if __name__ == "__main__":
    run_main_evaluation()
