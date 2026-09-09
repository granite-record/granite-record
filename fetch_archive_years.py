#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.1
"""
Every bill the General Court has filed since 1989, two requests a year.

    python3 fetch_archive_years.py --list             # the plan, no network
    python3 fetch_archive_years.py --from 1989 --to 2022
    python3 fetch_archive_years.py --year 2019        # just one

ARCHIVE_PLAN.md step 2, and the best ratio on that page by a wide margin.

The public database holds the docket back to 1989 but `Legislation` -- the
titles, the statuses, the sponsors -- only for 2025-2026. The web has the rest:
the Advanced Bill Status Search answers a session year with EVERY bill of that
year on one page, carrying the title, the general and per-chamber status, the
last committee, the last hearing and the links each bill cites.

That is two requests a session year. Thirty-six years is 72 requests for
roughly 36,000 bills, against the 36,000 requests it would take one bill at a
time -- which is the difference between a question and a crawl, on an address
that has been blocked twice.

WHAT THIS ADDS OVER fetch_archive_bills.py

Nothing about the fetching or the parsing: it calls that script once a year and
that script does the work, merging each year into archive_bills.json without
discarding the last. What this adds is the loop and its manners -- one year at
a time in one process, a wait between years, a hard stop after two consecutive
failures, and a note of what was already done so a second run costs nothing.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import proceedings as P

OUT = Path("archive_bills.json")
LOG = Path("archive_years.json")


def held():
    """{year: bills} for what is already on disk, by term."""
    if not OUT.exists():
        return {}
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="first", type=int, default=1989)
    ap.add_argument("--to", dest="last", type=int, default=2022)
    ap.add_argument("--year", type=int, help="one session year only")
    ap.add_argument("--wait", type=float, default=8.0,
                    help="seconds between years (default 8)")
    ap.add_argument("--list", action="store_true",
                    help="print the plan and make no request")
    a = ap.parse_args()

    years = [a.year] if a.year else list(range(a.first, a.last + 1))
    have = held()
    done = {t: len(v) for t, v in have.items()}

    print("=" * 70)
    print("Every bill, by session year, from the Advanced Bill Status Search")
    print("=" * 70)
    print(f"  years     {years[0]}-{years[-1]} ({len(years)})")
    print(f"  requests  {len(years) * 2} in total, two a year")
    print(f"  on disk   {sum(done.values()):,} bills across {len(done)} terms")
    for t in sorted(done):
        print(f"              {t}: {done[t]:,}")
    print()

    if a.list:
        for y in years:
            print(f"  {y}  -> term {P.term_of(str(y))}")
        print("\n  Nothing was asked for and nothing was written.")
        return 0

    run, ok, bad = 0, 0, []
    started = time.time()
    for i, y in enumerate(years, 1):
        print(f"[{i}/{len(years)}] session year {y}", flush=True)
        r = subprocess.run([sys.executable, "fetch_archive_bills.py",
                            "--year", str(y)],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        tail = (r.stdout or "").strip().split("\n")
        for line in tail[-3:]:
            print(f"      {line}", flush=True)
        if r.returncode != 0:
            bad.append(y)
            run += 1
            err = (r.stderr or r.stdout or "").strip().split("\n")[-1][:150]
            print(f"      FAILED: {err}", flush=True)
            # Two in a row is the server saying no, not one odd year.
            if run >= 2:
                print("\nTwo years failed in a row. Stopping rather than "
                      "pushing at a server that is\nrefusing. "
                      "python3 netcheck.py says why without making it worse.")
                break
        else:
            run = 0
            ok += 1
        if i < len(years):
            time.sleep(a.wait)

    have = held()
    total = sum(len(v) for v in have.values())
    print()
    print("=" * 70)
    print(f"  {ok} of {len(years)} years fetched in {time.time() - started:.0f}s, "
          f"{len(bad)} failed")
    if bad:
        print(f"  failed: {', '.join(str(b) for b in bad)}")
    print(f"  {total:,} bills across {len(have)} terms in {OUT}")
    for t in sorted(have):
        print(f"    {t}: {len(have[t]):,}")
    print("=" * 70)
    LOG.write_text(json.dumps(
        {"fetched": ok, "failed": bad, "terms": {t: len(v) for t, v in have.items()}},
        indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
