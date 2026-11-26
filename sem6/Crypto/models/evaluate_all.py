"""
evaluate_all.py: Deprecated legacy entry point.
Superseded by evaluation/evaluate_all.py, which fixes crash-on-empty-results
and inconsistent runtime-per-graph bugs present in the old implementation
here. Kept as a thin shim for backwards compatibility.

Usage:
    python models/evaluate_all.py
"""

import sys
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from evaluation.evaluate_all import run_full_evaluation


def run_main_evaluation() -> None:
    run_full_evaluation(export_tables=True)


if __name__ == "__main__":
    run_main_evaluation()
