#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-20.5
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

3. A PARAGRAPH IS NOT ALWAYS A <p>, AND SPANS ARE NOT THE WHOLE STORY. Walking
   <p> alone missed the spans inside <li>, <h1> and <h3>; collecting spans
   with findall dropped the whitespace BETWEEN them, so "credits pursuant"
   came out "creditspursuant" wherever the Court closed one span and opened
   the next mid-sentence. Both are recorded at the patterns below.

4. THE BRACKETS ARE STILL IN THE TEXT. Removed matter is struck AND wrapped in
   square brackets in the source, so the two encodings can be checked against
   each other -- a struck run that is not inside brackets, or a bracketed run
   that is not struck, means this parser has drifted. --probe reports that
   agreement as a number rather than trusting it.

WHAT IS LEFT, named rather than half-handled. Three documents of 6,825 still
differ from the plain column by more than 2%, and all three are fiscal notes
whose figures live in <table> rather than in paragraphs -- "FY 2025 FY 2026
FY 2027 GEN'L & EDUCATION TRUST FUND". Tables are a different kind of content
from marked prose and want different treatment in the reading view, so they
wait for that rather than being flattened into it here.
"""

import argparse
import collections
import difflib
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
#
# AND A PARAGRAPH IS NOT ALWAYS A <p>. Walking <p> alone reached 95,892 of the
# 96,218 spans in a sample of 975 documents and missed 326 -- 319 in <li>,
# five in <h3>, two in <h1>. That reads as a rounding error and is not: the
# misses are concentrated, so on House Resolution 3 the <ol><li> block held
# three of ten spans and more than half the words, and the document came out
# at 39 words against the plain column's 161. A numbered list in a New
# Hampshire bill carries statute like any other paragraph.
PARA = re.compile(
    r'<(p|li|h[1-6])\b[^>]*class="(cs[0-9A-Fa-f]{6,8})"[^>]*>(.*?)</\1>', re.S)
SPAN = re.compile(r'<span\b[^>]*class="(cs[0-9A-Fa-f]{6,8})"[^>]*>(.*?)</span>', re.S)
SIZE = re.compile(r"font-size:\s*([\d.]+)pt")
ANCHOR = re.compile(r'<a\b[^>]*name="([^"]+)"', re.I)

# THE LEGEND IS THREE SENTENCES, NOT TWO, and the third was being set as
# statute. Counted over a sample of every 23rd document: "Explanation: Matter
# added to current law appears in bold italics." 207 times, "Matter removed
# from current law appears [in brackets and struckthrough.]" 207 times, and
# "Matter which is either (a) all new or (b) repealed and reenacted appears in
# regular type" 207 times -- the last of which matched neither pattern, so
# every bill in the state rendered one line of its own legend in the body
# face as though the Court had enacted it. Found by looking at the rendered
# page rather than at the parser.
#
# The full stop is optional because 2 of the 207 have none, and "Explanation"
# needs its colon: "Explanation to Enrolled Bill Amendment to HB 464" is a
# real heading on five bills and is not a legend.
LEGEND = re.compile(
    r"matter (added|removed) (to|from) current law"
    r"|matter which is either\b.{0,90}?\bappears in regular type", re.I | re.S)
EXPLANATION = re.compile(r"^\s*Explanation\s*:", re.I)
# "SB 12 - AS INTRODUCED", "HB 99 - VERSION ADOPTED BY BOTH BODIES",
# "HB 1718-FN - CHAPTERED FINAL VERSION". Matching only the "AS ..." wording
# left the 166 enrolled and chaptered printings reading four to six words long,
# which was most of what remained after the first pass -- so this matches a
# bill number, a dash, and a run of capitals, and is anchored at both ends so a
# sentence merely mentioning a bill number is not mistaken for the header.
HEADER = re.compile(
    r"^(?:[A-Z]{2,5}\s*\d+[-\w]*)\s*[-–]\s*[A-Z][A-Z \-]{3,}$")


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
    for tag, pcls, inner in PARA.findall(body):
        anchor = ANCHOR.search(inner)
        # WALKED IN ORDER, NOT COLLECTED. findall over the spans drops
        # whatever sits BETWEEN them, and what sits between them is sometimes
        # the space that separates two words: "credits pursuant" came out
        # "creditspursuant" wherever the Court closed one span and opened the
        # next mid-sentence. The gaps are carried through as plain text.
        runs = []
        pos = 0
        for m in SPAN.finditer(inner):
            gap = strip_tags(inner[pos:m.start()])
            pos = m.end()
            if gap.strip() or (gap and runs):
                runs.append(["plain", gap if gap.strip() else " "])
            scls, raw = m.group(1), m.group(2)
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
        # THE RUNNING HEADER IS NOT THE BILL. Every printing repeats its own
        # number and version at the head -- "SB 12 - AS INTRODUCED" -- which
        # the database's plain Text column does not carry. It is page
        # furniture, and calling it text made this converter read four words
        # longer than the record on most documents.
        if HEADER.match(flat.strip()):
            kind = "head"
        elif LEGEND.search(flat) or EXPLANATION.match(flat):
            kind = "legend"
        elif tag in ("li",):
            kind = "item"
        elif tag.startswith("h"):
            kind = "head"
        else:
            kind = "ln"
        blk = {"k": kind, "runs": [[r if r != "plain" else "", t] for r, t in runs]}
        if anchor:
            blk["id"] = anchor.group(1)
        out.append(blk)
    return out


# A RULE IS NOT A WORD. The Court draws the line above a footer sometimes with
# ASCII hyphens and sometimes with U+2500 BOX DRAWINGS LIGHT HORIZONTAL, and it
# can differ between two printings of the SAME bill whose text is otherwise
# byte-identical. Diffed as text, that reads as sixty-five words removed and
# sixty-five added, which the page would then state as a change to the law.
# Measured: 8,840 U+2500 inside the differing runs of pairs that are identical
# in the Court's own plain column, and it is the ONLY non-ASCII character in
# any of them -- so this is the whole of that defect and no quote or dash
# normalisation is needed for it.
RULE_RUN = re.compile(r"^[-_=~.·‐-―─━]{3,}$")


def diff_stream(bs):
    """The words that count as the bill's text when two printings are compared.

    NOT THE SAME THING AS THE DOCUMENT, and the difference is the point. The
    document keeps its running header, its legend and its rules, because a
    reader is looking at a printed bill and those are on it. The comparison
    drops all three, because none of them is the law:

      * the running header names the printing, so it differs between every
        pair by definition -- "AS INTRODUCED" against "AS AMENDED BY THE
        HOUSE" -- and would report a change on every step ever taken;
      * the legend explains the bold-italic and bracket conventions and is the
        same sentence in every bill in the state;
      * a rule is furniture, and is drawn with different characters in
        different printings.

    Scored rather than argued: of 2,582 consecutive printing pairs, 480 are
    byte-identical in the database's own plain Text column and must therefore
    come out at zero changes.

        diffing every block                          479 called changed
        dropping the running header                  136
        dropping the legend as well                  136  (no effect: the
                                                     legend is the same
                                                     sentence in both)
        dropping rule runs as well                    12

    --probe reports that last number, so a change that lets furniture back
    into the comparison fails loudly rather than publishing false claims about
    bills.

    THE REMAINING TWELVE ARE NOT UNDERSTOOD and are not claimed to be. What is
    established: every differing word is plain ASCII, so no character this
    parser mishandles is involved; the difference is present in the HTML and
    absent from the plain column of the same two rows; and it takes the shape
    of one printing having a character where the other has nothing, as in
    '"Spouse"means' against '"Spouse"?means'. That pattern is what a lossy
    encode looks like applied inconsistently between two printings, which
    would put the damage in the database dump rather than here -- but that is
    a hypothesis and it has not been tested, so it is written down as one.
    Twelve of 2,582 pairs, 0.5%.
    """
    return [w for w, _, _, _ in word_spans(bs)]


def word_spans(bs):
    """Every diffable word with WHERE IT SITS: (word, block, start, end).

    The same words diff_stream returns, each with the block it is in and its
    character offsets inside that block's joined text. This is what lets a
    comparison be drawn ON the document instead of as an excerpt beside it.

    CHARACTER OFFSETS, NOT WORD INDICES, and the reason is a tokenisation that
    cannot be made to agree otherwise. The runs inside a block split wherever
    the Court changed typeface, which is usually mid-token: "[" is one run and
    "in brackets" the next. Joining the runs and then splitting gives "[in" --
    one word, and the same word the plain Text column has, which is what makes
    the diff comparable with the record. Splitting each run separately would
    give "[" and "in", two words, and a different stream.

    A reader's browser has the runs, not the joined text, so a mark expressed
    as "the 412th word" would have to be resolved against whichever of those
    two streams the client happened to build. Character offsets into the
    block's joined text are unambiguous: the client concatenates its runs,
    which it already has, and the offsets land where the server meant. It also
    handles the eleven places in 23,527 run boundaries where a boundary really
    does fall inside an alphanumeric word -- "propert|y." -- which a
    word-indexed mark cannot express at all.

    Blocks are indexed over the WHOLE list, header and legend included, so an
    index here means the same thing as an index into the blocks file. Only
    which words are DIFFED is filtered.
    """
    out = []
    for bi, b in enumerate(bs):
        if b["k"] in ("head", "legend"):
            continue
        text = "".join(t for _, t in (b.get("runs") or []))
        for m in re.finditer(r"\S+", text):
            w = m.group(0)
            if RULE_RUN.match(w):
                continue
            out.append((w, bi, m.start(), m.end()))
    return out


def marks(old_bs, new_bs):
    """What one printing did to the next, as spans over the NEW document.

    Returns (marks, added, removed). A mark is
        [block, start, end, "+"]                matter this printing inserts
        [block, at,    at,  "-", "the words"]   matter it removes
    and both are positions in the NEW version's blocks, because that is the
    document the reader is looking at.

    A REMOVAL HAS NO PLACE IN THE NEW TEXT, which is the awkward case and the
    reason removed words travel with their mark rather than being pointed at.
    It is anchored at the start of the next surviving word, or at the end of
    the last one when the removal runs to the end of the bill -- so it sits
    where the reader would have found it.
    """
    a, b = word_spans(old_bs), word_spans(new_bs)
    aw = [w for w, _, _, _ in a]
    bw = [w for w, _, _, _ in b]
    out, added, removed = [], 0, 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, aw, bw, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        if j1 != j2:
            added += j2 - j1
            # Consecutive inserted words inside one block are one mark; a run
            # that crosses a paragraph becomes one mark per paragraph, because
            # a span cannot straddle two blocks.
            for _, bi, s, e in b[j1:j2]:
                if out and out[-1][0] == bi and out[-1][3] == "+":
                    out[-1][2] = e
                else:
                    out.append([bi, s, e, "+"])
        if i1 != i2:
            removed += i2 - i1
            if b:
                _, bi, s, e = b[j2] if j2 < len(b) else b[-1]
                at = s if j2 < len(b) else e
                out.append([bi, at, at, "-", " ".join(aw[i1:i2])])
    return out, added, removed


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
        # RUNS JOIN WITH NOTHING, BLOCKS JOIN WITH A SPACE. Joining runs with
        # a space was this probe's own bug and not the parser's: a bracket and
        # the struck words inside it are two runs because they carry different
        # marking, so "[in brackets" came out "[ in brackets" and counted one
        # word extra every time. It made 1,711 documents look 2% long.
        # The legend IS in the database's plain column and stays in; the
        # running header is not and comes out.
        text = " ".join("".join(t for _, t in b["runs"])
                        for b in bs if b["k"] != "head")
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
    if not limit:
        _score_diff_stream()


def _score_diff_stream():
    """The one number that says whether the comparison lies.

    A pair of printings the database's own plain column says are byte for byte
    the same cannot have changed, so any the diff stream calls changed are
    false claims about a bill -- the project's first triage category, not its
    third. This is the guard on that.
    """
    order = json.loads((DB / "document_versions.json").read_text(encoding="utf-8"))
    per = collections.defaultdict(list)
    for i, lid, doc, plain, ver in rows():
        # OLS Release is an AMENDMENT document, not a printing of the bill --
        # 2,009 of 6,825 rows. Left in, it pairs a bill against its own
        # amendment text and word-stream similarity collapses from 0.95 to
        # 0.64, which reads as the documents being incomparable when it is
        # only that the wrong two were compared.
        if ver == "OLS Release":
            continue
        per[lid].append((order.get(ver, {}).get("sort", 999), ver, doc, plain))

    pairs = identical = false = 0
    for lid, vs in per.items():
        vs.sort(key=lambda x: x[0])
        for a, b in zip(vs, vs[1:]):
            pairs += 1
            if a[3] != b[3]:
                continue
            identical += 1
            if diff_stream(blocks(a[2])) != diff_stream(blocks(b[2])):
                false += 1
    print(f"\n  {pairs:,} consecutive printing pairs, {identical:,} of them "
          f"byte-identical\n  in the plain Text column")
    print(f"    called changed anyway: {false:,}"
          + ("   <- every one is a false claim about a bill" if false else ""))


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
