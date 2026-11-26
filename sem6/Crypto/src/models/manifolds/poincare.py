"""
poincare.py  –  src/models/manifolds/poincare.py
Poincaré ball model: exp/log maps, Möbius operations, and hyperbolic layers.

All operations are parameterised by curvature c (default c=1.0 for CryptoHGNN,
c=3.5 for Fusion-HGNN baseline).

References
----------
* Chami et al., "Hyperbolic Graph Convolutional Neural Networks", NeurIPS 2019.
* Nickel & Kiela, "Poincaré Embeddings for Learning Hierarchical Representations",
  NeurIPS 2017.
* Ganea et al., "Hyperbolic Neural Networks", NeurIPS 2018.
"""

from __future__ import annotations

import math
import torch
import torch.nn as nn
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# Core Poincaré ball primitives
# ---------------------------------------------------------------------------

def exp_map_zero(
    v: torch.Tensor,
    c: float = 1.0,
    eps: float = 1e-6,
) -> torch.Tensor:
    """
    Exponential map from tangent space at the origin T_0 D_c^n → D_c^n.

    exp_0^c(v) = tanh(√c · ‖v‖) / (√c · ‖v‖) · v

    Parameters
    ----------
    v   : Tangent vector(s).  Shape: (*batch, d)
    c   : Poincaré ball curvature (positive scalar).
    eps : Numerical stability clamp.

    Returns
    -------
    Tensor on the Poincaré ball, same shape as v.
    """
    sqrt_c = math.sqrt(c)
    norm = torch.norm(v, p=2, dim=-1, keepdim=True).clamp_min(eps)
    max_norm = (1.0 - eps) / sqrt_c
    res = (torch.tanh(sqrt_c * norm) / (sqrt_c * norm)) * v
    res_norm = torch.norm(res, p=2, dim=-1, keepdim=True)
    mask = res_norm > max_norm
    res = torch.where(mask, res * (max_norm / res_norm), res)
    return res


def log_map_zero(
    y: torch.Tensor,
    c: float = 1.0,
    eps: float = 1e-6,
) -> torch.Tensor:
    """
    Logarithmic map from D_c^n → tangent space at origin T_0 D_c^n.

    log_0^c(y) = atanh(√c · ‖y‖) / (√c · ‖y‖) · y
    """
    sqrt_c = math.sqrt(c)
    norm = torch.norm(y, p=2, dim=-1, keepdim=True).clamp_min(eps)
    safe_norm = (sqrt_c * norm).clamp(max=1.0 - eps)
    res = (torch.atanh(safe_norm) / (sqrt_c * norm)) * y
    return res


def project_to_ball(
    x: torch.Tensor,
    c: float = 1.0,
    frac: float = 0.8,
    eps: float = 1e-8,
) -> torch.Tensor:
    """
    Project rows of x into the open Poincaré ball of curvature c.

    Only oversized vectors are rescaled; vectors already inside the ball
    keep their relative magnitudes (preserving class-discriminative signal).

    Parameters
    ----------
    x    : Input tensor.  Shape: (*batch, d)
    c    : Ball curvature.
    frac : Safety fraction of the theoretical radius 1/√c.
    eps  : Zero-norm guard.
    """
    radius = (1.0 / (c ** 0.5)) * frac
    norm = torch.norm(x, p=2, dim=-1, keepdim=True).clamp_min(eps)
    scale = (radius / norm).clamp_max(1.0)
    return x * scale


def mobius_add(
    x: torch.Tensor,
    y: torch.Tensor,
    c: float = 1.0,
    eps: float = 1e-6,
) -> torch.Tensor:
    """
    Möbius addition: x ⊕_c y on the Poincaré ball.

    (1 + 2c⟨x,y⟩ + c‖y‖²)x + (1 - c‖x‖²)y
    ─────────────────────────────────────────────
       1 + 2c⟨x,y⟩ + c²‖x‖²‖y‖²
    """
    x2 = torch.sum(x * x, dim=-1, keepdim=True)
    y2 = torch.sum(y * y, dim=-1, keepdim=True)
    xy = torch.sum(x * y, dim=-1, keepdim=True)

    num = (1 + 2 * c * xy + c * y2) * x + (1 - c * x2) * y
    denom = (1 + 2 * c * xy + c ** 2 * x2 * y2).clamp_min(eps)
    return num / denom


def poincare_distance(
    x: torch.Tensor,
    y: torch.Tensor,
    c: float = 1.0,
    eps: float = 1e-6,
) -> torch.Tensor:
    """
    Poincaré ball geodesic distance: d_c(x, y) = (2/√c) · atanh(√c · ‖-x ⊕_c y‖).
    """
    sqrt_c = math.sqrt(c)
    neg_x = -x
    add = mobius_add(neg_x, y, c=c, eps=eps)
    add_norm = torch.norm(add, p=2, dim=-1).clamp(max=1.0 - eps)
    dist = (2.0 / sqrt_c) * torch.atanh(sqrt_c * add_norm)
    return dist


# ---------------------------------------------------------------------------
# Hyperbolic Neural Network layers
# ---------------------------------------------------------------------------

class HyperbolicLinear(nn.Module):
    """
    Hyperbolic linear layer: Möbius matrix-vector product via tangent-space
    projection at the origin.

    Parameters
    ----------
    in_features  : Input feature dimensionality.
    out_features : Output feature dimensionality.
    curvature    : Poincaré ball curvature c.
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        curvature: float = 1.0,
    ) -> None:
        super().__init__()
        self.c = curvature
        self.linear = nn.Linear(in_features, out_features, bias=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x_tan = log_map_zero(x, self.c)          # → tangent space
        x_tan = self.linear(x_tan)               # Euclidean linear transform
        x_tan = project_to_ball(x_tan, self.c)   # stabilise before exp-map
        return exp_map_zero(x_tan, self.c)        # → Poincaré ball


class HyperbolicGraphConv(nn.Module):
    """
    Hyperbolic Graph Convolution layer.

    Aggregates neighbour features in the tangent space at the origin using
    symmetric GCN-style (D^{-1/2} A D^{-1/2}) normalisation with self-loops,
    applies a HyperbolicLinear transform, and returns Poincaré embeddings.

    Parameters
    ----------
    in_features  : Input node feature dimensionality.
    out_features : Output node feature dimensionality.
    curvature    : Poincaré ball curvature c.
    dropout      : Dropout probability applied in tangent space.
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        curvature: float = 1.0,
        dropout: float = 0.3,
    ) -> None:
        super().__init__()
        self.c = curvature
        self.hyp_linear = HyperbolicLinear(in_features, out_features, curvature)
        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
    ) -> torch.Tensor:
        """
        Parameters
        ----------
        x          : Node embeddings on the Poincaré ball.  Shape: [N, d]
        edge_index : COO edge tensor.  Shape: [2, E]

        Returns
        -------
        Node embeddings on the Poincaré ball.  Shape: [N, out_features]
        """
        # Hyperbolic linear transform
        h = self.hyp_linear(x)

        # Map to tangent space for aggregation
        tan_h = log_map_zero(h, self.c)
        tan_h = self.dropout(tan_h)

        # Symmetric GCN normalisation with added self-loops
        num_nodes = x.size(0)
        row, col = edge_index
        self_loops = torch.arange(num_nodes, device=edge_index.device)
        row = torch.cat([row, self_loops])
        col = torch.cat([col, self_loops])

        deg = torch.bincount(col, minlength=num_nodes).clamp_min(1).float()
        w = (deg[col].pow(-0.5) * deg[row].pow(-0.5)).unsqueeze(-1)
        msg = tan_h[row] * w

        agg = torch.zeros_like(tan_h)
        agg.index_add_(0, col, msg)

        # Non-linearity and map back to Poincaré ball
        return exp_map_zero(F.relu(agg), self.c)
