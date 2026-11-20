"""Builds poster/poster.png and poster/poster.pdf in the layout of the VESIT department poster.

Every number is read from results/ (JSON and CSV). Nothing is typed by hand.
Run from the repo root:  python poster/make_poster.py
"""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
ASSETS = Path(__file__).resolve().parent / "assets"
OUT = Path(__file__).resolve().parent

S = 2                      # output scale; layout coordinates below are for a 1652 x 2000 canvas
W, H = 1652, 2000
BLUE, GREY, PANEL, WHITE, BLACK = (81, 88, 254), (128, 128, 128), (234, 234, 234), (255, 255, 255), (0, 0, 0)
NAVY, STEEL = "#1f4e79", "#8c8c8c"

TITLE = "Leakage-Controlled Localisation of Vulnerable Lines in C/C++ Functions with Interpretable Features"
AUTHORS = "Prof. Shanta Sondur, Ved V Joshi, Jai Udasi, Sakshi Falak, Aayush Patil"
INSTITUTE = "Vivekanand Education Society’s Institute Of Technology"
DEPARTMENT = "Department Of Information Technology"

FAMILY_NAMES = {
    "memory": "Memory", "integer": "Integer", "resource": "Resource", "crypto": "Crypto",
    "input_validation": "Input val.", "concurrency": "Concurr.", "info_exposure": "Info exp.",
    "access_control": "Access ctl.", "robustness": "Robust.",
}


# ---------------------------------------------------------------- data
def load_data():
    main = json.loads((RES / "localize" / "results.json").read_text())
    extra = json.loads((RES / "localize" / "results_extra.json").read_text())
    pairs = list(csv.DictReader(open(RES / "tables" / "pairs_results.csv")))
    return main, extra, pairs


def point(fam, name):
    return fam["methods"][name]["point"]


def ci(fam, name, metric):
    return fam["methods"][name]["ci95"][metric]


# ---------------------------------------------------------------- drawing helpers
def font(size, bold=False):
    return ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", int(round(size * S)))


def rect(d, box, fill):
    x0, y0, x1, y1 = box
    d.rectangle([x0 * S, y0 * S, x1 * S, y1 * S], fill=fill)


def centred(d, text, cx, cy, f, fill):
    d.text((cx * S, cy * S), text, font=f, fill=fill, anchor="mm")


def wrap(text, f, width):
    lines, cur = [], ""
    for word in text.split():
        while f.getlength(word) > width * S:
            k = len(word)
            while k > 1 and f.getlength(word[:k]) > width * S:
                k -= 1
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(word[:k])
            word = word[k:]
        trial = word if not cur else cur + " " + word
        if f.getlength(trial) <= width * S or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def justified(d, line, x, y, width, f, fill, last):
    words = line.split()
    if last or len(words) < 2:
        d.text((x * S, y * S), line, font=f, fill=fill)
        return
    total = sum(f.getlength(w) for w in words)
    gap = (width * S - total) / (len(words) - 1)
    if gap > 2.4 * f.getlength(" "):
        d.text((x * S, y * S), line, font=f, fill=fill)
        return
    cx = x * S
    for w in words:
        d.text((cx, y * S), w, font=f, fill=fill)
        cx += f.getlength(w) + gap


def layout(paras, width, size, bullet_indent=22):
    f = font(size)
    out = []
    for text, bullet in paras:
        w = width - (bullet_indent if bullet else 0)
        out.append((wrap(text, f, w), bullet))
    return out


def text_height(paras, width, size, lead=1.30, pgap=0.40):
    lay = layout(paras, width, size)
    n = sum(len(lines) for lines, _ in lay)
    return n * size * lead + (len(lay) - 1) * size * pgap


def draw_paras(d, box, paras, max_size=26, min_size=12, lead=1.30, pgap=0.40, pad=(18, 14), fill=BLACK):
    x0, y0, x1, y1 = box
    width, height = (x1 - x0) - 2 * pad[0], (y1 - y0) - 2 * pad[1]
    size = max_size
    while size > min_size and text_height(paras, width, size, lead, pgap) > height:
        size -= 0.5
    f = font(size)
    lay = layout(paras, width, size)
    y = y0 + pad[1]
    for lines, bullet in lay:
        indent = 22 if bullet else 0
        for i, line in enumerate(lines):
            if bullet and i == 0:
                d.text(((x0 + pad[0] + 2) * S, y * S), "•", font=f, fill=fill)
            justified(d, line, x0 + pad[0] + indent, y, width - indent, f, fill, i == len(lines) - 1)
            y += size * lead
        y += size * pgap
    return size


def header_bar(d, box, label, size=50):
    rect(d, box, GREY)
    x0, y0, x1, y1 = box
    centred(d, label, (x0 + x1) / 2, (y0 + y1) / 2, font(size), WHITE)


# ---------------------------------------------------------------- figures
def fig_to_image(fig, w, h):
    fig.canvas.draw()
    img = Image.frombytes("RGBA", fig.canvas.get_width_height(), bytes(fig.canvas.buffer_rgba())).convert("RGB")
    plt.close(fig)
    return img.resize((int(w * S), int(h * S)), Image.LANCZOS)


def figure_hitk(main, w, h):
    fig, axes = plt.subplots(2, 2, figsize=(w / 100, h / 100), dpi=200, sharey=True)
    ks = [1, 3, 5, 10]
    for ax, key in zip(axes.flat, ["memory", "integer", "resource", "crypto"]):
        fam = main["families"][key]
        m = [point(fam, "full")[f"hit{k}"] for k in ks]
        lo = [ci(fam, "full", f"hit{k}")[0] for k in ks]
        hi = [ci(fam, "full", f"hit{k}")[1] for k in ks]
        r = [point(fam, "full")[f"random_hit{k}"] for k in ks]
        ax.fill_between(range(4), lo, hi, color=NAVY, alpha=0.2, lw=0)
        ax.plot(range(4), m, "-o", color=NAVY, ms=3, lw=1.4, label="model")
        ax.plot(range(4), r, "--s", color=STEEL, ms=3, lw=1.2, label="chance")
        ax.set_xticks(range(4), [str(k) for k in ks])
        ax.set_title(FAMILY_NAMES[key], fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.3)
    axes[0, 0].legend(fontsize=6.5, loc="upper left")
    for ax in axes[1]:
        ax.set_xlabel("k", fontsize=7)
    for ax in axes[:, 0]:
        ax.set_ylabel("hit@k", fontsize=7)
    fig.tight_layout(pad=0.4)
    return fig_to_image(fig, w, h)


def figure_families(main, extra, w, h):
    rows = []
    for src, keys in ((main, ["memory", "integer", "resource", "crypto"]),
                      (extra, ["input_validation", "concurrency", "info_exposure", "access_control", "robustness"])):
        for key in keys:
            fam = src["families"][key]
            lo, hi = ci(fam, "full", "hit1")
            rows.append((key, point(fam, "full")["hit1"], lo, hi, point(fam, "full")["random_hit1"], src is extra))
    beat = sum(1 for _, _, lo, _, ch, _ in rows if lo > ch)
    not_beat = [FAMILY_NAMES[r[0]] for r in rows if r[2] <= r[4]]
    fig, ax = plt.subplots(figsize=(w / 100, h / 100), dpi=200)
    xs = range(len(rows))
    cols = [NAVY if not ex else "#6f93b8" for *_, ex in rows]
    ax.bar(xs, [r[1] for r in rows], color=cols, width=0.62,
           yerr=[[r[1] - r[2] for r in rows], [r[3] - r[1] for r in rows]], capsize=2, error_kw={"lw": 0.8})
    ax.scatter(xs, [r[4] for r in rows], marker="_", s=150, color="#d62728", zorder=3, label="chance")
    ax.set_xticks(list(xs), [FAMILY_NAMES[r[0]] for r in rows], rotation=40, ha="right", fontsize=6.5)
    ax.set_ylabel("hit@1", fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_ylim(0, 0.31)
    ax.grid(axis="y", alpha=0.3)
    ax.axvline(3.5, color="k", lw=0.5, ls=":")
    ax.text(1.5, ax.get_ylim()[1] * 0.97, "planned", ha="center", va="top", fontsize=6.5)
    ax.text(6, ax.get_ylim()[1] * 0.97, "exploratory", ha="center", va="top", fontsize=6.5)
    ax.legend(fontsize=6.5, loc="upper right", bbox_to_anchor=(1, 0.9))
    fig.tight_layout(pad=0.5)
    return fig_to_image(fig, w, h), beat, len(rows), not_beat


# ---------------------------------------------------------------- method flow chart
def flow_chart(d, box):
    x0, y0, x1, y1 = box
    rect(d, box, WHITE)
    cx = (x0 + x1) / 2
    bw = (x1 - x0) - 40
    steps = [
        ("MegaVul release (C/C++ vulnerability data)", None, 40, GREY),
        ("1  Select", "functions of one CWE family, duplicates removed", 54, None),
        ("2  Label", "lines changed by the fix are the true lines", 54, None),
        ("3  Split", "5 folds of whole repositories, no project shared", 54, None),
        ("BRANCH", None, 98, None),
        ("5  Rank", "gradient boosting scores every candidate line", 54, None),
        ("6  Evaluate", "hit@k, MRR, IFA, P, R, F1 against exact chance", 54, None),
    ]
    gap = 15
    total = sum(s[2] for s in steps) + gap * (len(steps) - 1)
    y = y0 + ((y1 - y0) - total) / 2
    tops = []
    for title, sub, h, shade in steps:
        tops.append(y)
        yb = y + h
        if title == "BRANCH":
            half = (bw - 16) / 2
            for k, (t, s) in enumerate([("4a  Line features", "25 line counts, 8 check-aware counts and the same counts for neighbouring lines"),
                                         ("4b  Token score", "hashed tokens of the line, scored by an out-of-fold logistic regression")]):
                bx0 = x0 + 20 + k * (half + 16)
                d.rectangle([bx0 * S, y * S, (bx0 + half) * S, yb * S], outline=BLACK, width=2)
                centred(d, t, bx0 + half / 2, y + 17, font(15, True), BLACK)
                lines = wrap(s, font(13), half - 14)
                for i, ln in enumerate(lines):
                    centred(d, ln, bx0 + half / 2, y + 41 + i * 16, font(13), BLACK)
        else:
            fill = (232, 232, 232) if shade else WHITE
            d.rectangle([(x0 + 20) * S, y * S, (x0 + 20 + bw) * S, yb * S], outline=BLACK, width=2, fill=fill)
            if sub is None:
                centred(d, title, cx, y + h / 2, font(15), BLACK)
            else:
                centred(d, title, cx, y + 17, font(16, True), BLACK)
                centred(d, sub, cx, y + 39, font(14), BLACK)
        y = yb + gap
    for i in range(len(steps) - 1):
        ya, yb = tops[i] + steps[i][2], tops[i + 1]
        if steps[i + 1][0] == "BRANCH":
            half = (bw - 16) / 2
            for k in range(2):
                ax_ = x0 + 20 + k * (half + 16) + half / 2
                d.line([cx * S, ya * S, cx * S, (ya + 7) * S], fill=BLACK, width=2)
                d.line([ax_ * S, (ya + 7) * S, ax_ * S, yb * S], fill=BLACK, width=2)
                d.polygon([(ax_ * S, yb * S), ((ax_ - 4) * S, (yb - 7) * S), ((ax_ + 4) * S, (yb - 7) * S)], fill=BLACK)
            d.line([(x0 + 20 + half / 2) * S, (ya + 7) * S, (x0 + 20 + half + 16 + half / 2) * S, (ya + 7) * S], fill=BLACK, width=2)
        elif steps[i][0] == "BRANCH":
            half = (bw - 16) / 2
            for k in range(2):
                ax_ = x0 + 20 + k * (half + 16) + half / 2
                d.line([ax_ * S, ya * S, ax_ * S, (ya + 7) * S], fill=BLACK, width=2)
            d.line([(x0 + 20 + half / 2) * S, (ya + 7) * S, (x0 + 20 + half + 16 + half / 2) * S, (ya + 7) * S], fill=BLACK, width=2)
            d.line([cx * S, (ya + 7) * S, cx * S, yb * S], fill=BLACK, width=2)
            d.polygon([(cx * S, yb * S), ((cx - 4) * S, (yb - 7) * S), ((cx + 4) * S, (yb - 7) * S)], fill=BLACK)
        else:
            d.line([cx * S, ya * S, cx * S, yb * S], fill=BLACK, width=2)
            d.polygon([(cx * S, yb * S), ((cx - 4) * S, (yb - 7) * S), ((cx + 4) * S, (yb - 7) * S)], fill=BLACK)


# ---------------------------------------------------------------- poster
def build():
    main, extra, pairs = load_data()
    st = main["stats"]
    fam = main["families"]
    auc = {r["family"]: float(r["value"]) for r in pairs if r["model"] == "model" and r["metric"] == "auc"}
    int_f, mem_f = fam["integer"], fam["memory"]

    img = Image.new("RGB", (W * S, H * S), BLUE)
    d = ImageDraw.Draw(img)

    # header
    rect(d, (10, 10, 1632, 143), WHITE)
    img.paste(Image.open(ASSETS / "ves_logo.png").resize((int(274 * S * 0.97), int(100 * S * 0.97))), (20 * S, 22 * S))
    centred(d, INSTITUTE, 828, 48, font(41), BLACK)
    centred(d, DEPARTMENT, 828, 108, font(41), BLACK)
    img.paste(Image.open(ASSETS / "sdg9.jpg").resize((120 * S, 120 * S)), (1498 * S, 18 * S))

    # title and authors
    t_font = font(40, True)
    lines = wrap(TITLE, t_font, 1560)
    for i, ln in enumerate(lines):
        centred(d, ln, 826, 172 + i * 44, t_font, WHITE)
    centred(d, AUTHORS, 826, 172 + len(lines) * 44 + 4, font(22, True), WHITE)

    # section header bars (positions as in the department poster)
    header_bar(d, (33, 305, 528, 377), "Introduction")
    header_bar(d, (545, 305, 1134, 377), "Methodology")
    header_bar(d, (1156, 305, 1628, 377), "Features and Models", size=44)
    header_bar(d, (33, 987, 528, 1059), "Problem Statement")
    header_bar(d, (549, 987, 1139, 1059), "Results")
    header_bar(d, (1156, 987, 1630, 1059), "Applications")
    header_bar(d, (35, 1653, 531, 1712), "Dataset")
    header_bar(d, (1158, 1292, 1630, 1364), "References")

    # content panels
    panels = {
        "intro": (33, 392, 525, 962), "method": (549, 392, 1134, 962), "feat": (1156, 392, 1628, 962),
        "problem": (35, 1082, 527, 1632), "res1": (549, 1077, 1139, 1549), "res2": (553, 1574, 1139, 1970),
        "apps": (1158, 1078, 1628, 1269), "refs": (1160, 1378, 1628, 1970), "data": (37, 1734, 531, 1970),
    }
    for box in panels.values():
        rect(d, box, PANEL)

    mean_lines, mean_true = float(mem_f["mean_lines"]), float(mem_f["mean_true_lines"])

    draw_paras(d, panels["intro"], [
        ("Learned vulnerability detectors report high scores on random splits of public datasets, "
         "yet their accuracy collapses once projects, duplicates and patch size are controlled.", True),
        (f"A security fix is small. In MegaVul a fix touches about {mean_true:.2f} lines of a memory-bug function "
         f"that has {mean_lines:.1f} code lines on average.", True),
        ("A reviewer who is told “this function is vulnerable” still has to find those lines.", True),
        ("The proposed work ranks the lines of a known-vulnerable function so that the lines the fix changed "
         "are read first, with interpretable features, no neural network and a leakage-controlled evaluation.", True),
    ], max_size=25)

    flow_chart(d, (556, 400, 1127, 954))

    draw_paras(d, panels["feat"], [
        ("Line features: counts of security-relevant calls (allocation, free, copy, format, input, crypto), "
         "check-aware counts and the same counts for the neighbouring lines.", True),
        ("Token score: hashed tokens of each line, scored by an out-of-fold logistic regression.", True),
        ("Ranker: gradient boosting over every candidate line of the function.", True),
        ("Baselines: a hand-written rule score, the token score alone, hand-built features alone and the exact "
         "random ranking of the function.", True),
        ("Folds hold whole repositories, so no project appears on both sides of a split.", True),
    ], max_size=24)

    aucs = ", ".join(f"{FAMILY_NAMES[k].lower()} {auc[k]:.3f}" for k in ["memory", "integer", "resource", "crypto"])
    draw_paras(d, panels["problem"], [
        ("Function-level detection on vulnerable-versus-fixed pairs is near chance with interpretable features "
         f"(AUC: {aucs}).", True),
        ("The task here is narrower and useful to a code reviewer: for a function known to be vulnerable, "
         "rank its lines so the vulnerable ones come first.", True),
        ("Labels are the lines changed by the security fix.", True),
        ("Every method is scored on the same candidate lines against an exact chance level computed for each function.", True),
        ("Three sources of leakage are controlled: shared projects, duplicated functions and patch size.", True),
    ], max_size=25)

    res1 = figure_hitk(main, 576, 332)
    img.paste(res1, (556 * S, 1090 * S))
    draw_paras(d, (549, 1430, 1139, 1549), [
        (f"hit@k of the model against exact chance, with 95% project-cluster bootstrap intervals. "
         f"Integer bugs: hit@1 {point(int_f, 'full')['hit1']:.3f} against chance {point(int_f, 'full')['random_hit1']:.3f}; "
         f"memory bugs: {point(mem_f, 'full')['hit1']:.3f} against {point(mem_f, 'full')['random_hit1']:.3f}.", False),
    ], max_size=19, pad=(14, 6))

    res2, beat, total, not_beat = figure_families(main, extra, 570, 330)
    img.paste(res2, (561 * S, 1580 * S))
    draw_paras(d, (553, 1912, 1139, 1970), [
        (f"hit@1 for all {total} CWE families. The model's interval lies above chance in {beat} of {total}; "
         "in the others it is indistinguishable from chance.", False),
    ], max_size=17, pad=(14, 4))

    ifa_m = point(int_f, "full")["ifa"]
    ifa_r = point(int_f, "full")["random_ifa"]
    draw_paras(d, panels["apps"], [
        ("A reading order for code review of a function already known to be vulnerable.", True),
        (f"For integer bugs the clean lines read before the first bug fall from {ifa_r:.1f} (chance) to {ifa_m:.1f}.", True),
        (f"Not better than chance in {len(not_beat)} of {total} families" + (", including " + " and ".join(n.lower() for n in not_beat if n in ("Resource", "Crypto")) if any(n in ("Resource", "Crypto") for n in not_beat) else "") + ".", True),
    ], max_size=24, pad=(18, 10))

    draw_paras(d, panels["data"], [
        (f"MegaVul full release: {st['kept']:,} vulnerable C/C++ functions kept from {st['pairs']:,} patch pairs, "
         f"{st['changed']:,} with changed lines and {st['add_only']:,} whose fix only adds lines.", True),
        (f"Planned families: memory {int(fam['memory']['functions']):,}, integer {int(fam['integer']['functions']):,}, "
         f"resource {int(fam['resource']['functions']):,}, crypto {int(fam['crypto']['functions']):,} functions; "
         f"five more families explored.", True),
    ], max_size=22)

    draw_paras(d, panels["refs"], [
        ("Ni, C., Shen, L., Yang, X., Zhu, Y., & Wang, S. (2024). MegaVul: A C/C++ vulnerability dataset with "
         "comprehensive code representations. Proc. 21st Int. Conf. Mining Software Repositories (MSR). "
         "https://doi.org/10.1145/3643991.3644886", True),
        ("Fan, J., Li, Y., Wang, S., & Nguyen, T. N. (2020). A C/C++ code vulnerability dataset with code changes "
         "and CVE summaries. Proc. 17th Int. Conf. Mining Software Repositories (MSR), 508–512.", True),
        ("Ding, Y., et al. (2025). Vulnerability detection with code language models: How far are we? "
         "Proc. 47th IEEE/ACM Int. Conf. Software Engineering (ICSE). arXiv:2403.18624", True),
        ("Allamanis, M. (2019). The adverse effects of code duplication in machine learning models of code. "
         "arXiv:1812.06469.", True),
    ], max_size=21)

    img.save(OUT / "poster.png", dpi=(150, 150))
    img.save(OUT / "poster.pdf", resolution=150)
    print("written", OUT / "poster.png", img.size, "| beat chance:", beat, "of", total)


if __name__ == "__main__":
    build()
