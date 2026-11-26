"""
interproc_graph_builder.py: Interprocedural Graph Builder for CryptoFlow v2.

Builds repository-level and test-group-level interprocedural graphs across
multiple C files, incorporating:
  1. Preprocessing and guard stripping (#ifndef OMITBAD / OMITGOOD)
  2. Context-specific function filtering ('bad' vs 'good' vs 'full')
  3. Multi-file AST parsing and semantic analysis
  4. Unified node registry with FILE, FUNCTION, WRAPPER, PARAMETER, VARIABLE,
     LITERAL, and CRYPTO_API nodes
  5. Cross-file CONTAINS, CALLS, ARGUMENT_TO_PARAMETER, FLOWS_TO, ALIASES,
     and USES_AS_KEY edges
  6. Interprocedural boundary detection
  7. Hierarchical call depth computation via BFS (for Poincaré ball hierarchy & 3D visualizer Z-axis)
  8. PyG Data generation with 34-dimensional node feature vectors
"""

import collections
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

import torch
from torch_geometric.data import Data

from External_scanner.c_parser import CParser, CFuncDef, CCall, CAssignment
from External_scanner.semantic_engine import SemanticEngine, load_crypto_catalog
from External_scanner.graph_schema import (
    NodeType,
    EdgeType,
    NODE_FEATURE_DIM,
    EDGE_FEATURE_DIM,
    encode_node_features,
    encode_edge_features,
    NODE_TYPE_TO_IDX,
    EDGE_TYPE_TO_IDX,
)


def strip_guards(code: str) -> str:
    """Removes #ifndef OMITBAD / #ifdef OMITBAD / #endif compilation guards."""
    code = re.sub(r'#ifndef\s+OMIT\w+\r?\n', '', code)
    code = re.sub(r'#ifdef\s+OMIT\w+\r?\n', '', code)
    code = re.sub(r'#endif(?:\s+/\*[^*]*\*/)?\r?\n', '\n', code)
    return code


class InterprocGraphBuilder:
    """
    Builds interprocedural semantic property graphs across multiple C source files.
    """

    def __init__(
        self,
        catalog_path: Optional[str] = None,
        use_macros: bool = True,
        use_wrappers: bool = True,
        use_aliases: bool = True,
    ):
        self.catalog = load_crypto_catalog(catalog_path)
        self.c_parser = CParser()
        self.semantic_engine = SemanticEngine(
            catalog_path=catalog_path,
            use_macros=use_macros,
            use_wrappers=use_wrappers,
            use_aliases=use_aliases,
        )

    def _filter_functions(self, functions: List[CFuncDef], context: str) -> List[CFuncDef]:
        """Filters functions based on the evaluation context (bad vs good vs full)."""
        filtered = []
        for fn in functions:
            name = fn.name
            if name in {"printLine", "printIntLine", "printHexCharLine"}:
                continue
            if context == "bad":
                if name == "main":
                    continue
                if re.search(r'good', name, re.IGNORECASE):
                    continue
                filtered.append(fn)
            elif context == "good":
                if name == "main":
                    continue
                if re.search(r'bad', name, re.IGNORECASE):
                    continue
                filtered.append(fn)
            else:
                # full context
                if name == "main" and len(functions) > 1:
                    continue
                filtered.append(fn)
        return filtered

    def build_from_file_group(
        self,
        file_paths: List[str],
        label: int,
        group_id: str,
        context: str = "full",
    ) -> Data:
        """
        Constructs a unified interprocedural PyG Data graph from a group of C files.
        """
        node_registry: Dict[str, Dict[str, Any]] = {}
        raw_edges: List[Dict[str, Any]] = []

        def add_node(
            nid: str,
            ntype: str,
            file_path: str = "",
            line_number: int = 1,
            api_role: str = "unknown",
            source_type: str = "unknown",
            sink_type: str = "none",
            confidence: float = 1.0,
        ):
            if nid not in node_registry:
                node_registry[nid] = {
                    "id": nid,
                    "type": ntype,
                    "file_path": file_path,
                    "line_number": line_number,
                    "api_role": api_role,
                    "source_type": source_type,
                    "sink_type": sink_type,
                    "confidence": confidence,
                    "is_boundary": 0.0,
                    "call_depth": 0,
                }

        def add_edge(src: str, tgt: str, etype: str, confidence: float = 1.0, param_idx: int = -1):
            if src in node_registry and tgt in node_registry and src != tgt:
                raw_edges.append({
                    "source": src,
                    "target": tgt,
                    "type": etype,
                    "confidence": confidence,
                    "param_idx": param_idx,
                })

        # Function definition index: fn_name -> (file_path, CFuncDef)
        defined_functions: Dict[str, Tuple[str, CFuncDef]] = {}
        per_file_c_res: Dict[str, Any] = {}
        per_file_sem_res: Dict[str, Any] = {}

        # 1. Parse and extract definitions for each file
        for fp in file_paths:
            p = Path(fp)
            if not p.exists():
                continue
            code_raw = p.read_text(encoding="utf-8", errors="ignore")
            code_clean = strip_guards(code_raw)
            fname = p.name

            # Add FILE node
            file_node_id = f"file_{fname}"
            add_node(file_node_id, "FILE", file_path=fname, line_number=1, confidence=1.0)

            # AST parse
            parse_res = self.c_parser.parse(code_clean)
            filtered_fns = self._filter_functions(parse_res.functions, context)
            per_file_c_res[fp] = (parse_res, filtered_fns, code_clean)

            # Semantic Engine parse
            sem_res = self.semantic_engine.analyze(code_clean, file_path=fname, label=label)
            per_file_sem_res[fp] = sem_res

            for fn in filtered_fns:
                defined_functions[fn.name] = (fname, fn)

        # 2. Build Nodes & Edges
        crypto_api_names = set(self.catalog.keys())
        # Add common Windows crypto APIs
        crypto_api_names.update({
            "CryptAcquireContext", "CryptAcquireContextA", "CryptAcquireContextW",
            "CryptCreateHash", "CryptHashData", "CryptDeriveKey",
            "CryptEncrypt", "CryptDecrypt", "CryptDestroyKey", "CryptReleaseContext",
            "rand", "srand", "RAND_bytes", "RAND_pseudo_bytes",
            "EVP_EncryptInit_ex", "EVP_DecryptInit_ex", "AES_set_encrypt_key", "AES_set_decrypt_key",
        })

        for fp in file_paths:
            if fp not in per_file_c_res:
                continue
            parse_res, filtered_fns, code_clean = per_file_c_res[fp]
            sem_res = per_file_sem_res[fp]
            fname = Path(fp).name
            file_node_id = f"file_{fname}"

            # Function nodes & CONTAINS edges
            for fn in filtered_fns:
                fn_node_id = f"func_{fn.name}"
                is_wrapper = any(w.name == fn.name for w in sem_res.wrappers)
                ntype = "WRAPPER" if is_wrapper else "FUNCTION"
                add_node(fn_node_id, ntype, file_path=fname, line_number=fn.line_number, confidence=0.95)
                add_edge(file_node_id, fn_node_id, "CONTAINS")

                # Parameters
                for p_idx, param_name in enumerate(fn.parameters):
                    clean_p = param_name.split()[-1].strip("*")
                    if clean_p:
                        p_node_id = f"param_{fn.name}_{clean_p}"
                        add_node(p_node_id, "PARAMETER", file_path=fname, line_number=fn.line_number)
                        add_edge(fn_node_id, p_node_id, "CONTAINS")

                # Call edges from this function
                for call in fn.calls:
                    callee = call.callee_name
                    if callee in crypto_api_names:
                        api_node_id = f"api_{callee}"
                        role = "algorithm" if "init" in callee.lower() or "set" in callee.lower() else "key"
                        add_node(api_node_id, "CRYPTO_API", file_path=fname, line_number=call.line_number, api_role=role, sink_type="crypto")
                        add_edge(fn_node_id, api_node_id, "CALLS", confidence=1.0)

                        # Check arguments to crypto API
                        for arg_idx, arg in enumerate(call.arguments):
                            clean_arg = arg.strip().strip("&")
                            arg_node_id = f"var_{fn.name}_{clean_arg}"
                            if arg_node_id in node_registry:
                                node_registry[arg_node_id]["type"] = "KEY"
                                node_registry[arg_node_id]["api_role"] = "key"
                                add_edge(arg_node_id, api_node_id, "USES_AS_KEY", param_idx=arg_idx)

                    elif callee in defined_functions:
                        target_file, target_fn = defined_functions[callee]
                        target_fn_id = f"func_{callee}"
                        add_edge(fn_node_id, target_fn_id, "CALLS", confidence=0.95)

                        # Interprocedural boundary detection
                        if target_file != fname:
                            node_registry[fn_node_id]["is_boundary"] = 1.0
                            if target_fn_id in node_registry:
                                node_registry[target_fn_id]["is_boundary"] = 1.0

                        # Map caller arguments to callee parameters
                        for arg_idx, arg in enumerate(call.arguments):
                            if arg_idx < len(target_fn.parameters):
                                clean_arg = arg.strip().strip("&")
                                target_param = target_fn.parameters[arg_idx].split()[-1].strip("*")
                                arg_node_id = f"var_{fn.name}_{clean_arg}"
                                param_node_id = f"param_{callee}_{target_param}"
                                if arg_node_id in node_registry and param_node_id in node_registry:
                                    add_edge(arg_node_id, param_node_id, "ARGUMENT_TO_PARAMETER", param_idx=arg_idx)

            # Assignments & Literals
            for a in parse_res.assignments:
                lhs = a.lhs.strip().strip("*")
                rhs = a.rhs.strip()
                if not lhs or not rhs:
                    continue

                # Locate enclosing function
                enclosing_fn = "global"
                for fn in filtered_fns:
                    if fn.line_number <= a.line_number:
                        enclosing_fn = fn.name

                lhs_id = f"var_{enclosing_fn}_{lhs}"
                is_key = "key" in lhs.lower() or "secret" in lhs.lower() or "pwd" in lhs.lower() or "pass" in lhs.lower()
                ntype = "KEY" if is_key else "VARIABLE"
                source_type = "hard-coded" if rhs.startswith('"') or rhs.startswith("'") or re.search(r'0x[0-9a-fA-F]+', rhs) else "runtime"
                add_node(lhs_id, ntype, file_path=fname, line_number=a.line_number, source_type=source_type)

                if enclosing_fn != "global":
                    add_edge(f"func_{enclosing_fn}", lhs_id, "CONTAINS")

                # If RHS is a literal
                if rhs.startswith('"') or rhs.startswith("'") or rhs.isdigit():
                    lit_id = f"lit_{fname}_{a.line_number}"
                    add_node(lit_id, "LITERAL", file_path=fname, line_number=a.line_number, source_type="hard-coded")
                    add_edge(lit_id, lhs_id, "ASSIGNED_FROM")
                else:
                    rhs_id = f"var_{enclosing_fn}_{rhs.strip().strip('*&')}"
                    if rhs_id in node_registry:
                        add_edge(rhs_id, lhs_id, "FLOWS_TO")

            # Dataflow & Aliases from semantic engine
            for nid, fnode in sem_res.flow_graph.nodes.items() if sem_res.flow_graph else []:
                for fn in filtered_fns:
                    v_id = f"var_{fn.name}_{nid}"
                    if v_id in node_registry:
                        if getattr(fnode, "is_hardcoded", False):
                            node_registry[v_id]["source_type"] = "hard-coded"

        # 3. Hierarchical Call Depth via BFS from FILE nodes
        # FILE nodes = depth 0
        # FILE -> FUNCTION = depth 1
        # FUNCTION -> FUNCTION (calls) = depth + 1
        # FUNCTION -> VARIABLES / SINK = depth + 1
        adjacency: Dict[str, List[str]] = collections.defaultdict(list)
        for e in raw_edges:
            adjacency[e["source"]].append(e["target"])

        depths: Dict[str, int] = {}
        queue = collections.deque()

        for nid, nmeta in node_registry.items():
            if nmeta["type"] == "FILE":
                depths[nid] = 0
                queue.append(nid)

        while queue:
            curr = queue.popleft()
            curr_depth = depths[curr]
            for nxt in adjacency.get(curr, []):
                if nxt not in depths:
                    depths[nxt] = curr_depth + 1
                    queue.append(nxt)

        max_depth = max(depths.values()) if depths else 1
        max_depth = max(max_depth, 1)

        for nid in node_registry:
            d = depths.get(nid, max_depth)
            node_registry[nid]["call_depth"] = d
            node_registry[nid]["call_depth_norm"] = min(float(d) / float(max_depth), 1.0)

        # 4. Assemble PyG Data tensors (dim=34)
        node_id_list = list(node_registry.keys())
        node_to_idx = {nid: idx for idx, nid in enumerate(node_id_list)}

        x_features: List[List[float]] = []
        for nid in node_id_list:
            n = node_registry[nid]
            feat = encode_node_features(
                node_type=n["type"],
                api_role=n["api_role"],
                source_type=n["source_type"],
                sink_type=n["sink_type"],
                line_number=n["line_number"],
                confidence=n["confidence"],
                is_interproc_boundary=n["is_boundary"],
                call_depth_normalized=n["call_depth_norm"],
            )
            x_features.append(feat)

        edge_index_list: List[List[int]] = [[], []]
        edge_attr_list: List[List[float]] = []

        for e in raw_edges:
            src_idx = node_to_idx[e["source"]]
            tgt_idx = node_to_idx[e["target"]]
            edge_index_list[0].append(src_idx)
            edge_index_list[1].append(tgt_idx)
            edge_feat = encode_edge_features(
                edge_type=e["type"],
                parameter_index=e.get("param_idx", -1),
                confidence=e.get("confidence", 1.0),
            )
            edge_attr_list.append(edge_feat)

        if not edge_index_list[0]:
            edge_index_tensor = torch.zeros((2, 0), dtype=torch.long)
            edge_attr_tensor = torch.zeros((0, EDGE_FEATURE_DIM), dtype=torch.float32)
        else:
            edge_index_tensor = torch.tensor(edge_index_list, dtype=torch.long)
            edge_attr_tensor = torch.tensor(edge_attr_list, dtype=torch.float32)

        x_tensor = torch.tensor(x_features, dtype=torch.float32)
        y_tensor = torch.tensor([label], dtype=torch.long)

        data = Data(
            x=x_tensor,
            edge_index=edge_index_tensor,
            edge_attr=edge_attr_tensor,
            y=y_tensor,
            node_ids=node_id_list,
            group_id=group_id,
        )
        return data
