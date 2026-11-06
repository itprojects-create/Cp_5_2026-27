"""Adds the security-API roles of catalogue.py to a Joern code property graph.

For every CALL node whose callee is in the catalogue (and whose role the variant enables):
  * the call node gets a one-hot call role (9 dims);
  * each argument with a catalogued role gets an argument role one-hot (6 dims) and two flags describing what the argument
    expression is built from: literal_only (a literal and no identifier) and has_call (a non-operator call inside it);
  * a typed edge argument -> call is added (USES_AS_KEY, USES_AS_SIZE, USES_AS_DEST, USES_AS_SRC, USES_AS_FORMAT, USES_AS_FREED).

The base variant adds nothing, so its graphs are the plain Joern node and edge graphs.
"""

from collections import defaultdict
from typing import Dict, List, Tuple

import numpy as np

from .catalogue import ARG_ROLES, CALL_ROLES, ROLE_EDGE_TYPES, is_crypto_name, lookup, split_roles

EXTRA_NODE_DIM = len(CALL_ROLES) + len(ARG_ROLES) + 2
EXTRA_EDGE_TYPES = [ROLE_EDGE_TYPES[r] for r in ARG_ROLES]
MAX_DEPTH = 8


def _subtree_flags(root: int, children: Dict[int, List[int]], label: Dict[int, str], name: Dict[int, str]) -> Tuple[bool, bool]:
    has_literal = has_identifier = has_call = False
    stack = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        kind = label[node]
        if kind == "LITERAL":
            has_literal = True
        elif kind in ("IDENTIFIER", "FIELD_IDENTIFIER"):
            has_identifier = True
        elif kind == "CALL" and not name[node].startswith("<operator>"):
            has_call = True
        if depth < MAX_DEPTH:
            stack.extend((c, depth + 1) for c in children.get(node, ()))
    return has_literal and not has_identifier, has_call


def has_crypto_call(graph: dict) -> bool:
    return any(n["_label"] == "CALL" and is_crypto_name(n.get("name") or "") for n in graph["nodes"])


def annotate(graph: dict, variant: str) -> Tuple[np.ndarray, List[Tuple[int, int, int]], Dict[str, int]]:
    """Returns (extra node features [N, EXTRA_NODE_DIM], extra edges as (src, dst, type index within EXTRA_EDGE_TYPES), counts)."""
    call_roles, arg_roles = split_roles(variant)
    nodes = graph["nodes"]
    extra = np.zeros((len(nodes), EXTRA_NODE_DIM))
    edges: List[Tuple[int, int, int]] = []
    counts: Dict[str, int] = defaultdict(int)
    if not call_roles:
        return extra, edges, counts
    index = {n["id"]: i for i, n in enumerate(nodes)}
    label = {n["id"]: n["_label"] for n in nodes}
    name = {n["id"]: (n.get("name") or "") for n in nodes}
    arg_index = {n["id"]: n.get("argumentIndex") for n in nodes}
    ast_children: Dict[int, List[int]] = defaultdict(list)
    arguments: Dict[int, Dict[int, int]] = defaultdict(dict)
    for e in graph["edges"]:
        if e["etype"] == "AST":
            ast_children[e["outNode"]].append(e["inNode"])
        elif e["etype"] == "ARGUMENT" and arg_index.get(e["inNode"]) is not None:
            arguments[e["outNode"]][arg_index[e["inNode"]]] = e["inNode"]
    for n in nodes:
        if n["_label"] != "CALL":
            continue
        entry = lookup(name[n["id"]])
        if entry is None or entry[0] not in call_roles:
            continue
        role, positions = entry
        extra[index[n["id"]], CALL_ROLES.index(role)] = 1.0
        counts[f"call_{role}"] += 1
        for pos, arole in positions.items():
            if arole not in arg_roles:
                continue
            arg = arguments[n["id"]].get(pos + 1)  # Joern argument indices start at 1
            if arg is None:
                continue
            literal_only, has_call = _subtree_flags(arg, ast_children, label, name)
            row = index[arg]
            extra[row, len(CALL_ROLES) + ARG_ROLES.index(arole)] = 1.0
            extra[row, len(CALL_ROLES) + len(ARG_ROLES)] = float(literal_only)
            extra[row, len(CALL_ROLES) + len(ARG_ROLES) + 1] = float(has_call)
            edges.append((row, index[n["id"]], ARG_ROLES.index(arole)))
            counts[f"arg_{arole}"] += 1
    return extra, edges, counts
