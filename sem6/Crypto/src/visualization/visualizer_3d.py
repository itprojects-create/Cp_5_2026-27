"""
visualizer_3d.py  –  src/visualization/visualizer_3d.py
3D Plotly WebGL hierarchical lattice visualizer.
Re-exports the existing Visualizer from agents.visualizer under the canonical
src namespace, and adds a thin Visualizer3D facade.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import torch

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agents.visualizer import Visualizer as _LegacyVisualizer  # noqa: F401
from torch_geometric.data import Data


class Visualizer3D(_LegacyVisualizer):
    """
    3D Plotly WebGL hierarchical lattice visualizer.

    Extends the legacy Visualizer with a standardised output path
    consistent with the new project layout (results/figures/).

    Parameters
    ----------
    output_dir : Directory for HTML outputs.
                 Defaults to ``results/figures``.
    """

    def __init__(self, output_dir: str = "results/figures") -> None:
        super().__init__(output_dir=output_dir)

    def render_graph(
        self,
        graph: Data,
        finding_id: str = "graph_3d",
        title: str = "CryptoFlow Graph",
        attention_weights: Optional[torch.Tensor] = None,
        evidence_path: Optional[list] = None,
    ) -> str:
        """
        Render a PyG graph as an interactive 3D Plotly HTML file.

        Parameters
        ----------
        graph            : PyG Data object to visualise.
        finding_id       : Output filename stem (used as HTML filename).
        title            : Figure title (passed in finding_details).
        attention_weights: Optional per-node attention tensor.
        evidence_path    : Optional list of node-id strings to highlight.

        Returns
        -------
        Absolute path to the generated HTML file.
        """
        # Delegate to the legacy visualizer's .generate() method
        return self.generate(
            graph=graph,
            evidence_path=evidence_path or [],
            finding_id=finding_id,
            attention_weights=attention_weights,
            finding_details={"title": title},
        )
