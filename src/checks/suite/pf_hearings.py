#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.6
"""
preflight's checks of livestreams, markers, dockets and proceedings.

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import argparse
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

from pf_core import (_run, _sealed_run, _source, check, imp)
from pf_fixture import (PROCEEDINGS_MODULES)
from pf_harness import (_components_js)
from pf_shared import (_CLERKS_COMMITTEES, _CLOCK_SEMICOLON, _DOCKET_TIME_CHANGE,
                       _FULL_COMMITTEE_NAMES, _ROOM_CHANGED, _cal_node, _hearing_fixture,
                       _inbox_files, _inbox_words, _json3, _narratives, _rc, _site_bills,
                       _sitting_fixture, _told_from_rows, _visible_text)


# Real rows: Docket_2015-2016.txt (HB 564 of 2015).
_DOCKET_CANCELED_SITTINGS = [
    "2015|0652|01/08/2015 03:27:23 PM|HB564|H|Introduced and Referred to Health, Human Services and Elderly Affairs; HJ 12, PG. 231|01/08/2015 03:27:23 PM",
    "2015|0652|02/03/2015 03:10:49 PM|HB564|H|==CANCELED== Public Hearing: 2/12/2015 1:15 PM LOB 206-208|02/03/2015 03:10:49 PM",
    "2015|0652|02/04/2015 12:50:42 PM|HB564|H|==RESCHEDULED== Public Hearing: 2/12/2015 2:30 PM LOB 205|02/04/2015 12:50:42 PM",
    "2015|0044|01/20/2015 03:51:45 PM|HB230|H|==CANCELED== Executive Session: 2/3/2015 LOB 302|01/20/2015 03:51:45 PM",
]


@check("build", "a notice marked cancelled with one L is no sitting in proceedings.csv, and "
                "--merge --drop-cancelled takes such a row out of a manifest and nothing else",
       needs=("docket_parser", "build_manifest"))
def _one_l_cancelled_sittings(D, M):
    """Decision 59d: 51 rows of proceedings.csv, 49 of them 2015-2016, were
    notices the clerk marked "==CANCELED==" -- HB 230 of 2015's executive
    session of 3 February, HB 564's hearing of 12 February at 1:15, moved to
    2:30 -- which build_sittings filed as sittings because it looked for the
    flag "CANCELLED" alone, so the stations, the committees' days and the
    download drew them beside histories that tell them as called off. The
    manifests were mended with --merge --drop-cancelled, which takes out a row
    whose meeting the parse reads only as called off, keeps every other row
    as it was, and refuses to take out one with a hand-marked time."""
    bad = []
    tmp = Path(tempfile.mkdtemp(prefix="gr-one-l-"))
    try:
        (tmp / "Docket.txt").write_text("\n".join(_DOCKET_CANCELED_SITTINGS) + "\n", encoding="utf-8")
        rows = D.parse_rows(str(tmp / "Docket.txt"))
        procs = D.parse_proceedings(rows, D.build_referral_timeline(rows))
        D.build_sittings(procs)
        live = sorted((p.bill, p.sched_date, p.sched_time) for p in procs
                      if p.confidence != "X-cancelled")
        if live != [("HB564", "2015-02-12", "14:30")]:
            bad.append(f"the sittings read are {live!r}, not HB 564's hearing at 2:30 alone")
        cols = M.MANIFEST_COLUMNS
        line = lambda b, k, d, t, mark="": (",".join([b, "H", "", k, d, t, "", "A-unique-slot", "1",
                                                      "no video found"] + [""] * (len(cols) - 13)
                                                     + [mark, "", ""]) + "\r\n")
        kept = [line("HB230", "executive session", "2015-02-03", ""),
                line("HB564", "public hearing", "2015-02-12", "13:15"),
                line("HB564", "public hearing", "2015-02-12", "14:30")]
        f = tmp / "verification_manifest_2015-2016.csv"
        f.write_text(",".join(cols) + "\r\n" + "".join(kept), encoding="utf-8", newline="")
        row = {**{c: "" for c in cols}, "bill": "HB564", "body": "H", "proceeding": "public hearing",
               "sched_date": "2015-02-12", "sched_time": "14:30"}
        off = {("HB230", "H", "2015-02-03", "executive session", ""),
               ("HB564", "H", "2015-02-12", "public hearing", "13:15")}
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            M.merge_rows(str(f), [row], ["HB564@2015-02-12", "HB230"], off)
        got = f.read_text(encoding="utf-8", newline="")
        if got != ",".join(cols) + "\r\n" + kept[2]:
            bad.append(f"--drop-cancelled left {got!r}")
        f.write_text(",".join(cols) + "\r\n" + line("HB230", "executive session", "2015-02-03", "",
                                                   "0:41:10"), encoding="utf-8", newline="")
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                M.merge_rows(str(f), [], None, off)
            bad.append("--drop-cancelled took out a row carrying a hand-marked time")
        except SystemExit:
            pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert not bad, "\n".join(bad)
    return "ok", ("two one-L notices read as called off; --drop-cancelled takes out two rows, "
                  "keeps the held one and refuses a hand-marked row")


@check("data", "no term's manifest holds a sitting its docket marks called off")
def _manifests_hold_no_called_off_sitting():
    """Decision 59d: the 51 one-L rows taken out of the 2001-2002, 2009-2010
    and 2015-2016 manifests stay out, and no other term's manifest holds a
    meeting its docket reads only as called off. Every term's, and the
    session's (Docket.txt, verification_manifest.csv): the check read those
    three alone while its sentence spoke for every term (the review of 59d,
    7 October 2026), and the review's reading of all nineteen found none."""
    D = imp("docket_parser")
    NA = imp("narrate_archive")
    if D is None or NA is None:
        return "skip", "docket_parser or narrate_archive will not import"
    bad, n, terms = [], 0, 0
    pairs = [(t, p, Path(f"verification_manifest_{t}.csv")) for t, p in sorted(NA.dockets().items())]
    pairs.append(("the session", "Docket.txt", Path("verification_manifest.csv")))
    for term, path, man in pairs:
        if not path or not Path(path).exists() or not man.exists():
            if term in ("2001-2002", "2009-2010", "2015-2016"):
                return "skip", f"no docket or manifest of {term} here"
            continue
        terms += 1
        rows = D.parse_rows(path)
        procs = D.parse_proceedings(rows, D.build_referral_timeline(rows))
        D.build_sittings(procs)
        key = lambda b, body, d, k, t: (b.strip().upper(), body.strip().upper(), d, k.lower(), t or "")
        live = {key(p.bill, p.body, p.sched_date, p.kind, p.sched_time) for p in procs
                if p.confidence != "X-cancelled"}
        off = {key(p.bill, p.body, p.sched_date, p.kind, p.sched_time) for p in procs
               if p.confidence == "X-cancelled"} - live
        with man.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                n += 1
                if key(r["bill"], r["body"], r["sched_date"], r["proceeding"], r["sched_time"]) in off:
                    bad.append(f"{man.name}: {r['bill']} {r['proceeding']} {r['sched_date']} "
                               f"{r['sched_time']} is a meeting its docket calls off")
    assert not bad, "\n".join(bad[:20])
    return "ok", f"{n:,} rows of {terms} manifests, none a meeting called off"


# Real rows: Docket_db_2001-2002.txt (SB 373) and Docket_db_1999-2000.txt (SB
# 79, SB 395 and SB 27), and rows that are cancellations.
_RESCHEDULED_ROWS = [
    # (row, the day and hour proceedings.csv should read, or None for a row
    # that is a cancelled sitting)
    ("2002|3004|01/02/2002 05:03:29 PM|SB373|S|Hearing; === CANCELLED === RESCHEDULED === "
     "January 22, 2002, 1:00 p.m.; SC2|01/02/2002 05:03:29 PM", ("2002-01-22", "13:00")),
    ("2001|0226|04/17/2001 05:57:57 PM|HB643|S|Hearing; ==CANCELLED== RESCHEDULED == May 8, 2001, "
     "Room 101, LOB, 2:15 p.m.; SC19|04/17/2001 05:57:57 PM", ("2001-05-08", "14:15")),
    ("2000|2327|02/16/2000 03:27:09 PM|SB395|S|==RESCHEDULED== Feb.24, Room 103, SH,10:00 a.m., "
     "SC 12, Pg.8|02/16/2000 03:27:09 PM", ("2000-02-24", "10:00")),
    ("2000|0923|03/10/1999 02:39:49 PM|SB79|S|Rescheduled Hearing, 3/24/99, Room 103, LOB, "
     "9:00 a.m. Hearing Cancelled|03/10/1999 02:39:49 PM", ("1999-03-24", "09:00")),
    ("2000|2679|01/13/2000 04:15:57 PM|SB324|S|(RESCHEDULED) Feb. 14, 10:00 a.m. Rooms 206-208, "
     "LOB;SC3, Pg.7|01/13/2000 04:15:57 PM", ("2000-02-14", "10:00")),
    ("2002|2131|03/05/2002 04:08:58 PM|HB1132|S|Hearing; March 7, 2002, Room 104, LOB, 8:45 a.m. "
     "=== CANCELLED === TO BE RESCHEDULED===; SC14|03/05/2002 04:08:58 PM", None),
    ("1999|0006|04/08/1999 08:48:51 AM|HB238|S|CANCELLED Hearing, 4/14/99, Room 101, LOB, "
     "3:30 p.m.|04/08/1999 08:48:51 AM", None),
    ("1999|0144|03/04/1999 05:52:52 PM|SB191|S|Hearing, 3/17/99, Room 105-A, SH 8:30 a.m. "
     "Hearing Cancelled|03/04/1999 05:52:52 PM", None),
]


@check("build", "a Senate row that names a hearing's new day gives proceedings.csv a sitting on "
                "that day, as the history reads it, and --merge adds it to a manifest whole",
       needs=("docket_parser", "build_manifest", "narrative"))
def _rescheduled_rows_proceedings(D, M, N):
    """Decision 60. SB 373 of 2002 and SB 79 and SB 395 of 1999-2000 had no
    hearing drawn anywhere: the history tells each on the day a row names --
    "Hearing; === CANCELLED === RESCHEDULED === January 22, 2002",
    "==RESCHEDULED== Feb.24, Room 103, SH,10:00 a.m.", "Rescheduled Hearing,
    3/24/99 ... Hearing Cancelled" -- and docket_parser read the first as a
    cancelled sitting, the second as nothing and the third as the new notice
    called off. Now each is a sitting on the day it names, and a cancellation
    is still one. The two readers' pattern for the first is one pattern.

    And build_manifest --merge: the rows a manifest has are kept byte for
    byte, a row of the parse it has no meeting for is added where main()
    sorts it, and --only keeps out what it does not name (the eight House
    conference meetings of June 2001 a whole rebuild of 2001-2002 adds)."""
    bad = []
    if D.CANCELLED_AND_RESCHEDULED.pattern != N.CANCELLED_AND_RESCHEDULED.pattern:
        bad.append("docket_parser and narrative read a cancelled-and-rescheduled row differently")
    for line, want in _RESCHEDULED_ROWS:
        tmp = Path(tempfile.mkdtemp(prefix="gr-resched-"))
        try:
            (tmp / "Docket.txt").write_text(line + "\n", encoding="utf-8")
            rows = D.parse_rows(str(tmp / "Docket.txt"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        procs = D.parse_proceedings(rows, D.build_referral_timeline(rows))
        D.build_sittings(procs)
        live = [(p.sched_date, p.sched_time) for p in procs if p.confidence != "X-cancelled"]
        if want and live != [want]:
            bad.append(f"{rows[0]['bill']}: read as {live!r}, not a sitting at {want!r}")
        if not want and live:
            bad.append(f"{rows[0]['bill']}'s cancellation is read as a sitting at {live!r}")
    # --merge, on a manifest of two rows written as build_manifest writes them.
    tmp = Path(tempfile.mkdtemp(prefix="gr-merge-"))
    try:
        cols = M.MANIFEST_COLUMNS
        head = ",".join(cols) + "\r\n"
        kept = ['SB79,S,,hearing,1999-03-17,09:00,LOB 103,A-unique-slot,1,no video found'
                + "," * (len(cols) - 10) + "\r\n",
                'SB395,S,Insurance,hearing,2000-02-22,10:30,SH 103,A-unique-slot,1,no video found'
                + "," * (len(cols) - 10) + "\r\n"]
        f = tmp / "verification_manifest_1999-2000.csv"
        f.write_text(head + "".join(kept), encoding="utf-8", newline="")
        row = lambda b, d, t, k="hearing": {**{c: "" for c in cols}, "bill": b, "body": "S",
                                            "proceeding": k, "sched_date": d, "sched_time": t,
                                            "tier": "A-unique-slot", "bills_in_slot": 1,
                                            "match": "no video found"}
        parse = [row("SB79", "1999-03-17", "09:00"), row("SB79", "1999-03-24", "09:00"),
                 row("SB395", "2000-02-22", "10:30"), row("SB395", "2000-02-24", "10:00"),
                 row("HB170", "2001-06-15", "13:30", "committee of conference")]
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            M.merge_rows(str(f), parse, ["SB79@1999-03-24", "SB395"])
        got = f.read_text(encoding="utf-8", newline="").split("\r\n")
        if [x + "\r\n" for x in (got[1], got[3])] != kept:
            bad.append(f"--merge changed or moved a row it had: {got!r}")
        if not (got[2].startswith("SB79,S,,hearing,1999-03-24,09:00")
                and got[4].startswith("SB395,S,,hearing,2000-02-24,10:00")):
            bad.append(f"--merge did not add the two new rows where they sort: {got!r}")
        if any("HB170" in x for x in got):
            bad.append("--merge added a row --only does not name")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert not bad, "\n".join(bad)
    return "ok", (f"{sum(1 for _, w in _RESCHEDULED_ROWS if w)} rows naming a new day are sittings "
                  f"on it, {sum(1 for _, w in _RESCHEDULED_ROWS if not w)} cancellations are not; "
                  "--merge keeps every row and adds what --only names")


# Real rows: Docket_db_1999-2000.txt 18564-18571 (SB 411 of 2000).
_DOCKET_NEW_TIME = [
    '2000|2637|01/05/2000 12:43:40 PM|SB411|S|Vacated from Ways and Means to Environment ; SJ Convening Day, Pg.6|01/05/2000 12:43:40 PM',
    '2000|2637|01/05/2000 01:11:39 PM|SB411|S|Introduced and Ref. to Ways and Means; SJ Convening Day, Pg.13|01/05/2000 01:11:39 PM',
    '2000|2637|01/06/2000 02:56:10 PM|SB411|S|Hearing, Feb. 4, Room 103, SH, 10:00 a.m.; SC1, Pg.7|01/06/2000 02:56:10 PM',
    '2000|2637|01/11/2000 10:25:41 AM|SB411|S|==CANCELLED==; SC2, Pg.17|01/11/2000 10:25:41 AM',
    '2000|2637|01/13/2000 04:30:01 PM|SB411|S|==RESCHEDULED== Feb.10, Room 104, LOB, 9:00 a.m.; SC3, Pg.7|01/13/2000 04:30:01 PM',
    '2000|2637|01/26/2000 03:55:32 PM|SB411|S|==NEW TIME== Feb.10, Room 104, LOB, 1:00 p.m., SC6 Pg. 4|01/26/2000 03:55:32 PM',
    '2000|2637|03/21/2000 05:23:30 PM|SB411|S|Committe Report Interim Study; 3/23/2000, SC18|03/21/2000 05:23:30 PM',
    '2000|2637|03/23/2000 01:33:03 PM|SB411|S|Interim Study, MA, VV; SJ 7, Pg. 202|03/23/2000 01:33:03 PM',
]


@check("build", "a Senate hearing's new day takes the hour a later row gave it and the committee "
                "the bill was vacated to, and --merge --refresh replaces the one row it names",
       needs=("docket_parser", "build_manifest", "narrative", "proceedings"))
def _rescheduled_row_new_time(D, M, N, P):
    """The review of decision 60: SB 411 of 2000's row merged into the
    1999-2000 manifest put its Senate hearing of 10 February at 9:00 before
    Ways and Means, the hour and committee of "==RESCHEDULED== Feb.10, Room
    104, LOB, 9:00 a.m." and its introduction. The docket's later row
    "==NEW TIME== Feb.10, Room 104, LOB, 1:00 p.m." moved it, and "Vacated
    from Ways and Means to Environment" sent the bill on; Senate Calendar 10
    prints "PLEASE NOTE THE TIME CHANGE FROM 9:00 A.M. TO 1:00 P.M." over
    ENVIRONMENT and SB 411 at 1:00. The bill page's station, the download and
    Senate Ways and Means' page, which said the committee met that day for a
    hearing on SB 411, took both from the row. --merge keeps a row it has byte
    for byte, so --refresh replaces the row of a meeting --only names by day,
    and refuses a row with a hand-marked time or an --only without a day.

    The notice of 4 February, "Hearing, Feb. 4", is the docket's and the table
    holds it since _docket_dotted_month reads the dotted month; the history
    voids it, cancelled by the row "==CANCELLED==; SC2, Pg.17", so
    proceedings.notice_only leaves it off every page and the one sitting
    drawn is the 10th's."""
    bad = []
    tmp = Path(tempfile.mkdtemp(prefix="gr-new-time-"))
    try:
        (tmp / "Docket.txt").write_text("\n".join(_DOCKET_NEW_TIME) + "\n", encoding="utf-8")
        rows = D.parse_rows(str(tmp / "Docket.txt"))
        procs = D.parse_proceedings(rows, D.build_referral_timeline(rows))
        D.build_sittings(procs)
        live = [(p.sched_date, p.sched_time, p.committee) for p in procs
                if p.confidence != "X-cancelled"]
        if live != [("2000-02-04", "10:00", "Environment"), ("2000-02-10", "13:00", "Environment")]:
            bad.append(f"SB 411's sittings are read as {live!r}, not the notice of 4 February at "
                       "10:00 and Environment's hearing at 1:00 on 10 February")
        narr = _told_from_rows(N, "1999-2000", "SB411", _DOCKET_NEW_TIME)
        drawn = [(p.sched_date, p.sched_time) for p in procs if p.confidence != "X-cancelled"
                 and not P.notice_only({"date": p.sched_date, "kind": p.kind, "body": p.body,
                                        "time": p.sched_time or ""}, narr)]
        if drawn != [("2000-02-10", "13:00")]:
            bad.append(f"SB 411's history leaves {drawn!r} drawn, not the hearing of 10 February "
                       f"alone (voided {narr.get('voided')!r})")
        cols = M.MANIFEST_COLUMNS
        line = lambda b, c, d, t, mark="": (",".join([b, "S", c, "hearing", d, t, "LOB 104",
                                                      "A-unique-slot", "1", "no video found"]
                                                     + [""] * (len(cols) - 13) + [mark, "", ""])
                                            + "\r\n")
        kept = [line("SB405", "Ways and Means", "2000-02-08", "10:00"),
                line("SB411", "Ways and Means", "2000-02-10", "09:00"),
                line("SB405", "Ways and Means", "2000-02-11", "10:00")]
        f = tmp / "verification_manifest_1999-2000.csv"
        head = ",".join(cols) + "\r\n"
        f.write_text(head + "".join(kept), encoding="utf-8", newline="")
        row = lambda b, c, d, t: {**{x: "" for x in cols}, "bill": b, "body": "S", "committee": c,
                                  "proceeding": "hearing", "sched_date": d, "sched_time": t,
                                  "venue": "LOB 104", "tier": "A-unique-slot", "bills_in_slot": 1,
                                  "match": "no video found"}
        parse = [row("SB405", "Ways and Means", "2000-02-08", "11:00"),
                 row("SB411", "Environment", "2000-02-10", "13:00"),
                 row("SB405", "Ways and Means", "2000-02-11", "10:00")]
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            M.merge_rows(str(f), parse, ["SB411@2000-02-10"], refresh=True)
        got = f.read_text(encoding="utf-8", newline="")
        if got != head + kept[0] + line("SB411", "Environment", "2000-02-10", "13:00") + kept[2]:
            bad.append(f"--refresh left {got!r}")
        for only, mark in ((["SB411"], ""), (["SB411@2000-02-10"], "0:12:00")):
            f.write_text(head + line("SB411", "Ways and Means", "2000-02-10", "09:00", mark),
                         encoding="utf-8", newline="")
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    M.merge_rows(str(f), parse, only, refresh=True)
                bad.append(f"--refresh ran with --only {only} on a row marked {mark!r}")
            except SystemExit:
                pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert not bad, "\n".join(bad)
    return "ok", ("SB 411 of 2000 heard by Environment at 1:00 on 10 February; --refresh replaces "
                  "the one row named and refuses a dayless --only and a marked row")


# Real rows: Docket_db_1999-2000.txt 17032-17037 (SB 398 of 2000).
_DOCKET_VACATED_SB398 = [
    "2000|2486|01/05/2000 09:56:03 AM|SB398|S|Introduced and Ref. to Transportation; SJ Convening Day, Pg. 12|01/05/2000 09:56:03 AM",
    "2000|2486|01/05/2000 03:17:52 PM|SB398|S|Hearing, Jan. 11, 3:45 p.m., Room 102, LOB; SC1, Pg. 3 ==CANCELLED==|01/05/2000 03:17:52 PM",
    "2000|2486|01/05/2000 03:18:43 PM|SB398|S|Vacated from Transportation to Wildlife and Recreation, MA, VV; SJ Convening Day, Pg. 6|01/05/2000 03:18:43 PM",
    "2000|2486|03/09/2000 08:48:04 AM|SB398|S|Hearing March 15, Room 101, LOB, 2:45 p.m.; SC16|03/09/2000 08:48:04 AM",
    "2000|2486|03/22/2000 09:00:23 AM|SB398|S|Committee Report Inexpedient to Legislate; 3/23/2000, SC18|03/22/2000 09:00:23 AM",
    "2000|2486|03/23/2000 04:29:52 PM|SB398|S|Inexpedient to Legislate, MA, VV  ==KILLED==; SJ 7, Pg. 224|03/23/2000 04:29:52 PM",
]


@check("build", "SB 398 of 2000's hearing is the committee's the Senate vacated the bill to, as "
                "its committee row and history say", needs=("docket_parser",))
def _vacated_sb398(D):
    """SB 398 of 2000 was introduced to Transportation and, the same
    afternoon, "Vacated from Transportation to Wildlife and Recreation";
    Wildlife and Recreation heard it on 15 March. The bill's committee row
    (referrals.vacated, data/bills.json) and its history named Wildlife and
    Recreation, and the 1999-2000 manifest, merged before docket_parser read
    the Senate's "Vacated from X to Y" (VACATED_FROM_TO_RE, the review of
    decision 60), filed the hearing under Transportation -- the station on
    the bill's page and Senate Transportation's day. The parser reads it;
    _vacated_sb398_manifest holds the files on disk to it."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-vacated-"))
    try:
        (tmp / "Docket.txt").write_text("\n".join(_DOCKET_VACATED_SB398) + "\n", encoding="utf-8")
        rows = D.parse_rows(str(tmp / "Docket.txt"))
        procs = D.parse_proceedings(rows, D.build_referral_timeline(rows))
        D.build_sittings(procs)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    live = [(p.sched_date, p.committee) for p in procs if p.confidence != "X-cancelled"]
    assert live == [("2000-03-15", "Wildlife and Recreation")], (
        f"SB 398's sittings are read as {live!r}, not Wildlife and Recreation's hearing of 15 March")
    return "ok", "SB 398 of 2000 heard by Wildlife and Recreation on 15 March"


# Real rows: Docket_db_1999-2000.txt 5488-5490 (SB 31 of 1999) and 2232-2234
# (HB 506 of 1999), the chamber of the last of each in lower case as the
# database gives it.
_DOCKET_LOWER_CHAMBER_MANIFEST = [
    "1999|0672|01/07/1999 04:14:22 PM|SB31|S|Introduction and referring to Ways & Means:  SJ 2, P 27|01/07/1999 04:14:22 PM",
    "1999|0672|02/03/1999 04:09:34 PM|SB31|S|Hearings, 2/12/99, Room 103, SH, 10:00 a.m. Hearing Recessed|02/03/1999 04:09:34 PM",
    "1999|0672|03/31/1999 10:42:26 AM|SB31|s|Rescheduled Hearing, 4/9/99, Room 103, SH, 1:00 p.m.|03/31/1999 10:42:26 AM",
    "1999|0275|01/28/1999 05:31:34 PM|HB506|H|Introduced and ref to Elec Law; HJ18, p272|01/28/1999 05:31:34 PM",
    "1999|0275|02/09/1999 05:29:15 PM|HB506|H|Copy to chairman on 2/9/1999   due on|02/09/1999 05:29:15 PM",
    "1999|0275|02/11/1999 05:30:48 PM|HB506|h|Hearing  Mar 2  10:30  Rm308,LOB|02/11/1999 05:30:48 PM",
]


@check("build", "a docket row whose chamber is in lower case is a sitting of that chamber in the "
                "manifest", needs=("build_manifest",))
def _manifest_lower_case_chamber(BM):
    """64 rows of 1999-2000 and one of 2001 give the chamber as "s" or "h",
    four of them meetings: SB 31's "Rescheduled Hearing, 4/9/99" (line 5490),
    HB 506's hearing of 2 March 1999, SB 30's and HB 346's conferences.
    docket_parser read the Senate's pattern on them, and build_manifest, which
    keeps the rows whose chamber its video indexes cover -- "H" and "S" --
    dropped all four; HB 506's hearing was looked up under a chamber no
    referral is filed under, so it named no committee. parse_rows reads the
    chamber in either case."""
    here = Path(".").resolve()
    tmp = Path(tempfile.mkdtemp(prefix="gr-manifest-case-"))
    head = ("video_id,title,title_parsed,parsed_committee,parsed_date,date_from,has_start_time,"
            "start_eastern,actual_start_utc,actual_end_utc,duration_iso,published_at\n")
    try:
        for name, vid in (("videos_house_x.csv", "h1"), ("videos_senate_x.csv", "s1")):
            (tmp / name).write_text(head + f"{vid},Finance,yes,Finance,2020-01-07,,,,,,,\n",
                                    encoding="utf-8")
        (tmp / "Docket.txt").write_text("\n".join(_DOCKET_LOWER_CHAMBER_MANIFEST) + "\n", encoding="utf-8")
        r = _run([sys.executable, _paths.script("build_manifest.py"), "--videos",
                  "videos_house_x.csv", "videos_senate_x.csv", "--docket", "Docket.txt",
                  "--out", "vm.csv"], cwd=tmp, capture_output=True, text=True, timeout=120,
                 env=dict(os.environ, PYTHONPATH=str(here)))
        assert r.returncode == 0, (r.stdout + r.stderr)[-300:]
        with (tmp / "vm.csv").open(encoding="utf-8", newline="") as fh:
            got = sorted((x["bill"], x["body"], x["sched_date"], x["committee"])
                         for x in csv.DictReader(fh))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    want = [("HB506", "H", "1999-03-02", "Elec Law"),
            ("SB31", "S", "1999-02-12", "Ways and Means"), ("SB31", "S", "1999-04-09", "Ways and Means")]
    assert got == want, f"the manifest holds {got!r}, not {want!r}"
    return "ok", "SB 31's hearing of 9 April 1999 and HB 506's of 2 March 1999 are in the manifest"


# Real rows: Docket_db_1999-2000.txt 8644-8645 (SB 49), 2044-2045 (SB 12),
# 8137-8138 (SB 48), 16092-16093 (HB 1471 in the Senate), 12195-12196 (SB 79)
# and 15318-15319 (SB 393, "Hearning" read by SENATE_SCHED_RE's kind).
_DOCKET_SENATE_INTRODUCTION = [
    ("SB49", "Education", [
        "1999|1007|01/07/1999 03:58:12 PM|SB49|S|Introduction and referring to Education;  SJ 2, P 29|01/07/1999 03:58:12 PM",
        "1999|1007|01/28/1999 03:58:48 PM|SB49|S|Hearing, 2/3/99, Room 105-A, SH, 8:30 a.m.|01/28/1999 03:58:48 PM"]),
    ("SB12", "Public Affairs", [
        "1999|0253|01/07/1999 09:45:37 AM|SB12|S|Introducing and referred to Public Affairs; SJ 2, P 26|01/07/1999 09:45:37 AM",
        "1999|0253|01/28/1999 02:51:58 PM|SB12|S|Hearing, Feb. 17, 1:00 p.m., Room 104, LOB|01/28/1999 02:51:58 PM"]),
    ("SB48", "Education", [
        "1999|0948|01/07/1999 03:54:54 PM|SB48|S|Introduction and referred to Education; SJ 2, P 29|01/07/1999 03:54:54 PM",
        "1999|0948|01/28/1999 03:55:24 PM|SB48|S|Hearing, 2/4/99, Room 105-A, SH, 8:30 a.m.|01/28/1999 03:55:24 PM"]),
    ("HB1471", "Capital Budget", [
        "2000|2397|02/03/2000 12:48:47 PM|HB1471|S|Introduced And Ref. to Capital Budget; SJ 2, Pg.86|02/03/2000 12:48:47 PM",
        "2000|2397|03/01/2000 02:22:26 PM|HB1471|S|Hearing March 10, Room 103, SH, 1:00 p.m.; SC14, Pg.3|03/01/2000 02:22:26 PM"]),
    ("SB79", "Banks", [
        "2000|0923|01/28/1999 10:39:54 AM|SB79|S|Introduction and referring to Banks 1/28/99;  SJ 3, P 34|01/28/1999 10:39:54 AM",
        "2000|0923|03/05/1999 09:33:07 AM|SB79|S|Hearing, 3/17/99, Room 103, LOB, 9:00 a.m.|03/05/1999 09:33:07 AM"]),
    ("SB393", "Insurance", [
        "2000|2307|01/05/2000 09:45:06 AM|SB393|S|Introduced and Ref. Insurance; SJ Convening Day, Pg.12|01/05/2000 09:45:06 AM",
        "2000|2307|01/06/2000 04:12:07 PM|SB393|S|Hearning, Feb. 15, Room 103, SH, 10:40 a.m.; SC1, Pg.8|01/06/2000 04:12:07 PM"]),
    # The review of 7 October 2026: Docket_db_1999-2000.txt 7125-7126 and
    # 7434-7436 (SB 27, and LSR 0881's introduction filed under SB 27 among
    # SB 26's rows), 7874-7877 (SB 69, a vacate over two rows) and 3807,
    # 3809-3810 (HB 707, "Moved Vacate to").
    ("SB27", "Banks", [
        "1999|0858|01/07/1999 04:21:20 PM|SB27|S|Introduction and referring to Banks:  SJ 2, P 27|01/07/1999 04:21:20 PM",
        "1999|0858|02/17/1999 01:50:06 PM|SB27|S|Hearing, 3/10/99, Room 103, LOB, 9:30 a.m.|02/17/1999 01:50:06 PM",
        "1999|0881|01/07/1999 04:23:15 PM|SB27|S|Introduction and referring to Judiciary:  SJ 2, P 27|01/07/1999 04:23:15 PM",
        "1999|0881|02/03/1999 03:37:40 PM|SB26|S|Hearing, 2/17/99, Room 102, LOB, 10:30 a.m.|02/03/1999 03:37:40 PM",
        "1999|0881|03/03/1999 11:32:04 AM|SB26|S|Committee Report, Ought to Pass, March 4|03/03/1999 11:32:04 AM"]),
    ("SB69", "Public Institutions, Health and Human Services", [
        "1999|0924|01/28/1999 10:19:52 AM|SB69|S|Introduction and referring to Executive Departments and Administration;   SJ 3,  P 33|01/28/1999 10:19:52 AM",
        "1999|0924|02/11/1999 11:15:50 AM|SB69|S|Sen. Cohen motion to Vacate from Executive Departments and Administration|02/11/1999 11:15:50 AM",
        "1999|0924|02/11/1999 11:23:26 AM|SB69|S|to the Public Institutions, Health and Human Services Committee.  MA, VV.|02/11/1999 11:23:26 AM",
        "1999|0924|02/25/1999 08:51:28 AM|SB69|S|Hearing, 3/30/99, Room 102, LOB, 1:45 p.m.|02/25/1999 08:51:28 AM"]),
    ("HB707", "Judiciary", [
        "1999|0473|06/29/1999 03:11:11 PM|HB707|S|Introduction and referring to Finance;  SJ 26, P 718.|06/29/1999 03:11:11 PM",
        "1999|0473|07/01/1999 03:47:29 PM|HB707|S|Sen. Hollingworth Moved Vacate to Judiciary, MA, VV; SJ 742-743|07/01/1999 03:47:29 PM",
        "1999|0473|08/18/1999 08:40:09 AM|HB707|S|Hearing, 9/8/99, Room 102, LOB, 10:30 a.m.|08/18/1999 08:40:09 AM"]),
]


@check("build", "a Senate hearing of 1999-2006 names the committee the Senate's own words "
                "introduced the bill to, or vacated it to, and never another bill's", needs=("docket_parser",))
def _senate_introduction_committee(D):
    """The Senate of 1999 wrote "Introduction and referring to Education" (615
    rows of the 1999-2000 docket), "Introducing and referred to", "Introduced
    And Ref. to", "Introduced and Ref. Insurance", and docket_parser's
    referral patterns read none of them, so 645 of the 998 Senate rows of the
    1999-2000 manifest named no committee and reached no committee's page.
    They are read as the bill's committee row reads them (referrals), the
    date after the name dropped: "referring to Banks 1/28/99" is Banks.

    AND AS IT READS THEM IN FULL (the review of 7 October 2026). Read alone,
    the introduction put six hearings under a committee the bill's own row
    does not name: SB 27's three under Judiciary, from LSR 0881's
    introduction of SB 26 filed under SB 27's number, and SB 69's and HB
    707's under the committee the Senate had vacated them from. Only the
    bill's own LSR's row, and the vacate after it, one row or two."""
    bad = []
    for bill, want, lines in _DOCKET_SENATE_INTRODUCTION:
        tmp = Path(tempfile.mkdtemp(prefix="gr-senate-intro-"))
        try:
            (tmp / "Docket.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            rows = D.parse_rows(str(tmp / "Docket.txt"))
            procs = D.parse_proceedings(rows, D.build_referral_timeline(rows))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        got = [p.committee for p in procs if p.bill == bill]
        if got != [want]:
            bad.append(f"{bill}'s Senate hearing is filed under {got!r}, not {want!r}")
    assert not bad, "\n".join(bad)
    return "ok", (f"{len(_DOCKET_SENATE_INTRODUCTION)} Senate hearings of 1999-2000 name the "
                  "committee their introduction, or the vacate after it, gave")


# Real rows: Docket_db_1999-2000.txt 2716-2717 (SB 39 of 1999) and 9481-9482
# (HB 273 of 2000); Docket_db_2009-2010.txt 21776 and 21779 (SB 483 of 2010).
_DOCKET_DOTTED_MONTH = [
    '1999|0331|01/07/1999 11:18:50 AM|SB39|S|Introduction and referring to Public Affairs:  SJ 2, P 28|01/07/1999 11:18:50 AM',
    '1999|0331|01/28/1999 03:59:04 PM|SB39|S|Hearing, Feb. 17, Room 104, LOB, 2:15 p.m.|01/28/1999 03:59:04 PM',
    '2000|0122|01/13/2000 09:24:18 AM|HB273|S|Introduced and Ref. to Education ; SJ 1, Pg.35|01/13/2000 09:24:18 AM',
    '2000|0122|02/16/2000 04:03:48 PM|HB273|S|Hearing, Feb.23, Room 105 A, SH, 9:10 a.m ; SC12, Pg.9|02/16/2000 04:03:48 PM',
    '2010|2791|01/21/2010 10:52:51 AM|SB483|S|Introduced and Referred to Ways & Means; SJ 3, Pg.46|01/21/2010 10:52:51 AM',
    '2010|2791|02/25/2010 09:59:02 AM|SB483|S|Hearing:==RECONVENE==Mar. 3, 2010, Rm 100, SH, 1:30 p.m. or immediately following session, SC9|02/25/2010 09:59:02 AM',
]


@check("build", "a Senate hearing whose month the clerk dotted (\"Feb. 17\", \"Feb.23\", \"Mar. 3, "
                "2010\") is a proceeding on that day", needs=("docket_parser",))
def _docket_dotted_month(D):
    """The Senate of 1999-2000 wrote "Hearing, Feb. 17, Room 104, LOB, 2:15
    p.m." and 2010 twice "Hearing:==RECONVENE==Mar. 3, 2010". SENATE_SCHED_RE
    read the line and _parse_date did not read the date, because strptime's
    %b takes no dot, so the row was dropped and 174 hearings had no
    proceedings row: SB 39's of 17 February 1999, HB 273's of 23 February
    2000, SB 483's reconvened sitting of 3 March 2010."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-dotted-"))
    try:
        (tmp / "Docket.txt").write_text("\n".join(_DOCKET_DOTTED_MONTH) + "\n", encoding="utf-8")
        rows = D.parse_rows(str(tmp / "Docket.txt"))
        procs = D.parse_proceedings(rows, D.build_referral_timeline(rows))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    got = sorted((p.bill, p.sched_date, p.sched_time, p.venue) for p in procs)
    want = [("HB273", "2000-02-23", "09:10", "SH 105 A"),
            ("SB39", "1999-02-17", "14:15", "LOB 104"),
            ("SB483", "2010-03-03", "13:30", "SH 100")]
    assert got == want, f"the dotted months' hearings are read as {got!r}, not {want!r}"
    return "ok", "SB 39 on 17 February 1999, HB 273 on 23 February 2000, SB 483 on 3 March 2010"


@check("data", "no Senate meeting line on disk whose month the clerk dotted is left without a day")
def _docket_dotted_month_on_disk():
    """_docket_dotted_month over every docket on this disk: a Senate line
    SENATE_SCHED_RE reads whose date opens with a dotted month ("Jan. 11",
    "Feb.23", "Mar. 3, 2010") must give _parse_date a day. 174 did not, 172
    of 1999-2000 and 2 of 2009-2010."""
    D = imp("docket_parser")
    if D is None:
        return "skip", "docket_parser.py will not import"
    files = sorted(Path(".").glob("Docket_db_*.txt")) + sorted(Path(".").glob("Docket_[0-9]*.txt"))
    if not files:
        return "skip", "no docket on this disk"
    seen, bad = 0, []
    for f in files:
        for r in D.parse_rows(str(f)):
            if (r["body"] or "").strip().upper() != "S":
                continue
            m = D.SENATE_SCHED_RE.search(D.extract_flags(r["desc"])[1])
            if not m or not re.match(r"[A-Za-z]{3,9}\.", m.group("date")):
                continue
            seen += 1
            if D._parse_date(m.group("date"), D._created(r)) is None:
                bad.append(f"{f.name}:{r['lineno']} {r['bill']} {m.group('date')!r}")
    assert not bad, f"{len(bad)} dotted Senate dates read as no day: " + "; ".join(bad[:6])
    return "ok", f"{seen:,} Senate meeting lines with a dotted month, every one dated"


@check("build", "a Senate hearing of 1999-2006 sits at the hour a later TIME CHANGE row gave its "
                "day, not the first notice's, and a history that voids it voids that hour",
       needs=("docket_parser", "narrative", "proceedings"))
def _senate_time_change(D, N, P):
    """SB 139 of 2005 was noticed for 1:30 on 22 February and moved to 2:00 by
    "Hearing; === TIME CHANGE === February 22, 2005"; SB 312 of 2000 for 1:00
    on 23 February and moved to 1:45 by "===TIME CHANGE=== Feb.23". A notice
    SENATE_SCHED_RE read kept the hour it stated, so proceedings.csv, which
    folds the two rows of one hearing into the one with the earlier hour, gave
    91 Senate sittings of 1999-2006 the first notice's hour. Every row of each
    hearing now carries the later hour.

    And SB 387 of 2000's hearing of 25 January, noticed for 3:40 and set for
    3:25 by "==TIME CHANGE== Jan. 25", was moved to 15 February: its history
    voided it at 3:40 alone, so the table's row, at 3:25, would have been drawn
    as a hearing that never sat (narrative._time_changed_clock)."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-time-change-"))
    try:
        (tmp / "Docket.txt").write_text("\n".join(_DOCKET_TIME_CHANGE) + "\n", encoding="utf-8")
        rows = D.parse_rows(str(tmp / "Docket.txt"))
        procs = D.parse_proceedings(rows, D.build_referral_timeline(rows))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = []
    got = sorted((p.bill, p.sched_date, p.sched_time) for p in procs)
    want = [("SB139", "2005-02-22", "14:00"), ("SB139", "2005-02-22", "14:00"),
            ("SB312", "2000-02-23", "13:45"),
            ("SB387", "2000-01-25", "15:25"), ("SB387", "2000-02-15", "15:30")]
    if got != want:
        bad.append(f"the hearings are read as {got!r}, not {want!r}")
    narr = _told_from_rows(N, "1999-2000", "SB387",
                           [x for x in _DOCKET_TIME_CHANGE if "|SB387|" in x])
    drawn = [(p.sched_date, p.sched_time) for p in procs if p.bill == "SB387"
             and not P.notice_only({"date": p.sched_date, "kind": p.kind, "body": p.body,
                                    "time": p.sched_time or ""}, narr)]
    if drawn != [("2000-02-15", "15:30")]:
        bad.append(f"SB 387 of 2000 has {drawn!r} drawn, not its hearing of 15 February alone "
                   f"(voided {narr.get('voided')!r})")
    assert not bad, "\n".join(bad)
    return "ok", ("SB 139 of 2005 at 2:00 on 22 February, SB 312 of 2000 at 1:45 on 23 February; "
                  "SB 387 of 2000's hearing of 25 January, at 3:25, left off as moved")


# Real rows: Docket_db_2003-2004.txt 16476-16478 (SB 339 of 2004) and
# 16830-16834 (SB 427 of 2004), Docket_db_2005-2006.txt 17879-17882 (SB 342 of
# 2006), Docket_db_2001-2002.txt 6354 and 6373-6376 (SB 164 of 2001) and
# 10049-10051 (SB 146 of 2001), Docket_db_1999-2000.txt 14367-14370 (HB 1548 of
# 2000).
_DOCKET_ROOM_CHANGE = [
    '2004|3037|01/07/2004 05:22:48 PM|SB339|S|Introduced and Referred to Judiciary; SJ 1, Pg.3|01/07/2004 05:22:48 PM',
    '2004|3037|01/08/2004 10:46:19 AM|SB339|S|Hearing; January 13, 2004, Room 105-A, SH, 10:15 a.m.; SC2|01/08/2004 10:46:19 AM',
    '2004|3037|01/12/2004 03:08:59 PM|SB339|S|Hearing; === ROOM CHANGE === January 13, 2004, Room 102, LOB, 10:15 a.m.|01/12/2004 03:08:59 PM',
    '2004|3066|01/07/2004 06:17:19 PM|SB427|S|Introduced and Referred to Public Institutions, Health & Human Services; SJ 1, Pg.8|01/07/2004 06:17:19 PM',
    '2004|3066|02/02/2004 03:54:42 PM|SB427|S|Hearing; February 17, 2004, Room 103, SH, 3:30 p.m.; SC6|02/02/2004 03:54:42 PM',
    '2004|3066|02/11/2004 04:39:40 PM|SB427|S|Hearing; === TIME CHANGE === February 17, 2004, Room 103, SH, 1:00 p.m.; SC7|02/11/2004 04:39:40 PM',
    '2004|3066|02/12/2004 12:45:27 PM|SB427|S|Hearing; === ROOM CHANGE === February 17, 2004, Room 100, SH, 1:00 p.m.; SC7|02/12/2004 12:45:27 PM',
    '2004|3066|02/13/2004 02:35:24 PM|SB427|S|Hearing; === ROOM CHANGE === February 17, 2004, Rooms 205-207, LOB 1:00 p.m.|02/13/2004 02:35:24 PM',
    '2006|2717|01/04/2006 12:18:47 PM|SB342|S|Introduced and Referred to Executive Departments and Administration; SJ 1, Pg.12|01/04/2006 12:18:47 PM',
    '2006|2717|01/04/2006 01:47:17 PM|SB342|S|Hearing; January 18, 2006, Room 102, LOB, 2:10 p.m.|01/04/2006 01:47:17 PM',
    '2006|2717|01/04/2006 02:54:29 PM|SB342|S|Hearing; === RESCHEDULED === January 19, 2006, Room 102, LOB, 2:10 p.m.; SC1A|01/04/2006 02:54:29 PM',
    '2006|2717|01/12/2006 12:39:12 PM|SB342|S|Hearing; === TIME CHANGE === ROOM CHANGE === January 19, 2006, Room 100, LOB, 1:30 p.m.; SC2|01/12/2006 12:39:12 PM',
    '2001|0824|02/22/2001 02:46:22 PM|SB164|S|Introduced and Ref. to Education; SJ 5, Pg.57|02/22/2001 02:46:22 PM',
    '2001|0824|06/14/2001 06:16:09 PM|SB164|S|Conference Committee Meeting; June 18, 2001, Room 105-A, SH, 10:00 a.m.|06/14/2001 06:16:09 PM',
    '2001|0824|06/19/2001 04:02:00 PM|SB164|S|Conference Committee Meeting; June 20, 2001, Room 103, SH, 9:00 a.m.|06/19/2001 04:02:00 PM',
    '2001|0824|06/20/2001 09:47:45 AM|SB164|S|Conference  Committe === ROOM AND TIME CHANGE === Meeting June 20, 2001, Room 207, LOB, 11:00 a.m|06/20/2001 09:47:45 AM',
    '2001|0824|06/20/2001 04:24:53 PM|SB164|S|Conference Committee Meeting; June 21, 2001, Room 207, LOB, 10:00 a.m.|06/20/2001 04:24:53 PM',
    '2002|0430|02/15/2001 11:37:29 AM|SB146|S|Introduced and Ref. to Wildlife & Recreation; SJ 4, Pg.46|02/15/2001 11:37:29 AM',
    '2002|0430|02/21/2001 06:07:59 PM|SB146|S|Hearing; March 6, 2001, Room 101, LOB, 10:15 a.m.; SC9|02/21/2001 06:07:59 PM',
    '2002|0430|02/28/2001 01:57:59 PM|SB146|S|Hearing; ===== ROOM CHANGE===== March 6, 2001, Representatives Hall, SH, 10:15 a.m.; SC10|02/28/2001 01:57:59 PM',
    '2000|2203|03/16/2000 11:33:33 AM|HB1548|S|Introduced and Ref. to Judiciary; SJ 6, Pg.196|03/16/2000 11:33:33 AM',
    '2000|2203|03/27/2000 05:08:28 PM|HB1548|S|Hearing ==CANCELLED==  April 17, Rooms 306 -- 308, LOB, 10:00 a.m.; SC19,|03/27/2000 05:08:28 PM',
    '2000|2203|03/31/2000 03:28:07 PM|HB1548|S|Hearing  == RESCHEDULED ==  April 24, Room Change  305 - 307, LOB, 10:00 a.m.; SC21, Pg.13|03/31/2000 03:28:07 PM',
    '2000|2203|04/19/2000 03:48:44 PM|HB1548|S|Hearing  April 24  == ROOM CHANGE  201-203, LOB == 10:00 a.m.; SC24|04/19/2000 03:48:44 PM',
]


@check("build", "a Senate sitting of 1999-2006 is in the room the latest ROOM CHANGE or TIME "
                "CHANGE row gave its day, on every row of it",
       needs=("docket_parser",))
def _senate_room_change(D):
    """The person's decision of 8 October 2026, on the review of the archived
    manifests. SB 339 of 2004 was noticed for SH 105-A on 13 January and moved
    by "Hearing; === ROOM CHANGE === January 13, 2004, Room 102, LOB"; SB 342
    of 2006 by "=== TIME CHANGE === ROOM CHANGE === January 19, 2006, Room 100,
    LOB, 1:30 p.m.", whose hour its notice took and whose room it did not.
    build_proceedings folds a sitting's rows into the first it reads, the
    notice, so 32 Senate sittings of 2001-2006 were in the room their notice
    gave. Every row of each now carries the room of the last such row, two
    room changes in a row (SB 427 of 2004) the second, a conference (SB 164 of
    2001) as well as a hearing, a hall (SB 146 of 2001) as well as a room, and
    the marks read off before the room is: HB 1548 of 2000's "== ROOM CHANGE
    201-203, LOB ==" was the room "LOB CHANGE 201-203"."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-room-change-"))
    try:
        (tmp / "Docket.txt").write_text("\n".join(_DOCKET_ROOM_CHANGE) + "\n", encoding="utf-8")
        rows = D.parse_rows(str(tmp / "Docket.txt"))
        procs = D.parse_proceedings(rows, D.build_referral_timeline(rows))
        D.build_sittings(procs)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    live = [p for p in procs if p.confidence != "X-cancelled"]
    bad = []
    for (_, bill, day), room in _ROOM_CHANGED.items():
        got = [p.venue for p in live if p.bill == bill and p.sched_date == day]
        if len(got) < 2 or set(got) != {room}:
            bad.append(f"{bill}'s sitting of {day} is read in {got!r}, not {room!r} on every row")
    hours = {(p.bill, p.sched_date): p.sched_time for p in live}
    for k, want in ((("SB342", "2006-01-19"), "13:30"), (("SB164", "2001-06-20"), "11:00"),
                    (("SB427", "2004-02-17"), "13:00")):
        if hours.get(k) != want:
            bad.append(f"{k[0]}'s sitting of {k[1]} is at {hours.get(k)!r}, not {want}")
    # The sittings no change row names keep their notice's room.
    for bill, day, room in (("SB342", "2006-01-18", "LOB 102"), ("SB164", "2001-06-18", "SH 105-A"),
                            ("SB164", "2001-06-21", "LOB 207")):
        got = [p.venue for p in live if p.bill == bill and p.sched_date == day]
        if got != [room]:
            bad.append(f"{bill}'s sitting of {day} is read in {got!r}, not {room!r}")
    assert not bad, "\n".join(bad)
    return "ok", (f"{len(_ROOM_CHANGED)} sittings in the room their latest change row gave them, "
                  "on every row")


# Real rows: Docket_2021-2022.txt 10218, 10231 and 10236-10242 (HB 355 of
# 2022), and Docket_2023-2024.txt 12396-12397 (HB 417 of 2023).
_DOCKET_CANCELLED_TWIN = [
    "2022|0518|1/9/2021 12:00:00 AM|HB355|H|Introduced (in recess of) 01/06/2021 and referred to Ways and Means HJ 2 P. 44|1/9/2021 12:00:00 AM",
    "2022|0518|1/18/2022 12:00:00 AM|HB355|S|Introduced 01/05/2022 and Referred to Ways and Means; SJ 2|1/18/2022 12:00:00 AM",
    "2022|0518|5/10/2022 12:00:00 AM|HB355|H|House Non-Concurs with Senate Amendment 2022-1131s and Requests CofC (Reps. Abrami, Spilsbury, Janigian, Ames): MA VV 05/05/2022 HJ 12|5/10/2022 12:00:00 AM",
    "2022|0518|5/12/2022 12:00:00 AM|HB355|S|Sen. Giuda Accedes to House Request for Committee of Conference, MA, VV; 05/12/2022; SJ 12|5/12/2022 12:00:00 AM",
    "2022|0518|5/12/2022 12:00:00 AM|HB355|S|President Appoints: Senators Giuda, Daniels, D'Allesandro; 05/12/2022; SJ 12|5/12/2022 12:00:00 AM",
    "2022|0518|5/16/2022 12:00:00 AM|HB355|H|Conference Committee Meeting: 05/16/2022 09:00 am LOB 202-204|5/16/2022 12:00:00 AM",
    "2022|0518|5/16/2022 12:00:00 AM|HB355|H|==CANCELLED== Conference Committee Meeting: 05/16/2022 09:00 am LOB 202-204|5/16/2022 12:00:00 AM",
    "2022|0518|5/17/2022 12:00:00 AM|HB355|H|==RECESSED== Conference Committee Meeting: 05/17/2022 11:00 am LOB 202-204|5/17/2022 12:00:00 AM",
    "2022|0518|5/18/2022 12:00:00 AM|HB355|H|Conference Committee Meeting: 05/18/2022 12:00 pm LOB 202-204|5/18/2022 12:00:00 AM",
]
_DOCKET_TWIN_SET_AGAIN = [
    "2023|0257|3/8/2023 12:00:00 AM|HB417|H|==CANCELLED== Executive Session: 03/15/2023 10:15 am LOB 305-307|3/8/2023 12:00:00 AM",
    "2023|0257|3/13/2023 12:00:00 AM|HB417|H|Executive Session: 03/15/2023 10:15 am LOB 305-307|3/13/2023 12:00:00 AM",
]


@check("build", "a notice its own cancelled twin of one stamp follows is a meeting called off, in "
                "the table and the history, and a twin entered before it is not",
       needs=("docket_parser", "narrative"))
def _cancelled_twin(D, N):
    """The person's decision of 8 October 2026: a cancelled meeting is not
    told. HB 355 of 2022's conference of 16 May is given twice at one stamp,
    plain and then "==CANCELLED==", word for word. The plain row was a
    conference drawn on the bill's page and the Calendar, which
    proceedings.notice_only never hides, and the history said a committee of
    conference "met on May 16, 2022, May 17, 2022 and May 18, 2022", since
    overtaken() reads no conference and no row of a midnight stamp is entered
    before another. HB 417 of 2023's executive session of 15 March was
    cancelled on 8 March and set down again on the 13th, and sat."""
    bad = []
    for lines, bill, want in ((_DOCKET_CANCELLED_TWIN, "HB355",
                               [("2022-05-17", "11:00"), ("2022-05-18", "12:00")]),
                              (_DOCKET_TWIN_SET_AGAIN, "HB417", [("2023-03-15", "10:15")])):
        tmp = Path(tempfile.mkdtemp(prefix="gr-twin-"))
        try:
            (tmp / "Docket.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            rows = D.parse_rows(str(tmp / "Docket.txt"))
            procs = D.parse_proceedings(rows, D.build_referral_timeline(rows))
            D.build_sittings(procs)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        live = [(p.sched_date, p.sched_time) for p in procs
                if p.confidence != "X-cancelled" and p.body == "H"]
        if live != want:
            bad.append(f"{bill}'s House meetings are read as {live!r}, not {want!r}")
    narr = _told_from_rows(N, "2021-2022", "HB355", _DOCKET_CANCELLED_TWIN)
    if "May 16, 2022" in narr["narrative"] or "May 17, 2022" not in narr["narrative"]:
        bad.append("HB 355's history tells the conference of 16 May or not that of the 17th: "
                   + narr["narrative"][narr["narrative"].find("committee of conference"):][:160])
    plain = [e for e in narr["events"] if e["date"] == "2022-05-16"
             and e["type"] == "conference_meeting"]
    if len(plain) != 2 or not all(e["cancelled"] for e in plain) \
            or not any(e.get("notice") and e.get("overtaken") == "cancelled" for e in plain):
        bad.append(f"HB 355's rows of 16 May are carried as {plain!r}, not a notice its twin "
                   "cancels beside the twin")
    narr = _told_from_rows(N, "2023-2024", "HB417", _DOCKET_TWIN_SET_AGAIN)
    if "March 15, 2023" not in narr["narrative"]:
        bad.append("HB 417's executive session of 15 March 2023, set down again after its "
                   "cancellation, is not told: " + narr["narrative"][:200])
    assert not bad, "\n".join(bad)
    return "ok", ("HB 355 of 2022's conference of 16 May called off by its twin, in the table and "
                  "the history; HB 417 of 2023's executive session set down again and told")


# Real rows: Docket_db_1999-2000.txt 18729-18731 (SB 362 of 2000), 13023-13024
# (HB 1337 of 2000) and 2267 and 2269 (HB 452 of 1999), Docket_db_2003-2004.txt
# 9175-9176 (SB 171 of 2003) and Docket_db_2005-2006.txt 4415-4416 (HB 199 of
# 2005).
_DOCKET_CLOCK_SEMICOLON = [
    "2000|2650|01/05/2000 12:10:17 PM|SB362|S|Introduced and Ref. to Transportation; SJ Convening Day, Pg. 10|01/05/2000 12:10:17 PM",
    "2000|2650|01/06/2000 03:23:09 PM|SB362|S|Hearing , Feb. 8 , Room 104 , LOB , 3:00 p.m.; SC1, Pg.8|01/06/2000 03:23:09 PM",
    "2000|2650|01/28/2000 12:55:52 PM|SB362|S|==TIME CHANGE== Hearing, Feb. 8, Room 104, LOB, 2;50 p.m.; SC6, Pg.4|01/28/2000 12:55:52 PM",
    "2000|2061|02/03/2000 11:47:25 AM|HB1337|S|Introduced and Ref. to Public Institutions, Health & Human Services; SJ 2, [ See Perm. Journal ]|02/03/2000 11:47:25 AM",
    "2000|2061|02/23/2000 02:19:41 PM|HB1337|S|Hearing  April 4, Room 102, LOB, 2;00 p.m.; SC13, Pg.4|02/23/2000 02:19:41 PM",
    "1999|0278|01/28/1999 09:05:54 AM|HB452|H|Introduced and ref to Health HS&EA;  HJ18, p270|01/28/1999 09:05:54 AM",
    "1999|0278|02/04/1999 02:08:03 PM|HB452|H|Hearing  Feb 9  2;00  Rm205,LOB|02/04/1999 02:08:03 PM",
    "2003|1139|01/30/2003 10:18:09 AM|SB171|S|Introduced and Ref. to Wildlife & Recreation; SJ 3, Pg.39|01/30/2003 10:18:09 AM",
    "2003|1139|02/07/2003 02:55:07 PM|SB171|S|Hearing; February 18, 2003, Room 104, LOB, 1;30 p.m.; SC9|02/07/2003 02:55:07 PM",
    "2005|0607|03/17/2005 10:44:32 AM|HB199|S|Introduced and Referred to Environment and Wildlife; SJ 9, Pg.139|03/17/2005 10:44:32 AM",
    "2005|0607|03/29/2005 08:04:39 AM|HB199|S|Hearing; April 5, 2005, Room 103, LOB, 2;20 p.m.; SC14|03/29/2005 08:04:39 AM",
]


@check("build", "a meeting's hour typed with a semicolon for the colon is read, and the hearing "
                "it sets is in the table at that hour", needs=("docket_parser",))
def _clock_semicolon(D):
    """The person's decision of 8 October 2026, on the review of the archived
    manifests. "==TIME CHANGE== Hearing, Feb. 8, Room 104, LOB, 2;50 p.m."
    (SB 362 of 2000) was read by no pattern, so the hearing kept its notice's
    3:00; HB 1337 of 2000's "2;00 p.m.", SB 171 of 2003's "1;30 p.m.", HB 199
    of 2005's "2;20 p.m." and HB 452 of 1999's House "Hearing  Feb 9  2;00
    Rm205,LOB" were hearings each bill's history tells and the table had no
    row for. Every row of each now gives the hour as the colon would."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-semicolon-"))
    try:
        (tmp / "Docket.txt").write_text("\n".join(_DOCKET_CLOCK_SEMICOLON) + "\n", encoding="utf-8")
        rows = D.parse_rows(str(tmp / "Docket.txt"))
        procs = D.parse_proceedings(rows, D.build_referral_timeline(rows))
        D.build_sittings(procs)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    got = sorted({(p.bill, p.body, p.sched_date, p.sched_time) for p in procs
                  if p.confidence != "X-cancelled"})
    want = sorted((b, ch, d, t) for (_, b, ch, d), t in _CLOCK_SEMICOLON.items())
    assert got == want, f"the hearings are read as {got!r}, not {want!r}"
    return "ok", f"{len(want)} hearings at the hour their semicolon gives"


# Real rows: Docket_db_1999-2000.txt 1440-1441 (HB 208 of 1999) and 1815-1816
# (HB 214 of 1999), Docket_db_2001-2002.txt 3249-3251 (HB 390 of 2001).
_DOCKET_CLERKS_COMMITTEES = [
    "1999|0188|04/14/1999 01:41:38 PM|HB208|S|Introduction and referring to Energy & Economic Department;  SJ 13, P 284|04/14/1999 01:41:38 PM",
    "1999|0188|04/21/1999 10:31:56 AM|HB208|S|Hearing, 4/27/99, Room 105-A, SH, 2:45 p.m.|04/21/1999 10:31:56 AM",
    "1999|0233|03/23/1999 02:13:14 PM|HB214|S|Introduction and referring to Public Institutions & Health Humans Services; SJ 8, P 111|03/23/1999 02:13:14 PM",
    "1999|0233|04/02/1999 08:33:10 AM|HB214|S|Hearing, 4/27/99, Room 102, LOB, 1:20 p.m.|04/02/1999 08:33:10 AM",
    "2001|0455|04/05/2001 03:56:48 PM|HB390|S|Introduced and Ref. to Judiciary; SJ 8, Pg.100|04/05/2001 03:56:48 PM",
    "2001|0455|05/09/2001 06:21:23 PM|HB390|S|Sen. Gordon Motion to Vacate HB390 From Judiciary to P I, H & H S;  MA, VV; SJ 12, Pg.232|05/09/2001 06:21:23 PM",
    "2001|0455|05/10/2001 03:15:56 PM|HB390|S|Hearing, May 29, 2001, Room 101, LOB, 1:45 p.m.; SC23-A|05/10/2001 03:15:56 PM",
]


@check("build", "the three Senate hearings of 1999-2001 whose committee the clerk misspelled or "
                "shortened are filed under the committee's name", needs=("docket_parser", "committee_names"))
def _clerks_committee_names(D, CN):
    """The review of the archived manifests (8 October 2026): docket_parser
    now reads the Senate of 1999-2006's introductions and vacates, so three
    hearings name their committee in the clerk's words -- "Public
    Institutions and Health Humans Services" (HB 214 of 1999), "Energy and
    Economic Department" (HB 208 of 1999) and "P I, H and H S" (HB 390 of
    2001, "From Judiciary to P I, H & H S") -- which committee_names.official
    gave back as written, so the hearing card printed the clerk's words and
    linked to no committee's page. The General Court files each under S14 or
    S18 (db/past/PastLegislation.psv); the aliases write the names those
    codes carried. On main before the night that reads the manifests sent
    with them, or the cards print the shorthand until it is."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-clerks-committees-"))
    try:
        (tmp / "Docket.txt").write_text("\n".join(_DOCKET_CLERKS_COMMITTEES) + "\n", encoding="utf-8")
        rows = D.parse_rows(str(tmp / "Docket.txt"))
        procs = D.parse_proceedings(rows, D.build_referral_timeline(rows))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    term = {"HB208": "1999-2000", "HB214": "1999-2000", "HB390": "2001-2002"}
    got = {(term[p.bill], p.bill, p.sched_date): CN.official(p.committee, "S", term[p.bill])
           for p in procs}
    assert got == _CLERKS_COMMITTEES, f"the hearings are filed under {got!r}"
    return "ok", "three hearings under the names their committees had then"


# ============================================================== code: markers ==

def _fixture(root):
    """A throwaway work tree: one House-style video, one Senate-style."""
    (root / "work" / "PFHOUSE").mkdir(parents=True)
    (root / "work" / "PFSENATE").mkdir(parents=True)

    def caps(lines, secs=6.0):
        out, t = [], 0.0
        for txt in lines:
            out.append({"start": round(t, 1), "end": round(t + secs, 1), "text": txt})
            t += secs
        return out

    h = ["good morning the committee will come to order"] + \
        ["housekeeping"] * 10 + \
        ["we are going to open the public hearing for House Bill 1082 enabling "
         "municipalities"] + ["testimony on HB 1082"] * 20 + \
        ["I'm closing the public hearing for HP 1082 and turning over the gavel"] + \
        ["a pause"] * 5
    (root / "work" / "PFHOUSE" / "transcript.json").write_text(
        json.dumps(caps(h)), encoding="utf-8")
    (root / "work" / "PFHOUSE" / "segments.json").write_text(json.dumps([
        {"bill": "HB1082", "kind": "public hearing", "located": True,
         "why_not": "", "short": False, "tolerance": 300, "dp_start": 0,
         "dp_end": 900, "start": 150.0, "end": 330.0, "mentions_inside": 4,
         "mentions_total": 6, "purity": 0.6}]), encoding="utf-8")

    # Two bills: the first has a loose opening the chair announced, the second
    # has none at all. That second one is the case worth testing, because it is
    # the common Senate shape -- a stated close and an inferred start.
    s = ["senate judiciary will come to order"] + ["introductions"] * 10 + \
        ["Senate Judiciary is now hearing House Bill 1637"] + \
        ["testimony regarding 1637"] * 18 + \
        ["Does anyone else wish to testify on 1637? Seeing no one, that'll end "
         "the hearing"] + \
        ["we will take up the next matter"] + ["testimony about 1416"] * 12 + \
        ["Does anyone else wish to testify on 1416? Seeing none, that will "
         "close the hearing"]
    (root / "work" / "PFSENATE" / "transcript.json").write_text(
        json.dumps(caps(s)), encoding="utf-8")
    (root / "work" / "PFSENATE" / "segments.json").write_text(json.dumps([
        {"bill": "HB1637", "kind": "hearing", "located": True, "why_not": "",
         "short": False, "tolerance": 900, "dp_start": 0, "dp_end": 300,
         "start": 120.0, "end": 260.0, "mentions_inside": 3,
         "mentions_total": 5, "purity": 0.5},
        {"bill": "HB1416", "kind": "hearing", "located": True, "why_not": "",
         "short": False, "tolerance": 900, "dp_start": 300, "dp_end": 600,
         "start": 320.0, "end": 500.0, "mentions_inside": 2,
         "mentions_total": 3, "purity": 0.4}]), encoding="utf-8")

    rows = [{"bill": "HB1082", "video_id": "PFHOUSE", "proceeding": "public hearing",
             "sched_date": "2026-02-03", "sched_time": "10:00",
             "committee": "Election Law", "venue": "LOB 306", "body": "H"},
            {"bill": "HB1637", "video_id": "PFSENATE", "proceeding": "hearing",
             "sched_date": "2026-04-01", "sched_time": "09:00",
             "committee": "Judiciary", "venue": "SH 100", "body": "S"},
            {"bill": "HB1416", "video_id": "PFSENATE", "proceeding": "hearing",
             "sched_date": "2026-04-01", "sched_time": "10:15",
             "committee": "Judiciary", "venue": "SH 100", "body": "S"}]
    with open(root / "manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def _run_markers(root, *flags):
    return _run(
        [sys.executable, _paths.script("apply_markers.py"), "--workdir", str(root / "work"),
         "--manifest", str(root / "manifest.csv"), *flags],
        capture_output=True, text=True, timeout=180)


@check("markers", "a whisper transcript is read, not counted as silence",
       needs=("segment_markers",))
def _whisper_transcript(segment_markers):
    """Every whisper-transcribed recording read as zero words.

    read_words parsed only YouTube's json3 {"events": [...]} shape.
    transcribe_and_align writes whisper's output as a LIST of
    {"start","end","text"}, so those folders returned nothing and were counted
    under "no captions" -- silence and failure looking the same again. Twelve
    folders were already dark this way, and the recordings YouTube has no
    captions for can only ever arrive in this shape.
    """
    d = Path(tempfile.mkdtemp())
    try:
        (d / "transcript.json").write_text(json.dumps([
            {"start": 462.8, "end": 465.2,
             "text": "If you would please rise for the pledge"},
            {"start": 610.0, "end": 616.0,
             "text": "we will open the hearing on House Bill 1123"},
        ]), encoding="utf-8")
        w = segment_markers.read_words(d)
        assert w, "a whisper transcript still reads as zero words"
        assert len(w) == 17, f"{len(w)} words, expected 17"
        assert w[0] == (462.8, "If"), w[0]
        # Per LINE, not per word: every word of a sentence carries the
        # sentence's start, which is the honest resolution whisper gives.
        assert w[7][0] == 462.8, w[7]
        assert w[8] == (610.0, "we"), w[8]
        return "ok", f"{len(w)} words off a whisper transcript"
    finally:
        shutil.rmtree(d, ignore_errors=True)


@check("markers", "the clustering fallback on one fixture: apply_markers reports and changes "
                  "nothing, --apply patches with a backup and repeats safely, and verify_batch "
                  "prints sub-minute bands")
def _markers_fallback():
    """THE SUPERSEDED CLUSTERING PATH, KEPT, AND CHECKED IN ONE RUN (6 October
    2026). build_all.py runs apply_markers.py only with --with-superseded: it
    is the fallback for recordings segment_markers.py finds nothing on, and
    the person decided to keep it. Until this date it had three checks, each
    building the same fixture of two recordings and running apply_markers
    again on it -- the report-only run, --apply twice, and verify_batch.py
    over an applied tree. They are one fixture and one sequence now, with
    every assertion the three made, in the order a person would run them:

      1. a run without --apply exits 0, finds the stated boundaries and
         leaves segments.json byte for byte as it was;
      2. --apply exits 0, keeps segments.pre_markers.json, marks the House
         hearing's two ends stated at a 30-second tolerance, and a second
         --apply moves neither end nor the tolerance; the Senate bill whose
         close alone was announced has its end stated, its start NOT stated,
         and a tolerance narrowed below the clustering's 900 seconds;
      3. verify_batch.py, over that applied tree, exits 0 and prints a band
         in seconds -- a 30-second tolerance printed as "+/- 0 min" was the
         bug it was written for.

    verify_batch.py absent skips the check, as its own check did, rather than
    passing on the first two parts alone.
    """
    if not _paths.locate("apply_markers.py").exists():
        return "skip", "apply_markers.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _fixture(root)
        p = root / "work" / "PFHOUSE" / "segments.json"

        # 1. Report only: it finds the boundaries and writes nothing.
        before = p.read_text(encoding="utf-8")
        r = _run_markers(root)
        assert r.returncode == 0, (r.stderr or r.stdout)[-200:]
        assert "stated boundaries found" in r.stdout, r.stdout[-200:]
        assert p.read_text(encoding="utf-8") == before, \
            "the report-only run rewrote segments.json"
        found = next(l for l in r.stdout.splitlines() if "stated boundaries found" in l)

        # 2. --apply patches, keeps a backup, and a second run moves nothing.
        assert _run_markers(root, "--apply").returncode == 0
        first = json.loads(p.read_text(encoding="utf-8"))[0]
        assert (root / "work" / "PFHOUSE" / "segments.pre_markers.json").exists(), \
            "no backup was written"
        assert first.get("start_stated") and first.get("end_stated"), first
        assert first["tolerance"] == 30, first["tolerance"]
        assert _run_markers(root, "--apply").returncode == 0
        second = json.loads(p.read_text(encoding="utf-8"))[0]
        assert (first["start"], first["end"], first["tolerance"]) == \
               (second["start"], second["end"], second["tolerance"]), \
               "a second --apply moved the boundaries"
        sen = json.loads((root / "work" / "PFSENATE" / "segments.json")
                         .read_text(encoding="utf-8"))
        closeonly = next((s for s in sen if s["bill"] == "HB1416"), None)
        assert closeonly, "the second Senate bill went missing"
        assert closeonly.get("end_stated"), "its stated close was not adopted"
        assert not closeonly.get("start_stated"), \
            "an unannounced Senate opening was reported as stated"
        assert closeonly["tolerance"] < 900, \
            "the stated close should narrow the start's tolerance"

        # 3. verify_batch over the applied tree prints a sub-minute band.
        if not _paths.locate("verify_batch.py").exists():
            return "skip", ("apply_markers passed; verify_batch.py is not here, so its "
                            "bands were not read")
        r = _run([sys.executable, _paths.script("verify_batch.py"),
                  "--work", str(root / "work"),
                  "--manifest", str(root / "manifest.csv")],
                 capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout)[-160:]
        assert "sec" in r.stdout, ("no sub-minute band; a 30s tolerance would "
                                   "print as '+/- 0 min'")
        band = next(l.strip() for l in r.stdout.splitlines() if "sec" in l)
        return "ok", (f"{found.strip()}; House both ends stated at +/-30s, Senate close "
                      f"stated and start still estimated; verify_batch: {band}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# SECONDS AS A CLOCK HAVE ONE HOME (the refactor's finding 8, 20 November 2026): proceedings.hms.
# Each of these wrote the rule out for itself until then, and each gave the home's answer on all
# 985,983 real inputs it was run on (proceedings.csv's offsets, review/'s times, 150 recordings'
# caption starts); (file, the name it is bound to, how it reads the home):
#   from   `from proceedings import hms` (as the name), and no def of the name
#   call   a def of the name whose body calls P.hms and writes no clock of its own: the copy kept
#          how it reads a missing value (apply_markers: none is 0:00:00; review: "" for none)
_CLOCK_READERS = (
    ("src/hearings/verify_batch.py", "hms", "from"),
    ("src/hearings/gap_excerpts.py", "hms", "from"),
    ("src/hearings/floor_markers.py", "hms", "from"),
    ("src/fetch/youtube/transcribe_and_align.py", "hhmmss", "from"),
    ("src/hearings/apply_markers.py", "hms", "call"),
    ("src/checks/review.py", "_hms", "call"),
)
# The clock written out ("{s // 3600}:{...}"), which only the home and these may write: each is
# a different rule, said here.
_CLOCK_OTHERS = {
    "src/hearings/caption_span.py": "rounds to the nearest second, where the home cuts to the second "
                                    "a moment is in (482,236 of the 985,983 real inputs differ by one)",
}
_CLOCK_WRITTEN = re.compile(r"\{\s*\(?\s*\w+\s*\)?\s*//\s*3600\s*\}\s*:")


def _clock_reader_faults(tree, name, how):
    """What is wrong with `name`'s reading of proceedings.hms in a parsed file; [] where none."""
    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    if how == "from":
        took = [n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == "proceedings"
                and any(a.name == "hms" and (a.asname or a.name) == name for a in n.names)]
        return ([] if took else [f"no `from proceedings import hms` binds {name}"]) + \
               [f"line {d.lineno} defines {name} again" for d in defs]
    if len(defs) != 1:
        return [f"{name} is defined {len(defs)} times, not once"]
    calls = [n for n in ast.walk(defs[0]) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "hms" and isinstance(n.func.value, ast.Name) and n.func.value.id == "P"]
    own = [n.lineno for n in ast.walk(defs[0]) if isinstance(n, ast.Constant) and isinstance(n.value, int)
           and n.value == 3600]
    return ([] if calls else [f"{name} does not call P.hms"]) + [f"line {n} works out hours itself" for n in own]


@check("markers", "seconds into a recording are written as a clock by proceedings.hms alone: the hearings "
                  "tools and the bench read it, and no copy of the rule is written again")
def _seconds_clock_one_home():
    """SECONDS AS A CLOCK, ONE HOME (finding 8 of stage0-code.md, "hms in 9 modules"). The rule
    "1:02:03", the hours unpadded and the second a moment is in, was written ten times; it is
    proceedings.hms now, and each copy _CLOCK_READERS names reads it, the two that read a missing
    value their own way keeping that and nothing else. Held: each reader binds or calls the home
    and writes no hours of its own; no code file outside the suite and the tests writes the clock
    out ("{s // 3600}:") but the home and _CLOCK_OTHERS, each a different rule said there (a
    session day's "01:02:03" is another form, and the fetchers' "1h 02m" another); and the home
    gives the old formula's answer over two days of seconds. Planted, each must be refused: the
    old def written back, a reader that works out its own hours, the clock written inline."""
    from pf_core import _in_suite, _parsed
    import proceedings as P
    for path, name, how in _CLOCK_READERS:
        faults = _clock_reader_faults(_parsed(_paths.ROOT / path), name, how)
        assert not faults, f"{path}: " + "; ".join(faults) + " (read proceedings.hms)"
    stray = []
    for f in _paths.code_files("*.py"):
        rel = f.relative_to(_paths.ROOT).as_posix()
        if _in_suite(f) or "tests" in f.relative_to(_paths.ROOT).parts or rel in _CLOCK_OTHERS \
                or rel == "src/lib/proceedings.py":
            continue
        for i, line in enumerate(_source(f, errors="replace").splitlines(), 1):
            if _CLOCK_WRITTEN.search(line):
                stray.append(f"{rel}:{i}")
    assert not stray, ("seconds written out as a clock again: " + ", ".join(stray[:8])
                       + ". Call proceedings.hms, or say in _CLOCK_OTHERS why it is another rule")
    for path in _CLOCK_OTHERS:
        assert any(_CLOCK_WRITTEN.search(l) for l in _source(_paths.ROOT / path).splitlines()), \
            f"{path} no longer writes its own clock: take it off _CLOCK_OTHERS"
    for x in range(0, 2 * 86400, 7):
        s = int(x + 0.9)
        assert P.hms(x + 0.9) == f"{s//3600}:{(s%3600)//60:02d}:{s%60:02d}", (
            f"proceedings.hms({x + 0.9}) is {P.hms(x + 0.9)!r}: the clock is the second a moment is in")
    assert [P.hms(v) for v in (0, 59.99, 3723.9, 36000)] == ["0:00:00", "0:00:59", "1:02:03", "10:00:00"]
    for planted, name, how in (
            ('def hms(s):\n    s = int(s)\n    return f"{s//3600}:{(s%3600)//60:02d}:{s%60:02d}"\n', "hms", "from"),
            ('from proceedings import hms\ndef hms(s):\n    return str(s)\n', "hms", "from"),
            ('def hms(s):\n    return P.hms(s) if s else f"{s // 3600}"\n', "hms", "call"),
            ('def _hms(s):\n    return str(s)\n', "_hms", "call")):
        assert _clock_reader_faults(ast.parse(planted), name, how), f"a reader writing its own clock was missed: {planted!r}"
    assert not _clock_reader_faults(ast.parse("from proceedings import hms as hhmmss\n"), "hhmmss", "from")
    for line in ('print(f"{t//3600}:{(t%3600)//60:02d}:{t%60:02d}")', 'x = f"{s // 3600}:{s % 3600 // 60:02d}"'):
        assert _CLOCK_WRITTEN.search(line), f"an inline clock was missed: {line}"
    assert not _CLOCK_WRITTEN.search('f"{x // 3600:02d}:{x % 3600 // 60:02d}"')
    return "ok", (f"{len(_CLOCK_READERS)} readers take proceedings.hms, no clock written out anywhere else but "
                  f"{len(_CLOCK_OTHERS)} other rule (caption_span's nearest second); the home is the old formula "
                  "over two days of seconds, and each planted copy is refused")


@check("markers", "segment_markers on a few recordings keeps every other "
                  "one, their consent calendars and sequences included")
def _markers_merge_siblings():
    """A writer run on a subset must not destroy the rest.

    segment_markers merged recordings one by one but replaced _absent and
    _sequence whole, so a run over one floor session left _absent holding
    that session alone. build_site_v2 reads _absent to say a bill passed on
    the consent calendar -- 2,071 stations on 25 September -- and a machine
    holding only a few recordings' captions, as the nightly's does, is that
    subset on every run. The phrases below were spoken: the clerk's reading
    is segment_markers' own quotation, the chair's is in tests/test_markers.
    """
    if not _paths.locate("segment_markers.py").exists():
        return "skip", "segment_markers.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "data").mkdir()
        (root / "data" / "bills.json").write_text(json.dumps(
            {"2025-2026": {"SB408": {"id": "SB408", "title": "x"}}}),
            encoding="utf-8")
        cols = ["term", "bill", "body", "kind", "date", "time", "committee",
                "venue", "video_id", "video_title", "stream_start",
                "predicted_offset", "match", "debate_end", "window_start",
                "precise", "motions", "tallies", "whole_video", "source"]
        rows = [("SB408", "S", "floor debate", "PFFLOOR"),
                ("SB409", "S", "floor debate", "PFFLOOR"),
                ("HB1491", "H", "public hearing", "PFCOMM"),
                ("HB77", "H", "public hearing", "PFOTHER")]
        with open(root / "proceedings.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for bill, body, kind, vid in rows:
                w.writerow({"term": "2025-2026", "bill": bill, "body": body,
                            "kind": kind, "date": "2026-03-05",
                            "video_id": vid, "source": "docket"})
        for vid, lines in (
                ("PFFLOOR", ["the Senate will come to order"] * 3 + [
                    "Majority of the Committee on Finance to which was "
                    "referred Senate Bill 408, relative to insurance coverage "
                    "for prosthetics, having considered the same, report the "
                    "same with the following amendment"]
                    + ["the ayes have it"] * 3),
                ("PFCOMM", ["good morning"] * 3
                 + ["I am opening the hearing on House Bill 1491"]
                 + ["thank you mister chair"] * 4)):
            (root / "work" / vid).mkdir(parents=True)
            (root / "work" / vid / "captions.en.json3").write_text(
                json.dumps(_json3(lines)), encoding="utf-8")
        other = {"HB77": [{"start": 60.0, "end": None, "how": "number",
                           "what": "hearing", "said": "x"}]}
        prior = {"PFOTHER": other,
                 "_absent": {"PFOTHER": ["HB88"], "PFFLOOR": ["SB408", "SB409"],
                             "PFCOMM": ["HB5"]},
                 "_sequence": {"PFOTHER": [{"bill": "HB77", "start": 60.0}]}}
        (root / "candidate_segments.json").write_text(json.dumps(prior),
                                                      encoding="utf-8")
        env = dict(os.environ, GRANITE_PROCEEDINGS=str(root / "proceedings.csv"))
        r = _run([sys.executable, _paths.script("segment_markers.py"),
                  "--transcript", "work/PFFLOOR", "work/PFCOMM", "--data", "data",
                  "--quiet", "--cache", "cache.json"],
                 cwd=str(root), env=env, capture_output=True, text=True,
                 timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout)[-300:]
        got = json.loads((root / "candidate_segments.json").read_text(encoding="utf-8"))
        assert got.get("PFOTHER") == other, "a recording not read was changed"
        assert "SB408" in (got.get("PFFLOOR") or {}), \
            f"the clerk's reading was not found: {got.get('PFFLOOR')}"
        assert "HB1491" in (got.get("PFCOMM") or {}), got.get("PFCOMM")
        ab = got.get("_absent") or {}
        assert ab.get("PFOTHER") == ["HB88"], \
            f"another recording's consent calendar went missing: {ab}"
        assert ab.get("PFFLOOR") == ["SB409"], \
            f"the re-read floor session's own answer did not replace its old one: {ab}"
        assert "PFCOMM" not in ab, \
            "a recording re-read with no absent bill kept its stale list"
        sq = got.get("_sequence") or {}
        assert sq.get("PFOTHER") == prior["_sequence"]["PFOTHER"], \
            f"another recording's sequence went missing: {sorted(sq)}"
        assert "PFFLOOR" in sq and "PFCOMM" in sq, sorted(sq)
        return "ok", ("two recordings re-read; the third, its consent calendar "
                      "and its sequence kept; a stale list replaced, one removed")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _markers_fixture(root, bills, rows, captions):
    """A folder segment_markers can run in: data/bills.json as given, a
    proceedings.csv of (term, bill, body, kind, video) rows, and a json3
    caption file per recording. Returns the environment to run it with."""
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data" / "bills.json").write_text(json.dumps(bills), encoding="utf-8")
    cols = ["term", "bill", "body", "kind", "date", "time", "committee", "venue",
            "video_id", "video_title", "stream_start", "predicted_offset", "match",
            "debate_end", "window_start", "precise", "motions", "tallies",
            "whole_video", "source"]
    with open(root / "proceedings.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for term, bill, body, kind, vid in rows:
            w.writerow({"term": term, "bill": bill, "body": body, "kind": kind,
                        "date": "2026-03-05", "video_id": vid, "source": "docket"})
    for vid, lines in captions.items():
        (root / "work" / vid).mkdir(parents=True, exist_ok=True)
        (root / "work" / vid / "captions.en.json3").write_text(
            json.dumps(_json3(lines)), encoding="utf-8")
    return dict(os.environ, GRANITE_PROCEEDINGS=str(root / "proceedings.csv"))


@check("markers", "segment_markers reads each recording's titles from its own term",
       needs=("segment_markers",))
def _markers_titles_by_term(segment_markers):
    """data/bills.json is {term: {bill: record}}, and segment_markers read it
    as a list of bills, so its title lookup was {None: ""} and the title
    fallback placed nothing from the day the file was keyed by term until 17
    October 2026. The clerk's reading below was spoken (itJRViVSJqk 5:33:24)
    with the number captioned "5604": only the title of the term's HB 564
    places it, and another term's HB 564 must not."""
    if not _paths.locate("segment_markers.py").exists():
        return "skip", "segment_markers.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        title = "relative to the adoption of school administrative unit budgets"
        bills = {"2025-2026": {"HB564": {"title": title}, "HB56": {"title": "relative to the state forester"}},
                 "2023-2024": {"HB564": {"title": "relative to the cutting of timber"}}}
        reading = ["the senate will come to order"] * 3 + [
            "Majority of the committee on education policy and administration to "
            "which was referred House Bill 5604, an act relative to the adoption of "
            "school administrative unit budgets, considered the same"] + ["thank you"] * 3
        env = _markers_fixture(
            root, bills,
            [("2025-2026", "HB564", "S", "floor debate", "PFNOW"),
             ("2025-2026", "HB56", "S", "floor debate", "PFNOW"),
             ("2023-2024", "HB564", "S", "floor debate", "PFTHEN"),
             ("2023-2024", "HB56", "S", "floor debate", "PFTHEN")],
            {"PFNOW": reading, "PFTHEN": reading})
        r = _run([sys.executable, _paths.script("segment_markers.py"),
                  "--transcript", "work/PFNOW", "work/PFTHEN", "--data", "data",
                  "--quiet", "--cache", "cache.json"],
                 cwd=str(root), env=env, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout)[-300:]
        got = json.loads((root / "candidate_segments.json").read_text(encoding="utf-8"))
        now = (got.get("PFNOW") or {}).get("HB564") or []
        assert now and now[0].get("how") == "title", (
            f"the clerk's reading of HB 564 was not placed by its title: {got.get('PFNOW')}")
        assert "HB564" not in (got.get("PFTHEN") or {}), (
            "a 2023-2024 recording was placed by the 2025-2026 bill's title")
        assert "bill titles across 2 terms" in r.stdout, r.stdout[-300:]
        return "ok", "the title of the recording's own term places a garbled number; another term's does not"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("markers", "segment_markers --gaps and --phrases write nothing the build reads",
       needs=("segment_markers",))
def _markers_diagnostics_write_nothing(segment_markers):
    """--gaps and --phrases are questions asked of the captions, and they
    rewrote --out (candidate_segments.json, which build_site_v2 publishes
    from) and missing_phrases.txt in the working folder (17 October 2026).
    Run on a fixture with a candidate file already there, each leaves the
    folder as it was; --phrases-out is the one place counting goes."""
    if not _paths.locate("segment_markers.py").exists():
        return "skip", "segment_markers.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        env = _markers_fixture(
            root, {"2025-2026": {"HB1491": {"title": "relative to x"},
                                 "HB77": {"title": "relative to y"}}},
            [("2025-2026", "HB1491", "H", "public hearing", "PFCOMM"),
             ("2025-2026", "HB77", "H", "public hearing", "PFCOMM")],
            {"PFCOMM": ["good morning"] * 3 + ["I am opening the hearing on House Bill 1491"]
             + ["thank you mister chair"] * 4})
        prior = json.dumps({"PFCOMM": {"HB5": [{"start": 1.0, "end": None}]}})
        (root / "candidate_segments.json").write_text(prior, encoding="utf-8")
        before = sorted(p.name for p in root.iterdir())
        for flag in ("--gaps", "--phrases"):
            r = _run([sys.executable, _paths.script("segment_markers.py"),
                      "--transcript", "work/PFCOMM", "--data", "data", flag,
                      "--cache", "cache.json"],
                     cwd=str(root), env=env, capture_output=True, text=True, timeout=120)
            assert r.returncode == 0, (r.stderr or r.stdout)[-300:]
            assert (root / "candidate_segments.json").read_text(encoding="utf-8") == prior, (
                f"segment_markers {flag} rewrote candidate_segments.json")
            assert sorted(p.name for p in root.iterdir()) == before, (
                f"segment_markers {flag} wrote {sorted(set(p.name for p in root.iterdir()) - set(before))}")
        r = _run([sys.executable, _paths.script("segment_markers.py"),
                  "--transcript", "work/PFCOMM", "--data", "data", "--phrases",
                  "--phrases-out", "counted.txt", "--cache", "cache.json"],
                 cwd=str(root), env=env, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0 and (root / "counted.txt").exists(), (
            "--phrases-out did not write where it was told")
        return "ok", "--gaps and --phrases leave the folder as it was; --phrases-out writes its file"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("markers", "segment_markers lists the clustered placements whose bill is named just "
                  "before them", needs=("segment_markers",))
def _markers_named_before(segment_markers):
    """build_site_v2 withholds a clustering placement with no mention of its
    bill inside, and 27 of 372 had it named in the minute before (after
    review, 17 October 2026): on 120gOWa2Jl0 the chair said "On to House Bill
    1315 relative to the sale of tobacco products" at 3:42:30 and the slot
    began at 3:43:00. The build has no captions, so segment_markers writes
    the answer as _named_before, and a later run on another recording keeps
    it. The words below were spoken there."""
    if not _paths.locate("segment_markers.py").exists():
        return "skip", "segment_markers.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        env = _markers_fixture(
            root, {"2025-2026": {"HB1315": {"title": "relative to the sale of tobacco products"},
                                 "HB1281": {"title": "relative to comfort dogs"}}},
            [("2025-2026", "HB1315", "H", "executive session", "PFEXEC"),
             ("2025-2026", "HB1281", "H", "executive session", "PFEXEC"),
             ("2025-2026", "HB1281", "H", "executive session", "PFOTHER")],
            {"PFEXEC": ["move unanimously."] * 3
             + ["On to House Bill 1315 relative to the sale of tobacco products,"]
             + ["Representative Hunt, second by Representative Patusk moves to pass."] * 3,
             "PFOTHER": ["good morning"] * 3})
        # The aligner's slots: HB 1315's 30 s after its mention, HB 1281's
        # nowhere near one.
        (root / "work" / "PFEXEC" / "segments.json").write_text(json.dumps([
            {"bill": "HB1315", "kind": "executive session", "located": True,
             "start": 30.0, "end": 60.0, "mentions_inside": 0},
            {"bill": "HB1281", "kind": "executive session", "located": True,
             "start": 400.0, "end": 430.0, "mentions_inside": 0}]), encoding="utf-8")
        cmd = [sys.executable, _paths.script("segment_markers.py"), "--data", "data",
               "--quiet", "--cache", "cache.json", "--transcript"]
        r = _run(cmd + ["work/PFEXEC"], cwd=str(root), env=env, capture_output=True,
                 text=True, timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout)[-300:]
        got = json.loads((root / "candidate_segments.json").read_text(encoding="utf-8"))
        assert (got.get("_named_before") or {}).get("PFEXEC") == ["HB1315|executive session"], (
            f"the placement named just before was not listed: {got.get('_named_before')}")
        r = _run(cmd + ["work/PFOTHER"], cwd=str(root), env=env, capture_output=True,
                 text=True, timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout)[-300:]
        got = json.loads((root / "candidate_segments.json").read_text(encoding="utf-8"))
        assert (got.get("_named_before") or {}).get("PFEXEC") == ["HB1315|executive session"], (
            "a run over another recording dropped this one's _named_before")
        return "ok", "HB 1315's slot, named 30 s before it, listed; HB 1281's not; kept across runs"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("markers", "segment_markers lists the committee bills a recording never names, by number, "
                  "digits or title, and the list survives a run over another recording",
       needs=("segment_markers",))
def _markers_not_named(segment_markers):
    """WHERE A RECORDING NEVER NAMES ITS BILL THE PAGE SAYS SO (17 October
    2026, the wording the person approved): 222 committee sittings read
    "ongoing work" where the recording's captions never name the bill. The
    build has no captions, so segment_markers writes those bills as
    _not_named, keyed on recording, and a later run over another recording
    -- as the night's livestreams --markers is -- keeps them. Named means by
    number, by any run of the bill's digits (an amount counts: the claim is
    made only where nothing could be the bill) or by title, as the clerk
    read HB 564 with its number captioned "5604". A floor recording's
    never-named bills are the consent calendar, _absent, and are not listed
    again. Every line below was spoken."""
    if not _paths.locate("segment_markers.py").exists():
        return "skip", "segment_markers.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        bills = {"2025-2026": {
            "HB1315": {"title": "relative to the sale of tobacco products"},
            "HB564": {"title": "relative to the adoption of school administrative unit budgets"},
            "HB1281": {"title": "relative to comfort dogs"},
            "SB100": {"title": "relative to election administration"},
            "HB639": {"title": "relative to the legalization and regulation of cannabis and "
                               "making appropriations therefor."},
            "HB1598": {"title": "(New Title) relative to notice and proceedings for tenants and "
                                "landlords engaged in eviction processes."},
            "HB77": {"title": "relative to the state forester"}}}
        reading = ("Majority of the committee on education policy and administration to "
                   "which was referred House Bill 5604, an act relative to the adoption of "
                   "school administrative unit budgets, considered the same")
        on_to = "On to House Bill 1315 relative to the sale of tobacco products,"
        comm = (["move unanimously."] * 3
                + ["Representative Hunt, second by Representative Patusk moves to pass."] * 3
                + [reading] + ["they're going to take $100,000 out the money that"]
                # BNKsnAKlHeo 1:24:12, the chair taking up HB 639 by two words of
                # its title, which the first reading called never named.
                + ["okay okay next legalization and regulation okay so um I have sent out"]
                # Ody4amuX03Q 0:39:03: HB 1598's title words, the other way round.
                + ["one of the situations that I think benefits both landlords and tenants"]
                + ["good morning"] * 3)
        env = _markers_fixture(
            root, bills,
            [("2025-2026", b, "H", "public hearing", "PFCOMM")
             for b in ("HB1315", "HB564", "HB1281", "SB100", "HB639", "HB1598")]
            + [("2025-2026", "HB77", "H", "floor debate", "PFFLOOR"),
               ("2025-2026", "HB1315", "H", "floor debate", "PFFLOOR")],
            {"PFCOMM": comm,
             "PFFLOOR": ["good morning"] * 3 + [on_to]})
        cmd = [sys.executable, _paths.script("segment_markers.py"), "--data", "data",
               "--quiet", "--cache", "cache.json", "--transcript"]

        def run(*vids):
            r = _run(cmd + [f"work/{v}" for v in vids], cwd=str(root), env=env,
                     capture_output=True, text=True, timeout=120)
            assert r.returncode == 0, (r.stderr or r.stdout)[-300:]
            return json.loads((root / "candidate_segments.json").read_text(encoding="utf-8"))
        got = run("PFCOMM", "PFFLOOR")
        nn = got.get("_not_named") or {}
        assert nn.get("PFCOMM") == ["HB1315", "HB1281"], (
            f"the committee recording's never-named bills are {nn.get('PFCOMM')}, not HB 1315 "
            "and HB 1281")
        assert "PFFLOOR" not in nn and "HB77" in (got.get("_absent") or {}).get("PFFLOOR", []), (
            f"the floor recording's bill never named went to _not_named, or not to _absent: {got}")
        got = run("PFFLOOR")
        assert (got.get("_not_named") or {}).get("PFCOMM") == ["HB1315", "HB1281"], (
            "a run over another recording dropped this one's _not_named")
        (root / "work" / "PFCOMM" / "captions.en.json3").write_text(json.dumps(_json3(
            comm[:3] + [on_to] + comm[3:])), encoding="utf-8")
        got = run("PFCOMM")
        assert (got.get("_not_named") or {}).get("PFCOMM") == ["HB1281"], (
            "a recording read again that now names HB 1315 did not answer for itself: "
            f"{(got.get('_not_named') or {}).get('PFCOMM')}")
        return "ok", ("HB 1281 listed; HB 564 by title, HB 639 and HB 1598 by two words of it, "
                      "SB 100 by digits and HB 1315 once said not; the floor's to _absent; kept "
                      "across runs, answered by a fresh read")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("data", "segment_markers' title lookup holds more than a thousand titles",
       needs=("segment_markers",))
def _markers_title_count(segment_markers):
    """The lookup was {None: ""} -- one empty title -- for as long as
    data/bills.json has been keyed by term, and every count stayed plausible
    (17 October 2026). A thousand is far below any term's bill count."""
    if not Path("data/bills.json").exists():
        return "skip", "no data/bills.json"
    by_term = segment_markers.title_lookup("data")
    n = sum(1 for t in by_term.values() for v in t.values() if v.strip())
    assert n > 1000, (f"segment_markers.title_lookup gives {n} titles across "
                      f"{len(by_term)} terms; the title fallback is not running")
    return "ok", f"{n:,} titles across {len(by_term)} terms"


# ============================================= code: the video index's rows ==

# fetch_channel_index.py's columns, for the checks that write an index.
_INDEX_COLS = ["video_id", "title", "title_parsed", "parsed_committee",
               "parsed_date", "date_from", "has_start_time", "start_eastern",
               "actual_start_utc", "actual_end_utc", "duration_iso",
               "published_at"]


@check("pipeline", "a later row that knows the stream aired wins in "
                   "build_manifest", needs=("build_manifest",))
def _manifest_prefers_aired(build_manifest):
    """The committed index lists a stream the day it is scheduled -- P0D, no
    start -- and livestreams.py writes the aired row into its own file, which
    sorts after it. First-file-wins kept the empty one."""
    root = Path(tempfile.mkdtemp())
    here = os.getcwd()
    try:
        base = {"video_id": "PFV", "title": "House Finance (09/17/2026)",
                "title_parsed": "yes", "parsed_committee": "Finance",
                "parsed_date": "2026-09-17", "date_from": "title",
                "has_start_time": "NO", "start_eastern": "",
                "actual_start_utc": "", "actual_end_utc": "",
                "duration_iso": "P0D", "published_at": "2026-08-20T13:16:12Z"}
        aired = dict(base, has_start_time="yes", start_eastern="2026-09-17 09:58:11",
                     actual_start_utc="2026-09-17T13:58:11Z",
                     actual_end_utc="2026-09-17T15:00:00Z", duration_iso="PT1H1M49S")
        for name, row in (("videos_house_2026-07-01_to_2026-12-31.csv", base),
                          ("videos_house_livestreams.csv", aired)):
            with open(root / name, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=_INDEX_COLS)
                w.writeheader()
                w.writerow(row)
        os.chdir(root)
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            got = build_manifest.load_videos(["videos_*.csv"])
        assert len(got) == 1 and got[0]["start_eastern"] == "2026-09-17 09:58:11", got
        # And never the other way: a row that knows it aired is kept.
        (root / "videos_house_2026-07-01_to_2026-12-31.csv").rename(
            root / "videos_house_2026-01-01_to_2026-06-30.csv")
        with open(root / "videos_house_zz.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=_INDEX_COLS)
            w.writeheader()
            w.writerow(base)
        with contextlib.redirect_stdout(io.StringIO()):
            got = build_manifest.load_videos(["videos_*.csv"])
        assert got[0]["start_eastern"] == "2026-09-17 09:58:11", got
        return "ok", "the aired row is taken over the pre-air one, in either order"
    finally:
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)


# ======================================================== code: livestreams ==

def _ls_env():
    """A child environment that can reach no key and thinks it is no runner."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("YOUTUBE_API_KEY", "GITHUB_ACTIONS")}
    env["PYTHONUTF8"] = "1"
    return env


def _ls_fixture(root, livestreams):
    """A committed index, the Data API's answers for three nights in the shape
    --record writes them, and a caption source. Every id is a test id."""
    known = {"video_id": "PFKNOWN0001", "title": "Fiscal Committee (09/04/2026)",
             "title_parsed": "yes", "parsed_committee": "Fiscal Committee",
             "parsed_date": "2026-09-04", "date_from": "title",
             "has_start_time": "yes", "start_eastern": "2026-09-04 12:58:41",
             "actual_start_utc": "2026-09-04T16:58:41Z",
             "actual_end_utc": "2026-09-04T18:32:47Z", "duration_iso": "PT1H34M21S",
             "published_at": "2026-09-05T06:44:31Z"}
    stale = {"video_id": "PFSTALE0001",
             "title": "JLCAR Administrative Rules (09/17/2026)",
             "title_parsed": "yes", "parsed_committee": "JLCAR Administrative Rules",
             "parsed_date": "2026-09-17", "date_from": "title",
             "has_start_time": "NO", "start_eastern": "", "actual_start_utc": "",
             "actual_end_utc": "", "duration_iso": "P0D",
             "published_at": "2026-08-20T13:16:12Z"}
    with open(root / "videos_house_2026-07-01_to_2026-12-31.csv", "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_INDEX_COLS)
        w.writeheader()
        w.writerows([known, stale])
    api = root / "api"
    api.mkdir()
    idx = {}

    def put(name, endpoint, params, doc):
        (api / name).write_text(json.dumps(doc), encoding="utf-8")
        idx[livestreams.canonical(endpoint, params)] = name

    for ch, cid in livestreams.CHANNELS.items():
        put(f"ch-{ch}.json", "channels", {"part": "contentDetails", "id": cid},
            {"items": [{"id": cid, "contentDetails": {
                "relatedPlaylists": {"uploads": "UU" + ch}}}]})

    def item(vid, title, pub):
        return {"snippet": {"title": title, "publishedAt": pub},
                "contentDetails": {"videoId": vid, "videoPublishedAt": pub}}

    pl = {"part": "contentDetails,snippet", "maxResults": 50}
    put("pl-house-1.json", "playlistItems", {**pl, "playlistId": "UUhouse"},
        {"nextPageToken": "P2", "items": [
            item("PFNEW000002", "House Education Policy and Administration "
                 "(09/25/2026)", "2026-09-24T20:00:00Z"),
            item("PFNEW000001", "House Ways and Means (09/23/2026)",
                 "2026-09-24T03:00:00Z"),
            item("PFKNOWN0001", known["title"], known["published_at"])]})
    put("pl-house-2.json", "playlistItems",
        {**pl, "playlistId": "UUhouse", "pageToken": "P2"},
        {"items": [item("PFSTALE0001", stale["title"], stale["published_at"])]})
    put("pl-senate-1.json", "playlistItems", {**pl, "playlistId": "UUsenate"},
        {"items": [item("PFSEN000001", "Senate Session (09/24/2026)",
                        "2026-09-24T21:00:00Z")]})
    parts = "snippet,contentDetails,liveStreamingDetails"

    def video(vid, title, pub, lbc, dur, start="", end="", sched=""):
        live = {k: v for k, v in (("actualStartTime", start), ("actualEndTime", end),
                                  ("scheduledStartTime", sched)) if v}
        return {"id": vid, "snippet": {"title": title, "publishedAt": pub,
                                       "liveBroadcastContent": lbc},
                "contentDetails": {"duration": dur}, "liveStreamingDetails": live}

    upcoming = video("PFNEW000002", "House Education Policy and Administration "
                     "(09/25/2026)", "2026-09-24T20:00:00Z", "upcoming", "P0D",
                     sched="2026-09-25T13:00:00Z")
    first = [video("PFNEW000001", "House Ways and Means (09/23/2026)",
                   "2026-09-24T03:00:00Z", "none", "PT2H1M5S",
                   "2026-09-23T13:58:30Z", "2026-09-23T15:59:35Z"),
             upcoming,
             video("PFSEN000001", "Senate Session (09/24/2026)",
                   "2026-09-24T21:00:00Z", "none", "PT3H0M0S",
                   "2026-09-24T13:59:00Z", "2026-09-24T16:59:00Z"),
             video("PFSTALE0001", stale["title"], stale["published_at"], "none",
                   "PT15M1S", "2026-09-17T12:58:11Z", "2026-09-17T13:13:03Z")]
    put("videos-1.json", "videos", {"part": parts, "id": ",".join(
        sorted(v["id"] for v in first))}, {"items": first})
    later = video("PFNEW000002", upcoming["snippet"]["title"],
                  "2026-09-24T20:00:00Z", "none", "PT1H0M0S",
                  "2026-09-25T13:00:05Z", "2026-09-25T14:00:05Z")
    put("videos-2.json", "videos", {"part": parts, "id": "PFNEW000002"},
        {"items": [later]})
    (api / "index.json").write_text(json.dumps(idx), encoding="utf-8")
    src = root / "src"
    (src / "PFNEW000001").mkdir(parents=True)
    (src / "PFNEW000001" / "captions.en.json3").write_text(json.dumps(_json3(
        ["good morning", "I am opening the hearing on House Bill 1491"])),
        encoding="utf-8")
    (src / "PFSEN000001").mkdir()
    (src / "PFSEN000001" / "ERROR.txt").write_text(
        "ERROR: [youtube] PFSEN000001: Sign in to confirm you’re not a bot. "
        "Use --cookies-from-browser or --cookies for the authentication.",
        encoding="utf-8")


def _ls_markers_fixture(root):
    """What --markers reads beside the night's captions: the bills, a
    proceedings table naming the new recording and one read before
    (PFOTHER), the caption results holding PFOTHER's reading, and a hand-timed
    proceeding on PFOTHER for the guard's probe (review/ground_truth.csv), a
    second from the reading. Returns PFOTHER's entry."""
    (root / "data").mkdir(exist_ok=True)
    (root / "data" / "bills.json").write_text(json.dumps(
        {"2025-2026": {"HB1491": {"id": "HB1491", "title": "x"}}}), encoding="utf-8")
    with open(root / "proceedings.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["term", "bill", "body", "kind", "date",
                                           "video_id", "source", "predicted_offset"])
        w.writeheader()
        for bill, vid in (("HB1491", "PFNEW000001"), ("HB77", "PFOTHER")):
            w.writerow({"term": "2025-2026", "bill": bill, "body": "H",
                        "kind": "public hearing", "date": "2026-09-23",
                        "video_id": vid, "source": "docket", "predicted_offset": "30"})
    (root / "review").mkdir(exist_ok=True)
    (root / "review" / "ground_truth.csv").write_text(
        "video_id,bill,kind,observed_start,observed_end,notes,marked_on\n"
        "PFOTHER,HB77,public hearing,61.0,,,2026-10-10\n", encoding="utf-8")
    other = {"HB77": [{"start": 60.0, "end": None, "how": "number",
                       "what": "hearing", "said": "x"}]}
    (root / "candidate_segments.json").write_text(json.dumps(
        {"PFOTHER": other, "_absent": {"PFOTHER": ["HB88"]}}), encoding="utf-8")
    (root / "caption_spans.json").write_text(json.dumps(
        {"about": "x", "recordings": {"PFOTHER": {"last": 60.0, "files": {}}}}),
        encoding="utf-8")
    return other


def _ls_run(root, *extra):
    # Sealed (_Seal): it replays the Data API's answers and a caption source,
    # and a regression that asked YouTube instead fails here, not quietly.
    return _sealed_run([sys.executable, _paths.script("livestreams.py"),
                        "--since-state", "--replay", "api", "--captions-from", "src",
                        "--origin", "runner", *extra],
                       cwd=str(root), env=_ls_env(), capture_output=True, text=True,
                       timeout=120)


@check("livestreams", "three nights of new livestreams: indexed, captioned, "
                      "refused, read, handed over, and nothing committed touched",
       needs=("livestreams", "build_manifest"))
def _ls_nights(livestreams, build_manifest):
    """The whole step on replayed answers, three nights running.

    Night one lists three new recordings and a committed row written before
    its stream aired; finds that one, eight days old, has no captions, and
    does not take one answer for it: it is to be asked again in a day,
    behind whatever is new; captions one; meets a data centre's bot check
    on the next and stops there. Night two, past the twelve-hour hold, turns
    the recording that was only scheduled into an aired one and asks for it
    first -- the refused recording, though older, goes behind it -- finds no
    captions on it yet, then asks the refused one again, is refused again and
    asks for nothing after it (the retry due that night waits); the build's
    --markers step reads the captioned one into candidate_segments.json and
    the caption summary, touches nothing else, and the guard passes it.
    Night three, on a machine with no captions and the kit's files holding
    the reading, asks nothing more of it; a night whose files lost it asks
    for it again, counted as a failure. No night changes a committed file,
    and build_manifest takes the aired row over the committed one written
    before the stream.
    """
    if not _paths.locate("livestreams.py").exists():
        return "skip", "livestreams.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _ls_fixture(root, livestreams)
        committed = (root / "videos_house_2026-07-01_to_2026-12-31.csv").read_bytes()
        r = _ls_run(root, "--now", "2026-09-25T06:30:00Z")
        assert r.returncode == 0, (r.stdout + r.stderr)[-400:]
        last = r.stdout.strip().splitlines()[-1]
        assert last.startswith("LIVESTREAMS: "), last
        st = json.loads((root / "archive" / "livestreams.json").read_text(encoding="utf-8"))
        v = st["videos"]
        assert v["PFNEW000001"]["captions"] == "captioned", v["PFNEW000001"]
        assert (root / "work" / "PFNEW000001" / "captions.en.json3").exists()
        assert v["PFSEN000001"]["captions"] == "deferred", v["PFSEN000001"]
        assert not (root / "work" / "PFSEN000001").exists(), \
            "a refused fetch left a folder behind"
        assert v["PFNEW000002"]["status"] == "upcoming", v["PFNEW000002"]
        assert v["PFSTALE0001"]["status"] == "finished", v["PFSTALE0001"]
        stale = v["PFSTALE0001"]
        assert stale["captions"] == "none-yet" and stale.get("asks") == 1, \
            f"one answer of \"no captions\" closed a recording, or was not counted: {stale}"
        assert stale.get("again") == "2026-09-26T04:30:00Z", stale
        ref = st["refusals"]["runner"]
        assert ref["count"] == 1 and "not a bot" in ref["why"], ref
        assert ref["until_iso"] == "2026-09-25T18:30:00Z", ref
        assert st["last_run"]["units"] == 6, \
            f"{st['last_run']['units']} units, expected 2 + 3 pages + 1"
        house = list(csv.DictReader(open(root / "videos_house_livestreams.csv",
                                         encoding="utf-8")))
        by = {x["video_id"]: x for x in house}
        assert set(by) == {"PFNEW000001", "PFNEW000002", "PFSTALE0001"}, set(by)
        assert by["PFNEW000001"]["start_eastern"] == "2026-09-23 09:58:30", \
            by["PFNEW000001"]
        assert by["PFNEW000001"]["parsed_committee"] == "Ways and Means"
        assert by["PFNEW000002"]["duration_iso"] == "P0D"
        assert by["PFSTALE0001"]["duration_iso"] == "PT15M1S"
        assert (root / "videos_senate_livestreams.csv").exists()

        r = _ls_run(root, "--now", "2026-09-26T06:30:00Z")
        assert r.returncode == 0, (r.stdout + r.stderr)[-400:]
        st = json.loads((root / "archive" / "livestreams.json").read_text(encoding="utf-8"))
        assert st["last_run"]["units"] == 3, st["last_run"]
        assert st["videos"]["PFNEW000002"]["status"] == "finished"
        ref = st["refusals"]["runner"]
        assert ref["count"] == 2 and ref["until_iso"] == "2026-09-27T04:30:00Z", \
            f"the second night did not ask the refused recording again and stop: {ref}"
        aired = st["videos"]["PFNEW000002"]
        assert aired["captions"] == "none-yet" and aired.get("asks") == 1 \
            and aired.get("tried") == "2026-09-26T06:30:00Z", \
            f"the recording refused the night before was asked ahead of a newer one: {aired}"
        assert st["videos"]["PFSEN000001"].get("refused") == "2026-09-26T06:30:00Z", \
            st["videos"]["PFSEN000001"]
        assert not (root / "work" / "PFNEW000002").exists()
        stale = st["videos"]["PFSTALE0001"]
        assert stale["captions"] == "deferred" and stale.get("asks") == 1 \
            and stale.get("tried") == "2026-09-25T06:30:00Z", \
            f"the recording without captions was asked ahead of the refused one: {stale}"
        house = {x["video_id"]: x for x in csv.DictReader(
            open(root / "videos_house_livestreams.csv", encoding="utf-8"))}
        assert house["PFNEW000002"]["duration_iso"] == "PT1H0M0S", house["PFNEW000002"]
        assert (root / "videos_house_2026-07-01_to_2026-12-31.csv").read_bytes() \
            == committed, "a committed index was written"

        here = os.getcwd()
        os.chdir(root)
        try:
            import io
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                vids = build_manifest.load_videos(["videos_*.csv"])
        finally:
            os.chdir(here)
        got = {x["video_id"]: x for x in vids}
        assert got["PFSTALE0001"]["start_eastern"] == "2026-09-17 08:58:11", \
            "build_manifest kept the row written before the stream aired"

        # build_all's step: segment_markers over this step's recordings alone,
        # merged into a candidate file that holds another recording already,
        # and the guard's probe against one hand-timed proceeding on it.
        other = _ls_markers_fixture(root)
        kits = {"PFOTHER": other, "_absent": {"PFOTHER": ["HB88"]}}
        env = {k: v for k, v in _ls_env().items() if k != "GRANITE_PROCEEDINGS"}

        def markers():
            r = _sealed_run([sys.executable, _paths.script("livestreams.py"),
                             "--markers", "--origin", "runner"], cwd=str(root), env=env,
                            capture_output=True, text=True, timeout=120)
            assert r.returncode == 0, (r.stdout + r.stderr)[-400:]
            return json.loads((root / "candidate_segments.json").read_text(
                encoding="utf-8"))

        cs = markers()
        read = cs.get("PFNEW000001") or {}
        assert "HB1491" in read, read
        assert cs.get("PFOTHER") == other and cs["_absent"] == {"PFOTHER": ["HB88"]}, \
            "--markers changed a recording it was not given"
        spans = json.loads((root / "caption_spans.json").read_text(encoding="utf-8"))
        assert spans["recordings"].get("PFOTHER") == {"last": 60.0, "files": {}}
        assert spans["recordings"].get("PFNEW000001", {}).get("files"), \
            "the caption summary was not given the new recording"
        st = json.loads((root / "archive" / "livestreams.json").read_text(encoding="utf-8"))
        n1 = st["videos"]["PFNEW000001"]
        assert n1.get("read") and not n1.get("carry") and "result" not in n1, \
            f"the reading was carried in the state rather than kept in the files: {n1}"
        # The totals; each proceeding's error rides along (livestreams.worse).
        tot = {k: {x: st["markers"]["probe"][k].get(x) for x in ("marked", "placed", "median")}
               for k in ("before", "after")}
        assert st["markers"]["guard"] == "passed" and st["markers"]["read"] == 1 and \
            tot["after"] == tot["before"] == {"marked": 1, "placed": 1, "median": 1.0}, \
            st["markers"]
        kept = {p: (root / p).read_bytes() for p in ("candidate_segments.json",
                                                     "caption_spans.json")}

        # Night three, on a machine with no captions: the kit brought the
        # night's own files, which hold the reading, so nothing is asked again.
        shutil.rmtree(root / "work" / "PFNEW000001")
        r = _ls_run(root, "--now", "2026-09-28T06:30:00Z")
        assert r.returncode == 0, (r.stdout + r.stderr)[-400:]
        st = json.loads((root / "archive" / "livestreams.json").read_text(encoding="utf-8"))
        n1 = st["videos"]["PFNEW000001"]
        assert n1["captions"] == "captioned" and not n1.get("tries"), n1
        assert st["last_run"]["units"] == 2, st["last_run"]
        assert {p: (root / p).read_bytes() for p in kept} == kept, \
            "--since-state wrote the caption results"
        # A night whose files lost it -- the build stopped before --markers --
        # asks for it again, as a failure, so that it cannot be asked forever:
        # tonight behind the hold night three's refusal started, so deferred.
        (root / "candidate_segments.json").write_text(json.dumps(kits), encoding="utf-8")
        r = _ls_run(root, "--now", "2026-09-28T07:30:00Z")
        assert r.returncode == 0, (r.stdout + r.stderr)[-400:]
        n1 = json.loads((root / "archive" / "livestreams.json").read_text(
            encoding="utf-8"))["videos"]["PFNEW000001"]
        assert n1["captions"] in ("failed", "deferred") and n1.get("tries") == 1 \
            and "read" not in n1 and "asked for again" in n1.get("why", ""), n1
        assert livestreams.carry_list(st) == [
            "archive/livestreams.json", "videos_house_livestreams.csv",
            "videos_senate_livestreams.csv"], livestreams.carry_list(st)
        return "ok", ("3 new and 1 pre-air row indexed at 6 units, then 3, then 2; "
                      "one captioned, read by --markers into the night's caption "
                      "results with the guard's probe unchanged, and not asked again "
                      "while they hold it, asked again as a failure when they lost it; "
                      "one refused, then asked behind the newly aired one the next "
                      "night and refused again; one with no captions put behind the "
                      "new ones, not closed; committed index untouched")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("livestreams", "the timestamp guard compares like with like: the median on the hand-timed "
       "proceedings both copies place, the newly placed within a minute, and none fewer placed",
       needs=("livestreams", "probe_alignment"))
def _timestamp_guard_like_with_like(L, PA):
    """The person, 24 October 2026, choosing "option A": a re-read that placed
    58 of the 63 hand-timed proceedings, where the copy in the bucket placed
    44, was refused by cloud.py send-night for a median of 1.5s against
    1.2s -- medians over two different sets, the 14 it newly placed (weak
    markers, about 3s each) the cause. The guard (livestreams.worse, which
    send-night and the night's own reading both use) now compares the
    proceedings both place, holds the newly placed to a minute at the median,
    since each is shown plainly as a stated boundary, and still refuses fewer
    placed. A score without each proceeding's error (a probe from before) is
    judged by the old rule.

    It fails if probe_alignment's scoreboard stops giving each proceeding's
    error by its key, or if worse() passes any of: the same proceedings
    placed worse, the newly placed more than a minute off, fewer placed; or
    refuses: more placed as well as before, the same file twice."""
    marks = [{"video": "V1", "bill": "HB1", "kind": "public hearing", "obs": 100.0},
             {"video": "V1", "bill": "HB2", "kind": "public hearing", "obs": 900.0},
             {"video": "V2", "bill": "SB3", "kind": "executive session", "obs": 50.0}]
    for m, got in zip(marks, (101.0, 903.5, None)):
        m["cand"] = got
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        sc = PA.score(marks, "fixture", lambda m: m.get("cand"))
    assert sc["each"] == {"V1|HB1|public hearing": 1.0, "V1|HB2|public hearing": 3.5}, sc
    assert PA.mark_key(marks[2]) == "V2|SB3|executive session"

    def s(**each):
        e = {k: float(v) for k, v in each.items()}
        xs = sorted(e.values())
        return {"marked": 63, "placed": len(e), "median": xs[len(xs) // 2] if xs else None,
                "each": e}

    old = s(a=1.0, b=1.2, c=1.4)
    bad = []
    for name, before, after, want in (
            ("more placed, the old ones as they were", old, s(a=1.0, b=1.2, c=1.4, d=3.0, e=4.0),
             ""),
            ("the same copy", old, old, ""),
            ("the same proceedings placed worse", old, s(a=1.0, b=9.0, c=9.0, d=1.0),
             "both copies place"),
            ("the newly placed more than a minute off", old, s(a=1.0, b=1.2, c=1.4, d=480.0),
             "for the first time"),
            ("fewer placed", old, s(a=1.0, b=1.2), "places 2 of 63"),
            ("a probe from before: the old rule", {"marked": 63, "placed": 44, "median": 1.2},
             {"marked": 63, "placed": 58, "median": 1.5}, "median went")):
        why = L.worse(before, after)
        if (want and want not in why) or (not want and why):
            bad.append(f"{name}: {why or 'passed'}")
    p = L.paired(old, s(a=1.0, b=1.2, c=1.4, d=3.0, e=4.0))
    if (p["both"], p["before"], p["after"], p["new"], p["new_median"]) != (3, 1.2, 1.2, 2, 4.0) \
            or "on the 3 placed by both" not in L.paired_line(p):
        bad.append(f"the like-with-like comparison reads {p}: {L.paired_line(p)!r}")
    assert not bad, "; ".join(bad)
    return "ok", ("each proceeding's error in the scoreboard; worse() holds the same proceedings, "
                  "the newly placed within a minute, and no fewer placed")


@check("livestreams", "yt-dlp's answers are read for what they mean",
       needs=("livestreams",))
def _ls_classify(livestreams):
    """A refusal stops the night; a missing caption waits; a stream not yet
    held waits for its broadcast. The messages are yt-dlp's own, from its
    YouTube extractor, and "Sign in to confirm your age" is a fact about a
    video, not a refusal of an address."""
    c = livestreams.classify
    cases = [
        ((1, "ERROR: [youtube] x: Sign in to confirm you’re not a bot. Use "
             "--cookies-from-browser or --cookies for the authentication.",
          None, None, False), "refused"),
        ((1, "ERROR: Unable to download video subtitles for 'en': HTTP Error "
             "429: Too Many Requests", None, None, False), "refused"),
        ((1, "ERROR: [youtube] x: This content isn't available, try again "
             "later. The current session has been rate-limited by YouTube",
          None, None, False), "refused"),
        ((1, "ERROR: [youtube] x: Sign in to confirm your age", None, None,
          False), "failed"),
        ((1, "ERROR: [youtube] x: This live event will begin in 8 days.",
          None, None, False), "not-aired"),
        ((1, "ERROR: [youtube] x: Private video. Sign in if you've been "
             "granted access to this video", None, None, False), "gone"),
        ((0, "[info] x: There are no subtitles for the requested languages",
          None, None, False), "none-yet"),
        ((0, "", None, None, False), "none-yet"),
        ((-1, "took longer than 300s", None, None, False), "failed"),
        ((0, "", "captions.en.json3", None, True), "captioned"),
        ((0, "", "captions.en.json3", None, False), "failed"),
        ((0, "", None, "captions.en.vtt", False), "failed"),
    ]
    bad = [(args[1][:40], want, c(*args)[0]) for args, want in cases
           if c(*args)[0] != want]
    assert not bad, bad
    return "ok", f"{len(cases)} answers read as meant"


@check("livestreams", "one caption track to an ask, a run the size of what is waiting, "
                      "the second track only at a recording's last ask",
       needs=("livestreams", "segment_markers"))
def _ls_gentle(livestreams, segment_markers):
    """What YouTube is asked for, pinned. On 30 September 2026 the laptop's
    catch-up was answered "HTTP Error 429: Too Many Requests" on its second
    recording: it asked for `en.*`, which is two caption requests a recording
    for one track -- yt-dlp lists a recording's own captions as `en` and as
    `en-orig`, and all 4,265 captioned folders in work/ held both (300
    compared, 300 identical) -- twenty seconds apart and twenty a run. So:

      - every ask names ONE track outright, a name yt-dlp can match one
        track with, and the tracks are the caption files segment_markers
        reads, in its order;
      - yt-dlp's own pauses are in its arguments, and a run waits a minute
        or two between recordings;
      - a run asks for what is waiting, oldest first, up to MAX_CAPTIONS,
        and leaves the rest -- two on a quiet evening, twenty in session --
        and the longest run there can be, every pause at its longest, ends
        inside --budget. That run is found by trying every mix of new
        recordings and retries and is counted in caption requests: for a
        day it was taken to be twenty new and two retries and counted in
        recordings, and an evening with nothing new and twenty retries a
        week old, both tracks each, was forty requests -- 85 minutes with
        every pause at its longest;
      - `en-orig` is asked for only when `en` is not there, and only at a
        recording's last ask: a week after its stream, and never its first.
        A recording with neither is then taken to have none -- by a run
        that captioned something, because "none" is also what yt-dlp says
        when it could not get at the captions -- and the laptop, which
        cannot write the night's state, remembers that itself.

    Nothing here asks YouTube: every ask is answered from a folder of saved
    files, and one that would start yt-dlp instead fails the check.
    """
    import argparse as _ap
    import contextlib
    import io
    from datetime import datetime, timedelta, timezone
    L = livestreams
    for track in L.CAPTION_TRACKS:
        args = L.ytdlp_args(track)
        at = [k for k, x in enumerate(args) if x == "--sub-langs"]
        assert len(at) == 1 and args[at[0] + 1] == track, args
        assert re.fullmatch(r"[A-Za-z]+(?:-[A-Za-z]+)*", track), \
            f"{track!r} is a pattern, not one track's name: yt-dlp would fetch every match"
    assert "--sub-langs" not in L.YTDLP, "YTDLP names tracks itself; ytdlp_args adds the one"
    assert L.CAPTION_FILES == [f"captions.{t}.json3" for t in L.CAPTION_TRACKS], \
        (L.CAPTION_TRACKS, L.CAPTION_FILES)
    reads = [f for f in segment_markers.WORK_FILES if f.startswith("captions.")]
    assert L.CAPTION_FILES == reads, \
        f"segment_markers reads {reads}; this step asks for {L.CAPTION_FILES}"
    try:
        L.ytdlp_args("en.*")
        raise AssertionError("ytdlp_args accepted a wildcard")
    except L.Broken:
        pass
    for flag in ("--sleep-requests", "--sleep-subtitles"):
        assert flag in L.YTDLP and float(L.YTDLP[L.YTDLP.index(flag) + 1]) >= 1, \
            f"yt-dlp is not told to pause between its own requests ({flag})"
    # A caption file asked for under about a minute after its page is a 429
    # (yt-dlp issue 13831; the laptop's refusal of 18 October 2026).
    assert float(L.YTDLP[L.YTDLP.index("--sleep-subtitles") + 1]) >= 60, (
        "yt-dlp waits less than a minute before the caption file, which YouTube "
        "answers with 429")
    assert L.DELAY >= 60 and 0 < L.JITTER and L.DELAY + L.JITTER <= 120, (L.DELAY, L.JITTER)
    # A run is the size of what is waiting, up to a ceiling, and no smaller.
    assert [L.allowance(n) for n in (0, 1, 2, 6)] == [0, 1, 2, 6], "a quiet evening is not small"
    assert L.allowance(L.MAX_CAPTIONS + 30) == L.MAX_CAPTIONS, "a run has no ceiling"
    assert 6 <= L.AFTER_REFUSAL <= L.MAX_CAPTIONS <= 24, (L.AFTER_REFUSAL, L.MAX_CAPTIONS)
    assert 1 <= L.AGAIN_MIN <= 2, L.AGAIN_MIN
    # The longest run, found and not assumed. What a run asks is counted in
    # caption requests: a new recording is one, a retry at its last ask is
    # one for each track, and AGAIN_MIN retries ride on top whatever is
    # left. Every mix of new and old, of one-track and two-track retries, at
    # the full size and at the size after a refusal.
    dear = len(L.CAPTION_TRACKS)
    for size in (L.MAX_CAPTIONS, L.AFTER_REFUSAL):
        recs = reqs = 0
        for nf in range(size + 4):
            first = [f"F{k:02d}" for k in range(nf)]
            for na in range(size + dear * L.AGAIN_MIN + 4):
                again = [f"A{k:02d}" for k in range(na)]
                for two in (again, [], again[::2], again[1::2], again[:L.AGAIN_MIN],
                            again[L.AGAIN_MIN:]):
                    cost = (lambda vid, two=frozenset(two): dear if vid in two else 1)
                    ask, left = L.tonight(first, again, size, cost)
                    n = min(nf, size)
                    assert ask[:n] == first[:n] and ask[n:] == again[:len(ask) - n], \
                        f"{nf} new, {na} old: not the new ones first and then the old, in order: {ask}"
                    assert left == nf + na - len(ask), (nf, na, left, ask)
                    assert len(ask) - n >= min(na, L.AGAIN_MIN), \
                        f"{nf} new, {na} old: a retry waited behind a full lane"
                    recs = max(recs, len(ask))
                    reqs = max(reqs, sum(cost(v) for v in ask))
        assert (recs, reqs) == (size + L.AGAIN_MIN, size + dear * L.AGAIN_MIN), \
            f"a run of {size} can reach {recs} recordings and {reqs} caption requests"
    most = L.MAX_CAPTIONS + L.AGAIN_MIN
    requests = L.MAX_CAPTIONS + dear * L.AGAIN_MIN
    # Every pause at its longest, one before each request but the first, and
    # inside yt-dlp the minute before each caption file plus twenty seconds
    # -- that last an estimate. The laptop's run must finish whole; the
    # night's stops at BUDGET, which its step and the night are timed to.
    wait = float(L.YTDLP[L.YTDLP.index("--sleep-subtitles") + 1])
    longest = (requests - 1) * (L.DELAY + L.JITTER) + requests * (wait + 20)
    assert longest <= L.INBOX_BUDGET * 60, \
        f"the longest run, {longest / 60:.0f} minutes, does not fit the laptop's --budget " \
        f"{L.INBOX_BUDGET:g}"
    assert L.BUDGET <= L.INBOX_BUDGET, (L.BUDGET, L.INBOX_BUDGET)
    for argv, want in ((["--to-inbox"], L.INBOX_BUDGET), ([], L.BUDGET),
                       (["--to-inbox", "--budget", "5"], 5.0)):
        seen = {}
        real = L.to_inbox
        try:
            L.to_inbox = lambda a: seen.setdefault("budget", a.budget) and 0
            if argv and argv[0] == "--to-inbox":
                L.main(argv + ["--dry-run", "--local-bucket", str(Path(tempfile.mkdtemp()))])
                assert seen.get("budget") == want, (argv, seen, want)
        finally:
            L.to_inbox = real

    root = Path(tempfile.mkdtemp())
    here = os.getcwd()
    real_ask, real_read, real_summary = L.ask_track, L.read_markers, L.write_summary
    asked = []

    def ask(vid, track, work=L.WORK, source=None, timeout=300):
        assert source, f"{vid}: an ask with no saved answers would have started yt-dlp"
        asked.append((vid, track))
        return real_ask(vid, track, work, source, timeout)

    L.ask_track = ask
    try:
        words = json.dumps(_json3(["I am opening the hearing on House Bill 1491"]))
        src, work = root / "src", root / "work"
        now = datetime(2026, 10, 1, 21, 0, tzinfo=timezone.utc)
        a = _ap.Namespace(max_captions=L.MAX_CAPTIONS, budget=L.BUDGET, delay=0, jitter=0,
                          timeout=60, stop_after=3, captions_from=str(src), origin="laptop")
        quiet = contextlib.redirect_stdout(io.StringIO())

        def run(st, at, table=None):
            del asked[:]
            first, again = L.caption_queue(st, at)
            with quiet:
                return L.run_captions(st, first, again,
                                      L.Refusals({} if table is None else table, "laptop"),
                                      at, a, work=work)

        # More waiting than a run asks for: the oldest go, both of a
        # recording's saved tracks are there, and only `en` is taken.
        vids = [f"V{k:02d}" for k in range(L.MAX_CAPTIONS + 3)]
        for vid in vids:
            (src / vid).mkdir(parents=True)
            for f in L.CAPTION_FILES:
                (src / vid / f).write_text(words, encoding="utf-8")
        st = {"videos": {vid: {"status": "finished", "captions": "waiting",
                               "ended": L.iso(now - timedelta(hours=40 - k))}
                         for k, vid in enumerate(vids)}}
        assert L.caption_queue(st, now) == (vids, []), L.caption_queue(st, now)
        got, why = run(st, now)
        head = vids[:L.MAX_CAPTIONS]
        assert asked == [(vid, "en") for vid in head], asked
        assert got == {"captioned": L.MAX_CAPTIONS, "left for tomorrow": 3} and not why, got
        assert all(sorted(x.name for x in (work / vid).iterdir()) == ["captions.en.json3"]
                   for vid in head), "an ask brought more than its one track"
        # The next run starts with what was left, and is that small.
        assert L.caption_queue(st, now) == (vids[L.MAX_CAPTIONS:], [])
        got, why = run(st, now)
        assert asked == [(vid, "en") for vid in vids[L.MAX_CAPTIONS:]] and got == {"captioned": 3}, \
            (asked, got)

        # A recording with only the second track, and one with none. Inside
        # the week each is asked for `en` and nothing else, and waits.
        (src / "ORIG").mkdir()
        (src / "ORIG" / "captions.en-orig.json3").write_text(words, encoding="utf-8")
        (src / "NONE").mkdir()
        young = {"status": "finished", "captions": "waiting",
                 "ended": L.iso(now - timedelta(days=2))}
        st = {"videos": {"NONE": dict(young), "ORIG": dict(young)}}
        got, why = run(st, now)
        assert asked == [("NONE", "en"), ("ORIG", "en")], asked
        assert got == {"none-yet": 2} and not why, (got, why)
        assert not (work / "ORIG").exists() and not (work / "NONE").exists()
        assert [st["videos"][v].get("asks") for v in ("NONE", "ORIG")] == [1, 1]
        assert L.caption_queue(st, now + timedelta(hours=12)) == ([], []), \
            "asked again the same day"
        # A week after the stream, and not its first ask: `en`, then `en-orig`.
        late = now + timedelta(days=6)
        assert L.caption_queue(st, late) == ([], ["NONE", "ORIG"]), \
            "a recording a week old was closed without its last ask"
        got, why = run(st, late)
        assert asked == [("NONE", "en"), ("NONE", "en-orig"),
                         ("ORIG", "en"), ("ORIG", "en-orig")], asked
        assert got == {"none-published": 1, "captioned": 1}, got
        assert st["videos"]["NONE"]["captions"] == "none-published"
        assert (work / "ORIG" / "captions.en-orig.json3").exists()
        assert segment_markers.read_words(work / "ORIG"), "the second track is not read"
        assert L.caption_queue(st, late) == ([], []), "a recording with no captions is still due"

        # A first ask is never a last one, however old the stream: one track,
        # and the recording is not closed on the strength of one answer. Nor
        # is it closed by a run that captioned nothing, at any ask.
        for vid in ("OLD", "NEW1", "NEW2"):
            (src / vid).mkdir()
        (src / "NEW1" / "captions.en.json3").write_text(words, encoding="utf-8")
        st = {"videos": {
            "OLD": {"status": "finished", "captions": "waiting",
                    "ended": L.iso(late - timedelta(days=30))},
            "NEW1": {"status": "finished", "captions": "waiting",
                     "ended": L.iso(late - timedelta(days=1))}}}
        got, why = run(st, late)
        assert asked == [("OLD", "en"), ("NEW1", "en")], asked
        assert got == {"none-yet": 1, "captioned": 1}, got
        assert st["videos"]["OLD"]["captions"] == "none-yet", \
            "a recording was taken to have no captions at its first ask"
        got, why = run(st, late + timedelta(days=1))
        assert asked == [("OLD", "en"), ("OLD", "en-orig")] and got == {"none-yet": 1}, (asked, got)
        assert st["videos"]["OLD"]["captions"] == "none-yet", \
            "a run that captioned nothing took a recording to have no captions"
        (src / "NEW2" / "captions.en.json3").write_text(words, encoding="utf-8")
        st["videos"]["NEW2"] = {"status": "finished", "captions": "waiting",
                                "ended": L.iso(late + timedelta(days=2))}
        got, why = run(st, late + timedelta(days=3))
        assert asked == [("NEW2", "en"), ("OLD", "en"), ("OLD", "en-orig")], asked
        assert got == {"captioned": 1, "none-published": 1}, got

        # A refusal of the first track is not a missing one: no second ask.
        (src / "REF").mkdir()
        (src / "REF" / "ERROR.txt").write_text(
            "ERROR: Unable to download video subtitles for 'en': HTTP Error 429: "
            "Too Many Requests", encoding="utf-8")
        st = {"videos": {"REF": {"status": "finished", "captions": "none-yet", "asks": 1,
                                 "again": L.iso(late - timedelta(days=1)),
                                 "ended": L.iso(late - timedelta(days=30))}}}
        table = {}
        got, why = run(st, late, table)
        assert asked == [("REF", "en")] and why and table["laptop"]["count"] == 1, (asked, table)

        # A refused recording goes behind the rest of its lane, so the next
        # run asks another first. From 30 September 2026 the laptop asked the
        # same oldest recording first four evenings running and was refused
        # on it each time, with 26 waiting behind it.
        (src / "NEXT").mkdir()
        (src / "NEXT" / "captions.en.json3").write_text(words, encoding="utf-8")
        st = {"videos": {
            "REF": {"status": "finished", "captions": "waiting",
                    "ended": L.iso(late - timedelta(days=9))},
            "NEXT": {"status": "finished", "captions": "waiting",
                     "ended": L.iso(late - timedelta(days=2))}}}
        assert L.caption_queue(st, late) == (["REF", "NEXT"], []), L.caption_queue(st, late)
        got, why = run(st, late, {})
        assert asked == [("REF", "en")] and why and st["videos"]["REF"].get("refused"), \
            (asked, st)
        assert L.caption_queue(st, late) == (["NEXT", "REF"], []), \
            "a recording refused last time is still asked first"
        got, why = run(st, late, {})
        assert asked == [("NEXT", "en"), ("REF", "en")] and got["captioned"] == 1 and why, \
            (asked, got, why)
        # Its next answer that is not a refusal clears the mark.
        (src / "REF" / "ERROR.txt").unlink()
        got, why = run(st, late, {})
        assert asked == [("REF", "en")] and "refused" not in st["videos"]["REF"], \
            (asked, st["videos"]["REF"])

        # An evening with nothing new and more retries a week old than a run
        # has requests for. Each is at its last ask, so each is two requests,
        # and the run is MAX_CAPTIONS requests and no more: while a run was
        # counted in recordings it was twice that.
        many = [f"W{k:02d}" for k in range(L.MAX_CAPTIONS + 4)]
        for vid in many:
            (src / vid).mkdir()
        st = {"videos": {vid: {"status": "finished", "captions": "none-yet", "asks": 1,
                               "again": L.iso(late - timedelta(hours=1)),
                               "ended": L.iso(late - timedelta(days=30, minutes=-k))}
                         for k, vid in enumerate(many)}}
        got, why = run(st, late)
        half = L.MAX_CAPTIONS // dear
        assert asked == [(v, t) for v in many[:half] for t in L.CAPTION_TRACKS], \
            f"a run of nothing but retries made {len(asked)} caption requests"
        assert got == {"none-yet": half, "left for tomorrow": len(many) - half} and not why, \
            (got, why)

        # The laptop's catch-up reads the night's state and never writes it,
        # so what it asked for and got no captions it keeps beside its own
        # refusal record. Three evenings: one that captions nothing, and so
        # closes nothing; one that captions the other recording, and so
        # takes "none" at its word; one that asks for nothing.
        night = root / "night"
        (night / "archive").mkdir(parents=True)
        (night / "src" / "NONE").mkdir(parents=True)
        state = {"version": 1, "channels": {}, "last_run": {}, "refusals": {}, "videos": {
            "NONE": {"status": "finished", "captions": "deferred", "chamber": "house",
                     "ended": L.iso(now - timedelta(days=9)), "title": "x"},
            "GOOD": {"status": "finished", "captions": "deferred", "chamber": "house",
                     "ended": L.iso(now - timedelta(days=1)), "title": "y"}}}
        (night / "archive" / "livestreams.json").write_text(json.dumps(state),
                                                            encoding="utf-8")
        before = (night / "archive" / "livestreams.json").read_bytes()
        record = night / "archive" / "youtube.refused.json"
        os.chdir(night)
        # The reading of what was captioned is --markers' and its own
        # checks'; here it would need a proceedings table.
        L.read_markers, L.write_summary = (lambda vids: 0), (lambda: 0)

        def evening(day):
            del asked[:]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = L.main(["--catch-up", "--captions-from", "src", "--origin", "laptop",
                               "--now", L.iso(now + timedelta(days=day))])
            assert code == 0, out.getvalue()[-300:]
            said = [ln for ln in out.getvalue().splitlines()
                    if ln.startswith("LIVESTREAMS CATCH-UP:")]
            assert len(said) == 1, out.getvalue()[-300:]
            return (list(asked), said[0],
                    json.loads(record.read_text(encoding="utf-8")).get(L.ASKED) or {})

        was, line, kept = evening(0)
        assert was == [("NONE", "en"), ("GOOD", "en")] and "2 none-yet" in line, (was, line)
        assert sorted(kept) == ["GOOD", "NONE"] and not any(
            e.get("closed") for e in kept.values()), kept
        (night / "src" / "GOOD").mkdir()
        (night / "src" / "GOOD" / "captions.en.json3").write_text(words, encoding="utf-8")
        was, line, kept = evening(1)
        assert was == [("NONE", "en"), ("NONE", "en-orig"), ("GOOD", "en")], was
        assert list(kept) == ["NONE"] and kept["NONE"].get("closed") == "none-published", kept
        assert "1 captioned" in line and "1 none-published" in line, line
        was, line, kept = evening(2)
        assert was == [] and list(kept) == ["NONE"], f"the third evening asked again: {was}"
        os.chdir(here)
        assert (night / "archive" / "livestreams.json").read_bytes() == before, \
            "the catch-up wrote the night's state"

        # The laptop keeps a refusal against the recording it met, so the
        # next evening asks another first: the evenings of 30 September to
        # 5 October 2026 asked aNisQhENQwc first every time.
        night2 = root / "night2"
        (night2 / "archive").mkdir(parents=True)
        for vid in ("OLDR", "NEWR"):
            (night2 / "src" / vid).mkdir(parents=True)
        (night2 / "src" / "OLDR" / "ERROR.txt").write_text(
            "ERROR: Unable to download video subtitles for 'en': HTTP Error 429: "
            "Too Many Requests", encoding="utf-8")
        (night2 / "src" / "NEWR" / "captions.en.json3").write_text(words, encoding="utf-8")
        state["videos"] = {
            "OLDR": {"status": "finished", "captions": "deferred", "chamber": "house",
                     "ended": L.iso(now - timedelta(days=9)), "title": "x"},
            "NEWR": {"status": "finished", "captions": "deferred", "chamber": "house",
                     "ended": L.iso(now - timedelta(days=1)), "title": "y"}}
        (night2 / "archive" / "livestreams.json").write_text(json.dumps(state),
                                                             encoding="utf-8")
        record = night2 / "archive" / "youtube.refused.json"
        os.chdir(night2)
        was, line, kept = evening(0)
        assert was == [("OLDR", "en")] and "refused" in line and kept["OLDR"].get("refused"), \
            (was, line, kept)
        was, line, kept = evening(1)
        assert was == [("NEWR", "en"), ("OLDR", "en")] and "1 captioned" in line, \
            f"the evening after a refusal asked the refused recording first: {was}"
        os.chdir(here)
        return "ok", (f"`en` alone to an ask; {L.MAX_CAPTIONS} oldest of {len(vids)} asked and 3 "
                      f"of 3, {L.DELAY:g}-{L.DELAY + L.JITTER:g}s apart; the longest run of "
                      f"any mix, {most} recordings and {requests} requests, {longest / 60:.0f} "
                      f"min of the laptop's {L.INBOX_BUDGET:g} min budget; {len(many)} retries a week old are "
                      f"{L.MAX_CAPTIONS} requests, not {dear * L.MAX_CAPTIONS}; `en-orig` only at a "
                      "last ask, never a first, and never after a refusal; a recording with "
                      "none is closed only by a run that captioned something, and the laptop "
                      "remembers it; a refused recording goes behind the rest")
    finally:
        L.ask_track, L.read_markers, L.write_summary = real_ask, real_read, real_summary
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)


@check("livestreams", "a recording without captions is never asked ahead of a newer one, "
                      "and is asked again a day later, then two, four and eight",
       needs=("livestreams",))
def _ls_starve(livestreams):
    """Six a run, oldest first, starved everything newer for good.

    A recording with no captions was asked again every run, and closed only
    by a run that captioned something. Six of them at the head of the queue
    filled every run, so no run captioned anything, so none ever closed: six
    captionless recordings from one day and three with captions from the
    next gave fourteen nights of six asks and not one for a recording that
    had captions. archive/captions.json has such days -- five on 11 January
    2022, five on 4 June 2024 -- and replayed over the real recordings of
    those years the rule left 107 and 117 never asked for at all.

    So, from saved files:

      - that case. All nine are asked the first night, and the three are
        captioned then. The six are asked again on nights 2, 4 and 8 and no
        other, each night after whatever is new, and at the last -- a week
        on -- for both tracks, and closed;
      - the same nine with the run held to six, as it was. The first night
        is six of "no captions" and nothing else, which is read as a refusal
        that did not say so; the second asks the three with captions first;
      - a retry never takes a new recording's place: with more new ones
        waiting than a run asks for, they get the whole of it and two
        retries are asked on top;
      - on the laptop, which cannot write the night's state, a recording
        gone private is asked on evenings 0, 1, 3, 7 and 15, after anything
        new from the second on, and not again -- where it used to be the
        first thing asked every evening.
    """
    import argparse as _ap
    import contextlib
    import io
    from datetime import datetime, timedelta, timezone
    L = livestreams
    root = Path(tempfile.mkdtemp())
    here = os.getcwd()
    real_ask, real_read, real_summary = L.ask_track, L.read_markers, L.write_summary
    asked = []

    def ask(vid, track, work=L.WORK, source=None, timeout=300):
        assert source, f"{vid}: an ask with no saved answers would have started yt-dlp"
        asked.append((vid, track))
        return real_ask(vid, track, work, source, timeout)

    L.ask_track = ask
    try:
        words = json.dumps(_json3(["I am opening the hearing on House Bill 1491"]))
        src, work = root / "src", root / "work"
        t0 = datetime(2027, 1, 14, 2, 0, tzinfo=timezone.utc)
        quiet = contextlib.redirect_stdout(io.StringIO())

        def namespace(most):
            return _ap.Namespace(max_captions=most, budget=L.BUDGET, delay=0, jitter=0,
                                 timeout=60, stop_after=3, captions_from=str(src),
                                 origin="laptop")

        def night(st, table, at, a, where):
            del asked[:]
            first, again = L.caption_queue(st, at)
            with quiet:
                got, why = L.run_captions(st, first, again, L.Refusals(table, "laptop"),
                                          at, a, work=where)
            return list(asked), got, why

        def nine():
            st = {"videos": {}}
            for k in range(6):
                (src / f"NONE{k}").mkdir(parents=True, exist_ok=True)
                st["videos"][f"NONE{k}"] = {
                    "status": "finished", "captions": "waiting",
                    "ended": L.iso(t0 - timedelta(hours=30, minutes=-k))}
            for k in range(3):
                (src / f"GOOD{k}").mkdir(parents=True, exist_ok=True)
                (src / f"GOOD{k}" / "captions.en.json3").write_text(words, encoding="utf-8")
                st["videos"][f"GOOD{k}"] = {
                    "status": "finished", "captions": "waiting",
                    "ended": L.iso(t0 - timedelta(hours=9, minutes=-k))}
            return st

        nones = [f"NONE{k}" for k in range(6)]
        goods = [f"GOOD{k}" for k in range(3)]

        # Fourteen nights, one new recording with captions each.
        st, table, retried = nine(), {}, []
        for n in range(1, 15):
            at = t0 + timedelta(days=n - 1)
            day = f"DAY{n:02d}"
            (src / day).mkdir()
            (src / day / "captions.en.json3").write_text(words, encoding="utf-8")
            st["videos"][day] = {"status": "finished", "captions": "waiting",
                                 "ended": L.iso(at - timedelta(hours=8))}
            was, got, why = night(st, table, at, namespace(L.MAX_CAPTIONS), work)
            assert not why and not table.get("laptop", {}).get("count"), (n, why, table)
            order = [vid for vid, _ in was]
            assert st["videos"][day]["captions"] == "captioned", f"night {n}: {day} waited"
            if n == 1:
                assert order == nones + goods + [day], order
                assert all(st["videos"][g]["captions"] == "captioned" for g in goods), \
                    "the recordings with captions were not captioned the first night"
            if any(vid in nones for vid in order):
                retried.append(n)
                if n > 1:
                    assert order[0] == day, \
                        f"night {n}: a recording asked before came ahead of a new one: {order}"
            want = [(v, t) for v in nones for t in (L.CAPTION_TRACKS if n == 8 else ["en"])]
            assert [x for x in was if x[0] in nones] == (want if n in (1, 2, 4, 8) else []), \
                (n, was)
        assert retried == [1, 2, 4, 8], f"asked again on nights {retried}"
        assert all(st["videos"][v]["captions"] == "none-published" for v in nones), \
            {v: st["videos"][v]["captions"] for v in nones}

        # The same nine at six a run, the size that starved them.
        st, table = nine(), {}
        was, got, why = night(st, table, t0, namespace(6), root / "work6")
        assert [vid for vid, _ in was] == nones and got == {"none-yet": 6, "deferred": 3}, (was, got)
        assert why and table["laptop"].get("silent"), "six of nothing but none was a normal night"
        was, got, why = night(st, table, t0 + timedelta(days=1), namespace(6), root / "work6")
        order = [vid for vid, _ in was]
        assert order[:3] == goods, f"at six a run the second night opened with {order[:3]}"
        assert all(st["videos"][g]["captions"] == "captioned" for g in goods), st["videos"]
        assert not why and not table["laptop"].get("count"), table

        # A retry is asked on top of the new ones, never in place of one.
        new = [f"N{k:02d}" for k in range(L.MAX_CAPTIONS + 10)]
        old = ["R0", "R1", "R2"]
        tonight, left = L.tonight(new, old)
        assert tonight == new[:L.MAX_CAPTIONS] + old[:L.AGAIN_MIN], tonight
        assert left == 10 + len(old) - L.AGAIN_MIN, left
        assert L.tonight(new[:4], old) == (new[:4] + old, 0)
        assert L.tonight([], old) == (old, 0)
        assert L.tonight(new, old, 6) == (new[:6] + old[:L.AGAIN_MIN],
                                           len(new) - 6 + len(old) - L.AGAIN_MIN)

        # The laptop, and a recording gone private at the head of its list.
        home = root / "night"
        (home / "archive").mkdir(parents=True)
        (home / "src" / "GONE").mkdir(parents=True)
        (home / "src" / "GONE" / "ERROR.txt").write_text(
            "ERROR: [youtube] GONE: Private video. Sign in if you've been granted "
            "access to this video", encoding="utf-8")
        os.chdir(home)
        L.read_markers, L.write_summary = (lambda vids: 0), (lambda: 0)
        state = {"version": 1, "channels": {}, "last_run": {}, "refusals": {}, "videos": {
            "GONE": {"status": "finished", "captions": "deferred", "chamber": "house",
                     "ended": L.iso(t0 - timedelta(days=3)), "title": "x"}}}
        record = home / "archive" / "youtube.refused.json"
        seen = []
        for day in range(26):
            at = t0 + timedelta(days=day)
            vid = f"E{day:02d}"
            (home / "src" / vid).mkdir()
            (home / "src" / vid / "captions.en.json3").write_text(words, encoding="utf-8")
            state["videos"][vid] = {"status": "finished", "captions": "deferred",
                                    "chamber": "house", "title": vid,
                                    "ended": L.iso(at - timedelta(hours=8))}
            text = json.dumps(state)
            (home / "archive" / "livestreams.json").write_text(text, encoding="utf-8")
            del asked[:]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = L.main(["--catch-up", "--captions-from", "src", "--origin", "laptop",
                               "--now", L.iso(at)])
            assert code == 0, out.getvalue()[-300:]
            assert (home / "archive" / "livestreams.json").read_text(encoding="utf-8") == text, \
                "the catch-up wrote the night's state"
            order = [v for v, _ in asked]
            assert vid in order, f"evening {day}: the new recording was not asked for"
            if "GONE" in order:
                seen.append(day)
                assert day == 0 or order == [vid, "GONE"], \
                    f"evening {day}: the recording gone private came first: {order}"
        assert seen == [0, 1, 3, 7, 15], f"the recording gone private was asked on {seen}"
        kept = json.loads(record.read_text(encoding="utf-8"))[L.ASKED]
        assert list(kept) == ["GONE"] and kept["GONE"].get("closed") == "given-up" \
            and kept["GONE"]["asks"] == L.GIVE_UP_ASKS, kept
        os.chdir(here)
        return "ok", ("six without captions and three with: all nine asked the first night, "
                      "the six again on nights 2, 4 and 8 after what was new, then closed; at "
                      "six a run the three are asked the second night; two retries ride on "
                      f"top of {L.MAX_CAPTIONS} new; the laptop asks a recording gone private "
                      "on evenings 0, 1, 3, 7, 15 and no more")
    finally:
        L.ask_track, L.read_markers, L.write_summary = real_ask, real_read, real_summary
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)


@check("livestreams", "a run of nothing but \"no captions\" is read as a refusal, and takes "
                      "no recording to have none", needs=("livestreams",))
def _ls_all_none(livestreams):
    """ "No captions" is also what yt-dlp says when it could not get at them.

    It discards the tracks YouTube wants a token for, and says so in a
    warning --no-warnings hides, so every recording then answers "none".
    Six a run met that with the same six asks every evening, exit 0, for as
    long as it lasted: replayed over a fortnight of February 2026, 150
    caption requests for nothing. So, from saved files:

      - a run in which three or more recordings answer "no captions" at
        their first ask and none is captioned is recorded as a refusal, with
        its hold, and is said to be one in the run's last line;
      - nothing is taken to have no captions by it, however old;
      - inside the hold nothing is asked; the run after it stops at its
        third such answer, and the hold doubles;
      - when captions come again the count clears, the new recordings are
        asked first and the others after them;
      - two such answers are too few to read anything into, and a recording
        that has said "none" before saying it again is not news: neither
        starts a hold. Counting retries read nine quiet evenings of 2021 as
        refusals and kept a new recording waiting six days;
      - but with a refusal standing it is news, unless a run that captioned
        something has heard the recording say so before. A run made of
        nothing but retries was never stopped and never read as anything:
        on a copy of the laptop's state of 1 October 2026 with every answer
        "none", 38 requests in a run, exit 0, seven refusals in a row on
        the record. Now it is three requests, one track each, and the hold
        renewed -- and a recording a good run has vouched for still does
        not count, because counting those made 34 recordings of January
        2022 wait three days after one real 429.
    """
    import argparse as _ap
    import contextlib
    import io
    from datetime import datetime, timedelta, timezone
    L = livestreams
    root = Path(tempfile.mkdtemp())
    here = os.getcwd()
    real_ask, real_read, real_summary = L.ask_track, L.read_markers, L.write_summary
    asked = []

    def ask(vid, track, work=L.WORK, source=None, timeout=300):
        assert source, f"{vid}: an ask with no saved answers would have started yt-dlp"
        asked.append((vid, track))
        return real_ask(vid, track, work, source, timeout)

    L.ask_track = ask
    try:
        assert L.ALL_NONE == 3, L.ALL_NONE
        words = json.dumps(_json3(["I am opening the hearing on House Bill 1491"]))
        src, work = root / "src", root / "work"
        now = datetime(2027, 1, 14, 2, 0, tzinfo=timezone.utc)
        a = _ap.Namespace(max_captions=L.MAX_CAPTIONS, budget=L.BUDGET, delay=0, jitter=0,
                          timeout=60, stop_after=3, captions_from=str(src), origin="laptop")
        quiet = contextlib.redirect_stdout(io.StringIO())

        def run(st, table, at):
            del asked[:]
            first, again = L.caption_queue(st, at)
            with quiet:
                got, why = L.run_captions(st, first, again, L.Refusals(table, "laptop"),
                                          at, a, work=work)
            return list(asked), got, why

        def waiting(names, ended, **more):
            for k, vid in enumerate(names):
                (src / vid).mkdir(parents=True, exist_ok=True)
            return {vid: dict({"status": "finished", "captions": "waiting",
                               "ended": L.iso(ended + timedelta(minutes=k))}, **more)
                    for k, vid in enumerate(names)}

        fresh = [f"N{k}" for k in range(8)]
        stale = ["OLD0", "OLD1"]
        st = {"videos": waiting(fresh, now - timedelta(hours=30))}
        st["videos"].update(waiting(stale, now - timedelta(days=9), captions="none-yet",
                                    asks=1, again=L.iso(now - timedelta(hours=1))))
        table = {}
        was, got, why = run(st, table, now)
        assert was == [(v, "en") for v in fresh] + [(v, t) for v in stale
                                                    for t in L.CAPTION_TRACKS], was
        rec = table.get("laptop") or {}
        assert why and "no captions" in why and rec.get("count") == 1 and rec.get("silent"), \
            f"a run of nothing but \"none\" was a normal night: {got} {table}"
        assert abs(rec["until"] - now.timestamp() - L.HOLD_HOURS * 3600) < 1, rec
        assert got == {"none-yet": 10}, got
        assert {v["captions"] for v in st["videos"].values()} == {"none-yet"}, \
            "a run that captioned nothing took a recording to have no captions"
        assert all(v.get("again") for v in st["videos"].values())
        # Inside the hold nothing is asked, of five new recordings either.
        late = ["M0", "M1", "M2", "M3", "M4"]
        st["videos"].update(waiting(late, now - timedelta(hours=3)))
        was, got, why = run(st, table, now + timedelta(hours=6))
        assert was == [] and got == {"deferred": 5} and why, (was, got)
        # After it, the run is wary: three such answers and it stops.
        was, got, why = run(st, table, now + timedelta(days=1))
        assert was == [(v, "en") for v in late[:3]], was
        assert got == {"none-yet": 3, "deferred": 2 + len(fresh)}, got
        rec = table["laptop"]
        assert rec["count"] == 2 and rec.get("silent") and why, rec
        assert abs(rec["until"] - (now + timedelta(days=1)).timestamp()
                   - (24 - L.EARLY_HOURS) * 3600) < 1, rec
        assert not any(v["captions"] == "none-published" for v in st["videos"].values())
        # Captions come again: the count clears, new first, the rest after.
        for vid in fresh + stale + late:
            (src / vid / "captions.en.json3").write_text(words, encoding="utf-8")
        was, got, why = run(st, table, now + timedelta(days=2))
        order = [v for v, _ in was]
        assert order[:2] == late[3:], f"the run after opened with {order[:2]}"
        assert sorted(order) == sorted(fresh + stale + late) and len(was) == len(order), was
        assert got == {"captioned": 15} and not why and table["laptop"]["count"] == 0, (got, table)

        # Too few to read anything into: two first asks, nothing captioned.
        st, table = {"videos": waiting(["P0", "P1"], now - timedelta(days=20))}, {}
        was, got, why = run(st, table, now)
        assert got == {"none-yet": 2} and not why and not table, (got, why, table)
        assert {v["captions"] for v in st["videos"].values()} == {"none-yet"}
        # And not news: four that have said it before say it again.
        st = {"videos": waiting(["Q0", "Q1", "Q2", "Q3"], now - timedelta(days=2),
                                captions="none-yet", asks=1,
                                again=L.iso(now - timedelta(hours=1)))}
        was, got, why = run(st, table, now)
        assert len(was) == 4 and got == {"none-yet": 4} and not why and not table, (got, table)
        assert [v["asks"] for v in st["videos"].values()] == [2, 2, 2, 2]
        assert not any(v.get("vouched") for v in st["videos"].values()), \
            "a run that captioned nothing vouched for a recording's \"none\""

        # With a refusal standing it is news. More retries a week old than a
        # run has requests for, each answered "none" only by runs that
        # captioned nothing, and YouTube's last word to this machine a 429:
        # three requests, one track each, and the hold is renewed. It was
        # all of them, both tracks, exit 0, and nothing said.
        weeks = [f"S{k:02d}" for k in range(L.MAX_CAPTIONS + 4)]
        standing = {"count": 1, "at": L.iso(now - timedelta(days=2)), "until": 0,
                    "until_iso": "", "why": "HTTP Error 429: Too Many Requests", "most": 8}
        st = {"videos": waiting(weeks, now - timedelta(days=9), captions="none-yet", asks=2,
                                again=L.iso(now - timedelta(hours=1)))}
        table = {"laptop": dict(standing)}
        was, got, why = run(st, table, now)
        assert was == [(v, "en") for v in weeks[:L.ALL_NONE]], \
            f"with a refusal standing, a run of retries made {len(was)} requests: {was[:8]}"
        rec = table["laptop"]
        assert why and "standing" in why and rec["count"] == 2 and rec.get("silent"), (why, rec)
        assert rec.get("most") == 8, f"the renewed hold lost the small run: {rec}"
        assert abs(rec["until"] - now.timestamp() - (24 - L.EARLY_HOURS) * 3600) < 1, rec
        assert got == {"none-yet": L.ALL_NONE, "deferred": len(weeks) - L.ALL_NONE}, got
        assert {v["captions"] for v in st["videos"].values()} == {"none-yet", "deferred"}
        # Vouched for -- a run that captioned something heard each of them
        # say it -- they are what they were: asked, one track each while the
        # refusal stands, none closed, and nothing read into it.
        st = {"videos": waiting(weeks[:5], now - timedelta(days=9), captions="none-yet", asks=2,
                                vouched=True, again=L.iso(now - timedelta(hours=1)))}
        table = {"laptop": dict(standing)}
        was, got, why = run(st, table, now)
        assert was == [(v, "en") for v in weeks[:5]] and got == {"none-yet": 5} and not why, \
            (was, got, why)
        assert table["laptop"] == standing, table
        assert {v["captions"] for v in st["videos"].values()} == {"none-yet"}
        # And that is what vouches: a "none" heard by a run that captioned
        # something. The recording that was captioned carries no such mark.
        st = {"videos": waiting(["T0", "T1", "T2"], now - timedelta(hours=30))}
        (src / "T2" / "captions.en.json3").write_text(words, encoding="utf-8")
        was, got, why = run(st, {}, now)
        assert got == {"none-yet": 2, "captioned": 1} and not why, (got, why)
        assert [st["videos"][v].get("vouched") for v in ("T0", "T1", "T2")] == [True, True, None], \
            st["videos"]

        # Through the laptop's catch-up: the last line says so, the record
        # holds it, and the recordings are kept as asked, none as closed.
        home = root / "night"
        (home / "archive").mkdir(parents=True)
        names = ["C0", "C1", "C2", "C3"]
        for vid in names:
            (home / "src" / vid).mkdir(parents=True)
        (home / "archive" / "livestreams.json").write_text(json.dumps({
            "version": 1, "channels": {}, "last_run": {}, "refusals": {}, "videos": {
                vid: {"status": "finished", "captions": "deferred", "chamber": "house",
                      "ended": L.iso(now - timedelta(days=9, minutes=-k)), "title": vid}
                for k, vid in enumerate(names)}}), encoding="utf-8")
        os.chdir(home)
        L.read_markers, L.write_summary = (lambda vids: 0), (lambda: 0)

        def evening(day):
            del asked[:]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = L.main(["--catch-up", "--captions-from", "src", "--origin", "laptop",
                               "--now", L.iso(now + timedelta(days=day))])
            assert code == 0, out.getvalue()[-300:]
            line = [ln for ln in out.getvalue().splitlines()
                    if ln.startswith("LIVESTREAMS CATCH-UP:")][-1]
            return list(asked), line, json.loads(Path("archive/youtube.refused.json").read_text(
                encoding="utf-8"))

        was, line, doc = evening(0)
        assert was == [(v, "en") for v in names], was
        assert "4 none-yet" in line and "refused" in line and "no captions" in line, line
        assert doc["laptop"]["count"] == 1 and doc["laptop"].get("silent"), doc
        assert sorted(doc[L.ASKED]) == names and not any(
            e.get("closed") for e in doc[L.ASKED].values()), doc
        # The next evening they are retries, a week old, nothing has vouched
        # for them and the refusal stands: one track each, the third "none"
        # ends the run, the hold is renewed and the last line says so --
        # and still none is taken to have none.
        was, line, doc = evening(1)
        assert was == [(v, "en") for v in names[:L.ALL_NONE]], was
        assert doc["laptop"]["count"] == 2 and "refused" in line and "standing" in line, \
            (doc, line)
        assert not any(e.get("closed") or e.get("vouched") for e in doc[L.ASKED].values()), doc
        assert [doc[L.ASKED][v]["asks"] for v in names] == [2, 2, 2, 1], doc
        for vid in names:
            (home / "src" / vid / "captions.en.json3").write_text(words, encoding="utf-8")
        was, line, doc = evening(3)
        assert "4 captioned" in line and doc["laptop"]["count"] == 0 and L.ASKED not in doc, \
            (line, doc)

        # And what a good evening vouched for stays vouched in the laptop's
        # own record, which is all it has: three that answered "none" on an
        # evening another recording was captioned, then a 429 on the record,
        # then an evening with nothing new. They are asked, one track each,
        # and nothing is read into them.
        home = root / "night2"
        (home / "archive").mkdir(parents=True)
        names = ["V0", "V1", "V2", "G0"]
        for vid in names:
            (home / "src" / vid).mkdir(parents=True)
        (home / "src" / "G0" / "captions.en.json3").write_text(words, encoding="utf-8")
        (home / "archive" / "livestreams.json").write_text(json.dumps({
            "version": 1, "channels": {}, "last_run": {}, "refusals": {}, "videos": {
                vid: {"status": "finished", "captions": "deferred", "chamber": "house",
                      "ended": L.iso(now - timedelta(days=2, minutes=-k)), "title": vid}
                for k, vid in enumerate(names)}}), encoding="utf-8")
        os.chdir(home)
        was, line, doc = evening(0)
        assert "3 none-yet" in line and "1 captioned" in line and "refused" not in line, line
        assert all(doc[L.ASKED][v].get("vouched") for v in names[:3]), \
            f"the laptop's record does not say a good run heard them: {doc}"
        doc["laptop"] = {"count": 1, "at": L.iso(now), "until": 0, "until_iso": "",
                         "why": "HTTP Error 429: Too Many Requests"}
        Path("archive/youtube.refused.json").write_text(json.dumps(doc), encoding="utf-8")
        was, line, doc = evening(1)
        assert was == [(v, "en") for v in names[:3]], was
        assert doc["laptop"]["count"] == 1 and "refused" not in line, \
            f"three vouched retries renewed the hold on the laptop: {line} {doc['laptop']}"
        os.chdir(here)
        return "ok", ("ten of nothing but none: a refusal on the record, twelve hours' hold, "
                      "nothing closed; the run after stops at three and the hold doubles; "
                      "captions again clear it, new recordings first; two are too few and "
                      "retries are not news -- until a refusal stands, when a run of nothing "
                      f"but {len(weeks)} unvouched retries is three requests and a renewed hold; "
                      "the catch-up's last line says it")
    finally:
        L.ask_track, L.read_markers, L.write_summary = real_ask, real_read, real_summary
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)


@check("livestreams", "after a refusal nothing is asked for twelve hours, the wait "
                      "doubles, and the next runs are small", needs=("livestreams",))
def _ls_hold(livestreams):
    """A refusal is kept per machine: this one's holds it for twelve hours --
    36 until 1 October 2026, which cost the laptop two evenings for one 429
    -- so its next run a day later opens with one request, and a second
    refusal in a row doubles the wait. Inside a hold nothing is asked at all.
    The laptop's own record is untouched by it.

    A wait of a day or more is two hours short of it. The runs come a day
    apart to the minute or the second, never exactly -- GitHub's started at
    08:42:23 on 28 September 2026 and 08:45:38 on the 30th -- so a hold of
    exactly 24 hours was one day or two by that accident.

    And a refusal is the only measure of "too much" YouTube gives. The run
    after one asks for six new recordings at most, or half of what the
    refused run had been answered if that is more, and each run that ends
    without a refusal lets the next ask for two more.

    A refusal that did not say so -- a run of nothing but "no captions" --
    sets no size and keeps the one in force, whether the record before it
    wrote the figure down or is one from before figures were kept. The
    laptop's record of its 429 of 30 September 2026 is the second kind, and
    one evening of "none" after it let the run after that ask for twenty."""
    import contextlib
    import io
    from datetime import datetime, timedelta, timezone
    L = livestreams
    root = Path(tempfile.mkdtemp())
    quiet = contextlib.redirect_stdout(io.StringIO())
    quiet.__enter__()
    real_ask, asked = L.ask_track, []

    def ask(vid, track, work=L.WORK, source=None, timeout=300):
        assert source, f"{vid}: an ask with no saved answers would have started yt-dlp"
        asked.append(vid)
        return real_ask(vid, track, work, source, timeout)

    L.ask_track = ask
    try:
        src = root / "src"
        words = json.dumps(_json3(["I am opening the hearing on House Bill 1491"]))
        for vid in ("A", "B"):
            (src / vid).mkdir(parents=True)
            (src / vid / "ERROR.txt").write_text("HTTP Error 429: Too Many "
                                                 "Requests", encoding="utf-8")
        import argparse as _ap
        a = _ap.Namespace(max_captions=20, budget=45, delay=0, jitter=0, timeout=60,
                          stop_after=3, captions_from=str(src), origin="runner")
        t0 = datetime(2026, 9, 25, 6, 30, tzinfo=timezone.utc)
        st = {"videos": {v: {"status": "finished", "captions": "waiting",
                             "ended": L.iso(t0 - timedelta(hours=20))}
                         for v in ("A", "B")}}
        table = {}
        assert (L.HOLD_HOURS, L.HOLD_MAX, L.EARLY_HOURS) == (12, 168, 2), \
            (L.HOLD_HOURS, L.HOLD_MAX, L.EARLY_HOURS)

        def run(at, vids=("A", "B")):
            del asked[:]
            return L.run_captions(st, list(vids), [], L.Refusals(table, "runner"), at, a,
                                  work=root / "work")

        got, why = run(t0)
        assert why and got["deferred"] == 2 and asked == ["A"], (got, why, asked)
        assert table["runner"]["count"] == 1
        held = table["runner"]["until"] - t0.timestamp()
        assert abs(held - 12 * 3600) < 1, held / 3600
        # Inside the hold nothing is attempted, an hour in or a minute before
        # its end. The source would now answer, so an attempt would show as a
        # caption file.
        for vid in ("A", "B"):
            (src / vid / "ERROR.txt").unlink()
            (src / vid / "captions.en.json3").write_text(words, encoding="utf-8")
        for inside in (timedelta(hours=1), timedelta(hours=11, minutes=59)):
            got, why = run(t0 + inside)
            assert why and got["deferred"] == 2 and not asked, (inside, got, why)
            assert not (root / "work" / "A").exists(), f"asked inside the hold, {inside} in"
        # A refusal on the laptop is its own: the runner's does not hold it.
        assert not L.Refusals(table, "laptop").held(t0 + timedelta(hours=1))
        # The next night, past the hold: one request, refused again, and
        # nothing after it. The wait doubles -- to a day less two hours, so
        # the run a day later is past it even when it starts early.
        (src / "A" / "captions.en.json3").unlink()
        (src / "A" / "ERROR.txt").write_text("HTTP Error 429", encoding="utf-8")
        t1 = t0 + timedelta(hours=24)
        got, why = run(t1)
        assert table["runner"]["count"] == 2 and why and asked == ["A"], (table, asked)
        held = table["runner"]["until"] - t1.timestamp()
        assert abs(held - 22 * 3600) < 1, held / 3600
        assert not (root / "work" / "B").exists(), "went on past a refusal"
        ref = L.Refusals(table, "runner")
        assert ref.held(t1 + timedelta(hours=21, minutes=59))
        assert not ref.held(t1 + timedelta(hours=24) - timedelta(minutes=90)), \
            "a run a day later, started ninety minutes early, is still inside the hold"
        # Doubling stops at a week: 12, then two hours short of 24, 48, 96, 168.
        probe, at, waits = {"runner": dict(table["runner"], count=0)}, t0, []
        for _ in range(6):
            waits.append(L.Refusals(probe, "runner").note(at, "HTTP Error 429"))
        assert waits == [12, 22, 46, 94, 166, 166], waits
        # And an answer clears it.
        (src / "A" / "ERROR.txt").unlink()
        (src / "A" / "captions.en.json3").write_text(words, encoding="utf-8")
        got, why = run(t0 + timedelta(hours=49), ("A",))
        assert got["captioned"] == 1 and table["runner"]["count"] == 0, (got, table)

        # How much the runs after a refusal ask for. Thirty waiting; the
        # thirteenth request of the first run is refused.
        names = [f"G{k:02d}" for k in range(30)]
        for vid in names:
            (src / vid).mkdir()
            (src / vid / "captions.en.json3").write_text(words, encoding="utf-8")
        (src / "G12" / "captions.en.json3").unlink()
        (src / "G12" / "ERROR.txt").write_text("HTTP Error 429", encoding="utf-8")
        st = {"videos": {v: {"status": "finished", "captions": "waiting",
                             "ended": L.iso(t0 - timedelta(hours=40 - k))}
                         for k, v in enumerate(names)}}
        table, sizes, ceilings = {}, [], []
        for day in range(4):
            del asked[:]
            at = t0 + timedelta(days=day)
            first, again = L.caption_queue(st, at)
            got, why = L.run_captions(st, first, again, L.Refusals(table, "runner"), at, a,
                                      work=root / "work")
            sizes.append(len(asked))
            ceilings.append(table["runner"].get("most"))
            assert bool(why) == (day == 0), (day, why)
            if day == 0:
                (src / "G12" / "ERROR.txt").unlink()
                (src / "G12" / "captions.en.json3").write_text(words, encoding="utf-8")
        assert sizes == [13, 6, 8, 4], f"the runs after a refusal asked for {sizes}"
        assert ceilings == [6, 8, 10, 12], ceilings
        # Refused after thirty answers, the next run may ask for fifteen.
        big = {}
        L.Refusals(big, "x").note(t0, "HTTP Error 429", answered=30)
        assert L.Refusals(big, "x").most(20) == 15 and L.Refusals(big, "x").most(10) == 10, big
        # The ceiling comes back, and a record from before this was kept --
        # a refusal standing, no figure -- is read as the small run.
        near = {"x": {"count": 0, "most": 18}}
        L.Refusals(near, "x").eased(18, 20)
        assert "most" not in near["x"], near
        assert L.Refusals({"x": {"count": 1, "until": 0}}, "x").most(20) == L.AFTER_REFUSAL
        assert L.Refusals({"x": {"count": 1, "silent": True}}, "x").most(20) == 20
        assert L.Refusals({}, "x").most(20) == 20
        # A silent refusal keeps the small run that was in force: a figure
        # the record holds, or the one an older record without a figure is
        # read as. Where none was in force it sets none.
        for before, want in (({"count": 1, "until": 0}, L.AFTER_REFUSAL),
                             ({"count": 1, "until": 0, "most": 9}, 9),
                             ({"count": 0, "most": 14}, 14),
                             ({"count": 1, "silent": True}, 20), ({}, 20)):
            kept = {"x": dict(before)} if before else {}
            for again in (1, 2):
                L.Refusals(kept, "x").note(t0, "nothing but \"none\"", silent=True)
                assert L.Refusals(kept, "x").most(20) == want, \
                    f"silent refusal {again} after {before}: the next run may ask for " \
                    f"{L.Refusals(kept, 'x').most(20)}, not {want}"
        # Through two runs, on the laptop's own record of 30 September 2026:
        # a 429, no figure. Twenty wait. The first evening every answer is
        # "none"; the next, captions are there -- and the run is the small
        # one a 429 calls for, six new and the two retries on top.
        names = [f"H{k:02d}" for k in range(20)]
        for vid in names:
            (src / vid).mkdir()
        st = {"videos": {v: {"status": "finished", "captions": "deferred",
                             "ended": L.iso(t0 - timedelta(hours=40 - k))}
                         for k, v in enumerate(names)}}
        table = {"runner": {"at": "2026-09-30T21:19:01Z", "count": 1, "until": 0,
                            "until_iso": "", "why": "HTTP Error 429: Too Many Requests"}}
        del asked[:]
        first, again = L.caption_queue(st, t0)
        got, why = L.run_captions(st, first, again, L.Refusals(table, "runner"), t0, a,
                                  work=root / "work")
        assert asked == names[:L.ALL_NONE] and why and table["runner"].get("silent"), \
            (asked, why, table)
        assert table["runner"].get("most") == L.AFTER_REFUSAL, \
            f"a silent refusal after a 429 with no figure lost the small run: {table}"
        for vid in names:
            (src / vid / "captions.en.json3").write_text(words, encoding="utf-8")
        del asked[:]
        first, again = L.caption_queue(st, t0 + timedelta(days=1))
        got, why = L.run_captions(st, first, again, L.Refusals(table, "runner"),
                                  t0 + timedelta(days=1), a, work=root / "work")
        fresh = [v for v in asked if v in names[L.ALL_NONE:]]
        assert len(fresh) == L.AFTER_REFUSAL and len(asked) == L.AFTER_REFUSAL + L.AGAIN_MIN, \
            f"the run after a silent refusal asked for {len(fresh)} new recordings: {asked}"
        assert not why and table["runner"]["most"] == L.AFTER_REFUSAL + L.EASE, (why, table)
        return "ok", ("held 12h and asked nothing inside it, then one request, then 22h, so "
                      "the run a day later is past it; 12, 22, 46, 94, 166 at most; cleared "
                      "by an answer; refused at its 13th request, the next runs ask 6, 8, 10; "
                      "a silent refusal after a 429 keeps the six, figure on the record or not")
    finally:
        L.ask_track = real_ask
        quiet.__exit__(None, None, None)
        shutil.rmtree(root, ignore_errors=True)


@check("livestreams", "the laptop keeps its count for a recording GitHub's machine "
                      "captioned, and starts over only when that is news",
       needs=("livestreams",))
def _ls_laptop_count(livestreams):
    """The laptop wants a recording GitHub's machine captioned: the files
    never come to it, and until it has read the recording itself the night
    goes on carrying the reading. But its own count of what it asked and got
    no captions for dropped every entry the night's state called captioned,
    every evening. So one that answered the laptop "no captions", or
    "private", was asked every evening, ahead of the new ones, its count
    stuck at one -- and three such on a quiet evening are three first asks
    of "none", which is the all-none hold, every time.

    From saved files, a recording GitHub's machine captioned that answers
    the laptop "no captions", and one new recording with captions a day:

      - it is asked on evenings 0, 1, 3 and 7 and no other, after the new
        recording from the second on, and at the last -- a week on -- for
        both tracks, and closed;
      - the night's state then says GitHub's machine got its captions AFTER
        the laptop last asked. That is news, so the laptop starts over: one
        ask, first, one track. An evening later the state says nothing new,
        and the count stands;
      - once the night has seen the laptop's reading, the entry goes;
      - the night's state is never written.
    """
    import contextlib
    import io
    from datetime import datetime, timedelta, timezone
    L = livestreams
    root = Path(tempfile.mkdtemp())
    here = os.getcwd()
    real_ask, real_read, real_summary = L.ask_track, L.read_markers, L.write_summary
    asked = []

    def ask(vid, track, work=L.WORK, source=None, timeout=300):
        assert source, f"{vid}: an ask with no saved answers would have started yt-dlp"
        asked.append((vid, track))
        return real_ask(vid, track, work, source, timeout)

    L.ask_track = ask
    try:
        words = json.dumps(_json3(["I am opening the hearing on House Bill 1491"]))
        t0 = datetime(2027, 1, 14, 2, 0, tzinfo=timezone.utc)
        (root / "archive").mkdir()
        (root / "src" / "RUN1").mkdir(parents=True)
        os.chdir(root)
        L.read_markers, L.write_summary = (lambda vids: 0), (lambda: 0)
        state = {"version": 1, "channels": {}, "last_run": {}, "refusals": {}, "videos": {
            "RUN1": {"status": "finished", "captions": "captioned", "by": "runner",
                     "carry": True, "result": {"segs": {}}, "chamber": "house", "title": "x",
                     "fetched": L.iso(t0 - timedelta(hours=17)),
                     "ended": L.iso(t0 - timedelta(days=1))}}}
        record = root / "archive" / "youtube.refused.json"

        def evening(day):
            at = t0 + timedelta(days=day)
            vid = f"E{day:02d}"
            (root / "src" / vid).mkdir()
            (root / "src" / vid / "captions.en.json3").write_text(words, encoding="utf-8")
            state["videos"][vid] = {"status": "finished", "captions": "deferred",
                                    "chamber": "house", "title": vid,
                                    "ended": L.iso(at - timedelta(hours=8))}
            text = json.dumps(state)
            (root / "archive" / "livestreams.json").write_text(text, encoding="utf-8")
            del asked[:]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = L.main(["--catch-up", "--captions-from", "src", "--origin", "laptop",
                               "--now", L.iso(at)])
            assert code == 0, out.getvalue()[-300:]
            assert (root / "archive" / "livestreams.json").read_text(encoding="utf-8") == text, \
                "the catch-up wrote the night's state"
            assert (vid, "en") in asked, f"evening {day}: the new recording was not asked for"
            kept = json.loads(record.read_text(encoding="utf-8")).get(L.ASKED) or {}
            return [x for x in asked if x[0] == "RUN1"], [v for v, _ in asked], kept

        seen, counts = [], []
        for day in range(10):
            mine, order, kept = evening(day)
            if mine:
                seen.append(day)
                counts.append(kept["RUN1"]["asks"])
                assert day == 0 or order[0] == f"E{day:02d}", \
                    f"evening {day}: the recording asked before came first: {order}"
                want = L.CAPTION_TRACKS if day == 7 else L.CAPTION_TRACKS[:1]
                assert mine == [("RUN1", t) for t in want], (day, mine)
        assert seen == [0, 1, 3, 7] and counts == [1, 2, 3, 4], \
            f"asked on evenings {seen}, its count {counts}"
        assert kept["RUN1"].get("closed") == "none-published", kept

        # News: GitHub's machine got its captions after the laptop last asked.
        state["videos"]["RUN1"]["fetched"] = L.iso(t0 + timedelta(days=9, hours=12))
        mine, order, kept = evening(10)
        assert mine == [("RUN1", "en")] and order[0] == "RUN1", (mine, order)
        assert kept["RUN1"]["asks"] == 1 and not kept["RUN1"].get("closed"), kept
        # And the evening after it is not news any more: the count stands.
        mine, order, kept = evening(11)
        assert order[0] == "E11" and mine == [("RUN1", t) for t in L.CAPTION_TRACKS], (mine, order)
        assert kept["RUN1"]["asks"] == 2, kept
        # The night has seen the laptop's reading: nothing more is wanted.
        state["videos"]["RUN1"].update(adopted="2027-01-26", carry=False)
        mine, order, kept = evening(12)
        assert not mine and "RUN1" not in kept, (mine, kept)
        os.chdir(here)
        return "ok", ("a recording GitHub's machine captioned and the laptop cannot: asked on "
                      "evenings 0, 1, 3 and 7, counted each time, after the new ones, then "
                      "closed; asked afresh once the state says its captions are newer than "
                      "the laptop's last ask; dropped once the night has the laptop's reading")
    finally:
        L.ask_track, L.read_markers, L.write_summary = real_ask, real_read, real_summary
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)


@check("livestreams", "the night sees what its caption results already hold, whether or "
                      "not a recording is due to be asked again", needs=("livestreams", "nightly"))
def _ls_laptop_read(livestreams, nightly):
    """A recording the night asked for and found without captions is not
    due again for a day, then two, four, eight. The night looked for a
    reading of it only among the recordings due, so one read elsewhere that
    same evening (the laptop's evening job, while there was one) stayed
    `none-yet` until its turn came round -- and nightly.py's warning,
    "finished more than 3 days ago has no start time", counted it for up to
    eight days after it had one.

    So: every recording still waiting is looked at, and the ones left for a
    person with them, due or not; one whose captions are on this disk
    likewise; one nothing has read is left exactly as it was. What counts as
    read (in_files) is what the caption results hold: the caption summary
    names it, and candidate_segments.json too -- or no proceeding names it,
    so there is nothing to read it against. Without that second rule a study
    commission captioned on the laptop on 30 September 2026, uVqpWyuJ8fo,
    waited for ever and was the first thing the night asked YouTube for.
    And through the step itself, on the three-night fixture: a recording
    answered "no captions" on night one, not due again for a week, named in
    candidate_segments.json, is settled on night two and leaves the count
    behind the nightly's warning.
    """
    if not _paths.locate("livestreams.py").exists():
        return "skip", "livestreams.py not here"
    from datetime import datetime, timedelta, timezone
    L = livestreams
    root = Path(tempfile.mkdtemp())
    here = os.getcwd()
    try:
        now = datetime(2026, 9, 26, 6, 30, tzinfo=timezone.utc)
        later = L.iso(now + timedelta(days=6))
        work = root / "unit"
        (work / "HERE").mkdir(parents=True)
        (work / "HERE" / "captions.en.json3").write_text(json.dumps(_json3(["good morning"])),
                                                         encoding="utf-8")
        ended = L.iso(now - timedelta(days=9))

        def videos():
            return {
                "DUE": {"status": "finished", "captions": "none-yet", "asks": 1,
                        "again": L.iso(now - timedelta(hours=2)), "ended": ended},
                "LATER": {"status": "finished", "captions": "none-yet", "asks": 3,
                          "vouched": True, "again": later, "ended": ended},
                "LEFT": {"status": "finished", "captions": "for-laptop", "tries": 3,
                         "ended": ended},
                "HERE": {"status": "finished", "captions": "deferred", "asks": 2,
                         "again": later, "ended": ended},
                "NOBODY": {"status": "finished", "captions": "none-yet", "asks": 2,
                           "again": later, "ended": ended},
                "SOON": {"status": "upcoming"}}

        st = {"videos": videos()}
        n = L.settle(st, now, {"DUE", "LATER", "LEFT", "SOON", "ELSEWHERE"}, work)
        v = st["videos"]
        for vid in ("DUE", "LATER", "LEFT"):
            assert v[vid]["captions"] == "captioned" and v[vid].get("read") == "2026-09-26" \
                and v[vid].get("by") == "files", f"{vid}, which the files hold: {v[vid]}"
        assert v["HERE"]["captions"] == "captioned" and v["HERE"].get("by") == "found" \
            and not v["HERE"].get("read"), v["HERE"]
        assert n == 4 and not any(k in v[vid] for vid in ("DUE", "LATER", "LEFT", "HERE")
                                  for k in ("asks", "again", "tries", "vouched")), (n, v)
        assert v["NOBODY"] == videos()["NOBODY"] and v["SOON"] == videos()["SOON"], v
        assert L.caption_queue(st, now) == ([], []), L.caption_queue(st, now)
        # A machine that cannot tell what the files hold settles nothing.
        st = {"videos": videos()}
        assert L.settle(st, now, None, work) == 1 and st["videos"]["LATER"] == videos()["LATER"]

        # What the files hold: the summary and the candidate file both, or the
        # summary alone for a recording no proceeding names; the summary's
        # side maps are not recordings; no summary, the candidate file alone.
        cand, summ = root / "cand.json", root / "spans.json"
        cand.write_text(json.dumps({"BOTH": {}, "CANDONLY": {}, "_absent": {"SIDE": []}}),
                        encoding="utf-8")
        summ.write_text(json.dumps({"recordings": {"BOTH": {}, "STUDY": {}, "NAMED": {}}}),
                        encoding="utf-8")
        named = {"BOTH", "CANDONLY", "NAMED"}
        assert L.in_files(cand, summ, named) == {"BOTH", "STUDY"}, L.in_files(cand, summ, named)
        assert L.in_files(cand, root / "none.json", named) == {"BOTH", "CANDONLY"}
        assert L.in_files(root / "none.json", summ, named) is None

        # Through the step. Night one answers PFSTALE0001 "no captions".
        _ls_fixture(root, L)
        r = _ls_run(root, "--now", "2026-09-25T06:30:00Z")
        assert r.returncode == 0, (r.stdout + r.stderr)[-400:]
        path = root / "archive" / "livestreams.json"
        st = json.loads(path.read_text(encoding="utf-8"))
        stale = st["videos"]["PFSTALE0001"]
        assert stale["captions"] == "none-yet" and stale.get("again"), stale
        # As after its third such answer: not due for a week. And that
        # evening the laptop reads it.
        stale.update(asks=3, again="2026-10-03T04:30:00Z")
        path.write_text(json.dumps(st), encoding="utf-8")
        (root / "candidate_segments.json").write_text(json.dumps({"PFSTALE0001": {}}),
                                                      encoding="utf-8")
        r = _ls_run(root, "--now", L.iso(now))
        assert r.returncode == 0, (r.stdout + r.stderr)[-400:]
        stale = json.loads(path.read_text(encoding="utf-8"))["videos"]["PFSTALE0001"]
        assert stale["captions"] == "captioned" and stale.get("read") == "2026-09-26" \
            and "again" not in stale and "asks" not in stale, \
            f"the files hold its reading and the night did not see: {stale}"
        return "ok", ("three the files hold are settled -- one due, one not due for six "
                      "days, one left for a person -- one with captions on disk is found, one "
                      "nothing has read is untouched; a study commission no proceeding names "
                      "counts as read once summarised; on the fixture a recording not due for "
                      "a week is settled the night after its reading lands")
    finally:
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)


@check("livestreams", "a row it writes is the row fetch_channel_index writes",
       needs=("livestreams",))
def _ls_rows(livestreams):
    """Every row of every committed index in fetch_channel_index's current
    twelve-column shape, rebuilt from the fields the API gives, comes back
    identical -- and the columns are that script's own, read from its source.
    The older eleven-column files are left out: they predate the corrected
    daylight-time rule and the bill-title fallback, which is why they differ.
    """
    src = _source(_paths.locate("fetch_channel_index.py"))
    m = re.search(r"cols = (\[[^\]]*\])", src)
    assert m, "no cols list in fetch_channel_index.main"
    assert ast.literal_eval(m.group(1)) == livestreams.COLS, \
        "livestreams.COLS is not fetch_channel_index's column list"
    n, bad = 0, []
    import proceedings as _P
    for f in _P.video_indexes():
        if f.name.endswith("_livestreams.csv"):
            continue
        with open(f, encoding="utf-8", newline="") as fh:
            rdr = csv.DictReader(fh)
            if rdr.fieldnames != livestreams.COLS:
                continue
            for r in rdr:
                live = {k: r[c] for k, c in (("actualStartTime", "actual_start_utc"),
                                             ("actualEndTime", "actual_end_utc"))
                        if r[c]}
                mine = livestreams.make_row(
                    r["video_id"], r["title"], r["published_at"],
                    {"liveStreamingDetails": live,
                     "contentDetails": {"duration": r["duration_iso"]}})
                n += 1
                if mine != r:
                    bad.append(f"{f.name}: {r['video_id']}")
    if not n:
        return "skip", "no twelve-column videos_*.csv here"
    assert not bad, f"{len(bad)} of {n} rows differ: " + "; ".join(bad[:3])
    return "ok", f"{n:,} committed rows rebuilt identically"


@check("livestreams", "the state is never started over, and no file it "
                      "writes holds the key", needs=("livestreams",))
def _ls_state(livestreams):
    root = Path(tempfile.mkdtemp())
    try:
        _ls_fixture(root, livestreams)
        (root / "archive").mkdir(exist_ok=True)
        (root / "archive" / "livestreams.json").write_text("{not json",
                                                          encoding="utf-8")
        r = _ls_run(root, "--now", "2026-09-25T06:30:00Z")
        assert r.returncode == 1, r.stdout[-300:]
        assert (root / "archive" / "livestreams.json").read_text(encoding="utf-8") \
            == "{not json", "an unreadable state was replaced"
        assert not (root / "videos_house_livestreams.csv").exists()
        # Its rows here and the state not: a kit that came down short.
        (root / "archive" / "livestreams.json").unlink()
        (root / "videos_house_livestreams.csv").write_text(
            ",".join(livestreams.COLS) + "\n", encoding="utf-8")
        r = _ls_run(root, "--now", "2026-09-25T06:30:00Z")
        assert r.returncode == 1 and "did not arrive" in r.stdout, r.stdout[-300:]
        (root / "videos_house_livestreams.csv").unlink()
        # A run with a key in its environment leaves it in no file. A marker,
        # not a key's shape: the check above rightly fails on one of those.
        key = "preflight-sentinel-" + "k" * 21
        env = dict(_ls_env(), YOUTUBE_API_KEY=key)
        r = _sealed_run([sys.executable, _paths.script("livestreams.py"),
                         "--since-state", "--replay", "api", "--captions-from", "src",
                         "--now", "2026-09-25T06:30:00Z"], cwd=str(root), env=env,
                        capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stdout + r.stderr)[-300:]
        assert key not in r.stdout + r.stderr
        leaks = [str(p) for p in root.rglob("*") if p.is_file()
                 and key.encode() in p.read_bytes()]
        assert not leaks, leaks
        # And a recording that would keep an answer carrying the key refuses.
        api = livestreams.Api(key=key, record=str(root / "rec"))
        try:
            api._save("videos?id=x", '{"echo": "' + key + '"}')
            raise AssertionError("an answer carrying the key was recorded")
        except livestreams.Broken:
            pass
        return "ok", ("an unreadable or missing state stops the step; the key "
                      "is in no file and no line of output")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("livestreams", "without yt-dlp nothing is asked for and nothing counts "
                      "against a recording", needs=("livestreams",))
def _ls_no_ytdlp(livestreams):
    """A machine set up without yt-dlp would fail every caption request the
    same way, and three failures hand a recording to the laptop for good. So
    the step says so once, exits 3 -- not configured -- and leaves every
    recording waiting, its rows written as usual."""
    import contextlib
    import importlib.util
    import io
    root = Path(tempfile.mkdtemp())
    here = os.getcwd()
    real = importlib.util.find_spec
    real_ask, asks = livestreams.ask_track, []
    saved = {k: os.environ.pop(k) for k in ("YOUTUBE_API_KEY", "GITHUB_ACTIONS")
             if k in os.environ}
    try:
        _ls_fixture(root, livestreams)
        os.chdir(root)
        importlib.util.find_spec = (lambda name, *a, **k:
                                    None if name == "yt_dlp" else real(name, *a, **k))

        # This run is given no caption source, so an ask would be a real one:
        # it must make none, and one made stops here, not at YouTube.
        def no_ask(vid, track, *a, **k):
            asks.append(vid)
            return "failed", "preflight: an ask was made with no caption source"

        livestreams.ask_track = no_ask
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = livestreams.main(["--since-state", "--replay", "api",
                                     "--now", "2026-09-25T06:30:00Z",
                                     "--origin", "runner"])
        importlib.util.find_spec = real
        assert not asks, f"captions were asked for with no yt-dlp here: {asks}"
        assert code == 3, (code, out.getvalue()[-300:])
        assert "yt-dlp is not installed" in out.getvalue()
        st = json.loads(Path("archive/livestreams.json").read_text(encoding="utf-8"))
        waiting = [v for v, x in st["videos"].items() if x.get("captions") == "waiting"]
        assert sorted(waiting) == ["PFNEW000001", "PFSEN000001", "PFSTALE0001"], \
            st["videos"]
        assert not any(x.get("tries") for x in st["videos"].values())
        assert Path("videos_house_livestreams.csv").exists(), "the rows were not written"
        return "ok", "exit 3, three recordings left waiting with no try counted"
    finally:
        importlib.util.find_spec = real
        livestreams.ask_track = real_ask
        os.environ.update(saved)
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)


@check("livestreams", "a refused YouTube key warns and the night goes out, with the recordings "
                      "it had kept", needs=("livestreams", "nightly"))
def _ls_refused_key_warns(livestreams, NI):
    """A REFUSED YOUTUBE KEY WARNS, AND THE NIGHT GOES OUT (nightly.py; the
    owner's decision 4, 19 November 2026). One good night on replayed answers,
    then a night on which every Data API answer is Google's 403 keyInvalid:
    the step exits 3, says why in its state (last_run "not_set_up"), and
    leaves every recording it knew and its rows byte for byte. The night's
    captions record carries the why; youtube_warned says it in one line of
    what is wrong and what to do, of a kind the gate never holds a night for,
    in the night's warnings and the standing ones; and --close, told the
    livestream step failed, closes the night clean, exit 0, so the publish
    job follows. The same failure with no such record -- the step broken,
    or killed at its limit -- still fails the night."""
    import contextlib
    import io
    import types
    if not _paths.locate("livestreams.py").exists():
        return "skip", "livestreams.py not here"
    root = Path(tempfile.mkdtemp())
    here = os.getcwd()
    saved = {k: os.environ.get(k) for k in ("GITHUB_ACTIONS", "GITHUB_STEP_SUMMARY",
                                            "GITHUB_OUTPUT", "GITHUB_RUN_ID", "GITHUB_SHA")}
    try:
        _ls_fixture(root, livestreams)
        r = _ls_run(root, "--now", "2026-09-25T06:30:00Z")
        assert r.returncode == 0, (r.stdout + r.stderr)[-400:]
        rows = {p.name: p.read_bytes() for p in sorted(root.glob("videos_*_livestreams.csv"))}
        assert len(rows) == 2, sorted(rows)
        before = json.loads((root / "archive" / "livestreams.json").read_text(encoding="utf-8"))
        # Google's answer to a key it refuses, for every call the step makes.
        refused = {"_status": 403, "error": {"code": 403, "message": "API key not valid. "
                                             "Please pass a valid API key.",
                                             "errors": [{"reason": "keyInvalid"}]}}
        idx = json.loads((root / "api" / "index.json").read_text(encoding="utf-8"))
        for name in set(idx.values()):
            (root / "api" / name).write_text(json.dumps(refused), encoding="utf-8")
        r = _ls_run(root, "--now", "2026-09-26T06:30:00Z")
        assert r.returncode == 3, (r.returncode, (r.stdout + r.stderr)[-400:])
        after = json.loads((root / "archive" / "livestreams.json").read_text(encoding="utf-8"))
        unset = after["last_run"].get("not_set_up")
        assert unset and len(unset) == 1 and unset[0].startswith("HTTP 403: keyInvalid") and \
            "key itself was refused" in unset[0], ("the state does not say why", after["last_run"])
        kept = {p.name: p.read_bytes() for p in sorted(root.glob("videos_*_livestreams.csv"))}
        assert kept == rows, "a refused key changed or emptied the recordings' rows"
        assert {k: v.get("status") for k, v in after["videos"].items()} == \
            {k: v.get("status") for k, v in before["videos"].items()}, \
            "a refused key dropped or changed a recording the state knew"

        # The night that follows the step, and its last word.
        os.chdir(root)
        for k in saved:
            os.environ.pop(k, None)
        os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_SHA"] = "9301", "0" * 40
        started = "2026-09-26T06:45:00+00:00"
        caps = NI.captions_record(started, after)
        assert caps["step"] == "tonight" and caps.get("not_set_up") == unset, caps
        warned = NI.youtube_warned(caps)
        assert [k for k, _s in warned] == [NI.KIND_YOUTUBE] and \
            NI.KIND_YOUTUBE.startswith(NI.KIND_HEALTH) and \
            NI.warning_reasons(warned, [], ()) == [], ("not one warning that never holds", warned)
        said = warned[0][1]
        assert said.startswith("YouTube refused the night's key (HTTP 403: keyInvalid)") and \
            "the site keeps the ones it had" in said and NI.YOUTUBE_SECRET in said and \
            len(said) <= 300 and "\n" not in said, said
        assert NI.youtube_warned(NI.captions_record("2026-09-27T09:00:00+00:00", after)) == [], \
            "a night the step did not run warns of last night's key"
        missing = NI.youtube_warned({"not_set_up": ["YOUTUBE_API_KEY is not set, so nothing "
                                                    "new was listed"]})
        assert missing and "secret is empty" in missing[0][1], missing
        v = {"kind": "nightly", "run_id": "9301", "day": "2026-09-26", "started": started,
             "built": True, "publishable": True, "clean": True, "not_clean": [], "captions": caps}
        assert said in [s for _k, s in NI.health_warned(v)] and said in NI.warns_of(v), \
            "the key's warning is not among the night's own health warnings and standing ones"
        v["warnings"] = [s for _k, s in NI.health_warned(v)]

        def close(verdict, outcomes):
            NI.write_json(NI.VERDICT, verdict)
            with contextlib.redirect_stdout(io.StringIO()):
                code = NI.close_verdict(types.SimpleNamespace(
                    weekly=False, dry_run=False, outcome=outcomes))
            return code, json.loads(Path(NI.VERDICT).read_text(encoding="utf-8"))

        code, out = close(dict(v), ["night=success", "livestreams=failure"])
        assert code == 0 and out["clean"] and said in out.get("warnings", []) and \
            said in out.get("standing_warnings", []) and out.get("livestreams_not_set_up"), (
                "a refused key failed the night, or its warning went missing", code, out)
        code, out = close({**v, "captions": {**caps, "not_set_up": []}},
                          ["night=success", "livestreams=failure"])
        assert code == 1 and not out["clean"], \
            "a livestream step that failed for another reason left the night clean"
        code, out = close({**v, "run_id": "9300"}, ["night=success", "livestreams=failure"])
        assert code == 1 and not out["clean"], \
            "an older night's record of a refused key excused tonight's failed step"
        code, out = close(dict(v), ["night=failure", "livestreams=failure"])
        assert code == 1, "a refused key excused another step's failure"
        return "ok", ("a 403 keyInvalid: exit 3, the why in the state, both row files byte for "
                      f"byte and all {len(after['videos'])} recordings kept; one line, never "
                      "holding, in the warnings and standing ones; --close exit 0 and clean; "
                      "exit 1 for no record, another night's record, or another failed step")
    finally:
        os.chdir(here)
        for k, val in saved.items():
            os.environ.pop(k, None) if val is None else os.environ.__setitem__(k, val)
        shutil.rmtree(root, ignore_errors=True)


@check("livestreams", "the nightly's livestreams files are never tracked")
def _ls_ignored():
    """GitHub's machine refuses to deploy a tree with a changed tracked file,
    and livestreams.py writes these there every night."""
    names = ["videos_house_livestreams.csv", "videos_senate_livestreams.csv",
             "archive/livestreams.json", "archive/livestreams.lock",
             "archive/captions-inbox/PFX.json", "archive/captions-laptop.json"]
    r = _run(["git", "check-ignore", *names], capture_output=True, text=True)
    if r.returncode not in (0, 1):
        return "skip", "git check-ignore would not run"
    ignored = set((r.stdout or "").split())
    missing = [n for n in names if n not in ignored]
    assert not missing, "not ignored: " + ", ".join(missing)
    t = _run(["git", "ls-files", "--", *names], capture_output=True, text=True)
    assert not (t.stdout or "").strip(), "tracked: " + t.stdout.strip()
    return "ok", f"{len(names)} ignored and untracked"


def _canary_source(root, n=3910, last=1969.5, video=None):
    """A saved answer for the canary: root/<video>/captions.en.json3 with `n`
    words, the last at `last` seconds, in YouTube's json3 shape."""
    video = video or "tFh6nyiGjOs"
    d = Path(root) / video
    d.mkdir(parents=True, exist_ok=True)
    events = [{"tStartMs": int(i * last * 1000 / max(n - 1, 1)), "dDurationMs": 100,
               "segs": [{"utf8": f"word{i}"}]} for i in range(n)]
    (d / "captions.en.json3").write_text(json.dumps({"events": events}), encoding="utf-8")
    return d


def _tree_names(root):
    return sorted(p.relative_to(root).as_posix() for p in Path(root).rglob("*"))


@check("livestreams", "the captions canary writes one line to its own log and nothing else: no state, "
       "no archive/, no inbox, no bucket, no refusal record, no scratch left behind; a refusal, a "
       "missing file, a shape that is not October's and a held refusal each end it with a "
       "verdict that is not ok", needs=("livestreams",))
def _canary_no_publish(L):
    """THE CAPTIONS CANARY (11 November 2026): the weekly proof that the laptop's
    route still brings back captions that read, with no recording waiting. It
    must change nothing the night or the evening run keeps. Run in an empty
    working folder from saved answers (--captions-from, the stand-in for
    YouTube): the folder holds the log it was told to write and nothing else,
    and the temporary scratch folder is gone. The source of canary() names
    none of the writers of state, the inbox or the bucket."""
    import contextlib
    import inspect
    import io
    src = inspect.getsource(L.canary)
    for banned in ("make_bucket", "FolderBucket", "inbox_add", "inbox_report", "inbox_listing",
                   "save_state", "load_state", "STATE", "LAPTOP_RUN", "LAPTOP_REFUSAL",
                   "refusals.note", "write_summary", "MARKERS", "lock("):
        assert banned not in src, f"canary() names {banned}: it must touch none of the night's files"
    assert "log=False" in src, "the canary's ask must leave the day's yt-dlp log alone"
    here = os.getcwd()
    base = Path(tempfile.mkdtemp())
    before_scratch = set(Path(tempfile.gettempdir()).glob("gr-canary-*"))
    work = base / "cwd"
    work.mkdir()
    log = base / "logs-out" / "captions-canary.log"
    answers = base / "answers"

    def run(at="2026-11-12T10:00:00Z", *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = L.main(["--canary", "--captions-from", str(answers), "--origin", "laptop",
                           "--canary-log", str(log), "--now", at, *extra])
        return code, out.getvalue()
    try:
        os.chdir(work)
        os.environ.pop("GITHUB_ACTIONS", None)
        os.environ.pop(L.HEARTBEAT_ENV, None)
        # ok: the October shape
        _canary_source(answers)
        code, said = run()
        assert code == 0, (code, said)
        lines = log.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1 and " CANARY ok " in lines[0] and lines[0].startswith(
            "2026-11-12T10:00:00Z"), lines
        assert _tree_names(work) == [], f"the canary left files in the working folder: {_tree_names(work)}"
        assert not (set(Path(tempfile.gettempdir()).glob("gr-canary-*")) - before_scratch), \
            "the canary's scratch folder was left behind"
        # not October's shape: a few words
        shutil.rmtree(answers)
        _canary_source(answers, n=500, last=300.0)
        code, said = run("2026-11-12T10:05:00Z")
        assert code == 1 and "FAIL" in log.read_text(encoding="utf-8").splitlines()[-1], said
        # YouTube's refusal, as yt-dlp words it
        shutil.rmtree(answers)
        (answers / L.CANARY_VIDEO).mkdir(parents=True)
        (answers / L.CANARY_VIDEO / "ERROR.txt").write_text(
            "ERROR: Unable to download video subtitles for 'en': HTTP Error 429: Too Many "
            "Requests", encoding="utf-8")
        code, said = run("2026-11-12T10:10:00Z")
        last = log.read_text(encoding="utf-8").splitlines()[-1]
        assert code == 1 and " CANARY FAIL " in last and "refused" in last, last
        # no captions at all (the folder holds nothing)
        shutil.rmtree(answers)
        (answers / L.CANARY_VIDEO).mkdir(parents=True)
        code, said = run("2026-11-12T10:15:00Z")
        assert code == 1 and " CANARY FAIL " in log.read_text(encoding="utf-8").splitlines()[-1]
        assert _tree_names(work) == [], f"a failed canary left files behind: {_tree_names(work)}"
        # a refusal held against this machine: not asked, and not a pass
        (work / "archive").mkdir()
        (work / "archive" / "youtube.refused.json").write_text(json.dumps(
            {"laptop": {"at": "2026-11-12T09:00:00Z", "until": 1e12, "until_iso":
                        "2030-01-01T00:00:00Z", "count": 1, "why": "x"}}), encoding="utf-8")
        before = _tree_names(work)
        asked = []
        real = L.ask_track
        L.ask_track = lambda *a_, **k: asked.append(a_) or ("captioned", "")
        try:
            code, said = run("2026-11-12T10:20:00Z")
        finally:
            L.ask_track = real
        assert code == 1 and not asked and " CANARY skipped " in log.read_text(
            encoding="utf-8").splitlines()[-1], (code, asked)
        assert _tree_names(work) == before, "a skipped canary wrote into the working folder"
        assert (work / "archive" / "youtube.refused.json").read_text(encoding="utf-8").count(
            "count") == 1
        # the runner's machine is not the canary's: refused, and nothing written
        n = len(log.read_text(encoding="utf-8").splitlines())
        with contextlib.redirect_stdout(io.StringIO()):
            code = L.main(["--canary", "--origin", "runner", "--canary-log", str(log)])
        assert code == 1 and len(log.read_text(encoding="utf-8").splitlines()) == n
    finally:
        os.chdir(here)
        shutil.rmtree(base, ignore_errors=True)
    return "ok", ("an October-shaped answer passes; a short file, a refusal, an empty answer and a "
                  "held refusal each give a verdict that is not ok; the working folder is empty "
                  "after all of them and no scratch is left")


@check("livestreams", "the heartbeat is optional: with no address nothing is sent and nothing said, "
       "with one it is pinged once (and /fail on a failed run), a bad address or a failing ping "
       "changes no exit status, and no address is written in the repository", needs=("livestreams",))
def _heartbeat_optional(L):
    import contextlib
    import io
    sent = []
    real_ping, real_url = L._ping, L.heartbeat_url
    here = os.getcwd()
    base = Path(tempfile.mkdtemp())
    saved = os.environ.pop(L.HEARTBEAT_ENV, None)
    try:
        os.chdir(base)
        L._ping = lambda url, body: sent.append(url)
        # nothing set: no ping, no output
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            assert L.heartbeat(True, "x") is False and L.heartbeat(False, "x") is False
        assert not sent and out.getvalue() == "", (sent, out.getvalue())
        # an address that is not https is none
        os.environ[L.HEARTBEAT_ENV] = "http://hc-ping.invalid/abc"
        assert L.heartbeat_url() == "" and L.heartbeat(True) is False and not sent
        os.environ[L.HEARTBEAT_ENV] = "https://hc-ping.invalid/abc"
        assert L.heartbeat(True, "ok") is True and sent == ["https://hc-ping.invalid/abc"], sent
        assert L.heartbeat(False, "bad") is True and sent[-1] == "https://hc-ping.invalid/abc/fail", sent
        # a ping that fails is said once, without the address, and raises nothing
        def broken(url, body):
            raise OSError("down")
        L._ping = broken
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            assert L.heartbeat(True) is False
        assert "hc-ping" not in out.getvalue() and "OSError" in out.getvalue(), out.getvalue()
        # the run's own status is the run's, whatever the ping did
        a = argparse.Namespace(canary=True)
        with contextlib.redirect_stdout(io.StringIO()):
            assert L.with_heartbeat(a, lambda _a: 0) == 0
            assert L.with_heartbeat(a, lambda _a: 1) == 1
            assert L.with_heartbeat(a, lambda _a: (_ for _ in ()).throw(L.Broken("x"))) == 1
        # no ping and no error when nothing is set, for a whole run
        os.environ.pop(L.HEARTBEAT_ENV)
        sent.clear()
        L._ping = lambda url, body: sent.append(url)
        with contextlib.redirect_stdout(io.StringIO()):
            assert L.with_heartbeat(a, lambda _a: 0) == 0
        assert not sent, sent
    finally:
        L._ping, L.heartbeat_url = real_ping, real_url
        os.chdir(here)
        if saved is not None:
            os.environ[L.HEARTBEAT_ENV] = saved
        else:
            os.environ.pop(L.HEARTBEAT_ENV, None)
        shutil.rmtree(base, ignore_errors=True)
    # no address in anything tracked: the example file names the key and holds no URL
    ex = json.loads(_source(_paths.ROOT / "secrets.example.json"))
    assert not re.search(r"https?://\S*(hc-ping|healthchecks)", json.dumps(ex)), ex
    for rel in ("src/ops/livestreams.py", "src/ops/captions_watch.py"):
        text = (_paths.ROOT / rel).read_text(encoding="utf-8")
        assert not re.search(r"hc-ping\.com/[0-9a-f-]{8,}", text), f"{rel} carries a ping address"
    return "ok", "no address, no ping; one address, one ping, /fail on failure; a failing ping changes no status"


@check("livestreams", "the silences are warnings with their thresholds: the laptop's job after 2 days, "
       "the canary after 8 days of no pass, a recording after 3 nights waiting or read with no "
       "timestamp; none fails, and the night's verdict carries the recording one", needs=("captions_watch", "nightly", "livestreams"))
def _captions_silences(W, N, L):
    import contextlib
    import io
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
    assert (W.JOB_SILENT_DAYS, W.CANARY_SILENT_DAYS, W.WAIT_NIGHTS) == (2, 8, 3)
    assert tuple(W.CAPTIONS_WAITING) == tuple(N.CAPTIONS_WAITING), "captions_watch's waiting set drifted"
    assert W.WAIT_MOST_DAYS == N.CAPTION_WAIT_MOST and W.WAIT_NIGHTS == N.CAPTION_WAIT_DAYS

    def stamp(days):
        return (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # the job: exactly two days is on time, a little more is not, no log is said
    assert W.job_silent(stamp(2.0) + ": 0 recording(s) wait", now) == []
    assert len(W.job_silent(stamp(2.1) + ": 0 recording(s) wait", now)) == 1
    assert len(W.job_silent("", now)) == 1
    assert W.job_silent(stamp(5) + ": a\n" + stamp(0.5) + ": b", now) == [], "the newest line decides"
    # the canary: only an ok line is a pass
    ok = lambda d: f"{stamp(d)} CANARY ok -- x"
    assert W.canary_silent(ok(8.0), now) == []
    assert len(W.canary_silent(ok(8.1), now)) == 1
    assert len(W.canary_silent("", now)) == 1 and "ever" in W.canary_silent("", now)[0]
    for bad in ("FAIL -- refused", "skipped -- held"):
        s = W.canary_silent(f"{stamp(1)} CANARY {bad}", now)
        assert len(s) == 1 and bad in s[0], s
    assert W.canary_silent(ok(3) + f"\n{stamp(1)} CANARY FAIL -- y", now) == [], \
        "a pass inside eight days stands though a later week failed (the failure is the next run's news)"

    # a recording: waiting or read and unplaced, after three days, within thirty
    def vid(days, captions, title="T", **kw):
        return dict({"status": "finished", "captions": captions, "title": title,
                     "ended": stamp(days)}, **kw)
    st = {"videos": {
        "W3": vid(3.0, "waiting"), "W4": vid(3.1, "deferred", "Late one"),
        "OLD": vid(31, "waiting"), "LIVE": {"status": "live", "captions": "waiting",
                                              "ended": stamp(9)},
        "AD": vid(9, "waiting", adopted=True),
        "U1": vid(9, "captioned", "Unplaced committee"), "P1": vid(9, "captioned", "Placed"),
        "U0": vid(2.9, "captioned", "Too new")}}
    got = W.waiting_long(st, {"P1"}, now)
    assert len(got) == 2, got
    assert "1 recording finished more than 3 nights ago still waits" in got[0] and "Late one" in got[0], got
    assert "Unplaced committee" in got[1] and "Placed" not in got[1].replace("Unplaced", "") and \
        "Too new" not in got[1], got
    assert len(W.waiting_long(st, None, now)) == 1, "no proceedings.csv leaves the unplaced half out"
    # a read recording whose meeting the calendar's notices show took up no bill can never have a
    # timestamp: left out (and counted) where the notices list no bill; kept where one lists a
    # bill, where no meeting fits, or where the notices are not there
    notices = [{"date": "2026-11-03", "committee": "Unplaced Committee", "bill": "", "kind": "regular meeting"}]
    st2 = {"videos": {"U1": vid(9, "captioned", "Unplaced Committee (11/03/2026)")}}
    left = []
    got = W.waiting_long(st2, set(), now, no_bill=W.no_bill_noticed(notices), left_out=left)
    assert got == [] and left == ["Unplaced Committee (11/03/2026)"], (got, left)
    for said_, want in (([dict(notices[0], bill="HB1", kind="public hearing")], False),
                        ([dict(notices[0], date="2026-11-04")], None),
                        ([dict(notices[0], committee="Something Else Entirely")], None),
                        (notices, True), (None, None)):
        assert W.no_bill_noticed(said_)("Unplaced Committee (11/03/2026)") is want, (said_, want)
    assert W.no_bill_noticed(notices)("Unplaced Committee") is None, "a title with no day cannot be placed"
    keep = []
    both = [notices[0], dict(notices[0], bill="HB1", kind="public hearing")]
    assert len(W.waiting_long(st2, set(), now, no_bill=W.no_bill_noticed(both), left_out=keep)) == 1 \
        and keep == [], "a meeting with a bill listed stays in the warning"
    assert len(W.waiting_long(st2, set(), now, no_bill=W.no_bill_noticed(None), left_out=keep)) == 1
    assert W.waiting_long({}, set(), now) == [] and W.waiting_long(None, set(), now) == []
    # and the night carries it, as a warning of the kind that never holds
    here = os.getcwd()
    base = Path(tempfile.mkdtemp())
    try:
        os.chdir(base)
        (base / "proceedings.csv").write_text("video_id\nP1\n", encoding="utf-8")
        (base / "meetings.json").write_text(json.dumps(notices), encoding="utf-8")
        st_nb = {"videos": dict(st["videos"], U1=vid(9, "captioned", "Unplaced Committee (11/03/2026)"))}
        n_log = len(N.LOG)
        got = N.recordings_waiting_long(st_nb, now)
        assert got == [], "a meeting that listed no bill was warned of"
        assert any("left out of the warning" in ln and "  1 recording" in ln for ln in N.LOG[n_log:]), \
            "the night did not say how many were left out"
        (base / "meetings.json").unlink()
        got = N.recordings_waiting_long(st, now)
        assert len(got) == 1 and all(k.startswith(N.KIND_NOT_MOVING) for k, _s in got) and             "Unplaced committee" in got[0][1], "the night's half is the unplaced one; the waiting one is KIND_CAPTIONS_WAIT's"
        v = {}
        said = N.not_moving(v, "2026-11-12", st, {"at": stamp(0.1)}, now=now, fetched=False)
        assert len([x for x in said if "read with no timestamp on the record" in x[0]]) == 1, said
        assert N.warning_reasons(said, None, ()) == [], "a silence held a night"
        # the command: read-only, exit 0 though it warns
        (base / "logs").mkdir()
        (base / "archive").mkdir()
        (base / "archive" / "livestreams.json").write_text(json.dumps(st), encoding="utf-8")
        before = _tree_names(base)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            assert W.main(["--root", str(base), "--now", now.isoformat()]) == 0
        assert out.getvalue().count("WARNING:") == 4, out.getvalue()
        assert _tree_names(base) == before, "captions_watch wrote something"
    finally:
        os.chdir(here)
        shutil.rmtree(base, ignore_errors=True)
    return "ok", "job 2 days, canary 8 days, recording 3 nights; warnings only; the night carries the last"


@check("livestreams", "the captions inbox, the laptop's side: it asks YouTube only for what the "
       "night's state lists as waiting, adds only inbox entries, never writes state or kit, "
       "and asks and sends nothing twice", needs=("livestreams", "cloud"))
def _inbox_laptop(livestreams, cloud):
    """The laptop is to write no state: the night is its one writer. So
    --to-inbox reads the bucket's state/livestreams.json in memory and puts
    caption files under inbox/captions/ through cloud.inbox_add, which adds
    and never replaces. From a bucket folder holding the state, the kit
    manifest and a kit file, and saved caption answers:

      - a dry run says what it would ask for, and asks, sends and writes
        nothing, not even archive/;
      - the run asks YouTube for the one waiting recording without captions
        on this disk, and none of the captioned, failed-out or unfinished
        ones; sends that and the one whose captions are already here; and
        every key it writes is under the inbox, every key that was there is
        as it was, and no copy of the night's state appears on the laptop;
      - each manifest names its file's size and sha256 truly;
      - a waiting recording that already has an entry is not asked for,
        though its captions are not on this disk (the entered filter);
      - a captions.en.json3 with no words of its own is never sent on the
        word of a file beside it (the review of 17 October 2026): the track
        that holds words is sent instead, and with only a transcript beside
        it nothing is, and it is said -- sent, it would be refused by the
        night and sent again every evening;
      - run again, it asks and sends nothing;
      - each run adds its own record beside the inbox, named for when it ran
        and never over one there (18 October 2026, cloud.inbox_report):
        what it sent, and the laptop's refusal and hold where one stands --
        and a run with a refusal standing still exits 0;
      - inbox_add leaves an entry already there alone, and refuses a key
        outside the inbox or a file that is not a caption file before
        sending anything; inbox_report refuses a record naming no time, or
        one too heavy to be one.
    """
    import contextlib
    import hashlib
    import io
    L, CL = livestreams, cloud
    root = Path(tempfile.mkdtemp(prefix="gr-inbox-"))
    here = os.getcwd()
    real_ask, real_folder = L.ask_track, CL.FolderBucket
    saved = {k: os.environ.get(k) for k in ("GITHUB_ACTIONS", CL.NO_BUCKET)}
    asked, writes = [], []

    def ask(vid, track, work=L.WORK, source=None, timeout=300):
        assert source, f"{vid}: an ask with no saved answers would have started yt-dlp"
        asked.append(vid)
        return real_ask(vid, track, work, source, timeout)

    class Watched(real_folder):
        def put_file(self, src, key, meta):
            writes.append(key)
            super().put_file(src, key, meta)

        def put_bytes(self, key, data):
            writes.append(key)
            super().put_bytes(key, data)

        def copy(self, src, dst):
            writes.append(dst)
            super().copy(src, dst)

        def delete(self, key):
            writes.append(f"delete {key}")
            super().delete(key)

    bucket, laptop = root / "bucket", root / "laptop"
    now = "2026-10-17T23:30:00Z"

    def run(*extra, at=now):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = L.main(["--to-inbox", "--local-bucket", str(bucket), "--captions-from",
                           "src", "--origin", "laptop", "--now", at, *extra])
        return code, out.getvalue()

    try:
        os.environ.pop("GITHUB_ACTIONS", None)
        os.environ[CL.NO_BUCKET] = "1"
        L.ask_track, CL.FolderBucket = ask, Watched
        fin = {"status": "finished", "chamber": "house", "title": "x",
               "ended": "2026-10-16T18:00:00Z"}
        state = {"version": 1, "channels": {}, "last_run": {}, "refusals": {}, "videos": {
            "PFDEFER01": dict(fin, captions="deferred"),
            "PFHERE01": dict(fin, captions="waiting"),
            "PFENTER1": dict(fin, captions="deferred"),
            "PFMUTE01": dict(fin, captions="waiting"),
            "PFMUTE02": dict(fin, captions="waiting"),
            "PFREAD01": dict(fin, captions="captioned", by="runner", read="2026-10-16"),
            "PFFAIL01": dict(fin, captions="failed", tries=L.MAX_TRIES),
            "PFLIVE01": {"status": "live", "chamber": "house", "captions": "waiting"}}}
        for rel, body in {"state/livestreams.json": json.dumps(state),
                          "state/refused.json": "{}", "kit/x.json": "{}",
                          "state/kit-manifest.json": json.dumps(
                              {"files": {"x.json": {"size": 2}}})}.items():
            (bucket / rel).parent.mkdir(parents=True, exist_ok=True)
            (bucket / rel).write_text(body, encoding="utf-8")
        words = _inbox_words()
        mute = json.dumps({"wireMagic": "pb3", "events": [{"tStartMs": 0, "id": 1}]})
        for vid in ("PFDEFER01", "PFREAD01", "PFFAIL01", "PFLIVE01", "PFENTER1"):
            (laptop / "src" / vid).mkdir(parents=True)
            (laptop / "src" / vid / "captions.en.json3").write_text(words, encoding="utf-8")
        for vid, files in (("PFHERE01", {"captions.en.json3": words}),
                           ("PFMUTE01", {"captions.en.json3": mute,
                                         "captions.en-orig.json3": words}),
                           ("PFMUTE02", {"captions.en.json3": mute, "transcript.json": json.dumps(
                               [{"start": 5.0, "end": 9.0, "text": "opening the hearing"}])})):
            (laptop / "work" / vid).mkdir(parents=True)
            for name, body in files.items():
                (laptop / "work" / vid / name).write_text(body, encoding="utf-8")
        assert CL.inbox_add(real_folder(bucket, create=False), "PFENTER1",
                            laptop / "src" / "PFENTER1" / "captions.en.json3",
                            {"fetched": now}), "the fixture's entry already in the inbox"
        os.chdir(laptop)
        before = _inbox_files(bucket)

        code, said = run("--dry-run")
        last = said.strip().splitlines()[-1]
        assert code == 0 and "would ask YouTube for 1," in last, said[-500:]
        assert not asked and not writes and _inbox_files(bucket) == before, (asked, writes)
        assert not (laptop / "archive").exists(), "a dry run of --to-inbox wrote under archive/"

        code, said = run()
        last = said.strip().splitlines()[-1]
        assert code == 0 and last.startswith("LIVESTREAMS TO-INBOX:") \
            and "3 sent to the inbox" in last and "1 not sent" in last \
            and "NOT sent: PFMUTE02" in said, said[-700:]
        assert asked == ["PFDEFER01"], f"--to-inbox asked YouTube for {asked}"
        after = _inbox_files(bucket)
        changed = [k for k, v in before.items() if after.get(k) != v]
        assert not changed, f"--to-inbox changed what the bucket held: {changed}"
        added = sorted(set(after) - set(before))
        assert added and all(k.startswith((CL.INBOX, ".meta/" + CL.INBOX, CL.INBOX_RUNS))
                             for k in added) \
            and all(w.startswith((CL.INBOX, CL.INBOX_RUNS)) for w in writes), \
            f"--to-inbox wrote outside {CL.INBOX} and {CL.INBOX_RUNS}: {added} {writes}"
        assert not (laptop / "archive" / "livestreams.json").exists(), \
            "--to-inbox wrote a copy of the night's state on the laptop"
        # THE RUN'S OWN RECORD (18 October 2026): one, named for when it ran,
        # saying what it sent and that no refusal stands.
        runs = CL.inbox_runs(real_folder(bucket, create=False))
        assert runs == [f"{CL.INBOX_RUNS}20261017T233000Z.json"], f"the run records: {runs}"
        rec = json.loads((bucket / runs[0]).read_text(encoding="utf-8"))
        assert rec.get("at") == now and rec.get("sent") == 3 and rec.get("unsent") == 1 \
            and rec.get("code") == 0 and rec.get("refusal") is None, rec
        entries = CL.inbox_listing(real_folder(bucket, create=False))
        assert sorted(entries) == ["PFDEFER01", "PFENTER1", "PFHERE01", "PFMUTE01"], entries
        for vid, e in entries.items():
            doc = json.loads((bucket / e["manifest"]).read_text(encoding="utf-8"))
            body = (bucket / doc["key"]).read_bytes()
            want = "captions.en-orig.json3" if vid == "PFMUTE01" else "captions.en.json3"
            assert doc["video"] == vid and doc["file"] == want and body == words.encode("utf-8") \
                and doc["size"] == len(body) \
                and doc["sha256"] == hashlib.sha256(body).hexdigest(), doc

        del asked[:], writes[:]
        code, said = run()
        assert code == 0 and not asked and not writes \
            and "0 sent to the inbox" in said.strip().splitlines()[-1], (asked, writes, said[-300:])

        # The next evening, with YouTube's refusal of the laptop on its record
        # and its hold standing: the run still exits 0 -- Task Scheduler is not
        # told a refusal is a failure -- and its record carries the refusal and
        # the hold, the one key it writes.
        ref = laptop / "archive" / "youtube.refused.json"
        table = json.loads(ref.read_text(encoding="utf-8")) if ref.exists() else {}
        table["laptop"] = {"at": "2026-10-18T19:52:53Z", "count": 2, "until": 4102444800.0,
                           "until_iso": "2100-01-01T00:00:00Z",
                           "why": "ERROR: Unable to download video subtitles for 'en': HTTP Error "
                                  "429: Too Many Requests"}
        ref.parent.mkdir(parents=True, exist_ok=True)
        ref.write_text(json.dumps(table), encoding="utf-8")
        code, said = run(at="2026-10-18T23:30:00Z")
        key = f"{CL.INBOX_RUNS}20261018T233000Z.json"
        assert code == 0 and not asked and writes == [key], (code, asked, writes, said[-300:])
        rec = json.loads((bucket / key).read_text(encoding="utf-8"))
        assert (rec.get("refusal") or {}).get("count") == 2 \
            and rec["refusal"].get("until_iso") == "2100-01-01T00:00:00Z" \
            and "429" in rec["refusal"].get("why", ""), rec
        for bad in ({"at": "yesterday"}, {"at": "2026-10-18T23:30:00Z", "x": "y" * (1 << 17)}):
            try:
                CL.inbox_report(real_folder(bucket, create=False), bad)
                raise AssertionError(f"inbox_report sent a record it should refuse: {str(bad)[:60]}")
            except CL.Failed:
                pass
        assert CL.inbox_report(real_folder(bucket, create=False),
                               {"at": "2026-10-18T23:30:00Z", "sent": 99}) is None
        assert json.loads((bucket / key).read_text(encoding="utf-8")) == rec, \
            "inbox_report wrote over a run's record already there"

        b = real_folder(bucket, create=False)
        held = (bucket / "inbox/captions/PFDEFER01.json").read_bytes()
        assert CL.inbox_add(b, "PFDEFER01", laptop / "work/PFHERE01/captions.en.json3",
                            {}) is None, "inbox_add wrote over an entry already there"
        assert (bucket / "inbox/captions/PFDEFER01.json").read_bytes() == held
        snap = _inbox_files(bucket)
        for vid, name in (("../../state/livestreams", "captions.en.json3"),
                          ("PFX", "livestreams.json")):
            src = root / name
            src.write_text(words, encoding="utf-8")
            try:
                CL.inbox_add(b, vid, src, {})
                raise AssertionError(f"inbox_add took {vid}/{name}, outside the inbox's shape")
            except CL.Failed:
                pass
        assert _inbox_files(bucket) == snap, "a refused inbox_add still wrote something"
        return "ok", ("a dry run asks, sends and writes nothing; the run asks for the one waiting "
                      "recording it lacks and none already entered, sends it and two already "
                      "here, never a file without words of its own, writes only under "
                      "inbox/captions/ with true sizes and sha256s, and its record under "
                      "inbox/laptop/, and no state; again, nothing; a refused evening exits 0 and "
                      "its record carries the refusal and the hold; an entry already there and a "
                      "key outside the inbox are refused")
    finally:
        L.ask_track, CL.FolderBucket = real_ask, real_folder
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)


@check("livestreams", "the captions inbox, the night's side: only a waiting recording's captions "
       "are taken, a corrupt or mismatched entry is refused, and what is taken is read and "
       "judged as the night's own", needs=("livestreams",))
def _inbox_night(livestreams):
    """The night stays the one writer of the state, and the inbox is only
    ever a source of caption files. From an inbox laid out as inbox-down
    lays it, on a night whose own asks of YouTube are held by its refusal:

      - the waiting recording with a sound entry is captioned "by inbox",
        its file in work/ byte for byte;
      - an entry a byte longer than its manifest, one whose sha256 is not
        its manifest's, one with no words, one naming a file outside its
        folder, one whose manifest names another recording, and one whose
        size is Infinity, which int() overflows on, are each refused: the
        recording waits, the state names the entry (the sha256 of its
        manifest), and nothing of it reaches work/;
      - a recording already captioned, one failed out, and one the state
        never listed are not taken, and their state is as it was;
      - --markers reads the taken recording and the guard judges it, as it
        does a recording this step fetched;
      - a night that finds the reading lost takes the entry again, its try
        counted; a New term run takes nothing; and a night whose inbox did
        not come down says so on its last line;
      - the state keeps when an entry for a waiting recording last arrived,
        taken or refused ("inbox_arrived", 18 October 2026), and a night
        that took nothing leaves it as it was;
      - inbox_spent keeps an entry taken and not yet read, and spends a
        refused one, a read one and one for a recording the state dropped;
        and prune keeps the state's entry for such a recording, and lets a
        read one go.
    """
    import contextlib
    import hashlib
    import io
    L = livestreams
    root = Path(tempfile.mkdtemp(prefix="gr-inbox-night-"))
    here = os.getcwd()
    saved = {k: os.environ.get(k) for k in ("YOUTUBE_API_KEY", "GITHUB_ACTIONS", L.NEW_TERM_ENV)}
    real = (L.read_markers, L.summarize, L.guard)
    t0 = "2026-10-18T08:30:00Z"

    def night(*argv, at=t0):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = L.main(list(argv) + ["--origin", "runner", "--now", at])
        return code, out.getvalue()

    def since(inbox="inbox", at=t0):
        return night("--since-state", "--inbox", inbox, "--replay", "api",
                     "--captions-from", "nosrc", at=at)

    try:
        for k in saved:
            os.environ.pop(k, None)
        os.chdir(root)
        fin = {"status": "finished", "chamber": "house", "title": "x",
               "ended": "2026-10-16T18:00:00Z", "captions": "deferred"}
        refused = ["PFSIZE01", "PFSHA01", "PFWORD01", "PFPATH01", "PFNAME01", "PFINF01"]
        state = {"version": 1, "last_run": {"at": "2026-10-17T08:30:00Z"},
                 "channels": {c: {"uploads": "UU" + c} for c in ("house", "senate")},
                 "refusals": {"runner": {"at": "2026-10-17T08:40:00Z", "count": 1,
                                         "why": "Sign in to confirm you're not a bot",
                                         "until": 4102444800, "until_iso": "2100-01-01T00:00:00Z"}},
                 "videos": {vid: dict(fin) for vid in ["PFTAKE01"] + refused}}
        state["videos"]["PFREAD01"] = dict(fin, captions="captioned", by="runner", read="2026-10-16")
        state["videos"]["PFFAIL01"] = dict(fin, captions="failed", tries=L.MAX_TRIES)
        (root / "archive").mkdir()
        (root / "archive" / "livestreams.json").write_text(json.dumps(state), encoding="utf-8")
        api = root / "api"
        api.mkdir()
        idx = {}
        for c in ("house", "senate"):
            (api / f"pl-{c}.json").write_text('{"items": []}', encoding="utf-8")
            idx[L.canonical("playlistItems", {"part": "contentDetails,snippet",
                                              "playlistId": "UU" + c, "maxResults": 50})] = f"pl-{c}.json"
        (api / "index.json").write_text(json.dumps(idx), encoding="utf-8")
        (root / "nosrc").mkdir()
        inbox = root / "inbox"
        good = _inbox_words().encode("utf-8")
        manifests = {}

        def entry(vid, body, **over):
            (inbox / vid).mkdir(parents=True, exist_ok=True)
            (inbox / vid / "captions.en.json3").write_bytes(body)
            doc = {"video": vid, "file": "captions.en.json3", "size": len(body),
                   "sha256": hashlib.sha256(body).hexdigest(), "fetched": "2026-10-17T23:30:00Z",
                   "key": f"inbox/captions/{vid}/x/captions.en.json3"}
            doc.update(over)
            raw = json.dumps(doc).encode("utf-8")
            (inbox / f"{vid}.json").write_bytes(raw)
            manifests[vid] = hashlib.sha256(raw).hexdigest()

        entry("PFTAKE01", good)
        entry("PFSIZE01", good, size=len(good) + 1)
        entry("PFSHA01", good.replace(b"1491", b"1492"), sha256=hashlib.sha256(good).hexdigest())
        entry("PFWORD01", b'{"wireMagic": "pb3", "events": []}')
        entry("PFPATH01", good, file="../../archive/livestreams.json")
        entry("PFNAME01", good, video="PFTAKE01")
        # "size": Infinity, which JSON reads and int() overflows on: refused, not a crash.
        entry("PFINF01", good, size=float("inf"))
        assert b"Infinity" in (inbox / "PFINF01.json").read_bytes()
        for vid in ("PFREAD01", "PFFAIL01", "PFNONE01"):
            entry(vid, good)

        code, said = since()
        st = json.loads((root / "archive" / "livestreams.json").read_text(encoding="utf-8"))
        v = st["videos"]["PFTAKE01"]
        assert code == 0 and v.get("captions") == "captioned" and v.get("by") == "inbox" \
            and v.get("inbox") == manifests["PFTAKE01"], (code, v, said[-500:])
        assert (root / "work" / "PFTAKE01" / "captions.en.json3").read_bytes() == good
        for vid in refused:
            v = st["videos"][vid]
            assert v.get("captions") in L.WAITING and \
                (v.get("inbox_refused") or {}).get("entry") == manifests[vid], (vid, v)
            assert not (root / "work" / vid).exists(), f"{vid}'s refused captions reached work/"
        assert st["videos"]["PFREAD01"] == state["videos"]["PFREAD01"], st["videos"]["PFREAD01"]
        assert st["videos"]["PFFAIL01"].get("captions") != "captioned" \
            and "PFNONE01" not in st["videos"], st["videos"]
        assert not any((root / "work" / vid).exists() for vid in ("PFREAD01", "PFFAIL01", "PFNONE01"))
        caps = st["last_run"]["captions"]
        assert caps.get("captioned") == 1 and caps.get("from the inbox") == 1 \
            and caps.get("refused from the inbox") == len(refused), caps
        assert "from the captions inbox:" in said.strip().splitlines()[-1], said[-300:]
        # When something last arrived, for the night's verdict
        # (nightly.inbox_silent): an entry taken or refused is the laptop's.
        assert st.get("inbox_arrived") == {"at": t0, "taken": 1, "refused": len(refused)}, \
            st.get("inbox_arrived")

        assert L.inbox_spent(st["videos"]["PFTAKE01"], manifests["PFTAKE01"]) == ""
        assert L.inbox_spent(st["videos"]["PFSIZE01"], manifests["PFSIZE01"])
        assert L.inbox_spent(st["videos"]["PFSIZE01"], "another entry") == ""
        assert L.inbox_spent(st["videos"]["PFREAD01"], manifests["PFREAD01"])
        assert L.inbox_spent(None, manifests["PFNONE01"])
        assert L.inbox_spent(dict(st["videos"]["PFTAKE01"], read="2026-10-18"), None)

        # prune keeps a recording taken from the inbox and not yet read, as it
        # keeps one the night captioned itself: its entry is still wanted.
        old = {"status": "finished", "captions": "captioned", "seen": "2026-07-01T00:00:00Z"}
        pst = {"videos": {"PFOLD01": dict(old, by="inbox"),
                          "PFOLD02": dict(old, by="inbox", read="2026-07-02"),
                          "PFOLD03": dict(old, by="found")}}
        L.prune(pst, L.utcnow(t0))
        assert sorted(pst["videos"]) == ["PFOLD01"], \
            f"prune kept {sorted(pst['videos'])}, where only the unread inbox capture stays"

        seen = {}

        def read(vids):
            seen["read"] = list(vids)
            return 0

        def judged(copies, tonight):
            seen["judged"] = sorted(tonight)
            return "", None
        L.read_markers, L.summarize, L.guard = read, (lambda vids, work=L.WORK: 0), judged
        code, said = night("--markers")
        assert code == 0 and "PFTAKE01" in seen.get("read", []) \
            and "PFTAKE01" in seen.get("judged", []), (seen, said[-300:])
        L.read_markers, L.summarize, L.guard = real

        (root / "candidate_segments.json").write_text("{}", encoding="utf-8")
        shutil.rmtree(root / "work" / "PFTAKE01")
        code, said = since(at="2026-10-19T08:30:00Z")
        v = json.loads((root / "archive" / "livestreams.json").read_text(
            encoding="utf-8"))["videos"]["PFTAKE01"]
        assert code == 0 and v.get("captions") == "captioned" and v.get("by") == "inbox" \
            and v.get("tries") == 1 and (root / "work" / "PFTAKE01").is_dir(), (v, said[-400:])

        st = json.loads((root / "archive" / "livestreams.json").read_text(encoding="utf-8"))
        st["videos"]["PFTAKE01"] = dict(fin)
        (root / "archive" / "livestreams.json").write_text(json.dumps(st), encoding="utf-8")
        shutil.rmtree(root / "work" / "PFTAKE01")
        os.environ[L.NEW_TERM_ENV] = "true"
        code, said = since(at="2026-10-20T08:30:00Z")
        os.environ.pop(L.NEW_TERM_ENV, None)
        v = json.loads((root / "archive" / "livestreams.json").read_text(
            encoding="utf-8"))["videos"]["PFTAKE01"]
        assert v.get("captions") != "captioned" and not (root / "work" / "PFTAKE01").exists(), \
            f"a New term run took from the inbox: {v}"
        code, said = since(inbox="not-here", at="2026-10-21T08:30:00Z")
        assert code == 0 and "the captions inbox did not come down" in \
            said.strip().splitlines()[-1], said[-300:]
        # The night of 19 October took the lost reading's entry again; the two
        # after it took nothing, and leave when something last arrived as it was.
        arrived = json.loads((root / "archive" / "livestreams.json").read_text(
            encoding="utf-8")).get("inbox_arrived") or {}
        assert arrived.get("at") == "2026-10-19T08:30:00Z", arrived
        return "ok", (f"one waiting recording taken and read under the guard, {len(refused)} "
                      "unsound entries refused and named, three not waiting left alone; a lost "
                      "reading taken again, a New term run taking nothing, a missing inbox said; "
                      "when an entry last arrived kept in the state")
    finally:
        L.read_markers, L.summarize, L.guard = real
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)


# WHAT THE LAPTOP CLOSED (29 October 2026; livestreams.py). The laptop had
# closed kS2PBKXOkzA, the House Special Committee on COVID Response Efficacy
# of 8 October 2026, as having no captions published, and sent nothing; the
# night, refused by YouTube, kept it waiting and warned of it every night.
# The laptop's run record now names what it closed, and the night records
# each as it records its own closure. These checks hold that on made-up
# states, asking nothing of YouTube or R2.

def _closed_night(L, root, videos, at, record=None, entries=()):
    """--since-state --inbox in `root`, the working folder, at `at`: the
    state holding `videos` where given (else as the last night left it), the
    night's own asks held by YouTube's refusal of GitHub's machine, the
    laptop's newest run record as inbox-down brings it (`record`, None for
    none), and a sound inbox entry for each of `entries`. (exit status, what
    it printed, the state after)."""
    import contextlib
    import hashlib
    import io
    if videos is not None:
        (root / "archive").mkdir(exist_ok=True)
        (root / "archive" / "livestreams.json").write_text(json.dumps({
            "version": 1, "last_run": {"at": "2026-10-17T08:30:00Z"},
            "channels": {c: {"uploads": "UU" + c} for c in ("house", "senate")},
            "refusals": {"runner": {"at": "2026-10-12T08:40:00Z", "count": 5,
                                    "why": "Sign in to confirm you're not a bot",
                                    "until": 4102444800, "until_iso": "2100-01-01T00:00:00Z"}},
            "videos": videos}), encoding="utf-8")
        api = root / "api"
        api.mkdir(exist_ok=True)
        idx = {}
        for c in ("house", "senate"):
            (api / f"pl-{c}.json").write_text('{"items": []}', encoding="utf-8")
            idx[L.canonical("playlistItems", {"part": "contentDetails,snippet",
                                              "playlistId": "UU" + c,
                                              "maxResults": 50})] = f"pl-{c}.json"
        (api / "index.json").write_text(json.dumps(idx), encoding="utf-8")
        (root / "nosrc").mkdir(exist_ok=True)
    # What inbox-down leaves: tonight's entries, and the laptop's newest record.
    inbox = root / "inbox"
    shutil.rmtree(inbox, ignore_errors=True)
    inbox.mkdir()
    body = _inbox_words().encode("utf-8")
    for vid in entries:
        (inbox / vid).mkdir()
        (inbox / vid / "captions.en.json3").write_bytes(body)
        (inbox / f"{vid}.json").write_text(json.dumps(
            {"video": vid, "file": "captions.en.json3", "size": len(body),
             "sha256": hashlib.sha256(body).hexdigest(), "fetched": at,
             "key": f"inbox/captions/{vid}/x/captions.en.json3"}), encoding="utf-8")
    run_rec = root / L.LAPTOP_RUN
    run_rec.unlink(missing_ok=True)
    if record is not None:
        run_rec.write_text(json.dumps(record), encoding="utf-8")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = L.main(["--since-state", "--inbox", "inbox", "--replay", "api",
                       "--captions-from", "nosrc", "--origin", "runner", "--now", at])
    st = json.loads((root / "archive" / "livestreams.json").read_text(encoding="utf-8"))
    return code, out.getvalue(), st


def _closed_fixture(check):
    """Runs check(L, NI, root, now, ended) in a working folder of its own,
    with the environment a night's step reads emptied and put back after:
    `now` the time to act as of, the real one so that the night's warnings,
    which read the clock, see what the step saw; `ended` five days before
    it, when the fixture's recordings finished."""
    from datetime import datetime, timedelta, timezone
    import livestreams as L
    import nightly as NI
    root = Path(tempfile.mkdtemp(prefix="gr-laptop-closed-"))
    here = os.getcwd()
    saved = {k: os.environ.get(k) for k in ("YOUTUBE_API_KEY", "GITHUB_ACTIONS", L.NEW_TERM_ENV)}
    now = datetime.now(timezone.utc).replace(microsecond=0)
    try:
        for k in saved:
            os.environ.pop(k, None)
        os.chdir(root)
        return check(L, NI, root, now, (now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)


def _iso_z(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


@check("livestreams", "a recording the laptop closed with no captions published is recorded by "
       "the night as none published, its approximate start kept, and warns no more",
       needs=("livestreams", "nightly"))
def _laptop_closed_recorded(livestreams, nightly):
    """kS2PBKXOkzA's case. A recording finished five days ago that the night
    lists as deferred, and the laptop's newest run record names as closed
    with no captions published: after the night's step its state says
    "none-published", by the laptop, the schedule's approximate start kept;
    it is no longer counted late (nightly._captions_late), so neither the
    waiting warning nor the silent inbox's names it, and the laptop no
    longer asks for it (inbox_wants); the step's verdict counts it. And the
    record must be where cloud.py inbox-down puts it."""
    import types
    import cloud as CL

    def check(L, NI, root, now, ended):
        assert L.LAPTOP_RUN.as_posix() == CL.INBOX_RUN_LOCAL, (L.LAPTOP_RUN, CL.INBOX_RUN_LOCAL)
        fin = {"status": "finished", "chamber": "house", "title": "x", "ended": ended,
               "captions": "deferred"}
        rec = {"at": _iso_z(now), "by": "laptop", "code": 0, "sent": 0,
               "none_published": ["PFCLOSE1"]}
        code, said, st = _closed_night(L, root, {"PFCLOSE1": dict(fin)}, _iso_z(now), rec)
        v = st["videos"]["PFCLOSE1"]
        assert code == 0 and v.get("captions") == "none-published" and v.get("by") == "laptop" \
            and "approximate start is kept" in str(v.get("why")), (code, v, said[-400:])
        assert not L.inbox_wants(v), "the laptop would still ask for a recording it closed"
        assert not NI._captions_late(st, now), "a recording the laptop closed is counted late"
        assert not NI.inbox_silent(dict(st, inbox_arrived={"at": "2026-10-01T00:00:00Z"}),
                                   rec, now), "the silent inbox still warns of it"
        assert NI.KIND_CAPTIONS_WAIT not in dict(NI.Night.warned(types.SimpleNamespace(
            v={"started": _iso_z(now)}))), "the waiting warning still names it"
        assert st["last_run"]["captions"].get("none published, by the laptop") == 1 \
            and "closed by the laptop" in said.strip().splitlines()[-1], (st["last_run"], said[-300:])
        return "ok", ("the laptop's closure recorded as none published, its approximate start "
                      "kept, counted in the verdict, and warned of no more")
    return _closed_fixture(check)


@check("livestreams", "a late recording the laptop did not close still warns: the night never "
       "closes one on its own say-so", needs=("livestreams", "nightly"))
def _laptop_closed_only_its_word(livestreams, nightly):
    """Beside one the laptop closed: a recording as late that the laptop's
    record does not name, and the same night with no record of the laptop's
    at all. Each stays waiting and is counted late, the waiting warning
    and the silent inbox's still count it, and the laptop still asks for
    it."""
    import types

    def check(L, NI, root, now, ended):
        fin = {"status": "finished", "chamber": "house", "title": "x", "ended": ended,
               "captions": "deferred"}
        rec = {"at": _iso_z(now), "by": "laptop", "none_published": ["PFCLOSE1"]}
        for record in (rec, None):
            code, said, st = _closed_night(
                L, root, {"PFCLOSE1": dict(fin), "PFLATE01": dict(fin)}, _iso_z(now), record)
            v = st["videos"]["PFLATE01"]
            assert code == 0 and v.get("captions") == "deferred" and L.inbox_wants(v), \
                (record, v, said[-300:])
            late = {id(x) for x in NI._captions_late(st, now)}
            assert id(v) in late, (record, v)
            silent = NI.inbox_silent(dict(st, inbox_arrived={"at": "2026-10-01T00:00:00Z"}),
                                     record, now)
            n = 1 if record else 2
            assert silent and f"{n} recording{'s' if n != 1 else ''} finished more than" \
                in silent[0][1], (record, silent)
            w = dict(NI.Night.warned(types.SimpleNamespace(v={"started": _iso_z(now)})))
            assert w.get(NI.KIND_CAPTIONS_WAIT, "").startswith(f"{n} recording"), (record, w)
        return "ok", ("a late recording the laptop's record does not name, and every late one "
                      "on a night with no record, waits and warns as before")
    return _closed_fixture(check)


@check("livestreams", "captions that arrive for a recording the laptop closed are taken from the "
       "inbox and read as any other", needs=("livestreams", "nightly"))
def _laptop_closed_then_captioned(livestreams, nightly):
    """A recording the laptop's record names as closed whose captions come
    down in the inbox the same night is taken, not closed; and one the night
    recorded closed on the laptop's word whose captions arrive on a later
    night is taken then -- captioned "by inbox", its file in work/ -- and
    --markers reads it under the guard as it reads every recording taken
    from the inbox."""
    import contextlib
    import io
    from datetime import timedelta

    def check(L, NI, root, now, ended):
        fin = {"status": "finished", "chamber": "house", "title": "x", "ended": ended,
               "captions": "deferred"}
        rec = {"at": _iso_z(now), "by": "laptop", "none_published": ["PFCLOSE1", "PFBOTH01"]}
        code, said, st = _closed_night(L, root, {"PFCLOSE1": dict(fin), "PFBOTH01": dict(fin)},
                                       _iso_z(now), rec, entries=["PFBOTH01"])
        both, closed = st["videos"]["PFBOTH01"], st["videos"]["PFCLOSE1"]
        assert code == 0 and both.get("captions") == "captioned" and both.get("by") == "inbox" \
            and closed.get("captions") == "none-published", (both, closed, said[-300:])
        later = _iso_z(now + timedelta(hours=1))
        code, said, st = _closed_night(L, root, None, later, rec, entries=["PFCLOSE1"])
        v = st["videos"]["PFCLOSE1"]
        assert code == 0 and v.get("captions") == "captioned" and v.get("by") == "inbox" \
            and (root / "work" / "PFCLOSE1" / "captions.en.json3").is_file(), (v, said[-400:])
        seen, real = {}, (L.read_markers, L.summarize, L.guard)

        def read(vids):
            seen["read"] = list(vids)
            return 0

        def judged(copies, tonight):
            seen["judged"] = sorted(tonight)
            return "", None
        L.read_markers, L.summarize, L.guard = read, (lambda vids, work=L.WORK: 0), judged
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                code = L.main(["--markers", "--origin", "runner", "--now", later])
        finally:
            L.read_markers, L.summarize, L.guard = real
        assert code == 0 and "PFCLOSE1" in seen.get("read", []) \
            and "PFCLOSE1" in seen.get("judged", []), seen
        return "ok", ("captions in the inbox the night the laptop closes a recording win, and "
                      "those that arrive after it are taken and read under the guard")
    return _closed_fixture(check)


@check("livestreams", "the laptop's closure settles only what waits: a recording the night closed "
       "itself, one adopted, one left for a person and one captioned are as they were",
       needs=("livestreams", "nightly"))
def _laptop_closed_leaves_the_rest(livestreams, nightly):
    """No command or document gives a person a way to accept an
    approximate start (29 October 2026): what settles a recording without a
    reading is the night's own closure ("none-published", taken at a
    recording's last ask in a run that captioned something), the old
    "adopted", and "for-laptop", which is left for a person and still
    warns. The laptop's record naming each of them, and one already
    captioned, changes none of them; a recording the night closed itself is
    still not taken from the inbox; and a record naming a recording the
    state does not hold, or a name of no recording's shape, is passed over."""
    import types

    def check(L, NI, root, now, ended):
        fin = {"status": "finished", "chamber": "house", "title": "x", "ended": ended}
        videos = {"PFSELF01": dict(fin, captions="none-published", why="taken to have none"),
                  "PFADOPT1": dict(fin, captions="captioned", by="laptop", adopted="2026-10-01"),
                  "PFLEFT01": dict(fin, captions="for-laptop", tries=L.MAX_TRIES),
                  "PFREAD01": dict(fin, captions="captioned", by="runner", read="2026-10-20")}
        rec = {"at": _iso_z(now), "by": "laptop",
               "none_published": sorted(videos) + ["PFNONE01", "../../x", 7, None]}
        code, said, st = _closed_night(L, root, json.loads(json.dumps(videos)), _iso_z(now), rec,
                                       entries=["PFSELF01"])
        moved = {k: st["videos"].get(k) for k in videos if st["videos"].get(k) != videos[k]}
        assert code == 0 and not moved and "PFNONE01" not in st["videos"], (moved, said[-300:])
        assert "none published, by the laptop" not in st["last_run"]["captions"], st["last_run"]
        assert not (root / "work" / "PFSELF01").exists(), \
            "captions were taken for a recording the night closed itself"
        w = dict(NI.Night.warned(types.SimpleNamespace(v={"started": _iso_z(now)})))
        assert w.get(NI.KIND_CAPTIONS_WAIT, "").startswith("1 recording"), \
            f"the one left for a person no longer warns: {w}"
        return "ok", ("the night's own closure, an adopted reading, one left for a person and one "
                      "read are untouched by the laptop's record, and a name the state does not "
                      "hold is passed over")
    return _closed_fixture(check)


@check("livestreams", "a laptop run's record names each waiting recording it closed with no "
       "captions published, and none given up on, captioned or no longer listed",
       needs=("livestreams", "cloud"))
def _laptop_closed_in_its_record(livestreams, cloud):
    """--to-inbox, from a bucket folder whose state lists four recordings
    as waiting and two not, and the laptop's own record of what it asked
    (archive/youtube.refused.json): closed with no captions published, given
    up on, one it never asked for, and three closed none-published that the
    night has captioned, left for a person or dropped. Its run's record
    names the one waiting recording it closed with none published, and no
    other; with a refusal standing, nothing is asked."""
    import contextlib
    import io
    L, CL = livestreams, cloud
    root = Path(tempfile.mkdtemp(prefix="gr-laptop-closed-rec-"))
    here = os.getcwd()
    saved = {k: os.environ.get(k) for k in ("GITHUB_ACTIONS", CL.NO_BUCKET)}
    now = "2026-10-28T23:30:00Z"
    try:
        os.environ.pop("GITHUB_ACTIONS", None)
        os.environ[CL.NO_BUCKET] = "1"
        fin = {"status": "finished", "chamber": "house", "title": "x",
               "ended": "2026-10-08T18:00:00Z"}
        state = {"version": 1, "channels": {}, "last_run": {}, "refusals": {}, "videos": {
            "kS2PBKXOkzA": dict(fin, captions="deferred"),
            "PFGIVE01": dict(fin, captions="deferred"),
            "PFWAIT01": dict(fin, captions="deferred"),
            "PFYET001": dict(fin, captions="none-yet"),
            "PFREAD01": dict(fin, captions="captioned", by="runner", read="2026-10-20"),
            "PFLEFT01": dict(fin, captions="failed", tries=L.MAX_TRIES)}}
        bucket, laptop = root / "bucket", root / "laptop"
        (bucket / "state").mkdir(parents=True)
        (bucket / "state" / "livestreams.json").write_text(json.dumps(state), encoding="utf-8")
        (laptop / "archive").mkdir(parents=True)
        (laptop / "src").mkdir()
        closed = {"asks": 3, "tried": "2026-10-20T23:40:00Z", "closed": "none-published"}
        (laptop / "archive" / "youtube.refused.json").write_text(json.dumps({
            "laptop": {"at": "2026-10-28T19:00:00Z", "count": 1, "until": 4102444800.0,
                       "until_iso": "2100-01-01T00:00:00Z", "why": "HTTP Error 429"},
            "asked": {"kS2PBKXOkzA": dict(closed),
                      "PFGIVE01": {"asks": 5, "tried": "2026-10-20T23:40:00Z",
                                   "closed": "given-up"},
                      "PFYET001": {"asks": 1, "tried": "2026-10-27T23:40:00Z",
                                   "again": "2026-10-29T21:40:00Z"},
                      "PFREAD01": dict(closed), "PFLEFT01": dict(closed),
                      "PFGONE01": dict(closed)}}), encoding="utf-8")
        os.chdir(laptop)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = L.main(["--to-inbox", "--local-bucket", str(bucket), "--captions-from",
                           "src", "--origin", "laptop", "--now", now])
        runs = CL.inbox_runs(CL.FolderBucket(bucket, create=False))
        assert code == 0 and len(runs) == 1, (code, runs, out.getvalue()[-400:])
        rec = json.loads((bucket / runs[0]).read_text(encoding="utf-8"))
        assert rec.get("none_published") == ["kS2PBKXOkzA"], rec
        assert set(rec.get("asked") or {}) <= {"deferred"}, \
            f"a run with a refusal standing asked: {rec}"
        return "ok", ("the record names the one waiting recording closed with none published, "
                      "not the one given up on, the one not closed, or those the night captioned, "
                      "left for a person or dropped")
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)


@check("markers", "every phrasing read from a transcript still matches")
def _marker_cases():
    """tests/test_markers.py holds the 34 phrasings that were read out of real
    recordings, plus the decoys that look like openings and are not. OPEN_RE
    went through nine revisions in a day collecting them, each checked against
    a fixture that was then thrown away. Running them here is what makes the
    tenth revision safe."""
    import subprocess, sys
    f = _paths.locate("tests/test_markers.py")
    if not f.exists():
        return "skip", "tests/test_markers.py not here"
    r = _run([sys.executable, str(f)], capture_output=True, text=True)
    assert r.returncode == 0, (r.stdout or r.stderr).strip()[-300:]
    return "ok", r.stdout.strip().splitlines()[-1][:70]


@check("build", "a hearing is filed under its committee's name at the time, and one sitting once",
       needs=("build_proceedings", "committee_names"))
def _proceedings_official_names(build_proceedings, committee_names):
    """The clerk of 1999-2006 wrote "Exec Depts and Admin" on the hearing
    lines, and the committee pages match a name exactly: House Executive
    Departments and Administration, Criminal Justice and Public Safety and
    Election Law showed no sitting at all for 1999-2004 beside more than a
    hundred bills a term. build_proceedings now writes every committee row's
    name through committee_names.official, BEFORE the fold that keys on it,
    so a sitting the docket wrote twice under two spellings -- 1991's HB 497,
    "EDUCATION VV" and "Education" -- is one event. A row with a recording
    keeps its name when that name is already the committee's, which every
    row with a recording's is; the floor names no committee and stays so."""
    BP = build_proceedings

    def row(term, bill, body, kind, date, committee, video=""):
        return {"term": term, "bill": bill, "body": body, "kind": kind,
                "date": date, "time": "", "committee": committee,
                "video_id": video, "source": "docket"}
    rows = [
        row("2001-2002", "HB101", "H", "public hearing", "2001-02-06",
            "Exec Depts and Admin for Interim Study VV"),
        row("2003-2004", "HB102", "H", "executive session", "2003-03-04",
            "Crim Just and PSfty"),
        row("1989-1990", "SB103", "S", "hearing", "1989-02-14", "Dev, Rec, and Envir"),
        row("1991-1992", "HB497", "H", "executive session", "1991-10-22", "EDUCATION VV"),
        row("1991-1992", "HB497", "H", "executive session", "1991-10-22", "Education"),
        row("2025-2026", "HB104", "H", "public hearing", "2026-01-13",
            "Executive Departments and Administration", video="VIDEO1"),
        row("2025-2026", "HB104", "H", "floor debate", "2026-03-05", "", video="FLOOR1"),
    ]
    n = BP.official_names(rows)
    got = [r["committee"] for r in rows]
    assert got == ["Executive Departments and Administration",
                   "Criminal Justice and Public Safety",
                   "Development, Recreation and Environment",
                   "Education", "Education",
                   "Executive Departments and Administration", ""], got
    assert n == 4, n
    kept = BP.fold_to_events(rows)
    assert len(kept) == 6, [(r["bill"], r["committee"]) for r in kept]
    src = _source(BP.__file__)
    main_ = src[src.index("def main("):]
    assert main_.index("official_names(rows)") < main_.index("fold_to_events(rows)"), (
        "build_proceedings renames after the fold, so two spellings of one "
        "sitting stay two events")
    return "ok", "four clerk's spellings written as their committees; one sitting under two spellings folded"


@check("build", "proceedings.csv builds from the fixture and both sources land in it")
def _proceedings_table():
    """One table, both sources. This exists because five tools in one day
    were found to read the manifest and not the floor index, and a check that
    builds the table from a fixture holding one of each is the cheapest way to
    notice the next tool that reads only one of them."""
    import shutil, subprocess, sys, tempfile
    root = Path(tempfile.mkdtemp(prefix="gr-proc-"))
    try:
        for f in PROCEEDINGS_MODULES:
            (root / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(_paths.locate(f), root / f)
        cols = ["bill","body","committee","proceeding","sched_date","sched_time",
                "venue","tier","bills_in_slot","match","video_id","video_title",
                "stream_start","predicted_offset","watch_url","candidates",
                "observed_start","observed_end","notes"]
        import csv
        with (root / "verification_manifest.csv").open("w", newline="",
                                                        encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(cols)
            w.writerow(["HB1442","H","Judiciary","public hearing","2026-02-03",
                        "10:00","LOB","A",1,"single video","CMTEV","t",
                        "2026-02-03 09:00:00","1:00:00","u","","","",""])
        (root / "floor_index.json").write_text(json.dumps({"HB1442": [
            {"date":"2026-03-05","body":"H","video_id":"FLOORV",
             "motions":["OTPA"],"tallies":["197-151"],"kind":"floor debate",
             "debate_end":21197.0,"window_start":18954.0,"precise":True}]}),
            encoding="utf-8")
        r = _run([sys.executable, "build_proceedings.py"], cwd=root,
                           capture_output=True, text=True)
        assert r.returncode == 0, (r.stderr or r.stdout)[-300:]
        sys.path.insert(0, str(root))
        import importlib
        P = importlib.import_module("proceedings")
        importlib.reload(P)
        rows = P.load(root / "proceedings.csv")
        assert len(rows) == 2, f"{len(rows)} rows, wanted 2"
        kinds = {r["kind"] for r in rows}
        assert kinds == {"public hearing", "floor debate"}, kinds
        fl = next(r for r in rows if r["kind"] == "floor debate")
        assert fl["debate_end"] == 21197.0 and fl["precise"], fl
        assert P.floor_videos(rows) == {"FLOORV"}
        assert rows[0]["term"] == "2025-2026", rows[0]["term"]
        return "ok", "2 rows, one of each kind, roll-call end carried"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("session", "a roll call of Organization Day is the next term's, whatever year it is filed "
                  "under, and a vote on no bill draws its sitting",
       needs=("proceedings", "build_data", "session_days", "build_session_pages"))
def _organization_day_votes(P, BD, SD, BSP):
    """The person's note of 6 October 2026: Organization Day -- the first
    Wednesday of December of an even year, 2 December 2026 next -- is the
    next General Court's, its votes the Speaker's election and the House's
    rules, on no bill. The docket files the day's resolutions under the next
    session (HR 1 of 2025, "Introduced and Adopted VV 12/04/2024"), and a roll
    call is keyed by its session year everywhere a term is asked of it; one
    filed under 2026 would have gone with 2025-2026, been set aside as a stray
    row of the frozen term (build_data.rows_all) and counted in left_out.json,
    its ballots tallied with that term's members and linked to its bills. No
    roll call file holds one yet (0 of 9,565), so this holds the rule on a
    fixture: proceedings.vote_term, rollcall_parser's terms, the frozen term's
    files, and a sitting page drawn for a vote on no bill.

    AND careers.json (7 October 2026): build_careers credited a ballot to
    its session year, so a member whose first vote was the Speaker's election
    of 2 December 2026, filed under 2026, would have served in 2025-2026. It
    reads the roll call's VoteDate now, and stops on a (year, chamber, number)
    that names votes of two terms -- December's numbered from 1 again under
    2026 -- whose ballots could not say which vote they are."""
    import datetime as _dt
    import html as _html
    bad = []
    # The days, against the docket's own rows of Organization Day: 12/04/2024
    # (HR 1 of 2025), 12/07/2022 (SR 1 of 2023), 12/02/2020 (HR 1 of 2021),
    # 12/01/2004 (HB 31 of 2005), 12/02/1998 (SCR 1 of 1999).
    for y, d in ((2026, "2026-12-02"), (2024, "2024-12-04"), (2022, "2022-12-07"),
                 (2020, "2020-12-02"), (2004, "2004-12-01"), (1998, "1998-12-02")):
        if str(P.organization_day(y)) != d:
            bad.append(f"Organization Day of {y} is {P.organization_day(y)}, not {d}")
    if P.organization_day(2025) is not None:
        bad.append("an odd year has an Organization Day")
    for year, when, want in (("2026", "2026-12-02", "2027-2028"),
                             ("2026", "12/2/2026 10:31:07 AM", "2027-2028"),
                             ("2027", "2026-12-02", "2027-2028"),
                             ("2026", "2026-12-01", "2025-2026"),
                             ("2026", "2026-08-19", "2025-2026"),
                             ("2025", "2025-12-03", "2025-2026"),
                             ("2026", "", "2025-2026")):
        if P.vote_term(year, when) != want:
            bad.append(f"a roll call of {year} taken {when or 'on no day'} is "
                       f"{P.vote_term(year, when)!r}, not {want}")
    tmp = Path(tempfile.mkdtemp(prefix="gr-orgday-"))
    try:
        # The session's files after the turn, holding one roll call of the
        # day under 2026 and one under 2027; 2026 is frozen beside them.
        org26 = "2026|H|400|12/2/2026 10:31:07 AM||210|180|0|10|||Election of Speaker|||"
        org27 = "2027|S|1|12/2/2026 10:05:00 AM|SR1|24|0|0|0|||Adopt|relative to the rules|"
        jan27 = "2027|H|1|1/6/2027 10:00:00 AM|HB1|200|150|0|50|||OTP|relative to something|"
        (tmp / "RollCallSummary.txt").write_text("\n".join([org26, org27, jan27]) + "\n",
                                                 encoding="utf-8")
        (tmp / "RollCallHistory.txt").write_text(
            "2026|H|400|123456|10001|x|1|\n2027|H|1|123456|10001|x|1|\n", encoding="utf-8")
        (tmp / "records" / "rollcalls").mkdir(parents=True)
        (tmp / "records" / "rollcalls" / "RollCallSummary_2026.txt").write_text(
            "2026|H|300|8/19/2026 2:58:41 PM|SB434|165|140|0|95|||Override|relative to school materials|\n",
            encoding="utf-8")
        (tmp / "records" / "rollcalls" / "RollCallHistory_2026.txt").write_text(
            "2026|H|300|123456|10001|x|1|\n", encoding="utf-8")
        left = Counter()
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            summary = BD.rows_all(tmp, "RollCallSummary", archive=tmp,
                                  finished={"2025", "2026"}, left=left)
            ballots = BD.rows_all(tmp, "RollCallHistory", 8, archive=tmp,
                                  finished={"2025", "2026"}, left=left)
        keys = {tuple(r[:3]) for r in summary}
        if ("2026", "H", "400") not in keys or ("2026", "H", "300") not in keys:
            bad.append(f"the frozen term's files and Organization Day's roll call are read as {sorted(keys)}")
        if ("2026", "H", "400") not in {tuple(r[:3]) for r in ballots}:
            bad.append("Organization Day's ballots are set aside as the frozen term's")
        if left:
            bad.append(f"Organization Day's roll call is counted as a row left out: {dict(left)}")
        # rollcall_parser keys each roll call by its term, as rollcalls.json is.
        r = _run([sys.executable, _paths.script("rollcall_parser.py"), "--file",
                  "RollCallSummary.txt", "--dir", "records/rollcalls", "--all", "--out", "rollcalls.json"],
                 cwd=str(tmp), capture_output=True)
        got = json.loads((tmp / "rollcalls.json").read_text(encoding="utf-8")) \
            if (tmp / "rollcalls.json").exists() else {}
        where = {(x["year"], x["body"], x["number"]): t
                 for t, byb in got.items() for rows in byb.values() for x in rows}
        want = {("2026", "H", 400): "2027-2028", ("2027", "S", 1): "2027-2028",
                ("2027", "H", 1): "2027-2028", ("2026", "H", 300): "2025-2026"}
        if where != want:
            bad.append(f"rollcalls.json files the roll calls under {where}"
                       + ("" if got else f" ({(r.stderr or r.stdout)[-300:]})"))
        if "_procedural" not in (got.get("2027-2028") or {}):
            bad.append("the Speaker's election is not with the next term's votes on no bill")
        # Nor is it a row of the frozen term's record, which a New term run
        # holds the installed files to (freeze_term.ready): the day's roll
        # call filed under 2026 would have stopped every run from 2 December.
        import freeze_term as FT
        summ = (tmp / "RollCallSummary.txt").read_bytes()
        org = FT.organization_keys(summ)
        if org != {("2026", "H", "400")}:
            bad.append(f"freeze_term reads Organization Day's roll calls as {org}")
        for name in FT.ROLLCALL_FILES:
            rows = FT.rows_of((tmp / name).read_bytes(), name, "2025-2026", org)
            if any(r.startswith("2026|H|400|") for r in rows):
                bad.append(f"Organization Day's roll call is in 2025-2026's record of {name}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # careers.json, from the database's roll calls: the day's ballot is the
    # next term's service, and a key that names two terms' votes stops it.
    careers_cols = {
        "Legislators": ["Employeeno", "FirstName", "LastName", "party", "LegislativeBody",
                        "countycode", "PersonID"],
        "RollCallHistory": ["EmployeeNumber", "SessionYear", "LegislativeBody",
                            "VoteSequenceNumber", "CondensedBillNo", "Vote", "UserName",
                            "DateModified", "CalendarItemID"],
        "RollCallSummary": ["SessionYear", "LegislativeBody", "VoteSequenceNumber", "VoteDate",
                            "CondensedBillNo", "Yeas", "Nays", "Present", "Absent",
                            "AbbreviatedTitle1", "AbbreviatedTitle2", "Question_Motion", "Title1",
                            "Title2", "UserName", "DateModified", "Verified", "CalendarItemID"]}
    summary_rows = ["2026|H|300|08/19/2026 14:58:41|SB434|165|140|0|95|||Override|||x|x|True|",
                    "2026|H|400|12/02/2026 10:31:07||210|180|0|10|||Election of Speaker|||x|x|True|"]
    for clashing in (False, True):
        tmp = Path(tempfile.mkdtemp(prefix="gr-orgday-careers-"))
        try:
            (tmp / "db").mkdir()
            (tmp / "db" / "_columns.json").write_text(json.dumps(careers_cols), encoding="utf-8")
            (tmp / "db" / "Legislators.psv").write_text(
                "111111|Pat|Old|R|H|06|1\n222222|Sam|New|D|H|06|2\n", encoding="utf-8")
            (tmp / "db" / "RollCallSummary.psv").write_text("\n".join(summary_rows + (
                ["2026|H|1|01/07/2026 10:15:33||321|2|34|38|||Call of the Roll|||x|x|True|",
                 "2026|H|1|12/02/2026 10:05:00||390|0|0|10|||Call of the Roll|||x|x|True|"]
                if clashing else [])) + "\n", encoding="utf-8")
            (tmp / "db" / "RollCallHistory.psv").write_text(
                "111111|2026|H|300|SB434|1|x|x|\n111111|2026|H|400||1|x|x|\n"
                "222222|2026|H|400||1|x|x|\n", encoding="utf-8")
            r = _run([sys.executable, _paths.script("build_careers.py"), "--out", "careers.json"],
                     cwd=str(tmp), capture_output=True, text=True, timeout=120)
            said = (r.stdout or "") + (r.stderr or "")
            if clashing:
                if r.returncode == 0 or "2026 H 1" not in said:
                    bad.append("build_careers built careers.json over two terms' votes under one key "
                               f"(2026 H 1): exit {r.returncode}, {said.strip()[-200:]!r}")
            else:
                got = json.loads((tmp / "careers.json").read_text(encoding="utf-8")) \
                    if (tmp / "careers.json").exists() else {}
                terms = {k: v.get("terms") for k, v in got.items()}
                if terms != {"111111": ["2025-2026", "2027-2028"], "222222": ["2027-2028"]}:
                    bad.append(f"careers.json gives the terms {terms} ({said.strip()[-200:]!r})")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    # A sitting of the day, for the next term's resolution and a vote on no bill.
    narr = {"2027-2028": {"HR1": [{"type": "floor", "date": "2026-12-02", "body": "H",
                                   "raw": "Ought to Pass: MA VV 12/02/2026  HJ 1",
                                   "action": "Ought to Pass", "motion": "MA",
                                   "vote_kind": "VV", "cite": "HJ 1"}]}}
    rolls = {"2027-2028": {"_procedural": [
        _rc("2026", "H", 400, "2026-12-02", "", "Election of Speaker", 210, 180, True,
            procedural=True)]}}
    days = _sitting_fixture(SD, narr, rolls)
    day = days.get(("H", "2026-12-02"))
    if day is None:
        bad.append(f"no sitting of 2 December 2026 is drawn: {sorted(days)}")
    else:
        if not any((i.yeas, i.nays) == (210, 180) for i in list(day.items) + list(day.others)):
            bad.append("the vote on no bill is not on the sitting of 2 December 2026")
        nobody = type("Nobody", (), {"slug": lambda self, body, name: None})()
        try:
            page = BSP.render(day, {"attributions": []}, {}, {("2027-2028", "HR1"): 2027},
                              nobody, _html.escape)[0]
            if "210" not in page or "HR 1" not in page:
                bad.append("the sitting of 2 December 2026 does not draw the day's votes")
        except Exception as e:
            bad.append(f"the sitting of 2 December 2026 does not render: {type(e).__name__}: {e}")
    assert not bad, "\n".join(bad)
    return "ok", ("Organization Day's roll calls are the next term's, filed under either year: "
                  "kept beside the frozen term's files and out of its record, keyed 2027-2028 "
                  "in rollcalls.json and careers.json, and drawn with a vote on no bill on the "
                  "day's sitting; a key naming two terms' votes stops careers.json")


# WHAT IS DATED AND FILED UNDER NO SESSION YEAR TAKES ITS TERM FROM THE DAY,
# Organization Day the next term's (proceedings.term_on): the files that read
# one, and what each reads it for.
TERM_ON_READERS = {
    "build_proceedings.py": ('"term": P.term_on(date), "bill": bill,',
                             '"term": P.term_on(date), "bill": b,', "term = P.term_on(day)"),
    "build_floor_index.py": ('(P.term_on(date), r["bill"]) not in known',),
    "build_feeds.py": ("by_id.get((P.term_on(date), bill))", 's.get("term") or P.term_on(d)',
                       '(bb or {}).get("term") or P.term_on(day)'),
    "calendar_meetings.py": ('P.term_on(r["date"]) != term',),
}


@check("session", "a floor debate, hearing or recording of Organization Day is the next term's "
       "in proceedings.csv, as its roll calls are", needs=("proceedings", "build_proceedings"))
def _organization_day_floor_rows(P, BP):
    """private/UNATTENDED_AUDIT_2026-10-18.md, section 2, called it latent:
    build_proceedings and build_floor_index gave a row its term with
    proceedings.term_of(day), the calendar-year rule, where vote_term gives
    Organization Day of an even year to the next term. It was not latent. The
    built proceedings.csv of 17 October 2026 held 10 floor rows of 4 December
    2024 -- HR 1 to 5 and SR 1 to 5 of 2025, the 2025-2026 rules and officers
    the docket files under 2025 -- under 2023-2024, and site/bill/2023/hr1.html,
    2023's own rules resolution, showed the 2024 Organization Day's recording
    (G744U5Zw5Kk) as its floor debate. 2 December 2026 would have done the same
    to 2027-2028's.

    Held here: proceedings.term_on on either side of three Organization Days
    and on nothing; build_proceedings' manifest, floor-index and term-recovery
    readers filing a row of 2 December 2026 under 2027-2028 and one of
    1 December under 2025-2026; and every reader in TERM_ON_READERS still
    reading the day that way, by its source."""
    bad = []
    for day, want in (("2026-12-01", "2025-2026"), ("2026-12-02", "2027-2028"),
                      ("2026-12-31", "2027-2028"), ("2027-01-06", "2027-2028"),
                      ("2024-12-03", "2023-2024"), ("2024-12-04", "2025-2026"),
                      ("2022-12-07", "2023-2024"), ("2025-12-17", "2025-2026"),
                      ("", ""), (None, "")):
        if P.term_on(day) != want:
            bad.append(f"term_on({day!r}) is {P.term_on(day)!r}, not {want!r}")
    tmp = Path(tempfile.mkdtemp(prefix="gr-orgday-floor-"))
    try:
        (tmp / "floor_index.json").write_text(json.dumps({
            "HR1": [{"date": "2026-12-02", "body": "H", "video_id": "ORG", "kind": "floor debate",
                     "motions": ["Ought to Pass"], "tallies": [], "precise": False}],
            "HB1": [{"date": "2026-12-01", "body": "H", "video_id": "OLD", "kind": "floor debate",
                     "motions": [], "tallies": [], "precise": False}]}), encoding="utf-8")
        got = {(r["bill"], r["date"]): r["term"] for r in BP.from_floor_index(tmp / "floor_index.json")}
        if got != {("HR1", "2026-12-02"): "2027-2028", ("HB1", "2026-12-01"): "2025-2026"}:
            bad.append(f"build_proceedings files the floor index's rows as {got}")
        with open(tmp / "m.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["bill", "sched_date", "body", "proceeding"])
            w.writeheader()
            w.writerow({"bill": "HB2", "sched_date": "2024-12-04", "body": "H", "proceeding": "hearing"})
            w.writerow({"bill": "HB3", "sched_date": "2024-11-20", "body": "H", "proceeding": "hearing"})
        got = {r["bill"]: r["term"] for r in BP.from_manifest(tmp / "m.csv")}
        if got != {"HB2": "2025-2026", "HB3": "2023-2024"}:
            bad.append(f"build_proceedings files a manifest's rows as {got}")
        rows = [{"term": "", "video_id": "V1", "date": ""}]
        BP.recover_terms(rows, {"V1": ("2026-12-02", "stream")})
        if rows[0]["term"] != "2027-2028":
            bad.append(f"a recording of 2 December 2026 recovers the term {rows[0]['term']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, says in TERM_ON_READERS.items():
        src = _paths.locate(name).read_text(encoding="utf-8")
        for s in says:
            if s not in src:
                bad.append(f"{name} no longer reads a day's term as term_on: {s!r} is gone")
    assert not bad, "; ".join(bad)
    return "ok", (f"Organization Day and after are the next term's on {len(TERM_ON_READERS)} readers "
                  "of a day; the floor index, a manifest and a recovered recording each file "
                  "2 December 2026 under 2027-2028")


@check("session", "a roll call's term is read once for each year and day, and what is kept is "
       "what a fresh reading gives, either side of Organization Day and for an argument no "
       "dict can hold", needs=("proceedings",))
def _vote_term_kept(P):
    """proceedings.vote_term keeps its answer for each (year, day) it is asked
    (16 October 2026, private/SITE_DATA_PROFILE.md, P1): the site data step
    asked it 13 million times for 718 different pairs, about a minute of the
    step. Held here against _vote_term, the same reading done afresh: the
    days either side of Organization Day of 2024 and 2026, in both shapes a
    roll call's day comes in, with the year as a number and as words, each
    asked twice so that the second answer is the kept one; 1 and then True
    and 1.0, which a dict takes for one key and term_of reads apart (1-2, and
    nothing); an argument no dict can hold, read afresh rather than raising;
    and a pair asked twice read once. Undone, the step is a minute slower
    and nothing else would say so."""
    import datetime as _dt
    plain = P._vote_term
    cases = []
    for y in (2024, 2026):
        org = P.organization_day(y)
        for d in (org - _dt.timedelta(days=1), org, org + _dt.timedelta(days=1)):
            for year in (y, str(y), y + 1, str(y + 1)):
                for when in (d.isoformat(), f"{d.month}/{d.day}/{d.year} 10:31:07 AM"):
                    cases.append((year, when))
    # 1 before True and 1.0, so that a key blind to the type hands them 1's.
    cases += [(1, ""), (True, ""), (1.0, ""), (2026, ""), (2026.0, ""), ("2026", None),
              (2026.0, "2026-12-02"), ("", ""), (None, None)]
    P._VOTE_TERMS.clear()
    bad = []
    for rnd in ("first", "kept"):
        for year, when in cases:
            got, want = P.vote_term(year, when), plain(year, when)
            if got != want or type(got) is not type(want):
                bad.append(f"{rnd} asking ({year!r}, {when!r}): {got!r}, read afresh {want!r}")
    for year, when in ((["2026"], "2026-12-02"), (["2026"], ""), ("2026", ["2026-12-02"]),
                       ({"y": 2026}, "12/2/2026 10:31:07 AM")):
        try:
            got = P.vote_term(year, when)
        except TypeError as e:
            bad.append(f"({year!r}, {when!r}), which no dict can hold, raises: {e}")
            continue
        if got != plain(year, when):
            bad.append(f"({year!r}, {when!r}), which no dict can hold, is {got!r}, "
                       f"read afresh {plain(year, when)!r}")
    asked = []
    P._VOTE_TERMS.clear()
    P._vote_term = lambda year, when="": (asked.append((year, when)), plain(year, when))[1]
    try:
        for _ in range(3):
            P.vote_term("2026", "2026-12-02")
    finally:
        P._vote_term = plain
        P._VOTE_TERMS.clear()
    if len(asked) != 1:
        bad.append(f"a pair asked three times is read by _vote_term {len(asked)} times, not "
                   "once: vote_term keeps nothing, or reads it some other way, and the site "
                   "data step asks 718 pairs 13 million times")
    assert not bad, "\n".join(bad[:8])
    return "ok", (f"{len(cases)} (year, day) pairs kept as read afresh, around Organization "
                  "Day of 2024 and 2026, 1 apart from True and 1.0; an argument no dict can "
                  "hold read afresh; a pair asked three times read once")


# Printed lines, not composed ones. The Election Law block is House Calendar 2
# of 2018 as pdftotext gave it, its two columns out of step at HB 1540; the
# Resources header and its work session are House Calendar 20 of 2005, and the
# Oversight header House Calendar 21 of 1999. Only the masthead's date and the
# stitching between blocks are this file's.
CALENDAR_FIELDS = """\
 Vol.40         Concord,N.H.  Friday,January12,2018                    No.2X

                              COMMITTEE MEETINGS

                    TUESDAY, JANUARY 23

ELECTION LAW, Room 308, LOB

10:00 a.m.  HB 1520, relative to access to ballots and relative to verification counts of machine-counted ballots.
10:30 a.m.  HB 1582, relative to the authority of the moderator to verify the device count.
11:00 a.m.  HB 1486, relative to "over voted" ballots.
            HB 1540-FN, relative to ranked-choice voting.
 1:00 p.m.  HB 1240, allowing voters to vote for multiple candidates for an office.
 1:30 p.m.  Executive session on pending legislation may be held throughout the day, time permitting, from
            the time the committee is initially convened.

RESOURCES, RECREATION AND DEVELOPMENT, Room 305, LOB
2:00 p.m.   Subcommittee work session on HB 491, relative to the inherent dangers of OHRV
            operation and limiting landowner liability for certain fish and game related land uses
            and HB 355, establishing a committee to study the environmental impact and
            damage mitigation of ATV use on public and private trails.

   HEALTH AND HUMAN SERVICES OVERSIGHT COMMITTEE, (RSA 126-A:13), Room 205, LOB
                                        1:30 p.m. Regular meeting.
"""


@check("calendar", "a committee's name keeps its commas, and a bill's line is never a committee",
       needs=("calendar_meetings",))
def _calendar_fields(calendar_meetings):
    """The two ways a calendar header was split in the wrong place.

    A name with a comma of its own was cut at it: "HEALTH, HUMAN SERVICES AND
    ELDERLY AFFAIRS, Room 205, LOB" became the committee "Health" with the rest
    kept as an address. And a bill's own line -- "HB 1540-FN, relative to
    ranked-choice voting.", which shouts and has a comma -- was read as a
    header wherever the columns slipped and left it with no time, so HB 1240
    was heard by the committee "Hb 1540-Fn" in the room "relative to
    ranked-choice voting.". Both were marked wrong on the bench. 16,375 and
    5,054 House rows on 10 September.
    """
    rows, pub, unpaired = calendar_meetings.parse(CALENDAR_FIELDS, "H")
    assert pub == (2018, 1, 12), f"the masthead read as {pub}"
    by = {r["bill"]: r for r in rows if r["bill"]}
    lead = re.compile(r"^(?:Hb|Sb|Hr|Sr|Hcr|Scr|Cacr|Hjr)\s*\d", re.I)
    bad = [r["committee"] for r in rows if lead.match(r["committee"] or "")]
    assert not bad, f"a bill's line was read as a committee: {bad}"
    want = [
        ("HB1240", "Election Law", "LOB 308"),
        ("HB355", "Resources, Recreation and Development", "LOB 305"),
        ("HB491", "Resources, Recreation and Development", "LOB 305"),
    ]
    for bill, com, room in want:
        r = by.get(bill)
        assert r, f"{bill} was not read at all"
        assert (r["committee"], r["room"]) == (com, room), (
            f"{bill} reads as {r['committee']!r} in {r['room'] or r['venue']!r}, "
            f"not {com!r} in {room!r}")
    over = [r for r in rows if r["kind"] == "regular meeting"]
    assert over and over[0]["committee"] == \
        "Health and Human Services Oversight Committee" and \
        over[0]["room"] == "LOB 205", (
        "a citation standing as its own part kept the room out of the room "
        f"field: {[(r['committee'], r['room'] or r['venue']) for r in over]}")
    # HB 1540's line has no time beside it, and the docket puts it at 1:00 --
    # the time printed a line below it. It is not given 11:00 by being welded
    # to HB 1486, and it is not given a time at all; it is counted.
    assert "HB1540" not in by, (
        f"HB 1540 was given a time the calendar does not print beside it: "
        f"{by['HB1540']['time']}")
    assert any("HB 1540" in u[3] for u in unpaired), \
        "HB 1540's untimed line was dropped without being counted"
    return "ok", (f"{len(rows)} rows: whole names, rooms in the room field, and "
                  "the untimed HB 1540 counted rather than timed or made a committee")


# Printed lines, each with its time, copied out of the file named beside it;
# only the indentation before the time and the line ending are dropped.
CALENDAR_KIND_LINES = [
    # calendars/2000/HC047.txt:561
    ("8:30 a.m. Interim study subcommittee work session on HB 1152, relative to the establishment of",
     "subcommittee work session"),
    # calendars/2005/HC058.txt:562
    ("10:00 a.m. Retained full committee work session on HB 690-FN, relative to medical services",
     "full committee work session"),
    # calendars/1997/HC013.txt:619
    ("2:00 p.m. Telecommunications subcommittee work session on HB 254, relative to shared tenant telecommunication services.",
     "subcommittee work session"),
    # calendars/1999/HC038.txt:1531
    ("9:00 a.m. Work and executive session on HB 596, making technical corrections to certain laws",
     "executive session"),
    # calendars/2009/HC056.txt:961
    ("11:00 a.m. Or immediately following the House session, executive session on HB 139,",
     "executive session"),
    # calendars/1997/HC011.txt:244
    ("10:15 a.m. Rescheduled public hearing on HB 143-LOCAL, requiring that SAU budgets be approved by vote at school district meetings.",
     "public hearing"),
    # calendars/2017/HC016.txt:404
    ("10:00 a.m. Budget work session on HB 1-A, making appropriations for the expenses of certain departments",
     "work session"),
]
# calendars/1998/HC005.txt:742 -- a title that says "public hearing".
CALENDAR_KIND_TITLE = \
    "10:30 a.m. HB 1282-LOCAL, requiring a public hearing and vote of the town before a conservation"

# The same through parse(). Printed lines again: the masthead (line 7), the
# section heading (1773), the day (2447) and the Finance block (2449-2456) are
# House Calendar 14 of 2012; the Health block is House Calendar 58 of 2005,
# lines 561-566. Only the stitching of the one block into the other is this
# file's.
CALENDAR_KINDS = """\
Vol. 34 Concord, N.H.  Friday, February 17, 2012                                    No. 14

                          COMMITTEE MEETINGS

                              TUESDAY, MARCH 20

HEALTH, HUMAN SERVICES AND ELDERLY AFFAIRS, Room 205, LOB
10:00 a.m. Retained full committee work session on HB 690-FN, relative to medical services

                     for children and pregnant women, HB 704-FN, establishing the New Hampshire Rx
                     advantage program and continually appropriating a special fund, SB 110-FN-A,
                     establishing the New Hampshire Rx plus program for prescription drugs.

FINANCE,    Rooms 210-211, LOB
11:00 a.m.      Executive session on HB 1274-FN, transferring the McAuliffe-Shepard
                discovery center to a private operator and making a supplemental
                appropriation therefor, HB 1285-FN, repealing the state art fund, HB 1521-
                FN, relative to retired state employees group insurance participation,
                rescheduled executive session on HB 234-FN-A, relative to food service
                licensure and establishing a committee to study the regulation of food service
                establishments, HB 533-FN-L, establishing a cap on the amount of school
"""


@check("calendar", "a qualified kind is read as the kind it qualifies, and a bill's title is never a kind",
       needs=("calendar_meetings",))
def _calendar_kinds(calendar_meetings):
    """The clerk writes "Interim study subcommittee work session on HB 1152",
    and the kind was read off a list anchored on the bare words -- so the line
    matched nothing, named a bill, and was published as a public hearing on
    it. 3,802 distinct House bill rows on 13 September, 2,819 of them
    subcommittee work sessions. KIND_OF reads past the qualifier.

    Two ways back to wrong, each checked here. A pattern loose enough to read
    past "Interim study" can read "requiring a public hearing" out of a bill's
    title, which is a public hearing only because it states nothing and names
    a bill; so the title line must match no pattern at all. And the qualifier
    list must stay out of the continuation split, where STATED decides what
    starts a new item: asked there, "rescheduled executive session on HB
    234-FN-A", a continuation line starting lower case, became an item of its
    own and was discarded as a column slip, with the bills after it. So the
    printed Finance block of 2012 must still give HB 234 its executive
    session, and the Health block of 2005 must come out of parse() -- not only
    out of kind_of() -- as a full committee work session.
    """
    CM = calendar_meetings

    def rest(line):
        t = CM.TIME.match(line)
        assert t, f"not a time line: {line[:50]!r}"
        return t.group(4)

    for line, want in CALENDAR_KIND_LINES:
        r = rest(line)
        read = next((k for rx, k in CM.KIND_OF if rx.match(r.strip())), "")
        got = CM.kind_of(r, CM._bills(r))
        assert got == want, f"{r[:60]!r} reads as {got!r}, not {want!r}"
        # A qualified public hearing would come out right by inference too,
        # so the kind must be READ, not guessed from the bill.
        assert read == want, (
            f"{r[:60]!r} came out {got!r} only because it names a bill; no "
            f"KIND_OF pattern read the {want!r} it states")

    r = rest(CALENDAR_KIND_TITLE)
    hit = [k for rx, k in CM.KIND_OF if rx.match(r.strip())]
    assert not hit, (f"a bill's title was read as a kind: {r[:60]!r} matched "
                     f"{hit}. It is a public hearing because it names a bill "
                     "and states nothing.")
    got = CM.kind_of(r, CM._bills(r))
    assert got == "public hearing", f"{r[:60]!r} reads as {got!r}"

    rows, pub, _ = CM.parse(CALENDAR_KINDS, "H")
    assert pub == (2012, 2, 17), f"the masthead read as {pub}"
    by = {r["bill"]: r["kind"] for r in rows if r["bill"]}
    assert by.get("HB690") == "full committee work session", (
        f"parse() read HB 690's retained full committee work session as "
        f"{by.get('HB690')!r}: the kind is not being read through kind_of()")
    lost = [b for b in ("HB234", "HB533") if b not in by]
    assert not lost, (
        f"{', '.join(lost)} vanished from the Finance block: a continuation line "
        "that opens \"rescheduled executive session\" was split off as an item "
        "and discarded as a column slip. The split asks STATED, not KIND_OF.")
    assert by["HB234"] == "executive session", f"HB 234 reads as {by['HB234']!r}"
    return "ok", (f"{len(CALENDAR_KIND_LINES)} qualified kinds read as stated, a "
                  f"title that says \"public hearing\" matched by nothing, and "
                  f"{len(by)} bills out of two printed blocks")


@check("data", "the calendar's picker on this disk links only addresses archive/queue.csv holds")
def _calendar_documents_on_disk():
    """The same rule as _calendar_documents, held against the real list.

    Every document the picker would link today is at an address the queue
    records, no two share one, and every row is either linked, left out and
    counted, or one of two listings of one document. Where a site is built,
    its index and its section link nothing the queue does not hold -- which
    stays true of a site built from an older, shorter list -- and a page that
    carries the section has the index it reads and the list page it links.

    The list's age is said and never failed on: the queue is refreshed at
    night, a picker a few days behind is no reason to stop a build, and
    build_calendar.py warns on every run when the newest House calendar is
    three weeks old.
    """
    import datetime as _dt
    import html as _h
    import calendar_documents as CD
    rows = CD.rows()
    if not rows:
        return "skip", "archive/queue.csv is not here"
    docs, left = CD.read()
    recorded = {r.get("url") for r in rows}
    assert docs, "archive/queue.csv lists nothing the picker can link"
    stray = [d.url for d in docs if d.url not in recorded]
    assert not stray, f"{len(stray)} linked addresses are not in the queue: {stray[:2]}"
    assert len({d.url for d in docs}) == len(docs), "two linked documents share one address"
    twice = len(rows) - len(docs) - len(left)
    assert 0 <= twice <= len(docs), (
        f"{len(rows)} rows became {len(docs)} linked and {len(left)} left out")
    ix = CD.index(docs)
    made = {CD.address(ix, s["chamber"], d) for s in ix["sets"]
            for ds in s["years"].values() for d in ds}
    assert made == {d.url for d in docs}, (
        "the index's prefix and tail do not give back the recorded addresses")
    said = (f"{len(docs):,} linked, {len(left):,} left out, {twice:,} second listings of "
            "one document")
    built = Path("site") / "calendar" / "documents.json"
    page = Path("site") / "calendar.html"
    if built.exists() and page.exists():
        sx = json.loads(built.read_text(encoding="utf-8"))
        on_site = {CD.address(sx, s["chamber"], d) for s in sx["sets"]
                   for ds in s["years"].values() for d in ds}
        assert on_site <= recorded, (
            f"site/calendar/documents.json holds {len(on_site - recorded)} addresses the "
            f"queue does not: {sorted(on_site - recorded)[:2]}")
        t = page.read_text(encoding="utf-8")
        assert t.count('<section class="cdocs" id="cdocs"') == 1, (
            "site/calendar/documents.json is built and site/calendar.html has no section")
        assert (Path("site") / "calendar" / "documents.html").exists(), (
            "site/calendar.html links /calendar/documents and site/calendar/documents.html "
            "is not there: run build_calendar.py")
        sec = t[t.index('<section class="cdocs"'):]
        sec = sec[:sec.index("</section>")]
        ext = {_h.unescape(h) for h in re.findall(r'href="(https://[^"]*)"', sec)}
        assert ext and ext <= recorded, (
            f"site/calendar.html's section links {sorted(ext - recorded)[:2]}, which the "
            "queue does not hold")
        said += f"; the built site links {len(on_site):,}, all of them recorded"
    elif page.exists():
        t = page.read_text(encoding="utf-8")
        # A PAGE WITH THE SECTION AND NO INDEX is pickers that load nothing and
        # a link to a list that is not there. A page with neither was built
        # before the pickers were, or on a folder with no queue, and is said.
        assert '<section class="cdocs" id="cdocs"' not in t, (
            "site/calendar.html carries the Calendars & Journals section and "
            "site/calendar/documents.json is not there: run build_calendar.py")
        said += ("; site/calendar.html was built without the section -- "
                 "build_calendar.py will draw it")
    first = CD.newest(docs, "hc")
    newest = CD.newest_date(docs, "hc")
    if first is not None and not first.date:
        said += f"; the newest House calendar listed is {first.name}, whose date is not read yet"
    elif newest:
        age = (_dt.date.today() - _dt.date.fromisoformat(newest)).days
        said += f"; the newest House calendar listed is {CD.day_words(newest)}, {age} days ago"
    return "ok", said


@check("livestreams", "the maps beside the recordings are one list, segment_markers', and the "
                      "night's guard keeps a reading whose merge carries _named_before or _not_named",
       needs=("livestreams", "segment_markers", "cloud"))
def _ls_sides_one_list(livestreams, segment_markers, CL):
    """ONE DEFINITION OF THE SIDES (17 October 2026). segment_markers writes
    maps beside candidate_segments.json's recordings, keyed on recording,
    and added _named_before to them; livestreams kept its own list of them,
    which did not hear of it, so the night's guard read _named_before as a
    recording that had changed and put back every reading of a new recording
    that carried one -- and cloud.py send-night's copy would have counted it
    as a recording. Now each reads segment_markers.SIDES. A night's merge
    that adds tonight's recording's _named_before is kept; one that changes
    another recording's is still caught."""
    S = segment_markers.SIDES
    assert {"_named_before", "_not_named"} <= set(S) and livestreams.SIDES is S, \
        "livestreams does not read segment_markers' list of the maps beside the recordings"
    recs, sides = CL.recordings_in("candidate_segments.json", json.dumps(
        {"V1": {}, **{s: {"V1": []} for s in S}}).encode("utf-8"))
    assert set(recs) == {"V1"} and set(sides) == set(S), (recs, sides)
    here = os.getcwd()
    real_probe = livestreams.probe
    tmp = Path(tempfile.mkdtemp(prefix="gr-sides-"))
    try:
        os.chdir(tmp)
        (tmp / "kept").mkdir()
        was = {"PFOTHER": {"HB77": [{"start": 60.0}]},
               "_named_before": {"PFOTHER": ["HB9|hearing"]}}
        spans = {"about": "x", "recordings": {"PFOTHER": {"last": 60.0}}}
        Path("kept/candidate_segments.json").write_text(json.dumps(was), encoding="utf-8")
        Path("kept/caption_spans.json").write_text(json.dumps(spans), encoding="utf-8")

        class Copies:
            def changed(self):
                return True

            def before(self, path):
                return Path("kept") / Path(path).name
        livestreams.probe = lambda c, cwd=None: {"marked": 1, "placed": 1, "median": 1.0}

        def night(named):
            now = json.loads(json.dumps(was))
            now["PFNEW"] = {"HB1": [{"start": 5.0}]}
            now["_named_before"] = named
            Path("candidate_segments.json").write_text(json.dumps(now), encoding="utf-8")
            s = json.loads(json.dumps(spans))
            s["recordings"]["PFNEW"] = {"last": 30.0}
            Path("caption_spans.json").write_text(json.dumps(s), encoding="utf-8")
            return livestreams.guard(Copies(), {"PFNEW"})[0]
        why = night({"PFOTHER": ["HB9|hearing"], "PFNEW": ["HB1|hearing"]})
        assert why == "", f"a reading carrying tonight's _named_before was put back: {why}"
        why = night({"PFOTHER": ["HB10|hearing"], "PFNEW": ["HB1|hearing"]})
        assert "_named_before/PFOTHER" in why, f"another recording's _named_before changed unseen: {why!r}"
        # _not_named, the committee bills a recording never names (17 October
        # 2026), is held the same way: tonight's added is kept, and another
        # recording's, changed or gone, is caught.
        was["_not_named"] = {"PFOTHER": ["HB12"]}
        Path("kept/candidate_segments.json").write_text(json.dumps(was), encoding="utf-8")

        def night_nn(nn):
            now = json.loads(json.dumps(was))
            now["PFNEW"] = {"HB1": [{"start": 5.0}]}
            now["_not_named"] = nn
            Path("candidate_segments.json").write_text(json.dumps(now), encoding="utf-8")
            s = json.loads(json.dumps(spans))
            s["recordings"]["PFNEW"] = {"last": 30.0}
            Path("caption_spans.json").write_text(json.dumps(s), encoding="utf-8")
            return livestreams.guard(Copies(), {"PFNEW"})[0]
        why = night_nn({"PFOTHER": ["HB12"], "PFNEW": ["HB2"]})
        assert why == "", f"a reading carrying tonight's _not_named was put back: {why}"
        why = night_nn({"PFNEW": ["HB2"]})
        assert "_not_named/PFOTHER" in why, f"another recording's _not_named went unseen: {why!r}"
    finally:
        livestreams.probe = real_probe
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", (f"{len(S)} maps, one list; a merge carrying tonight's _named_before or "
                  "_not_named is kept, another recording's changed is caught")


@check("livestreams", "the night keeps a reading of its new recordings only past the "
                      "timestamp guard, and its verdict says when one was put back",
       needs=("livestreams", "nightly", "probe_alignment", "caption_span"))
def _ls_markers_guard(livestreams, nightly, probe_alignment, caption_span):
    """CLAUDE.md: nothing about timestamps goes on the site before
    `probe_alignment.py --truth --candidate candidate_segments.json` has been
    run and the median has not regressed. The laptop's evening job held the
    caption results to that before it sent them, and was retired on
    10 October 2026, when the night took the captions over and
    candidate_segments.json and caption_spans.json became the night's files
    in the kit. So the night's --markers step holds itself to it: copies of
    both files before it reads, and both put back, byte for byte, when

      - an entry other than tonight's recordings changed (a merge that
        damages what is already there: the failure that cost 842
        recordings once and the hand-marked times twice);
      - the probe places fewer of the same hand-timed proceedings, or its
        median is worse -- driven here through the real probe, on a
        hand-timed proceeding the night's reading lands far from;
      - the probe would not run, so nothing could be scored;
      - segment_markers itself failed (exit 1, files put back first).

    Each put-back exits 0 -- the build and the night go on and publish --
    leaves the recordings to be asked for again (as failures, so three at
    most), says why in the state, and gives the night's verdict a warning of
    a kind of its own, which the gate holds for a person. A reading that
    passes is kept and the state says so. Nothing here asks anybody: the
    captions are a fixture, and the probe reads files.
    """
    import contextlib
    import io
    import types
    L = livestreams
    root = Path(tempfile.mkdtemp(prefix="gr-guard-"))
    here = os.getcwd()
    real_read, real_probe = L.read_markers, L.probe
    saved_env = {k: os.environ.pop(k, None) for k in ("GITHUB_ACTIONS", "GRANITE_PROCEEDINGS")}
    try:
        _ls_markers_fixture(root)
        (root / "work" / "PFNEW000001").mkdir(parents=True)
        (root / "work" / "PFNEW000001" / "captions.en.json3").write_text(json.dumps(_json3(
            ["good morning", "I am opening the hearing on House Bill 1491"])), encoding="utf-8")
        state = {"version": 1, "channels": {}, "last_run": {}, "refusals": {},
                 "videos": {"PFNEW000001": {"status": "finished", "captions": "captioned",
                                            "by": "runner", "chamber": "house",
                                            "seen": "2026-10-09T08:30:00Z"}}}
        (root / "archive").mkdir()
        files = ("candidate_segments.json", "caption_spans.json")
        os.chdir(root)

        def night(when="2026-10-10T09:00:00Z"):
            """A fresh night: the state and both files as kit-down brings
            them, --markers run; (exit, the state after, the files after)."""
            Path("archive/livestreams.json").write_text(json.dumps(state), encoding="utf-8")
            Path(".segment_cache.json").unlink(missing_ok=True)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = L.main(["--markers", "--origin", "runner", "--now", when])
            st = json.loads(Path("archive/livestreams.json").read_text(encoding="utf-8"))
            return code, st, {f: Path(f).read_bytes() for f in files}, out.getvalue()

        _ls_markers_fixture(root)
        kit = {f: Path(f).read_bytes() for f in files}

        def put_back(code, st, after, out, want_why, want_code=0):
            assert code == want_code, (code, out[-300:])
            assert after == kit, "the caption results were not put back as they came down"
            mk, v = st["markers"], st["videos"]["PFNEW000001"]
            assert mk["guard"].startswith("put back: ") and want_why in mk["guard"], mk
            assert v["captions"] == "failed" and v.get("tries") == 1 and "read" not in v \
                and "not kept" in v["why"], v
            return mk

        # A reading that passes is kept, and the state says so.
        code, st, after, out = night()
        assert code == 0 and after != kit, out[-300:]
        assert st["markers"]["guard"] == "passed" and st["videos"]["PFNEW000001"].get("read"), \
            st["markers"]
        assert "HB1491" in json.loads(after["candidate_segments.json"])["PFNEW000001"]

        # A merge that damages an entry already there.
        def damaging(vids):
            code = real_read(vids)
            doc = json.loads(Path("candidate_segments.json").read_text(encoding="utf-8"))
            doc["PFOTHER"]["HB77"][0]["start"] = 3600.0
            Path("candidate_segments.json").write_text(json.dumps(doc), encoding="utf-8")
            return code
        _ls_markers_fixture(root)
        L.read_markers = damaging
        put_back(*night(), "entries besides tonight's recordings changed")
        L.read_markers = real_read

        # The probe: worse, fewer placed, would not run -- each read as such.
        for scores, why in (([{"marked": 1, "placed": 1, "median": 1.0},
                              {"marked": 1, "placed": 1, "median": 30.0}], "median went"),
                            ([{"marked": 2, "placed": 2, "median": 1.0},
                              {"marked": 2, "placed": 1, "median": 1.0}], "places 1 of 2"),
                            ([{"marked": 1, "placed": 1, "median": 1.0}, None], "would not run")):
            seq = iter(scores)
            L.probe = lambda candidate, seq=seq: next(seq)
            _ls_markers_fixture(root)
            put_back(*night(), why)
        L.probe = real_probe

        # The real probe, on a hand-timed proceeding on tonight's recording
        # that the reading lands nearly eight minutes from: placed for the
        # first time, more than a minute off (livestreams.worse, like with
        # like since 24 October 2026; a worse median before).
        _ls_markers_fixture(root)
        with open("review/ground_truth.csv", "a", encoding="utf-8") as fh:
            fh.write("PFNEW000001,HB1491,public hearing,480.0,,,2026-10-10\n")
        mk = put_back(*night(), "for the first time")
        got = mk["probe"]["before"]
        assert {k: got.get(k) for k in ("marked", "placed", "median")} == {
            "marked": 2, "placed": 1, "median": 1.0} and len(got.get("each") or {}) == 1 \
            and mk["probe"]["after"]["placed"] == 2, mk["probe"]
        _ls_markers_fixture(root)

        # segment_markers failing is the step failing, with the files put back.
        def failing(vids):
            Path("candidate_segments.json").write_text("{half", encoding="utf-8")
            return 1
        L.read_markers = failing
        put_back(*night(), "did not finish", want_code=1)
        L.read_markers = real_read

        # And the night's verdict: a put-back is a warning of its own kind,
        # the waiting recordings keep the kind they always had, and the
        # verdict's "captions" says what --markers did.
        L.probe = lambda candidate, seq=iter([{"marked": 1, "placed": 1, "median": 1.0},
                                              None]): next(seq)
        night()
        L.probe = real_probe
        started = "2026-10-10T08:50:00+00:00"
        rec = nightly.captions_record(started)
        assert rec["guard"].startswith("put back") and rec["read"] == 1, rec
        assert "the guard: put back" in nightly.captions_line(rec), nightly.captions_line(rec)
        warned = nightly.Night.warned(types.SimpleNamespace(v={"started": started}))
        kinds = [k for k, _w in warned]
        assert nightly.KIND_CAPTIONS_PUT_BACK in kinds, warned
        assert "were not kept" in dict(warned)[nightly.KIND_CAPTIONS_PUT_BACK], warned
        assert nightly.KIND_CAPTIONS_WAIT == "recordings with no start time from their captions yet", \
            "the waiting recordings' warning changed its kind, so the gate would hold a night for it"
        # A night later, with no --markers since, the put-back is old news.
        later = "2026-10-11T08:50:00+00:00"
        assert not nightly.captions_record(later)["read"] and nightly.KIND_CAPTIONS_PUT_BACK not in \
            [k for k, _w in nightly.Night.warned(types.SimpleNamespace(v={"started": later}))]
        return "ok", ("a passing reading kept; a damaged neighbour, a worse median, fewer placed, "
                      "a probe that would not run and the real probe on a hand-timed proceeding "
                      "each put both files back byte for byte with exit 0, the recordings asked "
                      "again as failures; segment_markers failing exits 1 with them put back; the "
                      "verdict warns of a put-back that night only, under a kind of its own")
    finally:
        L.read_markers, L.probe = real_read, real_probe
        os.chdir(here)
        for k, val in saved_env.items():
            if val is not None:
                os.environ[k] = val
        shutil.rmtree(root, ignore_errors=True)


@check("livestreams", "yt-dlp asks with node, and its warnings go to the day's log, never into "
                      "how an answer is read", needs=("livestreams",))
def _ls_warnings_logged(livestreams):
    """yt-dlp 2026.08.19 uses no JavaScript runtime it is not told about
    (only deno by default, which neither machine has) and warned, unseen
    under --no-warnings, that YouTube extraction without one is deprecated.
    So every ask names node, and the warnings are kept: split off what yt-dlp
    said before it is read -- what is left is exactly what --no-warnings
    printed, so no answer is read differently (a warning that names an HTTP
    403 on a request yt-dlp retried is not a refusal) -- and written to
    logs/youtube-<day>.log, with everything yt-dlp said about an ask that
    brought no captions. Nothing of it is printed: the step's output is the
    run's public page. Driven through ask_track with yt-dlp stood in for."""
    import contextlib
    import io
    import subprocess as _sp
    import types
    L = livestreams
    args = L.ytdlp_args("en")
    at = [k for k, x in enumerate(args) if x == "--js-runtimes"]
    assert len(at) == 1 and args[at[0] + 1] == "node", f"yt-dlp is not told to use node: {args}"
    assert "--no-warnings" not in args and "--verbose" not in args and "-v" not in args, \
        f"yt-dlp's warnings are hidden, or its debug output (which prints a proxy) is on: {args}"
    said, warned = L.split_warnings("WARNING: [youtube] x: one\n[info] two\n  WARNING: three\nERROR: four")
    assert said == "[info] two\nERROR: four" and len(warned) == 2, (said, warned)
    root = Path(tempfile.mkdtemp(prefix="gr-ytwarn-"))
    here, real_sp = os.getcwd(), L.subprocess
    cmds = []

    def fake(answer, captions=False):
        def run(cmd, **kw):
            cmds.append(cmd)
            if captions:
                out = Path(cmd[cmd.index("-o") + 1])
                out.with_name("captions.en.json3").write_text(json.dumps(_json3(
                    ["good morning", "I am opening the hearing on House Bill 1491"])),
                    encoding="utf-8")
            return _sp.CompletedProcess(cmd, 0 if captions else 1, stdout="", stderr=answer)
        return types.SimpleNamespace(run=run, TimeoutExpired=_sp.TimeoutExpired)

    try:
        os.chdir(root)
        warn = ("WARNING: [youtube] PFWARN00001: Unable to download webpage: HTTP Error 403: "
                "Forbidden (caused by a retry)\nWARNING: [youtube] PFWARN00001: Some web client "
                "subtitles require a PO Token which was not provided. They will be discarded\n")
        L.subprocess = fake(warn + "ERROR: [youtube] PFWARN00001: Private video. Sign in if "
                            "you've been granted access to this video")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            got = L.ask_track("PFWARN00001", "en", L.WORK, None, 30)
        assert got[0] == "gone", f"a warning changed how the answer was read: {got}"
        assert "--js-runtimes" in cmds[-1] and "node" in cmds[-1], cmds[-1]
        L.subprocess = fake(warn, captions=True)
        with contextlib.redirect_stdout(out):
            got = L.ask_track("PFWARN00002", "en", L.WORK, None, 30)
        assert got[0] == "captioned", got
        logs = list(Path("logs").glob("youtube-*.log"))
        assert len(logs) == 1, logs
        text = logs[0].read_text(encoding="utf-8")
        assert "PFWARN00001 en: gone" in text and "PO Token" in text and "Private video" in text \
            and "PFWARN00002 en: captioned" in text, text
        assert "WARNING" not in out.getvalue() and "PO Token" not in out.getvalue(), \
            "yt-dlp's warnings reached the step's output, which is the run's public page"
    finally:
        L.subprocess = real_sp
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)
    s = L.setup_said({"yt-dlp": "2026.8.19", "node": "", L.SOLVER: ""})
    assert "no node" in s, s
    s = L.setup_said({"yt-dlp": "2026.8.19", "node": "v24.0.0", L.SOLVER: ""})
    assert f"no {L.SOLVER}" in s, s
    return "ok", ("asks name node; a 403 and a token warning beside a private video read as gone, "
                  "a captioned ask with warnings as captioned; both in the day's log and neither "
                  "on the page; the setup line names a missing node or solver")


@check("livestreams", "a lock left by a killed step goes stale, and a New term run asks YouTube "
                      "for nothing", needs=("livestreams",))
def _ls_lock_and_new_term(livestreams):
    """The night's livestream step has a time limit of its own, and a step
    killed at it leaves archive/livestreams.lock behind. Held for two hours
    by its date alone, that lock failed the build's --markers step -- a
    failed step, which check_site will not publish. So a held lock is
    touched every LOCK_BEAT seconds and one untouched for LOCK_STALE is
    taken over, which is minutes, not the hours before --markers runs. And
    the New term run, the longest there is, lists what is new and asks for
    no captions: the workflow's NEW_TERM, which every step inherits."""
    import time as _t
    L = livestreams
    assert 10 * L.LOCK_BEAT <= L.LOCK_STALE <= 15 * 60, (L.LOCK_BEAT, L.LOCK_STALE)
    root = Path(tempfile.mkdtemp(prefix="gr-lslock-"))
    here, beat = os.getcwd(), L.LOCK_BEAT
    try:
        os.chdir(root)
        Path("archive").mkdir()
        L.LOCK.write_text("pid 1", encoding="utf-8")
        try:
            with L.lock():
                raise AssertionError("a fresh lock was taken over")
        except L.Broken:
            pass
        old = _t.time() - L.LOCK_STALE - 60
        os.utime(L.LOCK, (old, old))
        L.LOCK_BEAT = 0.05
        with L.lock():
            os.utime(L.LOCK, (old, old))
            _t.sleep(0.5)
            assert _t.time() - L.LOCK.stat().st_mtime < 5, "a held lock was not touched"
        assert not L.LOCK.exists(), "the lock was left behind"
    finally:
        L.LOCK_BEAT = beat
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)

    root = Path(tempfile.mkdtemp(prefix="gr-lsterm-"))
    try:
        _ls_fixture(root, L)
        r = _sealed_run([sys.executable, _paths.script("livestreams.py"),
                         "--since-state", "--replay", "api", "--captions-from", "src",
                         "--origin", "runner", "--now", "2026-09-25T06:30:00Z"],
                        cwd=str(root), env=dict(_ls_env(), NEW_TERM="true"),
                        capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stdout + r.stderr)[-400:]
        st = json.loads((root / "archive" / "livestreams.json").read_text(encoding="utf-8"))
        assert not (root / "work").exists(), "a New term run asked for captions"
        assert {v.get("captions") for v in st["videos"].values()
                if v.get("status") == "finished"} == {"waiting"}, st["videos"]
        assert "a New term run" in st["last_run"]["verdict"] and st["last_run"]["units"] == 6, \
            st["last_run"]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", (f"a fresh lock refuses, one untouched for {L.LOCK_STALE}s is taken over, a held "
                  "one is touched; a New term run lists at 6 units and asks for no captions")


@check("data", "the proceeding parser is not dropping scheduling rows")
def _dropped():
    if not (Path("Docket.txt").exists() and _paths.locate("docket_parser.py").exists()):
        return "skip", "Docket.txt or docket_parser.py not here"
    dp = imp("docket_parser")
    assert dp, "docket_parser.py will not import"
    rows = dp.parse_rows("Docket.txt")
    looks = [r for r in rows
             if "Hearing:" in r["desc"] or "Executive Session:" in r["desc"]
             or "Work Session:" in r["desc"]]
    procs = dp.parse_proceedings(rows, dp.build_referral_timeline(rows))
    ratio = len(procs) / max(len(looks), 1)
    assert ratio > 0.95, (f"{len(looks):,} rows look scheduled, {len(procs):,} "
                          f"parsed ({ratio:.0%}); the rest are dropped silently")
    return "ok", f"{len(looks):,} look scheduled, {len(procs):,} parsed ({ratio:.0%})"


@check("narrative", "a proceeding takes its own chamber's committee, never the other's",
       needs=("docket_parser",))
def _referral_chamber(docket_parser):
    """HB 115 of 2025, as the docket has it. The timeline was keyed by bill, so
    the Senate's referral on 27 March joined the House's, and the House's
    executive session of 1 April was filed under the Senate's Education
    committee -- which is H05 by name in the House, and kept a committee no
    longer on the General Court's list looking current."""
    dp = docket_parser
    rows = [
        {"lsr": "2025-0061", "created": "1/6/2025 8:30:15 AM", "bill": "HB115", "body": "H",
         "desc": "  Introduced 01/08/2025 and referred to Education Funding  HJ 2  P. 6",
         "updated": "", "lineno": 1},
        {"lsr": "2025-0061", "created": "3/26/2025 12:42:38 PM", "bill": "HB115", "body": "H",
         "desc": "Executive Session: 04/01/2025 10:00 am LOB 210-211", "updated": "", "lineno": 2},
        {"lsr": "2025-0061", "created": "4/11/2025 3:46:58 PM", "bill": "HB115", "body": "S",
         "desc": "  Introduced 03/27/2025 and Referred to Education;  SJ 10", "updated": "", "lineno": 3},
        # A Senate hearing on a bill whose Senate referral is missing borrows nothing.
        {"lsr": "2025-0999", "created": "4/1/2025 9:00:00 AM", "bill": "HB999", "body": "H",
         "desc": "  Introduced 01/08/2025 and referred to Housing  HJ 2  P. 6", "updated": "", "lineno": 4},
        {"lsr": "2025-0999", "created": "4/2/2025 9:00:00 AM", "bill": "HB999", "body": "S",
         "desc": "Hearing: 04/15/2025, Room 103, LOB, 09:30 am;  SC 5", "updated": "", "lineno": 5},
    ]
    # And 2015-2016's way of writing an introduction, with no date: 1,255 of
    # them were skipped, and 2,600 proceedings of that term had no committee.
    rows += [
        {"lsr": "2015-1030", "created": "02/18/2015 10:38:31 AM", "bill": "HB25", "body": "H",
         "desc": "Introduced and Referred to Public Works and Highways.", "updated": "", "lineno": 6},
        {"lsr": "2015-1030", "created": "03/05/2015 01:42:48 PM", "bill": "HB25", "body": "H",
         "desc": "Subcommittee Work Session: 3/13/2015 9:30 AM LOB 201", "updated": "", "lineno": 7},
    ]
    procs = {(p.bill, p.body): p.committee
             for p in dp.parse_proceedings(rows, dp.build_referral_timeline(rows))}
    assert procs.get(("HB115", "H")) == "Education Funding", procs
    assert procs.get(("HB999", "S")) is None, "a Senate hearing borrowed the House's committee"
    assert procs.get(("HB25", "H")) == "Public Works and Highways", \
        "an undated introduction was skipped: " + repr(procs.get(("HB25", "H")))
    n = dp.normalize_committee
    assert n("Commerce and Consumer Affairs (in recess of 3/12/2015)") == "Commerce and Consumer Affairs"
    assert n("Labor, Industrial and Rehabilitative Services (In Recess from 3/12/2015)") == \
        "Labor, Industrial and Rehabilitative Services"
    assert n("Health, Human Services & Elderly Affairs") == "Health, Human Services and Elderly Affairs"
    assert n("Special Committee on the Division for Children, Youth and Families (DCYF)").endswith("(DCYF)")
    return "ok", "own chamber's committee, undated introductions read, no borrowing"


@check("narrative", "a 1989-1998 hearing takes the name of the committee its own bill was referred to, and only that",
       needs=("docket_parser",))
def _legacy_written_out(docket_parser):
    """The hearing lines of 1989-1998 name their committee in whatever the clerk
    typed: HB 1247 of 1996, referred to JUDICIARY & F L, has hearings for
    JUDICIARY, JU and JUD, and one committee reached the record under a dozen
    names. Every line below is copied from Docket_db_<term>.txt, not typed.

    A written name becomes the bill's own referral committee in the same chamber
    where it shortens exactly one of them, and that referral is a committee
    with a page or a name referrals proved: JUD is Judiciary and Family Law for
    HB 1247 in the House and Judiciary for SB 487 in the Senate. What stays as
    the clerk wrote it: two letters (JU), a hearing the referrals already name
    exactly (HB 560's Finance), and a referral that is shorthand itself (SCR 1's
    ST-FED REL).
    """
    dp = docket_parser
    rows = []
    for lsr, created, bill, body, desc in (
            ("1996-2345", "01/03/1996 03:04:56 PM", "HB1247", "H", "INTRODUCED AND REF TO JUDICIARY & F L; HJ4,P128"),
            ("1996-2345", "01/08/1996 10:40:03 AM", "HB1247", "H", "//CANCELLED//HEARING JAN25 02:30 RM208,LOB    FOR: JUDICIARY"),
            ("1996-2345", "01/10/1996 03:49:44 PM", "HB1247", "H", "//CANCELLED//RESCHEDULED HEARING JAN19 11:00 RM208,LOB    FOR: JU"),
            ("1996-2345", "01/24/1996 10:41:04 AM", "HB1247", "H", "RESCHEDULED HEARING FEB16 02:00 RM208,LOB    FOR: JUD"),
            ("1995-0208", "01/05/1995 02:45:04 PM", "HB560", "H", "INTRODUCED AND REF TO HEALTH HS&EA; HJ11,P160"),
            ("1995-0208", "01/19/1995 03:09:55 PM", "HB560", "H", "HEARING FEB01 10:30 RM205,LOB    FOR: HEALTH"),
            ("1995-0208", "03/02/1995 04:57:59 PM", "HB560", "H", "COMM AM, AA VV; PASSED WITH AM AND REF TO FINANCE VV;HJ31,P779-80"),
            ("1995-0208", "03/02/1995 06:34:58 PM", "HB560", "H", "FIN HEARING MAR07 11:00 RM100,ST HOUSE    FOR: FINANCE"),
            ("1995-0766", "02/16/1995 06:07:59 PM", "SCR1", "H", "INTRODUCED AND REF TO ST-FED REL; HJ26,P565"),
            ("1995-0766", "03/30/1995 06:20:22 PM", "SCR1", "H", "<NOTE RM CHANGE>  HEARING APR07 10:30 RM104,LOB    FOR: ST-FED"),
            ("1998-2825", "01/07/1998 01:51:54 PM", "SB487", "S", "INTRODUCED AND REF TO JUDICIARY; SJ1,P15"),
            ("1998-2825", "01/22/1998 03:39:19 PM", "SB487", "S", "RESCHEDULED HEARING JAN28 10:45 RM103, ST HOUSE   FOR: JUD"),
            # The same bill in the House, whose referral line opens with a date.
            ("1998-2825", "03/31/1998 01:57:22 PM", "SB487", "H", "03/25/98  INTRODUCED AND REF TO JUDICIARY & F L; HJ34,P1460"),
            ("1998-2825", "03/31/1998 03:38:59 PM", "SB487", "H", "HEARING APR07 10:00 RM208,LOB    FOR: JUD"),
            ("1992-2557", "01/08/1992 10:52:37 AM", "SCR12", "S", "INTRODUCED AND REF TO INTERNAL AFFAIRS;  SJ 1,P 15"),
            ("1992-2557", "01/13/1992 04:01:23 PM", "SCR12", "S", "RESCHEDULED HEARING FEB06 11:00 RM102,LOB    FOR: INT AFFS")):
        rows.append({"lsr": lsr, "created": created, "bill": bill, "body": body, "desc": desc,
                     "updated": "", "lineno": len(rows)})
    saved = dp._TARGETS
    try:
        # The committees with a page, as data/committees.json names the ones
        # this needs, so the check does not depend on that file being here.
        dp._TARGETS = None
        proven = dp._written_targets()[0]
        dp._TARGETS = (proven, {("H", "judiciary"), ("S", "judiciary"), ("H", "finance"),
                                ("S", "internal affairs")})
        got = {(p.bill, p.sched_date): p.committee
               for p in dp.parse_proceedings(rows, dp.build_referral_timeline(rows))}
    finally:
        dp._TARGETS = saved
    want = {
        ("HB1247", "1996-01-25"): "Judiciary and Family Law",
        ("HB1247", "1996-01-19"): "Ju",
        ("HB1247", "1996-02-16"): "Judiciary and Family Law",
        ("HB560", "1995-02-01"): "Health, Human Services and Elderly Affairs",
        ("HB560", "1995-03-07"): "Finance",
        ("SCR1", "1995-04-07"): "St-Fed",
        ("SB487", "1998-01-28"): "Judiciary",
        ("SB487", "1998-04-07"): "Judiciary and Family Law",
        ("SCR12", "1992-02-06"): "Internal Affairs",
    }
    wrong = {k: (got.get(k, "missing"), v) for k, v in want.items() if got.get(k, "missing") != v}
    assert not wrong, "got, wanted: " + repr(wrong)
    return "ok", ("JUD written out by its own bill's chamber and referral; JU, a name the referrals "
                  "already give, and a shorthand referral left as the clerk wrote them")


@check("narrative", "a proceeding after a second referral takes the second committee",
       needs=("docket_parser",))
def _second_referral(docket_parser):
    """HB 115 of 2025 again, with the row the timeline did not read. The House
    passed it on 13 March and referred it to Finance; its executive session of
    1 April, in LOB 210-211, is Finance's, and was filed under Education
    Funding because only introductions and vacates reached the timeline --
    2,040 proceedings across six terms, nearly all Finance or Ways and Means."""
    dp = docket_parser

    def row(bill, body, created, desc):
        return {"lsr": "2025-0061", "created": created, "bill": bill, "body": body,
                "desc": desc, "updated": "", "lineno": 0}

    rows = [
        # HB 115's House rows as the docket has them.
        row("HB115", "H", "1/6/2025 8:30:15 AM",
            "  Introduced 01/08/2025 and referred to Education Funding  HJ 2  P. 6"),
        row("HB115", "H", "2/27/2025 2:37:03 PM",
            "Executive Session: 03/05/2025 11:00 am LOB 205-207"),
        row("HB115", "H", "3/13/2025 12:00:44 PM",
            "Referred to Finance 03/13/2025  HJ 8  P. 44"),
        row("HB115", "H", "3/26/2025 12:42:38 PM",
            "Executive Session: 04/01/2025 10:00 am LOB 210-211"),
        # The Senate's later referral stays in the Senate, and is written with
        # a comma before its date (HB 123's line of 15 May 2025).
        row("HB123", "S", "3/27/2025 1:00:00 PM",
            "  Introduced 03/27/2025 and Referred to Education;  SJ 10"),
        row("HB123", "S", "4/15/2025 1:52:27 PM",
            "Hearing: 04/22/2025, Room 101, LOB, 10:15 am;  SC 18"),
        row("HB123", "S", "5/15/2025 1:00:00 PM",
            "Referred to Ways and Means, 05/15/2025;  SJ 13"),
        row("HB123", "S", "5/16/2025 1:00:00 PM",
            "Hearing: 05/20/2025, Room 103, SH, 09:00 am;  SC 20"),
        # Lines that mention a referral and are not one, each as the docket
        # writes it: "Rereferred to Committee" sends a bill back to the
        # committee it came from; a report recommending interim study and a
        # chair's waiver name no new committee.
        row("HB999", "S", "1/2/2025 9:00:00 AM",
            "  Introduced 01/02/2025 and Referred to Judiciary;  SJ 1"),
        row("HB999", "S", "2/13/2025 9:00:00 AM",
            "Rereferred to Committee, MA, VV; 02/13/2025; SJ 5"),
        row("HB999", "S", "2/14/2025 9:00:00 AM",
            "Committee Report: Referred to Interim Study, 02/14/2025; Vote 5-0; CC; SC 46"),
        row("HB999", "S", "2/20/2025 9:00:00 AM",
            "Hearing: 02/25/2025, Room 100, SH, 09:00 am;  SC 9"),
        row("HB998", "H", "1/2/2025 9:00:00 AM",
            "  Introduced 01/08/2025 and referred to Transportation  HJ 2  P. 6"),
        row("HB998", "H", "2/6/2025 9:00:00 AM",
            "Referral Waived by Committee Chair per House Rule 47(f) 02/06/2025  HJ 4  P. 31"),
        row("HB998", "H", "2/10/2025 9:00:00 AM",
            "Committee Report: Refer for Interim Study 02/10/2025 (Vote 15-0; CC)  HC 10  P. 14"),
        row("HB998", "H", "2/12/2025 9:00:00 AM",
            "Executive Session: 02/18/2025 10:00 am LOB 203"),
        # 2015-2016 writes the line with no date; the row's own stands in
        # (HB 616's, 18 February 2015). The sessions are invented around it.
        row("HB616", "H", "01/08/2015 09:58:49 AM",
            "Introduced and Referred to Judiciary; HJ 12, PG. 232"),
        row("HB616", "H", "02/18/2015 11:41:34 AM", "Referred to Finance"),
        row("HB616", "H", "02/05/2015 10:57:35 AM",
            "Executive Session: 2/12/2015 9:00 AM LOB 208"),
        row("HB616", "H", "02/20/2015 11:41:34 AM",
            "Executive Session: 3/3/2015 10:00 AM LOB 210-211"),
        # HB 1288 of 2022 has no House introduction row. A day before its
        # referral to Ways and Means is not Ways and Means's.
        row("HB1288", "H", "1/24/2022 12:00:00 AM",
            "Public Hearing: 01/24/2022 01:45 pm LOB 302-304"),
        row("HB1288", "H", "2/17/2022 12:00:00 AM",
            "Referred to Ways and Means 02/16/2022"),
        row("HB1288", "H", "3/14/2022 12:00:00 AM",
            "Full Committee Work Session: 03/18/2022 10:00 am LOB 202-204"),
    ]
    got = {(p.bill, p.body, p.sched_date): p.committee
           for p in dp.parse_proceedings(rows, dp.build_referral_timeline(rows))}
    want = {
        ("HB115", "H", "2025-03-05"): "Education Funding",
        ("HB115", "H", "2025-04-01"): "Finance",
        ("HB123", "S", "2025-04-22"): "Education",
        ("HB123", "S", "2025-05-20"): "Ways and Means",
        ("HB999", "S", "2025-02-25"): "Judiciary",
        ("HB998", "H", "2025-02-18"): "Transportation",
        ("HB616", "H", "2015-02-12"): "Judiciary",
        ("HB616", "H", "2015-03-03"): "Finance",
        ("HB1288", "H", "2022-01-24"): None,
        ("HB1288", "H", "2022-03-18"): "Ways and Means",
    }
    wrong = {k: (got.get(k, "missing"), v) for k, v in want.items() if got.get(k, "missing") != v}
    assert not wrong, "got, wanted: " + repr(wrong)
    return "ok", "Finance after 13 March, not before; waivers, interim study and 'Committee' add nothing"


@check("narrative", "a House conference notice is read with its time and room, in every wording the House has used",
       needs=("docket_parser",))
def _house_conference_notice(docket_parser):
    """HB 485's conference of 16 June 2025, as the House docket notices it:
    "Conference Committee Meeting: 06/16/2025 09:30 am LOB 206-208".

    HOUSE_SCHED_RE knew only the bare "Committee of Conference", which the
    House clerk never writes before a date, so not one House conference
    notice written with a clock time reached proceedings.csv -- 113 in the
    current term's docket, 927 across eleven terms -- while the Senate's
    "Committee of Conference Meeting: 06/16/2025, 12:00 pm, Room 100, SH"
    did. Every House conference card on the Calendar was its recording
    alone: untimed, with no room. Every line below is copied from a docket
    on this disk, not typed, and so are the ones that must stay unread.
    """
    dp = docket_parser

    def row(bill, created, desc, body="H"):
        return {"lsr": "2025-0741", "created": created, "bill": bill, "body": body,
                "desc": desc, "updated": "", "lineno": 0}
    rows = [
        row("HB485", "6/16/2025 12:00:00 AM",
            "Conference Committee Meeting: 06/16/2025 09:30 am LOB 206-208"),
        row("HB1", "6/12/2025 12:00:00 AM",
            "Conference Committee Meeting: 06/12/2025 02:00 pm LOB 210-211"),
        row("HB26", "6/8/2011 12:00:00 AM",
            "Conference Committee Meeting: 6/8/2011 9:00 AM LOB 307  ==RECESSED=="),
        row("HB37", "06/14/2007 02:56:52 PM",
            "Committee of Conference Meeting: 6/18/07 2:00 PM LOB 207"),
        row("HB653", "06/21/2007 08:17:24 AM",
            "Committee of Conference Meeting==RECONVENE==: 6/21/07 9:30 AM LOB 306"),
        row("HB1488", "05/23/2014 02:08:10 PM",
            "Conference of Committee Meeting: 5/27/2014; 11:00 AM; LOB 207"),
        row("HB1405", "05/23/2008 04:05:27 PM",
            "Committee of Conference Hearing: 05/29/2008 11:30 AM LOB 304"),
        row("HB170", "06/15/2001 11:12:13 AM",
            "Conf Comm meeting 6/15/01 1:30 p.m. Rm 202, LOB"),
        row("HB144", "6/12/2017 12:00:00 AM",
            "==CANCELLED== Conference Committee Meeting: 06/13/2017 10:00 AM LOB 210-211"),
        # A conference named and no conference noticed: a report, a change of
        # conferee, an accession. None of these is a sitting.
        row("HB485", "6/26/2025 2:09:16 PM",
            "Conference Committee Report 2025-2766c: Adopted, VV 06/26/2025  HJ 18  P. 18"),
        row("HB67", "6/16/2025 10:34:27 AM",
            "Conferee Change: Rep. Wood Replaces Rep. Lane 06/16/2025  HJ 17  P. 24"),
        row("SB32", "06/09/2015 02:00:34 PM",
            "House Accedes to Senate Request for Committee of Conference (Rep Hinch): MA VV "
            "(in recess of 6/3/2015); HJ 44, PG. 1953"),
        # And the Senate's, which was always read, still is.
        row("SB14", "6/11/2025 3:39:13 PM",
            "Committee of Conference Meeting: 06/16/2025, 12:00 pm, Room 100, SH", body="S"),
    ]
    got = {}
    for p in dp.parse_proceedings(rows, dp.build_referral_timeline(rows)):
        got[(p.bill, p.sched_date)] = (p.kind, p.sched_time, p.venue,
                                       "CANCELLED" in [str(f).upper() for f in p.flags])
    C = "committee of conference"
    want = {
        ("HB485", "2025-06-16"): (C, "09:30", "LOB 206-208", False),
        ("HB1", "2025-06-12"): (C, "14:00", "LOB 210-211", False),
        ("HB26", "2011-06-08"): (C, "09:00", "LOB 307", False),
        ("HB37", "2007-06-18"): (C, "14:00", "LOB 207", False),
        ("HB653", "2007-06-21"): (C, "09:30", "LOB 306", False),
        ("HB1488", "2014-05-27"): (C, "11:00", "LOB 207", False),
        ("HB1405", "2008-05-29"): (C, "11:30", "LOB 304", False),
        ("HB170", "2001-06-15"): (C, "13:30", "Rm 202, LOB", False),
        ("HB144", "2017-06-13"): (C, "10:00", "LOB 210-211", True),
        ("SB14", "2025-06-16"): (C, "12:00", "SH 100", False),
    }
    wrong = {k: (got.get(k, "missing"), v) for k, v in want.items() if got.get(k) != v}
    assert not wrong, "got, wanted: " + repr(wrong)
    extra = sorted(set(got) - set(want))
    assert not extra, f"a line that notices no conference was read as one: {extra}"
    return "ok", ("HB 485's conference of 16 June 2025 at 09:30 in LOB 206-208, and the "
                  "House's five other wordings of 2001-2014; reports, conferee changes and "
                  "accessions stay unread")


@check("narrative", "a Senate hearing report is read speaker by speaker, word for word",
       needs=("senate_hearing_reports",))
def _senate_hearing_reports(senate_hearing_reports):
    """Four real reports, names and all, because they are the Senate's record.

    The person decided on 24 September that these are shown as the Senate
    published them. So the check is not only that speakers come out, but that
    every point is a line of the report itself, and that each sits under the
    person the report put it under -- including the two layouts that put words
    in the wrong mouth if read naively: SB 11 types a second witness as a
    bullet under the first ("Ken Barnes, Contoocook" under Liz Tentarelli),
    and SB 14 writes each heading on two lines, which read as two people gave
    the first a speaker with nothing under it and the second the first one's
    points -- 464 of them across the table. SB 160 is prose, with nobody's
    name on a line of its own, and must be kept as prose, not guessed at.
    """
    S = senate_hearing_reports
    if not Path("tests/senate_hearing_reports.json").exists():
        return "skip", "tests/senate_hearing_reports.json not here"
    got = _hearing_fixture(S)
    sb4, bl4 = got["SB4"]
    assert (sb4["committee"], sb4["heard"], sb4["opened"], sb4["closed"]) == (
        "Senate Commerce Committee", "2025-01-09", "1:34 p.m.", "1:48 p.m."), (
        "SB 4's header: " + json.dumps([sb4["committee"], sb4["heard"],
                                         sb4["opened"], sb4["closed"]]))
    assert sb4["present"].startswith("Senators Innis, Ricciardi"), sb4["present"]
    assert [p[0] for p in sb4["positions"]] == [
        "Who supports the bill", "Who opposes the bill",
        "Who is neutral on the bill"], sb4["positions"]
    sup = sb4["sections"][0]
    assert sup["side"] == "support", sup["side"]
    assert [sp["who"] for sp in sup["speakers"]] == [
        "Senator Daniel Innis", "Steve Duprey",
        "James Key-Wallace, Executive Director, New Hampshire Business "
        "Finance Authority",
        "Sam Evans-Brown, Executive Director, Clean Energy NH"], (
        [sp["who"] for sp in sup["speakers"]])
    # A senator's question to a witness stays under that witness, and the
    # answer stays nested under the question.
    q = [p for p in sup["speakers"][2]["points"] if isinstance(p, dict)]
    assert q and q[0]["t"].startswith("Senator Innis asked") and \
        q[0]["sub"][0].startswith("Director Key-Wallace said"), q
    assert sb4["sections"][1].get("note") == "None", sb4["sections"][1]

    # WORD FOR WORD: every point is a whole line of the report, in order.
    def flat(bl):
        out = []

        def items(its):
            for it in its:
                out.append(it["t"])
                items(it["sub"])
        for k, v in bl:
            (out.append(v) if k == "p" else items(v))
        return out

    def points(pts, acc):
        for p in pts:
            acc.append(p if isinstance(p, str) else p["t"])
            if isinstance(p, dict):
                points(p.get("sub", []), acc)
        return acc
    n = 0
    for b, (rec, bl) in got.items():
        raw, at = flat(bl), -1
        for s in rec["sections"]:
            for sp in s.get("speakers", []):
                for t in points(sp["points"], []):
                    nxt = next((j for j in range(at + 1, len(raw))
                                if raw[j] == t), None)
                    assert nxt is not None, (
                        f"{b}: a point is not a line of the report, or is out "
                        f"of order: {t[:70]!r}")
                    at, n = nxt, n + 1

    sb11 = got["SB11"][0]
    opp = sb11["sections"][1]["speakers"]
    assert [sp["who"] for sp in opp] == [
        "Liz Tentarelli, League of Women Voters N.H.", "Ken Barnes, Contoocook",
        "Representative Alvin See, Merrimack 26"], [sp["who"] for sp in opp]
    assert opp[1]["points"][0].startswith("Doesn") and \
        not any(str(p).startswith("Doesn") for p in opp[0]["points"]), (
        "Ken Barnes's points were left under Liz Tentarelli")
    # The committee's questions to the sponsor, written as paragraphs with
    # the answers indented under them, stay the sponsor's, question over
    # answer.
    gan = sb11["sections"][0]["speakers"]
    assert len(gan) == 1 and gan[0]["who"] == "Senator Gannon, Prime Sponsor", (
        [sp["who"] for sp in gan])
    qa = [p for p in gan[0]["points"] if isinstance(p, dict)]
    assert len(qa) == 6 and qa[0]["t"].startswith("Senator Perkins Kwoka asked") \
        and qa[0]["sub"][0].startswith("Senator Gannon said"), qa[:1]

    sb14 = got["SB14"][0]
    heads = [(sp["who"], sp.get("also")) for sp in
             sb14["sections"][0]["speakers"]]
    assert heads[0] == ("Senator Bill Gannon", ["Senate District 23"]), heads[0]
    assert all(sp["points"] for s in sb14["sections"]
               for sp in s.get("speakers", [])), (
        "a speaker heading's second line was read as a speaker of its own")

    sb160 = got["SB160"][0]
    assert sb160.get("fallback"), "SB 160 is prose and was split into speakers"
    assert all("speakers" not in s and s.get("text") is not None
               for s in sb160["sections"]), sb160["sections"]
    assert any("Sen. Lang explained" in str(x) for s in sb160["sections"]
               for x in s["text"]), "SB 160's text did not come through"

    # A WITNESS'S HEADING THE NAME TEST DID NOT KNOW. Filed as the speaker
    # above's point, it took that witness's whole testimony, nested under it,
    # into the wrong mouth -- 13 witnesses in 11 reports, three under a
    # legislator's chip. HB 666 heads one with initials short of their last
    # full stop; HB 277 runs a name into its organisation with no comma, and
    # the report's own list of supporters names him.
    hb666 = got["HB666"][0]
    spk = hb666["sections"][0].get("speakers") or []
    assert [sp["who"] for sp in spk] == [
        "Representative Lisa Mazur", "Representative Henry Giasson",
        "D.J Withee", "Representative Timothy Horrigan",
        "Representative Kelley Potenza"], [sp["who"] for sp in spk]
    assert spk[2].get("also") == ["Attorney - Windham, New Hampshire"] and \
        spk[2]["points"][0].startswith("Mr. Withee testified in his "
                                       "individual capacity"), spk[2]
    assert not any((p if isinstance(p, str) else p["t"]).startswith(
        ("D.J", "Attorney", "Mr. Withee")) for p in spk[1]["points"]), (
        "D.J Withee's testimony was left under Rep. Giasson")
    hb277 = got["HB277"][0]
    spk = hb277["sections"][0].get("speakers") or []
    assert [sp["who"] for sp in spk] == [
        "Representative Peter Bixby", "Representative Judy Aron",
        "Robert Johnson II New Hampshire Farm Bureau"], (
        [sp["who"] for sp in spk])
    assert len(spk[1]["points"]) == 3 and \
        spk[2]["points"][0].startswith("Mr. Johnson stated"), spk[1:]
    # And where the lists do not name the person, the report is not guessed
    # at. SB 459's own lines: "Pasha Roberts 603 Equality" is on no list of
    # SB 459's, which gives counts only.
    blocks459 = [
        ("p", "Aimee Terravechia, 603 Equality"),
        ("ul", [{"t": "Ms. Terravechia spoke about her experience in sports.",
                 "sub": []}]),
        ("p", "Pasha Roberts 603 Equality"),
        ("ul", [{"t": "Ms. Roberts explained that the governor had previously "
                      "vetoed similar bills.", "sub": []}])]
    spk, _n, why = S.split_speakers(
        blocks459, "660 people signed up in opposition to this bill.")
    assert not spk and "heading" in why, (
        f"an unlisted heading was filed as a point: {why!r}")
    spk, _n, why = S.split_speakers(
        blocks459, "aimee terravechia (603 equality), pasha roberts "
                   "(603 equality)")
    assert not why and [sp["who"] for sp in spk] == [
        "Aimee Terravechia, 603 Equality", "Pasha Roberts 603 Equality"], (
        why, [sp["who"] for sp in spk])
    # The completed date with the aide's initials run on to it was a point.
    for line, day in (
            ("VH Senate Hearing Report completed: January 31, 2025",
             "2025-01-31"),
            ("jab/Date Hearing Report completed: March 27, 2025",
             "2025-03-27"),
            ("V.H Date Hearing Report completed: January 23, 2026",
             "2026-01-23")):
        m = S.COMPLETED.match(line)
        assert m and S.iso(m.group(1)) == day, line

    # A POSITION LIST KEEPS THE SENATE'S COUNT and drops the instruction
    # telling readers which member of staff to email. The count and the
    # instruction often share a sentence; cutting by sentence took the count
    # too, and eight reports showed a support count and no opposition row.
    # The strings are the table's own.
    for raw, kept in (
            ("8 Individuals signed in Support of this legislation. Please "
             "contact Joshua.Schauer@gc.nh.gov for more information.",
             "8 Individuals signed in Support of this legislation."),
            ("84 signed in opposition to HB 666-FN, contact "
             "peter.mulvey@gc.nh.gov for further details.",
             "84 signed in opposition to HB 666-FN"),
            ("174 individuals were in opposition.Full sign in sheets are "
             "available upon request by contacting the Legislative Aide, "
             "Jessica Bourque (jessica.bourque@gc.nh.gov).",
             "174 individuals were in opposition."),
            ("54 people signed in opposition, for a complete list of those "
             "who signed please email brendan.bunnell@gc.nh.gov.",
             "54 people signed in opposition"),
            ("11 individuals signed in opposition to HB 75-FN Contact Pete "
             "Mulvey (peter.mulvey@gc.nh.gov) for further details.",
             "11 individuals signed in opposition to HB 75-FN"),
            ("1 Person signed in neutrality to?SB 96. ?To see the full list "
             "of sign-ins, please email the committee aide "
             "(ryan.meleedy@gc.nh.gov).",
             "1 Person signed in neutrality to?SB 96."),
            ("In total, 76 individuals signed-in in support of SB 36. The "
             "full sign in sheets are available upon request to the "
             "Legislative Aide, Sophie Walsh (sophie.walsh@gc.nh.gov).",
             "In total, 76 individuals signed-in in support of SB 36."),
            # Nothing but the instruction: the Senate's sentence stays, so
            # the row still says that people took that side.
            ("Please contact the Senate Finance Committee Aide for a "
             "complete list of those opposed to SB297. "
             "(Debra.Martone@gc.nh.gov)",
             "Please contact the Senate Finance Committee Aide for a "
             "complete list of those opposed to SB297.")):
        assert S._clean_position(raw) == kept, (
            f"{raw[:50]!r} became {S._clean_position(raw)!r}")
    assert hb666["positions"][1] == [
        "Who opposes the bill", "84 signed in opposition to HB 666-FN"], (
        hb666["positions"])
    # HB 2 breaks the instruction over two paragraphs; cleaned apart, the
    # first half stood as the list.
    rec2, _d = S.parse_document([
        ("p", "Senate Finance Committee"),
        ("p", "Hearing Date: May 6, 2025"),
        ("p", "Who supports the bill: Please contact the Senate Finance "
              "Committee Legislative"),
        ("p", "Aide (Debra.Martone@gc.nh.gov) for a complete sign-in list."),
        ("p", "Summary of testimony presented:")])
    assert rec2["positions"] == [[
        "Who supports the bill", "Please contact the Senate Finance "
        "Committee Legislative Aide for a complete sign-in list."]], (
        rec2["positions"])
    assert sb14["positions"][1] == [
        "Who opposes the bill",
        "63 individuals signed in opposition to SB 14-FN."], sb14["positions"]
    assert "@" not in json.dumps([r for r, _bl in got.values()]), (
        "a staff address reached the parsed record")
    # A sentence is never a speaker.
    for line in ("Senator Perkins Kwoka asked whether the motivation is to "
                 "protect voters or is it political.",
                 "Senator Watters detailed the changes:",
                 "Ultimately, everyone operates under the same rules.",
                 "HB 51"):
        assert not S.is_name_line(line), f"read as a speaker: {line!r}"
    return "ok", (f"6 real reports: {n} points, each a line of the report in "
                  "its order; a mis-indented witness, two-line headings, "
                  "headings the name test missed, counts beside the aide's "
                  "address and a prose report each handled")


@check("narrative", "a bill's hearing and an amendment heard after it are two "
       "reports, and a re-filing is one", needs=("senate_hearing_reports",))
def _hearing_report_keys(senate_hearing_reports):
    """One report per hearing, and a hearing is its date, what was heard and
    when it opened -- not the date alone.

    Seven bills were heard and then had an amendment heard the same
    afternoon, each reported separately and sometimes in one row (HB 381 at
    1:26 and its amendment at 1:51). Keyed on the date alone, the bill's own
    report was thrown away. The table also holds the same hearing filed
    twice, and the later filing is the one kept. The layout here is the
    reports' own, cut to one witness each; nothing checked depends on the
    words. A House row of the same type is a committee report and is left
    out.
    """
    S = senate_hearing_reports

    def doc(subject, opened, who):
        return ("<p>Senate Finance Committee</p>"
                f"<p>{subject}</p><p>Hearing Date: April 1, 2025</p>"
                f"<p>Time Opened: {opened} Time Closed: 2:10 p.m.</p>"
                f"<p>Who supports the bill: {who}</p>"
                "<p>Summary of testimony presented in support:</p>"
                f"<p>{who}</p><ul><li>Spoke to the bill.</li></ul>"
                "<p>Date Hearing Report completed: April 2, 2025</p>")
    bill = doc("HB 381-FN, relative to the state budget.", "1:26 p.m.",
               "Senator Jane Roe")
    amd = doc("AMENDMENT # 2025-1481s, to HB 381-FN, relative to the state "
              "budget.", "1:51 p.m.", "Senator John Doe")

    def row(stamp, chamber, html):
        return "|".join(["1", stamp, "Hearing Report", "", chamber,
                         f"<body>{html}</body>", "HB 381", ""])
    root = Path(tempfile.mkdtemp())
    try:
        src = root / "CandH_Reports.psv"
        src.write_text("\n".join([
            row("04/02/2025 09:00:00", "S", bill + amd),
            row("04/03/2025 09:00:00", "S", bill),       # filed again
            row("04/02/2025 09:00:00", "H", bill)]) + "\n", encoding="utf-8")
        out, c = S.parse_all(src)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert c["rows"] == 2, f"{c['rows']} rows read; the House row is not one"
    recs = out.get(S.P.term_of("2025-04-01"), {}).get("HB381", [])
    assert [r["opened"] for r in recs] == ["1:26 p.m.", "1:51 p.m."], (
        "the bill's hearing and its amendment's were not kept apart: "
        + json.dumps([[r["opened"], r["subject"][:20]] for r in recs]))
    assert recs[1]["subject"].startswith("AMENDMENT"), recs[1]["subject"]
    assert c["duplicates"] == 1 and recs[0]["filed"] == "2025-04-03", (
        f"the re-filing was not folded to the later one: {c['duplicates']}, "
        f"{recs[0]['filed']}")
    return "ok", "the bill and its amendment apart, the later filing kept"


@check("narrative", "a vacated referral names the committee the bill went TO",
       needs=("referrals",))
def _vacated(referrals):
    """Every string below is a real description from db/Docket.psv.

    A vacate undoes the referral before it: "VACATED FROM JUDICIARY TO BANKS"
    means the chamber took the bill away from Judiciary and gave it to Banks.
    398 lines say so across 1989-2015 and none of the three referral patterns
    matched any of them, so until 17 September the site published, for those
    bills, the committee the chamber had explicitly taken the bill away from.

    THE FIVE WAYS THIS GOES WRONG, each measured in the corpus and each one
    line of the test below:

    1. "Vacate Referral to Ways & Means" means Ways and Means is the committee
       being LEFT. A pattern that takes the committee after "to" gets exactly
       the wrong answer. One line in the corpus is this shape -- few enough to
       pass a spot check, quite enough to put a wrong committee on a page --
       and it is refused rather than guessed.
    2. "VACATE FROM FINANCE TO 2ND READING" has no destination committee at
       all: the bill left committee for the chamber's calendar. Two lines.
    3. "VACATED TO JUDICIARY, REP POWERS MA VV" names the member who moved it,
       which is house style on a vacate and would have published about forty
       committees called things like "Judiciary, Rep Powers".
    4. "to Finance, MA. VV" -- the clerk separates the vote tokens with a full
       stop as often as with a comma, and a separator class that allowed only
       spaces and commas stripped just the last one, leaving "Finance, MA".
    5. "MOVED TO VACATE TO HEALTH, ML RC(167-178)" is a vacate the House voted
       DOWN (1995 HB54). Read as one, it published "Health, Ml".

    And the case that must NOT be broken by any of the above: a committee
    whose own name contains a comma. "Public Institutions, Health & Human
    Services" survives, because what follows its comma is not an honorific.
    """
    ok = [
        ("VACATED TO JUDICIARY, REP POWERS MA VV; HJ63, P1877", "Judiciary"),
        ("VACATED FROM JUDICIARY INTRODUCED TO BANKS", "Banks"),
        ("VACATE TO MUN & CTY GOVT; REP. SYTEK MA; HJ17, P211",
         "Municipal and County Government"),
        ("Vacate From Environment to Public Institutions, Health & Human "
         "Services; SJ 7, Pg.224",
         "Public Institutions, Health and Human Services"),
        ("Sen. D'Allesandro Vacate from Internal Affairs to Finance, MA. VV; "
         "SJ 10, Pg.292", "Finance"),
        ("Sen. D'Allesandro Moved to Vacate SB63 to Energy & Economic "
         "Development, MA, VV; SJ 4, Pg.43", "Energy and Economic Development"),
    ]
    for desc, want in ok:
        got = referrals.vacated(desc)
        assert got == want, f"vacated({desc[:46]!r}) gave {got!r}, wanted {want!r}"

    refuse = [
        ("Rep. Almy: Vacate Referral to Ways & Means, MA VV; HJ 20, pg.407",
         "the committee named is the one being LEFT"),
        ("MOTION TO VACATE FROM FINANCE TO 2ND READING",
         "second reading is the chamber's calendar, not a committee"),
        ("Vacated from Ways and Means; HJ 19, pg.390",
         "no destination on this row (_read_docket reads the next one)"),
        ("REP HAETTENSCHWILLER MOVED TO VACATE TO HEALTH, ML RC(167-178);",
         "the motion lost (ML), so Finance kept the bill"),
    ]
    for desc, why in refuse:
        got = referrals.vacated(desc)
        assert got == "", (
            f"vacated({desc[:46]!r}) gave {got!r} and should have refused: {why}")

    # An ordinary referral is not a vacate, and must not be read as one.
    assert referrals.vacated(
        "Introduced 1/4/2012 and Referred to Judiciary; HJ 11, PG. 183") == ""
    return "ok", (f"{len(ok)} vacate shapes read, {len(refuse)} refused "
                  "including the one that names the committee being left")


@check("narrative", "the committee of referral is read out of a docket line",
       needs=("referrals",))
def _referral(referrals):
    """Every string below is a real description from db/Docket.psv.

    Five terms had no committee at all until the docket was read for one --
    8,525 bills whose page named no committee -- so this is the parser that
    put a committee on a quarter of the archive, and the shapes it has to
    survive span 1989 to 2015 and four clerks' habits.
    """
    c = referrals.committee
    assert c("INTRODUCED AND REF TO EXEC & ADMIN     HJ 13 ,P 138") == \
        "Executive Departments and Administration"
    assert c("Introduced 1/4/2012 and Referred to Judiciary; HJ 11, PG. 183") == \
        "Judiciary"
    assert c("PASSED AND REF TO FINANCE VV; HJ35,P943") == "Finance"
    assert c("RE-REFERRED TO ENV & AGRIC VV; HJ53B,P1179") == \
        "Environment and Agriculture"
    assert c("Introduced and ref to Labor, Industrial and Rehabilitative "
             "Services   HJ 7, pg 341") == "Labor, Industrial and Rehabilitative Services"
    # A disposition, not a committee. "Refer to Interim Study" is what a
    # committee RECOMMENDS; reading it as a referral would invent a committee
    # of that name for 434 bills.
    assert c("Committee Report: Refer to Interim Study") == ""
    # "Rereferred to Committee" is back to the one it is already in.
    assert c("Rereferred to Committee, MA, VV; SJ 20, P 543") == ""
    # The shout is unshouted before the ampersand is spelled, or the
    # lower-case "and" drops it below the 90% that triggers unshouting.
    assert c("INTRODUCED AND REF TO WAYS & MEANS") == "Ways and Means"
    # This line once asserted "Judiciary and F L", which was the right answer
    # while it was: nothing in the docket or in any bill's text spelled that
    # committee out, and a plausible expansion of a committee's name is still
    # an invented one. Then the General Court's own key to its docket turned up
    # -- docket_abbrev.json -- and JUD is Judiciary and Family Law. The
    # expectation moved because the evidence did, and the rule that produced
    # the cautious answer is unchanged.
    assert c("INTRODUCED AND REF TO JUDICIARY & F L") == "Judiciary and Family Law"
    # And this one moved a third time, on the same rule. The key does not cover
    # "CORR & CJ" either, so it stood as the clerk's letters on 152 pages --
    # until a fourth witness was read: the resolution each House adopts its
    # rules by defines every standing committee in one sentence, and
    # legislation/1995/HR0001.html names "the Committee on Corrections and
    # Criminal Justice". referrals._rules_names reads those, --check counts
    # them as evidence like any other source, and the same witness settled
    # "Pub Prot" (104 pages).
    #
    # The pattern is the resolution's grammar rather than a name this project
    # hoped to find, which is what makes it evidence: it turned up 22
    # committees, most of which nothing here had asked about.
    assert c("INTRODUCED AND REF TO CORR & CJ") == "Corrections and Criminal Justice"
    assert c("INTRODUCED AND REF TO PUB PROT") == \
        "Public Protection and Veterans Affairs"
    # Still abbreviated: two referrals, and the two candidates on this disk
    # are different committees, so there is nothing to choose between them.
    assert c("INTRODUCED AND REF TO PUB INSTIT") == "Pub Instit"
    # The hearing line's shorthand (13 September). SB 143 of 1993 is referred
    # to "EXEC DEPTS+ADMIN" and heard "FOR: ED+A"; until then its hearing sat
    # under a committee called "Ed and a". Anchored: the letters are only a
    # committee when they are the whole name, and a key entry right for one
    # era only (PUBLIC WKS) is deliberately absent.
    e = referrals.expand
    assert c("INTRODUCED AND REF TO EXEC DEPTS+ADMIN; SJ2,P30") == \
        "Executive Departments and Administration"
    assert e("ED+A") == e("ED&A") == "Executive Departments and Administration"
    assert e("E&A") == "Environment and Agriculture"
    assert e("RR&D") == "Resources, Recreation and Development"
    assert e("M&CG") == "Municipal and County Government"
    assert e("LABOR") == "Labor, Industrial and Rehabilitative Services"
    assert e("E&A + RR&D") == "E&A + RR&D", "a joint hearing is two committees, not one"
    assert e("EDUC") == "Education" and e("W&M") == "Ways and Means"
    assert e("ENV & AGR") == e("ENV&AG") == "Environment and Agriculture"
    # Chamber-dependent, and this function is not told the chamber.
    assert e("JUD") == "JUD" and e("WILDLIFE") == "WILDLIFE"
    assert e("PUB INSTIT") == "PUB INSTIT"
    assert e("ST-FED") == "ST-FED" and e("PUBLIC WKS") == "PUBLIC WKS"
    # A longer name is not the shorter one inside it (23 September). The
    # Internal Affairs pattern found those two words inside two Senate
    # committees' names and returned "Internal Affairs" for both, on 38 cards
    # of 2007-2016; "REG REV" did the same to Local and Regulated Revenues.
    # 2007 SB234, 2015 SCR1, 2005 SB40, 1997 HB776 and 1989 HB172, verbatim.
    assert c("Introduced and Referred to Election Law and Internal Affairs; "
             "SJ 3, Pg.51") == "Election Law and Internal Affairs"
    assert c("Introduced and Referred to Rules, Enrolled Bills and Internal "
             "Affairs by the necessary 2/3 vote, Pursuant to Senate Rule 3-26; "
             "SJ 4") == "Rules, Enrolled Bills and Internal Affairs"
    assert c("Introduced and Referred to Internal Affairs; SJ 2, Pg.24") == \
        "Internal Affairs"
    assert c("INTRODUCED AND REF TO LOCAL & REG REV; HJ17, P284") == \
        "Local and Regulated Revenues"
    assert c("INTRODUCED AND REF TO REG REV          HJ 13 ,P 138") == \
        "Regulated Revenues"
    return "ok", ("fifteen real docket lines, the hearing shorthand, and two "
                  "that name no committee")


def _swallowed(referrals, names_):
    """The full names that expand() turns into a different committee."""
    return sorted(f"{n!r} -> {referrals.expand(n)!r}" for n in set(names_)
                  if referrals._key(referrals.expand(n)) != referrals._key(n))


@check("narrative", "expand() never turns a committee's full name into a different committee",
       needs=("referrals",))
def _full_names_survive(referrals):
    """A pattern for a short name must not fire inside a longer one.

    referrals.PHRASES is searched, not matched, so an entry for "Internal
    Affairs" also found those two words inside "Election Law and Internal
    Affairs" and "Rules, Enrolled Bills and Internal Affairs", and 38 bill
    cards of 2007-2016 named a Senate committee none of those terms had. A
    full name already written out must come back as itself: this fails on any
    PHRASES entry, present or future, that swallows one.
    """
    must = ("Election Law and Internal Affairs",
            "Rules, Enrolled Bills and Internal Affairs",
            "Election Law and Municipal Affairs", "Local and Regulated Revenues",
            "Public and Municipal Affairs")
    bad = _swallowed(referrals, _FULL_COMMITTEE_NAMES + must)
    assert not bad, "expand() renames a committee: " + "; ".join(bad)
    return "ok", f"{len(set(_FULL_COMMITTEE_NAMES + must))} full committee names each come back as themselves"


# Verbatim docket rows, by the file each is from. The bill's page narrates its
# history from the same file, which is why the committee row must be read
# from it too.
_FIRST_REFERRAL_DOCKETS = {
    "1989-1990": [   # Docket_db_1989-1990.txt: two measures numbered SCR 2
        "1989|0564|01/05/1989 05:08:50 PM|SCR2|S|INTRODUCED AND REF TO DEV. REC & ENV.  SJ 3  ,P 28|01/05/1989 05:08:50 PM",
        "1989|0564|02/07/1989 05:09:04 PM|SCR2|S|PASSED/ADOPTED|02/07/1989 05:09:04 PM",
        "1989|0564|03/02/1989 05:09:09 PM|SCR2|H|INTRODUCED AND REF TO ENV & AGR        HJ 39 ,P900|03/02/1989 05:09:09 PM",
        "1990|2730|01/03/1990 11:32:02 AM|SCR2|S|INTRODUCED AND REF TO PUBLIC AFFAIRS     SJ 1, P 6|01/03/1990 11:32:02 AM",
    ],
    "1991-1992": [   # Docket_db_1991-1992.txt: the committee on the next row
        "1991|0820|01/03/1991 10:10:25 AM|SB151|S|INTRODUCED AND REF TO TRANSPORTATION; SJ 2,P 19|01/03/1991 10:10:25 AM",
        "1991|0820|06/12/1991 08:54:00 AM|SB151|H|REP GROSS SUSP RULES FOR INTRO, MA 2/3VV; INTRODUCED AND REF TO|06/12/1991 08:54:00 AM",
        # The Senate's introduction filed under H, citing the Senate Journal.
        "1992|0495|01/03/1991 01:30:07 PM|SB192|H|INTRODUCED AND REF TO INTERNAL AFFAIRS;  SJ 2,P 21|01/03/1991 01:30:07 PM",
        "1992|0495|01/31/1991 10:32:49 AM|SB192|S|HEARING FEB14 10:30 RM101,LOB    FOR INTERNAL AFFAIRS|01/31/1991 10:32:49 AM",
        "1992|0495|03/26/1991 09:34:05 AM|SB192|S|PASSED AND REF TO FIN; SJ13,P175|03/26/1991 09:34:05 AM",
        "1992|0495|04/02/1991 03:05:32 PM|SB192|H|INTRODUCED AND REF TO EXEC DEPTS & ADMIN;  HJ60,P1371|04/02/1991 03:05:32 PM",
    ],
    "1993-1994": [   # Docket_db_1993-1994.txt: a reconsideration that lost
        "1994|2852|02/16/1994 05:16:15 PM|SB668|H|INTRODUCED AND REF TO EXEC DEPTS & ADMIN; HJ27,P809|02/16/1994 05:16:15 PM",
        "1994|2852|03/15/1994 05:29:09 PM|SB668|H|RECONSIDER INTRODUCTION, ML VV; HJ39,P1282|03/15/1994 05:29:09 PM",
        "1994|2852|03/31/1994 03:13:44 PM|SB668|H|REF TO EXEC DEPTS & ADMIN; HJ45,P1468|03/31/1994 03:13:44 PM",
    ],
    "1995-1996": [   # Docket_db_1995-1996.txt
        # A vacate the House voted down.
        "1995|0897|02/16/1995 10:38:45 AM|HB54|H|INTRODUCED AND REF TO FINANCE; HJ31,P738|02/16/1995 10:38:45 AM",
        "1995|0897|03/02/1995 07:03:17 PM|HB54|H|REP HAETTENSCHWILLER MOVED TO VACATE TO HEALTH, ML RC(167-178);|03/02/1995 07:03:17 PM",
        "1995|0897|03/02/1995 07:04:00 PM|HB54|H|HJ31,P740-742|03/02/1995 07:04:00 PM",
        # The other chamber's journal cited, and each row still its own
        # chamber's: HCR 25's number is the House's, and HB 1171's Senate
        # introduction is not the bill's first row.
        "1996|2611|01/03/1996 12:10:00 PM|HCR25|H|INTRODUCED AND REF TO SCIENCE, TECH & EN; SJ9,P142|01/03/1996 12:10:00 PM",
        "1996|2362|01/03/1996 03:58:11 PM|HB1171|H|INTRODUCED AND REF TO FINANCE; HJ4,P125|01/03/1996 03:58:11 PM",
        "1996|2362|02/21/1996 03:10:00 PM|HB1171|S|INTRODUCED AND REF TO TRANSPORTATION; HJ9,P115|02/21/1996 03:10:00 PM",
    ],
    "1999-2000": [   # Docket_db_1999-2000.txt
        "1999|0754|01/07/1999 09:50:11 AM|SB15|S|Introducing and referring to Insurance; SJ 2, P 26|01/07/1999 09:50:11 AM",
        "1999|0754|02/09/1999 03:12:46 PM|SB15|S|Hearing, 2/16/99, Room 103, SH, 11:10 a.m.|02/09/1999 03:12:46 PM",
        "1999|0660|05/27/1999 09:30:10 AM|HB722|s|Introduced and Refered to Judiciary SJ21 Pg.568|05/27/1999 09:30:10 AM",
        # The Senate's introduction filed under H, then the House's own.
        "2000|2472|01/05/2000 11:11:10 AM|SB369|H|Introduced and Ref. to Insurance; SJ Convening Day, Pg.10|01/05/2000 11:11:10 AM",
        "2000|2472|01/06/2000 08:26:41 AM|SB369|S|Hearing, Jan. 11, 9:30 a.m., Room 103, SH; SC1, Pg.3|01/06/2000 08:26:41 AM",
        "2000|2472|02/10/2000 12:27:42 PM|SB369|H|Introduced and ref to Commerce;  HJ18, p479|02/10/2000 12:27:42 PM",
        # A vacate whose row ends in "to", the committee on the next row.
        "1999|0874|01/28/1999 12:00:00 AM|SB108|S|Introduction; to Executive Dept. and Administration; SJ 3, P 36|01/28/1999 12:00:00 AM",
        "1999|0874|02/11/1999 11:24:43 AM|SB108|S|Sen. Cohen moved to Vacate from the Executive Departments and Administration to|02/11/1999 11:24:43 AM",
        "1999|0874|02/11/1999 11:25:36 AM|SB108|S|the Public Institutions, Health and Human Services Committee.  MA, VV. SJ,   P.|02/11/1999 11:25:36 AM",
    ],
    "2001-2002": [   # Docket_db_2001-2002.txt: a referral reconsidered, then made again
        "2002|0175|05/24/2001 12:30:10 PM|HB162|S|Introduced and Ref. to Public Affairs; SJ 14, Pg.301|05/24/2001 12:30:10 PM",
        "2002|0175|05/31/2001 03:46:11 PM|HB162|S|Sen. Francoeur Moved Reconsideration of Introduction and Committee Referral, MA,VV; SJ 15, Pg.319|05/31/2001 03:46:11 PM",
        "2002|0175|01/02/2002 05:13:36 PM|HB162|S|Introduced and Ref. to Education; SJ 1, Pg.10|01/02/2002 05:13:36 PM",
    ],
    "2007-2008": [   # Docket_db_2007-2008.txt: vacates written over two rows
        "2007|0032|01/31/2007 11:24:05 AM|HB829|H|Introduced and ref to Ways and Means; HJ 14, pg.230|01/31/2007 11:24:05 AM",
        "2007|0032|03/06/2007 12:08:11 PM|HB829|H|Rep. Almy: Vacate Referral to Ways & Means, MA VV; HJ 20, pg.407|03/06/2007 12:08:11 PM",
        "2007|0032|03/06/2007 12:08:37 PM|HB829|H|Referred to Municipal & County Government; HJ 20, pg.407|03/06/2007 12:08:37 PM",
        "2007|1094|04/12/2007 02:59:36 PM|HB866|S|Introduced and Referred to Executive Departments and Administration; SJ 12, Pg.301|04/12/2007 02:59:36 PM",
        "2007|1094|05/03/2007 01:02:17 PM|HB866|S|Sen. Burling Moved HB 866 be Vacated; SJ 15, Pg.329|05/03/2007 01:02:17 PM",
        "2007|1094|05/03/2007 01:02:51 PM|HB866|S|From ED&A to Public and Municipal Affairs, MA, VV; SJ 15, Pg.329|05/03/2007 01:02:51 PM",
        "2008|2540|03/27/2008 10:33:46 AM|HB1509|S|Introduced and Referred to Executive Departments and Administration; SJ 11, Pg.362|03/27/2008 10:33:46 AM",
        "2008|2540|04/10/2008 10:54:32 AM|HB1509|S|Sen. Burling Moved to Vacate HB 1509 From Executive Departments and Administration To|04/10/2008 10:54:32 AM",
        "2008|2540|04/10/2008 10:55:23 AM|HB1509|S|The Committee On Ways and Means, MA, VV; SJ 12, Pg.368|04/10/2008 10:55:23 AM",
    ],
    "2009-2010": [   # Docket_db_2009-2010.txt
        "2010|2002|12/10/2009 11:52:27 AM|HB1587|H|To Be Introduced 1/6/2010 and Referred to Finance|12/10/2009 11:52:27 AM",
    ],
    "2011-2012": [   # Docket_db_2011-2012.txt: drafted late, then referred
        "2012|3049|01/18/2012 02:04:48 PM|HB1716|H|Late Drafting and Introduction Approved By Rules Committee; HJ 10, PG.677|01/18/2012 02:04:48 PM",
        "2012|3049|01/18/2012 02:05:19 PM|HB1716|H|Referred to Public Works and Highways; HJ 10, PG.677|01/18/2012 02:05:19 PM",
    ],
    "2015-2016": [   # Docket_2015-2016.txt: a vacate over two rows, then the hearing
        "2016|0589|1/8/2015 12:00:00 AM|SB64|S|Introduced and Referred to Health and Human Services; SJ 4|1/8/2015 12:00:00 AM",
        "2016|0589|3/31/2015 12:00:00 AM|SB64|H|Introduced and Referred to Health, Human Services and Elderly Affairs (in recess of 3/25/2015); HJ 28 , PG. 1299|3/31/2015 12:00:00 AM",
        "2016|0589|4/1/2015 12:00:00 AM|SB64|H|Vacate (Rep Kotowski): MA VV; HJ 31 , PG. 1477|4/1/2015 12:00:00 AM",
        "2016|0589|4/1/2015 12:00:00 AM|SB64|H|Referred to Commerce and Consumer Affairs; HJ 31 , PG. 1477|4/1/2015 12:00:00 AM",
        "2016|0589|4/2/2015 12:00:00 AM|SB64|H|Public Hearing: 4/8/2015 11:30 AM LOB 302|4/2/2015 12:00:00 AM",
    ],
    "2021-2022": [   # Docket_2021-2022.txt: heard, THEN sent to the money committee
        "2022|2702|1/24/2022 12:00:00 AM|HB1288|H|Public Hearing: 01/24/2022 1:45 p.m. LOB302-304|1/24/2022 12:00:00 AM",
        "2022|2702|2/8/2022 12:00:00 AM|HB1288|H|Committee Report: Ought to Pass with Amendment #2022-0522h (Vote 18-0; CC)|2/8/2022 12:00:00 AM",
        "2022|2702|2/17/2022 12:00:00 AM|HB1288|H|Referred to Ways and Means 02/16/2022|2/17/2022 12:00:00 AM",
        "2022|2702|4/5/2022 12:00:00 AM|HB1288|S|Introduced 03/31/2022 and Referred to Executive Departments and Administration; SJ 8|4/5/2022 12:00:00 AM",
    ],
    "2023-2024": [   # Docket_2023-2024.txt
        "2024|2468|12/1/2023 12:00:00 AM|HB1215|H|Introduced 01/03/2024 and referred to Special Committee on Housing|12/1/2023 12:00:00 AM",
        "2024|2468|1/18/2024 12:00:00 AM|HB1215|H|Public Hearing: 02/16/2024 10:00 am LOB 302-304|1/18/2024 12:00:00 AM",
        "2024|2468|4/2/2024 12:00:00 AM|HB1215|S|Introduced 03/21/2024 and Referred to Election Law and Municipal Affairs; SJ 8|4/2/2024 12:00:00 AM",
        "2024|0057|12/23/2022 12:00:00 AM|HB91|H|Introduced 01/04/2023 and referred to Health, Human Services and Elderly Affairs|12/23/2022 12:00:00 AM",
        "2024|0057|2/14/2023 12:00:00 AM|HB91|H|Referred to Finance 02/14/2023 HJ 5|2/14/2023 12:00:00 AM",
    ],
    "2025-2026": [   # Docket.txt, the current term
        "2026|0994|1/22/2025 5:53:58 PM|SB83|S|  Introduced 01/09/2025 and Referred to Commerce;  SJ 3|1/22/2025 5:53:58 PM",
        "2026|0994|1/23/2025 4:53:44 PM|SB83|S|SB 83 is vacated from Commerce and referred to Ways and Means; (In recess 01/09/2025);  SJ 3|1/23/2025 4:53:44 PM",
        "2025|0138|1/6/2025 8:52:19 AM|HB165|H|  Introduced 01/08/2025 and referred to Municipal and County Government  HJ 2  P. 8|1/21/2025 2:00:30 PM",
        "2025|0138|3/28/2025 8:02:24 AM|HB165|S|  Introduced 03/27/2025 and Referred to Finance;  SJ 10|3/6/2026 4:24:49 PM",
        "2025|0957|1/22/2025 5:27:38 PM|CACR8|S|  Introduced 01/09/2025 and Referred to Judiciary;  SJ 3|1/22/2025 5:27:38 PM",
        "2025|0957|3/28/2025 2:00:10 PM|CACR8|H|  Introduced (in recess of) 03/27/2025 and referred to Criminal Justice and Public Safety  HJ 11  P. 113|5/19/2025 3:19:49 PM",
    ],
}


@check("narrative", "a bill's committee is its first referral in each chamber, read from its own term's docket",
       needs=("referrals", "build_data", "build_site_v2"))
def _first_referral(referrals, build_data, build_site_v2):
    """The committee rows name the committee each chamber FIRST referred to.

    Until 23 September the committee of every bill of 2016-2024 came from the
    General Court search page's "Next/Last Comm" -- the LAST committee, in
    ONE chamber -- because the docket was read only out of the database dump,
    which stops in 2016. HB 1215 of 2024 was referred to the House Special
    Committee on Housing and its page named only the Senate's committee; 778
    bill-chambers named a later referral, mostly Finance, and 4,087 left out
    the chamber the bill began in. Each assertion below is one way that came
    back, on rows copied verbatim from the dockets.
    """
    import contextlib
    import io
    R, BD, BS = referrals, build_data, build_site_v2
    c = R.committee
    # The shapes the introduction line takes, and the one it must refuse.
    for desc, want in (
            ("To Be Introduced 1/6/2010 and Referred to Finance", "Finance"),
            ("Introducing and referring to Insurance; SJ 2, P 26", "Insurance"),
            ("Introduction and referring to Wildlife & Recreation, SJ 10, P 219",
             "Wildlife and Recreation"),
            ("[APPROVED BY RULES] INTRODUCED AND REF TO PUBLIC WORKS; HJ29,P577",
             "Public Works"),
            ("(JAN23)INTRODUCED AND REF TO TRANSPORTATION; SJ3, P49", "Transportation"),
            ("04/09/91   INTRODUCED AND REF TO ENVIRONMENT;  SJ16,P234", "Environment"),
            ("Rules Comm Approved: Introduced 1/23/2008 and Ref to Criminal Justice "
             "& Public Safety; HJ 13, PG.724", "Criminal Justice and Public Safety"),
            ("Introduced & ref:  Criminal Justice & Public Safety   HJ 7, pg 346 <Finance>",
             "Criminal Justice and Public Safety"),
            ("Introduced and ref Executive Dept. & Admin <W & M>    HJ20, pg 1256",
             "Executive Departments and Administration"),
            ("INTRODUCED AND REF TO EDUC. HJ9   ,P89", "Education"),
            ("REP GROSS SUSP RULES FOR INTRO, MA 2/3VV; INTRODUCED AND REF TO", ""),
            ("Committee Report: Refer to Interim Study", "")):
        got = c(desc)
        assert got == want, f"committee({desc[:50]!r}) gave {got!r}, wanted {want!r}"

    with tempfile.TemporaryDirectory() as tmp:
        found = {}
        for term, lines in _FIRST_REFERRAL_DOCKETS.items():
            p = Path(tmp) / f"Docket_{term}.txt"
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            found[term] = str(p)
        refs, began = R.read_dockets(found, lsr_of={("1989-1990", "SCR2"): "2730"})
        majority = R.from_dockets({"1989-1990": found["1989-1990"]})
        # What each bill's committee rows must say.
        want = {
            ("2023-2024", "HB1215"): {"H": "Special Committee on Housing",
                                      "S": "Election Law and Municipal Affairs"},
            ("2023-2024", "HB91"): {"H": "Health, Human Services and Elderly Affairs"},
            ("1999-2000", "SB15"): {"S": "Insurance"},
            ("1999-2000", "HB722"): {"S": "Judiciary"},
            ("2009-2010", "HB1587"): {"H": "Finance"},
            ("2011-2012", "HB1716"): {"H": "Public Works and Highways"},
            # Heard first, so the bare "Referred to" is the money pass: no
            # House committee of referral is read, rather than a wrong one.
            ("2021-2022", "HB1288"): {"S": "Executive Departments and Administration"},
            # The record's own LSR picks the 1990 resolution, not the 1989 one.
            ("1989-1990", "SCR2"): {"S": "Public Affairs"},
            ("1991-1992", "SB151"): {"S": "Transportation"},
            # A first row filed under the House that cites the Senate Journal
            # is the Senate's introduction (SB 369, SB 192); a row citing the
            # other journal that is not the first, or whose number is its
            # chamber's own, stays where it is filed (HB 1171, HCR 25).
            ("1999-2000", "SB369"): {"S": "Insurance", "H": "Commerce"},
            ("1991-1992", "SB192"): {"S": "Internal Affairs",
                                     "H": "Executive Departments and Administration"},
            ("1995-1996", "HCR25"): {"H": "Science, Technology and Energy"},
            ("1995-1996", "HB1171"): {"H": "Finance", "S": "Transportation"},
            # A vacate over two rows: the second row names where the bill
            # went (SB 64 was heard by Commerce and Consumer Affairs), in
            # each shape the clerks used -- including the one vacated()
            # refuses on its own row (HB 829) and a row ending in "to".
            ("2015-2016", "SB64"): {"S": "Health and Human Services",
                                    "H": "Commerce and Consumer Affairs"},
            ("2007-2008", "HB829"): {"H": "Municipal and County Government"},
            ("2007-2008", "HB866"): {"S": "Public and Municipal Affairs"},
            ("2007-2008", "HB1509"): {"S": "Ways and Means"},
            ("1999-2000", "SB108"): {"S": "Public Institutions, Health and Human Services"},
            # A vacate the House voted down moves nothing.
            ("1995-1996", "HB54"): {"H": "Finance"},
            # A carried reconsideration of the introduction clears the
            # referral; one that lost does not.
            ("2001-2002", "HB162"): {"S": "Education"},
            ("1993-1994", "SB668"): {"H": "Executive Departments and Administration"},
            # A vacate replaces the first referral; the docket beats a code.
            ("2025-2026", "SB83"): {"S": "Ways and Means"},
            ("2025-2026", "HB165"): {"H": "Municipal and County Government",
                                     "S": "Finance"},
            ("2025-2026", "CACR8"): {"S": "Judiciary",
                                     "H": "Criminal Justice and Public Safety"},
        }
        bad = [f"{k}: {refs.get(k)} wanted {v}" for k, v in want.items() if refs.get(k) != v]
        assert not bad, "; ".join(bad)
        assert "H" in majority.get(("1989-1990", "SCR2"), {}), (
            "with no LSR given, the LSR most rows carry should be read")
        assert began.get(("2025-2026", "CACR8")) == "S", began.get(("2025-2026", "CACR8"))
        assert began.get(("1999-2000", "SB369")) == "S", began.get(("1999-2000", "SB369"))

        # The current term: the docket over the referral code, and the chamber
        # a stub CACR began in.
        bills = {
            "SB83": {"lsr_year": "2026", "lsr_num": "0994", "chamber": "S",
                     "house_committee": "", "senate_committee": "Commerce"},
            "HB165": {"lsr_year": "2025", "lsr_num": "0138", "chamber": "H",
                      "house_committee": "Municipal and County Government",
                      "senate_committee": "Health and Human Services"},
            "CACR8": {"lsr_year": "2025", "lsr_num": "0957", "chamber": "C",
                      "house_committee": "Criminal Justice and Public Safety",
                      "senate_committee": "Judiciary"}}
        table = {"S01": {"name": "Commerce"}, "S02": {"name": "Ways and Means"},
                 "S03": {"name": "Finance"}, "S26": {"name": "Health and Human Services"},
                 "S04": {"name": "Judiciary"},
                 "H01": {"name": "Municipal and County Government"},
                 "H02": {"name": "Criminal Justice and Public Safety"}}
        with contextlib.redirect_stdout(io.StringIO()):
            BD._current_referrals(bills, table, found["2025-2026"])
        assert bills["SB83"]["senate_committee"] == "Ways and Means", bills["SB83"]
        assert bills["HB165"]["senate_committee"] == "Finance", bills["HB165"]
        assert bills["HB165"]["house_committee"] == "Municipal and County Government"
        assert bills["CACR8"]["chamber"] == "S", bills["CACR8"]

    # Choosing between the docket's first referral and the search page's
    # last committee.
    known = {R._key(n) for n in ("Finance", "Public Works and Highways", "Ways and Means",
                                 "Criminal Justice and Public Safety",
                                 "Children and Family Law")}
    pick = BD._pick_committee
    for stored, first, in_use, got_want in (
            ("Finance", "Insurance", (), "Insurance"),       # a later money pass
            ("Public Works and Highways", "Public Works", {"publicworks"},
             "Public Works and Highways"),                    # one committee
            ("WILDLIFE, FISH AND GAME AND AGRICULTURE", "Wildlife, Fish and Game", (),
             "Wildlife, Fish and Game"),                      # renamed later
            ("Criminal Justice and Public Safety", "Criminal Justice", (),
             "Criminal Justice and Public Safety"),           # cut short
            ("Criminal Justice and Public Safety", "Criminal Justice",
             {"criminaljustice"}, "Criminal Justice"),        # a name in use
            ("ENVIRONMENT", "Enviroment", (), "ENVIRONMENT"),  # a clerk's typing
            ("Ways and Means", "Ways and Means Committee", (), "Ways and Means"),
            ("Children and Family Law", "Child and Fam", (), "Children and Family Law")):
        got = pick(stored, first, known, in_use)
        assert got == got_want, (f"_pick_committee({stored!r}, {first!r}) gave "
                                 f"{got!r}, wanted {got_want!r}")

    # THE committee of an index row is the originating chamber's; the card
    # keeps House first.
    got = BS.bill_committees({"chamber": "S", "house_committee": "Finance",
                              "senate_committee": "Judiciary"}, "SB1")
    assert got == ("Senate Judiciary", ["House Finance", "Senate Judiciary"]), got
    got = BS.bill_committees({"chamber": "H", "house_committee": "Finance",
                              "senate_committee": "Judiciary"}, "HB91")
    assert got == ("House Finance", ["House Finance", "Senate Judiciary"]), got
    return "ok", (f"{len(want)} bills read from verbatim docket rows, "
                  "the docket's name against the search page's, and the "
                  "originating chamber's committee first")


@check("data", "every committee name on disk comes back from expand() as itself",
       needs=("referrals",))
def _full_names_on_disk(referrals):
    """The same guard, over the names the General Court's own tables carry.

    data/committees.json and db/Committees.psv (its Name and LongName
    columns) name every committee this site links to, and grow when the
    General Court adds one. The code check above holds a copy of the list as
    it was; this reads the list as it is.
    """
    found = []
    f = Path("data/committees.json")
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
        found += [c.get("name") for c in (d.values() if isinstance(d, dict) else d)
                  if isinstance(c, dict) and c.get("name")]
    p = Path("db/Committees.psv")
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            cols = line.split("|")
            found += [x.strip() for x in cols[1:3] if len(cols) > 2 and x.strip()]
    if not found:
        return "skip", "no data/committees.json or db/Committees.psv"
    bad = _swallowed(referrals, found)
    assert not bad, "expand() renames a committee: " + "; ".join(bad)
    return "ok", f"{len(set(found))} committee names on disk each come back as themselves"


@check("data", "an archived bill's committees are its docket's first referrals, and THE committee is its own chamber's",
       needs=("referrals", "build_data"))
def _first_referral_on_disk(referrals, build_data):
    """The built record against each term's own docket.

    Wherever a chamber's docket names a first referral, data/bills.json must
    show that committee, or the search page's spelling of the same one
    (build_data._same_committee). And every row of the bill index whose
    bill has a committee in the chamber it began in must name that one as
    THE committee. On the build of 23 September, 778 bill-chambers showed a
    later referral, 4,087 left out the originating chamber's committee and
    8,385 index rows named the other chamber's; this is what fails if the
    reading, the keying on the term or the ordering comes undone. It
    measures the wiring, not the reader: a docket line in a shape referrals
    cannot read is invisible to both sides.
    """
    fb, fa = Path("data/bills.json"), Path("archive_bills.json")
    if not (fb.exists() and fa.exists()):
        return "skip", "no data/bills.json or archive_bills.json"
    found = referrals.term_dockets()
    if not found:
        return "skip", "no archived docket on this disk"
    bills = json.loads(fb.read_text(encoding="utf-8"))
    arch = json.loads(fa.read_text(encoding="utf-8"))
    refs = referrals.from_dockets(found, lsr_of={
        (t, b): r.get("lsr", "") for t, bb in arch.items() for b, r in bb.items()})
    fc = Path("data/committees.json")
    table = json.loads(fc.read_text(encoding="utf-8")) if fc.exists() else {}
    known = {referrals._key(c["name"]) for c in (table.values() if isinstance(table, dict) else table)
             if isinstance(c, dict) and c.get("name")}
    used = Counter((t, body, referrals._key(c)) for (t, _b), bodies in refs.items()
                   for body, c in bodies.items())
    in_use = {}
    for (t, body, k), n in used.items():
        if n >= 3:
            in_use.setdefault((t, body), set()).add(k)
    # The docket's first referral as build_data writes it: under the name the
    # committee had at the time (committee_names.official), which is a
    # spelling of the same committee and never a different one.
    import committee_names as CN
    # A BILL THAT WAS NEVER INTRODUCED WAS NEVER REFERRED (1 October 2026). Its
    # "To Be Introduced 1/6/2010 and Referred to Finance" row is a plan, which
    # the referral reader takes for a referral and the bill's own history
    # does not (narratives.json's not_introduced; build_data.add_past_bills
    # leaves such a record no committee). Those must show none.
    narr = _narratives() if Path("narratives.json").exists() else {}
    wrong, checked = [], 0
    for (t, b), bodies in refs.items():
        rec = (bills.get(t) or {}).get(b)
        if not rec or not rec.get("archived"):
            continue
        never = bool(((narr.get(t) or {}).get(b) or {}).get("not_introduced"))
        for body, first in bodies.items():
            checked += 1
            shown = rec.get("house_committee" if body == "H" else "senate_committee") or ""
            if never:
                if shown:
                    wrong.append(f"{t} {b} {body}: shows {shown!r}, and the bill was "
                                 "never introduced")
                continue
            said = {referrals._key(first), referrals._key(CN.official(first, body, t))}
            if not shown or (referrals._key(shown) not in said and not
                             build_data._same_committee(first, shown, known,
                                                        in_use.get((t, body), ())) and
                             referrals._key(CN.official(shown, body, t)) not in said):
                wrong.append(f"{t} {b} {body}: shows {shown!r}, docket {first!r}")
    assert not wrong, (f"{len(wrong)} of {checked:,} archived bill-chambers do not show "
                       "the docket's first referral (rebuild with build_all.py if the "
                       "code is newer than data/bills.json): " + "; ".join(wrong[:4]))
    rows = _site_bills()
    if rows is None:
        return "ok", f"{checked:,} archived bill-chambers show their first referral; no site built"
    off = []
    for row in rows:
        rec = (bills.get(row.get("term")) or {}).get(row.get("id")) or {}
        ch = "Senate " if str(rec.get("chamber") or row.get("id", "")[:1]).upper() \
            .startswith("S") else "House "
        if any(c.startswith(ch) for c in row.get("committees") or []) \
                and not str(row.get("committee") or "").startswith(ch):
            off.append(f"{row.get('term')} {row.get('id')}: {row.get('committee')!r}")
    assert not off, (f"{len(off):,} index rows name the other chamber's committee as "
                     "THE committee: " + "; ".join(off[:4]))
    return "ok", (f"{checked:,} archived bill-chambers show their first referral, and "
                  f"{len(rows):,} index rows name the originating chamber's committee")


@check("data", "an archived bill's committee came from a source that has one",
       needs=("referrals",))
def _referral_coverage(referrals):
    """The five terms before 1999 had 0 committees and now have 95-98%.

    A regression here does not raise anything: it silently returns the site
    to a 1989 bill that names no committee, which is what it looked like for
    a year.
    """
    f = Path("data/bills.json")
    if not f.exists():
        return "skip", "no data/bills.json"
    bills = json.loads(f.read_text(encoding="utf-8"))
    thin = []
    for term in ("1989-1990", "1991-1992", "1993-1994", "1995-1996",
                 "1997-1998"):
        bs = bills.get(term) or {}
        if not bs:
            continue
        got = sum(1 for r in bs.values()
                  if r.get("house_committee") or r.get("senate_committee"))
        if got < len(bs) * 0.85:
            thin.append(f"{term} {got}/{len(bs)}")
    assert not thin, ("the docket gives 95-98% of these terms a committee; "
                      "now: " + ", ".join(thin))
    return "ok", "the five pre-1999 terms all above 85%"


@check("frontend", "the Calendars & Journals section and its pickers say their words in Spanish and leave the documents' names as the General Court printed them",
       needs=("calendar_documents", "i18n"))
def _calendar_documents_in_spanish(CD, i18n):
    """block_html(lang="es") for a queue of four documents, one in each of the
    four sets: the heading, the labels, the button and the sentence in
    Spanish, the kinds of document in Spanish (Calendario de la Cámara), each
    document's own name marked lang="en"; English's section is what it was
    with no language stated. picker_js("es") run in node says a document's
    count, its button's name and its choice in Spanish, as the English says
    them in English."""
    import csv
    import datetime as _dt
    node = _cal_node()
    root = Path(tempfile.mkdtemp(prefix="gr-cdspanish-"))
    try:
        H = "https://gc.nh.gov/house/calendars_journals/viewer.aspx?fileName="
        SN = "https://gc.nh.gov/senate/calendars_journals/viewer.aspx?fileName="
        rows = [("H", "calendar", "2026", "HC 32.pdf", H + "calendars%5C2026%5CHC%2032.pdf",
                 r"calendars\2026\HC032.pdf", "held", "0", "", ""),
                ("H", "journal", "2026", "HJ 16 August 19, 2026.pdf",
                 H + "journals%5C2026%5CHJ%2016%20August%2019%2C%202026.pdf",
                 r"journals\2026\HJ 16 August 19, 2026.pdf", "held", "0", "", ""),
                ("S", "calendar", "2026", "SC 29.pdf", SN + "Calendars%5C2026%5CSC%2029.pdf",
                 r"calendars_senate\2026\SC029.pdf", "held", "0", "", ""),
                ("S", "journal", "2026", "SJ 15.pdf", SN + "Journals%5C2026%5CSJ%2015.pdf",
                 r"journals_senate\2026\SJ 15.pdf", "held", "0", "", "")]
        q = root / "queue.csv"
        with q.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["chamber", "kind", "year", "name", "url", "path", "state", "attempts",
                        "error", "bytes", "fetched"])
            for r in rows:
                w.writerow(list(r[:9]) + ["1", r[9]])
        docs, left = CD.read(q, root=root, today=_dt.date(2026, 10, 1))
        assert len(docs) == 4, f"{len(docs)} documents read, not 4"
        en = CD.block_html(docs, left)
        assert en == CD.block_html(docs, left, lang="en"), "English's section changed with its language stated"
        es = CD.block_html(docs, left, lang="es")
        for want in ("Calendarios y diarios de sesiones", "Abrir el PDF", "Calendario de la Cámara",
                     "Diario del Senado", "Calendario o diario", "Los más recientes de esta lista",
                     'lang="en">HC 32', "(en inglés)"):
            assert want in es, f"the Spanish section lacks {want!r}"
        seen = _visible_text("<main>" + es + "</main>")
        for lead in ("Open the PDF", "Calendar or journal", "The newest listed here", "Document", "House Calendar"):
            assert not re.search(rf"\b{re.escape(lead)}\b", seen), f"the Spanish section says {lead!r}"
        if not node:
            return "ok", "the Spanish section holds its words (node is not here for the picker's script)"
        import i18n as _i
        js = CD.picker_js("es")
        ix = json.dumps(CD.index(docs), ensure_ascii=False)
        prog = root / "picker.js"
        prog.write_text(
            "globalThis.document=undefined;\n" + _components_js() + "\n"
            'globalThis.window=globalThis; globalThis.GR_LANG="es";\n' + _i.words_js("es", js) + "\n"
            + js + "\nconst ix=" + ix + ";\nconst s=GRDOCS.state(ix,'hc','2026',0);\n"
            "const want={chosen:'Calendario de la Cámara, HC 32',"
            "name:'Abrir el PDF: Calendario de la Cámara, HC 32, en el sitio de la Legislatura',"
            "count:'1 Calendario de la Cámara de 2026.'};\n"
            "const bad=Object.keys(want).filter(k=>s[k]!==want[k]).map(k=>k+': '+JSON.stringify(s[k]));\n"
            "console.log(bad.length?bad.join('\\n'):'OK');\n", encoding="utf-8")
        r = _run([node, str(prog)], capture_output=True, text=True, encoding="utf-8", timeout=60)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        assert r.returncode == 0 and out.endswith("OK"), out[-900:]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", "the section, the kinds of document and the picker's script in Spanish; the documents' names marked English"


@check("build", "every recording's Eastern start is its UTC start on New Hampshire's clock",
       needs=("fetch_channel_index",))
def _video_starts_on_the_right_clock(fetch_channel_index):
    """54 rows of the video lists -- 40 of videos_house_2025-01-01_to_2025-03-31
    and 14 of videos_senate_2025-01-01_to_2025-06-30, streams of 3-7 March 2025
    -- carried a start_eastern an hour late, written before the fetcher's
    daylight-time fix of 5 March 2026 treated the first week of March as
    daylight time. The build places a recording by that column, so 21
    "approximate" stations opened their video an hour early, and six choices
    between two recordings were made against the wrong clock (found 25
    September 2026). Every row's Eastern start must be its own UTC start through
    the fetcher's to_eastern_clock, which is the rule the fetcher writes by.
    """
    import csv as _csv
    bad, n = [], 0
    import proceedings as _P
    for p in _P.video_indexes():
        rows = list(_csv.DictReader(p.open(encoding="utf-8", newline="")))
        if not rows or "actual_start_utc" not in rows[0] or "start_eastern" not in rows[0]:
            continue
        for r in rows:
            u, e = (r.get("actual_start_utc") or "").strip(), (r.get("start_eastern") or "").strip()
            if not u or not e:
                continue
            n += 1
            want = fetch_channel_index.to_eastern_clock(u)
            if want != e:
                bad.append(f"{p.name} {r.get('video_id')}: {e}, which its UTC start makes {want}")
    if not n:
        return "skip", "no video list with both start columns here"
    assert not bad, (f"{len(bad)} recordings start on the wrong clock: "
                     + "; ".join(bad[:4]))
    return "ok", f"{n:,} recordings' Eastern starts agree with their UTC starts"


@check("build", "a docket with no proceeding yet makes a manifest of its columns and no row",
       needs=("build_manifest",))
def _manifest_with_no_proceeding(BM):
    """A new term's first docket is Organization Day's resolutions and the
    first bills' introductions, and no hearing. build_manifest took its
    columns from its first row and stopped on an IndexError there, leaving
    the last term's manifest in place (the rehearsal of 5 October 2026)."""
    here = Path(".").resolve()
    tmp = Path(tempfile.mkdtemp(prefix="gr-manifest-"))
    try:
        (tmp / "v.csv").write_text("video_id,title,title_parsed,parsed_committee,parsed_date,"
                                   "date_from,has_start_time,start_eastern,actual_start_utc,"
                                   "actual_end_utc,duration_iso,published_at\n", encoding="utf-8")
        (tmp / "Docket.txt").write_text(
            "2027|0001|12/2/2026 10:44:26 AM|HR1|H|Introduced and Adopted, VV; 12/02/2026 HJ 1|"
            "12/2/2026 10:44:26 AM\n", encoding="utf-8")
        r = _run([sys.executable, _paths.script("build_manifest.py"), "--videos", "v.csv",
                  "--docket", "Docket.txt", "--out", "vm.csv"], cwd=tmp, capture_output=True,
                 text=True, timeout=120, env=dict(os.environ, PYTHONPATH=str(here)))
        assert r.returncode == 0, (r.stdout + r.stderr)[-300:]
        head = (tmp / "vm.csv").read_text(encoding="utf-8").splitlines()
        assert head == [",".join(BM.MANIFEST_COLUMNS)], head
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", "a resolutions-only docket writes the manifest's columns and no row"


@check("data", "status.txt's session_over is a day of the term the session's files describe",
       needs=("proceedings", "build_site_v2"))
def _session_over_current(P, BSV):
    """status/status.txt is the person's, and its session_over line says to
    delete it in December, when the next term brings its own session days.
    The build already reads it only for its own term (session_over_in), so a
    line left in ends no 2027 bill; this is the reminder, the CACR 13
    paragraph's kind, that once the session's files are the next term's the
    line, the headline, the phase and the note are last term's words."""
    day = BSV.session_over("corrections/status/status.txt")
    if not day:
        return "skip", "no session_over line in status/status.txt"
    sess = P.session_term(".")
    assert not sess or P.term_of(day) >= sess, (
        f"status/status.txt says session_over: {day}, a day of {P.term_of(day)}, and the session's "
        f"files are {sess}'s: delete the line, and bring the phase, headline and note up to date "
        "(the file is yours; the build already reads the line for its own term only)")
    return "ok", f"session_over {day} is a day of {P.term_of(day)}, the session's term"


@check("data", "bill_titles.json, where it is here, is keyed on the term",
       needs=("proceedings",))
def _bill_titles_by_term(P):
    """build_data reads bill_titles.json only by term since 5 October 2026,
    and passes over a flat one; this says so out loud, because a flat file
    put back by fetch_bill_titles.py would otherwise be quietly ignored."""
    p = Path("bill_titles.json")
    if not p.exists():
        return "skip", "no bill_titles.json here (none since the term-keyed files)"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert P.term_keyed(data), ("bill_titles.json is keyed on the bill number alone: a title of "
                                "one term would reach a bill of another. It must be "
                                "{term: {bill: title}}")
    return "ok", f"keyed on {len(data)} term(s)"


@check("data", "the calendar and the docket agree about a hearing")
def _calendar_meetings():
    """The calendar says who is hearing what, where, and when.

    It is the only source that can answer "what is Education hearing on
    Monday" -- the docket answers per bill and cannot be asked that way -- and
    it is also the legal notice, so its publication date is when the window
    for public testimony opens.

    Neither of those is worth anything if the parse is wrong, and the parse
    reads a two-column PDF whose columns do not always line up. So it is
    scored on every run against the docket, which nothing here wrote: for a
    hearing both sources know, do they call it the same kind of meeting, at
    the same time, in the same room?

    The floors are set below the measurement of 8 September (kind 96%, room
    100% of the rows where both name one) so that a regression fails and an
    improvement does not.
    """
    try:
        import calendar_meetings as CM
    except ImportError:
        return "skip", "calendar_meetings is not here"
    if not Path("calendars").exists():
        return "skip", "no calendars on disk"
    rows = CM.load("H") + CM.load("S")
    if not rows:
        return "skip", "no calendar produced a meeting"
    hearings = [r for r in rows
                if r["kind"] == "public hearing" and r["bill"] and r["date"]]
    assert len(hearings) > 5000, (
        f"only {len(hearings):,} public hearings parsed out of the calendars; "
        "8 September measured 7,293, and a collapse here means a format the "
        "parser stopped recognising rather than a quiet session")
    # A bill's own line is never a committee -- see the calendar check that
    # says so on printed lines. This is the same claim over every file.
    lead = re.compile(r"^(?:Hb|Sb|Hr|Sr|Hcr|Scr|Cacr|Hjr)\s*\d", re.I)
    billcom = [r for r in rows if lead.match(r["committee"] or "")]
    assert not billcom, (
        f"{len(billcom):,} calendar rows name a bill as their committee, e.g. "
        f"{billcom[0]['bill']} on {billcom[0]['date']} heard by "
        f"{billcom[0]['committee']!r} in {billcom[0]['calendar']}: a bill's line "
        "was read as a header again")

    # A notice cannot follow the thing it notices. All 7,293 were published on
    # or before the day of the hearing when this was written, median five days
    # ahead, so any exception is a parse fault rather than a late clerk.
    import datetime
    late = [r for r in hearings if r["noticed"] and
            datetime.date.fromisoformat(r["noticed"])
            > datetime.date.fromisoformat(r["date"])]
    assert not late, (
        f"{len(late)} hearing(s) are noticed by a calendar published after the "
        f"hearing itself, e.g. {late[0]['bill']} heard {late[0]['date']} and "
        f"announced {late[0]['noticed']}")

    got = CM.check(rows)
    # Docket.txt not here: nothing to score against. Here with no hearing in
    # it -- a new term's first nights, Organization Day's resolutions alone
    # (the rehearsal of the turn, 19 November 2026) -- the parse above is
    # still held and the scoring waits.
    if not Path("Docket.txt").exists():
        return "skip", f"{len(hearings):,} public hearings parsed; {got.get('note')}"
    known = int(str(got["the docket also knows"]).replace(",", ""))
    if known < 500:
        return "ok", (f"{len(hearings):,} public hearings parsed; the docket "
                      "holds too few of them to score against"
                      + (f" ({got['note']})" if got.get("note") else ""))
    kind = int(str(got["kind agrees"]).split(" of ")[0].replace(",", ""))
    room_s = str(got["room agrees, where both state one"])
    room = int(room_s.split(" of ")[0].replace(",", ""))
    room_n = int(room_s.split(" of ")[1].split(" ")[0].replace(",", ""))
    assert kind / known >= 0.93, (
        f"the calendar and the docket agree about the kind of meeting on only "
        f"{kind / known:.0%} of {known:,}; it was 96% on 8 September. "
        f"{got['kind disagreements'][:3]}")
    assert room_n == 0 or room / room_n >= 0.99, (
        f"they disagree about the room on {room_n - room} of {room_n:,}; "
        f"three was the whole of it on 8 September. {got['room disagreements'][:3]}")
    return "ok", (f"{len(hearings):,} public hearings out of the calendars, "
                  f"{kind:,} of {known:,} agreeing with the docket on kind, "
                  f"{room:,} of {room_n:,} on room")


@check("calendar", "the calendar's score against the docket gives every figure, with no docket, with "
       "a docket of no hearing, and with hearings to score", needs=("calendar_meetings",))
def _calendar_score_shape(calendar_meetings):
    """The rehearsal of the turn, 19 November 2026: on the first post-turn
    nights the docket held the 2027 batch and no hearing, calendar_meetings.
    check returned a note alone -- one saying Docket.txt was not here, which
    it was -- and the check of the calendars above raised KeyError 'the
    docket also knows'. On the real night of 2 December the docket holds
    Organization Day's resolutions only. Held on three dockets in a scratch
    folder: none, resolutions only, and one hearing the calendar calls
    another kind of meeting, which must still score as a disagreement."""
    CM = calendar_meetings
    keys = {"rows", "with a bill", "the docket also knows", "kind agrees",
            "time agrees, where both state one", "room agrees, where both state one",
            "kind disagreements", "room disagreements"}
    row = {"bill": "HB10", "date": "2027-01-14", "kind": "executive session",
           "time": "10:00", "room": "LOB 206"}
    here, root = os.getcwd(), tempfile.mkdtemp()
    said = {}
    try:
        os.chdir(root)
        for name, docket in (
                ("no docket", None),
                ("resolutions only", ["2027|0939|12/2/2026 12:59:53 PM|HR1|H|Introduced and "
                                      "Adopted VV 12/02/2026  HJ 1|12/2/2026 12:59:56 PM"]),
                ("one hearing", ["2027|7001|1/5/2027 9:00:00 AM|HB10|H|Public Hearing: "
                                 "01/14/2027 10:00 am LOB 206|1/5/2027 9:00:00 AM"])):
            if docket is not None:
                Path("Docket.txt").write_text("\n".join(docket) + "\n", encoding="utf-8")
            got = CM.check([dict(row)])
            assert keys <= set(got), f"{name}: the score lacks {sorted(keys - set(got))}"
            said[name] = (got["the docket also knows"], got["kind agrees"], got.get("note", ""))
    finally:
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)
    assert said["no docket"][0] == "0" and "is not here" in said["no docket"][2], said
    assert said["resolutions only"][0] == "0" and "no hearing yet" in said["resolutions only"][2], said
    assert said["one hearing"][:2] == ("1", "0 of 1 (0%)") and not said["one hearing"][2], (
        f"a hearing the calendar calls an executive session did not score as a disagreement: {said}")
    return "ok", ("every figure given with no docket, with resolutions only (\"no hearing yet\"), "
                  "and a hearing of another kind scored 0 of 1")


@check("data", "a proceeding is matched only to its own chamber's recording")
def _manifest_chamber():
    """build_manifest keyed recordings on committee and date, and both
    chambers have an Education, a Judiciary, a Finance and more that sit on
    the same days: all 91 Senate hearings of 2021-2022 that had a recording
    had the House committee's, and 79 House proceedings of 2023-2024 and 19
    of the current term had the Senate's. A committee of conference, which
    sits for both, is the one exception. Read from every manifest on disk,
    the chamber of a recording from the index file it came from."""
    import glob
    mans = sorted(glob.glob("verification_manifest*.csv"))
    if not mans:
        return "skip", "no manifest on disk"
    body_of = {}
    import proceedings as _P
    for f in map(str, _P.video_indexes()):
        b = "S" if "senate" in f.lower() else "H"
        with open(f, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                body_of[r["video_id"]] = b
    n, bad = 0, []
    for m in mans:
        with open(m, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                v = r.get("video_id")
                if not v or v not in body_of:
                    continue
                n += 1
                if (body_of[v] != r.get("body")
                        and r.get("proceeding") != "committee of conference"):
                    bad.append(f"{r['bill']} {r['body']} {r['proceeding']} "
                               f"{r['sched_date']} on {r['video_title'][:40]!r}"
                               f" ({m})")
    assert not bad, (f"{len(bad):,} of {n:,} matched proceedings are on the "
                     f"other chamber's recording: " + "; ".join(bad[:3]))
    return "ok", f"{n:,} matched proceedings, each on its own chamber's recording"


@check("data", "no published time was read off captions out of step with the recording")
def _late_captions_site():
    """The guard, on the site as built.

    build_site_v2 withholds every time read off a caption track that stops
    well short of its recording -- see caption_span.py, and the build check
    of the same name. A site built before that, or by a build that skipped
    it, still carries them, and nothing on the page looks wrong. So this
    reads what the pages publish: for every recording whose captions stop
    more than caption_span.SLACK short of it, does any station on it carry a
    time read off those captions -- a stated or clustered start, a stated
    floor boundary, or a consent-calendar finding?
    """
    try:
        import caption_span as CS
        import proceedings as P
        import site_read
    except ImportError:
        return "skip", "caption_span, proceedings or site_read is not here"
    if not (Path("site/bill").is_dir() and Path("work").is_dir()):
        return "skip", "no built site, or no work/ to compare it with"
    late, compared, undated = CS.out_of_step(
        [d.name for d in Path("work").iterdir() if d.is_dir()])
    if not compared:
        return "skip", ("no recording under work/ has both captions and a "
                        "published length")
    short = f"{CS.SLACK // 60} minutes"
    if not late:
        return "ok", f"{compared:,} recordings compared; none stops {short} short"
    # Only the terms those recordings belong to: the pages are the slow part.
    rows = P.by_video(P.load())
    years = sorted({y for v in late for r in rows.get(v, [])
                    for y in str(r.get("term") or "").split("-") if y.isdigit()})
    CAPTIONED = {"stated", "located", "floor_stated", "consent"}
    n, bad = 0, []
    for y, b, s in (site_read.stations("site", years) if years else ()):
        if s.get("video_id") not in late:
            continue
        n += 1
        if s.get("state") in CAPTIONED or s.get("start_stated"):
            bad.append(f"{b} of {y}, {s.get('when')}, on {s['video_id']}: "
                       f"{s.get('state')} at {s.get('start')}")
    assert not bad, (
        f"{len(bad)} published station(s) carry a time read off captions that "
        f"stop more than {short} short of their recording -- an hour early, on "
        f"every one measured: {'; '.join(bad[:2])}. Rebuild the site.")
    return "ok", (f"{compared:,} recordings compared; {len(late)} stop more "
                  f"than {short} short, and none of the {n} stations on them "
                  "publishes a time read off their captions"
                  + (f"; {len(undated)} have no published length to compare"
                     if undated else ""))


@check("data", "the caption summary the nightly reads agrees with the captions here")
def _caption_summary_data():
    """caption_spans.json is what the nightly's machine has in place of the
    caption files: where each recording's captions stop, as read here. If it
    falls behind them -- a caption job that did not rewrite it, a track
    fetched again -- the nightly withholds or publishes differently from the
    laptop, and nothing there could tell. So where both are on one disk they
    must agree recording by recording and name the same recordings late.
    `python3 src/hearings/caption_span.py --write` brings it up to date, and so does any
    build, whose markers step writes it.
    """
    try:
        import caption_span as CS
    except ImportError:
        return "skip", "caption_span.py will not import"
    if not Path("work").is_dir():
        return "skip", "no work/ here to compare it with"
    if not Path(CS.SUMMARY).exists():
        return "skip", (f"no {CS.SUMMARY} yet; the next build's markers step "
                        "writes it, or caption_span.py --write")
    bad = CS.check_summary()
    assert not bad, (
        f"{CS.SUMMARY} disagrees with the captions under work/ in {len(bad):,} "
        "place(s), e.g. " + "; ".join(f"{v} {w}"[:120] for v, w in bad[:2])
        + ". The nightly would check something other than what is here: "
          "python3 src/hearings/caption_span.py --write")
    return "ok", (f"{len(CS.load_summary() or {}):,} recordings summarised, each "
                  "agreeing with its caption files, and the same ones late "
                  "read either way")


@check("rollcalls", "the floor index reads every year's roll calls from 2025-2026 on, and only bills",
       needs=("build_floor_index",))
def _floor_every_year(build_floor_index):
    """build_floor_index read the download's roll calls alone -- one session
    year -- and the newest term of narratives.json, and read a docket floor
    action only where it had no roll call, taking the roll calls to have
    placed those. So 138 of 2025's 173 roll-call floor debates had no entry
    and their bills never linked the sitting, and at the new term the index
    would have been written with no 2025-2026 debate in it. It reads the
    archived years and every narratives term now, from FIRST_TERM on; a roll
    call is read once, from the first file holding it; and a roll call on
    something the docket does not know as a bill -- "HRULE64", the House
    adopting its rules -- is no bill's debate but still closes the window of
    the bill after it. A bill number typed another way, "HB 72", is keyed
    through rollcall_parser.bill_number as every other reader keys it, where it
    was upper-cased as typed and missed its bill. Driven end to end on a small
    tree."""
    BFI = build_floor_index
    assert BFI.FIRST_TERM == "2025-2026", (
        f"FIRST_TERM is {BFI.FIRST_TERM}: lowering it puts 2019-2024's floor debates on the "
        "site, which waits for a bench sample of those years (see its docstring)")
    tmp = Path(tempfile.mkdtemp(prefix="gr-floor-"))
    try:
        (tmp / "records" / "rollcalls").mkdir(parents=True)

        def put(name, lines):
            (tmp / name).write_text("\ufeff" + "\n".join(lines) + "\n", encoding="utf-8")
        put("videos_house_x.csv", [
            "video_id,title,title_parsed,parsed_committee,parsed_date,start_eastern,duration_iso",
            "v2025,House Session 2/6/2025,yes,House Session,2025-02-06,2025-02-06 10:00:00,PT5H",
            "v2023,House Session 3/9/2023,yes,House Session,2023-03-09,2023-03-09 10:00:00,PT5H"])
        put("RollCallSummary.txt", [
            "2026|H|1|1/7/2026 10:15:33 AM||321|2|34|38|||Call of the Roll|||",
            "2025|H|3|2/6/2025 10:20:00 AM|HB60|140|217|10|32|||The download's copy|tenancy|||"])
        put("records/rollcalls/RollCallSummary_2025.txt", [
            "2025|H|2|2/6/2025 10:10:00 AM|HRULE64|300|50|0|0|||Adopt|rules|||",
            "2025|H|3|2/6/2025 10:20:00 AM|HB60|140|217|10|32|||Adopt Floor Amendment|tenancy|||",
            "2025|H|4|2/6/2025 10:30:00 AM|HB60|217|139|11|32|||OTP|tenancy|||",
            # typed with a space, as 2017 S 198 typed "HB 315": still HB72's
            "2025|H|5|2/6/2025 10:40:00 AM|HB 72|200|150|10|32|||ITL|x|||"])
        put("records/rollcalls/RollCallSummary_2023.txt", [
            "2023|H|5|3/9/2023 11:00:00 AM|HB10|200|150|0|0|||OTP|x|||"])
        floor = lambda d, kind: {"type": "floor", "date": d, "body": "H",
                                 "vote_kind": kind, "action": "OTP"}
        (tmp / "narratives.json").write_text(json.dumps({
            "2023-2024": {"HB10": {"events": [floor("2023-03-09", "VV")]}},
            "2025-2026": {"HB60": {"events": [floor("2025-02-06", "RC")]},
                          "HB71": {"events": [floor("2025-02-06", "VV")]},
                          "HB72": {"events": [floor("2025-02-06", "RC")]}}}), encoding="utf-8")
        r = _run([sys.executable, str(Path(BFI.__file__).resolve()), "--videos", "videos_house_x.csv",
                  "--summary", "RollCallSummary.txt", "--narratives", "narratives.json",
                  "--out", "floor.json"], cwd=tmp, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, (r.stdout or "") + (r.stderr or "")
        got = json.loads((tmp / "floor.json").read_text(encoding="utf-8"))
        assert sorted(got) == ["HB60", "HB71", "HB72"], (
            f"the index holds {sorted(got)}: not HRULE64, which is not a bill, nor 2023's HB10, "
            "which is before FIRST_TERM, and HB72 though its roll call typed it 'HB 72'")
        (e72,) = got["HB72"]
        assert e72["precise"] and e72["window_start"] == 1800.0 and e72["debate_end"] == 2400.0, (
            f"HB72's roll call, typed 'HB 72', is not its debate from 30m to 40m: {e72}")
        (e,) = got["HB60"]
        assert e["precise"] and e["debate_end"] == 1800.0 and e["window_start"] == 600.0, (
            f"HB60 should close at 30m and open where the rules vote closed, at 10m: {e}")
        assert e["motions"] == ["The download's copy", "OTP"], (
            f"roll call 3 should be the download's copy, read once: {e['motions']}")
        assert got["HB71"][0]["precise"] is False, got["HB71"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("2025's archived roll calls placed, the download's copy first, a rules vote "
                  "left out but still a boundary, 'HB 72' read as HB72, and nothing before "
                  "FIRST_TERM")


@check("build", "the calendars' meetings kept between processes are the meetings the calendars "
       "give, and a check reads the calendars themselves", needs=("calendar_meetings",))
def _calendar_meetings_kept(CM):
    """calendar_meetings keeps each calendar's parse in .build_cache/ (30
    October 2026), keyed by its text and the code, for narrative.py's two
    runs and the next night. Laid out as a build has them, in calendars/ of
    the working folder: a second process parses nothing and gets the first's
    rows and unpaired lines; a calendar that changes is parsed again and its
    old answer is not kept; a load without cache=True parses and keeps
    nothing; and rows handed out are the caller's to change."""
    root = Path(tempfile.mkdtemp(prefix="gr-calendar-kept-"))
    try:
        for name in ("calendars/2026/HC001.txt", "calendars/2025/HC044.txt"):
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(CALENDAR_KINDS, encoding="utf-8")
        (root / "calendars/2025/HC044.txt").write_text(CALENDAR_KINDS.replace("2026", "2025"),
                                                       encoding="utf-8")
        code = "\n".join([
            "import sys, json",
            "sys.path.insert(0, sys.argv[1])",
            "import _paths",
            "import calendar_meetings as CM",
            "if sys.argv[2] in ('kept', 'nocache-boom'):",
            "    def boom(*a, **k):",
            "        raise SystemExit('a calendar was parsed again')",
            "    CM.parse = boom",
            "use = sys.argv[2] not in ('nocache', 'nocache-boom')",
            "years = [int(sys.argv[3])] if len(sys.argv) > 3 else None",
            "rows = CM.load('H', cache=use, years=years)",
            "if sys.argv[2] == 'twice':",
            "    for r in rows: r['date'] = 'changed'",
            "    rows = CM.load('H', cache=use)",
            "print(json.dumps([rows, [list(u) for u in CM.UNPAIRED]], ensure_ascii=False))"])

        def run(how, *more):
            return _run([sys.executable, "-c", code, str(_paths.ROOT), how, *more], cwd=root,
                        capture_output=True, text=True, timeout=120)
        cache = root / ".build_cache" / f"{CM.KEPT}.json.gz"
        plain = run("nocache")
        assert plain.returncode == 0, (plain.stderr or plain.stdout)[-400:]
        assert json.loads(plain.stdout)[0], "the fixture's calendars gave no meeting"
        assert not cache.exists(), "a load without cache=True kept a cache"
        boom = run("nocache-boom")
        assert boom.returncode != 0 and "parsed again" in (boom.stderr or ""), \
            "a load without cache=True did not read the calendars itself"
        first = run("read")
        assert first.returncode == 0 and first.stdout == plain.stdout, \
            "a cold cached load gives other rows than the calendars"
        assert cache.exists(), "a cached load kept nothing for the next process"
        second = run("kept")
        assert second.returncode == 0, "the second process parsed again: " + (second.stderr or "")[-300:]
        assert second.stdout == plain.stdout, "the kept rows are not the rows the calendars give"
        twice = run("twice")
        assert twice.returncode == 0 and json.loads(twice.stdout)[0] == json.loads(plain.stdout)[0], \
            "a caller's change to the rows reached the kept answer"
        c = root / "calendars/2026/HC001.txt"
        c.write_text(c.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        moved = run("kept")
        assert moved.returncode != 0 and "parsed again" in (moved.stderr or ""), \
            "a calendar changed and its kept answer was used"
        assert run("read").returncode == 0
        import build_cache as BC
        held = BC.load(CM.KEPT, CM._signature(), folder=root / ".build_cache")
        assert len(held) == 2, f"the cache holds {len(held)} answers for 2 calendars on disk"
        # TWO RUNS AT ONCE, each on its own year, as narrate_archive's four
        # processes are: both answers are kept, whichever finished last.
        cache.unlink()
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(2) as pool:
            both = list(pool.map(lambda y: run("read", y), ("2025", "2026")))
        assert all(r.returncode == 0 for r in both), [r.stderr[-200:] for r in both]
        held = BC.load(CM.KEPT, CM._signature(), folder=root / ".build_cache")
        assert len(held) == 2, (f"two runs at once left {len(held)} answers of 2: the last to "
                                "finish saved over the other's")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    src = _source(_paths.locate("narrative.py"))
    assert "cache=True" in src, "narrative.py no longer asks for the calendars' cache"
    return "ok", ("a second process parses no calendar and gets the first one's rows; a changed "
                  "calendar is parsed again and its old answer dropped; no cache unless asked")


@check("calendar", "a reversed meridiem is corrected, and the evening is left alone")
def _meridiem_window():
    """The one place this project rewrites what the record says.

    docket_parser._unslip turns "12:15 am" into 12:15 for a hearing that ran
    at quarter past noon. That is a deliberate narrowing of the usual rule,
    taken on 18 September 2026, and it is safe only because the window is
    narrow: 22:00 to 02:59, which nothing legitimate occupies, and only the
    meridiem, never a digit.

    What this check is really guarding is the EDGE. The evening is the thing
    that must not be swept in -- the House holds hearings off-site at six and
    eight in the evening on contested bills, and the docket carries "6:00 PM
    - 8:00 PM Kennet High School Auditorium" to prove it. Widen the window by
    two hours in either direction and real sittings start being moved by
    twelve hours, which would be the worst kind of error this site can make:
    a confident one, in the record's own voice.
    """
    import docket_parser as DP

    fixed = {
        "12:15AM": "12:15", "12:00AM": "12:00", "1:15AM": "13:15",
        "2:00AM": "14:00", "11:00PM": "11:00", "10:45PM": "10:45",
    }
    left = {
        # The evening, which is real and must never move.
        "6:00PM": "18:00", "8:00PM": "20:00", "5:30PM": "17:30",
        "9:00PM": "21:00",
        # Early, unusual, stated, and not corrected -- there is no second
        # reading of seven in the morning to prefer.
        "7:00AM": "07:00", "3:00AM": "03:00",
        # The ordinary committee day.
        "10:00AM": "10:00", "12:00PM": "12:00", "1:30PM": "13:30",
    }
    bad = []
    for s, want in list(fixed.items()) + list(left.items()):
        got = DP._parse_time(s)
        if got is None or got.strftime("%H:%M") != want:
            bad.append(f"{s} -> {got}, wanted {want}")
    assert not bad, ("_parse_time reads a time the window does not intend: "
                     + "; ".join(bad))
    assert DP._SLIP_HOURS == frozenset((22, 23, 0, 1, 2)), (
        f"the correction window is now {sorted(DP._SLIP_HOURS)}. It was "
        "22,23,0,1,2 -- the hours nothing legitimate occupies. Widening it "
        "moves real evening hearings by twelve hours; if the widening is "
        "wanted, change this check in the same edit and say what evidence "
        "moved it.")
    return "ok", (f"{len(fixed)} reversed meridiems corrected, "
                  f"{len(left)} real times left where the record put them")


@check("data", "no committee sits between ten at night and three in the morning")
def _no_night_sittings():
    """The correction above, measured on what actually shipped.

    Before it, 92 of the 99,234 stated times in proceedings.csv fell in that
    window, every one of them a clerk's reversed meridiem: each flipped into
    10:00-14:59, and 85 landed inside the same committee's own working day,
    several at the very minute a sibling row was set for.

    This reads the built table rather than the parser, so it fails if the
    manifests are stale -- which is the point. The parser can be right and the
    site still be showing the old times.
    """
    if not Path("proceedings.csv").exists():
        return "skip", "no proceedings.csv here; run build_proceedings.py first"
    import proceedings

    night, stated = [], 0
    for r in proceedings.load():
        tm = (r.get("time") or "").strip()
        if not tm or not (r.get("committee") or "").strip():
            continue
        stated += 1
        try:
            h = int(tm[:2])
        except ValueError:
            continue
        if h in (22, 23, 0, 1, 2):
            night.append(f'{r.get("date")} {tm} {r.get("committee")}')
    assert not night, (
        f"{len(night)} committee sittings are timed between 22:00 and 02:59, "
        "which is a reversed meridiem docket_parser should have corrected. "
        "The manifests are probably older than the parser -- rebuild them "
        f"with build_manifest.py. First few: {'; '.join(night[:3])}")
    return "ok", (f"{stated:,} stated committee times, none at night; "
                  "92 reversed meridiems were corrected at parse")


def _docket_file(rows):
    """A docket file of (year, lsr, bill, body, description) rows, in a scratch
    folder, as the database's dump writes them. Returns its path."""
    import tempfile
    path = Path(tempfile.mkdtemp()) / "Docket_db_1991-1992.txt"
    path.write_text("".join(
        f"{y}|{lsr}|01/05/{y} 10:00:00 AM|{b}|{body}|{d}|01/05/{y} 10:00:00 AM\n"
        for y, lsr, b, body, d in rows), encoding="utf-8")
    return path


@check("code", "a referral the clerk's line wrapped is read as one line, so a bill "
               "introduced 'and' / 'ref to Public Works' has its committee",
       needs=("referrals",))
def _referral_wrapped(referrals):
    """9 November 2026, the coverage audit: HB 785 of 1991 and SB 246 of 1993
    had no committee, because the docket breaks "INTRODUCED AND" / "REF TO
    PUBLIC WORKS;  HJ74" across two rows and the introduction pattern is
    anchored to one. Six Senate referrals of 1993-1996 were missing the same
    way (SB 173 and SB 667 among them)."""
    path = _docket_file([
        (1991, "1227", "HB785", "H", "REP GROSS SUSP RULES FOR INTRODUCTION, MA 2/3 VV; INTRODUCED AND"),
        (1991, "1227", "HB785", "H", "REF TO PUBLIC WORKS;  HJ74,P1710"),
        (1991, "1069", "SB246", "S", "SEN RUSSMAN SUSP RULES FOR INTRO, MA 2/3VV; INTRODUCED AND REF"),
        (1991, "1069", "SB246", "S", "TO TRANSPORTATION; SJ3,P39"),
        (1991, "1300", "HB900", "H", "INTRODUCED AND REF TO EXEC & ADMIN     HJ 13 ,P 138"),
    ])
    refs, _began = referrals._read_docket(str(path), "1991-1992")
    assert refs.get(("1991-1992", "HB785")) == {"H": "Public Works"}, refs.get(("1991-1992", "HB785"))
    assert refs.get(("1991-1992", "SB246")) == {"S": "Transportation"}, refs.get(("1991-1992", "SB246"))
    assert ("1991-1992", "HB900") in refs        # the one-row form still reads
    return "ok", "'INTRODUCED AND' / 'REF TO X' on two rows is one referral"


@check("code", "a bill whose docket never sends it to a committee is 'none on record', "
               "one that waived the referral on two rows too, and one referred is not",
       needs=("referrals",))
def _referral_none_on_record(referrals):
    """9 November 2026: the data page's Committee column read 96-99% because
    a resolution adopted the day it was introduced, and a bill passed under a
    suspension of the rules, were counted as committees this site had failed
    to read. The docket is the witness that they never had one."""
    path = _docket_file([
        (1991, "1", "HR5", "H", "INTRODUCED AND ADOPTED VV; HJ3,P32"),
        (1991, "2", "HB6", "H", "INTRODUCED AND REF TO EDUCATION; HJ4"),
        (1991, "3", "SCR1", "S", "Sen. Below susp. rules for intro. & no referral to comm. & notice in calendar &"),
        (1991, "3", "SCR1", "S", "no hearing and rpt in the calendar, 2nd rdg; MA 2/3 nec.;  OTP, MA, VV"),
        (1991, "4", "HB763", "S", "Sen. Boyce, Suspend Rules for Intro. & Without Ref. to Committee, 2/3 nec."),
        (1991, "5", "HB7", "H", "HEARING MAR04 01:00 RM306,LOB    FOR: EDUCATION"),
    ])
    none = referrals.unreferred({"1991-1992": str(path)})
    assert ("1991-1992", "HR5") in none and ("1991-1992", "SCR1") in none \
        and ("1991-1992", "HB763") in none, none
    assert ("1991-1992", "HB6") not in none and ("1991-1992", "HB7") not in none, none
    return "ok", "adopted and rules-waived bills are none on record; a referred or heard bill is not"
