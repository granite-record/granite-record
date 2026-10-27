#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.16
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

Hand-marked times are NOT here. They are in review/ground_truth.csv and join on
(video_id, bill, kind).

GRANITE_PROCEEDINGS, when set, names the file to read and write in place of
proceedings.csv. It exists so a candidate table can be built and scored in
scratch -- build_proceedings.py writes it, then the site builders and
probe_alignment.py run against it -- without the live table being touched.
build_site_v2, build_committees, build_exports, probe_alignment,
segment_markers and site_read follow it because they read through load() and
PATH. A tool that opens proceedings.csv by name does not: handoff.py reads the
live table.
"""

import csv
import os
import re
from collections import defaultdict
from pathlib import Path

# The live table, or the candidate GRANITE_PROCEEDINGS names (see above).
PATH = Path(os.environ.get("GRANITE_PROCEEDINGS") or "proceedings.csv")

# WHERE THE VIDEO INDEXES ARE (the root tidy, 8 October 2026). The channel
# indexes fetch_channel_index.py writes, which git keeps, are in
# collected/videos/. The night's new livestreams, which livestreams.py
# writes and the kit carries from one night to the next and git never
# holds, are videos_<chamber>_livestreams.csv at the root, beside the
# day's other files. Every reader takes both, through video_indexes().
VIDEO_DIR = Path("collected") / "videos"


def video_indexes(root="."):
    """Every video index here: collected/videos/videos_*.csv and any
    videos_*.csv at the root (the night's livestreams), in the order of
    their file names -- the order one glob of the root gave while both
    were there, which decides the first of two rows for one recording."""
    root = Path(root)
    found = list((root / VIDEO_DIR).glob("videos_*.csv")) + list(root.glob("videos_*.csv"))
    return sorted((p for p in found if p.is_file()), key=lambda p: (p.name, p.as_posix()))


# WHAT EACH RECORDING SAYS OF ITSELF (the Videos tab, 26 October 2026: the
# owner asked for a body's recordings "in a structured table with the date,
# list of bills, and other pertinent information"). One reader of every video
# index for the three pages that list recordings -- a committee's, a chamber's
# and a study committee's -- so none of them reads a subset. From each row:
# the channel, which is the chamber (videos_house_*, videos_senate_*); the
# committee its title names as the index parsed it ("Finance", "Finance
# Division II", "Session"; empty for a title in the older form, "Education
# 1/26/21", which the index could not parse); its day, the title's or else the
# stream's; when the stream began, YouTube's own start in Eastern time; and
# how long it ran. A scheduled stream that has not run carries no start and a
# length of nothing ("P0D"): it is not `streamed`, and no page lists it.
# Where two rows name one recording -- the night's livestreams beside the
# channel's own -- the row that knows more is kept (a length once it is over,
# a start while it was live), the first of equals in video_indexes' order.
_LENGTH = re.compile(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?")


def iso_seconds(s):
    """"PT1H52M3S" -> 6723; 0 for no length, "P0D", or one that will not read."""
    m = _LENGTH.fullmatch(str(s or "").strip())
    if not m or not any(m.groups()):
        return 0
    d, h, mi, sec = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + sec


def video_facts(root="."):
    """{video_id: {"date", "chamber" ("H"|"S"|""), "title", "parsed_committee",
    "began" ("13:13", or ""), "seconds" (int, 0 where unknown), "streamed"}}
    out of every video index here (video_indexes). Standard library; asks
    nobody anything."""
    out, knows = {}, {}
    for f in video_indexes(root):
        ch = {"house": "H", "senate": "S"}.get(f.name.split("_")[1] if f.name.count("_") else "", "")
        try:
            fh = open(f, encoding="utf-8-sig", newline="")
        except OSError:
            continue
        with fh:
            for r in csv.DictReader(fh):
                vid = (r.get("video_id") or "").strip()
                if not vid:
                    continue
                start = (r.get("start_eastern") or "").strip()
                secs = iso_seconds(r.get("duration_iso"))
                began = start[11:16] if re.match(r"\d{4}-\d\d-\d\d \d\d:\d\d", start) else ""
                rank = 2 if secs else 1 if began else 0
                if vid in out and rank <= knows[vid]:
                    continue
                day = (r.get("parsed_date") or "").strip()[:10] or start[:10]
                parsed = (r.get("title_parsed") or "").strip().lower() == "yes"
                out[vid] = {"date": day if re.fullmatch(r"\d{4}-\d\d-\d\d", day) else "",
                            "chamber": ch, "title": (r.get("title") or "").strip(),
                            "parsed_committee": (r.get("parsed_committee") or "").strip()
                            if parsed else "",
                            "began": began, "seconds": secs, "streamed": bool(began or secs)}
                knows[vid] = rank
    return out

COLS = ["term", "bill", "body", "kind", "date", "time", "committee", "venue",
        "video_id", "video_title", "stream_start", "predicted_offset", "match",
        "debate_end", "window_start", "precise", "motions", "tallies",
        "whole_video", "source",
        # Where a committee row's meeting or its committee name came from,
        # when that was a calendar's notice. Empty on every other row.
        "calendar", "noticed", "committee_from", "notice_times",
        # The recordings this sitting COULD be, where more than one exists for
        # its committee that day and nothing in the record says which. Empty on
        # every row that got a pick. 317 rows carry it, across 64 committee-days
        # -- 236 of them Finance divisions, which stream separately, and 81 the
        # clock could not separate. The page names them all and picks none.
        #
        # Named here or dropped: write() emits only the columns COLS lists, so
        # a field a builder sets and this list omits vanishes without a word.
        # build_proceedings.py warns when it has these rows and this entry is
        # missing, because that is the failure it would otherwise be.
        "candidate_ids"]

FLOOR_KINDS = {"floor debate", "committee of conference"}


def term_of(date_str):
    """'2026-02-03' -> '2025-2026'. A biennium starts in the odd year."""
    try:
        y = int(str(date_str)[:4])
    except (TypeError, ValueError):
        return ""
    start = y if y % 2 else y - 1
    return f"{start}-{start + 1}"


# ORGANIZATION DAY BELONGS TO THE NEXT TERM (6 October 2026). The General
# Court that was elected in November organizes on the first Wednesday of
# December of the even year -- 2 December 2026 -- and elects its Speaker and
# adopts its rules that day: the next term's business, in the old term's
# calendar year. The docket files the day's resolutions under the next
# session (HR 1 of 2025, "Introduced and Adopted VV 12/04/2024"), and a roll
# call is keyed by its session year everywhere a term is asked of it; one
# filed under the old year would have gone with 2025-2026 -- set aside as a
# stray row of a frozen term (build_data.rows_all), its ballots tallied with
# that term's members and linked to that term's bills. No roll call file on
# disk holds one yet (0 of 9,565), so this is the rule, not a correction of
# anything published: a roll call taken on or after Organization Day of an
# even year is the next term's, whatever year it is filed under.

def organization_day(year):
    """The first Wednesday of December of an even `year`, as a date; None
    for an odd year or one that is not a year."""
    import datetime as _dt
    try:
        y = int(str(year)[:4])
    except (TypeError, ValueError):
        return None
    if y % 2:
        return None
    first = _dt.date(y, 12, 1)
    return first + _dt.timedelta(days=(2 - first.weekday()) % 7)


def vote_day(when):
    """A roll call's day, from "2026-12-02" or "12/2/2026 10:30:00 AM", as a
    date; None where it gives none."""
    import datetime as _dt
    s = str(when or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s) or re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if not m:
        return None
    a, b, c = (int(x) for x in m.groups())
    try:
        return _dt.date(a, b, c) if a > 31 else _dt.date(c, a, b)
    except ValueError:
        return None


def _vote_term(year, when=""):
    """vote_term's reading, worked out afresh on every call: what the memo
    below keeps."""
    day = vote_day(when)
    org = organization_day(day.year) if day else None
    if org and day >= org:
        return term_of(day.year + 1)
    return term_of(year)


# ONE READING FOR EACH YEAR AND DAY (16 October 2026, private/SITE_DATA_PROFILE.md,
# P1). The site data step asked vote_term 13,133,383 times, about six times for
# each of 2,303,047 ballots, and the ballots hold only 718 different (year,
# day) pairs between them; each call matched two patterns, built a date and
# worked out Organization Day, about 65 seconds in all. The answer depends on
# its two arguments and nothing else, so it is kept the first time and handed
# back after. The types are part of the key because 1 and True, or 1 and 1.0,
# are one key to a dict and print differently, and term_of reads the printed
# form. An argument that cannot be a key (a list, say) is read afresh, as it
# always was, rather than raising where it never raised before.
_VOTE_TERMS = {}


def vote_term(year, when=""):
    """The term a roll call belongs to: its session year's, or the next
    term's where it was taken on or after Organization Day of an even year
    (ORGANIZATION DAY BELONGS TO THE NEXT TERM)."""
    key = (year, when, type(year), type(when))
    try:
        return _VOTE_TERMS[key]
    except KeyError:
        pass
    except TypeError:
        return _vote_term(year, when)
    term = _VOTE_TERMS[key] = _vote_term(year, when)
    return term


# A DAY'S TERM, FOR WHAT IS DATED AND FILED UNDER NO SESSION YEAR (18 October
# 2026, private/UNATTENDED_AUDIT_2026-10-18.md, section 2). A floor debate, a
# hearing or a recording carries a day and nothing else, and term_of(day)
# files Organization Day's business under the term that day ends. It already
# had: the House's and the Senate's resolutions of 4 December 2024 -- HR 1 to
# 5 and SR 1 to 5 of 2025, the rules and the officers of 2025-2026 -- were 10
# floor rows of proceedings.csv filed under 2023-2024, so 2023's HR 1, its
# own rules resolution, showed the recording of the 2024 Organization Day as
# its floor debate. On 2 December 2026 the same would have happened to
# 2027-2028's. term_on is vote_term with the day for the year.

def term_on(day):
    """The term a day falls in: "2026-12-01" -> "2025-2026", "2026-12-02",
    Organization Day, -> "2027-2028". "" for no day."""
    s = str(day or "").strip()
    return vote_term(s[:4], s) if re.match(r"\d{4}-\d\d-\d\d", s) else term_of(s)


# A term as this project writes one. Several derived files are {term: {...}}
# because a bill number is unique within a term and not across terms, and the
# test for "is this the new shape" belongs in one place rather than in each of
# them.
TERM_RE = re.compile(r"^\d{4}-\d{4}$")


def term_keyed(data):
    """Is this a {term: {...}} file rather than one keyed on bill number?"""
    return bool(data) and all(TERM_RE.match(k) for k in data)


# THE TERM THE SESSION'S OWN FILES DESCRIBE (5 October 2026). The newest term
# a derived file holds is not it: at the turn data/bills.json keeps 2025-2026
# while the day files already name 2027. Six of the General Court's files say
# which session year each row is of, and the newest of them is the session's.
# Read off the files every time it is asked, so a reader never carries one
# night's answer into the next.
#
# THE SAME SIX THE TURN GUARD READS (the review of 5 October 2026). This read
# Docket.txt and LSRs.txt alone while snapshot_gencourt.judge read all six, so
# sponsor files naming 2027 before the docket did were refused as a new term
# on a scheduled night, taken by the New term run -- and then built as
# 2025-2026's, the 2027 rows filed by number onto 2025-2026 bills, HB 10's
# nine sponsors replaced by one. One definition: the column each file gives
# its session year in (freeze_term.YEAR_COLUMN and snapshot_gencourt's, which
# preflight holds to this).
SESSION_FILES = ("Docket.txt", "LSRs.txt", "LsrSponsors.txt", "LsrsOnly.txt",
                 "RollCallSummary.txt", "RollCallHistory.txt")
SESSION_YEAR_COLUMN = {"Docket.txt": 0, "LSRs.txt": 0, "LsrSponsors.txt": 0,
                       "LsrsOnly.txt": 3, "RollCallSummary.txt": 0,
                       "RollCallHistory.txt": 0}


def session_term(folder="."):
    """The term of the newest session year any of SESSION_FILES in `folder`
    names, each in its own column (SESSION_YEAR_COLUMN); "" when none is
    there or names a year."""
    newest = ""
    for name in SESSION_FILES:
        p = Path(folder) / name
        if not p.exists():
            continue
        col = SESSION_YEAR_COLUMN[name]
        with p.open(encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                f = line.lstrip("﻿").split("|", col + 1)
                y = f[col].strip() if len(f) > col else ""
                if len(y) == 4 and y.isdigit() and y > newest:
                    newest = y
    return term_of(newest) if newest else ""


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


def same_minute(a, b):
    """Are two "HH:MM" clocks within five minutes of each other? True where
    either is unknown."""
    try:
        ha, ma = (int(x) for x in str(a).split(":")[:2])
        hb, mb = (int(x) for x in str(b).split(":")[:2])
    except ValueError:
        return True
    return abs((ha * 60 + ma) - (hb * 60 + mb)) <= 5


def voided(row, meeting):
    """Is this row of the table the meeting `meeting` names -- [day, chamber,
    kind, "HH:MM" or ""], one a later row of the docket cancelled or moved
    (narrative.voided_meetings)? Its day, its kind ("hearing" is a "public
    hearing" too, "work session" a subcommittee's or the full committee's),
    its chamber where the row gives one and its hour where both give one."""
    day, body, kind, at = (list(meeting) + ["", "", "", ""])[:4]
    k = (row.get("kind") or row.get("what") or "").strip().lower()
    b = (row.get("body") or "").strip().upper()
    return (bool(kind) and (row.get("date") or "-") == day and kind in k
            and (not b or b == body) and same_minute((row.get("time") or "").strip(), at))


def notice_only(row, narr):
    """Is this committee row the docket's notice of a sitting and nothing more:
    one set for a bill that was never introduced, or for a day after the bill
    was withdrawn?

    The table reads the docket's notices -- "Public Hearing: 1/12/2012 10:30 AM
    LOB 207", entered on 15 December -- and a notice is entered before the
    day. HB 1284 of 2012 was withdrawn on 4 January, never introduced, with a
    hearing set for the 12th and an executive session for the 24th; HB 1512
    was introduced and withdrawn that morning, with a hearing set for the
    12th; HB 273 of 2017 is a bill the House's resolution of introduction
    steps over, with a hearing set for 10 January and nothing on disk to say
    whether anybody met. Four rows of the table on 2 October 2026. They stay
    in it, because it holds what the docket scheduled, and the recordings are
    matched against that.

    AND A DAY THE BILL'S HISTORY DOES NOT PUT A SITTING ON ("no_sitting"). Two
    more rows: SB 106 of 2009's Senate hearing at 10 January 2009, the day its
    notice states -- 25 days before the bill was introduced, the clerk's slip
    for the 10 February that Senate Calendar 10 prints, which no rule here can
    prove and so no page states -- and HA 1 of 2008's hearing set for 25 April
    2008, two days after the House took the address from its joint committee
    and laid it on the table.

    AND A MEETING A LATER ROW OF THE DOCKET CANCELLED OR MOVED ("voided"):
    that meeting, by its day, kind, chamber and hour (voided), and not the
    rest of its day. HB 650 of 2014's Finance hearing of 18 February at ten
    was cancelled, and its work session that day at one was held.

    `narr` is the bill's history as narrative.build tells it, which dates a
    withdrawal ("withdrawn"), says where a bill was never introduced
    ("not_introduced") and lists those days ("no_sitting"); None, for a bill
    with no history, is no notice.

    ONE RULE FOR EVERYTHING THAT SAYS A COMMITTEE SAT ON A BILL: the bill's
    own stations (build_site_v2), its committee's days (build_committees),
    the download (build_exports) and the Learn pages' count of hearings
    (build_civics). It was written into the first alone, then into the first
    two from the stations a page lacked, and through both the download went
    on listing HB 273's hearing under a committee its own page says the bill
    never reached. Never a floor row: a withdrawal the chamber voted is a
    floor action itself, and a conference is not a committee's sitting.
    """
    if (row.get("kind") or "").strip().lower() in FLOOR_KINDS:
        return False
    narr = narr or {}
    if narr.get("not_introduced"):
        return True
    gone = narr.get("withdrawn") or ""
    return ((bool(gone) and (row.get("date") or "") > gone)
            or (row.get("date") or "-") in (narr.get("no_sitting") or ())
            or any(voided(row, m) for m in narr.get("voided") or ()))


def sittings(rows, histories):
    """(the rows a body sat for, the bare notices among them): `rows` parted
    by notice_only, each row asked of its own bill's history. `histories` is
    narratives.json as it is written, {term: {bill: history}}.

    One place looks the history up, by the term and the bill the row itself
    carries, so that a reader cannot key it another way: a lookup that misses
    finds no notice and keeps every row, which is the failure that says
    nothing."""
    kept, notices = [], []
    for r in rows:
        narr = ((histories or {}).get(r.get("term")) or {}).get(r.get("bill"))
        (notices if notice_only(r, narr) else kept).append(r)
    return kept, notices


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
