#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.1
"""
db/Docket.psv -> the seven-column shape narrative.py already reads.

    python3 docket_from_db.py --out Docket_db.txt              # 1989-2016
    python3 docket_from_db.py --out x.txt --years 1989 1990    # a slice

The dump's own columns are

    SessionYear|LSR|ExpandedBillNo|StatusDate|CondensedBillNo|
    LegislativeBody|Description|DataBase|legislationid|OrderDate|statusorder

and Docket.txt's are

    session|lsr|created|bill|body|description|modified

Both are on this disk; nothing here asks anyone for anything.

WHY CondensedBillNo AND NOT ExpandedBillNo

ExpandedBillNo is "HB  0169" -- padded for a fixed-width report. Every other
file on this disk says HB169, and narrative.py compares bill ids literally.

WHY THE DATE IS REFORMATTED

The dump writes "01/05/1989 14:18:39"; narrative.py's parse_docket asks
datetime for "%m/%d/%Y %I:%M:%S %p" and silently falls back to datetime.min
when that fails -- which would put every archived event at year one and sort
the whole history backwards. It is a real clock time here rather than the
midnight the web-page fetcher has to invent, so it is kept, converted.
"""
import argparse
import collections
from datetime import datetime
from pathlib import Path

SRC = Path("db/Docket.psv")
IN = "%m/%d/%Y %H:%M:%S"
OUT = "%m/%d/%Y %I:%M:%S %p"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--years", nargs="*", default=None,
                    help="default: every year the site has no docket for")
    ap.add_argument("--src", default=str(SRC))
    a = ap.parse_args()

    # 2025-2026 is already fetched from the live pages and 2023-2024 from the
    # legacy ones; this is for the years nothing on this disk covers.
    skip = {"2023", "2024", "2025", "2026"}
    want = set(a.years) if a.years else None

    rows = 0
    kept = []
    badtime = collections.Counter()
    years = collections.Counter()
    with open(a.src, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.rstrip("\n").split("|")
            if len(f) < 11:
                continue
            rows += 1
            year = f[0].strip()
            if want is not None:
                if year not in want:
                    continue
            elif year in skip:
                continue
            try:
                stamp = datetime.strptime(f[3].strip(), IN).strftime(OUT)
            except ValueError:
                badtime[year] += 1
                stamp = f[3].strip()
            try:
                order = datetime.strptime(f[9].strip(), IN).strftime(OUT)
            except ValueError:
                order = stamp
            kept.append("|".join([
                year, f[1].strip().zfill(4), stamp, f[4].strip().upper(),
                f[5].strip() or "H", f[6].replace("|", "/").strip(), order]))
            years[year] += 1

    Path(a.out).write_text("\n".join(kept) + "\n", encoding="utf-8")
    print(f"{rows:,} rows read, {len(kept):,} written -> {a.out}")
    print(f"  {len(years)} years, {min(years, default='-')}..{max(years, default='-')}")
    if badtime:
        print("  unparsed timestamps: "
              + ", ".join(f"{k} x{v}" for k, v in sorted(badtime.items())))
    # Silence is not success.
    if not kept:
        raise SystemExit("Nothing was written. Check --years against the dump.")


if __name__ == "__main__":
    main()
