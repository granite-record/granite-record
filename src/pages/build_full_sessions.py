#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-10.1
"""
The House and the Senate full sessions at the top of the Committees page.

    python3 src/pages/build_full_sessions.py --site site

The person, 9 October 2026 (round two, v12 and v13): "the House and the
Senate full sessions listed at the top of the Committees page, each letting a
reader go through that chamber's session days in one place, as a committee
page shows its meetings", and "a committee's meetings (and the chambers'
session days) can be sorted oldest to newest or newest to oldest".

So each chamber gets a column at the head of /committees: its session days of
the latest term, newest first, each a fold like a committee's meeting -- the
day, how many bills and roll calls, and, opened, the day's own page, its
journal, and every bill it voted on with each vote in order -- a term picker
for every earlier term, and the order either way. The days and their counts
are written into the page here; the bills and votes come from the term's
file, site/session/<H|S>/<term>.json, which the script fetches the first time
a day of that term is opened, so the page carries no term's whole record.

WHY A STEP OF ITS OWN, AFTER THE SESSION PAGES. The term files are written by
build_session_pages (write_term_records), which runs after build_committees,
so the committees step cannot read them on a build into an empty site --
GitHub's nightly -- and would draw the chambers from last night's files on the
laptop and from nothing on the night: the trap the home page's Committees card
fell into (13c674b). build_committees writes an empty slot
(<div id="fullsess"></div><!-- /fullsess -->) and this fills it, between the
same two marks, so running it again redraws rather than doubles it. Where the
slot or the term files are missing it says so and leaves the page as it is.

Reads site/session/days.json and site/session/<H|S>/<term>.json; writes
site/committees.html. Asks nobody anything.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import html as _html
import json
import re

from components import date_words

E = lambda s: _html.escape(str(s or ""), quote=True)  # noqa: E731
SLOT = re.compile(r'<div id="fullsess">.*?</div><!-- /fullsess -->', re.S)
CHAMBER = {"H": "House", "S": "Senate"}
JOURNAL = {"HJ": "House Journal", "SJ": "Senate Journal"}


def plural(n, word):
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def journal_words(j):
    """"HJ 5" -> "House Journal 5"."""
    m = re.match(r"^(HJ|SJ)\s*0*(\d+)", str(j or ""))
    return f"{JOURNAL[m.group(1)]} {m.group(2)}" if m else str(j or "")


def meta(day):
    """What the fold's head says of a day: its bills and its roll calls."""
    c = day.get("counts") or {}
    bits = []
    if c.get("bills"):
        bits.append(plural(c["bills"], "bill"))
    if c.get("roll_calls"):
        bits.append(plural(c["roll_calls"], "roll call"))
    return " &middot; ".join(bits)


def day_fold(body, term, day):
    """One session day as a fold: the day and its counts; opened, its own
    page and its journal, and a slot the script fills with its bills."""
    d = day["date"]
    links = [f'<a href="session/{body}/{E(d)}.html">Open this session day</a>']
    if day.get("journal_url"):
        links.append(f'<a href="{E(day["journal_url"])}">'
                     f'{E(journal_words(day.get("journal")))} (PDF)</a>')
    return (f'<li><details class="fsday" data-date="{E(d)}"><summary>'
            f'<span class="fsd">{E(date_words(d, "long"))}</span>'
            f'<span class="fsm">{meta(day)}</span></summary>'
            f'<div class="fsbody"><p class="fslinks">{" &middot; ".join(links)}</p>'
            f'<div class="fsbills" data-load="{body}|{E(term)}|{E(d)}">'
            '<p class="fsnote">The bills it voted on, and every vote, are on the '
            "session day&rsquo;s own page.</p></div></div></details></li>")


def chamber(body, dates, site):
    """A chamber's column: its heading, how many days, the term picker and
    the order, and its latest term's days, newest first."""
    # The terms are the files build_session_pages wrote, named by the term
    # each day is filed under there; nothing here works a term out again.
    terms = sorted((f.stem for f in (site / "session" / body).glob("*.json")
                    if re.fullmatch(r"\d{4}-\d{4}", f.stem)), reverse=True)
    if not terms or not dates:
        return ""
    latest = terms[0]
    f = site / "session" / body / f"{latest}.json"
    try:
        days = json.loads(f.read_text(encoding="utf-8")).get("days") or []
    except (OSError, ValueError):
        days = []
    if not days:
        return ""
    word = CHAMBER[body]
    first = min(dates)
    opts = "".join(f'<option value="{E(t)}"{" selected" if t == latest else ""}>'
                   f'{E(t.replace("-", chr(8211)))}</option>' for t in terms)
    folds = "".join(day_fold(body, latest, d) for d in reversed(days))
    return (f'<section class="fschamber" data-body="{body}" aria-labelledby="fs-{body}">'
            f'<h3 id="fs-{body}">{word} Session Days</h3>'
            f'<p class="fscount" aria-live="polite">{plural(len(days), "session day")} in '
            f'{E(latest.replace("-", chr(8211)))} &middot; {len(dates):,} since '
            f'{first[:4]}</p>'
            f'<div class="fsctl" hidden>'
            f'<label>Term <select class="fsterm">{opts}</select></label>'
            f'<label>Order <select class="fssort"><option value="new" selected>Newest first'
            f'</option><option value="old">Oldest first</option></select></label></div>'
            # A BOX OF ITS OWN HEIGHT, as Coming Up's week is on the home page:
            # a term is thirty to forty days, and the committees are below.
            # A box that scrolls is a stop for the keyboard, named.
            f'<div class="fsbox" role="region" tabindex="0" aria-label="{word} session days">'
            f'<ol class="fsdays">{folds}</ol></div></section>')


def block(site):
    site = Path(site)
    try:
        listed = json.loads((site / "session" / "days.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "", "no site/session/days.json"
    cols = [chamber(b, sorted(listed.get(b) or []), site) for b in ("H", "S")]
    cols = [c for c in cols if c]
    if not cols:
        return "", "no chamber's term file under site/session"
    return ('<div id="fullsess"><section class="fullsess" aria-labelledby="fs-h">'
            '<h2 id="fs-h">Full Sessions</h2>'
            '<p class="src fill">Each chamber meeting as a whole, on its session days: '
            "what it voted on and how, day by day, as a committee&rsquo;s page lists its "
            "meetings.</p>"
            f'<div class="ctwo">{"".join(cols)}</div></section>{SCRIPT}'
            "</div><!-- /fullsess -->"), ""


# THE SCRIPT: the term picker, the order, and a day's bills when it opens.
# It draws only from the term's own file, and a day it cannot load keeps the
# line that sends the reader to the day's page.
SCRIPT = """<script>
(function(){
  var cache={};
  function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
  function load(b,t){
    if(!cache[b+t])cache[b+t]=fetch("/session/"+b+"/"+t+".json")
      .then(function(r){if(!r.ok)throw new Error(r.status);return r.json();});
    return cache[b+t];
  }
  function plural(n,w){return n.toLocaleString("en-US")+" "+w+(n===1?"":"s");}
  function vote(v){
    var n=(v.yeas!=null&&v.nays!=null)?", "+v.yeas+"\\u2013"+v.nays:"";
    return esc(v.motion)+": "+esc(v.result)+n+(v.how?" ("+esc(v.how)+")":"")
      +(v.did?"; "+esc(v.did):"")+".";
  }
  function bills(day){
    var out=[],seq=(day.bills||[]).filter(function(b){return !b.consent;});
    seq.forEach(function(b){
      out.push('<li><a class="fsbn" href="bill/'+esc(b.year)+'/'+esc(String(b.bill).toLowerCase())
        +'.html">'+esc(b.n||b.bill)+'</a> <span class="fsv">'
        +(b.votes||[]).map(vote).join(" ")+'</span></li>');});
    var c=day.consent,line="";
    if(c&&c.bills)line='<p class="fscons">Consent calendar, '+plural(c.bills,"bill")+": "
      +(c.outcomes||[]).map(function(o){return esc(o.outcome)+" "+o.bills;}).join(", ")+".</p>";
    return line+(out.length?'<ul class="fsbl">'+out.join("")+"</ul>"
      :(line?"":'<p class="fsnote">No bill was voted on this day.</p>'));
  }
  function fill(det){
    var slot=det.querySelector(".fsbills");
    if(!slot||slot.dataset.done)return;
    var k=slot.dataset.load.split("|");
    load(k[0],k[1]).then(function(T){
      var d=(T.days||[]).filter(function(x){return x.date===k[2];})[0];
      if(!d)return;
      slot.innerHTML=bills(d);slot.dataset.done="1";
    }).catch(function(){});
  }
  function longDay(s){return typeof dateWords==="function"?dateWords(s,"long"):s;}
  function fold(b,t,d){
    var c=d.counts||{},m=[];
    if(c.bills)m.push(plural(c.bills,"bill"));
    if(c.roll_calls)m.push(plural(c.roll_calls,"roll call"));
    var j=String(d.journal||"").match(/^(HJ|SJ)\\s*0*(\\d+)/);
    var jw=j?(j[1]==="HJ"?"House Journal ":"Senate Journal ")+j[2]:(d.journal||"");
    return '<li><details class="fsday" data-date="'+esc(d.date)+'"><summary><span class="fsd">'
      +esc(longDay(d.date))+'</span><span class="fsm">'+m.join(" &middot; ")+'</span></summary>'
      +'<div class="fsbody"><p class="fslinks"><a href="session/'+b+'/'+esc(d.date)
      +'.html">Open this session day</a>'+(d.journal_url?' &middot; <a href="'+esc(d.journal_url)
      +'">'+esc(jw)+' (PDF)</a>':"")+'</p><div class="fsbills" data-load="'+b+"|"+esc(t)+"|"
      +esc(d.date)+'"><p class="fsnote">The bills it voted on, and every vote, are on the '
      +"session day&rsquo;s own page.</p></div></div></details></li>";
  }
  document.querySelectorAll(".fschamber").forEach(function(col){
    var b=col.dataset.body,list=col.querySelector(".fsdays"),
        term=col.querySelector(".fsterm"),sort=col.querySelector(".fssort"),
        count=col.querySelector(".fscount"),since=count.textContent.split("\\u00b7")[1]||"";
    col.querySelector(".fsctl").hidden=false;
    list.addEventListener("toggle",function(e){if(e.target.open)fill(e.target);},true);
    function order(){
      var items=[].slice.call(list.children);
      var want=sort.value==="old"?1:-1;
      items.sort(function(x,y){
        var a=x.firstChild.dataset.date,c=y.firstChild.dataset.date;
        return a<c?-want:a>c?want:0;});
      items.forEach(function(li){list.appendChild(li);});
    }
    sort.addEventListener("change",order);
    term.addEventListener("change",function(){
      var t=term.value;
      list.setAttribute("aria-busy","true");
      load(b,t).then(function(T){
        var days=T.days||[];
        list.innerHTML=days.map(function(d){return fold(b,t,d);}).join("");
        count.textContent=plural(days.length,"session day")+" in "+t.replace("-","\\u2013")
          +(since?" \\u00b7"+since:"");
        order();
      }).catch(function(){
        count.textContent="That term's session days could not be loaded.";
      }).then(function(){list.removeAttribute("aria-busy");});
    });
  });
})();
</script>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    a = ap.parse_args()
    page = Path(a.site) / "committees.html"
    if not page.exists():
        print("  committees.html is not built: nothing to put the full sessions on")
        return 0
    text = page.read_text(encoding="utf-8")
    if not SLOT.search(text):
        print("  committees.html has no slot for the full sessions "
              "(build_committees writes it): the page is left as it is")
        return 0
    html, why = block(a.site)
    if not html:
        print(f"  the full sessions are not drawn: {why}")
        return 0
    page.write_text(SLOT.sub(lambda _m: html, text, count=1), encoding="utf-8")
    n = html.count('class="fsday"')
    print(f"  committees.html: the House and Senate full sessions, {n} session days of "
          "the latest term drawn, every earlier term a pick away")
    return 0


if __name__ == "__main__":
    sys.exit(main())
