# Reproducing CryptoFlow v2 Experiments

This guide outlines the exact, end-to-end steps to reproduce all dataset generation, model training, evaluation metrics, ablation studies, attention analyses, and 3D visualizations from scratch.

---

## Prerequisites

- **Python**: 3.10 to 3.13 (64-bit)
- **Virtual Environment**: `.venv`
- **Dependencies**: `torch`, `torch-geometric`, `tree-sitter`, `tree-sitter-c`, `plotly`, `numpy`, `pytest`

```bash
# Setup environment
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Step 1: Run Unit Tests & Verify Parser

Verify that the AST parser and semantic analysis passes all 81 regression and component tests:

```bash
python -m pytest tests/
```

*Expected output: 81 passed in ~3.5 seconds.*

---

## Step 2: Build Interprocedural Graphs

Generate the 655 graph dataset from the NIST Juliet Test Suite across CWE-321, CWE-327, CWE-338, CWE-256, and CWE-259:

```bash
python scripts/build_interproc_dataset.py
```

*Outputs:*

- `datasets/interproc_graphs/*.pt` (655 graph files)
- `datasets/interproc_stats.csv` (split, label, node/edge counts, call depth)

---

## Step 3: Train All 4 Models

Train GenericGNN, CryptoGNN, GenericHGNN, and CryptoHGNN on the project-split interprocedural dataset:

```bash
python models/training/train.py
```

*Outputs:*

- Checkpoints in `models/checkpoints/` (`crypto_hgnn_best.pt`, `generic_hgnn_best.pt`, `crypto_gnn_best.pt`, `generic_gnn_best.pt`)
- Epoch-by-epoch metrics in `results/training_logs.csv`

---

## Step 4: Evaluate Models on Held-Out Test Split

Compute Accuracy, Precision, Recall, F1, FPR, FNR, and Inference Latency:

```bash
python models/training/evaluate.py
```

*Outputs:*

- `results/main_results.csv`

---

## Step 5: Run Ablation Study

Evaluate the 7 ablation variants (masking source types, wrapper calls, crypto semantics, interprocedural edges, HGNN vs GNN, and random edge shuffling):

```bash
python models/training/ablation_study.py
```

*Outputs:*

- `results/ablation_study.csv`

---

## Step 6: Attention Analysis Across Node Types

Analyze how attention weights distribute across `KEY`, `CRYPTO_API`, `WRAPPER`, `FUNCTION`, and `FILE` nodes:

```bash
python scripts/attention_analysis.py
```

*Outputs:*

- `results/attention_by_node_type.csv`

---

## Step 7: Generate 3D Interactive Visualizations

Generate the standalone interactive 3D WebGL visualizations with the glassmorphic security sidebar:

```bash
# Demo Juliet interprocedural finding:
python scripts/demo_visualize.py

# Real-world OpenSSL EVP case study:
python scripts/scan_real_repo.py --repo datasets/case_studies/openssl/crypto/evp --name openssl --max_files 8 --output openssl_case_study

# Real-world libssh case study:
python scripts/scan_real_repo.py --repo datasets/case_studies/libssh/src --name libssh --max_files 6 --output libssh_case_study
```

*Outputs:*

- `visualizations/DEMO-CWE321-54.html`
- `visualizations/openssl_case_study.html`
- `visualizations/libssh_case_study.html`

Open any of these `.html` files in any modern web browser to interactively inspect the 3D call hierarchy and vulnerability evidence flows.

---

## Step 8: Multi-CWE Semantic Scanning & Click-to-Code Navigation

Scan arbitrary directories or open-source repositories and generate interactive 3D visualizations with instant `vscode://` IDE jump links:

```bash
# Quick verification test suite:
python External_scanner/semantic_engine.py Day5_test

# Full repository scans (e.g. mbedTLS, Redis):
python External_scanner/semantic_engine.py datasets/opensource_examples/mbedtls --vis-dir visualizations/mbedtls
```

For complete usage options, see [docs/RUN_COMMANDS.md](file:///c:/Users/heram/Desktop/Crypto/docs/RUN_COMMANDS.md).

