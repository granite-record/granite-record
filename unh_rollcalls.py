#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.1
"""
Put the words back in the order the page prints them. No network.

    python3 unh_rollcalls.py --reflow journalofhouseof1997newh
    python3 unh_rollcalls.py --page 85 journalofhouseof1997newh   # one page, to read
    python3 unh_rollcalls.py --confidence journalofhouseof1997newh

WHAT IS WRONG WITH THE TEXT LAYER, AND WHY THIS FIXES IT

A roll call in these journals is set in four columns under a county heading.
The Internet Archive's flattened _djvu.txt reads them in an order that is not
the printed one, and unh_measure.py --split measures what that costs: the
names survive, and which side of the vote they were on does not. 62% of roll
calls come out with the right total number of names and only 11% with each
side right, because the NAYS heading is an object on the page like any other
and column-major reading does not leave it between the two lists.

The _djvu.xml carries a bounding box for every word. Page 85 of the 1997
House volume settles the layout without any guessing:

    y 1131   [823]YEAS [986]186 [1082]NAYS [1243]185
    y 1210   [949]YEAS [1114]186
    y 1305   [939]BELKNAP
    y 1384   [61]Laflam, [197]Robert   [560]Veazey, [701]John
    y 1467   [936]CARROLL
    y 1546   [60]Cooper, [204]Kipp   [561]Dickinson, [750]Howard, [898]Jr. ...

Four columns at x of roughly 60, 561, 1062 and 1566, headings centred over
them, and the rows running across. So reading order is simply: group words
into lines by y, sort each line by x, take pages in order. That is all this
script does. It is deliberately not clever -- no column detection, no
heuristics about counties -- because the geometry already says it plainly,
and an inference layer here would be a second thing that can be wrong.

The output is scored by the same extractor that scored the flat text:

    python3 unh_measure.py --ocr data/unh/reflow/journalofhouseof1997newh.txt

Same code, same roll calls, one difference. Whatever the number moves by is
what reading order was worth.

COORDINATES

DjVu writes coords="x0,y1,x1,y0". Read off page 1 rather than assumed: NEW
HAMPSHIRE GENERAL COURT, the top line of the title page, is y 374-440 on a
page 3382 high, so y increases DOWNWARD and the second value is the bottom
edge. x0 is the left edge and x1 the right.
"""

import argparse
import re
import statistics
import sys
from pathlib import Path

RAW = Path("archive/unh/raw")
OUT = Path("data/unh/reflow")

PAGE = re.compile(r'usemap="[^"]*_(\d{4})\.djvu"')
WORD = re.compile(r'<WORD coords="(\d+),(\d+),(\d+),(\d+)"'
                  r'(?:\s+x-confidence="(\d+)")?>([^<]*)</WORD>')


def xml_for(identifier):
    """The cached _djvu.xml for this item, found through the meta sidecars."""
    import json
    for meta in sorted(RAW.glob("*.meta.json")):
        try:
            url = json.loads(meta.read_text(encoding="utf-8")).get("url", "")
        except Exception:
            continue
        if url.endswith(f"{identifier}_djvu.xml"):
            body = meta.with_name(meta.name[: -len(".meta.json")])
            if body.exists():
                return body
    sys.exit(f"no cached _djvu.xml for {identifier}; unh_survey.py --get fetches it")


def pages(path):
    """Yield (page_number, [(x0, ytop, x1, ybot, conf, text), ...]) in order.

    Streamed a line at a time. The file is 51 MB for one year and there are
    nineteen years of two chambers behind this one, so it is never read whole.
    """
    page, buf = None, []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = PAGE.search(line)
            if m:
                if page is not None:
                    yield page, buf
                page, buf = int(m.group(1)), []
            for w in WORD.finditer(line):
                x0, ybot, x1, ytop, conf, text = w.groups()
                if text.strip():
                    buf.append((int(x0), int(ytop), int(x1), int(ybot),
                                int(conf) if conf else None, text.strip()))
    if page is not None:
        yield page, buf


def lines_of(words):
    """Words grouped into printed lines, each sorted left to right.

    A new line starts where a word's top edge drops more than half a line
    height below the top of the line being built. Half a line height, rather
    than a fixed number of pixels, because these volumes are scanned at 400
    ppi but not all at the same page size -- page 1 of the 1997 House journal
    is 3382 tall and page 2 is 3461.
    """
    if not words:
        return []
    heights = [w[3] - w[1] for w in words if w[3] > w[1]]
    tol = max(12, (statistics.median(heights) if heights else 40) * 0.6)
    out, cur, top = [], [], None
    for w in sorted(words, key=lambda w: (w[1], w[0])):
        if cur and w[1] - top > tol:
            out.append(sorted(cur, key=lambda w: w[0]))
            cur, top = [], None
        if not cur:
            top = w[1]
        cur.append(w)
    if cur:
        out.append(sorted(cur, key=lambda w: w[0]))
    return out


def render(line):
    """One printed line as text.

    Two spaces where the gap between words is wide enough to be a column
    break rather than a word space, so that the result reads like the flat
    text it replaces and the same extractor can be pointed at either. The
    threshold is relative to the line's own word sizes, not a pixel count.
    """
    if not line:
        return ""
    widths = [(w[2] - w[0]) / max(1, len(w[5])) for w in line if w[5]]
    em = statistics.median(widths) if widths else 20
    parts = [line[0][5]]
    for prev, w in zip(line, line[1:]):
        parts.append("  " if w[0] - prev[2] > em * 1.2 else " ")
        parts.append(w[5])
    return "".join(parts)


def reflow(identifier, out_dir=OUT):
    path = xml_for(identifier)
    OUT.mkdir(parents=True, exist_ok=True)
    dest = Path(out_dir) / f"{identifier}.txt"
    n_pages = n_lines = n_words = 0
    with dest.open("w", encoding="utf-8") as fh:
        for page, words in pages(path):
            n_pages += 1
            n_words += len(words)
            for line in lines_of(words):
                n_lines += 1
                fh.write(render(line) + "\n")
            fh.write("\n")
    # Silence is not success.
    if n_words == 0:
        sys.exit(f"{path} parsed to zero words; nothing was written that is worth keeping")
    print(f"{identifier}: {n_pages:,} pages, {n_lines:,} lines, {n_words:,} words")
    print(f"  -> {dest}  ({dest.stat().st_size:,} bytes)")
    return dest


def one_page(identifier, want):
    path = xml_for(identifier)
    for page, words in pages(path):
        if page == want:
            if not words:
                sys.exit(f"page {want} carries no words at all")
            for line in lines_of(words):
                print(render(line))
            return
    sys.exit(f"page {want} is not in {path}")


def confidence(identifier):
    """What ABBYY thought of its own reading, as a distribution.

    Worth a number because the repair pass that comes next has to decide
    which names to doubt, and the scan says so itself per word.
    """
    path = xml_for(identifier)
    buckets = {}
    total = scored = 0
    for _page, words in pages(path):
        for w in words:
            total += 1
            if w[4] is None:
                continue
            scored += 1
            buckets[w[4] // 10 * 10] = buckets.get(w[4] // 10 * 10, 0) + 1
    if not scored:
        sys.exit("no word carried an x-confidence; nothing to report")
    print(f"{total:,} words, {scored:,} with a confidence\n")
    for lo in sorted(buckets):
        n = buckets[lo]
        print(f"  {lo:>3}-{lo+9:<3} {n:>9,}  {100*n/scored:5.1f}%  "
              + "#" * int(60 * n / max(buckets.values())))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("identifier", help="an Internet Archive item id")
    ap.add_argument("--reflow", action="store_true", help="write the reordered text")
    ap.add_argument("--page", type=int, help="print one page, to read by eye")
    ap.add_argument("--confidence", action="store_true", help="ABBYY's own confidence")
    a = ap.parse_args()

    if a.page:
        one_page(a.identifier, a.page)
    elif a.confidence:
        confidence(a.identifier)
    else:
        reflow(a.identifier)


if __name__ == "__main__":
    main()
