"""
cryptohgnn.py  –  src/models/cryptohgnn.py
CryptoHGNN: Proposed model (c=1.0) with tangent-space attention readout.

Architecture
------------
* Input projection: Euclidean linear → Poincaré ball (c=1.0)
* 3 × HyperbolicGraphConv layers with GCN-style normalised aggregation
* Tangent-space attention-gated global pooling
* 2-layer Euclidean MLP classifier
"""

from __future__ import annotations

from typing import Tuple, Union

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import torch
import torch.nn as nn
from torch_geometric.nn import global_add_pool
from torch_geometric.data import Data

from External_scanner.graph_schema import NODE_FEATURE_DIM
from src.models.manifolds.poincare import (
    HyperbolicGraphConv,
    exp_map_zero,
    log_map_zero,
    project_to_ball,
)


class CryptoHGNN(nn.Module):
    """
    Crypto-HGNN: Core proposed model combining hyperbolic geometry on the
    Poincaré ball (c=1.0) with typed crypto-semantic graph representations
    and attention-gated graph pooling in the tangent space.

    Parameters
    ----------
    in_channels     : Dimensionality of input node features (default: 34).
    hidden_channels : Hidden / embedding dimensionality (default: 256).
    num_layers      : Number of HyperbolicGraphConv layers (default: 3).
    curvature       : Poincaré ball curvature c (default: 1.0).
    dropout         : Dropout probability (default: 0.3).
    num_classes     : Number of output classes / CWEs (default: 5).
    """

    def __init__(
        self,
        in_channels: int = NODE_FEATURE_DIM,
        hidden_channels: int = 256,
        num_layers: int = 3,
        curvature: float = 1.0,
        dropout: float = 0.3,
        num_classes: int = 5,
    ) -> None:
        super().__init__()
        self.c = curvature

        self.input_proj = nn.Linear(in_channels, hidden_channels)
        self._dropout = nn.Dropout(dropout)

        self.convs = nn.ModuleList(
            [
                HyperbolicGraphConv(
                    hidden_channels, hidden_channels,
                    curvature=curvature, dropout=dropout,
                )
                for _ in range(num_layers)
            ]
        )

        # Attention-gated pooling in tangent space
        self.attn_gate = nn.Linear(hidden_channels, 1)

        self.classifier = nn.Sequential(
            nn.Linear(hidden_channels, hidden_channels // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_channels // 2, num_classes),
        )

    def forward(
        self,
        data: Data,
        return_attention: bool = False,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Parameters
        ----------
        data             : PyG Data object with .x and .edge_index.
        return_attention : If True, also return per-node attention weights.

        Returns
        -------
        logits [B, num_classes]  or  (logits, attn [N])
        """
        x, edge_index = data.x, data.edge_index
        batch = getattr(data, "batch", None)
        if batch is None:
            batch = torch.zeros(x.size(0), dtype=torch.long, device=x.device)

        # --- Euclidean → Poincaré ball ---
        x = self._dropout(self.input_proj(x))
        x = project_to_ball(x, self.c)
        h = exp_map_zero(x, self.c)

        # --- Hyperbolic message passing ---
        for conv in self.convs:
            h = conv(h, edge_index)

        # --- Tangent-space attention pooling ---
        h_tan = log_map_zero(h, self.c)
        attn = torch.sigmoid(self.attn_gate(h_tan))   # [N, 1]
        pooled = global_add_pool(h_tan * attn, batch)  # [B, hidden]
        logits = self.classifier(pooled)

        if return_attention:
            return logits, attn.squeeze(-1)
        return logits
