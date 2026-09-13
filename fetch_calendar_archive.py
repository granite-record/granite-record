#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.6
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
requests whether or not the queue is empty. About 4,400 documents is then a
fortnight of quiet nights rather than one long crawl that looks exactly like
an attack from the far end.

AND SLOWLY. The first drain ran at three seconds and 18 documents a minute,
and one request in came back RemoteDisconnected -- the server accepting the
connection and closing it without sending a byte, which is this address's
signature for being refused. It recovered and kept going, and that is exactly
the behaviour not to have: a fetch that pushes through a refusal is how the
last two blocks were earned.

So the default is 15 seconds with jitter, which is four documents a minute and
about sixteen hours for the whole archive spread over as many nights as it
takes. The goal is every document eventually, not many documents today.
Nothing here has a deadline; the server is the only party that can be
inconvenienced, and it did not ask for any of this.

RemoteDisconnected is treated as its own thing. One is bad luck and costs a
two-minute pause; two in a run ends the run, whether or not they were
consecutive, because the second one is a pattern.
"""

import argparse
import csv
import os
import random
import refusal
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
# No LOCK here. The one-worker lock is refusal.LOCK, taken through
# refusal.hold(); a second name for the same file is how this script came to
# manage it by hand.
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
    ap.add_argument("--budget", type=int, default=150,
                    help="requests this run, then stop (default 150)")
    ap.add_argument("--delay", type=float, default=15.0,
                    help="seconds between requests (default 15). Jittered by "
                         "a quarter either way, so a run does not arrive on a "
                         "metronome.")
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
    #
    # refusal.hold() is the one-worker rule: take archive/.lock, or run under
    # the lane that holds it, or do not run. This block used to do it by hand
    # -- exit if the lock was under an hour old, delete it if older, and
    # unlink it unconditionally on the way out. Under watchers/gc_lane.py,
    # whose lock is touched every minute, that meant exiting 1 at once, which
    # stops the lane; and had it run, it would have deleted the lane's own
    # lock when it finished. refusal.py names this script as the one that
    # deleted locks.
    refusal.check("The calendar drain")
    with refusal.hold("the calendar drain") as held:
        return drain(rows, chambers, kinds, years, a, held)


def drain(rows, chambers, kinds, years, a, held):
    """Fetch up to --budget wanted documents. 0 done, 1 stopped, 2 refused.

    A run that stops early says so in its exit status. The lane reads any
    non-zero status as "stop here", and a drain that broke off on two failures
    and exited 0 would have had the lane rest half an hour and send the next
    batch at the same address.
    """
    stopped = ""
    try:
        todo = [r for r in rows
                if r["state"] == "wanted"
                and (r["chamber"] in chambers) and (r["kind"] in kinds)
                and (not years or int(r["year"]) in years)]
        n = min(len(todo), a.budget)
        print(f"{len(todo):,} wanted, taking {n:,} this run at about "
              f"{a.delay:g}s apart -- roughly {n * a.delay / 60:.0f} minutes, "
              f"{60 / a.delay:.1f} a minute")
        got = fail = 0
        run = dropped = 0
        t0 = time.time()
        for i, r in enumerate(todo[:a.budget], 1):
            path = Path(r["path"])
            if path.exists():
                r["state"] = "held"
                r["bytes"] = str(path.stat().st_size)
                continue
            # Immediately before the request, not before the sleep that
            # preceded it: a refusal another process met while this one
            # waited, or a lane killed while it waited, stops it here.
            if refusal.MARK.exists():
                stopped = "refused"
                print("\narchive/refused.json is on file. Stopping.")
                break
            if not held.still():
                stopped = "the lane"
                print("\nThe lane holding archive/.lock is gone. Stopping.")
                break
            path.parent.mkdir(parents=True, exist_ok=True)
            # ONE READING OF EVERY ANSWER. This loop used to recognise a
            # refusal by searching the error text for RemoteDisconnected,
            # ConnectionReset or 403 -- which missed a reset at connect time
            # ("[WinError 10054]"), a 429, a 503, and the firewall's block
            # page served with HTTP 200, which it would have saved as a PDF
            # and marked held for ever. refusal.classify() is the reading
            # every other fetch uses.
            try:
                blob = _get(r["url"])
                kind = refusal.classify(
                    body=blob[:4000].decode("utf-8", "replace"))
                why = "the firewall's block page, served as 200" if kind else ""
                if not kind and not blob.startswith(b"%PDF"):
                    kind, why = "failed", f"not a PDF ({len(blob):,} bytes)"
            except Exception as e:                      # noqa: BLE001
                kind = refusal.classify(e) or "failed"
                why = f"{type(e).__name__}: {e}"
            if kind:
                r["attempts"] = str(int(r["attempts"] or 0) + 1)
                r["error"] = why[:180]
                fail += 1
                print(f"  [{i}] {r['name']}: {kind}: {r['error'][:80]}",
                      flush=True)
                if kind == "refused":
                    # The address saying no. One ends the run.
                    refusal.note("fetch_calendar_archive", r["error"])
                    stopped = "refused"
                    print("\nRefused. Stopping and not coming back today.\n"
                          "python3 netcheck.py says what kind of refusal it "
                          "is without making it worse.")
                    break
                if kind == "missing":
                    # Listed by the index and not served. Not a refusal and
                    # not worth asking again: the index is where the name
                    # came from, so a 404 is the index being out of date.
                    r["state"] = "gone"
                    time.sleep(a.delay * random.uniform(0.75, 1.25))
                    continue
                if int(r["attempts"]) >= 3:
                    r["state"] = "failed"
                run += 1
                if kind == "dropped":
                    # Accepted and closed without an answer. One is bad
                    # luck; two in a run is this address refusing.
                    dropped += 1
                    if dropped >= 2:
                        refusal.note("fetch_calendar_archive", r["error"])
                        stopped = "refused"
                        print("\nTwo dropped connections this run. Stopping "
                              "and not coming back today.\npython3 "
                              "netcheck.py says what kind of refusal it is "
                              "without making it worse.")
                        break
                if run >= 2:
                    stopped = "two in a row"
                    print("\nTwo in a row. Stopping. netcheck.py says why "
                          "without making it worse.")
                    break
                cool = 120 if kind == "dropped" else a.delay * 3
                print(f"      waiting {cool:.0f}s before the next one",
                      flush=True)
                time.sleep(cool)
                continue
            run = 0
            # A part file, then a rename: a run killed mid-write must not
            # leave half a PDF that path.exists() then calls held.
            tmp = path.with_name(path.name + ".part")
            tmp.write_bytes(blob)
            os.replace(tmp, path)
            r["state"] = "held"
            r["bytes"] = str(len(blob))
            r["error"] = ""
            r["fetched"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            got += 1
            if got % 10 == 0:
                save_queue(rows)
                rate = got / max(1e-9, time.time() - t0)
                print(f"  {i}/{min(len(todo), a.budget)}  {got} fetched, "
                      f"{rate * 60:.0f}/min", flush=True)
            # Jittered, so a run does not arrive on a metronome.
            time.sleep(a.delay * random.uniform(0.75, 1.25))
    finally:
        # The queue is saved however the run ends. The lock is NOT touched
        # here: refusal.hold() releases it, and only if it is this run's own.
        save_queue(rows)
    n_held = sum(1 for x in rows if x["state"] == "held")
    print(f"\n{got:,} fetched, {fail} failed, {time.time() - t0:.0f}s")
    print(f"{n_held:,} of {len(rows):,} held "
          f"({sum(int(x['bytes'] or 0) for x in rows) / 1e6:.0f} MB)")
    left = sum(1 for x in rows if x["state"] == "wanted")
    if left and not stopped:
        print(f"{left:,} still wanted. Run again for the next {a.budget}.")
    if stopped == "refused":
        return 2
    return 1 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
