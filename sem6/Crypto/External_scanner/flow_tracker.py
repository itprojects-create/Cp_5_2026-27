"""
FlowTracker: Tracks intra- and inter-procedural dataflows, struct/array elements,
pointer dereferences, and constructs directed flow graphs with evidence paths.
"""

import re
from collections import deque
from typing import Dict, List, Optional, Set, Tuple, Any


class EdgeTypeStr(str):
    """String subclass that compares case-insensitively for edge types."""
    def __eq__(self, other):
        if isinstance(other, str):
            return self.lower() == other.lower() or super().__eq__(other)
        return False

    def __hash__(self):
        return hash(self.lower())


class FlowNode:
    def __init__(
        self,
        name: str = "",
        node_type: str = "variable",
        value: Optional[str] = None,
        file_path: Optional[str] = None,
        line_number: Optional[int] = 1,
        id: Optional[str] = None,
    ):
        self.name = name
        self.node_type = node_type
        self.value = value if value is not None else (name if node_type in ("LITERAL", "expression", "argument") else None)
        self.file_path = file_path or ""
        self.line_number = line_number if line_number is not None else 1
        self.id = id if id is not None else name

    def __eq__(self, other):
        if isinstance(other, FlowNode):
            return self.id == other.id
        if isinstance(other, str):
            return other in (self.id, self.name, self.value)
        return False

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return f"FlowNode(id='{self.id}', name='{self.name}', node_type='{self.node_type}')"


class FlowEdge:
    def __init__(
        self,
        source: str = "",
        target: str = "",
        edge_type: str = "flow",
        confidence: float = 1.0,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
    ):
        self.source = source
        self.target = target
        self.source_id = source_id if source_id is not None else source
        self.target_id = target_id if target_id is not None else target
        self.edge_type = EdgeTypeStr(edge_type)
        self.confidence = confidence

    def __repr__(self):
        return f"FlowEdge({self.source_id} -> {self.target_id}, type='{self.edge_type}')"


class NodeDict(dict):
    """Dictionary that indexes FlowNodes by id, and allows lookup by name/value."""
    def __init__(self):
        super().__init__()
        self._alt_keys: Dict[str, FlowNode] = {}

    def add(self, node: FlowNode):
        super().__setitem__(node.id, node)
        if node.name:
            self._alt_keys[node.name] = node
        if node.value:
            self._alt_keys[node.value] = node

    def __setitem__(self, key: str, value: FlowNode):
        super().__setitem__(key, value)
        if hasattr(value, "id"):
            super().__setitem__(value.id, value)
        if hasattr(value, "name") and value.name:
            self._alt_keys[value.name] = value
        if hasattr(value, "value") and value.value:
            self._alt_keys[value.value] = value

    def __getitem__(self, key: str) -> FlowNode:
        if super().__contains__(key):
            return super().__getitem__(key)
        if key in self._alt_keys:
            return self._alt_keys[key]
        raise KeyError(key)

    def __contains__(self, key: object) -> bool:
        return super().__contains__(key) or key in self._alt_keys

    def get(self, key: str, default=None):
        if super().__contains__(key):
            return super().__getitem__(key)
        if key in self._alt_keys:
            return self._alt_keys[key]
        return default


class FlowGraph:
    def __init__(self):
        self.nodes = NodeDict()
        self.edges: List[FlowEdge] = []

    def add_node(self, node: FlowNode) -> FlowNode:
        self.nodes.add(node)
        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        confidence: float = 1.0,
        source: Optional[str] = None,
        target: Optional[str] = None,
    ):
        edge = FlowEdge(
            source=source if source is not None else source_id,
            target=target if target is not None else target_id,
            edge_type=edge_type,
            confidence=confidence,
            source_id=source_id,
            target_id=target_id,
        )
        self.edges.append(edge)

    def get_neighbors(self, key: str) -> List[str]:
        """Returns target ids (and distinct target names) for outgoing edges from key."""
        neighbors = []
        for e in self.edges:
            if key in (e.source, e.source_id):
                neighbors.append(e.target_id)
                if e.target != e.target_id:
                    neighbors.append(e.target)
        return neighbors

    def build_evidence_path(self, source: str, sink: str) -> List[FlowNode]:
        """
        Computes the shortest path from source to sink in the flow graph using BFS.
        """
        for endpoint in (source, sink):
            if endpoint not in self.nodes:
                self.nodes[endpoint] = FlowNode(name=endpoint, id=endpoint, node_type="node")

        start_keys = [source]
        if source in self.nodes and self.nodes[source].name != source:
            start_keys.append(self.nodes[source].name)
        if source in self.nodes and self.nodes[source].id != source:
            start_keys.append(self.nodes[source].id)

        target_keys = {sink}
        if sink in self.nodes:
            target_keys.add(self.nodes[sink].id)
            target_keys.add(self.nodes[sink].name)

        # Run BFS starting strictly with source first
        queue = deque([[source]])
        visited = {source}

        while queue:
            path = queue.popleft()
            curr = path[-1]
            if curr in target_keys and len(path) > 1:
                return [self.nodes.get(nid, FlowNode(name=nid, id=nid)) for nid in path]

            for neighbor in self.get_neighbors(curr):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])

        # If strict start from source didn't find path, try alt start keys
        for alt_start in start_keys[1:]:
            queue = deque([[alt_start]])
            visited = {alt_start}
            while queue:
                path = queue.popleft()
                curr = path[-1]
                if curr in target_keys:
                    return [self.nodes.get(nid, FlowNode(name=nid, id=nid)) for nid in path]
                for neighbor in self.get_neighbors(curr):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(path + [neighbor])

        return []


class FlowTracker:
    """
    Dataflow analysis tracking assignments, parameter passing, return values,
    struct/array accesses, and bounded pointer dereferencing.
    """

    def __init__(self, max_deref_depth: int = 3, max_pointer_depth: Optional[int] = None):
        self.max_deref_depth = max_pointer_depth if max_pointer_depth is not None else max_deref_depth
        self.max_pointer_depth = self.max_deref_depth
        self.flow_graph = FlowGraph()
        self.global_graph = self.flow_graph

    def track_function_call(
        self,
        func_name: str = "",
        args: Optional[List[str]] = None,
        arg3: Any = "",
        line_number: int = 1,
        callee_name: Optional[str] = None,
        caller_args: Optional[List[str]] = None,
        callee_params: Optional[List[str]] = None,
    ) -> FlowGraph:
        """
        Tracks argument-to-parameter dataflow for a function invocation.
        Supports both positional and keyword argument variations.
        """
        name = callee_name if callee_name is not None else func_name
        actual_args = caller_args if caller_args is not None else (args if args is not None else [])

        sub_graph = self.flow_graph
        func_node = FlowNode(id=name, name=name, node_type="function_call", line_number=line_number)
        sub_graph.add_node(func_node)

        params = callee_params if callee_params is not None else (arg3 if isinstance(arg3, list) else None)

        if params is not None:
            for idx, arg in enumerate(actual_args):
                param_name = params[idx] if idx < len(params) else f"param_{idx}"
                arg_id = f"arg_{arg}_{line_number}"
                param_id = f"{name}_param_{param_name}"

                arg_type = "LITERAL" if (arg.startswith('"') or arg.isdigit()) else "VARIABLE"
                arg_node = FlowNode(id=arg_id, name=arg, node_type=arg_type, line_number=line_number)
                param_node = FlowNode(id=param_id, name=param_name, node_type="PARAMETER", line_number=line_number)

                sub_graph.add_node(arg_node)
                sub_graph.add_node(param_node)
                sub_graph.nodes.add(FlowNode(id=arg, name=arg, node_type=arg_type, line_number=line_number))
                sub_graph.add_edge(source_id=arg_id, target_id=param_id, edge_type="ARGUMENT_TO_PARAMETER", source=arg, target=param_name)
        else:
            file_path = str(arg3)
            for idx, arg in enumerate(actual_args):
                arg_node = FlowNode(id=arg, name=arg, node_type="argument", value=arg, file_path=file_path, line_number=line_number)
                sub_graph.add_node(arg_node)
                target_name = f"{name}_arg{idx}"
                sub_graph.add_edge(source_id=arg, target_id=target_name, edge_type="argument_to_parameter", source=arg, target=target_name)

        return sub_graph

    def track_assignment(
        self,
        var_name: str = "",
        expr: str = "",
        file_path: str = "",
        line_number: int = 1,
        lhs: Optional[str] = None,
        rhs: Optional[str] = None,
    ) -> FlowGraph:
        """
        Tracks dataflow from rhs expression to lhs variable.
        """
        sub_graph = self.flow_graph
        actual_lhs = (lhs if lhs is not None else var_name).strip()
        actual_rhs = (rhs if rhs is not None else expr).strip()

        lhs_type = self._classify_expr(actual_lhs)
        rhs_type = self._classify_expr(actual_rhs)

        rhs_id = f"expr_{actual_rhs}_{line_number}"
        lhs_id = f"var_{actual_lhs}_{line_number}"

        rhs_node = FlowNode(id=rhs_id, name=actual_rhs, node_type=rhs_type, value=actual_rhs, file_path=file_path, line_number=line_number)
        lhs_node = FlowNode(id=lhs_id, name=actual_lhs, node_type=lhs_type, value=actual_lhs, file_path=file_path, line_number=line_number)

        sub_graph.add_node(rhs_node)
        sub_graph.add_node(lhs_node)
        sub_graph.nodes.add(FlowNode(id=actual_lhs, name=actual_lhs, node_type=lhs_type, value=actual_lhs, file_path=file_path, line_number=line_number))
        sub_graph.nodes.add(FlowNode(id=actual_rhs, name=actual_rhs, node_type=rhs_type, value=actual_rhs, file_path=file_path, line_number=line_number))

        if "." in actual_rhs or "->" in actual_rhs:
            base_obj = re.split(r"[\.->]+", actual_rhs)[0]
            base_id = f"var_{base_obj}_{line_number}"
            base_node = FlowNode(id=base_id, name=base_obj, node_type="VARIABLE", line_number=line_number)
            sub_graph.add_node(base_node)
            sub_graph.add_edge(source_id=base_id, target_id=rhs_id, edge_type="FLOWS_TO", source=base_obj, target=actual_rhs)
            sub_graph.add_edge(source_id=rhs_id, target_id=lhs_id, edge_type="ASSIGNED_FROM", source=actual_rhs, target=actual_lhs)
        elif "[" in actual_rhs and "]" in actual_rhs:
            base_arr = actual_rhs[: actual_rhs.index("[")].strip()
            arr_id = f"var_{base_arr}_{line_number}"
            arr_node = FlowNode(id=arr_id, name=base_arr, node_type="VARIABLE", line_number=line_number)
            sub_graph.add_node(arr_node)
            sub_graph.add_edge(source_id=arr_id, target_id=rhs_id, edge_type="FLOWS_TO", source=base_arr, target=actual_rhs)
            sub_graph.add_edge(source_id=rhs_id, target_id=lhs_id, edge_type="ASSIGNED_FROM", source=actual_rhs, target=actual_lhs)
        else:
            sub_graph.add_edge(
                source_id=rhs_id,
                target_id=lhs_id,
                edge_type="assignment",
                source=actual_rhs,
                target=actual_lhs,
            )

        return sub_graph

    def track_return_value(
        self,
        func_name: str,
        return_expr: str,
        file_path: str = "",
        line_number: int = 1,
    ) -> FlowGraph:
        """
        Track return value from function: func -> return_expr.
        """
        sub_graph = self.flow_graph
        func_node = FlowNode(id=func_name, name=func_name, node_type="function", file_path=file_path, line_number=line_number)
        ret_node = FlowNode(id=return_expr, name=return_expr, node_type="return_value", value=return_expr, file_path=file_path, line_number=line_number)

        sub_graph.add_node(func_node)
        sub_graph.add_node(ret_node)
        sub_graph.add_edge(source_id=func_name, target_id=return_expr, edge_type="return_value", source=func_name, target=return_expr)
        return sub_graph

    def track_return(
        self,
        caller_var: str,
        func_name: str,
        return_expr: str,
        line_number: int = 1,
    ) -> FlowGraph:
        """
        Tracks return value from callee to caller variable.
        """
        sub_graph = self.flow_graph
        ret_id = f"{func_name}_ret_{line_number}"
        caller_id = f"var_{caller_var}_{line_number}"

        ret_node = FlowNode(id=ret_id, name=return_expr, node_type="RETURN", line_number=line_number)
        caller_node = FlowNode(id=caller_id, name=caller_var, node_type="VARIABLE", line_number=line_number)

        sub_graph.add_node(ret_node)
        sub_graph.add_node(caller_node)
        sub_graph.add_edge(source_id=ret_id, target_id=caller_id, edge_type="RETURNS_TO", source=return_expr, target=caller_var)
        return sub_graph

    def track_struct_field(
        self,
        struct_var: str,
        field_name: str,
        file_path: str = "",
        line_number: int = 1,
    ) -> FlowGraph:
        """
        Track struct field access: struct.field
        """
        sub_graph = self.flow_graph
        struct_node = FlowNode(id=struct_var, name=struct_var, node_type="struct", file_path=file_path, line_number=line_number)
        full_field = f"{struct_var}.{field_name}"
        field_node = FlowNode(id=full_field, name=full_field, node_type="struct_field", file_path=file_path, line_number=line_number)

        sub_graph.add_node(struct_node)
        sub_graph.add_node(field_node)
        sub_graph.add_edge(source_id=struct_var, target_id=full_field, edge_type="field_access", source=struct_var, target=full_field)
        return sub_graph

    def track_pointer_deref(
        self,
        ptr_var: str,
        dest_var: Optional[str] = None,
        depth: int = 0,
        line_number: int = 1,
    ) -> FlowGraph:
        """
        Tracks pointer dereference (*ptr, **ptr).
        Supports (ptr_var, depth) and (ptr_var, dest_var, depth, line_number).
        """
        sub_graph = self.flow_graph
        if dest_var is None:
            if depth > self.max_pointer_depth:
                return sub_graph
            ptr_node = FlowNode(id=ptr_var, name=ptr_var, node_type="pointer")
            deref_name = f"*{ptr_var}"
            deref_node = FlowNode(id=deref_name, name=deref_name, node_type="pointer_deref")
            sub_graph.add_node(ptr_node)
            sub_graph.add_node(deref_node)
            sub_graph.add_edge(source_id=ptr_var, target_id=deref_name, edge_type="pointer_deref", source=ptr_var, target=deref_name)
            return sub_graph

        bounded_depth = min(depth if depth > 0 else 1, self.max_deref_depth)
        prev_id = f"ptr_{ptr_var}_{line_number}"
        prev_node = FlowNode(id=prev_id, name=ptr_var, node_type="VARIABLE", line_number=line_number)
        sub_graph.add_node(prev_node)

        for d in range(1, bounded_depth + 1):
            deref_name = "*" * d + ptr_var
            deref_id = f"deref_{deref_name}_{line_number}"
            deref_node = FlowNode(id=deref_id, name=deref_name, node_type="DEREF", line_number=line_number)
            sub_graph.add_node(deref_node)
            sub_graph.add_edge(source_id=prev_id, target_id=deref_id, edge_type="DEREFERENCES", source=prev_node.name, target=deref_name)
            prev_id = deref_id

        dest_id = f"var_{dest_var}_{line_number}"
        dest_node = FlowNode(id=dest_id, name=dest_var, node_type="VARIABLE", line_number=line_number)
        sub_graph.add_node(dest_node)
        sub_graph.add_edge(source_id=prev_id, target_id=dest_id, edge_type="ASSIGNED_FROM", source=deref_name, target=dest_var)

        return sub_graph

    def build_evidence_path(self, source: str, sink: str) -> List[FlowNode]:
        """
        Builds shortest directed path between source node and sink node in global graph.
        """
        return self.global_graph.build_evidence_path(source, sink)

    def _classify_expr(self, expr: str) -> str:
        expr = expr.strip()
        if expr.startswith('"') or expr.startswith("L\"") or expr.isdigit():
            return "LITERAL"
        if "." in expr or "->" in expr:
            return "STRUCT_FIELD"
        if "[" in expr and "]" in expr:
            return "ARRAY_ELEMENT"
        if expr.startswith("*"):
            return "DEREF"
        return "VARIABLE"
