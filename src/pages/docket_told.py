#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
A bill's docket lines and the stages its history tells: the rows that are
procedural bookkeeping (ROUTINE, is_routine); the days a bill was acted on,
a clerk's note left out (CLERKS_NOTE, action_dates), and whether it was
carried over (carried_over); the "Enrolled" rows the history does not tell
and its stages without them (enrolled_untold, stages_told); a row that calls
a meeting off (called_off, marked_cancelled); the lines the bill's page
lists (listed_line, docket_lines); the status box once a term has closed
(settled_step); and the chapter of the session laws a bill became
(chapter_of).

    import docket_told as DT
    DT.docket_lines(narr)
    DT.stages_told(narr, kind, rail)

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md section 5). It moved here as it stood,
comments and all, nothing inside it edited, in four
pieces in the file's order: ROUTINE with its comment; is_routine; CLERKS_NOTE
to stages_told; listed_line to chapter_of. The comment above the import of
docket_line (parts.py's), between the last two, stays in build_site_v2 with
the import. It imports no builder (_import_cycles_cut). build_site_v2 imports every
name here back under its own, so build_site_v2.<name> answers as it did, for
build_bills, main and the checks.
"""

import re


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


def is_routine(text):
    return bool(ROUTINE.search(text or ""))


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
