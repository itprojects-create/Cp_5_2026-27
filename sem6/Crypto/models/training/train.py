"""
train.py: End-to-end training pipeline for CryptoFlow models.
Trains GenericGNN, CryptoGNN, GenericHGNN, and CryptoHGNN on project-split graph datasets.
Saves checkpoints to models/checkpoints/{model_name}_best.pt and logs to results/training_logs.csv.
Hyperparameters are loaded from config.py (single source of truth).
"""

import csv
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
import torch.optim as optim
from torch_geometric.loader import DataLoader
from torch_geometric.data import Data

# Ensure repository root is in sys.path
base_dir = Path(__file__).resolve().parent.parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from models.gnns.generic_gnn import GenericGNN
from models.gnns.crypto_gnn import CryptoGNN
from models.gnns.generic_hgnn import GenericHGNN
from models.gnns.crypto_hgnn import CryptoHGNN

from External_scanner.safe_io import safe_load_graph

# Central hyperparameter config (overrides hardcoded defaults below)
try:
    import config as _cfg
    _CFG_EPOCHS = _cfg.NUM_EPOCHS
    _CFG_BATCH  = _cfg.BATCH_SIZE
    _CFG_LR     = _cfg.LEARNING_RATE
    _CFG_WD     = _cfg.WEIGHT_DECAY
    _CFG_PAT    = getattr(_cfg, "PATIENCE", 30)
except ImportError:
    _CFG_EPOCHS, _CFG_BATCH, _CFG_LR, _CFG_WD, _CFG_PAT = 200, 32, 1e-3, 1e-5, 30


def load_dataset_by_split(base_path: Path) -> Tuple[List[Data], List[Data], List[Data]]:
    stats_csv = base_path / "datasets" / "interproc_stats.csv"
    graphs_dir = base_path / "datasets" / "interproc_graphs"

    if not stats_csv.exists():
        stats_csv = base_path / "datasets" / "dataset_stats.csv"
        graphs_dir = base_path / "datasets" / "graphs"

    train_graphs: List[Data] = []
    val_graphs: List[Data] = []
    test_graphs: List[Data] = []

    if not stats_csv.exists():
        raise FileNotFoundError(f"Missing stats CSV at {stats_csv}. Run scripts/build_interproc_dataset.py first.")

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

            graph_data = safe_load_graph(str(pt_path))
            split = row.get("split", "train").lower()
            if split == "train":
                train_graphs.append(graph_data)
            elif split == "val":
                val_graphs.append(graph_data)
            elif split == "test":
                test_graphs.append(graph_data)

    print(f"Loaded interproc dataset: {len(train_graphs)} train, {len(val_graphs)} val, {len(test_graphs)} test graphs.")
    return train_graphs, val_graphs, test_graphs


def train_epoch(model: nn.Module, loader: DataLoader, optimizer: optim.Optimizer, criterion: nn.Module) -> float:
    model.train()
    total_loss = 0.0
    for batch in loader:
        optimizer.zero_grad()
        out = model(batch)
        loss = criterion(out, batch.y)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * batch.num_graphs
    return total_loss / max(1, len(loader.dataset))


def evaluate_split(model: nn.Module, loader: DataLoader, criterion: nn.Module) -> Tuple[float, float]:
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    with torch.no_grad():
        for batch in loader:
            out = model(batch)
            loss = criterion(out, batch.y)
            total_loss += loss.item() * batch.num_graphs
            preds = out.argmax(dim=-1)
            correct += (preds == batch.y).sum().item()
            total += batch.num_graphs
    acc = correct / max(1, total)
    loss = total_loss / max(1, total)
    return loss, acc


def train_all_models(
    epochs: int = _CFG_EPOCHS,
    batch_size: int = _CFG_BATCH,
    lr: float = _CFG_LR,
    weight_decay: float = _CFG_WD,
    patience: int = _CFG_PAT,
):
    train_graphs, val_graphs, test_graphs = load_dataset_by_split(base_dir)

    train_loader = DataLoader(train_graphs, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_graphs, batch_size=batch_size, shuffle=False)

    checkpoints_dir = base_dir / "models" / "checkpoints"
    results_dir = base_dir / "results"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    log_csv = results_dir / "training_logs.csv"
    with open(log_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["model_name", "epoch", "train_loss", "val_loss", "val_acc", "epoch_time"])

    models_to_train = {
        "generic_gnn": GenericGNN(),
        "crypto_gnn": CryptoGNN(),
        "generic_hgnn": GenericHGNN(),
        "crypto_hgnn": CryptoHGNN(),
    }

    criterion = nn.CrossEntropyLoss()

    for name, model in models_to_train.items():
        print(f"\n--- Training {name} ---")
        optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
        best_val_loss = float("inf")
        best_epoch = 0
        patience_counter = 0

        for epoch in range(1, epochs + 1):
            t0 = time.time()
            train_loss = train_epoch(model, train_loader, optimizer, criterion)
            val_loss, val_acc = evaluate_split(model, val_loader, criterion)
            elapsed = time.time() - t0

            # Log to CSV
            with open(log_csv, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([name, epoch, f"{train_loss:.4f}", f"{val_loss:.4f}", f"{val_acc:.4f}", f"{elapsed:.2f}"])

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_epoch = epoch
                patience_counter = 0
                torch.save(model.state_dict(), checkpoints_dir / f"{name}_best.pt")
            else:
                patience_counter += 1

            if epoch % 10 == 0 or epoch == 1 or patience_counter == 0:
                print(f"Epoch {epoch:03d}: Train Loss={train_loss:.4f}, Val Loss={val_loss:.4f}, Val Acc={val_acc:.4f} (Best={best_val_loss:.4f} @ {best_epoch})")

            if patience_counter >= patience:
                print(f"Early stopping {name} at epoch {epoch} (no improvement for {patience} epochs).")
                break

    print(f"\nTraining finished for all models. Checkpoints saved in {checkpoints_dir}")


if __name__ == "__main__":
    train_all_models()
