#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-19.1
"""
The margin of a race, defined once (the elections display design of 19 November 2026,
reports/elections2-design/proposal.md section 2, approved in full by the owner that day).
Every card, label, filter, sort, summary and download takes it from margin() here, so no
two of them can disagree.

    import election_margin as EM
    m = EM.margin(race, contest="2024-11-05.general.house.cheshire-9")
    m["label"]        # "R+1.3"
    EM.words(m)       # "R+1.3", or "R+0.7 over R" where both share a party
    EM.band(m)        # "u5", "5-10", "10-20", "20", "unopposed", or "" (no seat count)
    EM.flip(m)        # 20: the votes that would have changed the result

THE RULE. The last winner is the candidate placed at the race's seat count by votes; the
first out is the next one (for one seat, the winner and the runner-up). The points are the
two-way lead between those two, 100 x (last winner - first out) / (last winner + first
out), to one decimal, rounded half up on the exact fraction. One rule for one seat or ten.

THE LABEL is the last winner's party letters as the file prints them, in capitals, as the
candidate's chip shows them, and the points: "R+1.3", "D+23.9", "I/D+4.0". Where the last
winner and the first out share a party, `over` is that party ("R+0.7 over R"), because
"R+0.7" alone would read as a win over the other party. A primary's label has no party
letter ("+9.7"): both candidates share it.

Where two or more are tied for the first place out, the margin is the same over each; the
first out named is the first of them by name, and the race is "over" a party only where all
of them are of it.

A BAND is the points the label shows, not the unrounded fraction, so that a race labelled
"D+10.0" is never under "5 to 10": a race within a twentieth of a point below an edge is
in the band above it, where the design's own measure (unrounded) put it below.

THE STATUS (`status`):
  contested   a margin, as above; a first out who is a named write-in keeps it
  unopposed   no more candidates than seats; scattered write-ins are not opposition.
              Label "Unopposed", no number
  tie         the last winner and the first out have the same count. Label "Tied", no
              number
  no_seats    the file prints no seat count (Strafford's at-large commissioners,
              2016-2022), so there is no last seat. No margin at all

Figures only: nothing here, and no word built from it, says "close", "safe" or
"competitive". Standard library and entities.py's ids only; reads no file.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import entities as EN

STATUSES = ("contested", "unopposed", "tie", "no_seats")
# The margin buttons and their order (decision 7): a band is the points the label shows,
# so a race labelled 5.0 is in 5 to 10, never under 5. A tie, whose gap is no vote, is
# under 5; a race with no seat count is in no band but Any.
BANDS = (("u5", "Under 5 points"), ("5-10", "5 to 10"), ("10-20", "10 to 20"),
         ("20", "20 or more"), ("unopposed", "Unopposed"))


def letters(party):
    """The party as the file prints it, in capitals: "d" -> "D", "i/d" -> "I/D"."""
    return str(party or "").upper()


def tenths(gap, pair):
    """100 * gap / pair in tenths of a point, rounded half up on the exact fraction."""
    return (2000 * gap + pair) // (2 * pair)


def candidacy(contest, c):
    """A candidate's id: the results file's own where it gives one (the other offices'
    files), else entities.candidacy_id of the contest, the printed name and the party."""
    if c.get("id"):
        return c["id"]
    return EN.candidacy_id(contest, c.get("name"), c.get("party")) if contest else None


def results_contest(election, key, stage="general", party=""):
    """The contest id of a House or Senate race of collected/election_<year>.json, by its
    key ("H|Cheshire|9", "S|5"), as src/parse/build_entities.py ids the members-elect's; a
    primary's (collected/primary_<year>.json, "D|S|1") with its party in the stage's word."""
    parts = key.split("|")
    if parts[0] not in ("H", "S"):
        party, parts = party or parts[0].lower(), parts[1:]
    if parts[0] == "H":
        return EN.contest_id(election, stage, "house", f"{EN.slug(parts[1])}-{int(parts[2])}", party)
    return EN.contest_id(election, stage, "senate", str(int(parts[1])), party)


def margin(race, contest=None, primary=False):
    """The race's margin, {status, last, first_out, gap, points, label, over}: `last` and
    `first_out` the two candidacies' ids (None where there is none, or no contest to id
    them by), `gap` the votes between them, `points` the two-way lead to one decimal,
    `label` the words of the rule above (None for no_seats), `over` the shared party of
    a contested race whose two share one, else None. `race` is a results file's race
    ({"seats", "candidates": [{"name", "party", "votes", "write_in", "id"?}]}); a primary
    (`primary`) is labelled without a party letter."""
    seats = race.get("seats")
    out = {"status": None, "last": None, "first_out": None, "gap": None, "points": None,
           "label": None, "over": None}
    if not isinstance(seats, int) or isinstance(seats, bool) or seats < 1:
        out["status"] = "no_seats"
        return out
    cands = sorted(race.get("candidates") or [], key=lambda c: (-c["votes"], c.get("name") or ""))
    if len(cands) <= seats:
        out["status"], out["label"] = "unopposed", "Unopposed"
        if cands:
            out["last"] = candidacy(contest, cands[-1])
        return out
    a, b = cands[seats - 1], cands[seats]
    out["last"], out["first_out"] = candidacy(contest, a), candidacy(contest, b)
    out["gap"] = a["votes"] - b["votes"]
    if out["gap"] == 0:
        out["status"], out["label"] = "tie", "Tied"
        return out
    t = tenths(out["gap"], a["votes"] + b["votes"])
    out["status"], out["points"] = "contested", t / 10
    out["label"] = ("" if primary else letters(a.get("party"))) + f"+{t // 10}.{t % 10}"
    # Two or more tied for the first place out are each the first out: the margin is the
    # same over each, and it is "over" a party only where every one of them is of it
    # (2016 Hillsborough 34: a Republican and a Democrat tied at 1,542).
    outs = {letters(c.get("party")) for c in cands[seats:] if c["votes"] == b["votes"]}
    if not primary and letters(a.get("party")) and outs == {letters(a.get("party"))}:
        out["over"] = letters(a.get("party"))
    return out


def words(m):
    """The label as a page prints it: "R+0.7 over R" where the two share a party."""
    if not m or not m.get("label"):
        return ""
    return m["label"] + (f" over {m['over']}" if m.get("over") else "")


def band(m):
    """The margin button a race is under (BANDS), or "" for a race with no seat count."""
    s = (m or {}).get("status")
    if s == "unopposed":
        return "unopposed"
    if s == "tie":
        return "u5"
    if s != "contested":
        return ""
    p = m["points"]
    return "u5" if p < 5 else "5-10" if p < 10 else "10-20" if p < 20 else "20"


def flip(m):
    """The votes that would have changed the result (the owner's rule of 11 November
    2026): a vote moved from the last winner to the first out closes the gap by two, so
    floor(gap / 2) + 1. None where there is no margin, and for a tie, which is a tie."""
    if (m or {}).get("status") != "contested":
        return None
    return m["gap"] // 2 + 1


def order_key(m):
    """Smallest margin first: a tie, then the contested by points and then by votes,
    then the unopposed, then a race with no seat count."""
    s = (m or {}).get("status")
    if s == "tie":
        return (0, 0, 0)
    if s == "contested":
        return (1, m["points"], m["gap"])
    return (2 if s == "unopposed" else 3, 0, 0)
