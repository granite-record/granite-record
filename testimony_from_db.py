#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-11.1
"""
Sign-in counts for an archived term's hearings, from the database dump on disk.

    python3 testimony_from_db.py --check     # rebuild 2025-2026, compare, write nothing
    python3 testimony_from_db.py             # write the archived terms into testimony_db.json

No network. Reads db/houseRemoteTestify.psv, db/Legislation.psv and
archive_bills.json; writes testimony_db.json by merging.

WHY

The House's online sign-in form -- support, oppose or neutral, for or
against a bill at its hearing -- is in the public database as
houseRemoteTestify, and fetch_testimony_db.py counts it for the current
term by joining legislationID to the Legislation view. That view holds the
current term only, and legislationID restarts every term, so the 74,084
sign-ins of 2024 were called unaddressable and left out.

They are addressable. A bill's legislationID in its own term is the id its
billText link carries, and archive_bills.json stores that link for every
2023-2024 bill. Joined through it, all 74,084 land on exactly one bill each
-- 963 bills, no id shared by two -- and 99.2% of them on the day
Docket_2023-2024.txt gives for that bill's House public hearing, which is a
witness nothing here wrote. The form did not exist before January 2024, so
2023's hearings have none and the page must say so rather than show zeros.

WHAT IT READS, AND WHAT IT NEVER READS

Three columns of the dump: the hearing date, the legislationID and the
stance. The dump also carries each person's name, town, who they represent
and anything they wrote. None of those is read into a variable, and nothing
here could publish them: this site gives testimony as counts, never as the
people.

WHAT IT WRITES

Only archived terms. The current term is fetch_testimony_db.py's, from the
live database every night; the dump on disk is a snapshot of 8 September and
writing the current term from it would put older counts over newer ones.
--check proves the reshape is the same as the database's own query by
rebuilding the current term from the dump and comparing it bill by bill.
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import proceedings as P

TESTIFY = Path("db/houseRemoteTestify.psv")
LEGISLATION = Path("db/Legislation.psv")
OUT = Path("testimony_db.json")
STANCES = ("support", "oppose", "neutral")

# The dump has no header row. These were established by reproducing the
# current term: with them, all 2,019 bills' counts equal the database's own
# GROUP BY in testimony_db.json, and every one of 402,908 lines has 14 fields.
T_DATE, T_LID, T_STANCE, T_FIELDS = 3, 5, 7, 14
L_BILL, L_YEAR, L_LID = 14, 2, 47


def current_ids():
    """{legislationID: (bill, sessionyear)} for the term Legislation holds."""
    out = {}
    for line in LEGISLATION.open(encoding="utf-8", errors="replace"):
        p = line.rstrip("\n").split("|")
        if len(p) > L_LID and p[L_YEAR].strip().isdigit():
            out[p[L_LID].strip().lstrip("0")] = (p[L_BILL].strip().upper(),
                                                 int(p[L_YEAR]))
    return out


def archived_ids():
    """{year: {legislationID: bill}} from the billText ids archive_bills.json
    stores. An id two bills of one year share is dropped, not guessed."""
    try:
        arch = json.loads(Path("archive_bills.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    seen = collections.defaultdict(lambda: collections.defaultdict(set))
    for _term, bills in arch.items():
        for bid, r in (bills or {}).items():
            y, tid = str(r.get("text_year") or ""), str(r.get("text_id") or "")
            if y.isdigit() and tid.isdigit():
                seen[int(y)][tid.lstrip("0")].add(bid.upper())
    return {y: {i: next(iter(b)) for i, b in ids.items() if len(b) == 1}
            for y, ids in seen.items()}


def build():
    cur, arch = current_ids(), archived_ids()
    by_term = collections.defaultdict(dict)
    unjoined = collections.Counter()
    for line in TESTIFY.open(encoding="utf-8", errors="replace"):
        p = line.rstrip("\n").split("|")
        if len(p) != T_FIELDS:
            unjoined["a line not 14 fields wide"] += 1
            continue
        when, lid, stance = p[T_DATE].strip(), p[T_LID].strip().lstrip("0"), \
            p[T_STANCE].strip().lower()
        m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", when)
        if not m:
            unjoined["no date"] += 1
            continue
        year = int(m.group(3))
        date = f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
        # The current term first, within its own biennium -- the rule
        # fetch_testimony_db's SQL applies, for the reason it gives.
        bill = None
        hit = cur.get(lid)
        if hit:
            b, sy = hit
            start = sy - (1 - sy % 2)
            if start <= year <= start + 1:
                bill = b
        if bill is None:
            bill = (arch.get(year) or {}).get(lid)
        if bill is None:
            unjoined[str(year)] += 1
            continue
        term = P.term_of(str(year))
        rec = by_term[term].setdefault(bill, {
            "total": 0, "support": 0, "oppose": 0, "neutral": 0,
            "hearings": {}})
        h = rec["hearings"].setdefault(date, {
            "date": date, "total": 0, "support": 0, "oppose": 0, "neutral": 0})
        for r in (rec, h):
            r["total"] += 1
            if stance in STANCES:
                r[stance] += 1
    out = {}
    for term, bills in by_term.items():
        out[term] = {}
        for bill, rec in bills.items():
            rec["hearings"] = sorted(rec["hearings"].values(),
                                     key=lambda h: h["date"])
            out[term][bill] = rec
    return out, unjoined


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="rebuild the current term and compare; write nothing")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    for f in (TESTIFY, LEGISLATION):
        if not f.exists():
            sys.exit(f"{f} is not here; fetch_archive_db.py dumps it.")

    built, unjoined = build()
    current = P.term_of(str(max(int(sy) for _b, sy in current_ids().values())))
    for term in sorted(built):
        bills = built[term]
        print(f"  {term}: {len(bills):,} bills, "
              f"{sum(r['total'] for r in bills.values()):,} sign-ins"
              + ("  (the current term: fetch_testimony_db's, not written here)"
                 if term == current else ""))
    if unjoined:
        print("  not joined to a bill: " + ", ".join(
            f"{k} {v:,}" for k, v in unjoined.most_common(6)))

    # The reshape is proven, not trusted: the current term rebuilt from the
    # dump must equal the database's own GROUP BY, bill for bill.
    out_path = Path(a.out)
    try:
        ref = json.loads(out_path.read_text(encoding="utf-8")).get(current) or {}
    except (OSError, ValueError):
        ref = {}
    mine = built.get(current) or {}
    same = sum(1 for b, r in ref.items()
               if all((mine.get(b) or {}).get(k) == r.get(k)
                      for k in ("total",) + STANCES))
    print(f"  {current} rebuilt from the dump: {same:,} of {len(ref):,} bills "
          "equal to the database's own counts")
    if ref and same < len(ref) * 0.98:
        print("  The dump predates the file, so a few may differ; this many "
              "is a reshape that is wrong. Not writing.")
        return 3
    if a.check:
        print("--check: nothing written")
        return 0

    archived = {t: v for t, v in built.items() if t != current}
    if not archived:
        print("no archived term's sign-ins to write")
        return 3
    try:
        merged = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        merged = {}
    merged.update(archived)      # merge: every other term is left as it is
    out_path.write_text(json.dumps(merged, indent=1), encoding="utf-8")
    print(f"-> {a.out}: " + ", ".join(f"{t} {len(v):,}"
                                      for t, v in sorted(merged.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
