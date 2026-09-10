#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-10.1
"""The 2,614 people the General Court's own list names, past and present.

    python3 past_members.py            # what it holds, and what it would name

WHY THIS EXISTS

Twenty-four session years of roll calls came off the database dump on 10
September -- 8,061 votes, 1.86 million ballots, 1999 to 2022, no requests.
Every ballot resolved to a member id and 784,310 of them resolved to nothing
else: `Member #330274`, cast by somebody the site could not name. The roster
views reach 1,081 people and `former_members.json` 676, and the archive needs
more than both.

byAnyMember.aspx offers a single list of **2,614 past and present
legislators**, and it is keyed by the same Employeeno the roll call history
uses. Measured against the ballots that had no name: **1,034 of the 1,137
unnamed members are in it, and 733,474 of the 784,310 nameless ballots -- 93%
-- gain a real name.** One request, already spent.

WHAT IT DOES NOT GIVE

A party. The label carries the chamber, the surname, the forename and the
district and nothing else, so a member named only from here votes without a
party letter beside them. That is a gap to state on the page rather than to
fill by inference: guessing a 1999 representative's party from a later
namesake, or from how they voted, would be inventing the one fact a reader is
most likely to act on.

WHERE THE FILE COMES FROM

`fetch_sponsors_by_member.py --members` writes it, one request. It is
generated, and gitignored the way `former_members.json` is.
"""

import json
import re
import sys
from pathlib import Path

SRC = Path("past_members.json")

# "Rep. Vartanian, Elsie(Rock. 20)" and "Sen. Blaisdell, Clesson(Dist. 10)".
# The district is the LAST parenthesis, not the first: "Battles(-Peirce),
# Marjorie(Rock. 18)" carries one inside the surname, and a non-greedy match
# would call that person's district "-Peirce".
LABEL = re.compile(r"^(?P<title>Rep\.|Sen\.)\s*(?P<name>.*)\((?P<where>[^()]*)\)\s*$")
SENATE = re.compile(r"^Dist\.?\s*(?P<num>\d+)$", re.I)
HOUSE = re.compile(r"^(?P<county>[A-Za-z.\- ]+?)\.?\s*(?P<num>\d+)$")


def parse(label):
    """One option's text as {name, chamber, county, district}, or {}."""
    m = LABEL.match((label or "").strip())
    if not m:
        return {}
    where = m.group("where").strip()
    county, num = "", ""
    s = SENATE.match(where)
    if s:
        num = s.group("num")
    else:
        h = HOUSE.match(where)
        if h:
            county, num = h.group("county").strip(" ."), h.group("num")
        else:
            county = where
    return {
        "name": m.group("name").strip(" ,"),
        "chamber": "S" if m.group("title") == "Sen." else "H",
        "county": county,
        # Stored as written -- "01" stays "01" -- because former_members.json
        # writes it that way and the two are read side by side.
        "district": num,
        # No party. See the docstring: this list does not carry one, and
        # inferring it would invent the fact a reader most relies on.
        "party": "",
    }


def roster(path=SRC):
    """{Employeeno: {name, chamber, county, district, party}}.

    Empty when the file is absent, so nothing that reads this fails for want
    of a fetch that has not happened.
    """
    p = Path(path)
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    pairs = raw.items() if isinstance(raw, dict) else raw
    out = {}
    for mid, label in pairs:
        got = parse(label)
        if got.get("name"):
            out[str(mid)] = got
    return out


def main():
    people = roster()
    if not people:
        sys.exit(f"No {SRC}. fetch_sponsors_by_member.py --members writes it, "
                 "in one request.")
    print(f"{len(people):,} legislators named, past and present")
    house = sum(1 for v in people.values() if v["chamber"] == "H")
    print(f"  {house:,} House, {len(people) - house:,} Senate")
    print(f"  {sum(1 for v in people.values() if v['district']):,} carry a district")
    mv = Path("data/member_votes.json")
    if not mv.exists():
        return 0
    votes = json.loads(mv.read_text(encoding="utf-8"))
    nameless = [r for r in votes if str(r.get("name", "")).startswith("Member #")]
    would = [r for r in nameless if str(r.get("member_id")) in people]
    print()
    print(f"{len(nameless):,} ballots are cast by somebody unnamed; "
          f"{len(would):,} of them ({100 * len(would) // max(len(nameless), 1)}%) "
          "are named here")
    return 0


if __name__ == "__main__":
    sys.exit(main())
