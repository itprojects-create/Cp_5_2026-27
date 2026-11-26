"""
SemanticEngine: Master coordinator for CryptoFlow semantic analysis pipeline.
Sequences:
  1. Macro Expansion (MacroExpander)
  2. Wrapper Resolution (WrapperResolver)
  3. Pointer Alias Analysis (AliasAnalyzer)
  4. Inter-procedural Dataflow Tracking (FlowTracker)
Integrates the crypto API parameter catalog (crypto_catalog.json) to map key and nonce flows.
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from External_scanner.macro_expander import MacroExpander
from External_scanner.wrapper_resolver import WrapperResolver, Function, WrapperFunction
from External_scanner.alias_analyzer import AliasAnalyzer
from External_scanner.flow_tracker import FlowTracker, FlowNode, FlowGraph, FlowEdge
from External_scanner.c_parser import CParser
from External_scanner.audit_logger import log_audit_trace


CATALOG_PATH = os.path.join(os.path.dirname(__file__), "crypto_catalog.json")


def load_crypto_catalog(path: Optional[str] = None) -> Dict[str, Any]:
    target_path = path or CATALOG_PATH
    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "EVP_EncryptInit_ex": {"key_index": 3, "iv_index": 4, "cipher_index": 1},
        "EVP_DecryptInit_ex": {"key_index": 3, "iv_index": 4, "cipher_index": 1},
        "CryptEncrypt": {"key_index": 0, "flags_index": 3, "data_index": 4},
        "AES_set_encrypt_key": {"key_index": 0, "bits_index": 1, "ctx_index": 2},
    }


@dataclass
class SemanticFinding:
    finding_id: str
    vulnerability_type: str
    cwe: str
    source_var: str
    sink_api: str
    evidence_path: List[str]
    confidence: float = 0.9
    file_path: str = ""
    line_number: int = 1


@dataclass
class AnalysisResult:
    code: str
    expanded_code: str
    functions: List[Function] = field(default_factory=list)
    wrappers: List[WrapperFunction] = field(default_factory=list)
    alias_groups: List[Set[str]] = field(default_factory=list)
    flow_graph: Optional[FlowGraph] = None
    findings: List[SemanticFinding] = field(default_factory=list)
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    label: int = 0


class SemanticEngine:
    """
    Master pipeline controller coordinating MacroExpander, WrapperResolver,
    AliasAnalyzer, and FlowTracker into a unified semantic analysis pass.
    """

    def __init__(
        self,
        catalog_path: Optional[str] = None,
        use_macros: bool = True,
        use_wrappers: bool = True,
        use_aliases: bool = True,
    ):
        self.catalog = load_crypto_catalog(catalog_path)
        self.use_macros = use_macros
        self.use_wrappers = use_wrappers
        self.use_aliases = use_aliases

        self.macro_expander = MacroExpander()
        self.wrapper_resolver = WrapperResolver(crypto_apis=set(self.catalog.keys()))
        self.alias_analyzer = AliasAnalyzer()
        self.flow_tracker = FlowTracker()
        self.c_parser = CParser()

    def analyze(self, code: str, file_path: str = "main.c", label: int = 0, finding_offset: int = 1) -> AnalysisResult:
        """
        Executes the full 4-stage sequential semantic pipeline.
        """
        if self.use_macros:
            expanded_code = self.macro_expander.expand(code)
        else:
            expanded_code = code

        functions = self.wrapper_resolver.extract_functions(expanded_code, file_path)
        if self.use_wrappers:
            wrappers = self.wrapper_resolver.find_wrappers(functions)
        else:
            wrappers = []

        if self.use_aliases:
            self.alias_analyzer.parse_pointer_assignments(expanded_code)
            self.alias_analyzer.find_pointer_assignments(expanded_code)
            alias_groups = self.alias_analyzer.build_alias_sets()
        else:
            alias_groups = []

        self.flow_tracker = FlowTracker()

        graphify_path = os.path.join(os.path.dirname(file_path), "graphify-out", "graph.json")
        if not os.path.exists(graphify_path):
            graphify_path = "graphify-out/graph.json"

        if os.path.exists(graphify_path):
            from External_scanner.graphify_parser import GraphifyParser
            g_parser = GraphifyParser(graphify_path)
            g_parser.parse()
            g_parser.integrate_into_flow_graph(self.flow_tracker.flow_graph)
        
        self._extract_assignments(expanded_code, file_path)

        if self.use_aliases and alias_groups:
            self._propagate_aliases(alias_groups)

        findings = self._detect_crypto_misuse(expanded_code, functions, wrappers, file_path, finding_offset=finding_offset)

        node_dicts, edge_dicts = self._serialize_graph(functions, wrappers, findings, file_path)

        return AnalysisResult(
            code=code,
            expanded_code=expanded_code,
            functions=functions,
            wrappers=wrappers,
            alias_groups=alias_groups,
            flow_graph=self.flow_tracker.global_graph,
            findings=findings,
            nodes=node_dicts,
            edges=edge_dicts,
            label=1 if findings else label,
        )

    def _extract_assignments(self, code: str, file_path: str):
        result = self.c_parser.parse(code)
        for a in result.assignments:
            if not a.lhs or not a.rhs:
                continue
            self.flow_tracker.track_assignment(a.lhs, a.rhs, file_path=file_path, line_number=a.line_number)

    def _propagate_aliases(self, alias_groups: List[Set[str]]):
        for group in alias_groups:
            group_list = list(group)
            for i in range(len(group_list)):
                for j in range(i + 1, len(group_list)):
                    v1, v2 = group_list[i], group_list[j]
                    if v1 in self.flow_tracker.flow_graph.nodes and v2 in self.flow_tracker.flow_graph.nodes:
                        self.flow_tracker.flow_graph.add_edge(v1, v2, "ALIASES", 0.95, source=v1, target=v2)
                        self.flow_tracker.flow_graph.add_edge(v2, v1, "ALIASES", 0.95, source=v2, target=v1)

    def _build_edges_by_target(self) -> Dict[str, List[Any]]:
        edges_by_target: Dict[str, List[Any]] = {}
        for edge in self.flow_tracker.flow_graph.edges:
            tgt = edge.target if edge.target else edge.target_id
            node = self.flow_tracker.flow_graph.nodes.get(tgt, None)
            keys = {tgt, f"var_{tgt}"}
            if node is not None and node.name:
                keys.add(node.name)
            for k in keys:
                edges_by_target.setdefault(k, []).append(edge)
        return edges_by_target

    def _is_value_hardcoded(self, var_name: str, edges_by_target: Dict[str, List[Any]]) -> Tuple[bool, List[str]]:
        if var_name.startswith('"') or var_name.startswith('{') or var_name.startswith("0x") or var_name.isdigit():
            return True, [var_name]

        candidate_vars = {var_name}
        if self.use_aliases:
            candidate_vars.update(self.alias_analyzer.get_aliases(var_name))

        for cand in candidate_vars:
            for edge in edges_by_target.get(cand, []):
                src = edge.source if edge.source else edge.source_id
                src_node = self.flow_tracker.flow_graph.nodes.get(src, None)
                src_val = getattr(src_node, "value", src) or src
                if (
                    src.startswith('"')
                    or '"' in src
                    or src.startswith('{')
                    or '{' in src
                    or (src_val and ('"' in src_val or '{' in src_val or src_val.startswith('0x')))
                ):
                    return True, [src_val or src, cand, var_name]

        return False, []

    def _is_value_bad_source(self, var_name: str, edges_by_target: Dict[str, List[Any]], bad_sources: List[str]) -> Tuple[bool, List[str]]:
        candidate_vars = {var_name}
        if self.use_aliases:
            candidate_vars.update(self.alias_analyzer.get_aliases(var_name))

        for cand in candidate_vars:
            for edge in edges_by_target.get(cand, []):
                src = edge.source if edge.source else edge.source_id
                src_node = self.flow_tracker.flow_graph.nodes.get(src, None)
                src_val = getattr(src_node, "value", src) or src
                for bad_src in bad_sources:
                    if bad_src in src or (src_val and bad_src in src_val):
                        return True, [src_val or src, cand, var_name]
        return False, []

    def _detect_crypto_misuse(
        self,
        code: str,
        functions: List[Function],
        wrappers: List[WrapperFunction],
        file_path: str,
        finding_offset: int = 1,
    ) -> List[SemanticFinding]:
        findings: List[SemanticFinding] = []
        finding_count = finding_offset

        wrapper_map = {w.name: w for w in wrappers}
        edges_by_target = self._build_edges_by_target()
        cwe_rules = self.catalog.get("CWE_RULES", {})

        for fn in functions:
            for call in fn.calls:
                api_name = call.callee_name
                target_api = api_name
                
                if api_name in self.catalog and api_name != "CWE_RULES":
                    api_config = self.catalog[api_name]
                elif api_name in wrapper_map:
                    sub_w = wrapper_map[api_name]
                    target_api = sub_w.target_crypto_api
                    if target_api in self.catalog:
                        api_config = self.catalog[target_api]
                    else:
                        continue
                else:
                    continue

                for rule_id, rule_config in cwe_rules.items():
                    for target_param in rule_config.get("target", []):
                        target_key_idx = api_config.get(target_param)
                        if target_key_idx is None:
                            continue

                        call_arg_idx = target_key_idx
                        if api_name in wrapper_map:
                            param_to_crypto = getattr(wrapper_map[api_name], "param_to_crypto_arg", {})
                            found_mapped = False
                            for p_idx, c_idx in param_to_crypto.items():
                                if c_idx == target_key_idx:
                                    call_arg_idx = p_idx
                                    found_mapped = True
                                    break
                            if not found_mapped:
                                continue

                        if call_arg_idx is not None and call_arg_idx < len(call.arguments):
                            key_arg = call.arguments[call_arg_idx].strip()
                            is_flagged = False
                            path_str = []
                            vuln_type = rule_config.get("type", "Unknown")

                            if rule_id == "CWE-321" or rule_id == "CWE-329":
                                is_flagged, path_str = self._is_value_hardcoded(key_arg, edges_by_target)
                                vuln_type = "Hard-coded Cryptographic Key" if rule_id == "CWE-321" else "Hard-coded Nonce/IV"
                            elif rule_id == "CWE-338":
                                is_flagged, path_str = self._is_value_bad_source(key_arg, edges_by_target, rule_config.get("bad_sources", []))
                                vuln_type = "Weak PRNG Source"
                            elif rule_id == "CWE-327":
                                is_flagged, path_str = self._is_value_bad_source(key_arg, edges_by_target, rule_config.get("bad_values", []))
                                vuln_type = "Broken Cryptographic Algorithm"
                                if not is_flagged:
                                    for bad_val in rule_config.get("bad_values", []):
                                        if bad_val in key_arg:
                                            is_flagged = True
                                            path_str = [key_arg]
                                            break

                            if is_flagged:
                                # Fix 1: Properly append the 'api_' prefix to align with node IDs in serialization
                                api_node_id = f"api_{target_api}"
                                evidence = path_str + [api_node_id]
                                finding_id = f"CF-{finding_count:03d}"
                                findings.append(
                                    SemanticFinding(
                                        finding_id=finding_id,
                                        vulnerability_type=vuln_type,
                                        cwe=rule_id,
                                        source_var=key_arg,
                                        sink_api=target_api,
                                        evidence_path=evidence,
                                        confidence=0.95,
                                        file_path=file_path,
                                        line_number=call.line_number,
                                    )
                                )
                                log_audit_trace(finding_id, rule_id, key_arg, target_api, evidence)
                                finding_count += 1

        return findings

    def _serialize_graph(
        self,
        functions: List[Function],
        wrappers: List[WrapperFunction],
        findings: List[SemanticFinding],
        file_path: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        import collections

        node_dicts: List[Dict[str, Any]] = []
        edge_dicts: List[Dict[str, Any]] = []
        seen_nodes: Set[str] = set()
        function_names = {fn.name for fn in functions}

        # Identify all nodes caught in the evidence path to force KEY tag assignment
        evidence_nodes = set()
        for f in findings:
            evidence_nodes.update(f.evidence_path)

        file_node_id = f"file_{file_path}"
        node_dicts.append({
            "id": file_node_id,
            "type": "FILE",
            "confidence": 1.0,
            "line_number": 1,
            "file_path": file_path,
        })
        seen_nodes.add(file_node_id)

        for fn in functions:
            fn_id = f"func_{fn.name}"
            n_type = "WRAPPER" if any(w.name == fn.name for w in wrappers) else "FUNCTION"
            node_dicts.append({
                "id": fn_id,
                "type": n_type,
                "confidence": 0.9,
                "line_number": fn.line_number,
                "file_path": file_path,
            })
            seen_nodes.add(fn_id)
            edge_dicts.append({"source": file_node_id, "target": fn_id, "type": "CONTAINS"})

            for p in getattr(fn, "parameters", []):
                clean_p = p.split()[-1].strip("*& ")
                if clean_p:
                    param_id = f"param_{fn.name}_{clean_p}"
                    if param_id not in seen_nodes:
                        # Force KEY tag if involved in vulnerability flow
                        p_type = "KEY" if param_id in evidence_nodes else "PARAMETER"
                        node_dicts.append({
                            "id": param_id,
                            "type": p_type,
                            "confidence": 0.85,
                            "line_number": fn.line_number,
                            "file_path": file_path,
                        })
                        seen_nodes.add(param_id)
                    edge_dicts.append({"source": fn_id, "target": param_id, "type": "CONTAINS"})

            for call in getattr(fn, "calls", []):
                callee = call.callee_name
                if callee in function_names:
                    callee_id = f"func_{callee}"
                    edge_dicts.append({"source": fn_id, "target": callee_id, "type": "CALLS"})
                elif callee in self.catalog and callee != "CWE_RULES":
                    api_id = f"api_{callee}"
                    if api_id not in seen_nodes:
                        node_dicts.append({
                            "id": api_id,
                            "type": "CRYPTO_API",
                            "confidence": 1.0,
                            "line_number": call.line_number,
                            "file_path": file_path,
                            "api_role": "key" if "init" in callee.lower() else "algorithm",
                            "sink_type": "crypto",
                        })
                        seen_nodes.add(api_id)
                    edge_dicts.append({"source": fn_id, "target": api_id, "type": "CALLS"})

        for nid, node in self.flow_tracker.flow_graph.nodes.items():
            if nid not in seen_nodes:
                # Fix 2: Explicitly upgrade node semantics based on deterministic evidence path
                if nid in evidence_nodes:
                    nt = "KEY"
                elif getattr(node, "node_type", "").upper() == "LITERAL" or nid.startswith('"') or nid.startswith('{'):
                    nt = "LITERAL"
                else:
                    nt = "KEY" if "key" in nid.lower() or "secret" in nid.lower() else "VARIABLE"

                n_file = getattr(node, "file_path", file_path)
                n_line = getattr(node, "line_number", 1)
                node_dicts.append({
                    "id": nid,
                    "type": nt,
                    "confidence": 0.9,
                    "line_number": n_line,
                    "file_path": n_file,
                })
                seen_nodes.add(nid)

                for fn in functions:
                    if fn.line_number <= n_line:
                        edge_dicts.append({"source": f"func_{fn.name}", "target": nid, "type": "CONTAINS"})
                        break

        for edge in self.flow_tracker.flow_graph.edges:
            src = edge.source if edge.source in seen_nodes else edge.source_id
            tgt = edge.target if edge.target in seen_nodes else edge.target_id
            if src in seen_nodes and tgt in seen_nodes:
                edge_dicts.append({"source": src, "target": tgt, "type": "FLOWS_TO"})

        for finding in findings:
            api_id = f"api_{finding.sink_api}"
            if api_id not in seen_nodes:
                node_dicts.append({
                    "id": api_id,
                    "type": "CRYPTO_API",
                    "confidence": 1.0,
                    "line_number": finding.line_number,
                    "file_path": file_path,
                    "sink_type": "crypto",
                })
                seen_nodes.add(api_id)
            if finding.source_var in seen_nodes:
                edge_dicts.append({"source": finding.source_var, "target": api_id, "type": "USES_AS_KEY"})
            elif finding.evidence_path and finding.evidence_path[-2] in seen_nodes:
                edge_dicts.append({"source": finding.evidence_path[-2], "target": api_id, "type": "USES_AS_KEY"})

        adjacency: Dict[str, List[str]] = collections.defaultdict(list)
        for e in edge_dicts:
            adjacency[e["source"]].append(e["target"])

        depths: Dict[str, int] = {file_node_id: 0}
        queue = collections.deque([file_node_id])

        while queue:
            curr = queue.popleft()
            curr_depth = depths[curr]
            for nxt in adjacency.get(curr, []):
                if nxt not in depths:
                    depths[nxt] = curr_depth + 1
                    queue.append(nxt)

        max_depth = max(depths.values()) if depths else 1
        max_depth = max(max_depth, 1)

        for n in node_dicts:
            d = depths.get(n["id"], max_depth)
            n["call_depth"] = d
            n["call_depth_norm"] = min(float(d) / float(max_depth), 1.0)

        return node_dicts, edge_dicts


def main():
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="CryptoFlow SemanticEngine: Analyze C/C++ code for cryptographic misuse vulnerabilities."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="Day5_test",
        help="Path to a C/C++ source file or directory of source files (default: Day5_test).",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        default=True,
        help="Generate 3D Plotly interactive visualizations with click-to-code IDE links (default: True).",
    )
    parser.add_argument(
        "--vis-dir",
        default="visualizations",
        help="Directory to save Plotly HTML visualizations (default: visualizations).",
    )
    parser.add_argument(
        "--catalog",
        default=None,
        help="Path to custom crypto_catalog.json.",
    )

    args = parser.parse_args()

    target_path = Path(args.target)
    if not target_path.exists():
        print(f"Error: Target path '{target_path}' does not exist.")
        sys.exit(1)

    if target_path.is_file():
        files_to_scan = [target_path]
    else:
        exts = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}
        files_to_scan = sorted([p for p in target_path.rglob("*") if p.suffix.lower() in exts])

    if not files_to_scan:
        print(f"No C/C++ files found in '{target_path}'.")
        return

    print("=" * 80)
    print(f"CryptoFlow SemanticEngine scanning {len(files_to_scan)} file(s) in: {target_path}")
    print("=" * 80)

    engine = SemanticEngine(catalog_path=args.catalog)
    total_findings = []
    generated_visualizations = []

    for file_p in files_to_scan:
        rel_path = file_p.as_posix()
        try:
            with open(file_p, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()
        except Exception as e:
            print(f"[!] Error reading {rel_path}: {e}")
            continue

        result = engine.analyze(code, file_path=rel_path, finding_offset=len(total_findings) + 1)
        verdict = "VULNERABLE (Confirmed Flow)" if result.findings else "CLEAN"
        print(f"\n[-] File: {rel_path} --> {verdict}")

        for finding in result.findings:
            total_findings.append(finding)
            clean_source = re.sub(r"\s+", " ", finding.source_var).strip()
            if len(clean_source) > 60:
                clean_source = clean_source[:57] + "..."
            clean_proof = " -> ".join(
                (re.sub(r"\s+", " ", p).strip()[:40] + "...") if len(re.sub(r"\s+", " ", p).strip()) > 40 else re.sub(r"\s+", " ", p).strip()
                for p in finding.evidence_path
            )
            print(f"    * [{finding.finding_id}] {finding.cwe}: {finding.vulnerability_type}")
            print(f"      Source: {clean_source} (line {finding.line_number})")
            print(f"      Sink:   {finding.sink_api}")
            print(f"      Proof:  {clean_proof}")

            if args.visualize:
                try:
                    from External_scanner.graph_builder import GraphBuilder
                    from agents.visualizer import Visualizer

                    gb = GraphBuilder()
                    g_data = gb.build_graph({"nodes": result.nodes, "edges": result.edges, "label": result.label})
                    vis = Visualizer(output_dir=args.vis_dir)
                    html_file = vis.generate(
                        g_data,
                        evidence_path=finding.evidence_path,
                        finding_id=finding.finding_id,
                        finding_details={
                            "cwe": finding.cwe,
                            "type": finding.vulnerability_type,
                            "file": rel_path,
                            "line": finding.line_number,
                        },
                    )
                    generated_visualizations.append((finding.finding_id, html_file))
                    print(f"      3D Visualizer: {html_file}")
                except Exception as ex:
                    print(f"      [!] Visualization skipped: {ex}")

    print("\n" + "=" * 80)
    print("SCAN COMPLETE SUMMARY")
    print("=" * 80)
    print(f"Total files scanned:    {len(files_to_scan)}")
    print(f"Total findings:         {len(total_findings)}")
    print(f"Audit trace log:        data/log/audit_trace.log")
    if generated_visualizations:
        print(f"Visualizations ({len(generated_visualizations)}):")
        for fid, path in generated_visualizations:
            print(f"  - {fid}: {path}")
    print("=" * 80)


if __name__ == "__main__":
    main()