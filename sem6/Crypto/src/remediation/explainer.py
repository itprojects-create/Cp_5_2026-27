"""
explainer.py  –  src/remediation/explainer.py
Re-export of agents.explainer.Explainer under the canonical src namespace.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agents.explainer import Explainer  # noqa: F401

__all__ = ["Explainer"]
