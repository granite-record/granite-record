#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.18
"""
Parse the NH General Court Docket.txt bulk dump into normalized "scheduled
proceedings" -- the input to video alignment.

Source: https://gc.nh.gov/dynamicdatadump/Docket.txt  (pipe-delimited, no header)

Field layout (positional, inferred -- see VERIFY notes in the design doc):
  0  lsr_year     pairs with field 1 to form the LSR id. NOT reliably the
                  session year: SB11 -> 2025 and SB15 -> 2026 were both
                  introduced 01/08/2025.
  1  lsr_number   zero-padded 4 digits
  2  created      timestamp the docket row was written
  3  bill         e.g. HB84, SB4, CACR2, HR6
  4  body         H | S
  5  description  free text, the only place scheduling data lives
  6  updated      timestamp the row was last modified
"""

import csv
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, time
from pathlib import Path

# --------------------------------------------------------------------------
# Description grammar
# --------------------------------------------------------------------------

# ==CANCELLED==, ==RECESSED==, ==ROOM CHANGE==, ==TIME CHANGE== ...
FLAG_RE = re.compile(r"==\s*([A-Z][A-Z ]*?)\s*==")

# House:  "Public Hearing: 01/13/2025 10:30 am LOB 301-303"
#         "Executive Session: 01/23/2025 01:40 pm LOB 301-303"
#         "Subcommittee Work Session: 01/22/2025 01:15 am LOB 302-304"
# THE DEFECT WAS THE $ ANCHOR, NOT THE MERIDIEM. The old pattern ended
# `...(?:venue)?(?:cite)?\s*$`, which made the venue class responsible for
# absorbing every word the clerk appended after the room. When it could not --
# a colon, a slash, a parenthesis, an "=" -- the WHOLE line failed and fell
# through to LEGACY_SCHED_RE below, which is the 1989-1998 pattern: it
# hardcodes kind="hearing" and puts everything after the bare HH:MM into the
# venue. That is how "a.m. LOB305-307" became a room and a Zoom paragraph
# became a room.
#
# 1,062 modern House lines were being read that way -- 1,029 of them in
# 2021-2022. Measured over those real lines: allowing dots in the meridiem
# rescues 288 of them; dropping the anchor rescues 1,061; making the colon
# optional takes it to 1,062.
#
# 742 of the 1,062 are the 2020-21 remote hearings, whose line states no room
# at all -- it states a Zoom link. Printing nothing there is the right answer,
# and printing the link as a room was the bug.
#
# The meridiem, every way the six modern dockets write it. Counted, not
# assumed: am 13,843 / AM 6,199 / pm 7,225 / PM 3,548 / a.m. 393 / p.m. 181.
HOUSE_MER = r"[ap]\s?\.?\s?m\.?"

HOUSE_SCHED_RE = re.compile(
    r"(?P<kind>Public Hearing|Executive Session|Subcommittee Work Session|"
    r"Full Committee Work Session|Work Session|"
    # THE HOUSE'S CONFERENCE NOTICE, AS THE HOUSE WORDS IT. The pattern knew
    # the bare "Committee of Conference", which the House clerk has never
    # written before a date, so of the House's conference notices only the
    # 1989-2006 shorthand LEGACY_SCHED_RE reads ever arrived: 927 lines across
    # eleven terms were read by nothing, 113 of them in the current term's
    # docket, while the Senate's, which SENATE_SCHED_RE reads, all arrived.
    # Every House conference card on the Calendar was the recording's alone:
    # untimed and with no room, beside a Senate one carrying both.
    # Each wording below was read off a real line, and each clerk's years:
    #   "Conference Committee Meeting: 06/16/2025 09:30 am LOB 206-208"
    #                                                   HB 485, 2010-2026
    #   "Committee of Conference Meeting: 6/18/07 2:00 PM LOB 207"
    #                                                   HB 37, 2007-2014
    #   "Conference of Committee Meeting: 5/27/2014; 11:00 AM; LOB 207"
    #                                                   HB 1488, 2014
    #   "Committee of Conference Hearing: 05/29/2008 11:30 AM LOB 304"
    #                                                   HB 1405, once
    #   "Conf Comm meeting 6/15/01 1:30 p.m. Rm 202, LOB"  HB 170, 2001
    # "Meeting" is required after the short forms, which is what keeps out
    # "Conference Committee Report 2025-2766c: Adopted" and "Conferee Change";
    # a date must follow, which keeps out "Accedes to Senate Request for
    # Committee of Conference (Rep Hinch): MA VV (in recess of 5/12/2016)".
    r"Committee\s+of\s+Conference(?:\s+(?:Meeting|Hearing))?|"
    r"Conf(?:erence)?\.?\s*Comm?(?:ittee)?\.?\s+Meeting|"
    r"Conference\s+of\s+Committee\s+Meeting)"
    # A colon, or a space, or both. "Continued Public Hearing:1/23/2014"
    # writes the colon and no space; "Second Public Hearing 02/14/2024"
    # writes the space and no colon. `\s*:\s*` read neither.
    r"(?:\s*:\s*|\s+)"
    # The year must not run into another digit. One 2015 row reads
    # "Continued Executive Session: 4/30/20105", and \d{4} alone reads that as
    # 30 April 2010 and files the sitting in the wrong term.
    # \d{2,4}, because the 2007-2008 docket writes the colon form with a
    # two-digit year and \d{4} refused the whole of it: "Executive Session:
    # 5/15/07 1:00 PM LOB 302" is 994 rows, "Retained Bill - Executive
    # Session: 11/14/07 10:00 AM LOB 208" another 501.
    r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4})(?!\d)"
    # Seconds because the 2007-08 docket writes "1:30:00 PM"; the meridiem in
    # its own group so a line that states none -- "02/15/2022 1:45 LOB302-304",
    # one line on this disk -- still gives up its kind, date and room without
    # anybody inventing an am or a pm.
    # A SEMICOLON MAY SEPARATE THEM. 46 conference notices of 2013-2014 write
    # "5/27/2014; 11:00 AM; LOB 207", and without it the time went unread and
    # the room was cut off at the first semicolon, which house_venue takes for
    # the start of the clerk's prose. Measured over every docket on this disk,
    # no House line of any other kind reads differently for it.
    r"(?:;?\s+(?P<time>\d{1,2}:\d{2})(?::\d{2})?"
    r"(?:\s*(?P<mer>" + HOUSE_MER + r"))?;?)?"
    # A stated END time: "6:00 PM - 8:00 PM Kennet High School Auditorium".
    r"(?:\s*-\s*\d{1,2}:\d{2}\s*(?:" + HOUSE_MER + r")?)?"
    # Deliberately NOT anchored. What follows is handed to house_venue below,
    # which decides where the room ends rather than making the match depend on
    # it.
    r"(?P<rest>.*)$",
    re.IGNORECASE,
)

# Where the room ends and the clerk's prose begins. Every alternative was read
# off a real line: 720 lines carry a Zoom paragraph, 14 end "=RECESSED=", 8 add
# "(exec. session may follow)", 4 are off-site addresses, 2 cite a non-germane
# amendment, and the rest are one-offs.
HOUSE_TAIL_RE = re.compile(
    r"\s*(?:"
    r"=+\s*[A-Za-z][A-Za-z &.,'\d/()-]*?\s*=*\s*$"
    r"|\("
    r"|\["
    r"|;"
    r"|\*"
    r"|\bMembers\s+of\s+the\s+public\b"
    r"|\bPlease\s+click\b"
    r"|\bTo\s+join\s+the\s+webinar\b"
    r"|https?://"
    r"|\bExecutive\s+session\s+on\s+pending\s+legislation\b"
    r"|\bCONTINUED\s+FROM\b"
    r"|\bPublic\s+Hearing\s+on\s+non-germane\b"
    # The journal citation the old pattern had its own group for:
    # "LOB 210-211 HC 19 P. 16" is a room, then House Calendar 19 page 16.
    # A letter may follow the number -- "HC 45A" is House Calendar 45A -- and
    # \d+\b refuses it, because there is no word boundary between "5" and "A".
    # Six 2023-2024 rows carried "LOB 202-204 HC 45A" as their room because of
    # it; the defect predates the legacy reorder that made it visible.
    r"|(?:HC|SC|HJ|SJ)\s+\d+[A-Za-z]?\b"
    r").*$", re.I | re.S)

# What is left has to look like a room before it is published as one. The
# longest venue the old pattern produces across every docket on this disk is
# 68 characters ("Silver Center for the Arts at Plymouth State University -
# Plymouth NH"), so the cap is 80 and nothing already published reaches it.
HOUSE_VENUE_OK = re.compile(r"^[A-Za-z0-9\-][A-Za-z0-9 ,.'&\-]{0,79}$")


def house_venue(rest):
    """The room this line states, or None if it states none."""
    v = HOUSE_TAIL_RE.sub("", rest or "").strip()
    # A MERIDIEM IS NOT A ROOM. One row states the half of the day and no
    # clock time at all -- "Subcommittee Work Session: 3/21/2007 PM LOB 208
    # During House Session Lunch Break" -- so the time group matches nothing
    # and the "PM" falls through to here. The room is what follows it.
    v = re.sub(r"(?i)^\s*[ap]\s?\.?\s?m\.?\b[\s,.]*", "", v)
    return v if v and HOUSE_VENUE_OK.match(v) else None


def house_kind(raw):
    """The legacy line's kind word as VIDEO_KINDS spells it.

    The legacy branch used to hardcode "hearing", because the pattern could
    only match that word. It now reads six families across seventy spellings --
    "SUBCOM WORK SESSION", "Fin Div II Subcom Work & Exec Session", "CONF COMM
    MEETING", "RE-REF SUBCOM WORK SESSION" -- and handing any of those through
    unchanged would drop the row at the VIDEO_KINDS test a few lines later,
    which looks exactly like the pattern having failed.

    Order matters here: a subcommittee work session names both "subcom" and
    "work session", and it is the former that makes it the more specific kind.
    """
    k = re.sub(r"\s+", " ", (raw or "")).strip().lower()
    if "conf" in k:
        return "committee of conference"
    if re.search(r"\bsubcomm?", k) or "re-ref subcom" in k:
        return "subcommittee work session"
    if re.search(r"\bcomm(?:ittee)?\b", k) and "sess" in k:
        return "full committee work session"
    if "exec" in k and "sess" in k and "work" not in k:
        return "executive session"
    if "sess" in k:
        return "work session"
    if "public" in k and "hear" in k:
        return "public hearing"
    if "hear" in k:
        return "hearing"
    return k


def house_time(m):
    """The time to hand to _parse_time, or None where no meridiem is stated."""
    if not m.group("time") or not m.group("mer"):
        return None
    return (m.group("time") + m.group("mer")).replace(" ", "").replace(".", "").upper()

# Senate: "Hearing: 01/14/2025, Room 103, LOB, 09:30 am;  SC 5"
#
# THIS WAS A PATTERN FOR ONE DECADE'S WORDING, AND THE SENATE HAS USED FOUR.
# It matched zero lines in every docket from 1999 to 2014 -- 9,732 Senate
# scheduling lines, none of them read -- so hearings for seven terms were
# absent from the site, and with them the committee pages: across all 53 files
# in site/committee/ there was not one session dated 1999 through 2014.
#
# The failures are not near-misses. Every one of those lines breaks at least
# two clauses at once, which is why no single relaxation ever rescued
# anything: fixing the separator and the date and leaving [ap]m alone still
# yields zero. Measured, as a cumulative ladder over the real lines:
#
#     today                           0      + month-name date         1
#     + separator ; , or none         0      + dotted a.m./p.m.    5,802
#     + two-digit year                0      + loose venue         7,122
#
# The dots are the universal one. Of 9,732 real lines, 9,704 write "a.m." or
# "p.m."; only 28 write the bare "am" this pattern required.
#
#     1999-2000   Hearing, 3/18/99, Room 104, LOB, 2:10 p.m.
#                 Hearing March 21, Room 104, LOB, 3:30 p.m.   <- no year
#     2001-2010   Hearing; May 23, 2001, Room 103, SH, 10:45 a.m.; SC24
#     2011-2015   Hearing: 3/29/11, Room 102, LOB, 10:00 a.m.; SC17
#     2016-       Hearing: 01/14/2025, Room 103, LOB, 09:30 am;  SC 5
#     remote      Remote Hearing: 04/12/2021, 09:50 am; Links to join the
#                 hearing can be found in the Senate Calendar; SC 19
#
# HEAD-ANCHORED, which the House pattern deliberately is not. 16,560 of the
# matched lines open with the kind word and the rest carry one of five known
# prefixes, so the anchor declines outright -- rather than by luck -- the two
# families that name a sitting mid-sentence and are not one: "Sen. Gray
# Accedes to House Request for Committee of Conference" (442 rows) and "Rules
# Suspension 2/3 nec.; For Intro., Referring, Hearing, and Committee Report".
#
# `mid` MAY NOT CONTAIN A DIGIT, which is what guarantees the date read is the
# first one after the kind word, so no run of noise can step over one date on
# to another. All 47 distinct values it takes were printed and read; every one
# is punctuation or a flag residue, none is a fact.
SENATE_MER = r"[ap]\s?\.?\s?m\.?"
MONTH_WORD = (r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
              r"[a-z]*\.?")

SENATE_SCHED_RE = re.compile(
    r"^[\s,=]*"
    r"(?:[A-Za-z][A-Za-z ]*=+\s*)?"
    r"(?P<pre>(?:(?:Re-?scheduled|Cancell?ed|Continued|Joint|Postponed)\s+)*)"
    r"(?P<kind>Remote\s+Hearing|Public\s+Hearing|Hearn?ings?"
    r"|Executive\s+Session|Exec\.?\s*Session|Work\s*Session"
    r"|(?:Committee\s+of\s+Conf\w*|Conf(?:erence)?\.?\s*Comm\w*|C\s+of\s+C)"
    r"(?!\s*Report))"
    r"(?:\s+on\s+Re-?referred\s+Bill)?"
    r"(?:\s*[;:,]?\s*Meet\w{0,3}ing)?"
    r"(?P<mid>(?:=+[^=]{0,30}=+|\{\d+\}|[^\d]){0,48})"
    r"(?P<date>\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4}"
    rf"|{MONTH_WORD}\s*\d{{1,2}}\s*,?\s*\d{{4}}"
    rf"|{MONTH_WORD}\s*\d{{1,2}})(?!\d)"
    r"(?P<between>.{0,110}?)"
    # THE FIRST TIME OF A RANGE, NOT THE LAST. The meridiem sits after the
    # whole range -- "6:00 - 9:00 p.m." -- so without somewhere for the second
    # half to go the engine backtracks and reads 9:00 as the start. It is only
    # five rows, and all five are the HB1 and HB2 budget hearings, which are
    # among the most-read pages on the site. A wrong time is worse than none.
    r"(?P<time>\d{1,2}:\d{2})(?::\d{2})?\s*"
    r"(?:[-–]\s*\d{1,2}:\d{2}(?::\d{2})?\s*)?"
    r"(?P<mer>" + SENATE_MER + r")"
    r"(?P<rest>.*)$",
    re.IGNORECASE,
)

# THE BUILDING IS THE ANCHOR, NOT THE ROOM, and the venue is a helper rather
# than a group for the reason HOUSE_SCHED_RE's own comment gives: a venue class
# that has to match before the line can match is a venue class that loses whole
# hearings. The building is a closed set the Senate has used since 1999; the
# room is whatever precedes it, spelt Room, Rooms, Roon, Rom or Rm, or absent
# entirely on the 41 rows reading "Map Room, SL" and the 44 reading
# "Representatives' Hall, SH". The comma is optional -- 57 rows turn on that.
SENATE_VENUE_RE = re.compile(
    r"(?:Rooms?|Roon|Rom|Rm)?\.?\s*"
    r"(?P<room>[A-Za-z0-9][\w .'’/&\-]{0,38}?)\s*(?:[,.;]\s*|\s+)"
    r"(?P<bldg>LOB|SH|SL|GP|State\s+House|Legislative\s+Office\s+Building)\b",
    re.I)
SENATE_VENUE_REV_RE = re.compile(      # "1:30 PM LOB 101", "Room, LOB 102"
    r"(?:Rooms?|Rm)?\s*[,.]?\s*"
    r"(?P<bldg>LOB|SH|SL|GP|State\s+House)\s*[,.]?\s*(?P<room>\d[\w\-]{0,10})",
    re.I)
SENATE_HALL_RE = re.compile(
    r"(Representatives?'?s?\s+Hall|Rep'?s\s+Hall|Reps'?\s*Hall)", re.I)


def senate_venue(between, rest):
    """Where the clerk actually puts the room, or None where there is none.

    A hearing states the room between the date and the time; a committee of
    conference states it after. None is a real answer and is given for all 457
    remote hearings of 2019-2022: not one of those lines contains Room, LOB, SH
    or Hall, because the sitting had no room -- the line says the links are in
    the Senate Calendar. Writing "Remote" or "Zoom" there would be inventing a
    venue the record does not state.
    """
    for span in (between or "", rest or ""):
        if not span:
            continue
        h = SENATE_HALL_RE.search(span)
        if h:
            return re.sub(r"\s+", " ", h.group(1)).strip()
        v = SENATE_VENUE_RE.search(span) or SENATE_VENUE_REV_RE.search(span)
        if v:
            room = re.sub(r"\s+", " ", v.group("room")).strip(" .,;")
            # The room word again, because the group is lazy and the engine
            # would rather leave the optional prefix unmatched than consume it.
            # Without this the venue reads "SH Room 103" where every other
            # venue on the site reads "LOB 302", and a venue string that is
            # spelt two ways is two venues to anything comparing them.
            room = re.sub(r"^(?:Rooms?|Roon|Rom|Rm)\b\.?\s*", "", room, flags=re.I)
            bldg = re.sub(r"\s+", " ", v.group("bldg")).strip().upper()
            # The clerk writes the same two buildings four ways -- "SH" and
            # "State House" are one building, 310 rows against 809 in
            # 1999-2010 alone. Left alone they are two venues to anything
            # grouping or comparing them, which is what a committee page does.
            bldg = {"STATE HOUSE": "SH",
                    "LEGISLATIVE OFFICE BUILDING": "LOB"}.get(bldg, bldg)
            return f"{bldg} {room}".strip() if room else bldg
    return None


def senate_kind(raw):
    """The kind word as VIDEO_KINDS spells it.

    Handing it through unchanged is a silent cliff: "remote hearing" is not in
    VIDEO_KINDS, so all 457 remote rows would match the pattern and then be
    dropped at the kind test a few lines later, which looks exactly like the
    pattern having failed. Same for "c of c" (100 rows) and the clerk's three
    one-off misspellings -- Hearning, Worksession, Committe.
    """
    k = re.sub(r"\s+", " ", (raw or "")).strip().lower()
    k = re.sub(r"^(?:remote|public|joint)\s+", "", k)
    if k.startswith(("c of c", "conf")) or "conference" in k or "committe" in k:
        return "committee of conference"
    if k.startswith("hear"):
        return "hearing"
    if "work" in k:
        return "work session"
    if k.startswith("exec"):
        return "executive session"
    return k

# THE ARCHIVE'S OWN SHORTHAND, 1989-1998.
#
#   HEARING   02/08/89       10:00 REP HALL  FOR: EXEC DEPTS & ADM
#   HEARING MAR17 08:30 RM101,LOB    FOR: TRANSPORTATION
#   RESCHEDULED HEARING 3/06/90 10:00  RM209LOB FOR: EDUCATION
#   COMMERCE HEARING SECS.5-14 MAR24 01:30 RM207,LOB
#
# 15,401 lines mention a hearing across those ten terms and 14,836 carry a
# date and a time -- 96%. Nothing else on this disk has them: the calendars
# start in 1997 and the video starts in 2020, so for eight of these ten terms
# this line is the only record that a bill was ever heard.
#
# A DATE AND A TIME MUST FOLLOW THE WORD, which is what keeps "SEN RUSSMAN
# SUSP RULES FOR HEARING, MA 2/3VV; SJ15,P371" from becoming a hearing.
# HEARING WAS NEVER THE ONLY WORD. Requiring the literal made every
# subcommittee, division and conference sitting of 1989-2006 invisible --
# counted over the lines nothing claimed: SUBCOM WORK SESSION 4,984,
# SUBCOMMITTEE WORK SESSION 1,066, EXECUTIVE SESSION 1,003, CONF COMM MEETING
# 709, RE-REF SUBCOM WORK SESSION 636, CONFERENCE COMMITTEE MEETING 467.
#
#     SUBCOM WORK SESSION OCT04 09:00 RM211,LOB    FOR: M&CG
#     Fin Div II  Subcom Work & Exec Session  Jan 27   1:30   RM209,LOB
#     Conf Comm meeting  June 30  8:30  Rm301,LOB
HOUSE_KIND = (
    r"(?P<kind>"
    r"(?:Subcomm?(?:ittee)?|Comm(?:ittee)?)\s*"
    r"(?:Work|Wk)\s*(?:&|and)?\s*(?:Exec\w*\s*)?Sess\w*"
    r"|(?:Work|Wk)\s*(?:&|and)?\s*(?:Exec\w*\s*)?Sess\w*"
    r"|Exec(?:utive)?\.?\s*Sess\w*"
    r"|(?:Public\s+)?Hearings?(?:\s+on\s+Prop\w*(?:\s+Am\w*)?)?"
    r"|(?:Conf(?:erence)?\.?\s*Comm\w*|Committee\s+of\s+Conference)"
    r"(?!\s*Report)(?:\s*Meeting)?"
    r")")

# DELIBERATELY NOT HEAD-ANCHORED. Head-anchoring was tried and loses 2,903
# lines that parse today, because the House clerk puts whatever he likes in
# front of the word: "CHANGED HEARING 2/15/89", "RECESSED HEARING 3/28/89",
# "//CANCELLED**STORM//RESCHEDULED HEARING APR01", "<NOTE TIME CHANGE>
# HEARING MAR05". The guard is the one this pattern already relied on and
# states in its own comment: a date AND a time must follow the word.
LEGACY_SCHED_RE = re.compile(
    # Up to ten characters of padding, because the clerk aligned these by eye
    # and "HEARING       02/07/89" carries seven spaces.
    r"\b" + HOUSE_KIND + r"[^0-9A-Za-z]{0,10}"
    # Three date forms: with a year, without one, and by month name. The
    # yearless ones take their year from the row that announced them.
    #
    # THE YEAR IS LAZY, AND THE SPACE BEFORE THE TIME OPTIONAL, TOGETHER.
    # 1,058 rows of 1989-1990 run the date straight into the time --
    # "=CANCELED HEARING=3/21/8910:00 RM201,LOB" -- and a greedy \d{2,4} reads
    # the year as 8910 and files the sitting in the year 8910. The old pattern
    # was safe from that only because its mandatory \s+ refused the line
    # outright. Both changes are needed, and so is the widened lookahead: a
    # bare (?!\d) refuses a two-digit year followed by a time and the engine
    # backtracks to 8910 anyway.
    r"(?P<date>\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4}?"
    r"|\d{1,2}\s*/\s*\d{1,2}|[A-Za-z]{3,9}\.?\s*\d{1,2})"
    r"(?=\D|\d{1,2}:\d{2}|$)"
    # NOON is a time. It is written 39 times and means exactly midday.
    r"\s{0,8}(?P<time>\d{1,2}:\d{2}|NOON)"
    # AND NOT A MERIDIEM AFTER IT, which is what keeps this pattern to the era
    # it is for. Tried first -- and it has to be tried first, or it loses
    # 1989-1990 its times, rooms and committees -- a widened kind list makes
    # this match modern lines too, and the legacy branch does not consume a
    # meridiem: every "Public Hearing: 01/13/2025 10:30 am LOB 301-303" came
    # back with the venue "am LOB 301-303". 51,766 of them, which preflight saw
    # only the sharpest edge of, as one venue carrying a journal citation.
    #
    # The meridiem is the era. The clerk of 1989-1998 writes a bare "10:00";
    # from 2007 he writes "1:00 PM". So a line that states one is not this
    # pattern's, and falls through to HOUSE_SCHED_RE, which reads it properly
    # and hands the remainder to house_venue.
    r"(?!\s*" + HOUSE_MER + r")"
    r"(?P<rest>.*)$", re.I)
# The committee is named after FOR, with or without its colon, and sometimes
# with the room run into it: "RM105-A,SHFOR: APPROPRIATIONS".
LEGACY_FOR_RE = re.compile(r"FOR\s*:?\s*(?P<committee>[A-Z][^;]*?)\s*$", re.I)
MONTHS = {m: i for i, m in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}


def _legacy_date(s, written, session=None):
    """The hearing's date. Two forms, and only one of them states a year.

    "4/5/89" is a date. "MAR17" is not -- it takes its year from the row that
    announced it, which is the only year on the line. A row is written days or
    weeks BEFORE the hearing it announces (02/08 announced on 01/25), so where
    the month-name form would fall well before the row was written, it belongs
    to the following year: a December row announcing a January sitting.
    """
    s = re.sub(r"\s+", "", s or "")
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})$", s)
    if m:
        mo, dy, yr = (int(x) for x in m.groups())
        two_digit = len(m.group(3)) <= 2
        if yr < 100:
            yr += 1900 if yr >= 60 else 2000
        try:
            got = date(yr, mo, dy)
        except ValueError:
            return None
        # A TWO-DIGIT YEAR IS ONE KEYSTROKE FROM A DIFFERENT DECADE. One row
        # in the 1989-1990 docket reads "HEARING 3/20/99" and was written on
        # 13 March 1990, announcing a hearing the following week; read
        # literally it put a 1990 hearing in 1999. Where the row that
        # announced it is on the record and the stated year is more than a
        # year away from it, the row's own year is taken instead -- and only
        # when that lands the hearing within a year, so a genuinely distant
        # date is kept rather than dragged closer.
        # NOT ONLY A TWO-DIGIT YEAR. A four-digit one is a keystroke from a
        # different century: the 2013-2014 docket writes "Executive Session:
        # 2/6/2104 2:30 PM LOB 205", which published a hearing in the year 2104
        # and invented a term in proceedings.csv to hold it. Six rows across
        # the archive, all of them 2104 for 2014. The correction is the same
        # one and carries the same proof -- it is applied only when the row's
        # own year lands the sitting back inside the ordinary window.
        if written and abs((got - written.date()).days) > 400:
            try:
                near = date(written.year, mo, dy)
            except ValueError:
                return got
            if abs((near - written.date()).days) <= 400:
                return near
        return got
    # "3/15", a month and a day with no year at all.
    m = re.match(r"(\d{1,2})/(\d{1,2})$", s)
    if m:
        mo, dy = int(m.group(1)), int(m.group(2))
    else:
        # EXACTLY THREE LETTERS WAS THE OLD PATTERN'S SHAPE, NOT THE CLERK'S.
        # Widening LEGACY_SCHED_RE to read a month name of any length leaves
        # 1,160 of the new matches here with no date -- "SEPT 27", "JAN. 16",
        # "JULY9", "SEPT18" -- so this has to be widened the same way or those
        # rows arrive dated nothing. The first three letters are the key, and
        # MONTHS is keyed upper case, so the abbreviation and the full name
        # both land on it.
        m = re.match(r"([A-Za-z]{3,9})\.?\s*(\d{1,2})$", s.strip())
        if not m or m.group(1)[:3].upper() not in MONTHS:
            return None
        mo, dy = MONTHS[m.group(1)[:3].upper()], int(m.group(2))
    if not written:
        return None
    # THE ROW'S OWN TIMESTAMP IS NOT ALWAYS SANE. Ten rows of these ten terms
    # carry a written year more than a year from their session year, and one
    # of them -- SB623, "01/06/1904" for a 1994 row -- put a hearing in 1904
    # and invented a 1903-1904 term in proceedings.csv. Where the two
    # disagree, the session year is the better of them: it is the year the
    # docket file is FOR, and it is not a keystroke.
    if session and abs(written.year - session) > 1:
        written = written.replace(year=session)
    try:
        got = date(written.year, mo, dy)
    except ValueError:
        return None
    if (got - written.date()).days < -60:
        try:
            got = date(written.year + 1, mo, dy)
        except ValueError:
            return None
    return got


def _legacy_time(s):
    """The stated time, on a twenty-four hour reading of a twelve-hour clock.

    The old docket writes "01:30" and "10:00" and never says which half of the
    day it means. The modern docket does say, and it settles the convention by
    counting rather than by assumption -- across 31,000 modern hearings:

        1:00 pm 7,196 / am 21      8:00 am    93 / pm  0
        2:00 pm 2,780 / am  4      9:00 am 6,000 / pm  0
        3:00 pm   638 / am  0     10:00 am 11,116 / pm 10
        4:00 pm    63 / am  0     11:00 am  3,439 / pm 15
        12:00 pm  333 / am  3

    So one to six is the afternoon and eight to eleven is the morning, and
    the legacy hours fall in exactly those two clusters: 10:00 is the commonest
    at 4,993 and 1:00 next at 2,242, with nothing between 12 and 1 either way.

    Seven is the one guess on this page. It occurs 15 times in the old docket
    and once in the whole modern one, where it is 7 am -- so it is read as
    morning, on a single instance of evidence, and it is worth knowing that is
    all that stands behind it.
    """
    if (s or "").strip().upper() == "NOON":
        return time(12, 0)
    try:
        h, mi = (int(x) for x in s.split(":"))
    except (ValueError, AttributeError):
        return None
    if not (0 <= mi < 60):
        return None
    if 1 <= h <= 6:
        h += 12
    if not (0 <= h < 24):
        return None
    return time(h, mi)


# Trailing journal/calendar citation: "HJ 2  P. 5", "SJ 3", "SC 7", "HC 5  P. 7".
# Must be stripped BEFORE referral extraction -- flag-cleaning collapses runs of
# whitespace, which destroys the two-space delimiter these rely on. Leaving it in
# makes "Municipal and County Government HJ 2 P. 5" and "... P. 6" look like two
# different committees, which silently splits a shared executive-session cohort
# and upgrades its members to unique-slot confidence.
JOURNAL_TAIL_RE = re.compile(r"\s*(?:HJ|SJ|HC|SC)\s+\d+\b.*$")

# "Introduced 01/08/2025 and referred to Municipal and County Government  HJ 2  P. 5"
# "Introduced 01/08/2025 and Referred to Commerce;  SJ 2"
# "Ref. to", "Ref to", "Refer to" -- NOT ONLY "Referred to".
#
# This required the literal, and the clerk of 1999-2006 did not write it. He
# wrote "Introduced and Ref. to Executive Departments & Administration; SJ 2",
# and across the archive he writes `ref to` 20,998 times against `referred to`
# 16,063. So this pattern matched ZERO rows in the 1997-1998 docket and 183 in
# 2001-2002, against 2,955 in 2009-2010 -- which is why those terms' referral
# timeline was empty and the hearings recovered this week land on no committee
# page. Committee attribution runs at 87-94% for 1996-1998 (which gets it from
# the legacy "FOR:" clause instead), collapses to 0-33% for 1999-2007, and
# returns to 94-99% from 2008.
#
# referrals.py has accepted `ref(?:erred)?\.?\s+to` since it was written. The
# two files simply disagreed about how the clerk writes the word, and only this
# one feeds the timeline.
#
# "reference to" is not a referral and does not match: after "refer" the
# pattern needs a dot or whitespace, and "ence" is neither.
REFERRAL_RE = re.compile(
    r"[Rr]ef(?:er|erred)?\.?\s+to\s+(?P<committee>.+?)\s*(?:;|$)"
)


def normalize_committee(name):
    if not name:
        return None
    name = JOURNAL_TAIL_RE.sub("", name)
    name = re.sub(r"\s*\bP\.\s*\d+\b.*$", "", name)   # stray page refs
    # "Commerce and Consumer Affairs (in recess of 3/12/2015)": the House's
    # recess sittings of 2015, which reached the timeline once undated
    # introductions were read, and 316 proceedings named no committee for it.
    # Only that parenthesis: "(DCYF)" is part of a committee's name.
    name = re.sub(r"\s*\(in recess (?:of|from)[^)]*\)", "", name, flags=re.I)
    # "Health, Human Services & Elderly Affairs" is the committee its page
    # spells with "and".
    name = re.sub(r"\s*&\s*", " and ", name)
    name = re.sub(r"\s+", " ", name).strip(" .,;")
    return name or None

# "Vacated and Referred to Finance (Rep. C. McGuire): MA VV 01/08/2025  HJ 2"
VACATED_RE = re.compile(
    r"Vacated and Referred to\s+(?P<committee>.+?)\s*(?:\(|:)"
)

# "Committee Report: Ought to Pass, 01/30/2025, Vote 5-0;  SC 7"
CMTE_REPORT_RE = re.compile(r"Committee Report:\s*(?P<rec>[^,(]+)")

# Effective-date extraction for referral ordering
INTRODUCED_RE = re.compile(r"Introduced(?:\s+\(in recess of\))?\s+(?P<date>\d{1,2}/\d{1,2}/\d{4})")
# "Introduced and Referred to Finance." -- the same line with no date, which is
# how the 2015-2016 docket writes 1,255 of them. Anchored at the start, so a
# line that only mentions an introduction in passing is not a referral.
# The same widening as REFERRAL_RE above, and for the same reason: 1999-2006
# writes "Introduced and Ref. to Judiciary; SJ 7, Pg.90" and this anchored
# pattern is what decides whether that line reaches the timeline at all.
UNDATED_INTRO_RE = re.compile(
    r"\s*Introduced\s+and\s+[Rr]ef(?:er|erred)?\.?\s+to\b")

# A bill's SECOND committee, written on its own line once the first has
# reported:
#   "Referred to Finance 03/13/2025  HJ 8  P. 44"          (House)
#   "Referred to Ways and Means, 05/15/2025;  SJ 13"       (Senate, once)
#   "Referred to Finance; HJ 36, PG. 1579"                 (2015-2016)
#   "Referred to Finance"                                  (2015-2016, 34 rows)
# 744 rows across the six modern dockets. Anchored at the start, which is what
# keeps out "Committee Report: Referred to Interim Study", "Referral Waived by
# Committee Chair", "Sen. Gray Waived Referral to Finance" and "SB 83 is
# vacated from Commerce and referred to". "Rereferred to Committee, MA, VV" is
# the Senate sending a bill back to the committee it came from, which changes
# nothing; LATER_REFERRAL_SKIP drops it, and those are the only rows it drops.
LATER_REFERRAL_RE = re.compile(
    r"^\s*(?:Re-?)?referred\s+to\s+(?:the\s+Committee\s+on\s+)?"
    r"(?P<committee>.+?)"
    r"(?:\s*,?\s*(?P<date>\d{1,2}/\d{1,2}/\d{4}))?"
    r"\s*(?:;|\s(?:HJ|SJ)\s|$)", re.I)
LATER_REFERRAL_SKIP = re.compile(r"(?:Committee|Interim\s+Study)\b", re.I)

# A proceeding that produces video. Committee Report does NOT: its date is the
# calendar day the report is *published to the chamber*, not when the committee
# voted. The vote happens in the executive session.
VIDEO_KINDS = {
    "public hearing",
    "hearing",
    "executive session",
    "subcommittee work session",
    "full committee work session",
    "work session",
    "committee of conference",
}


def _parse_time(s):
    """The stated time, or None if the record does not state a usable one.

    ONE BAD ROW MUST NOT END THE RUN. The 2023-2024 docket contains exactly
    one time the twelve-hour clock cannot express -- HB639, "Full Committee
    Work Session: 02/14/2023 00:00 pm LOB 302-304" -- and it raised out of the
    whole of build_manifest, so 1,643 recordings could not be matched against
    23,808 docket lines because of a typo in one of them.

    It is left as None rather than read as noon. Noon is very likely what was
    meant, and "very likely" is not something this project publishes as a
    time. The proceeding keeps its date and loses only the hour."""
    # THE DOTS TOO. The Senate writes "9:00 a.m." and has since 1999 -- 9,704
    # of its 9,732 scheduling lines dot the meridiem -- and stripping only
    # spaces left every one of them returning None. A rescued hearing would
    # then publish a date and no time, which is the D-no-time confidence band
    # and cannot be aligned against a recording at all.
    s = s.strip().replace(" ", "").replace(".", "").upper()
    try:
        got = datetime.strptime(s, "%I:%M%p").time()
    except ValueError:
        return None
    return _unslip(got)


# A meridiem the clerk typed the wrong way round. The General Court does not
# open a hearing between ten at night and three in the morning, and 92 rows
# say it did -- "Public Hearing: 03/09/2026 12:15 am GP 159" for a hearing at
# quarter past noon, "11:00 pm" for one at eleven in the morning.
#
# CORRECTED, NOT REPRODUCED. That is a narrowing of this project's usual
# instinct and it was a decision, taken on 18 September 2026: reproducing an
# evident typo is not fidelity to the record, it is fidelity to a stray
# keystroke, and a reader who sees a committee's day begin at quarter past
# midnight concludes the site is broken rather than that a clerk slipped.
#
# THE THRESHOLD IS WHAT MAKES IT SAFE, so keep it where it is. Only the
# meridiem is corrected -- the digits are taken exactly as written -- and only
# in a window nothing legitimate occupies. Measured over all 99,234 stated
# times in proceedings.csv:
#
#   * every one of the 92 in this window flips into 10:00-14:59, which is the
#     heart of the committee day (10:00 alone is 32,358 rows)
#   * 85 of the 92 land inside or beside the same committee's own working day
#     that same day, several at the very minute a sibling row was set for --
#     that is the same meeting, written twice, once wrongly
#
# THE EVENING IS NOT IN THE WINDOW and must not be added to it. 46 rows sit
# between 17:00 and 21:59 and they are real: the House holds evening hearings
# off-site on contested bills, and the docket carries "6:00 PM - 8:00 PM
# Kennet High School Auditorium" to prove it. 07:00 stays for the same reason.
# Widen this and the corrections stop being corrections.
_SLIP_HOURS = frozenset((22, 23, 0, 1, 2))

# Every correction made, as (what the record said, what it was read as), so a
# run can say how many it made. SILENCE IS NOT SUCCESS: a parser that quietly
# rewrites a time is exactly the kind of step that can start rewriting the
# wrong ones and never say so.
MERIDIEM_SLIPS = []


def _unslip(t):
    """A stated time, with an obviously reversed meridiem put back."""
    if t.hour not in _SLIP_HOURS:
        return t
    fixed = t.replace(hour=(t.hour + 12) % 24)
    MERIDIEM_SLIPS.append((t.strftime("%H:%M"), fixed.strftime("%H:%M")))
    return fixed


# How far a stated sitting may fall BEFORE the row that announces it before the
# year is read as a typo. 16,548 of 16,775 announcements sit 0 to 57 days ahead
# of their row and 60% of those within a week; 22 sit 328 to 716 days behind,
# and every one of the 22 is the year -- a clerk typing January writing last
# year's. Put each on its row's own year and all 22 land 0 to 23 days ahead,
# inside the ordinary window, which is corroboration rather than a guess. The
# threshold is 180 because the nearest genuinely late entry is 95 days behind
# and must stay where it is.
_STALE_DAYS = 180


def _parse_date(s, written=None):
    """The stated date, or None. NEVER RAISES.

    It used to, on '%m/%d/%Y' alone, and the Senate branch called it with no
    try -- so a single "Hearing: 3/29/11" would not have lost a row, it would
    have ended build_manifest for every docket. That is the failure _parse_time
    was already written about, in the same file, for the same reason.

    Three shapes, because the Senate has used three: 3/29/11 and 01/14/2025,
    "May 23, 2001", and "March 21" with no year at all -- 478 rows of 1999-2000
    where the year is the one on the row that announced it.
    """
    s = re.sub(r"\s+", " ", (s or "").strip())
    if not s:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y",
                "%B %d %Y", "%b %d %Y"):
        try:
            d = datetime.strptime(s, fmt).date()
            break
        except ValueError:
            d = None
    else:
        d = None
    if d is None:
        # No year stated. Take the one from the row, as _legacy_date does.
        if written:
            for fmt in ("%B %d", "%b %d"):
                try:
                    d = datetime.strptime(s.rstrip(","), fmt).date().replace(
                        year=written.year)
                    break
                except ValueError:
                    d = None
    if d is None:
        return None
    # A YEAR THAT IS ONE KEYSTROKE OUT, IN EITHER DIRECTION. Behind the row it
    # is last year's year typed in January; ahead of it, it is a digit: the
    # 2013-2014 docket carries "Executive Session: 2/6/2104 2:30 PM LOB 205",
    # which published a hearing in the year 2104 and invented a term to hold
    # it. Both are the same mistake and both are corrected the same way, and
    # only when the row's own year lands the sitting back inside the ordinary
    # window -- so a genuinely distant date is kept rather than dragged closer.
    if written and abs((d - written.date()).days) > _STALE_DAYS:
        try:
            near = d.replace(year=written.year)
        except ValueError:
            return d
        if abs((near - written.date()).days) <= _STALE_DAYS:
            return near
    return d


@dataclass
class Proceeding:
    bill: str
    body: str
    lsr: str
    kind: str
    sched_date: str
    sched_time: str | None
    venue: str | None
    flags: list
    committee: str | None
    raw: str
    row_created: str
    row_updated: str
    # filled in by the sitting pass
    sitting_key: str | None = None
    agenda_ordinal: int | None = None
    cohort_size: int = 1
    confidence: str | None = None
    expected_title: str | None = None
    notes: list = field(default_factory=list)


# --------------------------------------------------------------------------
# Pass 1: row -> typed events
# --------------------------------------------------------------------------

def parse_rows(path):
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) < 7:
                sys.stderr.write(f"skip line {lineno}: {len(parts)} fields\n")
                continue
            rows.append({
                "lsr": f"{parts[0]}-{parts[1]}",
                "created": parts[2],
                "bill": parts[3].strip(),
                "body": parts[4].strip(),
                "desc": parts[5],
                "updated": parts[6],
                "lineno": lineno,
            })
    return rows


def cancelled(desc):
    """Whether the sitting THIS ROW DESCRIBES was called off.

    FLAG_RE reads "==CANCELLED==" and the clerk has written the word a dozen
    other ways: "//CANCELLED//HEARING JAN25" (788 rows), "==CANCELLED(Storm)=="
    (198, the parenthesis falls outside FLAG_RE's [A-Z ] class), "==Cancelled=="
    in lower case, and ", SESSION CANCELLED DUE TO WEATHER" with no delimiter at
    all. 1,363 rows said the sitting was off and produced no flag, so
    build_manifest -- which filters on that flag and nothing else -- published
    them as real meetings. Two whole terms, 1993-1996, yielded no correctly
    flagged cancellation at all.

    THE ORDER OF THE TWO WORDS IS THE ANSWER, and it is why this is a function
    rather than a wider regex. 45 rows name a cancellation AND a reschedule:

        //CANCELLED//RESCHEDULED HEARING JAN28 01:00 RM303,LOB FOR: EN
        Rescheduled Hearing, 3/17/99, Room 103, LOB, 8:30 a.m. Hearing Cancelled

    The first says a sitting was called off and gives the date of the one that
    replaced it -- the row describes a hearing that HAPPENED, and flagging it
    would hide a real hearing. The second says the replacement was itself called
    off. So the test is which word the clerk wrote last.
    """
    d = desc or ""
    c = r = None
    for m in re.finditer(r"cancel", d, re.I):
        c = m.start()
    if c is None:
        return False
    for m in re.finditer(r"re-?sched", d, re.I):
        r = m.start()
    return r is None or c > r


def extract_flags(desc):
    flags = [m.group(1).strip() for m in FLAG_RE.finditer(desc)]
    clean = FLAG_RE.sub(" ", desc).strip()
    clean = re.sub(r"\s{2,}", " ", clean)
    return flags, clean


def build_referral_timeline(rows):
    """(bill, body) -> sorted [(effective_date, committee, how)] from
    introductions, later referrals and vacate rows; `how` is "introduced",
    "referred" or "vacated".

    KEYED BY CHAMBER, since 13 September. It was keyed by bill alone, so when a
    House bill was introduced in the Senate its Senate committee joined the
    House's timeline, and a House proceeding dated after that took the
    Senate's committee's name. HB 115 of 2025 was introduced in the Senate on
    27 March and referred to Education; the House's executive session of 1
    April -- by then in House Finance -- was filed as House "Education",
    which is H05, a committee not on the General Court's list, and it kept
    H05 looking current. 48 proceedings across six terms were named after the
    other chamber's committee that way, 15 of them in 2025-2026.

    A proceeding whose own chamber has no referral row now has no committee,
    where it used to borrow the other chamber's. That looked like 327 rows,
    318 of them in 2015-2016 -- until the reason was read: that term's docket
    writes its introductions without a date, and those lines were skipped
    (see UNDATED_INTRO_RE). With them read, what is left without a committee
    is small, and a station with none reads "House Executive Session", which
    is true; "House Capital Budget" was not.
    """
    timeline = defaultdict(list)
    for r in rows:
        _, clean = extract_flags(r["desc"])
        m_vac = VACATED_RE.search(clean)
        if m_vac:
            d = INTRODUCED_RE.search(clean)
            eff = _parse_date(d.group("date")) if d else None
            if eff is None:
                m2 = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", clean)
                eff = _parse_date(m2.group(1)) if m2 else date.min
            timeline[(r["bill"], r["body"])].append(
                (eff, normalize_committee(m_vac.group("committee")), "vacated"))
            continue
        if "Vacated" in clean:
            continue
        m_ref = REFERRAL_RE.search(clean)
        intro = INTRODUCED_RE.search(clean)
        # UNDATED, TOO. The 2015-2016 docket writes 786 House and 469 Senate
        # introductions as "Introduced and Referred to Public Works and
        # Highways." with no date, and INTRODUCED_RE wants one, so none of them
        # was read: 2,600 proceedings of that term had no committee, and 318
        # more borrowed the other chamber's until the key took the chamber.
        # The row's own timestamp stands in for the date -- the clerk writes
        # the line when the bill is introduced, and a committee_on() asked
        # about an earlier day still falls back to the first entry.
        if m_ref and not intro and UNDATED_INTRO_RE.match(clean):
            try:
                eff = _parse_date(r["created"].split()[0])
            except (ValueError, IndexError):
                eff = date.min
            timeline[(r["bill"], r["body"])].append(
                (eff, normalize_committee(m_ref.group("committee")), "introduced"))
        elif m_ref and intro:
            eff = _parse_date(intro.group("date"))
            timeline[(r["bill"], r["body"])].append(
                (eff, normalize_committee(m_ref.group("committee")), "introduced"))
        # THE SECOND REFERRAL, since 13 September. Only introductions and
        # vacates were read, so "Referred to Finance 03/13/2025" was not on the
        # timeline and a Finance executive session was filed under the policy
        # committee the bill had left: HB 115's of 1 April 2025, in LOB 210-211,
        # under Education Funding. 2,040 proceedings across six terms change
        # committee, 308 of them in 2025-2026. The rooms were the witness: of
        # the 877 recording matches this moved, one was held in the first
        # committee's home room.
        #
        # A row with no date takes the row's own, as an undated introduction
        # does. A referral later waived ("Referral Waived by Committee Chair")
        # is left on the timeline: the bill was in that committee until the
        # waiver, and 3 proceedings across six terms are dated after one, all
        # of them 2016-2018, before the House streamed.
        elif not intro:
            m_later = LATER_REFERRAL_RE.match(clean)
            if m_later:
                name = normalize_committee(m_later.group("committee"))
                if name and not LATER_REFERRAL_SKIP.match(name):
                    # No date at all and it is left off: date.min would put
                    # the second committee ahead of the first.
                    try:
                        eff = _parse_date(m_later.group("date")
                                          or r["created"].split()[0])
                    except (ValueError, IndexError):
                        continue
                    timeline[(r["bill"], r["body"])].append(
                        (eff, name, "referred"))
    for b in timeline:
        # A later referral and a vacate sort after an introduction on the same
        # date, and among themselves keep the docket's row order.
        timeline[b].sort(key=lambda t: (t[0], 0 if t[2] == "introduced" else 1))
    return timeline


def committee_on(timeline, bill, when, body):
    """Which of `body`'s committees held the bill on a given date.

    A day before every entry falls back to the first introduction or vacate,
    never to a later referral: HB 1288 of 2022 has no House introduction row,
    and its hearing of 24 January in LOB 302-304 would otherwise have been
    filed under the Ways and Means it was not referred to until 16 February.
    """
    entries = timeline.get((bill, body), [])
    current = None
    for eff, cmte, _ in entries:
        if eff <= when:
            current = cmte
        else:
            break
    return current or next(
        (cmte for _, cmte, how in entries if how != "referred"), None)


def _legacy_committee(raw):
    """"EXEC DEPTS & ADM" as a committee's name, or None."""
    if not raw:
        return None
    try:
        import referrals
    except ImportError:
        return normalize_committee(raw)
    got = referrals.committee("INTRODUCED AND REF TO " + raw)
    return got or normalize_committee(raw)


# ONE COMMITTEE, ONE NAME, IN THE 1989-1998 HEARING LINES, since 13 September.
# A hearing of those years names its committee after FOR: in whatever the clerk
# typed that day -- JUD, JUDICIAR, INSURANC, WILDLIF, INT AFFS, HEALTH -- so one
# committee reached proceedings.csv under a dozen names, and a committee's page
# and every count split with them. HB 1247 of 1996 is the pattern: referred to
# "JUDICIARY & F L", its three hearings say JUDICIARY, JU and JUD.
#
# The written-out name comes from the SAME BILL, never from a list: a hearing's
# name becomes one of that bill's own referral committees in the same chamber,
# when it is a shortening of exactly one of them -- each word a prefix of the
# referral's word in order ("St-Fed" for State-Federal Relations), or a
# contraction of it ("Affs" for Affairs). That is why JUD is Judiciary for a
# Senate bill and Judiciary and Family Law for a House bill of 1995-1998, which
# no table could say without being told the chamber and the year.
#
# The referral's name is taken only when it is itself a name worth having: a
# committee the site has a page for, or one referrals.py has proven against the
# General Court's key. A referral line can be shorthand too ("ST-FED REL"), and
# trading one abbreviation for another is no gain. A written name of fewer than
# three letters (JU, M) proves nothing, and a hearing a bill's referrals do not
# explain -- Finance, where it went next -- keeps the name the line gave.
# Measured on the manifests of 1989-1998, built with and without this: 1,119
# rows take a written-out name -- 177 of them House "Judiciary" on bills
# referred to Judiciary and Family Law, and 39 of them read only because a
# referral line that opens with a date is read too -- and no manifest of
# 2015-2026 changes. Distinct committee names in proceedings.csv, House 202 to
# 148 and Senate 117 to 85.
_TARGETS = None          # (proven names, {(chamber, name)} with a page); see _written_targets
LEGACY_DATED_RE = re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{2,4}\s+")


def _written_targets():
    """(names referrals proved, {(chamber, name)} of committees with a page).

    The second comes from data/committees.json, where it is on this disk; a
    checkout without it takes only the proven names, which is fewer changes,
    never a wrong one."""
    global _TARGETS
    if _TARGETS is None:
        proven, coded = set(), set()
        try:
            import referrals
            proven = {full.lower() for _, full in referrals.PHRASES}
        except ImportError:
            pass
        p = Path("data/committees.json")
        if p.exists():
            try:
                for code, rec in json.loads(p.read_text(encoding="utf-8")).items():
                    coded.add((str(code)[:1].upper(), str(rec.get("name") or "").strip().lower()))
            except (ValueError, OSError, AttributeError):
                pass
        _TARGETS = (proven, coded)
    return _TARGETS


def _name_words(s):
    """A committee's words, lower case, "and" and any <NOTE ...> the clerk added dropped."""
    s = re.sub(r"<[^>]*>", " ", s or "")
    s = re.sub(r"\s*[&+]\s*", " and ", s)
    return [w for w in re.findall(r"[a-z]+", s.lower()) if w != "and"]


def _word_shortens(w, full):
    if full.startswith(w):
        return True
    # A contraction: every letter in order, the first one first.
    if len(w) >= 3 and w[0] == full[0]:
        rest = iter(full)
        return all(ch in rest for ch in w)
    return False


def written_out(written, referred, body):
    """The one referral committee of this bill and chamber that a legacy
    hearing's written name shortens, or None. See the note above."""
    words = _name_words(written)
    if not words or sum(map(len, words)) < 3 or (len(words) == 1 and len(words[0]) < 3):
        return None
    proven, coded = _written_targets()
    hits = set()
    for full in referred:
        fw = _name_words(full)
        if not fw or fw == words or len(words) > len(fw):
            continue
        name = full.strip().lower()
        if name not in proven and (body, name) not in coded:
            continue
        if all(_word_shortens(w, f) for w, f in zip(words, fw)):
            hits.add(full)
    return hits.pop() if len(hits) == 1 else None


def parse_proceedings(rows, timeline):
    out = []
    referred = None      # {(bill, chamber): [its referral committees]}, read at the first legacy hearing
    for r in rows:
        flags, clean = extract_flags(r["desc"])
        # .upper(), because the body code is not always upper case. 65 rows of
        # 1999-2002 carry a lower-case 's' or 'h', and an exact == "S" meant
        # SENATE_SCHED_RE was never even tried on them.
        m = (SENATE_SCHED_RE.search(clean)
             if (r["body"] or "").strip().upper() == "S" else None)
        if m:
            kind = senate_kind(m.group("kind"))
            venue = senate_venue(m.group("between"), m.group("rest"))
            # A BARE "CANCELLED" PREFIX IS STILL A CANCELLATION. The pattern
            # has to consume the word to reach the kind behind it, and doing so
            # took it out of the reach of extract_flags -- so "CANCELLED
            # Hearing, 4/14/99, Room 101, LOB, 3:30 p.m." published as a real
            # sitting, and HB238 gained two hearings that day where one was
            # called off. The prefix is captured now and read here instead.
        else:
            # LEGACY FIRST, AND THE ORDER IS THE WHOLE OF A FIX.
            #
            # HOUSE_SCHED_RE now accepts a bare "Hearing" and a two-digit year,
            # which means it also matches the 1989-1990 shorthand that used to
            # fall through to the legacy branch -- 2,128 rows of it. Tried in
            # the old order those rows would have been claimed by the modern
            # pattern and quietly stripped: the line states no meridiem so the
            # time is dropped, "RM211,LOB FOR: MUN & CTY GOVT" fails
            # HOUSE_VENUE_OK on the colon so the room is dropped, and "FOR:" is
            # read only in the legacy branch so the committee goes too.
            # Measured: 2,126 lost times, 2,122 lost rooms, 2,100 lost
            # committees, and two thousand hearings would have stopped
            # appearing on committee pages -- the exact defect this work exists
            # to close, inflicted on a different decade.
            #
            # The legacy pattern is the more specific of the two: it requires a
            # date AND a time and reads the clerk's own "FOR:". Trying it first
            # costs no coverage, because anything it declines the modern
            # pattern still sees.
            m = LEGACY_SCHED_RE.search(clean)
            if m:
                kind = house_kind(m.group("kind"))
                rest = m.group("rest") or ""
                fm = LEGACY_FOR_RE.search(rest)
                venue = (rest[:fm.start()] if fm else rest).strip(" .,:") or None
                # A JOURNAL CITATION IS NOT A ROOM. "LOB 210-211 HC 19 P. 16"
                # is a room, then House Calendar 19 page 16. The modern branch
                # has known this since HOUSE_TAIL_RE was written; the legacy
                # branch strips at "FOR:" and never learnt it, which was
                # invisible while this pattern only read 1989-1998 and became
                # 14 rooms carrying a citation once it read the rest.
                if venue:
                    venue = re.sub(r"\s*\b(?:HC|SC|HJ|SJ)\s+\d+\b.*$", "",
                                   venue, flags=re.I).strip(" .,:") or None
                legacy_cmte = fm.group("committee").strip() if fm else None
            else:
                m = HOUSE_SCHED_RE.search(clean)
                if not m:
                    continue
                kind = m.group("kind").lower()
                # Every wording of the House's conference notice is the one
                # kind VIDEO_KINDS names; "conference committee meeting" as
                # it stands would be dropped at that test below, which looks
                # exactly like the pattern having failed.
                if "conf" in kind:
                    kind = "committee of conference"
                # house_venue decides where the room ends. The pattern no
                # longer has to, which is what stopped a Zoom paragraph from
                # failing the whole line.
                venue = house_venue(m.group("rest"))

        # EVERY BRANCH, not just the Senate's. A cancellation written in any of
        # the clerk's dozen spellings reaches the flag here, whichever pattern
        # claimed the line -- which is the point: the Senate branch had a rescue
        # for this and the two House branches did not, so 1,363 called-off
        # sittings published as real meetings.
        if cancelled(r["desc"]) and not any("CANCEL" in str(f).upper()
                                            for f in flags):
            flags = list(flags) + ["CANCELLED"]

        if kind not in VIDEO_KINDS:
            continue

        legacy = m.re is LEGACY_SCHED_RE
        if legacy:
            written = None
            try:
                written = datetime.strptime(r["created"].strip(),
                                            "%m/%d/%Y %I:%M:%S %p")
            except ValueError:
                try:
                    written = datetime.strptime(r["created"].strip()[:10],
                                                "%m/%d/%Y")
                except ValueError:
                    written = None
            session = None
            head = (r.get("lsr") or "").split("-")[0]
            if head.isdigit():
                session = int(head)
            d = _legacy_date(m.group("date"), written, session)
            if d is None:
                continue
            t = _legacy_time(m.group("time"))
        else:
            legacy_cmte = None
            # `written` is the row's own date, which is what a yearless
            # "Hearing March 21" and a mistyped year are resolved against.
            _created = (r.get("created") or "").strip()
            written = None
            for _text, _f in ((_created, "%m/%d/%Y %I:%M:%S %p"),
                              (_created[:10], "%m/%d/%Y")):
                try:
                    written = datetime.strptime(_text, _f)
                    break
                except ValueError:
                    written = None
            d = _parse_date(m.group("date"), written)
            if d is None:
                continue
            # A House line may state a time with no meridiem; house_time
            # returns None rather than let anyone guess am or pm.
            if m.re is HOUSE_SCHED_RE:
                _ht = house_time(m)
            elif m.groupdict().get("mer"):
                # The Senate states its meridiem and dots it. Keep both;
                # _parse_time strips the dots.
                _ht = f"{m.group('time')}{m.group('mer')}"
            else:
                _ht = m.group("time") if m.groupdict().get("time") else None
            t = _parse_time(_ht) if _ht else None

        # The legacy line names its own committee -- "FOR: EXEC DEPTS & ADM"
        # -- which is a better answer than the referral timeline, because that
        # timeline is built from "Introduced ... and referred to", and the clerk
        # of 1989 wrote "INTRODUCED AND REF TO". The name is expanded through
        # referrals, which knows the General Court's own key to its shorthand,
        # and then written out from the bill's own referral where it shortens
        # one (see written_out).
        legacy_name = _legacy_committee(legacy_cmte)
        if legacy_name:
            if referred is None:
                referred = defaultdict(list)
                try:
                    import referrals
                    for rr in rows:
                        # A crossed-over bill's first line in the other
                        # chamber can open with the day it arrived --
                        # "03/25/98  INTRODUCED AND REF TO JUDICIARY & F L",
                        # SB 487's in the House -- which referrals.committee,
                        # anchored at "INTRODUCED", does not read. 224 such
                        # lines in 1991-1998; the date is dropped here only.
                        c = referrals.committee(LEGACY_DATED_RE.sub("", rr["desc"]))
                        if c and c not in referred[(rr["bill"], rr["body"])]:
                            referred[(rr["bill"], rr["body"])].append(c)
                except ImportError:
                    pass
            legacy_name = written_out(legacy_name, referred.get((r["bill"], r["body"]), []),
                                      r["body"]) or legacy_name

        p = Proceeding(
            bill=r["bill"], body=r["body"], lsr=r["lsr"], kind=kind,
            sched_date=d.isoformat(),
            sched_time=t.strftime("%H:%M") if t else None,
            venue=venue, flags=flags,
            committee=(legacy_name
                       or committee_on(timeline, r["bill"], d, r["body"])),
            raw=r["desc"].strip(), row_created=r["created"], row_updated=r["updated"],
        )

        # WHAT IS LEFT AFTER _unslip, which is not the same set this note was
        # written for. The reversed meridiems -- midnight to two -- are now
        # corrected there, so what reaches here is three to seven in the
        # morning: early, stated plainly, and NOT corrected, because a hearing
        # at seven is merely unusual and there is no second reading of it to
        # prefer. The note says the time is early and stops short of calling
        # it wrong.
        if t and t.hour < 8:
            p.notes.append(
                f"time {t.strftime('%I:%M %p').lower()} is earlier than the "
                "General Court ordinarily sits; the record states it and it "
                "is left as stated"
            )
        if not p.committee:
            p.notes.append("no referral row found in input; committee unresolved")
        out.append(p)
    return out


# --------------------------------------------------------------------------
# Pass 2: group into sittings, assign ordinals and confidence
# --------------------------------------------------------------------------

def build_sittings(procs):
    """A sitting = one committee meeting in one room on one day.

    Keyed on (committee, date, venue) rather than room alone, because a
    committee moves rooms between days and two committees share a room on
    different days.
    """
    sittings = defaultdict(list)
    for p in procs:
        if "CANCELLED" in p.flags:
            p.confidence = "X-cancelled"
            p.notes.append("cancelled; no video expected for this row")
            continue
        key = f"{p.committee or 'UNKNOWN'}|{p.sched_date}|{p.venue or 'UNKNOWN'}"
        p.sitting_key = key
        sittings[key].append(p)

    for key, group in sittings.items():
        # An executive session is a distinct block within the day even when it
        # shares a room with that morning's hearings, so ordinal is computed
        # per (kind, time) within the sitting.
        by_time = defaultdict(list)
        for p in group:
            by_time[(p.kind, p.sched_time)].append(p)

        ordered = sorted(by_time.keys(), key=lambda k: (k[1] or "99:99", k[0]))
        for idx, k in enumerate(ordered, 1):
            cohort = by_time[k]
            for p in cohort:
                p.agenda_ordinal = idx
                p.cohort_size = len(cohort)
                if p.sched_time is None:
                    p.confidence = "D-no-time"
                elif len(cohort) == 1:
                    p.confidence = "A-unique-slot"
                else:
                    p.confidence = "C-shared-slot"
                    p.notes.append(
                        f"{len(cohort)} bills share this slot "
                        f"({', '.join(sorted(x.bill for x in cohort))}); "
                        "running order not recoverable from docket"
                    )
                if "RECESSED" in p.flags:
                    p.notes.append(
                        "RECESSED flag: proceeding continued to a later date that "
                        "this row does not state; actual video date unconfirmed"
                    )
    return sittings


HOUSE_TITLE = "House {committee} ({date})"


def attach_expected_titles(procs):
    for p in procs:
        if p.body == "H" and p.committee:
            d = datetime.fromisoformat(p.sched_date).strftime("%m/%d/%Y")
            p.expected_title = HOUSE_TITLE.format(committee=p.committee, date=d)
        else:
            p.expected_title = None  # Senate convention not yet verified


# --------------------------------------------------------------------------

def main(inp, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    rows = parse_rows(inp)
    timeline = build_referral_timeline(rows)
    procs = parse_proceedings(rows, timeline)
    sittings = build_sittings(procs)
    attach_expected_titles(procs)

    procs.sort(key=lambda p: (p.sched_date, p.sched_time or "99:99", p.bill))

    with open(outdir / "proceedings.json", "w") as fh:
        json.dump([asdict(p) for p in procs], fh, indent=2)

    cols = ["bill", "body", "lsr", "committee", "kind", "sched_date", "sched_time",
            "venue", "agenda_ordinal", "cohort_size", "confidence",
            "expected_title", "flags", "notes", "raw"]
    with open(outdir / "proceedings.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for p in procs:
            d = asdict(p)
            d["flags"] = "; ".join(d["flags"])
            d["notes"] = " | ".join(d["notes"])
            w.writerow(d)

    tally = defaultdict(int)
    for p in procs:
        tally[p.confidence] += 1
    print(f"rows in           : {len(rows)}")
    print(f"proceedings out   : {len(procs)}")
    print(f"distinct sittings : {len(sittings)}")
    print(f"bills w/ referral : {len(timeline)}")
    print("confidence tiers  :")
    for k in sorted(tally):
        print(f"  {k:16s} {tally[k]}")
    return procs


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/docket_sample.txt",
         sys.argv[2] if len(sys.argv) > 2 else "out")
