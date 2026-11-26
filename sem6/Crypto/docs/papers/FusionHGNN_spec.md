# FGH ("Fusion Graph + Hyperbolic" / "FusionHGNN") — Paper Spec

Source: `COMPARISON_PAPER/Base_paper.pdf` — Li, Bhattacharjya, Li, Zhou,
Wisniewski, Bazydlo, "A Novel Method for Vulnerability Detection Based on
Fusion and Hyperbolic Neural Network Graphs," IEEE TSE, Vol. 52, No. 3,
March 2026.

The paper's own abbreviation for its method is **FGH**. CLAUDE.md's task
brief calls this method "FusionHGNN" (matching this repo's existing file/
class names `src/models/baselines/fusion_hgnn.py:FusionHGNN`,
`configs/fusion_hgnn_config.yaml`). Per CLAUDE.md §9 ("method names differ
from the PDF → use the paper's name"), the paper's name is FGH; this
deviation (keeping the existing `FusionHGNN` identifier already used
throughout the codebase instead of renaming to FGH) is recorded in the
faithfulness table below and in `docs/ASSUMPTIONS.md`.

## Summary

FGH builds a **Fusion Graph (FG)** per function/file by taking the union of
AST, CFG, and DDG (data-dependency graph) edges produced by Joern, fuses
each node's structural + GraphCodeBERT semantic features via a learned
linear projection, then runs a multi-layer **Hyperbolic Graph Neural
Network** (Poincaré ball, curvature c=3.5) with a distance-aware attention
aggregation and sum-based READOUT, followed by a classifier. The claimed
contribution is combining three graph views (not just one) with hyperbolic
embedding to match C/CPP code's tree-like hierarchical structure.

## Input representation

- Graph: union of AST + CFG + DDG edges (`FG = AST ∪ CFG ∪ DDG ∪ R(...)`),
  node types include METHOD, PARAM, BLOCK, METHOD_RETURN (per Fig. 3).
- Node features initialized from GraphCodeBERT embeddings fused with
  structural one-hot features via a learned linear projection
  (`W · CONCAT(α^ast·AST, α^cfg·CFG, α^ddg·DDG) + b`).
- Edge types: AST parent-child, CFG control-flow, DDG data-flow.

## Model architecture

1. Exponential map Euclidean → Poincaré ball, curvature c=3.5 (Eq. 2).
2. L layers of hyperbolic feature transformation (Möbius matrix-vector
   multiplication + Möbius addition, Eq. 3–5).
3. Neighbourhood aggregation with a distance-and-degree-aware attention
   coefficient `α_ij = softmax(1/sqrt(d̃_i d̃_j) × D_c(x_i^H, x_j^H))`
   (Eq. 6–8), tangent-space mean aggregation.
4. Hyperbolic non-linear activation at variable curvature (Eq. 9).
5. Sum READOUT over final-layer node embeddings → graph embedding (Eq. 10).
6. (Implicit, not detailed in the excerpted sections) a classification head
   on top of the graph embedding.

## Training setup (paper, Devign-style setup)

- Datasets: SBP (smart contracts), Devign (27,318 C/C++ functions from
  QEMU/FFmpeg via CodeXGLUE), SARD. Reported headline number: 87.34%
  accuracy on Devign, c=3.5, L=3 layers, embedding dim 256.
  split 80/20 train/test, stratified, 10-fold cross-validation for
  stability.
- Optimizer, learning rate, batch size, number of epochs: **not specified**
  in the excerpted sections of the paper.
- No explicit mention of dropout, weight decay, or early-stopping patience.

## Not specified in the paper

- Optimizer name/lr/batch size/epochs/weight decay/dropout.
- Exact classifier head architecture after READOUT.
- How GraphCodeBERT is obtained/fine-tuned in an offline setting.
- Val split (paper only reports train/test, not train/val/test).

## Faithfulness table

| Component | Paper says | What we implement (`src/models/baselines/fusion_hgnn.py`) | Reason for deviation |
|---|---|---|---|
| Graph construction | Joern AST ∪ CFG ∪ DDG, GraphCodeBERT node init | CryptoHGNN's existing 34-dim crypto-semantic node features over the same interprocedural graph (AST/CFG/call-graph derived); no GraphCodeBERT | No offline GraphCodeBERT weights available in this environment (ambiguity default §9: "needs a resource we don't have → closest local substitute, log it, mark the row"); reusing CryptoHGNN's node features also satisfies CLAUDE.md's "same dataset, same labeling... same I/O conventions" requirement so the comparison isolates the *model*, not the *feature extractor* |
| Curvature | c = 3.5 | c = 3.5 | faithful |
| Depth | L layers (unspecified exact L in excerpt; Table uses L=3 for headline Devign result) | 3 `HyperbolicGraphConv` layers | faithful (matches paper's headline config) |
| Aggregation | distance-and-degree-aware softmax attention (Eq. 6–8) | tangent-space **mean** pooling only at READOUT, standard GCN-style normalized aggregation inside each layer (reusing `src/models/manifolds/poincare.py:HyperbolicGraphConv`, the same primitive CryptoHGNN's own layers use) | Implementing the paper's exact distance-aware attention coefficient (Eq. 6) was out of scope to build from scratch without the paper's reference code; the simpler aggregation is the closest locally-buildable faithful variant. Logged as the main architectural deviation. |
| Readout | sum READOUT (Eq. 10) | global **mean** pool in tangent space | Paper specifies sum; implementation uses mean (an intentional difference already present in this repo's pre-existing baseline code, documented in its docstring) |
| Classifier head | not detailed | 2-layer MLP (Linear→ReLU→Dropout→Linear) | standard choice, consistent with CryptoHGNN's own classifier head for architectural parity |
| Hyperparameters (lr, batch, epochs) | not specified | lr=1e-3, weight_decay=1e-4, batch_size as configured, epochs reduced from an initial 300 to a compute-budget value (see `docs/ASSUMPTIONS.md`) | paper omits these; CryptoHGNN's own config values reused per §9 default |
| num_classes | not applicable (paper reports Acc/Pre/Rec/F1 on binary vulnerable/not) | 2 (binary) | matches CryptoHGNN's label scheme, per CLAUDE.md §5 |
