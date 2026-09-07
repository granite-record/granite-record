#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.3
"""
Report what is actually on disk, and which scripts are out of date.

    python3 inventory.py              # tree, data files, script versions
    python3 inventory.py --full       # every filename, not just counts

Two questions this answers that are otherwise guesswork.

WHAT IS HERE. Directory sizes, file counts, and when each data file was last
written. Enough to see at a glance that a fetch produced nothing, or that a
build ran before the file it depends on.

AM I RUNNING THE CURRENT SCRIPT. There are no version numbers in these files,
so instead each is checked for a few lines that only the current version has --
a fix, a renamed variable, a new argument. A script missing them is an older
copy that was never replaced, which has already caused several confusing hours:
a bug reported as unfixed because the fix was sitting in the downloads folder.

Nothing here writes or changes anything.
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

# Every script carries a version stamp on its second line:
#
#     # GRANITE_VERSION: 2026-09-04.2
#
# versions.json says which version each file should be. Comparing the two
# answers "am I running the copy you gave me" exactly, rather than by looking
# for lines a newer version happens to contain. That guesswork was fragile in
# both directions: it missed real staleness when a fix did not add a
# distinctive line, and it cried wolf when I chose a marker badly.

# Files the pipeline reads. Their absence or staleness explains most surprises.
DATA = ["Docket.txt", "LSRs.txt", "LsrsOnly.txt", "LsrSponsors.txt",
        "RollCallSummary.txt", "RollCallHistory.txt", "legislators.txt",
        "Members.txt", "HouseDistricts.txt", "Counties.txt", "Committees.txt",
        "SubjectCodes.txt",
        "narratives.json", "rollcalls.json", "bill_status.json",
        "committee_reports.json", "senate_reports.json",
        "floor_index.json", "journals.json",
        "calendars.json", "former_members.json", "verification_manifest.csv"]

# A superseded SCRIPT does not always mean a superseded FILE. fetch_bill_titles.py
# was replaced by fetch_bill_status.py, but build_data.py still reads
# bill_titles.json as a fallback -- it holds titles recovered from the legacy
# docket pages for bills the current session's files no longer describe, which
# is the fix for the 847 bills that had a history and no title. Deleting it on
# this script's advice would quietly undo that.
#
# bill_sponsors.json is read by nothing, so it stays on the list.
STALE = ["bill_sponsors.json", "fetch_bill_titles.py",
         "fetch_rollcall_details.py", "analyze_drift.py", "build_site.py"]


def size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def age(p):
    d = datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)
    if d.days > 0:
        return f"{d.days}d ago"
    h = d.seconds // 3600
    return f"{h}h ago" if h else f"{d.seconds // 60}m ago"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args()
    root = Path(a.dir).resolve()
    print("=" * 68)
    print(root)
    print("=" * 68)

    # ---- folders -----------------------------------------------------------
    print("\nFOLDERS")
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        files = [f for f in d.rglob("*") if f.is_file()]
        tot = sum(f.stat().st_size for f in files)
        subs = sorted({f.parent.relative_to(d).as_posix() for f in files
                       if f.parent != d})
        print(f"  {d.name + '/':<22} {len(files):>7,} files  {size(tot):>10}"
              + (f"   ({len(subs)} subfolders)" if subs else ""))
        if a.full and subs:
            for sname in subs[:12]:
                n = sum(1 for f in (d / sname).iterdir() if f.is_file())
                print(f"      {sname + '/':<24} {n:,}")
            if len(subs) > 12:
                print(f"      ... {len(subs) - 12} more")

    # ---- data --------------------------------------------------------------
    print("\nDATA FILES")
    missing = []
    for name in DATA:
        f = root / name
        if f.exists():
            print(f"  {name:<28} {size(f.stat().st_size):>10}   {age(f)}")
        else:
            missing.append(name)
    if missing:
        print(f"\n  not present: {', '.join(missing)}")

    # ---- script versions ---------------------------------------------------
    print("\nSCRIPTS")
    expected = {}
    vp = root / "versions.json"
    if vp.exists():
        expected = json.loads(vp.read_text(encoding="utf-8")).get("files", {})
        print(f"  (versions.json lists {len(expected)} files)\n")
    else:
        print("  versions.json not found - versions are listed but not checked.")
        print("  Download it alongside the scripts to get the comparison.\n")

    old, absent, unstamped = [], [], []
    for name in sorted(set(expected) | {p.name for p in root.glob("*.py")}
                       | {"bills.html"}):
        f = root / name
        if not f.exists():
            # The search page lives in site/, not beside the scripts.
            alt = root / "site" / name if name.endswith(".html") else None
            if alt and alt.exists():
                f = alt
            else:
                if name in expected:
                    absent.append(name)
                continue
        txt = f.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"GRANITE_VERSION:\s*(\S+?)\s*(?:-->|$)", txt, re.M)
        got = m.group(1) if m else None
        want = expected.get(name)
        if got is None:
            # If versions.json expects this file, an unstamped copy predates
            # stamping entirely -- which makes it old, not merely unlabelled.
            if want:
                old.append((name, "unstamped", want))
                print(f"  {name:<28} OUT OF DATE  no stamp   want {want}")
            else:
                unstamped.append(name)
                print(f"  {name:<28} no version stamp     {age(f)}")
        elif want and got != want:
            old.append((name, got, want))
            print(f"  {name:<28} OUT OF DATE  have {got}  want {want}")
        else:
            print(f"  {name:<28} {got:<20} {age(f)}")

    if absent:
        print(f"\n  listed but not present: {', '.join(absent)}")
    if unstamped:
        print(f"\n  no stamp yet: {', '.join(unstamped)}")

    # ---- files that should be gone -----------------------------------------
    leftover = [n for n in STALE if (root / n).exists()]
    if leftover:
        print("\nSUPERSEDED, safe to delete")
        for n in leftover:
            print(f"  {n}")

    # ---- verdict -----------------------------------------------------------
    print("\n" + "=" * 68)
    if old:
        print(f"{len(old)} file(s) are older copies. Re-download these:")
        for n, got, want in old:
            print(f"  {n:<28} {got}  ->  {want}")
        print("\nAn old copy is the usual reason a fix appears not to have")
        print("worked: the change exists, just not in the file being run.")
    elif expected:
        print("Every file matches the version it should be.")
    else:
        print("No versions.json, so nothing was compared.")
    print("=" * 68)


if __name__ == "__main__":
    main()
