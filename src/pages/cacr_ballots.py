#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
A constitutional amendment's ballot: the election its own text names
(ELECTION_IN_TEXT, election_day), the voters' answer where the docket records
none (corrections/ballot_results.json, read by load_ballots and worked out
against two thirds by ratified), the voters' line of How it got here
(ballot_step, docket_count_differs), the card its Votes tab draws
(ballot_card), and what a CACR both chambers passed now says
(cacr_to_the_voters).

    import cacr_ballots as CB
    CB.load_ballots(CB.BALLOTS, bills)      # {(term, bill): row}
    CB.cacr_to_the_voters(narr, term, current, text, ballot=row)

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md section 5). It moved here as it stood,
comments and all, nothing inside it edited: from
ELECTION_IN_TEXT's comment to cacr_to_the_voters, one block. The docket's
referendum line (REFERENDUM) is parts.py's, whose count it is
ballot_source.py's, and the journey's marks journey.py's. It imports no builder (_import_cycles_cut). build_site_v2 imports every
name here back under its own, so build_site_v2.<name> answers as it did, for
build_bills, main and the checks.
"""

import json
import re
from datetime import date as _date, timedelta as _td
from pathlib import Path

import ballot_source as BS
import build_date
from journey import J_MARK, J_REF_TALLY
from parts import REFERENDUM


# Its own text names the election: "submitted to the qualified voters of the
# state at the state general election to be held in November, 2026".
ELECTION_IN_TEXT = re.compile(r"general election to be held in (?P<month>[A-Z][a-z]+),?\s*(?P<year>\d{4})")
TO_THE_VOTERS = "Passed both chambers, goes to the voters"


def election_day(year):
    """The state general election: the Tuesday after the first Monday in
    November."""
    d = _date(int(year), 11, 2)
    while d.weekday() != 1:
        d += _td(days=1)
    return d


# THE VOTERS' ANSWER WHERE THE DOCKET RECORDS NONE (the person, 5 October
# 2026). The docket stops at the second chamber's vote for the eight CACRs
# sent to the voters since 2006, and they read "went to the voters" with no
# answer. ballot_results.json holds the statewide vote on each of the
# eighteen, read off the source its rows name: a person's file, which no
# build_ or fetch_ script writes (preflight's HANDMADE).
#
# WHOSE COUNT IT IS IS THE ROW'S OWN SOURCE (ballot_source.py). Since 7
# October 2026 that is the Secretary of State for every amendment the voters
# have decided -- its results from 2016, its Manual for the General Court
# before -- with Ballotpedia's figures kept on each row as the cross-check,
# and Ballotpedia for the one still to come. The card, How it got here and
# the note where the docket's own count differs all name it from the row,
# never in words of their own: they said "Ballotpedia" whatever the row said.
#
# THE OUTCOME IS WORKED OUT HERE, NOT READ. An amendment needs two thirds of
# the votes cast on it (Part II, Article 100), and a majority is not that:
# CACR 6 of 2024, the judicial retirement age, won 452,307 to 237,221 --
# 65.6% -- and was not ratified. In whole numbers, so that exactly two
# thirds is two thirds.
BALLOTS = "corrections/ballot_results.json"
RATIFIED = "Passed both chambers, ratified by the voters"
NOT_RATIFIED = "Passed both chambers, not ratified by the voters"
ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def ratified(yes, no):
    """Whether the voters ratified an amendment: two thirds of the votes
    cast on it."""
    return yes + no > 0 and 3 * yes >= 2 * (yes + no)


def load_ballots(path, bills):
    """{(term, bill): row} out of ballot_results.json, or {} where it is
    not here.

    Refused where a row names a bill the record does not hold, or one that
    is not a CACR, or one twice; where its day is not a day; or where its
    figures are not two whole numbers, or two nulls for an election still to
    come. A row that matches nothing attaches nothing, and the build would
    exit zero having done it (check_notes)."""
    p = Path(path)
    if not p.exists():
        print(f"  the voters' votes: {path} is not here, so no CACR shows one")
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise SystemExit(f"{path} has no list of rows")
    out, bad = {}, []
    for r in rows:
        key = (r.get("term"), r.get("bill"))
        y, n = r.get("yes"), r.get("no")
        if key[1] not in (bills.get(key[0]) or {}):
            bad.append(f"{key[0]} {key[1]} is not in the record")
        elif not str(key[1]).startswith("CACR"):
            bad.append(f"{key[0]} {key[1]} is not a CACR")
        elif key in out:
            bad.append(f"{key[0]} {key[1]} is named twice")
        elif not (ISO_DAY.match(r.get("election") or "") and ISO_DAY.match(r.get("read") or "")):
            bad.append(f"{key[0]} {key[1]}'s election or read is not a day")
        elif not (y is None and n is None) and not (
                all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in (y, n))
                and y + n > 0):
            bad.append(f"{key[0]} {key[1]}'s yes and no are not two counts")
        elif not str(r.get("source") or "").startswith("https://") or not r.get("label"):
            bad.append(f"{key[0]} {key[1]} names no source or no label")
        else:
            out[key] = r
    if bad:
        raise SystemExit(f"{path}: " + "; ".join(bad))
    done = sum(1 for r in out.values() if r.get("yes") is not None)
    print(f"  the voters' votes: {done} {'amendment' if done == 1 else 'amendments'} "
          f"decided at the polls, {len(out) - done} still to go to them ({path})")
    return out


# What status_source says of a CACR whose voters' answer is a ballot row's
# figures against two thirds: the file the answer came from, which names its
# source on every row.
BALLOT_SOURCE = "ballot_results.json"


def ballot_step(row):
    """The voters' line of a CACR's journey, from its ballot row: the day of
    the election and its outcome, in the words a docket referendum line
    gets -- and whose count it is, by the row's source: "(the Secretary of
    State's count)". How it got here is the docket's list, and this line is
    not the docket's: it stops at the second chamber for every CACR this
    line is drawn for (the review of 5 October 2026)."""
    yes = ratified(row["yes"], row["no"])
    act = "ratified" if yes else "not_ratified"
    return {"date": row["election"], "body": "V", "act": act, "mark": J_MARK[act],
            "text": ("Ratified" if yes else "Not ratified")
            + f", {row['yes']:,}–{row['no']:,} ({BS.whose(row)} count)",
            "short": "ratified" if yes else "not ratified"}


def docket_count_differs(row):
    """What the voters' line of How it got here adds where it is the docket's
    referendum line and the docket's count is not the row's: whose the
    docket's is, and whose the other is, by the row's source. CACR 22 of 1998
    reads "Not ratified, 119,104–159,439 (the docket's count; the Secretary
    of State's is 119,104–169,439)": the docket says 159,439, and the Manual
    it cites prints 169,439."""
    return f" (the docket's count; {BS.whose(row)} is {row['yes']:,}–{row['no']:,})"


def ballot_card(row, narr, today=None):
    """What a CACR's Votes tab draws for the voters: the election, how the
    source lists it, the two counts and the outcome, or only the day where
    the election is still to come. Where the docket prints a referendum
    tally of its own and it is not the source's -- CACR 22 of 1998 reads
    "159,439" against the Secretary of State's 169,439 -- the docket's pair
    goes with it, so the card can say so rather than show one figure and
    print the other a tab away. (CACR 7 of 1992 did too, until 7 October
    2026: its 204,475 was the docket's and the Secretary of State's, and the
    file's 204,457 was Ballotpedia's.)

    WHOSE IT IS, FROM THE ROW (ballot_source.py): `by` begins the card's
    citation, before the row's `cite` -- "Secretary of State, Manual for the
    General Court 1993, p. 442 (NHPR's scan)" -- and `whose` says whose the
    counts above a differing docket's are. app.js named Ballotpedia on every
    card whatever the row's source was.

    AN ELECTION PAST WITH NO COUNT IN THE FILE is `over` as well as pending:
    the status turns to "went to the voters" the day after by itself
    (cacr_to_the_voters), and the card said "The vote is on 3 November" until
    a person typed the counts in (the review of 5 October 2026). `today` is
    the build's day (build_date), as it is there."""
    card = {"date": row["election"], "label": row["label"],
            "source": row["source"], "read": row["read"],
            "by": BS.by(row), "whose": BS.whose(row),
            **({"cite": row["cite"]} if row.get("cite") else {})}
    if row.get("yes") is None:
        over = (today or build_date.today()) > _date.fromisoformat(row["election"])
        return {**card, "pending": True, **({"over": True} if over else {})}
    card.update(yes=row["yes"], no=row["no"], ratified=ratified(row["yes"], row["no"]))
    for e in reversed([e for e in (narr or {}).get("events", []) if not e.get("cancelled")]):
        raw = e.get("raw") or ""
        m = REFERENDUM.search(raw)
        if not m:
            continue
        t = J_REF_TALLY.search(raw, m.end() - 1)
        if t:
            said = [int(t.group(1).replace(",", "")), int(t.group(2).replace(",", ""))]
            if said != [row["yes"], row["no"]]:
                card["docket"] = said
        break
    return card


def cacr_to_the_voters(narr, term, current, text="", today=None, ballot=None):
    """What a CACR both chambers passed now says, in the tense the record
    allows: the voters' answer where the docket records it, or where
    ballot_results.json does (`ballot`, its row); past tense for a closed
    term; for the current term, the election its own text names, in the
    future tense until that day."""
    for e in reversed([e for e in (narr or {}).get("events", []) if not e.get("cancelled")]):
        m = REFERENDUM.search(e.get("raw") or "")
        if m:
            return (RATIFIED if m.group("how").lower() == "adopted" else NOT_RATIFIED)
    if ballot and ballot.get("yes") is not None:
        return RATIFIED if ratified(ballot["yes"], ballot["no"]) else NOT_RATIFIED
    m = ELECTION_IN_TEXT.search(text or "")
    if term != current:
        return "Passed both chambers, went to the voters"
    if not m:
        return TO_THE_VOTERS
    when = f"{m.group('month')} {m.group('year')}"
    over = (today or build_date.today()) > election_day(m.group("year"))
    return (f"Passed both chambers, went to the voters in {when}" if over
            else f"Passed both chambers, goes to the voters in {when}")
