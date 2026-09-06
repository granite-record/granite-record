#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-06.1
"""
The roll calls for one session year, from the General Court's own database.

    python3 fetch_rollcalls_db.py --year 2025
    python3 fetch_rollcalls_db.py --year 2026 --check   # prove the mapping

WHY THIS EXISTS

RollCallSummary.txt and RollCallHistory.txt in the project root are the CURRENT
session only. On 6 September they held 419 votes and 131,199 member votes, and
every one of them was 2026. So the site showed no recorded vote for any of
2025: HB56's history says the House killed it on a roll call 216-154 and its
votes tab was empty.

The bulk files cannot be re-downloaded for a past year -- the General Court
publishes one file per current session -- but the database keeps them.
rollcallsummary and rollcallhistory both span 1999 to 2026: 9,565 votes and
2,303,047 member votes, with 380 and 107,118 of those in 2025.

WHAT IT WRITES

Files in exactly the shape the bulk downloads have, one pair per year, under
rollcalls/. The parsers already read that shape; giving them a second file to
read is a smaller change than teaching them a second format, and it means the
database and the download can never disagree about what a row means.

    rollcalls/RollCallSummary_2025.txt
    rollcalls/RollCallHistory_2025.txt

THREE THINGS THE DATABASE SPELLS DIFFERENTLY, ALL MEASURED

  The vote. The file writes a word -- Yea, Nay, Not Voting/Excused -- and the
  view writes a tinyint. Nothing documents the mapping, so it was read off the
  2026 rows the project has both halves of. Six codes, six words, and the
  counts match to the row on all 131,199: 1/Yea 61,325, 2/Nay 51,794,
  3/Excused 10,878, 4/Not Excused 6,876, 6/Presiding 325, 0/blank 1.

  The member. rollcallhistory identifies one by Employeeno (332247); every
  roster on this site uses PersonID (960). The legislators view carries both,
  and PersonID 960 does come back against Employeeno 332247 -- Phyllis
  Katsakiores -- which is the pair the 2026 file already shows.

  The date. The file writes M/d/yyyy h:mm:ss tt.

--check fetches a year already on disk and diffs it against the download,
which is the only honest way to know the shape is right.

THIS IS NOT THE WEB SERVER. It is the SQL host the General Court publishes
credentials for, at gc.nh.gov/downloads. Nothing here touches gc.nh.gov, and
nothing here writes: every statement is a SELECT.
"""

import argparse
import sys
from pathlib import Path

import probe_db

# Read off the 2026 rows, where the project holds the file and the view both.
# Counts matched exactly on every one of 131,199 member votes, so this is a
# measurement rather than a reading of documentation that does not exist.
VOTE_WORD = {"0": "", "1": "Yea", "2": "Nay", "3": "Not Voting/Excused",
             "4": "Not Voting/Not Excused", "6": "Presiding"}

# The columns of RollCallSummary.txt, in its order. The view has three more --
# UserName, Verified, CalendarItemID -- which the download does not carry and
# no parser reads.
SUMMARY_SQL = """
SELECT CAST(s.SessionYear AS varchar(4)) AS c0,
       ISNULL(s.LegislativeBody,'') AS c1,
       CAST(s.VoteSequenceNumber AS varchar(8)) AS c2,
       ISNULL(FORMAT(s.VoteDate,'M/d/yyyy h:mm:ss tt'),'') AS c3,
       ISNULL(s.CondensedBillNo,'') AS c4,
       CAST(ISNULL(s.Yeas,0) AS varchar(8)) AS c5,
       CAST(ISNULL(s.Nays,0) AS varchar(8)) AS c6,
       CAST(ISNULL(s.Present,0) AS varchar(8)) AS c7,
       CAST(ISNULL(s.Absent,0) AS varchar(8)) AS c8,
       ISNULL(s.AbbreviatedTitle1,'') AS c9,
       ISNULL(s.AbbreviatedTitle2,'') AS c10,
       ISNULL(s.Question_Motion,'') AS c11,
       ISNULL(s.Title1,'') AS c12,
       ISNULL(s.Title2,'') AS c13,
       '' AS c14
FROM rollcallsummary s
WHERE s.SessionYear = %d
ORDER BY s.LegislativeBody, s.VoteSequenceNumber
"""

# And of RollCallHistory.txt. Field 3 is the member's Employeeno and field 4
# the roster's PersonID; the view has only the first, so the legislators view
# supplies the second.
HISTORY_SQL = """
SELECT CAST(h.SessionYear AS varchar(4)) AS c0,
       ISNULL(h.LegislativeBody,'') AS c1,
       CAST(h.VoteSequenceNumber AS varchar(8)) AS c2,
       ISNULL(h.EmployeeNumber,'') AS c3,
       ISNULL(CAST(l.PersonID AS varchar(12)),'') AS c4,
       ISNULL(h.CondensedBillNo,'') AS c5,
       CAST(ISNULL(h.Vote,0) AS varchar(4)) AS c6,
       ISNULL(FORMAT(h.DateModified,'M/d/yyyy h:mm:ss tt'),'') AS c7
FROM rollcallhistory h
LEFT JOIN legislators l ON l.Employeeno = h.EmployeeNumber
WHERE h.SessionYear = %d
"""

COLS = {"summary": 15, "history": 8}


def rows_to_lines(rows, n, votecol=None):
    """The view's answer as the download's pipe-delimited lines."""
    out = []
    for r in rows:
        f = [str(r.get(f"c{i}", "") or "") for i in range(n)]
        if votecol is not None:
            f[votecol] = VOTE_WORD.get(f[votecol].strip(), f[votecol])
        # A pipe inside a field would move every column after it. None has one
        # in 2025 or 2026; if one ever does, losing it is better than silently
        # shifting a vote onto the wrong member.
        out.append("|".join(x.replace("|", " ") for x in f))
    return out


def fetch(cs, year):
    q = [("summary", SUMMARY_SQL % year), ("history", HISTORY_SQL % year)]
    res, err = probe_db.run(cs, q)
    if err:
        sys.exit(f"  the database refused: {err}")
    got = {}
    for block in res:
        if block.get("error"):
            sys.exit(f"  {block.get('name')}: {block['error'][:200]}")
        rows = block.get("rows") or []
        got[block["name"]] = [rows] if isinstance(rows, dict) else rows
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--out", default="rollcalls",
                    help="directory for the per-year files")
    ap.add_argument("--check", action="store_true",
                    help="diff against the download for a year already on disk "
                         "instead of writing anything")
    a = ap.parse_args()

    base = (f"Database={probe_db.DATABASE};User ID={probe_db.USER};"
            f"Password={probe_db.PASSWORD};Encrypt=False;"
            "TrustServerCertificate=True;Connect Timeout=20")
    cs = f"Server={probe_db.HOST};{base}"

    print(f"SELECT only, one connection, session year {a.year}")
    got = fetch(cs, a.year)
    summary = rows_to_lines(got.get("summary", []), COLS["summary"])
    history = rows_to_lines(got.get("history", []), COLS["history"], votecol=6)
    print(f"  {len(summary):,} roll calls, {len(history):,} member votes")

    if not summary:
        sys.exit(f"  nothing for {a.year}. rollcallsummary spans 1999-2026.")
    # A member the legislators view does not carry cannot be named downstream.
    blank = sum(1 for l in history if l.split("|")[4] == "")
    if blank:
        print(f"  {blank:,} member votes have no roster id, so those members "
              "will show as unnamed")

    if a.check:
        # The only honest test of the column mapping: ask for a year the
        # download already covers and compare, line for line.
        for name, lines, disk in (("summary", summary, "RollCallSummary.txt"),
                                  ("history", history, "RollCallHistory.txt")):
            p = Path(disk)
            if not p.exists():
                print(f"  {disk} is not here to compare against")
                continue
            have = [l.rstrip("\n") for l in
                    p.open(encoding="utf-8-sig", errors="replace")
                    if l.strip()]
            have = [l for l in have if l.split("|")[0].strip() == str(a.year)]
            same = set(lines) & set(have)
            print(f"\n  {name}: {len(lines):,} from the database, "
                  f"{len(have):,} on disk, {len(same):,} identical")
            for label, diff in (("only in the database", set(lines) - set(have)),
                                ("only on disk", set(have) - set(lines))):
                if diff:
                    print(f"    {len(diff):,} {label}:")
                    for l in sorted(diff)[:3]:
                        print(f"      {l[:150]}")
        return 0

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, lines in (("RollCallSummary", summary), ("RollCallHistory", history)):
        f = out / f"{name}_{a.year}.txt"
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  -> {f}  ({len(lines):,} lines)")
    print("\nThe parsers read every file in this directory alongside the "
          "current session's download, so a year fetched once stays fetched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
