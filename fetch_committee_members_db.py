#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-07.2
"""
Who sits on each committee, from the General Court's own database.

    python3 fetch_committee_members_db.py --dry-run
    python3 fetch_committee_members_db.py

WHY NOT THE WEB PAGES

fetch_committees.py reads the committee pages and gets the chair, the vice
chair, the aide, the room and the phone -- which is the only place this project
has found who chairs what. But it comes back with the Senate's rosters and NOT
the House's: 74 member seats for 14 Senate committees, and 0 for 27 House ones,
because the two chambers publish their pages differently.

CommitteeMembers holds both: 810 seats across 55 committees, 625 of them held
by a member who is still sitting. Joined to Legislators it gives a name, a
party, a district and the roster PersonID that every other part of this site
keys a member on -- which the web pages do not, so a name parsed off a page has
to be matched back by spelling.

So: the roster comes from here, the leadership and the room come from
fetch_committees.py, and build_committees.py puts them together.

WHAT ActiveMember MEANS, AND THE THING THIS FILE USED TO SAY ABOUT IT

This paragraph read "Every row in the table has ActiveMember = 0. Filtering on
1 returns nothing at all, which is how this script first came back empty."
That is false, and it was load-bearing: believing it, the SELECT below never
asked for the column, and the one signal that retires a seat was thrown away
before anything downstream could use it. Counted on the dump in db/ --
`awk -F'|' '{print $4}' db/CommitteeMembers.psv | sort | uniq -c` -- 509 rows
carry 1 and 305 carry 0. Why the first attempt came back empty is not known
and is not worth guessing at; the claim about the data is simply wrong.

It cost a wrong roster on a live page. House Legislative Administration
published 13 members where the committee has 12: Joe Barton's row is
`H12|72|409206|0`, the only 0 among that committee's thirteen and his only row
in the whole 814-row table.

So ActiveMember is selected now, and travels as seat_active. Both flags are
kept, and they answer different questions: Legislators.Active says the PERSON
is still in the building, ActiveMember says the SEAT is still theirs. A
committee's past membership is part of the record and an archived term needs
it, which is why nothing is filtered out here -- the decision belongs to
build_committees, which has the roster to weigh it against.

THIS IS NOT THE WEB SERVER. It is the SQL host the General Court publishes
credentials for at gc.nh.gov/downloads, and every statement is a SELECT.
"""

import argparse
import collections
import json
import sys
from pathlib import Path

import probe_db
import refusal

SQL = """
SELECT cm.CommitteeCode AS code,
       CAST(cm.SequenceNumber AS varchar(6)) AS seq,
       CAST(cm.ActiveMember AS varchar(4)) AS seat,
       CAST(l.PersonID AS varchar(12)) AS pid,
       ISNULL(l.LastName,'') AS last,
       ISNULL(l.FirstName,'') AS first,
       ISNULL(l.party,'') AS party,
       ISNULL(CAST(l.District AS varchar(8)),'') AS district,
       ISNULL(l.countycode,'') AS cc,
       ISNULL(l.LegislativeBody,'') AS body,
       CAST(l.Active AS varchar(4)) AS act
FROM CommitteeMembers cm
JOIN Legislators l ON l.Employeeno = cm.EmployeeNumber
ORDER BY cm.CommitteeCode, cm.SequenceNumber
"""

PARTY = {"D": "Democrat", "R": "Republican", "I": "Independent",
         "L": "Libertarian"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/committee_members.json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    # The database host, not the web server, so no refusal check -- but once the
    # laptop has stood down, GitHub's weekly job owns this file.
    refusal.stand_down("The committee roster fetch", "GitHub's weekly job takes "
                       "data/committee_members.json on Sunday nights now.")

    cs = (f"Server={probe_db.HOST};Database={probe_db.DATABASE};"
          f"User ID={probe_db.USER};Password={probe_db.PASSWORD};"
          "Encrypt=False;TrustServerCertificate=True;Connect Timeout=25")
    print("SELECT only: who sits on each committee")
    res, err = probe_db.run(cs, [("cm", SQL)])
    if err:
        sys.exit(f"  the database refused: {err}")
    if res[0].get("error"):
        sys.exit(f"  {str(res[0]['error'])[:200]}")
    rows = res[0].get("rows") or []
    rows = [rows] if isinstance(rows, dict) else rows
    if not rows:
        sys.exit("  nothing came back. CommitteeMembers joined 810 seats to "
                 "Legislators on 7 September. Note that ActiveMember is 0 on "
                 "every row, so filtering on 1 returns none.")

    out = collections.defaultdict(list)
    for r in rows:
        code = str(r.get("code") or "").strip()
        pid = str(r.get("pid") or "").strip()
        if not code or not pid:
            continue
        last, first = str(r.get("last") or ""), str(r.get("first") or "")
        p = str(r.get("party") or "").strip().upper()[:1]
        try:
            seq = int(str(r.get("seq") or 0) or 0)
        except ValueError:
            seq = 0
        out[code].append({
            "id": pid,
            "name": f"{last.strip()}, {first.strip()}".strip(", "),
            "party": PARTY.get(p, p),
            "party_code": p,
            "district": str(r.get("district") or "").strip(),
            "county_code": str(r.get("cc") or "").strip(),
            "chamber": str(r.get("body") or "").strip(),
            "sequence": seq,
            # Whether the PERSON still sits. Not the same question as the
            # next line, and the difference is a published wrong roster: a
            # member can be sitting and off the committee.
            "sitting": str(r.get("act") or "") == "1",
            # Whether the SEAT is still theirs -- CommitteeMembers.ActiveMember,
            # 509 rows at 1 and 305 at 0 in the dump on disk.
            "seat_active": str(r.get("seat") or "") == "1",
        })
    for code in out:
        out[code].sort(key=lambda m: (m["sequence"], m["name"]))

    seats = sum(len(v) for v in out.values())
    sitting = sum(1 for v in out.values() for m in v if m["sitting"])
    ch = collections.Counter(m["chamber"] for v in out.values() for m in v)
    print(f"  {seats:,} seats across {len(out)} committees; {sitting:,} held "
          "by a member who still sits")
    print("  by chamber: " + ", ".join(f"{k or '?'}: {v:,}"
                                       for k, v in sorted(ch.items())))

    if a.dry_run:
        k = next(iter(out))
        print(f"\n--dry-run: nothing written to {a.out}")
        print(f"    {k}: " + ", ".join(m["name"] for m in out[k][:5]))
        return 0

    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Rebuilt whole from one query, so there is no other term's rows to keep.
    # If that ever changes -- a past term's membership from another source --
    # this needs the merge every other writer here has.
    p.write_text(json.dumps(dict(sorted(out.items())), indent=1),
                 encoding="utf-8")
    print(f"  -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
