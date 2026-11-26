"""
ablation_study.py: Evaluates 7 ablation configurations of CryptoFlow to isolate the impact
of each architectural component (macros, wrappers, crypto semantics, interprocedural flow, HGNN vs GNN).
Outputs results to results/ablation_study.csv.
"""

import csv
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import torch
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader

base_dir = Path(__file__).resolve().parent.parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from External_scanner.graph_schema import NODE_FEATURE_DIM, EDGE_FEATURE_DIM
from models.gnns.crypto_gnn import CryptoGNN
from models.gnns.crypto_hgnn import CryptoHGNN
from models.training.evaluate import load_test_data, evaluate_model

# Node feature column layout (see graph_schema.py):
#   0-10   node_type one-hot (11)
#   11-18  api_role one-hot (8)
#   19-23  source_type one-hot (5)
#   24-29  sink_type one-hot (6)
#   30-31  line_number, confidence
NTYPE_COLS = slice(0, 11)
API_ROLE_COLS = slice(11, 19)
SOURCE_TYPE_COLS = slice(19, 24)
SINK_TYPE_COLS = slice(24, 30)

# Edge feature column layout:
#   0-9   edge_type one-hot (10)
#   10    parameter_index
#   11    confidence
EDGE_TYPE_COLS = slice(0, 10)


def mask_feature_columns(graphs: List[Data], cols) -> List[Data]:
    """Return deep copies of graphs with the given feature columns zeroed."""
    result = []
    for g in graphs:
        gc = g.clone()
        if gc.x is not None and gc.x.size(1) > 0:
            gc.x[:, cols] = 0.0
        result.append(gc)
    return result


def mask_structure(graphs: List[Data], mask_fn) -> List[Data]:
    """Return deep copies of graphs with structural edges masked per mask_fn."""
    result = []
    for g in graphs:
        gc = g.clone()
        if gc.edge_index.size(1) > 0 and gc.edge_attr is not None:
            keep = mask_fn(gc)
            gc.edge_index = gc.edge_index[:, keep]
            gc.edge_attr = gc.edge_attr[keep]
        result.append(gc)
    return result


def run_ablation_study():
    test_graphs = load_test_data(base_dir)
    checkpoints_dir = base_dir / "models" / "checkpoints"
    results_dir = base_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # 1. Full CryptoFlow (baseline)
    # num_classes=2: dataset labels are binary; evaluate_model()'s TP/TN/FP/FN
    # counting below assumes pred/actual in {0, 1}.
    hgnn_model = CryptoHGNN(num_classes=2)
    hgnn_ckpt = checkpoints_dir / "crypto_hgnn_best.pt"
    if hgnn_ckpt.exists():
        hgnn_model.load_state_dict(torch.load(hgnn_ckpt, weights_only=True))

    gnn_model = CryptoGNN(num_classes=2)
    gnn_ckpt = checkpoints_dir / "crypto_gnn_best.pt"
    if gnn_ckpt.exists():
        gnn_model.load_state_dict(torch.load(gnn_ckpt, weights_only=True))

    base_metrics = evaluate_model(hgnn_model, test_graphs)
    baseline_f1 = base_metrics["f1"]
    total_test = len(test_graphs)

    # Ablation variants (all structural ablations use a FIXED seed mask so that
    # different variants receive genuinely different graph perturbations).
    torch.manual_seed(42)

    # 2. No macro/source-type semantics: flatten source_type encoding
    #    (removes hard-coded/runtime signal but keeps node types + api roles).
    no_source_type_graphs = mask_feature_columns(test_graphs, SOURCE_TYPE_COLS)

    # 4. No crypto-semantic features: zero out api_role + source_type + sink_type
    no_crypto_graphs = mask_feature_columns(test_graphs, slice(11, 30))

    # 5. No interprocedural flow: drop edges whose nodes are functions/files,
    #    keeping within-function flow (data flow) edges.
    def _drop_interproc(g):
        node_ids = g.node_ids
        interproc = torch.zeros(g.edge_index.size(1), dtype=torch.bool)
        for i in range(g.edge_index.size(1)):
            s, t = g.edge_index[0, i].item(), g.edge_index[1, i].item()
            sn = node_ids[s].lower() if s < len(node_ids) else ""
            tn = node_ids[t].lower() if t < len(node_ids) else ""
            if sn.startswith("func_") and (tn.startswith("func_") or tn.startswith("file_")):
                interproc[i] = True
            if sn.startswith("file_") and tn.startswith("func_"):
                interproc[i] = True
        return ~interproc

    no_inter_graphs = mask_structure(test_graphs, _drop_interproc)

    # 3. No wrapper resolution: drop CALLS edges specifically
    def _drop_calls(g):
        if g.edge_attr is None or g.edge_attr.size(0) == 0:
            return torch.ones(g.edge_index.size(1), dtype=torch.bool)
        # edge_type one-hot col index of CALLS
        et_idx = 1  # EdgeType.CALLS = index 1 in EDGE_TYPE_LIST
        return ~(g.edge_attr[:, et_idx] == 1.0)

    no_wrapper_graphs = mask_structure(test_graphs, _drop_calls)

    ablation_runs = [
        ("Full CryptoFlow (baseline)", base_metrics, "-"),
        ("No source-type semantics", evaluate_model(hgnn_model, no_source_type_graphs), "-"),
        ("No wrapper resolution", evaluate_model(hgnn_model, no_wrapper_graphs), "-"),
        ("No crypto-semantic features", evaluate_model(hgnn_model, no_crypto_graphs), "-"),
        ("No interprocedural flow", evaluate_model(hgnn_model, no_inter_graphs), "-"),
        ("GNN instead of HGNN", evaluate_model(gnn_model, test_graphs), "-"),
        ("Random-edge ablation (sanity)", evaluate_model(hgnn_model, _random_edge_graphs(test_graphs)), "-"),
    ]

    out_csv = results_dir / "ablation_study.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["variant", "precision", "recall", "f1", "delta_f1"])

        print(f"{'Variant':<32} | {'Prec':<7} | {'Rec':<7} | {'F1':<7} | {'Delta F1':<8}")
        print("-" * 75)

        for variant_name, metrics, _ in ablation_runs:
            f1 = metrics["f1"]
            delta_f1 = f1 - baseline_f1
            print(
                f"{variant_name:<32} | {metrics['precision']:.4f}  | {metrics['recall']:.4f}  | {f1:.4f}  | {delta_f1:+.4f}"
            )
            writer.writerow([
                variant_name,
                f"{metrics['precision']:.4f}",
                f"{metrics['recall']:.4f}",
                f"{f1:.4f}",
                f"{delta_f1:+.4f}",
            ])

    print(f"\nAblation study completed. Saved to {out_csv}")
    return ablation_runs


def _random_edge_graphs(graphs):
    """Sanity ablation: randomly shuffle edge targets (destroys topology)."""
    result = []
    for g in graphs:
        gc = g.clone()
        if gc.edge_index.size(1) > 0:
            perm = torch.randperm(gc.edge_index[1].size(0))
            gc.edge_index = gc.edge_index[:, perm]
        result.append(gc)
    return result


if __name__ == "__main__":
    run_ablation_study()
