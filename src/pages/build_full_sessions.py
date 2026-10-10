#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-10.3
"""
The House and the Senate as committees of the whole: a card at the top of
each column of /committees, and a page for each chamber's session days.

    python3 src/pages/build_full_sessions.py --site site [--base URL]

The person, 9 October 2026 (round two, v12 and v13), and their correction of
10 October: "when I mentioned adding the house and Senate session days, I
meant that they would be listed in a similar format to the other committees
and that when you clicked to see their pages you'd be able to view each term
and select the session day you wanted to view the full page of." So:

  - /committees carries one card at the top of the House column and one at
    the top of the Senate column, drawn by build_committees.committee_card's
    markup (the same component): "House Session Days", who presides, its
    members, and its session days in the latest term and since the first
    year;
  - each card leads to the chamber's page, /session/H and /session/S, beside
    the day pages (/session/H/<date>), the counterpart of a committee's page:
    the same head (the chamber, who presides), a term picker covering every
    term the record holds, the latest chosen, and that term's session days
    listed as a committee's meetings are -- the day, its bills and roll
    calls, the consent calendar's line where there is one, its journal --
    newest first or oldest first, each leading to its full session-day page.

Two pages, not one per term: the latest term is written into the page, so it
reads without script; another term is drawn from that term's file,
site/session/<H|S>/<term>.json, which build_session_pages writes
(write_term_records), when it is chosen.

WHY A STEP OF ITS OWN, AFTER THE SESSION PAGES. Those term files are written
after build_committees, so the committees step cannot read them on a build
into an empty site -- GitHub's nightly -- and would draw the chambers from
last night's files on the laptop and from nothing on the night: the trap the
home page's Committees card fell into (13c674b). build_committees writes an
empty slot at the top of each column (<!-- chamber:H --><!-- /chamber:H -->)
and this fills it, between the same two marks, so running it again redraws
rather than doubles it. Where a slot or the term files are missing it says
so and leaves the page as it is.

Reads site/session/days.json, site/session/<H|S>/<term>.json,
site/officers.json and site/legislators.json; writes site/committees.html,
site/session/H.html and site/session/S.html, and adds the two to the sitemap.
Asks nobody anything.
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

import build_date
import shell as S
import structured as LD
import components as C
from components import date_words, pchip

E = lambda s: _html.escape(str(s or ""), quote=True)  # noqa: E731
CHAMBER = {"H": "House", "S": "Senate"}
BODY_NAME = {"H": "House of Representatives", "S": "State Senate"}
JOURNAL = {"HJ": "House Journal", "SJ": "Senate Journal"}
# Who presides, by the office officers.json names, in the order the head
# lists them; the card names the first.
PRESIDES = {"H": (("Speaker of the House", "Speaker"),
                  ("Deputy Speaker of the House", "Deputy Speaker")),
            "S": (("President of the Senate", "Senate President"),)}
TERM = re.compile(r"\d{4}-\d{4}")


def slot(body):
    """The marks build_committees writes at the top of a column."""
    return re.compile(rf"<!-- chamber:{body} -->.*?<!-- /chamber:{body} -->", re.S)


def plural(n, word):
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def dash(term):
    return str(term).replace("-", "–")


def journal_words(j):
    """"HJ 5" -> "House Journal 5"."""
    m = re.match(r"^(HJ|SJ)\s*0*(\d+)", str(j or ""))
    return f"{JOURNAL[m.group(1)]} {m.group(2)}" if m else str(j or "")


def _load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def chamber(site, body, today):
    """What the record holds for one chamber: its terms (the term files, newest
    first), its latest term's days, every day it sat, its members today and
    who presides today."""
    site = Path(site)
    terms = sorted((f.stem for f in (site / "session" / body).glob("*.json")
                    if TERM.fullmatch(f.stem)), reverse=True)
    dates = sorted((_load(site / "session" / "days.json", {}) or {}).get(body) or [])
    if not terms or not dates:
        return None
    days = (_load(site / "session" / body / f"{terms[0]}.json", {}) or {}).get("days") or []
    legs = _load(site / "legislators.json", []) or []
    by_id = {str(m.get("id")): m for m in legs}
    officers = (_load(site / "officers.json", {}) or {}).get("officers") or []
    chair = []
    for office, role in PRESIDES[body]:
        o = next((o for o in officers if o.get("office") == office and o.get("b") == body
                  and str(o.get("from") or "") <= today < str(o.get("to") or "9999")), None)
        m = by_id.get(str(o.get("id"))) if o else None
        if m and m.get("chamber") == body:
            chair.append((role, m))
    return {"body": body, "terms": terms, "latest": terms[0], "days": days, "dates": dates,
            "members": sum(1 for m in legs if m.get("chamber") == body), "chair": chair}


def bare_name(m):
    """"Sherman Packard" out of the roster's "Rep. Sherman Packard"."""
    return re.sub(r"^(Rep|Sen)\.\s*", "", str(m.get("display_plain") or m.get("name") or ""))


def card(c):
    """The chamber on /committees, as build_committees.committee_card draws a
    committee: its name, and what the record holds -- who presides, its
    members, and its session days, the latest term's and every term's."""
    bits = []
    if c["chair"]:
        role, m = c["chair"][0]
        bits.append(f"Presided over by {E(role)} {E(bare_name(m))}")
    if c["members"]:
        bits.append(plural(c["members"], "member"))
    bits.append(f"{plural(len(c['days']), 'session day')} in {E(dash(c['latest']))} and "
                f"{len(c['dates']):,} since {c['dates'][0][:4]}")
    return (f'<a class="ccard chcard" href="session/{c["body"]}.html">'
            f'<span class="cc-n">{CHAMBER[c["body"]]} Session Days</span>'
            f'<span class="cc-m">{" &middot; ".join(bits)}</span></a>')


def day_section(body, d):
    """One session day, as a committee's page lists a meeting: the day, as a
    meeting's is written ("Feb 19, 2026"), as the link to its full page, its bills and roll calls, the consent calendar's
    line where there is one, and its journal."""
    date = d["date"]
    c = d.get("counts") or {}
    said = [plural(c["bills"], "bill")] if c.get("bills") else []
    if c.get("roll_calls"):
        said.append(plural(c["roll_calls"], "roll call"))
    cons = d.get("consent") or {}
    cline = ""
    if cons.get("bills"):
        cline = (f'<p class="cnarr">Consent calendar, {plural(cons["bills"], "bill")}: '
                 + ", ".join(f'{E(o.get("outcome"))} {o.get("bills")}'
                             for o in cons.get("outcomes") or []) + ".</p>")
    links = [f'<a href="session/{body}/{E(date)}.html">The full session day</a>']
    if d.get("journal_url"):
        links.append(f'<a href="{E(d["journal_url"])}">{E(journal_words(d.get("journal")))} '
                     "(PDF)</a>")
    return (f'<section class="cday" id="day-{E(date)}" data-date="{E(date)}">'
            f'<h3><a class="daylink" href="session/{body}/{E(date)}.html">'
            f'{E(date_words(date))}</a></h3>'
            + (f'<p class="cnarr">{" &middot; ".join(said)}</p>' if said else "")
            + cline + f'<p class="src">{" &middot; ".join(links)}</p></section>')


def count_line(body, n, term):
    return (f"{plural(n, 'day')} the {CHAMBER[body]} sat in {E(dash(term))}, newest first. "
            "Each opens on the day&rsquo;s full page: what it took up, in the order the "
            "journal prints it, and how it voted.")


# Share, as a session day's head carries it (build_session_pages.SHARE).
SHARE = ('<button type="button" class="pshare" data-share>' + C.icon("share") + "Share</button>"
         '<span class="sharestate" role="status" aria-live="polite"></span>')


def page_head(c, path, base):
    """THE CHAMBER'S HEAD IS A COMMITTEE PAGE'S RECORD HEAD (the component
    plan's C6, as a committee's and a session day's are, 10 October 2026):
    Committees and the chamber in the trail, its session days as the title,
    who presides as a person in a sentence with the office, the facts -- its
    sitting members, its session days this term and since the first -- and
    Cite this page and Share."""
    body = c["body"]
    chair = [f"{C.person_link(m)}, {E(role)}" for role, m in c["chair"]]
    line = (f"The New Hampshire {BODY_NAME[body]}"
            + (", presided over by " + " and ".join(chair) if chair else "") + ".")
    facts = [["Members", f'<a href="officials.html#legislators">'
                         f'{plural(c["members"], "sitting member")}</a>'],
             ["This Term", f"{plural(len(c['days']), 'session day')}",
              f"in {E(dash(c['latest']))}"],
             ["On Record", f"{plural(len(c['dates']), 'session day')}",
              f"since {c['dates'][0][:4]}"]]
    cite = S.cite_block(path, f"{CHAMBER[body]} Session Days | Granite Record", base, S.BUILT)
    assert cite.endswith("</div>"), "the citation block no longer ends its row"
    return (C.record_head({"trail": [["Committees", "committees.html"], [CHAMBER[body], ""]],
                           "title": f"{CHAMBER[body]} Session Days", "line": line,
                           "facts": facts, "actions": cite[:-len("</div>")] + SHARE + "</div>",
                           "kind": "committee cmtehead chamberhead"})
            + f'<p class="src fill rnote">Every day the whole {CHAMBER[body]} sat, term by term, '
            "as its journal records it. A committee&rsquo;s days are on its own page, from "
            '<a href="committees.html">Committees</a>.</p>')


def page_body(c, path="", base=""):
    """The chamber's page: the record head, then the term and the order, then
    the latest term's days."""
    body = c["body"]
    opts = "".join(f'<option value="{E(t)}"{" selected" if t == c["latest"] else ""}>'
                   f"{E(dash(t))}</option>" for t in c["terms"])
    days = "".join(day_section(body, d) for d in reversed(c["days"]))
    return (page_head(c, path or f"/session/{body}.html", base)
            + f'<div class="bfilt pterm chamberctl" data-body="{body}">'
            f'<label>Term <select class="chterm">{opts}</select></label>'
            '<label>Order <select class="chsort"><option value="new" selected>Newest first'
            '</option><option value="old">Oldest first</option></select></label></div>'
            f'<p class="src chcount" aria-live="polite">{count_line(body, len(c["days"]), c["latest"])}</p>'
            f'<div class="chdays">{days}</div>')


# THE PAGE'S SCRIPT: another term from its own file, the order either way, and
# the term in the address (?term=2023-2024) so a reload or a link keeps it.
# The days it draws are day_section's, written again here in the same words;
# preflight holds the two to the same markup.
SCRIPT = """<script>
(function(){
  var ctl=document.querySelector(".chamberctl");
  if(!ctl)return;
  var b=ctl.dataset.body,term=ctl.querySelector(".chterm"),sort=ctl.querySelector(".chsort"),
      list=document.querySelector(".chdays"),count=document.querySelector(".chcount"),
      word=b==="S"?"Senate":"House",cache={};
  function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
  function plural(n,w){return n.toLocaleString("en-US")+" "+w+(n===1?"":"s");}
  function dash(t){return String(t).replace("-","\\u2013");}
  function long(d){return typeof dateWords==="function"?dateWords(d):d;}
  function journal(j){var m=String(j||"").match(/^(HJ|SJ)\\s*0*(\\d+)/);
    return m?(m[1]==="HJ"?"House Journal ":"Senate Journal ")+m[2]:String(j||"");}
  function day(d){
    var c=d.counts||{},said=[],cons=d.consent||{},cl="";
    if(c.bills)said.push(plural(c.bills,"bill"));
    if(c.roll_calls)said.push(plural(c.roll_calls,"roll call"));
    if(cons.bills)cl='<p class="cnarr">Consent calendar, '+plural(cons.bills,"bill")+": "
      +(cons.outcomes||[]).map(function(o){return esc(o.outcome)+" "+o.bills;}).join(", ")+".</p>";
    var links=['<a href="session/'+b+'/'+esc(d.date)+'.html">The full session day</a>'];
    if(d.journal_url)links.push('<a href="'+esc(d.journal_url)+'">'+esc(journal(d.journal))+' (PDF)</a>');
    return '<section class="cday" id="day-'+esc(d.date)+'" data-date="'+esc(d.date)+'">'
      +'<h3><a class="daylink" href="session/'+b+'/'+esc(d.date)+'.html">'+esc(long(d.date))+'</a></h3>'
      +(said.length?'<p class="cnarr">'+said.join(" &middot; ")+'</p>':"")
      +cl+'<p class="src">'+links.join(" &middot; ")+'</p></section>';
  }
  function line(n,t){
    return plural(n,"day")+" the "+word+" sat in "+esc(dash(t))+", "
      +(sort.value==="old"?"oldest":"newest")+" first. Each opens on the day&rsquo;s full page: "
      +"what it took up, in the order the journal prints it, and how it voted.";
  }
  function order(){
    var items=[].slice.call(list.children),up=sort.value==="old";
    items.sort(function(x,y){var a=x.dataset.date,c=y.dataset.date;
      return a<c?(up?-1:1):a>c?(up?1:-1):0;});
    items.forEach(function(s){list.appendChild(s);});
    count.innerHTML=line(items.length,term.value);
  }
  function show(t,write){
    if(!cache[t])cache[t]=fetch("/session/"+b+"/"+t+".json").then(function(r){
      if(!r.ok)throw new Error(r.status);return r.json();});
    list.setAttribute("aria-busy","true");
    cache[t].then(function(T){
      list.innerHTML=(T.days||[]).map(day).join("");
      order();
      if(write&&history.replaceState)history.replaceState(null,"",
        location.pathname+"?term="+t+location.hash);
    }).catch(function(){
      count.textContent="The session days of "+dash(t)+" could not be loaded.";
    }).then(function(){list.removeAttribute("aria-busy");});
  }
  term.addEventListener("change",function(){show(term.value,true);});
  sort.addEventListener("change",order);
  var want=new URLSearchParams(location.search).get("term");
  if(want&&want!==term.value&&[].some.call(term.options,function(o){return o.value===want;})){
    term.value=want;show(want,false);
  }
})();
</script>"""


def write_page(site, c, base):
    """site/session/<H|S>.html, built from the record template as a
    committee's page is, so it carries the same frame and Cite this page."""
    body = c["body"]
    path = f"/session/{body}.html"
    name = f"{CHAMBER[body]} Session Days"
    desc = (f"Every day the New Hampshire {CHAMBER[body]} sat, term by term since "
            f"{c['dates'][0][:4]}: the bills it took up and its roll calls, each day with "
            "its own page.")
    html = S.page(S.template(site), path=path, base=base,
                  title=f"{name} | Granite Record", og_title=name,
                  og_image="og-committee.png", og_alt="Granite Record: committees and hearings",
                  description=desc, globals={"GR_STATIC": True}, og_type="website",
                  jsonld=LD.listing(name, desc, base, S.canon(path)),
                  noscript="", skip_label="Skip to the session days",
                  nav_current="committees.html", sr_title="", cite=False)
    assert '<div id="results"></div>' in html, f"{path}: the template has no results slot"
    html = html.replace('<div id="results"></div>',
                        f'<div id="results">{page_body(c, path, base)}</div>{SCRIPT}', 1)
    (Path(site) / "session" / f"{body}.html").write_text(html, encoding="utf-8")
    return base + S.canon(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site, base = Path(a.site), a.base.rstrip("/")
    today = build_date.today().isoformat()
    made, urls = [], []
    for body in ("H", "S"):
        c = chamber(site, body, today)
        if not c:
            print(f"  the {CHAMBER[body]} has no session days on this site: no card, no page")
            continue
        urls.append(write_page(site, c, base))
        made.append(c)
    page = site / "committees.html"
    if page.exists() and made:
        text = page.read_text(encoding="utf-8")
        for c in made:
            pat = slot(c["body"])
            if not pat.search(text):
                print(f"  committees.html has no slot for the {CHAMBER[c['body']]} card "
                      "(build_committees writes it): the page is left as it is")
                continue
            b = c["body"]
            text = pat.sub(lambda _m: f"<!-- chamber:{b} -->{card(c)}<!-- /chamber:{b} -->",
                           text, count=1)
        page.write_text(text, encoding="utf-8")
    sm = site / "sitemap.xml"
    if sm.exists() and urls:
        text = sm.read_text(encoding="utf-8")
        add = "".join(f"<url><loc>{E(u)}</loc></url>\n" for u in urls if E(u) not in text)
        if add:
            sm.write_text(text.replace("</urlset>", add + "</urlset>"), encoding="utf-8")
    for c in made:
        print(f"  session/{c['body']}.html: {len(c['terms'])} terms, the latest "
              f"{c['latest']} with {len(c['days'])} days written in; its card on committees.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
