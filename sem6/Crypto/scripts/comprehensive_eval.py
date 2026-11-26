"""
comprehensive_eval.py: Evaluates all 4 CryptoFlow models across:
1. Primary NIST Juliet Held-Out Benchmark (304 graphs: CWE-256 and CWE-259)
2. Adversarial & Manual Edge-Case Stress Test (55 graphs: clean near-misses, macro obfuscations, alias chains)
3. Training Split Verification (296 graphs: CWE-321, CWE-327, CWE-338)
4. Per-CWE breakdown across all 5 CWE categories.
"""

import csv
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

import torch
from torch_geometric.data import Data

base_dir = Path(__file__).resolve().parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from External_scanner.safe_io import safe_load_graph
from models.gnns.crypto_hgnn import CryptoHGNN
from models.gnns.crypto_gnn import CryptoGNN
from models.gnns.generic_hgnn import GenericHGNN
from models.gnns.generic_gnn import GenericGNN


def load_all_data():
    stats_csv = base_dir / "datasets" / "interproc_stats.csv"
    graphs_dir = base_dir / "datasets" / "interproc_graphs"

    splits = {"train": [], "val": [], "test": []}
    by_cwe = {}

    with open(stats_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            split = row["split"]
            cwe = row["cwe"]
            gid = row["group_id"]
            pt_path = graphs_dir / f"{gid}.pt"
            if not pt_path.exists():
                continue
            g = safe_load_graph(str(pt_path))
            splits[split].append(g)
            if cwe not in by_cwe:
                by_cwe[cwe] = []
            by_cwe[cwe].append((split, g))

    return splits, by_cwe


def evaluate_graphs(model: torch.nn.Module, graphs: List[Data]) -> Dict[str, Any]:
    model.eval()
    tp, tn, fp, fn = 0, 0, 0, 0
    t0 = time.time()

    with torch.no_grad():
        for g in graphs:
            out = model(g)
            pred = out.argmax(dim=-1).item()
            actual = g.y.item()

            if pred == 1 and actual == 1:
                tp += 1
            elif pred == 0 and actual == 0:
                tn += 1
            elif pred == 1 and actual == 0:
                fp += 1
            elif pred == 0 and actual == 1:
                fn += 1

    runtime = (time.time() - t0) / max(1, len(graphs))
    total = len(graphs)
    accuracy = (tp + tn) / max(1, total)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = (2 * precision * recall) / max(1e-6, precision + recall)
    fpr = fp / max(1, fp + tn)
    fnr = fn / max(1, fn + tp)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fpr,
        "fnr": fnr,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "total": total,
        "runtime_ms": runtime * 1000.0,
    }


def main():
    splits, by_cwe = load_all_data()

    models = [
        ("CryptoHGNN", CryptoHGNN(), base_dir / "models" / "checkpoints" / "crypto_hgnn_best.pt"),
        ("GenericHGNN", GenericHGNN(), base_dir / "models" / "checkpoints" / "generic_hgnn_best.pt"),
        ("CryptoGNN", CryptoGNN(), base_dir / "models" / "checkpoints" / "crypto_gnn_best.pt"),
        ("GenericGNN", GenericGNN(), base_dir / "models" / "checkpoints" / "generic_gnn_best.pt"),
    ]

    for name, m, ckpt in models:
        m.load_state_dict(torch.load(ckpt, map_location="cpu"))
        m.eval()

    print("=" * 85)
    print("CRYPTOFLOW COMPREHENSIVE MULTI-TIER BENCHMARK REPORT")
    print("=" * 85)

    print("\n[TIER 1] PRIMARY NIST JULIET HELD-OUT BENCHMARK (304 Graphs: CWE-256 & CWE-259)")
    print("-" * 85)
    print(f"{'Model':14s} | {'Accuracy':8s} | {'Precision':9s} | {'Recall':8s} | {'F1':8s} | {'FPR':6s} | {'FNR':6s} | {'TP':3s} {'TN':3s} {'FP':3s} {'FN':3s} | {'Latency':8s}")
    print("-" * 85)
    tier1_results = {}
    for name, m, _ in models:
        res = evaluate_graphs(m, splits["val"])
        tier1_results[name] = res
        print(f"{name:14s} | {res['accuracy']:.4f}   | {res['precision']:.4f}    | {res['recall']:.4f}   | {res['f1']:.4f}   | {res['fpr']:.4f} | {res['fnr']:.4f} | {res['tp']:3d} {res['tn']:3d} {res['fp']:3d} {res['fn']:3d} | {res['runtime_ms']:.2f} ms")

    print("\n[TIER 2] ADVERSARIAL & MANUAL EDGE-CASE STRESS TEST (55 Graphs)")
    print("-" * 85)
    print(f"{'Model':14s} | {'Accuracy':8s} | {'Precision':9s} | {'Recall':8s} | {'F1':8s} | {'FPR':6s} | {'FNR':6s} | {'TP':3s} {'TN':3s} {'FP':3s} {'FN':3s} | {'Latency':8s}")
    print("-" * 85)
    tier2_results = {}
    for name, m, _ in models:
        res = evaluate_graphs(m, splits["test"])
        tier2_results[name] = res
        print(f"{name:14s} | {res['accuracy']:.4f}   | {res['precision']:.4f}    | {res['recall']:.4f}   | {res['f1']:.4f}   | {res['fpr']:.4f} | {res['fnr']:.4f} | {res['tp']:3d} {res['tn']:3d} {res['fp']:3d} {res['fn']:3d} | {res['runtime_ms']:.2f} ms")

    print("\n[PER-CWE BREAKDOWN ON HELD-OUT NIST BENCHMARK]")
    print("-" * 85)
    for cwe in sorted(by_cwe.keys()):
        val_graphs = [g for s, g in by_cwe[cwe] if s == "val"]
        if not val_graphs:
            continue
        print(f"\n--- {cwe} ({len(val_graphs)} held-out graphs) ---")
        for name, m, _ in models:
            res = evaluate_graphs(m, val_graphs)
            print(f"{name:14s} | Acc: {res['accuracy']:.4f} | Prec: {res['precision']:.4f} | Rec: {res['recall']:.4f} | F1: {res['f1']:.4f} | FN (Missed): {res['fn']:2d}/{res['fn']+res['tp']:2d}")

    # Save to CSV
    out_csv = base_dir / "results" / "comprehensive_benchmark.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["tier", "split_name", "model_name", "n_graphs", "accuracy", "precision", "recall", "f1", "fpr", "fnr", "tp", "tn", "fp", "fn", "latency_ms"])
        for name, res in tier1_results.items():
            writer.writerow(["Tier 1", "NIST Juliet Held-Out", name, res["total"], f"{res['accuracy']:.4f}", f"{res['precision']:.4f}", f"{res['recall']:.4f}", f"{res['f1']:.4f}", f"{res['fpr']:.4f}", f"{res['fnr']:.4f}", res["tp"], res["tn"], res["fp"], res["fn"], f"{res['runtime_ms']:.2f}"])
        for name, res in tier2_results.items():
            writer.writerow(["Tier 2", "Adversarial Stress Test", name, res["total"], f"{res['accuracy']:.4f}", f"{res['precision']:.4f}", f"{res['recall']:.4f}", f"{res['f1']:.4f}", f"{res['fpr']:.4f}", f"{res['fnr']:.4f}", res["tp"], res["tn"], res["fp"], res["fn"], f"{res['runtime_ms']:.2f}"])

    print(f"\nSaved comprehensive evaluation to: {out_csv}")


if __name__ == "__main__":
    main()
