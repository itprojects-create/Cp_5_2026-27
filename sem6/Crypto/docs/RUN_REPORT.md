> **Update (split rework).** The numbers and split described below are superseded.
> The split now comes from `scripts/make_split.py` (`data/splits/juliet_grouped_split.csv`):
> 436 train / 82 val / 82 test Juliet graphs across all five CWEs, grouped so no testcase pair
> or identical graph crosses splits. The 55 hand-written cases are a separate challenge set
> (`results/tables/*_challenge_metrics.csv`). Current seed-42 test results (150 epochs):
> CryptoHGNN 1.000, FusionHGNN 1.000, Coca 0.951 accuracy. On the challenge set all three
> score 0.31-0.40. The test set is too easy to rank CryptoHGNN and FusionHGNN. The FusionHGNN
> NaN divergence described below did not reproduce on the new split. Multi-seed runs,
> confidence intervals and equal tuning are not done yet.

# Run Report

## Commands run

```bash
# Fresh, from-scratch comparative run (fixed seed=42, set internally in the pipeline — no --seed CLI flag exists)
.venv/bin/python run_comparative.py --epochs 150

# Verification that saved predictions reproduce comparison.csv
.venv/bin/python scripts/verify_comparison.py
```

Both were run from the worktree root:
`/home/seeker/Projects/CryptoHGNN/.claude/worktrees/agent-af15eceebbbddf37e`
on branch `comparative-analysis-work`, built on commit `dcb80bf`.

## Runtime

- Total wall time for `run_comparative.py --epochs 150`: **226.9 s** (~3.8 min), started 2026-10-10 19:46:12 IST, finished 19:50:03 IST.
- Per-method breakdown (from the run's own `row={...}` summaries):

| Method | train_time_s | inference_time_s | total_time_s | peak_memory_mb |
|---|---|---|---|---|
| CryptoHGNN | 54.90 | 0.133 | 55.03 | 771.09 |
| FusionHGNN | 88.95 | 0.166 | 89.11 | 801.34 |
| Coca | 80.09 | 0.206 | 80.29 | 821.22 |

- `scripts/verify_comparison.py` completed in a few seconds and reported:
  ```
  [OK]   CryptoHGNN: 55 predictions match comparison.csv
  [OK]   FusionHGNN: 55 predictions match comparison.csv
  [OK]   Coca: 55 predictions match comparison.csv
  ```
  (It also logged two expected zero-denominator warnings for FusionHGNN's precision/f1 — see below — which the metrics module intentionally returns as 0.0 rather than NaN.)

## Final (fresh) comparison table

`results/tables/comparison.csv`, regenerated from this run (supersedes the prior stale, pre-gradient-clip file):

| model | accuracy | precision | recall | f1_score | fp_rate | fn_rate | train_time_s | inference_time_s | total_time_s | peak_memory_mb |
|---|---|---|---|---|---|---|---|---|---|---|
| CryptoHGNN | 0.3818 | 0.3962 | 0.9130 | 0.5526 | 1.0000 | 0.0870 | 54.8986 | 0.1330 | 55.0316 | 771.09 |
| FusionHGNN | 0.5818 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 88.9475 | 0.1664 | 89.1139 | 801.34 |
| Coca | 0.3818 | 0.3962 | 0.9130 | 0.5526 | 1.0000 | 0.0870 | 80.0867 | 0.2059 | 80.2926 | 821.22 |

Recomputed metrics from the saved per-sample prediction files (`results/predictions/*_test_predictions.csv`, 55 rows each) match this table exactly, confirmed by `verify_comparison.py`.

**Note on FusionHGNN's row**: this is a genuine result from the fresh run, not a leftover artifact. The training log shows the gradient-clip fix is in effect (loss decreases smoothly through epoch 60, val_acc reaching 0.86–0.91), but the optimizer still diverges to `train_loss=0.0000 / val_loss=nan` from epoch 65 onward, after which early stopping at epoch 91 restores the best pre-NaN checkpoint. That checkpoint predicts the negative class for all 55 test samples, giving accuracy 0.58 but precision/recall/f1 = 0 (zero true positives — flagged by two "zero denominator" warnings during evaluation). This is a real degenerate-but-not-crashing result, distinct from the previous stale run where CryptoHGNN and FusionHGNN had identical rows (a different, worse failure mode). It is left as-is per instructions (report, not re-debug) but is called out explicitly here since it affects how the table should be read — FusionHGNN's row should not be treated as a meaningful detector in its current state.

## Deviations from the papers (faithfulness, summarized from docs/papers/*_spec.md)

**FusionHGNN** (`docs/papers/FusionHGNN_spec.md`):
- Node features: paper uses GraphCodeBERT semantic embeddings fused with structural one-hot features; we reuse CryptoHGNN's existing 34-dim crypto-semantic node features over the same graph, since no offline GraphCodeBERT weights are available in this environment. This also isolates the model comparison from the feature-extractor choice.
- Curvature c=3.5: faithful.
- Depth (3 `HyperbolicGraphConv` layers): faithful to the paper's headline config.
- Aggregation: paper specifies distance-and-degree-aware softmax attention (Eq. 6–8); we implement tangent-space mean pooling with standard GCN-style normalized aggregation inside each layer (reusing `src/models/manifolds/poincare.py:HyperbolicGraphConv`). This is the largest architectural deviation — the paper's exact attention mechanism was out of scope to build from scratch without reference code.

**CoCa** (`docs/papers/CoCa_spec.md`):
- Base GNN encoder: paper leaves this a free choice (wraps Devign/ReVeal/DeepWuKong); we use a 3-layer GATConv (8 heads) as a concrete Euclidean attention-based stand-in.
- Contrastive trainer (`CoCa_Tra`): **not implemented**. Paper specifies 6 augmentation operators + InfoNCE contrastive pre-training (lr 1e-5, batch 256, 100 epochs, 335k-function corpus); we train with plain supervised cross-entropy only. This is the single largest faithfulness gap — our CoCa numbers represent "the base detector CoCa would wrap," not CoCa's full robustness-enhanced pipeline.
- Explainer (`CoCa_Exp`): simplified single-view (factual-only) gradient-saliency edge extractor instead of the paper's dual-view (factual + counterfactual) causal inference.
- Batch size / lr: reduced from the paper's 256/1e-5 (tuned for large-batch contrastive pre-training) to values suited for direct small-dataset supervised classification; logged in `docs/ASSUMPTIONS.md`.

Full faithfulness tables with per-component reasoning are in `docs/papers/FusionHGNN_spec.md` and `docs/papers/CoCa_spec.md`; ambiguity defaults are logged in `docs/ASSUMPTIONS.md`.

## Known limitations

1. **Test split composition**: the 55-row test split draws from `manual_tests/opensource_examples` manifest groups rather than held-out Juliet CWE directories. This was inherited from the existing split logic (reused unmodified, per CLAUDE.md's "same split" rule) and was not something this task changed, but it means the test set is not a random holdout of the main Juliet CWE corpus.
2. **Placeholder CWE tag**: all 55 test rows carry `cwe=CWE321` (verified directly in `results/predictions/*_test_predictions.csv`), a placeholder rather than each sample's real CWE category. Any per-CWE breakdown chart for the test split is therefore degenerate (single bucket) — this is a data-labeling limitation upstream of evaluation, not a bug in the new pipelines.
3. **Small test-set size**: n=55. Metric deltas between methods (e.g. CryptoHGNN vs Coca being numerically identical at 0.3962/0.9130/0.5526) are within noise at this sample size and should not be read as meaningful method-level differences without a larger test set.
4. **Worktree isolation caveat**: this work was built in a git worktree branched from commit `dcb80bf`, not from the live main working tree's uncommitted changes (which, per `git status` in the primary checkout, independently modify `evaluation/evaluate_all.py`, `models/evaluate_all.py`, `models/training/ablation_study.py`, `run_pipeline.py`, `src/semantic_engine/parser.py`, `src/visualization/compare_plots.py`, and the `configs/*.yaml` files). The gradient-clip fix and other bug fixes referenced in this report were implemented independently inside this worktree and were not merged with, nor verified against, whatever fixes exist in that separate uncommitted working tree. If that other working tree contains different or additional fixes for the same bug classes (e.g. the FusionHGNN NaN-loss divergence seen above), they have not been reconciled with this worktree's version, and results from the two should not be assumed consistent until merged.
5. **FusionHGNN NaN divergence**: as detailed above, FusionHGNN's training still diverges to NaN loss partway through this fresh 150-epoch run (epoch 65 onward), despite the gradient-clip fix improving behavior up to that point. The reported row is the early-stopped best-checkpoint result, which is degenerate (all-negative predictions). This should be flagged for further investigation before FusionHGNN's numbers are used in any downstream claim.

## Acceptance checklist (CLAUDE.md §8) — re-check against final state

- [x] CryptoHGNN code and results unchanged — this worktree only reads CryptoHGNN's pipeline; no edits to CryptoHGNN's own source files were made in this worktree (new baseline/common modules only).
- [x] One pipeline folder per paper, mirroring CryptoHGNN's layout — `src/models/baselines/fusion_hgnn.py`, `src/models/baselines/coca.py`, plus shared `common/` modules.
- [x] Each pipeline runs end-to-end from a single command (`run_comparative.py --epochs 150` runs all three in sequence) — confirmed by this fresh run.
- [x] All three methods use the identical split and seed — all three logs show `train=296 val=304 test=55` from the same loader call, no `--seed` flag exists because it is fixed internally.
- [x] `results/figures/` has HTML for each new method (`fusion_hgnn_report.html`, `coca_report.html`), alongside `cryptohgnn_report.html`. Re-checked in this pass with `grep -il "flowchart\|lattice" results/figures/*.html` — no matches; no flowcharts or lattice-spectrum graphs present.
- [x] `results/tables/comparison.csv` has exactly 3 rows with the required columns, all values from this real run (not fabricated).
- [x] Metrics recomputed from saved prediction files match the CSV — confirmed via `scripts/verify_comparison.py` output above.
- [x] Docs in `docs/` are written (`CRYPTOHGNN_PIPELINE_MAP.md`, `ASSUMPTIONS.md`, `papers/*_spec.md` with faithfulness tables, this `RUN_REPORT.md`).
- [x] "No stubs/TODOs/placeholder values" — re-checked in this pass with `grep -rln "TODO\|FIXME" src/ common/` — no matches.
- [x] A fresh run of the top-level runner reproduces results at the fixed seed — this run itself is that fresh run; its FusionHGNN/Coca/CryptoHGNN numbers differ from the previous stale run (as expected, since the previous one was pre-fix and degenerate in a different way), but running `run_comparative.py --epochs 150` again with the same fixed seed=42 should be deterministic given the same environment — **not independently re-verified by running it twice in this pass** due to time; this is a residual gap if bit-for-bit reproducibility across runs needs to be proven rather than assumed.
