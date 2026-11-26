"""
hyperbolic_ops.py: Poincaré ball model operations, exp/log maps, and HyperbolicLinear layer.
Based on base paper Section III.B with curvature c = 3.5.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F


def exp_map_zero(v: torch.Tensor, c: float = 3.5, eps: float = 1e-6) -> torch.Tensor:
    """
    Poincaré ball exponential map from tangent space at origin T_0 D_c^n to D_c^n.
    exp_0^c(v) = tanh(sqrt(c) * ||v||) * (v / (sqrt(c) * ||v||))
    """
    sqrt_c = math.sqrt(c)
    norm = torch.norm(v, p=2, dim=-1, keepdim=True).clamp_min(eps)
    max_norm = (1.0 - eps) / sqrt_c
    res = (torch.tanh(sqrt_c * norm) / (sqrt_c * norm)) * v
    # Project within Poincaré ball radius
    res_norm = torch.norm(res, p=2, dim=-1, keepdim=True)
    mask = res_norm > max_norm
    res = torch.where(mask, res * (max_norm / res_norm), res)
    return res


def log_map_zero(y: torch.Tensor, c: float = 3.5, eps: float = 1e-6) -> torch.Tensor:
    """
    Poincaré ball logarithmic map from D_c^n to tangent space at origin T_0 D_c^n.
    log_0^c(y) = arctanh(sqrt(c) * ||y||) * (y / (sqrt(c) * ||y||))
    """
    sqrt_c = math.sqrt(c)
    norm = torch.norm(y, p=2, dim=-1, keepdim=True).clamp_min(eps)
    # Clamp norm strictly inside ball
    safe_norm = (sqrt_c * norm).clamp(max=1.0 - eps)
    res = (torch.atanh(safe_norm) / (sqrt_c * norm)) * y
    return res


def project_to_ball(x: torch.Tensor, c: float = 3.5, frac: float = 0.8, eps: float = 1e-8) -> torch.Tensor:
    """
    Project each row of a tensor into (the interior of) the Poincaré ball of
    curvature c. Vectors already inside the ball keep their magnitude; only
    oversized vectors are scaled down. Preserving relative magnitudes is
    essential so class-discriminative signal survives mean pooling downstream
    (normalizing every row to a fixed radius destroyed the signal entirely).
    """
    radius = (1.0 / (c ** 0.5)) * frac
    norm = torch.norm(x, p=2, dim=-1, keepdim=True).clamp_min(eps)
    scale = (radius / norm).clamp_max(1.0)
    return x * scale


class HyperbolicLinear(nn.Module):
    """
    Hyperbolic linear layer performing Möbius matrix-vector operations
    via tangent space projection at origin.
    """

    def __init__(self, in_features: int, out_features: int, curvature: float = 3.5):
        super().__init__()
        self.c = curvature
        self.linear = nn.Linear(in_features, out_features)

    def log_map(self, x: torch.Tensor) -> torch.Tensor:
        return log_map_zero(x, self.c)

    def exp_map(self, x: torch.Tensor) -> torch.Tensor:
        return exp_map_zero(x, self.c)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x_tangent = self.log_map(x)
        x_tangent = self.linear(x_tangent)
        # Keep the finite-dimensional output inside the ball so the exp-map
        # below does not saturate tanh (which stalled HGNN training).
        x_tangent = project_to_ball(x_tangent, self.c)
        x_hyperbolic = self.exp_map(x_tangent)
        return x_hyperbolic


class HyperbolicGraphConv(nn.Module):
    """
    Hyperbolic Graph Convolution Layer.
    Aggregates neighbor features in tangent space at origin, applies linear mapping,
    and returns Poincaré embeddings.
    """

    def __init__(self, in_features: int, out_features: int, curvature: float = 3.5, dropout: float = 0.3):
        super().__init__()
        self.c = curvature
        self.hyp_linear = HyperbolicLinear(in_features, out_features, curvature=curvature)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        # Linear transformation in hyperbolic space
        h = self.hyp_linear(x)

        # Map to tangent space for message aggregation
        tan_h = log_map_zero(h, self.c)
        tan_h = self.dropout(tan_h)

        # Graph aggregation (renormalized GCN-style with self-loops).
        # Mean aggregation over compressed edge norms collapses node
        # representations toward the origin across layers; symmetric
        # (D^-1/2 A D^-1/2) normalization with self-loops keeps norms stable.
        num_nodes = x.size(0)
        row, col = edge_index
        self_loops = torch.arange(num_nodes, device=edge_index.device)
        row = torch.cat([row, self_loops])
        col = torch.cat([col, self_loops])

        deg = torch.bincount(col, minlength=num_nodes).clamp_min(1).float()
        weight_t = deg[col].pow(-0.5)
        weight_s = deg[row].pow(-0.5)
        msg = tan_h[row] * (weight_t * weight_s).unsqueeze(-1)

        agg = torch.zeros_like(tan_h)
        if row.numel() > 0:
            agg.index_add_(0, col, msg)
        else:
            agg = tan_h

        # Hyperbolic activation / mapping back
        h_out = exp_map_zero(F.relu(agg), self.c)
        return h_out
