"""
macro_expander.py  –  src/semantic_engine/macro_expander.py
Thin re-export of External_scanner.macro_expander.MacroExpander
under the canonical src namespace.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from External_scanner.macro_expander import MacroExpander  # noqa: F401

__all__ = ["MacroExpander"]
