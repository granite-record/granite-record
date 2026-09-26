#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-26.1
"""
What each committee's own page adds to the listing: committee_details.json.

    python3 committee_details.py                     # what is on file, and how it joins
    python3 committee_details.py --from-committees   # ONCE: seed it from committees.json

Asks nobody anything. --from-committees reads committees.json on this disk and
writes committee_details.json beside it; nothing here opens a connection.

TWO FILES, BECAUSE TWO WRITERS

committees.json is fetch_committees.py's: the two pages that list the
committees, two requests, for the chair, the vice chair, the aide, the room and
the phone. GitHub's weekly job runs it and swaps the file in whole.

committee_details.json is fetch_committee_details.py's: one request per
committee's own page, 41 of them, for what the listing does not carry -- the
clerk, the committee's purpose under the chamber's rules, and the page's own
roster. A person starts it on the laptop.

Until 26 September the second wrote into the first. So the weekly swap, which
replaces committees.json with what the listing pages say, would have taken the
clerk off 22 committee pages and the purpose off 23 the first Sunday it ran --
every page that had one; committees.json carried 24 clerks and 26 purposes,
some for committees with no page -- and nothing would have failed: a committee
page without a purpose is a page that renders. And the kit's rule is one writer per file -- committees.json is
the night's, so the laptop's details could never have reached the night at all.

THE JOIN

By chamber and the listing's own code: {"H": {"24": {...}}, "S": {"1712":
{...}}}, the two keys every row of committees.json carries and the ones its
address is built from. A name is not a key -- the General Court renames
committees -- and a detail that joins nothing is reported, not dropped
silently, because that is what a renumbering would look like.

WHICH WINS

  clerk, purpose, web_members     only a committee's own page carries these,
                                  so they come from here
  chair, vice_chair, aide,        both pages carry these. committees.json's
  researcher, location, phone     value stands, and this file's fills in only
                                  where the listing has none.

The listing wins the fields both carry because it is the fresher of the two --
GitHub reads it every week, and the detail pages are read when a person runs
the fetch -- so a chair who changes mid-term is on the page within a week
rather than whenever the laptop next asks. It is also the better reading of
the room: on 7 September the detail pages gave four Senate committees
"SH Rm 122-" and "SL Rm Map" where the listing gives "SH Rm 122-123" and
"SL Rm Map Room".

With both files holding what committees.json held on 26 September, the
committee pages come out byte for byte as they did from committees.json alone.
"""

import argparse
import json
import sys
from pathlib import Path

FILE = "committee_details.json"
COMMITTEES = "committees.json"

# Only a committee's own page carries these.
ONLY_HERE = ("clerk", "purpose", "web_members")
# Both pages carry these; the listing's value stands where it has one.
BOTH = ("chair", "vice_chair", "aide", "researcher", "location", "phone")


def _warn(msg):
    print(f"  committee_details: {msg}", file=sys.stderr, flush=True)


def load(path=FILE, quiet=False, strict=False):
    """{chamber: {code: record}} from committee_details.json, or {}.

    For a build, a missing or unreadable file is a warning, never a stopped
    build: the pages are built without the clerk and the purpose, and the
    warning says so. On the nightly's machine the file is in the kit.

    strict is for a writer merging into the file: one that is there and will
    not read stops it, because writing would replace whatever it held with
    only what this run found.
    """
    p = Path(path)
    if not p.exists():
        if not quiet:
            _warn(f"{p} is not here, so the committee pages go without the clerk "
                  "and the purpose unless committees.json still carries them. "
                  "fetch_committee_details.py writes it, and "
                  "`python3 committee_details.py --from-committees` seeds it "
                  "from committees.json without asking anybody.")
        return {}
    why = ""
    try:
        book = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        book, why = None, f"will not read ({type(e).__name__}: {e})"
    if not why and not (isinstance(book, dict) and all(
            isinstance(v, dict) and all(isinstance(r, dict) for r in v.values())
            for v in book.values())):
        why = "is not {chamber: {code: record}}"
    if why:
        if strict:
            raise SystemExit(f"{p} {why}. Not merging into it: writing would "
                             "replace what it holds with only what this run "
                             "found. Move it aside, or mend it, first.")
        _warn(f"{p} {why}; building without it")
        return {}
    return book


def merged(web, details):
    """committees.json's {chamber: [rows]}, each row carrying its details.

    Returns new rows and leaves both arguments as they were. A row whose
    chamber and code are not in `details` comes back as it went in.
    """
    if not isinstance(web, dict):
        return web
    out = {}
    for chamber, rows in web.items():
        if not isinstance(rows, list):
            out[chamber] = rows
            continue
        mine = details.get(chamber) or {}
        new = []
        for r in rows:
            if not isinstance(r, dict):
                new.append(r)
                continue
            d = mine.get(str(r.get("code", "")))
            if not d:
                new.append(r)
                continue
            row = dict(r)
            for k in ONLY_HERE:
                if d.get(k):
                    row[k] = d[k]
            for k in BOTH:
                if not row.get(k) and d.get(k):
                    row[k] = d[k]
            new.append(row)
        out[chamber] = new
    return out


def unjoined(web, details):
    """The details that join no committee in committees.json, as "H24"."""
    have = {(ch, str(r.get("code", ""))) for ch, rows in (web or {}).items()
            if isinstance(rows, list) for r in rows if isinstance(r, dict)}
    return sorted(f"{ch}{code}" for ch, recs in details.items() for code in recs
                  if (ch, code) not in have)


def read(committees=COMMITTEES, details=FILE):
    """committees.json with committee_details.json joined in: what a reader of
    the clerk, the purpose or the room should use, in place of opening
    committees.json itself."""
    p = Path(committees)
    try:
        web = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except ValueError:
        web = {}
    if not isinstance(web, dict) or not web:
        return web if isinstance(web, dict) else {}
    book = load(details)
    lost = unjoined(web, book)
    if lost:
        _warn(f"{len(lost)} committee(s) in {details} match no committee in "
              f"{committees} by chamber and code, so their details are not "
              f"used: {', '.join(lost[:6])}. A code the General Court changed "
              "looks like this; fetch_committee_details.py reads the new one.")
    return merged(web, book)


def fold(book, chamber, row, rec):
    """Put one committee page's parse into `book`, the way the fetch does.

    A field already on file is only replaced by a non-empty one: an empty
    parse must never blank a value that was there.
    """
    code = str(row.get("code", ""))
    entry = book.setdefault(chamber, {}).setdefault(code, {})
    if row.get("name"):
        entry["name"] = row["name"]
    for k, v in rec.items():
        if v:
            entry[k] = v
    return entry


def counts(book):
    """(committees, with a clerk, with a purpose)."""
    recs = [r for v in book.values() for r in v.values()]
    return (len(recs), sum(1 for r in recs if r.get("clerk")),
            sum(1 for r in recs if r.get("purpose")))


def write_details(book, path=FILE):
    """The one place committee_details.json is written. preflight holds every
    build_ and fetch_ script but fetch_committee_details.py to not calling it."""
    ordered = {ch: {code: book[ch][code] for code in sorted(book[ch], key=str)}
               for ch in sorted(book)}
    Path(path).write_text(json.dumps(ordered, indent=2), encoding="utf-8")


def from_committees(web):
    """committee_details.json's shape, from a committees.json that still carries
    the fields fetch_committee_details.py merged into it before 26 September.

    Only the fields only a committee's own page carries: a chair or a room in
    committees.json may be the listing's or the detail page's, and there is no
    telling which, so those stay committees.json's alone.
    """
    book = {}
    for chamber, rows in (web or {}).items():
        if not isinstance(rows, list):
            continue
        for r in rows:
            if not isinstance(r, dict):
                continue
            rec = {k: r[k] for k in ONLY_HERE if r.get(k)}
            if rec:
                fold(book, chamber, r, rec)
    return book


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--from-committees", action="store_true",
                    help="write committee_details.json from committees.json's "
                         "clerk, purpose and web roster. Asks nobody anything.")
    ap.add_argument("--committees", default=COMMITTEES)
    ap.add_argument("--out", default=FILE)
    ap.add_argument("--force", action="store_true",
                    help="--from-committees over an existing committee_details.json")
    a = ap.parse_args()

    cp = Path(a.committees)
    web = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {}

    if not a.from_committees:
        book = load(a.out)
        n, clerk, purp = counts(book)
        print(f"{a.out}: {n} committees, {clerk} with a clerk, {purp} with a purpose")
        if web:
            lost = unjoined(web, book)
            rows = sum(len(v) for v in web.values() if isinstance(v, list))
            print(f"{a.committees}: {rows} committees; "
                  + (f"{len(lost)} details join none of them: {', '.join(lost)}"
                     if lost else "every detail joins one of them"))
        return 0

    if not web:
        print(f"NOT WRITING {a.out}: {cp} is not here or holds nothing.")
        return 1
    out = Path(a.out)
    if out.exists() and not a.force:
        # One-time: a fetched file is newer than anything committees.json can
        # give it, and this would put the older values back over it.
        print(f"NOT WRITING {out}: it is already here. This seeds it once, from "
              f"{cp}; after that fetch_committee_details.py keeps it. --force "
              "writes over it anyway.")
        return 1
    book = from_committees(web)
    n, clerk, purp = counts(book)
    if not (clerk or purp):
        # SILENCE IS NOT SUCCESS. A committees.json the weekly job has already
        # swapped in carries neither, and seeding from it would write a file
        # that says every committee has no clerk and no purpose.
        print(f"NOT WRITING {out}: no committee in {cp} carries a clerk or a "
              "purpose, so there is nothing to seed from. That is what "
              "committees.json looks like after GitHub's weekly job; run "
              "fetch_committee_details.py instead, with the person's go-ahead.")
        return 1
    write_details(book, out)
    print(f"-> {out}: {n} committees, {clerk} with a clerk, {purp} with a purpose, "
          f"from {cp}. Nothing was asked of anybody.")
    print("Then `python3 cloud.py seed-kit`, so the nightly's kit carries it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
