#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.313
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
# states in words and report_station (hearing_reports.py) and the stations
# (stations.py) split on; named here as before.
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


# A BILL'S ROLL CALLS AS ITS VOTES TAB DRAWS THEM -- a day's votes in the order they
# happened (vote_chronology), every recorded vote on one bill (bill_rollcalls), the
# note above the table and the card of a roll call on no bill (write_nobill_cards)
# -- are bill_votes.py's (20 November 2026). Each name is here as before.
from bill_votes import (AMENDMENT_ROW, NOBILL, PASSAGE_Q, RC_TALLY, VOTE_KIND_RE, _paired_by_count,  # noqa: E402,F401
                        bill_rollcalls, vote_chronology, vote_note_for, write_nobill_cards)


# THE YEAR A CITED VOLUME IS FROM, AND ITS ADDRESS (SOURCE_YEAR, _source_url) are
# parts.py's (20 November 2026): _cite below reads them, and so do the committee
# reports. Each name is here as before.
from parts import SOURCE_YEAR, _source_url  # noqa: E402,F401


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


# WHAT A BILL'S TEXT SAYS IT CHANGES -- the statutes its clauses amend or repeal
# (bill_amends) and the articles a CACR amends (constitution_targets) -- is
# bill_statutes.py's (20 November 2026). Each name is here as before.
from bill_statutes import (AMEND_WORD, CLAUSE_END, NEXT_SECTION, PART_WORD, REPEALED, REPEAL_LIST,  # noqa: E402,F401
                           _CONSTITUTION, bill_amends, constitution_targets)


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


# WHAT A BILL'S COMMITTEES REPORTED AND WHO SPOKE AT ITS HEARINGS -- the calendars'
# committee reports, the interim study statements, a hearing's sign-ins and the
# Senate's hearing reports with their speakers -- are hearing_reports.py's (20
# November 2026). Each name is here as before.
from hearing_reports import (CAL_DATE, INTERIM_FROM_DOCKET, INTERIM_SIDE, INTERIM_WORDS,  # noqa: E402,F401
                             LOST_RECONSIDER, MONTHS, PUBLIC_HEARING, REPORT_AGAIN, REPORT_CAL,
                             SPEAKER_TITLE, _again_carried, _cal_date, _cal_key, _mdy,
                             _same_statement, attach_hearing_reports, committee_reports,
                             hearing_report_for_page, hearing_testimony, interim_cards, rec_key,
                             report_station, resolve_speaker, speaker_index)


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


# THE RAIL'S ENDINGS -- a bill the session's end killed with no vote, left on the
# table or held for interim study, the study committee's report, and the days
# each chamber sat, which date them -- are endings.py's (20 November 2026).
# Each name is here as before.
from endings import (FIRST_YEAR_TABLE_DIES, INTERIM_REPORT_ROW, INTERIM_REPORT_TALLY,  # noqa: E402,F401
                     INTERIM_REPORT_YEAR, NEXT_LSR, NO_SITTING_ROW, ROW_DAY, SESSION_END_DEATHS,
                     SITTING_TYPES, SPECIAL_JOURNAL, SPECIAL_SESSION_ROW, TABLE_DEATH_ROW,
                     TABLING_ROW, TOLD_TABLE_DEATH, _sat_by_journal, adjourned_by,
                     chamber_sittings, died_on_table, interim_report, journal_sittings, last_sat,
                     lsr_bills, next_term_bill, session_end_line, session_endings, study_ending,
                     study_said, table_death, table_death_line, table_death_told,
                     table_session_ends, term_years, with_journals)


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

# The lines the session's end makes (session_end_line) are endings.py's, imported
# with the rest of the rail's endings above.


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


# THE MEMBERS A BILL'S RECORD NAMES -- its sponsors, with the seats and parties the
# term's Manual gives, and each ballot's voter, a motion's mover, a report's author
# and a member the story names -- are sponsors.py's (20 November 2026). Each name
# is here as before.
from sponsors import (MANUAL_PARTY, MOVER_HONORIFIC, MOVER_SUFFIX, Parties, STORY_PERSON,  # noqa: E402,F401
                      _LABEL_PARTY, _SPELLINGS, _VOTE_LABELS, _manual_name_keys, _spellings,
                      bill_sponsor_list, early_party, early_party_said, manual_parties,
                      manual_said, manual_seats, mover_member, mover_pool, party_ids, party_letter,
                      party_record, report_author, report_authors, sponsor_record_chambers,
                      sponsor_record_rows, sponsor_record_said, story_people, term_voters,
                      vote_member)


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
# A CACR'S BALLOT -- the election its text names, the voters' answer where the docket
# records none (ballot_results.json, load_ballots), the voters' line and card
# (ballot_step, ballot_card) and what a CACR both chambers passed now says
# (cacr_to_the_voters) -- is cacr_ballots.py's (20 November 2026). Each name is
# here as before.
from cacr_ballots import (BALLOTS, BALLOT_SOURCE, ELECTION_IN_TEXT, ISO_DAY, NOT_RATIFIED,  # noqa: E402,F401
                          RATIFIED, TO_THE_VOTERS, ballot_card, ballot_step, cacr_to_the_voters,
                          docket_count_differs, election_day, load_ballots, ratified)


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


# A BILL'S TOPIC AS THE INDEX FILES IT -- the topic model's for the terms the General
# Court gave none (merge_guessed_topics), and the site's one vocabulary applied last
# (unify_vocabulary) -- is bill_topics.py's (20 November 2026). Each name is here as
# before.
from bill_topics import ADDED_CODES, TOPICS_GUESSED, merge_guessed_topics, unify_vocabulary  # noqa: E402,F401


# A General Court topic name in a reader's words (TOPIC_WORDS), and the site category a
# record's topic ends up under (vocabulary_of), are topic_vocabulary.py's, imported
# beside statute_changes above: request_topics files a request by them too.


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
