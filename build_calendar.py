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
from collections import OrderedDict, defaultdict
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


# THE FILTER RUNS IN THE READER'S BROWSER, AND THE PAGE IS WHOLE WITHOUT IT.
# Every card is already in the HTML with its chamber, committee and bills on
# it, so this hides and shows what is there rather than fetching or rebuilding
# anything. The controls are emitted `hidden` and this is what unhides them:
# a reader with no script never sees a dead control, and what they get -- the
# entire week, unfiltered -- is the correct answer to no filter at all.
WEEK_JS = r"""
(function(){
  var form=document.getElementById("wkfilter");
  if(!form)return;
  form.hidden=false;
  var meets=[].slice.call(document.querySelectorAll(".calmeet"));
  // A day with no meeting at all says so and stays, whatever the filter:
  // "No meetings scheduled" is true of it under every filter there is.
  var days=[].slice.call(document.querySelectorAll(".calday:not(.calnone)"));
  var count=document.getElementById("wkcount");
  var find=document.getElementById("wkfind");
  var chips=[].slice.call(form.querySelectorAll("[data-body]"));
  var body="";

  // "HB 1234", "hb1234" and "1234" all mean the same bill to a person typing
  // it, and none of them is what the attribute holds.
  function norm(s){ return String(s||"").toUpperCase().replace(/[^A-Z0-9]/g,""); }

  // STUDY AND STATUTORY COMMITTEES, on unless the reader turned them off
  // here before. The choice is a convenience kept in this browser; storage
  // that is blocked or empty leaves the default, which is on.
  var study=document.getElementById("wkstudy");
  var SKEY="gr.calendar.study";
  if(study){
    try{ if(localStorage.getItem(SKEY)==="0") study.checked=false; }catch(e){}
    study.addEventListener("change",function(){
      try{ localStorage.setItem(SKEY, study.checked?"1":"0"); }catch(e){}
      apply();
    });
  }

  function matches(m,q){
    if(study && !study.checked && m.hasAttribute("data-study")) return false;
    if(body && (m.getAttribute("data-body")||"").indexOf(body)<0) return false;
    if(!q) return true;
    var c=(m.getAttribute("data-cmte")||"");
    if(c.indexOf(q.toLowerCase())>=0) return true;
    var n=norm(q);
    if(!n) return false;
    var bills=(m.getAttribute("data-bills")||"").split(" ");
    for(var i=0;i<bills.length;i++){ if(norm(bills[i]).indexOf(n)===0) return true; }
    return false;
  }

  // A CANCELLED MEETING IS SHOWN AND NOT COUNTED, as the lead above counts:
  // "22 sittings" of a week in which 21 met was a wrong number.
  function sat(m){ return !m.hasAttribute("data-cancelled"); }
  var total=meets.filter(sat).length;

  function apply(){
    var q=(find.value||"").trim(), shown=0, seen=0;
    meets.forEach(function(m){
      var ok=matches(m,q);
      m.hidden=!ok;
      if(ok){ seen++; if(sat(m)) shown++; }
    });
    // A day with nothing left in it is not an empty day, it is a day the
    // filter excluded -- so it goes too, rather than standing as a heading
    // over nothing.
    days.forEach(function(d){
      var any=d.querySelector(".calmeet:not([hidden])");
      d.hidden=!any;
    });
    if(shown===total){
      count.textContent=total+" sitting"+(total===1?"":"s")+" this week.";
    }else if(seen===0){
      count.textContent="Nothing this week matches. "+
        "The General Court sits from January to June.";
    }else{
      count.textContent=shown+" of "+total+" sittings shown.";
    }
  }

  chips.forEach(function(b){
    b.addEventListener("click",function(){
      body=(b.getAttribute("data-body")||"");
      chips.forEach(function(x){
        x.setAttribute("aria-pressed", x===b ? "true":"false"); });
      apply();
    });
  });
  find.addEventListener("input",apply);
  form.addEventListener("submit",function(e){e.preventDefault();apply();});

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
  meets.forEach(function(m){
    var d=details(m);
    if(!d) return;
    var box=m.querySelector(".calbody");
    if(!box) return;
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
  });

  apply();
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


def week_page(site, base, key, weeks, order, at, titles, years, code, urls,
              today, sessions=frozenset(), study_note="", docs=None):
    """Write one week's page. `study_note` says where the study and
    statutory committee meetings come from; empty when there are none, and
    then neither the toggle nor the description mentions them."""
    days_raw = weeks[key]
    dated = [d for d in days_raw if days_raw[d]]
    first = monday(datetime.date.fromisoformat(min(dated) if dated
                                               else min(days_raw)))
    last = first + datetime.timedelta(days=6)
    label = span_words(first, last)

    def when(d):
        x = datetime.date.fromisoformat(d)
        off = (x - today).days
        # <= 14, as HOME_JS has it: `< 14` left a day exactly a fortnight off
        # with no label at all until the script wrote one.
        rel = ("today" if off == 0 else "tomorrow" if off == 1
               else f"in {off} days" if 0 < off <= 14 else "")
        return f"{DAYNAME[x.weekday()]} {x.day} {MONTH[x.month - 1]}", rel

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

    # level=2: the h1 of this page is the week itself, so a day is the
    # section under it. On the home page the days sit under "Coming up"
    # and stay h3.
    body, _missing = BP.cal_days(days, meets, titles, years, code, when, S.E,
                                 level=2, sessions=sessions, docs=docs)

    n = sum(1 for v in days.values() for k in v if k in live)
    bills = len({(r["date"], r["bill"]) for k in live for r in meets[k]
                 if r["bill"]})

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

    path = href_for(key, today)
    # THE CURRENT WEEK IS WRITTEN AT BOTH ITS ADDRESSES. /calendar is the tab,
    # and /calendar/2026-W39 is the address somebody was sent last week as
    # "next week". Leaving the dated file to the build that wrote it then was
    # how it went stale: its "week before" link pointed back at /calendar,
    # which was the same week. The copy is rewritten on every build and names
    # /calendar as the page it copies, so there is one page to index.
    copies = [path] + ([f"/calendar/{key}.html"] if path == "/calendar.html" else [])
    # HIDDEN UNTIL THE SCRIPT UNHIDES IT. A control that does nothing is worse
    # than no control, and this page is whole without one: every card is in the
    # HTML already.
    filt = ('<form class="wkfilter" id="wkfilter" role="search" hidden>'
            '<div class="wkchips" role="group" aria-label="Which chamber">'
            '<button type="button" data-body="" aria-pressed="true">Both chambers</button>'
            '<button type="button" data-body="H" aria-pressed="false">House</button>'
            '<button type="button" data-body="S" aria-pressed="false">Senate</button>'
            '</div>'
            '<label class="wkfind" for="wkfind">Committee or bill'
            '<input type="search" id="wkfind" autocomplete="off" '
            'placeholder="Judiciary, or HB 1234"></label>'
            # ON UNLESS THE READER TURNS IT OFF, and the script remembers
            # which. With no script the whole week is shown, which is the
            # toggle's default anyway.
            + ('<label class="wktoggle" for="wkstudy">'
               '<input type="checkbox" id="wkstudy" checked>'
               'Show study and statutory committees</label>' if study_note else "")
            + '<p class="wkcount" id="wkcount" role="status" aria-live="polite"></p>'
            '</form>')
    # THE KEY TO THE COLOURS, which are the General Court's own for each kind
    # of meeting. On every week, empty ones included, so the page reads the
    # same wherever a reader lands.
    key_html = ('<ul class="calkey" aria-label="What the colours mean">'
                + "".join(f'<li><i class="{c}" aria-hidden="true"></i>{S.E(w)}</li>'
                          for c, w in BP.MEET_LEGEND)
                + "</ul>")
    block = ('<div id="results"><div class="wkpage">'
             f'<h1>The week of {S.E(label)}</h1>'
             f'<p class="src">{lead}</p>'
             f'<nav class="wknav" aria-label="Other weeks">{"".join(nav)}</nav>'
             f'{filt}'
             f'{key_html}'
             + (f'<p class="src calsrc">{S.E(study_note)}</p>' if study_note else "")
             + f'{body}'
             f'<nav class="wknav wkfoot" aria-label="Other weeks">{"".join(nav)}</nav>'
             "</div></div>"
             # Inline in the body, which is where every other page-specific
             # script on this site lives -- shell.page takes no script, and a
             # separate file for forty lines would be a request per week page.
             f"<script>{WEEK_JS}</script>")
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
        assert '<div class="wkpage">' in html, f"{f}: the template has no results slot"
        out = site / f.lstrip("/")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
    urls.append(base + S.canon(path))
    return n


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
