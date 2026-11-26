"""
src.models package: Neural network architectures for CryptoFlow.

Sub-packages:
  - manifolds  : Poincaré ball math & Möbius operations
  - layers     : Hyperbolic Linear & Aggregation layers
  - baselines  : Competitor reference implementations (Fusion-HGNN, Coca)

Top-level modules:
  - cryptohgnn : CryptoHGNN – proposed model (c=1.0, tangent attention)
"""

# Lazy imports — torch is only pulled in when the submodule is explicitly
# accessed, preventing ImportError at package-scan time if torch is absent.
__all__ = ["CryptoHGNN", "FusionHGNN", "Coca", "EuclideanGNN"]


def __getattr__(name: str):
    if name == "CryptoHGNN":
        from src.models.cryptohgnn import CryptoHGNN
        return CryptoHGNN
    if name == "FusionHGNN":
        from src.models.baselines.fusion_hgnn import FusionHGNN
        return FusionHGNN
    if name == "Coca":
        from src.models.baselines.coca import Coca
        return Coca
    if name == "EuclideanGNN":
        from src.models.baselines.euclidean_gnn import EuclideanGNN
        return EuclideanGNN
    raise AttributeError(f"module 'src.models' has no attribute {name!r}")
