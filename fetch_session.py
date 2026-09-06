#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.1
"""
Fetch a whole past session from the legacy docket pages.

    python3 fetch_session.py --year 2023 --probe        # look at one page first
    python3 fetch_session.py --year 2023 --limit 25     # try a few
    python3 fetch_session.py --year 2023                # the lot

For any session before the current one there are no bulk files: no LSRs.txt, no
RollCallSummary.txt, no roster. Everything comes from
bill_docket.aspx?lsr=NNNN&sy=YYYY, one bill at a time.

The advanced search does list every bill for a year, but its results are a
WebForms grid with no addressable URL, so it cannot be linked to or fetched
directly. Walking LSR numbers needs no session state and cannot silently miss
anything: every bill has an LSR, LSRs are numbered from 1, and a gap is a gap
rather than a bill hiding behind a search filter.

The walk stops after enough consecutive misses to be confident the session is
exhausted, and every page is cached — a 2023 docket page will never change, so
it is fetched once and the cache becomes the source. Re-parsing later costs
nothing and touches no network.

Writes archive/<session>/pages/*.html and archive/<session>/parsed/bills.json.
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://gc.nh.gov/bill_status/legacy/bs2016/bill_docket.aspx"
UA = {"User-Agent": "granite-record/1.0 (civic transparency archive; "
                    "corrections@graniterecord.org)"}

TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")

BILLNO = re.compile(
    r"\b(HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s*0*(\d{1,4})((?:-[A-Z]+)*)\b", re.I)

DATE_ONLY = re.compile(r"^\s*(\d{1,2}/\d{1,2}/\d{4})\s*$")

SPONSOR = re.compile(
    r"\b(?:Rep|Sen)\.\s*[A-Z][\w'\u2019.\-]+(?:\s+[A-Z][\w'\u2019.\-]+){0,3}"
    r"(?:\s*,?\s*(?:Dist|Hills|Rock|Merr|Straf|Graf|Ches|Belk|Carr|Sull|Coos)"
    r"[.\s]*\d*)?", re.I)


def text_of(html):
    return WS.sub(" ", TAG.sub(" ", html)).strip()


class Rows(HTMLParser):
    """Pull real table rows out.

    Docket descriptions contain dates of their own -- "Introduced 01/05/2023 and
    referred to Ways and Means" -- so splitting flattened text on dates cuts
    actions in half. The rows are an actual table; read it as one.
    """

    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], [], []
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag in ("td", "th"):
            self.in_cell, self.cell = True, []
        elif tag == "tr":
            self.row = []

    def handle_data(self, data):
        if self.in_cell:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.row.append(WS.sub(" ", "".join(self.cell)).strip())
            self.in_cell = False
        elif tag == "tr" and any(c for c in self.row):
            self.rows.append(self.row)
            self.row = []


def get(url, timeout, tries=3):
    last = None
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace"), None
        except Exception as e:
            last = e
            if n < tries - 1:
                time.sleep(2 * (n + 1))
    return None, last


def url_for(lsr, year):
    return BASE + "?" + urllib.parse.urlencode({
        "lsr": f"{int(lsr):04d}", "sy": year, "sortoption": "",
        "txtsessionyear": year})


def parse(html, year):
    """Pull what the page holds. Anything absent comes back empty, not wrong."""
    t = text_of(html)
    rec = {"bill": "", "title": "", "actions": [], "sponsors": [], "chars": len(t)}

    m = BILLNO.search(t)
    if m:
        rec["bill"] = f"{m.group(1).upper()}{int(m.group(2))}"
        rec["suffix"] = (m.group(3) or "").upper()

    if rec["bill"]:
        spaced = re.sub(r"^([A-Z]+)(\d+)$", r"\1\\s*0*\2", rec["bill"])
        tm = re.search(rf"\b{spaced}\b[\s\-\u2013:,]*(?P<t>[a-z(][^.]{{10,300}}\.)",
                       t, re.I)
        if tm:
            rec["title"] = WS.sub(" ", tm.group("t")).strip(" -\u2013:")

    pr = Rows()
    pr.feed(html)
    for row in pr.rows:
        # A docket row is a date cell next to a description cell.
        dm = next((DATE_ONLY.match(c) for c in row[:2] if DATE_ONLY.match(c)), None)
        if not dm:
            continue
        rest = [c for c in row if not DATE_ONLY.match(c) and len(c.strip()) > 5]
        if rest:
            rec["actions"].append({"date": dm.group(1),
                                   "text": max(rest, key=len)[:300]})

    seen = set()
    for s in SPONSOR.finditer(t):
        v = WS.sub(" ", s.group(0)).strip(" ,.")
        if v not in seen:
            seen.add(v)
            rec["sponsors"].append(v)
    return rec


def looks_empty(html, rec):
    """A missing LSR still returns a page. Decide whether it holds a bill."""
    return not rec["bill"] or (not rec["actions"] and not rec["title"])


def probe(year, lsr, timeout):
    u = url_for(lsr, year)
    print(f"fetching {u}\n")
    html, err = get(u, timeout)
    if html is None:
        print(f"FAILED: {type(err).__name__}: {err}")
        return
    rec = parse(html, year)
    t = text_of(html)
    print(f"page: {len(html):,} bytes, {len(t):,} chars of text\n")
    print(f"bill     : {rec['bill'] or '(none found)'}{rec.get('suffix','')}")
    print(f"title    : {rec['title'][:110] or '(none found)'}")
    print(f"sponsors : {', '.join(rec['sponsors'][:6]) or '(none found)'}")
    print(f"actions  : {len(rec['actions'])}")
    for aa in rec["actions"][:8]:
        print(f"    {aa['date']}  {aa['text'][:88]}")
    print("\n--- first 900 characters of page text, for pattern work ---")
    print(t[:900])
    print("\n" + "=" * 62)
    print("If the bill, title and actions above look right, the patterns hold")
    print("for this era and the full run is safe. If sponsors are empty, send")
    print("the text above and the sponsor pattern can be fixed without another")
    print("fetch.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True)
    ap.add_argument("--session", help="term label, e.g. 2023-2024; derived if absent")
    ap.add_argument("--archive", default="archive")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--max-lsr", type=int, default=2600)
    ap.add_argument("--stop-after", type=int, default=60,
                    help="consecutive empty pages before assuming the end")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--timeout", type=float, default=90.0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--probe-lsr", type=int, default=1)
    ap.add_argument("--reparse", action="store_true",
                    help="re-run the parser over cached pages, no network")
    a = ap.parse_args()

    if a.probe:
        probe(a.year, a.probe_lsr, a.timeout)
        return

    yr = int(a.year)
    session = a.session or f"{yr if yr % 2 else yr - 1}-{yr + 1 if yr % 2 else yr}"
    root = Path(a.archive) / session
    pages = root / "pages" / a.year
    pages.mkdir(parents=True, exist_ok=True)
    (root / "parsed").mkdir(parents=True, exist_ok=True)

    bills, empties, fetched, cached, fails = {}, 0, 0, 0, Counter()
    checked = 0
    for lsr in range(a.start, a.max_lsr + 1):
        if a.limit and checked >= a.limit:
            break
        checked += 1
        cpath = pages / f"{lsr:04d}.html"
        if cpath.exists():
            html = cpath.read_text(encoding="utf-8", errors="replace")
            cached += 1
        elif a.reparse:
            continue
        else:
            time.sleep(a.delay)
            html, err = get(url_for(lsr, a.year), a.timeout)
            if html is None:
                fails[f"{type(err).__name__}"] += 1
                continue
            cpath.write_text(html, encoding="utf-8")
            fetched += 1

        rec = parse(html, a.year)
        if looks_empty(html, rec):
            empties += 1
            if empties >= a.stop_after and not a.reparse:
                print(f"\n{empties} consecutive empty pages at LSR {lsr}; "
                      "treating the session as exhausted.")
                break
            continue
        empties = 0
        rec["lsr"] = f"{lsr:04d}"
        rec["year"] = a.year
        rec["session"] = session
        rec["source"] = url_for(lsr, a.year)
        bills[rec["bill"]] = rec

        if len(bills) % 50 == 0:
            print(f"  {len(bills):,} bills, LSR {lsr}, "
                  f"{fetched} fetched / {cached} cached", flush=True)
            (root / "parsed" / "bills.json").write_text(
                json.dumps(bills, indent=2), encoding="utf-8")

    (root / "parsed" / "bills.json").write_text(
        json.dumps(bills, indent=2), encoding="utf-8")

    kinds = Counter(re.match(r"[A-Z]+", b).group(0) for b in bills)
    withtitle = sum(1 for b in bills.values() if b["title"])
    withsp = sum(1 for b in bills.values() if b["sponsors"])
    acts = sum(len(b["actions"]) for b in bills.values())

    print(f"\n{len(bills):,} bills for {a.year} -> {root}/parsed/bills.json")
    print(f"  by type: {dict(kinds)}")
    print(f"  {withtitle:,} with a title, {withsp:,} with sponsors, "
          f"{acts:,} docket actions")
    print(f"  {fetched:,} pages fetched, {cached:,} from cache")
    if fails:
        print(f"  failures: {dict(fails)}")
    if withtitle < len(bills) * 0.9:
        print("\nFewer than 90% have a title. The patterns may not fit this era —")
        print("run --probe on one of the bills that came back bare.")
    if withsp < len(bills) * 0.5:
        print("\nSponsors are mostly missing. That pattern is the least certain")
        print("of the three; --probe output would let it be fixed.")
    print("\nPages are cached permanently. Parser changes can be re-applied with")
    print("--reparse, which touches no network at all.")


if __name__ == "__main__":
    main()
