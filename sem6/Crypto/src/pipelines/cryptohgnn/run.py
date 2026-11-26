#!/usr/bin/env python3
"""
CryptoHGNN baseline re-run entry point.

CLAUDE.md Phase 4 requires CryptoHGNN included as the baseline row,
"reuse its existing predictions if saved, otherwise re-run it without
changing its code." No saved CryptoHGNN test predictions existed in this
repo state, so this script re-runs CryptoHGNN (src/models/cryptohgnn.py,
read-only / unmodified) through the exact same shared harness
(src/common/pipeline_runner.py) used for FusionHGNN and CoCa, on the
identical split/seed, so all three rows in results/tables/comparison.csv
are produced by the same measurement code.

Note: configs/cryptohgnn_config.yaml (CryptoHGNN's own config file) is left
untouched per the read-only rule. Its architecture.num_classes: 5 value is
for CryptoHGNN's separate multi-class CWE-typing experiments; for this
binary vulnerable/not-vulnerable comparison we override num_classes=2 at
call time only (in-memory), exactly as agents/repo_scanner_agent.py already
does when it instantiates CryptoHGNN(num_classes=2). This is logged in
docs/ASSUMPTIONS.md.

Usage:
    python -m src.pipelines.cryptohgnn.run --config configs/cryptohgnn_config.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.common.pipeline_runner import load_config, run_method  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-run the CryptoHGNN baseline pipeline (read-only reuse of its model).")
    parser.add_argument("--config", default="configs/cryptohgnn_config.yaml")
    parser.add_argument("--epochs", type=int, default=None, help="Override config epochs (compute-budget reduction).")
    args = parser.parse_args()

    config_path = _REPO_ROOT / args.config
    # Patch a throwaway in-memory copy of the config with num_classes=2 for
    # this binary comparison; the file on disk is never written to.
    import yaml

    cfg = load_config(config_path)
    cfg["architecture"]["num_classes"] = 2
    patched_path = _REPO_ROOT / "configs" / "_cryptohgnn_binary_runtime.yaml"
    with open(patched_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f)

    row = run_method(patched_path, method_key="cryptohgnn", epochs_override=args.epochs)
    print(row)


if __name__ == "__main__":
    main()
