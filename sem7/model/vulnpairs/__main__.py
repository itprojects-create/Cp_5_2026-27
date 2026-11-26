"""Command line: python -m vulnpairs build | train | guard | ablate | localize | paper | docx | all"""
import argparse

from .pairs import ablation, build_guard, build_pairs, train_eval
from .localization import localize
from .report import docx_paper, paper_tables


def main() -> None:
    ap = argparse.ArgumentParser(prog="vulnpairs")
    ap.add_argument("step", choices=["build", "train", "guard", "ablate", "localize", "explore", "paper", "docx", "all"],
                    help="explore: localisation on the exploratory CWE families (results_extra.json);build: pair feature table; train: baseline models and tables; guard: fix-aware feature table; "
                         "ablate: feature-group ablation with guard features; localize: line-level localisation; paper: LaTeX tables and numbers; docx: Word paper from the ICEET template; "
                         "all: every step in order")
    args = ap.parse_args()
    if args.step in ("build", "all"):
        build_pairs.main()
    if args.step in ("train", "all"):
        train_eval.main()
    if args.step in ("guard", "all"):
        build_guard.main()
    if args.step in ("ablate", "all"):
        ablation.main()
    if args.step in ("localize", "all"):
        localize.main()
    if args.step == "explore":
        localize.main(extra=True)
    if args.step in ("paper", "all"):
        paper_tables.main()
    if args.step in ("docx", "all"):
        docx_paper.main()


if __name__ == "__main__":
    main()
