"""
visualizer.py: Generates interactive 3D Plotly visualizations of interprocedural code graphs,
hierarchically arranged by call depth, colored by semantic node/edge types, sized by HGNN
attention weights, and augmented with a security analysis sidebar.
"""

import math
import os
from typing import Dict, List, Optional, Any, Tuple

import plotly.graph_objects as go
import torch
from torch_geometric.data import Data

from External_scanner.graph_schema import NodeType, EdgeType


# --- Color Palettes ---
NODE_TYPE_COLORS = {
    NodeType.FILE.value: "#ffffff",          # Pure White (Root)
    NodeType.FUNCTION.value: "#06b6d4",      # Cyan
    NodeType.PARAMETER.value: "#14b8a6",     # Teal
    NodeType.VARIABLE.value: "#94a3b8",      # Slate / Gray
    NodeType.LITERAL.value: "#f97316",       # Orange
    NodeType.KEY.value: "#ff00ff",           # Magenta/Hot Pink (Target)
    NodeType.NONCE.value: "#ec4899",         # Pink
    NodeType.CRYPTO_API.value: "#ffff00",    # Neon Yellow (Sink)
    NodeType.RANDOM_SOURCE.value: "#84cc16", # Lime
    NodeType.WRAPPER.value: "#00ffff",       # Bright Cyan
    NodeType.SINK.value: "#f43f5e",          # Rose
}

EDGE_TYPE_COLORS = {
    EdgeType.CONTAINS.value: "#a855f7",              
    EdgeType.CALLS.value: "#3b82f6",                 
    EdgeType.ARGUMENT_TO_PARAMETER.value: "#06b6d4", 
    EdgeType.RETURNS_TO.value: "#10b981",            
    EdgeType.ASSIGNED_FROM.value: "#f59e0b",         
    EdgeType.FLOWS_TO.value: "#f97316",              
    EdgeType.ALIASES.value: "#ec4899",               
    EdgeType.USES_AS_KEY.value: "#ef4444",           
    EdgeType.USES_AS_NONCE.value: "#d946ef",         
    EdgeType.EXPOSES_TO.value: "#e11d48",            
}

NODE_TYPE_LIST = [t.value for t in NodeType]
EDGE_TYPE_LIST = [e.value for e in EdgeType]


class Visualizer:
    """
    Renders 3D interactive HTML visualizations of interprocedural cryptographic graphs.
    """

    def __init__(self, output_dir: str = "visualizations"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _infer_node_type(self, graph: Data, idx: int, nid: str) -> str:
        """Determines the string node type from tensor one-hot or name heuristics."""
        if graph.x is not None and graph.x.size(0) > idx and graph.x.size(1) >= 11:
            slice_11 = graph.x[idx, :11]
            argmax = torch.argmax(slice_11).item()
            if slice_11[argmax] > 0.5 and argmax < len(NODE_TYPE_LIST):
                return NODE_TYPE_LIST[argmax]

        nid_low = nid.lower()
        if nid_low.startswith("file_"):
            return NodeType.FILE.value
        elif nid_low.startswith("func_"):
            return NodeType.FUNCTION.value
        elif "key" in nid_low or "secret" in nid_low or "pwd" in nid_low:
            return NodeType.KEY.value
        elif nid_low.startswith("lit_"):
            return NodeType.LITERAL.value
        elif "wrapper" in nid_low:
            return NodeType.WRAPPER.value
        elif "crypto" in nid_low or "crypt" in nid_low or "aes" in nid_low or "sha" in nid_low:
            return NodeType.CRYPTO_API.value
        elif "param" in nid_low:
            return NodeType.PARAMETER.value
        return NodeType.VARIABLE.value

    def _infer_edge_type(self, graph: Data, edge_idx: int) -> str:
        """Determines string edge type from edge_attr tensor one-hot."""
        if (
            graph.edge_attr is not None
            and graph.edge_attr.size(0) > edge_idx
            and graph.edge_attr.size(1) >= 10
        ):
            slice_10 = graph.edge_attr[edge_idx, :10]
            argmax = torch.argmax(slice_10).item()
            if slice_10[argmax] > 0.5 and argmax < len(EDGE_TYPE_LIST):
                return EDGE_TYPE_LIST[argmax]
        return EdgeType.FLOWS_TO.value

    def generate(
        self,
        graph: Data,
        evidence_path: Optional[List[str]] = None,
        finding_id: str = "CF-001",
        attention_weights: Optional[torch.Tensor] = None,
        finding_details: Optional[Dict[str, Any]] = None,
    ) -> str:
        num_nodes = graph.x.size(0) if graph.x is not None else 0
        if num_nodes == 0:
            output_file = os.path.join(self.output_dir, f"{finding_id}.html")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("<html><body><h3>Empty graph, no nodes to visualize.</h3></body></html>")
            return output_file

        evidence_set = set(evidence_path or [])
        node_ids = getattr(graph, "node_ids", [f"node_{i}" for i in range(num_nodes)])

        # Subgraph Filter: Keep Evidence Path + 1-Hop Neighbors for massive graphs
        keep_indices = set(range(num_nodes))
        if evidence_set and num_nodes > 150:
            keep_indices = set()
            ev_indices = {i for i, nid in enumerate(node_ids) if nid in evidence_set}
            keep_indices.update(ev_indices)
            if graph.edge_index is not None:
                for e in range(graph.edge_index.size(1)):
                    src, tgt = graph.edge_index[0, e].item(), graph.edge_index[1, e].item()
                    if src in ev_indices: keep_indices.add(tgt)
                    if tgt in ev_indices: keep_indices.add(src)

        attn_list = [0.0] * num_nodes
        if attention_weights is not None:
            if isinstance(attention_weights, torch.Tensor):
                attn_flat = attention_weights.detach().cpu().flatten().tolist()
            else:
                attn_flat = list(attention_weights)
            for i in range(min(num_nodes, len(attn_flat))):
                attn_list[i] = float(attn_flat[i])

        has_depth = graph.x is not None and graph.x.size(1) >= 34
        has_line = graph.x is not None and graph.x.size(1) >= 31

        # Calculate coordinates for ALL nodes to preserve edge indexing
        all_xs, all_ys, all_zs = [0.0]*num_nodes, [0.0]*num_nodes, [0.0]*num_nodes
        layer_counts: Dict[int, int] = {}
        layer_indices: Dict[int, int] = {}

        for idx in range(num_nodes):
            if idx not in keep_indices: continue
            depth_val = graph.x[idx, 33].item() if has_depth else (idx % 5) / 5.0
            layer = int(round(depth_val * 8.0))
            layer_counts[layer] = layer_counts.get(layer, 0) + 1

        plot_xs, plot_ys, plot_zs = [], [], []
        node_sizes, node_colors, hover_texts, node_urls = [], [], [], []

        for idx in range(num_nodes):
            nid = node_ids[idx]
            depth_norm = graph.x[idx, 33].item() if has_depth else (idx % 5) / 5.0
            z = 20.0 - (depth_norm * 40.0)

            layer = int(round(depth_norm * 8.0))
            layer_idx = layer_indices.get(layer, 0)
            total_in_layer = max(1, layer_counts.get(layer, 1))

            if idx in keep_indices:
                layer_indices[layer] = layer_idx + 1

            angle = (2.0 * math.pi * layer_idx) / total_in_layer + (layer * 0.4)
            base_radius = 8.0 + (layer % 3) * 3.0 + min(total_in_layer * 0.3, 12.0)
            x = base_radius * math.cos(angle)
            y = base_radius * math.sin(angle)

            all_xs[idx] = x
            all_ys[idx] = y
            all_zs[idx] = z

            if idx not in keep_indices: continue

            plot_xs.append(x)
            plot_ys.append(y)
            plot_zs.append(z)

            ntype = self._infer_node_type(graph, idx, nid)
            # Force explicit tags for the Evidence Path
            if nid in evidence_set:
                if nid.startswith("api_"):
                    ntype = NodeType.CRYPTO_API.value
                else:
                    ntype = NodeType.KEY.value

            if hasattr(graph, "line_numbers") and idx < len(graph.line_numbers) and graph.line_numbers[idx] > 0:
                line_no = graph.line_numbers[idx]
            elif has_line and graph.x[idx, 30].item() > 0:
                line_no = max(1, int(round(graph.x[idx, 30].item() * 1000)))
            else:
                line_no = "N/A"

            attn_val = attn_list[idx]
            size = 8.0 + 14.0 * max(0.0, min(1.0, attn_val))
            if nid in evidence_set:
                size = max(size, 16.0)
            node_sizes.append(size)

            color = NODE_TYPE_COLORS.get(ntype, "#94a3b8")
            node_colors.append(color)

            in_ev_str = "<b style='color:#f97316;'>YES (Vulnerable Flow)</b>" if nid in evidence_set else "No"
            
            n_file_path = ""
            if hasattr(graph, "file_paths") and idx < len(graph.file_paths):
                n_file_path = graph.file_paths[idx] or ""
            if not n_file_path and finding_details:
                n_file_path = finding_details.get("file") or finding_details.get("source_location", "").split(":")[0]

            if n_file_path and n_file_path != "N/A":
                abs_norm_path = os.path.abspath(n_file_path).replace("\\", "/")
                line_target = line_no if line_no != "N/A" else 1
                node_url = f"vscode://file/{abs_norm_path}:{line_target}"
                click_to_code = f" | <a href='{node_url}' target='_blank' style='color: #38bdf8; text-decoration: underline; font-weight: bold;'>Open in IDE</a>"
            else:
                node_url = ""
                click_to_code = ""

            tooltip = (
                f"<b>Role:</b> {ntype.upper()}<br>"
                f"<b>Node:</b> {nid}<br>"
                f"<b>Line:</b> {line_no}{click_to_code}<br>"
                f"<b>Hierarchy Depth:</b> {depth_norm:.2f}<br>"
                f"<b>In Evidence Path:</b> {in_ev_str}"
            )
            hover_texts.append(tooltip)
            node_urls.append(node_url)

        edge_groups: Dict[str, Tuple[List[float], List[float], List[float]]] = {}
        for et in EDGE_TYPE_LIST:
            edge_groups[et] = ([], [], [])

        ev_edge_x, ev_edge_y, ev_edge_z = [], [], []

        edge_index = graph.edge_index
        if edge_index is not None and edge_index.size(1) > 0:
            for e in range(edge_index.size(1)):
                src = edge_index[0, e].item()
                tgt = edge_index[1, e].item()
                if src < num_nodes and tgt < num_nodes and src in keep_indices and tgt in keep_indices:
                    src_id = node_ids[src]
                    tgt_id = node_ids[tgt]

                    is_ev = (src_id in evidence_set and tgt_id in evidence_set)
                    if is_ev:
                        ev_edge_x.extend([all_xs[src], all_xs[tgt], None])
                        ev_edge_y.extend([all_ys[src], all_ys[tgt], None])
                        ev_edge_z.extend([all_zs[src], all_zs[tgt], None])
                    else:
                        etype = self._infer_edge_type(graph, e)
                        gx, gy, gz = edge_groups[etype]
                        gx.extend([all_xs[src], all_xs[tgt], None])
                        gy.extend([all_ys[src], all_ys[tgt], None])
                        gz.extend([all_zs[src], all_zs[tgt], None])

        traces = []
        for etype, (ex, ey, ez) in edge_groups.items():
            if ex:
                color = EDGE_TYPE_COLORS.get(etype, "#475569")
                traces.append(
                    go.Scatter3d(
                        x=ex, y=ey, z=ez,
                        mode="lines",
                        line=dict(color=color, width=2),
                        hoverinfo="none",
                        name=f"Edge: {etype}",
                        legendgroup="edges",
                    )
                )

        if ev_edge_x:
            traces.append(
                go.Scatter3d(
                    x=ev_edge_x, y=ev_edge_y, z=ev_edge_z,
                    mode="lines",
                    line=dict(color="#f97316", width=7),
                    hoverinfo="none",
                    name="Evidence Path (Vulnerable Flow)",
                )
            )

        traces.append(
            go.Scatter3d(
                x=plot_xs, y=plot_ys, z=plot_zs,
                mode="markers",
                marker=dict(
                    size=node_sizes,
                    color=node_colors,
                    opacity=0.92,
                    line=dict(color="#1e293b", width=1),
                ),
                text=hover_texts,
                customdata=node_urls,
                hoverinfo="text",
                name="Graph Nodes",
            )
        )

        layout = go.Layout(
            title=dict(
                text=f"CryptoFlow 3D Interprocedural Graph — Finding {finding_id}",
                font=dict(color="#f8fafc", size=18),
                x=0.05,
                y=0.95,
            ),
            showlegend=True,
            paper_bgcolor="#0b0f19",
            plot_bgcolor="#0b0f19",
            font=dict(color="#94a3b8", family="Inter, system-ui, sans-serif"),
            scene=dict(
                xaxis=dict(showbackground=False, showgrid=False, zeroline=False, showticklabels=False, title=""),
                yaxis=dict(showbackground=False, showgrid=False, zeroline=False, showticklabels=False, title=""),
                zaxis=dict(showbackground=False, showgrid=False, zeroline=False, showticklabels=False, title="Hierarchy (Call Depth)"),
                camera=dict(eye=dict(x=1.6, y=1.6, z=1.2)),
            ),
            margin=dict(l=0, r=0, b=0, t=50),
            legend=dict(
                x=0.02,
                y=0.05,
                bgcolor="rgba(15, 23, 42, 0.75)",
                bordercolor="rgba(51, 65, 85, 0.5)",
                borderwidth=1,
                font=dict(size=10, color="#cbd5e1"),
            ),
        )

        fig = go.Figure(data=traces, layout=layout)
        plotly_html = fig.to_html(full_html=False, include_plotlyjs="cdn")
        dashboard_html = self._build_dashboard_html(finding_id, finding_details, plotly_html, len(keep_indices), len(evidence_set))

        output_file = os.path.join(self.output_dir, f"{finding_id}.html")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(dashboard_html)

        return os.path.abspath(output_file)

    def _build_dashboard_html(
        self,
        finding_id: str,
        finding_details: Optional[Dict[str, Any]],
        plotly_div: str,
        num_nodes: int,
        evidence_len: int,
    ) -> str:
        details = finding_details or {}
        cwe = details.get("cwe", "CWE-321: Hard-coded Cryptographic Key")
        risk = details.get("risk_level", "HIGH").upper()
        confidence = details.get("confidence", "98.4%")
        desc = details.get("description", "A sensitive cryptographic parameter (key/IV) is derived from a static constant across interprocedural wrapper calls.")
        fix = details.get("fix_suggestion", 'Replace static key literal with runtime secret from environment:\nconst char *key = getenv("CRYPTO_SECRET_KEY");')
        location = details.get("source_location", "Multiple source files across interprocedural boundary")

        risk_color = "#ef4444" if risk in {"CRITICAL", "HIGH"} else "#f59e0b"

        script_block = """
  <!-- Global click-to-code and Plotly interaction script -->
  <script>
    (function() {
      function openVscodeUri(url) {
        if (!url || typeof url !== 'string' || url.indexOf('vscode://') === -1) return;
        try {
          var iframe = document.createElement('iframe');
          iframe.style.display = 'none';
          iframe.src = url;
          document.body.appendChild(iframe);
          setTimeout(function() {
            try { document.body.removeChild(iframe); } catch(e) {}
          }, 2000);
        } catch(err) {
          window.location.href = url;
        }
      }

      document.addEventListener('click', function(e) {
        var anchor = e.target.closest('a');
        if (anchor && anchor.getAttribute('href') && anchor.getAttribute('href').startsWith('vscode://')) {
          e.preventDefault();
          openVscodeUri(anchor.getAttribute('href'));
        }
      });

      function setupPlotlyHooks() {
        var plotEl = document.querySelector('.plotly-graph-div');
        if (!plotEl || typeof plotEl.on !== 'function') {
          setTimeout(setupPlotlyHooks, 100);
          return;
        }

        var btn = document.getElementById('inspector-ide-btn');
        var titleEl = document.getElementById('inspector-node-title');
        var infoEl = document.getElementById('inspector-node-info');

        function updateInspector(pt) {
          if (!pt) return;
          var url = pt.customdata;
          var text = pt.text || "";
          var mNode = text.match(/Node:<\\/b>\\s*([^<]+)/i);
          var mType = text.match(/Role:<\\/b>\\s*([^<]+)/i);
          var mLine = text.match(/Line:<\\/b>\\s*([0-9]+)/i);

          var name = mNode ? mNode[1].trim() : "Node";
          var type = mType ? mType[1].trim() : "VARIABLE";
          var line = mLine ? mLine[1].trim() : "";

          if (titleEl) titleEl.innerText = type + ": " + name;
          if (infoEl) infoEl.innerText = line ? ("Line " + line + " | Click button or node to jump directly.") : "Select a node to inspect.";
          if (btn && url && typeof url === 'string' && url.indexOf('vscode://') !== -1) {
            btn.href = url;
            btn.style.display = 'inline-flex';
            btn.innerText = "⚡ Open in VS Code (Line " + (line || "1") + ")";
            btn.onclick = function(e) {
              e.preventDefault();
              openVscodeUri(url);
            };
          }
        }

        plotEl.on('plotly_click', function(data) {
          if (data && data.points && data.points.length > 0) {
            var pt = data.points[0];
            updateInspector(pt);
            if (pt.customdata && pt.customdata.indexOf('vscode://') !== -1) openVscodeUri(pt.customdata);
          }
        });

        plotEl.on('plotly_hover', function(data) {
          if (data && data.points && data.points.length > 0) {
            updateInspector(data.points[0]);
          }
        });
      }

      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupPlotlyHooks);
      } else {
        setupPlotlyHooks();
      }
    })();
  </script>
"""
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CryptoFlow 3D Security Graph — {finding_id}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: #0b0f19;
      color: #f8fafc;
      height: 100vh;
      overflow: hidden;
      display: flex;
    }}
    #sidebar {{
      width: 380px;
      height: 100vh;
      background: rgba(15, 23, 42, 0.95);
      border-right: 1px solid rgba(51, 65, 85, 0.6);
      backdrop-filter: blur(12px);
      display: flex;
      flex-direction: column;
      padding: 24px;
      overflow-y: auto;
      z-index: 10;
      box-shadow: 4px 0 24px rgba(0,0,0,0.5);
    }}
    #graph-container {{ flex: 1; height: 100vh; position: relative; }}
    .badge {{
      display: inline-block; padding: 4px 10px; border-radius: 6px;
      font-size: 11px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase;
    }}
    .badge-risk {{ background: rgba(239, 68, 68, 0.2); color: {risk_color}; border: 1px solid {risk_color}; }}
    .badge-cwe {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid #3b82f6; }}
    .badge-hgnn {{ background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid #a855f7; }}
    h1 {{ font-size: 20px; font-weight: 700; margin: 12px 0 6px 0; color: #f8fafc; }}
    .meta-row {{ font-size: 12px; color: #94a3b8; margin-bottom: 16px; }}
    .card {{ background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(51, 65, 85, 0.5); border-radius: 8px; padding: 14px; margin-bottom: 14px; }}
    .card-title {{ font-size: 12px; font-weight: 600; text-transform: uppercase; color: #94a3b8; margin-bottom: 6px; }}
    .card-body {{ font-size: 13px; line-height: 1.5; color: #e2e8f0; }}
    pre {{ background: #090d16; border: 1px solid #1e293b; padding: 10px; border-radius: 6px; font-family: ui-monospace, monospace; font-size: 12px; color: #38bdf8; overflow-x: auto; margin-top: 6px; }}
    .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 14px; }}
    .stat-box {{ background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(51, 65, 85, 0.4); padding: 10px; border-radius: 6px; text-align: center; }}
    .stat-val {{ font-size: 18px; font-weight: 700; color: #f8fafc; }}
    .stat-lbl {{ font-size: 10px; color: #94a3b8; text-transform: uppercase; }}
    .legend-item {{ display: flex; align-items: center; font-size: 12px; margin-bottom: 6px; }}
    .dot {{ width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; flex-shrink: 0; }}
    .hoverlayer {{ pointer-events: auto !important; }}
    .hoverlayer text, .hoverlayer a, .hoverlayer path {{ pointer-events: auto !important; cursor: pointer !important; }}
    .ide-btn {{ display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 10px 14px; background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); color: #ffffff !important; border: 1px solid #38bdf8; border-radius: 6px; font-size: 12px; font-weight: 700; text-decoration: none !important; cursor: pointer; box-shadow: 0 2px 8px rgba(2, 132, 199, 0.4); transition: all 0.15s ease; width: 100%; margin-top: 6px; }}
    .ide-btn:hover {{ background: linear-gradient(135deg, #0369a1 0%, #075985 100%); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(2, 132, 199, 0.6); }}
  </style>
</head>
<body>
  <div id="sidebar">
    <div style="display: flex; gap: 8px; align-items: center;">
      <span class="badge badge-risk">{risk} RISK</span>
      <span class="badge badge-hgnn">HGNN {confidence}</span>
    </div>
    <h1>CryptoFlow 3D Security</h1>
    <div class="meta-row">Finding: <b>{finding_id}</b> | {location}</div>

    <div class="stat-grid">
      <div class="stat-box">
        <div class="stat-val">{num_nodes}</div>
        <div class="stat-lbl">Graph Nodes (Rendered)</div>
      </div>
      <div class="stat-box">
        <div class="stat-val" style="color: #f97316;">{evidence_len}</div>
        <div class="stat-lbl">Evidence Nodes</div>
      </div>
    </div>

    <!-- Live IDE Code Navigator Card -->
    <div class="card" style="border-left: 3px solid #38bdf8; background: rgba(14, 116, 144, 0.15);">
      <div class="card-title" style="color: #38bdf8; display: flex; align-items: center; justify-content: space-between;">
        <span>IDE Code Navigator</span>
        <span style="font-size: 9px; background: rgba(56, 189, 248, 0.2); padding: 2px 6px; border-radius: 4px; color: #38bdf8;">CLICK TO OPEN</span>
      </div>
      <div class="card-body">
        <div id="inspector-node-title" style="font-weight: 700; color: #f8fafc; font-size: 13px; margin-bottom: 2px;">Click any node to jump to code</div>
        <div id="inspector-node-info" style="font-size: 11px; color: #94a3b8; margin-bottom: 6px;">Click or hover over any node in the 3D graph to view file location.</div>
        <a id="inspector-ide-btn" href="#" class="ide-btn" style="display: none;">
          ⚡ Open in VS Code
        </a>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Vulnerability Finding</div>
      <div class="card-body">
        <div style="margin-bottom: 6px;"><span class="badge badge-cwe">{cwe}</span></div>
        {desc}
      </div>
    </div>

    <div class="card">
      <div class="card-title">Recommended Remediation</div>
      <div class="card-body">
        <pre><code>{fix}</code></pre>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Node Hierarchy (Call Depth)</div>
      <div class="card-body" style="font-size: 11px;">
        <div class="legend-item"><span class="dot" style="background:#ffffff;"></span>FILE (Z=+20 Root)</div>
        <div class="legend-item"><span class="dot" style="background:#06b6d4;"></span>FUNCTION (Depth 1)</div>
        <div class="legend-item"><span class="dot" style="background:#00ffff;"></span>WRAPPER (Depth 2)</div>
        <div class="legend-item"><span class="dot" style="background:#ff00ff;"></span>KEY / SECRET (Target)</div>
        <div class="legend-item"><span class="dot" style="background:#f97316;"></span>LITERAL (Z=-20 Leaf)</div>
        <div class="legend-item"><span class="dot" style="background:#ffff00;"></span>CRYPTO_API (Sink)</div>
      </div>
    </div>
  </div>

  <div id="graph-container">
    {plotly_div}
  </div>

  {script_block}
</body>
</html>"""
        return html