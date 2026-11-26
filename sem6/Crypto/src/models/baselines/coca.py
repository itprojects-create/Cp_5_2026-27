"""
coca.py  –  src/models/baselines/coca.py
Coca Baseline (ICSE 2024) — Euclidean GAT + Post-hoc Gradient Subgraph Extractor

Faithful reimplementation of the paper's architecture (mirroring the
ICSE 2024 paper):
  - Standard 3-layer Graph Attention Network (GAT) in Euclidean space.
  - After the forward pass, applies a *post-hoc* crucial-subgraph extractor
    using gradient-based edge saliency (GradCAM-style masking on edge
    features), as described in the paper.
  - The post-hoc explanation step is decoupled from training by
    construction in the paper's method (it is computed after the model is
    frozen), which is a structural property of the design, not a
    performance claim. Actual detection performance is measured
    empirically in results/tables/comparison.csv.

Architecture
------------
  1. 3-layer GATConv (8 heads → linear projection)
  2. Attention-gated global pooling
  3. 2-layer MLP classifier

  Post-hoc subgraph extractor
  ---------------------------
  • Compute d(loss)/d(A_ij) via torch.autograd.grad
  • Threshold saliency scores → binary edge mask
  • Return subgraph as a new PyG Data object for visualisation / explanation
"""

from __future__ import annotations

import copy
from typing import Optional, Tuple, Union, List

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv, global_add_pool
from torch_geometric.data import Data
from torch_geometric.utils import subgraph

from External_scanner.graph_schema import NODE_FEATURE_DIM


class Coca(nn.Module):
    """
    Coca: Euclidean Graph Attention Network with post-hoc gradient-based
    subgraph extractor (ICSE 2024 competitor baseline).

    As in the paper, the post-hoc explanation is derived *after* message
    passing, from a frozen trained model, rather than being integrated
    into training the way CryptoHGNN's attention-gated pooling is.

    Parameters
    ----------
    in_channels     : Input node feature dim (default: 34).
    hidden_channels : Hidden dimensionality (default: 128).
    num_layers      : GAT conv layers (default: 3).
    heads           : Attention heads per GAT layer (default: 8).
    dropout         : Dropout probability (default: 0.3).
    num_classes     : Output classes (default: 5 CWEs).
    edge_saliency_threshold : Percentile threshold for subgraph masking (default: 0.75).
    """

    def __init__(
        self,
        in_channels: int = NODE_FEATURE_DIM,
        hidden_channels: int = 128,
        num_layers: int = 3,
        heads: int = 8,
        dropout: float = 0.3,
        num_classes: int = 2,
        edge_saliency_threshold: float = 0.75,
    ) -> None:
        super().__init__()
        self.threshold = edge_saliency_threshold

        # --- GAT stack ---
        self.convs = nn.ModuleList()
        # Layer 0: in_channels → hidden (multi-head)
        self.convs.append(
            GATConv(in_channels, hidden_channels, heads=heads,
                    dropout=dropout, concat=True)
        )
        # Layers 1 … n-2: hidden*heads → hidden (multi-head)
        for _ in range(num_layers - 2):
            self.convs.append(
                GATConv(hidden_channels * heads, hidden_channels,
                        heads=heads, dropout=dropout, concat=True)
            )
        # Final layer: hidden*heads → hidden (single head, no concat)
        self.convs.append(
            GATConv(hidden_channels * heads, hidden_channels,
                    heads=1, dropout=dropout, concat=False)
        )

        self.dropout = nn.Dropout(dropout)

        # Attention-gated global pooling
        self.attn_gate = nn.Linear(hidden_channels, 1)

        self.classifier = nn.Sequential(
            nn.Linear(hidden_channels, hidden_channels // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_channels // 2, num_classes),
        )

        # Edge embedding for saliency attribution
        self._edge_embed: Optional[torch.Tensor] = None
        self._edge_index_cache: Optional[torch.Tensor] = None

    # ------------------------------------------------------------------
    # Forward pass
    # ------------------------------------------------------------------

    def forward(
        self,
        data: Data,
        return_attention: bool = False,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Standard Euclidean GAT forward pass.

        Parameters
        ----------
        data             : PyG Data object.
        return_attention : If True, return per-node attention weights from
                           the last GAT layer.

        Returns
        -------
        logits [B, num_classes]  or  (logits, attn [N])
        """
        x, edge_index = data.x, data.edge_index
        batch = getattr(data, "batch", None)
        if batch is None:
            batch = torch.zeros(x.size(0), dtype=torch.long, device=x.device)

        self._edge_index_cache = edge_index  # cache for post-hoc extractor

        for i, conv in enumerate(self.convs):
            x = conv(x, edge_index)
            x = F.elu(x)
            x = self.dropout(x)

        # Attention-gated pooling
        attn = torch.sigmoid(self.attn_gate(x))  # [N, 1]
        pooled = global_add_pool(x * attn, batch)
        logits = self.classifier(pooled)

        if return_attention:
            return logits, attn.squeeze(-1)
        return logits

    # ------------------------------------------------------------------
    # Post-hoc subgraph extractor
    # ------------------------------------------------------------------

    def extract_subgraph(
        self,
        data: Data,
        target_class: Optional[int] = None,
    ) -> Tuple[Data, torch.Tensor]:
        """
        Gradient-based post-hoc crucial-subgraph extraction (Coca-style).

        Method
        ------
        1. Forward pass with gradient tracking on a learnable edge weight
           tensor initialised to ones.
        2. Compute gradient of the target-class logit w.r.t. edge weights.
        3. Threshold by the configured percentile → binary mask.
        4. Return the induced subgraph as a new PyG Data object.

        Parameters
        ----------
        data         : Original graph.
        target_class : Class index to explain.  Defaults to predicted class.

        Returns
        -------
        (subgraph_data, edge_saliency)  where edge_saliency ∈ [0, 1]^E

        Limitations
        -----------
        * Saliency is computed *after* message passing has collapsed
          multi-hop alias information.  Alias chains that were never
          propagated during the forward pass will have near-zero gradient
          and will be excluded from the explanation even if they are
          causally responsible for the vulnerability.
        * This structural blind spot is precisely what CryptoFlow's
          semantic engine corrects by resolving aliases *before* the GNN.
        """
        self.eval()
        data_copy = copy.copy(data)
        x, edge_index = data_copy.x, data_copy.edge_index
        n_edges = edge_index.size(1)
        batch = getattr(data_copy, "batch", None)
        if batch is None:
            batch = torch.zeros(x.size(0), dtype=torch.long, device=x.device)

        # Learnable edge importance weights (initialised to 1)
        edge_weight = torch.ones(n_edges, requires_grad=True, device=x.device)

        # Forward with manual weighted aggregation approximation
        # We apply edge_weight as a scalar multiplier on the adjacency
        # by injecting it into the GCN-style message (approximation for GAT)
        x_proc = x.clone()
        for i, conv in enumerate(self.convs):
            # Weighted adjacency approximation: scale each source embedding
            # by the corresponding edge weight before aggregation
            weighted_x = x_proc.clone()
            if n_edges > 0:
                src, dst = edge_index
                weight_per_node = torch.zeros(x_proc.size(0), device=x.device)
                weight_per_node.index_add_(0, dst, edge_weight)
                weight_per_node = weight_per_node.clamp_min(1.0)
                weighted_x = x_proc * weight_per_node.unsqueeze(-1)

            x_proc = conv(weighted_x, edge_index)
            x_proc = F.elu(x_proc)

        attn = torch.sigmoid(self.attn_gate(x_proc))
        pooled = global_add_pool(x_proc * attn, batch)
        logits = self.classifier(pooled)

        if target_class is None:
            target_class = int(logits.argmax(dim=-1).item())

        # Backpropagate to get edge saliency scores
        score = logits[0, target_class]
        grads = torch.autograd.grad(score, edge_weight, create_graph=False)[0]

        # Normalise saliency to [0, 1]
        saliency = grads.abs()
        if saliency.max() > 1e-8:
            saliency = (saliency - saliency.min()) / (saliency.max() - saliency.min() + 1e-8)

        # Threshold: keep top (1 - threshold) fraction of edges
        cutoff = torch.quantile(saliency, self.threshold)
        mask = saliency >= cutoff  # [E], bool

        # Induced subgraph
        kept_edges = edge_index[:, mask]
        nodes_in_subgraph = kept_edges.flatten().unique()

        sub_ei, _ = subgraph(
            nodes_in_subgraph, edge_index, relabel_nodes=True,
            num_nodes=x.size(0),
        )

        sub_x = x[nodes_in_subgraph]
        sub_y = getattr(data_copy, "y", None)

        sub_data = Data(x=sub_x, edge_index=sub_ei, y=sub_y)
        sub_data.node_ids = nodes_in_subgraph  # original node indices

        return sub_data, saliency

    # ------------------------------------------------------------------
    # Convenience: batch-mode extraction
    # ------------------------------------------------------------------

    def explain_batch(
        self,
        graphs: List[Data],
        target_class: Optional[int] = None,
    ) -> List[Tuple[Data, torch.Tensor]]:
        """
        Extract post-hoc explanations for a list of graphs.

        Returns
        -------
        List of (subgraph_data, saliency) tuples.
        """
        return [self.extract_subgraph(g, target_class) for g in graphs]
