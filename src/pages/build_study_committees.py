#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-18.5
"""
A page for every statutory and study committee the General Court lists as
active, at /committee/ss<CommitteeID>.

    python3 src/pages/build_study_committees.py --site site [--base URL]

WHY (the person, 17 October 2026): "Statutory and study committees should get
their own pages with information from the official source ... Information
about these committees is rather difficult to find for regular users on
GenCourt right now, so improving that experience would be helpful." The plan
the person approved (private/STUDY_COMMITTEES_PLAN.md) took the active ones
first -- 153 on 17 October 2026, 143 statutory and 10 study -- addressed by the
database's own number for each, which stays put when a committee is renamed or
the bill that made it is amended.

WHERE EACH PART COMES FROM. Nothing is asked of anybody; the database copy is
already on this disk, refreshed by the night (nightly.STUDY_NIGHTLY and
STUDY_WEEKLY).

  the committee: its name, class,      db/StatStudDetails.psv
  chamber, the bill and law that made
  it, its rules and its reporting duty
  the bill that made it, where the     db/vStatStudTemp.psv
  details name none
  who sits on it                       db/StatStudMembers.psv: a legislator's
                                       seat by the member's own number, drawn
                                       as the site's one chip from
                                       site/legislators.json; every other seat
                                       as the record describes it
  its meetings                         db/StatStudMeetings.psv, the venue read
                                       as the Calendar reads it
                                       (build_calendar.statstud and place)
  its recordings                       build_calendar.study_recordings: the
                                       Calendar's own matching, so a meeting's
                                       card and its page play the same one
  the statute's heading                site/laws/headings.json (build_rsa.py)
  the bill pages                       site/idx (site_read.bill_index)

WHAT IS NOT HERE YET, AND WHY. The names of members who are not legislators,
and links to the committees' reports and minutes, are on the General Court's
own page for each committee and not in its database: they wait on a fetch of
those pages, which is the person's to start (the plan's step 5). Until then a
public member's seat is described as the record describes it -- "Fifteen
members of the public ... appointed by the governor" -- and never named.

WRITES site/committee/ss<CommitteeID>.html, one an active committee, and
site/study_committees.json, a line each for the readers after it; and adds the
pages to the sitemap through shell.sitemap_merge, owning the /committee/ss*
addresses and nothing of build_committees'. SILENCE IS NOT SUCCESS: a run that
writes no page, or finds no active committee in a copy that is there, fails.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import contextlib
import datetime
import io
import json
import re
from collections import Counter, OrderedDict
from urllib.parse import quote_plus

import build_calendar as BC
import build_date
import build_full_sessions as FS
import build_rsa as RSA
import components as C
import plain_action as PA
import proceedings
import shell as S
import site_read as SR
import structured as LD

E = S.E

# THE VIEWS' COLUMNS, as db/_columns.json names them for the three views it
# describes; the fourth, vStatStudTemp, is not described there and holds the
# six fields below. A view that comes back in another shape stops the run
# (table) rather than reading one field as another.
DETAILS = ["CommitteeID", "CommitteeYear", "Expr1", "Expr2", "CondensedBillNo",
           "ExpandedBillNo", "Committeetype", "CommitteeName", "RSAChapter", "ChapterLaw",
           "ReportDueDate", "ReportFiled", "ReportDate", "EffectiveDate",
           "OtherEffectiveDates", "Comments", "DateModifeid", "CommitteeStatus", "Keywords",
           "CommitteeRepealedDate", "AdditionalReportDates", "FirstMeeting", "Quorum",
           "Report", "TerminationDate", "AmendingBills", "CommitteeTypeID", "LegislationID"]
MEMBERS = ["CommitteeID", "memberno", "SequenceNo", "MemberType", "AppointedBy", "Active",
           "Alternate", "Designee", "NonVotingMember", "Chairperson", "TermStartDate",
           "TermEndDate", "Organization", "username", "DateModified", "Affiliation"]
MEETINGS = ["webtext", "MeetingID", "CommitteeID", "MeetingDate", "MeetingLocation",
            "username", "DateModified"]
TEMP = ["CommitteeID", "CommitteeYear", "CondensedBillNo", "CommitteeName", "RSAChapter",
        "ChapterLaw"]

# THE GENERAL COURT'S TWO CLASSES, AND ITS CHAMBERS. CommitteeStatus is what
# says active, and study or statutory ("Active Chaptered Study Committee",
# "Active Statutory Committee"); the 0/1 Committeetype flag does not track it
# (build_calendar.statstud). CommitteeTypeID files each under a chamber, as
# db/committeeType.psv names the four: 6 House Study, 7 House Statutory, 13
# Senate Study, 14 Senate Statutory.
CHAMBER_OF_TYPE = {"6": "H", "7": "H", "13": "S", "14": "S"}
CHAMBER_WORD = {"H": "House", "S": "Senate"}
CLASS_WORD = {"statutory": "Statutory Committee", "study": "Study Committee"}

# WHAT EACH ONE IS, FROM ITS NAME (the person's answer of 17 October 2026: the
# General Court's two classes group them, and "Commission", "Council",
# "Board" and the rest are each card's kind, from its name). The kind is the
# last of these words before the name's first preposition -- "Business
# Finance Authority Board of Directors" is a board, "Advisory Committee on the
# Human Rights Commission" a committee -- else the first anywhere, else a
# committee, which is what the General Court calls all of them.
KINDS = ("Task Force", "Working Group", "Subcommittee", "Committee", "Commission",
         "Council", "Board", "Authority")
_HEAD = re.compile(r"\s+(?:of|on|to|for|within|regarding|pursuant)\s+", re.I)

# NON-LEGISLATIVE, IN THE LIST'S OWN WORDS. Four active names carry it --
# "==NON-LEGISLATIVE==", "=NON-LEGISLATIVE=" or "(No Legislative Members)" --
# the executive branch's boards the list carries. build_calendar.committee_name
# takes the mark off the name; the page says what it means instead.
NON_LEGISLATIVE = BC.NAME_MARK

# A STATUTE'S ADDRESS AS THE RECORD WRITES IT: "19-P:1", "126-T", "9:3-a,IV",
# "233-A:2, I", "362-H;3" (a semicolon for the colon), "19-a:14".
RSA_ADDR = re.compile(r"^(?:RSA\s*)?(\d+(?:-[A-Za-z]+)?)(?:\s*[:;]\s*(\d+(?:-[a-z]+)?))?", re.I)
BILL_YEAR = re.compile(r"\b([A-Z]{2,5})\s*0*(\d{1,4})\s*\(\s*(\d{4})\s*\)", re.I)

# site/study_committees.json: every page this step wrote, a line each.
INDEX = "study_committees.json"

# The meetings of the last few years are listed; the earlier ones fold away
# under one line, since the record reaches back to 1991 for some and a
# reader comes for the latest.
RECENT_YEARS = 3


def table(db, view, cols):
    """The rows of db/<view>.psv as dicts, or None where the file is not there.

    A view whose columns db/_columns.json names otherwise stops the run: the
    General Court changing a view's shape must not quietly read a name as a
    date. A row with another number of fields than the view has is left out
    and counted, never guessed at."""
    f = Path(db) / f"{view}.psv"
    if not f.exists():
        return None
    try:
        known = json.loads((Path(db) / "_columns.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        known = {}
    if isinstance(known, dict) and view in known and known[view] != cols:
        raise SystemExit(f"{f}: the view's columns are now {known[view]}, not the {len(cols)} "
                         "this step reads. Read the view again before trusting a field of it.")
    rows, odd = [], 0
    for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
        p = ln.split("|")
        if len(p) != len(cols):
            odd += bool(ln.strip())
            continue
        rows.append(dict(zip(cols, p)))
    if odd:
        print(f"  {odd} row(s) of {view} left out: not {len(cols)} fields")
    return rows


def day(s):
    """"11/01/2026 00:00:00" -> date(2026, 11, 1), or None."""
    try:
        return datetime.datetime.strptime((s or "").strip(), "%m/%d/%Y %H:%M:%S").date()
    except ValueError:
        return None


def kind_of(name):
    """"Commission", "Board" ... out of a committee's name (KINDS)."""
    head = _HEAD.split(name or "", 1)[0]
    found = [(m.start(), k) for k in KINDS
             for m in re.finditer(rf"\b{k}\b", head, re.I)]
    if found:
        return max(found)[1]
    found = [(m.start(), k) for k in KINDS for m in re.finditer(rf"\b{k}\b", name or "", re.I)]
    return min(found)[1] if found else "Committee"


def named(name):
    """The committee as a sentence names it, in "Recording of ..." and "Play
    the recording of ...": "the Fiscal Committee"; a name that carries its own
    article keeps the one, small ("the Governor's Commission on Addiction,
    Treatment and Prevention"); and a name that names no body is said bare, as
    the player's bar says it -- "Administrative Rules", which "the" made "the
    Administrative Rules" (the review of 29 October 2026)."""
    name = (name or "").strip()
    if re.match(r"the\s", name, re.I):
        return "the " + name[4:].lstrip()
    if any(re.search(rf"\b{k}\b", name, re.I) for k in KINDS):
        return "the " + name
    return name


# ---- the record's prose, read as it was written ------------------------------
#
# THE DATABASE COPY LOST THE LINE BREAKS INSIDE ITS TEXT, as it did inside a
# meeting's venue (build_calendar.place): the words either side of a break run
# together -- "chairpersons of thehouse and senate committees", "the
# committeeshall be called" -- and a sentence's full stop meets the next one,
# "pursuant to RSA 160-C:16.The committee". Measured on 18 October 2026:
# about sixty such words across the 153 active committees' reporting duties,
# first-meeting rules and quorums.
#
# A WORD IS PARTED ONLY WHERE THE RECORD ITSELF SAYS SO. A small letter met
# by a capital is a lost break -- "onNovember", "PharmacistsAssociation" --
# as it is in a venue. Otherwise the vocabulary is every word of every
# committee's text, all 1,543 of them, as the record spells it elsewhere: a
# word is parted into two the text uses at least five times as often as the
# joined one, and only one way, and a part of two letters only where it is a
# word of two letters ("of each", "at least"). Not only a word used once: the
# copies run together are copied from committee to committee, so
# "thehouse" is in the text forty times, against "house" 6,823, and
# "proposedlegislation" 37 against "proposed" 368. A word the
# statutes' own section headings use (site/laws/headings.json) is a word,
# and kept: "record" is not "re cord", nor "indirect" "in direct"; so are the
# common joined words of English below, and "forth" and "nonpublic", which
# part that way and are in no heading. This is a reading, not a recovery, and
# the run says how many words it parted; a quorum or a duty is never
# reworded.
KEEP_WHOLE = frozenset("""forth nonpublic nonvoting leadingage into onto upon within without
    therein thereof thereto thereafter therefore thereby herein hereby hereof hereafter
    whereas whereby wherein anyone someone everyone another cannot however whatever whenever
    wherever nonetheless notwithstanding forthwith inasmuch insofar itself themselves
    otherwise outside inside together toward towards today become became beforehand
    meantime overall""".split())
TWO = frozenset({"of", "on", "in", "at", "an", "to", "or", "no", "as", "by", "is", "it", "be"})


class Words:
    """The vocabulary prose() parts words by: how often the committees' own
    text uses each (counts) and the words the statutes' headings use (known)."""
    def __init__(self, known=()):
        self.counts, self.known = Counter(), frozenset(known)

    def add(self, texts):
        self.counts.update(w.lower() for t in texts for w in re.findall(r"[A-Za-z]+", t or ""))


def parted(word, words, depth=3):
    """`word` parted where the vocabulary says a break was lost, or None;
    each part read again, so "thehouseofrepresentatives" is four words."""
    lw, n = word.lower(), words.counts
    if lw in KEEP_WHOLE or depth <= 0:
        return None
    # McAuliffe and MacDonald are names, as build_calendar.place reads them,
    # and a brand's small first letter is its own ("eNorth").
    joined = re.search(r"[a-z][A-Z]", re.sub(r"^Ma?c(?=[A-Z])", "MC", word))
    at = joined.start() + 1 if joined and joined.start() > 0 else 0
    if not at:
        if len(lw) < 5 or lw in words.known:
            return None
        least = max(5, 5 * n[lw])
        ways = [i for i in range(2, len(lw) - 1)
                if n[lw[:i]] >= least and n[lw[i:]] >= least
                and (i > 2 or lw[:i] in TWO) and (len(lw) - i > 2 or lw[i:] in TWO)]
        if len(ways) != 1:
            return None
        at = ways[0]
    return " ".join(parted(p, words, depth - 1) or p for p in (word[:at], word[at:]))


def prose(s, vocab, said=None):
    """The record's text as a sentence: its lost breaks restored where the
    vocabulary says so, a space after a comma or a sentence's full stop, and
    the character the copy lost in "committee�s" read as the apostrophe it
    stands between two letters. `said` counts the words parted."""
    s = re.sub(r"(?<=[A-Za-z])�(?=[a-z])", "'", s or "").replace("�", "–")
    s = re.sub(r"([,;])(?=[A-Za-z(])", r"\1 ", s)
    s = re.sub(r"(?<=[a-z0-9)])\.(?=[A-Z][a-z])", ". ", s)

    def one(m):
        p = parted(m.group(0), vocab)
        if p and said is not None:
            said[m.group(0)] += 1
        return p or m.group(0)
    s = re.sub(r"[A-Za-z]+", one, s)
    return re.sub(r"\s+", " ", s).strip()


def seat_words(s, vocab, said=None):
    """A seat as the statute describes it, without the paragraph's letter or
    a note about one appointment: "(j) Fifteen members of the public ...
    (Reappointed 12/12/24)" -> "Fifteen members of the public ..."."""
    s = re.sub(r"\s*\((?:re-?\s*appointed|orig\.?\s*appt\.?|appointed)\b[^)]*\)", "", s or "",
               flags=re.I)
    s = re.sub(r"^\s*(?:\(?[a-z0-9]{1,4}\)|[IVX]+\.)\s*", "", s, flags=re.I)
    t = prose(s, vocab, said)
    return t[:1].upper() + t[1:]


# ---- one committee --------------------------------------------------------------

def rsa_of(rsa, law):
    """(the statute's address, the session law's chapter) as the record has
    them, the two put back where it swapped them. The Law Enforcement Conduct
    Review Committee's row reads RSA "312" and chapter "106-L:17": RSA 106-L:17
    is where the committee is, and chapter 312 of the Laws of 2022 the act."""
    rsa, law = (rsa or "").strip(), (law or "").strip()
    if re.fullmatch(r"\d+", rsa) and re.match(r"\d+-[A-Za-z]+:", law):
        rsa, law = law, rsa
    return rsa, re.sub(r"^0+(?=\d)", "", law)


def statute(rsa, headings, chapters):
    """{"addr", "href", "heading"} for a committee's statute, the link only
    where the Laws pages hold the chapter, and the section's anchor only
    where they hold the section; None where the record names none."""
    m = RSA_ADDR.match((rsa or "").strip())
    if not m:
        return None
    ch = m.group(1).upper()
    sec = f"{ch}:{m.group(2)}" if m.group(2) else ""
    out = {"addr": sec or ch, "href": "", "heading": ""}
    if ch in chapters:
        out["href"] = RSA.href(sec) if sec in headings else RSA.chapter_path(ch)
        out["heading"] = headings.get(sec, "") if sec else (chapters[ch] or [""])[0]
    return out


def read(db, words=None):
    """Every active committee in the copy at `db`, each a dict, in the order
    of their names; None where the details are not on disk. `words` (a
    Words) is given the vocabulary of every committee's text."""
    det = table(db, "StatStudDetails", DETAILS)
    if det is None:
        return None
    members = table(db, "StatStudMembers", MEMBERS) or []
    meets = table(db, "StatStudMeetings", MEETINGS) or []
    temp = {r["CommitteeID"].strip(): r for r in (table(db, "vStatStudTemp", TEMP) or [])}
    if words is not None:
        words.add([r[k] for r in det for k in ("Report", "FirstMeeting", "Quorum", "Comments")]
                  + [r["Organization"] for r in members])
    seats, held = {}, {}
    for s in members:
        seats.setdefault(s["CommitteeID"].strip(), []).append(s)
    for r in meets:
        held.setdefault(r["CommitteeID"].strip(), []).append(r)
    out = []
    for r in det:
        status = r["CommitteeStatus"].strip()
        if not status.lower().startswith("active"):
            continue
        cid = r["CommitteeID"].strip()
        t = temp.get(cid) or {}
        bill = re.sub(r"\s+", "", r["CondensedBillNo"] or t.get("CondensedBillNo") or "").upper()
        rsa, law = rsa_of(r["RSAChapter"] or t.get("RSAChapter"), r["ChapterLaw"] or t.get("ChapterLaw"))
        name = BC.committee_name(r["CommitteeName"])
        out.append({
            "cid": cid, "name": name, "kind": kind_of(name),
            "class": "study" if "study" in status.lower() else "statutory",
            "chamber": CHAMBER_OF_TYPE.get(r["CommitteeTypeID"].strip(), ""),
            "nonleg": bool(NON_LEGISLATIVE.search(r["CommitteeName"] or "")),
            "year": (r["CommitteeYear"] or t.get("CommitteeYear") or "").strip(),
            "bill": bill, "rsa": rsa, "law": law,
            "effective": day(r["EffectiveDate"]), "due": day(r["ReportDueDate"]),
            "filed": r["ReportFiled"].strip() == "True", "filed_on": day(r["ReportDate"]),
            "report": r["Report"], "first": r["FirstMeeting"], "quorum": r["Quorum"],
            "ends": r["TerminationDate"].strip(), "amended": r["AmendingBills"],
            "seats": [s for s in seats.get(cid, []) if s["Active"].strip() == "True"],
            "meetings": held.get(cid, [])})
    return sorted(out, key=lambda c: (c["name"].lower(), c["cid"]))


ROLE_RANK = {"Chair": 0, "": 1, "Non-voting": 2, "Alternate": 3}


def seat_role(s):
    return ("Chair" if s["Chairperson"].strip() == "True" else
            "Alternate" if s["Alternate"].strip() == "True" else
            "Non-voting" if s["NonVotingMember"].strip() == "True" else "")


def who_sits(c, legs, former, vocab, said=None):
    """(chips, described, left): the committee's sitting legislators as
    {"S": [...], "H": [...]}, each a roster entry with its role; every other
    active seat as the record describes it, alike seats as one line with how
    many hold it; and how many seats are held by members who have left the
    General Court, which are left off.

    A SEAT IS A LEGISLATOR'S BY ITS TYPE, 0 a representative's and 1 a
    senator's, and its member is the roster's by number: the database files
    a legislator's seat under the member's own number, which is
    site/legislators.json's id. A seat of another type is never looked up
    there -- its number is from another list, and sixteen of them collide
    with a legislator's. A legislator's seat whose member has left the
    General Court is not drawn: the seat says Active, the member no longer
    sits. One whose number is on neither list is described, as a public
    member's is."""
    chips, described, left = {}, OrderedDict(), 0
    for s in c["seats"]:
        no, typ, role = s["memberno"].strip(), s["MemberType"].strip(), seat_role(s)
        if typ in ("0", "1"):
            m = legs.get(no)
            if m:
                was = chips.get(no)
                if not was or ROLE_RANK[role] < ROLE_RANK[was[0]]:
                    chips[no] = (role, m)
                continue
            if no in former:
                left += 1
                continue
        words = seat_words(s["Organization"], vocab, said) or prose(s["Affiliation"], vocab)
        # One seat's description, however the copy spaced it this time.
        g = described.setdefault(re.sub(r"[^a-z0-9]", "", words.lower()),
                                 {"words": words, "n": 0, "aff": [], "chair": False})
        g["n"] += 1
        g["chair"] = g["chair"] or role == "Chair"
        aff = prose(s["Affiliation"], vocab)
        if aff and aff not in g["aff"] and aff.lower() not in words.lower():
            g["aff"].append(aff)
    by = {"S": [], "H": []}
    for no, (role, m) in chips.items():
        by["S" if m.get("chamber") == "S" else "H"].append(dict(m, role=role or "Member"))
    for ch in by:
        by[ch].sort(key=lambda m: (m["role"] != "Chair", str(m.get("sort") or m.get("name") or "")))
    return by, list(described.values()), left


MARK = re.compile(r"==\s*([A-Za-z ]+?)\s*==")
MARK_WORDS = (("CANCEL", "Cancelled"), ("CACEL", "Cancelled"), ("CAMCEL", "Cancelled"),
              ("POSTPONE", "Postponed"), ("RESCHEDULED TIME", "Time Change"),
              ("RESCHEDULE", "Rescheduled"), ("DATE CHANGE", "Rescheduled"),
              ("TIME AND ROOM", "Time and Room Change"), ("ROOM AND TIME", "Time and Room Change"),
              ("TIME CHANGE", "Time Change"), ("ROOM", "Room Change"), ("RM CHANGE", "Room Change"),
              ("LOCATION", "Room Change"), ("REVISED", "Revised"), ("AMENDED", "Amended"),
              ("SNOW", "Snow Date"), ("RECESS", "Recessed"), ("RECONVENE", "Continued"),
              ("CONTINUED", "Continued"))


def marks_of(webtext, location):
    """(chips, notes): the marks the record puts on a meeting -- ==CANCELLED==,
    ==REVISED==, ==ROOM CHANGE== -- each as the one word a chip says, and any
    other mark, "==OR IMMEDIATELY FOLLOWING JLFC==", as a note in its words."""
    chips, notes = [], []
    for m in MARK.findall(f"{webtext} {location}"):
        up = m.upper().strip()
        word = next((w for k, w in MARK_WORDS if k in up), "")
        if word:
            if word not in chips:
                chips.append(word)
        elif up not in ("REGULAR MEETING", "ORGANIZATIONAL MEETING"):
            note = " ".join(w if w in ("JLFC", "LBA") else w.lower() for w in up.split())
            note = note[:1].upper() + note[1:]
            if note not in notes:
                notes.append(note)
    return chips, notes


# A ROOM AS THE RECORD WROTE IT BEFORE 2016: "RM205,LOB -", "RMs306-308,LOB -
# Continued Meeting", "RM105-A, St House -". build_calendar.place reads a
# letter against a digit as two lines run together and gives no venue, which
# was right for none of these: 485 of the active committees' 3,567 meetings
# had no place until they were read as the room and building they are --
# "LOB Room 205", "LOB Rooms 306-308", "State House Room 105-A" -- with what
# follows the dash kept as the meeting's note. 191 still have none, measured
# on 18 October 2026: their lines really did run together, as place() says.
OLD_ROOM = re.compile(r"^RM(s?)\s*(\d+(?:-?[A-Z])?(?:\s*[-/]\s*\d+(?:-?[A-Z])?)?)\s*[,/]\s*"
                      r"(LOB|St(?:ate)?\.?\s*House|SH)\b\s*-?\s*(.*)$", re.I)


def old_room(room):
    """(venue, note) out of a room written the old way, or (room, "")."""
    m = OLD_ROOM.match((room or "").strip())
    if not m:
        return room, ""
    where = "LOB" if m.group(3).upper() == "LOB" else "State House"
    rooms = re.sub(r"\s+", "", m.group(2))
    many = m.group(1) or re.search(r"[-/]\d", rooms)
    return f"{where} Room{'s' if many else ''} {rooms}", m.group(4).strip(" -()")


def meetings_of(c, recent, today):
    """The committee's meetings, newest first, each {"date", "time", "venue",
    "type", "chips", "notes", "video", "id"}; a meeting the database holds
    twice is one. `recent` is {(CommitteeID, MeetingID): the Calendar's row},
    whose venue and recording are the Calendar's own reading of the meeting.

    ONE RECORDING, ONE MEETING (the Videos section's scout, 26 October 2026).
    `recent` was keyed by MeetingID alone, and a MeetingID repeats across
    committees and eras: the Cyanobacteria Mitigation Loan and Grant Fund
    Task Force's meeting of 23 October 2026 lent its room and its recording
    to the Nuclear Decommissioning Financing Committee's meeting of 14 June
    2002, a recording eighteen years before the channels began. A row is this
    meeting's only where it is this committee's and of this meeting's day."""
    out, seen = [], set()
    for r in c["meetings"]:
        try:
            when = datetime.datetime.strptime(r["MeetingDate"].strip(), "%m/%d/%Y %H:%M:%S")
        except ValueError:
            continue
        room, mtype = BC._where(r["MeetingLocation"])
        chips, notes = marks_of(r["webtext"], r["MeetingLocation"])
        cal = recent.get((c["cid"], r["MeetingID"].strip())) or {}
        if cal.get("date") != when.date().isoformat():
            cal = {}
        if cal:
            venue = cal["venue"]
        else:
            room, more = old_room(room)
            venue = BC.place(room)
            if more and more.lower() not in (n.lower() for n in notes) \
                    and more.lower() != mtype.lower():
                notes.append(more[:1].upper() + more[1:])
        m = {"date": when.date().isoformat(),
             "time": "" if when.time() == datetime.time(0) else when.strftime("%H:%M"),
             "venue": venue, "type": mtype, "chips": chips, "notes": notes,
             "video": cal.get("video_id") or ""}
        sig = (m["date"], m["time"], m["venue"], tuple(chips))
        if sig in seen:
            continue
        seen.add(sig)
        out.append(m)
    out.sort(key=lambda m: (m["date"], m["time"]), reverse=True)
    taken = Counter()
    for m in out:
        taken[m["date"]] += 1
        m["id"] = f"day-{m['date']}" + (f"-{taken[m['date']]}" if taken[m["date"]] > 1 else "")
    return out


# ---- the page --------------------------------------------------------------------

def plural(n, word, many=None):
    return f"{n:,} {word if n == 1 else (many or word + 's')}"


def bill_page(bid, year, bills, site):
    """HB621 of 2025's page on the site, "bill/2025/hb621.html", or "" where
    the site has none."""
    yr = bills.get((bid, str(year)))
    if yr and (Path(site) / "bill" / str(yr) / f"{bid.lower()}.html").exists():
        return f"bill/{yr}/{bid.lower()}.html"
    return ""


def bill_link(bid, year, bills, site):
    """HB 621 as a link to its page where the site has it, else as text."""
    num = re.sub(r"^([A-Z]+)(\d)", r"\1 \2", bid)
    href = bill_page(bid, year, bills, site)
    return f'<a href="{E(href)}">{E(num)}</a>' if href else E(num)


def bills_of(c, ctx):
    """THE BILLS TAB'S BILLS (the owner, 29 October 2026: a study committee's
    page has the tabs a standing committee's has, Bills | Meetings | Videos).
    A standing committee's Bills are the bills referred to it; nothing is
    referred to a study or statutory committee, and what the record does
    name are the bills that made it and changed it: the one that set it up
    (CondensedBillNo) and those it lists as amending it (AmendingBills,
    "HB1442(2026)"), each once -- 143 of the 151 active name
    the first (measured on the preview, 29 October 2026), and the Fiscal
    Committee, set up in 1965 by no bill the record names, four of the
    second. Each is {n, year, href, title, line}: its page and title where the
    site has the bill. A committee whose record names none has no Bills tab
    rather than an empty one.

    BY YEAR, AND NONE SAID TO COME "SINCE" (the review of 29 October 2026,
    5): the bills the record lists as amending a body can be older than the
    one that set it up -- the Advisory Council on Unemployment Compensation,
    set up by HB 317 of 1995, lists HB 746 of 1975 and HB 110 of 1981, and the
    tab had them as "Changed it", after it. The rows are in the order of
    their years, the bill that set it up first among its own year's, and a
    bill older than it -- or than the year a body set up by no bill named
    was set up -- says that, where the others say "Amended it"."""
    founded = c["year"] if str(c["year"] or "").isdigit() else ""
    older = ("Older than the bill that set it up" if c["bill"] else
             f"Older than {founded}, when it was set up")
    named = ([(c["bill"], c["year"], "Set it up")] if c["bill"] else []) + [
        (m.group(1).upper() + m.group(2), m.group(3),
         older if founded and m.group(3) < founded else "Amended it")
        for m in BILL_YEAR.finditer(c["amended"] or "")]
    out, seen = [], set()
    # The year this site's bills begin (1989, context): a bill before it has
    # no page and no title here, and says why rather than standing blank --
    # the Administrative Rules committee's HB 366 of 1983.
    first = ctx.get("first_year", "")
    for bid, year, role in named:
        if (bid, str(year)) in seen:
            continue
        seen.add((bid, str(year)))
        title = ctx["titles"].get((bid, str(year)), "")
        if not title and first and str(year) < first:
            title = f"Before {first}, when this site’s record of bills begins."
        out.append({"n": re.sub(r"^([A-Z]+)(\d)", r"\1 \2", bid), "year": str(year),
                    "href": bill_page(bid, year, ctx["bills"], ctx["site"]), "title": title, "line": role})
    return sorted(out, key=lambda r: (r["year"], r["line"] != "Set it up"))


def bills_html(c, rows):
    """The Bills tab: what the list is, then a row a bill (components.bill_row),
    its number as text where the site has no page for it."""
    made = sum(r["line"] == "Set it up" for r in rows)
    others = len(rows) - made
    # What the record says of them and no more: it lists them as amending
    # the body, in years that can come before the bill that set it up
    # (bills_of), so nothing here says "since".
    listed = (("the bill" if others == 1 else f"the {others:,} bills")
              + " the General Court&rsquo;s record lists as amending it"
              + (", by year" if len(rows) > 1 else ""))
    lead = (f"The bill that set it up, and {listed}." if made and others else
            "The bill that set it up, as the General Court&rsquo;s record names it." if made else
            listed[:1].upper() + listed[1:] + "."
            + (f" It was set up in {E(c['year'])}." if c["year"] else ""))
    out = [f'<p class="src">{lead}</p><div class="ssbills">']
    for r in rows:
        if r["href"]:
            out.append(C.bill_row(r))
        else:
            # A bill the site has no page for (A WRONG LINK IS WORSE THAN NO
            # LINK): its number and year as words.
            out.append(f'<div class="brow"><span class="brnum">{E(r["n"])}<span class="byr">'
                       f'({E(r["year"])})</span></span><span class="brtitle">{E(r["title"])}</span>'
                       f'<span class="brline">{E(r["line"])}</span></div>')
    return "".join(out) + "</div>"


def what_it_does(c, ctx):
    """The law that made it and governs it, and the rules it meets by."""
    out = []
    when = f" of {E(c['year'])}" if c["year"] else ""
    law = (f", chapter {E(c['law'])} of the Laws of {E(c['year'])}"
           if c["law"] and c["year"] else "")
    # The effective date only where it is the act's: the Fiscal Committee of
    # 1965 carries 21 March 2000, a later re-enactment's or the clerk's entry.
    eff = (f", in effect from {E(C.date_words(c['effective'], 'full'))}"
           if c["effective"] and c["year"].isdigit()
           and 0 <= c["effective"].year - int(c["year"]) <= 1 else "")
    if c["bill"]:
        out.append(f"<p>Set up by {bill_link(c['bill'], c['year'], ctx['bills'], ctx['site'])}"
                   f"{when}{law}{eff}.</p>")
    elif c["year"]:
        out.append(f"<p>Set up in {E(c['year'])}{law}{eff}.</p>")
    st = statute(c["rsa"], ctx["headings"], ctx["chapters"])
    if st:
        ctx["statutes"] += bool(st["href"])
        name = f"RSA {E(st['addr'])}"
        out.append("<p>The statute it sits in: "
                   + (f'<a href="{E(st["href"])}">{name}</a>' if st["href"] else name)
                   + (f", {E(st['heading'].rstrip('.'))}" if st["heading"] else "")
                   + ".</p>")
    # By year, and not "since": the record's amending bills can be older
    # than the one that set the body up (bills_of; the review of 29 October
    # 2026, 5), where this said "Changed since by HB 746 (1975)" of a council
    # set up in 1995.
    amended = [bill_link(b.upper(), y, ctx["bills"], ctx["site"]) + f" ({E(y)})"
               for b, y in sorted(((m.group(1) + m.group(2), m.group(3))
                                   for m in BILL_YEAR.finditer(c["amended"] or "")), key=lambda x: x[1])]
    if amended:
        out.append(f"<p>The General Court&rsquo;s record lists it as amended by {', '.join(amended)}.</p>")
    rules = [(w, prose(c[k], ctx["vocab"], ctx["parted"]))
             for w, k in (("First Meeting", "first"), ("Quorum", "quorum"), ("Ends", "ends"))]
    rules = [(w, t) for w, t in rules if t]
    if rules:
        out.append('<dl class="ssrules">' + "".join(
            f"<div><dt>{E(w)}</dt><dd>{E(t)}</dd></div>" for w, t in rules) + "</dl>")
    return "".join(out)


def report(c, ctx, today):
    """What it must report, when, and whether the record shows one filed."""
    out = []
    duty = prose(c["report"], ctx["vocab"], ctx["parted"])
    if duty:
        out.append(f'<p class="ssduty">{E(duty)}</p>')
    facts = []
    if c["due"]:
        facts.append(("Due" if c["due"] >= today else "Was Due",
                      C.date_words(c["due"], "full")))
    if c["filed"]:
        facts.append(("Filed", ("A report is on file, dated "
                                + C.date_words(c["filed_on"], "full")) if c["filed_on"]
                      else "A report is on file"))
    elif duty or c["due"]:
        facts.append(("Filed", "No report is on file"))
    if facts:
        out.append('<dl class="ssrules">' + "".join(
            f"<div><dt>{E(w)}</dt><dd>{E(t)}.</dd></div>" for w, t in facts) + "</dl>")
    return "".join(out)


def members_html(c, by, described):
    out = []
    for ch, word in (("S", "Senators"), ("H", "Representatives")):
        if by[ch]:
            out.append(f'<h3 class="ssh">{word} <span class="w4n">{len(by[ch])}</span></h3>'
                       '<ul class="sschips">'
                       + "".join(f"<li>{C.pchip(m)}</li>" for m in by[ch]) + "</ul>")
    if described:
        out.append(f'<h3 class="ssh">Other Members <span class="w4n">'
                   f'{sum(g["n"] for g in described)}</span></h3><ul class="ssseats">'
                   + "".join(
                       f'<li><span class="ssdesc">{E(g["words"])}</span>'
                       f'<span class="ssmeta">{plural(g["n"], "seat")} on record'
                       + (f" &middot; {E(', '.join(g['aff']))}" if g["aff"] and len(g["aff"]) <= 3 else "")
                       + "</span>" + (C.chip("Chair") if g["chair"] else "") + "</li>"
                       for g in described) + "</ul>"
                   '<p class="src">The General Court&rsquo;s database names the legislators who '
                   "sit on it; the other members&rsquo; names are on its own page for the "
                   "committee, and are not here yet.</p>")
    if not out:
        out.append('<p class="src">The General Court&rsquo;s record lists no one on it today.</p>')
    return "".join(out)


def player(c, m):
    """The meeting's recording, still until pressed, as a session day's is
    (build_full_sessions.day_players): app.js's one handler plays it."""
    pid = f"ss{c['cid']}_{m['date'].replace('-', '')}_{re.sub(r'[^\w-]', '', m['video'])}"
    title = f"Recording of {named(c['name'])}, {C.date_words(m['date'])}"
    return (f'<div class="player" data-player="{E(pid)}">'
            f'<button type="button" class="pstub" data-title="{E(title)}" '
            f'data-embed="{E(m["video"])}|0|{E(pid)}"><span>{C.icon("play")}</span>'
            "<span>Play the recording</span></button>"
            f'<div class="pbar"><span class="pwho"><b>{E(c["name"])}</b> &middot; '
            f'{E(C.date_words(m["date"]))}</span>'
            f'<a href="https://www.youtube.com/watch?v={E(m["video"])}" target="_blank" '
            'rel="noopener">On YouTube</a></div></div>')


def meeting_html(c, m, today):
    """One meeting, folded as a committee's meeting is (.cmeet): the day and
    the time, the place and the kind of meeting, the record's marks; open,
    its recording, and the way to it on the Calendar."""
    # The room in the words the Calendar says this same meeting in
    # (plain_action.place): ss166's "SL Room Map Room" is "State Library Map
    # Room" (the person, 26 October 2026: "SL is the state library map
    # room"), and "LOB Room 102" is "Legislative Office Building 102".
    said = " &middot; ".join(E(x) for x in (PA.place(m["venue"]), m["type"]) + tuple(m["notes"]) if x)
    chips = "".join(C.chip(w, "calkind") for w in m["chips"])
    if m["video"]:
        chips += C.chip("Recorded")
    body = (f'<div class="cmplay">{player(c, m)}</div>' if m["video"] else
            '<p class="note">Still to come.</p>' if m["date"] > today.isoformat() else
            '<p class="note">No recording of this meeting is on file.</p>')
    if m["date"] >= BC.FROM:
        week = BC.week_key(datetime.date.fromisoformat(m["date"]))
        body += (f'<p class="src"><a href="calendar.html?week={week}&amp;day={m["date"]}'
                 f'&amp;committee={E(quote_plus(c["name"]))}">This meeting on the Calendar</a></p>')
    return (f'<details class="cmeet" id="{E(m["id"])}" data-date="{E(m["date"])}">'
            '<summary><span class="calmix" aria-hidden="true"><i class="k-study"></i></span>'
            f'<span class="cmwhen"><b>{E(C.date_words(m["date"], "long"))}</b>'
            + (f'<span class="cmtime">{E(C.clock(m["time"]))}</span>' if m["time"] else "")
            + "</span>"
            + (f'<span class="cmcount">{said}</span>' if said else "")
            + (f'<span class="cmkinds">{chips}</span>' if chips else "")
            + '<span class="cmcaret" aria-hidden="true"></span></summary>'
            f'<div class="cmbody">{body}</div></details>')


def meetings_html(c, ms, today):
    if not ms:
        return ('<p class="src">No meeting of it is in the General Court&rsquo;s record, '
                "which holds the study and statutory committees&rsquo; meetings of "
                "1991 to 2015 and from 2024 on.</p>")
    cut = str(today.year - RECENT_YEARS + 1)
    now = [m for m in ms if m["date"][:4] >= cut]
    old = [m for m in ms if m["date"][:4] < cut]
    gap = any(m["date"][:4] <= "2015" for m in ms) and any(m["date"][:4] >= "2024" for m in ms)
    out = [f'<p class="src">{plural(len(ms), "meeting")} on record, newest first.'
           + (" The General Court&rsquo;s record holds none of any study or statutory "
              "committee from 2016 to 2023." if gap else "") + "</p>"]
    if now:
        out.append('<div class="cmeets">' + "".join(meeting_html(c, m, today) for m in now)
                   + "</div>")
    else:
        out.append(f'<p class="note">None since {cut}.</p>')
    if old:
        span = old[-1]["date"][:4] + (f" to {old[0]['date'][:4]}" if old[0]["date"][:4] != old[-1]["date"][:4] else "")
        out.append('<details class="sfold ssold" id="earlier"><summary>'
                   f'<span class="sflab">Earlier meetings, {span}</span>'
                   f'<span class="w4n">{len(old):,}</span>'
                   '<span class="cmcaret" aria-hidden="true"></span></summary>'
                   '<div class="cmeets">' + "".join(meeting_html(c, m, today) for m in old)
                   + "</div></details>")
    return "".join(out)


def videos_html(c, ms, ctx):
    """THE VIDEOS TAB (the owner, 26 October 2026: "Same goes for ... study
    committees, commissions, etc that are livestreamed"): the committee's
    recorded meetings as one player and its playlist, newest first, drawn by
    app.js's videoView -- the renderer a committee's Videos tab and a
    chamber's use -- from the rows this writes into the page, so no file is
    added. Each row is a meeting this page lists with the recording the
    Calendar matched to it (meetings_of): its day, the time it was set for,
    its room and kind of meeting, the fold it opens (anchor) and its day on
    the Calendar; and when the recording began and how long it ran, where the
    index says. ("", 0) where no meeting has a recording: no tab; else (the
    tab's body, how many recordings). Without script the tab's pane says
    each recorded meeting under Meetings has its player, which it does."""
    rows, seen = [], set()
    for m in ms:
        f = ctx["facts"].get(m["video"]) or {}
        # A stream the index has as still to come (no start, no length) is
        # not listed until it has run.
        if not m["video"] or m["video"] in seen or (f and not f.get("streamed")):
            continue
        seen.add(m["video"])
        rows.append({"id": m["video"], "date": m["date"], "time": m["time"],
                     "venue": PA.place(m["venue"]), "type": m["type"], "anchor": m["id"],
                     **({"calendar": f"calendar?week={BC.week_key(datetime.date.fromisoformat(m['date']))}"
                                     f"&day={m['date']}&committee={quote_plus(c['name'])}"}
                        if m["date"] >= BC.FROM else {}),
                     **({"began": f["began"]} if f.get("began") else {}),
                     **({"seconds": f["seconds"]} if f.get("seconds") else {})})
    if not rows:
        return "", 0
    data = json.dumps({"kind": "study", "who": c["name"], "what": named(c["name"]), "key": c["cid"],
                       "path": page_path(c), "rows": rows},
                      separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    return ('<div class="vwhere" data-vwview="gr-videos"><p class="src">Each recorded meeting under '
            "Meetings has its own player.</p></div>"
            f'<script type="application/json" id="gr-videos">{data}</script>'), len(rows)


def page_path(c):
    """"/committee/ss1451", the page's address, which its tabs' extend."""
    return "/" + BC.study_page(c["cid"]).removesuffix(".html")


def tab_n(n):
    """A tab's count as app.js's tabN draws it: the badge, its brackets
    there for a screen reader."""
    return f'<span class="tn"><span class="tnp"> (</span>{n:,}<span class="tnp">)</span></span>' if n else ""


# THE TABS (the owner, 29 October 2026, reversing the full-width Videos
# section: "study committees, commissions and boards get the same tab format
# as standing committees: Bills | Meetings | Videos"). A standing committee's
# strip in its own words and classes (app.js's tabStrip, .rhead ~ .tabs: on
# the head's foot rule and staying at the top of the window as a pane
# scrolls), each tab with its count, a pane each in the record's white sheet;
# what it does, its report and who sits on it stay above the strip, as a
# standing committee keeps its members and its rule. Each tab is (pane id,
# its name, the slug of its address, its count, its body); its address is
# the page's own for the one it lands on (landing), else
# /committee/ss<id>/<slug>, which the committee rewrite serves
# (build_pages.COMMITTEE_TAB_SLUGS) -- so a tab to
# come, Reports, is a pane, a name and a slug. A tab with nothing in it is
# not drawn: no Bills where the record names none, no Videos where no
# meeting was recorded.
#
# WRITTEN WHOLE, SHOWN BY SCRIPT: the strip is hidden without JavaScript and
# every pane is on the page in turn under its own heading; with it (html.js,
# set before the first paint) the pane the page lands on alone is shown from
# the first paint, and app.js (ssTabs) turns to the one the address names and
# to the one pressed.
#
# IT LANDS ON MEETINGS (the review of 29 October 2026, 4): opened on Bills,
# the first tab, the State Commission on Aging showed one row, HB 621 of 2019,
# which What It Does names just above it, and the Fiscal Committee four
# housekeeping bills with its 165 meetings a click away -- and 143 of the 151
# bodies name a founding bill, so nearly every page opened so. Nothing is
# referred to a study or statutory committee: what a reader comes for is
# when it meets and what it did. The strip keeps the owner's order; the tab
# landed on is at the page's own address and every other at its slug
# (/committee/ss57/bills, which the committee rewrite serves). A body that has
# never met lands on the first tab with something in it.
TABS = (("bills", "Bills", "bills"), ("meetings", "Meetings", "sessions"), ("videos", "Videos", "videos"))
LANDS_ON = "meetings"


def landing(bodies):
    """The pane a study committee's page opens on, from {pane id: (count,
    body)}: its meetings where it has met, else the first tab with something
    in it, else the first."""
    if bodies.get(LANDS_ON, (0, ""))[0]:
        return LANDS_ON
    have = [pid for pid, _w, _s in TABS if pid in bodies]
    return next((pid for pid in have if bodies[pid][0]), have[0])


def tabs_html(c, bodies):
    """The strip and its panes, from {pane id: (count, body)}, the ones there
    are, in TABS' order; the one it lands on (landing) chosen and shown, at
    the page's own address."""
    land = landing(bodies)
    panes = [(pid, word, "" if pid == land else slug, *bodies[pid]) for pid, word, slug in TABS if pid in bodies]
    strip = (f'<div class="tabs sstabs" role="tablist" data-base="{E(page_path(c))}">'
             + "".join(f'<button type="button" class="tab" role="tab" id="sstab-{pid}" aria-controls="{pid}" '
                       f'data-sstab="{slug}" aria-selected="{"true" if pid == land else "false"}">{E(word)}{tab_n(n)}'
                       "</button>" for pid, word, slug, n, _b in panes)
             + "</div>")
    return strip + "".join(
        f'<div class="pane sspane" role="tabpanel" id="{pid}" aria-labelledby="sstab-{pid}" tabindex="0"'
        f'{" data-on" if pid == land else ""}><h2 class="ssph">{E(word)}</h2>{body}</div>'
        for pid, word, _s, _n, body in panes)


def facts_of(c, by, described, ms, ctx, today):
    nleg = len(by["S"]) + len(by["H"])
    nother = sum(g["n"] for g in described)
    facts = [["Class", E(CLASS_WORD[c["class"]]),
              f"filed under the {CHAMBER_WORD[c['chamber']]}" if c["chamber"] else ""]]
    if c["year"]:
        facts.append(["Set Up", E(c["year"]),
                      f"by {bill_link(c['bill'], c['year'], ctx['bills'], ctx['site'])}"
                      if c["bill"] else ""])
    if nleg or nother:
        facts.append(["Members", plural(nleg, "legislator") if nleg else plural(nother, "member"),
                      f"and {plural(nother, 'other seat')}" if nleg and nother else ""])
    if ms:
        # The latest it held: not one still to come, nor one cancelled.
        held = [m["date"] for m in ms
                if m["date"] <= today.isoformat() and "Cancelled" not in m["chips"]]
        facts.append(["Meetings", f"{len(ms):,} on record",
                      f"the latest {E(C.date_words(held[0]))}" if held else ""])
    if c["due"]:
        facts.append(["Report Due" if c["due"] >= today else "Report Was Due",
                      E(C.date_words(c["due"]))])
    return facts


def page_body(c, ctx, today, path):
    """The committee's page: its head; What It Does, Report and Members, each
    a W4 section as a record's are; then its tabs, Bills, Meetings and
    Videos, as a standing committee's (TABS). A meeting the address names
    (#day-<date>, as a Calendar card leads here) is opened on the Meetings
    tab by app.js (ssTabs), which shows the tab first."""
    by, described, left = who_sits(c, ctx["legs"], ctx["former"], ctx["vocab"], ctx["parted"])
    ctx["chips"] += len(by["S"]) + len(by["H"])
    ctx["left"] += left
    ms = meetings_of(c, ctx["recent"], today)
    ctx["meetings"] += len(ms)
    ctx["recorded"] += sum(1 for m in ms if m["video"])
    held = [m["date"] for m in ms if m["date"] <= today.isoformat() and "Cancelled" not in m["chips"]]
    # The committee in a line, for /committees and the search (index_row).
    c["row"] = {"cid": c["cid"], "name": c["name"], "kind": c["kind"], "class": c["class"],
                "chamber": c["chamber"], "year": c["year"], "bill": c["bill"],
                "legislators": len(by["S"]) + len(by["H"]),
                "seats": len(by["S"]) + len(by["H"]) + sum(g["n"] for g in described),
                "meetings": len(ms), "last": held[0] if held else "",
                "chair": next((m.get("display_full") or m.get("name") or ""
                               for ch in ("S", "H") for m in by[ch] if m["role"] == "Chair"), ""),
                "nonleg": c["nonleg"], "page": "/" + BC.study_page(c["cid"])}
    line = (f"A {E(c['kind'].lower())} the General Court lists among its "
            f"{'study' if c['class'] == 'study' else 'statutory'} committees.")
    # DESCRIBED AS WHAT IT IS (the person's answer of 17 October 2026): a body
    # the list marks non-legislative is on it, and says so, in the list's own
    # terms rather than a branch of government this record does not name.
    if c["nonleg"]:
        line += (" The list marks it non-legislative: no seat on it is a "
                 "legislator&rsquo;s.")
    elif not (by["S"] or by["H"]) and c["seats"]:
        line += " No legislator holds a seat on it on the record."
    cite = S.cite_block(path, f"{c['name']} | Granite Record", ctx["base"], S.BUILT)
    assert cite.endswith("</div>"), "the citation block no longer ends its row"
    head = C.record_head({
        "trail": [["Committees", "committees.html#statstud"], [CLASS_WORD[c["class"]], ""]],
        "title": E(c["name"]), "chip": C.chip(c["kind"], "k-study", "m"), "line": line,
        "facts": facts_of(c, by, described, ms, ctx, today),
        "actions": cite[:-len("</div>")] + FS.SHARE + "</div>",
        "kind": "committee cmtehead sshead"})
    parts = [C.section("What It Does", what_it_does(c, ctx), "does")]
    rep = report(c, ctx, today)
    if rep:
        parts.append(C.section("Report", rep, "report"))
    parts.append(C.section("Members", members_html(c, by, described), "members"))
    tabs = {"meetings": (len(ms), meetings_html(c, ms, today))}
    bills = bills_of(c, ctx)
    if bills:
        tabs["bills"] = (len(bills), bills_html(c, bills))
        ctx["billtabs"] += 1
    vids, n = videos_html(c, ms, ctx)
    if vids:
        tabs["videos"] = (n, vids)
        ctx["videos"] += 1
    return head + '<div class="w4s ssbody">' + "".join(parts) + "</div>" + tabs_html(c, tabs)


def write_page(c, ctx, today):
    """site/committee/ss<CommitteeID>.html; returns its address for the sitemap."""
    site = ctx["site"]
    path = "/" + BC.study_page(c["cid"])
    word = CLASS_WORD[c["class"]].lower()
    desc = S.clip(f"The {c['name']}, a {c['kind'].lower()} on the New Hampshire General "
                  f"Court's list of {word.replace('committee', 'committees')}: what it does, "
                  "who sits on it, its reports and its meetings.", S.DESC_ROOM)
    html = S.page(S.template(site), path=path, base=ctx["base"],
                  title=f"{S.clip(c['name'], S.TITLE_ROOM)} | Granite Record",
                  og_title=c["name"], og_image="og-committee.png",
                  og_alt="Granite Record: committees and hearings", description=desc,
                  globals={"GR_STATIC": True},
                  jsonld=LD.study_committee(c["name"], ctx["base"], S.canon(path),
                                            legislative=not c["nonleg"]),
                  noscript="", skip_label="Skip to this committee",
                  nav_current="committees.html", sr_title="", cite=False)
    assert '<div id="results"></div>' in html, f"{path}: the template has no results slot"
    html = html.replace('<div id="results"></div>',
                        f'<div id="results">{page_body(c, ctx, today, path)}</div>', 1)
    out = Path(site) / BC.study_page(c["cid"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(S.clean_links(html), encoding="utf-8")
    return ctx["base"] + S.canon(path)


# ---- the Committees page's section ---------------------------------------------
#
# FOLDED, UNDER THE CHAMBERS' OWN (the person, 17 October 2026: "they should
# be included on the committee page ... but not as prominently as standing
# committees ... Maybe on the committee page they're under a drop-down menu
# of some kind"). One fold, "Statutory and study committees" with how many,
# that opens on the General Court's two classes, each committee a card as a
# standing one is, its kind from its name the card's chip; and a box that
# finds one by name, which the script shows -- without it the fold still
# opens on every card. build_committees writes the slot (STUDY_SLOT) and this
# fills it between its marks, so a second run redraws rather than doubles it.
SLOT = re.compile(r"<!-- statstud -->.*?<!-- /statstud -->", re.S)
GROUP_WORD = {"statutory": "Statutory Committees", "study": "Study Committees"}


def card(r):
    """One committee on /committees, as build_committees.committee_card draws
    a standing one: its name, then its kind and what the record holds."""
    bits = []
    if r["legislators"]:
        bits.append(plural(r["legislators"], "legislator"))
    elif r["seats"]:
        bits.append(plural(r["seats"], "member"))
    if r["year"]:
        bits.append(f"set up in {E(r['year'])}")
    if r["last"]:
        bits.append(f"last met {E(C.date_words(r['last']))}")
    said = " &middot; ".join(bits)
    find = " ".join([r["name"], r["kind"], CLASS_WORD[r["class"]]]).lower()
    return (f'<a class="ccard sscard" href="{E(BC.study_page(r["cid"]))}" '
            f'data-find="{E(re.sub(r"[^a-z0-9 ]+", " ", find))}">'
            f'<span class="cc-n">{E(r["name"])}</span>'
            f'<span class="cc-m">{C.chip(r["kind"], "k-study")} {said[:1].upper()}{said[1:]}'
            "</span></a>")


def section_html(rows):
    """The folded section of /committees, its two classes in that order."""
    groups = []
    for cls in ("statutory", "study"):
        mine = sorted((r for r in rows if r["class"] == cls), key=lambda r: r["name"].lower())
        if mine:
            groups.append(f'<section class="ssgrp" data-class="{cls}"><h3 class="ssgh">'
                          f'{GROUP_WORD[cls]} <span class="w4n">{len(mine)}</span></h3>'
                          '<div class="ccards sscards">' + "".join(card(r) for r in mine)
                          + "</div></section>")
    return ('<details class="sfold ssfold" id="statstud"><summary><h2 class="ssfh">'
            '<span class="sflab">Statutory and study committees</span> '
            f'<span class="w4n">{len(rows)}</span></h2>'
            '<span class="cmcaret" aria-hidden="true"></span></summary>'
            '<p class="src fill">Commissions, councils, boards and committees the law sets up, '
            "many with legislators and members of the public on them. The General Court lists "
            "each as statutory, set up in the statutes, or as a study committee, set up for a "
            "time by a session law.</p>"
            '<div class="ssfind" hidden><label for="ssq">Find one by name</label>'
            '<input type="search" id="ssq" autocomplete="off" placeholder="Aging, or Fiscal">'
            '<p class="ssfn" id="ssfn" role="status" aria-live="polite"></p></div>'
            + "".join(groups)
            + '<p class="note ssnone" id="ssnone" hidden>None of them has that in its name.</p>'
            "</details>" + FIND_JS)


# The find box: every card whose name, kind or class holds each word typed,
# and a class with none of them out of the way. No page without it hides a
# card, and the box is hidden until this shows it.
FIND_JS = """<script>
(function(){
  var box=document.getElementById("statstud");
  if(!box)return;
  var wrap=box.querySelector(".ssfind"),q=document.getElementById("ssq"),
      said=document.getElementById("ssfn"),none=document.getElementById("ssnone"),
      cards=[].slice.call(box.querySelectorAll(".sscard")),
      groups=[].slice.call(box.querySelectorAll(".ssgrp"));
  wrap.hidden=false;
  function words(s){return String(s||"").toLowerCase().replace(/[^a-z0-9 ]+/g," ").split(" ").filter(Boolean);}
  function run(){
    var w=words(q.value),n=0;
    cards.forEach(function(c){
      var hay=" "+c.getAttribute("data-find")+" ";
      var ok=w.every(function(x){return hay.indexOf(" "+x)>=0;});
      c.hidden=!ok;n+=ok?1:0;
    });
    groups.forEach(function(g){g.hidden=!g.querySelector(".sscard:not([hidden])");});
    none.hidden=!!n;
    said.textContent=w.length?(n===1?"1 committee matches.":n+" committees match."):"";
  }
  q.addEventListener("input",run);
  // Opened by an address that names it, as a committee's page leads here.
  function opened(){if(location.hash==="#statstud")box.open=true;}
  opened();
  window.addEventListener("hashchange",opened);
})();
</script>"""


def fill_section(site, rows):
    """Put the section in /committees' slot; False where the page or the slot
    is not there, which the run says."""
    page = Path(site) / "committees.html"
    if not page.exists():
        return False
    text = page.read_text(encoding="utf-8")
    if not SLOT.search(text):
        return False
    html = SLOT.sub(lambda _m: "<!-- statstud -->" + section_html(rows) + "<!-- /statstud -->",
                    text, count=1)
    page.write_text(S.clean_links(html), encoding="utf-8")
    return True


def load_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def context(site, base, today):
    """What every page reads, read once."""
    site = Path(site)
    legs = {str(m.get("id")): m for m in load_json(site / "legislators.json", []) or []}
    former = {str(m.get("id")) for m in load_json(site / "former.json", []) or []}
    bills, titles = {}, {}
    for b in SR.bill_index(site) or []:
        bid = str(b.get("id") or "").upper()
        bills.setdefault((bid, str(b.get("year") or "")), b.get("year"))
        titles.setdefault((bid, str(b.get("year") or "")), str(b.get("title") or ""))
        # A bill is filed in one year of its term and named by either.
        for y in re.findall(r"\d{4}", str(b.get("term") or "")):
            bills.setdefault((bid, y), b.get("year"))
            titles.setdefault((bid, y), str(b.get("title") or ""))
    headings = {str(s): h for s, h in (load_json(site / "laws" / "headings.json", []) or [])}
    chapters = load_json(site / "laws" / "chapters.json", {}) or {}
    known = {w.lower() for h in headings.values() for w in re.findall(r"[A-Za-z]+", str(h))}
    # THE CALENDAR'S OWN READING OF EVERY MEETING SINCE ITS FIRST WEEK: the
    # venue where the copy's ran together, and the recording, matched by
    # name and date (build_calendar.study_recordings), so a meeting's card
    # and its page play the same recording or none.
    # Its own account of the copy is the Calendar's to print.
    with contextlib.redirect_stdout(io.StringIO()):
        rows, _names, _fetched = BC.statstud()
    if rows:
        on_bills = {(r.get("video_id") or "").strip() for r in proceedings.load()} - {""}
        BC.study_recordings(rows, BC.recordings_by_day(), on_bills, today.isoformat())
    # By committee and meeting: a MeetingID alone repeats (meetings_of).
    recent = {(r.get("cid") or "", r["mid"]): r for r in rows if r.get("mid")}
    return {"site": site, "base": base, "legs": legs, "former": former, "bills": bills,
            # Each bill's title, and the year the site's bills begin, for the
            # Bills tab (bills_of).
            "titles": titles, "first_year": min((y for _b, y in bills if y), default=""),
            "headings": headings, "chapters": chapters, "recent": recent,
            # When each recording began and how long it ran, for the Videos
            # tab (videos_html).
            "facts": proceedings.video_facts() if rows else {},
            "vocab": Words(known), "parted": Counter(), "statutes": 0, "chips": 0,
            "left": 0, "meetings": 0, "recorded": 0, "videos": 0, "billtabs": 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    # The database copy where the Calendar reads it (build_calendar.STATSTUD_DIR).
    site, base, db = Path(a.site), a.base.rstrip("/"), BC.STATSTUD_DIR
    today = build_date.today()
    ctx = context(site, base, today)
    comms = read(db, ctx["vocab"])
    # SILENCE IS NOT SUCCESS: no copy, or a copy with no active committee,
    # is a run that would write nothing and say it had built the pages.
    if comms is None:
        print(f"  FAILED: {db}/StatStudDetails.psv is not on disk, so no statutory or study "
              "committee has a page")
        return 1
    if not comms:
        print(f"  FAILED: {db}/StatStudDetails.psv lists no active committee: the copy is "
              "empty or its CommitteeStatus is no longer read")
        return 1
    urls = [write_page(c, ctx, today) for c in comms]
    assert len(urls) == len(comms) == len({u for u in urls}), "a committee's page was not written once"
    # THE LIST OF THEM, a line each, for the readers after this step: the
    # Committees page's section and the search (build_indexes.find_index).
    (site / INDEX).write_text(json.dumps([c["row"] for c in comms], ensure_ascii=False,
                                         separators=(",", ":")), encoding="utf-8")
    # SILENCE IS NOT SUCCESS: pages that nothing on /committees leads to are
    # the "built, sitemapped and unreachable" build_committees once was.
    if not fill_section(site, [c["row"] for c in comms]):
        print(f"  FAILED: {site}/committees.html has no statutory and study committees slot "
              "(build_committees writes it): their pages would be reachable from no list")
        return 1
    # Writers merge: /committee/ss* is this step's, every other /committee
    # address build_committees'.
    added, dropped = S.sitemap_merge(site, base, urls, "/committee/ss*")
    n = Counter(c["class"] for c in comms)
    print(f"  {len(urls)} statutory and study committee pages -> {site}/committee/ss*.html "
          f"({n['statutory']} statutory, {n['study']} study)"
          + (f"; sitemap: {added} added, {dropped} taken out" if added or dropped else ""))
    print(f"  {ctx['chips']:,} legislators' seats drawn as their chips; {ctx['left']:,} seats of "
          "members who have left the General Court left off")
    print(f"  {ctx['meetings']:,} meetings, {ctx['recorded']:,} with their recording, on "
          f"{ctx['videos']} pages with a Videos tab; {ctx['billtabs']} pages with a Bills tab, the "
          f"bills that set them up or changed them; "
          f"{ctx['statutes']} committees' statutes linked to their Laws page")
    if ctx["parted"]:
        print(f"  {sum(ctx['parted'].values())} words the copy ran together parted, the "
              "commonest: " + ", ".join(w for w, _n in ctx["parted"].most_common(5)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
