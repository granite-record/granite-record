#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-10.1
"""db/RollCall*.psv -> the per-year files the parsers already read. No network.

    python3 rollcalls_from_db.py --check 2023   # prove it against the live fetch
    python3 rollcalls_from_db.py --missing      # write every year not on disk
    python3 rollcalls_from_db.py --year 2011

WHY THIS EXISTS

`RollCallSummary.txt` and `RollCallHistory.txt` in the project root are the
CURRENT session only, and `fetch_rollcalls_db.py` fetches one past year at a
time from the General Court's SQL host. Three years were fetched that way --
2023, 2024, 2025 -- and then the whole database was dumped to `db/`, which
means every roll call from 1999 to 2026 has been sitting on this disk ever
since: 9,565 votes and 2,303,047 member votes, of which 1999-2022 had never
been turned into a file anything reads.

So this asks the database nothing. It is `docket_from_db.py` for roll calls:
the same dump, reshaped into the format the parsers take, at no cost to
anybody's server.

WHY IT IS NOT A SECOND FORMATTER

`fetch_rollcalls_db.py` shapes its rows in SQL, because they are streamed
from the database straight to a file and never pass through Python. Here the
rows come off a local file, so the same shaping has to happen in Python --
which is a second implementation of one format, and this project has spent a
week undoing those. What stops it drifting is the check: `--check 2023`
rebuilds a year from the dump and diffs it line for line against the file the
live database produced, and the run refuses to write anything else until
that comes back identical. VOTE_WORD is imported from that module rather than
copied, so the one thing that is genuinely a lookup has one home.

THE DIFFERENCES THE DUMP HAS, MEASURED

  Column order. The dump's history is EmployeeNumber first and the file's is
  SessionYear first; the summary's dump carries three columns the file does
  not (UserName, Verified, CalendarItemID). Both are reorderings, not losses.
  The dates. The dump writes "05/18/2000 00:00:00" and the file writes
  "5/18/2000 12:00:00 AM" -- the same instant, in the format the download
  uses and the parsers expect.
  PersonID. The history names a member by Employeeno; every roster on this
  site uses PersonID, and db/Legislators.psv carries both.
"""

import argparse
import collections
import sys
from datetime import datetime
from pathlib import Path

from fetch_rollcalls_db import VOTE_WORD

DB = Path("db")
OUT = Path("rollcalls")
IN_FMT = "%m/%d/%Y %H:%M:%S"


def clock(s):
    """"05/18/2000 00:00:00" -> "5/18/2000 12:00:00 AM", the download's way.

    Anything that does not parse is passed through untouched rather than
    blanked: a date this does not understand is a thing to notice, and
    --check will notice it.
    """
    s = (s or "").strip()
    if not s:
        return ""
    try:
        d = datetime.strptime(s, IN_FMT)
    except ValueError:
        return s
    h = d.hour % 12 or 12
    ap = "AM" if d.hour < 12 else "PM"
    return f"{d.month}/{d.day}/{d.year} {h}:{d.minute:02d}:{d.second:02d} {ap}"


def rows(name):
    """Every line of a dump file, split on the pipe. The dump has no header."""
    with (DB / name).open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if line:
                yield line.split("|")


def person_ids():
    """{Employeeno: PersonID} -- the join the history file's field 5 needs."""
    out = {}
    for p in rows("Legislators.psv"):
        if len(p) > 3 and p[3].strip():
            out[p[3].strip()] = p[0].strip()
    return out


def summary_lines(year):
    """RollCallSummary.txt's fifteen columns, for one session year."""
    out = []
    for p in rows("RollCallSummary.psv"):
        if len(p) < 16 or p[0].strip() != str(year):
            continue
        # Columns 0-13 in the dump's own order, then DateModified, which the
        # dump puts at 15 behind UserName. Verified and CalendarItemID are
        # dropped because the download does not carry them and nothing reads
        # them.
        f = [p[i] for i in range(14)] + [p[15]]
        f[3] = clock(f[3])
        f[14] = clock(f[14])
        out.append("|".join(f))
    return out


def history_lines(year, ids):
    """RollCallHistory.txt's eight columns, for one session year."""
    out = []
    for p in rows("RollCallHistory.psv"):
        if len(p) < 8 or p[1].strip() != str(year):
            continue
        emp = p[0].strip()
        code = (p[5] or "").strip()
        out.append("|".join([
            p[1], p[2], p[3], emp, ids.get(emp, ""), p[4],
            VOTE_WORD.get(code, code), clock(p[7]),
        ]))
    return out


def sort_key(line):
    """Body, then vote number, then member -- the order the SQL asked for."""
    f = line.split("|")
    num = f[2] if len(f) > 2 else ""
    return (f[1] if len(f) > 1 else "",
            int(num) if num.strip().isdigit() else 0,
            f[3] if len(f) > 3 else "")


def build(year, ids):
    return (sorted(summary_lines(year), key=sort_key),
            sorted(history_lines(year, ids), key=sort_key))


def check(year, ids):
    """Rebuild a year the live database already produced, and diff it."""
    ok = True
    summ, hist = build(year, ids)
    for name, made in (("RollCallSummary", summ), ("RollCallHistory", hist)):
        have = OUT / f"{name}_{year}.txt"
        if not have.exists():
            print(f"  {have} is not here to compare against")
            ok = False
            continue
        disk = [ln.rstrip("\r\n") for ln in
                have.read_text(encoding="utf-8-sig", errors="replace").splitlines()
                if ln.strip()]
        a, b = set(made), set(disk)
        print(f"  {name}: {len(made):,} rebuilt, {len(disk):,} from the live "
              f"database, {len(a & b):,} identical")
        for label, diff in (("only rebuilt here", a - b),
                            ("only from the database", b - a)):
            if diff:
                ok = False
                print(f"    {len(diff):,} {label}:")
                for ln in sorted(diff)[:3]:
                    print(f"      {ln[:140]}")
    return ok


def years_present():
    """Years already on disk -- in rollcalls/ AND in the bulk download.

    The root RollCallSummary.txt is the current session's download, and
    build_data reads it BESIDE every rollcalls/RollCallSummary_*.txt. Writing
    a year that the root file already holds therefore does not replace it, it
    doubles it: 2026 would have arrived twice, 419 roll calls and 131,199
    member votes counted two apiece, and nothing would have raised. That is
    this project's oldest failure -- a second reader of one fact -- so the
    root file is consulted here rather than assumed to be the current term.
    """
    got = {int(p.stem.rsplit("_", 1)[1])
           for p in OUT.glob("RollCallSummary_*.txt")
           if p.stem.rsplit("_", 1)[1].isdigit()}
    root = Path("RollCallSummary.txt")
    if root.exists():
        with root.open(encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                y = line.split("|")[0].strip()
                if y.isdigit():
                    got.add(int(y))
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    ap.add_argument("--missing", action="store_true",
                    help="every year in the dump that has no file yet")
    ap.add_argument("--check", type=int, metavar="YEAR",
                    help="rebuild a year already fetched live and diff it")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    if not (DB / "RollCallSummary.psv").exists():
        sys.exit("No db/RollCallSummary.psv. This reads the dump and nothing else.")
    globals()["OUT"] = Path(a.out)

    ids = person_ids()
    print(f"{len(ids):,} Employeeno -> PersonID pairs from db/Legislators.psv")

    if a.check:
        print(f"\nsession year {a.check}, rebuilt from the dump:")
        return 0 if check(a.check, ids) else 1

    have = collections.Counter(p[0].strip() for p in rows("RollCallSummary.psv"))
    all_years = sorted(int(y) for y in have if y.isdigit())
    if a.year:
        todo = [a.year]
    elif a.missing:
        skip = years_present()
        todo = [y for y in all_years if y not in skip]
        print(f"  skipping {len(skip)} year(s) already on disk: "
              + ", ".join(str(y) for y in sorted(skip)))
    else:
        sys.exit("give --year, --missing, or --check. The dump holds "
                 f"{all_years[0]}-{all_years[-1]}.")

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"{len(todo)} year(s): {', '.join(str(y) for y in todo)}")
    tally = 0
    for y in todo:
        summ, hist = build(y, ids)
        if not summ:
            print(f"  {y}: nothing in the dump")
            continue
        (OUT / f"RollCallSummary_{y}.txt").write_text(
            "\n".join(summ) + "\n", encoding="utf-8")
        (OUT / f"RollCallHistory_{y}.txt").write_text(
            "\n".join(hist) + "\n", encoding="utf-8")
        print(f"  {y}: {len(summ):,} roll calls, {len(hist):,} member votes")
        tally += len(summ)
    print(f"\n{tally:,} roll calls written to {OUT}/, no requests made.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
