#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.12
"""
Join the docket to the video index. Produces a verification manifest with the
video ID and predicted offset already filled in, so the manual pass is only
"watch and mark boundaries" rather than "go find the video first."

Needs docket_parser.py in the same folder.

    python3 build_manifest.py --videos videos_house_2025-01-01_to_2025-03-31.csv

Downloads Docket.txt automatically unless you pass --docket with a local copy.
Standard library only.
"""

import argparse
import csv
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import docket_parser
    from docket_parser import (parse_rows, build_referral_timeline,
                               parse_proceedings, build_sittings)
except ImportError:
    sys.exit("Put docket_parser.py in this same folder, then rerun.")

# Named so the error above can print it. Nothing here requests it: this is
# a build script and fetching is fetch_*'s job.
DOCKET_URL = "https://gc.nh.gov/dynamicdatadump/Docket.txt"

# Committee names differ between the docket and the video titles. Left side is
# what appears in a video title; right side is what the docket referral says.
TITLE_TO_DOCKET = {
    "Committee on Housing": "Housing",
}

# Finance splits into three divisions on the video side, but a bill's referral
# row only ever says "Finance". Division assignment is not in the docket, so a
# Finance bill matches up to four videos on a given day and cannot be resolved
# from this data alone.
AMBIGUOUS_FAMILIES = {"Finance"}

# Titles carrying a bill number align themselves -- no transcript needed.
# Must match build_floor_index.py exactly: both decide whether a recording
# names its bill, and disagreeing means a video is exact in one view and
# unmatched in the other. HJR was missing here, and so was case tolerance.
BILLS_IN_TITLE = re.compile(
    r"\b(HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s?(\d+)\b", re.I)


def norm_title_committee(c):
    c = re.sub(r"\s+Work Session on .*$", "", c)
    c = re.sub(r"\s+(Afternoon\s+)?Subcommittee Work Session$", "", c)
    c = re.sub(r"\s+Work Session$", "", c)
    c = TITLE_TO_DOCKET.get(c.strip(), c.strip())
    return c


def family(c):
    """Finance Division II -> Finance. Everything else unchanged."""
    m = re.match(r"^(Finance)\b", c)
    return m.group(1) if m else c


# ---- the title's committee, said the way the docket says it ---------------
#
# The join below is on the committee STRING, and the two sources spell it
# differently: "Senate Education Committee Remote Public Hearing" against the
# docket's "Education and Workforce Development", "Commerce Committee" against
# "Commerce", "Science, Technology, and Energy" against "Science, Technology
# and Energy". Keyed on the raw string, 2,144 proceedings since May 2020 said
# no recording existed on a day their own chamber had recorded one.
#
# ROSTER is the docket's own committee names for that chamber and term, so
# nothing here invents a committee: a title resolves to a name the General
# Court used in that term, or it does not resolve and the string is left
# exactly as it was.
WORD = re.compile(r"[A-Za-z0-9]+")

# What may follow a committee's name and still be that committee. Every word
# was read off a real title: "Commerce Committee Remote Public Hearing",
# "Judiciary Afternoon", "Education Exec Session", "Senate Finance Committee
# Agency Budget Presentations-April 12", "Public Works and Highways (5/5/21
# full video downloaded from Zoom)", "Executive Departments and Administration
# LOB 306/308", "Senate Transportation Committee Public Hearing on HB 1135 and
# Amendment to HB 1135", "Special Committee on Redistricting - Community Input
# Session".
#
# What is NOT in this list is the point. "Division" is absent, so "Finance
# Division III" never collapses into "Finance" and AMBIGUOUS_FAMILIES keeps
# its job. "Oversight" and "Council" are absent, so "Health and Human Services
# Oversight Committee" (60 rows) and "New Hampshire Transportation Council"
# stay unresolved rather than handing a joint body's recording to a standing
# committee's hearings. Likewise "Higher": "Public Higher Education Study
# Committee" abbreviates to "Public", which prefixes nothing else the House
# has, and would otherwise have become Public Works and Highways.
NOISE = set("""
committee committees subcommittee
public hearing hearings remote meeting meetings session sessions
executive exec work full stream continued afternoon morning evening
deliberations budget briefing agency presentations orientation
community input zoom download downloaded from video entire part
lob sh room on of the to for with w audio no amendment amendments
hb sb cacr hr sr hcr scr hjr jr fn a l
january february march april may june july august september october
november december jan feb mar apr jun jul aug sept sep oct nov dec
monday tuesday wednesday thursday friday
""".split())


def canon(s):
    """Committee name as comparable words. "&" is spelled out and "and" is
    dropped, because the clerk writes all three of "Health, Human Services and
    Elderly Affairs", "Health and Human Services and Elderly Affairs" and
    "Executive Departments & Administration" for committees the docket names
    once."""
    return " ".join(w for w in WORD.findall(s.replace("&", " and ").lower())
                    if w != "and")


def _all_noise(words):
    return all(w.isdigit() or w in NOISE for w in words)


def resolve_committee(name, roster):
    """The docket's name for this committee, or None if it cannot be said.

    Two ways a title names a committee, and a tail of meeting words after
    either one:

      "Commerce Committee Remote Public Hearing" -- the docket's whole name,
      then noise.

      "Senate Education (01/13)" in the 2019-2020 term -- an abbreviation of
      "Education and Workforce Development", accepted only when exactly one
      committee on that chamber's roster begins with those words.

    None means leave the string alone. That is the safe answer: an unresolved
    title matches nothing, which is what it did before.
    """
    words = canon(name).split()
    if not words or not roster:
        return None
    for n in range(len(words), 0, -1):
        if " ".join(words[:n]) in roster:
            return (roster[" ".join(words[:n])]
                    if _all_noise(words[n:]) else None)
    for n in range(len(words), 0, -1):
        hits = {r for c, r in roster.items() if c.split()[:n] == words[:n]}
        if len(hits) > 1:
            return None
        if len(hits) == 1:
            return hits.pop() if _all_noise(words[n:]) else None
    return None


def build_roster(procs):
    """{body: {canon name: the docket's name}} from this term's proceedings."""
    roster = {}
    for p in procs:
        if p.committee:
            roster.setdefault(p.body, {}).setdefault(canon(p.committee),
                                                     p.committee)
    return roster


# WHAT THE CHANNEL INDEX COULD NOT PARSE, READ AGAIN FROM ITS OWN TITLE.
#
# fetch_channel_index.py writes title_parsed=NO and leaves parsed_committee
# and parsed_date empty when TITLE_RE misses, and _load_one used to drop those
# rows. 459 of the 510 rows in videos_senate_2019-01-01_to_2022-12-31.csv are
# such rows -- the whole Senate channel from May 2020 to the end of 2022,
# because the Senate's clerk wrote "Senate Judiciary (01.11)" and "Senate
# Health and Human Services Committee Public Hearing" where the House writes
# "House Election Law (03/07/2025)". Only 11 of the 459 take one fixed shape.
#
# Re-reading them here rather than re-fetching: fetch_channel_index.py has no
# --reparse, the index is on disk, and a parser is allowed to be wrong without
# costing a request to somebody else's server.
#
# The leading phrase the clerk puts before the committee, from the real
# titles: "Public Hearing of the NH Senate Executive Departments and
# Administration Committee", "Remote Public Hearing of the Senate Education
# Committee", "NH Senate Executive Departments & Administration Committee".
# It is a closed list on purpose -- "Joint Legislative Education Committee
# Hearing" and "Remote Meeting of Joint Education Committee" must NOT reduce
# to Education, and they do not, because "Joint" is not a way to open a title.
RECOVER_LEAD = re.compile(
    r"^\s*(?:(?:remote\s+)?(?:public\s+hearing|hearing|meeting|work\s+session|"
    r"executive\s+session)s?\s+(?:of|on)\s+(?:the\s+)?)?"
    r"(?:(?:nh|n\.?h\.?|new\s+hampshire)\s+)?"
    r"(?:(?:senate|house)\s+)?", re.I)

# A date with a year, anywhere in the title. Only used where the row has no
# livestream start time at all: "Ways and Means (5/5/21 full download from
# Zoom)" is one of four such rows and carries its date nowhere else.
RECOVER_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")


def recover_title(row, roster_for_body):
    """(committee, date) for a row the channel index could not parse.

    The date comes from start_eastern, not from the title: it is the moment
    the stream actually went live, it is present on 455 of the 459, and 190 of
    those titles carry no year -- "Senate Commerce (04/05)". Where the two are
    both present and disagree the title is the one that is wrong: the clerk
    typed "Administrative Rules (01/19/23)" on a stream that went out on
    19 January 2024.
    """
    cmte = resolve_committee(RECOVER_LEAD.sub("", row["title"], count=1),
                             roster_for_body)
    if not cmte:
        return None, None
    if row.get("start_eastern"):
        return cmte, row["start_eastern"][:10]
    m = RECOVER_DATE.search(row["title"])
    if m:
        mo, d, y = (int(x) for x in m.groups())
        y += 2000 if y < 100 else 0
        try:
            return cmte, date(y, mo, d).isoformat()
        except ValueError:
            return None, None
    return None, None


def load_videos(paths, roster=None):
    """Read one or more video index CSVs, tagging each row with its chamber.

    The chamber comes from the filename, since fetch_channel_index.py names
    them videos_house_... and videos_senate_..., and the CSV itself does not
    record which channel it came from.

    `roster` is {body: {canon name: docket name}} from this term's docket. It
    is what lets a title be read against the committees that actually sat;
    without it this behaves exactly as it did before, which is what a caller
    with no docket to hand should get.
    """
    if isinstance(paths, str):
        paths = [paths]

    # Expand patterns here rather than relying on the shell: Windows cmd does
    # not glob, so "videos_*.csv" arrives as a literal. Passing a pattern is
    # the only way to avoid typing six filenames exactly right, and typing
    # them exactly right is what has failed twice.
    files = []
    for pat in paths:
        if any(c in str(pat) for c in "*?["):
            hits = sorted(Path(".").glob(str(pat)))
            if not hits:
                sys.exit(f"Nothing matches {pat}")
            files.extend(hits)
        else:
            f = Path(pat)
            if not f.exists():
                near = sorted(x.name for x in Path(".").glob("videos_*.csv"))
                sys.exit(f"No {pat}.\n"
                         + ("These are here:\n  " + "\n  ".join(near)
                            if near else "No videos_*.csv here at all.")
                         + "\n\nOr just pass --videos \"videos_*.csv\" and let "
                           "it find them.")
            files.append(f)

    # The same recording can appear in two indexes whose date ranges overlap.
    # Counted twice it would look like a committee streamed the same sitting
    # on two channels, and the day would be treated as ambiguous.
    #
    # The first file's row is kept -- UNLESS a later one knows more about
    # the stream. The index lists a stream the day it is scheduled, so a row
    # can say P0D with no start for a hearing that has since been held, or
    # carry a start and P0D for one that was still live; livestreams.py
    # writes the later answer into its own file rather than into a committed
    # one, and that row has to win or the recording keeps no start, no length
    # and no predicted offset. No two rows on disk on 25 September were in
    # that relation, so this changed no manifest built that day.
    out, seen, dupes, later = [], {}, 0, 0
    recovered, unreadable = 0, []
    for p in files:
        body = "S" if "senate" in str(p).lower() else "H"
        for v in _load_one(p, (roster or {}).get(body) or {}, unreadable):
            v["body"] = body
            v["source"] = str(p)
            if v["video_id"] in seen:
                dupes += 1
                i = seen[v["video_id"]]
                if _aired(v) > _aired(out[i]):
                    recovered += v["recovered"] - out[i]["recovered"]
                    out[i] = v
                    later += 1
                continue
            seen[v["video_id"]] = len(out)
            recovered += v["recovered"]
            out.append(v)
    print(f"  {len(out):,} videos from {len(files)} file(s)"
          + (f", {dupes:,} duplicates across overlapping ranges skipped"
             if dupes else "")
          + (f", {later:,} of them in favour of a later row written after "
             "the stream aired" if later else ""))
    # SAY WHAT WAS DROPPED. This loop discarded 554 rows across the twelve
    # indexes without a word, and the largest block of them -- the Senate from
    # May 2020 -- read as a chamber that had never been filmed.
    if recovered or unreadable:
        print(f"  {recovered:,} recovered by re-reading a title the channel "
              f"index could not parse, {len(unreadable):,} still unreadable")
        for t in unreadable[:5]:
            print(f"      {t[:72]}")
        if len(unreadable) > 5:
            print(f"      ... and {len(unreadable) - 5:,} more")
    # What the indexes actually cover, so a gap is visible rather than
    # discovered later as a proceeding with no video.
    dates = sorted(v["date"] for v in out if v.get("date"))
    if dates:
        print(f"  covering {dates[0]} to {dates[-1]}")
        byyear = defaultdict(lambda: [None, None])
        for d in dates:
            y = d[:4]
            lo, hi = byyear[y]
            byyear[y] = [min(lo or d, d), max(hi or d, d)]
        for y, (lo, hi) in sorted(byyear.items()):
            print(f"    {y}: {lo} to {hi}")
    return out


def _aired(v):
    """How much an index row knows about its stream: 2 when it has the
    length, which a row only has once the stream is over; 1 when it has only
    the start, written while it was live; 0 when it has neither, written
    while it was only scheduled."""
    if (v.get("duration_iso") or "").strip() not in ("", "P0D"):
        return 2
    return 1 if v.get("start_eastern") else 0


def _load_one(path, roster, unreadable):
    vids = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["title_parsed"] == "yes":
            raw = r["parsed_committee"]
            cmte, when, got = norm_title_committee(raw), r["parsed_date"], 0
            cmte = resolve_committee(cmte, roster) or cmte
        else:
            raw = r["title"]
            cmte, when = recover_title(r, roster)
            got = 1
            if not (cmte and when):
                unreadable.append(r["title"])
                continue
        vids.append({
            "video_id": r["video_id"],
            "title": r["title"],
            "date": when,
            "committee_raw": raw,
            "committee": cmte,
            "family": family(cmte),
            "start_eastern": r["start_eastern"],
            # How long it was on air. The only thing in the index that can
            # separate two recordings of one committee on one day -- see
            # on_air_at below.
            "duration_iso": r.get("duration_iso") or "",
            "recovered": got,
            "bills_in_title": {f"{m.group(1)}{m.group(2)}"
                               for m in BILLS_IN_TITLE.finditer(r["title"])},
        })
    return vids


def predicted_offset(sched_time, start_eastern):
    """Seconds from the start of the stream to the scheduled time."""
    if not sched_time or not start_eastern:
        return None
    try:
        st = datetime.strptime(start_eastern, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    h, m = (int(x) for x in sched_time.split(":"))
    sched = st.replace(hour=h, minute=m, second=0)
    return int((sched - st).total_seconds())


DURATION = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def on_air_at(v, sched_date, sched_time):
    """Was this recording live when the docket says the bill was taken up?

    None when the index cannot say -- no start time, no duration, or no
    scheduled time -- which is not the same answer as False and is treated as
    such by the caller.

    This is the clock, not a guess. Two recordings of House Election Law on
    18 March 2025: the subcommittee work session went out 08:57 to 09:40 and
    the committee 09:58 to 12:08, and the docket puts HB 418's work session at
    09:00 and its executive session at 10:00. One reading of the same index
    that was already on disk separates them.
    """
    if not sched_time or not v.get("start_eastern"):
        return None
    m = DURATION.fullmatch(v.get("duration_iso") or "")
    if not m:
        return None
    try:
        st = datetime.strptime(v["start_eastern"], "%Y-%m-%d %H:%M:%S")
        h, mi = (int(x) for x in sched_time.split(":"))
        want = datetime.strptime(sched_date, "%Y-%m-%d").replace(hour=h,
                                                                 minute=mi)
    except ValueError:
        return None
    hrs, mins, secs = (int(x or 0) for x in m.groups())
    return st <= want <= st + timedelta(seconds=hrs * 3600 + mins * 60 + secs)


def hhmmss(sec):
    if sec is None:
        return ""
    sign = "-" if sec < 0 else ""
    return sign + str(timedelta(seconds=abs(int(sec))))


def read_any(path):
    """Rows from a .csv or a .xlsx, as dicts of strings."""
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        rws = list(load_workbook(p, read_only=True).active
                   .iter_rows(values_only=True))
        head = [str(c).strip() if c is not None else "" for c in rws[0]]
        return [dict(zip(head, r)) for r in rws[1:]]
    with p.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def as_date(v):
    """YYYY-MM-DD from a date cell, an Excel serial, or a string."""
    from datetime import date as _d, datetime as _dt
    if v is None or v == "":
        return ""
    if isinstance(v, _dt):
        return v.date().isoformat()
    if isinstance(v, _d):
        return v.isoformat()
    s = str(v).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    if re.fullmatch(r"\d{5}(\.\d+)?", s):
        # Excel counts days from 1899-12-30.
        return (_d(1899, 12, 30) + timedelta(days=int(float(s)))).isoformat()
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else s


def as_clock(v):
    """H:MM:SS from a time cell, a timedelta, an Excel fraction, or text."""
    from datetime import time as _t, timedelta as _td
    if v is None or v == "":
        return ""
    if isinstance(v, _td):
        return str(_td(seconds=int(v.total_seconds())))
    if isinstance(v, _t):
        return f"{v.hour}:{v.minute:02d}:{v.second:02d}"
    s = str(v).strip()
    if re.fullmatch(r"0?\.\d+", s):
        return str(timedelta(seconds=int(float(s) * 86400)))
    return s


def load_marks(path):
    """{(bill, date, kind): (start, end, notes)} from an earlier manifest.

    These are the only numbers in this project a person produced by watching
    the video. A fresh manifest writes observed_start empty, so without this
    every rebuild throws them away -- which has already happened once, and is
    why the site and the hand marks now name entirely different videos.
    """
    marks = {}
    for r in read_any(path):
        start = as_clock(r.get("observed_start"))
        if not start:
            continue
        key = (str(r.get("bill") or "").strip().upper(),
               as_date(r.get("sched_date")),
               str(r.get("proceeding") or "").strip().lower())
        marks[key] = (start, as_clock(r.get("observed_end")),
                      str(r.get("notes") or ""))
    return marks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", required=True, nargs="+",
                    help="one or more video index CSVs; pass the House and "
                         "Senate indexes together to match both chambers")
    ap.add_argument("--docket", default=None, help="local Docket.txt (downloads if omitted)")
    ap.add_argument("--out", default="verification_manifest.csv")
    ap.add_argument("--only-recorded", action="store_true",
                    help="drop proceedings on days with no recording. This "
                         "once happened unconditionally, which cost every "
                         "term before May 2020 all of its rows.")
    ap.add_argument("--keep-marks", metavar="OLD",
                    help="carry observed_start/observed_end forward from an "
                         "earlier manifest (.csv or .xlsx). Without this they "
                         "are lost on every rebuild.")
    a = ap.parse_args()

    # A build_* SCRIPT DOES NOT TOUCH THE NETWORK. This used to fetch
    # Docket.txt from gc.nh.gov when the file was absent, and the whole
    # permission rule in CLAUDE.md rests on the naming contract that only
    # fetch_* does that -- so a person or a model running this in good faith
    # would have asked the address that has blocked this one twice, without
    # ever being asked. It never fired here because Docket.txt is on disk. It
    # fires in a clean checkout, which is the state a refactor creates.
    #
    # Naming the file it wants and the command that gets it costs one run and
    # keeps the decision with a person.
    docket_path = a.docket or "Docket.txt"
    # AN ARCHIVED TERM IS WRITTEN TO ITS OWN FILE. --out defaults to
    # verification_manifest.csv, the current term's, and build_proceedings
    # reads every verification_manifest*.csv: a run over Docket_2019-2020.txt
    # that forgot --out would replace the current term's manifest with
    # 2019-2020's rows, so the current term would vanish from
    # proceedings.csv and 2019-2020 would appear in it twice.
    m = re.match(r"Docket(?:_db)?_(\d{4}-\d{4})\.txt$", Path(docket_path).name)
    if m and Path(a.out).name == "verification_manifest.csv":
        sys.exit(f"{docket_path} is the {m.group(1)} term's docket, and --out "
                 "is the current term's manifest. Pass\n"
                 f"    --out verification_manifest_{m.group(1)}.csv")
    if not Path(docket_path).exists():
        sys.exit(
            f"No {docket_path}.\n\n"
            "This builds the manifest and does not fetch anything. Get the "
            "docket first:\n"
            f"    curl -o Docket.txt {DOCKET_URL}\n\n"
            "or pass an archived term's docket with --docket "
            "Docket_2023-2024.txt.\n"
            "Those are on this disk already if fetch_archive_docket.py has "
            "run for that term.")
    print(f"Parsing {docket_path}...")

    rows = parse_rows(docket_path)
    timeline = build_referral_timeline(rows)
    procs = parse_proceedings(rows, timeline)
    build_sittings(procs)
    # Senate proceedings were filtered out here from the start. That single
    # condition, not any transcription problem, is why no Senate hearing has
    # ever had a timestamp: there was nothing in the manifest for a Senate
    # recording to align against.
    #
    # Which chambers are covered now follows from the video indexes given,
    # rather than being fixed in the code.
    vids = load_videos(a.videos, build_roster(procs))
    bodies = {v.get("body") or ("S" if "senate" in (v.get("source") or "").lower()
                                else "H") for v in vids}
    procs = [p for p in procs
             if p.confidence != "X-cancelled" and p.body in bodies]
    from collections import Counter as _C
    byb = _C(p.body for p in procs)
    print(f"  {len(procs):,} proceedings in {'/'.join(sorted(bodies))}: "
          + ", ".join(f"{n:,} {'House' if b == 'H' else 'Senate'}"
                      for b, n in sorted(byb.items())))
    # A HEARING THAT HAPPENED IS A HEARING, FILMED OR NOT. This dropped
    # every proceeding whose exact date had no recording, which was right
    # when the only job of this file was "watch the video and mark where the
    # bill starts" -- a row with no video is nothing to watch. It stopped
    # being right when build_proceedings.py started reading it, because
    # proceedings.csv is the site's record of what the General Court did, and
    # a hearing is a fact about the legislature rather than about YouTube.
    #
    # It was silently fatal for whole terms. The House streamed nothing before
    # May 2020, so 2017-2018 produced 0 rows from 6,431 proceedings, and
    # 2019-2020 produced 0 from 5,823 -- the 139 recordings that term has are
    # all from after the sitting, so not one of them shares a date with a
    # scheduled hearing. Both printed "0 fall inside the video window" and
    # exited zero.
    #
    # The loop below already handles a proceeding with no candidate: it marks
    # it "no video found" and writes the row with the video columns empty.
    # The site already draws 2,480 of those as state "novideo". Nothing new
    # had to be built; the rows simply had to be allowed through.
    dates = {v["date"] for v in vids}
    if a.only_recorded:
        procs = [p for p in procs if p.sched_date in dates]
        print(f"  {len(procs):,} fall inside the video window "
              "(--only-recorded)")
    else:
        inside = sum(1 for p in procs if p.sched_date in dates)
        print(f"  {len(procs):,} proceedings, {inside:,} on a day something "
              f"was recorded, {len(procs) - inside:,} on a day nothing was")

    # THE CHAMBER IS PART OF THE KEY. Both chambers have an Education, a
    # Judiciary, a Finance, a Transportation, a Ways and Means and an
    # Executive Departments and Administration, and they sit on the same
    # days. Keyed on committee and date alone, every one of the 91 Senate
    # hearings of 2021-2022 that had a recording had the HOUSE committee's
    # recording of that day -- SB 232's Senate Education hearing of
    # 11 January 2022 on "House Education (01/11/22)" -- and 79 House
    # proceedings of 2023-2024 and 19 of the current term had the other
    # chamber's. The bill's number is spoken on 2 of the 82 captioned ones.
    #
    # A committee of conference sits for both chambers and may be streamed
    # on either channel, so it alone may fall back to the other chamber's
    # recordings, and only when its own has none.
    exact = defaultdict(list)
    fam = defaultdict(list)
    for v in vids:
        exact[(v["body"], v["committee"], v["date"])].append(v)
        fam[(v["body"], v["family"], v["date"])].append(v)

    def candidates(p, body):
        return (exact.get((body, p.committee, p.sched_date))
                or fam.get((body, family(p.committee or ""), p.sched_date))
                or [])

    out, stats = [], defaultdict(int)
    for p in procs:
        cands = candidates(p, p.body)
        if not cands and p.kind == "committee of conference":
            cands = candidates(p, "S" if p.body == "H" else "H")

        named = [v for v in cands if p.bill in v["bills_in_title"]]
        # TWO RECORDINGS OF ONE COMMITTEE ON ONE DAY, AND WHICH ONE WAS ON AIR.
        #
        # 576 proceedings since May 2020 have more than one candidate, and the
        # matcher used to decline all of them -- which the site then drew as
        # "No recording matched to this proceeding", a stronger claim than the
        # evidence carries in the opposite direction. On 250 of them exactly
        # one candidate was broadcasting at the scheduled minute, and that is
        # the recording: a 1m06s false start against a 6h32m stream of House
        # Judiciary on 2 February 2021, "Senate Commerce (04/05)" at 08:59
        # against a second part at 10:18.
        #
        # Checked against the captions, which are nobody's inference here: of
        # the 250, 29 name the bill in the recording this picked and in no
        # other, and the one apparent contradiction is the pair above, where
        # the clock is right and the subcommittee simply never said "418".
        # ground_truth.csv reaches none of these 250, so it neither confirms
        # nor refutes them.
        #
        # NOT the Finance divisions. The docket does not record which division
        # holds a bill, so a division that streamed while another did not
        # would collect the other's hearings -- which is exactly what
        # AMBIGUOUS_FAMILIES exists to refuse. They stay unpicked.
        on_air = []
        if len(cands) > 1 and not named and \
                family(p.committee or "") not in AMBIGUOUS_FAMILIES:
            says = [on_air_at(v, p.sched_date, p.sched_time) for v in cands]
            if all(s is not None for s in says):
                on_air = [v for v, s in zip(cands, says) if s]

        # The row's own words and the bucket it is counted in, decided
        # together. The summary at the end used to derive the bucket by
        # cutting the row's words at " -" or " that", which silently made a
        # bucket per candidate count the moment a new phrasing arrived.
        if named:
            cands, match = named, "title names this bill"
            bucket = match
        elif not cands:
            match = bucket = "no video found"
        elif len(cands) == 1:
            match = bucket = "single video"
        elif len(on_air) == 1:
            match = f"only one of {len(cands)} was on air then"
            bucket = "only one was on air then"
        elif family(p.committee or "") in AMBIGUOUS_FAMILIES:
            match = f"{len(cands)} divisions - pick manually"
            bucket = "divisions"
        else:
            match = f"{len(cands)} videos that day - pick manually"
            bucket = "more than one video that day"
        stats[bucket] += 1

        v = (cands[0] if len(cands) == 1 or named
             else on_air[0] if len(on_air) == 1 else None)
        off = predicted_offset(p.sched_time, v["start_eastern"]) if v else None

        out.append({
            "bill": p.bill,
            # Which chamber. The manifest covers both now, and without this
            # there is no way to tell a Senate row from a House one, or to see
            # that Senate matching is failing while the totals look healthy.
            "body": p.body,
            "committee": p.committee,
            "proceeding": p.kind,
            "sched_date": p.sched_date,
            "sched_time": p.sched_time,
            "venue": p.venue,
            "tier": p.confidence,
            "bills_in_slot": p.cohort_size,
            "match": match,
            "video_id": v["video_id"] if v else "",
            "video_title": v["title"] if v else "",
            "stream_start": v["start_eastern"][11:19] if v else "",
            "predicted_offset": hhmmss(off),
            "watch_url": (f"https://www.youtube.com/watch?v={v['video_id']}&t={max(off - 300, 0)}s"
                          if v and off is not None else ""),
            "candidates": " | ".join(c["title"] for c in cands) if len(cands) > 1 else "",
            # A RECORDING EXISTS, AND THIS IS WHICH ONES IT COULD BE.
            #
            # 326 rows since May 2020 still end with more than one candidate
            # and no pick -- 245 Finance divisions and 81 the clock could not
            # separate. They are written with video_id empty, and empty is the
            # only thing the site reads, so build_site_v2 files them as
            # "novideo" and app.js draws "No recording matched to this
            # proceeding." That is false: the committee was filmed that day
            # and the index holds the recordings.
            #
            # `candidates` has carried the titles for a person to read since
            # this file was written; titles are not addressable. The ids are,
            # so the page can offer them once build_proceedings.py carries
            # this column and build_site_v2 grows the state for it. Both of
            # those are other files and are not changed here.
            "candidate_ids": " | ".join(c["video_id"] for c in cands) if len(cands) > 1 else "",
            "observed_start": "",
            "observed_end": "",
            "notes": "",
        })

    # If nothing was named, fall back to the file about to be overwritten.
    # Hand-marked times have now been lost twice by a rebuild that simply did
    # not know about them -- once when a later matching run replaced the
    # manifest, and once when build_all.py re-ran this without the flag. A
    # default that preserves them makes forgetting harmless; the flag is for
    # reading marks out of some OTHER file.
    keep = a.keep_marks
    if not keep:
        for c in (Path(a.out), Path(a.out).with_suffix(".xlsx")):
            if c.exists():
                keep = str(c)
                break
    marks = load_marks(keep) if keep else {}
    if marks and not a.keep_marks:
        print(f"  {len(marks)} hand-marked times found in {keep}; keeping them")

    # ground_truth.csv is the record and outranks anything in an old manifest.
    # It is keyed by (video, bill, kind) rather than by date, because the video
    # is what a person watched; map that back onto this manifest's rows.
    gt = Path("ground_truth.csv")
    if gt.exists():
        byvid = {}
        for r in read_any(gt):
            st = as_clock(r.get("observed_start"))
            if not st:
                continue
            k = (str(r.get("video_id") or ""),
                 str(r.get("bill") or "").upper(),
                 str(r.get("kind") or "").lower())
            byvid[k] = (st, as_clock(r.get("observed_end")),
                        str(r.get("notes") or ""))
        matched = 0
        for r in out:
            k = (r.get("video_id") or "", r["bill"].upper(),
                 (r["proceeding"] or "").lower())
            if k in byvid:
                r["observed_start"], r["observed_end"], nt = byvid[k]
                if nt:
                    r["notes"] = nt
                matched += 1
        print(f"  {len(byvid)} marks in ground_truth.csv, {matched} placed on "
              "this manifest's rows")
        if matched < len(byvid):
            print(f"  ({len(byvid) - matched} name a video this manifest does "
                  "not -- see ground_truth.py --check)")
    kept = 0
    if marks:
        for r in out:
            k = (r["bill"].upper(), r["sched_date"],
                 (r["proceeding"] or "").lower())
            if k in marks:
                r["observed_start"], r["observed_end"], nt = marks[k]
                if nt:
                    r["notes"] = nt
                kept += 1

    out.sort(key=lambda r: (r["sched_date"], r["sched_time"] or "99:99", r["bill"]))
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    if marks:
        print(f"\ncarried {kept} of {len(marks)} hand-marked times forward "
              f"from {keep}")
        if kept < len(marks):
            missed = [k for k in marks
                      if k not in {(r["bill"].upper(), r["sched_date"],
                                    (r["proceeding"] or "").lower())
                                   for r in out}]
            print(f"  {len(missed)} did not match a row in the new manifest. "
                  "First three:")
            for k in missed[:3]:
                print(f"    {k[0]} {k[2]} on {k[1]}")
            print("  Those proceedings are not in the new docket parse or fall "
                  "outside\n  the video window.")
            if keep == a.out:
                bak = Path(a.out).with_suffix(".marks-backup.csv")
                import shutil as _sh
                _sh.copy(a.out, bak)
                print(f"  {a.out} is about to be overwritten, so a copy is at "
                      f"{bak.name}.")

    print(f"\nWrote {a.out}: {len(out):,} rows\n")
    # A PARSER THAT REWRITES A TIME SAYS SO. docket_parser corrects a
    # meridiem the clerk typed the wrong way round -- a hearing at
    # "12:15 am" that ran at quarter past noon -- and this is the line
    # that keeps that from being a silent edit. If the number grows,
    # the window grew with it, and that is a thing to have decided
    # rather than to discover.
    if docket_parser.MERIDIEM_SLIPS:
        _n = len(docket_parser.MERIDIEM_SLIPS)
        _shown = ", ".join(f"{was}->{now}"
                           for was, now in docket_parser.MERIDIEM_SLIPS[:4])
        print(f"Reversed meridiems corrected: {_n} "
              f"({_shown}{', ...' if _n > 4 else ''})\n")
    print("Video matching:")
    for k, v in sorted(stats.items(), key=lambda kv: -kv[1]):
        print(f"  {v:6,}  {k}")

    ready = sum(1 for r in out if r["watch_url"])
    print(f"\n{ready:,} rows have a direct watch link, opening 5 minutes before")
    print("the predicted start. Open one, find where the chair takes the bill up,")
    print("and put that elapsed time in observed_start.\n")
    print("Start with rows where tier is A-unique-slot -- those calibrate drift.")
    print("Then do one whole C-shared-slot executive session in a single sitting.")


if __name__ == "__main__":
    main()
