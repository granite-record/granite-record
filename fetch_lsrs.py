#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.1
"""
Next session's bill requests, before any of them is a bill.

    python3 fetch_lsrs.py --probe     # what the page offers, saves nothing
    python3 fetch_lsrs.py             # fetch the CSV, save it, write lsrs.json
    python3 fetch_lsrs.py --parse     # re-read what is saved, no network

WHAT AN LSR IS

A Legislative Service Request is the first step in making a law: a legislator
asks the Office of Legislative Services to draft a bill, and the request is
given a number like 2027-0001. At that point it has a title and a prime
sponsor and nothing else -- no text, no committee, no hearing, no vote. When
drafting finishes and the bill is introduced it becomes an HB or an SB and
this file stops being the best record of it.

241 were on file for 2027 when this was written. They are worth publishing
because they are the earliest public sign of what the next session intends to
take up, and nothing else on this site can answer "what is coming" at all.

NOT EVERY REQUEST BECOMES A BILL. The General Court keeps a separate list of
withdrawn ones, and a request can disappear between two runs of this script.
That is a withdrawal, not a fetch error, and `--parse` keeps a request that
has gone rather than dropping it silently: the record that somebody asked for
a bill is true even after they stopped asking.

IT DISCOVERS THE CSV RATHER THAN GUESSING ITS ADDRESS

The search page offers a "Download CSV File" link. This loads that page, reads
the link out of it, and follows it. It does NOT construct the address.

That is not fastidiousness. This project's address has been blocked by the
General Court's firewall twice, and the first time was for asking for
filenames that did not exist. A guessed URL that 404s is exactly that
behaviour. If the link is not on the page, this says so and stops, which is a
report a person can act on rather than a probe somebody else has to absorb.

Two requests, a pause between them, and it identifies itself.
"""

import argparse
import csv
import io
import json
import re
import refusal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SEARCH = "https://gc.nh.gov/lsr_search/"
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}
RAW_PAGE = Path("archive/lsr_search.html")
RAW_CSV = Path("archive/lsrs.csv")
OUT = Path("lsrs.json")
PAUSE = 5.0

# The link that offers the file, by the words on it rather than by its href --
# the words are what the page promises a reader, and the href is what this
# must not assume.
CSV_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>\s*(?:[^<]*\bCSV\b[^<]*)</a>', re.I)

# "2027-0001", the shape of a request number, and the session it belongs to.
LSR_NO = re.compile(r"^\s*(\d{4})-(\d{3,4})\s*$")


def get(url, timeout=60):
    """One request, identified, with a refusal classified rather than guessed."""
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), r.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as e:
        kind = refusal.classify(e)
        if kind == "refused":
            refusal.note("fetch_lsrs", f"HTTP {e.code} from {url}")
            sys.exit(f"  HTTP {e.code}. refusal.py now holds the lane; "
                     "netcheck.py says what kind of refusal it was.")
        sys.exit(f"  HTTP {e.code} from {url}")
    except urllib.error.URLError as e:
        kind = refusal.classify(e)
        if kind == "refused":
            refusal.note("fetch_lsrs", f"{e.reason} from {url}")
            sys.exit(f"  {e.reason}. refusal.py now holds the lane.")
        sys.exit(f"  {e.reason} from {url}")


def find_csv(html):
    """The CSV link's absolute address, or None with nothing assumed."""
    m = CSV_LINK.search(html)
    return urllib.parse.urljoin(SEARCH, m.group(1)) if m else None


def parse_csv(text):
    """The rows, by header name rather than by column position.

    A column order is not a promise, and this file is somebody else's. Every
    field is matched on a substring of its header so that "LSR #", "LSR
    Number" and "LSRNumber" all land in the same place.
    """
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise SystemExit("  the CSV is empty")
    head = [h.strip().lower() for h in rows[0]]

    def col(*names):
        for i, h in enumerate(head):
            if any(n in h for n in names):
                return i
        return None

    ix = {"lsr": col("lsr", "number", "request"), "body": col("body", "chamber", "type"),
          "title": col("title", "subject"), "sponsor": col("sponsor", "prime", "member")}
    missing = [k for k, v in ix.items() if v is None]
    if missing:
        raise SystemExit(
            f"  the CSV has no column for {', '.join(missing)}.\n"
            f"  Its headers are: {rows[0]}\n"
            "  Match them in parse_csv rather than reading by position.")

    out = []
    for r in rows[1:]:
        if not any(x.strip() for x in r):
            continue
        def g(k):
            i = ix[k]
            return r[i].strip() if i < len(r) else ""
        num = g("lsr")
        m = LSR_NO.match(num)
        if not m:
            continue
        out.append({"lsr": num, "session": int(m.group(1)),
                    "body": g("body").upper()[:2] or "",
                    "title": " ".join(g("title").split()),
                    "sponsor": " ".join(g("sponsor").split()),
                    "withdrawn": False})
    if not out:
        raise SystemExit(
            f"  {len(rows)-1} rows and not one carried a request number of the "
            "shape 2027-0001. That is a format change, not an empty session.")
    return out


def merge(new):
    """New rows over old, and a request that has gone is kept and marked.

    A request vanishing between runs is a withdrawal, which is a fact about
    the record rather than a gap in it. Dropping it would make the site
    quietly disagree with what it said last week.
    """
    old = {}
    if OUT.exists():
        try:
            for r in json.loads(OUT.read_text(encoding="utf-8")):
                old[r["lsr"]] = r
        except (ValueError, OSError, KeyError):
            old = {}
    seen = {r["lsr"] for r in new}
    gone = 0
    for k, r in old.items():
        if k not in seen and not r.get("withdrawn"):
            r["withdrawn"] = True
            gone += 1
    merged = {**old, **{r["lsr"]: {**old.get(r["lsr"], {}), **r} for r in new}}
    return [merged[k] for k in sorted(merged)], gone


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true",
                    help="load the search page and report what it offers; save nothing")
    ap.add_argument("--parse", action="store_true",
                    help="re-read the saved CSV; touches no network")
    a = ap.parse_args()
    refusal.check("The LSR fetch")

    if a.parse:
        if not RAW_CSV.exists():
            raise SystemExit(f"  {RAW_CSV} is not here. Run without --parse first.")
        rows = parse_csv(RAW_CSV.read_text(encoding="utf-8", errors="replace"))
        merged, gone = merge(rows)
        OUT.write_text(json.dumps(merged, indent=1), encoding="utf-8")
        print(f"{len(rows)} requests parsed -> {OUT}"
              + (f"; {gone} newly marked withdrawn" if gone else ""))
        return 0

    print(f"asking {SEARCH} for the page that offers the file")
    body, enc = get(SEARCH)
    html = body.decode(enc, "replace")
    RAW_PAGE.parent.mkdir(parents=True, exist_ok=True)
    RAW_PAGE.write_text(html, encoding="utf-8")
    url = find_csv(html)
    if not url:
        raise SystemExit(
            "  no link on that page offers a CSV.\n"
            f"  The page is saved at {RAW_PAGE}; read it and fix CSV_LINK.\n"
            "  Nothing else is asked for -- a guessed address is how this "
            "address was blocked the first time.")
    print(f"  the file is at {url}")
    if a.probe:
        print("  --probe: stopping here, nothing downloaded")
        return 0

    time.sleep(PAUSE)
    raw, enc2 = get(url)
    RAW_CSV.write_bytes(raw)
    print(f"  {len(raw):,} bytes -> {RAW_CSV}")
    rows = parse_csv(raw.decode(enc2, "replace"))
    merged, gone = merge(rows)
    OUT.write_text(json.dumps(merged, indent=1), encoding="utf-8")
    sessions = sorted({r["session"] for r in rows})
    print(f"{len(rows)} requests for {', '.join(str(s) for s in sessions)} -> {OUT}")
    if gone:
        print(f"  {gone} request(s) no longer listed, kept and marked withdrawn")
    print("\nThese are requests, not bills: a title and a prime sponsor, and "
          "nothing else\nuntil one is drafted and introduced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
