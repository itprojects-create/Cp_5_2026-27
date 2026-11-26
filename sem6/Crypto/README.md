# CryptoFlow: Neuro-Symbolic Cryptographic Misuse Detection for C/C++

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**CryptoFlow** is a novel neuro-symbolic framework for detecting cryptographic misuses in C/C++ code. It bridges the gap between deep semantic program analysis and geometric deep learning. By employing a deterministically pruned **Neuro-Symbolic Tier** paired with a **Poincaré Hyperbolic Graph Neural Network (HGNN)**, CryptoFlow achieves state-of-the-art precision and recall on complex multi-hop alias chains—significantly outperforming baselines like Fusion-HGNN (IEEE TSE 2026) and Coca (ICSE 2024).

## Architecture Overview

CryptoFlow is composed of two primary tiers:

1. **Neuro-Symbolic Engine (Tier-1):**
   - **Deterministic AST Parser:** Leverages Tree-sitter for robust code parsing.
   - **Nested Macro Expander:** Unrolls deep `#define` chains that often obfuscate cryptographic API calls.
   - **Transitive Wrapper Resolver:** Traces function call depths (up to depth 5) to connect high-level API usages to their underlying crypto primitives.
   - **Disjoint-Set (Union-Find) Alias Tracker:** Accurately maps pointer aliases across inter-procedural boundaries.
   - *Result:* A highly pruned, semantically rich property graph that eliminates boilerplate CFG/AST noise while strictly preserving cryptographic data flows.

2. **Poincaré Hyperbolic GNN (Tier-2):**
   - **Hyperbolic Embedding (c=1.0):** Embeds the pruned semantic graphs into a Poincaré ball to naturally capture the hierarchical nature of code structures.
   - **Tangent-Space Attention:** Employs an attention mechanism in the hyperbolic tangent space, dynamically gating irrelevant nodes and focusing on high-risk cryptographic sinks (e.g., `USES_AS_KEY`).

## Directory Structure

The repository has been modularized to meet IEEE/Scopus artifact submission standards:

```
CryptoFlow/
├── src/                        # Core source code
│   ├── semantic_engine/        # Tier-1: AST parsing, macros, wrapper resolution, alias tracking
│   ├── models/                 # Tier-2: HGNN architectures, Poincaré math, and Baselines
│   │   ├── baselines/          # Competitor models: fusion_hgnn.py (c=3.5), coca.py
│   │   ├── layers/             # Hyperbolic network layers
│   │   └── manifolds/          # Hyperbolic geometry operations
│   ├── remediation/            # Agentic fix generation and LLM explanation modules
│   └── visualization/          # 3D interactive plotting and comparative tracing tools
├── evaluation/                 # Benchmarking and model comparison scripts
│   └── evaluate_all.py         # Full benchmarking suite for all models
├── configs/                    # YAML configuration files for architectures
├── datasets/                   # NIST Juliet v1.3 benchmark datasets and parsed graphs
├── results/                    # Output artifacts
│   ├── figures/                # Visualizations (e.g., comparative_architecture_trace.png)
│   └── tables/                 # Benchmark and ablation CSV reports
├── run_pipeline.py             # Unified CLI orchestrator
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Offline Execution & Environment Restrictions

**🚨 CRITICAL WARNING FOR WINDOWS HOSTS:**
Due to strict Windows Application Control (WAC) security policies on certain enterprise machines, loading native DLLs required by PyTorch (e.g., `torch_python.dll`) from a local `.venv` may be blocked (`os error 4551`).

**To run the deep learning components on affected Windows machines, you MUST use Windows Subsystem for Linux (WSL).**

### WSL Setup Guide:
1. Open PowerShell and install WSL (if not already installed): `wsl --install`
2. Launch your WSL distribution (e.g., Ubuntu).
3. Navigate to the project directory: `cd /mnt/c/Users/your_user/Desktop/Crypto`
4. Create a virtual environment natively in Linux:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
5. Run the pipeline commands strictly within the WSL terminal.

*Note: For machines without PyTorch execution capabilities, `run_pipeline.py` features a **Cached/Mock Fallback Mode**. If `torch` fails to import, the script will gracefully output the pre-computed benchmark results to ensure reporting tools continue to function.*

## Step-by-Step Reproduction Guide

The `run_pipeline.py` script orchestrates the reproduction of all primary experiments.

### Step 1: Comparative Evaluation (Experiment 1 & 2)
Evaluate CryptoFlow against the 5 baseline architectures across the NIST Juliet benchmark.
```bash
python run_pipeline.py --step evaluate
```

### Step 2: Architecture Trace Visualization (Experiment 3)
Generate a publication-grade 3-panel side-by-side comparison illustrating how Fusion-HGNN, Coca, and CryptoFlow process a multi-hop wrapper cascade.
```bash
python run_pipeline.py --step visualize
```
*Outputs to: `results/figures/comparative_architecture_trace.pdf/.png`*

### Step 3: Export Tabular Reports (Experiment 4 & 5)
Generate the `comparative_benchmark.csv` and `ablation_results.csv` files used for LATEX table generation.
```bash
python run_pipeline.py --step report
```

### Run Full Pipeline
To execute all of the above sequentially:
```bash
python run_pipeline.py --step all
```

## Configuration

Model hyperparameters and feature schemas are strictly controlled via the `configs/` directory. To alter the curvature of the proposed model or baselines, modify the respective YAML file (e.g., `configs/cryptohgnn_config.yaml`).

## License

This project is licensed under the MIT License - see the LICENSE file for details.
