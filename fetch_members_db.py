#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-07.1
"""
Members who have left, from the General Court's own database.

    python3 fetch_members_db.py --dry-run
    python3 fetch_members_db.py

WHY THIS EXISTS

data/legislators.json is the SITTING roster: 406 people. A roll call from an
earlier term names whoever voted in it, and many of them have since left, so
the site could not say what party they were. In the 2023-2024 term that is
63,065 of 199,385 member votes -- 32% -- across 139 people, every one of them
showing no party at all.

former_members.json was the answer and had 14 entries in it, resolved one at a
time by resolve_members.py reading member pages off gc.nh.gov. The database
holds 675 inactive legislators, 671 of them with a party, in one SELECT.

WHAT IT DOES NOT DO

It does not mark anyone as former, and nothing downstream should. A member who
has left is named and shown exactly like a sitting one -- some of them died in
office and are known personally to people reading this. The only difference the
site draws is that somebody who has left has no page of their own, because a
page says "this is who represents you" in the present tense.

So this fills in a name, a party, a county and a district. It adds no flag.

WHAT IT WRITES

former_members.json, in the shape it already has:

    {"11166": {"name": "Germana, Dylan", "party": "Democrat",
               "county": "Cheshire", "district": "1"}}

Merged, never replaced. resolve_members.py resolved some of these from member
pages and may know one this does not.

THIS IS NOT THE WEB SERVER. It is the SQL host the General Court publishes
credentials for, at gc.nh.gov/downloads. Nothing here touches gc.nh.gov, and
every statement is a SELECT.
"""

import argparse
import json
import sys
from pathlib import Path

import probe_db

# Inactive only. The sitting roster comes from legislators.txt and is richer;
# this is for the people that file no longer carries.
SQL = """
SELECT CAST(PersonID AS varchar(12)) AS pid,
       ISNULL(LastName,'') AS last,
       ISNULL(FirstName,'') AS first,
       ISNULL(party,'') AS party,
       ISNULL(countycode,'') AS ccode,
       ISNULL(CAST(District AS varchar(8)),'') AS district,
       ISNULL(LegislativeBody,'') AS body
FROM legislators
WHERE Active = 0 AND PersonID IS NOT NULL
ORDER BY PersonID
"""

PARTY = {"D": "Democrat", "R": "Republican", "I": "Independent",
         "L": "Libertarian"}


def counties(path="Counties.txt"):
    """{'06': 'Hillsborough'} from the General Court's own code table."""
    out = {}
    p = Path(path)
    if not p.exists():
        return out
    for line in p.open(encoding="utf-8-sig", errors="replace"):
        f = line.rstrip("\n").split("|")
        if len(f) >= 2 and f[0].strip():
            out[f[0].strip()] = f[1].strip()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="former_members.json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    base = (f"Database={probe_db.DATABASE};User ID={probe_db.USER};"
            f"Password={probe_db.PASSWORD};Encrypt=False;"
            "TrustServerCertificate=True;Connect Timeout=20")
    cs = f"Server={probe_db.HOST};{base}"

    print("SELECT only: legislators who no longer sit")
    res, err = probe_db.run(cs, [("members", SQL)])
    if err:
        sys.exit(f"  the database refused: {err}")
    if res[0].get("error"):
        sys.exit(f"  {res[0]['error'][:200]}")
    rows = res[0].get("rows") or []
    rows = [rows] if isinstance(rows, dict) else rows
    if not rows:
        sys.exit("  nothing came back. legislators held 675 inactive rows "
                 "on 7 September.")

    cty = counties()
    got = {}
    for r in rows:
        # Named in the SQL. The bridge hands columns back in a dict keyed on
        # the column name, and an unnamed expression gets a generated one.
        pid = str(r.get("pid") or "").strip()
        last, first = str(r.get("last") or ""), str(r.get("first") or "")
        party = str(r.get("party") or "")
        ccode, district = str(r.get("ccode") or ""), str(r.get("district") or "")
        if not pid:
            continue
        name = f"{last.strip()}, {first.strip()}".strip(", ")
        rec = {"name": name}
        if party.strip():
            rec["party"] = PARTY.get(party.strip().upper(), party.strip())
        if cty.get(ccode.strip()):
            rec["county"] = cty[ccode.strip()]
        if district.strip():
            rec["district"] = district.strip()
        got[pid] = rec

    print(f"  {len(got):,} members who have left, "
          f"{sum(1 for v in got.values() if v.get('party')):,} with a party")

    p = Path(a.out)
    prior = {}
    if p.exists():
        try:
            prior = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            prior = {}
    # Merged, never replaced: resolve_members.py read some of these off member
    # pages and may hold one the database does not.
    merged = dict(got)
    kept = 0
    for k, v in prior.items():
        if k not in merged:
            merged[k] = v
            kept += 1
        else:
            for field, val in v.items():
                if val and not merged[k].get(field):
                    merged[k][field] = val
    print(f"  {len(prior):,} already on file, {kept:,} of them the database "
          "does not have")

    if a.dry_run:
        print(f"\n--dry-run: nothing written to {a.out}")
        for k in list(got)[:3]:
            print(f"    {k}: {json.dumps(got[k])}")
        return 0
    p.write_text(json.dumps(merged, indent=1, sort_keys=True), encoding="utf-8")
    print(f"  -> {a.out}  ({len(merged):,} members)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
