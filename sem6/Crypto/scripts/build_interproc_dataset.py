"""
build_interproc_dataset.py: Builds the interprocedural dataset for CryptoFlow v2.

Reads datasets/juliet_groups.json, invokes InterprocGraphBuilder for each group,
saves PyTorch Geometric .pt graphs to datasets/interproc_graphs/, and writes
summary statistics to datasets/interproc_stats.csv.
"""

import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Set

import torch

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from External_scanner.interproc_graph_builder import InterprocGraphBuilder
from config import DATASETS_DIR, GRAPHS_DIR, INTERPROC_STATS_PATH


def compute_graph_hash(data) -> str:
    """Computes a SHA256 content hash of the graph structure and features."""
    hasher = hashlib.sha256()
    hasher.update(data.x.numpy().tobytes())
    hasher.update(data.edge_index.numpy().tobytes())
    hasher.update(data.edge_attr.numpy().tobytes())
    return hasher.hexdigest()[:16]


def main():
    manifest_path = Path(DATASETS_DIR) / "juliet_groups.json"
    if not manifest_path.exists():
        print(
            f"Error: Manifest not found at {manifest_path}. Run scripts/audit_juliet.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        groups = json.load(f)

    print(f"=== Building Interprocedural Dataset ({len(groups)} groups) ===")
    os.makedirs(GRAPHS_DIR, exist_ok=True)

    builder = InterprocGraphBuilder()
    stats_rows = []
    split_hashes: Dict[str, Set[str]] = {"train": set(), "val": set(), "test": set()}
    duplicates_detected = 0

    start_time = time.time()
    for idx, g in enumerate(groups, 1):
        group_id = g["group_id"]
        cwe = g["cwe"]
        split = g["split"]
        label = g["label"]
        context = g.get("context", "full")
        files = [
            str((BASE_DIR / file_path).resolve())
            if not Path(file_path).is_absolute()
            else file_path
            for file_path in g["files"]
        ]

        try:
            data = builder.build_from_file_group(
                file_paths=files,
                label=label,
                group_id=group_id,
                context=context,
            )
        except Exception as e:
            print(f"  [ERROR] Failed to build {group_id}: {e}", file=sys.stderr)
            continue

        ghash = compute_graph_hash(data)
        out_path = Path(GRAPHS_DIR) / f"{group_id}.pt"
        torch.save(data, out_path)

        # Cross-split hash verification
        for other_split, hashes in split_hashes.items():
            if other_split != split and ghash in hashes:
                duplicates_detected += 1

        split_hashes.setdefault(split, set()).add(ghash)

        # Calculate max call depth
        max_d = 0.0
        if data.x.shape[0] > 0 and data.x.shape[1] >= 34:
            max_d = data.x[:, 33].max().item()

        stats_rows.append(
            {
                "group_id": group_id,
                "cwe": cwe,
                "split": split,
                "label": label,
                "n_nodes": data.x.shape[0],
                "n_edges": data.edge_index.shape[1],
                "max_depth": round(max_d, 3),
                "n_files": len(files),
                "sha256": ghash,
            }
        )

        if idx % 50 == 0 or idx == len(groups):
            elapsed = time.time() - start_time
            print(
                f"  [{idx:3d}/{len(groups):3d}] Built graphs (elapsed: {elapsed:.1f}s)"
            )

    # Save interproc_stats.csv
    with open(INTERPROC_STATS_PATH, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "group_id",
            "cwe",
            "split",
            "label",
            "n_nodes",
            "n_edges",
            "max_depth",
            "n_files",
            "sha256",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(stats_rows)

    print(f"\nSaved stats to {INTERPROC_STATS_PATH}")
    print(f"Saved {len(stats_rows)} graphs to {GRAPHS_DIR}")
    print(
        f"Cross-split data leakage check: {duplicates_detected} duplicates detected (0 expected)"
    )

    # Print summary breakdown
    print("\n=== Dataset Distribution ===")
    split_summary = {}
    for r in stats_rows:
        sp = r["split"]
        if sp not in split_summary:
            split_summary[sp] = {
                "count": 0,
                "vuln": 0,
                "clean": 0,
                "nodes": 0,
                "edges": 0,
            }
        split_summary[sp]["count"] += 1
        if r["label"] == 1:
            split_summary[sp]["vuln"] += 1
        else:
            split_summary[sp]["clean"] += 1
        split_summary[sp]["nodes"] += r["n_nodes"]
        split_summary[sp]["edges"] += r["n_edges"]

    for sp, s in split_summary.items():
        avg_nodes = s["nodes"] / s["count"] if s["count"] > 0 else 0
        avg_edges = s["edges"] / s["count"] if s["count"] > 0 else 0
        print(
            f"  {sp:<8s}: {s['count']:3d} graphs (vuln={s['vuln']:3d}, clean={s['clean']:3d}, avg_nodes={avg_nodes:.1f}, avg_edges={avg_edges:.1f})"
        )


if __name__ == "__main__":
    main()
