#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.1
"""
The bill-version vocabulary, reshaped out of the database dump already on disk.

    python3 document_versions_from_db.py

Reads db/DocumentVersion.psv and writes db/document_versions.json: every
version label the General Court uses, with the chambers that use it, the
sessions it appears in, and the SortOrder that puts a bill's versions in the
order they actually happened. build_bill_versions.py reads it, and
build_all.py declares it as a need.

ASKS NOBODY ANYTHING. Standard library, no network, like docket_from_db.py,
rollcalls_from_db.py and testimony_from_db.py beside it. The fetching was done
once by fetch_archive_db.py, which dumps the view; this only reshapes what
that left on the disk.

WHY THIS SCRIPT EXISTS

db/ is gitignored -- 400 MB, re-fetchable in one run -- and the ignore rule is
right about every file in it but this one. document_versions.json was not
produced by any script: it was made by hand once, from a query asked by column
name, and nothing could rebuild it. So `db/document_versions.json` was a
declared dependency of build_all with no generator anywhere in the repository,
which a fresh clone cannot satisfy and cannot be told how to satisfy. That is
a hole in the open-source release rather than an inconvenience: the step it
gates writes the manifest that tells each bill's page how many versions it
has, and without it every one of the 2,234 current-term bills draws a Versions
tab with a 404 behind the 1,085 that have one.

WHY IT READS THE PSV BY POSITION AND NOT BY NAME

db/_columns.json describes DocumentVersion with 10 columns and the dump has
16. The view lives in PublicNHLMS, whose INFORMATION_SCHEMA publicuser cannot
read, so fetch_archive_db fell back to the 13-column view of the same name in
NHLegislatureDB for its column list. Reading the file against that catalogue
gives nonsense -- which is the whole reason the JSON was made separately in
the first place. The four fields used here are taken by position and asserted
against the data, so a shape change fails loudly instead of writing rubbish.

A LABEL IS NOT UNIQUE. 54 rows collapse to 36 labels: the same label is issued
to more than one chamber, and to more than one session. The chambers and
sessions are collected rather than one of them chosen, which is why those two
fields are lists.
"""

import json
from pathlib import Path

DB = Path("db")
SRC = DB / "DocumentVersion.psv"
OUT = DB / "document_versions.json"

# Field positions in the dump. Named here so the assertions below can say what
# was expected when a column moves.
ID, SESSION, CHAMBER, LABEL = 0, 1, 2, 3
SORT = 6
WIDTH = 16

# The chambers the view actually uses: House, Senate, and L for a drafting
# version that belongs to neither.
CHAMBERS = {"H", "S", "L"}


def rows():
    """Every row of the dump, as a list of fields, with the shape checked."""
    text = SRC.read_text(encoding="utf-8", errors="replace")
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        f = line.split("|")
        # A row that is not the width this was written for is not a row this
        # can read. Say so with the line number rather than guessing.
        if len(f) < WIDTH:
            raise SystemExit(
                f"{SRC} line {n} has {len(f)} fields, not {WIDTH}. The dump's "
                "shape changed; the positions at the top of this file are "
                "what needs revisiting, not the data.")
        out.append(f)
    return out


def main():
    if not SRC.exists():
        raise SystemExit(
            f"{SRC} is not on this disk. It comes from fetch_archive_db.py, "
            "which reads the SQL host the General Court publishes credentials "
            "for -- ask before running it.")

    by_label = {}
    for f in rows():
        label = f[LABEL].strip()
        if not label:
            continue
        chamber, session, sort = f[CHAMBER].strip(), f[SESSION].strip(), f[SORT].strip()
        if chamber not in CHAMBERS:
            raise SystemExit(
                f"{SRC}: chamber {chamber!r} on the row for {label!r} is not "
                f"one of {sorted(CHAMBERS)}. Read the row before widening this.")
        try:
            sort_n = int(sort)
        except ValueError:
            raise SystemExit(
                f"{SRC}: SortOrder {sort!r} on the row for {label!r} is not a "
                "number. Field 6 is where SortOrder was; check the dump.")

        e = by_label.setdefault(label, {"chambers": [], "sessions": [], "sort": sort_n})
        if chamber not in e["chambers"]:
            e["chambers"].append(chamber)
        if session not in e["sessions"]:
            e["sessions"].append(session)
        # THE LOWEST WINS where one label carries two. The sort is what orders
        # a bill's versions on the page, and the earliest position a label can
        # occupy is the one that keeps the sequence honest.
        e["sort"] = min(e["sort"], sort_n)

    # A run that reads the file and finds nothing is a failure, not an empty
    # vocabulary -- the rule this project keeps about silent success.
    if not by_label:
        raise SystemExit(f"{SRC} produced no labels. That is a failed read.")

    out = {k: by_label[k] for k in sorted(by_label)}
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"{len(out)} version labels -> {OUT}")
    print(f"  from {len(rows())} rows in {SRC}")
    print("  build_bill_versions.py reads this; build_all.py declares it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
