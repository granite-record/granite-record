#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.3
"""
The Senate's calendars, for the veto messages the House's do not carry.

    python3 fetch_senate_calendars.py --year 2026 --probe   # list, download nothing
    python3 fetch_senate_calendars.py --year 2026           # list and download

WHY A SEPARATE SCRIPT

fetch_committee_reports.py fetches the HOUSE calendars and parses House
committee reports out of them. The Senate's committee reports come from the
General Court's database instead -- one query, no PDFs -- so there is nothing
here to parse and threading a --chamber flag through that script would put a
House report parser over Senate documents for no gain.

What the Senate calendars are wanted for is the governor's veto messages. Ten
of the current term's vetoes are Senate bills and ten of the last term's are,
and a veto message is printed in the chamber the bill came from. All twenty
were missing, and extract_vetoes.py has been saying so on every run.

DISCOVERY, NOT GUESSING

The index page is read and its dropdowns are used, the same way
fetch_committee_reports and fetch_journals do it. Nothing is constructed from a
filename convention, because there is no convention -- the Senate's own list
holds both "No 28 August 20 2026.pdf" and "SC 29.pdf" for adjacent editions.
Guessing filenames is what got this address blocked, twice.

The Senate page differs from the House's in three ways, all read off the page
by probe_calendars.py --chamber senate rather than assumed:

    the kind dropdown says SenateCalendar, where the House says Calendar
    the path is Calendars\\<year>\\, with a capital C
    an edition can be named "SC 29.pdf" with no "No" in the value at all,
    though its LABEL still reads "No 29 September 3 2026"

WHAT IT WRITES

calendars_senate/<year>/SC###.pdf and the same name .txt beside it, which is
what extract_vetoes.py reads. Nothing else is touched, and a calendar already
on disk is never asked for again.
"""

import argparse
import json
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import os
import random

import refusal
from fetch_committee_reports import (DOCNUM_RE, SEL_DOC, SEL_KIND, SEL_YEAR,
                                     UA, _hidden, _options, extract_text)

INDEX = "https://gc.nh.gov/senate/calendars_journals/"
KIND = "SenateCalendar"
FOLDER = "Calendars"          # capital C; the House's is lower case

HOLD = None          # set in main(); None when nothing holds archive/.lock


def write_atomically(path, data):
    """A part file, then a rename.

    The download loop wrote straight into the final name with copyfileobj, and
    a run interrupted mid-file left a truncated PDF that `local.exists()` then
    skipped on every later run. A calendar that is half a document is worse
    than one that is absent: absent gets asked again.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def pause(delay):
    """Wait, then check nobody has been refused while we waited."""
    time.sleep(delay * random.uniform(0.75, 1.25) if delay else 0)
    if refusal.MARK.exists():
        return "archive/refused.json is on file"
    if HOLD is not None and not HOLD.still():
        return "the lane holding archive/.lock is gone"
    return ""


def calendar_urls(year, delay=2.0):
    """{number: url} for every Senate calendar of one year, from the index."""
    def fetch(data=None):
        req = urllib.request.Request(
            INDEX, data=data,
            headers=dict(UA, **({"Content-Type":
                                 "application/x-www-form-urlencoded"}
                                if data else {})))
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", errors="replace")

    print(f"  reading the Senate calendar list for {year}")
    page = fetch()
    listed = [v for v, _ in _options(page, SEL_YEAR)]
    if str(year) not in listed:
        print(f"  {year} is not offered; the page lists {listed[0]} back to "
              f"{listed[-1]}")
        return {}

    docs = _options(page, SEL_DOC)
    shown = next((v for v, txt in docs if str(year) in txt), None)
    if not shown:
        fields = _hidden(page)
        fields[SEL_KIND] = KIND
        fields[SEL_YEAR] = str(year)
        fields["__EVENTTARGET"] = SEL_YEAR
        fields["__EVENTARGUMENT"] = ""
        time.sleep(delay)
        page = fetch(urllib.parse.urlencode(fields).encode())
        docs = _options(page, SEL_DOC)

    out = {}
    for value, label in docs:
        if not value or str(year) not in label:
            continue
        # The LABEL is the reliable one. A value can be "SC 29.pdf".
        m = DOCNUM_RE.search(label) or DOCNUM_RE.search(value)
        if not m:
            continue
        key = m.group(1)
        out[int(key) if key.isdigit() else key] = (
            INDEX + "viewer.aspx?fileName="
            + urllib.parse.quote(f"{FOLDER}\\{year}\\{value}"))

    nums = [k for k in out if isinstance(k, int)]
    print(f"  {len(out)} calendars listed for {year}"
          + (f", numbered {min(nums)} to {max(nums)}" if nums else ""))
    return out


def order(k):
    m = re.match(r"(\d+)([A-Za-z]*)", str(k))
    return (int(m.group(1)), m.group(2).upper()) if m else (0, str(k))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True)
    # 20 seconds, not 2.5. This is the address that has blocked this project
    # twice, and the lane's other fetchers ask it every 20-25 seconds.
    ap.add_argument("--delay", type=float, default=20.0)
    ap.add_argument("--budget", type=int, default=0,
                    help="stop after this many requests, so a run always ends")
    ap.add_argument("--stop-refused", type=int, default=2,
                    help="dropped connections that end the run")
    ap.add_argument("--stop-missing", type=int, default=10,
                    help="documents that would not come before stopping")
    ap.add_argument("--cache", default="calendars_senate")
    ap.add_argument("--index", default="calendars.json",
                    help="calendar name -> address, shared with the House's")
    ap.add_argument("--probe", action="store_true",
                    help="list what is offered and download nothing")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    global HOLD

    cache = Path(a.cache) / a.year
    cache.mkdir(parents=True, exist_ok=True)

    # ONE WORKER OR NONE, and not at all while a refusal stands. This script
    # once had neither: it took no lock, so it could run beside the lane as a
    # second worker at this address, and it read no refusal, so it would have
    # carried on through one. It is also the run that met a 403 -- 664
    # calendars of 1998-2008 are still marked "wanted" in archive/queue.csv
    # from that day, each with "HTTP Error 403: Forbidden" against it.
    refusal.check("The Senate calendar fetch")
    with refusal.hold("fetch_senate_calendars") as held:
        HOLD = held
        return _run(a, cache)


def _run(a, cache):
    try:
        urls = calendar_urls(a.year, delay=a.delay)
    except Exception as e:                                   # noqa: BLE001
        kind = refusal.classify(e)
        if kind == "refused":
            refusal.note("fetch_senate_calendars",
                         f"reading the list: {type(e).__name__}: {e}")
            print("REFUSED while reading the list. refusal.py now holds one "
                  "for 24 hours; python3 netcheck.py says what kind it is.")
            return 2
        sys.exit(f"  could not read the list: {type(e).__name__}: {e}")
    if not urls:
        sys.exit("Nothing listed for that year.")

    if a.probe:
        for num in sorted(urls, key=order):
            print(f"    SC {num}  {urls[num].split('fileName=')[-1]}")
        print("\n--probe: nothing downloaded.")
        return 0

    got, failed, already, dropped, spent = 0, [], 0, 0, 0
    for num in sorted(urls, key=order):
        if a.budget and spent >= a.budget:
            print(f"\nbudget of {a.budget} reached. Nothing already on disk is "
                  "asked for again, so the same command carries on from here.")
            break
        n, suf = order(num)
        local = cache / f"SC{n:03d}{suf}.pdf"
        if local.exists():
            already += 1
        else:
            why = pause(a.delay if spent else 0)
            if why:
                print(f"\nStopping: {why}. The record on file is left as it is.")
                break
            spent += 1
            try:
                req = urllib.request.Request(urls[num], headers=UA)
                with urllib.request.urlopen(req, timeout=120) as r:
                    body = r.read()
            except Exception as e:                           # noqa: BLE001
                # One reading of an error for every fetcher in this project:
                # a reset or a timeout wrapped in a URLError is a dropped
                # connection, and a 403, 429, 503 or the firewall's own block
                # page is the address saying no.
                kind = refusal.classify(e)
                why = f"{type(e).__name__}: {e}"
                print(f"  ! SC {num}: {why}")
                if kind == "refused":
                    refusal.note("fetch_senate_calendars", why)
                    print("\nREFUSED. Stopping, and refusal.py now holds one "
                          "for 24 hours.\npython3 netcheck.py says what kind "
                          "it is without making it worse.")
                    return 2
                if kind == "dropped":
                    dropped += 1
                    if dropped >= a.stop_refused:
                        refusal.note("fetch_senate_calendars", why)
                        print(f"\n{dropped} dropped connections -- this "
                              "address's usual way of refusing. Stopping.")
                        return 2
                failed.append(f"SC {num}: {type(e).__name__}")
                # 664 of these are 1998-2007 and some may simply not be
                # served. Ten missing documents is a gap in the record; ten in
                # a row is the address, and the difference matters enough to
                # keep counting them separately from a refusal.
                if len(failed) >= a.stop_missing:
                    print(f"\n{len(failed)} would not come. Stopping for a "
                          "person to look rather than asking further.")
                    break
                continue
            # A BLOCK PAGE IS NOT A CALENDAR, and it arrives with HTTP 200.
            # Saved, it would sit in calendars_senate/ named SC012.pdf and be
            # counted as held for good.
            if refusal.classify(body=body[:4000].decode("utf-8", "replace")) == "refused":
                refusal.note("fetch_senate_calendars", "the block page, with a 200")
                print("\nREFUSED: the firewall's block page, with a 200. "
                      "Stopping.")
                return 2
            if not body.startswith(b"%PDF"):
                failed.append(f"SC {num}: not a PDF")
                print(f"  ! SC {num}: {len(body)} bytes and not a PDF")
                if len(failed) >= a.stop_missing:
                    print(f"\n{len(failed)} would not come. Stopping.")
                    break
                continue
            write_atomically(local, body)
            got += 1
            print(f"  downloaded SC {num}")
        txt = local.with_suffix(".txt")
        if not txt.exists():
            text, _ = extract_text(local)
            if text and len(text) > 500:
                txt.write_text(text, encoding="utf-8")
            else:
                print(f"  ! SC {num}: {len(text or '')} characters of text")
        if a.limit and got >= a.limit:
            break

    # The same index the House calendars use, so a citation resolves either way.
    idx = {}
    ip = Path(a.index)
    if ip.exists():
        try:
            idx = json.loads(ip.read_text(encoding="utf-8"))
        except ValueError:
            idx = {}
    before = len(idx)
    idx.update({f"SC {k} {a.year}": u for k, u in urls.items()})
    idx.update({f"SC {k}": u for k, u in urls.items()})
    assert len(idx) >= before, "the calendar index must not shrink"
    ip.write_text(json.dumps(idx, indent=2, sort_keys=True), encoding="utf-8")

    print(f"\n{got} downloaded, {already} already here, {len(failed)} failed"
          f" -> {cache}/")
    print(f"{len(idx):,} calendar links in {a.index} ({before:,} before)")
    print("\nextract_vetoes.py reads these for the governor's veto messages on "
          "Senate bills.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
