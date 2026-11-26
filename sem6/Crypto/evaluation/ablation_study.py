"""
ablation_study.py  –  evaluation/ablation_study.py
Ablation study re-routed to the new evaluation package.
Delegates to the original models/training/ablation_study.py logic.
"""

from __future__ import annotations
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Re-export from the canonical training location
from models.training.ablation_study import run_ablation_study  # noqa: F401

if __name__ == "__main__":
    run_ablation_study()
