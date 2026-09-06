#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.1
"""
Work out the shape of an NH data file without guessing.

I have been wrong twice about what a column means in these files: the docket's
first field is an LSR year rather than a session year, and the roll call
tally columns mean different things in the House and Senate. Guessing produces
confidently wrong output, which is worse than no output. So: run this, paste me
what it prints, and I will write the parser against the real thing.

    python3 probe_schema.py --dir .
    python3 probe_schema.py --file legislators.txt

Downloads the files it does not find locally. Standard library only.
"""

import argparse
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path

BASE = "https://gc.nh.gov/dynamicdatadump/"

WANTED = ["legislators.txt", "LsrSponsors.txt", "SubjectCodes.txt", "Committees.txt",
          "HouseDistricts.txt", "Counties.txt", "GeneralCodes.txt",
          "BodyStatusCodes.txt", "RollCallHistory.txt", "LSRs.txt"]

DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}")
BILL = re.compile(r"^(HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s?\d+$", re.I)


def guess(vals):
    """Name the likely role of a column from its values."""
    vals = [v for v in vals if v != ""]
    if not vals:
        return "always empty"
    u = len(set(vals))
    tags = []
    if all(DATE.match(v) for v in vals):
        tags.append("date/time")
    elif all(re.fullmatch(r"-?\d+", v) for v in vals):
        lo, hi = min(int(v) for v in vals), max(int(v) for v in vals)
        tags.append(f"integer {lo}..{hi}")
        if 1900 < lo and hi < 2100:
            tags.append("maybe a year")
    if all(BILL.match(v) for v in vals):
        tags.append("bill number")
    if all(v in ("H", "S") for v in vals):
        tags.append("chamber H/S")
    if all(v.upper() in ("R", "D", "I", "L", "U") for v in vals):
        tags.append("maybe party")
    if u == 1:
        tags.append(f"constant {vals[0]!r}")
    elif u == len(vals):
        tags.append("unique (likely a key)")
    elif u <= 12:
        tags.append(f"{u} distinct: " + ", ".join(sorted(set(vals))[:8]))
    lens = [len(v) for v in vals]
    tags.append(f"len {min(lens)}-{max(lens)}")
    return "; ".join(tags)


def probe(path, sample=400):
    print("\n" + "=" * 72)
    print(path.name)
    print("=" * 72)

    raw = path.read_bytes()
    print(f"size: {len(raw):,} bytes")

    text = raw.decode("utf-8-sig", errors="replace")
    lines = [l for l in text.splitlines() if l.strip()]
    print(f"lines: {len(lines):,}")
    if not lines:
        return

    delim = "|" if lines[0].count("|") else ("\t" if lines[0].count("\t") else ",")
    print(f"delimiter: {delim!r}")

    widths = Counter(l.count(delim) + 1 for l in lines)
    print(f"field counts: {dict(widths.most_common(5))}")
    ncols = widths.most_common(1)[0][0]

    rows = [l.split(delim) for l in lines[:sample] if l.count(delim) + 1 == ncols]

    # Header row?
    first = rows[0]
    looks_header = all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_ ]*", c.strip() or "x")
                       for c in first) and not any(DATE.match(c) for c in first)
    if looks_header:
        print(f"first row looks like a HEADER: {first}")
        rows = rows[1:]

    print(f"\n{'col':>4}  {'sample value':<38} inferred")
    print("-" * 72)
    for i in range(ncols):
        vals = [r[i].strip() for r in rows]
        shown = next((v for v in vals if v), "")
        if len(shown) > 36:
            shown = shown[:33] + "..."
        print(f"{i:>4}  {shown:<38} {guess(vals)}")

    print("\nfirst 3 rows verbatim:")
    for l in lines[:3]:
        print("  " + (l if len(l) < 200 else l[:197] + "..."))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--file")
    ap.add_argument("--no-download", action="store_true")
    a = ap.parse_args()

    d = Path(a.dir)
    targets = [Path(a.file)] if a.file else [d / n for n in WANTED]

    for t in targets:
        if not t.exists():
            if a.no_download:
                print(f"missing: {t.name}")
                continue
            try:
                print(f"downloading {t.name}...", file=sys.stderr)
                urllib.request.urlretrieve(BASE + t.name, t)
            except Exception as e:
                print(f"\ncould not fetch {t.name}: {e}")
                continue
        try:
            probe(t)
        except Exception as e:
            print(f"\nfailed to read {t.name}: {e}")

    print("\n" + "=" * 72)
    print("Paste this whole output back and I will write the parsers against it.")
    print("The ones that matter most: legislators.txt and HouseDistricts.txt for")
    print("the town lookup, LsrSponsors.txt for sponsor search, SubjectCodes.txt")
    print("for topic browse, and RollCallHistory.txt for how each member voted.")


if __name__ == "__main__":
    main()
