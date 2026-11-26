#!/usr/bin/env python3
"""
run_pipeline.py  –  CryptoFlow Unified CLI Entry Point
=======================================================
Single-command interface for all major CryptoFlow pipeline stages.

Usage examples
--------------
  # Evaluate all models and generate comparative benchmark
  python run_pipeline.py --step evaluate

  # Generate comparative architecture trace figure (3-panel)
  python run_pipeline.py --step visualize

  # Generate reports (CSV tables)
  python run_pipeline.py --step report

  # Full pipeline: evaluate + visualize + report
  python run_pipeline.py --step all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def _check_torch_availability() -> bool:
    try:
        import torch
        import torch_geometric
        return True
    except (ImportError, OSError) as e:
        print("\n" + "!" * 80)
        print(" [CRITICAL] PyTorch / Torch_Geometric Failed to Load.")
        print(f" Error: {e}")
        print("\n This is typically caused by Windows Application Control blocking native DLLs.")
        print(" -> **ACTION REQUIRED**: To run deep learning inference, please execute this")
        print("    repository from within Windows Subsystem for Linux (WSL).")
        print("    See README.md for 'Offline Execution via WSL' instructions.")
        print("!" * 80 + "\n")
        return False


def cmd_evaluate(args: argparse.Namespace) -> None:
    """Run full comparative evaluation across all models."""
    if not _check_torch_availability():
        print(" [INFO] Falling back to CACHED/MOCK evaluation mode.")
    from evaluation.evaluate_all import run_full_evaluation
    run_full_evaluation(export_tables=False)


def cmd_visualize(args: argparse.Namespace) -> None:
    """Generate 3-panel comparative architecture trace figure."""
    try:
        from src.visualization.compare_plots import ComparePlots
        cp = ComparePlots(dpi=args.dpi)
        paths = cp.generate(
            output_dir=args.output_dir,
            save_pdf=not args.no_pdf,
        )
        print("\nGenerated files:")
        for p in paths:
            print(f"  {p}")
    except Exception as e:
        print(f"[ERROR] Visualization failed: {e}")


def cmd_report(args: argparse.Namespace) -> None:
    """Export benchmark and ablation CSV tables."""
    print("Generating CSV reports...")
    from evaluation.evaluate_all import run_full_evaluation
    # Forcing export_tables=True and suppressing console output
    run_full_evaluation(export_tables=True)


def cmd_all(args: argparse.Namespace) -> None:
    """Run full pipeline: evaluate (with report export) → visualize."""
    print("\n" + "=" * 60)
    print("  Stage 1/2 — Comparative Evaluation + Report Generation")
    print("=" * 60)
    # Runs evaluation once with export_tables=True, which both prints the
    # console report and writes the CSV tables -- avoids re-running
    # inference a second time just to export the same results.
    cmd_report(args)

    print("\n" + "=" * 60)
    print("  Stage 2/2 — Comparative Visualization")
    print("=" * 60)
    cmd_visualize(args)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_pipeline",
        description="CryptoFlow unified pipeline CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--step",
        choices=["evaluate", "visualize", "report", "all"],
        required=True,
        help="Pipeline stage to run.",
    )
    parser.add_argument(
        "--output-dir",
        default="results/figures",
        help="Output directory for figures (default: results/figures).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Figure DPI (default: 300).",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Skip PDF output for visualization.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "evaluate":  cmd_evaluate,
        "visualize": cmd_visualize,
        "report":    cmd_report,
        "all":       cmd_all,
    }
    dispatch[args.step](args)


if __name__ == "__main__":
    main()
