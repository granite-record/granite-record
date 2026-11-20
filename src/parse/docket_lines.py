#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-19.1
"""
One docket line, read: the patterns the modern docket is written in, the
event each line makes (classify), the line cleaned of the clerk's flags
(clean), a committee report's fields (report_fields), and the term a date
belongs to (in_term, session_keeps, years_to_try).

    import docket_lines as DL
    DL.classify("Ought to Pass: MA VV 03/06/2025 HJ 8")   # {"_type": ..., "date": ..., ...}
    DL.session_keeps(2005, 12, 1, 2006)                   # True: the term's organisation day

No network. These were narrative.py's until 19 November 2026. docket_vocab
reads the older dockets in their own decades' words and falls back on these
for what they share, so it imported narrative, and narrative imports
docket_vocab to read a database-era bill: the one import cycle that ran at
load (reports/refactor/stage0-code.md, section 2), which worked only while
each side used the other's names at call time. Moved here as they stood,
comments and all; narrative names every one as before (narrative.classify,
narrative.PATTERNS, ...), and docket_vocab imports this module instead.

TODAY and ahead() stay in narrative: a history is told as of a day, and the
checks set narrative.TODAY to tell one as of another.
"""

import re
from datetime import date, datetime



def in_term(yr, mo, dy, session):
    """Whether a day falls in the term a session year belongs to: from
    1 November before the term's first year to the end of its second.

    The House and Senate organise on the first Wednesday of December of the
    even year, and the first bills are introduced that day -- the whole of
    2005-2006's first batch is dated 1 December 2004. The line is drawn where
    build_site_v2._j_in_term draws the rail's, so a date this keeps is one
    the rail will print.
    """
    start = session if session % 2 else session - 1
    return (start - 1, 11, 1) <= (yr, mo, dy) <= (start + 1, 12, 31)


def session_keeps(yr, mo, dy, session):
    """Whether a docket date belongs to a bill of this session year: within a
    year of it, as the database glue has always allowed, or anywhere in its
    term.

    THE SESSION COLUMN IS THE BILL'S LAST YEAR, NOT ITS FIRST. A bill
    retained into the second year of its term carries that year on every
    row, so a year either side of it reaches back only to January of the
    first -- and twelve introductions of 2005-2006 were entered at the
    organisation of the term, the December before. They are the only dates
    across the nineteen terms this keeps that the year either side did not.
    """
    return session - 1 <= yr <= session + 1 or in_term(yr, mo, dy, session)


def years_to_try(session, mo, dy, entered=None):
    """The years clamp_year tries for a month and day whose year is outside
    the bill's session, in order: the year the row was entered for, then the
    session's and the years either side of it.

    THE SESSION COLUMN IS THE BILL'S LAST YEAR, and a bill retained into its
    second year carries that year on every row. "Subcommittee Work Session:
    3/3/2008 10:00 AM LOB 208" was entered on 18 February 2009 on HB 50, a
    bill of 2009 retained into 2010, and "Retained Bill - Subcommittee Work
    Session: 9/30/2006 2:30 PM LOB 205" on 23 September 2009 on HB 606: the
    session's year made them work sessions of 3 March and 30 September 2010,
    a year after each was noticed. The year the row was entered in -- or the
    next, for a notice entered in December -- is tried first, where it puts
    the day from a week before the row to YEAR_SLIP_AHEAD days after it and
    inside the term."""
    first = []
    if isinstance(entered, datetime) and entered != datetime.min:
        for y in (entered.year, entered.year + 1):
            try:
                ahead = (date(y, mo, dy) - entered.date()).days
            except ValueError:
                continue
            if -7 <= ahead <= YEAR_SLIP_AHEAD and in_term(y, mo, dy, session):
                first.append(y)
    return first + [session, session - 1, session + 1]


YEAR_SLIP_FAR, YEAR_SLIP_AHEAD, YEAR_SLIP_ALONE = 150, 90, 30


# "== BILL KILLED ==" and "=== BILL KILLED ===". Two equals signs were
# allowed for and three were not, so 717 floor lines kept a flag in the
# middle and no pattern could read them.
FLAG_MARK = re.compile(r"=={1,}\s*[A-Z][A-Z ]*?\s*=={1,}")
# The clerk's cancel mark among those flags, spelled with one L or two.
CANCEL_WORD = re.compile(r"CANCELL?ED")


def clean(s, keep_cancel=False):
    """The docket line as every pattern here reads it: the clerk's flags
    taken out, and a citation at its end. With keep_cancel, a cancel mark
    stays where the clerk typed it (marked_line)."""
    s = FLAG_MARK.sub(lambda m: m.group(0) if keep_cancel and CANCEL_WORD.search(m.group(0))
                      else " ", s)
    s = re.sub(r"\s*(?:HJ|SJ|HC|SC)\s+\d+\b.*$", "", s)
    return re.sub(r"\s{2,}", " ", s).strip(" .;,")


# "Committee Amendment # 2025-1234s, AA, VV; 03/06/2025"
# "Amendment # 2025-1234h: AA VV 03/06/2025"
# "Enrolled Bill Amendment # 2025-2001e Adopted, VV, (In recess 06/26/2025)"
# "Sen. Birdsell Floor Amendment # 2026-1719s, AA, VV; 03/06/2026" -- the
# Senate puts the member who offered it in front, and the anchor meant 22 of
# these were not read as amendments at all. The name is captured rather than
# skipped, because who moved an amendment is worth a clause.
# "FLAM # 2026-1971h(NT) (Rep. Pauer): AA RC 171-162 05/14/2026" -- the
# House's floor amendment, with its mover in brackets. No pattern read it,
# and all 108 of 2025-2026 were told nowhere (classify gives "Floor
# Amendment" and the mover).
AMEND_RE = re.compile(
    # The name must not swallow the kind: "Sen. Birdsell Floor Amendment" is
    # a floor amendment offered by Birdsell, not an amendment by "Birdsell
    # Floor".
    r"^(?:(?P<mover>(?:Rep|Sen)\.\s+"
    r"(?:(?!Enrolled\b|Committee\b|Floor\b|Amendment\b)[A-Z][\w'\u2019.\-]*\s+){1,3}))?"
    r"(?P<what>(?:Enrolled Bill |Committee |Floor )?Amendment|FLAM\b)\s*#?\s*"
    # Not a number the clerk split with a space, "FLAM # 2022-041 7h (Rep.
    # Testerman): AF VV 02/16/2022" (HB 1598 of 2022): read as "2022-041", it
    # lost its day and was told after the bill's referral of that day, inside
    # Ways and Means' stage. It stays unread, as it was before FLAM was read.
    r"(?P<num>\d{4}-\d+[a-z]*)(?![\da-z])(?!\s\d+[a-z]\b)\s*[,:]?\s*"
    # The motion, the vote kind and the tally, in whatever order and
    # punctuation the chamber uses, each at most once:
    #
    #   House   "Amendment # 2025-1488h: AA RC 200-175 04/10/2025"
    #   Senate  "Floor Amendment # 2025-2647s, RC 9Y-15N, AF; 06/05/2025"
    #
    # None of the three was allowed for between the number and the date, so
    # every roll-called or divided amendment lost BOTH its tally and its date
    # -- the date pattern was left sitting in front of "200-175". Thirteen of
    # HB2's Senate amendments were undated in the published narrative and 26
    # of its House ones were dated only by the sentence before them.
    #
    # AND THE DOCKET PUTS THINGS BETWEEN THE NUMBER AND THE MOTION. Nothing
    # was allowed there, so the alternation below matched zero times and the
    # line lost its motion, its vote kind AND its tally together -- 1,075
    # amendment events, every one of them with vote_kind None. 2025-2026
    # SB13 reads "Amendment # 2025-1934h (NT): AA DV 183-163" -- adopted on
    # a division of 183 to 163 -- and the site showed none of the three. The
    # date survived, because it is matched separately, which is why this
    # looked like nothing was wrong.
    #
    # WHAT IS ACTUALLY THERE, counted over those 1,075 lines rather than
    # guessed at: the New Title marker in four punctuation shapes ((NT):
    # 330, "NT," 175, (NT) 79, "NT;" 5), a parenthesised sponsor ((Rep 132,
    # (Rep. 48, (Reps 15), and the enrolled-bill marker (E 26, -EBA: 17,
    # EBA 6). None of the three carries an outcome, so they are skipped
    # rather than captured -- this pattern is read for what the chamber
    # DID, and a title change is not that.
    r"(?:(?:\(?(?:NT|New Title)\)?|-?EBA)[,;:]?\s*"
    r"|\((?P<by>(?:Reps?|Sens?)\.?[^)]*)\)[,;:]?\s*){0,3}"
    # DIV is the House's other spelling of a division, and "Failed" is the
    # spelled-out form of AF. The docket writes the outcome either way and
    # this had the abbreviation of both and the word for only one -- the
    # same half-a-pair that left 153 events with no outcome in
    # build_site_v2.ADOPTED.
    r"(?:(?:(?P<motion>AA|Adopted|AF|AL|Failed)"
    r"|(?P<vote>VV|DIV|DV|RC)"
    r"|(?P<y>\d+)\s*Y?\s*[-\u2013]\s*(?P<n>\d+)\s*N?)[,;]?\s*){0,4}"
    r"(?:\(?(?:in recess of|In recess)\)?\s*)?"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4})?", re.I)


AMEND_VOTE = re.compile(r"\b(RC|VV|DV|DIV|Div\.?|Division)(?![\w])", re.I)
AMEND_TALLY = re.compile(r"\b(\d{1,3})\s*Y?\s*[-–]\s*(\d{1,3})\s*N?\b")


# "Enrolled Adopted, VV, (In recess 06/26/2025)" / "Enrolled (in recess of) 06/26/2025"
ENROLLED_RE = re.compile(
    r"^Enrolled\b(?!\s+Bill)\s*(?P<motion>Adopted)?[,;]?\s*(?P<vote>VV|DV|RC)?[,;]?\s*"
    r"(?:\(?(?:in recess of|In recess)\)?\s*)?(?P<date>\d{1,2}/\d{1,2}/\d{4})?", re.I)

RETAINED_RE = re.compile(r"^Retained in Committee", re.I)

# A bill sent to interim study comes back with a report, and the report is the
# last thing that happens to it. Real line, from a bill on the live site:
#
#   "Interim Study Report: Not Recommended for Future Legislation 06/02/2026
#    (Vote 14-0; RC)"
#
# The recommendation is captured rather than matched, for the same reason the
# veto outcome is: the negative form is the common one, and a pattern looking
# for "Recommended" would read a rejection as an endorsement. It is then
# repeated in the committee's own words.
INTERIM_REPORT_RE = re.compile(
    r"^Interim Study Report\s*:\s*(?P<rec>[^0-9]+?)\s*"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4})?\s*"
    r"(?:\(\s*Vote\s*(?P<y>\d+)\s*-\s*(?P<n>\d+)\s*;?\s*(?P<cal>CC|RC)?\s*\))?\s*$",
    re.I)

# "SB 123 was Removed from the Consent Calendar; 05/15/2025"
# A bill pulled off the consent calendar is taken up on its own instead of
# being adopted with the rest without discussion. That is a substantive event
# and it was being dropped.
CONSENT_OFF_RE = re.compile(
    r"^(?P<bill>[A-Z]+\s*\d+)?\s*was Removed from the Consent Calendar"
    r"[;,]?\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})?", re.I)

# "Conference Committee Meeting: 06/12/2025 10:00 am GP 201"
# Where a contested bill gets its final wording, and we index those videos.
CONF_MEET_RE = re.compile(
    r"^Conference Committee Meeting[:\s]+(?P<date>\d{1,2}/\d{1,2}/\d{4})"
    r"\s*(?P<time>\d{1,2}:\d{2}\s*[ap]m)?\s*(?P<venue>[A-Z].*)?$", re.I)
DIED_RE = re.compile(r"^Died on Table[,;]?\s*Session ended\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})?", re.I)
# A CHAMBER'S VOTE ON A COMMITTEE OF CONFERENCE'S REPORT (the launch audit of
# 7 October 2026, cause 10). "Conference Committee Report # 2026-2109c; RC
# 15Y-8N, Adopted; 06/04/2026" (the Senate) and "Conference Committee Report
# 2026-2109c: Adopted, RC 183-170 06/04/2026" (the House), HB 1300 of 2026:
# read by no pattern, so no history of 2007-2026 said a conference report was
# adopted, while the rail drew both votes. The number with its letter is
# required, which leaves the 1999-2008 readers' "Conference Committee
# Report{2206}" to them; a "Filed" row is the report arriving, not a vote on
# it. No date is captured: the row is dated by stated_day ("conference
# vote"), as it was while it was read by nothing.
CONF_REPORT_RE = re.compile(
    r"^Conference\s+Committee\s+Report\s*#?\s*(?P<num>(?:\d{4}-)?\d{3,4}[a-z])\b"
    r"(?!.*\bFiled\b).*?\b(?P<outcome>Adopted|Failed)\b", re.I)
# A BILL ENDED BY SENATE RULE 3-23 (the launch audit of 7 October 2026, cause
# 11): "Inexpedient to Legislate, Senate Rule 3-23, 10/31/2025" (SB 131 of
# 2025), "..., Adjournment 09/16/2020" (HB 1101 of 2020), "Inexpedient to
# Legislate, 2013 Adjournment, Senate Rule 3-23" (HB 135 of 2013). Read by no
# pattern, so 67 histories of 2025-2026 never said how the bill ended, while
# the rail drew it; SB 131's ended with the Senate's tabling. 723 of the 724
# rows on disk follow a Senate tabling. Dated by stated_day ("adjournment"),
# as it was while it was read by nothing. Its own type, not "died": the rail's
# reader passes over a "died" row as no floor action.
SENATE_RULE_KILL_RE = re.compile(
    r"^Inexpedient\s+to\s+Legislate,?\s*(?:\d{4}\s+Adjournment,?\s*)?"
    r"Senate\s+Rule\s+3-23\b", re.I)
# A PUBLIC HEARING ON A PROPOSED NON-GERMANE AMENDMENT (the launch audit of 7
# October 2026, cause 15). The House: "Public Hearing on non-germane Amendment
# # 2025-0102h: 02/11/2025 01:30 pm LOB 210-211" (HB 519 of 2025, which has
# sign-ins that day), "Public Hearing on non-germane Amendment #2016-0081h
# (NT): ...", "Public Hearing on Proposed Non-Germane Amendment ...", "...
# Non-Germane AM ...". The Senate: "Hearing: 02/18/2026, Room 103, SH, 09:00
# am, on proposed non-germane amendment # 2026-0579s" (SB 425 of 2026), and
# "Hearing: 4/16/13, Room 103, LOB, 10:00 a.m. Proposed non-germane amendment
# to HB 636 #2013-1233s". Read by no pattern: 65 hearings on 59 bills of
# 2025-2026 were in no history, and the House's were dated by the day the
# row was entered. Its own type, not "hearing": the meeting rules
# (overtaken, voided_meetings, whole_day) are about the bill's own hearings,
# and HB 1300 of 2026's of 10:00 and its hearing on 2026-0093h at 10:15 are
# two hearings of one day. The Senate's rows state their day as a hearing
# notice does, and keep it by stated_day ("notice"), as they did while they
# were read by nothing. And the bill's own hearing whose row says it takes
# the amendment up too, "Public Hearing: 4/21/2015 1:00 PM Representatives
# Hall; to include consideration of non-germane amendment #2015-1351h" (SB 30
# and SB 242 of 2015), which the hearing pattern could not read for what
# follows its room ("incl").
NONGERMANE_HEARING_HOUSE = re.compile(
    r"^Public\s+Hearing\s+on\s+(?:Proposed\s+)?Non-?\s?Germane\s+(?:Amendment|AM)\b\.?\s*"
    r"(?:#\s*)?(?P<num>(?:\d{4}-)?\d{3,4}[a-z])?\s*(?:\(NT\))?\s*:\s*"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4})", re.I)
NONGERMANE_HEARING_SENATE = re.compile(
    r"^(?P<joint>Joint\s+)?Hearing\b[^:;]{0,80}?:\s*(?P<sdate>\d{1,2}/\d{1,2}/\d{2,4})\b.*?"
    r"\b(?:on\s+)?proposed\s+non-?\s?germane\s+amendment\b(?:\s+to\s+[A-Z]+\s*\d+)?\s*(?:#\s*)?"
    r"(?P<num>(?:\d{4}-)?\d{3,4}[a-z])?", re.I)
NONGERMANE_HEARING_WITH_BILL = re.compile(
    r"^Public\s+Hearing\s*:\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})\b[^;]*;\s*"
    r"(?P<incl>to\s+include\s+consideration\s+of)\s+non-?\s?germane\s+amendment\s*(?:#\s*)?"
    r"(?P<num>(?:\d{4}-)?\d{3,4}[a-z])?", re.I)
REREF_RE = re.compile(r"^Referred to\s+(?P<committee>[A-Z][A-Za-z,&\-\s]+?)\s+"
                      r"(?P<date>\d{1,2}/\d{1,2}/\d{4})", re.I)

# The end of a session is where the docket's wording changes completely, and
# none of it was being recognised. These are real lines, taken from bills on
# the live site:
#
#   "Veto Sustained 08/19/2026: RC 152-167 Lacking Necessary Two-Thirds Vote"
#   "Notwithstanding the Governor's Veto, Shall SB 434 Become Law: RC 16Y-8N,
#    Veto Overridden by necessary two-thirds vote; 08/19/2026"
#
# The House states the outcome first; the Senate states the question first and
# the outcome last. That is the same split as the motion vocabularies in
# rollcall_parser.py, where the House abbreviates and the Senate spells out.
#
# The outcome word is CAPTURED, never assumed. A pattern that only knew how to
# find "Overridden" would silently miss every sustained veto, and a sustained
# veto is the more common result.
VETO_HOUSE_RE = re.compile(
    r"^Veto\s+(?P<outcome>Sustained|Overridden)\b[,;:]?\s*"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4})?\s*[,;:]?\s*"
    r"(?:(?P<vote>RC|VV|DV)\s*(?P<y>\d+)\s*[-\u2013]\s*(?P<n>\d+))?", re.I)

VETO_SENATE_RE = re.compile(
    r"^Notwithstanding the Governor'?s Veto,?\s*Shall\s+[A-Z]+\s*\d+\s+Become\s+Law"
    r"[,;:]?\s*(?:(?P<vote>RC|VV|DV)\s*(?P<y>\d+)\s*Y?\s*[-\u2013]\s*"
    r"(?P<n>\d+)\s*N?)?[,;:]?\s*Veto\s+(?P<outcome>Sustained|Overridden)"
    r"(?:.*?[;,]\s*(?P<date>\d{1,2}/\d{1,2}/\d{4}))?", re.I)

# A bill the governor neither signs nor returns becomes law regardless, and the
# docket says so two different ways. Both were unrecognised, which meant a bill
# that is law read as though it were still sitting on the governor's desk.
#
#   "Law Without Signature 08/19/2026; Chapter 344; Effective 08/19/2026; ..."
#   "Enacted in accordance with Article 44 PartII of the N.H. Constitution
#    without the signature of the governor. Chapter 343;I. sec 4 eff 12/1/26..."
#
# The second form carries no full date at all -- its effective dates use
# two-digit years -- so the event falls back to the docket row's own timestamp
# rather than inventing one.
UNSIGNED_RE = re.compile(
    r"^Law Without Signature\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})?"
    r"(?:.*?Chapter\s*(?P<chapter>\d+))?", re.I)
ENACTED_RE = re.compile(
    # ".*?" rather than "[^.]*?": the clause in between contains "N.H.", and a
    # class excluding dots can never cross it.
    r"^Enacted in accordance with Article\s*44.*?without the signature of the"
    r"\s*governor\.?\s*(?:.*?Chapter\s*(?P<chapter>\d+))?", re.I)

# A BILL WITHDRAWN, on a row that is not a floor vote (1 October 2026). Twelve
# rows across every docket on disk, all of them on bills the General Court's
# search page left out and the site had no record of: "Withdrawn Prior to
# Introduction" on four bills of 2010, "Withdrawn" and "Withdrawn 11/30/2011"
# on three of 2012, "Read in January 4, 2012 and Withdrawn" on a petition.
# The whole line, so that "Withdrawn from Committee Without Recommendation"
# -- a committee discharged -- is not one; a withdrawal the chamber voted,
# "Withdrawn (Rep Kreis): MA VV", is a floor row and is read as one.
# AND A PETITION ITS PETITIONER WITHDREW: "Petition Withdrawn By Petitioner",
# the last row of PET 7 of 2012, entered the day its committee was to vote on
# it. The row was read by nothing and the petition read "In committee".
WITHDRAWN_ROW = re.compile(
    r"^\s*(?:Read\s+in\s+(?P<read>[A-Z][a-z]+\s+\d{1,2},?\s+\d{4})\s+and\s+)?"
    r"(?:Petition\s+)?Withdrawn(?P<prior>\s+Prior\s+to\s+Introduction)?"
    r"(?P<by>\s+By\s+Petitioner)?"
    r"(?:\s+(?P<date>\d{1,2}/\d{1,2}/\d{4}))?\s*$", re.I)
# "Proposed bill for special sesssion." is the one row of HB 3 of the 2006
# special session: a bill proposed for it, and nothing after.
PROPOSED_ROW = re.compile(
    r"^\s*Proposed\s+bill\s+for\s+(?:the\s+)?special\s+sess+ion\s*$", re.I)


PATTERNS = [
    ("introduced", re.compile(
        r"Introduced\s+(?:\(in recess of\)\s*)?(?P<date>\d{1,2}/\d{1,2}/\d{4})"
        r"\s+and\s+[Rr]eferred to\s+(?P<committee>.+?)$", re.I)),
    ("vacated", re.compile(
        r"Vacated and Referred to\s+(?P<committee>.+?)\s*(?:\(|:)", re.I)),
    ("nongermane_hearing", NONGERMANE_HEARING_HOUSE),
    ("nongermane_hearing", NONGERMANE_HEARING_SENATE),
    ("nongermane_hearing", NONGERMANE_HEARING_WITH_BILL),
    ("hearing", re.compile(
        r"(?P<kind>Public Hearing|Hearing)\s*:\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})"
        # "Room Map Room, SL" -- the room name can be words, not a number,
        # and [\w-]+ cannot cross the space. 41 Senate hearings fell out of the
        # narrative on that alone.
        r"(?:[, ]+(?:Room\s+(?P<room>[\w][\w .\-]*?),\s*(?P<bldg>\w+),)?)?"
        r"\s*(?P<time>\d{1,2}:\d{2}\s*[ap]m)?\s*(?P<venue>[A-Za-z0-9 .-]*)$", re.I)),
    ("exec", re.compile(
        r"Executive Session\s*:\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})", re.I)),
    ("worksession", re.compile(
        r"(?P<kind>(?:Subcommittee|Full Committee)?\s*Work Session)\s*:\s*"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{4})", re.I)),
    # "Committee Report: Ought to Pass with Amendment # 2026-0797h (NT)
    # 02/18/2026 (Vote 9-8; RC)", and sixteen other punctuations of the same
    # six facts. Anchored at the start, because "Conference Committee Report"
    # is a different body -- the committee of conference, sitting for both
    # chambers -- and the unanchored pattern read fourteen of its lines as the
    # policy committee's own recommendation. The side is matched loosely --
    # Major\w*, not Majority -- because the clerk typed "Majoritiy
    # Committee Report" on HB749, and an exact spelling drops that report.
    #
    # The recommendation ends at the first thing that is not part of it: an
    # amendment number, a date, a vote, or a separator. Taking [^,(;#]+ instead
    # ended it at a comma that is often not there, so the date came away inside
    # it on 1,511 of 4,398 lines -- "Ought to Pass 05/06/2025" -- which turned
    # nine recommendations into 273 and put a raw docket date into a published
    # sentence. What follows the recommendation is picked apart by
    # report_fields(), because those facts appear in any order.
    ("report", re.compile(
        r"^\s*(?:(?P<side>Major\w*|Minor\w*)\s+)?Committee\s+Report\s*:\s*"
        r"(?P<rec>.*?)"
        r"(?=\s*(?:#|\d{1,2}/\d{1,2}/\d{4}|[,;(]|\bVote\b|$))"
        r"(?P<rest>.*)$", re.I)),
    ("conf_report", CONF_REPORT_RE),
    ("senate_rule_kill", SENATE_RULE_KILL_RE),
    ("veto_override", VETO_HOUSE_RE),
    ("veto_override", VETO_SENATE_RE),
    ("unsigned_law", UNSIGNED_RE),
    ("unsigned_law", ENACTED_RE),
    # Floor action. The House writes "Ought to Pass: MA VV 03/06/2025"; the
    # Senate writes "Ought to Pass: MA, VV; OT3rdg; 03/06/2025". Same event,
    # different punctuation, and the separator may also be a comma rather than
    # a colon: "Inexpedient to Legislate, MA, VV = =; 03/06/2025".
    ("floor", re.compile(
        r"^(?P<action>.+?)\s*[:,]\s*(?P<motion>MA|MF|ML)\b[,;\s]*"
        r"(?P<vote>VV|DV|RC)?\s*=?\s*=?[,;\s]*"
        r"(?:(?P<y>\d+)\s*-\s*(?P<n>\d+))?[,;\s]*"
        r"(?:OT\drdg)?[,;\s]*"
        # A bill can be sent straight on to Finance under House Rule 4-5 in the
        # same motion that passes it. That clause sits between the vote and the
        # date and was stopping the whole line from parsing.
        # THE NAME RUNS TO THE RULE, the bracket or the separator after it
        # (3 October 2026). "[A-Z][A-Za-z ]+?" with nothing after it required
        # stopped at two letters wherever the clause skipped below could take
        # the rest: "Refer to Finance Rule 4-5; 03/06/2025" (HB 71 of 2025)
        # read "Fi", and 966 histories said "sent it on to the Fi committee".
        r"(?:Refer(?:red)?\s+to\s+(?P<refer>[A-Z][A-Za-z ]*?[A-Za-z])"
        r"(?=\s*(?:\[|\(|Rule\b|[,;]|\d|$))"
        r"(?:\s+Rule\s*[\d\-]+)?[,;\s]*)?"
        # WHAT THE CHAMBER SAID ABOUT ITS OWN VOTE, between the tally and the
        # date: "Lacking Necessary Two-Thirds Vote", "by necessary two-thirds
        # vote", "(In recess of)". 2,024 floor lines across the archive and
        # the current term ended at this clause and were never read as votes
        # at all -- including every constitutional amendment that failed for
        # want of three fifths, which then had no outcome but a minority
        # report's words.
        r"(?:[A-Za-z(][^;]{0,70}?)?[,;\s]*"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{4})", re.I)),
    ("amendment", AMEND_RE),
    ("enrolled", ENROLLED_RE),
    ("consent_off", CONSENT_OFF_RE),
    ("conference_meeting", CONF_MEET_RE),
    ("interim_report", INTERIM_REPORT_RE),
    ("retained", RETAINED_RE),
    ("died", DIED_RE),
    ("rereferred", REREF_RE),
    ("governor", re.compile(
        # The clerk writes it both with and without the article: "Signed by
        # Governor Ayotte 7/10/2026" 400 times and "Signed by the Governor on
        # 7/10/2026" 233 times. Only the first was recognised, so a third of
        # the signatures on the record arrived as unclassified text.
        r"(?P<what>Signed by (?:the )?Governor|Vetoed by (?:the )?Governor"
        r"|Sent to (?:the )?Governor)"
        # And then the governor's SURNAME, or the word "on", before the date:
        # "Signed by Governor Ayotte 06/27/2025" and "Signed by the Governor
        # on 02/27/2025". Neither was allowed for, so the date matched empty
        # on all 1,254 signed lines and 49 of the 69 vetoes, and every bill
        # that became law read "The governor signed it on ." The chapter and
        # the effective date came through, which is why it looked like a
        # sentence with a gap in it rather than a pattern that had failed.
        r"(?:\s+(?:on|[A-Z][A-Za-z.'\u2019\-]+)){0,2}"
        r"[,;]?\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})?"
        r"(?:.*?Chapter\s*(?P<chapter>\d+))?"
        r"(?:.*?Effective\s*(?P<eff>\d{1,2}/\d{1,2}/\d{4}))?", re.I)),
    # Last: nothing above reads these two, which were "other" until now.
    ("withdrawn", WITHDRAWN_ROW),
    ("proposed", PROPOSED_ROW),
]


# --- the rest of a committee report line ------------------------------------
#
# The clerk punctuates the same six facts a dozen ways -- "; Vote 5-0; CC",
# "(Vote 9-8; RC)", ", 01/30/2025, Vote 3-2" -- so each is found by its own
# marker rather than by where it sits. Anything the line does not carry is
# simply absent: a minority report has no vote of its own, and 706 of them
# say so by omission.
R_AMEND = re.compile(r"#\s*(?P<amend>(?:\d{4}-)?\d+[a-z]*)", re.I)
# The date the committee signed its report, which is not the date the docket
# row was created and is usually days earlier.
R_RDATE = re.compile(r"(?P<date>\d{1,2}/\d{1,2}/\d{4})")
R_RVOTE = re.compile(r"\bVote\s+(?P<y>\d+)\s*-\s*(?P<n>\d+)", re.I)
# A new title travels with the amendment and changes what the bill is called,
# which is why two reports on one bill can carry two different titles.
R_NT = re.compile(r"\(NT\)", re.I)


def report_fields(rest):
    """Amendment, date and vote off the tail of a committee report line."""
    out = {}
    for pat in (R_AMEND, R_RDATE, R_RVOTE):
        m = pat.search(rest or "")
        if m:
            out.update({k: v for k, v in m.groupdict().items() if v})
    if R_NT.search(rest or ""):
        out["new_title"] = "1"
    return out


def classify(desc):
    c = clean(desc)
    for name, pat in PATTERNS:
        m = pat.search(c)
        if m:
            d = m.groupdict()
            if name == "report":
                d.update(report_fields(d.pop("rest", "")))
            if name == "conf_report":
                # The vote kind and count, in either chamber's order, the way
                # amendment_outcome reads them off an amendment row.
                vk = AMEND_VOTE.search(c, m.end("num"))
                tally = AMEND_TALLY.search(c, vk.end()) if vk else None
                d["vote"] = ({"RC": "RC", "VV": "VV"}.get(vk.group(1).upper(), "DV")
                             if vk else None)
                d["y"], d["n"] = (tally.group(1), tally.group(2)) if tally else (None, None)
                d["motion"] = "MA" if d["outcome"].lower() == "adopted" else "MF"
            if name == "nongermane_hearing":
                # The Senate's row states its day as a hearing notice does,
                # and stated_day reads it; where the year is two digits
                # ("Hearing: 4/10/13, Room 102, LOB, ..."), or the row is a
                # joint hearing's ("Joint Hearing with the House Education
                # Funding Committee: 10/14/2025, ..."), which it does not
                # read, the day is the row's here, as the era reader gave it.
                said = d.pop("sdate", None)
                if said and not d.get("date"):
                    mo, dy, yr = said.split("/")
                    if len(yr) == 2 or d.get("joint"):
                        yr = yr if len(yr) == 4 else f"{'20' if int(yr) < 50 else '19'}{yr}"
                        d["date"] = f"{int(mo):02d}/{int(dy):02d}/{yr}"
            if name == "amendment":
                # "FLAM # 2026-1971h(NT) (Rep. Pauer): AA RC 171-162" is the
                # House's floor amendment, and who offered it is in brackets.
                by = (d.pop("by", None) or "").strip()
                if (d.get("what") or "").upper() == "FLAM":
                    d["what"] = "Floor Amendment"
                    if by and not d.get("mover"):
                        d["mover"] = re.sub(r",\s*(?=[^,]+$)", " and ", by)
            d["_type"] = name
            d["_raw"] = c
            return d
    return {"_type": "other", "_raw": c}
