"""
CryptoGNN: 3-layer Graph Convolutional Network utilizing full crypto-semantic graph features
and attention-gated graph pooling.
"""

from typing import Tuple, Union
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, global_add_pool
from torch_geometric.data import Data

from External_scanner.graph_schema import NODE_FEATURE_DIM


class CryptoGNN(nn.Module):
    """
    3-layer GCN model trained on crypto-semantic graph features
    with attention-gated graph pooling.
    """

    def __init__(
        self,
        in_channels: int = NODE_FEATURE_DIM,
        hidden_channels: int = 256,
        num_layers: int = 3,
        dropout: float = 0.3,
        num_classes: int = 5,
    ):
        super().__init__()
        self.convs = nn.ModuleList()
        self.convs.append(GCNConv(in_channels, hidden_channels))
        for _ in range(num_layers - 1):
            self.convs.append(GCNConv(hidden_channels, hidden_channels))

        self.dropout = nn.Dropout(dropout)
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

        for conv in self.convs:
            x = conv(x, edge_index)
            x = F.relu(x)
            x = self.dropout(x)

        attn = torch.sigmoid(self.attn_gate(x))
        pooled = global_add_pool(x * attn, batch)
        logits = self.classifier(pooled)

        if return_attention:
            return logits, attn.squeeze(-1)
        return logits
