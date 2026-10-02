#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-01.4
"""
The day's records from the General Court's database, into .night/dbday/.

    python3 fetch_day_db.py --plan     # the statements it would send; no connection
    python3 fetch_day_db.py            # ask, then say what the rebuilt day files would
                                       # change against the files installed here
    python3 fetch_day_db.py --fetch-only   # ask, and leave the comparison to the caller

THIS ASKS THE GENERAL COURT'S SQL HOST. Not the web server that blocked this
address twice: the host the General Court publishes read-only credentials for
at its downloads page (probe_db.py names them and their source). It is still
somebody else's machine. Run it by hand only when the person has said to.

WHY THIS EXISTS

On 27 and 28 September and 1 October 2026 the General Court's bulk-file export
came back empty on every try and nothing was built. The person approved the
night asking the database, gently, as the fallback. nightly.py starts this
when, and only when, the export came back empty -- since 2 October 2026 on
its first try (nightly.DB_AFTER_TRIES), and until then on its sixth -- with
no refusal from the web server and no hold on this host on file, and once a
night at most. This fetches;
dayfiles_from_db.py, which asks nobody, reshapes what came back into the
seven day files and guards them; nightly.py installs.

WHAT IT ASKS, AND HOW GENTLY

Eleven connections, one after another, PAUSE seconds apart, each one
PowerShell process holding one connection that asks SELECT COUNT(*) and then
one SELECT, through probe_db.run_to_file_counted:

    six views the day's files are rebuilt from, the roster whole and the other
    five from the installed files' first session year on (so a newer year in
    the database is seen rather than assumed away): about 170,000 rows on the
    files of 6 September, 131,199 of them the session's ballots
    five lookups, whole, about 200 rows: compared with the installed lookups,
    and never installed

Every column is named, in the order of the dump in db/, so a renamed column
fails the query loudly and the reshaper reads the same positions it was
measured on. Smallest first, so a host that will not connect is found out in
seconds. No retry of anything, the same night.

WHAT STOPS IT

    this host's own hold      archive/sql-held.json (probe_db.py): a connection
                              that failed on an earlier night. Exit 5
    GitHub's night window     on a stood-down laptop (probe_db asks
                              refusal.window_check before every query). Exit 4
    another fetch             archive/.lock, through refusal.hold(): one fetch
                              at a time, and under the nightly its lock is the
                              parent's. Exit 3
    a connection that fails   recorded as this host's hold on GitHub's machine,
                              and nothing more is asked. Exit 3
    a query that fails, or a  of one of the six: nothing more is asked, and
    view that arrives short   the views are not usable. Exit 1. Of a lookup:
                              said, and the rest go on. Short is fewer rows
                              than the server counted a moment before; more
                              is a row entered meanwhile, and is said

The web server's refusal record does not govern this host, and this never
calls refusal.check(): a refusal there is a different problem with a different
cause. nightly.py will not START this with a refusal on file, which is the
person's rule about carrying on by another door.

WHAT IT WRITES

Only under .night/dbday/, the nightly's scratch folder, which this empties
first: <view>.psv for each view that arrived whole, and source.json saying
when each was asked, what the server counted and what was written. Never
db/*.psv: those are the laptop's files in the kit, and one file has one writer.
SELECT only. It never writes to the database, and does not test whether it
could.
"""

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import dayfiles_from_db as DF
import probe_db as P
import refusal

OUT = DF.VIEWS_DIR                  # .night/dbday, and nowhere else
DATABASE = P.DATABASE
PAUSE = 4.0                         # seconds between connections
# Seconds a view's query may take. The whole of RollCallHistory, 2.3 million
# rows, took 95 on 8 September; tonight's is a twentieth of it. A host too
# slow for this is the host that timed the export out, and is not asked twice.
TIMEOUT = 120
# The views that may honestly answer with no rows: a session that has taken no
# roll call yet, or signed no sponsor. Where the installed file has rows and
# the database gives none, dayfiles_from_db's guards stop the night.
MAY_BE_EMPTY = ("Sponsors", "RollCallSummary", "RollCallHistory")

# Smallest first.
ORDER = ("Legislators", "RollCallSummary", "Sponsors", "Legislation", "Docket",
         "RollCallHistory")
LOOKUP_ORDER = ("GeneralStatusCodes", "County", "Subject", "Committees", "BodyStatusCodes")


def connstr():
    return (f"Server={P.HOST};Database={DATABASE};User ID={P.USER};"
            f"Password={P.PASSWORD};Encrypt=False;"
            "TrustServerCertificate=True;Connect Timeout=30")


def statements(view, first_year=None):
    """(count, select) for one view: every column named, and the rows of
    `first_year` on where the view has a session year."""
    cols = DF.VIEWS.get(view) or DF.LOOKUPS[view]
    where = ""
    if first_year is not None:
        year = int(first_year)                  # a number, or no statement at all
        where = f" WHERE [{DF.YEAR_COLUMN[view]}] >= {year}"
    return (f"SELECT COUNT(*) FROM [{view}]{where}",
            "SELECT " + ", ".join(f"[{c}]" for c in cols) + f" FROM [{view}]{where}")


def plan(sc):
    """[(view, count, select, needed)] for tonight, from the installed files' years."""
    out = []
    for view in ORDER:
        year = sc["ask"].get(view) if view in DF.YEAR_COLUMN else None
        out.append((view,) + statements(view, year) + (True,))
    for view in LOOKUP_ORDER:
        out.append((view,) + statements(view) + (False,))
    return out


def scan(path, width):
    """(lines, lines that are not `width` columns wide) of a file just written."""
    n = bad = 0
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line:
                continue
            n += 1
            if line.count("|") != width - 1:
                bad += 1
    return n, bad


def write_source(src):
    tmp = OUT / (DF.SOURCE + ".part")
    tmp.write_text(json.dumps(src, indent=1) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(OUT / DF.SOURCE)


def fetch(todo, held, pause):
    """Ask for each view in turn. (exit status, source record)."""
    src = {"asked": datetime.now().isoformat(timespec="seconds"), "host": P.HOST,
           "database": DATABASE, "views": {}}
    conn = connstr()
    status = 0
    for i, (view, count_sql, sql, needed) in enumerate(todo):
        if i:
            time.sleep(pause)
        if not held.still():
            print(f"  stopping before {view}: the lock this runs under is gone, or GitHub's "
                  "night window has opened.", flush=True)
            status = status or 3
            break
        if P.hold_standing():
            print(f"  stopping before {view}: {P.hold_sentence(P.hold_standing())}.", flush=True)
            status = status or 3
            break
        cols = DF.VIEWS.get(view) or DF.LOOKUPS[view]
        part = OUT / f"{view}.psv.part"
        entry = {"asked": datetime.now().isoformat(timespec="seconds"), "needed": needed}
        t0 = time.time()
        count, rows, err = P.run_to_file_counted(conn, count_sql, sql, part, timeout=TIMEOUT,
                                                 every=50000, label=f"{view}: ")
        entry["seconds"] = round(time.time() - t0, 1)
        entry["count"], entry["rows"] = count, rows
        if not err:
            lines, bad = scan(part, len(cols)) if part.exists() else (0, 0)
            if count is None:
                err = "the server gave no count"
            elif not DF.arrived_whole(count, rows):
                # Fewer than it counted. More is a row entered while the view
                # was read, and is the view (dayfiles_from_db.arrived_whole).
                err = f"{rows or 0:,} rows were written and the server counted {count:,}"
            elif lines != rows:
                err = f"the file holds {lines:,} lines for {rows:,} rows"
            elif bad:
                err = f"{bad:,} of its lines are not {len(cols)} columns wide"
            elif needed and not rows and view not in MAY_BE_EMPTY:
                err = "the view answered with no rows"
        if err:
            entry["error"] = str(err)[:300]
            part.unlink(missing_ok=True)
            print(f"  FAIL  {view}: {str(err)[:200]}", flush=True)
            src["views"][view] = entry
            write_source(src)
            if str(err).startswith("CONNECT_FAIL"):
                print("        the host could not be connected to. Nothing more is asked.",
                      flush=True)
                status = 3
                break
            if needed:
                print("        one of the six the day's files are rebuilt from. Nothing more "
                      "is asked, and nothing is asked again tonight.", flush=True)
                status = 1
                break
            continue
        part.replace(OUT / f"{view}.psv")
        print(f"  ok    {view:20} {rows:>8,} rows, {entry['seconds']:.0f}s"
              + (f"; the server had counted {count:,}: {rows - count:,} entered while it "
                 "was read" if rows > count else ""), flush=True)
        src["views"][view] = entry
        write_source(src)
    src["finished"] = datetime.now().isoformat(timespec="seconds")
    src["rows"] = sum(e.get("rows") or 0 for e in src["views"].values() if not e.get("error"))
    write_source(src)
    return status, src


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--installed", default=".",
                    help="where the last good day's files are installed: their session "
                         "years are the ones asked for (default here)")
    ap.add_argument("--plan", action="store_true",
                    help="print the statements and make no connection")
    ap.add_argument("--fetch-only", action="store_true",
                    help="ask and write the views; leave the comparison to the caller")
    ap.add_argument("--pause", type=float, default=PAUSE,
                    help=f"seconds between connections (default {PAUSE:g})")
    a = ap.parse_args()

    try:
        sc = DF.scope(DF.installed_files(a.installed))
    except DF.Problem as e:
        print(f"NOT ASKED: {e}.")
        return 1
    todo = plan(sc)

    print("=" * 72)
    print("The day's records, from the General Court's database")
    print("=" * 72)
    print(f"  host      {P.HOST}, database {DATABASE}, SELECT only")
    print(f"  years     the docket's {', '.join(sc['docket'])}; the session's "
          f"{', '.join(sc['session'])} (the installed files')")
    print(f"  out       {OUT.as_posix()}/")
    if a.plan:
        for view, count_sql, sql, needed in todo:
            print(f"\n  {view}{'' if needed else '  (a lookup: compared, never installed)'}")
            print(f"    {count_sql}")
            print(f"    {sql}")
        print(f"\n{len(todo)} connections, one at a time, {a.pause:g}s apart, each a COUNT and "
              "one SELECT. Nothing was asked and nothing was written.")
        return 0

    P.hold_check("The day's records from the database")
    with refusal.hold("the day's records from the database") as held:
        shutil.rmtree(OUT, ignore_errors=True)
        OUT.mkdir(parents=True, exist_ok=True)
        status, src = fetch(todo, held, a.pause)
    got = [v for v, e in src["views"].items() if not e.get("error")]
    print(f"\n{len(got)} of {len(todo)} views arrived whole, {src['rows']:,} rows, in "
          f"{len(src['views'])} connections.")
    if status:
        print("The views are not all here, so the day's files cannot be rebuilt from them.")
        return status
    if a.fetch_only:
        return 0

    # By hand: what the rebuilt files would change. Nothing is installed.
    try:
        files, facts = DF.rebuild(OUT, a.installed)
        result = DF.judge(files, DF.installed_files(a.installed), facts)
    except DF.Problem as e:
        print(f"\nNOT REBUILT: {e}.")
        return 1
    print(f"\nThe seven day files rebuilt from them, against the files installed in "
          f"{Path(a.installed).as_posix()}/:")
    for ln in DF.report(result, facts, DF.lookup_notes(OUT, a.installed)):
        print(ln)
    DF.write_all(files, OUT / "files")
    print(f"They are in {(OUT / 'files').as_posix()}/ to read. Nothing was installed.")
    return 1 if result["stops"] else 0


if __name__ == "__main__":
    sys.exit(main())
