"""
baselines package: Competitor reference implementations.

  - FusionHGNN  : Fusion-HGNN (IEEE TSE 2024/2026) — unpruned dense graph,
                  hyperbolic GCN with curvature c=3.5, no crypto-role gating.
  - Coca        : Coca (ICSE 2024) — Euclidean GAT + post-hoc gradient-based
                  subgraph extractor.
  - EuclideanGNN: Standard GCN/GAT Euclidean baseline.
"""

from src.models.baselines.fusion_hgnn import FusionHGNN      # noqa: F401
from src.models.baselines.coca import Coca                    # noqa: F401
from src.models.baselines.euclidean_gnn import EuclideanGNN  # noqa: F401

__all__ = ["FusionHGNN", "Coca", "EuclideanGNN"]
