"""
fix_generator.py  –  src/remediation/fix_generator.py
Re-export of agents.fix_generator.FixGenerator under the canonical src namespace.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agents.fix_generator import FixGenerator  # noqa: F401

__all__ = ["FixGenerator"]
