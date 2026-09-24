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
        return sorted({i.bill for i in self.items})

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
            # A bill's events are in order, so the consent flag is simply
            # whichever committee report was seen most recently.
            on_consent = False
            for e in (rec.get("events") or []):
                if e.get("type") == "report":
                    on_consent = bool(ON_CONSENT.search(e.get("raw") or ""))
                if e.get("type") not in ("floor", "veto_override") \
                        or e.get("cancelled"):
                    continue
                body = (e.get("body") or "").strip().upper()
                date = (e.get("date") or "")[:10]
                if body not in ("H", "S") or not re.match(r"\d{4}-\d\d-\d\d$", date):
                    continue
                seq += 1
                it = Item(bill, term, e, seq)
                # A veto vote is never a consent item, whatever the bill's
                # last committee report said months earlier.
                it.consent = on_consent and not it.veto
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
        items.sort(key=lambda i: (i.page if i.page is not None else -1, i.seq))
        days[key] = Day(key[0], key[1], items)
    return days


def one(body, date, path=NARRATIVES):
    return load(path).get((body.strip().upper(), date))


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
