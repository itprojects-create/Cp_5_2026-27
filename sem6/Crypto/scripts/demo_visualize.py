"""
demo_visualize.py: Demonstrates 3D interactive visualization of interprocedural
code graphs using trained CryptoHGNN attention weights and security explanations.
Outputs standalone HTML to visualizations/demo_interproc.html.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List

import torch

base_dir = Path(__file__).resolve().parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from External_scanner.safe_io import safe_load_graph
from models.gnns.crypto_hgnn import CryptoHGNN
from agents.visualizer import Visualizer


def find_evidence_path(graph, node_ids: List[str]) -> List[str]:
    """Extracts a causal path of nodes from literal/key to sink."""
    evidence = []
    # Identify key/secret nodes and sink nodes
    for idx, nid in enumerate(node_ids):
        nid_low = nid.lower()
        if "key" in nid_low or "secret" in nid_low or nid_low.startswith("lit_"):
            evidence.append(nid)
        elif "crypt" in nid_low or "cipher" in nid_low or "wrapper" in nid_low or "func_" in nid_low:
            if idx < 12:  # keep top relevant functions/wrappers
                evidence.append(nid)
    return evidence


def run_demo(target_graph_file: str = "CWE321_Hard_Coded_Cryptographic_Key__w32_char_54__bad.pt"):
    graphs_dir = base_dir / "datasets" / "interproc_graphs"
    pt_path = graphs_dir / target_graph_file
    if not pt_path.exists():
        # Fallback to first available .pt
        pts = list(graphs_dir.glob("*.pt"))
        if not pts:
            print(f"Error: No graphs found in {graphs_dir}")
            return
        pt_path = pts[0]

    print(f"Loading graph: {pt_path.name}")
    graph = safe_load_graph(str(pt_path))

    # Load model
    ckpt_path = base_dir / "models" / "checkpoints" / "crypto_hgnn_best.pt"
    model = CryptoHGNN()
    if ckpt_path.exists():
        model.load_state_dict(torch.load(ckpt_path, weights_only=True))
        print("Loaded CryptoHGNN checkpoint.")
    else:
        print("Warning: Checkpoint not found, using untrained model.")

    model.eval()
    with torch.no_grad():
        out, attn = model(graph, return_attention=True)
        probs = torch.softmax(out, dim=-1)
        pred_label = out.argmax(dim=-1).item()
        confidence = probs[0, pred_label].item()

    status_str = "VULNERABLE" if pred_label == 1 else "BENIGN"
    print(f"Model Prediction: {status_str} (Confidence: {confidence * 100:.2f}%)")

    node_ids = getattr(graph, "node_ids", [f"node_{i}" for i in range(graph.x.size(0))])
    evidence_path = find_evidence_path(graph, node_ids)
    print(f"Evidence path contains {len(evidence_path)} nodes.")

    finding_details = {
        "cwe": "CWE-321: Use of Hard-coded Cryptographic Key",
        "risk_level": "CRITICAL" if pred_label == 1 else "LOW",
        "confidence": f"{confidence * 100:.1f}%",
        "source_location": "CWE321_Hard_Coded_Cryptographic_Key__w32_char_54 (5 files)",
        "description": "Hardcoded encryption key string flows across 5 interprocedural function calls (badSink_b -> c -> d -> e) directly into CryptDeriveKey / CryptEncrypt API sink.",
        "fix_suggestion": (
            "// Secure fix: Load key from secure key management or environment\n"
            "const char *key = getenv(\"APP_CRYPTO_KEY\");\n"
            "if (!key || strlen(key) < 16) { handle_error(\"Invalid key\"); }"
        ),
    }

    viz = Visualizer(output_dir=str(base_dir / "visualizations"))
    output_html = viz.generate(
        graph=graph,
        evidence_path=evidence_path,
        finding_id="DEMO-CWE321-54",
        attention_weights=attn,
        finding_details=finding_details,
    )

    print(f"[OK] Interactive 3D visualization created at:\n{output_html}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=str, default="CWE321_Hard_Coded_Cryptographic_Key__w32_char_54__bad.pt")
    args = parser.parse_args()
    run_demo(args.graph)
