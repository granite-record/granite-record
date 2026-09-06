#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-06.1
"""
Does the legacy bill status app answer for a whole session year at once?

    python3 probe_legacy.py --year 2019          # ONE request
    python3 probe_legacy.py --year 2019 --raw    # and keep the page

WHY THIS EXISTS

The public database covers 1989-2016 and 2025-2026 and has nothing at all for
2017-2024. Those eight years are wanted -- bill numbers, titles, dockets and
status, with links out to the General Court for the rest.

fetch_bill_status.py already talks to the legacy app for the current term:

    /bill_status/legacy/bs2016/Bill_status.aspx
        ?lsr=<n>&sy=<year>&sortoption=billnumber
        &txtsessionyear=<year>&txtbillnumber=<bill>

Two of those parameters -- sortoption and txtsessionyear -- are the fields of
a SEARCH form rather than of a single-bill lookup, and the app is named for
2016, which is where the database's own BillStatusDB era ends. So the question
is whether the same page, asked without an lsr, returns the year's bill LIST.

If it does, eight years cost eight requests. If it does not, they cost one
request per bill per year -- roughly 16,000 -- which is the pattern that got
this address blocked twice and would not be worth it.

WHAT IT WILL NOT DO

One request. One year. It does not sweep years, does not retry, and does not
construct filenames. It reports what came back and stops; nothing is written
unless --raw is given.

This asks one documented endpoint one question with parameters it already
uses. That is a different thing from the directory scan that got this address
blocked, and it is deliberately kept to a single request so it stays that way.
"""

import argparse
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://gc.nh.gov/bill_status/legacy/bs2016/Bill_status.aspx"
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "corrections@graniterecord.org)"}

BILLNO = re.compile(r"\b((?:CACR|HB|SB|HR|SR|HCR|SCR|HJR|SJR)\s?0*\d{1,4})\b", re.I)
ROW = re.compile(r"<tr\b", re.I)
BILLLINK = re.compile(r"billinfo\.aspx\?id=(\d+)[^\"']*", re.I)


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace"), r.status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True,
                    help="a session year with no database coverage, e.g. 2019")
    ap.add_argument("--raw", action="store_true", help="save the page")
    a = ap.parse_args()

    q = urllib.parse.urlencode({"sy": a.year, "txtsessionyear": a.year,
                                "sortoption": "billnumber"})
    url = f"{BASE}?{q}"
    print(f"one request: {url}\n")
    try:
        page, status = get(url)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}. That is an answer: this route does not "
                 f"serve {a.year}.")
    except Exception as e:
        sys.exit(f"{type(e).__name__}: {e}\n"
                 "netcheck.py diagnoses a refusal without making it worse.")

    bills = sorted({re.sub(r"\s+", "", m.group(1)).upper()
                    for m in BILLNO.finditer(page)})
    links = sorted(set(BILLLINK.findall(page)))
    rows = len(ROW.findall(page))
    print(f"HTTP {status}, {len(page):,} chars, {rows:,} table rows")
    print(f"  {len(bills):,} distinct bill numbers on the page")
    print(f"  {len(links):,} billinfo.aspx links")
    if bills:
        print("  first few: " + ", ".join(bills[:12]))
    if a.year in page:
        print(f"  the page does mention {a.year}")

    if a.raw:
        out = Path(f"probe_legacy_{a.year}.html")
        out.write_text(page, encoding="utf-8")
        print(f"\n  wrote {out}")

    print()
    if len(bills) > 50:
        print("A list. Eight missing years are eight requests, and the bill")
        print("numbers and titles for 2017-2024 come from here rather than")
        print("from one request per bill.")
    elif bills:
        print("Something came back, but not a full year. Read the page before")
        print("concluding anything -- rerun with --raw.")
    else:
        print("No bill numbers. This route does not list a year, so 2017-2024")
        print("would cost one request per bill and is not worth it now. The")
        print("architecture should carry a term key regardless, so the years")
        print("can be filled in later without rebuilding anything.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
