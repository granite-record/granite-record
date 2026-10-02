#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-12.6
"""
What changed at the General Court between two copies of its bulk files.

    python3 gc_changes.py                       # the archive's last two versions of each file
    python3 gc_changes.py --against-installed   # the archive's newest vs what the build reads now
    python3 gc_changes.py --out reports/gc-changes-2026-09-13.md
    python3 gc_changes.py --db-night 2026-10-02 # a night whose files came from the database

No network. It reads nh-archive/ (snapshot_gencourt.py's content-addressed
store and its index of which version each day had) and, with
--against-installed, the files at the repository root that the build reads.

WHY. The nightly fetches fourteen files, and a person -- or the session that
reads reader reports -- wants to know in a minute what the legislature did
that day: a hearing scheduled, a bill signed or vetoed, a roll call taken, a
status changed. The files are live views that are overwritten as a session
moves, so the difference between two nights is the only place that
information exists as "what happened today".

This is the General Court's own record, not a reader's words, so it is not
screened the way reader reports are. It is still quoted as data: every docket
line is shown as the clerk wrote it, inside a code block.

A NIGHT THE EXPORT FAILED (1 October 2026). When the General Court's export
comes back empty the nightly rebuilds the day's files from its database
(dayfiles_from_db.py) and keeps them in nh-archive/from-db/<day>/. Compared
line for line with an export they would report 13,060 docket lines as new --
the export's seventh column, when a row was last changed, is not in the
database's view. So --db-night DAY compares that night's files with the
files they replaced -- an export, or an earlier database night's, found by
the sha256 the night recorded (db_pair) -- on the columns both sources carry,
and the report's heading says which source it was.

A CHANGED BILL RECORD SAYS WHAT CHANGED (2 October 2026). The first database
night's files would have been reported as "0 new, 16 changed" bill records
and no more. The 16 were one column, the House status code, which no page is
built from, and which may be the database's word against the export's
rather than anything the General Court did (dayfiles_from_db.py's
docstring). Every changed record is now listed under the columns that
moved. Where one side of the comparison is the database's, a record that
differs only in columns the build does not read (dayfiles_from_db.LSR_READ)
is left out of the count and listed below it, as that. Between two exports
every column is the export's own and every change is counted, as before.

THE EXPORT NIGHT AFTER ONE. It compared the archive's last two exports, and
so repeated every docket line the database night had reported: 31, on the
first. An export night now looks for a database night since the export
before (after_db_night) and, finding one, compares with that night's copy on
the columns both carry: what is reported is what has happened since. The
bill records are compared whole there: the Senate status code in a database
night's copy is the export's own (dayfiles_from_db.py never writes the
view's), so a change in it is something the General Court did, and it was
being left out of both lists. Each section says, under its own heading,
when its older side is a database night's copy; said once at the top, it
was printed above sections that compared two exports.

WHAT THE NIGHT'S CHECKS COUNTED (2 October 2026). A database night's files
are installed only if dayfiles_from_db.judge() lets them through, and under
its ceilings a few rows may still differ from the installed ones: a docket
row gone or reworded, a ballot cast otherwise, a member's party, a sponsor
added to an old bill. The night's page says how many. Which ones is said
here, row by row, from the same judge() on the same two sets of files: the
morning's reader is the one who can tell a clerk's correction from a view
gone wrong.
"""

import argparse
import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ARCHIVE = Path("nh-archive")

# Docket actions worth a line of their own, in the order a reader cares.
KINDS = [
    ("signed, vetoed or became law", re.compile(
        r"signed by (the )?governor|vetoed|veto sustained|veto overridden|chaptered|"
        r"became law|law without signature|effective date", re.I)),
    ("roll call", re.compile(r"\bRC\b|roll call", re.I)),
    ("hearing or session scheduled", re.compile(
        r"public hearing|executive session|work session|hearing:|subcommittee", re.I)),
    ("committee report", re.compile(r"committee report|ought to pass|inexpedient|"
                                    r"interim study|refer for", re.I)),
    ("introduced or referred", re.compile(r"introduced|referred to|re-referred", re.I)),
]
PER_KIND = 25
# The three files a report compares.
COMPARED = ("Docket.txt", "RollCallSummary.txt", "LSRs.txt")


def lines_of(data):
    text = data.decode("utf-8", "replace").lstrip("".join(map(chr, (0xFEFF,))))
    return [ln.rstrip("\r") for ln in text.split("\n") if ln.strip()]


def blob(digest):
    with gzip.open(ARCHIVE / "store" / f"{digest}.gz", "rb") as fh:
        return fh.read()


def versions(name):
    idx = json.loads((ARCHIVE / "index.json").read_text(encoding="utf-8"))
    return idx.get(name, {}).get("history", [])


def pair(name, against_installed):
    """(old_label, old_bytes, new_label, new_bytes) or None when there is no pair."""
    hist = versions(name)
    if against_installed:
        root = Path(name)
        if not hist or not root.exists():
            return None
        return ("installed at the root", root.read_bytes(),
                f"archived {hist[-1][0]}", blob(hist[-1][1]))
    if len(hist) < 2:
        return None
    return (f"archived {hist[-2][0]}", blob(hist[-2][1]),
            f"archived {hist[-1][0]}", blob(hist[-1][1]))


def whole(ln):
    return ln


def db_pair(name, day):
    """(old_label, old_bytes, new_label, new_bytes) for a night whose files
    came from the database, or None: that night's copy against the file it
    replaced.

    The night's source.json names what it replaced by sha256 ("replaced",
    nightly.keep_db_copy), and the copy with those bytes is found by it: an
    export in the archive's store, or an earlier database night's. A copy that
    does not say is compared by date: with the newest export archived BEFORE
    that day, or an earlier database night as new as it.

    Before that day, because snapshot_gencourt.py writes every file that
    arrives whole into the index, on a night it installs nothing too: on a
    night some of the export arrived (20 and 28 September), the archive's
    newest Docket.txt was that night's own, and this compared the database's
    files with a copy nobody had installed.
    """
    root = ARCHIVE / "from-db"
    mine = root / day / f"{name}.gz"
    if not mine.exists():
        return None

    def gz(path):
        with gzip.open(path, "rb") as fh:
            return fh.read()

    def source(d):
        try:
            rec = json.loads((root / d / "source.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return rec if isinstance(rec, dict) else {}

    def of_db(d):
        return (f"from the database {d}", gz(root / d / f"{name}.gz"))
    new = (f"from the database {day}", gz(mine))
    hist = versions(name)
    earlier = sorted(d.name for d in root.iterdir()
                     if d.is_dir() and d.name < day and (d / f"{name}.gz").exists())
    replaced = source(day).get("replaced")
    digest = replaced.get(name) if isinstance(replaced, dict) else None
    if digest:
        nights = [d for d in earlier
                  if ((source(d).get("files") or {}).get(name) or {}).get("sha256") == digest]
        days = [h[0] for h in hist if h[1] == digest
                and (ARCHIVE / "store" / f"{digest}.gz").exists()]
        if nights and (not days or nights[-1] >= days[-1]):
            return of_db(nights[-1]) + new
        if days:
            return (f"archived {days[-1]}", blob(digest)) + new
    hist = [h for h in hist if h[0] < day]
    if earlier and (not hist or earlier[-1] >= hist[-1][0]):
        return of_db(earlier[-1]) + new
    if not hist:
        return None
    return (f"archived {hist[-1][0]}", blob(hist[-1][1])) + new


def after_db_night(name):
    """(old_label, old_bytes, new_label, new_bytes) for an export night that
    follows a database night, or None when none came between: the newest
    database night's copy, made since the export before the archive's newest,
    against that newest.

    "Since" counts the day of the export before. On a night some of the
    export arrives whole and nothing is installed, snapshot_gencourt.py
    writes the docket that arrived into the archive's history and the night
    builds from the database all the same: it is the database's files that
    were installed, and reported on."""
    hist = versions(name)
    root = ARCHIVE / "from-db"
    if not hist or not root.is_dir():
        return None
    first = hist[-2][0] if len(hist) > 1 else ""
    nights = sorted(d.name for d in root.iterdir()
                    if d.is_dir() and first <= d.name <= hist[-1][0]
                    and (d / f"{name}.gz").exists())
    if not nights:
        return None
    with gzip.open(root / nights[-1] / f"{name}.gz", "rb") as fh:
        was = fh.read()
    return (f"from the database {nights[-1]}", was,
            f"archived {hist[-1][0]}", blob(hist[-1][1]))


def night_checks(day, DF):
    """The section of a database night's report that names what its checks
    counted: [lines], or [] when the seven files of that night and the seven
    they replaced are not all on disk. The files are installed by now, and a
    report that is not written makes the night unclean: whatever goes wrong
    here is said in the section, and the rest of the report stands."""
    L = ["## What the night's checks counted",
         "(the seven files the night installed against the seven they replaced, by "
         "dayfiles_from_db.judge(); the rows are the General Court's, quoted as written)", ""]
    try:
        pairs = {name: db_pair(name, day) for name in DF.DAY_FILES}
        if not all(pairs.values()):
            return []
        try:
            src = json.loads((ARCHIVE / "from-db" / day / "source.json").read_text(
                encoding="utf-8"))
        except (OSError, ValueError):
            src = {}
        src = src if isinstance(src, dict) else {}
        got = DF.judge({n: p[3] for n, p in pairs.items()}, {n: p[1] for n, p in pairs.items()},
                       {"asked": src.get("asked"), "nights": src.get("nights")})
    except Exception as e:                                      # noqa: BLE001
        return L + [f"Not read here ({type(e).__name__}): the night's verdict has them, under "
                    "day_files, held and told.", ""]
    L += ["- " + ln.strip() for ln in DF.held_said(got["held"])]
    for what, rows in got["told"].items():
        L += ["", f"### {what}", "", "```"] + list(rows) + ["```"]
    if not got["told"]:
        L += ["", "Nothing under a ceiling needed naming."]
    for s in got["stops"]:
        L += ["", f"A check that stops this pair as it is read here: {s}"]
    return L + [""]


def docket(old, new, key=whole):
    """New docket lines, grouped by kind, each kept as the clerk wrote it.
    key: what makes two lines the same line (the whole of it, unless one side
    came from the database)."""
    before = {key(ln) for ln in lines_of(old)}
    added = [ln for ln in lines_of(new) if key(ln) not in before]
    groups = defaultdict(list)
    bills = Counter()
    for ln in added:
        f = ln.split("|")
        bill = f[3].strip() if len(f) > 3 else "?"
        text = f[5].strip() if len(f) > 5 else ln
        bills[bill] += 1
        kind = next((k for k, pat in KINDS if pat.search(text)), "other")
        groups[kind].append((bill, text))
    return added, groups, bills


def rollcalls(old, new):
    before = set(lines_of(old))
    out = []
    for ln in lines_of(new):
        if ln in before:
            continue
        f = ln.split("|")
        if len(f) > 12:
            out.append(f"{f[1]} #{f[2]} {f[3].split(' ')[0]}  {f[4] or '(no bill)'}  "
                       f"{f[12]}  {f[5]}-{f[6]}")
    return out


def lsrs(old, new, key=whole):
    """Bills whose record line changed, keyed by session and LSR: ([new
    bills], [changed bills], {changed bill: [the columns that differ, from
    0]})."""
    def keyed(data):
        return {tuple(ln.split("|")[:2]): ln for ln in lines_of(data)}
    a, b = keyed(old), keyed(new)
    added = [k for k in b if k not in a]
    changed = [k for k in b if k in a and key(a[k]) != key(b[k])]
    def bill(k):
        f = b[k].split("|")
        return f[10] if len(f) > 10 and f[10] else "-".join(k)
    def columns(k):
        x, y = a[k].split("|"), b[k].split("|")
        return [i for i in range(max(len(x), len(y)))
                if (x[i] if i < len(x) else None) != (y[i] if i < len(y) else None)]
    return ([bill(k) for k in added], [bill(k) for k in changed],
            {bill(k): columns(k) for k in changed})


def by_columns(bills, cols, names):
    """The changed bill records, a line for each set of columns that moved:
    "- House status code (16): HB224, HB660, ..."."""
    groups = defaultdict(list)
    for b in bills:
        groups[", ".join(names.get(i, f"column {i + 1}") for i in cols[b])].append(b)
    return [f"- {what} ({len(who)}): " + ", ".join(who[:40])
            + (f" ... and {len(who) - 40} more" if len(who) > 40 else "")
            for what, who in sorted(groups.items(), key=lambda g: (-len(g[1]), g[0]))]


def report(against_installed=False, db_night=None):
    # dayfiles_from_db.py says what a bill record's columns are called and,
    # for a pair one side of which is the database's, which columns both
    # sources carry. A night whose files are all the export's needs only the
    # names, and is written without them ("column 17") if that module will
    # not import: the report is one of the things a night must have written
    # to be clean, and an export's night does not hang on the fallback's code.
    try:
        import dayfiles_from_db as DF
    except Exception:                                           # noqa: BLE001
        if db_night:
            raise
        DF = None
    names = DF.LSR_NAMES if DF else {}
    L = [f"# What changed at the General Court, {date.today().isoformat()}", ""]
    # A pair is (old label, old bytes, new label, new bytes, whether a side
    # is the database's).
    docket_key, lsr_key = ((DF.shared_columns("Docket.txt"), DF.shared_columns("LSRs.txt"))
                           if DF else (whole, whole))
    # Under a section whose older side is a database night's copy, on an
    # export's night.
    after = ("The older side is a database night's copy: compared on the columns both sources "
             "carry, so what that night reported is not repeated here.")
    if db_night:
        def pick(name):
            p = db_pair(name, db_night)
            return p and p + (True,)
        got = {name: pick(name) for name in COMPARED}
        L += ["**From the General Court's database, not its bulk files**: the export came "
              f"back empty on the night of {db_night}, and the day's files were rebuilt from "
              "the database's views. Compared by gc_changes.py on the columns both sources "
              "carry. The docket lines are the clerk's, quoted as written.", ""]
    else:
        def pick(name):
            p = None if against_installed or DF is None else after_db_night(name)
            if p:
                return p + (True,)
            p = pair(name, against_installed)
            return p and p + (False,)
        got = {name: pick(name) for name in COMPARED}
        L += ["From the General Court's bulk files, compared by gc_changes.py. The docket "
              "lines are the clerk's, quoted as written.", ""]
    any_pair = False
    p = got["Docket.txt"]
    if p:
        any_pair = True
        added, groups, bills = docket(p[1], p[3], docket_key if p[4] else whole)
        L += [f"## Docket: {len(added):,} new lines on {len(bills):,} bills",
              f"({p[0]} -> {p[2]})"] + ([after] if p[4] and not db_night else []) + [""]
        for kind in [k for k, _ in KINDS] + ["other"]:
            rows = groups.get(kind, [])
            if not rows:
                continue
            L += [f"### {kind} -- {len(rows)}", "", "```"]
            L += [f"{b:<10} {t[:160]}" for b, t in rows[:PER_KIND]]
            if len(rows) > PER_KIND:
                L.append(f"... and {len(rows) - PER_KIND} more")
            L += ["```", ""]
    p = got["RollCallSummary.txt"]
    if p:
        any_pair = True
        rc = rollcalls(p[1], p[3])
        L += [f"## Roll calls: {len(rc)} new",
              f"({p[0]} -> {p[2]})"] + ([after] if p[4] and not db_night else []) + [""]
        if rc:
            L += ["```"] + rc[:40] + ([f"... and {len(rc) - 40} more"] if len(rc) > 40 else []) + ["```"]
        L.append("")
    p = got["LSRs.txt"]
    if p:
        any_pair = True
        # A database night's own files are compared without the Senate
        # status code, which is never the view's. The export after one is
        # compared whole: that code in the night's copy was the export's own.
        new_bills, changed, cols = lsrs(p[1], p[3], lsr_key if p[4] and db_night else whole)
        # Where one side is the database's, a record that differs only in
        # columns the build does not read is not counted: it may be one
        # source's word against the other's, and nothing that happened.
        apart = []
        if p[4]:
            if db_night:
                cols = {b: [i for i in c if i != DF.LSR_SENATE_STATUS] for b, c in cols.items()}
            apart = [b for b in changed if not any(i in DF.LSR_READ for i in cols[b])]
            changed = [b for b in changed if b not in set(apart)]
        L += [f"## Bill records: {len(new_bills)} new, {len(changed)} changed",
              f"({p[0]} -> {p[2]})"] + ([after] if p[4] and not db_night else []) + [""]
        if new_bills:
            L.append("new: " + ", ".join(new_bills[:60]))
        if changed:
            L += ["changed, by what changed:"] + by_columns(changed, cols, names)
        if apart and db_night:
            L += [f"not counted: {len(apart)} that differ only in columns no page is built "
                  "from, which between the database and an export may be one source's word "
                  "against the other's:"] + by_columns(apart, cols, names)
        elif apart:
            # The export's own word, tonight. What it is set against is the
            # database's for every column but the Senate status code.
            L += [f"not counted: {len(apart)} that differ from the database night's copy only "
                  "in columns no page is built from (the Senate status code there was the "
                  "export's own; the rest were the database's word):"]
            L += by_columns(apart, cols, names)
        L.append("")
    if db_night:
        L += night_checks(db_night, DF)
    if not any_pair:
        L += ["Nothing to compare: the archive has fewer than two versions of these files"
              + (" or the build has none installed." if against_installed else "."), ""]
    return "\n".join(L)


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", default="nh-archive")
    ap.add_argument("--against-installed", action="store_true")
    ap.add_argument("--db-night", metavar="DAY",
                    help="a night whose files came from the database: its copy in "
                         "<archive>/from-db/DAY/ against the files it replaced, on the columns "
                         "both sources carry")
    ap.add_argument("--out")
    a = ap.parse_args()
    global ARCHIVE
    ARCHIVE = Path(a.archive)
    md = report(a.against_installed, a.db_night)
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8", newline="\n")
        print(f"-> {out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
