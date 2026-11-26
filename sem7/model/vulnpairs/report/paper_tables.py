"""Writes the LaTeX tables and number macros of the paper from the result files, so no number in the paper is typed by hand.

Reads results/localize/results.json, results/pairs/ablation.json and results/pairs/results.json.
Writes paper/generated/numbers.tex (\\newcommand macros) and paper/generated/table_*.tex.
Usage: python -m vulnpairs paper
"""
import json

from ..paths import REPO_ROOT, RESULTS

OUT = REPO_ROOT / "paper" / "generated"
FAM = {"memory": "Mem", "integer": "Int", "resource": "Res", "crypto": "Cry"}
FAM_NAME = {"memory": "Memory", "integer": "Integer", "resource": "Resource", "crypto": "Crypto"}
METH = {"full": "Full", "random": "Random", "rule": "Rule", "token_lr": "Token", "hand_hgb": "Hand", "full_no_extra": "NoExtra",
        "full_no_context": "NoContext"}
MET = {"hit1": "HitOne", "hit3": "HitThree", "hit5": "HitFive", "hit10": "HitTen", "mrr": "Mrr", "ifa": "Ifa", "precision": "Prec",
       "recall": "Rec", "f1": "Fone", "accuracy": "Acc"}
TYPE = {"condition": "Cond", "call": "Call", "assignment_or_declaration": "Assign", "other": "Other"}
STRATUM = {"changed": "Changed", "add_only": "AddOnly"}


FAMX = {"input_validation": "Inp", "concurrency": "Con", "info_exposure": "Inf", "access_control": "Ctl", "robustness": "Rob"}
FAMX_NAME = {"input_validation": "Input validation", "concurrency": "Concurrency", "info_exposure": "Info exposure",
             "access_control": "Access control", "robustness": "Robustness"}


def above(e):
    """Part C reading rule: the lower end of the 95% interval of hit@1 lies above the exact chance level."""
    full = e["methods"]["full"]
    return full["ci95"]["hit1"][0] > full["point"]["random_hit1"]


def f3(x):
    return f"{x:.3f}"


def f1(x):
    return f"{x:.1f}"


def figure(loc) -> None:
    """hit@k of the full model against exact chance, one panel per family (paper/generated/fig_hitk.pdf)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ks = [1, 3, 5, 10]
    fig, axes = plt.subplots(1, 4, figsize=(7.0, 1.6), sharey=True)
    for ax, (fam, e) in zip(axes, loc["families"].items()):
        p = e["methods"]["full"]["point"]
        ci = e["methods"]["full"]["ci95"]
        mean = [p[f"hit{k}"] for k in ks]
        lo = [ci[f"hit{k}"][0] for k in ks]
        hi = [ci[f"hit{k}"][1] for k in ks]
        ax.plot(ks, mean, "o-", color="#1f4e79", label="model")
        ax.fill_between(ks, lo, hi, color="#1f4e79", alpha=0.2, linewidth=0)
        ax.plot(ks, [p[f"random_hit{k}"] for k in ks], "s--", color="#999999", label="chance")
        ax.set_title(FAM_NAME[fam], fontsize=8)
        ax.set_xticks(ks)
        ax.set_xlabel("k", fontsize=7)
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("hit@k", fontsize=7)
    axes[0].legend(fontsize=6, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "fig_hitk.pdf")
    plt.close(fig)

    # Single-column version (2 x 2 panels, 3.4 in wide) for the Word template.
    fig, axes = plt.subplots(2, 2, figsize=(3.4, 3.0), sharey=True)
    for ax, (fam, e) in zip(axes.ravel(), loc["families"].items()):
        p = e["methods"]["full"]["point"]
        ci = e["methods"]["full"]["ci95"]
        ax.plot(ks, [p[f"hit{k}"] for k in ks], "o-", color="#1f4e79", markersize=3, label="model")
        ax.fill_between(ks, [ci[f"hit{k}"][0] for k in ks], [ci[f"hit{k}"][1] for k in ks], color="#1f4e79", alpha=0.2, linewidth=0)
        ax.plot(ks, [p[f"random_hit{k}"] for k in ks], "s--", color="#999999", markersize=3, label="chance")
        ax.set_title(FAM_NAME[fam], fontsize=8)
        ax.set_xticks(ks)
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.3)
    for ax in axes[1]:
        ax.set_xlabel("k", fontsize=7)
    for ax in axes[:, 0]:
        ax.set_ylabel("hit@k", fontsize=7)
    axes[0, 0].legend(fontsize=6, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "fig_hitk_col.png", dpi=300)
    plt.close(fig)


def method_figure() -> None:
    """Pipeline of the proposed method, drawn in the plain black-and-white style of a journal figure
    (paper/generated/fig_method_col.pdf for LaTeX, fig_method_col.png for the Word template, one text column wide).
    The text holds only design constants of the method, no result numbers."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, Rectangle

    plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Liberation Serif", "Nimbus Roman", "DejaVu Serif"],
                         "pdf.fonttype": 42, "mathtext.fontset": "stix"})
    W, pad, gap = 3.4, 0.02, 0.11
    hd, h1, hb = 0.25, 0.33, 0.58
    rows = [hd, h1, h1, h1, hb, h1, h1]
    H = sum(rows) + gap * (len(rows) - 1) + 2 * pad
    tops, y = [], H - pad
    for h in rows:
        tops.append(y)
        y -= h + gap
    fig, ax = plt.subplots(figsize=(W, H))
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    cx, wide, half = W / 2, 2.7, 1.4
    cl, cr = 0.95, 2.45  # centres of the two parallel feature boxes

    def box(c, row, w, title, desc="", fc="white"):
        top, h = tops[row], rows[row]
        ax.add_patch(Rectangle((c - w / 2, top - h), w, h, fc=fc, ec="black", lw=0.6))
        if not desc:
            ax.text(c, top - h / 2, title, ha="center", va="center", fontsize=7.4)
        elif h > 0.4:  # three-line description
            ax.text(c, top - 0.085, title, ha="center", va="center", fontsize=7.4, fontweight="bold")
            ax.text(c, top - 0.165, desc, ha="center", va="top", fontsize=6.9, linespacing=1.15)
        else:
            ax.text(c, top - 0.09, title, ha="center", va="center", fontsize=7.4, fontweight="bold")
            ax.text(c, top - 0.225, desc, ha="center", va="center", fontsize=6.9)

    def arrow(x, row_from, row_to):
        ax.add_patch(FancyArrowPatch((x, tops[row_from] - rows[row_from]), (x, tops[row_to]), arrowstyle="-|>", mutation_scale=6.5,
                                     color="black", lw=0.6, shrinkA=0, shrinkB=0))

    box(cx, 0, 1.9, "MegaVul release (C/C++ vulnerability data)", fc="#eeeeee")
    box(cx, 1, wide, "1  Select", "functions of one CWE family, duplicates removed")
    box(cx, 2, wide, "2  Label", "lines changed by the fix are the true lines")
    box(cx, 3, wide, "3  Split", "5 folds of whole repositories, no project shared")
    box(cl, 4, half, "4a  Line features", "25 line counts, 8 check-aware\ncounts, and the same counts\nfor the neighbouring lines")
    box(cr, 4, half, "4b  Token score", "hashed tokens of the line,\nscored by an out-of-fold\nlogistic regression")
    box(cx, 5, wide, "5  Rank", "gradient boosting scores every candidate line")
    box(cx, 6, wide, "6  Evaluate", "hit@k, MRR, IFA, P, R, F1 against exact chance")
    arrow(cx, 0, 1)
    arrow(cx, 1, 2)
    arrow(cx, 2, 3)
    arrow(cl, 3, 4)
    arrow(cr, 3, 4)
    arrow(cl, 4, 5)
    arrow(cr, 4, 5)
    arrow(cx, 5, 6)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(OUT / "fig_method_col.pdf")
    fig.savefig(OUT / "fig_method_col.png", dpi=300)
    plt.close(fig)


def put(name, text):
    """Writes a generated file with plain LF line endings (a CRLF file can confuse some TeX setups)."""
    with open(OUT / name, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def tabular(spec, head, rows):
    """A complete tabular environment, so main.tex never has to \\input rows from inside a tabular."""
    lines = ["\\begin{tabular}{" + spec + "}", "\\toprule"] + head + ["\\midrule"] + rows + ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    loc = json.load(open(RESULTS.parent / "localize" / "results.json", encoding="utf-8"))
    abl = json.load(open(RESULTS / "ablation.json", encoding="utf-8"))
    pair = json.load(open(RESULTS / "results.json", encoding="utf-8"))
    mac = []

    def add(name, val):
        mac.append(f"\\newcommand{{\\{name}}}{{{val}}}")

    st = loc["stats"]
    add("numFunctionsTotal", f"{st['kept']:,}".replace(",", "{,}"))
    add("numChangedTotal", f"{st['changed']:,}".replace(",", "{,}"))
    add("numAddOnlyTotal", f"{st['add_only']:,}".replace(",", "{,}"))
    for fam, e in loc["families"].items():
        F = FAM[fam]
        add(f"num{F}Funcs", f"{e['functions']:,}".replace(",", "{,}"))
        add(f"num{F}Repos", str(e["repos"]))
        add(f"num{F}Lines", f1(e["mean_lines"]))
        add(f"num{F}TrueLines", f"{e['mean_true_lines']:.2f}")
        for s, c in e["strata_counts"].items():
            add(f"num{F}{STRATUM[s]}", f"{c:,}".replace(",", "{,}"))
        for m, v in e["methods"].items():
            for k, x in v["point"].items():
                if k.startswith("random_"):
                    if m == "full":
                        add(f"num{F}Random{MET[k[7:]]}", f1(x) if k == "random_ifa" else f3(x))
                    continue
                add(f"num{F}{METH[m]}{MET[k]}", f1(x) if k == "ifa" else f3(x))
            for k, (lo, hi) in v["ci95"].items():
                if k in MET and not k.startswith("random_"):
                    add(f"num{F}{METH[m]}{MET[k]}Lo", f1(lo) if k == "ifa" else f3(lo))
                    add(f"num{F}{METH[m]}{MET[k]}Hi", f1(hi) if k == "ifa" else f3(hi))
        for s, v in e["strata"].items():
            for k in ("hit1", "hit5", "hit10"):
                add(f"num{F}{STRATUM[s]}{MET[k]}", f3(v["full"][k]))
                add(f"num{F}{STRATUM[s]}Random{MET[k]}", f3(v["full"]["random_" + k]))
        for t, v in e["by_line_type"].items():
            add(f"num{F}Type{TYPE[t]}N", str(v["functions"]))
            for k in ("hit1", "hit5"):
                add(f"num{F}Type{TYPE[t]}{MET[k]}", f3(v[k]))
                add(f"num{F}Type{TYPE[t]}Random{MET[k]}", f3(v["random_" + k]))
    for fam, e in abl["families"].items():
        F = FAM[fam]
        add(f"num{F}PairCount", f"{e['pairs']:,}".replace(",", "{,}"))
        for s, name in (("size_control", "Size"), ("original", "Orig"), ("only_guard", "Guard"), ("all", "All")):
            p = e["sets"][s]["point"]
            lo, hi = e["sets"][s]["ci95"]["auc"]
            add(f"num{F}Pair{name}Auc", f3(p["auc"]))
            add(f"num{F}Pair{name}AucLo", f3(lo))
            add(f"num{F}Pair{name}AucHi", f3(hi))
            add(f"num{F}Pair{name}Fone", f3(p["f1"]))
            add(f"num{F}Pair{name}Acc", f3(p["accuracy"]))
            add(f"num{F}Pair{name}Prec", f3(p["precision"]))
            add(f"num{F}Pair{name}Rec", f3(p["recall"]))
            add(f"num{F}Pair{name}Rank", f3(p["pair_rank"]))
    for fam, e in loc["families"].items():
        pt = e["methods"]["full"]["point"]
        add(f"num{FAM[fam]}Lift", f"{pt['hit1'] / pt['random_hit1']:.1f}")
    for fam, e in pair["families"].items():
        add(f"num{FAM[fam]}SizeRank", f3(e["point"]["size_only"]["pair_rank"]))
    extra_path = RESULTS.parent / "localize" / "results_extra.json"
    ext = json.load(open(extra_path, encoding="utf-8")) if extra_path.exists() else None
    main_above = sum(1 for e in loc["families"].values() if above(e))
    extra_above = sum(1 for e in ext["families"].values() if above(e)) if ext else 0
    add("numMainFamilies", str(len(loc["families"])))
    add("numMainAbove", str(main_above))
    add("numAllFamilies", str(len(loc["families"]) + (len(ext["families"]) if ext else 0)))
    add("numAllAbove", str(main_above + extra_above))
    if ext:
        add("numExtraFamilies", str(len(ext["families"])))
        add("numExtraAbove", str(sum(1 for e in ext["families"].values() if above(e))))
        for fam, e in ext["families"].items():
            X = FAMX[fam]
            full = e["methods"]["full"]
            pt, ci = full["point"], full["ci95"]
            add(f"num{X}Funcs", f"{e['functions']:,}".replace(",", "{,}"))
            add(f"num{X}Repos", str(e["repos"]))
            add(f"num{X}FullHitOne", f3(pt["hit1"]))
            add(f"num{X}FullHitOneLo", f3(ci["hit1"][0]))
            add(f"num{X}FullHitOneHi", f3(ci["hit1"][1]))
            add(f"num{X}RandomHitOne", f3(pt["random_hit1"]))
            add(f"num{X}FullHitTen", f3(pt["hit10"]))
            add(f"num{X}RandomHitTen", f3(pt["random_hit10"]))
            add(f"num{X}FullIfa", f1(pt["ifa"]))
            add(f"num{X}RandomIfa", f1(pt["random_ifa"]))
            add(f"num{X}FullFone", f3(pt["f1"]))
            add(f"num{X}Lift", f"{pt['hit1'] / pt['random_hit1']:.1f}")
    put("numbers.tex", "\n".join(mac) + "\n")

    # Table: dataset
    rows = []
    for fam, e in loc["families"].items():
        rows.append(f"{FAM_NAME[fam]} & {e['functions']:,} & {e['strata_counts']['changed']:,} & {e['strata_counts']['add_only']:,} & {e['repos']} & "
                    f"{e['mean_lines']:.1f} & {e['mean_true_lines']:.2f} \\\\".replace(",", "{,}"))
    put("table_data.tex", tabular("lrrrrrr", ["Family & Funcs & Changed & Add-only & Repos & Lines & True \\\\"], rows))

    # Table: main results (random, rule, ours) per family
    rows = []
    for fam, e in loc["families"].items():
        for lab, m in (("Random", None), ("Rule", "rule"), ("Proposed", "full")):
            p = e["methods"]["full"]["point"] if m is None else e["methods"][m]["point"]
            g = (lambda k: p["random_" + k]) if m is None else (lambda k: p[k])
            cells = [f3(g("hit1")), f3(g("hit5")), f3(g("hit10")), f3(g("mrr")), f1(g("ifa"))]
            cells += ["--", "--", "--"] if m is None else [f3(p["precision"]), f3(p["recall"]), f3(p["f1"])]
            first = f"\\multirow{{3}}{{*}}{{{FAM_NAME[fam]}}}" if lab == "Random" else ""
            rows.append(f"{first} & {lab} & " + " & ".join(cells) + " \\\\")
        rows.append("\\midrule" if fam != "crypto" else "")
    put("table_main.tex", tabular("llrrrrrrrr", ["Family & Method & hit@1 & hit@5 & hit@10 & MRR & IFA & P & R & F1 \\\\"],
                                  [r for r in rows if r]))

    # Table: ablation (hit@1 / hit@10 per family)
    rows = []
    for m, lab in (("random", "Random"), ("rule", "Catalogue rule"), ("token_lr", "Tokens only"), ("hand_hgb", "Counts only"),
                   ("full_no_extra", "Full, no check features"), ("full_no_context", "Full, no neighbours"), ("full", "Full")):
        cells = []
        for fam, e in loc["families"].items():
            p = e["methods"]["full"]["point"] if m == "random" else e["methods"][m]["point"]
            g = (lambda k: p["random_" + k]) if m == "random" else (lambda k: p[k])
            cells += [f3(g("hit1")), f3(g("hit10"))]
        rows.append(f"{lab} & " + " & ".join(cells) + " \\\\")
    put("table_ablation.tex", tabular("lrrrrrrrr", [
        " & \\multicolumn{2}{c}{Memory} & \\multicolumn{2}{c}{Integer} & \\multicolumn{2}{c}{Resource} & \\multicolumn{2}{c}{Crypto} \\\\",
        "Method & @1 & @10 & @1 & @10 & @1 & @10 & @1 & @10 \\\\"], rows))

    # Table: strata and first-label type (hit@1, vs random in brackets) for memory and integer
    rows = []
    for fam in ("memory", "integer"):
        e = loc["families"][fam]
        for s, v in e["strata"].items():
            q = v["full"]
            lab = "fix changes code" if s == "changed" else "fix only adds code"
            rows.append(f"{FAM_NAME[fam]} & {lab} & {e['strata_counts'][s]:,} & {f3(q['hit1'])} ({f3(q['random_hit1'])}) & "
                        f"{f3(q['hit5'])} ({f3(q['random_hit5'])}) \\\\".replace(",", "{,}"))
        for t in ("condition", "call", "assignment_or_declaration", "other"):
            v = e["by_line_type"].get(t)
            if v:
                lab = {"condition": "label is a condition", "call": "label is a call", "assignment_or_declaration": "label is an assignment",
                       "other": "label is other"}[t]
                rows.append(f"{FAM_NAME[fam]} & {lab} & {v['functions']:,} & {f3(v['hit1'])} ({f3(v['random_hit1'])}) & "
                            f"{f3(v['hit5'])} ({f3(v['random_hit5'])}) \\\\".replace(",", "{,}"))
        rows.append("\\midrule" if fam == "memory" else "")
    put("table_strata.tex", tabular("llrrr", ["Family & Subset & Funcs & hit@1 & hit@5 \\\\"], [r for r in rows if r]))

    # Table: function-level pair detection (negative result)
    rows = []
    for fam, e in abl["families"].items():
        s = e["sets"]
        cells = []
        for key in ("size_control", "original", "only_guard", "all"):
            cells.append(f3(s[key]["point"]["auc"]))
        a = s["all"]["point"]
        rows.append(f"{FAM_NAME[fam]} & {e['pairs']:,} & " + " & ".join(cells) + f" & {f3(a['f1'])} & {f3(a['accuracy'])} \\\\".replace(",", "{,}"))
    put("table_pairs.tex", tabular("lrrrrrrr", ["Family & Pairs & Size & Orig. & Check & All & F1 & Acc \\\\"], rows))
    if ext:
        # Table: exploratory families (all five, whatever the outcome)
        rows = []
        for fam, e in ext["families"].items():
            full = e["methods"]["full"]
            p, c = full["point"], full["ci95"]["hit1"]
            rows.append(f"{FAMX_NAME[fam]} & {e['functions']:,} & {e['repos']} & {f3(p['hit1'])} & {f3(c[0])}--{f3(c[1])} & {f3(p['random_hit1'])} & "
                        f"{f3(p['hit10'])} & {f3(p['random_hit10'])} \\\\".replace(",", "{,}"))
        put("table_extra.tex", tabular("lrrrrrrr", ["Family & Funcs & Repos & hit@1 & 95\\% CI & Rand. & hit@10 & Rand. \\\\"], rows))
    figure(loc)
    method_figure()
    from . import bibliography
    bibliography.main()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
