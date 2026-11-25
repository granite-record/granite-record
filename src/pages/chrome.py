#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-23.18
"""
The frame every page shares, written once: the head's fonts, icons, share
card, theme script and stylesheet; the header and its sections; the footer;
and the scripts at the foot of the page.

    import chrome
    chrome.head("officials.html")      # fonts, icons, card, theme, app.css, components.js
    chrome.nav("officials.html")       # the header, that section marked as the current one
    chrome.footer()                    # the footer and the line that dates the data
    chrome.scripts()                   # the header search and the theme control's handler
    chrome.fill(template, "bills.html")    # a page's <!-- CHROME:... --> slots, filled

ONE FRAME, TWO KINDS OF PAGE (23 October 2026). The site's pages are written
two ways: shell.page() makes the 34,000 record pages from bills.html, and
build_pages.shell() writes the home page, Officials, About, /search and 404.
Each used to carry its own copy of the header, the nav and the footer --
bills.html by hand, build_pages.py in Python -- and their own comments said
so: "ONE WRAPPER, WRITTEN TWICE BECAUSE THE NAV IS". Data was once added to
one copy's nav and not the other's, and three pages lacked a link the other
34,000 had. preflight's parity checks found such drift after the fact; they
could not stop the second edit being needed.

So both emitters ask this module. bills.html carries four slots --
<!-- CHROME:head -->, <!-- CHROME:nav -->, <!-- CHROME:footer --> and
<!-- CHROME:scripts --> -- which shell.template() fills before any record page
is made from it, and which build_pages fills for the copy it publishes at
/bills; build_pages.shell() puts the same four calls where its own copy was.
A change to the header, the nav, the footer or the head's shared lines is a
change here, and it reaches every page of the site at the next build.
preflight holds that: no emitter writes the frame by hand, and every page
the fixture builds carries it.

WHAT IS NOT HERE: what differs from page to page -- the title, the
description and the canonical address (shell.page, build_pages.shell), the
skip link's words, the page's own scripts. And the stylesheet's contents:
app.css is the one stylesheet, linked here, from the root, so that the 404
page, served at any depth, finds it too.

A change to this file is a change to every page, so build_all.py's
--front-end fast path refuses it (it is a script, not one of the browser's
files): only the page steps of a full build rewrite the pages.

IN EITHER LANGUAGE (23 October 2026). head(), nav(), footer() and
scripts() take the page's language, "en" unless a page says otherwise; the
words are i18n.say()'s, with the English written here as it always was.
Every page's head also carries lang_head()'s script, which decides, before
anything is drawn, whether this reader wants the page in another language
and goes there (i18n says when a language is offered and how a translation
stays current).
"""

import html as _html
import json as _json
import re as _re

import i18n
import inline_js as IJ
from components import icon
from i18n import say

# THE SECTIONS, in the header's order, with each one's drawing (Polish 1, 9
# October 2026: the prototype kit's icon before the word, components.icon).
NAV_TABS = (("bills.html", "Bills", "bill"),
            # LAWS, BESIDE BILLS (the person, 11 October 2026: "The top level
            # nav and page urls should say Laws since that's the easiest thing
            # to understand for newcomers"). A bill proposes to change a law;
            # the two are read together. build_rsa.py writes /laws.
            ("laws.html", "Laws", "law"),
            # OFFICIALS, NOT LEGISLATORS, AND RESOURCES, NOT LEARN (the
            # person, 8 October 2026, late evening: "the polish release's five
            # tabs are Bills, Officials, Calendar, Committees, Resources"). The
            # page moved with its tab: /legislators and /learn answer with a
            # 301 to the new addresses (build_pages.MOVED).
            ("officials.html", "Officials", "person"),
            ("calendar.html", "Calendar", "calendar"),
            ("committees.html", "Committees", "gavel"),
            ("resources.html", "Resources", "book"))


def tab_words(lang="en"):
    """{href: label} of NAV_TABS in `lang`. The English is NAV_TABS's own,
    written again here so the translation can be checked against it;
    preflight holds the two to one word each (_translations)."""
    return {"bills.html": say(lang, "nav.bills", "Bills"),
            "laws.html": say(lang, "nav.laws", "Laws"),
            "officials.html": say(lang, "nav.officials", "Officials"),
            "calendar.html": say(lang, "nav.calendar", "Calendar"),
            "committees.html": say(lang, "nav.committees", "Committees"),
            "resources.html": say(lang, "nav.resources", "Resources")}


# THE SECOND ROW: EACH SECTION'S OWN PAGES (the header rows: the owner's
# approval of the prototype on 7 November 2026, and of navigation option A,
# "Section rows", on 20 November 2026). Under the six tabs, the pages of the
# section a reader is in, sentence case, the one they are on marked with the
# tab's own underline; on a phone a strip under the bar that names the
# section and scrolls sideways, and in the open menu every section with all
# its pages. AND THE FOOTER'S SITE MAP, on every page: each section with its
# row's pages, so a page two levels down -- Elections, Votes -- is one click
# from anywhere. One table, drawn by row(), menu_all() and site_map(), so the
# row, the phone menu and the footer cannot come to disagree, and drawn by
# nav() and footer_html() for both emitters -- shell.page()'s 34,000 record
# pages and build_pages.shell()'s five.
#
# Each entry is (id, address). The address is a page here, as NAV_TABS
# writes one, or a hub's tab at its existing address ("officials.html
# #legislators"): the in-page tabs of Laws, Officials and Resources are this
# row now, and every address they answered still opens them (their own
# script, parts.TABS_JS, which also follows a hashchange). A page planned and
# not built is not here; it joins the day it is.
#
# Six are drawn only while their page is written (row_facts): two seasonal --
# the bill requests, while a session's are listed and not on the days the bill
# search opens on them (requests_first), and the members-elect, between the
# election and Organization Day -- Live now, only while the owner's switch is
# on (build_live.LINKED), and three a build without their data does not write:
# the elections, the former members' list and the calendars and journals.
ROWS = {
    "bills.html": (("search", "bills.html"),
                   # VOTES IN THE BILLS ROW (the owner, 20 November 2026).
                   ("votes", "votes.html"),
                   # NOT WHILE THE SEARCH OPENS ON THEM (the owner, 24 November
                   # 2026: "2027 Bill requests does not need to be a separate
                   # tab under bills because it already opens to that page by
                   # default"): on those days row_facts leaves the requests out
                   # (requests_first), and a request's page is Search bills'
                   # (nav). On the others -- before the election, and once the
                   # requests are introduced as bills -- they have their item.
                   ("requests", "bills.html?term={term}"),
                   ("terms", "directory.html")),
    "laws.html": (("statutes", "laws.html"),
                  ("constitution", "laws.html#constitution")),
    # The tabs Officials has today, in the order of the hub the owner asked
    # for on 7 November (Legislative, Executive, Judicial, Federal, County),
    # the Overview first, the page the section opens on, in My Town's place
    # (the owner's choice of draft A, 21 November 2026: My Town is the town
    # panel now, opened from the Overview and the header); and Elections,
    # whose own trail says Officials (the owner, 20 November).
    "officials.html": (("overview", "officials.html"),
                       ("legislators", "officials.html#legislators"),
                       ("members-elect", "officials.html#members-elect"),
                       ("executive", "officials.html#executive"),
                       ("judicial", "officials.html#judicial"),
                       ("federal", "officials.html#federal"),
                       ("counties", "officials.html#counties"),
                       ("elections", "elections/index.html"),
                       ("former", "directory/former-legislators.html")),
    "calendar.html": (("week", "calendar.html"),
                      ("sessions", "session/house.html"),
                      ("live", "live.html"),
                      ("journals", "calendar/documents.html")),
    "committees.html": (("house", "committees.html#house"),
                        ("senate", "committees.html#senate"),
                        ("study", "committees.html#statstud"),
                        ("former", "committees.html#archived")),
    "resources.html": (("guides", "resources.html"),
                       ("learn", "resources.html#learn"),
                       ("glossary", "learn/glossary.html"),
                       ("sources", "resources.html#sources"),
                       ("data", "data.html")),
}

# The hubs whose row is their in-page tabs: each item there whose address is
# the hub itself names a panel (data-pane), and the row follows the panel the
# hub's script opens (find.js, rowMount) -- by an address, a link inside a
# panel, a member-elect tab handing over to Legislators on the day it retires.
TAB_HUBS = ("laws.html", "officials.html", "resources.html")

# The items drawn only while their page is written, and the fact of
# row_facts() each waits on.
COMES_AND_GOES = {("bills.html", "requests"): "requests",
                  ("officials.html", "members-elect"): "elect_until",
                  ("officials.html", "elections"): "elections",
                  ("officials.html", "former"): "former",
                  ("calendar.html", "live"): "live",
                  ("calendar.html", "journals"): "documents"}


def row_words(lang="en", year=""):
    """{(section, id): label} of ROWS in `lang`. Written out a call each, as
    tab_words is, so the catalog's checks can read every key and its English
    from the source."""
    return {
        ("bills.html", "search"): say(lang, "nav.row.bills.search", "Search bills"),
        ("bills.html", "votes"): say(lang, "nav.row.bills.votes", "Votes"),
        ("bills.html", "requests"): say(lang, "nav.row.bills.requests", "{year} bill requests",
                                        year=year),
        ("bills.html", "terms"): say(lang, "nav.row.bills.terms", "Every term"),
        ("laws.html", "statutes"): say(lang, "nav.row.laws.statutes", "Statutes (RSA)"),
        ("laws.html", "constitution"): say(lang, "nav.row.laws.constitution", "Constitution"),
        ("officials.html", "overview"): say(lang, "nav.row.officials.overview", "Overview"),
        ("officials.html", "legislators"): say(lang, "nav.row.officials.legislators", "Legislators"),
        ("officials.html", "members-elect"): say(lang, "nav.row.officials.members-elect",
                                                 "Members-elect"),
        ("officials.html", "executive"): say(lang, "nav.row.officials.executive", "Executive"),
        ("officials.html", "judicial"): say(lang, "nav.row.officials.judicial", "Judicial"),
        ("officials.html", "federal"): say(lang, "nav.row.officials.federal", "Federal"),
        ("officials.html", "counties"): say(lang, "nav.row.officials.counties", "County"),
        ("officials.html", "elections"): say(lang, "nav.row.officials.elections", "Elections"),
        ("officials.html", "former"): say(lang, "nav.row.officials.former", "Former members"),
        ("calendar.html", "week"): say(lang, "nav.row.calendar.week", "This week"),
        ("calendar.html", "sessions"): say(lang, "nav.row.calendar.sessions", "Session days"),
        ("calendar.html", "live"): say(lang, "nav.row.calendar.live", "Live now"),
        ("calendar.html", "journals"): say(lang, "nav.row.calendar.journals",
                                           "Calendars and journals"),
        ("committees.html", "house"): say(lang, "nav.row.committees.house", "House"),
        ("committees.html", "senate"): say(lang, "nav.row.committees.senate", "Senate"),
        ("committees.html", "study"): say(lang, "nav.row.committees.study", "Study and statutory"),
        ("committees.html", "former"): say(lang, "nav.row.committees.former", "Former committees"),
        ("resources.html", "guides"): say(lang, "nav.row.resources.guides", "How-to guides"),
        ("resources.html", "learn"): say(lang, "nav.row.resources.learn", "Learn"),
        ("resources.html", "glossary"): say(lang, "nav.row.resources.glossary", "Glossary"),
        ("resources.html", "sources"): say(lang, "nav.row.resources.sources", "Official sources"),
        ("resources.html", "data"): say(lang, "nav.row.resources.data", "Data and API"),
    }


# WHERE THE ROW'S COMING AND GOING PAGES ARE JUDGED FROM: the site folder
# the builders write (use_site), "site" unless a builder says otherwise.
# Judged once a run.
_SITE = ["site"]
_FACTS = {}


def use_site(site):
    """The site folder the row's coming and going pages are judged against
    (row_facts). shell.template() and build_pages call it with theirs."""
    if str(site) != _SITE[0]:
        _SITE[0] = str(site)
        _FACTS.clear()


def requests_first(meta, day):
    """Whether the bill search opens on the bill requests on `day` (a date,
    or "YYYY-MM-DD"), by meta.json (`meta`): app.js's requestsFirst, the same
    rule in the same steps, so the row and the search cannot disagree on the
    build's day -- preflight runs both over the same days
    (_row_requests_follow_the_search). From the day after the general
    election of the year before the requests' own, while one of them stands,
    the newest term is not past their session, and none has been introduced
    on a day of their own year."""
    def count(x):
        try:
            return float(x or 0)
        except (TypeError, ValueError):
            return 0.0

    def year(x):
        try:
            return int(str(x).strip())
        except ValueError:
            return None
    r = meta.get("requests") if isinstance(meta, dict) else None
    terms = (meta.get("terms") if isinstance(meta, dict) else None) or []
    if not isinstance(r, dict) or not r.get("term") or not terms:
        return False
    if not count(r.get("n")) - count(r.get("withdrawn")) > 0:
        return False
    ry, t0 = year(r.get("year") or str(r["term"])[:4]), year(str(terms[0])[:4])
    if ry is None:
        return False
    if t0 is not None and (ry < t0 or (ry == t0 and count(r.get("introduced_in_session")) > 0)):
        return False
    from build_members_elect import general_election
    return str(day)[:10] > general_election(ry - 1).isoformat()


def row_facts():
    """What the row's items that come and go need, judged once a run from
    the site folder (use_site) and the project beside it:
      "requests": {"term", "year"} of the bill requests the row draws, or
        None: where there are none, and on the days the bill search opens on
        them (requests_first, by the build's day), when Search bills is
        their list;
      "elect_until": the day the members-elect take office, or None;
      "elections": whether there are election results to build pages of;
      "former": whether any member who left has a page to list;
      "documents": whether there is a calendars' queue to list them from;
      "live": the owner's switch for Live now (build_live.LINKED).
    Each is a file a step before every page builder writes (build_all:
    build_site_v2's former.json, build_members_elect's file, build_lsrs'
    key in meta.json) or the source a later step builds its page from (the
    election results build_elections reads, the calendars' queue, which
    build_calendar reads), so every page of a run draws the same row, menu
    and footer, and none links a page the run did not write -- check_site
    would call it broken and hold the night."""
    if _FACTS:
        return _FACTS
    from pathlib import Path
    site = Path(_SITE[0])
    root = site.resolve().parent

    def read(p, default):
        try:
            return _json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default
        except ValueError:
            return default
    meta = read(site / "meta.json", {}) or {}
    r = meta.get("requests")
    req = ({"term": r["term"], "year": str(r.get("year") or str(r["term"])[:4])}
           if isinstance(r, dict) and r.get("term") else None)
    if req:
        import build_date
        if requests_first(meta, build_date.today()):
            req = None
    # A members-elect file that will not read stops each builder that draws
    # the members-elect, which says why (build_members_elect.for_pages); the
    # header leaves their item out rather than stopping every other page too.
    # And what for_pages prints is those builders' to say, once each, as the
    # night's checks count it: the header asks quietly.
    try:
        import contextlib
        import io
        from build_members_elect import for_pages
        with contextlib.redirect_stdout(io.StringIO()):
            elect = for_pages(site)
        until = elect["takes_office"] if elect else None
    except (ImportError, SystemExit):
        until = None
    former = any(isinstance(m, dict) and m.get("slug") for m in (read(site / "former.json", []) or []))
    _FACTS.update({"requests": req, "elect_until": until,
                   "elections": any((root / "collected").glob("election_*.json")),
                   "former": former, "documents": (root / DOCUMENTS_QUEUE).is_file(),
                   "live": live_linked()})
    return _FACTS


# NOT IMPORTED, READ. calendar_documents and build_live import shell, which
# imports this module, so importing either here would tie the page builders
# into one import cycle (preflight's _import_cycles_cut). So the calendars'
# queue is named here as calendar_documents.QUEUE names it -- build_calendar
# writes the list wherever the queue lists a document, and check_site holds a
# night whose queue lists none -- and the owner's switch for Live now is read
# from build_live.py's own line, where it stays the one place it is set.
# preflight holds both to the modules' own (_row_comes_and_goes).
DOCUMENTS_QUEUE = "archive/queue.csv"
_LINKED_LINE = _re.compile(r"^LINKED = (True|False)\s*$", _re.M)


def live_linked():
    """build_live.LINKED, the owner's switch for Live now, read from the line
    in build_live.py that sets it."""
    import _paths
    m = _LINKED_LINE.search(_paths.locate("build_live.py").read_text(encoding="utf-8"))
    assert m, "build_live.py no longer sets LINKED on a line of its own"
    return m.group(1) == "True"


def _split(address):
    """("officials.html", "#legislators"): an address's page and the rest."""
    for i, ch in enumerate(address):
        if ch in "?#":
            return address[:i], address[i:]
    return address, ""


def row_items(section, lang="en", facts=None):
    """[(id, label, href, extra attributes, English only)] of `section`'s
    row: the ones that come and go only while their page is written, every
    address `lang`'s page where it has one (i18n.href) and the English page
    where not, which the last field says."""
    f = row_facts() if facts is None else facts
    req = f.get("requests")
    words = row_words(lang, (req or {}).get("year", ""))
    out = []
    for iid, addr in ROWS.get(section, ()):
        wait = COMES_AND_GOES.get((section, iid))
        if wait and not f.get(wait):
            continue
        extra = ""
        if iid == "requests":
            addr = addr.format(term=req["term"])
        if iid == "members-elect":
            from components import until_attrs
            import build_date
            extra = f" data-elect{until_attrs(f['elect_until'], build_date.today().isoformat())}"
        page, rest = _split(addr)
        href = (page if lang == i18n.DEFAULT else i18n.href(lang, page)) + rest
        if section in TAB_HUBS and page == section:
            extra += f' data-pane="{iid if rest else ROWS[section][0][0]}"'
        elif page == section and rest.startswith("#"):
            extra += f' data-hash="{rest}"'
        out.append((iid, words[(section, iid)], href, extra, not i18n.has(lang, page)))
    return out


def written(address, facts=None):
    """Whether this run writes the page at `address` ("/calendar/documents.html"),
    as far as the row can tell: what row_facts() says of a page of its own
    that an item which comes and goes leads to (COMES_AND_GOES), and True of
    every other address, which the row does not judge. For a link to such a
    page from outside the row -- a guide's source row naming the calendars
    and journals, whose page is written only where the queue lists one
    (build_civics.sources_list, 25 November 2026) -- so that a build that
    writes no such page, a fork's or the fixture's, links none."""
    f = row_facts() if facts is None else facts
    p = _split(address.strip())[0].lstrip("/")
    page = p if p.endswith(".html") else (f"{p}index.html" if p.endswith("/") or not p else f"{p}.html")
    for (section, iid), wait in COMES_AND_GOES.items():
        for i, addr in ROWS.get(section, ()):
            own = _split(addr)[0]
            if i == iid and own == page and own != section:
                return bool(f.get(wait))
    return True


def _in_english(lang, english):
    """After a link to a page that is English only, on a page in another
    language: "(en inglés)", as the hub's lists mark one (the owner, 20
    November 2026: in the footer's map and the phone's menu, not the row)."""
    if not english or lang == i18n.DEFAULT:
        return ""
    return ' <span class="r-en">(' + say(lang, "guides.in_english", "in English") + ")</span>"


def _link(href, extra, label, current=False, lang="en", english=False):
    """One page of a row, the menu or the footer: hreflang="en" where it is
    English on a page that is not, and its mark where the menu or the footer
    says so (_in_english)."""
    hl = ' hreflang="en"' if english and lang != i18n.DEFAULT else ""
    cur = ' aria-current="page"' if current else ""
    return f'<a href="{href}"{extra}{hl}{cur}>{label}</a>'


def locate(path, g=None):
    """(section, item) a page at `path` ("/legislator/x.html") belongs to,
    by its address and, for a member, by whether they still sit (g, the
    page's globals): ("", "") for a page in no section, and an item of ""
    for a page in a section and none of its row's items -- the home page,
    About, /search and the 404 page are in none. The record pages' rule, set
    out in the header rows' brief: a bill's page is Bills' search, a chapter
    of the statutes Laws' Statutes, a member's page Legislators or Former
    members, a committee's its chamber or Study and statutory, a session day
    and the votes not on a bill Session days, a week This week, a guide
    How-to guides, a Learn page Learn, an election's page Elections."""
    g = g or {}
    p = path.lstrip("/")
    if p.startswith("es/"):
        p = p[3:]
    p = p[:-5] if p.endswith(".html") else p
    p = p.rstrip("/")
    if p.endswith("/index"):
        p = p[:-len("/index")]
    top, _, rest = p.partition("/")
    if p in ("", "index", "about", "search", "404"):
        return "", ""
    if top == "request":
        return "bills.html", "requests"
    if top in ("bills", "bill"):
        return "bills.html", "search"
    if top == "votes":
        return "bills.html", "votes"
    if top == "directory":
        if not rest:
            return "bills.html", "terms"
        if rest.endswith("-requests"):
            return "bills.html", "requests"
        if rest.startswith("bills-"):
            return "bills.html", "terms"
        if rest == "legislators":
            return "officials.html", "legislators"
        if rest == "former-legislators":
            return "officials.html", "former"
        if rest.startswith("sessions-"):
            return "calendar.html", "sessions"
        return "officials.html", "overview"  # every town and ward
    if top == "laws":
        return "laws.html", "statutes"
    if top in ("officials", "legislators"):
        return "officials.html", "overview"
    if top == "elections":
        return "officials.html", "elections"
    if top == "legislator":
        if g.get("GR_FORMER"):
            return "officials.html", "former"
        return "officials.html", "legislators"
    # A town's page is found from the Overview's "Find your town" (My Town,
    # until 21 November 2026, when it became the town panel).
    if top == "town":
        return "officials.html", "overview"
    if top == "calendar":
        return "calendar.html", "journals" if rest.startswith("documents") else "week"
    if top == "session":
        return "calendar.html", "sessions"
    if top == "live":
        return "calendar.html", "live"
    if top in ("committees", "committee"):
        # By the code in the address, in either case (committee/s42 is the
        # Senate's): ss is a statutory or study committee, then H or S.
        code = rest.lower()
        if code.startswith("ss"):
            return "committees.html", "study"
        if code.startswith("s"):
            return "committees.html", "senate"
        if code.startswith("h"):
            return "committees.html", "house"
        return "committees.html", ""
    if top in ("resources", "guides"):
        return "resources.html", "guides"
    if top == "learn":
        return "resources.html", "glossary" if rest == "glossary" else "learn"
    if top in ("data", "api"):
        return "resources.html", "data"
    return "", ""


def row(section, item=None, lang="en", facts=None):
    """The second row: `section`'s pages, `item` marked as the one a reader
    is on. Empty for a page in no section. A <nav> of its own, named for the
    section, after the header's, so a screen reader's landmarks say "Bills,
    navigation" for it; the section's name is drawn too, for the phone's
    strip, and hidden from a screen reader there, which has the landmark's.
    Plain links: Tab moves through them, and no arrow keys to learn. The row
    leads to the English page where there is no other and does not say so:
    the footer's map and the phone's menu do, where there is room."""
    items = row_items(section, lang, facts)
    if not section or not items:
        return ""
    name = _html.escape(tab_words(lang)[section])
    links = "".join(_link(href, extra, label, iid == item, lang, en)
                    for iid, label, href, extra, en in items)
    return (f'<nav class="subnav" aria-label="{name}" data-section="{section}"><div class="in">'
            f'<span class="sublab" aria-hidden="true">{name}</span>'
            f'<div class="subrow">{links}</div></div></nav>')


def menu_all(page="", item=None, lang="en", facts=None):
    """The phone's open menu: every section as a heading link, its pages
    under it in two columns (app.css hides it from 45em, where the tabs and
    the row do this). Folded into .navdrop beside the tabs, so the one menu
    button opens both, and the tabs alone are hidden there."""
    cur = ' aria-current="page"'
    words = tab_words(lang)
    to = (lambda h: h) if lang == i18n.DEFAULT else (lambda h: i18n.href(lang, h))
    out = []
    for href, _label, glyph in NAV_TABS:
        pages = "".join(_link(h, extra, label + _in_english(lang, en), href == page and iid == item,
                              lang, en)
                        for iid, label, h, extra, en in row_items(href, lang, facts))
        out.append(f'<div class="nvsec"><a class="nvhead" href="{to(href)}"'
                   f'{cur if href == page and not item else ""}>{icon(glyph)}{words[href]}</a>'
                   f'<div class="nvpages">{pages}</div></div>')
    return '<div class="navall">' + "".join(out) + "</div>"


def _elect_part(extra):
    """The members-elect's data-elect and the day they retire, which in the
    footer's map the list item carries, not the link, so that taking out each
    element that carries data-elect leaves no empty item behind (as the
    night's members-elect checks take them out)."""
    if not extra.startswith(" data-elect"):
        return ""
    i = extra.find(" data-pane")
    return extra if i < 0 else extra[:i]


def site_map(lang="en", facts=None):
    """The footer's map of the site: the six sections as headings, each with
    its row's pages (the owner, 20 November 2026). The same on every page --
    nothing in it is marked as the page a reader is on -- and drawn from
    ROWS, as the row and the menu are. On a phone each section folds under
    its heading (find.js, smapMount); without the script every one is open.
    Its headings are the serif over the links' sans, so they outrank what
    they head."""
    words = tab_words(lang)
    to = (lambda h: h) if lang == i18n.DEFAULT else (lambda h: i18n.href(lang, h))
    cols = []
    for href, _label, _glyph in NAV_TABS:
        stem = href[:-5]
        items = "".join(f"<li{_elect_part(extra)}>"
                        f"{_link(h, extra[len(_elect_part(extra)):], label + _in_english(lang, en), False, lang, en)}</li>"
                        for _iid, label, h, extra, en in row_items(href, lang, facts))
        cols.append(f'<div class="smcol"><h2 class="smh" id="fm-{stem}"><a href="{to(href)}">'
                    f'{words[href]}</a></h2><ul id="fm-{stem}-pages" aria-labelledby="fm-{stem}">'
                    f"{items}</ul></div>")
    label = _html.escape(say(lang, "foot.map", "Every page"))
    return f'<nav class="smap" aria-label="{label}">' + "".join(cols) + "</nav>"

# THE REPOSITORY, NAMED ONCE. The footer links it, and so do the Data page
# and "How this is made" -- three places for three different readers, and one
# constant so a move cannot leave two of them pointing at nothing.
REPO = "https://github.com/granite-record/granite-record"

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600'
         '&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Playfair+Display:wght@600'
         '&family=IBM+Plex+Mono:wght@500&display=swap" rel="stylesheet">')

# THE SITE'S SLOGAN (the owner, 24 October 2026, in place of "Public
# Records, Made Findable."): the home page's line under the logo, the home
# page's title and so the headline of a shared link to it, and the line the
# logo card carries under the drawing (build_brand.OG_SECTIONS["og.png"]).
# The home page asks the catalog for it in its own words, so preflight holds
# each of those to this one (_slogan_one_line).
SLOGAN = "New Hampshire government, in one place."

# THE CARD A SHARED LINK UNFURLS INTO, by kind of page (build_brand.py draws
# them); the logo card, the slogan under the drawing, for every page not named
# here. shell.page() puts each record's own kind's card in place of the
# template's, which is the bills section's.
CARDS = {"officials.html": ("og-legislator.png", "legislators and their voting records"),
         "bills.html": ("og-bill.png", "bills, votes and hearings")}

# THE MARK. assets/ holds the files and build_pages.py copies them into
# site/. The og tags name the card above; shell.page() replaces them per page.
_BRAND = """<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="icon" href="/icon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/icon-180.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#E9EAEC" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#171B1C" media="(prefers-color-scheme: dark)">
<meta property="og:image" content="{img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{alt}">
<meta name="twitter:image" content="{img}">"""

# THE PAGE'S LANGUAGE, BEFORE THE FIRST PAINT (23 October 2026; i18n.py says
# how the languages are kept and when one is offered). First in the head, so
# a reader who is going elsewhere is sent before anything is fetched or
# drawn. OFFER is the languages offered to everyone; LANGS every language
# the site is built in.
#
# WHICH LANGUAGE THIS READER WANTS, AND WHETHER THIS PAGE HAS IT. The
# reader's choice (Settings, kept as gr-lang) wins; without one, the first
# of the browser's languages the site has. A page in another language names
# itself on <html> as data-alt-<code>, and a reader who wants that language
# is sent there -- from a chosen language always, from the browser's only
# off an English page, since a reader who opens a Spanish page they were
# sent has asked for it. A language not yet offered to everyone moves nobody
# until the reader has opened one of its pages (gr-lang-seen), which is how
# the person and the proofreader try it. html.langs shows the language
# control and the footer's list. A link marked data-setlang makes its
# language the reader's choice as it is followed; so does a language chosen
# in the footer's list (data-footlang, 24 October 2026), which then goes to
# this page in that language, or that language's home page. The comments are
# here and not in the script, which is on every one of 34,000 pages.
# The script itself is inline/chrome.lang_head.js, whose holes lang_head() fills.


def notice_words():
    """{code: {label, text, home, close}}: what a page in English says to a
    reader who wants another language -- the settings row's word for
    "Language", and the notice that the page is not yet in theirs (find.js,
    langNotice) -- each in that language, from its catalog, since the page's
    own words are English."""
    return {c: {"label": say(c, "set.lang", "Language"),
                "text": say(c, "notice.text", "This page is not yet in Spanish."),
                "home": say(c, "notice.home", "Go to the home page in Spanish"),
                "close": say(c, "notice.close", "Close")}
            for c in i18n.LANGS if c != i18n.DEFAULT}


def lang_head():
    """The language script (inline/chrome.lang_head.js) with the site's
    languages, the ones offered to everyone and the words a reader of each is
    shown on an English page."""
    offer = [c for c in i18n.LANGS if i18n.offered(c)]
    notice = _json.dumps(notice_words(), ensure_ascii=False, separators=(",", ":"))
    return ("<script>\n" + IJ.script("chrome.lang_head", OFFER=_json.dumps(offer),
                                     LANGS=_json.dumps(list(i18n.LANGS)),
                                     NOTICE=notice.replace("</", "<\\/"))
            + "</script>")


# THE THEME CONTROL, in three pieces: the script that runs before the first
# paint, the button in the header, and the handler at the foot of the page.
THEMER_HEAD = "<script>\n" + IJ.script("chrome.themer_head") + "</script>"

THEMER_BTN = ('<button class="themer" id="themer" type="button" hidden><svg class="thsun" '
              'viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="3.6"/><path '
              'd="M10 1.8v2.2M10 16v2.2M1.8 10h2.2M16 10h2.2M4.2 4.2l1.6 1.6M14.2 14.2l1.6 1.6M4.2 '
              '15.8l1.6-1.6M14.2 5.8l1.6-1.6"/></svg><svg class="thmoon" viewBox="0 0 20 20" '
              'aria-hidden="true"><path d="M16.4 12.4A7 7 0 0 1 7.6 3.6a7 7 0 1 0 8.8 8.8z"/></svg>'
              '<span class="thword">Light</span></button>')

THEMER_JS = "<script>\n" + IJ.script("chrome.themer") + "</script>"

# The menu button a phone header carries. The SEARCH button is not here --
# find.js mounts its own, and a second one would be two controls doing one job.
MENU_BTN = ('<button class="navmenu" id="navmenu" type="button" aria-expanded="false" '
            'aria-controls="navdrop" aria-label="Sections"><svg viewBox="0 0 20 20" fill="none" '
            'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true">'
            '<path d="M3.2 6h13.6M3.2 10h13.6M3.2 14h13.6"/></svg></button>')


def menu_btn(lang="en"):
    """MENU_BTN, named in `lang`."""
    return MENU_BTN.replace('aria-label="Sections"',
                            f'aria-label="{_html.escape(say(lang, "nav.sections", "Sections"))}"', 1)

# WHAT A POWER USER NEEDS, IN THE FOOTER, WHERE THEY WILL LOOK FOR IT. The
# line says when the data was last rebuilt: a reader deciding whether to trust
# a status should not have to go to the home page to find out how old it is.
# Read from build.json rather than baked in, because the page steps run before
# build.json is written -- a baked stamp would always be a few minutes early
# and would differ page to page. It is one small cached request, and the line
# simply does not appear if the fetch fails.
FOOT_JS = "<script>" + IJ.script("chrome.foot") + "</script>"

def tr_report(lang):
    """On a page in another language, the button that reports a mistake in
    its translation (the owner, 24 October 2026: "We should also add a
    report button for translation inaccuracy."). Hidden as written:
    components.js shows it, and opens the box it sends from, so a page read
    without JavaScript keeps the address above it instead."""
    if lang == i18n.DEFAULT:
        return ""
    return ('\n<p class="trrep"><button type="button" class="trbtn" data-trreport hidden>'
            + say(lang, "foot.tr_report", "See a mistake in the translation? Tell us")
            + "</button></p>")


# WHAT STAYS IN ENGLISH, AND WHY, SAID ONE WAY ON EVERY PAGE IN ANOTHER
# LANGUAGE (the laptop manager session, 7 November 2026; the wording, English
# and Spanish, approved by the owner as drafted: "fine as is for now", on her
# translator friend's word, and still draft for the Latino caucus's review).
# A native Spanish speaker who read the Spanish pages for
# the owner on 6 November found them natural and accurate, but could not
# tell why some parts were translated and others, a bill's legal text among
# them, were not. Four pages said it four ways (home.lang_note,
# guides.lang_note, guides.hub_lang_note, learn.lang_note), and none said
# why. Now one line under the title on every such page -- home, Officials,
# Resources, the glossary, each guide and Learn page -- and under it an
# opener with the four reasons. The inline "(en inglés)" markers where a
# list names an English page stay as they are.
def lang_note(lang):
    """The line under a page's title in another language, and the opener
    under it saying what on the site stays in English and why; "" in
    English."""
    if lang == i18n.DEFAULT:
        return ""
    why = [say(lang, "lang.why_record", "The official record stays in English. Bill titles and "
               "text, the laws, each bill&rsquo;s history, votes and committee reports are the "
               "General Court&rsquo;s official record, which is written in English. Translating "
               "legal wording can change what it means, so the site shows it as written."),
           say(lang, "lang.why_names", "Names of people, committees and towns stay as the record "
               "prints them; where a committee is given a Spanish name, its English name is "
               "beside it. Search finds subjects by their English words (housing, not "
               "vivienda)."),
           say(lang, "lang.why_links", "Official state pages the site links to are in English."),
           say(lang, "lang.why_not_yet", "Not translated yet: the pages for bills, legislators, "
               "committees and the laws, and any page marked &ldquo;in "
               "English&rdquo; where it is listed.")]
    return ('<div class="langnote"><p>'
            + say(lang, "lang.note", "This page is in Spanish. Some parts stay in English on "
                  "purpose, and some pages aren&rsquo;t translated yet.")
            + '</p><details class="langwhy"><summary>'
            + say(lang, "lang.why", "Why some parts are in English")
            + "</summary><ul>" + "".join(f"<li>{w}</li>" for w in why) + "</ul></details></div>")


# The footer. The line under the attribution is the person's own credit, asked
# for on 7 October 2026: who makes the site, quietly, and the way to About.
# In either language (footer_html), and FOOTER is the English, which every
# English page carries.
#
# THE LANGUAGE LINE, under the columns: every language, each in its own
# words, for a reader who does not read this one. It is hidden until
# lang_head()'s script finds the language offered to this reader (html.langs), and on a
# Spanish page it leads to the page's English and back.
#
# A LIST TO CHOOSE FROM (the owner, 24 October 2026: "make the footer
# language change look more interactive like a dropdown to select
# language"): a globe, "Language · Idioma" in every language the site has,
# and a select holding each language by its own name, this page's chosen.
# Choosing one goes to this page in it (data-href), or to that language's
# home page where this page has no version in it, and makes it the reader's
# choice, as Settings' list does (lang_head()).
def footer_html(lang="en", alt=None, facts=None):
    """The footer in `lang`. `alt` is {code: address} of this page in the
    other languages; a page that has no other is offered the other
    language's home page. Above its columns, the map of the site
    (site_map), whose pages that come and go are row_facts()'s, or
    `facts`, which only a check gives."""
    opts = []
    for code in i18n.LANGS:
        to = ("" if code == lang
              else (alt or {}).get(code) or i18n.href(code, "index.html"))
        opts.append(f'<option value="{code}" lang="{code}" data-href="{to}"'
                    f'{" selected" if code == lang else ""}>{i18n.NAMES[code]}</option>')
    # "Language" in this page's words, then in each other language's.
    said = [say(lang, "set.lang", "Language")]
    said += [w for w in (say(c, "set.lang", "Language") for c in i18n.LANGS if c != lang)
             if w not in said]
    return f"""<footer><div class="in">
{site_map(lang, facts)}
<div class="fcols">
<div class="fcol">
<p class="fcolhead">Granite Record</p>
<p class="attrib">{say(lang, "foot.attrib", "Built from public records published by the <b>New Hampshire General Court</b>. Not affiliated with the General Court, and not a substitute for it &mdash; where this site and the Court&rsquo;s own record disagree, the Court is right and we want to know.")}</p>
<p class="footby">{say(lang, "foot.by", "An independent project by Alice Wade")} &middot; <a href="{i18n.href(lang, "about.html").lstrip("/")}">{say(lang, "foot.about", "About")}</a></p>
<p class="logocredit">{say(lang, "foot.logo", "Logo drawn by Debra Caplan, an artist in Peterborough, NH")}
&middot; <a href="https://www.linescapesnh.com/" rel="noopener">linescapesnh.com</a></p>
</div>
<div class="fcol">
<p class="fcolhead">{say(lang, "foot.record", "The record")}</p>
<ul class="flinks">
<li><a href="data.html">{say(lang, "foot.data", "Bulk data")}</a></li>
<li><a href="{i18n.href(lang, "learn/glossary.html").lstrip("/")}">{say(lang, "foot.glossary", "Glossary")}</a></li>
<li><a class="out" href="{REPO}" target="_blank" rel="noopener">{say(lang, "foot.source", "Source on GitHub")}</a></li>
</ul>
</div>
<div class="fcol">
<p class="fcolhead">{say(lang, "foot.tell", "Tell us")}</p>
<a class="fbk out" href="https://forms.gle/PYw9c3xgpDDwvX7E9" target="_blank"
 rel="noopener">{say(lang, "foot.think", "What do you think?")}</a>
<p class="fbknote">{say(lang, "foot.new", "The site is new and being tested. Found an error?")}
<a href="mailto:contact@graniterecord.org">contact@graniterecord.org</a></p>{tr_report(lang)}
</div>
</div>
<div class="footlang"><label class="footlangl" for="footlang">{icon("globe")}<span>{" · ".join(said)}</span></label>
<select id="footlang" data-footlang>{"".join(opts)}</select></div>
<p class="footdata"><span id="built"></span><span class="lic">{say(lang, "foot.licence", "Open source (MIT License)")}</span></p>
</div></footer>"""


# FOOTER, the English footer, is drawn when it is asked for (__getattr__,
# below): its map holds the pages that come and go as this run's site has
# them (row_facts), which a constant made when the module was first
# imported could not know.


def __getattr__(name):
    """chrome.FOOTER: footer_html("en"), drawn for this run's site."""
    if name == "FOOTER":
        return footer_html("en")
    raise AttributeError(f"module 'chrome' has no attribute {name!r}")

# The one stylesheet, from the root, and the components every page's scripts
# use, loaded before any of them.
STYLESHEET = '<link rel="stylesheet" href="/app.css">'
COMPONENTS_JS = '<script src="/components.js"></script>'
# The header's search, on every page: its own file, deferred.
FIND_JS = '<script src="/find.js" defer></script>'

SLOTS = ("head", "nav", "footer", "scripts")


def card(page=""):
    """(image file, its alt text) of the card a link to `page` unfurls into."""
    img, what = CARDS.get(page, ("og.png", SLOGAN.rstrip(".")))
    return img, f"Granite Record: {what}"


def head(page="", lang="en", scripts=()):
    """The head's shared lines: the language script, the fonts, the icons
    and theme colours, the share card for `page`'s kind, the theme's
    pre-paint script, the one stylesheet and components.js -- in that order,
    the language first so a reader bound elsewhere goes before anything is
    fetched, and the stylesheet after the theme so a chosen theme is set
    before anything is drawn.

    A page in another language also carries, before components.js, the
    words its scripts ask tr() for (i18n.page_words): `scripts` is the text
    of the page's own scripts, beside the frame's, which are added here; the
    shared scripts' words are a file of their own (i18n.SHARED_SCRIPTS)."""
    img, alt = card(page)
    brand = _BRAND.format(img=f"https://graniterecord.org/{img}", alt=_html.escape(alt, quote=True))
    words = i18n.page_words(lang, THEMER_JS, FOOT_JS, *scripts)
    return "\n".join(x for x in (lang_head(), words, FONTS, brand, THEMER_HEAD, STYLESHEET,
                                 COMPONENTS_JS) if x)


def nav(page="", home=False, lang="en", item=None, facts=None):
    """The header: the wordmark, the six sections with `page`'s marked as
    the one a reader is on, the theme control and the phone's menu button;
    then the second row, that section's own pages with `item` marked (row).

    `page` is a section ("officials.html") or any page a section holds
    ("data.html", which is Resources'); `item` is the row's id, which
    locate() gives a record page from its address, "" for none of them and
    None to have it worked out from `page`. `facts` are row_facts(), given
    only by a check.

    THE HOME PAGE HAS NO TAB, so the brand carries the "you are here" for it
    (home=True) -- said to a screen reader, not drawn, because the chip that
    marks a tab is scoped to .navtabs and the brand is not one.

    .navtabs exists so the strip wraps as one unit; .navdrop wraps the
    sections and the theme control so a phone can fold both behind one button
    without the markup being written twice (app.css, THE HEADER TABS). On a
    phone the folded panel shows .navall, every section with its pages,
    instead of the tabs alone (menu_all).

    In another language the words are that language's and every link is to
    the page in it where there is one (i18n.href), the English page where
    there is not."""
    cur = ' aria-current="page"'
    section = section_of(page)
    if item is None and section and section != page:
        item = locate("/" + page)[1]
    if item is None and section and section == page and ROWS[section][0][1] == section:
        # A section's own page is its first row item -- the search, This
        # week, a hub's first tab -- where that item is the page itself.
        # Committees' first is a heading on it (#house), and the page is all
        # four of its items at once, so none is marked until an address names
        # one (find.js, rowMount).
        item = ROWS[section][0][0]
    if item == "requests" and not (row_facts() if facts is None else facts).get("requests"):
        # A request's page, on the days the bill search opens on the
        # requests and the row draws no item of their own (row_facts): their
        # list is Search bills'.
        item = ROWS["bills.html"][0][0]
    words = tab_words(lang)
    to = (lambda h: h) if lang == i18n.DEFAULT else (lambda h: i18n.href(lang, h))
    tabs = "\n".join(f'<a href="{to(href)}"{cur if href == section else ""}>{icon(glyph)}{words[href]}</a>'
                     for href, _label, glyph in NAV_TABS)
    brand_cur = cur if home else ""
    sections = _html.escape(say(lang, "nav.sections", "Sections"))
    return (f'<nav class="top" aria-label="{sections}"><div class="in">\n'
            f'<a class="brand" href="{to("index.html")}"{brand_cur} translate="no">Granite Record</a>\n'
            f'<div class="navdrop" id="navdrop"><div class="navtabs">{tabs}</div>\n'
            f'{menu_all(section, item, lang, facts)}\n'
            f'{THEMER_BTN}</div>\n'
            f'{menu_btn(lang)}\n'
            '</div></nav>' + row(section, item, lang, facts))


def section_of(page):
    """The section `page` is in: itself where it is a tab, else the one whose
    row holds it, else the one locate() puts it in; "" for none."""
    if not page:
        return ""
    if page in {h for h, _l, _g in NAV_TABS}:
        return page
    for sec, items in ROWS.items():
        if any(_split(a)[0] == page for _i, a in items):
            return sec
    return locate("/" + page)[0]


# THE HEADER, WHOLE: the top bar and the row after it, as nav() writes them,
# so that a page made from a template can have its header drawn again for
# the page it is (shell.page).
NAV_RE = _re.compile(r'<nav class="top".*?</nav>(?:<nav class="subnav".*?</nav>)?', _re.S)


def footer(lang="en", alt=None):
    """The footer, and the script that puts the data's date in it."""
    return f"{footer_html(lang, alt)}\n{FOOT_JS}"


def scripts(lang="en"):
    """The scripts every page ends with: the header search and the theme
    control's handler. A page's own scripts go after them. The same in
    every language: what they say comes from the page's words."""
    return f"{FIND_JS}\n{THEMER_JS}"


def fill(t, page="", lang="en", page_scripts=(), alt=None):
    """`t` with its <!-- CHROME:... --> slots filled for `page`. A slot that
    is missing raises: a template that has lost one would be a site with no
    header, or no footer, on 34,000 pages, and nothing else would say so. A
    template with none left is returned as it came, so filling twice is
    harmless.

    IN ANOTHER LANGUAGE (the Calendar, 9 November 2026): the head, header and
    footer are `lang`'s, `page_scripts` the text of the page's own scripts (whose
    tr() words the head carries) and `alt` {code: address} the page's
    versions in the other languages, which the footer's language list leads
    to."""
    if not any(f"<!-- CHROME:{s} -->" in t for s in SLOTS):
        return t
    parts = {"head": head(page, lang, page_scripts), "nav": nav(page, lang=lang),
             "footer": footer(lang, alt), "scripts": scripts()}
    for s in SLOTS:
        slot = f"<!-- CHROME:{s} -->"
        assert t.count(slot) == 1, (
            f"the template has {t.count(slot)} of {slot}, not one: every page made from "
            "it would be missing that part of the frame, or carry it twice")
        t = t.replace(slot, parts[s], 1)
    return t
