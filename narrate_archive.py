#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-11.1
"""
Plain-language histories for every archived term whose docket is on disk.

    python3 narrate_archive.py                 # every archived docket
    python3 narrate_archive.py --list          # say what would run

narrative.py takes one docket at a time and MERGES into narratives.json,
which is right: the current term's step and the archived ones must not
overwrite each other. This runs it once per archived docket, in order, so a
rebuild from a clean narratives.json produces the whole archive rather than
whichever term was narrated by hand last.

WHICH FILES

  Docket_db_<term>.txt   the database's own dump, 1989-2014, written by
                         docket_from_db.py
  Docket_<term>.txt      a term fetched from the web pages, 2015-2024

Where both exist for a term the fetched one wins: it is the whole term,
while the database's stops part way through 2016. The current term's
Docket.txt is narrated by build_all's own step and is not touched here.
"""

import argparse
import glob
import re
import subprocess
import sys
from pathlib import Path

TERM = re.compile(r"^Docket(?:_db)?_(\d{4}-\d{4})\.txt$")


def dockets():
    """{term: path}, the fetched docket preferred over the database's."""
    out = {}
    for p in sorted(glob.glob("Docket_db_*.txt")) + sorted(glob.glob("Docket_[0-9]*.txt")):
        m = TERM.match(Path(p).name)
        if m:
            out[m.group(1)] = p
    return dict(sorted(out.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="narratives.json")
    ap.add_argument("--members", default="data/legislators.json")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    found = dockets()
    if not found:
        print("No archived docket on this disk; nothing to narrate.")
        return 0
    print(f"{len(found)} archived dockets: " + ", ".join(found))
    if a.list:
        for term, path in found.items():
            print(f"  {term:11} {path}")
        return 0

    bills = 0
    for term, path in found.items():
        r = subprocess.run(
            [sys.executable, "narrative.py", "--docket", path, "--all",
             "--out", a.out, "--members", a.members],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            tail = (r.stderr or r.stdout).strip().splitlines()[-1:]
            sys.exit(f"narrative.py failed on {path}: {tail}")
        m = re.search(r"([\d,]+) bills across", r.stdout or "")
        n = int(m.group(1).replace(",", "")) if m else 0
        bills += n
        print(f"  {term:11} {n:6,} bills  <- {path}")
        # What docket_corrections.json did, and above all what it failed to
        # do: an entry that stopped matching lets a mistyped date back onto
        # the site, and this run's output is captured, so it is passed on.
        for line in (r.stdout or "").splitlines():
            if "docket_corrections.json" in line:
                print("    " + line.strip())
    print(f"\n{bills:,} bills narrated into {a.out}")
    # Silence is not success: a run that narrated nothing looks exactly like
    # a term with no docket.
    if not bills:
        sys.exit("No bill was narrated out of any of them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
