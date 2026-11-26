"""
scan_real_repo.py: Performs interprocedural cryptographic analysis on real-world
C codebases (e.g., OpenSSL EVP, libssh) and produces interactive 3D security graph visualizations.
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

from External_scanner.interproc_graph_builder import InterprocGraphBuilder
from models.gnns.crypto_hgnn import CryptoHGNN
from agents.visualizer import Visualizer


def scan_repository(
    repo_path: str,
    case_name: str,
    max_files: int = 12,
    output_html: str = "",
):
    repo_dir = Path(repo_path)
    if not repo_dir.exists():
        print(f"Error: Repository path '{repo_path}' does not exist.")
        return

    # Find C source files
    c_files = sorted(list(repo_dir.glob("**/*.c")))
    if not c_files:
        print(f"No .c files found in {repo_path}")
        return

    selected_files = [str(f) for f in c_files[:max_files]]
    print(f"\n[CryptoFlow v2] Scanning '{case_name}' across {len(selected_files)} C source files...")
    for f in selected_files:
        print(f"  - {Path(f).name}")

    # Build interprocedural graph
    builder = InterprocGraphBuilder()
    graph = builder.build_from_file_group(
        file_paths=selected_files,
        label=0,
        group_id=case_name,
        context="full",
    )

    num_nodes = graph.x.size(0) if graph.x is not None else 0
    num_edges = graph.edge_index.size(1) if graph.edge_index is not None else 0
    print(f"[+] Interprocedural graph constructed: {num_nodes} nodes, {num_edges} edges.")

    # Model inference
    ckpt_path = base_dir / "models" / "checkpoints" / "crypto_hgnn_best.pt"
    model = CryptoHGNN()
    if ckpt_path.exists():
        model.load_state_dict(torch.load(ckpt_path, weights_only=True))
    model.eval()

    with torch.no_grad():
        out, attn = model(graph, return_attention=True)
        probs = torch.softmax(out, dim=-1)
        pred_label = out.argmax(dim=-1).item()
        confidence = probs[0, pred_label].item()

    verdict = "VULNERABLE" if pred_label == 1 else "BENIGN (Secure Usage)"
    print(f"[+] CryptoHGNN classification: {verdict} (Confidence: {confidence * 100:.2f}%)")

    # Find evidence / key nodes
    node_ids = getattr(graph, "node_ids", [f"node_{i}" for i in range(num_nodes)])
    evidence_nodes = []
    for idx, nid in enumerate(node_ids):
        nid_low = nid.lower()
        if "key" in nid_low or "secret" in nid_low or "cipher" in nid_low or "encrypt" in nid_low or "evp_" in nid_low:
            evidence_nodes.append(nid)

    finding_details = {
        "cwe": "CWE-327 / API Architecture Analysis" if pred_label == 0 else "CWE-321: Potential Secret Flow",
        "risk_level": "LOW" if pred_label == 0 else "HIGH",
        "confidence": f"{confidence * 100:.1f}%",
        "source_location": f"{case_name} ({len(selected_files)} source files)",
        "description": (
            f"Interprocedural cryptographic call and dataflow graph generated from production {case_name}. "
            "CryptoHGNN evaluated hierarchical wrapper structures and parameter flow into cipher primitives."
        ),
        "fix_suggestion": (
            "// Architectural Verification\n"
            "Ensure proper EVP_CIPHER_CTX_cleanup / EVP_CIPHER_CTX_free and\n"
            "validate that all key material is zeroized using OPENSSL_cleanse()."
        ),
    }

    viz_dir = base_dir / "visualizations"
    viz = Visualizer(output_dir=str(viz_dir))

    target_name = output_html or f"{case_name}_case_study"
    out_path = viz.generate(
        graph=graph,
        evidence_path=evidence_nodes,
        finding_id=target_name,
        attention_weights=attn,
        finding_details=finding_details,
    )

    print(f"[OK] Case study 3D visualization generated at:\n    {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=str, required=True, help="Path to codebase directory")
    parser.add_argument("--name", type=str, required=True, help="Case study identifier")
    parser.add_argument("--max_files", type=int, default=10, help="Max files to include in interproc graph")
    parser.add_argument("--output", type=str, default="", help="Output HTML filename")
    args = parser.parse_args()

    scan_repository(args.repo, args.name, args.max_files, args.output)


if __name__ == "__main__":
    main()
