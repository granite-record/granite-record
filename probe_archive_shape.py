#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-07.3
"""
How the General Court's record changes shape as you go back through it.

    python3 probe_archive_shape.py --ids archive_sample_ids.json --years 1989,2000,2016 --limit 6
    python3 probe_archive_shape.py --ids archive_sample_ids.json          # every year on file
    python3 probe_archive_shape.py --report                               # no network

WHY THIS EXISTS

The archive is roughly 2,000 bills a term for nineteen terms. Fetching it is
tens of thousands of requests against somebody else's server, and the one thing
worse than doing that slowly is doing it twice because the parser turned out to
be wrong about 1994.

So: a handful of bills per year, fetched once, kept on disk, and compared. It
answers the questions that decide the whole build -- does Bill_status.aspx
serve a 1989 bill at all; does it carry sponsors that far back; when do the
status vocabularies change; is the LSR number stable; do bill numbers repeat in
the shape proceedings.csv assumes.

WHAT IT DOES NOT DO

It does not add anything to the site. The samples live in archive_samples/ and
nothing in the build reads them. That is deliberate: a term is published when
the whole term is fetched, not when four bills of it are, and a half-populated
year in the search index is worse than an absent one.

GENTLE BY CONSTRUCTION

One request at a time, a delay between each, a hard --limit, and a cache -- a
page already on disk is never asked for again. This address has been blocked
twice; --limit exists so a wrong assumption cannot become an unbounded crawl.
"""

import argparse
import collections
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import refusal
from pathlib import Path

BASE = "https://gc.nh.gov/bill_status/legacy/bs2016/Bill_status.aspx"
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}
OUT = Path("archive_samples")

# What is read out of a page is whatever fetch_bill_status.parse() reads out
# of it -- the parser the real fetch uses. An earlier version of this file
# matched its own patterns instead and reported that no year carries sponsors,
# including years that plainly do. A probe that answers a different question
# from the build is worse than no probe.
FIELDS = ["title", "lsr", "body", "gen_status", "house_status", "senate_status",
          "date_introduced", "floor_date", "committee_code", "chapter", "local",
          "sponsors", "text_id", "text_pdf"]

TAGS = re.compile(r"<[^>]+>")
WS = re.compile(r"[\s ]+")


def flat(html_text):
    """The page as text, for the size and emptiness checks only."""
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_text,
               flags=re.S | re.I)
    return WS.sub(" ", TAGS.sub(" ", t))


def read(html_text):
    """One page through the production parser: {field: True} for what it got."""
    import fetch_bill_status as F
    rec = F.parse(html_text)
    return {k: bool(rec.get(k)) for k in FIELDS}, rec


def get(url, timeout):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace"), None
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        return None, e


def sample_url(year, bill, lsr):
    q = urllib.parse.urlencode({
        "lsr": lsr, "sy": year, "sortoption": "billnumber",
        "txtsessionyear": year, "txtbillnumber": bill.lower()})
    return f"{BASE}?{q}"


def report():
    """What the samples already on disk say, with no network at all."""
    rows = []
    for f in sorted(OUT.rglob("*.html")):
        year, bill = f.parent.name, f.stem
        raw = f.read_text(encoding="utf-8", errors="replace")
        have, rec = read(raw)
        rows.append((year, bill, have, len(flat(raw)), rec))
    if not rows:
        print(f"nothing in {OUT}/ yet. Run without --report to fetch some.")
        return 0

    print(f"{len(rows)} sample pages in {OUT}/\n")
    by_year = collections.defaultdict(list)
    for year, bill, have, n, rec in rows:
        by_year[year].append((bill, have, n, rec))

    keys = list(FIELDS)
    head = "year  n   " + " ".join(f"{k[:9]:>9}" for k in keys)
    print(head)
    print("-" * len(head))
    for year in sorted(by_year):
        items = by_year[year]
        cells = []
        for k in keys:
            hits = sum(1 for _, have, _, _ in items if have[k])
            cells.append(f"{hits}/{len(items)}".rjust(9))
        print(f"{year}  {len(items):<3} " + " ".join(cells))

    print("\nWHERE THE SHAPE CHANGES")
    prev, changes = None, 0
    for year in sorted(by_year):
        sig = tuple(any(have[k] for _, have, _, _ in by_year[year]) for k in keys)
        if prev is not None and sig != prev:
            gained = [k for k, a, b in zip(keys, sig, prev) if a and not b]
            lost = [k for k, a, b in zip(keys, sig, prev) if b and not a]
            bits = []
            if gained:
                bits.append("gains " + ", ".join(gained))
            if lost:
                bits.append("loses " + ", ".join(lost))
            print(f"  {year}: " + "; ".join(bits))
            changes += 1
        prev = sig
    if not changes:
        print("  none -- every year on file carries the same fields")

    print("\nHOW MANY SPONSORS THE PARSER GETS, BY YEAR")
    for year in sorted(by_year):
        ns = [len(rec.get("sponsors") or []) for _, _, _, rec in by_year[year]]
        print(f"  {year}: " + ", ".join(str(x) for x in ns))

    sizes = sorted(n for _, _, _, n, _ in rows)
    print(f"\npage size: {sizes[0]:,} to {sizes[-1]:,} characters, "
          f"median {sizes[len(sizes)//2]:,}")
    empty = [(y, b) for y, b, _, n, _ in rows if n < 900]
    if empty:
        print(f"{len(empty)} page(s) came back nearly empty, which usually means "
              "the bill was not found for that year:")
        for y, b in empty[:8]:
            print(f"    {y} {b}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="archive_sample_ids.json")
    ap.add_argument("--years", help="comma-separated, e.g. 1989,2000,2016")
    ap.add_argument("--per-year", type=int, default=2)
    ap.add_argument("--limit", type=int, default=8,
                    help="hard cap on requests, so a wrong assumption cannot "
                         "become an unbounded crawl")
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--report", action="store_true",
                    help="read what is already on disk and say nothing to the "
                         "server")
    a = ap.parse_args()
    refusal.check("The archive shape probe")

    if a.report:
        return report()

    ids = json.loads(Path(a.ids).read_text(encoding="utf-8"))
    years = ([y.strip() for y in a.years.split(",")] if a.years
             else sorted(ids))
    OUT.mkdir(exist_ok=True)

    todo = []
    for y in years:
        seen = set()
        for rec in ids.get(y, []):
            key = rec["bill"].upper()
            if key in seen:
                continue
            seen.add(key)
            todo.append((y, rec["bill"], rec["lsr"]))
            if len(seen) >= a.per_year:
                break

    print(f"{len(todo)} sample bills across {len(years)} year(s); "
          f"cap {a.limit} requests, {a.delay}s apart")
    fetched = cached = failed = 0
    for y, bill, lsr in todo:
        d = OUT / y
        d.mkdir(exist_ok=True)
        f = d / f"{bill.upper()}.html"
        if f.exists():
            cached += 1
            continue
        if fetched >= a.limit:
            print(f"\nstopped at the {a.limit}-request cap. "
                  "Raise --limit to continue; nothing already on disk is "
                  "asked for again.")
            break
        time.sleep(a.delay)
        html_text, err = get(sample_url(y, bill, lsr), a.timeout)
        fetched += 1
        if html_text is None:
            failed += 1
            print(f"  {y} {bill}: {type(err).__name__} {err}")
            continue
        f.write_text(html_text, encoding="utf-8")
        have, rec = read(html_text)
        got = sum(1 for v in have.values() if v)
        print(f"  {y} {bill}: {len(html_text):,} bytes, {got}/{len(FIELDS)} "
              f"fields, {len(rec.get('sponsors') or [])} sponsors")

    print(f"\n{fetched} fetched, {cached} already on disk, {failed} failed")
    if failed and failed == fetched:
        raise SystemExit(
            "every request failed. Run netcheck.py before trying again -- "
            "this address has been blocked twice.")
    print(f"\nNothing here is on the site. {OUT}/ is for deciding how to build "
          "the\narchive, not for publishing part of it.")
    print("Run with --report to compare what is on disk.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
