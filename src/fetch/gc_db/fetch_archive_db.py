#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.11
"""
Every view in the General Court's public database, onto this disk.

    python3 src/fetch/gc_db/fetch_archive_db.py --list          # what it would do, no network
    python3 src/fetch/gc_db/fetch_archive_db.py                 # everything not already here
    python3 src/fetch/gc_db/fetch_archive_db.py --only NH_RSA   # one view

WHY THIS EXISTS

ARCHIVE_PLAN.md step 1. The site has been reading this database a question at
a time -- roll calls for one year, Senate reports for one term, testimony for
one session -- and each of those is a script that knows how to ask for its own
slice and nothing else. That was right while the question was whether the
database was worth using. It is settled now, so the whole of it comes local
once and the parsers work offline afterwards.

Two spans make the case on their own. `RollCallSummary` and `RollCallHistory`
run 1999 to 2026 with no gaps -- 2.3 million individual ballots, thirteen
terms of how every member voted, where the General Court's bulk download
publishes the current session only. And `Docket` holds 1989 to 2016, which is
the entire archive's sequence of events and the material every narrative on
this site is built from.

WHAT IT IS NOT

Not a crawl. This is the SQL host the General Court publishes credentials for
at gc.nh.gov/downloads, not the web server that has blocked this address
twice. It is still somebody else's machine: one connection at a time, one
view at a time, in one process, and a view already on disk is never asked for
again.

SELECT only. It never writes, never creates, never drops.

WHAT IT WRITES

  db/<view>.psv        pipe-delimited and WITH NO HEADER ROW, streamed by
                       PowerShell so a 2.3-million-row answer never crosses
                       the Python boundary
  db/_columns.json     the column order of each file, because the files
                       themselves do not carry it and a blob column is
                       renamed to <name>_bytes on the way out. Without this
                       the dumps are unreadable, which is a poor thing for
                       624 MB to be.
  db/_manifest.json    what came back, how many rows, how long it took

Nothing else is touched. In particular nothing here writes any of the JSON
files the site builds from -- turning these dumps into those is a separate
step, so that a parser can be rewritten without another round trip.

THE TWO DATABASES

`NHLegislatureDB` is the public record. `PublicNHLMS` is the drafting system
behind it. Probed: `NHLegislatureDB2` and `NHRSA` answer nothing at all, and
`PublicNHLMS` answers only some names. Two of its views are wanted and are
named below with the reason.
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
import time

import probe_db as P
import refusal

OUT = Path("db")
MANIFEST = OUT / "_manifest.json"

# The views GitHub's workflows take once the laptop has stood down: the study
# committees' meetings and details every night, their members and bills on
# Sunday nights. nightly.py names the same four, and preflight holds the two
# lists together.
GITHUB_VIEWS = ("StatStudDetails", "StatStudMembers", "StatStudMeetings",
                "vStatStudTemp")

# (view, database, order-by or "", why). Ordered smallest-first so a run that
# is going to fail on connection fails in seconds rather than after the
# 2.3-million-row one.
#
# ORDER BY matters for exactly one reason: a dump that is stable across runs
# can be diffed against the next one. Where a view has no natural key the
# column is left empty rather than guessed at.
VIEWS = [
    # -- the small vocabularies. These decide whether a parser written for
    #    2026 can read 1997, and none of them has ever been read.
    ("DocumentVersion", "PublicNHLMS", "SortOrder",
     "the version vocabulary, 54 rows against the public view's 13, with the "
     "SortOrder the bill-version switcher needs"),
    ("GeneralStatusCodes", "NHLegislatureDB", "",
     "whether the status words used before 2016 are still listed"),
    ("BodyStatusCodes", "NHLegislatureDB", "",
     "the same question for the per-chamber status"),
    ("committeeType", "NHLegislatureDB", "", "what kinds of committee exist"),
    ("hearingType", "NHLegislatureDB", "", "what kinds of hearing exist"),
    ("County", "NHLegislatureDB", "", "counties, for district labels"),
    ("Subject", "NHLegislatureDB", "", "the subject vocabulary"),
    ("Towns", "NHLegislatureDB", "", "towns to districts"),
    ("HouseDistricts", "NHLegislatureDB", "", "House districts as they stand"),
    ("senateDistricts", "NHLegislatureDB", "", "Senate districts as they stand"),
    ("DistrictPast", "NHLegislatureDB", "",
     "districts as they WERE -- a 1998 member's district is not today's, and "
     "presenting it as though it were is the error this exists to prevent"),
    ("Committees", "NHLegislatureDB", "", "committees"),
    ("CommitteeMembers", "NHLegislatureDB", "", "who sat on what"),
    ("Legislators", "NHLegislatureDB", "", "the roster, 1,081 rows"),
    ("StatStudDetails", "NHLegislatureDB", "", "statutory study committees"),
    ("StatStudMembers", "NHLegislatureDB", "", "their members"),
    ("StatStudMeetings", "NHLegislatureDB", "", "their meetings"),
    # The 28th object, and the only one this disk did not have: found by
    # comparing INFORMATION_SCHEMA against db/_manifest.json.
    # 1,545 rows joining a study committee to the bill that created it and the
    # RSA chapter it studies -- a bill-to-statute link that exists nowhere
    # else here. NHRSA, NHLegislatureDB2 and PublicNHLMS show publicuser
    # nothing at all, so with this the host is complete.
    ("vStatStudTemp", "NHLegislatureDB", "",
     "study committee to the bill that made it, and its RSA chapter"),

    # -- the current term's own record
    ("Sponsors", "NHLegislatureDB", "", "sponsors on the roster's own id"),
    ("Legislation", "NHLegislatureDB", "",
     "the 48 columns behind the bill status page"),
    ("CandH_Reports", "NHLegislatureDB", "", "committee reports, both chambers"),
    ("VHearings", "NHLegislatureDB", "",
     "hearings -- the table the upcoming-hearings feature needs"),
    ("RollCallSummary", "NHLegislatureDB", "",
     "every recorded vote, 1999-2026"),

    # -- the large ones
    ("LegislationText", "NHLegislatureDB", "",
     "every version of every current-term bill: the second text the amendment "
     "diff needs and does not have"),
    ("NH_RSA", "NHLegislatureDB", "",
     "the statutes themselves, so the RSA linker can point at the law's words"),
    ("Docket", "NHLegislatureDB", "",
     "1989-2016 and 2025-2026, the sequence of what happened to every bill"),
    ("houseRemoteTestify", "NHLegislatureDB", "",
     "402,918 testimony sign-ins, 128,854 of them with written text"),
    ("RollCallHistory", "NHLegislatureDB", "",
     "2,303,047 individual ballots, thirteen terms"),
]

# A column holding HTML or free text keeps its line breaks as spaces; see
# probe_db.run_to_file for why the default is to delete them instead.
PROSE = {"LegislationText", "NH_RSA", "CandH_Reports", "houseRemoteTestify"}

# SELECT * IS THE SAME MISTAKE AS GUESSING A FILENAME, and it was made here
# first time out. `CandH_Reports` has a PDFImage column holding the report as
# PDF bytes, and PowerShell renders a byte array as space-separated decimal
# numbers: "37 80 68 70" for "%PDF". 3,254 of 5,597 rows had reached 710 MB
# when the run was stopped, and LegislationText -- the view the amendment diff
# needs -- carries TWO such columns.
#
# So the columns are read before they are asked for. A blob is recorded as
# its length rather than its content, which keeps the fact that a document is
# there without dragging the document through a text file; text and ntext are
# cast, because the streamer writes strings.
BLOB = {"image", "varbinary", "binary", "timestamp", "rowversion"}
CAST = {"text", "ntext", "xml"}


def columns(database, view):
    """(sql, note, [column names as written]) -- the SELECT list for this
    view, blobs left behind. The names are [] where they are not known."""
    conn = connstr(database)
    rows, err = P.run(conn, [("cols",
        "SELECT COLUMN_NAME AS c, DATA_TYPE AS ty FROM INFORMATION_SCHEMA.COLUMNS "
        f"WHERE TABLE_NAME = '{view}' ORDER BY ORDINAL_POSITION")])
    if err or not rows or not (rows[0].get("rows") or []):
        # INFORMATION_SCHEMA is closed on some of these databases. A star is
        # the fallback, and it is only reached for a view small enough that
        # it has already been read once by a probe.
        return f"SELECT * FROM {view}", "columns unknown, SELECT *", []
    picked, dropped, names = [], [], []
    for c in rows[0]["rows"]:
        name, ty = c["c"], (c["ty"] or "").lower()
        if ty in BLOB:
            picked.append(f"DATALENGTH([{name}]) AS [{name}_bytes]")
            dropped.append(name)
            names.append(f"{name}_bytes")
        elif ty in CAST:
            picked.append(f"CAST([{name}] AS varchar(max)) AS [{name}]")
            names.append(name)
        else:
            picked.append(f"[{name}]")
            names.append(name)
    note = (f"{len(dropped)} blob column(s) left behind as a byte count: "
            + ", ".join(dropped)) if dropped else ""
    return "SELECT " + ", ".join(picked) + f" FROM {view}", note, names


# A VIEW IS NOT REPLACED BY ONE THAT HAS LOST A TERM NOTHING ELSE HOLDS
# (5 October 2026). The current-term views -- Legislation, LegislationText,
# CandH_Reports, Sponsors, VHearings, the testimony sign-ins -- drop a term
# when the General Court turns them over, and this wrote straight over
# db/<view>.psv, with no part file, so the late-November download would have
# taken the only database-shaped copy of 2025's 847 bill records with it.
# Now every view is written beside its copy first and swapped in only when it
# arrived; and a view that holds no row of a term the installed copy does is
# swapped in only when that term is frozen under db/term/<term>/
# (freeze_term.py --views). Otherwise the new one is left at <view>.psv.new,
# the installed copy stays, and the run says which term would have gone.
COLUMNS = OUT / "_columns.json"


def terms_lost(view, old, new, old_cols, new_cols):
    """The terms of the session years -- or the SessionIDs, read as the
    session's term -- that `old` holds rows of and `new` holds none of, by
    the column freeze_term reads each view's years from; [] for a view with
    no year.

    BY THE SESSION YEAR, NOT THE TERM (the review of 5 October 2026): a dump
    that had lost 2025's 847 Legislation rows and kept 2026's still held the
    term, so it was swapped in, and the only database-shaped copy of 2025
    went with it. A year gone is its term gone, unless the term is frozen."""
    import freeze_term as FT
    import proceedings as PR
    if view not in FT.VIEW_YEAR or not old.exists() or not old_cols or not new_cols:
        return []
    _, was = FT.view_rows(old, old_cols, view)
    _, now = FT.view_rows(new, new_cols, view)
    gone = set(was) - set(now)
    return sorted({PR.term_of(k) if re.fullmatch(r"\d{4}", k) else PR.session_term(".")
                   for k in gone} - {""})


# AND NOT BY ONE THAT CAME BACK FAR SHORTER (the review of 5 October 2026):
# LegislationText is keyed on an internal SessionID and VHearings on nothing
# that names a year, so neither could lose a term by the rule above, and
# either was swapped in empty. A current-term view at less than SHRINK_MOST
# of its installed rows goes in only where the session's term is frozen
# under db/term/<term>/ with that view.
CURRENT_TERM = ("Legislation", "LegislationText", "CandH_Reports", "Sponsors", "VHearings",
                "houseRemoteTestify", "DocumentVersion")
SHRINK_MOST = 0.5


def far_shorter(view, old, new):
    """(installed rows, tonight's) where `new` is a current-term view at less
    than SHRINK_MOST of `old`'s lines, else None."""
    if view not in CURRENT_TERM or not old.exists():
        return None

    def n(p):
        with open(p, encoding="utf-8", errors="replace") as fh:
            return sum(1 for ln in fh if ln.strip())
    a, b = n(old), n(new)
    return (a, b) if a and b < a * SHRINK_MOST else None


def frozen_holds(view, term):
    """Whether db/term/<term>/ holds this view, as freeze_term wrote it."""
    try:
        rec = json.loads((OUT / "term" / term / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    files = rec.get("files") or {}
    return f"{view}.psv" in files or f"extra/{view}.psv" in files


def connstr(database):
    return (f"Server={P.HOST};Database={database};User ID={P.USER};"
            f"Password={P.PASSWORD};Encrypt=False;"
            "TrustServerCertificate=True;Connect Timeout=30")


def load_manifest():
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true",
                    help="print the plan and make no connection")
    ap.add_argument("--only", action="append", default=[],
                    help="one view name; repeatable")
    ap.add_argument("--refetch", action="store_true",
                    help="ask again for views already on disk")
    ap.add_argument("--timeout", type=int, default=3600,
                    help="seconds for one view (default an hour)")
    a = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    man = load_manifest()
    todo = [v for v in VIEWS if not a.only or v[0] in a.only]
    if a.only:
        unknown = set(a.only) - {v[0] for v in VIEWS}
        if unknown:
            raise SystemExit(f"not a view here: {', '.join(sorted(unknown))}")
    # Two writers of one file is how the older copy wins. Once GitHub owns the
    # study-committee views, a dump on the laptop takes everything else.
    if not a.list and refusal.stood_down() is not None:
        theirs = [v[0] for v in todo if v[0] in GITHUB_VIEWS]
        todo = [v for v in todo if v[0] not in GITHUB_VIEWS]
        if theirs:
            print(f"  left to GitHub's workflows, which own them since the "
                  f"stand-down: {', '.join(theirs)}")
        if not todo:
            refusal.stand_down("fetch_archive_db.py for the study-committee views",
                               "GitHub's nightly and weekly jobs take them now.")

    print("=" * 72)
    print("The General Court's public database, onto this disk")
    print("=" * 72)
    print(f"  host      {P.HOST}")
    print(f"  out       {OUT}/")
    print(f"  views     {len(todo)}")
    print()

    if a.list:
        for name, db, order, why in todo:
            path = OUT / f"{name}.psv"
            state = "held" if path.exists() and not a.refetch else "wanted"
            print(f"  [{state:6}] {db}.{name}")
            print(f"            {why}")
        print("\n  Nothing was asked for and nothing was written.")
        return

    done = skipped = failed = 0
    t0 = time.time()
    for i, (name, db, order, why) in enumerate(todo, 1):
        path = OUT / f"{name}.psv"
        if path.exists() and not a.refetch:
            print(f"[{i}/{len(todo)}] {name}: already here "
                  f"({path.stat().st_size:,} bytes)", flush=True)
            skipped += 1
            continue
        sql, note, names = columns(db, name)
        if order:
            sql += f" ORDER BY {order}"
        print(f"[{i}/{len(todo)}] {name}: {why}", flush=True)
        if note:
            print(f"          {note}", flush=True)
        started = time.time()
        part = path.with_name(path.name + ".part")
        rows, err = P.run_to_file(
            connstr(db), sql, part, timeout=a.timeout,
            label=f"{name}: ", newline=" " if name in PROSE else "")
        took = time.time() - started
        if err:
            # A view that is not in this database is a fact worth recording,
            # not a crash. The run keeps going. The installed copy, if there
            # is one, is not touched.
            print(f"          FAILED after {took:.0f}s: {err[:180]}", flush=True)
            man[name] = {"database": db, "error": err[:400],
                         "seconds": round(took, 1)}
            failed += 1
            part.unlink(missing_ok=True)
        else:
            cols = json.loads(COLUMNS.read_text(encoding="utf-8")) if COLUMNS.exists() else {}
            lost = [t for t in terms_lost(name, path, part, cols.get(name), names)
                    if not frozen_holds(name, t)]
            short = far_shorter(name, path, part)
            import proceedings as PR
            if short and frozen_holds(name, PR.session_term(".")):
                short = None
            if lost or short:
                held = path.with_name(path.name + ".new")
                os.replace(part, held)
                why = (f"it holds no row of {', '.join(lost)}, which {path} does" if lost else
                       f"it is {short[1]:,} lines against the {short[0]:,} of {path}")
                print(f"          NOT INSTALLED: {why}, and no db/term/<term>/ holds the term. "
                      f"Freeze the term first (python3 src/lib/freeze_term.py --views); what came back is at "
                      f"{held}", flush=True)
                failed += 1
                continue
            os.replace(part, path)
            if names:
                cols[name] = names
                tmp = COLUMNS.with_name(COLUMNS.name + ".part")
                tmp.write_text(json.dumps(cols, indent=1), encoding="utf-8")
                os.replace(tmp, COLUMNS)
            size = path.stat().st_size if path.exists() else 0
            print(f"          {rows:,} rows, {size:,} bytes, {took:.0f}s",
                  flush=True)
            man[name] = {"database": db, "rows": rows, "bytes": size,
                         "seconds": round(took, 1),
                         "fetched": time.strftime("%Y-%m-%dT%H:%M:%S")}
            done += 1
        MANIFEST.write_text(json.dumps(man, indent=1), encoding="utf-8")

    print()
    print("=" * 72)
    print(f"  {done} fetched, {skipped} already here, {failed} failed, "
          f"{time.time() - t0:.0f}s")
    total = sum(v.get("bytes", 0) for v in man.values())
    print(f"  {total / 1e6:.1f} MB in {OUT}/")
    if failed:
        print("  A failure is recorded in the manifest with its message. A view "
              "that\n  is not in that database is not an error to fix.")
    print("=" * 72)


if __name__ == "__main__":
    main()
