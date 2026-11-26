"""
alias_tracker.py  –  src/semantic_engine/alias_tracker.py
Disjoint-Set (Union-Find) pointer alias engine.

Wraps External_scanner.alias_analyzer.AliasAnalyzer and exposes it
under the canonical AliasTracker name used by the new src layout.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from External_scanner.alias_analyzer import AliasAnalyzer  # noqa: F401

# Canonical alias for the new namespace
AliasTracker = AliasAnalyzer

__all__ = ["AliasTracker", "AliasAnalyzer"]
