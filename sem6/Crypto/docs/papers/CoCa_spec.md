# CoCa — Paper Spec

Source: `COMPARISON_PAPER/Coca.pdf` — Cao, Sun, Wu, Lo, Bo, Li, Liu, "CoCa:
Improving and Explaining Graph Neural Network-Based Vulnerability Detection
Systems," ICSE '24.

## Summary

CoCa is a **framework**, not a single fixed architecture: it wraps an
existing off-the-shelf GNN-based vulnerability detector (e.g. Devign,
ReVeal, DeepWuKong) and replaces its feature encoder with one trained via
combinatorial contrastive learning (`CoCa_Tra`, the "Trainer"), then adds a
post-hoc, dual-view (factual + counterfactual) causal-inference explainer
(`CoCa_Exp`, the "Explainer") that extracts a minimal, concise sub-graph of
crucial statements justifying a "vulnerable" prediction.

## Input representation

- Code parsed into structural graphs — "code tokens/statements as nodes,
  structural relations as edges" (Code Property Graphs / GGNN-style graphs,
  depending on the wrapped baseline). This repo's comparative pipeline
  parses with tree-sitter via CryptoHGNN's own `External_scanner/c_parser.py`
  (reused, not re-implemented), consistent with the paper's own choice to
  use tree-sitter for parsing augmented variants (§6.3).
- Six token/statement-level **semantics-preserving augmentation operators**
  used to build contrastive positive pairs: Function/Variable Renaming
  (FR/VR), Operand Swap (OS), Statement Permutation (SP), Loop Exchange
  (LX), Block Swap (BS, if/else), Switch-to-If (SI). Applied with equal
  probability 0.5, averaging 3 transformations per program.

## Model architecture

1. **Trainer (`CoCa_Tra`)**: wraps the target detector's existing GNN
   feature encoder `f(·)`; trains it with combinatorial **contrastive
   learning** — NCE loss (Eq. 1) pulling together representations of
   augmented variants of the same program and pushing apart different
   programs — optionally combined with supervised cross-entropy
   (`CE`/`InfoNCE`/`NCE` variants in Table 2).
2. A classifier (described as "a convolutional layer with max-pooling") is
   trained on top of the frozen/fine-tuned encoder's representations.
3. **Explainer (`CoCa_Exp`)**: given a frozen, trained detector, extracts a
   sub-graph `G'_k = (A_k ⊙ M*_k, X_k ⊙ F*_k)` of nodes/edges via dual-view
   (factual `L_f` + counterfactual `L_c`) causal-inference optimisation
   (Eq. 6–8), trading off conciseness (`||M*||_1 + ||F*||_1`) against
   factual/counterfactual explanation strength.

## Training setup (paper)

- Encoder training: Adam optimizer, learning rate **1e-5**, batch size
  **256**, projection head output dim **128**, contrastive temperature
  **τ = 0.07**. Max **100 epochs with early stopping**.
- Explainer: `α = 0.5` trade-off between factual and counterfactual terms
  (Eq. 8).
- Dataset: a merged 335,671-function corpus (Devign, ReVeal, Big-Vul,
  CrossVul, CVEFixes), 80/10/10 train/val/test, 10 repeated runs to control
  for randomness.
- Hardware: Ubuntu 18.04, 2× NVIDIA Tesla V100.

## Not specified in the paper

- The exact GNN layer type/depth used as the "off-the-shelf feature
  encoder" is whichever baseline (Devign/ReVeal/DeepWuKong) is being
  wrapped — CoCa itself does not define a GNN architecture, only the
  training/explanation procedure around one.
- Exact classifier head dimensions ("a convolutional layer with
  max-pooling") beyond that one-line description.
- Weight decay / dropout for the encoder.

## Faithfulness table

| Component | Paper says | What we implement (`src/models/baselines/coca.py`) | Reason for deviation |
|---|---|---|---|
| Base GNN encoder | Unspecified — CoCa wraps an existing detector's GNN (paper uses Devign/ReVeal/DeepWuKong) | 3-layer GATConv (8 heads), Euclidean, as a concrete stand-in detector architecture | The paper deliberately leaves the base encoder a free choice; a 3-layer GAT is a standard, commonly-used vulnerability-detection GNN and lets us compare an attention-based Euclidean baseline against CryptoHGNN's hyperbolic model, which is the point of this comparison |
| Contrastive trainer (`CoCa_Tra`) | 6 augmentation operators + NCE/InfoNCE contrastive loss, 1e-5 lr, batch 256, 100 epochs | **Not implemented**: trained with plain supervised cross-entropy only, no augmentation-based contrastive pre-training stage | Implementing all 6 AST-level augmentation operators (safe semantics-preserving renaming/swap/permutation on parsed C) plus a full contrastive pre-training loop was out of scope for this comparative pass; this is the single largest faithfulness gap and is the main reason CoCa's numbers here should be read as "the base detector CoCa would wrap," not "CoCa's full robustness-enhanced pipeline" |
| Explainer (`CoCa_Exp`) | dual-view causal inference (factual + counterfactual, Eq. 6–8) | Simplified single-view (factual-only) gradient-based edge-saliency extractor (`Coca.extract_subgraph`) — GradCAM-style saliency on a learnable per-edge weight, thresholded at the 75th percentile | Full dual-view causal optimisation (Eq. 8, joint factual+counterfactual with L1 sparsity) requires solving a small constrained optimisation per explanation; the gradient-saliency approximation captures the paper's core idea (post-hoc, frozen-model explanation) without the counterfactual term |
| Batch size / lr | 256 / 1e-5 (for contrastive pre-training on a 335k-function corpus) | per-config value (reduced given this comparison trains a classifier directly on a few hundred small graphs, not a 335k-function contrastive corpus) — see `docs/ASSUMPTIONS.md` | batch size 256 and lr 1e-5 are tuned for the paper's much larger contrastive pre-training batch; using them unchanged for direct small-dataset supervised classification here would not converge in the available epoch budget |
| num_classes | binary vulnerable/not (Table 2: Acc/Pre/Rec/F1) | 2 (binary) | faithful, matches CryptoHGNN's label scheme |
