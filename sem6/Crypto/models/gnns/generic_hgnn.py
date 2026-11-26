"""
GenericHGNN: 3-layer Hyperbolic Graph Neural Network with curvature c=1.0 on generic graphs.
"""

from typing import Tuple, Union
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import global_add_pool
from torch_geometric.data import Data

from External_scanner.graph_schema import NODE_FEATURE_DIM
from models.gnns.hyperbolic_ops import HyperbolicGraphConv, exp_map_zero, log_map_zero, project_to_ball


class GenericHGNN(nn.Module):
    """
    3-layer Hyperbolic GNN operating on the Poincaré ball model with curvature c = 1.0.
    Evaluated on generic code graph features with attention-gated pooling.
    """

    def __init__(
        self,
        in_channels: int = NODE_FEATURE_DIM,
        hidden_channels: int = 256,
        num_layers: int = 3,
        curvature: float = 1.0,
        dropout: float = 0.3,
        num_classes: int = 5,
    ):
        super().__init__()
        self.c = curvature
        self.convs = nn.ModuleList()
        for _ in range(num_layers):
            self.convs.append(
                HyperbolicGraphConv(hidden_channels, hidden_channels, curvature=curvature, dropout=dropout)
            )

        self.input_proj = nn.Linear(in_channels, hidden_channels)
        self._dropout = nn.Dropout(dropout)

        # Attention-gated pooling in tangent space
        self.attn_gate = nn.Linear(hidden_channels, 1)

        self.classifier = nn.Sequential(
            nn.Linear(hidden_channels, hidden_channels // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_channels // 2, num_classes),
        )

    def forward(self, data: Data, return_attention: bool = False) -> Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        x, edge_index = data.x, data.edge_index
        batch = getattr(data, "batch", None)
        if batch is None:
            batch = torch.zeros(x.size(0), dtype=torch.long, device=x.device)

        # Zero out crypto domain features for generic baseline
        x_generic = x.clone()
        if x_generic.size(1) >= 30:
            x_generic[:, 11:30] = 0.0

        # Euclidean projection of generic features into target space
        x_proj = self._dropout(self.input_proj(x_generic))
        x_proj = project_to_ball(x_proj, self.c)
        h = exp_map_zero(x_proj, self.c)

        for conv in self.convs:
            h = conv(h, edge_index)

        # Tangent space attention pooling and prediction
        h_tan = log_map_zero(h, self.c)
        attn = torch.sigmoid(self.attn_gate(h_tan))  # [N, 1]
        pooled = global_add_pool(h_tan * attn, batch)
        logits = self.classifier(pooled)

        if return_attention:
            return logits, attn.squeeze(-1)
        return logits
