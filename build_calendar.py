#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.11
"""
The General Court's week, one page per week.

    python3 build_calendar.py --site site --base https://graniterecord.org

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

A CALENDAR ON TOP OF THE WEEKS (24 September 2026). The person asked for the
General Court's schedule done properly: a month down the left with the week
and the day marked, List, Week and Day views of the day chosen, a preview on
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
session after it has had one working day. The card carries a chip per kind and
a divided colour bar, and its body lists the day's items in order with the time
and room each was set for.

STUDY AND STATUTORY COMMITTEES. proceedings.csv is keyed on bills, so on its
own this showed bill business only, while the General Court's schedule also
lists the study commissions, boards and statutory committees that sit with no
bill before them -- seven of them in the week of 21 September 2026, against
two sittings shown. They come from the database copy in db/
(StatStudMeetings.psv, with StatStudDetails.psv for each committee's name and
whether it is a study or a statutory one), drawn as their own cards in the
meeting colour, and a reader can hide them with a toggle. NOTHING REFRESHES
THAT COPY YET -- it is a fetch_*_db.py run, which is the person's to start --
so the page states the date it was taken.
"""

import argparse
import datetime
import json
import re
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

import build_pages as BP
import proceedings
import shell as S
import structured as LD

# From 2025: the current term and the one before it. Everything earlier is in
# the record and reachable through a bill or a committee, but nobody pages a
# calendar back to 1998 and sixty-odd files is enough to carry the arrows.
FROM = "2025-01-01"

DAYNAME = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()
MONTH = ("January February March April May June July August September "
         "October November December").split()

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
CONFERENCE = "Committee of conference"


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
_ACRONYM = {"NH": "NH", "RSA": "RSA", "OHRVS": "OHRVs", "SAUS": "SAUs",
            "SIEC": "SIEC", "IDD": "IDD", "ABD": "ABD"}


def committee_name(caps):
    """COMMITTEE ON LEGISLATOR ORIENTATION -> Committee on Legislator Orientation."""
    words = (caps or "").strip().rstrip(".").split()
    out = []
    for i, w in enumerate(words):
        parts = []
        for p in w.split("-"):
            core = p.strip("(),")
            if core.upper() in _ACRONYM:
                parts.append(p.replace(core, _ACRONYM[core.upper()]))
            elif i and p.lower() in _SMALL:
                parts.append(p.lower())
            else:
                parts.append(re.sub(r"[A-Za-z]", lambda m: m.group(0).upper(),
                                    p.lower(), count=1))
        out.append("-".join(parts))
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


def statstud(root=Path(".")):
    """(rows, names, fetched): the study and statutory committee meetings
    from FROM on, shaped as weeks_from reads rows; {bill: [(year, name)]}
    for the committees a bill set up; and the date the copy was taken.

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
        det[f[0].strip()] = (name, kind, bill, f[1].strip())
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
        name, kind, bill, year = c
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
                     "study": True, "note": note})
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
# a preview of a day's meetings when the pointer rests on it; and filters of
# who is meeting and what kind of sitting it is, which combine.
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
# puts them on the page. The whole-line comments stay in this file and are
# left off the copy each page carries (lean_js).
WEEK_JS = r"""
(function(){
  "use strict";
  var G=typeof window!=="undefined"?window:globalThis;

  // ==== THE CORE, which touches no page ======================================
  //
  // Dates, the cards' own fields, the filters, the count and the markup of the
  // grid and the preview are plain functions over plain values, so preflight
  // runs them in node against the cards a build actually wrote. The part that
  // touches the page is below them and does no reasoning of its own.
  //
  // Dates are ISO strings, "2026-09-23", and all arithmetic is in UTC: a day
  // is a date, not a moment, and a reader's time zone must not move one.
  var DAYNAME=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"];
  var MONTH=["January","February","March","April","May","June","July",
             "August","September","October","November","December"];
  var WHO=["standing","study","floor"];
  var WHAT=["hearing","exec","work","conf"];
  // A card's kinds are its bar's colours; the "what" boxes take them in four.
  // Floor is not a kind of committee meeting and is the "who" box's to decide.
  var WHAT_OF={hearing:"hearing",exec:"exec",meet:"work",other:"work",conf:"conf"};
  var BAR_ORDER=["hearing","meet","exec","conf","floor","other"];
  var VIEWS=["list","week","day"];
  // A CARD'S OPENING TAG, NEVER WRITTEN WHOLE HERE. The checks count cards,
  // links and the empty day's sentence in a built page's text, and this
  // script is in that text; spelling the tag out would count as a card.
  var CARD='<details class="cal'+'meet"';
  var CARD_TAG=new RegExp("^"+CARD+"[^>]*>"), CARDS=new RegExp(CARD+"[\\s\\S]*?</details>","g");

  function pad(n){ return (n<10?"0":"")+n; }
  function iso(y,m,d){
    var x=new Date(Date.UTC(y,m-1,d));
    return x.getUTCFullYear()+"-"+pad(x.getUTCMonth()+1)+"-"+pad(x.getUTCDate());
  }
  function utc(s){ return Date.UTC(+s.slice(0,4),+s.slice(5,7)-1,+s.slice(8,10)); }
  function addDays(s,n){ return iso(+s.slice(0,4),+s.slice(5,7),+s.slice(8,10)+n); }
  // Monday is 0: the weeks here are ISO weeks, Monday to Sunday, which is
  // what every week's address names.
  function weekday(s){ return (new Date(utc(s)).getUTCDay()+6)%7; }
  function monday(s){ return addDays(s,-weekday(s)); }
  function weekKey(s){
    var t=addDays(monday(s),3), y=+t.slice(0,4);
    return y+"-W"+pad(Math.floor((utc(t)-Date.UTC(y,0,1))/864e5/7)+1);
  }
  // The fourth of January is always in week 1.
  function keyMonday(k){ return addDays(monday(iso(+k.slice(0,4),1,4)),(+k.slice(6)-1)*7); }
  function month(s){ return s.slice(0,7); }
  function addMonths(m,n){
    var y=+m.slice(0,4), i=+m.slice(5,7)-1+n;
    return (y+Math.floor(i/12))+"-"+pad(((i%12)+12)%12+1);
  }
  function daysIn(m){ return new Date(Date.UTC(+m.slice(0,4),+m.slice(5,7),0)).getUTCDate(); }
  // The rows a month's grid draws: whole weeks, Monday first, so a week is
  // one row and the selected one can be one band.
  function monthRows(m){
    var last=m+"-"+pad(daysIn(m)), d=monday(m+"-01"), rows=[];
    while(d<=last){
      var r=[];
      for(var i=0;i<7;i++){ r.push(d); d=addDays(d,1); }
      rows.push(r);
    }
    return rows;
  }
  function shiftMonth(s,n){
    var m=addMonths(month(s),n);
    return m+"-"+pad(Math.min(+s.slice(8),daysIn(m)));
  }
  function dayWords(s){ return DAYNAME[weekday(s)]+" "+(+s.slice(8))+" "+MONTH[+s.slice(5,7)-1]; }
  function monthWords(m){ return MONTH[+m.slice(5,7)-1]+" "+m.slice(0,4); }
  // build_calendar.day_words's rule, in the reader's clock.
  function relWord(s,today){
    var off=Math.round((utc(s)-utc(today))/864e5);
    return off===0?"today":off===1?"tomorrow":(off>0&&off<=14)?"in "+off+" days":"";
  }
  function plural(n,w){ return n+" "+w+(n===1?"":"s"); }
  function esc(s){
    return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;")
      .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }
  function unesc(s){
    return String(s).replace(/&(amp|lt|gt|quot|#x27|#39);/g,function(_m,e){
      return {amp:"&",lt:"<",gt:">",quot:'"',"#x27":"'","#39":"'"}[e]; });
  }
  function words(v){ return String(v||"").split(" ").filter(Boolean); }

  // ---- a card, read off the card ---------------------------------------------
  //
  // EVERYTHING THE GRID, THE PREVIEW AND THE FILTERS NEED IS ON THE CARD
  // ALREADY, put there by build_pages.cal_days for the week's own filter. So
  // an entry is its card's HTML and what that card says about itself, read
  // the same way whether the card came in the page or in a month file.
  function attr(tag,name){
    var m=new RegExp(" "+name+'="([^"]*)"').exec(tag);
    return m?unesc(m[1]):null;
  }
  function parseCard(html){
    var tag=(CARD_TAG.exec(html)||[""])[0],
        name=/<span class="calcmte">([^<]*)<\/span>/.exec(html);
    return {html:html, date:attr(tag,"data-date")||"",
            name:name?unesc(name[1]):"", cmte:attr(tag,"data-cmte")||"",
            body:attr(tag,"data-body")||"", bills:words(attr(tag,"data-bills")),
            time:attr(tag,"data-time")||"", last:attr(tag,"data-last")||"",
            venue:attr(tag,"data-venue")||"",
            study:attr(tag,"data-study")!==null,
            cancelled:attr(tag,"data-cancelled")!==null,
            who:attr(tag,"data-who")||"standing", kinds:words(attr(tag,"data-kinds"))};
  }
  // A day as cal_days draws it: its heading, then its cards, then the close.
  // Cards never nest, so each one runs to the first </details> after it.
  function parseDay(html){
    var i=html.indexOf(CARD);
    return {head:i<0?html.replace(/<\/div>\s*$/,""):html.slice(0,i),
            cards:(html.match(CARDS)||[]).map(parseCard)};
  }
  function dayHtml(day,cards){
    return day.head+cards.map(function(e){ return e.html; }).join("")+"</div>";
  }

  // ---- the filters -------------------------------------------------------------
  function defaults(){
    return {v:"list", who:WHO.slice(), what:WHAT.slice(), body:"", picks:[], q:""};
  }
  // "HB 1234", "hb1234" and "1234" all mean the same bill to a person typing
  // it, and none of them is what the attribute holds.
  function norm(s){ return String(s||"").toUpperCase().replace(/[^A-Z0-9]/g,""); }
  // WHO AND WHAT, AND THE REST. Committees chosen by name replace the "who"
  // boxes; an entry holding several kinds matches when any of them is ticked
  // and is shown whole; the floor answers to "who" alone.
  function matches(e,f){
    if(f.picks.length ? f.picks.indexOf(e.name)<0 : f.who.indexOf(e.who)<0) return false;
    if(e.who!=="floor" && e.kinds.length && !e.kinds.some(function(k){
        return f.what.indexOf(WHAT_OF[k]||"work")>=0; })) return false;
    if(f.body && e.body.indexOf(f.body)<0) return false;
    var q=String(f.q||"").trim();
    if(!q) return true;
    if(e.cmte.indexOf(q.toLowerCase())>=0) return true;
    var n=norm(q);
    return !!n && e.bills.some(function(b){ return norm(b).indexOf(n)===0; });
  }
  // THE TWO COMBINATIONS THE PERSON NAMED, one click each: standing
  // committees only, and public hearings only. Each sets the boxes, which
  // stay the model -- the reader can see exactly what was ticked, and change
  // it. A hearing is a committee's, so "public hearings only" takes the
  // floor off as well.
  var QUICK={standing:{who:["standing"],what:WHAT.slice()},
             hearing:{who:["standing","study"],what:["hearing"]}};
  function quickOf(f){
    if(f.picks.length) return "";
    for(var k in QUICK){
      var q=QUICK[k];
      if(q.who.join()===WHO.filter(function(x){ return f.who.indexOf(x)>=0; }).join()
         && q.what.join()===WHAT.filter(function(x){ return f.what.indexOf(x)>=0; }).join()) return k;
    }
    return "";
  }
  // How many things narrow the schedule now: what the reset control and the
  // folded filters' button say.
  function narrowed(f){
    return (f.who.length!==WHO.length)+(f.what.length!==WHAT.length)+(!!f.body)
      +(!!f.picks.length)+(!!String(f.q||"").trim());
  }
  // A CANCELLED MEETING IS SHOWN AND NOT COUNTED, as the week's lead counts:
  // "22 sittings" of a week in which 21 met was a wrong number.
  function tally(entries,f){
    var t={total:0,shown:0,seen:0};
    entries.forEach(function(e){
      var ok=matches(e,f);
      if(!e.cancelled) t.total++;
      if(ok){ t.seen++; if(!e.cancelled) t.shown++; }
    });
    return t;
  }
  function countLine(t,where){
    if(t.shown===t.total)
      return (t.total?plural(t.total,"sitting"):"No sittings")+" "+where+".";
    if(!t.seen)
      return t.total===1 ? "The one sitting "+where+" does not match."
                         : "None of the "+t.total+" sittings "+where+" match.";
    return t.shown+" of "+plural(t.total,"sitting")+" shown"
      +(where==="this week"?"":" "+where)+".";
  }

  // ---- the arrangements --------------------------------------------------------
  //
  // THE LIST: the week page's own rule. Every weekday, an empty one saying so
  // under any filter, because "No meetings scheduled" is true of it whatever
  // is ticked; a Saturday or Sunday only when something shown is on it; and a
  // busy day the filters emptied goes, rather than standing as a heading over
  // nothing.
  function listDates(dates,days,f){
    return dates.filter(function(d){
      var day=days[d];
      if(!day) return false;
      if(!day.cards.length) return weekday(d)<5;
      return day.cards.some(function(e){ return matches(e,f); });
    });
  }
  // THE WEEK AT A GLANCE: weekdays always, a weekend day when something shown
  // is on it.
  function weekCols(dates,days,f){
    return dates.filter(function(d){
      return weekday(d)<5 || ((days[d]||{}).cards||[]).some(function(e){ return matches(e,f); });
    });
  }
  // THE RECORD HAS NO END TIMES. The docket says when business is taken up
  // and never when a committee rises, so the week is not drawn as blocks of
  // invented length on a clock: its rows are the hours that something starts
  // in, and a sitting with no time on the record gets a row saying so.
  function hourOf(t){ return /^\d\d:\d\d/.test(t||"")?t.slice(0,2):""; }
  function weekRows(cols,by){
    var hours={}, none=false;
    cols.forEach(function(d){ (by[d]||[]).forEach(function(e){
      var h=hourOf(e.time); if(h) hours[h]=1; else none=true; }); });
    var hs=Object.keys(hours).sort();
    if(none) hs.push("");
    return hs.map(function(h){
      return {h:h, cells:cols.map(function(d){
        return (by[d]||[]).filter(function(e){ return hourOf(e.time)===h; }); })};
    });
  }
  // The day a week opens on, when the address does not name one: today if
  // the week holds it, else its first day with a sitting, else its Monday.
  function firstDay(key,days,today,first,last){
    var mon=keyMonday(key);
    for(var i=0;i<7;i++){ if(addDays(mon,i)===today && today>=first && today<=last) return today; }
    for(var j=0;j<7;j++){
      var day=days[addDays(mon,j)];
      if(day && day.cards.some(function(e){ return !e.cancelled; })) return addDays(mon,j);
    }
    return mon<first?first:mon;
  }

  // ---- the address ---------------------------------------------------------------
  //
  // THE VIEW, THE DAY AND THE FILTERS LIVE IN THE HASH of the week's own
  // address -- /calendar/2026-W11#d=2026-03-11&v=day&what=hearing -- so a view
  // can be sent to somebody and Back undoes a step. A hash, not a query: the
  // page is a file on a CDN and the week is already in the path.
  function readHash(h){
    var p=new URLSearchParams(String(h||"").replace(/^#/,"")), s={}, any=false;
    function list(k,ok){ return (p.get(k)||"").split(",").filter(function(x){ return ok.indexOf(x)>=0; }); }
    // A DAY THE CALENDAR HAS. "2026-02-30" has the shape of a date and is
    // not one: taken at its word it opened a Day view of nothing, stuck on
    // "Loading". A day is kept only if it comes back from the arithmetic as
    // itself; an address that names no real day opens the week as usual.
    var d=p.get("d")||"";
    if(/^\d{4}-\d\d-\d\d$/.test(d) && iso(+d.slice(0,4),+d.slice(5,7),+d.slice(8,10))===d){ s.d=d; any=true; }
    if(VIEWS.indexOf(p.get("v"))>=0){ s.v=p.get("v"); any=true; }
    if(p.has("who")){ s.who=list("who",WHO); any=true; }
    if(p.has("what")){ s.what=list("what",WHAT); any=true; }
    if(p.get("b")==="H"||p.get("b")==="S"){ s.body=p.get("b"); any=true; }
    var c=p.getAll("c").filter(Boolean);
    if(c.length){ s.picks=c; any=true; }
    if(p.get("q")){ s.q=p.get("q"); any=true; }
    return any?s:null;
  }
  function writeHash(f,d){
    var p=new URLSearchParams();
    p.set("d",d);
    if(f.v!=="list") p.set("v",f.v);
    if(f.who.length!==WHO.length) p.set("who",f.who.join(","));
    if(f.what.length!==WHAT.length) p.set("what",f.what.join(","));
    if(f.body) p.set("b",f.body);
    f.picks.forEach(function(c){ p.append("c",c); });
    if(String(f.q||"").trim()) p.set("q",String(f.q).trim());
    return "#"+p.toString();
  }

  // ---- the month grid and the preview ----------------------------------------------
  function barsOf(entries){
    var seen={};
    entries.forEach(function(e){ if(!e.cancelled) e.kinds.forEach(function(k){ seen[k]=1; }); });
    return BAR_ORDER.filter(function(k){ return seen[k]; });
  }
  // One day of the grid. THE MARKER IS A FEW DOTS IN THE KINDS' COLOURS, not a
  // number the eye has to read; the number is in the cell's name, which is
  // what a screen reader announces. c: {view, sel, focus, today, first, last,
  // days, f}.
  function cellHtml(d,c){
    var on=d>=c.first&&d<=c.last, day=c.days[d],
        vis=day?day.cards.filter(function(e){ return matches(e,c.f); }):[],
        live=vis.filter(function(e){ return !e.cancelled; }).length,
        cls=["cmday"], name=dayWords(d)+" "+d.slice(0,4);
    if(month(d)!==c.view) cls.push("cmout");
    if(d<c.today) cls.push("cmpast");
    if(d===c.today) cls.push("cmnow");
    if(d===c.sel) cls.push("cmpick");
    if(!on){ cls.push("cmoff"); name+=", not on the calendar"; }
    else if(!day) name+=", loading";
    else{
      name+=", "+(live?plural(live,"sitting"):"no sittings");
      if(vis.length>live) name+=", "+(vis.length-live)+" cancelled";
    }
    return '<td role="gridcell" class="'+cls.join(" ")+'" data-d="'+d+'" tabindex="'
      +(d===c.focus?"0":"-1")+'" aria-selected="'+(d===c.sel)+'"'
      +(d===c.today?' aria-current="date"':"")+(on?"":' aria-disabled="true"')+'>'
      +'<span class="cmn" aria-hidden="true">'+(+d.slice(8))+'</span>'
      +'<span class="cmdots" aria-hidden="true">'
      +barsOf(vis).map(function(k){ return '<i class="k-'+k+'"></i>'; }).join("")+'</span>'
      +'<span class="sr">'+esc(name)+'</span></td>';
  }
  function gridHtml(c){
    var sw=weekKey(c.sel);
    return '<thead><tr>'+DAYNAME.map(function(n){
        return '<th scope="col"><span aria-hidden="true">'+n.slice(0,2)
          +'</span><span class="sr">'+n+'</span></th>'; }).join("")+'</tr></thead><tbody>'
      +monthRows(c.view).map(function(r){
        return '<tr class="cmrow'+(weekKey(r[0])===sw?" cmsel":"")+'">'
          +r.map(function(d){ return cellHtml(d,c); }).join("")+'</tr>'; }).join("")
      +'</tbody>';
  }
  // The preview of one day: time, committee and the kind's colour, a handful
  // of them and how many more. c: {days, f}.
  function peekHtml(d,c,cap){
    var day=c.days[d], h='<p class="pkd">'+esc(dayWords(d))+'</p>';
    if(!day) return h+'<p class="pkmore">Loading&hellip;</p>';
    var vis=day.cards.filter(function(e){ return matches(e,c.f); });
    if(!vis.length)
      return h+'<p class="pkmore">'+(day.cards.length?"Nothing on this day matches the filters."
                                                     :"Nothing is scheduled.")+'</p>';
    h+='<ul class="pklist">'+vis.slice(0,cap).map(function(e){
      return '<li><span class="pkbar">'+(e.kinds.length?e.kinds:["other"]).map(function(k){
          return '<i class="k-'+k+'"></i>'; }).join("")+'</span>'
        +'<span class="pkt">'+esc(e.time)+'</span>'
        +'<span class="pkn">'+esc(e.name)+(e.cancelled?' <em>cancelled</em>':"")+'</span></li>';
    }).join("")+'</ul>';
    if(vis.length>cap) h+='<p class="pkmore">and '+(vis.length-cap)+' more</p>';
    return h;
  }
  // The arrow keys of a date grid, as the ARIA date-picker pattern has them.
  function stepKey(d,k,shift){
    switch(k){
      case "ArrowLeft": return addDays(d,-1);
      case "ArrowRight": return addDays(d,1);
      case "ArrowUp": return addDays(d,-7);
      case "ArrowDown": return addDays(d,7);
      case "Home": return monday(d);
      case "End": return addDays(monday(d),6);
      case "PageUp": return shiftMonth(d,shift?-12:-1);
      case "PageDown": return shiftMonth(d,shift?12:1);
    }
    return null;
  }

  var CORE={iso:iso, addDays:addDays, weekday:weekday, monday:monday, weekKey:weekKey,
    keyMonday:keyMonday, month:month, addMonths:addMonths, monthRows:monthRows,
    shiftMonth:shiftMonth, dayWords:dayWords, relWord:relWord, parseCard:parseCard,
    parseDay:parseDay, dayHtml:dayHtml, defaults:defaults, matches:matches,
    narrowed:narrowed, tally:tally, countLine:countLine, listDates:listDates,
    weekCols:weekCols, weekRows:weekRows, firstDay:firstDay, readHash:readHash,
    writeHash:writeHash, barsOf:barsOf, cellHtml:cellHtml, gridHtml:gridHtml,
    peekHtml:peekHtml, stepKey:stepKey, quickOf:quickOf, QUICK:QUICK, WHO:WHO, WHAT:WHAT};
  G.GRCAL=CORE;

  // ==== THE PAGE ===================================================================
  var app=document.getElementById("calapp");
  if(!app||!app.querySelector) return;
  function $(id){ return document.getElementById(id); }
  function all(root,sel){ return [].slice.call(root.querySelectorAll(sel)); }
  var side=$("calside"), bar=$("calbar"), view=$("calview"), grid=$("cmgrid"),
      mtitle=$("cmtitle"), count=$("wkcount"), form=$("wkfilter"), find=$("wkfind"),
      study=$("wkstudy"), peek=$("calpeek"), reset=$("calreset"), cpfind=$("cpfind"),
      cplist=$("cplist"), cpchosen=$("cpchosen"), cpall=$("cpall"), cpstat=$("cpstat"),
      whohint=$("whohint"), mfold=$("cmfold"), ffold=$("cffold"),
      head=app.querySelector(".calhead"), h1=head.querySelector("h1"),
      lead=head.querySelector("p.src");
  var HERE=app.getAttribute("data-here"), PAGEWEEK=app.getAttribute("data-week"),
      FIRST=keyMonday(app.getAttribute("data-first")),
      LAST=addDays(keyMonday(app.getAttribute("data-last")),6);
  // TODAY IS THE READER'S, not the build's: the page is read for a week after
  // it is made, and "past" and "today" are about when it is read.
  var now=new Date(), TODAY=iso(now.getFullYear(),now.getMonth()+1,now.getDate());
  var LASTMONTH=month(LAST)>month(TODAY)?month(LAST):month(TODAY);
  var DAYS={}, WEEKS={}, MONTHS={}, OPEN={list:{},week:{},day:{}}, NAMES=null;
  function inRange(d){ return d>=FIRST&&d<=LAST; }
  function clamp(d){ return d<FIRST?FIRST:d>LAST?LAST:d; }
  // Where a week lives: build_calendar.href_for, which puts the week the
  // build called this one at /calendar.
  function hrefFor(k){ return k===HERE?"/calendar":"/calendar/"+k; }
  function pathWeek(){ var m=/\/calendar\/(\d{4}-W\d\d)/.exec(location.pathname); return m?m[1]:HERE; }
  function weekDates(){
    var m=monday(SEL), out=[];
    for(var i=0;i<7;i++){ var d=addDays(m,i); if(inRange(d)) out.push(d); }
    return out;
  }
  function visible(d){ return ((DAYS[d]||{}).cards||[]).filter(function(e){ return matches(e,S); }); }

  // The week this page was built with is in it already: the script starts
  // from those cards and needs no file for them.
  all(view,".calday[data-d]").forEach(function(el){ DAYS[el.getAttribute("data-d")]=parseDay(el.outerHTML); });
  WEEKS[PAGEWEEK]={label:h1.textContent.replace(/^The week of /,""), lead:lead?lead.textContent:""};

  // ---- where the reader is -------------------------------------------------------
  var SKEY="gr.calendar.study", S, SEL, VIEWM, FOCUS;
  function fromLocation(){
    var h=readHash(location.hash);
    S=defaults();
    if(h) ["v","who","what","body","picks","q"].forEach(function(k){ if(k in h) S[k]=h[k]; });
    // STUDY AND STATUTORY COMMITTEES, on unless the reader turned them off
    // here before. The choice is a convenience kept in this browser; storage
    // that is blocked or empty leaves the default, which is on. An address
    // that says who to show wins over it.
    if(study && !(h&&h.who)){
      try{ if(localStorage.getItem(SKEY)==="0") S.who=S.who.filter(function(x){ return x!=="study"; }); }catch(e){}
    }
    // The tab, /calendar, opens on the reader's today; a week's own address
    // on that week.
    var onTab=!/\/calendar\/\d{4}-W\d\d/.test(location.pathname);
    SEL=h&&h.d&&inRange(h.d) ? h.d
      : onTab&&inRange(TODAY) ? TODAY
      : firstDay(pathWeek(),DAYS,TODAY,FIRST,LAST);
    VIEWM=month(SEL); FOCUS=SEL;
  }

  // ---- the month files -------------------------------------------------------------
  function load(m){
    if(MONTHS[m]) return;
    if(m<month(FIRST)||m>month(LAST)){ MONTHS[m]="none"; return; }
    MONTHS[m]="loading";
    fetch("/calendar/data/"+m+".json").then(function(r){
      if(!r.ok) throw new Error("HTTP "+r.status);
      return r.json();
    }).then(function(j){
      var shown=weekDates(), fresh=false;
      Object.keys(j.days||{}).forEach(function(d){
        if(!DAYS[d] && shown.indexOf(d)>=0) fresh=true;
        DAYS[d]=parseDay(j.days[d]);
      });
      Object.keys(j.weeks||{}).forEach(function(k){ WEEKS[k]=j.weeks[k]; });
      MONTHS[m]="ok"; landed(fresh);
    }).catch(function(){ MONTHS[m]="fail"; landed(true); });
  }
  function landed(panel){
    drawGrid(); drawHead();
    if(panel) drawPanel(); else drawCount();
    if(peekD) showPeek(peekD,peekFrom);
  }
  // The months the grid and the selected week need now; and a moment later
  // the months either side whose days the grid's first and last rows show,
  // which is all a neighbour is fetched for until the reader goes to it.
  var nearT=0;
  function need(){
    var mon=monday(SEL);
    [VIEWM, month(mon), month(addDays(mon,6))].forEach(load);
    clearTimeout(nearT);
    nearT=setTimeout(function(){
      var rows=monthRows(VIEWM);
      [rows[0][0], rows[rows.length-1][6]].forEach(function(d){ load(month(d)); });
    },600);
  }

  // ---- drawing -----------------------------------------------------------------------
  function drawGrid(focusIt){
    var had=focusIt||grid.contains(document.activeElement);
    // The cell that takes Tab is one the grid is showing.
    if(month(FOCUS)!==VIEWM)
      FOCUS=month(SEL)===VIEWM?SEL:month(TODAY)===VIEWM&&inRange(TODAY)?TODAY:clamp(VIEWM+"-01");
    // A live region, so written only when the month changes: set on every
    // redraw it would say the month again over the count.
    if(mtitle.textContent!==monthWords(VIEWM)) mtitle.textContent=monthWords(VIEWM);
    // aria-disabled, not disabled: a button that disables itself under the
    // reader's finger drops their focus on the page.
    $("cmprev").setAttribute("aria-disabled",VIEWM<=month(FIRST)?"true":"false");
    $("cmnext").setAttribute("aria-disabled",VIEWM>=LASTMONTH?"true":"false");
    grid.innerHTML=gridHtml({view:VIEWM, sel:SEL, focus:FOCUS, today:TODAY,
                             first:FIRST, last:LAST, days:DAYS, f:S});
    grid.setAttribute("aria-busy",MONTHS[VIEWM]==="loading"?"true":"false");
    if(had){ var td=grid.querySelector('td[data-d="'+FOCUS+'"]'); if(td) td.focus(); }
  }
  var NAV=null;
  function drawHead(){
    var k=weekKey(SEL), w=WEEKS[k];
    if(w){
      h1.textContent="The week of "+w.label;
      if(lead) lead.textContent=w.lead;
      document.title="The week of "+w.label+" | Granite Record";
      rename(k);
    }
    // The arrows are written again only when they change -- against what was
    // last written here, not against innerHTML, which a browser hands back
    // with "&lsaquo;" decoded and so never matched. AND FOCUS STAYS ON THE
    // ARROW PRESSED. Paging week to week is the page's keyboard flow, and the
    // link that had focus goes with the old arrows: left there, focus fell to
    // the page, a screen reader said nothing, and Enter again did nothing. The
    // same arrow in the new ones takes it; where that arrow is no more --
    // "This week" on this week, "The week after" on the last -- the heading
    // that names the week now shown takes it.
    var html=navHtml(k);
    if(html===NAV) return;
    NAV=html;
    var a=document.activeElement, navs=all(app,".wknav"), at=-1, cls="";
    navs.forEach(function(n,i){ if(a&&a!==n&&n.contains(a)){ at=i; cls=(a.className||"").split(" ")[0]; } });
    navs.forEach(function(n){ n.innerHTML=html; });
    if(at>=0){
      var t=cls?navs[at].querySelector("a."+cls):null;
      if(!t){ h1.tabIndex=-1; t=h1; }
      t.focus();
    }
  }
  // THE PAGE NAMES THE WEEK IT SHOWS, not the week it was loaded as. Moving
  // week in place changed the heading and the tab's title and left the rest
  // naming the old week: "Cite this page" cited 9-15 March at its address
  // while the reader looked at 16-22 March, and the canonical link and
  // og:url -- what a phone's share sheet sends -- said the same. So the
  // citation's four forms, the canonical link, the og tags, the description
  // and the structured data follow the heading, with the address
  // build_calendar gives that week. The citation is shell.py's and is not
  // drawn again here: the week and its address are swapped in the text it
  // already holds, which leaves the reader's own date app.js put in it alone.
  var canon=document.querySelector('link[rel="canonical"]'),
      CANON=canon?canon.getAttribute("href")||"":"",
      ORIGIN=CANON.indexOf("/calendar")>0?CANON.slice(0,CANON.indexOf("/calendar")):location.origin;
  // shell.cite_block's BibTeX key: the address, its slashes as hyphens.
  function citeKey(url){
    return url.slice(ORIGIN.length).replace(/^\/+/,"").replace(/\//g,"-").replace(/\./g,"")||"granite-record";
  }
  var NAMED={label:WEEKS[PAGEWEEK].label, url:CANON||ORIGIN+hrefFor(PAGEWEEK)};
  NAMED.key=citeKey(NAMED.url);
  function swap(s,pairs){
    pairs.forEach(function(p){ if(p[0]&&p[0]!==p[1]) s=s.split(p[0]).join(p[1]); });
    return s;
  }
  function swapText(n,pairs){
    for(var i=0;i<n.childNodes.length;i++){
      var c=n.childNodes[i];
      if(c.nodeType===3){ var t=swap(c.data,pairs); if(t!==c.data) c.data=t; }
      else if(c.nodeType===1) swapText(c,pairs);
    }
  }
  function rename(k){
    var to={label:WEEKS[k].label, url:ORIGIN+hrefFor(k)};
    to.key=citeKey(to.url);
    if(to.label===NAMED.label && to.url===NAMED.url) return;
    // The address first and whole: "/calendar" is the start of every week's.
    var pairs=[[NAMED.url,to.url],[NAMED.label,to.label],["{"+NAMED.key+",","{"+to.key+","]];
    all(document,".pcite dd").forEach(function(dd){ swapText(dd,pairs); });
    all(document,'script[type="application/ld+json"]').forEach(function(s){ swapText(s,pairs); });
    [['link[rel="canonical"]',"href"],['meta[property="og:url"]',"content"],
     ['meta[property="og:title"]',"content"],['meta[property="og:description"]',"content"],
     ['meta[name="description"]',"content"]].forEach(function(x){
      all(document,x[0]).forEach(function(el){
        var v=el.getAttribute(x[1])||"", t=swap(v,pairs);
        if(t!==v) el.setAttribute(x[1],t);
      });
    });
    NAMED=to;
  }
  // The week's arrows, as week_page writes them, stepping from the day
  // selected: previous on the left, next on the right.
  function navHtml(k){
    var mon=keyMonday(k), h="", tk=weekKey(clamp(TODAY));
    if(addDays(mon,-1)>=FIRST)
      h+='<a class="wkprev" data-step="-7" href="'+hrefFor(weekKey(addDays(mon,-7)))+'">&lsaquo; The week before</a>';
    if(k!==tk && inRange(TODAY))
      h+='<a class="wkhere" data-today="" href="'+hrefFor(tk)+'">This week</a>';
    if(addDays(mon,7)<=LAST)
      h+='<a class="wknext" data-step="7" href="'+hrefFor(weekKey(addDays(mon,7)))+'">The week after &rsaquo;</a>';
    return h;
  }
  function drawCount(){
    var dates=S.v==="day"?[SEL]:weekDates(), list=[];
    dates.forEach(function(d){ if(DAYS[d]) list=list.concat(DAYS[d].cards); });
    var t=countLine(tally(list,S), S.v==="day"?"on "+dayWords(SEL):"this week");
    // Said once: a live region repeats whatever it is given.
    if(count.textContent!==t) count.textContent=t;
  }
  function listView(dates){
    return listDates(dates,DAYS,S).map(function(d){ return dayHtml(DAYS[d],visible(d)); }).join("")
      || '<p class="calempty">Nothing this week matches the filters.</p>';
  }
  function dayView(){
    var d=SEL, day=DAYS[d], vis=visible(d);
    var step='<div class="calstep">'
      +(addDays(d,-1)>=FIRST?'<button type="button" class="calstepb" data-step="-1">&lsaquo; '
        +esc(dayWords(addDays(d,-1)))+'</button>':"")
      +(addDays(d,1)<=LAST?'<button type="button" class="calstepb calstepn" data-step="1">'
        +esc(dayWords(addDays(d,1)))+' &rsaquo;</button>':"")+'</div>';
    if(day.cards.length && !vis.length)
      return step+day.head+'<p class="calempty">Nothing on this day matches the filters.</p></div>';
    return step+dayHtml(day,vis);
  }
  function weekView(dates){
    var cols=weekCols(dates,DAYS,S), by={};
    cols.forEach(function(d){ by[d]=visible(d); });
    var rows=weekRows(cols,by), any=dates.some(function(d){ return DAYS[d]&&DAYS[d].cards.length; });
    var h='<div class="wkgridwrap" role="region" tabindex="0" '
      +'aria-label="The week at a glance, by the hour each sitting starts">'
      +'<table class="wkgrid" style="--cols:'+cols.length+'"><thead><tr>'
      +'<th scope="col" class="wkhr"><span class="sr">Starts</span></th>'
      +cols.map(function(d){
        return '<th scope="col" class="wkcol'+(d===SEL?" wksel":"")+(d<TODAY?" wkpast":"")+'"'
          +(d===TODAY?' aria-current="date"':"")+'><button type="button" class="wkday" data-d="'+d+'">'
          +'<span class="wkdn">'+DAYNAME[weekday(d)].slice(0,3)+'</span> '
          +'<span class="wkdd">'+(+d.slice(8))+" "+MONTH[+d.slice(5,7)-1].slice(0,3)+'</span>'
          +'<span class="sr">: open '+esc(dayWords(d))+'</span></button></th>'; }).join("")
      +'</tr></thead><tbody>';
    if(!rows.length)
      h+='<tr><td class="wknone" colspan="'+(cols.length+1)+'">'
        +(any?"Nothing this week matches the filters.":"Nothing is scheduled this week.")+'</td></tr>';
    rows.forEach(function(r){
      h+='<tr><th scope="row" class="wkhr">'+(r.h?r.h+":00":"No time given")+'</th>'
        +r.cells.map(function(c,i){
          return '<td data-d="'+cols[i]+'">'+c.map(function(e){ return e.html; }).join("")+'</td>'; }).join("")
        +'</tr>';
    });
    return h+'</tbody></table></div>';
  }
  function cardKey(m){ return (m.getAttribute("data-date")||"")+"|"+(m.getAttribute("data-cmte")||""); }
  // FOCUS IS NOT LOST WHEN THE PANEL IS DRAWN AGAIN: whatever held it -- a
  // card, a day's button, a step -- is found in the new drawing and given it
  // back, and failing that the schedule itself takes it.
  function focusMark(){
    var a=document.activeElement;
    if(!a||!view.contains(a)) return null;
    var m=a.closest&&a.closest(".calmeet");
    if(m) return {card:cardKey(m)};
    if(a.getAttribute("data-d")) return {day:a.getAttribute("data-d")};
    if(a.getAttribute("data-step")) return {step:a.getAttribute("data-step")};
    return {view:1};
  }
  function refocus(k){
    if(!k) return;
    var t=null;
    if(k.card) all(view,".calmeet").some(function(m){
      if(cardKey(m)===k.card){ t=m.querySelector("summary"); return true; } return false; });
    else if(k.day) t=view.querySelector('button[data-d="'+k.day+'"]');
    else if(k.step) t=view.querySelector('[data-step="'+k.step+'"]');
    (t||view).focus();
  }
  function drawPanel(){
    var dates=weekDates(), mark=focusMark(), html;
    var gone=dates.filter(function(d){ return !DAYS[d] && (weekday(d)<5 || (S.v==="day"&&d===SEL)); });
    if(gone.length){
      html=gone.some(function(d){ return MONTHS[month(d)]==="fail"; })
        ? '<p class="calempty">This week could not be loaded here. <a href="'+hrefFor(weekKey(SEL))
          +'">Open the week on its own page</a>.</p>'
        : '<p class="calempty">Loading the week&hellip;</p>';
    }else if(S.v==="day") html=dayView();
    else if(S.v==="week") html=weekView(dates);
    else html=listView(dates);
    view.innerHTML=html;
    view.setAttribute("data-view",S.v);
    all(view,".calmeet").forEach(function(m){
      var o=OPEN[S.v][cardKey(m)];
      // THE DAY VIEW IS EVERY ENTRY IN FULL, so its cards open; the list and
      // the week are for scanning, so theirs stay shut until opened.
      m.open=o===undefined?S.v==="day":o;
      addToCalendar(m);
    });
    all(view,".calday[data-d]").forEach(function(el){
      var d=el.getAttribute("data-d"), r=el.querySelector(".cdrel");
      if(r) r.textContent=relWord(d,TODAY);
      if(d===SEL && S.v==="list") el.classList.add("calsel");
    });
    refocus(mark);
    drawCount();
  }
  function drawAll(){ drawGrid(); drawHead(); drawPanel(); syncControls(); }
  // Bring the selected day into view when it is off the screen: the grid is
  // above the schedule on a phone, and beside a long list on a desktop.
  function reveal(){
    var t=S.v==="list"?view.querySelector(".calday.calsel"):view;
    if(!t||!t.getBoundingClientRect) return;
    var r=t.getBoundingClientRect();
    if(r.top<0||r.top>(window.innerHeight||0)*0.75) t.scrollIntoView({block:"start"});
  }
  function commit(push){
    var wk=weekKey(SEL), path=pathWeek()===wk?location.pathname:hrefFor(wk),
        url=path+writeHash(S,SEL);
    if(url===location.pathname+location.hash) return;
    try{ history[push?"pushState":"replaceState"](null,"",url); }catch(e){}
    skipTo();
  }
  // The shell's skip link names the page's own address, and the address may
  // now be another week's. Left as it was, following it loaded the week the
  // page was opened on as a new page and threw the reader's place away.
  function skipTo(){
    var s=document.querySelector("a.skip");
    if(s) s.setAttribute("href",location.pathname+"#results");
  }
  function select(d,how){
    SEL=clamp(d); FOCUS=SEL; VIEWM=month(SEL);
    need(); drawGrid(how==="key"); drawHead(); drawPanel(); commit(true);
    if(how==="grid"||how==="key"||how==="nav"||how==="today") reveal();
  }

  // ---- the controls ---------------------------------------------------------------
  function values(name){
    return all(form,'input[name="'+name+'"]').filter(function(i){ return i.checked; })
      .map(function(i){ return i.value; });
  }
  function syncControls(){
    all(form,'input[name="who"]').forEach(function(i){
      i.checked=S.who.indexOf(i.value)>=0; i.disabled=!!S.picks.length; });
    whohint.hidden=!S.picks.length;
    all(form,'input[name="what"]').forEach(function(i){ i.checked=S.what.indexOf(i.value)>=0; });
    all(form,"[data-body]").forEach(function(b){
      b.setAttribute("aria-pressed",(b.getAttribute("data-body")||"")===S.body?"true":"false"); });
    if(find.value!==S.q) find.value=S.q;
    var qk=quickOf(S);
    all(form,"[data-quick]").forEach(function(b){
      b.setAttribute("aria-pressed",b.getAttribute("data-quick")===qk?"true":"false"); });
    all(bar,"[data-view]").forEach(function(b){
      b.setAttribute("aria-pressed",b.getAttribute("data-view")===S.v?"true":"false"); });
    cpchosen.innerHTML=S.picks.map(function(n){
      return '<button type="button" class="cpchip" data-name="'+esc(n)+'">'+esc(n)
        +'<span class="sr">: stop showing only this committee</span><span aria-hidden="true"> &times;</span></button>';
    }).join("");
    all(cplist,"input").forEach(function(i){ i.checked=S.picks.indexOf(i.value)>=0; });
    var n=narrowed(S);
    reset.hidden=!n;
    ffold.textContent=(side.classList.contains("ffolded")?"Show the filters":"Hide the filters")
      +(n?" ("+n+" on)":"");
  }
  var CHAMBER={"H":"House","S":"Senate","H S":"House and Senate"};
  var GROUP={standing:"Standing committees and committees of conference",study:"Study and statutory committees",
             floor:"Floor sessions"};
  function drawList(){
    var q=cpfind.value.trim().toLowerCase(), open=cpall.getAttribute("aria-expanded")==="true";
    if(!q&&!open){ cplist.hidden=true; cpstat.textContent=""; return; }
    cplist.hidden=false;
    if(!NAMES){ cplist.innerHTML='<p class="calhint">Loading the committees&hellip;</p>'; return; }
    var rows=NAMES.filter(function(c){ return !q||c[0].toLowerCase().indexOf(q)>=0; }), last="";
    cplist.innerHTML=rows.map(function(c){
      var g=c[1]!==last?'<p class="cpgroup">'+esc(GROUP[c[1]]||"")+'</p>':"";
      last=c[1];
      return g+'<label class="calchk cpopt"><input type="checkbox" value="'+esc(c[0])+'"'
        +(S.picks.indexOf(c[0])>=0?" checked":"")+'><span>'+esc(c[0])
        +(CHAMBER[c[2]]?' <span class="cpwho">'+CHAMBER[c[2]]+'</span>':"")+'</span></label>';
    }).join("")||'<p class="calhint">No committee on the calendar has that in its name.</p>';
    cpstat.textContent=q?plural(rows.length,"committee")+" match.":"";
  }
  var asked=false;
  function loadNames(){
    if(asked) return;
    asked=true;
    fetch("/calendar/data/committees.json").then(function(r){
      if(!r.ok) throw new Error("HTTP "+r.status); return r.json();
    }).then(function(j){ NAMES=j; drawList(); }).catch(function(){
      asked=false;
      cplist.innerHTML='<p class="calhint">The list of committees could not be loaded.</p>';
    });
  }
  function apply(){
    syncControls(); drawGrid(); drawPanel(); commit(false);
    if(peekD) showPeek(peekD,peekFrom);
  }
  function setFold(on,store){
    side.classList.toggle("folded",on);
    mfold.setAttribute("aria-expanded",on?"false":"true");
    mfold.textContent=on?"Show the whole month":"Show only this week";
    if(store){ try{ localStorage.setItem("gr.calendar.fold",on?"1":"0"); }catch(e){} }
  }
  function setFilterFold(on){
    side.classList.toggle("ffolded",on);
    ffold.setAttribute("aria-expanded",on?"false":"true");
    syncControls();
  }

  // ---- the hover preview ---------------------------------------------------------------
  //
  // HALF A SECOND OF REST, THEN ONE ELEMENT MOVED, NOT SEVERAL OPENED. Once a
  // preview is up, the next day the pointer rests on takes it over at once, so
  // crossing the grid never opens and closes a string of them; leaving the
  // grid closes it after a beat. It sits beside the day it describes, never on
  // it, and Escape puts it away. Focus shows the same preview after the same
  // wait. A touch has no hover: a tap selects the day, and that is all.
  var peekD=null, peekFrom="", pendD=null, pendFrom="", peekT=0, coolT=0, hushD=null, touchT=0;
  function cellOf(t){ return t&&t.closest?t.closest("td[data-d]"):null; }
  function wantPeek(d,from){
    clearTimeout(coolT);
    if(d===peekD||d===pendD||d===hushD) return;
    hushD=null; pendD=d; pendFrom=from; clearTimeout(peekT);
    peekT=setTimeout(function(){ pendD=null; showPeek(d,from); }, peekD?80:500);
  }
  function showPeek(d,from){
    var td=grid.querySelector('td[data-d="'+d+'"]');
    if(!td||td.getAttribute("aria-disabled")){ hidePeek(); return; }
    peek.innerHTML=peekHtml(d,{days:DAYS,f:S},5);
    peek.hidden=false; peekD=d; peekFrom=from;
    var r=td.getBoundingClientRect(), w=peek.offsetWidth, h=peek.offsetHeight,
        W=document.documentElement.clientWidth, H=window.innerHeight, x, y;
    if(r.right+8+w<=W-8){ x=r.right+8; y=Math.min(Math.max(8,r.top),H-h-8); }
    else if(r.left-8-w>=8){ x=r.left-8-w; y=Math.min(Math.max(8,r.top),H-h-8); }
    else{
      x=Math.min(Math.max(8,r.left+r.width/2-w/2),W-w-8);
      y=r.bottom+8+h<=H-8?r.bottom+8:r.top-8-h;
    }
    peek.style.left=Math.round(x)+"px"; peek.style.top=Math.round(y)+"px";
    all(grid,'[aria-describedby="calpeek"]').forEach(function(x){ x.removeAttribute("aria-describedby"); });
    if(from==="focus") td.setAttribute("aria-describedby","calpeek");
  }
  function hidePeek(){
    clearTimeout(peekT); pendD=null;
    if(peekD===null) return;
    peek.hidden=true; peekD=null;
    all(grid,'[aria-describedby="calpeek"]').forEach(function(x){ x.removeAttribute("aria-describedby"); });
  }

  // ---- putting a sitting in the reader's own calendar ----------------------
  //
  // THE END TIME IS NOT IN THE RECORD. The docket says when a bill is taken
  // up and never when the committee rises, so every event here is an hour
  // long and says so in its own description. Inventing a plausible end and
  // staying quiet about it would put a number in somebody's calendar that no
  // document supports.
  function two(n){ return (n<10?"0":"")+n; }
  function stamp(date,time,addHours){
    var p=date.split("-"), t=(time||"09:00").split(":");
    var d=new Date(+p[0], +p[1]-1, +p[2], +t[0], +t[1]);
    if(addHours) d.setHours(d.getHours()+addHours);
    return d.getFullYear()+two(d.getMonth()+1)+two(d.getDate())+"T"+
           two(d.getHours())+two(d.getMinutes())+"00";
  }
  function details(m){
    var date=m.getAttribute("data-date"), time=m.getAttribute("data-time");
    // A cancelled meeting is not offered for anybody's calendar.
    if(!date || m.hasAttribute("data-cancelled")) return null;
    var cmte=(m.querySelector(".calcmte")||{}).textContent||"A sitting";
    var kinds=[].slice.call(m.querySelectorAll("summary .calkind"))
                 .map(function(k){return k.textContent;}).join(", ");
    var venue=m.getAttribute("data-venue")||"";
    var bills=(m.getAttribute("data-bills")||"").split(" ").filter(Boolean);
    var last=m.getAttribute("data-last");
    var note="New Hampshire General Court. "+(kinds||"Meeting")+
      (bills.length? ". Bills: "+bills.join(", ") : "")+
      (last && last!==time ? ". Items are scheduled from "+time+" to "+last : "")+
      ". The General Court does not publish an end time, so this entry is "+
      "one hour long. Source: graniterecord.org";
    // "Legislative Administration (Executive Session)". This goes into
    // somebody else's calendar, where it sits among entries from their
    // work and their family with no context at all, so it has to read as
    // a title: the committee, then what kind of sitting, in brackets and
    // capitalised. The chips on the page keep sentence case, because
    // there they sit under a heading that supplies the context.
    var titled=kinds.replace(/\w\S*/g,function(w){
      return w.charAt(0).toUpperCase()+w.slice(1);});
    return {title:cmte+(titled?" ("+titled+")":""), venue:venue, note:note,
            start:stamp(date,time,0), end:stamp(date,time,1)};
  }
  function ics(d){
    return ["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//Granite Record//EN",
            "BEGIN:VEVENT","DTSTART:"+d.start,"DTEND:"+d.end,
            "SUMMARY:"+d.title.replace(/[,;]/g,"\\$&"),
            "LOCATION:"+d.venue.replace(/[,;]/g,"\\$&"),
            "DESCRIPTION:"+d.note.replace(/[,;]/g,"\\$&"),
            "END:VEVENT","END:VCALENDAR"].join("\r\n");
  }
  function addToCalendar(m){
    var d=details(m), box=m.querySelector(".calbody");
    if(!d||!box||box.querySelector(".caladd")) return;
    var p=document.createElement("p");
    p.className="caladd";
    var g="https://calendar.google.com/calendar/render?action=TEMPLATE"+
      "&text="+encodeURIComponent(d.title)+
      "&dates="+d.start+"/"+d.end+
      "&details="+encodeURIComponent(d.note)+
      "&location="+encodeURIComponent(d.venue);
    var o="https://outlook.live.com/calendar/0/deeplink/compose?path=/calendar/action/compose"+
      "&subject="+encodeURIComponent(d.title)+
      "&startdt="+d.start.replace(/(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)/,"$1-$2-$3T$4:$5:$6")+
      "&enddt="+d.end.replace(/(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)/,"$1-$2-$3T$4:$5:$6")+
      "&body="+encodeURIComponent(d.note)+
      "&location="+encodeURIComponent(d.venue);
    p.innerHTML='<span>Add to calendar</span>'+
      '<a rel="nofollow noopener" target="_blank" href="'+g+'">Google</a>'+
      '<a rel="nofollow noopener" target="_blank" href="'+o+'">Outlook</a>'+
      '<a class="calics" href="#">Download</a>';
    p.querySelector(".calics").addEventListener("click",function(e){
      e.preventDefault();
      var blob=new Blob([ics(d)],{type:"text/calendar"});
      var a=document.createElement("a");
      a.href=URL.createObjectURL(blob);
      a.download=(m.getAttribute("data-date")||"sitting")+".ics";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function(){URL.revokeObjectURL(a.href);},2000);
    });
    box.appendChild(p);
  }

  // ---- wiring ------------------------------------------------------------------------
  fromLocation();
  side.hidden=false; bar.hidden=false;
  app.classList.add("on");
  view.tabIndex=-1;
  // A phone opens on the selected week alone, and the filters shut; a
  // reader's own choice about the month is remembered in this browser.
  var folded=null;
  try{ folded=localStorage.getItem("gr.calendar.fold"); }catch(e){}
  var narrow=!!(window.matchMedia&&window.matchMedia("(max-width:640px)").matches);
  setFold(folded===null?narrow:folded==="1");
  setFilterFold(!!(window.matchMedia&&window.matchMedia("(max-width:1023px)").matches)&&!narrowed(S));
  need(); drawAll();

  grid.addEventListener("click",function(e){
    var td=cellOf(e.target);
    if(!td||td.getAttribute("aria-disabled")) return;
    // The day just chosen is on the panel in full, so the focus the redraw
    // gives its new cell does not open its preview again half a second on.
    hidePeek(); hushD=td.getAttribute("data-d"); select(hushD,"grid");
  });
  grid.addEventListener("keydown",function(e){
    var td=cellOf(e.target);
    if(!td) return;
    var d=td.getAttribute("data-d");
    if(e.key==="Enter"||e.key===" "){
      e.preventDefault();
      if(!td.getAttribute("aria-disabled")) select(d,"key");
      return;
    }
    if(e.key==="Escape"){ hushD=peekD; hidePeek(); return; }
    var n=stepKey(d,e.key,e.shiftKey);
    if(!n) return;
    e.preventDefault();
    n=clamp(n); FOCUS=n;
    // Moving off the week a folded grid shows opens the month again, so the
    // focus never goes somewhere the reader cannot see.
    // Not remembered: the reader asked for a day, not for the month open on
    // every visit. Only the fold's own button changes the default.
    if(side.classList.contains("folded")&&weekKey(n)!==weekKey(SEL)) setFold(false);
    if(month(n)!==VIEWM){ VIEWM=month(n); need(); drawGrid(true); }
    else{
      all(grid,"td[data-d]").forEach(function(x){ x.tabIndex=x.getAttribute("data-d")===n?0:-1; });
      var t=grid.querySelector('td[data-d="'+n+'"]'); if(t) t.focus();
    }
  });
  grid.addEventListener("pointerdown",function(e){ if(e.pointerType==="touch") touchT=Date.now(); });
  grid.addEventListener("pointerover",function(e){
    if(e.pointerType==="touch") return;
    var td=cellOf(e.target); if(td) wantPeek(td.getAttribute("data-d"),"pointer");
  });
  grid.addEventListener("pointerleave",function(){
    clearTimeout(peekT); pendD=null; hushD=null;
    coolT=setTimeout(hidePeek,160);
  });
  grid.addEventListener("focusin",function(e){
    if(Date.now()-touchT<800) return;
    var td=cellOf(e.target); if(td) wantPeek(td.getAttribute("data-d"),"focus");
  });
  grid.addEventListener("focusout",function(e){
    if(e.relatedTarget&&grid.contains(e.relatedTarget)) return;
    // Focus has left the grid, so a preview it asked for and was still
    // waiting on goes too: tabbing through in under half a second left one
    // to open beside a day that no longer had focus, and stay.
    if(pendFrom==="focus"){ clearTimeout(peekT); pendD=null; }
    if(peekFrom==="focus") hidePeek();
  });
  document.addEventListener("keydown",function(e){ if(e.key==="Escape"&&peekD){ hushD=peekD; hidePeek(); } });
  // The preview is placed in the window, so anything that moves the day under
  // it -- the page, or the month's own column scrolling by itself -- puts it away.
  window.addEventListener("scroll",function(){ if(peekD) hidePeek(); },{passive:true});
  side.addEventListener("scroll",function(){ if(peekD) hidePeek(); },{passive:true});

  function turn(n){
    var m=addMonths(VIEWM,n);
    if(m<month(FIRST)||m>LASTMONTH) return;
    VIEWM=m;
    // The month is what was asked for, so a grid folded to one week opens --
    // for now: one tap on an arrow is not a choice about every later visit,
    // so it is not remembered. Only the fold's own button is.
    if(side.classList.contains("folded")) setFold(false);
    need(); drawGrid();
  }
  $("cmprev").addEventListener("click",function(){ turn(-1); });
  $("cmnext").addEventListener("click",function(){ turn(1); });
  $("cmnow").addEventListener("click",function(){ select(clamp(TODAY),"today"); });
  mfold.addEventListener("click",function(){
    var on=!side.classList.contains("folded");
    setFold(on,true);
    // Folded, the grid is the selected week's row, so it shows the month that
    // holds that row: folded over another month it was a row of day names.
    if(on && VIEWM!==month(SEL)){ VIEWM=month(SEL); FOCUS=SEL; need(); drawGrid(); }
  });
  ffold.addEventListener("click",function(){ setFilterFold(!side.classList.contains("ffolded")); });
  $("calskip").addEventListener("click",function(){ view.focus(); view.scrollIntoView({block:"start"}); });

  all(bar,"[data-view]").forEach(function(b){
    b.addEventListener("click",function(){
      var v=b.getAttribute("data-view");
      if(v===S.v) return;
      S.v=v; syncControls(); drawPanel(); commit(true);
    });
  });
  reset.addEventListener("click",function(){
    var v=S.v; S=defaults(); S.v=v;
    try{ localStorage.setItem(SKEY,"1"); }catch(e){}
    cpfind.value=""; drawList(); apply();
    // The control goes away with what it undid; the view switch keeps the
    // reader's place rather than dropping focus on the page.
    (bar.querySelector('[aria-pressed="true"]')||view).focus();
  });
  form.addEventListener("submit",function(e){ e.preventDefault(); });
  form.addEventListener("change",function(e){
    var t=e.target;
    if(t.name==="who"){
      S.who=values("who");
      // A page built without the database copy offers no study box, and a
      // box that is not there cannot have been unticked.
      if(!study) S.who.push("study");
      if(t===study){ try{ localStorage.setItem(SKEY, study.checked?"1":"0"); }catch(e2){} }
    }else if(t.name==="what") S.what=values("what");
    else if(cplist.contains(t)){
      var i=S.picks.indexOf(t.value);
      if(t.checked&&i<0) S.picks.push(t.value);
      if(!t.checked&&i>=0) S.picks.splice(i,1);
    }else return;
    apply();
  });
  all(form,"[data-body]").forEach(function(b){
    b.addEventListener("click",function(){ S.body=b.getAttribute("data-body")||""; apply(); });
  });
  // A quick choice pressed again undoes itself, back to every box ticked.
  all(form,"[data-quick]").forEach(function(b){
    b.addEventListener("click",function(){
      var k=b.getAttribute("data-quick"), on=quickOf(S)===k;
      S.who=on?WHO.slice():QUICK[k].who.slice();
      S.what=on?WHAT.slice():QUICK[k].what.slice();
      S.picks=[];
      apply();
    });
  });
  var findT=0;
  find.addEventListener("input",function(){
    clearTimeout(findT);
    findT=setTimeout(function(){ S.q=find.value; apply(); },150);
  });
  cpfind.addEventListener("focus",loadNames);
  cpfind.addEventListener("input",function(){ loadNames(); drawList(); });
  cpall.addEventListener("click",function(){
    var open=cpall.getAttribute("aria-expanded")!=="true";
    cpall.setAttribute("aria-expanded",open?"true":"false");
    cpall.textContent=open?"Hide the list":"Browse every committee";
    loadNames(); drawList();
  });
  cpchosen.addEventListener("click",function(e){
    var b=e.target.closest&&e.target.closest(".cpchip");
    if(!b) return;
    var i=S.picks.indexOf(b.getAttribute("data-name"));
    if(i>=0) S.picks.splice(i,1);
    apply();
    (cpchosen.querySelector(".cpchip")||cpfind).focus();
  });

  view.addEventListener("toggle",function(e){
    var m=e.target;
    if(m&&m.classList&&m.classList.contains("calmeet")) OPEN[S.v][cardKey(m)]=m.open;
  },true);
  view.addEventListener("click",function(e){
    var b=e.target.closest&&e.target.closest("button");
    if(!b||!view.contains(b)) return;
    if(b.classList.contains("wkday")){
      S.v="day"; syncControls(); select(b.getAttribute("data-d"),"view");
      var hd=view.querySelector(".caldate");
      if(hd){ hd.tabIndex=-1; hd.focus(); }
    }else if(b.hasAttribute("data-step")) select(addDays(SEL,+b.getAttribute("data-step")),"step");
  });
  // The week's arrows move the selection by a week, in place, keeping the
  // view and the filters; opened in a new tab they are plain links still.
  app.addEventListener("click",function(e){
    var a=e.target.closest&&e.target.closest(".wknav a");
    if(!a||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey||e.button) return;
    e.preventDefault();
    if(a.hasAttribute("data-today")) select(clamp(TODAY),"nav");
    else select(addDays(SEL,+a.getAttribute("data-step")||0),"nav");
  });
  window.addEventListener("popstate",function(){
    // A bare fragment -- the skip link's #results -- is not a state, and
    // leaves the reader's filters where they were.
    if(location.hash && !readHash(location.hash)) return;
    hidePeek(); fromLocation(); need(); drawAll(); skipTo();
  });
})();
"""


def week_key(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def monday(d):
    return d - datetime.timedelta(days=d.isoweekday() - 1)


def span_words(a, b):
    """21-27 September 2026, or 29 September - 5 October 2026."""
    if a.month == b.month:
        return f"{a.day}–{b.day} {MONTH[b.month - 1]} {b.year}"
    if a.year == b.year:
        return (f"{a.day} {MONTH[a.month - 1]} – "
                f"{b.day} {MONTH[b.month - 1]} {b.year}")
    return (f"{a.day} {MONTH[a.month - 1]} {a.year} – "
            f"{b.day} {MONTH[b.month - 1]} {b.year}")


def href_for(key, today):
    """Where a week lives. The current one is the tab's own page.

    From the site root, with its slash: shell.page joins this to the domain for
    the page's canonical link and citation, and without it they read
    "https://graniterecord.orgcalendar" on every week until 24 September."""
    return "/calendar.html" if key == week_key(today) else f"/calendar/{key}.html"


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

    code = {}
    cf = site / "committees.json"
    if cf.exists():
        try:
            for c in json.loads(cf.read_text(encoding="utf-8")):
                if c.get("name") and c.get("code"):
                    code[c["name"].strip().lower()] = c["code"]
        except (ValueError, OSError):
            pass

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
        weeks[week_key(d)][date].setdefault(BP.meeting_key(row), []).append(row)
    # A BILL'S ROW AT A STUDY COMMITTEE'S MEETING TAKES THE MEETING'S TIME AND
    # ROOM. The docket gives neither; the database copy's row for the same
    # committee on the same day does, and without this the one card would
    # list the day twice, once untimed.
    for days in weeks.values():
        for day in days.values():
            for key, rs in day.items():
                src = [x for x in rs if x.get("study") and x["what"] != "cancelled"]
                if len(src) != 1:
                    continue
                for x in rs:
                    if (not x.get("study") and x["what"].lower() == "study committee"
                            and not x["time"] and not x["venue"]):
                        x["time"], x["venue"] = src[0]["time"], src[0]["venue"]
    return weeks


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
                body = floors.get(key[1])
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
                             if r.get("bill") else by_name.get((date, _words(key[1]))))
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
    return sorted(day, key=lambda k: (min((r["time"] or "~") for r in day[k]),
                                      k[1]))


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


def day_words(d, today):
    """("Monday 21 September", "in 3 days") -- a day's heading and how far off
    it is from `today`. The page's script writes the second part again in the
    reader's own clock; this is what a reader without script is given."""
    x = datetime.date.fromisoformat(d)
    off = (x - today).days
    # <= 14, as HOME_JS has it: `< 14` left a day exactly a fortnight off
    # with no label at all until the script wrote one.
    rel = ("today" if off == 0 else "tomorrow" if off == 1
           else f"in {off} days" if 0 < off <= 14 else "")
    return f"{DAYNAME[x.weekday()]} {x.day} {MONTH[x.month - 1]}", rel


def week_facts(key, weeks, today):
    """What a week's page says about the week: its span, the days it lists,
    its cards and the lead sentence that counts them.

    One function, because two things say it: the week's own page, and the
    month files the Calendar page's script reads when a reader moves to
    another week -- the heading and the lead it shows then are these."""
    days_raw = weeks[key]
    dated = [d for d in days_raw if days_raw[d]]
    first = monday(datetime.date.fromisoformat(min(dated) if dated
                                               else min(days_raw)))
    last = first + datetime.timedelta(days=6)
    label = span_words(first, last)

    # EVERY WEEKDAY, WITH OR WITHOUT A MEETING. A week listing only the days
    # that held something let a quiet Monday simply vanish, and a reader
    # could not tell a day with nothing on it from a day missing from the
    # page. Monday to Friday are always drawn, an empty one saying so; a
    # Saturday or Sunday only when something is on it, because the General
    # Court does not keep weekends and seven headings over two empty days
    # would be noise.
    shown = sorted(set(dated) | {(first + datetime.timedelta(days=i)).isoformat()
                                 for i in range(5)})
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
    live = {k for k, rows in meets.items() if not BP.is_cancelled(rows)}
    off = len(meets) - len(live)
    busy = sum(1 for v in days.values() if any(k in live for k in v))
    n = sum(1 for v in days.values() for k in v if k in live)
    bills = len({(r["date"], r["bill"]) for k in live for r in meets[k]
                 if r["bill"]})

    # "covering 0 bills" was said of thirty weeks that held only study and
    # statutory committees, which meet on no bill; the clause goes where
    # there is nothing for it to count.
    cancelled = (f" {'One' if off == 1 else off} cancelled meeting"
                 f"{' is' if off == 1 else 's are'} shown as well, and not counted."
                 if off else "")
    if n:
        lead = (f"{n} sitting{'' if n == 1 else 's'} on {busy} "
                f"day{'' if busy == 1 else 's'}"
                + (f", covering {bills:,} bill{'' if bills == 1 else 's'}"
                   if bills else "")
                + ". A committee appears once a day, however many times it "
                "sat; open one for its items in order." + cancelled)
    elif off:
        lead = ("The one meeting set for this week was cancelled."
                if off == 1 else
                f"All {off} meetings set for this week were cancelled.")
    else:
        # In the tense of the week: a week that is over has nothing on the
        # record, and one still to come has nothing scheduled yet -- "yet",
        # because the study committees are read from a dated copy.
        lead = (("No meetings are on the record for this week. " if last < today
                 else "No meetings are scheduled yet for this week. ")
                + "The General Court sits from January to June, and committees "
                "meet on bills from the autumn filing period onwards.")
    return {"first": first, "last": last, "label": label, "days": days,
            "meets": meets, "n": n, "lead": lead}


# ---- the Calendar page's controls -------------------------------------------
#
# ALL OF IT IS EMITTED HIDDEN AND THE SCRIPT UNHIDES IT, as the week's filter
# always was. A reader without script gets the week as a list, which is the
# whole answer to no filter at all; a control that does nothing is worse than
# no control.
#
# WHO AND WHAT ARE TWO QUESTIONS, and the form asks them as two. The person's
# description on 24 September 2026 named five ways to narrow the schedule --
# everything with the study committees, standing committees only, public
# hearings, one committee, or any combination -- and those are one choice of
# who is meeting and one of what kind of sitting it is, taken together. A card
# holding several kinds matches when any of its items does, and stays whole.
# The floor is not a kind of COMMITTEE meeting, so the "what" boxes say
# nothing about it; the "who" box for it does.
#
# Choosing committees by name REPLACES the "who" boxes rather than narrowing
# them: somebody who picks the Commission on Aging wants that commission, and
# an unticked "study and statutory" box hiding it would read as a fault. The
# form says so while any are chosen.
WHAT_BOXES = (("hearing", "k-hearing", "Public hearings"),
              ("exec", "k-exec", "Executive sessions"),
              ("work", "k-meet", "Work sessions and other meetings"),
              ("conf", "k-conf", "Committees of conference"))


def side_html(study_note):
    """The month grid's frame and the filters, down the left of the page.

    The grid's days are the script's to draw -- which of them is today, and
    so which are past, is the reader's clock and not the build's -- so the
    table is emitted empty. `study_note` empty means the database copy was
    not on disk, and then the page offers no box for committees it lacks.
    """
    find = ('<label class="wkfind" for="wkfind">Bill or committee'
            '<input type="search" id="wkfind" autocomplete="off" '
            'placeholder="HB 1234, or Judiciary"></label>')
    # The two combinations the person named, a click each; they set the
    # boxes below, which remain the whole of the model.
    quick = ('<div class="wkchips calquick" role="group" aria-label="Quick choices">'
             '<button type="button" data-quick="standing" aria-pressed="false">'
             'Standing committees only</button>'
             '<button type="button" data-quick="hearing" aria-pressed="false">'
             'Public hearings only</button></div>')
    # ON UNLESS THE READER TURNS IT OFF, and the script remembers which. With
    # no script the whole week is shown, which is every box's default anyway.
    who = ('<fieldset class="calfs"><legend>Who is meeting</legend>'
           '<label class="calchk"><input type="checkbox" name="who" value="standing" '
           'checked>Standing committees and committees of conference</label>'
           + ('<label class="calchk" for="wkstudy"><input type="checkbox" id="wkstudy" '
              'checked name="who" value="study">Study and statutory committees</label>'
              if study_note else "")
           + '<label class="calchk"><input type="checkbox" name="who" value="floor" '
           'checked>Floor sessions of the House and Senate</label>'
           '<p class="calhint" id="whohint" hidden>Showing only the committees '
           'chosen below.</p></fieldset>')
    pick = ('<fieldset class="calfs cpick"><legend>Only these committees</legend>'
            '<div class="cpchosen" id="cpchosen"></div>'
            '<label class="wkfind" for="cpfind">Find a committee'
            '<input type="search" id="cpfind" autocomplete="off" '
            'placeholder="Name of a committee" aria-controls="cplist"></label>'
            '<button type="button" class="cpall" id="cpall" aria-expanded="false" '
            'aria-controls="cplist">Browse every committee</button>'
            '<div class="cplist" id="cplist" role="group" '
            'aria-label="Committees to show" hidden></div>'
            '<p class="calhint" id="cpstat" role="status" aria-live="polite"></p>'
            '</fieldset>')
    what = ('<fieldset class="calfs"><legend>What kind of committee meeting</legend>'
            + "".join(f'<label class="calchk"><input type="checkbox" name="what" '
                      f'value="{v}" checked><i class="{c}" aria-hidden="true"></i>'
                      f'{S.E(w)}</label>' for v, c, w in WHAT_BOXES)
            # Said where the boxes are, because ticking only Public hearings
            # and still seeing the House sit reads as a fault otherwise.
            + '<p class="calhint">A floor session is not a committee meeting: '
            'show or hide it under Who is meeting.</p>'
            + '</fieldset>')
    chamber = ('<fieldset class="calfs"><legend>Chamber</legend><div class="wkchips">'
               '<button type="button" data-body="" aria-pressed="true">Both chambers</button>'
               '<button type="button" data-body="H" aria-pressed="false">House</button>'
               '<button type="button" data-body="S" aria-pressed="false">Senate</button>'
               '</div></fieldset>')
    return ('<div class="calside" id="calside" hidden>'
            # Past the month and the filters to the schedule, which is a long
            # run of tab stops to cross by keyboard. A button, because it only
            # exists with the script, and a fragment link on a page carrying
            # <base href="/"> would go to the home page.
            '<button type="button" class="calskip" id="calskip">Skip to the schedule</button>'
            '<section class="calmonth" aria-labelledby="cmtitle">'
            '<div class="cmhead"><h2 class="cmtitle" id="cmtitle" aria-live="polite"></h2>'
            '<button type="button" class="cmbtn" id="cmprev" '
            'aria-label="The month before">&lsaquo;</button>'
            '<button type="button" class="cmbtn" id="cmnext" '
            'aria-label="The month after">&rsaquo;</button>'
            '<button type="button" class="cmbtn cmnowb" id="cmnow">Today</button></div>'
            '<table class="cmgrid" id="cmgrid" role="grid" aria-labelledby="cmtitle"></table>'
            '<button type="button" class="calfold" id="cmfold" aria-expanded="true" '
            'aria-controls="cmgrid">Show only this week</button>'
            '</section>'
            '<section class="calfilt" aria-labelledby="wkfhead">'
            '<div class="cfhead"><h2 id="wkfhead">Filter the calendar</h2>'
            '<button type="button" class="calfold" id="cffold" aria-expanded="true" '
            'aria-controls="wkfilter">Hide the filters</button></div>'
            '<form class="wkfilter" id="wkfilter" role="search" aria-labelledby="wkfhead">'
            + find + quick + who + pick + what + chamber
            + '</form></section></div>')


# The view switch, the count and the one control that undoes every filter,
# together above the schedule they act on.
BAR_HTML = ('<div class="calbar" id="calbar" hidden>'
            '<div class="calviews" role="group" aria-label="Show the schedule as">'
            '<button type="button" data-view="list" aria-pressed="true">List</button>'
            '<button type="button" data-view="week" aria-pressed="false">Week</button>'
            '<button type="button" data-view="day" aria-pressed="false">Day</button>'
            '</div>'
            '<p class="wkcount" id="wkcount" role="status" aria-live="polite"></p>'
            '<button type="button" class="calreset" id="calreset" hidden>'
            'Show everything</button></div>')


def week_page(site, base, key, weeks, order, at, titles, years, code, urls,
              today, sessions=frozenset(), study_note="", docs=None):
    """Write one week's page. `study_note` says where the study and
    statutory committee meetings come from; empty when there are none, and
    then neither the toggle nor the description mentions them."""
    w = week_facts(key, weeks, today)
    label, lead, days, meets, n = w["label"], w["lead"], w["days"], w["meets"], w["n"]

    # level=2: the h1 of this page is the week itself, so a day is the
    # section under it. On the home page the days sit under "Coming up"
    # and stay h3.
    body, _missing = BP.cal_days(days, meets, titles, years, code,
                                 lambda d: day_words(d, today), S.E,
                                 level=2, sessions=sessions, docs=docs)

    nav = []
    if at > 0:
        nav.append(f'<a class="wkprev" href="{S.canon(href_for(order[at - 1], today))}">'
                   f'&lsaquo; The week before</a>')
    here = week_key(today)
    if key != here and here in order:
        nav.append(f'<a class="wkhere" href="{S.canon("/calendar.html")}">This week</a>')
    if at < len(order) - 1:
        nav.append(f'<a class="wknext" href="{S.canon(href_for(order[at + 1], today))}">'
                   f'The week after &rsaquo;</a>')

    path = href_for(key, today)
    # THE CURRENT WEEK IS WRITTEN AT BOTH ITS ADDRESSES. /calendar is the tab,
    # and /calendar/2026-W39 is the address somebody was sent last week as
    # "next week". Leaving the dated file to the build that wrote it then was
    # how it went stale: its "week before" link pointed back at /calendar,
    # which was the same week. The copy is rewritten on every build and names
    # /calendar as the page it copies, so there is one page to index.
    copies = [path] + ([f"/calendar/{key}.html"] if path == "/calendar.html" else [])
    # THE KEY TO THE COLOURS, which are the General Court's own for each kind
    # of meeting. On every week, empty ones included, so the page reads the
    # same wherever a reader lands.
    key_html = ('<ul class="calkey" aria-label="What the colours mean">'
                + "".join(f'<li><i class="{c}" aria-hidden="true"></i>{S.E(w)}</li>'
                          for c, w in BP.MEET_LEGEND)
                + "</ul>")
    # THE PAGE IS THE WEEK AS A LIST, AND THE SCRIPT MAKES IT A CALENDAR.
    # Without script this reads exactly as it did: the week's heading, its
    # lead, the arrows, the key and every day in order. With it, the month
    # grid and the filters come up down the left and the list becomes one of
    # three views over the same cards. The attributes are what the script
    # needs to know about the page it is on: which week it holds, which week
    # the build called this one, and the first and last weeks there are.
    block = ('<div id="results">'
             f'<div class="wkpage calapp" id="calapp" data-week="{key}" '
             f'data-here="{here}" data-first="{order[0]}" data-last="{order[-1]}">'
             '<div class="calhead">'
             f'<h1>The week of {S.E(label)}</h1>'
             f'<p class="src">{lead}</p>'
             f'<nav class="wknav" aria-label="Other weeks">{"".join(nav)}</nav>'
             '</div>'
             + side_html(study_note)
             + '<div class="calmain">'
             + BAR_HTML
             + key_html
             + (f'<p class="src calsrc">{S.E(study_note)}</p>' if study_note else "")
             + f'<div class="calview" id="calview">{body}</div>'
             f'<nav class="wknav wkfoot" aria-label="Other weeks">{"".join(nav)}</nav>'
             '</div>'
             # The hover preview: one element, placed beside whichever day
             # it describes, so it never covers the day being read.
             '<div class="calpeek" id="calpeek" role="tooltip" hidden></div>'
             "</div></div>"
             # Inline in the body, which is where every other page-specific
             # script on this site lives -- shell.page takes no script -- and
             # without its comment lines, which stay here for the reader of
             # the source rather than travelling with 103 pages.
             f"<script>{lean_js(WEEK_JS)}</script>")
    for f in copies:
        html = S.page(S.template(site), path=f, canonical=path, base=base,
                      title=f"The week of {label} | Granite Record",
                      # WHAT THE PAGE HOLDS, and no more: it said "Every
                      # hearing..." while it held bill business only.
                      description=("Hearings, work sessions, executive sessions, "
                                   "floor sittings"
                                   + (" and study and statutory committee meetings"
                                      if study_note else "")
                                   + f" of the New Hampshire General Court, {label}."),
                      og_title=f"The week of {label}",
                      globals={"GR_STATIC": True}, noscript="",
                      skip_label="Skip to the week", sr_title="", og_type="website",
                      nav_current="calendar.html",
                      jsonld=LD.listing(f"The week of {label}",
                                        f"The General Court's business, {label}.",
                                        base, S.canon(path)))
        html = html.replace('<div id="results"></div>', block, 1)
        assert '<div class="wkpage calapp"' in html, f"{f}: the template has no results slot"
        out = site / f.lstrip("/")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
    urls.append(base + S.canon(path))
    return n


def lean_js(js):
    """The script without its whole-line comments or its indentation, for
    the page to carry. Safe because no string in WEEK_JS spans a line."""
    return "\n".join(ln.strip() for ln in js.splitlines()
                     if ln.strip() and not ln.lstrip().startswith("//"))


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
                sessions=frozenset(), docs=None):
    """Write calendar/data/<YYYY-MM>.json for every month the weeks in `order`
    touch, and calendar/data/committees.json; take out any other .json there.

    Returns (months written, cards written)."""
    out = Path(site).joinpath(*DATA_DIR)
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
            html, _m = BP.cal_days({iso: in_order(day)}, day, titles, years, code,
                                   lambda dd: day_words(dd, today), S.E, level=2,
                                   sessions=sessions, docs=docs)
            days[iso] = html
            cards += len(day)
            if k in weeks and k not in wk:
                if k not in facts:
                    f = week_facts(k, weeks, today)
                    facts[k] = {"label": f["label"], "lead": f["lead"]}
                wk[k] = facts[k]
        name = f"{ym}.json"
        (out / name).write_text(json.dumps({"month": ym, "days": days, "weeks": wk},
                                           ensure_ascii=False, separators=(",", ":")),
                                encoding="utf-8")
        wrote.add(name)

    # EVERY COMMITTEE ON THE CALENDAR, for the picker: its name as the cards
    # print it, whose it is, and its chamber or chambers. Read once, and only
    # when a reader goes looking for a committee.
    agg = {}
    for k in order:
        for _date, day in (weeks.get(k) or {}).items():
            for (_d, name), rows in day.items():
                a = agg.setdefault(name, [Counter(), set()])
                a[0][BP.meeting_who(name, rows)] += 1
                a[1].update((r.get("body") or "").strip().upper() for r in rows
                            if (r.get("body") or "").strip())
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
    weeks, titles, years, code = collect(site, study_rows)
    # SILENCE IS NOT SUCCESS: no weeks is a Calendar tab pointing at nothing,
    # and a build that said so only by printing a zero.
    assert weeks, f"no proceedings dated {FROM} or later; the calendar would be empty"
    study_note = ""
    if study_rows:
        when = fetched
        try:
            x = datetime.date.fromisoformat(fetched)
            when = f"{x.day} {MONTH[x.month - 1]} {x.year}"
        except ValueError:
            pass
        study_note = ("Study and statutory committee meetings come from the "
                      "General Court's own database, as copied on "
                      f"{when or 'an unrecorded date'}. Nothing has refreshed "
                      "that copy since, so a meeting set, moved or cancelled "
                      "after that date is not shown here.")

    today = datetime.date.today()
    here = week_key(today)
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
    urls, total = [], 0
    for i, key in enumerate(order):
        total += week_page(site, base, key, weeks, order, i,
                           titles, years, code, urls, today, sits,
                           study_note=study_note, docs=docs)

    # THE MONTH FILES, which the page's month grid and its other weeks read.
    # SILENCE IS NOT SUCCESS: a run that wrote weeks and no months is a
    # calendar whose grid shows nothing, so it says how many and stops if none.
    n_months, n_cards = month_files(site, weeks, order, titles, years, code,
                                    today, sits, docs)
    assert n_months, "no month files were written; the calendar's grid would be empty"
    print(f"  {n_months} month files -> calendar/data/ ({n_cards:,} cards, "
          "the same ones the week pages draw), and committees.json for the picker")

    # Every week is rebuilt on every run, so a calendar address in the sitemap
    # that this run did not write -- the current week's dated copy, a week
    # that no longer has a proceeding -- is taken out, not left beside the rest.
    added, dropped = S.sitemap_merge(site, base, urls, "/calendar")
    if added or dropped:
        print(f"  sitemap.xml: {added} added, {dropped} no longer written taken out")

    print(f"  {len(order)} weeks -> calendar.html and calendar/ "
          f"({total:,} sittings; {here} is this week; {empty} weeks with "
          f"nothing on them written as pages of their own)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
