#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-26.1
"""
Six views of past sessions in the General Court's public database, onto this
disk, each whole or not at all.

    python3 fetch_past_db.py --list                 # the plan and what is here; no connection
    python3 fetch_past_db.py                        # every view not already here
    python3 fetch_past_db.py --only PastDocket      # one view; a comma list or repeats for more
    python3 fetch_past_db.py --only PastDocket --refetch

WHAT THE VIEWS ARE

The General Court's IT office has added six views to NHLegislatureDB, the
database it publishes a read-only account for at gc.nh.gov/downloads, and
they were first read here on 26 September 2026. By their names and columns
they carry past sessions' record in the shape of the current term's views
that db/ already holds:

  PastSponsors           sponsors by employee number, with prime
                         sponsor, sign-off and withdrawal         144,565 rows
  PastLegislation        the bill record, 47 columns               34,084
  PastAmendments         amendment text                             7,958
  PastDocket             the docket                               677,618
  PastCommitteeReports   committee reports, as HTML                20,379
  PastLegislationText    bill text as HTML and as plain text,
                         with a VersionID                          39,089

The rows are what the views held on 26 September. A run asks COUNT(*) again
and checks each file against that answer, never against these. Which
sessions the views reach back to, and what a VersionID distinguishes, has
not been read yet; take both from the files once they are here, not from a
guess in this paragraph.

WHY A FOLDER AND A MANIFEST OF ITS OWN

db/_manifest.json belongs to GitHub's nightly now: it installs the study
committees' views and their entries there every night (nightly.take_views),
and two writers of one file is how the older copy wins. These dumps are a
one-off job the laptop keeps -- archive/runs-in-the-cloud.json says the
laptop "keeps the one-off jobs" -- so they live in db/past/ with
db/past/_manifest.json, which nothing else writes. db/ is gitignored, so none
of it reaches the public repository.

WHAT IT WRITES

  db/past/PastSponsors.psv, PastLegislation.psv, PastDocket.psv
        pipe-delimited with NO HEADER ROW, exactly as fetch_archive_db.py
        writes db/*.psv, through the same PS_STREAM: a pipe inside a value
        becomes a space, a line break inside one is deleted, and CRLF ends a
        line. That loses nothing a sponsor list, a bill record or a docket
        line needs.
  db/past/PastLegislationText.jsonl, PastAmendments.jsonl,
  PastCommitteeReports.jsonl
        JSON Lines, UTF-8, one object per row, the column names as keys in
        the view's own order. Bill text and reports hold pipes, line breaks,
        tabs and quotes, which the pipe-delimited convention would change;
        these keep every character (probe_db.run_to_jsonl says how). NULL is
        null; a number is a number where the SQL type is numeric; a bit is
        true or false; a date is an ISO string.
  db/past/_manifest.json
        for each view: rows, the server's count, bytes, sha256, seconds, the
        columns in file order with their SQL types, the SELECT, and when. For
        the .psv files it is the only record of the column order.

WHOLE OR NOT AT ALL

For each view: COUNT(*) and then the rows, on one connection; streamed into
<file>.part; checked -- the rows written equal the count, the file holds that
many lines, and every .psv line has one field per column -- and only then
renamed into place, in one step. Anything short leaves the .part where it is,
named, and stops the run with a non-zero exit; the next run starts that view
again and skips every file already complete. An empty view is a failure too:
all six had rows on 26 September. A file already complete -- on disk, and
the manifest agrees about its size and its count -- is not asked for again
unless --refetch.

WHAT IT WILL NOT DO

Ask anything but SELECT, or ask it of anything but these six views and
INFORMATION_SCHEMA.COLUMNS. Every statement is built from the allow-list in
VIEWS and passes select_only() before it is sent, and preflight holds the
script to that. It never writes, creates or drops anything, there or here
outside db/past/, and never SELECT *: a column is asked for by name, and a
blob, should one appear, as its length.

Crawl gc.nh.gov. This is the SQL host the General Court publishes the
account for, not the web server that has blocked this address twice, so
refusal.check() is not its business. It is still somebody else's machine:
one view at a time, one connection each (and one before them for the columns
of all of them), five seconds between views, smallest first so that a run
that is going to fail on connecting fails in seconds, and no ORDER BY --
sorting 900 MB of text for our convenience would be work on their server.

Run on GitHub. GITHUB_ACTIONS=true stops it before anything; its files are
the laptop's.

Run beside another fetch. It takes archive/.lock through refusal.hold(), as
the web fetchers do, so the lane and this never ask the General Court at the
same time.

Feed the site. Nothing reads db/past/ yet. Turning these into site data is a
separate step, so that a parser can be rewritten without another round trip.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import fetch_archive_db as FA
import probe_db as P
import refusal

OUT = Path("db") / "past"
MANIFEST = OUT / "_manifest.json"
DATABASE = P.DATABASE
PAUSE = 5                    # seconds between two views
SEEN_ON = "26 September 2026"

# The allow-list: the only names a statement here may read. Smallest first.
# (view, format, rows on 26 September, about how big, seconds allowed, what)
# The text views' sizes are the server's own totals; the .psv sizes are
# ESTIMATES, from bytes per row of the current term's dumps in db/.
VIEWS = (
    ("PastSponsors", "psv", 144_565, "about 7 MB, an estimate", 1800,
     "sponsors of past sessions' bills, by employee number"),
    ("PastLegislation", "psv", 34_084, "about 14 MB, an estimate", 1800,
     "the bill record of past sessions, 47 columns"),
    ("PastAmendments", "jsonl", 7_958, "about 42 MB", 3600,
     "amendment text"),
    ("PastDocket", "psv", 677_618, "about 90 MB, an estimate", 3600,
     "the docket of past sessions"),
    ("PastCommitteeReports", "jsonl", 20_379, "about 249 MB", 7200,
     "committee reports, as HTML"),
    ("PastLegislationText", "jsonl", 39_089, "about 905 MB (613 MB of HTML, "
     "292 MB of text)", 14400,
     "past bills' text, as HTML and as plain text"),
)
NAMES = tuple(v[0] for v in VIEWS)
SPEC = {v[0]: v for v in VIEWS}
CATALOGUE = "INFORMATION_SCHEMA.COLUMNS"

# A blob is asked for as its length, never its bytes: fetch_archive_db learned
# that from 710 MB of "37 80 68 70". text is cast to varchar(max) as it does;
# ntext and xml to nvarchar(max), which keeps what varchar(max) would not.
BLOB = FA.BLOB
WIDE = {"ntext", "xml"}


# ---- SELECT and nothing else ------------------------------------------------

_BRACKETED = re.compile(r"\[(?:[^\]]|\]\])*\]")
_LITERAL = re.compile(r"'(?:[^']|'')*'")
_NOT_READ = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|MERGE|TRUNCATE|"
    r"GRANT|REVOKE|DENY|INTO|DECLARE|SET|USE|BACKUP|RESTORE|BULK|DBCC|SHUTDOWN|"
    r"KILL|WAITFOR|RECONFIGURE|OPENROWSET|OPENQUERY|OPENDATASOURCE|OPENXML|"
    r"JOIN|UNION|APPLY|EXCEPT|INTERSECT|GO)\b", re.I)
# What may stand before a "(": the three functions, the two types a cast names,
# and the catalogue question's IN list.
_CALLS = {"COUNT", "CAST", "DATALENGTH", "VARCHAR", "NVARCHAR", "IN"}


def quote(name):
    """A column name as a bracketed identifier, whatever it holds."""
    return "[" + name.replace("]", "]]") + "]"


def select_only(sql):
    """`sql` if it is one SELECT reading one of VIEWS or the catalogue.

    Anything else raises ValueError before it can be sent. Identifiers in
    brackets and string literals are set aside first, so a column name the
    catalogue hands back cannot pass for SQL; what is left must be a single
    SELECT with one FROM, naming an allowed view, calling nothing but COUNT,
    CAST and DATALENGTH, with no comment, no second statement, no variable
    and no star but COUNT(*)'s. A literal is allowed only in the catalogue
    question, and only as one of the six names.
    """
    bare = _BRACKETED.sub("[]", sql)
    literals = [x[1:-1] for x in _LITERAL.findall(bare)]
    bare = _LITERAL.sub("''", bare)
    why = None
    if not re.match(r"\s*SELECT\s", bare, re.I):
        why = "it is not a SELECT"
    elif re.search(r"\[(?!\])|(?<!\[)\]", bare) or "'" in bare.replace("''", ""):
        why = "an identifier or a literal is not closed"
    elif re.search(r";|--|/\*|\*/|@|#|\\", bare):
        why = "it holds a statement end, a comment, a variable or a temporary table"
    elif _NOT_READ.search(bare):
        why = f"it says {_NOT_READ.search(bare).group(0)}"
    elif bare.replace("COUNT(*)", "").count("*"):
        why = "it asks for *, which is how a blob came through as text"
    else:
        called = {c.upper() for c in re.findall(r"([A-Za-z_]\w*)\s*\(", bare)}
        froms = re.findall(r"\bFROM\s+([A-Za-z_][\w.]*)", bare, re.I)
        if called - _CALLS:
            why = "it calls " + ", ".join(sorted(called - _CALLS))
        elif len(froms) != 1 or len(re.findall(r"\bFROM\b", bare, re.I)) != 1:
            why = "it does not read exactly one thing"
        elif froms[0] not in NAMES + (CATALOGUE,):
            why = f"{froms[0]} is not one of the six views"
        elif literals and froms[0] != CATALOGUE:
            why = "a literal in a SELECT from a view"
        elif any(x not in NAMES for x in literals):
            why = "the catalogue is asked about something other than the six views"
    if why:
        raise ValueError(f"not sent, because {why}: {sql[:160]}")
    return sql


def catalogue_sql(views):
    """The one question asked before the views: every column of each, in order."""
    bad = [v for v in views if v not in NAMES]
    if bad:
        raise ValueError(f"not one of the six views: {', '.join(bad)}")
    names = ", ".join(f"'{v}'" for v in views)
    return select_only(
        "SELECT TABLE_SCHEMA AS s, TABLE_NAME AS v, COLUMN_NAME AS c, "
        "DATA_TYPE AS ty, ORDINAL_POSITION AS n "
        f"FROM {CATALOGUE} WHERE TABLE_NAME IN ({names}) "
        "ORDER BY TABLE_NAME, ORDINAL_POSITION")


def statements(view, cols):
    """(count_sql, sql, names, types) for one view.

    `cols` is [(column, SQL type)] in the view's order, as the catalogue gave
    it. `names` is the column list of the file and `types` their SQL types,
    after a blob has become <name>_bytes and text has been cast.
    """
    if view not in NAMES:
        raise ValueError(f"not one of the six views: {view}")
    if not cols:
        raise ValueError(f"no columns for {view}")
    picked, names, types = [], [], []
    for name, ty in cols:
        ty = (ty or "").lower()
        q = quote(name)
        if ty in BLOB:
            picked.append(f"DATALENGTH({q}) AS {quote(name + '_bytes')}")
            names.append(name + "_bytes")
            types.append("bigint")
        elif ty == "text":
            picked.append(f"CAST({q} AS varchar(max)) AS {q}")
            names.append(name)
            types.append("varchar")
        elif ty in WIDE:
            picked.append(f"CAST({q} AS nvarchar(max)) AS {q}")
            names.append(name)
            types.append("nvarchar")
        else:
            picked.append(q)
            names.append(name)
            types.append(ty)
    return (select_only(f"SELECT COUNT(*) AS n FROM {view}"),
            select_only("SELECT " + ", ".join(picked) + f" FROM {view}"),
            names, types)


# ---- what is on disk --------------------------------------------------------

def path_for(view):
    return OUT / f"{view}.{SPEC[view][1]}"


def part_for(view):
    p = path_for(view)
    return p.with_name(p.name + ".part")


def load_manifest():
    if not MANIFEST.exists():
        return {}
    try:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except ValueError as e:
        # Not an empty manifest: that would refetch a gigabyte. A person looks.
        raise SystemExit(f"{MANIFEST.as_posix()} will not parse ({e}). Nothing was asked "
                         "for. Mend it or move it aside, then run this again.")
    return man if isinstance(man, dict) else {}


def save_manifest(man):
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_name(MANIFEST.name + ".tmp")
    tmp.write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, MANIFEST)


def complete(view, man):
    """On disk, and the manifest agrees about its size and its count."""
    e, p = man.get(view) or {}, path_for(view)
    return (p.exists() and isinstance(e.get("rows"), int) and e["rows"] > 0
            and e.get("rows") == e.get("count") and e.get("bytes") == p.stat().st_size)


def scan(path, fmt, ncols):
    """(lines, sha256, bytes, lines with the wrong number of fields, first such)."""
    h, lines, size, bad, first = hashlib.sha256(), 0, 0, 0, None
    with open(path, "rb") as fh:
        if fmt == "psv":
            for line in fh:
                h.update(line)
                size += len(line)
                lines += line.endswith(b"\n")
                if line.rstrip(b"\r\n").count(b"|") != ncols - 1:
                    bad += 1
                    first = first or lines + (not line.endswith(b"\n"))
        else:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
                size += len(chunk)
                lines += chunk.count(b"\n")
    return lines, h.hexdigest(), size, bad, first


# ---- asking -----------------------------------------------------------------

def catalogue(conn, views):
    """({view: [(column, type)]}, error) -- one connection, one question."""
    try:
        results, err = P.run(conn, [("columns", catalogue_sql(views))])
    except Exception as e:  # a timeout, or no PowerShell
        return None, f"{type(e).__name__}: {e}"
    if err:
        return None, err
    block = (results or [{}])[0]
    if block.get("error"):
        return None, block["error"]
    rows = block.get("rows") or []
    if isinstance(rows, dict):
        rows = [rows]
    by = {n.lower(): n for n in NAMES}
    found, schemas = {}, {}
    for r in rows:
        view = by.get(str(r.get("v") or "").lower())
        if view:
            schemas.setdefault(view, set()).add(r.get("s"))
            found.setdefault(view, []).append(
                (int(r.get("n") or 0), str(r.get("c")), str(r.get("ty") or "")))
    twice = [v for v, s in schemas.items() if len(s) > 1]
    if twice:
        return None, ("more than one schema has a view named "
                      + ", ".join(twice) + "; which one is meant is not a guess to make")
    return {v: [(c, t) for _, c, t in sorted(cols)] for v, cols in found.items()}, None


def fetch(view, cols, man, conn, allowed):
    """One view, whole or not at all. (ok, rows, bytes)."""
    fmt, seen, _about, _secs, why = SPEC[view][1:]
    final, part = path_for(view), part_for(view)
    print(f" {view}: {why}", flush=True)
    if not cols:
        return fail(view, man, "it is not in INFORMATION_SCHEMA.COLUMNS, so its "
                    "columns are unknown; SELECT * is not a fallback here, because the "
                    "column order is what makes the file readable", part)
    count_sql, sql, names, types = statements(view, cols)
    OUT.mkdir(parents=True, exist_ok=True)
    part.unlink(missing_ok=True)
    every = max(500, seen // 25)
    started = time.time()
    if fmt == "psv":
        count, rows, err = P.run_to_file_counted(
            conn, count_sql, sql, part, timeout=allowed, every=every,
            label=f"{view}: ", newline="")
    else:
        count, rows, err = P.run_to_jsonl(
            conn, count_sql, sql, part, types=dict(zip(names, types)),
            columns=names, timeout=allowed, every=every, label=f"{view}: ")
    took = time.time() - started
    if err:
        return fail(view, man, err, part)
    lines, sha, size, bad, first = scan(part, fmt, len(names))
    problems = []
    if count is None:
        problems.append("the server gave no count")
    elif count == 0:
        problems.append(f"the view answered with no rows; it had {seen:,} on "
                        f"{SEEN_ON}, so an empty answer is a failure, not a result")
    elif rows != count:
        problems.append(f"{rows or 0:,} rows were written and the server counted "
                        f"{count:,}: the stream came up short")
    if lines != (rows or 0):
        problems.append(f"the file holds {lines:,} lines for {rows or 0:,} rows")
    if bad:
        problems.append(f"{bad:,} lines do not have {len(names)} fields "
                        f"(the first is line {first:,})")
    if problems:
        return fail(view, man, "; ".join(problems), part)
    os.replace(part, final)
    entry = {"file": final.name, "format": fmt, "database": DATABASE,
             "rows": rows, "count": count, "bytes": size, "sha256": sha,
             "seconds": round(took, 1), "columns": names, "types": types,
             "select": sql, "fetched": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if fmt == "psv":
        entry["header"] = False
    if count < seen:
        entry["note"] = (f"{count:,} rows where the view held {seen:,} on {SEEN_ON}; "
                         "a past session's record shrinking is worth asking about")
    man[view] = entry
    save_manifest(man)
    print(f"    {rows:,} rows, the count was {count:,}; {size:,} bytes, "
          f"{took:.0f}s, sha256 {sha[:16]}", flush=True)
    if entry.get("note"):
        print(f"    NOTE: {entry['note']}", flush=True)
    return True, rows, size


def fail(view, man, why, part):
    """Say what went wrong, keep what came, record it; the run stops here."""
    print(f"    FAILED: {why[:400]}", flush=True)
    kept = None
    if part.exists():
        if part.stat().st_size == 0:
            part.unlink()
        else:
            kept = part.as_posix()
            print(f"    {kept} is left where it is ({part.stat().st_size:,} bytes) "
                  "for a person to look at; the next run starts this view again "
                  "and replaces it.", flush=True)
    if not kept:
        print("    Nothing of this view was written.", flush=True)
    entry = dict(man.get(view) or {})
    entry["last_error"] = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                           "error": why[:600], "part": kept}
    man[view] = entry
    save_manifest(man)
    return False, 0, 0


# ---- the run ----------------------------------------------------------------

def pick(only):
    """The views asked for, in the allow-list's order; ValueError for a stranger."""
    if not only:
        return list(NAMES)
    asked = [x.strip() for o in only for x in o.split(",") if x.strip()]
    by = {n.lower(): n for n in NAMES}
    unknown = [x for x in asked if x.lower() not in by]
    if unknown:
        raise ValueError(f"not one of the six views: {', '.join(unknown)}. "
                         f"They are {', '.join(NAMES)}.")
    want = {by[x.lower()] for x in asked}
    return [n for n in NAMES if n in want]


def show_plan(views, man, refetch):
    for view in views:
        fmt, seen, about, secs, why = SPEC[view][1:]
        p, part, e = path_for(view), part_for(view), man.get(view) or {}
        if complete(view, man):
            state = "refetch" if refetch else "here"
            size = f"{e['rows']:,} rows, {e['bytes']:,} bytes, fetched {e.get('fetched')}"
        else:
            state = "wanted"
            size = f"{seen:,} rows on {SEEN_ON}, {about}"
        print(f"  [{state:7}] {p.name:28} {size}")
        print(f"            {why}; up to {secs // 60} minutes")
        if part.exists():
            print(f"            a failed run left {part.name} "
                  f"({part.stat().st_size:,} bytes)")
        if e.get("last_error"):
            print(f"            last failure, {e['last_error'].get('at')}: "
                  f"{str(e['last_error'].get('error'))[:120]}")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Dump the six Past* views of NHLegislatureDB into db/past/.")
    ap.add_argument("--list", action="store_true",
                    help="print the plan and what is already here; connect to nothing")
    ap.add_argument("--only", action="append", default=[],
                    help="a view, or several separated by commas; repeatable")
    ap.add_argument("--refetch", action="store_true",
                    help="ask again for a view whose file is already complete")
    ap.add_argument("--timeout", type=int, default=0,
                    help="seconds allowed for each view, in place of its own allowance")
    a = ap.parse_args(argv)

    if os.environ.get("GITHUB_ACTIONS") == "true":
        print("fetch_past_db.py does not run on GitHub: its files are the laptop's "
              "one-off dump, and GitHub's machine keeps nothing. Nothing was asked "
              "for and nothing was written.", file=sys.stderr)
        return 3
    try:
        views = pick(a.only)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    man = load_manifest()
    held = [v for v in views if complete(v, man)]
    wanted = [v for v in views if a.refetch or v not in held]
    skipped = [v for v in views if v not in wanted]

    print("=" * 72)
    print("Past sessions from the General Court's public database, onto this disk")
    print("=" * 72)
    print(f"  host      {P.HOST}, database {DATABASE}, SELECT only")
    print(f"  out       {OUT.as_posix()}/  (its own manifest: {MANIFEST.name})")
    print(f"  views     {len(views)}: {len(held)} complete here, {len(wanted)} to fetch")
    print()

    if a.list:
        show_plan(views, man, a.refetch)
        print(f"\n  {len(views)} views: {len(held)} complete here, {len(wanted)} to "
              "fetch. Nothing was asked for and nothing was written.")
        return 0

    for v in skipped:
        print(f"  {v}: already here ({man[v]['rows']:,} rows, "
              f"{man[v]['bytes']:,} bytes); --refetch to ask again", flush=True)
    fetched, failed, rows, size = [], None, 0, 0
    t0 = time.time()
    if wanted:
        lock = refusal.hold("fetch_past_db.py")
        try:
            lock.__enter__()
        except SystemExit as e:
            print(f"\n  0 fetched, {len(skipped)} already here: another fetch holds "
                  "archive/.lock, so nothing was asked for.")
            return e.code if isinstance(e.code, int) else 3
        try:
            conn = FA.connstr(DATABASE)
            cat, err = catalogue(conn, wanted)
            if err:
                failed = "the catalogue"
                print(f"  the columns could not be read, so no view was asked for: "
                      f"{str(err)[:300]}", flush=True)
            else:
                for i, view in enumerate(wanted):
                    if i:
                        time.sleep(PAUSE)
                    print(f"\n[{i + 1}/{len(wanted)}]", end="", flush=True)
                    ok, n, b = fetch(view, cat.get(view), man, conn,
                                     a.timeout or SPEC[view][4])
                    if not ok:
                        failed = view
                        break
                    fetched.append(view)
                    rows, size = rows + n, size + b
        finally:
            lock.__exit__(None, None, None)

    left = len(wanted) - len(fetched) - (1 if failed in wanted else 0)
    print()
    print("=" * 72)
    print(f"  {len(fetched)} fetched, {len(skipped)} already here, "
          f"{1 if failed else 0} failed, {left} not reached; {rows:,} rows and "
          f"{size / 1e6:,.1f} MB put in place, in {time.time() - t0:,.0f}s")
    if failed == "the catalogue":
        print("  Stopped before the first view, because the columns could not be "
              "read. Nothing was written.")
    elif failed:
        print(f"  Stopped at {failed}. Its failure is in {MANIFEST.as_posix()} with its "
              "message; run this again to go on from there.")
    print("=" * 72)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
