#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.1
"""
Is every journal file in its session's folder, and is no file two files?

    python3 src/checks/journal_folders.py            # the OK line, or each file out of place
    python3 src/checks/journal_folders.py --detail   # and the evidence for every file

Reads journals/ and journals_senate/ on this disk. No network, nothing written.

WHY (29-30 October 2026)

The readers key a folder to one session's numbered series: that calendar
year's sittings, plus the Organization Day of the December before, which is
the series' No. 1 (session_days.journal_series, journal_days.read_day). The
General Court's own index filed thirteen 2011 issues under its 2010 folder
and two 1999 issues under 2000, and the fetch kept its folders. Nine 2010
session-day pages and two of 1999 lost their opening, leave list and speakers,
and nothing said so (docs/design/journals-misfiled/report.md on the branch
design/committee-videos).

THE RULE

A file's STRONG evidence is the dates it prints of its own sittings:
  - House: each "HOUSE JOURNAL No. N" heading that is not a continuation
    ("(cont.)", "(Cont'd)", "(Con't)"), a form feed allowed before it, with
    the dateline in the few lines under it, in parentheses or not, with a
    weekday or not; and the issue line, "Vol. NN Concord, N.H. <weekday>,
    <date> No. NN", ONLY where it prints the weekday -- 2003/HJ023's has
    none, and its date (7 January 2004) is a 2003-series sitting.
  - Senate: each "The Senate met" sitting, dated by the date line above it,
    and the "COMMENCEMENT -" and "ORGANIZATION DAY -" headings, never an
    "ADJOURNMENT -" one, which names the sitting before.
Each date maps to its series: the next year for a December of an even year
(the Organization Day), its own year otherwise -- an odd-year December
sitting stays (2001/HJ022, 2025/HJ 19). Every strong date of a file must map
to one series, and that series must be its folder.

A file with no strong date falls back on WEAK evidence, never used against
strong: the masthead "Calendar and Journal of the YYYY Session", the running
heads ("7MARCH2018HOUSERECORD", "SENATE JOURNAL 9 FEBRUARY 2006") and the
Senate's date at the top of the issue. Seven files misprint one of these
(1998/HJ004, 1999/HJ001, 2000/HJ027, 2019/HJ004; Senate 2005/SJ 9, 2007/SJ
14 and the 2011 and 2025 inauguration days), so the most common weak series
decides, and only where no strong date is printed. A file with no date at all
fails by name; it is never passed in silence.

Never read: the "Vol." number (2006/HJ004 prints "Vol. 27" among Vol. 28s)
or "First/Second Year of the NNNth" (misprinted in 1999/HJ001 and 2000/HJ027).

A SECOND RULE: no two files under journals/ and journals_senate/ are the same
bytes.

This is written apart from journal_days on purpose. Its DAY_HEADER missed a
heading after a form feed until 30 October 2026, which hid ten sittings, and
a check that shares the reader's pattern shares its blind spot.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import hashlib
import re
from collections import Counter

CHAMBERS = (("House", "journals"), ("Senate", "journals_senate"))

# Files in a journal folder that are not journals, and why: they are kept,
# and the check fails if one of them is no longer there, so the list cannot
# outlive what it excuses.
NOT_JOURNALS = {
    "journals/2003/HB1_FinanceAmended.txt":
        "the House Finance Committee's amendment to HB 1 of 2003, no Journal",
    "journals/2003/HB1_Floor_Amendment.txt":
        "a floor amendment to HB 1 of 2003, no Journal",
}

# The least share of files dated by their own sittings. 1,028 of the kit's
# 1,064 were on 29 October 2026 (96.6%); a reader that stopped reading the
# headings would fall far under it.
STRONG_FLOOR = 0.90

_MONTHS = ["january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december"]
MONTH = {m: i for i, m in enumerate(_MONTHS, 1)}
_MON = "(?P<mon>" + "|".join(_MONTHS) + ")"
_DAY = r"(?P<day>\d{1,2})"
_YR = r"(?P<yr>\d{4})"
_WEEKDAY = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"

# "State of  HOUSE JOURNAL NO. 1" opens the 2013 special session's two files.
H_HEAD = re.compile(r"^[ \t\f]*(?:State\s+of\s+)?HOUSE\s+JOURNAL\s+N[Oo]\.?\s*(?P<num>\d*)(?P<rest>[^\n]*)", re.M)
H_CONT = re.compile(r"\s*\(\s*con", re.I)
# A dateline alone on its line: "Wednesday, January 5, 2000", "(December 6,
# 2000)", "January 24, 2002", "(Thursday, January 6, 2005)".
H_DATELINE = re.compile(
    rf"^[ \t\f]*\(?[ \t]*(?:{_WEEKDAY},?[ \t]+)?{_MON}[ \t]+{_DAY},?[ \t]*{_YR}[ \t]*\)?[ \t]*$",
    re.I)
H_DATELINE_REACH = 4      # non-blank lines under the heading
H_ISSUE = re.compile(
    rf"^[ \t\f]*Vol\.\s*\d+\s+Concord,?\s*N\.\s*H\.,?\s+(?P<wd>{_WEEKDAY}),?\s+{_MON}\s+{_DAY},?"
    rf"\s*{_YR}\s+No\.", re.I | re.M)

# A sitting opens "The Senate met", "convened", "reconvened" or "assembled"
# (2018/SJ001: "The Senate reconvened at 10:00 a.m.").
S_MET = re.compile(r"^[ \t\f]*The\s+Senate\s+(?:met|reconvened|convened|assembled)\b", re.M)
S_DATELINE = re.compile(
    rf"^[ \t\f]*(?:SENATE[ \t]+|JOURNAL\s*\d+[A-Z]?[ \t]+)?{_MON}[ \t]+{_DAY},?[ \t]*{_YR}[ \t]*$",
    re.I | re.M)
S_DATELINE_REACH = 1200   # characters above "The Senate met"
S_HEADING = re.compile(
    rf"^[ \t\f]*(?P<what>COMMENCEMENT|ORGANIZATION\s+DAY)\s*-\s*(?:[A-Z][A-Z ]*?\s*-\s*)?"
    rf"{_MON}\s+{_DAY},?\s*{_YR}\s+SESSION", re.I | re.M)

W_MASTHEAD = re.compile(r"Calendar\s+and\s+Journal\s+of\s+the\s+(?P<yr>\d{4})\s+Session", re.I)
W_HOUSE_RUN = re.compile(rf"\b{_DAY}{_MON}{_YR}HOUSERECORD", re.I)
# Spaced or not: "SENATE JOURNAL 9 FEBRUARY 2006", "SENATEJOURNAL3JANUARY2018".
W_SENATE_RUN = re.compile(rf"SENATE\s*JOURNAL\s*{_DAY}\s*{_MON}\s*{_YR}", re.I)
# "January 5, 2005", or "January4,2023" as later issues print it.
W_TOP = re.compile(rf"^[ \t]*{_MON}[ \t]*{_DAY},?[ \t]*{_YR}[ \t]*$", re.I | re.M)
W_TOP_LINES = 5


def series(iso):
    """The year whose numbered series a sitting of `iso` belongs to: the next
    for a December of an even year, its own otherwise."""
    y, m = int(iso[:4]), int(iso[5:7])
    return str(y + 1) if m == 12 and y % 2 == 0 else str(y)


def _iso(m):
    mo = MONTH.get(m.group("mon").lower())
    return f"{m.group('yr')}-{mo:02d}-{int(m.group('day')):02d}" if mo else None


def _line(text, pos):
    return text.count("\n", 0, pos) + 1


def _words(iso):
    """"March 15, 2011" for 2011-03-15."""
    y, m, d = iso.split("-")
    return f"{_MONTHS[int(m) - 1].capitalize()} {int(d)}, {y}"


def strong(text, chamber):
    """[(iso, what, line)] -- the dates a file prints of its own sittings."""
    out = []
    if chamber == "House":
        for m in H_HEAD.finditer(text):
            if H_CONT.match(m.group("rest")):
                continue
            seen = 0
            pos = m.end()
            for ln in text[pos:pos + 2000].split("\n")[1:]:
                if not ln.strip(" \t\f"):
                    continue
                seen += 1
                d = H_DATELINE.match(ln)
                if d and _iso(d):
                    out.append((_iso(d), f"its own sitting HOUSE JOURNAL No. {m.group('num')} of "
                                         f"{_words(_iso(d))}", _line(text, m.start())))
                    break
                if seen >= H_DATELINE_REACH:
                    break
        for m in H_ISSUE.finditer(text):
            if _iso(m):
                out.append((_iso(m), f"its issue of {_words(_iso(m))}", _line(text, m.start())))
    else:
        for m in S_MET.finditer(text):
            above = list(S_DATELINE.finditer(text, max(0, m.start() - S_DATELINE_REACH), m.start()))
            if above and _iso(above[-1]):
                iso = _iso(above[-1])
                out.append((iso, f"its sitting of {_words(iso)}", _line(text, m.start())))
        for m in S_HEADING.finditer(text):
            if _iso(m):
                what = " ".join(m.group("what").upper().split())
                out.append((_iso(m), f"its {what} heading of {_words(_iso(m))}",
                            _line(text, m.start())))
    return out


def weak(text, chamber):
    """[(series, what, line)] -- the masthead, the running heads and the
    Senate's date at the top of the issue, for a file with no strong date."""
    out = []
    for m in W_MASTHEAD.finditer(text):
        out.append((m.group("yr"), f"its masthead's {m.group('yr')} Session",
                    _line(text, m.start())))
    run = W_HOUSE_RUN if chamber == "House" else W_SENATE_RUN
    for m in run.finditer(text):
        if _iso(m):
            out.append((series(_iso(m)), f"its running head of {_words(_iso(m))}",
                        _line(text, m.start())))
    if chamber == "Senate":
        head = "\n".join(text.split("\n")[:W_TOP_LINES])
        m = W_TOP.search(head)
        if m and _iso(m):
            out.append((series(_iso(m)), f"the date at the top of its issue, {_words(_iso(m))}",
                        _line(head, m.start())))
    return out


def _rel(p, root):
    return p.relative_to(root).as_posix()


def audit(root="."):
    """What the check finds under `root`:

    {"skip": reason} where neither folder is there; otherwise {"files":
    {chamber: n}, "strong": n, "weak": n, "named": n, "problems": [line, ...],
    "named_in": [[path, ...], ...], "detail": [line, ...]}. A problem line names
    the file and says why; named_in holds, at the same place, the files it
    names (none for the floor or a missing chamber)."""
    root = Path(root)
    if not any((root / d).is_dir() for _, d in CHAMBERS):
        return {"skip": "no journals/ or journals_senate/ here"}
    files, problems, named_in, detail = {}, [], [], []

    def problem(paths, line):
        named_in.append(list(paths))
        problems.append(line)

    n_strong = n_weak = n_named = 0
    digests = {}
    for chamber, folder in CHAMBERS:
        paths = sorted((root / folder).glob("*/*.txt")) if (root / folder).is_dir() else []
        files[chamber] = len(paths)
        if not paths:
            problem([], f"{folder}/: no {chamber} journal files at all, so nothing was checked")
            continue
        for p in paths:
            rel = _rel(p, root)
            raw = p.read_bytes()
            digests.setdefault(hashlib.sha256(raw).hexdigest(), []).append(rel)
            if rel in NOT_JOURNALS:
                n_named += 1
                detail.append(f"{rel}: not a journal, {NOT_JOURNALS[rel]}")
                continue
            # Line ends as text mode reads them: some files end lines "\r\n".
            text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
            folder_year = p.parent.name
            got = strong(text, chamber)
            if got:
                n_strong += 1
                by = {}
                for iso, what, line in got:
                    by.setdefault(series(iso), []).append(f"{what} (line {line})")
                if len(by) > 1:
                    problem([rel], f"{rel}: spans two sessions: " + "; ".join(
                        f"the {s} series by " + ", ".join(w[:2]) for s, w in sorted(by.items())))
                    continue
                (s, said), = by.items()
                how = f"prints the {s} series: " + " and ".join(said[:2])
            else:
                w = weak(text, chamber)
                if not w:
                    problem([rel], f"{rel}: no date read, from its sittings, its issue line, its "
                                    "masthead or its running heads; a person reads it")
                    continue
                n_weak += 1
                s = Counter(x[0] for x in w).most_common(1)[0][0]
                said = [f"{what} (line {line})" for x, what, line in w if x == s]
                how = (f"prints no sitting of its own, and by the rest the {s} series: "
                       + " and ".join(said[:2]))
            detail.append(f"{rel}: {how}")
            if s != folder_year:
                there = root / folder / s / p.name
                if not there.exists():
                    tail = "nothing of that name there."
                elif there.read_bytes() == raw:
                    tail = f"where {p.name} is the same bytes: this copy goes."
                else:
                    tail = "a different file of that name is there: look."
                problem([rel], f"{rel}: in {folder_year}, {how}. Belongs in {folder}/{s}/, {tail}")
    for rel in sorted(set(NOT_JOURNALS) - {d for ds in digests.values() for d in ds}):
        problem([rel], f"{rel}: named in NOT_JOURNALS and no longer there; take it off the list")
    for ds in digests.values():
        if len(ds) > 1:
            problem(ds, "the same bytes, twice: " + " and ".join(ds))
    total = sum(files.values()) - n_named
    if total and n_strong / total < STRONG_FLOOR:
        problem([], f"only {n_strong} of {total} journal files dated by their own sittings, "
                        f"under the {STRONG_FLOOR:.0%} floor: the reading has stopped working")
    return {"files": files, "strong": n_strong, "weak": n_weak, "named": n_named,
            "problems": problems, "named_in": named_in, "detail": detail}


def counts(r):
    """What was read: the files, and how each was dated."""
    return (f"{r['files'].get('House', 0):,} House and {r['files'].get('Senate', 0):,} Senate "
            f"journal files, {r['strong']:,} dated by their own sittings, {r['weak']:,} by their "
            f"masthead or running heads, {r['named']} named as no journal")


def ok_line(r):
    return counts(r) + "; each in its session's folder, and no two the same bytes"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--detail", action="store_true", help="the evidence for every file")
    ap.add_argument("--root", default=str(_paths.ROOT))
    a = ap.parse_args()
    r = audit(a.root)
    if "skip" in r:
        print(r["skip"])
        return 0
    if a.detail:
        for ln in r["detail"]:
            print(ln)
        print()
    for ln in r["problems"]:
        print(ln)
    print(ok_line(r) if not r["problems"] else
          f"{len(r['problems'])} problem(s) among {sum(r['files'].values()):,} journal files")
    return 1 if r["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
