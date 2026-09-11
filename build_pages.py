#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.37
"""
Build the pages the navigation links to: legislators, town lookup, how it
works, and about.

    python3 build_pages.py --out site

Reads site/legislators.json and site/towns.json, already written by
build_site_v2.py. Kept separate from that script so a change here cannot break
the bill search, which is the part that works.

Writes a shared style.css these pages link to. index.html keeps its own inline
styles and is untouched.
"""

import argparse
import hashlib
import html as _html
import shell as _shell
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

# The palette is app.css's, read at build time rather than copied. The copy
# that used to live here had already drifted: --st-veto was #7C2D3A in one
# file and #8C4A2F in the other, the same token name naming a plum and a rust,
# and nothing could see it because each file was internally consistent.
def palette(src="app.css"):
    text = Path(src).read_text(encoding="utf-8")
    i = text.index(":root{")
    return text[i:text.index("}", text.index('--sans:"Public Sans"')) + 1]


CSS = """
__PALETTE__
*{box-sizing:border-box}html,body{margin:0}
body{font-family:var(--sans);background:var(--paper);color:var(--ink);font-size:16px;
line-height:1.55;-webkit-font-smoothing:antialiased;font-feature-settings:"tnum" 1}
:focus-visible{outline:2px solid var(--pine);outline-offset:2px}
a{color:var(--pine)}button{font:inherit;color:inherit;background:none;border:none;padding:0;cursor:pointer}
nav.top{background:var(--surface);border-bottom:1px solid var(--rule)}
nav.top .in{max-width:1180px;margin:0 auto;padding:13px 24px;display:flex;align-items:baseline;gap:24px;flex-wrap:wrap}
nav.top .brand{font-size:16px;font-weight:600}
nav.top a{font-size:14px;text-decoration:none;color:var(--ink-2)}
nav.top a[aria-current]{color:var(--ink);font-weight:600;box-shadow:0 2px 0 var(--pine)}
.wrap{max-width:820px;margin:0 auto;padding:26px 24px 80px}
.wide{max-width:1180px}
h1{font-size:24px;font-weight:600;letter-spacing:-.015em;margin:0 0 6px}
h2{font-size:16px;font-weight:600;margin:32px 0 10px}
h3{font-size:14px;font-weight:600;margin:22px 0 8px}
p{margin:0 0 12px}
/* 34em is 68 characters at the body size. Without it the lead ran
   to 148 and the footer to 182 on a 1440px screen. */
.lead{font-family:var(--serif);font-size:19px;line-height:1.65;
color:var(--ink);max-width:28em}
.note,.statemeta,.corrections,.wrap>p:not(.lead),.wrap li{max-width:34em}
b,strong{font-weight:600}
.reading{font-family:var(--serif);font-size:16px;line-height:1.68}
.reading li{margin-bottom:9px}
.note{font-size:14px;color:var(--ink-2);background:var(--surface);border-left:3px solid var(--rule-2);
padding:11px 14px;margin:0 0 14px;line-height:1.6}
input[type=search],input[type=text]{width:100%;height:42px;padding:0 14px;font:inherit;font-size:16px;
border:1px solid var(--rule-2);border-radius:var(--r-out);background:var(--surface)}
input:focus{outline:none;border-color:var(--pine);box-shadow:0 0 0 3px var(--pine-soft)}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;font-size:12px;font-weight:600;color:var(--ink-2);padding:0 0 7px;border-bottom:1px solid var(--rule)}
td{padding:9px 0;border-bottom:1px solid var(--rule);vertical-align:top}
/* THE SAME CARD app.css draws. It was a --rule border at 9px here
   and a --rule-2 border at 6px there: one name, two objects, and
   the edge at 1.19:1 against the page instead of 1.66:1. */
.card{background:var(--surface);border:1px solid var(--rule-2);
border-radius:var(--r-out);padding:15px 18px;margin-bottom:14px}
.chip{font-size:12px;padding:3px 9px;border-radius:var(--r-pill);background:var(--wash);color:var(--ink-2);
display:inline-block;margin:0 5px 5px 0}
.p-R{background:var(--rep-soft);color:var(--rep)}.p-D{background:var(--dem-soft);color:var(--dem)}
.p-I{background:var(--ind-soft);color:var(--ind)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:2px 20px}
.ownpage{float:right;font-size:14px;margin-left:14px}
.mem{padding:4px 0;font-size:14px}
.count{font-size:14px;color:var(--ink-2);margin:10px 0}
.hit{display:block;width:100%;text-align:left;padding:12px 2px;border-bottom:1px solid var(--rule);cursor:pointer}
.entry{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:20px 0 30px}
.entry a{display:block;background:var(--surface);border:1px solid var(--rule);border-radius:var(--r-out);
padding:15px 17px;text-decoration:none;color:inherit}
.entry a:hover{border-color:var(--pine)}
.entry b{display:block;font-size:16px;margin-bottom:3px;color:var(--pine)}
.entry span{font-size:14px;color:var(--ink-2)}
.statgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:1px;
background:var(--rule);border:1px solid var(--rule);border-radius:var(--r-out);overflow:hidden;margin:12px 0 30px}
.stat{background:var(--surface);padding:14px 16px}
.stat b{display:block;font-size:24px;font-weight:600}
.stat span{font-size:14px;color:var(--ink-2)}
.searchbig{display:flex;gap:8px;margin:18px 0 4px}
.searchbig input{flex:1}
.searchbig button{background:var(--pine);color:#fff;border-radius:var(--r-out);padding:0 20px;font-size:14px}
.fresh{font-size:14px;color:var(--ink-2);margin:0 0 14px;display:flex;
align-items:center;gap:7px}
.fresh:empty{display:none}
.fresh .fdot{width:8px;height:8px;border-radius:50%;background:var(--pine);flex:0 0 auto}
.fresh.stale{color:var(--st-veto)}
.fresh.stale .fdot{background:var(--st-veto)}
.statebox{border:1px solid var(--rule);border-left:4px solid var(--ink-2);border-radius:var(--r-out);
padding:15px 18px;margin:0 0 24px;background:var(--surface)}
.statebox.live{border-left-color:var(--pine);background:var(--pine-soft)}
.statebox.wait{border-left-color:#8A6D2F;background:#FBF3E2}
.statebox.off{border-left-color:var(--ink-2)}
.stateline{display:flex;align-items:center;gap:9px;font-size:16px;flex-wrap:wrap}
.stateline .dot{width:9px;height:9px;border-radius:50%;background:var(--ink-2);flex:0 0 auto}
.statebox.live .dot{background:var(--pine)}
.statebox.wait .dot{background:#8A6D2F}
.statemeta{font-size:14px;color:var(--ink-2);font-weight:400}
.statehead{font-size:16px;margin:8px 0 0}
.statenote{font-size:14px;color:var(--ink-2);margin:8px 0 0;
line-height:1.6;max-width:34em}
.statebox p:last-child{margin-bottom:0}
.twoup{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
details.vac{margin-top:10px}
details.vac summary{cursor:pointer;font-size:14px;color:var(--pine)}
.comp{margin:0 0 20px}
.compline{display:flex;align-items:baseline;gap:10px;font-size:16px;margin-bottom:7px}
.pbar2{display:flex;height:16px;border-radius:var(--r-in);overflow:hidden;background:var(--wash)}
.pseg{display:block;height:100%}
/* A bar SEGMENT, not a chip. These were .p-R too -- the same class
   name in the same file for a tinted chip and a solid block. */
.seg-R{background:var(--rep)}.seg-D{background:var(--dem)}
.seg-I{background:var(--ind)}.seg-L{background:var(--ind)}
.seg-V{background:var(--rule-2)}
.plegend{display:flex;flex-wrap:wrap;gap:14px;margin-top:8px;font-size:14px;color:var(--ink-2)}
.pdot{display:inline-block;width:9px;height:9px;border-radius:var(--r-in);margin-right:5px}
.compbox{margin:0 0 16px}
.bar{display:flex;height:22px;border-radius:var(--r-in);overflow:hidden;margin:9px 0 8px;
border:1px solid var(--rule)}
.bar span{display:block}
.legendrow{display:flex;gap:16px;flex-wrap:wrap;font-size:14px;color:var(--ink-2)}
.legendrow i{display:inline-block;width:10px;height:10px;border-radius:var(--r-in);
margin-right:5px;vertical-align:-1px}
.legendrow i.vac{background:repeating-linear-gradient(45deg,var(--rule-2),
var(--rule-2) 3px,var(--surface) 3px,var(--surface) 6px);border:1px solid var(--rule-2)}
.player{margin-top:12px;border:1px solid var(--rule);border-radius:var(--r-out);overflow:hidden;background:#000}
.player iframe{width:100%;aspect-ratio:16/9;border:0;display:block}
.pstub{aspect-ratio:16/9;display:flex;align-items:center;justify-content:center;gap:10px;
cursor:pointer;background:#14181A;color:#C8CFD1;font-size:14px}
.pstub:hover{background:#1D2225}
.townlist{max-height:340px;overflow-y:auto;border:1px solid var(--rule);border-radius:var(--r-out);
background:var(--surface);margin-top:10px}
.townrow{display:flex;width:100%;text-align:left;padding:8px 13px;font-size:14px;
border-bottom:1px solid var(--rule);cursor:pointer;align-items:baseline;gap:10px}
.townrow:last-child{border-bottom:none}
.townrow:hover{background:var(--paper)}
.townrow.sel{background:var(--pine-soft);font-weight:600}
.wct{margin-left:auto;font-size:12px;color:var(--ink-2)}
.wards{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px}
.wbtn{border:1px solid var(--edge);border-radius:var(--r-out);padding:5px 12px;font-size:14px;
background:var(--surface);cursor:pointer}
.wbtn:hover{border-color:var(--pine)}
.wbtn.sel{background:var(--pine);color:#fff;border-color:var(--pine)}
.hit:hover{background:var(--surface)}
footer{border-top:1px solid var(--rule);background:var(--surface);padding:22px 0;font-size:14px;color:var(--ink-2)}
footer .in{max-width:34em;margin:0 auto;padding:0 24px}
@media(max-width:640px){.wrap{padding:20px 18px 60px}}
/* ---- narrow screens ---------------------------------------------------
   Most people arrive from a search result on a phone. Three things break at
   380px, and each is fixed by reflowing rather than by horizontal scrolling,
   which on a civic site reads as "not meant for you".
     1. The facet sidebar sits beside the results; it has to stack.
     2. Timeline rows use a fixed date column that leaves no room for text.
     3. Vote tables and member lists are wider than the screen.
   Nothing is hidden at any width.                                        */
@media (max-width: 720px){
  .wrap,.in{padding-left:14px;padding-right:14px}
  h1{font-size:24px;line-height:1.2}
  h2{font-size:19px}
  .shell{display:block}
  .facets{position:static;max-height:none;width:auto;margin:0 0 20px;
          border-right:none;border-bottom:1px solid var(--rule);padding-bottom:14px}
  .fbody{max-height:210px}
  .tl li{flex-direction:column;gap:2px;padding:10px 0}
  .tl .d{flex:none;font-weight:600}
  .cite{white-space:normal}
  /* Not display:block. That stops a table being a table for several screen
     readers -- rows and columns disappear -- in exchange for a horizontal
     scrollbar nobody finds on a phone. Wrapping the cell text keeps the
     semantics and keeps the whole table on screen. */
  table{width:100%}
  th,td{overflow-wrap:anywhere}
  .votes th,.votes td{padding:6px 8px;font-size:14px}
  .roll,.chosen{columns:1}
  .grid{grid-template-columns:1fr}
  .tabs{flex-wrap:wrap;gap:4px}
  .tabs button{font-size:14px;padding:6px 10px}
  .searchrow{flex-direction:column;align-items:stretch;gap:8px}
  .searchbig{flex-direction:column}
  .searchbig button{padding:11px 20px}
  #year{width:100%}
  .qhint{flex-wrap:wrap;gap:8px}
  .crow{flex-wrap:wrap;gap:4px}
  .cnum{font-size:16px}
  .pbar{flex-wrap:wrap;gap:6px}
  .pbar .jump{font-size:12px}
  .twoup{grid-template-columns:1fr}
  .entry{grid-template-columns:1fr}
  .statgrid{grid-template-columns:1fr 1fr}
  nav.top .in{flex-wrap:wrap;gap:10px 14px;padding-top:10px;padding-bottom:10px}
  nav.top a{font-size:14px}
  .note,.cite,footer,.corrections{font-size:14px}
  button,.hit,summary,nav.top a{min-height:44px}
}
@media (max-width: 420px){
  .statgrid{grid-template-columns:1fr}
  .plegend{gap:8px;font-size:12px}
}

/* Focus must be visible. Keyboard users navigate by it, and the default
   outline is removed by most resets without anything put back. */
:focus-visible{outline:2px solid var(--pine);outline-offset:2px;border-radius:var(--r-in)}
.skip{position:absolute;left:-9999px;top:0;background:var(--pine);color:#fff;
padding:10px 16px;z-index:99;border-radius:0 0 var(--r-out) 0}
.skip:focus{left:0}
/* Reduced motion: honour the system preference rather than overriding it. */
@media (prefers-reduced-motion: reduce){
  *{animation-duration:.01ms !important;transition-duration:.01ms !important}
}
.sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
clip:rect(0 0 0 0);white-space:nowrap;border:0}
.corrections{font-size:14px;color:var(--ink-2);margin-top:10px}
.corrections a{color:var(--pine)}

"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;600'
         '&family=Newsreader:opsz,wght@6..72,400;6..72,600&display=swap" rel="stylesheet">')


# The content hash of style.css, so a deploy cannot serve yesterday's.
# A hash rather than the GRANITE_VERSION stamp, for the reason shell.py gives
# about app.js: the stamp is bumped by hand and the once somebody forgets is
# the release that breaks, silently, for four hours, for everyone who visited
# that morning.
def style_query():
    css = CSS.replace("__PALETTE__", palette())
    return "?v=" + hashlib.md5(css.encode("utf-8")).hexdigest()[:8]


def shell(title, current, body, wide=False, script="", desc="",
          base="https://graniterecord.org"):
    nav = []
    for href, label in (("index.html", "Home"), ("bills.html", "Bills"),
                        ("legislators.html", "Legislators"),
                        ("committees.html", "Committees"),
                        # A second nav emitter. bills.html carries the nav
                        # every shell.page() page inherits; this tuple is what
                        # legislators.html, index.html and about.html get, and
                        # when Data was added to the first it was not added
                        # here, so three pages lacked the link the other
                        # 34,000 had.
                        ("learn.html", "Learn"), ("data.html", "Data"),
                        ("about.html", "About")):
        cur = ' aria-current="page"' if href == current else ""
        nav.append(f'<a href="{href}"{cur}>{label}</a>')
    STYLE_Q = style_query()
    # THE PAGES A SEARCH ENGINE REACHES FIRST HAD THE LEAST IN THEIR HEAD.
    # Every one of the 33,683 bill pages carries a description, a canonical
    # address and an unfurl card because shell.py writes them. The home page,
    # the search page, the legislator index and About did not, because they
    # are written here and this function never had them -- and those four are
    # where a person arrives.
    _e = lambda s: _html.escape(str(s or ""), quote=True)
    # The host serves /legislators, not /legislators.html, and redirects
    # the second to the first. shell.canon is where that is written down.
    _canon = (base + _shell.canon("/" + current)) if current else (base + "/")
    HEAD_SEO = (f'<meta name="description" content="{_e(desc)}">'
                f'<link rel="canonical" href="{_canon}">'
                f'<meta property="og:type" content="website">'
                f'<meta property="og:title" content="{_e(title)}">'
                f'<meta property="og:description" content="{_e(desc)}">'
                f'<meta property="og:url" content="{_canon}">'
                f'<meta property="og:site_name" content="Granite Record">'
                f'<meta name="twitter:card" content="summary">') if desc else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>{HEAD_SEO}{FONTS}<link rel="stylesheet" href="style.css{STYLE_Q}">
<link rel="alternate" type="application/rss+xml" title="Granite Record — all activity"
 href="/feed/all.xml">
<link rel="alternate" type="application/rss+xml" title="Granite Record — upcoming hearings"
 href="/feed/hearings.xml"></head><body>
<a class="skip" href="#main">Skip to the content</a>\n<nav class="top"><div class="in"><span class="brand">Granite Record</span>
{''.join(nav)}</div></nav>
<main class="wrap{' wide' if wide else ''}" id="main">{body}</main>
<footer><div class="in">Built from public records published by the New Hampshire
General Court. Not affiliated with the General Court.
<a href="about.html">How this is made</a>.
<span class="corrections">Found an error?
<a href="mailto:contact@graniterecord.org">contact@graniterecord.org</a>
</span></div></footer>
{script}</body></html>"""


# SUPERSEDED, AND KEPT ON PURPOSE. This was the whole of "How it works"
# until the civics section replaced it. Every paragraph here was redistributed
# into civics.py rather than rewritten -- the bill path, the shorthand tables,
# the five things that surprise people -- because this prose had been read and
# corrected and the new pages should inherit that rather than start again.
# Nothing writes it out any more. Delete it once civics.py has been reviewed
# by somebody who knows the building.
LEARN = """
<h1>How the New Hampshire legislature works</h1>
<p class="lead">New Hampshire has 400 representatives and 24 senators — the largest
state legislature in the country and, per resident, by far the smallest districts.
Legislators are paid $100 a year plus mileage. Almost none have staff.</p>

<h2>Every bill gets a public hearing</h2>
<p>This is unusual. In most states a committee chair can decline to hear a bill and
it dies without anyone speaking on it. In New Hampshire every bill introduced is
referred to a committee and given a public hearing that anyone may attend and speak
at. That is why hearing recordings matter here more than they would elsewhere: the
hearing is where the substantive argument actually happens.</p>

<h2>A term is two years, and bills can cross between them</h2>
<p>The General Court sits in two-year terms beginning in odd years. Bill numbers are
unique across the whole term, so there is only ever one HB 84 in 2025–2026 — but
there will be another in the next term.</p>
<p>Most bills are settled in the year they are filed. Some are not: a committee can
retain a bill for further work, or the chamber can send it for interim study, and it
is taken up again the following year. Those show as <b>carried over</b> here, and
they are the ones people most often fail to find, because they search the current
year for a bill filed in the previous one.</p>

<h2>The path a bill takes</h2>
<ol class="reading">
<li><b>Filed as an LSR.</b> Before a bill exists it is a Legislative Service Request
— a title and an idea. Office of Legislative Services attorneys draft the text.</li>
<li><b>Introduced and referred.</b> The bill gets a number and goes to a committee
chosen by subject.</li>
<li><b>Public hearing.</b> The sponsor introduces it, then members of the public
speak for and against. You can sign in supporting or opposing whether or not you
speak.</li>
<li><b>Executive session.</b> The committee votes on what to recommend. A separate
meeting from the hearing, often days later, usually covering several bills at once.</li>
<li><b>Floor vote.</b> The full chamber votes, and is not bound by the committee's
recommendation.</li>
<li><b>The other chamber.</b> The whole process repeats. This is called crossover.</li>
<li><b>Resolving differences.</b> If the second chamber changed the bill, the first
must concur. If it will not, a committee of conference tries to write a compromise.</li>
<li><b>The governor.</b> Sign, veto, or allow it to become law unsigned.</li>
</ol>

<h2>Five things that surprise people</h2>

<p><b>Most votes leave no record.</b> Unless someone requests a roll call, chambers
vote by voice or by division. A voice vote records only which side sounded louder; a
division records the count but not who voted which way. For a great many bills there
is simply no answer to "how did my representative vote" — not because it is hidden,
but because it was never recorded.</p>

<p><b>A majority is not always enough.</b> Overriding a veto takes two thirds of
those voting. A constitutional amendment takes three fifths of the entire membership
— 240 of 400 in the House — whether or not everyone shows up. Amendments regularly
win a clear majority and fail anyway.</p>

<p><b>The consent calendar is a signal about the committee.</b> A bill goes there
when the committee vote was unanimous or nearly so and no dissenting member objected
to the placement. It then passes without floor debate. Ten members may petition to
pull a bill off and have it taken up separately.</p>

<p><b>Someone has to run the room.</b> For every House roll call one member is
recorded as presiding — the Speaker, a Deputy Speaker, or a Speaker Pro Tempore —
and does not vote except to break a tie. A Speaker will appear as not having voted on
hundreds of roll calls, and that is the job rather than absence.</p>

<p><b>Absences come in two kinds.</b> An excused absence was arranged in advance for
the whole day — illness, a death in the family, or other significant obligation. An
unexcused absence means the member either left the chamber rather than vote on that
question, or was away without arranging it beforehand.</p>

<h2>Bills and resolutions are not the same thing</h2>
<p>Which chamber a measure starts in follows from its prime sponsor: a
representative's bill begins in the House, a senator's in the Senate.</p>
<table><tbody>
<tr><td><b>HB</b></td><td>House Bill — begins in the House, must pass both chambers,
goes to the governor</td></tr>
<tr><td><b>SB</b></td><td>Senate Bill — begins in the Senate, otherwise the same</td></tr>
<tr><td><b>HR</b></td><td>House Resolution — voted on by the House only. It does not
go to the Senate or the governor and does not change any law.</td></tr>
<tr><td><b>SR</b></td><td>Senate Resolution — the Senate's equivalent, voted on only
by the Senate</td></tr>
<tr><td><b>HCR</b></td><td>House Concurrent Resolution — introduced in the House but
voted on by both chambers</td></tr>
<tr><td><b>SCR</b></td><td>Senate Concurrent Resolution — introduced in the Senate,
voted on by both</td></tr>
<tr><td><b>CACR</b></td><td>Constitutional Amendment Concurrent Resolution — a
proposed change to the state constitution. Needs three fifths of the entire
membership in each chamber, then a two-thirds vote of the people at the next
general election. The governor has no role.</td></tr>
</tbody></table>

<h2>What the suffixes on a bill number mean</h2>
<table><tbody>
<tr><td><b>-FN</b></td><td>Carries a fiscal note — an estimate of what it costs or
raises. First-year bills carry these more often, since the first year of a term is
the budget year.</td></tr>
<tr><td><b>-A</b></td><td>Contains an appropriation</td></tr>
<tr><td><b>-LOCAL</b></td><td>Has a local fiscal impact, on towns, cities, counties
or school districts</td></tr>
</tbody></table>
<p>These stack in that order, so a bill can be HB 1442-FN or HB 660-FN-LOCAL.</p>

<h2>Reading the shorthand</h2>
<table><tbody>
<tr><td><b>OTP</b></td><td>Ought to Pass — a motion to pass the bill</td></tr>
<tr><td><b>OTP/A</b></td><td>Ought to Pass with Amendment</td></tr>
<tr><td><b>ITL</b></td><td>Inexpedient to Legislate — a motion to kill the bill</td></tr>
<tr><td><b>MA / MF</b></td><td>Motion Adopted / Motion Failed</td></tr>
<tr><td><b>VV</b></td><td>Voice vote — no record of individual votes</td></tr>
<tr><td><b>DV</b></td><td>Division vote — counted, but names not recorded</td></tr>
<tr><td><b>RC</b></td><td>Roll call — each member's vote recorded by name</td></tr>
<tr><td><b>RC</b> (in a report)</td><td>Regular Calendar, not Roll Call</td></tr>
<tr><td><b>CC</b></td><td>Consent Calendar</td></tr>
<tr><td><b>OT3rdg</b></td><td>Ordered to a third reading</td></tr>
<tr><td><b>HJ / SJ</b></td><td>House or Senate Journal, and the page number</td></tr>
</tbody></table>

<h2>How to testify</h2>
<p>You do not need to be invited, and you do not need to speak. You can sign in for
or against a bill online before the hearing, submit written testimony, or come and
say your piece in person. Committees generally hear anyone who signs up.</p>
"""

NOT_FOUND = """
<p class="note">NO PAGE AT THIS ADDRESS</p>
<h1>Nothing is published here</h1>
<p class="lead">The address may be mistyped, or name a bill in a year it does
not exist in: every bill since 1989 has a page at <code>/bill/&lt;year&gt;/&lt;number&gt;</code>,
and a bill number starts again every two years.</p>
<p id="nf-bill" hidden></p>
<p><a href="bills.html">Search every bill</a> &middot;
<a href="legislators.html">Legislators</a> &middot;
<a href="committees.html">Committees</a> &middot; <a href="index.html">Home</a></p>
<script>
(function(){
  var m=location.pathname.match(/^\\/bill\\/(\\d{4})\\/([a-z]+)0*(\\d+)/i);
  if(!m)return;
  var id=(m[2]+m[3]).toUpperCase(),p=document.getElementById("nf-bill");
  var a=document.createElement("a");
  a.href="/bills.html?q="+encodeURIComponent(id);
  a.textContent="Search for "+id+" in every term";
  p.appendChild(document.createTextNode("No page for "+id+" of "+m[1]+". "));
  p.appendChild(a);p.hidden=false;
})();
</script>
"""

ABOUT = """
<h1>About this site</h1>
<p class="lead">Granite Record indexes the public record of the New Hampshire General
Court: what each bill does, who sponsored it, when it was heard, how it was voted on,
and where in the recording it was discussed.</p>

<h2>Where the information comes from</h2>
<p>Bill histories, hearing schedules and sponsors come from the General Court's
published data files. Vote tallies and individual member votes come from its roll
call files, and for sessions those files no longer cover, from the read-only
database the General Court publishes credentials for. The House's committee
majority and minority reports are taken from the House Calendar; the Senate's
come from that same database, which is where the Senate files them. Hearing and
session recordings are the General Court's own, on YouTube, linked rather than
copied.</p>
<p>Where a hearing shows how many people signed in for and against a bill, those
are counts and nothing else. The General Court's sign-in sheet records a name, a
town and often written testimony for every person; almost all of them are members
of the public rather than public figures, and this site does not republish them.</p>
<p>An earlier term marked <i>archived</i> is a thinner record on purpose. For
the 2023-2024 term the bills, their titles and statuses, the committees they
went to, their hearing dates, their sponsors and every recorded vote are here.
What is not is the docket &#8212; the General Court's own line-by-line list of
actions &#8212; and the written committee reports, which are a further request
per bill. Every archived bill links its own official record, which has both.</p>

<h2>What is taken from the record and what is generated</h2>
<p>Dates, sponsors, vote tallies, committee assignments and hearing times are taken
directly from the official record. Committee reports are reproduced as filed, in the
committee's own words.</p>
<p>Plain-language summaries of a bill's progress are generated from those records by
software, not written by hand. Most timestamps are not estimates: they are the
moment the chair or the clerk opened the item, found by matching what they said
against the recording's captions. The player opens two seconds before that, which
is enough not to clip the first word. Where no boundary was heard, the site either
shows a start marked <i>approximate</i> or links the recording with no time at
all &#8212; it does not guess.</p>

<h2>Accuracy</h2>
<p>Automatic timing is checked against 35 proceedings that a person timed by
watching the recording, across seven sessions. Of the 19 the site can currently
place, the median is out by one second and the worst by 5 minutes 47 seconds;
17 of the 19 are within a minute. The 16 it cannot place carry no time at all
rather than a guessed one.</p>
<p>Across the whole site there are 10,810 proceedings. 4,994 carry a boundary
the chair or the clerk said out loud, and 209 a roll call's own clock time from
the General Court's record, which involves no speech recognition at all. 1,427
were worked out from where the bill is discussed rather than quoted; those are
the ones marked <i>approximate</i>, and they can be a few minutes out. The
remaining 4,180 are shown with no time: 2,522 passed on a consent calendar and
were never taken up separately, 1,068 have no recording, and 590 are floor
actions the site can date but not place in the video.</p>
<p>Only the word <i>approximate</i> distinguishes a start that was inferred
from one that was quoted. The site used to print the margin and the method
beside every timestamp; that turned out to be methodology in the reader's way,
and the useful thing is that a link lands where the bill was actually taken
up.</p>
<p>Speech recognition is worst at exactly the things that matter most — names,
numbers and organisations. Check the recording before quoting anything.</p>

<h2>Corrections</h2>
<p>If something here misrepresents the record, it should be corrected. The official
record at gencourt.state.nh.us always takes precedence over anything shown here.</p>

<h2>Independence</h2>
<p>This site is not affiliated with or endorsed by the New Hampshire General Court.
It takes no position on any bill.</p>
"""

LEG_JS = """
<script>
const P={R:"Republican",D:"Democrat",I:"Independent",L:"Libertarian",X:"Not on file"};
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let L=[],q="",open=null,det={};
// Anchored to the site root, not to the page. legislators.html is served at
// /legislators, and a legislators/ folder of per-member data sits beside it --
// so /legislators can be redirected to /legislators/, and a relative
// "legislators/377204.json" then resolves to /legislators/legislators/... and
// 404s. The bill page had the same trap and it cost an evening.
window.DATA=window.DATA||((f)=>new URL(f, location.origin+"/").href);
fetch(DATA("legislators.json")).then(r=>r.json()).then(d=>{
  L=d.map(m=>({...m,hay:[m.name,m.party,m.county,"district "+m.district,
    m.title||"",(m.committees||[]).join(" "),
    (m.towns||[]).join(" ")].join(" ").toLowerCase()}));
  document.getElementById("q").disabled=false; render();});
function render(){
  const rows=q?L.filter(m=>q.toLowerCase().split(/\\s+/).every(w=>m.hay.includes(w))):L;
  document.getElementById("count").textContent=
    `${rows.length} of ${L.length} legislators`;
  const by={};
  rows.forEach(m=>{(by[m.chamber==="S"?"Senate":"House"]=by[m.chamber==="S"?"Senate":"House"]||[]).push(m);});
  document.getElementById("out").innerHTML=Object.entries(by).map(([ch,ms])=>{
    const byc={};
    ms.forEach(m=>{(byc[m.county||"—"]=byc[m.county||"—"]||[]).push(m);});
    return `<h2>${ch} — ${ms.length}</h2>`+Object.keys(byc).sort().map(c=>
      `<h3>${esc(c)}</h3><div class="grid">`+byc[c]
        // By district number, then by name. Alphabetical order inside a county
        // scattered the members of one district across the list, when the
        // district is the thing a reader is looking for: it is what a town
        // lookup returns and what a ballot is organised by. Several members
        // share a district, so the name is the tiebreaker rather than the key.
        .sort((a,b)=>(parseInt(a.district,10)||0)-(parseInt(b.district,10)||0)
                     ||a.name.localeCompare(b.name)).map(m=>
        `<div class="mem"><button class="hit" style="border:none;padding:2px 0"
          data-id="${esc(m.id)}">${esc(m.display_plain||m.name)}</button>
          <span class="chip p-${esc((m.party||"X")[0])}">${esc((m.party||"?")[0])}</span>
          <span style="color:var(--ink-2);font-size:12px">${esc(m.district_label||("dist "+m.district))}</span>
          ${open===m.id?detail(m):""}</div>`).join("")+`</div>`).join("");}).join("");
}
function detail(m){
  const d=det[m.id];
  if(!d)return `<div class="note" style="margin-top:8px">Loading…</div>`;
  const c=d.counts||{};
  const votes=(d.votes||[]).slice(0,60);
  // The member's own page, which is where a reader following a name expects
  // to end up. Every name on this site linked back to this same search page
  // until now.
  const own=m.slug||d.slug;
  return `<div class="card" style="margin-top:8px">
    ${own?`<a class="ownpage" href="legislator/${esc(own)}.html">Full page
      &#8594;</a>`:""}
    <p style="margin:0 0 8px"><b>${own?`<a href="legislator/${esc(own)}.html"
      >${esc(d.display_plain||d.name)}</a>`:esc(d.display_plain||d.name)}</b>
      — ${esc(P[d.party_code]||d.party||"")},
      ${esc(d.county)} district ${esc(d.district)}
      ${d.url?` · <a href="${esc(d.url)}" target="_blank" rel="noopener">official
        page</a>`:""}
      · <a href="feed/legislator/${esc(m.id)}.xml">votes feed</a></p>
    <p class="statemeta" style="margin:0 0 8px">The official page carries a photo,
      biography, committee positions and towns represented. It stops resolving once
      a member leaves office; for those, the General Court keeps
      <a href="https://gc.nh.gov/bill_Status/byAnyMember.aspx" target="_blank"
      rel="noopener">a search across past members</a>.</p>
    ${(d.committees||[]).length?`<p style="font-size:13px;margin:0 0 8px">
      <b>Committees:</b> ${d.committees.map(esc).join(", ")}
      <span class="statemeta">Committee membership is where most of the work
      happens — every bill gets a hearing and a recommendation before the full
      chamber ever sees it.</span></p>`:""}
    ${(d.towns||[]).length?`<p style="font-size:13px;color:var(--ink-2);margin:0 0 8px">
      Represents ${d.towns.map(esc).join(", ")}</p>`:""}
    ${d.phone?`<p style="font-size:13px;color:var(--ink-2);margin:0 0 8px">
      ${esc(d.phone)}${d.email?` · <a href="mailto:${esc(d.email)}">${esc(d.email)}</a>`:""}</p>`:""}
    <p style="font-size:13px;margin:0 0 8px">
      ${c.Yea||0} yes · ${c.Nay||0} no
      ${c.Presiding?` · presided over ${c.Presiding} roll calls without voting`:""}
      ${c["Not Voting/Excused"]?` · excused ${c["Not Voting/Excused"]}`:""}
      ${c["Not Voting/Not Excused"]?` · absent ${c["Not Voting/Not Excused"]}`:""}</p>
    <p class="note" style="margin:0 0 10px">Roll calls only. Voice and division votes
      record no individual positions, so they are missing here for everyone equally.</p>
    ${votes.length?`<details><summary>Show voting record
      (${(d.votes||[]).length} recorded votes)</summary>
      <table style="margin-top:10px"><thead><tr><th>Date</th><th>Bill</th>
      <th>Question</th><th>Vote</th></tr></thead><tbody>${votes.map(v=>
      // #<year>/<bill>, not a bare number. A bill number exists in both
      // terms about a third of the time, and the app resolves a bare one to
      // whichever comes first in the index -- so these links opened the wrong
      // biennium's bill. v.y is the filing year, added to the vote record for
      // exactly this.
      `<tr><td>${esc(v.d)}</td><td>${v.b?`<a href="bills.html#${
        v.y?esc(v.y)+"/":""}${esc(v.b)}">${esc(v.b)}</a>`:"&mdash;"}</td>
       <td>${esc(v.q)}</td><td>${esc(v.v)}</td></tr>`).join("")}</tbody></table>
      ${(d.votes||[]).length>60?`<p class="count">Showing the 60 most recent of
        ${d.votes.length}.</p>`:""}</details>`:""}</div>`;
}
document.addEventListener("click",e=>{
  const b=e.target.closest("[data-id]"); if(!b)return;
  const id=b.dataset.id;
  if(open===id){open=null;render();return;}
  open=id;
  if(det[id]){render();return;}
  render();
  fetch(DATA(`legislators/${id}.json`)).then(r=>r.json()).then(d=>{det[id]=d;render();})
    .catch(()=>{det[id]={name:"(unavailable)",votes:[]};render();});
});
document.getElementById("q").addEventListener("input",e=>{q=e.target.value;render();});
</script>"""

TOWN_JS = """
<script>
(function(){
// Scoped: this runs alongside the roster search on the same page,
// so its element ids are its own and nothing leaks between them.
const ID={q:"tq",count:"tcount",list:"towns",out:"tout"};
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const num=x=>String(parseInt(x,10));
let T={},L=[],D={},TOWNS=[],town=null,ward=null;

// Anchored to the site root, not to the page. legislators.html is served at
// /legislators, and a legislators/ folder of per-member data sits beside it --
// so /legislators can be redirected to /legislators/, and a relative
// "legislators/377204.json" then resolves to /legislators/legislators/... and
// 404s. The bill page had the same trap and it cost an evening.
window.DATA=window.DATA||((f)=>new URL(f, location.origin+"/").href);
Promise.all([fetch(DATA("towns.json")).then(r=>r.json()),
             fetch(DATA("legislators.json")).then(r=>r.json()),
             fetch(DATA("districts.json")).then(r=>r.json()).catch(()=>({}))])
 .then(([t,l,d])=>{
   T=t;L=l;D=d;TOWNS=Object.keys(T).sort();
   document.getElementById(ID.q).disabled=false;
   document.getElementById(ID.count).textContent=`${TOWNS.length} towns and cities`;
   list(""); document.getElementById(ID.q).focus();});

function wardsOf(t){
  const seats=T[t]||[], dw=D[t]||{};
  return [...new Set(seats.map(s=>s.ward||"0").concat(Object.keys(dw)))]
    .sort((a,b)=>parseInt(a)-parseInt(b));
}
function houseOf(t,w){
  // Prefer districts.json: it includes floterial districts, which the General
  // Court's own district file omits entirely. A resident is in two House
  // districts at once -- their town's, and the floterial overlaying it.
  const d=(D[t]||{})[w];
  if(d&&d.house&&d.house.length)return d.house;
  return (T[t]||[]).filter(s=>(s.ward||"0")===w)
    .map(s=>({county:s.county,district:parseInt(s.district,10),
              seats:null,floterial:false}));
}

/* Always show a browsable list, not only type-ahead. Someone who is not sure
   how their town is spelled, or lives in one of the unincorporated places with
   names like "Atk. & Gil. Academy Grant", needs to be able to scroll to it. */
function list(q){
  const box=document.getElementById(ID.list);
  const rows=q?TOWNS.filter(t=>t.toLowerCase().includes(q.toLowerCase())):TOWNS;
  box.innerHTML=rows.length?rows.map(t=>{
    const w=wardsOf(t);
    return `<button class="townrow ${t===town?'sel':''}" data-town="${esc(t)}">
      <span>${esc(t)}</span>${w.length>1
        ?`<span class="wct">${w.length} wards</span>`:""}</button>`;}).join("")
   :`<p class="note">Nothing matches that.</p>`;
}

// The same slug build_town_pages.py writes. Two places compute it because
// one is Python at build time and one is JavaScript in the browser; they are
// checked against each other by preflight rather than trusted to agree.
function slugOf(t,w){
  const s=String(t).toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"");
  return (w&&w!=="0")?`${s}-ward-${w}`:s;
}

function reps(county,district){
  return L.filter(m=>m.chamber==="H"&&m.county===county&&
    num(m.district)===num(district));
}
function senators(dist){
  return L.filter(m=>m.chamber==="S"&&num(m.district)===num(dist));
}
function people(list){
  return list.length?`<div class="grid">${list.map(m=>
    `<div class="mem"><a href="${m.slug?`legislator/${esc(m.slug)}.html`
       :"legislators.html"}">${esc(m.display_plain||m.name)}</a>
     <span class="chip p-${esc((m.party||"X")[0])}">${esc((m.party||"?")[0])}</span>
     ${m.towns&&m.towns.length>1?`<span style="color:var(--ink-2);font-size:12px">
       also ${esc(m.towns.filter(x=>x!==town).slice(0,3).join(", "))}</span>`:""}
     </div>`).join("")}</div>`
    :`<p class="note">No sitting member matched to this district.</p>`;
}

function show(){
  const out=document.getElementById(ID.out);
  if(!town){out.innerHTML="";return;}
  const seats=T[town]||[], dw=D[town]||{}, ws=wardsOf(town);
  // A city's wards fall in different districts, so showing every seat in the
  // city at once buries the answer. Dover has six wards and eleven
  // representatives; a resident of ward 3 wants the ones who represent ward 3.
  const picker=ws.length>1?`<p style="margin:0 0 8px;font-size:14px;
    color:var(--ink-2)">${esc(town)} is divided into wards. Choose yours:</p>
    <div class="wards">${ws.map(w=>
      `<button class="wbtn ${w===ward?'sel':''}" data-ward="${esc(w)}">
        Ward ${esc(w)}</button>`).join("")}</div>`:"";

  let body="";
  if(ws.length>1&&!ward){
    body=`<p class="note">Select a ward to see who represents you. Your ward is on
      your voter registration, and the city clerk can confirm it.</p>`;
  }else{
    const w=ward||ws[0]||"0";
    const hd=houseOf(town,w);
    const dist=dw[w]||{};
    const house=hd.length?hd.map(h=>
      `<p style="margin:14px 0 4px"><b>House</b> &mdash; ${esc(h.county)} district
        ${h.district}${h.seats?` &middot; ${h.seats} seat${h.seats>1?"s":""}`:""}
        ${h.floterial?`<span class="chip" style="margin-left:6px">floterial</span>`:""}
        </p>${people(reps(h.county,h.district))}
        ${h.floterial?`<p class="note" style="margin:6px 0 0">A floterial district
          overlays several towns that each already have their own representative,
          and elects additional members across the combined population. You are
          represented by both.</p>`:""}`).join("")
      :`<p class="note" style="margin-top:14px">No House district on file for this
        ward.</p>`;
    const sen=dist.senate?`<p style="margin:16px 0 4px"><b>Senate</b> — district
      ${dist.senate}</p>${people(senators(dist.senate))}`:"";
    const cou=dist.council?`<p style="margin:16px 0 4px"><b>Executive Council</b> —
      district ${dist.council}</p>
      <p class="note" style="margin:4px 0 0">The Executive Council approves state
      contracts, judicial nominations and pardons. Its members are elected but
      rarely covered, and this site does not track their votes.</p>`:"";
    // The congressional district was in districts.json all along and had
    // never been shown, so a reader who came here to find out who represents
    // them was told about two of their four elected bodies.
    const con=dist.congress?`<p style="margin:16px 0 4px"><b>US House</b> —
      New Hampshire district ${dist.congress}</p>`:"";
    // And the whole answer, on a page that can be shared, printed or found in
    // a search. "Who represents Concord Ward 3" is a question people type.
    const full=`<p style="margin:18px 0 0"><a href="town/${slugOf(town,w)}.html"
      ><b>Everyone who represents ${esc(town)}${ws.length>1?` Ward ${esc(w)}`:""}</b>,
      with how to reach them &#8594;</a></p>`;
    body=house+sen+cou+con+full;
  }
  out.innerHTML=`<div class="card"><h2 style="margin:0 0 10px">${esc(town)}
    ${ward&&ws.length>1?`<span style="font-weight:400;color:var(--ink-2)">
      · Ward ${esc(ward)}</span>`:""}</h2>${picker}${body}</div>`;
}

document.addEventListener("click",e=>{
  const t=e.target.closest("[data-town]");
  if(t){ town=t.dataset.town;
    const ws=wardsOf(town); ward=ws.length>1?null:(ws[0]||"0");
    list(document.getElementById(ID.q).value); show();
    document.getElementById(ID.out).scrollIntoView({block:"nearest"}); return; }
  const w=e.target.closest("[data-ward]");
  if(w){ ward=w.dataset.ward; show(); }
});
document.getElementById(ID.q).addEventListener("input",e=>list(e.target.value));
})();
</script>"""


HOME_JS = """
<script>
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fd=d=>{if(!d)return"";const[y,m,dd]=d.split("-");
  return new Date(y,m-1,dd).toLocaleDateString("en-US",{month:"short",day:"numeric"});};
// If the nightly build stops running, nobody should be reading month-old data
// believing it is current. The banner degrades into saying so.
// Anchored to the site root, not to the page. legislators.html is served at
// /legislators, and a legislators/ folder of per-member data sits beside it --
// so /legislators can be redirected to /legislators/, and a relative
// "legislators/377204.json" then resolves to /legislators/legislators/... and
// 404s. The bill page had the same trap and it cost an evening.
window.DATA=window.DATA||((f)=>new URL(f, location.origin+"/").href);
fetch(DATA("build.json")).then(r=>r.json()).then(B=>{
  const el=document.getElementById("fresh"); if(!el||!B.finished)return;
  const days=Math.floor((Date.now()-new Date(B.finished))/86400000);
  const failed=(B.steps||[]).filter(s=>s.status==="failed").map(s=>s.step);
  const when=new Date(B.finished).toLocaleString("en-US",
    {month:"short",day:"numeric",hour:"numeric",minute:"2-digit"});
  let cls="ok", msg=`Data rebuilt ${when}`;
  if(days>=3){cls="stale";msg=`Data last rebuilt ${when} — ${days} days ago`;}
  if(failed.length){cls="stale";
    msg+=`. ${failed.length} build step${failed.length>1?"s":""} failed, so some `
       +`sections may be incomplete.`;}
  el.className="fresh "+cls;
  el.innerHTML=`<span class="fdot"></span>${esc(msg)}`;
}).catch(()=>{});

// Anchored to the site root, not to the page. legislators.html is served at
// /legislators, and a legislators/ folder of per-member data sits beside it --
// so /legislators can be redirected to /legislators/, and a relative
// "legislators/377204.json" then resolves to /legislators/legislators/... and
// 404s. The bill page had the same trap and it cost an evening.
window.DATA=window.DATA||((f)=>new URL(f, location.origin+"/").href);
fetch(DATA("home.json")).then(r=>r.json()).then(H=>{
  const c=H.counts||{}, k=c.by_kind||{}, S=H.status||{};

  const PHASE={"in session":["live","In session"],
               "veto day pending":["wait","Awaiting Veto Day"],
               "between sessions":["wait","Between sessions"],
               "out of session":["off","Out of session"]};
  const ph=PHASE[(S.phase||"").toLowerCase()]||["off",S.phase||"Status unknown"];
  const ms=(S.milestones||[])[0];
  const stale=S.stale_days>45;
  document.getElementById("state").innerHTML=`
    <div class="statebox ${ph[0]}">
      <div class="stateline"><span class="dot"></span><b>${esc(ph[1])}</b>
        ${S.last_session?`<span class="statemeta">last floor session
          ${fd(S.last_session)}</span>`:""}</div>
      ${S.headline?`<p class="statehead">${esc(S.headline)}</p>`:""}
      ${S.note?`<p class="statenote">${esc(S.note)}</p>`:""}
      ${ms?`<p class="statenote"><b>Next: ${esc(ms.label)}</b>, ${fd(ms.date)}.
        ${esc(ms.note||"")}</p>`:""}
      ${S.hearings_next_14?`<p class="statenote">${S.hearings_next_14} hearing${
        S.hearings_next_14===1?"":"s"} scheduled in the next two weeks.</p>`:""}
      <p class="statenote" style="margin-top:10px">
        ${(S.live||[]).map(l=>`<a href="${esc(l.url)}" target="_blank"
          rel="noopener">${esc(l.chamber)} livestream</a>`).join(" &nbsp;·&nbsp; ")}
        <span class="statemeta">these open whatever is streaming now, or the
        channel if nothing is</span></p>
      ${stale?`<p class="statenote" style="color:var(--st-veto)">This summary was
        last updated ${S.stale_days} days ago and may be out of date.</p>`
        :(S.updated?`<p class="statemeta" style="margin-top:8px">Summary updated
          ${fd(S.updated)}</p>`:"")}
    </div>`;
  const C=H.composition||{};
  // Five seats do not want a proportional bar; list them. The Council is also
  // executive branch, so it is set apart from the two chambers rather than
  // stacked with them as though it were a third one.
  const council=()=>{
    const c=C.council; if(!c)return "";
    const rows=(c.members||[]).map(m=>
      `<tr><td style="width:96px">District ${esc(m.district)}</td>
       <td>${m.name?`${esc(m.name)} <span class="chip p-${esc(m.party||"V")}">${
         esc(m.party||"?")}</span>`
        :`<span style="color:var(--ink-2)">vacant</span>`}</td></tr>`).join("");
    return `<div class="comp">
      <div class="compline"><b>Executive Council</b>
        <span class="statemeta">${c.sitting} of ${c.seats} seats filled${
          c.vacant?`, ${c.vacant} vacant`:""} \u00b7 ${
          (c.parties||[]).map(p=>`${p.n} ${esc(p.code)}`).join(", ")}</span></div>
      <table><tbody>${rows}</tbody></table>
      ${c.note?`<p class="statemeta" style="margin:8px 0 0">${esc(c.note)}</p>`:""}
      ${c.updated?`<p class="statemeta">Council and governor entered by hand,
        updated ${fd(c.updated)}.</p>`:""}</div>`;};
  const gov=()=>{
    const g=C.governor; if(!g)return "";
    return `<div class="comp"><div class="compline"><b>Governor</b>
      <span class="statemeta">${esc(g.name)}
      <span class="chip p-${esc(g.party||"V")}">${esc(g.party||"?")}</span></span>
      </div>
      <p class="statemeta" style="margin:4px 0 0">Signs or vetoes every bill that
      passes both chambers. A veto stands unless two thirds of those voting in
      each chamber vote to override.</p></div>`;};

  // Highest office first. Reading down from governor to the 400-seat House
  // matches how people picture the structure.
  // The chambers and the vacant seats moved to the legislators page, which is
  // where somebody looking for who holds a seat already is. What is left here
  // is the executive branch, which is not a legislature and was only ever
  // stacked with them for want of somewhere else to put it.
  const exec=gov()+council();
  const comp=document.getElementById("composition");
  if(comp)comp.innerHTML=exec?`<h2>Who holds office</h2>${exec}`:"";

  document.getElementById("stats").innerHTML=`
    <div class="statgrid">
      <div class="stat"><b>${(c.bills||0).toLocaleString()}</b><span>bills</span></div>
      <div class="stat"><b>${(k.law||0).toLocaleString()}</b><span>became law</span></div>
      <div class="stat"><b>${(k.done||0).toLocaleString()}</b><span>concluded</span></div>
      <div class="stat"><b>${(k.active||0).toLocaleString()}</b><span>still moving</span></div>
      <div class="stat"><b>${(c.votes||0).toLocaleString()}</b><span>recorded votes</span></div>
    </div>`;

  // What is coming sits above what has happened: someone who learns on Tuesday
  // that a hearing is Thursday can still turn up and speak.
  const up=H.upcoming||[];
  document.getElementById("upcoming").innerHTML=up.length
    ?`<h2>Coming up</h2><table><tbody>${up.map(u=>
      `<tr><td style="width:90px">${fd(u.date)}${u.time?` ${esc(u.time)}`:""}</td>
       <td><a href="bills.html#${esc(u.bill)}">${esc(u.bill)}</a>
       — ${esc(u.committee||"")} ${esc(u.what||"")}
       ${u.venue?`<span style="color:var(--ink-2)">· ${esc(u.venue)}</span>`:""}</td>
       </tr>`).join("")}</tbody></table>
      <p class="note">Anyone may attend a public hearing and speak, or sign in for or
      against without speaking.</p>`
    :`<h2>Coming up</h2><p class="note">No hearings scheduled in the next two weeks.
      The General Court sits from January to June.</p>`;

  document.getElementById("recent").innerHTML=`<h2>Latest activity</h2>
    <table><tbody>${(H.recent||[]).map(r=>
      `<tr><td style="width:80px">${fd(r.date)}</td>
       <td><a href="bills.html#${esc(r.bill)}">${esc(r.n)}</a>
       <span style="color:var(--ink-2)">${esc(r.title)}</span><br>
       <span style="font-size:12px">${esc(r.what)}</span></td></tr>`).join("")}
    </tbody></table>`;

  // Closest votes and most contested are computed and stored, but not shown.
  // Both invite a reading the site does not want to make, and the page is
  // better without them for now.
  const cl=[], co=[];
  document.getElementById("notable").innerHTML=
    `${cl.length?`<h2>Closest floor votes</h2><table><tbody>${cl.map(v=>
      `<tr><td style="width:86px"><b>${v.y}\u2013${v.nn}</b></td>
       <td><a href="bills.html#${esc(v.bill)}">${esc(v.n)}</a>
       <span style="color:var(--ink-2)">${esc(v.q||"")}, ${fd(v.date)}</span><br>
       <span style="font-size:12px">${esc(v.title)}</span></td></tr>`).join("")}
       </tbody></table>`:""}
     ${co.length?`<h2>Most contested</h2>
       <p class="note">Bills that took the most recorded floor votes to settle.
       Committee and executive session votes are excluded: a committee's
       recommendation is not binding on the chamber, and a 10\u20139 in committee
       is a different thing from a 201\u2013199 on the floor. This counts the
       record, not what people read here \u2014 nothing on this site tracks
       visitors.</p>
       <table><tbody>${co.map(b=>
       `<tr><td style="width:86px">${b.nrc} votes</td>
        <td><a href="bills.html#${esc(b.id)}">${esc(b.n)}</a>
        <span style="color:var(--ink-2)">${esc(b.title)}</span></td></tr>`).join("")}
       </tbody></table>`:""}`;

  // Both chambers. They sit on different days, so showing one hides the other.
  const ls=(H.latest_sessions&&H.latest_sessions.length)
    ? H.latest_sessions : (H.latest_session?[H.latest_session]:[]);
  document.getElementById("session").innerHTML=ls.length
    ?`<h2>Most recent floor sessions</h2><div class="twoup">${ls.map(v=>
      `<div><p style="margin:0 0 6px;font-size:14px"><b>${esc(v.chamber||"")}</b>
        <span class="statemeta">${fd(v.date)}</span></p>
        <div class="player"><div class="pstub" data-embed="${esc(v.video_id)}">
          <span>&#9654;</span><span>Play</span></div></div></div>`).join("")}</div>`
    :"";
});
document.addEventListener("click",e=>{
  const st=e.target.closest("[data-embed]");
  if(st)st.outerHTML=`<iframe allow="autoplay" allowfullscreen
    src="https://www.youtube-nocookie.com/embed/${st.dataset.embed}?autoplay=1"
    title="Floor session"></iframe>`;
});
document.getElementById("hq").addEventListener("keydown",e=>{
  if(e.key==="Enter")location.href="bills.html?q="+encodeURIComponent(e.target.value);
});
document.getElementById("hgo").addEventListener("click",()=>{
  location.href="bills.html?q="+encodeURIComponent(document.getElementById("hq").value);
});
</script>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "style.css").write_text(
        CSS.replace("__PALETTE__", palette()), encoding="utf-8")

    # bills.html is the one page written by hand rather than generated, and
    # nothing in the pipeline was copying it into the output folder. So an edit
    # to it sat at the project root while the deploy shipped whatever was in
    # site/ -- which looks exactly like the edit having no effect, and cost a
    # round more than once. Copied here, next to the stylesheet it needs.
    # bills.html and the two files it loads. They are written by hand rather
    # than generated, and nothing in the pipeline was copying bills.html into
    # the output folder -- so an edit sat at the project root while the deploy
    # shipped whatever was in site/, which looks exactly like the edit having
    # no effect and cost a round more than once.
    #
    # app.css and app.js used to be a <style> and a <script> inside the page.
    # They are files of their own so a second page can load the SAME renderer
    # rather than a copy of it, and so a reader who opens six bills downloads
    # 110KB once instead of six times.
    # bills.html is copied rather than built through shell.page, so the asset
    # URLs get versioned here instead. Without it the search page holds a
    # four-hour-old app.js after a publish, the same way every other page did
    # until 7 September.
    import shell as _S
    _q = _S.asset_query(out)
    for name in ("bills.html", "app.css", "app.js"):
        src = Path(name)
        if not src.exists():
            continue
        dst = out / name
        body = (_S.bust(src.read_text(encoding="utf-8"), _q).encode("utf-8")
                if name.endswith(".html") else src.read_bytes())
        if not dst.exists() or dst.read_bytes() != body:
            dst.write_bytes(body)
            print(f"copied {name} into the site folder"
                  + (f" (assets at {_q})" if name.endswith(".html") else ""))

    legs = json.loads((out / "legislators.json").read_text(encoding="utf-8")) \
        if (out / "legislators.json").exists() else []
    towns = json.loads((out / "towns.json").read_text(encoding="utf-8")) \
        if (out / "towns.json").exists() else {}


    # The "Your town" page was here. The finder it held is the top of the
    # legislators page, built from the same towns.json by the same TOWN_JS,
    # so this page was a second address for one thing and a seventh item in
    # the nav.
    # Render the home page content at build time as well as in the browser.
    # Fetching home.json works for a visitor with JavaScript, but a crawler --
    # and a reader on a slow connection before the JSON arrives -- sees an empty
    # page. Everything below is in the HTML as shipped; the script then replaces
    # it with the identical content, so nothing is duplicated on screen.
    H = json.loads((out / "home.json").read_text(encoding="utf-8")) \
        if (out / "home.json").exists() else {}
    S = H.get("status", {})
    C = H.get("composition", {})
    c = H.get("counts", {})
    k = c.get("by_kind", {})

    def esc(x):
        return (str(x or "").replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))

    def fd(d):
        if not d or len(str(d)) < 10:
            return esc(d)
        m = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
             "Oct", "Nov", "Dec"]
        try:
            return f"{m[int(d[5:7]) - 1]} {int(d[8:10])}"
        except (ValueError, IndexError):
            return esc(d)

    static_state = ""
    if S.get("headline") or S.get("phase"):
        ph = {"in session": ("live", "In session"),
              "veto day pending": ("wait", "Awaiting Veto Day"),
              "between sessions": ("wait", "Between sessions"),
              "out of session": ("off", "Out of session")}.get(
                  (S.get("phase") or "").lower(), ("off", S.get("phase") or ""))
        ms = (S.get("milestones") or [{}])[0]
        static_state = (
            f'<div class="statebox {ph[0]}"><div class="stateline">'
            f'<span class="dot"></span><b>{esc(ph[1])}</b></div>'
            + (f'<p class="statehead">{esc(S["headline"])}</p>'
               if S.get("headline") else "")
            + (f'<p class="statenote">{esc(S["note"])}</p>' if S.get("note") else "")
            + (f'<p class="statenote"><b>Next: {esc(ms.get("label"))}</b>, '
               f'{fd(ms.get("date"))}. {esc(ms.get("note"))}</p>' if ms.get("label") else "")
            + "</div>")

    static_stats = ""
    if c:
        static_stats = '<div class="statgrid">' + "".join(
            f'<div class="stat"><b>{v:,}</b><span>{lab}</span></div>'
            for v, lab in ((c.get("bills", 0), "bills"),
                           (k.get("law", 0), "became law"),
                           (k.get("done", 0), "concluded"),
                           (k.get("active", 0), "still moving"),
                           (c.get("votes", 0), "recorded votes"))) + "</div>"

    def static_bar(ch):
        """The party composition of one chamber, with its thresholds.

        Built here rather than in the page's JavaScript because it now lives on
        the legislators page, which has no reason to fetch home.json for it --
        and because a composition that only appears once a script has run is
        one more thing that is not there for a crawler or a screen reader.
        """
        x = C.get(ch)
        if not x:
            return ""
        tot = x.get("seats") or 1
        segs = "".join(
            f'<span class="pseg seg-{esc(pp["code"])}" '
            f'style="width:{100 * pp["n"] / tot:.4f}%" '
            f'title="{esc(pp["name"])}: {pp["n"]}"></span>'
            for pp in x.get("parties", []))
        if x.get("vacant"):
            segs += (f'<span class="pseg seg-V" '
                     f'style="width:{100 * x["vacant"] / tot:.4f}%" '
                     f'title="Vacant: {x["vacant"]}"></span>')
        legend = "".join(
            f'<span><span class="pdot seg-{esc(pp["code"])}"></span>'
            f'{esc(pp["name"])} <b>{pp["n"]}</b></span>'
            for pp in x.get("parties", []))
        if x.get("vacant"):
            legend += (f'<span><span class="pdot seg-V"></span>Vacant '
                       f'<b>{x["vacant"]}</b></span>')
        note = ""
        if x.get("majority"):
            note = (f'<p class="statemeta" style="margin:6px 0 0">A simple '
                    f'majority is {x["majority"]}. A constitutional amendment '
                    f'needs {x.get("three_fifths", "")}, three fifths of the '
                    f'full membership. A veto override needs '
                    f'{esc(x.get("two_thirds_note", ""))}.</p>')
        return (f'<div class="comp"><div class="compline"><b>{esc(x["chamber"])}</b>'
                f'<span class="statemeta">{x["sitting"]} of {x["seats"]} seats '
                f'filled{f", {x['vacant']} vacant" if x.get("vacant") else ""}</span>'
                f'</div><div class="pbar2">{segs}</div>'
                f'<div class="plegend">{legend}</div>{note}</div>')

    vacancies = ""
    if C.get("vacancies"):
        v = C["vacancies"]
        vacancies = (
            f'<details class="vac"><summary>{sum(x["vacant"] for x in v)} vacant '
            f'House seats across {len(v)} districts</summary>'
            '<p class="note" style="margin-top:8px">Seats fall vacant through the '
            'term as members resign or pass away, and are filled by special '
            'election.</p><div class="grid">' + "".join(
                f'<div class="mem">{esc(x["county"])} district {esc(x["district"])}'
                f'{f" — {x['vacant']} seats" if x["vacant"] > 1 else ""}</div>'
                for x in v) + "</div></details>")

    # Built here, after home.json has been read: the legislators page now
    # carries the party composition, so it cannot be written before the
    # data that composition comes from.
    leg_body = f"""<h1>Legislators</h1>
<p class="lead">Start with your town, or search the full roster below.</p>
<div class="card" style="margin-bottom:26px">
  <label for="tq" style="position:absolute;left:-9999px">Your town</label>
  <input id="tq" type="search" placeholder="Your town, e.g. Dover" disabled>
  <p class="count" id="tcount">Loading\u2026</p>
  <div class="townlist" id="towns"></div><div id="tout" style="margin-top:16px"></div>
</div>
<h2 style="margin-top:0">Everyone</h2>
<p class="lead">{len(legs)} members, with their committees and full roll call
record. Searching a committee name lists everyone on it.</p>
<label for="q" style="position:absolute;left:-9999px">Search legislators</label>
<input id="q" type="search" placeholder="Name, town, county, party, or committee" disabled>
{('<div class="comp-wrap">' + static_bar("S") + static_bar("H") + vacancies + "</div>")
 if C else ""}
<p class="count" id="count">Loading…</p><div id="out"></div>"""
    (out / "legislators.html").write_text(
        shell("Legislators | Granite Record", "legislators.html", leg_body,
              desc="Every member of the New Hampshire House and Senate: their "
                   "district, their party, the bills they sponsored and every "
                   "recorded vote they cast.",
              wide=True, script=TOWN_JS + LEG_JS), encoding="utf-8")

    static_up = ""
    if H.get("upcoming"):
        static_up = "<h2>Coming up</h2><table><tbody>" + "".join(
            f'<tr><td>{fd(u.get("date"))}</td><td>'
            f'<a href="bills.html#{esc(u.get("bill"))}">{esc(u.get("bill"))}</a>'
            f' — {esc(u.get("committee"))} {esc(u.get("what"))}</td></tr>'
            for u in H["upcoming"][:12]) + "</tbody></table>"

    static_recent = ""
    if H.get("recent"):
        static_recent = "<h2>Latest activity</h2><table><tbody>" + "".join(
            f'<tr><td>{fd(r.get("date"))}</td><td>'
            f'<a href="bills.html#{esc(r.get("bill"))}">{esc(r.get("n"))}</a> '
            f'{esc(r.get("title"))}<br><span style="font-size:12px">'
            f'{esc(r.get("what"))}</span></td></tr>'
            for r in H["recent"][:12]) + "</tbody></table>"

    home_body = f"""<h1>Granite Record</h1>
<p class="lead">A searchable record of the New Hampshire General Court: what each
bill does, who sponsored it, when it was heard, how every legislator voted, and
where in the recording it was discussed.</p>
<div class="searchbig">
  <label for="hq" style="position:absolute;left:-9999px">Search bills</label>
  <input id="hq" type="search" placeholder="Bill number, or a few words from the title">
  <button id="hgo">Search</button>
</div>
<div id="stats">{static_stats}</div>
<div class="entry">
  <a href="bills.html"><b>Browse bills</b><span>Search by committee, topic, sponsor,
    status or the day it was voted on</span></a>
  <a href="legislators.html"><b>Find your legislators</b><span>By town: your House,
    Senate, Executive Council and congressional districts</span></a>
  <a href="learn.html"><b>Learn</b><span>How a bill moves, what the shorthand
    means, and how to testify</span></a>
</div>
<div id="fresh" class="fresh"></div>
<div id="state">{static_state}</div>
<div id="upcoming">{static_up}</div>
<div id="session"></div>
<div id="recent">{static_recent}</div>
<div id="composition"></div>
<div id="notable" hidden></div>
<h2>Follow along</h2>
<p>Two feeds, no account and no email address. Any reader will take these, and
nothing here tracks who is subscribed because nothing here knows.</p>
<ul class="reading">
<li><a href="feed/hearings.xml">Upcoming hearings</a> — what is scheduled in the
next two weeks, in time to attend or sign in.</li>
<li><a href="feed/all.xml">All activity</a> — every recorded action, newest first.</li>
</ul>
<p class="note">Every bill has its own feed too, linked from its page, along with
one per committee and one per subject.</p>"""
    (out / "index.html").write_text(
        shell("Granite Record \u2014 the New Hampshire legislative record",
              "index.html", home_body, script=HOME_JS,
              desc="Every bill, vote, hearing and floor debate of the New "
                   "Hampshire General Court, linked to the moment in the "
                   "recording where it happened."),
        encoding="utf-8")

    # learn.html belongs to build_civics.py now: it is the way into eleven
    # topic pages rather than one page of its own, and two builders writing
    # the same address means whichever runs last wins. LEARN below is kept
    # because its prose was redistributed into civics.py rather than
    # rewritten, and it is the thing to diff against if a passage there
    # looks wrong.
    (out / "about.html").write_text(
        shell("About | Granite Record", "about.html", ABOUT,
              desc="How Granite Record is built, where every fact on it comes "
                   "from, and how to report something that is wrong."),
        encoding="utf-8")

    # THERE WAS NO 404 PAGE. Cloudflare Pages treats a project with no
    # top-level 404.html as a single-page app: every address it cannot find
    # is answered with the home page and a 200. A mistyped bill -- or a bill
    # number that exists in another year -- looked like a working page, and a
    # search engine would index the home page under every one of them.
    #
    # It is served AT the address that was asked for, so every link in it
    # must be absolute: from /bill/2026/hb99999 a relative "style.css" is
    # /bill/2026/style.css. And it is not a page to index, so it carries no
    # canonical address and asks not to be.
    page404 = shell("No page at this address | Granite Record", "", NOT_FOUND,
                    desc="There is no page at this address.")
    page404 = re.sub(r'(href|src)="(?!https?:|/|#|mailto:)([^"]+)"', r'\1="/\2"',
                     page404)
    page404 = re.sub(r'<link rel="canonical"[^>]*>',
                     '<meta name="robots" content="noindex">', page404)
    (out / "404.html").write_text(page404, encoding="utf-8")

    print(f"wrote legislators.html ({len(legs)} members), "
          f"about.html, 404.html, style.css -> {out}/  (learn.html: build_civics.py)")
    if not legs:
        print("  legislators.json missing — run build_site_v2.py first")


if __name__ == "__main__":
    main()
