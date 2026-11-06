"""Fix-aware features: is each risky operation protected by a check on the variable it uses?

Security fixes mostly add or tighten checks (bounds, null, sign, size, error returns, pointer reset after free). These features measure
the presence and absence of such checks inside one function graph, using the Joern control-dependence (CDG) and condition edges:
a risky operation is "guarded" when a condition that controls it (transitively, up to MAX_CTRL_DEPTH hops) mentions a variable that the
operation uses. Nothing is learned here; every value is a count from the graph.

Sink classes: idx (array index), deref (pointer / field dereference), arith (+, -, *, <<), div (divisor), size (size argument of an
allocation or copy), freed (argument of free). Plus: result checks of allocation and security calls, pointer reset after free,
later use of a freed name, double free, loop shape (infinite, nested, allocation or copy inside a loop), early-exit guards,
narrowing and sign-changing casts, mixed-sign comparisons.
"""
import re
from collections import defaultdict

from .catalogue import lookup

MAX_CTRL_DEPTH = 6
SUB_DEPTH = 8
SUB_CAP = 400
ARITH = {"<operator>.addition": "add", "<operator>.subtraction": "sub", "<operator>.multiplication": "mul", "<operator>.shiftLeft": "shl"}
DIV = {"<operator>.division", "<operator>.modulo"}
COMPARE = {"<operator>.lessThan", "<operator>.greaterThan", "<operator>.lessEqualsThan", "<operator>.greaterEqualsThan",
           "<operator>.equals", "<operator>.notEquals"}
IDX = "<operator>.indirectIndexAccess"
DEREF = {"<operator>.indirection", "<operator>.indirectFieldAccess"}
ASSIGN = "<operator>.assignment"
NOT = "<operator>.logicalNot"
CAST = "<operator>.cast"
LOOPS = {"FOR", "WHILE", "DO"}
NULLS = {"0", "NULL", "nullptr", "null", "(void*)0", "((void*)0)"}
SINKS = ["idx", "deref", "arith", "div", "size", "freed"]

FEATURES = ([f"g_{s}_{k}" for s in SINKS for k in ("total", "guarded", "unguarded")]
            + ["g_idx_const", "g_deref_nullcheck", "g_size_literal", "g_size_sizeof", "g_size_strlen", "g_size_arith", "g_size_var",
               "g_alloc_total", "g_alloc_checked", "g_alloc_unchecked", "g_sec_total", "g_sec_checked", "g_sec_unchecked",
               "g_free_reset", "g_free_noreset", "g_free_later_use", "g_double_free",
               "g_cond_total", "g_cond_compare", "g_cond_null", "g_cond_not", "g_cond_call", "g_guard_exit", "g_cond_only_ident",
               "g_loop_total", "g_loop_infinite", "g_loop_infinite_noexit", "g_loop_nested", "g_loop_max_depth", "g_alloc_in_loop",
               "g_copy_in_loop", "g_loop_cond_var_in_index",
               "g_cast_narrow", "g_cast_sign", "g_cmp_mixed_sign", "g_arith_narrow_operand",
               "g_unguarded_frac", "g_guard_per_sink"])

WIDTH = [("int8", 8), ("char", 8), ("int16", 16), ("short", 16), ("int32", 32), ("int64", 64), ("longlong", 64), ("long", 64),
         ("size_t", 64), ("ssize_t", 64), ("off_t", 64), ("int", 32)]


def _width(t: str):
    t = (t or "").lower().replace(" ", "").replace("*", "")
    if not t or "[" in t or t in ("any", "<empty>"):
        return None
    for k, w in WIDTH:
        if k in t:
            return w
    return None


def _unsigned(t: str):
    t = (t or "").lower()
    if not t or t in ("any", "<empty>") or "*" in t:
        return None
    if "unsigned" in t or "size_t" in t and "ssize" not in t or re.match(r"u(int|char|short|long)", t) or t.startswith("uint"):
        return True
    return False if _width(t) else None


def guard_features(graph: dict) -> dict:
    f = dict.fromkeys(FEATURES, 0.0)
    nodes = {n["id"]: n for n in graph["nodes"]}
    ast_ch, parent, args, ctrl, cond_expr = defaultdict(list), {}, defaultdict(dict), defaultdict(set), {}
    for e in graph["edges"]:
        t = e["etype"]
        if t == "AST":
            ast_ch[e["outNode"]].append(e["inNode"])
            parent[e["inNode"]] = e["outNode"]
        elif t == "ARGUMENT":
            ai = nodes.get(e["inNode"], {}).get("argumentIndex")
            if ai is not None and ai >= 0:
                args[e["outNode"]][ai] = e["inNode"]
        elif t == "CDG":
            ctrl[e["inNode"]].add(e["outNode"])
        elif t == "CONDITION":
            cond_expr[e["outNode"]] = e["inNode"]

    sub_cache, name_cache = {}, {}

    def sub(i):
        r = sub_cache.get(i)
        if r is None:
            r, st = [], [(i, 0)]
            while st and len(r) < SUB_CAP:
                x, d = st.pop()
                r.append(x)
                if d < SUB_DEPTH:
                    st.extend((c, d + 1) for c in ast_ch.get(x, ()))
            sub_cache[i] = r
        return r

    def names(i):
        r = name_cache.get(i)
        if r is None:
            r = set()
            for x in sub(i):
                n = nodes[x]
                if n["_label"] == "IDENTIFIER" and n.get("name"):
                    r.add(n["name"])
                elif n["_label"] == "FIELD_IDENTIFIER" and n.get("code"):
                    r.add(n["code"])
            name_cache[i] = r
        return r

    def calls_in(i):
        return [x for x in sub(i) if nodes[x]["_label"] == "CALL"]

    anc_cache = {}

    def controllers(i):
        r = anc_cache.get(i)
        if r is None:
            r, frontier = set(), {i}
            for _ in range(MAX_CTRL_DEPTH):
                nxt = set()
                for x in frontier:
                    for c in ctrl.get(x, ()):
                        if c not in r:
                            r.add(c)
                            nxt.add(c)
                frontier = nxt
                if not frontier:
                    break
            anc_cache[i] = r
        return r

    def guarded(i, used):
        if not used:
            return False
        own = set(sub(i))
        return any(c not in own and names(c) & used for c in controllers(i))

    def nm(x):
        return nodes[x].get("name") or ""

    cond_nodes = set(cond_expr.values()) | {c for cs in ctrl.values() for c in cs}
    cond_names, in_cond = set(), set()
    for c in cond_nodes:
        cond_names |= names(c)
        in_cond.update(sub(c))
        cn = [nm(x) for x in calls_in(c)]
        f["g_cond_total"] += 1
        f["g_cond_compare"] += 1.0 if any(x in COMPARE for x in cn) else 0.0
        f["g_cond_not"] += 1.0 if NOT in cn else 0.0
        f["g_cond_call"] += 1.0 if any(not x.startswith("<operator>") for x in cn) else 0.0
        nulllit = any(nodes[x]["_label"] == "LITERAL" and (nodes[x].get("code") in NULLS) for x in sub(c)) or any(
            nodes[x]["_label"] == "IDENTIFIER" and nodes[x].get("name") in NULLS for x in sub(c))
        f["g_cond_null"] += 1.0 if nulllit and any(x in ("<operator>.equals", "<operator>.notEquals") for x in cn) else 0.0
        f["g_cond_only_ident"] += 1.0 if nodes[c]["_label"] in ("IDENTIFIER", "FIELD_IDENTIFIER") else 0.0

    def loop_depth(i):
        d, x, hops = 0, i, 0
        while x in parent and hops < 60:
            x = parent[x]
            hops += 1
            if nodes[x]["_label"] == "CONTROL_STRUCTURE" and nodes[x].get("controlStructureType") in LOOPS:
                d += 1
        return d

    def add(sink, i, used):
        f[f"g_{sink}_total"] += 1
        if guarded(i, used):
            f[f"g_{sink}_guarded"] += 1
        else:
            f[f"g_{sink}_unguarded"] += 1

    frees, assigns = [], []
    for i, n in nodes.items():
        if n["_label"] != "CALL":
            continue
        name = n.get("name") or ""
        a = args.get(i, {})
        if name == IDX and 1 in a and 2 in a:
            ix = a[2]
            add("idx", i, names(ix))
            f["g_idx_const"] += 1.0 if nodes[ix]["_label"] == "LITERAL" else 0.0
        elif name in DEREF and 1 in a:
            add("deref", i, names(a[1]))
            f["g_deref_nullcheck"] += 1.0 if any(names(c) & names(a[1]) and (
                nodes[c]["_label"] in ("IDENTIFIER", "FIELD_IDENTIFIER") or nm(c) in (NOT, "<operator>.equals", "<operator>.notEquals"))
                for c in controllers(i)) else 0.0
        elif name in ARITH and 1 in a and 2 in a:
            u = names(a[1]) | names(a[2])
            if u:
                add("arith", i, u)
            for k in (1, 2):
                if (_width(nodes[a[k]].get("typeFullName")) or 64) <= 16:
                    f["g_arith_narrow_operand"] += 1
        elif name in DIV and 2 in a:
            if names(a[2]):
                add("div", i, names(a[2]))
        elif name == CAST and 2 in a:
            tw, sw = _width(n.get("typeFullName")), _width(nodes[a[2]].get("typeFullName"))
            tu, su = _unsigned(n.get("typeFullName")), _unsigned(nodes[a[2]].get("typeFullName"))
            f["g_cast_narrow"] += 1.0 if tw and sw and tw < sw else 0.0
            f["g_cast_sign"] += 1.0 if tu is not None and su is not None and tu != su else 0.0
        elif name in COMPARE and 1 in a and 2 in a:
            u1, u2 = _unsigned(nodes[a[1]].get("typeFullName")), _unsigned(nodes[a[2]].get("typeFullName"))
            f["g_cmp_mixed_sign"] += 1.0 if u1 is not None and u2 is not None and u1 != u2 else 0.0
        elif name == ASSIGN and 1 in a and 2 in a:
            assigns.append(i)
        e = lookup(name)
        if e is None:
            continue
        role, pos = e
        f["g_sec_total"] += 1
        res_names = set()
        p = parent.get(i)
        if p is not None and nm(p) == ASSIGN and 1 in args.get(p, {}) and args[p].get(2) == i:
            res_names = names(args[p][1])
        checked = i in in_cond or bool(res_names & cond_names)
        f["g_sec_checked"] += 1.0 if checked else 0.0
        f["g_sec_unchecked"] += 0.0 if checked else 1.0
        if role == "alloc":
            f["g_alloc_total"] += 1
            f["g_alloc_checked" if checked else "g_alloc_unchecked"] += 1
            if loop_depth(i) > 0:
                f["g_alloc_in_loop"] += 1
        if role == "copy" and loop_depth(i) > 0:
            f["g_copy_in_loop"] += 1
        for ap, arole in pos.items():
            node = a.get(ap + 1)
            if node is None:
                continue
            if arole == "size":
                add("size", node, names(node))
                cs = {nm(x) for x in calls_in(node)}
                f["g_size_literal"] += 1.0 if nodes[node]["_label"] == "LITERAL" else 0.0
                f["g_size_sizeof"] += 1.0 if "<operator>.sizeOf" in cs else 0.0
                f["g_size_strlen"] += 1.0 if any("strlen" in c for c in cs) else 0.0
                f["g_size_arith"] += 1.0 if cs & set(ARITH) else 0.0
                f["g_size_var"] += 1.0 if nodes[node]["_label"] in ("IDENTIFIER", "FIELD_IDENTIFIER") else 0.0
            elif arole == "freed":
                add("freed", node, names(node))
                frees.append((i, frozenset(names(node)), nodes[i].get("lineNumber") or 0))

    # free: pointer reset, later use, double free
    seen = set()
    for i, nset, line in frees:
        if not nset:
            continue
        reset = False
        for j in assigns:
            la = args[j]
            if (nodes[j].get("lineNumber") or 0) >= line and names(la[1]) == set(nset) and (
                    nodes[la[2]].get("code") in NULLS or nodes[la[2]].get("name") in NULLS):
                reset = True
                break
        f["g_free_reset" if reset else "g_free_noreset"] += 1
        if nset in seen:
            f["g_double_free"] += 1
        seen.add(nset)
        if len(nset) == 1 and not reset:
            (v,) = tuple(nset)
            f["g_free_later_use"] += 1.0 if any(
                n["_label"] == "IDENTIFIER" and n.get("name") == v and (n.get("lineNumber") or 0) > line for n in nodes.values()) else 0.0

    # control structures: early-exit guards and loops
    for i, n in nodes.items():
        if n["_label"] != "CONTROL_STRUCTURE":
            continue
        t = n.get("controlStructureType")
        body = sub(i)
        exits = any((nodes[x]["_label"] == "RETURN") or (nodes[x]["_label"] == "CONTROL_STRUCTURE" and nodes[x].get("controlStructureType") in (
            "BREAK", "GOTO")) for x in body)
        if t == "IF" and exits:
            f["g_guard_exit"] += 1
        if t in LOOPS:
            f["g_loop_total"] += 1
            c = cond_expr.get(i)
            infinite = c is None or (nodes[c]["_label"] == "LITERAL" and nodes[c].get("code") in ("1", "true"))
            f["g_loop_infinite"] += 1.0 if infinite else 0.0
            f["g_loop_infinite_noexit"] += 1.0 if infinite and not exits else 0.0
            d = loop_depth(i)
            f["g_loop_nested"] += 1.0 if d > 0 else 0.0
            f["g_loop_max_depth"] = max(f["g_loop_max_depth"], d + 1)
            if c is not None:
                cn = names(c)
                f["g_loop_cond_var_in_index"] += 1.0 if any(
                    nm(x) == IDX and 2 in args.get(x, {}) and names(args[x][2]) & cn for x in calls_in(i)) else 0.0

    tot = sum(f[f"g_{s}_total"] for s in SINKS)
    ung = sum(f[f"g_{s}_unguarded"] for s in SINKS)
    f["g_unguarded_frac"] = ung / tot if tot else 0.0
    f["g_guard_per_sink"] = f["g_cond_total"] / tot if tot else f["g_cond_total"]
    return f
