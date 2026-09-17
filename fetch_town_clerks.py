#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-12.2
"""
The town clerk and the polling place for every town and ward, in one request.

    python3 fetch_town_clerks.py --probe     # what the page answers, saves nothing
    python3 fetch_town_clerks.py             # fetch, parse, write town_clerks.json
    python3 fetch_town_clerks.py --parse     # re-parse what is already saved

NOT THE GENERAL COURT. This asks app.sos.nh.gov, the Secretary of State's
election lookup, and not gc.nh.gov -- so the lane's lock and the 24-hour
refusal in archive/refused.json are about a different server and do not
apply. It is still somebody else's server, and CLAUDE.md's rule stands: a
person starts this, not a script and not an assistant.

ONE REQUEST FOR ALL OF IT. The page at

    https://app.sos.nh.gov/statelistclerkandpolling

is a form whose Search button, pressed with nothing entered, returns the whole
state list -- 331 rows, which is every town and every ward, against the 320
town-ward pages this site builds. Each row carries:

    Town/City | Clerk | Address | Phone | Fax | E-Mail | Town Website
    | State Election Start-End | Local Election Start-End | Polling Place
    | Election Date-Name

WHAT WAS MEASURED BEFORE ANY OF THIS WAS WRITTEN, by opening the page in a
browser:

    clerk name        331 of 331
    phone             331 of 331
    e-mail            330 of 331
    town website      311 of 331
    POLLING PLACE     221 of 331   (67%)
    election hours    221 of 331

The polling place is blank for 110 rows and the page says what to do about it:
"If the polling location is blank contact your city/town clerk." So the town
page prints the clerk and says the list has no polling place rather than
leaving a gap, and build_town_pages.py already does that.

WHY THE CLERK'S DETAILS GO ON THE SITE AT ALL. They are the contact the
Secretary of State publishes for a public office, in a list published for
residents to use. That is the same test officials.json is held to.

WHAT THIS DOES NOT DO. It does not touch the per-address lookup at
app.sos.nh.gov/pollingplacesampleballot, which answers one household at a
time: 331 rows come from one page and there is no reason to ask 331 times,
still less to send somebody's address anywhere.

THE JOIN IS NOT ONE TO ONE, AND THE MERGE IS NOT DECIDED HERE. The two files
ward towns differently: the Secretary of State lists BERLIN WARD 01 and
BERLIN WARD 03, and this site builds one berlin.html, because the General
Court's district files give Berlin a single House district. 331 rows against
320 pages, so some rows match no page and some pages have several rows.
report() prints both counts and names examples rather than averaging them
away.

The tempting fix is to fall back to the bare town for an unmatched ward row,
and it is half right: a town has ONE clerk, so the clerk, phone, e-mail and
website are the same on every ward row and are safe to collapse. The polling
place is not -- that is the whole reason the rows are warded -- and silently
picking ward 1's would tell a ward 3 voter to go to the wrong building. So
nothing is collapsed here. The town page keys strictly, prints what matches,
and says the list has no polling place where it has none; deciding what a
warded town's unwarded page should show is a person's call with a map in
front of them.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://app.sos.nh.gov/statelistclerkandpolling"
RAW = Path("archive/sos_clerks.html")
OUT = Path("town_clerks.json")
AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# The columns, by the header text the page prints. Matched on a substring
# rather than a position, because a column order is not a promise.
WANT = {
    "town": "town/city", "clerk": "clerk", "address": "address",
    "phone": "phone", "email": "mail", "website": "website",
    "state_hours": "state election", "local_hours": "local election",
    "polling_place": "polling place", "election": "election date",
}


def slug(town, ward):
    """The same key build_town_pages.py names its files with.

    Kept in step with that file by test rather than by memory: the towns in
    this list and the pages on disk are compared by --parse, and a key that
    matches nothing is reported instead of silently dropped.
    """
    s = re.sub(r"[^a-z0-9]+", "-", town.lower()).strip("-")
    return f"{s}-ward-{ward}" if ward and str(ward) != "0" else s


def split_ward(name):
    """"BERLIN WARD 01" -> ("Berlin", "1"); "ACWORTH" -> ("Acworth", "")."""
    m = re.match(r"^(.*?)\s+WARD\s+0*(\d+)$", name.strip(), re.I)
    if m:
        return m.group(1).strip().title(), m.group(2)
    return name.strip().title(), ""


def fetch(timeout=60):
    """The page, once. A refusal is reported and nothing is written."""
    req = urllib.request.Request(URL, headers={
        "User-Agent": AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def parse(html):
    """Rows out of the widest table on the page, keyed by header text.

    ASP.NET renders this as one <table>; the parse is deliberately dumb about
    everything else on the page so a redesign of the surrounding chrome does
    not break it. If the headers stop matching, this raises rather than
    returning rows with the wrong columns in them.
    """
    tables = re.findall(r"<table\b.*?</table>", html, re.S | re.I)
    if not tables:
        raise SystemExit("no <table> on the page; the layout has changed")
    tbl = max(tables, key=len)
    rows = re.findall(r"<tr\b.*?</tr>", tbl, re.S | re.I)

    def cells(tr):
        out = []
        for c in re.findall(r"<t[dh]\b.*?</t[dh]>", tr, re.S | re.I):
            txt = re.sub(r"<[^>]+>", " ", c)
            txt = (txt.replace("&nbsp;", " ").replace("&amp;", "&")
                      .replace("&#39;", "'").replace("&quot;", '"'))
            out.append(re.sub(r"\s+", " ", txt).strip())
        return out

    head = None
    for tr in rows:
        c = cells(tr)
        if c and any("polling" in x.lower() for x in c):
            head = [x.lower() for x in c]
            break
    if not head:
        raise SystemExit("no header row naming a polling place; layout changed")

    col = {}
    for key, needle in WANT.items():
        hit = [i for i, h in enumerate(head) if needle in h]
        if hit:
            col[key] = hit[0]
    missing = sorted(set(WANT) - set(col))
    if missing:
        raise SystemExit("the page no longer prints: " + ", ".join(missing))

    out, skipped = {}, 0
    for tr in rows:
        c = cells(tr)
        if len(c) < len(head) or not c[col["town"]]:
            skipped += 1
            continue
        if c[col["town"]].lower() == head[col["town"]]:
            continue
        town, ward = split_ward(c[col["town"]])
        rec = {}
        for key, i in col.items():
            v = c[i].strip()
            # The page writes "Not Applicable" where a town has no fax or no
            # site. That is not a value and should not be printed as one.
            if v and v.lower() not in ("not applicable", "n/a", "-"):
                rec[key] = v
        rec.pop("town", None)
        # Titles, not the shouting the source uses. Names and place names only;
        # e-mail and hours are left exactly as published.
        for k in ("clerk", "address", "polling_place"):
            if rec.get(k):
                rec[k] = rec[k].title()
        if rec.get("website") and not rec["website"].lower().startswith("http"):
            rec["website"] = "https://" + rec["website"].lower()
        rec["town"] = town
        if ward:
            rec["ward"] = ward
        rec["source"] = URL
        out[slug(town, ward)] = rec
    return out, skipped


def report(recs, site=Path("site")):
    n = len(recs)
    have = lambda k: sum(1 for r in recs.values() if r.get(k))
    print(f"  {n} rows")
    for k in ("clerk", "phone", "email", "website", "polling_place",
              "state_hours"):
        print(f"    {k:14} {have(k):4} of {n}")
    # THE JOIN, CHECKED. A file keyed on a slug nothing on disk is named after
    # would render for no town at all and look like a fetch that worked.
    pages = {p.stem for p in (site / "town").glob("*.html")}
    if pages:
        hit = len(pages & set(recs))
        print(f"    matches a built town page: {hit} of {len(pages)} pages, "
              f"{len(set(recs) - pages)} rows matching none")
        miss = sorted(set(recs) - pages)[:6]
        if miss:
            print("      e.g. " + ", ".join(miss))
        if not hit:
            raise SystemExit("not one row matches a town page: the key is wrong")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true",
                    help="fetch and report, write nothing")
    ap.add_argument("--parse", action="store_true",
                    help="re-parse archive/sos_clerks.html, no request")
    a = ap.parse_args()

    if a.parse:
        if not RAW.exists():
            raise SystemExit(f"{RAW} is not on disk; run without --parse first")
        html = RAW.read_text(encoding="utf-8")
        print(f"reading {RAW} ({len(html)//1024} KB), no request made")
    else:
        print(f"one request to {URL}")
        try:
            html = fetch()
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            raise SystemExit(f"the address did not answer: {e}. Nothing "
                             "written. netcheck.py says what kind of refusal "
                             "this is; it is a different host from the one "
                             "the lane fetches.")
        print(f"  {len(html)//1024} KB")
        if not a.probe:
            RAW.parent.mkdir(parents=True, exist_ok=True)
            RAW.write_text(html, encoding="utf-8")
            print(f"  saved {RAW}")

    recs, skipped = parse(html)
    if not recs:
        raise SystemExit("the page parsed to no rows. Nothing written.")
    print(f"  parsed, {skipped} non-data rows skipped")
    report(recs)

    if a.probe:
        print("\n--probe: nothing written. Drop it to write " + str(OUT))
        return
    # 331 rows is the whole state and the count is known. A parse that
    # suddenly yields 40 is a layout change, not a state with 40 towns.
    if len(recs) < 300:
        raise SystemExit(f"only {len(recs)} rows, and the state has 331. "
                         "Refusing to overwrite " + str(OUT))
    OUT.write_text(json.dumps(recs, indent=1, sort_keys=True),
                   encoding="utf-8")
    print(f"\nwrote {OUT} ({len(recs)} towns and wards)")
    print("build_town_pages.py picks it up on the next run with no flag.")


if __name__ == "__main__":
    sys.exit(main())
