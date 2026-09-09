#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.2
"""
The text of every archived bill, two requests at a time and never in a hurry.

    python3 fetch_archive_text.py --discover        # does text exist that far back?
    python3 fetch_archive_text.py --budget 200      # fetch, then stop
    python3 fetch_archive_text.py --term 2015-2016 --budget 500

WHY TWO REQUESTS

billText.aspx is keyed by a text id -- billText.aspx?id=143&txtFormat=html&sy=2025
-- and nothing on this disk holds that id for an archived bill. Checked, before
any of this was written:

  db/Docket.psv          legislationid is 0 for every row from 1989 to 2016
  db/Legislation.psv     2025 and 2026 only
  LegislationText        one SessionID, 6,825 rows, the current term alone
  NHLegislatureDB2       nothing publicuser can see
  PublicNHLMS            nothing publicuser can see

The id is not derivable either: for 2025 it is a small dense sequence and for
2023 it is the sequence and the year concatenated, so the scheme has changed
at least once and guessing it would mean asking this server for thousands of
addresses that do not exist. That is what got this address blocked the first
time.

So the id is READ rather than guessed, off the bill's own status page, which
is keyed by lsr and session year -- both of which every archived bill in
data/bills.json already carries. Two requests per bill, no guesses in either.

WHY --discover COMES FIRST

31,449 archived bills at two requests each is 63,000 requests, and at fifteen
seconds apart that is eleven days. Before spending them it is worth knowing
which years have any digital text at all: the docket goes back to 1989, and
the text almost certainly does not. --discover samples a handful of bills from
each term and reports which terms carry a text link, so the run that follows
asks only for what exists.

GENTLE BY CONSTRUCTION

One worker holding archive/.lock, fifteen seconds between requests, a --budget
that stops the run, a queue on disk so a stopped run resumes exactly where it
was, and --stop-refused: a RemoteDisconnected, 403 or 429 is this address
being told no, and two of them end the run. Nothing already on disk is asked
for again.
"""

import argparse
import csv
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

STATUS = "https://gc.nh.gov/bill_status/legacy/bs2016/Bill_status.aspx"
TEXT = "https://gc.nh.gov/bill_status/legacy/bs2016/billText.aspx"
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "corrections@graniterecord.org)"}

QUEUE = Path("archive/text_queue.csv")
LOCK = Path("archive/.lock")
STATUS_CACHE = Path("status_pages_archive")
TEXT_CACHE = Path("bill_text_archive")
FIELDS = ["term", "bill", "year", "lsr", "state", "text_id", "bytes", "note"]

# billText.aspx?id=143&txtFormat=pdf&sy=2025 -- the id is what is wanted, and
# the format is switched to html because pdf is a link a phone downloads and a
# screen reader cannot read.
TEXT_LINK = re.compile(r"billText\.aspx\?[^\"'\s>]*?\bid=(\d+)", re.I)
NL = chr(10)


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace"), None
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        return None, e


def refusal(err):
    """True when the server is saying no rather than failing."""
    why = f"{type(err).__name__}: {err}"
    return any(k in why for k in ("RemoteDisconnected", "ConnectionReset",
                                  "403", "429")), why


def status_url(bill, year, lsr):
    return STATUS + "?" + urllib.parse.urlencode({
        "lsr": lsr, "sy": year, "sortoption": "billnumber",
        "txtsessionyear": year, "txtbillnumber": bill.lower()})


def text_url(text_id, year):
    return TEXT + "?" + urllib.parse.urlencode({
        "id": text_id, "txtFormat": "html", "sy": year})


# ------------------------------------------------------------------ the queue

def build_queue(bills, skip_terms):
    rows = []
    for term in sorted(bills):
        if term in skip_terms:
            continue
        for bill in sorted(bills[term]):
            rec = bills[term][bill]
            yr, lsr = rec.get("lsr_year"), rec.get("lsr_num")
            if not yr or not lsr:
                continue
            rows.append({"term": term, "bill": bill.upper(), "year": str(yr),
                         "lsr": str(lsr), "state": "wanted", "text_id": "",
                         "bytes": "", "note": ""})
    return rows


def read_queue():
    if not QUEUE.exists():
        return None
    with QUEUE.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_queue(rows):
    QUEUE.parent.mkdir(exist_ok=True)
    tmp = QUEUE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(QUEUE)


# ------------------------------------------------------------------ the work

def one_bill(row, delay, timeout, counts):
    """Advance one bill as far as it goes. Returns (requests, refused_why)."""
    made = 0
    bill, yr, lsr = row["bill"], row["year"], row["lsr"]

    # -- stage one: the status page, for the text id --------------------------
    sp = STATUS_CACHE / f"{yr}_{lsr}_{bill}.html"
    if not row.get("text_id"):
        if sp.exists():
            page = sp.read_text(encoding="utf-8", errors="replace")
        else:
            time.sleep(delay)
            page, err = get(status_url(bill, yr, lsr), timeout)
            made += 1
            if page is None:
                is_ref, why = refusal(err)
                row["note"] = why[:90]
                if is_ref:
                    return made, why
                row["state"] = "failed"
                counts["status failed"] += 1
                return made, None
            sp.parent.mkdir(exist_ok=True)
            sp.write_text(page, encoding="utf-8")
        m = TEXT_LINK.search(page)
        if not m:
            # NOT A FAILURE. An older bill can have a status page and no text
            # on the site at all, and recording that is how the next run knows
            # not to ask again.
            row["state"] = "no text"
            counts["no text link"] += 1
            return made, None
        row["text_id"] = m.group(1)

    # -- stage two: the text itself -------------------------------------------
    tp = TEXT_CACHE / row["term"] / f"{bill}.html"
    if tp.exists():
        row["state"] = "held"
        row["bytes"] = str(tp.stat().st_size)
        counts["already held"] += 1
        return made, None
    time.sleep(delay)
    body, err = get(text_url(row["text_id"], yr), timeout)
    made += 1
    if body is None:
        is_ref, why = refusal(err)
        row["note"] = why[:90]
        if is_ref:
            return made, why
        row["state"] = "failed"
        counts["text failed"] += 1
        return made, None
    tp.parent.mkdir(parents=True, exist_ok=True)
    tp.write_text(body, encoding="utf-8")
    row["state"] = "held"
    row["bytes"] = str(len(body.encode("utf-8")))
    counts["fetched"] += 1
    return made, None


# ------------------------------------------------------------------ discovery

def discover(bills, per_term, delay, timeout, stop_refused):
    """Which terms have any digital text at all."""
    rng = random.Random(11)
    found = {}
    refused = 0
    for term in sorted(bills, reverse=True):
        names = sorted(bills[term])
        picks = rng.sample(names, min(per_term, len(names)))
        hits = tried = 0
        for bill in picks:
            rec = bills[term][bill]
            yr, lsr = str(rec.get("lsr_year") or ""), str(rec.get("lsr_num") or "")
            if not yr or not lsr:
                continue
            sp = STATUS_CACHE / f"{yr}_{lsr}_{bill.upper()}.html"
            if sp.exists():
                page = sp.read_text(encoding="utf-8", errors="replace")
            else:
                time.sleep(delay)
                page, err = get(status_url(bill, yr, lsr), timeout)
                if page is None:
                    is_ref, why = refusal(err)
                    if is_ref:
                        refused += 1
                        print(f"  refused: {why}", flush=True)
                        if refused >= stop_refused:
                            print(NL + "Two refusals. Stopping discovery here; "
                                  "what it learned is below.", flush=True)
                            return found
                        time.sleep(120)
                    continue
                sp.parent.mkdir(exist_ok=True)
                sp.write_text(page, encoding="utf-8")
            tried += 1
            if TEXT_LINK.search(page):
                hits += 1
        found[term] = (hits, tried)
        print(f"  {term}: {hits} of {tried} sampled bills link to text",
              flush=True)
    return found


# ------------------------------------------------------------------ the run

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--discover", action="store_true",
                    help="sample a few bills per term and report which terms "
                         "have text at all; fetches no text")
    ap.add_argument("--sample", type=int, default=4,
                    help="bills per term for --discover (default 4)")
    ap.add_argument("--term", help="only this term")
    ap.add_argument("--budget", type=int, default=400,
                    help="requests this run, then stop (default 400)")
    ap.add_argument("--delay", type=float, default=15.0)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--stop-refused", type=int, default=2)
    ap.add_argument("--rebuild-queue", action="store_true")
    ap.add_argument("--status", action="store_true",
                    help="report the queue and stop; no network")
    a = ap.parse_args()

    bills = json.loads(Path("data/bills.json").read_text(encoding="utf-8"))
    # The current term's text is already fetched by fetch_bill_text.py, and
    # 2023-2024's is the next thing that script covers; this is the archive.
    current = max(bills)
    skip = {current}

    if a.status:
        rows = read_queue() or []
        if not rows:
            print("no queue yet; --rebuild-queue writes one")
            return 0
        by = defaultdict(Counter)
        for r in rows:
            by[r["term"]][r["state"]] += 1
        print(f"{'term':11} {'wanted':>7} {'held':>7} {'no text':>8} {'failed':>7}")
        for t in sorted(by):
            c = by[t]
            print(f"{t:11} {c['wanted']:7,} {c['held']:7,} "
                  f"{c['no text']:8,} {c['failed']:7,}")
        tot = Counter()
        for c in by.values():
            tot.update(c)
        print(f"\n{sum(tot.values()):,} bills: " +
              ", ".join(f"{v:,} {k}" for k, v in tot.most_common()))
        return 0

    # ---- one worker -------------------------------------------------------
    # DISCOVERY IS A FETCH TOO. It asks for a status page per sampled bill, so
    # it takes the lock like everything else: two fetches at once is what got
    # this address blocked the second time, and a small run is still a run.
    if LOCK.exists():
        age = (time.time() - LOCK.stat().st_mtime) / 60
        sys.exit(f"archive/.lock is held ({age:.0f} minutes old). Another "
                 "fetch is running, and two at once is what got this address "
                 "blocked. Wait for it.")
    LOCK.parent.mkdir(exist_ok=True)
    LOCK.write_text(str(os.getpid()), encoding="utf-8")
    try:
        if a.discover:
            print(f"sampling {a.sample} bills per term, {a.delay:.0f}s apart. "
                  "No text is fetched.")
            found = discover(bills, a.sample, a.delay, a.timeout,
                             a.stop_refused)
            live = [t_ for t_, (h, n) in sorted(found.items()) if h]
            print(NL + f"{len(live)} of {len(found)} terms sampled carry a "
                  "text link.")
            if live:
                print("  earliest with text: " + min(live))
            return 0

        rows = read_queue()
        if rows is None or a.rebuild_queue:
            rows = build_queue(bills, skip)
            write_queue(rows)
            print(f"queue written: {len(rows):,} archived bills")
        # NEWEST ARCHIVED TERM FIRST. The queue is built in term order, which
        # would spend the first fortnight on 1989 -- the term least likely to
        # have any digital text at all and the one fewest people are looking
        # for. Working backwards from the most recent archived term means the
        # text that lands first is the text most likely to exist and to be
        # read, and a run stopped half way has still bought something.
        todo = [r for r in rows
                if r["state"] == "wanted" and (not a.term or r["term"] == a.term)]
        todo.sort(key=lambda r: (r["term"], r["bill"]), reverse=True)
        if not todo:
            print("nothing wanted. --status says where things stand.")
            return 0

        print(f"{len(todo):,} bills wanted"
              + (f" in {a.term}" if a.term else "")
              + f"; budget {a.budget} requests, {a.delay:.0f}s apart")
        made = 0
        refused = 0
        counts = Counter()
        t0 = time.time()
        for i, row in enumerate(todo, 1):
            if made >= a.budget:
                print(NL + f"stopped at the {a.budget}-request budget.")
                break
            n, why = one_bill(row, a.delay, a.timeout, counts)
            made += n
            if why:
                refused += 1
                if refused >= a.stop_refused:
                    write_queue(rows)
                    sys.exit(
                        f"{NL}{refused} refusals ({why}). Stopping, and not "
                        f"coming back tonight.{NL}"
                        f"  {made:,} requests made, "
                        f"{counts['fetched']:,} texts fetched.{NL}"
                        "  netcheck.py says what kind of refusal it is "
                        "without making it worse.")
                print(f"{NL}  refused ({why}) -- cooling off 120s", flush=True)
                time.sleep(120)
            if i % 25 == 0:
                write_queue(rows)
                rate = made / max(1e-9, time.time() - t0) * 60
                print(f"  {i}/{len(todo)}  {made} requests, "
                      f"{counts['fetched']} texts, {rate:.1f}/min", flush=True)
        write_queue(rows)

        # Silence is not success.
        print(NL + f"{made:,} requests in {(time.time() - t0) / 60:.0f} min")
        for k, v in counts.most_common():
            print(f"  {v:,} {k}")
        if made and not counts["fetched"]:
            print(NL + "NOT ONE text was fetched from those requests. That is "
                  "a parser or an address that stopped working, not a quiet "
                  "night -- look before running it again.")
        return 0
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
