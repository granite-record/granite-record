#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.10
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

WHAT IS NOT HERE. proceedings.csv is keyed on bills, so this shows bill
business only. The General Court's own schedule also lists study committees,
boards and commissions sitting with no bill before them -- the Assessing
Standards Board, the Mount Washington Commission -- and none of those appear.
"""

import argparse
import datetime
import json
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
  var days=[].slice.call(document.querySelectorAll(".calday"));
  var count=document.getElementById("wkcount");
  var find=document.getElementById("wkfind");
  var chips=[].slice.call(form.querySelectorAll("[data-body]"));
  var body="";

  // "HB 1234", "hb1234" and "1234" all mean the same bill to a person typing
  // it, and none of them is what the attribute holds.
  function norm(s){ return String(s||"").toUpperCase().replace(/[^A-Z0-9]/g,""); }

  function matches(m,q){
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

  function apply(){
    var q=(find.value||"").trim(), shown=0;
    meets.forEach(function(m){
      var ok=matches(m,q);
      m.hidden=!ok;
      if(ok)shown++;
    });
    // A day with nothing left in it is not an empty day, it is a day the
    // filter excluded -- so it goes too, rather than standing as a heading
    // over nothing.
    days.forEach(function(d){
      var any=d.querySelector(".calmeet:not([hidden])");
      d.hidden=!any;
    });
    if(shown===meets.length){
      count.textContent=meets.length+" sitting"+(meets.length===1?"":"s")+" this week.";
    }else if(shown===0){
      count.textContent="Nothing this week matches. "+
        "The General Court sits from January to June.";
    }else{
      count.textContent=shown+" of "+meets.length+" sittings shown.";
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
    if(!date) return null;
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


def collect(site):
    """{week: {date: {meeting_key: [rows]}}}, plus the lookups a card needs."""
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

    return weeks_from(proceedings.load()), titles, years, code


def weeks_from(rows):
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
    for r in rows:
        date = (r.get("date") or "")[:10]
        if date < FROM:
            continue
        try:
            d = datetime.date.fromisoformat(date)
        except ValueError:
            continue
        cmte = (r.get("committee") or "").strip()
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
        weeks[week_key(d)][date].setdefault(BP.meeting_key(row), []).append(row)
    return weeks


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
              today, sessions=frozenset()):
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

    meets, days = {}, OrderedDict()
    for date in sorted(dated):
        for k, rows in days_raw[date].items():
            meets[k] = rows
        days[date] = in_order(days_raw[date])

    # level=2: the h1 of this page is the week itself, so a day is the
    # section under it. On the home page the days sit under "Coming up"
    # and stay h3.
    body, _missing = BP.cal_days(days, meets, titles, years, code, when, S.E,
                                 level=2, sessions=sessions)

    n = sum(len(v) for v in days.values())
    bills = len({(r["date"], r["bill"]) for rows in meets.values()
                 for r in rows if r["bill"]})

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

    if n:
        lead = (f"{n} sitting{'' if n == 1 else 's'} on {len(days)} "
                f"day{'' if len(days) == 1 else 's'}, covering {bills:,} "
                f"bill{'' if bills == 1 else 's'}. A committee appears once a day, "
                "however many times it sat; open one for its items in order.")
    else:
        lead = ("Nothing sat this week. The General Court sits from January to "
                "June, and committees meet on bills from the autumn filing "
                "period onwards.")

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
            '<p class="wkcount" id="wkcount" role="status" aria-live="polite"></p>'
            '</form>')
    block = ('<div id="results"><div class="wkpage">'
             f'<h1>The week of {S.E(label)}</h1>'
             f'<p class="src">{lead}</p>'
             f'<nav class="wknav" aria-label="Other weeks">{"".join(nav)}</nav>'
             f'{filt}'
             f'{body}'
             f'<nav class="wknav wkfoot" aria-label="Other weeks">{"".join(nav)}</nav>'
             "</div></div>"
             # Inline in the body, which is where every other page-specific
             # script on this site lives -- shell.page takes no script, and a
             # separate file for forty lines would be a request per week page.
             f"<script>{WEEK_JS}</script>")
    for f in copies:
        html = S.page(S.template(site), path=f, canonical=path, base=base,
                      title=f"The week of {label} | Granite Record",
                      description=("Every hearing, work session, executive session and "
                                   f"floor sitting of the New Hampshire General Court, "
                                   f"{label}."),
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

    weeks, titles, years, code = collect(site)
    # SILENCE IS NOT SUCCESS: no weeks is a Calendar tab pointing at nothing,
    # and a build that said so only by printing a zero.
    assert weeks, f"no proceedings dated {FROM} or later; the calendar would be empty"

    today = datetime.date.today()
    here = week_key(today)
    if here not in weeks:
        # Out of session the current week holds nothing, and the tab still has
        # to open on it rather than on whenever the House last sat.
        weeks[here][today.isoformat()] = OrderedDict()
    order = sorted(weeks)

    sits = sitting_pages(site)
    print(f"  {len(sits):,} sitting pages on disk to link to")
    urls, total = [], 0
    for i, key in enumerate(order):
        total += week_page(site, base, key, weeks, order, i,
                           titles, years, code, urls, today, sits)

    # Every week is rebuilt on every run, so a calendar address in the sitemap
    # that this run did not write -- the current week's dated copy, a week
    # that no longer has a proceeding -- is taken out, not left beside the rest.
    added, dropped = S.sitemap_merge(site, base, urls, "/calendar")
    if added or dropped:
        print(f"  sitemap.xml: {added} added, {dropped} no longer written taken out")

    print(f"  {len(order)} weeks -> calendar.html and calendar/ "
          f"({total:,} sittings; {here} is this week)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
