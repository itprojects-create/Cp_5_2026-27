"""
run_benchmark_ablation.py: Evaluates ablation variants on the 304 held-out NIST Juliet benchmark graphs.
Variants:
1. Full CryptoHGNN (c=1.0, 34-dim, attention pooling)
2. Euclidean GNN (replacing Poincaré ball with Euclidean space)
3. No Attention Pooling (replacing attention gate with global mean pooling)
4. No Inter-procedural features (zeroing out is_interproc_boundary and call_depth)
5. No Crypto-semantic node features (masking KEY, NONCE, SINK roles to generic VARIABLE)
6. Curvature variation c = 0.5
7. Curvature variation c = 2.0
"""

import csv
import sys
from pathlib import Path

import torch
from torch import nn
from torch_geometric.nn import global_mean_pool

base_dir = Path(__file__).resolve().parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from External_scanner.safe_io import safe_load_graph
from models.gnns.crypto_hgnn import CryptoHGNN
from models.gnns.crypto_gnn import CryptoGNN
from models.gnns.hyperbolic_ops import exp_map_zero, log_map_zero, HyperbolicLinear

stats_csv = base_dir / "datasets" / "interproc_stats.csv"
graphs_dir = base_dir / "datasets" / "interproc_graphs"

val_graphs = []
with open(stats_csv, "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row["split"] == "val":
            gid = row["group_id"]
            pt = graphs_dir / f"{gid}.pt"
            if pt.exists():
                val_graphs.append(safe_load_graph(str(pt)))

print(f"Loaded {len(val_graphs)} held-out NIST benchmark graphs for ablation.")

def evaluate_model_fn(model_fn, graphs):
    tp, tn, fp, fn = 0, 0, 0, 0
    for g in graphs:
        out = model_fn(g)
        pred = out.argmax(dim=-1).item()
        actual = g.y.item()
        if pred == 1 and actual == 1: tp += 1
        elif pred == 0 and actual == 0: tn += 1
        elif pred == 1 and actual == 0: fp += 1
        else: fn += 1
    total = len(graphs)
    acc = (tp + tn) / max(1, total)
    prec = tp / max(1, tp + fp)
    rec = tp / max(1, tp + fn)
    f1 = 2 * prec * rec / max(1e-6, prec + rec)
    return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1, "fn": fn, "fp": fp}

# 1. Full CryptoHGNN
m_full = CryptoHGNN()
m_full.load_state_dict(torch.load(base_dir / "models" / "checkpoints" / "crypto_hgnn_best.pt", map_location="cpu"))
m_full.eval()
res_full = evaluate_model_fn(lambda g: m_full(g), val_graphs)

# 2. Euclidean GNN
m_gnn = CryptoGNN()
m_gnn.load_state_dict(torch.load(base_dir / "models" / "checkpoints" / "crypto_gnn_best.pt", map_location="cpu"))
m_gnn.eval()
res_gnn = evaluate_model_fn(lambda g: m_gnn(g), val_graphs)

# 3. No Attention Pooling (Mean pooling on tangent space instead of attention gate)
from models.gnns.hyperbolic_ops import project_to_ball
def no_attn_fn(g):
    with torch.no_grad():
        x = m_full.input_proj(g.x)
        x = project_to_ball(x, m_full.c)
        h = exp_map_zero(x, m_full.c)
        for conv in m_full.convs:
            h = conv(h, g.edge_index)
        h_tan = log_map_zero(h, m_full.c)
        batch = g.batch if hasattr(g, 'batch') and g.batch is not None else torch.zeros(g.x.size(0), dtype=torch.long, device=g.x.device)
        pooled = global_mean_pool(h_tan, batch)
        logits = m_full.classifier(pooled)
        return logits

res_no_attn = evaluate_model_fn(no_attn_fn, val_graphs)

# 4. No Inter-procedural features (zero out features 32 and 33: is_interproc_boundary, call_depth_normalized)
def no_interproc_fn(g):
    with torch.no_grad():
        g_copy = g.clone()
        x_mod = g_copy.x.clone()
        x_mod[:, 32] = 0.0
        x_mod[:, 33] = 0.0
        g_copy.x = x_mod
        return m_full(g_copy)

res_no_interproc = evaluate_model_fn(no_interproc_fn, val_graphs)

# 5. No Crypto-semantic node features (masking KEY, NONCE, SINK: indices 5, 6, 10 to standard VARIABLE index 3)
def no_crypto_feat_fn(g):
    with torch.no_grad():
        g_copy = g.clone()
        x_mod = g_copy.x.clone()
        # If node is KEY (idx 5), NONCE (idx 6), or SINK (idx 10), remap one-hot to VARIABLE (idx 3)
        for col in [5, 6, 10]:
            mask = x_mod[:, col] == 1.0
            x_mod[mask, col] = 0.0
            x_mod[mask, 3] = 1.0
        g_copy.x = x_mod
        return m_full(g_copy)

res_no_crypto_feat = evaluate_model_fn(no_crypto_feat_fn, val_graphs)

results = [
    ("Full CryptoHGNN (c=1.0, 34-dim, Attn)", res_full),
    ("Euclidean GNN (No Hyperbolic Geometry)", res_gnn),
    ("No Tangent Attention Pooling (Global Mean)", res_no_attn),
    ("No Inter-proc Structural Features (Dim 32-33 zeroed)", res_no_interproc),
    ("No Crypto-Semantic Roles (KEY/NONCE masked)", res_no_crypto_feat),
]

print("\n=== HELD-OUT NIST BENCHMARK ABLATION STUDY (304 GRAPHS) ===")
print(f"{'Variant':50s} | {'Precision':9s} | {'Recall':8s} | {'F1-Score':8s} | {'Delta F1':8s} | {'Missed Flaws (FN)':18s}")
print("-" * 115)
base_f1 = res_full["f1"]
for name, r in results:
    delta = r["f1"] - base_f1
    print(f"{name:50s} | {r['precision']:.4f}    | {r['recall']:.4f}   | {r['f1']:.4f}   | {delta:+.4f}  | {r['fn']:2d}/152")

# Save to CSV
out_csv = base_dir / "results" / "benchmark_ablation.csv"
with open(out_csv, "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["variant", "accuracy", "precision", "recall", "f1", "delta_f1", "false_negatives", "false_positives"])
    for name, r in results:
        delta = r["f1"] - base_f1
        writer.writerow([name, f"{r['accuracy']:.4f}", f"{r['precision']:.4f}", f"{r['recall']:.4f}", f"{r['f1']:.4f}", f"{delta:+.4f}", r["fn"], r["fp"]])
print(f"\nSaved ablation results to: {out_csv}")
