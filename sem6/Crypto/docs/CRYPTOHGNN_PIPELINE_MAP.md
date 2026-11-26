> **Note:** this document describes the original split (55 hand-written test graphs).
> The split was replaced; see the update at the top of `docs/RUN_REPORT.md`.

# CryptoHGNN Pipeline Map (Phase 0 discovery)

This document records CryptoHGNN's existing pipeline, read-only, as the
template that the FusionHGNN and CoCa comparative pipelines mirror.

## Environment note (read before anything else)

This agent ran in a git worktree isolated from the main checkout. Two
artifacts described as already present in the main checkout were **not**
present in this worktree and had to be reconstructed/regenerated here
(read-only against CryptoHGNN's own code — no CryptoHGNN source file was
modified to do this):

1. **`datasets/juliet-test-suite-c/`** (raw Juliet C sources, gitignored,
   ~556MB) and **`datasets/interproc_graphs/*.pt`** (gitignored, cached PyG
   graphs) are both excluded from git (see `.gitignore`:
   `datasets/juliet/`, `datasets/graphs/*.pt`, `datasets/interproc_graphs/`).
   They were copied in from the sibling checkout at
   `/home/seeker/Projects/CryptoHGNN` (read-only copy of untracked data, not
   a git operation) so this worktree has the same inputs.
2. **A real, pre-existing bug was found and fixed as part of Phase 0**:
   `datasets/juliet_groups.json` (the manifest consumed by
   `scripts/build_interproc_dataset.py`) references source files under
   `datasets/juliet/testcases/...`, but the actual cloned Juliet checkout on
   disk is named `datasets/juliet-test-suite-c/` (matching the path given in
   this task's own instructions). Because of this path mismatch, the
   previously-cached `datasets/interproc_graphs/*.pt` files were almost all
   **empty graphs** (600 of 655 had zero nodes) even though
   `datasets/interproc_stats.csv` recorded non-zero node/edge counts for
   them — i.e. the cache was stale/corrupted relative to its own index.
   Fix applied: created a symlink `datasets/juliet -> datasets/juliet-test-suite-c`
   (no code or manifest file changed) and re-ran
   `scripts/build_interproc_dataset.py` to regenerate
   `datasets/interproc_graphs/*.pt` and `datasets/interproc_stats.csv` from
   scratch. This is read-only reuse of CryptoHGNN's own loader/builder code,
   not a modification of it. Result: 655/655 graphs now have real nodes/edges
   (train avg 25.2 nodes, val avg 37.1 nodes, test avg 5.4 nodes; 0
   cross-split duplicate hashes, confirming no train/test leakage). This is
   logged in `docs/ASSUMPTIONS.md`.

## Pipeline stages (file : function)

| # | Stage | File : function | Input | Output |
|---|-------|------------------|-------|--------|
| 1 | Manifest | `datasets/juliet_groups.json` (static, produced by `scripts/audit_juliet.py`, not re-run here) | Juliet CWE directory tree | JSON list of `{group_id, base_group, cwe, split, label, context, files, n_files}` (655 entries) |
| 2 | Graph construction | `scripts/build_interproc_dataset.py:main` → `External_scanner/interproc_graph_builder.py:InterprocGraphBuilder.build_from_file_group` | Juliet `.c` file group + manifest row | `torch_geometric.data.Data(x:[N,34], edge_index:[2,E], edge_attr:[E,12], y:[1], node_ids, group_id)` saved as `datasets/interproc_graphs/<group_id>.pt`; summary row appended to `datasets/interproc_stats.csv` |
| 3 | Semantic engine (feature enrichment) | `External_scanner/semantic_engine.py`, `External_scanner/macro_expander.py`, `External_scanner/wrapper_resolver.py`, `External_scanner/alias_tracker.py` | Parsed C AST (`External_scanner/c_parser.py:CParser`) | Node/edge type + crypto-role annotations folded into the 34-dim node feature vector (`External_scanner/graph_schema.py:encode_node_features`, `NODE_FEATURE_DIM=34`) |
| 4 | Dataset split & load | `models/training/train.py:load_dataset_by_split`, `models/training/evaluate.py:load_test_data` (read via `External_scanner/safe_io.py:safe_load_graph`) | `datasets/interproc_stats.csv` `split` column + `datasets/interproc_graphs/*.pt` | Three `List[torch_geometric.data.Data]` (train/val/test) |
| 5 | Model | `src/models/cryptohgnn.py:CryptoHGNN` (also `models/gnns/crypto_hgnn.py`, an earlier variant) — Poincaré-ball hyperbolic GNN, curvature c=1.0, 3 `HyperbolicGraphConv` layers, tangent-space attention-gated pooling, 2-layer MLP classifier. Hyperbolic primitives in `src/models/manifolds/poincare.py`. | PyG `Data` batch | `logits [B, num_classes]` (optionally `(logits, attn[N])`) |
| 6 | Training | `models/training/train.py:train_all_models` / `train_epoch` | train/val loaders, `config.py` hyperparameters (`NUM_EPOCHS=300, BATCH_SIZE=8, LEARNING_RATE=1e-3, WEIGHT_DECAY=1e-4, PATIENCE=30`) | Best checkpoint `models/checkpoints/<name>_best.pt`, per-epoch log `results/training_logs.csv` |
| 7 | Evaluation | `models/training/evaluate.py:run_main_evaluation` / `evaluate_model` | Test split + checkpoint | `results/main_results.csv` with accuracy/precision/recall/f1/fp_rate/fn_rate/runtime, computed from a binary (vulnerable=1 / not=0) confusion matrix |
| 8 | Agentic scan / visualization | `agents/repo_scanner_agent.py:RepoScannerAgent` (instantiates `CryptoHGNN(num_classes=2)` — this is the actual binary label scheme CryptoHGNN uses operationally) → `agents/visualizer.py:Visualizer` (3D Plotly scene of the code graph, colored by `External_scanner/graph_schema.py` node/edge types) | Repo path or test case | HTML/Plotly findings report |

## Labels

- Binary: `label = 1` (vulnerable / "bad" Juliet variant) vs `label = 0`
  (not vulnerable / "good" variant), stored per-group in
  `datasets/interproc_stats.csv:label` and as `Data.y` in each cached graph.
- `configs/cryptohgnn_config.yaml` sets `architecture.num_classes: 5` — this
  is for a *separate*, not-exercised-here multi-class CWE-typing experiment
  (5 target CWEs: 321/327/338/256/259). CryptoHGNN's actually-used evaluation
  code (`models/training/evaluate.py`, `agents/repo_scanner_agent.py`) treats
  the task as binary (`CryptoHGNN(num_classes=2)`, confusion matrix with
  `pred==1`/`actual==1`). Per CLAUDE.md §5 ("use CryptoHGNN's label scheme"),
  the comparative pipelines use **binary**, matching the code that is
  actually run, not the unused 5-class default. Logged in `docs/ASSUMPTIONS.md`.

## Split, seed, storage

- Split is pre-assigned per-group in `datasets/juliet_groups.json` /
  `datasets/interproc_stats.csv` (`split` column: train/val/test), generated
  by `scripts/audit_juliet.py` (not re-run; the manifest already existed).
  Test split uses `context="full"` groups (whole CWE test case, not the
  context-filtered bad/good halves used for train/val) — 55 groups.
- No single documented "seed" constant governs CryptoHGNN's existing split
  (it's a static pre-computed manifest, not re-sampled at train time).
  `src/common/data.py:SEED = 42` is the seed this comparative work fixes for
  model init / shuffling / anything stochastic in training, applied
  identically to all three methods via `set_global_seed()`.
- Split indices are saved by the comparative pipelines to
  `data/splits/<method>_split_seed42.csv` (group_id, cwe, label, split) for
  reproducibility, mirroring CryptoHGNN's own "saved split" intent.

## How to run (CryptoHGNN, unmodified)

```
python models/training/train.py        # trains all 4 CryptoFlow GNN variants
python models/training/evaluate.py     # evaluates on test split -> results/main_results.csv
python -m agents.repo_scanner_agent --help
```

## How to run (this comparative work)

```
python -m src.pipelines.cryptohgnn.run --config configs/cryptohgnn_config.yaml
python -m src.pipelines.fusion_hgnn.run --config configs/fusion_hgnn_config.yaml
python -m src.pipelines.coca.run --config configs/coca_config.yaml
python run_comparative.py --epochs 150   # all three, in sequence, writes results/tables/comparison.csv
```
