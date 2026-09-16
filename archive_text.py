#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-16.2
"""
The text of every archived bill, read off the pages already on this disk.

    python3 archive_text.py            # what is there, term by term; writes nothing
    python3 archive_text.py --apply    # writes archive_text.json

No network. It reads what fetch_legislation.py has saved under
legislation/<year>/, so it fills in as the lane goes.

WHAT WAS MISSING

bill_text.json holds the text of the current term and nothing else: 2,234
bills of 2025-2026. Every term before it showed a Bill Text tab with nothing
in it, including 2023-2024, whose pages have been on this disk since the
archive path was found on 10 September. The text was fetched, parsed for its
sponsors, and then not shown.

WHAT THIS PRODUCES

The same shape bill_text.json carries -- {term: {bill: {"text": ...}}} -- so
build_site_v2 needs no second reader and bill_text_block() splits the analysis
from the text exactly as it does for the current term. It is merged UNDER
bill_text.json, never over it: where the General Court's own current-session
text exists, that is the better copy.

WHAT THE PAGE IS

An archived page is the bill as introduced, which is not always the bill as
passed. It carries the LSR number, the analysis, and the text with its line
numbers and amendment marks. Nothing here edits that; the flattening is
fetch_legislation's own, the same function its parser reads sponsors through,
so the text on the page is the text the sponsor line was read from.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import fetch_legislation as FL
import text_sponsors as TS

BILLS = Path("data/bills.json")
OUT = Path("archive_text.json")

# WHAT A SHORT PAGE ACTUALLY IS, measured over all 8,348 saved pages rather
# than assumed. Thirteen come to under 600 characters and eleven of them are
# real documents: housekeeping resolutions adopting the chamber's rules, which
# genuinely run to a sentence. 2021 HR 1 is 182 characters and says everything
# it has to say. A cut at 600 threw all eleven away.
#
# Exactly two are stubs, and neither is short by accident: 2011 HB 1 reads
# 'Link to file "HB0001.pdf"' and 2013 HB 1 'For the full text of House Bill
# 1-A, please click on the pdf'. Both are the budget, whose text the archive
# serves as a PDF this site does not fetch. So they are excluded by what they
# say, and the floor is only there to catch an empty page.
LEAST = 100
STUB = re.compile(r"link to file|click on the pdf|please click", re.I)


# Where a line ends on these pages. fetch_legislation.flatten() is right for
# what it does -- it collapses a page to one line so a sponsor regex can run
# across it without caring where the markup broke -- and wrong for this: a
# bill read that way arrives as an unbroken wall of several thousand
# characters, and bill_text_block() cannot find the rule under the analysis
# because the rule is a LINE. So the block tags become newlines first.
BLOCK = re.compile(r"</?(?:p|div|br|tr|h[1-6]|li|table|blockquote)\b[^>]*>",
                   re.I)


def text_of(path, keep_front=False):
    """The text of one saved page with its lines kept, or "" if it is not a bill."""
    html = FL.decode(Path(path).read_bytes())
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = BLOCK.sub("\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = FL._unescape(t)
    # A page saved before 10 September was decoded as UTF-8 on the way in, and
    # the archive's non-breaking spaces became U+FFFD. They were spaces.
    t = t.replace("�", " ")
    # A non-breaking space is a space. The archive uses them for layout, so
    # without this every other line of a bill is a lone U+00A0 and the text
    # arrives double-spaced with an invisible character on the blank lines.
    t = t.replace(" ", " ")
    # Spaces collapse; newlines do not, beyond a blank line.
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    if len(t) < LEAST or (len(t) < 400 and STUB.search(t)):
        return ""
    # The caller strips the front matter, because the version is read off it
    # first and this function would have thrown it away.
    return t if keep_front else front_matter_off(t)


# The rule the archive draws under the front matter, as a line of its own.
RULE = re.compile(r"^[-─-╿_=]{5,}$", re.M)


def front_matter_off(t):
    """Start the text where the current session's own text starts.

    AN ARCHIVED PAGE OPENS WITH SOMETHING bill_text.json DOES NOT HAVE: the
    printing header, the session year, the LSR number, the title, the sponsor
    line and the committee, then a rule, and only then ANALYSIS. The current
    session's text begins at ANALYSIS.

    build_site_v2.bill_text_block splits the two apart by looking for the rule
    UNDER the analysis, so given the archive's shape it found the first rule --
    the one over it -- and filed the header as the analysis and the analysis as
    the start of the bill. Both halves were wrong and both looked plausible.

    So the front matter comes off here, where the difference between the two
    sources is known, rather than being taught to a function that should not
    have to know which source it is reading. Nothing is lost: the sponsors and
    the committee are on the page already, from the record rather than from a
    printed line.
    """
    m = RULE.search(t)
    if not m:
        return t
    rest = t[m.end():].lstrip("\n")
    # Only when what follows really is the analysis. A resolution has no
    # analysis and no rule in this position, and a page whose first rule is
    # somewhere else entirely should be left exactly as it was read.
    return rest if re.match(r"(?:[A-Z]+\s+)?ANALYSIS\b", rest) else t


# "HB 1000 - AS INTRODUCED", "SB 12 - AS AMENDED BY THE SENATE", "HB 2-FN-A -
# FINAL VERSION". The archive prints which version of the bill the page is in
# its first line, and that line is part of the front matter this module strips,
# so it is read off before the stripping. Without it every archived bill's text
# was headed VERSION NOT STATED, which the page itself contradicts.
VERSION = re.compile(r"^[A-Z]{2,5}\s*\d+[A-Z\-]*\s*[-–]\s*([A-Z][A-Z .,'-]{3,60})$",
                     re.M)


def version_of(t):
    m = VERSION.search(t[:400])
    if not m:
        return ""
    v = " ".join(m.group(1).split()).strip(" .,-")
    # Title case, because the archive shouts and the site does not.
    return v[:1] + v[1:].lower() if v else ""


def build(bills, have=None):
    """{term: {bill: {"text": ..., "version": ...}}} for every page not covered."""
    pages, strays = TS.saved_pages(bills)
    out, tally = {}, {"pages": 0, "too short": 0, "already covered": 0}
    for term, bid, path in pages:
        tally["pages"] += 1
        if have and (have.get(term) or {}).get(bid, {}).get("text"):
            tally["already covered"] += 1
            continue
        raw = text_of(path, keep_front=True)
        version = version_of(raw)
        body = front_matter_off(raw) if raw else ""
        if not body:
            tally["too short"] += 1
            continue
        out.setdefault(term, {})[bid] = {
            "text": body, "source": "archive page",
            "version": version}
    return out, tally, strays


def merge_into(texts, path=OUT):
    """Give a bill the text of its archived page where nothing else has one.

    NEVER OVER bill_text.json. The current session's own text is the better
    copy -- it is the bill as it now stands rather than as introduced -- so a
    term that has it keeps it. Returns how many bills gained a text.
    """
    p = Path(path)
    if not p.exists():
        return 0
    try:
        extra = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return 0
    n = 0
    for term, rows in extra.items():
        have = texts.setdefault(term, {})
        for bid, rec in rows.items():
            if rec.get("text") and not (have.get(bid) or {}).get("text"):
                have[bid] = rec
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    bills = json.loads(BILLS.read_text(encoding="utf-8"))
    have = json.loads(Path("bill_text.json").read_text(encoding="utf-8")) \
        if Path("bill_text.json").exists() else {}
    got, tally, strays = build(bills, have)
    total = sum(len(v) for v in got.values())
    print(f"{total:,} bills gain their text from the archived page:")
    for term in sorted(got):
        chars = sum(len(r["text"]) for r in got[term].values())
        print(f"  {term}: {len(got[term]):>5,} of {len(bills.get(term) or {}):>5,} bills, "
              f"{chars / 1e6:>5.1f} MB of text")
    for k, v in tally.items():
        print(f"  {v:>7,}  {k}")
    if strays:
        print(f"  {len(strays)} saved pages match no bill of that year")
    # Silence is not success: a run that reads pages and produces nothing has
    # found a parsing problem, not an empty archive.
    if tally["pages"] and not total and not tally["already covered"]:
        print("\nWARNING: pages were read and no text came out of any of them.")
    if a.apply:
        OUT.write_text(json.dumps(got), encoding="utf-8")
        print(f"\nwritten {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
