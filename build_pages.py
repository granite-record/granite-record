#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.117
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
import about_figures
import bill_order as BO
import html as _html
import shell as _shell
import seating
import json
import re
import shutil
from collections import OrderedDict, defaultdict
from pathlib import Path

# The palette is app.css's, read at build time rather than copied. The copy
# that used to live here had already drifted: --st-veto was #7C2D3A in one
# file and #8C4A2F in the other, the same token name naming a plum and a rust,
# and nothing could see it because each file was internally consistent.
def palette(src="app.css"):
    """The palette: the light block and the dark block that follows it.

    This used to stop at the first `}` after --sans, which was the whole
    palette for as long as there was only one. With a
    @media(prefers-color-scheme:dark) block under it that slice carries half
    a scheme -- style.css would define --surface:#fff and never redefine it,
    so the four pages built here (the home page, the legislator index, About
    and 404) would have stayed white while every record page went dark, and
    the drift check in preflight would have passed, because the tokens it
    compares would still have agreed.

    The end is a marker rather than a brace count, so that adding a token or
    a second media query cannot silently truncate it; a missing marker raises
    here instead of shipping a half-built stylesheet.
    """
    text = Path(src).read_text(encoding="utf-8")
    i = text.index(":root{")
    return text[i:text.index("/* PALETTE END")].rstrip()



def themer(part, src="bills.html"):
    """One piece of the theme control, read out of bills.html.

    READ, NOT COPIED, for the same reason palette() reads app.css. bills.html
    is the template every record page is built from, so the control has to
    live there; these four pages are built here instead and need the same
    three pieces. A second copy would be two controls that drift, and the
    drift would show as the toggle working on a bill and not on the home page.

    part is "HEAD" (the pre-paint script), "BTN" (the nav button) or "JS"
    (the handler). A missing marker raises rather than quietly emitting a page
    with no control on it.
    """
    text = Path(src).read_text(encoding="utf-8")
    a = text.index(f"<!-- THEMER:{part} -->")
    b = text.index(f"<!-- /THEMER:{part} -->")
    return text[a:b].split("-->", 1)[1].strip()


def shared(src="app.css"):
    """The rules both stylesheets need, read rather than copied.

    Same reason as palette(): a component pasted into two files diverges on
    the first fix, and each file goes on looking internally consistent while
    it happens. The hearing calendar is on the home page, which is built here
    and loads style.css, and is going on the committee pages, which app.js
    renders against app.css. One definition, between the markers.
    """
    text = Path(src).read_text(encoding="utf-8")
    a = text.index("/* SHARED:START")
    b = text.index("/* SHARED:END")
    return text[a:b].rstrip()


def pages_region(src="app.css"):
    """The rules only the pages this file writes need, read out of app.css.

    THERE IS NO SECOND STYLESHEET. These pages once had 24 KB of CSS of their
    own here, against app.css's 119 KB for the record pages, and a fix landed
    in one of them at a time: eleven font sizes in one file and more in the
    other, a component drawn twice, DESIGN.md's rules kept by hand in two
    places. The block lives in app.css between PAGES:START and PAGES:END,
    scoped to body.pg, and this reads it -- the same trick palette() and
    shared() already used, applied to the rest of the file.

    So style.css is a view of app.css: palette, the shared region, and the
    page region, in that order. There is one stylesheet to edit.
    """
    text = Path(src).read_text(encoding="utf-8")
    a = text.index("/* PAGES:START")
    b = text.index("/* PAGES:END")
    return text[a:b].rstrip()


CSS = """
__PALETTE__
__SHARED__
__PAGES__
"""


FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600'
         '&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=IBM+Plex+Mono:wght@500'
         '&display=swap" rel="stylesheet">')


# The menu button a phone header carries. Written here and in bills.html,
# which is the same duplication the nav itself has always had and for the
# same reason: one of them is the template every record page inherits.
# The SEARCH button is not here -- find.js mounts its own, and a second one
# would be two controls doing one job.
MENU_BTN = ('<button class="navmenu" id="navmenu" type="button" aria-expanded="false" aria-controls="navdrop" aria-label="Sections"><svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><path d="M3.2 6h13.6M3.2 10h13.6M3.2 14h13.6"/></svg></button>')


# THE HEADER THAT REPLACED THE VERSION QUERY.
#
# style.css, app.css and app.js used to carry "?v=<content hash>" in every
# page that named them, so that a deploy could not serve yesterday's script
# with today's page. Measured on the live site, that guard was needed:
# Cloudflare Pages hands out app.css as `public, max-age=14400,
# must-revalidate` -- four hours -- while it already serves HTML and JSON as
# `public, max-age=0, must-revalidate`, always revalidated and never stale.
#
# So the three asset files are told to behave the way the HTML already does,
# and the pages name them plainly. The query cost a gigabyte a publish: it
# lives inside the HTML, so one changed byte of a stylesheet rewrote all
# 34,000 record pages and every one of them became a file Cloudflare had
# never seen.
#
# Pages reads this file from the root of the output directory and it is not
# counted as an asset. Two-space indent under each path is the format.
HEADERS = """# Written by build_pages.py. Not an asset; Pages reads it.
#
# The same freshness HTML gets here by default: keep the file, ask before
# reusing it. It is what makes naming these files without a version query
# safe -- see THE VERSION QUERY, GONE in DESIGN.md.
/app.js
  Cache-Control: public, max-age=0, must-revalidate
/app.css
  Cache-Control: public, max-age=0, must-revalidate
/style.css
  Cache-Control: public, max-age=0, must-revalidate
/find.js
  Cache-Control: public, max-age=0, must-revalidate
/billmatch.js
  Cache-Control: public, max-age=0, must-revalidate
# The two files a page reads to say what is true today: the home page's own
# summary, and the header search's index of members, committees and towns. A
# cached copy of either is a page contradicting itself -- the home page's
# built HTML once said 39 hearings while its script, reading a cached
# home.json, said 4.
/home.json
  Cache-Control: public, max-age=0, must-revalidate
/find.json
  Cache-Control: public, max-age=0, must-revalidate

# THE PUBLISHED RECORD IS READABLE FROM ANYWHERE, which is what /data already
# tells programmers it is. Without this header a browser will not let a page on
# another origin read these files, so the promise held for curl and for a
# script on a server and quietly failed for anyone building in a browser --
# which is most of the people that page is addressed to.
#
# Nothing here is private: these are the same public files the site's own pages
# fetch, and they are already served to anyone who asks for them directly. The
# header does not widen who can read them, only which programs can.
#
# Deliberately NOT applied to the whole site. A wildcard on every path would
# also cover /_headers, /_redirects and anything added later without anybody
# thinking about it; these four are the tables /data documents.
/index.json
  Access-Control-Allow-Origin: *
/idx/*
  Access-Control-Allow-Origin: *
/legislators.json
  Access-Control-Allow-Origin: *
/rollcalls_index.json
  Access-Control-Allow-Origin: *

# And the bulk tables, because they are the half of that promise a programmer
# is most likely to want: 19 CSVs and the manifest that describes them. The
# manifest is the entry point -- /data says a program can find what is here in
# one request -- and a manifest a browser cannot read is a directory to files
# it also cannot read.
/data/manifest.json
  Access-Control-Allow-Origin: *
/data/*.csv
  Access-Control-Allow-Origin: *
"""

# Tab addresses, served their record's page: see where this is written.
# "videos" is kept alongside "hearings" deliberately. The tab was relabelled --
# it lists a bill's sittings and a recording only where one exists, and
# recordings begin in May 2020, so for fifteen terms it read "Videos" over
# entries that all said "No recording exists". Both addresses go in
# _redirects: the new one because that is what the page now writes, the old
# one because it has been published and indexed.
BILL_TAB_SLUGS = ("text", "votes", "hearings", "videos", "reports",
                  "sponsors", "documents")
MEMBER_TAB_SLUGS = ("cosponsored", "votes")
COMMITTEE_TAB_SLUGS = ("sessions",)
REDIRECTS = ("# Written by build_pages.py. Not an asset; Pages reads it.\n"
             + "".join(f"/bill/:year/:bill/{s} /bill/:year/:bill 200\n" for s in BILL_TAB_SLUGS)
             + "".join(f"/legislator/:who/{s} /legislator/:who 200\n" for s in MEMBER_TAB_SLUGS)
             + "".join(f"/committee/:code/{s} /committee/:code 200\n" for s in COMMITTEE_TAB_SLUGS))


# WHAT A POWER USER NEEDS, IN THE FOOTER, WHERE THEY WILL LOOK FOR IT.
# data.html and manifest.json describe every table, and nothing linked them
# from the bottom of a page, so the only way to find the bulk downloads was to
# already know they existed. The same line says when the data was last
# rebuilt: a reader deciding whether to trust a status should not have to go
# to the home page to find out how old it is.
#
# The date is read from build.json rather than baked in, because this function
# runs at step 15 of 22 and build.json is written after step 22 -- a baked
# stamp would always be a few minutes early and would differ page to page.
# It is one small cached request, and the line simply does not appear if the
# fetch fails.
FOOT_JS = (
    '<script>fetch(new URL("build.json",location.origin+"/").href)'
    '.then(r=>r.json()).then(B=>{'
    'var e=document.getElementById("built");'
    'if(!e||!B.finished)return;'
    'e.textContent=" Data rebuilt "+new Date(B.finished)'
    '.toLocaleDateString("en-US",{year:"numeric",month:"long",day:"numeric"})+".";'
    '}).catch(function(){});</script>')

# The one sentence that explains the bulk data, used in both footers so they
# cannot drift. "Every table" is literal: data.html builds from the same
# manifest the tables are written from.
# THE REPOSITORY, NAMED ONCE. The footer links it, and so do the Data page
# and "How this is made" -- three places for three different readers, and one
# constant so a move cannot leave two of them pointing at nothing.
REPO = "https://github.com/granite-record/granite-record"

# The directory link that used to sit in the footer has moved to the Data
# page: in a grey band it was one link among four and could not say what it
# was for, and on that page it gets a heading and the sentence that matters --
# every record as a plain link, no JavaScript, which is also what a crawler
# follows. The footer's own links are written inline in the two footers now,
# so there is no constant here to drift out of step with bills.html.


# ===================================================== the hearing calendar ==
# home.json's `upcoming` is ONE ROW PER BILL -- date, time, committee, what,
# venue, bill -- and a reader does not think in bill-rows. They think "who is
# meeting this week, about how much, and can I speak". Four rows of HB/SB
# numbers was a list of bills that happened to have dates on them; the same
# four rows grouped are two meetings.
#
# So the grouping is (date, time, committee, what, venue) and the bills fall
# inside it. Nothing new is fetched: the field names below are the ones
# build_site_v2 already writes.
#
# Titles are resolved HERE, at build time, out of site/idx/<term>.json -- 1.19
# MB that the home page must not load to print four of them. If the index is
# not on disk yet the bill still gets its number and its link and the build
# says how many titles it could not resolve, because a calendar that silently
# prints bare bill numbers looks like a calendar that is working.
# How much of Latest activity the home page shows, and where the rest is.
# Five is a glance; the twelve it showed before was most of a phone screen for
# a list nobody reads to the end. The overflow goes to the bill search, which
# sorts by most recent action and does it better than a table can.
RECENT_SHOWN = 5
RECENT_MORE = ('<p class="actmore"><a class="morebtn" href="/bills?sort=recent">'
               'See all recent activity &rarr;</a></p>')

# THE COLOURS ARE THE GENERAL COURT'S OWN, because staff already read its
# schedule by them: blue a hearing, green a meeting (work sessions, study and
# statutory committees), orange an executive session, red a committee of
# conference -- the legend fetch_schedule.py quotes. The floor, which that
# schedule does not colour, has one of its own. Until 24 September a hearing
# was gold and every work session, conference and floor sitting fell to the
# orange that means executive session there. A kind not named here keeps the
# neutral k-other rather than borrowing a colour that means something else.
MEET_KIND = {"public hearing": ("Public hearing", "k-hearing"),
             "hearing": ("Public hearing", "k-hearing"),
             "executive session": ("Executive session", "k-exec"),
             "work session": ("Work session", "k-meet"),
             "subcommittee work session": ("Subcommittee work session", "k-meet"),
             "full committee work session": ("Full committee work session", "k-meet"),
             "study committee": ("Study committee", "k-meet"),
             "statutory committee": ("Statutory committee", "k-meet"),
             "committee of conference": ("Committee of conference", "k-conf"),
             "floor debate": ("Floor session", "k-floor")}

# The key under a week's heading: each colour once, in the order a reader
# meets them, worded as the chips are.
MEET_LEGEND = (("k-hearing", "Public hearing"),
               # Most green cards say "Statutory committee", so the key names it.
               ("k-meet", "Work session, study or statutory committee"),
               ("k-exec", "Executive session"),
               ("k-conf", "Committee of conference"),
               ("k-floor", "Floor session"))


def meeting_key(u):
    """What makes one meeting out of a handful of `upcoming` bill rows.

    ONE DEFINITION, BECAUSE TWO PLACES COUNT IT. The calendar groups by this
    tuple and the status box above it states the number of groups; when the
    grouping lived only inside calendar_html the box counted the rows instead
    and said "39 hearings scheduled in the next two weeks" over a fortnight
    holding eight meetings -- and no hearing at all. Nothing can drift now
    without moving both.

    NOT THE TIME. The docket gives every BILL its own slot inside a meeting --
    Executive Departments on 21 January runs 09:00, 09:10, 09:20 and on down
    its fifteen bills -- so a key holding the time made one meeting into one
    card per bill. The busiest week of 2026 came out as 356 meetings where it
    holds 68, and a committee that had set aside a morning read as fifteen
    committees that each met for ten minutes.

    It has not shown yet because the fortnight this draws is out of session
    and its meetings carry a bill or two each. January is when it would have
    shown, on the page that gets the most readers, in the month that gets the
    most of them. The card states the span instead, 09:00-13:50, which is
    what the General Court's own schedule prints.

    NOR THE KIND. A committee that holds a public hearing in the morning and
    an executive session after it has had one day, not two, and a reader
    scanning a week wants to see the committee once: "they should only take
    up one entry and just list all of the scheduled items in order." Keyed on
    the kind it appeared twice, which across the record since 2025 is 1,452
    entries where the room holds 1,007 -- 34% of committee-days do more than
    one thing.

    The kinds are not lost, they are shown differently: the card carries a
    divided colour bar, one segment per kind, and its body lists the day's
    items in order with the time each was set for.

    NOR THE ROOM. Two rooms looked like two meetings until a real day said
    otherwise: Ways and Means on 30 September is a subcommittee at 09:30 in
    GP 228, then the full committee at 10:00 and 10:30 in GP 234. That is one
    committee having one working day, and a reader scanning the week wants it
    once. The room is a property of each item, not of the entry, and is shown
    on the line it belongs to -- with the entry naming it once when every item
    shares it.

    So the key is the day and the committee, and nothing else.
    """
    return (u.get("date") or "", u.get("committee") or "")


# THE FORTNIGHT'S MEETING COUNT IS OFF THE STATUS BOX, at the person's
# word on 19 September. It is not a fact about the state of the General
# Court, which is what the box is for; it is a fact about the calendar,
# which is on the same page saying it better -- by day, by committee and
# by bill. Three renderers wrote it and all three are gone with it: this
# one, HOME_JS's _meetline, and the clock block that counted the days off
# the total. meeting_key() stays: the calendar groups by it.

def calendar_html(out, today=None, rows=None):
    """What is left of this week, by day and then by meeting.

    `today` and `rows` are preflight's: it draws the rail for a fixed date out
    of rows it wrote, rather than out of the clock and proceedings.csv.
    """
    import datetime as _dt
    from collections import OrderedDict
    # build_calendar imports this module, so it is imported here, once both
    # are loaded, rather than at the top where it would be a cycle.
    import build_calendar as BC
    import proceedings

    # main()'s esc is nested inside it and this is module level, so it gets
    # its own -- the same one shell() uses two hundred lines down.
    esc = lambda s: _html.escape(str(s or ""), quote=True)

    # THIS WEEK, FROM TODAY TO SUNDAY, AND ALL OF IT. The rail's own comment
    # said it showed the Calendar tab's week, and it did not: it drew
    # home.json's fortnight, cut at the seventh DATE that had a meeting, so on
    # Wednesday 23 September 2026 it ran to Wednesday 7 October and seven of
    # its nine cards were in other weeks. In session the other limit bit
    # first -- home.json keeps eighty bill rows, and a January day holds 138 --
    # so it stopped partway through one day while calendar.html showed the
    # whole week.
    # And it held committee rows only, where the week page holds the floor.
    #
    # So it reads the week the way the Calendar tab does, out of the same
    # rows through the same function, from today to that week's Sunday, with
    # no cap. home.json's fortnight is left alone: the hearings feed reads it.
    today = today or _dt.date.today()
    weeks = BC.weeks_from(proceedings.load() if rows is None else rows)
    sunday = BC.monday(today) + _dt.timedelta(days=6)
    week = weeks.get(BC.week_key(today)) or {}
    dates = sorted(d for d in week
                   if today.isoformat() <= d <= sunday.isoformat() and week[d])
    nxt = BC.week_key(sunday + _dt.timedelta(days=1))
    n_next = sum(len(v) for v in (weeks.get(nxt) or {}).values())

    # WHERE THE REST IS: next week's own page, which build_calendar writes
    # for every week in its range, empty ones included -- linked here only
    # when next week has a sitting, and otherwise the link is the Calendar
    # tab. HOME_JS keeps this line when it empties the rail in the reader's
    # clock.
    if n_next:
        onward = (f"{n_next}{' more' if dates else ''} "
                  f"sitting{'' if n_next == 1 else 's'} next week. ",
                  f"calendar/{nxt}.html", "See next week")
    else:
        onward = ("Nothing is on the calendar for next week yet. ",
                  "calendar.html", "See the full calendar")
    more = ('<p class="calmore calall">' + esc(onward[0])
            + f'<a href="{esc(onward[1])}">{esc(onward[2])}</a></p>')

    if not dates:
        # THE REST OF THE WEEK IS EMPTY every weekend in session and every
        # day out of it. Out of session -- next week empty too -- it says when
        # business resumes rather than just "nothing", because the General
        # Court is a part-time legislature and this is what the page says for
        # half the year.
        note = "Nothing is scheduled for the rest of this week."
        if not n_next:
            note += (" The General Court sits from January to June, and "
                     "committees meet on bills from the autumn filing period "
                     "onwards.")
        return ('<section class="cal"><h2>Coming up</h2>'
                f'<p class="note">{esc(note)}</p>{more}</section>')

    meets = {k: rs for d in dates for k, rs in week[d].items()}
    up = [r for rs in meets.values() for r in rs]

    # --- titles and years, from the term index, once per term ---------------
    titles, years, missing = {}, {}, 0
    for term in {u.get("term") for u in up if u.get("term")}:
        f = out / "idx" / f"{term}.json"
        if not f.exists():
            continue
        try:
            for b in json.loads(f.read_text(encoding="utf-8")):
                titles[b.get("id")] = b.get("title") or ""
                years[b.get("id")] = b.get("year")
        except (ValueError, OSError):
            continue

    # --- committee name -> its own page -------------------------------------
    code = {}
    cf = out / "committees.json"
    if cf.exists():
        try:
            for c in json.loads(cf.read_text(encoding="utf-8")):
                if c.get("name") and c.get("code"):
                    code[c["name"].strip().lower()] = c["code"]
        except (ValueError, OSError):
            pass

    def when(d):
        """Tue 15 Sep, and how far off it is -- the part a reader acts on."""
        try:
            dd = _dt.date.fromisoformat(d)
        except ValueError:
            return d, ""
        off = (dd - today).days
        rel = ("today" if off == 0 else "tomorrow" if off == 1
               else f"in {off} days" if 0 < off <= 14 else "")
        return dd.strftime("%a %d %b").replace(" 0", " "), rel

    # A day's committees in the order they start, by the week page's own
    # ordering, so the two list them the same way round.
    days = OrderedDict((d, BC.in_order(week[d])) for d in dates)

    # A WEEK IN THE RAIL, NOT A FORTNIGHT: in session a fortnight is fourteen
    # days of committee cards down a 300px column, and it was asked on 19
    # September to be "a bit more consolidated ... so it isn't as long". A
    # week is the Calendar tab's own unit, and the rail is now that week.
    html = ['<section class="cal"><h2>Coming up</h2>']
    body, missing = cal_days(days, meets, titles, years, code, when, esc)
    html.append(body)
    html.append(more)
    return "".join(html) + cal_notes(up, missing, esc)


# ONE CHIP FOR A PERSON, AND THIS IS THE SECOND COPY OF IT.
#
# app.js's `pchip` draws a legislator wherever the page is built in the
# browser -- a bill's sponsors, a committee's members. The legislators page
# builds two of its three rosters in PYTHON, on purpose: they are the only
# listing a crawler and a reader without JavaScript can walk, and this page
# used to be a search box that showed nothing until somebody typed.
#
# So the chip exists twice, which this repository otherwise refuses. It is
# allowed here for the same reason plate() is allowed to: the two copies are
# held together by a check that runs BOTH and compares their output, rather
# than by a comment asking the next person to remember. preflight's
# "the person chip is drawn the same in both" is that check. Change one and
# it fails until you change the other.
#
# The party code reads party_code first and the first letter of party second,
# because sponsor records carry "Republican" and the roster carries "R", and
# a member must not read as one party on a bill and another on the roster --
# which is the bug that made this one component in the first place.
def _cesc(s):
    """app.js's esc, exactly: ampersand, the angles and the double quote.

    NOT shell.E, which is html.escape and also turns an apostrophe into
    &#x27;. The two render identically, so the difference is invisible on the
    page and would be invisible in a diff of the two chips as well -- which is
    how a check that was meant to hold them together would come to be relaxed
    until it held nothing. The chip escapes for itself so the comparison can
    stay byte for byte.
    """
    return (str("" if s is None else s).replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


# THE PARTY PILL HAS ITS OWN PREFIX NOW: pt-R, not p-R.
#
# `.p-R` was three components in this codebase -- the left edge of a member
# chip, the fill of a seat on the floor chart, and this small tinted pill --
# and app.css already recorded that as the third time one class name had meant
# two things here, with the standing instruction that a new component gets its
# own prefix.
#
# It was not academic. style.css concatenates the page region after the shared
# one, and both `.mchip{background:var(--surface)}` and
# `:where(body.pg) .p-R{background:var(--rep-soft)}` carried a single class, so
# the pill's tint won wherever a member chip appeared on a page built here: the
# roster's chips arrived tinted and unpadded. That was patched by specificity
# first; this is the real fix.
def pchip(m, esc=_cesc):
    """One legislator, as the site draws them everywhere else."""
    code = str(m.get("party_code") or m.get("party") or "").upper()[:1] or "X"
    who = esc(m.get("display_full") or m.get("label") or m.get("name") or "")
    role = m.get("role") if (m.get("role") and m.get("role") != "Member") else (
        "Prime" if m.get("prime") else "")
    slug = m.get("slug") or ""
    inner = (f'<a href="legislator/{esc(slug)}.html">{who}</a>' if slug else who)
    return (f'<span class="mchip p-{esc(code)}">{inner}'
            + (f" <i>{esc(role)}</i>" if role else "") + "</span>")


def is_cancelled(rows):
    """True when every row of a card is a cancelled meeting.

    ONE DEFINITION, BECAUSE TWO PLACES USE IT: the card marks itself
    data-cancelled from this, and the week's lead leaves the same cards out
    of its count. A cancelled meeting is shown, so a reader who saw it
    noticed can see it did not happen, and it is not a sitting -- counting
    it said "22 sittings" of a week of 2025 in which 21 met.
    """
    return bool(rows) and all((r.get("what") or "").lower() == "cancelled"
                              for r in rows)


def cal_days(days, meets, titles, years, code, when, esc, level=3,
             sessions=None, docs=None):
    """The day blocks and their meeting cards, for any set of days.

    Split out of calendar_html on 18 September so the calendar PAGE draws the
    same cards from the same grouping. meeting_key already exists because two
    places counted meetings and disagreed; a second renderer drawing something
    that merely looked like these would be the same mistake in markup.
    """
    # THE DAY'S HEADING LEVEL IS THE CALLER'S TO SAY. On the home page these
    # sit under "Coming up", an h2, so they are h3. On a week's own page the
    # h1 IS the week, and an h3 under it skips a level -- which is a depth,
    # not a size, and a screen reader reads it as a missing section.
    h = f"h{level}"
    html, missing = [], 0
    for date, keys in days.items():
        label, rel = when(date)
        # THE DAY'S OWN DATE TRAVELS WITH IT. This block is written when the
        # site is built and read for as long as the build stands, so the home
        # page has called a past day "today", with a meeting that had already
        # happened at the top of Coming up. HOME_JS
        # reads this attribute in the reader's own clock, drops the days that
        # have passed and writes the relative word again.
        # THE DATE AND HOW FAR OFF IT IS, and nothing else. The day's span
        # was briefly here, on 20 September, to spare the cards a line; the
        # card carries its own time again now -- beside its bill count, which
        # is the more compact place for it -- so a span here would be the
        # same string twice.
        # A DAY WITH NOTHING ON IT, which only the week page passes: it lists
        # every weekday so a quiet one reads as quiet rather than as missing.
        # Its own class, so the week's filter never hides a line that is true
        # under any filter, and the home rail's reader of `class="calday"`
        # never counts it.
        html.append(f'<div class="calday{"" if keys else " calnone"}" '
                    f'data-d="{esc(date)}"><{h} class="caldate">'
                    f'<span>{esc(label)}</span>'
                    f'<span class="cdrel">{esc(rel)}</span>'
                    + f"</{h}>")
        if not keys:
            html.append('<p class="calempty">No meetings scheduled.</p></div>')
            continue
        for key in keys:
            _d, cmte = key
            rows = meets[key]
            # THE DAY'S ITEMS, IN ORDER. One entry can hold a hearing, a work
            # session and an executive session, so the body is a little
            # schedule rather than a flat list of bills: each slot keeps the
            # time it was set for and says what kind of sitting it is.
            # Inside a slot, by number as bills.html lists them. Without the
            # last key a slot kept proceedings.csv's order, which is the
            # number's text: HB 101, HB 110, HB 78.
            slotted = OrderedDict()
            for r in sorted(rows, key=lambda x: ((x.get("time") or "~"),
                                                 (x.get("what") or ""),
                                                 (x.get("venue") or ""),
                                                 BO.bill_key((x.get("bill") or "").strip()))):
                slotted.setdefault(((r.get("time") or ""),
                                    (r.get("what") or ""),
                                    (r.get("venue") or "")), []).append(r)
            kinds, rooms = [], []
            for _tm, wk, vn in slotted:
                if wk not in kinds:
                    kinds.append(wk)
                if vn and vn not in rooms:
                    rooms.append(vn)
            venue = rooms[0] if len(rooms) == 1 else ""
            # THE SPAN, NOT A SLOT. Each row is one bill with its own place in
            # the meeting, so the meeting runs from the first to the last --
            # which is how the General Court prints it, 10:00am - 3:30pm. A
            # meeting whose bills all share one slot states it once.
            slots = sorted(x for x in (r.get("time") or "" for r in rows) if x)
            time = (slots[0] if len(set(slots)) == 1 else
                    f"{slots[0]}–{slots[-1]}") if slots else ""
            # BILLS, NOT ROWS. A study or statutory committee's meeting is a
            # row with no bill, and counting rows called it "(1 bill)".
            n = sum(1 for r in rows if (r.get("bill") or "").strip())
            # A study or statutory committee's card says so, for the week
            # page's toggle; a cancelled one says that, so it is not offered
            # for anybody's own calendar.
            study = any(r.get("study") for r in rows)
            cancelled = is_cancelled(rows)
            # WHAT A FILTER NEEDS, ON THE CARD ITSELF. The week page is static
            # HTML on a CDN and the filtering happens in the reader's browser,
            # so each card states its own chamber, committee and bills rather
            # than the page shipping a second copy of the week as JSON. A
            # reader with no script still gets every card, which is the whole
            # week and the correct answer to no filter at all.
            bodies = sorted({(r.get("body") or "").strip().upper()
                             for r in rows if (r.get("body") or "").strip()})
            bills_attr = " ".join(sorted({(r.get("bill") or "").strip().upper()
                                          for r in rows if r.get("bill")}))
            html.append('<details class="calmeet"'
                        f' data-body="{esc(" ".join(bodies))}"'
                        f' data-cmte="{esc(cmte.lower())}"'
                        f' data-bills="{esc(bills_attr)}"'
                        f' data-date="{esc(_d)}"'
                        + (f' data-time="{esc(slots[0])}"' if slots else "")
                        + (f' data-last="{esc(slots[-1])}"' if slots else "")
                        + (f' data-venue="{esc(venue)}"' if venue else "")
                        + (' data-study=""' if study else "")
                        + (' data-cancelled=""' if cancelled else "")
                        + "><summary>")
            # THE MIXED COLOUR. One segment per kind the day holds, stacked
            # down the edge of the card, so a committee doing two things reads
            # at a glance as one committee doing two things rather than as two
            # committees. Segments rather than a gradient, so the colours stay
            # in the stylesheet and both themes keep working.
            # DEDUPED ON THE COLOUR, not on the kind's name. A full committee
            # work session and a subcommittee work session are two kinds and
            # one colour, and drawn per kind the bar showed two identical
            # segments, which reads as two things rather than one.
            bars = []
            for k in kinds:
                cls = MEET_KIND.get(k.strip().lower(), ("", ""))[1] or "k-other"
                if cls not in bars:
                    bars.append(cls)
            html.append('<span class="calmix" aria-hidden="true">'
                        + "".join(f'<i class="{c}"></i>' for c in bars) + "</span>")
            # THE COMMITTEE FIRST. It is what a reader scans a rail for, and
            # putting the time ahead of it meant the rail's card spent its
            # first line on four digits. The time follows, beside the bill
            # count, so the two read as one phrase about that sitting:
            # "Ways and Means / 09:30-10:30 (11 bills)".
            html.append(f'<span class="calcmte">{esc(cmte)}</span>')
            if time:
                html.append(f'<span class="caltime">{esc(time)}</span>')
            # THE COUNT DIRECTLY AFTER THE TIME, not after the kind. The
            # parentheses only work while the two are adjacent -- with the
            # kind chip between them the rail read "09:30-11:30 Subcommittee
            # work session (5 bills)", a bracket around nothing in
            # particular. On its own where there is no time, for the same
            # reason.
            _bills = f'{n} bill{"" if n == 1 else "s"}'
            if n:
                html.append(f'<span class="calcount">'
                            + (f"({_bills})" if time else _bills) + "</span>")
            for k in kinds:
                word, kcls = MEET_KIND.get(k.strip().lower(),
                                           (k.capitalize() if k else "Meeting", ""))
                html.append(f'<span class="calkind {kcls}">{esc(word)}</span>')
            if venue:
                html.append(f'<span class="calwhere">{esc(venue)}</span>')
            html.append('<span class="caret"></span></summary>'
                        '<div class="calbody">')
            one = len(slotted) == 1
            for (tm, wk, vn), items in slotted.items():
                word, kcls = MEET_KIND.get(wk.strip().lower(),
                                           (wk.capitalize() if wk else "Meeting", ""))
                if not one:
                    html.append('<p class="calslot">'
                                + (f'<span class="caltime">{esc(tm)}</span>' if tm else "")
                                + f'<span class="calkind {kcls}">{esc(word)}</span>'
                                + (f'<span class="calwhere">{esc(vn)}</span>'
                                   if vn and not venue else "") + "</p>")
                # A ROW WITH NO BILL is a study or statutory committee's
                # meeting: it says what kind of meeting and what set the
                # committee up, as text, and links nowhere -- there is no
                # page here for a commission to lead to.
                # ONCE: the database holds some meetings twice -- the Land and
                # Community Heritage Authority's board on 16 November 2026 is
                # meetings 2941 and 2942 -- and the card said its note twice.
                for note in OrderedDict.fromkeys(
                        r["note"] for r in items
                        if not (r.get("bill") or "").strip() and r.get("note")):
                    html.append(f'<p class="calnote">{esc(note)}</p>')
                items = [r for r in items if (r.get("bill") or "").strip()]
                if not items:
                    continue
                html.append('<ul class="calbills">')
                for r in items:
                    bid = (r.get("bill") or "").strip()
                    yr, ti = years.get(bid), titles.get(bid)
                    if not ti:
                        missing += 1
                    href = (f'bill/{yr}/{bid.lower()}.html' if yr
                            else f'/bills#{esc(bid)}')
                    num = re.sub(r"^([A-Z]+)(\d)", r"\1 \2", bid)
                    html.append(f'<li><a class="cbn" href="{esc(href)}">{esc(num)}</a>'
                                + (f'<span class="cbt">{esc(ti)}</span>' if ti else "")
                                + "</li>")
                html.append("</ul>")
            # INTO THE SITTING, NOT JUST THE COMMITTEE. A day has an address
            # now -- committee/H05#day-2024-04-30 -- so the way out of a
            # calendar entry lands on the sitting it names rather than at the
            # top of a page holding eighty-six of them.
            # THE FLOOR HAS NO COMMITTEE PAGE TO GO TO. Floor rows carry no
            # committee -- which is why sitting days were nowhere on this site
            # until the calendar gave them one -- so "House floor" and "Senate
            # floor" lead to the day's own page instead, where the whole
            # sitting is set out in the order the journal records it.
            # A FLOOR CARD LINKS ONLY WHERE THE SITTING PAGE EXISTS. Both
            # chambers have pages now, but proceedings.csv and narratives.json
            # do not agree on every sitting: the Senate sat on 19 August 2026
            # by one and not by the other, and the link was a 404. `sessions`
            # is the set of pages actually on disk, so the caller that built
            # them decides, rather than this guessing from the name.
            floor = {"house floor": "H",
                     "senate floor": "S"}.get(cmte.strip().lower())
            if floor and sessions is not None and (floor, _d) not in sessions:
                floor = None
            elif floor and sessions is None:
                floor = None
            # THE OFFICIAL DOCUMENT, where the caller has one: the calendar
            # that printed the notice, or the journal of a floor sitting.
            # Addresses the record holds, passed in; never built here.
            got = (docs or {}).get(key) or []
            if got:
                html.append('<p class="calmore caldocs">'
                            + "".join(f'<a href="{esc(u)}" rel="noopener">'
                                      f'{esc(w)} (PDF)</a>' for w, u in got)
                            + "</p>")
            # A study committee that shares a name with a standing one is not
            # that committee, so its card does not borrow the page.
            cc = None if study else code.get(cmte.strip().lower())
            if floor:
                html.append('<p class="calmore">'
                            f'<a href="session/{floor}/{esc(_d)}.html">'
                            f'What the {esc(cmte[:-6].strip())} did that day'
                            "</a></p>")
            elif cc:
                html.append('<p class="calmore">'
                            f'<a href="committee/{esc(cc)}.html#day-{esc(_d)}">'
                            f'This sitting on the {esc(cmte)} page</a></p>')
            html.append("</div></details>")
        html.append("</div>")
    return "".join(html), missing


def cal_notes(up, missing, esc):
    """The note under the calendar: what a hearing is."""
    html = []
    # NO "MORE BILLS IN THE FORTNIGHT BEYOND THESE". That note counted what
    # home.json's eighty-row cap dropped, and in session the dropped rows
    # fell on the day already shown or the next one, not beyond them. The
    # rail reads the week uncapped now, so nothing is dropped, and what lies
    # past the week is calendar_html's own line, which counts next week and
    # links to it.
    # A public hearing is the one a reader can speak at; an executive session
    # is the one where the committee votes. Worth saying once.
    html.append('<p class="note">Anyone may attend and speak at a public '
                'hearing, or sign in for or against without speaking. An '
                'executive session is where the committee votes on what to '
                'recommend; it is open to watch but not to testify.</p>'
                "</section>")
    if missing:
        print(f"  calendar: {missing} of {len(up)} upcoming bills had no title "
              f"in site/idx (the number and the link are still printed)")
    return "".join(html)


def shell(title, current, body, wide=False, script="", desc="",
          base="https://graniterecord.org"):
    tabs = []
    # FOUR TABS. Data and About came off: both are pages for somebody who
    # already knows what they want, both have carried a footer link since the
    # footer was written, and seven similar words is what made the row hard to
    # read in the first place. Home came off because the mark beside the
    # wordmark is the way home on every site a reader uses -- it only needed
    # to be a link.
    for href, label in (("bills.html", "Bills"),
                        ("legislators.html", "Legislators"),
                        ("committees.html", "Committees"),
                        # A second nav emitter. bills.html carries the nav
                        # every shell.page() page inherits; this tuple is what
                        # legislators.html, index.html and about.html get, and
                        # when Data was added to the first it was not added
                        # here, so three pages lacked the link the other
                        # 34,000 had.
                        ("learn.html", "Learn"),
                        # Added to BOTH emitters in the same edit. The comment
                        # above records what happened the time it was not.
                        ("calendar.html", "Calendar")):
        cur = ' aria-current="page"' if href == current else ""
        tabs.append(f'<a href="{href}"{cur}>{label}</a>')
    # ONE WRAPPER, WRITTEN TWICE BECAUSE THE NAV IS. bills.html carries the
    # same <div class="navtabs"> around the same four links and app.css
    # styles it once; without it the links wrap through the middle of the row
    # and the theme control is stranded on a line of its own.
    # ONE DROPPABLE GROUP. .navdrop wraps the sections and the theme control
    # so that a phone can fold both behind one button without the markup
    # being written twice. On a desktop it is display:contents and the grid
    # sees straight through it, so the layout is brand / sections / control
    # exactly as before.
    nav = [f'<div class="navdrop" id="navdrop"><div class="navtabs">{"".join(tabs)}</div>',
           # The same control bills.html carries, read from there rather than
           # written again here.
           themer("BTN"),
           "</div>",
           MENU_BTN]
    # The home page has no tab any more, so the brand is what carries the
    # "you are here" for it -- said to a screen reader, not drawn, because the
    # chip that marks a tab is scoped to .navtabs and the brand is not one.
    BRAND_CUR = ' aria-current="page"' if current == "index.html" else ""
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
    # The same block bills.html carries, for the same reasons -- written
    # twice because the two emitters are, and kept next to each other in both
    # files so a change to one is obvious in the other.
    # The card a shared link unfurls into, by kind of page (build_brand.py
    # draws them); the plain logo card for the home page and About.
    _card = {"legislators.html": ("og-legislator.png", "legislators and their voting records"),
             "bills.html": ("og-bill.png", "bills, votes and hearings")}.get(current)
    _img = f"https://graniterecord.org/{_card[0] if _card else 'og.png'}"
    _alt = f"Granite Record: {_card[1]}" if _card else "Granite Record"
    BRAND_HEAD = f"""<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="icon" href="/icon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/icon-180.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#EAEBE7" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#171B1C" media="(prefers-color-scheme: dark)">
<meta property="og:image" content="{_img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{_alt}">
<meta name="twitter:image" content="{_img}">
"""
    HEAD_SEO = (f'<meta name="description" content="{_e(desc)}">'
                f'<link rel="canonical" href="{_canon}">'
                f'<meta property="og:type" content="website">'
                f'<meta property="og:title" content="{_e(title)}">'
                f'<meta property="og:description" content="{_e(desc)}">'
                f'<meta property="og:url" content="{_canon}">'
                f'<meta property="og:site_name" content="Granite Record">'
                f'<meta name="twitter:card" content="summary_large_image">') if desc else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>{HEAD_SEO}{FONTS}{BRAND_HEAD}{themer("HEAD")}<link rel="stylesheet" href="style.css">
<!-- body.pg is what the page half of app.css is scoped to: the record pages
     load app.css and must not take these rules. -->
<link rel="alternate" type="application/rss+xml" title="Granite Record — all activity"
 href="/feed/all.xml">
<link rel="alternate" type="application/rss+xml" title="Granite Record — upcoming hearings"
 href="/feed/hearings.xml"></head><body class="pg">
<a class="skip" href="#main">Skip to the content</a>\n<nav class="top"><div class="in"><a class="brand" href="index.html"{BRAND_CUR}>Granite Record</a>
{''.join(nav)}</div></nav>
<main class="wrap{' wide' if wide else ''}" id="main">{body}</main>
<footer><div class="in">
<div class="fcols">
<div class="fcol">
<p class="fcolhead">Granite Record</p>
<p class="attrib">Built from public records published by the <b>New Hampshire
General Court</b>. Not affiliated with the General Court, and not a substitute
for it &mdash; where this site and the Court&rsquo;s own record disagree, the
Court is right and we want to know.</p>
</div>
<div class="fcol">
<p class="fcolhead">The record</p>
<ul class="flinks">
<li><a href="data.html">Bulk data</a></li>
<li><a href="about.html">How this is made</a></li>
<li><a class="out" href="{REPO}" target="_blank" rel="noopener">Source on GitHub</a></li>
</ul>
</div>
<div class="fcol">
<p class="fcolhead">Tell us</p>
<a class="fbk out" href="https://forms.gle/PYw9c3xgpDDwvX7E9" target="_blank"
 rel="noopener">What do you think?</a>
<p class="fbknote">The site is new and being tested. Found an error?
<a href="mailto:contact@graniterecord.org">contact@graniterecord.org</a></p>
</div>
</div>
<p class="footdata"><span id="built"></span><span class="lic">MIT Open Source Licensed</span></p>
</div></footer>{FOOT_JS}
{themer("JS")}
<!-- The header's search, on every page this file writes. Its own file rather
     than app.js, which these pages do not load: 6 KB against 200. -->
<script src="/find.js" defer></script>
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
<p>Most bills are settled in the year they are filed. Two things happen to the rest,
and they are not the same. <b>Retaining</b> is a first-year move: the committee keeps
the bill, works on it over the autumn and reports it in the second year, so it
survives and keeps its number. Those show as <b>carried over</b> here, and they are
the ones people most often fail to find, because they search the current year for a
bill filed in the previous one. <b>Interim study</b> is a second-year move and it
ends the bill: the committee studies it that autumn, but the bill dies with the term
and has to be filed again, with a new number, to come back.</p>

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
those voting. A constitutional amendment takes three fifths of the members in office
— 240 when all 400 House seats are filled — whether or not everyone shows up.
Amendments regularly win a clear majority and fail anyway.</p>

<p><b>The consent calendar is a signal about the committee.</b> A bill goes there
when the committee vote was unanimous or nearly so and no dissenting member objected
to the placement. It then passes without floor debate. Ten members may petition to
pull a bill off and have it taken up separately.</p>

<p><b>Someone has to run the room.</b> Whoever is in the chair for a roll call —
the Speaker, or a member the Speaker has asked to preside — is usually recorded as
presiding rather than as voting. A Speaker will appear as not having voted on
hundreds of roll calls, and that is the job rather than absence.</p>

<p><b>Not voting comes in two kinds.</b> A member recorded as excused was excused
from that vote; an excuse can cover a whole day, part of a day or a single vote, so
an excused member may have cast other votes the same day. A member recorded
as not excused did not vote, and the roll call does not say why.</p>

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
proposed change to the state constitution. Needs three fifths of the members in
office in each chamber, then a two-thirds vote of the people at the next
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
<p>Bill histories and hearing schedules come from the General Court's docket:
for the current term its published data files, for 2015 to 2024 its web pages,
and before that the read-only database the General Court publishes credentials
for. Sponsors from 2023 on come from its sponsor file and bill status pages, and
before 2023 from the sponsor line printed on each bill's own text. Vote tallies
and individual member votes come from its roll call files, and for sessions
those files no longer cover, from the same database. The House's committee
majority and minority reports are taken from the House Calendar; the Senate's
come from the database too, which is where the Senate files them. Hearing and
session recordings are the General Court's own, on YouTube, linked rather than
copied.</p>
<p>Where a hearing shows how many people signed in for and against a bill, those
are counts and nothing else. The General Court's sign-in sheet records a name, a
town and often written testimony for every person; almost all of them are members
of the public rather than public figures, and this site does not republish them.</p>
<p>A term before the current one is marked <i>archived</i>. Nearly every
archived bill has its docket &#8212; the General Court's own line-by-line list
of actions &#8212; and its sponsors, the committee it went to, its hearings and
its text. Three parts of the record start later, because the General Court's
copies of them that this site reads start later. The House committees'
written reports start with the 1997-1998 term, the first in its online
calendars, and the Senate committees' with the current term, the only one its
database holds them for. Before those, the page gives each committee's
recommendation as the docket records it, and the committee's vote wherever the
docket gives one. Votes by name start in 1999, where its roll-call files
begin; before that, the docket gives the tallies it recorded, and the printed
journals name who voted which way. Recordings start in [[stream_start]], when
its YouTube channels begin. Every archived bill links its own official
record.</p>

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

<h2>How much of this is timed, and how well</h2>
<p>The record here holds [[stations]] occasions on which a bill was taken up
&#8212; hearings, executive sessions, work sessions and floor debates &#8212;
across [[station_bills]] bills. What the site can say about each one depends
almost entirely on whether there is a recording of it to link.</p>
<p>For [[no_recording]] of them, there is no recording to offer. The recordings
this site links are on the General Court's YouTube channels, which begin in
[[stream_start]]; [[prestream]] of these sittings happened before that, which
is [[prestream_pct]] of the whole record, and the other [[unmatched]] are
sittings since then that no recording has been matched to. Most carry the
date, the committee and the room, and nothing to play.</p>
<p>[[recorded]] have a recording. On [[placed]] of them &#8212;
[[placed_pct]] &#8212; the page opens the recording at the moment the bill
was taken up. On the other [[recording_only]] it links the recording and says
plainly that the moment has not been established, rather than guessing one. A
further [[consent]] passed on a consent calendar: adopted in a block, never
read out and never debated, so there is no moment in the recording to
find.</p>
<p>Where the moment is claimed, it usually comes from someone saying so. Most
of these are the chair or the clerk opening the item, matched against the
recording's captions; some are a roll call's own clock time from the General
Court's record, which involves no speech recognition at all; the rest are
inferred from where the bill is discussed, and those are the ones marked
<i>approximate</i>. Only that word separates an inferred start from a quoted
one. The site used to print the margin and the method beside every timestamp,
and that turned out to be methodology in the reader's way.</p>
<p>The timing is checked against [[marked]] proceedings that a person timed by
watching the recording, across [[marked_videos]] recordings. Of these it places
[[marked_placed]]: the median is out by [[median]], and [[within_minute]] of
[[marked_placed]] are within a minute. [[over_ten]] are more than ten minutes
out &#8212; the worst by [[worst]] &#8212; and that is not imprecision but a
proceeding placed somewhere else, which is a different fault and is being
worked through. The remaining [[marked_unplaced]] carry no time at all rather
than a guessed one. Opening each recording at its scheduled time
instead &#8212; the obvious method, and the one this replaced &#8212; would be
out by [[schedule_median]] at the median. Last measured [[measured]].</p>
<p>Speech recognition is worst at exactly the things that matter most — names,
numbers and organisations. Check the recording before quoting anything.</p>

<h2>What this site knows about you</h2>
<p>Page views are counted: how many there are, and which pages. That is
Cloudflare Web Analytics, which runs on the pages this site is served from.
It sets no cookies, it does not follow anyone between sites, and it does not
build a profile of a reader &mdash; what comes back is a count per page, with
the country, browser and referrer of the visit in aggregate. Nobody here can
tell one reader from another, and nothing about what you read is stored
against you.</p>
<p>Nothing else is collected. There are no accounts, no email addresses and
no advertising. The feeds need no subscription, so nothing knows who takes
them. Search runs in your own browser against files this site serves. When a
search takes you to a results page &mdash; the bill search, the record search
or the legislator list &mdash; your words travel in that page&rsquo;s address.
This site&rsquo;s server receives them, as it receives any address, and the
page-view count may record that address like any other. The typefaces come
from Google Fonts, so Google sees a request for them when a page opens. Video
is embedded from
YouTube&rsquo;s no-cookie address, which still means YouTube sees a request
when a player is opened &mdash; a player only loads if you press play.</p>
<p>One thing a reader sends deliberately is feedback, through the form
linked in the footer. That is a Google form, and what you put in it goes to
Google and to us.</p>
<p>The other is a report, from the box marked <i>Report a problem with this
page</i> on bill, committee and legislator pages. A report holds the page and
the record it is about, the tab that was open, the kind of problem chosen from
a list, what you wrote, the time it arrived and which build of the site you
were reading. Nothing in it identifies you &mdash; no IP address, no cookie, no
email address &mdash; which is also why we cannot reply to one. It is read only
to check the page against the official record and fix what is wrong, and it is
deleted after a week.</p>

<h2>Corrections</h2>
<p>If something here misrepresents the record, it should be corrected. The official
record at gc.nh.gov always takes precedence over anything shown here.</p>

<h2>Independence</h2>
<p>This site is not affiliated with or endorsed by the New Hampshire General Court.
It takes no position on any bill.</p>
"""

SEATING_JS = """
<script>
/* THE SEATING CHART, MADE USEFUL. Three ways to the same member, because the
   person asked for three: "you can either click the seat or you can click the
   dropdown sorted by number or search."

   The roster under the chart is already in the HTML, in seat order, so a
   reader with no JavaScript has the whole House and every link in it. All
   this does is filter it and join the two halves together.

   A SEAT IS ASKED, NOT FOLLOWED. Tapping one used to navigate straight to the
   member's page, which on a phone meant that finding out who sits somewhere
   cost a page load and a journey back -- and on a chart where seats are a
   thumb's width apart, an accidental one. A tap now names the member, lights
   the seat and lights their row below; the name it gives you is a link, so
   going through is a second, deliberate tap. */
(function(){
  var list=document.getElementById("seatlist");
  if(!list)return;
  var svg=document.querySelector(".seatmap");
  var wrap=document.querySelector(".seatwrap"), dragged=false;
  var note=document.getElementById("seatnote");
  var q=document.getElementById("sq"), go=document.getElementById("sgo");
  var rows=[].slice.call(list.querySelectorAll(".seatrow"));
  var picked=null;          // the chosen seat's circle, or null

  // 4017 is division 4, seat 17, and the plate reads 4-017. The same
  // function lives in seating.py and in app.js; preflight holds all three
  // together.
  function plate(s){
    s=String(s||"");
    return s.length>3 ? s.slice(0,s.length-3)+"-"+s.slice(-3) : s;
  }
  function rowFor(seat){
    return rows.filter(function(r){return r.dataset.seat===seat;})[0];
  }
  // A seat and its row light together, whichever one the reader reached for,
  // so the answer to "where does my rep sit" and "who sits there" is one
  // gesture either way.
  function mark(seat){
    rows.forEach(function(r){r.classList.toggle("on",!!seat&&r.dataset.seat===seat);});
    if(svg)[].forEach.call(svg.querySelectorAll(".seat"),function(c){
      c.classList.toggle("on",!!seat&&c.getAttribute("data-seat")===seat);});
  }
  // Built as nodes rather than markup: a member's name is theirs, and it is
  // not going through innerHTML on my say-so.
  function say(preview){
    if(!note)return;
    note.textContent="";
    var c=preview||picked;
    if(c){
      var a=document.createElement("a");
      a.href=DATA("legislator/"+c.getAttribute("data-slug")+".html");
      a.textContent=c.getAttribute("data-name");
      note.appendChild(a);
      note.appendChild(document.createTextNode(
        " — seat "+plate(c.getAttribute("data-seat"))));
      return;
    }
    var shown=rows.filter(function(r){return !r.hidden;}).length;
    note.textContent=shown===rows.length?"":shown+" of "+rows.length+" representatives";
  }
  function centre(c){
    if(!wrap||!c.getBoundingClientRect)return;
    var b=c.getBoundingClientRect(), w=wrap.getBoundingClientRect();
    wrap.scrollLeft+=(b.left+b.width/2)-(w.left+w.width/2);
    wrap.scrollTop +=(b.top+b.height/2)-(w.top+w.height/2);
  }
  function pick(c){
    picked=c||null;
    mark(picked?picked.getAttribute("data-seat"):"");
    say();
    if(!picked)return;
    var row=rowFor(picked.getAttribute("data-seat"));
    // NO JUMP TO THE LIST (the person, 24 September). Choosing a seat used to
    // scroll the page down to its row; the chart's own link, under it, names
    // the member and goes to their page, so the reader stays on the chart.
    // The row is still marked, and still shown if a search had hidden it.
    if(row)row.hidden=false;
    centre(picked);
  }
  function seatByNumber(seat){
    return svg?svg.querySelector('[data-seat="'+seat+'"][data-slug]'):null;
  }

  function draw(){
    var s=(q&&q.value||"").trim().toLowerCase();
    rows.forEach(function(r){
      var hay=(r.dataset.seat+" "+r.dataset.county+" "+r.textContent).toLowerCase();
      r.hidden=!(!s||hay.indexOf(s)>-1);
    });
    // Searching for one person should light their seat without a second
    // gesture; searching for a county should not light an arbitrary one of
    // its twelve.
    var only=rows.filter(function(r){return !r.hidden;});
    if(s&&only.length===1)pick(seatByNumber(only[0].dataset.seat));
    else {picked=null;mark("");say();}
  }
  if(q)q.addEventListener("input",draw);
  if(go)go.addEventListener("change",function(){
    if(go.value)pick(seatByNumber(go.value));
  });

  /* ZOOM, BECAUSE 400 SEATS DO NOT FIT A PHONE. The chart used to be pinned
     to a 680px minimum inside a sideways-scrolling box: on a 390px screen
     that is a seat about five pixels across, which is under half the
     smallest thing a thumb can reliably hit. It is sized by zoom now, and a
     narrow screen opens already zoomed in far enough for a seat to be a real
     target -- the whole floor at once is no use if nothing on it can be
     tapped. Fit puts it back. */
  var zoom=1;
  function apply(){ if(svg)svg.style.width=(zoom*100)+"%"; }
  // ZOOM ABOUT A POINT, not about the top-left corner. Zooming toward the
  // middle of the box moves whatever the reader was looking at out from under
  // them, which on a chart of 400 near-identical circles means losing your
  // place entirely. The content coordinate under the pointer is worked out
  // first and put back under the pointer afterwards.
  function zoomAt(next, cx, cy){
    if(!wrap)return;
    next=Math.max(1,Math.min(6,next));
    if(next===zoom)return;
    var r=wrap.getBoundingClientRect();
    var ox=(cx===undefined?r.width/2:cx-r.left), oy=(cy===undefined?r.height/2:cy-r.top);
    var k=next/zoom;
    var sx=(wrap.scrollLeft+ox)*k-ox, sy=(wrap.scrollTop+oy)*k-oy;
    zoom=next; apply();
    wrap.scrollLeft=sx; wrap.scrollTop=sy;
  }
  function fit(){
    var w=wrap?wrap.clientWidth:0;
    zoom=w?Math.max(1,Math.min(3.5,1100/w)):1;
    apply();
  }
  function step(by){ zoomAt(zoom*by); if(picked)centre(picked); }

  if(wrap){
    // THE WHEEL ZOOMS over the chart rather than scrolling past it, which is
    // what a reader expects of something they can drag around, and is what
    // was asked for. preventDefault stops the page moving underneath.
    wrap.addEventListener("wheel",function(e){
      e.preventDefault();
      zoomAt(zoom*(e.deltaY<0?1.12:1/1.12), e.clientX, e.clientY);
    },{passive:false});

    // DRAGGING MOVES THE FLOOR. Only from the background: a drag that starts
    // on a seat would otherwise swallow the tap that chooses it.
    var from=null;
    wrap.addEventListener("pointerdown",function(e){
      dragged=false;
      if(e.pointerType==="touch")return;      // one finger already pans natively
      if(e.target.closest&&e.target.closest("[data-seat]"))return;
      from={x:e.clientX,y:e.clientY,l:wrap.scrollLeft,t:wrap.scrollTop};
      wrap.setPointerCapture(e.pointerId);
      wrap.classList.add("dragging");
    });
    wrap.addEventListener("pointermove",function(e){
      if(!from)return;
      if(Math.abs(e.clientX-from.x)+Math.abs(e.clientY-from.y)>4)dragged=true;
      wrap.scrollLeft=from.l-(e.clientX-from.x);
      wrap.scrollTop =from.t-(e.clientY-from.y);
    });
    ["pointerup","pointercancel"].forEach(function(n){
      wrap.addEventListener(n,function(){from=null;wrap.classList.remove("dragging");});
    });

    // TWO FINGERS PINCH. One finger is left alone so the box still scrolls
    // the way every other scrollable thing on a phone does, and so a reader
    // can still get past the chart to the rest of the page.
    var gap=0, mid=null;
    function spread(t){
      var dx=t[0].clientX-t[1].clientX, dy=t[0].clientY-t[1].clientY;
      return Math.sqrt(dx*dx+dy*dy);
    }
    wrap.addEventListener("touchstart",function(e){
      if(e.touches.length!==2)return;
      gap=spread(e.touches);
      mid={x:(e.touches[0].clientX+e.touches[1].clientX)/2,
           y:(e.touches[0].clientY+e.touches[1].clientY)/2};
    },{passive:true});
    wrap.addEventListener("touchmove",function(e){
      if(e.touches.length!==2||!gap)return;
      e.preventDefault();
      var now=spread(e.touches);
      zoomAt(zoom*(now/gap), mid.x, mid.y);
      gap=now;
    },{passive:false});
    wrap.addEventListener("touchend",function(e){
      if(e.touches.length<2){gap=0;mid=null;}
    },{passive:true});
  }
  var zi=document.getElementById("szin"), zo=document.getElementById("szout"),
      zf=document.getElementById("szfit");
  if(zi)zi.addEventListener("click",function(){step(1.35);});
  if(zo)zo.addEventListener("click",function(){step(1/1.35);});
  if(zf)zf.addEventListener("click",function(){zoomAt(1);});
  fit();

  // A seat is a circle with a slug on it, not a link -- an <a> inside the SVG
  // would need its own focus and hit area. One handler on the map covers all
  // 400, and Enter or Space does what a tap does, which is what tabindex and
  // role="button" on each circle promise.
  // The Speaker's seat is a <g> with a rect and a label inside it, so a click
  // lands on a child. closest() walks up to whichever node carries the slug,
  // which makes the rostrum behave like the other 399 circles.
  function seatHit(t){
    if(!t||!t.closest)return null;
    var n=t.closest("[data-slug]");
    return n&&n.getAttribute("data-slug")?n:null;
  }
  if(svg){
    svg.addEventListener("click",function(e){
      var c=seatHit(e.target);
      if(c){e.preventDefault();pick(c===picked?null:c);}
    });
    svg.addEventListener("keydown",function(e){
      if(e.key!=="Enter"&&e.key!==" ")return;
      var c=seatHit(e.target); if(!c)return;
      e.preventDefault(); pick(c===picked?null:c);
    });
    // Hovering names who is in a seat without choosing it, so a mouse can
    // read the floor quickly; leaving restores whatever was chosen.
    svg.addEventListener("mouseover",function(e){
      var c=seatHit(e.target); if(c)say(c);
    });
    svg.addEventListener("mouseout",function(){say();});
  }
  // A CLICK ON THE FLOOR ITSELF LETS GO (the person, 24 September): anywhere
  // in the chart that is not a seat deselects whoever was chosen. A drag to
  // pan also ends in a click, so one that moved is not taken for a let-go.
  if(wrap)wrap.addEventListener("click",function(e){
    if(seatHit(e.target))return;
    if(dragged){dragged=false;return;}
    if(picked)pick(null);
  });
  draw();
})();

/* THREE TABS, WHICH ARE THE ORDERING. The person asked for "three tabs for
   ways to sort the legislators, sorted alphabetically by last name, sorting
   by county as they are now, and sorting by seat number", so the ordering is
   a choice a reader makes once rather than a control they have to find. It
   replaced an Order dropdown inside the seat view, which did the same job in
   a place nobody would look for it.

   All three panes are in the HTML and all three are visible until this runs,
   so a reader with no JavaScript gets the whole roster rather than one pane
   and two empty boxes. The first thing this does is hide two of them -- and
   that is also why losing this block is quiet: every pane simply stays open,
   the tabs still look like tabs, and clicking one changes nothing. */
(function(){
  var bar=document.querySelector(".rtabs");
  if(!bar)return;
  var tabs=[].slice.call(bar.querySelectorAll("[role=tab]"));
  if(!tabs.length)return;
  function show(id){
    tabs.forEach(function(t){
      var on=t.dataset.pane===id;
      t.setAttribute("aria-selected",String(on));
      t.tabIndex=on?0:-1;
      var pane=document.getElementById(t.dataset.pane);
      if(pane)pane.hidden=!on;
    });
  }
  tabs.forEach(function(t){
    t.addEventListener("click",function(){show(t.dataset.pane);});
  });
  // Left and right move between tabs, which is what a tablist promises the
  // moment it says role="tab".
  bar.addEventListener("keydown",function(e){
    var i=tabs.indexOf(document.activeElement);
    if(i<0)return;
    var j;
    if(e.key==="ArrowRight")j=(i+1)%tabs.length;
    else if(e.key==="ArrowLeft")j=(i-1+tabs.length)%tabs.length;
    else return;
    e.preventDefault();
    tabs[j].focus(); show(tabs[j].dataset.pane);
  });
  show(tabs[0].dataset.pane);
})();
</script>
"""

# THE BILL MATCHER, FOR THE HEADER SEARCH. The header's panel and /search show
# how many of the current term's bills match what was typed, and the number
# has to be the one /bills?q= then shows -- a panel that promises "All 30
# bills" and opens on 28 is a count the reader stops trusting. So they count
# with app.js's own matcher rather than a second one. app.js marks the lines
# that make it up (SYN and the query groups, the bill order, what a bill
# number is) between BILLMATCH:BEGIN and BILLMATCH:END; this copies them,
# unchanged and in order, into site/billmatch.js, inside a function so that
# none of their names can collide with a page's own, and hands back the four
# the header uses. find.js loads it only when somebody types, and only on a
# page that does not already run app.js.
BILLMATCH_BEGIN, BILLMATCH_END = "// BILLMATCH:BEGIN", "// BILLMATCH:END"
BILLMATCH_EXPORTS = ("queryGroups", "groupWeight", "billNumbers", "billKey")


def bill_matcher_js(app_js):
    """The marked regions of app.js, as one script defining GR_BILLMATCH.

    Stops the build rather than writing a partial file: a region left open,
    an END with no BEGIN, or a region set that no longer defines what the
    header calls would each ship a panel that counts nothing, silently."""
    keep, inside, regions = [], False, 0
    for n, line in enumerate(app_js.splitlines(), 1):
        mark = line.strip()
        if mark.startswith(BILLMATCH_BEGIN):
            if inside:
                raise SystemExit(f"app.js:{n}: BILLMATCH:BEGIN inside a "
                                 f"region that is already open")
            inside, regions = True, regions + 1
            continue
        if mark.startswith(BILLMATCH_END):
            if not inside:
                raise SystemExit(f"app.js:{n}: BILLMATCH:END with no BEGIN")
            inside = False
            continue
        if inside:
            keep.append(line)
    if inside:
        raise SystemExit("app.js: a BILLMATCH region is never closed")
    body = "\n".join(keep)
    missing = [f for f in BILLMATCH_EXPORTS
               if not re.search(r"\bfunction " + f + r"\(", body)]
    if not regions or missing:
        raise SystemExit("app.js's BILLMATCH regions do not define "
                         + ", ".join(missing or BILLMATCH_EXPORTS)
                         + ": the header search could not count bills")
    return ("// Written by build_pages.py from app.js's BILLMATCH regions, "
            "for find.js.\n// Do not edit here: edit app.js.\n"
            "window.GR_BILLMATCH=(function(){\n" + body + "\nreturn {"
            + ",".join(BILLMATCH_EXPORTS) + "};\n})();\n")


# THE ALL-RESULTS PAGE. find.js's panel is a dropdown: it shows eight rows and
# hands the rest on. Until 19 September it handed them to the BILL search,
# which indexes bills and nothing else -- so "See all search results for
# Concord" led to a page with no towns in it. This page reads the same
# find.json with the cap off and groups what it finds.
#
# It reuses find.js wholesale -- findRows, findMatch, findSuggest, _fmark,
# _froot, FKIND, and for the bills findBills, findBillsLoad, findBillsAll and
# findBillRow -- because a second matcher would be a second thing to keep in
# step with the first, and the panel and the page disagreeing about what
# matches is the bug a reader would notice fastest. find.js is deferred, so
# this waits for DOMContentLoaded rather than running as it is parsed.
SEARCH_JS = """
<script>
document.addEventListener("DOMContentLoaded",function(){
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const box=document.getElementById("resq");
const out=document.getElementById("resout");
const head=document.getElementById("reshead");
const lead=document.getElementById("reslead");
if(!box||!out)return;

// THE CHAMBERS ARE NOT INTERLEAVED. Every listing of legislators on this site
// puts the Senate and the House under their own headings, and a list of search
// results is a listing. r[2] is "Senate — SD22 — Republican" or "House — ...",
// which is where the chamber is; a row that says neither falls to the last
// bucket rather than being dropped.
const GROUPS=[
  {t:"Senators",            k:r=>r[0]==="legislator"&&/^Senate/.test(r[2])},
  {t:"Representatives",     k:r=>r[0]==="legislator"},
  {t:"Committees",          k:r=>r[0]==="committee"},
  {t:"Towns and wards",     k:r=>r[0]==="town"},
  {t:"Subjects",            k:r=>r[0]==="topic"},
  {t:"Former senators",     k:r=>r[0]==="former"&&/^Senate/.test(r[2])},
  {t:"Former representatives",k:r=>r[0]==="former"&&/^House/.test(r[2])},
  {t:"Former members",      k:r=>r[0]==="former"},
  {t:"Pages on this site",  k:r=>r[0]==="page"}
];

const row=(r,q)=>`<a href="${esc(_froot(r[3]))}">
  <span class="fl1"><span class="fname">${_fmark(r[1],q)}</span>
  <span class="fkind">${esc(FKIND[r[0]]||r[0])}</span></span>
  ${r[2]?`<span class="fwhat">${esc(r[2])}</span>`:""}</a>`;

// THE BILLS, counted. Until 24 September this was one card at the foot of the
// page, "Search every bill for firearms", under a line saying nothing on the
// site matched -- over 30 bills of this term. find.js's findBills counts them
// with the bill search's own matcher, so the number here is the one /bills?q=
// then shows, and the first five are listed. Before they are counted, or if
// they cannot be, the card offers the bill search without a number.
//
// Its description used to say the bill search reads "the words in its text".
// It does not: it reads a bill's number, title, sponsor and committee.
const WHAT="The bill search has every term since 1989, with filters for "
  +"committee, sponsor and what became of it.";
const bills=(q,B)=>{
  const counted=B&&B.state==="ready";
  const body=counted&&B.n
    ?findBillsAll(B,q,WHAT)+B.top.map(b=>findBillRow(b,q)).join("")
    :counted
    ?`<a href="/bills?q=${encodeURIComponent(q)}">
      <span class="fl1"><span class="fname">Search every bill for
        &ldquo;${esc(q)}&rdquo;</span></span>
      <span class="fwhat">None in the ${esc(B.term)} term. ${WHAT}</span></a>`
    :findBillsAll(B,q,WHAT);
  return `<section class="resgrp"><h2>Bills${counted&&B.n
    ?` <span class="resn">${B.n.toLocaleString()}</span>`:""}</h2>
    <div class="findout resout">${body}</div></section>`;
};
// Groups a reader reaches for after the bills: members who have left, and
// this site's own pages.
const AFTER=new Set(["Former senators","Former representatives",
  "Former members","Pages on this site"]);
let waiting=false;

function draw(q){
  const s=(q||"").trim();
  if(!s){
    head.textContent="Search the record";
    lead.textContent="Every sitting legislator and every member who has left, "
      +"every committee, every town and ward, every subject bills are filed "
      +"under, and this term's bills. The bill search has every term, with "
      +"filters.";
    out.innerHTML="";
    return;
  }
  const rows=findMatch(s,Infinity);
  const B=findBills(s,5);
  if(B&&B.state==="loading"&&!waiting){
    waiting=true;
    findBillsLoad().then(()=>draw(box.value));
  }
  const nB=B&&B.state==="ready"?B.n:null;
  const term=nB===null?"":`in the ${B.term} term`;
  head.innerHTML=`Results for &ldquo;${esc(s)}&rdquo;`;
  // The answer first. "0 matches on this site, and the bills" is a sentence
  // nobody would write, and "nothing matches" above 30 bills is false.
  const here=rows.length===1?"One match on this site"
    :`${rows.length} matches on this site`;
  const some=nB===1?`One bill ${term}`:`${(nB||0).toLocaleString()} bills ${term}`;
  lead.textContent=!rows.length
    ?(nB?`${some} ${nB===1?"matches":"match"}. No legislator, committee, `
        +"town or subject on this site does."
      :nB===0?"Nothing on this site matches that: no legislator, committee, "
        +`town or subject, and no bill ${term}.`
      :"No legislator, committee, town or subject on this site matches that.")
    :nB?`${here}, and ${some.charAt(0).toLowerCase()+some.slice(1)}.`
    :nB===0?`${here}, and no bill ${term}.`
    :`${here}, and the bills.`;
  // WHERE THE BILLS GO, as in the header's panel: first when no sitting
  // member, committee, town or subject is named with what was typed, and
  // otherwise after those and ahead of the members who have left.
  const low=s.toLowerCase(),edge=_fedge(low);
  const named=rows.some(r=>r[0]!=="former"&&_frank(r,low,edge)<2);
  const left=rows.slice();
  let html=named?"":bills(s,B),placed=!named;
  for(const g of GROUPS){
    const mine=[];
    for(let i=left.length-1;i>=0;i--)
      if(g.k(left[i]))mine.unshift(left.splice(i,1)[0]);
    if(!mine.length)continue;
    if(!placed&&AFTER.has(g.t)){html+=bills(s,B);placed=true;}
    html+=`<section class="resgrp"><h2>${esc(g.t)}
      <span class="resn">${mine.length}</span></h2>
      <div class="findout resout">${mine.map(r=>row(r,s)).join("")}</div></section>`;
  }
  if(!placed)html+=bills(s,B);
  // Only when something close exists, and only when no bill matched either:
  // its guesses are names, and "voting" was offered "zoning" over 141 bills.
  // findSuggest measures against every distinct word in the index and returns
  // nothing rather than reaching: there is no Firearms subject in the General
  // Court's own list, so a search for "firarms" offers nothing and says
  // nothing.
  if(!rows.length&&!nB&&!(B&&B.state==="loading")){
    const did=findSuggest(s);
    if(did)html=`<p class="note">Did you mean
      <a href="/search?q=${encodeURIComponent(did)}">${esc(did)}</a>?</p>`+html;
  }
  out.innerHTML=html;
}

const q0=new URLSearchParams(location.search).get("q")||"";
box.value=q0;
box.disabled=true;
findRows().then(()=>{
  box.disabled=false;
  draw(q0);
  // Typed into rather than submitted: the results are already here, so a
  // round trip would only redraw the same page. The address still follows,
  // because a reader who found something wants to be able to send the link.
  let tm=0;
  box.addEventListener("input",()=>{
    clearTimeout(tm);
    tm=setTimeout(()=>{
      const v=box.value.trim();
      draw(v);
      const u=v?`/search?q=${encodeURIComponent(v)}`:"/search";
      history.replaceState(null,"",u);
    },120);
  });
  if(q0)box.focus();
});
// The back button, when a "Did you mean" link or the panel put a new query in
// the address without reloading.
window.addEventListener("popstate",()=>{
  const v=new URLSearchParams(location.search).get("q")||"";
  box.value=v;draw(v);
});
});
</script>
"""


LEGFIND_JS = """
<script>
(function(){
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
// Anchored to the site root, not to the page. legislators.html is served at
// /legislators, and a legislators/ folder of per-member data sits beside it --
// so /legislators can be redirected to /legislators/, and a relative
// "legislators/377204.json" then resolves to /legislators/legislators/... and
// 404s. The bill page had the same trap.
window.DATA=window.DATA||((f)=>new URL(f, location.origin+"/").href);
const SHOW=12;            // matches at once: a screen of them, not a scroll
const MIN=2;              // letters before the list appears

let TOWNS=[], MEM=[], picked=null;

function slugOf(s){return String(s).toLowerCase().replace(/[^a-z0-9]+/g,"-")
  .replace(/^-|-$/g,"");}

/* RANKED, NOT JUST FILTERED. Somebody typing "Dover" was shown Andover first
   and their own town second, under a town they do not live in. Three tiers:
   the exact name, then names that BEGIN with what was typed, then names that
   merely contain it. Nothing is dropped -- "Hampton" lists Hampton, Hampton
   Falls and New Hampton, and all three are real answers. */
function tier(hay,n){const s=hay.toLowerCase();
  return s===n?0:s.startsWith(n)?1:s.includes(n)?2:3;}

function townRow(t){
  // ONE ROW PER TOWN, and the row says one thing: the name. The live list
  // said the name and, for a city, how many wards it has -- and that is all
  // it needs to say. "Town", "Go" and "who represents it" were three labels
  // repeating what a row in a list of towns obviously is.
  // A town without wards is a link straight to its page. A city cannot be:
  // there is no town/concord.html, only concord-ward-1 through 10. So it
  // opens its wards, one chip each, and the chip is the link.
  if(t.wards.length>1)
    return `<button type="button" class="lmrow${picked===t.town?" sel":""}"
      data-town="${esc(t.town)}"><b>${esc(t.town)}</b>
      <span class="wct">${t.wards.length} wards</span></button>`
      + (picked===t.town ? `<div class="wards">` + t.wards.map(w=>
          `<a class="wbtn" href="town/${esc(t.slug)}-ward-${esc(w)}.html"
            >Ward ${esc(w)}</a>`).join("") + `</div>` : "");
  return `<a class="lmrow" href="town/${esc(t.slug)}.html"
    ><b>${esc(t.town)}</b></a>`;
}

function render(){
  const box=document.getElementById("lq");
  const out=document.getElementById("lmatch");
  const n=(box.value||"").trim().toLowerCase();
  /* RANKED, NOT JUST FILTERED, AND NEVER EMPTY. With nothing typed this is
     every town in the state, scrollable -- which is what it was before, and
     what somebody unsure of their spelling needs. Typing ranks it and adds
     the members that match. */
  const towns=(n?TOWNS.map(t=>[tier(t.town,n),t]).filter(r=>r[0]<3)
                   .sort((a,b)=>a[0]-b[0]||a[1].i-b[1].i)
               :TOWNS.map(t=>[0,t]));
  const mem=n.length>=MIN
    ? MEM.map(m=>[Math.min(tier(m.name,n),m.hay.includes(n)?2:3),m])
         .filter(r=>r[0]<3)
         .sort((a,b)=>a[0]-b[0]||a[1].sortname.localeCompare(b[1].sortname))
    : [];
  const parts=[];
  if(towns.length){
    if(mem.length)parts.push('<p class="lmhead">Towns</p>');
    parts.push(towns.map(([,t])=>townRow(t)).join(""));
  }
  if(mem.length){
    parts.push('<p class="lmhead">Members</p>');
    parts.push(mem.slice(0,SHOW).map(([,m])=>
      `<a class="lmrow" href="legislator/${esc(m.slug)}.html">`
      +`<b>${esc(m.display)}</b>`
      +`<span class="chip pt-${esc(m.p)}">${esc(m.p)}</span>`
      +`<span class="lmwhere">${esc(m.where)}</span>`
      +`<span class="lmwhat">${m.chamber==="S"?"Senate":"House"}</span></a>`)
      .join(""));
    if(mem.length>SHOW)parts.push(`<p class="lmnone">and ${mem.length-SHOW}`
      +` more members &mdash; type another letter or two.</p>`);
  }
  // No apostrophe in these sentences on purpose: this is JavaScript inside a
  // Python string, where a backslash belongs to whichever one reads it
  // first. Python read one, dropped it, and left the JavaScript with an
  // unterminated string and the whole page with no script.
  out.innerHTML=parts.length?parts.join("")
    :'<p class="lmnone">Nothing matches that. Towns and wards, member names, '
     +'counties, parties and committees are all searched.</p>';
  /* The chips into view, and no further than the row they belong to. */
  const wb=out.querySelector(".wards");
  if(wb){
    const lr=out.getBoundingClientRect(), wr=wb.getBoundingClientRect();
    if(wr.bottom>lr.bottom)
      out.scrollTop+=Math.min(wr.bottom-lr.bottom,
        wb.previousElementSibling.getBoundingClientRect().top-lr.top);
  }
}

/* The roster: every member, by chamber and then by county, each county shut
   until it is asked for. */
function roster(){
  const by={};
  MEM.forEach(m=>{const ch=m.chamber==="S"?"Senate":"House";
    (by[ch]=by[ch]||{});
    (by[ch][m.county||"Not on file"]=by[ch][m.county||"Not on file"]||[]).push(m);});
  const html=["Senate","House"].filter(ch=>by[ch]).map(ch=>{
    const counties=Object.keys(by[ch]).sort();
    const total=counties.reduce((n,c)=>n+by[ch][c].length,0);
    return `<h2>${ch} &mdash; ${total}</h2>`+counties.map(c=>{
      // By district number, then by name. Alphabetical order inside a county
      // scattered the members of one district across the list, when the
      // district is the thing a reader is looking for: it is what a town
      // lookup returns and what a ballot is organised by.
      const ms=by[ch][c].slice().sort((a,b)=>
        (parseInt(a.district,10)||0)-(parseInt(b.district,10)||0)
        ||a.sortname.localeCompare(b.sortname));
      return `<details class="cgrp"><summary><span>${esc(c)}</span>`
        +`<span class="ccount">${ms.length}</span>`
        +`<span class="caret">&#9656;</span></summary><div class="grid">`
        // THE SAME CHIP AS THE OTHER TWO VIEWS (pchip in Python), which the
        // person asked for on 19 September; this view kept its own name, pill
        // and district until 24 September. display_full carries all three.
        +ms.map(m=>`<div class="mem"><span class="mchip p-${esc(m.p)}">`
          +`<a href="legislator/${esc(m.slug)}.html">${esc(m.full)}</a></span></div>`).join("")
        +`</div></details>`;
    }).join("");
  }).join("");
  document.getElementById("out").innerHTML=html;
}

Promise.all([fetch(DATA("districts.json")).then(r=>r.json()).catch(()=>({})),
             fetch(DATA("legislators.json")).then(r=>r.json())])
 .then(([D,L])=>{
   if(!Array.isArray(L))L=Object.values(L);
   // ONE ENTRY PER TOWN, with its wards inside it. 259 rows a reader can
   // scroll, not 320 with Concord taking ten of them.
   Object.keys(D).sort().forEach(town=>{
     const wards=Object.keys(D[town]||{})
       .sort((a,b)=>parseInt(a)-parseInt(b));
     TOWNS.push({town:town, slug:slugOf(town), wards:wards, i:TOWNS.length});
   });
   MEM=L.map(m=>({
     slug:m.slug, chamber:m.chamber, county:m.county||"",
     district:m.district, dlabel:m.district_label||("dist "+m.district),
     display:m.display_plain||m.name, sortname:m.sort||m.name||"",
     full:m.display_full||m.display_plain||m.name||"",
     // [.] and [ ] rather than the escapes: this JavaScript lives inside a
     // Python string, and a backslash in one is a warning in the other.
     name:(m.display_plain||m.name||"").replace(/^(Rep|Sen)[.][ ]*/,""),
     p:(m.party||"X")[0].toUpperCase(),
     where:[m.county,m.district_label].filter(Boolean).join(" "),
     hay:[m.name,m.party,m.county,"district "+m.district,m.district_label,
          m.title||"",(m.committees||[]).join(" "),
          (m.towns||[]).join(" ")].join(" ").toLowerCase()}));
   const box=document.getElementById("lq");
   box.disabled=false;
   document.getElementById("lcount").textContent=
     TOWNS.length+" towns and cities, "+MEM.length+" sitting members";
   roster();
   /* ?town= and ?q= arrive from the home page's finder. Both fill the one
      field: a town that is warded cannot be resolved to a page without
      knowing the ward, so the reader picks it from the matches. */
   const pr=new URLSearchParams(location.search);
   const pre=(pr.get("town")||pr.get("q")||"").trim();
   if(pre)box.value=pre;
   render();
   box.focus();
   box.addEventListener("input",()=>{picked=null;render();});
   /* One handler on the list rather than one per row: the list is rebuilt on
      every keystroke and a listener per row would be rebuilt with it. */
   document.getElementById("lmatch").addEventListener("click",e=>{
     const b=e.target.closest("[data-town]");
     if(!b)return;
     picked=picked===b.dataset.town?null:b.dataset.town;
     render();
   });
 });
})();
</script>"""


HOME_JS = """
<script>
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fd=d=>{if(!d)return"";const[y,m,dd]=d.split("-");
  return new Date(y,m-1,dd).toLocaleDateString("en-US",{month:"short",day:"numeric"});};
// With the year, for the status box: out of session, the last floor day and
// the summary's date can be months back, and across a new year "Aug 19" is
// ambiguous. The server-rendered copy below writes the same form.
const fdy=d=>{if(!d)return"";const[y,m,dd]=d.split("-");
  return new Date(y,m-1,dd).toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"});};
// If the nightly build stops running, nobody should be reading month-old data
// believing it is current. The banner degrades into saying so.
// Anchored to the site root, not to the page. legislators.html is served at
// /legislators, and a legislators/ folder of per-member data sits beside it --
// so /legislators can be redirected to /legislators/, and a relative
// "legislators/377204.json" then resolves to /legislators/legislators/... and
// 404s. The bill page had the same trap.
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
// 404s. The bill page had the same trap.
window.DATA=window.DATA||((f)=>new URL(f, location.origin+"/").href);
fetch(DATA("home.json")).then(r=>r.json()).then(H=>{
  const c=H.counts||{}, k=c.by_kind||{}, S=H.status||{};

  // Title case, and a colon after each label. The Python copy below says the
  // same.
  const PHASE={"in session":["live","In Session"],
               "veto day pending":["wait","Awaiting Veto Day"],
               "between sessions":["wait","Between Sessions"],
               "out of session":["off","Out of Session"]};
  const ph=PHASE[(S.phase||"").toLowerCase()]||["off",S.phase||"Status unknown"];
  const ms=(S.milestones||[])[0];
  const stale=S.stale_days>45;
  // ONE RENDERER WINS, AND IT IS THE SERVER'S. The same box is written into the
  // page at build time and again here, and the two have disagreed on screen:
  // the HTML said 39 hearings and this said 4, because home.json came out of
  // the browser's cache while the page itself is revalidated every time.
  // The built copy is the one a crawler and a reader without JavaScript get, it
  // is never stale, and preflight checks the two say the same thing -- so this
  // draws only where the server drew nothing.
  const _state=document.getElementById("state");
  if(_state&&_state.querySelector(".statebox")){/* already drawn */}
  else if(_state)_state.innerHTML=`
    <div class="statebox ${ph[0]}">
      <div class="stateline"><span class="dot"></span><b>${esc(ph[1])}</b>
        ${S.last_session?`<span class="statemeta">Last Floor Session:
          ${fdy(S.last_session)}</span>`:""}</div>
      ${S.headline?`<p class="statehead">${esc(S.headline)}</p>`:""}
      ${S.note?`<p class="statenote">${esc(S.note)}</p>`:""}
      ${ms?`<p class="statenote"><b>Next: ${esc(ms.label)}</b>, ${fd(ms.date)}.
        ${esc(ms.note||"")}</p>`:""}
      ${stale?`<p class="statenote stalewarn" style="color:var(--st-veto)"
        data-updated="${esc(S.updated||"")}">This summary was
        last updated ${S.stale_days} days ago and may be out of date.</p>`
        :(S.updated?`<p class="statemeta upd" style="margin-top:8px"
          data-updated="${esc(S.updated)}">Summary Updated:
          ${fdy(S.updated)}</p>`:"")}
    </div>`;
  const C=H.composition||{};
  // Five seats do not want a proportional bar; list them. The Council is also
  // executive branch, so it is set apart from the two chambers rather than
  // stacked with them as though it were a third one.
  const council=()=>{
    const c=C.council; if(!c)return "";
    const rows=(c.members||[]).map(m=>
      `<tr><td style="width:96px">District ${esc(m.district)}</td>
       <td>${m.name?`${esc(m.name)} <span class="chip pt-${esc(m.party||"V")}">${
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
      <span class="chip pt-${esc(g.party||"V")}">${esc(g.party||"?")}</span></span>
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

  // THE FIVE COUNTS ARE GONE: they sat between the search box and the three
  // cards that are the actual way in, and nobody arrives to be told how many
  // bills exist. The scale of the record is said once, in the footer's link
  // to the data. .statgrid still styles the same grid on the data page.

  // #upcoming IS NOT TOUCHED HERE, ON PURPOSE. The calendar is rendered into
  // the page by calendar_html() at build time, from the rows the Calendar
  // tab's week is drawn from -- so re-rendering it here would be a second
  // renderer of one thing, which is the mistake this project has paid for
  // more than once, and it would render it WORSE: the bill titles are
  // resolved out of site/idx/<term>.json, 1.19 MB that the home page must not
  // fetch to print four of them, and the meeting rows are <details> elements
  // that need no script to open. Leaving it alone means the calendar also
  // works before this file loads and with JavaScript off.

  // COMING UP, IN THE READER'S OWN CLOCK. The calendar block is written when
  // the site is built, and a build stands for as long as it stands, so the
  // home page has headed a past day "today" with a committee session that had
  // already met at the top of the list. Each day carries its own date, so
  // this drops the days that have gone and says how far off the rest are now.
  //
  // AND THE DAYS PAST THE READER'S SUNDAY. The rail is this week, as the
  // Calendar tab's is, and "this week" is the reader's as much as "today" is:
  // a build made just after midnight on a Monday, read somewhere it is still
  // Sunday evening, holds next week's days, and they are not coming up this
  // week. getDay() calls Sunday 0, which ends an ISO week rather than
  // starting one, so on a Sunday the week has no days left after today.
  // Nothing else here is touched.
  (function(){
    const now=new Date(); now.setHours(0,0,0,0);
    const toSun=(7-now.getDay())%7;
    const days=[...document.querySelectorAll(".calday[data-d]")];
    let left=0;
    days.forEach(d=>{
      const p=d.dataset.d.split("-").map(Number);
      const off=Math.round((new Date(p[0],p[1]-1,p[2])-now)/86400000);
      if(off<0||off>toSun){d.remove();return;}
      left++;
      const rel=d.querySelector(".cdrel");
      // `off<=14`, as the built labels have it: a week's days never reach
      // it, and a bound that matched them was the point -- `off<14` once left
      // the last day of a fortnight with no label at all.
      if(rel)rel.textContent=off===0?"today":off===1?"tomorrow"
        :off<=14?`in ${off} days`:"";
    });
    const cal=document.querySelector(".cal");
    if(cal&&days.length&&!left){
      // The line under the rail stays: it says what next week holds and is
      // the way to it, which is the useful thing to say about an empty week.
      const more=cal.querySelector(".calall");
      cal.innerHTML=`<h2>Coming up</h2><p class="note">Nothing else is
        scheduled this week.</p>`+(more?more.outerHTML:"");
    }
    // "Last updated N days ago" is the one line whose whole job is to say the
    // summary may be stale; it cannot be a number frozen at build time.
    const up=document.querySelector(".statebox .upd,.statebox .stalewarn");
    if(up&&up.dataset.updated){
      const p=up.dataset.updated.split("-").map(Number);
      const age=Math.round((now-new Date(p[0],p[1]-1,p[2]))/86400000);
      const nice=new Date(p[0],p[1]-1,p[2]).toLocaleDateString("en-US",
        {month:"short",day:"numeric",year:"numeric"});
      if(age>45){
        up.className="statenote stalewarn";
        up.style.color="var(--st-veto)";
        up.textContent=`This summary was last updated ${age} days ago and may be out of date.`;
      }else{
        up.className="statemeta upd";
        up.style.color="";
        up.style.marginTop="8px";
        up.textContent=`Summary Updated: ${nice}`;
      }
    }
  })();

  // FIVE, AND THEN THE DOOR. Twelve rows was most of a phone screen for a
  // list nobody reads to the end, and the bill search can do the rest of the
  // job better: it sorts by most recent action, and now takes that sort in
  // its address. Kept in step with build_pages' static copy of this block --
  // there are two renderers for it and the footer has already shown what
  // happens when only one of them is changed.
  document.getElementById("recent").innerHTML=`<h2>Latest activity</h2>
    <table><tbody>${(H.recent||[]).slice(0,5).map(r=>
      `<tr><td style="width:80px">${fd(r.date)}</td>
       <td><a href="bills.html#${esc(r.bill)}">${esc(r.n)}</a>
       <span style="color:var(--ink-2)">${esc(r.title)}</span><br>
       <span style="font-size:12px">${esc(r.what)}</span></td></tr>`).join("")}
    </tbody></table>
    <p class="actmore"><a class="morebtn" href="/bills?sort=recent">See all
    recent activity &rarr;</a></p>`;

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
       record, not what people read here. The site counts page views \u2014
       how many, and which pages \u2014 and nothing more; see
       <a href="about.html">About</a>.</p>
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
        <div class="player"><button type="button" class="pstub" data-embed="${esc(v.video_id)}"
          aria-label="Play the ${esc(v.chamber||"")} floor session of ${fd(v.date)}">
          <span>&#9654;</span><span>Play</span></button></div></div>`).join("")}</div>`
    :"";
});
document.addEventListener("click",e=>{
  const st=e.target.closest("[data-embed]");
  if(st)st.outerHTML=`<iframe allow="autoplay" allowfullscreen
    src="https://www.youtube-nocookie.com/embed/${st.dataset.embed}?autoplay=1"
    title="Floor session"></iframe>`;
});
// ONE ADDRESS, AND NO EMPTY QUESTION. Search with nothing typed sent the
// reader to /bills?q= -- the same page the header's Bills tab reaches at
// /bills, with a query string saying the reader searched for nothing. /bills
// is what the host serves and what the header lands on.
function goBills(v){
  v=(v||"").trim();
  location.href="/bills"+(v?"?q="+encodeURIComponent(v):"");
}
document.getElementById("hq").addEventListener("keydown",e=>{
  if(e.key==="Enter")goBills(e.target.value);
});
document.getElementById("hgo").addEventListener("click",()=>{
  goBills(document.getElementById("hq").value);
});
</script>"""


def committees_with_roster(out):
    """How many committees this site can say who sits on.

    THE NUMBER WAS TYPED AND MATCHED NOTHING. The home page offered "who sits
    on each of the 56 committees": site/committees.json holds 53, site/
    committee/ holds 53 pages, data/committees.json holds 55 and the General
    Court's own Committees.txt holds 55 -- no file on this disk produces 56.
    Nor would 53 have made the sentence true, because 15 of the 53 carry no
    roster at all (H05 Education among them, 1,532 bills and no members), and
    "who sits on each" is false of every one of those. So the card states the
    committees whose membership the record actually holds, counted at build
    time out of the JSON the page it links to is built from -- the way the
    Learn pages compute every figure they print.

    n_members is build_committees.py's own len(members), and the 38 it counts
    today are exactly the 38 that carry a chair. Returns 0 if committees.json
    is not written yet: build_committees runs after this one, so on a cold
    build there is nothing to count and the card drops the number rather than
    inventing one.
    """
    f = Path(out) / "committees.json"
    if not f.exists():
        return 0
    try:
        rows = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    return sum(1 for c in rows
               if isinstance(c, dict) and (c.get("n_members") or 0) > 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "style.css").write_text(
        CSS.replace("__PALETTE__", palette()).replace("__SHARED__", shared())
           .replace("__PAGES__", pages_region()),
        encoding="utf-8")

    # THE DRAWN FILES. brand/ holds the originals, build_brand.py derives
    # assets/, and this is the step that puts them beside the pages -- site/
    # is generated and gitignored, so anything left there by hand is gone on
    # the next build and was never in the repository.
    brand = Path("assets")
    if brand.is_dir():
        moved = 0
        for f in sorted(brand.iterdir()):
            if not f.is_file():
                continue
            dst = out / f.name
            b = f.read_bytes()
            if not dst.exists() or dst.read_bytes() != b:
                dst.write_bytes(b)
                moved += 1
        print(f"  brand: {len(list(brand.iterdir()))} files in assets/, "
              f"{moved} copied into the site folder")
    else:
        print("  brand: no assets/ -- run python3 build_brand.py")

    # bills.html and the files it loads are written by hand rather than
    # generated, and nothing in the pipeline copied them into the output
    # folder -- so an edit sat at the project root while the deploy shipped
    # whatever was in site/, which looks exactly like the edit having no
    # effect and cost a round more than once. app.css and app.js are files of
    # their own rather than a <style> and a <script> inside the page, so a
    # second page loads the SAME renderer and a reader who opens six bills
    # downloads 110 KB once instead of six times.
    #
    # Copied as they are. Nothing is rewritten on the way through any more:
    # the version query these three used to gain is a header now, written
    # below.
    for name in ("bills.html", "app.css", "app.js", "find.js"):
        src = Path(name)
        if not src.exists():
            continue
        dst = out / name
        body = src.read_bytes()
        if not dst.exists() or dst.read_bytes() != body:
            dst.write_bytes(body)
            print(f"copied {name} into the site folder")

    # The bill matcher, cut out of app.js for the header search on the pages
    # that do not load app.js. See bill_matcher_js.
    if Path("app.js").exists():
        body = bill_matcher_js(
            Path("app.js").read_text(encoding="utf-8")).encode("utf-8")
        dst = out / "billmatch.js"
        if not dst.exists() or dst.read_bytes() != body:
            dst.write_bytes(body)
            print("  billmatch.js: app.js's bill matcher, for the header "
                  "search")

    # LF, not the platform default: this file is parsed by Pages, not
    # by anything on this machine, and write_text on Windows would
    # give every line a carriage return Cloudflare never asked for.
    hdr = out / "_headers"
    if (not hdr.exists()
            or hdr.read_text(encoding="utf-8", newline="") != HEADERS):
        hdr.write_text(HEADERS, encoding="utf-8", newline="\n")
        print("  _headers: the three asset files must be revalidated, not reused")
    # A TAB'S ADDRESS IS ITS RECORD'S PAGE. /bill/2026/hb1442/votes is not a
    # file; Cloudflare Pages serves the record's own page there (a 200
    # rewrite, not a redirect, so the address stays), and app.js opens the tab
    # the address names. The page's canonical link is the record's own
    # address and no tab address is in the sitemap, so each record is indexed
    # once. The slugs here and BILL_TABS/MEMBER_TABS/COMMITTEE_TABS in app.js
    # are the same lists; preflight holds them together.
    red = out / "_redirects"
    if (not red.exists()
            or red.read_text(encoding="utf-8", newline="") != REDIRECTS):
        red.write_text(REDIRECTS, encoding="utf-8", newline="\n")
        print("  _redirects: a tab's address serves its record's page")

    legs = json.loads((out / "legislators.json").read_text(encoding="utf-8")) \
        if (out / "legislators.json").exists() else []
    towns = json.loads((out / "towns.json").read_text(encoding="utf-8")) \
        if (out / "towns.json").exists() else {}


    # The "Your town" page was here. The finder it held is the top of the
    # legislators page, built from the same towns.json by the same finder,
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
        ph = {"in session": ("live", "In Session"),
              "veto day pending": ("wait", "Awaiting Veto Day"),
              "between sessions": ("wait", "Between Sessions"),
              "out of session": ("off", "Out of Session")}.get(
                  (S.get("phase") or "").lower(), ("off", S.get("phase") or ""))
        ms = (S.get("milestones") or [{}])[0]

        def fdy(d):
            """"Aug 19, 2026", the form HOME_JS's fdy() writes."""
            try:
                return f"{fd(d)}, {int(d[:4])}"
            except (TypeError, ValueError):
                return esc(d or "")
        stale = (S.get("stale_days") or 0) > 45
        # THE SAME BOX THE SCRIPT DRAWS, line for line. This copy is what a
        # reader without JavaScript and every crawler get. It once had no last
        # floor session, no count of hearings and no date -- so it could not
        # say it was stale, which is the one thing a hand-kept summary most
        # needs to be able to say. The livestream links are in neither copy,
        # as redundant.
        static_state = (
            f'<div class="statebox {ph[0]}"><div class="stateline">'
            f'<span class="dot"></span><b>{esc(ph[1])}</b>'
            + (f'<span class="statemeta">Last Floor Session: {fdy(S["last_session"])}</span>'
               if S.get("last_session") else "")
            + "</div>"
            + (f'<p class="statehead">{esc(S["headline"])}</p>'
               if S.get("headline") else "")
            + (f'<p class="statenote">{esc(S["note"])}</p>' if S.get("note") else "")
            + (f'<p class="statenote"><b>Next: {esc(ms.get("label"))}</b>, '
               f'{fd(ms.get("date"))}. {esc(ms.get("note"))}</p>' if ms.get("label") else "")
            # THE STALE WARNING CARRIES ITS OWN DATE, so the page can work it
            # out again in the reader's clock: it was written when the site was
            # built and read for as long as the build stood.
            + (f'<p class="statenote stalewarn" style="color:var(--st-veto)" '
               f'data-updated="{esc(S.get("updated") or "")}">This summary was last '
               f'updated {S["stale_days"]} days ago and may be out of date.</p>' if stale
               else (f'<p class="statemeta upd" style="margin-top:8px" '
                     f'data-updated="{esc(S.get("updated") or "")}">Summary Updated: '
                     f'{fdy(S["updated"])}</p>' if S.get("updated") else ""))
            + "</div>")

    # The five counts the home page drew here are gone, for the reason the
    # script's copy above gives. The data page still counts, which is where
    # counting belongs.

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
            # A bill passes with a majority of the members VOTING, so there is
            # no fixed number to print for it; "a simple majority is 201" was
            # a majority of the 400 seats, which decides nothing. Three fifths
            # is of the members in office, counted from the roster, and the
            # sentence says which count it is.
            note = (f'<p class="statemeta" style="margin:6px 0 0">A bill passes '
                    f'with a majority of the members voting. Passing a '
                    f'constitutional amendment takes three fifths of the '
                    f'members in office: {x.get("three_fifths", "")} of the '
                    f'{x["sitting"]} on the current roster. A veto override '
                    f'needs {esc(x.get("two_thirds_note", ""))}.</p>')
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

    def roster_section(legs):
        """The roster, three ways, and the House floor as a chart.

        Asked for on 18 September: "on the legislators page, there would be
        three tabs for ways to sort the legislators, sorted alphabetically by
        last name, sorting by county as they are now, and sorting by seat
        number." So the three orderings are TABS, not a dropdown -- a reader
        picks how they want the chamber arranged and the page rearranges.

        By county is the listing this page already had, drawn into #out by the
        script from legislators.json, collapsible per county. It is unchanged:
        "as they are now" was the instruction.

        By last name and By seat are written into the HTML. That costs 406
        rows twice, about 15 KB over the wire, and buys a roster a crawler and
        a reader with no JavaScript can both walk -- which this page, being a
        search box that showed nothing until somebody typed, did not have.

        WHY ONLY REPRESENTATIVES HAVE A CHART. All 382 sitting
        representatives carry a seat number and not one of the 24 senators
        does, in the General Court's own roster. That is not missing data: the
        House assigns numbered seats in Representatives Hall and the Senate
        does not. So the Senate is listed under the chart, and says why.

        The seat number is the reason people look this up at all: a
        representative's licence plate carries it.
        """
        H = sorted((m for m in legs if m.get("chamber") == "H"),
                   key=lambda m: int(m.get("seat") or 0))
        S = sorted((m for m in legs if m.get("chamber") == "S"),
                   key=lambda m: int(str(m.get("district") or 0) or 0))
        # THE FIRST LETTER, UPPERCASED, which is what the rest of the site
        # does with a party (app.js:2873). The roster spells it out --
        # "Republican", "Democrat", "Independent" -- and the classes the
        # stylesheet knows are p-R, p-D and p-I, so writing the word straight
        # through produced `class="seat p-Republican"` and 400 seats in the
        # default grey.
        def pcode(m):
            return str(m.get("party_code") or m.get("party") or "").upper()[:1]
        by_seat = {int(m["seat"]): {"name": m.get("display_plain") or m.get("name"),
                                    "party_code": pcode(m),
                                    "slug": m.get("slug") or ""}
                   for m in H if m.get("seat")}

        def surname(m):
            n = (m.get("name") or "")
            return (n.split(",")[0] if "," in n else n).strip().lower()

        def given(m):
            n = (m.get("name") or "")
            return (n.split(",", 1)[1] if "," in n else "").strip().lower()

        def li(m, lead):
            """One row: the column that leads it, then the person as a chip.

            THE PERSON IS DRAWN BY THE SHARED COMPONENT, not by this function.
            It used to write its own name, district and party into three
            spans, so the same member read one way here and another on a
            committee page or a bill -- which is the exact bug pchip was made
            to end. display_full already carries the title, the party letter
            and the district ("Rep. Suzanne Vail (D - Hills 6)"), so the three
            spans were also saying twice what the chip says once.

            The LIST stays a list. Asked for on 18 September: the alphabetical
            view is split halfway down so a reader follows A to Z down one
            column and on down the next, rather than left-to-right across a
            flowing row. A committee's roster flows because it is a dozen
            people; a chamber's is four hundred.

            `lead` is the seat number in the seat view and the district in the
            Senate's. It is empty in the alphabetical view, where the chip's
            own "Rep." says it already.
            """
            return (f'<li class="seatrow" data-seat="{esc(str(m.get("seat") or ""))}" '
                    f'data-last="{esc(surname(m))}" '
                    f'data-county="{esc(m.get("county") or "")}" '
                    f'data-slug="{esc(m.get("slug") or "")}">'
                    + (f'<span class="sseat">{esc(lead)}</span>' if lead else "")
                    + pchip(m) + "</li>")

        # Sorted by number, which is the order the person asked the dropdown
        # to be in. A vacant seat is not offered: there is nobody to go to.
        opts = "".join(
            f'<option value="{esc(str(m["seat"]))}">{esc(seating.plate(m["seat"]))} '
            f'&mdash; {esc(m.get("display_plain") or m.get("name"))}</option>'
            for m in H if m.get("seat"))

        # TWO NUMBERS THAT LOOK LIKE ONE. 382 of the House's 400 members hold
        # a seat, so 18 seats are vacant -- but the Speaker's chair is on the
        # rostrum and not on the floor, so only 381 of the 400 places DRAWN
        # below are taken and 19 of them are empty. The page said "18 vacant"
        # over a picture with 19 dashed circles in it, which is the kind of
        # mismatch a reader counts and then distrusts the rest for. Both
        # numbers are said, and why they differ.
        seated = len(by_seat)
        vacant = 400 - seated
        on_floor = seated - (1 if seating.SPEAKER_SEAT in by_seat else 0)
        empty_places = 400 - on_floor

        # SENATORS AND REPRESENTATIVES APART, "like the county page does" --
        # asked for on 18 September. One alphabet across both chambers put a
        # senator between two representatives with nothing to say which was
        # which except the honorific, and the two chambers are not one body.
        # ONE COLUMN PER PARTY (the person, 24 September): within each chamber
        # the alphabetical view is broken up by party, each column A to Z by
        # last name and then by first name -- Alissandra Murray before Megan
        # Murray. The largest party first, so the majority leads.
        PARTY_PLURAL = {"Republican": "Republicans", "Democrat": "Democrats",
                        "Democratic": "Democrats", "Independent": "Independents",
                        "Libertarian": "Libertarians"}

        def alpha_block(ms, heading):
            groups = {}
            for m in ms:
                groups.setdefault((m.get("party") or "Party not on file").strip(), []).append(m)
            cols = []
            for party, pm in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
                # Surname, then given name: the seat order it once fell back on
                # put Michael Aron above Judy Aron and three Smiths out of order.
                pm = sorted(pm, key=lambda m: (surname(m), given(m)))
                name = PARTY_PLURAL.get(party, party) if len(pm) != 1 else party
                cols.append(f'<section class="pcol"><h3>{esc(name)} &mdash; {len(pm)}</h3>'
                            '<ol class="seatlist rlist">'
                            + "".join(li(m, "") for m in pm) + "</ol></section>")
            return (f'<h2>{heading} &mdash; {len(ms)}</h2>'
                    '<div class="partycols">' + "".join(cols) + "</div>")
        by_last = alpha_block(S, "Senate") + alpha_block(H, "House")
        by_seat_rows = "".join(
            li(m, seating.plate(m["seat"]) if m.get("seat") else "") for m in H)
        senate_rows = "".join(li(m, f'District {m.get("district")}') for m in S)

        return f"""<section class="roster" id="roster">
<div class="rtabs" role="tablist" aria-label="How to arrange the roster">
  <button type="button" role="tab" id="tab-last" data-pane="pane-last"
    aria-controls="pane-last" aria-selected="true">By last name</button>
  <button type="button" role="tab" id="tab-county" data-pane="pane-county"
    aria-controls="pane-county" aria-selected="false">By county</button>
  <button type="button" role="tab" id="tab-seat" data-pane="pane-seat"
    aria-controls="pane-seat" aria-selected="false">By seat</button>
</div>

<div class="rpane" id="pane-last" role="tabpanel" aria-labelledby="tab-last">
<p class="src">All {len(legs)} sitting members, by surname, each chamber on
its own.</p>
{by_last}
</div>

<div class="rpane" id="pane-county" role="tabpanel" aria-labelledby="tab-county">
<div id="out"></div>
</div>

<div class="rpane" id="pane-seat" role="tabpanel" aria-labelledby="tab-seat">
<h2>Where they sit</h2>
<p class="src">Every representative has a numbered seat in Representatives
Hall, and it is the number on their licence plate. Tap a seat to see who is in
it; tapping does not leave the page, and the name it gives you is the link. This is a diagram of the
five divisions, not a drawing of the room: it is faithful to which division a
seat is in and to the seat&rsquo;s number, and not to the true distances.
{seated} of the 400 seats are filled{f" and {vacant} are vacant" if vacant else ""}.
The Speaker&rsquo;s chair is on the rostrum rather than on the floor, so
{empty_places} of the places drawn below are empty.</p>
<div class="seatctl">
  <label for="sgo">Go to a seat</label>
  <select id="sgo"><option value="">Seat number&hellip;</option>{opts}</select>
  <label for="sq">Find</label>
  <input id="sq" type="search" autocomplete="off"
    placeholder="A name, a county or a seat number">
</div>
<div class="seatbar">
  <p class="seathint">Scroll or pinch to zoom, drag to move about the floor.</p>
  <div class="seatzoom">
    <button type="button" id="szout" aria-label="Show more of the floor">&minus;</button>
    <button type="button" id="szin" aria-label="Show the seats larger">+</button>
    <button type="button" id="szfit">Fit</button>
  </div>
</div>
<div class="seatstage">
  <div class="seatwrap">{seating.svg(by_seat)}</div>
  <p class="seatnote" id="seatnote" role="status" aria-live="polite"></p>
</div>
<ol class="seatlist" id="seatlist">{by_seat_rows}</ol>
<h2>The Senate</h2>
<p class="src">The Senate has no seating chart: its 24 members are elected
from numbered districts and the chamber does not assign numbered seats the way
the House does.</p>
<ol class="seatlist senate">{senate_rows}</ol>
</div>
</section>"""

    # Built here, after home.json has been read: the legislators page now
    # carries the party composition, so it cannot be written before the
    # data that composition comes from.
    # TWO WAYS IN, SIDE BY SIDE, AND THE CHARTS AFTER THE ROSTER.
    #
    # This page stacked three things before the first legislator and measured
    # 1,236px to reach one at 1440: a 471px town picker, then a second heading
    # and a second lead, then a full-width search box, and then 359px of party
    # composition charts sitting BETWEEN the search box and its own results --
    # so typing a name pushed the answer 380px down the page.
    #
    # The charts are context, not a way in, so they go below the roster. The
    # two ways in -- by town, by name -- become one block of two panes, side
    # by side where there is room, because they are alternatives rather than
    # steps: a reader should see both at once and pick. One heading and one
    # sentence instead of two of each.
    leg_body = f"""<h1>Legislators</h1>
<p class="lead">{len(legs)} sitting members. Type a town to see who represents
it, or a name, county, party or committee to find a member.</p>
<div class="lfind">
  <label for="lq" class="sr">Your town, or a legislator&rsquo;s name</label>
  <input id="lq" type="search" autocomplete="off"
    placeholder="Your town, or a legislator&rsquo;s name" disabled>
  <p class="count" id="lcount">Loading&hellip;</p>
  <div class="lmatch" id="lmatch"></div>
</div>
<!-- The roster's #out lives inside the By county pane, and there must be only
     ONE of it. This line used to hold a second, left from when the roster was
     drawn straight into the page: getElementById returns the first in document
     order, so the county listing rendered HERE, above the tab bar, and the
     pane a reader opened by clicking By county stayed empty. Two elements with
     one id is valid HTML that no validator complains about and no test caught,
     because both halves of it looked like they worked. -->
{roster_section(legs)}
{('<div class="comp-wrap"><h2>Who holds the seats</h2>' + static_bar("S")
  + static_bar("H") + vacancies + "</div>") if C else ""}"""
    (out / "legislators.html").write_text(
        shell("Legislators | Granite Record", "legislators.html", leg_body,
              desc="Every member of the New Hampshire House and Senate: their "
                   "district, their party, the bills they sponsored and every "
                   "recorded vote they cast.",
              wide=True, script=LEGFIND_JS + SEATING_JS), encoding="utf-8")

    static_up = calendar_html(out)

    # The Committees card's offer, counted rather than typed. See
    # committees_with_roster: what the card promises is a roster, so the number
    # it names is the committees that have one, and it names none at all if
    # committees.json is not there to count.
    n_roster = committees_with_roster(out)
    cmte_offer = (f"Who sits on each of the {n_roster} committees with a "
                  "roster, and what it did on every day it met" if n_roster
                  else "Who sits on a committee, and what it did on every day "
                       "it met")
    if not n_roster:
        print("  committees: no site/committees.json to count, so the home "
              "page's Committees card names no number")

    static_recent = ""
    if H.get("recent"):
        static_recent = ("<h2>Latest activity</h2><table><tbody>" + "".join(
            f'<tr><td>{fd(r.get("date"))}</td><td>'
            f'<a href="bills.html#{esc(r.get("bill"))}">{esc(r.get("n"))}</a> '
            f'{esc(r.get("title"))}<br><span style="font-size:12px">'
            f'{esc(r.get("what"))}</span></td></tr>'
            for r in H["recent"][:RECENT_SHOWN]) + "</tbody></table>"
                         + RECENT_MORE)

    # THREE COLUMNS, AND THE MIDDLE ONE IS WRITTEN FIRST. The order here is
    # the order a screen reader hears and the order the Tab key takes; the
    # grid in style.css puts .hleft to the left of it. See the comment on
    # .hcols for why that way round.
    home_body = f"""<div class="hcols">
<div class="hmid">
<h1 class="lockup"><span>Granite Record</span></h1>
<p class="slogan">Public Records, Made Findable.</p>
<p class="lead">Keep up with New Hampshire legislation, find bills on the issues you
care about, learn how the legislature works, and explore the record from 1989 to
today.</p>
<div class="searchbig">
  <label for="hq" style="position:absolute;left:-9999px">Search bills</label>
  <input id="hq" type="search" placeholder="Bill number, or words from the title">
  <button id="hgo">Search</button>
</div>
<div class="entry">
  <a href="/bills"><b>Browse bills</b><span>Search by committee, topic, sponsor,
    status or the day it was voted on</span></a>
  <!-- COMMITTEES, NOT LEGISLATORS. The finder in the right-hand column asks
       for a town and says what a town gives you, in nearly the same sentence
       this card used to -- so on a 1440px screen the same offer was made
       twice, side by side. Committees had no route from the home page at all,
       and it is where a reader who knows the subject rather than the bill
       number starts. -->
  <a href="committees.html"><b>Committees</b><span>{cmte_offer}</span></a>
  <a href="learn.html"><b>Learn</b><span>How a bill moves, what the shorthand
    means, and how to testify</span></a>
</div>
<div id="fresh" class="fresh"></div>
<!-- UNDER THE REBUILD LINE, IN THE MIDDLE. This was a full-width band below
     all three columns, so the thing that changes most often on the site was
     the last thing on the page and was never beside the search box a reader
     had just used. Asked for on 19 September. The left rail keeps the week
     ahead and this keeps the days just gone, which is the same column a
     reader is already reading down. -->
<div id="recent" class="hrecent">{static_recent}</div>
</div>
<section class="hside hleft" aria-label="Where the General Court is, and what is coming up">
<div id="state">{static_state}</div>
<div id="upcoming">{static_up}</div>
</section>
<section class="hside hright" aria-label="Find your legislators, and what has just happened">
<div class="hfind">
  <h2>Find your legislators</h2>
  <p class="hfnote">A town gives you its House and Senate districts, its
  Executive Councillor and its member of Congress.</p>
  <!-- ONE BOX. There were two forms here, one asking for a town and one for a
       name, and they were two doors into the same room: legislators.html
       reads `(pr.get("town") || pr.get("q") || "")` into the single #lq box,
       which has always matched a town OR a name OR a county, party or
       committee. So the split asked the reader to classify what they were
       typing before they typed it, to no end. Asked for on 20 September.
       The parameter is q, which is what that page's own box submits. -->
  <form class="hfrow" action="legislators.html" method="get">
    <label for="hq2" class="sr">Your town, or a legislator's name</label>
    <input id="hq2" name="q" type="search"
      placeholder="Your town, or a legislator&rsquo;s name">
    <button type="submit">Find</button>
  </form>
</div>
<div id="session"></div>
</section>
</div>
<div id="composition"></div>
<div id="notable" hidden></div>"""
    (out / "index.html").write_text(
        shell("Granite Record \u2014 the New Hampshire legislative record",
              # THE FULL PAGE WIDTH, which is what "offset to the left"
              # was. .wrap is 820px aligned to the nav's own gutter, so on a
              # 1440px screen the home page was an 820px column with 360px of
              # empty ground to the right of it -- aligned, and unbalanced.
              # wide=True makes it the 1180px the nav and every record page
              # already use, so the stat grid and the three entry cards fill
              # the width instead of stopping two thirds across.
              "index.html", home_body, script=HOME_JS, wide=True,
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
    # THE FIGURES ARE COUNTED, NOT TYPED. about_figures.py says why at length:
    # the eight numbers this page used to state about its own accuracy were
    # written when the site held one term, and seven of them were wrong by the
    # time it held nineteen. fill() raises rather than publishing a sentence
    # with a hole where a number was.
    (out / "about.html").write_text(
        shell("About | Granite Record", "about.html",
              about_figures.fill(ABOUT, about_figures.figures(site=out)),
              desc="How Granite Record is built, where every fact on it comes "
                   "from, and how to report something that is wrong."),
        encoding="utf-8")

    # THE ALL-RESULTS PAGE. Served at /search -- Pages strips the extension --
    # and reached from the header panel's last row on every page of the site.
    # noindex, because what it holds depends entirely on a query string: there
    # is no page here for a crawler to keep, and every variant of it would be
    # a near-copy of the bill search and the roster, which ARE indexed.
    search_body = """<h1 id="reshead">Search the record</h1>
<p class="lead" id="reslead">Every sitting legislator and every member who has
left, every committee, every town and ward, every subject bills are filed
under, and this term's bills. The bill search has every term, with filters.</p>
<form class="resfind" action="/search" method="get" role="search">
  <label for="resq" class="sr">A legislator, a committee, a town, a subject or a bill</label>
  <input id="resq" name="q" type="search" autocomplete="off"
    placeholder="A legislator, a committee, a town, a subject or a bill" disabled>
</form>
<div id="resout"></div>
<noscript><p class="note">This page needs JavaScript to search. Without it,
the <a href="/bills">bill search</a>, the <a href="/legislators">roster</a> and
the <a href="/committees">committee list</a> are all plain pages.</p></noscript>"""
    search_page = shell("Search | Granite Record", "", search_body,
                        desc="Search Granite Record for a legislator, a "
                             "committee, a town, a subject or a bill.",
                        script=SEARCH_JS)
    search_page = search_page.replace(
        '<link rel="canonical" href="https://graniterecord.org/">',
        '<meta name="robots" content="noindex,follow">')
    (out / "search.html").write_text(search_page, encoding="utf-8")

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
          f"about.html, search.html, 404.html, style.css -> {out}/  (learn.html: build_civics.py)")
    if not legs:
        print("  legislators.json missing — run build_site_v2.py first")


if __name__ == "__main__":
    main()
