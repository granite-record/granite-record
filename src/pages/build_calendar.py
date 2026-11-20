#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.59
"""
The General Court's week, one page per week.

    python3 src/pages/build_calendar.py --site site --base https://graniterecord.org

WHY PAGES AND NOT A FETCH

The home page showed a fixed fortnight and there was no way to look at any
other week. Asked for on 18 September: "the calendar can be more of a week to
week thing where you can tap back and forth to view all the hearings and
sessions this week, next week, the previous week, etc."

The first attempt shipped a JSON file per week and a script to page through
them. That was the wrong shape twice over. The card a reader sees is drawn by
build_pages.cal_days, in Python, from the grouping meeting_key defines -- so a
script paging through JSON would have needed a SECOND renderer drawing
something that merely looked like the first, which is the mistake this
repository keeps a check under. And a site of files on a CDN can simply have
the weeks as files: the arrows become links, every week is an address a reader
can send to somebody, and the whole thing works with no script at all.

  site/calendar.html            the current week, which is what the tab opens
  site/calendar/2026-W38.html   every week, one file each; the current one is
                                a copy of calendar.html that names it as the
                                page to index and cite
  site/calendar/data/2026-09.json
                                every day of a month as the week pages draw
                                it, for the page's script (month_files)
  site/calendar/data/committees.json
                                every committee on the calendar, for its picker
  site/calendar/documents.json  every calendar and journal linked, for the
                                pickers under the schedule
  site/calendar/documents.html  the same list as plain links, a year at a time

A CALENDAR ON TOP OF THE WEEKS (24 September 2026). The person asked for the
General Court's schedule done properly: a month down the left with the week
and the day marked, List and Week views of the day chosen (the Day view went on
8 November 2026; an address asking for it reads as the list), a preview on
hover and filters that combine. That is a script, and it does not repeat the
mistake above, because what went wrong there was a second renderer and a page
that needed script to show anything. Neither is true here. Every week is still
its own page, whole without script; the month files carry the cards cal_days
drew for the week pages, byte for byte, and the script only arranges them.

WHAT IS ON A WEEK

Every proceedings.csv row with a date, read through proceedings.py like
everything else: committee hearings, executive and work sessions, and the
floor. Floor rows carry no committee -- which is exactly why sitting days were
nowhere on this site, since every listing is keyed on one -- so they are given
"House floor" or "Senate floor" and take an entry of their own beside the
committees that sat around them.

ONE ENTRY PER COMMITTEE PER DAY, which is meeting_key's rule and not this
file's: a committee that holds a hearing in the morning and an executive
session after it has had one working day. A committee is its chamber as well
as its name -- House Finance and Senate Finance on one day are two entries,
each linking its own page -- and a committee of conference is one bill's. The
card carries a chip per kind and a divided colour bar, and its body lists the
day's items in order with the time and room each was set for.

STUDY AND STATUTORY COMMITTEES. proceedings.csv is keyed on bills, so on its
own this showed bill business only, while the General Court's schedule also
lists the study commissions, boards and statutory committees that sit with no
bill before them -- seven of them in the week of 21 September 2026, against
two sittings shown. They come from the database copy in db/
(StatStudMeetings.psv, with StatStudDetails.psv for each committee's name and
whether it is a study or a statutory one), drawn as their own cards in a
colour of their own, and shown when a reader ticks Study Committee, which is
off until they do (25 September 2026). NOTHING REFRESHES THAT COPY YET -- it
is a fetch_*_db.py run, which is the person's to start -- so the build says
on every run which copy it read. The page said so too until the person asked
on 25 September for that explanation to come off it.

ONE ADDRESS (25 September 2026). Every week keeps its own page, which a
canonical link names; since 17 October 2026 only /calendar is in the sitemap
and each week's page asks search engines not to index it (WEEK_ROBOTS);
moving about the calendar with
the script keeps the reader on /calendar, with the week, the day, the view
and the filters in the query -- /calendar?week=2026-W28 -- so a reload or a
link sent opens what was on the screen. WEEK_JS says how.

CALENDARS & JOURNALS, AS PDFs (1 October 2026). Under the schedule of every
week: pickers in a row -- House or Senate calendars or journals, the year, the
document -- and a button that opens the General Court's own PDF, as its own
pages do. calendar_documents.py reads the list and writes the section, its
script and the list page; this hands the section to every week's page and
writes the two files beside them. Without script the section is plain links.

MONDAY TO FRIDAY, IN TITLE CASE (9 October 2026, the second round of the
polish, approved). "Dont display Saturdays and sundays on the week view, only
weekdays since there aren't meetings on the weekend. If that would allow the
week view to be displayed like the list and day views which keep the month on
the left, that would be preferred." So the Week view is a column a day,
Monday to Friday, in the schedule's column beside the month, each the day's
cards in brief (WEEK_JS's weekView), where it was a table of hours with the
cards whole in its cells; the List view keeps every weekday too, one the
filters emptied saying what they hid; a week is named by the days it shows,
"The Week of February 16–20, 2026"; and the pager says "Previous Week", "This Week" and
"Next Week", each with the week it leads to, as the person asked the same
day (the Day view and its "Previous Day" and "Next Day" went on 8 November
2026). A Saturday or Sunday
is shown wherever one holds a meeting -- a column, a day in the list, the end
of the week's name -- and never hidden in silence. None has since the
calendar's first week: proceedings.csv has eleven weekend days, 1999-2015,
and the study committees' copy sixty, 1994-2015. The floor is "House Session
Day" and "Senate Session Day" (build_pages.card_name), under the key's
"Session Day".
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import csv
import datetime
import json
import re
from collections import Counter, OrderedDict, defaultdict

import bill_order as BO
import build_date
import calendar_documents as CD
import chrome
import i18n
import inline_js as IJ
import key_dates as KD
import parts as P
import proceedings
import shell as S
import structured as LD
from i18n import say

# From 2025: the current term and the one before it. Everything earlier is in
# the record and reachable through a bill or a committee, but nobody pages a
# calendar back to 1998 and sixty-odd files is enough to carry the arrows.
FROM = "2025-01-01"

# A ROW WITH NO COMMITTEE IS NOT AUTOMATICALLY THE FLOOR, and treating it as
# one put 4,370 committee meetings on this site under the heading "House
# floor" or "Senate floor". Of the 8,339 committee-less rows in
# proceedings.csv only 3,969 are floor debate; the rest are 1,512 hearings,
# 1,010 subcommittee work sessions, 805 committees of conference, 632 public
# hearings, 182 executive sessions, 139 full committee work sessions and 90
# work sessions whose committee the docket did not record.
#
# They are real sittings and they are not the floor. A committee of conference
# is named for what it is, because that is a thing a reader recognises; the
# rest say plainly that the committee is not on the record, which is true and
# is better than a confident wrong name.
FLOOR = {"H": "House floor", "S": "Senate floor"}
FLOOR_KINDS = ("floor debate",)
# build_pages.meeting_key's, which keys a conference on its bill.
CONFERENCE = P.CONFERENCE


def floor_name(kind, body):
    """What to call a sitting the docket gives no committee.

    None where it should not be shown at all.
    """
    k = (kind or "").strip().lower()
    if k in FLOOR_KINDS:
        return FLOOR.get(body)
    if k == "committee of conference":
        return CONFERENCE
    if not body:
        return None
    return f"{'House' if body == 'H' else 'Senate'} \u2014 committee not recorded"


# ---- study and statutory committees, from the database copy ---------------
#
# StatStudMeetings.psv: webtext|MeetingID|CommitteeID|MeetingDate|
# MeetingLocation|username|DateModified. StatStudDetails.psv has 28 fields
# (db/_columns.json); the ones read here are CommitteeID (0), CommitteeYear
# (1), CondensedBillNo (4), CommitteeName (7) and CommitteeStatus (17), a
# plain label such as "Active Chaptered Study Committee" or "Active
# Statutory Committee" -- which is what says study or statutory. The 0/1
# Committeetype flag does not track it.
STATSTUD_DIR = Path("db")

# Names are stored in capitals. Title case, with the short words down and
# the acronyms the names actually carry kept as the General Court writes them.
_SMALL = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or",
          "the", "to", "with"}
# OPLC, OBD II, GIS and SNAP added on 18 October 2026, when every active
# committee got a page of its own: "Oplc Oversight Committee" and "Obd Ii
# Testing Advisory Committee" were each one's heading. McAuliffe is a name.
_ACRONYM = {"NH": "NH", "RSA": "RSA", "OHRVS": "OHRVs", "SAUS": "SAUs",
            "SIEC": "SIEC", "IDD": "IDD", "ABD": "ABD", "OPLC": "OPLC", "OBD": "OBD",
            "II": "II", "GIS": "GIS", "SNAP": "SNAP", "MCAULIFFE": "McAuliffe"}
# THE LIST'S OWN MARKS ARE NOT THE NAME: "NH RETIREMENT SYSTEM BOARD OF
# TRUSTEES ==NON-LEGISLATIVE==", "=NON-LEGISLATIVE=", "(No Legislative
# Members)". The committee's page says what the mark means
# (build_study_committees reads it off the name by this same pattern).
NAME_MARK = re.compile(r"=+\s*NON-LEGISLATIVE\s*=+|\(No Legislative Members\)", re.I)


def committee_name(caps):
    """COMMITTEE ON LEGISLATOR ORIENTATION -> Committee on Legislator Orientation.

    A word is cased on both sides of a hyphen or a slash, so the Advisory
    Committee on the Education of Children/Students with Disabilities is not
    "Children/students"."""
    words = NAME_MARK.sub(" ", caps or "").strip().rstrip(".").split()
    out = []
    for i, w in enumerate(words):
        parts = []
        for p in re.split(r"([-/])", w):
            core = p.strip("(),")
            if p in ("-", "/"):
                parts.append(p)
            elif core.upper() in _ACRONYM:
                parts.append(p.replace(core, _ACRONYM[core.upper()]))
            elif i and p.lower() in _SMALL:
                parts.append(p.lower())
            else:
                parts.append(re.sub(r"[A-Za-z]", lambda m: m.group(0).upper(),
                                    p.lower(), count=1))
        out.append("".join(parts))
    return " ".join(out)


_MARK = re.compile(r"^\s*==\s*([A-Z ]+?)\s*==\s*")
# The whole label, so none of it is left on the room: with "Hearing" and
# "Session" alone, "Public Hearing" left "Claremont Public" as the place and
# "Subcommittee Work Session" left "Concord Subcommittee Work".
_TYPE = re.compile(r"\s*((?:Regular|Organizational|Subcommittee|Special)\s+Meeting"
                   r"|Other Meeting Type|(?:Public\s+)?Hearing"
                   r"|(?:Subcommittee\s+)?(?:Work\s+)?Session)\s*$", re.I)

# A VENUE IS SHOWN ONLY WHERE IT READS AS THE PLACE. The database copy lost
# the line breaks inside MeetingLocation, so its lines run together:
# "DHHSBrown BuildingConference Room 468129 Pleasant StreetConcord, NH" is
# Room 468 at 129 Pleasant Street, and printed as stored it reads as Room
# 468129. The General Court's own schedule has the same text with its
# breaks, so the loss is the copy's, not the source's -- and a wrong room or
# street number on a card is a wrong fact. These are the marks of a lost
# break: a lower-case letter against a capital, an acronym against a word
# ("BEAKingsman Room"), a letter against a digit, a
# number against a word, a bracket against the next word, a room number of
# five digits or one followed by a street's name, two numbers in a row before
# a street ("Room, 330 21 South Fruit Street"), and a word split at a line's
# end ("Ad- ministration") in a calendar's text.
_JOINED = re.compile(r"[a-z][A-Z]|[A-Z]{2}[A-Z][a-z]{2}|[A-Za-z]\d|\d[A-Z][a-z]"
                     r"|\)[A-Za-z0-9]"
                     r"|(?i:\broom)\s*#?\s*\d{5,}"
                     r"|(?i:\broom)\s*#?\s*\d+[A-Z]?\s+(?:[A-Z][\w.']*\s+){1,3}"
                     r"(?:Street|St|Road|Rd|Drive|Dr|Avenue|Ave|Lane|Ln|Way"
                     r"|Boulevard|Blvd|Highway|Hwy|Place|Pl|Court|Ct)\b"
                     r"|\b\d+ \d+ [A-Z][a-z]|[a-z]- [a-z]")
# NOR IS WHAT IS NOT A PLACE. The field also carries webinar addresses, a
# named employee's email and telephone cut off mid-name, and Teams meeting
# numbers with their passcodes. They are in the official notice, which the
# card links where the record has it; a card's one line of place is not
# where a passcode or somebody's email address belongs.
_NOT_PLACE = re.compile(r"(?i)https?:|www\.|@|passcode|meeting id|dial in|register")


def place(v):
    """The venue as the record has it, or "" where it does not read as a place.

    Leaving a venue out is the safe failure: the card still has its day,
    time and committee, and no address on it is one the record did not give.
    """
    v = re.sub(r"\s+,", ",", re.sub(r"\s+", " ", v or "")).strip(" ,")
    # "REMOTE Room 000" and "Offsite Room 9999" are the database's word for
    # where, with a placeholder where the room would be.
    v = re.sub(r"^(\w+) Room (?:0+|9999)$", lambda m: m.group(1).capitalize(), v)
    if (not v or len(v) > 150 or _NOT_PLACE.search(v)
            # McLane and MacDonald are names, not two lines run together.
            or _JOINED.search(re.sub(r"\bMa?c(?=[A-Z])", "", v))):
        return ""
    return v


def schedule_venues(path=Path("schedule_pages") / "_events.json"):
    """{meeting id: (start, venue)} from the General Court's own schedule.

    fetch_schedule's copy of the schedule's event feed titles each study
    committee meeting "NAME : place", with the place's line breaks intact, and
    its address eventDetails.aspx?event=N&et=2 carries the same N as the
    database's MeetingID: all 77 of that copy's meetings in the 2026 database
    rows join on it at the same minute. It covers August to December 2026,
    which is the weeks a reader is most likely to open.
    """
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        rows = json.loads(d["d"]) if isinstance(d, dict) else d
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    out = {}
    for r in rows if isinstance(rows, list) else []:
        m = re.search(r"[?&]event=(\d+)&et=2\b", str(r.get("url") or ""))
        title = str(r.get("title") or "")
        if not m or " : " not in title:
            continue
        lines = [x.strip().rstrip(",").strip() for x in
                 title.split(" : ", 1)[1].splitlines()]
        v = place(", ".join(x for x in lines if x))
        if v:
            out[m.group(1)] = (str(r.get("start") or "")[:16], v)
    return out


def notice_venues(path=Path("meetings.json")):
    """{(date, committee words): venue} for the meetings with no bill, as the
    House or Senate Calendar printed them -- the earliest notice whose venue
    reads as a place. Where the database copy's venue ran together, this is
    the same meeting's place in the General Court's printed notice."""
    try:
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for r in sorted(rows if isinstance(rows, list) else [],
                    key=lambda r: r.get("noticed") or "9999"):
        date = (r.get("date") or "")[:10]
        if date < FROM or (r.get("bill") or "").strip():
            continue
        v = place((r.get("venue") or "").strip() or (r.get("room") or "").strip())
        k = (date, _words(r.get("committee")))
        if v and k not in out:
            out[k] = v
    return out


def _where(loc):
    """(room, what kind of meeting) out of 'GP Room 234  Regular Meeting'.

    The record joins the two with spaces. A U+FFFD in it is a character the
    database copy lost -- 'NHDES \ufffd 29 Hazen Drive' -- and is shown as a
    dash, which is what separates a name from an address there; that is a
    reading of it, not a recovered character.
    """
    s = _MARK.sub("", loc or "").replace("\ufffd", "\u2013")
    kind = ""
    m = _TYPE.search(s)
    if m:
        kind = "" if m.group(1).lower() == "other meeting type" else m.group(1)
        s = s[:m.start()]
    return re.sub(r"\s+", " ", s).strip(" ,"), kind.capitalize()


# A STUDY OR STATUTORY COMMITTEE'S RECORDING (30 September 2026). A meeting
# with no bill has no page here to lead to -- its card says so -- so where the
# House or Senate channel published a recording named for it, the card leads
# to that. The recording is found in the video index every reader globs
# (proceedings.video_indexes: collected/videos/ and the nightly's new
# livestreams at the root) by its own date and
# its committee: the words of the recording's committee and the meeting's must
# mostly agree both ways, a Dice score of REC_MATCH, because a one-word title
# such as "House Education" would otherwise take a long name that merely
# contains the word. A recording already on a bill's sitting is that
# sitting's; a meeting after the build is not recorded yet; and a recording
# two committees fit equally well is not guessed between -- two rows of one
# name that day are one meeting the database holds twice, and share it.
# Measured on 30 September 2026: sixteen of the eighteen recordings since the
# nightly began that sat on no bill fit a study or statutory meeting of their
# own day by name, and the other two were the House Special Committee on
# COVID Response Efficacy, which is neither and has no card.
REC_MATCH = 0.6
REC_GENERIC = frozenset("house senate committee committees commission joint study special "
                        "task force the and for".split())
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _rec_words(s):
    return {w for w in re.findall(r"[a-z]{3,}", (s or "").lower()) if w not in REC_GENERIC}


def recordings_by_day(root=Path(".")):
    """{date: [(video_id, title, the words of its committee)]} out of every
    video index here (proceedings.video_indexes)."""
    out = defaultdict(list)
    for f in proceedings.video_indexes(root):
        try:
            with open(f, encoding="utf-8", newline="") as fh:
                for r in csv.DictReader(fh):
                    vid = (r.get("video_id") or "").strip()
                    date = (r.get("parsed_date") or "").strip()[:10]
                    if not VIDEO_ID.match(vid) or not date:
                        continue
                    name = ((r.get("parsed_committee") or "").strip()
                            or re.sub(r"\(.*?\)", " ", r.get("title") or ""))
                    out[date].append((vid, (r.get("title") or "").strip(), _rec_words(name)))
        except OSError:
            continue
    return out


def study_recordings(rows, videos, on_bills, today):
    """Give each study or statutory meeting held by `today` the recording named
    for it, as row["video_id"]. ([rows given one], [(date, title)] of the
    recordings from FROM to today on no bill that fit no meeting here)."""
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["date"]].append(r)
    linked, unmatched = [], []
    for date, recs in sorted(videos.items()):
        if date < FROM or date > today:
            continue
        day = [r for r in by_day.get(date, []) if r.get("kind") != "cancelled"]
        for vid, title, tw in recs:
            if vid in on_bills or not tw:
                continue
            scored = []
            for r in day:
                cw = _rec_words(r.get("committee"))
                if cw:
                    scored.append((2 * len(tw & cw) / (len(tw) + len(cw)), r))
            best = max((sc for sc, _ in scored), default=0)
            top = [r for sc, r in scored if sc == best]
            if best < REC_MATCH or len({r["committee"] for r in top}) > 1:
                unmatched.append((date, title))
                continue
            for r in top:
                if not r.get("video_id"):
                    r["video_id"] = vid
                    linked.append(r)
    return linked, unmatched


# A STUDY OR STATUTORY COMMITTEE'S OWN PAGE (18 October 2026). Every
# committee the General Court lists as active has one, written by
# build_study_committees.py at /committee/ss<CommitteeID>: the database's own
# number for it, which stays put when a committee is renamed or its
# establishing bill is amended, as the person chose. A meeting's card leads to
# its committee's page where the committee is active; an archived one has no
# page yet, and its card leads nowhere, as every study card did before.
def study_page(cid):
    """committee/ss1451.html, the page of the committee numbered 1451."""
    return f"committee/ss{cid}.html"


def statstud(root=Path(".")):
    """(rows, names, fetched): the study and statutory committee meetings
    from FROM on, shaped as weeks_from reads rows; {bill: [(year, name)]}
    for the committees a bill set up; and the date the copy was taken.

    Each row carries its committee's number ("cid"), the meeting's own
    ("mid"), and, where the committee is active and so has a page, that
    page's address ("page"), which build_study_committees reads the venue
    and the recording of each meeting back by.

    ([], {}, "") where the copy is not on disk -- the caller says so.
    """
    d = Path(root) / STATSTUD_DIR
    det_f, meet_f = d / "StatStudDetails.psv", d / "StatStudMeetings.psv"
    if not (det_f.exists() and meet_f.exists()):
        return [], {}, ""
    det, names = {}, defaultdict(list)
    for ln in det_f.read_text(encoding="utf-8", errors="replace").splitlines():
        f = ln.split("|")
        if len(f) < 18 or not f[0].strip():
            continue
        label = f[17].strip()
        kind = ("statutory committee" if "statutory" in label.lower()
                else "study committee" if "study" in label.lower() else "")
        name = committee_name(f[7])
        bill = re.sub(r"\s+", "", f[4]).upper()
        det[f[0].strip()] = (name, kind, bill, f[1].strip(),
                             label.lower().startswith("active"))
        if bill:
            names[bill].append((f[1].strip(), name))
    rows, skipped = [], 0
    printed, noticed, unplaced = notice_venues(Path(root) / "meetings.json"), 0, 0
    posted = schedule_venues(Path(root) / "schedule_pages" / "_events.json")
    for ln in meet_f.read_text(encoding="utf-8", errors="replace").splitlines():
        f = ln.split("|")
        if len(f) < 5:
            continue
        try:
            when = datetime.datetime.strptime(f[3].strip(), "%m/%d/%Y %H:%M:%S")
        except ValueError:
            continue
        date = when.date().isoformat()
        if date < FROM:
            continue
        c = det.get(f[2].strip())
        if not c or not c[1]:
            # A committee the details do not name, or one labelled neither
            # study nor statutory ("Repealed"): not guessed at.
            skipped += 1
            continue
        name, kind, bill, year, active = c
        room, mtype = _where(f[4])
        if room and not place(room):
            # The copy's own venue does not read as a place: the General
            # Court's schedule for this very meeting, then the calendar's
            # printed notice of it, else none.
            sched = posted.get(f[1].strip())
            room = (sched[1] if sched and sched[0] == when.isoformat()[:16]
                    else printed.get((date, _words(name)), ""))
            noticed += bool(room)
            unplaced += not room
        else:
            room = place(room)
        marks ={m.upper() for m in re.findall(r"==\s*([A-Za-z ]+?)\s*==",
                                               f[0] + " " + f[4])}
        cancelled = "CANCELLED" in marks
        note = (mtype + "." if mtype else "")
        if bill:
            pretty = re.sub(r"^([A-Z]+)", r"\1 ", bill)
            note += (" " if note else "") + f"Set up by {pretty} of {year}."
        rows.append({"date": date,
                     "time": "" if when.time() == datetime.time(0) else when.strftime("%H:%M"),
                     "bill": "", "committee": name,
                     "kind": "cancelled" if cancelled else kind,
                     "venue": room, "body": "", "term": "",
                     "study": True, "note": note, "cid": f[2].strip(), "mid": f[1].strip(),
                     "page": study_page(f[2].strip()) if active else ""})
    if skipped:
        print(f"  {skipped} study/statutory meetings left out: their committee "
              "is not named, or not labelled study or statutory, in StatStudDetails")
    # SILENCE IS NOT SUCCESS: a venue left off a card is said out loud here.
    if noticed or unplaced:
        print(f"  {noticed + unplaced} study/statutory venues do not read as a place "
              f"in the database copy (lines run together, or a link or passcode): "
              f"{noticed} taken from the General Court's schedule or the "
              f"calendar that printed the notice, {unplaced} left off the card")
    fetched = ""
    try:
        man = json.loads((d / "_manifest.json").read_text(encoding="utf-8"))
        fetched = (man.get("StatStudMeetings") or {}).get("fetched", "")[:10]
    except (OSError, ValueError, AttributeError):
        pass
    return rows, dict(names), fetched


_NAMES = None


def study_names():
    """{bill: [(year, name)]} for the committees a bill set up, read once."""
    global _NAMES
    if _NAMES is None:
        _NAMES = statstud()[1]
    return _NAMES


def study_name(bill, term, names):
    """The study committee a bill of this term set up, or None.

    The docket's floor index records a study committee's meeting under the
    bill it studies and with no committee -- HB 1763 on 2 September 2026 was
    "House -- committee not recorded" -- and the database copy names it.
    """
    years = set(re.findall(r"\d{4}", term or ""))
    hits = {n for y, n in names.get((bill or "").upper(), []) if not years or y in years}
    return hits.pop() if len(hits) == 1 else None


# THE CALENDAR RUNS IN THE READER'S BROWSER, AND THE PAGE IS WHOLE WITHOUT IT.
#
# A week's page is the week as a list, every card in the HTML with its
# chamber, committee, bills, kinds and whose sitting it is on it. This script
# is what makes that a calendar, as the person described it on 24 September
# 2026 with the General Court's own schedule beside it: a month grid down the
# left, with a few dots on each day in the kinds' colours, today marked, the
# selected week a band and past days greyed; a panel that shows the selected
# day's week as a list, as the week at a glance or as the one day in full;
# a preview of a day's meetings when the pointer rests on it; and filters,
# which combine: since 25 September 2026 a row of boxes in the kinds'
# colours, which is also their key, and down the side a search, a chamber
# and committees chosen by name.
#
# IT COMPOSES NO CARD. The cards are build_pages.cal_days's, in this page for
# its own week and in calendar/data/<month>.json for every other: the script
# picks them up, reads what each says about itself, and arranges them. The
# controls are in the HTML, hidden, and this unhides them -- a reader with no
# script never meets a control that does nothing, and gets the whole week,
# which is the correct answer to no filter at all.
#
# The first half is plain functions over plain values -- dates, a card's
# fields, the filters, the count, the grid's and the preview's markup -- and
# preflight runs them in node against cards a build wrote. The second half
# puts them on the page. The script is inline/build_calendar.js (inline_js,
# since 20 November 2026), after the blank line it opens with here; its
# whole-line comments stay in that file and are left off the copy each page
# carries (lean_js).
WEEK_JS = "\n" + IJ.script("build_calendar")


def week_key(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def monday(d):
    return d - datetime.timedelta(days=d.isoweekday() - 1)


def span_words(a, b, form="full", lang="en"):
    """September 21–25, 2026, or September 29 – October 3, 2026: shell's
    date_span, month first (D6, 8 October 2026); "Sep 21–25, 2026" in the
    form "medium", which the pager says under Previous Week and Next Week.
    In Spanish, day first: "21–25 de septiembre de 2026"."""
    return S.date_span(a, b, form, lang)


# THE CALENDAR IN SPANISH (9 November 2026). Each week is written twice: at
# /calendar/<week> in English and at /es/calendar/<week> in Spanish, the
# frame, the controls, the words around the cards and the script's words
# (week_js) in the page's language, the cards drawn by build_pages.cal_days
# in it too. What the General Court wrote -- a committee's name, a bill's
# number, a venue, a document's name -- stays as it printed it, marked
# lang="en" (i18n.py, the first kind of words). English is as it was.
def lang_prefix(lang):
    """"" for English, "/es" for Spanish: where a language's pages are."""
    return "" if lang == i18n.DEFAULT else f"/{lang}"


def href_for(key, today, lang="en"):
    """Where a week lives. The current one is the tab's own page.

    From the site root, with its slash: shell.page joins this to the domain for
    the page's canonical link and citation, and without it they read
    "https://graniterecord.orgcalendar" on every week until 24 September."""
    return lang_prefix(lang) + ("/calendar.html" if key == week_key(today)
                                else f"/calendar/{key}.html")


def collect(site, study_rows=()):
    """{week: {date: {meeting_key: [rows]}}}, plus the lookups a card needs.

    `study_rows` are statstud()'s, merged with the proceedings so a study
    committee that also has a bill's row on the day is one card."""
    titles, years = {}, {}
    idx = site / "idx"
    if idx.exists():
        for f in idx.glob("*.json"):
            try:
                rows = json.loads(f.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            for b in rows:
                if b.get("id"):
                    titles[b["id"]] = b.get("title") or ""
                    years[b["id"]] = b.get("year")

    # By chamber and name: build_pages.committee_codes says why.
    code = P.committee_codes(site)

    return (weeks_from(list(proceedings.load()) + list(study_rows)),
            titles, years, code)


def weeks_from(rows, names=None):
    """{week: {date: {meeting_key: [rows]}}} out of proceedings rows.

    ONE READING OF THE WEEK, AND THE HOME PAGE USES IT TOO. The home page's
    Coming up rail is this week's days from today on, and it used to be drawn
    from home.json's fortnight instead: committee rows only, cut at eighty,
    and counted in days that had meetings -- so on 23 September 2026 it ran to
    7 October, and in session it stopped partway through one day. It reads
    this now, so the rail and the Calendar tab it links to hold the same
    sittings -- the floor included -- because they are the same rows.
    """
    weeks = defaultdict(lambda: defaultdict(OrderedDict))
    names = study_names() if names is None else names
    for r in rows:
        date = (r.get("date") or "")[:10]
        if date < FROM:
            continue
        try:
            d = datetime.date.fromisoformat(date)
        except ValueError:
            continue
        cmte = (r.get("committee") or "").strip()
        if not cmte and (r.get("kind") or "").strip().lower() == "study committee":
            cmte = study_name(r.get("bill"), r.get("term"), names) or ""
        if not cmte:
            cmte = floor_name(r.get("kind"),
                              (r.get("body") or "").strip().upper()) or ""
            if not cmte:
                continue
        row = {"date": date, "time": (r.get("time") or "").strip(),
               "bill": r.get("bill") or "", "committee": cmte,
               "what": (r.get("kind") or "").strip(),
               "venue": (r.get("venue") or "").strip(),
               # THE CHAMBER, so the week can be filtered to one of them. It
               # is on the proceedings row already; nothing here derived it
               # from the committee's name, which would have been a second
               # answer to a question the record answers itself.
               "body": (r.get("body") or "").strip().upper(),
               # THE TERM, for the home rail: a bill number names one bill in
               # each biennium, and the rail resolves a title out of that
               # term's index rather than whichever term's HB 1 was read last.
               "term": (r.get("term") or "").strip()}
        if r.get("study"):
            row["study"] = True
            row["note"] = r.get("note") or ""
            if r.get("video_id"):
                row["video_id"] = r["video_id"]
            # The committee's own page, which its card leads to (study_page).
            if r.get("page"):
                row["page"] = r["page"]
        weeks[week_key(d)][date].setdefault(P.meeting_key(row), []).append(row)
    # A BILL'S ROW AT A STUDY COMMITTEE'S MEETING TAKES THE MEETING'S TIME AND
    # ROOM. The docket gives neither; the database copy's row for the same
    # committee on the same day does, and without this the one card would
    # list the day twice, once untimed.
    for days in weeks.values():
        for day in days.values():
            for key, rs in day.items():
                # AND A CONFERENCE'S RECORDING IS THE MEETING ITS NOTICE SET.
                # The floor index knows a conference from its video, which
                # gives no time; the docket's notice gives the time and room.
                # Where the bill's card has both, the untimed row is the same
                # sitting again, and listed it would count the bill twice.
                # AND TWO RECORDINGS OF ONE CONFERENCE ARE ONE LINE. HB 1709's
                # conference on 26 May 2026 is in the floor index twice -- in
                # a video of five bills' conferences and in one of its own --
                # with no notice to give either a time, so neither was folded
                # into a timed row, and its card listed HB 1709 twice and said
                # "2 bills" under a title naming one. A card's line carries no
                # video, so two identical lines are one line said twice.
                if P.is_conference(key):
                    kept, seen = [], set()
                    for x in [x for x in rs if x["time"]] or rs:
                        sig = tuple(sorted(x.items()))
                        if sig not in seen:
                            seen.add(sig)
                            kept.append(x)
                    rs[:] = kept
                    continue
                src = [x for x in rs if x.get("study") and x["what"] != "cancelled"]
                if len(src) != 1:
                    continue
                for x in rs:
                    if (not x.get("study") and x["what"].lower() == "study committee"
                            and not x["time"] and not x["venue"]):
                        x["time"], x["venue"] = src[0]["time"], src[0]["venue"]
    return weeks


# KEY DATES ON THE CALENDAR (the owner, 24 October 2026: "those dates should
# show up on the calendar page too under a separate meeting type in the
# key"). The elections, town meeting days and the legislature's own dates
# and deadlines (key_dates.py, which says where each comes from), on their
# days from FROM to KEY_AHEAD days after the build's: a year, so the next
# town meeting day and the next session's first days are a few pages on,
# and no week is written for a date further off than the record can say
# anything about. A week holding one has a page like any other.
KEY_AHEAD = 366


def key_date_days(weeks, today, evs=None):
    """{day: [(key date, role)]} of the Calendar's key dates, each day given
    its place in `weeks` (an empty day where no meeting is on it), so that
    every_week then spans them. One reading for main() and week_labels."""
    hi = today + datetime.timedelta(days=KEY_AHEAD)
    got = KD.days(KD.events(today) if evs is None else evs, FROM, hi.isoformat())
    for d in got:
        x = datetime.date.fromisoformat(d)
        weeks[week_key(x)].setdefault(d, OrderedDict())
    return got


def every_week(weeks, today):
    """Give every ISO week from the first to the last a place in `weeks`.

    A WEEK WITH NOTHING IN IT IS STILL A WEEK. Only weeks holding a sitting
    used to get a page, so "The week after" on 15-21 June 2026 went to 17-23
    August -- eight weeks on, under a label that says one -- and an address
    like /calendar/2026-W30 was a 404. The empty weeks are given their Monday
    with nothing on it, which is what week_page reads a span from, and they
    are pages like any other that say plainly nothing was on.

    The current week is always in the range, so the tab opens on it out of
    session rather than on whenever the House last sat. Returns how many
    weeks were added.
    """
    keys = set(weeks) | {week_key(today)}
    first = min(datetime.date.fromisocalendar(int(k[:4]), int(k[6:]), 1) for k in keys)
    last = max(datetime.date.fromisocalendar(int(k[:4]), int(k[6:]), 1) for k in keys)
    added, d = 0, first
    while d <= last:
        k = week_key(d)
        if k not in weeks or not weeks[k]:
            weeks[k][d.isoformat()] = OrderedDict()
            added += 1
        d += datetime.timedelta(days=7)
    return added


# ---- the official documents behind a card ----------------------------------
#
# A meeting's notice is printed in the House or Senate Calendar, and a
# sitting is recorded in its Journal. Linking both lets a reader check a card
# against the General Court's own document, which is the standard a clerk
# would apply. ONLY ADDRESSES THE RECORD HOLDS: archive/queue.csv names the
# viewer address of every calendar and journal fetched, and nothing here
# builds one from a pattern.
CAL_WORD = {"HC": "House Calendar", "SC": "Senate Calendar"}
JOURNAL_WORD = {"H": "House Journal", "S": "Senate Journal"}


def _words(s):
    return " ".join(re.findall(r"[a-z0-9]+", (s or "").lower()))


def first_notices(path=Path("meetings.json")):
    """({(date, BILL): "HC 32 2026"}, {(date, name words): key}).

    meetings.json is calendar_meetings.py's reading of the calendar PDFs on
    disk, and each row names the calendar that printed it and the date that
    calendar came out. The same notice is reprinted week after week -- this
    week's Solid Waste Working Group is in HC 29, 30, 31 and 32 -- so the one
    linked is the calendar that FIRST printed it. A row with no bill is keyed
    on the committee's name, compared word for word.
    """
    try:
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, {}
    by_bill, by_name = {}, {}
    for r in rows if isinstance(rows, list) else []:
        date = (r.get("date") or "")[:10]
        m = re.match(r"^(\d{4})/(HC|SC)0*(\d+)([A-Z]?)$", r.get("calendar") or "")
        if date < FROM or not m:
            continue
        key = f"{m.group(2)} {int(m.group(3))}{m.group(4)} {m.group(1)}"
        rank = (r.get("noticed") or "9999", int(m.group(3)))
        bill = re.sub(r"\s+", "", r.get("bill") or "").upper()
        k, into = ((date, bill), by_bill) if bill else (
            (date, _words(r.get("committee"))), by_name)
        if k not in into or rank < into[k][0]:
            into[k] = (rank, key)
    return ({k: v[1] for k, v in by_bill.items()},
            {k: v[1] for k, v in by_name.items()})


def doc_links(weeks, cal_urls, notices, journal_keys, sittings):
    """{meeting_key: [(label, address)]} -- the notice's calendar for a
    committee's card, the journal for a floor card.

    `sittings` is {(body, date): "HJ 16"}, the journal each sitting's own rows
    cite (session_days); build_site_v2.journal_url turns that into a file only
    where the number, the year and the file's own date agree.
    """
    import queue_links as B2  # not build_site_v2: see queue_links.py
    by_bill, by_name = notices
    out, n_cal, n_jnl = {}, 0, 0
    floors = {v: k for k, v in FLOOR.items()}
    for days in weeks.values():
        for date, day in days.items():
            for key, rows in day.items():
                links = []
                body = floors.get(key.name)
                if body:
                    url = B2.journal_url(date, sittings.get((body, date)), journal_keys)
                    if url:
                        links.append((f"{JOURNAL_WORD[body]} "
                                      f"{sittings[(body, date)].split()[-1].lstrip('0')}",
                                      url))
                        n_jnl += 1
                else:
                    keys = []
                    for r in rows:
                        k = (by_bill.get((date, (r.get("bill") or "").upper()))
                             if r.get("bill") else by_name.get((date, _words(key.name))))
                        if k and k in cal_urls and k not in keys:
                            keys.append(k)
                    for k in sorted(keys, key=lambda x: (x.split()[2], x.split()[0],
                                                         int(re.match(r"\d+", x.split()[1]).group(0)))):
                        # The year only where it is not the meeting's own: a
                        # January hearing noticed in December's calendar.
                        pre, num, yr = k.split()
                        links.append((f"{CAL_WORD[pre]} {num}"
                                      + (f" of {yr}" if yr != date[:4] else ""),
                                      cal_urls[k]))
                    n_cal += bool(keys)
                if links:
                    out[key] = links
    return out, n_cal, n_jnl


def in_order(day):
    """A day's meeting keys in the order they start, untimed ones last.

    One ordering for the week page and the home rail, so the two list a day's
    committees the same way round.
    """
    # Then by the committee's name, its chamber and a conference's bill, so
    # House Finance and Senate Finance at one hour, or two conferences, come
    # the same way round every time.
    return sorted(day, key=lambda k: (min((r["time"] or "~") for r in day[k]),
                                      k.name, k.chamber, BO.bill_key(k.bill)))


def sitting_pages(site):
    """{(body, date)} -- the sitting pages build_session_pages actually wrote.

    Read off the disk rather than recomputed, so a calendar card can never
    link to a day that was not built.
    """
    out = set()
    root = Path(site) / "session"
    if root.exists():
        for d in root.iterdir():
            if d.is_dir():
                for f in d.glob("*.html"):
                    out.add((d.name.upper(), f.stem))
    return out


def day_words(d, today, lang="en"):
    """("Monday, September 21", "in 3 days") -- a day's heading and how far off
    it is from `today`. The page's script writes the second part again in the
    reader's own clock; this is what a reader without script is given.
    In Spanish: ("lunes, 21 de septiembre", "en 3 días")."""
    x = datetime.date.fromisoformat(d)
    off = (x - today).days
    # <= 14, as HOME_JS has it: `< 14` left a day exactly a fortnight off
    # with no label at all until the script wrote one.
    rel = (say(lang, "cal.today", "today") if off == 0
           else say(lang, "cal.tomorrow", "tomorrow") if off == 1
           else say(lang, "cal.in_days", "in {n} days", n=off) if 0 < off <= 14 else "")
    return S.date_words(x, "day", lang), rel


def week_facts(key, weeks, today, events=None, lang="en"):
    """What a week's page says about the week: its span, the days it lists,
    its cards and the lead sentence that counts them.

    One function, because two things say it: the week's own page, and the
    month files the Calendar page's script reads when a reader moves to
    another week -- the heading and the lead it shows then are these.

    `events` is key_date_days()'s: a Saturday or Sunday holding a key date is
    listed as one holding a meeting is. A key date is not a meeting, so the
    lead and the counts leave it out."""
    days_raw = weeks[key]
    dated = sorted({d for d in days_raw if days_raw[d]}
                   | {d for d in (events or {})
                      if week_key(datetime.date.fromisoformat(d)) == key})
    first = monday(datetime.date.fromisoformat(min(dated) if dated
                                               else min(days_raw)))
    last = first + datetime.timedelta(days=6)

    # EVERY WEEKDAY, WITH OR WITHOUT A MEETING. A week listing only the days
    # that held something let a quiet Monday simply vanish, and a reader
    # could not tell a day with nothing on it from a day missing from the
    # page. Monday to Friday are always drawn, an empty one saying so; a
    # Saturday or Sunday only when something is on it, because the General
    # Court does not keep weekends and seven headings over two empty days
    # would be noise.
    shown = sorted(set(dated) | {(first + datetime.timedelta(days=i)).isoformat()
                                 for i in range(5)})
    # THE WEEK IS NAMED BY THE DAYS IT SHOWS: "February 16–20, 2026", Monday
    # to Friday, as the approved Calendar names it (9 October 2026), and to
    # the Saturday or Sunday where one holds a meeting. WEEK_JS's weekLabel
    # says the same from a key alone.
    end = datetime.date.fromisoformat(shown[-1])
    label = span_words(first, end, lang=lang)
    short = span_words(first, end, "medium", lang)
    meets, days = {}, OrderedDict()
    for date in shown:
        for k, rows in (days_raw.get(date) or {}).items():
            meets[k] = rows
        days[date] = in_order(days_raw.get(date) or {})
    # A CANCELLED MEETING IS SHOWN AND NOT COUNTED. Its card stays, marked, so
    # a reader who saw the notice can see it did not happen; but it is not a
    # sitting, and counting every card said "22 sittings on 5 days" of the
    # week of 13 January 2025, when one of the 22 was the Opioid Abatement
    # commission's cancelled meeting. The same cards are left out of the
    # week script's count, which reads data-cancelled off the card.
    live = {k for k, rows in meets.items() if not P.is_cancelled(rows)}
    off = len(meets) - len(live)
    n = sum(1 for v in days.values() for k in v if k in live)

    # NO SUMMARY OVER A WEEK THAT HAS SITTINGS (the person, 7 October 2026,
    # F11: remove "22 sittings on 5 days, covering 15 bills. A committee
    # appears once a day ..."). The count is the filter's own line beside the
    # views, which says it for what is shown; the week's cards say the rest.
    # What stays is the line for a week with nothing to show -- every meeting
    # cancelled, or none set -- which says why the days below are empty.
    # The paragraph is still written, empty, because the script writes "could
    # not be loaded" into it; app.css draws an empty one as nothing.
    if n:
        lead = ""
    elif off:
        lead = (say(lang, "calp.cancelled_one", "The one meeting set for this week was cancelled.")
                if off == 1 else
                say(lang, "calp.cancelled_all", "All {n} meetings set for this week were cancelled.",
                    n=off))
    else:
        # In the tense of the week: a week that is over has nothing on the
        # record, and one still to come has nothing scheduled yet -- "yet",
        # because the study committees are read from a dated copy.
        # MOSTLY (the survey of 7 October 2026): both chambers sat until veto
        # day, 19 August, in 2026, and into the autumn in most years.
        lead = ((say(lang, "calp.none_past", "No meetings are on the record for this week.")
                 if last < today
                 else say(lang, "calp.none_yet", "No meetings are scheduled yet for this week."))
                + " "
                + say(lang, "calp.sits", "The General Court sits mostly from January to June, and "
                      "committees meet on bills from the fall filing period onward."))
    return {"first": first, "last": last, "label": label, "short": short, "days": days,
            "meets": meets, "n": n, "lead": lead}


# ---- the Calendar page's controls -------------------------------------------
#
# ALL OF IT IS EMITTED HIDDEN AND THE SCRIPT UNHIDES IT, as the week's filter
# always was. A reader without script gets the week as a list, which is the
# whole answer to no filter at all; a control that does nothing is worse than
# no control.
#
# THE COLOURS ARE THE FILTER (25 September 2026). The person, having used
# the page: "Maybe change the selector to checkboxes on the color code, so
# each one is selected on by default aside from study committees and the
# checkbox matches the color of the meeting type. The more detailed filter
# would remain on the sidebar." So the key under the view switch became a
# row of six boxes, one per kind of meeting, each in its colour, named in
# title case; and the side keeps the search, the chamber and the committees
# chosen by name. The "who is meeting" and "what kind of committee meeting"
# questions, and the two quick choices that set them, are gone: the boxes
# ask the one question they were two halves of.
#
# `value` is what the script and the address call a box (WEEK_JS's CATS, in
# the same order); the class is the colour, build_pages.MEET_LEGEND's; the
# last field is whether it starts ticked. A study or statutory committee is
# Study Committee whatever kind of meeting it held, and a work session no
# longer shares a box, or a colour, with one.
#
# KEY DATES, THE SEVENTH (the owner, 24 October 2026: "those dates should
# show up on the calendar page too under a separate meeting type in the
# key"): the elections, town meeting days and the legislature's own dates
# and deadlines (key_dates.py), in a colour of their own, ticked for a new
# reader. Not a kind of meeting, so no meeting is counted under it, and the
# count line above the schedule counts meetings still.
CATEGORIES = (("hearing", "k-hearing", True),
              ("exec", "k-exec", True),
              ("work", "k-meet", True),
              ("conf", "k-conf", True),
              ("floor", "k-floor", True),
              ("study", "k-study", False),
              ("date", "k-date", True))


def legend_word(word, lang="en"):
    """One of build_pages.MEET_LEGEND's names in `lang`: the kinds' own words
    (words/meeting_kinds.json, said as the chips say them), and the seventh's."""
    if lang == i18n.DEFAULT:
        return word
    if word == "Important Dates":
        return say(lang, "calp.important_dates", "Important Dates")
    return i18n.say_word(lang, "kind", word)


def cats_html(lang="en"):
    """The row of boxes, hidden until the script shows it, and the key a
    reader without script is given in its place, which the script hides.

    A real checkbox in a label, laid over a box drawn in its colour (app.css,
    .calcat): the drawing is the key, the checkbox the filter. The key is
    the same seven names and colours, so the page reads the same either way.
    """
    names = {c: legend_word(w, lang) for c, w in P.MEET_LEGEND}
    assert [c for _v, c, _on in CATEGORIES] == [c for c, _w in P.MEET_LEGEND], (
        "the Calendar's boxes and build_pages.MEET_LEGEND name the kinds differently")
    boxes = "".join(f'<label class="calcat {c}"><input type="checkbox" name="cat" '
                    f'value="{v}"{" checked" if on else ""}>'
                    f'<span class="cbx" aria-hidden="true"></span>{S.E(names[c])}</label>'
                    for v, c, on in CATEGORIES)
    return ('<fieldset class="calcats" id="calcats" hidden>'
            f'<legend class="sr">{say(lang, "calp.kinds_legend", "Kinds of meeting to show")}</legend>'
            f'<div class="calcatrow">{boxes}</div></fieldset>'
            f'<ul class="calkey" aria-label="{say(lang, "calp.colors", "What the colors mean")}">'
            + "".join(f'<li><i class="{c}" aria-hidden="true"></i>{S.E(legend_word(w, lang))}</li>'
                      for c, w in P.MEET_LEGEND)
            + "</ul>")


def side_html(lang="en"):
    """The month grid's frame and the detailed filters, down the left.

    The grid's days are the script's to draw -- which of them is today, and
    so which are past, is the reader's clock and not the build's -- so the
    table is emitted empty.

    THE CHAMBER STAYS. Kept on 25 September 2026 when the kinds of meeting
    moved to the boxes: "only the House" is the question a clerk or a member
    of one chamber asks first, and choosing every House committee by name
    would be thirty ticks for it. Study committees are no chamber's, and a
    committee of conference is both chambers'.
    """
    find = ('<label class="wkfind" for="wkfind">' + say(lang, "calp.find_label", "Bill or committee")
            + '<input type="search" id="wkfind" autocomplete="off" placeholder="'
            + say(lang, "calp.find_ph", "Bill number or committee") + '"></label>')
    chamber = ('<fieldset class="calfs"><legend>' + say(lang, "calp.chamber", "Chamber")
               + '</legend><div class="wkchips">'
               '<button type="button" data-body="" aria-pressed="true">'
               + say(lang, "calp.both_chambers", "Both chambers") + '</button>'
               '<button type="button" data-body="H" aria-pressed="false">'
               + say(lang, "calp.house", "House") + '</button>'
               '<button type="button" data-body="S" aria-pressed="false">'
               + say(lang, "calp.senate", "Senate") + '</button>'
               '</div></fieldset>')
    # Committees chosen by name show only those committees, in the kinds
    # ticked in the row of boxes -- which a reader choosing here cannot see
    # from the side on a desktop, so it is said while any are chosen.
    pick = ('<fieldset class="calfs cpick"><legend>' + say(lang, "calp.only_these", "Only these committees")
            + '</legend><div class="cpchosen" id="cpchosen"></div>'
            '<p class="calhint" id="pickhint" hidden>'
            + say(lang, "calp.pick_hint", "Only the committees chosen here are shown, in the kinds of "
                  "meeting ticked above the schedule. A study committee chosen here is shown either way.")
            + '</p><label class="wkfind" for="cpfind">' + say(lang, "calp.find_cmte", "Find a committee")
            + '<input type="search" id="cpfind" autocomplete="off" placeholder="'
            + say(lang, "calp.cmte_ph", "Name of a committee") + '" aria-controls="cplist"></label>'
            '<button type="button" class="cpall" id="cpall" aria-expanded="false" '
            'aria-controls="cplist">' + say(lang, "calp.browse", "Browse every committee") + '</button>'
            '<div class="cplist" id="cplist" role="group" aria-label="'
            + say(lang, "calp.cmtes_label", "Committees to show") + '" hidden></div>'
            '<p class="calhint" id="cpstat" role="status" aria-live="polite"></p>'
            '</fieldset>')
    return ('<div class="calside" id="calside" hidden>'
            # Past the month and the filters to the schedule, which is a long
            # run of tab stops to cross by keyboard. A button, because it only
            # exists with the script, and a fragment link on a page carrying
            # <base href="/"> would go to the home page.
            '<button type="button" class="calskip" id="calskip">'
            + say(lang, "calp.skip", "Skip to the schedule") + '</button>'
            '<section class="calmonth" aria-labelledby="cmtitle">'
            '<div class="cmhead"><h2 class="cmtitle" id="cmtitle" aria-live="polite"></h2>'
            '<button type="button" class="cmbtn" id="cmprev" aria-label="'
            + say(lang, "calp.month_before", "The month before") + '">&lsaquo;</button>'
            '<button type="button" class="cmbtn" id="cmnext" aria-label="'
            + say(lang, "calp.month_after", "The month after") + '">&rsaquo;</button>'
            '<button type="button" class="cmbtn cmnowb" id="cmnow">'
            + say(lang, "calp.today", "Today") + '</button></div>'
            '<table class="cmgrid" id="cmgrid" role="grid" aria-labelledby="cmtitle"></table>'
            '<button type="button" class="calfold" id="cmfold" aria-expanded="true" '
            'aria-controls="cmgrid">' + say(lang, "calp.only_week", "Show only this week") + '</button>'
            '</section>'
            '<section class="calfilt" aria-labelledby="wkfhead">'
            '<div class="cfhead"><h2 id="wkfhead">' + say(lang, "calp.filter", "Filter the calendar")
            + '</h2><button type="button" class="calfold" id="cffold" aria-expanded="true" '
            'aria-controls="wkfilter">' + say(lang, "calp.hide_filters", "Hide the filters")
            + '</button></div>'
            '<form class="wkfilter" id="wkfilter" role="search" aria-labelledby="wkfhead">'
            + find + chamber + pick
            + '</form></section></div>')


# The view switch, the count and the one control that undoes every filter,
# together above the schedule they act on.
def bar_html(lang="en"):
    """The view switch, the count and the reset, in `lang` (BAR_HTML is
    the English)."""
    return ('<div class="calbar" id="calbar" hidden>'
            '<div class="calviews" role="group" aria-label="'
            + say(lang, "calp.show_as", "Show the schedule as") + '">'
            '<button type="button" data-view="list" aria-pressed="true">'
            + say(lang, "calp.list", "List") + '</button>'
            '<button type="button" data-view="week" aria-pressed="false">'
            + say(lang, "calp.week", "Week") + '</button>'
            '</div>'
            '<p class="wkcount" id="wkcount" role="status" aria-live="polite"></p>'
            # The study committee meetings the count says are hidden, shown
            # (18 October 2026): WEEK_JS's drawCount shows it while they are.
            '<button type="button" class="calshowst" id="calshowst" hidden>'
            + say(lang, "calp.show_them", "Show them")
            + '<span class="sr"> ' + say(lang, "calp.the_study", "(the study committee meetings)")
            + '</span></button>'
            # "Show everything" while the defaults were everything; they are
            # everything but the study committees now, so it says what it does.
            '<button type="button" class="calreset" id="calreset" hidden>'
            + say(lang, "calp.reset", "Reset filters") + '</button></div>')


BAR_HTML = bar_html()


def pager_html(key, weeks, order, at, today, lang="en"):
    """[link]: the week's pager, as WEEK_JS's navHtml draws it again.

    IN TITLE CASE, AND EACH SAYING WHERE IT LEADS (the person, 9 October
    2026: "This week should be This Week, The week before should be Previous
    Week, The week after should be Next Week"). Previous Week on the left and
    Next Week on the right, each with the week it leads to under it in the
    pager's short form ("Feb 9–13, 2026"), and This Week between them on any
    week but this one. The class comes before the address on each link:
    preflight counts 'class="wknext" href=' in a page's text, and the page's
    script, which writes the same links with a data-step between the two,
    must not be counted with them."""
    def short(k):
        return S.E(week_facts(k, weeks, today, lang=lang)["short"])
    nav = []
    if at > 0:
        nav.append(f'<a class="wkprev" href="{S.canon(href_for(order[at - 1], today, lang))}">'
                   f'<span class="wkpw">&lsaquo; {say(lang, "calp.prev_week", "Previous Week")}</span>'
                   f'<span class="wkpd">{short(order[at - 1])}</span></a>')
    here = week_key(today)
    if key != here and here in order:
        nav.append(f'<a class="wkhere" href="{S.canon(lang_prefix(lang) + "/calendar.html")}">'
                   f'{say(lang, "calp.this_week", "This Week")}</a>')
    if at < len(order) - 1:
        nav.append(f'<a class="wknext" href="{S.canon(href_for(order[at + 1], today, lang))}">'
                   f'<span class="wkpw">{say(lang, "calp.next_week", "Next Week")} &rsaquo;</span>'
                   f'<span class="wkpd">{short(order[at + 1])}</span></a>')
    return nav


def week_labels(site, today=None):
    """{"2026-W21": "May 18–22, 2026", ...}: every week main() writes a page
    for, by the name its page gives it, for a session day's pager, whose
    middle link names the day's week as the Calendar does ("The Week of
    February 16–20, 2026").

    FOR A STEP THAT RUNS BEFORE THIS ONE AND LINKS A WEEK. A sitting's page
    (build_session_pages.py) is written before the weeks are, so on a machine
    that starts empty it cannot read them off the disk. This is main()'s own
    reading, in main()'s order: the proceedings and the study committees'
    meetings, then every week from the first to the last. {} when there are
    no weeks, which is when main() stops without writing one."""
    weeks = collect(Path(site), statstud()[0])[0]
    if not weeks:
        return {}
    today = today or build_date.today()
    events = key_date_days(weeks, today)
    every_week(weeks, today)
    return {k: week_facts(k, weeks, today, events)["label"] for k in weeks}


# ONE CALENDAR PAGE FOR SEARCH ENGINES (17 October 2026, the person's
# decision). The person wants one link to the calendar, /calendar, which opens
# on the current week, to be the page search engines list, rather than a
# page for every week. So no week is in the sitemap, and every week's own
# page, the current week's dated copy included, carries this: not indexed,
# its links still followed, so the bills and sittings a week links are found
# through it. /calendar itself carries nothing and is listed.
WEEK_ROBOTS = '<meta name="robots" content="noindex,follow">'


# STUDY AND STATUTORY COMMITTEES ARE HIDDEN IN THE BUILT WEEK TOO (18 October
# 2026). The Study Committee box has started unticked since 25 September, but
# only the script hid the cards: the week's own HTML carried every one of
# them, so a reader without script, and every reader for the moment before
# the script ran, saw the week of 12 October 2026 as 24 cards of which 18
# were study committees -- the clutter the person asked to be rid of.
#
# So the built week hides them as the script does, and says so once: the
# week's one line counts them, with a box that shows them. The box is a real
# checkbox whose state app.css reads (.calst), so it works with no script at
# all; the script draws the schedule again from the cards, and its own line
# and "Show them" take its place. A card counts as a study committee's by the
# rule the script's filter uses (build_pages.meeting_who); a day holding
# nothing else says so, while the box is unticked, with a label for that
# box -- "Study committee meetings only. Show them", the script's words
# (emptyHtml; the R2 polish batch, 30 October 2026, where it said "No
# meetings shown.").
def study_only(lang="en"):
    """STUDY_ONLY in `lang`."""
    return ('<p class="calempty calstonly">'
            + say(lang, "calp.study_only", "Study committee meetings only.")
            + ' <label for="calst">' + say(lang, "calp.show_them", "Show them") + '</label></p>')


STUDY_ONLY = study_only()


def study_hidden(days, meets, draw, lang="en"):
    """The week's schedule as its page carries it: each day `draw({date:
    keys})` makes it, a day of study committees alone with STUDY_ONLY after
    its cards, and the box and the line that shows them first, where the
    week has any."""
    parts, live, off = [], 0, 0
    for date, keys in days.items():
        html = draw({date: keys})
        study = [k for k in keys if P.meeting_who(k.name, meets[k]) == "study"]
        live += sum(1 for k in study if not P.is_cancelled(meets[k]))
        off += sum(1 for k in study if P.is_cancelled(meets[k]))
        if keys and len(study) == len(keys):
            assert html.endswith("</div>"), f"{date}: a day's block no longer ends its div"
            html = html[:-len("</div>")] + study_only(lang) + "</div>"
        parts.append(html)
    if not (live or off):
        return "".join(parts)
    # Counted as the script's line counts them: a cancelled meeting is not
    # a meeting, unless it is all the week holds.
    # The sentence whole, one key for each, so a language puts the verb where it goes.
    if live:
        hid = (say(lang, "calp.st_hidden_one", "1 study committee meeting is hidden.") if live == 1
               else say(lang, "calp.st_hidden", "{n} study committee meetings are hidden.", n=live))
        shown = (say(lang, "calp.st_shown_one", "1 study committee meeting is shown.") if live == 1
                 else say(lang, "calp.st_shown", "{n} study committee meetings are shown.", n=live))
    else:
        hid = (say(lang, "calp.stc_hidden_one", "1 cancelled study committee meeting is hidden.")
               if off == 1 else say(lang, "calp.stc_hidden",
                                    "{n} cancelled study committee meetings are hidden.", n=off))
        shown = (say(lang, "calp.stc_shown_one", "1 cancelled study committee meeting is shown.")
                 if off == 1 else say(lang, "calp.stc_shown",
                                      "{n} cancelled study committee meetings are shown.", n=off))
    # Named by the week line's label alone: each study day's <label for="calst">
    # joined its name, "Show them" six times over (the review of 30 October 2026).
    line = ('<input type="checkbox" class="calst" id="calst" aria-labelledby="calstl">'
            '<p class="calstline">'
            f'<span class="cs-off">{hid}</span>'
            f'<span class="cs-on">{shown}</span> '
            '<label for="calst" id="calstl"><span class="cs-off">'
            + say(lang, "calp.show_them", "Show them") + '</span>'
            '<span class="cs-on">' + say(lang, "calp.hide_them", "Hide them") + '</span></label></p>')
    return line + "".join(parts)


def week_page(site, base, key, weeks, order, at, titles, years, code, urls,
              today, sessions=frozenset(), study=False, docs=None, picker="",
              events=None, lang="en"):
    """Write one week's page. `study` is whether the calendar holds the study
    and statutory committees' meetings from the database copy; the page's
    description claims them only then.

    `picker` is the Calendars & Journals section (calendar_documents.
    block_html), the same on every week because a reader may be on any of
    them; "" where there is no list, and then the page carries no section and
    no script for one.

    NO NOTE OF WHERE THEY COME FROM. The page said under its key that they
    come "from the General Court's own database, as copied on 8 September
    2026", and that nothing had refreshed the copy; the person asked on 25
    September 2026 for the explanation to go. The build still says which
    copy it read, every run (main), so it is not silent about it.

    `events` is key_date_days()'s: each key date is a card on its day, before
    the day's meetings, under the Important Dates box (24 October 2026; Key Dates until that evening).

    `lang` is the page's language (the Calendar in Spanish, 9 November 2026):
    "es" writes the same week at /es/calendar/<week>, its frame, words and
    cards in Spanish, its script week_js("es"). `picker` is then the
    section in Spanish too. Only English's pages are counted and listed."""
    w = week_facts(key, weeks, today, events, lang)
    label, lead, days, meets, n = w["label"], w["lead"], w["days"], w["meets"], w["n"]
    pre = lang_prefix(lang)

    # level=2: the h1 of this page is the week itself, so a day is the
    # section under it. On the home page the days sit under "Coming up"
    # and stay h3.
    body = study_hidden(days, meets, lambda one: P.cal_days(
        one, meets, titles, years, code, lambda d: day_words(d, today, lang), S.E,
        level=2, sessions=sessions, docs=docs, lang=lang, events=events,
        morning=today.isoformat())[0], lang)

    nav = pager_html(key, weeks, order, at, today, lang)
    here = week_key(today)

    path = href_for(key, today, lang)
    # THE CURRENT WEEK IS WRITTEN AT BOTH ITS ADDRESSES. /calendar is the tab,
    # and /calendar/2026-W39 is the address somebody was sent last week as
    # "next week". Leaving the dated file to the build that wrote it then was
    # how it went stale: its "week before" link pointed back at /calendar,
    # which was the same week. The copy is rewritten on every build and names
    # /calendar as the page it copies, so there is one page to index.
    copies = [path] + ([f"{pre}/calendar/{key}.html"] if path == f"{pre}/calendar.html" else [])
    heading = say(lang, "calp.week_of", "The Week of {label}", label=S.E(label))
    scripts = (week_js(lang),) + ((CD.picker_js(lang),) if picker else ())
    # THE PAGE IS THE WEEK AS A LIST, AND THE SCRIPT MAKES IT A CALENDAR.
    # Without script this reads exactly as it did: the week's heading, its
    # lead, the arrows, the key to the colours and every day in order. With
    # it, the month grid and the filters come up down the left, the key
    # becomes the row of boxes that is also the filter, and the list becomes
    # one of three views over the same cards. On every week, empty ones
    # included, so the page reads the same wherever a reader lands. The
    # attributes are what the script needs to know about the page it is on:
    # which week it holds, which week the build called this one, and the
    # first and last weeks there are.
    block = ('<div id="results">'
             f'<div class="wkpage calapp" id="calapp" data-week="{key}" '
             f'data-here="{here}" data-first="{order[0]}" data-last="{order[-1]}">'
             '<div class="calhead">'
             f'<h1>{heading}</h1>'
             + (chrome.lang_note(lang) if lang != i18n.DEFAULT else "")
             + f'<p class="src">{lead}</p>'
             # CITE THIS PAGE UNDER THE LINE, as a guide's is (the audit of 25
             # October 2026, S9), not alone above the week's name, where
             # shell.page sets it. Named and addressed as page() would; the
             # script renames it with the week (rename, in WEEK_JS).
             # (English only: a citation is MLA's, APA's, Chicago's and
             # BibTeX's own English form, and a page cited in one of them is
             # cited from its English page.)
             + (S.cite_block(path, f"The Week of {label}", base,
                          # The week's last day: a week that is over is dated by
                          # itself, and the week that is not is the build day's
                          # (shell.cited never gives a day still to come).
                          S.cited(datetime.date.fromisocalendar(
                              int(key[:4]), int(key[6:]), 7)))
                if lang == i18n.DEFAULT else "")
             # NO LINK DOWN TO THE CALENDARS & JOURNALS (F11): the section is
             # the last block of the schedule's column, where a reader finds it.
             + f'<nav class="wknav" aria-label="{say(lang, "calp.other_weeks", "Other weeks")}">'
             f'{"".join(nav)}</nav>'
             # THE NEXT ELECTION'S DATES (the owner, 19 November 2026: "The general info on
             # upcoming election deadlines should be included on the calendar"): its
             # filing period, primary and general, on every week, however far off --
             # a week's page holds a key date only within KEY_AHEAD.
             + KD.election_dates_html(KD.election_dates(today), today, lang, "h2", "kdnext")
             + '</div>'
             + side_html(lang)
             + '<div class="calmain">'
             + (BAR_HTML if lang == i18n.DEFAULT else bar_html(lang))
             + cats_html(lang)
             + f'<div class="calview" id="calview">{body}</div>'
             # ONE SET OF ARROWS, AT THE TOP, AND A RULE UNDER THE LIST (the
             # owner's walk of dry run 9, 8 November 2026), so the schedule
             # and the Calendars & Journals below it read as two things.
             '<hr class="calend">'
             # BELOW THE SCHEDULE AND ITS ARROWS, inside the schedule's column:
             # as wide as the schedule on a desktop, the last block of the page
             # on a phone. The script redraws #calview and the arrows and
             # leaves this alone.
             + picker
             + '</div>'
             # The hover preview: one element, placed beside whichever day
             # it describes, so it never covers the day being read.
             '<div class="calpeek" id="calpeek" role="tooltip" hidden></div>'
             "</div></div>"
             # Inline in the body, which is where every other page-specific
             # script on this site lives -- shell.page takes no script -- and
             # without its comment lines, which stay here for the reader of
             # the source rather than travelling with 103 pages.
             f"<script>{lean_js(scripts[0])}</script>"
             # A SCRIPT OF ITS OWN, after the Calendar's: neither reads the
             # other, and a fault in one leaves the other running.
             + (f"<script>{lean_js(scripts[1])}</script>" if picker else ""))
    named = say(lang, "calp.week_of", "The Week of {label}", label=label)
    for f in copies:
        # THIS PAGE IN THE OTHER LANGUAGES, for the footer's language list and
        # <html>'s data-alt (shell.page): the same week at the same kind of
        # address, English's without a prefix. Every language the Calendar is
        # built in (i18n.PAGES) is named, so English's pages lead to Spanish's.
        bare = f[len(pre):]
        alts = {c: S.canon(lang_prefix(c) + bare) for c in i18n.LANGS
                if c != lang and i18n.has(c, "calendar.html")}
        # Hreflang when every version is offered to everyone (build_pages.shell
        # does the same), and Spanish's pages unindexed until then.
        listed = alts and all(i18n.offered(c) for c in (lang, *alts))
        alternate = ""
        if listed:
            alternate = "".join(f'<link rel="alternate" hreflang="{c}" href="{base}{a}">'
                                for c, a in {lang: S.canon(f), **alts}.items())
            alternate += (f'<link rel="alternate" hreflang="x-default" href="{base}'
                          f'{alts.get(i18n.DEFAULT, S.canon(f))}">')
        if lang != i18n.DEFAULT and not i18n.offered(lang) and f == f"{pre}/calendar.html":
            alternate += '<meta name="robots" content="noindex">'
        html = S.page(S.template(site, lang, scripts, alts), path=f, canonical=path, base=base,
                      title=f"{named} | Granite Record",
                      # WHAT THE PAGE HOLDS, and no more: it said "Every
                      # hearing..." while it held bill business only.
                      description=(say(lang, "calp.desc_study", "Hearings, work sessions, executive "
                                       "sessions, floor sessions and study and statutory committee "
                                       "meetings of the New Hampshire General Court, {label}.",
                                       label=label)
                                   if study else
                                   say(lang, "calp.desc", "Hearings, work sessions, executive "
                                       "sessions, floor sessions of the New Hampshire General Court, "
                                       "{label}.", label=label)),
                      og_title=named, alternate=alternate,
                      globals={"GR_STATIC": True}, noscript="",
                      skip_label=say(lang, "calp.skip_week", "Skip to the week"), sr_title="",
                      og_type="website", nav_current="calendar.html", cite=False,
                      lang=lang, alts=alts,
                      jsonld=LD.listing(named, say(lang, "calp.ld_desc",
                                                   "The General Court's business, {label}.",
                                                   label=label),
                                        base, S.canon(path)))
        html = html.replace('<div id="results"></div>', block, 1)
        assert '<div class="wkpage calapp"' in html, f"{f}: the template has no results slot"
        if f != f"{pre}/calendar.html":
            html = html.replace('<link rel="canonical"', WEEK_ROBOTS + '\n<link rel="canonical"', 1)
            assert WEEK_ROBOTS in html, f"{f}: the page has no canonical link to put WEEK_ROBOTS beside"
        out = site / f.lstrip("/")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(S.clean_links(html), encoding="utf-8")
    # ONLY /calendar GOES IN THE SITEMAP (17 October 2026, WEEK_ROBOTS says
    # why). This replaced the rule of 16 October that left out a week with no
    # meeting until it had one: with no week listed, that rule has nothing to
    # decide. sitemap_merge takes out every week address an earlier build put
    # there.
    if path == "/calendar.html":
        urls.append(base + S.canon(path))
    return n


# The House prints a calendar most weeks of the year, in session and out of
# it. Three weeks with no new one in the list is more likely a list nobody
# has refreshed than a quiet House, so the build says so; it does not stop.
CD_STALE_DAYS = 21


def documents_problem(cdocs, queue=None, kit=None):
    """Why a run that has no calendars or journals to link is a failed run,
    or "" where it is not one.

    SILENCE IS NOT SUCCESS. With no list this builder draws no section on any
    week, takes the list page and the index off the disk and the list page
    out of the sitemap -- and it did all of that behind one WARNING line and
    an exit of zero, so the night would have published a Calendar page without
    its pickers and called the build good. Two cases are faults:

      - THE QUEUE IS HERE AND NOTHING CAN BE READ FROM IT: a file cut short, a
        header that is not the queue's. A fault on any machine.
      - THE QUEUE IS NOT HERE AND THIS FOLDER WAS FILLED FROM THE KIT. The
        queue is on cloud_kit.json's list, so the kit's contract is that it
        arrived (build_all.KIT_RECORD, as the journal step's kit_required).

    A bare folder with no queue -- a fork, preflight's fixture, a first build
    -- is neither: the page is built without the section and the run says so.
    """
    if cdocs:
        return ""
    queue = Path(queue or CD.QUEUE)
    if queue.exists():
        return (f"{queue.as_posix()} is here and no calendar or journal could be read "
                "from it, so every week would lose its Calendars & Journals section and "
                "the list page would go")
    if kit is None:
        import build_all
        kit = build_all.KIT_RECORD.exists()
    if kit:
        return (f"{queue.as_posix()} is not here and this folder was filled from the kit, "
                "whose list (cloud_kit.json) carries it: every week would lose its "
                "Calendars & Journals section and the list page would go")
    return ""


def documents_files(site, base, cdocs, left_out, urls):
    """Write calendar/documents.json and calendar/documents.html, and put the
    list page's address in `urls`; returns the index's size in bytes.

    BESIDE THE WEEK PAGES, not in calendar/data/, which month_files prunes of
    everything it did not write. And the page's address goes in this run's
    urls, or sitemap_merge would take it out as a /calendar address nobody
    wrote. With nothing to link, neither file is left on disk: a list page
    from an older build would be a page the Calendar no longer links.
    """
    index_f = Path(site) / CD.INDEX_PATH.lstrip("/")
    list_f = Path(site) / CD.LIST_PATH.lstrip("/")
    if not cdocs:
        for f in (index_f, list_f):
            if f.exists():
                f.unlink()
        return 0
    index_f.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(CD.index(cdocs), ensure_ascii=False, separators=(",", ":"))
    index_f.write_text(blob, encoding="utf-8")

    heading, lead, body = CD.list_body(cdocs, left_out)
    first, last = CD.span(cdocs)
    path = CD.LIST_PATH
    description = ("Every House and Senate calendar and journal the New Hampshire General "
                   f"Court publishes as a PDF, {first} to {last}: {len(cdocs):,} documents, "
                   "by year, each linked at the General Court's own address.")
    html = S.page(S.template(site), path=path, base=base,
                  title=f"{heading}, {first}–{last} | Granite Record",
                  description=description, og_title=heading,
                  globals={"GR_STATIC": True}, noscript="",
                  skip_label="Skip to the list", sr_title="", og_type="website",
                  nav_current="calendar.html", cite=False,
                  jsonld=LD.listing(heading, description, base, S.canon(path)))
    # Cite this page under the line, as on the weeks (week_page).
    html = html.replace('<div id="results"></div>',
                        '<div id="results"><div class="clist dirlist cdpage">'
                        f'<h1>{S.E(heading)}</h1><p class="src">{lead}</p>'
                        f'{S.cite_block(path, heading, base, S.cited(*(str(d.date or '') for d in cdocs)))}{body}</div></div>'
                        f"<script>{lean_js(CD.LIST_JS)}</script>", 1)
    assert '<div class="clist dirlist cdpage">' in html, f"{path}: the template has no results slot"
    list_f.write_text(S.clean_links(html), encoding="utf-8")
    urls.append(base + S.canon(path))
    return len(blob.encode("utf-8"))


def lean_js(js):
    """The script without its whole-line comments or its indentation, for
    the page to carry. Safe because no string in WEEK_JS spans a line."""
    return "\n".join(ln.strip() for ln in js.splitlines()
                     if ln.strip() and not ln.lstrip().startswith("//"))


# THE CALENDAR'S SCRIPT IN ANOTHER LANGUAGE (9 November 2026). WEEK_JS is the
# English script and stays so to the byte: a Spanish page carries week_js("es"),
# which is WEEK_JS with the pairs of WEEK_ES put over it, each (the text of
# WEEK_JS, what replaces it), applied once, and a pair that does not find its
# text exactly once stops the build -- so an English edit to a line the Spanish
# rests on is found at once, not by a reader. The words are tr() calls, which
# i18n.page_words gives the page's own for (lang/es.json, the "calp." keys);
# one with no current translation says its English. The dates and clock times
# are components.js's, asked for in the page's language (dw, ds, clk). WHAT THE
# GENERAL COURT WROTE -- a committee's name, a bill's number -- is not in
# these: it is in the cards, which build_pages.cal_days drew in the language.
WEEK_ES = [
    # the page's language, and where its pages are
    (r"""  var G=typeof window!=="undefined"?window:globalThis;
""", r"""  var G=typeof window!=="undefined"?window:globalThis;
  var LANG=G.GR_LANG||"en", ES=LANG==="es", P=ES?"/"+LANG:"";
  function dw(s,f){ return dateWords(s,f,LANG); }
  function ds(a,b,f){ return dateSpan(a,b,f,LANG); }
  function clk(t){ return clock(t,LANG); }
  function cap(s){ return s.charAt(0).toUpperCase()+s.slice(1); }
"""),
    (r"""  var DAYNAME=DW_DAYS, MONTH=DW_MONTHS;""",
     r"""  var DAYNAME=ES?DW_ES.days:DW_DAYS, MONTH=ES?DW_ES.months.map(cap):DW_MONTHS;"""),
    (r"""  function monthWords(m){ return MONTH[+m.slice(5,7)-1]+" "+m.slice(0,4); }""",
     r"""  function monthWords(m){ return MONTH[+m.slice(5,7)-1]+(ES?" de ":" ")+m.slice(0,4); }"""),
    (r"""    return off===0?"today":off===1?"tomorrow":(off>0&&off<=14)?"in "+off+" days":"";""",
     r"""    return off===0?tr("cal.today","today"):off===1?tr("cal.tomorrow","tomorrow")
      :(off>0&&off<=14)?tr("cal.in_days","in {n} days",{n:off}):"";"""),
    (r"""  function plural(n,w){ return n+" "+w+(n===1?"":"s"); }""",
     r"""  function plural(n,w){
    if(!ES) return n+" "+w+(n===1?"":"s");
    return w==="bill"?(n===1?tr("cal.one_bill","1 bill"):tr("cal.n_bills","{n} bills",{n:n}))
      :w==="meeting"?(n===1?tr("calp.one_meeting","1 meeting"):tr("calp.n_meetings","{n} meetings",{n:n}))
      :(n===1?tr("calp.one_committee","1 committee"):tr("calp.n_committees","{n} committees",{n:n}));
  }
  // The counts that name study committees, said whole, as the page's own are.
  function stHid(n){
    return n===1?tr("calp.st_hidden_one","1 study committee meeting is hidden.")
      :tr("calp.st_hidden","{n} study committee meetings are hidden.",{n:n});
  }"""),
    # the card's name span carries lang="en" on a page in another language
    (r"""name=/<span class="calcmte">([^<]*)<\/span>/.exec(html);""",
     r"""name=/<span class="calcmte"(?: lang="en")?>([^<]*)<\/span>/.exec(html);"""),
    # the language control leads to the screen the reader is on, as the address says it
    (r"""    if(s) s.setAttribute("href",location.pathname+location.search+"#results");
  }""", r"""    if(s) s.setAttribute("href",location.pathname+location.search+"#results");
    var en=(location.pathname.replace(/^\/es(?=\/|$)/,"")||"/")+location.search, lo=document.querySelector('#footlang option[value="en"]');
    document.documentElement.setAttribute("data-alt-en",en);
    if(lo) lo.setAttribute("data-href",en);
  }"""),
    # the cards' word for a cancelled meeting
    (r"""if(!(e.cancelled&&w==="Cancelled")) said.push(w); return ""; });""",
     r"""if(!(e.cancelled&&w===tr("calp.cancelled","Cancelled"))) said.push(w); return ""; });"""),
    (r"""+(e.cancelled?'<span class="wkn">Cancelled</span>':n?""",
     r"""+(e.cancelled?'<span class="wkn">'+tr("calp.cancelled","Cancelled")+'</span>':n?"""),
    (r"""+'<span class="sr">: open it in the list</span></button>')+'</li>';""",
     r"""+'<span class="sr">: '+tr("calp.open_list","open it in the list")+'</span></button>')+'</li>';"""),
    # what an emptied day says
    (r"""    if(!cards.length) return "No meetings";
    if(studyOnly(cards,f)) return "Study committee meetings only.";
    return (cards.length===1?"1 meeting is":cards.length+" meetings are")+" hidden by the filters.";""",
     r"""    if(!cards.length) return tr("calp.no_meetings","No meetings");
    if(studyOnly(cards,f)) return tr("calp.study_only","Study committee meetings only.");
    return cards.length===1?tr("calp.hid_one","1 meeting is hidden by the filters.")
      :tr("calp.hid_many","{n} meetings are hidden by the filters.",{n:cards.length});"""),
    (r"""      ? ' <button type="button" class="calshowday">Show them'
        +'<span class="sr"> (the study committee meetings)</span></button>' : "");""",
     r"""      ? ' <button type="button" class="calshowday">'+tr("calp.show_them","Show them")
        +'<span class="sr"> '+tr("calp.the_study","(the study committee meetings)")+'</span></button>' : "");"""),
    # the count line
    (r"""      return (t.study===1 ? "1 study committee meeting is" : t.study+" study committee meetings are")
        +" hidden.";
    if(t.shown===t.total)
      line=(t.total?plural(t.total,"meeting"):"No meetings")+" "+where+".";
    else if(!t.seen)
      line=t.total===1 ? "The one meeting "+where+" does not match."
                       : "None of the "+t.total+" meetings "+where+" match.";
    else
      line=t.shown+" of "+plural(t.total,"meeting")+" shown"
        +(where==="this week"?"":" "+where)+".";""",
     r"""      return stHid(t.study);
    if(t.shown===t.total)
      line=t.total?tr("calp.count_where","{count} {where}.",{count:plural(t.total,"meeting"),where:where})
        :tr("calp.none_where","No meetings {where}.",{where:where});
    else if(!t.seen)
      line=t.total===1 ? tr("calp.one_nomatch","The one meeting {where} does not match.",{where:where})
                       : tr("calp.all_nomatch","None of the {n} meetings {where} match.",{n:t.total,where:where});
    else
      line=where===tr("calp.where_week","this week")
        ?tr("calp.shown_of","{shown} of {count} shown.",{shown:t.shown,count:plural(t.total,"meeting")})
        :tr("calp.shown_of_where","{shown} of {count} shown {where}.",
            {shown:t.shown,count:plural(t.total,"meeting"),where:where});"""),
    (r"""      line+=" "+(t.study===1 ? "1 study committee meeting is"
                             : t.study+" study committee meetings are")
        +" hidden.";""",
     r"""      line+=" "+stHid(t.study);"""),
    # the grid
    (r"""    if(!on){ cls.push("cmoff"); name+=", not on the calendar"; }
    else if(!day) name+=", loading";""",
     r"""    if(!on){ cls.push("cmoff"); name+=", "+tr("calp.not_on","not on the calendar"); }
    else if(!day) name+=", "+tr("calp.loading_s","loading");"""),
    (r"""      name+=", "+(live?plural(live,"meeting"):!hidden?"no meetings"
        :studyOnly(meetings(day.cards),c.f)?"study committee meetings only":"no meetings shown");
      if(vis.length>live) name+=", "+(vis.length-live)+" cancelled";""",
     r"""      name+=", "+(live?plural(live,"meeting"):!hidden?tr("calp.no_mtgs_s","no meetings")
        :studyOnly(meetings(day.cards),c.f)?tr("calp.study_only_s","study committee meetings only")
        :tr("calp.none_shown_s","no meetings shown"));
      if(vis.length>live) name+=", "+tr("calp.n_cancelled","{n} cancelled",{n:vis.length-live});"""),
    (r"""        return '<th scope="col"><span aria-hidden="true">'+n.slice(0,2)""",
     r"""        return '<th scope="col"><span aria-hidden="true">'+(ES?cap(n.slice(0,2)):n.slice(0,2))"""),
    # the preview
    (r"""    if(!day) return h+'<p class="pkmore">Loading&hellip;</p>';""",
     r"""    if(!day) return h+'<p class="pkmore">'+tr("calp.loading","Loading")+'&hellip;</p>';"""),
    (r"""        : day.cards.length ? "Nothing on this day matches the filters." : "Nothing is scheduled.")+'</p>';""",
     r"""        : day.cards.length ? tr("calp.day_nomatch","Nothing on this day matches the filters.")
        : tr("calp.nothing","Nothing is scheduled."))+'</p>';"""),
    (r"""(e.cancelled?' <em>cancelled</em>':"")+'</span></li>';""",
     r"""(e.cancelled?' <em>'+tr("calp.cancelled_l","cancelled")+'</em>':"")+'</span></li>';"""),
    (r"""    if(vis.length>cap) h+='<p class="pkmore">and '+(vis.length-cap)+' more</p>';""",
     r"""    if(vis.length>cap) h+='<p class="pkmore">'+tr("calp.and_more","and {n} more",{n:vis.length-cap})+'</p>';"""),
    # where the pages are
    (r"""  function hrefFor(k){ return k===HERE?"/calendar":"/calendar/"+k; }""",
     r"""  function hrefFor(k){ return k===HERE?P+"/calendar":P+"/calendar/"+k; }"""),
    (r"""  var TAB=/\.html$/.test(location.pathname)?"/calendar.html":"/calendar";""",
     r"""  var TAB=/\.html$/.test(location.pathname)?P+"/calendar.html":P+"/calendar";"""),
    (r"""    fetch("/calendar/data/"+m+".json").then(function(r){""",
     r"""    fetch(P+"/calendar/data/"+m+".json").then(function(r){"""),
    (r"""      ORIGIN=CANON.indexOf("/calendar")>0?CANON.slice(0,CANON.indexOf("/calendar")):location.origin;""",
     r"""      ORIGIN=CANON.indexOf(P+"/calendar")>0?CANON.slice(0,CANON.indexOf(P+"/calendar")):location.origin;"""),
    # the heading and the title
    (r"""WEEKS[PAGEWEEK]={label:h1.textContent.replace(/^The Week of /,""), lead:lead?lead.textContent:""};""",
     r"""WEEKS[PAGEWEEK]={label:h1.textContent.slice(tr("calp.week_of","The Week of {label}",{label:""}).length),
                   lead:lead?lead.textContent:""};"""),
    (r"""    h1.textContent="The Week of "+label;
    if(lead) lead.textContent=broken()?"The meetings of this week could not be loaded here."
                                      :w?w.lead:"";
    document.title="The Week of "+label+" | Granite Record";""",
     r"""    h1.textContent=tr("calp.week_of","The Week of {label}",{label:label});
    if(lead) lead.textContent=broken()?tr("calp.week_cant","The meetings of this week could not be loaded here.")
                                      :w?w.lead:"";
    document.title=tr("calp.week_of","The Week of {label}",{label:label})+" | Granite Record";"""),
    # the pager
    (r"""<span class="wkpw">&lsaquo; Previous Week</span>'""",
     r"""<span class="wkpw">&lsaquo; '+tr("calp.prev_week","Previous Week")+'</span>'"""),
    (r"""data-today="" href="'+hrefFor(tk)+'">This Week</a>';""",
     r"""data-today="" href="'+hrefFor(tk)+'">'+tr("calp.this_week","This Week")+'</a>';"""),
    (r"""<span class="wkpw">Next Week &rsaquo;</span>'""",
     r"""<span class="wkpw">'+tr("calp.next_week","Next Week")+' &rsaquo;</span>'"""),
    # the count above the schedule
    (r"""    var t=broken()?"The meetings could not be loaded."
      :!tl?""
      :countLine(tl, S.v==="day"?"on "+dayWords(SEL):"this week");""",
     r"""    var t=broken()?tr("calp.cant","The meetings could not be loaded.")
      :!tl?""
      :countLine(tl, S.v==="day"?tr("calp.where_day","on {day}",{day:dayWords(SEL)})
                  :tr("calp.where_week","this week"));"""),
    (r"""      || '<p class="calempty">Nothing this week matches the filters.</p>';""",
     r"""      || '<p class="calempty">'+tr("calp.week_nomatch","Nothing this week matches the filters.")+'</p>';"""),
    # the Day view, which no control leads to now and whose words are said all the same
    (r"""    var step='<nav class="calstep" aria-label="Other days">'""",
     r"""    var step='<nav class="calstep" aria-label="'+tr("calp.other_days","Other days")+'">'"""),
    (r"""+'<span class="wkpw">&lsaquo; Previous Day</span>""",
     r"""+'<span class="wkpw">&lsaquo; '+tr("calp.prev_day","Previous Day")+'</span>"""),
    (r"""+'<span class="wkpw">Next Day &rsaquo;</span>""",
     r"""+'<span class="wkpw">'+tr("calp.next_day","Next Day")+' &rsaquo;</span>"""),
    # the week at a glance
    (r"""          +' aria-label="'+DAYNAME[weekday(d)]+' '+dw(d,"short")+(d===TODAY?", today":"")+': open this day">'""",
     r"""          +' aria-label="'+DAYNAME[weekday(d)]+' '+dw(d,"short")+(d===TODAY?", "+tr("cal.today","today"):"")
          +': '+tr("calp.open_day","open this day")+'">'"""),
    (r"""+(d===TODAY?" · Today":"")+'</span>'""",
     r"""+(d===TODAY?" · "+tr("calp.today","Today"):"")+'</span>'"""),
    # a week that did not come
    (r"""        ? '<p class="calempty">'+(S.v==="day"?esc(dayWords(SEL)):"The week of "
            +esc(WEEKS[k]?WEEKS[k].label:weekLabel(k)))
          +' could not be loaded here. <a href="'+hrefFor(k)+'">Open '
          +(S.v==="day"?"its week":"it")+' on its own page</a>.</p>'
        : '<p class="calempty">Loading the week&hellip;</p>';""",
     r"""        ? '<p class="calempty">'+(S.v==="day"?esc(dayWords(SEL))+" "+tr("calp.day_fail","could not be loaded here.")
            :tr("calp.week_fail","The week of {label} could not be loaded here.",
                {label:esc(WEEKS[k]?WEEKS[k].label:weekLabel(k))}))
          +' <a href="'+hrefFor(k)+'">'
          +(S.v==="day"?tr("calp.open_week","Open its week on its own page"):tr("calp.open_page","Open it on its own page"))
          +'</a>.</p>'
        : '<p class="calempty">'+tr("calp.loading_week","Loading the week")+'&hellip;</p>';"""),
    # the controls
    (r"""        +'<span class="sr">: stop showing only this committee</span><span aria-hidden="true"> &times;</span></button>';""",
     r"""        +'<span class="sr">: '+tr("calp.stop_only","stop showing only this committee")
        +'</span><span aria-hidden="true"> &times;</span></button>';"""),
    (r"""    ffold.textContent=(side.classList.contains("ffolded")?"Show the filters":"Hide the filters")
      +(n?" ("+n+" on)":"");""",
     r"""    ffold.textContent=(side.classList.contains("ffolded")?tr("calp.show_filters","Show the filters")
      :tr("calp.hide_filters","Hide the filters"))+(n?" ("+tr("calp.n_on","{n} on",{n:n})+")":"");"""),
    (r"""  var CHAMBER={"H":"House","S":"Senate","H S":"House and Senate"};
  var GROUP={standing:"Standing committees and committees of conference",study:"Study and statutory committees",
             floor:"Session days"};""",
     r"""  var CHAMBER={"H":"House","S":"Senate","H S":"House and Senate"};
  var CHAMBER_L={"H":tr("calp.house","House"),"S":tr("calp.senate","Senate"),
                 "H S":tr("calp.house_senate","House and Senate")};
  // The three names the site wrote itself, in the page's language; a committee's own is the record's.
  function nl(n){
    return !ES?"":n==="House Session Day"?tr("cal.house_day","House Session Day")
      :n==="Senate Session Day"?tr("cal.senate_day","Senate Session Day")
      :n==="Committee of conference"?tr("cal.conference","Committee of conference"):"";
  }
  var GROUP={standing:tr("calp.grp_standing","Standing committees and committees of conference"),
             study:tr("calp.grp_study","Study and statutory committees"),
             floor:tr("calp.grp_floor","Session days")};"""),
    (r"""cplist.innerHTML='<p class="calhint">Loading the committees&hellip;</p>'; return; }""",
     r"""cplist.innerHTML='<p class="calhint">'+tr("calp.loading_cmtes","Loading the committees")+'&hellip;</p>'; return; }"""),
    (r"""      return g+'<label class="calchk cpopt"><input type="checkbox" value="'+esc(c[0])+'"'
        +(S.picks.indexOf(c[0])>=0?" checked":"")+'><span>'+esc(c[0])
        +(ch&&!said?' <span class="cpwho">'+ch+'</span>':"")+'</span></label>';
    }).join("")||'<p class="calhint">No committee on the calendar has that in its name.</p>';
    cpstat.textContent=q?plural(rows.length,"committee")+" match.":"";""",
     r"""      return g+'<label class="calchk cpopt"><input type="checkbox" value="'+esc(c[0])+'"'
        +(S.picks.indexOf(c[0])>=0?" checked":"")+'><span'+(ES&&!nl(c[0])?' lang="en"':"")+'>'+esc(nl(c[0])||c[0])
        +(ch&&!said?' <span class="cpwho">'+CHAMBER_L[c[2]]+'</span>':"")+'</span></label>';
    }).join("")||'<p class="calhint">'+tr("calp.no_cmte","No committee on the calendar has that in its name.")+'</p>';
    cpstat.textContent=q?tr("calp.cmtes_match","{count} match.",{count:plural(rows.length,"committee")}):"";"""),
    (r"""      cplist.innerHTML='<p class="calhint">The list of committees could not be loaded.</p>';""",
     r"""      cplist.innerHTML='<p class="calhint">'+tr("calp.cmtes_fail","The list of committees could not be loaded.")+'</p>';"""),
    (r"""    mfold.textContent=on?"Show the whole month":"Show only this week";""",
     r"""    mfold.textContent=on?tr("calp.whole_month","Show the whole month"):tr("calp.only_week","Show only this week");"""),
    (r"""    cpall.textContent=open?"Hide the list":"Browse every committee";""",
     r"""    cpall.textContent=open?tr("calp.hide_list","Hide the list"):tr("calp.browse","Browse every committee");"""),
    # a committee's chip carries its name, which is the record's
    (r"""return '<button type="button" class="cpchip" data-name="'+esc(n)+'">'+esc(n)""",
     r"""return '<button type="button" class="cpchip" data-name="'+esc(n)+'">'+(ES&&!nl(n)?'<span lang="en">'+esc(n)+'</span>':esc(nl(n)||n))"""),
    # a meeting added to the reader's own calendar
    (r"""    var cmte=(m.querySelector(".calcmte")||{}).textContent||"A meeting";""",
     r"""    var cmte=(m.querySelector(".calcmte")||{}).textContent||tr("calp.a_meeting","A meeting");"""),
    (r"""    var note="New Hampshire General Court. "+(kinds||"Meeting")+
      (bills.length? ". Bills: "+bills.join(", ") : "")+
      (last && last!==time ? ". Items are scheduled from "+said(time)+" to "+said(last) : "")+
      ". The General Court does not publish an end time, so this entry is "+
      "one hour long. Source: graniterecord.org";""",
     r"""    var note=tr("calp.ics_head","New Hampshire General Court. {what}",{what:kinds||tr("calp.ics_meeting","Meeting")})+
      (bills.length? tr("calp.ics_bills",". Bills: {list}",{list:bills.join(", ")}) : "")+
      (last && last!==time ? tr("calp.ics_items",". Items are scheduled from {from} to {to}",{from:said(time),to:said(last)}) : "")+
      tr("calp.ics_end",". The General Court does not publish an end time, so this entry is one hour long. Source: graniterecord.org");"""),
    (r"""    var titled=kinds.replace(/\w\S*/g,function(w){""",
     r"""    var titled=ES?kinds:kinds.replace(/\w\S*/g,function(w){"""),
    (r"""    p.innerHTML='<span>Add to calendar</span>'+""",
     r"""    p.innerHTML='<span>'+tr("calp.add_cal","Add to calendar")+'</span>'+"""),
    (r"""'<a class="calics" href="#">Download</a>';""",
     r"""'<a class="calics" href="#">'+tr("calp.download","Download")+'</a>';"""),
]


def week_js(lang="en"):
    """WEEK_JS for a page in `lang`: itself, to the byte, for English."""
    if lang == i18n.DEFAULT:
        return WEEK_JS
    # The dates, the clock and the committee chip words are components.js's, asked for in the page's language.
    js = re.sub(r"\bdateWords\(", "dw(", WEEK_JS)
    js = re.sub(r"\bdateSpan\(", "ds(", js)
    js = re.sub(r"\bclock\(", "clk(", js)
    for old, new in WEEK_ES:
        assert js.count(old) == 1, (f"WEEK_JS no longer holds, exactly once, the text its Spanish "
                                    f"rests on: {old[:70]!r} ({js.count(old)} times)")
        js = js.replace(old, new)
    return js


# ---- the month files ----------------------------------------------------------
#
# WHAT THE SCRIPT READS WHEN A READER LEAVES THE WEEK THE PAGE HOLDS. One file
# a month, calendar/data/2026-09.json, carrying every day of the month the
# calendar covers as the week page draws it -- the day's heading and its cards,
# out of the same cal_days, byte for byte -- and the heading and lead of every
# week that touches the month. The script arranges those cards into a list, a
# week or a day; it never composes one. So there is still one renderer, and
# the month grid's markers, the hover preview and the filters all read the
# attributes the card already carries.
#
# A file a month rather than a week because the grid is a month: the markers
# for thirty days are one request, and the week a reader clicks into is almost
# always in a month already loaded. About two dozen files, none of them a page,
# so none goes in the sitemap.
DATA_DIR = ("calendar", "data")


def month_files(site, weeks, order, titles, years, code, today,
                sessions=frozenset(), docs=None, events=None, lang="en"):
    """Write calendar/data/<YYYY-MM>.json for every month the weeks in `order`
    touch, and calendar/data/committees.json; take out any other .json there.
    `events` is key_date_days()'s: a day's key dates are in its HTML, as the
    week page draws them.

    In Spanish (`lang`, 9 November 2026) the months are written to
    es/calendar/data/, their cards, labels and leads in Spanish, which the
    Spanish page's script fetches (week_js); the committees' list is English's
    alone, the committees' names being the record's own.

    Returns (months written, cards written)."""
    out = Path(site).joinpath(*lang_prefix(lang).strip("/").split("/"), *DATA_DIR)
    out.mkdir(parents=True, exist_ok=True)
    first = datetime.date.fromisocalendar(int(order[0][:4]), int(order[0][6:]), 1)
    last = datetime.date.fromisocalendar(int(order[-1][:4]), int(order[-1][6:]), 7)
    months, d = OrderedDict(), first
    while d <= last:
        months.setdefault(f"{d.year}-{d.month:02d}", []).append(d)
        d += datetime.timedelta(days=1)
    facts, wrote, cards = {}, set(), 0
    for ym, dates in months.items():
        days, wk = OrderedDict(), OrderedDict()
        for x in dates:
            iso, k = x.isoformat(), week_key(x)
            day = (weeks.get(k) or {}).get(iso) or {}
            # EVERY DAY, WEEKENDS AND EMPTY ONES INCLUDED: the Day view of a
            # quiet Saturday says it is quiet, in the words the week page uses.
            html, _m = P.cal_days({iso: in_order(day)}, day, titles, years, code,
                                  lambda dd: day_words(dd, today, lang), S.E, level=2,
                                  sessions=sessions, docs=docs, lang=lang, events=events,
                                  morning=today.isoformat())
            days[iso] = S.clean_links(html)
            cards += len(day)
            if k in weeks and k not in wk:
                if k not in facts:
                    f = week_facts(k, weeks, today, events, lang)
                    # The pager's short name for it too, which Previous Week
                    # and Next Week say under them (WEEK_JS's shortOf).
                    facts[k] = {"label": f["label"], "lead": f["lead"], "short": f["short"]}
                wk[k] = facts[k]
        name = f"{ym}.json"
        (out / name).write_text(json.dumps({"month": ym, "days": days, "weeks": wk},
                                           ensure_ascii=False, separators=(",", ":")),
                                encoding="utf-8")
        wrote.add(name)

    if lang != i18n.DEFAULT:
        for f in out.glob("*.json"):
            if f.name not in wrote:
                f.unlink()
        return len(months), cards

    # EVERY COMMITTEE ON THE CALENDAR, for the picker: its name as the cards
    # print it, whose it is, and its chamber or chambers. Read once, and only
    # when a reader goes looking for a committee. House Judiciary and Senate
    # Judiciary are two entries, because they are two cards; the committees
    # of conference are one, under build_pages.pick_name.
    agg = {}
    for k in order:
        for _date, day in (weeks.get(k) or {}).items():
            for key, rows in day.items():
                a = agg.setdefault(P.pick_name(key), [Counter(), set()])
                a[0][P.meeting_who(key.name, rows)] += 1
                a[1].update(P.card_bodies(key, rows))
    rank = {"standing": 0, "study": 1, "floor": 2}
    names = sorted(([n, c.most_common(1)[0][0], " ".join(sorted(b))]
                    for n, (c, b) in agg.items()),
                   key=lambda r: (rank.get(r[1], 3), r[0].lower()))
    (out / "committees.json").write_text(
        json.dumps(names, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    wrote.add("committees.json")
    # The directory is this builder's alone, and every month is rewritten on
    # every run, so a file it did not write this time is one nothing reads.
    for f in out.glob("*.json"):
        if f.name not in wrote:
            f.unlink()
    return len(months), cards


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site, base = Path(a.site), a.base.rstrip("/")

    global _NAMES
    study_rows, _NAMES, fetched = statstud()
    # SILENCE IS NOT SUCCESS: a build without the database copy still draws
    # every bill's sitting, and says out loud that the study and statutory
    # committees are missing rather than dropping them without a word. The
    # page then claims only what it has.
    if study_rows:
        print(f"  {len(study_rows):,} study and statutory committee meetings from "
              f"the database copy of {fetched or 'an unknown date'}")
    else:
        print("  WARNING: no study or statutory committee meetings -- "
              f"{STATSTUD_DIR}/StatStudMeetings.psv or StatStudDetails.psv is not "
              "on disk, so the calendar shows bill business only")
    if study_rows:
        # SILENCE IS NOT SUCCESS: how many meetings link a recording, and the
        # recordings on no bill that fit no meeting here, said out loud.
        on_bills = {(r.get("video_id") or "").strip() for r in proceedings.load()} - {""}
        linked, unmatched = study_recordings(study_rows, recordings_by_day(), on_bills,
                                             build_date.today().isoformat())
        print(f"  {len(linked):,} study and statutory meetings link their recording"
              + (f"; {len(unmatched):,} recordings since {FROM} on no bill fit no meeting "
                 "here, the newest: " + "; ".join(f"{t} ({d})" for d, t in unmatched[-3:])
                 if unmatched else ""))
    weeks, titles, years, code = collect(site, study_rows)
    # SILENCE IS NOT SUCCESS: no weeks is a Calendar tab pointing at nothing,
    # and a build that said so only by printing a zero.
    assert weeks, f"no proceedings dated {FROM} or later; the calendar would be empty"

    today = build_date.today()
    here = week_key(today)
    # THE KEY DATES, each on its day (key_date_days), before the weeks are
    # filled in: a date past the last meeting gives its week a page.
    events = key_date_days(weeks, today)
    n_kd = sum(len(v) for v in events.values())
    # SILENCE IS NOT SUCCESS: legislative_year and the statutes always give
    # some, so none is a reading that failed.
    assert n_kd, "no key dates from key_dates.events(); the Important Dates box would be empty"
    print(f"  {n_kd} key dates on {len(events)} days, {FROM} to "
          f"{today + datetime.timedelta(days=KEY_AHEAD)} (key_dates.py)")
    # Every week from the first to the last, the current one included, so the
    # arrows step one week at a time and every week has an address.
    empty = every_week(weeks, today)
    order = sorted(weeks)

    sits = sitting_pages(site)
    print(f"  {len(sits):,} sitting pages on disk to link to")

    import queue_links as B2  # not build_site_v2: see queue_links.py
    cal_urls = B2.calendar_keys_from_queue()
    journal_keys = B2.journal_keys_from_queue()
    try:
        import session_days
        sittings = {k: v.journal for k, v in session_days.load().items()
                    if k[1] >= FROM and v.journal}
    except Exception as e:  # the journal links are an addition; the week stands without them
        print(f"  WARNING: session_days would not load ({e!r}); no journal links")
        sittings = {}
    docs, n_cal, n_jnl = doc_links(weeks, cal_urls, first_notices(), journal_keys, sittings)
    # SILENCE IS NOT SUCCESS: printed either way, so a queue or meetings.json
    # that stopped being read shows as a zero rather than as nothing.
    print(f"  {n_cal:,} meetings linked to the calendar that printed their notice, "
          f"{n_jnl:,} floor sittings to their journal ({len(cal_urls):,} calendars "
          f"and {len(journal_keys):,} journals in archive/queue.csv)")
    # CALENDARS & JOURNALS: the list is read once and the same section goes on
    # every week. What was read is said at the end of the run (below).
    cdocs, cd_out = CD.read(today=today)
    # BEFORE ANYTHING IS WRITTEN: a list that should be here and is not stops
    # the run with the site as it was, and says why as the run's last line.
    problem = documents_problem(cdocs)
    if problem:
        print(f"  FAILED: {problem}")
        return 1
    picker = CD.block_html(cdocs, cd_out)
    urls, total = [], 0
    for i, key in enumerate(order):
        total += week_page(site, base, key, weeks, order, i,
                           titles, years, code, urls, today, sits,
                           study=bool(study_rows), docs=docs, picker=picker,
                           events=events)
    # THE SAME WEEKS IN EVERY OTHER LANGUAGE THE CALENDAR HAS (i18n.PAGES):
    # each at its own address under /<code>/, with that language's section of
    # Calendars & Journals, their files and months below. Not counted again.
    langs = [c for c in i18n.LANGS if c != i18n.DEFAULT and i18n.has(c, "calendar.html")]
    for lang in langs:
        picker_l = CD.block_html(cdocs, cd_out, lang=lang)
        for i, key in enumerate(order):
            week_page(site, base, key, weeks, order, i, titles, years, code, [], today, sits,
                      study=bool(study_rows), docs=docs, picker=picker_l, events=events,
                      lang=lang)
    size = documents_files(site, base, cdocs, cd_out, urls)
    if size:
        print(f"  calendar/documents.json ({size:,} bytes) and calendar/documents.html, "
              "the same list as plain links")

    # THE MONTH FILES, which the page's month grid and its other weeks read.
    # SILENCE IS NOT SUCCESS: a run that wrote weeks and no months is a
    # calendar whose grid shows nothing, so it says how many and stops if none.
    n_months, n_cards = month_files(site, weeks, order, titles, years, code,
                                    today, sits, docs, events)
    assert n_months, "no month files were written; the calendar's grid would be empty"
    for lang in langs:
        n_l, _c = month_files(site, weeks, order, titles, years, code, today, sits, docs, events,
                              lang=lang)
        # SILENCE IS NOT SUCCESS: a language's weeks with no months is a grid that shows nothing.
        assert n_l == n_months, (f"{lang}: {n_l} month files for {n_months} in English; the "
                                 "grid of its weeks would be empty")
        print(f"  {lang}: {len(order)} week pages under /{lang}/calendar and {n_l} month files")
    print(f"  {n_months} month files -> calendar/data/ ({n_cards:,} cards, "
          "the same ones the week pages draw), and committees.json for the picker")

    # Every week is rebuilt on every run, so a calendar address in the sitemap
    # that this run did not list -- any week's own page, since 17 October
    # 2026 (WEEK_ROBOTS) -- is taken out, not left beside the rest.
    added, dropped = S.sitemap_merge(site, base, urls, "/calendar")
    if added or dropped:
        print(f"  sitemap.xml: {added} added, {dropped} no longer written taken out")
    # Every week has a dated page, the current one's being its copy.
    print(f"  /calendar in the sitemap; {len(order)} week pages written noindex,follow "
          "and left out of it")

    print(f"  {len(order)} weeks -> calendar.html and calendar/ "
          f"({total:,} sittings; {here} is this week; {empty} weeks with "
          f"nothing on them written as pages of their own)")
    # WHAT THE PICKERS HOLD, LAST, because build_all and the night's log show a
    # step's last three lines and nothing above them. SILENCE IS NOT SUCCESS:
    # printed either way, so a queue that stopped being read shows as a line
    # and not as nothing, and a list that has fallen behind the General
    # Court's own is said to be -- as a warning, never a stop: a picker a few
    # weeks behind is no reason to hold back the day's schedule.
    if cdocs:
        print(f"  {CD.summary(cdocs, cd_out)}")
        # The age is told from the newest listed, and only where that one has
        # a date (CD.behind says why).
        late = CD.behind(cdocs, today, CD_STALE_DAYS)
        if late:
            print(f"  WARNING: the newest House Calendar listed is {CD.day_words(late[0])}, "
                  f"{late[1]} days ago -- if the House has printed one since, "
                  f"{CD.QUEUE.as_posix()} has not been refreshed and the pickers are "
                  "behind the General Court's own list")
    else:
        # Only a bare folder comes here: documents_problem stopped the run
        # above wherever the list ought to have been.
        print(f"  WARNING: no calendars or journals to link -- {CD.QUEUE.as_posix()} is not "
              "on disk, so the week pages carry no Calendars & Journals section")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
