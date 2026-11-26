#!/usr/bin/env python3
"""
FusionHGNN pipeline entry point.

Same CLI style as CryptoHGNN (python -m <package>.<method>.run --config ...).
Mirrors CryptoHGNN's own stage order (load -> split -> model -> train ->
inference -> raw predictions -> report), implemented in
src/common/pipeline_runner.py so both competitor methods and the
CryptoHGNN baseline re-run share one tested code path.

Usage:
    python -m src.pipelines.fusion_hgnn.run --config configs/fusion_hgnn_config.yaml
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
    parser = argparse.ArgumentParser(description="Run the FusionHGNN comparative pipeline.")
    parser.add_argument("--config", default="configs/fusion_hgnn_config.yaml")
    parser.add_argument("--epochs", type=int, default=None, help="Override config epochs (compute-budget reduction).")
    args = parser.parse_args()

    row = run_method(_REPO_ROOT / args.config, method_key="fusion_hgnn", epochs_override=args.epochs)
    print(row)


if __name__ == "__main__":
    main()
