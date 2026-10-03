#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.21
"""
A sitting day of the House or Senate, assembled from what is already parsed.

    import session_days
    days = session_days.load()            # {(body, date): Day}
    day = session_days.one("H", "2018-03-07")

WHY THERE IS NO PARSER HERE

The obvious way to build a session day page is to parse the chamber's journal.
That was measured before it was attempted, over all 1,064 journal files, and
thirty-six of the forty candidate patterns were refuted: the constructs are
real but they wrap across lines, the eras are wrong, and the regexes
over-match. One proposed day-boundary pattern matched 1,076 lines of which 561
were day starts.

None of that is needed for the RECORD of a day. narratives.json already holds
79,096 floor events across all nineteen terms, each carrying the bill, the
motion, who moved it, whether it carried, how it was voted and the journal page
it is printed on. That is the whole of what happened; the journal adds only who
spoke and what was said, which journal_days.py reads separately and which this
module does not need.

So the rule is: THE RECORD COMES FROM STRUCTURED DATA, the journal supplies
colour. A page can lose the colour and still be true.

AND THE ROLL CALLS COME FROM THE ROLL-CALL FILE. rollcalls.json holds every
roll call the voting system recorded from 1999, and it is the list a sitting
draws its roll calls from: each on the docket's motion that is that vote, or
on a motion of its own from the row or clause that states it, or from the
file alone where no docket row does (_roll_calls, below). Before 1999 the
docket is the only record of a roll call, and its own words are drawn.

THE THREE VOTES, AND WHY THE TALLY NEVER DECIDES

  roll call   vote_kind RC, with yeas and nays, and ballots in rollcalls/
  division    vote_kind DV, with yeas and nays and no names -- nobody recorded
              who voted which way, which is what a division IS
  voice       vote_kind VV, no count at all

WHICH SIDE PREVAILED IS `motion`, NEVER THE LARGER NUMBER. It is MA (motion
adopted), or MF or ML (motion failed, motion lost), stated by the clerk. Inferring it from the
tally gets every veto override and every constitutional amendment backwards: on
9 April 2026 the House recorded YEAS 186 - NAYS 169 and the veto was SUSTAINED,
because an override needs two thirds. 186 is the larger number and the losing
one.

WHAT A MOTION MEANS IS NOT WHAT IT SOUNDS LIKE, EITHER. "Inexpedient to
Legislate" carrying means the bill is DEAD, and a member who spoke for that
motion was arguing to kill it. `outcome_words` states the consequence in plain
English so no page has to work it out twice.
"""

import collections
import json
import re
from datetime import date as _date
from pathlib import Path

import build_date
import narrative

NARRATIVES = "narratives.json"

# The clerk's shorthand, expanded. MA, MF and ML are the only ones that decide
# anything; the rest appear in `raw` and are not relied on here. ML is
# "motion lost", the House docket's usual word where the Senate's is MF:
# without it every motion the record holds as ML -- 260 on 1 October 2026,
# among them 2006's HB 1240, whose passage failed 141-181 -- was drawn on its
# sitting page with no outcome at all.
CARRIED = {"MA": True, "MF": False, "ML": False}

VOTE_KIND = {
    "RC": "roll call",
    "DV": "division",
    "VV": "voice vote",
}

# What a motion CARRYING does to the bill. The journal states the motion, not
# the consequence, and the consequence is what a reader came for -- "Inexpedient
# to Legislate: MA" is a bill being killed and says so nowhere on its face.
#
# Keyed on the motion's opening words because the clerk appends detail to it:
# "Ought to Pass with Amendment 2026-0541h", "Lay HB1063 on Table (Rep. Mazur)".
KILLS = ("inexpedient to legislate", "indefinitely postpone")
PASSES = ("ought to pass", "adopt", "concur", "pass")
DEFERS = ("refer for interim study", "re-refer to committee", "lay ",
          "table", "special order", "rerefer")


def _consequence(action, carried):
    """What this motion carrying or failing did to the bill, in plain words.

    None where the motion is one this cannot speak for -- and returning None
    is the point. A page prints the motion and the outcome plainly when this
    has nothing to add, rather than being handed a confident wrong sentence.
    """
    a = (action or "").strip().lower()
    if not a or carried is None:
        return None
    # ONE CHAMBER'S OVERRIDE DOES NOT MAKE A LAW. Both must vote it by two
    # thirds, and an override carried in one chamber was said to have made
    # the bill law on 29 bills the other chamber then sustained: the Senate
    # overrode SB 434 16-8 on 19 August 2026, the House sustained it 165-140,
    # and the Senate's page said it became law without the Governor. A
    # sustained veto in either chamber is the end of the bill.
    if a.startswith("override the governor"):
        return ("the veto was overridden in this chamber" if carried else
                "the veto was sustained, so the bill did not become law")
    if a.startswith(KILLS):
        return "the bill was killed" if carried else "the bill stayed alive"
    if a.startswith("reconsider"):
        return ("the chamber agreed to take it up again" if carried
                else "the earlier decision stood")
    if a.startswith("remove from table"):
        return ("it came back off the table" if carried
                else "it stayed on the table")
    if a.startswith(DEFERS):
        return ("it was set aside rather than decided" if carried
                else "it was not set aside")
    # "Adoption of the suspension of the rules" (HB 2004, 25 May 2004) is a
    # suspension, and what one does is let something else be taken up.
    if re.search(r"\bsuspen", a):
        return None
    if a.startswith(PASSES):
        return ("it carried in this chamber" if carried
                else "it did not carry in this chamber")
    return None


# THE SENATE WRITES ITS VOTE INSIDE THE MOTION. "Ought to Pass RC 19Y-5N,
# 3/5 nec., MA; OT3rdg" is one Senate action: the kind, the tally and the
# threshold are all in the prose, and the vote_kind, yeas and nays fields are
# empty. 1,445 Senate actions are like this and no House action is. And
# "DIV" is a division as "DV" is: "Ought to Pass: DIV 15Y-8N, MA; OT3rdg"
# (SB 284, 20 March 2025) was drawn with its count taken out of its words
# (INLINE_COUNT) and none read, so the division was on no part of the page.
INLINE_VOTE = re.compile(r"\b(?P<kind>RC|DV|DIV\.?|VV)\s*(?P<y>\d+)\s*Y\s*-\s*"
                         r"(?P<n>\d+)\s*N", re.I)
# The same count where the reader left it in the motion's words: "Ought to
# Pass with Amendment #2025-0144s, RC 15Y-8N". The page draws the count
# under the motion, and the ballots' where they differ from the docket's, so
# the words carry none: 1,477 Senate motions of 2007-2026 said one count in
# their words and drew another beneath them wherever the two disagreed.
INLINE_COUNT = re.compile(r",?\s*\b(?:RC|DV|VV|Div(?:ision)?\.?)\s*\d+\s*Y\s*-\s*"
                          r"\d+\s*N\b", re.I)
# A division's count after a comma, which the docket reader leaves in the
# line: "Third Reading MA Div, 184-155", entered on 35 Senate bills of
# 30 April 2014, was one division drawn 35 times without its count and
# counted 35 times in the day's opening.
DIV_COUNT = re.compile(r"\b(?:DV|Div(?:ision)?)\b,?\s*(?P<y>\d+)\s*-\s*(?P<n>\d+)\b", re.I)

# "3/5 nec." and "2/3 nec." -- the motion needed a supermajority. Drawn as a
# simple majority the threshold mark on the ring sits in the wrong place and
# the chart says a motion cleared a bar it did not have to clear, or missed one
# it never faced. The House spells it out -- "By Necessary Three-Fifths Vote",
# "Lacking Necessary Two-Thirds Vote" -- and was drawn at a majority.
THRESHOLD = re.compile(r"\b(?P<a>\d)\s*/\s*(?P<b>\d)\s*nec", re.I)
THRESHOLD_WORDS = re.compile(r"\b(?:two|three)[\s-]*(?P<f>thirds|fifths)\b", re.I)
# And the 1989-1998 clerk's, in the clause that holds the count: "3RD READING
# FAILS 3/5 RC(197-126)" (CACR 20, 11 February 1992), "OTP/AM FAILS 3/5
# RC(193-163)" (CACR 45, 10 September 1998). Read only from that clause
# (_docket_only): a line's other clauses are other questions.
THRESHOLD_FAILS = re.compile(r"\b(?:FAIL(?:S|ED)?|LACKING|BY)\s+(?P<a>\d)\s*/\s*(?P<b>\d)\b",
                             re.I)
# And the fraction after the word: "Ought to Pass: MF DIV 161-91, Lacking
# Necessary 2/3" (HB 296, 5 April 2007), drawn at a majority.
THRESHOLD_AFTER = re.compile(r"\bnec(?:essary)?\.?\s+(?P<a>\d)\s*/\s*(?P<b>\d)\b", re.I)


def _fraction(src, more=False):
    """(a, b) where the words say a motion needed a / b of a vote, else None;
    with `more`, the 1989-1998 clerk's "FAILS 3/5" too."""
    th = (THRESHOLD.search(src or "") or THRESHOLD_AFTER.search(src or "")
          or (THRESHOLD_FAILS.search(src or "") if more else None))
    if th:
        a, b = int(th.group("a")), int(th.group("b"))
        return (a, b) if 0 < a < b else None
    tw = THRESHOLD_WORDS.search(src or "")
    if tw:
        return (2, 3) if tw.group("f").lower() == "thirds" else (3, 5)
    return None


def _needs(it, frac):
    """Set the motion's supermajority from a fraction (_fraction)."""
    if frac == (3, 5):
        it.fifths = True
    elif frac:
        tot = (it.yeas or 0) + (it.nays or 0)
        if tot:
            # Of those voting, rounded up: two thirds of 23 is 15.33, and it
            # takes 16.
            it.need = -(-tot * frac[0] // frac[1])

# TWO THIRDS AND THREE FIFTHS ARE OF DIFFERENT THINGS. Two thirds is of those
# voting, which the tally beside it gives. Three fifths -- passing a
# constitutional amendment -- is of the members IN OFFICE, and only the ballots
# of a roll call say how many that was: 239 of the 397 then seated carried
# CACR 26 in 2012, where three fifths of those voting would have been 212. So a
# three-fifths mark is taken from rollcalls.json, which rollcall_outcomes
# worked out from those ballots, and where no roll call carries one -- a
# division, where nobody's ballot was recorded -- no mark is drawn at all.
ROLLCALLS = "rollcalls.json"

# A VETO VOTE IS A FLOOR VOTE, AND IT IS THE BIGGEST ONE OF THE YEAR.
#
# narratives.json types these `veto_override` rather than `floor`, so taking
# only `floor` left every one of them off every sitting page -- 387 of them,
# 1989 to 2026. 19 August 2026 was veto day: the House took twenty-six
# override roll calls and the Senate fourteen, and the page for it read "1
# action on 1 bill".
#
# They carry no action, motion, vote_kind, yeas or nays at all. Everything is
# in the prose, in six spellings across the decades:
#
#   Veto Sustained 08/19/2026: RC 204-116 Lacking Necessary Two-Thirds Vote
#   Veto Overridden 08/19/2026: RC 231-88 by Required Two-Thirds Vote
#   GOVERNOR'S VETO SUSTAINED RC(215-157); HJ63,P1761-1764
#   GOVERNOR'S VETO OVERRIDDEN, RC(249-87); HJ97,P2806-2809
#   Governor's Veto Sustained RC(19-261); HJ77, p2084-2086
#   Notwithstanding the Governor's Veto, Shall SB 213 Become Law: RC 0Y-24N,
#     Veto Sustained, lacking the necessary two-thirds
#
# THE OUTCOME IS ALWAYS STATED IN WORDS, so it is read from the words and
# never from the tally. It has to be: an override needs two thirds, so the
# larger number loses constantly here. HB 396 was 204 to 116 and the veto was
# SUSTAINED; HB 1072 was 160 to 159 and sustained; HB 1102 was 231 to 88 and
# overridden. A parser taking the bigger number as the winner would report the
# opposite of the truth on most of a veto day.
# WHICH CALENDAR THE BILL WAS ON, which is the committee's own choice and is
# recorded in its report: "(Vote 18-0; RC)" is the Regular Calendar and
# "(Vote 5-0; CC)" the Consent. NOT a roll call -- RC here is a calendar, and
# reading it as a vote kind would label most of a sitting wrongly.
#
# A bill on the consent calendar is disposed of without debate, as part of one
# motion covering dozens at a time, so it belongs in a list rather than in the
# sequence: 76 of the 117 bills the House dealt with on 6 March 2025 went that
# way, and printing them as 76 separate entries buries the 41 it actually
# debated.
ON_CONSENT = re.compile(r"[;(]\s*CC\b")

# A REPORT'S CC PLACES THE BILL ON ONE CALENDAR, IN ONE CHAMBER, ON ONE DAY.
#
# This used to mark every later floor action on a bill as a consent item, in
# either chamber and for as long as the bill's last committee report said CC.
# The veto day of 19 August 2026 listed a failed motion to reconsider HB 396
# as "disposed of together, in one motion and without debate"; a House report's
# CC followed its bill into the Senate, onto Senate pages from 2003 to 2010 --
# years whose Senate Journals never mention a consent calendar; and a motion to
# table, moved by a named member and carried on a roll call, was listed as
# consent. The rule below is scored against the consent sections the House and
# Senate Journals print, which is the chamber's own list of what the calendar
# held. floor_items() applies it.
#
# WHAT A CONSENT CALENDAR ADOPTS IS A COMMITTEE'S REPORT, so the only floor
# action that can be a consent item is the one that disposes of the bill the
# way the report recommended: kill it, pass it, send it to interim study or
# back to committee. Everything else -- a motion to table, to reconsider, to
# move the bill to another day -- is a member's motion about the bill, taken
# on its own.
# "Ought Not to Pass" is a committee's report on a bill of address (HA 1 of
# 2018 was on the consent calendar of 6 March); "Inexepdient" is the clerk's.
REPORT_ADOPTED = re.compile(
    r"^\s*(?:inex|ought\s+(?:not\s+)?to\s+(?:pass|adopt)|otp\b|itl\b|pass(?:ed)?\b|"
    r"adopt(?:ed)?\b(?!\s+amendment)|interim\s+study|"
    r"ref(?:er(?:red)?)?\.?\s+(?:[\w&.,' ]{0,40}\s)?(?:for|to)\s+interim\s+study|"
    r"re-?\s*refer|rereferred)", re.I)

# "Removed from Consent (Rep. Stone)", "REMOVED FROM CC, REQ REP SYTEK",
# "HB 60 was Removed from the Consent Calendar". narratives.json types only
# some of these consent_off: 346 House and 12 Senate rows of this kind arrive
# as "other", and nine 1989 floor rows carry the removal inside the action.
#
# THE HISTORIES' OWN READER, not a second one. This page had a pattern of its
# own, "removed from" and then the calendar, and it did not read the Senate's
# "Sen. D'Allesandro Moved to Remove SB 58 from the Consent Calendar" (2011 to
# 2024) or the House's "REMOVED FROM CON CAL" of 1992, which the history's
# note beside the same bill did: on 2 October 2026 the sitting pages listed
# 93 bills under "On the consent calendar ... without debate" at the sitting
# where their chamber had taken them off it.
# narrative.removed_from_consent is the one list of the wordings, so a
# wording read for the note is read here too. What it leaves out on purpose
# -- a special order about the bills removed, a conference report's
# calendar, the Senate's Laid on the Table Consent List -- changes no
# sitting: those special orders are floor rows a member moved, and use the
# report up themselves.
def came_off(raw):
    """Does this docket row take its own bill off a consent calendar?"""
    return narrative.removed_from_consent(raw)


# The day a removal row writes, where it writes one: "Removed from Consent
# (Rep. Hoell) 01/26/2017 HJ 4 P. 2" (CACR 5 of 2017), entered on 2 February.
WRITTEN_DAY = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")

# A SUSPENSION OF THE RULES IS NOT THE BILL'S DISPOSITION. "Reps Hess &
# Nordgren Susp Rules for late ref to Finance" came before six consent bills
# of 25 March 2003 were passed on the calendar, and "REPS WHEELER & BURLING
# SUSP RULES FOR DEADLINE" before four of 20 May 1998. It neither uses up the
# report nor is a consent item itself -- but only on the day it was taken: a
# bill whose deadline was suspended and which came back a week later was
# taken up on its own.
SUSPENDS = re.compile(r"\bsusp(?:end(?:ed|s)?|ension|en)?\b|rules\s+suspen", re.I)

# The clerk sometimes says it in the floor row itself: "ITL Report Adopted (CC
# by nec 2/3)", "PASSED WITH AM/CONSENT CAL RC(270-60)", "Ought to Pass: MA
# Div 282-9 (Consent Calendar)".
SAID_IN_ROW = re.compile(r"\(\s*(?:CC|Cons(?:ent)?\.?\s+Cal\w*)\b|/\s*CONSENT\s+CAL\b",
                         re.I)

# A second committee's report is typed "other" in some years: "ED&A MAJ
# REPORT OTP/AM FOR MAR26 (VOTE 12-0;CC)".
REPORT_ROW = re.compile(r"\bREPORT\b", re.I)

# THE SENATE SOMETIMES DATES ITS REPORT ROW AFTER THE VOTE. "Committee
# Report: Ought to Pass, 05/16/2024; Vote 5-0; CC" follows the Senate's
# consent calendar of 15 May 2024, which the Senate Journal prints with that
# bill on it. A disposition with no report before it takes the chamber's next
# row when that is a CC report dated within this many days; without it, 64
# bills the Senate Journals print on a consent calendar were left off.
REPORT_LAG_DAYS = 2


def on_consent_calendar(report, e, item):
    """Was this floor action the chamber adopting a consent-calendar report?

    `report` is the committee report this is the first floor action after, or
    None when another action, or a row saying the bill was removed from the
    consent calendar, came between them.
    """
    if report is None or item.veto:
        return False
    if (report.get("body") or "").strip().upper() != \
            (e.get("body") or "").strip().upper():
        return False
    # A member who moves something is not adopting the committee's report.
    if item.mover:
        return False
    return bool(REPORT_ADOPTED.match(item.action or ""))


def _reported_after(events, n, e, item):
    """The chamber's own CC report, entered a day or two after the vote."""
    if item.veto or item.mover or not REPORT_ADOPTED.match(item.action or ""):
        return False
    body = (e.get("body") or "").strip().upper()
    try:
        voted = _date.fromisoformat((e.get("date") or "")[:10])
    except ValueError:
        return False
    for f in events[n + 1:]:
        if (f.get("body") or "").strip().upper() != body:
            continue
        if f.get("type") in ("floor", "veto_override") and not f.get("cancelled"):
            return False
        if f.get("type") == "report":
            try:
                lag = (_date.fromisoformat((f.get("date") or "")[:10]) - voted).days
            except ValueError:
                return False
            return (0 <= lag <= REPORT_LAG_DAYS
                    and bool(ON_CONSENT.search(f.get("raw") or "")))
    return False


def _one_counted_vote(items, calendars=frozenset()):
    """A consent calendar is ONE motion, so a counted vote on it is one tally
    shared by every bill on it.

    The Senate took the whole calendar by roll call through 2021 -- 23 to 1
    on 22 April 2021, and every bill on it carries that tally -- and the
    House divided on its calendar of 25 March 2014, 282 to 9. A roll call or
    division that belongs to one bill alone was a vote on that bill, taken
    after it came off the calendar, and is not a consent item.

    UNLESS THE ROLL-CALL FILE SAYS IT WAS THE CALENDAR. `calendars` is the
    {(yeas, nays)} of the roll calls the file words as the day's consent
    calendar (_calendar_rollcalls). The Senate took two bills off its
    calendar of 18 February 2021 ("Sen. Sherman Moved to Remove SB 120 from
    the Consent Calendar", and SB 38), which left SB 103 on it alone, and
    adopted it 24 to 0, the file's #55 "Consent Calendar": a lone bill with
    the calendar's count was the calendar, and was drawn as a vote of its own
    beside #55 among the votes on no bill -- one roll call twice, and an
    opening of 26 for the file's 25.
    """
    counted = collections.Counter((i.kind, i.yeas, i.nays) for i in items
                                  if i.consent and i.kind in ("RC", "DV"))
    for i in items:
        if i.consent and i.kind in ("RC", "DV") and \
                counted[(i.kind, i.yeas, i.nays)] < 2 and \
                not (i.kind == "RC" and (i.yeas, i.nays) in calendars):
            i.consent = False


# A roll call the file words as the consent calendar itself: "Consent
# Calendar", "Adoption of the Consent Calendar" (the Senate, 2021). Not the
# House's "Rules Suspension, Adopt CC", which was a suspension.
CALENDAR_Q = re.compile(r"^\s*(?:adoption\s+of\s+the\s+)?consent\s+calendar\s*$", re.I)


def _calendar_rollcalls(rolls):
    """{(body, date): {(yeas, nays)}} of the roll calls on a consent calendar,
    by the ballots' count and by the count the summary stated, since the
    docket line may carry either."""
    out = collections.defaultdict(set)
    for bills in (rolls.values() if isinstance(rolls, dict) else []):
        for rows in bills.values():
            for r in rows:
                if not CALENDAR_Q.search(r.get("question") or ""):
                    continue
                for y, n in {(r.get("yeas"), r.get("nays")),
                             (r.get("yeas_stated"), r.get("nays_stated"))}:
                    if y is not None and n is not None:
                        out[(r.get("body"), r.get("date"))].add((y, n))
    return out


VETO_TALLY = re.compile(r"\bRC\s*\(?\s*(?P<y>\d+)\s*Y?\s*-\s*"
                        r"(?P<n>\d+)\s*N?\s*\)?", re.I)
# THE RESULT, NEVER THE QUESTION. "OVERRIDE GOV VETO, ML RC(17-299)" (HB 149,
# 25 June 1997) names the motion, and read for "overrid" the page said the
# veto was overridden; nine failed overrides of 1997-1998 read so. A failure
# word decides first -- the veto sustained, the motion lost (ML), FAILED or
# FAILS 2/3 -- and only then the veto overridden, the motion adopted (MA), or
# the bill became law.
OVERRIDDEN = re.compile(r"\boverridden\b|\bMA\b|\bbecame\s+law\b", re.I)
SUSTAINED = re.compile(r"\bsustain|\bML\b|\bfail", re.I)


def _veto(e, item):
    """Fill an Item from a veto row, which states everything in prose."""
    raw = (e.get("raw") or "").strip()
    item.action = "Override the Governor's veto"
    if SUSTAINED.search(raw):
        item.carried = False
    elif OVERRIDDEN.search(raw):
        item.carried = True
    m = VETO_TALLY.search(raw)
    if m:
        item.kind = item.kind or "RC"
        item.yeas, item.nays = int(m.group("y")), int(m.group("n"))
        tot = item.yeas + item.nays
        # Two thirds of those voting, rounded up: 2/3 of 319 is 212.67 and it
        # takes 213. Part II, Article 44.
        item.need = -(-tot * 2 // 3)
    item.veto = True


class Item:
    """One thing the chamber did to one bill, at one point in the day."""

    __slots__ = ("bill", "term", "action", "mover", "carried", "kind",
                 "yeas", "nays", "cite", "page", "raw", "seq", "need", "veto",
                 "consent", "fifths", "entered", "recess", "joined",
                 "rc", "said", "added", "plain", "shared", "stated_kind")

    def __init__(self, bill, term, e, seq):
        # The roll call on record this motion is (rollcalls.json's row), or
        # None; tie() sets it, and with it the ballots' count and outcome.
        self.rc = None
        # The kind of vote the docket line stated, where tie() drew it as a
        # roll call: a "DV" the House Journal confirms is kept (_divisions).
        self.stated_kind = ""
        # The count the docket line states, where the page draws the
        # ballots' instead: speeches are tied to a motion by the journal's
        # count, which is the docket's more often than the ballots'.
        self.said = None
        # Not a floor row of the docket: "row" a question decided on a row of
        # another type or in another clause of a floor line, "rollcall" one
        # the roll-call file alone records (_roll_calls, below).
        self.added = ""
        # True where nothing should be said of what the motion did to the
        # bill: an amendment or a committee of conference report adopted is
        # the motion adopted, and the bill's fate is another question.
        self.plain = False
        # How many bills' motions this one roll call is drawn under that day,
        # where it is more than one: a motion covering several bills is
        # entered on each bill's docket and is one vote.
        self.shared = 0
        self.bill = bill
        self.term = term
        self.action = (e.get("action") or "").strip()
        self.mover = (e.get("mover") or "").strip()
        self.carried = CARRIED.get((e.get("motion") or "").strip().upper())
        self.kind = (e.get("vote_kind") or "").strip().upper()
        self.yeas = _int(e.get("yeas"))
        self.nays = _int(e.get("nays"))
        self.cite = (e.get("cite") or "").strip()
        self.page = _int(e.get("cite_page"))
        self.raw = (e.get("raw") or "").strip()
        # A line the 1999-2006 docket reader joined back together from rows
        # the database cut it into: how many floor actions those rows were
        # read as one by one, where more than one (narrative's "joined"),
        # else 0.
        self.joined = _int(e.get("joined")) or 0
        self.seq = seq
        self.need = None
        self.veto = False
        self.consent = False
        # Three fifths, whose count only the roll call's ballots give; load()
        # fills self.need from rollcalls.json where it can.
        self.fifths = False
        # The day the docket enters a row load() placed on the sitting whose
        # journal prints it; None for every other row. `recess` says whether
        # the docket's own words put it in that sitting's recess, which is
        # what the page may then say; the rest are placed by the journal.
        self.entered = None
        self.recess = False
        if e.get("type") == "veto_override":
            _veto(e, self)
            return

        # What the fields did not carry, the prose sometimes does. Read from
        # `raw` rather than `action` because the clerk puts the outcome after
        # the tally -- "RC 19Y-5N, 3/5 nec., MA" -- and `action` is cut before
        # it on some rows and not others.
        #
        # NOT A COUNT FOR A VOICE VOTE. A voice vote has none, so where the
        # fields say VV they carry all there is, and a count elsewhere on the
        # line is another question's: "Ought to Pass, RC 4Y-16N, MF, Sen.
        # Fernald Moved Laid on Table, MF, VV" (HB 661 of 1999) is passage
        # failing 4 to 16 and then a tabling motion failing by voice, and the
        # page said of the tabling "A voice vote: 4 yeas, 16 nays". 28 Senate
        # motions of 1999-2008 read that way on 1 October 2026, among them
        # kills "adopted" with the failed passage's count drawn beside them.
        src = self.raw or self.action
        if not self.kind or (self.yeas is None and self.kind != "VV"):
            m = INLINE_VOTE.search(src)
            if m:
                self.kind = self.kind or {"DIV": "DV", "DIV.": "DV"}.get(
                    m.group("kind").upper(), m.group("kind").upper())
                if self.yeas is None:
                    self.yeas, self.nays = int(m.group("y")), int(m.group("n"))
        if self.kind == "DV" and self.yeas is None:
            m = DIV_COUNT.search(src)
            if m:
                self.yeas, self.nays = int(m.group("y")), int(m.group("n"))
        # A voice vote has no count, and one the line states is a division's:
        # "Ought to Pass: Div. 16Y-8N, MA, VV; OT3rdg" (HB 1723, 2 May 2012)
        # read "A voice vote: 16 yeas, 8 nays".
        if self.kind == "VV" and self.yeas is not None and \
                re.search(r"\bDiv(?:ision)?\.?\s*\d+\s*Y", src, re.I):
            self.kind = "DV"
        _needs(self, _fraction(src))
        words = INLINE_COUNT.sub("", self.action)
        if words != self.action:
            self.action = words.strip(" ,;:") or self.action

    @property
    def threshold_needed(self):
        """Votes needed to carry, which is not always half plus one -- or
        None where it was three fifths of a count the record does not give."""
        if self.need:
            return self.need
        if self.fifths:
            return None
        tot = (self.yeas or 0) + (self.nays or 0)
        return (tot // 2) + 1 if tot else 0

    @property
    def threshold_unknown(self):
        """More than a majority was needed, and of how many is not known."""
        return self.fifths and not self.need

    @property
    def kind_words(self):
        return VOTE_KIND.get(self.kind, "")

    @property
    def counted(self):
        """Is there a tally to draw? A voice vote has none, and that is not a
        gap in the record -- nobody counted, which is what a voice vote is."""
        return self.yeas is not None and self.nays is not None

    @property
    def tallies(self):
        """Every count this motion is known by: the one drawn, and the
        docket's where the page draws the ballots' instead."""
        out = set()
        if self.counted:
            out.add((self.yeas, self.nays))
        if self.said:
            out.add(self.said)
        if self.rc and self.rc.get("yeas_stated") is not None:
            out.add((self.rc["yeas_stated"], self.rc["nays_stated"]))
        return out

    @property
    def outcome_words(self):
        """'The motion was adopted on a voice vote -- the bill was killed.'"""
        if self.carried is None:
            return ""
        verb = "was adopted" if self.carried else "failed"
        how = f" on a {self.kind_words}" if self.kind_words else ""
        tail = None if self.plain else _consequence(self.action, self.carried)
        return (f"The motion {verb}{how}"
                + (f" — {tail}." if tail else "."))

    def __repr__(self):
        return f"<Item {self.bill} {self.action!r} {self.kind} p{self.page}>"


class Day:
    """One chamber, one date, and everything it did to bills that day."""

    __slots__ = ("body", "date", "items", "journal", "ordered", "others", "printed")

    def __init__(self, body, date, items, others=()):
        self.body = body
        self.date = date
        self.items = items
        # The votes the chamber's journal prints in this sitting
        # (_journal_day), where load() read them; None otherwise.
        self.printed = None
        # The roll calls of the day that were on no bill -- the chamber's own
        # rules, a ruling of the chair, whether to print remarks -- as Items
        # whose bill is "". Never in `items`: they belong to no bill's card.
        self.others = list(others)
        # IS THIS THE ORDER IT HAPPENED IN? Only where the journal page says
        # so. 24% of House actions cite one and 0.3% of Senate actions do, so
        # a Senate day is a LIST of what the chamber did and not a sequence,
        # and the page must say that rather than implying an order the record
        # does not hold. Judged on the docket's floor rows, as it always was:
        # a roll call drawn from the roll-call file cites no page and says
        # nothing about the order of the rest.
        own = [i for i in items if not i.added] or items
        self.ordered = sum(1 for i in own if i.page is not None) > len(own) / 2
        # "HJ 4" -- the journal number this day is printed in. Taken from the
        # items rather than asserted, and only when they agree: a day whose
        # rows cite two different journals is telling us something and should
        # not be flattened into one of them.
        # Not from a row placed here from the day the docket enters it: HB
        # 517's report, entered on 26 March 2025 at "HJ 10", is printed in
        # House Journal 11 with the sitting of the 27th, which lost its
        # journal to the second number.
        cites = {i.cite for i in own if i.cite and not i.entered} or \
            {i.cite for i in own if i.cite}
        self.journal = cites.pop() if len(cites) == 1 else ""

    @property
    def bills(self):
        # One per BILL, and a bill is a number within a term: the House
        # organization day of 1 December 2004 took up HR 1 of both terms.
        return sorted(b for _, b in {(i.term, i.bill) for i in self.items})

    def split(self, removed=()):
        """(debated, consent) -- the day's sequence, and its consent list.

        `removed` is the bills the journal says members pulled off the consent
        calendar; any member may, and a bill that came off was debated like
        any other, so it goes back into the sequence.
        """
        off = {str(b).split("-")[0].upper() for b in removed}
        keep, cons = [], []
        for i in self.items:
            if i.consent and i.bill.upper() not in off:
                cons.append(i)
            else:
                keep.append(i)
        return keep, cons

    def votes(self, kind="RC"):
        """{key: [Item, ...]} -- the distinct counted votes of one kind the
        day draws, each with the motions it is drawn under.

        A VOTE IS COUNTED ONCE, HOWEVER MANY BILLS IT IS DRAWN UNDER. The
        opening said "43 roll calls" for the House on 30 April 2014, which
        took ten: one motion to reconsider the third reading of 35 Senate
        bills was entered on each bill's docket and counted 35 times. A
        consent calendar is one motion, and the Senate took it by roll call
        through 2021, so 22 April 2021 said 49 where the Senate took 19. Kept
        apart: a roll call on record by its number; a consent calendar's
        count; one motion entered on several bills' dockets with the same
        words and count, which the roll-call file holds as one vote or not
        at all; and everything else, one by one.
        """
        out = {}
        bills = collections.defaultdict(set)
        pages = collections.defaultdict(set)
        for i in self.items:
            if i.kind == kind and i.rc is None and i.counted and not i.consent:
                key = (_motion_key(i.action), i.yeas, i.nays)
                bills[key].add((i.term, i.bill))
                cited = CITED_PAGES.search(i.raw or "")
                pages[key].add((i.cite, i.page,
                                re.sub(r"\s+", "", cited.group(0)).upper() if cited else None))
        on_file = self.date >= ROLLCALLS_FROM.get(self.body, "9999")
        for i in list(self.items) + self.others:
            if i.kind != kind:
                continue
            key = (_motion_key(i.action), i.yeas, i.nays)
            if i.rc is not None:
                k = ("rc",) + rollcall_key(i.rc)
            elif i.consent and i.counted:
                k = ("consent", i.yeas, i.nays)
            # Before the roll-call file, only a motion that can be one on
            # several bills: "REP COOPER MOVED TO LAY REMAINDER OF CAL ON
            # TABLE, ML RC(133-163)" is entered on eight bills of 24 September
            # 1998 and was counted eight times. A division is never on the
            # file, and is held to the same: the resolution of 30 April 2014
            # that read 35 Senate bills a third time on one division made
            # the opening say 38 divisions where the House took 4.
            elif (i.counted and len(bills[key]) > 1
                  and ((kind == "RC" and on_file)
                       or (question_kind(i.action) not in UNSHARED
                           and self._one_vote(key, len(bills[key]), pages[key])))):
                k = ("motion",) + key
            else:
                k = ("item", id(i))
            out.setdefault(k, []).append(i)
        return out

    def _one_vote(self, key, n, pages):
        """Is one count, entered with the same words on n bills, one vote?
        ONLY WHERE THE RECORD SAYS SO: the day's journal prints it fewer
        times than it is entered, or, with no journal on disk, every row
        cites the same journal page (CITED_PAGES: "REP COOPER MOVED TO LAY
        REMAINDER OF CAL ON TABLE, ML RC(133-163) HJ78,P2521-2523" on each
        of eight bills). HB 1194's and HB 1660's reconsiderations of 7 March
        2024 each failed on a division of 171-192, and the journal prints
        both; the Senate's third readings of SB 45 and SB 57, each lost 10-14
        on 20 February 1997 and cited at SJ6 P83 and P82-83, are two roll
        calls, and the page drew one "on 2 bills"."""
        j = self.printed
        if j is not None:
            printed = j["div"].get(key[1:], 0) + j["rc"].get(key[1:], 0)
            return 0 < printed < n
        cite = next(iter(pages)) if len(pages) == 1 else (None, None, None)
        return cite[1] is not None or cite[2] is not None

    def counts(self):
        """{"roll call": n, "division": n, "voice vote": n} -- each counted
        vote once (votes(), above), each voice vote as the docket enters it."""
        c = collections.Counter(i.kind for i in self.items
                                if i.kind and i.kind not in ("RC", "DV"))
        for k in ("RC", "DV"):
            n = len(self.votes(k))
            if n:
                c[k] = n
        return {VOTE_KIND.get(k, k): v for k, v in c.items()}

    def __len__(self):
        return len(self.items)

    def __repr__(self):
        return (f"<Day {self.body} {self.date} {len(self.items)} items "
                f"on {len(self.bills)} bills>")


def _int(v):
    try:
        s = str(v).strip()
        return int(s) if s and s.lstrip("-").isdigit() else None
    except (TypeError, ValueError):
        return None


def floor_items(bill, term, events):
    """[(event, Item)] for each floor action of one bill, in the record's
    order, each Item's `consent` saying whether the chamber disposed of it on
    its consent calendar. The day-level half of the rule, _one_counted_vote,
    runs in load() once a day's items are together.

    A committee report marked CC is PENDING until the bill's next floor
    action, which uses it up. That action is a consent item only if it is in
    the report's own chamber, has no named mover, is not a veto vote, and
    disposes of the bill the way a report does. A row saying the bill was
    removed from the consent calendar clears the report; a suspension of the
    rules taken the same day leaves it in place.

    AND NOTHING THE CHAMBER DID TO THE BILL AT ITS NEXT SITTING ON IT AFTER IT
    TOOK THE BILL OFF IS A CONSENT ITEM, wherever the removal row stands. The
    clerk enters some of them after the bill's own disposition: "SB 74-FN was
    Removed from the Consent Calendar; 03/20/2025" was entered at 1:00 PM,
    twenty minutes after Senator Pearl's floor amendment to it, and the
    Senate's sitting of 20 March 2025 listed SB 74 among the bills it
    "disposed of together, in one motion and without debate"; "Sen. Sherman
    Moved to Remove HB 703-FN from the Consent Calendar; 05/15/2019" was
    entered on 4 June. The day is the one the row writes, or its own where it
    writes none, and the sitting is the chamber's first on the bill from then
    -- unless a report of that chamber came between, which is a new report on
    a new calendar: HB 442 of 1989 came off in April, went back to its
    committee, and passed on the consent calendar of 4 January 1990 on the
    report the committee made in November.
    """
    out = []
    events = events or []
    sat, reported = collections.defaultdict(set), collections.defaultdict(set)
    for x in events:
        ch, d = (x.get("body") or "").strip().upper(), (x.get("date") or "")[:10]
        if x.get("type") in ("floor", "veto_override") and not x.get("cancelled"):
            sat[ch].add(d)
        elif x.get("type") == "report" or REPORT_ROW.search(x.get("raw") or ""):
            reported[ch].add(d)
    off_on = set()
    for x in events:
        if x.get("cancelled") or not (x.get("type") == "consent_off"
                                      or came_off(x.get("raw"))):
            continue
        ch = (x.get("body") or "").strip().upper()
        m = WRITTEN_DAY.search(x.get("raw") or "")
        d = _mdy(m.group(0)) if m else None
        since = d.isoformat() if d else (x.get("date") or "")[:10]
        nxt = min((s for s in sat[ch] if s >= since), default=None)
        if nxt and not any(since < r <= nxt for r in reported[ch]):
            off_on.add((ch, nxt))
    pending, suspended_on = None, None
    for n, e in enumerate(events):
        kind = e.get("type")
        raw = e.get("raw") or ""
        floor = kind in ("floor", "veto_override")
        if kind == "report" or (kind == "other" and REPORT_ROW.search(raw)
                                and ON_CONSENT.search(raw)):
            pending = e if ON_CONSENT.search(raw) else None
            suspended_on = None
        elif kind == "consent_off" or (not floor and came_off(raw)):
            pending = None
        if not floor or e.get("cancelled"):
            continue
        it = Item(bill, term, e, 0)
        out.append((e, it))
        day = (e.get("date") or "")[:10]
        if (suspended_on and day != suspended_on) or came_off(raw):
            pending = None
        if not it.veto and SUSPENDS.search(it.action or raw):
            suspended_on = suspended_on or day
            continue
        report, pending = pending, None
        it.consent = ((e.get("body") or "").strip().upper(), day) not in off_on and (
            on_consent_calendar(report, e, it)
            or (not it.veto and not it.mover and not came_off(raw)
                and bool(SAID_IN_ROW.search(raw)))
            or (report is None and _reported_after(events, n, e, it)))
    return out


def _fifths_from_rollcalls(path=ROLLCALLS):
    """{(body, date, yeas, nays): {threshold_needed}} for the roll calls whose
    threshold is three fifths, by the ballots' tally and by the tally the
    General Court's summary stated, since the docket line may carry either.
    A set, so that two roll calls on one day with the same count but
    different thresholds answer nothing rather than the wrong one. `path`
    may be rollcalls.json already read."""
    out = collections.defaultdict(set)
    data = _read_rollcalls(path)
    for bills in (data.values() if isinstance(data, dict) else []):
        for rows in bills.values():
            for r in rows:
                if "three fifths" not in (r.get("threshold_rule") or ""):
                    continue
                for y, n in {(r.get("yeas"), r.get("nays")),
                             (r.get("yeas_stated"), r.get("nays_stated"))}:
                    if y is not None and n is not None:
                        out[(r.get("body"), r.get("date"), y, n)].add(
                            r.get("threshold_needed"))
    return out


# ------------------------------------------------- business done in recess --
#
# A SITTING DOES NOT END WITH ITS DAY. A chamber that recesses rather than
# adjourns is still in that sitting when it next does business, and the
# journal prints that business with the sitting: House Journal 49 of 5 June
# 2013 prints under RECESS, at pages 1649 to 1653, the House refusing Senate
# amendments on 11 to 13 June; the Senate Journal of 6 May 2004 prints at
# page 466 its accession to a House request made on 13 May, and the Senate
# came "Out of Recess" from 6 May only on the 25th. The docket enters each row
# on the day it was done and says whose recess it was:
#
#   "... MA VV [Recess of 6/5/13]; HJ49, PG.1650"                  12 June 2013
#   "... MA VV (In recess of 5/15/14)"                              21 May 2014
#   "... MA VV; [Recessed from 5/17/2012 Session]"                  24 May 2012
#   "Senator Peterson Accede to House Request for C of C,
#    MA, VV [05/06/04]"                                             13 May 2004
#
# Dated by the entry, 79 such rows made ten pages of their own -- "The House,
# Wednesday 12 June 2013" -- for days the chamber did not sit. The person
# decided on 24 September 2026 that business done in recess is shown on the
# sitting it belongs to, as the journal shows it, so load() puts it there and
# the page says the day the docket enters it. The bill's own history keeps
# the docket's date, and must: dated by the sitting, the House would refuse
# a Senate amendment the day before the Senate made it (docket_vocab.as_of).
#
# The bare bracketed date is the clerk's as-of date, the shape docket_vocab
# .AS_OF reads; narrative.hold_in_order refuses it for the bill's history
# exactly when it would put an answer ahead of its question, which is what
# recess business looks like, and every one of those rows cites the journal
# of the sitting it names. Two of 2005 say "[06/09/04]" beside nine saying
# "[06/09/05]" on the same afternoon's accessions, and the Senate Journal's
# continuation of 9 June 2005 prints the two among the other nine: a slipped
# year, read as the row's own.
#
# ONLY ONTO A SITTING THE RECORD ALREADY HOLDS, only a few weeks back, and
# only where the row's own journal citation, if it has one, is that
# sitting's. Anything else stays on the day the docket gives it.
RECESS_OF = re.compile(
    r"[\[(]\s*(?:in\s+)?recess(?:ed)?\s+(?:(?:of|from)\)?\s*)?"
    r"(?P<d>\d{1,2}/\d{1,2}/\d{2,4})", re.I)
AS_OF = re.compile(r"\[\s*(?P<d>\d{1,2}/\d{1,2}/\d{2,4})\s*\]"
                   r"|\(\s*as\s+of\s+(?P<e>\d{1,2}/\d{1,2}/\d{2,4})\s*\)", re.I)
AS_OF_NOT = re.compile(r"special order|deadline|reporting date|extended to|"
                       r"rept date", re.I)
RECESS_DAYS = 31


def _mdy(s):
    mo, dy, yr = (int(x) for x in s.split("/"))
    if yr < 100:
        yr += 2000 if yr < 50 else 1900
    try:
        return _date(yr, mo, dy)
    except ValueError:
        return None


def recess_sitting(e):
    """The earlier date of the sitting this floor row was done in the recess
    of, as the docket states it, or None. load() decides whether to use it."""
    raw = e.get("raw") or ""
    try:
        own = _date.fromisoformat((e.get("date") or "")[:10])
    except ValueError:
        return None
    m = RECESS_OF.search(raw)
    when, slip = (_mdy(m.group("d")), False) if m else (None, False)
    if when is None and not AS_OF_NOT.search(raw):
        m = AS_OF.search(raw)
        when, slip = (_mdy(m.group("d") or m.group("e")), True) if m else (None, False)
    if when is None:
        return None
    if slip and when.year == own.year - 1:
        try:
            when = when.replace(year=own.year)
        except ValueError:
            return None
    if not 0 < (own - when).days <= RECESS_DAYS:
        return None
    return when.isoformat()


# MOST RECESS BUSINESS IS NOT MARKED AT ALL. "House Non-Concurs with Senate
# Amendment 2024-1621s and Requests CofC (Rep. Ladd): MA VV 05/24/2024" says
# nothing of a recess, and cites HJ 14; House Journal 14 prints it under
# RECESS, after "The House recessed at 7:15 p.m." on 23 May, with the other
# thirty-eight refusals the docket spread over 24, 28, 29 and 30 May. The
# House's motion names what a recess is for -- "the introduction of bills,
# enrolled bill amendments, enrolled bill reports, receiving messages and
# forming Committees of Conference" -- and of that, what reaches the docket as
# a floor row is a refusal of the other chamber's amendment, an accession to
# its request for a committee of conference, or an enrolled bill amendment:
# RECESS_BUSINESS. ("HOUSE NONC WITH SEN AM REQ CONF COMM" is 1997's.)
#
# Such a row goes to the sitting whose journal it cites when that journal is
# an earlier sitting's -- the first day the record cites it, no more than
# RECESS_DAYS back and holding more of its rows than the row's own day -- and
# the row's day is plainly no sitting of its own in that journal:
#
#   - a day of nothing else: every row recess business, none with a count,
#     since a recess takes no roll call or division, and all citing the one
#     journal. 24, 28 and 29 May 2024, 29 May 1997, 11 June 1998, 14 and 15
#     June 2001 and the Senate's 15 June 2005, each read in the journal on
#     disk; and 18 May 1994, which has none on disk, whose five accessions the
#     docket cites among the pages of 17 May's own. One such day is not
#     recess: 31 May 2012 holds a refusal the journal prints at the 30 May
#     sitting itself, entered a day late. It goes to 30 May all the same --
#     the House did not sit on the 31st -- and is why the page says only
#     that the journal prints a row with the sitting, unless the docket
#     itself says recess.
#   - or a row on a later sitting of its own, whose other rows cite a later
#     journal, when its page comes after every page the earlier sitting's own
#     rows cite, which is where a journal prints its recess: HB 1292 and
#     HB 468, entered on 30 May 2024 at HJ 14 page 181. Without a page this
#     is not attempted, because the number cited is not always the journal
#     that prints the row: the Senate's seven refusals entered on 21 May 2008
#     cite SJ 18, the 15 May journal, and are printed in the 21 May sitting,
#     in an issue numbered "Nos. 18-19".
RECESS_BUSINESS = re.compile(
    r"\bnon-?\s*conc|\bnonc\b|\bacced|\benrolled\s+(?:bill\s+)?am", re.I)


def _journal_key(body, date, cite):
    m = JOURNAL_NO.match(cite or "")
    if not m or m.group(1) != body:
        return None
    return (body, journal_series(date), int(m.group(2)))


def unmarked_recess(grouped):
    """[(body, date, sitting, item)] -- the rows of {(body, date): [Item]}
    that belong on an earlier sitting by the journal they cite (above)."""
    by_cite = collections.defaultdict(collections.Counter)
    pages = collections.defaultdict(list)
    for (body, date), items in grouped.items():
        for i in items:
            k = _journal_key(body, date, i.cite)
            if k:
                by_cite[k][date] += 1
                if i.page is not None and not i.entered:
                    pages[(k, date)].append(i.page)

    def sitting_of(k, date):
        c = by_cite[k]
        first = min(c)
        if (first < date and c[first] >= 3 and c[first] > c[date]
                and (_date.fromisoformat(date)
                     - _date.fromisoformat(first)).days <= RECESS_DAYS):
            return first
        return None

    def business(i):
        return bool(RECESS_BUSINESS.search(i.raw or i.action or ""))

    out = []
    for (body, date), everything in sorted(grouped.items()):
        # Not what an earlier step already moved onto this day, which makes
        # it a sitting in its own right.
        items = [i for i in everything if not i.entered]
        keys = [_journal_key(body, date, i.cite) for i in items]
        cited = set(keys) - {None}
        if (len(items) == len(everything) and len(cited) == 1
                and all(business(i) and not i.counted for i in items)):
            there = sitting_of(next(iter(cited)), date)
            if there:
                out += [(body, date, there, i) for i in items]
                continue
        for i, k in zip(items, keys):
            if not k or i.page is None or not business(i):
                continue
            there = sitting_of(k, date)
            theirs = pages.get((k, there)) if there else None
            same = [x for x, kx in zip(items, keys) if kx == k]
            other = sum(1 for kx in keys if kx and kx != k)
            if (theirs and i.page > max(theirs) and other > len(same)
                    and all(business(x) for x in same)):
                out.append((body, date, there, i))
    return out


# ------------------------------------------------ a rule's date, not a sitting --
#
# A BILL THAT DIES UNDER A JOINT RULE DIES ON A DATE, NOT AT A SITTING. The
# joint rules kill what is not acted on by a deadline, and the docket enters
# the death on the deadline: "INDEFINITELY POSTPONED BY JOINT RULE 24(B)" on
# Sunday 1 July 1990 for fifteen House and three Senate bills, and "PER JT
# RULE 23-A" on Saturday 1 July 1995 for eight. Each made a sitting page of
# its own -- "The House, Sunday 1 July 1990" -- on a day neither chamber sat.
# The person decided on 24 September 2026 that those days are not sittings;
# the rows stay in their bills' histories, where a bill dying is a fact. A
# weekday deadline is left alone, and so is a joint-rule row on a weekend
# the chamber did sit, since it is then the day's business that makes the
# sitting and not the rule.
JOINT_RULE = re.compile(r"\b(?:by|per|under)\s+j(?:oin)?t\.?\s*rules?\b", re.I)


def _rule_only_weekend(date, items):
    return (_date.fromisoformat(date).weekday() >= 5
            and all(JOINT_RULE.search(i.raw or i.action or "") for i in items))


# ============================================== every roll call on record ==
#
# A SITTING PAGE DREW ONLY THE ROWS THE DOCKET READER TYPES AS FLOOR MOTIONS.
# Measured on 2 October 2026 against rollcalls.json, which holds every roll
# call the General Court's voting system recorded from 1999, 1,552 of 5,577
# House roll calls and 1,431 of 3,988 Senate ones were drawn on no sitting
# page, and the opening's count of roll calls was wrong on 363 House pages
# and 334 Senate ones. The Senate's page for 26 June 2025 said "1 roll
# call"; it took eleven, the budget's committee of conference reports among
# them. No one rule left them out:
#
#   - an amendment, a committee of conference report, a motion worded
#     without "MA" or "MF", a veto "Overriden": the docket reader types the
#     row as something other than a floor motion, and only floor motions
#     were read here;
#   - a 1999-2006 line holds several questions, and was one motion here;
#   - the docket and the roll-call file date a vote a day or more apart;
#   - the chamber's own rules, a ruling of the chair, whether to print a
#     debate: votes on no bill, where the page is built bill by bill;
#   - the docket says "voice vote" of a roll call, or has no row for it.
#
# So the roll calls on record are the list, and each is put where it belongs
# (_roll_calls): on the floor motion that is that vote; on a motion of its
# own, worded and dated from the docket row or clause that states it; and
# where no docket row states it, under its bill or among the day's votes on
# no bill, worded as the roll-call file words it. A roll call is paired with
# its docket tally as rollcall_outcomes pairs it for its outcome: within a
# day, the assignment that agrees on the most counts and keeps both in their
# order; then the same count anywhere in the term, on the same kind of
# question. Nothing is drawn that no roll call on record and no docket row
# states, and no debate or speaker is given to a vote the docket has no row
# for.

# Every counted tally the docket prints, in the punctuations the clerks used:
#   RC 239-114   RC(207-145)   RC (223-91)   RC 16Y-6N   RC: 16Y-8N
#   RC 12y - 12n   RC13Y-11N   Roll Call, 18y-4n   RC Y6- 17N   RC 18-Y-6N
#   RC 23Y-N0   RC 12Y-12F   RC 14Y-10   DIV(128-259)   Division 8Y-11N
# and the Senate's bare "19Y-5N" with no kind in front. A committee's
# "(Vote 11-5; RC)" names the Regular Calendar after its count, never a roll
# call before it, and is not read.
#   ... and the kind glued to its threshold: "COMM REPT: OTP/AM, FAILS
#   3/5RC(192-153)" (CACR 44, 24 September 1998), "MA 2/3DIV(296-27)".
TALLY = re.compile(
    r"(?:(?:\b|(?<=\d/\d))(?P<kind>RC|Rc|Roll\s+Call|DIV|Div|DV|Division(?:\s+Vote)?)"
    r"(?:\b|(?=\d))"
    r"\s*[-:,(]?\s*\(?\s*[Yy]?(?P<y>\d{1,3})\s*-?\s*[Yy]?\s*[-–]\s*[Nn]?"
    r"(?P<n>\d{1,3})\s*-?\s*[NnFf]?\b\s*\)?"
    r"|(?<![\w/{#-])(?P<y2>\d{1,2})\s*[Yy]\s*-\s*(?P<n2>\d{1,2})\s*[Nn]\b)")
DATE_IN = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
# A count with no kind at all, for the last look at a bill's own rows that
# day: "Reconsider 18-311 (Rep. H. Howard): MF DV 031126" (HB 1565 of 2026).
BARE = re.compile(r"(?<![\d/#.\w-])(?P<y>\d{1,3})\s*-\s*(?P<n>\d{1,3})(?![\d/\w])")
# Rows whose counts are a committee's, or no vote at all.
NOT_THE_FLOOR = ("report", "hearing", "exec", "worksession", "conference_meeting",
                 "interim_report")

# A quorum call puts no question: the House's "Call of the Roll" and the
# Senate's "Attendance", which the remote sittings of 2021 took by roll call.
# The journal prints no YEAS and NAYS for one, and it is not a vote.
QUORUM = re.compile(r"^\s*(?:call\s+of\s+the\s+roll|attendance|quorum)", re.I)

# Where the voting system began, for each chamber: before it, the docket is
# the only record of a roll call. Set from rollcalls.json by load(), and the
# file's own first days where it is not here: the House's first roll call on
# file is of 28 January 1999 and the Senate's of 11 February.
ROLLCALLS_BEGIN = {"H": "1999-01-28", "S": "1999-02-11"}
ROLLCALLS_FROM = dict(ROLLCALLS_BEGIN)

VETO_Q = re.compile(r"\bveto\b|become\s+law|notwithstanding|\boverrid", re.I)
SUSPEND_Q = re.compile(r"\bsusp", re.I)
THIRD_Q = re.compile(r"^(?:O[Tt]\s*3rd\w*\.?|Order(?:ed)?\s+to\s+(?:3rd|third)\s+Reading)\s*$",
                     re.I)
CONFERENCE_Q = re.compile(
    r"conf(?:erence)?\.?\s*comm(?:ittee)?\.?\s*(?:rep(?:ort)?|rpt)\b|committee\s+of\s+"
    r"conference|\bc\s*of\s*c\b|\bcofc\b|\bcoc\s+rep|conf\.?\s+rep(?:ort)?\b", re.I)
NOT_ADOPT = re.compile(r"\bnon[- ]?adopt|\bnot\s+adopt", re.I)
AMEND_Q = re.compile(
    r"(?P<kind>\bFLAM\b|\b(?:maj(?:ority)?|min(?:ority)?)\.?\s*(?:comm(?:ittee)?\.?\s*)?"
    r"(?:fl(?:oo)?r?\.?\s*)?am(?:end(?:ment)?)?\b\.?|\b(?:comm(?:ittee)?\.?\s*)?"
    r"fl(?:oo)?r?\.?\s*am(?:end(?:ment)?)?\b\.?|\bcomm(?:ittee)?\.?\s*am(?:end(?:ment)?)?\b\.?|"
    r"\bamend(?:ment)?\b\.?|\bam\b\.?)", re.I)
AMEND_NO = re.compile(r"(?:#\s*|[{(]\s*#?\s*)?(?P<no>(?:\d{4}-)?\d{4}[a-zA-Z]?)\b")
SECTIONS = re.compile(r"\b(?:remainder|rest|remaining|balance)\b.*|"
                      r"(?:\b\d+(?:st|nd|rd|th)\s+)?\bsec(?:tion)?s?\b\.?\s*[\w ,;&.-]*", re.I)
# A question about an amendment that is not the amendment's own: passing the
# bill with it, concurring in the other chamber's, considering one.
NOT_AMENDING = re.compile(r"^\s*(?:OTP|Ought\s+to\s+Pass|Pass(?:ed)?\b|ITL\b|Inexpedient)|"
                          r"\bOTP\s*/\s*AM\b|\b(?:non-?\s*)?concur|\bconsider", re.I)
# The clerk's shorthand anywhere in a question: "Comm Report OTP/AM".
INLINE_SHORTHAND = [
    (re.compile(r"\bComm\.?\s+Report\b", re.I), "Committee Report"),
    (re.compile(r"\bOTP\s*/\s*AM?\b", re.I), "Ought to Pass with Amendment"),
    (re.compile(r"\bOTP\b"), "Ought to Pass"),
    (re.compile(r"\bITL\b"), "Inexpedient to Legislate"),
]
# The clerk's result and vote words, and a threshold, around a question.
RESULT_WORDS = (r"MA|MF|ML|AA|AF|AL|VV|DV|DIV|RC|Adopted|Adpoted|Failed|Defeated|Lost|"
                r"Passed|Veto\s+Overrid+en|Veto\s+Override|Veto\s+Sustained|Overrid+en|"
                r"Sustained")
EDGE = (r"(?:[\s,;:.=\-]|\b(?:" + RESULT_WORDS + r")\b|\(\s*(?:" + RESULT_WORDS +
        r")\s*\)|\b\d\s*/\s*\d\b(?:\s*nec(?:essary)?\.?)?|\bnec(?:essary)?\.?|"
        r"\bby\s+(?:the\s+)?(?:necessary|required)\s+[\w-]+(?:\s+vote)?|"
        r"\b(?:not\s+getting|lacking|obtaining)\s+(?:the\s+)?(?:necessary|required)\s+"
        r"[\w/-]+(?:\s+vote)?)*")
# Not "Passed" at the front: "Passed with Am RC(194-149)" is the question.
LEAD_EDGE = re.compile("^" + EDGE.replace("Passed|", ""), re.I)
TAIL_EDGE = re.compile(EDGE + "$", re.I)
VOICE = re.compile(r"\bVV\b", re.I)
# Who moved it, where the clerk wrote it: "Rep Rubin moved", "Sen. Francoeur
# Moved", "Senator Larsen offered", "Reps Hess & Ward Prop", "Rep Camm:",
# "(Rep. Luneau)".
# A name: capitalised words that are not the motion's own ("Sen. McCarley
# OTP", "Sen. Fraser LOT", "Rep P LaFlamme moved OTP").
_NOT_NAME = (r"(?!(?i:OTP|LOT|ITL|OT3rdg|Ought|Motion|Moved?|Moves|Sub\w*|Inexpedient|"
             r"Laid|Lay|Floor|Fl|Flr|Comm|Committee|Am|Amend\w*|Divide|Special|Spec|"
             r"Rerefer\w*|Re-ref\w*|Recommit\w*|Reconsider\w*|Concur\w*|Non\w*|Prop\w*|"
             r"Offered|Served|Div|Rules?|Susp\w*|Indef\w*|Print|Postpone|Previous|Limit|"
             r"Remove|Ref|Referred|Final|Order\w*|Maj\w*|Min\w*|Vacate|Taken|Passed|"
             r"3rd)\b)")
_NAME = _NOT_NAME + r"[A-Z][\w'’.\-]*"
MOVER_LEAD = re.compile(
    r"^\s*\(?\s*(?P<t>(?i:Reps?|Representatives?|Sens?|Senators?))\.?\s+(?P<who>" + _NAME +
    r"(?:\s+" + _NAME + r"){0,2}(?:\s*(?:&|,|and)\s*" + _NAME + r"(?:\s+" + _NAME +
    r")?)*(?:\s+et\s+al\.?)?)\s*\)?\s*(?::\s*|,\s*|\s+(?i:moved?|moves|offered|served|"
    r"Prop(?:osed)?|motion(?:\s+of|\s+for)?|sub[- ]?motion(?:\s+of)?|"
    r"subst(?:itute)?(?:\s+motion)?(?:\s+of)?)\b\.?,?\s*"
    r"(?i:to\s+|that\s+|a\s+|the\s+)?|\s+(?=\S))")
# "Previous Question Rep. Sweeney", "INDEF POST, Rep Boyce".
MOVER_TAIL = re.compile(
    r"[,\s]+(?P<t>(?i:Reps?|Sens?|Senators?))\.?\s+(?P<who>" + _NAME +
    r"(?:\s+" + _NAME + r")?)\s*$")
MOVER_PAREN = re.compile(
    r"\(\s*(?P<t>Reps?|Sens?|Senators?)\.?\s+(?P<who>[^()]{1,80}?)\s*\)", re.I)
# The date a row states before its words: "9/7/11-Sen. Morse Concurs with
# House Amendment #2605h" (SB 198, entered on 4 January 2012).
DATE_FIRST = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2,4})\s*-\s*")
# The clerk's shorthand, expanded where it opens a question.
SHORTHAND = [
    (re.compile(r"^ITL\b(?:\s+rep(?:ort)?\b)?", re.I), "Inexpedient to Legislate"),
    (re.compile(r"^OTP\s*/\s*A(?:M)?\b|^OTPA\b|^OTP\s+w(?:ith)?/?\s*am(?:endment)?\b", re.I),
     "Ought to Pass with Amendment"),
    (re.compile(r"^OTP\b(?:\s+rep(?:ort)?\b)?", re.I), "Ought to Pass"),
    (re.compile(r"^LOT\b", re.I), "Lay on the Table"),
    (re.compile(r"^Spec(?:ial)?\.?\s+Order(?:ed)?\b", re.I), "Special Order"),
    (re.compile(r"^Recon\b\.?", re.I), "Reconsider"),
    (re.compile(r"^Susp(?:end)?\.?\s+(?:the\s+)?Rules?\b", re.I), "Suspend the Rules"),
    (re.compile(r"^Indef(?:initely)?\.?\s+Post(?:pone)?\.?\b", re.I), "Indefinitely Postpone"),
    (re.compile(r"^Maj\.?\s+R(?:e)?p(?:o)?r?t\b:?", re.I), "Majority Report:"),
    (re.compile(r"^Min\.?\s+R(?:e)?p(?:o)?r?t\b:?", re.I), "Minority Report:"),
    (re.compile(r"^Motion:\s*", re.I), ""),
]


def rollcall_key(r):
    """(year, body, number) -- one roll call. The voting system numbers them
    afresh each year in each chamber, and no two rows on record share one."""
    return (str(r.get("year")), r.get("body"), int(r.get("number") or 0))


def _motion_key(action):
    """A motion's words without its bill's number: one motion entered on
    several bills' dockets reads the same on each but for the number."""
    a = re.sub(r"\b(?:HB|SB|HR|SR|HCR|SCR|HJR|SJR|CACR)\s*\d+\w*", "", action or "",
               flags=re.I)
    return re.sub(r"[\W_]+", " ", a).strip().lower()


def _bill_of(key):
    """rollcalls.json's bill key as narratives.json keys the bill: "SR1 (2009)"
    is SR 1."""
    return re.sub(r"\s+", "", re.sub(r"\s*\(\d{4}\)\s*$", "", key or "")).upper()


# A key of rollcalls.json that names a measure, as _bill_of gives it; the
# others ("_procedural") name none.
BILL_KEY = re.compile(r"^(?:HB|SB|HR|SR|HCR|SCR|HJR|SJR|CACR|HA|SSSB|SSHB)\d+[A-Z]?$")


def _tallies(events, body):
    """[occurrence] -- every counted tally on one bill's rows of one chamber,
    with where it sits on its row and the date the row itself states after
    it ("FLAM #2016-0431h ...: AF RC 143-206 02/10/2016", entered on the
    12th)."""
    out = []
    for n, e in enumerate(events or ()):
        if ((e.get("body") or "").strip().upper() != body or e.get("cancelled")
                or (e.get("type") in NOT_THE_FLOOR and not _floor_report(e))):
            continue
        raw = e.get("raw") or ""
        ms = list(TALLY.finditer(raw))
        row = []
        entered = (e.get("date") or "")[:10]
        first = DATE_FIRST.match(raw)
        for k, m in enumerate(ms):
            if m.group("y") is not None:
                y, nn = int(m.group("y")), int(m.group("n"))
            else:
                y, nn = int(m.group("y2")), int(m.group("n2"))
            kind = (m.group("kind") or "").upper()
            kind = ("RC" if kind.startswith(("RC", "ROLL")) else "DV" if kind else "")
            d = DATE_IN.search(raw, m.end())
            if d and TALLY.search(raw, m.end(), d.start()):
                d = None
            own = _stated(d or first, entered)
            row.append({"e": e, "n": n, "k": k, "kind": kind, "y": y, "nn": nn,
                        "start": m.start(), "end": m.end(),
                        "date": entered, "own": own, "lead": ""})
        # A row the database cut from the line before it starts mid-question:
        # "SUSTAINED RC(221-117)" after "... MA DIV(211-125); GOVERNOR'S VETO"
        # (HB 332, 29 June 1995). The question's words are the last clause
        # of the row before, where that clause decides nothing itself.
        before = events[n - 1] if n else None
        if row and before is not None and \
                (before.get("body") or "").strip().upper() == body and \
                (before.get("date") or "")[:10] == entered:
            tail = (before.get("raw") or "").rsplit(";", 1)[-1].strip(" ,;")
            if tail and not TALLY.search(tail) and not VOICE.search(tail) and \
                    not RESULT_CODE.search(tail):
                row[0]["lead"] = tail
        for o in row:
            o["row"] = row
        out += row
    return out


def _floor_report(e):
    """A row typed as a committee's report that is the floor's vote on it:
    "COMM REPT: ITL ML VV; REPS KURK & BURLING FL AM<2454>, AA RC(192-156);
    ..." is CACR 44's whole day on 24 September 1998, five roll calls the
    reader typed "report" by its first words, and none was drawn. Only where
    the row states the chamber's result (MA, ML, AA ...), which no
    committee's own vote does: "Majority Committee Report: Inexpedient to
    Legislate for April 29 RC (9-8)" (SB 100 of 2009) is the committee's
    roll call."""
    return e.get("type") == "report" and bool(RESULT_CODE.search(e.get("raw") or ""))


def _stated(m, entered):
    """The ISO date a row states (a DATE_IN or DATE_FIRST match), where it is
    one and lies within a session's reach of the day the row is entered --
    SB 198's concurrence of 7 September 2011 is entered on 4 January 2012;
    a special order's date months ahead is not the row's -- else None."""
    if not m:
        return None
    yr = int(m.group(3))
    yr += (2000 if yr < 50 else 1900) if yr < 100 else 0
    try:
        when = _date(yr, int(m.group(1)), int(m.group(2))).isoformat()
    except ValueError:
        return None
    return when if _apart(when, entered) <= 160 else None


def _tally_set(r):
    out = {(r["yeas"], r["nays"])}
    if r.get("yeas_stated") is not None:
        out.add((r["yeas_stated"], r["nays_stated"]))
    return out


def _apart(a, b):
    try:
        return abs((_date.fromisoformat(a) - _date.fromisoformat(b)).days)
    except (TypeError, ValueError):
        return 99999


def _pair(rs, occ):
    """{id(roll call): occurrence} for one bill in one chamber and term.

    Within a day, the assignment that agrees on the most counts and keeps
    both the roll-call numbers and the docket's rows in their order -- SB
    331 of 2018 had three roll calls of 12-12, 13-11 and 12-12 -- and, where
    the day holds as many tallies as roll calls, pairs the rest in order
    too: the clerk's "RC 1Y-7N" is SB 133's 17-7 of 30 March 1999. Then any
    roll call left is paired on its exact count anywhere in the term, the
    nearest first, but only with a row about the same kind of question: the
    2003 veto session's House overrides are dated in January in the
    roll-call file and in September in the docket."""
    import rollcall_outcomes as RO
    got, used = {}, set()
    by_day = collections.defaultdict(list)
    for r in rs:
        by_day[r["date"]].append(r)
    for day, rr in sorted(by_day.items()):
        ks = [k for k, o in enumerate(occ) if o["kind"] != "DV"
              and day in (o["date"], o["own"])]
        if not ks:
            continue
        rr = sorted(rr, key=lambda x: x["number"])
        n = max(len(rr), len(ks))
        cost = [[0] * n for _ in range(n)]
        for i in range(min(n, len(rr))):
            for j in range(min(n, len(ks))):
                o = occ[ks[j]]
                cost[i][j] = ((0 if (o["y"], o["nn"]) in _tally_set(rr[i]) else 1000)
                              + abs(i - j) + (0 if o["kind"] == "RC" else 0.5))
        for i, j in RO._assign(cost):
            if (i < len(rr) and j < len(ks) and ks[j] not in used
                    and (cost[i][j] < 1000 or len(rr) == len(ks))):
                got[id(rr[i])] = occ[ks[j]]
                used.add(ks[j])
    for r in sorted(rs, key=lambda x: (x["date"], x["number"])):
        if id(r) in got:
            continue
        q = r.get("question_raw") or r.get("question") or ""
        best = None
        for k, o in enumerate(occ):
            if k in used or (o["y"], o["nn"]) not in _tally_set(r):
                continue
            t = o["e"].get("raw") or ""
            if (bool(VETO_Q.search(q)) != bool(VETO_Q.search(t))
                    or bool(SUSPEND_Q.search(q)) != bool(SUSPEND_Q.search(t))):
                continue
            far = min(_apart(o["date"], r["date"]), _apart(o["own"], r["date"]))
            cand = (0 if o["kind"] == "RC" else 1 if not o["kind"] else 2, far, k)
            if best is None or cand < best:
                best = cand
        if best:
            got[id(r)] = occ[best[2]]
            used.add(best[2])
    return got


def _owns(it, o):
    """Is this tally the one the floor motion `it`, made from the same row,
    tells -- or another question decided on the same line?"""
    if it.veto:
        return True
    row = o["row"]
    if it.counted:
        if (it.yeas, it.nays) == (o["y"], o["nn"]):
            return True
        # the line's one count, which the fields hold another way
        return len(row) == 1 and not any((p["y"], p["nn"]) == (it.yeas, it.nays)
                                         for p in row)
    if it.kind == "VV":
        # A voice vote has no count: a roll call on its line is another
        # question's (HB 661 of 1999: "Ought to Pass, RC 4Y-16N, MF, Sen.
        # Fernald Moved Laid on Table, MF, VV").
        return False
    if len(row) == 1:
        return True
    # A LINE OF SEVERAL COUNTS AND A MOTION READ WITH NONE: "Limit Debate ML
    # RC(160-205); Veto Sustained -failed nec 2/3- RC(245-128)" (HB 1, 30 June
    # 2003) is the reader's "Limit Debate", with no count. It is the one
    # clause that names its question. Owning none, it stayed on the page
    # beside its own clause drawn as a motion of its own, and the one vote
    # was drawn, and counted, twice: HB 1 then, HB 520 on 15 January 2004
    # ("ITL Report, ML RC(166-168); ... LOT, ML RC(142-193)"), HB 611's "Sec
    # 1" on 30 March 2005.
    mine = [p for p in row if _names_question(it, p)]
    return len(mine) == 1 and mine[0] is o


def _names_question(it, o):
    """Does the clause of tally `o` name the question the motion `it` is
    read as: the same words, or the same kind of question?"""
    seg = _segment(o)
    a, s = _motion_key(it.action), _motion_key(seg)
    if a and s and (s.startswith(a) or a.startswith(s)):
        return True
    k = question_kind(it.action)
    return bool(k) and k == question_kind(seg)


def _told_at(it, row):
    """Where on its line the clause `it` tells sits, as a character offset:
    its own count, or its voice vote -- the last, where several."""
    raw = it.raw or ""
    if it.counted:
        for p in row:
            if (p["y"], p["nn"]) == (it.yeas, it.nays):
                return p["start"]
    vv = [m.start() for m in VOICE.finditer(raw)]
    if it.kind == "VV" and vv:
        return vv[-1]
    return len(raw)


def _segment(o):
    """The words of the question one tally decides: back from the tally to
    the last thing decided before it on the line -- another tally, a voice
    vote, or a result followed by a semicolon -- with the result and vote
    words at both ends taken off."""
    raw = o["e"].get("raw") or ""
    lo = 0
    for p in o["row"]:
        if p["end"] <= o["start"]:
            lo = max(lo, p["end"])
    for m in VOICE.finditer(raw, 0, o["start"]):
        lo = max(lo, m.end())
    # A semicolon ends a question where a new one begins after it -- "Rep P
    # LaFlamme moved OTP; Rep Owen moved LOT, ML RC(142-193)" -- and not
    # inside one: "Floor Amendment #2026-0297s Sections 14; 15; and the
    # effective date; RC 24Y-0N".
    # Not before a bare result: "Adopt Section I Floor Amendment {2421h}; AA RC
    # 193-140" (SB 1 of the 2006 special session) is one question.
    for m in re.finditer(r";\s*(?=[A-Z(])(?!and\b)", raw[:o["start"]]):
        if m.start() >= lo and LEAD_EDGE.sub("", raw[m.end():o["start"]]).strip(" ,;:"):
            lo = m.end()
    o["clause"] = raw[lo:o["start"]]
    seg = DATE_FIRST.sub("", raw[lo:o["start"]])
    # "..., motion failed 2/3RC(179-103)" (SB 146 of 2005)
    seg = re.sub(r",?\s*motion\s+(?:failed|adopted|carried|lost)\b.*$", "", seg, flags=re.I)
    seg = re.sub(r"(?:\d\s*/\s*\d)?\s*(?:RC|DIV|DV)?\s*\(\s*$", "", seg)
    # A result written after its tally belongs to that tally: "RC 24Y-0N,
    # AA, OT3rdg, RC 21Y-3N, MA".
    seg = LEAD_EDGE.sub("", seg)
    seg = TAIL_EDGE.sub("", seg)
    return re.sub(r"\s+", " ", seg).strip(" ,;:-")


def _after(o):
    """The words after a tally, to the next question: where a 1999 House
    line puts its mover, "Reconsider 18-311 (Rep. H. Howard)"."""
    raw = o["e"].get("raw") or ""
    nxt = [p["start"] for p in o["row"] if p["start"] > o["start"]]
    end = min(nxt + [len(raw)])
    semi = raw.find(";", o["end"], end)
    return raw[o["end"]:semi if semi >= 0 else end]


def _person(t, who, body):
    """("Rep. Rubin", "") for one named member, or ("", "Reps. Hess & Ward")
    where several moved it together."""
    who = re.sub(r"\s+", " ", who or "").strip(" .,:;")
    who = re.sub(r"\s+(?:Prop(?:osed)?|moved?|moves|offered|served)\b.*$", "", who,
                 flags=re.I).strip(" .,:;")
    if not who:
        return "", ""
    several = bool(re.search(r"&|,|\band\b|\bet\s+al\b", who, re.I)) or \
        (t or "").lower().rstrip(".") in ("reps", "sens", "senators", "representatives")
    if who.isupper():
        # "W.O'BRIEN" is W. O'Brien, "D. YOUNG" D. Young
        who = re.sub(r"[A-Z]{2,}", lambda m: m.group(0).capitalize(), who)
    title = "Rep." if body == "H" else "Sen."
    if several:
        return "", f"{title[:-1]}s. {who}"
    return f"{title} {who}", ""


def _amendment(seg, e, r):
    """("Adopt Floor Amendment 2025-1979h", mover, others) for a question
    about an amendment, or None."""
    kind_text = e.get("amend_kind") if e.get("type") == "amendment" else ""
    if not kind_text and NOT_AMENDING.search(seg):
        return None
    m = AMEND_Q.search(seg)
    if not m and not kind_text:
        return None
    kt = (m.group("kind") if m else kind_text) or ""
    low = kt.lower()
    if re.search(r"enrolled", seg + " " + (kind_text or ""), re.I):
        kind = "Enrolled Bill Amendment"
    elif low.startswith(("maj",)):
        kind = "Majority Committee Amendment"
    elif low.startswith("min"):
        kind = "Minority Committee Amendment"
    elif "fl" in low:
        kind = "Floor Amendment"
    elif low.startswith("comm"):
        kind = "Committee Amendment"
    else:
        kind = "Amendment"
    rest = seg[m.end():] if m else seg
    num = AMEND_NO.search(rest) or AMEND_NO.search(seg)
    no = num.group("no") if num else ""
    if not no and e.get("type") == "amendment":
        no = (e.get("amendment") or "").strip()
    if not no:
        q = AMEND_NO.search(r.get("question") or "") if r else None
        no = q.group("no") if q else ""
    mover, several = "", ""
    lead = seg[:m.start()] if m else ""
    lm = MOVER_LEAD.match(lead + " Am") if lead.strip() else None
    pm = MOVER_PAREN.search(seg)
    if pm:
        mover, several = _person(pm.group("t"), pm.group("who"), (e.get("body") or "H"))
    elif lm:
        mover, several = _person(lm.group("t"), lm.group("who"), (e.get("body") or "H"))
    elif e.get("type") == "amendment" and e.get("mover"):
        w = re.sub(r"\b(?:offered|moved|prop(?:osed)?)\b.*$", "", e["mover"], flags=re.I)
        w = re.match(r"^\s*(?P<t>Reps?|Sens?|Senators?)\.?\s+(?P<who>.+)$", w)
        if w:
            mover, several = _person(w.group("t"), w.group("who"), (e.get("body") or "H"))
    extra = ""
    s = SECTIONS.search(seg)
    if s and not re.match(r"^\s*$", s.group(0)):
        extra = re.sub(r"\s+", " ", s.group(0)).strip(" ,;:")
        if re.match(r"^(?:remainder|rest|remaining|balance)\b", extra, re.I):
            extra = "the remainder"
        extra = MOVER_PAREN.sub("", extra).strip(" ,;:")
        # "Section I Floor Amendment {2421h}": the part, not the amendment again
        extra = re.split(r"\s+(?:Fl(?:oo)?r?\.?\s*Am|Comm(?:ittee)?\.?\s*Am|Amend|Am\b|\{)",
                         extra, maxsplit=1, flags=re.I)[0].strip(" ,;:")
        extra = re.sub(r"\s+of(?:\s+(?:the|prop\w*))?\s*$", "", extra, flags=re.I)
    action = f"Adopt {kind}" + (f" {no}" if no else "") + (f", {extra}" if extra else "")
    if several:
        action += f" ({several})"
    return action, mover


def _sentence(q):
    """An all-capitals question as a sentence: "REP NORDGREN: PRINT DEBATE"
    reads "Rep Nordgren: Print debate"."""
    if not q or not q.isupper():
        return q

    def word(m):
        w = m.group(0)
        if w in KEEP_CAPS or re.fullmatch(r"[IVX]{1,4}", w):
            return w
        if w.lower() in MONTH_NAMES or w in ("REP", "REPS", "SEN", "SENS"):
            return w.capitalize()
        return w.lower()
    out = re.sub(r"[A-Z]+", word, q)
    return out[:1].upper() + out[1:]


KEEP_CAPS = {"HB", "SB", "HR", "SR", "HCR", "SCR", "HJR", "SJR", "CACR", "ITL", "OTP",
             "RSA", "NT", "COC"}


MONTH_NAMES = ("january", "february", "march", "april", "may", "june", "july",
               "august", "september", "october", "november", "december")


# The Senate's roll-call file of 1999-2006 writes the mover and seconder
# after the question, sometimes with no space: "Ought to PassBrown/Krueger",
# "Order to 3rd Reading3/5 Necessary", "Inexpedient to Legislate - Sen.
# Burling/Sen. Green".
_SENATOR = r"(?:Sen(?:ator)?s?\.?\s*)?(?:[A-Z]\.?\s+)?[A-Z][\w'’]*"
SECONDED = re.compile(r"(?:\s*-\s*|\s+|(?<=[a-z)\]]))" + _SENATOR + r"\s*/\s*" + _SENATOR +
                      r"\s*\.?\s*$")
GLUED_THRESHOLD = re.compile(r"(?<=[a-z])(?=\d/\d\s+Necessary)", re.I)
GLUED_NAMES = re.compile(r"(?:(?<=[a-z]{3})|(?<=\)))"
                         r"(?=[A-Z][\w'’.]*(?:\s+[A-Z][\w'’.]*)?\s*/)")


def rollcall_question(r):
    """(action, mover) for a roll call the docket has no row for: the
    question as the roll-call file words it, with the 1999-2006 mover and
    seconder taken off the end and the House's "REP X:" taken off the
    front, and nothing added."""
    q = re.sub(r"\s+", " ", (r.get("question") or r.get("question_raw") or "")).strip()
    q = GLUED_THRESHOLD.sub(" ", q)
    if r.get("body") == "S":
        q = GLUED_NAMES.sub(" ", q)
        q = SECONDED.sub("", q).strip(" -")
    body = r.get("body") or "H"
    mover = several = ""
    # "REP NORDGREN: PRINT DEBATE"; and "REP NORELLI", a mover and no question.
    m = re.match(r"^(?P<t>REPS?|SENS?|Sen\.?|Rep\.?)\s+(?P<who>(?:(?!AMEND|MOTION)[A-Z][\w'.]*"
                 r"(?:\s*(?:&|AND)\s*)?\s*){1,4}?)(?::\s*(?P<rest>.*)|\s*$)", q)
    if m and (m.group("rest") or m.group("rest") is None):
        mover, several = _person(m.group("t"), m.group("who"), body)
        q = m.group("rest") or ""
    pm = MOVER_PAREN.search(q)
    if pm and not mover and not several:
        mover, several = _person(pm.group("t"), pm.group("who"), body)
        q = (q[:pm.start()] + q[pm.end():]).strip()
    # "FLAM to House Rule 67 (Covid)-Osborne & Cushing" (6 January 2021)
    q = _sentence(q.strip(" .:-")) or ""
    q = re.sub(r"^FLAM\b:?\s*", "Floor amendment ", q, flags=re.I).strip()
    if several:
        q += f" ({several})"
    return q, mover


def _question(o, r):
    """(action, mover, plain) for the question one docket tally decides,
    worded from the docket and, where its words name nothing, from the
    roll-call file."""
    e = o["e"]
    body = (e.get("body") or "H").strip().upper()
    raw = e.get("raw") or ""
    seg = _segment(o)
    # Only where there is no roll-call file to word the question: from 1999
    # it does, and a row before can be another question's (SB 118 of 2001's
    # nonconcurrence follows a conference report's row).
    if not seg and o.get("lead") and r is None:
        seg = re.sub(r"\s+", " ", o["lead"]).strip(" ,;:-")
        o["clause"] = o["lead"] + " " + o["clause"]
    whole = raw if len(o["row"]) == 1 else o["clause"]
    if e.get("type") == "veto_override" or VETO_Q.search(seg) or (
            not seg and VETO_Q.search(whole)) or (
            r is not None and VETO_Q.search(r.get("question") or "")
            and VETO_Q.search(whole)):
        return "Override the Governor's veto", "", False
    # A committee of conference report, by the docket's words or -- where the
    # docket names only the amendments it carries, "Senate Amendment + New
    # Amendment (2349)" (HB 1 of 2007) -- by the roll-call file's question.
    asked = (r or {}).get("question") or ""
    if (CONFERENCE_Q.search(seg) or (not seg and CONFERENCE_Q.search(whole))
            or (CONFERENCE_Q.search(asked) and not VETO_Q.search(asked)
                and not re.search(r"non-?\s*conc|request", asked, re.I))):
        src = (seg if CONFERENCE_Q.search(seg) else whole if CONFERENCE_Q.search(whole)
               else seg)
        c = CONFERENCE_Q.search(src)
        num = re.search(r"(?:#\s*|[{(]\s*)?((?:\d{4}-)?\d{4}c?)\b", src[c.end() if c else 0:])
        no = f" {num.group(1)}" if num else ""
        if NOT_ADOPT.search(src):
            return f"Not adopt the Conference Committee Report{no}", "", True
        return f"Adopt the Conference Committee Report{no}", "", True
    # Who divided the question, and the part then voted on: "Sen. Hollingworth
    # Divide the Question: Section 1-16,21-33,36-80,82; RC 24Y-0N" (HB 170, 12
    # June 2001) is the vote on those sections of Floor Amendment 1675, and
    # the page called it "Divide the Question".
    dq = re.match(r"^.*?\bDivide\s+the\s+Question\s*:\s*(?P<part>.+)$", seg, re.I)
    if dq and SECTIONS.match(dq.group("part")) and AMEND_Q.search(asked):
        seg = dq.group("part")
    # Sections of an amendment the roll-call file names and the line does
    # not: "Sections 3 and 6, RC 16Y-6N, AA" is Floor Amendment 1215s's.
    if SECTIONS.match(seg) and AMEND_Q.search(asked) and not NOT_AMENDING.search(asked):
        am = _amendment(asked, {}, r)
        if am:
            base_action = re.sub(r",.*$", "", am[0])
            return f"{base_action}, {seg}", "", True
    # A ROW ABOUT AN AMENDMENT CAN HOLD ANOTHER QUESTION'S ROLL CALL. "Sen.
    # Larsen Floor Amendment {0965}, AA, VV, OT3rdg, RC 14Y-8N, MA" (HB 117,
    # 22 April 1999) adopted the amendment by voice and ordered the bill to
    # third reading on the roll call, which the file words "Third Reading
    # Final Passage"; "Sen Johnson Floor Amendment, {2227}, AA, VV, Sen Below
    # Moved Rerefer, RC 8Y-14N, MF" (HB 625, 3 November 1999) put the roll
    # call on Senator Below's motion to re-refer. The page drew each as the
    # amendment adopted on the roll call, eleven of 1999-2001 among them.
    # Where the words before the count name a question and no amendment,
    # the count is that question's.
    # AND A MOTION TO DIVIDE IS NOT THE AMENDMENT IT WOULD DIVIDE. "Rep
    # Vaillancourt moved to Div ? on Maj Am, ML RC(20-338)" (HB 375, 3 May
    # 2001), the file's "REP VAILLANCOURT: DIVIDE THE QUESTION", was drawn as
    # the majority committee amendment failing 20-338, and "Motion To Divide
    # Section 13 Of FLAM: #2013-2434h (Rep. Hoell) Failed, RC 142-208" (SSHB
    # 1, 21 November 2013) as section 13 of the amendment.
    divide = MOTION_TO_DIVIDE.search(seg)
    if divide and re.search(r"\bdiv(?:ide)?\s*\?", seg, re.I):
        lead = MOVER_LEAD.match(seg)
        mover = _person(lead.group("t"), lead.group("who"), body)[0] if lead else ""
        return "Divide the question", mover, False
    # And the same motion worded as the part divided, beside the amendment it
    # would divide: "Floor Amendment #2014-0025h, Divide Sections 1-8 (Rep.
    # Jasper) MF RC 160-183" (HB 544, 8 January 2014), the file's "Divide Sect
    # 1-8", was drawn as sections 1-8 of the amendment failing, on the page
    # that draws the whole amendment adopted 186-155 next.
    if not divide and DIVIDE_PART.search(seg) and AMEND_Q.search(seg):
        pm = MOVER_PAREN.search(seg)
        lead = MOVER_LEAD.match(seg)
        mover = (_person(pm.group("t"), pm.group("who"), body)[0] if pm else
                 _person(lead.group("t"), lead.group("who"), body)[0] if lead else "")
        return "Divide the question", mover, False
    third = THIRD_IN_LINE.search(seg) or re.search(r"\b(?:3rd|third)\s+reading\b", seg, re.I)
    if divide:
        am = None
    elif e.get("type") == "amendment" and seg and (
            third or NOT_AMENDING.search(seg)
            or (not AMEND_Q.search(seg) and not AMEND_NO.search(seg)
                and (question_kind(seg) not in (None, "amendment")
                     or re.search(r"\bre-?\s*refer|\bre-?\s*commit", seg, re.I)))):
        # and before 1999: "COMM AM, AA DIV(173-141); 3RD READING FAILS 3/5
        # RC(197-126)" (CACR 20, 11 February 1992) and "FL AM<2398>, AL VV;
        # ...; OTP/AM FAILS 3/5 RC(193-163)" (CACR 45, 10 September 1998),
        # each drawn as the amendment failing on the count.
        if THIRD_IN_LINE.search(seg):
            return "Order to Third Reading", "", False
        if third:
            return "Third Reading", "", False
        seg = re.sub(r"\s+(?:fails?|failed|lost|adopted|passe[sd])\b.*$", "", seg, flags=re.I)
        am = None
    else:
        am = _amendment(seg, e, r) if seg or e.get("type") == "amendment" else None
    if am:
        return am[0], am[1], True
    # A committee's report with its amendment, voted as the amendment: the
    # Senate's "Ought to Pass W/Amendment, {1298}, (New Title), RC 10Y-13N,
    # AF" (SB 68 of 1999) is the committee amendment failing, AF being an
    # amendment's result, and the roll-call file's "Committee Amendment (1298)".
    after = (e.get("raw") or "")[o["end"]:]
    num = AMEND_NO.search(seg)
    if num and re.match(r"[\s,;:]*(?:AA|AF|AL)\b", after):
        kind = ("Floor Amendment" if re.search(r"\bfl", seg, re.I) else
                "Minority Committee Amendment" if re.search(r"\bmin", seg, re.I) else
                "Majority Committee Amendment" if re.search(r"\bmaj", seg, re.I) else
                "Committee Amendment")
        return f"Adopt {kind} {num.group('no')}", "", True
    # Parts of the bill, voted one at a time once a member divided the
    # question: "Secs 2,3 & 4 adopted RC(226-130); Rest of bill adopted
    # RC(233-123)" (HB 90 of 1999) names the parts and not the question, which
    # the roll-call file does: "Committee report: OTP (sections 2,3 & 4)".
    if SECTIONS.match(seg) and asked:
        q, qm = rollcall_question(r)
        if q:
            return q, qm, False
    if THIRD_Q.match(seg):
        return "Order to Third Reading", "", False
    mover = several = ""
    words = seg
    m = MOVER_LEAD.match(words)
    if m and words[m.end():].strip():
        mover, several = _person(m.group("t"), m.group("who"), body)
        words = words[m.end():]
    # "MOVED LOT", with no name; "DIV ?", a member asking that the question
    # be divided, before the part voted on -- or, alone, the motion to divide
    # it: "SEN HEATH MOVED TO DIV ?, ML RC(6-17)" (HB 1000, 8 January 1992).
    if re.fullmatch(r"\s*div(?:ision)?\s*\??\s*", words, re.I):
        words = "Divide the question"
    elif re.match(r"^\s*div(?:ision)?\s*\?", words, re.I):
        # who asked for the division did not move the part voted on
        mover = several = ""
    words = re.sub(r"^\s*(?:moved?\s+(?:to\s+)?|div(?:ision)?\s*\?[\s,;]*)", "", words,
                   flags=re.I)
    if words.isupper():
        # The 1989-1998 clerk strings a question's parts with commas and
        # puts the mover last: "MIN REPORT ITL, ITL REPORT ADOPTED RC(13-10)"
        # is the ITL report adopted; "RECOMMITTED TO WAYS & MEANS, REP SYTEK".
        parts = [p.strip() for p in words.split(",") if p.strip()]
        if len(parts) > 1 and not mover and not several:
            t = re.fullmatch(r"(?P<t>REPS?|SENS?)\.?\s+(?P<who>[A-Z][\w'.\- &]*)", parts[-1])
            if t:
                mover, several = _person(t.group("t"), t.group("who"), body)
                parts = parts[:-1]
        if len(parts) > 1 and (question_kind(parts[-1]) or
                               any(rx.match(parts[-1]) for rx, _ in SHORTHAND)):
            parts = parts[-1:]
        words = _sentence(", ".join(parts))
    if re.fullmatch(r"(?i:3rd\s+reading|third\s+reading)", words.strip()):
        words = "Third Reading"
    pm = MOVER_PAREN.search(words) or (None if mover or several else MOVER_PAREN.search(_after(o)))
    if pm and not mover and not several:
        mover, several = _person(pm.group("t"), pm.group("who"), body)
    if pm and pm.string is words:
        words = (words[:pm.start()] + words[pm.end():])
    t = MOVER_TAIL.search(words)
    if t and not mover and not several:
        mover, several = _person(t.group("t"), t.group("who"), body)
        words = words[:t.start()]
    words = re.sub(r"\s+", " ", words).strip(" ,;:.-")
    for rx, full in SHORTHAND:
        if rx.match(words):
            rest = rx.sub("", words, count=1).strip(" ,:.")
            rest = re.sub(r"^of\s+", "", rest)
            for rx2, full2 in SHORTHAND:
                if full2 and rx2.match(rest):
                    rest = (full2 + " " + rx2.sub("", rest, count=1).strip(" ,:.")).strip()
                    break
            words = (full + " " + rest).strip()
            break
    for rx, full in INLINE_SHORTHAND:
        words = rx.sub(full, words)
    # Words that name no question of their own: "Introduced and" once its
    # "Adopted" is read as the result, "Adoption", "Upheld".
    if (not re.search(r"[A-Za-z]{3,}", words) or re.search(r"\b(?:and|&)$", words)
            or re.fullmatch(r"(?i:adoption|adopted|passage|passed|upheld|overturned)", words)):
        q, qm = rollcall_question(r) if r is not None else ("", "")
        words, mover = q or words, mover or qm
    words = words[:1].upper() + words[1:]
    if several and words:
        words += f" ({several})"
    return words, mover, False


_SAT = {}
_JOURNALS = None


def _sat(body, date):
    """Does the chamber's journal on disk open a sitting on this date? The
    only evidence for a day whose every vote is on no bill, and the guard
    against a roll call the roll-call file misdates making a sitting that
    never was (doubtful() has the same worry). Only the openings are read --
    journal_days' whole parse of a House year is many seconds, its day
    headings a tenth of one, and they find the same days."""
    return _journal(body, date) is not None


def _journal(body, date):
    """{(yeas, nays)} the chamber's journal prints as roll calls in the
    sitting of this date, or None where the journal on disk opens no
    sitting on it."""
    j = _journal_day(body, date)
    return None if j is None else set(j["rc"])


# How each chamber's journal prints a vote. A roll call is "YEAS 182 - NAYS
# 172" in the House (journal_days.TALLY) and "Yeas: 16 - Nays: 8" in the
# Senate; a House division names no one: "On a division vote, with 193
# members having voted in the affirmative, and 177 in the negative" (2025),
# "division vote, 121 members having voted in the affirmative and 200 in the
# negative" (2006).
SENATE_TALLY = re.compile(r"\bYeas:?\s*(?P<yeas>\d+)\s*[-–,]\s*Nays:?\s*(?P<nays>\d+)", re.I)
# journal_days.DIVISION's pattern, and its three rarer wordings: "185 members
# having voted in the affirmative, 107 in the negative" (2001), "On a division
# vote,273 members" (2003), "268 members having spoken in the affirmative"
# (1998).
JOURNAL_DIVISION = re.compile(
    r"division\s+vote,?\s*(?:with\s+)?(?P<yeas>\d+)\s+members?\s+(?:having\s+)?"
    r"(?:vot|spok)\w*\s+in\s+the\s+affirmative,?\s+(?:and\s+)?(?P<nays>\d+)", re.I)
JOURNAL_BILL = re.compile(r"\b(HB|SB|HR|SR|HCR|SCR|HJR|SJR|CACR)\s*(\d+)\b")
SENATE_DIVISION = re.compile(r"division\s+(?:vote\s+)?was\s+requested|Division,\s*$", re.I)
SENATE_NAMED = re.compile(r"Senators\s+voted\s+(?:Yes|No)", re.I)


def _journal_day(body, date):
    """{"rc": Counter of (yeas, nays), "div": Counter, "bills": {"HB1559"}}
    -- the roll calls and divisions the chamber's journal prints in the
    sitting of this date and the measures it names, or None where the
    journal on disk opens no sitting on it. The Senate journal is on disk
    from 2003 and the House's from 1997. A House sitting printed only in a
    "(Cont.)" block is not read (journal_days.day_blocks), nor a Senate one
    no "The Senate met" line opens: the record then says nothing here."""
    if not date or not re.match(r"\d{4}-\d\d-\d\d$", date):
        return None
    if _JOURNALS is not None:
        # a check's own cut of the journals (load(journals=...)), never the
        # disk's: {(body, date): {"rc": [(y, n)], "div": [...], "bills": [...]}}
        g = _JOURNALS.get((body, date))
        return None if g is None else {
            "rc": collections.Counter(tuple(t) for t in g.get("rc", ())),
            "div": collections.Counter(tuple(t) for t in g.get("div", ())),
            "bills": set(g.get("bills", ())),
            # {bill: [(yeas, nays)]}, the counts printed after its heading
            **({"under": {b: collections.Counter(tuple(t) for t in ts)
                          for b, ts in g["under"].items()}}
               if g.get("under") is not None else {}),
            # [bill], those whose own stretch prints a decision
            **({"decided": set(g["decided"])} if g.get("decided") is not None else {})}
    import journal_days as J
    found = None
    for y in dict.fromkeys((date[:4], str(int(date[:4]) + 1)
                            if date[5:7] == "12" else date[:4])):
        key = (body, y)
        if key not in _SAT:
            got = {}
            root = J.HOUSE if body == "H" else J.SENATE
            for f in sorted((Path(root) / y).glob("*.txt")):
                if "erbatim" in f.name:
                    continue
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                text = text.replace("\r\n", "\n").replace("\r", "\n")
                blocks = J.day_blocks(text) if body == "H" else J.senate_sittings(text)
                rx = J.TALLY if body == "H" else SENATE_TALLY
                for d, block in blocks:
                    g = got.setdefault(d, {"rc": collections.Counter(),
                                           "div": collections.Counter(), "bills": set()})
                    for m in rx.finditer(block):
                        t = (int(m.group("yeas")), int(m.group("nays")))
                        # The Senate prints a division the way it prints a
                        # roll call, but after "A division vote was
                        # requested." and with no names voting Yes or No.
                        lead = block[max(0, m.start() - 300):m.start()]
                        division = (body == "S" and SENATE_DIVISION.search(lead)
                                    and not SENATE_NAMED.search(lead))
                        g["div" if division else "rc"][t] += 1
                    if body == "H":
                        g["div"].update((int(m.group("yeas")), int(m.group("nays")))
                                        for m in JOURNAL_DIVISION.finditer(block))
                        # Each count under the bill whose heading it follows
                        # (journal_days.bill_marks): _journal_checked holds a
                        # division the docket alone states to its own bill's.
                        marks = J.bill_marks(block)
                        under = g.setdefault("under", collections.defaultdict(
                            collections.Counter))
                        for m in list(JOURNAL_DIVISION.finditer(block)) + \
                                list(J.TALLY.finditer(block)):
                            b = None
                            for at, mb in marks:
                                if at > m.start():
                                    break
                                b = mb
                            if b:
                                under[b.split("-")[0]][
                                    (int(m.group("yeas")), int(m.group("nays")))] += 1
                        # The bills whose own stretch prints a decision -- a
                        # count, or a question carried or lost by voice: a
                        # bill named only in a list (HB 1398 of 15 February
                        # 2006, among the consent calendar's removals, whose
                        # debate is in a continuation not on disk) is not one.
                        joined = re.sub(r"(?<!\n)\n(?!\n)", " ", block)
                        points = sorted(
                            [m.start() for m in JOURNAL_DIVISION.finditer(block)]
                            + [m.start() for m in J.TALLY.finditer(block)]
                            + [m.start("s") for m in J.DECIDED.finditer(joined)
                               if not J.NOT_DECIDED.search(m.group("s"))])
                        decided = g.setdefault("decided", set())
                        for k, (at, mb) in enumerate(marks):
                            nxt = marks[k + 1][0] if k + 1 < len(marks) else len(block)
                            if mb and any(at <= p < nxt for p in points):
                                decided.add(mb.split("-")[0])
                    g["bills"] |= {a + b for a, b in JOURNAL_BILL.findall(block)}
            _SAT[key] = got
        g = _SAT[key].get(date)
        if g is not None:
            if found is None:
                found = {"rc": collections.Counter(), "div": collections.Counter(),
                         "bills": set()}
            found["rc"].update(g["rc"])
            found["div"].update(g["div"])
            found["bills"] |= g["bills"]
            for b, c in (g.get("under") or {}).items():
                found.setdefault("under", {}).setdefault(b, collections.Counter()).update(c)
            if g.get("decided") is not None:
                found.setdefault("decided", set()).update(g["decided"])
    return found


def _prints(body, date, tallies, tol=1):
    """Does the journal's sitting of this date print one of these counts as
    a roll call, give or take `tol` a side? None where the journal on disk
    opens no sitting on the date."""
    j = _journal_day(body, date)
    if j is None:
        return None
    return any(abs(y - a) <= tol and abs(n - b) <= tol
               for y, n in tallies for a, b in j["rc"])


def tie(it, r):
    """The floor motion `it` IS the roll call `r`: the kind is a roll call,
    the count is the ballots' (16 September: where the stated tally and the
    ballots differ the site publishes the ballots), and what it decided is
    what the record says it decided (rollcall_outcomes), which is the
    docket's word where the docket's word is possible on the count.

    ONE EXCEPTION, AND THE RECORD'S OWN: where the record's outcome cannot
    be true of the ballots' count -- SB 331 of 2018, 12-12 on the ballots and
    13-11 adopted in the Senate Permanent Journal by a Senate Clerk's note --
    the page keeps the count the outcome follows, and a reader is not shown
    a tie that carried."""
    ballots = (r["yeas"], r["nays"])
    passed = r.get("passed")
    corrected = (passed and ballots[0] <= ballots[1] and not r.get("threshold_needed")
                 and it.counted and it.yeas > it.nays)
    if it.counted and (it.yeas, it.nays) != ballots and not corrected:
        it.said = (it.yeas, it.nays)
        if it.need:
            it.need = r.get("threshold_needed") or it.need
    if not corrected:
        it.yeas, it.nays = ballots
    it.stated_kind = it.stated_kind or it.kind
    it.kind = "RC"
    if passed is not None:
        it.carried = bool(passed)
    if it.need is None and r.get("threshold_needed"):
        it.need = r["threshold_needed"]
    if r.get("threshold_unknown"):
        it.fifths = True
    it.rc = r


def _made(bill, term, action, mover, r, e=None, page=None):
    """A motion of its own for roll call `r`, from a docket row or clause
    (e) or from the roll-call file alone (e None)."""
    it = Item(bill, term, {"action": action, "mover": mover, "vote_kind": "RC",
                           "cite": (e or {}).get("cite") or "",
                           "cite_page": page}, 0)
    it.raw = ((e or {}).get("raw") or "").strip()
    it.yeas, it.nays = r["yeas"], r["nays"]
    it.carried = None if r.get("passed") is None else bool(r["passed"])
    it.need = r.get("threshold_needed")
    it.fifths = bool(r.get("threshold_unknown"))
    it.rc = r
    it.added = "row" if e is not None else "rollcall"
    if VETO_Q.search(action) and action.startswith("Override"):
        it.veto = True
    return it


# The kinds of question a roll call and a voice-voted motion of the same bill
# that day are compared by, where the docket has no count for the roll call:
# HB 1149 of 2022 was killed 283-43 on a roll call the docket enters as "MA
# VV". Only one roll call and one motion, of one kind, are ever matched so.
QUESTION_KINDS = [
    ("veto", r"veto|become\s+law"), ("reconsider", r"reconsid"),
    ("untable", r"(?:remove|take)\s+from\s+(?:the\s+)?table"),
    ("table", r"\btabl|\blay\b|\blaid\b"), ("nonconcur", r"non-?\s*conc"),
    ("conference", CONFERENCE_Q.pattern), ("concur", r"\bconcur"),
    ("amendment", r"amend|\bflam\b"), ("study", r"interim\s+study|\bRFS\b"),
    ("itl", r"inexpedient|\bITL\b"), ("postpone", r"postpone"),
    ("otp", r"ought\s+to\s+pass|\bOTP"),
]


# The kinds of question that are a bill's own disposition, never one motion
# entered on several bills' dockets.
UNSHARED = ("otp", "itl", "amendment", "conference", "concur", "nonconcur", "veto",
            "study")


def question_kind(text):
    for k, pat in QUESTION_KINDS:
        if re.search(pat, text or "", re.I):
            return k
    return None


THIRD_IN_LINE = re.compile(r"\b(?:O[Tt]\s*3rd\w*|Ordered\s+to\s+3rd\s+Reading)\b")
MOTION_TO_DIVIDE = re.compile(r"\bmotion\s+to\s+divide\b|\bmoved?\s+to\s+div(?:ide)?\b", re.I)
DIVIDE_PART = re.compile(r"\bdivide\s+sec(?:t(?:ion)?)?s?\b\.?\s*\d", re.I)
# The journal pages a 1989-2006 line cites in its own words: "HJ78,P2521-2523",
# "SJ6 P82-83".
CITED_PAGES = re.compile(r"\b[HS]J\s*\d+\w*\s*,?\s*P(?:G)?\.?\s*\d+(?:\s*-\s*\d+)?", re.I)
RESULT_CODE = re.compile(r"\b(?P<r>MA|MF|ML|AA|AF|AL)\b")


def _third_apart(it, o, r):
    """A Senate line of 1999-2002 that adopts the committee's amendment by
    voice and then fails to order the bill to third reading on a roll call:
    "Ought to Pass W/Amendment, {1066}, AA, VV, OT3rdg, RC 12Y-12N, MF" (SB 52
    of 1999). The reader keeps the third reading's result and count with the
    first motion's words, and the page said "Ought to Pass with Amendment"
    failed 12 to 12. Two questions: the amendment, adopted by voice, and the
    third reading, failed on the roll call. Returns the second as a motion
    of its own, with `it` put back to the first, or None."""
    raw = it.raw or ""
    t = None
    for t in THIRD_IN_LINE.finditer(raw, 0, o["start"]):
        pass
    if t is None or THIRD_IN_LINE.search(it.action or ""):
        return None
    if [p for p in o["row"] if t.end() <= p["start"] < o["start"]]:
        return None
    before = raw[:t.start()]
    codes = [m.group("r") for m in RESULT_CODE.finditer(before)]
    if not codes or [p for p in o["row"] if p["start"] < t.start()]:
        return None
    third = _made(it.bill, it.term, "Order to Third Reading", "", r, None, page=it.page)
    third.added, third.raw, third.cite = "row", raw, it.cite
    third.seq = it.seq + 0.001
    num = AMEND_NO.search(before)
    if codes[-1] in ("AA", "AF", "AL") and num:
        it.action = f"Adopt Committee Amendment {num.group('no')}"
        it.plain = True
    it.carried = CARRIED.get(codes[-1], codes[-1] == "AA")
    it.kind = "VV" if VOICE.search(before) else ""
    it.yeas = it.nays = None
    it.need = None
    return third


def _roll_calls(data, rolls, grouped, placed, base, sat=_sat, held=None):
    """Put every roll call in rollcalls.json on its sitting (above).

    `grouped` is {(body, date): [Item]} as the floor rows make it, and is
    added to; `placed` is {id(event): Item} for those rows; `base` the
    first sequence number of each (term, bill), so a motion made here sorts
    among its bill's own in the docket's order; `held` {term: {bill}} the
    bills of each term the General Court lists, or None where that list is
    not to hand. Returns ({(body, date):
    [Item]} the votes of each sitting that were on no bill, [(roll call,
    reason)] the roll calls no sitting draws, [(Item, body, date, reason)]
    the roll calls only the docket states that no sitting draws)."""
    left, others = [], collections.defaultdict(list)
    have = set(grouped)
    day_of = {id(i): key for key, items in grouped.items() for i in items}
    on = {}                      # rollcall_key -> sitting date drawn on
    tied_items = set()
    fresh = []                   # (body, [dates to try], Item, r, e)

    def place(body, item, dates, r, e=None):
        fresh.append((body, dates, item, r, e))

    every = []
    for term, bills in sorted((rolls or {}).items()):
        for key, rows in sorted(bills.items()):
            for r in rows:
                every.append((term, key, r))
    ROLLCALLS_FROM.clear()
    ROLLCALLS_FROM.update(ROLLCALLS_BEGIN)
    for b in ("H", "S"):
        ds = [r["date"] for _t, _k, r in every if r.get("body") == b and r.get("date")]
        ROLLCALLS_FROM[b] = min(ds + [ROLLCALLS_BEGIN[b]])

    loose = []                   # (term, bill or "", r)
    by_bill = collections.defaultdict(list)
    for term, key, r in every:
        bill = "" if key == "_procedural" else _bill_of(key)
        if bill and bill in (data.get(term) or {}):
            by_bill[(term, bill, r.get("body"))].append(r)
        else:
            # A bill the docket holds no rows for is still the bill the
            # roll-call file names: HB 476's reconsideration of 6 February
            # 2025, 15-340, on a bill withdrawn that day, was drawn among
            # the "votes on no bill". But not a bill the General Court's
            # list of the term does not hold (data/bills.json, `held`): the
            # Senate's 13-11 suspension of 27 June 2002 is filed under an SB
            # 457 of which there is none, and the record cannot say which
            # bill it was, so it is drawn plainly, as a vote of the day.
            named = BILL_KEY.match(bill) and (held is None or bill in held.get(term, ()))
            loose.append((term, bill if named else "", r))

    claimed = set()              # (id(event), offset) of each docket tally paired
    for (term, bill, body), rs in sorted(by_bill.items()):
        events = data[term][bill].get("events") or []
        occ = _tallies(events, body)
        got = _pair(rs, occ)
        claimed |= {(id(o["e"]), o["start"]) for o in got.values()}
        b0 = base.get((term, bill), 0)
        unpaired = []
        for r in sorted(rs, key=lambda x: (x["date"], x["number"])):
            o = got.get(id(r))
            if o is None:
                unpaired.append(r)
                continue
            e = o["e"]
            it = placed.get(id(e))
            if it is not None and id(it) not in day_of:
                it = None
            if it is not None and id(it) not in tied_items and _owns(it, o):
                third = _third_apart(it, o, r) if body == "S" else None
                if third is not None:
                    place(body, third, [day_of[id(it)][1]], r)
                    tied_items.add(id(third))
                    continue
                if not it.counted and len(o["row"]) > 1:
                    # owned by its clause's words (_owns): told as that
                    # clause tells it, "Sec 1" as Committee Amendment 0917's
                    action, mover, plain = _question(o, r)
                    if action:
                        it.action, it.plain = action, plain
                        it.mover = mover or it.mover
                tie(it, r)
                tied_items.add(id(it))
                on[rollcall_key(r)] = day_of[id(it)][1]
                continue
            action, mover, plain = _question(o, r)
            if it is not None:
                page = it.page
                at = _told_at(it, o["row"])
                new = _made(bill, term, action, mover, r, e, page)
                new.seq = it.seq + (0.001 * (o["k"] + 1) if o["start"] > at
                                    else -0.5 + 0.001 * (o["k"] + 1))
                new.plain = plain
                new.added = "row"
                place(body, new, [day_of[id(it)][1]], r, e)
            else:
                new = _made(bill, term, action, mover, r, e, _int(e.get("cite_page")))
                new.seq = b0 + o["n"] + 0.001 * (o["k"] + 1)
                new.plain = plain
                sitting = recess_sitting(e)
                dates = ([sitting] if sitting and (body, sitting) in have else [])
                if dates:
                    new.entered = (e.get("date") or "")[:10]
                    new.recess = bool(RECESS_OF.search(new.raw))
                place(body, new, dates or [o["own"], o["date"], r["date"]], r, e)
        for r in unpaired:
            if _second_look(r, term, bill, body, events, grouped, day_of, placed,
                            tied_items, on, place, b0):
                continue
            loose.append((term, bill, r))

    # ONE MOTION ON SEVERAL BILLS IS ONE ROLL CALL. A motion entered on each
    # bill's docket -- to reconsider the third reading of 35 Senate bills, to
    # suspend the rules for five new ones -- is held in the roll-call file
    # once, under one bill, under a rules number or under none, and a consent
    # calendar the Senate took by roll call is held as "Consent Calendar".
    # A drawn motion no roll call of its own bill accounts for is that roll
    # call where the day holds exactly one roll call of its count and kind
    # of question.
    unplaced = {rollcall_key(r) for _t, _b, r in loose}
    told = {}
    for key, items in grouped.items():
        for i in items:
            if i.rc is not None:
                told.setdefault(rollcall_key(i.rc), _motion_key(i.action))
    rc_by_day = collections.defaultdict(list)
    for term, key, r in every:
        rc_by_day[(r.get("body"), r.get("date"))].append(r)
    taken = set()
    for key, items in grouped.items():
        if key[1] < ROLLCALLS_FROM.get(key[0], "9999"):
            continue
        for it in items:
            if it.rc is None and not it.counted and it.kind in ("RC", ""):
                _count_on_line(it)
            if it.rc is not None or it.kind not in ("RC", "") or not it.counted:
                continue
            # A roll call another bill's motion already is, only where the
            # motion is one entered on several bills -- a special order, a
            # suspension, a tabling -- and never a bill's own disposition:
            # SB 198's and SB 330's committee amendments, 13-11 each on 14
            # February 2002, are two votes. AND ONLY WHERE THE JOURNAL NAMES
            # THIS BILL THAT DAY, where the journal is on disk: the docket
            # enters HB 1708's special order of 12 March 2026, 156-195, on HB
            # 1559 too, which the day's journal never names, and the page
            # said "One roll call on 2 bills".
            shareable = question_kind(it.action) not in UNSHARED
            if shareable:
                jd = _journal_day(key[0], key[1])
                shareable = jd is None or it.bill.upper() in jd["bills"]
            cands = [r for r in rc_by_day.get(key, ())
                     if (it.yeas, it.nays) in _tally_set(r)
                     and _bill_of(r.get("bill") or "") != it.bill.upper()
                     and (rollcall_key(r) in unplaced
                          or (shareable and told.get(rollcall_key(r))
                              == _motion_key(it.action)))]
            if len(cands) > 1:
                cands = _by_words(cands, it)
            if len(cands) != 1:
                continue
            r = cands[0]
            q = question_kind(r.get("question"))
            if not (it.consent or q is None or q == question_kind(it.action)):
                continue
            tie(it, r)
            tied_items.add(id(it))
            on.setdefault(rollcall_key(r), key[1])
            taken.add(rollcall_key(r))
    # The same motion on several bills, where no roll call that day has its
    # count: the clerk's "207-141" on three bills for the rules suspension
    # the roll-call file holds as 206-141 (21 March 2007), and Sen. Bradley's
    # suspension for four House bills, 16-6, entered on 4 January 2012 and
    # voted, by the roll-call file and the Senate Journal, on 7 September
    # 2011. One roll call on record that day within three of the count, or
    # the one of that count within the session, is the motion's.
    groups = collections.defaultdict(list)
    for key, items in grouped.items():
        if key[1] < ROLLCALLS_FROM.get(key[0], "9999"):
            continue
        for it in items:
            if it.rc is None and it.kind in ("RC", "") and it.counted and not it.consent:
                groups[(key, _motion_key(it.action), it.yeas, it.nays)].append(it)
    for (key, _m, y, n), its in groups.items():
        if len({(i.term, i.bill) for i in its}) < 2:
            continue
        free = [r for _t, _b, r in loose if rollcall_key(r) not in taken
                and r.get("body") == key[0] and _same_question(r, its[0])]
        near = [r for r in free if r.get("date") == key[1]
                and abs(r["yeas"] - y) <= 3 and abs(r["nays"] - n) <= 3]
        far = [r for r in free if (y, n) in _tally_set(r)
               and _apart(r.get("date"), key[1]) <= 160]
        cands = near or far
        if len(cands) != 1:
            continue
        for it in its:
            tie(it, cands[0])
            tied_items.add(id(it))
        on.setdefault(rollcall_key(cands[0]), key[1])
        taken.add(rollcall_key(cands[0]))
    loose = [x for x in loose if rollcall_key(x[2]) not in taken]

    # A ROLL CALL FILED UNDER ANOTHER BILL, OR UNDER NONE, THAT A DOCKET ROW
    # STATES. The Senate's 16-8 adoption of SB 287's conference report on 26
    # June 2025 is filed under HB 287, a bill the House had killed in
    # February; drawn under the file's bill with "the docket has no line for
    # this vote", the page put a conference report on a dead bill and left
    # SB 287's own row -- "Conference Committee Report # 2025-2797c; RC
    # 16Y-8N, Adopted" -- undrawn, and the Senate Journal prints SB 287. A
    # roll call no tally of its own bill's rows was paired with is the one
    # tally that day, on any bill's rows, that nothing else draws, with its
    # count and its kind of question.
    spare = _spare_tallies(data, placed, day_of, claimed)
    used, still = set(), []
    for term, bill, r in loose:
        cands = [x for x in spare.get((r.get("body"), r.get("date")), ())
                 if id(x[2]) not in used and (x[2]["y"], x[2]["nn"]) in _tally_set(r)
                 and _row_fits(r, x[2])]
        if len(cands) != 1 or QUORUM.search(r.get("question") or ""):
            still.append((term, bill, r))
            continue
        t2, b2, o = cands[0]
        used.add(id(o))
        e = o["e"]
        it = placed.get(id(e))
        action, mover, plain = _question(o, r)
        if it is not None and id(it) in day_of:
            new = _made(b2, t2, action, mover, r, e, it.page)
            at = _told_at(it, o["row"])
            new.seq = it.seq + (0.001 * (o["k"] + 1) if o["start"] > at
                                else -0.5 + 0.001 * (o["k"] + 1))
            dates = [day_of[id(it)][1]]
        else:
            new = _made(b2, t2, action, mover, r, e, _int(e.get("cite_page")))
            new.seq = base.get((t2, b2), 0) + o["n"] + 0.001 * (o["k"] + 1)
            dates = [o["own"], o["date"], r["date"]]
        new.plain = plain
        place(r.get("body"), new, dates, r, e)
    loose = still

    # BEFORE THE VOTING SYSTEM, THE DOCKET IS THE RECORD. A roll call the
    # docket states before rollcalls.json begins -- "COMM AM, AL RC(6-17);
    # LAID ON THE TABLE, SEN W. KING MA RC(16-7)" -- is drawn from the docket
    # alone, with the docket's count and the outcome its own words give, on a
    # sitting the floor rows already make; a row whose date is no sitting is
    # left, since nothing here can say a mistyped date from a sitting.
    left_docket = []
    for item, body, dates in _docket_only(data, placed, day_of, base):
        when = next((d for d in dates if d and (body, d) in have), None)
        if when is None:
            left_docket.append((item, body, dates[-1],
                                "a docket row of the years before the roll-call "
                                "file, dated on no sitting the floor rows make"))
            continue
        grouped[(body, when)].append(item)
        day_of[id(item)] = (body, when)

    # The motions made above, onto their sittings.
    for body, dates, item, r, e in fresh:
        when = _when(body, dates, r, have, sat)
        if when is None:
            left.append((r, "the docket and the roll-call file date it on no "
                            "sitting the record or the journal holds"))
            continue
        if (body, when) not in grouped:
            have.add((body, when))
        entered = (e.get("date") or "")[:10] if e else ""
        if entered and when != entered and not item.entered and \
                not _prints(body, entered, _tally_set(r)) and \
                _prints(body, when, _tally_set(r), 0):
            # put where the journal prints it (_when): the page says the
            # day the docket enters it
            item.entered = entered
        grouped[(body, when)].append(item)
        day_of[id(item)] = (body, when)
        on[rollcall_key(r)] = when
    _journal_dated(grouped, have, day_of, on)
    _fill_pages(grouped)

    # What no docket row states: under its bill where it has one, else among
    # the day's votes on no bill, on the day the roll-call file gives it --
    # or, where the chamber did not sit that day, on the sitting its
    # neighbours by number were drawn on (the House's roll calls of 24 and
    # 25 February 2021 are all dated the 26th).
    near = _neighbours(every, on)
    for term, bill, r in sorted(loose, key=lambda x: rollcall_key(x[2])):
        body = r.get("body")
        if QUORUM.search(r.get("question") or ""):
            left.append((r, "a quorum call, which puts no question"))
            continue
        when = _loose_day(r, body, have, near, sat)
        if when is None:
            left.append((r, "the roll-call file dates it on a day the chamber is "
                            "not recorded as sitting, and nothing places it"))
            continue
        action, mover = rollcall_question(r)
        if bill and VETO_Q.search(action or ""):
            # "Veto Override" (HB 396, 10 October 2024): the question every
            # veto row is told as, and what failing it did is the record's.
            action, mover = "Override the Governor's veto", ""
        it = _made(bill, term, action or "", mover, r, None, None)
        it.plain = not it.veto
        if not bill:
            it.bill = ""
            others[(body, when)].append(it)
            have.add((body, when))
            on[rollcall_key(r)] = when
            continue
        _anchor(it, grouped.get((body, when), []), base.get((term, bill), 0), r)
        grouped[(body, when)].append(it)
        have.add((body, when))
        on[rollcall_key(r)] = when

    _journal_checked(grouped)

    # How many bills' motions one roll call is drawn under, each day.
    for key, items in grouped.items():
        c = collections.Counter(rollcall_key(i.rc) for i in items
                                if i.rc is not None and not i.consent)
        for i in items:
            if i.rc is not None and not i.consent and c[rollcall_key(i.rc)] > 1:
                i.shared = c[rollcall_key(i.rc)]
    for v in others.values():
        v.sort(key=lambda i: rollcall_key(i.rc)[2])
    return others, left, left_docket


def _docket_only(data, placed, day_of, base):
    """[(Item, body, [dates to try])] -- a motion of its own for every roll
    call a docket row states before the roll-call file begins in its chamber
    that no floor motion tells, with the docket's count and the outcome the
    clause's own words give (rollcall_outcomes.outcome); and, in place, the
    count for a floor motion of those years whose line states its roll call
    in a form the reader did not take."""
    import rollcall_outcomes as RO
    out = []
    last = max(ROLLCALLS_FROM.values(), default="9999")[:4]
    for term, bills in sorted(data.items()):
        if term[:4] > last:
            continue
        for bill, rec in sorted(bills.items()):
            events = rec.get("events") or []
            for body in ("H", "S"):
                cut = ROLLCALLS_FROM.get(body, "9999")
                for o in _tallies(events, body):
                    if o["kind"] != "RC" or not o["date"] or o["date"] >= cut:
                        continue
                    e = o["e"]
                    it = placed.get(id(e))
                    if it is not None and id(it) in day_of and _owns(it, o):
                        if not it.counted:
                            # the line's own "RC" beside its count says how
                            # it was taken: "PASSED AND REF TO FIN DIV
                            # RC(19-4)" (SB 769 of 1994) is a roll call
                            it.yeas, it.nays = o["y"], o["nn"]
                            was, it.kind = it.kind, "RC"
                            if not (_contradicts(it) and not _names_question(it, o)):
                                continue
                            it.yeas = it.nays = None
                            it.kind = was
                        elif not (_contradicts(it) and not _names_question(it, o)):
                            continue
                        # THE COUNT IS ITS OWN CLAUSE'S, where the motion
                        # the reader made of the line came out the other
                        # way and the clause names another question: "OTP/AM
                        # ML RC(45-241); ITL REPORT ADOPTED" (HB 386,
                        # 3 January 1996) is Ought to Pass with Amendment
                        # lost 45 to 241, and the page said the report of
                        # Inexpedient to Legislate was adopted 45 to 241.
                        # The motion keeps its outcome; the count is drawn
                        # under the question its clause names, below.
                        _uncount(it)
                    raw = e.get("raw") or ""
                    carried, _clause, _how = RO.outcome(
                        [{"text": raw}], {"row": 0, "start": o["start"], "end": o["end"],
                                          "y": o["y"], "n": o["nn"], "text": raw})
                    action, mover, plain = _question(o, None)
                    new = Item(bill, term, {"action": action, "mover": mover,
                                            "vote_kind": "RC", "cite": e.get("cite") or "",
                                            "cite_page": e.get("cite_page")}, 0)
                    new.raw = raw.strip()
                    new.yeas, new.nays = o["y"], o["nn"]
                    new.carried = carried
                    _needs(new, _fraction(o.get("clause") or "", more=True))
                    new.plain = plain
                    new.added = "row"
                    if action.startswith("Override"):
                        new.veto = True
                    b0 = base.get((term, bill), 0)
                    if it is not None and id(it) in day_of:
                        new.page = it.page
                        new.seq = it.seq + (0.001 * (o["k"] + 1)
                                            if o["start"] > _told_at(it, o["row"])
                                            else -0.5 + 0.001 * (o["k"] + 1))
                        out.append((new, body, [day_of[id(it)][1]]))
                    else:
                        new.seq = b0 + o["n"] + 0.001 * (o["k"] + 1)
                        out.append((new, body, [o["own"], o["date"]]))
    return out


def _spare_tallies(data, placed, day_of, claimed):
    """{(body, date): [(term, bill, occurrence)]} -- the roll-call counts the
    docket's rows state from the roll-call file's first day on that no
    roll call on record was paired with (`claimed`) and no drawn floor
    motion tells: a vote whose row the reader typed as something other than
    a floor motion, on a bill the file holds no roll call for."""
    out = collections.defaultdict(list)
    first = min(ROLLCALLS_FROM.values(), default="9999")
    for term, bills in data.items():
        if term[5:9] < first[:4]:
            continue
        for bill, rec in bills.items():
            events = rec.get("events") or []
            for body in ("H", "S"):
                cut = ROLLCALLS_FROM.get(body, "9999")
                for o in _tallies(events, body):
                    if o["kind"] == "DV" or (o["date"] or "") < cut:
                        continue
                    if (id(o["e"]), o["start"]) in claimed:
                        continue
                    it = placed.get(id(o["e"]))
                    if it is not None and id(it) in day_of and (
                            (o["y"], o["nn"]) in it.tallies
                            or (not it.counted and _owns(it, o))):
                        continue
                    for d in dict.fromkeys((o["date"], o["own"])):
                        if d:
                            out[(body, d)].append((term, bill, o))
    return out


def _row_fits(r, o):
    """Could roll call `r` be the question docket tally `o` decides? Not a
    veto against one that is not, nor a suspension of the rules; and where
    both name a kind of question, the same kind."""
    q = r.get("question") or r.get("question_raw") or ""
    seg = _segment(o) or o["e"].get("raw") or ""
    if bool(VETO_Q.search(q)) != bool(VETO_Q.search(seg)) or \
            bool(SUSPEND_Q.search(q)) != bool(SUSPEND_Q.search(seg)):
        return False
    kq, ks = question_kind(q), question_kind(seg)
    return kq is None or ks is None or kq == ks


def _count_on_line(it):
    """The one roll call a floor motion's own line states, in a form the
    reader did not take: "Suspension of Rules, Introduced after deadlines &
    consideration at present time and immediate third reading, MA, RC
    (292-48)" (HR 25, 24 May 2006) was read with no count, so the one-motion
    pass below could not find it, and the roll call on record was drawn a
    second time among the day's votes on no bill. Only a line of one count;
    a line of several is told clause by clause (_owns)."""
    if it.kind == "VV" or it.veto:
        return
    ms = list(TALLY.finditer(it.raw or ""))
    if len(ms) != 1 or not (ms[0].group("kind") or "").upper().startswith(("RC", "ROLL")):
        return
    m = ms[0]
    it.yeas, it.nays = int(m.group("y")), int(m.group("n"))
    it.kind = "RC"


# A member named in a question: "Sen. Larsen", "Rep. P LaFlamme".
NAMED = re.compile(r"\b(?:Rep|Sen|Senator|Representative)s?\.?\s+(?:[A-Z]\.?\s+)?"
                   r"(?P<n>[A-Z][\w'’-]{2,})")


def _by_words(cands, it):
    """Of several roll calls on record whose count fits a docket motion, the
    one whose question names what the motion's line names -- the consent
    calendar, the motion's own bill, the member who moved it -- or none.

    The Senate's remote sittings of 2021 took every question by roll call,
    and nearly every one 24-0, so a count decides nothing: the consent
    calendar of 18 February 2021 was said on the consent list and drawn
    again as "Consent Calendar" among the votes on no bill, and HB 296's
    and HB 615's special order of 29 April as "Special Order HB 296-FN and
    HB 615-FN". On 7 June 2007 two rules suspensions of 17-7 are filed as
    "(Rule Suspension Sen. Larsen)" and "(Rule Suspension Sen. Gatsas)",
    and the docket enters them on CACR 19 and CACR 20, moved by each."""
    raw = f"{it.raw or ''} {it.mover or ''}"
    num = re.match(r"^([A-Z]+)(\d+)", (it.bill or "").upper())
    names = {m.group("n") for m in NAMED.finditer(raw)}
    tests = []
    if it.consent:
        tests.append(lambda q: bool(re.search(r"\bconsent\b", q, re.I)))
    if num:
        tests.append(lambda q: bool(re.search(
            rf"\b{num.group(1)}\s*{num.group(2)}\b", q, re.I)))
    if names:
        tests.append(lambda q: bool(names & {m.group("n") for m in NAMED.finditer(q)}))
    for test in tests:
        hit = [r for r in cands if test(r.get("question") or r.get("question_raw") or "")]
        if len(hit) == 1:
            return hit
    return []


def _same_question(r, it):
    """Could roll call `r` be the motion `it`? Not a veto question against
    one that is not, nor a suspension of the rules against one that is not;
    and where both name a kind of question, the same kind."""
    q, a = r.get("question") or r.get("question_raw") or "", it.action or ""
    if bool(VETO_Q.search(q)) != bool(VETO_Q.search(a)) or \
            bool(SUSPEND_Q.search(q)) != bool(SUSPEND_Q.search(a)):
        return False
    kq, ka = question_kind(q), question_kind(a)
    return kq is None or ka is None or kq == ka


def _second_look(r, term, bill, body, events, grouped, day_of, placed, tied_items,
                 on, place, b0):
    """A roll call of a bill no docket tally was paired with. True where it
    found its motion:

      - the bill's own row that day with the count in it and no kind before
        it ("Reconsider 18-311 (Rep. H. Howard): MF DV 031126", HB 1565 of
        2026; "Ought to Pass with Amendment #0417h (New Title): MA 213-141",
        HB 558 of 2010);
      - the one motion of its kind of question that bill had that day with
        no count of its own, or with a count within three of the ballots
        (the docket's "RC (211-79)" for 211-74, HB 1599 of 2006) -- where
        the docket says voice vote of a roll call (HB 1149 of 2022, killed
        283-43 on a roll call the docket enters "MA VV"), the roll call is
        the record of how it was decided."""
    want = _tally_set(r)
    for n, e in enumerate(events):
        if ((e.get("body") or "").strip().upper() != body or e.get("cancelled")
                or e.get("type") in NOT_THE_FLOOR):
            continue
        if (e.get("date") or "")[:10] != r["date"]:
            continue
        raw = e.get("raw") or ""
        for m in BARE.finditer(raw):
            if (int(m.group("y")), int(m.group("n"))) not in want:
                continue
            if DATE_IN.match(raw, max(0, m.start() - 3)):
                continue
            o = {"e": e, "n": n, "k": 0, "kind": "", "y": int(m.group("y")),
                 "nn": int(m.group("n")), "start": m.start(), "end": m.end(),
                 "date": r["date"], "own": None}
            o["row"] = [o]
            it = placed.get(id(e))
            if it is not None and id(it) in day_of and id(it) not in tied_items \
                    and it.kind != "VV":
                tie(it, r)
                tied_items.add(id(it))
                on[rollcall_key(r)] = day_of[id(it)][1]
                return True
            if it is None:
                action, mover, plain = _question(o, r)
                new = _made(bill, term, action, mover, r, e, _int(e.get("cite_page")))
                new.seq = b0 + n + 0.001
                new.plain = plain
                place(body, new, [r["date"]], r, e)
                return True
    kind = question_kind(r.get("question"))
    if kind is not None:
        it = _one_of_kind(r, kind, grouped.get((body, r["date"]), []), term, bill,
                          tied_items, 3)
        if it is not None:
            tie(it, r)
            tied_items.add(id(it))
            on[rollcall_key(r)] = r["date"]
            return True
    # A DAY OR TWO APART. The roll-call file dates HB 1599's kill of 2006,
    # 211-74, on 16 February; the docket enters it on the 15th as "ITL, MA,
    # RC (211-79)", and each was drawn on its own day's page, one vote on
    # two pages. SB 319's reconsideration of 2014, 94-169, is on the file's
    # 15 May and the docket's 16th ("Reconsideration (Rep Shurtleff) MF
    # 94-169"). The bill's own motion within NEAR_DAYS is the roll call's
    # where it is the only one that can be: its count on the line, or the
    # one motion of its kind of question with the record's outcome and a
    # count within five. Drawn where the motion is, and _journal_dated
    # then puts it where the journal prints it.
    near = []
    for n, e in enumerate(events):
        if ((e.get("body") or "").strip().upper() != body or e.get("cancelled")
                or e.get("type") in NOT_THE_FLOOR):
            continue
        if not 0 < _apart((e.get("date") or "")[:10], r["date"]) <= NEAR_DAYS:
            continue
        it = placed.get(id(e))
        if it is None or id(it) not in day_of or id(it) in tied_items or \
                it.kind == "VV" or it.rc is not None:
            continue
        raw = e.get("raw") or ""
        if any((int(m.group("y")), int(m.group("n"))) in want
               and not DATE_IN.match(raw, max(0, m.start() - 3))
               for m in BARE.finditer(raw)):
            near.append(it)
    if len(near) != 1 and kind is not None:
        days = [i for key, items in grouped.items() if key[0] == body
                and 0 < _apart(key[1], r["date"]) <= NEAR_DAYS for i in items]
        it = _one_of_kind(r, kind, days, term, bill, tied_items, 5)
        # not a voice vote on another day: that is another decision
        near = [it] if it is not None and it.kind != "VV" else []
    if len(near) != 1:
        return False
    it = near[0]
    tie(it, r)
    tied_items.add(id(it))
    on[rollcall_key(r)] = day_of[id(it)][1]
    return True


NEAR_DAYS = 3


def _one_of_kind(r, kind, items, term, bill, tied_items, within):
    """The one motion of the bill among `items` of the roll call's kind of
    question that can be it -- no count of its own, or one within `within`
    of the ballots -- or None."""
    cands = [i for i in items if i.bill == bill and i.term == term and i.rc is None
             and id(i) not in tied_items and question_kind(i.action) == kind]
    if len(cands) != 1:
        return None
    it = cands[0]
    if it.counted:
        if it.kind not in ("RC", "") or max(abs(it.yeas - r["yeas"]),
                                           abs(it.nays - r["nays"])) > within:
            return None
    elif it.kind not in ("VV", ""):
        return None
    # Never a motion the docket says came out the other way: the roll-call
    # file files the Senate's 14-10 kill of HB 617 (26 May 2005) under HB 611,
    # whose own motion to kill failed by voice that day; the 14-10 is HB 617's
    # docket roll call's (the one-motion pass in _roll_calls finds it there).
    if it.carried is not None and r.get("passed") is not None and \
            it.carried != bool(r["passed"]):
        return None
    return it


def _when(body, dates, r, have, sat):
    """The sitting a motion made from a docket row goes on: the first of the
    row's own stated date, the docket's date and the roll-call file's that
    is a sitting of the chamber's; else the roll-call file's date where the
    docket gives the same day (a day of conference reports and nothing
    else, 24 June 2009), or where the journal opens a sitting on it.

    UNLESS THE JOURNAL PRINTS THE VOTE ON ONE OF THOSE DAYS AND NOT THE
    OTHER. HB 2's amendment 1163h, 169-177, is entered in the docket on 5
    April 2017 and printed in House Journal 13 of Thursday 6 April, the day
    the roll-call file gives it; drawn on the 5th, the 6th's page said "1
    voice vote" of a day that took a roll call. The journal is the
    chamber's own account of its sitting, and where it prints the count on
    exactly one of the days in question, the vote is drawn there."""
    dates = [d for d in dates if d]
    if r is not None:
        want = _tally_set(r)
        cand = list(dict.fromkeys(dates + [r.get("date")]))
        printed = [d for d in cand if d and _prints(body, d, want, 0)]
        first = next((d for d in dates if (body, d) in have), None)
        if (len(printed) == 1 and printed[0] != first
                and not (first and _prints(body, first, want))
                and ((body, printed[0]) in have or sat(body, printed[0]))):
            return printed[0]
    for d in dates:
        if (body, d) in have:
            return d
    rd = r.get("date") if r else None
    if rd and rd in dates[:-1]:
        return rd
    for d in ([rd] if rd else []) + dates:
        if d and sat(body, d):
            return d
    return None


def _journal_dated(grouped, have, day_of, on):
    """A docket floor motion that is a roll call on record goes on the
    sitting whose journal prints the vote, where the docket enters it on a
    day whose journal does not.

    The roll-call file and House Journal 21 put all fifteen of SB 319's,
    SB 389's and SB 336's roll calls on Thursday 15 May 2014; the docket
    enters ten of them on the 16th and one on Monday the 19th, days the
    journal holds no sitting on, and the pages for those days said the
    House took nine roll calls and one. Only onto a sitting the record
    already holds, and the page says the day the docket enters it, as it
    does for business done in recess."""
    moves = []
    for (body, day), items in grouped.items():
        for it in items:
            r = it.rc
            if (r is None or it.consent or it.entered or it.added
                    or not r.get("date") or r["date"] == day):
                continue
            there = r["date"]
            if (body, there) not in have:
                continue
            want = it.tallies | _tally_set(r)
            if _prints(body, there, want, 0) and not _prints(body, day, want):
                moves.append((body, day, there, it))
    for body, day, there, it in moves:
        grouped[(body, day)].remove(it)
        it.entered = day
        grouped[(body, there)].append(it)
        day_of[id(it)] = (body, there)
        on[rollcall_key(it.rc)] = there
    for key in {(b, d) for b, d, _t, _i in moves}:
        if not grouped[key]:
            del grouped[key]
            have.discard(key)


def _journal_checked(grouped):
    """Where the chamber's journal is on disk, it is held to what the page
    counts as a roll call:

      - A DIVISION IS A DIVISION. Where the docket says division, or no roll
        call on record is the vote, and the House Journal prints that count
        only as a division -- "On a division vote, with 193 members having
        voted in the affirmative, and 177 in the negative" (HB 299, 20
        February 2025, "MA DV 193-177" in the docket) -- the page draws a
        division, though the roll-call file holds ballots for it.
      - A COUNT COPIED FROM ANOTHER ROW IS NOT ANOTHER ROLL CALL. HB 461's
        report of 22 January 2014 is entered "MA RC 289-48", HB 597's roll
        call on record that day; the journal prints 289-48 once, of HB 597,
        and HB 461's report "adopted and referred to the Committee on
        Finance" with no roll call. Where the page would count more votes of
        one count than the journal prints of it, and one of them is the
        roll call on record, a count only the docket states is taken off its
        motion: the motion and its outcome stay, the copied count does not.
        The Senate's "Enrolled RC 24Y-0N" of 2021 ("Adopted in recess", the
        journal says) and the docket's second 19-4 on SB 21 of 23 March 2017
        are the same.

    And without the journal: A RECESS TAKES NO ROLL CALL (unmarked_recess,
    above). The Senate's docket enters each enrolled bills report of its
    remote sittings of 2021 as "Enrolled RC 24Y-0N, MA, (In recess of
    04/08/2021)"; the roll-call file holds no such vote, and the Senate
    Journal says of each "Senator Avard moved adoption of the Report of
    Committee on Enrolled Bills. Adopted in recess." A count the docket
    states on business it marks as done in recess, which no roll call on
    record is, is not drawn."""
    for (body, day), items in grouped.items():
        for it in items:
            if it.kind == "RC" and it.counted and it.rc is None and \
                    RECESS_OF.search(it.raw or ""):
                _uncount(it)
        j = _journal_day(body, day)
        if j is None:
            continue
        for it in items:
            if it.kind != "RC" or not it.counted or it.consent:
                continue
            if it.rc is not None and not _says_division(it):
                continue
            counts = it.tallies
            if any(t in j["div"] for t in counts) and \
                    not any(t in j["rc"] for t in counts):
                it.kind = "DV"
        votes = {}
        for it in items:
            if it.kind != "RC" or not it.counted:
                continue
            k = (("rc",) + rollcall_key(it.rc) if it.rc is not None else
                 ("consent",) if it.consent else
                 ("motion", _motion_key(it.action), it.yeas, it.nays))
            votes.setdefault(k, []).append(it)
        rows = {(i.term, i.bill, i.raw) for k, its in votes.items() if k[0] == "rc"
                for i in its}
        gone = set()
        for k in [k for k in votes if k[0] == "motion"]:
            t = k[2:]
            # every vote the page draws within a vote of this count, and how
            # many the journal prints: the clerk's 207-141 is the 206-141 on
            # record (21 March 2007)
            # One off only where the journal prints no vote of this very
            # count: in a chamber of 24, 13-10 and 14-10 are two votes.
            by = 0 if j["rc"].get(t) else 1
            near = [v for v, its in votes.items()
                    if any(_near(t, x, by) for i in its for x in i.tallies)]
            printed = sum(c for x, c in j["rc"].items() if _near(t, x, by))
            if not printed or len(near) <= printed or \
                    not any(v[0] == "rc" for v in near):
                continue
            for it in votes.pop(k):
                if (it.term, it.bill, it.raw) in rows:
                    # the very row the roll call is drawn on, entered
                    # twice: HB 194's report of 4 January 2024
                    gone.add(id(it))
                elif JOURNAL_BILL.fullmatch(_spaced(it.bill)) and \
                        it.bill.upper() not in j["bills"]:
                    # a row copied onto a bill the day's journal never
                    # names: HB 1559's "Special Order to next order of
                    # business (Rep. Vallone): MF RC 156-195" of 12 March
                    # 2026 is HB 1708's motion, moved by Rep. Malone
                    gone.add(id(it))
                _uncount(it)
        _divisions_printed(body, j, items, gone)
        # A CONSENT CALENDAR IS ONE VOTE, AND THE JOURNAL PRINTS ITS COUNT.
        # The docket enters the House's calendar of 25 March 2014 as "Div
        # 282-9" on its bills and "289-9" on HB 1286 and HB 1348, and the
        # note said the calendar was adopted twice; the journal prints 282-9.
        # Where the journal prints one consent count of the day, a consent
        # count it prints nowhere comes off its bill, which stays on the list.
        if body == "H":
            cons = [it for it in items if it.consent and it.counted and it.rc is None]
            printed = j["div"] + j["rc"]
            if any(printed.get(t) for it in cons for t in it.tallies):
                for it in cons:
                    if not any(printed.get(t) for t in it.tallies):
                        _uncount(it)
        if gone:
            items[:] = [i for i in items if id(i) not in gone]
    # A COUNT AND AN OUTCOME THAT CANNOT BOTH BE TRUE ARE NEITHER DRAWN, from
    # 1999, where the docket alone states the vote. "Lay on Table: MA DV
    # 154-167" (HB 1134, 5 March 2026) is a motion carried with fewer yeas
    # than nays, and the journal says it failed; the ring drawn from it, which
    # marks one side the winner, said so too. The motion stays, with neither.
    for (body, day), items in grouped.items():
        if day < ROLLCALLS_BEGIN.get(body, "9999"):
            continue
        for it in items:
            if _against_its_count(it):
                _uncount(it)
                it.carried = None


def _divisions_printed(body, j, items, gone):
    """A DIVISION THE DOCKET ALONE STATES IS HELD TO THE HOUSE JOURNAL, as a
    roll call is (_journal_checked). The docket copies a division onto the
    wrong row as it copies a roll call: "Ought to Pass with Amendment
    2026-0610h: MA DV 176-160" is HB 1516's line of 12 March 2026, and the
    journal prints 176-160 for HB 1355 and says of HB 1516 "Majority
    committee report was adopted"; HB 652's recommittal of 7 January 2026 is
    entered "MA DV 183-161", SB 204's roll call, and the journal says "Motion
    was adopted"; and HB 446's report of 27 March 2025 is entered 202-166,
    where the journal prints 204-166 after HB 446's heading. So a division's
    count comes off its motion, which stays with its outcome, where the
    day's journal prints a count within three of it after the bill's own
    heading and the count itself nowhere, or prints the count fewer times than
    the docket's rows state it and after the heading of another bill whose
    own row states it. Not merely because the bill's own heading does not
    hold it: a motion to reconsider, to take from the table or to make a
    special order has no heading of its own, and the journal prints it under
    whichever came before. Held to its own bill's heading alone, this took
    the count off 302 divisions of 1997-2026, nearly all of them the
    journal's own; held as above it takes off 20, each read against the
    journal on 3 October 2026. One motion entered on several bills -- the
    resolution of 30 April 2014 that read 35 Senate bills a third time,
    carried 184-155 -- is printed once and is held to the day's journal
    printing it at all. And a copied row on a bill the day's journal never
    names is not drawn: HB 1114's "Remove from Table (Rep. Wade): MF DV
    123-207" of 11 March 2026 is HB 1814's motion."""
    under = j.get("under")
    if body != "H" or under is None:
        return
    rows = [it for it in items if it.kind == "DV" and it.counted
            and it.rc is None and not it.consent]
    def is_named(it):
        return not JOURNAL_BILL.fullmatch(_spaced(it.bill)) or \
            it.bill.upper() in j["bills"]
    bills = collections.defaultdict(set)
    some_named = collections.defaultdict(bool)
    for it in rows:
        key = (_motion_key(it.action), it.yeas, it.nays)
        bills[key].add(it.bill)
        some_named[key] |= is_named(it)
    printed = j["div"] + j["rc"]
    for it in rows:
        named = is_named(it)
        mine = under.get(it.bill.upper(), collections.Counter())
        key = (_motion_key(it.action), it.yeas, it.nays)
        if len(bills[key]) > 1:
            # A motion on "the remainder of bills on today's calendar"
            # (10 March 2016) names none of them; one that the journal makes
            # of one bill and not another is that bill's.
            off = not any(t in printed for t in it.tallies) or \
                (not named and some_named[key])
            named = named or not some_named[key]
        elif any(t in mine for t in it.tallies):
            off = not named
        else:
            near = any(not printed.get(t) and _near(t, x, 3)
                       for t in it.tallies for x in mine)
            # More rows state the count than the journal prints it -- four
            # divisions of 176-169 on 23 February 2023 are four, each
            # printed -- and one of the others is printed after its own
            # bill's heading.
            stated = sum(1 for o in items if o.counted and it.tallies & o.tallies)
            copied = any(stated > printed.get(t, 0) > 0 for t in it.tallies) and any(
                t in under.get(o.bill.upper(), ()) for o in items
                if o.bill != it.bill and o.counted for t in it.tallies & o.tallies)
            off = near or copied
            # THE JOURNAL'S OWN COUNT, WHERE IT PRINTS ONE UNDER THE BILL. A
            # count taken off as a typo or a copy took the division with it:
            # HB 446's report of 27 March 2025 is entered 202-166, HB 557's,
            # and House Journal 11 prints 204-166 after HB 446's own heading;
            # the page said "The motion was adopted" with no count, the
            # opening one division short, and Reps. Kluger and Litchfield, who
            # spoke before the 204-166, were named nowhere. Where exactly one
            # division the journal prints after the bill's heading is within
            # three of the docket's count, and no other motion of the day is
            # drawn with it, the division is drawn with the journal's count.
            if off and named:
                own = [x for x in mine if x in j["div"] and not j["rc"].get(x)
                       and any(_near(t, x, 3) for t in it.tallies)]
                if len(own) == 1 and not any(own[0] in o.tallies for o in items
                                             if o is not it):
                    it.yeas, it.nays = own[0]
                    continue
            # NOR A COUNT THE JOURNAL PRINTS NOWHERE, for a bill whose own
            # stretch of the day's journal prints a decision. "153 yeas, 29
            # nays" on CACR 4's motion to table of 23 March 2023, where the
            # journal prints 153-229; 191-158 on HB 1442's special order of 5
            # March 2026, where it says "Motion was adopted." The motion and
            # its outcome stay; the count goes. Not where the journal on disk
            # names the bill only in a list: its debate can be in a part of
            # the sitting no file here holds.
            told = j.get("decided")
            if not off and named and not any(printed.get(t) for t in it.tallies) and \
                    (told is None or it.bill.upper() in told):
                off = True
        if not off:
            continue
        if not named:
            gone.add(id(it))
        _uncount(it)


def _says_division(it):
    """Did the docket say this motion was decided on a division? Its kind
    before tie() made it a roll call, or its line where the reader read no
    kind: "Reconsider 18-311 (Rep. H. Howard): MF DV 031126" (HB 1565 of
    2026)."""
    if it.stated_kind:
        return it.stated_kind == "DV"
    raw = it.raw or ""
    return bool(re.search(r"\b(?:DV|DIV|Division)\b", raw)) and \
        not re.search(r"\bRC\b|\bRoll\s+Call\b", raw, re.I)


def _spaced(bill):
    """"HB1559" as a journal prints it, "HB 1559"."""
    return re.sub(r"^([A-Z]+)(\d)", r"\1 \2", (bill or "").upper())


def _near(a, b, by=1):
    return abs(a[0] - b[0]) <= by and abs(a[1] - b[1]) <= by


def _contradicts(it):
    """Does the motion's outcome contradict its count? A motion does not
    carry without more yeas than nays, and fails with more only where it
    needed more than a majority -- which an amendment never does: "COMM AM,
    AA DIV(173-141); 3RD READING FAILS 3/5 RC(197-126)" (CACR 20, 11 February
    1992) is not the committee amendment failing 197 to 126."""
    if not it.counted or it.carried is None:
        return False
    if it.carried:
        return it.yeas <= it.nays
    amendment = question_kind(it.action) == "amendment" and \
        not NOT_AMENDING.search(it.action or "")
    return it.yeas > it.nays and (amendment or not (it.need or it.fifths or it.veto))


# The questions a majority decides: never a suspension, a special order, a
# veto, three fifths, or a constitutional amendment's passage.
MAJORITY_KINDS = ("table", "untable", "reconsider", "concur", "nonconcur", "amendment",
                  "study", "itl", "otp", "postpone")


def _against_its_count(it):
    """Does a count only the docket states contradict the motion's outcome:
    carried with no more yeas than nays, or, on a question a majority
    decides, lost with more?"""
    if not it.counted or it.carried is None or it.rc is not None:
        return False
    if it.carried:
        return it.yeas <= it.nays
    if (it.need or it.fifths or it.veto or it.bill.upper().startswith("CACR")
            or SUSPEND_Q.search(it.action or "") or THIRD_Q.match(it.action or "")
            or re.search(r"(?<![\d/])\d\s*/\s*\d(?![\d/])|\bnec(?:essary)?\b|thirds|fifths",
                         it.raw or "", re.I)):
        return False
    return it.yeas > it.nays and question_kind(it.action) in MAJORITY_KINDS


def _uncount(it):
    """Take a count the docket alone states off its motion: the motion and
    its outcome stay, drawn as the docket words them."""
    it.yeas = it.nays = None
    it.kind = ""
    it.need = None
    it.fifths = False
    words = INLINE_COUNT.sub("", it.action or "")
    if words != it.action:
        it.action = words.strip(" ,;:") or it.action


def _neighbours(every, on):
    """{rollcall_key: [(number, time, date drawn on)]} -- the roll calls of
    each roll-call date in each chamber and year, with where each was drawn."""
    out = collections.defaultdict(list)
    for _t, _k, r in every:
        k = rollcall_key(r)
        if k in on:
            out[(k[0], k[1], r.get("date"))].append((k[2], r.get("time") or "", on[k]))
    for v in out.values():
        v.sort()
    return out


def _loose_day(r, body, have, near, sat):
    """The sitting a roll call no docket row states is drawn on."""
    k = rollcall_key(r)
    rows = near.get((k[0], k[1], r.get("date")), [])
    lo = [x for x in rows if x[0] < k[2]]
    hi = [x for x in rows if x[0] > k[2]]
    lo, hi = (lo[-1] if lo else None), (hi[0] if hi else None)
    there = None
    if lo and hi:
        if lo[2] == hi[2]:
            there = lo[2]
        elif (r.get("time") or "") and lo[1] and (r.get("time") or "") < lo[1]:
            there = hi[2]
        else:
            there = lo[2]
    elif lo or hi:
        there = (lo or hi)[2]
    day = r.get("date")
    if there and there != day:
        # The House Journal decides where it prints the count in one of the
        # two sittings and not the other: SB 319's reconsideration, 94-169,
        # is printed on 15 May 2014 -- the roll-call file's date -- though the
        # roll calls on either side of it are on the docket's 16 May.
        want = _tally_set(r)
        here, then = _journal(body, day), _journal(body, there)
        if then and then & want and not (here and here & want) and (body, there) in have:
            return there
        if here and here & want and not (then and then & want):
            return day
        if lo and hi and lo[2] == hi[2] and (body, there) in have:
            return there
    if (body, day) in have or sat(body, day):
        return day
    if there and (body, there) in have:
        return there
    return None


def _anchor(it, day, b0, r):
    """Where on its sitting a roll call the docket has no row for is drawn:
    after the motion of the day whose roll call came just before it, which is
    the House's own order by number and clock, and in its bill's place
    otherwise."""
    # Only by a roll call whose motion has a journal page: a day the record
    # gives no order to is listed by bill, and a roll call placed by its
    # number put HB 287 between HB 115 and HB 2 on the Senate's page of 26
    # June 2025 and HB 1370's report between HB 1292's two motions on 13
    # June 2024.
    before = [i for i in day if i.rc is not None and i.page is not None
              and rollcall_key(i.rc)[0] == rollcall_key(r)[0]
              and rollcall_key(i.rc)[2] < rollcall_key(r)[2]]
    mine = [i for i in day if i.bill == it.bill and i.term == it.term]
    if before:
        a = max(before, key=lambda i: rollcall_key(i.rc)[2])
        if a.bill == it.bill or not mine:
            it.page, it.seq = a.page, a.seq + 0.0001 * (1 + rollcall_key(r)[2] % 1000)
            it.entered = a.entered
            return
    if mine:
        a = max(mine, key=lambda i: i.seq)
        it.page, it.seq, it.entered = a.page, a.seq + 0.0001, a.entered
        return
    it.seq = b0 + 0.5


def _fill_pages(grouped):
    """A motion made from a row that cites no journal page takes the page of
    its bill's next motion that day, so a House sitting in the journal's
    order keeps it with its bill rather than first in the day."""
    for items in grouped.values():
        for it in items:
            if it.added != "row" or it.page is not None:
                continue
            mine = sorted((i for i in items if i.bill == it.bill and i.term == it.term
                           and i.page is not None), key=lambda i: i.seq)
            later = [i for i in mine if i.seq > it.seq]
            if later:
                it.page = later[0].page
            elif mine:
                it.page = mine[-1].page


def load(path=NARRATIVES, rollcalls=None, sat=None, journals=None):
    """Every sitting day, as {(body, date): Day}.

    The roll calls are the rollcalls.json beside the narratives.json read,
    unless `rollcalls` names a file or gives them already read: a record cut
    for a check is held to its own roll calls, never to the site's. `sat`
    says whether the journal opens a sitting on a date (_sat by default), and
    `journals` gives the journals' votes in place of the disk's, for a check
    that must not read them: {(body, date): {"rc": [(yeas, nays)], "div":
    [...], "bills": ["HB1559"], "under": {"HB1355": [(yeas, nays)]}}}
    (_journal_day; "under" optional).

    Ordered within a day by the journal page the action is printed on, which
    is the clerk's own ordering and the only one available -- the events carry
    no time. Rows with no page keep their relative order and sort first, so a
    missing citation never silently reorders the ones that have it -- except
    business done in recess, which the journal prints after the sitting's
    own and which goes with what was entered on the same day as it.
    """
    p = Path(path)
    # SILENCE IS NOT SUCCESS. Without this the whole feature builds cleanly and
    # emits nothing, which looks exactly like a chamber that never sat.
    assert p.exists(), f"{path} is not here; run build_narratives first"
    data = json.loads(p.read_text(encoding="utf-8"))

    grouped = collections.defaultdict(list)
    recess = []
    seq = 0
    # The docket's order, by event: a motion made from a row of another
    # type (_roll_calls) sorts among its bill's floor motions where its row is.
    placed, base = {}, {}
    for term, bills in sorted(data.items()):
        for bill, rec in sorted(bills.items()):
            events = rec.get("events") or []
            base[(term, bill)] = seq
            at = {id(e): n for n, e in enumerate(events)}
            seq += len(events) + 1
            for e, it in floor_items(bill, term, events):
                body = (e.get("body") or "").strip().upper()
                date = (e.get("date") or "")[:10]
                if body not in ("H", "S") or not re.match(r"\d{4}-\d\d-\d\d$", date):
                    continue
                it.seq = base[(term, bill)] + at[id(e)]
                placed[id(e)] = it
                sitting = recess_sitting(e)
                if sitting:
                    it.recess = bool(RECESS_OF.search(it.raw))
                    recess.append((body, date, sitting, it))
                else:
                    grouped[(body, date)].append(it)

    # Onto the sitting only where the record holds it, and where the row's
    # journal is that sitting's journal.
    for body, date, sitting, it in recess:
        there = grouped.get((body, sitting))
        cites = {i.cite for i in there or () if i.cite}
        if there and (not it.cite or not cites or it.cite in cites):
            it.entered = date
            there.append(it)
        else:
            it.recess = False
            grouped[(body, date)].append(it)

    # Then what the docket does not mark, by the journal it cites.
    for body, date, sitting, it in unmarked_recess(grouped):
        grouped[(body, date)].remove(it)
        it.entered = date
        grouped[(body, sitting)].append(it)
    for key in [k for k, items in grouped.items() if not items]:
        del grouped[key]

    for key in [k for k, items in grouped.items() if _rule_only_weekend(k[1], items)]:
        del grouped[key]

    assert grouped, ("no floor events in narratives.json -- every sitting day "
                     "page would be empty, and the build would not say so")

    rolls = _read_rollcalls(Path(path).parent / ROLLCALLS if rollcalls is None
                            else rollcalls)
    need = _fifths_from_rollcalls(rolls)
    for (body, date), items in grouped.items():
        for it in items:
            if it.fifths and it.counted:
                got = need.get((body, date, it.yeas, it.nays))
                if got and len(got) == 1:
                    it.need = next(iter(got))

    calendars = _calendar_rollcalls(rolls)
    for key, items in grouped.items():
        _one_counted_vote(items, calendars.get(key, frozenset()))
        for it in items:
            _conference_named(it)
    # Every roll call on record, onto its sitting (_roll_calls).
    global _JOURNALS
    was, _JOURNALS = _JOURNALS, journals
    try:
        others, left, left_docket = _roll_calls(data, rolls, grouped, placed, base,
                                                sat or _sat, _held_bills(p.parent))
    finally:
        _JOURNALS = was
    for (body, date), items in grouped.items():
        for it in items:
            # A motion with a roll call of its own is not a consent item,
            # whatever its count shares with the calendar's: SB 138 of 1
            # April 2021 was voted on alone, 23 to 1, the calendar's count.
            if it.consent and it.rc is not None and \
                    _bill_of(it.rc.get("bill") or "") == it.bill.upper():
                it.consent = False

    days = Sittings()
    days.left = left
    days.left_docket = left_docket
    for key in list(grouped) + [k for k in others if k not in grouped]:
        items = grouped.get(key, [])
        # A recess row with no page is not first: HB 1695's refusal, entered
        # on 24 May 2024 with no page, is printed among that day's page 177.
        last = max((i.page for i in items if i.page is not None), default=-1)
        batch = {}
        for i in items:
            if i.entered and i.page is not None:
                batch[i.entered] = max(batch.get(i.entered, -1), i.page)
        items.sort(key=lambda i: (
            i.page if i.page is not None
            else batch.get(i.entered, last) if i.entered else -1, i.seq))
        days[key] = Day(key[0], key[1], items, others.get(key, ()))
        was, _JOURNALS = _JOURNALS, journals
        try:
            days[key].printed = _journal_day(key[0], key[1])
        finally:
            _JOURNALS = was
        # One motion the docket enters on several bills and the roll-call
        # file holds as one vote or not at all is one roll call, and says so
        # under each bill as a roll call on record does (_roll_calls).
        for kind in ("RC", "DV"):
            for k, its in days[key].votes(kind).items():
                if k[0] == "motion":
                    for i in its:
                        i.shared = len(its)
    return days


# A COMMITTEE OF CONFERENCE REPORT TOLD AS "OUGHT TO PASS". The 1999-2006
# reader takes the bare "Adopted" of "Conference Committee Report{2254}, RC
# 18Y-6N, Adopted" for the question, and its words for "Adopted" are "Ought
# to Pass": 89 Senate motions of those years read "On the motion: Ought to
# Pass ... it carried in this chamber" of a vote on a conference report, HB 1
# and HB 2 of 2003 and 2005 among them, and one read "On the motion: Cohen".
# The bill's own history says the same and is the docket reader's to put
# right; the sitting page names the question the row names.
CONFERENCE_ROW = re.compile(
    r"^\s*(?:New\s+)?(?:Conf(?:erence)?\.?\s*Comm(?:ittee)?\.?\s*Rep(?:ort)?\b|"
    r"Committee\s+of\s+Conference\s+Report)", re.I)


def _conference_named(it):
    # Only where the motion the reader made of the row is its "Ought to
    # Pass", or no motion at all: "Conference Comm Report, ML RC(133-171);
    # Rep Norelli Susp Rules for new Conf Comm, MA 2/3VV" (HB 2004 of 25 May
    # 2004) is told by its second clause, the suspension, which stands.
    a = it.action or ""
    if it.veto or not CONFERENCE_ROW.match(it.raw or "") or CONFERENCE_Q.search(a) \
            or SUSPEND_Q.search(a) or question_kind(a) not in (None, "otp"):
        return
    num = re.search(r"[{#(]\s*((?:\d{4}-)?\d{4}c?)\b", it.raw)
    it.action = "Adopt the Conference Committee Report" + (f" {num.group(1)}" if num else "")
    it.mover = ""
    it.plain = True


def _held_bills(root):
    """{term: {bill}} -- every bill of each term in data/bills.json beside
    the narratives read, or None where it is not there (a check's own cut of
    the record): a bill the roll-call file names is then taken as named."""
    f = Path(root) / "data" / "bills.json"
    try:
        got = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {t: set(b) for t, b in got.items() if isinstance(b, dict)} if isinstance(got, dict) else None


class Sittings(dict):
    """{(body, date): Day}, and `left`: [(roll call, reason)] for each roll
    call on record that no sitting draws, so that a check can hold every
    one of them to a reason; `left_docket` the same for a roll call only the
    docket states, before the roll-call file: [(Item, body, date, reason)]."""
    left = ()
    left_docket = ()


def _read_rollcalls(path=ROLLCALLS):
    """rollcalls.json as {term: {bill key: [row]}}, or {} where it is not
    here -- a sitting page is then the docket's alone, as before 1999."""
    if isinstance(path, dict):
        return path
    p = Path(path) if path else None
    if p is None or not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def drawn(days):
    """{rollcall_key: (body, date)} -- where each roll call on record is
    drawn, from load()'s days."""
    out = {}
    for (body, date), d in days.items():
        for i in list(d.items) + list(d.others):
            if i.rc is not None:
                out.setdefault(rollcall_key(i.rc), (body, date))
    return out


def one(body, date, path=NARRATIVES):
    return load(path).get((body.strip().upper(), date))


# ------------------------------------------------- a sitting that never was --
#
# ONE MISTYPED DATE PUBLISHES A WHOLE SITTING. Every (chamber, date) that
# carries a floor action becomes a page, so "Reconsider HB1491 ... MF VV
# 09/19/2026 HJ 16 P. 48", written at 2:27 PM on 19 August four pages after
# that afternoon's veto vote, built "The House, Saturday 19 September 2026"
# and linked it as the sitting after veto day. Eleven such pages were live.
# docket_corrections.json puts the rows right; this is how the next one is
# noticed rather than published.

def _nth_weekday(y, m, wd, n):
    d = _date(y, m, 1)
    return d.fromordinal(d.toordinal() + (wd - d.weekday()) % 7 + 7 * (n - 1))


def holidays(year):
    """The state's legal holidays in a year: the fixed ones, and Civil Rights
    Day, Presidents Day, Memorial Day, Labor Day and Thanksgiving with the day
    after it. Neither chamber has sat on one in the record."""
    last_may = _date(year, 5, 31)
    thanks = _nth_weekday(year, 11, 3, 4)
    return {_date(year, 1, 1), _nth_weekday(year, 1, 0, 3),
            _nth_weekday(year, 2, 0, 3),
            last_may.fromordinal(last_may.toordinal() - last_may.weekday()),
            _date(year, 7, 4), _nth_weekday(year, 9, 0, 1), _date(year, 11, 11),
            thanks, thanks.fromordinal(thanks.toordinal() + 1),
            _date(year, 12, 25)}


def journal_series(date):
    """The year whose journal numbering a sitting's date belongs to. Numbers
    restart each session, and the December organization day opens the NEXT
    year's: journals/2023/HJ 01 December 7, 2022.txt."""
    return str(int(date[:4]) + 1) if date[5:7] == "12" else date[:4]


JOURNAL_NO = re.compile(r"^([HS])J\s*(\d+)$")


def read_rollcall_dates(paths):
    """{body: {iso date}} on which that chamber took a roll call, from
    RollCallSummary files. The voting system dates these, not the docket --
    with one caveat measured on 2020-21, when the House sat away from the
    State House and its roll calls were dated a day late."""
    out = collections.defaultdict(set)
    for f in paths:
        with open(f, encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                p = line.split("|")
                m = (re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", p[3].strip())
                     if len(p) > 3 else None)
                if m:
                    out[p[1].strip().upper()].add(
                        f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}")
    return out


def doubtful(days, today=None, rollcall_dates=None):
    """{(body, date): [reason, ...]} for the sitting days the record itself
    casts doubt on. A day is doubtful when it

      - is after `today` (the build date);
      - falls on a Saturday, a Sunday or a state holiday;
      - or when every one of its actions that cites a journal cites one whose
        other actions sit, three to one or more, on a single other date --
        and the chamber took no roll call that day.

    The last is the rule that caught the typed-wrong dates: the HB 1491 row
    cites HJ 16, and the other 88 House rows citing HJ 16 of 2026 are dated
    19 August. It is a flag for a person, not a verdict -- a day can be
    doubtful and real -- and it cannot see a slipped year (01/08/2019 for
    01/09/2018), which only the corrections file catches.
    """
    today = today or build_date.today()
    rc = rollcall_dates or {}
    by_cite = collections.defaultdict(collections.Counter)
    for (body, date), d in days.items():
        for i in d.items:
            m = JOURNAL_NO.match(i.cite or "")
            if m:
                by_cite[(body, journal_series(date), int(m.group(2)))][date] += 1
    out = {}
    for (body, date), d in sorted(days.items()):
        x = _date.fromisoformat(date)
        why = []
        if x > today:
            why.append("after the build date")
        if x.weekday() >= 5:
            why.append(DAYNAME[x.weekday()])
        if x in holidays(x.year):
            why.append("a state holiday")
        cited = [JOURNAL_NO.match(i.cite or "") for i in d.items]
        cited = [m for m in cited if m]
        if cited and date not in rc.get(body, ()):
            homes = set()
            for m in cited:
                c = by_cite[(body, journal_series(date), int(m.group(2)))]
                top, tn = max(((k, v) for k, v in c.items() if k != date),
                              key=lambda kv: (kv[1], kv[0]), default=(None, 0))
                homes.add(top if top and tn >= 3 and c[date] * 3 <= tn else None)
            if None not in homes:
                why.append("its journal belongs to " + ", ".join(sorted(homes)))
        if why:
            out[(body, date)] = why
    return out


DAYNAME = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--body", default="")
    ap.add_argument("--date", default="")
    a = ap.parse_args()

    days = load()
    if a.date:
        d = days.get(((a.body or "H").upper(), a.date))
        if not d:
            raise SystemExit(f"no sitting on {a.date} for {a.body or 'H'}")
        print(f"{d!r}  {d.journal}\n")
        for i in d.items:
            t = f"{i.yeas}-{i.nays}" if i.counted else ""
            print(f"  p{i.page or '?':<4} {i.bill:10} {i.action[:44]:44} "
                  f"{i.kind:3} {t:9} {i.outcome_words}")
        return 0

    by_body = collections.Counter(k[0] for k in days)
    yrs = collections.Counter(k[1][:4] for k in days)
    print(f"{len(days):,} sitting days: House {by_body['H']:,}, "
          f"Senate {by_body['S']:,}")
    print(f"  {min(k[1] for k in days)} to {max(k[1] for k in days)}, "
          f"{len(yrs)} calendar years")
    print(f"  {sum(len(d) for d in days.values()):,} floor actions in all")
    kinds = collections.Counter()
    for d in days.values():
        for i in d.items:
            kinds[i.kind_words or "unrecorded"] += 1
    for k, v in kinds.most_common():
        print(f"  {v:7,}  {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
