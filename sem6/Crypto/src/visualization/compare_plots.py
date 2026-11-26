"""
compare_plots.py  –  src/visualization/compare_plots.py
Publication-grade 3-panel comparative architecture trace figure.

Generates a side-by-side comparison of how each model processes a sample
NIST Juliet CWE-321/CWE-256 file with a 3-hop wrapper cascade:

  Panel A — Fusion-HGNN : Dense, unpruned graph; diffused uniform attention
             across all boilerplate AST / CFG nodes.
  Panel B — Coca        : Post-hoc explanation subgraph; disconnected because
             alias edges crossing wrapper boundaries have zero gradient.
  Panel C — CryptoFlow  : Clean pruned semantic path terminating at the
             USES_AS_KEY cryptographic API sink; focused tangent attention.

Output
------
  results/figures/comparative_architecture_trace.png   (300 DPI)
  results/figures/comparative_architecture_trace.pdf

Usage
-----
  python src/visualization/compare_plots.py

  or from Python:

    from src.visualization.compare_plots import ComparePlots
    cp = ComparePlots()
    cp.generate(output_dir="results/figures")
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Removed PyTorch / PyG dependencies to allow pure-static plotting
# on hosts with restricted DLL loading (Application Control).
import numpy as np
import matplotlib
matplotlib.use("Agg")          # non-interactive backend for headless / CI
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch

from External_scanner.graph_schema import NodeType, EdgeType


# ---------------------------------------------------------------------------
# Color palette (matches the 3D visualizer palette for consistency)
# ---------------------------------------------------------------------------

NODE_COLORS: Dict[str, str] = {
    NodeType.FILE.value:          "#FFFFFF",
    NodeType.FUNCTION.value:      "#06B6D4",
    NodeType.PARAMETER.value:     "#14B8A6",
    NodeType.VARIABLE.value:      "#94A3B8",
    NodeType.LITERAL.value:       "#F97316",
    NodeType.KEY.value:           "#FF00FF",
    NodeType.NONCE.value:         "#EC4899",
    NodeType.CRYPTO_API.value:    "#FACC15",
    NodeType.RANDOM_SOURCE.value: "#84CC16",
    NodeType.WRAPPER.value:       "#00FFFF",
    NodeType.SINK.value:          "#F43F5E",
}

EDGE_COLORS: Dict[str, str] = {
    EdgeType.CONTAINS.value:              "#A855F7",
    EdgeType.CALLS.value:                 "#3B82F6",
    EdgeType.ARGUMENT_TO_PARAMETER.value: "#06B6D4",
    EdgeType.RETURNS_TO.value:            "#10B981",
    EdgeType.ASSIGNED_FROM.value:         "#F59E0B",
    EdgeType.FLOWS_TO.value:              "#F97316",
    EdgeType.ALIASES.value:               "#EC4899",
    EdgeType.USES_AS_KEY.value:           "#EF4444",
    EdgeType.USES_AS_NONCE.value:         "#D946EF",
    EdgeType.EXPOSES_TO.value:            "#E11D48",
}

BG_DARK = "#0F1117"
PANEL_BG = "#1A1D27"
TEXT_COLOR = "#E2E8F0"
GRID_COLOR = "#2D3148"
ACCENT_CYAN = "#06B6D4"
ACCENT_MAGENTA = "#FF00FF"
ACCENT_RED = "#EF4444"

# ---------------------------------------------------------------------------
# Synthetic graph generators (CWE-321 / CWE-256, 3-hop wrapper cascade)
# ---------------------------------------------------------------------------

def _make_cryptoflow_graph() -> Tuple[List[Tuple[int, int]], List[str], List[str], List[float], List[str]]:
    """
    Panel C: CryptoFlow pruned semantic path.
    """
    node_types = [
        NodeType.FILE.value,
        NodeType.FUNCTION.value,   # main
        NodeType.WRAPPER.value,    # wrapperL1
        NodeType.WRAPPER.value,    # wrapperL2
        NodeType.WRAPPER.value,    # wrapperL3
        NodeType.KEY.value,        # hard-coded key var
        NodeType.CRYPTO_API.value, # AES_encrypt (sink)
        NodeType.SINK.value,       # downstream exposure
    ]
    labels = [
        "file.c", "main()", "wrapL1()", "wrapL2()", "wrapL3()",
        "key = \"ABC123\"", "AES_encrypt()", "network_send()",
    ]
    edge_tuples = [
        (0, 1, EdgeType.CONTAINS.value),
        (1, 2, EdgeType.CALLS.value),
        (2, 3, EdgeType.CALLS.value),
        (3, 4, EdgeType.CALLS.value),
        (4, 5, EdgeType.ALIASES.value),
        (5, 6, EdgeType.USES_AS_KEY.value),
        (6, 7, EdgeType.EXPOSES_TO.value),
    ]
    attn = [0.05, 0.10, 0.20, 0.30, 0.55, 0.95, 1.00, 0.80]
    edge_types = [e[2] for e in edge_tuples]
    edge_index = [(e[0], e[1]) for e in edge_tuples]
    return edge_index, node_types, labels, attn, edge_types


def _make_fusion_hgnn_graph() -> Tuple[List[Tuple[int, int]], List[str], List[str], List[float], List[str]]:
    """
    Panel A: Fusion-HGNN dense unpruned graph.
    """
    node_types = [
        NodeType.FILE.value,
        NodeType.FUNCTION.value,   # main
        NodeType.VARIABLE.value,   # loop var i
        NodeType.VARIABLE.value,   # buf[64]
        NodeType.LITERAL.value,    # "Hello"
        NodeType.FUNCTION.value,   # printf
        NodeType.WRAPPER.value,    # wrapL1
        NodeType.WRAPPER.value,    # wrapL2
        NodeType.WRAPPER.value,    # wrapL3
        NodeType.KEY.value,        # key (buried)
        NodeType.VARIABLE.value,   # ret_val
        NodeType.CRYPTO_API.value, # AES_encrypt
        NodeType.VARIABLE.value,   # cipher_out
        NodeType.SINK.value,       # network_send
        NodeType.VARIABLE.value,   # errno_check
        NodeType.FUNCTION.value,   # cleanup()
    ]
    labels = [
        "file.c", "main()", "i=0", "buf[64]", '"Hello"', "printf()",
        "wrapL1()", "wrapL2()", "wrapL3()", 'key="ABC123"',
        "ret", "AES_encrypt()", "cipher", "send()", "errno", "cleanup()",
    ]
    edge_tuples = [
        (0, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6),
        (6, 7), (7, 8), (8, 9), (9, 11), (11, 12), (12, 13),
        (1, 10), (10, 11), (13, 14), (14, 15), (3, 12), (5, 15),
        (2, 6), (4, 10),
    ]
    attn = [0.06, 0.07, 0.05, 0.05, 0.04, 0.06,
            0.12, 0.14, 0.18, 0.35, 0.08, 0.40,
            0.09, 0.11, 0.04, 0.06]
    max_a = max(attn)
    attn = [a / max_a for a in attn]
    edge_index = edge_tuples
    edge_types = [EdgeType.FLOWS_TO.value] * len(edge_tuples)
    return edge_index, node_types, labels, attn, edge_types


def _make_coca_graph() -> Tuple[List[Tuple[int, int]], List[str], List[str], List[float], List[str]]:
    """
    Panel B: Coca post-hoc subgraph (disconnected).
    """
    node_types = [
        NodeType.FILE.value,
        NodeType.FUNCTION.value,   # main
        NodeType.WRAPPER.value,    # wrapL1
        NodeType.WRAPPER.value,    # wrapL2
        NodeType.KEY.value,        # isolated key node
        NodeType.CRYPTO_API.value, # AES_encrypt
        NodeType.SINK.value,       # network_send
    ]
    labels = [
        "file.c", "main()", "wrapL1()", "wrapL2()",
        "key=? ✗", "AES_encrypt()", "send()",
    ]
    edge_tuples = [
        (0, 1, EdgeType.CONTAINS.value),
        (1, 2, EdgeType.CALLS.value),
        (2, 3, EdgeType.CALLS.value),
        (5, 6, EdgeType.EXPOSES_TO.value),
    ]
    attn = [0.08, 0.12, 0.22, 0.30, 0.02, 0.15, 0.18]
    max_a = max(attn)
    attn = [a / max_a for a in attn]
    edge_index = [(e[0], e[1]) for e in edge_tuples]
    edge_types = [e[2] for e in edge_tuples]
    return edge_index, node_types, labels, attn, edge_types


# ---------------------------------------------------------------------------
# Layout utilities
# ---------------------------------------------------------------------------

def _hierarchical_layout(
    n_nodes: int,
    edge_index: List[Tuple[int, int]],
) -> np.ndarray:
    """
    Simple BFS hierarchical layout returning (x, y) coordinates in [0, 1].
    """
    from collections import deque
    adj: Dict[int, List[int]] = {i: [] for i in range(n_nodes)}
    for s, d in edge_index:
        adj[s].append(d)

    visited = [False] * n_nodes
    level: Dict[int, int] = {}
    queue = deque([0])
    visited[0] = True
    level[0] = 0

    while queue:
        node = queue.popleft()
        for nb in adj[node]:
            if not visited[nb]:
                visited[nb] = True
                level[nb] = level[node] + 1
                queue.append(nb)

    max_level = max(level.values()) if level else 0
    for i in range(n_nodes):
        if i not in level:
            level[i] = max_level + 1

    level_groups: Dict[int, List[int]] = {}
    for node, lv in level.items():
        level_groups.setdefault(lv, []).append(node)

    pos = np.zeros((n_nodes, 2))
    n_levels = max(level_groups.keys()) + 1
    for lv, nodes in level_groups.items():
        y = 1.0 - lv / max(1, n_levels - 1)
        for k, node in enumerate(sorted(nodes)):
            x = (k + 1) / (len(nodes) + 1)
            pos[node] = [x, y]

    return pos


# ---------------------------------------------------------------------------
# Core drawing routine
# ---------------------------------------------------------------------------

def _draw_panel(
    ax: plt.Axes,
    node_types: List[str],
    labels: List[str],
    edge_tuples_src_dst_type: List[Tuple[int, int, str]],
    attn: List[float],
    edge_index: List[Tuple[int, int]],
    title: str,
    subtitle: str,
    highlight_edges: Optional[List[int]] = None,
    missing_nodes: Optional[List[int]] = None,
) -> None:
    n = len(node_types)
    pos = _hierarchical_layout(n, edge_index)

    ax.set_facecolor(PANEL_BG)
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.12, 1.12)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_COLOR)
        spine.set_linewidth(1.5)

    for idx, (s, d, et) in enumerate(edge_tuples_src_dst_type):
        x1, y1 = pos[s]
        x2, y2 = pos[d]
        color = EDGE_COLORS.get(et, "#6B7280")
        lw = 2.5 if (highlight_edges and idx in highlight_edges) else 1.2
        alpha = 0.9 if (highlight_edges and idx in highlight_edges) else 0.45
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(
                arrowstyle="-|>", color=color, lw=lw, alpha=alpha,
                mutation_scale=14, linestyle="-",
            ),
        )

    for i, (nt, lbl) in enumerate(zip(node_types, labels)):
        x, y = pos[i]
        color = NODE_COLORS.get(nt, "#6B7280")
        size = 600 + 1400 * attn[i]
        is_missing = missing_nodes and i in missing_nodes
        ec = "#FF4444" if is_missing else "#FFFFFF"
        ew = 2.0 if is_missing else 0.8
        ax.scatter(x, y, s=size, c=color, edgecolors=ec, linewidths=ew,
                   zorder=5, alpha=0.95 if not is_missing else 0.4)

        attn_pct = int(attn[i] * 100)
        ax.text(x, y + 0.005, f"{attn_pct}%",
                ha="center", va="center", fontsize=5.5,
                color="#0F1117", fontweight="bold", zorder=6)

        lbl_color = "#FF4444" if is_missing else TEXT_COLOR
        ax.text(x, y - 0.085, lbl,
                ha="center", va="top", fontsize=6.0,
                color=lbl_color, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc=PANEL_BG,
                          ec=GRID_COLOR, lw=0.5, alpha=0.8),
                zorder=7)

    ax.set_title(title, color=TEXT_COLOR, fontsize=11, fontweight="bold", pad=8, loc="center")
    ax.text(0.5, -0.09, subtitle, transform=ax.transAxes,
            ha="center", va="top", fontsize=7.5, color="#94A3B8", style="italic")


# ---------------------------------------------------------------------------
# ComparePlots class
# ---------------------------------------------------------------------------

class ComparePlots:
    def __init__(self, dpi: int = 300, figsize: Tuple[int, int] = (18, 7)) -> None:
        self.dpi = dpi
        self.figsize = figsize

    def generate(
        self,
        output_dir: str = "results/figures",
        prefix: str = "comparative_architecture_trace",
        save_pdf: bool = True,
        save_png: bool = True,
    ) -> List[str]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        (ei_cf, nt_cf, lbl_cf, attn_cf, et_cf) = _make_cryptoflow_graph()
        (ei_fh, nt_fh, lbl_fh, attn_fh, et_fh) = _make_fusion_hgnn_graph()
        (ei_co, nt_co, lbl_co, attn_co, et_co) = _make_coca_graph()

        tup_cf = [(s, d, et) for (s, d), et in zip(ei_cf, et_cf)]
        tup_fh = [(s, d, et) for (s, d), et in zip(ei_fh, et_fh)]
        tup_co = [(s, d, et) for (s, d), et in zip(ei_co, et_co)]

        fig = plt.figure(figsize=self.figsize, facecolor=BG_DARK)
        fig.patch.set_facecolor(BG_DARK)

        gs = fig.add_gridspec(1, 3, wspace=0.06, left=0.03, right=0.97, top=0.88, bottom=0.12)
        axes = [fig.add_subplot(gs[0, i]) for i in range(3)]

        _draw_panel(
            ax=axes[0], node_types=nt_fh, labels=lbl_fh,
            edge_tuples_src_dst_type=tup_fh, attn=attn_fh, edge_index=ei_fh,
            title="(A)  Fusion-HGNN  [IEEE TSE 2026]",
            subtitle=(
                "Dense unpruned AST+CFG+DDG fusion  ·  c = 3.5  ·  "
                "Uniform mean-pool\n"
                "Attention diffused across boilerplate  →  "
                "FPR ↑  |  alias chain lost"
            ),
        )

        _draw_panel(
            ax=axes[1], node_types=nt_co, labels=lbl_co,
            edge_tuples_src_dst_type=tup_co, attn=attn_co, edge_index=ei_co,
            title="(B)  Coca  [ICSE 2024]",
            subtitle=(
                "Euclidean GAT  ·  post-hoc gradient subgraph extractor\n"
                "Alias chain (wrapL3→key) pruned by zero grad  →  "
                "✗ disconnected explanation"
            ),
            missing_nodes=[4, 5],
        )

        _draw_panel(
            ax=axes[2], node_types=nt_cf, labels=lbl_cf,
            edge_tuples_src_dst_type=tup_cf, attn=attn_cf, edge_index=ei_cf,
            title="(C)  CryptoFlow  [Proposed]",
            subtitle=(
                "Pruned semantic path  ·  c = 1.0  ·  "
                "Tangent-space attention readout\n"
                "USES_AS_KEY sink resolved  →  FPR ↓  |  "
                "precision-recall balanced"
            ),
            highlight_edges=[4, 5],
        )

        fig.suptitle(
            "CryptoFlow vs. Competitor Baselines — "
            "CWE-321 / CWE-256 with 3-Hop Wrapper Cascade\n"
            "NIST SAMATE Juliet Test Suite v1.3",
            color=TEXT_COLOR, fontsize=13, fontweight="bold", y=0.97,
        )
        fig.text(
            0.5, 0.935,
            "Illustrative diagram — node/edge/attention values are hand-authored "
            "to demonstrate the architectural difference, not measured from a live model run.",
            color=TEXT_COLOR, fontsize=7, style="italic", ha="center", alpha=0.75,
        )

        legend_handles = [
            mpatches.Patch(color=NODE_COLORS[nt], label=nt)
            for nt in [NodeType.FUNCTION.value, NodeType.WRAPPER.value,
                       NodeType.KEY.value, NodeType.CRYPTO_API.value,
                       NodeType.SINK.value, NodeType.VARIABLE.value,
                       NodeType.LITERAL.value]
        ]
        legend_handles += [
            Line2D([0], [0], color=EDGE_COLORS[EdgeType.ALIASES.value], lw=2, label="ALIASES"),
            Line2D([0], [0], color=EDGE_COLORS[EdgeType.USES_AS_KEY.value], lw=2, label="USES_AS_KEY"),
            Line2D([0], [0], color=EDGE_COLORS[EdgeType.CALLS.value], lw=2, label="CALLS"),
            mpatches.Patch(color="#FF444466", label="✗ Missing / isolated node"),
        ]
        fig.legend(
            handles=legend_handles, loc="lower center", ncol=6, framealpha=0.15,
            facecolor=PANEL_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR,
            fontsize=7, bbox_to_anchor=(0.5, 0.01),
        )

        saved: List[str] = []
        if save_png:
            png_path = out_dir / f"{prefix}.png"
            fig.savefig(png_path, dpi=self.dpi, bbox_inches="tight", facecolor=BG_DARK)
            saved.append(str(png_path.resolve()))
            print(f"[ComparePlots] Saved PNG -> {png_path}")

        if save_pdf:
            pdf_path = out_dir / f"{prefix}.pdf"
            fig.savefig(pdf_path, bbox_inches="tight", facecolor=BG_DARK)
            saved.append(str(pdf_path.resolve()))
            print(f"[ComparePlots] Saved PDF -> {pdf_path}")

        plt.close(fig)
        return saved


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate 3-panel comparative architecture trace figure."
    )
    parser.add_argument("--output-dir", default="results/figures", help="Output directory for PNG/PDF files.")
    parser.add_argument("--dpi", type=int, default=300, help="Output image DPI (default: 300).")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF output.")
    args = parser.parse_args()

    cp = ComparePlots(dpi=args.dpi)
    paths = cp.generate(output_dir=args.output_dir, save_pdf=not args.no_pdf)
    print("\nGenerated files:")
    for p in paths:
        print(f"  {p}")
