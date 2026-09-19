#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.1
"""
Read what unh_survey.py cached. Touches no network, ever.

    python3 unh_parse.py --catalogue     # write data/unh/catalogue.csv
    python3 unh_parse.py --coverage      # which years of which chamber exist
    python3 unh_parse.py --gap           # just the years this site is missing

WHY A SEPARATE SCRIPT

fetch_legislation.py's rule, kept here: a parser must be allowed to be wrong
without costing a request. The titles in this collection are catalogue records
typed by hand over a century of volumes -- "Journal of the honorable senate,
January session of 1927", "Senate journal, 20 April 2006", "New hampshire
general court, journal of the house of representatives, containing the recall
session of November 1, 1995 and the 1996 session" -- and no first pattern
survives all of them. This one may be run a hundred times against the cache.

WHAT A VOLUME IS

Not a session day. A volume is a bound book, and its title says what sittings
are bound into it. That matters more than it looks: reading the series list as
one volume per year says the House has no journal for 1990, 1993 or 1996, and
two of those three are wrong. 1990 is bound into the volume whose title begins
with the special session of December 1989, and 1996 into the one that begins
with the recall session of November 1995. 1993 really is absent.

So this records, per volume, every year the title names, and a coverage table
is built from those rather than from one year per row.
"""

import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path

RAW = Path("archive/unh/raw")
OUT = Path("data/unh")
CATALOGUE = OUT / "catalogue.csv"

ITEM = re.compile(r'<a href="https://scholars\.unh\.edu/senate_house/(\d+)"[^>]*>(.*?)</a>', re.S)
YEAR = re.compile(r"\b(1[78]\d\d|19\d\d|20[0-2]\d)\b")

COLS = ["item", "title", "chamber", "years", "volume", "item_url", "pdf_url"]


def cached_pages(pattern):
    """Every cached body whose URL matches, newest listing first.

    Found through the .meta.json sidecars rather than by file name, because
    the cache names carry a hash of the URL and hard-coding one here would
    break the moment a page is re-fetched under a different query.
    """
    out = []
    for meta in sorted(RAW.glob("*.meta.json")):
        try:
            rec = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            continue
        if re.search(pattern, rec.get("url", "")):
            body = meta.with_name(meta.name[: -len(".meta.json")])
            if body.exists():
                out.append((rec["url"], body))
    return out


def chamber_of(title):
    """house | senate | both | index -- from what the title calls itself."""
    t = title.lower()
    # An index to the journals is a finding aid, not a journal. Checked first
    # because its title names the house and would otherwise pass as one.
    if t.startswith("index to the journal"):
        return "index"
    has_h = "house" in t
    has_s = "senate" in t
    if has_h and has_s:
        return "both"
    if has_h:
        return "house"
    if has_s:
        return "senate"
    return "?"


def volume_of(title):
    """'I', 'two', '' -- whatever the title calls this part, verbatim."""
    m = re.search(r"\bvol(?:ume)?\.?\s+([IVX]+|one|two|three|four|\d+)\b", title, re.I)
    return m.group(1) if m else ""


def years_of(title):
    """Every year the title names, in order. See WHAT A VOLUME IS above."""
    return sorted({int(y) for y in YEAR.findall(title)})


def catalogue():
    rows = []
    seen = {}
    pages = cached_pages(r"/senate_house/(index\.\d+\.html)?$")
    if not pages:
        sys.exit("no listing page is cached; run unh_survey.py --recon first")
    for url, body in pages:
        text = body.read_text(encoding="utf-8", errors="replace")
        for num, raw_title in ITEM.findall(text):
            title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
            title = re.sub(r"\s+", " ", title)
            if title:
                seen[int(num)] = title
    for num in sorted(seen):
        title = seen[num]
        rows.append({
            "item": num,
            "title": title,
            "chamber": chamber_of(title),
            "years": ";".join(str(y) for y in years_of(title)),
            "volume": volume_of(title),
            "item_url": f"https://scholars.unh.edu/senate_house/{num}",
            # Held as a fact about this collection, not a guess: across every
            # pairing printed on the two listing pages the download article id
            # is the item number plus 999. verify_pdf_offset() checks it.
            "pdf_url": ("https://scholars.unh.edu/cgi/viewcontent.cgi"
                        f"?article={num + 999}&context=senate_house"),
        })
    # Silence is not success.
    if not rows:
        sys.exit("the listing pages are cached but no item was read out of them")
    OUT.mkdir(parents=True, exist_ok=True)
    with CATALOGUE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    return rows


def verify_pdf_offset():
    """Is article == item + 999 on every pair the listing pages print?

    Stated as a count rather than asserted. The pairing is read off the
    listing markup, where the download link and the item link sit together.
    """
    pair = re.compile(
        r'href="https://scholars\.unh\.edu/cgi/viewcontent\.cgi\?article=(\d+)&amp;context=senate_house"'
        r'.*?href="https://scholars\.unh\.edu/senate_house/(\d+)"', re.S)
    ok = bad = 0
    examples = []
    for _url, body in cached_pages(r"/senate_house/(index\.\d+\.html)?$"):
        text = body.read_text(encoding="utf-8", errors="replace")
        for article, item in pair.findall(text):
            if int(article) - int(item) == 999:
                ok += 1
            else:
                bad += 1
                examples.append((item, article))
    return ok, bad, examples[:5]


def load():
    if not CATALOGUE.exists():
        return catalogue()
    with CATALOGUE.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def coverage(rows):
    """year -> {chamber: [items]}, from every year each volume's title names."""
    by_year = {}
    for r in rows:
        if r["chamber"] == "index" or not r["years"]:
            continue
        for y in r["years"].split(";"):
            y = int(y)
            for ch in (["house", "senate"] if r["chamber"] == "both" else [r["chamber"]]):
                by_year.setdefault(y, {}).setdefault(ch, []).append(int(r["item"]))
    return by_year


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalogue", action="store_true", help="write data/unh/catalogue.csv")
    ap.add_argument("--coverage", action="store_true", help="year by year, both chambers")
    ap.add_argument("--gap", action="store_true",
                    help="1989-1998 only: what this collection has that the site does not")
    a = ap.parse_args()

    if a.catalogue or not (a.coverage or a.gap):
        rows = catalogue()
        ok, bad, examples = verify_pdf_offset()
        print(f"{len(rows)} volumes -> {CATALOGUE}")
        chambers = {}
        for r in rows:
            chambers[r["chamber"]] = chambers.get(r["chamber"], 0) + 1
        print("  by chamber: " + ", ".join(f"{k} {v}" for k, v in sorted(chambers.items())))
        years = [int(y) for r in rows for y in r["years"].split(";") if y]
        print(f"  years named: {min(years)} to {max(years)}")
        print(f"  pdf address == item + 999: {ok} pairs agree, {bad} do not"
              + (f" -- {examples}" if bad else ""))
        if not (a.coverage or a.gap):
            return
    rows = load()

    if a.coverage:
        by_year = coverage(rows)
        print(f"{'year':>6}  {'house':<16} {'senate':<16}")
        for y in sorted(by_year):
            h = by_year[y].get("house", [])
            s = by_year[y].get("senate", [])
            print(f"{y:>6}  {str(h) if h else '-':<16} {str(s) if s else '-':<16}")
        return

    if a.gap:
        by_year = coverage(rows)
        print("The years this site has bills and hearings for but no journal,")
        print("against what the UNH collection holds. Items are volume numbers.")
        print()
        print(f"{'year':>6}  {'house':<14} {'senate':<14}")
        for y in range(1989, 1999):
            h = by_year.get(y, {}).get("house", [])
            s = by_year.get(y, {}).get("senate", [])
            print(f"{y:>6}  {str(h) if h else 'MISSING':<14} {str(s) if s else 'MISSING':<14}")


if __name__ == "__main__":
    main()
