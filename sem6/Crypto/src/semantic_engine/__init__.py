"""
semantic_engine package: Tier-1 symbolic static analysis components.

Sub-modules:
  - parser           : AST extraction via tree-sitter and fallback CParser
  - macro_expander   : Nested #define resolver (MacroExpander)
  - wrapper_resolver : Call-tree depth tracer (WrapperResolver)
  - alias_tracker    : Disjoint-Set Union-Find pointer alias engine (AliasAnalyzer)
"""

__all__ = ["SemanticParser", "MacroExpander", "WrapperResolver", "AliasTracker"]


def __getattr__(name: str):
    if name == "SemanticParser":
        from src.semantic_engine.parser import SemanticParser
        return SemanticParser
    if name == "MacroExpander":
        from src.semantic_engine.macro_expander import MacroExpander
        return MacroExpander
    if name == "WrapperResolver":
        from src.semantic_engine.wrapper_resolver import WrapperResolver
        return WrapperResolver
    if name == "AliasTracker":
        from src.semantic_engine.alias_tracker import AliasTracker
        return AliasTracker
    raise AttributeError(f"module 'src.semantic_engine' has no attribute {name!r}")
