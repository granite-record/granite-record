#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-07.1
"""
Which towns are in each Senate district, from the General Court's database.

    python3 fetch_senate_districts_db.py --dry-run
    python3 fetch_senate_districts_db.py

WHY

HouseDistricts.txt covers the House and nothing else, so every senator's page
said nothing at all about the towns they represent, and build_data.py has
carried the comment "Senate districts are not in this file" since it was
written. The database has senateDistricts: 320 rows of county, district, ward
and town, which is the same shape HouseDistricts.txt has.

That closes the gap for the 24 senators, and it means "find your
representatives" can answer the Senate half of the question too.

THIS IS NOT THE WEB SERVER. It is the SQL host the General Court publishes
credentials for at gc.nh.gov/downloads, and the one statement is a SELECT.
"""

import argparse
import collections
import json
import sys
from pathlib import Path

import probe_db

SQL = """
SELECT ISNULL(countycode,'') AS cc,
       ISNULL(County,'') AS county,
       CAST(Districtcode AS varchar(8)) AS district,
       CAST(ISNULL(Ward,'0') AS varchar(8)) AS ward,
       ISNULL(Town,'') AS town
FROM senateDistricts
ORDER BY Districtcode, Town
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/senate_towns.json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cs = (f"Server={probe_db.HOST};Database={probe_db.DATABASE};"
          f"User ID={probe_db.USER};Password={probe_db.PASSWORD};"
          "Encrypt=False;TrustServerCertificate=True;Connect Timeout=25")
    print("SELECT only: towns by Senate district")
    res, err = probe_db.run(cs, [("sd", SQL)])
    if err:
        sys.exit(f"  the database refused: {err}")
    if res[0].get("error"):
        sys.exit(f"  {str(res[0]['error'])[:200]}")
    rows = res[0].get("rows") or []
    rows = [rows] if isinstance(rows, dict) else rows
    if not rows:
        sys.exit("  nothing came back. senateDistricts held 320 rows on "
                 "7 September.")

    out = collections.defaultdict(list)
    for r in rows:
        d = str(r.get("district") or "").strip().lstrip("0") or "0"
        town = str(r.get("town") or "").strip()
        if not town or d == "0":
            continue
        out[d].append({
            "town": town,
            "ward": str(r.get("ward") or "0").strip().lstrip("0"),
            "county": str(r.get("county") or "").strip(),
            "county_code": str(r.get("cc") or "").strip().zfill(2),
        })
    for d in out:
        out[d].sort(key=lambda x: (x["town"], int(x["ward"] or 0)))

    n = sum(len(v) for v in out.values())
    warded = sum(1 for v in out.values() for x in v if x["ward"])
    print(f"  {n:,} town seats across {len(out)} Senate districts, "
          f"{warded:,} of them a single ward of a city")

    if a.dry_run:
        k = sorted(out, key=lambda x: int(x))[0]
        print(f"\n--dry-run: nothing written to {a.out}")
        print(f"    district {k}: "
              + ", ".join(x["town"] for x in out[k][:6]))
        return 0

    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({k: out[k] for k in
                             sorted(out, key=lambda x: int(x))}, indent=1),
                 encoding="utf-8")
    print(f"  -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
