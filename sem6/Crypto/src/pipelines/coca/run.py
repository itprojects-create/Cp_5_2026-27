#!/usr/bin/env python3
"""
CoCa pipeline entry point.

Usage:
    python -m src.pipelines.coca.run --config configs/coca_config.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.common.pipeline_runner import run_method  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CoCa comparative pipeline.")
    parser.add_argument("--config", default="configs/coca_config.yaml")
    parser.add_argument("--epochs", type=int, default=None, help="Override config epochs (compute-budget reduction).")
    args = parser.parse_args()

    row = run_method(_REPO_ROOT / args.config, method_key="coca", epochs_override=args.epochs)
    print(row)


if __name__ == "__main__":
    main()
