"""
attention_analysis.py: Analyzes node attention weights produced by CryptoHGNN
across semantic node types (CRYPTO_API, KEY, WRAPPER, LITERAL, FUNCTION, etc.).
Outputs summary statistics to results/attention_by_node_type.csv.
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch

base_dir = Path(__file__).resolve().parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from External_scanner.graph_schema import NodeType
from External_scanner.safe_io import safe_load_graph
from models.gnns.crypto_hgnn import CryptoHGNN

NODE_TYPES = [t.value for t in NodeType]


def run_attention_analysis():
    results_dir = base_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir = base_dir / "models" / "checkpoints"
    ckpt_path = checkpoints_dir / "crypto_hgnn_best.pt"

    if not ckpt_path.exists():
        print(f"Error: checkpoint {ckpt_path} not found.")
        return

    model = CryptoHGNN()
    model.load_state_dict(torch.load(ckpt_path, weights_only=True))
    model.eval()

    stats_csv = base_dir / "datasets" / "interproc_stats.csv"
    graphs_dir = base_dir / "datasets" / "interproc_graphs"

    # Gather validation graphs
    val_files = []
    with open(stats_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("split", "").lower() in {"val", "test"}:
                gid = row.get("group_id") or row.get("graph_file", "").replace(".pt", "")
                fname = f"{gid}.pt" if not gid.endswith(".pt") else gid
                pt = graphs_dir / fname
                if pt.exists():
                    val_files.append(pt)

    print(f"Analyzing attention scores across {len(val_files)} graphs...")

    attention_by_type: Dict[str, List[float]] = defaultdict(list)

    with torch.no_grad():
        for pt_path in val_files:
            g = safe_load_graph(str(pt_path))
            if g.x is None or g.x.size(0) == 0:
                continue

            _, attn = model(g, return_attention=True)
            attn_np = attn.cpu().numpy()

            num_nodes = g.x.size(0)
            for i in range(num_nodes):
                slice_11 = g.x[i, :11]
                argmax = torch.argmax(slice_11).item()
                if slice_11[argmax] > 0.5 and argmax < len(NODE_TYPES):
                    ntype = NODE_TYPES[argmax]
                else:
                    ntype = "OTHER"

                attention_by_type[ntype].append(float(attn_np[i]))

    out_csv = results_dir / "attention_by_node_type.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["node_type", "count", "mean_attention", "std_attention", "min_attention", "max_attention"])

        print(f"\n{'NodeType':<16} | {'Count':<8} | {'Mean Attn':<10} | {'Std Attn':<10} | {'Min Attn':<10} | {'Max Attn':<10}")
        print("-" * 75)

        # Sort by mean attention descending
        sorted_types = sorted(
            attention_by_type.keys(),
            key=lambda t: np.mean(attention_by_type[t]) if attention_by_type[t] else 0.0,
            reverse=True,
        )

        for nt in sorted_types:
            scores = attention_by_type[nt]
            count = len(scores)
            mean_a = float(np.mean(scores))
            std_a = float(np.std(scores))
            min_a = float(np.min(scores))
            max_a = float(np.max(scores))

            print(f"{nt:<16} | {count:<8} | {mean_a:<10.4f} | {std_a:<10.4f} | {min_a:<10.4f} | {max_a:<10.4f}")
            writer.writerow([nt, count, f"{mean_a:.4f}", f"{std_a:.4f}", f"{min_a:.4f}", f"{max_a:.4f}"])

    print(f"\nAttention analysis completed. Saved to {out_csv}")


if __name__ == "__main__":
    run_attention_analysis()
