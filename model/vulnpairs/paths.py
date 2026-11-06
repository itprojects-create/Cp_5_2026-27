"""Single place for every path and for the Joern node and edge vocabularies used by the feature extractor."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "dataset" / "megavul"          # megavul_simple.json and megavul_graph.zip (not committed)
RESULTS = REPO_ROOT / "results" / "pairs"      # features.csv, build_report.json, results.json
TABLES = REPO_ROOT / "results" / "tables"      # pairs_results.csv

# The 21 edge types listed in the paper (Section 3.1); edges of any other type are dropped and counted.
EDGE_TYPES = ["AST", "CFG", "REACHING_DEF", "CALL", "DOMINATE", "POST_DOMINATE", "CONTAINS", "REF", "EVAL_TYPE", "ARGUMENT",
              "PARAMETER_LINK", "SOURCE_FILE", "BINDS", "RECEIVER", "CONDITION", "BINDS_TO", "INHERITS_FROM", "ALIAS_OF",
              "TAGGED_BY", "CAPTURE", "CDG"]
EDGE_INDEX = {t: i for i, t in enumerate(EDGE_TYPES)}
# Joern 2.0 node labels (the paper reports 33 types); labels in the data but not here map to a shared UNKNOWN slot.
NODE_TYPES = ["METHOD", "METHOD_PARAMETER_IN", "METHOD_PARAMETER_OUT", "METHOD_RETURN", "MODIFIER", "TYPE_PARAMETER",
              "TYPE_ARGUMENT", "MEMBER", "TYPE_DECL", "TYPE", "NAMESPACE_BLOCK", "NAMESPACE", "FILE", "META_DATA",
              "BINDING", "CALL", "IDENTIFIER", "FIELD_IDENTIFIER", "LITERAL", "LOCAL", "RETURN", "BLOCK", "METHOD_REF",
              "TYPE_REF", "CONTROL_STRUCTURE", "JUMP_TARGET", "JUMP_LABEL", "UNKNOWN", "ANNOTATION", "ANNOTATION_LITERAL",
              "ANNOTATION_PARAMETER", "ANNOTATION_PARAMETER_ASSIGN", "TAG"]
NODE_INDEX = {t: i for i, t in enumerate(NODE_TYPES)}
