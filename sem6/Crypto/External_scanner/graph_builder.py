"""
GraphBuilder: Constructs PyTorch Geometric Data objects from semantic analysis of C/C++ code.
Supports node/edge feature tensor encoding, batch processing, and disk serialization (.pt).
"""

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any

import torch
from torch_geometric.data import Data

from External_scanner.graph_schema import (
    NodeType,
    EdgeType,
    encode_node_features,
    encode_edge_features,
    NODE_FEATURE_DIM,
    EDGE_FEATURE_DIM,
    NODE_TYPE_TO_IDX,
)
from External_scanner.macro_expander import MacroExpander
from External_scanner.wrapper_resolver import WrapperResolver, Function, WrapperFunction
from External_scanner.flow_tracker import FlowTracker, FlowNode, FlowGraph
from External_scanner.alias_analyzer import AliasAnalyzer
from External_scanner.safe_io import safe_load_graph


@dataclass
class CodeElement:
    id: str
    name: str
    node_type: str
    api_role: str = "unknown"
    source_type: str = "unknown"
    sink_type: str = "none"
    line_number: int = 1
    confidence: float = 1.0
    file_path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class GraphBuilder:
    """
    Transforms code and semantic analysis results into PyTorch Geometric Data objects.
    """

    def __init__(self):
        self.node_types = NodeType
        self.edge_types = EdgeType
        self.macro_expander = MacroExpander()
        self.wrapper_resolver = WrapperResolver()
        self.alias_analyzer = AliasAnalyzer()

    def build_graph(self, analysis_result: Dict) -> Data:
        """
        Build PyTorch Geometric graph from analysis result dictionary.
        """
        nodes = analysis_result.get('nodes', [])
        edges = analysis_result.get('edges', [])

        node_features = []
        node_ids = []
        node_file_paths = []
        node_lines = []

        for node in nodes:
            features = self._encode_node_features(node)
            node_features.append(features)
            node_ids.append(node['id'])
            node_file_paths.append(node.get('file_path', ''))
            node_lines.append(node.get('line_number', 1))

        x = torch.tensor(node_features, dtype=torch.float)

        node_id_to_idx = {nid: idx for idx, nid in enumerate(node_ids)}

        edge_index = []
        edge_attr = []

        for edge in edges:
            source_idx = node_id_to_idx.get(edge.get('source'))
            target_idx = node_id_to_idx.get(edge.get('target'))
            if source_idx is None or target_idx is None:
                continue

            edge_index.append([source_idx, target_idx])

            edge_features = self._encode_edge_features(edge)
            edge_attr.append(edge_features)

        if not edge_index:
            edge_index_tensor = torch.empty((2, 0), dtype=torch.long)
            edge_attr_tensor = torch.empty((0, EDGE_FEATURE_DIM), dtype=torch.float)
        else:
            edge_index_tensor = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
            edge_attr_tensor = torch.tensor(edge_attr, dtype=torch.float)

        y = torch.tensor([analysis_result.get('label', 0)], dtype=torch.long)

        return Data(
            x=x,
            edge_index=edge_index_tensor,
            edge_attr=edge_attr_tensor,
            y=y,
            node_ids=node_ids,
            file_paths=node_file_paths,
            line_numbers=node_lines,
        )

    def _encode_node_features(self, node: Dict) -> List[float]:
        node_type = str(node.get('type', 'VARIABLE')).upper()
        if node_type not in NODE_TYPE_TO_IDX:
            node_type = 'VARIABLE'
        return encode_node_features(
            node_type=node_type,
            api_role=node.get('api_role', 'unknown'),
            source_type=node.get('source_type', 'unknown'),
            sink_type=node.get('sink_type', 'none'),
            line_number=node.get('line_number', 1),
            confidence=node.get('confidence', 0.5),
            call_depth_normalized=node.get('call_depth_norm', 0.0),
        )

    def _encode_edge_features(self, edge: Dict) -> List[float]:
        edge_type = str(edge.get('type', 'FLOWS_TO')).upper()
        return encode_edge_features(edge_type=edge_type, confidence=edge.get('confidence', 1.0))

    def build_from_source(
        self,
        code: str,
        file_path: str = "main.c",
        label: int = 0,
    ) -> Data:
        """
        Parses source code through Macro, Wrapper, Flow, and Alias analysis,
        producing a typed PyTorch Geometric Data graph.
        """
        # 1. Macro Expansion
        expanded_code = self.macro_expander.expand(code)

        # 2. Wrapper Resolution
        functions = self.wrapper_resolver.parse_functions(expanded_code)
        call_graph = self.wrapper_resolver.build_call_graph(functions)

        # 3. Flow Tracking & Alias Analysis
        flow_tracker = FlowTracker()
        self.alias_analyzer.find_pointer_assignments(expanded_code)
        self.alias_analyzer.build_alias_sets()

        # Track assignments from code
        self._extract_source_flows(expanded_code, flow_tracker, file_path)

        # Connect call arguments to callee parameters
        for fn in functions:
            for call in fn.calls:
                callee_params = []
                if call.callee_name in call_graph.functions:
                    callee_params = call_graph.functions[call.callee_name].parameters
                flow_tracker.track_function_call(
                    callee_name=call.callee_name,
                    caller_args=call.arguments,
                    callee_params=callee_params,
                    line_number=call.line_number,
                )

        # Integrate alias relationships
        self.alias_analyzer.integrate_with_flow_tracker(flow_tracker)

        # 4. Construct CodeElements
        code_elements: List[CodeElement] = []
        node_id_to_idx: Dict[str, int] = {}

        # Add File Node
        file_elem = CodeElement(
            id=f"file_{file_path}",
            name=file_path,
            node_type=NodeType.FILE.value,
            line_number=1,
            file_path=file_path,
        )
        code_elements.append(file_elem)

        # Add Functions & Wrappers
        for fn in functions:
            is_wrapper = fn.name in call_graph.wrappers
            ntype = NodeType.WRAPPER.value if is_wrapper else NodeType.FUNCTION.value
            fn_elem = CodeElement(
                id=f"func_{fn.name}",
                name=fn.name,
                node_type=ntype,
                line_number=fn.line_number,
                file_path=file_path,
            )
            code_elements.append(fn_elem)

        # Add Flow Nodes
        for fn_id, fnode in flow_tracker.global_graph.nodes.items():
            ntype = fnode.node_type
            api_role = "unknown"
            src_type = "unknown"
            snk_type = "none"

            # Identify key / literal semantics
            lower_name = fnode.name.lower()
            if any(k in lower_name for k in ["key", "secret", "password", "token", "passwd"]):
                api_role = "key"
                ntype = NodeType.KEY.value

            if fnode.node_type == "LITERAL":
                src_type = "hard-coded"
                ntype = NodeType.LITERAL.value

            if fnode.node_type == "SINK" or any(api in fnode.name for api in self.wrapper_resolver.crypto_apis):
                snk_type = "crypto"
                ntype = NodeType.CRYPTO_API.value

            elem = CodeElement(
                id=fn_id,
                name=fnode.name,
                node_type=ntype,
                api_role=api_role,
                source_type=src_type,
                sink_type=snk_type,
                line_number=fnode.line_number,
                file_path=file_path,
            )
            code_elements.append(elem)

        # Index nodes
        for idx, elem in enumerate(code_elements):
            node_id_to_idx[elem.id] = idx

        # 5. Build Node Features Tensor
        x_tensor, node_ids_list = self.create_nodes(code_elements)

        # 6. Build Edges and Edge Features
        edge_index, edge_attr = self.create_edges(node_id_to_idx, flow_tracker.global_graph, functions, file_elem.id)

        # 7. Create PyG Data object
        y_tensor = torch.tensor([label], dtype=torch.long)
        pyg_data = Data(
            x=x_tensor,
            edge_index=edge_index,
            edge_attr=edge_attr,
            y=y_tensor,
            node_ids=node_ids_list,
            file_paths=[elem.file_path for elem in code_elements],
            line_numbers=[elem.line_number for elem in code_elements],
        )
        return pyg_data

    def create_nodes(self, elements: List[CodeElement]) -> Tuple[torch.Tensor, List[str]]:
        features = []
        node_ids = []
        for elem in elements:
            feat = encode_node_features(
                node_type=elem.node_type,
                api_role=elem.api_role,
                source_type=elem.source_type,
                sink_type=elem.sink_type,
                line_number=elem.line_number,
                confidence=elem.confidence,
            )
            features.append(feat)
            node_ids.append(elem.id)

        x = torch.tensor(features, dtype=torch.float32)
        return x, node_ids

    def create_edges(
        self,
        node_id_to_idx: Dict[str, int],
        flow_graph: FlowGraph,
        functions: List[Function],
        file_node_id: str,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        sources: List[int] = []
        targets: List[int] = []
        attrs: List[List[float]] = []

        def add_edge_entry(src_id: str, tgt_id: str, edge_type: str, param_idx: int = -1, conf: float = 1.0):
            if src_id in node_id_to_idx and tgt_id in node_id_to_idx:
                s_idx = node_id_to_idx[src_id]
                t_idx = node_id_to_idx[tgt_id]
                sources.append(s_idx)
                targets.append(t_idx)
                attrs.append(encode_edge_features(edge_type, param_idx, conf))

        # 1. Flow Graph Edges
        for edge in flow_graph.edges:
            add_edge_entry(edge.source_id, edge.target_id, edge.edge_type, conf=edge.confidence)

        # 2. File CONTAINS Function
        for fn in functions:
            fn_id = f"func_{fn.name}"
            add_edge_entry(file_node_id, fn_id, EdgeType.CONTAINS.value)
            # Function CALLS
            for call in fn.calls:
                target_fn_id = f"func_{call.callee_name}"
                add_edge_entry(fn_id, target_fn_id, EdgeType.CALLS.value, conf=0.9)

        if not sources:
            # Avoid empty edge tensor shape issues in PyG
            edge_index = torch.empty((2, 0), dtype=torch.long)
            edge_attr = torch.empty((0, EDGE_FEATURE_DIM), dtype=torch.float32)
        else:
            edge_index = torch.tensor([sources, targets], dtype=torch.long)
            edge_attr = torch.tensor(attrs, dtype=torch.float32)

        return edge_index, edge_attr

    def build_batch(self, sources: List[Tuple[str, str, int]]) -> Data:
        """
        Builds a combined graph for multiple files (file_code, file_path, label).
        """
        from torch_geometric.data import Batch
        graphs = [self.build_from_source(code, path, label) for code, path, label in sources]
        return Batch.from_data_list(graphs)

    def save_graph(self, graph: Data, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        torch.save(graph, path)

    def load_graph(self, path: str) -> Data:
        return safe_load_graph(path)

    def _extract_source_flows(self, code: str, tracker: FlowTracker, file_path: str):
        """
        Parses variable declarations and assignments from C/C++ source code using the AST parser.
        """
        from External_scanner.c_parser import CParser
        result = CParser().parse(code)
        for a in result.assignments:
            if not a.lhs or not a.rhs:
                continue
            tracker.track_assignment(a.lhs, a.rhs, file_path=file_path, line_number=a.line_number)
