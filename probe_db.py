#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-06.18
"""
What is actually in the General Court's public database.

    python3 probe_db.py              # connect, count, report; writes nothing
    python3 probe_db.py --raw        # also save the raw output for reading later
    python3 probe_db.py --hold       # the hold on this host, if one is on file; asks nobody
    python3 probe_db.py --clear-hold # lift it here: a person's decision

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

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import base64
import decimal
import hashlib
import json
import os
import re
import subprocess
import time
import child
import refusal

# From gc.nh.gov/downloads/ODBC and Data Table Structure.pdf, which publishes
# these for public use. Read-only account.
HOST = "66.211.150.69"
INSTANCE = "sqlexpress"
DATABASE = "NHLegislatureDB"
USER = "publicuser"
PASSWORD = "PublicAccess"

# ---- this host's own hold (1 October 2026) -----------------------------------
#
# refusal.py is about the web server's firewall. This is another server with
# another failure, and until the night began to fall back on it (nightly.py,
# when the General Court's export comes back empty) it had no record of one:
# a view that failed was "not taken" and asked again the next night. Now a
# CONNECTION that fails -- no route, a timeout, the login refused -- is
# recorded in archive/sql-held.json, and run(), run_to_file() and _bridge(),
# which every query of the host passes through, ask hold_check() first: no
# more queries that night, from anything.
#
#   It expires by itself, and lengthens: HOLD_HOURS, a day, two, four, then
#   a week, each four hours short so that the night after finds it over.
#   Each night it has expired one connection is tried; one that opens ends
#   it. That is the deliberate difference from the web server's rule, where
#   only a person clears a refusal: a month unattended needs it, and one
#   connection a night is not what that rule exists to prevent.
#   A login the server REJECTS is recorded as that, so the night's page can
#   say the published password may have changed and somebody has to read
#   the PDF again. It expires and lengthens like any other, and is over at
#   once when the credentials above are changed. As first written it stood
#   for ever, on the words "Login failed" alone, and nothing on GitHub's
#   machine could lift it: but the server ends its message for a database
#   that is offline or being restored (error 4060, "Cannot open database
#   ... requested by the login") with the same words, and says them for an
#   account locked for an hour, so one bad morning on their side would have
#   ended every query for good. login_refused() leaves 4060 out; the expiry
#   is for whatever else is worded that way and passes. The wording is
#   SqlClient's as remembered, not as seen from this host: say so if a real
#   night shows another.
#   A query that fails or times out on an OPEN connection (QUERY_FAIL,
#   "Execution Timeout Expired" included) is not a hold: the host answered.
#
# RECORDED ON GITHUB'S MACHINE ONLY, honoured wherever it is on file. The
# record travels in R2's state/ (cloud_kit.json), and the night is its one
# writer: the laptop never sends state up, and a failed connection there is
# the person's to see where they ran it. A refusal from the web server does
# not hold this host, and the reverse.
HELD = Path("archive/sql-held.json")
# nightly.py names the record by its full path for the fetches it starts in a
# scratch folder (take_views), where "archive/" would be somewhere else.
HELD_ENV = "GRANITE_SQL_HELD"
HOLD_HOURS = (20, 44, 92, 164)
SQL_HELD = 5            # the exit status of a query stopped by the hold
LOGIN_REFUSED = re.compile(r"Login failed for user", re.I)
# Error 4060: the database, not the password. Its message ends with the
# line above all the same.
DATABASE_UNAVAILABLE = re.compile(r"Cannot open database", re.I)


def login_refused(why):
    """Whether a failed connection's message is the server rejecting the
    login itself, rather than a database it could not open for it."""
    why = str(why)
    return bool(LOGIN_REFUSED.search(why)) and not DATABASE_UNAVAILABLE.search(why)


def hold_file():
    return Path(os.environ.get(HELD_ENV) or HELD)


def _login():
    """Which credentials a refused login was about: a login hold stands only
    while these are still the ones in this file."""
    return hashlib.sha256(f"{HOST}|{DATABASE}|{USER}|{PASSWORD}".encode("utf-8")).hexdigest()[:12]


def hold_record():
    try:
        d = json.loads(hold_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def hold_standing(now=None):
    """The hold on file, if it still stands, or None."""
    d = hold_record()
    if not d or not d.get("held"):
        return None
    if d.get("kind") == "login" and d.get("login") != _login():
        return None             # the credentials it was about have been changed
    try:
        until = float(d.get("until"))
    except (TypeError, ValueError):
        return None             # no hold stands without a time it ends
    return d if (time.time() if now is None else now) < until else None


def hold_sentence(d):
    """What a hold on file says: when, how many times in a row, and until when.
    Its words are this file's and none of the server's: the night's page,
    which is public, carries it. Short, because that page cuts a note off."""
    n = int(d.get("nights") or 1)
    until = f"nothing queries it until {d.get('until_at', '?')}"
    return (f"the General Court's database could not be connected to at {d.get('at', '?')}"
            + (f", {n} times in a row" if n > 1 else "")
            + (f": it refused the published login, and {until}, or until the credentials in "
               "probe_db.py are changed" if d.get("kind") == "login" else f", and {until}"))


def hold_check(who=""):
    """Stop the caller while a hold on this host stands. Exit SQL_HELD."""
    d = hold_standing()
    if d is None:
        return
    print(f"\n{who or 'This query'} is not starting: {hold_sentence(d)}. "
          f"({hold_file().as_posix()})\n", file=sys.stderr)
    sys.exit(SQL_HELD)


def _write_hold(d):
    path = hold_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(d, indent=1, sort_keys=True) + "\n", encoding="utf-8",
                   newline="\n")
    os.replace(tmp, path)


def note_connect_fail(why, now=None):
    """A connection to this host failed: on GitHub's machine, record it and
    hold every query. The record, or None where none is kept."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None
    now = time.time() if now is None else now
    was = hold_record() or {}
    nights = (int(was.get("nights") or 0) if was.get("held") else 0) + 1
    login = login_refused(why)
    hours = HOLD_HOURS[min(nights, len(HOLD_HOURS)) - 1]
    d = {"held": True, "kind": "login" if login else "connection", "nights": nights,
         "at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)), "epoch": now,
         "why": str(why)[:300], "run_id": os.environ.get("GITHUB_RUN_ID", ""),
         "until": now + hours * 3600, "hours": hours}
    d["until_at"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(d["until"]))
    if login:
        d["login"] = _login()
    try:
        _write_hold(d)
    except OSError as e:
        print(f"  the hold could not be written to {hold_file().as_posix()}: {e}",
              file=sys.stderr)
    return d


def note_connected():
    """A connection opened: a hold that had expired is over, and the count of
    failures in a row starts again."""
    was = hold_record()
    if not was or not was.get("held"):
        return
    try:
        _write_hold({"held": False, "nights": 0,
                     "cleared": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "by": "a connection that opened",
                     "was": {k: was.get(k) for k in ("at", "kind", "nights", "why")}})
    except OSError:
        pass

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
    # GITHUB'S NIGHT. The night takes the study committees' views from this
    # host and the weekly job the rosters, so on a stood-down laptop no query
    # starts inside its window, or in the half hour before it. Every query of
    # the host passes through run(), run_to_file() or _bridge() -- the last
    # under run_to_file_counted() and run_to_jsonl() -- and each asks first,
    # which is why the check is here and not in each fetch_*_db.py; preflight
    # holds every function here that starts PowerShell to it. The window
    # only: the web server's refusal record is a different host's
    # (CLAUDE.md), so it does not govern this one.
    refusal.window_check("A query of the General Court's database")
    hold_check("A query of the General Court's database")
    payload = "~~".join(f"{n}::{q}" for n, q in queries)
    p = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", PS],
        capture_output=True, text=True, timeout=300,
        encoding="utf-8", errors="replace",
        env={**__import__("os").environ,
             "GR_CONNSTR": connstr, "GR_QUERIES": payload})
    txt = (p.stdout or "").strip()
    if txt.startswith("CONNECT_FAIL"):
        note_connect_fail(txt)
        return None, txt[len("CONNECT_FAIL"):].strip()
    if not txt:
        return None, (p.stderr or "no output").strip()[:300]
    try:
        d = json.loads(txt)
    except ValueError:
        return None, txt[:300]
    note_connected()
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
#
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

# PS_STREAM with a SELECT COUNT(*) asked first, on the same connection, and
# answered as a COUNT line, for run_to_file_counted. Its own copy, so that
# PS_STREAM -- which the nightly and fetch_archive_db.py run -- stays exactly
# what it was, whatever the environment it inherits.
PS_STREAM_COUNTED = PS_STREAM.replace(
    """try { $conn.Open() } catch {
  Write-Output ("CONNECT_FAIL " + $_.Exception.Message); exit 3 }
""",
    """try { $conn.Open() } catch {
  Write-Output ("CONNECT_FAIL " + $_.Exception.Message); exit 3 }
if ($env:GR_COUNT) {
  try {
    $cc = $conn.CreateCommand()
    $cc.CommandText = $env:GR_COUNT
    $cc.CommandTimeout = [int]$env:GR_TIMEOUT
    $counted = $cc.ExecuteScalar()
  } catch {
    $conn.Close()
    Write-Output ("QUERY_FAIL " + $_.Exception.Message); exit 4
  }
  Write-Output ("COUNT " + [string]$counted); [Console]::Out.Flush()
}
""", 1)
assert PS_STREAM_COUNTED != PS_STREAM



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
    refusal.window_check("A query of the General Court's database")   # as run()
    hold_check("A query of the General Court's database")
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
        if err.startswith("CONNECT_FAIL"):
            note_connect_fail(err)
        else:
            note_connected()            # it opened; the query is what failed
        return None, err
    if rows is None:
        return None, (proc.stderr.read() or "no output").strip()[:300]
    note_connected()
    return rows, None


# ---- counted streams, and text kept exactly ---------------------------------
#
# Two more bridges, written for fetch_past_db.py, which takes whole views and
# has to show that each one arrived whole. Both ask COUNT(*) on the same
# connection as the rows, just before them, so the number a file is checked
# against is the server's own and not a figure remembered from a probe.
#
# run_to_file_counted is run_to_file with that count and nothing else: the
# same PS_STREAM, the same pipe-delimited file, the same deleted line breaks.
#
# run_to_jsonl is for text that must come through EXACTLY. Bill text and
# committee reports hold pipes, line breaks, tabs, quotes and characters
# outside ASCII, and a pipe-delimited line can keep none of them. PowerShell
# does not write this file, for two reasons found in Windows PowerShell 5.1:
# its ConvertTo-Json writes a date as "\/Date(1136196000000)\/", and a
# console pipe carries text in the console's code page, which is not UTF-8.
# So PowerShell only reads. Each value crosses the pipe as base64 of its UTF-8
# bytes -- plain ASCII, which no code page can damage -- or as "-" for NULL,
# and Python decodes it and writes the JSON. Every byte of the text is then
# Python's to get right, which is also what lets preflight test it without a
# database.
#
# Neither holds more than one row in memory, on either side of the pipe, and
# both print progress as they go.

# The rows half of PS_JSONL is its own string so that preflight can run it
# over an in-memory table: the part that encodes a value is then tested in
# real PowerShell with no connection anywhere. It expects $o (the output
# writer) and $rdr (any IDataReader), and leaves $n, the rows it read.
PS_JSONL_ROWS = r"""
  $inv = [System.Globalization.CultureInfo]::InvariantCulture
  $utf8 = New-Object System.Text.UTF8Encoding($false)
  $every = [int]$env:GR_EVERY
  $f = $rdr.FieldCount
  $cells = New-Object 'string[]' $f
  for ($i = 0; $i -lt $f; $i++) {
    $cells[$i] = [Convert]::ToBase64String($utf8.GetBytes($rdr.GetName($i)))
  }
  $o.WriteLine('COLUMNS ' + [string]::Join(',', $cells))
  $n = 0
  while ($rdr.Read()) {
    for ($i = 0; $i -lt $f; $i++) {
      $v = $rdr.GetValue($i)
      if ($v -is [System.DBNull] -or $null -eq $v) { $cells[$i] = '-'; continue }
      if ($v -is [datetime]) { $s = $v.ToString('yyyy-MM-ddTHH:mm:ss.fffffff', $inv) }
      elseif ($v -is [System.DateTimeOffset]) { $s = $v.ToString('o', $inv) }
      elseif ($v -is [bool]) { if ($v) { $s = '1' } else { $s = '0' } }
      elseif ($v -is [double] -or $v -is [single]) { $s = $v.ToString('R', $inv) }
      elseif ($v -is [System.IFormattable]) { $s = $v.ToString($null, $inv) }
      else { $s = [string]$v }
      $cells[$i] = [Convert]::ToBase64String($utf8.GetBytes($s))
    }
    $o.WriteLine('R ' + [string]::Join(',', $cells))
    $n++
    if ($every -gt 0 -and ($n % $every) -eq 0) { $o.WriteLine('PROGRESS ' + $n); $o.Flush() }
  }
  $rdr.Close()
"""

PS_JSONL_CLOSE = r"""
} catch {
  $o.WriteLine('QUERY_FAIL ' + ($_.Exception.Message -replace '[\r\n]+', ' ')); $o.Flush()
  $conn.Close(); exit 4
}
$conn.Close()
$o.WriteLine('DONE ' + $n); $o.Flush()
"""

PS_JSONL = r"""
$ErrorActionPreference = 'Stop'
$o = [Console]::Out
$conn = New-Object System.Data.SqlClient.SqlConnection
$conn.ConnectionString = $env:GR_CONNSTR
try { $conn.Open() } catch {
  $o.WriteLine('CONNECT_FAIL ' + ($_.Exception.Message -replace '[\r\n]+', ' ')); $o.Flush()
  exit 3 }
try {
  $cc = $conn.CreateCommand()
  $cc.CommandText = $env:GR_COUNT
  $cc.CommandTimeout = [int]$env:GR_TIMEOUT
  $o.WriteLine('COUNT ' + [string]$cc.ExecuteScalar()); $o.Flush()
  $cmd = $conn.CreateCommand()
  $cmd.CommandText = $env:GR_SQL
  $cmd.CommandTimeout = [int]$env:GR_TIMEOUT
  $rdr = $cmd.ExecuteReader()
""" + PS_JSONL_ROWS + PS_JSONL_CLOSE

# The SQL type, as INFORMATION_SCHEMA.COLUMNS names it, decides what a value
# becomes in JSON. A bit is true or false, which is what SqlClient hands back
# and what the pipe-delimited dumps print as True and False.
JSON_INTS = {"tinyint", "smallint", "int", "bigint"}
JSON_DECIMALS = {"decimal", "numeric", "money", "smallmoney"}
JSON_FLOATS = {"float", "real"}
JSON_DATETIMES = {"datetime", "smalldatetime", "datetime2"}


def json_value(cell, sql_type=""):
    """One value of a PS_JSONL row line, as what it stands for in JSON.

    "-" is NULL. Anything else is base64 of UTF-8, decoded strictly: a value
    that will not decode is an error, never a guess. Numbers become numbers
    where the SQL type is numeric; a date or time becomes an ISO string, with
    no fraction of a second where the server stored none.
    """
    if cell == "-":
        return None
    s = base64.b64decode(cell, validate=True).decode("utf-8")
    ty = (sql_type or "").lower()
    if ty in JSON_INTS:
        return int(s)
    if ty == "bit":
        if s not in ("0", "1"):
            raise ValueError(f"a bit that is neither 0 nor 1: {s[:40]!r}")
        return s == "1"
    if ty in JSON_DECIMALS:
        d = decimal.Decimal(s)
        return int(d) if d.as_tuple().exponent >= 0 else float(d)
    if ty in JSON_FLOATS:
        return float(s)
    if ty == "date":
        return s[:10]
    if ty in JSON_DATETIMES:
        whole, _, frac = s.partition(".")
        frac = frac.rstrip("0")
        return whole + ("." + frac if frac else "")
    return s


def json_line(row):
    """One row as one line of JSON, UTF-8 left as it is.

    json.dumps escapes every control character, so a line break inside a value
    cannot end the line. It does not escape U+2028, U+2029 or U+0085, which
    str.splitlines() treats as line ends; they are escaped here, so a reader
    splitting on any line end still gets one row per line. The text a reader
    decodes is the same either way.
    """
    s = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    return (s.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
            .replace("\x85", "\\u0085") + "\n")


def _bridge(script, env, on_line, budget):
    """Run one bridge script, handing each line it prints to on_line.

    Returns (exit status, the end of what it said on stderr, whether it was
    stopped for running past `budget` seconds). stderr is drained as it comes,
    so a chatty failure cannot fill the pipe and hang both processes; and if
    on_line raises, or the run is interrupted, PowerShell is killed rather
    than left reading a view nobody is listening to.
    """
    import collections
    import threading
    refusal.window_check("A query of the General Court's database")   # as run()
    hold_check("A query of the General Court's database")
    proc = child.popen(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    # What the connection did, for this host's hold: whether it opened.
    link = {"failed": "", "opened": False}

    def heard(s):
        t = s.strip()
        if t.startswith("CONNECT_FAIL"):
            link["failed"] = link["failed"] or t
        elif t.startswith(("COUNT ", "COLUMNS ", "DONE ", "QUERY_FAIL")):
            link["opened"] = True
        on_line(s)
    tail = collections.deque(maxlen=40)
    drain = threading.Thread(target=lambda: tail.extend(proc.stderr), daemon=True)
    drain.start()
    late = threading.Event()

    def stop():
        late.set()
        proc.kill()

    timer = threading.Timer(budget, stop)
    timer.daemon = True
    timer.start()
    whole = False
    try:
        for raw in proc.stdout:
            heard(raw.rstrip("\r\n"))
        whole = True
    finally:
        timer.cancel()
        if not whole and proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        drain.join(timeout=10)
    if link["failed"]:
        note_connect_fail(link["failed"])
    elif link["opened"]:
        note_connected()
    return proc.returncode, "".join(tail).strip()[-400:], late.is_set()


def _verdict(got, rc, tail, late, timeout):
    """The error a finished bridge run amounts to, or None."""
    if late:
        return f"TIMEOUT no answer inside {timeout:,}s; the bridge was stopped"
    if got["err"]:
        return got["err"]
    if got["done"] is None:
        return (tail or f"no output (exit {rc})")[:300]
    if rc:
        return f"the bridge exited {rc} after its last row: {tail[:200]}"
    return None


def run_to_file_counted(connstr, count_sql, sql, path, timeout=1800,
                        every=20000, label="", newline=""):
    """run_to_file, with COUNT(*) asked first on the same connection.

    Returns (count, rows, error): the server's count, the rows PS_STREAM wrote,
    and what went wrong. The file is run_to_file's in every byte.
    """
    # Before the file is touched, as well as in _bridge: stopped for the
    # window, or by this host's hold, a run must leave what was on disk as it
    # was.
    refusal.window_check("A query of the General Court's database")
    hold_check("A query of the General Court's database")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    got = {"count": None, "done": None, "err": None}

    def line(s):
        s = s.strip()
        if s.startswith("PROGRESS "):
            print(f"    {label}{int(s[9:]):,} rows so far", flush=True)
        elif s.startswith("COUNT "):
            got["count"] = int(s[6:])
        elif s.startswith("DONE "):
            got["done"] = int(s[5:])
        elif s.startswith(("CONNECT_FAIL", "QUERY_FAIL")):
            got["err"] = got["err"] or s

    env = {"GR_CONNSTR": connstr, "GR_SQL": sql, "GR_COUNT": count_sql,
           "GR_OUT": str(path.resolve()), "GR_TIMEOUT": str(int(timeout)),
           "GR_EVERY": str(int(every)), "GR_NEWLINE": newline}
    try:
        rc, tail, late = _bridge(PS_STREAM_COUNTED, env, line, timeout + 300)
    except (OSError, ValueError) as e:
        return got["count"], got["done"], f"{type(e).__name__}: {e}"
    return got["count"], got["done"], _verdict(got, rc, tail, late, timeout)


def run_to_jsonl(connstr, count_sql, sql, path, types=None, columns=None,
                 timeout=3600, every=1000, label=""):
    """Stream one SELECT to JSON Lines, every value exactly as the server holds it.

    One object per line, the column names as keys in the order selected,
    UTF-8. `types` maps a column to its SQL type (see json_value); a column it
    does not name stays a string. `columns`, when given, is the list the
    reader must name, in order. Returns (count, rows, error): the server's
    COUNT(*), the rows written to `path`, and what went wrong.
    """
    # Before `path` is opened for writing, which empties it, as well as in
    # _bridge (run_to_file_counted says why).
    refusal.window_check("A query of the General Court's database")
    hold_check("A query of the General Court's database")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    types = {k: (v or "").lower() for k, v in (types or {}).items()}
    got = {"count": None, "done": None, "err": None, "cols": None, "rows": 0}
    env = {"GR_CONNSTR": connstr, "GR_SQL": sql, "GR_COUNT": count_sql,
           "GR_TIMEOUT": str(int(timeout)), "GR_EVERY": str(int(every))}
    with open(path, "w", encoding="utf-8", newline="\n") as out:

        def line(s):
            if s.startswith("R "):
                cols = got["cols"]
                if cols is None:
                    raise ValueError("a row arrived before the column names")
                cells = s[2:].split(",")
                if len(cells) != len(cols):
                    raise ValueError(f"row {got['rows'] + 1:,} carries {len(cells)} "
                                     f"values for {len(cols)} columns")
                out.write(json_line({c: json_value(v, types.get(c))
                                     for c, v in zip(cols, cells)}))
                got["rows"] += 1
            elif s.startswith("COLUMNS "):
                got["cols"] = [base64.b64decode(x, validate=True).decode("utf-8")
                               for x in s[8:].split(",")]
                if columns is not None and got["cols"] != list(columns):
                    raise ValueError(f"the reader named {got['cols']}, not {list(columns)}")
            elif s.startswith("PROGRESS "):
                out.flush()
                size = os.fstat(out.fileno()).st_size
                print(f"    {label}{got['rows']:,} rows so far, "
                      f"{size / 1e6:,.1f} MB", flush=True)
            elif s.startswith("COUNT "):
                got["count"] = int(s[6:])
            elif s.startswith("DONE "):
                got["done"] = int(s[5:])
            elif s.startswith(("CONNECT_FAIL", "QUERY_FAIL")):
                got["err"] = got["err"] or s

        try:
            rc, tail, late = _bridge(PS_JSONL, env, line, timeout + 300)
        except (OSError, ValueError, UnicodeDecodeError, decimal.InvalidOperation) as e:
            return got["count"], got["rows"], f"{type(e).__name__}: {str(e)[:300]}"
    err = _verdict(got, rc, tail, late, timeout)
    if not err and got["done"] != got["rows"]:
        err = (f"the reader read {got['done']:,} rows and {got['rows']:,} "
               "were written")
    return got["count"], got["rows"], err


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
    ap.add_argument("--hold", action="store_true",
                    help="say whether a hold on this host is on file; asks nobody")
    ap.add_argument("--clear-hold", action="store_true",
                    help="lift the hold on file here; asks nobody")
    a = ap.parse_args()

    if a.hold or a.clear_hold:
        d = hold_record()
        standing = hold_standing()
        if not d or not d.get("held"):
            print(f"No hold on the General Court's database is on file ({hold_file().as_posix()}).")
        elif a.clear_hold:
            _write_hold({"held": False, "nights": 0,
                         "cleared": time.strftime("%Y-%m-%dT%H:%M:%S"), "by": "a person",
                         "was": {k: d.get(k) for k in ("at", "kind", "nights", "why")}})
            print(f"Lifted here: {hold_sentence(d)}. GitHub's night keeps its own copy in the "
                  "private bucket's state/sql-held.json, which this does not touch.")
        else:
            print(("Standing: " if standing else "On file, and over: ") + hold_sentence(d) + ".")
        return 0

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
