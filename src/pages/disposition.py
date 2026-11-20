#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
What became of a bill, and where that answer came from: its disposition
(bill_disposition, which answers a Disposition), read from the status page's
fields, the docket's own decisions, the database where both say nothing, a
CACR's ballot and the House Journal; the chamber it started in (origin_of);
the record's own name for a stage it stopped at (STAGE_STATED,
stated_stage); a measure of a finished term that cannot still be moving
(ENDING_NOT_ON_RECORD to ENDED_WITH_TERM, ended_with_the_term); and the test
that the journey, the status and the rail tell one story
(journey_disagrees).

    import disposition as DSP
    d = DSP.bill_disposition(b, bid, st, narr, rcs, term, current)
    d.kind, d.status, d.source

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md section 5). It moved here as it stood,
comments and all, nothing inside it edited, in eight
pieces in the file's order: origin_of; journey_disagrees with the comment
above it; Disposition with its comment; STAGE_STATED and stated_stage;
SECOND_ADOPTED; DIED_ON_TABLE_ROW; the section "a measure of a finished
term cannot still be moving" to ENDED_WITH_TERM; ended_with_the_term and
bill_disposition. The comments above the imports of TABLE_DEATH (parts.py)
and of conference_not_taken_up (conferences.py), which name what they
import, stay in build_site_v2 with the imports. A bill's status words are
status.py's, the journey journey.py's, what the chambers did with each
other's version conferences.py's, a CACR's ballot cacr_ballots.py's, a
record's source documents.py's and a clerk's note docket_told.py's.
It imports no builder (_import_cycles_cut). build_site_v2 imports every
name here back under its own, so build_site_v2.<name> answers as it did, for
build_bills, main and the checks.
"""

import re
from collections import namedtuple

from cacr_ballots import TO_THE_VOTERS, cacr_to_the_voters
from conferences import (CHAMBERS_APART, CONF_UNABLE, ENDED_AS, between_chambers,
                         conference_not_taken_up)
from docket_told import CLERKS_NOTE
from documents import PAST_SOURCE
# The lines the session's end makes (session_end_line), which journey_disagrees reads.
from endings import session_end_line
from journey import J_ENDING, J_PASSING, journey, journey_state
from parts import NO_GOVERNOR, SINGLE_CHAMBER, TABLE_DEATH, bill_prefix
from status import (DISPOSED, JOURNAL_SOURCE, classify, classify_stated, docket_outcome,
                    floor_disposed, journal_not_introduced, last_decision, veto_votes)


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


# `between` is true where a dated docket line between the chambers decided
# the status over the fields (between_chambers and the two rules beside it),
# so status_source can say the docket did.
#
# `source` is JOURNAL_SOURCE where the status is the House Journal's, for a
# bill the General Court's files do not carry; "" otherwise.
Disposition = namedtuple("Disposition",
                         "kind status told settled prefix stated stale between source",
                         defaults=(False, ""))


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


# A resolution the second chamber adopted says so in the docket even where its
# status field does not: HCR 6 of 1990, "S INTRODUCED AND ADOPTED" the day the
# House adopted it, and SCR 3 of 1996, "H ADOPTED DIV(178-116)".
SECOND_ADOPTED = re.compile(r"^\s*(?:introduced and )?adopted\b", re.I)


# AND THE HOUSE'S OWN CLOSING ROW. The House laid 26 measures of 2015 on the
# table and entered "Died on the Table" on each on 18 November 2015; its field
# for them was never advanced from LAID ON TABLE, a field outranks what
# classify() reads in the docket, and they read "Laid on the table" over a
# last row that says they died there.
DIED_ON_TABLE_ROW = re.compile(r"^\s*died\s+on\s+(?:the\s+)?table\b", re.I)


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
