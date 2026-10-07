#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.4
"""
One record per person, across every term they served.

    python3 src/parse/build_careers.py            # writes careers.json
    python3 src/parse/build_careers.py --check    # report only, writes nothing

No network. Reads db/Legislators.psv, db/RollCallHistory.psv and
db/RollCallSummary.psv (the day each roll call was taken), all on this disk.

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

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import collections
import json

import proceedings as P

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
    lc, rc, sc = C["Legislators"], C["RollCallHistory"], C["RollCallSummary"]

    # ---- the day each roll call was taken --------------------------------
    # A BALLOT CARRIES NO DATE, AND ITS SESSION YEAR IS NOT ITS TERM (7 October
    # 2026). Organization Day -- 2 December 2026 next -- is the next General
    # Court's (proceedings.vote_term), and a roll call of that day filed under
    # 2026 would have put every member of the next House in 2025-2026. The
    # roll call's own VoteDate decides, as it does everywhere else a term is
    # asked of a vote. A ballot is that vote's by (year, chamber, number), so
    # the key must name one vote: were December's numbered from 1 again under
    # 2026, (2026, H, 1) would be January's call of the roll and December's
    # first vote at once, and its ballots could not say which. That stops the
    # build, naming the keys, rather than filing them under either.
    taken, clash = {}, {}
    iy_s, ib_s, iv_s, id_s = (sc.index("SessionYear"), sc.index("LegislativeBody"),
                              sc.index("VoteSequenceNumber"), sc.index("VoteDate"))
    for f in rows("RollCallSummary", sc):
        k = (f[iy_s].strip(), f[ib_s].strip(), f[iv_s].strip())
        d = f[id_s].strip()
        if k in taken and P.vote_term(k[0], taken[k]) != P.vote_term(k[0], d):
            clash.setdefault(k, {taken[k]}).add(d)
        taken.setdefault(k, d)
    if clash:
        raise SystemExit(
            f"{len(clash)} roll call key(s) name votes of two terms, so their ballots "
            "cannot say which they are: " + "; ".join(
                f"{y} {b} {n} ({', '.join(sorted(ds))})" for (y, b, n), ds in sorted(clash.items())[:6])
            + ". Join the ballots by something that tells them apart before building careers.json.")

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
    ie, iy, ib, iv = (rc.index("EmployeeNumber"), rc.index("SessionYear"),
                      rc.index("LegislativeBody"), rc.index("VoteSequenceNumber"))
    for f in rows("RollCallHistory", rc):
        emp = f[ie].strip()
        if not emp:
            continue
        # The year of the term the vote belongs to: its session year, or the
        # next term's first where it was taken on or after Organization Day.
        year = f[iy].strip()
        t = P.vote_term(year, taken.get((year, f[ib].strip(), f[iv].strip()), ""))
        years[emp].add(int(year) if t == term_of(year) else int(t[:4]))
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
