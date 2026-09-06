#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.1
"""
Lay out the archive so more than one legislative term can coexist.

    python3 setup_archive.py --dry-run      # show what would move
    python3 setup_archive.py                # copy current files into place
    python3 setup_archive.py --verify       # check an existing layout

The problem this solves is narrow and certain: bill numbers repeat between
terms. There is an HB 84 in 2025-2026 and there will be another in 2023-2024.
Every file that keys on a bill number alone -- bills.json, sponsors.json,
bill_status.json -- silently overwrites one with the other the moment a second
term is added. Nothing errors; a bill just quietly becomes the wrong bill.

The layout:

    archive/
      sessions.json                 which terms exist, and what each holds
      2025-2026/
        raw/       Docket.txt, LSRs.txt, ...   bulk files as downloaded
        pages/     status/, docket/            cached web pages
        parsed/    bills.json, sponsors.json   normalised, this term only
      2023-2024/
        pages/     status/                     no bulk files exist for it
        parsed/    ...

Two rules make it work. Raw and cached pages are immutable once written, so a
parser change is re-applied from disk with no network. And parsed output lives
under its term, so a bill number is only ever unique within the folder it sits
in.

This copies rather than moves. The live pipeline keeps running from the flat
layout until you switch it over, and nothing here can break a working site.
"""

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

# Files the General Court publishes for the current session only. Once a term
# ends these stop describing it, which is why they are worth archiving the day
# they are downloaded rather than the day they are needed.
BULK = ["Docket.txt", "LSRs.txt", "LsrsOnly.txt", "LsrSponsors.txt",
        "RollCallSummary.txt", "RollCallHistory.txt", "legislators.txt",
        "Members.txt", "HouseDistricts.txt", "Counties.txt", "Committees.txt",
        "SubjectCodes.txt", "GeneralCodes.txt", "BodyStatusCodes.txt"]

DERIVED = ["narratives.json", "rollcalls.json", "bill_status.json",
           "committee_reports.json", "floor_index.json", "journals.json",
           "calendars.json", "former_members.json"]


def term_of(year):
    y = int(year)
    start = y if y % 2 else y - 1
    return f"{start}-{start + 1}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--archive", default="archive")
    ap.add_argument("--term", help="which term the flat files belong to; "
                                   "worked out from LSRs.txt if not given")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    src, arc = Path(a.dir), Path(a.archive)

    if a.verify:
        return verify(arc)

    # Which term are the flat files for? Take it from the data rather than
    # asking, so it cannot be answered wrongly.
    term = a.term
    if not term:
        lsr = src / "LSRs.txt"
        if lsr.exists():
            with open(lsr, encoding="utf-8-sig", errors="replace") as fh:
                first = fh.readline().split("|")
                if first and first[0].strip().isdigit():
                    term = term_of(first[0].strip())
    if not term:
        term = term_of(datetime.now().year)
        print(f"Could not read a year from LSRs.txt; assuming {term}. "
              "Use --term to set it.")
    print(f"Term: {term}\n")

    root = arc / term
    plan = []

    for name in BULK:
        f = src / name
        if f.exists():
            plan.append((f, root / "raw" / name, f.stat().st_size))
    for name in DERIVED:
        f = src / name
        if f.exists():
            plan.append((f, root / "parsed" / name, f.stat().st_size))

    # Cached pages are already named with the year they came from, so they can
    # be filed by term without guessing.
    for cache, dest in (("status_pages", "status"), ("bill_pages", "docket"),
                        ("rc_pages", "rollcall"), ("calendars", "calendars")):
        d = src / cache
        if not d.exists():
            continue
        for f in d.iterdir():
            if not f.is_file():
                continue
            yr = f.name.split("_")[0]
            t = term_of(yr) if yr.isdigit() and len(yr) == 4 else term
            plan.append((f, arc / t / "pages" / dest / f.name, f.stat().st_size))

    if not plan:
        print("Nothing found to archive. Run this from the folder with the "
              "data files in it.")
        return

    by_kind = Counter(p[1].parent.name for p in plan)
    total = sum(p[2] for p in plan)
    print(f"{len(plan):,} files, {total/1e6:.1f} MB")
    for k, n in sorted(by_kind.items(), key=lambda x: -x[1]):
        print(f"  {k:<12} {n:,}")

    if a.dry_run:
        print("\nA sample of what would be copied:")
        for f, to, _ in plan[:6]:
            print(f"  {f}  ->  {to}")
        print("\nNothing was written. Drop --dry-run to do it.")
        return

    done = 0
    for f, to, _ in plan:
        to.parent.mkdir(parents=True, exist_ok=True)
        if not to.exists() or to.stat().st_mtime < f.stat().st_mtime:
            shutil.copy2(f, to)
            done += 1
    print(f"\n{done:,} copied, {len(plan) - done:,} already current")

    write_manifest(arc)
    print("\nThe flat files are untouched, so the live pipeline still works.")
    print("Nothing switches over until build_data.py is pointed at the archive.")


def write_manifest(arc):
    """A record of what each term holds, so a build can see it without guessing."""
    sessions = {}
    for d in sorted(arc.iterdir()):
        if not d.is_dir() or "-" not in d.name:
            continue
        raw = sorted(f.name for f in (d / "raw").glob("*") if f.is_file()) \
            if (d / "raw").exists() else []
        parsed = sorted(f.name for f in (d / "parsed").glob("*.json")) \
            if (d / "parsed").exists() else []
        pages = {}
        if (d / "pages").exists():
            for sub in (d / "pages").iterdir():
                if sub.is_dir():
                    pages[sub.name] = sum(1 for _ in sub.iterdir())
        sessions[d.name] = {
            "term": d.name,
            "years": [int(d.name[:4]), int(d.name[5:])],
            "bulk_files": raw,
            "has_bulk_data": bool(raw),
            "parsed": parsed,
            "cached_pages": pages,
        }
    (arc / "sessions.json").write_text(
        json.dumps({"generated": datetime.now().isoformat(timespec="seconds"),
                    "sessions": sessions}, indent=2), encoding="utf-8")
    print(f"\narchive/sessions.json: {len(sessions)} term(s)")
    for t, v in sessions.items():
        print(f"  {t}  bulk: {'yes' if v['has_bulk_data'] else 'no '}  "
              f"parsed: {len(v['parsed'])}  "
              f"pages: {sum(v['cached_pages'].values()):,}")


def verify(arc):
    p = arc / "sessions.json"
    if not p.exists():
        print(f"No {p}. Run setup_archive.py first.")
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    print(f"archive built {d['generated']}\n")
    for t, v in d["sessions"].items():
        print(f"{t}")
        print(f"  bulk files : {len(v['bulk_files'])}"
              + ("" if v["has_bulk_data"]
                 else "   (none - this term predates the download, so every "
                      "field comes from cached pages)"))
        print(f"  parsed     : {', '.join(v['parsed']) or 'none yet'}")
        for k, n in v["cached_pages"].items():
            print(f"  pages/{k:<10} {n:,}")
    print("\nA term with no bulk files is expected for anything before the")
    print("current one: those files only ever describe the session in progress.")


if __name__ == "__main__":
    main()
