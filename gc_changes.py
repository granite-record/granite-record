#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-12.2
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
database's view -- and 29 bills as changed, for a Senate status code the two
sources have always disagreed on. So --db-night DAY compares that night's
files with the newest export, or with an earlier database night newer than
it, on the columns both sources carry, and the report's heading says which
source it was. The next export night compares export with export as ever, and
so repeats what the database night reported: correct, if repetitive.
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
    came from the database, or None: that night's copy against the newest
    export, or against an earlier database night newer than that export."""
    root = ARCHIVE / "from-db"
    mine = root / day / f"{name}.gz"
    if not mine.exists():
        return None

    def gz(path):
        with gzip.open(path, "rb") as fh:
            return fh.read()
    hist = versions(name)
    earlier = sorted(d.name for d in root.iterdir()
                     if d.is_dir() and d.name < day and (d / f"{name}.gz").exists())
    if earlier and (not hist or earlier[-1] > hist[-1][0]):
        return (f"from the database {earlier[-1]}", gz(root / earlier[-1] / f"{name}.gz"),
                f"from the database {day}", gz(mine))
    if not hist:
        return None
    return (f"archived {hist[-1][0]}", blob(hist[-1][1]), f"from the database {day}", gz(mine))


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
    """Bills whose record line changed, keyed by session and LSR."""
    def keyed(data):
        return {tuple(ln.split("|")[:2]): ln for ln in lines_of(data)}
    a, b = keyed(old), keyed(new)
    added = [k for k in b if k not in a]
    changed = [k for k in b if k in a and key(a[k]) != key(b[k])]
    def bill(k):
        f = b[k].split("|")
        return f[10] if len(f) > 10 and f[10] else "-".join(k)
    return [bill(k) for k in added], [bill(k) for k in changed]


def report(against_installed=False, db_night=None):
    L = [f"# What changed at the General Court, {date.today().isoformat()}", ""]
    if db_night:
        # The columns both sources carry, as dayfiles_from_db.py compares them.
        import dayfiles_from_db as DF
        docket_key, lsr_key = DF.shared_columns("Docket.txt"), DF.shared_columns("LSRs.txt")

        def pick(name):
            return db_pair(name, db_night)
        L += ["**From the General Court's database, not its bulk files**: the export came "
              f"back empty on the night of {db_night}, and the day's files were rebuilt from "
              "the database's views. Compared by gc_changes.py on the columns both sources "
              "carry. The docket lines are the clerk's, quoted as written.", ""]
    else:
        docket_key = lsr_key = whole

        def pick(name):
            return pair(name, against_installed)
        L += ["From the General Court's bulk files, compared by gc_changes.py. The docket "
              "lines are the clerk's, quoted as written.", ""]
    any_pair = False
    p = pick("Docket.txt")
    if p:
        any_pair = True
        added, groups, bills = docket(p[1], p[3], docket_key)
        L += [f"## Docket: {len(added):,} new lines on {len(bills):,} bills",
              f"({p[0]} -> {p[2]})", ""]
        for kind in [k for k, _ in KINDS] + ["other"]:
            rows = groups.get(kind, [])
            if not rows:
                continue
            L += [f"### {kind} -- {len(rows)}", "", "```"]
            L += [f"{b:<10} {t[:160]}" for b, t in rows[:PER_KIND]]
            if len(rows) > PER_KIND:
                L.append(f"... and {len(rows) - PER_KIND} more")
            L += ["```", ""]
    p = pick("RollCallSummary.txt")
    if p:
        any_pair = True
        rc = rollcalls(p[1], p[3])
        L += [f"## Roll calls: {len(rc)} new", f"({p[0]} -> {p[2]})", ""]
        if rc:
            L += ["```"] + rc[:40] + ([f"... and {len(rc) - 40} more"] if len(rc) > 40 else []) + ["```"]
        L.append("")
    p = pick("LSRs.txt")
    if p:
        any_pair = True
        new_bills, changed = lsrs(p[1], p[3], lsr_key)
        L += [f"## Bill records: {len(new_bills)} new, {len(changed)} changed",
              f"({p[0]} -> {p[2]})", ""]
        if new_bills:
            L.append("new: " + ", ".join(new_bills[:60]))
        if changed:
            L.append("changed: " + ", ".join(changed[:80])
                     + (f" ... and {len(changed) - 80} more" if len(changed) > 80 else ""))
        L.append("")
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
                         "<archive>/from-db/DAY/ against the newest export, on the columns "
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
