"""Turns one Joern code property graph into a fixed-length feature vector (counts only; nothing is learned here).

Groups: size (nodes, edges), node-type counts (33), edge-type counts (21), operator-group counts (compare, logic, arith, index, cast, assign),
security-API role counts (9 call roles, 6 argument roles, 2 argument flags) and call totals.
"""
import math

from .catalogue import ARG_ROLES, CALL_ROLES
from ..paths import EDGE_TYPES, NODE_TYPES
from .roles import annotate

OPS = {"compare": ("lessThan", "greaterThan", "lessEqualsThan", "greaterEqualsThan", "equals", "notEquals"),
       "logic": ("logicalNot", "logicalAnd", "logicalOr"), "arith": ("addition", "subtraction", "multiplication", "division", "shiftLeft", "modulo"),
       "index": ("indirectIndexAccess", "indirection", "indirectFieldAccess", "pointerShift", "addressOf"), "cast": ("cast",),
       "assign": ("assignment", "assignmentPlus", "assignmentMinus")}
OP_OF = {f"<operator>.{n}": k for k, v in OPS.items() for n in v}
FEATURES = (["nodes", "edges", "log_nodes"] + [f"n_{t}" for t in NODE_TYPES] + [f"e_{t}" for t in EDGE_TYPES] + [f"op_{k}" for k in OPS]
            + [f"call_{r}" for r in CALL_ROLES] + [f"arg_{r}" for r in ARG_ROLES] + ["arg_literal_only", "arg_has_call", "calls_total", "calls_external"])


def features(graph: dict) -> dict:
    nodes, edges = graph["nodes"], graph["edges"]
    f = dict.fromkeys(FEATURES, 0.0)
    f["nodes"], f["edges"] = len(nodes), len(edges)
    f["log_nodes"] = float(math.log(max(len(nodes), 1)))
    for n in nodes:
        lab = n["_label"]
        f[f"n_{lab if lab in NODE_TYPES else 'UNKNOWN'}"] += 1
        if lab == "CALL":
            f["calls_total"] += 1
            f["calls_external"] += 1.0 if n.get("isExternal") else 0.0
            k = OP_OF.get(n.get("name") or "")
            if k:
                f[f"op_{k}"] += 1
    for e in edges:
        if e["etype"] in EDGE_TYPES:
            f[f"e_{e['etype']}"] += 1
    extra, _, counts = annotate(graph, "full")
    for k, v in counts.items():
        if k in f:
            f[k] = float(v)
    f["arg_literal_only"] = float(extra[:, len(CALL_ROLES) + len(ARG_ROLES)].sum())
    f["arg_has_call"] = float(extra[:, len(CALL_ROLES) + len(ARG_ROLES) + 1].sum())
    return f


