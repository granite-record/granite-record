#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.331
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
# parts.py's (20 November 2026): _cite (documents.py) reads them, and so do the
# committee reports. Each name is here as before.
from parts import SOURCE_YEAR, _source_url  # noqa: E402,F401


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


# WHERE THE SESSION IS -- the day the current term ran out of session days
# (session_over, session_over_in) and the site's panel of where the session is
# (build_status) -- is session_status.py's (20 November 2026). Each name is here
# as before.
from session_status import (build_status, session_over, session_over_in)  # noqa: E402,F401


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


# THE DATABASE'S STATUS CODES, WHERE THE STATUS PAGE STATES NOTHING -- the dump's
# codes in the page's words (db_statuses), the terms no dump holds (no_dump_for)
# and a record's blank fields filled from it (fill_status_from_db) -- are
# db_status.py's (20 November 2026). Each name is here as before.
from db_status import (DB_FROZEN, DB_LEGISLATION, DB_STATUS_COLUMNS, _DB_STATUS, _status_codes,  # noqa: E402,F401
                       db_statuses, fill_status_from_db, no_dump_for, terms_without_a_dump)


# WHAT BECAME OF A BILL, AND WHERE THAT ANSWER CAME FROM -- its disposition
# (bill_disposition, Disposition), the chamber it started in (origin_of), a
# measure of a finished term that cannot still be moving (ended_with_the_term)
# and the test that its journey, status and rail tell one story
# (journey_disagrees) -- is disposition.py's (20 November 2026). Each name is
# here as before.
from disposition import (CONFERENCE_NOT_REPORTED, CONSIDERATION_REFUSED, DIED_ON_TABLE_ROW,  # noqa: E402,F401
                         Disposition, ENDED_WITH_TERM, ENDING_NOT_ON_RECORD, NO_DISPOSITION,
                         SECOND_ADOPTED, SESSION_ENDED_STANDS, STAGE_STATED, UNFINISHED,
                         bill_disposition, ended_with_the_term, journey_disagrees, origin_of,
                         stated_stage)


# Whether a chamber would not take a conference's report up
# (conference_not_taken_up, and CONF_NOT_TAKEN_UP, one of the tests of a
# finished term's measure in disposition.py) is conferences.py's: the status
# reads it too.
from conferences import CONF_NOT_TAKEN_UP, conference_not_taken_up  # noqa: E402,F401


# WHAT A BILL'S PAGE CITES AND LISTS OF ITS RECORD -- a docket line's citation
# (_cite) and plain words (_with_plain), the documents a reader can open
# (bill_documents), the story of a bill whose record is the House Journal's
# (journal_story) and the notes on where a record comes from (record_notes,
# PAST_SOURCE) -- are documents.py's (20 November 2026). Each name is here as
# before.
from documents import (DOCKET_SOURCE, J_DECIDED_ACT, PAST_SOURCE, ROW_NAMES_ANOTHER, _cite,  # noqa: E402,F401
                       _docket_as_entered, _long_day, _with_plain, bill_documents, bill_text_url,
                       journal_decided_story, journal_story, record_notes)


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


# A BILL'S DOCKET LINES AND THE STAGES ITS HISTORY TELLS -- the routine rows
# (is_routine), the days it was acted on (action_dates, carried_over), the stages
# told (stages_told), the lines its page lists (docket_lines), the status box once
# a term has closed (settled_step) and its chapter (chapter_of) -- are
# docket_told.py's (20 November 2026). Each name is here as before.
from docket_told import (CALLED_OFF_KINDS, CANCELLED_NOT_TOLD, CANCELLED_ROW_NOT_TOLD, CLERKS_NOTE,  # noqa: E402,F401
                         ENROLLED_NOT_TOLD, ENROLLED_SAID, PENDING, ROUTINE, STEP_CLAIM,
                         action_dates, called_off, carried_over, chapter_of, docket_lines,
                         enrolled_untold, is_routine, listed_line, marked_cancelled, settled_step,
                         stages_told)


# The docket line an event was read from (docket_line) is parts.py's, for the
# same reason.
from parts import docket_line  # noqa: E402,F401


# WHAT MAIN ADDS TO THE BILLS' PAGES AFTER THE LOOP -- the related bills
# (add_related), the same number in other terms under a standing note
# (bill_note, add_same_number) and the tags (site_tagging) -- is related.py's
# (20 November 2026). Each name is here as before.
from related import (RELATED_GROUPS, RELATED_MAX, add_related, add_same_number, bill_note,  # noqa: E402,F401
                     check_notes, related_entries, same_number_rows, site_tagging)


def stated_status_pages():
    """bill_status.json, the General Court's status pages, {term: {bill: record}}
    (or one term's, not keyed), or {} where it is not here; and the line the
    build says of how many bills it covers. A step of build_bills, lifted out of it as it stood (20 November 2026)."""
    status_pages = load("bill_status.json", {})
    if status_pages:
        n = (sum(len(v) for v in status_pages.values())
             if P.term_keyed(status_pages) else len(status_pages))
        terms = (", ".join(sorted(status_pages)) if P.term_keyed(status_pages)
                 else "one term, not keyed")
        print(f"stated status available for {n:,} bills ({terms})")
    return status_pages


def sponsor_pool(legs, former, links, numbers):
    """Everyone a bill's sponsor lookup can name, {id: member}: the sitting members
    (`legs`) and the former ones, then under the numbers a sitting member voted
    under in the other chamber (`links`, member_links') and the employee numbers
    of the register (`numbers`), each only where the person is one the site has
    a page for. The comments below say why each. A step of build_bills, lifted out of it as it stood (20 November 2026)."""
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
    return _people


def members_who_left(term_rosters, former):
    """The former members by name, for a term whose own roster is frozen and for the
    term still sitting (bill_sponsor_list says why): (by sort name, by name key),
    each a list of every member of that name in order, or None where there is no
    frozen roster and no former member; and `term_rosters`, {} where None was
    given. A step of build_bills, lifted out of it as it stood (20 November 2026)."""
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
    return _left, term_rosters


def hearing_speakers(legs, former, term_rosters):
    """The members a Senate hearing report's speakers are resolved among
    (speaker_index): every sitting and former member, and for each term whose
    own roster is frozen, that roster and the members who left before it was.
    A step of build_bills, lifted out of it as it stood (20 November 2026)."""
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
    return _hr_idx, _hr_term


def early_sponsor_parties(id_parties, bills, current, sponsors, _people, leg_by_sort,
                          leg_by_name, seats, _left, term_rosters, record_chambers):
    """The parties a 1989-1998 sponsor placed on a page takes (party_record), drawn
    from the labels of their bills of 1999 on exactly as build_bills' loop will
    draw them, or None where no `id_parties` is given. A step of build_bills, lifted out of it as it stood (20 November 2026)."""
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
    return _parties


def status_record(status_pages, b, bid, term, current, own):
    """The status page's record of bill `bid` of `term`, each field it leaves blank
    filled from the bill's own record (`b`), or that record's fields for an
    archived term the file does not hold. `own` is whether `term` is the current
    one. A step of build_bills' loop, lifted out of it as it stood (20 November 2026)."""
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
    return st


def status_source_of(disp, status, settled, told, b, ev):
    """Where a bill's status is from, in the words the page says it: the House
    Journal, the General Court docket, its database, its bill status page, the
    docket read where nothing states it, or a CACR's ballot row. `disp` is
    bill_disposition's answer and `status`, `settled` and `told` its fields; `ev`
    the bill's docket rows not cancelled. A step of build_bills' loop, lifted out of it as it stood (20 November 2026)."""
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
    return status_source


def journey_told(narr, bid, rcs, chapter, dl, term, bill_texts, current, ballot):
    """How it got here, from the docket, for bill `bid` of `term`: (untold, btext,
    intro, jsteps, voters) -- the docket rows the journey leaves untold, the
    bill's text (bill_text_block, read here because a law's own Effective Date
    lines date its Law stop), the day it was introduced and the journey's steps
    (journey), with a CACR's voters' line where its ballot row has the answer the
    docket lacks, and the card its Votes tab draws for the voters (ballot_card),
    or None. `dl` is the bill's line of the chapters (extract_chapters), `ballot`
    its ballot_results.json row or None. A step of build_bills' loop, lifted out of it as it stood (20 November 2026)."""
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
    return untold, btext, intro, jsteps, voters


def row_sponsors(row, prime, sp_list, term, current, sponsors, _shared_names, people):
    """The index row's sponsors past the prime: a prime sponsor placed on a person
    with no page keyed on their full name (sponsor_person), the co-sponsors by
    the name the Sponsor filter groups on (cosp), and everyone the row names
    noted in `people` for the term's list (sponsor_roster). Fills `row`,
    `_shared_names` ({term: full names two employee numbers share}, read once a
    term) and `people`. A step of build_bills' loop, lifted out of it as it stood (20 November 2026)."""
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


def unenrolled_rows(story, narr, kind, row, ev, intro, dates):
    """The docket's "Enrolled" rows of a bill a chamber ended (enrolled_untold), the
    chamber that ended it, and the days the bill was acted on without those rows:
    (unenrolled, ended_in, dates), with the row's last action and carried-over
    mark taken again from those days. [] and "" and `dates` as given for every
    other bill. A step of build_bills' loop, lifted out of it as it stood (20 November 2026)."""
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
    return unenrolled, ended_in, dates


def index_tags(row, tagging, term, bid):
    """The bill's tags, {id: why} from site_tagging's answer, or None; the index row
    gains them as their places in meta.json's list. A step of build_bills' loop, lifted out of it as it stood (20 November 2026)."""
    # THE BILL'S TAGS, as their places in meta.json's list (site_tagging),
    # only on a bill that has one: the up-front index grows by a few
    # digits a tagged bill, and by nothing without a registry.
    bill_tags_ = ((tagging or {}).get("bills") or {}).get((term, bid))
    if bill_tags_:
        row["tags"] = [tagging["at"][t_] for t_ in bill_tags_]
    return bill_tags_


def rail_drawn(story, row, narr, jsteps, intro, bid, kind, status, term, current, own,
               session_over, sittings, lsrs, ending, table_ends, j_tally, j_current):
    """The bill's rail and its endings: (ending, jrail, srep) -- the closing
    paragraph, now with a death on the table or in interim study where the rail
    ends there (session_endings); the rail's dated stops (journey_rail), whose
    copy the index row takes (index_rail); and what the committee reported on a
    bill held for interim study (study_report), or None. Counts the journey
    against the status and the rail in `j_tally` and `j_current`
    (journey_disagrees), and takes the words off the journey's and the rail's
    stops, which the page says itself. A step of build_bills' loop, lifted out of it as it stood (20 November 2026)."""
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
    return ending, jrail, srep


def reports_and_documents(b, bid, st, narr, sources, reports, term, story):
    """A bill's committee reports and the documents a reader can open:
    (rep_written, rep_docket, rep_actions, docs, text_url) -- the reports dated
    and in order, the Senate's beside the House's (committee_reports), and the
    documents deduped on the address with the bill's own text's (bill_documents),
    with the journals a House Journal record cites (`story`, journal_story's).
    A step of build_bills' loop, lifted out of it as it stood (20 November 2026)."""
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
    return rep_written, rep_docket, rep_actions, docs, text_url


def rollcalls_named(rc_out, bid, term, _mpool, _mpages, rep_written, rc_cards):
    """Each roll call of the bill (`rc_out`, bill_rollcalls') in the approved words
    of its motion (motions.classify), with the chair's ruling where the Journal
    states it and its mover as the person among the term's members (`_mpool`,
    mover_pool's); each committee report's author likewise (report_authors);
    and where each roll call's card is on the bill's Votes tab, for the session
    days (`rc_cards`). A step of build_bills' loop, lifted out of it as it stood (20 November 2026)."""
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


def stations_drawn(bid, term, procs, segs, marks, narr, tdb, floor, hearing_reports, _hr_term,
                   _hr_idx, _hr_name, hr_tally, hr_unmatched, _people, video_facts, moments):
    """The stations a bill's Hearings tab draws, in date order: its committee
    sittings (bill_stations) less a notice the bill's own record says no
    committee held (proceedings.notice_only), with the sign-ins of each hearing
    and the Senate's hearing reports on theirs (attach_hearing_reports, counted
    in `hr_tally` and `hr_unmatched`), its floor appearances (station_for_floor)
    and each recording's length; and each floor station's moment, for the
    session day's card (`moments`). A step of build_bills' loop, lifted out of it as it stood (20 November 2026)."""
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
    return stations


def count_stations(stations, station_states, station_kinds):
    """The census of a bill's stations, by state and kind and in the four groups a
    reader meets, into the counters write_station_census writes. A step of build_bills' loop, lifted out of it as it stood (20 November 2026)."""
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


def record_story(narr, kind, row, unenrolled, story, ending, _mpool, _mpages):
    """The record's history: (_narrative, _stages, _story_who) -- the stages' text
    run together, the stages as they are told with the closing paragraph where
    the ending is only on the status page (or a House Journal record's own), and
    the members the story names, among the term's members with the seat each
    held then (story_people), or []. A step of build_bills' loop, lifted out of it as it stood (20 November 2026)."""
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
    return _narrative, _stages, _story_who


def record_events(narr, bid, sources, tdb, testimony, own, unenrolled, ended_in):
    """The record's docket lines, each with its citation and plain words: a corrected
    date and why, an "Enrolled" row the history does not tell, a row that calls
    a meeting off or the docket cancelled, a misfiled row's note, a notice, and
    the hearing's sign-ins. A step of build_bills' loop, lifted out of it as it stood (20 November 2026)."""
    return _with_plain([{"date": e["date"], "text": listed_line(e),
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
            for e in docket_lines(narr)], bid)


def say_statuses(index, status_pages, n_stated, n_stale, n_db, current, session_over):
    """What build_bills says, after its loop, of the statuses it gave: how many the
    status page stated and how many of a closed term were marked finished, the
    chips as they were written, and what the database's dump answered. `index`
    is the loop's rows; the counts are its own. A step of build_bills, lifted out
    of it as it stood (20 November 2026)."""
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


def say_journeys(j_tally, j_current, current):
    """What build_bills says of the journeys it told against each bill's status and
    rail (journey_disagrees): `j_tally` counted per term, `j_current` this term's
    that disagree. A step of build_bills, lifted out of it as it stood (20
    November 2026)."""
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


def say_chapters(n_chapter):
    """What build_bills says of where each chapter of the session laws came from
    (chapter_of counts them). A step of build_bills, lifted out of it as it stood
    (20 November 2026)."""
    if n_chapter:
        print(f"  chapter of the session laws: {n_chapter['the status page']:,}"
              f" from the status page, {n_chapter['the docket']:,} from the "
              f"docket; {n_chapter['differ']} where the two differ (the "
              f"page's field shown), {n_chapter['withheld']} withheld")


def write_station_census(out, station_states, station_kinds, n_station_bills):
    """site/station_census.json, the stations build_bills drew counted by state and
    kind, which about.html's figures are read from (about_figures.py), and the
    line the build says of them. build_bills holds the counters, filled as each
    bill's stations are drawn; this writes them. A step of build_bills, lifted
    out of it as it stood (20 November 2026)."""
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


def say_hearing_reports(hearing_reports, hr_tally, hr_unmatched):
    """What build_bills says of the Senate's hearing reports it placed on their
    hearings (attach_hearing_reports counts them), naming the ones that found
    none. A step of build_bills, lifted out of it as it stood (20 November
    2026)."""
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
    status_pages = stated_status_pages()
    n_stated = 0
    _people = sponsor_pool(legs, former, links, numbers)
    _left, term_rosters = members_who_left(term_rosters, former)
    _hr_idx, _hr_term = hearing_speakers(legs, former, term_rosters)
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
    _parties = early_sponsor_parties(id_parties, bills, current, sponsors, _people,
                                     leg_by_sort, leg_by_name, seats, _left, term_rosters,
                                     record_chambers)
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
        st = status_record(status_pages, b, bid, term, current, own)
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
        status_source = status_source_of(disp, status, settled, told, b, ev)
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
        untold, btext, intro, jsteps, voters = journey_told(narr, bid, rcs, chapter, dl,
                                                            term, bill_texts, current,
                                                            ballot)
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
        row_sponsors(row, prime, sp_list, term, current, sponsors, _shared_names, people)
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
        unenrolled, ended_in, dates = unenrolled_rows(story, narr, kind, row, ev, intro, dates)
        bill_tags_ = index_tags(row, tagging, term, bid)
        index.append(row)
        ending, jrail, srep = rail_drawn(story, row, narr, jsteps, intro, bid, kind, status,
                                         term, current, own, session_over, sittings, lsrs,
                                         ending, table_ends, j_tally, j_current)

        # ---- one detail file per bill, loaded only when expanded
        rep_written, rep_docket, rep_actions, docs, text_url = reports_and_documents(
            b, bid, st, narr, sources, reports, term, story)

        bill_amds = bill_amendments(narr, amend_texts, claims.get(term, {}))

        rc_out = bill_rollcalls(bid, term, rcs, narr,
                                votes_by_bill, legs, unnamed, in_office)
        # Whom this term's movers are looked for among (mover_pool).
        _mpool, _mpages = mover_pool(term, current, legs, term_rosters, _people,
                                     voter_pools)
        rollcalls_named(rc_out, bid, term, _mpool, _mpages, rep_written, rc_cards)

        stations = stations_drawn(bid, term, procs, segs, marks, narr, tdb, floor,
                                  hearing_reports, _hr_term, _hr_idx, _hr_name, hr_tally,
                                  hr_unmatched, _people, video_facts, moments)
        # The census, taken after the sort so it counts exactly the list the
        # page receives -- including the floor stations, which is the half of
        # the record five tools in one day were found to be missing.
        if stations:
            n_station_bills += 1
        count_stations(stations, station_states, station_kinds)

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
        _narrative, _stages, _story_who = record_story(narr, kind, row, unenrolled, story,
                                                       ending, _mpool, _mpages)
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
            "events": record_events(narr, bid, sources, tdb, testimony, own, unenrolled,
                                    ended_in),
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

    say_statuses(index, status_pages, n_stated, n_stale, n_db, current, session_over)
    say_journeys(j_tally, j_current, current)
    say_chapters(n_chapter)

    write_station_census(out, station_states, station_kinds, n_station_bills)
    say_hearing_reports(hearing_reports, hr_tally, hr_unmatched)
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


def bills_with_topics(D):
    """data/bills.json, {term: {bill: record}}, refused in the flat shape, with each
    bill's topic: the General Court's own subject code for the archive
    (official_topics), the topic model's for the terms it gave none
    (merge_guessed_topics), and the site's one vocabulary over all of them, last
    (unify_vocabulary). `D` is the data folder. A step of main's loading, lifted out of it as it stood (20 November 2026)."""
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
    return bills


def sponsors_merged(D, bills):
    """data/sponsors.json with the sponsors each bill's own text names where the
    database names nobody (text_sponsors.merge_into), 2023-2024 from the General
    Court's own sponsor record and every other past term filled from it
    (past_sponsors.merge_into), and the seats dated from the bill's own printed
    line (text_sponsors.seat_into), in that order. A step of main's loading, lifted out of it as it stood (20 November 2026)."""
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
    return sponsors


def sitting_roster(D):
    """The sitting members, {id: member}, from data/legislators.json, and the two
    lookups a sponsor is joined to them by (roster_name_keys), with a warning for
    two members one key names. A step of main's loading, lifted out of it as it stood (20 November 2026)."""
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
    return legs, leg_by_sort, leg_by_name


def dockets_and_rollcalls(a, bills):
    """The histories (narratives.json), the standing notes
    (corrections/bill_notes.json, held to the bills by check_notes) and the roll
    calls (rollcalls.json), each refused in the flat shape, with a roll call on
    no bill drawn under the bill whose debate it divided, limited or called the
    question of (vote_passage.move_on_bills, whose map of them is MOVED_TO_BILL).
    `a` is the parsed arguments. A step of main's loading, lifted out of it as it stood (20 November 2026)."""
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
    return narratives, notes, rollcalls, MOVED_TO_BILL


def committee_records(a, narratives):
    """The committee reports, the House's corrected from the committee's filed copy
    (report_check) and the Senate's merged in, with each committee's interim
    study statement (interim_cards); the veto messages; the chapters of the
    session laws (extract_chapters); and the Senate's reports of its public
    hearings: each {term: {bill: ...}}, refused in the flat shape, and each said.
    A step of main's loading, lifted out of it as it stood (20 November 2026)."""
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
    return reports, vetoes, chapters, hearing_reports


def main():
    a = parse_args()

    D, out = Path(a.data), Path(a.out)
    (out / "bills").mkdir(parents=True, exist_ok=True)
    (out / "legislators").mkdir(parents=True, exist_ok=True)

    bills = bills_with_topics(D)
    sponsors = sponsors_merged(D, bills)
    legs, leg_by_sort, leg_by_name = sitting_roster(D)

    # Members who left mid-term are already named upstream: resolve_members.py
    # writes former_members.json to the project root, build_data.py reads it
    # there, and every member_votes row therefore carries a resolved "name"
    # whether the member is sitting or not. That is what the double build_data
    # pass in build_all.py exists for. Reading the file a second time here
    # would only add a way for the two to disagree -- and the copy this looked
    # for, under the data directory, is not where the pipeline writes it.
    towns = load(D / "towns.json", {})
    narratives, notes, rollcalls, MOVED_TO_BILL = dockets_and_rollcalls(a, bills)
    reports, vetoes, chapters, hearing_reports = committee_records(a, narratives)
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
