#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.302
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
import inline_js as IJ
import bill_order as BO
import build_date
import civics as _civics
import html as _html
import i18n
import shell as _shell
from i18n import say
from components import WORDBOOK, chip, clock, date_span, icon, pchip, until_attrs
import components as _components
from htmlesc import esc_blank
# A committee's recommendation in the committee page's words (REC_WORDS), for
# Latest Activity.
import committee_acts as CA
# A room in the words the rest of the site uses ("Granite Place 231" for the
# clerk's "GP 231"), for the Calendar's cards: plain_action.place.
import plain_action as PA
import seating
import site_read as SR
import strip_js
import json
import legislative_year as _year
import re
import shutil
from collections import OrderedDict, defaultdict, namedtuple
# What the builders share -- a calendar card and its key, Latest activity's sizes, a
# party's word -- is parts.py's, named here too, so that build_pages.<name> still answers.
from parts import (CHAMBER_WORD, CONFERENCE, EN_ATTR, FLOOR_CARD, MEET_KIND, MEET_LEGEND,
                   RECENT_BILLS, RECENT_SHOWN, _SMALL, Meet, cal_days, card_bodies, card_name,
                   clock_span, committee_codes, is_cancelled, is_conference, kind_title,
                   kind_word, meeting_key, meeting_who, party_word, pick_name)


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


# THE TAGS ARE PUBLISHED ONLY WITH A REGISTRY (topics as tags, stages 3 and 4,
# 17 November 2026; switched off until the owner approves the list). What
# draws a bill's tags, filters by them and searches through them is written
# in app.js, find.js and app.css between a line holding TAGS:BEGIN and the
# next holding TAGS:END -- each region whole lines, added beside the code they
# extend and changing none of it -- and front_end keeps those regions only
# where the site has tags: where build_site_v2 wrote a "tags" list into
# meta.json (site_has_tags), which it does only when corrections/tags.json is
# in force. Without one the published files are the files published before
# tags, byte for byte, as the rest of the site is. The source runs as it
# stands too (preflight's node harnesses run it): with no tags in meta.json
# what the regions add does nothing.
TAGS_BEGIN, TAGS_END = "TAGS:BEGIN", "TAGS:END"


def without_tags(text, name="app.js"):
    """`text` with each TAGS region cut out, its two marker lines with it, and
    nothing else touched: its lines and their endings are kept as they were.
    A region left open, opened inside another, or closed with none open stops
    the build, since half a feature published is worse than none."""
    out, inside = [], False
    for n, line in enumerate(text.splitlines(keepends=True), 1):
        mark = line.strip()
        begin = mark.startswith(("// " + TAGS_BEGIN, "/* " + TAGS_BEGIN))
        end = mark.startswith(("// " + TAGS_END, "/* " + TAGS_END))
        if begin:
            if inside:
                raise SystemExit(f"{name}:{n}: {TAGS_BEGIN} inside a region that is already open")
            inside = True
            continue
        if end:
            if not inside:
                raise SystemExit(f"{name}:{n}: {TAGS_END} with no {TAGS_BEGIN}")
            inside = False
            continue
        if not inside:
            out.append(line)
    if inside:
        raise SystemExit(f"{name}: a {TAGS_BEGIN} region is never closed")
    return "".join(out)


def site_has_tags(out):
    """Whether the site in `out` has tags: its meta.json names any (build_site_v2
    site_tagging). False where it has no meta.json or one that will not read."""
    try:
        return bool(json.loads((Path(out) / "meta.json").read_text(encoding="utf-8")).get("tags"))
    except (OSError, ValueError, AttributeError):
        return False


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

# THE PUBLISHED RECORD IS READABLE FROM ANYWHERE, which is what /data tells
# programmers it is: a page on another origin may read these files in a
# browser, as curl and a script on a server can. Cloudflare Pages already
# sends this header on every response, the HTML included (measured on /,
# /about and a bill page, 26 October 2026), so these rules change nothing it
# serves today. They say here which files the promise is made for, so that
# it does not rest on a default of the host's.
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

# And the public data API's files, which the manifest lists under "files":
# the people register as JSON (its CSV is a CSV above); each term's bills a
# line at a time, and their texts the same way (bill-texts-<term>, since 16
# November 2026); the whole record as one database; and schema.json, which
# describes every file here, once the API's branch writes it. A program that
# reads the manifest is handed these addresses, so a browser has to be let
# follow them. preflight's _data_cors holds every address the manifest names
# to exactly one rule here -- a second rule that matched too would send the
# header twice, "*, *", which a browser refuses, so do not add /data/* beside
# these -- and it says which new files it can and cannot see.
/data/schema.json
  Access-Control-Allow-Origin: *
/data/people.json
  Access-Control-Allow-Origin: *
/data/bills-*.jsonl.gz
  Access-Control-Allow-Origin: *
/data/bill-texts-*.jsonl.gz
  Access-Control-Allow-Origin: *
/data/granite-record.sqlite.xz
  Access-Control-Allow-Origin: *

# And the API's files a record (api_records.py, 16 November 2026), which
# /api/index.json lists: its folders one by one, so that no rule here reaches
# /api/live/, /api/report or /api/follow/, which are the Functions' own and
# answer for themselves. preflight's _api_records_cors holds every file the
# fixture writes under /api/ to exactly one of these.
/api/index.json
  Access-Control-Allow-Origin: *
/api/bills/*
  Access-Control-Allow-Origin: *
/api/rollcalls/*
  Access-Control-Allow-Origin: *
/api/members/*
  Access-Control-Allow-Origin: *
/api/requests/*
  Access-Control-Allow-Origin: *
/api/laws/*
  Access-Control-Allow-Origin: *
/api/changes/*
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
MEMBER_TAB_SLUGS = ("cosponsored", "votes", "elections")
# A committee's Videos tab (26 October 2026); its rule serves a study or
# statutory committee's /committee/ss<id>/videos too, which opens that page
# on its Videos tab, and /committee/ss<id>/sessions on its Meetings tab.
# And /bills (29 October 2026): a study committee's page opens on its
# Meetings, so its Bills tab has an address of its own; a standing
# committee's Bills is its page's own address, and /bills opens it too.
COMMITTEE_TAB_SLUGS = ("bills", "sessions", "videos")
# The chambers' pages (build_full_sessions.SLUG), whose Videos tab is
# /session/<chamber>/videos.
CHAMBER_TAB_PAGES = ("house", "senate")
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
         # In both spellings: the .html one answered 404 (Search Console, 7
         # November 2026), which every other mover here already covers.
         *((f"/legislator/jr-barnes-john-sd-17{x}", "/legislator/john-barnes-jr-sd-17")
           for x in ("", ".html")))
def moved_members(site):
    """The 301s from the page of a member's earlier chamber to the one page
    they have now (build_site_v2.former_movers, 30 October 2026): Shannon
    Chandley's House page answers with her Senate page, which carries both
    chambers' votes. Read off former.json's rows, where build_site_v2 says
    which addresses each took in; in both spellings, as MOVED's are."""
    try:
        rows = json.loads((Path(site) / "former.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ""       # no former.json: no moved members yet
    except (OSError, ValueError) as e:
        # Returning "" here rewrote _redirects without the moved members' 301s
        # and said nothing (bug hunt of 11 November 2026, finding 11).
        sys.exit(f"{Path(site) / 'former.json'} could not be read, and _redirects "
                 f"would lose the moved members' 301s: {e!r}")
    out = []
    for r in rows if isinstance(rows, list) else []:
        new = f"/legislator/{r.get('slug')}" if r.get("slug") else ""
        for old in (r.get("moved_from") or []) if new else []:
            # And a tab of the old page to the same tab of the new one: the
            # first rule that matches is the one served, and the tab rules'
            # /legislator/:who/votes would otherwise rewrite the old address to
            # a page that is gone (the review of 30 October 2026). Each tab
            # by name, a static rule, never old/* (STATIC RULES FIRST, below).
            # And the address with a trailing slash, which old/* caught.
            out += [f"{old} {new} 301\n", f"{old}.html {new} 301\n", f"{old}/ {new} 301\n"]
            out += [f"{old}/{s} {new}/{s} 301\n" for s in MEMBER_TAB_SLUGS]
        # AND THE DATA OF A NUMBER JOINED TO THIS PAGE (the deep walk of 6
        # November 2026): each page linked "This page's data as JSON" to
        # /legislators/<its id>.json, and a number joined to another's page
        # has no file of its own now, so the second number of each of the 34
        # joined members answered 404 where live gave their record. It
        # answers with the file of the page it was joined to.
        mid = str(r.get("id") or "")
        for j in (r.get("member_ids") or [])[1:] if new and mid else []:
            if str(j) != mid:
                out.append(f"/legislators/{j}.json /legislators/{mid}.json 301\n")
    return "".join(sorted(out))


# STATIC RULES FIRST, THEN THE DYNAMIC ONES (5 November 2026). Cloudflare
# Pages allows a file 2,000 static and 100 dynamic redirects and says
# "Static redirects should appear before dynamic redirects". The movers'
# rules went first, each mover with a dynamic old/* rule among its static
# ones; with the owner's thirty confirmed pairs that was 34 movers and 102
# lines, and the dry run of 4613f04 (run 175) served those 102 and none of
# the 52 after them -- every tab address, /legislators, /learn, the cities.
# Measured on that deployment: static rules after the first dynamic one
# were still served (its 5th and its 102nd), and the file stopped exactly
# 100 rules after the first dynamic one, its 3rd. So, counted from the first
# rule with a placeholder or a splat, every rule counts against the 100, and
# the 101st ends the file; that is how Cloudflare's parser reads it, as the
# review recalled it. The order is what keeps the count at the tab rewrites
# alone: every rule here is static but those, and they come last.
# preflight's _redirects_cloudflare holds the built file to it, and
# check_live asks for the last rule's address (rule_probes).
REDIRECTS_STATIC = (
    # A chamber's Videos tab (build_full_sessions), its page's.
    "".join(f"/session/{c}/videos /session/{c} 200\n" for c in CHAMBER_TAB_PAGES)
    + "".join(f"{old} {new} 301\n" for old, new in MOVED))
REDIRECTS_DYNAMIC = (
    "".join(f"/bill/:year/:bill/{s} /bill/:year/:bill 200\n" for s in BILL_TAB_SLUGS)
    + "".join(f"/legislator/:who/{s} /legislator/:who 200\n" for s in MEMBER_TAB_SLUGS)
    + "".join(f"/committee/:code/{s} /committee/:code 200\n" for s in COMMITTEE_TAB_SLUGS))
REDIRECTS_HEAD = "# Written by build_pages.py. Not an asset; Pages reads it.\n"
REDIRECTS = REDIRECTS_HEAD + REDIRECTS_STATIC + REDIRECTS_DYNAMIC


def moved_elect(site):
    """The 301s from a new member-elect's provisional page to their regular
    one, where the roster numbered them at another address
    (build_elect_pages.py's "moved"; Alice, 7 November 2026): the same
    spellings and tabs as moved_members."""
    try:
        doc = json.loads((Path(site) / "elect_pages.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    out = []
    for old, new in sorted(((doc or {}).get("moved") or {}).items()):
        out += [f"{old} {new} 301\n", f"{old}.html {new} 301\n", f"{old}/ {new} 301\n"]
        out += [f"{old}/{s} {new}/{s} 301\n" for s in MEMBER_TAB_SLUGS]
    return "".join(out)


def moved_requests(site):
    """The 301s from a bill request's page to where it now is (Alice, 8
    November 2026): a bill's page once it is introduced, its prime sponsor's
    once filing is complete -- each row of the requests' list with a
    "moved_to" (build_lsrs.py). build_request_pages writes no page at these
    addresses, so none is both a page and a redirect."""
    try:
        req = json.loads((Path(site) / "meta.json").read_text(encoding="utf-8")).get("requests") or {}
        rows = json.loads((Path(site) / "idx" / f"{req['term']}.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, KeyError, TypeError, AttributeError):
        return ""       # no requests window, or none listed yet
    except (OSError, ValueError) as e:
        sys.exit(f"the requests' meta.json or index in {site} could not be read, and "
                 f"_redirects would lose their 301s: {e!r}")
    # ONE RULE A REQUEST (the review of 8 November 2026): Cloudflare Pages
    # allows 2,000 static rules, 616 are in use, and a session files over a
    # thousand requests, most of them introduced by January -- three
    # spellings each, as a member's moved page has, would pass the limit
    # this winter and stop the nightly. The address as it is shared is the
    # one without .html; Pages sends the .html spelling there itself.
    out = []
    for r in rows if isinstance(rows, list) else []:
        if r.get("address") and r.get("moved_to"):
            out.append(f"/{r['address']} /{r['moved_to']} 301\n")
    # A withdrawn request of a member not returning is dropped from the list
    # (build_lsrs.drop_unreturned): its address, if a page was ever published,
    # forwards to the requests' list.
    for addr in req.get("dropped") or []:
        out.append(f"/{addr} /bills?term={req['term']} 301\n")
    return "".join(sorted(out))


def redirects_file(site):
    """_redirects as written: the head, every static rule -- the moved
    members' (moved_members), the members-elect's (moved_elect) and
    REDIRECTS_STATIC -- and then the dynamic tab rewrites (STATIC RULES
    FIRST)."""
    return (REDIRECTS_HEAD + moved_members(site) + moved_elect(site) + moved_requests(site)
            + REDIRECTS_STATIC + REDIRECTS_DYNAMIC)


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
# How much of Latest activity the home page shows (RECENT_SHOWN, RECENT_BILLS) is
# parts.py's, which latest_activity reads too.
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

# THE KINDS OF MEETING, what a meeting is keyed on (meeting_key) and a card's name,
# bodies and committee links (card_name, card_bodies, committee_codes) are parts.py's:
# the Calendar's week pages, Live Now and Latest activity draw and key the same cards.


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


# party_word, a party's name as the roster spells it, is parts.py's: the Officials
# page's members-elect say it too.


# THE PARTY'S LETTER STAYS UNDER THE CHART (the review of 29 October 2026).
# The owner asked for the rows under the seating chart to be "names only,
# without the full district, so the five columns are more compact", and the
# whole "(R - Belk 6)" was hidden from the eye: the party was then only the
# chip's coloured bar (WCAG 1.4.1), and in forced colours, where every bar is
# the one system colour, nothing at all. So a row's tag is written
# "(R<span class="mdist"> - Belk 6</span>)": app.css hides the district from
# the eye under the chart, the eye reads "(R)", and a screen reader hears the
# tag whole, as everywhere else. A tag of another shape is left as it is.
#
# THE CLOSING BRACKET GOES WITH THE DISTRICT, and the eye's own is aria-hidden
# (the blend's check, 29 October 2026). Clipped, the district is laid out as
# a block, and Chrome puts a space either side of a block when it names the
# link: "Rep. Debra DeSimone (R - Rock 18 )". With the ")" inside the clipped
# part the name is "(R - Rock 18)" again, word for word as everywhere else,
# and the ")" the eye sees is a second one a screen reader is not given.
_SEAT_TAG = re.compile(r'(<span class="mtag">)\(([^()\s<]+)( - [^()<]+)\)(</span>)')

# NAMES WITHOUT "REP." UNDER THE CHART (the owner, 29 October 2026: "the
# roster under the seating chart drops 'Rep.' from each name and keeps the
# party letter"). Every row under the chart is a representative, so the
# title says nothing the heading does not; "Debra DeSimone (R)" is what the
# eye reads. A screen reader still hears "Rep. Debra DeSimone (R - Rock 18)",
# as everywhere else, and the callout above a seat keeps its "Rep.".
_SEAT_HON = re.compile(r'(<span class="mchip[^"]*"[^>]*>(?:<a [^>]*>)?)(Rep\.) ')


# THE LETTER STAYS WITH THE SURNAME (the manager's polish, 29 October 2026):
# "Debra DeSimone / (R)" wrapped the party's letter onto a line of its own.
# The space before the tag is a no-break space, so a row too long for its
# column breaks before the surname: "Debra / DeSimone (R)".
_SEAT_GAP = re.compile(r' (<span class="mtag">)')


# ZOOM TO FIT, AN ICON (the owner, 29 October 2026): the seating chart's
# "Fit" was a word between two signs; it is four corners, the usual sign for
# zooming to fit, in the box of the - and + beside it. Its title is its name
# and its tooltip, "Zoom to fit" (with an aria-label as well, a screen reader
# heard the words twice: the review of 29 October 2026). Drawn in the
# button's own colour, so forced colours draw it as they draw the button's
# text.
ZOOM_FIT_ICON = ('<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">'
                 '<path d="M1 5.5V1h4.5M10.5 1H15v4.5M15 10.5V15h-4.5M5.5 15H1v-4.5" fill="none" '
                 'stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>'
                 '</svg>')


# THE SEAT NUMBER INSIDE THE CARD (the owner, 29 October 2026, a blend of the
# two mock-ups put to them): no gutter; each card carries its seat, "001",
# right-aligned, small and muted, without the division its column is headed
# with. That number is the eye's alone (aria-hidden), and the row's own
# "1-001" stays where it was, clipped by app.css, so a screen reader hears
# the seat in full before the name, as it always has. The Speaker's card on
# the rostrum carries none: the rostrum is no division, and its "6-002" is
# a plate a reader has no use for.
_SEAT_NUM = re.compile(r'<span class="sseat"[^>]*>(\d+)-(\d+)</span>')
_ROW_END = "</span></li>"


def seat_row_tag(row):
    """A row of the House by seat with its chip's district apart from its
    party's letter (_SEAT_TAG), its "Rep." apart from its name (_SEAT_HON):
    app.css shows the eye neither; the letter held to the surname by a
    no-break space (_SEAT_GAP); and, but on the rostrum, the seat's number
    within its division written inside the chip for the eye (_SEAT_NUM)."""
    row = _SEAT_HON.sub(r'\1<span class="mhon">\2 </span>', row)
    row = _SEAT_GAP.sub(r'&#160;\1', row)
    row = _SEAT_TAG.sub(r'\1(\2<span class="mdist">\3)</span><span aria-hidden="true">)</span>\4', row)
    num = _SEAT_NUM.search(row)
    if num and int(num.group(1)) != seating.SPEAKER_SEAT // 1000 and row.endswith(_ROW_END):
        row = (row[:-len(_ROW_END)] + f'<span class="mseat" aria-hidden="true">{num.group(2)}</span>'
               + _ROW_END)
    return row


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
    # The week's name and its weekdays, as the Calendar's pager says them
    # ("This Week", "Next Week": the person, 9 October 2026, item 17).
    label = ('<p class="calwk">' + chip(say(lang, "cal.next_week", "Next Week") if ahead
                                        else say(lang, "cal.this_week", "This Week"))
             + f' <span>{esc(date_span(monday, monday + _dt.timedelta(days=4), "medium", lang))}'
             + "</span></p>")
    coming = say(lang, "cal.coming", "Coming Up")

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
    # In another language the full calendar is that language's page (9
    # November 2026), from the root as the footer's About link is.
    more = ('<p class="calmore calall"><a href="'
            + ("calendar.html" if lang == i18n.DEFAULT else i18n.href(lang, "calendar.html").lstrip("/"))
            + '">' + say(lang, "cal.full", "See the full calendar") + '</a></p>')

    if not dates:
        # THE REST OF THE WEEK IS EMPTY every weekend in session and every
        # day out of it. With next week empty too it went on to say when the
        # General Court sits and when committees meet on bills (cal.season),
        # until the owner's choice of 26 October 2026: the rail says what is
        # scheduled, and the status box beside it where the General Court is
        # in its year.
        # WHAT IS NOT SCHEDULED, NOT "NOTHING" (the audit of 25 October 2026,
        # M8). The rail leaves the special study committees to the Calendar
        # (home_week), and "Nothing is scheduled next week yet" stood over a
        # week of 26 October 2026 for which the Calendar held seventeen of
        # theirs. It says what the rail holds and does not: the chambers' own
        # meetings.
        # ITS SENTENCE IS AN ELEMENT OF ITS OWN (the preview check of 25
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


# A card's days -- is_cancelled, meeting_who and cal_days, which draw a day of the
# Calendar -- are parts.py's: the week pages and Live Now draw the same cards.


HEARING_NOTE = ("Anyone may attend a public hearing and ask to speak. You can "
                "also sign in online to register a position and submit "
                "written testimony.")
# A SENATE HEARING'S NOTE (23 October 2026). The person's words above are the
# House's form, which takes written testimony with a sign-in. The Senate's
# takes a position and no testimony, and the page that confirms the sign-in
# says how to send it (the Senate's Public Guidance for Committee Meetings,
# which guides.TESTIMONY cites). So a Senate hearing's note says that. The
# bill page's Testify pane (app.js testifyButton) and the follow emails
# (workers/follow/mail.js testifyWords) said it too until the person's
# shorter wording of 26 October 2026, which both now share, and neither
# carries this sentence any more.
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
<h1>Nothing is published here</h1>
<p class="lead" id="nf-lead">The address may be mistyped, or name a bill in a year it does
not exist in: every bill since 1989 has a page of its own, for example
<code>[[example]]</code>, and a bill number starts again every two years.</p>
<p id="nf-bill" hidden></p>
<p><a href="bills.html">Search every bill</a> &middot;
<a href="officials.html">Officials</a> &middot;
<a href="committees.html">Committees</a> &middot; <a href="index.html">Home</a></p>
<script>
""" + IJ.script("build_pages.not_found") + "</script>\n"

# THE EXAMPLE IS A PAGE THERE IS (the polish of 26 October 2026, P2). The
# page said "for example /bill/2026/hb1", and HB 1 of the 2025-2026 term was
# filed in 2025: the one address offered to a reader who is lost was itself
# not found. It is now read off the bill index build_site_v2.py has already
# written, as build_bill_pages.py reads it to write /bill/<year>/<id>.
NOT_FOUND_EXAMPLE = ", for example\n<code>[[example]]</code>"


def not_found_example(out):
    """The address of a bill page this build writes, for the not-found page:
    HB 1 of the newest term that has a page, or that term's first bill. A
    bill's page is written under the year its index row gives, and only from
    its record (site/bills/<year>/<id>.json, or the page an earlier run
    inlined it into); "" where no bill has either."""
    try:
        rows = SR.bill_index(out) or []
    except SR.Broken:
        return ""
    for term in sorted({r.get("term") or "" for r in rows}, reverse=True):
        have = [r for r in rows if r.get("term") == term and r.get("year") and r.get("id")
                and ((out / "bills" / str(r["year"]) / f"{r['id']}.json").is_file()
                     or (out / "bill" / str(r["year"]) / f"{r['id'].lower()}.html").is_file())]
        if have:
            pick = next((r for r in have if r["id"] == "HB1"), have[0])
            return f"/bill/{pick['year']}/{pick['id'].lower()}"
    return ""


def not_found_body_lang(example, lang):
    """The not-found page of a page in another language (/es/404.html): the
    site's own wording in `lang`, its links to that language's pages where it
    has them (i18n.href: the English page where it has not). No script: the
    English page's script reads addresses of bills, towns and laws, none of
    which is under /es/."""
    ex = (f'<code>{example}</code>' if example else "")
    lead = (say(lang, "nf.lead_example", "The address may be mistyped, or name a bill in a year "
                "it does not exist in: every bill since 1989 has a page of its own, for example "
                "{example}, and a bill number starts again every two years.", example=ex)
            if example else
            say(lang, "nf.lead", "The address may be mistyped, or there may be no page "
                "here yet. Some pages are not translated."))
    return (f'<h1>{say(lang, "nf.head", "Nothing is published here")}</h1>\n'
            f'<p class="lead">{lead}</p>\n'
            f'<p><a href="{i18n.href(lang, "bills.html")}">'
            f'{say(lang, "nf.bills", "Search every bill")}</a> &middot;\n'
            f'<a href="{i18n.href(lang, "officials.html")}">'
            f'{say(lang, "nav.officials", "Officials")}</a> &middot;\n'
            f'<a href="{i18n.href(lang, "committees.html")}">'
            f'{say(lang, "nav.committees", "Committees")}</a> &middot; '
            f'<a href="{i18n.href(lang, "index.html")}">{say(lang, "nf.home", "Home")}</a></p>')


def not_found_body(example):
    """NOT_FOUND with its example, or without the clause where there is none."""
    body = (NOT_FOUND.replace("[[example]]", example) if example
            else NOT_FOUND.replace(NOT_FOUND_EXAMPLE, ""))
    assert "[[example]]" not in body, "the not-found page's example was left unfilled"
    return body

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
# audit of 25 October 2026, S6), its words unchanged. "Neutrality and
# Methods" replaced "Independence" by the person's approval of 29 October 2026
# (docs/design/about-neutrality/draft.md on branch design/email-pass gives the
# source of each sentence); its [[median]] is the Data page's figure, from
# about_figures, and never typed. Its first sentence is Independence's own,
# kept because nothing else on the page says the site is not affiliated with
# the General Court or takes no position on any bill (the review of 29 October
# 2026); "or endorsed by" was cut at the owner's word the same day.
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
written reports start with the 1997–1998 term, the first in its online
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

<h2>Neutrality and Methods</h2>
<p>Granite Record is not affiliated with the New Hampshire General Court, and it
takes no position on any bill. I'm a sitting member of the House,
so the site keeps to these rules.</p>
<ul>
<li>Nothing on it is editorialized. Dates, sponsors, vote tallies, committee
assignments and hearing times are taken directly from the official record.
Committee reports appear as filed, in the committee's own words, and summaries
of a bill's progress are generated from the record by software.</li>
<li>A report made with <i>Report a problem</i> holds nothing that identifies who
sent it, so every one is checked against the official record in the same way,
and corrected where the record bears it out. An email to
<a href="mailto:contact@graniterecord.org">contact@graniterecord.org</a> is
handled the same way, whoever sends it.</li>
<li>On the Learn pages, where a concept needs an example bill, town or
legislator, the site uses a less polarizing one when there is a choice. A list
taken from the record, such as the hearings with the most sign-ins, is shown as
the record has it.</li>
</ul>
<p>Each step-by-step guide links the official page that has the final word, and
says when it was last checked against it.</p>
<p>Hearing timestamps are measured against proceedings a person timed by
watching the recording. On the ones the method places, the median is out by
[[median]]. <a href="data.html#how-built">How the record is built</a>, on the
Data page, gives every figure.</p>

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

def about_logo(has_lockup, lang="en"):
    """THE DRAWING ITSELF, in the section about it (the person, 10 October
    2026: "add the logo drawing to the section in the about page about the
    logo"): the lockup the home page's heading draws, as the same mask over
    the text colour (app.css .aboutlogo), so it is right in both themes. A
    build without lockup.png -- a clone, a fork -- writes nothing here rather
    than an empty box, as the home page writes its name as text."""
    if not has_lockup:
        return ""
    return ('<p class="aboutlogo" role="img" aria-label="'
            + say(lang, "about.logo_label", "The Granite Record logo, drawn by Debra Caplan")
            + '"></p>\n')


# THE ABOUT PAGE IN ANOTHER LANGUAGE (the owner, 9 November 2026: "more of
# the site in Spanish where feasible"). The page is translated a piece at a
# time as a guide is (i18n.say_html), keyed about.<its first words>; the
# artist's own words, which are hers and in English, are set apart and
# printed as she wrote them, marked lang="en". The four figures that are
# words rather than numbers are said in the page's language (about_figs).
ABOUT_PAGE = "about.html"
SEARCH_PAGE = "search.html"
ABOUT_QUOTE = re.compile(r'<blockquote class="artist">.*?</blockquote>', re.S)
ABOUT_QUOTE_SLOT = "<!-- artist -->"
ABOUT_LOGO_SLOT = "<!-- logo -->"


def _about_english(live):
    """The page's English as it is translated: the follow lines for `live`,
    the logo's slot emptied and the artist's quotation set apart."""
    return ABOUT_QUOTE.sub(ABOUT_QUOTE_SLOT, about_text(live).replace("__LOGO__", ABOUT_LOGO_SLOT))


def about_words():
    """[(key, English, where)] of every piece of the About page, in reading
    order, in both of its wordings of email following (about_text), once each."""
    out, keys, used = [], {}, {}
    for live in (True, False):
        html_ = _about_english(live)
        for s_, e_ in i18n.pieces(html_):
            en = i18n.norm(html_[s_:e_])
            if en in keys:
                continue
            base = f"about.{i18n.slug_words(en)}"
            key, n = base, 2
            while used.get(key, en) != en:
                key, n = f"{base}-{n}", n + 1
            used[key] = en
            keys[en] = key
            out.append((key, en, "about.html"))
    return out


def about_figs(figs, lang):
    """about_figures' figures, with those that are words rather than a
    number said in `lang`: the month the recordings begin and the median."""
    if lang == i18n.DEFAULT:
        return figs
    out = dict(figs)
    if "stream_start" in figs:
        out["stream_start"] = say(lang, "about.fig.stream_start", "May 2020")
    m = re.fullmatch(r"(\d+) (second|minute)s?", str(figs.get("median", "")))
    if m:
        n = int(m.group(1))
        out["median"] = (
            (say(lang, "about.fig.second", "1 second") if n == 1 else
             say(lang, "about.fig.seconds", "{n} seconds", n=n)) if m.group(2) == "second" else
            (say(lang, "about.fig.minute", "1 minute") if n == 1 else
             say(lang, "about.fig.minutes", "{n} minutes", n=n)))
    return out


def about_html(lang, has_lockup, figs, live=None):
    """The About page's body in `lang`: its words piece by piece, the
    artist's quotation as she wrote it, the figures filled in after."""
    english = _about_english(_shell.follow_live() if live is None else live)
    quote = ABOUT_QUOTE.search(about_text(live)).group(0)
    if lang == i18n.DEFAULT:
        body = english
    else:
        keys = {en: key for key, en, _w in about_words()}
        body = i18n.say_html(lang, english, keys)
        quote = quote.replace('<blockquote class="artist">', '<blockquote class="artist" lang="en">')
        body = body.replace("</h1>", "</h1>" + chrome.lang_note(lang), 1)
    body = body.replace(ABOUT_QUOTE_SLOT, quote)
    body = body.replace(ABOUT_LOGO_SLOT, about_logo(has_lockup, lang))
    return i18n.lang_links(about_figures.fill(body, about_figs(figs, lang)), lang)


SEATING_JS = "\n<script>\n" + IJ.script("build_pages.seating") + "</script>\n"

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
                     "titleShare", "statusCat", "requestNumber",
                     "setRequestYear")
# And what its TAGS regions define, handed back where they are published.
BILLMATCH_TAGS = ("setTagWords",)
# The head of the file bill_matcher_js writes: not a page's script but the
# start of a file of its own, around app.js's code, so it stays here
# (preflight's _INLINE_KEPT) where the pages' scripts are in inline/.
BILLMATCH_HEAD = ("// Written by build_pages.py from app.js's BILLMATCH regions, "
                  "for find.js.\n// Do not edit here: edit app.js.\n"
                  "window.GR_BILLMATCH=(function(){\n")


def bill_matcher_js(app_js, tags=False):
    """The marked regions of app.js, as one script defining GR_BILLMATCH.

    Stops the build rather than writing a partial file: a region left open,
    an END with no BEGIN, or a region set that no longer defines what the
    header calls would each ship a panel that counts nothing, silently.

    Without its TAGS regions (without_tags) unless `tags`: the site has tags
    (site_has_tags). With them, GR_BILLMATCH hands back setTagWords as well,
    which find.js gives meta.json's tags and the words that lead to them."""
    if not tags:
        app_js = without_tags(app_js)
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
    exports = BILLMATCH_EXPORTS + tuple(f for f in BILLMATCH_TAGS
                                        if re.search(r"\bfunction " + f + r"\(", body))
    return (BILLMATCH_HEAD + body + "\nreturn {"
            + ",".join(exports) + "};\n})();\n")


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
SEARCH_JS = "\n<script>\n" + IJ.script("build_pages.search") + "</script>\n"


# THE OLD PAGE'S TOWNS TAB IS MY TOWN. /legislators#towns arrives here as
# /officials#towns through the 301, and the tab it named is #my-town now: the
# address is rewritten before TABS_JS reads it, without a history entry.
# AND STATEWIDE OFFICIALS IS EXECUTIVE BRANCH (17 October 2026). The tab was
# renamed and its address with it, and a link already made to
# /officials#statewide must still open it, so the old address is rewritten
# the same way -- at load, and on a hashchange too, because this listener is
# added before TABS_JS's and so runs first, and a link to #statewide from the
# page itself then opens the tab rather than nothing.
OFFICIALS_HASH_JS = "<script>\n" + IJ.script("build_pages.officials_hash") + "</script>"

# THE DISTRICT MAP ON MY TOWN (map v1, src/pages/map.js, the person's label
# toggle with town names by default). Mounted the first time its tab is
# shown, at the size it will have: a map drawn into a hidden panel measures
# nothing. The finder's town is the map's town: typing a town's whole name,
# or opening a city's wards, zooms the map to it (LEGFIND_JS sends "grtown").
OFFICIALS_MAP_JS = ('<link rel="stylesheet" href="/map.css">\n<script src="/map.js" defer></script>\n'
                    "<script>\n" + IJ.script("build_pages.officials_map") + "</script>")


LEGFIND_JS = "\n<script>\n" + IJ.script("build_pages.legfind") + "</script>"


# THE WAY FROM THE STATUS BOX TO THE LEGISLATURE'S YEAR (the person, 17
# October 2026: a page on the schedule "which links to the homepage status in
# some way so that folks understand when the legislature is in session and the
# various deadlines around filing bills"). One line at the foot of the box,
# written once here for both of its renderers -- the box main() builds and
# HOME_JS's copy -- so that the two cannot say different things; the address
# and the link's words are legislative_year's, the page's own.
YEAR_LINK = (f'<p class="statenote stateyear"><a href="{_shell.canon(_year.HREF)}">'
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


# THE RECORDING, ONCE IT IS OVER (the owner, 11 November 2026: "Add the link
# to the webinar youtube video as an embedded player on the homepage"). The
# same place under the search, the same box, and the player the home page's
# session recordings use: nothing is asked of YouTube until Play is pressed.
WEBINAR_VIDEO = "BMPOb0BFdYw"


def home_webinar_recording(lang="en"):
    """The webinar's recording, in the box the registration had."""
    esc = _html.escape
    title = say(lang, "web.rec.title", "Recording of the Granite Record launch webinar, November 10, 2026")
    note = "" if lang == "en" else say(lang, "web.rec.english", " (in English)")
    return (f'<aside class="webinar wbrec" aria-label="{esc(say(lang, "web.rec.label", "Webinar recording"))}">'
            f'<p class="wbwhen">{say(lang, "web.rec.head", "Watch the launch webinar")}{note}</p>'
            f'<p class="wbwhat">{say(lang, "web.rec.what", "How Granite Record works, and how to use it to keep up with Concord this session, with Alice Wade. Recorded November 10, 2026.")}</p>'
            f'<div class="player"><button type="button" class="pstub" data-embed="{esc(WEBINAR_VIDEO, quote=True)}" '
            f'data-title="{esc(title, quote=True)}" aria-label="{esc(say(lang, "web.rec.play", "Play the recording of the launch webinar"), quote=True)}">'
            f'<span>{icon("play")}</span><span>{say(lang, "sess.play", "Play the recording")}</span></button></div>'
            '</aside>')


def home_webinar(today=None, lang="en"):
    """The webinar's box for the home page: its registration until it is
    over, then its recording. In another language it says it is in English."""
    today = today or build_date.today().isoformat()
    if str(today)[:10] >= WEBINAR_UNTIL:
        return home_webinar_recording(lang)
    return (f'<aside class="webinar" aria-label="{_html.escape(say(lang, "web.label", "Webinar"))}"'
            f'{until_attrs(WEBINAR_UNTIL, today)}>'
            f'<p class="wbwhen">{say(lang, "web.when", "Free webinar &middot; Tuesday, November 10, 6:30&nbsp;PM")}</p>'
            f'<p class="wbwhat">{say(lang, "web.what", "How Granite Record works, and how to use it to keep up with Concord this session. Hosted by Alice Wade. All are welcome to join, ask questions and say which features they would like most.")}</p>'
            f'<a class="wbgo" href="{_html.escape(WEBINAR_URL, quote=True)}" target="_blank" rel="noopener">'
            f'{say(lang, "web.go", "Register on Zoom")}</a></aside>')


# The home page's escape: components.js's esc, the ampersand, the angles and the
# double quote (src/lib/htmlesc.py).
_home_esc = esc_blank


def _record(x, lang):
    """The record's own words (a bill's title, the hand-kept status note), as
    the record has them: in English, marked so on a page in another language,
    so a screen reader says them in English (i18n.py, the first kind)."""
    x = _home_esc(x)
    return x if lang == i18n.DEFAULT or not x else f'<span lang="en">{x}</span>'


def _kept(x, es, lang):
    """A hand-kept line of the status box in `lang`: its Spanish twin
    (status.txt's note_es, milestone_es) when the page is Spanish and there is
    one -- the site's own wording, so lang="es" and no "en" mark -- else the
    English line as the record has it (_record)."""
    if lang != i18n.DEFAULT and es:
        return _home_esc(es)
    return _record(x, lang)


def year_link(lang="en"):
    """YEAR_LINK in `lang`: the way to the legislature's year, in `lang`
    where that page is built in it (i18n.href). Absolute, because the
    Spanish home page carries <base href="/">, under which the bare HREF
    opened the English page."""
    if lang == i18n.DEFAULT:
        return YEAR_LINK
    return (f'<p class="statenote stateyear"><a href="{_shell.canon(i18n.href(lang, _year.HREF))}">'
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
            # NO "LAST SESSION DAY" LINE (the owner, 19 November 2026): the
            # House and Senate recordings under the box name the last session
            # day already.
            + "</div>"
            + (f'<p class="statehead">{_record(S["headline"], lang)}</p>'
               if S.get("headline") else "")
            + (f'<p class="statenote">{_kept(S["note"], S.get("note_es"), lang)}</p>' if S.get("note") else "")
            + (f'<p class="statenote"><b>{say(lang, "state.next", "Next:")} '
               f'{_kept(ms.get("label"), ms.get("label_es"), lang)}</b>, '
               f'{fd(ms.get("date")).rstrip(".")}. {_kept(ms.get("note"), ms.get("note_es"), lang)}</p>'
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
# An interim study report, by one rule wherever it is shown (the person, 30
# October 2026): recommending the subject for future legislation in the green
# of a law, not recommending it in the colour of a bill that died, and making
# no recommendation in none -- as the Reports tab's chip (app.js RECCOLOUR),
# the docket line's mark (app.css .jrec-*) and a committee's meeting card
# (.mrec, .mkill, .mwithout) colour it.
# A report whose row states none of the three ("") is plain, as "without" is.
STUDY_KIND = {"rec": "law", "not": "done", "without": "", "": ""}


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
    # THE VOTE INSIDE THE CHIP (the owner's walk of dry run 8, 8 November
    # 2026): "Does Not Recommend Future Legislation (18–3)", as a bill's
    # Reports tab now draws it. The tally is a span of its own so it never
    # breaks at its dash.
    if did.get("yeas") is not None and did.get("nays") is not None and out.endswith("</span>"):
        out = (out[:-len("</span>")]
               + f' <span class="latvote">({did["yeas"]}–{did["nays"]})</span></span>')
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


def recent_sessions(H, lang="en", sits=None):
    """RECENT SESSION DAYS, under the status box: the latest sitting of each
    chamber, as a title and a player each -- "House Session (Aug 19, 2026)"
    over a 16:9 still with Play in its middle.

    THE PLAYERS ARE BACK (the owner, 26 October 2026, of the release
    candidate: "the embedded house and session recent session videos are no
    longer displaying properly"). From 25 October they were one line, "Aug
    19, 2026 — House · Senate recordings" (the audit's M8); before that
    HOME_JS drew them from home.json. As the live site had them, with these
    changes: drawn here, at build time and in the page's language, so they
    are there before any script runs; the date in the site's own style,
    date_words' medium form, where it was "August 19th, 2026", and still the
    way to the sitting's page where one is built (`sits`, sitting_days()),
    words where none is; and Play named for its chamber and day ("Play the
    House floor session of Aug 19, 2026"), as the player that takes its place
    is ("Recording of the House floor session, Aug 19, 2026"). Each chamber
    carries its own date, so chambers that last sat on different days each
    say theirs. In home.json's order, the House's first.

    NOTHING FROM YOUTUBE UNTIL PLAY IS PRESSED (the privacy page: "a player
    only loads if you press play"). Play is a button carrying the recording's
    id (data-embed) and the frame's title (data-title); HOME_JS puts the
    no-cookie player in its place when it is pressed. No thumbnail, no
    script and no frame from YouTube or Google before that. "" where
    home.json names no sitting."""
    esc = _home_esc
    shown = [v for v in H.get("latest_sessions") or [] if v.get("date") and v.get("video_id")]
    if not shown:
        return ""
    cells = []
    for v in shown:
        b = "S" if v.get("chamber") == "Senate" else "H"
        d = v["date"]
        day = _shell.date_words(d, "medium", lang)
        dated = (f'<a href="session/{b}/{esc(d)}.html">{esc(day)}</a>' if (b, d) in (sits or ())
                 else esc(day))
        if b == "S":
            name = say(lang, "sess.senate", "Senate Session")
            rec = say(lang, "sess.rec_senate", "Recording of the Senate floor session, {date}", date=day)
            play = say(lang, "sess.play_senate", "Play the recording of the Senate floor session, {date}",
                       date=day)
        else:
            name = say(lang, "sess.house", "House Session")
            rec = say(lang, "sess.rec_house", "Recording of the House floor session, {date}", date=day)
            play = say(lang, "sess.play_house", "Play the recording of the House floor session, {date}",
                       date=day)
        cells.append(
            f'<div class="sess"><p class="sesstitle"><b>{name}</b> ({dated})</p>'
            f'<div class="player"><button type="button" class="pstub" '
            f'data-embed="{esc(v["video_id"])}" data-title="{esc(rec)}" aria-label="{esc(play)}">'
            # "Play the recording", as every other player's button says (the
            # cohesion audit of 30 October 2026, I-11); its name says which.
            f'<span>{icon("play")}</span><span>{say(lang, "sess.play", "Play the recording")}</span>'
            "</button></div></div>")
    return (f'<h2>{say(lang, "sess.recent", "Recent Session Days")}</h2>'
            f'<div class="twoup">{"".join(cells)}</div>')


def home_body(lang, has_lockup, static_state, static_up, static_recent, static_sessions):
    """The home page's <main>, in `lang`: the hero, the search box, the cards
    and the guides' slot in the middle; the status and Recent Session Days,
    the latest sittings' players (recent_sessions), on the left; Coming up, the rebuild
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
    # WHAT IS IN THE PAGE'S LANGUAGE, AND WHY THE REST IS NOT: the one note
    # every page in another language carries (chrome.lang_note).
    only = "" if lang == i18n.DEFAULT else chrome.lang_note(lang) + "\n"
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
     box's own dropdown, the header panel's rows; Return opens the first
     where it is the one clear destination (find.js, findClear), as in the
     header, and every result where it is not, and Search opens every result.
     Without script, Search opens the bill search, as it did.
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
<!-- EACH CARD WITH ITS SECTION'S DRAWING, the nav's own (Polish 1, 9 October
     2026): Bills, Officials, Laws and Resources since 17 October 2026
     (HOME_CARDS says why). -->
{home_cards(lang)}
<!-- THE WEBINAR'S RECORDING UNDER THE CARDS (the owner, 19 November 2026:
     "move the webinar video block on the homepage below the cards for bills,
     laws, officials, and resources"; under the search since 24 October). -->
{home_webinar(lang=lang)}
<!-- COMMON QUESTIONS, under the cards (the person, 18 October 2026: "a sort
     of top 3-5 guides for the most common inquiries"): a few guides, each by
     its title over a line saying what a reader will learn there, and All
     guides. Filled by build_civics, which knows which guides passed their
     checks; empty while build_civics.HOME_GUIDES is off. -->
{guides}
</div>
<section class="hside hleft" aria-label="{esc(say(lang, "home.left", "Where the General Court is, and its latest session days"))}">
<div id="state">{static_state}</div>
{'<p class="lv-home" hidden data-day=""></p>' if lang == "en" else ""}
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
     October 2026) -- then the latest meetings. Recent Session Days, with
     the status, is on the left. Below 1180px the same order: the hero, the
     search and the cards, the status, Recent Session Days, Coming Up, the
     rebuild line and Latest Activity. -->
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


HOME_JS = "\n<script>\n" + IJ.script("build_pages.home", YEAR_LINK=YEAR_LINK) + "</script>"
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


def published_js(name, text, tags=False):
    """A browser script's text as the site publishes it: components.js with
    the words written between its markers (with_words), and every script
    without its comments (strip_js.published, which publishes one as it is,
    and says so, where its reader refuses it). What front_end() writes, and
    what preflight holds the site's copy to (_published_scripts_stripped);
    build_district_map.py writes map.js through strip_js.published itself,
    since it has no words. Without its TAGS regions (without_tags) unless
    `tags`: the site has tags (site_has_tags)."""
    if not tags:
        text = without_tags(text, name)
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


def front_end(out, has_mark, has_tags=None):
    """Everything this step makes of the browser's files and of nothing else:
    the files it copies (COPIED) and billmatch.js. Returns the names it wrote
    whose bytes changed, and style.css where it took an old build's away.
    `has_tags` keeps the TAGS regions of the scripts and app.css (without_tags);
    None asks the site's own meta.json (site_has_tags), as the fast path does.

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
    if has_tags is None:
        has_tags = site_has_tags(out)
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
            css = (body if has_mark else without_mark(body)).decode("utf-8")
            body = strip_css(css if has_tags else without_tags(css, name)).encode("utf-8")
        if name.endswith(".js"):
            body = published_js(name, body.decode("utf-8"), tags=has_tags).encode("utf-8")
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
            Path("src/pages/app.js").read_text(encoding="utf-8"), tags=has_tags),
            tags=has_tags).encode("utf-8")
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


def brand_files_placed(out):
    """The drawn files of assets/ put in the site folder `out`, the licensed ones
    over the clipart and the emails' copy of the mark made from the header's.
    Returns whether the home page's lockup and the header's mark are there, and
    the one line said at the end of main where any of BRAND_FILES is missing
    (`no_brand`, else empty; printed here where none is).
    A step of main, lifted out of it as it stood (20 November 2026)."""
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
    return has_lockup, has_mark, no_brand


def headers_and_redirects(out):
    """The host's two files, _headers (HEADERS) and _redirects (redirects_file),
    written with LF line ends where either differs from what it should hold.
    A step of main, lifted out of it as it stood (20 November 2026)."""
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
    # The moved members' rules FIRST, under the header line: a rule is
    # served by the first that matches, and the tab rules, last, would catch
    # /legislator/<anyone>/votes before a later 301 could. All static, and
    # every static rule before the dynamic ones (STATIC RULES FIRST).
    want = redirects_file(out)
    if (not red.exists()
            or red.read_text(encoding="utf-8", newline="") != want):
        red.write_text(want, encoding="utf-8", newline="\n")
        print("  _redirects: a tab's address serves its record's page")


def officials_pages(out, legs, C):
    """The Officials page, officials.html, in each language it has: the roster in
    both chambers (`legs`, the sitting members) with the seating charts of the
    party composition `C` (home.json's), the vacancies, the other offices, the
    members-elect and the towns finder; and the old legislators.html removed.
    A step of main, lifted out of it as it stood (20 November 2026)."""
    esc = _home_esc

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
        # One vacancy in words of its own (the release walk, 2 November 2026:
        # "1 vacantes"); the English is the same.
        filled = (say(lang, "comp.filled_vacant_one", "{sitting} of {seats} seats filled, {vacant} "
                      "vacant", sitting=x["sitting"], seats=x["seats"], vacant=x["vacant"])
                  if x.get("vacant") == 1 else
                  say(lang, "comp.filled_vacant", "{sitting} of {seats} seats filled, {vacant} "
                      "vacant", sitting=x["sitting"], seats=x["seats"], vacant=x["vacant"])
                  if x.get("vacant") else
                  say(lang, "comp.filled", "{sitting} of {seats} seats filled",
                      sitting=x["sitting"], seats=x["seats"]))
        # The chamber's one short line closes the block, under the bar: a
        # phone draws the bar and the line, a wider screen the bar, its line
        # and legend and the thresholds (the walk of 8 November 2026: a
        # chart on a phone as well).
        return (f'<div class="comp"><div class="compline"><b>{esc(chamber)}</b>'
                f'<span class="statemeta">{filled}</span>'
                f'</div><div class="pbar2">{segs}</div>'
                f'<div class="plegend">{legend}</div>{note}{short_bar(ch, lang)}</div>')

    def short_bar(ch, lang="en"):
        """One chamber's seats in one short line, which is all a phone shows
        of them (the owner's walk of 7 November 2026, C): "Senate 16 R
        &middot; 8 D", "House 212 R &middot; 169 D &middot; 1 I &middot; 18
        vacant" -- a party's letter for the eye and its name for a screen
        reader, from the same counts as static_bar's."""
        x = C.get(ch)
        if not x:
            return ""
        bits = [f'{pp["n"]} <span aria-hidden="true">{esc(pp["code"])}</span>'
                f'<span class="sr">{esc(party_word(pp["name"], lang, plural=pp["n"] != 1))}</span>'
                for pp in x.get("parties", [])]
        if x.get("vacant"):
            bits.append(say(lang, "comp.n_vacant_one", "{n} vacant", n=x["vacant"])
                        if x["vacant"] == 1 else say(lang, "comp.n_vacant", "{n} vacant", n=x["vacant"]))
        chamber = {"House": say(lang, "comp.house", "House"),
                   "Senate": say(lang, "comp.senate", "Senate")}.get(x["chamber"], x["chamber"])
        # Each count whole on its line (.csb): a line too long for the phone
        # breaks between two of them, never inside one.
        return (f'<p class="compshort"><b>{esc(chamber)}</b> '
                + " &middot; ".join(f'<span class="csb">{b}</span>' for b in bits) + "</p>")

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

    def legislator_box(lang="en"):
        """The Legislators tab's search box (the owner, 21 November 2026:
        "The legislators tab should get its own search box"): a member found
        by name, county, party or committee, in the site's own suggestion
        list, which build_pages.legfind.js mounts (lsMount) and which lists
        every match under it, the Senate apart from the House. The town box's
        look (.ovtown), with an id of its own. Disabled until the script has
        mounted it; without the script the roster below is the way in.
        Each party the roster holds is written into data-parties in the page's
        language (party_word), so a reader can find a party by its name in
        that language and the script keeps no party table of its own."""
        parties = {p: party_word(p, lang) for p in sorted({m.get("party") for m in legs if m.get("party")})}
        return ('<div class="ovtown lsbox" id="lsbox" data-parties="'
                + esc(json.dumps(parties, ensure_ascii=False, separators=(",", ":"))) + '">'
                '<form class="ovtform" role="search" action="officials.html#legislators">'
                '<label for="lsq" class="ovtl">' + say(lang, "of.ls.find", "Find a legislator") + "</label>"
                '<div class="ovtrow"><div class="ovtbox">'
                '<input id="lsq" type="search" autocomplete="off" placeholder="'
                + say(lang, "of.ls.ph", "Name, county, party or committee") + '" disabled></div>'
                '<button type="submit" class="ovgo" disabled>' + say(lang, "search.go", "Search")
                + "</button></div></form></div>"
                '<div class="lsres" id="lsres" hidden></div>')

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
        # THE PARTY AND THE DISTRICT, ON THE SEAT, for the name's callout
        # above it (the owner, 29 October 2026): the party in the page's
        # words, the district as the county's name and its number.
        by_seat = {int(m["seat"]): {"name": m.get("display_plain") or m.get("name"),
                                    "party_code": pcode(m),
                                    "party": party_word(m.get("party") or "", lang)
                                    if m.get("party") else "",
                                    "dist": " ".join(str(x) for x in (m.get("county"), m.get("district"))
                                                     if x),
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
            H, lambda m: seat_row_tag(li(m, seating.plate(m["seat"]) if m.get("seat") else "")), lang)
        senate_rows = "".join(li(m, say(lang, "off.district", "District {d}", d=m.get("district")))
                              for m in S)

        seats_said = (say(lang, "roster.filled_vacant_one", "{seated} of the 400 seats are filled and "
                          "{vacant} is vacant.", seated=seated, vacant=vacant) if vacant == 1 else
                      say(lang, "roster.filled_vacant", "{seated} of the 400 seats are filled and "
                          "{vacant} are vacant.", seated=seated, vacant=vacant) if vacant else
                      say(lang, "roster.filled", "{seated} of the 400 seats are filled.",
                          seated=seated))
        return f"""<section class="roster" id="roster">
<div class="rtabs" role="tablist" aria-label="{say(lang, "roster.arrange", "How to arrange the roster")}" hidden>
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
  <div class="seatfld"><label for="sgo">{say(lang, "roster.go", "Go to a seat")}</label>
  <select id="sgo"><option value="">{say(lang, "roster.seat_number", "Seat number&hellip;")}</option>{opts}</select></div>
  <div class="seatfld seatfind"><label for="sq">{say(lang, "roster.find", "Find")}</label>
  <input id="sq" type="search" autocomplete="off"
    placeholder="{say(lang, "roster.find_ph", "Name, county or seat")}"></div>
</div>
<div class="seatbar">
  <p class="seathint">{say(lang, "roster.hint", "Scroll or pinch to zoom, drag to move about the floor.")}</p>
  <div class="seatzoom">
    <button type="button" id="szout" aria-label="{say(lang, "roster.zoom_out", "Show more of the floor")}">&minus;</button>
    <button type="button" id="szin" aria-label="{say(lang, "roster.zoom_in", "Show the seats larger")}">+</button>
    <button type="button" id="szfit" title="{say(lang, "roster.zoom_fit", "Zoom to fit")}">{ZOOM_FIT_ICON}</button>
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
    # (parts.TABS_JS, the .twntabs rules in app.css's shared
    # region): without JavaScript both panels are shown, each under its
    # heading; with it the strip shows, a panel's id is its address
    # (/legislators#legislators), and Back leaves the page.
    from parts import TABS_JS as TOWN_TABS_JS
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
    # Branch (OFFICIALS_HASH_JS). Since 21 November 2026 the Overview is
    # first in My Town's place, and #towns and #my-town open it with the
    # town panel over it (below).
    import officials_tabs as OT
    # THE OVERVIEW, FIRST (the owner's choice of draft A, 21 November 2026):
    # the page the section opens on, in My Town's place, which became the
    # town panel (find.js) that its "Find your town" box opens.
    import officials_overview as OV
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
    # The towns of each race, for the search on the Members-Elect tab: a reader
    # looking for the town's members-elect types the town. From the district
    # table the build wrote (districts.json), as build_members_elect reads it.
    elect_towns = {}
    if elect and (out / "districts.json").is_file():
        from build_members_elect import races_on_file
        elect_towns = {k: v["towns"] for k, v in
                       races_on_file(json.loads((out / "districts.json").read_text(encoding="utf-8")))[0].items()}
    elect_attrs = (f" data-elect{until_attrs(elect['takes_office'], today)}"
                   if elect else "")
    # The general elections on file, for the overview's Elections block: the
    # results files build_elections makes a page of each of, beside the site
    # folder as chrome.row_facts finds them.
    ov_elections = OV.elections_on_file(out.resolve().parent / "collected")
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
            ("overview", say(lang, "of.tab.overview", "Overview"), None,
             OV.overview(lang, comp=C, elect=elect, officers=officers, legs=legs, off=off,
                         today=today, facts=chrome.row_facts(), elections_list=ov_elections)),
            # WHO HOLDS THE SEATS AT THE TOP (the owner's walk of 7 November
            # 2026, C): under the presiding officers and over the roster, as
            # the Members-Elect tab's totals are over its lists; on a phone,
            # each chamber's bar and its one short line (short_bar), without
            # the legend and the thresholds (the walk of 8 November 2026).
            ("legislators", say(lang, "of.tab.legislators", "Legislators"), len(legs),
             legislator_box(lang) + OT.presiding(officers, legs, today, lang)
             + (('<div class="comp-wrap comp-top"><h2>' + say(lang, "of.who_holds", "Who holds the seats")
                 + "</h2>" + static_bar("S", lang) + static_bar("H", lang) + vacancies_box(lang)
                 + "</div>") if C else "")
             + roster_section(legs, lang)),
            # MEMBERS-ELECT BESIDE LEGISLATORS (the owner's walk of 8 November
            # 2026), the two lists of who sits now and who sits next.
            # "Members-Elect (N)", N the winners the file names: a race not
            # final counts none, and a tab of none says no number, as any tab.
            ("members-elect", say(lang, "of.tab.elect", "Members-Elect"), OT.elect_count(elect),
             OT.members_elect(elect, today, lang, [*legs, *gone], elect_towns, C)),
            ("federal", say(lang, "of.tab.federal", "Federal Delegation"),
             OT.count(off, "federal"), OT.federal(off, lang)),
            ("executive", say(lang, "of.tab.executive", "Executive Branch"),
             OT.count(off, "executive"), OT.executive(off, member_pages.__contains__, lang)),
            ("judicial", say(lang, "of.tab.judicial", "Judicial Branch"),
             OT.count(off, "judicial"), OT.judicial(off, lang)),
            # #counties, not #county: the roster's By county button is tab-county.
            ("counties", say(lang, "of.tab.counties", "County Officials"),
             OT.count(off, "county"), OT.county(off, legs, None, lang)),
        ]
        of_panes = [p for p in of_panes if p[3]]
        # SEVEN TABS ON ONE LINE (the owner, 7 November 2026): with
        # Members-Elect the strip needed 1,282px of its 1,132 at 1280 and at
        # 1440, and the new tab showed only its "M" behind the edge, in both
        # languages. The tab says the short name -- "Federal (4)", "County
        # (80)" -- and its panel's heading the whole one, which a screen
        # reader walking the headings and a page read without the script
        # still get. Measured on dry run 6 with the web fonts: 1,016px in
        # English and 971 in Spanish, of 1,132.
        short = {"federal": say(lang, "of.tab_short.federal", "Federal"),
                 "executive": say(lang, "of.tab_short.executive", "Executive"),
                 "judicial": say(lang, "of.tab_short.judicial", "Judicial"),
                 "counties": say(lang, "of.tab_short.counties", "County")}
        of_tabs = "".join(
            f'<button type="button" role="tab" id="tab-{pid}" data-pane="{pid}" '
            f'aria-controls="{pid}" aria-selected="{"true" if i == 0 else "false"}" '
            f'tabindex="{0 if i == 0 else -1}"{elect_attrs if pid == "members-elect" else ""}>'
            f'{short.get(pid, name)}'
            + (f' <span class="ofn">({n:,})</span>' if n else "") + "</button>"
            for i, (pid, name, n, _h) in enumerate(of_panes))
        of_body = "".join(
            f'<div class="twnpane" id="{pid}" role="tabpanel" aria-labelledby="tab-{pid}"'
            f'{elect_attrs if pid == "members-elect" else ""}>'
            f'<h2 class="twnph">{name}</h2>{inner}</div>'
            for pid, name, _n, inner in of_panes)
        leg_body = f"""<h1>{say(lang, "of.title", "Officials")}</h1>
<p class="lead">{say(lang, "of.lead", "Everyone who represents your town, from your select board to\nCongress; the {n} sitting members of the New Hampshire House and\nSenate; and the state&rsquo;s other officials.", n=len(legs))}</p>
{chrome.lang_note(lang)}<div class="twntabs oftabs" role="tablist" aria-label="{say(lang, "of.title", "Officials")}" data-retired="legislators" hidden>{of_tabs}</div>
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


def home_pages(out, H, S, has_lockup):
    """The home page, index.html, in each language it has, from home.json (`H`, its
    status `S`) and the key dates: Coming up, the status box, latest activity and
    the recent session days, the guides' row the last full build put there kept;
    and what the language tables and the key dates left unsaid, said.
    A step of main, lifted out of it as it stood (20 November 2026)."""
    # THE KEY DATES, worked out once for both languages and both of the
    # boxes that show them: Coming up, and the status box's next deadline.
    # SILENCE IS NOT SUCCESS: a box with no deadline says why, here.
    import key_dates as KD
    today_d = build_date.today()
    kd_events = KD.events(today_d)
    if KD.no_deadline_line(kd_events, today_d):
        print(KD.no_deadline_line(kd_events, today_d))
    static_up = calendar_html(out, today=today_d, events=kd_events)

    # WHICH SITTINGS HAVE A PAGE: Recent Session Days (recent_sessions)
    # dates each player with the way to its sitting's page where one is
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
                         recent_box(H, lang, codes, sits), recent_sessions(H, lang, sits))
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
    KD.unread()


def about_pages(out, has_lockup):
    """The About page in each language it is in, its figures counted once
    (about_figures).
    A step of main, lifted out of it as it stood (20 November 2026)."""
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
    # AND IN EACH OTHER LANGUAGE IT IS IN (i18n.PAGES; the owner, 9 November
    # 2026), at i18n.href's address, its figures counted once for both.
    about_figs_ = about_figures.figures(site=out)
    for lang in i18n.LANGS:
        if not i18n.has(lang, ABOUT_PAGE):
            continue
        dest = (out / ABOUT_PAGE if lang == i18n.DEFAULT
                else out / i18n.href(lang, ABOUT_PAGE).lstrip("/"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            shell(say(lang, "about.title", "About") + " | Granite Record", ABOUT_PAGE,
                  about_html(lang, has_lockup, about_figs_),
                  desc=say(lang, "about.desc", "How Granite Record is built, where every fact on it "
                           "comes from, and how to report something that is wrong."), lang=lang),
            encoding="utf-8")


def search_pages(out):
    """The all-results page, search.html, in each language it is in, asking not to be
    indexed.
    A step of main, lifted out of it as it stood (20 November 2026)."""
    # THE ALL-RESULTS PAGE. Served at /search -- Pages strips the extension --
    # and reached from the header panel's last row on every page of the site.
    # noindex, because what it holds depends entirely on a query string: there
    # is no page here for a crawler to keep, and every variant of it would be
    # a near-copy of the bill search and the roster, which ARE indexed.
    # AND IN EACH OTHER LANGUAGE IT IS IN (i18n.PAGES; the owner, 9 November
    # 2026): the page's own words by say(), the script's by tr() (SEARCH_JS),
    # the rows by find.js, which was already in both. Its address is
    # i18n.href's, so the form, the address bar and the header's "see all
    # results" row stay in the language (window.GR_HREFS).
    def search_html(lang):
        me = i18n.href(lang, SEARCH_PAGE).replace(".html", "")
        return f"""<h1 id="reshead">{say(lang, "sr.head", "Search the record")}</h1>
<p class="lead" id="reslead">{say(lang, "sr.lead", "Every sitting legislator and every member who has left, every committee, every town and ward, every subject bills are filed under, and every bill since 1989.")}</p>
{chrome.lang_note(lang)}<form class="resfind" action="{me}" method="get" role="search">
  <label for="resq" class="sr">{say(lang, "sr.label", "A legislator, a committee, a town, a subject or a bill")}</label>
  <input id="resq" name="q" type="search" autocomplete="off"
    placeholder="{say(lang, "find.hint", "Name, town, committee or bill")}" disabled>
</form>
<p class="sr" id="ressay" role="status"></p>
<div id="resout"></div>
<noscript><p class="note">{say(lang, "sr.noscript", 'This page needs JavaScript to search. Without it, the <a href="/bills">bill search</a>, the <a href="/officials">roster</a> and the <a href="/committees">committee list</a> are all plain pages.')}</p></noscript>"""
    # WIDE, as the roster is: a list of results is a list, and in the 820px
    # column of the prose pages it ended near the middle of a 1440px window
    # with the rest of the row empty (the review of 2 October 2026).
    for lang in i18n.LANGS:
        if not i18n.has(lang, SEARCH_PAGE):
            continue
        search_page = shell(say(lang, "sr.title", "Search") + " | Granite Record", SEARCH_PAGE,
                            i18n.lang_links(search_html(lang), lang), wide=True,
                            desc=say(lang, "sr.desc", "Search Granite Record for a legislator, a "
                                     "committee, a town, a subject or a bill."),
                            script=SEARCH_JS, lang=lang)
        search_page = re.sub(r'<link rel="canonical"[^>]*>',
                             '<meta name="robots" content="noindex,follow">', search_page, count=1)
        # A page asked not to be indexed names no alternate to a search engine.
        search_page = re.sub(r'<link rel="alternate" hreflang="[^"]*" href="[^"]*">', "", search_page)
        dest = (out / SEARCH_PAGE if lang == i18n.DEFAULT
                else out / i18n.href(lang, SEARCH_PAGE).lstrip("/"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_shell.clean_links(search_page), encoding="utf-8")


def not_found_pages(out):
    """The 404 pages, /404.html and one under each other language's folder, every
    link absolute and asking not to be indexed. Returns the bill page the English
    one offers as an example (not_found_example), or None.
    A step of main, lifted out of it as it stood (20 November 2026)."""
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
    example404 = not_found_example(out)
    page404 = shell("No page at this address | Granite Record", "", not_found_body(example404),
                    desc="There is no page at this address.")
    page404 = re.sub(r'(href|src)="(?!https?:|/|#|mailto:)([^"]+)"', r'\1="/\2"',
                     page404)
    page404 = re.sub(r'<link rel="canonical"[^>]*>',
                     '<meta name="robots" content="noindex">', page404)
    (out / "404.html").write_text(_shell.clean_links(page404), encoding="utf-8")

    # THE SPANISH 404. Cloudflare Pages answers a missing address with the
    # nearest 404.html up its path, so /es/404.html serves every missing
    # /es/... address and /404.html the rest; no rule in _redirects reaches
    # either (it holds no splat over /es/). Links are absolute, as above.
    for lang in i18n.LANGS:
        if lang == i18n.DEFAULT:
            continue
        pl = shell(say(lang, "nf.title", "No page at this address") + " | Granite Record", "",
                   not_found_body_lang(example404, lang),
                   desc=say(lang, "nf.desc", "There is no page at this address."), lang=lang)
        pl = re.sub(r'<link rel="canonical"[^>]*>', '<meta name="robots" content="noindex">', pl)
        (out / lang).mkdir(parents=True, exist_ok=True)
        (out / lang / "404.html").write_text(_shell.clean_links(pl), encoding="utf-8")
    return example404


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    chrome.use_site(out)

    has_lockup, has_mark, no_brand = brand_files_placed(out)
    front_end(out, has_mark)

    headers_and_redirects(out)

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

    officials_pages(out, legs, C)

    home_pages(out, H, S, has_lockup)

    about_pages(out, has_lockup)

    search_pages(out)

    example404 = not_found_pages(out)

    print(f"wrote officials.html ({len(legs)} members), "
          f"about.html, search.html, 404.html -> {out}/  (learn.html: build_civics.py)")
    print(f"  404.html's example: {example404}" if example404 else
          "  404.html gives no example: no bill in the index has a record to write a page from")
    if not legs:
        print("  legislators.json missing — run build_site_v2.py first")
    if no_brand:
        print(no_brand)


if __name__ == "__main__":
    main()
