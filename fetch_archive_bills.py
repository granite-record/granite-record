#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-06.3
"""
Every bill of an archived session year, from the General Court's own search.

    python3 fetch_archive_bills.py --file probe_legacy_2024.html   # no network
    python3 fetch_archive_bills.py --year 2024

WHY THIS EXISTS

The public database covers 1989-2016 and 2025-2026 and has nothing at all for
2017-2024, so the eight years in between cannot be queried. They are not
missing from the web: the Advanced Bill Status Search answers a session year
with every bill of that year on one page, and that page carries the title, the
general and per-chamber status, the last committee, the last hearing and the
links a bill cites.

    2023   675 bills
    2024 1,321 bills

TWO REQUESTS A YEAR. That is the point of using this page rather than the
per-bill pages: 1,996 bills of the 2023-2024 term for four requests. This
address has been blocked twice, and the difference between four requests and
four thousand is the difference between a question and a crawl.

WHAT IT DOES NOT GET

Sponsors, and the docket -- the actual sequence of what happened to the bill.
Both are one request per bill, so both are a separate decision with a separate
cost, and neither is guessed at here. Roll calls do not need the web at all:
the database has them for 1999-2026.

WHAT IT WRITES

archive_bills.json, keyed on the term, in the shape bill_status.json uses so
that build_data and build_site_v2 need no new format:

    {"2023-2024": {"HB1001": {"title": ..., "gen_status": ..., "body": ...,
                              "house_status": ..., "senate_status": ...,
                              "lsr": ..., "text_id": ..., "text_pdf": ...,
                              "committee": ..., "last_hearing": ...}}}

--file parses a page already saved by probe_legacy.py --raw and makes no
request, which is how the parser below was written and checked.
"""

import argparse
import html as _html
import json
import re
import refusal
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import proceedings as P

URL = "https://gc.nh.gov/bill_status/legacy/bs2016/"
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}
HIDDEN = re.compile(r"<input\b[^>]*type=[\"']hidden[\"'][^>]*>", re.I)
ATTR = re.compile(r"([\w:-]+)\s*=\s*[\"']([^\"']*)[\"']")

# One bill's block begins with its number in <big> and runs to the next one.
# Read off the saved 2024 page rather than imagined: the number, then Session
# Year, then four links, then a Title and a small table of statuses.
# Each bill block opens with the same cell. 740 of 2024's 1,321 numbers
# carry a fiscal-note suffix -- "HB15 -FN", with the space -- and a pattern
# that stopped at the digits found only the other 581.
BILL_START = re.compile(
    r'<td[^>]*vAlign="top"[^>]*>\s*<big>\s*'
    r"([A-Z]{2,5}\s*\d+(?:\s*-[A-Z]+)*)\s*</big>", re.I)
TITLE = re.compile(r"<b>\s*Title:\s*</b>\s*(.*?)\s*<table", re.I | re.S)
LSR = re.compile(r"bill_docket\.aspx\?lsr=(\d+)&sy=(\d{4})", re.I)
TEXT_ID = re.compile(r"billText\.aspx\?sy=(\d{4})&id=(\d+)", re.I)
# The status rows are <i>G-Status:</i> then the value in the next cell. The
# colour tags around them differ per row and are not part of the meaning.
# The label and the value are in adjacent cells, and each row wraps both in a
# <font> of its own colour, which is decoration and not meaning.
ROW = re.compile(r"<i>\s*(G-Status|House Status|Senate Status|Next/Last Comm|"
                 r"Next/Last Hearing)\s*:?\s*</i>.*?</td>\s*<td[^>]*>(.*?)</td>",
                 re.I | re.S)
TAG = re.compile(r"<[^>]+>")

FIELD = {"g-status": "gen_status", "house status": "house_status",
         "senate status": "senate_status", "next/last comm": "committee",
         "next/last hearing": "last_hearing"}


def text_of(h):
    return re.sub(r"\s+", " ", _html.unescape(TAG.sub(" ", h or ""))).strip()


def parse(page):
    """{bill: record} for every bill on a results page."""
    # The key is the number without its suffix, which is how every other file
    # on this site spells a bill: HB1442, not HB1442-FN-A-LOCAL.
    marks = []
    for m in BILL_START.finditer(page):
        full = re.sub(r"\s+", "", m.group(1)).upper()
        marks.append((m.start(), full.split("-")[0], full))
    out = {}
    for i, (pos, bill, full) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(page)
        chunk = page[pos:end]
        rec = {"bill": bill, "designation": full}
        t = TITLE.search(chunk)
        if t:
            rec["title"] = text_of(t.group(1))
        lsr = LSR.search(chunk)
        if lsr:
            rec["lsr"] = lsr.group(1)
            rec["year"] = lsr.group(2)
        tid = TEXT_ID.search(chunk)
        if tid:
            rec["text_year"], rec["text_id"] = tid.group(1), tid.group(2)
            # The same address the current term's records carry, so a reader
            # gets the document rather than a note that it exists.
            rec["text_pdf"] = (
                "https://gc.nh.gov/bill_status/legacy/bs2016/billText.aspx"
                f"?id={tid.group(2)}&txtFormat=pdf&sy={tid.group(1)}")
        for m in ROW.finditer(chunk):
            key = FIELD.get(m.group(1).strip().lower())
            if key:
                rec[key] = text_of(m.group(2))
        # "HouseMunicipal and County Government" -- the page prints the chamber
        # and the committee in adjacent cells with nothing between them, and
        # flattening the table runs them together. Both chambers have a
        # Finance and a Judiciary, so which one it is has to survive.
        c = re.match(r"(House|Senate)\s*(.+)$", rec.get("committee") or "", re.I)
        if c:
            rec["committee_chamber"] = c.group(1).title()
            rec["committee"] = c.group(2).strip()
        # The chamber a bill started in, from its number. Every prefix the
        # General Court uses is one chamber's.
        rec["body"] = "S" if bill[:1] == "S" else "H"
        if rec.get("title"):
            out[bill] = rec
    return out


def get(url, data=None):
    req = urllib.request.Request(
        url, data=data,
        headers=dict(UA, **({"Content-Type":
                             "application/x-www-form-urlencoded"} if data else {})))
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_year(year):
    """Two requests: load the form, post the year back to it."""
    print(f"  1/2 loading the search form")
    form = get(URL)
    fields = {}
    for m in HIDDEN.finditer(form):
        a = {k.lower(): v for k, v in ATTR.findall(m.group(0))}
        if a.get("name"):
            fields[a["name"]] = _html.unescape(a.get("value", ""))
    fields.update({"txtsessionyear": str(year), "sortoption": "billnumber",
                   "cmdsubmit": "Submit"})
    print(f"  2/2 posting txtsessionyear={year}")
    return get(URL, urllib.parse.urlencode(fields).encode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", help="a session year the database does not have")
    ap.add_argument("--file", help="a results page already saved; no network")
    ap.add_argument("--out", default="archive_bills.json")
    ap.add_argument("--save", action="store_true",
                    help="keep the results page beside the output")
    a = ap.parse_args()
    refusal.check("The bs2016 archive fetch")
    if not (a.year or a.file):
        sys.exit("give --year (two requests) or --file (none).")

    if a.file:
        page = Path(a.file).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"txtsessionyear=(\d{4})", page)
        year = m.group(1) if m else (a.year or "")
        print(f"reading {a.file}, session year {year or 'unknown'}")
    else:
        year = str(a.year)
        print(f"session year {year}, two requests")
        try:
            page = fetch_year(year)
        except urllib.error.HTTPError as e:
            sys.exit(f"  HTTP {e.code}. netcheck.py diagnoses a refusal "
                     "without making it worse.")
        except Exception as e:
            sys.exit(f"  {type(e).__name__}: {e}")
        if a.save:
            Path(f"archive_{year}.html").write_text(page, encoding="utf-8")
            print(f"  saved archive_{year}.html")

    said = re.search(r"Bills\s*Found\s*:\s*(?:&nbsp;|\s)*([\d,]+)", page)
    claimed = int(said.group(1).replace(",", "")) if said else 0
    recs = parse(page)
    print(f"  the page says {claimed:,} bills; parsed {len(recs):,}")
    if claimed and len(recs) < claimed * 0.98:
        sys.exit(f"  parsed {len(recs):,} of {claimed:,}. That is a page whose "
                 "shape has changed, not a session with fewer bills.")

    missing = {k: sum(1 for r in recs.values() if not r.get(k))
               for k in ("title", "lsr", "text_id", "gen_status")}
    for k, n in missing.items():
        if n:
            print(f"    {n:,} bills have no {k}")

    if not year:
        sys.exit("  no session year on the page, so nothing can be keyed.")
    term = P.term_of(year)
    p = Path(a.out)
    out = {}
    if p.exists():
        try:
            out = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            out = {}
    # Merge into the term. A term is two session years and each is one request
    # pair, so the second run must not discard the first.
    into = out.setdefault(term, {})
    before = len(into)
    into.update(recs)
    p.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"  {term}: {before:,} -> {len(into):,} bills -> {a.out}")
    for t in sorted(out):
        print(f"    {t}: {len(out[t]):,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
