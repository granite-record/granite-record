#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.174
"""
Generate the faceted site from real General Court data.

    python3 src/pages/build_site_v2.py --data data --out site

Reads (all optional except data/):
    data/*.json              from build_data.py
    narratives.json          from narrative.py --all
    rollcalls.json           from rollcall_parser.py --all
    verification_manifest.csv  from build_manifest.py
    segments/<videoid>.json  from transcribe_and_align.py
    committee_reports.json   from fetch_committee_reports.py

Design note: 131,199 member votes are far too much to ship to a browser at
once, so this writes a small search index plus one JSON file per bill. The
index drives search and the facets; a bill's votes, sponsors and hearings load
only when that bill is expanded. Initial load stays a few hundred KB no matter
how many roll calls a session produced.

Standard library only.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import build_date
import caption_span
import committee_names as CN
# Where the recordings this site links begin: one constant, which about.html
# states in words and station_for_proceeding and station_for_floor split on.
from about_figures import STREAM_START
import narrative as N
import fiscal
import proceedings as P
import report_check as RC
import senate_hearing_reports as SHR
import site_read
import csv
import json
import member_links as ML
import names
import re
import archive_text as AT
import ballot_source as BS
import bill_order as BO
import past_sponsors as PSP
import text_sponsors as TS
import topic_model as TM
import unicodedata
from collections import Counter, defaultdict, namedtuple
from datetime import date as _date, timedelta as _td

STATUS_ORDER = ["law", "veto", "done", "active"]


def load(p, default):
    p = Path(p)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default



# Sign-ins are filed for a public hearing, so the count belongs on that line.
PUBLIC_HEARING = re.compile(r"public hearing", re.I)


AMEND_NUM = re.compile(r"#\s*(\d{4}-\d+[a-z]?)", re.I)
AMEND_ANY = re.compile(r"\b(\d{4}-\d{3,4}[a-z]?)\b")
# AA is adopted, AF and AL are not. The docket's own abbreviations.
#
# AND "FAILED" SPELLED OUT, which was the missing half of a pair. The docket
# writes the outcome either way -- "AA" or "Adopted", "AF" or "Failed" -- and
# this map took three of the four. So 153 amendment events whose docket line
# says plainly that they failed were published with no outcome at all:
# 2007-2008 SB27 reads "Floor Amendment #2071h (Rep P. Preston, et al) Failed,
# RC 131-221" and the page declined to say it failed.
#
# A missing key here is silent. ADOPTED.get returns None, which the page reads
# as "the record does not say" and draws no chip -- indistinguishable from the
# 598 amendments that really were only filed and never voted on. That is the
# failure mode worth naming: an absent mapping does not error, it publishes a
# claim of ignorance the record contradicts.
#
# Only FAILED is added, because only FAILED occurs. Counted over all 19,105
# amendment events in narratives.json, the motion field holds exactly AA
# (12,249), ADOPTED (4,583), AF (997), AL (48), FAILED (153) and blank (1,075).
# LOST and WITHDRAWN appear in docket PROSE but never in this field, so adding
# them would be guessing at data rather than reading it.
ADOPTED = {"AA": True, "ADOPTED": True,
           "AF": False, "AL": False, "FAILED": False}


# What an amendment says it changes. New Hampshire amendments are written as
# instructions rather than as a redline: "Amend RSA 415:6-e, III(a) as inserted
# by section 1 of the bill by replacing it with the following". So the targets
# can be read off the instruction, and two amendments touching the same target
# is the case where the later one governs.
# The same widening as RSA_CITE below, and for the same reason: a two-letter
# chapter (126-AA) and a hyphenated or dotted section (6-602, 10.01) are real
# addresses, and this pattern dropped an amendment's target entirely when it met
# one -- so the Changes row silently lost the statute the bill actually amends.
RSA_CITE_T = re.compile(
    r"\bRSA\s+(\d{1,3}(?:-[A-Z]{1,2})?:\d{1,4}(?:-[a-z0-9]{1,3})?(?:\.\d{1,2})?"
    r"(?:,\s*[IVXLC]+(?:-[a-z])?)?(?:\([a-z]\))?)(?!\d)", re.I)
# Where the instruction stops and the new text begins. Everything after this is
# what the amendment INSERTS, and the statutes quoted in there are not the ones
# it changes -- an amendment replacing one paragraph may quote a dozen others
# around it.
PREAMBLE_END = re.compile(
    r"with the following|to read as follows|as follows\s*:", re.I)
TARGET_SECT = re.compile(
    r"\b(?:replacing|inserting after|deleting|amending)\s+section\s+(\d+)", re.I)
TARGET_ALL = re.compile(r"replacing all after the enacting clause", re.I)


def amendment_targets(text):
    """The parts of the bill or the statutes an amendment says it changes."""
    if not text:
        return []
    out = []
    if TARGET_ALL.search(text):
        out.append("the whole bill")
    # Only the instruction, so "Amend RSA 91-A:4 and RSA 91-A:1-a" gives both
    # and the statutes quoted in the replacement text give none.
    stop = PREAMBLE_END.search(text)
    head = text[:stop.start()] if stop else text[:400]
    if re.search(r"\bAmend\b", head, re.I):
        for m in RSA_CITE_T.finditer(head):
            v = "RSA " + re.sub(r"\s+", " ", m.group(1)).strip()
            if v not in out:
                out.append(v)
    for m in TARGET_SECT.finditer(text):
        v = f"section {m.group(1)}"
        if v not in out:
            out.append(v)
    return out[:8]


# The General Court prints an ANALYSIS above the bill: a plain-language
# summary written by the people who drafted it. Splitting it off means the
# reader meets that before several thousand words of statute -- and it is the
# drafters' own summary, not this site's, which makes it worth more.
ENACTING = re.compile(
    r"^\s*(?:Be it Enacted|That the following|Whereas\b|RESOLVED\b)", re.M | re.I)
# The General Court prints a rule of spaced dashes between the analysis and the
# bill's front matter. Read as text it is a line of "- - - - - -", and it ended
# up inside the analysis along with everything after it.
DASH_RULE = re.compile(r"^[\s\-\u2013\u2014_=]{10,}$", re.M)
# The drafting legend, which describes formatting the reader cannot see here.
# We say the same thing in our own words next to the text, so printing theirs
# as though it were the bill's summary is both wrong and confusing.
LEGEND = re.compile(
    r"(?:Matter (?:removed|added|which is)[^\n]*|Explanation:[^\n]*|"
    r"\[?in brackets and struck ?through[^\n]*)", re.I)
# "26-2608 07/06", "STATE OF NEW HAMPSHIRE", "In the Year of Our Lord ...",
# "AN ACT ..." -- the bill's formal opening. It belongs with the bill, not with
# the summary of it.
FRONT = re.compile(
    r"^\s*(?:\d{2}-\d{3,4}(?:\s+\d{2}/\d{2})?|STATE OF NEW HAMPSHIRE|"
    r"In the Year of Our Lord[^\n]*|AN ACT\b[^\n]*|A RESOLUTION\b[^\n]*|"
    r"CACR\s*\d+[^\n]*)\s*$", re.M | re.I)
# "Explanation: Matter added to current law appears in bold italics." The
# General Court says this on the page, and it is true of the PDF and false of
# the text, because bold and italic do not survive extraction.
EXPLANATION = re.compile(r"^\s*Explanation:.*$", re.M | re.I)


def bill_text_block(rec):
    """The analysis and the text itself, told apart."""
    if not rec:
        return None
    body = rec.get("text") or ""
    if not body:
        return None
    cut = ENACTING.search(body)
    analysis = body[:cut.start()] if cut else ""
    rest = body[cut.start():] if cut else body
    # The analysis is what sits between its heading and the rule under it.
    # Everything after that rule -- the drafting legend, the LSR number, the
    # formal opening -- is the bill's own front matter and was being printed as
    # though the drafters had written it as a summary.
    rule = DASH_RULE.search(analysis)
    if rule:
        front = analysis[rule.end():]
        analysis = analysis[:rule.start()]
        rest = (FRONT.sub("", LEGEND.sub("", front)).strip() + "\n" + rest).strip()
    analysis = LEGEND.sub("", EXPLANATION.sub("", analysis)).strip()
    # "ANALYSIS" or "AMENDED ANALYSIS", and any rule printed above it.
    analysis = re.sub(r"^[\s\u2500-\u257F_=-]*(?:[A-Z]+\s+)?ANALYSIS\s*", "",
                      analysis, flags=re.I).strip()
    # The fiscal note is a table, flattened to one column by the PDF
    # extraction. Taken out of the body so it can be drawn as a table and
    # not printed twice.
    note, rest = fiscal.parse(rest)
    return {"version": rec.get("version") or "",
            "title": rec.get("title") or "",
            "analysis": analysis,
            **({"fiscal": note} if note else {}),
            "body": rest.strip(),
            "in_text": rec.get("amendments_in_text") or [],
            "chars": len(body)}


def amended_bill(s):
    """'HB 614-FN' -> 'HB614', 'SSHB1' -> 'HB1': near enough to compare the
    bill an amendment's heading names with the bill it is shown on, a Senate
    substitute amending the bill it substitutes for. extract_amendments.
    plain_bill writes the headings the same way."""
    m = re.match(r"(?:SS)?([A-Z]+)[ \t]*0*(\d+)", (s or "").upper().strip())
    return f"{m.group(1)}{int(m.group(2))}" if m else ""


def amendment_num(e):
    """The amendment number a docket event moves, or ''."""
    num = (e.get("amendment") or "").strip()
    if not num:
        m = AMEND_NUM.search(e.get("raw", "")) or AMEND_ANY.search(e.get("raw", ""))
        num = m.group(1) if m else ""
    return num


def amendment_claims(narratives):
    """{term: {amendment number: {bills whose docket names it}}}: in any line,
    since a committee's report names the amendment it recommends before any
    line moves it -- "Ought to Pass with Amendment #2022-0996h" on HB 1347."""
    out = defaultdict(lambda: defaultdict(set))
    for term, byb in (narratives or {}).items():
        if not isinstance(byb, dict):
            continue
        for bid, narr in byb.items():
            for e in (narr or {}).get("events", []):
                nums = set(AMEND_ANY.findall(e.get("raw") or ""))
                if e.get("amendment"):
                    nums.add(e["amendment"].strip())
                for num in nums:
                    out[term][num].add(amended_bill(bid))
    return out


def bill_amendments(narr, texts, claimed=None):
    """Every amendment on one bill, in the order the docket took them up.

    Order is the whole point. A committee amendment is considered before any
    floor amendment, and where two touch the same section the later one wins,
    so a list sorted any other way describes a bill that does not exist. The
    docket is already chronological, so it is simply not re-sorted.

    Text is attached where the calendars had it and left absent where they did
    not. An amendment nobody can read is still an amendment that was moved,
    and dropping it would hide a step rather than a document.

    And left absent where the calendar printed it under ANOTHER bill's
    heading. extract_amendments records the bill named in "Amendment to HB
    1347" above each number, and where that is not this bill the text is
    that bill's: HB 1180's docket of 2022 moves 2022-0996h, which House
    Calendar 10A prints, and the database files, as HB 1347's. It is left off
    -- with its proposer and its calendar -- and the row stays, because the
    docket says the number was moved here.

    `claimed` is the term's {number: {bills whose docket moves it}}, from
    amendment_claims. Given, the heading must name a bill that moves the
    number too, since a calendar also misprints headings: it put 2022-1160h,
    HB 1604's, under "Amendment to HB 1160-FN" -- its own number -- and
    2026-0976h under "HB 16678-FN", which is no bill. Neither is another
    bill's amendment, and neither is left off.
    """
    own = amended_bill((narr or {}).get("bill"))
    out, seen = [], {}
    for e in (narr or {}).get("events", []):
        if e.get("type") != "amendment" or e.get("cancelled"):
            continue
        num = amendment_num(e)
        if not num:
            continue
        # THE ROW THAT DECIDED IT, WHERE THE FIRST ONLY ANNOUNCED IT. The
        # Senate enters a floor amendment twice: "Sen. Birdsell Floor
        # Amendment # 2026-0720s; 02/19/2026" when it is offered, then "...#
        # 2026-0720s, AA, VV" when it carries (HB 266 of 2026, 10:23 and
        # 10:26). In the order the clerk entered them the first has no
        # outcome, and keeping only it dropped "adopted" from three
        # amendments the Senate adopted (HB 266, HB 751 and SB 557 of 2026).
        # The first row keeps its place; a later one fills in the outcome,
        # with its own day, since the day is printed beside it: HB 718 of
        # 2025's 2025-2080s was offered on 15 May and adopted on 5 June.
        if num in seen:
            a = seen[num]
            said = _amendment_said(e)
            if a["adopted"] is None and said is not None:
                a["adopted"] = said
                a["vote_kind"] = a["vote_kind"] or e.get("vote_kind") or ""
                a["mover"] = a["mover"] or e.get("mover") or ""
                a["date"], a["body"] = e.get("date"), e.get("body")
            continue
        kind = (e.get("amend_kind") or "").strip() or "Amendment"
        doc = texts.get(num) or {}
        printed_for = amended_bill(doc.get("heading"))
        if own and printed_for and printed_for != own and (
                claimed is None or printed_for in claimed.get(num, ())):
            doc = {}
        seen[num] = {
            "num": num,
            "kind": kind,
            # Committee or floor is not a label this invents: it is the word
            # the docket line used, and where the line says only "Amendment"
            # that is what the reader is told.
            "where": ("committee" if "committee" in kind.lower()
                      else "floor" if "floor" in kind.lower()
                      else "enrolment" if "enrolled" in kind.lower() else ""),
            "date": e.get("date"), "body": e.get("body"),
            # Not the outcome of a vote the same docket line goes on to
            # undo: HB 375 of 2001's floor amendment 1081 lost 179-181, was
            # reconsidered, and was adopted 180-179, all on one line the
            # history tells question by question. The first carries
            # "decided_again", and the row that decided it again fills the
            # outcome in, as a row does for an amendment only announced.
            "adopted": None if e.get("decided_again") else _amendment_said(e),
            "vote_kind": e.get("vote_kind") or "",
            "mover": e.get("mover") or "",
            "proposed_by": doc.get("proposed_by") or "",
            "text": doc.get("text") or "",
            "source": doc.get("source") or "",
            "targets": amendment_targets(doc.get("text") or ""),
        }
        out.append(seen[num])

    # Where a later amendment touches something an earlier one already
    # touched. That is the case the reader most needs pointed out, because
    # both were adopted and only the later one is in the bill.
    for i, a in enumerate(out):
        clash = []
        for b in out[:i]:
            shared = [x for x in a["targets"] if x in b["targets"]]
            if shared and a.get("adopted") and b.get("adopted"):
                clash.append({"num": b["num"], "shared": shared})
        a["supersedes"] = clash
    return out


def _amendment_said(e):
    """Whether one amendment event says its amendment was adopted (True),
    rejected (False) or neither (None).

    A VOTE ON SOME OF IT SAYS NEITHER. The House divides an amendment and
    votes on its sections, and the 1999-2006 reader tells each numbered part
    with "part": "Comm Am{4383}, Sec. 5, AL DIV(141-160)" is section 5 of
    SB 303 of 2000's committee amendment lost, and the remainder then carried
    238-74, so "rejected" beside 4383 would be false. The remainder's vote is
    the amendment's ("rest"): "Am{2229}, Remaining Secs, AA RC(239-112)"
    adopted HB 999 of 1999's floor amendment, whose sections 17 and 18 had
    carried 255-96."""
    if e.get("part") == "some":
        return None
    return ADOPTED.get((e.get("motion") or "").upper())


VOTE_KIND_RE = re.compile(r"\b(RC|VV|DV)\b")


def vote_chronology(rcs, narr):
    """Put a day's votes back in the order they happened, and name amendments.

    Two problems, one cause. The votes tab sorted by question text inside a
    date, so a tabling motion came before the vote it interrupted because "Lay"
    sorts before "Ought". And an amendment roll call is recorded as "Adopt
    Amendment" with no number, so two of them in a row are indistinguishable.

    The docket already answers both. It lists every floor action in the order
    it happened, names the amendment each one is about, and marks how each was
    decided. The roll call file numbers its votes in that same order. So the
    two are paired, in order, within a chamber and a day.

    The pairing is only used when the counts agree. If the docket shows three
    roll calls that day and the roll call file has four, something is missing
    from one of them and lining them up would put the wrong number beside the
    wrong vote -- so nothing is claimed and the votes fall back to their own
    numbering.

    Returns (order, names) keyed by (body, roll call number).
    """
    lines = defaultdict(list)
    for i, e in enumerate((narr or {}).get("events", [])):
        if e.get("cancelled"):
            continue
        raw = e.get("raw", "")
        vk = (e.get("vote_kind") or "").upper()
        if not vk:
            m = VOTE_KIND_RE.search(raw)
            vk = m.group(1) if m else ""
        if vk:
            lines[(e.get("date"), e.get("body"))].append((i, vk, raw))

    order, names = {}, {}
    for (date, body), evs in lines.items():
        rc_lines = [(i, raw) for i, vk, raw in evs if vk == "RC"]
        mine = sorted((r for r in rcs
                       if r.get("date") == date and r.get("body") == body),
                      key=lambda r: int(r.get("number") or 0))
        if len(rc_lines) != len(mine):
            continue
        for (i, raw), r in zip(rc_lines, mine):
            k = (r.get("body"), r.get("number"))
            order[k] = i
            am = AMEND_NUM.search(raw)
            if am and "amendment" in (r.get("question") or "").lower():
                names[k] = am.group(1)
    return order, names


# The year a published volume is from, out of the path in its own link. Two
# shapes, because the two files were fetched by different scripts:
#
#   .../Journals/2026/HJ 03 February 5, 2026.PDF
#   .../viewer.aspx?fileName=calendars%5C2026%5CNo10 March 6 2026.pdf
#
# Every one of the 188 keys on file yields a year this way.
SOURCE_YEAR = re.compile(r"(?:%5C|/)(\d{4})(?:%5C|/)", re.I)


def _cite(ev, sources, year=""):
    """The journal or calendar one docket action is printed in, as a link.

    A docket line cites "HJ 7" with no year, because within one session there
    is only one. Across sessions there is one per year, so the lookup is tried
    with the year first.

    It then used to fall back to the bare key, and that was wrong. calendars.json
    and journals.json each hold both forms -- "HC 10" beside "HC 10 2025" and
    "HC 10 2026" -- because their fetchers write the bare key too, and the bare
    key holds whichever year was fetched last. So a 2025 action citing HJ 3
    resolved to the 2026 journal: 4,468 of 12,970 links, a third of them,
    pointing at a volume that does not contain the action they claim to record.
    SR1 cited SJ 1 on a 2024 action and opened the 2026 Senate Journal.

    A missing citation is a gap. A citation to the wrong document is a false
    one, on a site whose whole claim is that it can be checked -- so the year in
    the resolved link is compared with the year of the action, and a link that
    disagrees is not offered at all. The citation itself is still printed; only
    the link is withheld.

    The citation is read off the event, not searched for in the line. The line
    has already been through narrative.clean(), which removes the citation so
    that the hearing pattern's venue group does not swallow "SC 4" -- so a
    search of it found nothing, on every event of every bill. narrative.py
    takes the citation off the raw line and carries it on the event.
    """
    # `year` is the year of the action's date -- or, where narrative.py dated
    # a row by the day it states in another year than it was entered, the
    # year it was entered (the event's "cite_year"): a notice of December
    # for a hearing in January cites December's calendar.
    key = (ev.get("cite") or "").strip()
    if not key:
        return {}
    page = (ev.get("cite_page") or "").strip()
    out = {"cite": key + (f", page {page}" if page else "")}
    url = _source_url(sources, key, year)
    if url:
        out["cite_url"] = url
    return out


def _source_url(sources, key, year):
    """The address for a calendar or journal cited in a given year, or "".

    The year-qualified key first; the bare key only where the address it holds
    is from that same year. One rule for every citation on the site --
    committee_reports() used to take the bare key unguarded, and all 7,376
    House report citations of 2013-2022 linked a 2023 or 2024 calendar and
    printed that calendar's date as the day the report was printed.
    """
    if not key:
        return ""
    url = sources.get(f"{key} {year}") if year else None
    if url:
        return url
    bare = sources.get(key, "")
    m = SOURCE_YEAR.search(bare)
    return bare if (m and year and m.group(1) == str(year)) else ""


# The calendar and journal PDF finders moved to queue_links.py on 24 September
# so the calendar and sitting builders can use them without importing this
# file (whose topic_model import moves the working folder). Same names here.
from queue_links import (calendar_keys_from_queue, journal_keys_from_queue,  # noqa: E402,F401
                         journal_url)


# The General Court's own status vocabulary, mapped to the four display states.
# Reading the field beats inferring it from docket prose: this is the fact most
# people come to the site for, and a wrong guess here is a wrong headline.
# What a bill of each kind actually has to clear before it is finished.
#
# Reading every bill as House, then Senate, then governor is right for HB and
# SB and wrong for everything else. A House Resolution is adopted by the House
# and that is the end of it; a concurrent resolution needs both chambers and
# never goes to the governor; a CACR needs both chambers and then the voters.
# Measured on this term: 32 adopted resolutions read "Passed one chamber" and
# three more read "In progress", one of them offering "Pending action in the
# other chamber" for a resolution that has no other chamber.
# "SS" is a special session's numbering of the same kinds: SSHR 1 of 2008 is
# the House adopting its rules, SSHCR 1 of 2015 a concurrent resolution both
# chambers adopted the same day.
#
# AND A HOUSE BILL OF INTENT, the House's measure of 1989-1994 (HBI, fourteen
# of them): passing one sends its subject to its committee to study and report
# on -- "STATEMENT OF INTENT The committee to which this bill is referred
# shall review existing legislation ... The committee shall submit any
# recommendations for legislation" (HBI 2 of 1991's own text) -- and it never
# goes to the Senate; none of the fourteen dockets has a Senate row. Read as a bill,
# the six the House passed said "Passed one chamber", of a second chamber
# they were never going to, and HBI 2011 of 1990 "Committee report filed",
# which is the report of the study it ordered.
BILL_OF_INTENT = "HBI"
SINGLE_CHAMBER = {"HR": "House", "SR": "Senate", "SSHR": "House", "SSSR": "Senate",
                  BILL_OF_INTENT: "House"}
NO_GOVERNOR = {"HCR", "SCR", "CACR", "SSHCR", "SSSCR"}


def origin_of(bid, narr=None, st=None):
    """"H" or "S": the chamber the bill started in. The docket's first line,
    then the status page's body, then the letters -- a CACR can start in
    either chamber, so its letters cannot say, and data/bills.json's
    "chamber" is "H" on 537 of the 545 CACRs, CACR 9 of 1995 (a Senate one)
    among them."""
    first = next((e for e in (narr or {}).get("events", [])
                  if not e.get("cancelled") and e.get("body")), None)
    for v in ((first or {}).get("body"), (st or {}).get("body")):
        v = (v or "").strip().upper()[:1]
        if v in ("H", "S"):
            return v
    p = bill_prefix(bid)
    return "S" if (p[2:] if p.startswith("SS") else p).startswith("S") else "H"

# "(New Title)" AT THE FRONT OF A TITLE IS NOT PART OF THE TITLE. It is the
# General Court's mark that an amendment changed a bill's subject, and 5,718 of
# the site's 33,683 bills carry one. In the search index it is searchable text,
# and it is the word "new": 7,472 bills match that word today and only 2,260 of
# them because their own title says anything about anything new. It is also the
# first thing read on the card, in front of what the bill is about.
#
# 24 spellings, counted rather than assumed -- "(New Title)" 4,571, "(2nd New
# Title)" 649, "(Second New Title)" 239, "(3rd New Title)" 133, down through
# "(Ninth New Title)", "( New Title )", "(NEW TITLE)" and "(New TItle)". The
# ordinal is one optional word rather than a list, because the drafters write
# it both as a numeral and as a word and got as far as the ninth; that catches
# all 5,718 and nothing else in the 33,683.
#
# Anchored at the front. 1989's SB 177 carries a second mark in the middle --
# its title is two titles concatenated, "(New Title) establishing a grant
# program ... (Second New Title) establishing an interest-free revolving loan
# fund ..." -- and cutting there would join two sentences into one.
NEW_TITLE = re.compile(
    r"^\s*\(\s*(?:[A-Za-z0-9]{1,9}\s+)?New\s+Title\s*\)\s*", re.I)


def clean_title(s):
    """The title without the amendment mark, or the mark where that is all
    there is. Four bills of 1989-1990 are titled "(New Title)" and nothing
    else: the General Court's record of their subject is the mark, and a card
    with an empty heading reads as a broken page rather than as a gap."""
    s = (s or "").strip()
    return NEW_TITLE.sub("", s).strip() or s


# A code in Committees.txt that names no committee. H29 is "No Committee
# Assignment" -- what the General Court files a bill under when it referred it
# nowhere -- and build_committees.py refuses to write a page for it. The two
# files have to agree about what a committee is, so the same words are refused
# here; the name itself still prints on the bill, as plain text rather than as
# a link to a page that was never written.
NOT_A_COMMITTEE = {"no committee assignment"}


def committee_links(index, codes):
    """meta.json's committee_codes: every committee name a bill carries, to the
    page it links to.

    `codes` is {"House Finance": "H34"} for the committees the General Court
    lists today, which is all a name alone can say, and a name can mean more.
    1995's "House Corrections and Criminal Justice" is H26, sitting today under
    a later name; 2003's "House Commerce" is H33, a code the General Court has
    retired, with an archived page of its own; and "Senate Election Law and
    Internal Affairs" is the retired S33 in 2007-2008 and S50, formed later
    under the same name, in 2017-2018. 1989-1990's "Senate Development,
    Recreation and Environment" is S03-1989, a page of its own, because the
    General Court later gave its code, S03, to Appropriations, a different
    committee. committee_names.page_code settles each name in each term from
    the General Court's own filing; this writes the answer down, and the page
    prints the name as the bill carries it.

    A name that goes to one page in every term stays a string. One whose page
    depends on the term becomes {"": the page when no term is given, "<term>":
    the page in that term, "" for none}, carrying only the terms that differ
    from the first. The first is today's committee of that name, because the
    one caller with no term is a member's list of the committees they sit on.
    """
    today = {}
    for full, code in codes.items():
        word, _, nm = full.partition(" ")
        today[(word[:1], CN._norm(nm))] = code
    per = defaultdict(dict)
    for b in index:
        t = b.get("term") or ""
        for full in (b.get("committees")
                     or ([b["committee"]] if b.get("committee") else [])):
            word, _, nm = full.partition(" ")
            if t and word in ("House", "Senate"):
                per[full][t] = CN.page_code(nm, word[:1], t, today) or ""
    out = dict(codes)
    for full, by_term in per.items():
        base = codes.get(full, "")
        got = set(by_term.values())
        if got == {base}:
            continue
        if len(got) == 1 and not base:
            out[full] = got.pop()
            continue
        out[full] = {"": base, **{t: c for t, c in sorted(by_term.items())
                                  if c != base}}
    return out


def bill_prefix(bid):
    """HB1442 -> HB, CACR9 -> CACR. The letters, which say what kind it is."""
    m = re.match(r"^[A-Za-z]+", str(bid or ""))
    return m.group(0).upper() if m else ""


def for_bill_kind(needle, kind, label, prefix):
    """The same status word, read against what that kind of bill needs.

    "PASSED/ADOPTED" on a House Bill means one chamber down and one to go. On
    a House Resolution it is the final action. The status page does not make
    the distinction because it does not have to -- the reader knows which kind
    of thing they asked about, and this site has to say so.
    """
    if needle == "passed/adopted" and prefix in SINGLE_CHAMBER:
        return "adopted", f"Adopted by the {SINGLE_CHAMBER[prefix]}"
    if needle == "concurred" and prefix in NO_GOVERNOR:
        if prefix == "CACR":
            return "adopted", "Passed both chambers, goes to the voters"
        return "adopted", "Adopted by both chambers"
    return kind, label


STATED = [
    ("signed by governor", "law", "Signed into law"),
    # The field says "LAW WITHOUT SIGNATURE"; the needle wanted "became law
    # without signature" and so never matched it. Nine bills. Masked until
    # now because docket_outcome rescued every one of them from the docket.
    ("law without signature", "law", "Became law unsigned"),
    # The three outcomes of a veto, most specific first. A bill awaiting the
    # override vote, one where the override failed, and one where it succeeded
    # are three different situations, and lumping them as "Vetoed" hides the
    # only part anyone wants to know.
    #
    # SUSTAINED BEFORE OVERRIDDEN, as classify() already has it for the
    # docket: an override needs two-thirds in both chambers, so one chamber
    # sustaining ends the bill whatever the other did. The fields are read
    # together, and a bill whose House field says VETO OVERRIDDEN and whose
    # Senate field says VETO SUSTAINED read "Veto overridden, became law" --
    # eleven of them, 1989 to 2012, every one confirmed by its docket as an
    # override that failed in the second chamber. The fourteen in terms with
    # a narrated docket were rescued by docket_outcome.
    ("veto sustained", "veto", "Vetoed, override failed"),
    ("override failed", "veto", "Vetoed, override failed"),
    ("veto overridden", "law", "Veto overridden, became law"),
    ("override adopted", "law", "Veto overridden, became law"),
    ("veto override", "veto", "Vetoed, override vote pending"),
    ("vetoed by governor", "veto", "Vetoed, awaiting an override vote"),
    ("inexpedient to legislate", "done", "Killed"),
    # OUGHT NOT TO PASS, ADOPTED, IS THE CHAMBER'S REJECTION: BodyStatusCodes.txt
    # code 26, the House's field on five addresses for the removal of a judge
    # -- HA 1 of 1999, of 2006 and of 2018, HA 1 and HA 3 of 2010 -- each of
    # whose dockets has the House adopting that report ("Ought Not to Pass: MA
    # DIV 220-106"). With no row here they read "In committee" or "In
    # progress". "Killed" is the word this site gives a chamber's adopted
    # rejection: HA 1 of 2015, ended by Inexpedient to Legislate, reads it.
    ("ought not to pass", "done", "Killed"),
    ("died on the table", "done", "Died on the table"),
    ("died, session ended", "done", "Died when the session ended"),
    # Parked for the committee to work on out of session, not killed.
    ("interim study", "study", "Referred for interim study"),
    ("indefinitely postponed", "done", "Indefinitely postponed"),
    ("laid on table", "active", "Laid on the table"),
    ("retained in committee", "active", "Retained in committee"),
    # The docket hyphenates; BodyStatusCodes.txt code 21 does not.
    ("re-referred", "active", "Re-referred to committee"),
    ("rereferred", "active", "Re-referred to committee"),
    # BEFORE "concurred", which is a substring of both of these. 21 bills
    # were live reading "Passed, awaiting the governor" when a chamber had
    # refused to concur -- the opposite of what happened, on the field the
    # site treats as most authoritative. BodyStatusCodes.txt has all three
    # as separate codes: 12 CONCURRED, 13 NONCONCURRED, 14 NONCONCURRED
    # REQUEST CONFERENCE.
    ("nonconcurred request conference", "active",
     "One chamber did not concur; a committee of conference was asked for"),
    ("nonconcurred", "active", "One chamber did not concur"),
    ("concurred", "active", "Passed, awaiting the governor"),
    ("passed/adopted", "active", "Passed one chamber"),
    ("in committee", "active", "In committee"),
    # A CHAMBER REFUSED TO INTRODUCE THE BILL: BodyStatusCodes.txt code 24,
    # in the General Court's own words. SB 267 of 2007 and SB 499 of 2016
    # carry it in their Senate field and nothing else -- the Senate voted
    # down the motion to introduce each -- and with no row here they read
    # "In committee", a committee neither ever reached. LAST, so that it is
    # the answer only where nothing above is: HB 2002 and HCO 1 of 2002
    # passed the House before the Senate refused them, and stay "Passed one
    # chamber".
    ("refused introduction", "done", "Refused introduction"),
]

# The statuses of a bill that was never introduced: the passage rail starts
# at Introduced, and none is drawn for these (build_bills).
WITHDRAWN_PRIOR = "Withdrawn prior to introduction"
PROPOSED_ONLY = "Proposed for the special session"
# AND ONE WHOSE DOCKET SAYS "INTRODUCED" AND WHOSE HOUSE DID NOT INTRODUCE IT.
# HB 87 and HB 134 of 2009 and HB 633 of 2007 each have one docket row, the
# introduction row typed ahead of the day, and the House's resolution of
# introduction steps over each number (build_data.INTRODUCTION_FROM_JOURNAL;
# narrative.build types the row entered_introduced). Nothing on disk says
# what became of them -- withdrawn, most likely, and no row says so -- so the
# status says the one thing the record bears out. HB 177, HB 273, HB 274 and
# HB 277 of 2017 are the same, on records the bill search's own list carries.
NOT_INTRODUCED = "Not introduced"
NEVER_INTRODUCED = {"Refused introduction", WITHDRAWN_PRIOR, PROPOSED_ONLY, NOT_INTRODUCED}


# THE CHIP: SIX WORDS FOR WHERE A BILL STANDS. The person, 5 October 2026:
# "let's change the chips to say Became Law, Died, Interim Study, Tabled (For
# bills currently on the table during session, bills that died at the end of
# session on the table are just labeled as Died), Vetoed (For those pending a
# vote, and if it was overridden then it will say Became Law and if it wasn't
# it would be Died, but the summary and rail would indicate which), and
# Withdrawn." The chip is for searching and for a glance; how a bill ended
# belongs to its history.
#
# So the status is untouched -- "Killed", "Died on the table", "Vetoed,
# override failed" -- and it is still what the history, the rail, the status
# box, the closing paragraph and bills.csv's status column say. The chip is
# read from it here and nowhere else: the index carries it as `chip`
# (bill_index_row), and the card, the Status filter, the grouping by status,
# a member's and a committee's Status select, the directory and bills.csv's
# chip column all print that.
#
# Tabled and Vetoed need a session with days left (`live`: the current term,
# with no session_over in status/status.txt). A bill left on the table when
# the session ended died there; a veto never put to a vote stood. A bill
# still moving keeps its stage, and a resolution adopted, a constitutional
# amendment's ballot, a bill only proposed for a special session, one the
# House did not introduce and one awaiting the governor keep their own words
# (CHIP_KEEPS): none of them is among the six, and which word they take is
# the person's to say.
BECAME_LAW, DIED, INTERIM_STUDY, TABLED, VETOED, WITHDRAWN = (
    "Became Law", "Died", "Interim Study", "Tabled", "Vetoed", "Withdrawn")
CHIP_WORDS = (BECAME_LAW, DIED, INTERIM_STUDY, TABLED, VETOED, WITHDRAWN)
# A withdrawal the record states: the chamber's, and one before introduction.
WITHDRAWN_ENDINGS = frozenset({"Withdrawn", WITHDRAWN_PRIOR})
# A veto whose override vote is still to come, in bill_disposition's words:
# the docket's "vetoed" with no vote after it, VETOED BY GOVERNOR, VETO
# OVERRIDE, and a veto one chamber has overridden and the other has not yet
# voted on. "Vetoed, override failed" is not one.
VETO_PENDING = frozenset({"Vetoed", "Vetoed, awaiting an override vote",
                          "Vetoed, override vote pending"})
AWAITING_GOVERNOR = "Passed, awaiting the governor"
# A bill whose chip keeps its own word, until the person gives it one.
#
# NOT INTRODUCED IS NOT WITHDRAWN. Nothing on disk says what became of the
# seven (NOT_INTRODUCED above): HB 87 and HB 134 of 2009 carry
# PastLegislation's CurrentLSRStatus 8, an introduced bill's code, and the
# five others 9, a code nothing on disk defines, on 2,491 rows, 2,484 of them
# with no bill number. Their histories say only that the House Journal left
# them out, and "Withdrawn" would say what no record does.
#
# NOR IS A BILL AWAITING THE GOVERNOR DEAD. Both chambers passed it and the
# docket has not recorded what the governor did, which can come after the
# last session day: the session being over does not make it "Died".
CHIP_KEEPS = frozenset({PROPOSED_ONLY, NOT_INTRODUCED, AWAITING_GOVERNOR})


def chip_word(kind, status, live):
    """The chip of a bill whose disposition is (`kind`, `status`); `live` is
    whether its session still has days to sit."""
    if kind == "law":
        return BECAME_LAW
    if status in WITHDRAWN_ENDINGS:
        return WITHDRAWN
    if kind == "study":
        return INTERIM_STUDY
    if kind == "veto":
        return VETOED if live and status in VETO_PENDING else DIED
    if kind == "active" and live:
        return TABLED if status == "Laid on the table" else status
    if kind in ("active", "done"):
        return status if status in CHIP_KEEPS else DIED
    return status


def journal_not_introduced(narr):
    """Whether the bill's history is one the House Journal's resolution of
    introduction decided against its docket: narrative.build found the
    record's reading, typed the docket's introduction row entered_introduced
    and marked the bill not_introduced. The one question classify() and
    bill_disposition() both ask."""
    return bool((narr or {}).get("not_introduced")) and any(
        e.get("type") == "entered_introduced" for e in (narr or {}).get("events", []))


# Docket lines that are procedural bookkeeping rather than steps in a bill's
# progress. Appointing an alternate to a committee of conference, or one member
# acceding to another's motion, is a real recorded action and is kept -- but it
# is not why anyone opened the page, and forty of them bury the four lines that
# matter.
#
# Nothing is discarded. Every action is still written to the bill's record and
# shown in full on its static page; the interactive view collapses these behind
# a toggle and says how many it is hiding.
ROUTINE = re.compile(
    r"\b(?:"
    r"appoint\w*\s+(?:alternate|conferee)|"
    r"alternate\s+(?:member|conferee)|"
    r"replaces\s+(?:Rep|Sen)\.|"
    r"accedes|"
    r"conference committee meeting|"
    r"committee meeting:|"
    r"(?:name|member)s?\s+(?:added|removed)|"
    r"reconsider(?:ation)?\s+(?:notice|filed)|"
    r"sponsor\s+(?:added|removed)|"
    r"enrolled bill amendment|"
    r"pending\s+(?:motion|question)|"
    r"lay on table\s*\(|"
    r"special order|"
    r"withdrawn from|"
    r"printed in|"
    r"referred to (?:the )?(?:committee on )?rules"
    r")", re.I)


# --------------------------------------------------------------------- RSA --
# A statute cites as "RSA 91-A:4", and its page lives at
#
#     /rsa/html/VI/91-A/91-A-4.htm
#             ^^ the TITLE, which the citation does not carry
#
# So the chapter has to be resolved to a title first. The General Court's own
# table of contents at /rsa/html/nhtoc.htm lists every title with the chapters
# it covers, and that is the table below, read from it on 4 September 2026.
#
# Chapters sort as (number, suffix), which is what makes the awkward pairs come
# out right: chapter 361 is Title XXXIII and 361-A is XXXIII-A; 227-F ends Title
# XIX and 227-G begins XIX-A. Comparing the pair handles both without a special
# case. A chapter in none of the ranges -- 251 to 258 exist in no title -- is
# not linked at all, because a citation link that 404s is worse than plain text.
RSA_TITLES = [
    ("I", "1", "21-V"), ("II", "22", "30-B"), ("III", "31", "53-G"),
    ("IV", "54", "70"), ("V", "71", "90"), ("VI", "91", "103"),
    ("VII", "104", "106-R"), ("VIII", "107", "119"), ("IX", "120", "124-A"),
    ("X", "125", "149-R"), ("XI", "150", "152"), ("XII", "153", "174"),
    ("XIII", "175", "180"), ("XIV", "183", "185"), ("XV", "186", "200-O"),
    ("XVI", "201", "202-B"), ("XVII", "203", "205-D"), ("XVIII", "206", "215-D"),
    ("XIX", "216", "227-F"), ("XIX-A", "227-G", "227-M"), ("XX", "228", "250"),
    ("XXI", "259", "269"), ("XXII", "270", "272"), ("XXIII", "273", "283"),
    ("XXIV", "284", "287-J"), ("XXV", "288", "288"), ("XXVI", "289", "291-A"),
    ("XXVII", "292", "303"), ("XXVIII", "304", "305-A"), ("XXIX", "306", "308"),
    ("XXX", "309", "332-N"), ("XXXI", "333", "359-U"), ("XXXII", "360", "360"),
    ("XXXIII", "361", "361"), ("XXXIII-A", "361-A", "361-E"),
    ("XXXIV", "362", "382"), ("XXXIV-A", "382-A", "382-A"),
    ("XXXV", "383", "397-B"), ("XXXVI", "398", "399-G"), ("XXXVII", "400", "420-Q"),
    ("XXXVIII", "421", "421-B"), ("XXXIX", "422", "424"), ("XL", "425", "439-A"),
    ("XLI", "444", "454-C"), ("XLII", "455", "456-B"), ("XLIII", "457", "461-B"),
    ("XLIV", "462", "465"), ("XLV", "466", "470"), ("XLVI", "471", "471-D"),
    ("XLVII", "472", "476"), ("XLVIII", "477", "479-B"), ("XLIX", "480", "480"),
    ("L", "481", "489-C"), ("LI", "490", "505"), ("LII", "506", "513"),
    ("LIII", "514", "526"), ("LIV", "527", "533"), ("LV", "534", "546-C"),
    ("LVI", "547", "567-A"), ("LVII", "568", "569"), ("LVIII", "570", "591"),
    ("LIX", "592", "614"), ("LX", "615", "623-C"), ("LXI", "624", "624"),
    ("LXII", "625", "651-F"), ("LXIII", "652", "671"), ("LXIV", "672", "679"),
]

# "RSA 91-A:4" / "RSA 638:26-a" / "RSA 91-A" / "RSA 91-A:2, III" -- the roman
# numeral after a comma is a paragraph within the section, not part of the
# address, so it is left out of the link and left in the sentence.
# FIVE WAYS THIS SENT A READER TO THE WRONG STATUTE, all of them from a class
# that was one character too narrow. These are LINKS, so a mis-parse does not
# lose a citation -- it publishes a different law under the right words.
#
#   RSA 2025, 141:389  ->  chapter 202   a SESSION LAW, not an RSA chapter at
#                                        all; \d{1,3} took "202" out of "2025"
#                                        and linked RSA 202, Public Libraries
#   RSA 126-AA:2       ->  126-A         -[A-Z] is one letter; 126-AA and
#                                        126-A are different chapters
#   RSA 21-I:19-ff     ->  21-I:19-f     likewise for the section suffix
#   RSA 383-A:6-602    ->  383-A:6       a hyphenated section number, truncated
#   RSA 293-A:10.01    ->  293-A:10      a dotted section number, truncated
#
# The trailing lookaheads are what make the first case give NOTHING rather than
# something wrong: "2025" cannot end after three digits, so the whole match
# fails and the session-law citation is left as plain words. Refusing to link
# is the right answer where the target is not an RSA chapter.
RSA_CITE = re.compile(
    r"\bRSA\s+(\d{1,3}(?:-[A-Z]{1,2})?)(?![\d-])"
    r"(?::(\d{1,4}(?:-[a-z0-9]{1,3})?(?:\.\d{1,2})?)(?!\d))?",
    re.I)


def _chapter_key(ch):
    m = re.match(r"(\d+)(?:-([A-Za-z]+))?$", ch.strip())
    return (int(m.group(1)), (m.group(2) or "").upper()) if m else None


def rsa_url(chapter, section=None):
    """The General Court's own page for a citation, or "" if unresolvable."""
    key = _chapter_key(chapter)
    if not key:
        return ""
    for title, lo, hi in RSA_TITLES:
        klo, khi = _chapter_key(lo), _chapter_key(hi)
        if klo and khi and klo <= key <= khi:
            ch = chapter.upper()
            if section:
                return (f"https://gc.nh.gov/rsa/html/{title}/{ch}/"
                        f"{ch}-{section}.htm")
            return f"https://gc.nh.gov/rsa/html/NHTOC/NHTOC-{title}-{ch}.htm"
    return ""


def rsa_links(*texts):
    """{citation as written: url} for every statute cited in these strings.

    A map rather than rewritten text: the renderers escape what they print, and
    handing them HTML to escape would show the tags. They substitute after
    escaping, which is safe because a citation contains nothing to escape.
    """
    out = {}
    for txt in texts:
        for m in RSA_CITE.finditer(txt or ""):
            url = rsa_url(m.group(1), m.group(2))
            if url:
                out[m.group(0)] = url
    return out


# WHAT A BILL AMENDS IS NOT WHAT IT MENTIONS. rsa_links finds every citation
# anywhere in a document, which is right for turning words into links and wrong
# for a row headed "Amends RSA chapters". 628 bills on this site cite RSA 91-A
# and 150 of them amend it; the other 478 say things like "exempt from
# disclosure under RSA 91-A:5, IV" inside the text of some other statute, and
# the row told a reader the bill changes the Right-to-Know law. Counted over
# the 14,085 bills whose text is on disk: 15,788 of 36,303 chapter claims --
# 43.5% -- were mentions of this kind.
#
# A New Hampshire bill states what it changes in ONE CLAUSE ENDING IN A COLON,
# and everything after that colon is the new text:
#
#   Amend RSA 126-A:5 by inserting after paragraph II the following new
#     paragraph:                                          -> RSA 126-A:5
#   Amend RSA 91-A:4, IV(a) to read as follows:           -> RSA 91-A:4
#   Repeal. RSA 91-A:5, VI, relative to X, is repealed.   -> RSA 91-A:5
#   The following are repealed: I. RSA 77:3 ... II. RSA 76:8 ...
#
# Of those bills' 24,700 `Amend` instructions, 24,267 close with a colon within
# 400 characters. The 433 that do not are lower-case "amend" inside statutory
# prose -- "may amend the petition only if the defendant is provided..." -- and
# are not instructions at all, so a clause with no colon yields NOTHING rather
# than 400 characters of somebody else's text. `Amend` is matched case
# sensitively for the same reason: an instruction opens a sentence.
AMEND_WORD = re.compile(r"\bAmend\b")
# The two forms the drafters use, and no third.
REPEALED = re.compile(r"\b(?:is|are)\s+repealed\b", re.I)
REPEAL_LIST = re.compile(r"\bfollowing\s+(?:is|are)\s+repealed\s*:", re.I)
# The colon that ends a clause -- NOT the one inside "RSA 91-A:4", which is
# part of the citation and is always followed by a digit.
CLAUSE_END = re.compile(r":(?!\d)")
# Where a repeal list stops: the bill's next numbered section. "213:1" as well
# as "1", because an enacted bill is renumbered into the session laws and its
# sections then read "213:1 New Chapter; ...".
NEXT_SECTION = re.compile(r"^\s*(?:\d{1,3}:)?\d{1,3}\s+[A-Z(]", re.M)
# A WINDOW CUT MID-CITATION INVENTS ONE. The 2,000 character stop landed inside
# "XXIII. RSA 175:1" in 2011's HB 1500 and the tail read as RSA 17 -- a real
# chapter, and the wrong one. Trimming the part-word is what makes this reader
# a strict subset of rsa_links rather than nearly one.
PART_WORD = re.compile(r"\S+$")


def bill_amends(body):
    """{citation as written: url} for the statutes a bill's text says it changes.

    The same shape rsa_links returns, so the page reads it the same way, and
    measured to be a strict subset of it: across all 14,085 texted bills this
    names no chapter rsa_links did not.

    A bill that CREATES a chapter -- "Amend RSA by inserting after chapter
    359-S the following new chapter:" -- names no existing chapter here and
    gets no row. That is the largest part of the 784 bills that had a row and
    now have none; the rest are findings, appropriations and effective-date
    clauses that cite a statute without touching it.
    """
    out = {}
    body = body or ""

    def take(s):
        for m in RSA_CITE.finditer(s or ""):
            url = rsa_url(m.group(1), m.group(2))
            if url:
                out.setdefault(m.group(0), url)

    for m in AMEND_WORD.finditer(body):
        stop = CLAUSE_END.search(body, m.end(), m.end() + 400)
        if stop:
            take(body[m.start():stop.start()])
    # "The following are repealed:" puts its targets AFTER the colon, one
    # roman numeral to a line, and the list runs to the next section.
    for m in REPEAL_LIST.finditer(body):
        nxt = NEXT_SECTION.search(body, m.end())
        end = min(nxt.start() if nxt else len(body), m.end() + 2000)
        take(PART_WORD.sub("", body[m.end():end]))
    # "RSA 21-I:19-a, relative to X, is repealed." -- the target is behind the
    # verb, so the window runs back to the start of that sentence.
    for m in REPEALED.finditer(body):
        lo = body.rfind(". ", max(0, m.start() - 300), m.start())
        take(body[(lo + 2 if lo != -1 else max(0, m.start() - 300)):m.start()])
    return out


_OWN_SLUG = {}


def own_slug(m):
    """The address of this member's OWN page, built the way that page is.

    NOT member_slug(m, whatever_label_is_to_hand). member_slug takes the name
    out of the label it is given, and a sponsor's label is deliberately the
    seat and the name AS THE RECORD PRINTED THEM AT THE TIME -- so a 2009 bill
    naming "Patrick Long, Hills 10" produced patrick-long-sd-20 for a senator
    whose page is pat-long-sd-20, because the roster spells him Pat. A link to
    a file that does not exist.

    It has been right for everyone else by coincidence: Cindy Rosenwald and
    Mark McConkey are spelled the same way in a 2009 bill's text as in today's
    roster, so the name the label carried happened to be the name the page was
    built from. Pat Long is the first case where the two differ, and the
    mechanism was wrong for all of them.

    So the slug comes from the member's own roster row, through the same
    member_labels call build_legislators makes, which is what guarantees the
    two agree. Cached because a sponsor list asks for it 68,930 times.
    """
    mid = str(m.get("id") or "")
    if not mid:
        return ""
    if mid not in _OWN_SLUG:
        lab = member_labels(m.get("name"), chamber=m.get("chamber"),
                            party=m.get("party_code") or m.get("party"),
                            district=m.get("district"), county=m.get("county"),
                            county_abbr=m.get("county_abbr"))
        _OWN_SLUG[mid] = m.get("slug") or member_slug(m, lab)
    return _OWN_SLUG[mid]


def member_slug(m, lab):
    """jodi-nelson-rock-13, debra-altschiller-sd-24.

    Computed here so the search page and the static page agree on the address
    without either having to guess.

    House districts are numbered within a county -- Rockingham 13 and
    Hillsborough 13 are different places -- so the county has to be in the
    address. Senate districts are numbered once across the state, so the number
    is already unique. Both are geographic; only the numbering differs.
    """
    name = re.sub(r"^(?:Rep|Sen)\.\s+", "",
                  lab.get("display_plain") or m.get("name", ""))
    if "," in name:
        last, _, first = name.partition(",")
        name = f"{first.strip()} {last.strip()}"
    senate = str(m.get("chamber", "")).upper().startswith("S")
    where = "sd" if senate else (m.get("county_abbr") or m.get("county") or "")
    s = unicodedata.normalize("NFKD", f"{name} {where} {m.get('district','')}")
    s = s.encode("ascii", "ignore").decode()
    return re.sub(r"-{2,}", "-", re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")).lower()


# ------------------------------------------------------------------ naming --
# One way of naming a member, used everywhere the site refers to one.
#
#     display_plain   Rep. Jodi Nelson
#     display         Rep. Jodi Nelson (R)
#     display_full    Rep. Jodi Nelson (R - Rock. 13)
#                     Sen. Debra Altschiller (D - SD24)
#
# Three forms rather than one because a party letter beside a name that already
# sits next to a party colour chip reads as a stutter. The page picks the form
# that fits what is already on screen; nothing downstream has to split strings
# apart to get there.
#
# The honorific comes from the CHAMBER, not from a member's `title` field. That
# field can hold "Speaker" or "President", and this is a consistent way of
# referring to somebody rather than a statement of their highest office.
#
# The party letter is DROPPED rather than guessed when it is not known, and the
# district with it. A member resolved from a roll call page may have neither,
# and "(?)" beside a name is worse than a name on its own. A House district
# with no county is likewise omitted: "Rock. 13" locates a seat, "13" does not.
# Without the trailing point, which is the form data/legislators.json's own
# county_abbr carries. A member drawn from the roster read "Hills 12" and
# one drawn from here read "Hills. 6", so the punctuation tracked exactly
# who had left office.
COUNTY_ABBR = {
    "belknap": "Belk", "carroll": "Carr", "cheshire": "Ches",
    "coos": "Coos", "co\u00f6s": "Coos", "grafton": "Graf",
    "hillsborough": "Hills", "merrimack": "Merr", "rockingham": "Rock",
    "strafford": "Straf", "sullivan": "Sull",
}
# EITHER SPELLING RESOLVES, because the sources do not agree on which they
# store. member_party.json writes a seat already abbreviated -- 622 rows say
# "Hills", 440 "Rock", 212 "Merr", and so on through all nine that shorten --
# and this map is keyed on the full name, so .get() missed and the seat was
# dropped out of the label altogether: 228 sponsor rows read "Rep. Jane Smith
# (R)" where every other row on the same bill reads "(R - Hills 12)".
#
# 62 of those 228 are filled from former_members.json by way of build_data's
# roll-call pass, and the seat it carries is the one that member held LAST,
# not the one they held when the bill was filed. That is a fact about where
# the seat comes from and cannot be told apart here -- district_tag is handed
# a county and a number and no provenance -- so it is fixed upstream or not at
# all, and is written down rather than guessed at.
#
# A trailing point is allowed on the way in because Counties.txt writes
# "Hills." and the roster writes "Hills"; what comes out is always the
# roster's spelling, so the punctuation stops tracking who has left office.
COUNTY_OF = {**COUNTY_ABBR, **{v.lower(): v for v in COUNTY_ABBR.values()}}
HONORIFIC = {"H": "Rep.", "S": "Sen."}

_TITLE_RE = re.compile(r"^(?:rep|sen|representative|senator)\.?\s+", re.I)
# Case-insensitive: the bill status page writes the letter in lower case,
# so "Howard Pearl (r)" kept its tail, sorted as "(r), howard pearl" and
# matched nobody on the roster. 112 sponsor rows, all his.
_PARTY_TAIL_RE = re.compile(r"\s*\([RDILU](?:\s*[-\u2013][^)]*)?\)\s*$", re.I)
# build_data.py's "label" field is a composite -- "Nelson, Jodi(R) Rock. 13" --
# with the party letter in the MIDDLE and the seat after it. Nothing here is
# fed that field any more, but a formatter that mangles its input silently is
# worse than one that guards against it: this cuts at the party marker
# wherever it appears. No real name contains "(R)".
_COMPOSITE_RE = re.compile(r"\s*\([RDILU]\)\s.*$")
_PLACEHOLDER_RE = re.compile(r"^(?:Member\s*#|\(unknown)", re.I)


def person_name(raw):
    """"Nelson, Jodi" -> "Jodi Nelson".

    Idempotent: run it on something already formatted and the honorific and
    party letter are stripped before being put back, so nothing can ever read
    "Rep. Rep. Jodi Nelson (R) (R)".
    """
    s = re.sub(r"\s+", " ", (raw or "").strip())
    s = _COMPOSITE_RE.sub("", _PARTY_TAIL_RE.sub("", _TITLE_RE.sub("", s)))
    if "," in s:
        parts = [x.strip() for x in s.split(",") if x.strip()]
        if len(parts) == 2:
            s = f"{parts[1]} {parts[0]}"
        elif len(parts) > 2:
            # "Smith, John, Jr." - the suffix belongs at the end, not the middle.
            s = f"{parts[1]} {parts[0]} {' '.join(parts[2:])}"
    return s.strip()


def sort_name(raw):
    """Surname first, for the lists that are read alphabetically."""
    s = re.sub(r"\s+", " ", (raw or "").strip())
    s = _PARTY_TAIL_RE.sub("", _TITLE_RE.sub("", s))
    if "," in s:
        return s.lower()
    bits = s.split()
    return f"{bits[-1]}, {' '.join(bits[:-1])}".lower() if len(bits) > 1 else s.lower()


def name_key(raw):
    """("rebecca", "kwoka") -- a member's first and last word, either way round.

    sort_name treats the final word as the surname, which is right until a
    surname has more than one word in it. "Rebecca Perkins Kwoka" becomes
    "kwoka, rebecca perkins" while the roster holds "Perkins Kwoka, Rebecca",
    and the two never meet. The same for "Sabourin dit Choiniere" and for the
    particle in "de Vries" -- 217 sponsor rows across four members, drawn
    without the district everybody else has beside their name.

    Taking the first word and the last word sidesteps the split entirely: both
    spellings of a name yield the same pair however many words sit between
    them. It is a weaker key than a surname, so it is tried only after
    sort_name has failed.
    """
    s = _PARTY_TAIL_RE.sub("", _TITLE_RE.sub("", re.sub(r"\s+", " ",
                                                        (raw or "").strip())))
    if "," in s:
        last, first = [x.strip() for x in s.split(",", 1)]
        s = f"{first} {last}"
    w = [x for x in re.sub(r"[^\w' -]", " ", s, flags=re.UNICODE).lower().split()
         if x]
    return (w[0], w[-1]) if len(w) >= 2 else None


def district_tag(chamber, district, county=None, county_abbr=None):
    d = str(district or "").strip()
    if not d:
        return ""
    if chamber == "S":
        return f"SD{d}"
    ab = (county_abbr or "").strip() or COUNTY_OF.get(
        (county or "").strip().rstrip(".").lower(), "")
    return f"{ab} {d}" if ab else ""


def member_labels(name, chamber=None, party=None, district=None, county=None,
                  county_abbr=None, label=None):
    who = person_name(label or name)
    if not who:
        return {"display_plain": "", "display": "", "display_full": "",
                "district_label": "", "sort": ""}
    if _PLACEHOLDER_RE.match(who):
        # A member the roster could not name. Calling that "Rep. Member #377204"
        # dresses up a gap as a person.
        return {"display_plain": who, "display": who, "display_full": who,
                "district_label": "", "sort": who.lower()}
    hon = HONORIFIC.get((chamber or "").strip().upper()[:1], "")
    plain = f"{hon} {who}".strip()
    pc = (party or "").strip()[:1].upper()
    p = pc if pc in "RDILU" else ""
    short = f"{plain} ({p})" if p else plain
    tag = district_tag((chamber or "").strip().upper()[:1], district, county,
                       county_abbr)
    if tag:
        full = f"{plain} ({p} - {tag})" if p else f"{plain} ({tag})"
    else:
        full = short
    return {"display_plain": plain, "display": short, "display_full": full,
            "district_label": tag, "sort": sort_name(label or name)}


def is_routine(text):
    return bool(ROUTINE.search(text or ""))


def classify_stated(st, prefix="", origin=""):
    """Map the page's own status wording to a display state, or None.

    Scans every status field at once and takes the most specific match, rather
    than the first field that matches anything. Checking gen_status first meant
    a bill whose override had already failed still read "VETOED BY GOVERNOR" and
    came out as awaiting a vote, because the general field never catches up with
    the chamber's.
    """
    blob = " ".join((st.get(f) or "").strip().lower()
                    for f in ("gen_status", "house_status", "senate_status"))
    if not blob.strip():
        return None
    hit = next(((n, k, l) for n, k, l in STATED if n in blob), None)
    # A RESOLUTION BOTH CHAMBERS PASSED IS FINISHED, and "passed/adopted" is
    # in every such record's fields -- so the STATED row below answered
    # "Passed one chamber" for 151 of them (CACR 13 of 2026 among them, its
    # own status box saying "Senate: PASSED/ADOPTED"), and the bare-PASSED
    # fallback at the foot of this function was never reached. What says
    # both chambers are done is the SECOND chamber's own field reading
    # PASSED/ADOPTED without amendment -- nothing is left to concur in.
    # gen_status PASSED is not enough on its own: HCR 10 and HCR 11 of 2024
    # carry it with no Senate action in their dockets at all. Only where
    # nothing more decisive is stated: a resolution a field says was killed
    # stays so.
    if prefix in NO_GOVERNOR and (hit is None or hit[0] in ("passed/adopted", "in committee")):
        second = (st.get("senate_status" if (origin or "H") == "H" else "house_status")
                  or "").strip().lower()
        if second.startswith("passed/adopted") and "amend" not in second:
            if prefix == "CACR":
                return "adopted", "Passed both chambers, goes to the voters"
            return "adopted", "Adopted by both chambers"
    if hit:
        return for_bill_kind(*hit, prefix)
    # Nothing in the table matched. GeneralCodes.txt code 04 is "PASSED", and
    # the table does not carry it because for a bill it says nothing the docket
    # does not say better -- passed the legislature, governor next. For a
    # resolution it is the whole answer, and HR35 sat on "In progress" with
    # gen_status PASSED and an adopted floor vote behind it. Asked last, and
    # only of resolutions, so it cannot shadow a more specific outcome.
    if "passed" in blob:
        if prefix in SINGLE_CHAMBER:
            return "adopted", f"Adopted by the {SINGLE_CHAMBER[prefix]}"
        if prefix == "CACR":
            return "adopted", "Passed both chambers, goes to the voters"
        if prefix in NO_GOVERNOR:
            return "adopted", "Adopted by both chambers"
    return None


# The docket writes the signature two ways -- "Signed by Governor Ayotte
# 7/10/2026" and "Signed by the Governor on 7/10/2026" -- and the second is
# 233 of the 632. Reading only the first left those bills showing whatever
# they were before it: 137 "Passed one chamber", 82 "Passed, awaiting the
# governor", nine "In committee" and five "Killed", for bills that are law.
SIGNED_RE = re.compile(r"signed by (?:the )?governor", re.I)


# How a bill ends when the docket does not say so.
#
# The docket records actions, and a session ending is not an action: it just
# stops. For 111 bills the last line is a committee report and the status page
# alone knows the bill died with the term, so the page showed a red headline
# over a history that trailed off mid-sentence -- the status said one thing and
# the story below it said nothing at all.
#
# Each of these says what happened and what it means, because "DIED, SESSION
# ENDED" is the General Court's phrase rather than a plain-English one.
CLOSING = {
    # label: (phrases that mean the history ALREADY says it, the paragraph)
    #
    # The guards are per outcome, and they have to be. A first attempt tested
    # for "kill it" anywhere in the narrative and matched every bill whose
    # committee recommended that the chamber kill it -- which is a committee
    # report, not an ending, and it suppressed the paragraph on all 111.
    "Died when the session ended": (
        ("session ended", "died when the session", "died on the table"),
        # "THE BILL ITSELF", because a vote on a motion about it is still a
        # vote. HB 1420, HB 1223 and CACR 19 of 2026 each met a motion to
        # take it up out of order that failed on a division -- HB 1420's
        # 141-203 -- and then nothing more, and
        # the page said "No vote was ever taken on it" over the tally. The
        # journey counts decisions on the bill, not procedural motions, so
        # the sentence claims exactly that much.
        "Neither chamber ever voted on the bill itself, and it died when the "
        "session ended. That is a procedural end rather than a decision -- much like a "
        "bill left on the table, it ran out of time -- and it would have to be "
        "filed again as a new bill in a later term."),
    "Indefinitely postponed": (
        ("indefinitely postpone",),
        "The chamber voted to indefinitely postpone it. That ends the bill for "
        "the term and, under the rules, bars the same subject from being taken "
        "up again before the term is out."),
    # CONF_UNABLE. The history says "adopted Conference Committee Report"
    # and no more, which is the one reading this paragraph must not leave
    # standing: what the chambers adopted was the conferees' word that they
    # could not agree.
    "Died: conferees could not agree": (
        ("could not agree", "unable to agree"),
        "The committee of conference -- members of both chambers named to settle "
        "the differences between the House and Senate versions -- could not "
        "agree on one, and reported that it was unable to agree. With no version "
        "that both chambers had accepted, the bill went no further, and it died."),
    # "Killed" is deliberately NOT here. The status page reports it for bills
    # whose docket already says what ended them -- 28 were laid on the table
    # and died there, and the narrative says so in as many words -- so a
    # paragraph claiming "the docket does not record the vote that ended it"
    # would have been false on most of the bills it appeared under.
}

# The same ending where the conferees filed no report saying so: the paragraph
# says what the docket says, which is that no report was signed, or none
# filed, or that the bill died in the committee (conference_failure's word
# for the row). "Reported that it was unable to agree" would be a report the
# record does not have.
CONF_UNABLE_CLOSING = {
    how: ("The committee of conference -- members of both chambers named to "
          "settle the differences between the House and Senate versions -- could "
          f"not agree on one, and {said}. With no version that both chambers had "
          f"accepted, {rest}")
    for how, said, rest in (
        ("unsigned", "no report was signed", "the bill went no further, and it died."),
        ("unfiled", "no report was filed", "the bill went no further, and it died."),
        ("died", "the bill died in the committee", "it went no further."))}


# "No vote was ever taken on it" is a claim, and on 35 of the 111 bills of
# 2025-2026 that carried it the docket records one: HB 243 passed both
# chambers and went to a committee of conference that never reported; CACR 8
# passed the Senate 21-3 and failed in the House, 203-158. Where a chamber
# decided anything, this is what the ending was instead.
SESSION_ENDED_AFTER_VOTES = (
    "It had not finished its passage when the session ended, and the bill died "
    "then. That is a procedural end rather than a decision -- it ran out of "
    "time -- and it would have to be filed again as a new bill in a later term.")


# AND "IT RAN OUT OF TIME" IS A CLAIM TOO, which the record can contradict.
# SSSB 1 of the 2010 special session passed the Senate 14-9 and the House
# voted it down 141-191 an hour before "Died, Session Ended": the paragraph
# above called that "a procedural end rather than a decision". HB 1534 of
# 2016's last row is "Pursuant to House Rule 35e HB 1534 returned to the
# Senate", and HB 1048, HB 1216 and HB 1562 of 2026 were "returned to the House
# per Senate Rule 3-21": sent back, which is not the clock.
SESSION_ENDED_AFTER_FAILED = (
    "The last vote on it was a motion to pass it, which failed, and nothing more "
    "was done on it before the session ended. It would have to be filed again as "
    "a new bill in a later term.")
# Where the record shows something else than time running out -- a measure
# one chamber sent back to the other: what is known, and no more.
SESSION_ENDED_PLAINLY = (
    "It had not finished its passage when the session ended, and the bill died "
    "then. It would have to be filed again as a new bill in a later term.")
# A measure one chamber sent back to the other.
RETURNED_ROW = re.compile(r"\breturned\s+to\s+(?:the\s+)?(?:house|senate)\b", re.I)

# WHERE THE ENDING IS THIS SITE'S READING OF A FINISHED TERM (ended_with_the_
# term), THE PARAGRAPH DATES NOTHING. The General Court never said when these
# died. Seventy House measures of 2021 were reported and never voted on
# before the House's deadline of 9 April 2021, in the first year of their
# term, and "it died when the session ended ... it ran out of time ... a
# later term" gave them a day and a cause the record does not. What is known
# is what was not done.
ENDED_UNVOTED = (
    "Neither chamber ever voted on the bill itself, and the record shows nothing "
    "more done on it. It went no further.")
ENDED_UNFINISHED = (
    "It had not finished its passage, and the record shows nothing more done on "
    "it. It went no further.")
# And where the docket says what stopped it: a chamber asked to suspend its
# rules for a conference report after the deadline, and refusing. "Sen.
# Wheeler Rules Suspension; To Allow C of C Report After Deadline 2/3 nec.,
# MF" is HB 1410 of 2002's last row, the day after "(Conf Comm Report Not
# Signed)"; "MOVED TO SUSP RULES FOR CONF COMM REPT, FAILED 2/3RC(185-133)"
# is SB 437 of 1998's.
CONF_REPORT_NOT_TAKEN_UP = (
    "The {chamber} voted on suspending its rules to take up the committee of "
    "conference's report, and the motion failed. The report was not taken up, and "
    "the bill went no further.")
# And where the House Journal says the conference never reported
# (CONFERENCE_NOT_REPORTED).
CONF_NEVER_REPORTED = (
    "The committee of conference it was last sent to -- members of both chambers "
    "named to settle the differences between the House and Senate versions -- "
    "never reported: {journal}. Nothing more is recorded on the bill, and it went "
    "no further.")

# THE DECISION THE STATUS RESTS ON, WHERE THE HISTORY ABOVE DOES NOT TELL IT.
# The history is told from the rows narrative.py reads, and the status from
# the journey, which reads more of them. SB 95 of 2001 "Died when the
# conference report was rejected" under a history whose last sentence had the
# House adopting the report 196-159: the Senate's "Conference Committee Report
# RC 11Y-13N, Non Adopt" is a row no pattern tells. SB 305 of 2016's ended at
# the conference's meetings, over "Conference Committee Report Not Accepted by
# House pursuant to House Rule 49(j)"; CACR 2 of 2004 "Failed to pass" under
# a floor stage that ends on an amendment adopted, because "OTP/AM failed 3/5
# RC(186-172)" is left untold on purpose (docket_era_1999: no sentence there
# can say it without reading as 186 voting it down). Where the journey's last
# decision is a conference report rejected or a vote to pass that failed, and
# the row it was read from is one the history does not tell (journey's
# `untold`), this says it, in the journey's own words and with its day.
ENDING_UNTOLD = {
    "conf_rejected": ("{when} {chamber} {did}. A conference report has to be adopted by "
                      "both chambers, so the bill went no further."),
    "failed": "{when} {chamber} voted on the motion to {verb} it, and the motion failed{how}.",
}
UNTOLD_FOR = {"Died when the conference report was rejected": "conf_rejected",
              "Failed to pass": "failed"}


def _long_date(iso):
    """"2001-06-26" -> "June 26, 2001", or ""."""
    try:
        d = _date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def untold_ending(label, steps, untold):
    """The paragraph for a status whose deciding row the history does not tell
    (ENDING_UNTOLD), or None. `untold` is the ids of the journey's lines read
    from such a row, as journey() fills it."""
    act = UNTOLD_FOR.get(label)
    last = next((s for s in reversed(steps or []) if s.get("body") in ("H", "S")), None)
    if not act or not last or last.get("act") != act or id(last) not in (untold or ()):
        return None
    chamber = {"H": "the House", "S": "the Senate"}[last["body"]]
    day = _long_date(last.get("date") or "")
    when = f"On {day}" if day else ""
    text = last.get("text") or ""
    if act == "conf_rejected":
        said = ENDING_UNTOLD[act].format(when=when, chamber=chamber,
                                         did=text[:1].lower() + text[1:])
    else:
        head = next((h for h in ("Failed to pass", "Not adopted") if text.startswith(h)), None)
        if head is None:
            return None
        said = ENDING_UNTOLD[act].format(
            when=when, chamber=chamber, verb="adopt" if head == "Not adopted" else "pass",
            how=text[len(head):])
    said = said.strip()
    return {"label": "How it ended", "text": said[:1].upper() + said[1:]}


def closing_stage(label, narr, decided=False, steps=None, inferred=False,
                  untold=None, journal=""):
    """A last paragraph for a bill whose ending the docket never narrates.

    The docket records actions, and a session ending is not an action: it just
    stops. For 111 bills the last line is a committee report and only the
    status page knows the bill died with the term, so a settled red headline
    sat above a history that trailed off mid-sentence.

    `decided` is whether the journey has a chamber deciding anything on the
    bill. Returns None where the history already says it.

    `steps` is the journey's lines, where the caller has them, and `inferred`
    whether the ending is this site's reading of a finished term rather than
    the General Court's word (ended_with_the_term): together they say which
    of the session-ended paragraphs the record bears out. `untold` is the
    journey's lines read from rows the history does not tell, and `journal`
    what the House Journal says of a conference that never reported
    (CONFERENCE_NOT_REPORTED).
    """
    said = untold_ending(label, steps, untold)
    if said:
        return said
    hit = CLOSING.get(label)
    if not hit:
        return None
    guards, text = hit
    told = " ".join(s.get("text", "") for s in (narr or {}).get("stages", [])).lower()
    if any(g in told for g in guards):
        return None
    if inferred and label == "Died when the session ended":
        evs = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
        row = conference_not_taken_up(evs)
        if journal:
            text = CONF_NEVER_REPORTED.format(journal=journal)
        elif row is not None and (row.get("body") or "")[:1].upper() in ("H", "S"):
            text = CONF_REPORT_NOT_TAKEN_UP.format(
                chamber={"H": "House", "S": "Senate"}[row["body"][:1].upper()])
        else:
            text = ENDED_UNFINISHED if decided else ENDED_UNVOTED
    elif decided and label == "Died when the session ended":
        text = SESSION_ENDED_AFTER_VOTES
        last = next((s for s in reversed(steps or []) if s.get("body") in ("H", "S")), None)
        if last and last.get("act") == "failed":
            text = SESSION_ENDED_AFTER_FAILED
        elif any(RETURNED_ROW.search(e.get("raw") or "")
                 for e in (narr or {}).get("events", [])
                 if not e.get("cancelled")):
            text = SESSION_ENDED_PLAINLY
    if label == CONF_UNABLE:
        failed = conference_failure([e for e in (narr or {}).get("events", [])
                                     if not e.get("cancelled")])
        text = CONF_UNABLE_CLOSING.get((failed or ("unable",))[0], text)
    return {"label": "How it ended", "text": text}


def veto_votes(evs):
    """Each chamber's last word on a veto, {body: "law" or "veto"}: "law"
    where it overrode, "veto" where it sustained. veto_outcome reads the
    answer from it, and bill_disposition whether only one chamber has voted."""
    said = {}
    for e in evs:
        raw = (e.get("raw") or "").lower()
        word = (e.get("outcome") or "").lower()
        body = (e.get("body") or "").upper() or "?"
        if "veto sustained" in raw or word == "sustained":
            said[body] = "veto"
        elif ("veto overridden" in raw or "veto overriden" in raw
              or "=veto override=" in raw or word == "overridden"):
            said[body] = "law"
    return said


def veto_outcome(evs):
    """What became of a veto, read per chamber and in order, or None.

    An override needs two-thirds in BOTH chambers, so one chamber sustaining
    ends the bill whatever the other did -- SB 434 of 2026, where the Senate
    overrode 16Y-8N and the House sustained 165-140 the same day. But a
    chamber may reconsider its own vote: HB 542 of 2011 was sustained
    244-130, reconsidered, and overridden 255-112 that morning, and it is
    Chapter 271. So the answer is each chamber's LAST word, and a sustain by
    either of them wins.
    """
    said = veto_votes(evs)
    if not said:
        return None
    if "veto" in said.values():
        return "veto", "Vetoed, override failed"
    return "law", "Veto overridden, became law"


def docket_outcome(narr):
    """The outcome as the DOCKET states it, or None.

    classify_stated already knows the status page lags: its own note records a
    bill whose override had failed still reading VETOED BY GOVERNOR because
    "the general field never catches up with the chamber's". The docket is the
    same official source and does not lag -- it carries a dated line the day
    the vote happens.

    HB 396 is the case. The House sustained the veto on 19 August; the status
    page still says "Senate: PASSED/ADOPTED WITH AMENDMENT", which was true in
    May and is the Senate's last action rather than the bill's state. So a
    dated outcome in the docket outranks a summary field that has not caught
    up, and only for this family, where the lag is known.

    Sustained is tested before overridden for the reason it always is: both
    chambers must override, so one sustaining ends the bill.
    """
    evs = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
    text = " ".join(e.get("raw", "") for e in evs).lower()
    # THE LAST OUTCOME IN THE RECORD, for the reason classify() gives: one
    # chamber sustaining ends the bill (SB 434), but a chamber may reconsider
    # and override an hour later (HB 542 of 2011, Chapter 271).
    outcome = veto_outcome(evs)
    if outcome:
        return outcome
    if ("without the signature of the governor" in text
            or "law without signature" in text):
        return "law", "Became law unsigned"
    # And the signature itself, for the same reason and on the same evidence.
    # The status page carries no governor field for 219 bills whose docket
    # records the day the governor signed them and the chapter number they
    # became -- so they read "Passed one chamber", "Passed, awaiting the
    # governor", "In committee" or, for five of them, "Killed". The page is
    # describing the last thing it was told; the docket is describing what
    # happened.
    if SIGNED_RE.search(text):
        return "law", "Signed into law"
    return None


# A floor motion the chamber ADOPTED that finishes the bill.
#
# Read from the motion code and the action, not from a substring of the whole
# docket. classify() below tests `"inexpedient to legislate" in text`, and that
# phrase appears in every MINORITY report as well -- which is how HCR1, HCR4
# and HCR9 came to read "Killed" when the House had adopted Ought to Pass on
# them 197-156, 195-149 and 204-163.
#
# A WITHDRAWAL THE CHAMBER ADOPTED FINISHES THE BILL TOO (30 September 2026).
# "Withdrawn Under House Rule 38(e) (Rep Cebrowski): MA VV" is HB 641 of
# 2013, and "Withdrawn Pursuant to House Rule 38(e) (Rep Coulombe): MA VV" HB
# 1186 of 2012; both read "In committee", over a docket that withdrew them.
# The action has to BEGIN with the withdrawal -- "REP. HEALY SUB ITL,
# WITHDRAWN; PASSED VV" is a motion withdrawn, not a bill, and "Withdraw From
# Joint Committee" is not "Withdrawn" -- and only an adopted one counts, as
# for every row here: "Persuant to House Rule 39(e), Withdrawn: MF RC
# 160-207" is HB 431 of 2025, which the House then passed. The rule is cited
# with "to" and without -- "Persuant House Rule 39(e), Withdrawn: MF DV" is
# SB 78 of 2025 -- and "Per House Rule 38, Withdrawn from Committee" is a
# committee discharged, not a bill withdrawn.
WITHDRAWN_ACT = re.compile(
    r"^\s*(?:(?:p[eu]r?s?uant(?:\s+to)?|per)\s+(?:house|senate)\s+rule\s+[\w.]+"
    r"(?:\s*\(\w\))?\s*,?\s*)?withdrawn\b(?!\s+from)", re.I)
DISPOSED = [
    (re.compile(r"inexpedient to legislate", re.I), ("done", "Killed")),
    # The motion a chamber carried, never a committee's report of the same
    # words: floor_disposed reads the floor rows a chamber adopted, and HA 2
    # of 2010 and HB 31 of 2023 carry "Ought Not to Pass" on a report alone.
    (re.compile(r"ought not to pass", re.I), ("done", "Killed")),
    (re.compile(r"indefinitely postpone", re.I),
     ("done", "Indefinitely postponed")),
    (re.compile(r"interim study", re.I), ("study", "Referred for interim study")),
    (WITHDRAWN_ACT, ("done", "Withdrawn")),
]
# A reconsideration the chamber carried, as a clause of a floor line:
# "Rep Norelli moved to Reconsider, MA RC(153-150)". See classify().
RECONSIDER_CARRIED = re.compile(r"(?i:\breconsider\w*)[^;]*?\bMA\b")
# Where a bill's record is the House Journal's rather than the General
# Court's files (journal_bills.py, build_data.add_journal_bills).
JOURNAL_SOURCE = "House Journal"


def floor_disposed(narr):
    """The last adopted floor motion that finished the bill, or None.

    A later adopted motion that is NOT a disposal clears an earlier one: a bill
    killed, reconsidered and then passed is not killed, and the docket records
    that as two adopted motions in order.
    """
    out = None
    for e in sorted((narr or {}).get("events", []),
                    key=lambda x: x.get("date") or ""):
        if e.get("cancelled") or e.get("type") != "floor":
            continue
        if (e.get("motion") or "").upper() != "MA":
            continue
        act = e.get("action") or ""
        hit = next((res for pat, res in DISPOSED if pat.search(act)), None)
        out = hit
    return out


def last_decision(narr, bid, rcs=(), term=""):
    """The last decision either chamber made on the measure, as the journey
    reads it -- one of journey()'s lines -- or None where neither decided
    anything.

    The journey is the one reading of a docket that knows a tabling undone by
    a carried removal from the table, a decision reconsidered, a day's
    motions in the order they stood, a suspension of the rules that is not
    the business it would have allowed, and a row wrapped onto the next. What
    ended a measure is asked of it rather than of a second reading of the
    same rows: the tests in classify() that looked for a word among the
    carried motions could not tell CACR 4 of 2009's special order from a
    decision, and so could not see that its last decision was a vote it
    lost.
    """
    steps = [s for s in journey(narr, bid, rcs, term=term)[1] if s["body"] in ("H", "S")]
    return steps[-1] if steps else None


def classify(narr, rcs, prefix="", bid="", term=""):
    """Map a bill to one of four display states, from the docket alone.

    Only the fallback for bills the status page does not cover: 804 of
    33,683 once the archived terms have histories.

    A DECISION IS A MOTION THE CHAMBER ADOPTED, NOT A WORD IN THE DOCKET.
    This read substrings of the whole history, and "inexpedient to
    legislate" is in every MINORITY report, in every committee report
    recommending it, and in the question the chamber then voted down. When
    the 1989-2016 histories arrived that called 36 bills "Killed" that no
    chamber had killed -- including HB 589 of 2002, which died because its
    committee of conference never signed a report. The tests below read the
    events: type "floor", motion MA, and the action the chamber carried,
    which is the same rule floor_disposed() uses.
    """
    evs = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
    text = " ".join(e.get("raw", "") for e in evs).lower()
    # THE LAST VETO OUTCOME, NOT ANY OF THEM. Both chambers must override, so
    # one sustaining ends the bill -- SB 434, where the House sustained and
    # the Senate overrode. But a chamber may reconsider: HB 542 of 2011 was
    # sustained 244-130, reconsidered, and overridden 255-112 the same
    # morning, and it is Chapter 271. Reading "sustained" anywhere called a
    # law a dead bill; reading the last outcome in the record gets both right.
    outcome = veto_outcome(evs)
    if outcome:
        return outcome
    if ("without the signature of the governor" in text
            or "law without signature" in text):
        return "law", "Became law unsigned"
    if SIGNED_RE.search(text):
        return "law", "Signed into law"
    if "vetoed" in text:
        return "veto", "Vetoed"
    # A WITHDRAWAL THE CHAMBER ADOPTED, where it is the last disposal the
    # floor carried (floor_disposed, and WITHDRAWN_ACT above DISPOSED). HB 641
    # of 2013 and HB 1186 of 2012 read "In committee" without this.
    _w = floor_disposed(narr)
    if _w and _w[1] == "Withdrawn":
        return _w
    # AND A WITHDRAWAL THE DOCKET RECORDS ON A ROW OF ITS OWN, with no vote
    # (narrative.WITHDRAWN_ROW, event type "withdrawn"): "Withdrawn" and
    # "Withdrawn 11/30/2011" on three House bills of 2012, "Read in January
    # 4, 2012 and Withdrawn" on a petition -- and "Withdrawn Prior to
    # Introduction" on four of 2010, which says so in the row's own words,
    # because a bill never introduced was never "withdrawn" from anything a
    # reader would take that word to mean. Each read "In committee". Only
    # where it is the last thing the record says the bill did: a floor
    # decision after it would be the answer.
    _gone = [i for i, e in enumerate(evs) if e.get("type") == "withdrawn"]
    if _gone and not any(e.get("type") == "floor" for e in evs[_gone[-1] + 1:]):
        return "done", (WITHDRAWN_PRIOR if evs[_gone[-1]].get("before_introduction")
                        else "Withdrawn")
    # A BILL ONLY EVER PROPOSED. HB 3 of the 2006 special session has one
    # row, "Proposed bill for special sesssion.", and no introduction: it was
    # in no committee, and "In committee" is what the foot of this function
    # would have called it.
    if evs and all(e.get("type") == "proposed" for e in evs):
        return "done", PROPOSED_ONLY
    # AN INTRODUCTION THE DOCKET ENTERS AND THE HOUSE JOURNAL DOES NOT HAVE
    # (NOT_INTRODUCED). Read "In committee", of a committee nothing was
    # referred to.
    if journal_not_introduced(narr):
        return "done", NOT_INTRODUCED
    # A DISPOSAL THE CHAMBER RECONSIDERED IS NOT ONE. HB 323 of 2005 read
    # "Killed": the House adopted Inexpedient to Legislate on 23 March, 164-153,
    # and on 30 March reconsidered it, 153-150, voted the kill down and passed
    # the bill, which went on to die in a committee of conference. Reading
    # "inexpedient to legislate" anywhere among the carried motions counted a
    # kill the House had undone. So a carried disposal is dropped where the
    # same chamber later carried a motion to reconsider AND then passed the
    # bill, and what followed decides. Both are needed: HB 1267 of 2012's
    # "Special Order (Reconsideration Motion)" only scheduled a motion that
    # then failed, and HB 666 of 1997 reconsidered its kill and killed the
    # bill again in a row the parser reads in two halves.
    #
    # The reconsideration can also be a clause of the passage's own line. The
    # House typed 30 March 2005 as one entry, "Rep Norelli moved to
    # Reconsider, MA RC(153-150); ITL ML DIV(149-151); ...; Passed with Am
    # VV", which the 1999-2006 docket reader joins back together from the
    # rows the database cut it into, and a whole line is told by its last
    # carried question, the passage. So a passage whose own line carried a
    # reconsideration before it undoes the disposal too.
    fl = [e for e in evs if e.get("type") == "floor"
          and (e.get("motion") or "").upper() == "MA"]
    fl = [e for _i, e in sorted(enumerate(fl),
                                key=lambda x: (x[1].get("date") or "", x[0]))]
    passage = re.compile(r"ought to pass|\botp\b|\bpassed\b", re.I)

    def undone(i, e):
        a = (e.get("action") or "").lower()
        if not re.search(r"inexpedient to legislate|ought not to pass|interim study"
                         r"|refer for study|indefinitely postpone", a):
            return False
        body = e.get("body") or ""
        for j in range(i + 1, len(fl)):
            if (fl[j].get("body") or "") == body and \
                    RECONSIDER_CARRIED.search(fl[j].get("raw") or "") and \
                    passage.search(fl[j].get("action") or ""):
                return True
            x = (fl[j].get("action") or "").lower()
            if (fl[j].get("body") or "") != body or not re.search(r"\breconsider", x) \
                    or re.match(r"\s*special order", x):
                continue
            return any((y.get("body") or "") == body and re.search(
                r"ought to pass|\botp\b|\bpassed\b", (y.get("action") or ""), re.I)
                for y in fl[j + 1:])
        return False
    carried = " | ".join((e.get("action") or "").lower()
                         for i, e in enumerate(fl) if not undone(i, e))
    if "inexpedient to legislate" in carried or "ought not to pass" in carried:
        return "done", "Killed"
    if re.search(r"interim study|refer for study", carried):
        # Its own kind, not "done". A bill sent to interim study has not been
        # killed -- it is parked for the committee to work on out of session,
        # and it can come back. Grouping it with bills that were voted down
        # said something untrue about it every time.
        return "study", "Referred for interim study"
    if "indefinitely postpone" in carried:
        return "done", "Indefinitely postponed"
    # A MOTION TO PASS THAT FAILED IS AN ANSWER. Where nothing else carried
    # after it, the chamber voted and the bill did not pass -- which is what
    # happened to every constitutional amendment that fell short of three
    # fifths. Until the floor pattern could read "MF RC 202-171 Lacking
    # Necessary Three-Fifths Vote", those bills had no outcome at all, and 78
    # of them took the word "Killed" from a MINORITY report.
    if not carried and any(
            e.get("type") == "floor" and (e.get("motion") or "").upper() in ("MF", "ML")
            and re.search(r"ought to pass|passage", e.get("action") or "", re.I)
            for e in evs):
        return "done", "Failed to pass"
    # With the article and without: "Died on Table, Session ended" is the
    # current docket's row and "Died on the Table" the House's of 2010 and
    # 2015, which this did not match.
    if re.search(r"died on (?:the )?table", text):
        return "done", "Died on the table"
    # THE SESSION ENDING IS AN ENDING. The docket's own last line says so --
    # "Died, Session ended 10/10/2024" -- and without this a bill whose kill
    # motion FAILED fell through to "In committee": CACR 17 of 2024, where
    # Inexpedient to Legislate lost 174-186 and Ought to Pass then lost
    # 180-183 for want of three fifths. The same words STATED uses.
    if "session ended" in text or "died, session" in text:
        return "done", "Died when the session ended"
    # A CHAMBER'S OWN RULE IS A DECISION, even though the clerk records it
    # with no motion code: "Inexpedient to Legislate, Senate Rule 3-23,
    # Adjournment" is how a bill left on the table dies at adjournment. 80
    # bills of 2017-2026 say exactly that and nothing else.
    # SENATE RULE 3-23 IS THE TABLE'S: it ends what is still lying there, and
    # this site's words for that are "Died on the table", on 669 bills whose
    # field says DIED ON THE TABLE or LAID ON TABLE over the same row. SB 14,
    # SB 20, SB 113, SB 227 and SB 304 of 2025 carry the row under a blank
    # field and read "Killed", of bills no chamber voted to kill: each was
    # laid on the table by a carried motion and never taken off it.
    if TABLE_DEATH.search(text):
        return "done", "Died on the table"
    if re.search(r"inexpedient to legislate,\s*(?:senate|house)\s+rule", text):
        return "done", "Killed"
    # THE LAST DECISION ON THE MEASURE WAS A MOTION TO PASS IT THAT FAILED.
    # The test above answers only where no motion of any kind carried, and a
    # carried special order, reconsideration, recommittal or tabling since
    # undone is not a decision on the measure: CACR 4 of 2009 was special
    # ordered on 12 February and lost 193-176 on the 18th, "Lacking Necessary
    # Three-Fifths", and read "In committee"; CACR 26 of 2008 lost, was
    # reconsidered and lost again; CACR 8 and CACR 11 of 2012 were retained,
    # lost, were tabled and taken off the table, and read "Retained in
    # committee"; CACR 2 of 2004's "OTP/AM failed 3/5 RC(186-172)" followed an
    # amendment it adopted. The LAST decision, of any kind: a tabling that
    # stood (HB 1681 of 1998, HB 1176 of 2026), a kill, a study, a
    # postponement or a recommittal after the vote is the answer instead, and
    # so is the docket's own row for the end, tested above.
    last = last_decision(narr, bid or prefix, rcs, term)
    if last and last["act"] == "failed":
        return "done", "Failed to pass"
    # AND A TABLING THAT STOOD IS WHERE THE MEASURE IS. Only a status field
    # saying LAID ON TABLE gave that label, and a bill tabled under a field
    # that says something STATED does not list fell through: HB 1668, HB 1679
    # and HB 1681 of 1998, three of the school-funding tax bills the House
    # laid on the table on 24 September 1998 ("LAID ON THE TABLE, REP HAGER MA
    # DIV(193-109)"), read "Committee report filed" from the field REPORT
    # FILED; SB 476, SB 566 and SB 651 of 2026, tabled by the Senate under a
    # blank field, read "In progress". After the tests above, which read a
    # docket's own row for a death on the table, the term's end or a
    # chamber's rule: SB 14 of 2025 was tabled and then killed by Senate Rule
    # 3-23, and that row is its ending.
    if last and last["act"] == "tabled":
        return "active", "Laid on the table"
    # RETAINED IS WHERE A BILL WAS, NOT WHERE IT IS once anything came after.
    # Read as "any retention anywhere" it called 21 bills "Retained in
    # committee" that had since been reported, passed both chambers and gone
    # to a committee of conference -- HB 589 of 2002 among them.
    # Moved on means the chamber then passed it, or the other chamber took it
    # up; a later vote that failed leaves the answer where it was.
    ret = [i for i, e in enumerate(evs) if e.get("type") == "retained"]
    if ret:
        where = evs[ret[-1]].get("body")
        moved_on = any(
            (e.get("type") == "floor" and (e.get("motion") or "").upper() == "MA"
             and re.search(r"ought to pass|adopted", e.get("action") or "", re.I))
            or (e.get("body") and where and e.get("body") != where)
            for e in evs[ret[-1] + 1:])
        if not moved_on:
            return "active", "Retained in committee"
    # THE LAST THING THE RECORD SAYS. Where a committee has reported and no
    # floor vote is on the page, that is the honest answer: 51 bills of 2021
    # carry a majority report of Inexpedient to Legislate, a minority report
    # the other way, and nothing after them. Reading the majority's
    # recommendation as the chamber's decision called them "Killed"; reading
    # nothing called them "In committee", which is where they are not.
    if evs and evs[-1].get("type") == "report" and not any(
            e.get("type") == "floor" for e in evs):
        return "active", "Committee report filed"
    # And a resolution of one chamber "Introduced and Adopted", which the
    # clerk writes with no motion code: HR 13 of 2007 read "In committee"
    # over the one line of its docket that adopted it.
    # And the 1989-1998 reader's word for it: "REP MAVIGLIO MOVED LOT, ML
    # RC(74-250); ADOPTED VV" is told as the action "Adopt", carried. Every
    # other resolution of those years states PASSED/ADOPTED in its fields and
    # never reaches this line; HR 69 of 1992 has a docket and no fields, and
    # read "In committee" beside a journey that had the House adopting it.
    adopted_floor = any(
        (e.get("type") == "floor" and (e.get("motion") or "").upper() == "MA"
         and re.search(r"ought to pass|adopted", e.get("action") or "", re.I))
        or (prefix in SINGLE_CHAMBER
            and re.match(r"\s*introduced\s+and\s+adopted\b", e.get("raw") or "", re.I))
        or (prefix in SINGLE_CHAMBER and e.get("type") == "floor"
            and (e.get("motion") or "").upper() == "MA"
            and re.match(r"\s*adopt\s*$", e.get("action") or "", re.I))
        for e in (narr or {}).get("events", []) if not e.get("cancelled"))
    if adopted_floor or any(r.get("passed") for r in rcs):
        # A resolution of one chamber that has carried a vote is finished.
        # There is no other chamber for it to be in progress towards.
        if prefix in SINGLE_CHAMBER:
            return "adopted", f"Adopted by the {SINGLE_CHAMBER[prefix]}"
        return "active", "In progress"
    return "active", "In committee"


# What the status box says of a one-chamber measure its chamber carried: a
# resolution, and a House bill of intent, which is not one and whose docket
# says PASSED.
ONE_CHAMBER_DONE = ("Adopted. A resolution of one chamber goes no further",
                    "Passed by the House, which is as far as a House bill of intent goes")


def next_step(narr, bill, prefix=""):
    """Plain-language 'what happens next', from the last recognised event."""
    evs = (narr or {}).get("events", [])
    if not evs:
        return "No recorded action yet"
    last = evs[-1]
    raw, t = last.get("raw", "").lower(), last.get("type")
    # A veto outcome is read from the WHOLE history, not just the last line.
    # An override is voted in each chamber separately, so the final line is one
    # chamber's answer rather than the bill's, and taking it alone reported
    # SB 434 as law when the House had already sustained the veto.
    every = " ".join(e.get("raw", "").lower() for e in evs)
    if "veto sustained" in every:
        return "Vetoed. The override failed and the bill is dead"
    if "veto overridden" in every:
        return "Vetoed, then overridden. It becomes law"
    if ("without the signature of the governor" in every
            or "law without signature" in every):
        return "Became law without the governor's signature"
    # THE SIGNATURE, LIKE THE VETO ABOVE, IS READ FROM THE WHOLE HISTORY.
    # Read off the last line alone it was missed whenever anything followed
    # it -- an effective-date row, a chaptering line, a same-day row that
    # sorts after it -- and 185 bills whose chip said "Signed into law" had a
    # status box reading "In progress" or "Enrolled. Pending the governor's
    # signature", 31 of them in the current term.
    if SIGNED_RE.search(every):
        return "Signed into law"
    if "vetoed" in raw:
        return "Vetoed. Awaiting a possible override vote"
    # A resolution of one chamber is finished the moment that chamber adopts
    # it, and the line recording that is not always the last one: HR16's floor
    # vote is followed by the roll call on the amendment it adopted, so the
    # chain below read "amendment" and answered "In progress" for a resolution
    # the House had passed a month earlier.
    if prefix in SINGLE_CHAMBER and any(
            e.get("type") == "floor" and (e.get("motion") or "").upper() == "MA"
            and re.search(r"ought to pass|adopted", e.get("action") or "", re.I)
            for e in evs if not e.get("cancelled")):
        return ONE_CHAMBER_DONE[prefix == BILL_OF_INTENT]
    if t == "introduced":
        return f"Pending public hearing in {bill.get('house_committee') or 'committee'}"
    if t == "hearing":
        return "Pending executive session in committee"
    if t == "exec":
        return "Pending a committee report"
    if t == "report":
        return "Pending a vote of the full chamber"
    if t == "floor":
        if prefix in SINGLE_CHAMBER:
            return ONE_CHAMBER_DONE[prefix == BILL_OF_INTENT]
        return "Pending action in the other chamber"
    if t == "enrolled":
        if prefix == "CACR":
            return "Goes to the voters at the next general election"
        if prefix in NO_GOVERNOR:
            return "Adopted by both chambers. It does not go to the governor"
        return "Enrolled. Pending the governor's signature"
    if t == "retained":
        return "Retained in committee for further work"
    if t == "died":
        return "Died when the session ended"
    return "In progress"


def station_for_proceeding(p, bid, segs, marks):
    """One committee proceeding -- a hearing or an executive session -- as the
    station the page draws.

    Split out of main() with station_for_floor below it. The two used to sit
    ninety lines apart inside one 955-line function, which is how a lookup
    added to one of them silently missed the other.
    """
    seg = None
    for s in segs.get(p.get("video_id", ""), []):
        if s.get("bill", "").upper() == bid and s.get("kind") == p["proceeding"]:
            seg = s
            break
    # THE RECORDINGS THIS SITTING COULD BE, where the matcher declined to
    # pick one of them. build_manifest writes the ids whenever more than one
    # recording of the committee exists that day; build_proceedings carries
    # them. Empty on every row where one recording was chosen, and on every
    # row from a day that had only one.
    cands = [v for v in str(p.get("candidate_ids") or "").split(" | ") if v]
    # Five states, and the two in the middle are the point. A recording
    # matched to the proceeding with only an approximate starting point is
    # still far more useful than no link at all: the reader scrubs a few
    # minutes instead of hunting through 331 videos. Exact timestamps
    # are an upgrade to this, not a precondition for it.
    #
    # `candidates` is the same argument one level up -- the day and the
    # committee are known and the tape is not. It is tested before the date,
    # because "recordings of this committee exist that day" is a fact about
    # the index and STREAM_START, the day the General Court's YouTube
    # channels begin, is a fact about the calendar; nothing reaches both,
    # since the index holds nothing older than the channels. 317
    # proceedings of 100,556 are in it: 236 Finance, whose divisions stream
    # separately and which the docket does not tell apart, and 81 whose
    # scheduled minute fell inside more than one stream. They used to fall
    # to "novideo", which app.js draws as "No recording matched to this
    # proceeding." -- a claim this site's own manifest contradicts.
    if seg and seg.get("located"):
        state, start = "located", seg["start"]
    elif p.get("video_id"):
        state, start = "approximate", None
    elif cands:
        state, start = "candidates", None
    elif p["sched_date"] < STREAM_START:
        state, start = "prestream", None
    else:
        state, start = "novideo", None
    # A stated boundary replaces the estimate outright.
    # The filter exists to stop a hearing's boundary being handed to an
    # executive session on the same recording. A marker that names the
    # proceeding is checked against the kind; one that does not -- a weak
    # marker with no noun, or the bare word "session", which one chair uses
    # for what the docket calls a public hearing -- makes no claim to check,
    # so it is kept as a fallback rather than discarded.
    #
    # Two passes, in that order. Discarding the ambiguous ones outright cost
    # HB1123 its boundary: the chair said "we're opening the session on House
    # Bill 1123", the docket calls it a public hearing, neither word contained
    # the other, and the only quotation on the recording was thrown away in
    # favour of a clustered guess a minute and a half out.
    AMBIGUOUS = {"", "session"}

    # THE LAST WORD IS NOT THE DISTINGUISHING WORD. An executive session, a
    # work session and a subcommittee work session all end in "session", so a
    # last-word test says a marker for one is a marker for another. That was
    # harmless only while segment_markers mislabelled every one of them as the
    # bare word "session", which AMBIGUOUS caught and demoted. Fixing that
    # labelling on 2,580 markers turned the weakness live: measured against the
    # rebuilt markers, 460 stations would take a marker of the wrong kind --
    # 301 an executive session's moment onto a work session, 159 the reverse.
    # On one recording those are different times, so each is a wrong moment
    # published as a stated one.
    #
    # "exec" is what chairs actually say -- "going to open up the exec session
    # for HB 251" -- and "exact" is what the captions make of it, 402 times.
    # Both are the same sitting and both normalise here; the captions garble
    # bill numbers the same way, which is why nothing on this site quotes them.
    def _kind_key(s):
        s = re.sub(r"[^a-z ]", " ", str(s or "").lower())
        s = re.sub(r"\b(?:exec|exact)\b", "executive", s)
        for k in ("conference", "floor", "executive", "work", "hearing"):
            if k in s:
                return k
        return ""

    def _matches(cand):
        want = str(p.get("proceeding") or "").lower()
        what = str(cand.get("what") or "")
        if not want or not what or what in AMBIGUOUS:
            return None
        kw, kp = _kind_key(what), _kind_key(want)
        # Neither recognisable: no claim to check, so it stays a fallback
        # rather than becoming a match or a refusal.
        if not kw or not kp:
            return None
        return kw == kp

    usable = [c for c in (marks.get(p.get("video_id") or "") or {}).get(bid, [])
              if isinstance(c, dict) and c.get("start") is not None]
    said = next((c for c in usable if _matches(c) is True), None)
    if said is None:
        said = next((c for c in usable if _matches(c) is None), None)

    # The clustering's end, but only where it is describing the same span.
    #
    # A stated start replaces the clustered one outright, and it does that
    # precisely in the cases where the two disagree. Reaching past it for the
    # clustered END then pairs a quotation with an inference about somewhere
    # else in the recording. 2,732 proceedings did that: 429 ended at or
    # before the start they were pinned to -- which the page dropped without a
    # word, so a wrong number became a missing one in silence -- and 743 more
    # came from a placement further from the chair's than the clustering's own
    # tolerance allows, giving the reader a duration that was never measured
    # from that point.
    #
    # The threshold is the segment's own tolerance rather than one invented
    # here: the aligner already says how sure it is, from 30 seconds where the
    # evidence was thick to half an hour where it was thin, and a placement
    # inside that is the same placement. Where it is not, the proceeding keeps
    # its stated start and no end, which the page already draws as "from
    # 1:19:26".
    seg_end = None
    if seg and seg.get("located") and seg.get("end") is not None:
        anchor = said["start"] if said else seg.get("start")
        near = (abs(seg["start"] - anchor) <= (seg.get("tolerance") or 300)
                if said else True)
        if anchor is not None and seg["end"] > anchor and near:
            seg_end = seg["end"]

    # WHERE THE END CAME FROM, AND WHETHER IT IS WORTH PUBLISHING.
    #
    # segment_markers.py records how it decided each end and the site threw
    # that away, so a chair announcing "we are closed on 1118" and the moment
    # the NEXT bill happened to be opened arrived on the page as the same
    # kind of fact. Scored against 43 hand-timed proceedings:
    #
    #   the chair closed it        10 scored, median 0m 04s, 10/10 in a minute
    #   last mention of the bill    8 scored, median 0m 59s,  5/8
    #   next boundary               7 scored, median 29m 06s, 1/7
    #
    # An end taken from the next boundary inherits every error in the
    # placement of the item after it, and it does so in both directions:
    # HB84's hearing was published as 101 seconds against the 29 minutes it
    # ran, SB659's was stretched 94 minutes past where it finished. There is
    # no offset that repairs a thing that fails both ways, and 2,338 segments
    # -- 43% of every end this site has -- come from it.
    #
    # So it is not published. The proceeding keeps its start, which is good
    # to four seconds where a chair spoke it, and the page draws it as "from
    # 1:19:26" exactly as it already does for a proceeding that never had an
    # end. end_from still records what the candidate was, so a null end here
    # reads as "we had a number and would not stand behind it" rather than as
    # "we found nothing".
    UNPUBLISHABLE = {"next boundary"}
    end_from = None
    end_val = None
    if said and said.get("end") is not None:
        end_from = said.get("end_from") or "the chair closed it"
        end_val = said["end"]
    elif seg_end is not None:
        end_from = "clustered"
        end_val = seg_end
    if end_from in UNPUBLISHABLE:
        end_val = None

    # The state the page will actually see, computed once: the key below has
    # to agree with it, and an inline ternary in two places is how two things
    # that must agree stop agreeing.
    shown = "stated" if said else state
    return {
        "when": p["sched_date"], "time": p.get("sched_time"),
        "what": p["proceeding"], "committee": p.get("committee"),
        # Which chamber's committee, from proceedings.csv's own
        # column. A House bill is heard by a Senate committee too,
        # so this cannot be read off the bill number.
        "body": p.get("body"),
        "venue": p.get("venue"), "video_id": p.get("video_id"),
        "watch": p.get("watch_url"), "predicted": p.get("predicted_offset"),
        "start": said["start"] if said else start,
        "state": shown,
        # ONLY WHERE NOTHING WAS CHOSEN. A row that got a pick carries these
        # ids too -- build_manifest writes them whenever the day held more
        # than one recording, and 246 of the 563 were resolved by the clock
        # -- and shipping them beside a chosen recording would invite the
        # page to offer a reader alternatives to a match this site stands
        # behind. Absent rather than null on the other 100,239 stations, the
        # way "archived" is absent on a current bill: every key is paid for
        # 33,683 times.
        **({"candidate_ids": cands} if shown == "candidates" else {}),
        # The aligner sets a tolerance per segment from how much
        # evidence it had -- 3 minutes with many bill mentions, 30 with
        # a short span and few. Dropping it here made every hearing on
        # the site claim the same +/-5 minutes, understating the good
        # ones and, worse, overstating the weak ones.
        "tolerance": (5 if said else
                      (seg.get("tolerance") if seg else None)),
        "short": bool(seg.get("short")) if seg else False,
        # The aligner produces a span, not a point. Showing only the
        # start throws away half of it -- and the duration is what tells
        # a reader whether a proceeding was a five-minute executive
        # session or a two-hour hearing before they click anything.
        # A stated close outranks a clustered one: four seconds at the
        # median against whatever the cluster's tail happened to be.
        "end": end_val,
        # WHAT IT SAYS, NOT WHETHER THERE IS ONE. This was
        # bool(said and said.get("end")), which is "an end exists" -- so
        # SB659's end, which is the second HB1815 was opened 94 minutes after
        # the hearing finished, was recorded as stated by the chair. It is
        # true now only where the close itself was spoken: segment_markers
        # leaves end_from unset in exactly that case, and those score four
        # seconds at the median against a stopwatch.
        "end_stated": bool(said and said.get("end") is not None
                           and not said.get("end_from")),
        # How the end was decided, or -- where end is null -- what the
        # candidate was that this refused to publish.
        "end_from": end_from,
        "candidate": seg["start"] if seg and not seg.get("located") else None,
        # Which ends of this span were stated by the chair rather than
        # inferred, written by apply_markers.py. The page does not say
        # so in words -- the tolerance carries that -- but it decides
        # the tolerance's unit and how early the player opens, and it
        # is what a methodology page would count.
        #
        # Per end, not per segment: a Senate chair announces the close
        # and not the opening, so a proceeding can have a quoted end
        # and an estimated start.
        #
        # The caption lines themselves stay in work/<id>/segments.json
        # as the audit trail and are not shipped to the browser.
        # Seconds, not minutes: a boundary the chair said is good to
        # about a second, and calling that "+/- 1 min" would understate
        # it as badly as the old tolerances overstated theirs.
        "start_stated": bool(said) or (bool(seg.get("start_stated"))
                                       if seg else False),
        # The words are deliberately NOT published. Captions mangle
        # bill numbers constantly, and a garbled quote presented as the
        # chair's own words is a transcription error wearing the
        # clothes of a citation. How it was found is kept, because that
        # is a fact about this site's method rather than a claim about
        # what anyone said.
        "said_how": said.get("how") if said else None,
        "end_stated_cluster": bool(seg.get("end_stated")) if seg else False,
    }


def fold_conference_notices(rows):
    """One bill's floor rows, with a conference's notice folded into its recording.

    A committee of conference that was noticed on a docket and recorded on a
    channel is two rows of proceedings.csv: the docket's, with the time and
    the room and no recording, and the floor index's, with the recording and
    neither. Each became a station, so the bill page drew the one sitting
    twice on the same day -- once as "No recording matched to this
    proceeding." at 09:30 in LOB 206-208, and once as the recording with no
    time -- and HB 1709's of 26 May 2026, which is on two recordings, three
    times. 61 Senate bill-days were drawn so, SB 108's of 13 June 2025 among
    them, and reading the House's notices too (docket_parser) made it 159.

    So where a bill has a recorded conference on a day, a notice of a
    conference that day with no recording is the same sitting: it is dropped,
    and its time and room go onto the recorded row, which has none of its own.
    Where there are several notices the earliest time is the one the sitting
    was called for. A notice no recording covers is left as it is, and draws
    "No recording matched", which is true. Nothing else is touched: a floor
    debate is never folded, and neither is a conference on another day.
    """
    conf = "committee of conference"
    recorded = {f.get("date") for f in rows
                if f.get("kind") == conf and f.get("video_id")}
    notice = {}
    for f in rows:
        if (f.get("kind") == conf and not f.get("video_id")
                and f.get("date") in recorded):
            cur = notice.get(f["date"])
            if cur is None or (f.get("time") or "~") < (cur.get("time") or "~"):
                notice[f["date"]] = f
    if not notice:
        return list(rows)
    out = []
    for f in rows:
        if f.get("kind") != conf or f.get("date") not in notice:
            out.append(f)
        elif f.get("video_id"):
            n = notice[f["date"]]
            out.append(dict(f, time=f.get("time") or n.get("time") or "",
                            venue=f.get("venue") or n.get("venue") or ""))
    return out


def station_for_floor(f, bid, marks):
    """One floor appearance as a station.

    Returns a finished dict. The consent case and the stated-boundary upgrade
    are applied before returning, rather than by reaching back into
    stations[-1] after appending.
    """
    precise = f.get("precise") and f.get("debate_end")
    # NO RECORDING AT ALL. 1,613 committee-of-conference sittings are on the
    # docket and on neither of the General Court's channels, and they came
    # through here as "floor_dated" -- which app.js draws as a player: an
    # embed of an empty id and an "Open on YouTube" link to watch?v=, on
    # sittings from 1990 on. They take the two states a committee sitting
    # with nothing to play takes, split on the same date: older than the
    # channels, or since them and unmatched. And they keep the time and the
    # room the docket gives, which proceedings.csv has for all but one and
    # the page used to drop.
    if not f.get("video_id"):
        # The index's own word for what this is, as below.
        kind = f.get("kind") or "floor debate"
        return {
            "when": f["date"], "time": f.get("time") or None,
            "what": kind,
            "committee": ("House" if f.get("body") == "H" else "Senate"
                          ) if kind == "floor debate" else None,
            "venue": f.get("venue") or None, "video_id": "", "watch": None,
            "predicted": None, "start": None, "debate_end": None,
            "window_start": None,
            "motions": f.get("motions", []), "tallies": f.get("tallies", []),
            "state": ("prestream" if (f.get("date") or "") < STREAM_START
                      else "novideo"),
            "candidate": None}
    # A conference's time and room, where fold_conference_notices put its
    # docket notice's onto the recording. A floor-index row carries neither
    # of its own, so on every other recorded row these are None as they were.
    conf_when = (f.get("time") or None, f.get("venue") or None) if (
        f.get("kind") == "committee of conference") else (None, None)
    if f.get("whole_video"):
        # The title names the bill, so the entire recording is this
        # proceeding. No timestamp to estimate and none needed.
        return {
            "when": f["date"], "time": conf_when[0],
            "what": f.get("kind", "committee of conference"),
            "committee": None, "venue": conf_when[1],
            "video_id": f["video_id"],
            "watch": f"https://www.youtube.com/watch?v={f['video_id']}",
            "predicted": None, "start": 0, "debate_end": None,
            "window_start": None, "motions": [], "tallies": [],
            "title": f.get("title", ""),
            "state": "whole_video", "candidate": None}
    # THE INDEX'S OWN WORD FOR WHAT THIS IS, not "floor debate" for everything
    # that is not a whole recording. build_floor_index.py writes three kinds --
    # "floor debate", "committee of conference" and "recording naming this
    # bill" -- and only the whole_video branch above read it, so a conference
    # was labelled a floor debate whenever its recording named more than one
    # bill. 63 of the 114 recordings that carry a kind name several, and the
    # page called 191 committee-of-conference proceedings "House Floor Debate"
    # and 12 more the same.
    #
    # And no chamber on those, the way the whole_video branch already does it:
    # a committee of conference is both chambers sitting together, so
    # "House Committee Of Conference" would be a second wrong claim under the
    # first. f["body"] is the chamber whose channel carried the recording, not
    # the body that met.
    kind = f.get("kind") or "floor debate"
    st = {
        "when": f["date"], "time": conf_when[0],
        "what": kind,
        "committee": ("House" if f.get("body") == "H" else "Senate"
                      ) if kind == "floor debate" else None,
        "venue": conf_when[1], "video_id": f["video_id"],
        "watch": (f"https://www.youtube.com/watch?v={f['video_id']}"
                  f"&t={max(int(f.get('window_start') or 0) - 60, 0)}s"),
        "predicted": None,
        "start": (max(f.get("window_start", 0),
                      f["debate_end"] - 1800) if precise else None),
        "debate_end": f.get("debate_end") if precise else None,
        "window_start": f.get("window_start") if precise else None,
        "motions": f.get("motions", []), "tallies": f.get("tallies", []),
        "state": "floor_precise" if precise else "floor_dated",
        "candidate": None,
    }
    # The clerk reads a committee report to open every bill, and
    # segment_markers.py finds it. That is the START of the debate --
    # exact, and from the clerk's own words. Without it the player fell
    # back to the window, which opens at the PREVIOUS bill's roll call
    # and can be half an hour of other business away.
    #
    # This branch once did not consult the markers at all: they were
    # found, written, and ignored, because floor stations were built in
    # one place and the lookup was added in another, ninety lines away
    # in the same function. The same manifest-and-floor-index split, for
    # the fifth time. Both halves are now one short function each, and
    # the station is finished before it is returned rather than adjusted
    # through stations[-1] after the fact.
    # A bill never named on its own floor recording passed on the
    # consent calendar: adopted as part of a block, never read out,
    # never debated. Offering to play a nine-hour session for it invites
    # a reader to listen for something that is not there.
    if bid in (marks.get("_absent") or {}).get(f.get("video_id") or "",
                                               []):
        st["state"] = "consent"
        st["start"] = None
        # Not a debate. The heading read "House floor debate" over a paragraph
        # explaining the bill was never debated, which is the page contradicting
        # itself in two lines.
        st["what"] = "consent calendar"
        return st

    said_f = None
    for cand in (marks.get(f.get("video_id") or "") or {}).get(bid, []):
        if not isinstance(cand, dict) or cand.get("start") is None:
            continue
        if str(cand.get("what") or "") not in ("", "floor debate"):
            continue
        end = f.get("debate_end")
        if precise and end and not (0 <= end - cand["start"] <= 7200):
            continue      # not this sitting's debate
        said_f = cand
        break
    if said_f:
        st["start"] = said_f["start"]
        st["debate_start"] = said_f["start"]
        st["start_stated"] = True
        st["said_how"] = said_f.get("how")
        if not precise and said_f.get("end"):
            st["debate_end"] = said_f["end"]
            st["state"] = "floor_stated"
    return st


def withhold_late_captions(segs, marks, work, summary=caption_span.SUMMARY):
    """Take every time read off a caption track that is out of step with its
    recording out of both sources, before a station is drawn from either.

    The chair's stated boundary and the clustering estimate are both read off
    the captions, so a track that starts an hour late puts both an hour early.
    When it was measured, that was 74 published starts on nine recordings, 55
    of them drawn as the moment the chair opened the proceeding. caption_span.py
    holds the measurement and the line.

    What is left is the schedule, which comes from the stream's own clock: the
    page opens the recording five minutes before the scheduled time and says
    the start was not identified, which is true. The consent calendar goes
    too -- "never named on the recording" is read off the same track, and a
    track that stops short of its recording may simply not reach the bill.

    ON THE NIGHTLY'S MACHINE there are no caption files, and `summary` --
    caption_spans.json, written where they are -- answers for each recording
    instead. With a summary in use, a recording that has times and neither a
    caption file nor an entry is withheld as well: nothing here can say its
    track is in step, and a summary that fell behind must cost a "start not
    identified", never a start an hour early.
    """
    vids = set(segs) | {k for k in marks if not k.startswith("_")}
    spans = caption_span.load_summary(summary)
    rep = {}
    late, compared, undated = caption_span.out_of_step(vids, work, spans=spans,
                                                       report=rep)
    unknown = rep.get("unsummarised") or []
    # A caption job that did not rewrite the summary leaves a handful of new
    # recordings unknown, and withholding them is the right answer. Most of
    # them unknown is not a summary that fell behind -- it is an empty one, or
    # another machine's -- and a site with every timestamp withdrawn is a
    # failed build, not a cautious one.
    if spans is not None and len(unknown) > max(25, len(vids) // 20):
        raise SystemExit(
            f"{summary} knows {rep.get('from_summary', 0):,} of the "
            f"{len(vids):,} recordings with times, and {len(unknown):,} have "
            f"neither an entry there nor a caption file under {work}/. That is "
            "the wrong summary or an empty one. Rewrite it where the captions "
            "are: python3 src/hearings/caption_span.py --write")

    def read_off(vs):
        return (sum(len(c) for v in vs for c in (marks.get(v) or {}).values()),
                sum(1 for v in vs for s in (segs.get(v) or []) if s.get("located")))
    said, placed = read_off(late)
    u_said, u_placed = read_off(unknown)
    for v in list(late) + list(unknown):
        segs.pop(v, None)
        marks.pop(v, None)
        for side in ("_absent", "_sequence"):
            if isinstance(marks.get(side), dict):
                marks[side].pop(v, None)
    print(f"caption tracks: {compared:,} recordings compared with the length "
          "YouTube published")
    if rep.get("from_summary"):
        print(f"  {rep['from_summary']:,} of them answered by {summary}: no "
              f"caption file for them under {work}/ on this machine")
    if unknown:
        print(f"  {len(unknown):,} have times and neither a caption file under "
              f"{work}/ nor an entry in {summary}, so nothing here says their "
              f"captions are in step; their {u_said:,} stated boundaries and "
              f"{u_placed:,} clustered placements are withheld: "
              f"{', '.join(unknown[:6])}{' ...' if len(unknown) > 6 else ''}")
    # Nothing compared is not the same as nothing late, and the two print
    # differently.
    if vids and not compared:
        print(f"  NONE could be compared -- no caption file under {work}/ for "
              f"any of {len(vids):,} recordings, or no videos_*.csv here -- so "
              "nothing was checked and nothing withheld")
    if undated:
        print(f"  {len(undated):,} have captions and no published length, so "
              f"were not compared: {', '.join(undated[:4])}")
    if late:
        print(f"  {len(late):,} stop more than {caption_span.SLACK // 60} "
              f"minutes short of their recording; {said:,} stated boundaries "
              f"and {placed:,} clustered placements read off them are "
              f"withheld: {', '.join(sorted(late))}")
    return late


def vote_date(s):
    """"8/19/2026" as something that sorts. Text does not.

    The docket writes m/d/Y with no padding, so a string sort puts August
    above December and 2023 above 2025. Every member page claimed "newest
    first" over that order.
    """
    p = (s or "").split("/")
    try:
        return (int(p[2]), int(p[0]), int(p[1]))
    except (IndexError, ValueError):
        return (0, 0, 0)


def write_rollcall_index(out, rollcalls, votes_by_member):
    """One shared file describing all 1,504 roll calls.

    A legislator's page listed 1,081 rows of "HB2026 / Veto Override / Yea":
    no plain English for the question, no outcome, and no way to see that a
    member had broken with their own party. Everything needed to answer that
    is already built -- rollcalls.json has the tallies and the plain-English
    question, and the party split falls out of the member votes themselves.

    It is one file rather than a copy inside each of the 406 member files
    because the same roll calls describe all of them: repeated, it would add
    something over a hundred megabytes to the site; shared, it is fetched
    once, when a reader opens the Votes tab, and serves every member page
    after that. The bill's title is not in it at all -- the page already has
    the term's bill index loaded and can look the title up there.
    """
    ix = {}
    for term_bills in rollcalls.values():
        for rows in term_bills.values():
            for r in rows:
                # The same key main() builds votes_by_bill with. A vote
                # sequence number restarts each session, so the year and the
                # body are both part of naming one.
                key = f'{r.get("year")}-{r.get("body")}-{r.get("number")}'
                ix[key] = {
                    # The plain-English gloss, where the parser could make
                    # one. "OTPA" is the record's word and means nothing to
                    # anyone who has not read the manual; "pass the bill with
                    # changes" is the same fact in language a reader has.
                    "q": (r.get("question_plain") or "").strip(),
                    # The tallies as the source document gives them, not as
                    # summed from the member rows: the clerk's count is the
                    # count, and where the two disagree the clerk wins.
                    "y": r.get("yeas"), "n": r.get("nays"),
                    "p": 1 if r.get("passed") else 0,
                    "pr": 1 if r.get("procedural") else 0,
                }
                if r.get("threshold_note"):
                    ix[key]["tn"] = r["threshold_note"]
                # Where the clerk's record and the ballots disagree, the
                # member's Votes row says so, as the bill's vote card does.
                if r.get("outcome_conflict"):
                    ix[key]["oc"] = r["outcome_conflict"]

    # HOW EACH PARTY VOTED, so a member's page can say when they broke with
    # their own. Yea and Nay only: a member not voting has not taken a side,
    # and counting an excused absence as agreement with anybody would be an
    # invention.
    split = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for rows in votes_by_member.values():
        for v in rows:
            key = f'{v["year"]}-{v["body"]}-{v["vote_number"]}'
            party = (v.get("party") or "").strip()[:1].upper()
            side = (v.get("vote") or "").strip().lower()
            if party and side in ("yea", "nay"):
                split[key][party][0 if side == "yea" else 1] += 1
    for key, parties in split.items():
        if key in ix:
            ix[key]["s"] = {p: c for p, c in sorted(parties.items()) if any(c)}

    f = out / "rollcalls_index.json"
    f.write_text(json.dumps(ix, separators=(",", ":"), sort_keys=True),
                 encoding="utf-8")
    print(f"{len(ix):,} roll calls -> {f.name} "
          f"({f.stat().st_size / 1024:,.0f} KB, read once per reader)")


# The seat out of a ballot's own label: "Shurtleff, Steve(D) Merrimack 15".
# build_data._former_label builds that string and says at length why this reads
# it rather than former_members.json -- it is the only copy
# member_corrections.json has been applied to. The shape is a contract between
# the two functions: change it in both places or in neither.
FORMER_LABEL = re.compile(r"\(\s*[A-Za-z]?\s*\)\s*(?P<county>[A-Za-z .']+?)\s+"
                          r"(?P<district>\d+)\s*$")


def former_roster(legs, votes_by_member, links, former_file, current_term):
    """People who voted in the current term and hold no seat in it now.

    THE MID-TERM DEPARTURES. Twenty members of the 2025-2026 House cast
    between 250 and 591 votes each and then left -- resignations, and a seat
    filled at a special election. The roster is a snapshot of who serves
    today, correctly, so it does not carry them; the vote record does. Until
    now that meant the site held their whole voting history and gave them no
    page, so every one of those votes and every bill they sponsored was plain
    text. They are the former members a reader is most likely to look up,
    because they were here this term.

    Deliberately NOT merged into the sitting roster. site/legislators.json is
    read by about a dozen builders -- the legislators page, the town pages,
    committee rosters, the feeds, the exports, the directory, and the Learn
    section's count of sitting members -- and a former member reaching any of
    them would be the site saying they still serve. This returns a separate
    map, and build_legislators writes it to its own file.

    The seat comes from the vote rows themselves ("St. Clair, Charlie(D)
    Belknap 05"), because that is the seat they held when the vote was cast,
    which is the only seat the record can honestly give them --
    former_members.json fills any gap. No email and no telephone: a published
    official address belongs to the office, and they no longer hold it.
    """
    folded = {str(x) for v in (links or {}).values() for x in v}
    former_file = former_file or {}
    # THE ADDRESS HAS TO READ LIKE EVERYONE ELSE'S. member_slug puts the county
    # in a House member's address because district numbers repeat between
    # counties, and it uses the abbreviation the roster carries -- rock-13, not
    # rockingham-13. A former member has no roster row and so no abbreviation,
    # which gave the first build /legislator/michael-vose-rockingham-5 beside
    # /legislator/jodi-nelson-rock-13. Same map build_data.py builds for the
    # same reason: the sitting roster is where the abbreviations live.
    abbr = {m["county"]: m["county_abbr"] for m in legs.values()
            if m.get("county") and m.get("county_abbr")}
    out = {}
    for mid, mv in votes_by_member.items():
        mid = str(mid)
        if mid in legs or mid in folded or not mv:
            continue
        # EVERY TERM, not only the current one. The cost was measured before
        # this was widened: about 3,600 more files and 200 MB, against a
        # 100,000 cap and a warning threshold of 90,000. Run check_site.py for
        # where the deployment actually sits; the figure this comment used to
        # name here was not one any command produced. What
        # it buys is 36,541 sponsor mentions, 53% of every one on the site,
        # turning from plain text into a link to that person's record.
        #
        # Anyone the record holds at all: a page is written even where the
        # party, the seat or the dates are thin, and says what it does not
        # know rather than guessing. A sparse page is still the only place
        # that person's voting record exists.
        if not mv:
            continue
        dated = sorted(mv, key=lambda v: vote_date(v.get("date")))
        last = dated[-1]
        rec = dict(former_file.get(mid) or {})
        # THE BALLOT'S OWN LABEL FIRST, because it is the only thing here that
        # has been through member_corrections.json. That file is the person's,
        # no generator writes it, and build_data applies it to the map it
        # builds the labels from -- but it never writes that corrected map out,
        # so former_members.json on disk still holds whatever the generators
        # deduced. Reading the file first published the uncorrected seat while
        # taking the corrected NAME from the same ballot two lines above:
        # 376628 went out as "Rep. Steve Shurtleff (D - Graf 9)", the name from
        # the correction and the seat from the Thomas Oppel record it replaced.
        #
        # Where no correction exists the two sources agree, because the label
        # is built from the same file. So this costs nothing and picks up every
        # correction made there without a second copy of the logic.
        m = FORMER_LABEL.search(str(last.get("label") or ""))
        county = (m.group("county").strip() if m else "") or rec.get("county") or ""
        district = ((m.group("district").lstrip("0") if m else "")
                    or str(rec.get("district") or "").lstrip("0"))
        out[mid] = {
            "id": mid,
            "name": last.get("name") or rec.get("name") or "",
            "chamber": last.get("body") or "",
            "party": last.get("party") or rec.get("party") or "",
            "party_code": last.get("party") or "",
            "county": county, "district": district,
            "county_abbr": abbr.get(county, ""),
            "former": True,
            # What the record can say about their service, and nothing beyond
            # it. Not why they left: the site does not distinguish a member
            # who resigned from one who died, and must not start here.
            "served": {"first": dated[0].get("date") or "",
                       "last": last.get("date") or "",
                       "terms": sorted({P.vote_term(v.get("year", ""), v.get("date"))
                                        for v in mv if v.get("year")})},
        }
    return out


# What one ballot says about whether the member took part, in the order a
# roll call is read when two of a member's numbers somehow both hold a ballot
# on it: a vote cast outranks anything else the other ballot says.
ATTENDANCE_KIND = {"Yea": "voted", "Nay": "voted", "Presiding": "presided",
                   "Not Voting/Excused": "excused",
                   "Not Voting/Not Excused": "not_excused"}
_ATTENDANCE_RANK = ("voted", "presided", "conflict", "excused", "not_excused",
                    "no_vote")
# In the room without a Yea or a Nay: in the chair, or standing aside from
# one question under the chamber's conflict rule.
_ATTENDANCE_PRESENT = ("voted", "presided", "conflict")


def _roll_call_key(v):
    return f'{v.get("year")}-{v.get("body")}-{v.get("vote_number")}'


def attendance_context(votes_by_member):
    """{"dates": {roll call: day}, "chair": {roll call: member_id}, ...}.

    Two things a member's own ballots cannot say about themselves, read once
    off every ballot for member_attendance. Beside them, for the build's log,
    the roll calls whose date was not trusted and the declared conflicts seen.

    THE DAY A ROLL CALL WAS TAKEN, where its date breaks the order. The
    numbers run in the order the votes were taken, and two dates do not: 1999
    Senate roll call 109 is dated 10/22/2009 between two of 10/22/1999, and
    2003 Senate roll call 24 is dated 4/4/2003 between 3/27 and 4/3, where the
    journal prints it on the pages of 3 April. As they stand, each is a
    sitting that never happened, attended by every senator on it. So a date
    outside its term, or one its two neighbours keep in order while it
    breaks it, is not trusted: where both neighbours fall on one day the roll
    call is read on that day, having been taken between them, and otherwise
    it is a roll call on no day. A run that breaks the order together --
    2008 House 144-148, the veto day of 24 September, numbered before the
    special session's eight of 4 June, 401-408 -- has neighbours out of order
    with each other, and is left as it is.

    WHO WAS IN THE CHAIR, where the record names nobody. The House codes its
    presiding officer "Presiding" -- except that on some days no roll call
    carries that ballot at all, and the Speaker is coded Excused or Not
    Excused on every one: 2/11/2016, 1/3/2018, 1/2/2019 and 2/16/2022 among
    them, each a day the journal puts the Speaker in the chair, and every
    House roll call of 2021 from 7 April. So on a House day on which no roll
    call names anyone presiding, the member the record puts in the chair most
    often that year is read as presiding wherever they are coded absent. On
    those days only: where the record names somebody else it is believed,
    which is how the five days Speaker Packard was on leave in 2025-2026 stay
    days absent. Not the Senate, whose President votes as a senator and is
    recorded presiding on 195 ballots in twenty-eight years.
    """
    dates, chaired, conflicts = {}, set(), 0
    in_chair = defaultdict(Counter)
    for rows in votes_by_member.values():
        for v in rows:
            key = _roll_call_key(v)
            conflicts += bool(v.get("conflict"))
            if key not in dates:
                dates[key] = vote_date(v.get("date"))
            if v.get("vote") == "Presiding":
                chaired.add(key)
                in_chair[(str(v.get("year")), v.get("body"))][v.get("member_id")] += 1
    runs = defaultdict(list)
    for key in dates:
        y, b, n = key.split("-", 2)
        if n.isdigit():
            runs[(y, b)].append((int(n), key))
    none = (0, 0, 0)
    trusted = dict(dates)
    for (y, b), seq in runs.items():
        seq.sort()
        t = P.term_of(y)
        span = {int(t[:4]), int(t[5:])} if t else set()
        for i, (_, key) in enumerate(seq):
            day = dates[key]
            if day == none:
                continue
            prev = dates[seq[i - 1][1]] if i else none
            nxt = dates[seq[i + 1][1]] if i + 1 < len(seq) else none
            broken = (none not in (prev, nxt) and prev <= nxt
                      and not prev <= day <= nxt)
            if day[0] not in span or broken:
                trusted[key] = prev if prev != none and prev == nxt else none
    house_days = defaultdict(list)
    for key, day in trusted.items():
        if key.split("-")[1] == "H" and day != none:
            house_days[day].append(key)
    chair = {}
    for day, keys in house_days.items():
        if any(k in chaired for k in keys):
            continue
        for k in keys:
            top = in_chair.get((k.split("-")[0], "H"))
            if top:
                chair[k] = top.most_common(1)[0][0]
    return {"dates": trusted, "chair": chair, "conflicts": conflicts,
            "redated": sorted(k for k in dates if trusted[k] != dates[k])}


def member_attendance(votes, context=None):
    """{term: {"chambers", "days", "attended", "roll_calls", "voted", ...}}.

    ATTENDANCE, AS THE PERSON DEFINED IT (23-24 September): a day is a day the
    member's chamber held at least one roll call while they held the seat, and
    it counts as attended if they cast a vote on any roll call that day, with
    no note about part days; beside that, how many of the roll calls held
    while they sat they voted on.

    WHILE THEY SAT is the ballots themselves. Every roll call from 1999 lists
    the members seated for it, whatever they did -- 381 to 400 ballots on a
    House roll call, 22 to 24 on a Senate one -- and between a member's first
    and last ballot of a term, 8 of the 6,015 member-terms miss a roll call at
    all. So a member who arrived at a special election is counted from the
    roll call they first appear on and one who left stops at their last, with
    no service dates to model and none to get wrong. The same rows the Votes
    tab lists: `votes` is every number the member voted under.

    ONE SEAT OUTLIVES ITS HOLDER. The 2017 Senate kept one member on every
    roll call for three months after they had gone, each ballot code 7 with
    nothing in it: 134 ballots on ten days, which counted as absences from a
    seat nobody held. So a run of ballots recording nothing that ends a
    member's term in a chamber is not counted. Only there, and only ballots
    that record nothing: an excused ballot is a member who held the seat and
    was away. No other member-term from 1999 ends in such a run.

    PRESIDING COUNTS AS PRESENT. The Speaker is recorded "Presiding" on most
    of a term's House roll calls and votes on few; on 98 days Terie Norelli
    presided and cast no Yea or Nay at all. Reading that as absence would make
    the person running the chamber its worst attender. The Votes tab already
    tells a reader a presiding ballot "is not a missed vote", and this agrees
    with it; the page says "presided over" where it happened. `context` is
    attendance_context(), which also says who presided where the record
    names nobody, and which day a misdated roll call was taken.

    SO DOES A DECLARED CONFLICT OF INTEREST (rollcall_parser.CONFLICT): the
    member was there and stood aside from one question under the chamber's
    rule. On seven days a member declared a conflict and voted on nothing
    else, and each read as a day absent.

    "No vote recorded" otherwise -- database code 7 and an empty code -- is
    not a vote cast, so it is missed.
    """
    ctx = context or {}
    dates, chair = ctx.get("dates", {}), ctx.get("chair", {})
    by_term = defaultdict(list)
    for v in votes:
        # Organization Day's ballots are the next term's (proceedings.vote_term).
        t = P.vote_term(str(v.get("year") or ""), v.get("date"))
        if not t:
            continue
        kind = ATTENDANCE_KIND.get(v.get("vote"), "no_vote")
        key = _roll_call_key(v)
        if v.get("conflict"):
            kind = "conflict"
        elif (kind in ("excused", "not_excused")
              and chair.get(key) == v.get("member_id")):
            kind = "presided"
        num = str(v.get("vote_number") or "")
        by_term[t].append(((v.get("body"), str(v.get("year")),
                            int(num) if num.isdigit() else 0), key, kind, v))
    out = {}
    for t in sorted(by_term):
        kept = []
        for body in sorted({b[0][0] for b in by_term[t]}, key=str):
            run = sorted((b for b in by_term[t] if b[0][0] == body),
                         key=lambda b: b[0])
            while run and run[-1][2] == "no_vote":
                run.pop()
            kept += run
        if not kept:
            continue
        calls, days, chambers = {}, {}, set()
        for (body, _, _), key, kind, v in kept:
            was = calls.get(key)
            if was is None or _ATTENDANCE_RANK.index(kind) < _ATTENDANCE_RANK.index(was):
                calls[key] = kind
            if body in ("H", "S"):
                chambers.add(body)
            day = dates.get(key) or vote_date(v.get("date"))
            # An undated ballot is still a roll call held while they sat; it
            # cannot say which day, so it is left out of the days rather than
            # lumped into one invented day with every other undated ballot.
            if day != (0, 0, 0):
                days[day] = days.get(day, False) or kind in _ATTENDANCE_PRESENT
        kinds = Counter(calls.values())
        out[t] = {"chambers": "".join(sorted(chambers)),
                  "days": len(days),
                  "attended": sum(1 for x in days.values() if x),
                  "roll_calls": len(calls),
                  **{k: kinds.get(k, 0) for k in _ATTENDANCE_RANK}}
    return out


def sponsored_in_order(rows):
    """A member's sponsored bills: prime first, then by year, oldest first,
    then by bill number in bills.html's order (bill_order)."""
    return sorted(rows, key=lambda x: (not x["prime"], x.get("year") or 0,
                                       BO.bill_key(x["bill"])))


def build_legislators(out, legs, votes_by_member, towns, unnamed,
                      sponsored=None, bill_year=None, links=None,
                      former=None):
    """One JSON per member, plus the index and the town map.

    Split out of main(). main() was 808 lines even after the station
    builders came out, and the bug that cost 611 bills their facts was two
    different things sharing the name `st` 350 lines apart in this scope.

    `links` is member_links.links(): the numbers a sitting member also voted
    under in the other chamber.
    """
    lg, fm = [], []
    # Read off every ballot once, because what one member's attendance needs
    # to know about a roll call -- its day, its chair -- is not in their own.
    attending = attendance_context(votes_by_member)
    print(f"attendance: {len(attending['chair']):,} House roll call(s) naming nobody in "
          f"the chair read as the year's presiding officer's; "
          f"{len(attending['redated'])} misdated ({', '.join(attending['redated'][:4])}); "
          f"{attending['conflicts']:,} declared conflict(s)")
    # The record holds 411 of them, 1999-2019. None at all, over ballots
    # from those years, is a member_votes.json written before build_data
    # flagged them -- and then every one counts as an absence, silently.
    if not attending["conflicts"] and any(
            str(v.get("year") or "9999") < "2020"
            for rows in votes_by_member.values() for v in rows):
        print("  WARNING: no ballot is flagged as a declared conflict of interest; "
              "data/member_votes.json predates rollcall_parser.ballot and counts each "
              "as an absence. Rebuild it: python3 src/parse/build_data.py")
    # ONE CODE PATH FOR BOTH POPULATIONS. The former members go through the
    # same member_labels, the same member_slug and the same per-member JSON as
    # the sitting roster, so every check that guards how a member is named --
    # preflight's "nobody is named surname-first", "a member is named the same
    # way by both namers", "an unnamed member is not dressed up as a person" --
    # applies to them unchanged. Only the list they land in differs, and that
    # is the whole point: former_roster says why.
    for mid, m in [*legs.items(), *(former or {}).items()]:
        # A MEMBER WHO CHANGED CHAMBER VOTED UNDER TWO NUMBERS, one for each:
        # Sen. Cindy Rosenwald's page carried 1,399 of her 4,218 votes. A page
        # keeps every chamber the member sat in. Own votes first, so a member
        # nobody is joined to sorts exactly as before.
        joined = (links or {}).get(mid, [])
        mv = sorted([v for x in (mid, *joined) for v in votes_by_member.get(x, [])],
                    key=lambda v: vote_date(v.get("date")), reverse=True)
        counts = defaultdict(int)
        for v in mv:
            counts[v["vote"]] += 1
        lab = member_labels(m.get("name"), chamber=m.get("chamber"),
                            party=m.get("party_code") or m.get("party"),
                            district=m.get("district"), county=m.get("county"),
                            county_abbr=m.get("county_abbr"))
        # "seat" is the House floor seat, division * 1000 + number, and it is
        # empty for all 24 senators because only the House has a seating
        # chart. build_data says how the number decodes and why it is worth
        # carrying.
        row = {**{k: m.get(k) for k in ("id", "name", "chamber", "party", "county",
                                        "county_abbr", "district", "label", "email",
                                        "url", "url_past", "towns",
                                        "committees", "title", "phone", "seat")},
               **lab, "n_votes": len(mv), "counts": dict(counts),
               "n_sponsored": len((sponsored or {}).get(mid, [])),
               "slug": member_slug(m, lab)}
        if m.get("former"):
            # No email and no telephone, whatever the roster once held: the
            # address belonged to the office. The towns go too -- the town map
            # is today's, and the district they sat for may not exist in it.
            # The seat goes for the same reason as the towns: a House seat is
            # occupied by whoever sits there now, so printing a former
            # member's would name a chair that is somebody else's, and the
            # only seat this disk holds is the current one anyway.
            row.update({"former": True, "served": m.get("served") or {},
                        "email": "", "phone": "", "towns": [],
                        "committees": [], "seat": ""})
            fm.append(row)
        else:
            lg.append(row)
        # What they put their name to. The page's own meta description has
        # promised "sponsored bills" since it was written and the file did not
        # carry them, so the page could not show them and a search engine was
        # being told about a section that does not exist.
        #
        # Prime sponsorship first, then the rest: a member's own bills are the
        # ones they are asked about. Within each, OLDEST year first -- this
        # said "newest first" over code that has always run oldest first --
        # and then by number as bills.html lists them. The number was compared
        # as text, so HB436 was listed before HB61.
        mine = sponsored_in_order((sponsored or {}).get(mid, []))
        # Which numbers the votes below were cast under, and the years in each
        # chamber, for the page to say why a senator's list has House votes in
        # it. Only where there are two: everyone else's file is as it was.
        both = ({"member_ids": [mid, *joined], "service": ML.service(mv)}
                if joined else {})
        (out / "legislators" / f"{mid}.json").write_text(json.dumps({
            **m, **lab, "counts": dict(counts), **both,
            # In the member's own file and nowhere else: not in the `row`
            # above, which is what the legislators page, the town pages and
            # every other listing read. It is a figure on their own page, not
            # a column anyone is sorted by.
            "attendance": member_attendance(mv, attending),
            "n_sponsored": len(mine),
            "n_prime": sum(1 for x in mine if x["prime"]),
            "sponsored": mine,
            # y is the bill's FILING year, which is what its address is under
            # -- a 2025 bill voted on in 2026 lives at /bill/2025/. Without it
            # the page had to guess the year from the bill number, and a
            # number that exists in two terms was resolved to whichever came
            # first in the index.
            # k names the roll call this vote was cast in, in the
            # shape main() already keys them by. It is what lets the page
            # look up what the vote decided without all 406 member files
            # carrying their own copy of that.
            "votes": [{"d": v["date"], "b": v["bill"], "q": v["question"],
                       "v": v["vote"],
                       "k": (f'{v["year"]}-{v["body"]}-{v["vote_number"]}'),
                       "y": (bill_year or {}).get(
                           (P.vote_term(v.get("year", ""), v.get("date")), v["bill"]), "")}
                      for v in mv],
        }), encoding="utf-8")
    if unnamed:
        print(f"{len(unnamed):,} member id(s) still have no name and appear as "
              '"Member #id" in roll calls:')
        print("  " + ", ".join(sorted(unnamed)[:12])
              + (" ..." if len(unnamed) > 12 else ""))
        # A six-digit id is an Employeeno that build_data fell back to because
        # the legislators table has no row for that person -- not a PersonID
        # nobody has looked up yet. fetch_members_db.py has already read every
        # inactive legislator the database holds, so re-running it will not
        # name these; the General Court's own roster does not carry them.
        #
        # resolve_members.py could, in principle: rc_yeahnay.aspx lists the
        # names who voted each way, and the leftovers after removing everyone
        # identified must be these people. It reads the current session's
        # RollCallHistory.txt only, and skips a blank id outright, so it needs
        # both of those changed first. Three members of the 2023-2024 House,
        # 1,470 votes, is what that would buy.
        orphans = [u for u in unnamed if u.isdigit() and len(u) >= 6]
        if orphans:
            print(f"  {len(orphans)} of these are an Employeeno, used because "
                  "the legislators table")
            print("  has no row for them at all. fetch_members_db.py has read "
                  "every inactive")
            print("  member it holds, so it will not name them; only "
                  "rc_yeahnay.aspx would.")
        if len(orphans) < len(unnamed):
            print("  The rest are PersonIDs: run fetch_members_db.py, which "
                  "writes")
            print("  former_members.json, then build_data.py, which reads it.")
    (out / "legislators.json").write_text(json.dumps(lg), encoding="utf-8")
    # Its own file, never merged into the one above. See former_roster.
    (out / "former.json").write_text(json.dumps(fm), encoding="utf-8")
    (out / "towns.json").write_text(json.dumps(towns), encoding="utf-8")
    print(f"{len(lg):,} legislator pages, {len(towns):,} towns")
    if fm:
        print(f"{len(fm):,} former member(s) -> former.json "
              f"({sum(x['n_votes'] for x in fm):,} votes, "
              f"{sum(x['n_sponsored'] for x in fm):,} sponsorships now linkable)")
    return lg


def build_composition(a, legs):
    """Party composition, vacancies, the Executive Council and the governor.

    Returns (comp, vac). Split out of main(); this block already carried a
    dead duplicate of itself once -- two versions of the same work eighteen
    lines apart, the second silently discarding the first.
    """
    # Seat totals come from the district files where available, since those sum
    # to the constitutional membership exactly. The roster holds only sitting
    # members, so the difference is vacancies -- which accumulate through a term
    # as people resign or die, and which nothing else reports.
    dj = load(a.districts, {})
    seats_by = defaultdict(int)
    for wards in dj.values():
        for v in wards.values():
            for h in v.get("house", []):
                seats_by[("H", h["county"], h["district"])] = h.get("seats") or 1
    house_seats = sum(seats_by.values()) or 400

    PARTY_FULL = {"R": "Republican", "D": "Democrat", "I": "Independent",
                  "L": "Libertarian"}
    comp = {}
    for ch, label, total in (("H", "House", house_seats), ("S", "Senate", 24)):
        members = [m for m in legs.values() if m["chamber"] == ch]
        counts = Counter(m["party_code"] or "?" for m in members)
        comp[ch] = {
            "chamber": label, "seats": total, "sitting": len(members),
            "vacant": max(total - len(members), 0),
            "parties": [{"code": k, "name": PARTY_FULL.get(k, k), "n": v}
                        for k, v in sorted(counts.items(), key=lambda x: -x[1])],
            # Reference thresholds, stated as arithmetic rather than as any
            # party's distance from them. A bill passes with a majority of
            # those voting, so that one has no fixed number. Three fifths
            # (passing a constitutional amendment) is of the members IN
            # OFFICE, not of the seats: 239 of the 397 then seated carried
            # CACR 26 in 2012, and every CACR vote the dockets and Journals
            # record as needing three fifths fits that count. Counted here
            # from the roster, and the page says so, because the most recent
            # roll call's ballots can differ from it by a member or two.
            "majority": total // 2 + 1,
            "two_thirds_note": "two thirds of those voting, so it moves with turnout",
            "three_fifths": -(-3 * len(members) // 5),
        }

    # Which districts are short a member. Only possible where the district files
    # give seat counts.
    vac = []
    if seats_by:
        held = Counter()
        for m in legs.values():
            if m["chamber"] == "H":
                held[("H", m["county"], int(m["district"] or 0))] += 1
        for key, n in sorted(seats_by.items()):
            gap = n - held.get((key[0], key[1], int(key[2])), 0)
            if gap > 0:
                vac.append({"county": key[1], "district": key[2], "seats": n,
                            "vacant": gap})
    comp["vacancies"] = vac

    # Executive branch: hand-maintained, because the Council and the governor
    # are not the General Court and appear in none of its files. An unedited
    # file yields nothing, so the section is absent rather than wrong.
    op = Path(a.officials)
    if op.exists():
        council, gov, onote, oupd = [], None, "", ""
        last = None
        for raw in op.read_text(encoding="utf-8").splitlines():
            if raw.strip().startswith("#"):
                continue
            line = raw.split("#")[0].rstrip()
            if not line.strip():
                last = None
                continue
            if raw[:1] in " \t" and last == "note":
                onote = (onote + " " + line.strip()).strip()
                continue
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            last = k
            if k == "councilor":
                parts = [x.strip() for x in v.split("|")]
                if parts and parts[0]:
                    council.append({"district": parts[0],
                                    "name": parts[1] if len(parts) > 1 else "",
                                    "party": (parts[2] if len(parts) > 2 else "").upper()})
            elif k == "governor" and v:
                parts = [x.strip() for x in v.split("|")]
                gov = {"name": parts[0],
                       "party": (parts[1] if len(parts) > 1 else "").upper()}
            elif k == "note":
                onote = v
            elif k == "updated":
                oupd = v
        named = [c for c in council if c["name"]]
        if named or gov:
            cc = Counter(c["party"] or "?" for c in named)
            comp["council"] = {
                "chamber": "Executive Council", "seats": len(council) or 5,
                "sitting": len(named), "vacant": len(council) - len(named),
                "members": council,
                "parties": [{"code": k, "name": PARTY_FULL.get(k, k), "n": v}
                            for k, v in sorted(cc.items(), key=lambda x: -x[1])],
                "majority": (len(council) or 5) // 2 + 1,
                "note": onote, "updated": oupd}
            print(f"  Executive Council: {len(named)} of {len(council)} seats named")
        if gov:
            comp["governor"] = gov
        if not named and not gov:
            print("  status/officials.txt is unedited \u2014 the Executive Council "
                  "and governor are omitted from the page")

    return comp, vac


def session_over(path):
    """The day the current term ran out of session days, as status/status.txt
    states it, or "".

    Read on its own and before the bills are built, because it decides whether a
    bill of the current term that is still pending is still moving. build_status
    reads the same file later for the page's panel; this is one line of it, and
    duplicating the read costs nothing next to threading the panel through the
    bill loop.
    """
    p = Path(path)
    if not p.exists():
        return ""
    for raw in p.read_text(encoding="utf-8").splitlines():
        if raw.strip().startswith("#"):
            continue
        k, _, v = raw.split("#")[0].partition(":")
        if k.strip().lower() == "session_over" and v.strip():
            return v.strip()
    return ""


def session_over_in(day, current):
    """`day`, the file's session_over, where it is a day of the term `current`;
    else "".

    THE LINE IS TAKEN OUT BY HAND ("Delete the line in December"), AND A LINE
    LEFT IN SAYS NOTHING OF THE NEXT TERM. With "session_over: 2026-08-19"
    still in the file when 2027-2028 is the current term, every measure of
    2027 that had passed its own chamber and awaited the other read "Died
    when the session ended", over a paragraph saying it went no further
    (ended_with_the_term, which the day turns on for the current term): 138
    of 138, when this term's docket was replayed two years on and cut at 15
    March. The day is of a term, and it ends that one.
    """
    return day if day and current and P.term_of(str(day)) == current else ""


def build_status(a, index, procs, floor, today, latest_by_body, upcoming):
    """The site's "where the session is" panel.

    Hand-maintained facts from status/session.txt merged with what the data
    can show. Split out of main(); returns the status dict.
    """
    # Hand-maintained facts merged with what the data can show. The phase, the
    # session calendar and veto day are set by the chambers and published only
    # in the calendars, so they are edited rather than derived; the last session
    # date and the count of scheduled hearings come from the data.
    status = {"milestones": []}
    sp = Path(a.status)
    if sp.exists():
        last_key = None
        for raw in sp.read_text(encoding="utf-8").splitlines():
            if raw.strip().startswith("#"):
                continue
            line = raw.split("#")[0].rstrip()
            if not line.strip():
                last_key = None
                continue
            # An indented line continues the previous value, so a note can be
            # written as a paragraph instead of one unreadable line.
            if raw[:1] in " \t" and last_key in ("note", "headline"):
                status[last_key] = (status.get(last_key, "") + " "
                                    + line.strip()).strip()
                continue
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            last_key = k
            if k == "milestone":
                parts = [x.strip() for x in v.split("|")]
                if parts and parts[0] >= today:
                    status["milestones"].append({
                        "date": parts[0],
                        "label": parts[1] if len(parts) > 1 else "",
                        "note": parts[2] if len(parts) > 2 else ""})
            elif k in ("updated", "phase", "headline", "note", "session_over"):
                status[k] = v
        status["milestones"].sort(key=lambda m: m["date"])
        if status.get("updated"):
            age = (build_date.today() - _date.fromisoformat(status["updated"])).days
            status["stale_days"] = age
            if age > 45:
                print(f"  status/status.txt was last updated {age} days ago "
                      "\u2014 the page will say so")
    # Latest sitting of either chamber, from the per-chamber map that replaced
    # the old single "most recent session".
    status["last_session"] = (max(v["date"] for v in latest_by_body.values())
                              if latest_by_body else None)
    status["hearings_next_14"] = len(upcoming)
    # Always-correct live links: these URLs resolve to whatever is streaming now,
    # or to the channel if nothing is, so no polling is needed.
    status["live"] = [
        {"chamber": "House",
         "url": "https://www.youtube.com/@NHHouseofRepresentatives/live"},
        {"chamber": "Senate",
         "url": "https://www.youtube.com/@NewHampshireSenate/live"}]

    return status


# A calendar's publication date, out of the filename the viewer link carries:
# "calendars%5C2026%5CNo10%20March%206%202026.pdf". Every one of the 24
# calendars a committee report cites resolves this way, so a report that the
# docket does not date can still be placed on the day it was printed.
CAL_DATE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October"
    r"|November|December)%20(\d{1,2})%20(\d{4})", re.I)
MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]
# "House Calendar 51, 2025" is how a report names the calendar it was printed
# in; "HC 51" is how the docket cites the same volume. One key for both.
REPORT_CAL = re.compile(r"House Calendar (\d+[A-Za-z]?)(?:,\s*(\d{4}))?", re.I)
# What the chamber did between one report and the next. These are the three
# ways a bill goes back to a committee that has already reported it, and one
# of them sits between the two reports on eight of the nine bills whose
# reports all come from a single committee -- which is the answer to "what
# does the second report mean". Interim study is deliberately not here: it
# ends a bill for the session rather than sending it back for another report.
REPORT_AGAIN = re.compile(r"recommit|re-?refer|retained in committee", re.I)


def rec_key(s):
    """A recommendation as the two sources agree on it.

    The docket writes "Ought to Pass with Amendment"; the Senate's own report
    writes "OUGHT TO PASS WITH AMENDMENT", and sometimes "IS INEXPEDIENT TO
    LEGISLATE" where the docket says "Inexpedient to Legislate". Stripping the
    leading verb, the case and the punctuation makes them one string -- the
    punctuation being what separates "Re-referred" from "rereferred". Measured
    on every Senate report the database holds: 1,443 of the 1,443 bills whose
    docket records a Senate report agree with the report's own wording, with
    no disagreements.
    """
    s = re.sub(r"^(?:is|be|has)\s+", "", (s or "").strip().lower())
    return re.sub(r"[^a-z ]", "", s).strip()


def _cal_key(source):
    """"House Calendar 51, 2025" as the docket writes it: ("HC 51", "2025")."""
    m = REPORT_CAL.search(source or "")
    return (f"HC {m.group(1)}", m.group(2) or "") if m else ("", "")


def _cal_date(url):
    """The day a calendar was published, from the filename in its link."""
    m = CAL_DATE.search(url or "")
    if not m:
        return ""
    return (f"{int(m.group(3)):04d}-{MONTHS.index(m.group(1).lower()) + 1:02d}"
            f"-{int(m.group(2)):02d}")


def _mdy(s):
    """The docket's 03/17/2026 as 2026-03-17."""
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})$", (s or "").strip())
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""


def committee_reports(recs, narr, sources, house_cmte, senate_cmte):
    """Every committee report on a bill, dated, in the order they were signed.

    Two sources hold different halves of this and neither is enough alone.

    The House Calendar prints why a committee decided as it did, signed by
    name, and that is the only place the reasoning exists. It says nothing
    about when, and a bill reported twice by one committee -- 9 of the 108
    with more than one report -- came out as two identical-looking blocks with
    no way to tell which was which, or that on HB104 they are one report
    printed in two calendars.

    The docket records that a committee reported, the day it signed, what it
    moved, by what vote, and the volume and page it was printed in. It has no
    prose. It also has the Senate: 1,708 reports the tab used to answer with
    "Senate reports use a different format and are not loaded yet". The format
    is one report, with a vote and no minority -- which is what the Senate
    does.

    So each written report is dated from the docket line citing the same
    calendar, or failing that from the day that calendar was published, and
    every report the docket has that no calendar printed is carried alongside
    it. The page says which of the two dates it is showing.
    """
    events = [e for e in (narr or {}).get("events", [])
              if e.get("type") == "report" and not e.get("cancelled")]
    # The date the committee signed, per calendar volume, from the docket.
    signed = {}
    for e in events:
        d = _mdy(e.get("report_date"))
        if e.get("cite") and d:
            signed.setdefault(e["cite"], d)

    # The Senate's reports come from the database, not from a House Calendar,
    # and carry their own printed date. Where the docket records the same
    # recommendation it has the day the committee SIGNED and the journal page
    # it was printed in, which are better than the day it was released -- so
    # those are taken, and that docket line is then not shown a second time
    # saying what the report above it already says.
    #
    # Keyed on the CHAMBER as well as the recommendation. On the wording alone
    # it matched the wrong chamber 364 times out of 1,446 -- both chambers say
    # "Ought to Pass" -- and gave a Senate report a House Calendar citation and
    # the day the House committee signed. A citation to the wrong document is
    # worse than none on a site whose whole claim is that it can be checked.
    by_rec, used = {}, set()
    for e in events:
        if e.get("recommendation"):
            by_rec.setdefault((e.get("body") or "",
                               rec_key(e["recommendation"])), []).append(e)

    out, seen_cal = [], set()
    for r in recs:
        key, year = _cal_key(r.get("source"))
        seen_cal.add(key)
        url = _source_url(sources, key, year)
        rr = dict(r)
        if signed.get(key):
            rr["date"], rr["dated"] = signed[key], "signed"
        elif _cal_date(url):
            rr["date"], rr["dated"] = _cal_date(url), "printed"
        elif r.get("date"):
            rr["date"], rr["dated"] = r["date"], r.get("dated") or "printed"
        else:
            rr["date"], rr["dated"] = "", ""
        rr["cite"] = key
        rr["cite_url"] = url
        if not key and r.get("date") and r.get("body"):
            match = next((e for e in
                          by_rec.get((r["body"],
                                      rec_key(r.get("majority_recommendation"))), [])
                          if id(e) not in used), None)
            if match:
                used.add(id(match))
                when = _mdy(match.get("report_date"))
                if when:
                    rr["date"], rr["dated"] = when, "signed"
                cite = match.get("cite", "")
                rr["cite"] = cite
                rr["cite_url"] = _source_url(sources, cite, rr["date"][:4])
        out.append(rr)
    out.sort(key=lambda x: x.get("date") or "9999")

    # Reports the docket has and no calendar printed. A House report reaches
    # this list when it was printed in a calendar this site has not read; a
    # Senate report always does, because the Senate prints no reasoning.
    docket = []
    for e in events:
        if id(e) in used:
            continue          # a written report above is this same report
        if e.get("cite") and e["cite"] in seen_cal:
            continue
        # A minority report carries no vote and no volume of its own; where the
        # calendar's version of it is already above, showing the docket's bare
        # line again says nothing new.
        if e.get("side") and any(x.get("side") == e["side"]
                                 for r in recs for x in (r.get("reports") or [])):
            continue
        docket.append({
            "date": _mdy(e.get("report_date")) or e.get("date", ""),
            "dated": "signed" if _mdy(e.get("report_date")) else "recorded",
            "body": e.get("body", ""),
            # The committee that reported, which narrative.py carries forward
            # from the referral line. The bill record holds only the committee
            # it is with now, so a report from an earlier one had no name.
            "committee": (e.get("committee")
                          or (senate_cmte if e.get("body") == "S" else house_cmte)),
            "side": e.get("side", ""),
            "recommendation": (e.get("recommendation") or "").upper(),
            "vote_yeas": int(e["yeas"]) if e.get("yeas") else None,
            "vote_nays": int(e["nays"]) if e.get("nays") else None,
            "amendment": e.get("amendment", ""),
            "new_title": bool(e.get("new_title")),
            "cite": e.get("cite", ""),
            "cite_url": _source_url(sources, e.get("cite", ""),
                                    (e.get("date") or "")[:4]),
        })
    docket.sort(key=lambda x: x.get("date") or "9999")

    # Why there is a second report. Taken from the docket between one report
    # and the next, so it is the chamber's own record of what it did rather
    # than an inference from the two reports looking different.
    dates = sorted(x["date"] for x in out + docket if x.get("date"))
    between = []
    for a, z in zip(dates, dates[1:]):
        # Strictly before the later report: an action on the same day
        # is the floor acting on that report, not the reason for it.
        # The docket's lines, each whole and once (docket_line): the note
        # quotes a line. Read by the clause, HB 278 of 1999's "Comm Am, AA
        # VV; Rep Soltani moved to recommit, ML VV; Passed with Am and ref to
        # Finance VV" gave the failed motion alone as what the docket records
        # between its two reports.
        again = [e for e in (narr or {}).get("events", [])
                 if not e.get("cancelled") and not e.get("in_line")
                 and e.get("type") != "report"
                 and a < (e.get("date") or "") < z and REPORT_AGAIN.search(docket_line(e))]
        # THE ONE THAT SENT IT BACK, not the first that names it: HB 75 of
        # 1999 quoted "Sen. Russman moved Rerefer, Sen. Russman Withdrew
        # Motion to Rerefer" over "Sen D'Allesandro Moved Rerefer, MA, VV",
        # which carried. A motion that failed, was withdrawn or was not voted
        # on is quoted only where nothing else between the reports is.
        e = (next((e for e in again if _again_carried(docket_line(e))), None)
             or next((e for e in again if _again_carried(docket_line(e)) is None), None)
             or (again[0] if again else None))
        if e:
            between.append({"before": z, "date": e["date"], "text": docket_line(e)})
    return out, docket, between


def _again_carried(raw):
    """True where a line sending a bill back to committee records it carried,
    False where it records it failed, was withdrawn or was not voted on, None
    where it says neither."""
    raw = raw or ""
    m = REPORT_AGAIN.search(raw)
    rest = raw[m.start():] if m else raw
    # AND NO FURTHER THAN A FAILED MOTION TO RECONSIDER IT. "Re-Referred to
    # Res, Rec & Dev committee RC(158-154); Rep Royce moved to reconsider, ML
    # RC(156-157)" (SB 135 of 1999, one line since the 1999-2006 reader joins
    # the two rows the database cut it into) is the bill sent back and a
    # motion to undo that which failed, the reading _j_segments gives it too.
    # Read to the end, the ML was the re-referral's, and the Reports tab gave
    # a cancelled subcommittee session as the reason for the second report.
    # A reconsideration that carried is left where it was.
    again = LOST_RECONSIDER.search(rest) if m else None
    if again:
        rest = rest[:again.start()]
        raw = raw[:m.start() + again.start()]
    # Withdrawn or not voted on in the clause that sends it back, not in one
    # before it: "Ought to Pass [not voted on]; Sen. Prescott Moved Recommit,
    # MA, VV" (SB 10 of 2001) and "REP FLANAGAN WITHDREW OTP/AM MOTION;
    # RE-REFERRED TO CON & STAT" (HB 303 of 1991) are recommittals that
    # carried. "REP BUCKLEY WITHDREW RECOMMIT MOTION" is still withdrawn.
    clause = raw[raw.rfind(";", 0, m.start()) + 1:] if m else raw
    if re.search(r"withdr[ae]w|not\s+voted\s+on", clause, re.I):
        return False
    if re.search(r"\b(?:MF|ML)\b|\bfail|\blost\b", rest):
        return False
    # The past tense is the outcome only where no one is said to have moved
    # it: "Sen. Kelly moved to Rereferred to Committee" (HB 450 of 2009) is
    # the motion, and its "MA, VV" is the next line.
    if re.search(r"\bMA\b|\badopted\b|\bcarried\b", rest, re.I) or (
            re.search(r"\b(?:re-?referred|recommitted|retained)\b", raw, re.I)
            and not re.search(r"\bmov(?:ed|es?)\b", raw, re.I)):
        return True
    return None


# A later clause of the line moving to reconsider, which failed.
LOST_RECONSIDER = re.compile(r";[^;]*\b(?i:reconsider)[^;]*\b(?:ML|MF)\b")


def hearing_testimony(e, tdb, scraped):
    """Who signed in for and against, on the hearing this line records.

    The database carries the hearing DATE with each sign-in, so the count sits
    with the hearing it belongs to rather than as one number for the whole
    bill -- which is the point of it: a hearing next week, and where opinion
    stands today. 2,072 of the 2,122 docket hearing lines match a date the
    database also has.

    Counts only. The table has names, towns and the written testimony, and
    almost every one of the 400,000 rows is a private individual who signed a
    committee's sheet; fetch_testimony_db does not ask for any of it.
    """
    if not PUBLIC_HEARING.search(e.get("raw", "")):
        return {}
    if tdb:
        hit = next((h for h in tdb.get("hearings", [])
                    if h.get("date") == e.get("date")), None)
        if hit:
            return {"testimony": {**hit, "dated": True}}
        # The database has the bill but not this date. Its whole-bill total is
        # still true of the bill; it is just not true of this hearing alone,
        # and the page has to say which it is showing.
        return {"testimony": {k: tdb[k] for k in
                              ("total", "support", "oppose", "neutral")}}
    return {"testimony": scraped} if scraped else {}


# THE SENATE'S OWN HEARING REPORTS, on the hearing they report.
#
# senate_hearing_reports.py reads them out of the database dump; this puts
# each on the Senate public-hearing station of the same bill and the same
# date, and resolves the legislators who testified to the member they are, so
# the page can draw them with the chip everybody else on the site is drawn
# with. Everyone else -- members of the public, officials, lobbyists -- is
# printed as the report names them. The person decided on 24 September that
# the reports are shown as the Senate published them, names and all; the
# sign-in system's names stay out, which is hearing_testimony's rule above
# and a different source.
SPEAKER_TITLE = re.compile(
    r"^(?P<t>Senators?|Sen\.|Representatives?\.?|Reps?\.)\s+(?P<n>.+)$")


def speaker_index(people):
    """{(chamber, surname): [member, ...]} over the sitting and the departed.

    A surname here is everything after the first name, lower-cased, so
    "Perkins Kwoka" and "Sabourin dit Choiniere" index whole.
    """
    idx = defaultdict(list)
    for m in people:
        ch = str(m.get("chamber") or "")[:1].upper()
        last = str(m.get("last") or "").strip()
        first = str(m.get("first") or "").strip()
        if not last and "," in str(m.get("name") or ""):
            last, first = [x.strip() for x in m["name"].split(",", 1)]
        if ch and last:
            idx[(ch, last.lower().replace("’", "'"))].append(
                {**m, "_first": first.lower()})
    return idx


def resolve_speaker(heading, idx, name_part):
    """The member a report's speaker line names, or None.

    Only a line that opens with the chamber's own title -- "Senator Gannon",
    "Rep. Alvin See" -- is tried, and only in that chamber. The surname must
    name exactly one member of it, or name several and the first name settle
    which; a first name that disagrees with the only candidate, and every
    doubt besides, leaves the speaker as the plain text the report printed.
    A wrong member in a chip is a factual error; a missing chip is not.
    """
    m = SPEAKER_TITLE.match(name_part(heading) or "")
    if not m:
        return None
    # "Representatives Barbara Comtois (Belk. 7) and Peters Bixby (Straf. 13)"
    # heads two people's points; a chip would give them to the first.
    if m.group("t").lower().rstrip(".") in ("senators", "representatives"):
        return None
    ch = "S" if m.group("t").lower().startswith("sen") else "H"
    # The report's apostrophe is a typesetter's and the roster's is not:
    # "Prudhomme-O’Brien" and "Prudhomme-O'Brien" are one member.
    words = m.group("n").replace("’", "'").split()
    # A House member's seat run on -- "Rep. David Fracht-Grafton 16" -- and
    # a generational suffix, "Henry Giasson III", are not the surname.
    while len(words) > 1 and (words[-1].isdigit() or re.fullmatch(
            r"(?:Jr|Sr|II|III|IV)\.?", words[-1])):
        words.pop()
    if not words:
        return None
    for cut in range(len(words)):
        first = words[0].lower() if cut else ""
        cands = idx.get((ch, " ".join(words[cut:]).lower()), [])
        if not cands:
            continue
        if first:
            exact = [c for c in cands if c["_first"] == first]
            if len(exact) == 1:
                return exact[0]
            if len(cands) == 1 and cands[0]["_first"][:1] == first[:1]:
                # "Dan Innis" for Daniel, "Pat Long" for Patrick.
                return cands[0]
            return None
        return cands[0] if len(cands) == 1 else None
    return None


def hearing_report_for_page(rec, idx, name_part, pages=None):
    """One parsed report as the Hearings tab draws it, legislators resolved.

    Returns (report, members resolved, legislator lines left as text).
    `pages` is attach_hearing_reports': the party is the member's as `idx`
    holds them, which for a term whose own roster is frozen is the party
    they sat with; the link is to their own page, wherever it is now.
    """
    got = miss = 0
    secs = []
    for s in rec.get("sections", []):
        o = {k: v for k, v in s.items() if k != "speakers"}
        if "speakers" in s:
            o["speakers"] = []
            for sp in s["speakers"]:
                sp = dict(sp)
                mem = resolve_speaker(sp.get("who", ""), idx, name_part)
                if mem:
                    got += 1
                    # The report's own words for the person, in the chip the
                    # site draws a legislator with: the party colour and the
                    # link are the site's; the name is the Senate's.
                    _page = mem if pages is None else pages.get(str(mem.get("id")))
                    sp["member"] = {"label": name_part(sp["who"]),
                                    "party_code": mem.get("party_code") or "",
                                    "slug": own_slug(_page) if _page else ""}
                elif SPEAKER_TITLE.match(name_part(sp.get("who", "")) or ""):
                    miss += 1
                o["speakers"].append(sp)
        secs.append(o)
    # `fallback` is the parser's diagnosis of why a report stayed as text,
    # snippets and all; the page reads a section's `text` instead, and the
    # reasons are for senate_hearing_reports.py --fallbacks, not the reader.
    out = {k: v for k, v in rec.items()
           if k not in ("sections", "filed", "bill", "subject", "fallback")}
    # What was heard, only where it is not the bill itself: the page is the
    # bill's, and its title is already at the top of it. An amendment heard
    # on its own is named, because that is what the report is about.
    if SHR.AMEND_LINE.match(rec.get("subject") or ""):
        out["subject"] = rec["subject"]
    out["sections"] = secs
    return out, got, miss


def report_station(rep, docket_dates):
    """The station a hearing report stands on when the docket has no Senate
    hearing of the bill on the date the report gives.

    UNDER THE REPORT'S OWN DATE. 20 of the 1,293 reports of 24 September give
    a hearing date the docket does not: most a few days after the docket's
    hearing of the same bill -- SB 42 heard on 21 January 2025 by the docket
    and on the 23rd by its report -- and three, HB 183, HB 268 and HB 435, for
    bills the docket gives no Senate hearing at all. They were left off the
    page. The person decided on 24 September that they are shown, dated as
    the Senate committee dated them, and neither date is corrected to the
    other: this site cannot say which is right. The station says it is dated
    by the report, and names the docket's own hearing dates where it has any,
    so a reader sees both. Nothing is matched to it, so it offers no
    recording.
    """
    # "Senate Judiciary Committee" as the docket's rows name it, "Judiciary",
    # so the station's title reads like the other Senate hearings'.
    cmte = re.sub(r"^\s*Senate\s+|\s+Committee\s*$", "",
                  rep.get("committee") or "", flags=re.I).strip()
    heard = rep.get("heard") or ""
    y = int(heard[:4]) if heard[:4].isdigit() else 0
    term = f"{y - 1 + y % 2}-{y + y % 2}" if y else ""
    return {
        "when": heard, "time": None, "what": "hearing",
        "committee": CN.official(cmte, "S", term) if cmte else None,
        "body": "S", "venue": None, "video_id": "", "watch": None,
        "predicted": None, "start": None,
        "state": "prestream" if heard < STREAM_START else "novideo",
        "candidate": None,
        # What the page reads to say where the date came from.
        "dated_by": "report",
        "docket_heard": sorted(docket_dates),
    }


def attach_hearing_reports(stations, reports, bid, idx, name_part, tally,
                           unmatched, pages=None):
    """Each report onto the station of the hearing it reports.

    That is the bill's Senate public hearing on the date the report gives --
    the station the Hearings tab draws with the recording. A list on the
    station, because a committee can hear a bill and then an amendment to it
    the same afternoon and file a report of each. A report whose date the
    docket has no Senate hearing for is not pinned to some other sitting: it
    is counted and named in `unmatched`, and stands on a station of its own
    under the date it gives (report_station).

    `pages` is {id: member} of whose page a member resolved in `idx` links
    to, where `idx` is a term's own frozen roster (build_bills says when).
    """
    heard = [s for s in stations
             if s.get("body") == "S"
             and "hearing" in (s.get("what") or "").lower()]
    docket = {s.get("when") for s in heard}
    own = {}
    for rep in reports:
        at = next((s for s in heard if s.get("when") == rep.get("heard")), None)
        if at is None:
            tally["unmatched"] += 1
            unmatched.append(f"{bid} {rep.get('heard')}")
            # One station for the date, which a bill's report and its
            # amendment's, filed the same afternoon, share.
            at = own.get(rep.get("heard"))
            if at is None:
                at = own[rep.get("heard")] = report_station(rep, docket)
                stations.append(at)
        else:
            tally["matched"] += 1
        page, got, miss = hearing_report_for_page(rep, idx, name_part, pages)
        at.setdefault("reports", []).append(page)
        tally["members"] += got
        tally["members_unresolved"] += miss
        tally["plain"] += bool(rep.get("fallback"))


# The four stops a bill passes, and what happened at each. "p" passed,
# "h" here now, "x" stopped here, "-" never reached.
#
# Read off the stages narrative.py built from the docket, which every bill
# has. house_status and senate_status from the status page would have been
# the obvious source and cover 1,387 of the current term's 2,234 bills and
# none of the archive.
# A HOUSE RESOLUTION NEVER GOES TO THE SENATE. HR and SR are the business of
# one chamber -- its rules, its own thanks and condolences -- and they never
# cross, never reach a governor and never become law. A concurrent resolution
# (HCR, SCR) and a constitutional amendment (CACR) do cross, so they are not
# in here. A special session numbers the same kinds with "SS" in front: SSHR 1
# of 2008 is the House adopting its rules and has two stops, not four.
ONE_CHAMBER = ("HR", "SR", "SSHR", "SSSR", BILL_OF_INTENT)
# The chamber a measure starts in, by its number.
OWN_CHAMBER = {"HB": "H", "HCR": "H", "HJR": "H", "HR": "H",
               "SB": "S", "SCR": "S", "SJR": "S", "SR": "S"}


# Written by build_bill_versions.py, which runs before this step. Absent is
# not an error: a tree where that step has not been run yet simply has no
# Versions tab anywhere, which is the truth about that tree.
try:
    VERSIONS = json.loads(
        Path("data/bill_versions.json").read_text(encoding="utf-8"))
except (OSError, ValueError):
    VERSIONS = {}


def passage(stages, kind, status="", bill="", passed=None, acted=None):
    """`passed` is the chambers whose own last decision on the bill, in the
    journey, carried it on (journey_state "p"); `acted` every chamber the
    journey has deciding anything, in the order they first did."""
    hands = [st.get("hand", "") for st in (stages or []) if st.get("hand")]
    # A CHAMBER THAT DECIDED ON THE BILL WAS REACHED. The stages are built
    # from the lines narrative.py recognises, and "Introduced and Laid on
    # Table MA VV" -- one of the two lines with which the House of June 2020
    # laid 45 Senate bills on the table -- is not one of them, so SB 436's
    # rail said the House was never reached by a bill the House had tabled.
    for b in (acted or ()):
        if b not in {h.split(":")[0] for h in hands}:
            hands.append(f"{b}:floor")
    if not hands:
        return ""
    # A RAIL IS FOUR CLAIMS, AND IT MAY NOT CONTRADICT THE FIFTH. It is drawn
    # from the hands the docket names, and an archived docket does not always
    # name them all: 29 bills that became law came out as "House: stopped
    # here ... Law: passed". Where the marks disagree with the outcome beside
    # them, no rail is drawn -- as for the 21,000 archived bills that had
    # none at all until now.
    if kind == "law" and not {"H", "S"} <= {h.split(":")[0] for h in hands}:
        return ""

    # TWO STOPS, NOT FOUR. The rail drew a resolution against a Senate it was
    # never going to see and a Law it could never become, and marked its own
    # chamber with an X for stopping there -- so 36 resolutions that were
    # ADOPTED showed a cross on the chamber that adopted them. What the rail
    # should say is simply: this chamber, and whether it adopted the thing.
    if bill and any(bill.upper().startswith(k) and
                    not bill.upper().startswith(k + "R") for k in ONE_CHAMBER):
        origin = hands[0].split(":")[0]
        if origin in ("H", "S"):
            # Or where the docket has the chamber adopting it: HR 13 of 2007,
            # "Introduced and Adopted", whose status field says in committee.
            adopted = (kind == "adopted" or "adopt" in (status or "").lower()
                       or origin in (passed or ()))
            return origin + ("p" if adopted else "x") + ("p" if adopted else "x")
    # A bill reaches the governor THROUGH BOTH CHAMBERS. SB286 never left the
    # Senate -- laid on the table, then killed under Senate Rule 3-23 -- and
    # its last docket row is "Enrolled Adopted, VV", which stage_of files with
    # the governor. Dropped from the HANDS, not just from the set derived from
    # them: taking it out of the set alone left "where it ended" pointing at a
    # stop that was no longer on the rail, so the Senate read as passed rather
    # than as where the bill stopped.
    if not {"H", "S"} <= {h.split(":")[0] for h in hands}:
        hands = [h for h in hands if not h.startswith("G")]
    # AND THE GOVERNOR DID NOT ACT ON A BILL A CHAMBER ENDED. HB 613 and HB 614
    # of 1993 passed both chambers; the Senate recalled and tabled each the
    # next day and killed it with every tabled bill on 25 May, the day of a
    # House row "ENROLLED", which stage_of files with the governor. The rail
    # read "Senate: Passed, Governor: Passed, Law: Did not become law" beside
    # "Killed". A bill that reached the governor is law, or was vetoed, or is
    # there now: where the status is none of those and a chamber's own last
    # word did not carry the bill on, the enrolment is no governor's stop.
    if (kind == "done" and passed is not None and "veto" not in (status or "").lower()
            and not {"H", "S"} <= set(passed)):
        hands = [h for h in hands if not h.startswith("G")]
    if not hands:
        return ""
    seen = {h.split(":")[0] for h in hands}
    moving = kind == "active"
    # Where it ended is the last hand it was in.
    last = hands[-1].split(":")[0]
    # IN THE ORDER THE BILL TRAVELLED. A Senate bill goes to the Senate first
    # and the rail drew House first for everything, so SB 139 opened with an
    # empty House stop it had never been to. The chamber of origin comes from
    # the bill's own first hand rather than from its number -- the record
    # answering for itself.
    origin = next((h.split(":")[0] for h in hands
                   if h.split(":")[0] in ("H", "S")), "H")
    # UNLESS THE RECORD HAS FILED A ROW UNDER THE WRONG CHAMBER, and both
    # chambers decided on the bill: then its number says which went first.
    # HB 1650 of 2022 passed the House and the Senate on 5 January; the
    # House's rows were entered on the 10th, and the rail opened in the
    # Senate. The Senate's "Introduced 9/7/2011" on HB 652 of 2011 predates
    # the House vote that sent it there. A bill decided on by one chamber
    # keeps the record's answer, whatever its number.
    own = OWN_CHAMBER.get(bill_prefix(bill), "") if bill else ""
    if own and own != origin and {"H", "S"} <= set(acted or ()):
        origin = own
    other = "S" if origin == "H" else "H"
    # The governor stop says what the GOVERNOR DID, not that the bill got as
    # far as the desk. Reaching a stop was being read as clearing it, so all
    # 68 vetoed bills drew a green check on the governor who vetoed them --
    # the rail stating the opposite of the sentence beside it.
    vetoed = kind == "veto" or "veto" in (status or "").lower()
    reached_gov = "G" in seen
    out = []
    for stop in (origin, other, "G"):
        if stop not in seen:
            out.append("-")
        elif stop == "G" and bill and bill_prefix(bill) in NO_GOVERNOR:
            # "Enrolled" is filed with the governor, but a CACR, HCR or SCR
            # never goes to one: 30 resolution rails read "Governor: passed".
            out.append("-")
        elif stop == "G":
            out.append("x" if vetoed else
                       "p" if kind == "law" else
                       "h" if moving else "p")
        elif moving and stop == last:
            out.append("h")
        elif reached_gov or (stop == origin and other in seen):
            # It CLEARED this chamber: the bill went on from here, and a later
            # visit does not undo that. The House that failed to override the
            # veto of HB 1442 by 165-149 had passed the bill in May, and
            # crossing it because the override was the last thing in the
            # docket said the House had rejected it.
            out.append("p")
        elif kind == "adopted":
            # A resolution both chambers adopted stopped in the second one
            # because it was finished, not because it was refused there:
            # CACR 13 of 2026 drew a cross on the Senate that passed it 23-1.
            out.append("p")
        elif stop in (passed or ()):
            # THE LAST HAND IS NOT ALWAYS WHERE IT WAS STOPPED. HCR 14 of 2026
            # was adopted by the House, 5 March, and never taken up by the
            # Senate; its rail crossed the House that adopted it, beside a chip
            # saying "Passed one chamber". SB 625 passed the Senate and then
            # the House, amended; the Senate refused the amendment and the
            # conference never reported, and the rail crossed the House that
            # had passed it. A chamber whose own last word carried the bill on
            # is passed, and the stop after it is where it went no further.
            out.append("p")
        elif stop == last:
            out.append("x")
        elif acted and stop in acted:
            # Not the last hand, and its own last word did not carry the
            # bill on: SB 223 of 2020's docket dates the House's referral
            # before the Senate's final vote, so the Senate was the last hand,
            # and the House -- which then laid it on the table -- read passed.
            out.append("x")
        elif stop == other and status == "Passed one chamber" and not moving:
            # ONE CHAMBER PASSED IT, AND THIS IS THE OTHER. CACR 9 of 1995
            # passed the Senate 18-6 on 21 February; the House's row of
            # introduction states the 16th, so the Senate was the last hand,
            # and the House -- which vacated it from committee and "RETURNED
            # TO SENATE PER HOUSE RULE 19B" without a vote -- read passed,
            # beside a chip saying one chamber had. Of a measure that is
            # finished: while it is still moving the second chamber has not
            # stopped it, and a cross there would say it had.
            out.append("x")
        else:
            out.append("p")
    # THE FOURTH STOP IS THE OUTCOME, NOT A PLACE -- and it was drawing the
    # "here now" ring on 175 bills that are going nowhere. A bill is never AT
    # the law stop: it either became law or it did not, and while it is still
    # moving the honest mark is that it has not got there. The ring is a
    # 3px pine circle that reads as active, so a bill laid on the table in a
    # chamber that has finished sitting was showing a bold "in progress" mark
    # on its outcome. Reported, and right.
    out.append("p" if kind == "law" else
               "x" if kind in ("done", "veto") else "-")
    # The order is part of the answer, so it travels with it.
    return origin + "".join(out)


# =============================================================== THE JOURNEY ==
#
# WHAT EACH CHAMBER DECIDED, AND WHEN: one line a decision, read from the
# docket, for the two places a bill's own view says how it got where it is --
# the dated stops of its rail and the "How it got here" row of On the record.
# Both read this one list, so the two cannot say different things.
#
# NOT THE STATUS PAGE'S HOUSE STATUS AND SENATE STATUS. Those were the rows On
# the record printed, and they are blank for one chamber on most bills: of
# this term's 2,234, 932 carry only a House status, 351 only a Senate one and
# 156 neither. HB 57 of 2025 passed the House on a voice vote on 13 February
# and its House field is empty. The docket has every decision, dated, in the
# chamber's own words -- the same events passage() and bill_disposition()
# already read.
#
# FLOOR DECISIONS ONLY: a motion a chamber carried that moved the bill --
# passed, killed, laid on the table, sent to interim study or back to
# committee, agreed to or refused the other chamber's amendment, adopted or
# rejected a conference report, overrode a veto or sustained it -- and a
# motion to pass that failed. Plus the governor, the chapter, and a CACR's
# referendum where the docket records one. Amendments, special orders,
# reconsiderations and rules suspensions are the Votes tab's, not this list's.
#
# Read clause by clause, because the clerks of 1989-1998 wrote a sitting's
# business on one line -- "COMM AM, AA VV; PASSED WITH AM VV; SJ20,P503" --
# and every era punctuates the motion, the vote and the outcome its own way.
# What a clause decided is the motion code the clerk wrote (MA, MF, AA...) or,
# on the oldest lines, the verb: "PASSED", "LAID ON THE TABLE", "RE-REFERRED".
# A clause naming a motion and no outcome -- "Ought to Pass [Not Voted On]",
# "Sen. Ward Moved Ought to Pass" -- decided nothing and is not a line.

# The event types that are never a floor decision. "introduced" is read for
# its date on its own; "Introduced and Adopted" and "Introduced ..., and Laid
# on Table" are typed floor or other, and are read.
J_NOT_FLOOR = {"hearing", "exec", "worksession", "report", "conference_meeting",
               "interim_report", "consent_off", "retained", "died", "introduced",
               "vacated", "subcommittee"}
# The motion codes are case-sensitive, as rollcall_outcomes reads them: "ma"
# is a syllable of a name as often as it is a motion.
# Lower case only where a voice vote follows: "Sen. Hollingworth susp rules
# for 3rd reading, ma 2/3vv; 3rd reading; ma vv" (HB 100 of 1999).
J_YES_CODE = re.compile(r"\b(?:MA|AA)\b|\b(?:ma|aa)(?=[,\s]+(?:2/3\s*)?vv\b)")
J_NO_CODE = re.compile(r"\b(?:MF|ML|AF|AL)\b|\b[am][fl](?=[,\s]+(?:2/3\s*)?vv\b)")
J_YES_WORD = re.compile(r"\b(?:adopted|adpoted|adotped|passed|overrid+en|concurred|"
                        r"carried|killed)\b", re.I)
J_NO_WORD = re.compile(r"\b(?:failed|fails|lost|defeated|lacking|not\s+adopted|"
                       r"sustained|overturned)\b", re.I)
# A tally, however the clerk wrote it: "RC 217-156", "RC(15-8)", "RC 16Y-8N",
# "DIV (166-103)", "DV 183-163", "Division 13Y-11N", "ROLL CALL: YEAS 5 NAYS
# 17", "ROLL CALL VOTE: YEA-13 NAYS-11" (HB 377 of 1989).
J_TALLY = re.compile(
    r"\b(?P<k>RC|DIV|DV|Division|Roll\s*Call)\b(?:\s+vote)?\.?\s*[:,]?\s*\(?\s*"
    r"(?:YEAS?\s*[-:]?\s*)?(?P<y>\d{1,3})\s*[Yy]?\s*(?:[-–]|,?\s*NAYS?\s*[-:]?)\s*"
    r"(?P<n>\d{1,3})(?!\d)", re.I)
J_RC_BARE = re.compile(r"\bRC\b|\bRoll\s*Call\b", re.I)
# "VV", "2/3VV", "MA 2/3 VV". Upper case only: it is a code, not a word.
J_VOICE = re.compile(r"(?<![A-Za-z])(?:VV|vv)\b|\bvoice\s+vote\b")
# Business that is not a decision about the bill's fate, however it was
# carried: the order of the day, the rules, a reconsideration (whose result is
# the next decision), a bill coming off the table or the consent calendar, a
# motion recorded as pending or not voted on, the chair's rulings.
# Not "GOVERNOR'S VETO SUSTAINED RC(11-11) (VETO MESSAGE PRINTED)" (SB 105 of
# 1993): the message was printed; the vote is the House's.
J_SKIP = re.compile(
    r"enrolled|special\s+order|reconsider|notice\s+of|^\s*(?:secs?|sections?)\b|"
    r"\b(?:remov\w*|taken|take)\s+(?:\w+\s+){0,2}from\s+(?:the\s+)?(?:table|consent)|"
    r"from\s+the\s+consent|pending\s+motion|(?<!message )\bprint\w*|"
    r"limit\w*\s+debate|divisible|divided|previous\s+question|moved\s+the\s+question|"
    r"non-?\s?germane|\brul(?:ed|ing)\b|rescind|technical\s+(?:and\s+\w+\s+)?correction|"
    r"sent\s+to\s+(?:the\s+)?governor|^\s*sections?\b|change\s+rept|deadline|"
    r"late\s+(?:drafting|filing|introduction)|withdr[ae]w|\bappoint", re.I)
J_NOT_VOTED = re.compile(r"^[^;]*?\bnot\s+voted\s+on\b\s*[)\]]?\s*,?\s*", re.I)
# A VOTE TO SUSPEND THE RULES DECIDES ONLY THAT THE RULES ARE SUSPENDED, and
# the business it names is what it lets the chamber take up, not what the
# chamber then did with it. "REPS WHEELER & BURLING MOVED TO SUSP RULES FOR
# CONF COMM REPORT, ML RC(221-135)" (HB 1 and HB 2 of 1997) is 221 members
# wanting to take the report up, short of two thirds -- and it read as the
# House rejecting the budget's conference report. "Rules Suspension to
# consider at the present time ... MF lacking necessary 2/3 RC 197-143" (CACR
# 21 of 2020) read as the House defeating a CACR a majority wanted to hear.
# So the suspension is taken out of the clause, through its own outcome and
# the vote that carried it, and what the clause says after that is read as
# usual: "Sen. Below Moved Rule Suspension, MA, VV (2/3rds Nec) Sen. Below
# Moved Rerefer, MA, VV" (HB 542 of 1999) is the bill sent back to committee.
J_SUSPEND = re.compile(r"\bsusp(?:\.|\w*)", re.I)
# "RULES SUSPENDED PLACED ON THIRD READING PASSED/ADOPTED" (HB 750 of 1989),
# "JOINT RULES SUSPENDED CONF COMM REPORT ADOPTED": the clerk's past tense,
# with no vote of its own. The words go, and the business after them stays.
J_SUSPENDED = re.compile(r"\b(?:(?:joint|jt\.?|house|senate)\s+)?rules?\s+suspended\b\s*[:;,]?",
                         re.I)
# The business a suspension would allow "if passed" is not its outcome.
J_IF_PASSED = re.compile(r"\b(?:if|upon|when)\s+(?:so\s+)?(?:passed|adopted|passage)\b", re.I)
# Its outcome is the first motion code after it, or on a line with none the
# first word of one -- not "adopted" in "by the adopted Senate deadline for
# HBs. 2/3 necessary, MA, RC 24Y-0N" (HB 652 of 2012).
J_SUSP_CODE = re.compile(r"\b(?:MA|MF|ML|AA|AF|AL)\b")
# The purpose, not a rule it sets aside: "SUSP RULES TO REF TO FINANCE", "for
# late ref to Finance" -- not "Rules Suspension to consider at the present
# time without required referral to committee" (HB 1650 of 2022).
J_SUSP_REFERRAL = re.compile(r"\b(?:to|for)\s+(?:late\s+)?ref(?:er(?:ral)?|\.)?\s+to\s+"
                             r"(?P<c>[A-Za-z0-9][A-Za-z0-9&/ ]*?)\s*(?:,|\(|\bafter\b|$)", re.I)
J_SUSP_WORD = re.compile(r"\b(?:adopted|failed|lost|lacking|carried|defeated|not\s+getting)\b",
                         re.I)
# What follows a suspension's outcome and is still the suspension's: the vote
# and the two thirds it needed.
J_SUSP_VOTE = re.compile(
    r"(?:[\s,;:.()]*(?:\d\s*/\s*\d\s*(?:rds?)?\s*(?:VV|nec\w*\.?)?|"
    r"(?:RC|DV|DIV|Division)?\s*\(?\s*\d{1,3}\s*[YN]?\s*-\s*-?\s*\d{1,3}\s*[YN]?|"
    r"(?:VV|RC|DV|Division|DIV|MF|MA|ML|vote|the|by|two-thirds|lacking|obtaining|getting|not)\b|"
    r"(?:required|nec|req)\w*\.?|"
    r"\d{1,2}/\d{1,2}/\d{2,4}))*[\s,;:.()]*", re.I)


def _j_unsuspend(clause):
    """A clause without the suspension of the rules in it: "" where that is
    all it was."""
    m = J_SUSPEND.search(clause or "")
    if not m:
        return clause
    past = next((x for x in J_SUSPENDED.finditer(clause)
                 if x.start() <= m.start() < x.end()), None)
    # What was before it and what comes after are kept apart, each a clause
    # of its own: "REPS PALUMBO & CHAMBERS SUSP RULES TO CONSIDER, MA 2/3VV,
    # ADOPTED" (HCR 6 of 1989) is the resolution adopted, not the movers.
    if past and not re.search(r"\bmov\w*|\bmotion\b", clause[:past.start()], re.I):
        return _j_unsuspend("; ".join(x for x in (clause[:past.start()].strip(" ,;:/"),
                                                   clause[past.end():].strip(" ,;:/")) if x))
    head = clause[:m.start()]
    # Blanked rather than removed, so positions in the rest still count.
    rest = J_IF_PASSED.sub(lambda x: " " * len(x.group(0)), clause[m.end():])
    o = J_SUSP_CODE.search(rest) or J_SUSP_WORD.search(rest)
    if not o:
        # No outcome: the clause from the suspension on is the motion,
        # wrapped onto the next row if it goes on (_j_rows joins it).
        return head.strip(" ,;:")
    end = J_SUSP_VOTE.match(rest, o.end()).end()
    left = _j_unsuspend("; ".join(x for x in (head.strip(" ,;:"), rest[end:].strip(" ,;:"))
                                  if x))
    # EXCEPT A SUSPENSION TO SEND THE BILL TO A SECOND COMMITTEE, which is
    # the referral: "COMM AM, AA VV; PASSED WITH AM VV; REPS A TORR & TROMBLY
    # SUSP RULES TO REF TO FINANCE, MA 2/3VV" (HB 1162 of 1996), whose House
    # passage was in March, after Finance.
    ref = J_SUSP_REFERRAL.search(rest, 0, o.start())
    if ref and re.match(r"MA|AA|adopted|carried", o.group(0), re.I):
        return f"Referred to {ref.group('c').strip()}" + (f"; {left}" if left else "")
    return left


def _j_suspension_failed(raw):
    """Where in a row a vote to suspend the rules failed, or -1.

    _j_unsuspend takes the vote out of the clause, which is right for what
    the bill's line says and loses that the chamber voted: "REPS GROSS &
    CHAMBERS MOVED TO SUSP RULES, ML DIV(213-115)" and then "REP KURK MOVED
    TO RECONSIDER, MA VV" (HB 322 of 1991) is the House taking up again the
    suspension it had just refused, not its refusal of the Senate's
    amendment a month before. Not "RULES SUSPENDED", which is the clerk's
    past tense for one that carried."""
    for x in re.finditer(r"[^;]+", raw or ""):
        clause = x.group(0)
        m = J_SUSPEND.search(clause)
        if not m or any(y.start() <= m.start() < y.end()
                        for y in J_SUSPENDED.finditer(clause)):
            continue
        rest = J_IF_PASSED.sub(lambda y: " " * len(y.group(0)), clause[m.end():])
        o = J_SUSP_CODE.search(rest) or J_SUSP_WORD.search(rest)
        if o and not re.match(r"MA|AA|adopted|carried", o.group(0), re.I):
            return x.start() + m.start()
    return -1


# The procedural motions whose outcome the clerk can put in the next clause:
# "Enrolled Bill Amendment{2230}; Adopted", "Sen. Gordon Moved Remove From
# Table; MA, VV". Not a finished act -- "REP BUCKLEY WITHDREW RECOMMIT
# MOTION; ADOPTED VV" is SCR 1 of 1995 adopted.
J_TAKES_OUTCOME = re.compile(r"\benroll|\b(?:remov\w*|taken|take)\s+(?:\w+\s+){0,2}from\s+"
                             r"(?:the\s+)?table|\breconsider|special\s+order", re.I)


# What a clause is about, tried in this order: a clause about a conference
# report is not an adoption of the bill, and one about the other chamber's
# amendment is not an amendment of this one.
J_ACTS = [
    # A vote on the veto names the veto. "SUSTAINED" alone is also the House
    # upholding its chair: "RULING OF CHR" / "SUSTAINED VV; PASSED WITH AM
    # RC(233-122)" (HB 1075 of 1998, which became law) drew a veto the
    # governor never made. A vote wrapped onto the next row, "...; GOVERNOR'S
    # VETO" / "SUSTAINED RC(221-117)" (HB 332 of 1995), is joined by _j_rows.
    ("veto_vote", re.compile(r"\bveto\w*\b[^;]{0,60}?\b(?:overrid|sustain)|"
                             r"\b(?:overrid|sustain)\w*[^;]{0,60}?\bveto|"
                             r"notwithstanding|\bshall\b[^;]{0,40}\bbecome\s+law", re.I)),
    # "As Passed by the House {2199}" is the name of the version a committee
    # of conference proposes, not a chamber passing the bill: all fourteen
    # rows in the record that say it are conference reports. The Senate's
    # "As Passed by the House {2199} RC 13Y-11N, Adopted" (HB 429 of 2007)
    # is it adopting conference report #2199 -- which read as the Senate
    # passing the bill 13-11, three weeks after it did so on a voice vote.
    ("conference", re.compile(r"conf(?:erence)?\.?\s*comm(?:ittee)?\.?\s*rep(?:ort|t)?\b"
                              r"|committee of conference report|\bC\s?of\s?C\s+rep"
                              r"|\bas\s+passed\s+by\s+(?:the\s+)?(?:house|senate)\b", re.I)),
    ("accede", re.compile(r"acced", re.I)),
    ("nonconcur", re.compile(r"non-?\s?conc|\bnonc\b|refus\w*\s+to\s+(?:concur|accept)",
                             re.I)),
    ("concur", re.compile(r"\bconc(?!urrent)(?:ur\w*|urrence)?\b", re.I)),
    # "Inexpedient to Legislate, Senate Rule 3-23, Adjournment 09/16/2020"
    # and, from 2025, the same without "Adjournment": the rule that kills a
    # bill still on the table. No motion code, because nothing was moved.
    # And the older rules to the same end: "ITL PER JOINT RULE 10(c)(1)"
    # (SB 4 of 1989), "DIED ON TABLE (RULE 6F)" (HB 250 of 1990).
    ("died", re.compile(r"(?:inexpedient\s+to\s+legislate|\bITL\b),?\s*(?:per\s+|under\s+)?"
                        r"(?P<rule>(?:senate|house|joint)\s+rule\s+[\w\-]+(?:\([\w]+\))*)"
                        r"|died\s+on\s+(?:the\s+)?table\s*\(\s*(?P<rule2>rule\s+[\w\-]+)\s*\)",
                        re.I)),
    # And the clerk's spellings: "REP HOLDEN MOVED REF FOR STUDY, MA VV" (CACR
    # 25 of 1992), "Sen. Below moved Rerefer to Iterim Study, MA, VV" (HB 109
    # of 2000).
    ("study", re.compile(r"\bin?terim\s+study|\bint\.?\s+study|\bRFS\b|"
                         r"\bref(?:er\w*)?\.?\s+for\s+study", re.I)),
    ("postponed", re.compile(r"indefinite\w*\s+postpone|\bindef\w*\.?\s+post", re.I)),
    # "Inexpedient to Lehgislate, MA, VV" (HB 353 of 2002): the clerk's
    # typing, so the first word is enough.
    # And "Ought Not to Pass", the report against an address for the removal
    # of a judge, adopted: "Ought Not to Pass: MA DIV 220-106" (HA 1 of 2010).
    ("killed", re.compile(r"\binexpedient\b|\bITL\b|\bkilled\b|"
                          r"\bought\s+not\s+to\s+pass\b", re.I)),
    ("tabled", re.compile(r"\b(?:lay|laid|lie|placed)\b[^;]{0,40}?\b(?:up)?on\s+(?:the\s+)?table\b"
                          r"|\btabled\b|\bLOT\b", re.I)),
    ("recommitted", re.compile(r"\brecommit\w*|\bre-?\s?refer\w*|\breferred\s+back",
                               re.I)),
    # "Adopted" is the passage of a resolution only where it is the motion:
    # "ADOPTED VV", "INTRODUCED AND ADOPTED", "PASSED/ADOPTED", "ADOPTED WITH
    # AM". After another motion it is that motion's outcome -- "ITL REPORT
    # ADOPTED" is a bill killed.
    ("passed", re.compile(r"ought\s+to\s+(?:pass|adopt)|\bOTP\w*|\bthird\s+reading\b|"
                          r"\b3rd\s+r(?:ea)?d(?:in)?g\b|\bOT\s?3\s?rd?g\b|\bpassed\b|^\s*pass\b|"
                          r"^\s*(?:[HS]\s+)?(?:introduced\s+and\s+)?adopt(?:ed|ion)?\b|"
                          r"\badopted\s+with\s+am|\bresolution\s+adopted\b", re.I)),
]
# "SEN RUSSMAN MOVED ITL ON BILLS LOT, MA VV" (SB 66 of 1993) kills the bills
# on the table; the table is where they were, not what was moved.
J_ON_THE_TABLE = re.compile(r"\b(?:on\s+)?(?:all\s+)?bills\s+(?:LOT|(?:laid\s+)?on\s+"
                            r"(?:the\s+)?table)\b", re.I)
# An amendment's own vote, not the bill's: "COMM AM, AA VV", "Committee
# Amendment # 2025-2308s, RC 16Y-8N, AA", "Sen. Birdsell Floor Amendment #
# 2026-1719s, AA, VV", "FLAM # 2025-1311h (Rep. McFarlane): AF DV 57-286".
# Adopted, it tells that day's passage that the bill passed amended --
# whichever of the two the clerk entered first: "Sen. Larsen moved OTP, MA,
# VV; Sen. Larsen Fl. Amend. (0179) AA, VV" (SR 3 of 1999). And the clerks'
# other ways of writing who offered it and what it was: "Sen. McCarley,
# Floor Amendment., {1666}" (HB 265 of 1999), "Flr AM {1759h}, AA" (SB 310
# of 2006).
J_AMEND_SUBJ = re.compile(
    r"^\s*(?:(?:Reps?|Sens?|Senator)[.,]?\s+[^,;:]*?,?\s+)?(?:adopt(?:ion\s+of)?\s+(?:the\s+)?)?"
    r"(?:prop(?:osed)?\s+)?(?:maj(?:ority)?\.?\s+|min(?:ority)?\.?\s+)?"
    r"(?:comm(?:ittee)?\.?\s+|floor\s+|flr?\.?\s+|senate\s+|house\s+|approp\s+)?"
    r"(?:am(?:end(?:ment)?)?s?\b|FLAM\b)", re.I)
# "Ought to Pass W/Majority Amendment, {1330}" (SB 108 of 1999), "Ought to
# Pass with Part of AM #1223h" (SB 492 of 2008).
J_AMENDED = re.compile(r"\bw(?:ith|/)\s*(?:part\s+of\s+)?(?:the\s+)?"
                       r"(?:maj(?:ority)?\.?\s+|min(?:ority)?\.?\s+|comm(?:ittee)?\.?\s+|"
                       r"floor\s+|fl\.?\s+)?am|\bas\s+amended|\bOTP\s*/\s*AM|\bOTPA\b|"
                       r"with\s+amendments?\b", re.I)
# AN AMENDMENT ADOPTED IN THE CLAUSE THAT PASSES THE BILL. The Senate of
# 1999-2002 wrote the two as one: "Sen. Larsen Floor Amendment {0965}, AA,
# VV, OT3rdg, RC 14Y-8N, MA" (HB 117 of 1999) is the bill passing amended,
# and it read "Passed, 14-8"; so is "Ought to Pass, MA, VV, Sen. Brown Floor
# Amendment, {1865}, RC 14Y-8N, AA" (HB 626 of 1999), the amendment after
# the motion. Adopted, with no other motion's code between the amendment
# and its AA.
J_AMEND_ADOPTED = re.compile(r"(?i:\bam(?:end(?:ment)?)?s?\b|\bFLAM\b)"
                             r"(?:(?!\b(?:MA|MF|ML|AF|AL)\b)[^;])*?\bAA\b")
# Past tense on the oldest lines is the outcome: "LAID ON THE TABLE",
# "RE-REFERRED TO HEALTH", "REFERRED TO INTERIM STUDY", with no code after.
J_DONE_VERB = re.compile(r"\b(?:laid|tabled|re-?referred|recommitted|referred|"
                         r"postponed)\b", re.I)
# "Ought to Pass, MA. VV. Rule 24 (refer to Finance)" and "..., AA, Refered
# to Finance Rule #24" (HB 224 and HB 1240 of 1999-2000) are the Senate
# sending a bill it approved to Finance, as much as "PASSED WITH AM AND REF
# TO FINANCE" is.
J_REFERRED_TO = re.compile(
    r"\bref(?:er(?:r?ed)?)?\.?\s+to\s+(?P<c>(?!interim)[A-Za-z][A-Za-z&/ ]{1,40}?)"
    r"(?=\s*(?:\(|\)|\[|\]|rule\b|;|,|$|\d))", re.I)
J_BARE_REFERRAL = re.compile(r"^\s*ref(?:er(?:red)?)?\.?\s+to\s+(?P<c>[A-Za-z][A-Za-z&/ ,]+?)"
                             r"\s*(?:\(|\[|\d|rule\b|$)", re.I)
J_SECOND_COMMITTEE = [(re.compile(r"^fin", re.I), "Finance"),
                      (re.compile(r"^approp", re.I), "Appropriations"),
                      (re.compile(r"^(?:ways|w\s*&\s*m)", re.I), "Ways and Means"),
                      (re.compile(r"^capital", re.I), "Capital Budget")]
J_THIRD = re.compile(r"third\s+reading|3rd\s+r(?:ea)?d(?:in)?g|\bOT\s?3\s?rd?g\b", re.I)
J_SIGNED = re.compile(r"signed\s+by\s+(?:the\s+)?gov|governor\s+signed", re.I)
J_VETOED = re.compile(r"vetoed\s+by\s+(?:the\s+)?gov|^\s*vetoed\b", re.I)
# "...enacted in accordance with Article 44, Part II of New Hampshire
# Constitution without signature of the Governor, July 16, 2008" (SB 312 of
# 2008) has no "the" before "signature".
J_UNSIGNED = re.compile(r"law\s+without\s+(?:the\s+)?(?:governor'?s\s+)?signature|"
                        r"without\s+(?:the\s+)?signature\s+of\s+the\s+governor", re.I)
J_OTHER_BILL = re.compile(r"\b(?:HB|SB|HCR|SCR|HJR|SJR|CACR)\s*(\d+)", re.I)
J_WAIVED = re.compile(r"\bwaiv\w*\b[^;]*\breferral|\breferral\b[^;]*\bwaiv", re.I)
# A MOTION DIVIDED TO TAKE THIS BILL OUT OF IT, and the vote on the bills
# left in it. The House reconsidered its third reading of 14 March 2012 to
# take HB 1659 out, "Divide Third Reading Motion to Remove HB1659: Speaker
# Ordered", then "Remaining Bills to Third Reading: MA VV", and sent HB 1659
# to a second committee -- and the second row, filed under HB 1659 as the
# first was, read as the House passing it.
J_DIVIDED_OUT = re.compile(r"\bdivide\w*\b[^;]*?\bremov\w*\b", re.I)
J_REMAINING = re.compile(r"^\s*remaining\s+bills\b", re.I)
# Where a governor's line starts saying when the law takes effect.
J_EFF_ANY = re.compile(r"\beff(?:ective|\.|:|-)?(?![a-z])|\btake\s+effect", re.I)
# A LAW WITH MORE THAN ONE EFFECTIVE DATE HAS NO ONE DATE TO STATE. "eff. I.
# Sec 3 1/1/2027 II. Rem eff 8/1/2026" (HB 131 of 2026), "eff as provided in
# Sec 3" (HB 557 of 2025), "EFF: 06/05/98*", and the governor's row carried on
# a row of its own: "I. Sections 5 & 6 Eff. 07/01/2011" and then "II.
# Remainder Eff. 08/12/2007" (HB 337 of 2007), which read as "in effect 1 Jul
# 2011" for a law most of which took effect four years earlier.
J_EFF_SEVERAL = re.compile(
    r"\bsec(?:tion)?s?\b|\bsec\.|\bremain\w*|\brem\b|as\s+provided|\bprov\b|"
    r"\bpart\s+[IVX]+\s+(?:eff|shall)|(?:^|[\s;.,])[IVX]{1,4}\.\s|multiple|\*|\bparagraph", re.I)
# The governor's row carried on in rows of its own.
J_EFF_MORE = re.compile(r"^\s*(?:\*|[IVX]{1,4}\.|part\s+[IVX]+\b|(?:the\s+)?remainder\b|"
                        r"effective\b|eff\b|sec(?:tion)?s?\b)", re.I)
J_DAY = re.compile(r"(?<![\d/])(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4}|\d{2})(?![\d/])")
J_MONTH_DAY = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+"
                         r"(\d{1,2}),?\s+(\d{4})\b", re.I)
# The day a clause states at its end: "Adopted and read a 3rd time MA VV
# 01/05/22". Not a sitting the chamber met "in recess of", and not a date in
# brackets, the older dockets' "done as of" a sitting: "Introduced and
# Adopted [11/30/2011]", entered on 4 January.
J_CLAUSE_DAY = re.compile(r"(?<!recess of )(?<!recess of\) )(?<!recess )(?<![\d/\[])"
                          r"(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\W*$", re.I)
# The Senate's way: the day as a clause of its own at the end of the row,
# "Conference Committee Report #2024-2290c , Adopted, VV; 06/13/2024".
J_ROW_DAY = re.compile(r";\s*(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\s*$")
# "Introduced ...", "5/3/2001 Introduced and ref to Judiciary", "Introducing
# and referred to Public Affairs" (SB 12 of 1999), "Sen. Birdsell Moved
# Introduction; 2/3 necessary, MA, VV" (SCR 1 of 2023).
J_INTRO_ROW = re.compile(r"^\s*(?:\d{1,2}/\d{1,2}/\d{2,4}\s+)?introduc(?:ed|ing|tion)\b|"
                         r"\bmoved\s+introduction\b", re.I)
J_REF_TALLY = re.compile(r"\(\s*([\d,]{3,})\s*[-–]\s*([\d,]{3,})\s*\)")
# The other chamber agreeing to a second committee of conference: "HOUSE
# ACCEDED TO REQ FOR NEW CONF COMM, REP R FOSTER MA VV" (HB 723 of 1997),
# "Senator Foster Moved Accede to House Request for New C of C; MA, VV" (HB
# 1640 of 2008). Not "REFUSED TO ACCEDE TO REQUEST OF NEW CONFERENCE
# COMMITTEE" (HB 1248 of 1990).
J_NEW_CONFERENCE = re.compile(
    r"(?<!refused to )(?<!refuses to )\bacced\w*\s+to\s+(?:(?:house|senate)\s+)?req(?:uest)?\s+"
    r"(?:for|of)\s+(?:a\s+)?new\s+(?:conf|c\s?of\s?c|committee\s+of\s+conf)", re.I)
J_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
         "Nov", "Dec"]
# The glyph each decision is drawn with, which carries its state as well as
# its colour: a check for a decision that moved the bill on, a cross for one
# that stopped it, and a turning arrow for one that sent it round again --
# tabled, back to committee, to interim study, the other chamber's amendment
# refused.
J_MARK = {"passed": "p", "adopted": "p", "concurred": "p", "conf_adopted": "p",
          "override": "p", "signed": "p", "unsigned": "p", "law": "p",
          "ratified": "p",
          "killed": "x", "failed": "x", "postponed": "x", "died": "x",
          "conf_rejected": "x", "conf_refused": "x", "sustained": "x",
          "vetoed": "x", "not_ratified": "x",
          "tabled": "h", "study": "h", "recommitted": "h", "referred": "h",
          "nonconcurred": "h"}
# The chamber carried the bill on at this line.
J_PASSING = {"passed", "adopted", "referred"}


def _j_prose_date(iso, year=True):
    """"2026-01-11" -> "11 Jan 2026"."""
    try:
        y, m, d = (int(x) for x in iso.split("-"))
    except (AttributeError, ValueError):
        return ""
    return f"{d} {J_MON[m - 1]}" + (f" {y}" if year else "")


def _j_iso(m, d, y):
    y = int(y)
    y += (1900 if y > 50 else 2000) if y < 100 else 0
    try:
        return _date(y, int(m), int(d)).isoformat()
    except ValueError:
        return ""


def _j_outcome(seg, at):
    """True, False or None: what became of the motion a clause names -- the
    first outcome after it, else the last before it."""
    toks = sorted((m.start(), val) for rx, val in
                  ((J_YES_CODE, True), (J_NO_CODE, False),
                   (J_YES_WORD, True), (J_NO_WORD, False))
                  for m in rx.finditer(seg))
    if not toks:
        return None
    after = [t for t in toks if t[0] >= at]
    return (after[0] if after else toks[-1])[1]


def _j_motions(seg):
    """[(act, match)]: every motion a clause names, in the order it names
    them. Where two readings claim the same words -- "Non-Concurs" is a
    refusal, not a concurrence; "Inexpedient to Legislate, Senate Rule 3-23"
    is the rule, not a vote -- the one tried first keeps them.

    An amendment's own vote is ("amendment", None): "COMM AM, AA VV"."""
    got = []
    for act, rx in J_ACTS:
        for m in rx.finditer(seg):
            if any(m.start() < g.end() + 2 and m.end() > g.start() - 6
                   for _a, g in got):
                continue
            got.append((act, m))
    got.sort(key=lambda x: x[1].start())
    if J_AMEND_SUBJ.search(seg) and all(a == "passed" for a, _m in got) and not re.search(
            r"\bOT\s?3\s?rd?g\b|ought\s+to\s+pass|\bpassed\b|third\s+reading", seg, re.I):
        return [("amendment", None)]
    return got


def _j_act(seg):
    """The first motion a clause names, or None."""
    got = _j_motions(seg)
    return got[0][0] if got else None


def _j_has_outcome(seg):
    return bool(J_YES_CODE.search(seg) or J_NO_CODE.search(seg)
                or J_YES_WORD.search(seg) or J_NO_WORD.search(seg))


# A clause that is nothing but a vote and its outcome: "RC 15Y-8N, Adopted".
J_OUTCOME_ONLY = re.compile(
    r"^\s*(?:(?:RC|DV|DIV|Division|VV)\b[^,;A-Za-z]*(?:[YN]\b[^,;A-Za-z]*)*,?\s*)*"
    r"(?:adopted|failed|MA|MF|ML|AA|AF|AL)\b", re.I)


# "1427s; 1851s; and 1925s", "1807s;1824s;and 1932s", "#1735h; #1843h".
J_AMEND_LIST = re.compile(r"(?<=\d[hse]);(?=\s*(?:and\s+)?#?(?:\d{4}-)?\d{3,4}[hse]\b)")


def _j_segments(raw):
    """The clauses of one docket line. A motion whose outcome the clerk put in
    the next clause is one clause: "Sen. Gray Moved Nonconcur with the House
    Amendment; Requests C of C, MA, VV", "Conference Committee Report #
    2026-2114c; RC 15Y-8N, Adopted".

    A SEMICOLON IN A LIST OF AMENDMENTS IS NOT THE END OF A CLAUSE. "House
    Non-Concurs with Senate Amendment 1427s; 1851s; 1898s; and 1925s (Rep.
    Kurk): MA RC 180-163" (HB 1636 of 2018) left "House Non-Concurs with
    Senate Amendment 1427s" to stand alone, which read as the House refusing
    with no count -- and so did the motion before it, which failed."""
    out = []
    raw = J_AMEND_LIST.sub(",", raw or "")
    for p in (y.strip() for x in raw.split(";")
              for y in _j_unsuspend(x.strip()).split(";")):
        if not p:
            continue
        # Not a floor amendment's own vote after a motion that was only
        # made: "Rep Goley moved OTP/AM; Rep Goley Fl Am{3930}, AA
        # RC(190-152)" (HB 1475 of 2000) is the amendment carrying, not the
        # bill -- which was killed that morning.
        nxt = _j_act(p)
        # AN OUTCOME ALONE IS THE OUTCOME OF THE CLAUSE BEFORE IT, whatever
        # that clause was about: "Enrolled Bill Amendment{2230}; Adopted" is
        # the enrolled bill amendment adopted (HB 1243 of 2006), and "Enrolled
        # Bill; Adopted, SJ 14" the enrolment (HB 235 of 2000). Read apart, the
        # bare "Adopted" was a committee report adopted -- a kill, on two bills
        # that became law.
        # BUT NOT A RECONSIDERATION'S. "Re-Referred to Res, Rec & Dev
        # committee RC(158-154); Rep Royce moved to reconsider, ML
        # RC(156-157)" (SB 135 of 1999, read whole since 1 October from the
        # two rows the database cut it into) is the bill sent back and a
        # motion to reconsider that failed, not a re-referral that failed.
        if (out and not _j_has_outcome(out[-1]) and _j_has_outcome(p)
                and not re.search(r"withdr[ae]w", out[-1], re.I)
                and not (J_RECONSIDER.search(p) and not J_RECONSIDER.search(out[-1])) and (
                (_j_act(out[-1]) and (
                    nxt is None or J_OUTCOME_ONLY.match(p)
                    or (nxt == "amendment" and _j_act(out[-1]) == "conference")))
                or (J_TAKES_OUTCOME.search(out[-1]) and J_OUTCOME_ONLY.match(p)))):
            out[-1] = f"{out[-1]}; {p}"
        # Across a clause that is neither motion nor outcome: "Sen. Prescott
        # moved Nonconcur with House Amendment #1958h, NT; Requests C of C;
        # MA VV" (SB 255 of 2015) is the Senate refusing the amendment.
        elif (len(out) > 1 and J_OUTCOME_ONLY.match(p) and not _j_act(out[-1])
              and not _j_has_outcome(out[-1]) and _j_act(out[-2])
              and not _j_has_outcome(out[-2])):
            out[-2:] = [f"{out[-2]}; {out[-1]}; {p}"]
        else:
            out.append(p)
    return out


def _j_tally(seg, at=0):
    """("RC"|"DV"|"VV", yeas, nays): the vote the clause records, preferring
    one after the motion's own words."""
    ms = list(J_TALLY.finditer(seg))
    m = next((x for x in ms if x.start() >= at), ms[-1] if ms and not at else None)
    if m:
        k = m.group("k").upper()
        return ("RC" if k.startswith(("RC", "ROLL")) else "DV",
                int(m.group("y")), int(m.group("n")))
    if J_VOICE.search(seg):
        return ("VV", None, None)
    if J_RC_BARE.search(seg):
        return ("RC", None, None)
    return ("", None, None)


def _j_roll_call(rcs, date, body, vote, said):
    """The roll call a docket line's tally names: (vote, passed or None).

    The ballots are the headline wherever the docket's count and the roll
    call's differ (16 September), and what the vote decided is the roll
    call's `passed`, which rollcall_outcomes.py reads from the docket and the
    Journals -- SB 82 of 2005, "Ought to Pass with Amendment, RC 10Y-14N, MA",
    is a motion the Journal records as failing."""
    kind, y, n = vote
    if kind != "RC":
        return vote, None
    mine = [r for r in (rcs or []) if r.get("date") == date and r.get("body") == body]
    if y is not None:
        same = [r for r in mine
                if (r.get("yeas"), r.get("nays")) == (y, n)
                or (r.get("yeas_stated"), r.get("nays_stated")) == (y, n)]
        # Two roll calls of a day can share a count: CACR 20 of 2018 failed
        # to pass 13-11 and was laid on the table 13-11 the same morning.
        # The one whose outcome is the line's own is this line's.
        r = next((r for r in same if said is not None
                  and bool(r.get("passed")) == bool(said)), same[0] if same else None)
        if r:
            return ("RC", r.get("yeas"), r.get("nays")), r.get("passed")
        return vote, None
    cand = [r for r in mine if not r.get("procedural")
            and bool(r.get("passed")) == bool(said)]
    if said is not None and len(cand) == 1 and cand[0].get("yeas") is not None:
        return ("RC", cand[0]["yeas"], cand[0]["nays"]), cand[0].get("passed")
    return vote, None


def _j_decide(seg, bid, rcs=(), date="", body=""):
    """One clause, read: a dict of what it decided, "amended" for an amendment
    the chamber adopted, or None."""
    if J_SIGNED.search(seg) and not re.search(r"overrid", seg, re.I):
        # "{LSR 0155, HB 154, CH. 183, 1997 SIGNED BY GOV 6/18/97}" is on
        # 1996's HB 1179 and is about another bill's signature.
        if any(re.sub(r"\s+", "", m.group(0)).upper() != bid
               for m in J_OTHER_BILL.finditer(seg)):
            return None
        return {"act": "signed"}
    if J_VETOED.search(seg) and not re.search(r"overrid|sustain", seg, re.I):
        return {"act": "vetoed"}
    if J_UNSIGNED.search(seg) and not re.search(r"overrid", seg, re.I):
        return {"act": "unsigned"}
    # A motion "not voted on" decided nothing, and what the clause says after
    # it may have: "Ought to Pass (not voted on), Sen. Larsen Moved Laid on
    # Table, MA, VV" (HB 101 of 2001) is the Senate laying the bill on the
    # table.
    seg = J_NOT_VOTED.sub("", seg)
    if not seg.strip() or J_SKIP.search(seg):
        return None
    on_table = bool(J_ON_THE_TABLE.search(seg))
    seg = J_ON_THE_TABLE.sub(" ", seg)
    motions = _j_motions(seg)
    if motions and motions[0][0] == "amendment":
        return "amended" if _j_outcome(seg, 0) else None
    # THE LAST MOTION THAT DECIDED SOMETHING. The oldest lines put a
    # sitting's motions in one clause: "REP HATCH SUBST ITL, ML RC
    # (149-201), PASSED/ADOPTED VV" (HB 18 of 1989) is a kill that failed
    # and then the bill passing. Each motion is read up to the next.
    got, since = None, 0
    for i, (act, m) in enumerate(motions):
        end = motions[i + 1][1].start() if i + 1 < len(motions) else len(seg)
        begin = motions[i - 1][1].end() if i else 0
        one = _j_motion(seg, act, m, begin, end, len(motions) == 1,
                        bid, (rcs, date, body), since)
        if one is not None:
            got = one
            if one["act"] == "failed":
                since = end
    # Killing every bill still on the table is how a chamber of the 1990s
    # and 2000s ended the ones it had tabled: "Reps. O'Neil and Craig move
    # ITL all bills on table, MA, VV" (HB 646 of 2006) -- a bill that died
    # on the table, as the Senate's Rule 3-23 does it now.
    if got and on_table and got["act"] == "killed":
        got["act"], got["rule"] = "died", ""
    return got


def _j_motion(seg, act, m, begin, end, alone, bid="", ctx=((), "", ""), since=0):
    """What one motion in a clause decided, or None: read from the clause
    between its own words and the next motion's. `since` is where the clause
    starts to be about the motion that carried, after one that failed."""
    at = m.start()
    part = seg[at:end]
    if act == "accede" and not re.search(r"refus", seg, re.I):
        return None
    # "ADOPTED VV" is how the 1990s record a resolution passing -- and, on a
    # bill, a committee's REPORT being adopted, whatever it recommended.
    # Where no row says which (_j_rows joins the one that does), it says
    # nothing about the bill.
    # Not where the clause says the bill was read a third time: "Adopted and
    # read a 3rd time MA VV 01/05/22" is the House passing HB 1650 of 2022.
    bare = (act == "passed" and not bill_prefix(bid).endswith("R") and re.match(
        r"\s*(?:[HS]\s+)?adopt", m.group(0), re.I)
        and not re.search(r"\bread\s+(?:a\s+)?(?:3rd|third)\s+time", seg, re.I))
    # "INTRODUCED AND ADOPTED" on a bill is no committee's report: in the
    # Senate of the 1990s, under a suspension of the rules, it is the bill
    # passing ("SEN DELAHUNTY SUSP RULES TO CONSIDER, MA 2/3VV; INTRODUCED AND
    # ADOPTED VV", HB 27 of 1993, signed a week later); in the House of
    # 2019, "Introduced and Adopted (without objection)" ahead of "Ought to
    # Pass : MA RC 316-40", the motion to introduce it. So it is a passage
    # that a passage of the same day replaces, tally and all (_j_settle).
    intro_adopt = (act == "passed" and not bill_prefix(bid).endswith("R") and re.match(
        r"\s*(?:[HS]\s+)?introduced\s+and\s+adopt", m.group(0), re.I))
    said = _j_outcome(part, 0)
    if said is None and alone:
        said = _j_outcome(seg, at)
    vote = _j_tally(part, 0)
    if not vote[0] and alone:
        vote = _j_tally(seg, at)
    vote, counted = _j_roll_call(ctx[0], ctx[1], ctx[2], vote, said)
    if counted is not None:
        said = counted
    elif act != "veto_vote" and vote[1] is not None:
        # A majority question, where the clerk's count is all there is: a
        # line with no outcome is decided by it ("Inexpedient to Legislate,
        # Division 14Y-10N", HB 327 of 2007), and "MA" on fewer yeas than
        # nays is the count's, as rollcall_outcomes rules for a roll call.
        if said is None or (said and vote[1] <= vote[2]):
            said = vote[1] > vote[2]
    if act == "veto_vote":
        if said is None and vote[1] is not None:
            y, n = vote[1], vote[2]
            said = y >= -(-2 * (y + n) // 3)
        if said is None:
            return None
        return {"act": "override" if said else "sustained", "vote": vote}
    if act == "died":
        rule = " ".join(w.capitalize() if w.isalpha() else w
                        for w in (m.group("rule") or m.group("rule2") or "").split())
        return {"act": "died", "vote": ("", None, None), "rule": rule,
                "adjourned": bool(re.search(r"adjourn", seg, re.I))}
    # No code at all, on a line of the 1990s, is the clerk recording what was
    # done: "SENATE CONC WITH HOUSE AM", "LAID ON THE TABLE", "RE-REFERRED TO
    # HEALTH". Not where a member only MOVED it: "REP MUSLER MOVED CONC WITH
    # SEN AM; LAID ON THE TABLE" (HB 119 of 1993) concurred two days later.
    moved = re.search(r"\bmov(?:ed|es?)\b|\bmotion\b", seg[begin:end], re.I)
    if (said is None and not moved
            and (act in ("concur", "nonconcur") or J_DONE_VERB.search(seg[begin:end]))):
        said = True
    # "Sen. Gannon Moved Laid on Table, 05/07/2026", and nothing after it
    # in the Senate: the clerk wrote the motion and not the vote. Kept only
    # where it is the chamber's last word (journey() drops it otherwise);
    # both such bills in the record, HB 1217 and HB 1544 of 2026, are on
    # the table by the General Court's own status.
    if said is None and moved and act == "tabled":
        return {"act": "tabled", "vote": ("", None, None), "unanswered": True}
    if said is None and not (act == "conference"
                             and re.search(r"\bnot\s+accepted\b", seg[at:end], re.I)):
        return None
    out = {"vote": vote}
    # MORE YEAS THAN NAYS, AND IT FAILED: it needed more than a majority, and
    # the clerk says how much -- "MF RC 184-157 Lacking Necessary
    # Three-Fifths Vote" (CACR 4 of 2026). "Failed to pass, 184–157" read as
    # 184 voting it down; the line says what it fell short of.
    frac = re.search(r"\b(?:two[\s-]*thirds?|2\s*/\s*3)|\b(?:three[\s-]*fifths?|3\s*/\s*5)",
                     seg, re.I)
    if not said and frac and vote[1] is not None and vote[1] > vote[2]:
        out["short_of"] = ("three fifths" if re.search(r"fifth|5", frac.group(0), re.I)
                           else "two thirds")
    if bare:
        # Its committee's report adopted: journey() reads what the report
        # recommended. HB 33 of 2007, "Adopted VV", passed the House.
        if not said:
            return None
        out["act"] = "report_adopted"
        return out
    if act == "conference":
        if re.search(r"\btable\b", part, re.I):
            return None
        # A REPORT THE CHAMBER DID NOT ACCEPT, with no vote: "Conference
        # Committee Report Not Accepted by House pursuant to House Rule 49(j)"
        # (SB 305 of 2016). The line says that much and no more -- nobody
        # voted it down.
        if re.search(r"\bnot\s+accepted\b", part, re.I):
            return {"act": "conf_rejected", "vote": ("", None, None), "unaccepted": True}
        # A motion NOT to adopt, carried, is the report rejected: "Sen.
        # Pignatelli Moved Non Adopt Conference Committee Report RC 17Y-7N,
        # Non Adopt" (SB 69 of 2001) read as the Senate adopting it 17-7.
        # So is "REFUSED TO ADOPT CONF COMM REPT, REQ NEW CONF COMM REPORT,
        # SEN HEATH MA VV" (HB 352 of 1991).
        if re.search(r"\bnon[-\s]?adopt|\bnot\s+(?:to\s+)?adopt(?!ed)|\bmov\w*\s+(?:to\s+)?reject"
                     r"|\brefus\w*\s+to\s+adopt", seg[:end], re.I):
            # Unless nobody moved it and the words are the outcome, after a
            # count that lost: "Conference Committee Report RC 11Y-13N, Non
            # Adopt" (SB 95 of 2001) is the report voted down, 11-13.
            if not said and re.search(r"\bmov\w*|\bmotion\b|\brefus", seg[:end], re.I):
                return None
            out["act"] = "conf_rejected"
            return out
        out["act"] = "conf_adopted" if said else "conf_rejected"
    elif act == "accede":
        if not said:
            return None
        out["act"] = "conf_refused"
    elif act == "nonconcur":
        if not said:
            return None
        out["act"] = "nonconcurred"
        out["conf"] = bool(re.search(r"\bc\s?of\s?c\b|cofc|conf(?:erence)?\b|"
                                     r"\breq\w*", seg[at:], re.I))
    elif act == "concur":
        # A motion to concur that failed is a refusal (HB 1215 of 2024,
        # 172-180), which is what concurrence_outcome reads it as too.
        out["act"] = "concurred" if said else "nonconcurred"
    elif act == "passed":
        if not said:
            out["act"] = "failed"
        else:
            out["act"] = "passed"
            if intro_adopt:
                out["intro_adopt"] = True
            # Not the words of a motion before it that failed: "Ought to Pass
            # W/Amendment, {1683}, RC 6Y-16N, AF, Ought to Pass, MA, VV,
            # OT3rdg, RC 22Y-1N, MA" (HB 546 of 1999) is the bill passing
            # without the amendment, and read "Passed with an amendment".
            out["amended"] = bool(J_AMENDED.search(seg[since:end])
                                  or J_AMEND_ADOPTED.search(seg))
            # "Passed by Third Reading Resolution" (HB 118 of 2005, the day
            # after "Ought to Pass, RC 16Y-8N, MA") is the passage it names,
            # read a third time, and not a second one.
            out["third"] = bool(J_THIRD.search(seg)) and not re.search(
                r"ought\s+to\s+pass|\bOTP", seg, re.I)
            to = J_REFERRED_TO.search(part)
            if to:
                out["act"] = "referred"
                out["to"] = to.group("c").strip()
    elif not said:
        return None
    else:
        out["act"] = act
    return out


def _j_second_committee(name):
    """The committee a chamber sent a bill on to after approving it: the
    money committees by their full names, any other by its own, written out
    the way the rest of the site writes a committee."""
    name = (name or "").strip(" ,.")
    for rx, full in J_SECOND_COMMITTEE:
        if rx.search(name):
            return full
    # "SUSP RULES TO REF TO 2ND COMM": the docket does not say which.
    if re.match(r"(?:a\s+)?(?:2nd|second)\s+comm", name, re.I):
        return "a second committee"
    if not re.search(r"[A-Za-z]{3}", name):
        return ""
    try:
        import referrals
        return referrals.AMP.sub(" and ", names.committee(
            referrals.expand(referrals.clean(name)))) or name
    except Exception:                                       # pragma: no cover
        return name


def _j_vote_words(vote):
    """(" on a voice vote" | ", 217–156" | "", "voice vote" | "217–156" | "")."""
    kind, y, n = vote or ("", None, None)
    if y is not None:
        return f", {y}–{n}", f"{y}–{n}"
    if kind == "VV":
        return " on a voice vote", "voice vote"
    if kind == "RC":
        return " on a roll call", "roll call"
    return "", ""


def _j_words(st, bid):
    """The line's words, and the rail's one or two."""
    act, body = st["act"], st["body"]
    other = {"H": "Senate", "S": "House"}.get(body, "")
    long_, short = _j_vote_words(st.get("vote"))
    if st.get("consent") and (long_.startswith(",") or not long_):
        long_ = " on the consent calendar" + long_
    pre = bill_prefix(bid)
    # A bill of intent is one chamber's and is no resolution: its docket's
    # word is PASSED.
    resolution = ((pre in SINGLE_CHAMBER and pre != BILL_OF_INTENT)
                  or (pre in NO_GOVERNOR and pre != "CACR"))
    if act in ("passed", "adopted"):
        am = st.get("amended")
        text = ("Adopted" if resolution else "Passed") + (" with an amendment" if am else "")
        return text + long_, ", ".join(x for x in (short, "amended" if am else "") if x)
    if act == "referred":
        to = _j_second_committee(st.get("to"))
        money = to in {full for _rx, full in J_SECOND_COMMITTEE}
        return (("Approved with an amendment" if st.get("amended") else "Approved")
                + f" and sent to {to or 'another committee'}" + long_,
                f"to {to}" if money else "to committee")
    if act == "died":
        # The docket's words, not the status chip's: the rule killed it.
        rule = st.get("rule") or ""
        if not rule:
            return "Killed with the other bills left on the table" + long_, "killed"
        if rule.lower().startswith("rule"):
            return f"Died on the table under {rule}", "died on table"
        return (f"Killed under {rule}"
                + (", still on the table" if rule == "Senate Rule 3-23" else "")
                + (" at adjournment" if st.get("adjourned") else ""), "killed")
    words = {
        "failed": ("Not adopted" if resolution else "Failed to pass", "failed"),
        "killed": ("Killed", "killed"),
        "study": ("Sent to interim study", "interim study"),
        "postponed": ("Indefinitely postponed", "postponed"),
        "tabled": ("Laid on the table", "tabled"),
        "recommitted": ("Sent back to committee", "sent back"),
        "concurred": (f"Agreed to the {other}'s amendment", "agreed"),
        "nonconcurred": (f"Refused the {other}'s amendment"
                         + (" and asked for a committee of conference"
                            if st.get("conf") else ""), "refused amendment"),
        "conf_adopted": ("Adopted the conference report", "conference report"),
        "conf_rejected": (("Did not accept the conference report", "report not accepted")
                          if st.get("unaccepted")
                          else ("Rejected the conference report", "report rejected")),
        "conf_refused": ("Refused a committee of conference", "refused conference"),
        "override": ("Veto overridden", "overridden"),
        "sustained": ("Veto sustained", "sustained"),
    }
    text, word = words.get(act, (act, act))
    # A VOTE TO OVERRIDE IS COUNTED FOR THE OVERRIDE. "Veto Sustained
    # 12/17/2025: RC 176-175 Lacking Necessary Two-Thirds Vote" (HB 358 of
    # 2025) is 176 members voting to override, and "Veto sustained, 176–175"
    # read as 176 voting to sustain.
    kind, y, n = st.get("vote") or ("", None, None)
    if act == "sustained" and y is not None:
        long_ = f", {y}–{n} to override" + (", short of two thirds" if y > n else "")
    elif st.get("short_of"):
        long_ += f", short of {st['short_of']}"
    return text + long_, (f"{word}, {short}" if short and short != "voice vote"
                          and act in ("killed", "failed") else word)


def _j_effective(*lines):
    """The one date a law took effect, or "" where its lines give none or
    several. `lines` are the governor's row, the rows that carry it on, and
    the chapter's line: all of them are read, and any sign of a second date
    -- a section, a remainder, "as provided", a starred date -- is enough to
    state none."""
    lines = [x for x in lines if x]
    if any(J_EFF_SEVERAL.search(x) for x in lines):
        return ""
    # Each line's dates after its own "eff": HB 1256 of 2026's "Law Without
    # Signature 06/05/2026; Chapter 128; eff.Enacted in accordance with
    # Article 44" states no effective date at all.
    #
    # OR THE DAY STRAIGHT AFTER THE CHAPTER, where the line has no "eff":
    # "Signed by Governor Ayotte 06/02/2025; Chapter 59; 08/01/2025" (HB 227
    # of 2025, and HB 2, HB 153 and HB 230), which the database's
    # EffectiveDate agrees with on all four.
    days = {_j_iso(*d.groups()) for x in lines
            for m in [J_EFF_ANY.search(x) or J_CHAPTER_THEN_DAY.search(x)] if m
            for d in J_DAY.finditer(x, m.start())} - {""}
    return days.pop() if len(days) == 1 else ""


# The day straight after the chapter, where the line has no "eff" word: the
# row ends there, or a journal's citation follows.
J_CHAPTER_THEN_DAY = re.compile(r"\bchapter\s*\d+\s*;\s*(?=\d{1,2}/\d{1,2}/\d{2,4}\s*"
                                r"(?:$|\s+[HS][JC]\b))", re.I)

# A LAW WITH MORE THAN ONE EFFECTIVE DATE, PART BY PART (the audit of 7
# October 2026, cause 12). "eff. I. Sec 3 eff 01/01/2032 II. Rem eff
# 09/01/2026" (HB 1300 of 2026), or the Senate's rows of their own, "I.
# Section 24 Effective 07/01/2031" and "II. Remainder Effective 07/01/2026"
# (SB 56): 92 of the term's 649 laws stated no date at all, because a law in
# effect on several dates had no one date to state. Each part is read only
# where it names what it covers and gives one date, or the section that
# provides its date; anything else -- "I Sec 1-3-5", "Sec I", a line the
# docket cut short, "eff.06/05/20256" -- states none, as before. The reason
# for the old rule stands: no date is stated that the line does not give for
# that part.
J_EFF_PART = re.compile(r"(?:(?<=[\s.;,])|^)(?:I{1,3}|IV|VI{0,3})\s*\.?\s*"
                        r"(?=(?:Secs?|Sections?|Rem\w*|RSA)\b)", re.I)
J_EFF_PROVIDED = re.compile(r"\bas\s+(?:prov(?:ided)?\.?\s+(?:in\s+)?|in\s+)?"
                            r"sec(?:tion)?s?\.?\s*(\d+)\b"
                            r"|\beff\.?\s+prov(?:ided)?\.?\s+(?:in\s+)?sec(?:tion)?\.?\s*(\d+)",
                            re.I)
J_EFF_WHAT = re.compile(r"^\s*(?P<what>(?:Secs?|Sections?)\.?\s*(?P<nums>[\dI][\d\s,&+.\-and]*?)"
                        r"|Rem\w*\.?|RSA\s+.+?)\s*(?:of\s+this\s+act\s+)?"
                        r"(?=\beff|\bshall\b|\bas\s|\d{1,2}/|$)", re.I)


def _j_sections(s):
    """"1.2.5.6" -> "sections 1, 2, 5 and 6", "5-8" -> "sections 5 to 8",
    "3" -> "section 3"; "" where it is not plainly a list of numbers."""
    s = re.sub(r"\band\b", "&", s, flags=re.I).strip(" .")
    if re.fullmatch(r"\d+\s*-\s*\d+", s):
        a, b = re.split(r"\s*-\s*", s)
        return f"sections {a} to {b}"
    nums = [p for p in re.split(r"\s*[&+,.]\s*|\s+", s) if p]
    if not nums or not all(re.fullmatch(r"\d+(?:-\d+)?", p) for p in nums):
        return ""
    if len(nums) == 1 and "-" not in nums[0]:
        return f"section {nums[0]}"
    nums = [p.replace("-", " to ") for p in nums]
    return "sections " + (", ".join(nums[:-1]) + " and " + nums[-1] if len(nums) > 1
                          else nums[0])


def _j_effective_parts(*lines):
    """A law in effect on several dates, part by part: "section 3 on 1 Jan
    2032, the rest on 1 Sep 2026", or "" where any part does not say plainly
    what it covers and when. `lines` are the governor's row, the rows that
    carry it on and the chapter's line, each distinct line read once."""
    tails = []
    for x in dict.fromkeys(x.strip() for x in lines if x and x.strip()):
        m = re.search(r"\bchapter\s*\d+\s*[;,.]?", x, re.I)
        tails.append(x[m.end():] if m else x)
    pieces = J_EFF_PART.split(" ".join(tails))
    if len(pieces) < 3:
        return ""
    out = []
    for p in pieces[1:]:
        p = re.sub(r"\s+(?:HJ|SJ|HC|SC)\s*\d+.*$", "", p).strip()
        s = J_EFF_WHAT.match(p)
        if not s:
            return ""
        what = s.group("what")
        if re.match(r"rem", what, re.I):
            label = "the rest"
        elif re.match(r"RSA", what, re.I):
            label = re.sub(r"\s+", " ", what).strip(" .")
        else:
            label = _j_sections(s.group("nums") or "")
            if not label:
                return ""
        rest = p[s.end():]
        days = [d for d in (_j_iso(*x.groups()) for x in J_DAY.finditer(rest)) if d]
        prov = J_EFF_PROVIDED.search(rest)
        if len(days) == 1 and not prov:
            out.append((label, "on " + _j_prose_date(days[0])))
        elif not days and prov:
            out.append((label, "as section " + (prov.group(1) or prov.group(2))
                        + " provides"))
        else:
            return ""
    out = list(dict.fromkeys(out))
    if len({w for w, _ in out}) != len(out):
        return ""
    out.sort(key=lambda x: x[0] == "the rest")
    return ", ".join(f"{w} {d}" for w, d in out)


def _j_days(a, b):
    """Days from ISO date b to ISO date a; 0 where either is missing."""
    try:
        return (_date.fromisoformat(a) - _date.fromisoformat(b)).days
    except (TypeError, ValueError):
        return 0


def _j_in_term(day, term):
    """Whether an ISO day can be a day of the term "2019-2020": from the
    December before its first year, when the House organises and the first
    bills are introduced, to the end of its second. True where either is
    missing.

    A day outside it is the clerk's year, not the bill's: "Introduced
    01/02/2014" on HB 214 of 2019-2020, "Adjournment 09/16/2021" on HB 201
    of the same term, a term that ended in December 2020."""
    m = re.match(r"(\d{4})-(\d{4})$", term or "")
    if not m or not day:
        return True
    return f"{int(m.group(1)) - 1}-11-01" <= day <= f"{m.group(2)}-12-31"


def _j_year_slip(said, day, term):
    """The day a row means where the one it states has the clerk's year:
    the same month and day in the year of the row's own date, where that is
    in the term and is the row's day or up to 60 days before it -- or "".

    "Introduction and referring to Judiciary 1/28/98" was entered at 10:14
    on 28 January 1999, the day the Senate sat (SB 66 of 1999); "Introduced
    and Adopted, VV; 02/09/2016" on SR 8 of 2017 cites Senate Journal 5, of
    9 February 2017; "Introduced and Adopted VV 01/06/2020" on HR 6 of 2021
    cites House Journal 2, of 6 January 2021. A month and a day are the
    clerk's; the year the row was entered in says which one."""
    try:
        got = _date(int(day[:4]), int(said[5:7]), int(said[8:10])).isoformat()
    except (TypeError, ValueError):
        return ""
    return got if _j_in_term(got, term) and 0 <= _j_days(day, got) <= 60 else ""


def _j_stated_day(text):
    """The first date a line states, "2007-06-11", or ""."""
    got = []
    for m in J_DAY.finditer(text or ""):
        iso = _j_iso(*m.groups())
        if iso:
            got.append((m.start(), iso))
            break
    m = J_MONTH_DAY.search(text or "")
    if m:
        try:
            got.append((m.start(), _date(int(m.group(3)), J_MON.index(m.group(1)[:3].title()) + 1,
                                         int(m.group(2))).isoformat()))
        except ValueError:
            pass
    return min(got)[1] if got else ""


def _j_gov_more(evs, gov):
    """The rows that carry a governor's row on -- "II. Remainder Eff.
    08/12/2007" -- in the order they follow it."""
    try:
        i = next(k for k, x in enumerate(evs) if x is gov)
    except StopIteration:
        return []
    out = []
    for x in evs[i + 1:i + 8]:
        if x.get("type") not in ("other", "governor") or not J_EFF_MORE.match(x.get("raw") or ""):
            break
        out.append(x.get("raw") or "")
    return out


def _j_introduced(evs, bid, term=""):
    """The day the bill was introduced in the chamber it started in: the
    day its introduction row states where it states one ("Introduced pursuant
    to Rule 36c 02/20/2025", HR 17 of 2025, entered on the 25th), else the
    day of the row.

    A ROW THAT STATES A DAY OUTSIDE THE TERM STATES THE CLERK'S YEAR.
    "Introduction and referring ... 1/28/98" on SB 53 of 1999, "Introduced
    and Adopted, VV; 02/09/2016" on SR 8 of 2017 and "Introduced 01/02/2014"
    on HB 214 of 2019 had the rail say each was introduced a year or five
    before its term began. The month and day are taken in the year of the
    row's own date where that is in the term and not after the row
    (_j_year_slip) -- 28 January 1999, 9 February 2017, 2 January 2019, each
    the day of the Journal the row cites -- and otherwise the stop goes
    undated rather than take either.

    IN ITS OWN CHAMBER. A bill is introduced twice, once in each chamber, and
    the first row typed as an introduction is not always the first chamber's:
    SCR 1 of 2023's Senate row, "Sen. Birdsell Moved Introduction; 2/3
    necessary, MA, VV; 02/09/2023", is typed as a floor decision, and the
    House's introduction of 16 March was taken for the resolution's."""
    rows = [e for e in evs
            if e.get("type") == "introduced" or J_INTRO_ROW.search(e.get("raw") or "")]
    pre = bill_prefix(bid)
    # The chamber the number names, a special session's "SSHB" included: SSHB
    # 1 of 2013 was read as a Senate bill by its first letter, and its rail's
    # Introduced stop took 21 November, the day the Senate introduced it, a
    # fortnight after "Introduced: MA RC 183-141 and Referred to Finance" in
    # the House on the 7th.
    # Only where that chamber has an introduction row: SSHB 1 of 2010's House
    # rows begin at "Ought to Pass", and its stop keeps the Senate's row of
    # the same day, 9 June, the one day that session sat.
    named = pre[2:] if pre.startswith("SS") and len(pre) > 3 else pre
    if named != pre and any((e.get("body") or "")[:1].upper() == named[:1] for e in rows):
        pre = named
    own = "S" if pre.startswith("S") else "H" if pre.startswith("H") else ""
    # Where the first chamber's own row is missing, no date: SB 109 of 2009
    # has only the House's "Introduced and Referred to Transportation", a
    # fortnight after the Senate passed it.
    if own:
        rows = [e for e in rows if (e.get("body") or "")[:1].upper() == own]
    days = []
    for e in rows:
        d = e.get("date") or ""
        said = _j_stated_day(e.get("raw") or "")
        if said and not e.get("date_as_recorded") and (not d or said <= d):
            d = said if _j_in_term(said, term) else _j_year_slip(said, d, term)
        if d and _j_in_term(d, term):
            days.append(d)
    return min(days) if days else ""


# What a committee report recommended, as the decision its adoption was.
J_FROM_REPORT = [(re.compile(r"inexpedient|ought\s+not\s+to\s+pass", re.I), "killed"),
                 (re.compile(r"interim\s+study", re.I), "study"),
                 (re.compile(r"indefinitely\s+postpone", re.I), "postponed"),
                 (re.compile(r"ought\s+to\s+(?:pass|adopt)", re.I), "passed"),
                 (re.compile(r"re-?\s?refer|recommit", re.I), "recommitted")]
J_WRAPPED_TALLY = re.compile(r"\(\s*\d+\s*-?\s*$")
J_TALLY_TAIL = re.compile(r"^\s*-?\s*\d+\s*\)")
J_FILED = re.compile(r"\bfiled\b", re.I)
J_CONF = dict(J_ACTS)["conference"]
J_VETO_VOTE = dict(J_ACTS)["veto_vote"]
# Past tense: "Shall HB 455-FN Become Law" is the question the vote is on.
J_CHAPTERED = re.compile(J_EFF_ANY.pattern + r"|\bchap(?:ter)?\b|\bbecame\s+law\b", re.I)


def _j_unfile(raw):
    """A docket row without a conference report's filing in it: "" where
    that is all the row records.

    A REPORT FILED IS NOT A VOTE ON IT, and the words that describe the
    version it proposes read as one. "Conference Committee Report #2084, As
    Passed by the Senate: Filed" (SB 32 of 2008) was the House passing the
    bill, days before it voted the report down; "Conference Committee Report
    #2021-1946c Filed 06/10/2021; Version Adopted by Senate" (SB 103 of 2021)
    was the House adopting the report eight days before it did; "Conference
    Committee Report; Concur with Senate Am { 1729}; Filed" (HB 215 of 2001)
    was the Senate agreeing to an amendment of its own. So everything up to
    "Filed" goes, and the clause after it when it carries no vote -- "As
    Passed by the Senate", "House Amendment + New Amendment". A vote the
    clerk put in the same row stays: "CONF COMM REPORT (S AM + NEW AM)
    FILED; CONF COMM REPORT ADOPTED RC(19-3)" (HB 25 of 1991)."""
    m = J_FILED.search(raw or "")
    if not m or not J_CONF.search(raw[:m.end()]):
        return raw
    rest = [p.strip() for p in raw[m.end():].split(";")][1:]
    if rest and not (J_YES_CODE.search(rest[0]) or J_NO_CODE.search(rest[0])
                     or J_TALLY.search(rest[0]) or J_VOICE.search(rest[0])
                     or J_RC_BARE.search(rest[0])):
        rest = rest[1:]
    return "; ".join(p for p in rest if p)


def _j_rows(evs):
    """[(event, text)]: the docket rows a decision can be read from, with a
    row the clerk wrapped joined to the row it runs on into.

    "REP MCCANN MOVED OTP, ML RC(107-198); REP HOLDEN MOVED ITL, ITL" and
    then "REPORT ADOPTED VV; HJ37,P1295" (CACR 21 of 1996) are one motion
    and its outcome; so are "...ADOPTION ML RC(95-" and "235); HJ83,P2147"
    (SCR 13 of 1992). Read apart, the first is nothing and the second, in
    "REP B. HALL SUBST REF FOR STUDY, ML DIV(99-196); ITL REPORT" / "ADOPTED
    VV" (HB 265 of 1992), a resolution adopted.

    THE FLOOR'S WORDS CAN SIT IN A ROW TYPED AS A REPORT. "MAJ REPT OTP, ML
    DIV(114-223); REP MCGUIRK MOVED ITL, ITL REPORT" is a report row of SB 217
    of 1997, and its "ADOPTED VV" is the House's floor row of the same day --
    in whichever order the two were entered.

    A LINE TOLD QUESTION BY QUESTION IS STILL ONE LINE HERE. The 1999-2006
    reader gives a House floor day an event for each question it decided
    (docket_vocab.questions), each with its own clause as `raw`. Those are
    whole clauses, not a row wrapped onto the next, and read as rows they are
    joined back wrongly: SB 135 of 1999's "Re-Referred to Res, Rec & Dev
    committee RC(158-154)" and "Rep Royce moved to reconsider, ML
    RC(156-157)" became a re-referral that failed, and left the rail. The
    line is read whole, once, from the event that carries it (docket_line),
    which is what this was written for."""
    evs = [e for e in evs if not e.get("in_line")]
    tails = defaultdict(list)
    voted = set()
    for e in evs:
        if e.get("type") != "report":
            continue
        raw = docket_line(e)
        segs = _j_segments(raw)
        if (segs and re.search(r"\bM[AFL]\b|\bmoved\b|\bsubst", raw, re.I)
                and _j_act(segs[-1]) and not _j_has_outcome(segs[-1])):
            tails[(e.get("body"), e.get("date"))].append(raw)
        # A report row that is itself the floor's vote on the report, whole:
        # "Minority Committee Report: Ought to Pass with AM #0625h NT: MA RC
        # 193-141" (HB 1623 of 2008) is the House passing the bill; "COMM
        # REPORT ITL, ML VV; RE-REFERRED TO MUN & CNTY GOVT, REP BEHRENS MA
        # VV" (HB 475 of 1995) is it sending the bill back. Not the Senate's
        # "Committee Report; Ought to Pass with Amendment{0400s} (New
        # Title), MA, VV" (SB 165 of 2009), the committee's own report,
        # whose floor vote is a row of its own a fortnight later.
        elif ((J_YES_CODE.search(raw) or J_NO_CODE.search(raw))
              and not re.match(r"\s*committee\s+report\s*;", raw, re.I)):
            voted.add(id(e))
    out = []
    for e in evs:
        if e.get("type") in J_NOT_FLOOR and id(e) not in voted:
            continue
        raw = _j_unfile(docket_line(e))
        first = (_j_segments(raw) or [""])[0]
        tail = tails.get((e.get("body"), e.get("date")))
        if tail and J_OUTCOME_ONLY.match(first):
            out.append((e, f"{tail.pop(0).rstrip()} {raw.lstrip()}"))
            continue
        if out and raw.strip():
            pe, prev = out[-1]
            same = ((pe.get("body"), pe.get("date")) == (e.get("body"), e.get("date")))
            segs_p, segs_n = _j_segments(prev), _j_segments(raw)
            last = segs_p[-1] if segs_p else ""
            first = segs_n[0] if segs_n else ""
            tally = J_WRAPPED_TALLY.search(prev) and J_TALLY_TAIL.match(raw)
            # A motion wrapped mid-phrase: "...; NEW CONF COMM" and "REPORT
            # ADOPTED VV" (HB 1399 of 1992), "...; GOVERNOR'S VETO" and
            # "SUSTAINED RC(221-117)" (HB 332 of 1995) -- neither half names
            # a motion, and the two together do.
            wrapped = (last and not _j_has_outcome(last) and first and _j_has_outcome(first)
                       and not _j_act(first) and _j_act(f"{last} {first}"))
            # And a suspension of the rules the clerk ran onto the next row:
            # "REPS KURK & PFAFF SUSP" and "RULES FOR 3RD READING, MA 2/3VV".
            # Read alone, the second half is the bill passing.
            # Where the next row starts a motion of its own, it is not the
            # rest of this one, unless this one broke off at "SUSP".
            tail_p = prev.split(";")[-1]
            sm = J_SUSPEND.search(tail_p)
            open_susp = bool(sm) and not (J_SUSP_CODE.search(tail_p, sm.end())
                                          or J_SUSP_WORD.search(tail_p, sm.end())) and (
                bool(re.search(r"\bsusp\w*\.?\s*$", tail_p, re.I))
                or not _j_act(raw.split(";")[0]))
            if same and (tally or wrapped or open_susp
                         or (last and _j_act(last) and not _j_has_outcome(last)
                             and first and _j_has_outcome(first)
                             and (J_OUTCOME_ONLY.match(first) or not _j_act(first)))):
                out[-1] = (pe, prev.rstrip() + ("" if tally else " ") + raw.lstrip())
                continue
        out.append((e, raw))
    return out


def _j_row_day(e, raw):
    """The day a row states at its end ("; 03/27/2025"), else its event's.
    A row no pattern reads is dated by its entry: SB 86 of 2025's "Pending
    Motion OT3rdg; 03/27/2025" was entered on 4 June."""
    m = J_ROW_DAY.search(raw or "")
    return (_j_iso(*m.groups()) if m else "") or (e.get("date") or "")


def _j_untold(e, seg, evs):
    """Whether the history tells nothing of the clause a decision was read
    from: the row is one no pattern reads (type "other"), or it is a line
    told question by question (docket_vocab.questions) and this question is
    the one left untold -- "OTP/AM failed 3/5 RC(186-172)", the last clause
    of CACR 2 of 2004's floor line, whose event carries the clause alone."""
    if e.get("type") == "other":
        return True
    if not e.get("line"):
        return False
    want = re.sub(r"\s+", " ", seg or "").strip()
    for o in evs:
        if not (o.get("in_line") and o.get("type") == "other"
                and (o.get("body"), o.get("date")) == (e.get("body"), e.get("date"))):
            continue
        clause = re.sub(r"\s+", " ", o.get("raw") or "").strip()
        if clause and want and (clause in want or want in clause):
            return True
    return False


def journey(narr, bid, rcs=(), chapter="", law_line="", term="", db_effective="",
            untold=None):
    """(the date it was introduced, [one dict a decision]) -- from the docket.

    Each decision carries its date, its body (H, S, the Governor G, the Law L
    or the Voters V), what it was (`act`), the glyph it is drawn with
    (`mark`: p, x or h), its words for On the record (`text`) and for the
    rail (`short`). `term`, "2019-2020", bounds the days it will state.

    `untold`, a set the caller passes, is filled with the id() of each line
    read from a docket row narrative.py tells nothing of (its type "other"):
    a decision the bill's history does not narrate (closing_stage).
    """
    evs = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
    intro = _j_introduced(evs, bid, term)
    # The day the conferees reported that they could not agree, where that is
    # the last word of the bill's conferences: a report adopted from that day
    # on is that report, and the line says what it said. Only a REPORT of no
    # agreement: where the record says none was signed, a chamber adopted no
    # report of that conference, and none of its lines is rewritten.
    failed = conference_failure(evs)
    unable_day = (max((e.get("date") or "" for e in evs
                       if CONF_UNABLE_RE.search(e.get("raw") or "")), default="")
                  if failed and failed[0] == "unable" else None)
    steps, amended = [], set()
    gov_raw, gov_more = "", []
    reports = [e for e in evs if e.get("type") == "report"]
    # A second committee's chair can waive the referral, and the bill then
    # goes on as the chamber passed it: HB 243 of 2025, "Ought to Pass: MA
    # VV", "Referred to Criminal Justice and Public Safety", "Referral Waived
    # by Committee Chair per House Rule 47(f)", all on 20 February, and in
    # the Senate a fortnight later. The waiver can be entered ahead of the
    # referral it waives (SB 482 of 2026), or days after it.
    waived = {((e.get("body") or "")[:1].upper(), e.get("date") or "")
              for e in evs if J_WAIVED.search(e.get("raw") or "")}
    divided = {((e.get("body") or "")[:1].upper(), e.get("date") or "")
               for e in evs if J_DIVIDED_OUT.search(e.get("raw") or "")
               and any(re.sub(r"\s+", "", m.group(0)).upper() == bid
                       for m in J_OTHER_BILL.finditer(e.get("raw") or ""))}
    # What a reconsideration naming nothing is of (_j_reconsidered): a vote
    # the chamber took since its last decision, on any day; and, on the day
    # of the reconsideration, a motion it took up with no vote written beside
    # it or a suspension of the rules it refused.
    pending, voted, moved = {}, set(), {}
    # A MOTION TO PASS ADOPTED AND THEN TABLED BEFORE THE STEP THAT PASSES THE
    # BILL (narrative.passage_left_pending, the one reading the history and
    # the sitting pages ask too). The Senate passes a bill by ordering it to a
    # third reading -- "Ought to Pass: MA, VV; OT3rdg" -- or under its Rule 4-5
    # sends it to Finance first; SB 131 of 2025 has "Ought to Pass: MA, VV",
    # "Sen. Gray Moved Laid on Table, MA, VV" and "Pending Motion OT3rdg", all
    # of 27 March (Senate Journal 9: the motion "Adopted." and the tabling, and
    # no "bill ordered to Third Reading"), and died under Rule 3-23. Its rail
    # read "Passed on a voice vote". The line is kept while the rows are read,
    # so that a removal from the table, a reconsideration and the order to a
    # third reading that carries it later each find what they would have, and
    # is left out after, unless that order came.
    unpassed = N.passage_left_pending(
        [((e.get("body") or "").upper()[:1], _j_row_day(e, raw), raw) for e, raw in _j_rows(evs)])
    for e, raw in _j_rows(evs):
        body = (e.get("body") or "").upper()[:1]
        # THE JOURNAL A ROW CITES NAMES THE CHAMBER THAT ACTED. "PASSED VV;
        # SJ12,P305 + 318" is filed under the House on HB 1113 of 1994 and
        # is the Senate passing it; "Sen. Francoeur Moved Laid On Table, MA,
        # VV" sits under the House on HB 1249 of 2002 with the Senate
        # Journal's page. Read by the filing, the House passed those bills
        # twice and the Senate never did.
        # BUT A CITATION CAN BE THE TYPO, and then the filing is right. Which
        # it is, the chamber that held the bill says -- the one whose
        # introduction or committee report came last before the row: HB 366
        # of 1995's "ITL REPORT ADOPTED; SJ25,P532" is the House killing a
        # bill the Senate never received, and HB 426 of 1993's "PASSED VV;
        # HJ46,P217 + 221", filed under the Senate the day of the Senate
        # committee's report, is the Senate passing it.
        cite = (e.get("cite") or "").upper()
        if cite[:2] in ("HJ", "SJ") and body in ("H", "S") and cite[0] != body:
            before = evs[:next((k for k, x in enumerate(evs) if x is e), len(evs))]
            held = next(((x.get("body") or "")[:1].upper() for x in reversed(before)
                         if x.get("type") in ("introduced", "report")
                         or J_INTRO_ROW.search(x.get("raw") or "")), "")
            # Or the row says whose it is: "SEN CONC WITH HOUSE AM, SEN DANAIS
            # MA VV; SJ10,P117" (SB 157 of 1995) is the Senate concurring,
            # back from the House with no new introduction.
            who = ("S" if re.match(r"\s*(?:sen(?:ator)?s?\b\.?|senate\b)", raw, re.I)
                   else "H" if re.match(r"\s*(?:reps?\b\.?|house\b)", raw, re.I) else "")
            if held == cite[0] or who == cite[0] or J_INTRO_ROW.search(raw):
                body = cite[0]
        date = e.get("date") or ""
        # THE CHAPTER, NOT A THIRD VOTE ON THE VETO. Once both chambers have
        # overridden, the clerk records the law: "Veto Overriden 05/30/2019:
        # Eff: 05/30/2019; Chapter 42" (HB 455 of 2019, filed under the House
        # a week after the House's own 247-123), "VETO OVERRIDDEN (BECAME LAW
        # WITHOUT SIGNATURE) 09/15/93" (HB 25 of 1993). Read as a vote, the
        # House overrode twice. An override is a roll call; a row naming one
        # with no vote at all and a chapter, an effective date or the bill
        # becoming law is the Law line's, which says it already.
        if (J_VETO_VOTE.search(raw) and J_CHAPTERED.search(raw)
                and not any(rx.search(raw) for rx in (J_YES_CODE, J_NO_CODE, J_TALLY,
                                                      J_VOICE, J_RC_BARE))):
            continue
        # A vote to suspend the rules that failed, ahead of any
        # reconsideration in the row, or after it once the row is read. That
        # day only: HB 462 of 1989 was sent back to committee on 16 March,
        # failed to have the joint rules suspended on 13 April, and on 25
        # April had the rules suspended and reconsidered the recommittal.
        failed, rc = _j_suspension_failed(raw), J_RECONSIDER.search(raw)
        if failed >= 0 and (not rc or failed < rc.start()):
            moved[body] = date
        for seg in _j_segments(raw):
            if J_REMAINING.match(seg) and (body, date) in divided:
                continue
            if J_WAIVED.search(seg):
                last = next((s for s in reversed(steps) if s["body"] == body), None)
                if last and last["act"] == "referred":
                    last["act"] = "passed"
                    last.pop("to", None)
                continue
            # A BILL TAKEN OFF THE TABLE WAS NOT LEFT ON IT, whether the same
            # day or later: SB 315 of 2012 was passed and tabled with a batch
            # of Senate bills on 25 April, taken off on 16 May and signed in
            # June. "Remove from Table (Rep. Wherry): MF RC 151-168" (SB 222
            # of 2025) is a motion that failed, and left it there.
            off = re.search(r"\b(?:remov\w*|taken|take)\s+(?:\w+\s+){0,2}from\s+(?:the\s+)?table",
                            seg, re.I)
            if off:
                said = _j_outcome(seg, off.start())
                if said is None:
                    said = bool(re.match(r"removed|taken", off.group(0), re.I))
                # Not a line left out once the rows are read (`unpassed`):
                # HB 282 of 2025's Ought to Pass row was entered after the
                # tabling of 15 May that its removal of 26 June undid.
                mine = [i for i, s in enumerate(steps)
                        if s["body"] == body and not s.get("_unpassed")]
                if said and mine and steps[mine[-1]]["act"] == "tabled":
                    steps.pop(mine[-1])
                # And what the clause does next: "Sen D'Allesandro Moved
                # Remove From Table, MA, VV, Ought to Pass, MA, VV, OT3rdg,
                # MA, VV" (HB 501 of 1999) is the Senate passing the bill.
                o = J_SUSP_CODE.search(seg, off.end()) or J_SUSP_WORD.search(seg, off.end())
                seg = seg[J_SUSP_VOTE.match(seg, o.end()).end():] if o else ""
                if not _j_act(seg):
                    continue
            # "Ought to Pass ...: MA RC 197-149" and then, the same day,
            # "Referred to Finance" -- or "...MA, VV; Refer to Finance Rule
            # 4-5" on one line: the chamber approved it and sent it to a
            # second committee, which is not the bill leaving the chamber.
            # ANY SECOND COMMITTEE, not only the money ones. HB 493 of 2025
            # was approved on 13 March and "Referred to Executive Departments
            # and Administration" the same day, which killed it 193-177 in
            # April; read as passed, the House passed a bill it never passed.
            # THE CLERKS OF 1989 WROTE THE REFERRAL WHEN THEY GOT TO IT: before
            # the passage it followed ("REFERRED TO FINANCE/APPROP" at 12:49,
            # "PASSED/ADOPTED" at 14:36, HB 115 of 1989), or days after it
            # (HB 396, passed on 21 April, "REFERRED TO APPROP/FINANCE" on the
            # 25th). A passage the chamber sent on to a second committee
            # before the other chamber did anything is that referral; one
            # waiting for its passage takes it when it comes.
            ref = J_BARE_REFERRAL.match(seg)
            to = _j_second_committee(ref.group("c")) if ref and not _j_act(seg) else ""
            if to:
                at = next((i for i in range(len(steps) - 1, -1, -1)
                           if steps[i]["body"] == body), None)
                last = steps[at] if at is not None else None
                # Not a passage the chamber has since reconsidered, which the
                # referral came after: the Senate passed HB 1331 of 1990 on
                # 29 March, reconsidered it on 3 April and sent it to Finance
                # that day, and it read "Approved and sent to Finance,
                # reconsidered on 3 Apr".
                if last and last.get("reconsidered") and date >= last["reconsidered"]:
                    continue
                if (last and last["act"] == "passed" and (body, date) not in waived
                        and 0 <= _j_days(date, last["date"]) <= 30
                        and not any(s["body"] in ("H", "S") for s in steps[at + 1:])):
                    last["act"], last["to"] = "referred", to
                elif (body, date) not in waived:
                    pending[(body, date)] = to
                continue
            _j_reconsidered(steps, body, date, seg,
                            body not in voted and moved.get(body) != date)
            # THE PENDING ORDER, CARRIED LATER WITH NO CODE: "OT3rdg;
            # 03/21/2024", the day SB 173 of 2024 came off the table, its
            # Ought to Pass of 3 January left pending by the tabling; "OT3rdg"
            # on SB 144 of 2015. The bill passed then, on the motion it had
            # adopted.
            if N.BARE_THIRD.match(raw) and (body, _j_row_day(e, raw)) not in unpassed:
                waiting = next((s for s in reversed(steps)
                                if s["body"] == body and s.get("_unpassed")), None)
                if waiting:
                    waiting["_unpassed"], waiting["date"] = False, date
                    continue
            got = _j_decide(seg, bid, rcs, date, body)
            if (got is None or got == "amended") and not J_RECONSIDER.search(seg):
                # A vote since the chamber's last decision, which a
                # reconsideration naming nothing is then about -- or a
                # motion that day with no vote written beside it: "REP
                # LARSON SUBST ITL; VOTE TAKEN, INCORRECTLY, ON COMM AM; REP D
                # HALL MOVED TO RECONSIDER, MA VV" (SB 796 of 1994) undid that
                # day's mistaken vote, not the passage of a month before.
                if _j_has_outcome(seg):
                    voted.add(body)
                elif _j_act(seg) or J_AMEND_SUBJ.search(seg):
                    moved[body] = date
            if got is None:
                continue
            if got == "amended":
                amended.add((body, date))
                # The amendment's row can carry the referral that followed
                # the passage: "Sen. Pignatelli Floor Amendment, {2150}, AA,
                # VV, Rule 24 (Refer to Finance)" (HB 707 of 1999).
                to_ = J_REFERRED_TO.search(seg)
                last = next((s for s in reversed(steps) if s["body"] == body), None)
                if (to_ and last and last["date"] == date and last["act"] == "passed"
                        and (body, date) not in waived):
                    last["act"], last["to"] = "referred", to_.group("c").strip()
                continue
            if got["act"] == "report_adopted":
                rec = next((r.get("recommendation") or "" for r in reversed(reports)
                            if (r.get("body") or "")[:1] == body
                            and (r.get("date") or "") <= date
                            and r.get("side") != "Minority" and r.get("recommendation")), "")
                act = next((a for rx, a in J_FROM_REPORT if rx.search(rec)), "")
                # No report to adopt: the rules were suspended to take the
                # bill up without one, and "ADOPTED VV" is the bill -- "REPS
                # TEAGUE & WALLNER SUSP RULES TO CONSIDER, MA 2/3VV; ADOPTED
                # VV" (HB 1503 of 1992, signed in June). Not an amendment's
                # adoption: "Adopt Remainder Floor Amendment {2421h}; AA VV".
                if not rec and not re.search(r"amend|\brep(?:ort|t)\b", seg, re.I):
                    act = "passed"
                if not act:
                    continue
                got = {**got, "act": act,
                       "amended": act == "passed" and bool(re.search(r"amend", rec, re.I))}
            st = {"date": date, "body": body, **got, "_untold": _j_untold(e, seg, evs)}
            if got["act"] == "passed" and (body, _j_row_day(e, raw)) in unpassed:
                st["_unpassed"] = True
            # A COUNT THAT IS THE CONSENT CALENDAR'S (decision 51,
            # narrative.CONSENT_VOTE): "PASSED WITH AM/CONSENT CAL RC(248-8)"
            # read "Passed with an amendment, 248-8", the calendar's roll call
            # of 7 January 1998 as the bill's own.
            if (st.get("vote") or ("", None))[1] is not None and N.CONSENT_VOTE.search(seg):
                st["consent"] = True
                # And a count the calendar's other rows do not give is no
                # count of the calendar's (narrative.calendar_count_disputed):
                # "on the consent calendar", and no count.
                if e.get("calendar_count_disputed"):
                    st["vote"] = ("", None, None)
            # Whether its own clause names the amendment, before the day's
            # amendment rows mark every passage of that day (_j_merge).
            if got["act"] in J_PASSING:
                st["_own_am"] = bool(got.get("amended"))
            # THE DAY THE CLAUSE STATES, where the row was dated by its entry:
            # "Adopted and read a 3rd time MA VV 01/05/22", entered on 10
            # January (HB 1650 of 2022) -- four days after the governor
            # signed the bill it passed. Not a sitting the chamber met "in
            # recess of", which is the day before the one it acted on.
            # A BILL KILLED BY RULE AT ADJOURNMENT DIED THE DAY IT STATES, and
            # the clerk enters those rows in a batch long after: 427 of
            # 2019-2020's read "Inexpedient to Legislate, Senate Rule 3-23,
            # Adjournment 09/16/2020" and were entered in September 2021, a
            # year after the term ended, which is the day the line and the
            # rail's Senate stop carried. So its day is taken however far
            # back, as long as it is in the term and not before the
            # chamber's last word on the bill (the tabling it died on).
            # AND THE DAY AN INTRODUCTION ROW STATES, which is the day of what
            # it did on introduction: "Introduced and Adopted, VV; 02/09/2016"
            # on SR 8 of 2017 is Senate Journal 5 of 9 February 2017, the day
            # its rail says it was introduced (_j_introduced) -- and it read
            # as adopted on the 15th, the day the row was entered, six days
            # after the one motion that did both.
            said = J_CLAUSE_DAY.search(seg) or (J_INTRO_ROW.search(seg)
                                                and J_ROW_DAY.search(raw)) or None
            if (said and got["act"] not in ("signed", "vetoed", "unsigned")
                    and not e.get("date_as_recorded")):
                day = _j_iso(*said.groups())
                # The clerk's year, as on an introduction: HR 6 of 2021's
                # "Introduced and Adopted VV 01/06/2020", entered on 7 January.
                if day and not _j_in_term(day, term):
                    day = _j_year_slip(day, date, term)
                back = _j_days(day, date) if day else 0
                if day and _j_in_term(day, term) and (-60 <= back < 0 or (
                        got["act"] == "died" and back < 0 and not any(
                            s["body"] == body and s["date"] > day for s in steps))):
                    st["date"] = day
            # AND A SITTING THE ROW WAS ENTERED AHEAD OF. The Senate's clerk
            # enters a conference report's adoption before the sitting and
            # states the sitting after it: "Conference Committee Report
            # #2024-2290c , Adopted, VV; 06/13/2024", entered on 12 June (HB
            # 1573 of 2024), is Senate Journal 17 of 13 June, and the Senate
            # did not sit on the 12th. So were 34 of this term's, dated 29 May
            # 2026 and 24 June 2025. Up to a fortnight ahead, on a weekday:
            # "OT3rdg; 03/19/2017" on SB 152 of 2017, entered on the 16th
            # when the Senate sat, states a Sunday.
            ahead = [x for x in (said, J_ROW_DAY.search(raw)) if x]
            if got["act"] not in ("signed", "vetoed", "unsigned") and not e.get("date_as_recorded"):
                for x in ahead:
                    day = _j_iso(*x.groups())
                    if (day and _j_in_term(day, term) and 0 < _j_days(day, date) <= 14
                            and _date.fromisoformat(day).weekday() < 5):
                        st["date"] = day
                        break
                if ahead:
                    st["_stated"] = _j_iso(*ahead[-1].groups())
            # A report not accepted states the sitting it was done in recess
            # of, "05/19/2016" on SB 305 of 2016, a week before the report was
            # filed, and was entered on 3 June: undated, rather than either.
            if st.get("unaccepted"):
                st["date"] = ""
            # And no day outside the term at all: HB 201 of 2020's own row
            # reads "Adjournment 09/16/2021", entered on 9 September 2021,
            # and neither is a day of 2019-2020. Undated, rather than either.
            if not _j_in_term(st["date"], term):
                st["date"] = ""
            if got["act"] in ("signed", "vetoed", "unsigned"):
                st["body"] = "G"
                gov_raw = raw
                gov_more = _j_gov_more(evs, e)
                # THE DAY THE LINE GIVES, NOT THE DAY IT WAS ENTERED. "Signed
                # by the Governor on 06/11/07" (HB 101 of 2007) was entered on
                # the 12th, and 628 governor lines were dated by their entry.
                # Not a day before the chambers finished with the bill -- "on
                # 06/14/10" on a bill of 2011 is the clerk's year -- nor far
                # from the row itself, and not where a person corrected the
                # docket's date (docket_corrections.json).
                said = _j_stated_day(J_EFF_ANY.split(raw, 1)[0])
                done = max((s["date"] for s in steps if s["body"] in ("H", "S")), default="")
                if (said and not e.get("date_as_recorded") and done <= said
                        and _j_days(said, date) <= 14):
                    st["date"] = said
                # A veto overridden is enacted "without the signature of the
                # governor" (HB 1422 of 2026, the day after both chambers
                # overrode). That is the override's result, which the Law
                # line says; the governor's act was the veto.
                if got["act"] == "unsigned" and any(s["act"] == "override" for s in steps):
                    continue
            st["_row_day"] = date
            if re.search(r"\bin\s+recess\b", raw, re.I):
                st["_recess"] = True
            voted.discard(st["body"])
            moved.pop(st["body"], None)
            if st["act"] == "passed" and (body, date) in pending:
                st["act"], st["to"] = "referred", pending.pop((body, date))
            steps.append(st)
        if failed >= 0 and rc and failed > rc.start():
            moved[body] = date
    steps = [s for s in steps if not s.pop("_unpassed", False)]
    # AN AMENDMENT ADOPTED THAT DAY AMENDS THAT DAY'S PASSAGE, whether the
    # clerk entered it before the passage or after: "Sen. Fernald Moved Ought
    # to Pass, RC 22y - 1n, MA" and then "Sen. Francoeur Floor Amendment
    # {2837}, (New Title), RC 13y - 10n, AA" (SB 336 of 2002), the bill that
    # went to the House amended.
    # A DECISION ENTERED AFTER THE GOVERNOR ACTED WAS MADE BEFORE: the
    # Senate's "Conference Committee Report # 2025-2809c; RC 16Y-8N, Adopted;
    # 06/26/2025" on HB 377 of 2025 was entered on 3 November and read as the
    # Senate adopting the report three months after the governor signed the
    # bill. The day its row states, where that is in the term and not after
    # the governor. Not a vote on the veto, which comes after it.
    gov = min((s["date"] for s in steps if s["body"] == "G" and s["date"]), default="")
    for st in steps:
        if st["act"] in ("passed", "referred") and (st["body"], st.get("_row_day")) in amended:
            st["amended"] = True
        st.pop("_row_day", None)
        said = st.pop("_stated", "")
        if (gov and st["body"] in ("H", "S") and st["date"] > gov and said
                and st["act"] not in ("override", "sustained")
                and _j_in_term(said, term) and said <= gov):
            st["date"] = said
    # The governor's line where the history has none but the chapter's
    # line does: the same evidence, read the same way.
    if law_line and not any(s["body"] == "G" for s in steps):
        got = _j_decide(law_line, bid)
        if isinstance(got, dict) and got["act"] in ("signed", "unsigned"):
            steps.append({"date": _j_stated_day(J_EFF_ANY.split(law_line, 1)[0]),
                          "body": "G", **got})
            gov_raw = law_line
    # A vote on a veto is the record of the veto. The 1989 docket has
    # "GOVERNOR'S VETO SUSTAINED, RC(172-140)" on HB 377 and no line of its
    # own for the veto, so the veto is the line before the vote, undated.
    first = next((i for i, s in enumerate(steps)
                  if s["act"] in ("override", "sustained")), None)
    if first is not None and not any(s["act"] == "vetoed" for s in steps):
        steps.insert(first, {"date": "", "body": "G", "act": "vetoed"})
    # One veto, one signature: HB 396 of 2024 carries "Vetoed by Governor
    # Sununu 07/19/2024" and, in October, "Vetoed by Governor 101024 [&]".
    seen_g = set()
    steps = [s for s in steps if s["body"] != "G"
             or not (s["act"] in seen_g or seen_g.add(s["act"]))]
    # In the order of the days the lines now carry, which a row dated by its
    # entry can have put out of step: HB 1650 of 2022's House passage of 5
    # January was entered after the governor's signature of the 6th. Stable,
    # so a day's own order stands; an undated line keeps its place.
    carry, keyed = "", []
    for i, s in enumerate(steps):
        carry = s["date"] or carry
        keyed.append((carry, i, s))
    steps = [s for _d, _i, s in sorted(keyed, key=lambda x: (x[0], x[1]))]
    steps = _j_answers_after(_j_in_recess(steps), bid)
    steps = _j_settle(_j_amended_on(steps))
    # A CONFERENCE FOLLOWS A PASSAGE. SB 200 of 1989 was killed on 9
    # February, "ITL REPORT ADOPTED", and its docket then has "CONF COMM
    # REPORT ADOPTED" on 24 May -- a report of a conference no chamber's vote
    # could have called, which made the rail pass the Senate under a
    # "Killed" chip. A conference line after a decision that ended the bill,
    # and no passage, is not read.
    steps = [s for i, s in enumerate(steps)
             if s["act"] not in ("conf_adopted", "conf_rejected", "conf_refused")
             or not any(t["act"] in J_ENDING for t in steps[:i])
             or any(t["act"] in ("passed", "referred", "concurred", "nonconcurred")
                    for t in steps[:i])]
    # A REPORT VOTED DOWN AND A NEW CONFERENCE AGREED TO IS NOT WHERE THE BILL
    # STOPPED. HB 723 of 1997: the Senate, which had passed the bill (amended,
    # on a voice vote, after voting Ought to Pass 19-5), voted down its
    # conferees' "unable to agree" report 10-13 and asked for a
    # new committee of conference 13-10, and the House acceded the same day
    # ("HOUSE ACCEDED TO REQ FOR NEW CONF COMM"). The new conference never
    # reported (CONFERENCE_NOT_REPORTED), and the rail marked the Senate as
    # where the bill was stopped -- "Rejected the conference report, 10–13"
    # -- under "Died when the session ended". A rejection the other chamber
    # answered by acceding to a new conference, with no vote on a report in
    # the rejecting chamber after it, is not that chamber's last word: its
    # passage is. Where the new conference did report, the rejection stays
    # on the record beside the vote that followed it (HB 1182 of 1990).
    renewed = max((e.get("date") or "" for e in evs
                   if J_NEW_CONFERENCE.search(e.get("raw") or "")), default="")
    if renewed:
        steps = [s for i, s in enumerate(steps)
                 if s["act"] != "conf_rejected" or (s["date"] or "") > renewed
                 or any(t["body"] == s["body"] and t["act"].startswith("conf_")
                        for t in steps[i + 1:])]
    # An introduction dated after the first decision on the bill is a date
    # something has wrong, and the stop goes undated rather than out of
    # order. HB 113 of 2005's "Introduced and ref to Crim Just & PSfty" stood
    # at 1 December 2006, eleven months after the House killed it -- but the
    # docket says 1 December 2004, and it was narrative.clamp_year that moved
    # it, reading a retained bill's second-year session as the whole of its
    # term (narrative.session_keeps).
    first_day = min((s["date"] for s in steps if s["body"] in ("H", "S") and s["date"]),
                    default="")
    if intro and first_day and intro > first_day:
        intro = ""
    if chapter:
        eff = _j_effective(gov_raw, *gov_more, law_line)
        # A LINE THAT CARRIES ANOTHER BILL'S CHAPTER CARRIES ITS EFFECTIVE DATE
        # TOO. SB 28 of 2009 reads "Signed by the Governor on 05/15/09;
        # Effective 07/07/09; Chapter 0028" -- SB 109's line, signed a week
        # earlier, with the day of the signature changed: sixty days from 15
        # May is 14 July, which is what SB 28's enrolled text prints
        # ("Effective Date: July 14, 2009") and what the database holds. Once
        # extract_chapters settled the chapter at 31 the rail read "Chapter
        # 31, in effect 7 Jul 2009". `db_effective` is the database's date on
        # a settled record whose docket number is not its chapter
        # (chapters.json's database_effective), and it is taken only where
        # the line states one date and the database another: a line that
        # states none, or several, is left saying none.
        if eff and db_effective and eff != db_effective:
            eff = db_effective
        # A law in effect on several dates says each, part by part, and its
        # stop on the rail stays undated: there is no one day to draw.
        parts = "" if eff else _j_effective_parts(gov_raw, *gov_more, law_line)
        # `effective` is the day the rail's Law stop is dated by (F13); the
        # line itself stays undated, so How it got here does not print the
        # day twice beside words that already say it.
        steps.append({"date": "", "body": "L", "act": "law",
                      "text": f"Chapter {chapter}" + (
                          f", in effect {_j_prose_date(eff)}" if eff else
                          f", in effect in parts: {parts}" if parts else ""),
                      "short": f"Chapter {chapter}", "effective": eff or ""})
    for e in evs:
        m = REFERENDUM.search(e.get("raw") or "")
        if m:
            yes = m.group("how").lower() == "adopted"
            t = J_REF_TALLY.search(e.get("raw") or "", m.end() - 1)
            steps.append({"date": e.get("date") or "", "body": "V",
                          "act": "ratified" if yes else "not_ratified",
                          "text": ("Ratified" if yes else "Not ratified")
                          + (f", {t.group(1)}–{t.group(2)}" if t else ""),
                          "short": "ratified" if yes else "not ratified"})
    for st in steps:
        st["mark"] = J_MARK.get(st["act"], "h")
        if "text" not in st:
            if st["body"] == "G":
                st["text"], st["short"] = {
                    "signed": ("Signed", "signed"), "vetoed": ("Vetoed", "vetoed"),
                    "unsigned": ("Became law without signature", "unsigned")}[st["act"]]
            else:
                st["text"], st["short"] = _j_words(st, bid)
        # "Adopted the conference report" on HB 42 of 1989, whose report said
        # "UNABLE TO AGREE", reads as the conferees having settled it.
        if (st["act"] == "conf_adopted" and unable_day is not None
                and (st.get("date") or "") >= unable_day):
            # THE VOTE BEFORE THE REPORT. "...the conferees' report that they
            # could not agree on a voice vote" reads as though the voice vote
            # were what they could not agree on; a tally after a comma is
            # read rightly.
            voice = "Adopted the conference report on a voice vote"
            if st["text"].startswith(voice):
                st["text"] = ("Adopted, on a voice vote, the conferees' report that "
                              "they could not agree" + st["text"][len(voice):])
            else:
                st["text"] = st["text"].replace(
                    "Adopted the conference report",
                    "Adopted the conferees' report that they could not agree", 1)
        if st.get("reconsidered"):
            st["text"] += ", reconsidered on " + _j_prose_date(
                st["reconsidered"], st["reconsidered"][:4] != st["date"][:4])
        for k in ("vote", "amended", "third", "to", "conf", "rule", "adjourned",
                  "unanswered", "intro_adopt", "short_of", "reconsidered", "recon_third",
                  "consent",
                  "_recess", "unaccepted", "_own_am"):
            st.pop(k, None)
        if st.pop("_untold", False) and untold is not None:
            untold.add(id(st))
    return intro, steps


def _j_answers_after(steps, bid):
    """A day's steps with each answer after the act it answers, across the
    two chambers, whose rows of one day the clerk can enter in either order.

    A chamber agreeing to or refusing the other's amendment answers that
    chamber's passage: HB 10 of 2025 had the House "Agreed to the Senate's
    amendment, 210–160" (entered at 1:52) ahead of the Senate passing it with
    that amendment (2:48), both on 5 June. And a vetoed bill goes back to the
    chamber it started in, which votes on the veto first: SB 434 of 2026 had
    the House sustaining the veto ahead of the Senate overriding it.

    And a bill passes the chamber its number names before the other one:
    HB 1650 of 2022 passed both on 5 January, and the Senate's row, entered
    that day, was listed ahead of the House's, entered on the 10th."""
    pre = bill_prefix(bid)
    origin = "H" if pre.startswith("H") else "S" if pre.startswith("S") else ""
    veto = ("override", "sustained")
    passing = ("passed", "referred")
    # The chamber the number names, special sessions' "SSHB" included.
    named = (pre[2:] if pre.startswith("SS") else pre)[:1]
    named = named if named in ("H", "S") else ""

    def answers(s, t, before):
        if not s["date"] or s["date"] != t["date"] or {s["body"], t["body"]} != {"H", "S"}:
            return False
        return ((s["act"] in ("concurred", "nonconcurred") and t["act"] == "passed")
                or (s["act"] in veto and t["act"] in veto and origin and s["body"] != origin)
                or (s["act"] in passing and t["act"] in passing and t["body"] == named
                    and not any(x["body"] == named and x["act"] in passing for x in before)))

    out = list(steps)
    i = 0
    while i < len(out):
        s = out[i]
        last = max((j for j in range(i + 1, len(out)) if answers(s, out[j], out[:i])),
                   default=None)
        if last is None:
            i += 1
            continue
        out.insert(last, out.pop(i))
    return out


# A RECONSIDERATION CARRIED ON A LATER DAY. _j_settle keeps the last of a
# day's decisions, so a decision reconsidered the same day is gone; one
# reconsidered days later stood until then, and is said to have been undone:
# "SEN REFUSED TO ACCEDE TO REQ FOR CONF COMM" on 12 May and "SEN MACDONALD
# MOVED TO RECONSIDER REQ TO ACCEDE, MA VV" on the 17th (HB 628 of 1994) read
# as a refusal followed by a conference report, with no word between.
J_RECONSIDER = re.compile(r"\breconsider\w*", re.I)
# Not the notice of one, the order of the day it is set for, or its debate.
J_RECON_NOT = re.compile(r"notice|special\s+order|limit\w*\s+debate", re.I)
# Where the motion names what it reconsiders, the decision must be that one:
# "REP GROSS MOVED TO RECONSIDER REQ FOR NEW CONF COMM" (HB 1025 of 1992) is
# the House's accession to a new conference, which is no line here, and not
# its adoption of the report the day before.
J_RECON_NAMES = [
    (re.compile(r"acced|\breq\w*\.?\s+(?:for|to)\s+(?:a\s+)?(?:new\s+)?(?:conf|c\s?of\s?c)", re.I),
     {"conf_refused"}),
    (re.compile(r"non-?\s?conc", re.I), {"nonconcurred"}),
    (re.compile(r"\bconc", re.I), {"concurred"}),
    (re.compile(r"conf\w*\.?\s*comm\w*\.?\s*rep|conference\s+report", re.I),
     {"conf_adopted", "conf_rejected"}),
    (re.compile(r"third\s+reading|3rd\s+r|\bpass|\bOTP|ought\s+to\s+pass", re.I),
     {"passed", "referred"}),
    (re.compile(r"inexpedient|\bITL\b|\bkill", re.I), {"killed"}),
    (re.compile(r"\btabl", re.I), {"tabled"}),
    (re.compile(r"interim\s+study", re.I), {"study"})]
# Where the naming stops: its vote, or the chamber's code for the outcome.
J_RECON_END = re.compile(r"\b(?:MA|MF|ML|AA|AF|AL|VV)\b|\b(?:RC|DV|DIV|Division)(?![A-Za-z])|"
                         r"\b(?:adopted|failed|lost|carried)\b", re.I)


def _j_reconsidered(steps, body, date, seg, last=True):
    """Mark the chamber's last decision reconsidered where `seg` is a
    reconsideration carried on a later day than it -- of that decision.

    One that names nothing reconsiders the last vote the chamber took, which
    is the decision only where nothing was voted on since (`last`): "REP
    CHAMPAGNE MOVED TO RECONSIDER, MA RC(211-160)" on HR 1 of 1997 is the
    House taking up again an amendment to its rules it had just rejected
    186-186, not the rules it adopted in December. Nor where the clause takes
    something up ahead of it: "Sen. Squires Concur with House
    Amendment{4347}; Sen. Squires Motion Reconsideration, MA,VV" (SB 326 of
    2000) is the Senate going back on that day's concurrence, which it then
    refused, and not on its passage of March.

    One that names the third reading alone, where the chamber reads the bill
    a third time again that day, is marked `recon_third` for _j_settle."""
    rc = J_RECONSIDER.search(seg or "")
    if not rc or J_RECON_NOT.search(seg[:rc.start()]):
        return
    o = J_SUSP_CODE.search(seg, rc.end()) or J_SUSP_WORD.search(seg, rc.end())
    if not o or not re.match(r"MA|AA|adopted|carried", o.group(0), re.I):
        return
    mine = [s for s in steps if s["body"] == body]
    if not mine or not mine[-1]["date"] or not date or mine[-1]["date"] >= date:
        return
    end = J_RECON_END.search(seg, rc.end())
    named = re.sub(r"(?i)\([^)]*\)|\b(?:motion|the|of|to|on|by|its|vote|action|whereby)\b|"
                   r"[^A-Za-z]+", " ", seg[rc.end():end.start() if end else len(seg)]).strip()
    if named:
        acts = next((a for rx, a in J_RECON_NAMES if rx.search(named)), set())
        if mine[-1]["act"] not in acts:
            return
    elif not last or _j_act(seg[:rc.start()]) or _j_has_outcome(seg[:rc.start()]):
        return
    mine[-1]["reconsidered"] = date
    if J_THIRD.search(named) and not re.search(r"\bpass|\bOTP|ought", named, re.I):
        mine[-1]["recon_third"] = True


def _j_in_recess(steps):
    """Steps with an answer to the other chamber's amendment that the docket
    dates before the amendment was made put after it, undated.

    A CHAMBER IN RECESS DATES ITS BUSINESS BY THE SITTING IT RECESSED. "House
    Non-Concurs and Requests Committee of Conference (Rep Hinch): MA VV (in
    recess of 6/3/2015)" was entered on 5 June; the Senate passed the
    amendments it refuses on the 4th, and the House Journal of the 3 June
    sitting prints them "Amendments printed SJ 6-4-15". The 1999 and 2005
    budgets' "6/23/1999 House Nonc with Sen Am" and "06/08/2005 House Nonc"
    are the same, a day before the Senate's passage. The day the House acted
    is after the Senate's and the row does not say it, so the line goes after
    the passage it answers with no day, rather than a day before it. Only
    within a week of that passage: HB 109 of 1999's refusal of 30 March is
    the answer to a Senate passage of 25 March its docket writes in words
    the journey does not read, not to the one of October."""
    out = list(steps)
    i = 0
    while i < len(out):
        s = out[i]
        other = {"H": "S", "S": "H"}.get(s["body"])
        # Of the passages that stood: a refusal made in recess answers the
        # passage the other chamber made again after reconsidering one. HB
        # 1409 of 2014's "Non-Concur with Senate AM and request C of C; MA VV
        # (In recess of 5/15/2014)", entered on the 21st, answers the Senate's
        # passage of 16 May, not the one of the 15th it reconsidered.
        later = [j for j, t in enumerate(out) if t["body"] == other
                 and t["act"] == "passed" and t["date"]
                 and not (s.get("_recess") and t.get("reconsidered"))]
        if (s["act"] in ("concurred", "nonconcurred") and s["date"] and later
                and all(out[j]["date"] > s["date"] for j in later)
                and _j_days(out[later[0]]["date"], s["date"]) <= 7 and later[0] > i):
            s["date"] = ""
            out.insert(later[0], out.pop(i))
            continue
        i += 1
    return out


def _j_amended_on(steps):
    """Steps with a chamber's passage amended where the passage it sent to a
    second committee was.

    THE AMENDMENT GOES TO FINANCE WITH THE BILL. SB 538 of 2026 passed the
    House "with Amendment 2026-1453h and 2026-1578h" on 23 April and went to
    Finance, whose report the House passed on 14 May with no amendment of its
    own -- and the rail's House stop read "voice vote", above the Senate
    refusing "the House Amendment" that same day. The passage after the
    second committee is the passage of the bill as the chamber amended it --
    and so is a passage after the chamber reconsidered its first, which
    undoes the vote and not the amendments adopted before it.

    A day's passages are one passage, amended if any was, as _j_merge folds
    them: HB 1462 of 2002's "Ought to Pass with Amendment {3485}, RC 13y -
    11n, AA" and its "OT3rdg, MA, VV" of 16 April, reconsidered on the 18th."""
    held, day = set(), {}
    for s in steps:
        b = s["body"]
        if s["act"] in ("passed", "referred"):
            if day.get(b) == s["date"]:
                s["amended"] = True
            if s.get("amended"):
                day[b] = s["date"]
        if s.get("amended") and (s["act"] == "referred" or s.get("reconsidered")):
            held.add(b)
        elif s["act"] == "passed" and b in held:
            held.discard(b)
            s["amended"] = True
    return steps


def _j_merge(into, st):
    """A second passage of the same sitting, folded into the first: amended
    if either was, and the count of the one that has a count -- but never the
    count of a motion to introduce ("Introduced and Adopted: MA DV 259-66 By
    Necessary Two-Thirds Vote", then "Ought to Pass : MA VV", HB 2023 of
    2022)."""
    into["amended"] = into.get("amended") or st.get("amended")
    # A reconsideration of the third reading is of the passage it is.
    into["reconsidered"] = into.get("reconsidered") or st.get("reconsidered")
    if st.get("intro_adopt"):
        return
    # NOR THE COUNT OF A MOTION TAKEN BEFORE THE AMENDMENT, where the passage
    # that names the amendment states a vote of its own. "OTP MA RC(19-5); SEN
    # F KING FL AM<1494>, WITHDRAWN; SEN SQUIRES FL AM<1504>, AA VV; SEN
    # RUBENS MOVED LOT, ML VV; PASSED WITH AM VV" (HB 723 of 1997) is the
    # Senate voting Ought to Pass 19-5, adopting a floor amendment, and
    # passing the bill so amended on a voice vote, and the rail read "Passed
    # with an amendment, 19–5": the count of the bill before it was amended,
    # beside the words of the bill after. The rail had no rule for a count
    # taken on an earlier motion of the day; this is the one case of it a
    # passage's own words decide. Measured over every history on 2 October
    # 2026 it moves eight Senate and House stops of 1990-1998, each of this
    # shape, two of them a passage counted, reconsidered, and made again
    # amended on a voice vote: "PASSED RC(21-3)", then "SEN DANAIS MOVED TO
    # RECONSIDER, MA VV; SEN RUBENS FL AM<1930> (NEW TITLE), AA VV; PASSED
    # WITH AM VV" (HB 1226 of 1998). Where no later passage names the
    # amendment -- SB 336 of 2002, passed 22-1 and then amended 13-10 on a
    # row of its own -- the count stays the passage's, as it was. Nor where
    # the later passage states no vote at all ("PASSED WITH AM", no VV): it
    # has no count of its own to give, and the earlier one stands.
    if st.get("_own_am") and not into.get("_own_am") and st["vote"][0]:
        into["vote"], into["_own_am"] = st["vote"], True
        into["consent"] = st.get("consent", False)
        into.pop("intro_adopt", None)
        return
    if into.pop("intro_adopt", False) or st["vote"][1] is not None or not into["vote"][0]:
        # And whose count it is (the consent calendar's, decision 51).
        into["vote"], into["consent"] = st["vote"], st.get("consent", False)


def _j_settle(steps):
    """One line a sitting: of a chamber's decisions on one day, the last is
    the one that stood -- a failed motion to pass followed by a kill, a
    passage followed by the table, a kill reconsidered and passed. And a third
    reading after a passage is that passage, not a second one."""
    out = []
    for st in steps:
        prev = out[-1] if out else None
        # The same across the other chamber's rows of that day: HB 282 of
        # 2025 passed the Senate on 26 June, was reconsidered and passed
        # again with a second amendment, and the House's concurrence in both
        # amendments sits between the two rows.
        mine = next((s for s in reversed(out) if s["body"] == st["body"]), None)
        if (st["act"] == "passed" and st["body"] in ("H", "S") and mine is not None
                and mine is not prev and mine["act"] == "passed"
                and mine["date"] == st["date"]):
            _j_merge(mine, st)
            continue
        if (prev and st["body"] in ("H", "S") and prev["body"] == st["body"]
                and prev["date"] == st["date"]):
            if st["act"] == "passed" and prev["act"] in ("passed", "referred") \
                    and st.get("third"):
                # With its count, where the third reading had one:
                # "Ought to Pass with Amendment {1084}, AA, VV; OT3rdg, RC
                # 23Y-1N, MA" (SB 110 of 2001).
                if prev["act"] == "passed":
                    _j_merge(prev, st)
                continue
            if st["act"] == "passed" and prev["act"] == "passed":
                _j_merge(prev, st)
                continue
            # A motion to pass that failed is a substitute motion the clerk
            # wrote AFTER the result it lost to: "ITL REPORT ADOPTED VV; REP.
            # OUELLETTE REMOVED & SUBST OTP, ML VV" (HB 339 of 1989).
            if st["act"] == "failed" and not prev.get("unanswered"):
                continue
            # Passed, then laid on the table before it went anywhere: both
            # happened, and a later day may take it off the table again.
            if prev["act"] in J_PASSING and st["act"] == "tabled":
                out.append(st)
                continue
            # The same two the other way round are the same two: a bill on
            # the table is not passed until it is taken off, which is a row
            # of its own. HB 50 of 2023 has "Lay HB50 on Table: MA DV
            # 206-170" entered before "Ought to Pass with Amendment: MA VV",
            # and died on the table.
            if prev["act"] == "tabled" and st["act"] in J_PASSING:
                out[-1:] = [st, prev]
                continue
            out[-1] = st
            continue
        # Unless that passage was reconsidered: HB 1462 of 2002 passed the
        # Senate on 16 April, was reconsidered on the 18th, and "OT3rdg, MA,
        # VV" that day is it passing again.
        # BUT NOT WHERE ONLY ITS THIRD READING WAS, AND WAS READ AGAIN THAT
        # DAY. The House reconsidered its third reading of 14 March 2012 to
        # take one bill out of it, and read the other fourteen a third time
        # again: "Reconsider Third Reading Motion of March 14: MA VV", then
        # "Third Reading: MA VV". HB 1282's passage, 180-133 on the 14th,
        # read "reconsidered on 15 Mar", as if that vote had been undone, and
        # the rail showed the voice vote of the repeated reading in its
        # place. The reading again is the passage it was, as a third reading
        # on a later day always is.
        if st.get("third") and st["act"] == "passed":
            mine = [s for s in out if s["body"] == st["body"]]
            if mine and mine[-1]["act"] == "passed":
                last = mine[-1]
                if last.get("recon_third") and last.get("reconsidered") == st["date"]:
                    last.pop("reconsidered")
                    last.pop("recon_third")
                if not last.get("reconsidered"):
                    continue
        out.append(st)
    # A motion to table the clerk gave no vote for stands only as the
    # chamber's last word.
    return [s for i, s in enumerate(out) if not s.get("unanswered") or not any(
        t["body"] == s["body"] for t in out[i + 1:])]


def journey_state(steps, body):
    """p, x or h: where a chamber's own decisions left the bill, or "" where
    it made none."""
    mine = [s for s in steps if s["body"] == body]
    return mine[-1]["mark"] if mine else ""


def journey_rail(intro, steps, rail, bid, status=""):
    """The rail's stops for a bill's own view, dated from the journey.

    The marks are the index's -- the same `passage` the list card draws -- so
    the card and the page cannot disagree about a stop; the journey gives
    each one its date, its word (`short`, which only the index row keeps, for
    the sentence its card says) and its sentence (`say`). The stops follow
    the bill's route: a resolution of one chamber has that chamber; a
    concurrent resolution two chambers and no governor; a CACR goes to the
    voters instead of the governor, with the ring on Voters while it waits
    for them."""
    if not rail or rail[0] not in ("H", "S"):
        return []
    origin = rail[0]
    other = "S" if origin == "H" else "H"
    marks = rail[1:]
    pre = bill_prefix(bid)
    stops = [{"stop": "Introduced", "mark": "p", "date": intro or "",
              "short": "", "say": "Introduced"}]

    def chamber(b, mark):
        mine = [s for s in steps if s["body"] == b]
        pick = None
        if mark == "p":
            pick = (next((s for s in reversed(mine) if s["act"] in ("passed", "adopted")), None)
                    or next((s for s in reversed(mine) if s["act"] == "referred"), None))
        elif mark in ("x", "h"):
            pick = (next((s for s in reversed(mine) if s["mark"] == "x"), None)
                    if mark == "x" else None) or (mine[-1] if mine else None)
        name = {"H": "House", "S": "Senate"}[b]
        return {"stop": name, "mark": mark, "date": (pick or {}).get("date", ""),
                "short": (pick or {}).get("short", ""),
                "say": (pick or {}).get("text", "") or RAIL_SAY.get(mark, "")}

    if len(marks) == 2:
        return stops + [chamber(origin, marks[0])]
    stops += [chamber(origin, marks[0]), chamber(other, marks[1])]
    if pre == "CACR":
        v = next((s for s in steps if s["body"] == "V"), None)
        low = (status or "").lower()
        when = re.search(r"in ([A-Z][a-z]+) (\d{4})", status or "")
        if v:
            stops.append({"stop": "Voters", "mark": v["mark"], "date": v["date"],
                          "short": v["short"], "say": v["text"]})
        elif "goes to the voters" in low:
            said = status.split(", ", 1)[-1]
            stops.append({"stop": "Voters", "mark": "h", "date": "",
                          "short": (f"{when.group(1)[:3]} {when.group(2)}" if when else ""),
                          "say": said[:1].upper() + said[1:]})
        elif "went to the voters" in low:
            stops.append({"stop": "Voters", "mark": "-", "date": "",
                          "short": "not recorded",
                          "say": "Went to the voters; the docket does not record "
                                 "their answer"})
        else:
            stops.append({"stop": "Voters", "mark": "-", "date": "", "short": "",
                          "say": RAIL_SAY["-"]})
        return stops
    if pre in NO_GOVERNOR:
        return stops
    gm, lm = marks[2], marks[3]
    g = next((s for s in steps if s["body"] == "G"
              and (s["act"] == "vetoed") == (gm == "x")), None)
    law = next((s for s in steps if s["body"] == "L"), None)
    stops.append({"stop": "Governor", "mark": gm,
                  "date": g["date"] if g and gm in ("p", "x") else "",
                  "short": g["short"] if g and gm in ("p", "x") else "",
                  "say": g["text"] if g and gm in ("p", "x") else RAIL_SAY.get(gm, "")})
    stops.append({"stop": "Law", "mark": lm, "date": law_day(lm, law, stops, steps),
                  "short": law["short"] if law and lm == "p" else "",
                  "say": (law["text"] if law and lm == "p"
                          else "Did not become law" if lm == "x"
                          else RAIL_SAY.get(lm, ""))})
    return stops


def law_day(mark, law, stops, steps):
    """The day under the rail's last stop, Law (the person, 7 October 2026,
    F13): "under Law, the effective date when it became law; when killed, the
    day it was killed under that last stop". The Law stop was the one stop
    reached that carried no day.

    A law: the day it took effect, where its lines state one day
    (_j_effective) -- a law in effect on several dates, by section, states
    none, and neither does its stop. A bill that did not become law: the day
    it was stopped, which is the latest day of a decision that ended it, on
    a stop or in the journey (a kill, a veto sustained, a conference report
    rejected). A Law stop not reached -- a bill still moving, or held for
    interim study -- has no day, as no stop not reached has."""
    if mark == "p":
        return (law or {}).get("effective", "") if law else ""
    if mark != "x":
        return ""
    days = [s.get("date") or "" for s in stops if s.get("mark") == "x"]
    days += [s.get("date") or "" for s in steps if s.get("mark") == "x"]
    return max((d for d in days if d), default="")


# What a stop says when no line of the journey fills it -- the same words the
# list card's rail uses.
RAIL_SAY = {"p": "Passed", "h": "Is here now", "x": "Stopped here",
            "-": "Never reached"}

# ONE RAIL, ALWAYS DETAILED (the person, 5 October 2026). A card in a list
# drew the bare rail -- four glyphs from `passage` -- and the same card opened
# drew the dated one, so the rail changed shape under the reader's eye as the
# card opened. The list card draws the dated rail now, before anything is
# fetched, so its stops travel in the term's index row: each one the stop's
# letter and its mark, its day and its words, ["Hp", "2025-02-13", "voice
# vote"], with blanks at the end left off -- ["S-"] for a Senate it never
# reached. The words a reader hears on the bill's page (`say`) stay in the
# record.
#
# THE DAY IS DRAWN AND THE WORDS ARE NOT (the person, the same day: "only
# have dates for the actions under each of the items"). A stop's words --
# "voice vote", "16–8, amended", "Chapter 160" -- are what the card's rail
# says to a reader who hears it, and drawn nowhere; the record's stops carry
# none, because its `say` is what the page says (build_bills drops them once
# the index row has its copy).
#
# idx/<term>.json only. index.json, which once held every row, was retired on
# 5 October 2026 at nine tenths of Cloudflare's 25 MiB for one file, and the
# rail is the card's, which bills.csv does not draw.
RAIL_CODE = {"Introduced": "I", "House": "H", "Senate": "S", "Governor": "G",
             "Law": "L", "Voters": "V"}


def without_rail(row):
    """An index row as everything but idx/<term>.json writes it."""
    return {k: v for k, v in row.items() if k != "rail"}


def index_rail(jrail):
    """journey_rail's stops as the index row carries them."""
    out = []
    for s in jrail:
        cell = [RAIL_CODE[s["stop"]] + s["mark"], s.get("date") or "", s.get("short") or ""]
        while len(cell) > 1 and not cell[-1]:
            cell.pop()
        out.append(cell)
    return out

# The decisions that end a bill in the chamber that makes them.
J_ENDING = {"killed", "died", "postponed", "study", "failed", "sustained",
            "conf_rejected", "conf_refused"}


def journey_disagrees(steps, kind, status, rail, bid):
    """Why the journey, the bill's status and its rail do not tell one story,
    or "" where they do. Each is a claim the page makes about the same bill,
    and this is the test that they are one claim.

    Read against the status the bill carries and the marks the list card
    draws, so the answer is about what a reader sees."""
    if not steps:
        return ""
    status = status or ""
    low = status.lower()
    ch = [s for s in steps if s["body"] in ("H", "S")]
    last = ch[-1] if ch else None
    # Where each chamber's own decisions left it. Rows of one day are not
    # reliably in order across the two chambers -- HB 609 of 2026 has the
    # House laying the bill on the table and the Senate adopting the
    # conference report on 4 June, in that order -- so an ending is looked
    # for in either chamber's last word, not only in the last row.
    finals = [s for b in ("H", "S") for s in [next(
        (x for x in reversed(ch) if x["body"] == b), None)] if s]
    gacts = [s["act"] for s in steps if s["body"] == "G"]
    gov = "vetoed" if "vetoed" in gacts else (gacts[-1] if gacts else "")
    law = any(s["body"] == "L" for s in steps)
    acts = {s["act"] for s in steps}
    name = {"H": "House", "S": "Senate"}

    def passed(b):
        # A chamber that agreed to the other's version agreed to the bill:
        # "SEN CONCURS WITH HOUSE AM TO JT RULES" is the Senate's word on HCR
        # 28 of 1996.
        return any(s["body"] == b and (s["act"] in J_PASSING or s["act"] == "concurred")
                   for s in steps)

    # THE RAIL. A chamber the rail passes is one the journey has passing it;
    # a chamber the rail crosses is not one the journey leaves passed.
    if rail and rail[0] in ("H", "S"):
        origin, marks = rail[0], rail[1:]
        other = "S" if origin == "H" else "H"
        for b, m in zip((origin, other), marks[:2] if len(marks) == 4 else marks[:1]):
            if m == "p" and not passed(b):
                return f"the rail passes the {name[b]} and no line has it passing the bill"
            if m == "x" and journey_state(steps, b) == "p":
                return f"the rail stops the bill in the {name[b]}, whose last word passed it"
            if m == "-" and any(s["body"] == b for s in steps):
                return f"the rail never reaches the {name[b]}, which decided on it"
        if len(marks) == 4:
            g, lw = marks[2], marks[3]
            if g == "p" and gov not in ("signed", "unsigned"):
                return "the rail passes the governor and no line has a signature"
            if g == "x" and gov != "vetoed":
                return "the rail has the governor stop it and no line has a veto"
            if g == "-" and gov:
                return "the rail never reaches the governor, whose action is a line"
            if lw == "p" and not (law or gov in ("signed", "unsigned") or "override" in acts):
                return "the rail ends at law and no line says it became law"
            if lw != "p" and law:
                return "a line gives it a chapter and the rail does not end at law"

    # THE STATUS.
    if kind == "law":
        if "unsigned" in low:
            return "" if gov == "unsigned" else "law unsigned, with no line saying so"
        if "overrid" in low:
            return "" if gov == "vetoed" and "override" in acts else (
                "a veto overridden, with no veto and override among the lines")
        return "" if gov == "signed" else "signed into law, with no signature among the lines"
    if kind == "veto":
        if gov != "vetoed":
            return "vetoed, with no veto among the lines"
        if "override failed" in low and "sustained" not in acts:
            return "the override failed, with no vote sustaining the veto"
        return ""
    if gov and kind != "law":
        return f"the governor's action is a line and the status is {status!r}"
    if kind == "adopted":
        pre = bill_prefix(bid)
        if pre in SINGLE_CHAMBER:
            b = "H" if SINGLE_CHAMBER[pre] == "House" else "S"
            return "" if passed(b) else f"{status}, with no line adopting it"
        if not (passed("H") and passed("S")):
            return f"{status}, without both chambers passing it"
        v = [s for s in steps if s["body"] == "V"]
        if "not ratified" in low:
            return "" if v and v[-1]["act"] == "not_ratified" else "not ratified, with no referendum line"
        if "ratified" in low:
            return "" if v and v[-1]["act"] == "ratified" else "ratified, with no referendum line"
        return ""
    want = {
        # A motion to pass that failed, with nothing after it, is how the
        # record of the 1990s shows a resolution or bill rejected: SCR 13 of
        # 1992, "ADOPTION ML RC(95-235)", is "Killed" by its status.
        "Killed": {"killed", "died", "conf_rejected", "failed"},
        "Failed to pass": {"failed"},
        "Indefinitely postponed": {"postponed"},
        "Referred for interim study": {"study"},
        "Died on the table": {"tabled", "died"},
        "Laid on the table": {"tabled", "died"},
        "Died when the conference report was rejected": {"conf_rejected"},
        # Only a journal record's journey has this line (journal_story).
        "Withdrawn": {"withdrawn"},
    }.get(status)
    if want is not None:
        if any(f["act"] in want for f in finals):
            return ""
        return (f"{status}, and the last decision is "
                f"{last['text'][:40]!r}" if last else f"{status}, and no chamber decided")
    if status.startswith("One chamber did not concur") or status == "In a committee of conference":
        if any(f["act"] in ("nonconcurred", "conf_refused", "concurred") for f in finals):
            return ""
        return f"{status}, and the last decision is {last['text'][:40]!r}" if last else (
            f"{status}, and no chamber decided")
    if status == "Conference committee report adopted":
        return "" if "conf_adopted" in acts else f"{status}, with no line adopting one"
    # The conferees' report of no agreement need not have been voted on, but
    # the bill must have gone to a conference: a chamber refused the other's
    # version, or adopted a conference report.
    if status == CONF_UNABLE:
        return "" if acts & {"nonconcurred", "conf_adopted"} else (
            f"{status}, with no line sending it to a conference")
    if status == "Passed one chamber":
        if last and last["act"] in J_ENDING:
            return f"{status}, and the last decision is {last['text'][:40]!r}"
        # By where each chamber's own last word left it: HB 707 of 1999 was
        # approved by the Senate and sent to Finance, which never reported.
        carried = [b for b in ("H", "S") if journey_state(steps, b) == "p"]
        return "" if len(carried) == 1 else f"{status}, and the lines have " + (
            "both chambers passing it" if carried else "neither passing it")
    # A bill still in its first committee has had no floor decision carry it
    # -- or none that stood: HB 442 of 1993 was approved and sent to
    # Appropriations, and then to interim study, where its report was filed.
    if status in ("In committee", "Committee report filed", "Retained in committee") and \
            any(journey_state(steps, b) == "p" for b in ("H", "S")):
        return f"{status}, and the lines have a chamber passing it"
    # Everything else says the bill was still on its way when it stopped:
    # died when the session ended, in progress. An interim study's report
    # filed is the study's end: HB 442 of 1993.
    if status == "Committee report filed" and last and last["act"] == "study":
        return ""
    if last and last["act"] in {"killed", "postponed", "study", "died"}:
        return f"{status}, and the last decision is {last['text'][:40]!r}"
    return ""


def archive_coverage(bills, narratives, sponsors, reports, rollcalls,
                     procs, current):
    """What has actually been fetched for each archived term.

    ONE SENTENCE DESCRIBED 1989 AND 2023 IDENTICALLY. The page carried a
    single paragraph gated on one boolean, on 31,449 of 33,683 bill pages,
    and it was wrong in both directions.

    It UNDERSTATED the recent archived terms: 2017-2018, 2019-2020 and
    2023-2024 have full dockets and generated histories, and the "View docket"
    block contradicting the paragraph renders seven lines below it.

    It OVERSTATED the older ones. "The recorded votes come from the General
    Court's database" is false for fifteen terms -- named roll calls exist
    only for 2023-2024 and the current term. "The committee it went to and the
    date of its hearing" is false for the five terms 1989-1998, which have no
    committee at all.

    Measured per TERM, not per bill. 466 bills of 2023-2024 have no committee
    report and 131 have no sponsors; deriving this from the record in hand
    would have each of them announce that the whole term lacks them. Coverage
    is a property of what was fetched.
    """
    cov = {}
    for term in bills:
        if term == current:
            continue
        # SPONSORS BY SHARE, since they arrive a page at a time. The bill text
        # the lane saves names them, so a term can hold ten sampled bills'
        # sponsors and none for its other 1,600; "any" would tell all 1,600
        # their term has them. Nine in ten is a judgement, not a measurement:
        # the database's own term, 2023-2024, holds 93% and its gaps are real
        # gaps. A bill that has sponsors in a term below the line says so for
        # itself -- app.js reads the bill's own list before this flag.
        _named = sum(1 for _b in bills[term] if ((sponsors or {}).get(term) or {}).get(_b))
        cov[term] = {
            "docket": bool((narratives or {}).get(term)),
            "sponsors": _named >= 0.9 * max(len(bills[term]), 1),
            "reports": bool((reports or {}).get(term)),
            "votes": bool((rollcalls or {}).get(term)),
            # A recording linked to a bill, not merely a proceeding on record.
            "video": any(p.get("video_id")
                         for (t_, _b), ps in (procs or {}).items()
                         if t_ == term for p in ps),
            # A committee proceeding on record at all. 1989-1998 have their
            # hearings from the docket's shorthand and no roll call; 1999-2014
            # the other way round. The page has to be able to say which.
            "hearings": any(t_ == term and ps
                            for (t_, _b), ps in (procs or {}).items()),
            "committee": any(b.get("house_committee") or b.get("senate_committee")
                             for b in bills[term].values()),
        }
    return cov


def bill_note(notes, term, bid):
    """The standing note for this bill, if it has one.

    TWO KEY SHAPES, DELIBERATELY. A note in "every_term" is about a number
    that means the same thing term after term -- HB1 has been the budget in
    every term since 1993-1994 -- which is the exact opposite of how the rest
    of this project keys things, and is why the file says so at the top.
    A note in "by_term" is about one bill in one term, which is what the
    ten-year transportation plan needs: it is HB2000, then HB2004, HB2006,
    HB2010, and on to HB2026, a different number every time.

    "from" is what keeps a standing note off the bills that merely share a
    number. HB1 goes back to 1989-1990, but the 1989 bill is a special
    session bill about the public utilities commission and the 1991 one is a
    medicaid enhancement tax. Neither is the budget, and without this both
    would have been published saying they were.
    """
    if not notes:
        return None
    one = ((notes.get("by_term") or {}).get(term) or {}).get(bid)
    if one:
        return one
    n = (notes.get("every_term") or {}).get(bid)
    if not n:
        return None
    if n.get("from") and term < n["from"]:
        return None
    if n.get("until") and term > n["until"]:
        return None
    return n


def check_notes(notes, bills):
    """Every note must name a bill that exists, or say so loudly.

    A note file that matches nothing exits zero having attached nothing,
    which is the silent success this project keeps getting caught by --
    "HB 1" with a space instead of "HB1" would do it, and the only symptom
    would be a page that looks exactly as it did before.
    """
    if not notes:
        return
    have = {(term, bid) for term, bs in bills.items() for bid in bs}
    numbers = {bid for _t, bid in have}
    missing = []
    for bid, n in (notes.get("every_term") or {}).items():
        if bid not in numbers:
            missing.append(f"every_term {bid}")
        elif n.get("from") and not any(t >= n["from"] for t, b in have
                                       if b == bid):
            missing.append(f'every_term {bid} from {n["from"]}')
    for term, bs in (notes.get("by_term") or {}).items():
        for bid in bs:
            if (term, bid) not in have:
                missing.append(f"by_term {term} {bid}")
    if missing:
        raise SystemExit(
            "bill_notes.json names bills that are not in the record: "
            + ", ".join(missing)
            + "\nA note that matches nothing attaches nothing and the build "
              "would exit zero having done it.")


def vote_member(m, body, legs, unnamed):
    """One member's entry in a roll call.

    This was nested inside build_bills and captured legs and unnamed from the
    enclosing scope; they are parameters now. unnamed is still mutated, which
    is why it is passed explicitly rather than quietly closed over.

    The name comes from the VOTE record, which build_data.py has already
    resolved against the roster and against former_members.json. The roster
    is the fallback rather than the source, because it holds sitting members
    only.

    Not "label": that field is a composite of name, party and seat, and the
    roll call grid wants a name.

    The party letter comes from the vote too, so the name agrees with the
    party segment the member is shown under.
    """
    raw = (m.get("name") or "").strip()
    if not raw or raw.lower().startswith(("member #", "former member")):
        rec = legs.get(m.get("member_id"), {})
        raw = (rec.get("name") or raw or "").strip()
    if not raw or raw.lower().startswith(("member #", "former member")):
        unnamed.add(str(m.get("member_id")))
        raw = f"Member #{m.get('member_id')}"
    lab = member_labels(raw, chamber=(legs.get(m.get("member_id"), {})
                                      .get("chamber") or body),
                        party=m.get("party"))
    return {"n": lab["display"], "s": lab["sort"] or sort_name(raw),
            "p": m.get("party") or "X", "v": m.get("vote")}


def bill_sponsor_list(bid, b, year, term, current, sponsors, legs,
                      leg_by_sort, leg_by_name, sponsored, seats=None, left=None,
                      term_roster=None):
    """Who put their name to this bill, and their own bill list, both.

    It mutates `sponsored`, which is the caller's accumulator of what
    each member has sponsored, the same way vote_member mutates
    `unnamed`. That is why it is passed explicitly rather than closed
    over: a function that changes something belonging to its caller
    should say so in its signature.

    `left` is ({sort name: [member]}, {name key: [member]}) of the members
    who hold no seat now, and `term_roster` {id: member} the term's own
    roster as it was frozen, both passed only for a term whose frozen roster
    is not the sitting one (build_bills says which); None everywhere else,
    which is every term before the first Organization Day.

    `prime` stays in the loop. It is one line and it reads better
    beside the payload that uses it than as an extra return value.
    """
    sp_list, filed = [], set()
    for _s in P.per_term(sponsors, term, current).get(bid, []):
        _m = legs.get(_s.get("member_id"))
        if not _m:
            _m = (leg_by_sort.get(sort_name(_s.get("name") or ""))
                  or leg_by_name.get(name_key(_s.get("name") or "") or ("", "")))
            # A NAME IS A PERSON ONLY WHERE THAT PERSON SAT. A record matched on
            # its name alone is the member only if they held a seat in that
            # chamber that term (member_links.seats_held); otherwise it is
            # somebody else of the same name, and stays unlinked the way a
            # former member does. When it was added it turned nobody away.
            ch = (_s.get("chamber") or "")[:1]
            if _m and seats is not None and not any(
                    t == term and (not ch or c == ch)
                    for t, c in seats.get(str(_m.get("id")), ())):
                _m = None
            # A FINISHED TERM'S MEMBERS WHO HOLD NO SEAT NOW (5 October 2026).
            # While 2025-2026 was the session's, this name fell back on the
            # roster, which was that term's. After the turn the roster is the
            # next House, and on the rehearsal of the turn 900 sponsor names
            # on 491 of the term's bills -- a third of the House, gone at the
            # election -- lost their link and read their seat as the record
            # pads it ("Belk 07"), though each of them has a page under
            # `former`. So for a term frozen and finished (`left`), a name
            # the sitting roster does not answer is looked for among those
            # members too, under the same rule: only one who sat in that
            # chamber that term.
            if not _m and left:
                for _f in (*left[0].get(sort_name(_s.get("name") or ""), ()),
                           *left[1].get(name_key(_s.get("name") or "") or ("", ""), ())):
                    if seats is None or any(
                            t == term and (not ch or c == ch)
                            for t, c in seats.get(str(_f.get("id")), ())):
                        _m = _f
                        break
        _m = _m or {}
        # The roster first, then whatever the sponsor record carries in
        # its own right. build_data fills the county and district in for a
        # member who has left, from former_members.json, so that they are
        # named the same way as anyone else: "Rep. Suzanne Vail (D - Hills
        # 6)", not a bare name under a heading about a missing chamber.
        #
        # EXCEPT A SPONSOR READ OFF THE BILL'S TEXT, which carries the seat the
        # text printed and the party of that term's roll calls -- the seat they
        # held when they signed it. Built from the roster, 2023 HB 25's "Rep.
        # McConkey, Carr. 8" read "Sen. Mark McConkey (R - SD3)" under the
        # heading Representatives, and every House bill of a member now in the
        # Senate would have done the same. The link still goes to their page.
        # ... or whose seat was dated from it: seat_into puts the bill's own
        # printed chamber, county and district on a database sponsor, and the
        # roster must not then be preferred over the thing that corrected it.
        # ... AND A ROW WHOSE SEAT IS ITS OWN RECORD'S AND NOTHING ELSE'S: the
        # General Court's sponsor record filling a bill no other source names
        # a sponsor for (past_sponsors.filled), which holds a chamber and no
        # district, and the House Journal's list on a bill of a past term
        # (build_data.journal_sponsor_rows), which prints the seat of the
        # day. Neither takes anything from the roster: a 1993 bill's sponsor
        # who sits in the Senate today was drawn "Sen." at today's district,
        # and one with no party on that term's ballots is given none.
        #
        # AND A TERM WHOSE OWN ROSTER IS FROZEN (`term_roster`, the review of
        # 5 October 2026): its member as that roster has them, the seat they
        # sat in, before the record of whoever they are today. After the turn
        # `_m` is the sitting record, and a Representative elected to the
        # Senate under a new id is joined to it by member_links: all 93 of
        # Rep. Sabourin dit Choinière's 2025-2026 bills would have read "Sen.
        # ... (R - SD23)". The link still goes to their own page, through `_m`.
        _t = ((term_roster or {}).get(str(_s.get("member_id") or ""))
              or (term_roster or {}).get(str(_m.get("id") or "")) or _m)
        if _s.get("seat_source") in (PSP.SOURCE, JOURNAL_SOURCE):
            _lab = member_labels(
                _s.get("name"),
                chamber=_s.get("chamber") or _m.get("chamber"),
                party=_s.get("party"),
                district=_s.get("district"), county=_s.get("county"))
        elif _s.get("source") == TS.SOURCE or _s.get("seat_source") == TS.SOURCE:
            _lab = member_labels(
                _s.get("name"),
                chamber=_s.get("chamber") or _t.get("chamber"),
                party=_s.get("party") or _t.get("party_code"),
                district=_s.get("district") or _t.get("district"),
                county=_s.get("county") or _t.get("county"),
                county_abbr=None if _s.get("district") else _t.get("county_abbr"))
        else:
            _lab = member_labels(
                _s.get("name"),
                chamber=_t.get("chamber") or _s.get("chamber"),
                party=_t.get("party_code") or _s.get("party"),
                district=_t.get("district") or _s.get("district"),
                county=_t.get("county") or _s.get("county"),
                county_abbr=_t.get("county_abbr"))
        # The address of this member's own page, where the sponsor was
        # matched to the roster. Where they were not -- a former member,
        # or a name the join missed -- there is no page and no link, which
        # is the honest outcome rather than a link that goes nowhere.
        # The member's OWN address, not one derived from the label above --
        # own_slug says why that distinction is not cosmetic.
        _slug = own_slug(_m) if _m.get("id") else ""
        sp_list.append({**_s, **_lab, "slug": _slug})
        # FILED UNDER THE MEMBER THE PAGE LINKS. This used the record's own id,
        # and every 2023-2024 record, with 4,569 of 2025-2026's, carries an
        # employee number or none: 349 of 406 members' Sponsored tabs missed
        # 11,855 bills their bill pages credited them with. A record matched to
        # nobody keeps its own id, as before; one member twice on a bill is
        # filed once.
        _mid = str(_m.get("id") or _s.get("member_id") or "")
        if _mid and _mid not in filed:
            filed.add(_mid)
            sponsored[_mid].append({
                "bill": bid, "n": b.get("designation") or bid,
                "title": b.get("title", ""), "year": year, "term": term,
                "prime": bool(_s.get("prime"))})
    return sp_list


# `between` is true where a dated docket line between the chambers decided
# the status over the fields (between_chambers and the two rules beside it),
# so status_source can say the docket did.
#
# `source` is JOURNAL_SOURCE where the status is the House Journal's, for a
# bill the General Court's files do not carry; "" otherwise.
Disposition = namedtuple("Disposition",
                         "kind status told settled prefix stated stale between source",
                         defaults=(False, ""))


def bill_committees(b, bid):
    """(committee, committees) for a bill's index row.

    `committees` is every committee the bill has, each with its chamber, House
    first; the card lists them in that order. `committee` is THE committee of
    the bill -- what idx/<term>.json and the committee list in the
    site's meta carry -- and it is the one in the chamber the bill began in.
    It was committees[0], which made it the House's for every Senate bill that
    crossed over: SB 1 of 2023, referred to the Senate's Judiciary, was filed
    under House Finance.
    """
    cmtes = [f"{ch} {names.committee(nm)}" for ch, nm in
             (("House", b.get("house_committee") or ""),
              ("Senate", b.get("senate_committee") or "")) if nm]
    origin = ("Senate " if str(b.get("chamber") or bid[:1]).upper()
              .startswith("S") else "House ")
    return (next((c for c in cmtes if c.startswith(origin)),
                 cmtes[0] if cmtes else ""), cmtes)


def bill_index_row(bid, b, year, term, cmte, cmtes, disp, prime,
                   narr, rcs, coverage, carried, dates, chapter="",
                   passed=None, acted=None, live=False):
    """One bill's row in the search index.

    It comes after bill_disposition because it reads that function's
    result, so a mistake there surfaces here. `live` is whether the bill's
    session still has days to sit, which is what Tabled and Vetoed need
    (chip_word).

    years.add(year) stays in the loop. It belongs to the caller's
    bookkeeping rather than to a row, and moving it would give this
    function a side effect for no gain.
    """
    return {
        "id": bid,
        "n": b.get("designation") or re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", bid),
        # WITHOUT THE "(New Title)" MARK. This string is the card's heading and
        # app.js builds the search haystack out of it, so the mark was both the
        # first thing read on 5,718 cards and a word every one of them matched.
        # build_bill_pages.py has taken it off the page's own title, its
        # citation and its description since it was written; the index never
        # got the same treatment, which is why the two disagreed.
        "year": year, "title": clean_title(b.get("title", "")),
        # The sponsor FACET groups on this string, so it has to be one
        # spelling per person. The two sources spell a name differently --
        # the LSR files write "Germana, Nicholas" and the status page
        # writes "Nicholas Germana" -- and the raw name was going straight
        # into the facet, so 323 of the site's 430 sponsors were listed
        # twice, once per source. person_name() is the same normaliser the
        # display label already goes through.
        "sponsor": person_name(prime["name"]) if prime else "",
        "sponsor_label": prime.get("display", "") if prime else "",
        "committee": cmte, "committees": cmtes,
        "topic": b.get("subject", ""),
        # Whether the General Court filed it there or this site did.
        # The facet mixes the two and a reader is entitled to know which.
        "topic_by": b.get("subject_source", ""),
        "kind": disp.kind, "status": disp.status,
        # The word the card and the Status filter show (chip_word). The
        # status beside it keeps how the bill ended.
        "chip": chip_word(disp.kind, disp.status, live),
        "term": term, "carried": carried,
        # An archived term, whose bills come from the General Court's
        # search rather than from a session's own files. The page says
        # so, because an empty summary reads as a broken page and this
        # is a stated limit rather than a fault.
        **({"archived": (coverage or {}).get(term) or True}
           if b.get("archived") else {}),
        "status_stated": bool(disp.told),
        # HSGL, one character each: how far the bill got and where it
        # stopped. Four characters in the index rather than four fields,
        # because idx/<term>.json is loaded up front by every visitor.
        # The journey says which chambers carried it and which decided on it
        # at all, where the stages alone cannot (see passage()).
        "passage": passage((narr or {}).get("stages"), disp.kind,
                           disp.status, bid, passed, acted),
        "last_action": dates[-1] if dates else "",
        # Only on a bill that became one, so the 21,864 that did not cost
        # the up-front index nothing. bills.csv reads it from here, which
        # keeps the download and the page from disagreeing.
        **({"chapter": chapter} if chapter else {}),
        "nrc": len([r for r in rcs if not r.get("procedural")]),
        "votedays": sorted({r["date"] for r in rcs if r.get("date")}),
    }

# The record's own name for a stage a bill stopped at, for bill_disposition's
# last resort. Latest stage first: a bill whose fields read CONFERENCE
# COMMITTEE and CONFERENCE REPORT ADOPTED got as far as the report. The
# report's being adopted says nothing about whether the conferees agreed --
# 1989's HB 42 was adopted "UNABLE TO AGREE" and died -- so the label says
# only what the field says, and between_chambers() then asks the docket,
# which gives HB 42 its own ending (CONF_UNABLE).
STAGE_STATED = [
    ("conference report adopted", "Conference committee report adopted"),
    ("conference committee", "In a committee of conference"),
    ("report filed", "Committee report filed"),
]


def stated_stage(st):
    blob = " ".join((st.get(f) or "").lower()
                    for f in ("gen_status", "house_status", "senate_status"))
    return next((label for needle, label in STAGE_STATED if needle in blob),
                None)


STUDY_REPORT = re.compile(
    r"Interim Study Report:\s*(Not\s+)?Recommended for Future Legislation"
    r"[^(]*(?:\(\s*Vote\s*([\d*]+)\s*-\s*([\d*]+))?", re.I)


def study_report(narr):
    """What the committee said about a bill it took for interim study, or None.

    The docket prints one line per report -- "Interim Study Report: Not Recommended
    for Future Legislation 09/02/2026 (Vote 18-0; )" -- and it is the end of that
    bill's story: the committee either asks for the subject to come back as a new
    bill next term or it does not. 10 are on file for 2025-2026 so far and the rest
    arrive through the autumn; 129 in 2023-2024, 134 in 2021-2022. The bill's page
    said nothing about it, which left "Referred for interim study" as the last word
    on bills whose committee had since reported.
    """
    best = None
    for e in (narr or {}).get("events", []) or []:
        raw = (e.get("raw") or "")
        m = STUDY_REPORT.search(raw)
        if not m:
            continue
        rec = {"date": e.get("date", ""), "body": e.get("body", ""),
               "recommended": not m.group(1),
               "vote": (f"{m.group(2)}–{m.group(3)}"
                        if m.group(2) and m.group(3) else "")}
        if not best or (rec["date"] or "") >= (best["date"] or ""):
            best = rec
    return best


# WHAT THE TWO CHAMBERS DID WITH EACH OTHER'S VERSION, from the docket.
#
# The status fields name a stage and stop there: HB 1215 of 2024 has a Senate
# field saying CONFERENCE REPORT ADOPTED and nothing in STATED for the House's
# CONFERENCE REPORT FAILED, so it read "Conference committee report adopted"
# over a docket whose last line is the House voting the report down 102-261.
# CACR 6 and CACR 12 of 2012 have no field saying it at all. And SB 34 of 2026
# read "Passed one chamber" because its Senate field is blank -- the docket has
# the House passing it amended and the Senate refusing to concur.
CONF_REPORT = re.compile(r"conf(?:erence)?\.?\s*comm(?:ittee)?\.?\s*rep(?:ort|t)?\b"
                         r"|committee of conference report", re.I)
# "Failed", and the older dockets' "Fails", "lost" and "defeated": 1999's
# HB 252 "Conf Comm Report Fails DIV(76-210)", 2006's HB 381 "Conf Comm Report
# lost RC(154-175)".
# And the Senate clerk of 2001's "Non Adopt" -- "Conference Committee Report
# RC 11Y-13N, Non Adopt" is SB 95 of 2001, whose report the House had adopted
# 196-159 that morning -- and the House's "Conference Committee Report Not
# Accepted by House pursuant to House Rule 49(j)" (SB 305 of 2016), a report
# filed and never taken up. SB 95 read "One chamber did not concur" and SB 305
# "In a committee of conference", each over a last row that ended it.
CONF_FAILED = re.compile(r"\bfail(?:ed|s)?\b|not adopted|\brejected\b|lacking|"
                         r"\blost\b|\bdefeated\b|\bnon[-\s]?adopt|\bnot\s+accepted\b", re.I)
# A NEW committee of conference -- "New Conf Comm", "New Committee of
# Conference", "new C of C" -- but not "New Conf Comm Report ... MA", which
# is the new conference's report being adopted (SB 140 of 1999).
NEW_CONF = re.compile(r"\bnew\s+(?:conf(?:erence)?\.?\s*comm(?:ittee)?\.?(?!\s*rep)|"
                      r"comm\w*\s+of\s+conf|c\s?of\s?c(?!\s*rep))", re.I)
# The clause about the report ends where the next member's motion starts:
# "Conf Comm Report Adopted RC(190-181); Rep Herman moved to Reconsider, ML".
NEXT_MOTION = re.compile(r";\s*(?:rep|reps|sen|senator)\b|moved to reconsider", re.I)
CONF_REJECTED = "Died when the conference report was rejected"

# CONFEREES WHO COULD NOT AGREE, AND SAID SO. A committee of conference that
# cannot settle the two versions files a report saying it is "unable to agree"
# -- the docket's words from 1989 to 2010 run "CONF COMM REPORT (UNABLE TO
# AGREE) ADOPTED VV" (HB 1181 of 1990), "CONF COMM REPORT (COMM UNABLE TO
# REACH AGREEMENT) SIGNED" (HB 1332 of 1990) and "Conference Committee Report
# 2246; Unable to Reach Agreement, Filed" (HB 431 of 2010) -- and the chambers
# adopt that report, which ends the bill: there is no agreed version left to
# pass. The status fields call it CONFERENCE REPORT ADOPTED, and 69 bills of
# 1989-2010 read "Conference committee report adopted" as though the
# conferees had settled it; every one of their dockets says they could not.
# The House Calendar says it in prose where the committee reported it: "The
# House and Senate members agreed to disagree" (SB 326, 2000).
CONF_UNABLE = "Died: conferees could not agree"
CONF_UNABLE_RE = re.compile(r"\bunable\s+to\s+(?:reach\s+)?agree", re.I)

# AND CONFEREES WHO NEVER SIGNED A REPORT AT ALL. A conference's report is
# signed off by its conferees, and where they did not settle the versions and
# signed nothing, the clerks record that instead:
# "(CONF COMM REPORT NOT SIGNED)" (HB 75 of 2000), "Conference Committee
# Report [Not Signed Off]" (HB 109 of 2003), "Conference Committee; Not
# Signed Off" (HB 1227 of 2004), "Conference Committee Report; Not Signed
# Off" (HB 1323 of 2026); the House's clerk "Conference Committee Report: Not
# Filed" (SB 625 of 2026); and in the oldest docket "NO CONF COMM REPORT
# SIGNED" (HB 575 of 1990) and "DIED IN COMMITTEE OF CONFERENCE" (SB 65 of
# 1989). The status fields stop at CONFERENCE COMMITTEE, NONCONCURRED REQUEST
# CONFERENCE or DIED, SESSION ENDED, so these bills read "In a committee of
# conference", "One chamber did not concur; a committee of conference was
# asked for" or "Died when the session ended", the last on 20 bills of
# 2025-2026 alone. Every such row in the record is about a conference; the
# conference is still named in the pattern, so that a line saying something
# else was not signed never reads as one.
CONF_UNSIGNED_RE = re.compile(
    r"(?:\bconf(?:erence)?|\bc\s?of\s?c)\b.*?\bnot\s+(?:signed|filed)\b"
    r"|\bno\s+conf\w*\.?\s*comm\w*\.?\s*rep\w*\s+signed\b"
    r"|\bdied\s+in\s+(?:the\s+)?comm\w*\s+of\s+conf", re.I)
# A REPORT SIGNED AFTER ALL, too late. HB 1091 of 2026's conferees were "Not
# Signed Off" at the deadline and then filed report 2026-2022c, which the
# Senate adopted the same day; the House refused 180-156 to suspend its rules
# "to consider late sign off report", and the bill died there -- not for want
# of an agreement. HB 1410 of 2002's Senate voted down a motion "To Allow C of
# C Report After Deadline" the day after its "(Conf Comm Report Not Signed)",
# which says a report may have been signed late. Neither is read as conferees
# who could not agree; both keep the label they have.
CONF_LATE_RE = re.compile(
    r"\blate\s+sign\w*[\s-]*off"
    r"|\b(?:c\s?of\s?c|conf\w*\.?\s*comm\w*\.?)\s+rep\w*\s+after\s+(?:the\s+)?deadline", re.I)


FAILURE_RANK = {"unable": 3, "unsigned": 2, "died": 1, "unfiled": 1}


def _failure_how(raw):
    """What a docket row says of a conference that ended without an agreement:
    "unable" (its report said so), "unsigned" or "unfiled" (no report was
    signed, or none filed), "died" (it died there), or None."""
    if CONF_UNABLE_RE.search(raw):
        return "unable"
    m = CONF_UNSIGNED_RE.search(raw)
    if not m:
        return None
    said = m.group(0).lower()
    return ("died" if said.startswith("died") else
            "unfiled" if said.endswith("filed") else "unsigned")


def conference_failure(evs):
    """(how, day) where the bill's last committee of conference ended without
    an agreement, or None. `how` is _failure_how's word for the row; a
    report saying the conferees were unable to agree outranks a note that no
    report was signed, in one conference.

    A new conference formed after it starts again: HB 1210 of 2002's first
    report went unsigned, the chambers formed a new one, and its report
    became Chapter 230. One the other chamber REFUSED leaves the earlier
    conference standing, as conference_outcome reads it (SB 69 of 2001:
    "House Refused to Accede to req for New Conf Comm"). Within one row,
    whichever comes later decides.

    And nothing after it may say the bill went on -- enrolled, to the
    governor, a concurrence that carried -- nor anything in that conference
    say a report was signed after all: a report signed late (CONF_LATE_RE),
    or, where the only word is that none was signed, a chamber voting on one.
    """
    said, start, saved = None, 0, None

    def keep(was, how, i):
        # The conferees' own report of no agreement says the most, and that
        # none was signed says more than that none was filed: HB 243 of
        # 2025's Senate row is "Not Signed Off" and the House's, three weeks
        # later, "Not Filed". Of two rows that say as much, the later.
        if was and FAILURE_RANK[was[0]] > FAILURE_RANK[how]:
            return was
        return how, evs[i].get("date") or "", i

    for i, e in enumerate(evs):
        raw = e.get("raw") or ""
        how = _failure_how(raw)
        hit = (CONF_UNABLE_RE.search(raw) or CONF_UNSIGNED_RE.search(raw)) if how else None
        new = NEW_CONF.search(raw)
        if new and re.search(r"refus", raw, re.I):
            if saved is not None:
                said, start = saved
            new = None
        elif new and not (re.search(r"\bMA\b", raw) or re.search(r"\bacced", raw, re.I)):
            new = None
        if hit and new and hit.start() < new.start():
            said = keep(said, how, i)
            saved, said, start = (said, start), None, i
        elif hit:
            if new:
                saved, said, start = (said, start), None, i
            said = keep(said, how, i)
        elif new:
            saved, said, start = (said, start), None, i
    if not said:
        return None
    how, day, at = said
    later = evs[at + 1:]
    if any(e.get("type") in ("enrolled", "governor") or SIGNED_RE.search(e.get("raw") or "")
           for e in later):
        return None
    went_on = concurrence_outcome(later)
    if went_on and went_on[0] == "con":
        return None
    if any(CONF_LATE_RE.search(e.get("raw") or "") for e in evs[start:]):
        return None
    if how != "unable" and conference_outcome(evs):
        return None
    return how, day


def conferees_disagreed(evs):
    """Whether the bill's last committee of conference ended without an
    agreement, as conference_failure reads it."""
    return conference_failure(evs) is not None


def _conference_vote(said, e, raw, m):
    """One chamber's vote on a conference report, into `said`, from the clause
    that names the report -- not from the whole row, where an MF or ML
    often belongs to another motion."""
    before = raw[:m.start()]
    # A motion ABOUT the report -- to reconsider it, table it, suspend the
    # rules for it -- is not a vote on it, when it is in the same clause as
    # the report's name: "Reconsideration, Conference Committee Report #2089c
    # ...: MF RC 108-247" (SB 135 of 2014) left the adopted report standing.
    if re.search(r"(?:reconsider\w*|susp\w*|table|\bLOT\b)[^;]*$", before, re.I):
        return
    tail = raw[m.start():]
    cut = NEXT_MOTION.search(tail)
    if cut:
        tail = tail[:cut.start()]
    if re.search(r"susp", tail, re.I):
        return
    body = (e.get("body") or "").upper() or "?"
    if CONF_FAILED.search(tail) or re.search(r"\bM[FL]\b", tail):
        said[body] = "failed"
    elif re.search(r"\badopted\b", tail, re.I) or re.search(r"\bMA\b", tail):
        said[body] = "adopted"


def conference_outcome(evs):
    """{chamber: "adopted" | "failed"} -- each chamber's LAST vote on a
    conference report, as veto_outcome reads overrides: a chamber may
    reconsider (SB 14 of 2025 failed 183-186, then carried 185-182).

    A NEW conference asked for or agreed to starts the count again -- but one
    the other chamber REFUSED leaves the rejected report as the last word:
    HB 1211 of 1992 lost its report, the House asked for a new conference and
    the Senate refused to accede. Same-day rows are not reliably in order, so
    either side may come first (HB 723 of 1998 has the House acceding before
    the Senate's request)."""
    said = {}
    saved = None
    for e in evs:
        raw = e.get("raw") or ""
        if NEW_CONF.search(raw) and re.search(r"refus", raw, re.I):
            if saved is not None:
                said = saved
            continue
        ms = list(CONF_REPORT.finditer(raw))
        # The report's vote first: the narrative joins wrapped rows, so one
        # event can carry "REPORT LOST ...; REQ NEW CONF COMM, ... MA".
        if ms:
            _conference_vote(said, e, raw, ms[-1])
        if NEW_CONF.search(raw) and (re.search(r"\bMA\b", raw)
                                     or re.search(r"\bacced", raw, re.I)):
            saved = said if said else saved
            said = {}
    return said


def concurrence_outcome(evs):
    """("non", asked_for_conference) or ("con", False): the last decision on
    concurring with the other chamber's amendment, or None. A motion to
    concur that FAILED is a refusal (HB 1215: 172-180), and a motion to
    non-concur that failed is not one."""
    last = None
    for e in evs:
        raw = e.get("raw") or ""
        low = raw.lower()
        failed = bool(re.search(r"\bM[FL]\b", raw))
        if re.search(r"non-?\s?conc|\bnonc\b|refused to accept|refuses? to concur|"
                     r"refused to concur", low):
            if not failed:
                last = ("non", bool(re.search(r"\bc\s?of\s?c\b|cofc|conf(?:erence)?\b", low)))
        elif re.search(r"\bconc(?:ur\w*)?\b", low) and "enrolled" not in low:
            if failed:
                last = ("non", False)
            elif re.search(r"\bMA\b|\bVV\b", raw):
                last = ("con", False)
    return last


# The labels a later dated docket line is allowed to replace: the stages a bill
# goes THROUGH. An outcome -- killed, tabled, law, vetoed -- is never replaced.
BEFORE_CONFERENCE = {
    "Passed one chamber", "In progress", "In committee", "Retained in committee",
    "Committee report filed", "Passed, awaiting the governor",
    "In a committee of conference", "Conference committee report adopted",
    "One chamber did not concur",
    "One chamber did not concur; a committee of conference was asked for"}
BEFORE_CONCURRENCE = {
    "Passed one chamber", "In progress", "In committee", "Retained in committee",
    "Committee report filed"}
# The labels the conferees' failure replaces: the stages before and in a
# conference -- not "Passed, awaiting the governor", which says the bill went
# on -- and the General Court's DIED, SESSION ENDED, which says only that the
# term ran out where the docket says why the bill did not get there.
BEFORE_UNABLE = (BEFORE_CONFERENCE - {"Passed, awaiting the governor"}) | {
    "Died when the session ended"}
# Any row about a committee of conference: one asked for, acceded to, named,
# meeting, or reporting. "Concur" is not one.
CONFERENCE_ROW = re.compile(r"\bconf(?:erence|eree)|\bc\s?of\s?c\b|\bcofc\b", re.I)


def between_chambers(narr, status):
    """A dated docket answer to what became of the two versions, or None."""
    evs = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
    conf = conference_outcome(evs)
    # NOT WHERE THE REPORT A CHAMBER VOTED DOWN WAS THE CONFEREES' REPORT THAT
    # THEY COULD NOT AGREE. SB 69 of 2001's conferees filed "Conf Comm Report
    # (UNABLE TO AGREE)"; the House adopted that report, the Senate non-adopted
    # it 17-7 and asked for a new conference, and the House refused to accede.
    # No agreed version was rejected: the conferees could not agree, which the
    # test below says.
    unable = (conference_failure(evs) or ("",))[0] == "unable"
    if status in BEFORE_CONFERENCE and "failed" in conf.values() and not unable:
        return "done", CONF_REJECTED
    # A report ADOPTED keeps its label only where the conferees agreed; a
    # conference the fields still call sitting (HB 1323 of 2026), a request
    # for one (HB 291 of 2021) and the term's end (HB 243 of 2025) give way
    # where its conferees reported no agreement or never signed a report.
    if status in BEFORE_UNABLE and conferees_disagreed(evs):
        return "done", CONF_UNABLE
    # A committee of conference the other chamber REFUSED to form never sat:
    # SB 58 of 1990, "HOUSE REFUSED TO ACCEDE", and HB 1432 of 2022.
    if status == "In a committee of conference" and not conf:
        req = [i for i, e in enumerate(evs) if re.search(r"acced", e.get("raw") or "", re.I)]
        if req and re.search(r"refus", evs[req[-1]].get("raw") or "", re.I):
            return "active", ("One chamber did not concur; a committee of "
                              "conference was asked for")
    if status in BEFORE_CONCURRENCE and not conf:
        c = concurrence_outcome(evs)
        if c and c[0] == "non":
            return "active", ("One chamber did not concur; a committee of "
                              "conference was asked for" if c[1]
                              else "One chamber did not concur")
    # AND "DIED, SESSION ENDED" IS THE TERM RUNNING OUT, WHERE THE DOCKET SAYS
    # WHAT STOPPED THE BILL: HB 1768 of 2026 passed the Senate amended and on
    # 21 May the House refused the amendment and asked for no conference,
    # "House Non-Concurs with Senate Amendment 2026-1745s (Rep. Harb): MA VV",
    # its last row. Forty-one bills of that term with the same last row read
    # "One chamber did not concur"; this one read "Died when the session
    # ended", from the House's field. ONLY WHERE NO COMMITTEE OF CONFERENCE
    # WAS EVER ASKED FOR OR FORMED -- no row of the docket names one. HB 751
    # and HB 1709 of 2026 went to a conference whose report the Senate laid on
    # the table, and no vote on a report is what `conf` being empty means for
    # them too: a bill that reached a conference did not end at the refusal.
    if (status == "Died when the session ended" and not conf
            and not any(CONFERENCE_ROW.search(e.get("raw") or "") for e in evs)
            and concurrence_outcome(evs) == ("non", False)):
        return "active", "One chamber did not concur"
    return None


# A resolution the second chamber adopted says so in the docket even where its
# status field does not: HCR 6 of 1990, "S INTRODUCED AND ADOPTED" the day the
# House adopted it, and SCR 3 of 1996, "H ADOPTED DIV(178-116)".
SECOND_ADOPTED = re.compile(r"^\s*(?:introduced and )?adopted\b", re.I)

# What became of a CACR once both chambers passed it is the voters' to say, and
# the docket records their answer for nine of them: "AMENDMENT ADOPTED BY 2/3
# REF(199,229-26,336)" (CACR 23 of 1990) and "Amendment Failed Referendum
# (271,091 - 205,589)" (CACR 5 of 2004). A referendum needs two thirds, so
# "failed" there means it did not reach two thirds, not that most voted no.
REFERENDUM = re.compile(r"\bamendment\s+(?P<how>adopted|failed)\b[^;]{0,20}?\bref(?:erendum)?\b\s*\(",
                        re.I)
# Its own text names the election: "submitted to the qualified voters of the
# state at the state general election to be held in November, 2026".
ELECTION_IN_TEXT = re.compile(r"general election to be held in (?P<month>[A-Z][a-z]+),?\s*(?P<year>\d{4})")
TO_THE_VOTERS = "Passed both chambers, goes to the voters"


def election_day(year):
    """The state general election: the Tuesday after the first Monday in
    November."""
    d = _date(int(year), 11, 2)
    while d.weekday() != 1:
        d += _td(days=1)
    return d


# THE VOTERS' ANSWER WHERE THE DOCKET RECORDS NONE (the person, 5 October
# 2026). The docket stops at the second chamber's vote for the eight CACRs
# sent to the voters since 2006, and they read "went to the voters" with no
# answer. ballot_results.json holds the statewide vote on each of the
# eighteen, read off the source its rows name: a person's file, which no
# build_ or fetch_ script writes (preflight's HANDMADE).
#
# WHOSE COUNT IT IS IS THE ROW'S OWN SOURCE (ballot_source.py). Since 7
# October 2026 that is the Secretary of State for every amendment the voters
# have decided -- its results from 2016, its Manual for the General Court
# before -- with Ballotpedia's figures kept on each row as the cross-check,
# and Ballotpedia for the one still to come. The card, How it got here and
# the note where the docket's own count differs all name it from the row,
# never in words of their own: they said "Ballotpedia" whatever the row said.
#
# THE OUTCOME IS WORKED OUT HERE, NOT READ. An amendment needs two thirds of
# the votes cast on it (Part II, Article 100), and a majority is not that:
# CACR 6 of 2024, the judicial retirement age, won 452,307 to 237,221 --
# 65.6% -- and was not ratified. In whole numbers, so that exactly two
# thirds is two thirds.
BALLOTS = "ballot_results.json"
RATIFIED = "Passed both chambers, ratified by the voters"
NOT_RATIFIED = "Passed both chambers, not ratified by the voters"
ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def ratified(yes, no):
    """Whether the voters ratified an amendment: two thirds of the votes
    cast on it."""
    return yes + no > 0 and 3 * yes >= 2 * (yes + no)


def load_ballots(path, bills):
    """{(term, bill): row} out of ballot_results.json, or {} where it is
    not here.

    Refused where a row names a bill the record does not hold, or one that
    is not a CACR, or one twice; where its day is not a day; or where its
    figures are not two whole numbers, or two nulls for an election still to
    come. A row that matches nothing attaches nothing, and the build would
    exit zero having done it (check_notes)."""
    p = Path(path)
    if not p.exists():
        print(f"  the voters' votes: {path} is not here, so no CACR shows one")
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise SystemExit(f"{path} has no list of rows")
    out, bad = {}, []
    for r in rows:
        key = (r.get("term"), r.get("bill"))
        y, n = r.get("yes"), r.get("no")
        if key[1] not in (bills.get(key[0]) or {}):
            bad.append(f"{key[0]} {key[1]} is not in the record")
        elif not str(key[1]).startswith("CACR"):
            bad.append(f"{key[0]} {key[1]} is not a CACR")
        elif key in out:
            bad.append(f"{key[0]} {key[1]} is named twice")
        elif not (ISO_DAY.match(r.get("election") or "") and ISO_DAY.match(r.get("read") or "")):
            bad.append(f"{key[0]} {key[1]}'s election or read is not a day")
        elif not (y is None and n is None) and not (
                all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in (y, n))
                and y + n > 0):
            bad.append(f"{key[0]} {key[1]}'s yes and no are not two counts")
        elif not str(r.get("source") or "").startswith("https://") or not r.get("label"):
            bad.append(f"{key[0]} {key[1]} names no source or no label")
        else:
            out[key] = r
    if bad:
        raise SystemExit(f"{path}: " + "; ".join(bad))
    done = sum(1 for r in out.values() if r.get("yes") is not None)
    print(f"  the voters' votes: {done} {'amendment' if done == 1 else 'amendments'} "
          f"decided at the polls, {len(out) - done} still to go to them ({path})")
    return out


# What status_source says of a CACR whose voters' answer is a ballot row's
# figures against two thirds: the file the answer came from, which names its
# source on every row.
BALLOT_SOURCE = "ballot_results.json"


def ballot_step(row):
    """The voters' line of a CACR's journey, from its ballot row: the day of
    the election and its outcome, in the words a docket referendum line
    gets -- and whose count it is, by the row's source: "(the Secretary of
    State's count)". How it got here is the docket's list, and this line is
    not the docket's: it stops at the second chamber for every CACR this
    line is drawn for (the review of 5 October 2026)."""
    yes = ratified(row["yes"], row["no"])
    act = "ratified" if yes else "not_ratified"
    return {"date": row["election"], "body": "V", "act": act, "mark": J_MARK[act],
            "text": ("Ratified" if yes else "Not ratified")
            + f", {row['yes']:,}–{row['no']:,} ({BS.whose(row)} count)",
            "short": "ratified" if yes else "not ratified"}


def docket_count_differs(row):
    """What the voters' line of How it got here adds where it is the docket's
    referendum line and the docket's count is not the row's: whose the
    docket's is, and whose the other is, by the row's source. CACR 22 of 1998
    reads "Not ratified, 119,104–159,439 (the docket's count; the Secretary
    of State's is 119,104–169,439)": the docket says 159,439, and the Manual
    it cites prints 169,439."""
    return f" (the docket's count; {BS.whose(row)} is {row['yes']:,}–{row['no']:,})"


def ballot_card(row, narr, today=None):
    """What a CACR's Votes tab draws for the voters: the election, how the
    source lists it, the two counts and the outcome, or only the day where
    the election is still to come. Where the docket prints a referendum
    tally of its own and it is not the source's -- CACR 22 of 1998 reads
    "159,439" against the Secretary of State's 169,439 -- the docket's pair
    goes with it, so the card can say so rather than show one figure and
    print the other a tab away. (CACR 7 of 1992 did too, until 7 October
    2026: its 204,475 was the docket's and the Secretary of State's, and the
    file's 204,457 was Ballotpedia's.)

    WHOSE IT IS, FROM THE ROW (ballot_source.py): `by` begins the card's
    citation, before the row's `cite` -- "Secretary of State, Manual for the
    General Court 1993, p. 442 (NHPR's scan)" -- and `whose` says whose the
    counts above a differing docket's are. app.js named Ballotpedia on every
    card whatever the row's source was.

    AN ELECTION PAST WITH NO COUNT IN THE FILE is `over` as well as pending:
    the status turns to "went to the voters" the day after by itself
    (cacr_to_the_voters), and the card said "The vote is on 3 November" until
    a person typed the counts in (the review of 5 October 2026). `today` is
    the build's day (build_date), as it is there."""
    card = {"date": row["election"], "label": row["label"],
            "source": row["source"], "read": row["read"],
            "by": BS.by(row), "whose": BS.whose(row),
            **({"cite": row["cite"]} if row.get("cite") else {})}
    if row.get("yes") is None:
        over = (today or build_date.today()) > _date.fromisoformat(row["election"])
        return {**card, "pending": True, **({"over": True} if over else {})}
    card.update(yes=row["yes"], no=row["no"], ratified=ratified(row["yes"], row["no"]))
    for e in reversed([e for e in (narr or {}).get("events", []) if not e.get("cancelled")]):
        raw = e.get("raw") or ""
        m = REFERENDUM.search(raw)
        if not m:
            continue
        t = J_REF_TALLY.search(raw, m.end() - 1)
        if t:
            said = [int(t.group(1).replace(",", "")), int(t.group(2).replace(",", ""))]
            if said != [row["yes"], row["no"]]:
                card["docket"] = said
        break
    return card


def cacr_to_the_voters(narr, term, current, text="", today=None, ballot=None):
    """What a CACR both chambers passed now says, in the tense the record
    allows: the voters' answer where the docket records it, or where
    ballot_results.json does (`ballot`, its row); past tense for a closed
    term; for the current term, the election its own text names, in the
    future tense until that day."""
    for e in reversed([e for e in (narr or {}).get("events", []) if not e.get("cancelled")]):
        m = REFERENDUM.search(e.get("raw") or "")
        if m:
            return (RATIFIED if m.group("how").lower() == "adopted" else NOT_RATIFIED)
    if ballot and ballot.get("yes") is not None:
        return RATIFIED if ratified(ballot["yes"], ballot["no"]) else NOT_RATIFIED
    m = ELECTION_IN_TEXT.search(text or "")
    if term != current:
        return "Passed both chambers, went to the voters"
    if not m:
        return TO_THE_VOTERS
    when = f"{m.group('month')} {m.group('year')}"
    over = (today or build_date.today()) > election_day(m.group("year"))
    return (f"Passed both chambers, went to the voters in {when}" if over
            else f"Passed both chambers, goes to the voters in {when}")


# THE 2020 SENATE LEFT 427 BILLS ON THE TABLE, and its Rule 3-23 killed them at
# adjournment: every one's last docket line is "Inexpedient to Legislate,
# Senate Rule 3-23, Adjournment 09/16/2020", while its status field still said
# LAID ON TABLE. The site already called this ending "Died on the table" on 211
# bills whose last line is the same, 164 of them in other terms (2015-2016 to
# 2023-2024) and 47 in 2019-2020 itself.
#
# THE 2025 ROW HAS NO "ADJOURNMENT": "Inexpedient to Legislate, Senate Rule
# 3-23, 10/31/2025". The rule is named, and that is what the row is.
TABLE_DEATH = re.compile(r"inexpedient to legislate,\s*senate\s+rule\s+3-23\b", re.I)
# AND THE HOUSE'S OWN CLOSING ROW. The House laid 26 measures of 2015 on the
# table and entered "Died on the Table" on each on 18 November 2015; its field
# for them was never advanced from LAID ON TABLE, a field outranks what
# classify() reads in the docket, and they read "Laid on the table" over a
# last row that says they died there.
DIED_ON_TABLE_ROW = re.compile(r"^\s*died\s+on\s+(?:the\s+)?table\b", re.I)


# ---- the database's status codes, where the status page states nothing ------
#
# bill_status.json is the status pages, and they leave fields blank: of the
# 2,243 records of 2025-2026, 577 have no general status there, 311 no House
# status and 121 no Senate status. The General Court's own database has a
# code in every one of those columns, and its dump is on this disk
# (db/Legislation.psv, read with GeneralCodes.txt and BodyStatusCodes.txt; no
# network). HB 1708 and HB 1824 of 2026 were reported to the floor, met a
# failed motion to take them up at once, and were never voted on: the
# database says DIED, SESSION ENDED for each, the page says nothing, and they
# read "In committee".
#
# FILLED, NEVER REPLACED. The dump is older than the pages and behind them
# where both have a value -- HB 592 of 2025 reads NO ACTION in the Senate
# there and is Chapter 3 -- so a field the page filled is left exactly as it
# is.
#
# AND IT ANSWERS ONLY WHERE THIS SITE WOULD OTHERWISE GUESS (bill_disposition:
# the page's fields state nothing, and the docket gives classify() nothing
# better than "In committee" or "In progress"). A database code beside a page
# field that already answers would outrank it by STATED's order alone: HB 751
# and HB 1709 of 2026 are LAID ON TABLE on the page's Senate field, which is
# what their dockets end on, and the database's House code for both is DIED,
# SESSION ENDED. A reading of the docket's own decisions outranks it too --
# CACR 10 of 2026 lost its vote, and the database says DIED, SESSION ENDED --
# and so does every dated row that outranks a page field: a refusal to
# concur, a conference's outcome. And a code the bill's own journey
# contradicts is not taken: the database is stale on some bills (SB 532 of
# 2026 reads IN COMMITTEE and was killed 16-8), and "In committee" over a
# chamber's passage would be worse than the guess.
#
# The page's table of the General Court's fields still shows what the status
# page says, and the status's source is "General Court database".
DB_LEGISLATION = Path("db") / "Legislation.psv"
DB_STATUS_COLUMNS = {"sessionyear": 2, "lsr": 3, "CondensedBillNo": 14,
                     "HouseStatusCode": 21, "SenateStatusCode": 29, "GeneralStatusCode": 34}
_DB_STATUS = {}


def _status_codes(path):
    """GeneralCodes.txt or BodyStatusCodes.txt: {"31": "DIED, SESSION ENDED"}."""
    out = {}
    try:
        for line in Path(path).open(encoding="utf-8-sig", errors="replace"):
            p = line.rstrip("\n").split("|")
            if len(p) >= 2 and p[0].strip():
                out[p[0].strip()] = p[1].strip()
    except OSError:
        pass
    return out


# A TERM'S ROWS, WHEREVER THEY ARE, AND NOT "THE CURRENT TERM'S". The dump is
# read by each row's own session year, and a term whose views the General
# Court has turned over to the next is read from the copy frozen at its end
# (db/term/<term>/Legislation.psv, with the _columns.json it was dumped with:
# cloud_kit.json's "frozen" list, which build_bill_versions.py reads the same
# way). The first version of this answered only for the term that was current
# on the night of the build, so on the first night of 2027-2028 the five
# records it settles -- HB 1708 and HB 1824 of 2026, HCR 1, HCR 4 and HCR 9 of
# 2025 -- would have gone back to "In committee" and "In progress", in a term
# by then finished, with nothing failing. Where both hold a measure the
# current dump is the later word, and is read last.
DB_FROZEN = Path("db") / "term"


def db_statuses(term, folder="."):
    """{BILL: {"lsr", "gen_status", "house_status", "senate_status"}} for the
    measures of `term` in the database dump under `folder` -- the term's own
    frozen copy, then the current dump -- in the status page's own words; {}
    where no dump holds the term or a code table is not there."""
    folder = Path(folder)
    gen = _status_codes(folder / "GeneralCodes.txt")
    body = _status_codes(folder / "BodyStatusCodes.txt")
    out = {}
    if not (gen and body):
        return out
    for dump in (folder / DB_FROZEN / term, folder / "db"):
        at = dict(DB_STATUS_COLUMNS)
        for cols_at in (dump / "_columns.json", folder / "db" / "_columns.json"):
            try:
                cols = json.loads(cols_at.read_text(encoding="utf-8")).get("Legislation") or []
            except (OSError, ValueError):
                continue
            at.update({n: cols.index(n) for n in at if n in cols})
            break
        try:
            fh = (dump / DB_LEGISLATION.name).open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                f = line.rstrip("\n").split("|")
                if len(f) <= max(at.values()):
                    continue
                year = f[at["sessionyear"]].strip()
                if not year.isdigit() or P.term_of(year) != term:
                    continue
                out[f[at["CondensedBillNo"]].strip().upper()] = {
                    "lsr": f[at["lsr"]].strip().lstrip("0"),
                    "gen_status": gen.get(f[at["GeneralStatusCode"]].strip(), ""),
                    "house_status": body.get(f[at["HouseStatusCode"]].strip(), ""),
                    "senate_status": body.get(f[at["SenateStatusCode"]].strip(), "")}
    return out


def terms_without_a_dump(bills, pages):
    """[(term, its measures whose status page states nothing)] for each of
    the two newest terms that has such measures and that no database dump
    holds.

    THE NIGHT THE GENERAL COURT'S VIEWS TURN OVER, the dump on disk holds the
    new term and, unless a copy was frozen under db/term/, nothing holds the
    one just finished: HB 1708 and HB 1824 of 2026 and HCR 1, HCR 4 and HCR 9
    of 2025 go back to "In committee" and "In progress". The build asked only
    about the newest term, which the new dump answers, and said nothing; the
    check that asks about both (preflight's "a database dump on this disk
    holds each of the two newest terms ...") is a data check, which the night
    does not run. main() says this as its last lines.
    """
    if not bills:
        return []
    current = max(bills)
    fields = ("gen_status", "house_status", "senate_status")
    out = []
    for term in sorted(bills)[-2:]:
        page = P.per_term(pages, term, current)
        blank = sorted(b for b, rec in bills[term].items()
                       if not any(((page.get(b) or {}).get(f) or rec.get(f) or "").strip()
                                  for f in fields))
        if blank and no_dump_for(term):
            out.append((term, blank))
    return out


def no_dump_for(term):
    """What to say of a term no database dump holds, or "" where one does."""
    if not term:
        return ""
    if term not in _DB_STATUS:
        _DB_STATUS[term] = db_statuses(term)
    if _DB_STATUS[term]:
        return ""
    return (f"NO DATABASE DUMP HOLDS {term} ({DB_LEGISLATION.as_posix()}, or "
            f"{(DB_FROZEN / term / DB_LEGISLATION.name).as_posix()}): a bill of it whose "
            "status page states nothing keeps what the docket alone gives it")


def fill_status_from_db(st, b, bid, term, current, db=None):
    """The status page's record with each field it left blank taken from the
    database's row for the same measure, or None where there is nothing to
    fill: no dump holding the measure's term, no row for this bill and this
    LSR, or no blank the database has a word for. `current` is not asked:
    a term is read from whichever dump holds its rows (db_statuses)."""
    if db is None:
        if term not in _DB_STATUS:
            _DB_STATUS[term] = db_statuses(term)
        db = _DB_STATUS[term]
    row = db.get(str(bid).upper())
    if not row or row["lsr"] != str((b or {}).get("lsr_num") or "").lstrip("0"):
        return None
    fill = {k: row[k] for k in ("gen_status", "house_status", "senate_status")
            if row.get(k) and not ((st or {}).get(k) or "").strip()}
    return {**(st or {}), **fill} if fill else None


# ---- a measure of a finished term cannot still be moving ---------------------
#
# Where every narrower reading has had its say and a measure of a finished
# term still carries a word for a stage it was at -- "In committee",
# "Committee report filed", "In a committee of conference", "Passed one
# chamber" -- the stage is where it died, and the site's words for that are
# "Died when the session ended": the General Court's own code for the same
# end on the bills beside them. 71 House measures of 2021 were reported out
# of committee and never voted on before the House's deadline of 9 April
# 2021; the code on each is MISCELLANEOUS, and they read "In committee" or
# "Committee report filed", five years on. HB 1716 and HB 2020 of 2020 and 75
# House bills of 2026, with the same docket, are coded DIED, SESSION ENDED.
#
# IT SAYS NO MORE THAN THE RECORD DOES, so each label has its own test:
#
#   - "In committee", "In progress", "Committee report filed", "Retained in
#     committee": only where a chamber's field is MISCELLANEOUS or RECOMMIT,
#     the General Court's own word that no ordinary disposition was reached.
#     A docket that ends on a committee report with no floor row is also what
#     a consent-calendar vote the clerk did not itemise looks like (HB 1154
#     of 2022 reads "Killed" only because its field says so), so the absence
#     of a row is not enough. Not where the general status is PASSED over it
#     (HB 160 of 2021: the two records disagree), and not where the chamber
#     refused to consider the measure ("Shall House Consider: MF", HB 520 of
#     2017), which is a decision this site has no word for yet.
#   - "In a committee of conference": only where the docket says a chamber
#     would not take the conference's report up -- a report after the
#     deadline (CONF_LATE_RE: HB 1410 of 2002), or a vote to suspend the rules
#     for the report that failed ("MOVED TO SUSP RULES FOR CONF COMM REPT,
#     FAILED 2/3RC(185-133)", SB 437 of 1998). It is the shape the General
#     Court codes DIED, SESSION ENDED on HB 1091 of 2026. A conference with
#     no row after it formed is left: nothing says whether it reported --
#     EXCEPT WHERE THE HOUSE JOURNAL DOES (CONFERENCE_NOT_REPORTED, below).
#   - "Passed one chamber": only a bill or joint resolution with no row of
#     the other chamber at all (HB 462 of 1989, HB 1027 of 1992, SSSB 1 of
#     2008). One the other chamber refused, returned or held in committee has
#     a row that says more, and a concurrent resolution's refusal by the
#     Senate is not always in its docket.
#
# AND NOT THE ONES THE RECORD DOES NOT SETTLE, held at their last word until a
# person decides. Each was read against everything on disk on 2 October 2026.
ENDING_NOT_ON_RECORD = {
    ("2015-2016", "HB1702"): "one row, \"Introduced and Adopted\", on 1 June 2016; the "
                             "database gives a Senate introduction that day and no docket "
                             "row says what the Senate did",
    ("2015-2016", "HB1703"): "one row, \"Introduced and Adopted: MA RC 314-25\", on 1 June "
                             "2016; as HB 1702",
    ("2019-2020", "HB1717"): "passed the House 243-92 on 11 June 2020 and has no Senate row",
    # Not a bill that ran out of time: its one row of passage ends "(See SR
    # 9)", and SR 9 of 1999 carries the same title and was adopted by the
    # Senate on 29 June 1999. "It would have to be filed again as a new bill
    # in a later term" was said of a measure the Senate redid as its own
    # resolution three months later.
    ("1999-2000", "SB23"): "passed the Senate on 17 March 1999, \"(See SR 9)\"; the Senate "
                           "adopted SR 9, of the same title, on 29 June 1999, and no House "
                           "row follows",
}

# THREE CONFERENCES THE HOUSE JOURNAL SAYS NEVER REPORTED. HB 430, HB 564 and
# HB 723 of 1997 each went to a committee of conference at the end of May
# 1997 (HB 723 to a second one, on 10 June), and the docket of each stops at
# a conference meeting. The House Journal of the last day of that session
# prints, under OUTSTANDING BILLS: "The customary end-of-session motion to
# dispose of outstanding bills was not entertained. The bills that would
# have been affected by that motion are those bills not reported by
# Committees of Conference (HB 430, HB 564, HB 723 and SB 216) and those
# bills Laid on the Table (HR 19)" (journals/1997/HJ025.txt, lines 542-546).
# Nothing follows on any of them in 1998. They read "In a committee of
# conference", twenty-nine years on. SB 216, the fourth, carries its own row
# "(CONFEREES UNABLE TO AGREE)" and reads "Died: conferees could not agree";
# these three have no such row, so they take the words for a measure that did
# not finish, and the paragraph says what the journal says. A TABLE OF WHAT
# WAS READ, as narrative.INTRODUCED_ON is, and preflight reads the journal
# again where it is on disk. The ten other conferences with no row after
# they formed have no such word anywhere on disk, and are left.
CONFERENCE_NOT_REPORTED = {
    ("1997-1998", b): "the House Journal of the 1997 session's last day lists it among the "
                      "bills \"not reported by Committees of Conference\""
    for b in ("HB430", "HB564", "HB723")}

# AND SIX WHOSE DOCKET'S OWN LAST ROW IS THE SESSION'S END, AFTER A VOTE THEY
# LOST: "Died, Session ended 10/10/2024" on CACR 15, 17, 19, 22 and 23 of
# 2024, and "Died, Session Ended" on SSSB 1 of the 2010 special session. The
# rule that a lost vote is the outcome (bill_disposition) would call each
# "Failed to pass"; the General Court's row calls it the session's end. Both
# are true, the sweep of 2 October 2026 left the choice to a person, and
# until one is made these keep the row's word. BY NAME, not by "the docket
# has such a row": by that test CACR 8 of 2025 and CACR 9, 11, 12 and 18 of
# 2026 read "Failed to pass" only until the House's clerk enters the closing
# rows -- on 10 October, in 2024 -- and then changed back, on the live site,
# with nobody having decided it.
SESSION_ENDED_STANDS = {("2023-2024", f"CACR{n}") for n in (15, 17, 19, 22, 23)} | {
    ("2009-2010", "SSSB1")}
UNFINISHED = {"In committee", "In progress", "Committee report filed", "Retained in committee"}
NO_DISPOSITION = {"MISCELLANEOUS", "RECOMMIT"}
CONSIDERATION_REFUSED = re.compile(
    r"^\s*shall\s+(?:the\s+)?(?:house|senate)\s+(?:now\s+)?consider\b", re.I)
CONF_NOT_TAKEN_UP = re.compile(
    r"\bsusp\w*\.?\s+rules?\s+for\s+(?:the\s+)?conf\w*\.?\s*comm\w*\.?\s*rep\w*\s*,\s*"
    r"(?:failed|fails|ML\b|MF\b)", re.I)
ENDED_WITH_TERM = "the term's end"


def conference_not_taken_up(evs):
    """The docket row that says a chamber would not take the conference's
    report up -- a report after the deadline, or a failed vote to suspend the
    rules for it -- or None."""
    return next((e for e in evs if CONF_LATE_RE.search(e.get("raw") or "")
                 or CONF_NOT_TAKEN_UP.search(e.get("raw") or "")), None)


def ended_with_the_term(status, st, narr, bid, term):
    """Whether a measure of a finished term, still carrying `status` after
    every other rule, died where it stood when the term ended -- by the tests
    above. The caller asks it only of a finished term."""
    if (term, bid) in ENDING_NOT_ON_RECORD:
        return False
    prefix = bill_prefix(bid)
    evs = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
    said = [((st or {}).get(f) or "").strip().upper()
            for f in ("gen_status", "house_status", "senate_status")]
    if status in UNFINISHED:
        if said[0] == "PASSED" or not set(said[1:]) & NO_DISPOSITION:
            return False
        return not any(CONSIDERATION_REFUSED.search(e.get("raw") or "") for e in evs)
    if status == "In a committee of conference":
        return (term, bid) in CONFERENCE_NOT_REPORTED or conference_not_taken_up(evs) is not None
    if status == "Passed one chamber":
        if prefix in NO_GOVERNOR or prefix in SINGLE_CHAMBER:
            return False
        own = origin_of(bid, narr, st)
        return bool(evs) and not any(
            (e.get("body") or "").upper()[:1] in ("H", "S")
            and (e.get("body") or "").upper()[:1] != own for e in evs)
    return False


def bill_disposition(b, bid, st, narr, rcs, term, current, law_line="",
                     override_failed="", term_over=False, text="", today=None,
                     db_st=None, ballot=None):
    """What became of this bill, and where that answer came from.

    The two counters the build reports at the end leave as data rather than
    as side effects on an enclosing scope. The caller does
        n_stated += d.stated
        n_stale  += d.stale
    which is the same arithmetic written where it can be seen.

    Returns a namedtuple rather than a tuple: this has seven fields
    and positional unpacking of seven things is the shape of the bug
    build_bills' own docstring is about.

    law_line is the docket line that numbered the bill's chapter, from
    extract_chapters. A term whose docket is not narrated has no events for
    docket_outcome to read, but it has that line, and it is the same
    evidence: HB 1075 of 1998 -- the ABC plan, "SIGNED BY GOVERNOR 10/01/98
    ... CHAP.0389" -- read "In committee", because its status fields stop at
    CONFERENCE REPORT ADOPTED, which nothing in STATED names.

    override_failed is the same kind of line for a veto that stood: HB 149
    of 1997, "OVERRIDE GOV VETO, ML RC(17-299)", read "Vetoed, awaiting an
    override vote" because its fields stop at VETOED BY GOVERNOR.

    db_st is the status page's record with its blanks filled from the
    database (fill_status_from_db), or None. It is asked only where nothing
    else answers.

    ballot is a CACR's row of ballot_results.json, or None: the voters'
    answer where the docket records none (cacr_to_the_voters).
    """
    stated = stale = 0
    source = ""
    between = None
    # A dated docket line decided the status over a field that says otherwise,
    # where between_chambers() below did not: for status_source.
    from_docket = False
    prefix = bill_prefix(bid)
    told = classify_stated(st, prefix, origin_of(bid, narr, st))
    # A STATUS FIELD DOES NOT INTRODUCE A BILL THE HOUSE JOURNAL LEAVES OUT.
    # HB 177, HB 273, HB 274 and HB 277 of 2017 are records of the bill
    # search's own list, and its House status for each is IN COMMITTEE: the
    # field that goes with the row typed ahead of 4 January 2017, on bills the
    # House's resolution of that day steps over and no committee was sent
    # (build_data.INTRODUCTION_FROM_JOURNAL). The three of 2007 and 2009 carry
    # no such field, so classify() answered for them; these four read "In
    # committee", from the field. Where the history says the journal decided,
    # the field is not asked, here or for the status box (bill_next_step).
    if told and journal_not_introduced(narr):
        told = None
    settled = docket_outcome(narr)
    # THE DOCKET LINE THAT NUMBERED THE CHAPTER, OR RECORDED A FAILED
    # OVERRIDE, COUNTS WHENEVER THE HISTORY ITSELF SAYS NOTHING -- not only
    # when there is no history at all. Gated on "no narrative" it switched
    # itself off the moment the archived terms were narrated, and nine bills
    # of 1997-1998 went back from "Vetoed, override failed" to "Vetoed"
    # because their own wording ("OVERRIDE GOV VETO, ML") is not one
    # docket_outcome reads.
    if not settled and law_line:
        settled = docket_outcome({"events": [{"raw": law_line}]})
    if not settled and override_failed:
        settled = ("veto", "Vetoed, override failed")
    # A VETO ONE CHAMBER HAS OVERRIDDEN IS STILL A VETO. An override needs
    # two-thirds in both, and veto_outcome answers "Veto overridden, became
    # law" on the first chamber's vote. The House overrode HB 1102 of 2026 at
    # 11.23 on 19 August and the Senate at 3.24; the Senate overrode SB 91 of
    # 2011 on 7 September and the House on 12 October. A build between the
    # two would have called each law. With one chamber's
    # override, no other chamber's vote and no chapter line, the vote is
    # pending, and once the session is over the veto stood (below). A chapter
    # line is the law: SB 153 of 2000 and HB 724 of 2003 word their second
    # override "= VETO OVERRIDE=" and "Veto Override", and each has one.
    if (settled == ("law", "Veto overridden, became law") and not law_line
            and set(veto_votes([e for e in (narr or {}).get("events", [])
                                if not e.get("cancelled")])) in ({"H"}, {"S"})):
        settled = ("veto", "Vetoed, override vote pending")
    # A BILL THE GENERAL COURT'S FILES DO NOT CARRY, whose record is the House
    # Journal's (build_data.add_journal_bills): introduced, and withdrawn. No
    # docket, no status page and nothing else says otherwise, because nothing
    # else has it; were any of them to, this would give way to it.
    if (b or {}).get("journal", {}).get("withdrawn") and not (settled or told or narr):
        return Disposition("done", "Withdrawn", told, settled, prefix,
                           0, 0, False, JOURNAL_SOURCE)
    # AND THE ONE WHOSE JOURNAL RECORD IS A VOTE ON ITS COMMITTEE'S REPORT
    # (journal_bills.EARLIER: HB 459 of 2021, Inexpedient to Legislate adopted
    # 198-153). The report's recommendation, adopted, is the decision DISPOSED
    # names for the docket's own floor rows. Where its docket is on this
    # machine (the past docket view) the history is narrated and this gives
    # way to it, as above; the two say the same thing.
    _dec = (b or {}).get("journal", {}).get("decided") or {}
    if _dec.get("carried") and not (settled or told or narr):
        _hit = next((res for pat, res in DISPOSED
                     if pat.search(_dec.get("question") or "")), None)
        if _hit:
            return Disposition(_hit[0], _hit[1], told, settled, prefix,
                               0, 0, False, JOURNAL_SOURCE)
    disposed = floor_disposed(narr)
    if settled:
        # A dated docket line beats a status field that has not caught up.
        kind, status = settled
        stated = 1
    elif told and disposed and (told[0] == "active"
                                or told[1] == "Died when the session ended"):
        # A bill cannot be "In committee" after the chamber adopted a
        # motion to kill it. The status columns are not always advanced
        # once a bill is finished -- 21 of them still read REPORT FILED or
        # NO ACTION on bills signed into law -- and an in-progress status
        # is the one case where a dated floor vote is plainly later than
        # the field. Only "active" yields; a stated outcome still wins.
        #
        # AND "DIED, SESSION ENDED" IS NOT AN OUTCOME WHERE THE CHAMBER KILLED
        # IT. Eleven CACRs the House killed in the first year of 2023-2024 or
        # of 2025-2026 read that way -- CACR 1 of 2025 among them,
        # "Inexpedient to Legislate: MA VV 03/26/2025" -- where the ones it
        # killed in the second year say INEXPEDIENT TO LEGISLATE. The page
        # then said "No vote was ever taken on it" over the docket's vote.
        kind, status = disposed
        stated = 1
    elif (told and told[1] == "Died when the session ended"
          and (term, bid) not in SESSION_ENDED_STANDS
          and (last_decision(narr, bid, rcs, term) or {}).get("act") == "failed"):
        # AND "DIED, SESSION ENDED" IS NOT THE OUTCOME WHERE THE LAST DECISION
        # WAS A VOTE THE MEASURE LOST, for the reason above. Which word a
        # constitutional amendment that fell short of three fifths carried
        # depended on the code the clerk typed: CACR 4, 10, 14, 15, 21 and 24
        # of 2026, with a blank or MISCELLANEOUS field, read "Failed to pass",
        # and CACR 9 and CACR 18 of the same term, CACR 2 and CACR 7 of 2023
        # and CACR 9 of 2019, the same docket under DIED, SESSION ENDED, read
        # "Died when the session ended" over a page saying no chamber had
        # voted on them. So do CACR 8 of 2025 and CACR 11 and CACR 12 of 2026,
        # which passed the Senate and lost in the House.
        # NOT THE SIX HELD FOR A PERSON (SESSION_ENDED_STANDS): CACR 15, 17,
        # 19, 22 and 23 of 2024 and SSSB 1 of 2010, whose docket's own last
        # row is the session's end.
        kind, status = "done", "Failed to pass"
        stated = 1
        from_docket = True
    elif told:
        kind, status = told
        stated = 1
    else:
        kind, status = classify(narr, rcs, prefix, bid, term)
        # classify's last two answers, "In committee" and "In progress", are
        # this site's words for a bill it knows nothing more about. Where
        # the status fields name a stage STATED has no entry for, that is
        # something more: 495 bills of closed terms read "In committee" or
        # "In progress" over fields saying REPORT FILED (the committee had
        # reported), CONFERENCE COMMITTEE or CONFERENCE REPORT ADOPTED. Not
        # added to STATED, where it would also outrank a docket's "Killed"
        # or a CACR's "goes to the voters": measured that way it overrode
        # "Killed" on 20 narrated bills. Here it replaces only the guess.
        if status in ("In committee", "In progress"):
            said = stated_stage(st)
            if said:
                status = said
    # A TERM THAT HAS ENDED HAS NO BILLS IN PROGRESS. The General Court's
    # status field stops being updated when a term closes, so 1,954
    # archived bills across eighteen terms still say "In committee",
    # "Laid on the table" or "Passed one chamber" -- 608 of them in
    # committee, some since 1989. Read literally that is a 37-year-old
    # bill awaiting a hearing.
    #
    # The word is left exactly as the record gives it, because it is what
    # the record last said and this site does not rewrite that. What
    # changes is the KIND, which drives the colour and the rail: in a
    # closed term the bill did not go on from there, so it is finished
    # rather than moving. The current term is untouched -- a bill laid on
    # the table in 2026 may yet be taken up -- UNTIL THE TERM RUNS OUT OF
    # SESSION DAYS, which status/status.txt states as session_over: with no
    # session days left, every bill has concluded, tabled ones included. 107
    # bills of 2025-2026 were still counted as moving, 50 of them laid on the
    # table and 46 where one chamber had not concurred, and the home page
    # called them moving while the status box said the session was finished. The
    # docket records "Died on Table, Session ended" for these, but not until
    # the General Court closes the term -- 10 October last term -- so the site
    # would have said it for another month.
    #
    # A DATED DOCKET LINE BETWEEN THE CHAMBERS outranks a field that stopped
    # at an earlier stage -- the rule docket_outcome already applies to the
    # governor, and floor_disposed to a chamber's own kill. It replaces only a
    # stage, never an outcome, and it does not make the bill "settled": SB 34
    # of 2026's box would then read "Pending action in the other chamber".
    # `between` carries the fact that the docket decided, for status_source.
    if not settled:
        between = between_chambers(narr, status)
        if between:
            kind, status = between
            stated = 1
        elif prefix in NO_GOVERNOR and status == "Passed one chamber":
            org = origin_of(bid, narr, st)
            evs2 = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
            if any((e.get("body") or "").upper()[:1] not in ("", org)
                   and SECOND_ADOPTED.search(e.get("raw") or "")
                   and not re.search(r"\bam\b|amend", e.get("raw") or "", re.I)
                   for e in evs2):
                between = ("adopted", TO_THE_VOTERS if prefix == "CACR"
                           else "Adopted by both chambers")
                kind, status = between
        elif status == "Laid on the table":
            # The last row that is an action on the bill: a clerk's note
            # entered after the closing row (CLERKS_NOTE) is not one, and
            # with it last the bill stayed "Laid on the table" under a field
            # that had stopped at LAID ON TABLE.
            evs2 = [e for e in (narr or {}).get("events", [])
                    if not e.get("cancelled") and not CLERKS_NOTE.match(e.get("raw") or "")]
            if evs2 and (TABLE_DEATH.search(evs2[-1].get("raw") or "")
                         or DIED_ON_TABLE_ROW.search(evs2[-1].get("raw") or "")):
                between = ("done", "Died on the table")
                kind, status = between
        # "PASSED/ADOPTED" IN BOTH CHAMBERS' FIELDS IS NOT ONE CHAMBER. HB 549
        # of 1991, SB 1 of 2005 and HB 1534 of 2016 read "Passed one chamber"
        # where the House's field and the Senate's each say PASSED/ADOPTED,
        # one of them WITH AMENDMENT, and their dockets agree: the second
        # chamber passed it amended and the first never took the amendment
        # up. In a closed term that is a bill that died when the session
        # ended, the General Court's own words for the same end on 41 others.
        elif (status == "Passed one chamber" and prefix not in NO_GOVERNOR
              and prefix not in SINGLE_CHAMBER and (term != current or term_over)
              and all((st.get(f) or "").strip().lower().startswith("passed/adopted")
                      for f in ("house_status", "senate_status"))):
            kind, status = "done", "Died when the session ended"
    # AND THE DATABASE'S OWN CODE, where after all of that the status is
    # still classify()'s guess (see fill_status_from_db). Not a code the
    # bill's journey contradicts.
    if status in ("In committee", "In progress") and db_st and not (settled or told):
        said = classify_stated(db_st, prefix, origin_of(bid, narr, db_st))
        if said and not journey_disagrees(
                journey(narr, bid, rcs, term=term)[1], said[0], said[1], "", bid):
            kind, status = said
            told, stated, source = said, 1, PAST_SOURCE
    if status == TO_THE_VOTERS:
        status = cacr_to_the_voters(narr, term, current, text, today, ballot)
    # A MEASURE OF A FINISHED TERM CANNOT STILL BE MOVING (ended_with_the_term).
    # The word is this site's reading and no field's, so no field is named as
    # having stated it.
    if (term != current or term_over) and not settled and ended_with_the_term(
            status, st, narr, bid, term):
        kind, status = "done", "Died when the session ended"
        told, stated, source = None, 0, ENDED_WITH_TERM
    if kind == "active" and (term != current or term_over):
        kind = "done"
        stale = 1
    # The veto labels are the one place the words themselves are this
    # site's and say the bill is still waiting. "Awaiting an override vote"
    # expands VETOED BY GOVERNOR; in a closed term nothing is awaited, and
    # the veto stood -- whether or not a vote was ever taken, which the
    # record does not always say (HB 1407 of 1992 has no override line at
    # all). So a closed term says what the field says, and so does the
    # current one once its session is over: "awaiting an override vote"
    # beside a chip saying Died was each contradicting the other.
    if (kind == "veto" and (term != current or term_over)
            and status in ("Vetoed, awaiting an override vote",
                           "Vetoed, override vote pending")):
        status = "Vetoed"
    return Disposition(kind, status, told, settled, prefix,
                       stated, stale, bool(between) or from_docket, source)


def bill_documents(b, bid, st, narr, sources, rep_written, rep_docket):
    """Everything a reader can open for themselves, deduped on the URL.

    add_doc was defined once per bill inside a 465-line body; it is a
    nested helper of a 60-line function now, which is what a closure
    that small should be.

    Its third parameter is named `sort` rather than `kind`, so that no
    binding called `kind` exists in this scope at all. `kind` means the
    bill's status kind in the caller, and the last thing this refactor
    should do is create a fresh instance of the shadowing it is here
    to remove.

    Returns (docs, text_url): the text URL is built here and the caller
    needs it for the payload as well.
    """
    docs, seen_doc = [], set()

    def add_doc(label, url, sort):
        if url and url not in seen_doc:
            seen_doc.add(url)
            docs.append({"label": label, "url": url, "kind": sort})

    text_url = bill_text_url(b, st)
    add_doc("Bill text", text_url, "text")
    # NOT FOR A JOURNAL RECORD. Both addresses are built from the LSR, which a
    # bill read off the House Journal does not have (add_journal_bills says
    # why none is invented). Whether the General Court's own pages have the
    # bill is not known here: its data files do not, and no page was asked.
    if not b.get("journal"):
        add_doc("Bill status page", (
            "https://gc.nh.gov/bill_status/legacy/bs2016/Bill_status.aspx"
            f"?lsr={b.get('lsr_num','')}&sy={b.get('lsr_year','')}"
            f"&txtsessionyear={b.get('lsr_year','')}"
            f"&txtbillnumber={bid.lower()}&sortoption=billnumber"), "status")
        add_doc("Docket", (
            "https://gc.nh.gov/bill_status/legacy/bs2016/bill_docket.aspx"
            f"?lsr={b.get('lsr_num','')}&sy={b.get('lsr_year','')}"
            f"&txtsessionyear={b.get('lsr_year','')}"
            f"&txtbillnumber={bid.lower()}&sortoption=billnumber"), "docket")
    # The journals and calendars the docket itself cites. These are the
    # official record of the individual actions, which is a stronger thing
    # to link than a summary of them.
    # One entry per volume, naming every page of it this bill is on.
    # add_doc dedupes on the URL, and a volume has one URL however many
    # pages are cited -- so listing them per event kept whichever page came
    # first and dropped the rest without a word. 565 of the 7,013 volumes
    # cited on this site carry a bill on more than one page; HB686 is on
    # HJ 7 at both 143 and 144, and the list named only 143.
    vols = {}
    for e in (narr or {}).get("events", []):
        # Not a row the docket cancelled. A notice a later row cancelled or
        # moved (narrative.overtaken) is carried as cancelled so that nothing
        # reads it as a sitting, but the calendar it cites printed the bill:
        # Senate Calendar 1A of 2006 printed SB 339's hearing of 19 January,
        # and the Documents tabs of 59 bills lost 62 calendars like it when
        # those notices stopped being told as held (decision 56). And so does
        # every other notice the history no longer tells -- one set for after
        # the bill was withdrawn, or after the chamber took the measure from
        # its committee (decision 59e) -- since its calendar printed the bill.
        if e.get("cancelled") and not (e.get("overtaken") or e.get("notice")):
            continue
        c = _cite(e, sources, e.get("cite_year") or (e.get("date") or "")[:4])
        if not c.get("cite_url"):
            continue
        key = (e.get("cite") or "").strip()
        v = vols.setdefault(key, {"url": c["cite_url"], "pages": []})
        pg = (e.get("cite_page") or "").strip()
        if pg and pg not in v["pages"]:
            v["pages"].append(pg)
    for key, v in vols.items():
        pages = sorted(v["pages"], key=lambda x: int(x))
        label = key + ("" if not pages else
                       f", page {pages[0]}" if len(pages) == 1 else
                       ", pages " + ", ".join(pages[:-1]) + " and " + pages[-1])
        add_doc(label, v["url"], "record")
    # The calendar a committee report was printed in.
    # committee_reports() has already turned each report's calendar into
    # a key and a URL, so this cites what the report itself is citing
    # rather than parsing "House Calendar 51, 2025" a second time.
    for r in rep_written:
        add_doc(f"{r.get('source') or r.get('cite')}, committee report",
                r.get("cite_url", ""), "report")
    for r in rep_docket:
        if r.get("cite_url"):
            add_doc(f"{r['cite']}, committee report", r["cite_url"], "report")
    return docs, text_url


def _long_day(iso):
    """"2025-02-06" -> "February 6, 2025", as the narratives write a day."""
    try:
        y, m, d = (int(x) for x in str(iso).split("-"))
        return f"{MONTHS[m - 1].capitalize()} {d}, {y}"
    except (ValueError, IndexError):
        return str(iso or "")


def journal_story(b, jkeys):
    """What the page says of a bill whose record is the House Journal's:
    {intro, steps, dates, stages, notes, docs}.

    The bill is in none of the General Court's current files, so there is no
    docket to narrate and none is invented: no docket row, no status-page
    field, nothing presented as the General Court's own words. What is said
    is what the journal prints -- the day the bill was introduced and the
    committee it went to, and the day it was withdrawn and how -- in this
    site's words, with the journal cited for each, and one note saying where
    the record comes from. It says nothing about why the General Court's
    files lack the bill, which nothing on disk states.

    The rail and On the record read `steps` the way they read journey()'s:
    one House decision, drawn as the stop where the bill ended.
    """
    j = b.get("journal") or {}
    i, w = j.get("introduced") or {}, j.get("withdrawn") or {}
    if j.get("decided") and not w:
        return journal_decided_story(b, jkeys)
    committee = names.committee(b.get("house_committee") or "")
    vote, _, kind = (w.get("vote") or "").partition(", ")
    if not re.search(r"\d", vote):
        vote, kind = "", vote
    tally = vote.replace("-", "–")
    how = {"division": "on a division vote", "roll call": "on a roll call",
           "voice vote": "on a voice vote"}.get(kind, "")
    if w.get("how") == "consent calendar":
        step = "Withdrawn on the consent calendar"
        said = (f"On {_long_day(w.get('date'))} the House adopted its consent "
                "calendar, which listed the bill to be withdrawn.")
    else:
        step = "Withdrawn" + (f", {tally}" if tally else f" {how}" if how else "")
        said = (f"On {_long_day(w.get('date'))} the House voted to withdraw it"
                + (f" {how}" if how else "") + (f", {tally}" if tally else "") + ".")
        recon, _, rv = (w.get("reconsideration") or "").partition(", ")
        if recon:
            said += (f" A motion to reconsider {recon}"
                     + (f", {rv.replace('-', chr(0x2013))}" if rv else "") + ".")
    stages = [
        {"label": "In House committee" + (f" — {committee}" if committee else ""),
         "hand": "H:committee", "notes": [],
         "text": (f"It was introduced on {_long_day(i.get('date'))}"
                  + (f" and referred to the House {committee} committee." if committee
                     else "."))},
        {"label": "On the House floor", "hand": "H:floor", "notes": [], "text": said},
    ]

    def where(c):
        return (f"{c.get('journal')}, {_long_day(c.get('date'))}, page {c.get('page')}"
                if c else "")
    # ONLY WHAT WAS LOOKED AT. The bulk files and the database view were read
    # (journal_bills.py says which) and the bill is in none of them; no
    # status page was ever asked for, so the note does not speak for one.
    notes = [("The data files the General Court publishes for this term, its "
              "docket among them, do not list this bill. This record is the "
              f"House Journal's, which prints its introduction ({where(i)}) and "
              f"its withdrawal ({where(w)}).")]
    vols = {}
    for c in (i, w):
        url = journal_url(c.get("date", ""), c.get("journal", ""), jkeys) if c else ""
        if url:
            v = vols.setdefault(c["journal"], {"url": url, "pages": []})
            if str(c.get("page")) not in v["pages"]:
                v["pages"].append(str(c.get("page")))
    docs = [(f"{k}, page{'s' if len(v['pages']) > 1 else ''} {' and '.join(v['pages'])}",
             v["url"]) for k, v in vols.items()]
    return {"intro": i.get("date", ""),
            "steps": [{"date": w.get("date", ""), "body": "H", "act": "withdrawn",
                       "mark": "x", "text": step, "short": "withdrawn"}] if w else [],
            "dates": sorted(d for d in (i.get("date"), w.get("date")) if d),
            "stages": stages, "notes": notes, "docs": docs}


# What the House Journal's question on a committee report becomes as a line
# of the journey, by the status DISPOSED gives it.
J_DECIDED_ACT = {"Killed": "killed", "Indefinitely postponed": "postponed",
                 "Referred for interim study": "study"}


def journal_decided_story(b, jkeys):
    """journal_story for the bill whose journal record is the House's vote on
    its committee's report rather than a withdrawal (journal_bills.EARLIER:
    HB 459 of 2021), told only where its docket is not on this machine --
    with the docket narrated, the page is the docket's like any other bill's.

    The same shape and the same restraint: the day it was introduced and the
    committee it went to, the day the House voted and the count, each in this
    site's words with the journal cited, and one note of where the record
    comes from. The floor sentence is narrative.py's for the docket's own row
    of the vote, "Inexpedient to Legislate: MA RC 198-153", so the two builds
    read alike.
    """
    j = b.get("journal") or {}
    i, d = j.get("introduced") or {}, j.get("decided") or {}
    committee = names.committee(b.get("house_committee") or "")
    what = d.get("question") or ""
    hit = next((res for pat, res in DISPOSED if pat.search(what)), None)
    act = J_DECIDED_ACT.get(hit[1] if hit else "", "")
    y, _, n = (d.get("vote") or "").partition("-")
    counted = y.strip().isdigit() and n.strip().isdigit()
    tally = f"{int(y)}–{int(n)}" if counted else ""
    verb = N.RECOMMENDATION.get(what.strip().lower())
    said = (f"On {_long_day(d.get('date'))} the House "
            + (f"voted to {verb}" if verb else f"adopted “{what}”")
            + (f" on a {d['how']}" if d.get("how") else "")
            + (f" {tally}" if tally else "") + ".")
    stages = [
        {"label": "In House committee" + (f" — {committee}" if committee else ""),
         "hand": "H:committee", "notes": [],
         "text": (f"It was introduced on {_long_day(i.get('date'))}"
                  + (f" and referred to the House {committee} committee." if committee
                     else "."))},
        {"label": "On the House floor", "hand": "H:floor", "notes": [], "text": said},
    ]

    def where(c):
        return (f"{c.get('journal')}, {_long_day(c.get('date'))}, page {c.get('page')}"
                if c else "")
    # ONLY WHAT WAS LOOKED AT: the list the bill search gave for the term and
    # the database's table of past bills, neither of which has it.
    notes = [("This bill is not in the list the General Court's bill search gave "
              "for the term, and its database's table of past bills has no row for "
              "it. This record is the House Journal's, which prints its "
              f"introduction ({where(i)}) and the vote on its committee's report "
              f"({where(d)}).")]
    vols = {}
    for c in (i, d):
        url = journal_url(c.get("date", ""), c.get("journal", ""), jkeys) if c else ""
        if url:
            v = vols.setdefault(c["journal"], {"url": url, "pages": []})
            if str(c.get("page")) not in v["pages"]:
                v["pages"].append(str(c.get("page")))
    docs = [(f"{k}, page{'s' if len(v['pages']) > 1 else ''} {' and '.join(v['pages'])}",
             v["url"]) for k, v in vols.items()]
    steps = []
    if act and d:
        st = {"date": d.get("date", ""), "body": "H", "act": act,
              "mark": J_MARK.get(act, "x"),
              "vote": ("RC", int(y), int(n)) if counted else None}
        st["text"], st["short"] = _j_words(st, b.get("bill") or "")
        st.pop("vote")
        steps = [st]
    return {"intro": i.get("date", ""), "steps": steps,
            "dates": sorted(x for x in (i.get("date"), d.get("date")) if x),
            "stages": stages, "notes": notes, "docs": docs}


# WHERE A RECORD COMES FROM, where that is not the list the General Court's
# bill search gave for the term. build_data marks each: "source" on a measure
# added from the database's table of past bills (its PAST_SOURCE) or from the
# docket alone (DOCKET_SOURCE, with title_source naming the journal that
# titles it), "number_source" where the database has no bill number and the
# docket's is used, "journal" on a House Journal record. preflight holds the
# two files' words to each other.
PAST_SOURCE = "General Court database"
DOCKET_SOURCE = "General Court docket"


# A DOCKET ROW THAT NAMES ANOTHER BILL, on a record build_data made from the
# database: quoted as the docket has it, because the page shows the docket's
# lines, and said. SB 267 of 2007's one vote is entered "Sen. Foster Moved
# Suspend All Rules Necessary to Allow for Consideration of SB 266 ...; RC
# 14Y-10N, MF; SJ 25, Pg. 1406-1407". The Senate Journal of 5 September 2007
# prints two motions on those pages: SB 266-FN-A's, "Adopted by the necessary
# 2/3 vote", and then SB 267-FN's, on which Senator Estabrook asked for the
# roll call the docket records, 14 to 10 (journals_senate/2007/SJ 25.txt,
# lines 50-80). The row is under the right bill and names the wrong one.
# {(term, bill): the note}. For the Clerk's list.
ROW_NAMES_ANOTHER = {
    ("2007-2008", "SB267"): (
        "The docket's row for this vote names \u201cSB 266\u201d. The Senate Journal of "
        "September 5, 2007 (pages 1406\u20131407) records the motion, and the 14\u201310 "
        "roll call on it, as being on SB 267-FN, this bill; the row is quoted here as "
        "the docket has it."),
}


def _docket_as_entered(b, narr):
    """The close of the note on a bill told as not introduced: what its docket
    holds, in the docket's own tense, and what this site does with it.

    HB 87 of 2009 has one row, which enters it as introduced. HB 177 and
    HB 277 of 2017 have one that still reads "To Be Introduced 01/04/2017 and
    referred to ...". HB 273 of 2017 has a second, "Public Hearing: 01/10/2017
    01:30 PM LOB 306", which narrative.build tells as the docket's notice: it
    is quoted here, beside the row that enters the bill, and the page's list
    of docket lines shows both (docket_lines). And
    on a record of the bill search's own list, the House status that list
    gives -- IN COMMITTEE on all four of 2017 -- is said, because it is what
    the General Court's own page shows and this page does not repeat."""
    evs = [e for e in (narr or {}).get("events", []) if not e.get("in_line")]
    entered = [e for e in evs if e.get("type") == "entered_introduced"]
    notices = [e for e in evs if e.get("cancelled")
               and e.get("type") in ("hearing", "exec", "worksession")]
    as_ = ("to be introduced" if entered and N.TO_BE_INTRODUCED.match(
        entered[0].get("raw") or "") else "introduced")
    field = ((b or {}).get("house_status") or "").strip() \
        if (b or {}).get("source") != PAST_SOURCE else ""
    field = (f"the General Court's bill search gives its House status as "
             f"\u201c{field}\u201d") if field else ""
    told = "told here as not introduced, and no record on this site says what became of it."
    if len(entered) == 1 and len(evs) == 1:
        return (f"Its docket has one row, which enters it as {as_}"
                + (f", and {field}" if field else "") + f"; it is {told}")
    if len(entered) == 1 and notices and len(evs) == 1 + len(notices):
        count = {2: "two", 3: "three", 4: "four"}.get(len(evs), str(len(evs)))
        rows = ", and ".join(f"one reads \u201c{e.get('raw')}\u201d" for e in notices)
        return (f"Its docket has {count} rows: one enters it as {as_}, and {rows}. "
                + (f"{field[0].upper()}{field[1:]}. " if field else "") + f"It is {told}")
    return (f"Its docket enters it as {as_}" + (f", and {field}" if field else "")
            + f"; it is {told}")


def record_notes(b, narr, status_source="", sponsors=(), term="", bid="",
                 text_version=""):
    """The notes a page carries about where its record comes from, as a list
    (empty for a record of the bill search's own list, which is nearly every
    one). One plain sentence or two each, in this site's words: a reader shown
    a bill the General Court's own search does not return is owed where it was
    read. Said after the docket's own notes, and never on a journal record
    told by journal_story, which says its own.

    ONLY WHAT IS TRUE OF THIS PAGE. The first note said "Its title, committee
    and status here are from the General Court's database" on every one of
    these records -- on the ones with no committee at all, and on the ones
    whose status_source beside it read "derived from the docket". The title is
    always the database's. The status is said to be where status_source says
    it is from. The committee is not placed: it is the docket's introduction
    row's where there is one and the referral code's otherwise, as on every
    archived bill, and no page says which.
    """
    b = b or {}
    out = []
    said = b.get("introduction") or {}
    if b.get("source") == PAST_SOURCE:
        from_db = status_source == PAST_SOURCE
        from_journal = status_source == JOURNAL_SOURCE
        note = ("This bill is not in the list the General Court's bill search gave "
                "for the term, which is where this site's other records of the term "
                "come from. Its title" + (" and status here are" if from_db else " here is")
                + " from the General Court's database of past sessions"
                + ((", and its history from its docket." if from_db or from_journal
                    else ", and its history and status from its docket.") if narr
                   else "."))
        if b.get("number_source") == DOCKET_SOURCE:
            note += (" The database's row for it carries no bill number; the number "
                     "is the one its docket files it under.")
        out.append(note)
    if said:
        # What the House Journal's resolution of introduction says of it
        # (build_data.INTRODUCTION_FROM_JOURNAL), where that decided how
        # the docket is told: on a record made from the database, and on the
        # four of 2017 that are the bill search's own, which carry this note
        # and not the one above.
        where = (f"The House introduces its bills by a resolution that names them "
                 f"by number. The resolution of {_long_day(said.get('date'))} "
                 f"({said.get('journal')}) names House Bills "
                 f"{said.get('numbered')}")
        if said.get("introduced"):
            out.append(where + ", which takes in this one, and the journal's list "
                       "prints its entry with its committee. Its docket enters its "
                       "withdrawal on the morning of the same day, so it is told "
                       "here as introduced and then withdrawn.")
        elif (narr or {}).get("withdrawn"):
            out.append(where + ", which leaves this number out, so it is told here "
                       "as withdrawn without having been introduced.")
        else:
            note = (where + ", which leaves this number out, and no later "
                    "resolution of the term names it. "
                    + _docket_as_entered(b, narr))
            # AND THE HEADING ON ITS TEXT IS NOT AN INTRODUCTION. The four of
            # 2017 have a text on the General Court's site, each headed "HB
            # 273 - AS INTRODUCED" (legislation/2017/HB0273.html), and the Bill
            # Text tab shows that heading under a status of Not introduced.
            # `text_version` is the heading as the tab prints it.
            if (text_version or "").strip().lower() == "as introduced":
                note += (" The General Court's text of it is headed \u201cAs "
                         "introduced\u201d, the heading it gives a bill's first "
                         "printing, and the Bill Text tab shows it under that heading.")
            out.append(note)
    if b.get("source") == PAST_SOURCE and (term, bid) in ROW_NAMES_ANOTHER and narr:
        out.append(ROW_NAMES_ANOTHER[(term, bid)])
    # A SPONSOR LIST THAT MAY BE SHORT. In 1999-2000 the General Court's
    # sponsor record lists fewer sponsors than the bills print
    # (past_sponsors.SHORT_TERMS says what was measured), and a bill filled
    # from it has nothing else to be held to.
    if term in PSP.SHORT_TERMS and any(
            x.get("seat_source") == PSP.SOURCE for x in sponsors or ()):
        out.append("This bill's sponsors are from the General Court's sponsor record, "
                   "the only source this site has for them. For 1999\u20132000 that "
                   "record leaves co-sponsors off some bills that print them, so this "
                   "list may not be complete.")
    if out:
        return out
    ts = b.get("title_source") or {}
    if ts:
        return [("The General Court's data holds this measure's docket and no title "
                 f"for it. The title here is as the {ts.get('journal', 'journal')} "
                 f"prints it ({_long_day(ts.get('date'))}, page {ts.get('page')} of "
                 f"{ts.get('volume', 'the bound volume')}).")]
    j = b.get("journal") or {}
    if j.get("decided") and narr:
        i = j.get("introduced") or {}
        return [("This bill is not in the list the General Court's bill search gave "
                 "for the term, and its database's table of past bills has no row for "
                 "it. Its title and sponsors here are as the House Journal prints "
                 f"them in its list of bills introduced ({i.get('journal')}, "
                 f"{_long_day(i.get('date'))}, page {i.get('page')}); its history is "
                 "from its docket.")]
    return []


def bill_text_url(b, st):
    """The address of the bill's own text, corrected on the way out.

    Small, and out on its own because it feeds both the documents list
    and the payload, and because the twenty lines of comment below are
    the record of two separate failures that each reached every bill on
    the site. They travel with the code they explain.
    """
    # billText.aspx needs the session year as well as the id. Without it
    # the page answers with an ASP.NET error and the reader gets a blank
    # screen. Records fetched before that was understood carry a two-
    # parameter link, so the year is added here from the bill's own filing
    # year -- which is what the status page's link says, on every one
    # checked. Re-running fetch_bill_status.py --reparse replaces the
    # guess with the page's own value and needs no network.
    #
    # AND txtFormat=pdf IS NOT AN ADDRESS THE GENERAL COURT SERVES. The
    # scrape built one anyway, so every bill on this site linked to
    #
    #   error: condensedbillno is neither a DataColumn nor a DataRelation
    #   for table text.
    #
    # All 4,230 of them. The status page's own link -- the one shape that
    # appears in 2,234 cached pages -- is txtFormat=html, which answers
    # with the bill. So the format is corrected here rather than in the
    # scrape, because the scrape is a record of what was fetched and this
    # is a link being published.
    text_url = (st.get("text_pdf", "") or "").replace("txtFormat=pdf",
                                                      "txtFormat=html")
    if text_url and "sy=" not in text_url:
        sy = st.get("text_year") or b.get("lsr_year") or ""
        if sy:
            text_url += f"&sy={sy}"
    # AND 2016 NEEDS &v=current, or the link we publish is dead. Without it
    # billText answers 200 with a two-byte body, so this was sending readers
    # of up to 1,072 bills to a blank page that looked like a working address.
    # Measured 19 September; fetch_legislation.NEEDS_VERSION is the same fact
    # on the fetching side.
    if text_url and "sy=2016" in text_url and "v=" not in text_url:
        text_url += "&v=current"
    return text_url


def bill_next_step(narr, b, prefix, st, settled, told):
    """What happens to this bill next, in one line.

    It was a conditional expression nested three deep across six lines, with
    `next_step(narr, b, prefix)` appearing in three of its branches -- and two
    of those three are the same branch wearing different conditions: if the
    bill is settled the answer is that call, and if nobody has told us a
    status the answer is that call again. Written as statements the shape is
    obvious and the duplication collapses to one line.

    Behaviour is unchanged, which the manifest diff is there to prove rather
    than to assert: the site was rebuilt into a scratchpad tree and every one
    of 34,114 files hashed identical before and after.

    A bill with no narrated docket has no history for next_step() to read,
    and it answers "No recorded action yet" -- which is what the status box
    of about 10,000 laws of 1989-2016 said once the docket's signature line
    began settling those bills. Such a bill says what settled
    it, the way next_step() says "Signed into law" for a narrated one; and
    one nothing settled says what its fields say, which is a recorded
    action, rather than that there is none.
    """
    if settled and not narr:
        return settled[1]
    if narr and (settled or not told):
        return next_step(narr, b, prefix)
    joined = " \u00b7 ".join(x for x in [
        f"House: {st['house_status']}" if st.get("house_status") else "",
        f"Senate: {st['senate_status']}" if st.get("senate_status") else "",
    ] if x)
    return joined or next_step(narr, b, prefix)


def bill_stations(bid, term, procs, segs, marks):
    """Every committee proceeding on one bill, oldest first.

    A leaf: one output, no other reader in the loop, nothing captured that is
    not passed. Keyed (term, bid) because a bill number names a different bill
    in each biennium.
    """
    return [station_for_proceeding(p, bid, segs, marks)
            for p in sorted(procs.get((term, bid), []),
                            key=lambda x: (x["sched_date"],
                                           x["sched_time"] or ""))]


def bill_rollcalls(bid, term, rcs, narr, votes_by_bill, legs, unnamed):
    """Every recorded vote on one bill, in the order the docket took them.

    Lifted verbatim out of build_bills except for indentation.

    IT ALSO KILLS A SHADOW, BY CONSTRUCTION RATHER THAN BY CARE. In the
    enclosing scope `kind` is the bill's status kind, read five times in the
    payload; this block rebound it to a ("voice vote", False) tuple 147 lines
    after the last of those reads. Harmless only by that distance -- any new
    use of `kind` in the payload would silently have got a tuple or None. The
    same was true of `n`, a bill count outside and a nay count here. Neither
    name means anything else in this function now, so neither can shadow
    anything again.

    build_bills' own docstring records that this failure already happened
    once, with `st` meaning two things 350 lines apart. This is the second
    instance, found while splitting the function the first one caused.
    """
    rc_out = []
    rc_order, rc_names = vote_chronology(rcs, narr)
    for r in sorted(rcs, key=lambda x: (x.get("date", ""), int(x.get("number", 0)))):
        key = f"{r.get('year')}-{r['body']}-{r['number']}"
        members = votes_by_bill.get((term, bid), {}).get(key, [])
        tally = defaultdict(lambda: defaultdict(int))
        for m in members:
            tally[m["party"] or "X"][m["vote"]] += 1
        rc_out.append({
            "date": r.get("date"), "body": r.get("body"),
            "question": r.get("question"), "yeas": r.get("yeas"),
            "nays": r.get("nays"), "passed": r.get("passed"),
            "threshold_note": r.get("threshold_note"),
            # Which amendment this vote was on, where the docket says so.
            # "Adopt Amendment" twice in an afternoon is two different
            # amendments and no way to tell which is which.
            "amendment": rc_names.get((r.get("body"), r.get("number"))),
            "_ord": (r.get("date") or "",
                     rc_order.get((r.get("body"), r.get("number")),
                                  10 ** 6 + int(r.get("number") or 0))),
            # What the yes side had to reach, so the chart can mark it.
            # rollcall_outcomes works this out per motion: two thirds of
            # those voting for a veto override or a rules suspension, three
            # fifths of the members in office (the ballots, not the seats)
            # to pass a CACR, and whatever the docket or the Journal names
            # for a motion it says needed more; a simple majority otherwise.
            # `passed` is the clerk's recorded outcome where the record
            # names one, and where the record and the ballots disagree the
            # page says so -- in the site's own words, each side attributed
            # to its source -- rather than choosing quietly.
            "threshold_needed": r.get("threshold_needed"),
            "threshold_rule": r.get("threshold_rule"),
            **({"threshold_unknown": True} if r.get("threshold_unknown") else {}),
            **({"outcome_conflict": r["outcome_conflict"]}
               if r.get("outcome_conflict") else {}),
            "tally": {p: dict(v) for p, v in tally.items()},
            # "s" is the surname-first sort key. The grids are read
            # alphabetically, and sorting the displayed string would order
            # 400 members by honorific and then by first name.
            "members": [vote_member(m, r.get("body"), legs, unnamed)
                        for m in members],
        })

    # Voice and division votes, from the docket. A voice vote records only
    # which side sounded louder; a division records the count but not who
    # voted which way. Both decide bills, and leaving them off the votes tab
    # makes a bill look as though nothing happened on the floor.
    VK = {"VV": ("voice vote", False), "DV": ("division vote", False)}
    for _i, e in enumerate((narr or {}).get("events", [])):
        if e.get("type") != "floor" or e.get("cancelled"):
            continue
        kind = VK.get(e.get("vote_kind"))
        if not kind:
            continue          # RC is already covered by the roll call file
        label, _ = kind
        y, n = e.get("yeas"), e.get("nays")
        rc_out.append({
            "date": e["date"], "body": e.get("body"),
            "question": e.get("action") or "Floor action",
            # Who made the motion, split off the question by narrative.py so
            # the Senate's "Sen. Abbas Moved Laid on Table" reads as a motion
            # to lay on the table, moved by Abbas. Roll calls from the roll
            # call file never carry one; the page prints it only when present.
            "mover": e.get("mover") or "",
            "yeas": int(y) if y else None, "nays": int(n) if n else None,
            "passed": e.get("motion") in ("MA", "AA"),
            "vote_kind": e.get("vote_kind"), "vote_kind_label": label,
            "threshold_note": None, "tally": {}, "members": [],
            "amendment": None, "_ord": (e["date"], _i),
        })
    # By the docket's own sequence, not by the wording of the motion.
    rc_out.sort(key=lambda r: r["_ord"])
    return rc_out


TOPICS_GUESSED = Path("topics_assigned.json")


def merge_guessed_topics(bills):
    """Fill a topic for the eighteen terms the General Court gave none.

    Its own assignment reaches 2,221 bills of 2025-2026 and no others, so the
    topic facet has been a filter that hides 29,449 bills. topics.py learns
    from the term they did label and answers for the rest, or says
    Miscellaneous where it cannot -- at the threshold it publishes at, 14 of
    15 of its answers were judged defensible at the bench and none wrong.

    NEVER OVER A TOPIC THE GENERAL COURT GAVE. A record that already carries
    one keeps it, so 2025-2026 is untouched and a later term the General Court
    labels will overwrite nothing.

    AND IT IS MARKED AS OURS. subject_source distinguishes the two on every
    record that has a topic at all, because a reader filtering by Elections
    should be able to find out whether the General Court filed a bill there or
    this site did. That is the same distinction the page already draws between
    a boundary the chair spoke and one a model placed, and between a veto
    message quoted and a bill note written here.

    Absent the file, nothing happens and the site is exactly as it was.
    """
    if not TOPICS_GUESSED.exists():
        return 0
    try:
        guessed = json.loads(TOPICS_GUESSED.read_text(encoding="utf-8"))
    except ValueError:
        return 0
    n = 0
    for term, by_bill in bills.items():
        for bid, rec in by_bill.items():
            if rec.get("subject"):
                rec.setdefault("subject_source", "general court")
                continue
            got = (guessed.get(term) or {}).get(bid)
            if not got or not got.get("subject"):
                continue
            rec["subject"] = got["subject"]
            rec["subject_code"] = got.get("subject_code") or ""
            rec["subject_source"] = "granite record"
            n += 1
    if n:
        print(f"  {n:,} bills given a topic by the topic model "
              f"(the General Court gave none); marked subject_source")
    return n


# Codes for the two categories the General Court does not have. Nothing reads
# subject_code -- it is carried through and displayed -- but it must not be
# empty where every other subject has one.
# One definition, in topic_model beside the names themselves: this file had
# its own copy, and two tables of the same two codes are two chances to
# disagree the day a third name is added.
ADDED_CODES = TM.ADDED_CODES


def unify_vocabulary(bills):
    """ONE VOCABULARY ACROSS ALL NINETEEN TERMS, applied last and to everything.

    The topic model predicts in the General Court's own 46 categories, which is
    the vocabulary it was measured in -- 62.1% to 67.2% held out. The site's
    own vocabulary is a different thing: five starved categories folded into
    parents, Regular Meeting retired, and Housing and Study Committees added.
    Applying it inside the model would have meant
    scoring the model against a vocabulary it was not measured in.

    So it is applied HERE instead, once, to every bill of every term -- the
    General Court's own labels for 2025-2026 as much as the model's answers for
    the archive. That is the point. Fold the archive alone and the two halves of
    the site stop sharing a vocabulary: a reader filtering Parks and Recreation
    would find 2025-2026's bills and none of the eighteen terms before it, and a
    reader filtering Housing would find the archive and not the current term.
    A facet that means different things in different terms is worse than either
    name on its own.

    The rule for the folds is that a category has to carry its own
    weight: measured from the General Court's own labels, these five run at 0.5
    to 6 bills a year against a threshold of ten, and the seven others between 7
    and 9.5 were deliberately left alone.
    """
    moved = Counter()
    for term, by_bill in bills.items():
        for bid, rec in by_bill.items():
            s = (rec.get("subject") or "").strip()
            if not s:
                continue
            if s in TM.RETIRED:
                rec["subject"], rec["subject_code"] = "", ""
                moved["retired"] += 1
                continue
            new_s = TM.remap_gold(s, rec)
            if new_s != s:
                rec["subject"] = new_s
                rec["subject_code"] = ADDED_CODES.get(new_s) or rec.get("subject_code") or ""
                moved[f"{s} -> {new_s}"] += 1
    if moved:
        total = sum(moved.values())
        print(f"  {total:,} bills moved into the site's own topic vocabulary")
        for k, v in moved.most_common(8):
            print(f"      {v:>6,}  {k}")
    return sum(moved.values())


def vote_note_for(narr, rollcalls):
    """The note above the votes table, silenced where it would contradict it."""
    note = (narr or {}).get("vote_note", "")
    if rollcalls and note.startswith("Every floor vote"):
        return ""
    return note


# A CLERK'S NOTE ON THE RECORD IS NOT AN ACTION ON THE BILL. "(SENATE CLERK'S
# NOTE: The roll call vote below on SB 331 was inadvertently entered in the
# Daily Journal and has been corrected in the Senate Permanent Journal from
# 12-12 to 13-11)" was entered on 20 April 2020 on a bill the Senate tabled on
# 15 March 2018. It states no day, so it keeps the day it was entered -- and
# with it SB 331 of 2018's last action was of 2020, sixteen months after its
# term ended, and the bill was "carried over". The note stays on the bill's
# list of docket lines; it is left out of the days the bill was acted on.
CLERKS_NOTE = re.compile(r"^\W*(?:senate\s+|house\s+)?clerk'?s\s+note\b", re.I)


def action_dates(evs):
    """The days a bill was acted on, in order: the day of every docket row
    that is not cancelled and is not a clerk's note on the record. The last
    is the bill's last action, and two years among them, from its
    introduction on, make it one carried over from the first
    (carried_over)."""
    return sorted(e["date"] for e in evs
                  if e.get("date") and not CLERKS_NOTE.match(e.get("raw") or ""))


def carried_over(dates, intro=""):
    """Whether a bill was acted on in more than one year: filed in one and
    acted on in the next, retained in committee or sent to interim study.

    FROM ITS INTRODUCTION ON. A row entered before the bill was introduced is
    a notice of what was to come, not a session's action on it: "Amendment
    #2022-0013s to SB 240 will be proposed and can be accessed via the General
    Court Website", entered on 29 December 2021 for a hearing of 10 January,
    on a bill "To Be Introduced 01/05/2022". SB 240, SB 253 and SB 254 of
    2022, the redistricting bills, each carried that one row of 2021 and were
    "carried over" from a session they were not in. A bill that really was
    carried over was introduced in its first year, so it loses nothing by
    this. `intro` is the journey's day of introduction; where the docket
    gives none, every row counts, as before.
    """
    return len({d[:4] for d in dates if not intro or d >= intro}) > 1


# "WITH THE GOVERNOR" IS A PLACE, AND A BILL A CHAMBER ENDED WAS NOT THERE.
# narrative.py files an "Enrolled" row with the governor, which is where
# enrolment leads. HB 613 and HB 614 of 1993 carry "ENROLLED; HJ82,P1921 (SEE
# MAY 25TH PERM JRNL)" under the House on 25 May 1993, the day the Senate --
# which had recalled and tabled both a week before -- killed them with every
# tabled bill; SB 286 of 2025, dead on the Senate's table since October,
# carries "Enrolled Adopted, VV, (In recess 01/07/2026)". Each history had a
# stage headed "With the governor", under a rail saying "Governor: Never
# reached". Only for a bill that is finished and whose rail does not reach
# the governor; a resolution's enrolment is another matter and is left.
#
# AND THE SENTENCE WENT ON SAYING IT WAS ENROLLED. Under the chamber's heading
# the stage still read "The bill was enrolled on January 7, 2026 -- the final
# check of the text before it goes to the governor", on SB 286 of 2025, which
# the Senate had killed on its table on 31 October 2025 and which was never
# enrolled: the report of the Committee on Enrolled Bills in the Senate Journal
# that row cites (SJ 2 of 2026) names HB 480, SB 189 and SB 268, and the row on
# SB 286 is the row of SB 268 entered under the wrong number. A bill is
# enrolled when both chambers have passed it, and HB 613, HB 614 and SB 286
# each ended in one. The sentence is not said
# (ENROLLED_SAID); the row stays on the bill's list of docket lines with why
# (ENROLLED_NOT_TOLD); and it is not a day the bill was acted on, so SB 286's
# last action is 31 October 2025 and it is not "carried over" into 2026
# (enrolled_untold, which the build asks for all three).
ENROLLED_SAID = re.compile(
    r"\s*The bill was enrolled(?: on [A-Z][a-z]+ \d{1,2}, \d{4})? — the final check of "
    r"the text before it goes to the governor\.")
ENROLLED_NOT_TOLD = ("The docket carries this row on a bill that ended in the {chamber} and "
                     "did not go to the governor. The history does not tell it as the bill's "
                     "enrolment, and it is not counted as a day the bill was acted on.")

# A ROW THAT CALLS A MEETING OFF IS ON THE BILL'S LIST OF DOCKET LINES (7
# October 2026; the person: "I just didn't want to have the cancellations or
# rescheduling listed in the narrative, but the docket should keep them as the
# official docket has them listed"). The list, headed "every action the
# General Court recorded", left off every row the docket cancelled -- 4,847
# rows on 3,885 bills on that day, "==CANCELLED== Public Hearing: 01/15/2013
# 2:00 PM LOB 301" (HB 114 of 2013) and SB 107 of 1999's "Hearing Cancelled
# Due To Town Meeting Day" alike -- by the convention a notice's row once
# followed too, and stage 2b's reading of more of the clerk's spellings of the
# mark took 99 more off. Each is listed now, with this note beside it, as a
# notice no committee sat for is listed with narrative.notice_note's; the
# history, the stations, the committee days and the download tell none of
# them, as before. The clerk's "==CANCELLED==" is not in the line, as no
# line's "==MARK==" is (narrative.clean), so the note is what says it.
CANCELLED_NOT_TOLD = ("A cancellation. The history does not tell a meeting the docket "
                      "called off.")

# The kinds of row a cancellation is: a meeting's, or a line no table reads
# ("==CANCELLED==;SC 6-A,Pg.3", HB 214 of 1999; "==CANCELLED==JUN12 & 19 WORK
# SESSIONS", HB 321 of 1991). NOT A ROW OF ANOTHER KIND: the same mark on SB 38
# of 2009's committee report ("=== CANCELLED === Committee Report; Ought to
# Pass [1/28/09]; SC8", the report's day moved to 4 February) and on HB 1611 of
# 2020's Senate introduction calls no meeting off. Those two are listed too
# now, like every other cancelled row (the person, 7 October 2026), with
# CANCELLED_ROW_NOT_TOLD beside them, which does not call them a meeting.
CANCELLED_ROW_NOT_TOLD = ("A cancellation. The history does not tell a row the docket "
                          "marked cancelled.")
CALLED_OFF_KINDS = ("hearing", "exec", "worksession", "conference_meeting", "other")


def called_off(e):
    """Is this event a row that calls a meeting off: one the docket cancelled
    (narrative's "cancelled"), not a notice told as one ("notice"), and of a
    meeting's kind (CALLED_OFF_KINDS)?"""
    return bool(e.get("cancelled")) and not e.get("notice") \
        and e.get("type") in CALLED_OFF_KINDS


def enrolled_untold(narr, kind, rail):
    """The docket's "Enrolled" rows of a finished bill whose rail ends in a
    chamber and does not reach the governor, which the history does not tell
    as an enrolment; [] for every other bill."""
    stages = (narr or {}).get("stages", [])
    if (kind != "done" or len(rail or "") < 4 or rail[3] != "-" or "x" not in rail[1:3]
            or not any(s.get("hand") == "G:governor" for s in stages)):
        return []
    return [e for e in (narr or {}).get("events", [])
            if not e.get("cancelled") and e.get("type") in ("enrolled", "enrolled_amendment")]


def stages_told(narr, kind, rail):
    """The history's stages, with a "With the governor" stage of a bill the
    rail has ending in a chamber left without the sentence that says the bill
    was enrolled, and headed by the chamber that entered the row where
    anything of it is left."""
    stages = (narr or {}).get("stages", [])
    rows = enrolled_untold(narr, kind, rail)
    body = next(((e.get("body") or "")[:1].upper() for e in rows), "")
    if body not in ("H", "S"):
        return stages
    label = f"On the {'House' if body == 'H' else 'Senate'} floor"
    told = []
    for s in stages:
        if s.get("hand") != "G:governor":
            told.append(s)
            continue
        text = ENROLLED_SAID.sub("", s.get("text") or "").strip()
        if text:
            told.append({**s, "text": text, "label": label, "hand": f"{body}:floor"})
    return told


def docket_line(e):
    """The docket line an event was read from, as the clerk typed it: the
    whole line where the event is one question of a line told question by
    question and is the one that carries it ("line"), else its own `raw`."""
    return e.get("line") or e.get("raw") or ""


def listed_line(e):
    """The line as the bill's docket list prints it: docket_line, with the
    clerk's cancel mark where the line carries one (narrative.marked_line's
    `said`, the person's item of 7 October 2026). Only the list reads it;
    everything that reads a line for what it says reads docket_line."""
    return e.get("line") or e.get("said") or e.get("raw") or ""


def marked_cancelled(e):
    """A row the docket itself cancelled: narrative's "cancelled", and not a
    notice told as one ("notice"). A meeting's (called_off) or, twice in the
    record, another kind of row."""
    return bool(e.get("cancelled")) and not e.get("notice")


def docket_lines(narr):
    """The docket's own lines for the bill's page: its events, and the rows
    the docket files under it that belong to another bill, by date. Those
    are not in "events", so nothing that tells the bill's story reads them.

    A line told question by question (docket_vocab.questions) is listed
    once, whole, by the event that carries it: the page shows the clerk's
    lines, and a clause of one is not a line.

    A MEETING ROW TOLD AS A NOTICE IS LISTED: narrative.build carries it as
    cancelled, so that nothing reads it as a sitting, and the docket did not
    cancel it -- "Public Hearing: 01/10/2017 01:30 PM LOB 306" on HB 273 of
    2017, a bill the House did not introduce, and the notices HB 1284 and HB
    1512 of 2012 were withdrawn ahead of. The list is every action the General
    Court recorded, and HB 273's note said "Its docket has two rows" above a
    list of one. The row comes with the note narrative.notice_note gives it.

    AND SO IS A ROW THAT CALLS A MEETING OFF (called_off, 7 October 2026),
    with CANCELLED_NOT_TOLD beside it: the docket keeps it, and only the
    history leaves it out. AND A CANCELLED ROW OF ANOTHER KIND (the same
    day): SB 38 of 2009's committee report and HB 1611 of 2020's Senate
    introduction, the only two, with CANCELLED_ROW_NOT_TOLD. So every row the
    docket holds is listed, each cancelled one with the clerk's mark
    (listed_line)."""
    evs = [e for e in (narr or {}).get("events", [])
           if not e.get("in_line")]
    away = list((narr or {}).get("misfiled", []))
    if not away:
        return evs
    return sorted(evs + away, key=lambda e: e.get("date") or "")


PENDING = re.compile(r"(In progress|In committee|Pending|Enrolled\.)", re.I)

# WHAT A next_step() LINE CLAIMS, as the kind of status it would sit under.
# next_step() reads the LAST event, and the last event is often not the one
# that decided the bill: HB 691 of 2025's is the House killing it, 190-156, a
# floor row, so it read "Pending action in the other chamber"; HB 675 of 2026's
# is a failed motion to reconsider the kill; HR 24 of 2000's is a rules
# suspension, which a one-chamber resolution read as "Adopted" under a chip
# saying "In committee". The General Court's own field wording ("House:
# INEXPEDIENT TO LEGISLATE") is not one of these and is left as it is. Most
# specific first: "Vetoed, then overridden" is law, not a veto.
STEP_CLAIM = [
    (re.compile(r"(?:Signed into law|Became law|Vetoed, then overridden)"), "law"),
    (re.compile(r"Vetoed"), "veto"),
    (re.compile(r"(?:Adopted|Goes to the voters)"), "adopted"),
    (re.compile(r"Died\b"), "done"),
    (re.compile(r"(?:In progress|In committee|Pending|Enrolled\.|Retained)"), "active"),
]


def settled_step(step, status, term, current, kind=""):
    """The status box, with nothing left pending once a term has closed, and
    never claiming what the status does not: a line that says the bill is
    still moving, adopted, law or vetoed, under a status of another kind,
    gives way to the status. Once the session was over, 130 records of
    2025-2026 claimed another kind of status than their chip -- 93 of them
    "Pending action in the other chamber" under "Killed", and HR 30
    "Adopted" under "Killed" -- and two of closed terms did: HR 24 of 2000,
    and HB 542 of 2011, overridden and Chapter 271, "The override failed"."""
    if term != current and PENDING.match(step or ""):
        return status or step
    claim = next((k for rx, k in STEP_CLAIM if rx.match(step or "")), "")
    if kind and status and claim and claim != kind:
        return status
    return step


def chapter_of(st, docket, tally):
    """The chapter of the session laws a bill became, as the page prints it.

    The status page's own field for the terms it was fetched for; the
    docket's law line, as extract_chapters.py reads it, for every term. Where
    both exist they agree on 1,268 of 1,270 bills, and the two that differ
    are the docket's typing -- SB 62 of 2025 is chapter 38 in its enrolled
    text and the field, 39 in the docket -- so the field is shown and every
    difference counted. Leading zeros go: the field says "0043", the docket
    "Chapter 43" or "CHAP.0043", and the law is chapter 43.
    """
    stated = str((st or {}).get("chapter") or "").strip()
    found = (docket or {}).get("chapter")
    if stated:
        num = str(int(stated)) if stated.isdigit() else stated
        tally["the status page"] += 1
        # A number the docket withheld as a clash is still a number it
        # wrote, and still counts as a difference if it is not this one.
        said = found or (docket or {}).get("docket")
        if said and str(said) != num:
            tally["differ"] += 1
        return num
    if found:
        tally["the docket"] += 1
        return f"{found}, special session" if docket.get("special") else str(found)
    if (docket or {}).get("withheld"):
        tally["withheld"] += 1
    return ""


def build_bills(out, bills, narratives, rollcalls, reports, sponsors,
                bill_texts, amend_texts, testimony, testimony_db, procs, floor, segs,
                marks, sources, legs, leg_by_sort, leg_by_name,
                votes_by_bill, vetoes=None, notes=None, coverage=None,
                chapters=None, seats=None, session_over="", former=None,
                links=None, hearing_reports=None, ballots=None, term_rosters=None):
    """One JSON per bill, and the index row for each.

    This is the loop ARCHITECTURE item 5 names. It ran inside a 955-line
    main(), which is how `st` came to mean the bill's status record at the
    top and a video station 350 lines later -- costing 611 bills their
    facts, their bill-text link and, for 496, their status line.

    Every input is named in the signature rather than inherited from an
    enclosing scope, so a name can no longer be quietly reused.

    Returns (index, years, unnamed, sponsored) -- unnamed being the member
    ids the roll calls reference that the roster cannot name, and sponsored
    being what each member put their name to, which the legislator pages have
    advertised since they were written and never had.
    """
    unnamed = set()
    sponsored = defaultdict(list)

    index, years = [], set()
    status_pages = load("bill_status.json", {})
    if status_pages:
        n = (sum(len(v) for v in status_pages.values())
             if P.term_keyed(status_pages) else len(status_pages))
        terms = (", ".join(sorted(status_pages)) if P.term_keyed(status_pages)
                 else "one term, not keyed")
        print(f"stated status available for {n:,} bills ({terms})")
    n_stated = 0
    # For the sponsor lookup only. Built once rather than per bill: 33,683
    # bills against one dict merge.
    #
    # AND THE NUMBERS A SITTING MEMBER VOTED UNDER IN THE OTHER CHAMBER.
    # member_links joins those to the member for their VOTES, and their page
    # carries both chambers; the sponsor lookup never learned about them, so a
    # bill filed under the earlier number found nobody. It mostly did not show,
    # because the fallback that matches on a name caught them anyway -- and it
    # caught them only where the bill's text spells the member the way today's
    # roster does. Sen. Pat Long's House record is filed under "Patrick", which
    # is how 100 of his own sponsorships rendered as plain text while every
    # other chamber-changer's linked.
    #
    # Keyed on the earlier number and pointing at the sitting member, so the
    # join is the one member_links already made rather than a second guess at
    # it. The label is untouched: a 2009 bill still reads "Rep. Patrick Long
    # (D - Hills 10)", the seat he held when he filed it.
    _people = {**legs, **(former or {})}
    for _sit, _earlier in (links or {}).items():
        for _old in _earlier:
            _people.setdefault(str(_old), legs.get(_sit) or {})
    # And, for a term whose own roster is frozen and not the sitting one
    # (main says which), the members who left by name: bill_sponsor_list
    # says why. Every one of a name, in order, since only the one who sat
    # that term is taken.
    _left = None
    term_rosters = term_rosters or {}
    if term_rosters:
        _left = (defaultdict(list), defaultdict(list))
        for _m in (former or {}).values():
            _left[0][sort_name(_m.get("name") or "")].append(_m)
            _k = name_key(_m.get("name") or "")
            if _k:
                _left[1][_k].append(_m)
    # The Senate's hearing reports: who testified, resolved to members where
    # a line names one. Counted as they are attached, so the build says how
    # many found their hearing and names the ones that did not.
    _hr_idx = speaker_index([*legs.values(), *(former or {}).values()])
    # ... and for a term whose own roster is frozen and is not the sitting
    # one, that roster and the members who left before it was frozen: a
    # speaker is resolved among the people who sat that term, with the party
    # they sat with, and linked to their page as it is now -- or not linked,
    # where they have none (the rehearsal of the review, 5 October 2026).
    _hr_term = {_t: speaker_index([*_r.values(),
                                   *(f for _mid, f in (former or {}).items() if _mid not in _r)])
                for _t, _r in term_rosters.items()}
    _hr_name = SHR.name_part
    hr_tally = Counter()
    hr_unmatched = []

    # Every bill of every term the file holds. The term is still taken from the
    # bill's own filing year rather than from the key, so the two can be
    # compared if they ever disagree.
    #
    # bill_status.json and bill_text.json are keyed on the term. Either may
    # still be in the flat shape, in which case it holds the current term and
    # P.per_term hands an archived term nothing -- HB100 exists in every
    # biennium, so the current term's text on an archived bill is worse than
    # no text. The scraped testimony.json, flat and once read through the
    # `own` guard below for the same reason, is retired (main says why): the
    # `testimony` handed in is empty, and every count is testimony_db.json's.
    current = max(bills) if bills else ""
    session_over = session_over_in(session_over, current)
    n_stale = 0
    n_db = 0
    n_chapter = Counter()
    # THE ABOUT PAGE'S ARITHMETIC, COUNTED WHERE THE STATIONS ARE MADE.
    # about.html described the site's timing coverage in eight typed figures.
    # Seven of them were wrong -- it said 10,810 proceedings
    # against 101,290, and 1,068 with no recording against 78,344 -- because
    # they were true of one term on the day somebody typed them and the site
    # grew eighteen more terms afterwards. A figure a person retypes is a
    # figure that goes stale silently, and this one was published as a
    # statement about the site's accuracy.
    #
    # Counted here rather than re-derived: this loop already holds every
    # station the site will draw, so the tally costs nothing and cannot
    # disagree with the pages. about_figures.py reads the file and refuses to
    # print a sentence it has no number for.
    station_states = Counter()
    station_kinds = Counter()
    n_station_bills = 0
    # The journey against the status and the rail, counted per term.
    j_tally, j_current = Counter(), []
    # Which bills' dockets move each amendment number, so that an amendment
    # the calendar printed under another bill is known for that bill's.
    claims = amendment_claims(narratives)
    # The journals the drain fetched, for a House Journal record's citations:
    # read once, and only if a bill needs them.
    _jk = {}

    def _jkeys():
        if "keys" not in _jk:
            _jk["keys"] = journal_keys_from_queue()
        return _jk["keys"]
    for bid, b in ((k, v) for byb in bills.values() for k, v in byb.items()):
        # New Hampshire sits in two-year terms beginning in odd years. Bill
        # numbers are unique across the whole term, so the term -- not the year
        # -- is the unit a number identifies within, and it has to be known
        # before anything is looked up by bill number.
        year = int(b.get("lsr_year") or 0)
        term = P.term_of(str(year)) if year else ""
        rcs = rollcalls.get(term, {}).get(bid, [])
        tdb = testimony_db.get(term, {}).get(bid)
        narr = narratives.get(term, {}).get(bid)
        # Only for the term these files describe; see the loop header.
        own = term == current
        # An archived term reads its own term out of bill_status.json, and
        # falls back to the statuses carried on the bill record itself -- put
        # there by build_data from the General Court's own search, in the same
        # vocabulary classify_stated already reads -- for a term the file does
        # not hold yet.
        st = P.per_term(status_pages, term, current).get(bid, {})
        # A BLANK FIELD IS NOT AN ANSWER. bill_status.json comes from the
        # status pages and leaves fields empty or null -- HB 523 of 2023 has
        # no House status there -- while data/bills.json carries what the
        # General Court's own search said about the same bill, in the same
        # vocabulary ("INEXPEDIENT TO LEGISLATE"). The page's value wins
        # where it has one; where it has none, the record fills it. Without
        # this, 79 bills killed by their chamber fell through to a status
        # derived from the docket, which called them "In committee".
        fields = ("gen_status", "house_status", "senate_status", "text_pdf")
        if not st and not own:
            st = {k: b.get(k, "") for k in fields}
        elif st:
            st = {**st, **{k: b.get(k) for k in fields
                           if not (st.get(k) or "").strip() and b.get(k)}}
        dl = (chapters or {}).get(term, {}).get(bid) or {}
        db_st = fill_status_from_db(st, b, bid, term, current)
        # A CACR's row of ballot_results.json: the statewide vote on it.
        ballot = (ballots or {}).get((term, bid))
        disp = bill_disposition(
            b, bid, st, narr, rcs, term, current,
            term_over=bool(session_over) and term == current,
            law_line=dl.get("line", ""),
            override_failed=dl.get("override_failed", ""),
            # What the database says where the page states nothing, for a
            # status that would otherwise be this site's guess.
            db_st=db_st,
            # A CACR's own text names the election it goes to, which is
            # what decides whether it "goes" or "went" to the voters.
            text=((P.per_term(bill_texts, term, current).get(bid) or {}).get("text", "")
                  if bill_prefix(bid) == "CACR" else ""),
            # And the voters' answer, where the docket records none.
            ballot=ballot)
        kind, status = disp.kind, disp.status
        told, settled, prefix = disp.told, disp.settled, disp.prefix
        n_stated += disp.stated
        n_stale += disp.stale
        n_db += disp.source == PAST_SOURCE

        # Sponsor records already carry member_id, party and chamber from
        # build_data.py, and for the LsrSponsors path that id IS the roster's.
        # The bill-status fallback path carries a web member id from a
        # different space, so that one falls back to matching on the name.
        # The sitting roster AND the members who left mid-term, because this
        # is the one lookup whose answer decides whether a sponsor's name is a
        # link. Everything else in this function stays on `legs`: a former
        # member belongs in a sponsor list, not in a roster.
        sp_list = bill_sponsor_list(bid, b, year, term, current,
                                    sponsors, _people, leg_by_sort,
                                    leg_by_name, sponsored, seats,
                                    left=_left if term in term_rosters else None,
                                    term_roster=term_rosters.get(term))
        prime = next((s for s in sp_list if s.get("prime")), sp_list[0] if sp_list else None)
        years.add(year)
        ev = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
        dates = action_dates(ev)
        # Filed one year, acted on the next: retained in committee or sent to
        # interim study. These are exactly the bills someone loses when they
        # search the current year and the bill was filed in the previous one.
        # Counted from the bill's introduction, once the journey below has
        # read it (carried_over).
        carried = carried_over(dates)
        # NOT A BILL THAT WAS NEVER INTRODUCED. Its "To Be Introduced" row is
        # dated the day it was typed, in the December before -- HB 1308 of
        # 2010's on 10 December 2009 -- and two years of rows made it a bill
        # "carried over" from a session it was never in.
        if status in NEVER_INTRODUCED or (narr or {}).get("not_introduced"):
            carried = False
        # "General Court docket" where a dated docket line decided the status
        # over the fields: settled (the governor, a veto), or between the
        # chambers (a refusal to concur, a conference report voted down, a
        # resolution the second chamber adopted).
        # "House Journal" where the bill is in none of the General Court's
        # files and the journal is its record (journal_story) -- and where
        # the journal's resolution of introduction is what says the bill was
        # not introduced (NOT_INTRODUCED).
        # "General Court database" where the fields that state it are the
        # database's own, on a record build_data made from it: no status page
        # was read for that bill.
        status_source = (
            JOURNAL_SOURCE if disp.source == JOURNAL_SOURCE or status == NOT_INTRODUCED
            else "General Court docket" if settled or disp.between
            else PAST_SOURCE if told and (b.get("source") == PAST_SOURCE
                                          or disp.source == PAST_SOURCE)
            else "General Court bill status page" if told
            else "derived from the docket")
        # A CACR'S VOTERS ARE NOT ON ITS STATUS PAGE, which stops at the
        # second chamber: "ratified" or "not ratified" was its docket's
        # referendum line where it has one, and the ballot row's count against
        # two thirds where it has not. Credited to the status page on all
        # eighteen until the review of 5 October 2026.
        if status in (RATIFIED, NOT_RATIFIED) and status_source in (
                "General Court bill status page", "derived from the docket"):
            status_source = ("General Court docket"
                             if any(REFERENDUM.search(e.get("raw") or "") for e in ev)
                             else BALLOT_SOURCE)
        # Committees carry their chamber. Both chambers have a Finance, a
        # Judiciary and a Ways and Means, and the ones that differ differ
        # slightly -- Senate "Health and Human Services" against House "Health,
        # Human Services and Elderly Affairs" -- which is worse than a
        # collision, because it looks like a typo rather than two committees.
        #
        # A bill also gets BOTH where it has both. The old line took the House
        # committee or the Senate one, so a Senate bill's own committee vanished
        # from the facets the moment it crossed over and was referred in the
        # House. Filtering for the committee that actually heard it found
        # nothing.
        # ONE SPELLING PER COMMITTEE, the same rule the sponsor facet already
        # follows below. The archived bill records write a committee in
        # capitals -- "COMMERCE, LABOR AND CONSUMER PROTECTION", "WILDLIFE &
        # RECREATION", 28 of them across the terms before about 2015 -- and
        # the current term writes it in title case. Same committee, two
        # spellings, and the facet listed both.
        cmte, cmtes = bill_committees(b, bid)
        chapter = chapter_of(st, (chapters or {}).get(term, {}).get(bid),
                             n_chapter)
        # HOW IT GOT HERE, from the docket: every floor decision, dated. The
        # rail's marks are read with it and the rail's dates are read from
        # it, so the list card, the bill's own rail and On the record are
        # one account. journey_disagrees() is the test that they are.
        untold = set()
        intro, jsteps = journey(narr, bid, rcs, chapter, dl.get("line", ""), term,
                                db_effective=dl.get("database_effective", ""),
                                untold=untold)
        # THE VOTERS' LINE, where the docket has none to read it from: the
        # election and its outcome, from the CACR's ballot row. The rail's
        # Voters stop is dated from it like every other stop.
        voters = ballot_card(ballot, narr) if ballot else None
        if (ballot and ballot.get("yes") is not None
                and not any(s_["body"] == "V" for s_ in jsteps)):
            jsteps.append(ballot_step(ballot))
        # AND WHERE THE DOCKET'S OWN REFERENDUM COUNT IS NOT THE CARD'S, its
        # line says whose it is, and whose the card's is: CACR 7 of 1992's
        # How it got here read "249,759–204,475" a tab away from the Votes
        # card's 204,457, with nothing to say which was which (the review of
        # 5 October 2026). Now CACR 22 of 1998: the docket's 159,439 against
        # the Secretary of State's 169,439 (docket_count_differs).
        elif (voters or {}).get("docket"):
            for s_ in jsteps:
                if s_["body"] == "V":
                    s_["text"] += docket_count_differs(ballot)
        if carried:
            carried = carried_over(dates, intro)
        # A BILL WHOSE RECORD IS THE HOUSE JOURNAL'S has no docket for the
        # journey to read; its introduction and withdrawal are the journal's,
        # and so are its dates (journal_story).
        story = journal_story(b, _jkeys()) if disp.source == JOURNAL_SOURCE else None
        if story:
            intro, jsteps, dates = story["intro"], story["steps"], story["dates"]
            carried = len({d_[:4] for d_ in dates}) > 1
        # The paragraph for an ending the history does not narrate, made while
        # the journey's lines are still the ones `untold` names.
        ending = None if story else closing_stage(
            status, narr, decided=any(s_["body"] in ("H", "S") for s_ in jsteps),
            steps=jsteps, inferred=disp.source == ENDED_WITH_TERM, untold=untold,
            journal=CONFERENCE_NOT_REPORTED.get((term, bid), ""))
        row = bill_index_row(
            bid, b, year, term, cmte, cmtes, disp, prime,
            narr, rcs, coverage, carried, dates, chapter,
            passed={c for c in ("H", "S") if journey_state(jsteps, c) == "p"},
            acted=list(dict.fromkeys(s["body"] for s in jsteps
                                     if s["body"] in ("H", "S"))),
            live=own and not session_over)
        # NO RAIL FOR A BILL THAT WAS NEVER INTRODUCED. The rail's first stop
        # is "Introduced", drawn as passed, and its second is a chamber the
        # bill is shown stopping in. A bill the Senate refused to introduce,
        # one withdrawn before the day it was to be introduced, one only ever
        # proposed for a session, entered neither: its status says what
        # became of it, its history says when, and a rail would say it was
        # introduced. narrative.build says which dockets say so
        # (not_introduced); the status says it for a field (NEVER_INTRODUCED).
        if status in NEVER_INTRODUCED or (narr or {}).get("not_introduced"):
            row["passage"] = ""
        # AN "ENROLLED" ROW ON A BILL A CHAMBER ENDED IS NOT A DAY IT WAS ACTED
        # ON (enrolled_untold). Asked here because the rail is what says the
        # bill ended in a chamber: SB 286 of 2025's last action is the day the
        # Senate killed it on its table, and it was not carried into 2026.
        unenrolled = [] if story else enrolled_untold(narr, kind, row["passage"])
        ended_in = ""
        if unenrolled:
            rail_ = row["passage"]
            ended_in = {"H": "House", "S": "Senate"}[
                rail_[0] if rail_[1] == "x" else "S" if rail_[0] == "H" else "H"]
            dates = action_dates([e for e in ev if not any(e is u for u in unenrolled)])
            row["last_action"] = dates[-1] if dates else ""
            row["carried"] = bool(row["carried"]) and carried_over(dates, intro)
        index.append(row)
        jrail = journey_rail(intro, jsteps, row["passage"], bid, status)
        # The same stops on the list card, from the start (index_rail).
        if jrail:
            row["rail"] = index_rail(jrail)
        why = journey_disagrees(jsteps, kind, status, row["passage"], bid)
        j_tally[(term, "empty" if not jsteps else "disagree" if why else "agree")] += 1
        if why and term == current:
            j_current.append(f"{bid}: {why}")
        for s_ in jsteps:
            s_.pop("short", None)
            # The Law stop has taken its day (law_day); the line keeps its words.
            s_.pop("effective", None)
        # NOR DO THE RECORD'S STOPS (RAIL_CODE): the rail draws a day and no
        # words, and the page says each stop in its own `say`. The index row
        # keeps its copy, the only one a card has to say before the record.
        for s_ in jrail:
            s_.pop("short", None)

        # ---- one detail file per bill, loaded only when expanded
        # ---- the official documents behind this bill --------------------
        # Every one of these is a page or a PDF the General Court publishes.
        # They are already scattered across the tabs -- a text link in the
        # header, a citation on a timeline row, a calendar name under a
        # committee report -- and somebody who wants the source rather than
        # the summary has to hunt for them. Gathered in one place, with the
        # thing each one actually is written next to it.
        # Every committee report on this bill, dated and in order, with
        # the Senate's alongside the House's. Computed here because the
        # Documents list below cites the same calendars.
        rep_written, rep_docket, rep_actions = committee_reports(
            reports.get(term, {}).get(bid, []), narr, sources,
            b.get("house_committee", ""), b.get("senate_committee", ""))

        docs, text_url = bill_documents(b, bid, st, narr, sources,
                                        rep_written, rep_docket)
        # The journals a House Journal record cites, in place of the docket's.
        for _lab, _url in (story or {}).get("docs", []):
            if _url not in {x["url"] for x in docs}:
                docs.append({"label": _lab, "url": _url, "kind": "record"})

        bill_amds = bill_amendments(narr, amend_texts, claims.get(term, {}))
        btext = bill_text_block(P.per_term(bill_texts, term, current).get(bid))

        rc_out = bill_rollcalls(bid, term, rcs, narr,
                                votes_by_bill, legs, unnamed)
        for r in rc_out:
            r.pop("_ord", None)

        # Two short builders, defined together above main(). Committee
        # proceedings and floor appearances are different enough to need
        # different code and close enough that a change to one usually belongs
        # in the other; adjacent functions make that visible, which one long
        # function did not.
        stations = bill_stations(bid, term, procs, segs, marks)
        # A SITTING SET FOR A DAY AFTER THE BILL WAS WITHDRAWN DID NOT TAKE
        # IT UP. The proceedings table reads the docket's notices -- "Public
        # Hearing: 1/12/2012 10:30 AM LOB 207", entered on 15 December -- and
        # HB 1284 of 2012 was withdrawn on 4 January. narrative.build dates
        # the withdrawal and tells such a notice as one; here the notice is
        # not drawn as a hearing the committee held.
        # NOR DID ONE SET FOR A BILL THAT WAS NEVER INTRODUCED, withdrawal or
        # none: no committee was sent it. HB 273 of 2017 has no withdrawal on
        # its docket and one notice, "Public Hearing: 01/10/2017 01:30 PM LOB
        # 306", and was drawn a station for a hearing nothing on disk says
        # was held. Its history tells the notice as the docket's.
        # The rule is proceedings.notice_only, and the committee's page, the
        # download and the Learn pages' count ask it of the same rows, so none
        # of them says a committee sat where this page draws nothing.
        # And a meeting a later row of the docket cancelled or moved, by its
        # kind and hour, which leaves the rest of its day drawn.
        stations = [x for x in stations
                    if not P.notice_only({"date": x.get("when"), "kind": x.get("what"),
                                          "time": x.get("time"), "body": x.get("body")},
                                         narr)]
        # The sign-in counts, on the hearing itself. They already reach the
        # docket line that records the hearing -- 2,115 of them across 2,018
        # bills -- but that line sits inside a collapsed disclosure on another
        # tab, so somebody wanting to know how opinion stood before a hearing
        # had to go looking for it among the raw docket actions.
        #
        # Matched on the date, so the figure belongs to THIS hearing. Where
        # the database has the bill but not this date, nothing is attached
        # rather than the whole-bill total: on a station the reader is looking
        # at one sitting, and a number that quietly means something else is
        # worse than no number. The docket line still shows the whole-bill
        # figure and still says that is what it is.
        if tdb:
            _by_date = {h.get("date"): h for h in (tdb.get("hearings") or [])}
            for _st in stations:
                if "hearing" not in (_st.get("what") or "").lower():
                    continue
                _hit = _by_date.get(_st.get("when"))
                if _hit:
                    _st["testimony"] = {**_hit, "dated": True}
        # The Senate committee's own report of the hearing, on the station
        # for that hearing: the same bill, the Senate, a public hearing, the
        # date the report gives. A report whose hearing the docket does not
        # carry is not pinned to some other sitting: it stands under its own
        # date, says so, and is named in the build's output. Before the sort
        # below, so it takes its place in the bill's order of events.
        attach_hearing_reports(
            stations, (hearing_reports or {}).get(term, {}).get(bid, []),
            bid, _hr_term.get(term, _hr_idx), _hr_name, hr_tally, hr_unmatched,
            pages=_people if term in _hr_term else None)
        # Floor debates, stacked with the committee proceedings and sorted by
        # date so a bill's whole journey reads in order: hearing, executive
        # session, floor, then the second chamber.
        # A conference noticed and recorded is one sitting, not two stations
        # a day (fold_conference_notices).
        stations += [station_for_floor(f, bid, marks)
                     for f in fold_conference_notices(floor.get((term, bid), []))]
        stations.sort(key=lambda x: (x["when"], x.get("time") or ""))
        # The census, taken after the sort so it counts exactly the list the
        # page receives -- including the floor stations, which is the half of
        # the record five tools in one day were found to be missing.
        if stations:
            n_station_bills += 1
        for _st in stations:
            _state = str(_st.get("state") or "?")
            station_states[_state] += 1
            station_kinds[str(_st.get("what") or "?")] += 1
            # THE FOUR GROUPS A READER ACTUALLY MEETS, which are not the
            # eleven state names. Either the page puts you at the moment the
            # bill was taken up; or it offers the recording and says it has
            # not established the moment; or the bill went through on a
            # consent calendar and there is no moment to find; or there is no
            # recording to offer.
            #
            # Taken from the station itself rather than from a list of state
            # names, because the states do not divide on this cleanly: a
            # "floor_dated" station has a stated start on the few occasions
            # the clerk's reading of the committee report was found and none
            # on the rest, so a list would have to know that. The two
            # exceptions are named because they are claims the station's own
            # fields do not carry: "whole_video" needs no start, the recording
            # being the proceeding; and "candidates" has no video_id yet draws
            # every recording the sitting could be, which is an offer of
            # recordings and not the absence of one.
            if _st.get("start") is not None or _state == "whole_video":
                station_states["_placed"] += 1
            elif _state == "consent":
                station_states["_consent"] += 1
            elif _st.get("video_id") or _state == "candidates":
                station_states["_recording_only"] += 1
            else:
                station_states["_no_recording"] += 1

        # Under the filing year, because a bill number is unique within a term
        # and not beyond it. A 2027 HB686 is a different bill from this one and
        # would have overwritten it here, taking its docket, its votes and its
        # recordings with it. The static page and the feed have carried the
        # year in their paths from the start -- build_bill_pages says why, in
        # as many words -- and both of them read THIS file, so the year they
        # were keeping the pages apart by was doing nothing for the data.
        _bd = out / "bills" / str(year)
        _bd.mkdir(parents=True, exist_ok=True)
        (_bd / f"{bid}.json").write_text(json.dumps({
            "id": bid, "year": year, "term": term,
            "title": b.get("title", ""),
            # The stages' text run together; of the stages as they are told,
            # where one of them is told without its enrolment (stages_told).
            "narrative": (" ".join(s_["text"] for s_ in
                                   stages_told(narr, kind, row["passage"]))
                          if unenrolled else (narr or {}).get("narrative", "")),
            # The history, plus a closing paragraph where the bill's ending
            # is only on the status page. 120 bills showed a settled headline
            # over a story that stopped at the committee report.
            "stages": (story["stages"] if story else
                       stages_told(narr, kind, row["passage"])
                       + ([ending] if ending else [])),
            # Where the record comes from, on a bill the House Journal alone
            # carries; the docket's own notes everywhere else.
            # And where the record itself comes from, on the few that are not
            # of the bill search's own list (record_notes).
            "notes": (story["notes"] if story else
                      (narr or {}).get("notes", [])
                      + record_notes(b, narr, status_source, sp_list, term, bid,
                                     (btext or {}).get("version", ""))),
            # Belongs on the Votes tab, not above the history.
            # NOT OVER THE TOP OF THE ROLL CALLS. narrative counts the
            # floor votes the DOCKET records as voice or division votes; the
            # table under this note comes from RollCallSummary, which knows
            # votes the docket line does not mention. On 7,872 bills the note
            # said "there is no record of how individual legislators voted"
            # directly above the record of how they voted. The partial form
            # ("3 of the floor votes were voice votes") is still true beside
            # them and is kept.
            "vote_note": vote_note_for(narr, rc_out),
            # Each action keeps the citation it ends with -- "HJ 7 P. 55" -- and
            # the URL of that journal or calendar where we have it. That is the
            # official record of the line being displayed, and it is the thing
            # that makes a claim on this site checkable rather than trusted.
            # A DATE A PERSON CORRECTED (docket_corrections.json) is shown on
            # the day it happened, beside the clerk's line, which still says
            # the other date -- so the line carries why, in plain words.
            "events": [{"date": e["date"], "text": listed_line(e),
                        "routine": is_routine(docket_line(e)),
                        **({"date_as_recorded": e["date_as_recorded"],
                            "date_note": e.get("date_note") or (
                                "The General Court's online docket gives "
                                "another date for this; the journal and the "
                                "other records of the sitting place it on the "
                                "date shown.")}
                           if e.get("date_as_recorded") else {}),
                        # An "Enrolled" row on a bill a chamber ended, with
                        # why the history does not tell it (enrolled_untold).
                        **({"row_note": ENROLLED_NOT_TOLD.format(chamber=ended_in)}
                           if any(e is u for u in unenrolled) else {}),
                        # A row that calls a meeting off (called_off), which
                        # the history does not tell, with why; the feeds
                        # leave it out by the same mark (build_feeds), as the
                        # Documents tab does. A cancelled row of another kind
                        # (marked_cancelled) carries the same mark, so it is
                        # left out of both in the same way, and its own note.
                        **({"row_note": CANCELLED_NOT_TOLD if called_off(e)
                                        else CANCELLED_ROW_NOT_TOLD,
                            "called_off": True}
                           if marked_cancelled(e) else {}),
                        # A ROW FILED UNDER THE WRONG BILL (docket_corrections
                        # .json "misfiled") is listed here, with its note, and
                        # nowhere else on the page; the bill it belongs to
                        # carries a note on its own row of the same vote.
                        **({"row_note": e["row_note"]} if e.get("row_note") else {}),
                        # A meeting row told as a notice (docket_lines): the
                        # Hearings tab says the docket noticed one where it
                        # draws none.
                        **({"notice": True} if e.get("notice") else {}),
                        # The sign-ins belong to the hearing's notice, which
                        # carries them; a row calling it off does not repeat
                        # them.
                        **({} if marked_cancelled(e) else hearing_testimony(
                            e, tdb, testimony.get(bid) if own else None)),
                        **_cite(e, sources,
                                e.get("cite_year") or (e.get("date") or "")[:4])}
                       for e in docket_lines(narr)],
            # Prefer what the General Court says over what we would infer.
            # Where the docket has settled the bill, the per-chamber fields
            # are describing a superseded state and reading them beside
            # "Vetoed, override failed" is a contradiction. Say what happened.
            # A CLOSED TERM HAS NOTHING PENDING. next_step reads the last
            # recognised event, and on an archived bill that is often a
            # committee report or a conference that never reported, so the
            # box read "In progress" or "Pending a vote of the full chamber"
            # under a chip saying what became of the bill -- 488 bills once
            # the 1989-2016 histories arrived. The chip's own words are the
            # answer there. In any term, a line claiming another kind of
            # status than the chip's gives way to it (STEP_CLAIM).
            "next_step": (status if story else settled_step(
                # With the database's fields where they are what stated it.
                bill_next_step(narr, b, prefix,
                               db_st if disp.source == PAST_SOURCE else st, settled, told),
                status, term, current, kind)),
            **({"archived": (coverage or {}).get(term) or True}
               if b.get("archived") else {}),
            # Where the status is from (computed above, beside the status).
            "status_source": status_source,
            "chapter": chapter,
            # HOW IT GOT HERE: each chamber's floor decisions, the governor,
            # the chapter and a CACR's referendum, dated, one line each; and
            # the stops of the rail, dated from them -- the rail the list
            # card draws too, from the index row's copy (index_rail).
            **({"journey": {"steps": jsteps, "rail": jrail}}
               if jsteps or jrail else {}),
            # THE VOTERS' VOTE on a CACR they were sent, for its Votes tab:
            # the election, the two counts and the outcome, or the day of an
            # election still to come (ballot_card), made above with the
            # voters' line of How it got here.
            **({"ballot": voters} if voters else {}),
            # Named for what it is rather than for the format the
            # scrape guessed at: the General Court's own text of
            # this bill, in the form its status page links to.
            "text_url": text_url,
            # The rest of what the status page states. All of it was being
            # fetched and thrown away; the detail page is where it belongs,
            # since these are the facts someone reads when the summary card is
            # not enough.
            "facts": {k: st[k] for k in
                      ("lsr", "body", "local", "gen_status", "house_status",
                       "senate_status", "date_introduced", "floor_date",
                       "committee_code") if st.get(k)},
            # THE END OF A BILL THAT SIMPLY RAN OUT OF DAYS. The record's own
            # word stays in the status -- "Laid on the table", where the chip
            # says Died -- and this says
            # why nothing follows it, on the bills of the current term only:
            # an archived term says the same thing in its coverage note.
            **({"session_over": session_over}
               if session_over and term == current and disp.stale else {}),
            # What the committee reported on a bill taken for interim study.
            **({"study_report": study_report(narr)} if study_report(narr) else {}),
            "sponsors": sp_list, "rollcalls": rc_out, "stations": stations,
            "reports": rep_written,
            # Reports the docket records that no calendar this site has
            # read printed the reasoning for. Almost all of them are the
            # Senate's, which files one report with a vote and no
            # minority -- the shape the tab used to say was not loaded.
            "docket_reports": rep_docket,
            # What the chamber did between one report and the next.
            "report_actions": rep_actions,
            # Why the governor vetoed it, in her own words, from the House
            # calendar the message was read into. The docket records that a
            # bill was vetoed and the date; it does not record the reasons,
            # and the reasons are the whole of a veto message.
            "veto_message": P.per_term(vetoes or {}, term, current).get(bid),
            # A standing note about what this bill IS, where its number
            # carries a meaning across terms. Written by a person, and the
            # page labels it as this site's words rather than the General
            # Court's -- the same line the veto message draws from the other
            # side, where the words are quoted and attributed.
            "bill_note": bill_note(notes, term, bid),
            "subject": b.get("subject", ""),
            "subject_source": b.get("subject_source", ""),
            "house_committee": names.committee(b.get("house_committee", "")),
            "senate_committee": names.committee(b.get("senate_committee", "")),
            "lsr": b.get("lsr", ""),
            # None for a House Journal record: the address is built from the
            # LSR, which such a bill does not have; whether the General
            # Court's page has it was never asked.
            "docket_url": ("" if b.get("journal") else
                           "https://gc.nh.gov/bill_status/legacy/bs2016/bill_docket.aspx"
                           f"?lsr={b.get('lsr_num','')}&sy={b.get('lsr_year','')}"
                           f"&txtsessionyear={b.get('lsr_year','')}"
                           f"&txtbillnumber={bid.lower()}&sortoption=billnumber"),
            "documents": docs,
            # The amendments this bill went through, in the order they were
            # taken up, with the text where the calendars printed it.
            "amendments": bill_amds,
            # The bill itself, as the General Court publishes it.
            "billtext": btext,
            # HOW MANY VERSIONS THIS BILL HAS, from the manifest
            # build_bill_versions.py writes before this step runs. Only 1,149
            # of 2,234 bills have a second version, so without this the page
            # would draw a Versions tab on every bill and put a 404 behind
            # 1,085 of them. The texts and the diffs themselves are fetched
            # when the tab is opened; this is only the count.
            "nver": (VERSIONS.get(str(year), {}).get(bid, {})
                     .get("versions", 0)),
            "namd": (VERSIONS.get(str(year), {}).get(bid, {})
                     .get("amendments", 0)),
            # Statutes cited in the committee's own words and in the bill's
            # title. Committee reports cite the RSAs constantly, and a reader
            # who has to leave to find out what 91-A says usually does not
            # come back.
            # Amendment text as well as report text. An amendment is mostly
            # statute citations by volume -- "Amend RSA 415:6-e, III(a)" is
            # how one opens -- so leaving it out meant the linker missed the
            # place it was most useful.
            "rsa": rsa_links(b.get("title", ""),
                             *[e.get("text", "") for r in rep_written
                               for e in r.get("reports", [])],
                             *[x.get("text", "") for x in bill_amds],
                             # And the bill, which is mostly statute citations
                             # by weight -- it is the document the linker was
                             # built for.
                             (btext or {}).get("body", "")),
            # WHICH STATUTES THIS BILL CHANGES, as against which it cites.
            # "rsa" above is the linker's map and stays as it is: a citation
            # anywhere -- a committee report, an amendment, the analysis --
            # should become a link. This is the CLAIM, and the page prints it
            # as "Amends RSA chapters".
            #
            # The bill's own text and nothing else. A committee report's
            # citations are commentary and an amendment's are a proposal --
            # 546 of them were being read as amendments -- and the text on
            # file is the version that carries the amendments that were
            # adopted. A bill with no text on disk gets no row rather than a
            # row inferred from either.
            "amends": bill_amends((btext or {}).get("body", "")),
        }), encoding="utf-8")

    if status_pages:
        print(f"  {n_stated:,} bills take their status from the page; "
              f"{len(index) - n_stated:,} still derive it from the docket")
        if n_stale:
            print(f"  {n_stale:,} bills in closed terms read as still moving "
                  "and are marked finished;")
            print("    the status word the record gave them is unchanged")
    # THE CHIPS, counted as they were written: a build whose chips came out
    # all one word, or none of the six, says so in its own output.
    chips = Counter(r["chip"] for r in index)
    print("  chips: " + ", ".join(f"{w} {chips[w]:,}" for w in CHIP_WORDS)
          + f"; {sum(v for k, v in chips.items() if k not in CHIP_WORDS):,} keep a "
          "still-moving stage or a word that is not one of the six"
          + (f" (the session of {current} ended {session_over}, so none is Tabled or Vetoed)"
             if session_over else ""))
    # What the database's dump answered, or that it is not here: a dump that
    # is missing looks exactly like one with nothing to add. main() says the
    # second again as its last line, which is the one build_all shows.
    held = sorted(t for t, rows in _DB_STATUS.items() if rows)
    print(f"  {n_db:,} bills take their status from the database's own code, where the "
          "status page states nothing and the docket gives only a guess (a dump holds "
          f"{', '.join(held) or 'no term'})")
    if no_dump_for(current):
        print("  " + no_dump_for(current))
    # THE JOURNEY, THE STATUS AND THE RAIL, AS ONE ACCOUNT. A build that drew
    # a list contradicting the chip above it would otherwise exit zero.
    j_all = Counter()
    for (t_, k_), v_ in j_tally.items():
        j_all[k_] += v_
    print(f"  journey: {j_all['agree']:,} bills agree with their status and "
          f"rail, {j_all['disagree']:,} do not, {j_all['empty']:,} have no "
          f"floor decision on record; this term: "
          f"{j_tally[(current, 'agree')]:,} / {j_tally[(current, 'disagree')]:,}"
          f" / {j_tally[(current, 'empty')]:,}")
    for line in j_current[:10]:
        print(f"      {line}")
    if n_chapter:
        print(f"  chapter of the session laws: {n_chapter['the status page']:,}"
              f" from the status page, {n_chapter['the docket']:,} from the "
              f"docket; {n_chapter['differ']} where the two differ (the "
              f"page's field shown), {n_chapter['withheld']} withheld")

    # THE ABOUT PAGE'S ARITHMETIC, written here rather than in main() because
    # this is the function that holds the counter. station_states above says
    # why it is counted at all.
    #
    # The four group totals share the counter, so the sum of everything in it
    # is twice the number of stations. Counted off the state names instead --
    # the ones a station actually carries, which never begin with "_".
    _n_stations = sum(v for k, v in station_states.items()
                      if not k.startswith("_"))
    # Written under site/ beside the other build products. Nothing fetches it;
    # build_pages.py runs next in the pipeline and writes about.html from it.
    (out / "station_census.json").write_text(json.dumps({
        "total": _n_stations,
        "bills": n_station_bills,
        "placed": station_states["_placed"],
        "recording_only": station_states["_recording_only"],
        "consent": station_states["_consent"],
        "no_recording": station_states["_no_recording"],
        "by_state": {k: v for k, v in station_states.most_common()
                     if not k.startswith("_")},
        "by_kind": dict(station_kinds.most_common()),
    }, indent=1), encoding="utf-8")
    print(f"  station census: {_n_stations:,} stations across "
          f"{n_station_bills:,} bills "
          f"({station_states['_placed']:,} placed at the moment, "
          f"{station_states['_recording_only']:,} recording only, "
          f"{station_states['_consent']:,} consent calendar, "
          f"{station_states['_no_recording']:,} no recording)")
    if hearing_reports:
        _offered = sum(len(v) for byb in hearing_reports.values()
                       for v in byb.values())
        print(f"  Senate hearing reports: {hr_tally['matched']:,} of "
              f"{_offered:,} placed on their hearing "
              f"({hr_tally['plain']:,} drawn as plain text); "
              f"{hr_tally['members']:,} legislators who testified drawn as "
              f"members, {hr_tally['members_unresolved']:,} left as the "
              "report printed them")
        if hr_unmatched:
            # Named, not just counted: each is a report whose date the docket
            # does not carry, shown under that date on a station of its own
            # (report_station), and the docket for that bill says what it
            # has instead.
            print(f"  {len(hr_unmatched):,} found no Senate public hearing "
                  "of that bill on that date in proceedings.csv, and are "
                  "shown under the report's own date: "
                  + ", ".join(hr_unmatched))
    return index, years, unnamed, dict(sponsored)


def parse_args():
    """Everything this script can be pointed at, and what it defaults to.

    Lifted out of main so that what is left there is the work rather than
    thirty lines of defaults. The defaults are the interesting part and
    they carry their own warnings: --segments is "work" and not
    "segments", because the aligner writes work/<videoid>/segments.json
    and a bare run once built a site with no video timestamps on it at
    all, then reported the cause as a session-year mismatch.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--narratives", default="narratives.json")
    ap.add_argument("--rollcalls", default="rollcalls.json")
    ap.add_argument("--notes", default="bill_notes.json",
                    help="hand-written standing notes about particular bills")
    ap.add_argument("--markers", default="candidate_segments.json",
                    help="boundaries a chair stated, from segment_markers.py")
    ap.add_argument("--allow-no-manifest", action="store_true",
                    help="build anyway, with no committee proceedings at all")
    # "work", not "segments". The aligner writes work/<videoid>/segments.json
    # and every other default here names the file it will actually find, so a
    # bare run of this script quietly built a site with no video timestamps on
    # it at all -- and then reported the cause as a session-year mismatch,
    # which sent the diagnosis in the wrong direction entirely.
    ap.add_argument("--segments", default="work")
    ap.add_argument("--caption-spans", default=caption_span.SUMMARY,
                    help="where each recording's captions stop, for a machine "
                         "without the caption files (caption_span.py --write)")
    ap.add_argument("--reports", default="committee_reports.json")
    ap.add_argument("--report-corrections", default="report_corrections.json",
                    help="House reports the calendar printed under another "
                         "bill, from report_check.py; skipped if not there")
    ap.add_argument("--vetoes", default="veto_messages.json",
                    help="governor's veto messages, from extract_vetoes.py; "
                         "skipped if the file is not there")
    ap.add_argument("--senate-reports", default="senate_reports.json")
    ap.add_argument("--hearing-reports", default="senate_hearing_reports.json",
                    help="the Senate committees' hearing reports, from "
                         "senate_hearing_reports.py; skipped if not there")
    ap.add_argument("--chapters", default="chapters.json",
                    help="the chapter each bill became, from "
                         "extract_chapters.py; skipped if not there")

    ap.add_argument("--status", default="status/status.txt")
    ap.add_argument("--districts", default="site/districts.json")
    ap.add_argument("--officials", default="status/officials.txt")
    ap.add_argument("--out", default="site")
    return ap.parse_args()


def load_transcripts(a, procs, prows):
    """The aligner's segments and the chair's stated boundaries.

    Returns (segs, marks). `prows` is the raw proceedings rows, passed in
    rather than reloaded, because P.load() is not free and two readings of
    it could disagree. Both are read off captions, and a caption
    track can be an hour out of step with its recording, so the
    withholding and the checks below belong with the loading rather
    than apart from it: a silent mismatch here looks exactly like poor
    alignment accuracy, with every hearing reading "start time not
    identified" because the transcripts are for a different set of
    videos than the manifest points at.
    """
    # The aligner writes work/<videoid>/segments.json; an earlier layout used
    # segments/<videoid>.json. Accept either so the site picks them up wherever
    # they are.
    segs = {}
    sp = Path(a.segments)
    if sp.exists():
        for f in sp.glob("*.json"):
            segs[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        for d_ in sp.iterdir():
            f = d_ / "segments.json"
            if d_.is_dir() and f.exists():
                segs[d_.name] = json.loads(f.read_text(encoding="utf-8"))
    print(f"segments loaded for {len(segs):,} videos")

    # Boundaries a chair stated aloud, from segment_markers.py. Measured
    # against the 35 hand-marked proceedings at a median of ONE SECOND, with
    # ends at four -- against 1m 27s for the clustering estimate and 17m 05s
    # for the schedule. Where one of these exists it is not an improvement on
    # the estimate, it is a different kind of claim: a quotation rather than an
    # inference, and the page says so.
    mp2 = Path(a.markers)
    marks = {}
    if mp2.exists():
        try:
            marks = json.loads(mp2.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            marks = {}
    if marks:
        # _absent and _sequence are siblings of the recordings, not recordings,
        # and counting them made the total two higher than the truth.
        vids = {k: v for k, v in marks.items() if not k.startswith("_")}
        nb = sum(len(v) for v in vids.values())
        print(f"{nb:,} stated boundaries across {len(vids):,} recordings "
              f"from {mp2.name}")
    # Both of the above are read off captions, and a caption track can be an
    # hour out of step with its recording.
    withhold_late_captions(segs, marks, a.segments, a.caption_spans)
    # A silent mismatch here looks exactly like poor alignment accuracy: every
    # hearing reads "start time not identified" because the transcripts are for
    # a different set of videos than the manifest now points at.
    if procs:
        man_vids = {r["video_id"] for rs in procs.values() for r in rs
                    if r.get("video_id")}
        overlap = man_vids & set(segs)
        print(f"  manifest references {len(man_vids):,} videos; "
              f"{len(overlap):,} of them have transcripts")
        if man_vids and not overlap:
            print(f"  NONE overlap. Either --segments is pointing somewhere "
                  f"with no transcripts\n  in it (it is {a.segments!r}; the "
                  "aligner writes work/<videoid>/segments.json),\n  or the "
                  "transcripts cover a different set of videos than the "
                  "manifest --\n  most likely a different session year.")
        elif len(overlap) < len(man_vids) * 0.5:
            print(f"  {len(man_vids) - len(overlap):,} manifest videos have no "
                  "transcript; those proceedings get a recording link with no "
                  "start time.")
        # AND THE SITTINGS WITH NO RECORDING CHOSEN AT ALL. 317 of them name
        # the two or three recordings of their committee that day, and the
        # page offers those instead of saying none exists. The number can go
        # to zero silently: a proceedings.csv written before
        # build_proceedings.py carried candidate_ids has no such column, and
        # every one of them goes back to "No recording matched to this
        # proceeding." with nothing in any log to say when it started. A
        # fixture may hold no such rows legitimately, so the alarm is on the
        # column being absent, not on the count being zero.
        no_pick = sum(1 for rs in procs.values() for r in rs
                      if not r.get("video_id"))
        named = sum(1 for rs in procs.values() for r in rs
                    if not r.get("video_id") and r.get("candidate_ids"))
        if named:
            print(f"  {named:,} of the {no_pick:,} proceedings with no "
                  "recording chosen name the recordings they could be")
        elif no_pick and not any("candidate_ids" in r for r in prows):
            print(f"  {no_pick:,} proceedings have no recording chosen, and "
                  f"{P.PATH.name} has no candidate_ids column, so not one of "
                  "them can say a recording of that day exists. Rebuild it "
                  "with build_proceedings.py.")
    return segs, marks


def main():
    a = parse_args()

    D, out = Path(a.data), Path(a.out)
    (out / "bills").mkdir(parents=True, exist_ok=True)
    (out / "legislators").mkdir(parents=True, exist_ok=True)

    bills = load(D / "bills.json", {})
    # {term: {bill: record}} -- the file the whole per-bill loop is driven from.
    # Read flat and the loop would run over term names instead of bills.
    if bills and not P.term_keyed(bills):
        sys.exit(f"{D / 'bills.json'} is keyed on bill number, not on term. "
                 "Rebuild it: python3 src/parse/build_data.py --dir . --out data")
    merge_guessed_topics(bills)
    # LAST, so it catches the General Court's labels and the model's alike.
    unify_vocabulary(bills)
    sponsors = load(D / "sponsors.json", {})
    # The sponsors each bill's own text names, for the bills the database names
    # nobody for: every term before 2023, as the lane saves their pages.
    # text_sponsors.py says how they are matched and what that was measured at;
    # merge_into never replaces a sponsor the database gave.
    _n = TS.merge_into(sponsors)
    if _n:
        print(f"  sponsors: {_n:,} bills named on their own text (text_sponsors.json)")
    # 2023-2024 FROM THE GENERAL COURT'S OWN SPONSOR RECORD, where each bill's printed
    # sponsor line agrees with it, and as the page prints it where they do not. The
    # bill status page this term's list came from left Steve Shurtleff off 29 bills and
    # made him nobody's prime sponsor, and carried no link for 5,900 of its names;
    # past_sponsors.py says what was measured against what. After merge_into, whose
    # page lists it takes for the bills that disagree; before seat_into, which dates the
    # seats on the record's rows as it did on the status page's.
    # AND EVERY OTHER PAST TERM FILLED FROM IT, never replaced: a bill with no
    # sponsor from the database's files, the status pages or its own text takes
    # the record's list (past_sponsors.filled), and a bill with any keeps it.
    _ps = PSP.merge_into(sponsors)
    if _ps:
        print(f"  sponsors: 2023-2024 from the General Court's sponsor record on "
              f"{_ps['record']:,} bills, as the page prints them on {_ps['page']:,}"
              + (f"; {_ps['differs, and no page list to publish']:,} kept the status "
                 "page's, having no page list to take"
                 if _ps['differs, and no page list to publish'] else "")
              + f"; {_ps['filled']:,} bills of the other past terms, which no other "
                "source names a sponsor for, filled from it"
              + " (past_sponsors.json)")
    elif (PSP.PAST / "_manifest.json").exists():
        # Not silent: the dump is here and the file made from it is not, so 2023-2024
        # is being built from the status page the record corrects.
        print("  sponsors: past_sponsors.json is missing though db/past/ is here, so "
              "2023-2024 keeps the bill status page's list. Run python3 "
              "src/parse/past_sponsors.py --apply.")
    # And the seat on a sponsor the database DOES name, dated from the same
    # pages: the database's rows for 2023-2024 carry no county and no
    # district, so the site was taking both from the roster of the House and
    # Senate sitting today. See TS.seat_into. The current term keeps the
    # roster, which for it is the contemporaneous source.
    _seated = TS.seat_into(sponsors, current=max(bills) if bills else None)
    if _seated:
        print(f"  sponsors: {_seated:,} seats dated from the bill's own printed line")
    legs = {m["id"]: m for m in load(D / "legislators.json", [])}
    # Sponsor records carry a name but not a party or a district. The roster
    # has both, so they are joined on the surname-first form of the name --
    # never on a member id, because there are three id spaces in these files
    # and a sponsor's is not necessarily the roster's. A sponsor who matches
    # nobody keeps a bare name rather than borrowing somebody else's party.
    leg_by_sort, leg_by_name = {}, {}
    for _m in legs.values():
        leg_by_sort.setdefault(sort_name(_m.get("name") or ""), _m)
        _k = name_key(_m.get("name") or "")
        if _k:
            leg_by_name.setdefault(_k, _m)

    # Members who left mid-term are already named upstream: resolve_members.py
    # writes former_members.json to the project root, build_data.py reads it
    # there, and every member_votes row therefore carries a resolved "name"
    # whether the member is sitting or not. That is what the double build_data
    # pass in build_all.py exists for. Reading the file a second time here
    # would only add a way for the two to disagree -- and the copy this looked
    # for, under the data directory, is not where the pipeline writes it.
    towns = load(D / "towns.json", {})
    narratives = load(a.narratives, {})
    # {term: {bill: record}}, for the reason rollcalls.json is: a bill number
    # is unique within a term and not across terms. Reading the old flat shape
    # with a term lookup finds nothing for every bill and still exits zero.
    if narratives and not N.is_term_keyed(narratives):
        sys.exit(f"{a.narratives} is keyed on bill number, not on term. "
                 "Rebuild it: python3 src/parse/narrative.py --docket Docket.txt --all "
                 f"--out {a.narratives}")
    # Hand-written, and in the same class as ground_truth.csv: no generator
    # writes it and preflight fails if one opens it for writing.
    notes = load(a.notes, {})
    check_notes(notes, bills)
    rollcalls = load(a.rollcalls, {})
    # {term: {bill: [votes]}}, since rollcall_parser started reading past
    # sessions. The older shape was {bill: [votes]}, and reading one with the
    # new lookup returns nothing for every bill without failing -- the exact
    # shape of silence this project keeps getting caught by. So it is checked.
    if rollcalls and not all(isinstance(v, dict) for v in rollcalls.values()):
        sys.exit(f"{a.rollcalls} is keyed on bill number, not on term. Rebuild "
                 "it: python3 src/parse/rollcall_parser.py --all --out rollcalls.json")
    reports = load(a.reports, {})
    # The Senate's committee reports, with their reasoning, from the General
    # Court's database -- the half the House Calendar PDFs cannot cover. Kept
    # in its own file because fetch_committee_reports.py rebuilds
    # committee_reports.json a calendar year at a time and decides what to keep
    # by looking for ", <year>" in each record's source; a record that is not
    # from a calendar has no business inside that. Merged here instead, which
    # is the one place that has to know both exist.
    # {term: {bill: message}}, and refused in the old flat shape for the same
    # reason every other per-bill file is: a bill number names one bill in each
    # biennium, and a flat file read through a term lookup gives every bill
    # nothing while exiting zero.
    vetoes = load(a.vetoes, {})
    if vetoes and not N.is_term_keyed(vetoes):
        sys.exit(f"{a.vetoes} is keyed on bill number, not on term. "
                 "Delete it and run extract_vetoes.py again.")
    if vetoes:
        print(f"  {sum(len(v) for v in vetoes.values())} veto message(s) "
              f"across {len(vetoes)} term(s)")

    chapters = load(a.chapters, {})
    if chapters and not N.is_term_keyed(chapters):
        sys.exit(f"{a.chapters} is not keyed on term. "
                 "Delete it and run extract_chapters.py again.")

    senate = load(a.senate_reports, {})
    # Both are {term: {bill: [reports]}} now, for the reason every per-bill file
    # is: a bill number is unique within a term and not across terms. Reading
    # the old flat shape with a term lookup gives every bill no reports and
    # still exits zero, so it is refused.
    for name, data in ((a.reports, reports), (a.senate_reports, senate)):
        if data and not N.is_term_keyed(data):
            sys.exit(f"{name} is keyed on bill number, not on term. Rebuild it: "
                     "delete it and run its fetcher once for each year of the "
                     "term.")
    # A House Calendar that printed another bill's report under a heading --
    # 2021 HB 365's majority report was HB 197's -- is corrected from the
    # report the committee filed, before anything else reads the record.
    # report_check.py finds them and says what it did; absent, nothing changes.
    n_fixed = RC.apply(reports, load(a.report_corrections, {}))
    print(f"House committee reports corrected from the committee's filed "
          f"copy: {n_fixed}"
          + ("" if Path(a.report_corrections).exists()
             else f" ({a.report_corrections} is not here; report_check.py writes it)"))
    if senate:
        for term, byb in senate.items():
            into = reports.setdefault(term, {})
            for bid, recs in byb.items():
                into.setdefault(bid, []).extend(recs)
        n_prose = sum(1 for byb in senate.values() for v in byb.values()
                      for r in v for x in r.get("reports", [])
                      if len((x.get("text") or "").split()) >= 15)
        n_bills = sum(len(byb) for byb in senate.values())
        print(f"Senate committee reports: {n_bills:,} bills, "
              f"{n_prose:,} with the committee's reasoning")
    # The Senate's reports of its public hearings: who spoke and what the
    # report says they said. {term: {bill: [report]}}, refused in any other
    # shape for the reason above.
    hearing_reports = load(a.hearing_reports, {})
    if hearing_reports and not N.is_term_keyed(hearing_reports):
        sys.exit(f"{a.hearing_reports} is not keyed on term. Delete it and "
                 "run senate_hearing_reports.py again.")
    if hearing_reports:
        print(f"Senate hearing reports: "
              f"{sum(len(v) for b in hearing_reports.values() for v in b.values()):,}"
              f" across {sum(len(b) for b in hearing_reports.values()):,} bills")
    else:
        # Silence is not success: without this line a hand-run build that
        # never had the file looks the same as one whose reports all landed.
        print(f"Senate hearing reports: NONE -- {a.hearing_reports} is not "
              "here or is empty, so no Hearings tab carries one. "
              "senate_hearing_reports.py writes it.")
    # Written by extract_amendments.py out of the cached calendars. Absent is
    # fine: the amendments are still listed, without their text.
    amend_texts = load("amendments.json", {})
    if amend_texts:
        print(f"{len(amend_texts):,} amendment texts loaded")
    bill_texts = load("bill_text.json", {})
    if bill_texts:
        n = (sum(len(v) for v in bill_texts.values())
             if P.term_keyed(bill_texts) else len(bill_texts))
        print(f"{n:,} bill texts loaded")
    # And the archived pages, for every term before this one. bill_text.json is
    # the current session's own text and holds 2025-2026 alone, so the Bill
    # Text tab was empty on every older bill -- including 2023-2024, whose
    # pages have been on this disk since the archive path was found, fetched
    # and read for their sponsors and then not shown.
    # merge_into never puts an archived page over a text the General Court
    # publishes for the live session, which is the better copy.
    _at = AT.merge_into(bill_texts)
    if _at:
        print(f"  {_at:,} more from their archived pages (archive_text.json)")
    # Journal and calendar URLs, so every docket line can cite its source.
    sources = {**load("calendars.json", {}), **load("journals.json", {})}
    # Every calendar the drain fetched, under its own year, where the files
    # above have no key for that year. What calendars.json already says wins.
    for _k, _u in calendar_keys_from_queue().items():
        sources.setdefault(_k, _u)
    # Sign-in counts, attached to the hearing they were filed for.
    #
    # testimony.json IS RETIRED (5 October 2026), with fetch_testimony's step,
    # at the person's word and on their condition that the counts stay
    # retrievable another way. They do: the scraped file's 565 bills were all
    # in testimony_db.json, so the page never showed one of its counts
    # (hearing_testimony takes it only for a bill the database has nothing
    # for), and testimony_from_db.py rebuilds the database's 2,019 bills of
    # 2025-2026 from the dump, every count and every hearing equal. Kept, the
    # flat file was a leak waiting for the turn: read by number for the
    # current term, 102 of its bills have numbers 2027's first-year bills
    # will reuse, and each would have shown 2025-2026's sign-ins.
    testimony = {}
    # Counts per bill AND per hearing, from the General Court's database:
    # 2,019 bills against the scraped page's 565. Keyed on the term, because
    # legislationID is reused across terms -- joining without that put 67,119
    # sign-ins from 2024 onto 856 bills of this one.
    testimony_db = load("testimony_db.json", {})
    if testimony_db:
        nb = sum(len(v) for v in testimony_db.values())
        ns = sum(r["total"] for v in testimony_db.values() for r in v.values())
        print(f"testimony sign-ins: {ns:,} across {nb:,} bills, per hearing")
    if sources:
        print(f"source links available for {len(sources)} journals and calendars")
    # One table for every proceeding on the site: committee hearings, executive
    # sessions, work sessions, floor debates. Presented below in the two shapes
    # the station code was written against -- manifest columns for committee
    # rows, floor-index keys for floor rows -- so that code did not change.
    # It is the SOURCE that changed. Committee and floor proceedings used to be
    # loaded from two files here, ninety lines apart, and the floor half never
    # saw the markers that had been wired into the committee half.
    prows = P.load()
    if not prows:
        print("=" * 74)
        print("NO proceedings.csv. Every hearing, executive session and floor")
        print("debate on this site comes from that one file. Without it the")
        print("build will finish and publish a site with none of them, and no")
        print("error anywhere to say why.")
        print("")
        print("Run: python3 src/hearings/build_proceedings.py")
        print("=" * 74)
        if not a.allow_no_manifest:
            raise SystemExit("Refusing to build without it. Pass "
                             "--allow-no-manifest to override.")

    # Keyed (term, bill), like everything else per-bill on this site. Keyed
    # on the number alone, and with the per-bill file written per filing
    # year, site/bills/2023/CACR10 carried the 2025-2026 CACR10's hearings
    # and floor debates verbatim -- an archived bill showing another term's
    # recordings. The path was made term-aware and this lookup was not.
    procs = defaultdict(list)
    for r in P.committee_only(prows):
        procs[(r["term"], r["bill"])].append({
            "bill": r["bill"], "body": r["body"], "committee": r["committee"],
            "proceeding": r["kind"], "sched_date": r["date"],
            "sched_time": r["time"], "venue": r["venue"], "match": r["match"],
            "video_id": r["video_id"], "video_title": r["video_title"],
            "stream_start": r["stream_start"],
            "predicted_offset": ("" if r["predicted_offset"] is None
                                 else r["predicted_offset"]),
            # The recordings of this committee on this day that the matcher
            # would not choose between, " | "-joined. Empty on all but 563
            # rows, and it decides a state below on the 317 of those where
            # no recording was chosen at all. .get, because a proceedings.csv
            # written before build_proceedings.py carried the column has no
            # such key.
            "candidate_ids": r.get("candidate_ids") or "",
        })
    floor = defaultdict(list)
    for r in P.floor_only(prows):
        floor[(r["term"], r["bill"])].append({
            "date": r["date"], "body": r["body"], "video_id": r["video_id"],
            "motions": r["motions"], "tallies": r["tallies"],
            "kind": r["kind"], "debate_end": r["debate_end"],
            "window_start": r["window_start"], "precise": r["precise"],
            "whole_video": r["whole_video"], "title": r["video_title"],
            # The docket's time and room, which station_for_floor gives a
            # sitting with no recording. Nothing reads them on the rest.
            "time": r["time"], "venue": r["venue"],
        })
    print(f"{sum(len(v) for v in procs.values()):,} committee proceedings and "
          f"{sum(len(v) for v in floor.values()):,} floor appearances from "
          f"{P.PATH.name}")

    votes_by_bill = defaultdict(lambda: defaultdict(list))
    votes_by_member = defaultdict(list)
    for v in load(D / "member_votes.json", []):
        # A vote sequence number restarts each session, so "H-112" names two
        # different roll calls once 2025 sits beside 2026 -- and both years
        # belong to the same term, so the term alone does not separate them.
        # The bill is keyed by term for the same reason every other per-bill
        # map now is: HB396 exists in every biennium.
        key = f"{v['year']}-{v['body']}-{v['vote_number']}"
        # A ballot of Organization Day is on the next term's measure
        # (proceedings.vote_term): HR 1 of 2027, not of 2025.
        votes_by_bill[(P.vote_term(v["year"], v.get("date")), v["bill"])][key].append(v)
        votes_by_member[v["member_id"]].append(v)
    print(f"{len(bills):,} bills, {len(legs):,} legislators, "
          f"{sum(len(x) for x in votes_by_member.values()):,} member votes")
    write_rollcall_index(out, rollcalls, votes_by_member)

    # Sitting members who also voted under a number in the other chamber, joined
    # on the rules member_links.py sets out -- not on the name alone, which is
    # how careers.json came to merge two different Rep. Patrick Longs. Before
    # the bills, because a sponsor matched on a name is tested against the
    # seats the joined numbers held.
    links, not_joined = ML.links(legs.values(), votes_by_member, load(a.districts, {}))
    print(f"{len(links)} sitting member(s) also voted under a number in the other "
          "chamber, and their pages carry both"
          + (f"; {len(not_joined)} candidate(s) not joined, listed by "
             "python3 src/parse/member_links.py" if not_joined else ""))
    # The mid-term departures: they voted this term and the roster, which is a
    # snapshot of who serves today, does not carry them. former_roster says at
    # length why this is a separate map and not an addition to `legs`.
    former = former_roster(legs, votes_by_member, links,
                           load("former_members.json", {}),
                           max(bills) if bills else "")
    if former:
        print(f"{len(former):,} member(s) in the record hold no seat now; "
              "they get a page of their own and the sitting roster is "
              "unchanged")
    # The terms whose own roster is frozen and is not the sitting one
    # (freeze_term.own_roster_terms): every finished term, and the session's
    # once Organization Day has seated the next House before the files show
    # the next term (the review of 5 October 2026). Their sponsors are looked
    # for by name among `former` too, and labelled from that roster, as they
    # sat -- build_data writes it to data/frozen/<term>/legislators.json. None
    # before the first Organization Day, so nothing here moves until then.
    import freeze_term
    term_rosters = {t: {str(m.get("id")): m for m in load(D / "frozen" / t / "legislators.json", [])
                        if isinstance(m, dict)}
                    for t in freeze_term.own_roster_terms()}
    if term_rosters:
        print(f"  {', '.join(term_rosters)}: a frozen roster that is not the sitting one, "
              f"{sum(len(v) for v in term_rosters.values()):,} members; their sponsors are "
              "labelled from it and looked for among the members who hold no seat now")
    # BEFORE seats_held, and over both populations. A sponsor matched on their
    # name alone is only that member if this says they held a seat in that
    # chamber that term -- so a former member absent from it would be matched
    # and then thrown away again, and their sponsorships would stay unlinked
    # for the one reason the guard was never meant to cover.
    seats = ML.seats_held([*legs.values(), *former.values()], votes_by_member,
                          links, max(bills) if bills else "")

    segs, marks = load_transcripts(a, procs, prows)
    # -------------------------------------------------------------- index --
    index, years, unnamed, sponsored = build_bills(out, bills, narratives, rollcalls, reports,
                               sponsors, bill_texts, amend_texts, testimony,
                               testimony_db,
                               procs, floor, segs, marks, sources,
                               legs, leg_by_sort, leg_by_name,
                               votes_by_bill, vetoes=vetoes, notes=notes,
                               chapters=chapters, seats=seats,
                               former=former, links=links,
                               hearing_reports=hearing_reports,
                               term_rosters=term_rosters,
                               session_over=session_over(a.status),
                               coverage=archive_coverage(
                                   bills, narratives, sponsors, reports,
                                   rollcalls, procs,
                                   max(bills) if bills else ""),
                               ballots=load_ballots(BALLOTS, bills))
    # NO index.json (retired 5 October 2026). It was every row below in one
    # file, read by six build steps and by no page: 23.7 MB on 2 October,
    # 90.5% of the 25 MiB Cloudflare Pages takes in one file, and a term's
    # worth bigger with every field added to a row. The build reads the term
    # files instead, through site_read.bill_index. The copy an earlier build
    # left is deleted: site/ is never emptied, so it would stay and publish
    # would go on deploying a frozen list of every bill. check_site refuses
    # one as well.
    (out / "index.json").unlink(missing_ok=True)

    # ONE TERM AT A TIME, BECAUSE THAT IS ALL THE PAGE EVER SHOWS. The search
    # has always filtered to a single term -- there is a term picker and
    # render() reads it -- so a visitor was downloading nineteen terms to look
    # at one. With the archive in, index.json is 15.7 MB (1.6 gzipped) and
    # every first visit pays for it before a word can be typed.
    #
    # These are what the browser fetches: the newest term is 0.14 MB gzipped
    # and an archived one about 0.08, fetched only if somebody picks it. And
    # they are the record: the build reads them too (site_read.bill_index),
    # meta.json naming the terms, and data/manifest.json lists them for
    # programs.
    idx_dir = out / "idx"
    idx_dir.mkdir(exist_ok=True)
    by_term = defaultdict(list)
    for row in index:
        if row.get("term"):
            by_term[row["term"]].append(row)
    # EVERY ROW IN A TERM'S FILE. The build reads the bill index from these
    # files (site_read.bill_index), so a row with no term would be in none:
    # no page, no feed, no line in the downloads, and nothing to say so. No
    # row has lacked one; this stops the build if one ever does.
    termless = [row.get("id") for row in index if not row.get("term")]
    if termless:
        raise SystemExit(f"{len(termless):,} bill row(s) name no term, so no term's "
                         f"file would hold them: {', '.join(map(str, termless[:5]))}")
    for term_, rows_ in by_term.items():
        (idx_dir / f"{term_}.json").write_text(
            json.dumps(rows_, separators=(",", ":")), encoding="utf-8")
    # AND NO TERM'S FILE THIS BUILD DID NOT WRITE. site/ is never emptied, so a
    # term an earlier build wrote and this one does not would stay in idx/,
    # and site_read.bill_index refuses a term file meta.json does not name --
    # every step after this one, check_site and the census would stop on it,
    # and building again would not clear it. The bill requests' file
    # (2027-requests) is not a term's and is build_lsrs.py's. A term that
    # really went missing is the census's to see, by its count.
    for stale_ in sorted(idx_dir.glob("*.json")):
        if site_read.TERM_FILE.fullmatch(stale_.stem) and stale_.stem not in by_term:
            print(f"  idx/{stale_.name}: a term this build has no bills for, "
                  "left by an earlier one -- removed")
            stale_.unlink()
    newest_ = max(by_term) if by_term else ""
    print(f"  idx/: {len(by_term)} terms, newest {newest_} "
          f"({len(by_term.get(newest_, [])):,} bills, "
          f"{(idx_dir / f'{newest_}.json').stat().st_size / 1024:,.0f} KB) "
          "-- what a visitor actually loads")

    size = sum((idx_dir / f"{t_}.json").stat().st_size for t_ in by_term) / 1024
    biggest = max((((idx_dir / f"{t_}.json").stat().st_size, t_) for t_ in by_term),
                  default=(0, ""))
    print(f"idx/: {size:,.0f} KB for {len(index):,} bills; the largest, "
          f"{biggest[1]}, is {biggest[0] / 1024:,.0f} KB")

    # (term, bill) -> the year its page is under, so a vote can link to the
    # right one of two bills sharing a number.
    bill_year = {(t, b): str(r.get("lsr_year") or "")
                 for t, byb in bills.items() for b, r in byb.items()}
    lg = build_legislators(out, legs, votes_by_member, towns, unnamed,
                           sponsored, bill_year, links, former)

    # ---- home page data ----------------------------------------------------
    # Everything the landing page needs, precomputed here where the full records
    # are already in memory rather than making the browser fetch 2,000 files.
    today = build_date.today().isoformat()
    soon = (build_date.today() + _td(days=14)).isoformat()
    recent_cut = (build_date.today() - _td(days=3650)).isoformat()

    actions = []
    for b in index:
        narr = narratives.get(b["term"], {}).get(b["id"])
        for e in (narr or {}).get("events", []):
            if e.get("cancelled") or not e.get("date") or e["date"] > today:
                continue
            actions.append({"date": e["date"], "bill": b["id"], "n": b["n"],
                            "title": b["title"][:110], "what": e.get("raw", "")[:150]})
    actions.sort(key=lambda x: x["date"], reverse=True)

    upcoming = []
    # (term, bill), NOT bill. procs was re-keyed when bill numbers turned out
    # to repeat every biennium, and this loop was not: it put the whole tuple
    # in the "bill" field, so home.json carried
    # "bill": ["2025-2026", "HB1648"] and build_feeds died on
    # (bill or "").upper().
    #
    # It hid for as long as it did because it only fires when a hearing is
    # actually scheduled in the next fortnight. Every build for weeks printed
    # "0 upcoming" and never built a single one of these; the first day with
    # seven of them took the feed build down. A field that is only populated
    # some days needs a check that runs on the days it is empty, which
    # preflight now has.
    for (term_, bid), ps in procs.items():
        for pr in ps:
            d = pr.get("sched_date", "")
            if today <= d <= soon:
                # THE CHAMBER, because the name does not say it. A committee
                # page's Upcoming session (app.js cmteUpcoming) matched a row
                # on the name and on a bill of its own list, and a bill both
                # chambers' committees list matches both: House Judiciary's
                # sitting on SB 519 of 30 September 2026 was on Senate
                # Judiciary's page, and replayed over 2025-2026, 719 sittings
                # were on the other chamber's page on 384 days.
                upcoming.append({"date": d, "time": pr.get("sched_time"),
                                 "bill": bid, "term": term_,
                                 "committee": pr.get("committee"),
                                 "body": pr.get("body"),
                                 "what": pr.get("proceeding"),
                                 "venue": pr.get("venue")})
    upcoming.sort(key=lambda x: (x["date"], x["time"] or ""))

    # "Most contested" beats "most viewed": it is a fact about the record rather
    # than about traffic, and needs no analytics on a static site.
    contested = [without_rail(b) for b in sorted([b for b in index if b["nrc"] > 1],
                                                 key=lambda b: -b["nrc"])[:8]]
    closest = []
    for b in index:
        for r in rollcalls.get(b["term"], {}).get(b["id"], []):
            # RollCallSummary holds chamber floor votes only, but be explicit:
            # procedural motions and anything without a tally are excluded, so
            # "closest" means how close the chamber came on the bill itself.
            if r.get("procedural") or not r.get("yeas"):
                continue
            if r.get("body") not in ("H", "S"):
                continue
            m = abs(r["yeas"] - r["nays"])
            if m <= 12:
                closest.append({"bill": b["id"], "n": b["n"], "title": b["title"][:110],
                                "date": r.get("date"), "q": r.get("question"),
                                "y": r["yeas"], "nn": r["nays"], "margin": m})
    closest.sort(key=lambda x: (x["margin"], x["date"] or ""))

    # "Still moving" counts the CURRENT term only. A bill that did not finish
    # before its biennium ended did not carry on moving -- it died with the
    # session -- and counting 492 bills of 2023-2024 among the 599 the home
    # page called live was the site asserting something that stopped being
    # true two years ago. The other totals are of the whole record on purpose:
    # a law passed in 2023 is still a law.
    newest = max((b["term"] for b in index if b.get("term")), default="")
    by_kind = defaultdict(int)
    for b in index:
        if b["kind"] == "active" and b.get("term") and b["term"] != newest:
            continue
        by_kind[b["kind"]] += 1
    # One per chamber. The House and Senate sit on different days, so a single
    # "most recent" hides whichever sat second.
    latest_by_body = {}
    for v in floor.values():
        for f in v:
            if not (f.get("date") and f.get("video_id")):
                continue
            b = f.get("body") or "H"
            cur = latest_by_body.get(b)
            if not cur or f["date"] > cur["date"]:
                latest_by_body[b] = {"date": f["date"], "video_id": f["video_id"],
                                     "chamber": "House" if b == "H" else "Senate"}
    latest_session = latest_by_body.get("H")   # kept for older page versions

    comp, vac = build_composition(a, legs)
    status = build_status(a, index, procs, floor, today,
                          latest_by_body, upcoming)
    (out / "home.json").write_text(json.dumps({
        "status": status, "composition": comp,
        "generated": today,
        "counts": {"bills": len(index), "legislators": len(lg) if 'lg' in dir() else 0,
                   "votes": sum(len(x) for x in votes_by_member.values()),
                   "by_kind": dict(by_kind)},
        "terms": sorted({b["term"] for b in index if b["term"]}, reverse=True),
        # EIGHTY ROWS, NOT TWELVE. The status box beside this calendar counts
        # the whole fortnight, which has run to 39 bill-sittings, and the
        # calendar was cut to twelve, so the page said 39 above a list of 12
        # and dropped whole days off the end without saying so. The cut is
        # still there because a fortnight in session is hundreds of rows, and
        # build_pages says how many did not fit.
        "recent": actions[:12], "upcoming": upcoming[:80],
        "contested": contested, "closest": closest[:6],
        "latest_session": latest_session,
        "latest_sessions": [latest_by_body[b] for b in ("H", "S")
                            if b in latest_by_body],
    }), encoding="utf-8")
    print(f"home.json: {len(actions):,} actions, {len(upcoming)} upcoming, "
          f"{len(closest)} close votes")
    for ch in ("H", "S"):
        c = comp[ch]
        print(f"  {c['chamber']}: {c['sitting']} of {c['seats']} seats"
              + (f", {c['vacant']} vacant" if c["vacant"] else "")
              + " — " + ", ".join(f"{p['n']} {p['code']}" for p in c["parties"]))
    if vac:
        print(f"  {sum(v['vacant'] for v in vac)} vacant House seats identified "
              f"across {len(vac)} districts")

    # Name as the index writes it -- "House Finance" -- to the code its page
    # lives at. Both chambers have a Finance, so the chamber is part of the
    # key, and it comes from the code's own first letter.
    committee_codes = {}
    for _code, _rec in (load(D / "committees.json", {}) or {}).items():
        _nm = (_rec.get("name") or "").strip()
        _ch = _code[:1].upper()
        # A CODE IS NOT A PAGE. build_committees.py refuses to write one for
        # H29, whose name in Committees.txt is "No Committee Assignment" --
        # the code the General Court files a bill under when it referred it
        # nowhere. Written into this map anyway, it made cmteLink draw
        # committee/H29.html on 138 bill cards, and those 138 were the only
        # dead internal target among the site's 624,515 links.
        #
        # The LABEL stays: "No Committee Assignment" is the General Court's own
        # wording for a bill it never referred, so it is a fact about the bill
        # and belongs on the card. Left out of this map, cmteLink prints it as
        # text, which is what it is.
        #
        # Kept as the same set of words build_committees.py refuses on, because
        # the two have to agree about what a committee is.
        if _nm.lower() in NOT_A_COMMITTEE:
            continue
        if _nm and _ch in ("H", "S"):
            committee_codes[f"{'House' if _ch == 'H' else 'Senate'} {_nm}"] = _code
    committee_codes = committee_links(index, committee_codes)
    meta = {"years": sorted(years, reverse=True),
            "terms": sorted({b["term"] for b in index if b["term"]}, reverse=True),
            "committees": sorted({b["committee"] for b in index if b["committee"]}),
            # {"House Finance": "H34"}, so a committee named on a bill card is
            # a link to that committee rather than a dead end -- 3,967
            # mentions across the site, none of them clickable before.
            # Written from data/committees.json, whose codes carry the
            # chamber, because "Finance" alone names one in each. A name
            # whose committee depends on the term is an object instead:
            # committee_links says which, and app.js's cmteLink reads both.
            "committee_codes": committee_codes,
            "topics": sorted({b["topic"] for b in index if b["topic"]}),
            "sponsors": sorted({b["sponsor"] for b in index if b["sponsor"]}),
            "votedays": sorted({d for b in index for d in b["votedays"]}, reverse=True)}
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"facets: {len(meta['committees'])} committees, {len(meta['topics'])} topics, "
          f"{len(meta['sponsors'])} sponsors, {len(meta['votedays'])} vote days")

    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    front = ((out / "idx" / f"{newest_}.json").stat().st_size / 1024
             if newest_ else 0)
    print(f"\nsite data: {total/1e6:.1f} MB total, {front:,.0f} KB loaded "
          f"up front (idx/{newest_}.json)")
    print(f"  idx/ is {size:,.0f} KB in all, one file a term, and the build "
          "reads the same files")
    print(f"-> {out}/")
    print("\nNext: the HTML shell reads idx/<term>.json and meta.json for search and")
    print("facets, then fetches bills/<year>/<id>.json when a card is expanded.")
    # Last, so that it is one of the lines build_all prints of this step.
    if no_dump_for(newest_):
        print("WARNING: " + no_dump_for(newest_))
    # And of the term before it, where it has measures only a dump answers
    # for (terms_without_a_dump): the one the views have just turned away from.
    for term_, blank_ in terms_without_a_dump(bills, load("bill_status.json", {})):
        if term_ != newest_:
            print(f"WARNING: {no_dump_for(term_)} ({len(blank_):,} of its measures have a "
                  "status page that states nothing)")


if __name__ == "__main__":
    main()
