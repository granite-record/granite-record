#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.3
"""
Thirty years of calendars and journals, a night at a time.

    python3 fetch_calendar_archive.py --list             # the plan, no network
    python3 fetch_calendar_archive.py --discover         # list what exists
    python3 fetch_calendar_archive.py --budget 400       # fetch that many
    python3 fetch_calendar_archive.py --status           # what is held, no network

ARCHIVE_PLAN.md step 4, built the way that page says: DISCOVERY AND FETCHING
ARE SEPARATE PROGRAMS, there is one queue and it is a file, and one worker
drains it.

WHY IT IS BUILT THAT WAY AND NOT AS A LOOP

Calendar discovery once guessed filenames -- two folder spellings, two ways of
writing "No", two day paddings -- and made about a thousand requests for files
that mostly did not exist. The firewall read that as a directory scan, which is
what it was, and blocked this address. probe_calendars.py then established that
the index lists every document by its REAL filename, in a dropdown, for every
year back to 1997 in the House and 1998 in the Senate.

So nothing here is ever constructed. `--discover` asks the index what exists
and writes it to the queue; a fetch only ever drains the queue. The filename
travels verbatim, because across thirty years there are at least three
incompatible forms of it and (year, number) is not a key for anything -- the
2003 journal list holds "HJ No 21 09-04-2003" and "HJ No 21 06-30-2003", the
same number twice, and "HJ No 23 01-07-2004", a 2004 date filed under 2003.

THE QUEUE

archive/queue.csv, one row per document:

    chamber,kind,year,name,url,path,state,attempts,error,bytes,fetched

state is wanted / held / failed / gone. A file already on disk is never asked
for again, so an interrupted run resumes by re-reading the queue and every run
is idempotent.

ONE WORKER. The queue is drained by a single process holding archive/.lock.
Two fetches at once is what got this address blocked the second time, and a
design that cannot do it beats a rule that has to be remembered.

A NIGHTLY BUDGET, NOT A MARATHON. --budget stops the run at that many
requests whether or not the queue is empty. About 5,500 documents is then a
week of quiet nights rather than one long crawl that looks exactly like an
attack from the far end.
"""

import argparse
import csv
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

from fetch_committee_reports import (DOCNUM_RE, SEL_DOC, SEL_KIND, SEL_YEAR,
                                     UA, _hidden, _options)

ROOT = Path("archive")
QUEUE = ROOT / "queue.csv"
LOCK = ROOT / ".lock"
FIELDS = ["chamber", "kind", "year", "name", "url", "path", "state",
          "attempts", "error", "bytes", "fetched"]

# The two index pages, and what each calls its own document kinds. Read off
# the pages by probe_calendars.py rather than assumed: the House says
# "Calendar"/"Journal" and the Senate "SenateCalendar"/"SenateJournal", and
# the folder is lower case in one and capitalised in the other.
SOURCES = {
    ("H", "calendar"): ("https://gc.nh.gov/house/calendars_journals/",
                        "Calendar", "calendars", "calendars", "HC"),
    ("H", "journal"): ("https://gc.nh.gov/house/calendars_journals/",
                       "Journal", "journals", "journals", "HJ"),
    ("S", "calendar"): ("https://gc.nh.gov/senate/calendars_journals/",
                        "SenateCalendar", "Calendars", "calendars_senate", "SC"),
    ("S", "journal"): ("https://gc.nh.gov/senate/calendars_journals/",
                       "SenateJournal", "Journals", "journals_senate", "SJ"),
}
VIEWER = "viewer.aspx?fileName="


def _get(url, data=None, timeout=60):
    req = urllib.request.Request(
        url, data=data,
        headers=dict(UA, **({"Content-Type":
                             "application/x-www-form-urlencoded"} if data else {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _page(url, data=None):
    return _get(url, data).decode("utf-8", errors="replace")


def _local(prefix, name, label):
    """The name the existing archive uses: HC010.pdf, SC005.pdf, HJ016.pdf.

    The number comes from the LABEL ("No 32 September 4 2026"), not the
    filename, because a filename can be "SC 29.pdf" with no "No" in it at all
    while its label still reads "No 29". Where neither carries a number the
    source name is kept, so nothing is silently renamed to a collision.
    """
    m = DOCNUM_RE.search(label or "") or DOCNUM_RE.search(name or "")
    if not m:
        return name
    num = m.group(1)
    digits = "".join(c for c in num if c.isdigit())
    suffix = "".join(c for c in num if c.isalpha()).upper()
    if not digits:
        return name
    return f"{prefix}{int(digits):03d}{suffix}.pdf"


def load_queue():
    if not QUEUE.exists():
        return []
    with QUEUE.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def save_queue(rows):
    ROOT.mkdir(exist_ok=True)
    tmp = QUEUE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    tmp.replace(QUEUE)


def discover(chamber, kind, years=None, delay=3.0):
    """Ask one index what it has. One request to load, one per year to switch."""
    index, kindval, folder, outdir, prefix = SOURCES[(chamber, kind)]
    print(f"  {chamber} {kind}: reading {index}")
    page = _page(index)
    listed = [v for v, _ in _options(page, SEL_YEAR) if v.isdigit()]
    if not listed:
        print("    the year list is empty; the page shape has changed")
        return []
    print(f"    {len(listed)} years offered, {listed[0]} back to {listed[-1]}")
    want = [y for y in listed if not years or int(y) in years]

    found = []
    # DISCOVERY NEEDS THE SAME STOP-LOSS AS THE DRAIN. The first run made five
    # failing requests in a row -- the Senate publishes no journals for
    # 1998-2002 and its page answers HTTP 500 rather than an empty list -- and
    # nothing here stopped it. Five is harmless; a whole index answering 500
    # and this looping through thirty years of it is the shape of the request
    # pattern that got this address blocked.
    run = 0
    for n, y in enumerate(want, 1):
        fields = _hidden(page)
        fields[SEL_KIND] = kindval
        fields[SEL_YEAR] = y
        fields["__EVENTTARGET"] = SEL_YEAR
        fields["__EVENTARGUMENT"] = ""
        time.sleep(delay)
        try:
            page = _page(index, urllib.parse.urlencode(fields).encode())
        except Exception as e:                          # noqa: BLE001
            run += 1
            print(f"    {y}: {type(e).__name__}: {e}")
            if run >= 4:
                print("    four years in a row failed. Stopping this "
                      "index rather than asking for twenty-six more "
                      "that will answer the same way.")
                break
            continue
        run = 0
        docs = [(v, lab) for v, lab in _options(page, SEL_DOC)
                if v and v.lower() != "select"]
        for name, label in docs:
            rel = f"{folder}\\{y}\\{name}"
            found.append({
                "chamber": chamber, "kind": kind, "year": y,
                # THE SOURCE FILENAME, VERBATIM, because across thirty years
                # there are at least three incompatible forms of it and it is
                # the only identifier this source offers.
                "name": name,
                "url": index + VIEWER + urllib.parse.quote(rel, safe=""),
                # But the LOCAL name follows the 376 files already on this
                # disk: calendars/2026/HC010.pdf, calendars_senate/2026/
                # SC005.pdf. Keyed on the source name instead, not one of
                # them would be recognised as held, and the first run would
                # re-download every one -- 376 needless requests at the
                # address that has blocked this project twice.
                "path": str(Path(outdir) / y / _local(prefix, name, label)),
                "state": "wanted", "attempts": "0", "error": "",
                "bytes": "", "fetched": ""})
        print(f"    [{n}/{len(want)}] {y}: {len(docs)} documents", flush=True)
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--chamber", choices=["H", "S", "both"], default="both")
    ap.add_argument("--kind", choices=["calendar", "journal", "both"],
                    default="both")
    ap.add_argument("--from", dest="first", type=int, default=0)
    ap.add_argument("--to", dest="last", type=int, default=9999)
    ap.add_argument("--budget", type=int, default=300,
                    help="requests this run, then stop (default 300)")
    ap.add_argument("--delay", type=float, default=3.0)
    a = ap.parse_args()

    ROOT.mkdir(exist_ok=True)
    rows = load_queue()

    if a.status or a.list:
        by = Counter((r["chamber"], r["kind"], r["state"]) for r in rows)
        print(f"{len(rows):,} documents in the queue")
        for (ch, kind, state), n in sorted(by.items()):
            print(f"  {ch} {kind:9} {state:7} {n:6,}")
        if not rows:
            print("  Nothing yet. Run --discover first; it asks the index what "
                  "exists\n  and writes the answer here.")
        held = sum(1 for r in rows if r["state"] == "held")
        if rows:
            print(f"\n  {held:,} of {len(rows):,} held "
                  f"({held / len(rows):.0%}), "
                  f"{sum(int(r['bytes'] or 0) for r in rows) / 1e6:.0f} MB")
        return 0

    chambers = ["H", "S"] if a.chamber == "both" else [a.chamber]
    kinds = ["calendar", "journal"] if a.kind == "both" else [a.kind]
    years = set(range(a.first, a.last + 1)) if a.first else None

    if a.discover:
        print("=" * 70)
        print("Asking each index what it has. Nothing is constructed.")
        print("=" * 70)
        seen = {(r["chamber"], r["kind"], r["year"], r["name"]) for r in rows}
        added = 0
        for ch in chambers:
            for kind in kinds:
                for rec in discover(ch, kind, years, a.delay):
                    key = (rec["chamber"], rec["kind"], rec["year"], rec["name"])
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(rec)
                    added += 1
        # A document already on disk is held before anything is asked for.
        for r in rows:
            if r["state"] == "wanted" and Path(r["path"]).exists():
                r["state"] = "held"
                r["bytes"] = str(Path(r["path"]).stat().st_size)
        save_queue(rows)
        held = sum(1 for r in rows if r["state"] == "held")
        print(f"\n{added:,} new, {len(rows):,} in the queue, {held:,} already "
              f"on disk -> {QUEUE}")
        return 0

    # ---- draining, and only one process may ------------------------------
    if LOCK.exists():
        age = time.time() - LOCK.stat().st_mtime
        if age < 3600:
            sys.exit(f"archive/.lock is {age / 60:.0f} minutes old: another "
                     "run has the queue.\nTwo fetches at once is what got this "
                     "address blocked. Delete the lock only\nif you are sure "
                     "nothing else is running.")
        LOCK.unlink()
    LOCK.write_text(str(os.getpid()), encoding="utf-8")
    try:
        todo = [r for r in rows
                if r["state"] == "wanted"
                and (r["chamber"] in chambers) and (r["kind"] in kinds)
                and (not years or int(r["year"]) in years)]
        print(f"{len(todo):,} wanted, taking {min(len(todo), a.budget):,} "
              f"this run at {a.delay}s apart")
        got = fail = 0
        run = 0
        t0 = time.time()
        for i, r in enumerate(todo[:a.budget], 1):
            path = Path(r["path"])
            if path.exists():
                r["state"] = "held"
                r["bytes"] = str(path.stat().st_size)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                blob = _get(r["url"])
            except Exception as e:                      # noqa: BLE001
                r["attempts"] = str(int(r["attempts"] or 0) + 1)
                r["error"] = f"{type(e).__name__}: {e}"[:180]
                if int(r["attempts"]) >= 3:
                    r["state"] = "failed"
                fail += 1
                run += 1
                print(f"  [{i}] {r['name']}: {r['error'][:80]}", flush=True)
                if run >= 3:
                    print("\nThree in a row. Stopping. netcheck.py says why "
                          "without making it worse.")
                    break
                time.sleep(a.delay * 2)
                continue
            run = 0
            path.write_bytes(blob)
            r["state"] = "held"
            r["bytes"] = str(len(blob))
            r["error"] = ""
            r["fetched"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            got += 1
            if got % 25 == 0:
                save_queue(rows)
                rate = got / max(1e-9, time.time() - t0)
                print(f"  {i}/{min(len(todo), a.budget)}  {got} fetched, "
                      f"{rate * 60:.0f}/min", flush=True)
            time.sleep(a.delay)
        save_queue(rows)
        held = sum(1 for x in rows if x["state"] == "held")
        print(f"\n{got:,} fetched, {fail} failed, {time.time() - t0:.0f}s")
        print(f"{held:,} of {len(rows):,} held "
              f"({sum(int(x['bytes'] or 0) for x in rows) / 1e6:.0f} MB)")
        left = sum(1 for x in rows if x["state"] == "wanted")
        if left:
            print(f"{left:,} still wanted. Run again for the next {a.budget}.")
    finally:
        LOCK.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
