"""Builds paper/ICEET-2026-paper.docx from the official ICEET Word template, using the template's own styles.

Source of truth is the same as for the LaTeX paper: paper/main.tex (text), paper/generated/*.tex (numbers and tables),
paper/generated/fig_hitk_col.png (figure) and paper/references.bib. Only word/document.xml is replaced; styles, numbering,
headers, footers and page setup stay exactly as the conference template defines them.
Usage: python -m vulnpairs docx
"""
import json
import re
import zipfile
from xml.sax.saxutils import escape

from ..paths import REPO_ROOT
from .bibliography import authors, parse_bib

PAPER = REPO_ROOT / "paper"
TEMPLATE = PAPER / "ICEET-2026-Template.docx"
OUT = PAPER / "ICEET-2026-paper.docx"

TITLE = "Leakage-Controlled Localisation of Vulnerable Lines in C/C++ Functions with Interpretable Features"

# figure label -> (png file in paper/generated, relationship id, description)
FIGS = {
    "fig:method": ("fig_method_col.png", "rIdFig2", "Pipeline of the proposed method: select, label, split, describe, rank, evaluate"),
    "fig:hitk": ("fig_hitk_col.png", "rIdFig1", "hit@k of the full model against chance for four CWE families"),
}
# e-mail addresses are read from paper/authors.json ({"name": "address"}), which stays local with the manuscript
_MAIL_FILE = PAPER / "authors.json"
_MAIL = json.loads(_MAIL_FILE.read_text(encoding="utf-8")) if _MAIL_FILE.exists() else {}
AUTHORS = [(n, _MAIL.get(n, "")) for n in ("Ved V Joshi", "Jai Udasi", "Sakshi Falak", "Aayush Patil")]
GUIDE = ("Prof. Shanta Sondur", _MAIL.get("Prof. Shanta Sondur", ""))
DEPT, ORG, CITY = "Dept. of Information Technology", "VES Institute of Technology", "Mumbai, India"

# column widths in points (a text column of the template is about 251 pt wide)
WIDTHS = {
    "tab:data": [44, 34, 36, 38, 30, 32, 30],
    "tab:pairs": [42, 30, 28, 28, 28, 28, 28, 28],
    "tab:main": [34, 34, 25, 25, 29, 22, 22, 22, 22, 22],
    "tab:ablation": [74, 22, 22, 22, 22, 22, 22, 22, 22],
    "tab:extra": [50, 28, 28, 26, 54, 26, 28, 26],
    "tab:strata": [40, 84, 28, 50, 50],
    "tab:diff": [44, 104, 104],
    "tab:challenges": [58, 96, 96],
}


# ---------------------------------------------------------------- numbers and text
def load_numbers():
    d = {}
    for m in re.finditer(r"\\newcommand\{\\(num[A-Za-z]+)\}\{([^\n]*)\}\s*$", (PAPER / "generated" / "numbers.tex").read_text(encoding="utf-8"), flags=re.M):
        d[m.group(1)] = m.group(2).replace("{,}", ",")
    return d


def roman(n):
    out = ""
    for v, s in ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out += s
            n -= v
    return out


class Ctx:
    def __init__(self, nums, cite_order, labels):
        self.nums, self.cite_order, self.labels = nums, cite_order, labels


def parse_group(s, i):
    """s[i] == '{'; returns (inner, index after the matching '}')."""
    depth, j = 0, i
    while j < len(s):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    raise ValueError("unbalanced braces: " + s[i:i + 60])


def tex_runs(s, ctx, b=False, it=False):
    """LaTeX fragment -> list of (text, bold, italic)."""
    out, i = [], 0

    def add(t, bb=b, ii=it):
        if t:
            out.append((t, bb, ii))

    while i < len(s):
        c = s[i]
        if c == "\\":
            m = re.match(r"\\([A-Za-z]+)", s[i:])
            if m:
                name = m.group(1)
                i += len(m.group(0))
                if name in ("textbf", "emph", "texttt", "textit"):
                    inner, i = parse_group(s, i)
                    out.extend(tex_runs(inner, ctx, b or name == "textbf", it or name in ("emph", "textit")))
                elif name == "cite":
                    inner, i = parse_group(s, i)
                    nums = [ctx.cite_order.index(k.strip()) + 1 for k in inner.split(",")]
                    add(", ".join(f"[{n}]" for n in nums))
                elif name == "ref":
                    inner, i = parse_group(s, i)
                    add(ctx.labels[inner])
                elif name == "url":
                    inner, i = parse_group(s, i)
                    add(inner)
                elif name == "label":
                    _, i = parse_group(s, i)
                elif name == "multirow":
                    _, i = parse_group(s, i)
                    _, i = parse_group(s, i)
                    inner, i = parse_group(s, i)
                    out.extend(tex_runs(inner, ctx, b, it))
                elif name.startswith("num"):
                    add(ctx.nums[name])
                    if s[i:i + 2] == "{}":
                        i += 2
                elif name in ("centering", "footnotesize", "small"):
                    pass
                else:
                    raise ValueError("unhandled LaTeX command \\" + name)
            else:
                nxt = s[i + 1] if i + 1 < len(s) else ""
                i += 2
                add({"%": "%", "&": "&", "_": "_", " ": " ", "#": "#", "$": "$", ",": "\u2009"}.get(nxt, nxt))
        elif c == "$":
            j = s.index("$", i + 1)
            add(s[i + 1:j], b, True)
            i = j + 1
        elif c == "~":
            add("\u00a0")
            i += 1
        elif s.startswith("``", i):
            add("\u201c")
            i += 2
        elif s.startswith("''", i):
            add("\u201d")
            i += 2
        elif s.startswith("--", i):
            add("\u2013")
            i += 2
        elif c in "{}":
            i += 1
        else:
            j = i
            while j < len(s) and s[j] not in "\\${}~`'-":
                j += 1
            if j == i:
                add(c)
                i += 1
            else:
                add(s[i:j])
                i = j
    # merge neighbours with identical formatting
    merged = []
    for t, bb, ii in out:
        if merged and merged[-1][1:] == (bb, ii):
            merged[-1] = (merged[-1][0] + t, bb, ii)
        else:
            merged.append((t, bb, ii))
    return merged


# ---------------------------------------------------------------- xml builders
def run_xml(t, b=False, it=False, sz=None):
    pr = ("<w:b/>" if b else "") + ("<w:i/>" if it else "") + (f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>' if sz else "")
    return f'<w:r>{"<w:rPr>" + pr + "</w:rPr>" if pr else ""}<w:t xml:space="preserve">{escape(t)}</w:t></w:r>'


def runs_xml(runs, sz=None):
    return "".join(run_xml(t, b, i, sz) for t, b, i in runs)


def para(style, runs, extra="", sect="", tail=""):
    ppr = f'<w:pStyle w:val="{style}"/>{extra}{sect}'
    return f"<w:p><w:pPr>{ppr}</w:pPr>{runs_xml(runs) if isinstance(runs, list) else runs}{tail}</w:p>"


def sect_xml(cols, header_refs=False, title_pg=False, cont=True):
    refs = ('<w:headerReference w:type="even" r:id="rId8"/><w:headerReference w:type="default" r:id="rId9"/>'
            '<w:footerReference w:type="even" r:id="rId10"/><w:footerReference w:type="default" r:id="rId11"/>'
            '<w:headerReference w:type="first" r:id="rId12"/><w:footerReference w:type="first" r:id="rId13"/>') if header_refs else ""
    mar = '<w:pgMar w:top="54pt" w:right="44.65pt" w:bottom="72pt" w:left="44.65pt" w:header="36pt" w:footer="36pt" w:gutter="0pt"/>'
    if cols == 2:
        mar = mar.replace("44.65pt", "45.35pt")
    colx = {1: '<w:cols w:space="36pt"/>', 2: '<w:cols w:num="2" w:space="18pt"/>', 4: '<w:cols w:num="4" w:space="10.80pt"/>'}[cols]
    return (f'<w:sectPr>{refs}{"<w:type w:val=" + chr(34) + "continuous" + chr(34) + "/>" if cont else ""}'
            f'<w:pgSz w:w="612pt" w:h="792pt" w:code="1"/>{mar}{colx}{"<w:titlePg/>" if title_pg else ""}<w:docGrid w:linePitch="360"/></w:sectPr>')


def author_para(name, email, first=True, sect="", after="0pt"):
    lines = [(name, False), (DEPT, True), (ORG, False), (CITY, False), (email, False)]
    runs = "" if first else '<w:r><w:br w:type="column"/></w:r>'  # break at the start, so no blank line tops the next column
    for k, (t, it) in enumerate(lines):
        runs += f'<w:r><w:rPr>{"<w:i/>" if it else ""}<w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr>{"<w:br/>" if k else ""}<w:t xml:space="preserve">{escape(t)}</w:t></w:r>'
    return f'<w:p><w:pPr><w:pStyle w:val="Author"/><w:spacing w:before="0pt" w:after="{after}"/>{sect}</w:pPr>{runs}</w:p>'


def parse_tabular(tex):
    m = re.search(r"\\begin\{tabular\}\{((?:[^{}]|\{[^{}]*\})*)\}(.*?)\\end\{tabular\}", tex, flags=re.S)
    spec, body = m.group(1), m.group(2)
    head_part, _, rest = body.partition("\\midrule")
    head_part = head_part.replace("\\toprule", "")
    rest = re.sub(r"\\(midrule|bottomrule)", "", rest)

    def rows_of(part):
        rows = []
        for r in re.split(r"\\\\", part):
            r = r.strip()
            if r:
                rows.append(r)
        return rows

    return spec, rows_of(head_part), rows_of(rest)


def table_xml(label, spec, head, body, ctx, left_cols=1, text_table=False):
    widths = WIDTHS[label]
    grid = "".join(f'<w:gridCol w:w="{int(w * 20)}"/>' for w in widths)

    def row(cells_tex, header):
        cells, k, tcs = cells_tex.split("&"), 0, ""
        for cell in cells:
            cell = cell.strip()
            span = 1
            mm = re.match(r"\\multicolumn\{(\d+)\}\{[^}]*\}\{(.*)\}$", cell, flags=re.S)
            if mm:
                span, cell = int(mm.group(1)), mm.group(2)
            w = sum(widths[k:k + span])
            runs = tex_runs(cell, ctx, b=header)
            style = "tablecolhead" if header else "tablecopy"
            jc = "start" if (k < left_cols or text_table) else "center"
            if header and not text_table:
                jc = "center"
            sz = '<w:sz w:val="15"/><w:szCs w:val="15"/>' if label in ("tab:main", "tab:ablation", "tab:pairs", "tab:extra") else ""
            r_xml = "".join(
                f'<w:r><w:rPr>{"<w:b/>" if b else ""}{"<w:i/>" if i else ""}{sz}</w:rPr><w:t xml:space="preserve">{escape(t)}</w:t></w:r>'
                for t, b, i in runs)
            tcs += (f'<w:tc><w:tcPr><w:tcW w:w="{w}pt" w:type="dxa"/>{f"<w:gridSpan w:val={chr(34)}{span}{chr(34)}/>" if span > 1 else ""}'
                    f'<w:vAlign w:val="center"/></w:tcPr><w:p><w:pPr><w:pStyle w:val="{style}"/><w:keepNext/><w:jc w:val="{jc}"/></w:pPr>{r_xml}</w:p></w:tc>')
            k += span
        trpr = "<w:trPr><w:cantSplit/>" + ("<w:tblHeader/>" if header else "") + "</w:trPr>"
        return f"<w:tr>{trpr}{tcs}</w:tr>"

    rows = "".join(row(r, True) for r in head) + "".join(row(r, False) for r in body)
    borders = "".join(f'<w:{s} w:val="single" w:sz="2" w:space="0" w:color="auto"/>' for s in ("top", "start", "bottom", "end", "insideH", "insideV"))
    mar = "".join(f'<w:{s} w:w="{v}" w:type="dxa"/>' for s, v in (("top", 15), ("start", 40), ("bottom", 15), ("end", 40)))
    return (f'<w:tbl><w:tblPr><w:tblW w:w="{int(sum(widths))}pt" w:type="dxa"/><w:jc w:val="center"/><w:tblBorders>{borders}</w:tblBorders>'
            f'<w:tblLayout w:type="fixed"/><w:tblCellMar>{mar}</w:tblCellMar><w:tblLook w:firstRow="0" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" w:noHBand="0" w:noVBand="0"/></w:tblPr>'
            f'<w:tblGrid>{grid}</w:tblGrid>{rows}</w:tbl>')


def spacer():
    return '<w:p><w:pPr><w:pStyle w:val="BodyText"/><w:spacing w:after="0pt" w:line="6pt" w:lineRule="exact"/><w:ind w:firstLine="0pt"/></w:pPr></w:p>'


def png_size(path, width_emu=3108960):
    """(cx, cy) in EMU for a PNG scaled to the given width (3.4 in by default), read from the PNG header."""
    import struct
    head = path.read_bytes()[:24]
    w, h = struct.unpack(">II", head[16:24])
    return width_emu, int(round(width_emu * h / w))


def note_xml(runs):
    """Footnote under a table: template style 'table footnote' without its list number, left to right, 7.5 pt."""
    extra = ('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="0"/></w:numPr><w:spacing w:before="2pt" w:after="6pt"/>'
             '<w:ind w:start="0pt" w:firstLine="0pt"/><w:jc w:val="both"/>')
    return para("tablefootnote", runs_xml([("Note: ", False, True)] + runs, sz=15), extra)


def image_xml(rid, cx, cy, did, name, file, descr):
    return (f'<w:p><w:pPr><w:pStyle w:val="BodyText"/><w:keepNext/><w:spacing w:before="6pt" w:after="0pt"/><w:ind w:firstLine="0pt"/><w:jc w:val="center"/></w:pPr>'
            f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:docPr id="{did}" name="{name}" descr="{escape(descr)}"/>'
            f'<a:graphic xmlns:a="http://purl.oclc.org/ooxml/drawingml/main"><a:graphicData uri="http://purl.oclc.org/ooxml/drawingml/picture">'
            f'<pic:pic xmlns:pic="http://purl.oclc.org/ooxml/drawingml/picture"><pic:nvPicPr><pic:cNvPr id="0" name="{file}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            f'</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')


# ---------------------------------------------------------------- bibliography
def reference_runs(e):
    segs = [(authors(e["author"]) + ", \u201c" + re.sub(r"[{}]", "", e["title"]) + ",\u201d ", False)]
    if "booktitle" in e:
        segs.append(("in ", False))
        segs.append((e["booktitle"], True))
        segs.append((", ", False))
    if "journal" in e:
        segs.append((e["journal"], True))
        segs.append((", ", False))
        if "volume" in e:
            segs.append(("vol. " + e["volume"] + ", ", False))
        if "number" in e:
            segs.append(("no. " + e["number"] + ", ", False))
    if "pages" in e:
        segs.append(("pp. " + e["pages"].replace("--", "\u2013") + ", ", False))
    tail = e["year"] + "."
    if "note" in e:
        tail += " " + e["note"].replace("; year inferred from volume 52, verify", "") + "."
    if "doi" in e:
        tail += " doi: " + e["doi"] + "."
    segs.append((tail.replace("..", "."), False))
    return [(t, False, it) for t, it in segs]


# ---------------------------------------------------------------- main build
TOKEN = re.compile(
    r"\\begin\{(abstract|IEEEkeywords|enumerate|table\*?|figure\*?)\}(.*?)\\end\{\1\}"
    r"|\\(section\*?|subsection)\{([^}]*)\}(?:\\label\{([^}]*)\})?"
    r"|\\input\{generated/bibliography\}", re.S)


def build():
    tex = (PAPER / "main.tex").read_text(encoding="utf-8")
    tex = re.sub(r"(?m)^%.*$", "", tex)
    body = tex[tex.index("\\maketitle") + len("\\maketitle"):tex.index("\\end{document}")]
    nums = load_numbers()
    bib = parse_bib((PAPER / "references.bib").read_text(encoding="utf-8"))

    cite_order = []
    for m in re.finditer(r"\\cite\{([^}]*)\}", body):
        for k in m.group(1).split(","):
            if k.strip() not in cite_order:
                cite_order.append(k.strip())

    # pass 1: numbers for sections, tables and figures
    labels, s1, s2, nt, nf = {}, 0, 0, 0, 0
    for m in TOKEN.finditer(body):
        env, inner, sec, _, lab = m.groups()
        if sec == "section":
            s1, s2 = s1 + 1, 0
            if lab:
                labels[lab] = roman(s1)
        elif sec == "subsection":
            s2 += 1
            if lab:
                labels[lab] = f"{roman(s1)}-{chr(64 + s2)}"
        elif env and env.startswith("table"):
            nt += 1
            labels[re.search(r"\\label\{([^}]*)\}", inner).group(1)] = roman(nt)
        elif env and env.startswith("figure"):
            nf += 1
            labels[re.search(r"\\label\{([^}]*)\}", inner).group(1)] = str(nf)
    ctx = Ctx(nums, cite_order, labels)

    # title section
    xml = [para("papertitle", [(TITLE, False, False)], '<w:spacing w:before="5pt" w:beforeAutospacing="1" w:after="5pt" w:afterAutospacing="1"/>')]
    xml.append(f'<w:p><w:pPr><w:pStyle w:val="Author"/><w:spacing w:before="5pt" w:beforeAutospacing="1" w:after="5pt" w:afterAutospacing="1" w:line="6pt" w:lineRule="auto"/>'
               f'{sect_xml(1, header_refs=True, title_pg=True, cont=False)}</w:pPr></w:p>')
    xml.append(author_para(GUIDE[0], GUIDE[1], first=True, sect=sect_xml(1), after="10pt"))  # supervisor is the first author
    for k, (n, e) in enumerate(AUTHORS):
        last = k == len(AUTHORS) - 1
        xml.append(author_para(n, e, first=(k == 0), sect=sect_xml(4) if last else "", after="10pt" if last else "0pt"))

    pos = 0
    for m in list(TOKEN.finditer(body)) + [None]:
        chunk = body[pos:m.start()] if m else body[pos:]
        for ptxt in re.split(r"\n\s*\n", chunk):
            ptxt = " ".join(ptxt.split())
            if ptxt:
                xml.append(para("BodyText", tex_runs(ptxt, ctx)))
        if m is None:
            break
        pos = m.end()
        env, inner, sec, title, lab = m.groups()
        if env == "abstract":
            runs = [("Abstract", False, True), ("\u2014", False, False)] + tex_runs(" ".join(inner.split()), ctx)
            xml.append(para("Abstract", runs))
        elif env == "IEEEkeywords":
            xml.append(para("Keywords", [("Keywords\u2014", True, True)] + tex_runs(" ".join(inner.split()), ctx, False, False)))
        elif env == "enumerate":
            for k, item in enumerate([i for i in re.split(r"\\item", inner) if i.strip()], 1):
                xml.append(para("BodyText", [(f"{k}) ", False, False)] + tex_runs(" ".join(item.split()), ctx)))
        elif sec:
            style = "Heading5" if sec.endswith("*") else ("Heading1" if sec == "section" else "Heading2")
            xml.append(para(style, tex_runs(title, ctx), "<w:keepNext/>"))  # a heading never ends a column
        elif env and env.startswith("table"):
            label = re.search(r"\\label\{([^}]*)\}", inner).group(1)
            cap = re.search(r"\\caption\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}", inner).group(1)
            xml.append(para("tablehead", tex_runs(" ".join(cap.split()), ctx), "<w:keepNext/>"))  # caption stays with its table
            inp = re.search(r"\\input\{(generated/[^}]*)\}", inner)
            src = (PAPER / (inp.group(1) + ".tex")).read_text(encoding="utf-8") if inp else inner
            spec, head, rows = parse_tabular(src)
            xml.append(table_xml(label, spec, head, rows, ctx, left_cols=2 if label in ("tab:main", "tab:strata") else 1,
                                 text_table=label in ("tab:diff", "tab:challenges")))
            nm = re.search(r"\\tablenote\{", inner)
            if nm:  # footnote under the table (professor's request: explanations go below, not into the caption)
                note, _ = parse_group(inner, nm.end() - 1)
                xml.append(note_xml(tex_runs(" ".join(note.split()), ctx)))
            else:
                xml.append(spacer())
        elif env and env.startswith("figure"):
            cap = re.search(r"\\caption\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}", inner).group(1)
            flabel = re.search(r"\\label\{([^}]*)\}", inner).group(1)
            fname, rid, descr = FIGS[flabel]
            xml.append(image_xml(rid, *png_size(PAPER / "generated" / fname), 100 + int(labels[flabel]), "Figure " + labels[flabel], fname, descr))
            xml.append(para("figurecaption", tex_runs(" ".join(cap.split()), ctx)))
        else:  # \input{generated/bibliography}
            xml.append(para("Heading5", [("References", False, False)], "<w:keepNext/>"))
            for k in cite_order:
                xml.append(para("references", reference_runs(bib[k]), '<w:ind w:start="17.70pt" w:hanging="17.70pt"/>'))
    return "".join(xml) + sect_xml(2), nums


def main() -> None:
    body, _ = build()
    zin = zipfile.ZipFile(TEMPLATE)
    doc = zin.read("word/document.xml").decode("utf-8")
    head = doc[:doc.index("<w:body>") + len("<w:body>")]
    new_doc = head + body + "</w:body></w:document>"
    rels = zin.read("word/_rels/document.xml.rels").decode("utf-8")
    rels = rels.replace("</Relationships>", "".join(
        f'<Relationship Id="{rid}" Type="http://purl.oclc.org/ooxml/officeDocument/relationships/image" Target="media/{fname}"/>'
        for fname, rid, _ in FIGS.values()) + "</Relationships>")
    ctypes = zin.read("[Content_Types].xml").decode("utf-8")
    if 'Extension="png"' not in ctypes:
        ctypes = ctypes.replace("<Override", '<Default Extension="png" ContentType="image/png"/><Override', 1)
    core = zin.read("docProps/core.xml").decode("utf-8")
    core = re.sub(r"(<dc:title>)[^<]*(</dc:title>)", r"\g<1>" + escape(TITLE) + r"\g<2>", core)
    core = re.sub(r"(<dc:creator>)[^<]*(</dc:creator>)", r"\g<1>" + escape(", ".join([GUIDE[0]] + [a for a, _ in AUTHORS])) + r"\g<2>", core)
    target = OUT
    try:
        open(OUT, "ab").close()
    except PermissionError:  # the file is open in Word: write beside it instead of failing
        target = OUT.with_name(OUT.stem + "-new.docx")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = new_doc.encode("utf-8")
            elif item.filename == "word/_rels/document.xml.rels":
                data = rels.encode("utf-8")
            elif item.filename == "[Content_Types].xml":
                data = ctypes.encode("utf-8")
            elif item.filename == "word/footer3.xml":  # drop the template's copyright placeholder line
                data = data.decode("utf-8").replace("XXX-X-XXXX-XXXX-X/XX/$XX.00 ©20XX IEEE", "").encode("utf-8")
            elif item.filename == "docProps/core.xml":
                data = core.encode("utf-8")
            zout.writestr(item, data)
        for fname, _, _ in FIGS.values():
            zout.writestr("word/media/" + fname, (PAPER / "generated" / fname).read_bytes())
    print("wrote", target)


if __name__ == "__main__":
    main()
