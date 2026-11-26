"""
trainer.py — shared train/inference loop used identically by CryptoHGNN's
baseline re-run, FusionHGNN, and CoCa, so timing/memory/accuracy comparisons
are apples-to-apples. Mirrors the loop structure in
models/training/train.py and models/training/evaluate.py (CryptoHGNN's own
code, which is not modified — only its pattern is reused here).
"""

from __future__ import annotations

import csv
import logging
import math
from pathlib import Path
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
import torch.optim as optim
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader

from src.common.resource_tracking import RunResourceReport, cuda_peak_mb, peak_rss_mb, reset_cuda_peak, timed

logger = logging.getLogger("common.trainer")


def train_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: optim.Optimizer,
    criterion: nn.Module,
    max_grad_norm: float = 1.0,
) -> Tuple[float, int]:
    """One training epoch. Applies gradient-norm clipping uniformly across
    every method's training (common harness, not method-specific), which is
    a standard stability safeguard for the hyperbolic models (curvature-
    parameterised exp/log maps near the Poincare-ball boundary).

    Returns (mean train loss, number of skipped steps). A step is skipped when
    the loss or the gradient norm is not finite, so one bad batch cannot
    write NaN into the weights."""
    model.train()
    total_loss = 0.0
    n = 0
    skipped = 0
    for batch in loader:
        optimizer.zero_grad()
        out = model(batch)
        loss = criterion(out, batch.y)
        if not torch.isfinite(loss):
            skipped += 1
            continue
        loss.backward()
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)
        if not torch.isfinite(grad_norm):
            optimizer.zero_grad()
            skipped += 1
            continue
        optimizer.step()
        total_loss += loss.item() * batch.num_graphs
        n += batch.num_graphs
    return total_loss / max(1, n), skipped


@torch.no_grad()
def eval_loss_acc(model: nn.Module, loader: DataLoader, criterion: nn.Module) -> Tuple[float, float]:
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    for batch in loader:
        out = model(batch)
        loss = criterion(out, batch.y)
        total_loss += loss.item() * batch.num_graphs
        preds = out.argmax(dim=-1)
        correct += (preds == batch.y).sum().item()
        total += batch.num_graphs
    return total_loss / max(1, total), correct / max(1, total)


def fit(
    model: nn.Module,
    train_graphs: List[Data],
    val_graphs: List[Data],
    epochs: int,
    batch_size: int,
    lr: float,
    weight_decay: float,
    patience: int,
    log_csv_path: Path,
    checkpoint_path: Path,
) -> RunResourceReport:
    """Train with early stopping on val loss. Logs per-epoch metrics to
    log_csv_path and the best checkpoint to checkpoint_path. Returns a
    RunResourceReport with train_time_s and peak_memory_mb filled in."""
    train_loader = DataLoader(train_graphs, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_graphs, batch_size=batch_size, shuffle=False)

    log_csv_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_csv_path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(["epoch", "train_loss", "val_loss", "val_acc", "epoch_time_s"])

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    reset_cuda_peak()
    best_val_loss = float("inf")
    best_epoch = 0
    patience_counter = 0

    report = RunResourceReport()
    skipped_steps = 0
    epochs_run = 0
    with timed() as train_timer:
        for epoch in range(1, epochs + 1):
            epochs_run = epoch
            with timed() as epoch_timer:
                train_loss, skipped = train_epoch(model, train_loader, optimizer, criterion)
                val_loss, val_acc = eval_loss_acc(model, val_loader, criterion)
            skipped_steps += skipped
            if not math.isfinite(val_loss):
                report.diverged = True
                logger.warning("Non-finite val loss at epoch %d; stopping training.", epoch)
                break

            with open(log_csv_path, "a", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow(
                    [epoch, f"{train_loss:.4f}", f"{val_loss:.4f}", f"{val_acc:.4f}", f"{epoch_timer.elapsed:.3f}"]
                )

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_epoch = epoch
                patience_counter = 0
                torch.save(model.state_dict(), checkpoint_path)
            else:
                patience_counter += 1

            if epoch % 5 == 0 or epoch == 1:
                logger.info(
                    "epoch=%03d train_loss=%.4f val_loss=%.4f val_acc=%.4f (best=%.4f@%d)",
                    epoch, train_loss, val_loss, val_acc, best_val_loss, best_epoch,
                )

            if patience_counter >= patience:
                logger.info("Early stopping at epoch %d (no val improvement for %d epochs).", epoch, patience)
                break

    report.best_epoch = best_epoch
    report.epochs_run = epochs_run
    report.skipped_steps = skipped_steps
    report.train_time_s = train_timer.elapsed
    report.peak_memory_mb = peak_rss_mb()
    report.cuda_peak_memory_mb = cuda_peak_mb()

    # Reload best checkpoint before returning.
    if checkpoint_path.exists():
        model.load_state_dict(torch.load(checkpoint_path, weights_only=True))
    return report


@torch.no_grad()
def predict(model: nn.Module, test_samples) -> Tuple[List[dict], float]:
    """Run inference over the test split, one graph at a time (as
    CryptoHGNN's own evaluate.py does), returning per-sample predictions and
    the total inference wall-clock time."""
    model.eval()
    rows: List[dict] = []
    with timed() as t:
        for s in test_samples:
            loader = DataLoader([s.data], batch_size=1, shuffle=False)
            batch = next(iter(loader))
            out = model(batch)
            probs = torch.softmax(out, dim=-1)
            pred = int(out.argmax(dim=-1).item())
            score = float(probs[0, 1].item())  # P(vulnerable)
            rows.append(
                {
                    "id": s.group_id,
                    "cwe": s.cwe,
                    "true_label": int(s.label),
                    "pred_label": pred,
                    "score": score,
                }
            )
    return rows, t.elapsed


def save_predictions_csv(rows: List[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "cwe", "true_label", "pred_label", "score"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
