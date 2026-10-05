#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-11.6
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

AND THE BILLS A TERM'S FILE HAS NO ROW FOR (1 October 2026)

  db/past/PastDocket.psv   the General Court's past docket view, dumped by
                           fetch_past_db.py

A fetched docket holds the bills the General Court's search listed, so a bill
that list left out has no row in it: SB 340 and SB 499 of 2016, HR 1 to HR 6
of 2017, HB 451 of 2019, HB 459 of 2021. narrative.py takes those bills'
rows from the view (its past_docket_rows says how, and that a bill with any
row of its own takes none). The view is 94 MB and is the laptop's to send to
the nightly's machine; where it is not here those bills have no history, and
this says so rather than narrating nothing for them in silence.

AND THE CHAPTER THE PAGE PRINTS. chapters.json is passed too, so that a law
the docket numbers as another bill's is told with the number extract_chapters
settled: this step runs after that one in a build.
"""

import argparse
import glob
import re
import subprocess
import sys
from pathlib import Path

TERM = re.compile(r"^Docket(?:_db)?_(\d{4}-\d{4})\.txt$")
# narrative.py's own account of which rows the LSRs took off a bill or gave to
# one (narrative.report_lsrs), summed across the terms below. The bill list's
# path is in brackets and may hold a colon of its own: "D:/nh/data/bills.json".
LSR_SAID = re.compile(r"rows by LSR \(.*\): ([\d,]+) row\(s\) left out of ([\d,]+) "
                      r"histor(?:y|ies)[^;]*; ([\d,]+) given to the ([\d,]+) bill"
                      r"\(s\)[^,]*, from ([\d,]+) key")
# And its account of the rows it took from the past docket view for the bills
# a term's own file has none for (narrative.past_docket_rows).
PAST_DOCKET = Path("db/past/PastDocket.psv")
PAST_SAID = re.compile(r"rows from the past docket \(.*\): ([\d,]+) row\(s\) given to "
                       r"the ([\d,]+) bill\(s\)[^(]*(?:\((.*)\))?")
CHAPTERS = Path("chapters.json")


def dockets():
    """{term: path}, the fetched docket preferred over the database's.

    NOT THE SESSION'S OWN TERM (5 October 2026). freeze_term.py writes
    Docket_<term>.txt for the current term before the files turn, and until
    they do the term is narrated from Docket.txt, by build_all's own step,
    which runs before this one: narrating its frozen copy here would put the
    older docket's histories over the newer ones. Once the session's files
    are the next term's, the copy is the term's docket like any other."""
    import proceedings as P
    session = P.session_term()
    out = {}
    for p in sorted(glob.glob("Docket_db_*.txt")) + sorted(glob.glob("Docket_[0-9]*.txt")):
        m = TERM.match(Path(p).name)
        if m and m.group(1) != session:
            out[m.group(1)] = p
        elif m:
            print(f"  {p} waits: {session} is still the session's term, narrated from Docket.txt")
    return dict(sorted(out.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="narratives.json")
    ap.add_argument("--members", default="data/legislators.json")
    # Each bill's own LSR, which decides which docket rows are its own:
    # narrative.own_rows says why. Passed rather than left to narrative.py's
    # default, so the rule cannot silently stop when one of them moves.
    ap.add_argument("--bills", default="data/bills.json")
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

    bills, lsr = 0, None
    # The past docket view and the settled chapters, where each is here.
    extra = []
    if PAST_DOCKET.exists():
        extra += ["--past-docket", str(PAST_DOCKET)]
    if CHAPTERS.exists():
        extra += ["--chapters", str(CHAPTERS)]
    past = [0, 0, []]
    for term, path in found.items():
        r = subprocess.run(
            [sys.executable, "narrative.py", "--docket", path, "--all",
             "--out", a.out, "--members", a.members, "--bills", a.bills] + extra,
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
        # And which rows the LSRs took off a bill or gave to one: a rule that
        # stopped working looks exactly like a docket with nothing misfiled.
        for line in (r.stdout or "").splitlines():
            if "docket_corrections.json" in line or "rows by LSR" in line:
                print("    " + line.strip())
            said = LSR_SAID.search(line)
            if said:
                lsr = [x + int(y.replace(",", "")) for x, y in
                       zip(lsr or [0] * 5, said.groups())]
            said = PAST_SAID.search(line)
            if said and int(said.group(2).replace(",", "")):
                print("    " + line.strip())
                past[0] += int(said.group(1).replace(",", ""))
                past[1] += int(said.group(2).replace(",", ""))
                past[2] += [f"{b} {term}" for b in (said.group(3) or "").split(", ") if b]
    # What the past docket view gave, or that it is not here to give it.
    if PAST_DOCKET.exists():
        print(f"rows from the past docket, every term: {past[0]:,} row(s) given to the "
              f"{past[1]:,} bill(s) their term's own docket has no row for"
              + (f" ({', '.join(past[2])})" if past[2] else ""))
    else:
        print(f"rows from the past docket: {PAST_DOCKET} IS NOT HERE, so the bills "
              "whose docket only that view holds have no history (SB 340 and SB 499 "
              "of 2016, HR 1 to HR 6 of 2017, HB 451 of 2019 and HB 459 of 2021 on "
              "1 October 2026). fetch_past_db.py dumps it, and the kit carries it "
              "once the laptop has sent it.")
    # The whole archive's count, last, where build_all's summary of this step
    # shows it: per term it is one line among thirty-six.
    if lsr is None:
        print("rows by LSR: no term said what its LSRs did -- narrative.py read no "
              f"bill list at {a.bills}, so every row stayed under the number it was "
              "filed under")
    else:
        print(f"rows by LSR, every term: {lsr[0]:,} row(s) left out of {lsr[1]:,} "
              f"histories as another measure's; {lsr[2]:,} given to the {lsr[3]:,} "
              f"bill(s) whose LSR they carry, from {lsr[4]:,} key(s) no bill carries")
    print(f"\n{bills:,} bills narrated into {a.out}")
    # Silence is not success: a run that narrated nothing looks exactly like
    # a term with no docket.
    if not bills:
        sys.exit("No bill was narrated out of any of them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
