#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-19.1
"""
What a saved legislation page says: its text, the sponsor, committee, title
and analysis read off it, and the LSR it prints about itself.

    import legislation_text as LT
    LT.parse(LT.decode(path.read_bytes()))   # {"sponsors", "committee", "title", "analysis", "_chars"}
    LT.same_bill(text, rec)                  # True, False, or None where the page prints no LSR
    LT.PAD.match("HB15")                     # the kind and the number, padded as the address wants

No network: it reads pages fetch_legislation.py has already saved under
legislation/<year>/. It was the parsing half of fetch_legislation.py until
19 November 2026, and archive_text, build_data, past_sponsors, referrals and
text_sponsors -- parsers -- imported the fetcher for it (src/fetch/README.md
called that a known wart; reports/refactor/stage0-code.md, section 2). Moved
as it stood; fetch_legislation names every piece as before
(fetch_legislation.parse, .decode, .PAD, ...), and its --parse reads through it.
"""

import re
from html import unescape as _unescape



# A page names its own LSR near the top -- "05-1078 10/09", "89-0002 08" --
# on 268 of the 269 static pages in the sample that print one and on all
# 2,220 pages in bill_text/ that do. A bill carried into its second year
# prints its first year's: 1990 HB33 is LSR 1990-114 in data/bills.json and
# its page says 89-0114.
PAGE_LSR = re.compile(r"(?<![\d/-])(\d\d)-(\d{4})(?![\d/])")


# Padded to four digits, which is what the address wants: HB15 is HB0015.
PAD = re.compile(r"^([A-Z]+)(\d+)$")


def lsr_of(rec):
    """(year, number) of a bill's LSR from data/bills.json, or None."""
    rec = rec or {}
    y, n = str(rec.get("lsr_year") or ""), str(rec.get("lsr_num") or "")
    if not (y.isdigit() and n.isdigit()):
        m = re.match(r"^(\d{4})-(\d+)$", str(rec.get("lsr") or ""))
        if not m:
            return None
        y, n = m.groups()
    return int(y), int(n)


def page_lsr(text):
    """The LSR a page prints about itself, as (two-digit year, number)."""
    m = PAGE_LSR.search(text[:1500])
    return (int(m.group(1)), int(m.group(2))) if m else None


def same_bill(text, rec):
    """True, False, or None where the page prints no LSR to check."""
    got, want = page_lsr(text), lsr_of(rec)
    if not got or not want:
        return None
    yy, num = got
    return num == want[1] and yy in (want[0] % 100, (want[0] - 1) % 100)



# ------------------------------------------------------------------ parsing

def decode(raw):
    """Text of a saved page.

    Bytes that are valid UTF-8 are UTF-8: every pure-ASCII page, the 48 that
    declare it, and every page this script saved in its first days, which it
    decoded on the way in and wrote back out as UTF-8 whatever the page said.
    Anything else is Windows-1252, the superset of the Latin-1 that
    152 of the 297 sample pages declare. The declaration itself is not
    consulted: a page declaring iso-8859-1 that was saved as UTF-8 text
    would have its replacement characters read as three Latin-1 letters
    each, which is how "Sen. Clegg" came out as "ï¿½ï¿½ Sen. Clegg".
    """
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def flatten(html):
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    # Every entity, not five of them. "SCR 1 &#8211; FINAL VERSION" and the
    # box-drawing rule "&#9472;&#9472;..." the modern page draws under the
    # committee were arriving as text, and the rule was landing inside the
    # committee's name. 268 of 297 pages carry an entity of some kind.
    t = _unescape(t)
    # The pages saved in this script's first days were decoded as UTF-8 on
    # the way in, and the archive's 0xA0 -- a non-breaking space, in the
    # Latin-1 most of it is served as -- became U+FFFD. It was a space; it is
    # one again.
    t = t.replace("\ufffd", " ")
    return re.sub(r"\s+", " ", t).strip()


# READ OFF THE PAGES, NOT IMAGINED. The first version of this anchored
# everything on "AN ACT", which is what a bill says and what nothing else
# does, so every resolution in the sample yielded a sponsor and no committee
# and no title. Three shapes, from the sample:
#
#   a bill        INTRODUCED BY: ... REFERRED TO: ... AN ACT <title>.
#   a CACR        INTRODUCED BY: ... REFERRED TO: ... RELATING TO: <subject>
#                 PROVIDING THAT: <what it does>
#   a resolution  HOUSE RESOLUTION NO. 1  RESOLVED, that ...
#
# The third has no sponsor and no committee because a House resolution has
# neither. That is the document, not a gap in the parser, and it is recorded
# as such rather than counted as a failure.
#
# STOP is every heading that can follow the one being read. Anchoring on one
# of them is what broke this the first time.
# Where a captured field ends: the label of the next field, or the head of
# the document proper. Each entry past the first line was added because a
# page needed it. "AMENDED ANALYSIS" follows an amended bill's committee;
# "STATE OF NEW HAMPSHIRE", the session line and the LSR number ("19-0789
# 11/06") are what follows a COMMITTEE: that names nobody, and without them
# the capture ran on into the bill.
STOP = (r"(?:REFERRED TO|AN ACT|AN ORDER|AN ADDRESS|A RESOLUTION|JOINT RESOLUTION|"
        r"CONCURRENT RESOLUTION|RELATING TO|PROVIDING THAT|RESOLVED|"
        r"AMENDED ANALYSIS|ANALYSIS|STATEMENT OF INTENT|STATE OF NEW HAMPSHIRE|"
        r"COMMITTEE:|SPONSORS?:|\d{4} SESSION|\d\d-\d{4}\s+\d\d\b)")
# A field begins with a letter (or the "[committee]" placeholder, dropped by
# clean) and not with the next label. "COMMITTEE: 2002 SESSION 02-2470" and
# "COMMITTEE: ANALYSIS This senate bill..." are a committee left blank, and
# both read as one before this.
BEGIN = r"(?!" + STOP + r")(?=[A-Za-z\[])"

# The labels are upper-case, and the field begins after the tab that follows
# them. Matching them case-blind let "COMMITTEE" find the word inside "AN ACT
# establishing a committee to study..." and report the bill's own study
# committee as the one it was referred to, and find "committees of the senate"
# and report "s of the senate". Upper case is what rules that out. The colon is
# not, and SPONSOR_RE says why.
SPONSOR_RE = [
    re.compile(r"INTRODUCED BY:\s*(.+?)\s*" + STOP),
    # THE COLON IS NOT THE ANCHOR. Two of the 7,761 saved pages mistype it, and
    # both print a sponsor that was read as none. From the bytes, not inferred:
    #
    #   2020 SB 222   "SPONSORS\tSen. Rosenwald, Dist 13; ..."   no colon
    #   2022 HB 52    "SPONSORSF\tRep. B. Griffin, Hills. 6"     an F for it
    #
    # That is what the General Court's own document says; the other 7,678 say
    # "SPONSORS:". What all of them share is the upper-case word and the tab the
    # field begins after, so the separator may be a colon, a single stray
    # upper-case letter, or nothing at all, and the whitespace is what is
    # required -- it is also what stops the word running into the name.
    re.compile(r"SPONSORS?(?::|[A-Z])?\s+(.+?)\s*" + STOP),
]
COMMITTEE_RE = [
    re.compile(r"REFERRED TO:\s*" + BEGIN + r"(.+?)\s*" + STOP),
    re.compile(r"COMMITTEE:\s*" + BEGIN + r"(.+?)\s*" + STOP),
]
TITLE_RE = [
    # The opener is upper-case and the title after it lower-case, on every
    # page read: "AN ACT relative to term limits", "A RESOLUTION affirming
    # revenue estimates", "JOINT RESOLUTION supporting the improvement of
    # primary health care delivery" (1993, no article), "AN ORDER relative to
    # implementing an election" (a House concurrent order). Only AN ACT was
    # known before the sample: 94 pages open that way, 93 with CONCURRENT
    # RESOLUTION, 40 with JOINT RESOLUTION, 29 with A RESOLUTION. This is
    # case-sensitive, and the look-ahead for a lower-case letter is what
    # keeps the header "HOUSE CONCURRENT RESOLUTION 6" from being the title.
    # A House address ("AN ADDRESS for the removal of ... from his said
    # office") is the seventh opener. The full stop that ends a title is
    # not one after an initial or "St", "Mt", "Dr", "Jr", "No", "Inc":
    # "naming the Kenneth M. Tarr Highway" was ending at "Kenneth M".
    re.compile(r"\b(?:AN ACT|AN ORDER|AN ADDRESS|(?:A |AN )?(?:JOINT |CONCURRENT )?RESOLUTION)"
               r"\s+(?=[a-z])(.+?)(?:\s+SPONSORS?:|\s+COMMITTEE:|\s+ANALYSIS\b|"
               r"(?<![A-Z])(?<!\bSt)(?<!\bMt)(?<!\bDr)(?<!\bJr)(?<!\bNo)(?<!\bInc)\.\s)"),
    # A CACR states a subject and then what it would do. Both are the title.
    # In 1989 the sponsor and committee came before RELATING TO and the
    # analysis after; by 2009 SPONSORS: and COMMITTEE: follow it, and a
    # capture that ran on to ANALYSIS swallowed both, exceeded the cap, and
    # left the title to the RESOLVED clause -- "be amended as follows: I".
    re.compile(r"RELATING TO:?\s*(.+?)\s*(?:SPONSORS?:|COMMITTEE:|ANALYSIS|"
               r"EXPLANATION|STATEMENT OF INTENT|$)", re.I),
    re.compile(r"RESOLVED,?\s*(.+?)(?:\.\s|$)", re.I),
]
# A bill of intent (HBI, 1989-1994) carries a STATEMENT OF INTENT where a bill
# carries an ANALYSIS. The modern page ends its analysis with a rule of dashes
# and then the LSR number; the old one with EXPLANATION.
ANALYSIS_RE = re.compile(
    r"\b(?:ANALYSIS|STATEMENT OF INTENT)\b\s*(.+?)"
    r"(?=\s*(?:EXPLANATION\b|(?:-\s*){5,}|\u2500{5,}|STATE OF NEW HAMPSHIRE|"
    r"\d\d-\d{4}\s+\d\d\b)|$)", re.I)


def clean(s):
    """A captured field without the rule drawn after it.

    The modern page draws a line -- ASCII dashes on some pages, box-drawing
    characters on others -- between the committee and the analysis, and it
    was arriving inside the committee's name. "[committee]" is the template's
    placeholder for a committee never filled in, and is no committee.
    """
    s = re.sub(r"^[\s:;.\-\u2500-\u257f]+|[\s:;.\-\u2500-\u257f]+$", "", s)
    return "" if re.fullmatch(r"\[.*\]", s) else s

# NO SUCH RULE. There was one here -- NO_SPONSOR_KINDS = {"HR", "SR"} -- on
# the grounds that a simple resolution of one chamber names no sponsor and is
# referred to nobody. Four pages supported it. All four were from 1991-1994,
# because that is as far as the sample had fetched, and a modern House
# resolution does have sponsors and does get referred to a committee.
#
# So it was never a fact about the kind. It was a fact about the era, stated
# as a fact about the kind, from the only pages that had arrived yet -- which
# is this project's oldest failure wearing new clothes: a rule generalised
# from the subset that happened to be on disk.
#
# What replaces it is not a better rule but no rule. The report crosses kind
# with era and prints what was found, so "HR carries no sponsor before the
# mid-nineties and carries one after" is something a reader sees in the
# numbers rather than something this file asserts.


def parse(html):
    flat = flatten(html)
    got = {}
    # The cap on a sponsor list was 400 characters. Six pages exceed it --
    # SB 1 of 1995 names 21 sponsors in 478 -- and every one of the six was
    # reported as having no sponsor at all. 2,500 is room for a budget
    # trailer's forty-odd names; STOP is what keeps a runaway capture short.
    for rx in SPONSOR_RE:
        m = rx.search(flat)
        if m and len(m.group(1)) < 2500 and clean(m.group(1)):
            got["sponsors"] = clean(m.group(1))
            break
    for rx in COMMITTEE_RE:
        m = rx.search(flat)
        if m and len(m.group(1)) < 120 and clean(m.group(1)):
            got["committee"] = clean(m.group(1))
            break
    for rx in TITLE_RE:
        m = rx.search(flat)
        if m and 3 < len(m.group(1)) < 400:
            got["title"] = m.group(1).strip(" .,")
            break
    m = ANALYSIS_RE.search(flat)
    if m:
        got["analysis"] = m.group(1).strip()[:600]
    got["_chars"] = len(flat)
    return got
