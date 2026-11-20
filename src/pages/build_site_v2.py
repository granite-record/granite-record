#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.305
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
import state_settings as ST
import shell as _shell
import caption_span
import committee_names as CN
# Where the recordings this site links begin: one constant, which about.html
# states in words, report_station splits on, and the stations (stations.py) too.
from about_figures import STREAM_START
# The Speaker's chair, whose occupant's page names the office (member_office).
from seating import SPEAKER_SEAT
# The words the pages say, src/pages/words/: here, the vote words and the study
# reports' (the chip's six, CHIP_WORDS, are parts.py's).
from components import WORDBOOK as _WORDBOOK
import narrative as N
import plain_action as PA
import fiscal
import proceedings as P
import report_check as RC
import rollcall_outcomes as RO
import vote_passage as VP
import senate_hearing_reports as SHR
import sos_archives as SA
import site_read
import sponsor_roster as SR
import spellings
import csv
import functools
import json
import member_figures as MF
import member_links as ML
import motions as MO
import names
import re
import archive_text as AT
import ballot_source as BS
import parse_constitution as PCON
import bill_order as BO
import past_sponsors as PSP
import text_sponsors as TS
import entities as EN
from past_roster import MATCHED as PAST_ROSTER_MATCH, shared_names as past_roster_shared_names
import topic_model as TM
import official_topics as OT
import law_effect as LE
import unicodedata
from collections import Counter, defaultdict, namedtuple
from datetime import date as _date, timedelta as _td

STATUS_ORDER = ["law", "veto", "done", "active"]


def load(p, default):
    """A JSON input, or `default` where the file is not there at all.

    A file that IS there and cannot be read -- cut off mid-array, a permission
    error, MemoryError on the 245 MB narratives.json -- stops the build and
    names the file. It used to return `default` for every failure, and a site
    was built with no journeys or no votes while the shape guards after the
    call, which skip an empty value, passed (bug hunt of 11 November 2026,
    finding 1)."""
    p = Path(p)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default
    except (OSError, MemoryError) as e:
        sys.exit(f"{p} could not be read: {e!r}")
    try:
        return json.loads(text)
    except (ValueError, MemoryError, RecursionError) as e:
        sys.exit(f"{p} is not readable JSON (truncated or corrupt?): {e!r}")



# Sign-ins are filed for a public hearing, so the count belongs on that line.
PUBLIC_HEARING = re.compile(r"public hearing", re.I)


# A BILL'S AMENDMENTS AND ITS TEXT -- the amendments the docket moved, in its
# order, with what each says it changes, and the text's analysis told apart
# from the bill -- are amendments.py's (20 November 2026). Each name is here
# as before.
from amendments import (AMEND_ANY, AMEND_NUM, DASH_RULE, ENACTING, EXPLANATION, FRONT, LEGEND,  # noqa: E402,F401
                        PREAMBLE_END, RSA_CITE_T, TARGET_ALL, TARGET_SECT, _amendment_said,
                        amended_bill, amendment_claims, amendment_num, amendment_targets,
                        amendments_in_text, bill_amendments, bill_text_block)


# AA is adopted, AF and AL are not; and "FAILED" spelled out. The map, and
# why it holds exactly these, are session_days.ADOPTED's: a session day and
# the bill's Votes tab read an amendment's row one way (9 October 2026).
from session_days import ADOPTED, amendment_carried  # noqa: E402,F401


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

    AND AN AMENDMENT IS NAMED BY THE ROW WHOSE COUNT IS ITS ROLL CALL'S (the
    launch audit's recheck of 7 October 2026). The counts of a day can agree
    and its order not: HB 1711 of 2024's floor amendment 2024-1358h, "FLAM #
    2024-1358h ...: AF RC 101-252", was entered the day after the passage it
    preceded, so the docket's order put it second, and roll call 197 -- the
    passage, 204-149 -- was named as that amendment; HB 2 of 2025's 1526h and
    1560h were entered in the other order from their votes, 195-175 and
    203-167, and each roll call carried the other's number. On 38 days of 37
    bills a row so paired states a count its roll call does not have. The
    order is still the docket's sequence; the name is the row's whose count,
    and kind (an amendment or not), the roll call carries (_paired_by_count),
    and a row whose count no roll call of the day carries names nothing.

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
        said = _paired_by_count([raw for _i, raw in rc_lines], mine)
        for j, ((i, raw), r) in enumerate(zip(rc_lines, mine)):
            k = (r.get("body"), r.get("number"))
            order[k] = i
            row = said.get(j)
            am = AMEND_NUM.search(rc_lines[row][1]) if row is not None else None
            if am and "amendment" in (r.get("question") or "").lower():
                names[k] = am.group(1)
    return order, names


# A roll call's count as a docket row states it: "RC 171-162" (the House),
# "RC 16Y-8N" (the Senate).
RC_TALLY = re.compile(r"\bRC\s*\(?\s*(\d{1,3})\s*Y?\s*[-–]\s*(\d{1,3})\s*N?\b", re.I)
AMENDMENT_ROW = re.compile(r"\b(?:FLAM|Amendment)\b", re.I)
PASSAGE_Q = re.compile(r"^\s*(?:Ought\s+to\s+Pass|OTP)\b", re.I)


def _paired_by_count(raws, mine):
    """{position in mine: position in raws}: each roll call of a day (mine,
    in their numbering) and the docket row (raws, in the docket's order) it
    is. In order, except where a pair's counts disagree: those rows and roll
    calls are paired again by count and kind -- an amendment, a passage or
    another motion -- in order within each; one row and one roll call left
    over, of one kind, are each other (a count mistyped); any other left over
    is paired with nothing."""
    def tally(raw):
        m = RC_TALLY.search(raw or "")
        return (int(m.group(1)), int(m.group(2))) if m else None

    def kind(s, question=False):
        s = s or ""
        if PASSAGE_Q.match(s):
            return "passage"
        if ("amendment" in s.lower()) if question else AMENDMENT_ROW.search(s):
            return "amendment"
        return "other"

    def counted(r):
        try:
            return (int(r.get("yeas")), int(r.get("nays")))
        except (TypeError, ValueError):
            return None

    out = {j: j for j in range(min(len(raws), len(mine)))}
    off = [j for j in out if tally(raws[j]) and counted(mine[j])
           and tally(raws[j]) != counted(mine[j])]
    if not off:
        return out
    for j in off:
        out.pop(j)
    rows, rcs = defaultdict(list), defaultdict(list)
    for j in off:
        rows[tally(raws[j]) + (kind(raws[j]),)].append(j)
        rcs[counted(mine[j]) + (kind(mine[j].get("question"), True),)].append(j)
    for key, idx in rows.items():
        if len(rcs.get(key, ())) == len(idx):
            out.update(zip(rcs[key], idx))
    left_rows = [j for j in off if j not in out.values()]
    left_rcs = [j for j in off if j not in out]
    if (len(left_rows) == len(left_rcs) == 1
            and kind(raws[left_rows[0]]) == kind(mine[left_rcs[0]].get("question"), True)):
        out[left_rcs[0]] = left_rows[0]
    return out


# The year a published volume is from, out of the path in its own link. Two
# shapes, because the two files were fetched by different scripts:
#
#   .../Journals/2026/HJ 03 February 5, 2026.PDF
#   .../viewer.aspx?fileName=calendars%5C2026%5CNo10 March 6 2026.pdf
#
# Every one of the 188 keys on file yields a year this way.
SOURCE_YEAR = re.compile(r"(?:%5C|/)(\d{4})(?:%5C|/)", re.I)


def _with_plain(events, bill):
    """Each cited docket line with its plain words beside it (plain_action.py),
    which the Documents tab prints first and the clerk's line under them (the
    person's choice A, 14 October 2026). Only a line with a citation: those
    are the Documents tab's rows, and the rest would only make the page
    heavier.

    Each is read with the docket line after it, in the list's order: HB 2023
    of 2022's "Introduced and Adopted: MA DV 259-66" is its introduction
    because "Ought to Pass" follows it, and HB 1703 of 2016's, with nothing
    after it, its passage too (plain_action._introduced, 16 October 2026)."""
    lines = [ev.get("text") or "" for ev in events]
    for i, ev in enumerate(events):
        if ev.get("cite"):
            words = PA.plain(lines[i], bill, next_line=lines[i + 1] if i + 1 < len(lines) else "")
            if words:
                ev["plain"] = words
    return events


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
# What a bill of each kind has to clear before it is finished (BILL_OF_INTENT,
# SINGLE_CHAMBER, NO_GOVERNOR) is parts.py's (20 November 2026), so that the
# modules this file is split into can read it without importing this file.
from parts import BILL_OF_INTENT, NO_GOVERNOR, SINGLE_CHAMBER  # noqa: E402,F401


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


# A bill's kind by its letters (bill_prefix) is parts.py's, for the same reason.
from parts import bill_prefix  # noqa: E402,F401


# The status vocabulary -- the General Court's status words read against what a
# bill of each kind has to clear (for_bill_kind, STATED), and the statuses of a
# bill never introduced -- is status.py's (20 November 2026), with the rest of
# a bill's status. Each name is here as before.
from status import (NEVER_INTRODUCED, NOT_INTRODUCED, PROPOSED_ONLY, STATED, WITHDRAWN_PRIOR,  # noqa: E402,F401
                    for_bill_kind)


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
# with no session_over in corrections/status/status.txt). A bill left on the table when
# the session ended died there; a veto never put to a vote stood. A bill
# still moving keeps its stage, and a resolution adopted, a constitutional
# amendment's ballot, a bill only proposed for a special session, one the
# House did not introduce and one awaiting the governor keep their own words
# (CHIP_KEEPS): none of them is among the six, and which word they take is
# the person's to say.
#
# The six words (CHIP_WORDS, and a name for each) are parts.py's, read there
# from src/pages/words/chips.json, for the same reason.
from parts import (BECAME_LAW, CHIP_WORDS, DIED, INTERIM_STUDY, TABLED,  # noqa: E402,F401
                   VETOED, WITHDRAWN)
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


# The one question classify() and bill_disposition() both ask
# (journal_not_introduced) is status.py's.
from status import journal_not_introduced  # noqa: E402,F401


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


from rsa_links import (RSA_CITE, RSA_TITLES, _STATUTES, _chapter_key, _statutes,  # noqa: F401
                       rsa_links, rsa_url)


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


_CONSTITUTION = []


def constitution_targets(body):
    """The articles a CACR's text says it changes, as parse_constitution reads
    them against collected/constitution.json, which is read once a build; []
    on a disk without that file."""
    if not _CONSTITUTION:
        _CONSTITUTION.append(PCON.load() or {})
    return PCON.cacr_targets(body, _CONSTITUTION[0])


# The seat's county as the roster spells it (COUNTY_ABBR, COUNTY_OF) and the district
# a label carries (district_tag) are parts.py's, which officials_tabs reads too.
from parts import COUNTY_ABBR, COUNTY_OF, district_tag


# NAMING A MEMBER -- the one way of naming one (member_labels), the address of
# their page (member_slug, own_slug) and the names a record prints read into one
# form (person_name, sort_name, name_key) -- is members.py's (20 November 2026).
# Each name is here as before.
from members import (HONORIFIC, PARTY_INITIALS, _COMPOSITE_RE, _OWN_SLUG, _PARTY_TAIL_RE,  # noqa: E402,F401
                     _PLACEHOLDER_RE, _SUFFIX_RE, _TITLE_RE, member_labels, member_slug, name_key,
                     own_slug, person_name, roster_name_keys, sitting_labels, sort_name)


def is_routine(text):
    return bool(ROUTINE.search(text or ""))


# How the docket writes the governor's signature (SIGNED_RE) is parts.py's, for
# the same reason.
from parts import SIGNED_RE  # noqa: E402,F401


# A BILL'S STATUS, read from its status fields and its docket -- classify,
# classify_stated, closing_stage, next_step and the endings the docket does
# not tell -- is status.py's (20 November 2026). Each name is here as before.
from status import (CLOSING, CONF_NEVER_REPORTED, CONF_REPORT_NOT_TAKEN_UP, CONF_UNABLE_CLOSING,  # noqa: E402,F401
                    DISPOSED, ENDED_UNFINISHED, ENDED_UNVOTED, ENDING_UNTOLD, JOURNAL_SOURCE,
                    ONE_CHAMBER_DONE, RECONSIDER_CARRIED, RETURNED_ROW, SESSION_ENDED_AFTER_FAILED,
                    SESSION_ENDED_AFTER_VOTES, SESSION_ENDED_PLAINLY, UNTOLD_FOR, WITHDRAWN_ACT,
                    _long_date, classify, classify_stated, closing_stage, docket_outcome,
                    floor_disposed, last_decision, next_step, untold_ending, veto_outcome,
                    veto_votes)


# PROCEEDINGS AS STATIONS -- a committee sitting or a floor appearance placed on
# its recording, and the caption times out of step with it withheld first -- are
# stations.py's (20 November 2026). Each name is here as before.
from stations import (CONCURRENCE, concurrence_action, fold_conference_notices, invented_end,  # noqa: E402,F401
                      motion_keys, station_for_floor, station_for_proceeding, weak_marker,
                      withhold_late_captions)


# A BALLOT'S DATE AND PLACE IN A SERVICE, and the one index of every roll call a
# member's Votes tab reads (write_rollcall_index), are members.py's (20 November
# 2026), with the rest of a member's record. Each name is here as before.
from members import service_order, vote_date, write_rollcall_index  # noqa: E402,F401


# EVERY ROLL CALL HAS ITS CARD, A VOTE ON NO BILL TOO (the person, 23 October
# 2026: "every vote on a rep's page should be a roll call in order to know how
# they voted ... The two displays should not be structured differently from
# each other"). A bill's roll calls are cards in its record, which its Votes
# tab draws as a ring with a row for each party's yes and no, and a member's
# Votes tab opens the same ring from that card. A roll call on no bill -- a
# rules suspension, a ruling of the chair, a reprimand -- had no record and so
# no card, and could be drawn only as its two counts. Its card is made here by
# the bill's own code (bill_rollcalls), from the same ballots, and kept a term
# to a file, nobill/<term>.json, {"rollcalls": [card, ...]}, so a member's
# Votes tab draws it with the bill page's own ring. A few hundred roll calls
# across every term; the files are small and fetched only when one is opened.
NOBILL = "nobill"


def write_nobill_cards(out, rollcalls, votes_by_bill, legs, unnamed):
    """Write nobill/<term>.json for every term with a roll call on no bill,
    and return {term: {roll call: index into that file's rollcalls}}."""
    folder = out / NOBILL
    folder.mkdir(parents=True, exist_ok=True)
    found, written = {}, set()
    for term, term_bills in sorted(rollcalls.items()):
        rows = term_bills.get("_procedural") or []
        if not rows:
            continue
        keys = {f"{r.get('year')}-{r.get('body')}-{r.get('number')}" for r in rows}
        # The ballots of these roll calls, wherever build_data filed them: a
        # vote on no bill is filed under its bill column as typed ("", or
        # "HRULE64"), never under "_procedural".
        ballots = defaultdict(list)
        for (t, _b), by_key in votes_by_bill.items():
            if t != term:
                continue
            for k, members in by_key.items():
                if k in keys:
                    ballots[k].extend(members)
        cards = bill_rollcalls("_procedural", term, rows, None,
                               {(term, "_procedural"): ballots}, legs, unnamed)
        at = {}
        for i, c in enumerate(cards):
            c.pop("_ord", None)
            k = c.pop("_rc", None)
            if k:
                at[k] = i
        f = folder / f"{term}.json"
        f.write_text(json.dumps({"term": term, "rollcalls": cards},
                                separators=(",", ":"), sort_keys=True), encoding="utf-8")
        written.add(f.name)
        found[term] = at
    # A term an earlier build wrote and this one has no such vote for.
    for stale in folder.glob("*.json"):
        if stale.name not in written:
            stale.unlink()
    n = sum(len(v) for v in found.values())
    print(f"{NOBILL}/: {n:,} roll calls on no bill, each with its card, in {len(found)} terms")
    # SILENCE IS NOT SUCCESS: the roll calls are there and none found a card.
    if any(t.get("_procedural") for t in rollcalls.values()) and not n:
        print(f"  WARNING: roll calls on no bill exist and {NOBILL}/ holds none of them")
    return found


# THE FLOOR AS A MEMBER'S RECORD READS IT -- the seats of a term (term_seats),
# what the session-day step needs of the floor (write_floor_record) -- and THE
# MEMBERS -- former members and their kept addresses, attendance, the officers
# and the legislator pages' files (build_legislators) -- are members.py's (20
# November 2026). Each name is here as before.
from members import (ATTENDANCE_KIND, FLOOR_RECORD, FORMER_LABEL, MOVED_ADDRESSES,  # noqa: E402,F401
                     _ATTENDANCE_PRESENT, _ATTENDANCE_RANK, _LABEL_SEAT, _SUFFIX, _member_address,
                     _roll_call_key, _surname, attendance_context, ballot_seat, build_legislators,
                     build_officers, corrected_seats, date_former_seats, floor_moment,
                     former_movers, former_roster, keep_moved, last_term_labels, member_attendance,
                     member_office, printed_record, printed_seats, same_person, seat_of_the_lines,
                     sponsored_in_order, term_seats, write_floor_record)


def build_composition(a, legs):
    """Party composition and vacancies, the two chambers' alone.

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

    PARTY_FULL = ST.party_words("name")      # the state's one table of parties
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

    # THE EXECUTIVE BRANCH IS NOT HERE (23 October 2026). The Council and the
    # Governor were read from corrections/status/officials.txt for a "Who
    # holds office" block on the home page; the file was never filled in, so
    # the block never drew, and corrections/officials.json had come to hold
    # the same offices with their sources. Two copies of one fact drift, so
    # the person retired this one: who holds an office is
    # build_members_elect.read_officials's, and the Officials page's.
    return comp, vac


def session_over(path):
    """The day the current term ran out of session days, as corrections/status/status.txt
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
    ms_es = {}  # milestone_es: DATE | LABEL | NOTE, matched to the English one by date
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
            if raw[:1] in " \t" and last_key in ("note", "headline", "note_es"):
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
            elif k == "milestone_es":
                parts = [x.strip() for x in v.split("|")]
                if parts and parts[0]:
                    ms_es[parts[0]] = {
                        "label_es": parts[1] if len(parts) > 1 else "",
                        "note_es": parts[2] if len(parts) > 2 else ""}
            elif k in ("updated", "phase", "headline", "note", "note_es", "session_over"):
                status[k] = v
        for m in status["milestones"]:
            m.update({x: y for x, y in ms_es.get(m["date"], {}).items() if y})
        status["milestones"].sort(key=lambda m: m["date"])
        if status.get("updated"):
            age = (build_date.today() - _date.fromisoformat(status["updated"])).days
            status["stale_days"] = age
            if age > 45:
                print(f"  corrections/status/status.txt was last updated {age} days ago "
                      "\u2014 the page will say so")
    # Latest sitting of either chamber, from the per-chamber map that replaced
    # the old single "most recent session".
    status["last_session"] = (max(v["date"] for v in latest_by_body.values())
                              if latest_by_body else None)
    status["hearings_next_14"] = len(upcoming)

    return status


# A calendar's publication date, out of the filename the viewer link carries:
# "calendars%5C2026%5CNo10%20March%206%202026.pdf". Every one of the 24
# calendars a committee report cites resolves this way, so a report that the
# docket does not date can still be placed on the day it was printed.
# ONE SPACE OR MORE (the walk of 31 October 2026): 2018's House Calendar 39
# is "November%2009%20%202018", two before the year, and every interim report
# it printed had no date. A space as typed counts too (SOURCE_YEAR's second
# shape, "No10 March 6 2026.pdf").
CAL_DATE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October"
    r"|November|December)(?:%20| )+(\d{1,2})(?:%20| )+(\d{4})", re.I)
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


# THE DOCKET'S RECOMMENDATION, in the calendar's words, for a statement the
# calendar printed none for (2004's): interim_report's "rec", "not", "without".
INTERIM_WORDS = {"rec": "RECOMMENDED FOR FUTURE LEGISLATION",
                 "not": "NOT RECOMMENDED FOR FUTURE LEGISLATION",
                 "without": "WITHOUT RECOMMENDATION"}
INTERIM_SIDE = "Interim study report"
INTERIM_FROM_DOCKET = ("The calendar prints no recommendation for this one; the "
                       "recommendation shown is the House docket's.")


def _same_statement(r, s):
    """Whether committee_reports.json's record `r` is the interim study
    statement `s` mis-filed as a report: from the same calendar, and signed
    by the same member or opening on the same words. Every one of the 39 on
    29 October 2026's kit is; a report the calendar printed for the bill
    beside the statement would not be, and stays."""
    if r.get("source") != s.get("source"):
        return False
    lead = lambda x: re.sub(r"\W+", " ", x or "").strip().lower()[:80]
    return any((x.get("author") and x.get("author") == s.get("author"))
               or (lead(x.get("text")) and lead(x.get("text")) == lead(s.get("text")))
               for x in r.get("reports") or [])


def interim_cards(reports, statements, narratives):
    """Put each committee's INTERIM STUDY STATEMENT (interim_statements.py)
    on its bill's Reports tab, as a report of its own, in `reports` -- {term:
    {bill: [report]}}, committee_reports.json's shape -- and return the ones
    held back: [(term, bill, calendar, why)].

    The owner, 29 October 2026: what the committee said, the recommendation
    in plain words, the vote and the calendar, because it matters to anyone
    deciding whether to file the subject again. The docket's one-line
    "Interim Study Report" stays where it is.

    HELD BACK where the docket's own Interim Study Report line disagrees --
    the recommendation, or the vote, both being stated: the calendar and the
    docket are the Clerk's two records of one report, and a page showing one
    over the other would choose without saying so. Three on 29 October
    2026's kit, listed for the Clerk rather than shown.

    A statement the calendar prints no recommendation for (2004 prints none)
    takes the docket's and says so; neither, and it states none.

    The same calendar's report fetch_committee_reports.py mis-filed for the
    bill -- its split takes a statement for an ordinary report now and then,
    HB 1530 of 2024's RECOMMENDED FOR FUTURE LEGISLATION as one of "INTERIM
    STUDY" -- gives way to the statement, so neither shows twice; a report
    of the same calendar that is not the statement (_same_statement) stays."""
    held = []
    for term, byb in (statements or {}).items():
        for bid, sts in byb.items():
            narr = (narratives.get(term) or {}).get(bid)
            d = interim_report(narr, term) if narr else None
            for s in sts:
                why = []
                if d and s.get("rec") and d.get("rec") and s["rec"] != d["rec"]:
                    why.append(f"the calendar says {s.get('printed')}, the docket "
                               f"{INTERIM_WORDS.get(d['rec'], d['rec'])}")
                if d and d.get("vote") and s.get("vote_yeas") is not None and \
                        f"{s['vote_yeas']}–{s['vote_nays']}" != d["vote"]:
                    why.append(f"the calendar's vote is {s['vote_yeas']}-{s['vote_nays']}, "
                               f"the docket's {d['vote'].replace('–', '-')}")
                if why:
                    held.append((term, bid, s.get("source", ""), "; ".join(why)))
                    continue
                printed = s.get("printed") or ""
                from_docket = not printed and bool(d and d.get("rec"))
                if from_docket:
                    printed = INTERIM_WORDS.get(d["rec"], "")
                block = {"side": INTERIM_SIDE, "author": s.get("author", ""),
                         "committee": s.get("committee", ""), "text": s.get("text", "")}
                if s.get("vote_yeas") is not None:
                    block["vote_yeas"], block["vote_nays"] = s["vote_yeas"], s["vote_nays"]
                if from_docket:
                    block["note"] = INTERIM_FROM_DOCKET
                mine = [r for r in (reports.setdefault(term, {}).get(bid) or [])
                        if not _same_statement(r, s)]
                mine.append({"bill": bid, "title": s.get("title", ""), "body": "H",
                             "source": s.get("source", ""), "interim": True,
                             "majority_recommendation": printed or None,
                             "minority_recommendation": None, "reports": [block]})
                reports[term][bid] = mine
    return held


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
        # A HOUSE REPORT ROW THE CLERK ENTERED WITH NO CALENDAR CITED is the
        # calendar's written report of the same committee, recommendation and
        # vote, printed within sixty days after the day the row says it was
        # signed: "Committee Report: Inexpedient to Legislate 03/03/2025 (Vote
        # 18-0; CC)" on HB 125 of 2025 is House Calendar 15's report of 7
        # March, and was shown again below it saying its calendar had not been
        # read (the launch audit of 7 October 2026: 180 bills of 2025-2026).
        # Not SB 110 of 2025's Ways and Means report, 15-1 like Resources' a
        # month before it.
        signed_on = _mdy(e.get("report_date")) or e.get("date", "")
        if (e.get("body") == "H" and not e.get("cite") and signed_on
                and any((r.get("body") or "H") == "H" and r.get("date")
                        and 0 <= _j_days(r["date"][:10], signed_on[:10]) <= 60
                        and any(rec_key(r.get("minority_recommendation" if x.get("side") == "Minority"
                                              else "majority_recommendation"))
                                == rec_key(e.get("recommendation"))
                                and x.get("committee") == e.get("committee")
                                and str(x.get("vote_yeas")) == str(e.get("yeas"))
                                and str(x.get("vote_nays")) == str(e.get("nays"))
                                for x in (r.get("reports") or []))
                        for r in out)):
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


# THE PASSAGE RAIL AND THE JOURNEY are journey.py's (20 November 2026): the four
# stops a bill passes and what happened at each (passage), and what each chamber
# decided and when (journey, journey_rail and the J_ readers). Each name is here
# as before.
from journey import (J_ACTS, J_AMENDED, J_AMEND_ADOPTED, J_AMEND_LIST, J_AMEND_SUBJ,  # noqa: E402,F401
                     J_BARE_REFERRAL, J_CHAPTERED, J_CHAPTER_THEN_DAY, J_CLAUSE_DAY, J_CONF, J_DAY,
                     J_DIVIDED_OUT, J_DONE_VERB, J_EFF_ANY, J_EFF_MORE, J_EFF_PART, J_EFF_PROVIDED,
                     J_EFF_SEVERAL, J_EFF_WHAT, J_ENDING, J_FILED, J_FROM_REPORT, J_IF_PASSED,
                     J_INTRO_ROW, J_MARK, J_MON, J_MONTH_DAY, J_NEW_CONFERENCE, J_NOT_FLOOR,
                     J_NOT_VOTED, J_NO_CODE, J_NO_WORD, J_ON_THE_TABLE, J_OTHER_BILL,
                     J_OUTCOME_ONLY, J_PASSING, J_RC_BARE, J_RECONSIDER, J_RECON_END, J_RECON_NAMES,
                     J_RECON_NOT, J_REFERRED_TO, J_REF_TALLY, J_REMAINING, J_ROW_DAY,
                     J_SECOND_COMMITTEE, J_SIGNED, J_SKIP, J_SUSPEND, J_SUSPENDED, J_SUSP_CODE,
                     J_SUSP_REFERRAL, J_SUSP_VOTE, J_SUSP_WORD, J_TAKES_OUTCOME, J_TALLY,
                     J_TALLY_TAIL, J_THIRD, J_UNSIGNED, J_VETOED, J_VETO_VOTE, J_VOICE, J_WAIVED,
                     J_WRAPPED_TALLY, J_YES_CODE, J_YES_WORD, ONE_CHAMBER, OWN_CHAMBER, RAIL_ACT,
                     RAIL_DEAD_TABLE, RAIL_MARK_OF_CHIP, RAIL_REFINES, RAIL_SAY, STAGES_FROM,
                     _STAGE_END, _j_act, _j_act_sections, _j_amended_on, _j_answers_after,
                     _j_chaptered, _j_clauses, _j_days, _j_decide, _j_effective, _j_effective_parts,
                     _j_gov_more, _j_has_outcome, _j_in_recess, _j_in_term, _j_introduced, _j_iso,
                     _j_merge, _j_motion, _j_motions, _j_outcome, _j_prose_date, _j_reconsidered,
                     _j_roll_call, _j_row_day, _j_rows, _j_second_committee, _j_sections,
                     _j_segments, _j_settle, _j_stated_day, _j_suspension_failed, _j_tally,
                     _j_unfile, _j_unsuspend, _j_untold, _j_vote_words, _j_words, _j_year_slip,
                     _journey_rail, journey, journey_rail, journey_state, law_day, law_in_stages,
                     law_line_dated, passage)


# Written by build_bill_versions.py, which runs before this step. Absent is
# not an error: a tree where that step has not been run yet simply has no
# Versions tab anywhere, which is the truth about that tree.
try:
    VERSIONS = json.loads(
        Path("data/bill_versions.json").read_text(encoding="utf-8"))
except (OSError, ValueError):
    VERSIONS = {}


# ===================================================== THE RAIL'S ENDINGS ==
#
# TWO BILLS THE SESSION'S END KILLED, WITH NO VOTE ON EITHER (the person, 8
# and 9 October 2026). Neither was drawn as dead on a day:
#
#   * A BILL LEFT ON THE TABLE: "Show the body it was tabled in with the
#     yellow pause, and show the red x mark on the law once it died when the
#     session ended". The chamber's stop was the cross on the day it was
#     tabled -- HB 1043 of 2026 read "Senate ✕ 7 May, Law ✕ 7 May" -- and the
#     history said nothing of a death that came three months later. Now the
#     stop is the pause, dated by the tabling; Law is the cross, on the day
#     it died (table_death); and How it got here has the death's line after
#     the tabling's (died_on_table). 2,170 bills in nineteen terms.
#   * A BILL HELD FOR INTERIM STUDY: "same goes for interim study bills that
#     weren't recommended for future legislation by showing the orange icon
#     in the body it was studied in", and a recommended one the same (option
#     (d), the person's answer of 9 October): the chamber keeps its "~", Law
#     takes the cross on the day the chamber that studied it last sat, and
#     How it got here a line of that and one of the committee's report -- an
#     orange arrow where it recommended the subject for future legislation,
#     the "~" where it did not, naming the next term's bill where the docket
#     does (study_ending). 2,392 bills.
#
# WHILE THE SESSION SITS NEITHER IS DEAD, and nothing changes: a bill on the
# table is the pause with Law not reached (its chip Tabled, and none of this
# applies), and one in interim study the "~" with Law not reached.
#
# THE SENATE OF 2026 (the person, 9 October 2026): its session counts as
# ended on 19 August 2026, its last sitting, though its journal says it
# recessed to the call of the chair. Its 52 tabled bills and 107 studied
# bills take that day, "when the Senate last sat"; a row of its own, when the
# clerk enters one, replaces the date by the first rule of table_death.

# The rows that show a chamber sitting: its floor's (narrative.FLOOR_TYPES,
# which has the veto votes) and its vote on a conference report.
SITTING_TYPES = frozenset(N.FLOOR_TYPES) | {"conf_report"}
# A row of a special session on a bill whose number does not say so: SB 1 of
# 2006, "Introduced, MA VV; 2006 Special Session", "Rep Vaillancourt moved
# lay on table; MF VV; 2006 Spec Sess", "Sen. Clegg Moved to Adopt Rules for
# Special Session; MA, VV; SJ, Special Session" -- the special session of 26
# September 2006 on the ballot (SJ SS, "PETITION FOR THE CALLING OF A
# SPECIAL SESSION"). Every row of the bill that day is the special session's.
SPECIAL_SESSION_ROW = re.compile(r"\bspec(?:ial)?\.?\s*ses+(?:ion)?\b", re.I)
# A row that records no sitting: Joint Rule 24(b)'s postponement of what was
# left unacted on, "INDEFINITELY POSTPONED PER JT. RULE 24 (B)", "...BY
# JOINT RULE 24(B)", 18 rows entered on Sunday 1 July 1990 with no motion,
# no vote and no journal. Read as the House's and the Senate's last sitting
# of 1990, they dated the 82 interim study bills of 1989-1990 to a Sunday
# (the review of the rail's endings, 9 October 2026).
NO_SITTING_ROW = re.compile(r"^\s*indefinitely\s+postponed\s+(?:per|by)\s+(?:jt\.?|joint)\s+"
                            r"rule\s*[\w()\s]*$", re.I)


def chamber_sittings(narratives):
    """{(body, year): [each day the chamber sat that year, in order]}, from
    the floor's rows of every bill of every term; and a special session's
    days apart, under (body + "*", year).

    THE LAST OF A YEAR IS ITS ADJOURNMENT, which is what a bill left on the
    table or in interim study died at: the House's of 2026 is 19 August (HJ
    16, "The House adjourned at 3:28 p.m."), the Senate's the same day (SJ
    15), 2020's 16 September for both. The docket does not hold every
    sitting -- the Senate's of 17 June 2004 and 28 June 2006 have no floor
    row -- and with_journals adds the days the journals open.

    NOT A SPECIAL SESSION'S: SSHB 1 of 2013 sat on 7 and 21 November 2013,
    after both chambers had ended their year, and the special session of 18
    November 2015 the same; a bill of the regular session did not die on
    either. Nor 26 September 2006's, whose bill is SB 1 and whose rows say
    "2006 Special Session" (SPECIAL_SESSION_ROW): read as the regular
    session's last sitting, it dated 154 bills of 2006 to it. NOR A DECEMBER
    OF THE SECOND YEAR, which is the next General Court's organization day
    (7 December 2022), not this one's. NOR A ROW THAT RECORDS NO SITTING
    (NO_SITTING_ROW, Sunday 1 July 1990).
    """
    days = defaultdict(set)
    for term_bills in (narratives or {}).values():
        for bid, narr in (term_bills or {}).items():
            evs = (narr or {}).get("events", []) or []
            ss = str(bid).upper().startswith("SS")
            sdays = {e.get("date") for e in evs if not e.get("cancelled")
                     and SPECIAL_SESSION_ROW.search(e.get("raw") or "")}
            for e in evs:
                d, body = e.get("date") or "", (e.get("body") or "")[:1].upper()
                if (e.get("type") not in SITTING_TYPES or e.get("cancelled")
                        or body not in ("H", "S") or not re.match(r"\d{4}-\d\d-\d\d$", d)
                        or (d[5:7] == "12" and int(d[:4]) % 2 == 0)
                        or NO_SITTING_ROW.search(e.get("raw") or "")):
                    continue
                days[(body + ("*" if ss or d in sdays else ""), d[:4])].add(d)
    return {k: sorted(v) for k, v in days.items()}


# A journal of a special session, by its name: "SJ SS.txt" (26 September
# 2006), "SJ SS November 07, 2013.txt", "HJ_SS 1 November 18 2015.txt".
SPECIAL_JOURNAL = re.compile(r"(?:^|[\s_])SS(?:[\s_.,]|$)|special", re.I)


def journal_sittings(roots=None):
    """{(body, year): {each day the chamber's journals on disk open a
    sitting}} -- the House's from 1997, the Senate's from 2003, by their day
    headings alone (journal_days.day_blocks, senate_sittings) -- leaving out
    a journal of a special session by its name. Empty where none is on disk."""
    try:
        import journal_days as J
    except Exception:
        return {}
    out = defaultdict(set)
    for body, root in (roots or (("H", J.HOUSE), ("S", J.SENATE))):
        if not Path(root).is_dir():
            continue
        for yd in sorted(Path(root).glob("[12][0-9][0-9][0-9]")):
            for f in sorted(yd.glob("*.txt")):
                if "erbatim" in f.name or SPECIAL_JOURNAL.search(f.stem):
                    continue
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                text = text.replace("\r\n", "\n").replace("\r", "\n")
                for d, _b in (J.day_blocks(text) if body == "H" else J.senate_sittings(text)):
                    if d and re.match(r"\d{4}-\d\d-\d\d$", d):
                        out[(body, d[:4])].add(d)
    return dict(out)


def with_journals(sittings, journal):
    """chamber_sittings with the days the chambers' journals open a sitting
    on (journal_sittings), where the docket has no floor row: the Senate's
    of 17 June 2004 ("At the time of adjournment on June 17, 2004, the
    following House Bills remained on the table in the Senate", SJ 17) and
    of 28 June 2006 (SJ 17), which the 45 bills of 2004 and the 66 of 2006
    the Senate left on its table or in interim study died at, not the 25
    May 2004 and 24 May 2006 of its last floor rows.

    Not a December of the second year (the organization day, 1 December
    2010), nor a day either chamber sat in a special session by the docket
    (7 November 2013, whose Senate journal is "SJ SS November 07, 2013")."""
    out = {k: list(v) for k, v in (sittings or {}).items()}
    for (body, y), days in (journal or {}).items():
        special = set(out.get(("H*", y)) or []) | set(out.get(("S*", y)) or [])
        add = {d for d in days if d[:4] == y and d not in special
               and not (d[5:7] == "12" and int(y) % 2 == 0)}
        if add:
            out[(body, y)] = sorted(set(out.get((body, y)) or []) | add)
    return out


def term_years(term):
    """(1999, 2000) for "1999-2000"; (0, 0) for anything else."""
    m = re.match(r"(\d{4})-(\d{4})$", term or "")
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


# A row that says the bill died on the table: "Died on Table, Session ended
# 08/19/2026" (the House since 2021), "Died on Table" and "Died On The Table;
# SJ 11A" (both chambers, 2001-2020), "Died on Table (Sine Die)", "Died on
# Table at End of Session", "Died on Table [11/30/2011]", "Died, Session
# Ended" (SSHB 2 of 2010), "Died (All bills Laid on Table, by Sine Die
# Adjournment)", and the Senate's Rule 3-23 that ends a bill still on its
# table: "Inexpedient to Legislate, Senate Rule 3-23, Adjournment
# 10/10/2024", "..., Senate Rule 3-23, 10/31/2025", "Inexpedient to
# Legislate, 2013 Adjournment, Senate Rule 3-23".
TABLE_DEATH_ROW = re.compile(
    r"^\s*died\b|inexpedient\s+to\s+legislate,?\s*(?:\d{4}\s+adjournment,?\s*)?"
    r"senate\s+rule\s+3-23\b", re.I)
ROW_DAY = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")


def died_on_table(steps, chip, status):
    """The line that laid a Died bill on the table it died on, or None: the
    chamber's last tabling, where the bill's status says it died on the table
    or a tabling is the last thing either chamber did, and nothing but the
    death followed it in that chamber."""
    if chip != DIED:
        return None
    hs = [s for s in steps if s.get("body") in ("H", "S")]
    if not (status in ("Died on the table", "Laid on the table")
            or (hs and hs[-1].get("act") == "tabled")):
        return None
    at = next((i for i in range(len(hs) - 1, -1, -1) if hs[i].get("act") == "tabled"), None)
    if at is None:
        return None
    tab = hs[at]
    if any(s.get("body") == tab["body"] and s.get("act") != "died" for s in hs[at + 1:]):
        return None
    return tab


def _sat_by_journal(body, day):
    """Whether the chamber's journal on disk opens a sitting on `day`
    (session_days, which reads only the journals' day headings); False where
    no journal says so, or none is on disk."""
    try:
        import session_days
        return bool(session_days._sat(body, day))
    except Exception:
        return False


# A row that lays a bill on the table (J_ACTS' "tabled"), for table_session_ends.
TABLING_ROW = next(rx for act, rx in J_ACTS if act == "tabled")


def table_session_ends(narratives):
    """{(body, term, year): day} -- the day a chamber's own death rows state
    that the bills it left on its table in `year` of `term` died, where
    every such row states the same day (table_death's first rule); a special
    session's bills under body + "*".

    FOR A BILL WHOSE OWN ROW IS MISSING: HB 266 of 2021, laid on the House's
    table on 9 April 2021 beside HB 111, HB 155 and HB 165, has no row of
    its death, and theirs say "Died on Table, Session ended 01/05/2022" --
    the House adjourned from its 2021 session on 5 January 2022 (HJ 1 of
    2022, "ADJOURN FROM 2021 SESSION"). Its last floor row of 2021 is of 24
    June, which last_sat gave it."""
    seen = defaultdict(set)
    for term, byb in (narratives or {}).items():
        first, last = term_years(term)
        for bid, narr in (byb or {}).items():
            ss = "*" if str(bid).upper().startswith("SS") else ""
            evs = [e for e in (narr or {}).get("events", []) or [] if not e.get("cancelled")]
            for i, e in enumerate(evs):
                raw = e.get("raw") or ""
                if not TABLE_DEATH_ROW.search(raw):
                    continue
                body, entered = (e.get("body") or "")[:1].upper(), e.get("date") or ""
                m = ROW_DAY.search(raw)
                day = _j_iso(m.group(1), m.group(2), m.group(3)) if m else ""
                laid = next((x.get("date") or "" for x in reversed(evs[:i])
                             if (x.get("body") or "")[:1].upper() == body
                             and not TABLE_DEATH_ROW.search(x.get("raw") or "")
                             and TABLING_ROW.search(x.get("raw") or "")), "")
                if (body in ("H", "S") and day and laid and first <= int(day[:4]) <= last
                        and laid <= day <= (entered or day)):
                    seen[(body + ss, term, laid[:4])].add(day)
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}


def table_death(narr, tab, term, sittings, sat=_sat_by_journal, ends=None):
    """(the day a bill left on the table died, the row that says it died or
    None). `tab` is the line that laid it there (died_on_table).

    A BILL LEFT ON THE TABLE DIED WHEN ITS CHAMBER'S SESSION ENDED, never on
    the day it was tabled: counted over all 2,170 such bills on 8 October
    2026, none was taken off a table after its chamber adjourned -- the
    motions to take SB 436 of 2022 and HB 1711 of 2024 off it on their Veto
    Days both failed, 10-13 -- and the Senate's journals list the bills
    still on its table at adjournment (29 September 2016, "remained on the
    table"). The day, in this order:

      1. The day the bill's own death row states, where it is a day of the
         term no later than the row was entered: "Died on Table, Session
         ended 08/19/2026" (HB 609 of 2026); "Inexpedient to Legislate,
         Senate Rule 3-23, Adjournment 10/10/2024"; "..., Senate Rule 3-23,
         10/31/2025", the day the 2025 rule fixed (SB 14 of 2025); "Died on
         Table [11/30/2011]".
      2. Where the row states none -- "Died on Table", "(Sine Die)", "at End
         of Session", "2013 Adjournment, Senate Rule 3-23" -- or one it
         cannot be (HB 201 of 2020's "Adjournment 09/16/2021", entered on 9
         September 2021): the day the chamber adjourned, the last day it
         sat in a year of the term between the tabling and the row
         (adjourned_by). 227 House rows entered on 23 September 2020 are of
         a session that ended on the 16th.
      3. No row, the session over: the day the chamber's rows state for the
         other bills it left on its table that year, where they agree
         (`ends`, table_session_ends: HB 266 of 2021, 5 January 2022); else
         the last day the chamber sat in the year the bill lay there
         (last_sat), which the line says in as many words. The Senate's 52
         bills of 2026, HB 1043 among them, take 19 August 2026; the House's
         112 of 2022 its days.

    The row is the death's own in the chamber whose table it was, where it
    has one: SB 698 of 2020, which the House laid on its table, carries the
    Senate's Rule 3-23 row and the House's "Died on Table"."""
    body, laid = tab["body"], tab.get("date") or ""
    special = str((narr or {}).get("bill") or "").upper().startswith("SS")
    evs = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
    rows = [e for e in evs if TABLE_DEATH_ROW.search(e.get("raw") or "")
            and (e.get("date") or "") >= laid]
    row = next((e for e in rows if (e.get("body") or "")[:1].upper() == body),
               rows[0] if rows else None)
    if row is None:
        peer = (ends or {}).get((body + ("*" if special else ""), term, laid[:4]))
        if peer and peer >= laid:
            return peer, None
        return last_sat(body, laid, term, sittings, special), None
    entered = row.get("date") or ""
    first, last = term_years(term)
    m = ROW_DAY.search(row.get("raw") or "")
    day = _j_iso(m.group(1), m.group(2), m.group(3)) if m else ""
    if day and first <= int(day[:4]) <= last and laid <= day <= (entered or day):
        return day, row
    return adjourned_by(body, laid, entered, term, sittings, sat, special), row


def adjourned_by(body, laid, entered, term, sittings, sat=_sat_by_journal, special=False):
    """The day the chamber adjourned with the bill on its table, by a row
    entered on `entered` that states no day: the last day it sat in the
    latest year of the term to end between the tabling and the row.

    THE ROW'S OWN DAY, where the chamber's journal opens a sitting on it
    after the last of its floor's that year, and no special session sat
    then: the House's "Died on Table" rows of 30 November 2017 were entered
    on the day it adjourned (HJ 21, "stand adjourned from the 2017 House
    Session"), when it voted on nothing, and the Senate's 2013 Rule 3-23
    rows on 3 September 2013, a sitting of its own. Not 18 November 2015,
    the special session's day the House entered its "Died on the Table" on
    26 measures of 2015, which died with the regular session.

    A SPECIAL SESSION'S BILL BY ITS OWN DAYS (`special`): SSHB 2 of 2010,
    laid on the House's table on 9 June 2010 and "Died, Session Ended" the
    same day. Where no day the chamber sat is known, none is given.

    A FIRST YEAR'S SESSION RECESSED INTO THE SECOND ended on the day it was
    called back to order and adjourned, the chamber's first sitting of the
    second year, where the row was entered that January (the review of the
    rail's endings, 9 October 2026): the House's of 2013 and 2019 -- "Although
    the June 26, 2013 Session continues here, the actual date is January 8,
    2014" (HJ 20 cont.), "The recessed Session of September 25, 2019 was
    called to order by the Speaker on January 8, 2020" (HJ 23 cont.), each
    then "adjourn[ed] from the 2013 [2019] Session" -- and the Senate's of
    2005, out of recess and adjourned on 4 January 2006 (SJ 24 cont.). Their
    "Died on Table" rows were entered on 8 January 2014, 9 January 2020 and
    4 January 2006; and the House's own rows of 2021 say so in as many words,
    "Died on Table, Session ended 01/05/2022". The 13, 29 and 25 bills of
    those tables were dated 26 June 2013, 25 September 2019 and 16 November
    2005."""
    first, last = term_years(term)
    if not (first and laid):
        return ""
    key = body + ("*" if special else "")
    if (not special and entered and int(laid[:4]) == first and entered[:4] == str(last)
            and entered[5:7] == "01"):
        opened = (sittings.get((body, str(last))) or [""])[0]
        if opened and opened[5:7] == "01" and laid <= opened <= entered:
            return opened
    upto = entered or laid
    years = range(max(int(laid[:4]), first), min(int(upto[:4]), last) + 1)
    ends = []
    for y in years:
        days = sittings.get((key, str(y))) or []
        if days and laid <= days[-1] <= upto:
            ends.append(days[-1])
    if not special and entered and first <= int(entered[:4]) <= last and entered >= laid:
        days = sittings.get((body, entered[:4])) or []
        sessions = sittings.get((body + "*", entered[:4])) or []
        if ((not days or entered > days[-1]) and entered not in sessions
                and sat is not None and sat(body, entered)):
            ends.append(entered)
    if ends:
        return max(ends)
    within = [d for y in years for d in sittings.get((key, str(y))) or [] if laid <= d <= upto]
    return max(within, default="")


# Since when each chamber's adjournment killed the bills left on its table
# in the first year of a term, as the record shows it: the Senate from 2001,
# the House from 2007 (the review of the tabled bills, 8 October 2026).
# Before them a bill tabled in the first year carried over into the second
# -- the House calendar of 2000 says its bills "remained on the table" at
# the adjournment of 3 November 1999, and HB 536 came off it in 2000.
FIRST_YEAR_TABLE_DIES = {"S": 2001, "H": 2007}


def last_sat(body, laid, term, sittings, special=False):
    """The last day the chamber sat in the year a bill tabled on `laid` lay
    there: that year's, or the term's second year's for a first-year tabling
    of a chamber that carried them over (FIRST_YEAR_TABLE_DIES); a special
    session's own days for its bill. Never before the tabling, and none
    where no day the chamber sat is known."""
    first, last = term_years(term)
    if not (first and laid):
        return ""
    y = int(laid[:4])
    if y < last and y < FIRST_YEAR_TABLE_DIES.get(body, 0):
        y = last
    days = sittings.get((body + ("*" if special else ""), str(y))) or []
    return max(days[-1], laid) if days else ""


def table_death_line(narr, tab, steps, term, sittings, sat=_sat_by_journal, ends=None):
    """The line of How it got here that says the bill died on the table: a
    new one, or the journey's own where it already has the death's in that
    chamber -- the Senate's Rule 3-23 ("Killed under Senate Rule 3-23, still on the table at
    adjournment"), or the 1990s motion that killed "the other bills left on
    the table" -- whose day is set to table_death's where its row's is not
    the day it died: HB 201 of 2020's line had no day, its row saying
    "Adjournment 09/16/2021", and its Law stop none.
    Returns (line, day, how): `how` is "row" or "sat" for a new line, and
    "line" where `line` is the journey's own, which the caller does not add."""
    day, row = table_death(narr, tab, term, sittings, sat, ends)
    at = next(i for i, s in enumerate(steps) if s is tab)
    had = next((s for s in steps[at + 1:] if s.get("body") == tab["body"]
                and s.get("act") == "died"), None)
    if had is not None:
        if (row is not None and (had.get("text") or "").startswith("Killed under Senate Rule 3-23")
                and had.get("date") in ("", row.get("date")) and day and had.get("date") != day):
            had["date"] = day
        return had, had.get("date") or day, "line"
    chamber = {"H": "House", "S": "Senate"}[tab["body"]]
    text = ("Died on the table when the session ended" if row is not None else
            f"Still on the table when the {chamber} last sat; died there when the "
            "session ended")
    return ({"date": day, "body": tab["body"], "act": "died", "mark": "x", "text": text,
             "short": "died on table"}, day, "row" if row is not None else "sat")


# What a history already says of a death on the table, in its own words or a
# closing paragraph's: narrative.py's "The bill died on the table when the
# session ended ..." and "... under Senate Rule 3-23", the 1990s' kill of
# "all bills on table", CLOSING's "died when the session ended".
TOLD_TABLE_DEATH = ("died on the table", "died there", "rule 3-23", "session ended",
                    "died when the session", "bills on the table", "bills laid on the table",
                    "left on the table")


def table_death_told(narr, tab, day, how, line=None, ending=None):
    """The sentence a history ends with where it does not tell the bill's
    death on the table, or None where it does: in narrative.py's own words
    for a row it reads ("died", "senate_rule_kill"), so a history that comes
    to tell the row itself says the same; and where no row is on the docket,
    in the words of the line (table_death_line). `line` is the death's line
    of How it got here."""
    told = " ".join([s.get("text", "") for s in (narr or {}).get("stages", [])]
                    + [(ending or {}).get("text", "")]).lower()
    if any(g in told for g in TOLD_TABLE_DEATH) or not day:
        return None
    chamber = {"H": "House", "S": "Senate"}[tab["body"]]
    if how == "sat":
        return (f"It was still on the {chamber}'s table when the {chamber} last sat, on "
                f"{_long_date(day)}, and it died there when the session ended.")
    said = (line or {}).get("text") or ""
    if said.startswith("Killed under Senate Rule 3-23"):
        adj = " at adjournment" if said.endswith("at adjournment") else ""
        return (f"The bill died on the table under Senate Rule 3-23{adj} on {_long_date(day)}, "
                "having been set aside and never taken back up.")
    if how == "line":
        return (f"The bill died on the table on {_long_date(day)}, having been set aside and "
                "never taken back up.")
    return (f"The bill died on the table when the session ended on {_long_date(day)}, "
            "having been set aside and never taken back up.")


# THE INTERIM STUDY COMMITTEE'S REPORT, in every wording the docket has used
# (the review of interim study, 8 October 2026): "INT STUDY REPORT ITL FOR
# 1991 SESSION (VOTE 11-0)" (1989-90), "INT STUDY REPORT (ITL) FILED (VOTE
# 11-0)" (1991-92), "INT STUDY REPT: REC FOR LEG IN 1997 (VOTE 17-0) <LSR
# 97-0155>" (1993-98), "Int Study Report: REC FOR LEGIS IN 2001 (vote 14-0)",
# "Interim Study Report: Recommended for Future Legislation in 2009 (Vote
# 11-0)", "Interim Study Report: Without Recomendation (Vote 10-10)" (2024),
# "Interim Study Report: Not Recommended for Future Legislation 09/29/2026
# (Vote 8-2; )", "Interim Study Report: No Recommendation" (HB 1592 of
# 2014). STUDY_REPORT read the last two wordings alone, 751 of the 1,534
# reports.
# The interim study report's row, its tally and the year it names, read as
# the committee pages read them: committee_acts holds the patterns, and
# study_said what a report recommends, so that one row is read one way on
# both (9 October 2026).
from committee_acts import (INTERIM_REPORT_ROW, INTERIM_REPORT_TALLY,  # noqa: E402
                            INTERIM_REPORT_YEAR, study_said)


def interim_report(narr, term=""):
    """What the interim study committee reported, or None: {"date", "body",
    "rec": "rec", "not" or "without" (or "" where the row states none),
    "vote": "17–0", "year": "1997" where it names the next term's first year}.
    The majority's report over the minority's (HB 1561 of 1994 has both),
    and of several the latest."""
    reps = [e for e in (narr or {}).get("events", []) or []
            if not e.get("cancelled") and INTERIM_REPORT_ROW.search(e.get("raw") or "")]
    if not reps:
        return None
    maj = [e for e in reps if not re.search(r"\bMIN\b", e.get("raw") or "", re.I)] or reps
    e = max(maj, key=lambda x: x.get("date") or "")
    raw = e.get("raw") or ""
    rec = study_said(raw)
    t = INTERIM_REPORT_TALLY.search(raw)
    y = INTERIM_REPORT_YEAR.search(raw)
    nxt = term_years(term)[1] + 1 if term else 0
    return {"date": e.get("date") or "", "body": (e.get("body") or "")[:1].upper(),
            "rec": rec, "recommended": rec == "rec",
            "vote": f"{t.group(1)}–{t.group(2)}" if t else "",
            "year": y.group(1) if y and nxt and int(y.group(1)) == nxt else ""}


# THE NEXT TERM'S BILL, where the clerk wrote down its LSR (1991-1998): "<LSR
# 97-0155>" on the report itself (HB 1179 of 1996), "1995 LSR: 0131" (HB 1162
# of 1994, which is HB 581 of 1995), "<1995 LSR 0108>", "(SEE LSR 0175,
# 1993)", "{LSR 0155, HB 154, CH. 183, 1997 SIGNED BY GOV 6/18/97}". A "?"
# after the number is the clerk's own doubt, and the line says so.
NEXT_LSR = (
    re.compile(r"<\s*LSR\s+(?P<yy>\d{2})\s*-\s*(?P<num>\d{1,4})(?P<q>\?)?", re.I),
    re.compile(r"(?P<yyyy>(?:19|20)\d\d)\s+(?:MIN\s+REPT\s+)?LSR\s*:?\s*(?P<num>\d{1,4})(?P<q>\?)?",
               re.I),
    re.compile(r"\bSEE\s+LSR\s+(?P<num>\d{1,4})(?P<q>\?)?\s*,\s*(?P<yyyy>(?:19|20)\d\d)", re.I),
    re.compile(r"\{\s*LSR\s+(?P<num>\d{1,4})(?P<q>\?)?\s*,\s*(?P<bill>[A-Z]+)\s*(?P<bnum>\d+)",
               re.I),
)


def lsr_bills(bills):
    """{(term, LSR number): (bill, year)} over every term, for the next term's
    bill a clerk's LSR note names. Within a term the number is the bill's
    own: the 1990s numbered a second year's requests from 2000 up. Keyed by
    the term, not the year, because a bill carried into the second year is
    filed under it: "1995 LSR: 0171" on HB 1261 of 1994 is HB 207, whose
    docket rows of 1995 carry the session year 1996. A number two bills of a
    term carry is left out. `year` is the bill's year on this site, its
    address and the one its card names."""
    seen, out = Counter(), {}
    for term, byb in (bills or {}).items():
        for bid, b in byb.items():
            try:
                k = (term, int(str(b.get("lsr_num") or "").lstrip("0") or 0))
                y = int(b.get("lsr_year") or 0)
            except ValueError:
                continue
            if k[1] and y:
                seen[k] += 1
                out[k] = (bid, y)
    return {k: v for k, v in out.items() if seen[k] == 1}


def next_term_bill(narr, term, lsrs):
    """{"id", "year", "queried"} -- the next term's bill a clerk's LSR note
    on this one names, by the next term's first year and the number, where
    it resolves to a bill of that term -- or None."""
    end = term_years(term)[1]
    nxt, after = end + 1, f"{end + 1}-{end + 2}"
    if not (end and lsrs):
        return None
    got = []
    for e in (narr or {}).get("events", []) or []:
        raw = e.get("raw") or ""
        for rx in NEXT_LSR:
            for m in rx.finditer(raw):
                g = m.groupdict()
                y = (int(g["yyyy"]) if g.get("yyyy") else
                     (1900 if int(g["yy"]) > 50 else 2000) + int(g["yy"]) if g.get("yy") else nxt)
                hit = lsrs.get((after, int(g["num"]))) if y == nxt else None
                if not hit:
                    continue
                if g.get("bill") and hit[0].upper() != f"{g['bill']}{g['bnum']}".upper():
                    continue
                got.append({"id": hit[0], "year": hit[1], "queried": bool(g.get("q"))})
    if not got:
        return None
    return next((x for x in got if not x["queried"]), got[0])


def study_ending(narr, steps, rail, term, sittings, lsrs=None):
    """The lines How it got here ends with for a bill held for interim study
    once its session is over: the death, and the committee's report.

    IT DIED WHEN ITS SESSION ENDED, on the last day the chamber that studied
    it sat: counted over all 2,392 interim study bills of nineteen terms on 8
    October 2026, no row says one died, and none was acted on after that day.
    Since 1993 every referral is of the second year; the 23 of the first
    year, the Senate's of 1989 and 1991, take the second year's day too.

    THE REPORT IS ADVICE, NOT AN ACT ON THE BILL (House Rule 44(a) as
    amended in 1997, Rule 45(a) of 2025: the committee "shall submit ... its
    findings and any recommendations"), dated by the report and usually after
    the death: SB 570 of 2026 died on 19 August and was recommended for future
    legislation, 9-0, on 28 September. Its line is a green arrow where the
    committee recommended the subject come back as a new bill, and names
    that bill where the clerk wrote down its LSR; the "~" where it did not,
    or made no recommendation at all. The Senate files none."""
    hs = [s for s in steps if s.get("body") in ("H", "S")]
    study = next((s for s in reversed(hs) if s.get("act") == "study"), None)
    if study is not None:
        body = study["body"]
    elif rail and rail[0] in ("H", "S") and "x" in rail[1:3]:
        order = (rail[0], "S" if rail[0] == "H" else "H")
        body = order[rail[1:3].index("x")]
    else:
        return []
    chamber = {"H": "House", "S": "Senate"}[body]
    special = str((narr or {}).get("bill") or "").upper().startswith("SS")
    days = sittings.get((body + ("*" if special else ""), str(term_years(term)[1]))) or []
    day = days[-1] if days else ""
    if study is not None and day and (study.get("date") or "") > day:
        day = study["date"]
    out = [{"date": day, "body": body, "act": "died", "mark": "x",
            # THE PERSON'S WORDS (approved 17 October 2026), with the fall
            # named by its year so the line reads true in any later year: it
            # said "Still in interim study when the House last sat; died when
            # the session ended" beside an Interim Study chip and a work
            # session still to come.
            "text": (f"In interim study: the committee studies the subject in the fall of "
                     f"{term_years(term)[1]}; the bill goes no further"),
            "short": "died in interim study"}]
    rep = interim_report(narr, term)
    if rep:
        # SAID AS EVERY OTHER PLACE SAYS IT (23 October 2026): the phrase is
        # study_report.json's, which the docket's plain line, the bill's
        # closing note, a committee's meeting card and the emails take too;
        # this line adds the next term's year where the clerk wrote one.
        sr = _WORDBOOK["study_report"]
        words = sr["said"].get(rep["rec"])
        if words and rep["year"] and rep["rec"] != "without":
            words += f" in {rep['year']}"
        text = (f"{sr['head']}: {words}" if words else f"{sr['head']} filed") + (
            f", {rep['vote']}" if rep["vote"] else "")
        line = {"date": rep["date"], "body": rep["body"] if rep["body"] in ("H", "S") else body,
                "act": "study_report", "mark": "f" if rep["rec"] == "rec" else "s",
                # Which of the three it said, for its colour (app.js journeyList).
                "rec": rep["rec"], "text": text, "short": "interim study report"}
        nb = next_term_bill(narr, term, lsrs)
        if nb:
            name = re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", nb["id"]) + f" of {nb['year']}"
            line["text"] += (f"; the clerk noted, with a question mark, that it was filed "
                             f"again as {name}" if nb["queried"] else f"; filed again as {name}")
            line["link"] = {"text": name, "href": f"bill/{nb['year']}/{nb['id'].lower()}"}
        out.append(line)
    out.sort(key=lambda s: s.get("date") or "9999")
    return out


def session_endings(narr, steps, rail, chip, status, term, over, sittings, lsrs=None,
                    ending=None, sat=_sat_by_journal, ends=None):
    """The rail's endings for one bill, as build_bills makes them: the lines
    How it got here ends with, added to `steps`, for a bill that died on the
    table (table_death_line) and for one held for interim study whose
    session is `over` (study_ending). Returns (tabled, ending): the line that
    laid a bill that died on the table there, for journey_rail; and the
    history's closing paragraph (closing_stage's `ending`), with the death's
    sentence where the history does not tell it (table_death_told)."""
    tabled = died_on_table(steps, chip, status)
    if tabled is not None:
        line, day, how = table_death_line(narr, tabled, steps, term, sittings, sat, ends)
        if how != "line":
            steps.append(line)
        said = table_death_told(narr, tabled, day, how, line, ending)
        if said and ending:
            ending = {**ending, "text": f"{ending['text']} {said}"}
        elif said:
            ending = {"label": "How It Ended", "text": said}
    elif chip == INTERIM_STUDY and over:
        steps.extend(study_ending(narr, steps, rail, term, sittings, lsrs))
    return tabled, ending


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

# The lines the session's end makes (table_death_line, study_ending), which
# no row of the docket decided.
SESSION_END_DEATHS = ("In interim study:", "Still on the table when",
                      "Died on the table when the session ended")


def session_end_line(s):
    """Whether a line of How it got here is one the session's end made."""
    return s.get("act") == "study_report" or (
        s.get("act") == "died" and (s.get("text") or "").startswith(SESSION_END_DEATHS))


def journey_disagrees(steps, kind, status, rail, bid):
    """Why the journey, the bill's status and its rail do not tell one story,
    or "" where they do. Each is a claim the page makes about the same bill,
    and this is the test that they are one claim.

    Read against the status the bill carries and the marks the list card
    draws, so the answer is about what a reader sees.

    Without the lines the session's end makes (session_end_line), which no
    row decided: they say how a bill already stopped ended, and read as the
    chamber's last word they would make a journey that never names the
    decision agree with its status -- HB 715 of 1989, studied by a Senate
    no line of its journey has."""
    steps = [s for s in (steps or []) if not session_end_line(s)]
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
    if (status.startswith("One chamber did not concur")
            or status in ("In a committee of conference", CHAMBERS_APART)):
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


# ONE LABEL A NAME, CHAMBER AND PARTY (16 October 2026,
# private/SITE_DATA_PROFILE.md, P3). bill_rollcalls asks vote_member for each
# of 2.2 million ballots, and each asking ran member_labels -- person_name,
# sort_name and three patterns -- for the same few thousand people. The pair
# vote_member uses, the name drawn and the name sorted, depends only on the
# name it settles on, the chamber and the party, so the pair is kept by those
# three. The entry is built fresh around it on every call and the dict
# member_labels returns is never kept, so no caller can change what the next
# is given. The unnamed member is noted before the pair is looked up, so that
# every ballot naming nobody is noted, kept pair or not. A key no dict can hold
# is labelled afresh, as before.
_VOTE_LABELS = {}


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
    chamber = legs.get(m.get("member_id"), {}).get("chamber") or body
    key = (raw, chamber, m.get("party"))
    try:
        display, sort = _VOTE_LABELS[key]
    except KeyError:
        lab = member_labels(raw, chamber=chamber, party=m.get("party"))
        display, sort = _VOTE_LABELS[key] = (lab["display"], lab["sort"] or sort_name(raw))
    except TypeError:
        lab = member_labels(raw, chamber=chamber, party=m.get("party"))
        display, sort = lab["display"], lab["sort"] or sort_name(raw)
    return {"n": display, "s": sort, "p": m.get("party") or "X", "v": m.get("vote")}


MOVER_HONORIFIC = re.compile(r"^(?:Rep|Sen|Representative|Senator)s?\.?\s+", re.I)
MOVER_SUFFIX = re.compile(r",?\s+(?:Jr|Sr|II|III|IV)\.?$", re.I)


_SPELLINGS = []


def _spellings():
    """member_corrections.json's spellings, read once a run."""
    if not _SPELLINGS:
        _SPELLINGS.append(spellings.load())
    return _SPELLINGS[0]


def mover_member(mover, body, legs, pages=None):
    """{"label", "slug"} of the one sitting member of `body` the docket's
    mover can mean -- "Rep. Alexander Jr." is Rep. Joe Alexander (R - Hills
    29), the only Alexander in the House -- or None where the name is no
    one's or more than one's. A WRONG LINK IS WORSE THAN NO LINK: a surname
    two members of the chamber share is left as the docket wrote it, and a
    full name ("Peter Schmidt") is tried before the surname alone.

    `legs` is the members the name is looked for among (mover_pool says
    which), and `pages` {id: member}, where given, whose page each of them
    links to now: `legs` is then a term's own roster as it was frozen, which
    gives the seat held in that term, and the link goes to the person's own
    page as it is now (own_slug), or nowhere where they have none. A member
    of term_voters' carries `held`, the seat of the term, which names them; a
    voter with no seat of the term is not linked."""
    n = MOVER_SUFFIX.sub("", MOVER_HONORIFIC.sub("", (mover or "").strip())).strip().strip(".")
    ch = (body or "").strip().upper()[:1]
    if not n or not ch:
        return None
    # A name the record misspells, as a person put it right (spellings.py):
    # "Rep. Poloszaj" is looked up as Ploszaj.
    n = spellings.respell(ch, n, _spellings())
    pool = []
    for m in (legs or {}).values():
        if (m.get("chamber") or "").strip().upper()[:1] != ch or "," not in (m.get("name") or ""):
            continue
        last, first = (x.strip() for x in m["name"].split(",", 1))
        pool.append((MOVER_SUFFIX.sub("", last).lower(), f"{first.split()[0] if first.split() else ''} "
                     f"{MOVER_SUFFIX.sub('', last)}".lower(), m))
    want = n.lower()
    cands = [m for _l, full, m in pool if full == want] or (
        [m for last, _f, m in pool if last == want] if " " not in want else [])
    if len(cands) != 1:
        return None
    m = cands[0]
    lab = member_labels(m.get("name"), chamber=m.get("chamber"),
                        party=m.get("party_code") or m.get("party"), district=m.get("district"),
                        county=m.get("county"), county_abbr=m.get("county_abbr"))
    label = lab.get("display_full") or m.get("label") or ""
    # A TERM'S VOTER (term_voters) is named by the seat the term gives them,
    # and by no other: one with no seat of the term stays words.
    if "held" in m:
        label = m["held"]
        if not label:
            return None
    if pages is not None:
        page = pages.get(str(m.get("id") or ""))
        slug = own_slug(page) if page else ""
        return {"label": label, "slug": slug} if slug else None
    return {"label": label,
            "slug": m.get("slug") or member_slug(m, lab)}


# "(D - Rock 37)" at the end of a member's label: the party's letter.
_LABEL_PARTY = re.compile(r"\(([A-Z])\b[^()]*\)\s*$")


def report_author(author, body, legs, pages=None):
    """{"label", "slug", "party_code"} for the member a committee report says
    wrote it -- "Rep. David Meuse", "Senator Daryl Abbas" -- or None. A WRONG
    MEMBER IN A CHIP IS A FACTUAL ERROR AND A MISSING CHIP IS NOT: the name is
    taken only where mover_member finds exactly one member of the report's
    chamber it can mean, among `legs` and `pages` as mover_pool gives them
    (the term's own members, with the seat each held then), and only a name
    with its chamber's title; anything else stays the report's words. The
    party is the label's own, so the chip's colour is the seat's of the term."""
    said = (author or "").strip()
    if not MOVER_HONORIFIC.match(said):
        return None
    who = mover_member(said, body, legs, pages=pages)
    if not who or not who.get("label") or not who.get("slug"):
        return None
    m = _LABEL_PARTY.search(who["label"])
    return {**who, "party_code": m.group(1) if m else ""}


def report_authors(written, legs, pages=None):
    """Each written report's sides gain `author_m` (report_author) where the
    author can be named; a House Calendar report is the House's, a report
    that says "S" the Senate's."""
    for r in written or ():
        body = "S" if (r.get("body") or "").upper().startswith("S") else "H"
        for e in r.get("reports") or ():
            if e.get("author"):
                who = report_author(e["author"], body, legs, pages)
                if who:
                    e["author_m"] = who


def term_voters(votes_by_member, seats):
    """{term: {"<id>|<chamber>": member}}: THE MEMBERS OF EACH TERM'S CHAMBERS,
    AS THEIR OWN BALLOTS OF THE TERM GIVE THEM -- everyone who voted in that
    chamber that term, those who left mid-term and those who came in among
    them -- each with `held`, the seat the term gives them (term_seats, the
    seats a session day names them by), or "" where it gives none, or gives
    the other chamber's. For mover_pool, in the terms no frozen roster
    describes. The name and party are the term's last ballot's."""
    out = defaultdict(dict)
    for mid, rows in votes_by_member.items():
        mid = str(mid)
        for v in sorted(rows, key=service_order):
            body = (v.get("body") or "").strip().upper()[:1]
            if body not in ("H", "S") or "," not in str(v.get("name") or ""):
                continue
            t = P.vote_term(v["year"], v.get("date"))
            held = (seats.get(t) or {}).get(mid) or ""
            out[t][f"{mid}|{body}"] = {
                "id": mid, "name": v["name"], "chamber": body,
                "party_code": v.get("party") or "",
                "held": held if held.startswith(("Sen. " if body == "S" else "Rep. ")) else ""}
    return dict(out)


def mover_pool(term, current, legs, term_rosters, people, voters=None):
    """(members, pages) a mover of `term` is looked for among, for
    mover_member: THE TERM'S OWN MEMBERS, WITH THE SEAT EACH HELD IN IT
    (labels-use-the-seat-held-at-the-time). A term whose own roster is frozen
    and is not the sitting one (`term_rosters`, freeze_term.own_roster_terms)
    takes that roster, linked to each person's page as it is now (`people`,
    build_bills' every member and former member); the current term, while its
    roster is the sitting one, takes `legs`; a term before it, its own voters
    (`voters`, term_voters: the owner, 19 November 2026, "Yes, link them"),
    each named by the seat of the term and linked to the page their ballots
    are on (`people`); any other term -- 1989-1998, with no ballots -- nobody,
    and the docket's words stand.

    The rehearsal of the turn (19 November 2026): matched against the sitting
    roster for the current term alone, 2025-2026 lost the link on 843 movers
    of 647 bills the night 2027-2028 became the current term, and between
    Organization Day and the switch, with the next House installed and the
    term still current, a name would have been looked for among the next
    House, where a member who left at the election is nobody, or a newcomer
    who shares the surname."""
    if term in (term_rosters or {}):
        return term_rosters[term], people
    if term == current:
        return legs, None
    if term in (voters or {}):
        return voters[term], people
    return None, None


# A MEMBER NAMED IN THE STORY: "offered by Rep. Jane Smith", "Sen. Bradley
# moved". The honorific, then up to three capitalised words, tried longest
# first, so "Rep. Smith Amendment" falls back to "Rep. Smith".
STORY_PERSON = re.compile(r"\b(Rep|Sen)\.\s+((?:[A-Z][\w'\u2019.-]*)(?:\s+[A-Z][\w'\u2019.-]*){0,2})")


def story_people(texts, legs, pages=None):
    """[{"text", "label", "slug"}]: each member the story names as the docket
    did -- a mover, the member who offered an amendment -- where the words
    can mean one sitting member of that chamber (mover_member). The page
    links them where they stand (the person, 10 October 2026: "movers in
    story text not linked"). A WRONG LINK IS WORSE THAN NO LINK, so a name
    two members share stays words. `legs` and `pages` are mover_pool's, as
    for a roll call's mover."""
    out, seen = [], set()
    for text in texts:
        for m in STORY_PERSON.finditer(text or ""):
            hon, words = m.group(1), m.group(2).split()
            for k in range(len(words), 0, -1):
                said = f"{hon}. {' '.join(words[:k])}".rstrip(".,")
                if said in seen:
                    break
                who = mover_member(said, "H" if hon == "Rep" else "S", legs, pages=pages)
                if who and who.get("slug") and who.get("label"):
                    seen.add(said)
                    out.append({"text": said, **who})
                    break
    return out


def sponsor_record_chambers(sponsors, table="auto", people=None):
    """{(employee number, term): "H" | "S"}: the chamber the Manual for the General Court of
    the term seats a 1989-1998 sponsor in, for each row the General Court's sponsor record
    supplies itself (past_sponsors.filled) that is linked to a member, where the term's seat
    list names that one person and was read without doubt (past_roster.term_seat). For the
    member's "On Record" line: bill_sponsor_list's `ch`.

    A ROW OF THE RECORD HOLDS A CHAMBER AND NO SEAT, and before 1999 the chamber is the
    member's last (the review before the release of 16 November 2026): past_sponsors gives a
    row the chamber its number voted in that term, else the roster's, the legislators table's
    or the list of members', and no number voted before 1999. Measured for that review, on
    past_sponsors.json of 7 November, the Manual seated 402 of the 486 linked rows of those
    terms, each in the row's own chamber; the other 84 it does not name without doubt, and
    they keep their own. {} where no such row is linked to a member, or the seat list is not
    on this disk. `table` and `people` stand in for generated/manual_seats.json and the files
    past_sponsors.load_people reads."""
    import past_roster as PR
    want = {(str(s["employee"]), term) for term, s in sponsor_record_rows(sponsors)}
    table = (PR.seat_table() if table == "auto" else table) if want else None
    if not table:
        return {}
    people = people if people is not None else PSP.load_people(with_votes=False)
    out = {}
    for emp, term in sorted(want):
        seat, _why, _row = PR.term_seat(emp, term, people, table)
        if seat:
            out[(emp, term)] = seat[0]
    return out


def sponsor_record_rows(sponsors):
    """[(term, row)]: each 1989-1998 row the General Court's sponsor record supplies itself
    that is linked to a member and carries its employee number, the rows
    sponsor_record_chambers looks up in the term's Manual."""
    import past_roster as PR
    if not P.term_keyed(sponsors or {}):
        return []
    return [(term, s) for term in PR.PRE_TERMS
            for rows in (sponsors.get(term) or {}).values() for s in rows or ()
            if s.get("source") == PSP.SOURCE and s.get("employee") and s.get("member_id")]


def sponsor_record_said(sponsors, record_chambers):
    """What the build says of sponsor_record_chambers' answer, so that it never falls back in
    silence (the review before the release of 16 November 2026): how many it seated; that no
    seat list was read, where the record has rows to seat and none was; and how many rows the
    Manual seats in another chamber than the row's own, which their bill pages still name
    (bill_sponsor_list labels a row of the record by its own chamber; only `ch` takes the
    Manual's)."""
    rows = sponsor_record_rows(sponsors)
    out = []
    if record_chambers:
        out.append(f"  sponsors: {len(record_chambers):,} member-terms of 1989-1998 from the "
                   "General Court's sponsor record seated by that term's Manual, for the On "
                   "Record line")
    elif rows:
        out.append("  sponsors: no Manual seat list read; every 1989-1998 row of the General "
                   "Court's sponsor record keeps its own chamber")
    moved = sum(1 for term, s in rows
                if (record_chambers or {}).get((str(s["employee"]), term))
                not in (None, (s.get("chamber") or "")[:1]))
    if moved:
        out.append(f"  sponsors: {moved:,} 1989-1998 row(s) of the General Court's sponsor record "
                   "seated by the term's Manual in another chamber than the row's own; their "
                   "bill pages still name the row's own chamber")
    return out


def _manual_name_keys(name):
    """The surname keys past_roster._table_name_fits tests a seat list's full name by: its last
    word, and its last two run together where it has three or more (suffixes left out)."""
    w = [x for x in re.split(r"[\s,]+", name or "") if x and TS.letters(x) not in TS.SUFFIXES]
    if len(w) < 2:
        return set()
    return {TS.letters(w[-1])} | ({TS.letters(w[-2] + w[-1])} if len(w) > 2 else set())


def manual_seats(pages, links=None, sponsored=None, votes_by_member=None, table="auto",
                 people=None, counties=None):
    """THE TERMS OF 1989-1998 THE MANUAL FOR THE GENERAL COURT SEATS A MEMBER IN, whether or not
    they have a bill that term (the owner, 14 November 2026: "If we can address the manual gaps
    now, I'd rather just do it"). Francis Vincent's line read "House, 1989–1992, 1995–2000",
    and the 1993 Manual seats Francis C. Vincent at Strafford 14: his bills skip a term his
    seat does not.

    Returns ({page id: {chamber: [term]}}, [(page id, term, kind, words)]): for each member
    page, the terms the Manual seats them in that their 1989-1998 bills (`sponsored`, with the
    `ch` bill_sponsor_list gives) do not show, each in the Manual's chamber; and every seat
    left out, and why. The terms from 1999 on are the roll calls' and are not touched.

    A SEAT COUNTS where past_roster.term_seat -- the call sponsor_record_chambers makes --
    seats one of the member's own General Court numbers without doubt: one person of that full
    name in the term's list, its row read cleanly. A member's numbers are the employee numbers
    whose site id (the PersonID the legislators table gives a number, else the number) is the
    page's own or one joined to it (`links`).

    AND NEVER, AS FAR AS THE RECORD CAN TELL, ANOTHER PERSON'S. Left out, and said:
      - "doubtful": term_seat's own doubt (two people of that full name in the term's list, a
        row not read cleanly), or the member's numbers seated at two seats, or doubted, in the
        same term;
      - "perhaps another person": another number of the General Court's list has the same full
        name; the Manual's House seat is in a county the member's own record does not name; its
        chamber is one the member's record has nowhere (their numbers, their votes, their bills,
        their page); or their bills of that term print the other chamber.
    A term their bills of the same chamber already show adds nothing. `table`, `people` and
    `counties` ({number: county}) stand in for generated/manual_seats.json and the files
    past_sponsors.load_people and past_members.roster read."""
    import past_roster as PR
    import past_members as PM
    table = PR.seat_table() if table == "auto" else table
    if not pages:
        return {}, []
    if not table:
        return {}, [(None, None, "unread", "no Manual seat list read")]
    people = people if people is not None else PSP.load_people(with_votes=False)
    if counties is None:
        counties = {e: r.get("county") or "" for e, r in PM.roster(PSP.PAST_MEMBERS).items()}
    abbr = lambda c: ST.COUNTY_ABBR.get(c or "", c or "")
    by_site, by_key = defaultdict(set), defaultdict(set)
    for e in people.pm:
        by_site[str(people.vid(e))].add(e)
        for k in people.surnames(e):
            by_key[k].add(e)
    term_keys = {t: {k for _c, r in PR._manual_rows(table, t) for k in _manual_name_keys(r.get("name"))}
                 for t in PR.PRE_TERMS}
    seat_words = lambda s: (f"Senate district {s[2]}" if s[0] == "S"
                            else f"House {s[1].title()} {s[2]}")
    out, left = {}, []
    for pid, m in pages.items():
        ids = [str(pid), *(str(x) for x in (links or {}).get(pid, []))]
        nums = set().union(*(by_site.get(i, set()) for i in ids))
        if not nums:
            continue
        bills = ML.earlier_terms((sponsored or {}).get(pid, []))
        bill_ch = defaultdict(set)
        for ch, ts in bills.items():
            for t in ts:
                bill_ch[t].add(ch)
        known_ch = ({str(m.get("chamber") or "")[:1]} | {people.pm[e][0] for e in nums} | set(bills)
                    | {v.get("body") for i in ids for v in (votes_by_member or {}).get(i, ())})
        known_co = {abbr(m.get("county")), m.get("county_abbr") or ""} | {abbr(counties.get(e))
                                                                          for e in nums}
        known_co.discard("")
        for term in PR.PRE_TERMS:
            seats, doubts = {}, []
            for e in sorted(nums):
                if not people.surnames(e) & term_keys[term]:
                    continue
                seat, why, row = PR.term_seat(e, term, people, table)
                if seat:
                    seats[e] = (seat, row)
                elif not why.startswith("no person"):
                    doubts.append(f"{why} (number {e})")
            if not seats:
                left += [(pid, term, "doubtful", d) for d in doubts]
                continue
            if doubts or len({s for s, _r in seats.values()}) > 1:
                left.append((pid, term, "doubtful", "; ".join(
                    doubts + [f"number {e} at {seat_words(s)}" for e, (s, _r) in sorted(seats.items())])))
                continue
            e, (seat, row) = sorted(seats.items())[0]
            ch, at = seat[0], seat_words(seat)
            others = sorted(x for k in _manual_name_keys(row.get("name")) for x in by_key.get(k, ())
                            if x not in nums and PR._table_name_fits(row.get("name"), x, people))
            why = ""
            if others:
                why = (f"number {others[0]} of the General Court's list has the full name "
                       f"{row.get('name')!r} too")
            elif ch == "H" and known_co and abbr(row.get("county")) not in known_co:
                why = (f"{at} is in a county the member's record does not name "
                       f"({', '.join(sorted(known_co))})")
            elif ch not in known_ch:
                why = f"the member's record has no {'Senate' if ch == 'S' else 'House'} anywhere"
            elif bill_ch.get(term) and ch not in bill_ch[term]:
                why = f"their bills of {term} print the other chamber"
            if why:
                left.append((pid, term, "perhaps another person", f"{row.get('name')} at {at}: {why}"))
            elif not bill_ch.get(term):
                out.setdefault(pid, {}).setdefault(ch, []).append(term)
    return {k: {ch: sorted(ts) for ch, ts in sorted(v.items())} for k, v in out.items()}, left


def manual_said(manual, left):
    """What the build says of manual_seats' answer: how many pages gain how many terms, and how
    many seats were left out, by why; or that no seat list was read -- never in silence."""
    if any(k == "unread" for _p, _t, k, _w in left):
        return ["  members: no Manual seat list read; the 1989-1998 terms on record are their "
                "bills' alone"]
    n = sum(len(ts) for v in manual.values() for ts in v.values())
    kinds = Counter(k for _p, _t, k, _w in left)
    return [f"  members: {len(manual):,} page(s) take {n:,} term(s) of 1989-1998 their Manual "
            "for the General Court seats them in, with no bill that term"
            + (f"; left out: {', '.join(f'{v:,} {k}' for k, v in sorted(kinds.items()))}"
               if kinds else "")]


# ------------------------------------------------------- the party of a 1989-1998 sponsor

# The party letters the Manual for the General Court's returns print for a candidate of one
# party (build_manual_seats.PARTY). A line of two or three ("d&r", "r&d&l") is a candidate
# more than one party nominated, and names no one party. Read by the state's one table of
# parties, whole: "d&r" is no form of it.
MANUAL_PARTY = ST.party_lookup()


def party_letter(party):
    """The letter a chip and a label draw for `party` -- "R" for "R", "r" or "Republican" -- as
    member_labels draws it: the first letter, where it is one of PARTY_INITIALS; else ""."""
    pc = (party or "").strip()[:1].upper()
    return pc if pc in PARTY_INITIALS else ""


# What the records give as a person's party, for early_party -- party_ids keys it by the ids
# the records use, party_record by the page each id reaches: `person`, {id: {party letter}},
# every party any record of them gives; `term`, {(id, term): {party letter}}, the party each
# 1989-1998 term's Manual for the General Court prints beside their name, where the line names
# one party (manual_parties).
Parties = namedtuple("Parties", "person term")


def early_party(page, record, term=""):
    """THE PARTY ON THE CHIP OF A 1989-1998 SPONSOR PLACED ON A PERSON WITH A PAGE.

    THE OWNER'S DECISIONS, both of 15 November 2026:
      - show on their 1989-1998 chips the party the person's own page gives, and leave it off
        for anyone the record shows in more than one party;
      - and, for a person the record shows in more than one party, a bill of 1989-1998 shows
        the party that bill's term's Manual for the General Court gives them (the general
        election's returns), where it settles the term with a single letter. A
        cross-nomination ("d&r") settles nothing, and a term the Manual does not seat them in
        gives nothing: no party for that term.
    No roll call of 1989-1998 is on this site, so no sponsor row of those years carries a party
    of its own -- the bill's own sponsor rows place the printed name (past_roster.py), or the
    General Court's sponsor record supplies the list (past_sponsors.filled) -- and Rep. Donna
    Sytek, R on her page, was drawn with no party on the 34 bills of 1993-1994 she is prime
    sponsor of. The page's party is today's. It is said of 1993 only where nothing the site holds
    of the person says otherwise; where something does, only the term's own Manual speaks for
    that term.

    `page` is the member record the row is placed on (bill_sponsor_list's `_m`), `term` the
    bill's term. `record` is party_record's Parties: in `person`, the parties of the labels and
    chips of their bills of 1999-2026, their ballots, the legislators table's party
    (generated/careers.json) and every term's Manual; in `term`, each term's Manual on its own
    (manual_parties). Measured on the live site and these files on 15 November 2026: 343 of the
    353 people with a page on 1989-1998 bills give one party, and their Manual lines agree with
    it by construction; Michael Downing's own bills give two (D in 1999-2000, R from 2007), and
    nine more give two only by a Manual -- Steve Vaillancourt, R on his page, is a Democrat in
    the 1997 Manual's returns, and so his 1997-1998 bills read D.

    Returns a party letter, or "": where the row is placed on no page (the people who served
    only before 1999 have none, and keep no party and no link), where the page gives no party
    and no record another, where the record shows two parties and the term's Manual names none
    of its own, and where no record was read at all (`record` None), since then nothing can say
    the person was of one party. The seat is never this function's: it stays the one the bill
    printed."""
    if record is None or not (page or {}).get("id"):
        return ""
    pid = str(page["id"])
    own = party_letter(page.get("party_code") or page.get("party"))
    if len({own, *record.person.get(pid, ())} - {""}) <= 1:
        return own
    got = record.term.get((pid, term)) or set()
    return min(got) if len(got) == 1 else ""


def manual_parties(table="auto", people=None):
    """{site id: {term: {party letter}}}: the party the general election's returns print, in the
    Manual for the General Court of each 1989-1998 term (generated/manual_seats.json), for the
    one person of a number's full name the term's seat list holds -- the row
    past_roster.term_seat joins the number to -- for every number the General Court's list of
    members names, keyed by the id the number's ballots are cast under
    (past_sponsors.People.vid). For early_party, as the record of the person's party in that
    term; a term with two letters (two numbers of one person seated apart) settles none.

    A row term_seat calls unclean still counts: its doubt is about the seat (a mark, a district
    count), not the party printed beside the name. A line of two nominations ("d&r") names no one
    party and counts for nothing, and so does a term whose list holds nobody, or two people, of
    that full name. None where the seat list is not on this disk.

    Each number is held only to the rows its own surnames could fit (_manual_name_keys: a row
    _table_name_fits fits carries one of the number's surnames as one of its keys), which is
    term_seat's answer over the whole list at a fraction of its cost -- 16 ms a call over a
    term's 424 rows. `table` and `people` stand in for generated/manual_seats.json and the files
    past_sponsors.load_people reads."""
    import past_roster as PR
    table = PR.seat_table() if table == "auto" else table
    if not table:
        return None
    people = people if people is not None else PSP.load_people(with_votes=False)
    near_rows = {}
    for term in PR.PRE_TERMS:
        k = defaultdict(dict)
        for ch, r in PR._manual_rows(table, term):
            for key in _manual_name_keys(r.get("name")):
                k[key][id(r)] = (ch, r)
        near_rows[term] = k
    out = defaultdict(lambda: defaultdict(set))
    for e in sorted(people.pm):
        keys = people.surnames(e)
        for term in PR.PRE_TERMS:
            near = {}
            for key in keys:
                near.update(near_rows[term].get(key) or {})
            if not near:
                continue
            one = {"terms": {term: {"house": [r for ch, r in near.values() if ch == "H"],
                                    "senate": [r for ch, r in near.values() if ch == "S"]}}}
            _seat, _why, row = PR.term_seat(e, term, people, one)
            p = MANUAL_PARTY.get(str((row or {}).get("party") or "").strip().lower(), "")
            if p:
                out[str(people.vid(e))][term].add(p)
    return {i: dict(ts) for i, ts in out.items()}


def party_ids(votes_by_member=None, careers=None, manual=None):
    """Parties keyed by the ids the records use, for party_record. `person`: the party of every
    ballot cast under an id (votes_by_member), the legislators table's party for each id
    generated/careers.json joins to a person (their PersonID and each of their employee
    numbers), and every party manual_parties' answer (`manual`) gives the id in any term.
    `term`: that answer, term by term."""
    out, by_term = defaultdict(set), {}
    for mid, vs in (votes_by_member or {}).items():
        got = {party_letter(p) for p in {v.get("party") for v in vs}} - {""}
        if got:
            out[str(mid)] |= got
    for key, c in (careers or {}).items():
        p = party_letter((c or {}).get("party"))
        if p:
            for i in {str(key), str(c.get("person_id") or ""), *map(str, c.get("employee_nos") or ())}:
                if i:
                    out[i].add(p)
    for i, terms in (manual or {}).items():
        for t, ps in terms.items():
            out[str(i)] |= set(ps)
            by_term[(str(i), t)] = set(ps)
    return Parties(dict(out), by_term)


def party_record(people, labelled=None, ids=None):
    """Parties keyed by page id, for early_party: each party a record of the person gives, and
    the Manual's term by term. The labels and chips of their bills of 1999-2026 (`labelled`,
    keyed by page id already, as bill_sponsor_list draws them), and party_ids' answer (`ids`),
    each id joined to the page it reaches through `people` -- build_bills' `_people`, the lookup
    that places a sponsor row on a page, so a record of an earlier number reaches the page that
    number's bills link to, and two numbers of one person seated apart in a term give that term
    two letters."""
    out, by_term = defaultdict(set), defaultdict(set)
    ids = ids or Parties({}, {})
    for pid, ps in (labelled or {}).items():
        out[str(pid)] |= set(ps) - {""}
    for i, ps in ids.person.items():
        page = people.get(str(i)) or {}
        if page.get("id"):
            out[str(page["id"])] |= set(ps) - {""}
    for (i, t), ps in ids.term.items():
        page = people.get(str(i)) or {}
        if page.get("id"):
            by_term[(str(page["id"]), t)] |= set(ps) - {""}
    return Parties(dict(out), dict(by_term))


def early_party_said(sponsored, people, record):
    """What the build says of early_party's answer, so it never falls back in silence: how many
    people with a page take its party on how many of their 1989-1998 bills; and each the record
    shows in more than one party, with the parties and, term by term, the Manual's party their
    bills of that term take (early_party), or none, and on how many. [] where no 1989-1998 bill
    is filed under a page, or no record was read."""
    took, bills_, two = 0, 0, []
    for pid in sorted(sponsored or {}):
        terms = Counter(str(x.get("term") or "") for x in sponsored[pid]
                        if str(x.get("term") or "")[:4] < "1999")
        page = (people or {}).get(str(pid)) or {}
        if record is None or not terms or not page.get("id"):
            continue
        own = party_letter(page.get("party_code") or page.get("party"))
        seen = sorted({own, *record.person.get(str(page["id"]), ())} - {""})
        if len(seen) <= 1:
            if own:
                took, bills_ = took + 1, bills_ + sum(terms.values())
            continue
        two.append((page.get("name") or pid, seen,
                    [(t, early_party(page, record, t), n) for t, n in sorted(terms.items())]))
    if not (took or two):
        return []
    out = [f"  sponsors: {took:,} people with a page take its party on {bills_:,} of their "
           "1989-1998 bills (early_party)"]
    if two:
        given = sum(n for _w, _s, ts in two for _t, p, n in ts if p)
        none = sum(n for _w, _s, ts in two for _t, p, n in ts if not p)
        out.append(f"  sponsors: {len(two):,} the record shows in more than one party take the party "
                   f"their bill's term's Manual gives on {given:,} bills and none on {none:,}: "
                   + "; ".join(f"{w} ({', '.join(s)}): "
                               + ", ".join(f"{t} {p or 'none'} on {n:,}" for t, p, n in ts)
                               for w, s, ts in two))
    return out


def bill_sponsor_list(bid, b, year, term, current, sponsors, legs,
                      leg_by_sort, leg_by_name, sponsored, seats=None, left=None,
                      term_roster=None, record_chambers=None, labelled=None,
                      parties=None):
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

    `record_chambers` is sponsor_record_chambers': the chamber the term's
    Manual seats a 1989-1998 sponsor of the General Court's record in.

    `parties` is party_record's Parties, from which a 1989-1998 row placed
    on a page takes that page's party, or the bill's term's Manual's for a
    person of two parties (early_party); None gives it none. `labelled`,
    where given, is filled with the party letters this list's labels and
    chips draw for each page on a bill of 1999 on -- build_bills reads those
    first, for `parties`.

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
        # day. Neither takes a seat from the roster: a 1993 bill's sponsor
        # who sits in the Senate today was drawn "Sen." at today's district.
        # One with no party on that term's ballots is given none -- save a
        # 1989-1998 row placed on a page, below.
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
        # ... AND A 1989-1998 SPONSOR PLACED BY THE BILL'S OWN SPONSOR ROWS
        # (past_roster.py), or supplied by the record itself: the seat is the
        # one the bill printed, and the party the person's own page gives,
        # where every record of them gives that one party; where a record
        # gives another, the party the bill's term's Manual gives them, where
        # it names one; and none where it does not, or there is no page
        # (early_party: the owner's decisions, 15 November 2026). The row has
        # none of its own; the page's is said of 1993 only where nothing the
        # site holds says otherwise.
        _gave = ""
        if (_s.get("seat_source") in (PSP.SOURCE, JOURNAL_SOURCE)
                or _s.get("matched") == PAST_ROSTER_MATCH):
            if not _s.get("party") and term[:4] < "1999":
                _gave = early_party(_m, parties, term)
            _party = _s.get("party") or _gave
            _lab = member_labels(
                _s.get("name"),
                chamber=_s.get("chamber") or _m.get("chamber"),
                party=_party,
                district=_s.get("district"), county=_s.get("county"))
        elif _s.get("source") == TS.SOURCE or _s.get("seat_source") == TS.SOURCE:
            _party = _s.get("party") or _t.get("party_code")
            _lab = member_labels(
                _s.get("name"),
                chamber=_s.get("chamber") or _t.get("chamber"),
                party=_party,
                district=_s.get("district") or _t.get("district"),
                county=_s.get("county") or _t.get("county"),
                county_abbr=None if _s.get("district") else _t.get("county_abbr"))
        elif ((_s.get("chamber") or "")[:1].upper() in ("H", "S")
              and (_t.get("chamber") or "")[:1].upper() in ("H", "S")
              and (_s.get("chamber") or "")[:1].upper() != (_t.get("chamber") or "")[:1].upper()
              and _s.get("district")):
            # THE SEAT THE RECORD PRINTS, WHERE THE MEMBER HAS SINCE MOVED
            # CHAMBER (9 November 2026): a bill filed as Rep. for Grafton 1 reads
            # so, linked to the page the member has now as a senator.
            _party = _s.get("party") or _t.get("party_code")
            _lab = member_labels(
                _s.get("name"),
                chamber=_s.get("chamber"),
                party=_party,
                district=_s.get("district"), county=_s.get("county"))
        else:
            _party = _t.get("party_code") or _s.get("party")
            _lab = member_labels(
                _s.get("name"),
                chamber=_t.get("chamber") or _s.get("chamber"),
                party=_party,
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
        # The party given (early_party) is the row's too, so that the chip on
        # the bill's Sponsors tab, the card's (the index row's sponsor_party)
        # and the bill search's party filter read the party the label does.
        sp_list.append({**_s, **_lab, "slug": _slug, **({"party": _gave} if _gave else {})})
        # WHAT A PAGE'S BILLS OF 1999 ON DRAW THEM WITH, for early_party: the
        # label's party and the row's own, which the chip and the card read.
        if labelled is not None and _m.get("id") and term[:4] >= "1999":
            labelled.setdefault(str(_m["id"]), set()).update(
                {party_letter(_party), party_letter(_s.get("party"))} - {""})
        # FILED UNDER THE MEMBER THE PAGE LINKS. This used the record's own id,
        # and every 2023-2024 record, with 4,569 of 2025-2026's, carries an
        # employee number or none: 349 of 406 members' Sponsored tabs missed
        # 11,855 bills their bill pages credited them with. A record matched to
        # nobody keeps its own id, as before; one member twice on a bill is
        # filed once.
        _mid = str(_m.get("id") or _s.get("member_id") or "")
        if _mid and _mid not in filed:
            filed.add(_mid)
            # THE CHAMBER OF A 1989-1998 TERM THE GENERAL COURT'S SPONSOR RECORD PUTS THIS
            # PERSON IN, for their "On Record" line (ML.earlier_terms), on every such row: the
            # line covers the terms the TERM picker lists, and the picker lists them all. Only
            # the printed rows had one, and Donna Sytek, Speaker in 1997-1998, whose bills of
            # that term are all the record's own rows, read "House, 1989–1996, 1999–2000" (the
            # review before the release of 16 November 2026). A sponsor the bill printed and
            # its sponsor rows placed (past_roster.py) takes the chamber the bill printed; a
            # row the record supplies itself (past_sponsors.filled), the chamber the term's
            # Manual seats them in (sponsor_record_chambers), else the row's own.
            # build_legislators takes it out again.
            if _s.get("matched") == PAST_ROSTER_MATCH:
                _ch = (_s.get("chamber") or "")[:1]
            elif _s.get("source") == PSP.SOURCE and term[:4] < "1999":
                _ch = ((record_chambers or {}).get((str(_s.get("employee") or ""), term))
                       or (_s.get("chamber") or "")[:1])
            else:
                _ch = ""
            sponsored[_mid].append({
                "bill": bid, "n": b.get("designation") or bid,
                "title": b.get("title", ""), "year": year, "term": term,
                "prime": bool(_s.get("prime")),
                **({"ch": _ch} if _ch else {})})
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


# The chapters and sections a bill's text changes (statute_changes) and the topic
# vocabulary that reads them (vocabulary_of) are src/parse/topic_vocabulary.py's,
# named here as they were.
from topic_vocabulary import (TOPIC_WORDS, _CHANGES, statute_chapters, statute_changes,
                              vocabulary_of)


_ENACTED = []


def statutes_enacted(term, bid):
    """The statute sections the source notes say this bill wrote, as the law
    it became (RSA_PAGE.md §7, "Changed these statutes"), in statute order:
    the other way round from a section's history, so the two pages link both
    ways. [] where rsa_citations.json is not on this disk or the bill became
    no law a note names."""
    if not _ENACTED:
        inv = defaultdict(list)
        p = Path("rsa_citations.json")
        try:
            data = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
        except (OSError, ValueError):
            data = {}
        for addr, rows in (data.get("enacted") or {}).items():
            for _y, _law, b in rows:
                if b and addr not in inv[b]:
                    inv[b].append(addr)
        _ENACTED.append(inv)
    got = list(_ENACTED[0].get(f"{term}/{bid}", []))

    def key(a):
        ch, _, sec = a.partition(":")
        m = re.match(r"(\d+)(?:-([A-Z]+))?$", ch)
        n = re.match(r"(\d+)(?:\.(\d+))?(?:-(.*))?$", sec)
        return ((int(m.group(1)), m.group(2) or "") if m else (99999, ch),
                (int(n.group(1)), int(n.group(2) or 0), n.group(3) or "") if n else (99999, 0, sec))
    return sorted(got, key=key)


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
        # THE SPONSOR AS THE PERSON CHIP ON A CARD (D14, the person, 8 October
        # 2026: the chip wherever a person is listed or labelled, with the seat
        # held at the time): the label in full, "Rep. George Grant (R - Sull
        # 5)", where it was "(R)", and the page and party the chip needs, only
        # where the record has them, so the up-front index grows by little.
        "sponsor_label": (prime.get("display_full") or prime.get("display", "")) if prime else "",
        **({"sponsor_slug": prime["slug"]} if prime and prime.get("slug") else {}),
        **({"sponsor_party": str(prime.get("party") or "").strip().upper()[:1]}
           if prime and prime.get("party") else {}),
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
                           disp.status, bid, passed, acted, over=not live),
        "last_action": dates[-1] if dates else "",
        # Only on a bill that became one, so the 21,864 that did not cost
        # the up-front index nothing. bills.csv reads it from here, which
        # keeps the download and the page from disagreeing.
        **({"chapter": chapter} if chapter else {}),
        "nrc": len([r for r in rcs if not r.get("procedural")]),
        "votedays": sorted({r["date"] for r in rcs if r.get("date")}),
        # Only where the bill changes a statute, so the index grows by what
        # the RSA filter needs and nothing on a night without the file.
        **({"rsa": ch} if (ch := statute_changes(term, bid)) else {}),
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


def study_report(narr, term=""):
    """What the committee said about a bill it took for interim study, or None.

    The docket prints one line per report -- "Interim Study Report: Not Recommended
    for Future Legislation 09/02/2026 (Vote 18-0; )" -- and it is the end of that
    bill's story: the committee either asks for the subject to come back as a new
    bill next term or it does not. 10 are on file for 2025-2026 so far and the rest
    arrive through the autumn; 129 in 2023-2024, 134 in 2021-2022. The bill's page
    said nothing about it, which left "Referred for interim study" as the last word
    on bills whose committee had since reported.

    IN EVERY WORDING THE DOCKET HAS USED (interim_report), since the review of
    interim study of 8 October 2026: this read "(Not) Recommended for Future
    Legislation" alone, 751 of the 1,534 reports in nineteen terms, so the note
    said nothing of 1989-2006's, 2011-2012's ("Not Recommended for Legislation
    in 2013") or the 17 of 2024 "Without Recomendation". The note under the
    panel and the report's line of How it got here (study_ending) are one
    reading.
    """
    return interim_report(narr, term)


# WHAT THE TWO CHAMBERS DID WITH EACH OTHER'S VERSION is conferences.py's (20
# November 2026): a concurrence, a committee of conference and how it ended,
# from the docket, which the journey (journey.py) reads too. Each name is here
# as before.
from conferences import (BEFORE_CONCURRENCE, BEFORE_CONFERENCE, BEFORE_UNABLE,  # noqa: E402,F401
                         CHAMBERS_APART, CONF_FAILED, CONF_LATE_RE, CONF_REJECTED,
                         CONF_REPORT, CONF_UNABLE, CONF_UNABLE_RE, CONF_UNSIGNED_RE,
                         CONFERENCE_ROW, ENDED_AS, FAILURE_RANK, NEW_CONF, NEXT_MOTION,
                         _conference_vote, _failure_how, between_chambers,
                         concurrence_outcome, conferees_disagreed, conference_failure,
                         conference_outcome)


# A resolution the second chamber adopted says so in the docket even where its
# status field does not: HCR 6 of 1990, "S INTRODUCED AND ADOPTED" the day the
# House adopted it, and SCR 3 of 1996, "H ADOPTED DIV(178-116)".
SECOND_ADOPTED = re.compile(r"^\s*(?:introduced and )?adopted\b", re.I)

# A CACR's referendum as the docket records it (REFERENDUM) is parts.py's, for
# the same reason.
from parts import REFERENDUM  # noqa: E402,F401
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
BALLOTS = "corrections/ballot_results.json"
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


# THE 2020 SENATE'S DEATHS BY ITS RULE 3-23 (TABLE_DEATH) are parts.py's, for the
# reason the others are: the status reads them too.
from parts import TABLE_DEATH  # noqa: E402,F401
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
ENDED_WITH_TERM = "the term's end"


# Whether a chamber would not take a conference's report up
# (conference_not_taken_up, and CONF_NOT_TAKEN_UP, one of the tests above) is
# conferences.py's: the status reads it too.
from conferences import CONF_NOT_TAKEN_UP, conference_not_taken_up  # noqa: E402,F401


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
    # The word is left as the record gives it, because it is what the record
    # last said -- except the stages a bill dies at, which say how it died
    # (ENDED_AS, below, since 17 October 2026). What
    # changes is the KIND, which drives the colour and the rail: in a
    # closed term the bill did not go on from there, so it is finished
    # rather than moving. The current term is untouched -- a bill laid on
    # the table in 2026 may yet be taken up -- UNTIL THE TERM RUNS OUT OF
    # SESSION DAYS, which corrections/status/status.txt states as session_over: with no
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
    # HOW IT ENDED, IN THE WORDS OF AN ENDING (17 October 2026). Where the
    # record's last word is a stage -- on the table, or the chambers apart --
    # and the term has no session days left, that stage is how the bill died,
    # and the status says so beside the Died chip rather than reading as
    # though something were still to come: "Laid on the table" on 52 bills of
    # 2026 where 197 others already said "Died on the table", and "a committee
    # of conference was asked for" on HB 191 of 2026, whose conference the
    # Senate refused. ENDED_AS has the words.
    if (term != current or term_over) and kind in ("active", "done"):
        status = ENDED_AS.get(status, status)
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
    # THE LABEL SAYS WHAT IT IS FIRST, AND THE YEAR IN BRACKETS (the cohesion
    # audit's P-12, 6 November 2026): "House Calendar 12, 2026, committee
    # report" read as a date, December 2026. The citation is the General
    # Court's own and is not changed where it is shown as one, on the Reports
    # tab; only this list's label is.
    def report_label(cite):
        return "Committee report, " + re.sub(r",\s*((?:19|20)\d\d)\s*$", r" (\1)", cite or "")
    for r in rep_written:
        add_doc(report_label(r.get('source') or r.get('cite')),
                r.get("cite_url", ""), "report")
    for r in rep_docket:
        if r.get("cite_url"):
            add_doc(report_label(r['cite']), r["cite_url"], "report")
    return docs, text_url


def _long_day(iso):
    """"2025-02-06" -> "February 6, 2025", as the narratives write a day:
    shell.date_words."""
    return _shell.date_words(str(iso or ""), "full")


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
        {"label": "House Committee" + (f" ({committee})" if committee else ""),
         "hand": "H:committee", "notes": [],
         "text": (f"It was introduced on {_long_day(i.get('date'))}"
                  + (f" and referred to the House {committee} committee." if committee
                     else "."))},
        {"label": "On the House Floor", "hand": "H:floor", "notes": [], "text": said},
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
        {"label": "House Committee" + (f" ({committee})" if committee else ""),
         "hand": "H:committee", "notes": [],
         "text": (f"It was introduced on {_long_day(i.get('date'))}"
                  + (f" and referred to the House {committee} committee." if committee
                     else "."))},
        {"label": "On the House Floor", "hand": "H:floor", "notes": [], "text": said},
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

    In docket order, sharing one `claimed` between the sittings, so a marker
    that names no proceeding goes to one of them and not to all
    (station_for_proceeding, 17 October 2026).
    """
    claimed = set()
    return [station_for_proceeding(p, bid, segs, marks, claimed)
            for p in sorted(procs.get((term, bid), []),
                            key=lambda x: (x["sched_date"],
                                           x["sched_time"] or ""))]


def bill_rollcalls(bid, term, rcs, narr, votes_by_bill, legs, unnamed,
                   in_office=None):
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
            # The roll call's own name, "2026-H-95", taken off before the
            # record is written (build_bills): a session day names the card.
            "_rc": key,
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
    #
    # AND A DIVISION ON AN AMENDMENT, AND A VOTE ON A CONFERENCE REPORT (the
    # launch audit of 7 October 2026, cause 16). "Amendment # 2025-2406h: AF
    # DV 153-185" (SB 222 of 2025) and "FLAM # 2026-1971h(NT) ...: AA DV" are
    # counted votes of the floor, and the tab took floor motions alone, so 105
    # divisions on amendments of 2025-2026 had no card; nor did a chamber's
    # voice or division vote on a conference report, which narrative.py now
    # reads ("conf_report"). Asked in the roll call file's own words for the
    # same questions, "Adopt Floor Amendment", "Adopt Committee Amendment",
    # "Adopt Amendment", "Adopt Conference Committee Report", with the
    # number beside it. An amendment's voice vote is not drawn: 1,508 of
    # 2025-2026, most a committee's amendment adopted without a word; nor a
    # vote on part of one, whose question is not the amendment's.
    VK = {"VV": ("voice vote", False), "DV": ("division vote", False)}
    for _i, e in enumerate((narr or {}).get("events", [])):
        if e.get("cancelled"):
            continue
        vk = "DV" if (e.get("vote_kind") or "").upper() in ("DV", "DIV") else e.get("vote_kind")
        number = None
        if e.get("type") == "amendment":
            said = _amendment_said(e)
            if (vk != "DV" or not (e.get("yeas") and e.get("nays")) or said is None
                    or e.get("part") == "some"):
                continue
            k = (e.get("amend_kind") or "").lower()
            question = ("Adopt Floor Amendment" if "floor" in k
                        else "Adopt Committee Amendment" if "committee" in k
                        else "Adopt Amendment")
            passed, number = said, (e.get("amendment") or "").strip() or None
        elif e.get("type") == "conf_report":
            question = "Adopt Conference Committee Report"
            passed, number = e.get("motion") == "MA", (e.get("amendment") or "").strip() or None
        elif e.get("type") == "floor":
            question = e.get("action") or "Floor action"
            passed = e.get("motion") in ("MA", "AA")
        else:
            continue
        kind = VK.get(vk)
        if not kind:
            continue          # RC is already covered by the roll call file
        label, _ = kind
        y, n = e.get("yeas"), e.get("nays")
        # WHAT A DIVISION NEEDED, BY THE ROLL CALL'S RULE (17 October 2026).
        # These cards carried no threshold, so the chart marked a majority of
        # those voting on every one: "171 needed" beside the House's 325-15
        # on CACR 13, which needed three fifths of the 394 members in office,
        # 237. 185 counted divisions of 1989-2026 needed more than a majority
        # by their docket line, their question or the Journal
        # (rollcall_outcomes.division_threshold); fifteen of them of a count
        # not on record, which the chart leaves unmarked rather than marked
        # wrong.
        # And a CACR's division whose docket line names no fraction is read
        # with the House Journal's sentence for it (rollcall_outcomes.
        # journal_division_words): 2000's CACR 2, taken from the table "by
        # the necessary three-fifths", 17 October 2026.
        need = (RO.division_threshold(
                    bid, question, e.get("raw") or "", int(y), int(n),
                    (in_office or {}).get((e.get("body"), e["date"])), passed,
                    RO.journal_division_words(".", e.get("body"), e["date"], int(y), int(n))
                    if bid.upper().startswith("CACR") else "")
                if y and n else {})
        rc_out.append({
            "date": e["date"], "body": e.get("body"),
            "question": question,
            # Who made the motion, split off the question by narrative.py so
            # the Senate's "Sen. Abbas Moved Laid on Table" reads as a motion
            # to lay on the table, moved by Abbas. Roll calls from the roll
            # call file never carry one; the page prints it only when present.
            "mover": e.get("mover") or "",
            "yeas": int(y) if y else None, "nays": int(n) if n else None,
            "passed": passed,
            "vote_kind": vk, "vote_kind_label": label,
            "threshold_note": None, "tally": {}, "members": [],
            # The amendment's or the report's number, beside the question.
            "amendment": number, "_ord": (e["date"], _i),
            **need,
        })
    # THE MOTIONS ON THE BILL'S OWN DEBATE (the owner, 23 October 2026):
    # moving the previous question, limiting debate, dividing the question --
    # by division or by voice, from the bill's docket rows narrative.py reads
    # as no floor action ("Sen. Sanborn moved to call the question, MA, VV")
    # and from the Journal where the docket gives none (HB 1601's previous
    # question, 255-78 on a division, 12 March 2014). vote_passage decides
    # which, once for this tab and the session day; each is drawn before the
    # bill's own rows of that day, where the motion was made.
    for e in VP.motion_events(term, bid, (narr or {}).get("events", []), rcs):
        label, _ = VK[e["vote_kind"]]
        rc_out.append({
            "date": e["date"], "body": e["body"], "question": e["action"],
            "mover": e.get("mover") or "", "yeas": e.get("yeas"), "nays": e.get("nays"),
            "passed": e["motion"] == "MA", "vote_kind": e["vote_kind"],
            # By the Journal's own words (the owner, 23 October 2026): carried
            # "without objection" is said so, and is no voice vote.
            "vote_kind_label": "adopted without objection" if e.get("wo") else label,
            **({"wo": True} if e.get("wo") else {}),
            **({"ruling": e["ruling"]} if e.get("ruling") else {}),
            "threshold_note": None, "tally": {}, "members": [], "amendment": None,
            "_ord": (e["date"], e["_at"] - 0.5),
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
            # A subject the site retires ("Regular Meeting") is no label: the
            # model's answer for the bill, if there is one, replaces it.
            if rec.get("subject") and not (
                    rec["subject"] in TM.RETIRED
                    and ((guessed.get(term) or {}).get(bid) or {}).get("subject")):
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


# A General Court topic name in a reader's words (TOPIC_WORDS), and the site category a
# record's topic ends up under (vocabulary_of), are topic_vocabulary.py's, imported
# beside statute_changes above: request_topics files a request by them too.


def unify_vocabulary(bills):
    """ONE VOCABULARY ACROSS ALL NINETEEN TERMS, applied last and to everything.

    The topic model predicts in the General Court's own 46 categories, which is
    the vocabulary it was measured in -- 62.1% to 67.2% held out. The site's
    own vocabulary is a different thing: five starved categories folded into
    parents, Regular Meeting retired, Housing and Study Committees added,
    two split in two (TM.SPLITS) and Cannabis drawn from the rest
    (TM.cannabis_topic). Applying it inside the model would have meant
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
            new_s = vocabulary_of(s, rec, bid, term)
            if new_s is None:
                rec["subject"], rec["subject_code"] = "", ""
                moved["retired"] += 1
                continue
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
CALLED_OFF_KINDS = ("hearing", "exec", "worksession", "conference_meeting", "other",
                    # A hearing on a proposed non-germane amendment, which
                    # narrative.py reads as a kind of its own (the launch
                    # audit of 7 October 2026, cause 15): "==CANCELLED==
                    # Public Hearing on non-germane Amendment # 2025-0707h"
                    # (HB 555 of 2025) is a meeting called off.
                    "nongermane_hearing")


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
    label = f"On the {'House' if body == 'H' else 'Senate'} Floor"
    told = []
    for s in stages:
        if s.get("hand") != "G:governor":
            told.append(s)
            continue
        text = ENROLLED_SAID.sub("", s.get("text") or "").strip()
        if text:
            told.append({**s, "text": text, "label": label, "hand": f"{body}:floor"})
    return told


# The docket line an event was read from (docket_line) is parts.py's, for the
# same reason.
from parts import docket_line  # noqa: E402,F401


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


# RELATED BILLS ON A BILL'S PAGE (RELATED_BILLS.md §6; related_bills.py).
# Added after the loop, because an entry names the other bill's number,
# title and status, and the loop has not reached every other bill when it
# writes this one. Only what related_bills.shown passes: a relation at the
# line, and an amendment only with a fate the docket records. Absent file,
# no tab: a night without the statute table skips the step, and that is the
# truth about that night.
RELATED_GROUPS = (("inside_law", "amendment"), ("language_across",), ("language_same",))
RELATED_MAX = 40


def related_entries(term, bid, rows, by_key):
    """[{g, o, n, t, y, c, s}] for one bill: the group (0 where its language
    went, 1 filed before or after, 2 this term's bills with the same text),
    the other bill's key, number, title, year and status, and the sentence
    with "{b}" where the other bill is named, which the page links."""
    import related_bills as RB
    me, out, seen = f"{term}/{bid}", [], set()
    for r in rows:
        o = r.get("other") or ""
        if not RB.shown(r) or o == me or o not in by_key:
            continue
        kind = r["kind"]
        if kind == "language":
            g = 2 if o[:9] == term else 1
        else:
            g = 0
        if kind != "amendment":
            if o in seen:
                continue
            seen.add(o)
        it = {"kind": kind, "a": me, "b": o, "share": r.get("share"), "mine": r.get("mine"),
              "theirs": r.get("theirs"), "order": r.get("order", ""), "amendment": r.get("amendment", ""),
              "direction": r.get("direction", ""), "fate": r.get("fate", ""),
              "fate_vote": r.get("fate_vote", ""), "fate_body": r.get("fate_body", "")}
        x = by_key[o]
        e = {"g": g, "o": o, "n": x.get("n") or o.split("/")[1], "t": x.get("title") or "",
             "y": x.get("year"), "c": x.get("chip") or "", "s": RB.sentence(it, lambda _k: "{b}"),
             "_share": float(r.get("share") or 0)}
        if kind == "amendment":
            # What the History tab needs to say an amendment in a second
            # sentence where the same bill is also listed for its text
            # (the owner's walk of dry run 8, 8 November 2026).
            e.update({"m": it["amendment"], "f": it["fate"], "fb": it["fate_body"], "fv": it["fate_vote"]})
        out.append(e)
    out.sort(key=lambda e: (e["g"], -e["_share"], e["o"]))
    for e in out:
        del e["_share"]
    return out[:RELATED_MAX]


def add_related(out, index, path=None):
    """Puts each bill's related entries into its own JSON. Returns how many
    bills have some."""
    p = Path(path or "related_bills.json")
    if not p.is_file():
        print("  related bills: no related_bills.json here; no related bills on any History tab")
        return 0
    data = json.loads(p.read_text(encoding="utf-8"))
    by_key = {f"{r.get('term')}/{r.get('id')}": r for r in index}
    n_bills = n_rows = 0
    for r in index:
        term, bid = r.get("term"), r.get("id")
        rows = (data.get(term) or {}).get(bid)
        if not rows:
            continue
        rel = related_entries(term, bid, rows, by_key)
        if not rel:
            continue
        f = out / "bills" / str(r.get("year")) / f"{bid}.json"
        if not f.is_file():
            continue
        rec = json.loads(f.read_text(encoding="utf-8"))
        rec["related"] = rel
        f.write_text(json.dumps(rec), encoding="utf-8")
        n_bills += 1
        n_rows += len(rel)
    print(f"  related bills: {n_rows:,} relations on {n_bills:,} bills' pages")
    return n_bills


def same_number_rows(notes, index):
    """{(term, bid): [{term, y, id, n, t, c}, ...]}: for a bill number corrections/
    bill_notes.json gives a standing meaning (HB 1 is the budget), the same
    number in each OTHER term the note is true of, newest first, each with its
    year, number, title and outcome chip. Only the terms the note holds for
    (bill_note's `from` and `until`): the HB 1 of 1989-1990 is another bill that
    shares the number. Bills the note does not name get nothing."""
    rows = {}
    for r in index:
        n = bill_note(notes, r.get("term"), r.get("id"))
        if n:
            rows.setdefault(r.get("id"), []).append(r)
    out = {}
    for bid, mine in rows.items():
        for r in mine:
            others = sorted((x for x in mine if x["term"] != r["term"]),
                            key=lambda x: x["term"], reverse=True)
            if others:
                out[(r["term"], bid)] = [
                    {"term": x["term"], "y": x.get("year"), "id": bid, "n": x.get("n") or bid,
                     "t": x.get("title") or "", "c": x.get("chip") or ""} for x in others]
    return out


def add_same_number(out, index, notes):
    """Puts each standing-note bill's same-number list into its own JSON, as
    `same_number`, for the History tab's "HB 1 in other terms". Returns how many
    bills have one."""
    by = same_number_rows(notes, index)
    n_bills = 0
    for r in index:
        rows = by.get((r.get("term"), r.get("id")))
        if not rows:
            continue
        f = out / "bills" / str(r.get("year")) / f"{r.get('id')}.json"
        if not f.is_file():
            continue
        rec = json.loads(f.read_text(encoding="utf-8"))
        rec["same_number"] = rows
        f.write_text(json.dumps(rec), encoding="utf-8")
        n_bills += 1
    print(f"  same number in other terms: {n_bills:,} bills' History tabs")
    return n_bills


def site_tagging(bills, bill_texts, registry=None):
    """The bills' tags, as build_bills and meta.json take them: {} where no
    registry is in force, else {"bills": {(term, bill): {id: why}}, "at":
    {id: its place in meta.json's list}, "names": {id: name}, "meta": the
    keys meta.json gains}.

    TOPICS AS TAGS, STAGES 3 AND 4 (reports/topics-as-tags-design-2026-11.md,
    sections 2.2, 5 and 6), SWITCHED OFF UNTIL THE OWNER APPROVES THE LIST.
    The registry is hers, corrections/tags.json (tag_rules.in_force), which
    she puts in force by copying a draft there. Without it this answers {},
    and the site is the site that was built before tags, byte for byte: no
    bill's record or index row and no key of meta.json changes, and
    build_pages publishes the scripts and app.css without their TAGS regions.
    With it, each bill is read by the engine as it stands (tag_rules), from
    its title, its text (the archived page's where that is all there is) and
    the topic it is filed under, after the site's vocabulary has named that.
    `registry` is the file to read in place of corrections/tags.json, for a
    check.
    """
    import tag_rules as TR
    doc = TR.in_force(registry)
    if not doc:
        return {}
    current = max(bills) if bills else ""
    rows = ((term, bid, rec.get("title") or "",
             ((P.per_term(bill_texts, term, current).get(bid) or {}).get("text") or ""),
             rec.get("subject") or "")
            for term, byb in bills.items() for bid, rec in byb.items())
    tagged = TR.site_tags(rows, doc)
    meta = TR.site_meta(doc, tagged, {r.get("subject") for byb in bills.values()
                                      for r in byb.values() if r.get("subject")})
    at = {t["id"]: i for i, t in enumerate(meta.get("tags") or [])}
    names = {t["id"]: t["name"] for t in meta.get("tags") or []}
    n_bills = sum(len(byb) for byb in bills.values())
    print(f"tags: {len(at)} of the registry's {len(doc['tags'])} on {len(tagged):,} of "
          f"{n_bills:,} bills (corrections/tags.json); {len((meta or {}).get('tag_words') or {}):,} "
          "words a reader may type lead to a tag or a topic")
    if not tagged:
        # SILENCE IS NOT SUCCESS: a registry in force that tags nothing
        # publishes a site with no tags, which looks like no registry at all.
        print("WARNING: corrections/tags.json is in force and no bill carries one of its tags: "
              "check its rules with python3 src/parse/tag_rules.py --bill TERM BILL")
    return {"bills": tagged, "at": at, "names": names, "meta": meta}


def build_bills(out, bills, narratives, rollcalls, reports, sponsors,
                bill_texts, amend_texts, testimony, testimony_db, procs, floor, segs,
                marks, sources, legs, leg_by_sort, leg_by_name,
                votes_by_bill, vetoes=None, notes=None, coverage=None,
                chapters=None, seats=None, session_over="", former=None,
                links=None, hearing_reports=None, ballots=None, term_rosters=None,
                rc_cards=None, moments=None, numbers=None, record_chambers=None,
                id_parties=None, tagging=None, voter_pools=None, people=None):
    """One JSON per bill, and the index row for each.

    This is the loop ARCHITECTURE item 5 names. It ran inside a 955-line
    main(), which is how `st` came to mean the bill's status record at the
    top and a video station 350 lines later -- costing 611 bills their
    facts, their bill-text link and, for 496, their status line.

    Every input is named in the signature rather than inherited from an
    enclosing scope, so a name can no longer be quietly reused.

    `id_parties` is party_ids' Parties: the parties a person's ballots,
    the legislators table and the Manual give, which a 1989-1998 sponsor
    placed on their page is held to with the labels of their bills of 1999
    on, and the Manual's term by term, which speaks for a term where they
    disagree (early_party). None gives no 1989-1998 sponsor a party, as
    before 15 November 2026: main passes None where the Manual's seat list
    is not on this disk.

    `tagging` is site_tagging's answer: each tagged bill's row gains "tags"
    and its record "tags", and nothing changes where it is empty or None.

    `voter_pools` is term_voters': each term's members as their ballots
    give them, with the seat of the term, among whom a roll call's mover of a
    term before the current one is looked for (mover_pool). None links none.
    NOT `voters`: the loop below binds that name to a CACR's ballot card on
    every bill, and the parameter of that name, read after it, was None on
    every bill but a CACR's -- the dry run of 20 November 2026 linked no mover
    of 1999-2024 at all.

    `people`, where given, is filled as `sponsored` is: {term: {key: member}},
    everyone each term's index rows name as a sponsor (sponsor_roster), for
    the Sponsor filter's list.

    Returns (index, years, unnamed, sponsored) -- unnamed being the member
    ids the roll calls reference that the roster cannot name, and sponsored
    being what each member put their name to, which the legislator pages have
    advertised since they were written and never had.
    """
    unnamed = set()
    sponsored = defaultdict(list)
    # Each recording's length, from the video indexes the committees' Videos
    # tabs read (proceedings.video_facts), for a bill's Hearings tab.
    video_facts = P.video_facts()

    index, years = [], set()
    # WHERE EACH BILL'S COMMITTEE FILES ARE (the owner, 19 November 2026):
    # the Secretary of State's archive page, by the rule sos_archives.address
    # keeps, read from collected/sos_archives.json. Never fetched.
    sos_files, sos_day = SA.load(), build_date.today().isoformat()
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
            _people.setdefault(str(_old), legs.get(_sit) or (former or {}).get(_sit) or {})
    # AN EMPLOYEE NUMBER IS ITS PERSON (9 November 2026). The bill status page
    # names a sponsor by the employee number of the seat they then held, and a
    # member who has since moved chamber holds another: Sen. David Rochefort's
    # 2025 House bills, filed as Rep. for Grafton 1, name 409162, which the
    # register (generated/person_numbers.json) gives to the person member_links
    # already joins to the senator. `numbers` is that register, {employee
    # number: person}; a number is taken only where its person is one the site
    # has a page for, and never over an id the site already answers.
    for _n, _p in (numbers or {}).items():
        if _people.get(_p):
            _people.setdefault(_n, _people[_p])
    # And, for a term whose own roster is frozen and not the sitting one
    # (main says which), the members who left by name: bill_sponsor_list
    # says why. Every one of a name, in order, since only the one who sat
    # that term is taken.
    _left = None
    term_rosters = term_rosters or {}
    # ... AND THE TERM STILL SITTING (Alice, 9 November 2026): a member who
    # resigned mid-term holds no seat in the roster either, and the bill
    # status page names them by an employee number the roster no longer
    # answers. Rep. Glenn Cordelli's HB 137 read "Carr 07", unlinked, while
    # his HB 121 (a database row) linked to his page. The same name rule
    # holds: only someone who sat in that chamber that term is taken.
    if term_rosters or former:
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
    _shared_names = {}      # {term: full names two employee numbers of that term share}
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
    # Each chamber's sitting days, for the day a bill left on the table or in
    # interim study died (chamber_sittings), and the bill each LSR became, for
    # the next term's bill an interim study report's clerk named (lsr_bills).
    # The journals add the sittings the docket has no floor row of
    # (with_journals), and the other bills' rows the day a bill whose own row
    # is missing died on the table (table_session_ends).
    sittings = with_journals(chamber_sittings(narratives), journal_sittings())
    table_ends = table_session_ends(narratives)
    lsrs = lsr_bills(bills)
    # The journals the drain fetched, for a House Journal record's citations:
    # read once, and only if a bill needs them.
    _jk = {}

    def _jkeys():
        if "keys" not in _jk:
            _jk["keys"] = journal_keys_from_queue()
        return _jk["keys"]
    # ONE MKDIR A YEAR FOLDER (16 October 2026, private/SITE_DATA_PROFILE.md,
    # section 5). Each bill made its year's folder, which already stood for
    # every bill but the year's first: 33,717 calls and about 13 seconds on
    # Windows. The folders made are kept here, and each is made once.
    year_dirs = set()
    # How many members were in office on each day a chamber took a roll call,
    # which is what three fifths is of on a division (bill_rollcalls).
    in_office = RO.members_in_office(rollcalls)
    # THE PARTY A 1989-1998 SPONSOR PLACED ON A PAGE TAKES (early_party, the owner's
    # decisions of 15 November 2026) is the page's only where every record of the person gives
    # that one party, else the bill's term's Manual's, and the labels of their bills of
    # 1999-2026 are among those records. This loop reaches 1989 first, so those labels are drawn
    # here beforehand, exactly as the loop will draw them, and nothing else of the lists is
    # kept. With no `id_parties` none is given.
    _parties = None
    if id_parties is not None:
        _labelled = {}
        for bid, b in ((k, v) for byb in bills.values() for k, v in byb.items()):
            year = int(b.get("lsr_year") or 0)
            term = P.term_of(str(year)) if year else ""
            if term[:4] >= "1999":
                bill_sponsor_list(bid, b, year, term, current, sponsors, _people, leg_by_sort,
                                  leg_by_name, defaultdict(list), seats,
                                  left=_left if (term in term_rosters or term == current) else None,
                                  term_roster=term_rosters.get(term),
                                  record_chambers=record_chambers, labelled=_labelled)
        _parties = party_record(_people, _labelled, id_parties)
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
                                    left=_left if (term in term_rosters or term == current) else None,
                                    term_roster=term_rosters.get(term),
                                    record_chambers=record_chambers, parties=_parties)
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
        # The bill's text, read here rather than with the rest of its record
        # below: a law's own Effective Date lines date its Law stop.
        btext = bill_text_block(P.per_term(bill_texts, term, current).get(bid), narr)
        intro, jsteps = journey(narr, bid, rcs, chapter, dl.get("line", ""), term,
                                db_effective=dl.get("database_effective", ""),
                                untold=untold, text=(btext or {}).get("body", ""))
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
        # A PRIME SPONSOR PLACED ON A PERSON (past_roster.py), who has no page and
        # no party: the Sponsor filter keys them on their full name, not on the
        # surname and seat it must use for a row left as printed (app.js
        # spKey). Only while no other employee number of the term carries the
        # same full name; two do, and the seat tells them apart again.
        if (prime and prime.get("employee") and prime.get("matched") == PAST_ROSTER_MATCH
                and not prime.get("slug") and not prime.get("party")):
            if term not in _shared_names:
                _shared_names[term] = past_roster_shared_names(
                    P.per_term(sponsors, term, current), person_name)
            if row["sponsor"] not in _shared_names[term]:
                row["sponsor_person"] = 1
        # THE CO-SPONSORS, by the name the Sponsor filter groups on (the
        # person, 12 October 2026: choosing a sponsor shows "the prime
        # sponsored bills by the selected rep first and then the bills they
        # cosponsor"). Only where there are any, so the index grows by little.
        _cosp = list(dict.fromkeys(
            n for n in (person_name(s_.get("name") or "") for s_ in sp_list if s_ is not prime)
            if n and n != row.get("sponsor")))
        if _cosp:
            row["cosp"] = _cosp
        # And everyone the row names, for the Sponsor filter's list of the
        # term's members (sponsor_roster: site/sponsors/<term>.json).
        if people is not None:
            SR.note_bill(people, term, row, sp_list, prime, person_name)
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
        # THE BILL'S TAGS, as their places in meta.json's list (site_tagging),
        # only on a bill that has one: the up-front index grows by a few
        # digits a tagged bill, and by nothing without a registry.
        bill_tags_ = ((tagging or {}).get("bills") or {}).get((term, bid))
        if bill_tags_:
            row["tags"] = [tagging["at"][t_] for t_ in bill_tags_]
        index.append(row)
        # THE RAIL'S ENDINGS (the person, 8 and 9 October 2026): a bill that
        # died on the table is the pause where it was tabled and the cross at
        # Law on the day it died, with the death's line and, where its history
        # does not tell it, the sentence; a bill held for interim study, once
        # its session is over, the cross at Law on the day its chamber last
        # sat, with that line and the committee's report's (study_ending).
        tabled = None
        if not story and row.get("passage"):
            tabled, ending = session_endings(
                narr, jsteps, row["passage"], row.get("chip", ""), status, term,
                not (own and not session_over), sittings, lsrs, ending, ends=table_ends)
        jrail = journey_rail(intro, jsteps, row["passage"], bid, status, chip=row.get("chip", ""),
                             tabled=tabled)
        # What the committee reported, on a bill held for interim study: the
        # note under the panel (app.js endNote).
        srep = study_report(narr, term) if row.get("chip") == INTERIM_STUDY else None
        # The same stops on the list card, from the start (index_rail).
        if jrail:
            row["rail"] = index_rail(jrail)
        why = journey_disagrees(jsteps, kind, status, row["passage"], bid)
        j_tally[(term, "empty" if not jsteps else "disagree" if why else "agree")] += 1
        if why and term == current:
            j_current.append(f"{bid}: {why}")
        for s_ in jsteps:
            law_line_dated(s_)
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

        rc_out = bill_rollcalls(bid, term, rcs, narr,
                                votes_by_bill, legs, unnamed, in_office)
        # Whom this term's movers are looked for among (mover_pool).
        _mpool, _mpages = mover_pool(term, current, legs, term_rosters, _people,
                                     voter_pools)
        for r in rc_out:
            r.pop("_ord", None)
            # THE VOTE WORDS' KEY (the person, 8 October 2026; motions.py):
            # which motion this was, read once here, so the Votes tab draws
            # its head and its chip in the approved words (components.
            # vote_head, vote_chip), with the record's own words under it
            # where they differ (mrec).
            r.update(MO.classify(r.get("question"), bid, r.get("body") or "",
                                 _WORDBOOK["votes"]["motions"]))
            # WHAT THE CHAIR RULED (the owner, 23 October 2026: "Uphold the
            # Ruling of the Chair" with the ruling for context, where the
            # Journal states it, and no gloss): journal_motions.ruling_of.
            if r.get("mk") == "uphold_ruling" and not r.get("ruling") and r.get("_rc"):
                rul = VP.ruling(r["_rc"])
                if rul:
                    r["ruling"] = rul
            # THE MOVER AS THE PERSON IN A SENTENCE (D14): "Moved by Rep. Joe
            # Alexander (R - Hills 29)", linked, where the docket's "Rep.
            # Alexander Jr." can mean one member of the chamber. Among the
            # term's own members with the seat each held then (mover_pool):
            # the sitting roster in the current term, a finished term's frozen
            # roster after the turn; elsewhere the docket's words stand.
            if r.get("mover") and _mpool is not None:
                who = mover_member(r["mover"], r.get("body"), _mpool, pages=_mpages)
                if who:
                    r["mover_m"] = who
        # THE MEMBER WHO WROTE A COMMITTEE'S REPORT AS THE PERSON'S CHIP (the
        # owner, 19 November 2026), by the movers' rule and among the same
        # members, with the seat held then: report_author says when.
        if _mpool is not None:
            report_authors(rep_written, _mpool, _mpages)
        # WHERE EACH ROLL CALL'S CARD IS on this bill's Votes tab, for the
        # session days (`rc_cards`, write_floor_record): {term: {bill: {roll
        # call: index into the record's rollcalls}}}.
        _cards = {}
        for _card, _rc in enumerate(rc_out):
            _rc_key = _rc.pop("_rc", None)
            if _rc_key:
                _cards[_rc_key] = _card
        if rc_cards is not None and _cards:
            rc_cards.setdefault(term, {})[bid] = _cards

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
        # How long its recording runs, where the video index says: the Hearings
        # tab's playlist gives it beside each recording, as a committee's does.
        for _st in stations:
            _secs = (video_facts.get(_st.get("video_id") or "") or {}).get("seconds")
            if _secs:
                _st["seconds"] = int(_secs)
        # EACH FLOOR STATION'S MOMENT, for the session day's card of this bill
        # (`moments`, write_floor_record): the very time this bill's own
        # Hearings tab opens its player at and the vote it ends on, so the two
        # pages give one answer (nothing about a timestamp changes). A bill
        # the consent calendar decided has none: "a bill that passes on the
        # consent calendar needs no embedded YouTube recording" (the person,
        # 9 October 2026, v3).
        if moments is not None:
            for _st in stations:
                _m = floor_moment(_st)
                if _m:
                    moments.setdefault(term, {}).setdefault(bid, []).append(_m)
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
        if _bd not in year_dirs:
            _bd.mkdir(parents=True, exist_ok=True)
            year_dirs.add(_bd)
        # The stages' text run together; of the stages as they are told,
        # where one of them is told without its enrolment (stages_told).
        _narrative = (" ".join(s_["text"] for s_ in stages_told(narr, kind, row["passage"]))
                      if unenrolled else (narr or {}).get("narrative", ""))
        # The history, plus a closing paragraph where the bill's ending
        # is only on the status page. 120 bills showed a settled headline
        # over a story that stopped at the committee report.
        _stages = (story["stages"] if story else
                   stages_told(narr, kind, row["passage"]) + ([ending] if ending else []))
        # The members the story names, for the page to link (story_people).
        # Among the term's own members with the seat each held then, as for a
        # roll call's mover (mover_pool): the sitting roster in the current
        # term, a finished term's frozen roster after the turn, and a term of
        # 1999-2024 its own voters by the seat of the term.
        # _story_who, NOT _people: that is every member and former member,
        # which bill_sponsor_list and the hearing record read for the bills
        # after this one; taking the name made it a list there, and the dry run
        # of 8f700a7 stopped in the site data ('list' object has no attribute
        # 'get') on the second current-term bill a sponsor list was read for.
        _story_who = (story_people([_narrative] + [s_.get("text") or "" for s_ in _stages or []],
                                _mpool, pages=_mpages) if _mpool is not None else [])
        (_bd / f"{bid}.json").write_text(json.dumps({
            "id": bid, "year": year, "term": term,
            "title": b.get("title", ""),
            "narrative": _narrative,
            "stages": _stages,
            **({"story_people": _story_who} if _story_who else {}),
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
            "events": _with_plain([{"date": e["date"], "text": listed_line(e),
                        "routine": is_routine(docket_line(e)),
                        **({"date_as_recorded": e["date_as_recorded"],
                            "date_note": e.get("date_note") or (
                                "The General Court's online docket gives "
                                "another date for this; the journal and the "
                                "other records of that session day place it "
                                "on the date shown.")}
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
                       for e in docket_lines(narr)], bid),
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
            # word stays in the status -- "Committee report filed", where the
            # chip says Died; a tabling or a disagreement between the chambers
            # says how it died (ENDED_AS) -- and this says
            # why nothing follows it, on the bills of the current term only:
            # an archived term says the same thing in its coverage note.
            **({"session_over": session_over}
               if session_over and term == current and disp.stale else {}),
            # What the committee reported on a bill taken for interim study.
            **({"study_report": srep} if srep else {}),
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
            # The Secretary of State's archive page of the bill's committee
            # files, where sos_archives.address gives one (the Reports tab).
            **({"sos_archives": _sos} if (_sos := ("" if b.get("journal") else SA.address(
                sos_files, b.get("lsr_year"), bid, b.get("lsr_num"), sos_day))) else {}),
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
            # WHICH ARTICLES OF THE CONSTITUTION A CACR CHANGES (17 October
            # 2026), from its own resolving clauses ("That article 78 of the
            # second part of the constitution be amended ..."), each to its
            # article on the Laws page's Constitution tab. Only a CACR, only
            # a clause in a form that leaves no doubt, and only an article
            # the Constitution as read holds (parse_constitution.cacr_targets).
            **({"constitution": c} if bid.startswith("CACR")
               and (c := constitution_targets((btext or {}).get("body", ""))) else {}),
            # WHAT IT CHANGED, AS THE LAW IT BECAME: the statute's own source
            # notes, not the bill's text (RSA_PAGE.md §3: the two agree on
            # about nine in ten of the text's claims). Only on a bill a note
            # names, and only where the statute pages are built.
            **({"changed": ch} if (ch := statutes_enacted(term, bid)) else {}),
            # THE TAGS (tag_rules.site_tags), in the registry's order, each by
            # its id and its name as the registry words it, and the evidence
            # that attached it ("T:mental health", the rule's phrase in the
            # title): in the record, for the page's source data and the
            # downloads, and never printed on the page. Only where there are any.
            **({"tags": [{"id": t_, "name": tagging["names"][t_], "why": w_}
                         for t_, w_ in bill_tags_.items()]} if bill_tags_ else {}),
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
    for _said in early_party_said(sponsored, _people, _parties):
        print(_said)
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
    ap.add_argument("--notes", default="corrections/bill_notes.json",
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
    ap.add_argument("--interim", default="interim_statements.json")
    ap.add_argument("--hearing-reports", default="senate_hearing_reports.json",
                    help="the Senate committees' hearing reports, from "
                         "senate_hearing_reports.py; skipped if not there")
    ap.add_argument("--chapters", default="chapters.json",
                    help="the chapter each bill became, from "
                         "extract_chapters.py; skipped if not there")

    ap.add_argument("--status", default="corrections/status/status.txt")
    ap.add_argument("--districts", default="site/districts.json")
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
    # The General Court's own subject code for the archive, where the database
    # holds one and the record has none (official_topics says how); the model
    # then answers only for the bills left without a subject.
    _n = OT.adopt(bills, load(D / "subjects.json", {}))
    if _n.get("filled"):
        print(f"  {_n['filled']:,} archived bills given the General Court's own "
              f"subject code as their topic ({_n['a code with no name on disk']:,} "
              "carry a code with no name on disk and keep the model's answer)")
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
    leg_by_sort, leg_by_name, _roster_clash = roster_name_keys(legs.values())
    for _how, _k, _ms in _roster_clash:
        print(f"  WARNING: two sitting members share the {_how} {_k!r} "
              f"({' and '.join(str(x.get('name')) + ' ' + str(x.get('id')) for x in _ms)}); a sponsor named by it alone "
              "is left unlinked rather than given to the first")

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
    # A MOTION ON ONE BILL'S DEBATE IS THE BILL'S (the owner, 23 October 2026):
    # a roll call the roll-call file files under no bill whose Journal passage
    # moves to divide, limit or call the question of one bill of the term --
    # HB 1570's division of 20 March 2014 -- is drawn under that bill, and
    # its ballots go with it (below). vote_passage says which; session_days
    # and build_nobill_votes move the same ones.
    rollcalls, MOVED_TO_BILL = VP.move_on_bills(rollcalls)
    if MOVED_TO_BILL:
        print(f"  {len(MOVED_TO_BILL)} roll call(s) on no bill drawn under the bill whose debate "
              "they divided, limited or called the question of: "
              + ", ".join(f"{k} -> {b}" for k, b in sorted(MOVED_TO_BILL.items())))
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
    # Each committee's interim study statement, a report of its own on the
    # Reports tab, held back where the docket's line disagrees (interim_cards).
    interim = load(a.interim, {})
    if interim and not N.is_term_keyed(interim):
        sys.exit(f"{a.interim} is not keyed on term. Run interim_statements.py again.")
    if interim:
        held = interim_cards(reports, interim, narratives)
        n_int = sum(len(v) for byb in interim.values() for v in byb.values())
        print(f"Interim study statements: {n_int - len(held):,} on the Reports tab, "
              f"{len(held)} held back where the docket's line disagrees"
              + "".join(f"\n    {t_} {b_} ({c_}): {w_}" for t_, b_, c_, w_ in held))
    else:
        print(f"  ({a.interim} is not here: no interim study statements on the Reports tab)")
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
    tagging = site_tagging(bills, bill_texts)
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
        # A roll call drawn under the bill whose debate it was on (above):
        # its ballots are that bill's, and a member's Votes tab names it.
        if key in MOVED_TO_BILL:
            v["bill"] = MOVED_TO_BILL[key]
        # A ballot of Organization Day is on the next term's measure
        # (proceedings.vote_term): HR 1 of 2027, not of 2025.
        votes_by_bill[(P.vote_term(v["year"], v.get("date")), v["bill"])][key].append(v)
        votes_by_member[v["member_id"]].append(v)
    print(f"{len(bills):,} bills, {len(legs):,} legislators, "
          f"{sum(len(x) for x in votes_by_member.values()):,} member votes")

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
    # AND A MEMBER WHO MOVED AND HAS LEFT (former_movers): one page, the later
    # chamber's, with every chamber's votes, as for a sitting mover; the
    # earlier page's address answers with a 301 to it (build_pages, from the
    # index row's moved_from). Worked out from the former members as they
    # would stand apart, so each earlier page's address is the one it had.
    import people as PE
    register = PE.load_register(Path("generated/person_numbers.json"))
    e2p = PE.emp_to_pid("db")
    if register and e2p is None:
        # NOT SILENT (the review of 30 October 2026): without the roster view
        # no register number maps to a site id, nothing joins, and the pages
        # of the members who moved and left come back in two halves.
        print("  WARNING: db/Legislators.psv is not here, so no member who sat in both "
              "chambers and has left is joined; their pages stand split, one per chamber")
    movers = former_movers(register, e2p or {}, legs, links, votes_by_member,
                           confirmed=same_person())
    movers = {k: v for k, v in movers.items() if k in former and all(e in former for e in v)}
    if movers:
        def _addr(m):
            lab = member_labels(m.get("name"), chamber=m.get("chamber"),
                                party=m.get("party_code") or m.get("party"),
                                district=m.get("district"), county=m.get("county"),
                                county_abbr=m.get("county_abbr"))
            return "/legislator/" + (m.get("slug") or member_slug(m, lab))
        moved_from = {k: [_addr(former[e]) for e in v] for k, v in movers.items()}
        for k, v in movers.items():
            links[k] = [*links.get(k, []), *v]
        former = former_roster(legs, votes_by_member, links,
                               load("former_members.json", {}),
                               max(bills) if bills else "")
        for k, addrs in moved_from.items():
            former[k]["moved_from"] = addrs
        print(f"{len(movers)} member(s) who sat in both chambers and have left now have one "
              "page, the later chamber's, with every chamber's votes: "
              + ", ".join(f"{former[k].get('name')} ({'+'.join([k, *v])})"
                          for k, v in sorted(movers.items())))
    # THE SEAT A FORMER MEMBER'S PAGE GIVES, FROM THE BILLS OF THEIR LAST TERM
    # (date_former_seats): the record of where they last sat is wrong on 75
    # of the 1,468 pages whose last term's bills print one seat.
    former, redated = date_former_seats(former, votes_by_member, printed_seats(),
                                        corrected_seats(), legs)
    if redated:
        print(f"{len(redated)} former member(s) given the seat their last term's bills print, "
              "not the record's; the old address answers with a 301: "
              + ", ".join(f"{former[k].get('name')} ({was} -> {now})"
                          for k, (was, now) in sorted(redated.items())[:12])
              + (" ..." if len(redated) > 12 else ""))
    _kept, _unrecorded = keep_moved(former, links=links,
                                    sitting={_member_address(m) for m in legs.values() if m.get("name")})
    if _kept:
        print(f"{_kept} recorded former address(es) kept answering with a 301 though the page "
              f"no longer moves from them ({MOVED_ADDRESSES})")
    if _unrecorded:
        # NOT SILENT: a move this build made and the file does not hold dies
        # the first build after its reason goes away
        print(f"  WARNING: {len(_unrecorded)} former address(es) answered with a 301 are not "
              f"in {MOVED_ADDRESSES}: record them with python3 src/ops/record_moves.py "
              f"after this build, and commit the file. First: {', '.join(_unrecorded[:4])}")
    # THE LABEL NAMES THE LAST TERM'S SEAT, OR NONE (last_term_labels); the page stays put.
    import parse_districts as PDIST
    district_lines = PDIST.table(".", ST.SETTINGS)
    former, relabelled = last_term_labels(former, votes_by_member, printed_record(),
                                          district_lines)
    if relabelled:
        print(f"{len(relabelled)} former member(s) labelled with their last term's seat, or none where "
              "it is not known; no page moves: "
              + ", ".join(f"{former[k].get('name')} ({was} -> {now})"
                          for k, (was, now) in sorted(relabelled.items())[:12]))
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
    # The chamber of the term for a 1989-1998 sponsor the General Court's record supplies,
    # from that term's Manual, for the members' "On Record" line (sponsor_record_chambers).
    # Never in silence: the seated, a seat list not read, a row the Manual seats elsewhere.
    record_chambers = sponsor_record_chambers(sponsors)
    for _said in sponsor_record_said(sponsors, record_chambers):
        print(_said)
    # WHAT EACH OTHER RECORD OF A PERSON SAYS THEIR PARTY IS, which the party a 1989-1998
    # sponsor placed on their page takes is held to (early_party): the ballots cast under their
    # ids, the legislators table's party (generated/careers.json) and the party the general
    # election's returns print for them in each 1989-1998 term's Manual for the General Court
    # (manual_parties), which is also, term by term, the party a person of two parties takes on
    # that term's bills. build_bills adds the labels of their bills of 1999-2026. A record not
    # read gives more people a party, not fewer, so it is said; and without the Manual, the one
    # record here of anyone's party in those years (nine of the ten people found in two parties
    # on 15 November 2026 were found by it alone), no 1989-1998 sponsor is given one.
    _careers = load(Path("generated/careers.json"), {})
    _manual_party = manual_parties()
    id_parties = None if _manual_party is None else party_ids(votes_by_member, _careers,
                                                              _manual_party)
    if _manual_party is None:
        print("  sponsors: no Manual seat list read; no 1989-1998 sponsor is given a party, "
              "since its returns are the one record here of a party in those years")
    elif not _careers:
        print("  sponsors: no generated/careers.json read; a 1989-1998 sponsor's party is not "
              "held to the legislators table's")

    segs, marks = load_transcripts(a, procs, prows)
    # Each roll call's card on its bill's Votes tab, filled by build_bills
    # for write_floor_record.
    rc_cards = {}
    # And each floor station's moment, for the session day's cards.
    floor_moments = {}
    # THE SEAT EACH MEMBER HELD IN EACH TERM (term_seats), worked out once, here,
    # for the movers of the terms before the current one (term_voters) and the
    # session days (write_floor_record), so both name a member by one seat.
    # Only a seat of the lines the term sat on (term_seats, seat_of_the_lines).
    floor_ballots, seats_refused = {}, []
    floor_seats = term_seats(votes_by_member, ballots=floor_ballots, lines=district_lines,
                             refused=seats_refused)
    if seats_refused:
        print(f"{len(seats_refused)} term seat(s) named by no district of the lines their term sat on, "
              "so the member is named without a seat on that term's days: "
              + ", ".join(f"{lab} in {t}" for t, _m, lab in seats_refused[:8]))
    voters = term_voters(votes_by_member, floor_seats)
    # -------------------------------------------------------------- index --
    # Who each term's bills name, for the Sponsor filter (sponsor_roster).
    sponsor_people = {}
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
                               people=sponsor_people,
                               numbers={str(_n): str(_q.get("person") or "")
                                        for _q in ((register or {}).get("people") or [])
                                        for _n in (_q.get("numbers") or [])},
                               session_over=session_over(a.status),
                               coverage=archive_coverage(
                                   bills, narratives, sponsors, reports,
                                   rollcalls, procs,
                                   max(bills) if bills else ""),
                               ballots=load_ballots(BALLOTS, bills),
                               rc_cards=rc_cards, moments=floor_moments,
                               record_chambers=record_chambers, id_parties=id_parties,
                               tagging=tagging, voter_pools=voters)
    add_related(out, index)
    add_same_number(out, index, notes)
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
    # THE SPONSOR FILTER'S MEMBERS, a file a term beside the index (the owner,
    # 19 November 2026): who the term's bills name, and for the term the
    # sitting roster describes, every sitting member and every member who
    # served in it and has left. Only for a term the index has.
    sponsor_people = {t: b for t, b in sponsor_people.items() if t in by_term}
    _sitting_term = max(bills) if bills else ""
    if _sitting_term in by_term and _sitting_term not in term_rosters:
        SR.add_sitting(sponsor_people, _sitting_term, legs, former, own_slug, person_name,
                       labels=sitting_labels)
    SR.write(out, sponsor_people)
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
    # Who held the chair's offices, for the vote cards' presiding ballots
    # and the officers' own pages (build_officers).
    offices = build_officers(out, votes_by_member, legs)
    # What the session days need of the floor that only the ballots and the
    # bills' Votes tabs say: who presided over each roll call, and where each
    # roll call's card is (write_floor_record, FLOOR_RECORD).
    # The cards of the roll calls on no bill first (nobill/<term>.json),
    # since the session days draw those from them too.
    nobill = write_nobill_cards(out, rollcalls, votes_by_bill, legs, unnamed)
    write_floor_record(D, votes_by_member, rc_cards, floor_moments, nobill,
                       worked=(floor_seats, floor_ballots))
    # The members' Votes tabs' shared file, once build_bills has said where
    # each roll call's card is (write_rollcall_index).
    write_rollcall_index(out, rollcalls, rc_cards, nobill)
    # The terms of 1989-1998 each member's Manual for the General Court seats them in with no
    # bill that term (manual_seats), and what was left out, said.
    manual, manual_left = manual_seats({**legs, **former}, links, sponsored, votes_by_member)
    for _said in manual_said(manual, manual_left):
        print(_said)
    lg = build_legislators(out, legs, votes_by_member, towns, unnamed,
                           sponsored, bill_year, links, former, offices,
                           index_rows={(r.get("term"), r.get("id")): r for r in index},
                           manual=manual)

    # ---- home page data ----------------------------------------------------
    # Everything the landing page needs, precomputed here where the full records
    # are already in memory rather than making the browser fetch 2,000 files.
    today = build_date.today().isoformat()
    soon = (build_date.today() + _td(days=14)).isoformat()
    recent_cut = (build_date.today() - _td(days=3650)).isoformat()

    def _said(e):
        s = (e.get("told") or "").strip()
        if not s:
            return (e.get("raw") or "")[:150]
        return s if len(s) <= 220 else s[:220].rsplit(" ", 1)[0] + "\u2026"

    actions = []
    for b in index:
        narr = narratives.get(b["term"], {}).get(b["id"])
        for e in (narr or {}).get("events", []):
            if e.get("cancelled") or not e.get("date") or e["date"] > today:
                continue
            # The year the bill's own page is filed under (/bill/<year>/), which
            # a link to it needs and the day of the action does not give.
            actions.append({"date": e["date"], "bill": b["id"], "n": b["n"],
                            "year": b.get("year") or "",
                            "title": b["title"][:110],
                            # IN THE HISTORY'S WORDS, NOT THE CLERK'S (the
                            # person's list, 10 October 2026): the row's own
                            # sentence (narrative.SAID_DAYS), the line as typed
                            # only where the history tells the row in none.
                            "what": _said(e)})
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

    # LATEST ACTIVITY, A MEETING AN ITEM (the person, 24 October 2026: "bills
    # should not be repeated twice like they are right now for both the bill
    # executive sessions and the outcome of the executive session listed as
    # two separate meetings"). `recent` above is a row a docket event, and an
    # executive session and the report voted at it are two events, so each
    # bill a committee voted on took two of the box's five rows. `latest` is
    # the newest meetings -- a committee's day, a chamber's sitting -- each
    # with its bills once and what was done to each there; latest_activity.py
    # says how, and build_pages draws it.
    import latest_activity as LA
    latest = LA.latest(prows, narratives, today, {(b["term"], b["id"]): b for b in index},
                       motion_words=_WORDBOOK["votes"]["motions"])
    if latest:
        print(f"  latest activity: {len(latest)} meetings, from {latest[-1]['date']} to "
              f"{latest[0]['date']}, {sum(m['n'] for m in latest):,} bills taken up")
    else:
        # SILENCE IS NOT SUCCESS: the box would draw nothing, which looks like
        # a General Court that has not met.
        print("  WARNING: latest activity holds no meeting: no committee day or sitting "
              "on or before today in proceedings.csv or narratives.json")

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
        # `recent` is no longer drawn on the home page (`latest` is, 24
        # October 2026); it is the docket's own newest lines, kept as they were.
        "recent": actions[:12], "latest": latest, "upcoming": upcoming[:80],
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
    # The tags' list and the words that lead to them, only where a bill
    # carries one (site_tagging), so meta.json is as it was without them.
    meta.update(tagging.get("meta") or {})
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
