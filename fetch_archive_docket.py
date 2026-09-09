#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-07.4
"""
The docket of every bill of an archived term, in Docket.txt's own format.

    python3 fetch_archive_docket.py --term 2023-2024 --limit 10   # try it
    python3 fetch_archive_docket.py --term 2023-2024              # the term
    python3 fetch_archive_docket.py --term 2023-2024 --reparse    # no network

WHY

An archived term has titles, statuses, sponsors and every recorded vote, and no
DOCKET -- the General Court's own line-by-line list of what happened to a bill.
Without it there is no event timeline, no narrative, no committee report
reasoning and no journal citation, so a 2023 bill reads as a title and a status
where a 2025 one reads as a story.

The docket is not in the bulk download for a past session and not in the
database either: Docket holds 1989-2016 and 2025-2026, and 2017-2024 is in
neither. It is on the legacy web page, one bill at a time.

WHAT IT WRITES

Docket_<term>.txt, in exactly the seven-column shape Docket.txt has --

    session|lsr|created|bill|body|description|modified

-- because narrative.py already parses that, and has for every bill of the
current term. Emitting a new shape would mean a second parser for the same
vocabulary, which is the mistake this project has spent a week undoing.

GENTLE BY CONSTRUCTION

One request at a time, fifteen seconds between each, a hard --limit, and a
cache: a page already on disk is never asked for again, so a stopped run
resumes for free and --reparse re-reads the lot with no network at all.

And --stop-refused, which is the one that matters over 7,500 requests. A
RemoteDisconnected, a 403 or a 429 is this address being told no rather than a
flaky link, and two of them end the run with the work so far on disk. This
address has been blocked twice, and both times something kept going after the
first refusal.
"""

import argparse
import html
import json
import re
import refusal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

BASE = "https://gc.nh.gov/bill_status/legacy/bs2016/bill_docket.aspx"
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "corrections@graniterecord.org)"}

# One docket line: three cells, date / body / description.
ROW = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>(?P<date>[^<]*?)</td>\s*"
    r"<td[^>]*>(?P<body>[^<]*?)</td>\s*"
    r"<td[^>]*>(?P<desc>.*?)</td>\s*</tr>", re.S | re.I)
TAGS = re.compile(r"<[^>]+>")
NL = chr(10)
WS = re.compile(r"[\s ]+")


def text(s):
    return WS.sub(" ", html.unescape(TAGS.sub(" ", s))).strip()


def rows_of(page):
    """Every docket line on the page, as (date, body, description)."""
    out = []
    for m in ROW.finditer(page):
        d, b, desc = text(m.group("date")), text(m.group("body")), \
            text(m.group("desc"))
        # The header row, and any row that is not a dated action.
        if not re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", d):
            continue
        if not desc:
            continue
        out.append((d, b, desc))
    return out


def get(url, timeout):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace"), None
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        return None, e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--term", required=True)
    ap.add_argument("--data", default="data")
    ap.add_argument("--cache", default="docket_pages")
    ap.add_argument("--out")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after this many REQUESTS; 0 means the term")
    ap.add_argument("--delay", type=float, default=15.0,
                    help="seconds between requests (default 15)")
    ap.add_argument("--stop-refused", type=int, default=2,
                    help="refusals this run before giving up entirely")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--reparse", action="store_true",
                    help="re-read the cached pages, ask the server nothing")
    ap.add_argument("--seed",
                    help="a Docket-shaped file whose bills are already "
                         "accounted for; its lines are kept and those bills "
                         "are never asked for")
    a = ap.parse_args()

    # A refusal is a fact about the address, so it stops this run even though
    # it was some other run that was told no.
    if not a.reparse:
        refusal.check("The docket fetch")

    bills = json.loads((Path(a.data) / "bills.json").read_text(encoding="utf-8"))
    if a.term not in bills:
        sys.exit(f"data/bills.json has no term {a.term!r}. It holds: "
                 + ", ".join(sorted(bills)))
    todo = sorted(bills[a.term])
    out_path = Path(a.out or f"Docket_{a.term}.txt")
    cache = Path(a.cache)
    cache.mkdir(exist_ok=True)

    print(f"{a.term}: {len(todo):,} bills"
          + (f", capped at {a.limit} requests" if a.limit else "")
          + (", no network" if a.reparse else f", {a.delay}s apart"))

    lines, fetched, cached_n, failed, empty = [], 0, 0, Counter(), 0
    refused = 0

    # A BILL THE DATABASE ALREADY ACCOUNTS FOR IS NOT ASKED FOR AGAIN. The
    # public database's Docket view holds 1989-2014 whole and then stops part
    # way through 2016: 905 of the 2015-2016 term's 1,788 bills are in it and
    # 883 are not. Fetching the term blind would ask this server for 905 pages
    # whose contents are already on this disk -- nearly four hours of load on
    # an address that has been blocked twice, for nothing.
    #
    # So the seed's lines are kept as they are and its bills are skipped. The
    # output is still the whole term in one file, which is what narrative.py
    # wants.
    seeded = set()
    if a.seed:
        sp = Path(a.seed)
        if not sp.exists():
            sys.exit(f"--seed {a.seed} is not here")
        for ln in sp.read_text(encoding="utf-8-sig",
                               errors="replace").splitlines():
            p = ln.split("|")
            if len(p) >= 7 and p[3].strip():
                seeded.add(p[3].strip().upper())
                lines.append(ln)
        print(f"  seeded with {len(lines):,} docket lines covering "
              f"{len(seeded):,} bills, none of which will be asked for")
    for i, bid in enumerate(todo, 1):
        if bid.upper() in seeded:
            continue
        rec = bills[a.term][bid]
        yr, lsr = str(rec.get("lsr_year") or ""), str(rec.get("lsr_num") or "")
        if not yr or not lsr:
            continue
        f = cache / f"{yr}_{lsr}_{bid.upper()}.html"
        if f.exists():
            page = f.read_text(encoding="utf-8", errors="replace")
            cached_n += 1
        elif a.reparse:
            continue
        else:
            if a.limit and fetched >= a.limit:
                print(f"\nstopped at the {a.limit}-request cap. Nothing "
                      "already on disk is asked for again, so raising it "
                      "continues from here.")
                break
            q = urllib.parse.urlencode({
                "lsr": lsr, "sy": yr, "txtsessionyear": yr,
                "txtbillnumber": bid.lower(), "sortoption": "billnumber"})
            time.sleep(a.delay)
            page, err = get(f"{BASE}?{q}", a.timeout)
            fetched += 1
            if page is None:
                failed[type(err).__name__] += 1
                # A REFUSAL IS NOT A FAILURE AMONG OTHERS. A server that
                # accepts the connection and closes it without sending a byte,
                # or answers 403 or 429, is not a flaky link -- it is this
                # address being told no, and it is what being blocked looks
                # like from here. That has happened twice on this project and
                # cost days each time.
                #
                # Everything before this counted failures and kept going.
                # Over 7,500 requests that is the difference between one bad
                # minute and an address that stops being served, so a refusal
                # now ends the run with the work so far written out. Nothing
                # already on disk is asked for again, so starting again later
                # resumes for free.
                why = f"{type(err).__name__}: {err}"
                if any(k in why for k in ("RemoteDisconnected",
                                          "ConnectionReset", "403", "429")):
                    refused += 1
                    if refused >= a.stop_refused:
                        out_path.write_text(NL.join(lines) + NL,
                                            encoding="utf-8")
                        refusal.note("fetch_archive_docket", why)
                        sys.exit(
                            f"{NL}{refused} refusals ({why}). Stopping, and "
                            f"not coming back tonight.{NL}"
                            f"  {fetched:,} fetched this run, {len(lines):,} "
                            f"docket lines written to {out_path}.{NL}"
                            "  netcheck.py says what kind of refusal it is "
                            "without making it worse.")
                    print(f"{NL}  refused ({why}) -- cooling off 120s",
                          flush=True)
                    time.sleep(120)
                continue
            f.write_text(page, encoding="utf-8")

        got = rows_of(page)
        if not got:
            empty += 1
            continue
        for d, body, desc in got:
            # Docket.txt's own columns, so narrative.py needs no second parser.
            # The created and modified stamps are the action's date at midnight:
            # the page states a day and no clock time, and inventing one would
            # be a precision the record does not have.
            lines.append("|".join([
                yr, lsr.zfill(4), f"{d} 12:00:00 AM", bid.upper(),
                body or "H", desc.replace("|", "/"), f"{d} 12:00:00 AM"]))
        if fetched and fetched % 100 == 0:
            print(f"  {i}/{len(todo)}  {fetched} fetched, {cached_n} cached, "
                  f"{len(lines):,} docket lines", flush=True)
            out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Silence is not success: a run that asked for pages and parsed nothing out
    # of them is a parser that stopped matching, and looks identical from the
    # outside to a term with no docket.
    if (fetched or cached_n) and not lines:
        sys.exit(f"\n{fetched + cached_n:,} pages read and NOT ONE docket line "
                 f"parsed out of them. The pages are in {a.cache}/, so "
                 "--reparse re-reads them once the pattern is fixed.")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    bills_seen = len({l.split("|")[3] for l in lines})
    print(f"\n{len(lines):,} docket lines across {bills_seen:,} bills "
          f"-> {out_path}")
    print(f"  {fetched:,} fetched, {cached_n:,} from cache, {empty:,} pages "
          "with no docket line on them")
    if failed:
        print("  failures: " + ", ".join(f"{k} x{v}" for k, v in failed.items()))
    if refused:
        print(f"  {refused} of those were refusals -- the address was told no")
    print("\nSame seven columns as Docket.txt, so narrative.py reads it with "
          "no change:\n  python3 narrative.py --docket "
          f"{out_path} --all --out narratives_{a.term}.json "
          "--members data/legislators.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
