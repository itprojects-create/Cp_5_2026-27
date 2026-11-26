
# Task: Build FusionHGNN and CoCa pipelines, generate results, compare with CryptoHGNN

> Read this whole file before touching any code. Follow the phases in order.
> Do not ask questions mid-task. Where something is ambiguous, apply the default in §9 and log it in `docs/ASSUMPTIONS.md`.

---

## 1. Goal

CryptoHGNN already has a working pipeline in this repo (data loading → graph/feature construction → model → training/inference → results → visualizations).

Build **equivalent pipelines** for the two methods described in the papers in `COMPARISON_PAPER/`:

- **FusionHGNN**
- **CoCa**

Then, for each method: run it on the same dataset, produce HTML visualizations, evaluate it, and produce one CSV that compares all three methods (CryptoHGNN + the two new ones).

"Equivalent" means: same dataset, same labeling, same train/val/test split, same seeds, same I/O conventions, same code layout as CryptoHGNN. Only the method-specific parts (graph construction, model, training objective) come from the papers.

---

## 2. Inputs

| What                     | Path                                       | Note                                                                                   |
| ------------------------ | ------------------------------------------ | -------------------------------------------------------------------------------------- |
| Papers                   | `COMPARISON_PAPER/*.pdf`                 | Identify each method by reading the PDF. Use the method names given in the paper.      |
| Dataset                  | `datasets/juliet-test-suite-c/testcases` | Task text had`juliet-test-suitte-c`. Use whichever spelling actually exists on disk. |
| Reference implementation | the existing CryptoHGNN code               | Locate it in Phase 0. This is the template.                                            |
| Reference visual style   | `visualizations/juliet_scan`             | CryptoHGNN's HTML output. Match its look and structure.                                |

---

## 3. Hard rules

**DO**

- Reuse CryptoHGNN's data loader, label extraction, split logic, seeds, config style, logging style, and CLI conventions. Import them. Do not copy-paste-modify them.
- Put shared helpers (metrics, timing, memory, HTML rendering) in a common module used by all three methods.
- Make every run reproducible: fixed seed, saved config, saved split indices.
- Keep each new method in its own folder, mirroring CryptoHGNN's structure.
- If the paper's method cannot be reproduced exactly (missing detail, needs a resource we don't have, incompatible with C/Juliet), implement the closest faithful version and record the deviation (see §4, Phase 1).

**DO NOT**

- Do not modify CryptoHGNN code, outputs, or existing results. Read-only.
- Do not change the dataset, relabel it, or use a different split for the new methods.
- Do not fabricate numbers. Every value in a table or figure must come from an actual run.
- Do not generate flowcharts.
- Do not generate "representation graph in a lattice spectrum" visualizations.
- Do not leave stubs, `TODO`s, `pass` bodies, or placeholder metrics in delivered code.
- Do not stop to ask for confirmation between phases.

---

## 4. Workflow

### Phase 0 — Discovery (read-only)

1. List the repo tree and find the CryptoHGNN pipeline entry point, config, data loader, model, trainer, evaluator, and visualization code.
2. Find how `visualizations/juliet_scan` is produced.
3. Write `docs/CRYPTOHGNN_PIPELINE_MAP.md` containing:
   - the pipeline stages in order, with file and function for each
   - the exact inputs and outputs of each stage (types, shapes, file formats)
   - how labels are derived from Juliet (e.g. good vs bad functions, CWE mapping)
   - split method, seed, and where the split is stored
   - how to run it (command)
4. If you cannot find a CryptoHGNN pipeline at all, **stop and report this**. This is the only allowed stop.

### Phase 1 — Paper extraction

For each PDF in `COMPARISON_PAPER/`, write `docs/papers/<method>_spec.md` with:

- Method name, one-paragraph summary
- Input representation (what graph / code form it consumes, node and edge types, features)
- Model architecture (layers, dimensions, fusion or contrastive components, loss)
- Training setup (optimizer, lr, epochs, batch size, augmentations, hyperparameters stated in the paper)
- Anything that is **not specified** in the paper
- **Faithfulness table**: component | paper says | what we implement | reason for deviation (if any)

### Phase 2 — Build pipelines

For each paper, create a pipeline that follows the stage order from `docs/CRYPTOHGNN_PIPELINE_MAP.md`:

1. Load Juliet testcases using the CryptoHGNN loader.
2. Build the method's input representation from the C source, as described in the paper. Cache intermediate artifacts the same way CryptoHGNN does.
3. Build the model.
4. Train using the same split and seed.
5. Run inference on the test split and save raw predictions (per sample: id, true label, predicted label, score).

Expose one entry point per method with the same CLI style as CryptoHGNN, for example:

```
python -m <package>.<method>.run --config configs/<method>.yaml
```

Add one top-level runner that executes all methods in sequence:

```python
def execution(params):
    papers = sorted(glob("COMPARISON_PAPER/*.pdf"))
    pipelines = [create_pipeline(p) for p in papers]
    results = [generate_results(pl, p) for pl, p in zip(pipelines, papers)]
    evaluate(results)
```

### Phase 3 — Results and visualizations

For **each** new method, generate HTML visualizations. See §6 for the spec.

### Phase 4 — Evaluation

Evaluate all three methods (CryptoHGNN included as the baseline row; reuse its existing predictions if saved, otherwise re-run it without changing its code). See §5 for metrics and §7 for output files.

### Phase 5 — Verify and report

Run every item in the §8 checklist. Fix failures. Then write `docs/RUN_REPORT.md` with: commands run, runtime, final comparison table, deviations from the papers, and known limitations.

---

## 5. Evaluation spec

Compute on the **test split only**, binary vulnerable (positive) vs not vulnerable (negative), unless CryptoHGNN uses a different label scheme. In that case use CryptoHGNN's scheme.

**Main metrics**

| Metric    | Formula                 |
| --------- | ----------------------- |
| accuracy  | (TP+TN) / (TP+TN+FP+FN) |
| precision | TP / (TP+FP)            |
| recall    | TP / (TP+FN)            |
| f1_score  | 2·P·R / (P+R)         |
| fp_rate   | FP / (FP+TN)            |
| fn_rate   | FN / (FN+TP)            |

Return 0.0 (not NaN) when a denominator is 0, and log a warning.

**Sub metrics**

| Metric         | How to measure                                                                                                                                                                                                                 |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| execution_time | Wall-clock with`time.perf_counter()`. Record `train_time_s` and `inference_time_s` separately, plus `total_time_s`. Exclude one-off dataset parsing only if CryptoHGNN also excludes it. State the rule in the report. |
| memory_usage   | Peak RSS in MB (`psutil` or `resource`). If a GPU is used, also record `torch.cuda.max_memory_allocated()` in MB.                                                                                                        |

Measure all three methods with the same code and the same hardware.

---

## 6. Visualization spec

- Scope: for each paper, one set of visualizations.
- Output directory: `results/figures/`
- Format: standalone `.html` files, naming `results/figures/<method>_<chart>.html`
- Style: match CryptoHGNN's `visualizations/juliet_scan` (same library, layout, color palette, fonts, titles, and axis conventions). Study that output first.
- Content: the same chart types CryptoHGNN's scan produces (for example class distribution, prediction results, confusion matrix, per-CWE performance, if present there). Do not invent a new visual language.
- Exclusions: no flowcharts. No "representation graph in a lattice spectrum".
- Each HTML file must open offline in a browser without errors. Inline or vendor any JS it needs if CryptoHGNN's does.

---

## 7. Output tree

```
COMPARISON_PAPER/                 # input, unchanged
docs/
  CRYPTOHGNN_PIPELINE_MAP.md
  ASSUMPTIONS.md
  RUN_REPORT.md
  papers/<method>_spec.md
src/ (or existing package)/
  <fusionhgnn>/                   # mirrors CryptoHGNN layout
  <coca>/
  common/                         # shared metrics, timing, memory, html rendering
configs/<method>.yaml
results/
  predictions/<method>_test_predictions.csv
  figures/<method>_*.html
  tables/
    <method>_metrics.csv          # one row per method
    comparison.csv                # all three methods, one row each
```

`results/tables/comparison.csv` columns, in this order:

```
model, accuracy, precision, recall, f1_score, fp_rate, fn_rate, train_time_s, inference_time_s, total_time_s, peak_memory_mb
```

The earlier draft path `results/tables/_.csv` was treated as a typo for the above.

---

## 8. Acceptance checklist (all must pass before you finish)

- [ ] CryptoHGNN code and results are unchanged (`git diff` shows no edits to them).
- [ ] One pipeline folder exists per paper in `COMPARISON_PAPER/`, mirroring CryptoHGNN's layout.
- [ ] Each pipeline runs end to end from a single command on the Juliet dataset.
- [ ] All three methods use the identical split and seed.
- [ ] `results/figures/` has HTML for each new method, matching the `juliet_scan` style, with no flowcharts or lattice-spectrum graphs.
- [ ] `results/tables/comparison.csv` has exactly 3 rows with the columns in §7, all values from real runs.
- [ ] Metrics are recomputed from the saved prediction files and match the CSV.
- [ ] Docs in `docs/` are written and the faithfulness tables are filled in.
- [ ] No stubs, TODOs, or placeholder values remain in delivered code.
- [ ] A fresh run of the top-level runner reproduces the same numbers (same seed).

---

## 9. Ambiguity policy

- Do not ask. Choose the most reasonable default, keep it consistent, and log it in `docs/ASSUMPTIONS.md` as: decision | alternatives | why.
- Defaults:
  - Paper hyperparameter missing → use the value from CryptoHGNN's config if equivalent, otherwise a standard value, and log it.
  - Paper's method needs something we cannot get offline (e.g. a pretrained model not in the repo) → use the closest locally available substitute, log it, and mark the row in the faithfulness table.
  - Compute is too heavy to finish → reduce epochs or batch size, never the dataset, and log it.
  - Method names differ from "FusionHGNN" / "CoCa" in the PDFs → use the names printed in the papers.
- Only stop for the case in Phase 0 step 4.

---

## 10. Final message to the user

Keep it short: what was built, the exact command to rerun everything, the comparison table, and any deviation that could affect how the numbers should be read.
