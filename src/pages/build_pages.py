#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.239
"""
Build the pages the navigation links to: legislators, town lookup, how it
works, and about.

    python3 src/pages/build_pages.py --out site

Reads site/legislators.json and site/towns.json, already written by
build_site_v2.py. Kept separate from that script so a change here cannot break
the bill search, which is the part that works.

Every page here links /app.css, the one stylesheet, as every record page
does (app.css, ONE STYLESHEET FOR EVERY PAGE).

The browser's files -- bills.html, app.css, components.js, app.js and find.js,
and print.js and print.css, a bill's print sheet -- are read from src/pages/
under the folder the build runs in, where they sit beside this file, and
copied into the site as they are, but for these: components.js with the words
of src/pages/words/ written between its markers (with_words), app.css without
its comments (strip_css), every script without its comments (published_js,
strip_js.py), and bills.html, the bill search, as the host serves it
(bills_page).
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import about_figures
import chrome
import bill_order as BO
import build_date
import civics as _civics
import html as _html
import i18n
import shell as _shell
from i18n import say
from components import WORDBOOK, chip, clock, date_span, icon, pchip, until_attrs
import components as _components
# A committee's recommendation in the committee page's words (REC_WORDS), for
# Latest Activity.
import committee_acts as CA
# A room in the words the rest of the site uses ("Granite Place 231" for the
# clerk's "GP 231"), for the Calendar's cards: plain_action.place.
import plain_action as PA
import seating
import strip_js
import json
import legislative_year as _year
import re
import shutil
from collections import OrderedDict, defaultdict, namedtuple


# THE LOGO AND THE ICONS: THE FILES A COMPLETE SITE CARRIES BESIDE ITS PAGES.
#
# NONE OF THEM IS IN THE REPOSITORY, bar the manifest, which is text. The
# person decided on 30 September 2026 that the bought clipart leaves git as
# the artist's drawing already had (DATA.md says why), and the commit that
# removed it is of 1 October, so on a fresh clone
# assets/ holds site.webmanifest and nothing else. The project's own machines
# get them back from the private kit (cloud_kit.json); a fork brings its own.
#
# This is the one list. main() places them and says which are missing;
# check_site.py reports a site without them as one plain error instead of ten
# broken links; preflight's fixture writes a stand-in for each, and holds this
# to what the pages, the stylesheet and the manifest actually name and to the
# kit entry that carries them. Every name is a file at the site's root:
#
#   favicon.ico, icon.svg, icon-32.png, icon-180.png   the <link>s in every head
#   icon-512.png, icon-512-pad.png                     site.webmanifest's icons
#   lockup.png                                         the home page's heading
#   og.png, og-<kind>.png                              a shared link's card
#   site.webmanifest                                   tracked, and here so that
#                                                      one list is the whole set
BRAND_FILES = ("favicon.ico", "icon.svg", "icon-32.png", "icon-180.png",
               "icon-512.png", "icon-512-pad.png", "lockup.png",
               "og.png", "og-bill.png", "og-committee.png", "og-learn.png",
               "og-legislator.png", "og-town.png", "site.webmanifest")

# THE HEADER'S MARK IS NOT ON THAT LIST, because a site is complete without
# it. It is the artist's drawing cut to its ink (build_brand.write_licensed),
# it exists only where assets/licensed/ does, and where it does not the header
# is the wordmark alone -- by design, not by accident: the rule that draws the
# mark sits between MARK:START and MARK:END in app.css, and main() keeps that
# block only when this file was placed. A fork that wants a mark puts a mask
# of this name in assets/ (opaque where the ink is, at any size: the 33x56 box
# fits it).
HEADER_MARK = "mark.png"


def without_mark(css):
    """app.css's bytes with the header mark's block cut out.

    For a build that has no mark.png: the rule would otherwise draw an empty
    33x56 box before the site's name on every page. Bytes in, bytes out; a
    file with no such block is returned as it came.
    """
    a = css.find(b"/* MARK:START")
    b = css.find(b"/* MARK:END")
    if a < 0 or b < a:
        return css
    end = css.find(b"\n", b)
    return css[:a] + (css[end + 1:] if end >= 0 else b"")


# THE PUBLISHED app.css CARRIES NO COMMENTS (23 October 2026). They are this
# file's documentation and stay in src/pages/app.css -- 526 KB of it, 153 KB
# over the wire, of which the rules are 266 KB and 46. Every page loads it now,
# the home page among them, which until that day loaded a 61 KB cut of it.
_CSS_WORD = re.compile(r"[A-Za-z0-9_\-\\\u0080-\U0010ffff]")


def strip_css(css):
    """app.css's text without its comments, and without the lines they leave
    blank. Nothing else is touched: a comment is found only outside a string
    and outside an unquoted url(...), where a /* is part of the value, and
    a comment that stood between two parts of one word (a/**/b) leaves a
    space, so the two are not joined into one. An unclosed comment raises,
    as it would end the stylesheet in a browser."""
    out, i, n = [], 0, len(css)
    while i < n:
        c = css[i]
        if c in "\"'":
            j = i + 1
            while j < n and css[j] != c and css[j] != "\n":
                j += 2 if css[j] == "\\" else 1
            out.append(css[i:j + 1])
            i = j + 1
        elif css.startswith("/*", i):
            j = css.find("*/", i + 2)
            if j < 0:
                raise ValueError(f"app.css has an unclosed comment at character {i}")
            j += 2
            before = out[-1][-1:] if out else ""
            if before and _CSS_WORD.match(before) and _CSS_WORD.match(css[j:j + 1]):
                out.append(" ")
            i = j
        elif css[i:i + 4].lower() == "url(":
            k = i + 4
            while k < n and css[k] in " \t\n":
                k += 1
            if k < n and css[k] in "\"'":
                out.append(css[i:k])
                i = k
            else:
                j = k
                while j < n and css[j] != ")":
                    j += 2 if css[j] == "\\" else 1
                out.append(css[i:j + 1])
                i = j + 1
        else:
            out.append(c)
            i += 1
    return "\n".join(ln.rstrip() for ln in "".join(out).split("\n") if ln.strip()) + "\n"


# THE HEADER THAT REPLACED THE VERSION QUERY.
#
# app.css and app.js (and style.css, while there was one) used to carry
# "?v=<content hash>" in every
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
/find.js
  Cache-Control: public, max-age=0, must-revalidate
/components.js
  Cache-Control: public, max-age=0, must-revalidate
/print.js
  Cache-Control: public, max-age=0, must-revalidate
/print.css
  Cache-Control: public, max-age=0, must-revalidate
/billmatch.js
  Cache-Control: public, max-age=0, must-revalidate
/lang/*
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
# thinking about it; these three are the tables /data documents. (A fourth,
# /index.json, every bill in one file, was retired on 5 October 2026: the
# files under /idx/ are the same rows a term at a time.)
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
                  "sponsors", "documents", "related")
MEMBER_TAB_SLUGS = ("cosponsored", "votes")
COMMITTEE_TAB_SLUGS = ("sessions",)
# THE LEARN HUB MOVED. /learn was the hub of the Learn pages and is now the
# first tab of the Resources hub, /resources (the person, 8 October 2026,
# decision 128: "/learn redirects to /resources ... the articles keep their
# /learn/<page> addresses"). Both spellings, because a request for
# /learn.html meets no file to be 308'd from; build_civics writes the hub and
# no longer a learn.html that could stand in the redirect's place.
# AND THE LEGISLATORS PAGE BECAME OFFICIALS (decision 127, 8 October 2026:
# "The Legislators tab and page are renamed Officials now"), so /legislators
# and /legislators.html answer the same way. Only those two addresses: the
# members' data under /legislators/<id>.json and their pages under
# /legislator/ are where they were, and no rule here reaches them.
# AND THREE LEARN PAGES BECAME HOW-TO GUIDES (the person, 17 October 2026:
# "Certain pages currently on learn can move to how to like using this site,
# finding your representatives, how to testify or attend meetings"). Each is
# at /guides/<slug> now (civics.HOW_TO), and its /learn/ address, which
# search engines have indexed and bookmarks hold, answers with a 301 to it,
# in both spellings for the reason above.
# AND A CITY'S OWN ADDRESS (the audit of 25 October 2026, M4). A city's
# pages are its wards', /town/concord-ward-3, so /town/concord -- the address
# a reader types and a search engine guesses -- answered 404. Each goes to the
# Officials page's town box with the city in it, which offers its wards
# (?town= is read there). Berlin, the thirteenth city, is one district whole,
# so /town/berlin is its own page and is not here: preflight holds this list
# to the towns the House map divides into wards.
WARDED_CITIES = ("Claremont", "Concord", "Dover", "Franklin", "Keene", "Laconia",
                 "Lebanon", "Manchester", "Nashua", "Portsmouth", "Rochester", "Somersworth")
MOVED =(("/learn", "/resources"), ("/learn.html", "/resources"),
         *((f"/learn/{s}{x}", f"/guides/{s}") for s in _civics.HOW_TO for x in ("", ".html")),
         # /guides holds the guides and was never a page: the hub opens on them.
         ("/guides", "/resources"), ("/guides.html", "/resources"),
         *((f"/town/{c.lower()}{x}", f"/officials?town={c}")
           for c in WARDED_CITIES for x in ("", ".html")),
         ("/legislators", "/officials"), ("/legislators.html", "/officials"),
         # Sen. John Barnes Jr.'s page, named from "Barnes, Jr., John" as
         # "Jr. Barnes John" until build_site_v2.person_name put the suffix
         # last (12 October 2026).
         ("/legislator/jr-barnes-john-sd-17", "/legislator/john-barnes-jr-sd-17"))
REDIRECTS = ("# Written by build_pages.py. Not an asset; Pages reads it.\n"
             + "".join(f"/bill/:year/:bill/{s} /bill/:year/:bill 200\n" for s in BILL_TAB_SLUGS)
             + "".join(f"/legislator/:who/{s} /legislator/:who 200\n" for s in MEMBER_TAB_SLUGS)
             + "".join(f"/committee/:code/{s} /committee/:code 200\n" for s in COMMITTEE_TAB_SLUGS)
             + "".join(f"{old} {new} 301\n" for old, new in MOVED))


# THE REPOSITORY, NAMED ONCE: chrome.REPO, which the footer links too.
REPO = chrome.REPO

# The directory link that used to sit in the footer has moved to the Data
# page: in a grey band it was one link among four and could not say what it
# was for, and on that page it gets a heading and the sentence that matters --
# every record as a plain link, no JavaScript, which is also what a crawler
# follows. The footer's own links are chrome.FOOTER's.


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
# FOUR MEETINGS NOW, NOT FIVE DOCKET LINES (the person, 24 October 2026;
# latest_activity.py), and THREE BILLS OF EACH, then "and N more", which
# leads to the meeting: a House sitting takes up a hundred bills and a
# committee's day twenty. Four, because that is what keeps the box the height
# it was: drawn from the data of 24 October 2026 in the 248px rail of a
# 1280px window, the five docket lines stood 1,258px tall, four meetings stand
# 1,317 and five 1,645, their interim study reports' words wrapping in the
# narrow column.
# AND EVERY BILL OF EACH, IN A CARD THAT OPENS (the owner, the same evening:
# "formatted similarly to the coming up page ... with the ability to click it
# for a dropdown to list all the bills from that session"). A card shut is two
# lines, so four meetings stand shorter than before; open, it lists every bill
# the meeting took up, up to RECENT_BILLS -- which latest_activity keeps in
# home.json for the meetings shown, and eight for the rest -- and "and N
# more" past that, which only a House sitting reaches.
RECENT_SHOWN = 4
RECENT_BILLS = 40
RECENT_MORE = ('<p class="actmore"><a class="morebtn" href="/bills?sort=recent">'
               'See all recent activity &rarr;</a></p>')


def recent_more(lang="en"):
    """RECENT_MORE in `lang`."""
    if lang == i18n.DEFAULT:
        return RECENT_MORE
    return ('<p class="actmore"><a class="morebtn" href="/bills?sort=recent">'
            + say(lang, "home.recent_more", "See all recent activity &rarr;") + '</a></p>')


def recent_href(r):
    """Where a Latest activity row's bill number leads: the bill's own page,
    under the year it is filed in. It led to the search list, bills.html#SB256
    (the survey of 7 October 2026), which opens on whichever SB 256 the list
    shows first. A row from before home.json carried the year keeps that
    address. HOME_JS draws the same."""
    year, bid = str(r.get("year") or ""), str(r.get("bill") or "")
    return f"bill/{year}/{bid.lower()}.html" if year and bid else f"bills.html#{bid}"

# THE KINDS OF MEETING: the schedule's word, lower case, to what a reader sees
# and the class that colours it. THE COLOURS ARE THE GENERAL COURT'S OWN,
# because staff already read its schedule by them: blue a hearing, green a
# work session, orange an executive session, red a committee of conference
# -- the legend fetch_schedule.py quotes; the floor has one of its own, a
# study or statutory committee its own raspberry (the person, 25 September
# 2026), and a kind not named keeps the neutral k-other. The table is words,
# written once since 9 October 2026 (the component plan's C3): it is
# src/pages/words/meeting_kinds.json, whose notes say the rest, and app.js draws
# a committee's calendar with the same file, from components.js. It was a
# table here and another in app.js, held alike by a check that read both.
MEET_KIND = {k: tuple(v) for k, v in WORDBOOK["meeting_kinds"]["kinds"].items()}

# THE CHIPS ARE NAMES TOO, in title case like the boxes above the schedule
# (the person, 25 September 2026: capitalise the chips to match). A kind the
# table does not know -- "cancelled", or a phrase the docket invents -- is
# set the same way, its small words left small: "Committee of Conference".
# The small words are meeting_kinds.json's, which app.js's kindTitle reads too.
_SMALL = frozenset(WORDBOOK["meeting_kinds"]["small"])


def kind_title(k):
    words = (k or "").split()
    return " ".join(w if (i and w.lower() in _SMALL) or not w[:1].isalpha()
                    else w[:1].upper() + w[1:] for i, w in enumerate(words)) or "Meeting"

# THE KEY, each colour once, in the order the Calendar's row of boxes has
# them -- which is the key, and the filter, above its schedule. Names, so in
# title case, as the person asked on 25 September 2026: "Public Hearing or
# Executive Session". "Work Session" also covers the chamber committees'
# other meetings, and "Study Committee" the statutory ones, whose chips
# say which they are. meeting_kinds.json's "legend".
MEET_LEGEND = tuple(tuple(kc) for kc in WORDBOOK["meeting_kinds"]["legend"])


# The record's own words on a page in another language are marked as
# English (i18n.py, the first kind).
EN_ATTR = ' lang="en"'


def kind_word(k, lang="en"):
    """(the words a chip says for the schedule's kind `k`, its colour's
    class): MEET_KIND's, in `lang` (i18n.say_word, keyed by the English, so
    words/meeting_kinds.json changing a word asks for its translation)."""
    word, kcls = MEET_KIND.get((k or "").strip().lower(), (kind_title(k), ""))
    return i18n.say_word(lang, "kind", word), kcls


def clock_span(a, b, lang="en"):
    """"10:00 AM–12:15 PM" -- a sitting from its first item to its last,
    which is how the General Court prints one -- or one time where the two
    are the same."""
    return clock(a, lang) if a == b else f"{clock(a, lang)}–{clock(b, lang)}"


# What a calendar card is keyed on; see meeting_key. A named tuple so the
# code reading one says which part it means: `key.chamber` is "H", "S" or ""
# (a study committee, a conference), and `key.bill` is empty except on a
# committee of conference, which is one bill's.
Meet = namedtuple("Meet", "date chamber name bill")
CHAMBER_WORD = {"H": "House", "S": "Senate"}
CONFERENCE = "Committee of conference"


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

    So the key is the day and the committee, and nothing else -- where "the
    committee" is a committee in full, which for most of them means its
    chamber as well as its name.

    THE CHAMBER, BECAUSE A NAME IS NOT A COMMITTEE. Both chambers have a
    Finance, a Judiciary, a Ways and Means, a Transportation, an Executive
    Departments and Administration and a Children and Family Law. Keyed on
    the name alone, the two sitting on one day became one card: 28 January
    2025's "Finance" held House Finance's work session on HB 519 in LOB
    210-211 and Senate Finance's hearings on SB 64, 113, 114 and 117 in SH
    103, under one name and one link -- and 50 cards on the calendar were
    two chambers' committees drawn as one. So a chamber's committee is keyed
    on (chamber, name), and the card names its chamber.

    A study or statutory committee has no chamber: the database copy's row
    carries none, and the docket's row for a bill that set one up carries
    the BILL's chamber, which must not split the one meeting into two.

    A COMMITTEE OF CONFERENCE IS ONE BILL'S, AND BOTH CHAMBERS'. House Rule
    50, as the House Calendar prints it each June: "The House and Senate
    Conferees on a bill shall meet jointly but vote separately while in
    conference", and the first-named conferee of the bill's own chamber sets
    the time and place. Each bill has its own conferees, its own notice on
    its own docket -- "Conference Committee Meeting: 06/16/2025 09:30 am LOB
    206-208" on HB 485, 02:00 pm on HB 273 -- and its own report. So a
    conference is keyed on the bill, with no chamber and whatever name the
    row carries: one card per bill's conference per day. The Senate docket's
    notice names no committee -- "Committee of Conference Meeting:
    06/16/2025, 12:00 pm, Room 100, SH" on SB 14 -- yet the row came to carry
    the bill's Senate committee, and keyed on that name SB 14's conference
    was drawn as a sitting of Senate Judiciary, linked to that committee's
    page, and a second time from its recording. Per day would be one card for every conference in
    the building, which is the mistake above made across a whole corridor:
    the docket noticed 33 for 26 May 2026, each at its own time, in nine
    rooms.
    """
    date = u.get("date") or ""
    what = (u.get("what") or u.get("kind") or "").strip().lower()
    if what == "committee of conference":
        return Meet(date, "", CONFERENCE, (u.get("bill") or "").strip().upper())
    name = u.get("committee") or ""
    if u.get("study") or what in ("study committee", "statutory committee"):
        return Meet(date, "", name, "")
    return Meet(date, (u.get("body") or "").strip().upper(), name, "")


def is_conference(key):
    return key.name == CONFERENCE


# The floor's cards, by the name build_calendar.FLOOR keys them on.
FLOOR_CARD = {"house floor": "House Session Day", "senate floor": "Senate Session Day"}


def card_name(key, lang="en"):
    """What a card calls its committee: "House Judiciary", "Senate Finance",
    "Committee of conference on HB 2", "Commission on Aging", "House Session
    Day".

    THE CHAMBER IS SAID, on every chamber's committee and not only on the
    names both chambers use: a card reading "Commerce" beside one reading
    "Senate Finance" would leave a reader to guess whose Commerce it is. It
    is how the General Court's own schedule titles them -- "House Ways and
    Means : GP, Room 234". The floor and the sittings whose committee the
    docket did not record already say it, and are not told twice.

    THE FLOOR IS A SESSION DAY (the person, 9 October 2026: "Session day
    should be Session Day"). Its card said "House floor", the key the week
    is grouped on, over a chip saying Floor Session; the approved Calendar
    calls it "House Session Day", and the key stays "House floor" for every
    lookup made on it (build_calendar.FLOOR, the floor's links below).
    """
    if is_conference(key):
        num = re.sub(r"^([A-Z]+)(\d)", r"\1 \2", key.bill)
        if lang != i18n.DEFAULT:
            return (say(lang, "cal.conference_on", "Committee of conference on {bill}", bill=num)
                    if num else say(lang, "cal.conference", "Committee of conference"))
        return f"{CONFERENCE} on {num}" if num else CONFERENCE
    if key.name.strip().lower() in FLOOR_CARD:
        if lang != i18n.DEFAULT:
            return (say(lang, "cal.house_day", "House Session Day")
                    if key.name.strip().lower() == "house floor"
                    else say(lang, "cal.senate_day", "Senate Session Day"))
        return FLOOR_CARD[key.name.strip().lower()]
    word = CHAMBER_WORD.get(key.chamber)
    first = (key.name.split() or [""])[0]
    if word and first not in CHAMBER_WORD.values():
        return f"{word} {key.name}"
    return key.name


def pick_name(key):
    """The committee as the Calendar page's picker lists it: the card's own
    name, except that every committee of conference is one entry. A reader
    who asks for the conferences wants them all, not a list of eighty bills."""
    return CONFERENCE if is_conference(key) else card_name(key)


def card_bodies(key, rows):
    """The chambers a card is filtered under. A committee of conference is
    both chambers' by rule, whichever of them called it; anything else is the
    chambers its rows record."""
    if is_conference(key):
        return ["H", "S"]
    return sorted({(r.get("body") or "").strip().upper()
                   for r in rows if (r.get("body") or "").strip()})


def committee_codes(site, data=None):
    """{(chamber, lower-cased name): code} out of site/committees.json, for
    a card's link to its committee's page.

    ON THE CHAMBER AS WELL AS THE NAME. Keyed on the name alone, the second
    of two committees of one name overwrote the first, so every House
    Finance, Judiciary, Ways and Means, Transportation, Executive
    Departments and Administration and Children and Family Law card linked
    to the Senate committee's page -- 168 cards, House Judiciary of 15
    January 2025 among them, sent to committee/S10.
    """
    # FROM THE STEP THAT KNOWS FIRST, WHERE `data` IS GIVEN (10 October
    # 2026): build_committees' own reading of today's committees, which no
    # later step writes, so a build into an empty site links its Coming Up
    # cards as a warm one does; last night's committees.json, where it is
    # here, fills in after it. The home page asks for it (main); the calendar,
    # which runs after build_committees, reads the file it wrote. Asked for
    # only where `data` is named, because the folder is the real data's: a
    # caller holding the map to a committees.json of its own (preflight's
    # _calendar_chambers) got every real committee as well, on GitHub's
    # machine and not on a clone without data.
    code = {}
    try:
        if data is None:
            raise LookupError("not asked for")
        import build_committees as BC
        code.update(BC.page_codes(site, data))
    except LookupError:
        pass
    except Exception as e:   # noqa: BLE001 -- the cards keep their words, unlinked
        print(f"  committee links: build_committees could not be read ({e}); "
              "falling back to site/committees.json")
    cf = Path(site) / "committees.json"
    if cf.exists():
        try:
            for c in json.loads(cf.read_text(encoding="utf-8")):
                if c.get("name") and c.get("code"):
                    code.setdefault(((c.get("chamber") or "").strip().upper(),
                                     c["name"].strip().lower()), c["code"])
        except (ValueError, OSError):
            pass
    return code


# THE FORTNIGHT'S MEETING COUNT IS OFF THE STATUS BOX, at the person's
# word on 19 September. It is not a fact about the state of the General
# Court, which is what the box is for; it is a fact about the calendar,
# which is on the same page saying it better -- by day, by committee and
# by bill. Three renderers wrote it and all three are gone with it: this
# one, HOME_JS's _meetline, and the clock block that counted the days off
# the total. meeting_key() stays: the calendar groups by it.

VACANCY_NOTE = ("Seats fall vacant during a term when members resign or die. "
                "A House seat is filled by special election only if the town "
                "or city asks the Governor and Executive Council to call one, "
                "so some stay vacant until the next general election. A "
                "Senate seat is filled as the state constitution provides.")


def party_word(name, lang="en", plural=False):
    """A party's name as the roster spells it ("Republican", "Democrat"), in
    `lang`, singular or plural; a name not here, as it came."""
    one = {"Republican": say(lang, "party.r", "Republican"),
           "Democrat": say(lang, "party.d", "Democrat"),
           "Democratic": say(lang, "party.dem", "Democratic"),
           "Independent": say(lang, "party.i", "Independent"),
           "Libertarian": say(lang, "party.l", "Libertarian"),
           "Party not on file": say(lang, "party.none", "Party not on file")}
    many = {"Republican": say(lang, "party.rs", "Republicans"),
            "Democrat": say(lang, "party.ds", "Democrats"),
            "Democratic": say(lang, "party.ds", "Democrats"),
            "Independent": say(lang, "party.is", "Independents"),
            "Libertarian": say(lang, "party.ls", "Libertarians")}
    return (many if plural else one).get(name, one.get(name, name) if plural else name)


def seat_columns(house, row, lang="en"):
    """The House by seat, one column per division, as markup; `house` the
    members in seat order and `row(m)` the row that draws one.

    ONE COLUMN PER DIVISION (the person, 7 October 2026, F8: "the House
    seating chart shows 3 columns for 5 sections"). The list under the chart
    was one run of seat numbers balanced into as many columns as fit, three at
    full width, so a column ended partway through a division. Now each of the
    chamber's five divisions is a column of its own, headed as the chart
    labels it and counted, five abreast where the width allows (app.css,
    .seatdivs). A seat number decodes as division * 1000 + seat (seating.py).
    The Speaker, whose seat is on the rostrum and in no division, is above
    them, and a member with no seat on file, which the roster has not had,
    after them. Every row is still a .seatrow inside #seatlist, where the seat
    map's script finds them.

    IN THE CHART'S ORDER, 1 TO 5 (the person, 7 October 2026: "rotated 180
    degrees so that the divisions can be listed in ascending order left to
    right since descending order is a bit confusing"). The chart above is the
    Clerk's plan turned half a circle, the rostrum at the top and Division 1
    on the left (seating.LEFT_TO_RIGHT), and the columns are taken from that
    order rather than written out again, so each stands under its own
    division and the two cannot come to disagree. It ran 5 to 1 while the
    chart was drawn as the plan is. The markup is in the chart's
    order, so the reading order, the keyboard's order and what the eye sees
    agree at every width: five abreast, or one division under the next where
    five do not fit.
    """
    divs = OrderedDict()
    for m in house:
        divs.setdefault(int(m["seat"]) // 1000 if m.get("seat") else 0, []).append(m)
    rostrum = divs.pop(seating.SPEAKER_SEAT // 1000, [])
    unseated = divs.pop(0, [])
    across = {d: i for i, d in enumerate(seating.LEFT_TO_RIGHT)}

    def block(heading, ms, cls="sdiv"):
        return (f'<section class="{cls}"><h3>{heading}</h3><ol class="seatlist">'
                + "".join(row(m) for m in ms) + "</ol></section>")
    return ((block(say(lang, "seat.rostrum", "The rostrum"), rostrum, "sdiv srost")
             if rostrum else "")
            + ('<div class="seatdivs">' + "".join(
                block(say(lang, "seat.division_n", "Division {d} &mdash; {n}", d=d, n=len(ms)), ms)
                for d, ms in sorted(divs.items(),
                                    key=lambda kv: (across.get(kv[0], len(across)), kv[0])))
               + "</div>" if divs else "")
            + (block(say(lang, "seat.none", "No seat on file"), unseated) if unseated else ""))


def home_week(week):
    """A week's days as the home page's Coming up holds them: without the
    special study and statutory committees.

    "Study committee meetings should not be in 'Coming up'" (the person, 7
    October 2026, F1), and later the same day which ones: a special committee
    set up by a bill to study something -- "Committee to Study Siting and
    Maintenance Rules Regarding Certain Intellectual and Developmental
    Disability (IDD) and Acquired Brain Disorder (ABD) Community Residences" --
    is left off, while a standing committee's interim study sessions stay,
    because those are the chamber's own committees at work on its own bills.
    meeting_who already draws that line for the Calendar page's filters, so
    the rail asks it rather than drawing a second one. They stay on the
    Calendar, where the Study Committee filter shows them.
    """
    from collections import OrderedDict
    return {d: OrderedDict((k, rs) for k, rs in day.items()
                           if meeting_who(k.name, rs) != "study")
            for d, day in (week or {}).items()}


def calendar_html(out, today=None, rows=None, lang="en", events=None):
    """What is left of this week, by day and then by meeting, and the key
    dates after it.

    `today` and `rows` are preflight's: it draws the rail for a fixed date out
    of rows it wrote, rather than out of the clock and proceedings.csv.
    `events` is key_dates.events()'s list, worked out for `today` where it is
    not given; [] draws the rail with none.

    THE KEY DATES (the owner, 24 October 2026: "Coming up should list major
    events like the election days, town meeting days, organization day,
    etc"), NOW CALLED IMPORTANT DATES, AND ONLY THE WEEK'S (the owner, the
    same evening: "those events would show up under the coming up section
    when they are within that week's days, but not ones that are months
    out ... The key dates should display within the other coming up
    sessions in the same format, just color coded with the same scheme used
    on the calendar page"). Those of the rail's week stand first in their
    days, each the card the Calendar draws for it (key_dates.card_html), in
    its gold, opening on its sentence and source; a day holding only one is
    one of the rail's days. None after the week: the list of the next four
    that followed it, out to December on 24 October, is gone, and a date
    comes into the rail with its week, as a meeting does.
    """
    import key_dates as KD
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
    today = today or build_date.today()
    weeks = BC.weeks_from(proceedings.load() if rows is None else rows)
    # FROM SATURDAY, NEXT WEEK (D13, the person, 8 October 2026: "Coming up
    # shows the current week's upcoming meetings; from Saturday it switches
    # to the next week's, clearly labelled as next week (never read as the
    # week just past)"). A weekend has no committee meetings, so on Saturday
    # and Sunday the rail is the coming Monday's week, whole, and says so.
    ahead = today.weekday() >= 5
    start = BC.monday(today) + _dt.timedelta(days=7) if ahead else today
    monday = BC.monday(start)
    sunday = monday + _dt.timedelta(days=6)
    week = home_week(weeks.get(BC.week_key(start)))
    evs = KD.events(today) if events is None else events
    kds = KD.days(evs, start, sunday)
    dates = sorted(d for d in set(week) | set(kds)
                   if start.isoformat() <= d <= sunday.isoformat()
                   and (week.get(d) or kds.get(d)))
    nxt = BC.week_key(sunday + _dt.timedelta(days=1))
    n_next = sum(len(v) for v in home_week(weeks.get(nxt)).values())
    # The week's name and its weekdays, as the Calendar's pager says them
    # ("This Week", "Next Week": the person, 9 October 2026, item 17).
    label = ('<p class="calwk">' + chip(say(lang, "cal.next_week", "Next Week") if ahead
                                        else say(lang, "cal.this_week", "This Week"))
             + f' <span>{esc(date_span(monday, monday + _dt.timedelta(days=4), "medium", lang))}'
             + "</span></p>")
    coming = say(lang, "cal.coming", "Coming up")

    # WHERE THE REST IS: next week's own page, which build_calendar writes
    # for every week in its range, empty ones included -- linked here only
    # when next week has a sitting, and otherwise the link is the Calendar
    # tab. HOME_JS keeps this line when it empties the rail in the reader's
    # clock. The link says "Next Week ›", the Calendar pager's own words for
    # the same page (the person, 9 October 2026: "The week after should be
    # Next Week"); it said "See next week".
    # THE RAIL ENDS WITH THE CALENDAR (D13, item 118: "Coming up ends with a
    # plain 'See the full calendar' link instead of the count of next week's
    # meetings"). It said how many meetings next week held and linked that
    # week's page; from Saturday next week is the rail itself.
    more = ('<p class="calmore calall"><a href="calendar.html">'
            + say(lang, "cal.full", "See the full calendar") + '</a></p>')

    if not dates:
        # THE REST OF THE WEEK IS EMPTY every weekend in session and every
        # day out of it. Out of session -- next week empty too -- it says when
        # business resumes rather than just "nothing", because the General
        # Court is a part-time legislature and this is what the page says for
        # half the year.
        # WHAT IS NOT SCHEDULED, NOT "NOTHING" (the audit of 25 October 2026,
        # M8). The rail leaves the special study committees to the Calendar
        # (home_week), and "Nothing is scheduled next week yet" stood over a
        # week of 26 October 2026 for which the Calendar held seventeen of
        # theirs. It says what the rail holds and does not: the chambers' own
        # meetings.
        # ITS FIRST SENTENCE IS AN ELEMENT OF ITS OWN (the preview check of 25
        # October 2026), .calnomeet, because it names the same week as the
        # chip above it and HOME_JS says both again in the reader's clock. A
        # rail built on a Sunday read on the Monday had "This Week" over
        # "... scheduled next week.": the script renamed the chip and could
        # not reach the sentence, which was one string with the season's.
        note = (say(lang, "cal.none_next", "No House or Senate committee meetings are "
                    "scheduled next week.") if ahead
                else say(lang, "cal.none_left", "No House or Senate committee meetings are "
                         "scheduled for the rest of this week."))
        note = f'<span class="calnomeet">{esc(note)}</span>'
        if not n_next:
            # MOSTLY (the survey of 7 October 2026): both chambers sat until veto
            # day, 19 August, in 2026, and into the autumn in most years.
            note += " " + esc(say(lang, "cal.season", "The General Court sits mostly from "
                                  "January to June, and committees meet on bills from the fall "
                                  "filing period onwards."))
        return (f'<section class="cal" data-mon="{monday.isoformat()}"><h2>{coming}</h2>'
                f'{label}<p class="note">{note}</p>{more}</section>')

    meets = {k: rs for d in dates for k, rs in (week.get(d) or {}).items()}
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

    # --- a chamber's committee -> its own page -----------------------------
    code = committee_codes(out, data="data")

    def when(d):
        """Tue, Sep 15, and how far off it is -- the part a reader acts on."""
        try:
            dd = _dt.date.fromisoformat(d)
        except ValueError:
            return d, ""
        off = (dd - today).days
        rel = (say(lang, "cal.today", "today") if off == 0
               else say(lang, "cal.tomorrow", "tomorrow") if off == 1
               else say(lang, "cal.in_days", "in {n} days", n=off) if 0 < off <= 14 else "")
        return _shell.date_words(dd, "wkd", lang), rel

    # A day's committees in the order they start, by the week page's own
    # ordering, so the two list them the same way round.
    days = OrderedDict((d, BC.in_order(week.get(d) or {})) for d in dates)

    # A WEEK IN THE RAIL, NOT A FORTNIGHT: in session a fortnight is fourteen
    # days of committee cards down a 300px column, and it was asked on 19
    # September to be "a bit more consolidated ... so it isn't as long". A
    # week is the Calendar tab's own unit, and the rail is now that week.
    html = [f'<section class="cal" data-mon="{monday.isoformat()}"><h2>{coming}</h2>{label}']
    body, missing = cal_days(days, meets, titles, years, code, when, esc, lang=lang,
                             events=kds, kd_full=False)
    # THE WHOLE WEEK, IN A BOX OF ITS OWN HEIGHT. A week in session is forty
    # sittings -- the week of 26 January 2026 held 43 -- and drawn in full it
    # ran the left rail to about four times the height of the middle column. It
    # was asked on 24 September to keep the week and cap the length, with a
    # way to scroll through the rest, so every card is still here and the
    # stylesheet gives the box its height (app.css, .calscroll). Nothing is
    # dropped, so the Calendar tab and this rail still hold the same sittings.
    #
    # A BOX THAT SCROLLS IS A STOP ON THE KEYBOARD. Tab lands on it and the
    # arrow keys and Page Down move it, which is the only way to scroll it
    # without a pointer. Focusable and nameless, it would be announced as
    # nothing, so it is a region and its name says what it holds.
    html.append('<div class="calscroll" role="region" tabindex="0" '
                f'aria-label="{esc(say(lang, "cal.scroll", "Meetings from today to Sunday"))}">'
                + body + "</div>")
    html.append(more)
    return "".join(html) + cal_notes(up, missing, esc)


# ONE CHIP FOR A PERSON is components.py's pchip, imported above: the
# legislators page builds two of its three rosters here, in Python, because
# they are the only listing a crawler and a reader without JavaScript can
# walk, and components.js's pchip draws the same chip wherever a page is
# drawn in the browser.
#
# THE PARTY PILL HAS ITS OWN PREFIX NOW: pt-R, not p-R.
#
# `.p-R` was three components in this codebase -- the left edge of a member
# chip, the fill of a seat on the floor chart, and this small tinted pill --
# and app.css already recorded that as the third time one class name had meant
# two things here, with the standing instruction that a new component gets its
# own prefix.
#
# It was not academic. style.css, as it was then, put the page region after
# the shared one, and both `.mchip{background:var(--surface)}` and
# `:where(body.pg) .p-R{background:var(--rep-soft)}` carried a single class, so
# the pill's tint won wherever a member chip appeared on a page built here: the
# roster's chips arrived tinted and unpadded. That was patched by specificity
# first; this is the real fix.


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


def meeting_who(cmte, rows):
    """Who is meeting: "floor", "study" or "standing".

    For the Calendar page's filters, which ask who and what separately. The
    floor is the House or the Senate sitting as a whole. A study or statutory
    committee is one the database copy says is one, or one the docket files
    as a "study committee" sitting -- HB 1763's committee on 2 September 2026
    reached the calendar through the docket alone. Everything else is a
    chamber's own committee: the standing committees, a committee of
    conference drawn from them, and the sittings whose committee the docket
    did not record.
    """
    if (cmte or "").strip().lower() in ("house floor", "senate floor"):
        return "floor"
    if any(r.get("study") or (r.get("what") or "").strip().lower()
           in ("study committee", "statutory committee") for r in rows):
        return "study"
    return "standing"


def cal_days(days, meets, titles, years, code, when, esc, level=3,
             sessions=None, docs=None, lang="en", events=None, kd_full=True):
    """The day blocks and their meeting cards, for any set of days.

    Split out of calendar_html on 18 September so the calendar PAGE draws the
    same cards from the same grouping. meeting_key already exists because two
    places counted meetings and disagreed; a second renderer drawing something
    that merely looked like these would be the same mistake in markup.

    THE KEY DATES OF A DAY COME FIRST (the owner, 24 October 2026: "Coming
    up should list major events like the election days, town meeting days,
    organization day, etc and those dates should show up on the calendar
    page too"). `events` is key_dates.days(): {day: [(key date, role)]}.
    Each is a card of its own class, which opens on its sentence and source,
    on the Calendar and in Coming up alike (the owner, 24 October 2026: "in
    the same format, just color coded"); it was a plain line in Coming up
    until that evening. Neither is a meeting: a day holding only a key date
    still says it has no meetings on the Calendar (`kd_full`), and is not a
    calnone day.
    """
    import key_dates as KD
    events = events or {}
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
        kds = events.get(date) or []
        html.append(f'<div class="calday{"" if keys or kds else " calnone"}" '
                    f'data-d="{esc(date)}"><{h} class="caldate">'
                    f'<span>{esc(label)}</span>'
                    f'<span class="cdrel">{esc(rel)}</span>'
                    + f"</{h}>")
        html += [KD.card_html(e, role, date, lang) for e, role in kds]
        if not keys:
            if kd_full or not kds:
                html.append(f'<p class="calempty">{say(lang, "cal.empty", "No meetings scheduled.")}</p>')
            html.append("</div>")
            continue
        for key in keys:
            # THE NAME THE CARD PRINTS, with its chamber: two committees of
            # one name on one day are two cards now, and each has to say
            # which it is. The key's own name is the committee's, for the
            # links and the questions asked about it below.
            _d, cmte = key.date, card_name(key)
            # In another language the card's name is the page's words for a
            # session day or a conference, and the committee's own name
            # otherwise, which is the record's and stays English.
            shown = card_name(key, lang)
            own_name = lang != i18n.DEFAULT and shown == cmte
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
            # meeting whose bills all share one slot states it once. In the
            # twelve-hour clock a reader uses (clock); the record's own
            # "10:00" stays in data-time and data-last below.
            slots = sorted(x for x in (r.get("time") or "" for r in rows) if x)
            time = clock_span(slots[0], slots[-1], lang) if slots else ""
            # BILLS, NOT ROWS. A study or statutory committee's meeting is a
            # row with no bill, and counting rows called it "(1 bill)".
            # AND EACH BILL ONCE. A bill heard and then voted on the same day
            # is two items on the card and one bill: House Housing on 21
            # January 2025 heard eight bills and voted on five of them after,
            # and its card said "(13 bills)" over the eight it lists. 250 of
            # the 1,883 cards since January 2025 stated more bills than they
            # held, House Commerce's of 18 February 2026 "(53 bills)" over 37.
            # The items stay two, each in its own slot; the count is of the
            # bills.
            n = len({(r.get("bill") or "").strip().upper() for r in rows
                     if (r.get("bill") or "").strip()})
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
            bodies = card_bodies(key, rows)
            bills_attr = " ".join(sorted({(r.get("bill") or "").strip().upper()
                                          for r in rows if r.get("bill")}))
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
            html.append('<details class="calmeet"'
                        f' data-body="{esc(" ".join(bodies))}"'
                        f' data-cmte="{esc(cmte.lower())}"'
                        # THE PICKER'S NAME, where it is not the card's own:
                        # the committees of conference are one entry there.
                        + (f' data-pick="{esc(pick_name(key))}"'
                           if pick_name(key) != cmte else "")
                        + f' data-bills="{esc(bills_attr)}"'
                        f' data-date="{esc(_d)}"'
                        + (f' data-time="{esc(slots[0])}"' if slots else "")
                        + (f' data-last="{esc(slots[-1])}"' if slots else "")
                        + (f' data-venue="{esc(PA.place(venue))}"' if venue else "")
                        + (' data-study=""' if study else "")
                        + (' data-cancelled=""' if cancelled else "")
                        # WHO AND WHAT, for the Calendar page's filters: whose
                        # sitting it is, and the kinds its bar is drawn in
                        # (hearing, meet, exec, conf, floor, other). The same
                        # colours as the bar, because they are the bar.
                        + f' data-who="{esc(meeting_who(key.name, rows))}"'
                        + f' data-kinds="{esc(" ".join(b[2:] for b in bars))}"'
                        + "><summary>")
            html.append('<span class="calmix" aria-hidden="true">'
                        + "".join(f'<i class="{c}"></i>' for c in bars) + "</span>")
            # THE COMMITTEE FIRST. It is what a reader scans a rail for, and
            # putting the time ahead of it meant the rail's card spent its
            # first line on four digits. The time follows, beside the bill
            # count, so the two read as one phrase about that sitting:
            # "Ways and Means / 09:30-10:30 (11 bills)".
            html.append(f'<span class="calcmte"{EN_ATTR if own_name else ""}>{esc(shown)}</span>')
            if time:
                html.append(f'<span class="caltime">{esc(time)}</span>')
            # THE COUNT DIRECTLY AFTER THE TIME, not after the kind. The
            # parentheses only work while the two are adjacent -- with the
            # kind chip between them the rail read "09:30-11:30 Subcommittee
            # work session (5 bills)", a bracket around nothing in
            # particular. On its own where there is no time, for the same
            # reason.
            _bills = (say(lang, "cal.one_bill", "1 bill") if n == 1
                      else say(lang, "cal.n_bills", "{n} bills", n=n))
            if n:
                html.append(f'<span class="calcount">'
                            + (f"({_bills})" if time else _bills) + "</span>")
            # A SESSION DAY'S NAME SAYS WHAT IT IS ("House Session Day"), so
            # no chip says "Session Day" again under it, as the approved
            # Calendar has it (9 October 2026); its bar keeps the colour.
            for k in ([] if key.name.strip().lower() in FLOOR_CARD else kinds):
                word, kcls = kind_word(k, lang)
                html.append(chip(word, f"calkind {kcls}"))
            # THE ROOM IN WORDS (the audit of 25 October 2026, S7): "Granite
            # Place 231" for the clerk's "GP 231", as app.js's calendarBlock
            # says it (roomWords) and a bill's Hearings tab always has.
            if venue:
                html.append(f'<span class="calwhere">{esc(PA.place(venue))}</span>')
            html.append('<span class="caret"></span></summary>'
                        '<div class="calbody">')
            one = len(slotted) == 1
            for (tm, wk, vn), items in slotted.items():
                word, kcls = kind_word(wk, lang)
                if not one:
                    html.append('<p class="calslot">'
                                + (f'<span class="caltime">{esc(clock(tm, lang))}</span>' if tm else "")
                                + chip(word, f"calkind {kcls}")
                                + (f'<span class="calwhere">{esc(PA.place(vn))}</span>'
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
                    html.append(f'<p class="calnote"{EN_ATTR if lang != i18n.DEFAULT else ""}>'
                                f'{esc(note)}</p>')
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
                                + (f'<span class="cbt"{EN_ATTR if lang != i18n.DEFAULT else ""}>'
                                   f'{esc(ti)}</span>' if ti else "")
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
                     "senate floor": "S"}.get(key.name.strip().lower())
            if floor and sessions is not None and (floor, _d) not in sessions:
                floor = None
            elif floor and sessions is None:
                floor = None
            # THE OFFICIAL DOCUMENT, where the caller has one: the calendar
            # that printed the notice, or the journal of a floor sitting.
            # Addresses the record holds, passed in; never built here.
            # In a new tab and marked as going out, as every calendar and
            # journal on the Calendar opens (F12, 7 October 2026).
            got = (docs or {}).get(key) or []
            if got:
                html.append('<p class="calmore caldocs">'
                            + "".join(f'<a class="out" href="{esc(u)}" '
                                      'target="_blank" rel="noopener">'
                                      f'{esc(w)} (PDF)</a>' for w, u in got)
                            + "</p>")
            # A STUDY OR STATUTORY COMMITTEE'S RECORDING, where one is named
            # for the meeting (build_calendar.study_recordings). Its card has
            # no page to lead to, so it leads to the recording itself; a bill's
            # sitting leads to the bill, whose page holds its recording at the
            # moment the bill was taken up.
            rec = next((r.get("video_id") for r in rows
                        if r.get("study") and r.get("video_id")), "")
            if study and rec:
                html.append('<p class="calmore"><a class="out" href="https://www.youtube.com/'
                            f'watch?v={esc(rec)}" target="_blank" rel="noopener">'
                            + say(lang, "cal.recording", "The recording, on YouTube") + "</a></p>")
            # A study committee that shares a name with a standing one is not
            # that committee, so its card does not borrow the page; and a
            # chamber's committee takes its OWN chamber's page, which the
            # name alone does not say.
            cc = None if study else code.get((key.chamber, key.name.strip().lower()))
            # A STUDY OR STATUTORY COMMITTEE HAS A PAGE OF ITS OWN (18 October
            # 2026) where the General Court lists it as active: the row names
            # it (build_calendar.study_page), and the card leads into the
            # meeting there, as a standing committee's card leads into its day.
            own = next((r.get("page") for r in rows
                        if r.get("study") and r.get("page")), "") if study else ""
            if floor:
                did = (f'What the {esc(key.name[:-6].strip())} did that day'
                       if lang == i18n.DEFAULT
                       else say(lang, "cal.house_did", "What the House did that day")
                       if floor == "H" else say(lang, "cal.senate_did", "What the Senate did that day"))
                html.append('<p class="calmore">'
                            f'<a href="session/{floor}/{esc(_d)}.html">{did}</a></p>')
            elif cc:
                html.append('<p class="calmore">'
                            f'<a href="committee/{esc(cc)}.html#day-{esc(_d)}">'
                            + say(lang, "cal.on_page", "This meeting on the {name} page",
                                  name=esc(cmte)) + '</a></p>')
            elif own:
                html.append('<p class="calmore">'
                            f'<a href="{esc(own)}#day-{esc(_d)}">'
                            + say(lang, "cal.on_page", "This meeting on the {name} page",
                                  name=esc(cmte)) + '</a></p>')
            html.append("</div></details>")
        html.append("</div>")
    return "".join(html), missing


HEARING_NOTE = ("Anyone may attend a public hearing and ask to speak. You can "
                "also sign in online to register a position and submit "
                "written testimony.")
# A SENATE HEARING'S NOTE (23 October 2026). The person's words above are the
# House's form, which takes written testimony with a sign-in. The Senate's
# takes a position and no testimony, and the page that confirms the sign-in
# says how to send it (the Senate's Public Guidance for Committee Meetings,
# which guides.TESTIMONY cites). So a Senate hearing's note says that, in the
# words the bill page's Testify box and the emails use for the same form
# (app.js testifyBox, mail.js testifyWords, 22 October 2026).
HEARING_NOTE_SENATE = ("Anyone may attend a public hearing and ask to speak. You can "
                       "also sign in online to register a position. The page that "
                       "confirms your sign-in says how to send written testimony.")


def hearing_note(body):
    """What a reader may do at a hearing of the chamber `body` ("H", "S"):
    the Senate's note for the Senate, and the person's words otherwise."""
    return HEARING_NOTE_SENATE if str(body or "").strip().upper() == "S" else HEARING_NOTE


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
    # THE FIRST TWO SENTENCES ARE THE PERSON'S, word for word (7 October
    # 2026, F2): speaking at a hearing is asked for rather than assumed, and
    # the online sign-in both registers a position and takes written
    # testimony. HEARING_NOTE is the one copy; app.js's calendarBlock prints
    # the same words, and preflight holds the two to them.
    # The executive session's sentence is off the home page (the person,
    # 10 October 2026); a committee's Upcoming sessions keep it (app.js).
    # OFF THE HOME PAGE (the person, 22 October 2026: "Remove this section
    # below the homepage calendar card"). A committee's Upcoming sessions
    # keep the words (app.js calendarBlock), and the hearings feed too.
    html.append("</section>")
    if missing:
        print(f"  calendar: {missing} of {len(up)} upcoming bills had no title "
              f"in site/idx (the number and the link are still printed)")
    return "".join(html)


# THE SECTIONS, in the header's order: chrome.NAV_TABS, which draws them.
NAV_TABS = chrome.NAV_TABS


def shell(title, current, body, wide=False, script="", desc="",
          base="https://graniterecord.org", lang="en", scripts=()):
    """A page of the five this file writes -- the home page, Officials, About,
    /search and 404 -- in the frame every page shares (chrome.py): the head's
    shared lines, the header with `current` marked as the section a reader is
    on, the footer and the closing scripts, around `body`. shell.page() puts
    the record pages in the same frame, from bills.html's CHROME slots.

    IN ANOTHER LANGUAGE (i18n.py): `lang` is the page's, and `current` is
    still the English page it is a version of ("index.html"). The page is
    written at i18n.href's address, one folder down (/es/), so it carries
    <base href="/"> as every record page does: the links it and its scripts
    write from the root lead there, and its skip link is written whole. Each
    version names the others on <html> (data-alt-<code>), which chrome's
    language script reads. While a language is not offered to everyone, its
    page asks not to be indexed and neither version names the other to a
    search engine (hreflang). `scripts` is the text of any script the page
    carries beside `script`, whose tr() words its head must carry."""
    # THE PAGES A SEARCH ENGINE REACHES FIRST HAD THE LEAST IN THEIR HEAD.
    # Every one of the 33,683 bill pages carries a description, a canonical
    # address and an unfurl card because shell.py writes them. The home page,
    # the search page, the legislator index and About did not, because they
    # are written here and this function never had them -- and those four are
    # where a person arrives.
    _e = lambda s: _html.escape(str(s or ""), quote=True)
    # The host serves /legislators, not /legislators.html, and redirects
    # the second to the first. shell.canon is where that is written down.
    here = i18n.href(lang, current) if current else "/"
    _canon = (base + _shell.canon(here)) if current else (base + "/")
    # This page's versions, {code: address}, itself among them.
    versions = {c: _shell.canon(i18n.href(c, current)) for c in i18n.LANGS
                if current and i18n.has(c, current)}
    others = {c: h for c, h in versions.items() if c != lang}
    alt_attrs = "".join(f' data-alt-{c}="{_e(h)}"' for c, h in others.items())
    listed = len(versions) > 1 and all(i18n.offered(c) for c in versions)
    seo_alt = ("".join(f'<link rel="alternate" hreflang="{c}" href="{base}{h}">'
                       for c, h in versions.items())
               + f'<link rel="alternate" hreflang="x-default" href="{base}{versions[i18n.DEFAULT]}">'
               ) if listed else ""
    robots = ('<meta name="robots" content="noindex">'
              if lang != i18n.DEFAULT and not i18n.offered(lang) else "")
    HEAD_SEO = (f'<meta name="description" content="{_e(desc)}">'
                f'<link rel="canonical" href="{_canon}">'
                f'<meta property="og:type" content="website">'
                f'<meta property="og:title" content="{_e(title)}">'
                f'<meta property="og:description" content="{_e(desc)}">'
                f'<meta property="og:url" content="{_canon}">'
                f'<meta property="og:site_name" content="Granite Record">'
                + (f'<meta property="og:locale" content="{i18n.LOCALE[lang].replace("-", "_")}">'
                   if lang != i18n.DEFAULT else "")
                + f'<meta name="twitter:card" content="summary_large_image">') if desc else ""
    HEAD_SEO += seo_alt + robots
    # One folder down, the root is reached as a record page reaches it.
    base_tag = '\n<base href="/">' if lang != i18n.DEFAULT else ""
    skip = (_shell.canon(here) if lang != i18n.DEFAULT else "") + "#main"
    # The home page has no tab, so the brand carries its "you are here"
    # (chrome.nav's home).
    # Every link at the address the host serves (shell.clean_links).
    return _shell.clean_links(f"""<!DOCTYPE html><html lang="{lang}"{alt_attrs}><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">{base_tag}
<title>{title}</title>{HEAD_SEO}
{chrome.head(current, lang, (script, *scripts))}
<!-- body.pg is what the rules for these pages alone are scoped to in app.css
     (:where(body.pg)): every page loads the one stylesheet. -->
<link rel="alternate" type="application/rss+xml" title="Granite Record — all activity"
 href="/feed/all.xml">
<link rel="alternate" type="application/rss+xml" title="Granite Record — upcoming hearings"
 href="/feed/hearings.xml"></head><body class="pg">
<a class="skip" href="{skip}">{say(lang, "page.skip", "Skip to the content")}</a>
{chrome.nav(current, home=current == "index.html", lang=lang)}
<main class="wrap{' wide' if wide else ''}" id="main">{body}</main>
{chrome.footer(lang, others)}
{chrome.scripts(lang)}
{script}</body></html>""")


NOT_FOUND = """
<p class="note">NO PAGE AT THIS ADDRESS</p>
<h1>Nothing is published here</h1>
<p class="lead">The address may be mistyped, or name a bill in a year it does
not exist in: every bill since 1989 has a page of its own, for example
<code>/bill/2026/hb1</code>, and a bill number starts again every two years.</p>
<p id="nf-bill" hidden></p>
<p><a href="bills.html">Search every bill</a> &middot;
<a href="officials.html">Officials</a> &middot;
<a href="committees.html">Committees</a> &middot; <a href="index.html">Home</a></p>
<script>
(function(){
  // A LAW OR A BILL ASKED FOR IN CAPITALS, OR A STATUTE BY ITS CITATION
  // (the polish of 12 October 2026): /laws/91-A is chapter 91-A's page and
  // /laws/91-A:4 its section 4. Every such page's address is lower case, so
  // the lower-case form is tried once; an address already in it is left
  // here, which is what keeps this from going round.
  // RSA 404's page is a folder's, at its address with a slash: FOLDERS is
  // build_rsa.FOLDER_CHAPTERS, which preflight holds this to (16 October 2026).
  var FOLDERS=["404"];
  var lp=location.pathname,c=lp.match(/^\\/laws\\/(\\d{1,3}(?:-[a-z]{1,2})?)(?::([0-9a-z.\\-]+))?\\/?$/i);
  if(c&&(c[2]||c[1]!==c[1].toLowerCase())){var s=c[1].toLowerCase();
    location.replace("/laws/"+s+(FOLDERS.indexOf(s)>=0?"/":"")+(c[2]?"#s"+c[2].toLowerCase():location.hash));return;}
  if(/^\\/(bill|laws)\\//.test(lp)&&lp!==lp.toLowerCase()){location.replace(lp.toLowerCase()+location.search+location.hash);return;}
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

# THE ABOUT PAGE AS THE PERSON APPROVED IT, word for word (9 October 2026;
# private/design/ABOUT_FINAL_2026-10-09.md). Its headings are in Title Case,
# and [[bills]] and [[since]] are counted from the bill index at build time
# (about_figures), never typed. Three sections that were here moved word for
# word to the Data page (build_exports.py): "What is taken from the record and
# what is generated" and "How much of this is timed, and how well" under "How
# the Record Is Built", and "What this site knows about you" under "Privacy in
# Detail"; the two links below lead to them. The paragraphs that were "Where
# the information comes from" are unchanged, in the closed "Sources in
# detail" fold under the section that now carries that name. "The Logo" and
# the artist's words are as they were. The repository's address is REPO's,
# put in below, so the footer, the Data page and this page cannot point at two
# places. Each line of What You Can Do Here links the page that does it (the
# audit of 25 October 2026, S6), its words unchanged.
ABOUT = """
<h1>About Granite Record</h1>
<p class="lead">Granite Record is a free, independent and searchable record of the New Hampshire
General Court: what each bill does, who sponsored it, when it was heard, how it
was voted on, and where in the recording it was discussed. It covers [[bills]]
bills since [[since]], for anyone who follows the legislature, from a first-time
testifier to the people who work in the State House.</p>

<h2 id="who">Who Makes Granite Record</h2>
<p>I'm Alice Wade, a State Representative from Dover, and Granite Record is my
independent project to make state government more accessible to everyone. It
started with one problem: bill hearings had no timestamps, so finding a single
bill meant combing through hours of livestream footage. From there I kept
gathering everything I needed to track legislation into one place, and Granite
Record grew out of that.</p>
<p>I'm committed to keeping it free, neutral and open source, for anyone who has
trouble keeping up with the state legislature. Built from the New Hampshire
General Court's own digital records, it covers bills back to [[since]]. You can
search for bills in plain language, prepare public testimony, research how
legislation has changed over time, and get in touch with your state legislators.</p>
<p>The eventual goal is a hub of information about New Hampshire's state, county and
municipal government, including guides to how state government is structured,
with interactive diagrams written to be accessible no matter your prior
experience with state government.</p>
<p>Nothing on this site is editorialized: it presents the official record in a more
searchable form. The code is public, and you can download the official record as
spreadsheets from the <a href="data.html">Data page</a>.</p>
<p>Granite Record is independent of my role as a state legislator and is not
affiliated with the New Hampshire General Court. For feature suggestions or
corrections to a bill's record, use the <i>Report a problem</i> button on a bill's,
legislator's or committee's page, or write to <a href="mailto:contact@graniterecord.org">contact@graniterecord.org</a>.</p>
<p>Special thanks to the House Clerk's Office and the General Court's IT staff,
without whom this project would not be possible.</p>

<h2>What You Can Do Here</h2>
<ul>
<li><a href="bills.html">Search for bills</a> in plain language, or by number, sponsor or committee.</li>
<li><a href="guides/using-this-site#s-what-a-timestamp-claims">Open a hearing's recording</a> at the moment a bill was taken up.</li>
<li><a href="guides/testifying">Prepare to testify</a>, with a bill's hearings, reports and text in one place.</li>
<li><a href="bills.html?term=all">Research how a bill, or an issue, has changed</a> over the years.</li>
<li>__FOLLOW_BULLET__</li>
</ul>

<h2>Where the Information Comes From</h2>
<p>Everything here comes from the General Court's own records: its docket, roll
calls, committee reports, journals and calendars, and the recordings on its
YouTube channels. Each bill links to its official record. Most hearing timestamps
are the moment the chair opened the item, checked against recordings a person
timed by hand; the rest are marked <i>approximate</i>.
<a href="data.html#how-built">How the record is built</a>, on the
Data page, explains the methods and how well they measure up.</p>
<details class="fold">
<summary>Sources in detail</summary>
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
</details>

<h2>Keeping It Accurate</h2>
<p>The official record at <a href="https://gc.nh.gov/" rel="noopener">gc.nh.gov</a> always takes precedence over anything shown
here. If something on a bill's, legislator's or committee's page doesn't match it,
use the <i>Report a problem</i> button on that page: reports are read every day, checked against the official record,
and corrected.</p>

<h2>Your Privacy</h2>
__PRIVACY__

<h2>Free and Open Source</h2>
<p>Granite Record is free to use, now and always. Its code is public on
<a href="__REPO__" rel="noopener">GitHub</a>
under the MIT License, and the whole record can be downloaded as spreadsheets
from the <a href="data.html">Data page</a>.</p>

<h2>Independence</h2>
<p>Granite Record is not affiliated with or endorsed by the New Hampshire General
Court, and it takes no position on any bill.</p>

<h2>The Logo</h2>
__LOGO__<p>The Granite Record logo was drawn by Debra Caplan, an artist in Peterborough,
New Hampshire, and is used under license from her. More of her work is at
<a href="https://www.linescapesnh.com/" rel="noopener">linescapesnh.com</a>.
In her own words:</p>
<blockquote class="artist">
<p>I moved to Peterborough, NH in 2011, and fell in love with the town; its rich
past, historic buildings and vibrant art community.</p>
<p>My idea for LineScapes prints sprang from my early school research into Louis
Prang, the father of lithography and a promoter of affordable art for all,
through lithographic prints.</p>
<p>I began making prints of my pen and ink sketches of Peterborough buildings,
hand-coloring some, and matting or framing them. &hellip; Over the years I have
added scenes from the Monadnock Region, New Hampshire and beyond.</p>
</blockquote>
""".replace("__REPO__", REPO)

# WHAT ABOUT SAYS OF FOLLOWING, BEFORE AND AFTER EMAIL GOES LIVE (the
# person's wording, 11 October 2026: "Approved the language for the privacy
# info"). shell.follow_live() decides which; the first of each pair is the
# text of 9 October, unchanged.
ABOUT_FOLLOW = {
    False: ('<a href="guides/using-this-site#s-following-a-bill">Follow a bill\'s progress</a>, '
            'and <a href="officials.html">find your legislators and how to reach them</a>.',
            """<p>Granite Record doesn't track you. There are no accounts and no advertising,
nothing about what you read is tied to you, and reports sent through the
<i>Report a problem</i> button are deleted after a week.
<a href="data.html#privacy">Privacy in detail</a> is on the Data page.</p>"""),
    True: ('<a href="guides/using-this-site#s-following-a-bill">Follow a bill, legislator, '
           'committee or topic</a> by feed or by email, and <a href="officials.html">find '
           'your legislators and how to reach them</a>.',
           """<p>Granite Record doesn't track you. There are no accounts and no advertising,
and nothing about what you read is tied to you. If you sign up for email updates,
your address is used only to send them. It is stored encrypted, never shared or
sold, and deleted at once when you unsubscribe. Reports sent through the
<i>Report a problem</i> button are deleted after a week.
<a href="data.html#privacy">Privacy in detail</a> is on the Data page.</p>"""),
}


def about_text(live=None):
    bullet, privacy = ABOUT_FOLLOW[_shell.follow_live() if live is None else bool(live)]
    return ABOUT.replace("__FOLLOW_BULLET__", bullet).replace("__PRIVACY__", privacy)

def about_logo(has_lockup):
    """THE DRAWING ITSELF, in the section about it (the person, 10 October
    2026: "add the logo drawing to the section in the about page about the
    logo"): the lockup the home page's heading draws, as the same mask over
    the text colour (app.css .aboutlogo), so it is right in both themes. A
    build without lockup.png -- a clone, a fork -- writes nothing here rather
    than an empty box, as the home page writes its name as text."""
    if not has_lockup:
        return ""
    return ('<p class="aboutlogo" role="img" aria-label="The Granite Record logo, '
            'drawn by Debra Caplan"></p>\n')


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
  // The Speaker's circle carries no number: the <g> round it and the word
  // "Speaker" does (seating.svg), so choosing the Speaker named him and lit
  // his row and never his chair (the review of 7 October 2026). A circle
  // with no number of its own takes its group's.
  function mark(seat){
    rows.forEach(function(r){r.classList.toggle("on",!!seat&&r.dataset.seat===seat);});
    if(svg)[].forEach.call(svg.querySelectorAll(".seat"),function(c){
      var p=c.parentNode, n=c.getAttribute("data-seat")||
        (p&&p.getAttribute?p.getAttribute("data-seat"):null);
      c.classList.toggle("on",!!seat&&n===seat);});
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
        " — "+tr("sc.seat","seat {plate}",{plate:plate(c.getAttribute("data-seat"))})));
      return;
    }
    var shown=rows.filter(function(r){return !r.hidden;}).length;
    note.textContent=shown===rows.length?""
      :tr("sc.shown","{n} of {m} representatives",{n:shown,m:rows.length});
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
    return !!w;
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
  /* A CHART IN A TAB NOT YET OPEN HAS NO WIDTH. The page opens on its Towns
     tab, so the chart is hidden when this runs and fit() met a box 0px wide:
     it left the zoom at 1, and a phone that went Legislators, then By seat,
     was shown the whole floor with seats five pixels across, where the page
     opened at #legislators was zoomed in to 315% (the review of 7 October
     2026). So fit waits for the box to have a width, once, and then lets
     go: after that the zoom is the reader's. */
  if(!fit()&&wrap&&typeof ResizeObserver==="function"){
    var sized=new ResizeObserver(function(){
      if(wrap.clientWidth){sized.disconnect();fit();}
    });
    sized.observe(wrap);
  }

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
    /* ONE STOP FOR THE TAB KEY, AND THE ARROW KEYS WITHIN IT. Every seat was
       its own Tab stop: 382 of them between the chart's controls and the
       list under it, from the 6th Tab press to the 387th (the audit of
       2 October 2026, M22). seating.py writes every seat out of the Tab
       order now; this makes one of them the stop -- the first, until a seat
       is chosen or reached -- and the arrow keys walk the seats in the order
       of their numbers, Home and End to the first and the last. That order
       runs the way the chart is drawn: Division 1 on the left to Division 5
       on the right, so Right goes on toward 5 (seating.LEFT_TO_RIGHT). Focus
       on a seat names its member under the chart, as the pointer over it does. */
    var seats=[].slice.call(svg.querySelectorAll("[data-slug]"))
      .filter(function(c){return c.getAttribute("data-slug");});
    var stopAt=function(c){
      seats.forEach(function(s){s.setAttribute("tabindex",s===c?"0":"-1");});
    };
    if(seats.length)stopAt(seats[0]);
    svg.addEventListener("keydown",function(e){
      var c=seatHit(e.target), i=seats.indexOf(c), j=-1;
      if(i<0)return;
      if(e.key==="ArrowRight"||e.key==="ArrowDown")j=Math.min(seats.length-1,i+1);
      else if(e.key==="ArrowLeft"||e.key==="ArrowUp")j=Math.max(0,i-1);
      else if(e.key==="Home")j=0;
      else if(e.key==="End")j=seats.length-1;
      else return;
      e.preventDefault();
      stopAt(seats[j]); seats[j].focus(); centre(seats[j]);
    });
    /* HEARD ON THE BOX ROUND THE CHART, NOT ON THE CHART. Chrome takes an
       <svg> that listens for focus to be something the Tab key stops on, so
       with these two on the svg the chart itself became a stop between Fit
       and the seat: a ring round all 400 seats, drawn where the box clips
       it, and no key that did anything there. And leaving a seat emptied the
       note under the chart -- which holds the link to the member's page, the
       next thing Tab reaches -- while focus was on its way to it, so that
       press landed on nothing and the link could not be reached from a seat
       at all (the review of 2 October 2026). The note is left as it is while
       focus goes into it, and put back when focus leaves it: for the list
       under the chart it says again whatever is chosen, and for a seat the
       seat's own focus names its member a moment later. */
    var host=wrap||svg.parentNode;
    host.addEventListener("focusin",function(e){
      var c=seatHit(e.target); if(c){stopAt(c);say(c);}
    });
    host.addEventListener("focusout",function(e){
      if(note&&e.relatedTarget&&note.contains(e.relatedTarget))return;
      say();
    });
    if(note)note.addEventListener("focusout",function(){say();});
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

# THE BILL MATCHER, FOR THE HEADER SEARCH. The header's panel shows how many
# of the current term's bills match what was typed, and /search how many of
# every term's, and each number has to be the one /bills?q= then shows (on
# All terms, for /search's) -- a panel that promises "All 30
# bills" and opens on 28 is a count the reader stops trusting. So they count
# with app.js's own matcher rather than a second one. app.js marks the lines
# that make it up (SYN and the query groups, the bill order, what a bill
# number is) between BILLMATCH:BEGIN and BILLMATCH:END; this copies them,
# unchanged and in order, into site/billmatch.js, inside a function so that
# none of their names can collide with a page's own, and hands back the ones
# the header uses -- looseness since 25 September, so that the header and
# /search put a bill that has the word itself above one that only has a
# longer word it begins, as /bills does; and since 1 October indexAdd (the
# header hands it sidx/<term>.json, what each bill's analysis and text are
# about), readShort (a two-letter word read as the start of one where a
# search lists nothing), whyListed (the line that says why a bill is listed),
# and spelling and wordsAdd (a misspelt word offered as the word it sounds
# like, once sidx/words.json says it is no word of any bill), and since
# 2 October knownWord (so the header offers no member's name for a word the
# bills use: "zebra" was offered "debra"); and since 16 October 2026
# titleShare and statusCat, best match's tie-break -- a bill still moving
# first where its title has the search, then the most of the title that is
# the search -- so that the header and /search break a tie as /bills does.
# find.js loads it only when somebody types, and only on a page that does
# not already run app.js.
BILLMATCH_BEGIN, BILLMATCH_END = "// BILLMATCH:BEGIN", "// BILLMATCH:END"
BILLMATCH_EXPORTS = ("queryGroups", "groupWeight", "billNumbers", "billKey",
                     "looseness", "indexAdd", "readShort", "whyListed",
                     "spelling", "wordsAdd", "knownWord", "matchScore",
                     "titleShare", "statusCat")


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


# THE WORDS INTO components.js (the component plan's C3, approved 9 October
# 2026). The chip's words and classes, the kinds of meeting, the vote words
# and the glossary are JSON in src/pages/words/, which components.py reads as
# WORDBOOK for the builders. The browser has them from site/components.js: its
# copy in src/pages/ marks where they go and holds none of them, and the
# build writes them there, so each table is written once where there were
# two kept alike by hand. A marker missing, doubled, out of order or sharing
# a line stops the build rather than publishing a components.js without the
# words, where app.js would meet WORDBOOK as a name never defined and draw no
# bill, member or committee at all.
WORDBOOK_START, WORDBOOK_END = "// WORDBOOK:START", "// WORDBOOK:END"


def words_js(nl="\n"):
    """The words as site/components.js carries them: one const, WORDBOOK, each
    file of src/pages/words/ on a line of its own, as compact JSON, which is
    a JavaScript literal of the same value."""
    return ("const WORDBOOK={" + nl
            + ("," + nl).join(json.dumps(k) + ":" + json.dumps(v, ensure_ascii=False,
                                                                separators=(",", ":"))
                              for k, v in WORDBOOK.items())
            + "};" + nl)


def with_words(js):
    """components.js as the site gets it: `js`, the file in src/pages/, with
    the words written between its two markers, each of which begins a line
    of its own, in the file's own line ending. Raises ValueError where a
    marker is missing, doubled, out of order or does not begin its line."""
    a, b = js.find(WORDBOOK_START), js.find(WORDBOOK_END)
    eol = js.find("\n", a)
    if (js.count(WORDBOOK_START), js.count(WORDBOOK_END)) != (1, 1) or not (-1 < a < eol < b) \
            or (a and js[a - 1] != "\n") or js[b - 1] != "\n":
        raise ValueError(
            f"components.js must hold one {WORDBOOK_START} line and one {WORDBOOK_END} line "
            f"after it, each beginning its line, for the build to write the words between "
            f"(it holds {js.count(WORDBOOK_START)} and {js.count(WORDBOOK_END)})")
    return js[:eol + 1] + words_js("\r\n" if "\r\n" in js else "\n") + js[b:]


# THE ALL-RESULTS PAGE. find.js's panel is a dropdown: it shows eight rows and
# hands the rest on. Until 19 September it handed them to the BILL search,
# which indexes bills and nothing else -- so "See all search results for
# Concord" led to a page with no towns in it. This page reads the same
# find.json with the cap off and groups what it finds.
#
# It reuses find.js wholesale -- findRows, findMatch, findOffers, _fmark,
# _froot, _fwhole, FKIND, and for the bills findBills, findBillsLoad,
# findBillsLoadAll, findBillsAll and findBillRow -- because a second matcher
# would be a second thing to keep in
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
  // THE GUIDES FIRST, AND LEARN WITH THIS SITE'S PAGES (17 October 2026: "the
  // how to guides should be incorporated into the search in some fashion").
  // A guide is found by its task and its plain words (find.js, _fnamed), so
  // when it is found it is what the reader came to do; the Learn pages, which
  // this page listed nowhere before, go with the site's other pages, after
  // the bills.
  // A STATUTE ASKED FOR BY ITS NUMBER, FIRST (the audit of 25 October 2026,
  // M3): find.js's one Law row, "RSA 91-A" (findLawRow).
  {t:"Laws",                k:r=>r[0]==="law"},
  {t:"How-To Guides",       k:r=>r[0]==="guide"},
  {t:"Senators",            k:r=>r[0]==="legislator"&&/^Senate/.test(r[2])},
  {t:"Representatives",     k:r=>r[0]==="legislator"},
  // A committee that no longer sits goes with the people who have left, below
  // the ones that do (find.js, _fgone).
  {t:"Committees",          k:r=>r[0]==="committee"&&!r[5]},
  // A city above its wards, each ward a Ward (find.json, 25 October 2026).
  {t:"Towns and wards",     k:r=>r[0]==="town"||r[0]==="ward"},
  {t:"Subjects",            k:r=>r[0]==="topic"},
  // THE OFFICIALS PAGE AND ITS TABS, before the bills where a name of theirs
  // was typed (the audit of 25 October 2026, M3): "my senator" is the page,
  // "ayotte" its Executive Branch, "shaheen" its Federal Delegation.
  {t:"Officials",           k:r=>r[0]==="page"&&/^[/]?officials([#?]|$)/.test(r[3])},
  // Their own group, after the bills (AFTER): find.js, _fstudy (18 October 2026).
  {t:"Statutory and study committees",k:r=>r[0]==="statutory"||r[0]==="study"},
  {t:"Former senators",     k:r=>r[0]==="former"&&/^Senate/.test(r[2])},
  {t:"Former representatives",k:r=>r[0]==="former"&&/^House/.test(r[2])},
  {t:"Former members",      k:r=>r[0]==="former"},
  {t:"Former committees",   k:r=>r[0]==="committee"},
  {t:"Learn",               k:r=>r[0]==="learn"},
  {t:"Pages on this site",  k:r=>r[0]==="page"}
];

// A committee by its chamber, as the header's rows show it (find.js, findName).
const row=(r,q)=>`<a href="${esc(_froot(r[3]))}">
  <span class="fl1"><span class="fname">${_fmark(findName(r),q)}</span>
  ${chip(findKind(r),"fkind")}</span>
  ${findWhat(r,q)?`<span class="fwhat">${esc(findWhat(r,q))}</span>`:""}</a>`;

// THE BILLS, counted. Until 24 September this was one card at the foot of the
// page, "Search every bill for firearms", under a line saying nothing on the
// site matched -- over 30 bills of this term. find.js's findBills counts them
// with the bill search's own matcher, so the number here is the one /bills?q=
// then shows, and the first five are listed. Before they are counted, or if
// they cannot be, the card offers the bill search without a number.
//
// Its description used to say the bill search reads "the words in its text"
// when it read a bill's number, title, sponsor and committee. Since 1 October
// it does read the topic, the analysis and the text (build_search_index.py),
// and a row found that way says so.
const WHAT="The bill search has every term since 1989, with filters for "
  +"committee, sponsor and what became of it.";
const WHAT_ALL="In the bill search, with filters for committee, sponsor and "
  +"what became of it.";
/* EVERY TERM'S BILLS (the person, 24 September: "all terms should show up in
   the full search results"). Until then this page counted the current
   term's alone, as the header's panel does, so a reader looking for SB 412
   of 2000 or the bail bills of 2019 was told about 2026's. B is what the page
   counts: every term's once findBillsLoadAll has them all, and the current
   term's until then or if it cannot, with the page saying which. C is the
   current term's, which gets a row of its own under the total, since the
   bill search opens on it. The rows are dated -- "SB 412 (2000)" -- because
   across terms a number alone names up to nineteen bills, and for a number
   every one of them is listed rather than the first five: SB 412 is in
   fourteen terms, and the 2000 bill is the twelfth of them. */
/* NEXT SESSION'S REQUESTS, ON ONE LINE OF THEIR OWN (the audit of 25
   October 2026, S5): how many of them match, as the line above says how many
   of the bills are this term's, and the bill search opened on their list.
   Not a group and not in the bills' count: requests are not bills yet, and
   no term's (find.js, FREQ). R is findBills(q,0,"requests"). */
const asked=(q,R)=>R&&R.state==="ready"&&R.n
  ?`<a class="fbills" href="/bills?q=${_fenc(q)}&amp;term=${_fenc(R.term)}">
    <span class="fl1"><span class="fname">${R.n===1?"1 bill request"
      :`${R.n.toLocaleString()} bill requests`} for ${esc(FREQ.year)}</span></span>
    <span class="fwhat">Not bills yet: listed in the bill search under
      ${esc(FREQ.label||"its bill requests")}.</span></a>`:"";
/* A MEMBER'S BILLS WHERE THEIR NAME LISTS NONE (the audit of 25 October 2026,
   M3). A name finds the person and never their bills (app.js, A NAME IS NOT
   WHAT A BILL IS ABOUT), so "daryl abbas" was told "no bill in any of the
   19 terms" under Sen. Abbas, whom the index names as sponsor or co-sponsor
   of 182 (the preview's, 25 October 2026). Where the search finds a
   member by a whole word of their name and no bill, the bills' place is one
   link: theirs, the Sponsor filter on All terms, with the name the bills
   give their sponsor -- the prime sponsor's of a bill whose sponsor_slug is
   the member's page, or their own name where they only co-sponsored, which
   the index spells as the member's (every one of the 328 sitting members
   with a bill, on 25 October 2026). A member no bill names keeps the line
   that says so. {who, name} for the first such member in `rows`, or null. */
const memberBills=(rows,s)=>{
  const pool=FALL.rows||FBILLS.file||[];
  for(const m of rows){
    if((m[0]!=="legislator"&&m[0]!=="former")||!_fwhole(m,s))continue;
    const slug=String(m[3]||"").replace(/^[/]?legislator[/]/,"").replace(/[.]html$/,"");
    const who=_fbare(m[1]).replace(/[ ]*[(][^()]*[)]$/,"");
    const own=who.replace(/^(Rep|Sen)[.] /,"");
    const b=pool.find(x=>x.sponsor_slug===slug);
    const name=b?b.sponsor:pool.some(x=>(x.cosp||[]).includes(own))?own:"";
    if(name)return {who,name};
  }
  return null;
};
const theirs=M=>`<a class="fbills" href="/bills?sponsor=${_fenc(M.name)}&amp;term=all">
    <span class="fl1"><span class="fname">${esc(M.who)}&rsquo;s bills</span></span>
    <span class="fwhat">Every bill they sponsored or co-sponsored, in the bill search.</span></a>`;
const bills=(q,B,C,counting,R,mem)=>{
  const counted=B&&B.state==="ready";
  const every=counted&&B.every;
  const what=every?WHAT_ALL:counting?"Counting the earlier terms&hellip;":WHAT;
  const none=every?`None in any of the ${B.terms.length} terms.`
    :counted?`None in the ${esc(B.term)} term.`:"";
  const now=every&&C&&C.state==="ready"&&C.n&&C.n<B.n
    ?`<a class="fbills" href="/bills?q=${_fenc(q)}">
      <span class="fl1"><span class="fname">${C.n.toLocaleString()} of them in
        the ${esc(C.term)} term</span></span>
      <span class="fwhat">The current term, where the bill search starts.</span></a>`:"";
  const top=B&&B.top?(B.numbers?B.top:B.top.slice(0,5)):[];
  const body=(counted&&B.n
    ?findBillsAll(B,q,what)+now+top.map(b=>findBillRow(b,q,every,B.why.get(b))).join("")
    :counted&&mem?theirs(mem)
    :counted
    ?`<a href="/bills?q=${_fenc(q)}">
      <span class="fl1"><span class="fname">Search every bill for
        &ldquo;${esc(q)}&rdquo;</span></span>
      <span class="fwhat">${none} ${counting?what:WHAT}</span></a>`
    :findBillsAll(B,q,WHAT))+asked(q,R);
  return `<section class="resgrp"><h2>Bills${counted&&B.n
    ?` <span class="resn">${B.n.toLocaleString()}</span>`:""}</h2>
    <div class="findout resout">${body}</div></section>`;
};
// Groups a reader reaches for after the bills: members who have left, and
// this site's own pages.
const AFTER=new Set(["Statutory and study committees","Former senators","Former representatives",
  "Former members","Learn","Pages on this site"]);
let waiting=false,waitingAll=false,waitingWords=false,waitingLaw=false,waitingReq=false;

function draw(q){
  const s=(q||"").trim();
  if(!s){
    head.textContent="Search the record";
    lead.textContent="Every sitting legislator and every member who has left, "
      +"every committee, every town and ward, every subject bills are filed "
      +"under, and every bill since 1989.";
    out.innerHTML="";
    return;
  }
  const rows=findMatch(s,Infinity);
  // A statute's number: the Laws pages' list of chapters, then drawn again.
  const law=findLawRow(s);
  if(law&&law.loading&&!waitingLaw){
    waitingLaw=true;
    findLawsLoad().then(()=>draw(box.value));
  }
  const C=findBills(s,40);
  const A=findBills(s,40,true);
  // Next session's requests, counted apart (find.js, FREQ).
  const R=findBills(s,0,"requests");
  if(R&&R.state==="loading"&&!waitingReq){
    waitingReq=true;
    findRequestsLoad().then(()=>draw(box.value));
  }
  if(C&&C.state==="loading"&&!waiting){
    waiting=true;
    findBillsLoad().then(()=>draw(box.value));
  }
  if(A&&A.state==="loading"&&!waitingAll){
    waitingAll=true;
    findBillsLoadAll().then(()=>draw(box.value));
  }
  const B=A&&A.state==="ready"?A:C;
  // This term's count is on the page while the others are still coming.
  const counting=!!(A&&A.state==="loading"&&B&&B.state==="ready");
  const nB=B&&B.state==="ready"?B.n:null;
  const term=nB===null?"":B.every?`across all ${B.terms.length} terms`
    :`in the ${B.term} term`;
  const noBill=nB===null?"":B.every?`no bill in any of the ${B.terms.length} terms`
    :`no bill ${term}`;
  // A member found by a whole word of their name, where no bill is: the
  // bills' place is their bills (theirs), and the lead says no "no bill".
  const mem=nB===0?memberBills(rows,s):null;
  const nR=R&&R.state==="ready"?R.n:0;
  head.innerHTML=`Results for &ldquo;${esc(s)}&rdquo;`;
  // The answer first. "0 matches on this site, and the bills" is a sentence
  // nobody would write, and "nothing matches" above 30 bills is false.
  // PAGES, NOT "MATCHES ON THIS SITE" (17 October 2026): "4 matches on this
  // site, and 940 bills" left a reader to work out that the four are the
  // legislators, committees, towns and subjects listed below.
  const here=rows.length===1?"One page on this site"
    :`${rows.length} pages on this site`;
  const some=nB===1?`One bill ${term}`:`${(nB||0).toLocaleString()} bills ${term}`;
  lead.textContent=(!rows.length
    ?(nB?`${some} ${nB===1?"matches":"match"}. No legislator, committee, `
        +"town or subject on this site does."
      :nB===0&&!counting&&!nR?"Nothing on this site matches that: no legislator, "
        +`committee, town or subject, and ${noBill}.`
      :nB===0?`No legislator, committee, town or subject on this site matches `
        +`that, and ${noBill}.`
      :"No legislator, committee, town or subject on this site matches that.")
    :nB?`${here}, and ${some.charAt(0).toLowerCase()+some.slice(1)}.`
    :nB===0&&mem?`${here}.`
    :nB===0?`${here}, and ${noBill}.`
    :`${here}, and the bills.`)
    +(counting?" Counting the earlier terms…":"");
  // WHERE THE BILLS GO, as in the header's panel: first unless a sitting
  // member, committee, town or subject has every word typed as a whole word
  // of its name (_fwhole), and then after those and ahead of the members who
  // have left. "bail" leads with the bail bills; "bailey" with Rep. Bailey.
  // A BILL NUMBER LEADS WITH THE BILLS, whatever else has its words (17
  // October 2026): a guide found by its own words is never put above a bill
  // whose number was typed.
  const named=!findBill(s)&&rows.some(r=>r[0]==="law"||(r[0]!=="former"&&_fwhole(r,s)));
  const left=rows.slice();
  let html=named?"":bills(s,B,C,counting,R,mem),placed=!named;
  for(const g of GROUPS){
    const mine=[];
    for(let i=left.length-1;i>=0;i--)
      if(g.k(left[i]))mine.unshift(left.splice(i,1)[0]);
    if(!mine.length)continue;
    if(!placed&&AFTER.has(g.t)){html+=bills(s,B,C,counting,R,mem);placed=true;}
    html+=`<section class="resgrp"><h2>${esc(g.t)}
      <span class="resn">${mine.length}</span></h2>
      <div class="findout resout">${mine.map(r=>row(r,s)).join("")}</div></section>`;
  }
  if(!placed)html+=bills(s,B,C,counting,R,mem);
  // Only when something close exists, and only when no bill matched either
  // ("voting" was offered "zoning" over 141 bills). find.js's findOffers
  // gives a name close to what was typed and the word of the bills that a
  // misspelt one sounds like ("medicade", "firarms"), and nothing rather
  // than reaching: a word any bill has used is never offered as another.
  // Not while the earlier terms are still being counted either.
  if(!rows.length&&!nB&&!nR&&!(B&&B.state==="loading")&&!counting){
    const offer=findOffers(s,!!(B&&B.every));
    if(offer.wait&&!waitingWords){
      waitingWords=true;
      offer.wait.then(()=>draw(box.value));
    }
    const did=offer.words.map(d=>
      `<a href="/search?q=${_fenc(d)}">${esc(d)}</a>`);
    if(did.length)html=`<p class="note">Did you mean ${did.join(" or ")}?</p>`+html;
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
      const u=v?`/search?q=${_fenc(v)}`:"/search";
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


# THE OLD PAGE'S TOWNS TAB IS MY TOWN. /legislators#towns arrives here as
# /officials#towns through the 301, and the tab it named is #my-town now: the
# address is rewritten before TABS_JS reads it, without a history entry.
# AND STATEWIDE OFFICIALS IS EXECUTIVE BRANCH (17 October 2026). The tab was
# renamed and its address with it, and a link already made to
# /officials#statewide must still open it, so the old address is rewritten
# the same way -- at load, and on a hashchange too, because this listener is
# added before TABS_JS's and so runs first, and a link to #statewide from the
# page itself then opens the tab rather than nothing.
OFFICIALS_HASH_JS = """<script>
(function(){
  var OLD={"#towns":"#my-town","#statewide":"#executive"};
  function alias(){
    var to=OLD[location.hash];
    if(to&&history.replaceState)
      history.replaceState(null,"",location.pathname+location.search+to);
  }
  alias();
  addEventListener("hashchange",alias);
})();
</script>"""

# THE DISTRICT MAP ON MY TOWN (map v1, src/pages/map.js, the person's label
# toggle with town names by default). Mounted the first time its tab is
# shown, at the size it will have: a map drawn into a hidden panel measures
# nothing. The finder's town is the map's town: typing a town's whole name,
# or opening a city's wards, zooms the map to it (LEGFIND_JS sends "grtown").
OFFICIALS_MAP_JS = """<link rel="stylesheet" href="/map.css">
<script src="/map.js" defer></script>
<script>
(function(){
  var el=document.getElementById("ofmap"),api=null,want=null;
  if(!el)return;
  function mount(){
    if(api||!window.GRMap||el.offsetParent===null)return;
    api=GRMap.mount(el,{layer:"base",layers:["base","senate","exec","cong"]});
    if(want)api.ready.then(function(){api.pickTown(want);});
  }
  addEventListener("DOMContentLoaded",mount);
  var pane=el.closest(".twnpane");
  if(pane&&window.MutationObserver)
    new MutationObserver(mount).observe(pane,{attributes:true,attributeFilter:["hidden"]});
  addEventListener("grtown",function(e){
    want=e.detail;
    if(api)api.ready.then(function(){api.pickTown(want);});else mount();
  });
})();
// THE CHOSEN TAB IN VIEW. Below 1024px the strip scrolls, so an address
// naming the fourth or fifth tab (/officials#executive) opened it with its
// tab half past the strip's edge; the strip is moved to show it, at load and
// whenever a tab is chosen, and the page itself does not move.
(function(){
  var bar=document.querySelector(".oftabs");
  if(!bar)return;
  function shown(){
    var t=bar.querySelector('[aria-selected="true"]');
    if(!t)return;
    var l=t.offsetLeft-bar.offsetLeft,r=l+t.offsetWidth;
    // 2rem clear of the edge, where the strip's shadow says it goes on
    if(l<bar.scrollLeft)bar.scrollLeft=Math.max(0,l-32);
    else if(r>bar.scrollLeft+bar.clientWidth)bar.scrollLeft=r-bar.clientWidth+32;
  }
  shown();
  // and again once the fonts have their widths
  if(document.fonts)document.fonts.ready.then(shown);
  bar.addEventListener("click",function(){setTimeout(shown,0);});
  bar.addEventListener("keydown",function(){setTimeout(shown,0);});
  addEventListener("hashchange",shown);
})();
</script>"""


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
// A party as the page's language says it, so a reader can find the members
// of one by typing its name in that language too (the Officials page in
// Spanish, 25 October 2026). In English these are the words already searched.
const PW={R:tr("party.r","Republican"),D:tr("party.d","Democrat"),
          I:tr("party.i","Independent"),L:tr("party.l","Libertarian")};

function slugOf(s){return String(s).toLowerCase().replace(/[^a-z0-9]+/g,"-")
  .replace(/^-|-$/g,"");}

/* RANKED, NOT JUST FILTERED. Somebody typing "Dover" was shown Andover first
   and their own town second, under a town they do not live in. Three tiers:
   the exact name, then names that BEGIN with what was typed, then names with
   a word that begins with it. "Hampton" lists Hampton, Hampton Falls, New
   Hampton and North Hampton, and all four are real answers.
   FROM THE START OF A WORD (the audit of 25 October 2026, M4): the third tier
   was any name that held the letters, so "Dover" still listed Andover, and
   "ham" Durham. A member's name and record are still searched anywhere in
   them (render(), m.hay). */
function tier(hay,n){const s=hay.toLowerCase();
  return s===n?0:s.startsWith(n)?1:(" "+s.replace(/-/g," ")).includes(" "+n)?2:3;}

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
      <span class="wct">${tr("lf.wards","{n} wards",{n:t.wards.length})}</span></button>`
      + (picked===t.town ? `<div class="wards">` + t.wards.map(w=>
          `<a class="wbtn" href="town/${esc(t.slug)}-ward-${esc(w)}.html"
            >${tr("lf.ward","Ward {w}",{w:esc(w)})}</a>`).join("") + `</div>` : "");
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
    if(mem.length)parts.push('<p class="lmhead">'+tr("lf.towns","Towns")+'</p>');
    parts.push(towns.map(([,t])=>townRow(t)).join(""));
  }
  if(mem.length){
    parts.push('<p class="lmhead">'+tr("lf.members","Members")+'</p>');
    parts.push(mem.slice(0,SHOW).map(([,m])=>
      `<a class="lmrow" href="legislator/${esc(m.slug)}.html">`
      +`<b>${esc(m.display)}</b>`
      +chip(m.p,"pt-"+m.p)
      +`<span class="lmwhere">${esc(m.where)}</span>`
      +`<span class="lmwhat">${m.chamber==="S"?tr("lf.senate","Senate"):tr("lf.house","House")}</span></a>`)
      .join(""));
    if(mem.length>SHOW)parts.push('<p class="lmnone">'
      +tr("lf.more","and {n} more members &mdash; type another letter or two.",{n:mem.length-SHOW})
      +'</p>');
  }
  // No apostrophe in these sentences on purpose: this is JavaScript inside a
  // Python string, where a backslash belongs to whichever one reads it
  // first. Python read one, dropped it, and left the JavaScript with an
  // unterminated string and the whole page with no script.
  /* THE MAP FOLLOWS THE FINDER: a town named in full, or a city whose
     wards were opened, is the map's town too (OFFICIALS_MAP_JS). */
  const exact=towns.length&&n&&towns[0][1].town.toLowerCase()===n?towns[0][1].town:null;
  const tw=picked||exact;
  if(tw&&tw!==window.__grTown){window.__grTown=tw;
    dispatchEvent(new CustomEvent("grtown",{detail:tw}));}
  out.innerHTML=parts.length?parts.join("")
    :'<p class="lmnone">'+tr("lf.none","Nothing matches that. Towns and wards, member names, counties, parties and committees are all searched.")+'</p>';
  /* WHAT THE LIST NOW HOLDS, SAID. It is redrawn at every letter and nothing
     told a screen reader that it had changed (the audit of 2 October 2026,
     S4). One line the eye does not see, role="status": how many towns and
     members match what was typed, or that nothing does. Silent while the box
     is empty, when the list is every town and is not an answer to anything. */
  const say=document.getElementById("lsay");
  if(say){
    const said=[towns.length?(towns.length===1?tr("lf.n_town","{n} town",{n:1})
                                 :tr("lf.n_towns","{n} towns",{n:towns.length})):"",
                mem.length?(mem.length===1?tr("lf.n_member","{n} member",{n:1})
                             :tr("lf.n_members","{n} members",{n:mem.length})):""]
      .filter(Boolean);
    const what=said.length===2?tr("lf.and","{a} and {b}",{a:said[0],b:said[1]}):said[0];
    const text=!n?"":!said.length?tr("lf.nothing","Nothing matches that.")
      :towns.length+mem.length===1?tr("lf.matches","{what} matches",{what:what})
      :tr("lf.match","{what} match",{what:what});
    if(say.textContent!==text)say.textContent=text;
  }
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
    const chName=ch==="Senate"?tr("lf.senate","Senate"):tr("lf.house","House");
    return `<h2>${chName} &mdash; ${total}</h2>`+counties.map(c=>{
      // By district number, then by name. Alphabetical order inside a county
      // scattered the members of one district across the list, when the
      // district is the thing a reader is looking for: it is what a town
      // lookup returns and what a ballot is organised by.
      const ms=by[ch][c].slice().sort((a,b)=>
        (parseInt(a.district,10)||0)-(parseInt(b.district,10)||0)
        ||a.sortname.localeCompare(b.sortname));
      return `<details class="cgrp"><summary><span>${c==="Not on file"?tr("lf.not_on_file","Not on file"):esc(c)}</span>`
        +`<span class="ccount">${ms.length}</span>`
        +`<span class="caret">&#9656;</span></summary><div class="grid">`
        // THE SAME CHIP AS THE OTHER TWO VIEWS (pchip in Python), which the
        // person asked for on 19 September; this view kept its own name, pill
        // and district until 24 September. display_full carries all three.
        +ms.map(m=>`<div class="mem"><span class="mchip p-${esc(m.p)}" translate="no">`
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
          (m.towns||[]).join(" "),PW[(m.party||"X")[0].toUpperCase()]||""].join(" ").toLowerCase()}));
   const box=document.getElementById("lq");
   box.disabled=false;
   document.getElementById("lcount").textContent=
     tr("lf.count","{t} towns and cities, {m} sitting members",{t:TOWNS.length,m:MEM.length});
   roster();
   /* ?town= and ?q= arrive from the home page's finder. Both fill the one
      field: a town that is warded cannot be resolved to a page without
      knowing the ward, so the reader picks it from the matches. */
   const pr=new URLSearchParams(location.search);
   const pre=(pr.get("town")||pr.get("q")||"").trim();
   if(pre)box.value=pre;
   /* A CITY NAMED IN THE ADDRESS OPENS ITS WARDS: the site search's one row
      for a city, "Concord, 10 wards", leads here (find.json, 25 October
      2026), and the reader came for a ward. */
   const city=TOWNS.find(t=>t.wards.length>1&&t.town.toLowerCase()===pre.toLowerCase());
   if(city)picked=city.town;
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


# THE WAY FROM THE STATUS BOX TO THE LEGISLATURE'S YEAR (the person, 17
# October 2026: a page on the schedule "which links to the homepage status in
# some way so that folks understand when the legislature is in session and the
# various deadlines around filing bills"). One line at the foot of the box,
# written once here for both of its renderers -- the box main() builds and
# HOME_JS's copy -- so that the two cannot say different things; the address
# and the link's words are legislative_year's, the page's own.
YEAR_LINK = (f'<p class="statenote stateyear"><a href="{_year.HREF}">'
             + _html.escape(_year.HOME_LINK).replace("&#x27;", "&rsquo;")
             + '</a></p>')    # the words alone (the person, 22 October 2026)


# THE WEBINAR, ON THE HOME PAGE UNTIL IT IS OVER (the person, 22 October
# 2026: "put the registration on the homepage ... and remove it after the
# webinar is over"). It retires the way a member-elect's box does
# (until_attrs): from WEBINAR_UNTIL, the day after it, components.js hides it
# by the reader's own date, so a page built before then does not keep it; and
# a build on or after that day leaves it out.
WEBINAR_UNTIL = "2026-11-11"
WEBINAR_URL = "https://zoom.us/meeting/register/SoxLZ-b5TnWYcGPfmVaZDA#/registration"


def home_webinar(today=None, lang="en"):
    """The webinar's box for the home page, or "" once it is over. In
    another language it says the webinar is held in English."""
    today = today or build_date.today().isoformat()
    if str(today)[:10] >= WEBINAR_UNTIL:
        return ""
    return (f'<aside class="webinar" aria-label="{_html.escape(say(lang, "web.label", "Webinar"))}"'
            f'{until_attrs(WEBINAR_UNTIL, today)}>'
            f'<p class="wbwhen">{say(lang, "web.when", "Free webinar &middot; Tuesday, November 10, 6:30 p.m.")}</p>'
            f'<p class="wbwhat">{say(lang, "web.what", "How Granite Record works, and how to use it to keep up with Concord this session. Hosted by Alice Wade. All are welcome to join, ask questions and say which features they would like most.")}</p>'
            f'<a class="wbgo" href="{_html.escape(WEBINAR_URL, quote=True)}" target="_blank" rel="noopener">'
            f'{say(lang, "web.go", "Register on Zoom")}</a></aside>')


def _home_esc(x):
    """The home page's escape: components.js's esc, the ampersand, the angles
    and the double quote."""
    return (str(x or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _record(x, lang):
    """The record's own words (a bill's title, the hand-kept status note), as
    the record has them: in English, marked so on a page in another language,
    so a screen reader says them in English (i18n.py, the first kind)."""
    x = _home_esc(x)
    return x if lang == i18n.DEFAULT or not x else f'<span lang="en">{x}</span>'


def year_link(lang="en"):
    """YEAR_LINK in `lang`: the way to the legislature's year, in `lang`
    where that page is built in it (i18n.href). Absolute, because the
    Spanish home page carries <base href="/">, under which the bare HREF
    opened the English page."""
    if lang == i18n.DEFAULT:
        return YEAR_LINK
    return (f'<p class="statenote stateyear"><a href="{i18n.href(lang, _year.HREF)}">'
            + say(lang, "home.year_link", "NH Legislative Schedule") + '</a></p>')


def deadline_line(lang="en", today=None, events=None):
    """The status box's next deadline (key_dates.deadline_html), or "".

    THE MOST RELEVANT UPCOMING DEADLINE (the owner, 24 October 2026:
    "Statuses should list the most relevant upcoming deadline like the
    deadline for committees to finish interim study reports, filing periods,
    etc."): the nearest last day for something on the legislature's schedule,
    or the last day of a filing period, on or after the build's day, by the
    rule key_dates.next_deadline gives. Above the way to the schedule, which
    is where it comes from. Both copies of the box carry it -- this one, and
    HOME_JS's through home_js -- and it retires the day after its date in the
    reader's clock (components.until_attrs)."""
    import key_dates as KD
    today = today or build_date.today()
    return KD.deadline_html(KD.events(today) if events is None else events, today, lang)


def state_box(S, lang="en", today=None, events=None):
    """The status box as the server draws it, from home.json's status, in
    `lang`: the phase, the last session day, the hand-kept headline and note
    (the person's own words, so in English on every page), the next
    milestone, the summary's date or the warning that it is stale, and the
    legislature's next deadline (deadline_line) over the way to its
    schedule."""
    esc = _home_esc

    def fd(d):
        """"Aug 19", the form HOME_JS's fd() writes: shell.date_words."""
        return esc(_shell.date_words(d or "", "short", lang))

    static_state = ""
    if S.get("headline") or S.get("phase"):
        ph = {"in session": ("live", say(lang, "state.in", "In Session")),
              "veto day pending": ("wait", say(lang, "state.veto", "Awaiting Veto Day")),
              "between sessions": ("wait", say(lang, "state.between", "Between Sessions")),
              "out of session": ("off", say(lang, "state.out", "Out of Session"))}.get(
                  (S.get("phase") or "").lower(), ("off", S.get("phase") or ""))
        ms = (S.get("milestones") or [{}])[0]

        def fdy(d):
            """"Aug 19, 2026", the form HOME_JS's fdy() writes."""
            return esc(_shell.date_words(d or "", "medium", lang))
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
            + (f'<span class="statemeta">{say(lang, "state.last", "Last Session Day:")} '
               f'{fdy(S["last_session"])}</span>'
               if S.get("last_session") else "")
            + "</div>"
            + (f'<p class="statehead">{_record(S["headline"], lang)}</p>'
               if S.get("headline") else "")
            + (f'<p class="statenote">{_record(S["note"], lang)}</p>' if S.get("note") else "")
            + (f'<p class="statenote"><b>{say(lang, "state.next", "Next:")} '
               f'{_record(ms.get("label"), lang)}</b>, '
               f'{fd(ms.get("date"))}. {_record(ms.get("note"), lang)}</p>'
               if ms.get("label") else "")
            # THE STALE WARNING CARRIES ITS OWN DATE, so the page can work it
            # out again in the reader's clock: it was written when the site was
            # built and read for as long as the build stood.
            + (f'<p class="statenote stalewarn" style="color:var(--st-veto)" '
               f'data-updated="{esc(S.get("updated") or "")}">'
               + say(lang, "state.stale", "This summary was last updated {n} days ago and "
                     "may be out of date.", n=S["stale_days"]) + '</p>' if stale
               # NO "SUMMARY UPDATED" LINE (the person, 25 October 2026: "the
               # summary updated line can also be removed"). The date stays,
               # hidden, so that the reader's clock can still turn it into the
               # stale warning above once the summary is 45 days old.
               else (f'<p class="statemeta upd" hidden '
                     f'data-updated="{esc(S.get("updated") or "")}"></p>'
                     if S.get("updated") else ""))
            + deadline_line(lang, today, events) + year_link(lang) + "</div>")
    return static_state


# ---- LATEST ACTIVITY, A MEETING AN ITEM -------------------------------------
# The person, 24 October 2026: "bills should not be repeated twice like they
# are right now for both the bill executive sessions and the outcome of the
# executive session listed as two separate meetings. Maybe have latest
# activity show things like recent meetings and all the bills from that
# meeting are grouped together and when you click it, it takes you to the
# committee page or a house session day page scrolled down to that meeting?"
# home.json's `latest` is the meetings (latest_activity.py says why the box
# repeated a bill, and how a meeting and what it did are read); this draws it.

# WHAT A COMMITTEE RECOMMENDED, IN THE COLOUR OF WHAT IT MOVED, as a bill's
# Reports tab colours the same recommendation (app.js RECCOLOUR): killing it
# in the grey of a bill that died, interim study or another committee in the
# orange of interim study, passing it in the green of a law. By the chips'
# own kinds (chips.json), so the colours are the chips'. Without
# Recommendation takes none.
REC_KIND = {"OTP": "law", "OTPA": "law", "ITL": "done", "IS": "study", "RR": "study"}
# An interim study report: recommending the subject for future legislation in
# the orange of its mark on a committee's page (app.css .mrec), and not
# recommending it, or making no recommendation, in the grey of the killing
# the person called it (committee_acts, v8; .mkill).
STUDY_KIND = {"rec": "study", "not": "done", "without": "done"}


def _vote_chip_said(key, passed, bill, fill, lang="en"):
    """components.vote_chip, the chip a sitting's page draws for the motion
    (votes.json's words, coloured by whether the motion passed), in `lang`:
    each of its words is votes.json's, translated by the table of them
    (i18n.say_word, "vote"), and a place in them filled after."""
    if lang == i18n.DEFAULT:
        return _components.vote_chip(key, passed, bill, fill)
    if passed is None:
        return ""
    v = WORDBOOK["votes"]
    m = (v["consent"] if key == "consent" else v["motions"].get(key)) or {}
    prefix = re.match(r"[A-Z]+", str(bill or "").upper())
    noun = next((n for n, ps in v["nouns"].items() if prefix and prefix.group(0) in ps), "")
    raw = m.get("passed" if passed else "failed") or ""
    vals = {k: i18n.say_word(lang, "vote", x) for k, x in (fill or {}).items() if k == "Chamber"}
    vals.update({k: x for k, x in (fill or {}).items() if k != "Chamber"})
    if noun:
        vals["Bill"] = i18n.say_word(lang, "vote", noun)
    tail = "" if not raw or ("{Bill}" in raw and not noun) else i18n.fill(i18n.say_word(lang, "vote", raw), vals)
    tail = "" if "{" in tail else tail
    word = i18n.say_word(lang, "vote", v["passed"] if passed else v["failed"]) + (f": {tail}" if tail else "")
    return chip(word, "rcres " + ("pass" if passed else "fail"))


def did_html(did, bill, lang="en"):
    """What a meeting did to a bill (latest_activity's `did`), as Latest
    Activity draws it beside the bill's number: a chip in the words the site
    already says it in, the vote, and the day the docket dates it where that
    is not the meeting's. "" where the meeting did nothing to it that the
    record dates (a hearing, a work session)."""
    if not did:
        return ""
    esc = _home_esc
    kinds = WORDBOOK["chips"]["kind"]
    act, en = did.get("act"), lang == i18n.DEFAULT
    if act == "floor":
        out = _vote_chip_said(did.get("mk") or "", did.get("carried"), bill, did.get("mf"), lang)
    elif act == "report":
        code = did.get("code") or ""
        if code in CA.REC_WORDS:
            out = chip(i18n.say_word(lang, "rec", CA.REC_WORDS[code]),
                       f"cstat {kinds.get(REC_KIND.get(code), '')}".strip())
        else:
            # A recommendation of no code the site knows: the docket's own
            # words, as a bill's Reports tab chips them, in English.
            out = (("" if en else '<span lang="en">')
                   + chip(_components.title_words(did.get("recommendation") or ""), "cstat")
                   + ("" if en else "</span>"))
    elif act == "study report":
        sr = WORDBOOK["study_report"]
        phrase = sr["said"].get(did.get("said") or "") or sr["head"]
        word = i18n.say_word(lang, "study", phrase)
        word = _components.title_words(word) if en else word[:1].upper() + word[1:]
        out = chip(word, f"cstat {kinds.get(STUDY_KIND.get(did.get('said') or ''), '')}".strip())
    elif act == "retained":
        out = chip(say(lang, "home.retained", "Retained"), f"cstat {kinds['active']}")
    else:
        return ""
    if did.get("yeas") is not None and did.get("nays") is not None:
        out += f' <span class="latvote">{did["yeas"]}–{did["nays"]}</span>'
    if did.get("dated"):
        out += (' <span class="latdated">'
                + say(lang, "home.dated", "dated {date}",
                      date=esc(_shell.date_words(did["dated"], "short", lang))) + "</span>")
    return out


def past_rel(date, today, lang="en"):
    """How long ago a day of Latest Activity was, beside its date as Coming
    up says how far off its days are: "today", "yesterday", "3 days ago",
    and nothing past a fortnight or for a day not yet past. HOME_JS's latRel
    says the same in the reader's own clock, which is the one that knows what
    today is."""
    import datetime as _dt
    try:
        off = (today - _dt.date.fromisoformat(str(date)[:10])).days
    except (TypeError, ValueError):
        return ""
    if off == 0:
        return say(lang, "cal.today", "today")
    if off == 1:
        return say(lang, "cal.yesterday", "yesterday")
    if 1 < off <= 14:
        return say(lang, "cal.days_ago", "{n} days ago", n=off)
    return ""


def latest_href(m, codes, sits):
    """Where a meeting of Latest Activity leads: a committee's page at that
    day's meeting (#day-<date>, which app.js's showDay opens on the Meetings
    tab, as Coming up's cards lead), or the sitting's own page; None where
    there is neither."""
    if m.get("floor"):
        key = (m.get("body"), m.get("date"))
        return f"session/{key[0]}/{key[1]}.html" if key in (sits or ()) else None
    code = (codes or {}).get(((m.get("body") or "").strip().upper(),
                              (m.get("committee") or "").strip().lower()))
    return f"committee/{code}.html#day-{m.get('date')}" if code else None


def latest_card(m, lang, codes, sits, esc):
    """One meeting of Latest Activity, as Coming up draws a meeting
    (cal_days): a card with its colour bar, its name, its hours and how many
    bills it took up, which opens on those bills -- each with its title and
    what was done to it there, in the site's words and colour for it
    (did_html) -- and the way into the meeting: the committee's page at that
    day, or the sitting's own page."""
    # Here rather than above: build_calendar imports this module.
    import build_calendar as _BCal
    import latest_activity as _LA
    rec_attr = EN_ATTR if lang != i18n.DEFAULT else ""
    href = latest_href(m, codes, sits)
    if m.get("floor"):
        # A SITTING'S NAME SAYS WHAT IT IS ("House Session Day"), as its card
        # on the Calendar says it, and no word says it again.
        key = Meet(m.get("date") or "", m.get("body") or "",
                   _BCal.FLOOR.get(m.get("body"), ""), "")
        name, own, kinds = card_name(key, lang), False, []
    else:
        key = _LA.key_of(m)
        name = card_name(key, lang)
        own = lang != i18n.DEFAULT and name == card_name(key)
        kinds = m.get("kinds") or []
    bars = []
    for k in (m.get("kinds") or []):
        cls = MEET_KIND.get(str(k).strip().lower(), ("", ""))[1] or "k-other"
        if cls not in bars:
            bars.append(cls)
    bills = m.get("bills") or []
    n = int(m.get("n") or len(bills))
    time = clock_span(m["time"], m.get("last") or m["time"], lang) if m.get("time") else ""
    count = (say(lang, "cal.one_bill", "1 bill") if n == 1
             else say(lang, "cal.n_bills", "{n} bills", n=n))
    # THE SUMMARY IS COMING UP'S: the bar, the name, the hours with the count
    # beside them, the kinds as chips (which the rail hides, its bar being the
    # colour), and the caret.
    head = ('<span class="calmix" aria-hidden="true">'
            + "".join(f'<i class="{c}"></i>' for c in bars) + "</span>"
            + f'<span class="calcmte"{EN_ATTR if own else ""}>{esc(name)}</span>'
            + (f'<span class="caltime">{esc(time)}</span>' if time else "")
            + ('<span class="calcount">' + (f"({count})" if time else count) + "</span>"
               if n else "")
            + "".join(chip(kind_word(k, lang)[0], f"calkind {kind_word(k, lang)[1]}")
                      for k in kinds)
            + '<span class="caret"></span>')
    body = []
    # The kinds in words, at the top of what opens: the rail hides the chips.
    if kinds:
        body.append('<p class="latkinds">'
                    + esc(", ".join(kind_word(k, lang)[0] for k in kinds)) + "</p>")
    # EVERY BILL IT TOOK UP (the owner, 24 October 2026: "the ability to click
    # it for a dropdown to list all the bills from that session"), as many as
    # home.json keeps for a meeting the page shows (RECENT_BILLS), each once,
    # its title and then what was done to it, on a line of its own so that a
    # long outcome is one box that wraps inside itself rather than a chip torn
    # across two lines ("The status outcome cards that are split between lines
    # aren't displaying properly").
    if bills:
        body.append('<ul class="calbills">' + "".join(
            f'<li><a class="cbn" href="{esc(recent_href(b))}">{esc(b.get("n"))}</a>'
            '<span class="cbt">'
            + (f'<span class="latt"{rec_attr}>{esc(b.get("title"))}</span>'
               if b.get("title") else "")
            + (f'<span class="latdid">{did_html(b.get("did"), b.get("bill"), lang)}</span>'
               if b.get("did") else "")
            + "</span></li>" for b in bills) + "</ul>")
    rest = max(n - len(bills), 0)
    if rest:
        body.append('<p class="latmore">'
                    + say(lang, "home.n_more", "and {n} more", n=f"{rest:,}") + "</p>")
    # INTO THE MEETING, in Coming up's words for the same link.
    if href:
        if m.get("floor"):
            chamber = "House" if m.get("body") == "H" else "Senate"
            words = (f"What the {chamber} did that day" if lang == i18n.DEFAULT
                     else say(lang, "cal.house_did", "What the House did that day")
                     if chamber == "House"
                     else say(lang, "cal.senate_did", "What the Senate did that day"))
        else:
            words = say(lang, "cal.on_page", "This meeting on the {name} page",
                        name=esc(card_name(key)))
        body.append(f'<p class="calmore"><a href="{esc(href)}">{words}</a></p>')
    return (f'<details class="calmeet latm" data-date="{esc(m.get("date"))}"'
            f' data-kinds="{esc(" ".join(b[2:] for b in bars))}"><summary>{head}</summary>'
            f'<div class="calbody">{"".join(body)}</div></details>')


def recent_box(H, lang="en", codes=None, sits=None, today=None):
    """Latest Activity as the server draws it, IN COMING UP'S FORMAT (the
    owner, 24 October 2026: "I meant for latest activity that it could be
    formatted similarly to the coming up page just listing past events with
    the ability to click it for a dropdown to list all the bills from that
    session"): the newest meetings of home.json's `latest` under their days,
    newest first, each day headed as Coming up heads one -- its date and how
    long ago it was -- and each meeting a card as Coming up draws one
    (latest_card); and the way to the rest.

    `codes` is committee_codes', by which Coming up's cards link a committee;
    `sits` the sittings with a page (sitting_days); `today` the day "today"
    and "yesterday" are said from, which HOME_JS says again in the reader's
    own clock (latRel). THE ONE RENDERER: HOME_JS drew this box again from
    home.json after the page loaded, and does not now (see HOME_JS).

    ITS DAYS ARE NOT COMING UP'S. They are .calday blocks, as Coming up's
    are, and HOME_JS removes every Coming up day that has passed: it asks
    only within .cal, Coming up's section, and this box is not in one."""
    import datetime as _dt
    esc = _home_esc
    meets = (H.get("latest") or [])[:RECENT_SHOWN]
    if not meets:
        return ""
    today = today or build_date.today()
    if isinstance(today, str):
        today = _dt.date.fromisoformat(today[:10])
    days = {}
    for m in meets:
        days.setdefault(m.get("date") or "", []).append(m)
    html = []
    for d, ms in days.items():
        try:
            label = _shell.date_words(_dt.date.fromisoformat(d), "wkd", lang)
        except ValueError:
            label = d
        html.append(f'<div class="calday" data-d="{esc(d)}"><h3 class="caldate">'
                    f'<span>{esc(label)}</span>'
                    f'<span class="cdrel">{esc(past_rel(d, today, lang))}</span></h3>'
                    + "".join(latest_card(m, lang, codes, sits, esc) for m in ms) + "</div>")
    return (f'<h2>{say(lang, "home.recent", "Latest Activity")}</h2>'
            '<div class="latcal">' + "".join(html) + "</div>" + recent_more(lang))


def session_line(H, lang="en", sits=None):
    """The latest sitting of each chamber, as one line under the status box
    where it fits, and broken after its dash where it does not:
    "Aug 19, 2026 — House · Senate recordings", each chamber the way to its
    day's page, which opens on the recording.

    ONE LINE, NOT TWO PLAYERS (the audit of 25 October 2026, M8). Two large
    black players for the sittings of 19 August were the heaviest thing on
    the home page's first screen, under a date written as no other date on
    the site is ("August 19th, 2026"); the day's page has the recording and
    everything said and voted on around it. Chambers that last sat on
    different days take a line each, the newest first. A sitting with no
    page here (`sits`, sitting_days()) leads to its recording on YouTube, so
    neither chamber's is lost. "" where home.json names none."""
    esc = _home_esc
    by_day = {}
    for v in H.get("latest_sessions") or []:
        if v.get("date") and v.get("video_id"):
            by_day.setdefault(v["date"], []).append(v)
    lines = []
    for d in sorted(by_day, reverse=True):
        links = []
        for v in by_day[d]:
            b = "S" if v.get("chamber") == "Senate" else "H"
            href = (f"session/{b}/{d}.html" if (b, d) in (sits or ())
                    else f"https://www.youtube.com/watch?v={v['video_id']}")
            name = (say(lang, "home.senate", "Senate") if b == "S"
                    else say(lang, "home.house", "House"))
            links.append(f'<a href="{esc(href)}">{name}</a>')
        day = esc(_shell.date_words(d, "medium", lang))
        said = (say(lang, "home.recordings", "{date} — {chambers} recordings",
                    date=day, chambers=" · ".join(links)) if len(links) > 1
                else say(lang, "home.recording", "{date} — {chamber} recording",
                         date=day, chamber=links[0]))
        # IT BREAKS AFTER THE DASH, IF IT BREAKS (the preview check of 25
        # October 2026). The left rail's text is 258px wide from 1180px up,
        # and "Aug 19, 2026 — House · Senate recordings" needs about 325, so
        # the browser broke at the last space that fit and left "recordings"
        # alone on a second row (the Spanish, before "Cámara · Senado"). What
        # follows the dash is held together (.sesswhat, an inline block in
        # app.css), so a line too long for its rail reads "Aug 19, 2026 —"
        # over "House · Senate recordings", and one that fits, on a phone or
        # at 1024, is still one row; at a reader's larger default font size,
        # where even a row of its own cannot hold it, it still wraps. Split on
        # the words as said, so the Spanish keeps its own order; the date
        # holds no dash, so the first one is the template's.
        head, dash, rest = said.partition(" — ")
        if dash:
            said = f'{head}{dash}<span class="sesswhat">{rest}</span>'
        lines.append(f'<p class="sessline">{said}</p>')
    return "".join(lines)


def home_body(lang, has_lockup, static_state, static_up, static_recent, static_sessions):
    """The home page's <main>, in `lang`: the hero, the search box, the cards
    and the guides' slot in the middle; the status and the line to the latest
    sittings' recordings (session_line) on the left; Coming up, the rebuild
    line's slot (a warning only: HOME_JS) and Latest Activity on the right
    (the owner, 24 October 2026). The parts drawn from data are passed in,
    drawn in `lang`."""
    esc = _home_esc
    # THREE COLUMNS, AND THE MIDDLE ONE IS WRITTEN FIRST. The order here is
    # the order a screen reader hears and the order the Tab key takes; the
    # grid in app.css puts .hleft to the left of it. See the comment on
    # .hcols for why that way round.
    # THE HEADING IS THE LOCKUP WHERE THERE IS ONE. h1.lockup is a mask over
    # the text colour, and a mask whose file is missing is drawn as nothing:
    # an empty band above the search box, with the site's name hidden inside
    # it. A build that placed no lockup.png writes the name as text instead.
    home_h1 = ('<h1 class="lockup"><span>Granite Record</span></h1>' if has_lockup
               else '<h1 class="wordmark">Granite Record</h1>')
    # WHAT IS IN THE PAGE'S LANGUAGE, SAID ONCE (i18n.py): this page, and not
    # yet the pages it leads to, nor the record's own words.
    only = ("" if lang == i18n.DEFAULT else
            f'<p class="langnote">{say(lang, "home.lang_note", "This page is in Spanish. The rest of the site is in English for now, and so is what the record itself says: bill titles, committee names, each bill&rsquo;s history and the subjects the search knows.")}</p>\n')
    # THE GUIDES' SLOT is the English page's: build_civics fills it with
    # guides, and the guides are in English.
    guides = "<!-- guides --><!-- /guides -->" if lang == i18n.DEFAULT else ""
    # THE SLOGAN BREAKS AT ITS COMMA (the owner, 24 October 2026: "the line
    # split should be at the comma if possible"). Balanced, it broke after
    # "New Hampshire". Each half is one unit (.sl), so a line too narrow for
    # the whole puts "in one place." on the second line, and a half breaks
    # within itself only on a screen too narrow for it. The Spanish breaks
    # at its comma the same way.
    slogan = say(lang, "home.slogan", "New Hampshire government, in one place.")
    head, comma, tail = slogan.partition(", ")
    slogan = f'<span class="sl">{head},</span> <span class="sl">{tail}</span>' if comma else slogan
    # The columns' treatment, HOME_COLUMN_OPTIONS[HOME_COLUMNS]: one class.
    return f"""<div class="hcols {HOME_COLUMN_OPTIONS[HOME_COLUMNS]}">
<div class="hmid">
{home_h1}
<p class="slogan">{slogan}</p>
<p class="lead">{say(lang, "home.lead", "Keep up with New Hampshire legislation, find bills on the issues you care about, learn how the legislature works, and explore the record from 1989 to today.")}</p>
{only}<!-- ONE BOX, THE HEADER'S FINDER (D13, the person, 8 October 2026: "one
     search box like the header search: bills, legislators, towns, committees
     and the rest from the same box, with a dropdown of the top results (no
     separate legislator finder)"). find.js draws the top results into the
     box's own dropdown, the header panel's rows; Return takes the first, as
     in the header, and Search opens every result. Without script, Search
     opens the bill search, as it did.
     ITS WORDS SAY WHAT TO TYPE AND WHERE IT LEADS (the owner, 24 October
     2026: "The homepage searchbar should be phrased a bit better so folks
     know what they should be searching for and where the searchbar can take
     you to"), and name only what it reaches: find.json's rows -- legislators
     sitting and gone, committees, towns and their wards, the subjects bills
     are filed under, the how-to guides and the Learn pages -- and the bills,
     by number, and by the words of their titles on /search. It finds no
     statute: the Laws page has its own search. -->
<div class="searchbig" role="search">
  <label for="hq" style="position:absolute;left:-9999px">{say(lang, "home.search_label", "Search for a bill, a legislator, a committee, a town, a subject or a guide")}</label>
  <input id="hq" type="search" autocomplete="off" aria-controls="hqout"
    aria-describedby="hqhint" placeholder="{esc(say(lang, "home.search_hint", "Bill number, topic, name or town"))}">
  <button id="hgo">{icon("search")}{say(lang, "search.go", "Search")}</button>
  <div class="findout hqdrop" id="hqout" role="region" aria-label="{esc(say(lang, "search.top", "Top results"))}" hidden></div>
</div>
<p class="hqhint" id="hqhint">{say(lang, "home.try", "Try <b>HB 1</b>, <b>housing</b>, <b>Concord</b> or a legislator&rsquo;s name. It finds bills since 1989, legislators past and present, committees, towns and who represents them, subjects and how-to guides.")}</p>
<p class="sr" id="hqsay" role="status"></p>
<!-- THE WEBINAR UNDER THE SEARCH (the owner, 24 October 2026: "Could you
     move the webinar below the search bar?"): the search is what the page
     is for, and the box that retires on 11 November stands under it. -->
{home_webinar(lang=lang)}
<!-- EACH CARD WITH ITS SECTION'S DRAWING, the nav's own (Polish 1, 9 October
     2026): Bills, Officials, Laws and Resources since 17 October 2026
     (HOME_CARDS says why). -->
{home_cards(lang)}
<!-- COMMON QUESTIONS, under the cards (the person, 18 October 2026: "a sort
     of top 3-5 guides for the most common inquiries"): a few guides, each by
     its title over a line saying what a reader will learn there, and All
     guides. Filled by build_civics, which knows which guides passed their
     checks; empty while build_civics.HOME_GUIDES is off. -->
{guides}
</div>
<section class="hside hleft" aria-label="{esc(say(lang, "home.left", "Where the General Court is, and its latest session days"))}">
<div id="state">{static_state}</div>
<div id="session">{static_sessions}</div>
</section>
<!-- WHAT IS COMING UP OVER WHAT HAS JUST HAPPENED (the owner, 24 October
     2026: "if the coming up and latest activity sections are going to use
     similar formats, we could swap the recent session days section with
     coming up so they're stacked on top of each other on the right side
     which shows you what's coming up and what just happened more
     continuously"). The two are one format now, a day and its meetings'
     cards, so the right column reads forward and back from the present: the
     week ahead, then the rebuild line -- drawn only to warn that the data
     is stale or a step failed, the footer saying when it was rebuilt (25
     October 2026) -- then the latest meetings. The line to the latest
     sittings' recordings, with the status, is on the left. Below 1180px the
     same order: the hero, the search and the cards, the status, the
     recordings' line, Coming Up, the rebuild line and Latest Activity. -->
<section class="hside hright" aria-label="{esc(say(lang, "home.right", "What is coming up, and what has just happened"))}">
<div id="upcoming">{static_up}</div>
<div id="fresh" class="fresh"></div>
<div id="recent" class="hrecent">{static_recent}</div>
</section>
</div>
<div id="notable" hidden></div>"""


def home_js(lang="en", today=None, events=None):
    """HOME_JS for the home page in `lang`. Its words are tr()'s, which the
    page's head carries; the status box's way to the legislature's year,
    which the script carries as HTML, is put in `lang` here, with the next
    deadline above it (deadline_line), as the built box has them."""
    return HOME_JS.replace(YEAR_LINK, deadline_line(lang, today, events) + year_link(lang), 1)


HOME_JS = """
<script>
// The day without its year where the year goes without saying ("Oct 7" in
// Latest activity), and with it for the status box: out of session, the last
// floor day and the summary's date can be months back, and across a new year
// "Aug 19" is ambiguous. components.js's dateWords() writes both, and the
// server-rendered copy below writes the same with shell.date_words().
// In the page's language: window.GR_LANG on a Spanish page, English
// where it is not set.
const fd=d=>dateWords(d||"","short",window.GR_LANG);
const fdy=d=>dateWords(d||"","medium",window.GR_LANG);
// THE RECORD'S OWN WORDS on a page in another language are marked English
// (i18n.py): a bill's title and the line of its history.
const REC=window.GR_LANG&&window.GR_LANG!=="en"?' lang="en"':"";
// LATEST ACTIVITY'S DAYS, IN THE READER'S CLOCK (24 October 2026). The box is
// the build's, and a build stands for a day or more: a day it called
// "yesterday" is two days back by the next evening. Each day carries its date,
// and this says how long ago it was as build_pages.past_rel does -- "today",
// "yesterday", "3 days ago", nothing past a fortnight -- from the day the
// reader is in, as Coming up's days say "tomorrow". Not from home.json, so it
// holds with the fetch failing.
const latRel=(d,now)=>{
  const p=String(d||"").split("-").map(Number);
  const off=Math.round((now-new Date(p[0],p[1]-1,p[2]))/86400000);
  return off===0?tr("cal.today","today"):off===1?tr("cal.yesterday","yesterday")
    :off>1&&off<=14?tr("cal.days_ago","{n} days ago",{n:off}):"";
};
document.querySelectorAll("#recent .calday[data-d]").forEach(el=>{
  const rel=el.querySelector(".cdrel");
  if(rel)rel.textContent=latRel(el.dataset.d,new Date(new Date().setHours(0,0,0,0)));});
// If the nightly build stops running, nobody should be reading month-old data
// believing it is current. THIS LINE SPEAKS ONLY THEN (the audit of 25 October
// 2026, M8: "Data rebuilt" stood under Coming up and again in the footer).
// The footer says when every page's data was rebuilt (chrome.FOOT_JS); this
// says it again only as a warning -- three days old or more, or a step of the
// build failed -- which the footer's date alone does not give.
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
  if(days<3&&!failed.length)return;
  const when=new Date(B.finished).toLocaleString(window.GR_LOCALE||"en-US",
    {month:"short",day:"numeric",hour:"numeric",minute:"2-digit"});
  let msg=days>=3?tr("fresh.stale","Data last rebuilt {when} — {days} days ago",{when,days})
    :tr("fresh.rebuilt","Data rebuilt {when}",{when});
  if(failed.length)
    msg+=". "+(failed.length>1
      ?tr("fresh.failed_n","{n} build steps failed, so some sections may be incomplete.",{n:failed.length})
      :tr("fresh.failed_1","1 build step failed, so some sections may be incomplete."));
  el.className="fresh stale";
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
  const PHASE={"in session":["live",tr("state.in","In Session")],
               "veto day pending":["wait",tr("state.veto","Awaiting Veto Day")],
               "between sessions":["wait",tr("state.between","Between Sessions")],
               "out of session":["off",tr("state.out","Out of Session")]};
  const ph=PHASE[(S.phase||"").toLowerCase()]||["off",S.phase||tr("state.unknown","Status unknown")];
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
        ${S.last_session?`<span class="statemeta">${tr("state.last","Last Session Day:")}
          ${fdy(S.last_session)}</span>`:""}</div>
      ${S.headline?`<p class="statehead"${REC}>${esc(S.headline)}</p>`:""}
      ${S.note?`<p class="statenote"${REC}>${esc(S.note)}</p>`:""}
      ${ms?`<p class="statenote"><b>${tr("state.next","Next:")} ${esc(ms.label)}</b>, ${fd(ms.date)}.
        ${esc(ms.note||"")}</p>`:""}
      ${stale?`<p class="statenote stalewarn" style="color:var(--st-veto)"
        data-updated="${esc(S.updated||"")}">${tr("state.stale","This summary was last updated {n} days ago and may be out of date.",{n:S.stale_days})}</p>`
        :(S.updated?`<p class="statemeta upd" hidden data-updated="${esc(S.updated)}"></p>`:"")}
    """ + YEAR_LINK + """</div>`;
  // NO "WHO HOLDS OFFICE" HERE (23 October 2026). The Governor and the
  // Council were drawn under the calendar from home.json's composition,
  // read from a second hand file beside status.txt that was never filled
  // in, so the block never drew; the person retired that file, and who holds an
  // office is the Officials page's, from corrections/officials.json. The
  // chambers and the vacant seats are the legislators page's.

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
  // FROM SATURDAY, NEXT WEEK (D13): on a Saturday or a Sunday in the
  // reader's clock the rail is the coming Monday's week, Monday to Sunday,
  // and its name says so; on a weekday it is today to Sunday, and its name
  // says This Week again for a rail built at the weekend.
  (function(){
    const now=new Date(); now.setHours(0,0,0,0);
    const dow=now.getDay(),ahead=dow===6||dow===0;
    const from=ahead?(dow===6?2:1):0,to=ahead?from+6:(7-dow)%7;
    // COMING UP'S OWN DAYS: Latest Activity's are days of the same class,
    // all of them past, and this would take every one of them away.
    const days=[...document.querySelectorAll(".cal .calday[data-d]")];
    let left=0;
    days.forEach(d=>{
      const p=d.dataset.d.split("-").map(Number);
      const off=Math.round((new Date(p[0],p[1]-1,p[2])-now)/86400000);
      if(off<from||off>to){d.remove();return;}
      left++;
      const rel=d.querySelector(".cdrel");
      // `off<=14`, as the built labels have it: a week's days never reach
      // it, and a bound that matched them was the point -- `off<14` once left
      // the last day of a fortnight with no label at all.
      if(rel)rel.textContent=off===0?tr("cal.today","today"):off===1?tr("cal.tomorrow","tomorrow")
        :off<=14?tr("cal.in_days","in {n} days",{n:off}):"";
    });
    const cal=document.querySelector(".cal");
    const name=cal&&cal.querySelector&&cal.querySelector(".calwk .chip");
    if(name&&cal.dataset&&cal.dataset.mon){
      const p=cal.dataset.mon.split("-").map(Number);
      const off=Math.round((new Date(p[0],p[1]-1,p[2])-now)/86400000);
      // The rail's Monday against the reader's: this week's is 0 to 6 days
      // back, next week's 1 to 7 days on.
      // AND AN EMPTY RAIL'S SENTENCE WITH IT (the preview check of 25
      // October 2026): built on a Sunday and read on the Monday, the chip
      // said This Week and the note under it "... scheduled next week.", in
      // calendar_html's words for the day it was built. The sentence names
      // the same week as the chip, so it is said again with it, in the same
      // words; the season's sentence after it does not change with the day.
      const none=cal.querySelector(".calnomeet");
      if(off<=0&&off>-7){
        name.textContent=tr("cal.this_week","This Week");
        if(none)none.textContent=tr("cal.none_left","No House or Senate committee meetings are scheduled for the rest of this week.");
      }else if(off>0&&off<=7){
        name.textContent=tr("cal.next_week","Next Week");
        if(none)none.textContent=tr("cal.none_next","No House or Senate committee meetings are scheduled next week.");
      }
    }
    if(cal&&days.length&&!left){
      // The line under the rail stays: it is the way to the full calendar,
      // which is the useful thing to offer under an empty week.
      const more=cal.querySelector(".calall");
      // In calendar_html's words for an empty week: the rail holds the
      // chambers' own meetings, not the study committees.
      cal.innerHTML=`<h2>${tr("cal.coming","Coming up")}</h2><p class="note">${tr("cal.none_else","No more House or Senate committee meetings are scheduled this week.")}</p>`
        +(more?more.outerHTML:"");
    }
    // "Last updated N days ago" is the one line whose whole job is to say the
    // summary may be stale; it cannot be a number frozen at build time. A
    // fresh summary says nothing about its date (the person, 25 October
    // 2026), so the line shows only as the warning.
    const up=document.querySelector(".statebox .upd,.statebox .stalewarn");
    if(up&&up.dataset.updated){
      const p=up.dataset.updated.split("-").map(Number);
      const age=Math.round((now-new Date(p[0],p[1]-1,p[2]))/86400000);
      if(age>45){
        up.className="statenote stalewarn";
        up.style.color="var(--st-veto)";
        up.hidden=false;
        up.textContent=tr("state.stale","This summary was last updated {n} days ago and may be out of date.",{n:age});
      }else{
        up.className="statemeta upd";
        up.style.color="";
        up.hidden=true;
        up.textContent="";
      }
    }
  })();

  // #recent IS NOT TOUCHED HERE EITHER (24 October 2026). Latest Activity is
  // drawn into the page by build_pages' recent_box, a meeting an item, with
  // what was done to each bill in the site's words for it, which this script
  // does not carry; drawn again here from home.json it would be the second
  // renderer the calendar's comment above warns of. Its days are said again
  // in the reader's own clock, below (latWhen), as Coming up's are.

  // Closest votes and most contested are computed and stored, but not shown.
  // Both invite a reading the site does not want to make, and the page is
  // better without them for now.
  const cl=[], co=[];
  document.getElementById("notable").innerHTML=
    `${cl.length?`<h2>Closest floor votes</h2><table><tbody>${cl.map(v=>
      `<tr><td style="width:86px"><b>${v.y}\u2013${v.nn}</b></td>
       <td><a href="bills.html#${esc(v.bill)}">${esc(v.n)}</a>
       <span style="color:var(--ink-2)">${esc(v.q||"")}, ${fd(v.date)}</span><br>
       <span class="actw">${esc(v.title)}</span></td></tr>`).join("")}
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

  // #session IS NOT TOUCHED HERE (25 October 2026). The latest sittings
  // are one line the build writes (build_pages.session_line), where two
  // players were drawn from home.json.
});
// ONE BOX, THE HEADER'S FINDER (D13): find.js's findDraw, given this box's
// ids, draws the header panel's rows into the box's dropdown -- the same
// matcher, the same order, the same rows, so the two boxes cannot disagree.
// find.js is deferred, so it is asked for when a reader types, not now.
// GO IS SEARCH HERE (the webinar's phone check, 16 October 2026; the person
// approved it). This box has a Search button, and Return or a phone's Go key
// took the first row instead, as the header's finder does: "housing" opened
// the House Housing committee where the reader wanted the housing bills. So
// Return does what the button does -- every result (/search), and with
// nothing typed the bill search, as it always did -- except for a bill
// number, which opens the bill as in the header (find.js's findBill: the
// person's rule of 12 October). A row is still one tap away.
const HQ={out:"hqout",box:"hq",clear:"",say:"hqsay"};
const hq=document.getElementById("hq"),hqout=document.getElementById("hqout");
// ABOVE THE KEYBOARD. On a phone this box stands most of the way down the
// first screen, and the keyboard covered the rows it opens; as they first
// appear, the box is brought up to the top of the window.
function hqLift(){
  if(!(window.matchMedia&&matchMedia("(max-width:45em)").matches))return;
  const top=hq.getBoundingClientRect().top;
  if(top>80)window.scrollBy({top:top-16,behavior:"smooth"});
}
function hqDraw(){
  const v=hq.value;
  if(!v.trim()||typeof findDraw!=="function"){hqout.hidden=true;return;}
  const opening=hqout.hidden;
  hqout.hidden=false;
  findDraw(v,HQ);
  if(opening)hqLift();
  findRows().then(()=>{if(hq.value===v&&!hqout.hidden)findDraw(v,HQ);});
}
// Half an emoji is not an address (find.js, _fwell).
const hqAddr=v=>{v=(v||"").trim();return v?"/search?q="+encodeURIComponent(
  v.replace(/[\\uD800-\\uDFFF]/gu,"\\uFFFD")):"/bills";};
hq.addEventListener("input",hqDraw);
hq.addEventListener("focus",()=>{if(hq.value.trim())hqDraw();});
hq.addEventListener("keydown",e=>{
  if(e.key==="Escape"){hqout.hidden=true;return;}
  if(e.key!=="Enter")return;
  e.preventDefault();
  const first=hqout.hidden?null:hqout.querySelector("a");
  const bill=typeof findBill==="function"&&findBill(hq.value);
  location.href=first&&bill?first.href:hqAddr(hq.value);
});
document.getElementById("hgo").addEventListener("click",()=>{location.href=hqAddr(hq.value);});
// Away from the box, the dropdown closes; "Did you mean" searches again here.
document.addEventListener("click",e=>{
  const d=e.target.closest&&e.target.closest("#hqout .fdym");
  if(d){e.stopPropagation();hq.value=d.dataset.find;hqDraw();hq.focus();return;}
  if(!(e.target.closest&&e.target.closest(".searchbig")))hqout.hidden=true;
},true);
</script>"""
# The home page loads no app.js. Its script draws with components.js's esc and
# dateWords, which every page loads in its head.


def sitting_days():
    """{(body, date)}: the sittings build_session_pages.py writes a page for.

    Asked of that step's own rule and not read off the disk: it runs after
    this one, so on a machine that starts empty there is no page to find yet.
    Empty where narratives.json is not here, which is where that step writes
    nothing either.
    """
    import session_days
    if not Path(session_days.NARRATIVES).exists():
        return set()
    import build_session_pages
    return set(build_session_pages.sittings()[0])


# THE HOME PAGE'S CARDS (the person, 17 October 2026: "Switch out the
# committees card on the home page for the officials page", and "a card or
# some other way to link to laws on the homepage other than the nav"). Four,
# in the nav's order: the bills, the laws they change, who represents you,
# and the guides and explainers. The Committees card goes -- its count of
# committees with a roster, counted for it since 10 October, goes with it,
# and the Committees tab in the nav is the way there -- and Officials takes
# its place, because "who represents my town" is what more readers arrive
# asking. Two abreast in the middle column, one above the other on a phone.
#
# THE CONSTITUTION ON THE LAWS CARD (the person's request, carried out 18
# October 2026, once the Laws page had its Constitution tab). The card names
# it first and links its tab -- /laws#constitution, constitution_tab.TABS'
# address -- beside the card's own way to the statutes: the whole card opens
# /laws, as every card opens its page, and "The Constitution" in its line
# opens the tab. Only while the Laws page carries that tab: a card says what
# the page holds, not what it will.
HOME_CARDS = (
    ("/bills", "bill", "Browse Bills",
     "Search by committee, topic, sponsor, status or the day it was voted on"),
    ("officials.html", "person", "Officials",
     "Who represents your town, and every legislator&rsquo;s bills and votes"),
    ("laws.html", "law", "Laws",
     "Every New Hampshire statute, by number or subject, with the bills that would change it"),
    ("resources.html", "book", "Resources",
     "How-to guides, how the legislature works, and official sources"),
)
CONSTITUTION_HREF = "/laws#constitution"


def card_words(lang="en"):
    """{href: (name, line)} of HOME_CARDS in `lang`. The English is written
    again here so its translation can be checked against it; preflight holds
    it to HOME_CARDS's, word for word (_translations)."""
    return {"/bills": (say(lang, "card.bills", "Browse Bills"),
                       say(lang, "card.bills_line", "Search by committee, topic, sponsor, "
                           "status or the day it was voted on")),
            "officials.html": (say(lang, "card.officials", "Officials"),
                               say(lang, "card.officials_line", "Who represents your town, "
                                   "and every legislator&rsquo;s bills and votes")),
            "laws.html": (say(lang, "card.laws", "Laws"),
                          say(lang, "card.laws_line", "Every New Hampshire statute, by number "
                              "or subject, with the bills that would change it")),
            "resources.html": (say(lang, "card.resources", "Resources"),
                               say(lang, "card.resources_line", "How-to guides, how the "
                                   "legislature works, and official sources"))}


def _laws_has_constitution():
    """Whether the Laws page carries its Constitution tab."""
    import constitution_tab
    return any(pid == "constitution" for pid, _name in constitution_tab.TABS)


def home_cards(lang="en"):
    """The .entry block of the home page: HOME_CARDS, each with its section's
    drawing (the nav's own, Polish 1), in `lang`. The Laws card, while the
    Laws page carries the Constitution, is a card with two links (.ecard):
    the card itself to /laws and "The Constitution" to its tab, the inner
    link above the card's, so each answers its own click."""
    out = []
    words = card_words(lang)
    # THE LAWS CARD IS ONE LINK AGAIN (the person, 22 October 2026: "Remove
    # the constitution hyperlink on the homepage laws card"); the Laws page
    # keeps its Constitution tab.
    for href, ic, _name, _line in HOME_CARDS:
        name, line = words[href]
        to = href if lang == i18n.DEFAULT else i18n.href(lang, href)
        out.append(f'  <a href="{to}">{icon(ic)}<b>{name}</b><span>{line}</span></a>\n')
    return '<div class="entry">\n' + "".join(out) + "</div>"


# THE COLUMNS, SET APART (the person, 17 October 2026: "It would be good if
# the columns on the homepage could be a bit more differentiated because
# there's a lot of information to look at and it doesn't feel very
# segmented"). Three treatments were drawn, each a class on .hcols whose
# rules are in app.css beside the three-column grid, and the one in use is
# HOME_COLUMNS: another is this one line. None moves a column (the layout is
# settled, homepage-three-column-is-settled), touches the hero's logo, or
# tints a band across the page (the person's "no pale pine band", 8 October).
#   panels    each side column is a sheet of its own; the hero on the ground
#   rules     rules between the columns, and each section under a heavy rule
#   sections  each block of the side columns is its own card
# "panels" is the one recommended: it sets the two rails apart from the hero
# at a glance, in light and dark, and on a phone each block becomes a card.
HOME_COLUMN_OPTIONS = {"panels": "hv-panels", "rules": "hv-rules", "sections": "hv-sections"}
HOME_COLUMNS = "panels"


# THE BROWSER'S FILES, as this step puts them in the site: copied from
# src/pages/, and bills.html first because it is also the template every
# record page is made from (shell.template) -- which is why front_end.py,
# the fast path, takes a change to it to a full build and the others not.
# components.js before app.js, the order every page loads them in.
# print.js and print.css are a bill's print sheet, which a bill's page
# loads when its Print button is pressed (print.js, GRPrint.open).
def bills_page(t):
    """The bill search as published at /bills, from the template (the SEO
    review of 12 October 2026). Its title named the site and never the word
    "bills"; its canonical and og:url named /bills.html, which redirects; and
    to a reader without scripts it was nineteen characters. So the title says
    what the page is, every address is the one the host serves, and the page
    carries a plain paragraph and the way to every bill as a plain list,
    hidden under html.js as a record page's static record is."""
    t = _shell.clean_links(chrome.fill(t, "bills.html")).replace(
        'content="https://graniterecord.org/bills.html"', 'content="https://graniterecord.org/bills"')
    t = t.replace(_shell.NEEDS["title"],
                  "<title>New Hampshire Bills \u2014 search every bill since 1989 | Granite Record</title>", 1)
    plain = ('<div class="static-rec" id="static-rec"><p class="sx-name">New Hampshire Bills</p>'
             "<p>Every bill filed in the New Hampshire General Court since 1989, searchable by "
             "number, subject, sponsor, committee and status, each with its votes, hearings and "
             "history. Searching needs JavaScript; without it, "
             '<a href="/directory">the directory</a> lists every bill by term, each linking '
             "to its own page.</p></div>")
    slot = '<div id="results"></div>'
    assert slot in t, "bills.html has no results slot"
    return t.replace(slot, plain + slot, 1)


COPIED = ("bills.html", "app.css", "components.js", "app.js", "find.js",
          "print.js", "print.css")


def published_js(name, text):
    """A browser script's text as the site publishes it: components.js with
    the words written between its markers (with_words), and every script
    without its comments (strip_js.published, which publishes one as it is,
    and says so, where its reader refuses it). What front_end() writes, and
    what preflight holds the site's copy to (_published_scripts_stripped);
    build_district_map.py writes map.js through strip_js.published itself,
    since it has no words."""
    if name == "components.js":
        text = with_words(text)
    return strip_js.published(name, text)


def header_mark_placed(brand=Path("assets")):
    """Whether main() places HEADER_MARK: it is a file in assets/ or in
    assets/licensed/, which main() lays over it. What front_end.py asks,
    with assets/ as the full build left it, to write what main() wrote."""
    brand = Path(brand)
    return brand.is_dir() and ((brand / HEADER_MARK).is_file()
                               or (brand / "licensed" / HEADER_MARK).is_file())


def front_end(out, has_mark):
    """Everything this step makes of the browser's files and of nothing else:
    the files it copies (COPIED) and billmatch.js. Returns the names it wrote
    whose bytes changed, and style.css where it took an old build's away.

    ONE FUNCTION FOR THE BUILD AND THE FAST PATH (9 October 2026). main()
    calls it, and so does `build_all.py --front-end` (front_end.py), which
    puts a change to app.css, components.js, app.js or find.js into the
    site the last full build made -- so what the fast path writes is what
    this step writes,
    because it is this step's code. A file added to what this step derives
    from the browser's files goes here, or the fast path will not know it.
    """
    out = Path(out)
    wrote = []
    # THERE IS NO style.css (23 October 2026): every page links app.css. A
    # site folder an earlier build wrote one into would publish it unused.
    stale = out / "style.css"
    if stale.exists():
        stale.unlink()
        wrote.append("style.css")
        print("took the old style.css out of the site folder: no page links it")

    # bills.html and the files it loads are written by hand rather than
    # generated, and nothing in the pipeline copied them into the output
    # folder -- so an edit sat in the code while the deploy shipped
    # whatever was in site/, which looks exactly like the edit having no
    # effect and cost a round more than once. app.css and app.js are files of
    # their own rather than a <style> and a <script> inside the page, so a
    # second page loads the SAME renderer and a reader who opens six bills
    # downloads 110 KB once instead of six times.
    #
    # Copied as they are, but for these. The version query they used to gain
    # is a header now (HEADERS). app.css goes into the site without its
    # comments (strip_css), and where the build has no header mark, without
    # the block that draws it (without_mark). components.js gains the words
    # between its markers (with_words), so they are written once, in
    # src/pages/words/. And every script goes without its comments
    # (published_js, strip_js.py), as app.css does.
    for name in COPIED:
        src = Path("src/pages") / name
        if not src.exists():
            continue
        dst = out / name
        body = src.read_bytes()
        if name == "app.css":
            body = strip_css((body if has_mark else without_mark(body)).decode("utf-8")).encode("utf-8")
        if name.endswith(".js"):
            body = published_js(name, body.decode("utf-8")).encode("utf-8")
        # THE PAGE IS CLEANED, THE TEMPLATE IS NOT. src/pages/bills.html is
        # also the template every record's page is made from, and shell.page
        # finds its tabs by their written addresses ("officials.html"), so
        # it keeps them; the copy published as /bills gets the addresses the
        # host serves (shell.clean_links), its og:url among them.
        if name == "bills.html":
            body = bills_page(body.decode("utf-8")).encode("utf-8")
        if not dst.exists() or dst.read_bytes() != body:
            dst.write_bytes(body)
            wrote.append(name)
            print(f"copied {name} into the site folder")

    # The bill matcher, cut out of app.js for the header search on the pages
    # that do not load app.js. See bill_matcher_js.
    if Path("src/pages/app.js").exists():
        body = published_js("billmatch.js", bill_matcher_js(
            Path("src/pages/app.js").read_text(encoding="utf-8"))).encode("utf-8")
        dst = out / "billmatch.js"
        if not dst.exists() or dst.read_bytes() != body:
            dst.write_bytes(body)
            wrote.append("billmatch.js")
            print("  billmatch.js: app.js's bill matcher, for the header "
                  "search")
    # THE SHARED SCRIPTS' WORDS, for each language the site is built in
    # (i18n.SHARED_SCRIPTS): what components.js and find.js ask tr() for, in
    # that language, which a page in it loads in its head. Here, beside the
    # files themselves, so the fast path writes them when either moves.
    shared = [(Path("src/pages") / n).read_text(encoding="utf-8")
              for n in i18n.SHARED_SCRIPTS if (Path("src/pages") / n).exists()]
    for lang in i18n.LANGS:
        if lang == i18n.DEFAULT:
            continue
        # And the glossary's, which the term pop-ups on every page read
        # (i18n.gloss_js; the owner, 24 October 2026).
        body = (i18n.words_js(lang, *shared) + "\n" + i18n.gloss_js(lang) + "\n").encode("utf-8")
        dst = out / i18n.shared_words_path(lang).lstrip("/")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or dst.read_bytes() != body:
            dst.write_bytes(body)
            wrote.append(dst.relative_to(out).as_posix())
            print(f"  {dst.relative_to(out).as_posix()}: the shared scripts' words in {lang}")
    return wrote


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    # THE DRAWN FILES. brand/ holds the originals, build_brand.py derives
    # assets/, and this is the step that puts them beside the pages -- site/
    # is generated and gitignored, so anything left there by hand is gone on
    # the next build. None of the images is in the repository (BRAND_FILES
    # above says why), so on a clone this places the manifest and nothing
    # else, says so once, and the build carries on.
    brand = Path("assets")
    placed, moved, n_lic = set(), 0, 0
    if brand.is_dir():
        # THE LICENSED LOGO GOES OVER THE CLIPART. assets/licensed/ holds what
        # build_brand.py draws from Debra Caplan's lockups; it is gitignored,
        # because the person asked that her files never be in the public
        # repository, so it exists only on a machine that has them. Where it
        # does, its files replace the clipart copies of the same name (the home
        # page's lockup, the link cards); the favicon and tab icons are not in
        # it and stay the clipart, which reads better at small sizes. The
        # header's mark is in it and has no clipart twin, so it arrives by the
        # second loop or not at all.
        licensed = brand / "licensed"
        over = {f.name: f for f in sorted(licensed.iterdir()) if f.is_file()} \
            if licensed.is_dir() else {}
        for f in sorted(brand.iterdir()):
            if not f.is_file():
                continue
            dst = out / f.name
            b = over.pop(f.name, f).read_bytes()
            placed.add(f.name)
            if not dst.exists() or dst.read_bytes() != b:
                dst.write_bytes(b)
                moved += 1
        for name, f in over.items():
            dst = out / name
            b = f.read_bytes()
            placed.add(name)
            if not dst.exists() or dst.read_bytes() != b:
                dst.write_bytes(b)
                moved += 1
        n_lic = len([p for p in licensed.iterdir() if p.is_file()]) if licensed.is_dir() else 0
        # THE EMAILS' COPY OF THE MARK (build_brand.mail_mark): the same ink
        # on a white tile, which a mail app's dark mode cannot hide. Made
        # here, from the mark just placed, so the kit carries nothing new.
        # Pillow is the one thing it needs that the rest of this file does
        # not; where it is missing the file is not made, and check_site.py
        # refuses a site with the mark and without its copy.
        if HEADER_MARK in placed:
            import build_brand
            try:
                b = build_brand.mail_mark(out / HEADER_MARK)
            except ImportError:
                b = None
            dst = out / build_brand.MAIL_MARK
            if b:
                placed.add(build_brand.MAIL_MARK)
                if not dst.exists() or dst.read_bytes() != b:
                    dst.write_bytes(b)
                    moved += 1
    # WHAT THIS BUILD HAS, read off what it just placed and not off site/,
    # which is never emptied and may hold a logo from an earlier build.
    missing = [f for f in BRAND_FILES if f not in placed]
    has_lockup = "lockup.png" in placed
    has_mark = HEADER_MARK in placed
    no_brand = ""
    if missing:
        # ONE MESSAGE, AND THE BUILD CARRIES ON. A clone has no logo because
        # the logo is not in the repository, and that is not a failure of the
        # build: it is the state every fork starts in. check_site.py is what
        # refuses to publish a site without them.
        # SAID LAST, at the end of main(), not here. build_all.py shows a
        # step's last three lines, and this is the one thing about the step a
        # person on a clone needs to read; printed here it scrolled out of
        # that window and the build looked as if it had nothing to say.
        without = ["pages link icons that are not there"]
        if not has_lockup:
            without.append("the home page's heading is set as text")
        if not has_mark:
            without.append("the header is the wordmark alone")
        no_brand = (f"  brand: the logo and icons are not here -- {len(missing)} of "
                    f"{len(BRAND_FILES)} files are missing ({', '.join(missing)}). "
                    "They are not part of the open-source release; DATA.md says why. "
                    "To add your own, put a mark in brand/ and run python3 "
                    "build_brand.py, or put files of those names in assets/. The site "
                    "is built without them: " + ", ".join(without) + ".")
    else:
        print(f"  brand: {len(placed)} files from assets/"
              + (f", {n_lic} of them the artist's (assets/licensed/)" if n_lic
                 else ", none of them the artist's (no assets/licensed/ on this machine)")
              + f"; {moved} copied into the site folder"
              + ("" if has_mark else
                 f". No {HEADER_MARK} among them (build_brand.py draws it into "
                 "assets/licensed/ from the artist's drawing), so the header is "
                 "the wordmark alone"))
    front_end(out, has_mark)

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
        """"Aug 19", the form HOME_JS's fd() writes: shell.date_words."""
        return esc(_shell.date_words(d or "", "short"))

    # The five counts the home page drew here are gone, for the reason the
    # script's copy above gives. The data page still counts, which is where
    # counting belongs.

    def static_bar(ch, lang="en"):
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
        vac = say(lang, "comp.vacant", "Vacant")
        segs = "".join(
            f'<span class="pseg seg-{esc(pp["code"])}" '
            f'style="width:{100 * pp["n"] / tot:.4f}%" '
            f'title="{esc(party_word(pp["name"], lang))}: {pp["n"]}"></span>'
            for pp in x.get("parties", []))
        if x.get("vacant"):
            segs += (f'<span class="pseg seg-V" '
                     f'style="width:{100 * x["vacant"] / tot:.4f}%" '
                     f'title="{vac}: {x["vacant"]}"></span>')
        legend = "".join(
            f'<span><span class="pdot seg-{esc(pp["code"])}"></span>'
            f'{esc(party_word(pp["name"], lang))} <b>{pp["n"]}</b></span>'
            for pp in x.get("parties", []))
        if x.get("vacant"):
            legend += (f'<span><span class="pdot seg-V"></span>{vac} '
                       f'<b>{x["vacant"]}</b></span>')
        note = ""
        if x.get("majority"):
            # A bill passes with a majority of the members VOTING, so there is
            # no fixed number to print for it; "a simple majority is 201" was
            # a majority of the 400 seats, which decides nothing. Three fifths
            # is of the members in office, counted from the roster, and the
            # sentence says which count it is.
            tt = x.get("two_thirds_note", "")
            if lang != i18n.DEFAULT and tt == "two thirds of those voting, so it moves with turnout":
                tt = say(lang, "comp.two_thirds", "two thirds of those voting, so it moves with "
                         "turnout")
            note = ('<p class="statemeta" style="margin:6px 0 0">'
                    + say(lang, "comp.note", "A bill passes with a majority of the members "
                          "voting. Passing a constitutional amendment takes three fifths of the "
                          "members in office: {three} of the {sitting} on the current roster. A "
                          "veto override needs {two}.", three=x.get("three_fifths", ""),
                          sitting=x["sitting"], two=esc(tt))
                    + "</p>")
        chamber = {"House": say(lang, "comp.house", "House"),
                   "Senate": say(lang, "comp.senate", "Senate")}.get(x["chamber"], x["chamber"])
        filled = (say(lang, "comp.filled_vacant", "{sitting} of {seats} seats filled, {vacant} "
                      "vacant", sitting=x["sitting"], seats=x["seats"], vacant=x["vacant"])
                  if x.get("vacant") else
                  say(lang, "comp.filled", "{sitting} of {seats} seats filled",
                      sitting=x["sitting"], seats=x["seats"]))
        return (f'<div class="comp"><div class="compline"><b>{esc(chamber)}</b>'
                f'<span class="statemeta">{filled}</span>'
                f'</div><div class="pbar2">{segs}</div>'
                f'<div class="plegend">{legend}</div>{note}</div>')

    def vacancies_box(lang="en"):
        if not C.get("vacancies"):
            return ""
        v = C["vacancies"]
        # HOW A SEAT IS FILLED, FROM THE STATUTE (the person, 7 October 2026,
        # F7). The sentence said every vacancy is filled by special election,
        # and RSA 661:8, II says a House seat is only if the town or city asks
        # the Governor and Council to call one. VACANCY_NOTE is the wording
        # agreed in private/FRONTEND_FEEDBACK.md. And "District" takes its
        # capital, as a district's name does everywhere else on the site
        # ("Grafton District 6", F6).
        # VACANCY_NOTE's words, said in the page's language; preflight's
        # _spanish_officials holds the two the same.
        note = say(
            lang, "comp.vacancy_note", "Seats fall vacant during a term when members resign or "
            "die. A House seat is filled by special election only if the town or city asks the "
            "Governor and Executive Council to call one, so some stay vacant until the next "
            "general election. A Senate seat is filled as the state constitution provides.")
        return (
            '<details class="vac"><summary>'
            + say(lang, "comp.vacant_seats", "{n} vacant House seats across {d} districts",
                  n=sum(x["vacant"] for x in v), d=len(v))
            + f'</summary><p class="note" style="margin-top:8px">{note}</p>'
            '<div class="grid">' + "".join(
                '<div class="mem">'
                + say(lang, "comp.county_district", "{county} District {district}",
                      county=esc(x["county"]), district=esc(x["district"]))
                + (" " + say(lang, "comp.n_seats", "— {n} seats", n=x["vacant"])
                   if x["vacant"] > 1 else "") + "</div>"
                for x in v) + "</div></details>")

    def roster_section(legs, lang="en"):
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
        representative's license plate carries it.
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
        def alpha_block(ms, heading):
            groups = {}
            for m in ms:
                groups.setdefault((m.get("party") or "Party not on file").strip(), []).append(m)
            cols = []
            for party, pm in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
                # Surname, then given name: the seat order it once fell back on
                # put Michael Aron above Judy Aron and three Smiths out of order.
                pm = sorted(pm, key=lambda m: (surname(m), given(m)))
                name = party_word(party, lang, plural=len(pm) != 1)
                cols.append(f'<section class="pcol"><h3>{esc(name)} &mdash; {len(pm)}</h3>'
                            '<ol class="seatlist rlist">'
                            + "".join(li(m, "") for m in pm) + "</ol></section>")
            return (f'<h2>{heading} &mdash; {len(ms)}</h2>'
                    '<div class="partycols">' + "".join(cols) + "</div>")
        by_last = (alpha_block(S, say(lang, "comp.senate", "Senate"))
                   + alpha_block(H, say(lang, "comp.house", "House")))
        by_seat_rows = seat_columns(
            H, lambda m: li(m, seating.plate(m["seat"]) if m.get("seat") else ""), lang)
        senate_rows = "".join(li(m, say(lang, "off.district", "District {d}", d=m.get("district")))
                              for m in S)

        seats_said = (say(lang, "roster.filled_vacant", "{seated} of the 400 seats are filled and "
                          "{vacant} are vacant.", seated=seated, vacant=vacant) if vacant else
                      say(lang, "roster.filled", "{seated} of the 400 seats are filled.",
                          seated=seated))
        return f"""<section class="roster" id="roster">
<div class="rtabs" role="tablist" aria-label="{say(lang, "roster.arrange", "How to arrange the roster")}">
  <button type="button" role="tab" id="tab-last" data-pane="pane-last"
    aria-controls="pane-last" aria-selected="true">{say(lang, "roster.by_last", "By last name")}</button>
  <button type="button" role="tab" id="tab-county" data-pane="pane-county"
    aria-controls="pane-county" aria-selected="false">{say(lang, "roster.by_county", "By county")}</button>
  <button type="button" role="tab" id="tab-seat" data-pane="pane-seat"
    aria-controls="pane-seat" aria-selected="false">{say(lang, "roster.by_seat", "By seat")}</button>
</div>

<div class="rpane" id="pane-last" role="tabpanel" aria-labelledby="tab-last">
<p class="src">{say(lang, "roster.all", "All {n} sitting members, by surname, each chamber on\nits own.", n=len(legs))}</p>
{by_last}
</div>

<div class="rpane" id="pane-county" role="tabpanel" aria-labelledby="tab-county">
<div id="out"></div>
</div>

<div class="rpane" id="pane-seat" role="tabpanel" aria-labelledby="tab-seat">
<h2>{say(lang, "roster.where", "Where they sit")}</h2>
<p class="src">{say(lang, "roster.seat_about", "Every representative has a numbered seat in Representatives\nHall, and it is the number on their license plate. Tap a seat to see who is in\nit; tapping does not leave the page, and the name it gives you is the link. This is a diagram of the\nfive divisions, not a drawing of the room: it is faithful to which division a\nseat is in and to the seat&rsquo;s number, and not to the true distances.")}
{seats_said}
{say(lang, "roster.rostrum", "The Speaker&rsquo;s chair is on the rostrum rather than on the floor, so\n{empty} of the places drawn below are empty.", empty=empty_places)}</p>
<div class="seatctl">
  <label for="sgo">{say(lang, "roster.go", "Go to a seat")}</label>
  <select id="sgo"><option value="">{say(lang, "roster.seat_number", "Seat number&hellip;")}</option>{opts}</select>
  <label for="sq">{say(lang, "roster.find", "Find")}</label>
  <input id="sq" type="search" autocomplete="off"
    placeholder="{say(lang, "roster.find_ph", "Name, county or seat")}">
</div>
<div class="seatbar">
  <p class="seathint">{say(lang, "roster.hint", "Scroll or pinch to zoom, drag to move about the floor.")}</p>
  <div class="seatzoom">
    <button type="button" id="szout" aria-label="{say(lang, "roster.zoom_out", "Show more of the floor")}">&minus;</button>
    <button type="button" id="szin" aria-label="{say(lang, "roster.zoom_in", "Show the seats larger")}">+</button>
    <button type="button" id="szfit">{say(lang, "roster.fit", "Fit")}</button>
  </div>
</div>
<div class="seatstage">
  <div class="seatwrap">{seating.svg(by_seat, lang=lang)}</div>
  <p class="seatnote" id="seatnote" role="status" aria-live="polite"></p>
</div>
<div class="seatcols" id="seatlist">{by_seat_rows}</div>
<h2>{say(lang, "roster.senate", "The Senate")}</h2>
<p class="src">{say(lang, "roster.senate_about", "The Senate has no seating chart: its 24 members are elected\nfrom numbered districts and the chamber does not assign numbered seats the way\nthe House does.")}</p>
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
    #
    # TWO TABS, TOWNS AND LEGISLATORS (the person, 7 October 2026, F5): "divide
    # into a Towns section and a Legislators section", as tabs like the town
    # pages', because an interactive map of the state's districts is to come
    # and belongs with the towns. The finder is the Towns tab; the roster in
    # its three arrangements, who holds the seats and the vacancies are the
    # Legislators tab. The finder still matches a member's name as well as a
    # town, because the home page's box sends either here.
    #
    # The strip, the panels and the script are the town pages' own
    # (build_town_pages.TABS_JS, the .twntabs rules in app.css's shared
    # region): without JavaScript both panels are shown, each under its
    # heading; with it the strip shows, a panel's id is its address
    # (/legislators#legislators), and Back leaves the page.
    from build_town_pages import TABS_JS as TOWN_TABS_JS
    # THE LEAD IS THE PAGE'S, AND THE INSTRUCTION IS THE TOWNS TAB'S (the look
    # of 7 October 2026): "Type a town ... or a name" sat over both tabs and
    # described only the box in the first, so it moved into that panel, over
    # the box it is about.
    # THE OFFICIALS PAGE, FIVE TABS (Polish 3: the person's feedback of 9
    # October 2026, item 4, and decision 127; the approved drawing is
    # private/design/polish/proto/officials.html): My Town (the town finder
    # and the district map), Legislators (the roster, as it was), Federal
    # Delegation, Executive Branch, Judicial Branch and County Officials
    # (officials_tabs, from corrections/officials.json, read and never
    # written). Executive Branch was Statewide Officials until 17 October
    # 2026, when the person approved the rename, the department heads inside
    # it and a thin Judicial Branch tab beside it. The strip, the panels and
    # the script are still the town pages' (build_town_pages.TABS_JS):
    # without JavaScript every panel is on the page under its own heading;
    # with it, a panel's id is its address (/officials#federal), and the old
    # page's #towns opens My Town, as the old #statewide opens Executive
    # Branch (OFFICIALS_HASH_JS).
    import officials_tabs as OT
    # Through the file's one reader, which puts a successor in office on the
    # day the file gives (build_members_elect.read_officials, 23 October 2026).
    from build_members_elect import read_officials
    try:
        off = read_officials()
    except (OSError, ValueError):
        off = {}
    try:
        officers = json.loads((out / "officers.json").read_text(encoding="utf-8")).get("officers")
    except (OSError, ValueError, AttributeError):
        officers = []
    # A DEPARTMENT HEAD THE SITE ALREADY HAS (17 October 2026): the hand file
    # names a former member's page under `member`, and the head is drawn as
    # that member's chip only where the build has the page -- a sitting
    # member's, or one in former.json, which build_legislator_pages writes a
    # page for. A name it does not find is drawn plain, and said here, so a
    # renamed page does not quietly lose its link.
    try:
        gone = json.loads((out / "former.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        gone = []
    member_pages = {str(m.get("slug")) for m in [*legs, *gone] if m.get("slug")}
    for r in (off.get("department_heads") or {}).get("departments") or []:
        if r.get("member") and r["member"] not in member_pages:
            print(f"  officials.html: {r.get('name')}'s member page {r['member']} is not in "
                  "this build; drawn as a plain name")
    today = build_date.today().isoformat()
    # THE LAST TAB, MEMBERS-ELECT (the person's decisions of 16 October
    # 2026): who November's election sent, from site/members_elect.json alone
    # (build_members_elect.for_pages), between the election and Organization
    # Day. With no file the tab and its panel are not drawn and the page is
    # the page it was; with one, the tab, its panel and the panel's content
    # each carry data-elect and retire on the day they take office. And the
    # map's note under My Town says "its sitting members", as the town pages'
    # copy does, the year round (build_town_pages.map_section says why).
    from build_members_elect import for_pages as members_elect
    elect = members_elect(out)
    elect_attrs = (f" data-elect{until_attrs(elect['takes_office'], today)}"
                   if elect else "")
    # THE OLD ADDRESS GOES. /legislators is a 301 to /officials (decision
    # 127, MOVED). A legislators.html left in the folder by an earlier build
    # would be published beside the redirect, so it goes.
    old_page = out / "legislators.html"
    if old_page.exists():
        old_page.unlink()
        print("  legislators.html: removed; /legislators redirects to /officials")
    def officials_html(lang):
        """The Officials page in `lang`."""
        of_panes = [
            ("my-town", say(lang, "of.tab.town", "My Town"), None, f"""<div class="yt ytcard" data-yt="seats" hidden></div>
<section class="ofpart" aria-labelledby="of-find">
<h3 id="of-find">{say(lang, "of.find", "Find Your Town")}</h3>
<p class="src fill">{say(lang, "of.find_how", "Type a town to see who represents it, or a name, county,\nparty or committee to find a member.")}</p>
<div class="lfind">
  <label for="lq" class="sr">{say(lang, "of.find_label", "Your town, or a legislator&rsquo;s name")}</label>
  <input id="lq" type="search" autocomplete="off"
    placeholder="{say(lang, "of.find_ph", "Your town or a legislator")}" disabled>
  <p class="count" id="lcount">{say(lang, "of.loading", "Loading&hellip;")}</p>
  <p class="sr" id="lsay" role="status"></p>
  <div class="lmatch" id="lmatch"></div>
</div>
</section>
<section class="ofpart ofmap" aria-labelledby="of-map">
<h3 id="of-map">{say(lang, "of.map", "The Map")}</h3>
<p class="src fill">{say(lang, "of.map_how", "Choose a district to see who represents it. Zoom in for\na city&rsquo;s wards.")}</p>
<div class="ofmapbox" id="ofmap"></div>
<noscript><p class="note">{say(lang, "of.map_noscript", "The map needs JavaScript. Every town&rsquo;s districts\nare on its own page, listed in <a href=\"/directory/towns.html\">every town and\nward</a>.")}</p></noscript>
</section>"""),
            ("legislators", say(lang, "of.tab.legislators", "Legislators"), len(legs),
             OT.presiding(officers, legs, today, lang) + roster_section(legs, lang)
             + (('<div class="comp-wrap"><h2>' + say(lang, "of.who_holds", "Who holds the seats")
                 + "</h2>" + static_bar("S", lang) + static_bar("H", lang) + vacancies_box(lang)
                 + "</div>") if C else "")),
            ("federal", say(lang, "of.tab.federal", "Federal Delegation"),
             OT.count(off, "federal"), OT.federal(off, lang)),
            ("executive", say(lang, "of.tab.executive", "Executive Branch"),
             OT.count(off, "executive"), OT.executive(off, member_pages.__contains__, lang)),
            ("judicial", say(lang, "of.tab.judicial", "Judicial Branch"),
             OT.count(off, "judicial"), OT.judicial(off, lang)),
            # #counties, not #county: the roster's By county button is tab-county.
            ("counties", say(lang, "of.tab.counties", "County Officials"),
             OT.count(off, "county"), OT.county(off, legs, None, lang)),
            # "Members-Elect (N)", N the winners the file names: a race not
            # final counts none, and a tab of none says no number, as any tab.
            ("members-elect", say(lang, "of.tab.elect", "Members-Elect"), OT.elect_count(elect),
             OT.members_elect(elect, today, lang)),
        ]
        of_panes = [p for p in of_panes if p[3]]
        of_tabs = "".join(
            f'<button type="button" role="tab" id="tab-{pid}" data-pane="{pid}" '
            f'aria-controls="{pid}" aria-selected="{"true" if i == 0 else "false"}" '
            f'tabindex="{0 if i == 0 else -1}"{elect_attrs if pid == "members-elect" else ""}>{name}'
            + (f' <span class="ofn">({n:,})</span>' if n else "") + "</button>"
            for i, (pid, name, n, _h) in enumerate(of_panes))
        of_body = "".join(
            f'<div class="twnpane" id="{pid}" role="tabpanel" aria-labelledby="tab-{pid}"'
            f'{elect_attrs if pid == "members-elect" else ""}>'
            f'<h2 class="twnph">{name}</h2>{inner}</div>'
            for pid, name, _n, inner in of_panes)
        leg_body = f"""<h1>{say(lang, "of.title", "Officials")}</h1>
<p class="lead">{say(lang, "of.lead", "Everyone who represents your town, from your select board to\nCongress; the {n} sitting members of the New Hampshire House and\nSenate; and the state&rsquo;s other officials.", n=len(legs))}</p>
<div class="twntabs oftabs" role="tablist" aria-label="{say(lang, "of.title", "Officials")}" hidden>{of_tabs}</div>
{of_body}
{OFFICIALS_HASH_JS}{TOWN_TABS_JS}{OFFICIALS_MAP_JS}"""
        return shell(say(lang, "of.page_title", "Officials | Granite Record"), "officials.html",
                     i18n.lang_links(leg_body, lang),
                     desc=say(lang, "of.desc", "Who represents your town, from the State House to "
                              "Congress; every member of the New Hampshire House and Senate, with "
                              "their district, their party, the bills they sponsored and every "
                              "recorded vote they cast; and the state's and counties' elected "
                              "officials."),
                     wide=True, script=LEGFIND_JS + SEATING_JS, lang=lang)

    # THE PAGE IN EACH LANGUAGE IT HAS (i18n.PAGES; the person, 25 October
    # 2026: "Start on the Officials page and My Town in Spanish"), from the
    # same files: the English at /officials, the Spanish at /es/officials.
    # A name, a party letter, a phone number is the record's in both; what the
    # site says is in the page's language, and a link to a page the language
    # has goes to that page (i18n.lang_links).
    for lang in i18n.LANGS:
        if not i18n.has(lang, "officials.html"):
            continue
        dest = out / ("officials.html" if lang == i18n.DEFAULT
                      else i18n.href(lang, "officials.html").lstrip("/"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(officials_html(lang), encoding="utf-8")

    # THE KEY DATES, worked out once for both languages and both of the
    # boxes that show them: Coming up, and the status box's next deadline.
    # SILENCE IS NOT SUCCESS: a box with no deadline says why, here.
    import key_dates as KD
    today_d = build_date.today()
    kd_events = KD.events(today_d)
    if KD.no_deadline_line(kd_events, today_d):
        print(KD.no_deadline_line(kd_events, today_d))
    static_up = calendar_html(out, today=today_d, events=kd_events)

    # WHICH SITTINGS HAVE A PAGE: the line to the latest sittings'
    # recordings (session_line) leads to a sitting's page where one is
    # built, asked of the step that builds them (sitting_days).
    sits = sitting_days()
    # LATEST ACTIVITY'S WAYS INTO EACH MEETING: a committee's page by the
    # codes Coming up's cards link by, and a sitting's page where that step
    # writes one (the same `sits`).
    codes = committee_codes(out, data="data")
    if H.get("latest"):
        shown = H["latest"][:RECENT_SHOWN]
        print(f"  latest activity: {len(shown)} meetings shown, "
              f"{sum(1 for m in shown if latest_href(m, codes, sits))} of them linked")
    else:
        print("  WARNING: home.json holds no latest activity: the home page's box is empty")


    # THE GUIDES' ROW IS KEPT. build_civics fills the home page's guides slot
    # after this writes it (home_guides); a run of this step alone -- the
    # front end's fast path, or build_pages by hand -- keeps the row the last
    # full build put there rather than emptying it until the next night.
    prev = out / "index.html"
    kept = re.search(r"<!-- guides -->.*?<!-- /guides -->",
                     prev.read_text(encoding="utf-8"), re.S) if prev.is_file() else None
    # THE HOME PAGE IN EACH LANGUAGE IT HAS (i18n.PAGES; 23 October 2026),
    # from the same home.json and the same week's rows: the English at /,
    # the Spanish at /es/. What the record says is the record's words in
    # both; what the site says is in the page's language.
    for lang in i18n.LANGS:
        if not i18n.has(lang, "index.html"):
            continue
        home = home_body(lang, has_lockup, state_box(S, lang, today_d, kd_events),
                         static_up if lang == i18n.DEFAULT
                         else calendar_html(out, today=today_d, lang=lang, events=kd_events),
                         recent_box(H, lang, codes, sits), session_line(H, lang, sits))
        if lang == i18n.DEFAULT and kept:
            home = home.replace("<!-- guides --><!-- /guides -->", kept.group(0), 1)
        dest = (out / "index.html" if lang == i18n.DEFAULT
                else out / i18n.href(lang, "index.html").strip("/") / "index.html")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            shell(say(lang, "home.title", "Granite Record — New Hampshire government, in one place"),
                  # THE FULL PAGE WIDTH, which is what "offset to the left"
                  # was. .wrap is 820px aligned to the nav's own gutter, so on a
                  # 1440px screen the home page was an 820px column with 360px of
                  # empty ground to the right of it -- aligned, and unbalanced.
                  # wide=True makes it the 1180px the nav and every record page
                  # already use, so the stat grid and the three entry cards fill
                  # the width instead of stopping two thirds across.
                  "index.html", home, script=home_js(lang, today_d, kd_events), wide=True, lang=lang,
                  desc=say(lang, "home.desc", "Every bill, vote, hearing and floor debate of "
                           "the New Hampshire General Court, linked to the moment in the "
                           "recording where it happened.")),
            encoding="utf-8")
    i18n.report()
    KD.unnamed()

    # learn.html belongs to build_civics.py now: it is the way into eleven
    # topic pages rather than one page of its own, and two builders writing
    # the same address means whichever runs last wins. The old Learn prose,
    # LEARN, was redistributed into civics.py rather than rewritten, and was
    # deleted from here on 23 October 2026; git history keeps it, to diff
    # against if a passage there looks wrong.
    # THE FIGURES ARE COUNTED, NOT TYPED. about_figures.py says why at length:
    # the eight numbers this page used to state about its own accuracy were
    # written when the site held one term, and seven of them were wrong by the
    # time it held nineteen. fill() raises rather than publishing a sentence
    # with a hole where a number was.
    (out / "about.html").write_text(
        shell("About | Granite Record", "about.html",
              about_figures.fill(about_text().replace("__LOGO__", about_logo(has_lockup)),
                                 about_figures.figures(site=out)),
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
under, and every bill since 1989.</p>
<form class="resfind" action="/search" method="get" role="search">
  <label for="resq" class="sr">A legislator, a committee, a town, a subject or a bill</label>
  <input id="resq" name="q" type="search" autocomplete="off"
    placeholder="Name, town, committee or bill" disabled>
</form>
<div id="resout"></div>
<noscript><p class="note">This page needs JavaScript to search. Without it,
the <a href="/bills">bill search</a>, the <a href="/officials">roster</a> and
the <a href="/committees">committee list</a> are all plain pages.</p></noscript>"""
    # WIDE, as the roster is: a list of results is a list, and in the 820px
    # column of the prose pages it ended near the middle of a 1440px window
    # with the rest of the row empty (the review of 2 October 2026).
    search_page = shell("Search | Granite Record", "", search_body, wide=True,
                        desc="Search Granite Record for a legislator, a "
                             "committee, a town, a subject or a bill.",
                        script=SEARCH_JS)
    search_page = search_page.replace(
        '<link rel="canonical" href="https://graniterecord.org/">',
        '<meta name="robots" content="noindex,follow">')
    (out / "search.html").write_text(_shell.clean_links(search_page), encoding="utf-8")

    # THERE WAS NO 404 PAGE. Cloudflare Pages treats a project with no
    # top-level 404.html as a single-page app: every address it cannot find
    # is answered with the home page and a 200. A mistyped bill -- or a bill
    # number that exists in another year -- looked like a working page, and a
    # search engine would index the home page under every one of them.
    #
    # It is served AT the address that was asked for, so every link in it
    # must be absolute: from /bill/2026/hb99999 a relative "about.html" is
    # /bill/2026/about.html. And it is not a page to index, so it carries no
    # canonical address and asks not to be.
    page404 = shell("No page at this address | Granite Record", "", NOT_FOUND,
                    desc="There is no page at this address.")
    page404 = re.sub(r'(href|src)="(?!https?:|/|#|mailto:)([^"]+)"', r'\1="/\2"',
                     page404)
    page404 = re.sub(r'<link rel="canonical"[^>]*>',
                     '<meta name="robots" content="noindex">', page404)
    (out / "404.html").write_text(_shell.clean_links(page404), encoding="utf-8")

    print(f"wrote officials.html ({len(legs)} members), "
          f"about.html, search.html, 404.html -> {out}/  (learn.html: build_civics.py)")
    if not legs:
        print("  legislators.json missing — run build_site_v2.py first")
    if no_brand:
        print(no_brand)


if __name__ == "__main__":
    main()
