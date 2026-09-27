#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-16.5
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

WHERE THE PAGE IS NOT THE VERSION IT SAYS IT IS

Twenty-three pages of 2018 print VERSION ADOPTED BY BOTH BODIES over an
earlier printing. Those bills take the final version's text from the General
Court's own copy of every printing, db/past/PastLegislationText.jsonl, which
fetch_past_db.py dumps; FINAL_FROM_DB says which bills and how that was
measured. The file is read where it is on this disk and not otherwise, and
GitHub's nightly is not given it (cloud_kit.json), so a build there keeps the
page's text for those bills and says so.
"""

import argparse
import difflib
import json
import re
import sys
from collections import Counter
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


# WHAT A BROWSER NEVER SHOWS, and this used to print as the bill. A page Word
# saved as HTML carries the document's properties in its head, inside a
# comment only Office reads:
#
#     <!--[if gte mso 9]><xml> <o:DocumentProperties>
#       <o:Author>Fowler_E</o:Author> <o:Created>2004-12-28T20:07:00Z</o:Created>
#       ... <w:BrowserLevel>MicrosoftInternetExplorer4</w:BrowserLevel>
#
# Stripping tags left the values, so 2005, 2007, 2009, 2011 and 2013 HR 1 and
# 2009 HR 2 -- resolutions, which have no analysis for front_matter_off to cut
# at -- opened with a staff username, two edit timestamps and a word count as
# though the House had adopted them. A comment is removed whole, <xml> too
# where one stands outside a comment. Word's OTHER conditional,
# <![if !supportLists]>1.<![endif]>, is not a comment: it is how the page
# shows a list's numbers to every browser, so its tags go and its text stays.
COMMENT = re.compile(r"<!--.*?-->", re.S)
XML = re.compile(r"<xml\b.*?</xml\s*>", re.S | re.I)

# A TAG BETWEEN A WORD AND ITS PUNCTUATION IS NOT A SPACE. Every inline tag
# became one, so "elections are made<B><I>, except as provided in article
# 68-a</I></B>." -- the bold italics of an amendment -- read "made , except
# as provided in article 68-a ." across 166,075 places in the archive. Where
# the tags are the ONLY thing between a character and a closing punctuation
# mark they go with nothing in their place; everywhere else a tag is still a
# space, because a tag between two words may be the only thing keeping them
# apart and joining them would print a word nobody wrote. A space the page
# itself put before the mark is left alone: the lookbehind wants a character,
# not a space and not the end of another tag.
TAG_BEFORE_MARK = re.compile(r"(?<=[^\s>])(?:<[^>]+>)+(?=[,.;:!?)\]])")

# The Basic Multilingual Plane's private-use area and planes 15-16.
PRIVATE = re.compile("[-\U000f0000-\U0010ffff]")


def text_of(path, keep_front=False):
    """The text of one saved page with its lines kept, or "" if it is not a bill."""
    t = flatten(FL.decode(Path(path).read_bytes()))
    if len(t) < LEAST or (len(t) < 400 and STUB.search(t)):
        return ""
    # The caller strips the front matter, because the version is read off it
    # first and this function would have thrown it away.
    return t if keep_front else front_matter_off(t)


def flatten(html):
    """A bill's HTML as the text a browser shows, its lines kept, front matter
    and all. A saved page goes through it, and so does the HTML of a printing
    in the General Court's database, so that when the two are compared a
    difference is the bill's and never this function's."""
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    # "<!>", not "": a comment between two words is still between them, and
    # the tag rules below decide what it becomes like any other tag.
    t = COMMENT.sub("<!>", t)
    t = XML.sub("<!>", t)
    t = BLOCK.sub("\n", t)
    t = TAG_BEFORE_MARK.sub("", t)
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
    return re.sub(r"\n{3,}", "\n\n", t).strip()


# The rule the archive draws under the front matter, as a line of its own.
RULE = re.compile(r"^[-─-╿_=]{5,}$", re.M)

# The analysis's own label. ANALYSIS, AMENDED ANALYSIS, or the STATEMENT OF
# INTENT a bill of intent carries instead -- the same pair fetch_legislation's
# ANALYSIS_RE reads. _LINE wants it alone on its line, which is how the label
# is printed and is what makes it a boundary; _LABEL only wants the text to
# begin with it, which is what the rule branch above asks.
ANALYSIS_LINE = re.compile(
    r"^(?:[A-Z]+[ \t]+)?(?:ANALYSIS|STATEMENT OF INTENT)[ \t]*$", re.M)
ANALYSIS_LABEL = re.compile(r"(?:[A-Z]+\s+)?(?:ANALYSIS|STATEMENT OF INTENT)\b")


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
    if m:
        rest = t[m.end():].lstrip("\n")
        # Only when what follows really is the analysis. A resolution has no
        # analysis and no rule in this position.
        if ANALYSIS_LABEL.match(rest):
            return rest
    # NO RULE IS DRAWN ABOVE THE ANALYSIS BEFORE ABOUT 2015, and that is the
    # whole of the defect this branch exists for. The archive of the older
    # terms separates its sections with blank lines and nothing else, so
    # RULE.search found nothing, this function returned the text unchanged,
    # and every page kept its printing header -- 0 of 8,853 pages of 1989-1999
    # were stripped, and 21,914 of the 29,346 on disk overall. build_site_v2
    # then cut the analysis at the enacting clause, so the header, the title,
    # the sponsor line and the committee were all published as though the
    # drafters had written them as the bill's summary. Reported by the person
    # on 19 September, against 1990s bills.
    #
    # So when there is no rule, the label itself is the boundary. It is a line
    # of its own -- "ANALYSIS", "AMENDED ANALYSIS", or "STATEMENT OF INTENT"
    # on a bill of intent -- and the first one on the page is the header's,
    # because the header is what comes before it. The label is KEPT at the
    # start: build_site_v2.bill_text_block strips it, and a page that arrived
    # without it would have its first sentence eaten instead.
    #
    # Still nothing when there is no label. A resolution carries no analysis,
    # and a page this cannot find one on is left exactly as it was read
    # rather than cut at a guess.
    m = ANALYSIS_LINE.search(t)
    return t[m.start():] if m else t


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


# WHERE THE PAGE IS NOT THE VERSION IT SAYS IT IS (27 September 2026).
#
# Twenty-three bills of 2018 print "VERSION ADOPTED BY BOTH BODIES" over an
# earlier printing -- the House's or the Senate's amended text, or a committee
# of conference's -- without the enrolled bill amendment of 23 May 2018 that
# the version adopted by both bodies carries. The enacted numbers come from
# that amendment: SB 421's page inserts an RSA 415:6-v where chapter 361
# enacted 415:6-w, and HB 1356's an RSA 126-A:75 enacted as 126-A:76. HB 1418
# and HB 1819 are the Senate's amended printing word for word, and SB 421 the
# House's.
#
# The General Court's database holds every printing of a past bill, each with
# a VersionID from PublicNHLMS.DocumentVersion (db/DocumentVersion.psv): 13 and
# 14 are the Senate's and the House's "Version adopted by both bodies", sort
# order 70, and 48, 52 and 53 the three CHAPTERED FINAL VERSIONs, 120, the law
# as enacted. For each of the 23 the view's version adopted by both bodies
# prints the bill's own LSR and title, and is at least as near the chaptered
# law as the page is. final_versions() is the rule, and in 2018 it takes those
# 23 and no other bill. Of the other 245 pages carrying the label, 223 are that
# printing word for word, and 22 -- bills of 2017 carried into 2018, whose
# pages print a 17- LSR -- have no printing in the view to be measured against,
# so they keep their pages.
#
# ONLY 2018, BY MEASUREMENT. Every page of 2016-2024 the site shows as a final
# version was set against the view on 27 September. Elsewhere such a page is,
# to within a stray word or line, the chaptered law or the version adopted by
# both bodies, once what the page adds -- a governor's veto or approval note, a
# fiscal note -- and the chapter's own section numbers, "224:1" for "1", are
# set aside. The exceptions are
# fifteen vetoed bills of 2019-2024, with no chapter to measure against, whose
# page and view differ by a word or two in either direction: 2024 SB 543's
# page carries an enrolled bill amendment that its copy in the view lacks. So
# nothing outside this tuple changes; a session joins it after the same
# measurement and not before.
PAST_TEXT = Path("db/past/PastLegislationText.jsonl")
FINAL_FROM_DB = ("2018",)
ADOPTED = "Version adopted by both bodies"   # version_of()'s spelling of it
BOTH_BODIES = (13, 14)
CHAPTERED = (48, 52, 53)
NO_PRINTING = "not one printing adopted by both bodies under its LSR"

# A word, for comparing two printings: letters and digits, with the hyphens,
# colons and stops inside a citation kept, so "415:6-v" and "415:6-w" are two
# words and not one. Spacing and punctuation are how a copy was read rather
# than what the bill says, and a rule of dashes is no word at all.
WORD = re.compile(r"[A-Za-z0-9]+(?:[-:.,'/][A-Za-z0-9]+)*")

# What a page carries under the bill's last section and the database's copy
# does not: "VETOED: May 29, 2018", "Veto Sustained September 25, 2019".
VETO = re.compile(r"^(?:VETOED|Vetoed|Veto\s+(?:Sustained|Overridden)|SUSTAINED|"
                  r"OVERRIDDEN)\b.*$", re.M)
# Where a fiscal note starts in the view's text: "LBAO" or "LBA" on its own line.
FISCAL_HEAD = re.compile(r"^LBAO?$", re.M)


def words(t):
    return WORD.findall(t or "")


def text_column(t):
    """The view's plain text, set out the way flatten() sets out a page.

    From 2016 on the text column keeps the real characters, and it has no tag
    in the middle of a word: 2018 HB 1785's HTML reads "RS A" where its text
    reads "RSA". So it is the copy that is shown, and the HTML only what a
    page is compared with."""
    t = (t or "").replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    t = re.sub(r"[ \t\f\v]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def with_veto_note(text, page):
    """`text` with the veto note `page` carries, where the page puts it: under
    the bill's last section, before any fiscal note."""
    notes = [m.group(0) for m in VETO.finditer(page) if m.group(0) not in text]
    if not notes:
        return text
    note = "\n\n".join(notes)
    m = FISCAL_HEAD.search(text)
    if m:
        return f"{text[:m.start()].rstrip()}\n\n{note}\n\n{text[m.start():]}"
    return f"{text.rstrip()}\n\n{note}"


def past_rows(keys, path=PAST_TEXT):
    """{(sessionyear, lsr): [row]} of the view's printings adopted by both
    bodies and chaptered, for `keys`, in one pass over a gigabyte. A line is
    parsed only where it holds one of the wanted years' digits, which every row
    of that year does in its sessionyear and its legislationID: the test lets
    through rows that are not wanted and keeps out none that are."""
    years = {str(y) for y, _ in keys}
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not any(y in line for y in years):
                continue
            r = json.loads(line)
            try:
                key = (int(r.get("sessionyear")), int(r.get("lsr")))
                vid = int(r.get("VersionID"))
            except (TypeError, ValueError):
                continue
            if key in keys and vid in BOTH_BODIES + CHAPTERED:
                out.setdefault(key, []).append({**r, "VersionID": vid})
    return out


def _plain(s):
    return " ".join(re.findall(r"[a-z0-9]+", (s or "").lower()))


def _bill(s):
    m = re.match(r"^([A-Z]+)0*(\d+)$", re.sub(r"\s+", "", (s or "").upper()))
    return f"{m.group(1)}{int(m.group(2))}" if m else ""


def final_versions(cands, bills, path=PAST_TEXT):
    """({(term, bill): the fields that replace the page's}, Counter of why every
    other candidate keeps its page).

    `cands` is [(term, bill, the page's text as front_matter_off leaves it)],
    the pages of FINAL_FROM_DB labelled ADOPTED. A page gives way to the view's
    printing adopted by both bodies when all of these hold:

      - the view has exactly one such printing under the bill's STORED LSR,
        sessionyear and lsr against lsr_year and lsr_num, the join
        past_sponsors makes;
      - its words are not the page's, both read through flatten(), so the
        difference is in the bill and not in how either copy was read;
      - it is filed under the bill's number and prints the bill's LSR and
        title, so it is this bill's;
      - the view has the chaptered law, and the printing is at least as near
        it as the page is.

    What is shown then is that printing's text column, with any veto note the
    page carries. The page's label for the version stays.
    """
    why, keys = Counter(), {}
    for term, bid, _ in cands:
        rec = (bills.get(term) or {}).get(bid) or {}
        try:
            keys[(term, bid)] = (int(rec["lsr_year"]), int(rec["lsr_num"]))
        except (KeyError, TypeError, ValueError):
            why["no stored LSR"] += 1
    rows = past_rows(set(keys.values()), path)
    out = {}
    for term, bid, page in cands:
        if (term, bid) not in keys:
            continue
        year, lsr = keys[(term, bid)]
        mine = rows.get((year, lsr), [])
        final = [r for r in mine if r["VersionID"] in BOTH_BODIES]
        law = [r for r in mine if r["VersionID"] in CHAPTERED]
        if len(final) != 1:
            why[NO_PRINTING] += 1
            continue
        f = final[0]
        theirs, ours = (words(front_matter_off(flatten(f.get("html") or ""))),
                        words(page))
        if theirs == ours:
            why["the page is that printing word for word"] += 1
            continue
        text = text_column(f.get("text"))
        title = re.sub(r"\(\s*(?:\w+\s+)?new\s+title\s*\)", " ",
                       bills[term][bid].get("title") or "", flags=re.I)
        if (_bill(f.get("BillNbr")) != bid
                or not re.search(rf"(?<![\d/-]){year % 100:02d}-{lsr:04d}(?![\d/])",
                                 text[:3000])
                or not _plain(title) or _plain(title) not in _plain(text[:4000])):
            why["the printing does not print this bill's number, LSR and title"] += 1
            continue
        if not law:
            why["no chaptered law to measure the two against"] += 1
            continue
        enacted = words(front_matter_off(flatten(law[0].get("html") or "")))

        def near(a):
            return difflib.SequenceMatcher(None, a, enacted, autojunk=False).ratio()

        if near(theirs) < near(ours):
            why["the page is the nearer of the two to the chaptered law"] += 1
            continue
        out[(term, bid)] = {
            "text": with_veto_note(front_matter_off(text), page),
            "source": f"PastLegislationText {f.get('id')}"}
    return out, why


def build(bills, have=None, past=PAST_TEXT):
    """{term: {bill: {"text": ..., "version": ...}}} for every page not covered."""
    pages, strays = TS.saved_pages(bills)
    out, tally = {}, {"pages": 0, "too short": 0, "already covered": 0}
    cands = []
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
        if path.parent.name in FINAL_FROM_DB and version == ADOPTED:
            cands.append((term, bid, body))
    if cands and not Path(past).exists():
        tally[f"labelled {ADOPTED.lower()} in {', '.join(FINAL_FROM_DB)} and not "
              f"checked: {past} is not here"] = len(cands)
    elif cands:
        got, why = final_versions(cands, bills, past)
        for (term, bid), fields in got.items():
            out[term][bid].update(fields)
        tally["the final version from the General Court's database, the page "
              "being an earlier printing"] = len(got)
        for k, n in why.most_common():
            tally[f"labelled {ADOPTED.lower()} and kept: {k}"] = n
        # Silence is not success: a view read whole in which no page finds its
        # printing is a file whose shape changed, not 2018's bills.
        if why[NO_PRINTING] == len(cands):
            tally[f"WARNING: {past} was read and not one of these found its "
                  "printing in it"] = len(cands)
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
    for term in sorted(got):
        db = [b for b, r in got[term].items()
              if r.get("source", "").startswith("PastLegislationText")]
        if db:
            print(f"  {term}, the final version from the database: {', '.join(db)}")
    if strays:
        print(f"  {len(strays)} saved pages match no bill of that year")
    # Counted and LEFT AS THEY ARE. A private-use code point is a character a
    # font on the drafter's machine drew -- a Wingdings bullet, a symbol from
    # a table -- and nothing says which; replacing it would be a guess printed
    # as the General Court's text. So it is reported, for a person to read.
    pua = [(t, b, len(PRIVATE.findall(r["text"])))
           for t in sorted(got) for b, r in sorted(got[t].items())
           if PRIVATE.search(r["text"])]
    if pua:
        print(f"  {sum(n for *_, n in pua):,} private-use characters, left as "
              f"the page has them, in {len(pua)} texts: "
              + ", ".join(f"{t[:4]} {b} ({n})" for t, b, n in pua[:8])
              + (" ..." if len(pua) > 8 else ""))
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
