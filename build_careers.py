#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.1
"""
One record per person, across every term they served.

    python3 build_careers.py            # writes careers.json
    python3 build_careers.py --check    # report only, writes nothing

No network. Reads db/Legislators.psv and db/RollCallHistory.psv, both already
on this disk.

WHY A PERSON IS NOT AN EMPLOYEE NUMBER

The roll call record keys every ballot to an EmployeeNumber, and it is stable
-- no number in the roster carries two names. But a PERSON can carry two
numbers: 21 of the 1,079 in the roster do. Reading the pairs shows why, and it
is not what you would guess:

    Cindy Rosenwald    376622  2005-2018 (House)   209106  2019-2026 (Senate)
    Daryl Abbas        408908  2019-2022 (House)   218760  2023-2026 (Senate)

Almost every one is a member moving from the House to the Senate. The General
Court issues a new number and the old one stops. Treated as two people, a
member's record breaks in half at the moment they were promoted, which is
exactly the point somebody looking them up cares about.

HOW TWO NUMBERS ARE JUDGED TO BE ONE PERSON

Same first and last name, and service periods that DO NOT OVERLAP. Nobody
holds two seats at once, so an overlap is proof of two people rather than
evidence of one. Both of the two overlapping pairs in the roster are exactly
that, and both are corroborated by a different county:

    David Pierce   209092 2013-2016 (Grafton)  377256 2015-2018 (Sullivan)
    John O'Connor  376993 2011-2020 (Rock.)    408726 2017-2018 (Straf.)

They stay separate. The rule is deliberately narrow: a shared name alone
merges nothing.

WHAT THIS CANNOT DO, AND SAYS SO

The database's Legislators view names nobody whose service ended before 2015.
Of the 2,211 people who have cast a recorded vote since 1999, 1,075 are named
there and 1,136 are not -- and an unnamed number cannot be matched to another
unnamed number, because the rule is a name. Those stay one-number people and
are marked unnamed rather than merged on a guess.

AND NO DISTRICT IS CARRIED BACKWARDS. The roster holds one district per
number: the last one. New Hampshire redistricts every ten years, so a member's
2005 district is very often not their 2015 one, and printing today's beside an
old vote states something the record does not. A term gets a district here
only where the source gives one FOR THAT TERM, which today means none of them.
"""

import argparse
import collections
import json
from pathlib import Path

DB = Path("db")
OUT = Path("careers.json")


def columns():
    return json.loads((DB / "_columns.json").read_text(encoding="utf-8"))


def rows(name, cols):
    n = len(cols)
    with (DB / f"{name}.psv").open(encoding="utf-8") as fh:
        for line in fh:
            f = line.rstrip("\n").split("|")
            if len(f) >= n:
                yield f


def term_of(year):
    y = int(year)
    return f"{y if y % 2 else y - 1}-{y + 1 if y % 2 else y}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report and write nothing")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    C = columns()
    lc, rc = C["Legislators"], C["RollCallHistory"]

    # ---- who each number is, where the roster knows ----------------------
    who = {}
    for f in rows("Legislators", lc):
        emp = f[lc.index("Employeeno")].strip()
        if not emp:
            continue
        who[emp] = {
            "first": f[lc.index("FirstName")].strip(),
            "last": f[lc.index("LastName")].strip(),
            "party": f[lc.index("party")].strip(),
            "chamber": f[lc.index("LegislativeBody")].strip(),
            "county_code": f[lc.index("countycode")].strip(),
            "person_id": f[lc.index("PersonID")].strip(),
        }

    # ---- what each number did, from the ballots --------------------------
    years = collections.defaultdict(set)
    votes = collections.Counter()
    chambers = collections.defaultdict(set)
    ie, iy, ib = (rc.index("EmployeeNumber"), rc.index("SessionYear"),
                  rc.index("LegislativeBody"))
    for f in rows("RollCallHistory", rc):
        emp = f[ie].strip()
        if not emp:
            continue
        years[emp].add(int(f[iy]))
        votes[emp] += 1
        b = f[ib].strip()
        if b:
            chambers[emp].add(b)

    # ---- group numbers into people ---------------------------------------
    by_name = collections.defaultdict(list)
    for emp in years:
        rec = who.get(emp)
        if rec and rec["last"]:
            by_name[(rec["first"].lower(), rec["last"].lower())].append(emp)

    groups, merged, refused = [], 0, []
    taken = set()
    for name, emps in sorted(by_name.items()):
        if len(emps) == 1:
            groups.append(emps)
            taken.update(emps)
            continue
        # Nobody holds two seats at once, so an overlap is two people.
        emps = sorted(emps, key=lambda e: min(years[e]))
        buckets = []
        for e in emps:
            for b in buckets:
                if not any(years[e] & years[x] for x in b):
                    b.append(e)
                    break
            else:
                buckets.append([e])
        for b in buckets:
            groups.append(b)
            taken.update(b)
            if len(b) > 1:
                merged += len(b) - 1
        if len(buckets) > 1:
            refused.append((name, [sorted(b) for b in buckets]))

    for emp in years:
        if emp not in taken:
            groups.append([emp])

    # ---- one record per person -------------------------------------------
    out = {}
    for emps in groups:
        emps = sorted(emps, key=lambda e: max(years[e]), reverse=True)
        lead = who.get(emps[0]) or {}
        allyears = sorted({y for e in emps for y in years[e]})
        terms = sorted({term_of(y) for y in allyears})
        per_term = {}
        for e in emps:
            for y in sorted(years[e]):
                t = term_of(y)
                per_term.setdefault(t, {"chambers": set(), "employee_nos": set()})
                per_term[t]["chambers"] |= chambers.get(e, set())
                per_term[t]["employee_nos"].add(e)
        gaps = [terms[i] for i in range(len(terms) - 1)
                if int(terms[i + 1][:4]) - int(terms[i][:4]) > 2]
        key = emps[0]
        out[key] = {
            "employee_nos": sorted(emps),
            "named": bool(lead.get("last")),
            "first": lead.get("first", ""),
            "last": lead.get("last", ""),
            "party": lead.get("party", ""),
            "chamber_last": lead.get("chamber", ""),
            "person_id": lead.get("person_id", ""),
            "terms": terms,
            "first_term": terms[0] if terms else "",
            "last_term": terms[-1] if terms else "",
            "returned_after_a_gap": bool(gaps),
            "votes": sum(votes[e] for e in emps),
            "by_term": {t: {"chambers": sorted(v["chambers"]),
                            "employee_nos": sorted(v["employee_nos"])}
                        for t, v in sorted(per_term.items())},
            # No district: the roster holds only the last one, and New
            # Hampshire redistricts every ten years.
            "district_by_term": {},
        }

    named = sum(1 for v in out.values() if v["named"])
    multi = sum(1 for v in out.values() if len(v["employee_nos"]) > 1)
    ret = sum(1 for v in out.values() if v["returned_after_a_gap"])
    both = sum(1 for v in out.values()
               if len({c for x in v["by_term"].values() for c in x["chambers"]}) > 1)
    print(f"{len(years):,} employee numbers -> {len(out):,} people "
          f"({merged:,} numbers merged into an existing person)")
    print(f"  {named:,} named by the roster, {len(out) - named:,} not "
          "(their service ended before 2015)")
    print(f"  {multi:,} people hold more than one number")
    print(f"  {both:,} served in both chambers")
    print(f"  {ret:,} left and came back after a gap")
    if refused:
        print(f"  {len(refused)} shared name(s) kept apart because their "
              "service overlaps:")
        for nm, bs in refused[:4]:
            print(f"     {nm[0].title()} {nm[1].title()}: {bs}")

    # Silence is not success.
    if not out:
        raise SystemExit("No careers were built. Check db/ is populated.")
    if a.check:
        print("\n  --check: nothing written.")
        return 0
    Path(a.out).write_text(json.dumps(out, indent=1, sort_keys=True),
                           encoding="utf-8")
    print(f"\n-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
