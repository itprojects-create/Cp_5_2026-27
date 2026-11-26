"""
euclidean_gnn.py  –  src/models/baselines/euclidean_gnn.py
Standard Euclidean GCN/GAT Baseline.

Re-exports GenericGNN and CryptoGNN from the legacy models package
under the canonical baselines namespace, and provides a unified
EuclideanGNN factory class for configuration-driven instantiation.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import torch.nn as nn
from torch_geometric.data import Data

from models.gnns.generic_gnn import GenericGNN   # noqa: F401
from models.gnns.crypto_gnn import CryptoGNN     # noqa: F401
from External_scanner.graph_schema import NODE_FEATURE_DIM


class EuclideanGNN(nn.Module):
    """
    Unified Euclidean GNN baseline factory.

    Wraps either the generic (no crypto features) or crypto-aware GCN
    depending on the ``variant`` argument, providing a single entry point
    for the evaluation harness.

    Parameters
    ----------
    variant : 'generic' | 'crypto'
        'generic' → GenericGNN (crypto features zeroed out).
        'crypto'  → CryptoGNN (full crypto-semantic features).
    in_channels     : Input node feature dim (default: 34).
    hidden_channels : Hidden / embedding dimensionality (default: 256).
    num_layers      : GCN depth (default: 3).
    dropout         : Dropout probability (default: 0.3).
    num_classes     : Output classes (default: 5 CWEs).
    """

    def __init__(
        self,
        variant: Literal["generic", "crypto"] = "crypto",
        in_channels: int = NODE_FEATURE_DIM,
        hidden_channels: int = 256,
        num_layers: int = 3,
        dropout: float = 0.3,
        num_classes: int = 5,
    ) -> None:
        super().__init__()
        self.variant = variant

        if variant == "generic":
            self._model = GenericGNN(
                in_channels=in_channels,
                hidden_channels=hidden_channels,
                num_layers=num_layers,
                dropout=dropout,
                num_classes=num_classes,
            )
        else:
            self._model = CryptoGNN(
                in_channels=in_channels,
                hidden_channels=hidden_channels,
                num_layers=num_layers,
                dropout=dropout,
                num_classes=num_classes,
            )

    def forward(self, data: Data, **kwargs):
        return self._model(data, **kwargs)
