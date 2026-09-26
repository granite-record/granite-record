#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-26.2
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
page without a purpose is a page that renders. And committees.json is the
night's in the kit: seed-kit sends a file the night owns only while the bucket
has no copy of it, so the laptop's details reached the night at most once, in
the first seed, and no later fetch of them would have.

THE JOIN

By chamber and the listing's own code: {"H": {"24": {...}}, "S": {"1712":
{...}}}, the two keys every row of committees.json carries and the ones its
address is built from. A name is not a key -- the General Court renames
committees -- and a detail that joins nothing is reported, not dropped
silently, because that is what a renumbering would look like. So is a
committee in committees.json with no details at all, which is what one the
General Court added since the last fetch looks like.

WHICH FILE SAYS WHAT

  clerk, purpose, web_members     committee_details.json, and only it
  everything else                 committees.json, and only it

Where committee_details.json is here, it is the ONLY source of the three.
committees.json on the laptop, and the copy the first seed put in the bucket,
still carry the values the fetch merged into it before 26 September, and a
join that let those stand where the details say nothing would make
committees.json a second, hidden source: a clerk taken out of the details
would stay on the page. So the three are taken off every committees.json row
before the details go on. Only where there is no details file at all do the
pages fall back to whatever committees.json carries, and the build says so.

Both pages carry the chair, the vice chair, the aide, the researcher, the room
and the phone, and the details file is not asked for any of them, not even to
fill a gap. The listing is the fresher of the two -- GitHub reads it every
week, and the detail pages are read when a person runs the fetch -- so a chair
who changes mid-term is on the page within a week rather than whenever the
laptop next asks. It is also the better reading of the room: on 7 September
the detail pages gave four Senate committees "SH Rm 122-" and "SL Rm Map" where
the listing gives "SH Rm 122-123" and "SL Rm Map Room".

HOW A FETCH CHANGES A RECORD

A committee page that parses as one -- a purpose or a roster came out of it --
replaces that committee's record with exactly what it says, stamped with the
day it was read ("fetched"): a clerk the page no longer names comes off. A
page that failed changes nothing, and one that parsed as nothing a committee
page carries adds what it has and blanks nothing: an empty parse is a parser
that no longer matches, not a committee that lost its clerk. put() is that
rule; fetch_committee_details.py also refuses a run that would take a field
off every committee it read.

With both files holding what committees.json held on 26 September, the
committee pages come out byte for byte as they did from committees.json alone.
"""

import argparse
import json
import os
import sys
from pathlib import Path

FILE = "committee_details.json"
COMMITTEES = "committees.json"

# Only a committee's own page carries these, and only committee_details.json
# gives them to a page.
ONLY_HERE = ("clerk", "purpose", "web_members")


def _warn(msg):
    print(f"  committee_details: {msg}", file=sys.stderr, flush=True)


def load(path=FILE, quiet=False, strict=True, writing=False):
    """{chamber: {code: record}} from committee_details.json; None if absent.

    A missing file is a warning (quiet silences it), never a stopped build:
    the pages are built without the clerk and the purpose, and the warning
    says so. On the nightly's machine the file is in the kit.

    A file that is here and will not read stops the caller (strict, the
    default). Built from, it would take the clerk and the purpose off every
    committee page as quietly as a missing one, while looking like a file
    that is fine; merged into (writing), it would be replaced by only what
    one run found. strict=False is for a caller that writes nothing, like the
    fetch's --probe: it warns and goes on as if nothing were on file.
    """
    p = Path(path)
    if not p.exists():
        if not quiet:
            _warn(f"{p} is not here, so the committee pages go without the "
                  "clerk and the purpose unless committees.json still carries "
                  "them. fetch_committee_details.py writes it, and "
                  "`python3 committee_details.py --from-committees` seeds it "
                  "from committees.json without asking anybody.")
        return None
    why = ""
    try:
        book = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        book, why = None, f"will not read ({type(e).__name__}: {e})"
    if not why and not (isinstance(book, dict) and all(
            isinstance(v, dict) and all(isinstance(r, dict) for r in v.values())
            for v in book.values())):
        why = "is not {chamber: {code: record}}"
    if not why:
        return book
    if not strict:
        _warn(f"{p} {why}; going on as if nothing were on file")
        return {}
    if writing:
        raise SystemExit(f"{p} {why}. Not merging into it: writing would "
                         "replace what it holds with only what this run "
                         "found. Move it aside, or mend it, first.")
    raise SystemExit(
        f"{p} is here and {why}, so the committee pages cannot be given their "
        "clerks and purposes, and building on would drop them as quietly as a "
        "missing file does. Mend it, or put back a good copy -- the laptop's "
        "is the one fetch_committee_details.py keeps, and `python3 cloud.py "
        "seed-kit` sends it to the nightly's kit -- or move it aside to build "
        "without them, which the build then says.")


def merged(web, details):
    """committees.json's {chamber: [rows]}, each row carrying its details.

    `details` is committee_details.json as load() read it, or None when there
    is no such file. With a details file, the clerk, the purpose and the web
    roster come from it alone: they are taken off every committees.json row
    first, so a value committees.json still carries from before 26 September
    cannot stand in for one the details do not have. With None, each row
    keeps whatever committees.json gives it -- the fallback read() warns
    about. No other field is taken from the details.

    Returns new rows and leaves both arguments as they were.
    """
    if not isinstance(web, dict):
        return web
    out = {}
    for chamber, rows in web.items():
        if not isinstance(rows, list):
            out[chamber] = rows
            continue
        if details is None:
            out[chamber] = [dict(r) if isinstance(r, dict) else r for r in rows]
            continue
        mine = details.get(chamber) or {}
        new = []
        for r in rows:
            if not isinstance(r, dict):
                new.append(r)
                continue
            row = {k: v for k, v in r.items() if k not in ONLY_HERE}
            d = mine.get(str(r.get("code", ""))) or {}
            for k in ONLY_HERE:
                if d.get(k):
                    row[k] = d[k]
            new.append(row)
        out[chamber] = new
    return out


def _keys(web):
    return {(ch, str(r.get("code", ""))) for ch, rows in (web or {}).items()
            if isinstance(rows, list) for r in rows if isinstance(r, dict)}


def unjoined(web, details):
    """The details that join no committee in committees.json, as "H24"."""
    have = _keys(web)
    return sorted(f"{ch}{code}" for ch, recs in (details or {}).items()
                  for code in recs if (ch, code) not in have)


def undetailed(web, details):
    """The committees in committees.json with no record in the details."""
    have = {(ch, str(code)) for ch, recs in (details or {}).items()
            for code in recs}
    return sorted(f"{ch}{code}" for ch, code in _keys(web)
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
    if book is not None:
        lost = unjoined(web, book)
        if lost:
            _warn(f"{len(lost)} committee(s) in {details} match no committee "
                  f"in {committees} by chamber and code, so their details are "
                  f"not used: {', '.join(lost[:6])}. A code the General Court "
                  "changed looks like this; fetch_committee_details.py reads "
                  "the new one.")
        bare = undetailed(web, book)
        if bare:
            _warn(f"{len(bare)} committee(s) in {committees} have no record in "
                  f"{details}, so their pages go without a clerk and a "
                  f"purpose: {', '.join(bare)}. A committee the General Court "
                  "added since the last fetch looks like this; "
                  "fetch_committee_details.py reads its page.")
    return merged(web, book)


def fold(book, chamber, row, rec):
    """Add what one committee page gave to its record, blanking nothing.

    For a page that did not parse as a committee's: a field already on file
    is only replaced by a non-empty one, because an empty parse must never
    blank a value that was there.
    """
    code = str(row.get("code", ""))
    entry = book.setdefault(chamber, {}).setdefault(code, {})
    if row.get("name"):
        entry["name"] = row["name"]
    for k, v in rec.items():
        if v:
            entry[k] = v
    return entry


def is_committee_page(rec):
    """Whether a page's parse is a committee page's: a purpose or a roster
    came out of it. Only then is its silence about a clerk an answer."""
    return bool(rec.get("purpose") or rec.get("web_members"))


def put(book, chamber, row, rec, day):
    """One committee page's parse into `book`, the way the fetch does.

    A page that parsed as a committee's replaces the record with exactly what
    it says, and "fetched" is the day it was read: a clerk, a purpose or a
    roster the page no longer names comes off. Anything else adds what it has
    and blanks nothing, and a page that gave nothing at all changes nothing.

    Returns "replaced", "added" or "unchanged".
    """
    if is_committee_page(rec):
        code = str(row.get("code", ""))
        entry = {"name": row["name"]} if row.get("name") else {}
        entry.update({k: v for k, v in rec.items() if v})
        entry["fetched"] = day
        book.setdefault(chamber, {})[code] = entry
        return "replaced"
    if any(rec.values()):
        fold(book, chamber, row, rec)
        return "added"
    return "unchanged"


def counts(book):
    """(committees, with a clerk, with a purpose)."""
    recs = [r for v in (book or {}).values() for r in v.values()]
    return (len(recs), sum(1 for r in recs if r.get("clerk")),
            sum(1 for r in recs if r.get("purpose")))


def write_details(book, path=FILE):
    """The one place committee_details.json is written. preflight holds every
    build_ and fetch_ script but fetch_committee_details.py to not calling it.

    Written beside itself and moved into place, so a write that stops half way
    leaves the file as it was rather than a file that will not read.
    """
    ordered = {ch: {code: book[ch][code] for code in sorted(book[ch], key=str)}
               for ch in sorted(book)}
    p = Path(path)
    tmp = p.with_name(p.name + ".tmp")
    try:
        tmp.write_text(json.dumps(ordered, indent=2), encoding="utf-8")
        os.replace(tmp, p)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


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
                    help="--from-committees over an existing "
                         "committee_details.json")
    a = ap.parse_args()

    cp = Path(a.committees)
    web = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {}

    if not a.from_committees:
        book = load(a.out) or {}
        n, clerk, purp = counts(book)
        print(f"{a.out}: {n} committees, {clerk} with a clerk, "
              f"{purp} with a purpose")
        if web:
            lost = unjoined(web, book)
            bare = undetailed(web, book)
            rows = sum(len(v) for v in web.values() if isinstance(v, list))
            print(f"{a.committees}: {rows} committees; "
                  + (f"{len(lost)} details join none of them: {', '.join(lost)}"
                     if lost else "every detail joins one of them"))
            print(f"  {len(bare)} of them have no details: {', '.join(bare)}"
                  if bare else "  every one of them has details")
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
    print(f"-> {out}: {n} committees, {clerk} with a clerk, {purp} with a "
          f"purpose, from {cp}. Nothing was asked of anybody.")
    print("Then `python3 cloud.py seed-kit`, so the nightly's kit carries it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
