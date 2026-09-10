#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-10.2
"""
The bill itself, from an address that can simply be constructed.

    python3 fetch_legislation.py --sample 10 --from 1989 --to 2026
    python3 fetch_legislation.py --parse            # no network; read what is saved

WHY THIS PATH AND NOT THE OTHER ONE

Every archive fetcher here goes through bill_status/legacy/bs2016, which wants
a search, a session and a POST per bill. A person found this instead:

    https://gc.nh.gov/legislation/1989/HB0015.html

It is directly constructible from a year and a zero-padded bill number, and it
carried, in four kilobytes, the two fields five terms of this archive do not
have at all:

    INTRODUCED BY: Rep. Millard of Merrimack Dist. 4
    REFERRED TO:   Commerce, Small Business and Consumer Affairs
    AN ACT repealing certain laws relative to measuring wood.
    ANALYSIS  This bill repeals laws relating to cord dimensions...

Probed across eight years from 1989 to 2017, plus 2021: every one returned a
page.

FETCH ONCE, PARSE MANY TIMES

Pages are saved under legislation/<year>/<BILL>.html and never re-fetched. The
labels move with the decades -- INTRODUCED BY and REFERRED TO in 1989-1993,
SPONSORS: by 2017 -- so the parser will be wrong several times before it is
right, and it must be possible to be wrong without asking the General Court
again. --parse reads the saved pages and touches no network at all.

GENTLE, AND IT STOPS

15 seconds between requests, two refusals end the run, and refusal.py records
one so that it outlives this process and stops every other fetcher for 24
hours. This address has been blocked twice. Nothing else may be fetching from
the General Court while this runs.
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import refusal

OUT = Path("legislation")
URL = "https://gc.nh.gov/legislation/{year}/{bill}.html"
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}

# Padded to four digits, which is what the address wants: HB15 is HB0015.
PAD = re.compile(r"^([A-Z]+)(\d+)$")

# The order a sample should reach for. One of each kind that exists in a year
# beats ten House bills, because the point of sampling is to meet the formats
# rather than to count them.
KIND_ORDER = ["HB", "SB", "CACR", "HR", "SR", "HCR", "SCR", "HJR", "SJR"]


def padded(bid):
    m = PAD.match(bid.strip().upper())
    return f"{m.group(1)}{int(m.group(2)):04d}" if m else None


def sample(bills, per_year, lo, hi):
    """A stratified draw: every kind a year has, before any kind twice."""
    by_year = defaultdict(lambda: defaultdict(list))
    for _term, bs in bills.items():
        for bid, rec in bs.items():
            y = str(rec.get("year") or rec.get("lsr_year") or "")[:4]
            m = PAD.match(bid.strip().upper())
            if y.isdigit() and lo <= int(y) <= hi and m:
                by_year[int(y)][m.group(1)].append(bid)
    picked = {}
    for year in sorted(by_year):
        kinds = by_year[year]
        for k in kinds:
            kinds[k].sort(key=lambda b: int(PAD.match(b).group(2)))
        order = [k for k in KIND_ORDER if k in kinds]
        order += sorted(k for k in kinds if k not in KIND_ORDER)
        out, i = [], 0
        # Round-robin: one of each kind, then a second of each, and so on.
        while len(out) < per_year and any(len(kinds[k]) > i for k in order):
            for k in order:
                if len(out) >= per_year:
                    break
                if len(kinds[k]) > i:
                    out.append(kinds[k][i])
            i += 1
        picked[year] = out
    return picked


def fetch(year, bid, delay):
    """One page, saved. Returns "saved", "cached", "missing" or "refused"."""
    pad = padded(bid)
    if not pad:
        return "skipped"
    f = OUT / str(year) / f"{pad}.html"
    if f.exists() and f.stat().st_size > 200:
        return "cached"
    f.parent.mkdir(parents=True, exist_ok=True)
    url = URL.format(year=year, bill=pad)
    time.sleep(delay)
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            refusal.note("fetch_legislation", f"HTTP {e.code} on {url}")
            return "refused"
        return "missing"
    except (urllib.error.URLError, TimeoutError):
        return "missing"
    f.write_text(body, encoding="utf-8")
    return "saved"


# ------------------------------------------------------------------ parsing

def flatten(html):
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    for ent, ch in (("&#160;", " "), ("&nbsp;", " "), ("&amp;", "&"),
                    ("&quot;", '"'), ("&#39;", "'")):
        t = t.replace(ent, ch)
    return re.sub(r"\s+", " ", t).strip()


# READ OFF THE PAGES, NOT IMAGINED. The first version of this anchored
# everything on "AN ACT", which is what a bill says and what nothing else
# does, so every resolution in the sample yielded a sponsor and no committee
# and no title. Three shapes, from the sample:
#
#   a bill        INTRODUCED BY: ... REFERRED TO: ... AN ACT <title>.
#   a CACR        INTRODUCED BY: ... REFERRED TO: ... RELATING TO: <subject>
#                 PROVIDING THAT: <what it does>
#   a resolution  HOUSE RESOLUTION NO. 1  RESOLVED, that ...
#
# The third has no sponsor and no committee because a House resolution has
# neither. That is the document, not a gap in the parser, and it is recorded
# as such rather than counted as a failure.
#
# STOP is every heading that can follow the one being read. Anchoring on one
# of them is what broke this the first time.
STOP = r"(?:REFERRED TO|AN ACT|RELATING TO|PROVIDING THAT|RESOLVED|ANALYSIS|COMMITTEE:)"

SPONSOR_RE = [
    re.compile(r"INTRODUCED BY:?\s*(.+?)\s*" + STOP, re.I),
    re.compile(r"SPONSORS?:?\s*(.+?)\s*" + STOP, re.I),
]
COMMITTEE_RE = [
    re.compile(r"REFERRED TO:?\s*(.+?)\s*" + STOP, re.I),
    re.compile(r"COMMITTEE:?\s*(.+?)\s*" + STOP, re.I),
]
TITLE_RE = [
    re.compile(r"\bAN ACT\s+(.+?)(?:\s+SPONSORS?:|\s+COMMITTEE:|"
               r"\s+ANALYSIS\b|\.\s)", re.I),
    # A CACR states a subject and then what it would do. Both are the title.
    re.compile(r"RELATING TO:?\s*(.+?)\s*(?:ANALYSIS|EXPLANATION|$)", re.I),
    re.compile(r"RESOLVED,?\s*(.+?)(?:\.\s|$)", re.I),
]
ANALYSIS_RE = re.compile(r"\bANALYSIS\b\s*(.+?)(?:\s*EXPLANATION\b|$)", re.I)

# A kind that has no sponsor and no committee by its nature. A simple
# resolution of one chamber is adopted by that chamber; nobody is referred to
# and the page names no sponsor.
NO_SPONSOR_KINDS = {"HR", "SR"}


def parse(html):
    flat = flatten(html)
    got = {}
    for rx in SPONSOR_RE:
        m = rx.search(flat)
        if m and len(m.group(1)) < 400:
            got["sponsors"] = m.group(1).strip(" :;.")
            break
    for rx in COMMITTEE_RE:
        m = rx.search(flat)
        if m and len(m.group(1)) < 120:
            got["committee"] = m.group(1).strip(" :;.")
            break
    for rx in TITLE_RE:
        m = rx.search(flat)
        if m and 3 < len(m.group(1)) < 400:
            got["title"] = m.group(1).strip(" .")
            break
    m = ANALYSIS_RE.search(flat)
    if m:
        got["analysis"] = m.group(1).strip()[:600]
    got["_chars"] = len(flat)
    return got


def report():
    """What is on disk, and what the parser makes of it, by year and kind."""
    if not OUT.is_dir():
        sys.exit(f"No {OUT}/. Fetch a sample first.")
    rows = []
    for f in sorted(OUT.rglob("*.html")):
        year = f.parent.name
        bid = f.stem
        kind = (PAD.match(bid) or re.match(r"([A-Z]+)", bid)).group(1)
        rows.append((int(year), kind, bid, parse(f.read_text(
            encoding="utf-8", errors="replace"))))
    if not rows:
        sys.exit(f"{OUT}/ holds no pages yet.")
    print(f"{len(rows):,} saved pages, {len({r[0] for r in rows})} years, "
          f"{len({r[1] for r in rows})} kinds")
    print()
    FIELDS = ["sponsors", "committee", "title", "analysis"]
    print(f"{'era':12}{'pages':>7}" + "".join(f"{f:>11}" for f in FIELDS))
    for lo in range(1989, 2027, 4):
        hi = lo + 3
        era = [r for r in rows if lo <= r[0] <= hi]
        if not era:
            continue
        line = f"{lo}-{str(hi)[2:]:2}{'':6}{len(era):>7}"
        for fld in FIELDS:
            n = sum(1 for r in era if r[3].get(fld))
            line += f"{n:>7}/{len(era):<3}"
        print(line)
    print()
    print(f"{'kind':12}{'pages':>7}" + "".join(f"{f:>11}" for f in FIELDS))
    for kind in sorted({r[1] for r in rows},
                       key=lambda k: -sum(1 for r in rows if r[1] == k)):
        ks = [r for r in rows if r[1] == kind]
        line = f"{kind:12}{len(ks):>7}"
        for fld in FIELDS:
            n = sum(1 for r in ks if r[3].get(fld))
            line += f"{n:>7}/{len(ks):<3}"
        print(line)
    # The ones a parser must be shown, not told about.
    # A House or Senate resolution names no sponsor because it has none.
    # Counting those as parser misses would bury the real ones.
    expected = [r for r in rows
                if not r[3].get("sponsors") and r[1] in NO_SPONSOR_KINDS]
    if expected:
        print()
        print(f"{len(expected)} pages have no sponsor because their kind has "
              "none (" + ", ".join(sorted(NO_SPONSOR_KINDS)) + "); not a miss.")
    blank = [r for r in rows if not r[3].get("sponsors")
             and r[1] not in NO_SPONSOR_KINDS]
    if blank:
        print()
        print(f"{len(blank)} pages yielded no sponsor and should have. "
              "First few:")
        for r in blank[:6]:
            print(f"    {r[0]} {r[2]:10} {r[3].get('_chars', 0):>7,} chars  "
                  + (r[3].get("title") or "(no title either)")[:52])
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=10,
                    help="bills per year, spread across the kinds that year has")
    ap.add_argument("--from", dest="lo", type=int, default=1989)
    ap.add_argument("--to", dest="hi", type=int, default=2026)
    ap.add_argument("--delay", type=float, default=15.0)
    ap.add_argument("--stop-refused", type=int, default=2)
    ap.add_argument("--parse", action="store_true",
                    help="read the saved pages and report; no network")
    a = ap.parse_args()

    if a.parse:
        return report()

    refusal.check("The legislation fetch")
    bills = json.loads(Path("data/bills.json").read_text(encoding="utf-8"))
    picked = sample(bills, a.sample, a.lo, a.hi)
    total = sum(len(v) for v in picked.values())
    print(f"{total:,} bills across {len(picked)} years, {a.delay:g}s apart "
          f"-- about {total * a.delay / 60:.0f} minutes if none are cached")
    print()
    tally, refused = Counter(), 0
    for year in sorted(picked):
        line = []
        for bid in picked[year]:
            what = fetch(year, bid, a.delay if tally else 0)
            tally[what] += 1
            line.append(f"{bid}:{what[0]}")
            if what == "refused":
                refused += 1
                if refused >= a.stop_refused:
                    print(f"  {year}: " + " ".join(line))
                    print()
                    print(f"{refused} refusals. Stopping, and refusal.py now "
                          "holds one for 24 hours.")
                    print("python3 netcheck.py says what kind it is without "
                          "making it worse.")
                    return 2
        print(f"  {year}: " + " ".join(line))
    print()
    print(", ".join(f"{v:,} {k}" for k, v in tally.most_common()))
    print(f"-> {OUT}/   then: python3 fetch_legislation.py --parse")
    return 0


if __name__ == "__main__":
    sys.exit(main())
