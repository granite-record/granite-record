#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.1
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

from fetch_committee_reports import (DOCNUM_RE, SEL_DOC, SEL_KIND, SEL_YEAR,
                                     UA, _hidden, _options, extract_text)

INDEX = "https://gc.nh.gov/senate/calendars_journals/"
KIND = "SenateCalendar"
FOLDER = "Calendars"          # capital C; the House's is lower case


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
    ap.add_argument("--delay", type=float, default=2.5)
    ap.add_argument("--cache", default="calendars_senate")
    ap.add_argument("--index", default="calendars.json",
                    help="calendar name -> address, shared with the House's")
    ap.add_argument("--probe", action="store_true",
                    help="list what is offered and download nothing")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    cache = Path(a.cache) / a.year
    cache.mkdir(parents=True, exist_ok=True)

    try:
        urls = calendar_urls(a.year, delay=a.delay)
    except Exception as e:                                   # noqa: BLE001
        sys.exit(f"  could not read the list: {type(e).__name__}: {e}")
    if not urls:
        sys.exit("Nothing listed for that year.")

    if a.probe:
        for num in sorted(urls, key=order):
            print(f"    SC {num}  {urls[num].split('fileName=')[-1]}")
        print("\n--probe: nothing downloaded.")
        return 0

    got, failed, already = 0, [], 0
    for num in sorted(urls, key=order):
        n, suf = order(num)
        local = cache / f"SC{n:03d}{suf}.pdf"
        if local.exists():
            already += 1
        else:
            try:
                req = urllib.request.Request(urls[num], headers=UA)
                with urllib.request.urlopen(req, timeout=120) as r, \
                        open(local, "wb") as fh:
                    shutil.copyfileobj(r, fh)
                got += 1
                print(f"  downloaded SC {num}")
            except Exception as e:                           # noqa: BLE001
                failed.append(f"SC {num}: {type(e).__name__}")
                print(f"  ! SC {num}: {e}")
                # Three in a row is a server refusing, not three bad
                # documents. Stopping is the whole reason this address is
                # still able to fetch anything.
                if len(failed) >= 3:
                    print("\nThree failed. Stopping rather than making more "
                          "requests at a server that is refusing.\n"
                          "python3 netcheck.py says what kind of refusal it is.")
                    break
                time.sleep(a.delay)
                continue
            time.sleep(a.delay)
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
