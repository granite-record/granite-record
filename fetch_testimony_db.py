#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-06.2
"""
How many people signed in for and against a bill, per hearing.

    python3 fetch_testimony_db.py --dry-run
    python3 fetch_testimony_db.py

WHY THIS EXISTS

testimony.json is scraped from the House's remote testimony page and covers
565 bills. The General Court's database has the same sign-in sheet for 2,124 --
almost every bill that got a hearing -- and carries the hearing DATE with each
sign-in, so the count can sit with the hearing it belongs to rather than as one
number for the whole bill. That is the point of it: a hearing next week on
something you care about, and the tally as it stands today.

WHAT IT DELIBERATELY DOES NOT TAKE

Names, written testimony, and towns. The table has all three -- roughly 400,000
sign-ins with a name and a town attached, and 129,000 pieces of written
testimony -- and almost every one is a private individual who signed a
committee's sheet, not a public figure. The aggregate carries the civic fact
without republishing the person, and this site has no business doing the
second.

So the counting happens in SQL. No name and no testimony text is ever sent
over the connection, let alone written to disk; the query cannot return one.

WHAT IT WRITES

testimony_db.json, keyed on the term:

    {"2025-2026": {"HB283": {
        "total": 30212, "support": 71, "oppose": 30108, "neutral": 33,
        "hearings": [{"date": "2025-02-11", "total": 30212, ...}]}}}

THIS IS NOT THE WEB SERVER. It is the SQL host the General Court publishes
credentials for, at gc.nh.gov/downloads. Nothing here touches gc.nh.gov, and
every statement is a SELECT.
"""

import argparse
import collections
import json
import sys
import tempfile
from pathlib import Path

import proceedings as P
import probe_db

# Counted per bill, per hearing day, per stance -- and nothing else selected.
# Expr1 is the column the sign-in form's support/oppose/neutral lands in;
# whoIsName (member of the public, lobbyist, elected official) and the name,
# town and testimony columns are not named here on purpose.
SQL = """
SELECT ISNULL(l.CondensedBillNo,''),
       CAST(ISNULL(l.sessionyear,0) AS varchar(4)),
       ISNULL(FORMAT(t.CommitteeDate,'yyyy-MM-dd'),''),
       LOWER(ISNULL(t.Expr1,'')),
       CAST(COUNT(*) AS varchar(12))
FROM houseRemoteTestify t
JOIN Legislation l ON l.legislationID = t.legislationID
-- Within the bill's own biennium, and this is not belt-and-braces.
-- legislationID is reused across terms and Legislation holds the current one
-- only, so the join alone put 67,119 sign-ins from 2024 onto 856 bills of the
-- 2025-2026 term -- 17.6% of the file -- including hearings dated eighteen
-- months before the bill they were attached to was filed. A term begins in the
-- odd year, so sessionyear 2025 and 2026 both start at 2025.
WHERE YEAR(t.CommitteeDate)
      BETWEEN (l.sessionyear - (1 - l.sessionyear % 2))
          AND (l.sessionyear - (1 - l.sessionyear % 2) + 1)
GROUP BY l.CondensedBillNo, l.sessionyear,
         FORMAT(t.CommitteeDate,'yyyy-MM-dd'), t.Expr1
ORDER BY l.CondensedBillNo
"""

# Sign-ins that belong to no bill of a term this site holds: the table reaches
# back into 2024 and Legislation holds the current term only, so a hearing on a
# bill of an earlier term has nowhere to go. Counted so the gap is stated
# rather than implied.
UNJOINED = """
SELECT CAST(COUNT(*) AS varchar(12))
FROM houseRemoteTestify t
WHERE NOT EXISTS (
    SELECT 1 FROM Legislation l
    WHERE l.legislationID = t.legislationID
      AND YEAR(t.CommitteeDate)
          BETWEEN (l.sessionyear - (1 - l.sessionyear % 2))
              AND (l.sessionyear - (1 - l.sessionyear % 2) + 1))
"""

STANCES = ("support", "oppose", "neutral")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="testimony_db.json")
    ap.add_argument("--dry-run", action="store_true",
                    help="report the counts and write nothing")
    a = ap.parse_args()

    base = (f"Database={probe_db.DATABASE};User ID={probe_db.USER};"
            f"Password={probe_db.PASSWORD};Encrypt=False;"
            "TrustServerCertificate=True;Connect Timeout=20")
    cs = f"Server={probe_db.HOST};{base}"

    print("SELECT only: sign-in counts per bill and hearing, no names, no text")
    tmp = tempfile.TemporaryDirectory()
    raw = Path(tmp.name) / "testimony.txt"
    n, err = probe_db.run_to_file(cs, SQL, raw, every=4000, label="rows ")
    if err:
        sys.exit(f"  the database refused: {err}")
    if not n:
        sys.exit("  nothing came back. houseRemoteTestify held 402,908 "
                 "sign-ins on 6 September.")
    print(f"  {n:,} (bill, hearing, stance) groups")

    by_term = collections.defaultdict(dict)
    unknown = collections.Counter()
    for line in raw.open(encoding="utf-8", errors="replace"):
        p = line.rstrip("\n").split("|")
        if len(p) != 5:
            continue
        bill, year, date, stance, count = (x.strip() for x in p)
        if not bill or not year:
            continue
        try:
            count = int(count)
        except ValueError:
            continue
        if stance not in STANCES:
            # A stance the form does not offer. Counted into the total and
            # named, rather than folded into one of the three it is not.
            unknown[stance or "(blank)"] += count
        term = P.term_of(year)
        rec = by_term[term].setdefault(
            bill.upper(), {"total": 0, "support": 0, "oppose": 0, "neutral": 0,
                           "hearings": {}})
        rec["total"] += count
        if stance in STANCES:
            rec[stance] += count
        h = rec["hearings"].setdefault(
            date, {"date": date, "total": 0, "support": 0, "oppose": 0,
                   "neutral": 0})
        h["total"] += count
        if stance in STANCES:
            h[stance] += count
    tmp.cleanup()

    out = {}
    for term, bills in by_term.items():
        out[term] = {}
        for bill, rec in bills.items():
            rec["hearings"] = sorted(rec["hearings"].values(),
                                     key=lambda h: h["date"] or "9999")
            out[term][bill] = rec

    total = sum(r["total"] for b in out.values() for r in b.values())
    nbills = sum(len(b) for b in out.values())
    print(f"  {total:,} sign-ins across {nbills:,} bills")
    for term in sorted(out):
        sup = sum(r["support"] for r in out[term].values())
        opp = sum(r["oppose"] for r in out[term].values())
        neu = sum(r["neutral"] for r in out[term].values())
        print(f"    {term}: {len(out[term]):,} bills, "
              f"{sup:,} support, {opp:,} oppose, {neu:,} neutral")
    if unknown:
        print("  stances the form does not offer, counted in the total only: "
              + ", ".join(f"{k} {v:,}" for k, v in unknown.most_common(5)))

    res, err = probe_db.run(cs, [("unjoined", UNJOINED)])
    if not err and res and not res[0].get("error"):
        rows = res[0].get("rows") or []
        rows = [rows] if isinstance(rows, dict) else rows
        if rows:
            left = int(list(rows[0].values())[0] or 0)
            if left:
                print(f"  {left:,} sign-ins are for a bill this term's files do "
                      "not carry, so they are left out")

    if a.dry_run:
        print(f"\n--dry-run: nothing written to {a.out}")
        return 0
    # Merge, not replace. This rebuilds every term the database holds, so
    # replacing is correct TODAY -- but the database holds the current session
    # only, and the moment a past term's sign-ins come from anywhere else, or
    # a --term flag is added here, writing `out` over the file deletes them.
    #
    # That is not hypothetical: resolve_members.py took former_members.json
    # from 675 entries to 3 on 7 September doing exactly this, and the
    # manifest lost its hand-marked times twice before that. Keeping a term
    # this run did not produce costs four lines.
    op = Path(a.out)
    merged = {}
    if op.exists():
        try:
            merged = json.loads(op.read_text(encoding="utf-8"))
        except ValueError:
            merged = {}
    kept = [t for t in merged if t not in out]
    merged.update(out)
    op.write_text(json.dumps(merged, indent=1), encoding="utf-8")
    print(f"  -> {a.out}  ("
          + ", ".join(f"{t}: {len(v):,}" for t, v in sorted(merged.items())) + ")")
    if kept:
        print("     kept, because this run did not cover them: "
              + ", ".join(sorted(kept)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
