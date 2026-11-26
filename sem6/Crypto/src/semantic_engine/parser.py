"""
parser.py  –  src/semantic_engine/parser.py
AST extraction facade.

Wraps both the primary tree-sitter-based graphify parser and the
custom fallback CParser from the legacy External_scanner package.
Public API intentionally matches the original External_scanner.c_parser.CParser
so existing call-sites remain valid.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root on path for legacy imports
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Re-export the canonical parser under the new namespace
from External_scanner.c_parser import CParser, CParseResult
from External_scanner.graphify_parser import GraphifyParser


class SemanticParser:
    """
    Unified parser facade. Delegates to the regex/heuristic CParser.

    Parameters
    ----------
    use_graphify : bool
        Reserved for future tree-sitter GraphifyParser integration.
        GraphifyParser currently only consumes a pre-generated
        ``graphify-out/graph.json`` (see External_scanner/graphify_parser.py)
        and has no per-file/per-source parse entry point compatible with
        CParser's interface, so this flag is a no-op until that integration
        is implemented. Always False for now -- do not set True.
    """

    def __init__(self, use_graphify: bool = False) -> None:
        self.use_graphify = False
        self._graphify = GraphifyParser()
        self._fallback = CParser()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def parse_file(self, path: str | Path) -> CParseResult:
        """
        Parse a C/C++ source file and return its parse result.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {path}")

        source = path.read_text(encoding="utf-8", errors="ignore")
        return self._fallback.parse(source)

    def parse_source(self, source: str, filename: str = "<string>") -> CParseResult:
        """Parse raw source text."""
        return self._fallback.parse(source)
