#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.4
"""
Read proceedings.csv. Every tool that needs to know what happened on which
recording imports this and nothing else.

    from proceedings import load, by_video, floor_only, term_of

Why one reader: for a whole day, floor debates lived in floor_index.json and
committee proceedings in verification_manifest.csv, in different shapes with
different keys. Five separate tools were taught the manifest and then, one at a
time, found not to know the floor existed. Each fix was a different bug with
the same cause. A single file with a single reader removes the cause.

A row is one (bill, date, kind, recording). Times are seconds into the
recording. Columns:

  term            2025-2026 -- the biennium, because bill numbers repeat across
                  terms and everything archival will be keyed on this
  bill            HB1442
  body            H or S
  kind            public hearing | hearing | executive session | work session |
                  subcommittee work session | full committee work session |
                  floor debate | committee of conference
  date            2026-02-03
  time            10:00, or empty for the floor
  committee       empty for the floor
  venue
  video_id        empty when nothing was matched
  video_title
  stream_start    2026-02-03 09:12:44, the livestream's start
  predicted_offset  seconds: the schedule's guess, or the floor window's start
  match           how the recording was chosen
  debate_end      floor only: the roll call's clock time, seconds in
  window_start    floor only: the previous bill's last roll call
  precise         floor only: true when debate_end came from the clock
  motions         floor only, joined with " | "
  tallies         floor only, joined with " | "
  whole_video     true when the title names the bill (conference committees)
  source          docket | calendar | floor_index -- where this row came from:
                  docket, read from the General Court's docket; calendar, a
                  meeting announced in the House or Senate Calendar that the
                  part of the docket this site reads does not have; floor_index,
                  a floor debate. A table written before calendar rows existed
                  says manifest where it now says docket.
  calendar        the calendar that announced the meeting, 2003/HC012: on every
                  calendar row, and on a docket row whose committee came from it
  noticed         calendar rows: the day that calendar was printed
  committee_from  calendar, on a docket row whose committee name was taken from
                  the calendar's notice for that bill and day
  notice_times    calendar rows: 10:00;13:00 when the notice gives the bill more
                  than one time that day, and time is then empty

Hand-marked times are NOT here. They are in ground_truth.csv and join on
(video_id, bill, kind).

GRANITE_PROCEEDINGS, when set, names the file to read and write in place of
proceedings.csv. It exists so a candidate table can be built and scored in
scratch -- build_proceedings.py writes it, then the site builders and
probe_alignment.py run against it -- without the live table being touched.
build_site_v2, build_committees, build_exports, probe_alignment,
segment_markers and site_read follow it because they read through load() and
PATH. A tool that opens proceedings.csv by name does not: handoff.py reads the
live table, and caption_gaps.py whatever its --proceedings says.
"""

import csv
import os
import re
from collections import defaultdict
from pathlib import Path

# The live table, or the candidate GRANITE_PROCEEDINGS names (see above).
PATH = Path(os.environ.get("GRANITE_PROCEEDINGS") or "proceedings.csv")

COLS = ["term", "bill", "body", "kind", "date", "time", "committee", "venue",
        "video_id", "video_title", "stream_start", "predicted_offset", "match",
        "debate_end", "window_start", "precise", "motions", "tallies",
        "whole_video", "source",
        # Where a committee row's meeting or its committee name came from,
        # when that was a calendar's notice. Empty on every other row.
        "calendar", "noticed", "committee_from", "notice_times"]

FLOOR_KINDS = {"floor debate", "committee of conference"}


def term_of(date_str):
    """'2026-02-03' -> '2025-2026'. A biennium starts in the odd year."""
    try:
        y = int(str(date_str)[:4])
    except (TypeError, ValueError):
        return ""
    start = y if y % 2 else y - 1
    return f"{start}-{start + 1}"


# A term as this project writes one. Several derived files are {term: {...}}
# because a bill number is unique within a term and not across terms, and the
# test for "is this the new shape" belongs in one place rather than in each of
# them.
TERM_RE = re.compile(r"^\d{4}-\d{4}$")


def term_keyed(data):
    """Is this a {term: {...}} file rather than one keyed on bill number?"""
    return bool(data) and all(TERM_RE.match(k) for k in data)


def per_term(data, term, current=""):
    """One term's rows out of a per-bill file, tolerating the flat old shape.

    Every per-bill file here was keyed on the bill number alone before a second
    term existed, and they are being converted one at a time. A file still in
    the flat shape holds the CURRENT term and nothing else, so an archived term
    must read nothing from it rather than the current term's record for the
    same number: HB100 exists in every biennium, and the wrong sponsors are
    worse than no sponsors. Passing no `current` treats a flat file as
    answering for whatever term is asked, which is what a tool that knows it is
    working on one term wants.
    """
    if not data:
        return {}
    if term_keyed(data):
        return data.get(term, {})
    return data if (not current or term == current) else {}


def in_term(data, current_term):
    """A flat-or-termed file rewritten as {term: {...}}, ready to merge into.

    The counterpart of per_term for a writer. A flat file is taken to be the
    current term's, which is what it was; a file already keyed on the term is
    returned as it is. Neither loses a term the caller is not writing -- a
    writer run on a subset that replaces the whole file is how the manifest
    lost its hand-marked times twice.
    """
    if not data:
        return {}
    if term_keyed(data):
        return dict(data)
    return {current_term: dict(data)} if current_term else {}


def for_term(data, term=None):
    """One term out of a {term: {...}} file; the most recent by default.

    The default is what every tool working on the current session wants, and
    is the reason a reader that has no notion of terms keeps working once the
    file it reads grows a second one.
    """
    if not data:
        return {}
    return data.get(term or max(data), {})


def _num(v):
    if v in (None, "", "None"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _bool(v):
    return str(v).strip().lower() in ("1", "true", "yes", "y")


def load(path=PATH):
    """All rows, typed. Empty list if the file is not there."""
    p = Path(path)
    if not p.exists():
        return []
    out = []
    with p.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            r["predicted_offset"] = _num(r.get("predicted_offset"))
            r["debate_end"] = _num(r.get("debate_end"))
            r["window_start"] = _num(r.get("window_start"))
            r["precise"] = _bool(r.get("precise"))
            r["whole_video"] = _bool(r.get("whole_video"))
            r["motions"] = [m for m in (r.get("motions") or "").split(" | ") if m]
            r["tallies"] = [t for t in (r.get("tallies") or "").split(" | ") if t]
            r["bill"] = (r.get("bill") or "").strip().upper()
            r["kind"] = (r.get("kind") or "").strip().lower()
            r["video_id"] = (r.get("video_id") or "").strip()
            out.append(r)
    return out


def by_video(rows=None):
    """{video_id: [rows]} for rows that have a recording."""
    rows = load() if rows is None else rows
    out = defaultdict(list)
    for r in rows:
        if r["video_id"]:
            out[r["video_id"]].append(r)
    return dict(out)


def bills_on(video_id, rows=None):
    """Bills scheduled on one recording, in the file's order, no repeats."""
    seen, out = set(), []
    for r in (by_video(rows).get(video_id) or []):
        if r["bill"] not in seen:
            seen.add(r["bill"])
            out.append(r["bill"])
    return out


def floor_only(rows=None):
    rows = load() if rows is None else rows
    return [r for r in rows if r["kind"] in FLOOR_KINDS]


def committee_only(rows=None):
    rows = load() if rows is None else rows
    return [r for r in rows if r["kind"] not in FLOOR_KINDS]


def floor_videos(rows=None):
    """Recordings that are floor sessions to segment (not whole-video ones)."""
    return {r["video_id"] for r in floor_only(rows)
            if r["video_id"] and not r["whole_video"]}


def whole_videos(rows=None):
    """Recordings whose title names the bill -- nothing to segment."""
    return {r["video_id"] for r in (load() if rows is None else rows)
            if r["video_id"] and r["whole_video"]}


def write(rows, path=PATH):
    """Only build_proceedings.py calls this."""
    with Path(path).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            o = dict(r)
            o["motions"] = " | ".join(r.get("motions") or [])
            o["tallies"] = " | ".join(r.get("tallies") or [])
            o["precise"] = "true" if r.get("precise") else ""
            o["whole_video"] = "true" if r.get("whole_video") else ""
            for k in ("predicted_offset", "debate_end", "window_start"):
                if o.get(k) is None:
                    o[k] = ""
            w.writerow({c: o.get(c, "") for c in COLS})
