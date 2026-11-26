"""
wrapper_resolver.py  –  src/semantic_engine/wrapper_resolver.py
Re-export of External_scanner.wrapper_resolver under the canonical src namespace.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from External_scanner.wrapper_resolver import WrapperResolver, Function, WrapperFunction  # noqa: F401

__all__ = ["WrapperResolver", "Function", "WrapperFunction"]
