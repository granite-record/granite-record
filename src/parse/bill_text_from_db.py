#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-16.3
"""
The text of a bill the web fetch has not read yet, from the General Court's
database: each bill's current printing, for the bills bill_text.json lacks.

    python3 src/parse/bill_text_from_db.py --check   # measure it against the web's records; write nothing
    python3 src/parse/bill_text_from_db.py           # add what bill_text.json lacks

No network. Reads db/Legislation.psv, db/LegislationText.psv, db/_columns.json
and data/bills.json (and db/_manifest.json, where LegislationText is empty);
writes bill_text.json by merging.

WHY

bill_text.json is fetch_bill_text.py's: each bill's page off the General
Court's web server, bill_status/legacy/bs2016/ -- the path its IT office asked
be requested lightly on session days -- and a person's run. So a bill
introduced since the last such run had no text on the site, no search by its
words and no topic read from it, until somebody ran it again; and in January
that is every bill of the new term.

The night takes LegislationText from the database every night
(nightly.TERM_VIEWS), and that view holds every printing of every bill the
term has. This reads each bill's current printing out of it with the very
parser fetch_bill_text uses (bill_page.parse_text), so the record it adds is
the one the web page would have given.

WHAT IT MEASURED (16 October 2026, the dump of 8 September)

Over the 2,234 bills both hold, the printing chosen below, read by
bill_page.parse_text, gives:

  the version the web page served      2,234 of 2,234
  the whole record (bar "chars")       2,192 identical; the other 42 the
                                       same words, differing only where the
                                       dump turned a line break or a "|"
                                       inside the HTML into a space

--check says it again on whatever dump is on disk.

WHICH PRINTING IS CURRENT

The chaptered final version; else the version adopted by both bodies; else
the latest amended printing; else the introduced one. Not simply the latest
stamp: a chaptered bill's "Version adopted by both bodies" is stamped after
its chaptered text (HB 2 of 2025: 09:13 and 14:19 on 23 July), and the web
page serves the chaptered one. The "OLS Release" rows are the amendments the
Office of Legislative Services releases, not printings of the bill, and are
never read.

WHAT IT WRITES, AND WHAT IT NEVER TOUCHES

For each bill of data/bills.json the view holds and bill_text.json has no
web record for: fetch_bill_text's own record shape, with "source":
"database" and "printed", the printing's stamp. It owns those records and
no others: each run replaces them, so a bill amended since keeps up, and a
record without "source": "database" -- one the web fetch wrote -- is never
read for writing, replaced or removed. When fetch_bill_text next reads a
bill's page, its record takes the bill over.

A web record older than the database's current printing is left as it is
and counted by --check: whether the database should replace the web's text
where it is newer is a person's decision, not this script's.

A PRINTING NAMES ITS OWN BILL (16 October 2026, the release review)

A printing is filed under its bill by LegislationID, and the database starts
that id again every term, so a LegislationText of one term beside a
Legislation of the next would file 2026's printings under 2027's bills. The
night no longer installs such a pair (nightly.take_views, together), and this
is the cheap guard behind it: the printing's own heading names its bill ("HB
1442-FN - AS INTRODUCED", as bill_page.parse_text reads it), and a printing
whose heading names another bill, by kind or by number, is skipped and
counted, and the bill's record is left as it stood. Measured on the dump of 8
September: 2,218 of the 2,234 current printings name their own bill and none
another. The other 16 name no number -- the thirteen housekeeping
resolutions, a memorial resolution and SB 400 print no such heading, and SB
290's reads "SB - AS INTRODUCED" -- and say nothing either way, so they are
read as before. With the dump's ids moved one bill along, as a Legislation of
another term would file them, 2,218 were skipped; the 7 still written were
printings whose heading names no number, which this cannot place, and the
night's guard is the one that keeps such a pair out.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import os
import re
from collections import Counter
from datetime import datetime

import bill_page
import freeze_term as FT
import proceedings as P

LEGISLATION = Path("db/Legislation.psv")
TEXT = Path("db/LegislationText.psv")
COLUMNS = Path("db/_columns.json")
BILLS = Path("data/bills.json")
OUT = Path("bill_text.json")
SOURCE = "database"

# The printings a bill can be at, best first (current() says why this order).
CHAPTERED = "CHAPTERED FINAL VERSION"
BOTH_BODIES = "Version adopted by both bodies"
OLS = "OLS Release"
# The bill a heading names, at the start of the line bill_page.VERSION_RE
# matches, and a bill number as the record files it ("HB1442").
HEADING_BILL = re.compile(r"\s*(HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s*0*(\d+)")
BILL_NUMBER = re.compile(r"([A-Z]+)0*(\d+)")


def rows(path, names):
    """Each line of a dumped view as wide as its column list, as a dict. A line
    of another width is a row the dump's "|" rule split or a shape that moved,
    and is counted rather than guessed at."""
    out, odd = [], 0
    with Path(path).open(encoding="utf-8", errors="replace", newline="") as fh:
        for ln in fh:
            f = ln.rstrip("\r\n").split("|")
            if len(f) == len(names):
                out.append(dict(zip(names, f)))
            elif ln.strip():
                odd += 1
    return out, odd


def stamp(r):
    try:
        return datetime.strptime(r.get("DateTimeStamp", "").strip(), "%m/%d/%Y %H:%M:%S")
    except ValueError:
        return datetime.min


def rank(r):
    v = r.get("DocumentVersion", "")
    return (3 if v == CHAPTERED else 2 if v == BOTH_BODIES else
            1 if v.startswith("As Amended") else 0)


def current(printings):
    """The bill's current printing, or None where it has none with HTML."""
    have = [r for r in printings
            if r.get("DocumentVersion") != OLS and r.get("HTMLText", "").strip()]
    return max(have, key=lambda r: (rank(r), stamp(r))) if have else None


def printings(root="."):
    """({term: {bill: (sessionyear, row of its current printing)}}, notes)."""
    root = Path(root)
    cols = json.loads((root / COLUMNS).read_text(encoding="utf-8"))
    leg, odd_l = rows(root / LEGISLATION, cols["Legislation"])
    txt, odd_t = rows(root / TEXT, cols["LegislationText"])
    # A NEW TERM'S PRINTINGS MAY BE NONE YET (16 October 2026). The night now
    # takes a LegislationText that came back with no rows once the term has
    # turned and before its first printing (nightly.TERM_VIEWS), and this step
    # is not optional: a STOP here would have stopped the night's build. A
    # view whose dump counts its query's rows as none (freeze_term.counted_none)
    # has no printing to add, and nothing is; one with lines and none of them
    # as wide as its columns is still a shape that moved.
    none = not txt and FT.counted_none(root / TEXT)
    if not leg or (not txt and not none):
        raise SystemExit(f"STOP: {LEGISLATION} gave {len(leg):,} rows and {TEXT} {len(txt):,} "
                         "as wide as db/_columns.json says. The dump's shape moved; nothing "
                         "written.")
    by_id = {}
    for r in leg:
        bill = r.get("CondensedBillNo", "").replace(" ", "").upper()
        year = r.get("sessionyear", "").strip()
        if bill and year.isdigit():
            by_id[r.get("legislationID", "").strip()] = (bill, year)
    each = {}
    for r in txt:
        b = by_id.get(r.get("LegislationID", "").strip())
        if b:
            each.setdefault(b, []).append(r)
    out = {}
    for (bill, year), ps in each.items():
        r = current(ps)
        if r:
            out.setdefault(P.term_of(year), {})[bill] = (year, r)
    return out, {"odd lines": odd_l + odd_t, "bills": len(by_id),
                 "with a printing": sum(len(v) for v in out.values()), "none yet": none}


def heading_bill(html):
    """The bill a printing's own heading names, as the record files a bill
    ("HB 1442-FN - AS INTRODUCED" -> "HB1442"), or "" where it names none."""
    m = bill_page.VERSION_RE.search(bill_page.strip_chrome(bill_page.text_of(html)))
    h = HEADING_BILL.match(m.group(0)) if m else None
    return f"{h.group(1)}{int(h.group(2))}" if h else ""


def names_another(bill, row):
    """What the printing's heading names, where that is a bill other than
    `bill`, the one it is filed under; else ""."""
    named = heading_bill(row.get("HTMLText", ""))
    m = BILL_NUMBER.fullmatch(bill)
    mine = f"{m.group(1)}{int(m.group(2))}" if m else bill
    return named if named and named != mine else ""


def record(bill, year, row):
    """fetch_bill_text's record of the printing, marked as the database's."""
    rec = bill_page.parse_text(row["HTMLText"], bill, year)
    rec["source"] = SOURCE
    rec["printed"] = stamp(row).isoformat(timespec="seconds")
    return rec


def is_a_bill(rec):
    """fetch_bill_text.is_empty's test: a version, a title or some text."""
    return bool(rec.get("version") or rec.get("title") or len(rec.get("text") or "") >= 200)


def check(root="."):
    """The chosen printing against every web record of the same bill."""
    found, _ = printings(root)
    have = json.loads((Path(root) / OUT).read_text(encoding="utf-8"))
    n, tally, later = 0, Counter(), Counter()
    for term, bills in sorted(found.items()):
        web = {b: w for b, w in (have.get(term) or {}).items() if w.get("source") != SOURCE}
        for bill, w in web.items():
            if bill not in bills:
                tally["web records the database has no printing for"] += 1
                continue
            year, row = bills[bill]
            if names_another(bill, row):
                tally["the printing's own heading names another bill"] += 1
                continue
            rec = record(bill, year, row)
            n += 1
            tally["version the same" if rec.get("version") == w.get("version")
                  else "version differs"] += 1
            diff = sorted(k for k in set(w) | set(rec)
                          if k not in ("chars", "source", "printed") and w.get(k) != rec.get(k))
            if not diff:
                tally["record identical"] += 1
            elif diff == ["text"] and re.findall(r"\w+", w["text"]) == re.findall(r"\w+", rec["text"]):
                tally["same words, other spacing"] += 1
            else:
                tally["differs: " + ", ".join(diff)] += 1
            if rec.get("version") != w.get("version"):
                later[f"{w.get('version')} -> {rec.get('version')}"] += 1
    print(f"{n:,} bills both hold:")
    for k, v in tally.most_common():
        print(f"  {v:>6,}  {k}")
    if later:
        print("where the database's current printing is not the web record's version "
              "(the web record is older, or this chose wrongly):")
        for k, v in later.most_common(8):
            print(f"  {v:>6,}  {k}")
    same = tally["record identical"] + tally["same words, other spacing"]
    return 0 if n and same / n >= 0.98 else 1


def fill(root=".", out=OUT):
    """Add or refresh the database's records; (added, refreshed, kept, said)."""
    root = Path(root)
    found, notes = printings(root)
    bills = json.loads((root / BILLS).read_text(encoding="utf-8"))
    path = root / out
    have = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if have and not P.term_keyed(have):
        raise SystemExit(f"STOP: {out} is not keyed on the term; nothing written.")
    added = refreshed = removed = web = unknown = thin = 0
    other = []
    for term, got in sorted(found.items()):
        known = bills.get(term) or {}
        now = dict(have.get(term) or {})
        for bill, (year, row) in sorted(got.items()):
            prior = now.get(bill)
            if prior and prior.get("source") != SOURCE:
                web += 1
                continue
            named = names_another(bill, row) if bill in known else ""
            if named:
                # Not this bill's printing (the docstring's last section):
                # skipped, and the bill's record left as it stood.
                other.append(f"{bill}'s names {named}")
                continue
            if bill not in known:
                unknown += 1
                rec = None
            else:
                rec = record(bill, year, row)
                if not is_a_bill(rec):
                    thin += 1
                    rec = None
            if rec is None:
                removed += prior is not None
                now.pop(bill, None)
                continue
            if prior != rec:
                added += prior is None
                refreshed += prior is not None
            now[bill] = rec
        # A record of ours whose bill the view no longer prints is the view's
        # to take back: it goes, and a web record is never one of these. A
        # term the view no longer holds at all -- a finished one, after the
        # turn -- is not looked at: its last printings stand.
        for bill in [b for b, r in now.items() if r.get("source") == SOURCE and b not in got]:
            del now[bill]
            removed += 1
        if now:
            have[term] = now
        else:
            have.pop(term, None)
    said = ((f"{TEXT} holds no printing, and its dump counted none: the term's view before its "
             "first printing; " if notes["none yet"] else "")
            + f"{notes['with a printing']:,} bills with a printing in the database; {web:,} have "
            f"the web's record, kept; {added:,} added from the database and {refreshed:,} "
            f"refreshed" + (f"; {removed:,} of its own taken back" if removed else "")
            + (f"; {unknown:,} not in {BILLS}, left out" if unknown else "")
            + (f"; {thin:,} printings with no bill on them, left out" if thin else "")
            + (f"; {len(other):,} printings whose own heading names another bill, skipped "
               f"({', '.join(other[:3])})" if other else "")
            + (f"; {notes['odd lines']:,} lines of another width, unread" if notes["odd lines"] else ""))
    changed = added or refreshed or removed
    if changed:
        part = path.with_name(path.name + ".part")
        part.write_text(json.dumps(have, indent=2), encoding="utf-8")
        os.replace(part, path)
    return added, refreshed, web, said


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="measure the database's printings against the web's records; write nothing")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    if a.check:
        return check()
    before = Path(a.out).read_bytes() if Path(a.out).exists() else None
    added, refreshed, web, said = fill(out=a.out)
    print(said)
    print(f"-> {a.out}" if Path(a.out).exists() and Path(a.out).read_bytes() != before
          else f"{a.out} unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
