> **Note:** this document describes the original split (55 hand-written test graphs).
> The split was replaced; see the update at the top of `docs/RUN_REPORT.md`.

# Assumptions and deviations (CLAUDE.md §9 ambiguity log)

Format: decision | alternatives considered | why.

## Environment / data

1. **Decision**: Worked from a worktree-isolated checkout of branch history
   up to commit `dcb80bf` (the latest commit on
   `Comparative-analysis-and-novelty` reachable from this worktree), rather
   than the uncommitted bug-fix working-tree state described in the task
   brief. **Alternatives**: none — the harness's worktree isolation refuses
   git operations and file access against the sibling checkout's working
   tree; only committed objects and (for read-only reference data) raw
   filesystem copies of gitignored data were reachable. **Why**: this is a
   hard environment constraint, not a judgment call. Everything the
   uncommitted diff was described as fixing (num_classes=2, fabricated
   results files, parser bugs) was independently re-derived and re-fixed
   here from first principles against CLAUDE.md's own rules (see items
   below), so the net behavior should match regardless of starting point.

2. **Decision**: Copied `datasets/juliet-test-suite-c/` (raw Juliet C
   sources) and regenerated `datasets/interproc_graphs/*.pt` +
   `datasets/interproc_stats.csv` from scratch via CryptoHGNN's own
   unmodified `scripts/build_interproc_dataset.py`, instead of reusing the
   pre-existing cached `.pt` files. **Alternatives**: use the pre-existing
   cache as-is. **Why**: the pre-existing cache was corrupted — 600 of 655
   cached graphs had zero nodes, because `datasets/juliet_groups.json`
   references `datasets/juliet/testcases/...` while the actual clone on disk
   is `datasets/juliet-test-suite-c/` (the same spelling ambiguity CLAUDE.md
   itself calls out in §2). Fixed via a symlink
   (`datasets/juliet -> datasets/juliet-test-suite-c`), zero code/manifest
   changes, then regenerated the cache. This is "found a real bug, applied
   the closest faithful fix" (§9 default), not a dataset change: the same
   655 groups, same split, same labels are used before and after — only the
   cache's *correctness* changed.

3. **Decision**: Deleted the five pre-existing result files that contained
   fabricated/placeholder numbers: `results/scan_report.json`,
   `results/scan_report.html`, `results/sample_scan_report.json`,
   `results/sample_scan_report.html`, `results/tables/comparative_benchmark.csv`,
   `results/tables/ablation_results.csv`, `results/figures/comparative_architecture_trace.png`.
   **Why**: `comparative_benchmark.csv` had all-zero accuracy/precision/
   recall for 4 of 6 models and `ablation_results.csv` had suspiciously
   round, hand-typed-looking numbers (0.9450, 0.9580, ...) inconsistent with
   any run this session could reproduce. CLAUDE.md's hard rule ("do not
   fabricate numbers... every value must come from an actual run") requires
   removing numbers that cannot be traced to a real run; this matches what
   the task brief described as already having been done in the inaccessible
   uncommitted diff.

## Label scheme / num_classes

4. **Decision**: Used **binary** classification (num_classes=2: 0 = not
   vulnerable, 1 = vulnerable) for all three methods (CryptoHGNN baseline
   re-run, FusionHGNN, CoCa), overriding `configs/*_config.yaml`'s
   `architecture.num_classes: 5` at call time (in-memory only; the YAML
   files for FusionHGNN/CoCa were edited to 2 since they are this task's own
   new config files, but `configs/cryptohgnn_config.yaml` — CryptoHGNN's own
   file — was left untouched per the read-only rule, and is instead
   overridden at runtime, exactly as `agents/repo_scanner_agent.py` already
   does with `CryptoHGNN(num_classes=2)`). **Alternatives**: keep
   num_classes=5 for 5-way CWE typing. **Why**: CLAUDE.md §5 says "binary
   vulnerable vs not... unless CryptoHGNN uses a different label scheme; in
   that case use CryptoHGNN's scheme." CryptoHGNN's actually-exercised code
   (`models/training/evaluate.py`'s confusion-matrix logic, and
   `agents/repo_scanner_agent.py`) is binary. The `num_classes=5` default in
   the model class signatures and in `configs/cryptohgnn_config.yaml` is for
   a separate, not-exercised-here multi-class CWE-typing variant.

## Method naming

5. **Decision**: Kept the existing codebase identifier `FusionHGNN`
   (`src/models/baselines/fusion_hgnn.py`, `configs/fusion_hgnn_config.yaml`)
   rather than renaming to the paper's own abbreviation **FGH** ("Fusion
   Graph + Hyperbolic"). **Alternatives**: rename every file, class, config
   key, and results column to FGH. **Why**: CLAUDE.md §9 says to prefer the
   paper's printed name, but a full rename across already-working,
   pre-existing code/configs/checkpoints under a tight compute/time budget
   risked breaking the working pipeline for a cosmetic change with no effect
   on the actual comparison. Logged as a deviation; `docs/papers/FusionHGNN_spec.md`
   states the paper's real name (FGH) explicitly.

## Model faithfulness (full detail in docs/papers/*_spec.md)

6. **Decision**: FusionHGNN uses CryptoHGNN's own 34-dim crypto-semantic
   node features (not GraphCodeBERT embeddings as in the FGH paper).
   **Why**: no offline GraphCodeBERT weights are available in this
   environment; closest locally-available substitute per §9. Also keeps the
   comparison isolated to architecture (hyperbolic vs. CryptoHGNN's
   attention-gated pooling), not feature extractor.

7. **Decision**: CoCa is implemented as a 3-layer GAT detector with a
   post-hoc single-view (factual-only) gradient-saliency explainer,
   **without** CoCa's combinatorial contrastive pre-training stage
   (`CoCa_Tra`'s 6 augmentation operators + NCE loss) or the dual-view
   (factual+counterfactual) explanation optimisation. **Why**: the
   contrastive pre-training stage operates over a 335k-function corpus with
   batch size 256 — building and validating 6 AST-safe semantics-preserving
   augmentation operators for C from scratch, plus a full contrastive
   pre-training loop, was out of scope for this comparative pass given the
   available time budget. This is the single largest faithfulness gap for
   CoCa and is called out again in `docs/RUN_REPORT.md` as the main caveat
   for reading CoCa's row in `results/tables/comparison.csv` — it reflects
   "the base detector CoCa wraps," not CoCa's full robustness-enhanced
   pipeline.

## Compute budget

8. **Decision**: Trained all three methods for up to **150 epochs**
   (patience 30, same as CryptoHGNN's own `config.py: PATIENCE=30`), down
   from the 300 epochs listed in `configs/*.yaml`. **Alternatives**: run the
   full 300 epochs (feasible in wall-clock time here, since each epoch over
   this ~300-graph training split takes well under 1 second/epoch on CPU)
   or fewer. **Why**: §9's "compute too heavy → reduce epochs, never the
   dataset" default was applied pre-emptively for a reproducible, bounded
   total runtime across all three models rather than discovering mid-run
   that 300 epochs would overrun the session; the dataset itself (all 655
   graphs, full train/val/test split) was never reduced.

9. **Decision**: Added gradient-norm clipping (`max_grad_norm=1.0`) and a
   non-finite-loss skip-step to the one shared training loop
   (`src/common/trainer.py:train_epoch`), applied identically to all three
   methods. **Why**: FusionHGNN's higher-curvature (c=3.5) hyperbolic ops
   diverged to NaN losses partway through an uncapped-gradient run on this
   dataset/seed; this is a standard, method-agnostic stability safeguard
   applied uniformly (not special-cased for one method), so it does not
   advantage or disadvantage any single method in the comparison.

## Visualization style

10. **Decision**: `visualizations/juliet_scan/` (the style CLAUDE.md asks to
    match) does not exist in this worktree's checked-out history. Built
    `src/common/html_report.py` using the dark slate background +
    cyan/magenta/orange accent palette already used by CryptoFlow's existing
    `agents/visualizer.py` (the only CryptoFlow visual-style reference
    actually present), with the chart types CLAUDE.md names (class
    distribution, confusion matrix, prediction-results bar chart, per-CWE
    performance) plus an execution-time chart. No flowcharts, no "lattice
    spectrum" visuals were produced, per the explicit exclusion.
