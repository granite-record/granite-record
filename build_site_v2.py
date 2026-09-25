#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.110
"""
Generate the faceted site from real General Court data.

    python3 build_site_v2.py --data data --out site

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

import argparse
import caption_span
# Where the recordings this site links begin: one constant, which about.html
# states in words and station_for_proceeding and station_for_floor split on.
from about_figures import STREAM_START
import narrative as N
import fiscal
import proceedings as P
import senate_hearing_reports as SHR
import csv
import json
import member_links as ML
import names
import re
import sys
import archive_text as AT
import bill_order as BO
import text_sponsors as TS
import topic_model as TM
import unicodedata
from collections import Counter, defaultdict, namedtuple
from datetime import date as _date, timedelta as _td
from pathlib import Path

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


def bill_amendments(narr, texts):
    """Every amendment on one bill, in the order the docket took them up.

    Order is the whole point. A committee amendment is considered before any
    floor amendment, and where two touch the same section the later one wins,
    so a list sorted any other way describes a bill that does not exist. The
    docket is already chronological, so it is simply not re-sorted.

    Text is attached where the calendars had it and left absent where they did
    not. An amendment nobody can read is still an amendment that was moved,
    and dropping it would hide a step rather than a document.
    """
    out, seen = [], {}
    for e in (narr or {}).get("events", []):
        if e.get("type") != "amendment" or e.get("cancelled"):
            continue
        num = (e.get("amendment") or "").strip()
        if not num:
            m = AMEND_NUM.search(e.get("raw", "")) or AMEND_ANY.search(e.get("raw", ""))
            num = m.group(1) if m else ""
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
            said = ADOPTED.get((e.get("motion") or "").upper())
            if a["adopted"] is None and said is not None:
                a["adopted"] = said
                a["vote_kind"] = a["vote_kind"] or e.get("vote_kind") or ""
                a["mover"] = a["mover"] or e.get("mover") or ""
                a["date"], a["body"] = e.get("date"), e.get("body")
            continue
        kind = (e.get("amend_kind") or "").strip() or "Amendment"
        doc = texts.get(num) or {}
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
            "adopted": ADOPTED.get((e.get("motion") or "").upper()),
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
SINGLE_CHAMBER = {"HR": "House", "SR": "Senate", "SSHR": "House", "SSSR": "Senate"}
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
]


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
        # vote. HB 1364, HB 1559, HB 1420, HB 1223 and CACR 19 of 2026 each
        # met a motion to take it up out of order that failed on a roll call
        # or a division -- HB 1364's 151-180 -- and then nothing more, and
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
    # "Killed" is deliberately NOT here. The status page reports it for bills
    # whose docket already says what ended them -- 28 were laid on the table
    # and died there, and the narrative says so in as many words -- so a
    # paragraph claiming "the docket does not record the vote that ended it"
    # would have been false on most of the bills it appeared under.
}


# "No vote was ever taken on it" is a claim, and on 35 of the 111 bills of
# 2025-2026 that carried it the docket records one: HB 243 passed both
# chambers and went to a committee of conference that never reported; CACR 8
# passed the Senate 21-3 and failed in the House, 203-158. Where a chamber
# decided anything, this is what the ending was instead.
SESSION_ENDED_AFTER_VOTES = (
    "It had not finished its passage when the session ended, and the bill died "
    "then. That is a procedural end rather than a decision -- it ran out of "
    "time -- and it would have to be filed again as a new bill in a later term.")


def closing_stage(label, narr, decided=False):
    """A last paragraph for a bill whose ending the docket never narrates.

    The docket records actions, and a session ending is not an action: it just
    stops. For 111 bills the last line is a committee report and only the
    status page knows the bill died with the term, so a settled red headline
    sat above a history that trailed off mid-sentence.

    `decided` is whether the journey has a chamber deciding anything on the
    bill. Returns None where the history already says it.
    """
    hit = CLOSING.get(label)
    if not hit:
        return None
    guards, text = hit
    told = " ".join(s.get("text", "") for s in (narr or {}).get("stages", [])).lower()
    if any(g in told for g in guards):
        return None
    if decided and label == "Died when the session ended":
        text = SESSION_ENDED_AFTER_VOTES
    return {"label": "How it ended", "text": text}


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
DISPOSED = [
    (re.compile(r"inexpedient to legislate", re.I), ("done", "Killed")),
    (re.compile(r"indefinitely postpone", re.I),
     ("done", "Indefinitely postponed")),
    (re.compile(r"interim study", re.I), ("study", "Referred for interim study")),
]


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


def classify(narr, rcs, prefix=""):
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
    carried = " | ".join((e.get("action") or "").lower() for e in evs
                         if e.get("type") == "floor"
                         and (e.get("motion") or "").upper() == "MA")
    if "inexpedient to legislate" in carried:
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
    if "died on table" in text:
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
    if re.search(r"inexpedient to legislate,\s*(?:senate|house)\s+rule", text):
        return "done", "Killed"
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
    adopted_floor = any(
        e.get("type") == "floor" and (e.get("motion") or "").upper() == "MA"
        and re.search(r"ought to pass|adopted", e.get("action") or "", re.I)
        for e in (narr or {}).get("events", []) if not e.get("cancelled"))
    if adopted_floor or any(r.get("passed") for r in rcs):
        # A resolution of one chamber that has carried a vote is finished.
        # There is no other chamber for it to be in progress towards.
        if prefix in SINGLE_CHAMBER:
            return "adopted", f"Adopted by the {SINGLE_CHAMBER[prefix]}"
        return "active", "In progress"
    return "active", "In committee"


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
        return "Adopted. A resolution of one chamber goes no further"
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
            return "Adopted. A resolution of one chamber goes no further"
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
    if f.get("whole_video"):
        # The title names the bill, so the entire recording is this
        # proceeding. No timestamp to estimate and none needed.
        return {
            "when": f["date"], "time": None,
            "what": f.get("kind", "committee of conference"),
            "committee": None, "venue": None,
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
        "when": f["date"], "time": None,
        "what": kind,
        "committee": ("House" if f.get("body") == "H" else "Senate"
                      ) if kind == "floor debate" else None,
        "venue": None, "video_id": f["video_id"],
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


def withhold_late_captions(segs, marks, work):
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
    """
    vids = set(segs) | {k for k in marks if not k.startswith("_")}
    late, compared, undated = caption_span.out_of_step(vids, work)
    said = sum(len(c) for v in late for c in (marks.get(v) or {}).values())
    placed = sum(1 for v in late for s in (segs.get(v) or []) if s.get("located"))
    for v in late:
        segs.pop(v, None)
        marks.pop(v, None)
        for side in ("_absent", "_sequence"):
            if isinstance(marks.get(side), dict):
                marks[side].pop(v, None)
    print(f"caption tracks: {compared:,} recordings compared with the length "
          "YouTube published")
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
                       "terms": sorted({P.term_of(v.get("year", ""))
                                        for v in mv if v.get("year")})},
        }
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
                           (P.term_of(v.get("year", "")), v["bill"]), "")}
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
            age = (_date.today() - _date.fromisoformat(status["updated"])).days
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
        for e in (narr or {}).get("events", []):
            if e.get("cancelled") or e.get("type") == "report":
                continue
            # Strictly before the later report: an action on the same day
            # is the floor acting on that report, not the reason for it.
            if a < (e.get("date") or "") < z and REPORT_AGAIN.search(
                    e.get("raw", "")):
                between.append({"before": z, "date": e["date"],
                                "text": e.get("raw", "")})
                break
    return out, docket, between


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


def hearing_report_for_page(rec, idx, name_part):
    """One parsed report as the Hearings tab draws it, legislators resolved.

    Returns (report, members resolved, legislator lines left as text).
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
                    sp["member"] = {"label": name_part(sp["who"]),
                                    "party_code": mem.get("party_code") or "",
                                    "slug": own_slug(mem)}
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


def attach_hearing_reports(stations, reports, bid, idx, name_part, tally,
                           unmatched):
    """Each report onto the station of the hearing it reports.

    That is the bill's Senate public hearing on the date the report gives --
    the station the Hearings tab draws with the recording. A list on the
    station, because a committee can hear a bill and then an amendment to it
    the same afternoon and file a report of each. A report whose date the
    docket has no Senate hearing for is not pinned to some other sitting: it
    is counted and named in `unmatched`.
    """
    for rep in reports:
        at = next((s for s in stations
                   if s.get("body") == "S"
                   and "hearing" in (s.get("what") or "").lower()
                   and s.get("when") == rep.get("heard")), None)
        if at is None:
            tally["unmatched"] += 1
            unmatched.append(f"{bid} {rep.get('heard')}")
            continue
        page, got, miss = hearing_report_for_page(rep, idx, name_part)
        at.setdefault("reports", []).append(page)
        tally["matched"] += 1
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
ONE_CHAMBER = ("HR", "SR", "SSHR", "SSSR")
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
    ("killed", re.compile(r"\binexpedient\b|\bITL\b|\bkilled\b", re.I)),
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
# "Introduced ...", "5/3/2001 Introduced and ref to Judiciary", "Introducing
# and referred to Public Affairs" (SB 12 of 1999), "Sen. Birdsell Moved
# Introduction; 2/3 necessary, MA, VV" (SCR 1 of 2023).
J_INTRO_ROW = re.compile(r"^\s*(?:\d{1,2}/\d{1,2}/\d{2,4}\s+)?introduc(?:ed|ing|tion)\b|"
                         r"\bmoved\s+introduction\b", re.I)
J_REF_TALLY = re.compile(r"\(\s*([\d,]{3,})\s*[-–]\s*([\d,]{3,})\s*\)")
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
        if (out and not _j_has_outcome(out[-1]) and _j_has_outcome(p)
                and not re.search(r"withdr[ae]w", out[-1], re.I) and (
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
    if said is None:
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
        # A motion NOT to adopt, carried, is the report rejected: "Sen.
        # Pignatelli Moved Non Adopt Conference Committee Report RC 17Y-7N,
        # Non Adopt" (SB 69 of 2001) read as the Senate adopting it 17-7.
        # So is "REFUSED TO ADOPT CONF COMM REPT, REQ NEW CONF COMM REPORT,
        # SEN HEATH MA VV" (HB 352 of 1991).
        if re.search(r"\bnon[-\s]?adopt|\bnot\s+(?:to\s+)?adopt(?!ed)|\bmov\w*\s+(?:to\s+)?reject"
                     r"|\brefus\w*\s+to\s+adopt", seg[:end], re.I):
            if not said:
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
    pre = bill_prefix(bid)
    resolution = pre in SINGLE_CHAMBER or (pre in NO_GOVERNOR and pre != "CACR")
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
        "conf_rejected": ("Rejected the conference report", "report rejected"),
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
    days = {_j_iso(*d.groups()) for x in lines for m in [J_EFF_ANY.search(x)] if m
            for d in J_DAY.finditer(x, m.start())} - {""}
    return days.pop() if len(days) == 1 else ""


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
J_FROM_REPORT = [(re.compile(r"inexpedient", re.I), "killed"),
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
    in whichever order the two were entered."""
    tails = defaultdict(list)
    voted = set()
    for e in evs:
        if e.get("type") != "report":
            continue
        raw = e.get("raw") or ""
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
        raw = _j_unfile(e.get("raw") or "")
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


def journey(narr, bid, rcs=(), chapter="", law_line="", term=""):
    """(the date it was introduced, [one dict a decision]) -- from the docket.

    Each decision carries its date, its body (H, S, the Governor G, the Law L
    or the Voters V), what it was (`act`), the glyph it is drawn with
    (`mark`: p, x or h), its words for On the record (`text`) and for the
    rail (`short`). `term`, "2019-2020", bounds the days it will state.
    """
    evs = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
    intro = _j_introduced(evs, bid, term)
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
    pending = {}
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
        for seg in _j_segments(raw):
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
                mine = [i for i, s in enumerate(steps) if s["body"] == body]
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
                if (last and last["act"] == "passed" and (body, date) not in waived
                        and 0 <= _j_days(date, last["date"]) <= 30
                        and not any(s["body"] in ("H", "S") for s in steps[at + 1:])):
                    last["act"], last["to"] = "referred", to
                elif (body, date) not in waived:
                    pending[(body, date)] = to
                continue
            got = _j_decide(seg, bid, rcs, date, body)
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
            st = {"date": date, "body": body, **got}
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
            said = J_CLAUSE_DAY.search(seg)
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
            if st["act"] == "passed" and (body, date) in pending:
                st["act"], st["to"] = "referred", pending.pop((body, date))
            steps.append(st)
    # AN AMENDMENT ADOPTED THAT DAY AMENDS THAT DAY'S PASSAGE, whether the
    # clerk entered it before the passage or after: "Sen. Fernald Moved Ought
    # to Pass, RC 22y - 1n, MA" and then "Sen. Francoeur Floor Amendment
    # {2837}, (New Title), RC 13y - 10n, AA" (SB 336 of 2002), the bill that
    # went to the House amended.
    for st in steps:
        if st["act"] in ("passed", "referred") and (st["body"], st.get("_row_day")) in amended:
            st["amended"] = True
        st.pop("_row_day", None)
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
    # An introduction dated after the first decision on the bill is a date
    # the docket has wrong -- HB 113 of 2005's "Introduced and ref to Crim
    # Just & PSfty" stands at 1 December 2006, eleven months after the House
    # killed it -- and the stop goes undated rather than out of order.
    first_day = min((s["date"] for s in steps if s["body"] in ("H", "S") and s["date"]),
                    default="")
    if intro and first_day and intro > first_day:
        intro = ""
    if chapter:
        eff = _j_effective(gov_raw, *gov_more, law_line)
        steps.append({"date": "", "body": "L", "act": "law",
                      "text": f"Chapter {chapter}" + (
                          f", in effect {_j_prose_date(eff)}" if eff else ""),
                      "short": f"Chapter {chapter}"})
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
        for k in ("vote", "amended", "third", "to", "conf", "rule", "adjourned",
                  "unanswered", "intro_adopt", "short_of"):
            st.pop(k, None)
    return intro, steps


def _j_answers_after(steps, bid):
    """A day's steps with each answer after the act it answers, across the
    two chambers, whose rows of one day the clerk can enter in either order.

    A chamber agreeing to or refusing the other's amendment answers that
    chamber's passage: HB 10 of 2025 had the House "Agreed to the Senate's
    amendment, 210–160" (entered at 1:52) ahead of the Senate passing it with
    that amendment (2:48), both on 5 June. And a vetoed bill goes back to the
    chamber it started in, which votes on the veto first: SB 434 of 2026 had
    the House sustaining the veto ahead of the Senate overriding it."""
    pre = bill_prefix(bid)
    origin = "H" if pre.startswith("H") else "S" if pre.startswith("S") else ""
    veto = ("override", "sustained")

    def answers(s, t):
        if not s["date"] or s["date"] != t["date"] or {s["body"], t["body"]} != {"H", "S"}:
            return False
        return ((s["act"] in ("concurred", "nonconcurred") and t["act"] == "passed")
                or (s["act"] in veto and t["act"] in veto and origin and s["body"] != origin))

    out = list(steps)
    i = 0
    while i < len(out):
        s = out[i]
        last = max((j for j in range(i + 1, len(out)) if answers(s, out[j])), default=None)
        if last is None:
            i += 1
            continue
        out.insert(last, out.pop(i))
    return out


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
        later = [j for j, t in enumerate(out) if t["body"] == other
                 and t["act"] == "passed" and t["date"]]
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
    second committee is the passage of the bill as the chamber amended it."""
    held = set()
    for s in steps:
        if s["act"] == "referred" and s.get("amended"):
            held.add(s["body"])
        elif s["act"] == "passed" and s["body"] in held:
            held.discard(s["body"])
            s["amended"] = True
    return steps


def _j_merge(into, st):
    """A second passage of the same sitting, folded into the first: amended
    if either was, and the count of the one that has a count -- but never the
    count of a motion to introduce ("Introduced and Adopted: MA DV 259-66 By
    Necessary Two-Thirds Vote", then "Ought to Pass : MA VV", HB 2023 of
    2022)."""
    into["amended"] = into.get("amended") or st.get("amended")
    if st.get("intro_adopt"):
        return
    if into.pop("intro_adopt", False) or st["vote"][1] is not None or not into["vote"][0]:
        into["vote"] = st["vote"]


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
        if st.get("third") and st["act"] == "passed":
            mine = [s for s in out if s["body"] == st["body"]]
            if mine and mine[-1]["act"] == "passed":
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
    each one its date and its word. The stops follow the bill's route: a
    resolution of one chamber has that chamber; a concurrent resolution two
    chambers and no governor; a CACR goes to the voters instead of the
    governor, with the ring on Voters while it waits for them."""
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
    stops.append({"stop": "Law", "mark": lm, "date": "",
                  "short": law["short"] if law and lm == "p" else "",
                  "say": (law["text"] if law and lm == "p"
                          else "Did not become law" if lm == "x"
                          else RAIL_SAY.get(lm, ""))})
    return stops


# What a stop says when no line of the journey fills it -- the same words the
# list card's rail uses.
RAIL_SAY = {"p": "Passed", "h": "Is here now", "x": "Stopped here",
            "-": "Never reached"}

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
                      leg_by_sort, leg_by_name, sponsored, seats=None):
    """Who put their name to this bill, and their own bill list, both.

    It mutates `sponsored`, which is the caller's accumulator of what
    each member has sponsored, the same way vote_member mutates
    `unnamed`. That is why it is passed explicitly rather than closed
    over: a function that changes something belonging to its caller
    should say so in its signature.

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
        if _s.get("source") == TS.SOURCE or _s.get("seat_source") == TS.SOURCE:
            _lab = member_labels(
                _s.get("name"),
                chamber=_s.get("chamber") or _m.get("chamber"),
                party=_s.get("party") or _m.get("party_code"),
                district=_s.get("district") or _m.get("district"),
                county=_s.get("county") or _m.get("county"),
                county_abbr=None if _s.get("district") else _m.get("county_abbr"))
        else:
            _lab = member_labels(
                _s.get("name"),
                chamber=_m.get("chamber") or _s.get("chamber"),
                party=_m.get("party_code") or _s.get("party"),
                district=_m.get("district") or _s.get("district"),
                county=_m.get("county") or _s.get("county"),
                county_abbr=_m.get("county_abbr"))
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
Disposition = namedtuple("Disposition",
                         "kind status told settled prefix stated stale between",
                         defaults=(False,))


def bill_committees(b, bid):
    """(committee, committees) for a bill's index row.

    `committees` is every committee the bill has, each with its chamber, House
    first; the card lists them in that order. `committee` is THE committee of
    the bill -- what index.json, idx/<term>.json and the committee list in the
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
                   passed=None, acted=None):
    """One bill's row in the search index.

    It comes after bill_disposition because it reads that function's
    result, so a mistake there surfaces here.

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
# only what the field says.
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
CONF_FAILED = re.compile(r"\bfail(?:ed|s)?\b|not adopted|\brejected\b|lacking|"
                         r"\blost\b|\bdefeated\b", re.I)
# A NEW committee of conference -- "New Conf Comm", "New Committee of
# Conference", "new C of C" -- but not "New Conf Comm Report ... MA", which
# is the new conference's report being adopted (SB 140 of 1999).
NEW_CONF = re.compile(r"\bnew\s+(?:conf(?:erence)?\.?\s*comm(?:ittee)?\.?(?!\s*rep)|"
                      r"comm\w*\s+of\s+conf|c\s?of\s?c(?!\s*rep))", re.I)
# The clause about the report ends where the next member's motion starts:
# "Conf Comm Report Adopted RC(190-181); Rep Herman moved to Reconsider, ML".
NEXT_MOTION = re.compile(r";\s*(?:rep|reps|sen|senator)\b|moved to reconsider", re.I)
CONF_REJECTED = "Died when the conference report was rejected"


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


def between_chambers(narr, status):
    """A dated docket answer to what became of the two versions, or None."""
    evs = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
    conf = conference_outcome(evs)
    if status in BEFORE_CONFERENCE and "failed" in conf.values():
        return "done", CONF_REJECTED
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


def cacr_to_the_voters(narr, term, current, text="", today=None):
    """What a CACR both chambers passed now says, in the tense the record
    allows: the voters' answer where the docket records it; past tense for a
    closed term; for the current term, the election its own text names, in
    the future tense until that day."""
    for e in reversed([e for e in (narr or {}).get("events", []) if not e.get("cancelled")]):
        m = REFERENDUM.search(e.get("raw") or "")
        if m:
            return ("Passed both chambers, ratified by the voters"
                    if m.group("how").lower() == "adopted"
                    else "Passed both chambers, not ratified by the voters")
    m = ELECTION_IN_TEXT.search(text or "")
    if term != current:
        return "Passed both chambers, went to the voters"
    if not m:
        return TO_THE_VOTERS
    when = f"{m.group('month')} {m.group('year')}"
    over = (today or _date.today()) > election_day(m.group("year"))
    return (f"Passed both chambers, went to the voters in {when}" if over
            else f"Passed both chambers, goes to the voters in {when}")


# THE 2020 SENATE LEFT 427 BILLS ON THE TABLE, and its Rule 3-23 killed them at
# adjournment: every one's last docket line is "Inexpedient to Legislate,
# Senate Rule 3-23, Adjournment 09/16/2020", while its status field still said
# LAID ON TABLE. The site already called this ending "Died on the table" on 211
# bills whose last line is the same, 164 of them in other terms (2015-2016 to
# 2023-2024) and 47 in 2019-2020 itself.
TABLE_DEATH = re.compile(r"inexpedient to legislate,\s*senate\s+rule\s+3-23,\s*adjournment", re.I)


def bill_disposition(b, bid, st, narr, rcs, term, current, law_line="",
                     override_failed="", term_over=False, text="", today=None):
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
    """
    stated = stale = 0
    between = None
    prefix = bill_prefix(bid)
    told = classify_stated(st, prefix, origin_of(bid, narr, st))
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
    elif told:
        kind, status = told
        stated = 1
    else:
        kind, status = classify(narr, rcs, prefix)
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
            evs2 = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
            if evs2 and TABLE_DEATH.search(evs2[-1].get("raw") or ""):
                between = ("done", "Died on the table")
                kind, status = between
    if status == TO_THE_VOTERS:
        status = cacr_to_the_voters(narr, term, current, text, today)
    if kind == "active" and (term != current or term_over):
        kind = "done"
        stale = 1
    # The veto labels are the one place the words themselves are this
    # site's and say the bill is still waiting. "Awaiting an override vote"
    # expands VETOED BY GOVERNOR; in a closed term nothing is awaited, and
    # the veto stood -- whether or not a vote was ever taken, which the
    # record does not always say (HB 1407 of 1992 has no override line at
    # all). So a closed term says what the field says.
    if (kind == "veto" and term != current
            and status in ("Vetoed, awaiting an override vote",
                           "Vetoed, override vote pending")):
        status = "Vetoed"
    return Disposition(kind, status, told, settled, prefix,
                       stated, stale, bool(between))


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
        if e.get("cancelled"):
            continue
        c = _cite(e, sources, (e.get("date") or "")[:4])
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


PENDING = re.compile(r"(In progress|In committee|Pending|Enrolled\.)", re.I)


def settled_step(step, status, term, current):
    """The status box, with nothing left pending once a term has closed."""
    if term != current and PENDING.match(step or ""):
        return status or step
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
                links=None, hearing_reports=None):
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
    # The Senate's hearing reports: who testified, resolved to members where
    # a line names one. Counted as they are attached, so the build says how
    # many found their hearing and names the ones that did not.
    _hr_idx = speaker_index([*legs.values(), *(former or {}).values()])
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
    # no text. testimony.json is still flat and is read through the `own`
    # guard below for the same reason.
    current = max(bills) if bills else ""
    n_stale = 0
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
        disp = bill_disposition(
            b, bid, st, narr, rcs, term, current,
            term_over=bool(session_over) and term == current,
            law_line=dl.get("line", ""),
            override_failed=dl.get("override_failed", ""),
            # A CACR's own text names the election it goes to, which is
            # what decides whether it "goes" or "went" to the voters.
            text=((P.per_term(bill_texts, term, current).get(bid) or {}).get("text", "")
                  if bill_prefix(bid) == "CACR" else ""))
        kind, status = disp.kind, disp.status
        told, settled, prefix = disp.told, disp.settled, disp.prefix
        n_stated += disp.stated
        n_stale += disp.stale

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
                                    leg_by_name, sponsored, seats)
        prime = next((s for s in sp_list if s.get("prime")), sp_list[0] if sp_list else None)
        years.add(year)
        ev = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
        dates = sorted(e["date"] for e in ev if e.get("date"))
        act_years = {d[:4] for d in dates}
        # Filed one year, acted on the next: retained in committee or sent to
        # interim study. These are exactly the bills someone loses when they
        # search the current year and the bill was filed in the previous one.
        carried = len(act_years) > 1
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
        intro, jsteps = journey(narr, bid, rcs, chapter, dl.get("line", ""), term)
        row = bill_index_row(
            bid, b, year, term, cmte, cmtes, disp, prime,
            narr, rcs, coverage, carried, dates, chapter,
            passed={c for c in ("H", "S") if journey_state(jsteps, c) == "p"},
            acted=list(dict.fromkeys(s["body"] for s in jsteps
                                     if s["body"] in ("H", "S"))))
        index.append(row)
        jrail = journey_rail(intro, jsteps, row["passage"], bid, status)
        why = journey_disagrees(jsteps, kind, status, row["passage"], bid)
        j_tally[(term, "empty" if not jsteps else "disagree" if why else "agree")] += 1
        if why and term == current:
            j_current.append(f"{bid}: {why}")
        for s_ in jsteps:
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

        bill_amds = bill_amendments(narr, amend_texts)
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
        # carry is left off the page and named in the build's output rather
        # than pinned to some other sitting.
        attach_hearing_reports(
            stations, (hearing_reports or {}).get(term, {}).get(bid, []),
            bid, _hr_idx, _hr_name, hr_tally, hr_unmatched)
        # Floor debates, stacked with the committee proceedings and sorted by
        # date so a bill's whole journey reads in order: hearing, executive
        # session, floor, then the second chamber.
        stations += [station_for_floor(f, bid, marks)
                     for f in floor.get((term, bid), [])]
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
            "narrative": (narr or {}).get("narrative", ""),
            # The history, plus a closing paragraph where the bill's ending
            # is only on the status page. 120 bills showed a settled headline
            # over a story that stopped at the committee report.
            "stages": ((narr or {}).get("stages", [])
                       + [x for x in [closing_stage(
                           status, narr,
                           decided=any(s_["body"] in ("H", "S") for s_ in jsteps))]
                          if x]),
            "notes": (narr or {}).get("notes", []),
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
            "events": [{"date": e["date"], "text": e.get("raw", ""),
                        "routine": is_routine(e.get("raw", "")),
                        **({"date_as_recorded": e["date_as_recorded"],
                            "date_note": e.get("date_note") or (
                                "The General Court's online docket gives "
                                "another date for this; the journal and the "
                                "other records of the sitting place it on the "
                                "date shown.")}
                           if e.get("date_as_recorded") else {}),
                        **hearing_testimony(
                            e, tdb, testimony.get(bid) if own else None),
                        **_cite(e, sources, (e.get("date") or "")[:4])}
                       for e in (narr or {}).get("events", []) if not e.get("cancelled")],
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
            # answer there; the current term is untouched.
            "next_step": settled_step(
                bill_next_step(narr, b, prefix, st, settled, told),
                status, term, current),
            **({"archived": (coverage or {}).get(term) or True}
               if b.get("archived") else {}),
            # "General Court docket" where a dated docket line decided the
            # status over the fields: settled (the governor, a veto), or
            # between the chambers (a refusal to concur, a conference report
            # voted down, a resolution the second chamber adopted).
            "status_source": ("General Court docket" if settled or disp.between
                              else "General Court bill status page" if told
                              else "derived from the docket"),
            "chapter": chapter,
            # HOW IT GOT HERE: each chamber's floor decisions, the governor,
            # the chapter and a CACR's referendum, dated, one line each; and
            # the stops of the rail on the bill's own view, dated from them.
            # The list card's rail stays the index's four characters.
            **({"journey": {"steps": jsteps, "rail": jrail}}
               if jsteps or jrail else {}),
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
            # word stays on the chip -- "Laid on the table" -- and this says
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
            "docket_url": ("https://gc.nh.gov/bill_status/legacy/bs2016/bill_docket.aspx"
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
            # Named, not just counted: each is a report the site holds and
            # does not show, and the reason is in the docket for that bill.
            print(f"  {len(hr_unmatched):,} found no Senate public hearing "
                  "of that bill on that date in proceedings.csv: "
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
    ap.add_argument("--reports", default="committee_reports.json")
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
    withhold_late_captions(segs, marks, a.segments)
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
                 "Rebuild it: python3 build_data.py --dir . --out data")
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
                 "Rebuild it: python3 narrative.py --docket Docket.txt --all "
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
                 "it: python3 rollcall_parser.py --all --out rollcalls.json")
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
    testimony = load("testimony.json", {})
    # Counts per bill AND per hearing, from the General Court's database:
    # 2,019 bills against the scraped page's 565. Keyed on the term, because
    # legislationID is reused across terms -- joining without that put 67,119
    # sign-ins from 2024 onto 856 bills of this one.
    testimony_db = load("testimony_db.json", {})
    if testimony_db:
        nb = sum(len(v) for v in testimony_db.values())
        ns = sum(r["total"] for v in testimony_db.values() for r in v.values())
        print(f"testimony sign-ins: {ns:,} across {nb:,} bills, per hearing")
    if testimony:
        print(f"testimony counts for {len(testimony):,} bills")
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
        print("Run: python3 build_proceedings.py")
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
        votes_by_bill[(P.term_of(v["year"]), v["bill"])][key].append(v)
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
             "python3 member_links.py" if not_joined else ""))
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
                               session_over=session_over(a.status),
                               coverage=archive_coverage(
                                   bills, narratives, sponsors, reports,
                                   rollcalls, procs,
                                   max(bills) if bills else ""))
    (out / "index.json").write_text(json.dumps(index), encoding="utf-8")

    # ONE TERM AT A TIME, BECAUSE THAT IS ALL THE PAGE EVER SHOWS. The search
    # has always filtered to a single term -- there is a term picker and
    # render() reads it -- so a visitor was downloading nineteen terms to look
    # at one. With the archive in, index.json is 15.7 MB (1.6 gzipped) and
    # every first visit pays for it before a word can be typed.
    #
    # index.json stays whole because six build steps read it and expect every
    # bill. These are what the browser fetches: the newest term is 0.14 MB
    # gzipped and an archived one about 0.08, fetched only if somebody picks
    # it.
    idx_dir = out / "idx"
    idx_dir.mkdir(exist_ok=True)
    by_term = defaultdict(list)
    for row in index:
        if row.get("term"):
            by_term[row["term"]].append(row)
    for term_, rows_ in by_term.items():
        (idx_dir / f"{term_}.json").write_text(
            json.dumps(rows_, separators=(",", ":")), encoding="utf-8")
    newest_ = max(by_term) if by_term else ""
    print(f"  idx/: {len(by_term)} terms, newest {newest_} "
          f"({len(by_term.get(newest_, [])):,} bills, "
          f"{(idx_dir / f'{newest_}.json').stat().st_size / 1024:,.0f} KB) "
          "-- what a visitor actually loads")

    size = (out / "index.json").stat().st_size / 1024
    print(f"index.json: {size:.0f} KB for {len(index):,} bills "
          f"(roughly {size/4:.0f} KB gzipped, which is what a static host sends)")

    # (term, bill) -> the year its page is under, so a vote can link to the
    # right one of two bills sharing a number.
    bill_year = {(t, b): str(r.get("lsr_year") or "")
                 for t, byb in bills.items() for b, r in byb.items()}
    lg = build_legislators(out, legs, votes_by_member, towns, unnamed,
                           sponsored, bill_year, links, former)

    # ---- home page data ----------------------------------------------------
    # Everything the landing page needs, precomputed here where the full records
    # are already in memory rather than making the browser fetch 2,000 files.
    today = _date.today().isoformat()
    soon = (_date.today() + _td(days=14)).isoformat()
    recent_cut = (_date.today() - _td(days=3650)).isoformat()

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
                upcoming.append({"date": d, "time": pr.get("sched_time"),
                                 "bill": bid, "term": term_,
                                 "committee": pr.get("committee"),
                                 "what": pr.get("proceeding"),
                                 "venue": pr.get("venue")})
    upcoming.sort(key=lambda x: (x["date"], x["time"] or ""))

    # "Most contested" beats "most viewed": it is a fact about the record rather
    # than about traffic, and needs no analytics on a static site.
    contested = sorted([b for b in index if b["nrc"] > 1],
                       key=lambda b: -b["nrc"])[:8]
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
    meta = {"years": sorted(years, reverse=True),
            "terms": sorted({b["term"] for b in index if b["term"]}, reverse=True),
            "committees": sorted({b["committee"] for b in index if b["committee"]}),
            # {"House Finance": "H34"}, so a committee named on a bill card is
            # a link to that committee rather than a dead end -- 3,967
            # mentions across the site, none of them clickable before.
            # Written from data/committees.json, whose codes carry the
            # chamber, because "Finance" alone names one in each.
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
    print(f"  index.json is {size:,.0f} KB and is read by the build "
          "rather than by a browser")
    print(f"-> {out}/")
    print("\nNext: the HTML shell reads idx/<term>.json and meta.json for search and")
    print("facets, then fetches bills/<year>/<id>.json when a card is expanded.")


if __name__ == "__main__":
    main()
