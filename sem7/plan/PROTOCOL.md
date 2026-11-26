# Protocol (fixed before any model was trained)

Two parts: A. patch-pair detection (function level), B. line localisation. Part B was added after A showed chance-level detection; its design was fixed before the final runs and nothing was tuned on test folds.

## A. Patch-pair detection

**Question.** How much vulnerable-code signal remains when the size and project shortcuts are removed?

**Data.** Full MegaVul release: 17,975 vulnerable functions, each with the same function after the fix (`func_before` against `func`) and a Joern graph
for both sides. Selection: both graphs available; 3-5,000 nodes per side; duplicate vulnerable versions removed (whitespace-normalised hash); at least one
CWE tag in a family below. Result: 9,640 pairs.

**Families** (a pair can belong to several): memory 7,186 pairs, integer 1,214, resource exhaustion 1,221, cryptographic 260.

**Features.** Counts only: size, 33 node types, 21 edge types, operator groups, security-API roles (`catalogue.py`).

**Model.** One gradient-boosting model per family (300 trees, depth 3, learning rate 0.05, subsample 0.8), seeds 42-46, scores averaged over seeds.

**Evaluation.** Project-grouped 5-fold cross-validation; both members of a pair stay in one fold; threshold 0.5. Metrics: accuracy, precision, recall,
F1, AUC, and pair-ranking accuracy (share of pairs where the vulnerable version scores above its own fix). 95% intervals resample whole projects
(1,000 resamples, seed 0).

**Control.** Logistic regression on log(node count) alone, same folds.

**Not done:** no parameter was tuned on these results; no comparison with other published numbers.

---

## B. Line localisation

**Question.** Given a function known to be vulnerable, can the lines the fix changed be ranked above the other lines, better than chance?

**Data.** The functions of part A with a usable fix position: 9,422 functions (6,938 where the fix removes or rewrites lines, 2,484 where it only inserts code), 1,062-repository MegaVul release. Positions come from the unified diff (`diff_func`, `diff_line_info`); alignment to `func_before` was checked on 7,155 deleted lines (100%).

**Labels.** "changed": the lines the fix removed or rewrote. "add_only": for pure-insertion fixes, the line after the inserted block. The two groups are reported separately.

**Candidate lines.** Every code line of the function except blank, brace-only, comment-only and preprocessor lines (about 65 per function). The same candidates are used for every method and for the random baseline.

**Families.** Memory 7,010 functions, integer 1,200, resource exhaustion 1,195, cryptographic 249 (a function can belong to several).

**Features.** 25 hand-made counts per line (position, length, nesting depth, call roles alloc/free/copy/format/input/crypto, calls, index/dereference, arithmetic, comparison, logic, assignment, control keywords, literals, casts, sizeof, pointer declaration), 8 check-aware counts, counts of the previous and next line, and an out-of-fold score from a logistic regression on hashed line tokens (2^16 buckets, C = 0.5; the score is computed with a 3-way project split inside the training part).

**Model.** One model per family: HistGradientBoosting (200 iterations, learning rate 0.05, depth 4, balanced class weights, seed 42).

**Methods compared.** Exact random order (analytic expectation); catalogue rule; tokens only; counts only; full model without check features; full model without neighbours; full model.

**Evaluation.** Project-grouped 5-fold cross-validation (same folds as part A). Per function: hit@1/3/5/10, MRR, IFA (non-vulnerable lines above the first true line). Line level, when the top 5 lines of every function are flagged: precision, recall, F1, accuracy. 95% intervals resample whole repositories (1,000 resamples, seed 0). Accuracy is about 0.91 for every method including random, so it is reported but not used as evidence.

**Strata.** Fix type (changed vs add-only) and type of the true line (condition, call, assignment, other).

**Not done:** no tuning on test folds; no neural network; no comparison with published systems (different splits, candidate pools and labels make the numbers incomparable, and no head-to-head was run); only C/C++.

---

## C. Exploratory families (added 6 Nov 2026, before the run)

**Question.** Do the localisation results hold for CWE families outside the four of part A and B, and which families, if any, are localisable?

**Status.** Exploratory. The groups below were fixed from CWE availability in MegaVul (counts of usable pairs per CWE) before any model was run on them. All five are run and all five are reported, whatever the outcome. Nothing is dropped or merged afterwards.

| Group | CWE ids |
|---|---|
| input_validation | 20, 1284, 129, 22, 74, 77, 78, 79, 89, 134 |
| concurrency | 362, 367, 667, 364, 366, 413 |
| info_exposure | 200, 201, 203, 209, 212, 532 |
| access_control | 264, 284, 269, 287, 862, 863, 732, 276, 59, 254 |
| robustness (error handling and initialisation) | 617, 754, 252, 755, 665, 908, 909, 404, 459 |

**Method.** Identical to part B: same labels, candidates, features, model, folds rule, exact random baseline and repository-cluster bootstrap. Run with `python -m vulnpairs explore`; results go to `results/localize/results_extra.json`, so the four main families are not touched.

**Reading rule.** A family counts as localisable when the 95% interval of hit@1 lies above the exact random hit@1. With five additional families tested, one interval can miss by chance, so a single marginal family is reported as suggestive, not established. Families with few repositories are flagged, because the repository bootstrap is unreliable below about 20 repositories.
