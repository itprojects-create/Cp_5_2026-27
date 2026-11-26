# vulnpairs

Per-family study on the full MegaVul release (C/C++ functions with Joern code property graphs), with two parts:

1. **Patch pairs.** Each vulnerable function is paired with its own fixed version, and one model per CWE family is trained with project-grouped folds. Function-level detection stays near chance.
2. **Line localisation.** Given a vulnerable function, rank its lines so the lines the fix changed come first. Compared with an exact random baseline.

Families: memory, integer, resource exhaustion, cryptographic.

## At a glance
```
dataset/   MegaVul input data (not committed)
plan/      protocol: what is done and how, fixed before the runs
model/     code: features, patch-pair study, line localisation, report generation
results/   outputs: JSON, CSV tables, logs
paper/     manuscript (LaTeX) and generated tables
```

## Detail
```
model/vulnpairs/
  paths.py              all paths, Joern node and edge vocabularies
  __main__.py           command line
  features/             code-to-feature extraction
    catalogue.py          security-API catalogue (alloc, free, copy, format, input, crypto)
    roles.py              marks catalogued calls and their arguments in a graph
    graph_features.py     graph -> fixed-length count vector
    guard_features.py     fix-aware (check/guard) features
  pairs/                function-level patch-pair study
    build_pairs.py        MegaVul -> results/pairs/features.csv
    build_guard.py        -> results/pairs/guard_features.csv
    train_eval.py         per-family models, controls, intervals
    ablation.py           feature-group ablation
  localization/
    localize.py           line-level localisation, baselines, ablation, strata
  report/
    paper_tables.py       results -> paper/generated/*.tex
dataset/megavul/        megavul_simple.json, megavul_graph.zip (download separately; not committed)
results/
  pairs/  localize/     JSON results
  tables/               CSV tables
  logs/                 run logs
  archive/              superseded runs (deleted-lines-only labels), not used by the paper
plan/PROTOCOL.md        fixed protocol (patch pairs and localisation)
paper/                  manuscript (git-ignored until visibility is decided)
```

## Run
```
pip install -r requirements.txt
set PYTHONPATH=model          (PowerShell: $env:PYTHONPATH="model")
python -m vulnpairs build     # about 5 min
python -m vulnpairs train     # about 10 min, CPU only
python -m vulnpairs guard     # about 3 min
python -m vulnpairs ablate
python -m vulnpairs localize
python -m vulnpairs explore      # five exploratory CWE families (PROTOCOL.md part C) -> results/localize/results_extra.json
python -m vulnpairs paper     # writes paper/generated/*.tex
```
Settings are fixed in the headers of the modules. Nothing is tuned on the results.
