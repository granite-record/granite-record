#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.2
"""
The definitions preflight's checks share across areas, and those no check reaches
by name (the _DOCKET_* rows _journey_clauses_kept reads by their prefix among them).

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5). This module uses pf_core, pf_fixture, pf_harness,
pf_runner and itself, and no module of an area.
"""

import ast
import csv
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

import _paths

from pf_core import (_SWITCHED, _THIS_RUN, _reaching, _run, _source)
from pf_fixture import (CHAIN_NEEDS, _fixture_site_shared, _fixture_site_whole, _once_a_run,
                        _shared_root)
from pf_harness import (_components_js, _with_components)
from pf_runner import (MAIN_REF)

# ---- the bill index, as a fixture writes it and a check reads it --------------
#
# THE TERM FILES, NOT index.json (5 October 2026). Every reader of the built
# site's bill rows goes through site_read.bill_index, which reads
# site/idx/<term>.json as site/meta.json names them, and a fixture writes them
# the way build_site_v2 does, here, in one place.

def _bill_index_write(site, rows):
    """A fixture's bill rows written as build_site_v2 writes them: one
    idx/<term>.json per term, compact, and meta.json naming the terms newest
    first, merged into a meta.json the fixture already has. A term file left
    from an earlier write is removed, so that site_read.bill_index does not
    find a term meta.json does not name. Returns site."""
    site = Path(site)
    idx = site / "idx"
    idx.mkdir(parents=True, exist_ok=True)
    for f in idx.glob("*.json"):
        if re.fullmatch(r"\d{4}-\d{4}", f.stem):
            f.unlink()
    by = {}
    for r in rows:
        by.setdefault(r["term"], []).append(r)
    for t, part in by.items():
        (idx / f"{t}.json").write_text(json.dumps(part, separators=(",", ":")),
                                       encoding="utf-8")
    mp = site / "meta.json"
    meta = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    meta["terms"] = sorted(by, reverse=True)
    mp.write_text(json.dumps(meta), encoding="utf-8")
    return site


def _site_bills(site="site"):
    """Every bill row of a built site through site_read.bill_index, or None
    where none is built. A broken one raises site_read.Broken, which fails the
    check that asked with the loader's own words."""
    import site_read
    return site_read.bill_index(site)


# ---- the built bill pages, read once a run ------------------------------------
#
# SIX CHECKS EACH WALKED EVERY BILL PAGE OF THE BUILT SITE (2 October 2026):
# 33,717 pages and 1.2 GB, opened, searched for their record and parsed, six
# times over, for one field or two apiece. They share one walk now. What is
# kept of a record is what those six read and nothing else -- a whole record
# carries every ballot of every roll call and the bill's text, and 33,717 of
# them are more than this machine's memory -- so a record here answers for
# the fields below and FAILS the check that asks it for any other: a field
# that was not kept must not read as a field the page does not have.
#
# site/ is not written during a run of these checks, so nothing is hidden by
# reading it once. A check that reads a fixture's site, or one page, still
# asks site_read itself.
_RECORD_WHOLE = ("id", "term", "archived", "veto_message", "vote_note", "next_step",
                 "journey", "ballot",
                 "status_source",   # whose a CACR's voters' line is (_ballots_shown)
                 "study_report")    # the report's line (_rail_endings_on_the_site)
_RECORD_KEPT = _RECORD_WHOLE + (
    "rollcalls",        # kept as whether the page has any
    "reports")          # kept as each report's cite_url and source
_SITE_RECORDS = []


class _KeptRecord(dict):
    """A bill page's record, cut down to _RECORD_KEPT."""

    @staticmethod
    def _kept(key):
        assert key in _RECORD_KEPT, (
            f"_site_records() keeps {', '.join(_RECORD_KEPT)} of a bill page's record, "
            f"and a check asked it for {key!r}: add the field to _RECORD_KEPT, or walk "
            "the pages with site_read.records")

    def get(self, key, default=None):
        self._kept(key)
        return dict.get(self, key, default)

    def __getitem__(self, key):
        self._kept(key)
        return dict.__getitem__(self, key)


def _site_records():
    """[(year, BILLID, record)] for every bill page of site/, in the order
    site_read.records gives them, from the run's one walk.

    KEPT ONLY ONCE THE WALK HAS ENDED. The first version filled _SITE_RECORDS
    as it went and took a list with anything in it for the finished walk, so a
    walk that stopped part-way -- a page another session was rewriting, a
    record that would not parse -- left its first few hundred pages there, and
    the five checks after the one that took the error read those as the whole
    site and reported ok on them. A walk that stops keeps nothing, and the
    next check walks for itself, as each of the six did before they shared
    one. And a report that is not an object is kept as it is, for
    _report_citations to fail on in its own name: one check's field does not
    stop the walk the other five read.
    """
    if not _SITE_RECORDS:
        import site_read as SR
        walked = []
        for year, bid, rec in SR.records("site"):
            kept = {k: rec[k] for k in _RECORD_WHOLE if k in rec}
            if "rollcalls" in rec:
                kept["rollcalls"] = bool(rec["rollcalls"])
            if "reports" in rec:
                reps = rec["reports"]
                kept["reports"] = [{k: rep[k] for k in ("cite_url", "source") if k in rep}
                                   if isinstance(rep, dict) else rep
                                   for rep in reps] if isinstance(reps, list) else reps
            walked.append((year, bid, _KeptRecord(kept)))
        _SITE_RECORDS.extend(walked)
    return _SITE_RECORDS


# What runs unattended, and so what _import_all reads for the scripts they
# start: the build, the night, the lane and its queue, and the workflow. In
# the first three a script is a quoted "name.py", and one named there and
# missing is a failure; the last two are text, where a name may only be
# mentioned, so there only what is here is imported. The laptop's evening job
# was among them until 10 October 2026, when the night took its captions over
# and it was retired.
_RUNNERS = ("build_all.py", "nightly.py", "watchers/gc_lane.py",
            "watchers/gc_lane.queue", ".github/workflows/nightly.yml")


def _mk(p):
    """`p`, with its folder made: a fixture's tree is new, and the root
    tidy's folders (corrections/, collected/, records/...) are not in it until a
    file is put in one."""
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _plant(root, files):
    """A tree for a reader to be proved on: {relative path: text}."""
    for rel, text in files.items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return Path(root)


def _first_script(node):
    """The script a launch's argument list starts with: ["x.py", ...] or
    ["x.py", ...] + more. None for any other node."""
    if isinstance(node, ast.BinOp):
        return _first_script(node.left)
    if isinstance(node, ast.List) and node.elts and isinstance(node.elts[0], ast.Constant) \
            and isinstance(node.elts[0].value, str) \
            and re.fullmatch(r"[\w./\\-]+\.py", node.elts[0].value):
        return node.elts[0].value
    return None


_RUN_BY_PATH = re.compile(r"(?:\bpython3?|\bpy)\s+([\w./\\-]+\.py)\b|Test-Path\s+([\w./\\-]+\.py)\b")


def _runner_names(root=None):
    """{runner: [(script name, run by its path)]}: every script that
    build_all's steps, nightly, the lane's queue, the workflows and
    publish.bat start, as each writes it. The first three find theirs
    through _paths.script; the workflows and publish.bat run a path, which
    must be there as written."""
    base = Path(root).resolve() if root is not None else _paths.ROOT
    out = {}

    def code(rel, also=None):
        f = _paths.locate(rel, root=base)
        if not f.exists():
            return
        names = []
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if also and isinstance(n, ast.Call) and getattr(n.func, "id", None) == also \
                    and len(n.args) > 1:
                hit = _first_script(n.args[1])
            elif not also and isinstance(n, (ast.List, ast.BinOp)):
                hit = _first_script(n)
            else:
                continue
            if hit:
                names.append((hit, False))
        out[rel] = sorted(set(names))
    code("build_all.py", also="Step")
    code("nightly.py")
    queue = _paths.locate("watchers/gc_lane.queue", root=base)
    if queue.exists():
        lines = []
        for ln in queue.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            ln = re.sub(r"^daily\s+\S+\s+", "", ln)
            ln = re.sub(r"^handover\s+", "", ln)
            lines.append((ln.split()[0], False))
        out["watchers/gc_lane.queue"] = sorted(set(lines))
    for f in sorted((base / ".github" / "workflows").glob("*.y*ml")) + [base / "publish.bat"]:
        if not f.exists():
            continue
        found = set()
        for ln in f.read_text(encoding="utf-8").splitlines():
            bare = ln.strip()
            if bare.startswith(("#", "::")) or bare.upper().startswith("REM"):
                continue
            for m in _RUN_BY_PATH.finditer(ln):
                found.add(((m.group(1) or m.group(2)).replace("\\", "/"), True))
        out[f.relative_to(base).as_posix()] = sorted(found)
    return out


# Most of what each runner named on 6 October 2026, before any file moved
# (47, 14, 5, 3, 2 and 3): a runner read as naming fewer has stopped being
# read, not stopped running things. The slack is for a step retired on
# purpose. laptop_evening.py, which named 3, was retired on 10 October 2026.
_RUNNER_FLOORS = {"build_all.py": 40, "nightly.py": 12,
                  "watchers/gc_lane.queue": 3, ".github/workflows/nightly.yml": 2,
                  ".github/workflows/weekly.yml": 1, "publish.bat": 2}


# Real rows: Docket_db_2005-2006.txt 17549-17561 (SB 339), 12571-12577 (HB
# 1696), 11485-11489 (SB 24's in the House), 8702-8704 and 8715-8720 (HB 607);
# Docket_db_2013-2014.txt 8250-8255 (HB 114); Docket_2015-2016.txt 672-679 (HB
# 142); Docket_db_2009-2010.txt 2243-2249 (SB 17); Docket_db_2007-2008.txt
# 13950 and 13953-13954 (HB 145).
_DOCKET_OVERTAKEN = {
    ("SB339", "2005-2006"): [
        "2006|2668|01/04/2006 12:18:07 PM|SB339|S|Introduced and Referred to Executive Departments and Administration; SJ 1, Pg.12|01/04/2006 12:18:07 PM",
        "2006|2668|01/04/2006 01:45:43 PM|SB339|S|Hearing; === CANCELLED === January 18, 2006, Room 102, LOB, 1:50 p.m.; SC1|01/04/2006 01:45:43 PM",
        "2006|2668|01/04/2006 02:53:44 PM|SB339|S|Hearing; === RESCHEDULED === January 19, 2006, Room 102, LOB, 1:50 p.m.; SC1A|01/04/2006 02:53:44 PM",
        "2006|2668|01/12/2006 12:35:20 PM|SB339|S|Hearing; === CANCELLED === January 19, 2006, Room 102, LOB, 1:50 p.m.; SC2|01/12/2006 12:35:20 PM",
        "2006|2668|01/20/2006 03:14:40 PM|SB339|S|Hearing; === RESCHEDULED === March 15, 2006, Room 102, LOB, 1:20 p.m.|01/20/2006 03:14:40 PM",
        "2006|2668|01/26/2006 10:42:47 AM|SB339|S|Hearing; === CANCELLED === TIME CHANGE === March 15, 2006, Room 102, LOB, 1:00 p.m.; SC4|01/26/2006 10:42:47 AM",
        "2006|2668|02/08/2006 09:32:10 AM|SB339|S|Hearing; === RESCHEDULED === February 22, 2006, Room 102, LOB, 2:30 p.m.; SC6|02/08/2006 09:32:10 AM",
        "2006|2668|02/27/2006 11:39:09 AM|SB339|S|Committee Report; Ought to Pass [03/09/06]; SC9|02/27/2006 11:39:09 AM",
        "2006|2668|03/09/2006 02:42:33 PM|SB339|S|Ought to Pass, MA, VV; Refer To Finance [Rule 26]; SJ 7, Pg.164|03/09/2006 02:42:33 PM",
        "2006|2668|03/16/2006 09:11:40 AM|SB339|S|Committee Report; Ought to Pass with Amendment{1409} [03/22/06]; SC11, Pg.17|03/16/2006 09:11:40 AM",
        "2006|2668|03/22/2006 04:50:04 PM|SB339|S|Committee Amendment{1409}, AA, VV; SJ 9, Pg.261-362|03/22/2006 04:50:04 PM",
        "2006|2668|03/22/2006 04:51:34 PM|SB339|S|Ought to Pass with Amendment{1409}, MA, VV; OT3rdg; SJ 9, Pg.262|03/22/2006 04:51:34 PM",
        "2006|2668|03/22/2006 06:44:14 PM|SB339|S|Passed by Third Reading Resolution; SJ 9, Pg.308|03/22/2006 06:44:14 PM"],
    ("HB1696", "2005-2006"): [
        "2006|2095|01/04/2006 02:43:00 PM|HB1696|H|Introduced and ref to Executive Departments & Administration  HJ 7, pg 353|01/04/2006 02:43:00 PM",
        "2006|2095|01/04/2006 02:43:26 PM|HB1696|H|===RESCHEDULED===Public Hearing Jan 31 11:00 RM 306 LOB|01/04/2006 02:43:26 PM",
        "2006|2095|01/19/2006 10:51:48 AM|HB1696|H|Public Hearing    Feb 9  10:00  RM306/LOB|01/19/2006 10:51:48 AM",
        "2006|2095|02/14/2006 02:18:21 PM|HB1696|H|Subcommittee Work Session    Feb 16   9:00  RM306/LOB|02/14/2006 02:18:21 PM",
        "2006|2095|02/16/2006 06:50:37 PM|HB1696|H|Subcommittee Work Session   Feb 21  1:30  RM306/LOB|02/16/2006 06:50:37 PM",
        "2006|2095|02/23/2006 01:04:17 PM|HB1696|H|Comm Rprt:  OTP/AM {1198h}  for March 7 (vote 14-0; CC)|02/23/2006 01:04:17 PM",
        "2006|2095|03/07/2006 04:56:38 PM|HB1696|H|Passed with AM {1198h}, MA,  VV   HJ 23, pg 1395-1401|03/07/2006 04:56:38 PM"],
    ("SB24", "2005-2006"): [
        "2006|0987|02/22/2006 11:05:47 AM|SB24|H|Introduced and ref Judiciary    HJ20, pg 1256|02/22/2006 11:05:47 AM",
        "2006|0987|03/09/2006 08:23:45 AM|SB24|H|===CANCELLED===Public Hearing    March 21    10:00   RM208/LOB|03/09/2006 08:23:45 AM",
        "2006|0987|03/09/2006 09:33:27 AM|SB24|H|===RESCHEDULED===Public Hearing  March 30   10:00  RM208/LOB|03/09/2006 09:33:27 AM",
        "2006|0987|03/31/2006 07:59:03 AM|SB24|H|Subcommittee Work Session     April 11   9:30  RM208/LOB|03/31/2006 07:59:03 AM",
        "2006|0987|04/20/2006 09:58:29 AM|SB24|H|Comm Rprt:   OTP    April 26 (vote 18-2; CC)   HC 34, pg 1818|04/20/2006 09:58:29 AM"],
    ("HB607", "2005-2006"): [
        "2006|0085|01/26/2005 01:54:05 PM|HB607|H|Introduced and ref to Elec Law;  HJ 15, p 259|01/26/2005 01:54:05 PM",
        "2006|0085|02/23/2005 06:15:20 PM|HB607|H|Hearing   Mar 15   2:00   RM308,LOB|02/23/2005 06:15:20 PM",
        "2006|0085|03/23/2005 09:20:58 AM|HB607|H|Retained in committee|03/23/2005 09:20:58 AM",
        "2006|0085|10/25/2005 02:22:58 PM|HB607|H|Ret Subcommittee Work Session   Nov 1  10:00  RM308/LOB|10/25/2005 02:22:58 PM",
        "2006|0085|10/25/2005 02:23:26 PM|HB607|H|===RESCHEDULED===   Ret Subcommittee Work Session   Nov 8 10:00  RM308/LOB|10/25/2005 02:23:26 PM",
        "2006|0085|11/01/2005 12:52:06 PM|HB607|H|Ret Subcommittee Work Session   Nov 8  9:00 ===NOTE TIME CHANGE===|11/01/2005 12:52:06 PM",
        "2006|0085|11/08/2005 01:20:20 PM|HB607|H|Ret Subcommittee Work Session    Nov 15 10:00  RM308/LOB  <Rep Drisko>|11/08/2005 01:20:20 PM",
        "2006|0085|11/15/2005 01:43:12 PM|HB607|H|Ret Subcommittee Work Session    Nov 22 9:30  RM308/LOB  <Rep Drisko>|11/15/2005 01:43:12 PM",
        "2006|0085|12/01/2005 04:16:05 PM|HB607|H|Comm Rprt for Jan 18:  ITL  (vote 11-3;  RC)|12/01/2005 04:16:05 PM"],
    ("HB114", "2013-2014"): [
        "2014|0067|01/03/2013 09:38:55 AM|HB114|H|Introduced 1/3/2013 and Referred to Municipal and County Government; HJ 12, PG.183|01/03/2013 09:38:55 AM",
        "2014|0067|01/09/2013 08:07:44 AM|HB114|H|Public Hearing: 1/15/2013 2:00 PM LOB 301|01/09/2013 08:07:44 AM",
        "2014|0067|01/10/2013 08:24:51 AM|HB114|H|===CANCELLED=== Public Hearing: 1/15/2013 2:00 PM LOB 301|01/10/2013 08:24:51 AM",
        "2014|0067|01/16/2013 10:45:08 AM|HB114|H|Public Hearing: 1/22/2013 11:30 AM LOB 301|01/16/2013 10:45:08 AM",
        "2014|0067|01/23/2013 11:16:52 AM|HB114|H|Executive Session: 1/30/2013 10:00 AM LOB 301|01/23/2013 11:16:52 AM",
        "2014|0067|01/30/2013 04:04:01 PM|HB114|H|Retained in Committee|01/30/2013 04:04:01 PM"],
    ("HB142", "2015-2016"): [
        "2015|0091|01/08/2015 09:45:42 AM|HB142|H|Introduced and Referred to Education; HJ 12, PG. 209|01/08/2015 09:45:42 AM",
        "2015|0091|01/21/2015 11:46:00 AM|HB142|H|Public Hearing: 2/3/2015 10:00 AM LOB 207|01/21/2015 11:46:00 AM",
        "2015|0091|01/29/2015 09:15:21 AM|HB142|H|===CANCELLED=== Public Hearing: 2/3/2015 10:00 AM LOB 207|01/29/2015 09:15:21 AM",
        "2015|0091|01/29/2015 09:46:40 AM|HB142|H|Public Hearing: 2/12/2015 1:00 PM LOB 207|01/29/2015 09:46:40 AM",
        "2015|0091|02/04/2015 11:56:17 AM|HB142|H|===CANCELLED=== Public Hearing: 2/12/2015 1:00 PM LOB 207|02/04/2015 11:56:17 AM",
        "2015|0091|02/04/2015 11:58:53 AM|HB142|H|Public Hearing: 2/12/2015 10:00 AM LOB 207|02/04/2015 11:58:53 AM",
        "2015|0091|02/11/2015 11:19:58 AM|HB142|H|Executive Session: 2/17/2015 10:00 AM LOB 207|02/11/2015 11:19:58 AM",
        "2015|0091|02/20/2015 12:02:55 PM|HB142|H|Committee Report: Ought to Pass with Amendment #2015-0424h for Mar 4 (Vote 16-4; RC); HC18, PG. 356|02/20/2015 12:02:55 PM"],
    ("SB17", "2009-2010"): [
        "2009|0256|01/08/2009 01:23:48 PM|SB17|S|Introduced and Referred to Executive Departments and Administration; SJ 2, Pg.21|01/08/2009 01:23:48 PM",
        "2009|0256|01/08/2009 04:06:04 PM|SB17|S|Hearing; === RECESSED === January 13, 2009, Room 101, LOB, 2:40 p.m.; SC6 Pg. 2|01/08/2009 04:06:04 PM",
        "2009|0256|01/15/2009 09:36:51 AM|SB17|S|Hearing; === RECONVENE === January 27, 2009, Room 101, LOB, 2:00 p.m.; SC7|01/15/2009 09:36:51 AM",
        "2009|0256|01/22/2009 11:57:12 AM|SB17|S|Hearing; === CANCELLED === RECONVENE === January 27, 2009, Room 101, LOB, 2:00 p.m.; SC8|01/22/2009 11:57:12 AM",
        "2009|0256|03/18/2009 04:22:50 PM|SB17|S|Hearing; === RECONVENE === March 24, 2009, Room 101, LOB, 2:00 p.m.; SC16|03/18/2009 04:22:50 PM",
        "2009|0256|03/26/2009 11:06:20 AM|SB17|S|Committee Report; Inexpedient to Legislate [04/01/09]; SC17|03/26/2009 11:06:20 AM",
        "2009|0256|04/01/2009 03:25:59 PM|SB17|S|Inexpedient to Legislate, MF, VV; S J 10, Pg.165|04/01/2009 03:25:59 PM"],
    ("HB145", "2007-2008"): [
        "2008|0662|07/05/2007 12:47:20 PM|HB145|H|Sales Tax Subcommittee Work Session: 8/21/07 1:00 PM LOB 202|07/05/2007 12:47:20 PM",
        "2008|0662|08/14/2007 03:57:09 PM|HB145|H|==CANCELLED==Casino Subcommittee Work Session: 8/21/07 9:00 AM LOB 202|08/14/2007 03:57:09 PM",
        "2008|0662|08/14/2007 03:57:59 PM|HB145|H|==CANCELLED==Casino Subcommittee Work Session: 8/21/07 1:00 PM LOB 207|08/14/2007 03:57:59 PM"],
}


def _told_from_rows(N, term, bill, lines):
    """A bill's history built from its real docket rows, read as the docket's
    own file is (parse_docket): the marks on a row are what overtaken() reads."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-overtaken-"))
    saved = (N.CORRECTIONS, N.MISFILED, N.TERM, N.INTRODUCTIONS)
    try:
        (tmp / "Docket.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        rows = N.parse_docket(str(tmp / "Docket.txt"))[bill]
        N.CORRECTIONS, N.MISFILED, N.INTRODUCTIONS, N.TERM = [], [], {}, term
        return N.build(bill, rows)
    finally:
        N.CORRECTIONS, N.MISFILED, N.TERM, N.INTRODUCTIONS = saved
        shutil.rmtree(tmp, ignore_errors=True)


# Real rows: Docket_db_2005-2006.txt 2119-2121 (SB 139 of 2005) and
# Docket_db_1999-2000.txt 18606-18608 (SB 312 of 2000) and 13072-13075 (SB 387
# of 2000).
_DOCKET_TIME_CHANGE = [
    '2005|0330|01/06/2005 11:02:19 AM|SB139|S|Introduced and Referred to Judiciary; SJ 2, Pg.29|01/06/2005 11:02:19 AM',
    '2005|0330|02/10/2005 02:03:07 PM|SB139|S|Hearing; February 22, 2005, Room 105-A, SH 1:30 p.m.; SC7|02/10/2005 02:03:07 PM',
    '2005|0330|02/16/2005 02:34:11 PM|SB139|S|Hearing; === TIME CHANGE === February 22, 2005, Room 105-A, SH, 2:00 p.m.; SC8|02/16/2005 02:34:11 PM',
    '2000|2641|01/05/2000 10:25:17 AM|SB312|S|Introduced and Ref. to Public Affairs; SJ Convening Day, Pg.7|01/05/2000 10:25:17 AM',
    '2000|2641|01/06/2000 04:13:15 PM|SB312|S|Hearing, 2/23/00, Room 104, LOB, 1:00 p.m.; SC1, Pg.9|01/06/2000 04:13:15 PM',
    '2000|2641|02/16/2000 03:43:03 PM|SB312|S|===TIME CHANGE=== Feb.23, Room 104, LOB, 1:45 p.m.; SC 12, Pg.9|02/16/2000 03:43:03 PM',
    '2000|2068|01/05/2000 09:25:22 AM|SB387|S|Introduced and Ref. to Transportation; SJ Convening Day, Pg. 11|01/05/2000 09:25:22 AM',
    '2000|2068|01/06/2000 01:40:01 PM|SB387|S|Hearing, Jan. 25 , Room 104 , LOB ,3:40 p.m.;SC1, Pg.6|01/06/2000 01:40:01 PM',
    '2000|2068|01/19/2000 03:50:53 PM|SB387|S|==TIME CHANGE== Jan. 25, Room 104, LOB, 3:25 p.m.; SC 5, Pg.3|01/19/2000 03:50:53 PM',
    '2000|2068|01/26/2000 04:05:34 PM|SB387|S|==RESCHEDULED==Feb.15,Room 104,LOB,3:30 p.m.; SC 6,Pg.6|01/26/2000 04:05:34 PM',
]

# The sittings _senate_room_change reads, with the room each was moved to.
_ROOM_CHANGED = {("2003-2004", "SB339", "2004-01-13"): "LOB 102",
                 ("2003-2004", "SB427", "2004-02-17"): "LOB 205-207",
                 ("2005-2006", "SB342", "2006-01-19"): "LOB 100",
                 ("2001-2002", "SB164", "2001-06-20"): "LOB 207",
                 ("2001-2002", "SB146", "2001-03-06"): "Representatives Hall",
                 ("1999-2000", "HB1548", "2000-04-24"): "LOB 201-203"}

# The hearings _clock_semicolon reads: (term, bill, chamber, day) -> the hour.
_CLOCK_SEMICOLON = {("1999-2000", "SB362", "S", "2000-02-08"): "14:50",
                    ("1999-2000", "HB1337", "S", "2000-04-04"): "14:00",
                    ("1999-2000", "HB452", "H", "1999-02-09"): "14:00",
                    ("2003-2004", "SB171", "S", "2003-02-18"): "13:30",
                    ("2005-2006", "HB199", "S", "2005-04-05"): "14:20"}

# (term, bill, day) -> the committee each hearing above is filed under.
_CLERKS_COMMITTEES = {("1999-2000", "HB208", "1999-04-27"): "Energy and Economic Development",
                      ("1999-2000", "HB214", "1999-04-27"):
                          "Public Institutions, Health and Human Services",
                      ("2001-2002", "HB390", "2001-05-29"):
                          "Public Institutions, Health and Human Services"}


def _ev(body, raw, type_="other", motion=None, action=None, date="2026-01-01"):
    return {"body": body, "raw": raw, "type": type_, "motion": motion,
            "action": action, "cancelled": False, "date": date}


def _nar(*evs, hands=()):
    return {"events": list(evs), "stages": [{"hand": h} for h in hands]}


# THE VOTERS' VOTE ON A CONSTITUTIONAL AMENDMENT, as ballot_results.json
# holds it: CACR 6 of 2024 (the judicial retirement age), CACR 30 of 2006
# (eminent domain), CACR 7 of 1992 (the military reserve) and CACR 22 of 1998
# (a senator's age), with the figures the source gives and the rows their
# dockets have. Since 7 October 2026 a decided row's source is the Secretary
# of State -- its sos.nh.gov results from 2016, NHPR's scan of its Manual for
# the General Court before -- and the one still to come keeps Ballotpedia's
# list (the person's decision of that day).
_SOS_2024 = ("https://www.sos.nh.gov/2024-general-election-results",
             "2024 general election results, sos.nh.gov")
_MANUAL_1993 = ("https://electiondatabase.nhpr.org/document/690?page=324",
                "Manual for the General Court 1993, p. 442 (NHPR's scan)")
_MANUAL_1999 = ("https://electiondatabase.nhpr.org/document/686?page=184",
                "Manual for the General Court 1999, p. 350 (NHPR's scan)")
_BALLOTPEDIA = ("https://ballotpedia.org/List_of_New_Hampshire_ballot_measures",
                "List of New Hampshire ballot measures")


def _voters_row(term, bill, election, yes, no, label="Question 1", src=_SOS_2024,
                read="2026-10-07"):
    return {"term": term, "bill": bill, "election": election, "label": label,
            "yes": yes, "no": no, "read": read, "source": src[0], "cite": src[1]}


def _ballot_file():
    """ballot_results.json's rows by (term, bill). The file is tracked, the
    person's own (HANDMADE), and the night's clone carries it, so a check of
    what it holds runs with the code checks."""
    f = Path("corrections/ballot_results.json")
    assert f.exists(), "ballot_results.json is not here"
    return {(r.get("term"), r.get("bill")): r
            for r in json.loads(f.read_text(encoding="utf-8"))["rows"]}


# ---- what the record says ended a measure (2 October 2026) -------------------
#
# A sweep of all nineteen terms read every status the site gives against the
# measure's own docket rows, its status codes and, where one is on disk, the
# journal. The checks from here to the conferees' below each hold one of the
# readings that came of it, on the rows it was found on.

def _narrated(N, term, bill, lines, introduction=None, reported=None):
    """A measure's history as narrative.build tells it from real docket rows
    (Docket*.txt lines), with no corrections file and no journal reading: the
    House Journals' reports (narrative.house_reported) are `reported`,
    {bill: {committee}}, and none where it is None, whatever is on disk."""
    saved = (N.CORRECTIONS, N.MISFILED, N.TERM, N.INTRODUCTIONS)
    journals = (getattr(N, "JOURNALS", None), getattr(N, "HOUSE_REPORTED", None))
    try:
        N.CORRECTIONS, N.MISFILED, N.INTRODUCTIONS = [], [], {}
        N.TERM = term
        if journals[1] is not None:
            N.JOURNALS = Path(tempfile.gettempdir()) / "gr-no-journals-here"
            N.HOUSE_REPORTED = {term: dict(reported or {})}
        return N.build(bill, _docket_rows(lines), introduction=introduction)
    finally:
        N.CORRECTIONS, N.MISFILED, N.TERM, N.INTRODUCTIONS = saved
        if journals[1] is not None:
            N.JOURNALS, N.HOUSE_REPORTED = journals


# THE CHIP, ENDING BY ENDING (the person, 5 October 2026): "Became Law, Died,
# Interim Study, Tabled (For bills currently on the table during session,
# bills that died at the end of session on the table are just labeled as
# Died), Vetoed (For those pending a vote ...), and Withdrawn." Written out
# here, not read from build_site_v2, so that chip_word moving an ending to
# another word fails until this table moves with it. Each status is what
# bill_disposition gives; a stage is "done" in a term that has ended.
_CHIP_STAGES = ("In committee", "In progress", "Committee report filed",
                "Retained in committee", "Re-referred to committee", "Passed one chamber",
                "One chamber did not concur",
                "One chamber did not concur; a committee of conference was asked for",
                "In a committee of conference", "Conference committee report adopted")
# Not one of the six, in session or after it: each keeps its word until the
# person gives it one. A bill the House did not introduce is not "Withdrawn"
# -- no record says it was (HB 87 and HB 134 of 2009 carry an introduced
# bill's database code) -- and one awaiting the governor is not "Died": the
# governor can act after the last session day.
_CHIP_OWN = ("Proposed for the special session", "Not introduced",
             "Passed, awaiting the governor")
_CHIP_FINISHED = {
    "law": {s: "Became Law" for s in ("Signed into law", "Became law unsigned",
                                      "Veto overridden, became law")},
    "study": {"Referred for interim study": "Interim Study"},
    # In a session that has ended nothing is awaited: the veto stood.
    "veto": {s: "Died" for s in ("Vetoed", "Vetoed, awaiting an override vote",
                                 "Vetoed, override vote pending", "Vetoed, override failed")},
    "done": {**{s: "Died" for s in (
        "Killed", "Died on the table", "Died when the session ended", "Failed to pass",
        "Indefinitely postponed", "Refused introduction",
        "Died when the conference report was rejected", "Died: conferees could not agree",
        "Died: the chambers did not agree on a version",
        "Laid on the table", *_CHIP_STAGES)},
             **{s: "Withdrawn" for s in ("Withdrawn", "Withdrawn prior to introduction")},
             **{s: s for s in _CHIP_OWN}},
}
# While the session has days left: on the table is Tabled, a veto whose
# override vote is to come is Vetoed, and a stage is its own word.
_CHIP_LIVE = {
    "active": {**{s: s for s in _CHIP_STAGES}, "Laid on the table": "Tabled",
               "Passed, awaiting the governor": "Passed, awaiting the governor"},
    "veto": {"Vetoed": "Vetoed", "Vetoed, awaiting an override vote": "Vetoed",
             "Vetoed, override vote pending": "Vetoed", "Vetoed, override failed": "Died"},
}


# THE CHECK'S OWN READING OF A REMOVAL FROM THE CONSENT CALENDAR, written
# apart from narrative.removed_from_consent and looser than it on purpose: any
# word starting "remov" within forty characters of "consent", "cons cal",
# "con cal" or "CC", whatever stands between. The check shared the reader's
# pattern, and passed while 149 notes stood beside removals neither of them
# read ("Sen. Daniels Moved to Remove HB 1313 from the Consent Calendar",
# "REMOVED FROM CON CAL"). What it sets aside is named for what it is: a
# special order about the bills removed, a conference report's consent
# calendar, and the Senate's Laid on the Table Consent List of 16 June 2020.
_CONSENT_REMOVAL_LOOSE = re.compile(
    r"remov\w*.{0,40}?(?:consent|\bcons?\.?\s*cal|\bCC\b)", re.I)
_CONSENT_REMOVAL_NOT = re.compile(
    r"special\s+order|\bconf\w*\.?\s+comm\w*\.?\s+consent|consent\s+list", re.I)


_WRITTEN_DAY = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_COMMITTEE_WORK = {"hearing", "exec", "worksession", "report", "retained", "interim_report"}


# THE SITTING DAYS OF THE RECORD ON DISK, READ ONCE A RUN (23 October 2026).
# Three checks of the built site -- this one, _no_phantom_sittings and
# _every_rollcall_on_its_sitting -- each called session_days.load() on
# narratives.json and the rollcalls.json beside it, and each paid the whole
# read: 108 seconds of preflight --built together on GitHub's machine. They
# ask it the same question of the same files and only read what it answers,
# so it is answered once a run for those files as they stand (where each
# is, its size and its time of writing), and a file that moves is read again.
_SITTINGS = {}


def _sittings_on_disk(SD, narr, rolls=None):
    """session_days.load(narr, rolls), once a run for the same two files.
    `rolls` None is the rollcalls.json beside narr, as load() reads it."""
    narr = Path(narr)
    beside = narr.parent / SD.ROLLCALLS if rolls is None else Path(rolls)

    def stamp(p):
        try:
            st = p.stat()
        except OSError:
            return (str(p.resolve()), None, None)
        return (str(p.resolve()), st.st_size, st.st_mtime_ns)
    key = (stamp(narr), stamp(beside))
    if key not in _SITTINGS:
        _SITTINGS[key] = SD.load(narr) if rolls is None else SD.load(narr, rolls)
    return _SITTINGS[key]


def _json3(lines, start=5.0, step=4.0):
    """A caption file in YouTube's json3 shape: the opening window event, then
    one event per line with a word to a seg, as yt-dlp writes them."""
    ev = [{"tStartMs": 0, "dDurationMs": int((start + step * len(lines)) * 1000),
           "id": 1, "wpWinPosId": 1, "wsWinStyleId": 1}]
    t = start
    for line in lines:
        segs = [{"utf8": w} if not i else {"utf8": " " + w, "tOffsetMs": i * 200}
                for i, w in enumerate(line.split())]
        ev.append({"tStartMs": int(t * 1000), "dDurationMs": int(step * 1000),
                   "wWinId": 1, "segs": segs})
        t += step
    return {"wireMagic": "pb3", "events": ev}


# ===================================================== code: the captions inbox ==
#
# THE CAPTIONS INBOX (17 October 2026). YouTube refuses GitHub's machine and
# answers the laptop, so the laptop asks for what the night's state says
# waits and puts each caption file in the bucket's inbox (livestreams.py
# --to-inbox), and the night takes them (--since-state --inbox) and clears
# what it no longer waits for (cloud.py inbox-down, inbox-clear). Each rule
# of that design has a check here: the laptop adds inbox entries and writes
# no state and no kit; the night takes only a waiting recording's captions,
# and only a sound entry; a dry night consumes nothing. None of them asks
# YouTube or R2: saved caption files and a folder standing in for the bucket.

def _inbox_words():
    return json.dumps(_json3(["I am opening the hearing on House Bill 1491"]))


def _inbox_files(bucket):
    """{path: bytes} of everything in a folder bucket, its .meta included."""
    bucket = Path(bucket)
    return {p.relative_to(bucket).as_posix(): p.read_bytes()
            for p in bucket.rglob("*") if p.is_file()} if bucket.exists() else {}


# ============================================================ code: front end ==

def page_source(name="src/pages/bills.html"):
    """bills.html together with the app.css, components.js and app.js it loads.

    The page was one file with a <style> and a <script> in it. It is three
    files now, so a bill's own page can load the SAME renderer rather than a
    second copy of it. Everything these checks look for -- the palette, the
    station branches, the declaration order -- moved into app.js and app.css
    with it.

    A check that reads only the page now finds nothing to disagree with and
    passes, which is worse than failing, so there is one reader rather than
    three places to remember. Returns ("", None) when the page is not here, so
    a caller can skip rather than assert against nothing.
    """
    p = Path(name)
    if not p.exists():
        p = Path("site") / p.name
    if not p.exists():
        return "", None
    out = p.read_text(encoding="utf-8")
    for asset in ("app.css", "components.js", "app.js"):
        f = p.parent / asset
        if f.exists():
            out += "\n" + f.read_text(encoding="utf-8")
    return out, p


def _cite_plain(html_text):
    """A citation's address as one run of text again, for a check that reads
    a page's HTML: shell.cite_url draws it with a <wbr> after each slash and
    its last part in a span of its own, so turning tags into spaces, or
    looking for the address as a string, would find it in pieces. The spans
    are unwrapped where they open; their ends follow the address's stop."""
    return re.sub(r'<wbr>|<span class="cite(?:url|tail)">', "", html_text)


def _cors_rules(text):
    """[(address pattern, compiled, value)] for each Access-Control-Allow-Origin
    line of a _headers text, read as Cloudflare Pages reads one: a line that,
    trimmed, starts with "/" or a scheme starts a rule, whatever its
    indentation, and any other line is a header of the rule above it; a
    pattern's splat (*) matches anything, a placeholder (:name) one segment.
    A rule that carries the header twice is listed twice, as Pages sends it."""
    out, at = [], None
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if re.match(r"(?:[^\s]+://|/)", s):
            at = s
            continue
        name, _, value = s.partition(":")
        if at and name.strip().lower() == "access-control-allow-origin":
            out.append((at, re.compile("".join(
                ".*" if t == "*" else "[^/]+" if t.startswith(":") else re.escape(t)
                for t in re.split(r"(\*|:[A-Za-z]\w*)", at) if t)), value.strip()))
    return out


def _cors_said(rules, path):
    """The Access-Control-Allow-Origin values _headers sends `path`: one per
    matching rule, in order. Pages appends a header a second rule names
    again, so two values are served as "*, *", which a browser refuses."""
    return [v for _at, rx, v in rules if rx.fullmatch(path)]


def _css_hex(v):
    h = v.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _css_ratio(a, b):
    """WCAG contrast of two (r, g, b) colours."""
    def lum(c):
        ch = [v / 255 for v in c]
        ch = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


# ---- the stylesheet, read as rules -------------------------------------------
#
# The checks below read app.css as rules rather than as text, because what
# they ask -- which size a rule sets, which colour it writes, which two
# tokens it draws together -- is a question about one declaration in one
# block, and the block's at-rule (print, forced colours) decides how it is
# read. Comments come out first; a block inside an at-rule carries it.

def _css_rules(text):
    """[(at-rules around it, selector, body, line)] for every block of
    declarations in a stylesheet. An at-rule's own block is not one; the
    rules inside it carry its prelude in their first field."""
    t = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    out, stack, mark, quote, line = [], [], 0, None, 1
    for i, c in enumerate(t):
        if c == "\n":
            line += 1
        if quote:
            if c == quote:
                quote = None
            continue
        if c in "\"'":
            quote = c
        elif c == "{":
            stack.append((" ".join(t[mark:i].split()), i, line))
            mark = i + 1
        elif c == "}":
            if stack:
                prelude, at, at_line = stack.pop()
                body = t[at + 1:i]
                if not prelude.startswith("@") and "{" not in body:
                    out.append((tuple(p for p, _, _ in stack), prelude, body, at_line))
            mark = i + 1
        elif c == ";" and (not stack or stack[-1][0].startswith("@")):
            mark = i + 1
    return out


def _css_decls(body):
    """[(property, value)] of a declaration block, split on the semicolons
    that are not inside brackets or quotes; property names in lower case."""
    out, cur, depth, quote = [], [], 0, None
    for c in body + ";":
        if quote:
            cur.append(c)
            if c == quote:
                quote = None
            continue
        if c in "\"'":
            quote = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if c == ";" and depth == 0:
            d = "".join(cur)
            cur = []
            if ":" in d:
                k, v = d.split(":", 1)
                out.append((k.strip().lower(), v.replace("!important", "").strip()))
        else:
            cur.append(c)
    return out


def _css_palette(text):
    """{"light": {--token: value}, "dark": {...}}: every custom property of
    app.css's palette, from its :root block and its DARK:OS block (which
    _palette holds identical to DARK:CHOSEN)."""
    end = text.find("/* PALETTE END")
    light, dark = {}, {}
    for ctx, sel, body, _ in _css_rules(text[:end] if end > 0 else text):
        for k, v in _css_decls(body):
            if not k.startswith("--"):
                continue
            if sel == ":root" and not ctx:
                light[k] = v
            elif sel == ':root:not([data-theme="light"])' and ctx:
                dark[k] = v
    return {"light": light, "dark": dark}


def _css_px(value, tokens, seen=()):
    """(pixels, how) for a font size, at the browser's default of 16px:
    "px", "rem" or "pt" with the number; or None with "relative" (em, %, a
    keyword: it depends on the parent, which the rendered sweep measures),
    "undefined --x" (a var() nothing defines) or "unread"."""
    v = value.strip()
    m = re.fullmatch(r"var\(\s*(--[\w-]+)\s*(?:,\s*(.+))?\)", v)
    if m:
        name, fallback = m.group(1), m.group(2)
        if name in tokens and name not in seen:
            return _css_px(tokens[name], tokens, seen + (name,))
        if fallback:
            return _css_px(fallback, tokens, seen)
        return None, f"undefined {name}"
    m = re.fullmatch(r"(\d*\.?\d+)(px|rem|pt)", v)
    if m:
        return float(m.group(1)) * {"px": 1, "rem": 16, "pt": 4 / 3}[m.group(2)], m.group(2)
    if re.fullmatch(r"(\d*\.?\d+)(em|%)|inherit|initial|unset|smaller|larger|[a-z-]*small|"
                    r"[a-z-]*large|medium", v):
        return None, "relative"
    return None, "unread"


def _css_font_size(prop, value):
    """The size a declaration sets, as written, or None: font-size's value,
    or the size inside a font shorthand ("600 12px var(--sans)")."""
    if prop == "font-size":
        return value.strip()
    if prop != "font":
        return None
    for part in re.findall(r"var\([^)]*\)|\S+", value):
        m = re.match(r"(\d*\.?\d+(?:px|rem|pt|em|%))(?:/\S*)?$", part)
        if m:
            return m.group(1)
        if part.startswith("var(--t-"):
            return part
    return None

# What a builder may write that is not the palette's, and why. A file named
# with None is left out whole; with a string, from that string on.
_FRONT_EXEMPT = {
    "build_brand.py": None,     # the brand's own art: the icons, the manifest, the share images
    "seating.py": "def main(",  # from here, the --svg preview a person opens; never published
}


def _front_sources(root="."):
    """[(name, text)] of every file whose markup reaches a page besides
    app.css: components.js, app.js, find.js, print.js (a bill's print sheet),
    bills.html and every builder in src/pages/ (components.py among them),
    each cut where _FRONT_EXEMPT says."""
    base = Path(root)
    files = [base / "src/pages/components.js", base / "src/pages/app.js", base / "src/pages/find.js",
             base / "src/pages/print.js",
             base / "src/pages/bills.html"] + sorted((base / "src/pages").glob("*.py"))
    out = []
    for f in files:
        if not f.is_file():
            continue
        if f.name in _FRONT_EXEMPT and _FRONT_EXEMPT[f.name] is None:
            continue
        t = f.read_text(encoding="utf-8")
        cut = _FRONT_EXEMPT.get(f.name)
        if cut and cut in t:
            t = t[:t.index(cut)]
        out.append((f.name, t))
    return out


def _line_of(text, at):
    return text.count("\n", 0, at) + 1


def _css_selectors(sel):
    """A rule's selector list, each one with its spaces made single. A comma
    inside :is() or :not() does not part it."""
    out, depth, cur = [], 0, ""
    for ch in sel:
        depth += (ch == "(") - (ch == ")")
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    return [" ".join(s.split()) for s in out + [cur] if s.strip()]


def _css_token_colour(spec, scheme):
    """(r, g, b) for a token or a color-mix of two tokens in srgb, or None."""
    if "|" in spec:
        a, pct, b = spec.split("|")
        ca, cb = _css_token_colour(a, scheme), _css_token_colour(b, scheme)
        if not ca or not cb:
            return None
        k = float(pct) / 100
        return tuple(x * k + y * (1 - k) for x, y in zip(ca, cb))
    v = scheme.get(spec, "")
    return _css_hex(v) if re.fullmatch(r"#[0-9A-Fa-f]{3}|#[0-9A-Fa-f]{6}", v.strip()) else None


def _built_sites():
    """[(what to call it, the site folder)] for each built site the stylesheet
    checks read: the fixture's, which the builders write once a run
    (_fixture_site_shared), wherever the builders are; and site/, where a site
    has been built.

    THE FIXTURE'S, SO THAT THESE GUARD THE NIGHT (2 October 2026). nightly.py
    runs the code checks BEFORE it builds: on GitHub's machine there is no
    site/ yet, and a check that read only site/ skipped on the one run that
    stands between a change to build_pages.py or app.css and the deploy. The
    laptop's built site is still read where there is one: it is what a
    reader's browser was given.
    """
    sites = []
    if not [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]:
        sites.append(("the fixture's site", _fixture_site_shared()[0] / "site"))
    if Path("site/app.css").exists():
        sites.append(("site/", Path("site")))
    return sites


ic_SOURCES = {
    # Every build_all `needs=` path that no step declares and git does not
    # track, with the thing that creates it. A fresh clone has none of these,
    # so each one is a question a contributor will ask, and this is the answer.
    "RollCallSummary.txt": "the General Court's bulk file, archived by snapshot_gencourt.py",
    "Docket.txt": "the General Court's bulk file, archived by snapshot_gencourt.py",
    "legislators.txt": "the General Court's bulk file, archived by snapshot_gencourt.py",
    "bill_status.json": "fetch_bill_status.py",
    "data/legislators.json": "build_data.py, which does not declare it",
    "data/member_votes.json": "build_data.py, which does not declare it",
    "verification_manifest.csv": "build_manifest.py",
    "site/legislators.json": "build_site_v2.py, which does not declare it",
    "site/former.json": "build_site_v2.py, which does not declare it",
    "site/towns.json": "build_town_pages.py, which does not declare it",
    "site/idx": "build_indexes.py, which does not declare it",
    "bill_text.json": "fetch_bill_text.py, the current term's bills as the "
                      "General Court prints them; the kit carries it",
    "work": "fetch_captions.py -- a directory of caption folders",
    "calendars": "fetch_calendar_archive.py -- a directory of PDFs",
    "journals": "fetch_calendar_archive.py, the House Journals' PDFs, and "
                "extract_calendar_text.py, the .txt beside each -- a directory "
                "of year folders; the kit carries the text (journals/*/*.txt)",
    "journals_senate": "fetch_calendar_archive.py, the Senate Journals' PDFs, and "
                       "extract_calendar_text.py, the .txt beside each -- a directory "
                       "of year folders; the kit carries the text "
                       "(journals_senate/*/*.txt)",
    "legislation": "fetch_legislation.py -- a directory of saved bill pages",
    "db/DocumentVersion.psv": "fetch_archive_db.py, which dumps the SQL views",
    "db/LegislationText.psv": "fetch_archive_db.py, which dumps the SQL views",
    "db/Legislation.psv": "fetch_archive_db.py, which dumps the SQL views; the night's "
                          "take_views every night",
    "db/CandH_Reports.psv": "fetch_archive_db.py, which dumps the SQL views",
    "db/Legislators.psv": "fetch_archive_db.py, which dumps the SQL views",
    "db/_columns.json": "fetch_archive_db.py, the column order of each view it dumps",
    "db/NH_RSA.psv": "fetch_archive_db.py --only NH_RSA, the statute table (a person's run)",
    # The statutory and study committees' views (18 October 2026), which the
    # night refreshes (nightly.STUDY_NIGHTLY and STUDY_WEEKLY) and the kit carries.
    "db/StatStudDetails.psv": "fetch_archive_db.py, which dumps the SQL views; the night's "
                              "study-committee refresh",
    "db/StatStudMembers.psv": "fetch_archive_db.py, which dumps the SQL views; the week's "
                              "study-committee refresh",
    "db/StatStudMeetings.psv": "fetch_archive_db.py, which dumps the SQL views; the night's "
                               "study-committee refresh",
    "db/past/PastSponsors.psv": "fetch_past_db.py, which dumps the six Past* views",
    "db/past/PastLegislation.psv": "fetch_past_db.py, which dumps the six Past* views",
    "db/past/_manifest.json": "fetch_past_db.py, the column order of each Past* view",
    "past_members.json": "fetch_sponsors_by_member.py --members, one request",
    "committee_reports.json": "fetch_committee_reports.py, which does not declare it",
    "archive/livestreams.json": "livestreams.py --since-state, the nightly's "
                              "step before build_all",
}


# A NAME THAT READS AS A LIST: a separator, a role mark left in, or two names joined.
LSR_LISTLIKE = re.compile(r"[;,()]|\band\b|\s&\s")


def _strip_js_comments(js):
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return "\n".join(re.sub(r"//.*$", "", ln) for ln in js.splitlines())


# THE RAIL ON A PHONE, MEASURED WITHOUT A BROWSER (the review of 5 October
# 2026). Every card draws the dated rail since that day, and on a 360px phone
# a list card's was 272px: five stops of 54px, and 4,132 of the index's rails
# set two stops' words within 3px of each other -- "8 Jan 2025 8 Jan 2026",
# "voice vote, amended" running into "postponed" -- while every check passed,
# because the only ones on the rail asked whether two CSS rules were there.
#
# This lays a rail out the way app.css does, in the advance widths of the
# faces it is drawn in (_RAIL_FACE, below; Verdana's until the words went to
# 14px on 8 October 2026), so a rail that passes here has room in the face
# that loads and in the one it falls back to: the stops share the width
# equally; under each one its words are centred and wrapped at spaces inside
# the stop less its gutter either side (.rail.dated small's padding-inline),
# with a word wider than that overflowing both ways as Chrome centres it; its
# label sits on one line above, at 14px, with its day under it at 14px and,
# on a rail under 552px, the day's year on a line of its own; and the lines
# of neighbouring stops
# share rows. The narrowest gap between two stops' words on one row is the
# answer. Chrome also breaks after a dash, "197–" over "149,", which this
# does not, so it errs narrow.
#
# A stop's words have been its day alone since the same evening (the person:
# "only have dates for the actions under each of the items"): "8 Jan 2025",
# never "voice vote, amended" (_rail_drawn), and month first with its year
# since 8 October 2026, "Jan 8, 2025". The rails below keep the words
# their index rows carry, which a card says and no longer draws.
_VERDANA = dict(zip(map(chr, range(32, 127)), (
    352, 394, 459, 818, 636, 1076, 727, 269, 454, 454, 636, 818, 364, 454, 364, 454, 636, 636,
    636, 636, 636, 636, 636, 636, 636, 636, 454, 454, 818, 818, 818, 545, 1000, 684, 686, 698,
    771, 632, 575, 775, 751, 421, 455, 693, 557, 843, 748, 787, 603, 787, 695, 684, 616, 732,
    684, 989, 685, 615, 685, 454, 454, 454, 818, 636, 636, 601, 623, 521, 623, 596, 352, 623,
    633, 274, 344, 592, 274, 973, 633, 607, 623, 623, 427, 521, 394, 633, 592, 818, 592, 592,
    525, 635, 454, 635, 818)), **{"–": 636, "—": 1000})
# THE FACES THE RAIL IS DRAWN IN, since its words went to 14px (8 October
# 2026): per character the wider of Public Sans, the site's face, and Segoe
# UI, the system face it falls back to on Windows, in thousandths of an em,
# measured in Chrome (canvas measureText at 1000px). Verdana, above, is wider
# than any face in the stack and was the model at 11 and 12px, when it left
# room; at 14px it set "Introduced" over "Senate" where neither real face
# does, so it no longer stands for what a reader can be shown.
_RAIL_FACE = dict(zip(map(chr, range(32, 127)), (
    274, 284, 426, 603, 659, 904, 800, 248, 303, 309, 417, 684, 242, 400, 225, 390, 612, 539,
    596, 630, 629, 641, 623, 601, 648, 625, 226, 240, 684, 684, 684, 521, 955, 710, 671, 689,
    701, 621, 594, 733, 766, 283, 389, 682, 578, 898, 754, 754, 637, 754, 677, 670, 594, 701,
    673, 954, 688, 607, 637, 303, 379, 303, 684, 518, 268, 553, 597, 544, 597, 567, 396, 623,
    577, 248, 263, 562, 303, 865, 577, 586, 596, 596, 391, 506, 389, 581, 504, 780, 565, 535,
    481, 328, 263, 332, 684)), **{"–": 555, "—": 1117})


_SUMMARY_VOTES = {
    "b": {"id": "HB1", "year": "2025", "term": "2025-2026"},
    "d": {
        "rollcalls": [
            {"date": "2025-03-12", "body": "H", "yeas": 231, "nays": 99, "question": "Ought to Pass", "vote_kind": "RC",
             "passed": True, "members": [], "tally": {}},
            {"date": "2025-03-12", "body": "H", "yeas": 231, "nays": 99, "question": "Ought to Pass again",
             "vote_kind": "RC", "passed": True, "members": [], "tally": {}},
            {"date": "2025-04-10", "body": "S", "yeas": 16, "nays": 8, "question": "Ought to Pass", "vote_kind": "RC",
             "passed": True, "members": [], "tally": {}},
            {"date": "2025-05-01", "body": "H", "yeas": 198, "nays": 167, "question": "Concur", "vote_kind": "DV",
             "passed": True, "members": [], "tally": {}},
        ],
        "journey": {"steps": [
            {"date": "2025-04-10", "body": "S", "mark": "p", "act": "passed", "text": "Passed on a roll call, 16–8"},
            {"date": "2025-05-01", "body": "H", "mark": "p", "act": "concurred", "text": "Concurred on a division vote, 198–167"},
            {"date": "2025-05-02", "body": "H", "mark": "p", "act": "passed", "text": "Passed, 198–167"},
            {"date": "2025-04-10", "body": "H", "mark": "p", "act": "passed", "text": "Passed, 16–8"},
            {"date": "2025-03-12", "body": "H", "mark": "p", "act": "passed", "text": "Passed, 231–99"},
        ]},
        "stages": [{"label": "On the House Floor", "text":
                    "On May 1, 2025 the House concurred 198–167 on a division vote. On April 10, 2025 the House "
                    "passed it 16–8. On April 10, 2025 the Senate voted 16–8 to pass it on a roll call."}],
    },
}


# Rows shaped as ballot_results.json's, of three sources and one left off, for
# the two checks below: the Secretary of State's with Ballotpedia's figures
# beside it, Ballotpedia's as the file held every row until 7 October 2026,
# one with no cite, and the election still to come.
def _ballot_mixed_rows():
    sos = {**_voters_row("2023-2024", "CACR6", "2024-11-05", 452307, 237221, "Question No. 1"),
           "ballotpedia": {"yes": 452307, "no": 237221, "label": "Question 1",
                           "source": _BALLOTPEDIA[0], "read": "2026-10-05"}}
    bp = _voters_row("1997-1998", "CACR22", "1998-11-03", 119104, 169439, "Question 1",
                     _BALLOTPEDIA, "2026-10-05")
    uncited = {**_voters_row("1991-1992", "CACR7", "1992-11-03", 249759, 204475,
                             "Question No. 4", _MANUAL_1993), "cite": ""}
    pending = _voters_row("2025-2026", "CACR13", "2026-11-03", None, None,
                          "Eliminate Office of Register of Probate Amendment", _BALLOTPEDIA,
                          "2026-10-05")
    return sos, bp, uncited, pending
BASE_HREF = re.compile(r'<base\s+href\s*=\s*"([^"]*)"', re.I)
OFFSITE = re.compile(r'^(?:[a-z][a-z0-9+.\-]*:|//|#)', re.I)
INLINE_BODY = re.compile(r"(?is)(<(script|style)\b[^>]*>).*?</\2\s*>")


# The House Journal for 9 June 1999 (HB 374), 23 March 2000 (HR 20),
# 10 February 1999 (HB 110) and 21 March 2006 (CACR 34), as
# journals/1999/HJ019.txt, journals/2000/HJ009.txt, journals/1999/HJ004.txt
# and journals/2006/HJ009.txt print them, without each committee's statement
# and the names under each roll call.
_JOURNAL_MOTION_AFTER = """
HB 374, relative to the order of names on presidential primary election ballots. (Amendment printed
SJ 22, 6/8/99)

Rep. Arndt moved that the House concur and spoke in favor.

                                                  motion to lay on the table
Rep. Rice moved that the request for concurrence with amendment on HB 374, relative to the order
of names on presidential primary election ballots, be laid on the table.

Rep. Buckley requested a roll call; sufficiently seconded.

                                   YEAS 62 NAYS 273

and the motion failed.

Adopted.

HR 20, urging Congress to pass a pending resolution proposing an amendment to the United States
Constitution relating to voluntary school prayer. MAJORITY: OUGHT TO PASS. MINORITY:
INEXPEDIENT TO LEGISLATE.

Reps. Gary Johnson and Jacobson spoke against.

Reps. Richard Herman and Potter spoke against and yielded to questions.

Reps. Buckley and Ronald Nowe spoke in favor.

Rep. Burling spoke to the bill.

Rep. Ronald Nowe requested a roll call; sufficiently seconded.

The question being the adoption of the majority report.

                                                  motion to lay on the table

Rep. Eugene Gagnon moved that HR 20, urging Congress to pass a pending resolution proposing an
amendment to the United States Constitution relating to voluntary school prayer, be laid on the
table.

On a division vote, 156 members having voted in the affirmative and 185 in the negative, the motion
failed.

The question now being the adoption of the majority report.

YEAS 162 NAYS 179
and the majority report failed.

HB 110-FN-L, authorizing each town and city to determine its methods of raising revenue to fulfill
its obligation to fund public elementary and secondary education. INEXPEDIENT TO LEGISLATE

Rep. Mirski spoke against.

Reps. Vaillancourt and Burling spoke in favor.

Rep. Alger moved Re-commit to Committee.
Rep. Kurk spoke against.
Rep. Alger requested a roll call; sufficiently seconded.
The question being the motion to Re-commit to Committee.

YEAS 50 NAYS 302
and the motion failed.

                                                  motion to lay on the table

Rep. Mirski moved that HB 110-FN-L, authorizing each town and city to determine its methods of
raising revenue to fulfill its obligation to fund public elementary and secondary education be laid on
the table.

The motion failed.

The question now being the adoption of the committee report.

Adopted.

CACR 34, relating to the definition of marriage. Providing that marriage between one man

and one woman shall be the only legal union that shall be valid or recognized in this state.

MAJORITY: INEXPEDIENT TO LEGISLATE. MINORITY: OUGHT TO PASS.
Rep. Balboni spoke against and yielded to question.
Rep. Sorg spoke against.
Rep. Desmarais spoke in favor.

                                      MOTION TO LAY ON THE TABLE

Rep. Hutchinson moved that CACR 34, relating to the definition of marriage. Providing that
marriage between one man and one woman shall be the only legal union that shall be valid
or recognized in this state, be laid on the table.
Rep. James Wheeler requested a roll call; sufficiently seconded.
The question being to lay CACR 34 on the table.

                                                YEAS 55 NAYS 277

and the motion to lay CACR 34 on the table failed.
"""


# ---- the two large files, read once a run -------------------------------------
#
# narratives.json, 246 MB, WAS LOADED SEVEN TIMES A RUN and
# data/member_votes.json, 561 MB, three (2 October 2026), by ten checks that
# each read a field or two. Each is read once now, and what is kept is kept
# under the file's path, its size and the time it was last written: a file
# written again during a run is read again, and the reading of the file it
# replaced is dropped. (Five checks written since loaded their own, and
# _introductions_against_journal had kept its load while three branches
# changed the lines around it; all six take _narratives() since 9 October
# 2026, each by its loading line alone.)
#
# THEY ARE FOR READING. Every check that takes one of these shares the same
# object with the checks after it; one that needs to change what it reads
# loads its own.
#
# THE BALLOTS ARE COUNTED, NOT KEPT, AND NEVER LOADED WHOLE. The file is 2.3
# million rows: 2.2 GB once loaded and nearly 3 GB while it loads, which was
# the most a run of these checks asked of the machine, three times over. Its
# three readers each walked every row for a count: how many ballots sit under
# each bill number, how many of each year name a member and a party, and
# which chamber each member voted in each year. One pass takes all three
# (_ballot_census), a row at a time (_json_rows), in about 100 MB.
_READ_ONCE = {}


def _read_once(path, read):
    """read(path), or what it returned the last time this run called it for
    a file of this path, size and time of writing."""
    p = Path(path)
    st = p.stat()
    was = (str(p.resolve()), read.__name__)
    now = (st.st_size, st.st_mtime_ns)
    if _READ_ONCE.get(was, (None, None))[0] != now:
        _READ_ONCE.pop(was, None)
        _READ_ONCE[was] = (now, read(p))
    return _READ_ONCE[was][1]


def _narratives():
    """narratives.json, {term: {bill: record}}, as json.loads gives it."""
    def whole(p):
        return json.loads(p.read_text(encoding="utf-8"))
    return _read_once("narratives.json", whole)


def _json_rows(path, chunk=1 << 24):
    """Each element of the JSON list a file holds, in the file's order, read
    a piece of the file at a time: neither its text nor the list is ever
    whole in memory. A row is taken only once the comma or the bracket after
    it is in hand, so one cut by the end of a piece -- a number most of all,
    whose first digits read as a number -- is read again with the next piece.
    A file that is not a list, or that ends inside one, raises."""
    decoder = json.JSONDecoder()
    space = " \t\r\n"
    with open(path, encoding="utf-8") as fh:
        buf = fh.read(chunk)
        while buf and not buf.strip():                  # white space, a piece long
            more = fh.read(chunk)
            if not more:
                break
            buf += more
        i = len(buf) - len(buf.lstrip())
        if buf[i:i + 1] != "[":
            raise ValueError(f"{path} does not hold a JSON list")
        i += 1
        while True:
            while i < len(buf) and (buf[i] in space or buf[i] == ","):
                i += 1
            if i < len(buf) and buf[i] == "]":
                return
            try:
                if i >= len(buf):
                    raise json.JSONDecodeError("the piece ends between rows", buf, i)
                row, end = decoder.raw_decode(buf, i)
                while end < len(buf) and buf[end] in space:
                    end += 1
                if end >= len(buf) or buf[end] not in ",]":
                    raise json.JSONDecodeError("the piece ends inside a row", buf, i)
            except json.JSONDecodeError:
                more = fh.read(chunk)
                if not more:
                    raise
                buf, i = buf[i:] + more, 0
                continue
            i = end
            yield row


def _ballot_census():
    """data/member_votes.json, as the three counts its readers take from it,
    each keyed on the row's own values so that a reader applies its own rule
    to them:

      bills   {bill as the row writes it: ballots}, in the file's order of
              first appearance -- _own_lsr_on_disk asks whether each is the
              bill's own number;
      named   {(year, has no party, is named "Member #..."): ballots} --
              _vote_identity sums these into its terms;
      seats   {(year, body, member id)} -- _past_sponsors_chamber reads the
              chamber a member voted in.
    """
    def count(p):
        bills, named, seats = Counter(), Counter(), set()
        for v in _json_rows(p):
            bills[v.get("bill")] += 1
            named[(v.get("year"), (v.get("party") or "X") == "X",
                   str(v.get("name") or "").startswith("Member #"))] += 1
            seats.add((v.get("year"), v.get("body"), str(v.get("member_id") or "")))
        return {"bills": bills, "named": named, "seats": seats}
    return _read_once("data/member_votes.json", count)


def _docket_rows(lines):
    """Docket.txt lines as the rows narrative.build() takes."""
    from datetime import datetime as _dt
    out = []
    for x in lines:
        p = x.split("|")
        out.append({"lsr": f"{p[0]}-{p[1]}", "session": p[0], "body": p[4],
                    "desc": p[5], "flags": [],
                    "created": _dt.strptime(p[2], "%m/%d/%Y %I:%M:%S %p")})
    return out


# Real rows, copied from the dockets on disk: Docket_db_1999-2000.txt lines
# 2970-2973 (HB 605), 263-264 (HB 110), 88-89 (HB 94), 1866-1867 (HB 278) and
# 12500-12501 (HR 10); Docket_db_2005-2006.txt lines 10939-10940 (HB 317),
# 12891-12893 (HB 1240), 8811 (HB 162) and 6199 (SB 42).
_DOCKET_CUT_1999 = {
    "HB605": [
        "1999|0365|04/06/1999 11:07:57 AM|HB605|H|Maj Report  ITL  for  Apr 14   (vote 13-1;CC#2)|04/06/1999 11:07:57 AM",
        "1999|0365|04/14/1999 02:25:49 PM|HB605|H|ITL Report adopted;  Consent Cal reconsidered, Rep Mock|04/14/1999 02:25:49 PM",
        "1999|0365|04/14/1999 03:36:29 PM|HB605|H|MA VV; Removed from Consent Cal, req Rep Mock; Recommitted to|04/14/1999 03:36:29 PM",
        "1999|0365|04/14/1999 03:38:09 PM|HB605|H|committee, Rep Mock MA VV;  HJ40, p943|04/14/1999 03:38:09 PM"],
    "HB110": [
        "1999|0042|02/10/1999 12:16:46 PM|HB110|H|Rep Alger moved to recommit, ML RC(50-302); Rep Mirski moved to Lay on the Table, ML VV; ITL report|02/10/1999 12:16:46 PM",
        "1999|0042|02/10/1999 12:18:53 PM|HB110|H|adopted VV; HJ18, p283-285|02/10/1999 12:18:53 PM"],
    "HB94": [
        "1999|0018|03/04/1999 10:35:30 AM|HB94|H|Rep LaPorte moved to reconsider, MA DIV(190-147); Recommited to Transportation, Rep Packard|03/04/1999 10:35:30 AM",
        "1999|0018|03/04/1999 10:53:29 AM|HB94|H|MA VV;  HJ29, p598|03/04/1999 10:53:29 AM"],
    "HB278": [
        "1999|0238|03/18/1999 04:20:34 PM|HB278|H|Comm Am, AA VV; Rep Soltani moved to recommit, ML VV; Passed with Am and ref to Finance VV;  HJ29,|03/18/1999 04:20:34 PM",
        "1999|0238|03/18/1999 04:22:09 PM|HB278|H|p633-634|03/18/1999 04:22:09 PM"],
    "HR10": [
        "2000|1015|05/25/1999 04:24:10 PM|HR10|H|Taken from the Table, Rep Alukonis MA VV; Reps Kurk & Alukonis Prop Am{1416}(New Title),|05/25/1999 04:24:10 PM",
        "2000|1015|05/25/1999 04:25:07 PM|HR10|H|AA VV; Laid on the Table, Rep Alukonis MA VV; HJ58, p1579-1580|05/25/1999 04:25:07 PM"],
    "HB317": [
        "2006|0863|02/15/2006 01:33:33 PM|HB317|H|Passed with AM {0074h},  MA, VV|02/15/2006 01:33:33 PM",
        "2006|0863|02/15/2006 03:12:57 PM|HB317|H|ref to Ways & Means|02/15/2006 03:12:57 PM"],
    "HB1240": [
        "2006|2126|02/15/2006 04:43:17 PM|HB1240|H|Maj AM {0795h},  AA, RC (172-150)   HJ 19, pg 1151-1154|02/15/2006 04:43:17 PM",
        "2006|2126|02/15/2006 05:10:11 PM|HB1240|H|Passed with AM {0795h},  ML,  RC (141-181)   HJ 19, pg 1154-1156|02/15/2006 05:10:11 PM",
        "2006|2126|02/15/2006 05:15:37 PM|HB1240|H|Ref to Interim Study,  MA,  Div (170-152)   HJ 19, pg 1156|02/15/2006 05:15:37 PM"],
    "HB162": [
        "2006|0103|02/02/2006 02:25:53 PM|HB162|H|Lay on Table,   ML,  RC (140-198)     HJ 14, pg 747-749|02/02/2006 02:25:53 PM"],
    "SB42": [
        "2005|0821|02/17/2005 10:25:50 AM|SB42|S|Sen. Larsen Moved Laid on Table Division 8Y-15N, MF; SJ 6, Pg.64|02/17/2005 10:25:50 AM"],
    # The 2006 clerk's comma between the kind of vote and its count
    # (Docket_db_2005-2006.txt line 11521).
    "SB128": [
        "2006|1003|01/18/2006 03:59:31 PM|SB128|H|Lay on Table,  ML, RC, (144-195)  HJ 10, pg 532-534|01/18/2006 03:59:31 PM"],
    # The result after a semicolon of its own (Docket_db_1999-2000.txt line
    # 19526, Docket_db_2005-2006.txt line 20896).
    "SB301": [
        "2000|2722|03/09/2000 02:24:57 PM|SB301|S|Inexpedient to Legislate(not voted on), Sen. Fernald Moved Laid on Table; Division 8y-14n, MF,VV|03/09/2000 02:24:57 PM"],
    "SB1": [
        "2006|4001|09/26/2006 02:00:53 PM|SB1|H|Rep Vaillancourt moved lay on table; MF VV; 2006 Spec Sess HJ 1, p.18|09/26/2006 02:00:53 PM"],
    # A Senate question and a third reading that came out differently
    # (Docket_db_1999-2000.txt lines 7344 and 12279).
    "SB108": [
        "1999|0874|05/20/1999 04:11:59 PM|SB108|S|Sen. Gordon Moved Rerefer to Committee, RC 10Y-14N, MF, OT3rdg, MA, VV; SJ 20, P 528-534|05/20/1999 04:11:59 PM"],
    "SB219": [
        "2000|0954|02/03/2000 02:10:55 PM|SB219|S|Ought to Pass with Amendment {3073}[New Title], AA, VV,  Ordered to 3rd Reading, RC 12y -12n, MF|02/03/2000 02:10:55 PM"],
}


def _site_gen(path="workers/follow/site.gen.js"):
    """workers/follow/site.gen.js as it is committed: {export name: value},
    each `export const NAME = <JSON>;` line read as JSON. What the Worker is
    bundled with, whatever follow_site.py would write now."""
    text = Path(path).read_text(encoding="utf-8")
    return {n: json.loads(v) for n, v in re.findall(r"^export const (\w+) = (.*);$", text, re.M)}


# EVERY ROLL CALL A SITTING HOLDS, cut from the record (narratives.json's
# events and rollcalls.json's rows, as they stood on 2 October 2026). Until
# then a sitting page was made of the docket rows typed as floor motions and
# nothing else: 1,552 House and 1,431 Senate roll calls were on no page, and
# the opening's count was wrong on 697 of them (session_days._roll_calls).
def _sitting_fixture(SD, narr, rolls, sat=None, journals=None, held=None):
    """session_days.load() over a cut of the record: narr is {term: {bill:
    [event]}} and rolls {term: {bill key: [roll call]}}; `sat` says which
    days the journal opens a sitting on, none by default, and `journals` the
    votes each journal prints, {(body, date): {"rc": [...], "div": [...],
    "bills": [...], "under": {bill: [...]}}}, none by default ("under", the
    counts after each bill's heading, optional): a code check never reads the journals
    on disk, which the nightly's machine does not hold. `held` {term:
    [bill]} is the term's list of bills (data/bills.json), none by default."""
    d = Path(tempfile.mkdtemp(prefix="sitting_"))
    try:
        (d / "n.json").write_text(json.dumps(
            {t: {b: {"events": evs} for b, evs in bills.items()}
             for t, bills in narr.items()}), encoding="utf-8")
        if held is not None:
            (d / "data").mkdir()
            (d / "data" / "bills.json").write_text(json.dumps(
                {t: {b: {} for b in bills} for t, bills in held.items()}), encoding="utf-8")
        journals = journals or {}
        return SD.load(d / "n.json", rolls,
                       sat=sat or (lambda body, date: (body, date) in journals),
                       journals=journals)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _rc(year, body, number, date, bill, question, yeas, nays, passed, need=None,
        **more):
    return {"year": year, "body": body, "number": number, "date": date, "bill": bill,
            "question": question, "question_raw": question, "yeas": yeas,
            "nays": nays, "passed": passed, "threshold_needed": need, **more}


def _one_roll_call_each(days):
    """[(body, date, key, n)] -- a roll call on record drawn by more than one
    motion of one bill on a page, or on more than one page."""
    out, pages = [], {}
    for (body, date), d in days.items():
        per = {}
        for i in list(d.items) + list(d.others):
            if i.rc is not None:
                per.setdefault(SD_key(i.rc), []).append((i.term, i.bill, i.consent))
        for k, its in per.items():
            bills = [x[:2] for x in its if not x[2]]
            if len(bills) != len(set(bills)):
                out.append((body, date, k, len(bills)))
            if k in pages and pages[k] != (body, date):
                out.append((body, date, k, "also on " + pages[k][1]))
            pages.setdefault(k, (body, date))
    return out


def SD_key(r):
    return (str(r.get("year")), r.get("body"), int(r.get("number") or 0))


# A House Calendar, laid out the way pdftotext -layout returns one: the heading
# begins a line, the prose that follows does not. The minority's paragraph
# cites ANOTHER bill mid-sentence, which is what the real calendars do
# constantly -- "changes enacted in 2025 through HB 394, which established..."
# and "prevented many towns from adopting SB 2, concentrating budgetary and
# governance decisions...".
CALENDAR_PAGE = """REGULAR CALENDAR

HB 1418, setting a minimum affirmative vote for new or expanded spending.
MAJORITY: OUGHT TO PASS. MINORITY: INEXPEDIENT TO LEGISLATE.
Rep. Ross Berry for the Majority of Election Law. This legislation applies
only to towns and school districts that use the official ballot system. In
many towns turnout is extremely low, often around 15 percent. Vote 12-8.
Rep. Jim Maggiore for the Minority of Election Law. This limitation has
prevented many towns from adopting SB 2, concentrating budgetary decisions
among a relatively small number of attendees. It aligns with changes made
in 2025 through HB 394, which established that representatives serve in an
ex-officio capacity. For these reasons the minority opposes the motion.

HB 1419, relative to something else entirely.
OUGHT TO PASS.
Rep. Dan McGuire for Election Law. The committee heard testimony from the
sponsor and from two municipal clerks, and found the change to be a plain
correction of a cross-reference rather than a matter of policy. No member
spoke against it and the vote was unanimous. Vote 18-0.
"""

# The shape of House Calendar 12 of 2023, pages 57-58, and of 4 March 2022's
# last amendment: a heading on its own line with the number under it, one of
# them printed "2023- 0533h" by pdftotext, then the calendar's own business.
# And between them HB 174's heading as House Calendar 11 of 2013 prints it,
# "(2013-00079h)", a number no marker reads: only the heading can end the
# amendment above it there, as it ended 2013-0065h.
AMENDMENT_PAGE = """\
                                                        Amendment to HB 610-FN
                                                                   (2023-0471h)

             Proposed by the Committee on Health, Human Services and Elderly Affairs - c

Amend the bill by replacing section 2 with the following:
   2 Registry Identification Cards; Qualifications for Minors. Amend RSA 126-X:5, V(a) to read as follows:
           (a) A custodial parent or legal guardian responsible for health care decisions for the qualifying patient
submits a written certification from 2 providers, one of whom shall be a [pediatrician] provider who provides
pediatric care, as provided in the capital budget and in
Amendment to HB 25-A as passed.

                                                                    2023-0471h
                                                            AMENDED ANALYSIS
   This bill expands the definition of provider under the therapeutic cannabis program.

                                                        Amendment to HB 174
                                                                  (2013-00079h)

             Proposed by the Committee on Transportation - c

Amend the title of the bill by replacing it with the following:
AN ACT prohibiting the use of a mobile electronic device while driving.

                                                        Amendment to HB 614-FN
                                                                  (2023- 0533h)

             Proposed by the Committee on Health, Human Services and Elderly Affairs - r

Amend the bill by replacing all after the enacting clause with the following:
   1 Notice of Homestead Exemption. The party shall provide the following notice by certified mail:
NOTICE
   IF YOU OR YOUR SPOUSE OWNS AND RESIDES IN THIS PROPERTY, YOU MAY BE ENTITLED TO A HOMESTEAD EXEMPTION.
   2 Effective Date. This act shall take effect July 1, 2023.

                   SESSION DAY LOGISTICS MARCH 10, 2022

The House will meet on Thursday, March 10th at 9:00 a.m. in Representative's Hall.
PARKING
All legislators should park where they are assigned to park.
"""


# What the two harnesses below share, run in node beside page.js (app.js) and
# stub.js (dom_stub.js). The stub drops what the window and the document are
# asked to listen for, and its history writes nothing down; here both are
# kept, so a check can press a key, click, and go back, and read what the
# page then did to the address. A raw string: it carries a regular expression.
_HEARD_PRELUDE = r"""
require("./stub.js");
const fs = require("fs");
const heard = {window: {}, document: {}};
globalThis.addEventListener = (t, f) => (heard.window[t] = heard.window[t] || []).push(f);
document.addEventListener = (t, f) => (heard.document[t] = heard.document[t] || []).push(f);
globalThis.CSS = {escape: s => String(s).replace(/["\\|#.:\[\]]/g, "\\$&")};
// The address as the page writes it: what was pushed, replaced or gone back
// from, and location following each as a browser's does.
const wrote = [];
const go = u => { const m = /^([^?#]*)(\?[^#]*)?(#.*)?$/.exec(u);
  location.pathname = m[1]; location.search = m[2] || ""; location.hash = m[3] || ""; };
history.pushState = (st, t, u) => { wrote.push("push " + u); history.state = st; go(u); };
history.replaceState = (st, t, u) => { wrote.push("replace " + u); history.state = st; go(u); };
history.back = () => { wrote.push("back"); };
location.origin = "https://x";
let s;
function load(names) {
  try { s = (0, eval)(fs.readFileSync("./page.js", "utf8") + "; ({" + names + "})"); }
  catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
}
// Stand the page at an address, as if it had loaded there or written it.
// location.href is a mark: anything else in it afterwards is where the page
// sent the reader.
function place(path, state, standalone) {
  go(path); history.state = state; window.GR_STANDALONE = standalone;
  s.addressed(); wrote.length = 0; location.href = "HERE";
}
const pop = state => { history.state = state; heard.window.popstate.forEach(f => f({state})); };
// A click on something `hit` answers for: hit(selector) is what
// e.target.closest(selector) finds.
function click(hit, ev) {
  const e = Object.assign({button: 0, detail: 1, prevented: 0,
    preventDefault() { this.prevented++; },
    target: {closest: q => hit(q) || null, dataset: {}, id: ""}}, ev || {});
  heard.document.click.forEach(f => f(e));
  return e;
}
const seen = () => ({href: location.href, wrote: wrote.slice(), focused: s.getFocused()});
"""


# THE STATUS FILTER'S CATEGORIES, chip word by chip word (the person, 8
# October 2026): "one In Progress selection ... for bills that haven't
# concluded, separate to those that Passed, Died, were sent to Interim Study,
# or those that are Tabled", every bill that became law and every resolution
# that passed as Passed, and Withdrawn and Vetoed their own. Written out here,
# not read from app.js, so that the page filing a word anywhere else fails
# until this table moves with it.
_STATUS_CATEGORY = {
    "Became Law": "Passed", "Died": "Died", "Interim Study": "Interim Study",
    "Tabled": "Tabled", "Vetoed": "Vetoed", "Withdrawn": "Withdrawn",
    # Not concluded: the governor has yet to act, the voters have yet to vote.
    "Passed, awaiting the governor": "In Progress",
    "Passed both chambers, goes to the voters": "In Progress",
    "Passed both chambers, goes to the voters in November 2026": "In Progress",
    "Passed both chambers, goes to the voters in November 2028": "In Progress",
    # Nor have they, as far as the record says, from the day after the
    # election until a person types the count in, and the line says "went"
    # (the release review of 16 October 2026: CACR 13 from 4 November 2026,
    # and, if its term closes first, the line with no November in it). The
    # same category as the day before; _cacr_went_to_the_voters.
    "Passed both chambers, went to the voters": "In Progress",
    "Passed both chambers, went to the voters in November 2026": "In Progress",
    "Passed both chambers, went to the voters in November 2028": "In Progress",
    # Ended: never introduced, only proposed for the 2006 special session
    # (HB 3, whose record says nothing after it), turned down at the ballot.
    "Proposed for the special session": "Died", "Not introduced": "Died",
    "Passed both chambers, not ratified by the voters": "Died",
    "Passed both chambers, ratified by the voters": "Passed",
    "Adopted by the House": "Passed", "Adopted by the Senate": "Passed",
    "Adopted by both chambers": "Passed",
    **{s: "In Progress" for s in _CHIP_STAGES},
}
# EVERY (chip, kind) THE NINETEEN TERMS CARRIED, read off site/idx on 8
# October 2026: 33,717 bills, and the 302 requests of 2027, which have no
# chip and no category. The data check below reads the built site's rows
# themselves whenever there is one; this is what a run of the code checks,
# which has none, still holds.
_STATUS_REAL_PAIRS = {
    ("Died", "done"): 18100, ("Became Law", "law"): 12107,
    ("Interim Study", "study"): 2392, ("Adopted by the House", "adopted"): 448,
    ("Died", "veto"): 309, ("Adopted by both chambers", "adopted"): 169,
    ("Adopted by the Senate", "adopted"): 144, ("Withdrawn", "done"): 22,
    ("Passed both chambers, not ratified by the voters", "adopted"): 12,
    ("Not introduced", "done"): 7, ("Passed both chambers, ratified by the voters", "adopted"): 5,
    ("Proposed for the special session", "done"): 1,
    ("Passed both chambers, goes to the voters in November 2026", "adopted"): 1,
}
_STATUS_CATS = ["In Progress", "Passed", "Tabled", "Interim Study", "Died", "Withdrawn",
                "Vetoed"]

# Runs beside page.js (app.js) and stub.js: each {chip, kind} through
# statusCat, with whether its chip's word or its kind decided it, and each
# word through catOfWord, as ?status= in an address is read.
_STATUSCAT_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({statusCat, catOfChip, catOfWord, CAT_OF_KIND, STATUSCATS})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const pairs = JSON.parse(fs.readFileSync("./pairs.json", "utf8"));
const words = JSON.parse(fs.readFileSync("./words.json", "utf8"));
const out = {cats: s.STATUSCATS, pairs: [], words: []};
try {
  for (const [chip, kind] of pairs)
    out.pairs.push([chip, kind, s.statusCat({chip, kind}), !!s.catOfChip(chip),
                    !!s.CAT_OF_KIND[kind]]);
  // A list, not an object: "__proto__" is one of the words.
  for (const w of words) out.words.push([w, s.catOfWord(w, [])]);
  out.request = s.statusCat({id: "LSR20270001", status: "Filed as a request", kind: ""});
} catch (e) { out.threw = e.constructor.name + ": " + e.message; }
process.stdout.write("\n@@" + JSON.stringify(out));
"""


def _json3_cues(cues):
    """YouTube's json3 as yt-dlp writes it: a window spanning the track, then
    one event per cue, indented a field to a line."""
    ev = [{"tStartMs": 0, "dDurationMs": cues[-1][0] + 4000, "id": 1,
           "wpWinPosId": 1, "wsWinStyleId": 1}]
    ev += [{"tStartMs": t, "dDurationMs": 4000, "wWinId": 1,
            "segs": [{"utf8": s}]} for t, s in cues]
    return json.dumps({"wireMagic": "pb3", "events": ev}, indent=2)


def _cloud_call(CL, *argv):
    import contextlib
    import io
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = CL.main(list(argv))
    return code, out.getvalue() + err.getvalue()


# ---- the night's list of calendars and journals --------------------------------
#
# Added on 1 October 2026: the checks of fetch_calendar_archive.py --listing
# and nightly.take_documents, which keep the list the Calendar page's picker
# is built from current.
#
# THE PAGES. tests/calendar_index/ holds the form cut out of two pages the
# General Court served on 6 September 2026: the Senate's index as it opens
# (its calendars for 2026) and after its year was changed to 2025. A third
# page was saved that day, probe_calendars_type.html, the answer to a change
# of kind: it shows the same Senate calendars of 2026 as the first, so it is
# no evidence of a journal list and is not kept here. The House's page, and
# both chambers' journal lists, were never saved, so here they are the same
# markup with the House's own values put in (_docs_page): the kind names
# "Calendar" and "Journal", the lower-case folder, and file names the queue
# recorded from that page on 13 September. The select names are the ones both
# chambers' lists were read through for thirty years of documents; the
# House's link form is the one probe_calendars.py printed off its page. House
# Calendars 33 to 35 and their labels are the fixture's own -- No 35 of
# 25 September is the person's example of what the list was missing.

_DOCS_FIX = Path("tests") / "calendar_index"
_DOCS_REAL = ("senate_calendars_2026.html", "senate_calendars_2025.html")
_DOCS_H = [("Calendar", "Calendars"), ("Journal", "Journals")]
_DOCS_S = [("SenateCalendar", "Calendars"), ("SenateJournal", "Journals")]
_DOCS_HC = [("HC 35.pdf", "No 35 September 25 2026"), ("HC 34.pdf", "No 34 September 18 2026"),
            ("HC 33.pdf", "No 33 September 11 2026"), ("HC 32.pdf", "No 32 September 4 2026"),
            ("HC 31.pdf", "No 31 August 28 2026"),
            ("No30 August 14 2026.pdf", "No30 August 14 2026"),
            ("No29 August 07 2026.pdf", "No29 August 07 2026")]
_DOCS_HJ = [("HJ 16 August 19, 2026.pdf", "HJ 16 August 19, 2026"),
            ("HJ 15 June 4, 2026.pdf", "HJ 15 June 4, 2026")]
_DOCS_SJ = [("SJ 15.pdf", "SJ 15"), ("SJ 14 June 4, 2026.pdf", "SJ 14 June 4, 2026")]
_DOCS_HC25 = [("No 51 December 19 2025.pdf", "No 51 December 19 2025")]
_DOCS_HJ25 = [("HJ 19 December 17, 2025.pdf", "HJ 19 December 17, 2025")]
_DOCS_SJ25 = [("SJ 18 October 23, 2025.pdf", "SJ 18 October 23, 2025")]


def _docs_page(CA, form, kinds, kind, years, year, docs, link):
    """A saved index form showing another list: its three selects' options
    and the file its "View PDF File" link names are replaced, and nothing
    else. Values are written as a page writes them, so an entity stays one."""
    def options(rows, chosen):
        return "".join('\n\t<option {}value="{}">{}</option>'.format(
            'selected="selected" ' if v == chosen else "", v, lab) for v, lab in rows) + "\n"

    def put(page, name, body):
        m = next(m for m in CA.SELECT_RE.finditer(page) if m.group("name") == name)
        return page[:m.start("body")] + body + page[m.end("body"):]
    page = put(form, CA.SEL_KIND, options(kinds, kind))
    page = put(page, CA.SEL_YEAR, options([(y, y) for y in years], year))
    page = put(page, CA.SEL_DOC, options(docs, docs[0][0] if docs else None))
    m = CA.LINK_RE.search(page)
    return page[:m.start(1)] + link + page[m.end(1):]


def _docs_fixture(CA):
    """(pages, rows): what each index shows tonight, keyed "H calendar 2026",
    and the queue on file, in the eleven columns it had before the label.

    The Senate's two calendar pages are the saved ones, untouched. On file
    are all of the Senate's calendars but the newest, SC 29 -- so the page as
    it was really served lists one document the queue does not have -- and
    the House's calendars up to No 32, one of them still wanted.
    """
    import urllib.parse
    missing = [n for n in _DOCS_REAL if not (_DOCS_FIX / n).exists()]
    assert not missing, (f"{_DOCS_FIX.as_posix()}/ is missing {', '.join(missing)}: the saved "
                         "index pages these checks read")
    s26, s25 = ((_DOCS_FIX / n).read_text(encoding="utf-8") for n in _DOCS_REAL)
    years = CA.shown(s26)["years"]
    pages = {"S calendar 2026": s26, "S calendar 2025": s25}
    for key, kinds, kind, docs, folder in (
            ("H calendar 2026", _DOCS_H, "Calendar", _DOCS_HC, "calendars"),
            ("H journal 2026", _DOCS_H, "Journal", _DOCS_HJ, "journals"),
            ("S journal 2026", _DOCS_S, "SenateJournal", _DOCS_SJ, "Journals"),
            ("H calendar 2025", _DOCS_H, "Calendar", _DOCS_HC25, "calendars"),
            ("H journal 2025", _DOCS_H, "Journal", _DOCS_HJ25, "journals"),
            ("S journal 2025", _DOCS_S, "SenateJournal", _DOCS_SJ25, "Journals")):
        year = key[-4:]
        pages[key] = _docs_page(CA, s26, kinds, kind, years, year, docs,
                                f"{folder}\\{year}\\{docs[0][0]}")

    def row(ch, kind, year, name, state="held"):
        index, _, folder, outdir, _ = CA.SOURCES[(ch, kind)]
        return {"chamber": ch, "kind": kind, "year": year, "name": name,
                "url": index + CA.VIEWER + urllib.parse.quote(f"{folder}\\{year}\\{name}", safe=""),
                "path": f"{outdir}\\{year}\\{name}", "state": state, "attempts": "0",
                "error": "", "bytes": "100" if state == "held" else "", "fetched": ""}
    rows = [row("H", "calendar", "2026", n) for n, _ in _DOCS_HC[3:6]]
    rows.append(row("H", "calendar", "2026", _DOCS_HC[6][0], "wanted"))
    rows += [row("H", "calendar", "2025", n) for n, _ in _DOCS_HC25]
    rows += [row("H", "journal", "2026", n) for n, _ in _DOCS_HJ]
    rows += [row("H", "journal", "2025", n) for n, _ in _DOCS_HJ25]
    rows += [row("S", "calendar", "2026", n) for n, _ in CA.shown(s26)["docs"][1:]]
    rows += [row("S", "calendar", "2025", n) for n, _ in CA.shown(s25)["docs"]]
    rows += [row("S", "journal", "2026", n) for n, _ in _DOCS_SJ]
    rows += [row("S", "journal", "2025", n) for n, _ in _DOCS_SJ25]
    return pages, rows


def _docs_turn(CA, pages):
    """The fixture's pages as they would be once 2027's lists have opened:
    the same lists, with 2027 at the head of each page's years, and each
    chamber's calendars for 2027 with one document in them. No journal list
    for 2027 is here: the page answers HTTP 500 for a year with no journals,
    and the checks serve it that."""
    years = ["2027"] + CA.shown(pages["S calendar 2026"])["years"]
    turn = {}
    for key, page in pages.items():
        st = CA.shown(page)
        turn[key] = _docs_page(CA, pages["S calendar 2026"],
                               _DOCS_H if key[0] == "H" else _DOCS_S, st["kind"], years,
                               key[-4:], st["docs"], st["link"])
    for ch, kinds, kind, folder, doc in (
            ("H", _DOCS_H, "Calendar", "calendars", ("HC 1.pdf", "No 1 December 4 2026")),
            ("S", _DOCS_S, "SenateCalendar", "Calendars", ("SC 1.pdf", "No 1 December 3 2026"))):
        turn[f"{ch} calendar 2027"] = _docs_page(
            CA, pages["S calendar 2026"], kinds, kind, years, "2027", [doc],
            f"{folder}\\2027\\{doc[0]}")
    assert all(CA.shown(turn[k])["docs"] == CA.shown(pages[k])["docs"] for k in pages), \
        "the fixture's pages for the turn of the year do not list what the saved ones do"
    return turn


def _docs_write_old(path, rows):
    """A queue file as the laptop's discovery left it: no label column."""
    cols = ["chamber", "kind", "year", "name", "url", "path", "state", "attempts", "error",
            "bytes", "fetched"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})


_DOCS_HC35 = ("https://gc.nh.gov/house/calendars_journals/viewer.aspx"
              "?fileName=calendars%5C2026%5CHC%2035.pdf")
# The address the laptop's discovery recorded for this document on 13
# September, from the same page: the listing must write the same one.
_DOCS_SC29 = ("https://gc.nh.gov/senate/calendars_journals/viewer.aspx"
              "?fileName=Calendars%5C2026%5CSC%2029.pdf")


def _hearing_fixture(S):
    """The six real Senate hearing reports in tests/, parsed and finished."""
    fx = json.loads(_source("tests/senate_hearing_reports.json"))
    out = {}
    for b in ("SB4", "SB11", "SB160", "SB14", "HB666", "HB277"):
        docs = S.parse_report(fx[b]["HTMLText"])
        assert len(docs) == 1, f"{b}: {len(docs)} reports read out of one"
        rec, doubts = docs[0]
        out[b] = (S.finish(rec, doubts, b, "2025-01-10"),
                  S.blocks(fx[b]["HTMLText"]))
    return out


# Every committee name in data/committees.json when this was written, as a
# literal so the check below needs nothing on disk.
_FULL_COMMITTEE_NAMES = (
    "Capital Budget", "Children and Family Law", "Commerce",
    "Commerce and Consumer Affairs", "Committee of Conference",
    "Criminal Justice and Public Safety",
    "Criminal Justice and Public Safety Joint with Judiciary", "Education",
    "Education Finance", "Education Funding",
    "Education Policy and Administration",
    "Education and Workforce Development", "Election Law",
    "Election Law and Internal Affairs", "Election Law and Municipal Affairs",
    "Energy and Natural Resources", "Environment and Agriculture",
    "Executive Departments and Administration", "Finance",
    "Fish and Game and Marine Resources", "Health and Human Services",
    "Health, Human Services and Elderly Affairs", "Housing", "Judiciary",
    "Labor, Industrial and Rehabilitative Services",
    "Legislative Administration", "Municipal and County Government",
    "No Committee Assignment", "Public Works and Highways",
    "Public and Municipal Affairs", "Resources, Recreation and Development",
    "Rules", "Rules and Enrolled Bills",
    "Rules, Enrolled Bills and Internal Affairs",
    "Science, Technology and Energy",
    "Senate Special Committee on Redistricting", "Special Committee",
    "Special Committee on COVID Response Efficacy",
    "Special Committee on Childcare", "Special Committee on Commissions",
    "Special Committee on Housing",
    "Special Committee on Public Employee Pension Plans",
    "Special Committee on Redistricting",
    "Special Committee on the Division for Children, Youth and Families (DCYF)",
    "Special Committee on the Family Division of the Circuit Court",
    "State-Federal Relations and Veterans Affairs", "Transportation",
    "Ways and Means",
)


# THE DOT GOES WITH THE PART AFTER IT (the owner's fix S9, and the manager's
# review of the Videos view, 26 October 2026, 4): every middle dot in a Videos
# view is drawn at the head of the part after it, held to it by a no-break
# space (app.js, vwJoin), so no line ends on one. The caption had ended
# "Senate Finance · May 5, 2026 · 1:28 PM ·" at 390px, and House Commerce's
# "· 5 h 49 min ·" over "On YouTube" at 1280.
_VW_DOT_HEAD = '<span class="vwi"><span aria-hidden="true">&middot;&nbsp;</span>'


def _vw_loose_dots(html):
    """How many of a Videos view's middle dots a line could end on."""
    return html.count("&middot;") + html.count("\u00b7") - html.count(_VW_DOT_HEAD)


# THE CALENDAR PAGE'S FIXTURE, for the four checks below: three weeks of March
# 2026 and one that runs into April, so there are two month files and a week
# that straddles them. Built for Wednesday 11 March, which is the reader's
# today in the checks that run the page. The week of 9 March holds a committee
# doing two things on one day, a Senate committee, the floor, a committee of
# conference, an executive session, a statutory committee, and a cancelled
# meeting on a Saturday; Monday the 9th is empty.
CAL_TODAY = (2026, 3, 11)


def _cal_rows():
    def r(d, bill, body, kind, time, cmte, venue=""):
        return {"term": "2025-2026", "bill": bill, "body": body, "kind": kind,
                "date": d, "time": time, "committee": cmte, "venue": venue}
    return [
        r("2026-03-03", "HB10", "H", "public hearing", "10:00", "Commerce", "LOB 302"),
        r("2026-03-10", "HB1", "H", "public hearing", "10:00", "Judiciary", "LOB 206"),
        r("2026-03-10", "HB2", "H", "executive session", "13:00", "Judiciary", "LOB 206"),
        r("2026-03-10", "SB5", "S", "public hearing", "09:00", "Finance", "SH 103"),
        r("2026-03-11", "HB9", "H", "floor debate", "", ""),
        r("2026-03-11", "HB3", "H", "committee of conference", "", ""),
        r("2026-03-12", "HB4", "H", "executive session", "09:30", "Commerce", "LOB 302"),
        {"study": True, "bill": "", "kind": "statutory committee", "date": "2026-03-13",
         "time": "10:00", "committee": "Commission on Aging", "venue": "GP 230",
         "note": "Regular meeting."},
        {"study": True, "bill": "", "kind": "cancelled", "date": "2026-03-14",
         "time": "10:00", "committee": "Commission on Aging", "venue": "", "note": ""},
        r("2026-03-18", "SB6", "S", "executive session", "14:00", "Finance", "SH 103"),
        r("2026-03-18", "HB7", "H", "subcommittee work session", "09:00", "Judiciary", "LOB 206"),
        r("2026-04-01", "HB20", "H", "public hearing", "10:00", "Education", "LOB 207"),
    ]


def _cal_fixture(root):
    """Build the fixture's week pages and month files under root/site."""
    import contextlib
    import datetime as _dt
    import io
    import build_calendar as BC
    today = _dt.date(*CAL_TODAY)
    weeks = BC.weeks_from(_cal_rows(), names={})
    BC.every_week(weeks, today)
    order = sorted(weeks)
    site = root / "site"
    site.mkdir(parents=True)
    shutil.copy(Path("src/pages/bills.html"), site / "bills.html")
    (site / "components.js").write_text(_components_js(), encoding="utf-8", newline="\n")
    urls = []
    with contextlib.redirect_stdout(io.StringIO()):
        for i, k in enumerate(order):
            BC.week_page(site, "https://graniterecord.org", k, weeks, order, i,
                         {}, {}, {}, urls, today, set(), study=True)
        months = BC.month_files(site, weeks, order, {}, {}, {}, today)
    return site, weeks, order, urls, months


def _cal_node():
    return shutil.which("node") or shutil.which("node.exe")


def _fixture_drawn():
    """The fixture's pages as their scripts draw them (drawn_pages.draw), once a
    run: {page or page#tab: what it drew}."""
    def make():
        import contextlib
        import io
        import drawn_pages as DP
        shared, _base, _ran, days = _fixture_site_shared()
        root = _shared_root("gr-drawn-icons-")
        with contextlib.redirect_stdout(io.StringIO()):
            return DP.draw(shared / "site", root / "drawn", days[0])
    return _once_a_run("the fixture's pages, drawn", make)


# A DOM small enough to read and real enough to run the Calendar page's
# script: _calendar_in_a_dom's. It parses the markup this site writes,
# answers the selectors the script uses, captures and bubbles events,
# moves focus, keeps history and lets the check move the clock by hand.
_CAL_DOM = r"""// A DOM small enough to read and real enough to run the Calendar page's script:
// an HTML parser for the markup this site writes, the selectors the script
// uses, events that capture and bubble, focus, history and a clock the test
// moves by hand.
const VOID = new Set(["area","base","br","col","embed","hr","img","input","link","meta","source","track","wbr"]);
const ENT = {amp:"&",lt:"<",gt:">",quot:'"',apos:"'",nbsp:" ",lsaquo:"‹",rsaquo:"›",
             hellip:"…",times:"×",rarr:"→",ndash:"–",mdash:"—",
             ldquo:"“",rdquo:"”",lsquo:"‘",rsquo:"’"};
function dec(s){ return String(s).replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi,(m,e)=>{
  if(e[0]==="#") return String.fromCodePoint(e[1]==="x"||e[1]==="X"?parseInt(e.slice(2),16):+e.slice(1));
  return ENT[e]!==undefined?ENT[e]:m; }); }
function escT(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
function escA(s){ return String(s).replace(/&/g,"&amp;").replace(/"/g,"&quot;"); }

class Ev { constructor(type,o){ Object.assign(this,{type,bubbles:true,defaultPrevented:false},o||{}); }
  preventDefault(){ this.defaultPrevented=true; } stopPropagation(){ this._stop=true; } }

class N {
  constructor(doc){ this.ownerDocument=doc; this.parentNode=null; this.childNodes=[]; this._on={}; }
  get children(){ return this.childNodes.filter(n=>n.nodeType===1); }
  appendChild(n){ if(n.parentNode) n.remove(); n.parentNode=this; this.childNodes.push(n); return n; }
  remove(){ const p=this.parentNode; if(p){ p.childNodes.splice(p.childNodes.indexOf(this),1); this.parentNode=null; } }
  contains(n){ for(;n;n=n.parentNode) if(n===this) return true; return false; }
  get textContent(){ return this.nodeType===3?this.data:this.childNodes.map(c=>c.textContent).join(""); }
  set textContent(v){ if(this.nodeType===3){ this.data=String(v); return; }
    this.childNodes.forEach(c=>c.parentNode=null); this.childNodes=[];
    if(String(v)!=="") this.appendChild(new T(this.ownerDocument,String(v))); }
  addEventListener(t,f,o){ (this._on[t]=this._on[t]||[]).push({f,cap:o===true||!!(o&&o.capture)}); }
  removeEventListener(t,f){ this._on[t]=(this._on[t]||[]).filter(x=>x.f!==f); }
  dispatchEvent(ev){
    ev.target=ev.target||this; const path=[]; for(let n=this;n;n=n.parentNode) path.push(n);
    if(this.ownerDocument&&path[path.length-1]===this.ownerDocument) path.push(this.ownerDocument.defaultView);
    for(let i=path.length-1;i>=0&&!ev._stop;i--) (path[i]._on&&path[i]._on[ev.type]||[]).filter(x=>x.cap||i===0).forEach(x=>{ ev.currentTarget=path[i]; x.f.call(path[i],ev); });
    if(ev.bubbles) for(let i=1;i<path.length&&!ev._stop;i++) (path[i]._on&&path[i]._on[ev.type]||[]).filter(x=>!x.cap).forEach(x=>{ ev.currentTarget=path[i]; x.f.call(path[i],ev); });
    return !ev.defaultPrevented;
  }
}
class T extends N { constructor(doc,data){ super(doc); this.nodeType=3; this.data=data; } }
class C extends N { constructor(doc,data){ super(doc); this.nodeType=8; this.data=data; } get textContent(){ return ""; } }
class E extends N {
  constructor(doc,tag){ super(doc); this.nodeType=1; this.tagName=tag.toUpperCase(); this.localName=tag.toLowerCase();
    this.attrs=new Map(); this.style={}; this._checked=null; this._value=null; this._open=null; }
  getAttribute(k){ return this.attrs.has(k)?this.attrs.get(k):null; }
  setAttribute(k,v){ this.attrs.set(k,String(v)); }
  hasAttribute(k){ return this.attrs.has(k); }
  removeAttribute(k){ this.attrs.delete(k); }
  get id(){ return this.getAttribute("id")||""; }
  get className(){ return this.getAttribute("class")||""; } set className(v){ this.setAttribute("class",v); }
  get classList(){ const e=this; const get=()=>e.className.split(/\s+/).filter(Boolean);
    const put=(l)=>e.setAttribute("class",l.join(" "));
    return {contains:c=>get().includes(c), add:(...c)=>put([...new Set([...get(),...c])]),
      remove:(...c)=>put(get().filter(x=>!c.includes(x))),
      toggle:(c,f)=>{ const on=f===undefined?!get().includes(c):!!f; on?put([...new Set([...get(),c])]):put(get().filter(x=>x!==c)); return on; }}; }
  _bool(k){ return this.hasAttribute(k); } _setBool(k,v){ v?this.setAttribute(k,""):this.removeAttribute(k); }
  get hidden(){ return this._bool("hidden"); } set hidden(v){ this._setBool("hidden",v); }
  get disabled(){ return this._bool("disabled"); } set disabled(v){ this._setBool("disabled",v); }
  get open(){ return this._bool("open"); }
  set open(v){ const was=this.open; this._setBool("open",v);
    if(was!==!!v){ const d=this.ownerDocument; d._later(()=>this.dispatchEvent(new Ev("toggle",{bubbles:false}))); } }
  get checked(){ return this._checked===null?this._bool("checked"):this._checked; } set checked(v){ this._checked=!!v; }
  get value(){ return this._value===null?(this.getAttribute("value")||""):this._value; } set value(v){ this._value=String(v); }
  get tabIndex(){ const t=this.getAttribute("tabindex"); return t===null?(/^(A|BUTTON|INPUT|SUMMARY)$/.test(this.tagName)?0:-1):+t; }
  set tabIndex(v){ this.setAttribute("tabindex",v); }
  get name(){ return this.getAttribute("name")||""; }
  get offsetWidth(){ return 280; } get offsetHeight(){ return 120; }
  // Where an element is, if the world was given a layout: its page offset
  // less the page's scroll. Without one every element is at 100px, as the
  // checks written before scrolling mattered expect.
  getBoundingClientRect(){ const d=this.ownerDocument, y=d._y?d._y(this):undefined;
    if(y===undefined) return {top:100,left:40,right:80,bottom:140,width:40,height:40};
    const top=y-d._sy; return {top,left:40,right:80,bottom:top+40,width:40,height:40}; }
  scrollIntoView(o){ const d=this.ownerDocument; d._scrolled.push(this);
    const y=d._y?d._y(this):undefined; if(y===undefined) return;
    const top=y-d._sy, H=d.defaultView.innerHeight;
    if(o&&o.block==="nearest"){ if(top<0) d._sy=y; else if(top+40>H) d._sy=y+40-H; }
    else d._sy=y; }
  focus(){ const d=this.ownerDocument, was=d.activeElement; if(was===this) return;
    d.activeElement=this;
    if(was&&was!==d.body) was.dispatchEvent(new Ev("focusout",{relatedTarget:this}));
    this.dispatchEvent(new Ev("focusin",{relatedTarget:was})); }
  blur(){ const d=this.ownerDocument; if(d.activeElement===this){ d.activeElement=d.body; this.dispatchEvent(new Ev("focusout",{relatedTarget:null})); } }
  click(){ this.dispatchEvent(new Ev("click",{button:0})); }
  get outerHTML(){ let s="<"+this.localName; for(const [k,v] of this.attrs) s+=" "+k+'="'+escA(v)+'"';
    s+=">"; if(VOID.has(this.localName)) return s; return s+this.innerHTML+"</"+this.localName+">"; }
  get innerHTML(){ return this.childNodes.map(c=>c.nodeType===3?(/^(SCRIPT|STYLE)$/.test(this.tagName)?c.data:escT(c.data)):c.nodeType===8?"<!--"+c.data+"-->":c.outerHTML).join(""); }
  set innerHTML(v){ this.childNodes.forEach(c=>c.parentNode=null); this.childNodes=[];
    const d=this.ownerDocument; if(d.activeElement&&!d.documentElement.contains(d.activeElement)) d.activeElement=d.body;
    parseInto(this,String(v),d);
    if(d.activeElement&&!d.documentElement.contains(d.activeElement)) d.activeElement=d.body; }
  matches(sel){ return sel.split(",").some(s=>matchComplex(this,s.trim())); }
  closest(sel){ for(let n=this;n&&n.nodeType===1;n=n.parentNode) if(n.matches(sel)) return n; return null; }
  querySelectorAll(sel){ const out=[]; const walk=(n)=>{ for(const c of n.childNodes) if(c.nodeType===1){ if(c.matches(sel)) out.push(c); walk(c); } }; walk(this); return out; }
  querySelector(sel){ return this.querySelectorAll(sel)[0]||null; }
}
function parseInto(root,html,doc){
  const stack=[root]; const re=/<!--([\s\S]*?)-->|<!DOCTYPE[^>]*>|<\/([a-zA-Z0-9]+)\s*>|<([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^\s=\/>]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*(\/?)>|([^<]+|<)/g;
  let m;
  while((m=re.exec(html))){
    const top=stack[stack.length-1];
    if(m[1]!==undefined) top.appendChild(new C(doc,m[1]));
    else if(m[2]){ const t=m[2].toLowerCase(); for(let i=stack.length-1;i>0;i--){ if(stack[i].localName===t){ stack.length=i; break; } } }
    else if(m[3]){ const el=new E(doc,m[3]); const ar=/([^\s=\/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g; let a;
      while((a=ar.exec(m[4]||""))) el.attrs.set(a[1].toLowerCase(),dec(a[2]!==undefined?a[2]:a[3]!==undefined?a[3]:a[4]!==undefined?a[4]:""));
      top.appendChild(el);
      if(/^(script|style)$/.test(el.localName)){ const end=html.indexOf("</"+el.localName,re.lastIndex); el.appendChild(new T(doc,html.slice(re.lastIndex,end<0?html.length:end))); re.lastIndex=end<0?html.length:html.indexOf(">",end)+1; }
      else if(!VOID.has(el.localName)&&!m[5]) stack.push(el); }
    else if(m[6]!==undefined) top.appendChild(new T(doc,dec(m[6])));
  }
}
// Compound selectors joined by descendant spaces: tag, #id, .class, [a], [a="v"].
function parseCompound(s){ const r={tag:null,id:null,cls:[],attr:[]}; const re=/^([a-zA-Z*][a-zA-Z0-9-]*)|#([\w-]+)|\.([\w-]+)|\[([\w-]+)(?:="([^"]*)")?\]/g; let m, used=0;
  while((m=re.exec(s))&&m[0]){ used+=m[0].length; if(m[1]) r.tag=m[1].toUpperCase(); else if(m[2]) r.id=m[2]; else if(m[3]) r.cls.push(m[3]); else r.attr.push([m[4],m[5]]); re.lastIndex=used; }
  if(used!==s.length) throw new Error("minidom: selector not understood: "+s); return r; }
function matchOne(el,c){ if(c.tag&&c.tag!=="*"&&el.tagName!==c.tag) return false; if(c.id&&el.id!==c.id) return false;
  const cl=el.className.split(/\s+/); if(c.cls.some(x=>!cl.includes(x))) return false;
  return c.attr.every(([k,v])=>el.hasAttribute(k)&&(v===undefined||el.getAttribute(k)===v)); }
function matchComplex(el,sel){ const parts=sel.split(/\s+/).map(parseCompound); if(!matchOne(el,parts[parts.length-1])) return false;
  let n=el.parentNode; for(let i=parts.length-2;i>=0;i--){ while(n&&n.nodeType===1&&!matchOne(n,parts[i])) n=n.parentNode; if(!n||n.nodeType!==1) return false; n=n.parentNode; } return true; }

function makeWorld(o){
  const doc=new N(null); doc.nodeType=9; doc.ownerDocument=doc;
  const html=new E(doc,"html"), body=new E(doc,"body"); doc.appendChild(html); html.appendChild(body);
  doc.documentElement=html; doc.body=body; doc.activeElement=body; doc.title=""; doc._scrolled=[];
  doc._y=o.layout||null; doc._sy=0;
  let now=o.now||0; const timers=[]; let seq=0; const later=[];
  doc._later=(f)=>later.push(f);
  doc.getElementById=(id)=>html.querySelector("#"+id);
  doc.querySelector=(s)=>html.querySelector(s); doc.querySelectorAll=(s)=>html.querySelectorAll(s);
  doc.createElement=(t)=>new E(doc,t); doc.createTextNode=(d)=>new T(doc,String(d));
  const win={document:doc, innerHeight:800, _on:{}, addEventListener:N.prototype.addEventListener,
    removeEventListener:N.prototype.removeEventListener,
    matchMedia:(q)=>({matches:!!(o.narrow&&/max-width/.test(q)), addEventListener(){}})};
  doc.defaultView=win;
  doc.documentElement.clientWidth=o.width||1440;
  // The address in three parts, as a browser's location has them: the path,
  // the query ("?week=2026-W12", or "") and the hash. A reload is a new world
  // opened at the same address and handed the same store.
  const loc={pathname:o.path||"/calendar", search:o.search||"", hash:o.hash||"", origin:"https://x"};
  const at=()=>({p:loc.pathname,s:loc.search,h:loc.hash});
  const go=(url)=>{ const u=new URL(url,"https://x"+loc.pathname+loc.search); loc.pathname=u.pathname; loc.search=u.search; loc.hash=u.hash; };
  const hist=[at()];
  const history={length:1,
    pushState(_s,_t,url){ go(url); hist.push(at()); this.length=hist.length; },
    replaceState(_s,_t,url){ go(url); hist[hist.length-1]=at(); },
    back(){ if(hist.length<2) return; hist.pop(); this.length=hist.length; const t=hist[hist.length-1];
      loc.pathname=t.p; loc.search=t.s; loc.hash=t.h;
      N.prototype.dispatchEvent.call(win,new Ev("popstate",{bubbles:false})); }};
  const store=o.store||new Map();
  const RealDate=Date;
  class FixedDate extends RealDate { constructor(...a){ if(a.length) super(...a); else super(o.today[0],o.today[1]-1,o.today[2],12,0,0); }
    static now(){ return now; } }
  const G={window:win, document:doc, location:loc, history, localStorage:{getItem:k=>store.has(k)?store.get(k):null, setItem:(k,v)=>store.set(k,String(v)), removeItem:k=>store.delete(k)},
    setTimeout:(f,ms)=>{ const id=++seq; timers.push({id,at:now+(ms||0),f}); return id; },
    clearTimeout:(id)=>{ const i=timers.findIndex(t=>t.id===id); if(i>=0) timers.splice(i,1); },
    fetch:async(url)=>{ const body=o.files(url); return {ok:body!==null,status:body===null?404:200,json:async()=>JSON.parse(body)}; },
    Date:FixedDate, URLSearchParams, URL, Blob:class{}, innerHeight:800};
  Object.assign(win,G);
  return {win, doc, G, store, hist,
    advance(ms){ const end=now+ms; for(;;){ timers.sort((a,b)=>a.at-b.at||a.id-b.id); const t=timers[0]; if(!t||t.at>end) break; timers.shift(); now=t.at; t.f(); } now=end; },
    async settle(){ for(let i=0;i<20;i++){ await new Promise(r=>setImmediate(r)); while(later.length) later.shift()(); } },
    ev:(type,o2)=>new Ev(type,o2)};
}
// THE SCRIPTS A PAGE RUNS BEFORE THIS ONE, as a browser runs them: each one the
// page names by its own address ahead of `at` -- components.js, in the head --
// and then `code`, all in one context, so what the first declares the second
// can use. A file the site does not hold stops the run, as a missing script
// would leave the page broken.
function runPage(W,text,site,at,code){
  const vm=require("vm"), fs=require("fs"), path=require("path");
  const ctx=vm.createContext(Object.assign({console},W.G));
  for(const m of text.slice(0,at).matchAll(/<script src="\/?([\w.-]+\.js)"><\/script>/g))
    vm.runInContext(fs.readFileSync(path.join(site,m[1]),"utf8"),ctx,{filename:m[1]});
  vm.runInContext(code,ctx);
  return ctx;
}
module.exports={makeWorld, parseInto, E, Ev, runPage};
"""


def _braced(text, head):
    """The body of the first `head{...}` block in text, braces balanced."""
    i = text.index(head) + len(head)
    depth, j = 1, i
    while depth:
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
    return text[i:j - 1]


def _rsa_sections(path, want):
    """{section: (its heading, its text)} of the sections `want` names, read
    from the database copy of the RSA (db/NH_RSA.psv), or None where it is not
    on this disk. The text is the section's own, its tags taken out."""
    import html as _h
    p = Path(path)
    if not p.is_file():
        return None
    out = {}
    with p.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split("|")
            if len(f) < 9:
                continue
            m = re.search(r"Section (\S+) ", f[6])
            if m and m.group(1) in want and m.group(1) not in out:
                text = _h.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", f[8])))
                out[m.group(1)] = (f[6], text)
    return out


def _css_parts(sel):
    """A complex selector as [(combinator, compound)], left to right; the
    first combinator is "". Brackets and parentheses are kept whole."""
    out, cur, comb, depth, i = [], "", "", 0, 0
    while i < len(sel):
        c = sel[i]
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        if depth == 0 and c in " >+~":
            j = i
            while j < len(sel) and sel[j] in " >+~":
                j += 1
            if cur:
                out.append((comb, cur))
                cur = ""
            k = sel[i:j].strip()
            comb = k or " "
            i = j
            continue
        cur += c
        i += 1
    if cur:
        out.append((comb, cur))
    return out


def _css_simple(compound):
    """A compound selector's simple selectors: ("tag", t), ("id", x),
    ("class", x), ("attr", text), ("pseudo", name, argument or None),
    ("element", name)."""
    out, i, n = [], 0, len(compound)
    m = re.match(r"[A-Za-z*][\w-]*", compound)
    if m:
        out.append(("tag", m.group(0).lower()))
        i = m.end()
    while i < n:
        c = compound[i]
        if compound.startswith("::", i):
            m = re.match(r"::([\w-]+)(\([^)]*\))?", compound[i:])
            out.append(("element", m.group(1).lower()))
            i += m.end()
        elif c in "#.":
            m = re.match(r"[#.]((?:\\.|[\w-])+)", compound[i:])
            out.append(("id" if c == "#" else "class", m.group(1).replace("\\", "")))
            i += m.end()
        elif c == "[":
            j = compound.index("]", i)
            out.append(("attr", compound[i + 1:j]))
            i = j + 1
        elif c == ":":
            m = re.match(r":([\w-]+)", compound[i:])
            name, i = m.group(1).lower(), i + m.end()
            arg = None
            if i < n and compound[i] == "(":
                depth, j = 0, i
                while True:
                    depth += (compound[j] == "(") - (compound[j] == ")")
                    if depth == 0:
                        break
                    j += 1
                arg, i = compound[i + 1:j], j + 1
            out.append(("pseudo", name, arg))
        else:
            i += 1
    return out


def _css_compound_fits(compound, el):
    """Whether a compound selector can match `el` -- {"tag", "ids", "classes",
    "attrs", "states"}, an attribute's value None where it may be any -- or,
    for el None, a sibling this model does not know: there anything but a
    pseudo-element or a state of the pointer or of the focus may hold."""
    for s in _css_simple(compound):
        kind = s[0]
        if kind == "element":
            return False
        if kind == "pseudo":
            name, arg = s[1], s[2]
            if name in ("is", "where", "matches", "any"):
                alts = [(_css_parts(a) or [("", "*")])[-1][1] for a in _css_selectors(arg)]
                if not any(_css_compound_fits(a, el) for a in alts):
                    return False
            elif name == "not":
                sure = None if el is None else dict(el, attrs={k: v for k, v in el["attrs"].items() if v is not None})
                if sure is not None and any(_css_compound_fits((_css_parts(a) or [("", "*")])[-1][1], sure)
                                            for a in _css_selectors(arg)):
                    return False
            elif name in ("hover", "active", "focus", "focus-visible", "focus-within", "open",
                          "checked", "disabled", "empty", "target", "placeholder-shown", "visited",
                          "link", "any-link", "invalid", "required", "indeterminate", "popover-open",
                          "modal", "fullscreen", "autofill", "read-only", "read-write", "enabled",
                          "default", "valid", "optional", "user-invalid", "user-valid"):
                states = el["states"] if el is not None else {"focus-within"}
                if name not in states:
                    return False
            elif name == "root":
                if el is None or el["tag"] != "html":
                    return False
            # :has(), :first-child, :nth-*, :lang() and the like: may hold.
            continue
        if el is None:
            continue
        if kind == "tag" and s[1] not in ("*", el["tag"]):
            return False
        if kind == "id" and s[1] not in el["ids"]:
            return False
        if kind == "class" and s[1] not in el["classes"]:
            return False
        if kind == "attr":
            m = re.fullmatch(r"\s*([\w-]+)\s*(?:([~|^$*]?=)\s*[\"']?(.*?)[\"']?\s*(?:\s[is])?)?\s*", s[1])
            if not m or m.group(1) not in el["attrs"]:
                return False
            if m.group(2) and el["attrs"][m.group(1)] is not None \
                    and not (m.group(2) == "=" and el["attrs"][m.group(1)] == m.group(3)):
                return False
    return True


def _css_can_reach(sel, chain):
    """Whether the complex selector `sel` can match chain[0], the element in
    question, whose ancestors outward are chain[1:], to the root; a sibling
    named by + or ~ is one this model does not know."""
    parts = _css_parts(sel)
    if not parts:
        return False

    def fits(k, j):
        comb, compound = parts[k]
        el = chain[j] if j < len(chain) else None
        if not _css_compound_fits(compound, el):
            return False
        if k == 0:
            return True
        if comb == ">":
            return j + 1 < len(chain) and fits(k - 1, j + 1)
        if comb in ("+", "~"):
            # A sibling this model does not know, and then its parent's line.
            prev_comb, prev = parts[k - 1]
            if not _css_compound_fits(prev, None):
                return False
            if k - 1 == 0:
                return True
            return any(fits(k - 2, jj) for jj in ([j + 1] if prev_comb == ">" else
                                                     range(j + 1, len(chain))) if jj < len(chain))
        return any(fits(k - 1, jj) for jj in range(j + 1, len(chain)))
    return fits(len(parts) - 1, 0)


def _css_specificity(sel):
    """(ids, classes, types) of a complex selector: :is() and :not() count as
    their most specific argument, :where() as nothing."""
    a = b = c = 0
    for _, compound in _css_parts(sel):
        for s in _css_simple(compound):
            if s[0] == "id":
                a += 1
            elif s[0] in ("class", "attr"):
                b += 1
            elif s[0] == "tag" and s[1] != "*":
                c += 1
            elif s[0] == "element":
                c += 1
            elif s[0] == "pseudo":
                if s[1] == "where":
                    continue
                if s[1] in ("is", "not", "matches", "has") and s[2]:
                    best = max((_css_specificity(x) for x in _css_selectors(s[2])), default=(0, 0, 0))
                    a, b, c = a + best[0], b + best[1], c + best[2]
                else:
                    b += 1
    return (a, b, c)


# ---- what app.css sets on an element of a built page (29 October 2026) ---------
#
# The accessibility sweep of the R1 preview found what a page drew, and the
# checks that hold its findings read the same thing without a browser: the
# element a page's words sit in, as html.parser reads the page, and the
# declarations app.css's cascade gives it on a screen (_css_can_reach's
# model: specificity, then order, !important over both; an inherited
# property from the nearest element outward that a rule sets it on).

_OUTLINE_STYLES = ("none", "hidden", "dotted", "dashed", "solid", "double", "groove", "ridge",
                   "inset", "outset", "auto")


def _css_sides(prop, value):
    """{padding-top: ..., ...} for a padding or margin shorthand, or its
    -block or -inline pair, as the browser spreads it over the sides; {} for
    any other property. A function's value (var(), calc(), max()) is one
    value, however many spaces it has."""
    m = re.fullmatch(r"(padding|margin)(?:-(block|inline))?", prop)
    if not m:
        return {}
    vals, depth, cur = [], 0, ""
    for c in value.strip() + " ":
        depth += (c == "(") - (c == ")")
        if c.isspace() and depth == 0:
            if cur:
                vals.append(cur)
            cur = ""
        else:
            cur += c
    if not vals:
        return {}
    kind, axis = m.group(1), m.group(2)
    if axis:
        a, b = vals[0], vals[1] if len(vals) > 1 else vals[0]
        sides = ("top", "bottom") if axis == "block" else ("left", "right")
        return {f"{kind}-{sides[0]}": a, f"{kind}-{sides[1]}": b}
    t = vals[0]
    r = vals[1] if len(vals) > 1 else t
    b = vals[2] if len(vals) > 2 else t
    left = vals[3] if len(vals) > 3 else r
    return {f"{kind}-top": t, f"{kind}-right": r, f"{kind}-bottom": b, f"{kind}-left": left}


def _css_screen_rules(text):
    """[(order, at-rules, selector, {property: (value, important)}, line)]
    for every rule of a stylesheet that draws on a screen -- the printed
    sheet's are left out -- one entry a selector of its list. The outline
    shorthand is its three longhands, what it leaves out reset as a browser
    resets it ("outline:none" is a style of none and a width of medium);
    padding and margin, and their -block and -inline forms, are their four
    sides (_css_sides); the font shorthand's size is font-size too, which
    it sets."""
    out = []
    for order, (ctx, sel, body, line) in enumerate(_css_rules(text)):
        if any(re.search(r"\bprint\b", c) and not re.search(r"\bnot\s+print\b", c) for c in ctx):
            continue
        decls = {}
        for k, v in _css_decls(body):
            imp = bool(re.search(r"(?:^|[;{\s])" + re.escape(k) + r"\s*:[^;]*!\s*important", body, re.I))
            if k == "outline":
                width, style, colour = "medium", "none", "currentcolor"
                for tok in re.findall(r"[\w-]+\([^)]*\)|\S+", v):
                    if tok.lower() in _OUTLINE_STYLES:
                        style = tok.lower()
                    elif re.fullmatch(r"-?\d*\.?\d+(?:px|em|rem)?|thin|medium|thick", tok):
                        width = tok
                    else:
                        colour = tok
                decls.update({"outline-width": (width, imp), "outline-style": (style, imp),
                              "outline-color": (colour, imp)})
            elif _css_sides(k, v):
                decls.update({side: (x, imp) for side, x in _css_sides(k, v).items()})
            else:
                decls[k] = (v, imp)
                if k == "font" and _css_font_size(k, v):
                    decls["font-size"] = (_css_font_size(k, v), imp)
        if decls:
            out.extend((order, ctx, one, decls, line) for one in _css_selectors(sel))
    return out


def _css_won(rules, chain):
    """{property: (value, selector, line)} as the cascade leaves it on
    chain[0], whose ancestors outward are chain[1:] (_css_can_reach's chain),
    of _css_screen_rules' `rules`. What it inherits is _css_inherited's."""
    won = {}
    for order, _ctx, one, decls, line in rules:
        if not _css_can_reach(one, chain):
            continue
        key = (_css_specificity(one), order)
        for k, (v, imp) in decls.items():
            if k not in won or (imp, key) >= won[k][0]:
                won[k] = ((imp, key), v, one, line)
    return {k: (v, one, line) for k, (_r, v, one, line) in won.items()}


def _html_walk(page, text=None, element=None):
    """A page read as html.parser reads it: each element as
    _css_compound_fits reads one (no state: not hovered, not focused).
    `text(data, chain)` for each run of a page's text and `element(chain)`
    for each element as it opens, chain[0] the element the text is written
    in, or the one opening, and then its ancestors out to the root. A
    script's or a style's content is not text."""
    from html.parser import HTMLParser

    class Walk(HTMLParser):
        VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
                "track", "wbr"}

        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack = []

        def handle_starttag(self, tag, attrs):
            a = {k: ("" if v is None else v) for k, v in attrs}
            el = {"tag": tag, "ids": {a["id"]} if a.get("id") else set(),
                  "classes": set((a.get("class") or "").split()), "attrs": a, "states": set()}
            if element:
                element([el] + list(reversed(self.stack)))
            if tag not in self.VOID:
                self.stack.append(el)

        def handle_endtag(self, tag):
            if any(e["tag"] == tag for e in self.stack):
                while self.stack and self.stack.pop()["tag"] != tag:
                    pass

        def handle_data(self, data):
            if self.stack and self.stack[-1]["tag"] in ("script", "style"):
                return
            if text:
                text(data, list(reversed(self.stack)))

    w = Walk()
    w.feed(page)
    w.close()


def _officials_now(path=None, today=None):
    """corrections/officials.json as the pages draw it on `today` (the
    build's day by default): through build_members_elect.read_officials, the
    file's one reader, so a check holds a page to the holder the page was
    built with, a successor in office from their day (23 October 2026). A
    successor that will not read stops a builder with SystemExit; here it is
    the check's failure, in the reader's words, and not the end of the run."""
    import build_members_elect as BME
    try:
        return BME.read_officials(path, today)
    except SystemExit as e:
        raise AssertionError(str(e)) from None


# THE CALENDAR AND LEARN'S BY THE NUMBERS IN SPANISH (9 November 2026, the
# person's "more of the site in Spanish where feasible"). The Calendar's week
# pages, their month files and their script's words, and the page of statistics,
# are built in the language beside the English ones; what is held here is that
# they are, that nothing the site wrote is left in English among them, that the
# English pages gained only the way to the Spanish ones, and that the script
# that makes a page a calendar says its dates, counts and sentences in Spanish.
# The record's own words stay English (i18n.py) and are marked.

def _visible_text(page, keep_en=False):
    """The words of a page's <main>, without scripts, styles and -- unless
    keep_en -- whatever is marked lang="en"."""
    m = re.search(r"<main.*?</main>", page, re.S)
    t = m.group(0) if m else page
    t = re.sub(r"<(script|style|template)\b.*?</\1>", " ", t, flags=re.S)
    if not keep_en:
        t = re.sub(r'<(\w+)\b[^>]*\blang="en"[^>]*>.*?</\1>', " ", t, flags=re.S)
    return " ".join(__import__("html").unescape(re.sub(r"<[^>]+>", " ", t)).split())


# How many scripts asked gc.nh.gov on 6 October 2026, before any file moved
# (25), less fetch_testimony.py, retired on 7 October, and fetch_leadership.py,
# deleted on 23 October.
_ASKS_GC_FLOOR = 23


def _tap_failures(out):
    """[(test's name, the first line of what it said)] for every test that
    failed in node's TAP output, at any depth: a test whose only failure is a
    subtest's is left to the subtest, which names the failure."""
    lines, fails = out.splitlines(), []
    for i, line in enumerate(lines):
        m = re.match(r"^\s*not ok \d+ - (.*?)(?: # (?:SKIP|TODO)\b.*)?$", line)
        if not m:
            continue
        block = []
        for nxt in lines[i + 1:]:
            if nxt.strip() == "...":
                break
            block.append(nxt.strip())
        if "failureType: 'subtestsFailed'" in block:
            continue
        said = ""
        for j, b in enumerate(block):
            if b.startswith("error:"):
                said = b[len("error:"):].strip().strip("'")
                if said in ("|-", "|", ">-", ">"):
                    said = next((x for x in block[j + 1:] if x), "")
                break
        if said == "test failed":
            # A file that did not load is "test failed" in its block; what
            # failed is in node's own lines above it, as TAP comments.
            said = next((x[2:] for x in lines[:i] if re.match(r"# \w*Error\b", x)), said)
        fails.append((m.group(1).replace("\\#", "#"), said[:160]))
    return fails


# What nightly.py's logs say, in its own words. Its own lines start at the
# beginning of a line; every line a step it runs prints is indented two spaces
# by run(), so no child's output -- compile_reports.py printing a failed pull
# included -- can write any of these.
NIGHTLY_STALE_HOURS = 48      # two nights missed: one can be a machine switched off
NIGHTLY_WEEK = 7              # a week; the nightly keeps fourteen logs
NIGHTLY_SCHEDULE_RUN = 3      # three runs in a row about a day apart is a schedule
NIGHTLY_DAY_APART = (18, 30)  # hours: a day, give or take a missed start run late
NIGHTLY_STARTED = re.compile(r"^Granite Record nightly  (\d{4}-\d\d-\d\d \d\d:\d\d)", re.M)
NIGHTLY_INSTALLED = re.compile(r"^--- what the General Court changed ---$", re.M)
NIGHTLY_NO_FETCH = re.compile(r"^--- fetch ---\n  skipped: --no-fetch$", re.M)
NIGHTLY_REPORTS_RAN = re.compile(r"^--- what readers reported ---$", re.M)
NIGHTLY_REPORTS_FAILED = re.compile(r"^REPORTS FAILED:", re.M)
# Why a night meant to fetch installed nothing. The first that matches wins.
NIGHTLY_WHY = [
    (re.compile(r"^DEFERRED: a build is running", re.M), "deferred to a running build"),
    (re.compile(r"^STOPPED: preflight failed", re.M), "stopped at preflight"),
    (re.compile(r"^FETCH DEFERRED: a refusal is on file", re.M), "waited out a refusal on file"),
    (re.compile(r"^FETCH DEFERRED: archive/\.lock is held", re.M),
     "found archive/.lock held by the lane or a fetch"),
    (re.compile(r"^REFUSED while fetching", re.M), "were refused while fetching"),
    (re.compile(r"^The fetch did not complete", re.M), "had a fetch that did not complete"),
]
NIGHTLY_WHY_UNNAMED = "installed nothing for a reason the log does not name"


def _nightly_night(text):
    """What one nightly log says its night did, from nightly.py's own lines."""
    from datetime import datetime
    m = NIGHTLY_STARTED.search(text)
    failed = bool(NIGHTLY_REPORTS_FAILED.search(text))
    return {"started": datetime.strptime(m.group(1), "%Y-%m-%d %H:%M") if m else None,
            "installed": bool(NIGHTLY_INSTALLED.search(text)),
            "no_fetch": bool(NIGHTLY_NO_FETCH.search(text)),
            "why": next((w for p, w in NIGHTLY_WHY if p.search(text)), NIGHTLY_WHY_UNNAMED),
            "reports_ran": failed or bool(NIGHTLY_REPORTS_RAN.search(text)),
            "reports_failed": failed}


def _installed_none(nights):
    """The problem when the last NIGHTLY_WEEK nights meant to fetch installed
    none of the General Court's files, or "". On the laptop's own logs and,
    once it has stood down, on the nights pulled from GitHub's."""
    meant = [n for n in nights if not n["no_fetch"]][-NIGHTLY_WEEK:]
    if len(meant) < NIGHTLY_WEEK or any(n["installed"] for n in meant):
        return ""
    causes = ", ".join(f"{k} {why}" for why, k in
                       Counter(n["why"] for n in meant).most_common())
    return (f"The last {NIGHTLY_WEEK} nightly logs meant to fetch, {meant[0]['name']} to "
            f"{meant[-1]['name']}, installed none of the General Court's files: {causes}. Those "
            "files are live views, and a day not fetched cannot be fetched later. Clearing what "
            "stopped them is the person's decision -- a refusal (only after netcheck.py), "
            "whatever holds archive/.lock, a fetch that fails: tell them, and do not run "
            "nightly.py, a fetch_*.py script or refusal.py --clear to clear this. It clears on "
            "the first night that installs the day's files.")


def _nightly_log_findings(logs, now):
    """(problems, summary, scheduled) for the nightly logs in `logs`, as of `now`.

    problems is None when there is no log at all. scheduled is whether the logs
    show the nightly running on a schedule -- three runs in a row, each 18 to 30
    hours after the one before -- and only then is an old newest log a problem.
    Until 13 September 2026 any old log was: master's one nightly log is from a
    manual run on 4 September that stopped with exit 1, and nothing has
    scheduled the nightly, so preflight there would have said "the nightly has
    stopped running" of a nightly that never started.

    No problem quotes a log: a REPORTS FAILED: line carries what the step
    printed, which can be what the database sent back, and preflight's output
    is read by assistant sessions. And each problem says whose it is to clear
    and how it clears, because a session told to fix preflight first would
    otherwise reach for nightly.py, which fetches from the General Court.
    """
    from datetime import datetime
    found = sorted(Path(logs).glob("nightly-*.log"))
    if not found:
        return None, ("no logs/nightly-*.log here: the nightly has never run in this folder, "
                      "which means it has not been scheduled (or runs somewhere else)"), False
    nights = []
    for f in found:
        n = _nightly_night(f.read_text(encoding="utf-8", errors="replace"))
        n["name"] = f.name
        n["started"] = n["started"] or datetime.fromtimestamp(f.stat().st_mtime)
        nights.append(n)
    lo, hi = NIGHTLY_DAY_APART
    streak = longest = 1
    for a, b in zip(nights, nights[1:]):
        gap = (b["started"] - a["started"]).total_seconds() / 3600
        streak = streak + 1 if lo <= gap <= hi else 1
        longest = max(longest, streak)
    scheduled = longest >= NIGHTLY_SCHEDULE_RUN
    newest = nights[-1]
    hours = (now - newest["started"]).total_seconds() / 3600
    problems = []

    if scheduled and hours > NIGHTLY_STALE_HOURS:
        problems.append(
            f"The newest nightly log, logs/{newest['name']}, is from a run that started "
            f"{newest['started']:%Y-%m-%d %H:%M}, {hours:.0f} hours ago, and the logs before it "
            "show a schedule: the nightly has stopped running, or stopped reaching the end where "
            "it writes its log. Starting it again, or deciding it should stay stopped, is the "
            "person's decision, because it fetches from the General Court: tell them, and do not "
            "run nightly.py in any form to clear this. It clears when the nightly next writes a log.")

    week = _installed_none(nights)
    if week:
        problems.append(week)

    ran = [n for n in nights if n["reports_ran"]]
    if ran and ran[-1]["reports_failed"]:
        problems.append(
            f"logs/{ran[-1]['name']}, the newest log whose night reached the reports step, "
            "records REPORTS FAILED: those reader reports were not compiled, and no pull has "
            "worked since. Do not open the log for the reason: that line can carry what the "
            "database sent back, and it is for the person to read. Tell them, and do not run "
            "compile_reports.py or nightly.py to repair the pull. It clears when a later "
            "nightly's reports step succeeds.")

    if not scheduled:
        summary = (f"{len(nights)} nightly log{'s' if len(nights) != 1 else ''}, the newest "
                   f"{newest['name']} from {newest['started']:%Y-%m-%d %H:%M}, and no "
                   f"{NIGHTLY_SCHEDULE_RUN} in a row about a day apart: manual runs, not a "
                   "schedule, so their age says nothing about whether the nightly is running")
    else:
        summary = (f"{len(nights)} nightly logs on a schedule; the newest, {newest['name']}, "
                   f"started {hours:.0f} hours ago")
    summary += (f"; the last reports step, in {ran[-1]['name']}, did not fail" if ran
                else "; no log reached the reports step")
    return problems, summary, scheduled


def _nightly_log_selftest():
    """The log reader on folders of made-up logs whose answers are known.

    The bodies use nightly.py's own sentences; _nightly_reports_loud holds the
    reader to logs nightly.main() really writes, so a sentence changed there
    fails there rather than passing here.
    """
    import time
    from datetime import datetime, timedelta
    now = datetime(2026, 9, 13, 9, 0)
    tmp = Path(tempfile.mkdtemp())
    pre = "\n--- preflight ---\n  (12s, exit 0)\n"
    nothing = "\nNothing new was installed, so there is nothing to rebuild.\n"
    reports = "\n--- what readers reported ---\n  0 new, 0 for triage, 0 held, 0 malformed\n  (3s, exit 0)"
    good = (pre + "\n--- the day's bulk files ---\n  (40s, exit 0)\n"
            "\n--- what the General Court changed ---\n  (1s, exit 0)\n"
            "\n--- rebuild ---\n  (900s, exit 0)\n" + reports)
    refused = (pre + "\nFETCH DEFERRED: a refusal is on file (docket at 2026-09-12T21:36); "
               "clearing one is a person's decision, after netcheck.py\n" + nothing + reports)
    locked = (pre + "\nFETCH DEFERRED: archive/.lock is held (pid 1): the lane or a fetch is "
              "running\n" + nothing + reports)
    building = ("\nDEFERRED: a build is running (.build.lock is fresh). Nothing done, and no "
                "reports: they read the pages that build is rewriting.")
    fetch_failed = (pre + "\n--- the day's bulk files ---\n  (40s, exit 1)\n\nThe fetch did not "
                    "complete (exit 1); nothing was installed, so tonight's build would be "
                    "yesterday's.\n" + nothing + reports)
    stopped = ("\n--- preflight ---\n  (12s, exit 1)\n\nSTOPPED: preflight failed. Nothing "
               "fetched, nothing built.\n" + reports)
    no_fetch = pre + "\n--- fetch ---\n  skipped: --no-fetch\n\n--- rebuild ---\n  (900s, exit 0)\n" + reports
    pull_failed = good + "\n\nREPORTS FAILED: compile_reports.py exit 1: SECRET-WORDS"
    # Master's one nightly log, 4 September: a run by hand from an older
    # nightly.py, no fetch step, stopped in the build with exit 1.
    by_hand = ("\nlive now: 2,234 bills, 406 legislators, 2,234 bill_data, 2,234 bill_pages\n"
               + pre + "\n--- rebuild ---\n  18 steps, session 2026\n  [1/18] archive the bulk "
               "files\n        FAILED after 15.5s\n\n" + "=" * 74 + "\nfinished 17:56, 3 min, exit 1")

    def night(day, body=good, at="03:00", header=True):
        head = f"{'=' * 74}\nGranite Record nightly  {day} {at}\n{'=' * 74}\n" if header else ""
        f = tmp / f"nightly-{day}.log"
        f.write_text(head + body + "\n", encoding="utf-8")
        return f

    def nights(bodies, last=now, at="03:00"):
        """One log a night, a day apart, the last of them on `last`'s date."""
        for k, body in enumerate(bodies):
            night(f"{last - timedelta(days=len(bodies) - 1 - k):%Y-%m-%d}", body, at)

    def read():
        return _nightly_log_findings(tmp, now)

    def findings():
        return read()[0]

    def says_whose(problem):
        return "person" in problem and "It clears" in problem and "do not run" in problem

    def clear():
        for f in tmp.iterdir():
            f.unlink()

    try:
        assert findings() is None, "a folder with no nightly log was not a skip"
        (tmp / "build.log").write_text("DEFERRED: not the nightly's\n", encoding="utf-8")
        assert findings() is None, "a log that is not the nightly's was read as one"
        clear()
        night("2026-09-13")
        assert findings() == [], f"a good night this morning was a problem: {findings()}"

        # Old is stale only once the logs show a schedule.
        clear()
        night("2026-09-04", by_hand, at="17:53")
        problems, summary, scheduled = read()
        assert problems == [] and not scheduled, \
            f"one old log from a run by hand was read as a nightly that stopped: {problems}"
        assert "manual runs" in summary, summary
        night("2026-09-03", by_hand, at="17:10")
        assert findings() == [], "two old runs by hand a day apart were read as a schedule"
        clear()
        for day in ("2026-09-01", "2026-09-03", "2026-09-05"):
            night(day)
        assert findings() == [] and not read()[2], "three runs two days apart were read as a schedule"
        clear()
        nights([good] * 3, last=datetime(2026, 9, 11), at="10:00")      # 47 hours
        assert findings() == [] and read()[2], "a scheduled night 47 hours ago was called stale"
        clear()
        nights([good] * 3, last=datetime(2026, 9, 11), at="08:00")      # 49 hours
        got = findings()
        assert got and "stopped running" in got[0], "a scheduled night 49 hours ago was not stale"
        assert says_whose(got[0]) and "nightly.py" in got[0], \
            "the stale message does not say it is the person's, and how it clears"
        clear()
        nights([good] * 3, last=datetime(2026, 8, 22))
        night("2026-09-04", by_hand, at="17:53")
        got = findings()
        assert got and "stopped running" in got[0], \
            "a schedule that stopped, then one run by hand, was not stale"
        clear()
        nights([good] * 2, last=datetime(2026, 9, 10), at="07:00")
        old = night("2026-09-11", header=False)               # no header: the file's own time
        t = time.mktime((now - timedelta(hours=50)).timetuple())
        os.utime(old, (t, t))
        assert findings() and "stopped running" in findings()[0], "a headerless stale log passed"

        # A week meant to fetch that installed nothing, whatever the cause.
        clear()
        nights([refused] * 7)
        got = findings()
        assert len(got) == 1 and "7 waited out a refusal" in got[0], f"a week of refusal: {got}"
        assert says_whose(got[0]) and "refusal.py --clear" in got[0], \
            "the week message does not say clearing it is the person's"
        clear()
        nights([locked, building] * 3 + [locked])
        got = findings()
        assert got and "4 found archive/.lock held" in got[0] and "3 deferred to a running build" \
            in got[0], f"the causes of a week were not named: {got}"
        clear()
        nights([fetch_failed] * 7)
        assert findings() and "did not complete" in findings()[0], "a week of failed fetches passed"
        clear()
        nights([stopped] * 7)
        assert findings() and "stopped at preflight" in findings()[0], \
            "a week stopped at preflight passed"
        night(f"{now - timedelta(days=7):%Y-%m-%d}")          # an older good night changes nothing
        assert findings(), "an eighth, older good night hid the week"
        night(f"{now:%Y-%m-%d}")                              # the newest one fetched
        assert findings() == [], "six nights stopped and a good one were a problem"
        clear()
        nights([refused] * 6)
        assert findings() == [], "six nights without a fetch are not yet a week"
        clear()
        nights([refused] * 6 + [no_fetch])
        assert findings() == [], "a --no-fetch night was counted as a night meant to fetch"
        night(f"{now - timedelta(days=7):%Y-%m-%d}", refused)
        assert findings(), "a --no-fetch night ended a week without a fetch"
        clear()
        nights([no_fetch] * 7)
        assert findings() == [], "a week of rebuilds by hand with --no-fetch was a missed week"
        clear()
        nights([good + "\n  FETCH DEFERRED: said by a child"] * 7)
        assert findings() == [], "a step's indented output was read as the nightly deferring"
        clear()
        nights([refused.replace("  (12s", "  --- what the General Court changed ---\n  (12s")] * 7)
        assert findings(), "a step's indented output was read as the nightly installing"

        # REPORTS FAILED: in the newest log whose night reached the reports step.
        clear()
        night("2026-09-12", pull_failed)
        night("2026-09-13")
        assert findings() == [], "a report failure two nights ago, followed by a good night, still failed"
        night("2026-09-13", pull_failed)
        got = findings()
        assert got and "REPORTS FAILED" in got[0], "the newest log's REPORTS FAILED: passed"
        assert "SECRET-WORDS" not in " ".join(got), "the check quoted what the failed step printed"
        assert says_whose(got[0]) and "Do not open the log" in got[0], \
            "the REPORTS FAILED message does not keep a session out of the log"
        night("2026-09-13", building)
        got = findings()
        assert got and "nightly-2026-09-12.log" in got[0], \
            "a failed pull followed by a night that ran no reports step passed"
        clear()
        night("2026-09-13", good.replace("  0 new", "  REPORTS FAILED: a child's line"))
        assert findings() == [], "a step's indented output was read as the nightly's REPORTS FAILED:"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ("empty folder skips; old logs are stale only on a schedule, 47 h fresh, 49 h stale; "
            "seven nights meant to fetch that installed nothing fail, with the cause, and "
            "--no-fetch nights do not count; REPORTS FAILED: counts from the newest log that "
            "reached the reports step, and is never quoted")


# ---- the turn, built on a fixture -------------------------------------------------
#
# THE RULES BY WHAT THEY DO (the review of 5 October 2026). Fourteen of thirty
# mutations of the turn's rules got past preflight --code, because the never-
# merge rule and several freeze checks were held by words in the source: a
# build_data that merged a finished term's docket rows, took a build of another
# freeze, or went on over an older term nobody froze passed every check. So a
# term of two bills is written as the General Court's fourteen day files,
# frozen with freeze_term, turned, and built with build_data itself.

_TURN_LASTS = ("Adams", "Baker", "Clark", "Davis", "Evans", "Foster", "Grant", "Hayes", "Irwin",
               "Jones")


def _turn_day(rows):
    return ("﻿" + "".join(r + "\r\n" for r in rows)).encode("utf-8")


def _turn_member(i):
    # A surname of letters only: build_data matches a member by first and last
    # name with every other character taken out.
    last = _TURN_LASTS[i % 10] + "son" * (i // 10)
    return (f"{i}|{last}|Pat||H|{1000 + i}|01|{i % 9 + 1}|R||1 Main St|Concord|NH|03301|"
            f"m{i}@gc.nh.gov")


def _turn_files(members, docket, lsrs, only, spons, summary, history):
    """The fourteen day files, as snapshot_gencourt installs them."""
    head = ("LastName\tFirstName\tMiddleName\tLegislativeBody\tseatno\tCounty\tDistrict\t"
            "electedStatus\tWorkEmail\tparty\tCommittee1")
    rows = [_turn_member(i).split("|") for i in members]
    return {
        "Docket.txt": _turn_day(docket), "LSRs.txt": _turn_day(lsrs),
        "LsrsOnly.txt": _turn_day(only), "LsrSponsors.txt": _turn_day(spons),
        "legislators.txt": _turn_day(["|".join(f) for f in rows]),
        "Members.txt": _turn_day([head] + [f"{f[1]}\t{f[2]}\t\tH\t0\tBelknap\t{f[7]}\tIncumbent\t"
                                           f"{f[14]}\tR\tFixture Affairs" for f in rows]),
        "RollCallSummary.txt": _turn_day(summary), "RollCallHistory.txt": _turn_day(history),
        "Committees.txt": _turn_day(["H01|Fixture Affairs|FA"]),
        "SubjectCodes.txt": _turn_day(["1|AGR|Agriculture"]),
        "GeneralCodes.txt": _turn_day(["02|HOUSE"]),
        "BodyStatusCodes.txt": _turn_day(["15|CONFERENCE COMMITTEE"]),
        "HouseDistricts.txt": _turn_day(["01|01|0|Fixtureville"]),
        "Counties.txt": _turn_day(["01|Belknap|Belk."])}


# ---- a night the export fails: the day's files from the database --------------
#
# On 27 and 28 September and 1 October 2026 the General Court's bulk-file
# export came back empty on every try and nothing was built. The person
# approved the night asking the SQL host instead, gently, as the fallback:
# fetch_day_db.py asks, dayfiles_from_db.py reshapes and guards, nightly.py
# installs all seven changing files or none, and probe_db.py keeps that host's
# own hold. Nothing below asks anybody anything: the views are a fixture, or
# the dump already in db/, and PowerShell is never started.

# A few rows of each view, in the dump's column order, and the lines the
# export holds for the same state. The bills' rows are the General Court's own
# (HB 54, HB 109 and SB 416 as they stood on 8 September 2026); the members
# are made up, in the shapes real rows have: a senator with both address
# lines, which the export writes the other way round; a member who has left.
_DBDAY_VIEWS = {
    "Legislators": [
        "43|Cedar|Cy|200043|H.|S|True||09|04|D|6035550043|State House Annex, Room 228|"
        "25 Capitol Street|Concord|03301|NH|cy.cedar@example.gov|M|1034|NHLMS",
        "101|Alder|Ann|300101|B|H|True|3001|08|13|R|6035550101|1 Example Street| |Derry|"
        "03038-4258|NH|ann.alder@example.gov|F||NHLMS",
        "38|Elm|Ed|200038|L|S|False||11|02|R|6035550038|107 North Main Street State House "
        "Rm. 105||Concord|03301|NH|ed.elm@example.gov|M|76|NHLMS",
        "102|Birch|Ben|300102||H|True|2044|10|01|D||State House-House Member Mail|"
        "107 North Main Street|Concord|03301|NH|ben.birch@example.gov|M||NHLMS",
        "35|Dogwood|Di|200035||S|True||07|15|R||State House, Room 302|107 North Main Street|"
        "Concord|03301|NH|di.dogwood@example.gov|F|1041|NHLMS",
        "103|Fir|Flo|300103||H|False|1001|01|00|D||9 Example Road||Laconia|03246|NH|"
        "flo.fir@example.gov|F||NHLMS",
    ],
    "Legislation": [
        "0054|HB|2026|0010|allowing alternative treatment centers to operate for-profit.|True|H|1|"
        "False|True|False|25-0010|PMH|HB  0054|HB54|12/19/2024 11:19:00||R|H09|H34|"
        "01/08/2025 00:00:00|10||03/06/2025 00:00:00|01/07/2026 00:00:00|0|S10|S10|"
        "01/29/2026 00:00:00|06|04/09/2026||04/09/2026 00:00:00|0|03||||False|PublicNHLMS||8|S10|"
        "02/17/2026 13:40:00|SH Room 100|True|NHLMS|15",
        "0109|HB|2026|0024|relative to false reports to law enforcement.|True|H|1|False|True|"
        "False|25-0024|CCP|HB  0109|HB109|12/24/2024 12:50:00|43|R|H26|H26|01/08/2025 00:00:00|12||"
        "03/20/2025 00:00:00|04/09/2026 00:00:00|0|S10|S10|03/20/2025 00:00:00|11|01/07/2026||"
        "01/07/2026 00:00:00|1|05||07/07/2026||True|PublicNHLMS||8|S10|04/03/2025 13:30:00|"
        "SH Room 100|False|NHLMS|29",
        "0050|HB|2025|0002|(New Title) relative to intentional or knowing violation of the "
        "prohibition on teaching discrimination.|True|H|1|False|False|False|25-0002|DIS|HB  0050|"
        "HB50|12/19/2024 11:16:00||R|H62|H62|01/08/2025 00:00:00|11||03/20/2025 00:00:00|"
        "03/26/2025 00:00:00|1|S05|S05|03/27/2025 00:00:00|09|05/15/2025||05/15/2025 00:00:00|0|03|"
        "|||False|PublicNHLMS||8|S05|04/29/2025 10:15:00|LOB Room 101|False|NHLMS|7",
        "0416|SB|2026|2001|relative to the pooling and sharing of tips among tipped employees.|"
        "True|S|2|False|False|False|26-2001|EPR|SB  0416|SB416|11/20/2025 16:24:00||R|H11|H11|"
        "02/19/2026 00:00:00|07||05/07/2026 00:00:00|05/14/2026 00:00:00|1|S37|S37|"
        "01/07/2026 00:00:00|11|02/19/2026||02/19/2026 00:00:00|1|02||||False|PublicNHLMS||8|H11|"
        "04/14/2026 10:30:00|GP Room 159|False|NHLMS|1190",
    ],
    "Sponsors": [
        "2026|2001|1|200035|1|True|NHLMS||False|1190|35",
        "2025|240|1|300101|1|True|NHLMS||False|247|101",
        "2026|10|1|300101|1|True|NHLMS||False|15|101",
        "2026|10|4|300102|0|False|NHLMS||False|15|102",
        "2026|2001|2|300102|0|True|NHLMS||False|1190|102",
        "2026|10|3|200043|0|True|NHLMS||False|15|43",
        "2026|2001|3|300103|0|True|NHLMS||False|1190|103",
    ],
    "Docket": [
        "2026|10||02/19/2025 10:47:54|HB54|H|  Executive Session: 02/05/2025 08:30 am LOB 301-303|"
        "NHLMS|15|01/01/2200 00:00:00|10050000",
        "2025|173||12/04/2024 10:44:26|SR1 |S|Introduced and Adopted, VV; 12/04/2024;  SJ 1|NHLMS|"
        "180|01/01/2200 00:00:00|1000",
        "2026|2001||01/27/2026 15:52:15|SB416|S| Hearing: 02/03/2026, Room 100, SH, 10:00 am;  SC 2|"
        "NHLMS|1190|01/01/2200 00:00:00|48286000",
        "2026|10||12/23/2024 15:19:36|HB54|H|  Introduced 01/08/2025 and referred to Health, Human "
        "Services and Elderly Affairs  HJ 2  P. 3|NHLMS|15|01/01/2200 00:00:00|88000",
        "1989|1|HB  0169|01/05/1989 14:18:39|HB169|H|INTRODUCED AND REF TO EXEC & ADMIN     HJ 13 "
        ",P 138|BillStatusDB|0|01/05/1989 14:18:39|",
        "2026|2001||11/21/2025 16:09:25|SB416|S|  Introduced 01/07/2026 and Referred to Commerce;  "
        "SJ 1|NHLMS|1190|01/01/2200 00:00:00|39134000",
        "2026|10||01/15/2025 12:24:36|HB54|H|  Public Hearing: 01/22/2025 01:45 pm LOB 210-211|"
        "NHLMS|15|01/01/2200 00:00:00|2662000",
        "2026|2001||02/04/2026 15:30:58|SB416|S|Committee Report: Ought to Pass with Amendment # "
        "2026-0507s, 02/19/2026; Vote 5-0; CC;  SC 6|NHLMS|1190|01/01/2200 00:00:00|50856000",
        "2026|10||02/05/2025 08:20:30|HB54|H|   Subcommittee Work Session: 02/05/2025 08:30 am LOB "
        "301-303|NHLMS|15|01/01/2200 00:00:00|6614000",
    ],
    "RollCallSummary": [
        "2026|S|1|01/07/2026 00:00:00|HB292|7|17|24|0|||Floor Amendment|(New Title) establishing "
        "a revolving loan fund for school districts.||sysAdminSenApp|01/07/2026 15:24:43|True|",
        "2025|H|1|01/08/2025 11:08:04|HRULE64|216|164|6|13|||Amend H Rule 64|||hadmin|"
        "01/09/2025 16:34:06|True|35250",
        "2026|H|3|01/07/2026 11:12:09|HB609|193|152|16|34|||Adopt Floor Amendment|relative to "
        "firearms.||VOTE SYSTEM||True|39663",
    ],
    "RollCallHistory": [
        "200043|2026|S|1|HB292|1|119|01/07/2026 15:24:43|",
        "300102|2026|H|3|HB609|1|VOTE SYSTEM||39663",
        "300101|2025|H|1|HRULE64 |1|hadmin|01/09/2025 16:34:06|35250",
        "200035|2026|S|1|HB292|2|119|01/07/2026 15:24:43|",
        "300101|2026|H|3|HB609|3|VOTE SYSTEM||39663",
        "200038|2026|S|1|HB292|6|119|01/07/2026 15:24:43|",
    ],
    "Subject": ["2|6|L|Agency Appropriations|0|1|AGE|True|10/23/2014 00:00:00",
                "3|6|L|Agriculture|0|1|AGR|True|10/23/2014 00:00:00"],
    "GeneralStatusCodes": ["01|LEGISLATIVE SERVICES|True", "02|HOUSE|True"],
    "BodyStatusCodes": ["2|02|IN COMMITTEE|IN COMMITTEE|True|House",
                        "30|01|NO ACTION|NO ACTION|True|Senate",
                        "31|02|IN COMMITTEE|IN COMMITTEE|True|Senate"],
    "County": ["1|Belknap|03/18/2015 15:53:11|Belk.", "2|Carroll|03/18/2015 15:53:26|Carr.",
               "11||09/13/2015 00:00:00|"],
    "Committees": ["H05|Education|Education|EDUCATION|LOB 205-|603-271-3565||1|A|B||"
                   "e@example.gov|1|NHLMS"],
}
_DBDAY_EXPORT = {
    "Docket.txt": [
        "2025|0173|12/4/2024 10:44:26 AM|SR1|S|Introduced and Adopted, VV; 12/04/2024;  SJ 1|"
        "12/4/2024 10:44:26 AM",
        "2026|0010|12/23/2024 3:19:36 PM|HB54|H|  Introduced 01/08/2025 and referred to Health, "
        "Human Services and Elderly Affairs  HJ 2  P. 3|1/21/2025 1:21:39 PM",
        "2026|0010|2/5/2025 8:20:30 AM|HB54|H|   Subcommittee Work Session: 02/05/2025 08:30 am "
        "LOB 301-303|2/5/2025 8:20:48 AM",
        "2026|0010|1/15/2025 12:24:36 PM|HB54|H|  Public Hearing: 01/22/2025 01:45 pm LOB 210-211|"
        "1/30/2025 12:00:27 PM",
        "2026|0010|2/19/2025 10:47:54 AM|HB54|H|  Executive Session: 02/05/2025 08:30 am LOB "
        "301-303|2/19/2025 10:47:54 AM",
        "2026|2001|11/21/2025 4:09:25 PM|SB416|S|  Introduced 01/07/2026 and Referred to Commerce;"
        "  SJ 1|1/8/2026 12:27:34 PM",
        "2026|2001|1/27/2026 3:52:15 PM|SB416|S| Hearing: 02/03/2026, Room 100, SH, 10:00 am;  SC "
        "2|1/27/2026 3:52:15 PM",
        "2026|2001|2/4/2026 3:30:58 PM|SB416|S|Committee Report: Ought to Pass with Amendment # "
        "2026-0507s, 02/19/2026; Vote 5-0; CC;  SC 6|2/9/2026 11:13:45 AM",
    ],
    "LSRs.txt": [
        "2026|0024|relative to false reports to law enforcement.|H|1|0|1|0|25-0024|HB  0109|HB109|"
        "0043|CCP|H26|H26|1/8/2025 12:00:00 AM|12||3/20/2025 12:00:00 AM|4/9/2026 12:00:00 AM|0|"
        "S10|S10|3/20/2025 12:00:00 AM|11|01/07/2026||1/7/2026 12:00:00 AM|0|05|S10|"
        "4/3/2025 1:30:00 PM|SH Room 100||||0|0|",
        "2026|0010|allowing alternative treatment centers to operate for-profit.|H|1|0|1|0|25-0010|"
        "HB  0054|HB54||PMH|H09|H34|1/8/2025 12:00:00 AM|10||3/6/2025 12:00:00 AM|"
        "1/7/2026 12:00:00 AM|0|S10|S10|1/29/2026 12:00:00 AM|06|04/09/2026||4/9/2026 12:00:00 AM|0|"
        "03|S10|2/17/2026 1:40:00 PM|SH Room 100||||0|0|",
        "2026|2001|relative to the pooling and sharing of tips among tipped employees.|S|2|0|0|0|"
        "26-2001|SB  0416|SB416||EPR|H11|H11|2/19/2026 12:00:00 AM|07||5/7/2026 12:00:00 AM|"
        "5/14/2026 12:00:00 AM|0|S37|S37|1/7/2026 12:00:00 AM|12|02/19/2026||2/19/2026 12:00:00 AM|"
        "0|02|H11|4/14/2026 10:30:00 AM|GP Room 159||||0|0|",
    ],
    "LsrSponsors.txt": ["2026|10|3|43|0", "2026|2001|3|103|0", "2026|10|1|101|1",
                        "2026|2001|2|102|0", "2026|2001|1|35|1"],
    "LsrsOnly.txt": [
        "26-2001|102|1190|2026|Sponsor|SB416|H|relative to the pooling and sharing of tips among "
        "tipped employees.",
        "26-2001|35|1190|2026|Prime|SB416|S|relative to the pooling and sharing of tips among "
        "tipped employees.",
    ],
    "legislators.txt": [
        "101|Alder|Ann|B|H|3001|8|13|R|1 Example Street| |Derry|NH|03038-4258|"
        "ann.alder@example.gov",
        "35|Dogwood|Di||S||7|15|R|107 North Main Street|State House, Room 302|Concord|NH|03301|"
        "di.dogwood@example.gov",
        "43|Cedar|Cy|H.|S||9|4|D|25 Capitol Street|State House Annex, Room 228|Concord|NH|03301|"
        "cy.cedar@example.gov",
        "102|Birch|Ben||H|2044|10|1|D|State House-House Member Mail|107 North Main Street|Concord|"
        "NH|03301|ben.birch@example.gov",
    ],
    "RollCallSummary.txt": [
        "2026|H|3|1/7/2026 11:12:09 AM|HB609|193|152|16|34|||Adopt Floor Amendment|relative to "
        "firearms.||",
        "2026|S|1|1/7/2026 12:00:00 AM|HB292|7|17|24|0|||Floor Amendment|(New Title) establishing "
        "a revolving loan fund for school districts.||1/7/2026 3:24:43 PM",
    ],
    "RollCallHistory.txt": [
        "2026|H|3|300101|101|HB609|Not Voting/Excused|",
        "2026|H|3|300102|102|HB609|Yea|",
        "2026|S|1|200035|35|HB292|Nay|1/7/2026 3:24:43 PM",
        "2026|S|1|200038|38|HB292|Presiding|1/7/2026 3:24:43 PM",
        "2026|S|1|200043|43|HB292|Yea|1/7/2026 3:24:43 PM",
    ],
    "SubjectCodes.txt": ["2|AGE|Agency Appropriations", "3|AGR|Agriculture"],
    "GeneralCodes.txt": ["01|LEGISLATIVE SERVICES", "02|HOUSE"],
    "BodyStatusCodes.txt": ["02|IN COMMITTEE", "01|NO ACTION"],
    "Counties.txt": ["01|Belknap|Belk.", "02|Carroll|Carr."],
    "Committees.txt": ["H05|Education|EDUCATION",
                       "H53|Criminal Justice and Public Safety Joint with Judiciary|CJ/JUD"],
    "HouseDistricts.txt": ["1|Belknap|1"],
    "Members.txt": ["Alder, Ann|ann.alder@example.gov|603-555-0101|Member"],
}


def _dbday_bytes(lines):
    """A file as the export writes one: a byte-order mark, CRLF line ends."""
    return ("\ufeff" + "".join(ln + "\r\n" for ln in lines)).encode("utf-8")


def _dbday_install(root, export=None):
    """The fixture's export, installed in `root` as the last good day's files."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for name, lines in (export or _DBDAY_EXPORT).items():
        (root / name).write_bytes(_dbday_bytes(lines))


def _dbday_views(DF, folder, views=None, source=True, entries=None):
    """What fetch_day_db.py leaves: one .psv per view and source.json.
    `views` replaces rows of the fixture's; `entries` replaces a view's entry
    in source.json (an error, a count that is not the rows)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    rows = dict(_DBDAY_VIEWS, **(views or {}))
    src = {"asked": "2026-10-01T07:21:00", "views": {}}
    for name, lines in rows.items():
        if lines is None:
            continue
        (folder / f"{name}.psv").write_bytes("".join(ln + "\r\n" for ln in lines).encode("utf-8"))
        src["views"][name] = {"asked": "2026-10-01T07:21:00", "count": len(lines),
                              "rows": len(lines), "seconds": 1.0}
    for name, e in (entries or {}).items():
        src["views"][name] = e
    if source:
        (folder / DF.SOURCE).write_text(json.dumps(src), encoding="utf-8")


def _dbday_expected():
    """The seven day files the fixture's views must make: the export's own
    lines in the export's own order, but for the one thing the database
    cannot give -- the docket's seventh column, which repeats the third. SB
    416's Senate status code is 11 in the view and 12 in the export, and the
    rebuilt file keeps the installed 12: the view is the side that is wrong."""
    want = {k: list(v) for k, v in _DBDAY_EXPORT.items()}
    want["Docket.txt"] = ["|".join(f[:6] + [f[2]])
                          for f in (ln.split("|") for ln in _DBDAY_EXPORT["Docket.txt"])]
    lsr = want["LSRs.txt"][2].split("|")
    assert lsr[10] == "SB416" and lsr[24] == "12" and \
        _DBDAY_VIEWS["Legislation"][3].split("|")[29] == "11"
    return want


# Real rows, for the content guards: cut on 2 October 2026 from the files the
# General Court published, and each as it stood in the export named.
#
#   Docket.txt           18 rows of the export of 30 September: three of HB
#                        1218's, its minority report as the export of
#                        6 September still had it (amendment 2026-0596h, which
#                        the clerk corrected to 0956h on the 14th); the last
#                        row of each bill that 2 October's new rows are under;
#                        three rows that carry a journal citation and one a
#                        mark; a conference meeting stamped a week ahead of the
#                        day it was written; and the file's newest entry
#   LSRs.txt             six bill records of that export
#   LsrSponsors.txt,     the senators' rows on four of those bills
#   LsrsOnly.txt
#   legislators.txt      the 24 senators. Their e-mail addresses are made up,
#                        so that none a scraper could use is in the
#                        repository; every other column is the export's
#   RollCallSummary.txt  the Senate's roll calls 45 to 52 of 2026, and the 24
#   RollCallHistory.txt  ballots of the 49th, as the export of 6 September
#                        had them: filed under SB 655
#
# and what a later night really brought (_DBGUARD_TONIGHT): nine of the 31
# docket rows the database held on 2 October; HB 1218's row as corrected;
# roll call 49 as the export of 13 September had it, moved to SB 665; and the
# senators' rows on the two requests with no bill number, which the
# Legislation view does not carry.
_DBGUARD_REAL = {
    "Docket.txt": [
        "2026|2711|2/17/2026 3:29:16 PM|HB1218|H|Executive Session: 03/03/2026 10:00 am GP 231|2/17/2"
        "026 3:29:16 PM",
        "2026|2711|3/4/2026 5:49:51 PM|HB1218|H|Majority Committee Report: Inexpedient to Legislate  "
        "03/03/2026 (Vote 9-8; RC)  HC 11  P. 94|3/16/2026 11:06:00 AM",
        "2026|2711|3/4/2026 5:50:17 PM|HB1218|H|Minority Committee Report: Ought to Pass with Amendme"
        "nt # 2026-0596h|3/4/2026 5:50:17 PM",
        "2026|0038|9/15/2026 3:58:02 PM|HB100|H|   Full Committee Work Session: 09/29/2026 10:00 am G"
        "P 228|9/15/2026 3:58:02 PM",
        "2026|2083|9/15/2026 3:58:54 PM|SB632|H|   Full Committee Work Session: 09/29/2026 10:00 am G"
        "P 228|9/15/2026 3:58:54 PM",
        "2026|0001|9/15/2026 3:58:38 PM|HB561|H|   Full Committee Work Session: 09/29/2026 10:00 am G"
        "P 228|9/15/2026 3:58:38 PM",
        "2026|2986|8/21/2026 3:00:50 PM|HB1753|H|Executive Session: 09/24/2026 10:30 am GP 228|8/21/2"
        "026 3:00:50 PM",
        "2026|3022|8/21/2026 3:01:02 PM|HCR16|H|Executive Session: 09/24/2026 10:30 am GP 228|8/21/20"
        "26 3:01:02 PM",
        "2026|0452|9/14/2026 10:00:59 AM|HB312|H|   Subcommittee Work Session: 09/30/2026 10:10 am GP"
        " 229|9/14/2026 10:00:59 AM",
        "2026|0393|9/14/2026 10:01:16 AM|HB359|H|   Subcommittee Work Session: 09/30/2026 10:10 am GP"
        " 229|9/14/2026 10:01:16 AM",
        "2026|2092|8/21/2026 12:26:15 PM|SB647|H|   Subcommittee Work Session: 09/09/2026 10:00 am GP"
        " 229|8/21/2026 12:26:15 PM",
        "2026|0602|9/14/2026 10:01:36 AM|HB427|H|   Subcommittee Work Session: 09/30/2026 10:10 am GP"
        " 229|9/14/2026 10:01:36 AM",
        "2026|2136|2/19/2026 1:29:10 PM|SB532|S|Inexpedient to Legislate, RC 16Y-8N, MA === BILL KILL"
        "ED ===; 02/19/2026;  SJ 4|5/11/2026 8:46:46 AM",
        "2026|2797|3/5/2026 9:23:44 AM|HB1036|H|Inexpedient to Legislate: MA VV 03/05/2026  HJ 6  P. "
        "2|6/9/2026 1:21:57 PM",
        "2026|2947|3/5/2026 9:24:15 AM|HB1228|H|Ought to Pass: MA VV 03/05/2026  HJ 6  P. 2|6/9/2026 "
        "1:22:14 PM",
        "2026|2187|3/19/2026 9:14:15 AM|SB633|H|==CANCELLED== Executive Session: 03/23/2026 11:30 am "
        "GP 159|3/30/2026 2:20:34 PM",
        "2026|3166|5/26/2026 12:00:00 AM|HB1042|H|Conference Committee Meeting: 05/26/2026 01:00 pm G"
        "P 228|5/19/2026 12:05:52 PM",
        "2026|2191|9/29/2026 12:41:48 PM|SB570|H| Interim Study Report: Recommended for Future Legisl"
        "ation  09/28/2026 (Vote 9-0; )|9/29/2026 12:41:48 PM",
    ],
    "LSRs.txt": [
        "2026|0038|prohibiting the use of state funds for new passenger rail projects.|H|1|0|1|0|25-0"
        "038|HB  0100|HB100||TRA|H20|H20|1/8/2025 12:00:00 AM|07||3/20/2025 12:00:00 AM|1/7/2026 12:0"
        "0:00 AM|0||||||||0|02|H20|1/28/2025 11:30:00 AM|LOB Room 201||||0|0|",
        "2026|0213|relative to rebates to ratepayers from the renewable energy fund.|H|1|0|1|0|25-021"
        "3|HB  0224|HB224||ENU|H24|H28|1/8/2025 12:00:00 AM|04||3/6/2025 12:00:00 AM|1/7/2026 12:00:0"
        "0 AM|0||||||||0|02|H28|3/18/2025 10:00:00 AM|LOB Room 202-204||||0|0|",
        "2026|2136|increasing the requirements of the education freedom savings account oversight com"
        "mittee and modifying the purpose of the committee.|S|2|0|0|0|26-2136|SB  0532|SB532||STG||||"
        "||||0|S05|S05|1/7/2026 12:00:00 AM|09|05/08/2026||2/19/2026 12:00:00 AM|0|03|S05|2/10/2026 9"
        ":15:00 AM|SL Room Map Room||||0|0|",
        "2026|2187|(New Title) relative to donations received by the granite patron of the arts fund."
        "|S|2|0|1|0|26-2187|SB  0633|SB633|0144|STG|H28|H28|2/19/2026 12:00:00 AM|11||5/7/2026 12:00:"
        "00 AM|4/23/2026 12:00:00 AM|0|S17|S17|1/7/2026 12:00:00 AM|12|05/07/2026||2/5/2026 12:00:00 "
        "AM|0|05|H28|3/23/2026 10:30:00 AM|GP Room 159||||0|0|",
        "2026|2191|(New Title) relative to legislative ethics.|S|2|0|0|0|26-2191|SB  0570|SB570||LEG|"
        "H12|H12|3/26/2026 12:00:00 AM|04||5/7/2026 12:00:00 AM|5/14/2026 12:00:00 AM|0|S06|S06|1/7/2"
        "026 12:00:00 AM|11|03/26/2026||3/26/2026 12:00:00 AM|0|02|H12|4/15/2026 10:00:00 AM|GP Room "
        "234||||0|0|",
        "2026|2711|relative to the disclosure of rights and responsibilities during the sale of a mob"
        "ile home in a mobile home park.|H|1|0|0|0|26-2711|HB  1218|HB1218||PRP|H64|H64|1/7/2026 12:0"
        "0:00 AM|31||3/5/2026 12:00:00 AM|3/11/2026 12:00:00 AM|0||||||||0|02|H64|2/10/2026 11:00:00 "
        "AM|GP Room 231||||0|0|",
    ],
    "LsrSponsors.txt": [
        "2026|2187|1|43|1",
        "2026|2092|3|926|0",
        "2026|2187|4|926|0",
        "2026|2092|4|928|0",
        "2026|2187|2|8747|0",
        "2026|2092|2|9406|0",
        "2026|2187|3|9406|0",
        "2026|2092|5|9839|0",
        "2026|2136|3|9856|0",
        "2026|2187|8|9856|0",
        "2026|2136|2|10599|0",
        "2026|2187|7|10599|0",
        "2026|2136|1|10600|1",
        "2026|2187|9|10604|0",
        "2026|2092|1|11458|1",
        "2026|2187|5|11460|0",
        "2026|2083|1|11461|1",
        "2026|2092|6|11461|0",
    ],
    "LsrsOnly.txt": [
        "26-2083|11461|1272|2026|Prime|SB632|S|relative to a certain highway sign in Concord.",
        "26-2092|926|1281|2026|Sponsor|SB647|S|authorizing the department of insurance to participate"
        " in a cooperative procurement group via an intergovernmental agreement for a prescription dr"
        "ug discount program.",
        "26-2092|928|1281|2026|Sponsor|SB647|S|authorizing the department of insurance to participate"
        " in a cooperative procurement group via an intergovernmental agreement for a prescription dr"
        "ug discount program.",
        "26-2092|9406|1281|2026|Sponsor|SB647|S|authorizing the department of insurance to participat"
        "e in a cooperative procurement group via an intergovernmental agreement for a prescription d"
        "rug discount program.",
        "26-2092|9839|1281|2026|Sponsor|SB647|S|authorizing the department of insurance to participat"
        "e in a cooperative procurement group via an intergovernmental agreement for a prescription d"
        "rug discount program.",
        "26-2092|11458|1281|2026|Prime|SB647|S|authorizing the department of insurance to participate"
        " in a cooperative procurement group via an intergovernmental agreement for a prescription dr"
        "ug discount program.",
        "26-2092|11461|1281|2026|Sponsor|SB647|S|authorizing the department of insurance to participa"
        "te in a cooperative procurement group via an intergovernmental agreement for a prescription "
        "drug discount program.",
        "26-2136|9856|1327|2026|Sponsor|SB532|S|increasing the requirements of the education freedom "
        "savings account oversight committee and modifying the purpose of the committee.",
        "26-2136|10599|1327|2026|Sponsor|SB532|S|increasing the requirements of the education freedom"
        " savings account oversight committee and modifying the purpose of the committee.",
        "26-2136|10600|1327|2026|Prime|SB532|S|increasing the requirements of the education freedom s"
        "avings account oversight committee and modifying the purpose of the committee.",
        "26-2187|43|1386|2026|Prime|SB633|S|(New Title) relative to donations received by the granite"
        " patron of the arts fund.",
        "26-2187|926|1386|2026|Sponsor|SB633|S|(New Title) relative to donations received by the gran"
        "ite patron of the arts fund.",
        "26-2187|8747|1386|2026|Sponsor|SB633|S|(New Title) relative to donations received by the gra"
        "nite patron of the arts fund.",
        "26-2187|9406|1386|2026|Sponsor|SB633|S|(New Title) relative to donations received by the gra"
        "nite patron of the arts fund.",
        "26-2187|9856|1386|2026|Sponsor|SB633|S|(New Title) relative to donations received by the gra"
        "nite patron of the arts fund.",
        "26-2187|10599|1386|2026|Sponsor|SB633|S|(New Title) relative to donations received by the gr"
        "anite patron of the arts fund.",
        "26-2187|10604|1386|2026|Sponsor|SB633|S|(New Title) relative to donations received by the gr"
        "anite patron of the arts fund.",
        "26-2187|11460|1386|2026|Sponsor|SB633|S|(New Title) relative to donations received by the gr"
        "anite patron of the arts fund.",
    ],
    "legislators.txt": [
        "11461|Reardon|Tara||S||7|15|D||||NH||senator.11461@example.gov",
        "11460|McGough|Tim||S||6|11|R|107 North Main Street|State House, Room 105-A|Concord|NH|03301|"
        "senator.11460@example.gov",
        "11462|Sullivan|Victoria||S||6|18|R||||NH||senator.11462@example.gov",
        "11463|Long|Pat||S||6|20|D|25 Capitol Street|State House Annex, Room 239F|Concord|NH|03301|se"
        "nator.11463@example.gov",
        "11459|McConkey|Mark||S||2|3|R|107 North Main Street|State House, Room 107|Concord|NH|03301|s"
        "enator.11459@example.gov",
        "11458|Rochefort|David||S||5|1|R||||NH||senator.11458@example.gov",
        "9406|Rosenwald|Cindy||S||6|13|D||||NH||senator.9406@example.gov",
        "926|Birdsell|Regina||S||8|19|R||||NH||senator.926@example.gov",
        "35|Carson|Sharon|M.|S||8|14|R|107 North Main Street|State House, Room 302|Concord|NH|03301|s"
        "enator.35@example.gov",
        "8739|Gray|James|P.|S||9|6|R|107 North Main Street|State House, Room 105|Concord|NH|03301|sen"
        "ator.8739@example.gov",
        "8747|Innis|Daniel|E.|S||1|7|R||||NH||senator.8747@example.gov",
        "43|Watters|David|H.|S||9|4|D|25 Capitol Street|State House Annex, Room 228|Concord|NH|03301|"
        "senator.43@example.gov",
        "9839|Prentiss|Suzanne|M.|S||5|5|D|25 Capitol Street|State House Annex, Room 236|Concord|NH|0"
        "3301|senator.9839@example.gov",
        "9856|Perkins Kwoka|Rebecca||S||8|21|D||||NH||senator.9856@example.gov",
        "9845|Ricciardi|Denise||S||3|9|R||||NH||senator.9845@example.gov",
        "10599|Fenton|Donovan||S||3|10|D||||NH||senator.10599@example.gov",
        "10698|Murphy|Keith|R.|S||6|16|R||||NH||senator.10698@example.gov",
        "10604|Pearl|Howard||S||7|17|r||||NH||senator.10604@example.gov",
        "10607|Abbas|Daryl||S||8|22|R||||NH||senator.10607@example.gov",
        "10600|Altschiller|Debra||S||8|24|D||||NH||senator.10600@example.gov",
        "928|Avard|Kevin|A.|S||6|12|R||||NH||senator.928@example.gov",
        "8740|Ward|Ruth||S||3|8|R||||NH||senator.8740@example.gov",
        "8745|Gannon|Bill|M.|S||8|23|R||||NH||senator.8745@example.gov",
        "10595|Lang|Timothy||S||1|2|R||||NH||senator.10595@example.gov",
    ],
    "RollCallSummary.txt": [
        "2026|S|45|3/12/2026 12:00:00 AM|SB566|24|0|24|0|||Ought to Pass|relative to recruiting incen"
        "tive programs for the national guard.||3/12/2026 3:10:53 PM",
        "2026|S|46|3/26/2026 12:00:00 AM|HB1815|16|8|24|0|||Ought to Pass|relative to education finan"
        "cing.||3/26/2026 3:44:54 PM",
        "2026|S|47|3/26/2026 12:00:00 AM|CACR13|23|1|24|0|||Ought to Pass|relating to registers of pr"
        "obate. Providing that the office of register of probate and all references to such office be"
        " eliminated.||3/26/2026 3:46:32 PM",
        "2026|S|48|3/26/2026 12:00:00 AM|SB441|16|8|24|0|||Floor Amendment|(New Title) relative to th"
        "e financial responsibility for local assistance and enabling municipalities to request a hea"
        "ring regarding the residency of an assisted person.||3/26/2026 3:47:31 PM",
        "2026|S|49|3/26/2026 12:00:00 AM|SB655|24|0|24|0|||Ought to Pass w/Amendment|(New Title) rela"
        "tive to employee leasing companies, workers' compensation coverage options, and a minimum wa"
        "ge exemption for minor league baseball players.||3/26/2026 3:48:57 PM",
        "2026|S|50|3/26/2026 12:00:00 AM|CACR11|23|1|24|0|||Ought to Pass w/Amendment|(New Title) rel"
        "ating to sheriffs. Providing that  there shall be no age limitation for a person to hold the"
        " office of county sheriff.||3/26/2026 3:51:25 PM",
        "2026|S|51|3/26/2026 12:00:00 AM|SB476|16|8|24|0|||Ought to Pass w/Amendment|relative to cons"
        "umer health care cost transparency.||3/26/2026 3:53:24 PM",
        "2026|S|52|3/26/2026 12:00:00 AM|SB459|15|9|24|0|||Reconsideration|(New Title) exempting clas"
        "sification of individuals based on biological sex from the definition of an unlawful discrim"
        "inatory practice in certain limited circumstances.||3/26/2026 3:55:40 PM",
    ],
    "RollCallHistory.txt": [
        "2026|S|49|209076|35|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|209091|43|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|209099|928|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|209101|926|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|209106|9406|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218739|8739|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218740|8740|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218745|8745|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218747|8747|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218751|9839|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218752|9845|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218754|9856|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218756|10595|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218757|10599|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218758|10698|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218759|10604|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218760|10607|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218761|10600|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218762|11458|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218763|11459|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218764|11460|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218765|11461|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218766|11462|SB655|Yea|3/26/2026 3:48:57 PM",
        "2026|S|49|218767|11463|SB655|Yea|3/26/2026 3:48:57 PM",
    ],
}


def _workflows():
    return sorted(_SWITCHED.workflow_dir.glob("*.yml")) + sorted(_SWITCHED.workflow_dir.glob("*.yaml"))


def _wf_block(lines, key):
    """The lines under a top-level `key:`, up to the next top-level key."""
    out, inside = [], False
    for ln in lines:
        if re.match(rf"^{re.escape(key)}:", ln):
            inside = True
            out.append(ln)
            continue
        if inside and ln and not ln[0].isspace() and not ln.startswith("#"):
            break
        if inside:
            out.append(ln)
    return out


def _wf_jobs(text):
    """{job: its lines}, for jobs two spaces in under a top-level `jobs:`."""
    jobs, cur = {}, None
    for ln in _wf_block(text.splitlines(), "jobs")[1:]:
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", ln)
        if m:
            cur = m.group(1)
            jobs[cur] = []
        elif cur is not None:
            jobs[cur].append(ln)
    return jobs


def _wf_steps(job_lines):
    """Each step's lines: the items six spaces in under the job's `steps:`."""
    steps, cur, inside = [], None, False
    for ln in job_lines:
        if re.match(r"^    steps:\s*$", ln):
            inside = True
            continue
        if inside and re.match(r"^    \S", ln):
            inside = False
        if not inside:
            continue
        if ln.startswith("      - "):
            cur = [ln]
            steps.append(cur)
        elif cur is not None:
            cur.append(ln)
    return steps


def _wf_code(lines):
    return [ln for ln in lines if not ln.lstrip().startswith("#")]

# EVERY KIND OF RUN, AND WHAT EACH MUST BE (7 October 2026). For each
# workflow: the run's event, its ref, the boxes as given (an input left out is
# null, as every input is on a schedule), whether it is a dry run, and its
# title on the Actions tab. A scheduled run is always main's; a run by hand
# of any other branch is a dry run whatever its boxes say, and its title
# says why where the Dry run box was unticked.
_HAND = {"dry_run": True, "fetch": False, "preview": True, "new_term": False}
WF_RUNS = {
    "nightly.yml": [
        ("schedule", MAIN_REF, {}, False, "nightly (scheduled)"),
        ("workflow_dispatch", MAIN_REF, _HAND, True, "nightly (dry run)"),
        ("workflow_dispatch", MAIN_REF, dict(_HAND, dry_run=False), False,
         "nightly (by hand, may publish)"),
        ("workflow_dispatch", "refs/heads/dev", _HAND, True, "nightly (dry run)"),
        ("workflow_dispatch", "refs/heads/dev", dict(_HAND, dry_run=False, fetch=True), True,
         "nightly (dry run: not main)"),
        ("workflow_dispatch", "refs/heads/dev", dict(_HAND, dry_run=False, fetch=True,
                                                     new_term=True), True,
         "nightly (by hand, new term: refused, not main)"),
        ("workflow_dispatch", MAIN_REF, dict(_HAND, dry_run=False, fetch=True, new_term=True),
         False, "nightly (by hand, new term)"),
        ("workflow_dispatch", MAIN_REF, dict(_HAND, fetch=True, new_term=True), True,
         "nightly (by hand, new term: refused, its page says which boxes)"),
        # The night's timer (workers/night-timer): the scheduled night's boxes
        # and its own, through GitHub's API (25 October 2026).
        ("workflow_dispatch", MAIN_REF, dict(_HAND, dry_run=False, fetch=True, timer=True), False,
         "nightly (scheduled, by the timer)"),
    ],
    # The weekly has no Dry run box: only its branch makes a run of it a dry run.
    "weekly.yml": [
        ("schedule", MAIN_REF, {}, False, "weekly (scheduled)"),
        ("workflow_dispatch", MAIN_REF, {"fetch": True, "new_term": False}, False,
         "weekly (by hand, fetching)"),
        ("workflow_dispatch", MAIN_REF, {"fetch": False, "new_term": False}, False,
         "weekly (by hand, no fetch)"),
        ("workflow_dispatch", MAIN_REF, {"fetch": True, "new_term": True}, False,
         "weekly (by hand, fetching, new term)"),
        ("workflow_dispatch", MAIN_REF, {"fetch": False, "new_term": True}, False,
         "weekly (by hand, new term without the fetch: refused)"),
        ("workflow_dispatch", "refs/heads/dev", {"fetch": True, "new_term": False}, True,
         "weekly (dry run: not main, fetching)"),
        ("workflow_dispatch", "refs/heads/dev", {"fetch": False, "new_term": False}, True,
         "weekly (dry run: not main, no fetch)"),
        ("workflow_dispatch", "refs/heads/dev", {"fetch": True, "new_term": True}, True,
         "weekly (dry run: not main, new term: refused)"),
    ],
}

_GH_TOKEN = re.compile(r"\s*(?:(\|\||&&|==|!=|!|\(|\))|('(?:[^']|'')*')|([A-Za-z_][\w.\-]*)"
                       r"|(-?\d+(?:\.\d+)?))")


def _gh_eval(expr, ctx):
    """A GitHub Actions expression, as GitHub evaluates it -- the part the
    workflows use: literals, context paths, (), !, == and !=, && and ||, and
    always(), success() and failure() -- so that a check can read what a line
    does in each kind of run, not only what it says. `ctx` maps a path
    ("inputs.dry_run", "env.DRY_RUN") to its value; a path it does not hold
    is null, as every input is on a schedule. A status function is true (the
    step was reached) unless `ctx` says otherwise. && and || return one of
    their operands, as GitHub's do; strings compare without case, and values
    of two types compare as numbers, as GitHub's docs say."""
    expr = expr.strip()
    if expr.startswith("${{") and expr.endswith("}}"):
        expr = expr[3:-2]
    toks, i, s = [], 0, expr.rstrip()
    while i < len(s):
        m = _GH_TOKEN.match(s, i)
        if not m or m.end() == i:
            raise ValueError(f"an expression this cannot read, at {s[i:i + 30]!r}")
        op, lit, name, num = m.groups()
        if op:
            toks.append(("op", op))
        elif lit is not None:
            toks.append(("lit", lit[1:-1].replace("''", "'")))
        elif name is not None:
            toks.append(("lit", {"true": True, "false": False, "null": None}[name])
                        if name in ("true", "false", "null") else ("name", name))
        else:
            toks.append(("lit", float(num)))
        i = m.end()
    at = [0]

    def peek():
        return toks[at[0]] if at[0] < len(toks) else (None, None)

    def take():
        t = peek()
        at[0] += 1
        return t

    def truthy(v):
        return not (v is None or v is False or v == "" or (type(v) is float and v == 0))

    def number(v):
        if v is None or v is False:
            return 0.0
        if v is True:
            return 1.0
        if isinstance(v, float):
            return v
        try:
            return float(v.strip()) if v.strip() else 0.0
        except ValueError:
            return float("nan")

    def same(a, b):
        if type(a) is type(b):
            return a.lower() == b.lower() if isinstance(a, str) else a == b
        return number(a) == number(b)

    def either():
        v = both()
        while peek() == ("op", "||"):
            take()
            r = both()
            v = v if truthy(v) else r
        return v

    def both():
        v = compare()
        while peek() == ("op", "&&"):
            take()
            r = compare()
            v = r if truthy(v) else v
        return v

    def compare():
        v = unary()
        while peek() in (("op", "=="), ("op", "!=")):
            op = take()[1]
            r = unary()
            v = same(v, r) if op == "==" else not same(v, r)
        return v

    def unary():
        if peek() == ("op", "!"):
            take()
            return not truthy(unary())
        return primary()

    def primary():
        kind, val = take()
        if (kind, val) == ("op", "("):
            v = either()
            if take() != ("op", ")"):
                raise ValueError(f"an unclosed ( in {expr!r}")
            return v
        if kind == "lit":
            return val
        if kind == "name":
            if peek() == ("op", "("):
                take()
                if take() != ("op", ")") or val not in ("always", "success", "failure",
                                                        "cancelled"):
                    raise ValueError(f"{val}(...) in {expr!r}, which this does not evaluate")
                # Reached, and not cancelled, unless `ctx` says otherwise.
                return ctx.get(f"{val}()", val != "cancelled")
            return ctx.get(val)
        raise ValueError(f"{val!r} where a value belongs in {expr!r}")
    v = either()
    if at[0] != len(toks):
        raise ValueError(f"more after the end of {expr!r}")
    return v


def _gh_render(text, ctx):
    """A value with ${{ }} in it, as GitHub writes it out: an env value or a
    run's title."""
    def one(m):
        v = _gh_eval(m.group(1), ctx)
        return ("true" if v is True else "false" if v is False else "" if v is None
                else str(int(v)) if isinstance(v, float) and v == int(v) else str(v))
    return re.sub(r"\$\{\{(.*?)\}\}", one, text, flags=re.S)


def _wf_value(lines, key):
    """A top-level env entry's or the run-name's value as one line: a folded
    run-name (>-) joined by spaces, as YAML folds it."""
    block = _wf_block(lines, key) if key == "run-name" else \
        [ln for ln in _wf_block(lines, "env") if re.match(rf"^  {re.escape(key)}:", ln)]
    if not block:
        return None
    first = block[0].split(":", 1)[1].strip()
    if key == "run-name" and first in (">-", ">"):
        return " ".join(ln.strip() for ln in _wf_code(block[1:]) if ln.strip())
    return first


def _wf_dry_run_sets(text):
    """Every place a workflow sets DRY_RUN, as one list: the top-level env's
    line where that is the only one; otherwise each place, named.

    THE REVIEW OF 7 OCTOBER 2026. The checks read a setting only in block
    style, "DRY_RUN:" at the start of a line, and a job's flow-style env --
    env: {DRY_RUN: "false"} -- which GitHub lets override the workflow's for
    every step of the job and for env.DRY_RUN in their ifs, passed all three
    of them. So a key named DRY_RUN is found wherever it is and however it is
    written: in any mapping of the parsed file (PyYAML, where installed), and
    in any line that is not a comment, block or flow style, quoted or not;
    and so is a script's assignment of it ("DRY_RUN=..." for GITHUB_ENV, or
    $env:DRY_RUN = ...), which would change it for the steps after."""
    lines = _wf_code(text.splitlines())
    keys = [ln.strip() for ln in lines
            if re.search(r"""(?<![\w$.:-])["']?DRY_RUN["']?\s*:(?!:)""", ln)]
    sets = [ln.strip() for ln in lines if re.search(r"""DRY_RUN["']?\s*=(?!=)""", ln)]
    try:
        import yaml
    except ImportError:
        yaml = None
    where = []
    if yaml is not None:
        def walk(node, path):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k == "DRY_RUN":
                        where.append("/".join(path + ["DRY_RUN"]))
                    walk(v, path + [str(k)])
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, path + [str(i)])
        walk(yaml.safe_load(text), [])
    top = [ln for ln in _wf_block(text.splitlines(), "env") if re.match(r"^  DRY_RUN:", ln)]
    if len(keys) == 1 and not sets and where in ([], ["env/DRY_RUN"]) and \
            [ln.strip() for ln in top] == keys:
        return keys
    return keys + [f"sets it in a script: {s}" for s in sets] + \
        [f"parsed at {w}" for w in where if w != "env/DRY_RUN"]


def _wf_run_ctx(event, ref, boxes):
    return {"github.event_name": event, "github.ref": ref,
            **{f"inputs.{k}": v for k, v in boxes.items()}}


def _gh_unwrap(cond):
    cond = cond.strip()
    return cond[3:-2].strip() if cond.startswith("${{") and cond.endswith("}}") else cond


def _wf_job_heads(job_lines):
    """(the jobs a job needs, its if as written or ""), from its own lines."""
    code = _wf_code(job_lines)
    need = next((m.group(1) for ln in code for m in [re.match(r"^    needs:\s*(.+?)\s*$", ln)] if m), "")
    cond = next((m.group(1) for ln in code for m in [re.match(r"^    if:\s*(.+?)\s*$", ln)] if m), "")
    return [x.strip() for x in need.strip("[]").split(",") if x.strip()], cond


def _member_surnames():
    """Every surname the record knows a member by, in lower case, the last word
    of each: careers.json's, the roster's and the two lists of members who have
    left. Empty where none of them is here."""
    out = set()
    for f, pick in ((Path("generated/careers.json"), lambda d: [v.get("last") for v in d.values()]),
                    (Path("data/legislators.json"), lambda d: [v.get("last") for v in d]),
                    (Path("former_members.json"), lambda d: [v.get("name") for v in d.values()]),
                    (Path("past_members.json"), lambda d: list(d.values()))):
        try:
            names = pick(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError, AttributeError, TypeError):
            continue
        for n in names:
            n = re.sub(r"^(?:Rep|Sen)\.\s+", "", str(n or "")).split(",")[0].split("(")[0].strip()
            if n:
                out.add(n.split()[-1].lower())
    return out


def _one_edit(a, b):
    """Whether two different words are one letter apart: one changed, added or
    dropped."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def _speakers_against_journal(root, jroot):
    """([what the journal contradicts], motions held) for the House pages
    under root/H against the journal files under jroot
    (_every_speaker_where_the_journal_decides)."""
    import bisect
    import html as _html
    import journal_days as J
    # A bill's card and its votes' lines since 10 October 2026: "<b>184–157</b>
    # on a roll call".
    art = re.compile(r'<article class="card"[^>]*>(.*?)</article>', re.S)
    bill_rx = re.compile(r'class="cnum"[^>]*>([^<]+)<')
    tal = re.compile(r"<b>(?P<y>\d+)\u2013(?P<n>\d+)</b> on a (?P<k>roll call|division)")
    spk = re.compile(r'<p class="sspoke(?: sother)?"><span class="slab">([^<]+)</span>(.*?)</p>',
                     re.S)
    mover_spoke = re.compile(r'<p class="dvby">Moved by (.*?), who spoke for it, urging a yes '
                             r'vote\.</p>', re.S)

    def names_of(h):
        h = re.sub(r'<span class="snote">.*?</span>', "", h, flags=re.S)
        # a person chip's "(R - Rock 14)" is no name
        h = re.sub(r'<span class="mtag">.*?</span>', "", h, flags=re.S)
        # and the surname is the chip's last word but a suffix ("Rep. Robert
        # Christie Jr." is Christie, as the journal names him), read without
        # its case: the roster's "MacKenzie" is the journal's "Mackenzie"
        return [[w for w in _html.unescape(n).strip(" ,").replace("Rep. ", "").split()
                 if w not in ("Jr.", "Jr", "Sr.", "Sr", "II", "III", "IV")][-1].lower()
                for n in re.sub(r"<[^>]+>", "\x00", h).split("\x00") if n.strip(" ,")]

    def base(b):
        return (b or "").split("-")[0].upper()

    def motions(h):
        out = []
        for a in art.finditer(h):
            a = a.group(1)
            m = bill_rx.search(a)
            bill = re.sub(r"\s+", "", _html.unescape(m.group(1))).upper() if m else ""
            also = {n for s in spk.finditer(a) if s.group(1).startswith("Also")
                    for n in names_of(s.group(2))}
            for mo in a.split('<div class="dvote"')[1:]:
                t = tal.search(mo)
                sides = {("for" if " for " in s.group(1) else "against"): names_of(s.group(2))
                         for s in spk.finditer(mo) if not s.group(1).startswith("Also")}
                # The mover who was the one speaker, said in the mover's line
                # (build_session_pages.MOVER_SPOKE, 25 October 2026): a
                # speaker for the motion, as a row of one would have named.
                ms = mover_spoke.search(mo)
                if ms:
                    sides.setdefault("for", []).extend(
                        names_of(re.sub(r"\s*\([^)]*\)\s*$", "", re.sub(r"<[^>]+>", "", ms.group(1)))))
                out.append({"bill": bill, "rc": bool(t) and t.group("k") == "roll call",
                            "count": (int(t.group("y")), int(t.group("n"))) if t else None,
                            "sides": sides, "also": also,
                            "skip": any(w in mo for w in (
                                "Printed in the journal with this session day", "Done in the recess",
                                "The docket has no line for this vote"))})
        return out

    years = {}

    def blocks(date):
        if date[:4] not in years:
            got = {}
            for f in sorted((jroot / date[:4]).glob("*.txt")):
                raw = f.read_text(encoding="utf-8", errors="replace")
                for iso, b in J.day_blocks(J.clean(raw, lines=True)):
                    got.setdefault(iso, []).append(b)
            years[date[:4]] = got
        return years[date[:4]].get(date, [])

    def read(block):
        text = re.sub(r"(?<!\n)\n(?!\n)", " ", block)
        marks = J.bill_marks(block)
        ev = [("tally", m.start(), (int(m.group("yeas")), int(m.group("nays"))), m.end())
              for m in J.TALLY.finditer(block)]
        ev += [("division", m.start(), (int(m.group("yeas")), int(m.group("nays"))), m.end())
               for m in J.DIVISION.finditer(block)]
        # EACH PATTERN WHERE IT CAN BEGIN (29 October 2026): decisions() and
        # found() give finditer's own list (_speakers_check_found holds these
        # three classes to their patterns), and finditer from every character
        # of every House day was 20 of this check's 53 seconds on the night.
        ev += [("voice", m.start("s"), re.sub(r"\s+", " ", m.group("s")), m.end("s"))
               for m in J.decisions(text) if not J.NOT_DECIDED.search(m.group("s"))]
        for m in J.found(J.MOTION_EVENT, text, "[MmOoAaCcWwRr]"):
            w = J.MOVED_SINCE.match(block, m.start()) if m.group(0).lower() == "moved" else None
            ev.append(("move", m.start(), re.sub(r"\s+", " ", w.group(0) if w else m.group(0)),
                       w.end() if w else m.end()))
        ev.sort(key=lambda e: e[1])
        side = lambda m: "for" if "favor" in m.group("side").lower() else "against"
        sp = [(m.start(), J.SPOKE_END.search(text, m.start()).end(), side(m),
               J._names(m.group("names"))) for m in J.found(J.SPOKE, text, "[Rr]")]
        sp += [(m.start(), J.SPOKE_END.search(text, m.start()).end(), side(m),
                J._names(m.group("name"))) for m in J.found(J.MOVED_SPOKE, text, "[Rr]")]

        def bill_at(pos):
            cur = None
            for at, b in marks:
                if at > pos:
                    break
                cur = b
            return base(cur)

        def end_of(pos):
            return next((at for at, _b in marks if at > pos), len(block))
        return text, ev, sp, bill_at, end_of

    plain_verdict = re.compile(r"^(?:(?:the\s+)?motion\s+(?:was\s+)?)?(?:adopted|failed|carried|"
                               r"lost)\b[^.]{0,20}\.?$", re.I)

    def lands(text, ev, starts, start, stop):
        """The decision of the question pending at `start`, "END" where the
        journal decides nothing after it in the bill, or None where another
        question was put first."""
        pend, put = None, 0
        for e in ev[bisect.bisect_left(starts, start):]:
            k, at, v, end = e
            if at >= stop:
                break
            if pend and re.search(r"\bruled\b[^.]{0,80}\bout\s+of\s+order", text[put:at], re.I):
                pend = None
            if k == "move":
                if re.match(r"moved\s+(?:a|the)\s+call\s+of\s+the\s+house", v, re.I):
                    continue
                if pend and re.match(r"withdrew\s+\w+\s+motion", v, re.I):
                    pend = None
                    continue
                if pend:
                    return None
                put = end
                if re.match(r"moved\s+(?:the\s+)?previous\s+question|moved\s+to\s+limit\s+debate",
                            v, re.I):
                    pend = "pq"
                elif re.match(r"moved\s+that\s+.{0,300}?\bbe\s+printed", v, re.I | re.S):
                    pend = "print"
                elif v.lower().startswith("moved") and re.search(
                        r"on\s+the\s+table|\btable[ds]?\b|postpon|special\s+order|re-?\s*commit|"
                        r"re-?\s*refer|referred|interim\s+study|divided", v, re.I) and not re.search(
                        r"reconsider|concur|from\s+the\s+table|vacate|suspend|recess|adjourn", v,
                        re.I):
                    pend = "aside"
                else:
                    return None
                continue
            plain = k == "voice" and plain_verdict.match(v)
            if pend == "pq":
                said = text[at:end + 300].split(".")[0] if k == "division" else str(v)
                if plain or re.search(r"previous\s+question|limit\w*\s+debate|debate\s+(?:now\s+)?be"
                                      r"\s+limited", text[put:at] + " " + said, re.I):
                    pend = None
                    continue
                return None
            if pend == "print":
                pend = None
                if re.search(r"question\s+(?:now\s+)?being", text[put:at], re.I):
                    return e
                if plain:
                    continue
                return None
            if pend == "aside":
                if k == "voice":
                    lost = re.search(r"failed|lost|defeated", v, re.I)
                elif k == "division":
                    said = text[end:end + 200].split(".")[0]
                    lost = re.search(r"failed|lost|defeated", said, re.I) or (
                        not re.search(r"adopted|prevailed|carried", said, re.I) and v[0] < v[1])
                else:
                    lost = v[0] < v[1]
                if not lost:
                    return None
                pend = None
                continue
            return e
        return "END" if pend is None else None

    def near(a, b):
        return abs(a[0] - b[0]) <= 1 and abs(a[1] - b[1]) <= 1

    bad, held = [], 0
    # A SLIP OF THE JOURNAL'S IS SAID, NOT FAILED (the person, 15 October
    # 2026: "I don't want our website to stop working because of a typo in the
    # official record, but we should still flag it"). The House Journal of
    # 9 April 2026 prints "Reps. Poloszaj, Terry, Comtois and St. Clair spoke
    # against" for Rep. Tom Ploszaj, whom the page names. A journal surname no
    # member of the record has ever had, one letter from a member's the page
    # names, is that member; each is returned to be said in the check's
    # message, and goes on the clerk's list.
    known, slips = _member_surnames(), set()

    def same(j, n, where):
        if j == n:
            return True
        if known and j not in known and n in known and _one_edit(j, n):
            slips.add(f"{j.capitalize()} for {n.capitalize()} ({where})")
            return True
        return False

    for p in sorted((root / "H").glob("*.html")):
        date = p.stem
        bl = blocks(date)
        if not bl:
            continue
        mots = motions(p.read_text(encoding="utf-8"))
        an = [read(b) for b in bl]
        landed = []
        for i, (text, ev, sp, bill_at, end_of) in enumerate(an):
            starts = [e[1] for e in ev]
            landed += [(i, s, bill_at(s[0]), lands(text, ev, starts, s[1], end_of(s[0])))
                       for s in sp]
        shared = Counter((base(m["bill"]), m["count"]) for m in mots if m["count"])
        per_bill = Counter(base(m["bill"]) for m in mots)
        for mo in mots:
            b, c = base(mo["bill"]), mo["count"]
            if not b or not c or mo["skip"] or shared[(b, c)] > 1:
                continue
            # the clerk's count one off the ballots, where no other motion of
            # the bill is drawn with it
            exact = {m["count"] for m in mots if base(m["bill"]) == b}
            prints = [(i, e) for i, (_t, ev, _s, bill_at, _e) in enumerate(an) for e in ev
                      if e[0] in ("tally", "division") and bill_at(e[1]) == b
                      and (e[2] == c or (e[0] == "tally" and mo["rc"] and near(e[2], c)
                                         and e[2] not in exact))]
            if len(prints) != 1:
                continue
            held += 1
            i, P = prints[0]
            landing = [s for j, s, sb, at in landed if j == i and sb == b and at == P]
            ended = [s for _j, s, sb, at in landed if sb == b and at == "END"] \
                if per_bill[b] == 1 else []
            where = f"H {date} {mo['bill']}"
            for side, names in mo["sides"].items():
                for n in names:
                    if not any(s[2] == side and any(same(x.split()[-1].lower(), n, where)
                                                    for x in s[3])
                               for s in landing + ended):
                        bad.append(f"H {date} {mo['bill']} {c[0]}-{c[1]}: {n} ({side}) is named, "
                                   "and the journal decides no speech of theirs there")
            # Named on it, or under "also spoke" where the journal has the
            # member speaking on both sides of it, which the page never says.
            named = {(side, n) for side, ns in mo["sides"].items() for n in ns}
            both = ({x.split()[-1].lower() for s in landing if s[2] == "for" for x in s[3]}
                    & {x.split()[-1].lower() for s in landing if s[2] == "against" for x in s[3]})
            for s in landing:
                for x in s[3]:
                    sur = x.split()[-1].lower()
                    if (s[2], sur) not in named and not (sur in both and sur in mo["also"]):
                        if any(sd == s[2] and same(sur, nn, where) for sd, nn in named):
                            continue
                        bad.append(f"H {date} {mo['bill']} {c[0]}-{c[1]}: {x} ({s[2]}) spoke on it "
                                   "and is " + ("named only as having spoken during the bill"
                                                if sur in mo["also"] else "named nowhere on it"))
    return bad, held, sorted(slips)


# "Rep." or "Sen." as a word of a sponsor's name. The chamber is a field of the row and never
# part of the name; \b on both sides keeps Larsen, Senter and Repass names.
SPONSOR_HONORIFIC = re.compile(r"\b(?:Rep|Sen)s?\b\.?", re.I)


# ============================================================= members-elect ==
#
# WHO NOVEMBER'S ELECTION SENT, UNTIL THEY SIT (the person's decisions of 16
# October 2026; private/MEMBERS_ELECT_PLAN.md). src/parse/build_members_elect.py
# writes site/members_elect.json, the one file the pages will draw a
# member-elect from, and the rules it holds are each one a page could break
# quietly: written only between the election and Organization Day while the
# site's newest term is the one before theirs; a winner linked to a page only
# on a certain match; the roster files left byte for byte; the person's file
# read and never written; every race adding up to its seats. These hold them
# on a copy of the fixture's built site, with tests/election_fixture.json as
# its results and three former members added to its former.json -- not to
# _site_fixture, whose page counts other checks hold. The pages that draw the
# file are a later pass, and its checks with them.

_ELECT_SOURCE = b"A stand-in for the Secretary of State's results, for preflight's fixture.\n"
# A day between the fixture's election, 3 November 2026, and Organization Day.
_ELECT_IN = "2026-11-20"


def _elect_former(sur, first, mid, county, district, slug):
    """A former representative's row, in the shape build_site_v2 writes
    former.json."""
    abbr = {"Rockingham": "Rock", "Belknap": "Belk"}.get(county, county)
    label = f"Rep. {first} {sur}"
    return {"id": mid, "name": f"{sur}, {first}", "chamber": "H", "party": "R",
            "county": county, "county_abbr": abbr, "district": district, "label": None,
            "email": "", "url": None, "url_past": None, "towns": [], "committees": [],
            "title": None, "phone": "", "seat": "", "display_plain": label,
            "display": f"{label} (R)", "display_full": f"{label} (R - {abbr} {district})",
            "district_label": f"{abbr} {district}", "sort": f"{sur.lower()}, {first.lower()}",
            "n_votes": 0, "counts": {}, "n_sponsored": 0, "slug": slug, "former": True,
            "served": {"first": "1/4/2017", "last": "6/30/2022", "terms": ["2017-2018"]}}


# Michael Vose, the one former member of his name, of Rockingham: returning,
# and linked. Two John Smiths, both of Rockingham: a name the rule cannot
# settle, until the person's file says which.
_ELECT_FORMER = [
    _elect_former("Vose", "Michael", "900001", "Rockingham", "5", "michael-vose-rock-5"),
    _elect_former("Smith", "John", "900002", "Rockingham", "3", "john-smith-rock-3"),
    _elect_former("Smith", "John", "900003", "Rockingham", "20", "john-smith-rock-20")]

# The fixture's recount deadline, made up like the rest of its election: a
# day between the election and _ELECT_IN, so that on _ELECT_IN every race the
# person has not held back is final (the person's rule, 16 October 2026: final
# once posted and past the recount deadline, or once recounted).
_ELECT_DEADLINE = "2026-11-13"

# The person's file for the fixture's election: John Smith is 900002, Pat
# Newell is confirmed new, Danville's race is not final with a recount asked
# for, and Fremont's write-in winner is held off the pages. The reasons are
# private, and must never reach the site.
_ELECT_HAND = {"2026-11-03": {
    "recount_deadline": _ELECT_DEADLINE,
    "matches": {"H|Rockingham|13": {"John Smith": "900002"},
                "H|Rockingham|32": {"Pat Newell": None}},
    "not_final": {"H|Rockingham|8": {"recount": True, "why": "PRIVATE-NOT-FINAL"}},
    "held": {"H|Rockingham|7": {"Sam Wright": "PRIVATE-HELD"}}}}


def _elect_absent():
    """What the members-elect checks need and this folder lacks."""
    return [x for x in CHAIN_NEEDS + ["build_members_elect.py"] if not _paths.locate(x).exists()] \
        + [x for x in ("tests/election_fixture.json",) if not Path(x).exists()]


def _elect_fixture(root):
    """The fixture's built project in `root` (_fixture_site_whole), with the
    election's results in collected/, their saved source in records/sources/,
    and the three former members above in site/former.json. Returns site/."""
    _fixture_site_whole(root)
    site = root / "site"
    fp = site / "former.json"
    former = json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else []
    fp.write_text(json.dumps(former + _ELECT_FORMER), encoding="utf-8")
    (root / "collected").mkdir(exist_ok=True)
    shutil.copy2(Path("tests/election_fixture.json"), root / "collected" / "election_2026.json")
    src = root / "records" / "sources" / "sos-general-election-2026-fixture.txt"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(_ELECT_SOURCE)
    return site


def _elect_run(root, day, hand=None, err=False):
    """build_members_elect.py in `root` with its day stated, the person's
    file written first where one is given: (exit code, what it printed, the
    file it left in site/ or None) -- and, where `err`, what it printed on
    stderr alone after the rest."""
    if hand is not None:
        (root / "corrections").mkdir(exist_ok=True)
        (root / "corrections" / "members_elect.json").write_text(json.dumps(hand),
                                                                 encoding="utf-8")
    r = _run([sys.executable, _paths.script("build_members_elect.py")], cwd=root,
             capture_output=True, text=True, timeout=120, env={"GRANITE_BUILD_DATE": day})
    f = root / "site" / "members_elect.json"
    got = (r.returncode, (r.stdout or "") + (r.stderr or ""),
           json.loads(f.read_text(encoding="utf-8")) if f.exists() else None)
    return got + ((r.stderr or "",) if err else ())


def _elect_part(out, title):
    """One part of the step's report, from its title to the next blank line."""
    at = out.find(title)
    return "" if at < 0 else out[at:].split("\n\n")[0]


# ---- the pages that draw them (the pages' pass, 16 October 2026) -----------
#
# The town pages and places.json (with find.js's My Town card), the Officials
# page's sixth tab, a re-elected or returning member's own page (with
# app.js), and the district map's panel draw who the election sent, from
# site/members_elect.json alone, through build_members_elect.for_pages and
# the components elect_now, elect_race, elect_block and elect_line. The
# person's rules, which each of these holds: a member-elect is never drawn
# as sitting; a link goes to their own member's page and a new person has
# none; and nothing is drawn on Organization Day, before the election, or
# once the term is theirs. They read the fixture's election built twice --
# the step run and not -- with the four builders run again over each, once
# a run (_elect_built).

_ELECT_BASE = "https://graniterecord.org"
# The builders that draw a member-elect, in build_all's order. build_indexes
# and build_committees follow the step too (_elect_step_order) but draw no page
# of one: build_indexes gives the search its rows (find.json, elect_rows, held by
# _find_members_elect).
_ELECT_PAGES = (("build_pages.py", ["--out", "site"]),
                ("build_legislator_pages.py", ["--site", "site", "--base", _ELECT_BASE]),
                ("build_town_pages.py", ["--site", "site", "--base", _ELECT_BASE]),
                ("build_district_map.py", ["--site", "site"]))
# An element that is the members-elect's: whatever carries data-elect, whole.
_ELECT_TAG = re.compile(r"<([a-z][a-z0-9]*)\b[^>]*\sdata-elect\b[^>]*>")


def _elect_pages(root, day):
    """The four page builders run again over `root`'s built site, dated
    `day`. Returns what they printed."""
    said = []
    for script, args in _ELECT_PAGES:
        r = _run([sys.executable, _paths.script(script), *args], cwd=root, capture_output=True,
                 text=True, timeout=180, env={"GRANITE_BUILD_DATE": day})
        tail = (r.stderr or r.stdout or "").strip().splitlines()
        assert r.returncode == 0, (f"{script} dated {day} stopped: "
                                   + (tail[-1][:200] if tail else "no output"))
        said.append(r.stdout or "")
    return "\n".join(said)


def _elect_blocks(html):
    """[(start, end), ...]: each element of `html` that carries data-elect,
    its closing tag found by counting its own name in and out."""
    spans, i = [], 0
    while True:
        m = _ELECT_TAG.search(html, i)
        if not m:
            return spans
        tag = re.compile(r"<(/?)" + m.group(1) + r"\b[^>]*>")
        depth, j = 1, m.end()
        while depth:
            n = tag.search(html, j)
            assert n, f"an element with data-elect is never closed: {html[m.start():m.start() + 160]}"
            depth += -1 if n.group(1) else 1
            j = n.end()
        spans.append((m.start(), j))
        i = j


def _elect_strip(html):
    """`html` with every element carrying data-elect taken out whole, and a
    member page's GR_ELECT: what the page is once the members-elect are
    taken out of it."""
    out, i = [], 0
    for a, b in _elect_blocks(html):
        out.append(html[i:a])
        i = b
    return re.sub(r"window\.GR_ELECT=\{[^{}]*\};", "", "".join(out) + html[i:])


def _elect_built():
    """(with, without, the file, what the builders printed with it): two
    copies of the fixture's built site with the election's results and the
    person's file (_elect_fixture, _ELECT_HAND, which names winners and holds
    and marks races not final), the step run on _ELECT_IN in one and the file
    taken out of the other, and the four page builders run again over both,
    dated _ELECT_IN. Once a run, for reading only: a check that writes takes
    a copy."""
    def build():
        a, b = _shared_root("gr-elect-with-"), _shared_root("gr-elect-without-")
        _elect_fixture(a)
        code, out, doc = _elect_run(a, _ELECT_IN, hand=_ELECT_HAND)
        assert code == 0 and doc, f"the step wrote no file on {_ELECT_IN}: {out[-300:]}"
        shutil.copytree(a, b, dirs_exist_ok=True)
        (b / "site" / "members_elect.json").unlink()
        said = _elect_pages(a, _ELECT_IN)
        _elect_pages(b, _ELECT_IN)
        return a, b, doc, said
    return _once_a_run("the members-elect pages, with the file and without", build)


_ELECT_CARD_JS = r"""
require("./stub.js");
const fs = require("fs"), vm = require("vm");
vm.runInThisContext(fs.readFileSync("./find.js", "utf8"), { filename: "find.js" });
const F = vm.runInThisContext("({YT, ytSeats})");
const out = {};
for (const name of ["with", "without"]) {
  const d = JSON.parse(fs.readFileSync("./" + name + ".json", "utf8"));
  F.YT.data = d; out[name] = {};
  for (const p of d.places) out[name][p.s] = F.ytSeats(p);
}
process.stdout.write("\n@@" + JSON.stringify(out));
"""


def _elect_card(with_places, without_places):
    """{"with": {slug: html}, "without": {...}}: find.js's My Town card
    (ytSeats) for every place, drawn in node from each places.json, with
    components.js loaded first as every page loads it. None without node."""
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        assert not os.environ.get("GITHUB_ACTIONS"), "node is not on PATH on the nightly"
        return None
    root = Path(tempfile.mkdtemp(prefix="gr-elect-card-"))
    try:
        (root / "stub.js").write_text(_source("tests/dom_stub.js"),
                                      encoding="utf-8")
        (root / "find.js").write_text(_with_components(
            _source("src/pages/find.js")), encoding="utf-8")
        (root / "with.json").write_bytes(with_places.read_bytes())
        (root / "without.json").write_bytes(without_places.read_bytes())
        (root / "go.js").write_text(_ELECT_CARD_JS, encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, encoding="utf-8",
                 timeout=60)
        said = (r.stderr or r.stdout or "").strip()
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "find.js would not draw the My Town card in node: " + said[-300:])
        return json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ========================================================== the district map ==
#
# MAP V1 (9 October 2026): src/pages/map.js and map.css, a module a page
# mounts, drawing one file, /district_map.json, which build_district_map.py
# writes every night from generated/district_geometry.json (a person builds
# that from the GIS zips on the laptop and commits it), the district files,
# the roster and the officials file. The design is the person's, settled in
# private/design/polish/map_v2/ and the decisions of 8 and 9 October; these
# hold the parts of it a change could quietly undo: the label toggle and its
# default, labels that never overlap, every district filled from the record's
# party, and a geometry no older than its inputs.

def _map_data(roster=()):
    """/district_map.json as build_district_map.build() makes it, from the
    tracked files alone: the committed geometry, records/districts/ through
    parse_districts.combine() (which is what the night's site/districts.json
    is), the officials file, and `roster` for the members. None where one of
    them is not here."""
    import build_district_map as BDM
    import parse_districts as PD
    geom, off = Path("generated/district_geometry.json"), Path("corrections/officials.json")
    if not (geom.exists() and off.exists() and Path("records/districts/house.txt").exists()):
        return None
    districts = PD.combine("records/districts", say=lambda *a, **k: None)
    return BDM.build(geom.read_bytes(), districts, list(roster), _officials_now(off))


# THE CHAMBER STATEWIDE UNDER THE LEGEND (the owner, 7 November 2026: "on the
# map, a short list of the party totals for the chamber layer shown (Senate or
# House): Democrats, Republicans, Independents, statewide"). map.js mounted in
# node, as _map_legend_words mounts it, on each *.map.json here: its pure
# totals() and totalsLine() for every layer, and the line mount() draws under
# the legend as the layer switch goes State House, State Senate, Council, US
# House and back, in English and with the Spanish words a Spanish page carries
# (WORDS, from the catalog). And the markup: the line inside the legend's box,
# after the legend, and not there at all for a page that asks for none.
_MAP_TOTALS_JS = r"""
require("./stub.js");
globalThis.CSS = { escape: s => String(s) };
document.createElementNS = (ns, t) => document.createElement(t);
const fs = require("fs");
const G = require("./map.js");
const WORDS = JSON.parse(fs.readFileSync("./words.json", "utf8"));
function held() {
  const e = document.createElement("div"), q = {};
  e.querySelector = sel => (q[sel] = q[sel] || held());
  e.style.setProperty = () => {};
  return e;
}
(async () => {
  const out = {};
  for (const name of fs.readdirSync(".").filter(f => f.endsWith(".map.json")).sort()) {
    const T = JSON.parse(fs.readFileSync("./" + name, "utf8"));
    globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => T });
    const M = G.model(T), one = out[name] = { totals: {}, lines: {} };
    for (const lk of ["base", "senate", "exec", "cong", "county", "towns"]) {
      const t = G.totals(M, lk);
      one.totals[lk] = t; one.lines[lk] = G.totalsLine(t, lk);
    }
    for (const lang of ["en", "es"]) {
      globalThis.GR_WORDS = lang === "es" ? WORDS : {};
      const root = held();
      const api = G.mount(root, { labels: "none", zoom: false, layers: ["base", "senate", "exec", "cong"],
                                  data: "/" + name + "?" + lang });
      if (lang === "en") one.markup = root.innerHTML;
      await api.ready;
      const tot = root.querySelector(".gmtot"), drawn = [["base", tot.innerHTML]];
      for (const lk of ["senate", "exec", "cong", "base", "senate"]) {
        api.setLayer(lk); drawn.push([lk, tot.innerHTML]);
      }
      one["drawn_" + lang] = drawn;
    }
    globalThis.GR_WORDS = {};
    const none = held();
    G.mount(none, { labels: "none", zoom: false, totals: false, data: "/" + name + "?none" });
    one.markupNone = none.innerHTML;
  }
  process.stdout.write("\n@@" + JSON.stringify(out));
})().catch(e => { console.error(String(e && e.stack || e)); process.exit(1); });
"""


def _map_totals_run(maps):
    """{name: {"totals": {layer: totals() or None}, "lines": {layer: html},
    "drawn_en"/"drawn_es": [[layer, the line drawn]], "markup",
    "markupNone"}}: map.js in node on each of `maps` ({name: the map's data
    as a dict}). None without node."""
    import i18n
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        assert not os.environ.get("GITHUB_ACTIONS"), "node is not on PATH on the nightly"
        return None
    js = _source("src/pages/map.js")
    # the Spanish a Spanish page carries for map.js's words (i18n.words_js)
    words = {k: i18n.lookup("es", k, en) for k, en in i18n.tr_calls(js)}
    root = Path(tempfile.mkdtemp(prefix="gr-maptotals-"))
    try:
        (root / "stub.js").write_text(_source("tests/dom_stub.js"),
                                      encoding="utf-8")
        (root / "map.js").write_text(_with_components(js), encoding="utf-8")
        (root / "words.json").write_text(json.dumps({k: v for k, v in words.items() if v is not None}),
                                         encoding="utf-8")
        for name, data in maps.items():
            (root / f"{name}.map.json").write_text(json.dumps(data), encoding="utf-8")
        (root / "go.js").write_text(_MAP_TOTALS_JS, encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, encoding="utf-8",
                 timeout=180)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "map.js would not count the chambers in node: " + (r.stderr or r.stdout or "")[-300:])
        return {k[:-len(".map.json")]: v for k, v in json.loads(r.stdout.rsplit("@@", 1)[1]).items()}
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _map_totals_text(html):
    """The line as a reader reads it: no tags, entities read, spaces single."""
    import html as _h
    return re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]+>", "", html or ""))).strip()


# The 25 measures the General Court's own records hold and the search page
# left out, by where each one's record comes from. Counted by name, as the
# withdrawn bills above are: a step that dropped them would fall below every
# count the nightly guards.
_LEFT_OUT = {
    "database": [
        ("2005-2006", "HB3"), ("2007-2008", "HB633"), ("2007-2008", "SB267"),
        ("2009-2010", "HB87"), ("2009-2010", "HB134"), ("2009-2010", "HB1308"),
        ("2009-2010", "HB1582"), ("2009-2010", "HB1584"), ("2009-2010", "HB1587"),
        ("2011-2012", "HB523"), ("2011-2012", "HB547"), ("2011-2012", "HB1284"),
        ("2011-2012", "HB1472"), ("2011-2012", "HB1512"), ("2011-2012", "HR31"),
        ("2011-2012", "PET29"), ("2015-2016", "SB499"), ("2017-2018", "HR1"),
        ("2017-2018", "HR2"), ("2017-2018", "HR3"), ("2017-2018", "HR4"),
        ("2017-2018", "HR5"), ("2017-2018", "HR6")],
    "docket": [("1991-1992", "HR69")],
    "journal": [("2021-2022", "HB459")],
}


# ------------------------------------------- the cards' data (9 October 2026) --
#
# What the next visual stages draw a bill's card from on a committee's
# meeting, a session day and a member's term, decided once, upstream, in
# Python (the component plan's C4; the person's feedback of 9 October 2026,
# items 1, 7, 12 and 18 and v7, v8, v12, v13, v15, v16 and v18).

# Real rows, copied from Docket.txt on 9 October 2026: HB 1681 (lines 13162,
# 16668, 17316, 18930, 19540-19541, 19565, 19770, 20150, 21797, 22429, 22580,
# 22619, 23615), HB 1652 (13009, 16693, 17461-17462, 18573, 25340, 25396),
# HB 65 (35, 470, 2121, 11346, 11932-11933, 13095, 25331, 25388), HB 572 (918,
# 1163, 4014, 4466, 5137, 5530-5531, 6009, 6569, 7285, 11425, 11544,
# 11839-11840, 13904), HB 1525 (12883, 14107, 15739, 16298, 17229) and
# HB 1705 (13186, 15195, 15828, 16694-16695, 17609-17612).
_CARD_DOCKETS = {
    ('HB1681', "2025-2026"): [
        "2026|3110|12/12/2025 9:34:08 AM|HB1681|H|  Introduced 01/07/2026 and referred to Housing  HJ 1  P. 31|3/25/2026 3:13:36 PM",
        "2026|3110|2/11/2026 11:35:54 AM|HB1681|H|Public Hearing: 02/17/2026 01:00 pm GP 231|2/11/2026 11:35:54 AM",
        "2026|3110|2/17/2026 3:32:21 PM|HB1681|H|Executive Session: 03/03/2026 10:00 am GP 231|2/17/2026 3:32:21 PM",
        "2026|3110|3/4/2026 5:21:40 PM|HB1681|H| Committee Report: Ought to Pass with Amendment # 2026-0998h   03/03/2026 (Vote 17-0; CC)  HC 10  P. 25|3/16/2026 9:53:57 AM",
        "2026|3110|3/11/2026 8:13:48 PM|HB1681|H|Amendment # 2026-0998h: AA VV 03/11/2026  HJ 7  P. 226|6/23/2026 1:19:20 PM",
        "2026|3110|3/11/2026 8:15:00 PM|HB1681|H|Ought to Pass with Amendment 2026-0998h: MA DV 231-99 03/11/2026  HJ 7  P. 228|6/23/2026 1:19:34 PM",
        "2026|3110|3/10/2026 10:08:37 AM|HB1681|H|Removed from Consent (Reps. Turcotte, Sheehan, Hill, Verville, T. Walsh, Corcoran, Gilman, Stavis, Mandelbaum, Maggiore) 03/09/2026  HJ 7  P. 1|6/23/2026 3:07:53 PM",
        "2026|3110|3/11/2026 8:13:40 PM|HB1681|H|Special Order to the next order of business (Rep. Alexander Jr.): MA DV 299-28 03/11/2026  HJ 7  P. 226|6/23/2026 1:18:49 PM",
        "2026|3110|3/17/2026 11:53:26 AM|HB1681|S|  Introduced 03/12/2026 and Referred to Commerce;  SJ 7|3/17/2026 11:53:30 AM",
        "2026|3110|4/16/2026 9:13:48 AM|HB1681|S| Hearing: 04/21/2026, Room 100, SH, 10:30 am;  SC 15|4/16/2026 9:13:48 AM",
        "2026|3110|4/30/2026 9:18:33 AM|HB1681|S|Committee Report: Ought to Pass with Amendment # 2026-1709s, 05/07/2026; Vote 4-1; CC;  SC 17|4/30/2026 9:18:33 AM",
        "2026|3110|5/5/2026 9:54:46 AM|HB1681|S|Committee Amendment # 2026-1709s, AA, VV; 05/07/2026;  SJ 11|5/7/2026 9:33:04 AM",
        "2026|3110|5/5/2026 10:23:02 AM|HB1681|S|Ought to Pass with Amendment # 2026-1709s, MA, VV; OT3rdg; 05/07/2026;  SJ 11|5/7/2026 9:33:09 AM",
        "2026|3110|5/21/2026 12:01:21 PM|HB1681|H|House Concurs with Senate Amendment 2026-1709s (Rep. Alexander Jr.): MA RC 242-102 05/21/2026  HJ 14  P. 14|7/24/2026 3:57:46 PM",
    ],
    ('HB1652', "2025-2026"): [
        "2026|3100|12/10/2025 1:33:38 PM|HB1652|H|  Introduced 01/07/2026 and referred to Housing  HJ 1  P. 30|3/25/2026 3:07:05 PM",
        "2026|3100|2/11/2026 11:36:24 AM|HB1652|H|Public Hearing: 02/17/2026 02:00 pm GP 231|2/11/2026 11:36:24 AM",
        "2026|3100|2/18/2026 3:28:33 PM|HB1652|H|  Executive Session: 02/17/2026 02:00 pm GP 231|2/18/2026 3:28:33 PM",
        "2026|3100|2/18/2026 3:28:52 PM|HB1652|H| Committee Report: Refer for Interim Study  02/17/2026 (Vote 12-0; CC)  HC 9  P. 17|3/3/2026 11:44:46 AM",
        "2026|3100|3/5/2026 10:21:35 AM|HB1652|H|Refer for Interim Study: MA VV 03/05/2026  HJ 6  P. 20|6/9/2026 1:57:42 PM",
        "2026|3100|9/22/2026 1:40:01 PM|HB1652|H|Executive Session: 10/01/2026 10:00 am GP 231|9/22/2026 1:40:01 PM",
        "2026|3100|10/5/2026 12:43:18 PM|HB1652|H| Interim Study Report: Recommended for Future Legislation  10/01/2026 (Vote 8-1; )|10/5/2026 12:43:18 PM",
    ],
    ('HB65', "2025-2026"): [
        "2026|0045|12/23/2024 3:26:13 PM|HB65|H|  Introduced 01/08/2025 and referred to Housing  HJ 2  P. 4|1/21/2025 1:23:35 PM",
        "2026|0045|1/9/2025 10:45:23 AM|HB65|H|  Public Hearing: 01/21/2025 11:30 am LOB 210-211|1/17/2025 2:44:45 PM",
        "2026|0045|1/31/2025 10:50:41 AM|HB65|H|Retained in Committee|1/31/2025 10:50:41 AM",
        "2026|0045|8/28/2025 11:01:36 AM|HB65|H|  Full Committee Work Session: 09/23/2025 10:00 am GP 231|8/28/2025 11:01:36 AM",
        "2026|0045|11/12/2025 8:33:46 AM|HB65|H|  Executive Session: 09/23/2025 10:00 am GP 231|11/12/2025 8:33:46 AM",
        "2026|0045|11/12/2025 8:34:17 AM|HB65|H| Committee Report: Refer for Interim Study  09/23/2025 (Vote 16-0; CC)  HC 51  P. 12|12/19/2025 12:14:25 PM",
        "2026|0045|1/7/2026 11:23:14 AM|HB65|H|Refer for Interim Study: MA VV 01/07/2026  HJ 1  P. 73|3/27/2026 3:04:43 PM",
        "2026|0045|9/22/2026 1:38:37 PM|HB65|H|Executive Session: 10/01/2026 10:00 am GP 231|9/22/2026 1:38:37 PM",
        "2026|0045|10/5/2026 12:22:52 PM|HB65|H| Interim Study Report: Not Recommended for Future Legislation  09/30/2026 (Vote 5-4; )|10/5/2026 12:22:52 PM",
    ],
    ('HB572', "2025-2026"): [
        "2026|0095|1/16/2025 9:11:19 AM|HB572|H|  Introduced (in recess of) 01/09/2025 and referred to Housing  HJ 3  P. 17|2/18/2025 2:59:38 PM",
        "2026|0095|1/22/2025 1:41:28 PM|HB572|H|Public Hearing: 01/28/2025 10:00 am LOB 305|1/22/2025 1:41:28 PM",
        "2026|0095|2/26/2025 9:43:34 AM|HB572|H|Executive Session: 03/04/2025 10:00 am LOB 305|2/26/2025 9:43:34 AM",
        "2026|0095|3/5/2025 12:10:23 PM|HB572|H| Committee Report: Ought to Pass with Amendment # 2025-0560h (NT)  03/04/2025 (Vote 16-0; RC)|3/5/2025 12:10:23 PM",
        "2026|0095|3/13/2025 3:51:27 PM|HB572|H|Referred to Finance 03/13/2025  HJ 8  P. 79|4/21/2025 3:36:55 PM",
        "2026|0095|3/13/2025 3:50:45 PM|HB572|H|Amendment # 2025-0560h (NT): AA VV 03/13/2025  HJ 8  P. 78|4/21/2025 3:36:24 PM",
        "2026|0095|3/13/2025 3:51:24 PM|HB572|H|Ought to Pass with Amendment 2025-0560h: MA VV 03/13/2025  HJ 8  P. 79|4/21/2025 3:36:50 PM",
        "2026|0095|3/19/2025 12:41:51 PM|HB572|H|  Division I Work Session: 03/24/2025 09:00 am LOB 212|3/20/2025 12:55:16 PM",
        "2026|0095|3/26/2025 12:41:27 PM|HB572|H|Executive Session: 04/01/2025 10:00 am LOB 210-211|3/26/2025 12:41:27 PM",
        "2026|0095|4/2/2025 11:20:47 AM|HB572|H|Retained in Committee|4/2/2025 11:20:47 AM",
        "2026|0095|9/18/2025 3:39:04 PM|HB572|H|  Division I Work Session: 10/02/2025 01:00 pm GP 230|9/18/2025 3:39:04 PM",
        "2026|0095|10/14/2025 11:40:15 AM|HB572|H|Executive Session: 10/30/2025 10:00 am GP 230|10/14/2025 11:40:15 AM",
        "2026|0095|11/6/2025 2:47:28 PM|HB572|H|Majority Committee Report: Inexpedient to Legislate  10/30/2025 (Vote 14-11; RC)  HC 51  P. 35|12/19/2025 2:15:36 PM",
        "2026|0095|11/6/2025 2:47:54 PM|HB572|H|Minority Committee Report: Ought to Pass with Amendment # 2025-2956h (NT)|11/6/2025 2:47:54 PM",
        "2026|0095|1/8/2026 9:56:39 AM|HB572|H|Inexpedient to Legislate: MA RC 191-156 01/08/2026  HJ 2  P. 6|3/30/2026 2:30:51 PM",
    ],
    ('HB1525', "2025-2026"): [
        "2026|2678|12/10/2025 11:50:05 AM|HB1525|H|  Introduced 01/07/2026 and referred to Housing  HJ 1  P. 24|3/25/2026 1:13:49 PM",
        "2026|2678|1/14/2026 11:28:09 AM|HB1525|H|Public Hearing: 01/22/2026 01:00 pm GP 231|1/14/2026 11:28:09 AM",
        "2026|2678|2/3/2026 2:33:31 PM|HB1525|H|  Executive Session: 01/22/2026 01:00 pm GP 231|2/3/2026 2:35:42 PM",
        "2026|2678|2/6/2026 12:37:00 PM|HB1525|H| Committee Report: Inexpedient to Legislate  02/22/2026 (Vote 15-0; CC)  HC 7  P. 15|2/18/2026 10:20:21 AM",
        "2026|2678|2/19/2026 10:43:49 AM|HB1525|H|Inexpedient to Legislate: MA VV 02/19/2026  HJ 5  P. 24|5/12/2026 9:00:48 AM",
    ],
    ('HB1705', "2025-2026"): [
        "2026|2393|12/12/2025 9:43:06 AM|HB1705|H|  Introduced 01/07/2026 and referred to Labor, Industrial and Rehabilitative Services  HJ 1  P. 32|3/25/2026 3:21:39 PM",
        "2026|2393|1/28/2026 4:19:31 PM|HB1705|H|Public Hearing: 02/03/2026 01:30 pm GP 159|1/28/2026 4:19:31 PM",
        "2026|2393|2/5/2026 8:22:59 AM|HB1705|H|Executive Session: 02/10/2026 10:00 am GP 159|2/5/2026 8:22:59 AM",
        "2026|2393|2/11/2026 11:07:18 AM|HB1705|H|Majority Committee Report: Refer for Interim Study  02/10/2026 (Vote 11-9; RC)  HC 7  P. 36|2/18/2026 11:04:37 AM",
        "2026|2393|2/11/2026 11:08:02 AM|HB1705|H|Minority Committee Report: Ought to Pass with Amendment # 2026-0531h|2/11/2026 11:08:02 AM",
        "2026|2393|2/19/2026 2:09:56 PM|HB1705|H|Refer for Interim Study: MF DV 167-174 02/19/2026  HJ 5  P. 93|5/12/2026 10:13:46 AM",
        "2026|2393|2/19/2026 2:10:23 PM|HB1705|H|Amendment # 2026-0531h: AA VV 02/19/2026  HJ 5  P. 93|5/12/2026 10:13:54 AM",
        "2026|2393|2/19/2026 2:11:12 PM|HB1705|H|Ought to Pass with Amendment 2026-0531h: MA RC 194-154 02/19/2026  HJ 5  P. 93|5/12/2026 10:14:05 AM",
        "2026|2393|2/19/2026 2:11:30 PM|HB1705|H|Referred to Finance 02/19/2026  HJ 5  P. 95|5/12/2026 10:14:22 AM",
    ],
}


def _card_events(N):
    """{bill: events} for _CARD_DOCKETS, as narrative.build tells them."""
    keep = N.MEMBERS
    try:
        N.MEMBERS = {}
        return {b: _narrated(N, t, b, rows)["events"]
                for (b, t), rows in _CARD_DOCKETS.items()}
    finally:
        N.MEMBERS = keep


# ---- the published scripts do what the source does (23 October 2026) -------
#
# LAST ON PURPOSE: it runs again every check that runs a page's script, on
# the copy the site publishes, and holds each to how it came out on the
# source in this same run (_OUTCOMES, which main() keeps), so it registers
# after all of them.



def _published_harnesses():
    """(every check of the code that runs a page's script in node through
    _node_app or _with_components, directly or through a function of the
    suite's; those of them this run runs again on the published copy): every
    one, or in a run that chose its checks (_THIS_RUN.chosen, --changed) those
    it chose."""
    found = [c for c in _reaching({"_node_app", "_with_components"},
                                  skip=("_published_scripts_run_the_same",))
             if c["group"] != "data"]
    chosen = _THIS_RUN.chosen
    return found, [c for c in found if chosen is None or c["fn"].__name__ in chosen]
