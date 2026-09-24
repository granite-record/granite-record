#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.5
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

THE THREE VOTES, AND WHY THE TALLY NEVER DECIDES

  roll call   vote_kind RC, with yeas and nays, and ballots in rollcalls/
  division    vote_kind DV, with yeas and nays and no names -- nobody recorded
              who voted which way, which is what a division IS
  voice       vote_kind VV, no count at all

WHICH SIDE PREVAILED IS `motion`, NEVER THE LARGER NUMBER. It is MA (motion
adopted) or MF (motion failed), stated by the clerk. Inferring it from the
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

NARRATIVES = "narratives.json"

# The clerk's shorthand, expanded. MA and MF are the only two that decide
# anything; the rest appear in `raw` and are not relied on here.
CARRIED = {"MA": True, "MF": False}

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
    if a.startswith("override the governor"):
        return ("the veto was overridden and the bill became law without the "
                "Governor" if carried else
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
    if a.startswith(PASSES):
        return ("it carried in this chamber" if carried
                else "it did not carry in this chamber")
    return None


# THE SENATE WRITES ITS VOTE INSIDE THE MOTION. "Ought to Pass RC 19Y-5N,
# 3/5 nec., MA; OT3rdg" is one Senate action: the kind, the tally and the
# threshold are all in the prose, and the vote_kind, yeas and nays fields are
# empty. 1,445 Senate actions are like this and no House action is.
INLINE_VOTE = re.compile(r"\b(?P<kind>RC|DV|VV)\s*(?P<y>\d+)\s*Y\s*-\s*"
                         r"(?P<n>\d+)\s*N", re.I)

# "3/5 nec." and "2/3 nec." -- the motion needed a supermajority. Drawn as a
# simple majority the threshold mark on the ring sits in the wrong place and
# the chart says a motion cleared a bar it did not have to clear, or missed one
# it never faced. The House spells it out -- "By Necessary Three-Fifths Vote",
# "Lacking Necessary Two-Thirds Vote" -- and was drawn at a majority.
THRESHOLD = re.compile(r"\b(?P<a>\d)\s*/\s*(?P<b>\d)\s*nec", re.I)
THRESHOLD_WORDS = re.compile(r"\b(?:two|three)[\s-]*(?P<f>thirds|fifths)\b", re.I)

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
CONSENT_OFF = re.compile(r"removed\s+from\s+(?:the\s+)?(?:consent|cons\b|cons\.|CC\b)",
                         re.I)

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


def _one_counted_vote(items):
    """A consent calendar is ONE motion, so a counted vote on it is one tally
    shared by every bill on it.

    The Senate took the whole calendar by roll call through 2021 -- 23 to 1
    on 22 April 2021, and every bill on it carries that tally -- and the
    House divided on its calendar of 25 March 2014, 282 to 9. A roll call or
    division that belongs to one bill alone was a vote on that bill, taken
    after it came off the calendar, and is not a consent item.
    """
    counted = collections.Counter((i.kind, i.yeas, i.nays) for i in items
                                  if i.consent and i.kind in ("RC", "DV"))
    for i in items:
        if i.consent and i.kind in ("RC", "DV") and \
                counted[(i.kind, i.yeas, i.nays)] < 2:
            i.consent = False


VETO_TALLY = re.compile(r"\bRC\s*\(?\s*(?P<y>\d+)\s*Y?\s*-\s*"
                        r"(?P<n>\d+)\s*N?\s*\)?", re.I)
OVERRIDDEN = re.compile(r"\boverrid", re.I)
SUSTAINED = re.compile(r"\bsustain", re.I)


def _veto(e, item):
    """Fill an Item from a veto row, which states everything in prose."""
    raw = (e.get("raw") or "").strip()
    item.action = "Override the Governor's veto"
    if OVERRIDDEN.search(raw):
        item.carried = True
    elif SUSTAINED.search(raw):
        item.carried = False
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
                 "consent", "fifths")

    def __init__(self, bill, term, e, seq):
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
        self.seq = seq
        self.need = None
        self.veto = False
        self.consent = False
        # Three fifths, whose count only the roll call's ballots give; load()
        # fills self.need from rollcalls.json where it can.
        self.fifths = False
        if e.get("type") == "veto_override":
            _veto(e, self)
            return

        # What the fields did not carry, the prose sometimes does. Read from
        # `raw` rather than `action` because the clerk puts the outcome after
        # the tally -- "RC 19Y-5N, 3/5 nec., MA" -- and `action` is cut before
        # it on some rows and not others.
        src = self.raw or self.action
        if not self.kind or self.yeas is None:
            m = INLINE_VOTE.search(src)
            if m:
                self.kind = self.kind or m.group("kind").upper()
                if self.yeas is None:
                    self.yeas, self.nays = int(m.group("y")), int(m.group("n"))
        frac = None
        th = THRESHOLD.search(src)
        if th:
            a, b = int(th.group("a")), int(th.group("b"))
            if 0 < a < b:
                frac = (a, b)
        else:
            tw = THRESHOLD_WORDS.search(src)
            if tw:
                frac = (2, 3) if tw.group("f").lower() == "thirds" else (3, 5)
        if frac == (3, 5):
            self.fifths = True
        elif frac:
            tot = (self.yeas or 0) + (self.nays or 0)
            if tot:
                # Of those voting, rounded up: two thirds of 23 is 15.33,
                # and it takes 16.
                self.need = -(-tot * frac[0] // frac[1])

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
    def outcome_words(self):
        """'The motion was adopted on a voice vote -- the bill was killed.'"""
        if self.carried is None:
            return ""
        verb = "was adopted" if self.carried else "failed"
        how = f" on a {self.kind_words}" if self.kind_words else ""
        tail = _consequence(self.action, self.carried)
        return (f"The motion {verb}{how}"
                + (f" — {tail}." if tail else "."))

    def __repr__(self):
        return f"<Item {self.bill} {self.action!r} {self.kind} p{self.page}>"


class Day:
    """One chamber, one date, and everything it did to bills that day."""

    __slots__ = ("body", "date", "items", "journal", "ordered")

    def __init__(self, body, date, items):
        self.body = body
        self.date = date
        self.items = items
        # IS THIS THE ORDER IT HAPPENED IN? Only where the journal page says
        # so. 24% of House actions cite one and 0.3% of Senate actions do, so
        # a Senate day is a LIST of what the chamber did and not a sequence,
        # and the page must say that rather than implying an order the record
        # does not hold.
        self.ordered = sum(1 for i in items if i.page is not None) > len(items) / 2
        # "HJ 4" -- the journal number this day is printed in. Taken from the
        # items rather than asserted, and only when they agree: a day whose
        # rows cite two different journals is telling us something and should
        # not be flattened into one of them.
        cites = {i.cite for i in items if i.cite}
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

    def counts(self):
        c = collections.Counter(i.kind for i in self.items if i.kind)
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
    """
    out = []
    events = events or []
    pending, suspended_on = None, None
    for n, e in enumerate(events):
        kind = e.get("type")
        raw = e.get("raw") or ""
        floor = kind in ("floor", "veto_override")
        if kind == "report" or (kind == "other" and REPORT_ROW.search(raw)
                                and ON_CONSENT.search(raw)):
            pending = e if ON_CONSENT.search(raw) else None
            suspended_on = None
        elif kind == "consent_off" or (not floor and CONSENT_OFF.search(raw)):
            pending = None
        if not floor or e.get("cancelled"):
            continue
        it = Item(bill, term, e, 0)
        out.append((e, it))
        day = (e.get("date") or "")[:10]
        if (suspended_on and day != suspended_on) or CONSENT_OFF.search(raw):
            pending = None
        if not it.veto and SUSPENDS.search(it.action or raw):
            suspended_on = suspended_on or day
            continue
        report, pending = pending, None
        it.consent = (
            on_consent_calendar(report, e, it)
            or (not it.veto and not it.mover and not CONSENT_OFF.search(raw)
                and bool(SAID_IN_ROW.search(raw)))
            or (report is None and _reported_after(events, n, e, it)))
    return out


def _fifths_from_rollcalls(path=ROLLCALLS):
    """{(body, date, yeas, nays): {threshold_needed}} for the roll calls whose
    threshold is three fifths, by the ballots' tally and by the tally the
    General Court's summary stated, since the docket line may carry either.
    A set, so that two roll calls on one day with the same count but
    different thresholds answer nothing rather than the wrong one."""
    p = Path(path)
    out = collections.defaultdict(set)
    if not p.exists():
        return out
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return out
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


def load(path=NARRATIVES, rollcalls=ROLLCALLS):
    """Every sitting day, as {(body, date): Day}.

    Ordered within a day by the journal page the action is printed on, which
    is the clerk's own ordering and the only one available -- the events carry
    no time. Rows with no page keep their relative order and sort first, so a
    missing citation never silently reorders the ones that have it.
    """
    p = Path(path)
    # SILENCE IS NOT SUCCESS. Without this the whole feature builds cleanly and
    # emits nothing, which looks exactly like a chamber that never sat.
    assert p.exists(), f"{path} is not here; run build_narratives first"
    data = json.loads(p.read_text(encoding="utf-8"))

    grouped = collections.defaultdict(list)
    seq = 0
    for term, bills in sorted(data.items()):
        for bill, rec in sorted(bills.items()):
            for e, it in floor_items(bill, term, rec.get("events")):
                body = (e.get("body") or "").strip().upper()
                date = (e.get("date") or "")[:10]
                if body not in ("H", "S") or not re.match(r"\d{4}-\d\d-\d\d$", date):
                    continue
                seq += 1
                it.seq = seq
                grouped[(body, date)].append(it)

    assert grouped, ("no floor events in narratives.json -- every sitting day "
                     "page would be empty, and the build would not say so")

    need = _fifths_from_rollcalls(rollcalls)
    for (body, date), items in grouped.items():
        for it in items:
            if it.fifths and it.counted:
                got = need.get((body, date, it.yeas, it.nays))
                if got and len(got) == 1:
                    it.need = next(iter(got))

    days = {}
    for key, items in grouped.items():
        _one_counted_vote(items)
        items.sort(key=lambda i: (i.page if i.page is not None else -1, i.seq))
        days[key] = Day(key[0], key[1], items)
    return days


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
    today = today or _date.today()
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
