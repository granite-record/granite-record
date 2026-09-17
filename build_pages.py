#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.76
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

    THE SECOND STYLESHEET IS GONE, 16 September. These pages had 24 KB of CSS
    of their own here, against app.css's 119 KB for the record pages, and a
    fix landed in one of them at a time: eleven font sizes in one file and
    more in the other, a component drawn twice, DESIGN.md's rules kept by
    hand in two places. The block lives in app.css between PAGES:START and
    PAGES:END now, scoped to body.pg, and this reads it -- the same trick
    palette() and shared() already used, applied to the rest of the file.

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
         '<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;600'
         '&family=Newsreader:opsz,wght@6..72,400;6..72,600&display=swap" rel="stylesheet">')


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
# The two files a page reads to say what is true today: the home page's own
# summary, and the header search's index of members, committees and towns. A
# cached copy of either is a page contradicting itself -- on 16 September the
# home page's built HTML said 39 hearings and its script, reading a cached
# home.json, said 4.
/home.json
  Cache-Control: public, max-age=0, must-revalidate
/find.json
  Cache-Control: public, max-age=0, must-revalidate
"""

# Tab addresses, served their record's page: see where this is written.
# "videos" is kept alongside "hearings" deliberately. The tab was relabelled on
# 17 September -- it lists a bill's sittings and a recording only where one
# exists, and recordings begin in May 2020, so for fifteen terms it read
# "Videos" over entries that all said "No recording exists". Both addresses go
# in _redirects: the new one because that is what the page now writes, the old
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
# data.html and manifest.json have described every table since the 10th and
# nothing linked them from the bottom of a page, so the only way to find the
# bulk downloads was to already know they existed. The same line says when the
# data was last rebuilt: a reader deciding whether to trust a status should not
# have to go to the home page to find out how old it is.
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
FOOT_DATA = ('<a href="directory.html">The whole record, as lists</a> — every bill, '
             'legislator and town as plain links. '
             '<a href="data.html">Bulk data</a> — every table on this '
             'site as CSV, with a manifest naming each column.')


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
MEET_KIND = {"public hearing": ("Public hearing", "k-hearing"),
             "hearing": ("Public hearing", "k-hearing"),
             "executive session": ("Executive session", "k-exec"),
             "work session": ("Work session", ""),
             "subcommittee work session": ("Subcommittee work session", "")}


def meeting_key(u):
    """What makes one meeting out of a handful of `upcoming` bill rows.

    ONE DEFINITION, BECAUSE TWO PLACES COUNT IT. The calendar groups by this
    tuple and the status box above it states the number of groups; when the
    grouping lived only inside calendar_html the box counted the rows instead
    and said "39 hearings scheduled in the next two weeks" over a fortnight
    holding eight meetings -- and no hearing at all. Nothing can drift now
    without moving both.
    """
    return (u.get("date") or "", u.get("time") or "", u.get("committee") or "",
            u.get("what") or "", u.get("venue") or "")


def meeting_line(n, floor=False):
    """The status box's one sentence about the fortnight ahead.

    Its own function because the same sentence is written in three places and
    they have disagreed before: here for the built page, in HOME_JS's
    _meetline for a page that reached the reader with no box in it, and again
    in the clock block that counts the days that have passed off the total.
    `floor` is true when home.json's 80-row cap hid meetings from the count and
    the page must not claim the number is all of them; it travels on the
    element as data-partial so the rewrite keeps the word it earned.
    """
    if not n:
        return ""
    return (f'<p class="statenote hearcount" data-total="{n}"'
            + (' data-partial="1"' if floor else "")
            + f'>{"At least " if floor else ""}{n} committee '
            f'meeting{"" if n == 1 else "s"} scheduled in the next two '
            "weeks.</p>")


def calendar_html(H, out):
    """The next fortnight of committee business, by day and then by meeting."""
    import datetime as _dt
    from collections import OrderedDict

    # main()'s esc is nested inside it and this is module level, so it gets
    # its own -- the same one shell() uses two hundred lines down.
    esc = lambda s: _html.escape(str(s or ""), quote=True)

    up = H.get("upcoming") or []
    if not up:
        # The honest out-of-session state. The General Court is a part-time
        # legislature and this is what the page says for half the year, so it
        # says when business resumes rather than just "nothing".
        return ('<section class="cal"><h2>Coming up</h2>'
                '<p class="note">No committee meetings are scheduled in the '
                'next two weeks. The General Court sits from January to June, '
                'and committees meet on bills from the autumn filing period '
                'onwards.</p></section>')

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

    meets = OrderedDict()
    for u in up:
        meets.setdefault(meeting_key(u), []).append(u)

    today = _dt.date.today()

    def when(d):
        """Tue 15 Sep, and how far off it is -- the part a reader acts on."""
        try:
            dd = _dt.date.fromisoformat(d)
        except ValueError:
            return d, ""
        off = (dd - today).days
        rel = ("today" if off == 0 else "tomorrow" if off == 1
               else f"in {off} days" if 0 < off < 14 else "")
        return dd.strftime("%a %d %b").replace(" 0", " "), rel

    days = OrderedDict()
    for key in sorted(meets, key=lambda k: (k[0], k[1])):
        days.setdefault(key[0], []).append(key)

    html = ['<section class="cal"><h2>Coming up</h2>']
    for date, keys in days.items():
        label, rel = when(date)
        # THE DAY'S OWN DATE TRAVELS WITH IT. This block is written when the
        # site is built and read for as long as the build stands: on
        # 16 September the home page still called the 15th "today", with a
        # meeting that had already happened at the top of Coming up. HOME_JS
        # reads this attribute in the reader's own clock, drops the days that
        # have passed and writes the relative word again.
        html.append(f'<div class="calday" data-d="{esc(date)}"><h3 class="caldate">'
                    f'<span>{esc(label)}</span>'
                    f'<span class="cdrel">{esc(rel)}</span>'
                    + "</h3>")
        for key in keys:
            _d, time, cmte, what, venue = key
            rows = meets[key]
            word, kcls = MEET_KIND.get(what.strip().lower(),
                                       (what.capitalize() if what else "Meeting", ""))
            n = len(rows)
            html.append('<details class="calmeet"><summary>')
            if time:
                html.append(f'<span class="caltime">{esc(time)}</span>')
            html.append(f'<span class="calcmte">{esc(cmte)}</span>')
            html.append(f'<span class="calkind {kcls}">{esc(word)}</span>')
            html.append(f'<span class="calcount">{n} bill{"" if n == 1 else "s"}</span>')
            if venue:
                html.append(f'<span class="calwhere">{esc(venue)}</span>')
            html.append('<span class="caret"></span></summary>'
                        '<div class="calbody"><ul class="calbills">')
            for r in rows:
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
            cc = code.get(cmte.strip().lower())
            if cc:
                html.append('<p class="calmore">'
                            f'<a href="committee/{esc(cc)}.html">'
                            f'The {esc(cmte)} committee</a></p>')
            html.append("</div></details>")
        html.append("</div>")
    # What did not fit. build_site_v2 writes upcoming[:80] and its
    # hearings_next_14 counts the fortnight's bill rows uncapped, so the
    # difference is what the cap dropped. The status box beside this counts the
    # MEETINGS these rows make -- it can only count the rows it was given, and
    # says "at least" when this line has something to report, so the two
    # numbers no longer stand next to each other contradicting one another.
    more = (H.get("status") or {}).get("hearings_next_14", 0) - len(up)
    if more > 0:
        html.append(f'<p class="note">{more} more bill{"" if more == 1 else "s"} '
                    "sit in the fortnight beyond these; each one is on its own "
                    "committee's page.</p>")
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
                        ("learn.html", "Learn")):
        cur = ' aria-current="page"' if href == current else ""
        tabs.append(f'<a href="{href}"{cur}>{label}</a>')
    # ONE WRAPPER, WRITTEN TWICE BECAUSE THE NAV IS. bills.html carries the
    # same <div class="navtabs"> around the same seven links and app.css
    # styles it once; without it the links wrap through the middle of the row
    # and the theme control is stranded on a line of its own.
    nav = [f'<div class="navtabs">{"".join(tabs)}</div>',
           # The same control bills.html carries, read from there rather than
           # written again here.
           themer("BTN")]
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
<p class="fbkwrap"><a class="fbk" href="https://forms.gle/PYw9c3xgpDDwvX7E9" target="_blank"
 rel="noopener">Tell us what you think</a>
<span class="fbknote">This site is new and being tested. Two minutes of your feedback is worth more than a week of our guessing.</span></p>
Built from public records published by the New Hampshire
General Court. Not affiliated with the General Court.
<a href="about.html">How this is made</a>.
<span class="corrections">Found an error?
<a href="mailto:contact@graniterecord.org">contact@graniterecord.org</a>
</span>
<p class="footdata">{FOOT_DATA}<span id="built"></span></p>
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
them. The search box works in your own browser against files this site
serves; what you type is never sent anywhere. Video is embedded from
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
record at gencourt.state.nh.us always takes precedence over anything shown here.</p>

<h2>Independence</h2>
<p>This site is not affiliated with or endorsed by the New Hampshire General Court.
It takes no position on any bill.</p>
"""

LEGFIND_JS = """
<script>
(function(){
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
// Anchored to the site root, not to the page. legislators.html is served at
// /legislators, and a legislators/ folder of per-member data sits beside it --
// so /legislators can be redirected to /legislators/, and a relative
// "legislators/377204.json" then resolves to /legislators/legislators/... and
// 404s. The bill page had the same trap and it cost an evening.
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
      +`<span class="chip p-${esc(m.p)}">${esc(m.p)}</span>`
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
        +ms.map(m=>`<div class="mem">`
          +`<a href="legislator/${esc(m.slug)}.html">${esc(m.display)}</a>`
          +` <span class="chip p-${esc(m.p)}">${esc(m.p)}</span>`
          +` <span class="mdist">${esc(m.dlabel)}</span></div>`).join("")
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

  // Title case, and a colon after each label, as the person wrote the box on
  // 14 September. The Python copy below says the same.
  const PHASE={"in session":["live","In Session"],
               "veto day pending":["wait","Awaiting Veto Day"],
               "between sessions":["wait","Between Sessions"],
               "out of session":["off","Out of Session"]};
  const ph=PHASE[(S.phase||"").toLowerCase()]||["off",S.phase||"Status unknown"];
  const ms=(S.milestones||[])[0];
  const stale=S.stale_days>45;
  // MEETINGS, NOT BILL ROWS, AND THE NOUN FOLLOWS WHAT THEY ARE. This line
  // printed status.hearings_next_14, which is the length of home.json's
  // `upcoming` -- one row per bill. On 16 September that made it "39 hearings
  // scheduled in the next two weeks" over a fortnight holding eight meetings
  // and not one hearing: seventeen subcommittee work sessions, fifteen
  // executive sessions and seven full committee work sessions, on three days.
  // Grouped by the key the calendar below groups by, so the box and "Coming
  // up" are one count of one thing. The Python copy does the same.
  const _meetline=(rows14)=>{
    const u=H.upcoming||[];
    const n=new Set(u.map(m=>JSON.stringify(
      [m.date||"",m.time||"",m.committee||"",m.what||"",m.venue||""]))).size;
    if(!n)return "";
    // home.json carries at most 80 of the fortnight's bill rows. Where the cap
    // bit, meetings are hidden with them and this number is a floor, so it is
    // said as one -- the calendar's own note says how many bills went missing.
    const part=rows14>u.length;
    return `<p class="statenote hearcount" data-total="${n}"${
      part?' data-partial="1"':""}>${part?"At least ":""}${n} committee `
      +`meeting${n===1?"":"s"} scheduled in the next two weeks.</p>`;
  };
  // ONE RENDERER WINS, AND IT IS THE SERVER'S. The same box is written into the
  // page at build time and again here, and on 16 September the two disagreed on
  // screen: the HTML said 39 hearings and this said 4, because home.json came
  // out of the browser's cache while the page itself is revalidated every time.
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
      ${_meetline(S.hearings_next_14||0)}
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

  // THE FIVE COUNTS ARE GONE, 15 September, at the person's word: they sat
  // between the search box and the three cards that are the actual way in, and
  // nobody arrives to be told how many bills exist. The scale of the record is
  // said once, in the footer's link to the data. .statgrid still styles the
  // same grid on the data page.

  // #upcoming IS NOT TOUCHED HERE, ON PURPOSE. The calendar is rendered into
  // the page by calendar_html() at build time, from the same home.json this
  // script reads -- so re-rendering it here would be a second renderer of one
  // thing, which is the mistake this project has paid for more than once, and
  // it would render it WORSE: the bill titles are resolved out of
  // site/idx/<term>.json, 1.19 MB that the home page must not fetch to print
  // four of them, and the meeting rows are <details> elements that need no
  // script to open. Leaving it alone means the calendar also works before this
  // file loads and with JavaScript off.

  // COMING UP, IN THE READER'S OWN CLOCK. The calendar block is written when
  // the site is built, and a build stands for as long as it stands: on the
  // morning of 16 September the home page still headed the 15th "today", with
  // a Legislative Administration session that had already met at the top of
  // the list. Each day carries its own date, so this drops the days that have
  // gone and says how far off the rest are now. Nothing else here is touched.
  (function(){
    const now=new Date(); now.setHours(0,0,0,0);
    const days=[...document.querySelectorAll(".calday[data-d]")];
    let left=0,gone=0;
    days.forEach(d=>{
      const p=d.dataset.d.split("-").map(Number);
      const off=Math.round((new Date(p[0],p[1]-1,p[2])-now)/86400000);
      // MEETINGS, because that is the unit the box above counts. It counted
      // the bill rows of a day that had passed and subtracted them from a
      // count of bill rows; both are meetings now and the arithmetic has to
      // follow, or a day going by takes seven off a count of eight.
      if(off<0){gone+=d.querySelectorAll(".calmeet").length;d.remove();return;}
      left++;
      const rel=d.querySelector(".cdrel");
      // Fourteen days out is still inside the fortnight this block covers, so
      // it says how far off it is like every other day. `off<14` left the last
      // day of the window with no label at all.
      if(rel)rel.textContent=off===0?"today":off===1?"tomorrow"
        :off<=14?`in ${off} days`:"";
    });
    const cal=document.querySelector(".cal");
    if(cal&&days.length&&!left){
      cal.innerHTML=`<h2>Coming up</h2><p class="note">No committee meetings are
        scheduled in the next two weeks. The General Court sits from January to
        June, and committees meet on bills from the autumn filing period
        onwards.</p>`;
    }
    // The status box counts the same meetings, so it is counted again here
    // rather than left saying what was true when the site was built: the
    // build's total less the meetings whose day has passed, not a count of
    // what is on screen, because the calendar can be shorter than the
    // fortnight. data-partial says the build already knew its number was a
    // floor, and the word it earned travels with it.
    const hc=document.querySelector(".statebox .hearcount");
    if(hc){
      const n=Math.max(0,(+hc.dataset.total||0)-gone);
      if(!n)hc.remove();
      else hc.textContent=`${hc.dataset.partial?"At least ":""}${n} committee `
        +`meeting${n===1?"":"s"} scheduled in the next two weeks.`;
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
// ONE ADDRESS, AND NO EMPTY QUESTION. Search with nothing typed sent the
// reader to /bills?q= -- the same page the header's Bills tab reaches at
// /bills, with a query string saying the reader searched for nothing. The
// person reported the three addresses this page had on 16 September; this was
// one of them. /bills is what the host serves and what the header lands on.
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

    # A MEETING IS THE THING; A BILL ROW IS NOT. The status box printed
    # status.hearings_next_14, which is build_site_v2's len(upcoming), and
    # `upcoming` is one row per bill -- so on 16 September it read "39 hearings
    # scheduled in the next two weeks" over a fortnight whose 39 rows were 17
    # subcommittee work sessions, 15 executive sessions and 7 full committee
    # work sessions: eight meetings on three days, and not one hearing among
    # them. Grouped here by meeting_key, the same key the calendar below groups
    # by, so the count and the blocks under it are one count of one thing. The
    # noun is the calendar's own: its empty state has said "committee meetings"
    # all along.
    #
    # The cap is the caveat. home.json holds upcoming[:80] while
    # hearings_next_14 counts the fortnight whole, so where the cap bit these
    # meetings are a floor -- meeting_line() says "at least" then, and the
    # calendar's own note names the bills that went with them.
    up14 = H.get("upcoming") or []
    meets14 = len({meeting_key(u) for u in up14})
    if (S.get("hearings_next_14") or 0) > len(up14):
        print(f"  status box: home.json carries {len(up14)} of the "
              f"fortnight's {S['hearings_next_14']} bill rows, so its "
              f'{meets14} meetings are a floor and the page says "at least"')

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
        # Meetings, not bill rows -- counted above. hearings_next_14 counts
        # the fortnight whole where home.json carries upcoming[:80], so when
        # it is the larger the cap hid meetings and the line says "at least".
        hearline = meeting_line(
            meets14, (S.get("hearings_next_14") or 0) > len(up14))
        stale = (S.get("stale_days") or 0) > 45
        # THE SAME BOX THE SCRIPT DRAWS, line for line. This copy is what a
        # reader without JavaScript and every crawler get, and until 13
        # September it had no last floor session, no count of hearings and
        # no date -- so it could not say it was stale, which is the one thing
        # a hand-kept summary most needs to be able to say. The livestream
        # links are gone from both copies: the person found them redundant on
        # 14 September.
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
            # THE COUNT AND THE STALE WARNING CARRY THEIR OWN DATES, so the page
            # can work them out again in the reader's clock. Both were written
            # when the site was built and read for as long as the build stood.
            + hearline
            + (f'<p class="statenote stalewarn" style="color:var(--st-veto)" '
               f'data-updated="{esc(S.get("updated") or "")}">This summary was last '
               f'updated {S["stale_days"]} days ago and may be out of date.</p>' if stale
               else (f'<p class="statemeta upd" style="margin-top:8px" '
                     f'data-updated="{esc(S.get("updated") or "")}">Summary Updated: '
                     f'{fdy(S["updated"])}</p>' if S.get("updated") else ""))
            + "</div>")

    # The five counts the home page drew here were taken out on 15 September at
    # the person's word: they stood between the search box and the three cards
    # that are the way in, and a visitor does not arrive to be told how many
    # bills exist. The data page still counts, which is where counting belongs.

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
<div id="out"></div>
{('<div class="comp-wrap"><h2>Who holds the seats</h2>' + static_bar("S")
  + static_bar("H") + vacancies + "</div>") if C else ""}"""
    (out / "legislators.html").write_text(
        shell("Legislators | Granite Record", "legislators.html", leg_body,
              desc="Every member of the New Hampshire House and Senate: their "
                   "district, their party, the bills they sponsored and every "
                   "recorded vote they cast.",
              wide=True, script=LEGFIND_JS), encoding="utf-8")

    static_up = calendar_html(H, out)

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
        static_recent = "<h2>Latest activity</h2><table><tbody>" + "".join(
            f'<tr><td>{fd(r.get("date"))}</td><td>'
            f'<a href="bills.html#{esc(r.get("bill"))}">{esc(r.get("n"))}</a> '
            f'{esc(r.get("title"))}<br><span style="font-size:12px">'
            f'{esc(r.get("what"))}</span></td></tr>'
            for r in H["recent"][:12]) + "</tbody></table>"

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
  <form class="hfrow" action="legislators.html" method="get">
    <label for="ht" class="sr">Your town</label>
    <input id="ht" name="town" type="search" placeholder="Your town or city">
    <button type="submit">Find</button>
  </form>
  <form class="hfrow" action="legislators.html" method="get">
    <label for="hn" class="sr">Search the roster by name, county, party or committee</label>
    <input id="hn" name="q" type="search" placeholder="Name or committee">
    <button type="submit">Search</button>
  </form>
</div>
<div id="session"></div>
</section>
</div>
<div id="recent">{static_recent}</div>
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
