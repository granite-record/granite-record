#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.1
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


class Item:
    """One thing the chamber did to one bill, at one point in the day."""

    __slots__ = ("bill", "term", "action", "mover", "carried", "kind",
                 "yeas", "nays", "cite", "page", "raw", "seq")

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

    __slots__ = ("body", "date", "items", "journal")

    def __init__(self, body, date, items):
        self.body = body
        self.date = date
        self.items = items
        # "HJ 4" -- the journal number this day is printed in. Taken from the
        # items rather than asserted, and only when they agree: a day whose
        # rows cite two different journals is telling us something and should
        # not be flattened into one of them.
        cites = {i.cite for i in items if i.cite}
        self.journal = cites.pop() if len(cites) == 1 else ""

    @property
    def bills(self):
        return sorted({i.bill for i in self.items})

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


def load(path=NARRATIVES):
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
            for e in (rec.get("events") or []):
                if e.get("type") != "floor" or e.get("cancelled"):
                    continue
                body = (e.get("body") or "").strip().upper()
                date = (e.get("date") or "")[:10]
                if body not in ("H", "S") or not re.match(r"\d{4}-\d\d-\d\d$", date):
                    continue
                seq += 1
                grouped[(body, date)].append(Item(bill, term, e, seq))

    assert grouped, ("no floor events in narratives.json -- every sitting day "
                     "page would be empty, and the build would not say so")

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
