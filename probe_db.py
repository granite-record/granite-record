#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-06.11
"""
What is actually in the General Court's public database.

    python3 probe_db.py              # connect, count, report; writes nothing
    python3 probe_db.py --raw        # also save the raw output for reading later

WHY THIS EXISTS

gc.nh.gov/downloads publishes "ODBC and Data Table Structure.pdf", which gives
read-only credentials to a SQL Server holding the tables behind the bill status
system. The bulk .txt files this project already downloads are dumps of those
same tables. The database may or may not hold more than the current session,
and that single fact decides the shape of the archive:

  if it keeps past sessions   term-keyed identifiers are a column, not a
                              migration, and the 2005/2023 page-structure
                              probes are unnecessary for docket, votes,
                              sponsors and members
  if it does not              the archive is the project already planned

Nothing else about the archive can be settled until that is known, so this asks
and stops.

WHAT IT WILL NOT DO

Only SELECT. It never writes, never creates, never drops, and does not test
whether it could -- an account being read-only is the agency's business to
enforce, not this script's to probe. It opens one connection with a short
timeout and closes it.

The credentials are published by the General Court in that PDF for public use,
so they are not a secret being handled here. They are named once, below, with
the source cited.

HOW IT CONNECTS

There is no Python SQL Server driver on this machine and none is installed for
this. Windows PowerShell can open a connection through .NET's SqlClient with
nothing added, so that is what this shells out to. The PDF notes the instance
name may not be needed, so both forms are tried, plainest first.
"""

import argparse
import json
import subprocess
import sys
import child
from pathlib import Path

# From gc.nh.gov/downloads/ODBC and Data Table Structure.pdf, which publishes
# these for public use. Read-only account.
HOST = "66.211.150.69"
INSTANCE = "sqlexpress"
DATABASE = "NHLegislatureDB"
USER = "publicuser"
PASSWORD = "PublicAccess"

# Every question worth one round trip, and nothing that changes anything.
QUERIES = [
    ("server", "SELECT @@VERSION AS v"),
    # No filter. The first run asked for BASE TABLE and got nothing back
    # while INFORMATION_SCHEMA.COLUMNS answered fine for docket, which says
    # the public objects are probably views rather than tables -- and a view
    # is a strong hint about where the 2017-2024 gap comes from.
    ("tables",
     "SELECT TABLE_NAME AS t, TABLE_TYPE AS kind "
     "FROM INFORMATION_SCHEMA.TABLES ORDER BY TABLE_NAME"),
    # The one that decides the archive.
    ("docket span",
     "SELECT MIN(SessionYear) AS first_year, MAX(SessionYear) AS last_year, "
     "COUNT(*) AS rows FROM docket"),
    # "Retained" and "one stale row survived" look identical in a MIN/MAX.
    ("docket rows per session",
     "SELECT SessionYear AS yr, COUNT(*) AS rows FROM docket "
     "GROUP BY SessionYear ORDER BY SessionYear"),
    ("sponsors span",
     "SELECT MIN(SessionYear) AS first_year, MAX(SessionYear) AS last_year, "
     "COUNT(*) AS rows FROM sponsors"),
    ("rollcall span",
     "SELECT MIN(sessionYear) AS first_year, MAX(sessionYear) AS last_year, "
     "COUNT(*) AS rows FROM rollcallsummary"),
    # The site has sign-in counts for 565 of 1,237 bills and no testimony text.
    # DATALENGTH, not LEN: testimonyText is the legacy `text` type and LEN
    # refuses it outright, which is what the first run hit.
    ("testimony",
     "SELECT COUNT(*) AS rows, "
     "SUM(CASE WHEN testimonyText IS NULL OR DATALENGTH(testimonyText) = 0 "
     "THEN 0 ELSE 1 END) AS with_text FROM houseRemoteTestify"),
    ("testimony by year",
     "SELECT YEAR(committeeDate) AS yr, COUNT(*) AS rows "
     "FROM houseRemoteTestify GROUP BY YEAR(committeeDate) ORDER BY yr"),
    # docket carries a [DataBase] column the PDF does not document. If the
    # 2017-2024 rows live under a different value, or a different database on
    # this server, that is where they are.
    ("docket DataBase column",
     "SELECT [DataBase] AS src, COUNT(*) AS rows, MIN(SessionYear) AS first_year, "
     "MAX(SessionYear) AS last_year FROM docket GROUP BY [DataBase] "
     "ORDER BY [DataBase]"),
    ("other databases on this server",
     "SELECT name FROM sys.databases ORDER BY name"),
    # Everything else that might reach back, so the archive is planned on what
    # is actually retained rather than on docket alone.
    ("legislators span",
     "SELECT COUNT(*) AS rows FROM legislators"),
    ("rollcall history span",
     "SELECT MIN(sessionYear) AS first_year, MAX(sessionYear) AS last_year, "
     "COUNT(*) AS rows FROM rollcallhistory"),
    # The PDF documents 13 objects; the server exposes 28, all views, and
    # several are things this project currently scrapes a page at a time.
    ("all columns",
     "SELECT TABLE_NAME AS v, COLUMN_NAME AS c, DATA_TYPE AS ty "
     "FROM INFORMATION_SCHEMA.COLUMNS ORDER BY TABLE_NAME, ORDINAL_POSITION"),
    ("LegislationText", "SELECT COUNT(*) AS rows FROM LegislationText"),
    ("Legislation", "SELECT COUNT(*) AS rows FROM Legislation"),
    ("CandH_Reports", "SELECT COUNT(*) AS rows FROM CandH_Reports"),
    ("CommitteeMembers", "SELECT COUNT(*) AS rows FROM CommitteeMembers"),
    ("VHearings", "SELECT COUNT(*) AS rows FROM VHearings"),
    ("DocumentVersion", "SELECT COUNT(*) AS rows FROM DocumentVersion"),
    ("NH_RSA", "SELECT COUNT(*) AS rows FROM NH_RSA"),
]

# Counts say a view exists; they do not say what is in it. These read a few
# real rows, which is the only way to know whether CandH_Reports is the
# committee reports this site is missing for 1,254 bills, and whether
# LegislationText is the bill text it currently spends 2,234 requests on.
#
# HTMLText is `text` and PDFImage is `image`. Both are cast and clipped --
# nothing here pulls a megabyte, and PDFImage is never selected at all.
SAMPLES = [
    # Proof, not assumption: RollCallHistory.txt's first 2026 row pairs
    # EmployeeNumber 332247 with roster id 960. If the legislators view puts
    # PersonID 960 against Employeeno 332247, the two id spaces are joined and
    # any year in the database can be named against the roster.
    ("legislators: does PersonID 960 carry Employeeno 332247",
     "SELECT PersonID, Employeeno, LastName, FirstName, LegislativeBody, Active "
     "FROM legislators WHERE Employeeno = '332247' OR PersonID = 960"),
    ("legislators: how many, and how many still sitting",
     "SELECT Active, COUNT(*) AS rows, COUNT(DISTINCT PersonID) AS people "
     "FROM legislators GROUP BY Active"),
    # rollcallhistory identifies a member by EmployeeNumber (376972);
    # legislators.txt and every roster on this site use a different id
    # (11332). RollCallHistory.txt carries BOTH, so the join exists somewhere.
    # If the legislators view holds the pair, an archived year can be joined
    # to the roster; if it does not, only members who also voted in a year
    # already on disk can be named.
    ("legislators: its columns",
     "SELECT COLUMN_NAME AS c, DATA_TYPE AS ty FROM INFORMATION_SCHEMA.COLUMNS "
     "WHERE TABLE_NAME = 'legislators' ORDER BY ORDINAL_POSITION"),
    ("legislators: a real row",
     "SELECT TOP 2 * FROM legislators"),
    # RollCallHistory.txt stores the vote as a word -- "Yea", "Not
    # Voting/Excused" -- and this view stores a tinyint. The mapping is not
    # documented anywhere, so it is read off the 2026 rows the site already
    # has both halves of: match the counts and the codes name themselves.
    ("rollcallhistory: 2026 vote codes",
     "SELECT Vote AS code, COUNT(*) AS rows FROM rollcallhistory "
     "WHERE sessionYear = 2026 GROUP BY Vote ORDER BY Vote"),
    ("rollcallhistory: a real 2026 row",
     "SELECT TOP 3 * FROM rollcallhistory WHERE sessionYear = 2026 "
     "AND LegislativeBody = 'H' AND VoteSequenceNumber = 1"),
    # The roll calls. RollCallSummary.txt and RollCallHistory.txt on disk are
    # the CURRENT session only -- 419 summary rows and 131,199 member votes,
    # every one of them 2026 -- so the site shows no recorded vote for any of
    # 2025. HB56 says the House killed it on a roll call 216-154 and lists
    # none. The views here span 1999-2026, so the gap is a fetch rather than a
    # loss, and these ask what shape it would arrive in.
    ("rollcallsummary: rows per year",
     "SELECT sessionYear AS yr, COUNT(*) AS rows FROM rollcallsummary "
     "GROUP BY sessionYear ORDER BY sessionYear DESC"),
    ("rollcallsummary: its columns",
     "SELECT COLUMN_NAME AS c, DATA_TYPE AS ty FROM INFORMATION_SCHEMA.COLUMNS "
     "WHERE TABLE_NAME = 'rollcallsummary' ORDER BY ORDINAL_POSITION"),
    ("rollcallsummary: a real 2025 row",
     "SELECT TOP 3 * FROM rollcallsummary WHERE sessionYear = 2025 "
     "ORDER BY voteSequenceNumber"),
    ("rollcallhistory: its columns",
     "SELECT COLUMN_NAME AS c, DATA_TYPE AS ty FROM INFORMATION_SCHEMA.COLUMNS "
     "WHERE TABLE_NAME = 'rollcallhistory' ORDER BY ORDINAL_POSITION"),
    ("rollcallhistory: rows for this term only",
     "SELECT sessionYear AS yr, COUNT(*) AS rows FROM rollcallhistory "
     "WHERE sessionYear IN (2025, 2026) GROUP BY sessionYear ORDER BY sessionYear"),
    ("CandH_Reports: what a Senate one looks like",
     "SELECT TOP 3 BillNbr, ChamberCode, CommitteeType, ReleaseDate, "
     "LEFT(CAST(HTMLText AS varchar(max)), 300) AS text_head "
     "FROM CandH_Reports WHERE ChamberCode = 'S' ORDER BY ReleaseDate DESC"),
    ("CandH_Reports: and a House one",
     "SELECT TOP 2 BillNbr, ChamberCode, CommitteeType, ReleaseDate, "
     "LEFT(CAST(HTMLText AS varchar(max)), 300) AS text_head "
     "FROM CandH_Reports WHERE ChamberCode = 'H' ORDER BY ReleaseDate DESC"),
    ("CandH_Reports: by chamber and type",
     "SELECT ChamberCode, CommitteeType, COUNT(*) AS rows, "
     "MIN(YEAR(ReleaseDate)) AS first_year, MAX(YEAR(ReleaseDate)) AS last_year "
     "FROM CandH_Reports GROUP BY ChamberCode, CommitteeType "
     "ORDER BY ChamberCode, CommitteeType"),
    ("LegislationText: versions per bill",
     "SELECT TOP 5 * FROM (SELECT LegislationID, COUNT(*) AS versions "
     "FROM LegislationText GROUP BY LegislationID) q ORDER BY versions DESC"),
    ("LegislationText: columns are enough to key on?",
     "SELECT COLUMN_NAME AS c, DATA_TYPE AS ty FROM INFORMATION_SCHEMA.COLUMNS "
     "WHERE TABLE_NAME = 'LegislationText' ORDER BY ORDINAL_POSITION"),
    ("CommitteeMembers: both chambers?",
     "SELECT LEFT(CommitteeCode, 1) AS chamber_letter, COUNT(*) AS rows, "
     "COUNT(DISTINCT CommitteeCode) AS committees "
     "FROM CommitteeMembers GROUP BY LEFT(CommitteeCode, 1)"),
    # What an archived bill could actually say. 2005 has docket and nothing
    # else, so this is the honest ceiling for the 1989-2016 era.
    ("Docket 2005: a real row",
     "SELECT TOP 4 SessionYear, ExpandedBillNo, LegislativeBody, StatusDate, "
     "LEFT(Description, 90) AS descr FROM Docket WHERE SessionYear = 2005 "
     "ORDER BY ExpandedBillNo, StatusDate"),
    ("Docket 2005: distinct bills",
     "SELECT COUNT(DISTINCT ExpandedBillNo) AS bills FROM Docket "
     "WHERE SessionYear = 2005"),
    # Is a bill's TITLE anywhere for the old years, or only its number?
    ("Legislation: columns",
     "SELECT COLUMN_NAME AS c, DATA_TYPE AS ty FROM INFORMATION_SCHEMA.COLUMNS "
     "WHERE TABLE_NAME = 'Legislation' ORDER BY ORDINAL_POSITION"),
]


PS = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$conn = New-Object System.Data.SqlClient.SqlConnection
$conn.ConnectionString = $env:GR_CONNSTR
try { $conn.Open() } catch {
  Write-Output ("CONNECT_FAIL " + $_.Exception.Message); exit 3 }
$out = @()
foreach ($pair in ($env:GR_QUERIES -split '~~')) {
  $bits = $pair -split '::', 2
  $cmd = $conn.CreateCommand()
  $cmd.CommandText = $bits[1]
  $cmd.CommandTimeout = 60
  try {
    $rdr = $cmd.ExecuteReader()
    $rows = @()
    while ($rdr.Read()) {
      $row = @{}
      for ($i = 0; $i -lt $rdr.FieldCount; $i++) {
        $row[$rdr.GetName($i)] = [string]$rdr.GetValue($i)
      }
      $rows += $row
    }
    $rdr.Close()
    $out += @{ name = $bits[0]; rows = $rows }
  } catch {
    $out += @{ name = $bits[0]; error = $_.Exception.Message }
  }
}
$conn.Close()
$out | ConvertTo-Json -Depth 6 -Compress
"""


def run(connstr, queries):
    """One PowerShell process, one connection, every query."""
    payload = "~~".join(f"{n}::{q}" for n, q in queries)
    p = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", PS],
        capture_output=True, text=True, timeout=300,
        encoding="utf-8", errors="replace",
        env={**__import__("os").environ,
             "GR_CONNSTR": connstr, "GR_QUERIES": payload})
    txt = (p.stdout or "").strip()
    if txt.startswith("CONNECT_FAIL"):
        return None, txt[len("CONNECT_FAIL"):].strip()
    if not txt:
        return None, (p.stderr or "no output").strip()[:300]
    try:
        d = json.loads(txt)
    except ValueError:
        return None, txt[:300]
    return (d if isinstance(d, list) else [d]), None


# A second bridge, for answers too big to hand back through JSON.
#
# run() builds a PowerShell array with $rows += $row and then serialises the
# whole thing with ConvertTo-Json. That is quadratic in the number of rows --
# += reallocates the array every time -- and it works fine for the forty-row
# questions it was written for. Asking it for rollcallhistory's 107,118 member
# votes for 2025 did not come back inside five minutes.
#
# Nothing about those rows needs to be in memory at all. The download they are
# replacing is pipe-delimited text, so the reader can write pipe-delimited text
# straight to a file as it goes and the process stays flat.
#
# It prints a count as it goes for the same reason everything here does: a step
# that can produce nothing and still exit zero has to say which it did.
PS_STREAM = r"""
$ErrorActionPreference = 'Stop'
$conn = New-Object System.Data.SqlClient.SqlConnection
$conn.ConnectionString = $env:GR_CONNSTR
try { $conn.Open() } catch {
  Write-Output ("CONNECT_FAIL " + $_.Exception.Message); exit 3 }
$cmd = $conn.CreateCommand()
$cmd.CommandText = $env:GR_SQL
$cmd.CommandTimeout = [int]$env:GR_TIMEOUT
$CR = [string][char]13
$LF = [string][char]10
$NL = $env:GR_NEWLINE
$every = [int]$env:GR_EVERY
$enc = New-Object System.Text.UTF8Encoding($false)
$w = New-Object System.IO.StreamWriter($env:GR_OUT, $false, $enc)
$n = 0
try {
  $rdr = $cmd.ExecuteReader()
  $f = $rdr.FieldCount
  while ($rdr.Read()) {
    $vals = for ($i = 0; $i -lt $f; $i++) {
      $v = $rdr.GetValue($i)
      if ($v -eq $null -or $v -is [System.DBNull]) { '' }
      else { ([string]$v).Replace('|',' ').Replace($CR,$NL).Replace($LF,$NL) }
    }
    $w.WriteLine([string]::Join('|', [string[]]$vals))
    $n++
    if ($every -gt 0 -and ($n % $every) -eq 0) {
      Write-Output ("PROGRESS " + $n); [Console]::Out.Flush()
    }
  }
  $rdr.Close()
} catch {
  $w.Close(); $conn.Close()
  Write-Output ("QUERY_FAIL " + $_.Exception.Message); exit 4
}
$w.Close()
$conn.Close()
Write-Output ("DONE " + $n)
"""


def run_to_file(connstr, sql, path, timeout=1800, every=20000, label="",
                newline=""):
    """Stream one SELECT to a pipe-delimited file. Returns (rows, error).

    The file is written by PowerShell, not by Python: the rows never cross the
    process boundary, so a query's size stops mattering. A pipe inside a value
    would move every column after it, so one is replaced with a space. A newline
    would split one row into two, and is DELETED rather than replaced: that is
    what the General Court's own bulk download does, measured on 2026's roll
    call titles, where a title runs "laws." then a space, then a newline, then
    "Providing", and the file holds "laws. Providing" on one line with a single
    space. Deleting reproduced 328 of the 419 rows exactly; replacing with a
    space reproduced 317. Pass newline=" " for a column that holds HTML, where
    a line break between two words is the only space between them.
    """
    import os
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    proc = child.popen(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_STREAM],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env={**os.environ, "GR_CONNSTR": connstr, "GR_SQL": sql,
             "GR_OUT": str(path.resolve()), "GR_TIMEOUT": str(int(timeout)),
             "GR_EVERY": str(int(every)), "GR_NEWLINE": newline})
    rows, err = None, None
    try:
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("PROGRESS "):
                print(f"    {label}{int(line[9:]):,} rows so far", flush=True)
            elif line.startswith("DONE "):
                rows = int(line[5:])
            elif line.startswith(("CONNECT_FAIL", "QUERY_FAIL")):
                err = line
    finally:
        proc.wait(timeout=timeout + 60)
    if err:
        return None, err
    if rows is None:
        return None, (proc.stderr.read() or "no output").strip()[:300]
    return rows, None


def show(results):
    for block in results:
        name = block.get("name", "?")
        if block.get("error"):
            print(f"\n  {name}: FAILED -- {block['error'][:160]}")
            continue
        rows = block.get("rows") or []
        if isinstance(rows, dict):
            rows = [rows]
        print(f"\n  {name}: {len(rows)} row(s)")
        for r in rows[:60]:
            print("    " + "  ".join(f"{k}={v}" for k, v in r.items())[:150])
        if len(rows) > 60:
            print(f"    ... {len(rows) - 60} more")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", action="store_true", help="save the JSON reply")
    # docket's [DataBase] column shows two source systems -- BillStatusDB for
    # 1989-2016 and NHLMS for 2025-2026 -- and nothing at all for 2017-2024.
    # The server also lists NHLegislatureDB2 and PublicNHLMS.
    ap.add_argument("--database", default=DATABASE,
                    help="another database on the same server")
    ap.add_argument("--sample", action="store_true",
                    help="read a few real rows instead of counting them")
    a = ap.parse_args()

    base = (f"Database={a.database};User ID={USER};Password={PASSWORD};"
            "Encrypt=False;TrustServerCertificate=True;Connect Timeout=20")
    # The PDF says the instance name may not be needed. Plainest first.
    attempts = [("host only", f"Server={HOST};{base}"),
                ("named instance",
                 "Server=" + HOST + chr(92) + INSTANCE + ";" + base)]

    print("=" * 70)
    print("The General Court's public database")
    print("=" * 70)
    print(f"  host      {HOST}")
    print(f"  database  {a.database}")
    print(f"  user      {USER}  (published for public use in "
          "ODBC and Data Table Structure.pdf)")
    print("  SELECT only. Nothing is written, here or there.")

    for label, cs in attempts:
        print(f"\nconnecting, {label} ...")
        try:
            results, err = run(cs, SAMPLES if a.sample else QUERIES)
        except subprocess.TimeoutExpired:
            print("  timed out after 5 minutes")
            continue
        except FileNotFoundError:
            sys.exit("  powershell is not on PATH; this needs Windows "
                     "PowerShell to reach SqlClient")
        if results is None:
            print(f"  no: {err}")
            continue
        print(f"  connected ({label})")
        show(results)
        if a.raw:
            Path(f"probe_db_{a.database}.json").write_text(
                json.dumps(results, indent=1), encoding="utf-8")
            print(f"\n  wrote probe_db_{a.database}.json")
        print("\n" + "=" * 70)
        print("The number that matters is the docket span. If it reaches back")
        print("past this term, the archive is a different project: term keying")
        print("becomes a column and the page-structure probes are only needed")
        print("for calendars, journals, bill text and committee reports, none")
        print("of which are in this database.")
        print("=" * 70)
        return 0

    print("\nCould not connect either way. That is an answer too -- the")
    print("published endpoint may be firewalled to the outside, in which case")
    print("the bulk .txt files remain the only route and the archive plan")
    print("stands as written. netcheck.py diagnoses a refusal without making")
    print("anything worse.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
