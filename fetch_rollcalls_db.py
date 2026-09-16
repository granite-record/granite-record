#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-06.3
"""
The roll calls for one session year, from the General Court's own database.

    python3 fetch_rollcalls_db.py --check --year 2026   # prove the mapping
    python3 fetch_rollcalls_db.py --year 2025

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

The rows are written by the database bridge straight to those files and never
pass through this process. A first attempt handed them back as JSON and did
not return inside five minutes; see probe_db.run_to_file.

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

  The date. The file writes M/d/yyyy h:mm:ss tt. And it writes TWO of them:
  field 3 is VoteDate and field 14 is DateModified. The House fills the first
  and leaves the second null on all 329 of its 2026 roll calls; the Senate
  writes a date with no time in the first and the clock time in the second, on
  all 90 of its. So a Senate roll call's field 3 reads midnight.

--check fetches a year already on disk and diffs it against the download,
which is the only honest way to know the shape is right.

THIS IS NOT THE WEB SERVER. It is the SQL host the General Court publishes
credentials for, at gc.nh.gov/downloads. Nothing here touches gc.nh.gov, and
nothing here writes: every statement is a SELECT.
"""

import argparse
import sys
import tempfile
from pathlib import Path

import probe_db

# Read off the 2026 rows, where the project holds the file and the view both.
# Counts matched exactly on every one of 131,199 member votes, so this is a
# measurement rather than a reading of documentation that does not exist.
# 5 and 7 added on 16 September. They were never here, and a code this dict
# does not cover passes through as its own digit -- which is how 411 ballots
# reached the site reading "5" and 156 reading "7". Neither is a vote cast
# either way: the General Court's own page for 2017 SB 133 shows the Vote
# column EMPTY for the member whose ballot is code 7. What 5 means, in
# 1999-2002, is not established here; it is named the same way because
# whatever it is, it is not a Yea or a Nay.
VOTE_WORD = {"0": "", "1": "Yea", "2": "Nay", "3": "Not Voting/Excused",
             "4": "Not Voting/Not Excused", "5": "No vote recorded",
             "6": "Presiding", "7": "No vote recorded"}


def vote_case(col):
    """VOTE_WORD as a SQL CASE, so one dict stays the only copy of it.

    The translation happens in the database rather than here because the rows
    are streamed to a file and are never in this process to translate. A code
    the dict does not cover passes through as its own digit rather than being
    blanked, so an unmapped value shows up as an oddity instead of vanishing.
    """
    whens = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in sorted(VOTE_WORD.items()))
    n = f"CAST(ISNULL({col},0) AS varchar(4))"
    return f"CASE {n} {whens} ELSE {n} END"


# The columns of RollCallSummary.txt, in its order. The view has three more --
# UserName, Verified, CalendarItemID -- which the download does not carry and
# no parser reads.
SUMMARY_SQL = """
SELECT CAST(s.SessionYear AS varchar(4)),
       ISNULL(s.LegislativeBody,''),
       CAST(s.VoteSequenceNumber AS varchar(8)),
       ISNULL(FORMAT(s.VoteDate,'M/d/yyyy h:mm:ss tt'),''),
       ISNULL(s.CondensedBillNo,''),
       CAST(ISNULL(s.Yeas,0) AS varchar(8)),
       CAST(ISNULL(s.Nays,0) AS varchar(8)),
       CAST(ISNULL(s.Present,0) AS varchar(8)),
       CAST(ISNULL(s.Absent,0) AS varchar(8)),
       ISNULL(s.AbbreviatedTitle1,''),
       ISNULL(s.AbbreviatedTitle2,''),
       ISNULL(s.Question_Motion,''),
       ISNULL(s.Title1,''),
       ISNULL(s.Title2,''),
       ISNULL(FORMAT(s.DateModified,'M/d/yyyy h:mm:ss tt'),'')
FROM rollcallsummary s
WHERE s.SessionYear = %d
ORDER BY s.LegislativeBody, s.VoteSequenceNumber
"""

# And of RollCallHistory.txt. Field 3 is the member's Employeeno and field 4
# the roster's PersonID; the view has only the first, so the legislators view
# supplies the second.
HISTORY_SQL = """
SELECT CAST(h.SessionYear AS varchar(4)),
       ISNULL(h.LegislativeBody,''),
       CAST(h.VoteSequenceNumber AS varchar(8)),
       ISNULL(h.EmployeeNumber,''),
       ISNULL(CAST(l.PersonID AS varchar(12)),''),
       ISNULL(h.CondensedBillNo,''),
       %s,
       ISNULL(FORMAT(h.DateModified,'M/d/yyyy h:mm:ss tt'),'')
FROM rollcallhistory h
LEFT JOIN legislators l ON l.Employeeno = h.EmployeeNumber
WHERE h.SessionYear = %d
ORDER BY h.LegislativeBody, h.VoteSequenceNumber, h.EmployeeNumber
"""


def lines_of(path):
    """The non-empty lines of a pipe-delimited file, newline stripped."""
    with Path(path).open(encoding="utf-8-sig", errors="replace") as fh:
        return [ln.rstrip("\r\n") for ln in fh if ln.strip()]


def stream(cs, sql, path, label):
    n, err = probe_db.run_to_file(cs, sql, path, label=label)
    if err:
        sys.exit(f"  the database refused: {err}")
    return n


def compare(name, mine, disk, year):
    """Line for line against the download, for a year the download covers."""
    p = Path(disk)
    if not p.exists():
        print(f"  {disk} is not here to compare against")
        return False
    have = [ln for ln in lines_of(p) if ln.split("|")[0].strip() == str(year)]
    got = lines_of(mine)
    same = set(got) & set(have)
    print(f"\n  {name}: {len(got):,} from the database, {len(have):,} on disk, "
          f"{len(same):,} identical")
    ok = True
    for label, diff in (("only in the database", set(got) - set(have)),
                        ("only on disk", set(have) - set(got))):
        if diff:
            ok = False
            print(f"    {len(diff):,} {label}:")
            for ln in sorted(diff)[:3]:
                print(f"      {ln[:150]}")
    return ok


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

    print(f"SELECT only, one connection each, session year {a.year}")
    tmp = tempfile.TemporaryDirectory() if a.check else None
    out = Path(tmp.name) if a.check else Path(a.out)

    jobs = [("RollCallSummary", SUMMARY_SQL % a.year, "RollCallSummary.txt"),
            ("RollCallHistory", HISTORY_SQL % (vote_case("h.Vote"), a.year),
             "RollCallHistory.txt")]
    wrote = {}
    for name, sql, download in jobs:
        f = out / f"{name}_{a.year}.txt"
        n = stream(cs, sql, f, f"{name} ")
        print(f"  {name}: {n:,} rows")
        wrote[name] = (f, n, download)

    if not wrote["RollCallSummary"][1]:
        sys.exit(f"  nothing for {a.year}. rollcallsummary spans 1999-2026.")

    # A member the legislators view does not carry cannot be named downstream.
    blank = sum(1 for ln in lines_of(wrote["RollCallHistory"][0])
                if ln.split("|")[4] == "")
    if blank:
        print(f"  {blank:,} member votes have no roster id, so those members "
              "will be named from former_members.json or not at all")

    if a.check:
        # The only honest test of the column mapping: ask for a year the
        # download already covers and compare, line for line.
        ok = all([compare(n, f, download, a.year)
                  for n, (f, _, download) in wrote.items()])
        print("\n  the database's answer is the download, exactly" if ok else
              "\n  they differ; the mapping above is not settled")
        tmp.cleanup()
        return 0 if ok else 1

    for name, (f, n, _) in wrote.items():
        print(f"  -> {f}  ({n:,} lines)")
    print("\nThe parsers read every file in this directory alongside the "
          "current session's download, so a year fetched once stays fetched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
