#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-05.2
"""
A finished term's inputs, frozen before the General Court turns its files over.

    python3 freeze_term.py --views     the database's views of the term, out of
                                       db/, into db/term/<term>/
    python3 freeze_term.py --session   the day files as installed, into
                                       frozen/<term>/day/, with Docket_<term>.txt,
                                       verification_manifest_<term>.csv and the
                                       roll calls' rollcalls/<file>_<year>.txt
    python3 freeze_term.py --check     writes nothing: is each freeze whole, and
                                       is it the files installed?

The term is the one the installed files describe (proceedings.session_term,
the newest session year in Docket.txt and LSRs.txt). --term names it, and must
be that term: a term can be frozen only while the files still hold it. Standard
library only, and no network: everything it copies is already on this disk.

WHY THIS EXISTS (5 October 2026)

The General Court's files are live views of the CURRENT term. When 2027-2028
begins they stop holding 2025-2026, and nothing else on this disk holds that
term in the shape the build reads: archive_bills.json ends at 2024, and an
archived term rebuilt from the bill search's thin record loses its subject
codes (2,220, which the topic model learns from), its hearing rooms and its
committee codes. Fed a fake first 2027 batch on a copy, build_data.py wrote
eighteen archived terms and 78 bills of 2027-2028 and no 2025-2026 at all, and
exited 0 (private/NEW_TERM_DESIGN.md). So the term's INPUTS are frozen, and
after the turn the build makes the term from them every night
(build_data.py --frozen-terms): a correction to member_corrections.json or a
parser still reaches it, which a frozen copy of the built output never would.
On the day of the freeze the rebuild is the published slice exactly.

The person decided on 5 October 2026: freeze the inputs and rebuild the term
nightly; switch on the first night the files show 2027, even if Organization
Day brings only resolutions; and let a file that turns on a later night go in
without a second New term run when its frozen copy is the file it replaces,
byte for byte (snapshot_gencourt.install).

WHAT IT WRITES

  --views     db/term/<term>/: Legislation, LegislationText and CandH_Reports
              (which build_bill_versions, senate_hearing_reports,
              report_check and build_site_v2 read once the current dump no
              longer holds the term), Sponsors, VHearings and DocumentVersion
              (the database's own record of the term, as insurance), the
              _columns.json they were dumped with and the dump's own entries
              for them; houseRemoteTestify, 103 MB, in extra/, a backup that
              the kit's db/term/*/* does not carry to every night; and
              manifest.json, last: each file's sha256 and bytes, and its rows
              by session year (or by SessionID, where a view has no year)
  --session   frozen/<term>/day/: the fourteen files snapshot_gencourt
              installs, byte for byte as installed, and manifest.json, last,
              with the same for each; Docket_<term>.txt, the archived terms'
              name for a term's docket, which narrate_archive, extract_chapters
              and build_manifest read once the term is not the session's;
              verification_manifest_<term>.csv, the night's manifest with its
              hand-marked times, which build_proceedings reads then; and
              rollcalls/RollCallSummary_<year>.txt and RollCallHistory_<year>.txt
              where they are not already the installed files. Those two are
              TRACKED: when this writes one it says so, and it must be
              committed and merged to main before the switch

Every folder is written beside itself first (<name>.part) and put in place by
a rename, the manifest last, so a freeze cut short leaves the earlier one
standing; every file is a part file and a rename.

WHAT IT REFUSES

  --views     a dump that does not hold rows of both years of the term in
              Legislation; a dump whose newest year is past the term (the
              views have turned, and the freeze already on disk is the term's
              record: it is kept, and this says so); a view shorter than the
              dump's own manifest says it was, or empty; views dumped more
              than a day apart (two dumps are not one record); and any view
              holding fewer rows of the term than the freeze it would replace
  --session   files that hold any year outside the term (a turn has begun, or
              some of tonight's files are another term's); a docket without
              both years of the term; a file missing or empty; a docket that
              has lost a bill, or any file that has lost more than FALL_MOST of
              its rows of the term, against the freeze it would replace; and a
              roster that has turned (more than ROSTER_MOVED of its members
              differ from the freeze before it). If the roster turned before
              the docket did -- Organization Day is 2 December 2026 -- put the
              last roster of the old term back first, from nh-archive:
                  python3 -c "import snapshot_gencourt as S; S.restore('nh-archive', 'DAY', 'legislators.txt', 'legislators.txt')"
              and the same for Members.txt, where DAY is the last snapshot
              before Organization Day, so 2025-2026's chips keep the seat each
              member held then

WHEN, AND WHO

It asks nobody anything, so the assistant may run it; what it writes reaches
GitHub's nightly only through the person's seed-kit, and the roll-call copies
only through a merge to main.

  1. Now, and again straight after the late-November database download that
     is the person's to start: --views. The 8 September dump is the only copy
     of 2025's 847 bill records in the database's own shape, and that
     download writes over db/ (R2 keeps a replaced copy 30 days). Then
         python3 cloud.py seed-kit --only "db/term/*/*"
  2. The switch night: the first scheduled night that refuses the General
     Court's files as a new term. Its installed files are still the last of
     2025-2026, because a refused night installs nothing. Bring them here
     (cloud.py pull), then --session and --check, commit any roll-call copy
     it wrote, and
         python3 cloud.py seed-kit --only "frozen/**" Docket_2025-2026.txt verification_manifest_2025-2026.csv
     Then the nightly by hand with New term ticked; it stops before asking
     anything if this freeze is not the files installed (ready()).

WHAT READS IT

  build_data.py --frozen-terms     builds each frozen term that is no longer the
                                   session's from frozen/<term>/day/ and
                                   db/term/<term>/Legislation.psv
  snapshot_gencourt.install()      a file whose installed copy is a finished
                                   term's frozen one may be replaced however
                                   much smaller tonight's is
  nightly.py --new-term            ready(), before any request
  preflight                        --check's verdict, where a freeze is on disk
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import proceedings as P

FROZEN = Path("frozen")
DAY = "day"
MANIFEST = "manifest.json"
VIEWS_DIR = Path("db") / "term"

# The fourteen files snapshot_gencourt installs, by the names it installs them
# under. Named here rather than imported: snapshot_gencourt is the night's
# fetcher, and this asks nobody anything. preflight holds the two lists equal.
SESSION_FILES = ("Docket.txt", "LSRs.txt", "LsrsOnly.txt", "LsrSponsors.txt",
                 "legislators.txt", "RollCallSummary.txt", "RollCallHistory.txt",
                 "Committees.txt", "SubjectCodes.txt", "GeneralCodes.txt",
                 "BodyStatusCodes.txt", "HouseDistricts.txt", "Counties.txt",
                 "Members.txt")
# The column of each that says which session year a row is of: the year
# itself in each, the fourth field of LsrsOnly.txt ("26-2001|944|1190|2026|...").
# snapshot_gencourt.YEAR_COLUMN, which the turn guard reads, is held to this.
YEAR_COLUMN = {"Docket.txt": 0, "LSRs.txt": 0, "LsrSponsors.txt": 0,
               "LsrsOnly.txt": 3, "RollCallSummary.txt": 0,
               "RollCallHistory.txt": 0}
# The seven of them that change from night to night (dayfiles_from_db's
# DAY_FILES): a New term run takes tonight's files only when these are the
# frozen ones byte for byte. The lookups and Members.txt may have moved since
# without the term's record having moved.
CHANGING = ("Docket.txt", "LSRs.txt", "LsrSponsors.txt", "LsrsOnly.txt",
            "legislators.txt", "RollCallSummary.txt", "RollCallHistory.txt")
ROLLCALL_FILES = ("RollCallSummary.txt", "RollCallHistory.txt")

# The views of the term, and how a row says which part of the term it is of.
VIEWS_REQUIRED = ("Legislation", "LegislationText", "CandH_Reports")
VIEWS_INSURANCE = ("Sponsors", "VHearings", "DocumentVersion")
VIEWS_EXTRA = ("houseRemoteTestify",)
EXTRA = "extra"
# (column, how to read it): "year" is a session year as it stands, "date" a
# date whose year is taken, "id" an internal session number counted as it is.
VIEW_YEAR = {"Legislation": ("sessionyear", "year"),
             "Sponsors": ("SessionYear", "year"),
             "CandH_Reports": ("ReleaseDate", "date"),
             "houseRemoteTestify": ("CommitteeDate", "date"),
             "LegislationText": ("SessionID", "id"),
             "DocumentVersion": ("SessionID", "id")}
# Views dumped further apart than this are not one dump.
ONE_DUMP_HOURS = 24

# A freeze is not replaced by one that has lost more than this share of any
# file's rows of the term, nor by a docket that has lost a bill. A clerk's
# correction deletes a row or two; a file cut short loses far more.
FALL_MOST = 0.01
# ... nor by a roster of which more than this share of members differ from
# the freeze before it: Organization Day replaces about a third of the House.
ROSTER_MOVED = 0.10

YEAR = re.compile(r"(?:^|\D)((?:19|20)\d\d)(?:\D|$)")
DATE_YEAR = re.compile(r"^\s*\d{1,2}/\d{1,2}/((?:19|20)\d\d)")


class Refused(Exception):
    """A freeze this would not write, in a sentence for the person."""


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def term_years(term):
    a, b = term.split("-")
    return {a, b}


def session_years(data, name):
    """{year: rows} of one session file's bytes, by its YEAR_COLUMN; {} for a
    file that names no year."""
    col = YEAR_COLUMN.get(name)
    if col is None:
        return {}
    out = Counter()
    for line in data.decode("utf-8-sig", "replace").splitlines():
        f = line.lstrip("﻿").split("|")
        if len(f) > col and re.fullmatch(r"(?:19|20)\d\d", f[col].strip()):
            out[f[col].strip()] += 1
    return dict(sorted(out.items()))


def count_lines(data):
    return sum(1 for ln in data.decode("utf-8-sig", "replace").splitlines() if ln.strip())


def session_entry(data, name):
    """What the manifest says of one frozen session file."""
    years = session_years(data, name)
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "rows": sum(years.values()) if years else count_lines(data),
            **({"years": years} if years else {})}


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_bytes(path, data):
    """A part file and a rename."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def put_in_place(part, final):
    """`part`, a finished folder, where `final` is: the old one out of the way
    first, and removed only once the new one stands."""
    old = final.with_name(final.name + ".old")
    if old.exists():
        shutil.rmtree(old)
    if final.exists():
        os.replace(final, old)
    os.replace(part, final)
    if old.exists():
        shutil.rmtree(old)


def stamp():
    """When the freeze was made. A record of the run, not of a page: no
    builder reads it, so the clock is asked here (build_date says which
    stamps may)."""
    return datetime.now().isoformat(timespec="seconds")


# ---- the database's views -------------------------------------------------------

def view_rows(path, columns, view):
    """(rows, {part: rows}) of a dumped view: the lines as wide as the view,
    and how many of them are of each session year (or SessionID)."""
    col, how = VIEW_YEAR.get(view, (None, None))
    at = columns.index(col) if col in columns else None
    n, parts, lines_ = 0, Counter(), 0
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        for line in fh:
            f = line.rstrip("\r\n").split("|")
            lines_ += bool(line.strip())
            if len(f) != len(columns):
                continue
            n += 1
            if at is None:
                continue
            v = f[at].strip()
            if how == "date":
                m = DATE_YEAR.match(v)
                v = m.group(1) if m else ""
            if v:
                parts[v if how != "id" else f"session {v}"] += 1
    # DocumentVersion is PublicNHLMS's, and its rows are wider than the column
    # list _columns.json gives it (16 fields against 10 on 8 September):
    # document_versions_from_db reads it by position. A view no line of which
    # is as wide as its list is counted by its lines, and by nothing finer.
    if not n and lines_ and view not in VIEWS_REQUIRED:
        return lines_, {}
    return n, dict(sorted(parts.items()))


def of_term(entry, term):
    """Rows of `term` in a view's manifest entry: by its years where it has
    them, else all of its rows."""
    years = entry.get("years") or {}
    if years and any(re.fullmatch(r"\d{4}", k) for k in years):
        return sum(v for k, v in years.items() if k in term_years(term))
    return int(entry.get("rows") or 0)


def freeze_views(term, src=Path("db"), out_root=VIEWS_DIR):
    """db/term/<term>/ from the dump in `src`. Lines for the person."""
    said = []
    cols = load_json(src / "_columns.json")
    dump = load_json(src / "_manifest.json") or {}
    if not isinstance(cols, dict):
        raise Refused(f"{src / '_columns.json'} is not here or will not parse: the views "
                      "cannot be read without it")
    have = [v for v in VIEWS_REQUIRED + VIEWS_INSURANCE + VIEWS_EXTRA
            if (src / f"{v}.psv").exists()]
    missing = [v for v in VIEWS_REQUIRED if v not in have]
    if missing:
        raise Refused(f"{src} holds no {', '.join(missing)}.psv: the term's versions, Senate "
                      "reports and statuses come from these, and a freeze without them is "
                      "not the term")
    # ONE DUMP. The views are read together -- a LegislationText row is
    # joined to its Legislation row by an id that restarts every term -- so
    # views asked for on different days are not one record.
    when = []
    for v in have:
        try:
            when.append(datetime.fromisoformat(str((dump.get(v) or {}).get("fetched"))))
        except ValueError:
            pass
    if when and (max(when) - min(when)).total_seconds() > ONE_DUMP_HOURS * 3600:
        raise Refused(f"the views in {src} were dumped from {min(when):%Y-%m-%d} to "
                      f"{max(when):%Y-%m-%d}: more than a day apart is not one dump")

    entries = {}
    for v in have:
        if v not in cols:
            raise Refused(f"{src / '_columns.json'} has no column list for {v}")
        p = src / f"{v}.psv"
        rows, parts = view_rows(p, cols[v], v)
        listed = (dump.get(v) or {}).get("rows")
        if not rows:
            if v in VIEWS_REQUIRED:
                raise Refused(f"{p} holds no row as wide as the view: empty, or not the view")
            said.append(f"  {v}: no row, so not frozen")
            continue
        if isinstance(listed, int) and rows < listed:
            raise Refused(f"{p} has {rows:,} rows and the dump's own manifest says "
                          f"{listed:,}: a view cut short is not frozen")
        entries[v] = {"rows": rows, **({"years": parts} if parts else {})}

    # THE TERM, AND NOTHING PAST IT. Legislation says which years the dump
    # holds. Both of the term's, or this is not the term's record; a year
    # past it, and the views have turned -- whatever is frozen already is
    # the term's last record and stays.
    yrs = {k for k in (entries["Legislation"].get("years") or {})}
    want = term_years(term)
    if not want <= yrs:
        raise Refused(f"{src / 'Legislation.psv'} holds session years "
                      f"{', '.join(sorted(yrs)) or 'none'}: both of {term}'s are needed")
    past = sorted(y for y in yrs if y > max(want))
    if past:
        raise Refused(f"{src / 'Legislation.psv'} already holds {', '.join(past)}: the "
                      f"General Court's views have turned past {term}, and the freeze "
                      f"of {term} on disk, if there is one, is its record and is kept")

    final = out_root / term
    earlier = load_json(final / MANIFEST) or {}
    worse = []
    for v, e in entries.items():
        before = ((earlier.get("files") or {}).get(f"{v}.psv")
                  or (earlier.get("files") or {}).get(f"{EXTRA}/{v}.psv"))
        if before and of_term(e, term) < of_term(before, term):
            worse.append(f"{v} {of_term(e, term):,} rows of {term} against "
                         f"{of_term(before, term):,} frozen")
    if worse:
        raise Refused("this dump holds fewer of the term's rows than the freeze it would "
                      "replace: " + "; ".join(worse) + ". The freeze on disk is kept")

    part = final.with_name(final.name + ".part")
    if part.exists():
        shutil.rmtree(part)
    part.mkdir(parents=True)
    files = {}
    for v, e in entries.items():
        rel = f"{EXTRA}/{v}.psv" if v in VIEWS_EXTRA else f"{v}.psv"
        (part / rel).parent.mkdir(exist_ok=True)
        tmp = part / (rel + ".part")
        shutil.copyfile(src / f"{v}.psv", tmp)
        os.replace(tmp, part / rel)
        files[rel] = {"sha256": sha256_of(part / rel), "bytes": (part / rel).stat().st_size, **e}
        said.append(f"  {rel:32} {e['rows']:>9,} rows  "
                    + ", ".join(f"{k} {n:,}" for k, n in (e.get("years") or {}).items()))
    write_bytes(part / "_columns.json",
                json.dumps({v: cols[v] for v in entries}, indent=1).encode("utf-8"))
    files["_columns.json"] = {"sha256": sha256_of(part / "_columns.json"),
                              "bytes": (part / "_columns.json").stat().st_size}
    write_bytes(part / MANIFEST, json.dumps({
        "term": term, "frozen": stamp(), "from": str(src).replace("\\", "/"),
        "dump": {v: dump.get(v) for v in entries if dump.get(v)},
        "files": files}, indent=1).encode("utf-8"))
    put_in_place(part, final)
    said.append(f"{final}: {len(entries)} views of {term}, "
                + ("replacing the freeze of " + str(earlier.get("frozen")) if earlier
                   else "the first freeze"))
    return said


# ---- the day files ----------------------------------------------------------------

def rollcall_copies(root, data_by_name):
    """{installed name: (rollcalls path, its year)} for the two roll-call
    files: the copy of each, by the one session year it holds. A file with no
    year, or more than one, has none."""
    out = {}
    for name in ROLLCALL_FILES:
        years = session_years(data_by_name[name], name)
        if len(years) == 1:
            y = next(iter(years))
            out[name] = (root / "rollcalls" / f"{name[:-4]}_{y}.txt", y)
    return out


def member_ids(data):
    return {ln.split("|")[0].lstrip("﻿").strip()
            for ln in data.decode("utf-8-sig", "replace").splitlines() if "|" in ln}


def freeze_session(term, root=Path(".")):
    """frozen/<term>/ and the archived names beside it, from the installed
    day files in `root`. Lines for the person."""
    said = []
    data = {}
    for name in SESSION_FILES:
        p = root / name
        if not p.exists() or not p.stat().st_size:
            raise Refused(f"{p} is not here, or empty: a freeze is of all fourteen files")
        data[name] = p.read_bytes()
    entries = {name: session_entry(b, name) for name, b in data.items()}
    want = term_years(term)
    stray = {name: sorted(set(e.get("years") or {}) - want)
             for name, e in entries.items() if set(e.get("years") or {}) - want}
    if stray:
        raise Refused("these files hold years outside " + term + ": "
                      + "; ".join(f"{n} {', '.join(y)}" for n, y in stray.items())
                      + ". A turn has begun, or some files are another term's, and either "
                      "way this is not the term as it ended")
    if set(entries["Docket.txt"].get("years") or {}) != want:
        raise Refused(f"Docket.txt holds {', '.join(entries['Docket.txt'].get('years') or {}) or 'no year'}"
                      f": the docket of a term that has ended holds both of {term}'s years")
    for name in YEAR_COLUMN:
        if not entries[name].get("years"):
            raise Refused(f"{name} holds no row of {term}: a freeze is of the term's files "
                          "as they ended, and this one is empty")
    vm = root / "verification_manifest.csv"
    if not vm.exists() or not vm.stat().st_size:
        raise Refused(f"{vm} is not here: the term's recordings and hand-marked times are in it")

    final = root / FROZEN / term
    earlier = load_json(final / MANIFEST) or {}
    worse = []
    for name, e in entries.items():
        before = (earlier.get("files") or {}).get(name)
        if not before or name in ("legislators.txt", "Members.txt"):
            continue
        if e["rows"] < before.get("rows", 0) * (1 - FALL_MOST):
            worse.append(f"{name} {e['rows']:,} rows against {before['rows']:,} frozen")
    if earlier:
        was_bills = set(earlier.get("docket_bills") or [])
        now_bills = docket_bills(data["Docket.txt"])
        gone = sorted(was_bills - now_bills)
        if gone:
            worse.append(f"Docket.txt has lost {len(gone)} bill(s) the freeze holds "
                         f"({', '.join(gone[:5])}{', ...' if len(gone) > 5 else ''})")
        old_frozen = final / DAY / "legislators.txt"
        if old_frozen.exists():
            a, b = member_ids(old_frozen.read_bytes()), member_ids(data["legislators.txt"])
            moved = len(a ^ b)
            if a and moved > ROSTER_MOVED * len(a):
                worse.append(f"legislators.txt: {moved} members differ from the freeze's "
                             f"{len(a)} -- the roster has turned; put 2025-2026's back from "
                             "nh-archive first (this script's docstring says how)")
    if worse:
        raise Refused("the installed files are worse than the freeze they would replace: "
                      + "; ".join(worse) + ". The freeze on disk is kept")

    part = final.with_name(final.name + ".part")
    if part.exists():
        shutil.rmtree(part)
    (part / DAY).mkdir(parents=True)
    for name, b in data.items():
        write_bytes(part / DAY / name, b)
    copies = rollcall_copies(root, data)
    rec = {"term": term, "frozen": stamp(), "files": entries,
           "export_day": export_day(root, data["Docket.txt"]),
           "docket_bills": sorted(docket_bills(data["Docket.txt"])),
           "docket": {"path": f"Docket_{term}.txt", "sha256": entries["Docket.txt"]["sha256"]},
           "manifest": {"path": f"verification_manifest_{term}.csv",
                        "sha256": sha256_of(vm), "rows": count_lines(vm.read_bytes()) - 1},
           "rollcalls": {n: {"path": c.relative_to(root).as_posix(), "year": y,
                             "sha256": entries[n]["sha256"]}
                         for n, (c, y) in copies.items()}}
    write_bytes(part / MANIFEST, json.dumps(rec, indent=1).encode("utf-8"))
    put_in_place(part, final)
    said.append(f"{final}: the fourteen day files of {term} as installed"
                + (f" (the export of {rec['export_day']})" if rec["export_day"] else "")
                + ", " + ("replacing the freeze of " + str(earlier.get("frozen")) if earlier
                          else "the first freeze"))
    for name, e in entries.items():
        said.append(f"  {name:22} {e['bytes']:>11,} bytes {e['rows']:>9,} rows"
                    + ("  " + ", ".join(f"{k} {n:,}" for k, n in e["years"].items())
                       if e.get("years") else ""))
    write_bytes(root / f"Docket_{term}.txt", data["Docket.txt"])
    said.append(f"Docket_{term}.txt: the docket as installed, for the readers of an "
                "archived term's docket")
    write_bytes(root / f"verification_manifest_{term}.csv", vm.read_bytes())
    said.append(f"verification_manifest_{term}.csv: the night's manifest, "
                f"{rec['manifest']['rows']:,} rows, its hand-marked times with it")
    for name, (copy, y) in copies.items():
        if copy.exists() and _lines(copy.read_bytes()) == _lines(data[name]):
            said.append(f"{copy.relative_to(root).as_posix()}: already the installed "
                        f"{name}, line for line")
            continue
        write_bytes(copy, data[name])
        said.append(f"{copy.relative_to(root).as_posix()}: WRITTEN from the installed {name}. "
                    "git tracks it: commit it, and merge it to main before the switch")
    return said


def docket_bills(data):
    """{"2025 HB1", ...}: each (session year, bill) the docket names."""
    out = set()
    for line in data.decode("utf-8-sig", "replace").splitlines():
        f = line.lstrip("﻿").split("|")
        if len(f) > 5 and f[3].strip():
            out.add(f"{f[0].strip()} {f[3].strip().upper()}")
    return out


def export_day(root, docket):
    """The day nh-archive first held this docket as the General Court's
    export, or "" -- which day's files these are, for the record."""
    digest = hashlib.sha256(docket).hexdigest()
    idx = load_json(root / "nh-archive" / "index.json") or {}
    hist = (idx.get("Docket.txt") or {}).get("history") if isinstance(idx, dict) else None
    days = [h[0] for h in (hist or []) if isinstance(h, list) and len(h) == 2 and h[1] == digest]
    return str(days[-1]) if days else ""


# ---- is it whole, and is it what is installed --------------------------------------

def frozen_terms(root=Path(".")):
    """Every term frozen under frozen/, oldest first."""
    d = Path(root) / FROZEN
    return sorted(p.name for p in d.iterdir()
                  if p.is_dir() and P.TERM_RE.match(p.name) and (p / MANIFEST).exists()) \
        if d.is_dir() else []


def intact(root, term):
    """Problems with frozen/<term>/ itself: a file missing or not the one its
    manifest names. [] when it is whole."""
    root = Path(root)
    rec = load_json(root / FROZEN / term / MANIFEST)
    if not isinstance(rec, dict):
        return [f"frozen/{term}/{MANIFEST} is not here or will not parse"]
    bad = []
    for name, e in (rec.get("files") or {}).items():
        p = root / FROZEN / term / DAY / name
        if not p.exists():
            bad.append(f"frozen/{term}/{DAY}/{name} is missing")
        elif p.stat().st_size != e.get("bytes") or sha256_of(p) != e.get("sha256"):
            bad.append(f"frozen/{term}/{DAY}/{name} is not the file its manifest names")
    for key in ("docket", "manifest"):
        p = root / ((rec.get(key) or {}).get("path") or "")
        if not p.name or not p.exists():
            bad.append(f"{p.name or key} is not here")
        elif sha256_of(p) != (rec.get(key) or {}).get("sha256"):
            bad.append(f"{p.name} is not the copy frozen with the term")
    # The roll-call copies travel in git, which may hand them back with other
    # line endings than the installed file had (core.autocrlf on GitHub's
    # machine): compared by their lines, not their bytes.
    for name, c in (rec.get("rollcalls") or {}).items():
        p = root / c.get("path", "")
        frozen_copy = root / FROZEN / term / DAY / name
        if not p.exists() or not frozen_copy.exists() or \
                _lines(p.read_bytes()) != _lines(frozen_copy.read_bytes()):
            bad.append(f"{c.get('path')} is not the frozen {name}")
    return bad


def _lines(data):
    """A text file's lines, whatever its line endings and byte-order mark."""
    return [ln.rstrip() for ln in data.decode("utf-8-sig", "replace").splitlines() if ln.strip()]


def views_intact(root, term):
    """Problems with db/term/<term>/, the same way; [] when it is whole and
    holds both years of the term in Legislation."""
    base = Path(root) / VIEWS_DIR / term
    rec = load_json(base / MANIFEST)
    if not isinstance(rec, dict):
        return [f"{VIEWS_DIR.as_posix()}/{term}/{MANIFEST} is not here: --views has not run"]
    bad = []
    for rel, e in (rec.get("files") or {}).items():
        p = base / rel
        if not p.exists():
            bad.append(f"{VIEWS_DIR.as_posix()}/{term}/{rel} is missing")
        elif p.stat().st_size != e.get("bytes"):
            bad.append(f"{VIEWS_DIR.as_posix()}/{term}/{rel} is not the size its manifest gives")
    leg = (rec.get("files") or {}).get("Legislation.psv") or {}
    if not term_years(term) <= set(leg.get("years") or {}):
        bad.append(f"{VIEWS_DIR.as_posix()}/{term}/Legislation.psv does not hold both years")
    return bad


def differs(root, term, names=CHANGING):
    """The installed files among `names` that are not frozen/<term>/'s, with
    how far each has moved."""
    root = Path(root)
    rec = load_json(root / FROZEN / term / MANIFEST) or {}
    out = []
    for name in names:
        p, e = root / name, (rec.get("files") or {}).get(name) or {}
        if not p.exists():
            out.append(f"{name} is not installed")
            continue
        b = p.read_bytes()
        if hashlib.sha256(b).hexdigest() == e.get("sha256"):
            continue
        now = session_entry(b, name)
        out.append(f"{name} {now['rows'] - int(e.get('rows') or 0):+,} rows")
    return out


# WHAT "AS INSTALLED" MEANS (5 October 2026). The term's record is its docket
# and its roll calls: a New term run takes tonight's files only when every
# row of the term in the installed Docket.txt and roll-call files is in the
# freeze, and no other. Compared by what the rows say -- the docket's first six
# columns, which are all the database's view holds, and the roll calls whole --
# and not byte for byte, so that a database night, which rewrites the
# docket's seventh column from the third, does not make a fresh freeze look
# stale. The other changing files are said where they have moved, and do not
# stop the run: from Organization Day the installed roster, and with it
# LsrsOnly.txt, may be the new term's (the person's decision of 5 October on
# the database night's roster), and the freeze keeps the old one.
RECORD = {"Docket.txt": 6, "RollCallSummary.txt": None, "RollCallHistory.txt": None}


def rows_of(data, name, term):
    """{row}: the rows of `term` in one file, cut to what RECORD compares."""
    width, col, want = RECORD.get(name), YEAR_COLUMN.get(name, 0), term_years(term)
    out = set()
    for line in data.decode("utf-8-sig", "replace").splitlines():
        f = [x.strip() for x in line.lstrip("﻿").split("|")]
        if len(f) > col and f[col] in want:
            out.add("|".join(f[:width] if width else f).rstrip("|"))
    return out


def ready(root=Path("."), term=None):
    """(ok, why): may a New term run take tonight's files? The term the
    installed files describe must be frozen whole, with its views under
    db/term/, and its record frozen AS INSTALLED (RECORD). Otherwise the run
    would install a new term over a term this disk no longer holds whole."""
    root = Path(root)
    term = term or P.session_term(root)
    if not term:
        return False, "no installed Docket.txt or LSRs.txt says which term they are"
    how = ("run freeze_term.py --session (and --views, if it says so) on the files "
           "installed, send them with seed-kit, and run this again")
    bad = intact(root, term) + views_intact(root, term)
    if bad:
        return False, f"{term} is not frozen whole: {'; '.join(bad[:4])}. Freeze first: {how}"
    moved = []
    for name in RECORD:
        now = rows_of((root / name).read_bytes(), name, term) if (root / name).exists() else set()
        was = rows_of((root / FROZEN / term / DAY / name).read_bytes(), name, term)
        if now != was:
            moved.append(f"{name}: {len(now - was):,} row(s) of {term} installed and not frozen, "
                         f"{len(was - now):,} frozen and not installed")
    if moved:
        return False, (f"the freeze of {term} is not its record as installed ({'; '.join(moved)}). "
                       f"Freeze again first: {how}")
    rec = load_json(root / FROZEN / term / MANIFEST) or {}
    other = differs(root, term, [n for n in CHANGING if n not in RECORD])
    return True, (f"{term} is frozen as installed (frozen {rec.get('frozen', '?')}"
                  + (f", the export of {rec['export_day']}" if rec.get("export_day") else "")
                  + "), its views with it"
                  + (f"; moved since, and kept as frozen: {'; '.join(other)}" if other else ""))


def check(root=Path("."), term=None):
    """--check: (exit code, lines). 0 when every freeze on disk is whole and
    the session's own term, if frozen, is the files installed; 1 when one is
    not; 2 when nothing is frozen."""
    root = Path(root)
    sess = P.session_term(root)
    views = root / VIEWS_DIR
    terms = [term] if term else sorted(
        set(frozen_terms(root)) | ({p.name for p in views.iterdir()
                                     if p.is_dir() and P.TERM_RE.match(p.name)}
                                    if views.is_dir() else set()))
    if not terms:
        return 2, [f"nothing is frozen here (no {FROZEN}/<term>/ and no {VIEWS_DIR.as_posix()}/<term>/)"]
    lines, code = [f"the installed files are {sess or 'of no term'}'s"], 0
    for t in terms:
        session_bad = intact(root, t) if (root / FROZEN / t).exists() else \
            [f"frozen/{t}/ is not here: --session has not run"]
        view_bad = views_intact(root, t)
        lines.append(f"{t}:")
        lines.append("  the day files: " + ("whole" if not session_bad else "; ".join(session_bad)))
        lines.append("  the views:     " + ("whole" if not view_bad else "; ".join(view_bad)))
        if t == sess and not session_bad:
            moved = differs(root, t)
            lines.append("  against the files installed: "
                         + ("fresh, byte for byte" if not moved else
                            "STALE: " + "; ".join(moved) + " -- freeze again before the switch"))
            code = max(code, 1 if moved else 0)
        elif t != sess and sess and t < sess:
            lines.append(f"  the session's files have moved on to {sess}: this freeze is "
                         f"{t}'s record, and build_data --frozen-terms builds the term from it")
        code = max(code, 1 if session_bad or view_bad else 0)
    return code, lines


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    what = ap.add_mutually_exclusive_group(required=True)
    what.add_argument("--views", action="store_true",
                      help="freeze the database's views of the term out of db/")
    what.add_argument("--session", action="store_true",
                      help="freeze the installed day files, the docket and the manifest")
    what.add_argument("--check", action="store_true", help="write nothing; say what is frozen")
    ap.add_argument("--term", help="the term (default: the one the installed files describe)")
    ap.add_argument("--db", default="db", help="the dump to freeze the views from (default db)")
    a = ap.parse_args()

    if a.check:
        code, lines = check(term=a.term)
        print("\n".join(lines))
        return code
    sess = P.session_term(Path("."))
    term = a.term or sess
    if not term or not P.TERM_RE.match(term):
        print("No term to freeze: no installed Docket.txt or LSRs.txt says which term they "
              "are, and --term was not given.")
        return 1
    if a.session and term != sess:
        print(f"NOT FROZEN: the installed files are {sess or 'of no term'}'s, not {term}'s. A "
              "term's day files can be frozen only while they are the ones installed.")
        return 1
    try:
        lines = (freeze_views(term, Path(a.db)) if a.views else freeze_session(term))
    except Refused as e:
        print(f"NOT FROZEN: {e}.")
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
