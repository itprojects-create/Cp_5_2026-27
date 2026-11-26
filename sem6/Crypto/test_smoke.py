"""
test_smoke.py  –  Quick smoke-test for the full CryptoFlow src/ package.
Run from repo root:
    .venv\\Scripts\\python.exe test_smoke.py
"""

import sys
import traceback

sys.path.insert(0, ".")

PASS = []
FAIL = []


def check(label, fn):
    try:
        result = fn()
        PASS.append(label)
        print(f"  [OK]  {label}" + (f" → {result}" if result else ""))
    except Exception as exc:
        FAIL.append(label)
        print(f"  [FAIL] {label}: {exc}")
        traceback.print_exc()


# ── 1. Basic imports ──────────────────────────────────────────────────────
check("import torch", lambda: __import__("torch").__version__)
check("import torch_geometric", lambda: __import__("torch_geometric").__version__)
check("import matplotlib", lambda: __import__("matplotlib").__version__)
check("import sklearn", lambda: __import__("sklearn").__version__)
check(
    "import External_scanner.graph_schema",
    lambda: (
        __import__(
            "External_scanner.graph_schema", fromlist=["NODE_FEATURE_DIM"]
        ).NODE_FEATURE_DIM
    ),
)


# ── 2. Poincaré math ─────────────────────────────────────────────────────
def test_poincare():
    import torch

    from src.models.manifolds.poincare import (
        HyperbolicGraphConv,
        HyperbolicLinear,
        exp_map_zero,
        log_map_zero,
        project_to_ball,
    )

    v = torch.randn(8, 32)
    ball_c1 = exp_map_zero(v, c=1.0)
    ball_c35 = exp_map_zero(v, c=3.5)
    assert ball_c1.norm(dim=-1).max() < 1.0 + 1e-4, "c=1 ball overflow"
    assert ball_c35.norm(dim=-1).max() < 1.0 / (3.5**0.5) + 1e-4, "c=3.5 ball overflow"
    back = log_map_zero(ball_c1, c=1.0)
    err = (back - v).abs().max().item()
    return f"round-trip err={err:.5f}"


check("Poincaré exp/log round-trip", test_poincare)


# ── 3. CryptoHGNN forward ─────────────────────────────────────────────────
def test_cryptohgnn():
    import torch
    from torch_geometric.data import Data

    from src.models.cryptohgnn import CryptoHGNN

    n, e = 12, 20
    x = torch.randn(n, 34)
    ei = torch.randint(0, n, (2, e))
    g = Data(x=x, edge_index=ei, y=torch.tensor([1]))
    m = CryptoHGNN()
    logits, attn = m(g, return_attention=True)
    assert logits.shape == (1, 5)
    assert attn.shape == (n,)
    assert 0 <= attn.min().item() <= attn.max().item() <= 1
    return f"logits={list(logits.shape)}, attn_max={attn.max().item():.3f}"


check("CryptoHGNN forward + attention", test_cryptohgnn)


# ── 4. FusionHGNN forward ─────────────────────────────────────────────────
def test_fusionhgnn():
    import torch
    from torch_geometric.data import Data

    from src.models.baselines.fusion_hgnn import FusionHGNN

    n, e = 16, 30
    x = torch.randn(n, 34)
    ei = torch.randint(0, n, (2, e))
    g = Data(x=x, edge_index=ei, y=torch.tensor([2]))
    m = FusionHGNN(num_classes=2)
    assert m.c == 3.5, f"Expected c=3.5, got {m.c}"
    logits, attn = m(g, return_attention=True)
    assert logits.shape == (1, 2)
    # Uniform pseudo-attn: all equal, sum to 1
    assert abs(attn.sum().item() - 1.0) < 1e-5
    return (
        f"c={m.c}, logits={list(logits.shape)}, pseudo_attn_sum={attn.sum().item():.4f}"
    )


check("FusionHGNN forward (c=3.5, uniform attn)", test_fusionhgnn)


# ── 5. Coca forward + subgraph extraction ─────────────────────────────────
def test_coca():
    import torch
    from torch_geometric.data import Data

    from src.models.baselines.coca import Coca

    n, e = 10, 18
    x = torch.randn(n, 34)
    ei = torch.randint(0, n, (2, e))
    g = Data(x=x, edge_index=ei, y=torch.tensor([0]))
    m = Coca(num_classes=2)
    logits, _attn = m(g, return_attention=True)
    assert logits.shape == (1, 2)
    sub, sal = m.extract_subgraph(g, target_class=0)
    assert sub.x is not None
    assert sub.x.shape[1] == 34
    assert sal.shape[0] == e
    assert 0 <= sal.min().item() <= sal.max().item() <= 1
    assert sub.x is not None
    return (
        f"logits={list(logits.shape)}, "
        f"sub_nodes={sub.x.shape[0]}/{n}, sal_max={sal.max().item():.3f}"
    )


check("Coca forward + post-hoc subgraph extractor", test_coca)


# ── 6. compare_plots dry run ──────────────────────────────────────────────
def test_compare_plots():
    from src.visualization.compare_plots import ComparePlots

    cp = ComparePlots(dpi=72)  # low dpi for speed in smoke test
    paths = cp.generate(
        output_dir="results/figures",
        save_pdf=False,
        save_png=True,
    )
    assert len(paths) >= 1
    import os

    assert os.path.exists(paths[0]), f"PNG not found: {paths[0]}"
    return f"saved to {paths[0]}"


check("compare_plots 3-panel figure generation", test_compare_plots)

# ── 7. evaluate_all import ────────────────────────────────────────────────
check(
    "evaluation.evaluate_all import",
    lambda: (
        __import__(
            "evaluation.evaluate_all", fromlist=["run_full_evaluation"]
        ).run_full_evaluation.__name__
    ),
)

# ── Summary ───────────────────────────────────────────────────────────────
print()
print("=" * 60)
print(f"  PASSED: {len(PASS)}/{len(PASS) + len(FAIL)}")
if FAIL:
    print(f"  FAILED: {', '.join(FAIL)}")
print("=" * 60)
sys.exit(0 if not FAIL else 1) 
