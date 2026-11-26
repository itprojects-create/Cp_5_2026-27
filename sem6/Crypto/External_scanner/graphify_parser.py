import json
import os
from typing import Dict, List, Any

class GraphifyParser:
    def __init__(self, json_path: str = "graphify-out/graph.json"):
        self.json_path = json_path
        self.nodes = []
        self.edges = []
        
    def parse(self) -> Dict[str, Any]:
        """Parses graphify output and returns nodes and edges."""
        if not os.path.exists(self.json_path):
            print(f"Warning: Graphify output {self.json_path} not found.")
            return {"nodes": [], "edges": []}
            
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        self.nodes = data.get("nodes", [])
        self.edges = data.get("edges", [])
        
        return {
            "nodes": self.nodes,
            "edges": self.edges
        }
        
    def integrate_into_flow_graph(self, flow_graph):
        """
        Integrates Graphify nodes and edges into the given FlowGraph.
        """
        from External_scanner.flow_tracker import FlowNode, FlowEdge
        
        # We support Graphify nodes with ('id', 'type', 'name', 'file', 'line')
        # as well as Graphify AST format ('id', 'label', 'file_type', 'source_file', 'source_location')
        for n in self.nodes:
            file_path = n.get("file") or n.get("source_file") or ""
            line_num = n.get("line")
            if line_num is None:
                src_loc = n.get("source_location") or ""
                if src_loc.startswith("L"):
                    try:
                        line_num = int(src_loc[1:])
                    except ValueError:
                        line_num = 1
                else:
                    line_num = 1
            
            source_ref = n.get("Source", "")
            if source_ref and not file_path:
                # e.g., 'Source: routing.py L2210'
                parts = source_ref.replace("Source:", "").strip().split(" L")
                if len(parts) == 2:
                    file_path = parts[0].strip()
                    try:
                        line_num = int(parts[1].strip())
                    except ValueError:
                        pass
                        
            node_name = n.get("name") or n.get("label") or str(n.get("id", ""))
            raw_type = n.get("type") or n.get("file_type") or "variable"
            node = FlowNode(
                id=str(n.get("id", "")),
                name=node_name,
                node_type=raw_type,
                file_path=file_path,
                line_number=line_num
            )
            flow_graph.add_node(node)
            
        for e in self.edges:
            edge_rel = e.get("type") or e.get("relation") or "flow"
            conf_tag = e.get("tag") or e.get("confidence") or ""
            flow_graph.add_edge(
                source_id=str(e.get("source", "")),
                target_id=str(e.get("target", "")),
                edge_type=edge_rel,
                confidence=1.0 if conf_tag == "EXTRACTED" else 0.8
            )
