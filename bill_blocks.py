#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-20.1
"""
Read the General Court's own typeset bill HTML into blocks of marked runs.

    python3 bill_blocks.py --probe            # score it over every row
    python3 bill_blocks.py --show 893         # print one row as marked text

NO NETWORK. It reads db/LegislationText.psv, which the database dump already
put on this disk, and writes nothing. Step three of the Bill Text rebuild, and
it is deliberately its own module rather than an edit to build_bill_versions:
that file works today, this has to be proved first, and a converter that can be
scored on its own is worth more than one tangled into a builder.

WHY BOTHER, when db already has a plain Text column. Because the HTML carries
something the plain text does not: THE COURT'S OWN MARKING of what the bill
adds to and removes from existing law. A New Hampshire bill is written as an
edit to the statute -- added matter in bold italics, removed matter in brackets
and struck through -- and every printing says so in a legend at its head. That
marking is thrown away at parse time today, which is why the archive's Bill
Text tab can show a document but not what the bill DOES to the law.

THE FORMAT, read off the artefact rather than assumed. Each document carries
its own <style> block defining classes named csXXXXXXX. Paragraph classes hold
layout (text-align, text-indent, margin); span classes hold typography (font,
size, weight, style, decoration). So:

    .cs5D3E032C{... font-weight:normal;font-style:normal;text-decoration: line-through;}
    .csE2DB38B2{... font-size:9pt;font-weight:bold;font-style:italic;}
    .csDD5E5F52{... font-size:10pt;font-weight:normal;font-style:normal;}

line-through is removed matter, bold+italic is added matter, the rest is the
law as it stands.

THREE THINGS THAT WOULD HAVE CORRUPTED THE OUTPUT, all found by opening real
documents before writing this rather than after:

1. THE LEGEND USES THE REAL CLASSES. Every bill heads its text with
   "Explanation: Matter added to current law appears in bold italics. Matter
   removed from current law appears [in brackets and struckthrough.]" -- and
   the words "bold italics." really are bold italic, and "in brackets and
   struckthrough." really is struck. Read naively, every bill in the state
   appears to delete that sentence from the law. The legend is detected and
   marked as what it is.

2. BOLD ITALIC IS ALSO A HEADING. The bill number at the top is set in 14pt
   bold italic where the body runs at 9 or 10pt. Weight and style alone are
   not enough; the size has to match the document's own body size, which is
   computed per document rather than assumed, because it differs between
   printings.

3. THE BRACKETS ARE STILL IN THE TEXT. Removed matter is struck AND wrapped in
   square brackets in the source, so the two encodings can be checked against
   each other -- a struck run that is not inside brackets, or a bracketed run
   that is not struck, means this parser has drifted. --probe reports that
   agreement as a number rather than trusting it.
"""

import argparse
import collections
import html as H
import io
import json
import re
from pathlib import Path

DB = Path("db")

RULE = re.compile(r"\.(cs[0-9A-Fa-f]{6,8})\s*\{([^}]*)\}")
STYLE = re.compile(r"<style[^>]*>(.*?)</style>", re.S)
# A <p> or <span> may carry a style attribute after its class, which is why
# this does not look for class="..." immediately after the tag name.
PARA = re.compile(r'<p\b[^>]*class="(cs[0-9A-Fa-f]{6,8})"[^>]*>(.*?)</p>', re.S)
SPAN = re.compile(r'<span\b[^>]*class="(cs[0-9A-Fa-f]{6,8})"[^>]*>(.*?)</span>', re.S)
SIZE = re.compile(r"font-size:\s*([\d.]+)pt")
ANCHOR = re.compile(r'<a\b[^>]*name="([^"]+)"', re.I)

LEGEND = re.compile(r"matter (added|removed) (to|from) current law", re.I)
EXPLANATION = re.compile(r"^\s*Explanation\s*:", re.I)


def strip_tags(s):
    return H.unescape(re.sub(r"<[^>]+>", "", s))


def _roles(style_text):
    """class -> (role, size). Role is decided on decoration and weight+style;
    the size is returned so the caller can reject a heading."""
    out = {}
    for cls, decl in RULE.findall(style_text or ""):
        m = SIZE.search(decl)
        size = float(m.group(1)) if m else 0.0
        if "line-through" in decl:
            role = "cut"
        elif "font-weight:bold" in decl and "font-style:italic" in decl:
            role = "add"
        else:
            role = "plain"
        out[cls] = (role, size)
    return out


def _body_size(roles, body):
    """The document's own body size, in points.

    Taken from the plain spans actually used, weighted by how much text each
    carries, because a document defines classes it never uses and the largest
    block of ordinary prose is the body by definition. Assuming 10pt was
    tempting and wrong: printings differ, and 9pt is common.
    """
    weight = collections.Counter()
    for cls, inner in SPAN.findall(body):
        role, size = roles.get(cls, ("plain", 0.0))
        if role == "plain" and size:
            weight[size] += len(strip_tags(inner))
    return weight.most_common(1)[0][0] if weight else 0.0


def blocks(doc):
    """The document as [{k, id, runs:[[role, text], ...]}].

    role is "" for the law as it stands, "add" for matter the bill inserts and
    "cut" for matter it removes. A block whose k is "legend" is the bill's own
    explanation of those two conventions and is not part of the text.
    """
    st = STYLE.search(doc)
    roles = _roles(st.group(1) if st else "")
    i = doc.find("<body>")
    body = doc[i:] if i >= 0 else doc
    base = _body_size(roles, body)

    out = []
    for pcls, inner in PARA.findall(body):
        anchor = ANCHOR.search(inner)
        runs = []
        for scls, raw in SPAN.findall(inner):
            text = strip_tags(raw)
            if not text.strip():
                continue
            role, size = roles.get(scls, ("plain", 0.0))
            # A HEADING IS NOT AN INSERTION. Bold italic at anything other
            # than the body size is the bill's own furniture -- its number,
            # its title -- and calling it added matter would tell a reader the
            # bill inserts its own heading into the statute.
            if role == "add" and base and abs(size - base) > 0.01:
                role = "plain"
            if runs and runs[-1][0] == role:
                runs[-1][1] += text
            else:
                runs.append([role, text])
        if not runs:
            continue
        flat = "".join(t for _, t in runs)
        kind = "legend" if (LEGEND.search(flat) or EXPLANATION.match(flat)) else "ln"
        blk = {"k": kind, "runs": [[r if r != "plain" else "", t] for r, t in runs]}
        if anchor:
            blk["id"] = anchor.group(1)
        out.append(blk)
    return out


def as_marked(bs):
    """One string, brackets and braces showing the marking. For reading, and
    for a person to check this against the PDF with their own eyes."""
    lines = []
    for b in bs:
        s = "".join(("[-" + t + "-]") if r == "cut"
                    else ("{+" + t + "+}") if r == "add" else t
                    for r, t in b["runs"])
        lines.append(("LEGEND: " if b["k"] == "legend" else "") + s.strip())
    return "\n".join(lines)


def rows(limit=None):
    C = json.loads((DB / "_columns.json").read_text(encoding="utf-8"))
    lt = C["LegislationText"]
    i_lid, i_html, i_txt, i_dv = (lt.index("LegislationID"), lt.index("HTMLText"),
                                  lt.index("Text"), lt.index("DocumentVersion"))
    with io.open(DB / "LegislationText.psv", encoding="utf-8",
                 errors="replace") as f:
        for i, line in enumerate(f, 1):
            p = line.rstrip("\n").split("|")
            if len(p) < len(lt):
                continue
            yield i, p[i_lid].strip(), p[i_html], p[i_txt], p[i_dv].strip()
            if limit and i >= limit:
                return


def probe(limit=None):
    n = marked = no_html = 0
    legends = 0
    wdiff = []
    bracket_ok = bracket_bad = 0
    sizes = collections.Counter()
    for i, lid, doc, plain, ver in rows(limit):
        n += 1
        if "<body>" not in doc:
            no_html += 1
            continue
        bs = blocks(doc)
        if not bs:
            no_html += 1
            continue
        legends += sum(1 for b in bs if b["k"] == "legend")
        text = " ".join(t for b in bs if b["k"] != "legend"
                        for _, t in b["runs"])
        pw, bw = len(plain.split()), len(text.split())
        if pw:
            wdiff.append(abs(bw - pw) / pw)
        if any(r == "cut" or r == "add" for b in bs for r, _ in b["runs"]
               if b["k"] != "legend"):
            marked += 1
        # THE TWO ENCODINGS SHOULD AGREE: struck matter is also bracketed.
        for b in bs:
            if b["k"] == "legend":
                continue
            s = "".join(t for _, t in b["runs"])
            for r, t in b["runs"]:
                if r != "cut" or not t.strip():
                    continue
                k = s.find(t)
                before, after = s[:k], s[k + len(t):]
                if before.rstrip().endswith("[") or after.lstrip().startswith("]"):
                    bracket_ok += 1
                else:
                    bracket_bad += 1
        st = STYLE.search(doc)
        if st:
            sizes[_body_size(_roles(st.group(1)), doc[doc.find("<body>"):])] += 1

    med = sorted(wdiff)[len(wdiff) // 2] if wdiff else 0
    over = sum(1 for d in wdiff if d > 0.02)
    print(f"{n:,} rows read")
    print(f"  {no_html:,} carry no usable HTML body")
    print(f"  {marked:,} carry added or removed matter outside the legend "
          f"({marked / max(1, n - no_html) * 100:.0f}% of the rest)")
    print(f"  {legends:,} legend paragraphs recognised and set aside")
    print(f"\n  word count against the plain Text column:")
    print(f"    median difference {med * 100:.2f}%")
    print(f"    {over:,} of {len(wdiff):,} rows differ by more than 2%")
    tot = bracket_ok + bracket_bad
    print(f"\n  struck runs also inside brackets: {bracket_ok:,} of {tot:,} "
          f"({bracket_ok / max(1, tot) * 100:.1f}%)")
    print(f"\n  body font size, per document: "
          + ", ".join(f"{s:g}pt {c:,}" for s, c in sizes.most_common(5)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true",
                    help="score the converter over every row")
    ap.add_argument("--show", type=int, metavar="ROW",
                    help="print one row as marked text")
    ap.add_argument("--limit", type=int, help="stop after N rows")
    a = ap.parse_args()
    if a.show:
        for i, lid, doc, plain, ver in rows():
            if i == a.show:
                print(f"row {i}  LegislationID {lid}  {ver}\n")
                print(as_marked(blocks(doc)))
                return
        print(f"no row {a.show}")
    else:
        probe(a.limit)


if __name__ == "__main__":
    main()
