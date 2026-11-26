"""
data.py — shared dataset loading, reusing CryptoHGNN's own loader logic
(datasets/interproc_stats.csv + datasets/interproc_graphs/*.pt) and split
column, so every method (CryptoHGNN baseline re-run, FusionHGNN, CoCa) trains
and evaluates on the identical train/val/test split, with the identical
label scheme (binary: 0 = not vulnerable, 1 = vulnerable).

This module does not modify CryptoHGNN's code — it re-reads the same cached
artifacts CryptoHGNN's own models/training/{train,evaluate}.py read
(datasets/interproc_stats.csv / datasets/interproc_graphs), via CryptoHGNN's
own safe_load_graph helper.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
from torch_geometric.data import Data

from External_scanner.safe_io import safe_load_graph

REPO_ROOT = Path(__file__).resolve().parents[2]
STATS_CSV = REPO_ROOT / "datasets" / "interproc_stats.csv"
GRAPHS_DIR = REPO_ROOT / "datasets" / "interproc_graphs"

#: Fixed seed used for every method, per CLAUDE.md "same seeds" requirement.
SEED = 42


def set_global_seed(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


@dataclass
class Sample:
    data: Data
    group_id: str
    cwe: str
    label: int
    split: str


SPLIT_CSV = REPO_ROOT / "data" / "splits" / "juliet_grouped_split.csv"


def load_split_assignment(split_csv: Path = SPLIT_CSV) -> Dict[str, str]:
    """group_id -> split ('train' | 'val' | 'test' | 'challenge'), as written
    by scripts/make_split.py. This replaces the split column in
    interproc_stats.csv, which is left untouched."""
    if not split_csv.exists():
        raise FileNotFoundError(f"Missing {split_csv}. Run scripts/make_split.py first.")
    with open(split_csv, "r", encoding="utf-8") as f:
        return {row["group_id"]: row["split"] for row in csv.DictReader(f)}


def load_all_samples(stats_csv: Path = STATS_CSV, graphs_dir: Path = GRAPHS_DIR) -> List[Sample]:
    """Load every cached graph referenced in interproc_stats.csv (CryptoHGNN's
    own dataset index). The split of each graph comes from
    data/splits/juliet_grouped_split.csv, not from the stats file."""
    assignment = load_split_assignment()
    samples: List[Sample] = []
    if not stats_csv.exists():
        raise FileNotFoundError(
            f"Missing dataset index at {stats_csv}. Run scripts/build_interproc_dataset.py first."
        )
    with open(stats_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gid = row.get("group_id") or row.get("graph_file", "").replace(".pt", "")
            if not gid or gid == "N/A":
                continue
            fname = f"{gid}.pt" if not gid.endswith(".pt") else gid
            pt_path = graphs_dir / fname
            if not pt_path.exists():
                continue
            graph = safe_load_graph(str(pt_path))
            n_nodes = int(graph.x.size(0))
            expected = row.get("n_nodes")
            if n_nodes == 0 or (expected and int(expected) != n_nodes):
                raise RuntimeError(
                    f"Stale graph cache: {pt_path.name} has {n_nodes} nodes but "
                    f"{stats_csv.name} records {expected}. Rebuild with "
                    "scripts/build_interproc_dataset.py."
                )
            if gid not in assignment:
                raise KeyError(f"{gid} is missing from the split file; rerun scripts/make_split.py.")
            samples.append(
                Sample(
                    data=graph,
                    group_id=gid,
                    cwe=row.get("cwe", "UNKNOWN"),
                    label=int(row.get("label", graph.y.item() if hasattr(graph, "y") else 0)),
                    split=assignment[gid],
                )
            )
    return samples


def split_samples(samples: List[Sample]) -> Tuple[List[Sample], List[Sample], List[Sample]]:
    """Split into train/val/test using data/splits/juliet_grouped_split.csv.
    The same split feeds all three methods."""
    train = [s for s in samples if s.split == "train"]
    val = [s for s in samples if s.split == "val"]
    test = [s for s in samples if s.split == "test"]
    return train, val, test


def challenge_samples(samples: List[Sample]) -> List[Sample]:
    """The 55 hand-written cases. Never used for training or tuning."""
    return [s for s in samples if s.split == "challenge"]


def save_split_indices(samples: List[Sample], out_path: Path) -> None:
    """Persist the exact group_ids per split for reproducibility (CLAUDE.md:
    'saved split indices')."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["group_id", "cwe", "label", "split"])
        for s in samples:
            writer.writerow([s.group_id, s.cwe, s.label, s.split])


def to_pyg_list(samples: List[Sample]) -> List[Data]:
    out = []
    for s in samples:
        d = s.data
        d.y = torch.tensor([s.label], dtype=torch.long)
        out.append(d)
    return out
