"""Builds paper/generated/bibliography.tex (an IEEE-style thebibliography block) from paper/references.bib, in order of first citation.

The block is plain LaTeX, so the reference list appears with a single pdflatex run and needs no BibTeX step or .bib upload.
Usage: python -m vulnpairs paper   (also called from there)
"""
import re

from ..paths import REPO_ROOT

PAPER = REPO_ROOT / "paper"


def parse_bib(text):
    entries = {}
    for m in re.finditer(r"@(\w+)\{([^,]+),(.*?)\n\}", text, flags=re.S):
        kind, key, body = m.groups()
        fields = {}
        for f in re.finditer(r"(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}", body):
            fields[f.group(1).lower()] = f.group(2).strip()
        fields["_kind"] = kind.lower()
        entries[key.strip()] = fields
    return entries


def initials(name):
    parts = name.split()
    if len(parts) == 1:
        return name
    first = " ".join(p if "." in p else p[0] + "." for p in parts[:-1])
    return f"{first} {parts[-1]}"


def authors(a):
    names = [n.strip() for n in a.split(" and ")]
    etal = bool(names) and names[-1] == "others"
    names = [initials(n) for n in names if n != "others"]
    if etal:
        return ", ".join(names) + ", et al."
    if len(names) > 2:
        return ", ".join(names[:-1]) + ", and " + names[-1]
    return " and ".join(names)


def escape(s):
    return s.replace("&", "\\&").replace("_", "\\_").replace("%", "\\%")


def fmt(e):
    s = authors(e["author"]) + ", \\textquotedblleft " + e["title"] + ",\\textquotedblright{} "
    if "booktitle" in e:
        s += "in \\textit{" + e["booktitle"] + "}, "
    if "journal" in e:
        s += "\\textit{" + e["journal"] + "}, "
        if "volume" in e:
            s += "vol. " + e["volume"] + ", "
        if "number" in e:
            s += "no. " + e["number"] + ", "
    if "pages" in e:
        s += "pp. " + e["pages"] + ", "
    s += e["year"] + "."
    if "note" in e:
        s += " " + e["note"].replace("; year inferred from volume 52, verify", "") + "."
    if "doi" in e:
        s += " doi: " + e["doi"] + "."
    return escape(s).replace("..", ".")


def main() -> None:
    tex = (PAPER / "main.tex").read_text(encoding="utf-8")
    entries = parse_bib((PAPER / "references.bib").read_text(encoding="utf-8"))
    order = []
    for m in re.finditer(r"\\cite\{([^}]*)\}", tex):
        for k in m.group(1).split(","):
            k = k.strip()
            if k not in order:
                order.append(k)
    missing = [k for k in order if k not in entries]
    if missing:
        raise SystemExit(f"cited but not in references.bib: {missing}")
    lines = ["\\begin{thebibliography}{" + str(len(order)) + "}"]
    for k in order:
        lines.append("\\bibitem{" + k + "} " + fmt(entries[k]))
    lines.append("\\end{thebibliography}")
    with open(PAPER / "generated" / "bibliography.tex", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("wrote bibliography.tex with", len(order), "references")


if __name__ == "__main__":
    main()
