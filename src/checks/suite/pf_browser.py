#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.26
"""
preflight's checks of the browser's scripts (app.js, find.js, components.js, map.js).

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import _paths

from pf_core import (_in_suite, _run, _source, _suite_files, check)
from pf_fixture import (CHAIN_NEEDS, _fixture_site_shared)
from pf_harness import (_app_js, _node_app, _node_file, _with_components)
from pf_shared import (_CAL_DOM, _HEARD_PRELUDE, _STATUSCAT_HARNESS, _STATUS_CATEGORY,
                       _STATUS_CATS, _SUMMARY_VOTES, _bill_index_write, _cal_fixture, _cal_node,
                       _css_decls, _css_rules, _elect_absent, _elect_blocks, _elect_built,
                       _elect_card, _fixture_drawn, _front_sources, _line_of, _map_data,
                       _officials_now, _site_bills, _strip_js_comments, page_source)


@check("frontend", "the Bill Text tab asks for a version index only where one exists")
def _version_index_gate():
    """29,841 bill pages printed an error about a file that was never written.

    build_bill_versions writes /versions/<year>/<ID>.json for a bill with more
    than one version or with amendments, and for no other: 1,087 of the 33,030
    records that draw a Bill Text tab. The tab is drawn far more widely,
    because a bill with one version and no amendments still has text and that
    text is in the record. So the pane asked for the index on all of them and
    printed "The versions of this bill could not be loaded. HTTP 404" on the
    29,841 that were never going to have one -- in a warning box, directly
    above the bill text that had loaded perfectly well.

    The record knows: (nver > 1 || namd) was true for exactly the 1,087 with a
    file, 0 false either way across the whole built site. hasVersionIndex is
    that predicate, and both the render and the fetch consult it.
    """
    p = Path("src/pages/app.js")
    if not p.exists():
        return "skip", "app.js not in this directory"
    t = _source(p)
    assert "function hasVersionIndex(" in t, (
        "app.js has no hasVersionIndex: the Bill Text pane would ask for a "
        "version index on every bill that draws the tab, and report a 404 on "
        "the nine tenths that never had one")
    i = t.find("function renderVersions(")
    assert i > 0, "renderVersions is gone"
    head = t[i:i + 700]
    err = "The versions of this bill could not be"
    assert "hasVersionIndex" in head, (
        "renderVersions no longer consults hasVersionIndex")
    assert head.index("hasVersionIndex") < head.index(err), (
        "renderVersions reports the index missing before it asks whether one "
        "was ever meant to exist")
    j = t.find("function needVersions(")
    assert j > 0 and "hasVersionIndex" in t[j:j + 700], (
        "needVersions fetches without consulting hasVersionIndex, so the 404 "
        "is requested even where the pane no longer shows it")
    return "ok", "the record decides, and it is right 33,030 times out of 33,030"


@check("frontend", "a bill with one printing shows its text in the Bill Text tab, in the list too")
def _bill_text_in_its_tab():
    """The other half of the check above. With no version history the pane
    rendered nothing, and the bill's text was drawn only below the tabs, only
    for the bill a page is focused on -- so a card opened in the bills list
    showed an empty Bill Text tab on every bill with one printing and no
    amendments, which is most of the record (the person, 24 September:
    "sometimes just doesn't display anything"). The pane now carries the text
    for such a bill, and the block below the tabs is kept for bills with a
    version history only, so nothing is drawn twice."""
    p = Path("src/pages/app.js")
    if not p.exists():
        return "skip", "app.js not in this directory"
    t = _source(p)
    assert "function billTextSection(" in t, "app.js has no billTextSection"
    assert "hasVersionIndex(d)?renderVersions(b,d):billTextSection(" in t, (
        "the Bill Text pane no longer draws the text of a bill with no version "
        "history, so it opens empty in the bills list")
    i = t.find("const btsec=")
    # Since 10 October 2026 nothing is drawn under the tabs at all: the
    # text is the Bill Text tab's (option E, the summary taking its tab).
    assert i > 0 and (t[i:].startswith('const btsec="";') or "hasVersionIndex(d)" in t[i:i + 200]), (
        "the text below the tabs is drawn for bills whose tab already holds it, "
        "so a one-printing bill's text appears twice on its page")
    return "ok", "one printing: text in the tab; a version history: the viewer in the tab"


@check("frontend", "no component quietly takes a class another one already uses")
def _class_collisions():
    """The bug that has happened five times: .ctitle, .p-R, .cite, .fhead, .chead.

    Two renderers draw this site. app.js draws the record pages from bills.html,
    and the build_*.py scripts write the static ones. app.css dresses both. When
    a new component takes a name an old one already has, the later rule wins on
    source order and the older component changes shape somewhere nobody is
    looking -- .chead, on 19 September, gave every bill card's head button
    max-width:560px and took 24px off its left padding, on all 33,683 of them,
    while this suite passed 133 of 133.

    So the set of names both sides emit is frozen. Sharing is not the fault and
    is not forbidden: the nav, the footer, the player and the search panel are
    each drawn twice on purpose, and they are most of the list. Sharing by
    ACCIDENT is the fault, and a name arriving in this set without a person
    deciding it should be there is exactly that.

    To add one deliberately, put it in SHARED below with the component it
    belongs to. To find where a name is drawn, grep class=" in app.js, find.js,
    bills.html, build_*.py and shell.py.

    SHELL.PY IS A RENDERER TOO. It draws "Cite this page" on every page built
    through shell.page(), and until 24 September this check did not read it --
    so its <details class="cite"> went unseen beside app.js's docket
    <span class="cite">, took that span's white-space:nowrap, and above 720px
    every citation ran past its box and made the page scroll sideways. .cite
    was already the third name in this docstring's first line.
    """
    SHARED = {
        # The requests' explanation, one box: the bill search's requests term
        # (app.js) and each request's own page (build_request_pages, 8
        # November 2026), in the same words.
        "lsrnote",
        # The earlier bills of the same title: app.js's lsrPane draws them for
        # a request in the bill search, build_request_pages' history_pane for
        # its own page -- one component in the same words (the owner, 13
        # November 2026). What LSR stands for is the site's term popover on
        # the request's page (components.term_mark, glossary.json) since the
        # owner's word of 15 November 2026, no class of its own.
        "lsrhist",
        # THE SPONSORS TAB, a request's as a bill's: app.js draws it for a
        # bill (spBlock) and for a request's card (lsrPane), and
        # build_request_pages for a request's own page (sponsors_pane), the
        # same count line, group headings and row of person chips (the same
        # tab format as a bill). .chosen is also the row of
        # the bill search's picked filters (app.js alone), one flex row that
        # both want; the sponsors' row is the bill page's own use of it.
        "spcount", "sech", "sechn", "spgrp", "chosen",
        # THE BILL TEXT TAB, a request's as a bill's (17 November 2026): the
        # line saying what the text is and the block of a text, which app.js
        # draws for a bill (billTextSection, renderVersions) and for a
        # request's card (lsrTextPane), and build_request_pages for a
        # request's own page (text_pane).
        "btwhat", "vtext",
        # Your town's slot: a builder writes the empty box where an example
        # from the reader's own town belongs, and find.js fills it (the My
        # Town card, 14 October 2026).
        "yt",
        # the header and the footer, written once in bills.html for the record
        # pages and again in build_pages.shell() for the static ones
        "brand", "navdrop", "navmenu", "navtabs", "top", "in", "skip", "sr",
        "attrib", "fcol", "fcolhead", "fcols", "footdata", "lic", "flinks",
        "logocredit", "footby",
        "out", "note", "src", "count", "caret", "chev",
        # .src.fill, a source note that takes the width it has: the
        # committees index (build_committees) and a committee page (app.js)
        # both draw it, for the same component (F9, 7 October 2026)
        "fill",
        # the header search panel: find.js mounts it everywhere, and
        # build_pages draws the same row on /search -- the bills' row too,
        # for the current term's count under every term's (24 September)
        "findout", "fkind", "fl1", "fname", "fwhat", "fbills",
        # the calendar, drawn on the home page and on its own pages
        "cal", "calbills", "calbody", "calcmte", "calcount", "caldate",
        "calday", "calmeet", "calmix", "calslot", "caltime", "calwhere",
        "cdrel",
        # the recording player, on a bill's Videos tab and the home page
        "player", "pstub",
        # A COMMITTEE'S MEETING, as a fold: app.js's meetingHtml for a
        # committee's Meetings tab, and build_full_sessions' day_section for
        # each day a chamber sat, drawn as a committee's meeting is (the
        # person, 10 October 2026); and a statutory or study committee's
        # meeting, with its time and its marks (build_study_committees, 18
        # October 2026)
        "cmeets", "cmeet", "cmwhen", "cmcount", "cmcaret", "cmbody", "cmsaid", "cmplay",
        "cmtime", "cmkinds",
        # a page heading block, and the bill-number/title pair
        "phead", "pmeta", "cbn", "cbt",
        # THE VOTES TABLE's day and question cells: a member's Votes tab
        # (app.js voteRow) and a term's votes not on a bill
        # (build_nobill_votes, 23 October 2026) are the same table, stacked
        # into labelled blocks on a phone by the same rules
        "votes", "vfull", "b", "d", "o", "vch",
        # AND THE ELECTIONS TAB'S ROW in that table, its result cell and the
        # quiet asides in it ("(4 seats)", "Recounted", the share): app.js's
        # electionRow on a member's page, and build_legislator_pages'
        # election_row_html for the race on a new member-elect's provisional
        # page, held to app.js's row by _elect_page_member_form (16 November 2026)
        "v", "dim",
        # AND THE TAB'S UPCOMING ELECTIONS (19 November 2026): a card in the race card's
        # shape under a cycle's heading, which app.js's electionUpcoming draws on a
        # member's tab and build_legislator_pages.upcoming_html on a new member-elect's
        # page, held to app.js's by _member_elections_upcoming; .er-race and .er-hd are
        # build_elections.race_card's, the card the tab's races already are
        "er-cycle", "er-stack", "er-race", "er-hd", "er-up", "er-up-rows", "er-up-d", "er-up-w",
        "er-up-law",
        # the feedback box
        "fbk", "fbknote",
        # a person chip's "(R - Rock 2)", which pchip writes in components.js
        # and in components.py alike, held together by "every component gives
        # the same answer in Python and in the browser" (the look of 7 October
        # 2026)
        "mtag",
        # a drawing, which icon() writes in components.js and components.py
        # alike, and bills.html's header carries written out (Polish 1, 9
        # October 2026); _icons_named holds every one to the component
        "icon",
        # THE RECORD PAGES' COMPONENTS (Polish 2, ws/records, 10 October
        # 2026), each written in components.js and components.py alike and
        # held to one answer by _components_agree, so a session day built
        # ahead draws what app.js draws: a bill as a card (bill_card), its
        # byline's dot and the list the cards stand in
        "chead", "crow", "cnum", "cyear", "ctitle", "cmeta", "cline", "cbody", "cdot",
        "cards",
        # a bill named in words (bill_mention) and as a row (bill_row)
        "bmention", "byr", "brow", "brnum", "brtitle", "brline",
        # the dated rail (rail_html) and its drawn wave
        "rail", "dated", "wave",
        # a person in a sentence (person_link)
        "psent",
        # the record head (record_head) and its note
        "rtrail", "rtop", "rh1", "ryear", "ry", "rline", "rfacts", "rrail", "racts", "rnote",
        # the W4 sections (section) and the run of them; w4n, a count beside a
        # heading, on a study committee's page as on a record's (18 October 2026)
        "w4", "w4h", "w4b", "w4s", "w4n",
        # a document's row (doc_row)
        "docof",
        # a vote in the approved words: its amendment's number and the
        # record's own words where they differ
        "ramd", "rcrec",
        # a recording's moment and its player, on a committee's meeting and
        # a session day alike, and the fold's caret
        "jump", "mjumps", "pbar", "pwho", "tolnote", "cmcaret",
        # Share, among the record head's actions on every record page
        "pshare", "sharestate",
        # a committee's page -- its head, its term control and its meetings
        # -- which app.js draws for a committee and build_full_sessions for
        # the House's and the Senate's session days, drawn as a committee's
        # page at the person's asking (10 October 2026)
        "cmtehead", "cinfo", "bfilt", "pterm", "cday", "daylink", "cnarr",
        # THE MEMBERS-ELECT (the pages' pass, 16 October 2026): the block, its
        # head, its list and its notes, "Serving now" and a member's own
        # line, written by components.js and components.py alike (elect_now,
        # elect_race, elect_block, elect_line) and held to one answer by
        # _components_agree -- a town page draws in Python what the My Town
        # card and the map's panel draw in the browser; and "elown", the item
        # of a member re-elected to their own seat, the one a saved town's
        # "Your rep" may tag (find.js, ytMark; the owner, 7 November 2026)
        "elect", "elhead", "elwhere", "ellist", "elnf", "elnone", "elnow", "elline", "elown",
        # THE BILL SEARCH'S BOX AND FILTERS, drawn by bills.html and app.js
        # for /bills and by build_rsa for the Laws page's search, which the
        # person asked to work as the bill search does (24 October 2026): the
        # box and the count under it, the filter groups, their heads, badges
        # and counts, the Filter button, the Bill Type filter's letters
        # beside a name (a title's number on /laws), and Clear as a link
        "qline", "qbox", "qhint", "facets", "ftoggle", "fhead", "badge", "c", "tname", "tcode", "link",
        # bills.html's search row and the frame round the filters and the
        # list, which shell.page writes shut on a page that is not a list of
        # bills, so a phone never paints them there (the phone audit of 25
        # October 2026)
        "searchrow", "shell",
        # A RECORD PAGE'S TABS: the strip, a tab, its count's badge and its
        # pane, which app.js draws for a bill, a member and a committee
        # (tabStrip, pagePane, tabN) and build_study_committees for a study
        # or statutory committee, in the same words and classes at the
        # owner's asking ("the same tab format as standing committees", 29
        # October 2026; _study_committee_tabs)
        "tabs", "tab", "tn", "tnp", "pane",
        # THE RACE CARDS' GRID: build_elections lays an election's races out
        # in it, and app.js a member's Elections tab, whose cards are
        # build_elections.race_card's own (the owner, 18 November 2026); and the one
        # line under them saying what an incumbent's * is, which the elections page
        # writes and the member tab draws (19 November 2026)
        "er-cards", "er-incl",
    }
    here = Path(".")
    # The components draw on both sides by design: components.js with the
    # browser's files, components.py with the builders.
    app_side = ["components.js", "app.js", "find.js", "print.js", "bills.html"]
    bld_side = [f.name for f in _paths.code_files("build_*.py")] + ["shell.py", "components.py",
                                                                    "parts.py"]
    # And their own scripts, in inline/ beside them since 20 November 2026 (inline_js).
    import inline_js as IJ
    bld_side += [p.relative_to(_paths.ROOT).as_posix() for n, p in IJ.files().items()
                 if n.split(".")[0] + ".py" in bld_side]
    if not all(_paths.locate(f).exists() for f in app_side + ["shell.py"]) or not bld_side:
        return "skip", "not all renderers are in this directory"

    def drawn(paths):
        found = {}
        for f in paths:
            txt = _paths.locate(f).read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'class="([^"${}]+)"', txt):
                for c in m.group(1).split():
                    if re.fullmatch(r"[a-z][a-z0-9-]*", c):
                        found.setdefault(c, set()).add(f)
        return found

    a, b = drawn(app_side), drawn(bld_side)
    both = set(a) & set(b)
    new = sorted(both - SHARED)
    assert not new, (
        "these class names are drawn by BOTH renderers and are not in this "
        "check's SHARED list, so one component has probably taken a name "
        "another already uses:\n"
        + "\n".join(f"    .{c}: {', '.join(sorted(a[c]))} "
                     f"and {', '.join(sorted(b[c]))}" for c in new)
        + "\n  If the sharing is deliberate, add the name to SHARED with the "
          "component it belongs to. If it is not, give the new component its "
          "own prefix -- that is what .chead cost 33,683 bill cards.")
    gone = sorted(SHARED - both)
    return "ok", (f"{len(both)} names shared on purpose"
                  + (f"; {len(gone)} in SHARED no longer shared" if gone else ""))


@check("frontend", "the search panel's way out leads to a page the build writes")
def _find_all_results():
    """find.js's last row is on all 49,000 pages, and it points at one page.

    It used to point at the bill search, which indexes bills and nothing else,
    so "See all search results for Concord" opened a page with no towns in it.
    It points at /search now -- one page, written by build_pages.py, reached
    from everywhere. If either half of that moves without the other, the one
    row every page carries becomes a 404 on every page at once, and no test of
    any individual page would see it: the panel is mounted by script and the
    link check reads HTML.

    Both halves are read from source rather than from a build, so this runs
    under --code with nothing on disk.
    """
    js, bp = Path("src/pages/find.js"), _paths.locate("build_pages.py")
    if not js.exists() or not bp.exists():
        return "skip", "find.js or build_pages.py not in this directory"
    t = _source(js)
    # Since 9 November 2026 /search is also in Spanish: the row's address is
    # the page's own (window.GR_HREFS["search.html"]) and /search otherwise.
    assert "/search?q=" in t or ('"/search"' in t and '"search.html"' in t and "?q=" in t), (
        "find.js sends its last row somewhere other than /search -- if that "
        "is deliberate, this check names the page it should point at")
    import inline_js as IJ
    # The builder and its scripts, in inline/ since 20 November 2026.
    b = _source(bp) + "".join(_source(p) for n, p in IJ.files().items() if n.split(".")[0] == "build_pages")
    assert '"search.html"' in b, (
        "build_pages.py no longer writes search.html, and find.js still sends "
        "every page's search panel to /search")
    # The page reads this index with the cap off, so it needs the argument
    # that turns the cap off. A findMatch that ignores it would show eight
    # results on a page whose whole purpose is to show all of them, and would
    # look right.
    assert "findMatch(q,limit)" in t and "limit||8" in t, (
        "findMatch no longer takes a limit, so /search cannot ask for more "
        "than the panel's eight rows")
    # And the rows it draws are the panel's own. .resout only unpicks the
    # dropdown geometry; without .findout beside it the page has no row rules
    # at all, because they live in the shared region under .findout.
    assert 'class="findout resout"' in b, (
        "/search draws its rows without .findout, so it no longer shares the "
        "panel's one definition of a result row")
    return "ok", "find.js -> /search -> search.html, rows shared with the panel"


# The harness of _header_keyboard: find.js in node against dom_stub.js, with a
# class list that keeps what it is given (the menu's open state is a class)
# and the three elements the search mounts caught as it makes them.
_HEADER_KEYS = r"""
require("./stub.js");
const fs = require("fs"), vm = require("vm");
// A class list that keeps what it is given: the menu's open state is a class.
const classes = () => { const s = new Set(); return {add: c => s.add(c), remove: c => s.delete(c),
  contains: c => s.has(c), toggle: (c, on) => { (on === undefined ? !s.has(c) : on) ? s.add(c) : s.delete(c); return s.has(c); }}; };
const nav = document.querySelector("nav.top"); nav.classList = classes();
const menuBtn = document.getElementById("navmenu"), drop = document.getElementById("navdrop");
const link = {focused: 0, focus() { this.focused++; }};
drop.querySelector = sel => link;
drop.contains = x => x === link; menuBtn.contains = x => x === menuBtn;
// The search panel mounts itself where there is no search button yet, and
// makes its button, scrim and panel in that order.
const byId = document.getElementById.bind(document);
let asked = 0;
document.getElementById = id => id === "findbtn" && !asked++ ? null : byId(id);
const made = [], create = document.createElement.bind(document);
document.createElement = t => { const e = create(t); made.push(e); return e; };
let F;
try { vm.runInThisContext(fs.readFileSync("./find.js", "utf8"), {filename: "find.js"});
      F = vm.runInThisContext("({findSay, findDraw})"); }
catch (e) { console.log("LOAD " + e.message); process.exit(1); }
const out = {};
const [findBtn, scrim, panel] = made;
const fire = (el, type, ev) => (el._on[type] || []).forEach(f => f(Object.assign(
  {target: el, relatedTarget: null, preventDefault() {}, stopPropagation() {}}, ev || {})));

// The menu: opening it puts focus on its first link; focus that goes to
// anything but the panel or its button closes it.
fire(menuBtn, "click");
out.menu = {open: nav.classList.contains("open"), focused: link.focused};
fire(nav, "focusout", {relatedTarget: link});
out.menu.within = nav.classList.contains("open");
fire(nav, "focusout", {relatedTarget: null});
out.menu.nowhere = nav.classList.contains("open");
fire(nav, "focusout", {relatedTarget: {}});
out.menu.left = nav.classList.contains("open");

// The panel: the same, and its markup carries the status line and the names.
const inside = {};
panel.contains = x => x === inside; findBtn.contains = x => x === findBtn;
out.panel = {role: null, label: null, html: panel.innerHTML};
fire(findBtn, "click");
out.panel.open = panel.hidden === false;
fire(panel, "focusout", {relatedTarget: inside});
out.panel.within = panel.hidden === false;
fire(panel, "focusout", {relatedTarget: findBtn});
out.panel.onButton = panel.hidden === false;
fire(panel, "focusout", {relatedTarget: null});
out.panel.nowhere = panel.hidden === false;
fire(panel, "focusout", {relatedTarget: {}});
out.panel.left = panel.hidden === false;
out.panel.scrim = scrim.hidden;

// What the list holds, said.
const say = byId("findsay");
const said = html => { F.findSay(html); return say.textContent; };
const door = '<a class="fall" href="/search?q=x"><span>See all search results for x</span></a>';
out.say = {
  seven: said('<a href="/a">a</a>'.repeat(3) + '<a class="fbills" href="/bills?q=x">All 12 bills</a>'
              + '<a href="/bill/2026/hb1">b</a>'.repeat(3) + door),
  one: said('<a href="/a">a</a>' + door),
  none: said(door + '<p class="fnote">No matching results.</p>'),
  counting: said(door),
  number: said('<a class="fall" href="/bills?q=HB%202"><span>HB 2</span></a>' + door),
  empty: said(""),
};
F.findDraw("");
out.say.cleared = say.textContent;
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("frontend", "the header's menu and search by keyboard: focus goes in, leaving closes, and the list says what it holds")
def _header_keyboard():
    """The audit of 2 October 2026, S2, S3 and S4, all in find.js.

    S2. At phone width (and for a desktop reader at 400%) Enter on "Sections"
    opened the menu and left focus on the button; the panel comes before the
    button in the document, so the next Tab press went on into the page with
    the menu still open, and the sections were three Shift+Tab presses back.
    S3. With the search panel open, Tab past the last answer went on into the
    page with the panel still open -- on a phone, under the scrim, where the
    focused link could not be seen. S4. The answers appear as the reader
    types, and nothing said so to a screen reader.

    Held, by running find.js: opening the menu focuses its first link; focus
    that goes to something outside the menu and its button closes it, and
    focus that goes nowhere (the window losing it) or stays within does not;
    the same for the search panel, with its own button counted as within; the
    panel is a named search landmark whose box names the list it fills; and
    the one role="status" line says how many results the list holds, counts
    the door to every result as no result, says "No matching results." when
    the list does, and is silent while the bills are still being counted and
    when the box is empty.
    """
    js, stub = Path("src/pages/find.js"), Path("tests/dom_stub.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and stub.exists() and node):
        return "skip", "find.js, dom_stub.js or node is not here"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "find.js").write_text(_source(js), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        (root / "go.js").write_text(_HEADER_KEYS, encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "find.js did not run under node: " + (r.stderr or r.stdout or "")[-300:])
        got = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    m = got["menu"]
    assert m["open"] and m["focused"] == 1, (
        f"opening the sections menu leaves focus on its button ({m}): the next "
        "Tab press goes on into the page, past the menu")
    assert m["within"] and m["nowhere"] and not m["left"], (
        f"the sections menu and focus leaving it: {m}. It closes when focus goes "
        "somewhere else in the page, and only then")
    p = got["panel"]
    assert p["open"] and p["within"] and p["onButton"] and p["nowhere"], (
        f"the search panel closed on focus that had not left it: {p}")
    assert not p["left"] and p["scrim"], (
        "the search panel stays open, or its scrim up, when focus has gone on "
        "into the page: on a phone the focused link is then under the scrim")
    assert 'role="status"' in p["html"] and 'id="findsay"' in p["html"] \
        and 'aria-controls="findout"' in p["html"], (
        "the search panel's markup lost its status line, or its box no longer "
        "names the list it fills")
    src = _source(js)
    assert 'panel.setAttribute("role","search")' in src and \
        'panel.setAttribute("aria-label",' in src, (
        "the search panel is not a named search landmark")
    want = {"seven": "7 results", "one": "1 result", "none": "No matching results.",
            "counting": "", "number": "1 result", "empty": "", "cleared": ""}
    assert got["say"] == want, (
        "the search panel's status line says "
        + "; ".join(f"{k}: {got['say'].get(k)!r}, not {v!r}"
                    for k, v in want.items() if got["say"].get(k) != v))
    draw = src[src.index("function findDraw("):src.index("function findSay(")]
    assert draw.count("findSay(") == 2, (
        "findDraw does not say what it drew on both of its ways out (the empty "
        "box, and a list)")
    return "ok", ("opening the menu focuses its first link, focus gone elsewhere closes the "
                  "menu and the search panel, and the panel's status line counts what the "
                  "list holds")


# A PASTED PARAGRAPH, AND ONE DRAWING OF THE LIST (2 October 2026). Nothing
# among the checks measured how much work a search is, which is how a page
# that stopped for 17 seconds on 200 pasted words passed 419 of them. This
# loads app.js as bills.html does, over the bills the search cases name, and
# counts: how many searches one drawing runs, and how many times it asks a
# bill what a part of the search found in it.
_SEARCH_WORK_JS = r"""
require("./stub.js");
const fs = require("fs");
const C = JSON.parse(fs.readFileSync("./cases.json", "utf8"));
const rows = Object.entries(C.bills).map(([id, b]) => ({ id, term: C.term, year: 2025, ...b }));
const words = new Set();
for (const b of rows) for (const w of (b.title + " " + b.sponsor).toLowerCase().match(/[a-z]{5,}/g) || []) words.add(w);
const FIX = { "/meta.json": { terms: [C.term], topics: [], committees: [], sponsors: [], votedays: [], years: [2025, 2026] },
  ["/idx/" + C.term + ".json"]: rows, ["/sidx/" + C.term + ".json"]: JSON.parse(fs.readFileSync("./sidx.json", "utf8")),
  "/sidx/words.json": { v: 1, n: words.size, words: [...words].sort().join(" ") } };
globalThis.fetch = async (u) => { const p = decodeURIComponent(new URL(u).pathname);
  if (!(p in FIX)) return { ok: false, status: 404, json: async () => { throw new Error("404"); } };
  return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(FIX[p])) }; };
const ticks = async (n) => { for (let i = 0; i < n; i++) await new Promise(r => setImmediate(r)); };
let moved = null;
history.replaceState = (s, t, u) => { moved = u; };
const box = document.querySelector("#q"); box.disabled = true;
let scope;
try { scope = (0, eval)(fs.readFileSync("./app.js", "utf8")
  + ";({getIDX: () => IDX, addressSearch: typeof addressSearch === 'undefined' ? null : addressSearch,"
  + " most: typeof MAXWORDS === 'undefined' ? null : MAXWORDS})"); }
catch (e) { console.log("LOAD " + e.message); process.exit(1); }
// Counted where the page itself calls them: a function app.js declares is
// the global one, so a wrapper put in its place is what the page then calls.
const calls = { queryGroups: 0, fitAlone: 0 };
for (const name of Object.keys(calls)) { const real = globalThis[name];
  globalThis[name] = function () { calls[name]++; return real.apply(this, arguments); }; }
(async () => {
  for (let i = 0; i < 400 && box.disabled !== false; i++) await ticks(1);
  if (box.disabled !== false) { console.log("app.js never finished loading the fixture"); process.exit(1); }
  const out = { bills: scope.getIDX().length, most: scope.most, draws: {} };
  const type = async (s) => { box.value = s; box.fire("input"); await ticks(30); };
  await type("firearms");           // the term's text arrives on the first search
  const draw = async (name, s) => {
    await type("");
    const groups = globalThis.queryGroups(s);
    calls.queryGroups = calls.fitAlone = 0;
    const t = process.hrtime.bigint();
    box.value = s; box.fire("input");
    const ms = Number(process.hrtime.bigint() - t) / 1e6;
    out.draws[name] = { ms: Math.round(ms), groups: groups.length, cut: groups.cut || 0,
      searches: calls.queryGroups, fits: calls.fitAlone,
      count: document.querySelector("#count").textContent,
      hint: document.querySelector("#synhint").textContent,
      says: document.querySelector("#results").innerHTML.replace(/<article[\s\S]*$/, "")
        .replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").slice(0, 600) };
  };
  const para = "relative to the regulation of certain municipal water systems and establishing a commission to study the effects of groundwater withdrawal on private wells in towns bordering public forest lands and requiring annual reports to the general court by department heads on the cost of compliance with federal standards for treatment plants";
  const ws = para.split(" ");
  const two = Array.from({ length: 200 }, (_, i) => ws[i % ws.length] + (i >= ws.length ? String.fromCharCode(97 + (i % 26)) : "")).join(" ");
  await draw("one word", "abortion");
  await draw("three words", "college students voting");
  await draw("200 words", two);
  await draw("tax, 5000 times", "tax ".repeat(5000));
  await draw("20,000 letters", "a".repeat(20000));
  await draw("a title", "permitting classification of individuals based on biological sex under certain limited circumstances.");
  // An offered search, taken, is the one the address names.
  out.address = {};
  if (scope.addressSearch) {
    location.search = "?q=vacine%20exemption&term=all"; moved = null;
    scope.addressSearch("vaccine exemption");
    out.address.named = moved;
    location.search = ""; moved = null; scope.addressSearch("vaccine exemption");
    out.address.unnamed = moved;
  }
  console.log(JSON.stringify(out));
})().catch(e => { console.log("RUN " + e.message); process.exit(1); });
"""

# What one drawing may cost, on the cases' few hundred bills. The page before
# 2 October took 5.6 seconds over them for 200 pasted words and ran 361
# searches doing it; it takes 25 ms and runs 13.
SEARCH_DRAW_MS = 1500
SEARCH_DRAW_SEARCHES = 40


@check("frontend", "a pasted paragraph is read to its twelfth word, and one "
                   "drawing of the list asks each bill once")
def _search_work():
    """The second review's performance lens, 2 October: 200 words pasted into
    the search box stopped /bills for 17 seconds in the current term and 220
    on All terms, and every letter typed on All terms held the page for half
    a second on a desktop and five on a phone. Every check passed, because
    none measured how much work a search is.

    Three causes, each held here by counting what the page does, so that the
    check does not turn on how fast this machine is:

    - a search was read to its last word, and every word is a part every
      bill is asked for: it is read to its twelfth now (queryGroups,
      MAXWORDS), the page says so, and a pasted title still finds its bill;
    - a search that listed nothing ran one more whole search for every word
      typed, and another for every word left out: 361 for 200 words. One
      drawing may run SEARCH_DRAW_SEARCHES;
    - one drawing asked every bill the same question six times -- the list,
      four filters' counts and the order. It asks once: fitAlone() is called
      at most twice a bill for a one-word search.

    The time is held too, loosely: SEARCH_DRAW_MS for any of them, where the
    old page took 5.6 seconds for the paste and the new one 25 ms.

    And an offered search, taken, is the one the address names: a reader who
    arrived at /bills?q=vacine%20exemption and took "vaccine exemption" was
    left at an address that still said "No bills match" on reload.
    """
    if not shutil.which("node"):
        return "skip", "node is not installed"
    need = ("src/pages/app.js", "tests/dom_stub.js", "tests/search_cases.json",
            "tests/search_index.json")
    if not all(Path(f).exists() for f in need):
        return "skip", "app.js, dom_stub.js or the search cases are not here"
    root = Path(tempfile.mkdtemp())
    try:
        for name, src in (("stub.js", "tests/dom_stub.js"), ("app.js", "src/pages/app.js"),
                          ("cases.json", "tests/search_cases.json"),
                          ("sidx.json", "tests/search_index.json")):
            text = Path(src).read_text(encoding="utf-8")
            (root / name).write_text(_with_components(text) if name == "app.js" else text,
                                     encoding="utf-8")
        (root / "go.js").write_text(_SEARCH_WORK_JS, encoding="utf-8")
        r = _run(["node", "go.js"], cwd=root, capture_output=True, text=True,
                 timeout=180)
        said = (r.stdout + r.stderr).strip()
        last = (said.splitlines() or ["no output"])[-1]
        assert r.returncode == 0 and last.startswith("{"), (
            "node go.js: " + " / ".join(said.splitlines()[-3:])[:300])
        got = json.loads(last)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    n, d = got["bills"], got["draws"]
    assert n >= 300, f"only {n} bills were loaded: the counts below prove little"
    assert got["most"] and got["most"] <= 15, (
        f"app.js reads a search to its word {got['most']!r}: there is no "
        "limit on how many parts a pasted paragraph becomes")
    paste = d["200 words"]
    assert paste["groups"] <= got["most"] and paste["cut"] >= 100, (
        f"200 pasted words are read as {paste['groups']} parts with "
        f"{paste['cut']} left unread: every one is a part every bill is asked for")
    assert "first twelve words" in paste["says"].lower(), (
        "a search cut short does not say so where nothing is listed: "
        f"{paste['says'][:160]!r}")
    assert "first twelve words" in d["tax, 5000 times"]["hint"].lower(), (
        "a search cut short does not say so under the box where bills are "
        f"listed: {d['tax, 5000 times']['hint'][:160]!r}")
    for name, x in d.items():
        assert x["searches"] <= SEARCH_DRAW_SEARCHES, (
            f"drawing {name!r} ran {x['searches']} searches over every bill "
            f"(at most {SEARCH_DRAW_SEARCHES}): the offers for a search that "
            "lists nothing are counted without limit again")
        assert x["ms"] <= SEARCH_DRAW_MS, (
            f"drawing {name!r} took {x['ms']:,} ms over {n} bills, more than "
            f"{SEARCH_DRAW_MS:,}: on the 2,243 of a term that is a page that "
            "has stopped answering")
    one = d["one word"]
    assert n <= one["fits"] <= 2 * n, (
        f"one drawing of a one-word search asked a bill what it found "
        f"{one['fits']:,} times for {n} bills: each bill is to be asked once, "
        "and its answer kept (app.js, recall)")
    three = d["three words"]
    # Each word on its own as a sentence, "'voting' alone matches 4 bills"
    # (the audit of 25 October 2026, S7), not "On their own: voting (4)".
    assert "Without one word" in three["says"] and re.search(
            r"alone matches [\d,]+ bills?\b", three["says"]) \
        and "On their own" not in three["says"], (
        "a search of three words that lists nothing no longer offers its "
        f"parts, each as a sentence: {three['says'][:200]!r}")
    assert d["a title"]["count"].split(" ")[0] not in ("", "0"), (
        "a bill's whole title, pasted, does not find the bill: "
        f"{d['a title']['count']!r}")
    a = got["address"]
    assert a.get("named") and "q=vaccine+exemption" in a["named"] \
        and "term=all" in a["named"] and a.get("unnamed") is None, (
        "an offered search, taken, does not rewrite an address that named "
        f"the misspelt one, or rewrites one that named none: {a}")
    return "ok", (f"over {n} bills: 200 pasted words are read as "
                  f"{paste['groups']} and drawn in {paste['ms']} ms with "
                  f"{paste['searches']} searches run; a one-word search asks "
                  f"each bill once ({one['fits']} for {n}); a pasted title "
                  "finds its bill; an offered search rewrites the address "
                  "that named the misspelling")


@check("frontend", "every record's own page is a working shell for app.js")
def _bill_shell():
    """What replaced "the bill page stylesheet still formats".

    That check guarded 200 lines of CSS inside build_bill_pages.py, which
    rendered every bill a second time in Python. Both are gone: a bill's page
    is bills.html with one bill open, so the stylesheet it uses is app.css and
    the palette check already covers that.

    What needs guarding now is different and worse if it breaks. app.js binds
    to #q, #qgo, #year, #sort, #facets, #results and #count as it loads, and
    tells the page which bill it is through GR_BILL. Drop any one of those and
    the page is a blank screen that reports nothing -- 4,230 times over, with
    every check passing. build_bill_pages.py asserts them as it builds; this
    asserts them on what was actually written.
    """
    # A bill's, a legislator's and a committee's page are the same shell with
    # a different global set, all three from shell.py. Each is checked, because
    # a generator that stops setting its global produces thousands of pages
    # that load, draw nothing and report nothing.
    kinds = [("site/bill", "*/*.html", "GR_BILL", "/bill/"),
             ("site/legislator", "*.html", "GR_MEMBER", "/legislator/"),
             ("site/committee", "*.html", "GR_COMMITTEE", "/committee/")]
    found, sizes = [], []
    for folder, pat, glob_name, urlbit in kinds:
        # A STUDY OR STATUTORY COMMITTEE'S PAGE (ss<id>.html, since 17 October
        # 2026) is not this shell: build_study_committees writes its record in
        # place under GR_STATIC. There are 153 of them, so the middle of the
        # folder was one, and dry run 94 (18 October) failed here. They are
        # checked below for what makes them findable.
        pages = sorted(q for q in Path(folder).glob(pat) if not q.name.startswith("ss"))
        if not pages:
            continue
        f = pages[len(pages) // 2]
        t = f.read_text(encoding="utf-8")
        for need in ('id="q"', 'id="qgo"', 'id="year"', 'id="sort"',
                     'id="facets"', 'id="results"', 'id="count"'):
            assert need in t, (
                f"{f} has no {need}, which app.js binds to on load. The page "
                "draws nothing and says nothing about why.")
        # The src carries a content hash now, so match the prefix.
        assert 'src="app.js' in t, f"{f} does not load app.js"
        assert -1 < t.find('<script src="/components.js"></script>') < t.find('src="app.js'), (
            f"{f} does not load components.js before app.js, which draws with it")
        assert f"window.{glob_name}=" in t, (
            f"{f} never says which record it is, so app.js opens none of them")
        assert '<base href="/">' in t, (
            f"{f} has no <base>, so every relative link app.js writes resolves "
            f"under {folder}/ and 404s")
        # The record as plain HTML, for a reader that runs no scripts, ahead
        # of the slot app.js draws into. It replaced the <noscript> line on
        # 12 October 2026 (f4dad63, shell.page's static=), and this asked for
        # the <noscript> until 15 October: a data check, so no night ran it,
        # and the laptop's build was older than the change.
        rec, slot = t.find('id="static-rec"'), t.find('<div id="results">')
        assert -1 < rec < slot, (
            f"{f} carries no record as plain HTML before the results slot: a reader "
            "without JavaScript gets a blank page and no way to the General Court")
        # The three things that make a record findable, and the whole reason
        # these pages exist rather than a fragment on the search page.
        assert "<title>" in t and "| Granite Record</title>" in t, f"{f}: no title"
        assert 'name="description"' in t, f"{f}: no meta description"
        assert 'rel="canonical"' in t, f"{f}: no canonical link"
        sm = Path("site/sitemap.xml")
        assert sm.exists() and urlbit in sm.read_text(encoding="utf-8"), (
            f"sitemap.xml does not list {urlbit} pages")
        found.append(f"{len(pages):,} {urlbit.strip('/')}")
        sizes.append(f.stat().st_size)
    if not found:
        return "skip", "no record pages built yet"
    assert len(found) == 3, (
        "only " + ", ".join(found) + " were built. All three page types come "
        "from shell.py and build_all runs all three, so a missing one is a "
        "step that did not run rather than a page type that does not exist.")
    study = sorted(Path("site/committee").glob("ss*.html"))
    if study:
        f = study[len(study) // 2]
        t = f.read_text(encoding="utf-8")
        assert "window.GR_STATIC=" in t, (
            f"{f} does not say it is a page written in place, so app.js would draw over it")
        rec = t.find('<div id="results">')
        assert -1 < rec and "</div>" not in t[rec:rec + len('<div id="results">') + 6], (
            f"{f} has an empty results slot: the committee's record was not written into it")
        assert "<title>" in t and "| Granite Record</title>" in t, f"{f}: no title"
        assert 'name="description"' in t, f"{f}: no meta description"
        assert 'rel="canonical"' in t, f"{f}: no canonical link"
        found.append(f"{len(study):,} study and statutory committee")
    return "ok", (", ".join(found) + f"; {min(sizes)/1024:.1f}-"
                  f"{max(sizes)/1024:.1f} KB each")


@check("frontend", "no source file carries a control character")
def _no_control_bytes():
    """app.js was a binary file for two days and nothing said so.

    cmteUpcoming joins a term and a bill number with U+0000, because that is
    the one character no committee name, bill number, time or venue can
    contain -- a good separator. It was written into app.js as the *byte*
    rather than as the two characters JavaScript reads as that byte, five
    times, and a single NUL is all it takes for git, grep, diff and most other
    text tools to treat a file as binary: git stopped normalising the file's
    line endings, so an edit on Windows rewrote all 3,058 lines and hid eleven
    real changes inside them, and any step that reads text and stops at a NUL
    would have truncated the site's whole script at line 2396 with no error.

    The same afternoon, the same cause wrote 0x01 and 0x02 into a regular
    expression's backreferences in parse_clerks.py -- `re.sub(r"...\\1", r"\\1\\2")`
    became `re.sub(r"...\x01", r"\x01\x02")` -- which does not error, does not
    look wrong, and quietly replaced a substitution with a deletion. CLAUDE.md
    warns that a heredoc in either shell eats backslash escapes and says to
    write patch scripts with the editor instead; this is what it costs when
    that is forgotten.

    So: no control character except tab, newline and carriage return, in any
    source file in the tree. Naming ten files by hand was the first version of
    this check and it did not cover the second incident.

    C1 AS WELL AS C0, in the one pass (2 October 2026; until then a second
    check, "no source file carries a mangled control character", read the
    root's files again for these). app.css carried U+0083 inside the citation
    control's content string, with a capital A after it, and every page on
    the site drew a small empty box and a stray letter A in front of "Cite
    this page". U+0083 is NO BREAK HERE, a C1 control that no editor puts
    there on purpose; it is what is left of a glyph that went through a
    cp1252 round trip, and the A beside it is debris from the same accident.
    It survived because nothing errored: the stylesheet parsed, the page
    rendered, and the damage was one character wide.

    So the range is U+0000 to U+001F and U+007F to U+009F, less the three
    whitespace characters source legitimately contains. Nothing else in that
    span belongs in a text file here, and the failure names each character
    it found, so which of the two accidents it was is in the message.
    """
    exts = {".py", ".css", ".js", ".html", ".json", ".md", ".bat"}
    # town_sites/ added 20 September: 234 town pages fetched by another
    # session, one of which is a binary response saved with an .html name, and
    # this check went red on somebody else's download rather than on a source
    # file. Worth noticing that this list is the same shape as the one the
    # pane measure rule had to abandon -- "each attempt capped a list and the
    # list was never the whole list". A fetched page cache is gitignored by
    # definition, so asking git what it ignores would end this class of
    # failure rather than adding to it; that is a change to make deliberately
    # and not while two sessions are in the same tree.
    skip = ("site/", "work/", "archive/", "logs/", "data/", "db/",
            "docket_pages/", "bill_text/", "legislation/", "captions/",
            "review/", ".git/", "records/sources/", "brand/", "assets/",
            "town_sites/")
    #
    # GIT'S LIST, WHICH IS THAT CHANGE (2 October 2026). The walk was every
    # file under the folder -- 91,000 entries in a worktree, and in the main
    # folder the caption folders as well -- and it read what the tuple above
    # did not name: 660 MB of generated JSON at a worktree's root; in the main
    # folder 858 MB in 6,364 files, the fetched page caches among them; and
    # then every source file of every worktree under .claude/worktrees/, with
    # a pattern added on 1 October to skip their caches. And the tuple's ".git/"
    # never matched: the path was compared after lstrip("./"), which takes
    # the dot off ".git" as well as off "./". What is read now is what git
    # tracks and what it would track if added, less the folders above, matched
    # as git spells them. .gitignore keeps the fetched caches and the
    # worktrees out, so no list here has to.
    #
    # AND WHAT GIT IGNORES THAT IS STILL THIS PROJECT'S OWN WRITING. Git's list
    # alone left out files the two checks had read, and three kinds of them
    # are exactly what this is for. A patch script: .gitignore's `_*.py` is
    # the name this project gives one, so the file likeliest to carry an
    # eaten escape was the one not read. The generated JSON at the root that
    # the build publishes from: json.dump writes a C0 character as an escape,
    # but with ensure_ascii=False it writes C1 and DEL as they are --
    # senate_hearing_reports.json and past_members.json are written so, and
    # the first is 10 MB of hearing reports the site prints. And the files a
    # person keeps on this machine only: launch_register.json, CLAUDE.local.md
    # and the plans under private/. So every file at the root is read whether
    # git ignores it or not, which is all the second check ever read, and so
    # is BY_HAND. The rest of reports/ is left out: a night's triage file
    # quotes readers' own words, and a character a reader typed is not damage
    # to the source. Nor are the caches read that git ignores below the root.
    #
    # WITHOUT GIT -- an export of the tree, a copy -- the folder is walked,
    # without going into a folder the tuple names or into a worktree.
    BY_HAND = ("private", "reports/cloud", "reports/TRIAGE.md")
    try:
        out = _run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                   capture_output=True, text=True, timeout=120)
        listed = out.stdout.split("\0") if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        listed = None
    how = "that git tracks or would, at the root, or kept by hand"
    if listed is None:
        how, listed = "in the folder (no git here)", []
        for d, dirs, files in os.walk("."):
            rel = Path(d).as_posix()
            rel = "" if rel == "." else rel + "/"
            dirs[:] = sorted(x for x in dirs if not (rel + x + "/").startswith(skip)
                             and rel + x != ".claude/worktrees")
            listed += [rel + x for x in files]
    else:
        listed += [f.name for f in Path(".").iterdir() if f.is_file()]
        for d in map(Path, BY_HAND):
            listed += [f.as_posix() for f in ([d] if d.is_file() else d.rglob("*"))]
    # One pattern for both ranges, over the bytes: C0 less tab, newline and
    # carriage return, with DEL; and C1, which UTF-8 writes as 0xC2 and then
    # the character's own number. The pattern is run only over a file that
    # has one of those bytes in it -- taking every other byte out of a file
    # and looking at what is left is a seventh of the pattern's time, and the
    # root's generated files are 670 MB.
    ctl = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]|\xc2[\x80-\x9f]")
    not_c0 = bytes(b for b in range(256) if not ctl.match(bytes([b])))
    bad, n, c0, c1 = [], 0, False, False
    for rel in sorted(set(listed)):
        f = Path(rel)
        if f.suffix.lower() not in exts or rel.startswith(skip) or not f.is_file():
            continue
        n += 1
        raw = f.read_bytes()
        first = (ctl.search(raw) if b"\xc2" in raw or raw.translate(None, not_c0)
                 else None)
        if first:
            hits = sorted({m[-1] for m in ctl.findall(raw)})
            c0, c1 = c0 or hits[0] < 0x80, c1 or hits[-1] >= 0x80
            bad.append(f"{rel}: {', '.join(f'U+{h:04X}' for h in hits)}"
                       f" (first near line {raw.count(b'\n', 0, first.start()) + 1})")
    assert n, ("no source file was read: the list of files came back with none "
               "of this folder's in it")
    assert not bad, (
        "control characters in " + "; ".join(bad[:4])
        + (". Write the escape rather than the byte -- a heredoc turns \\1 into "
           "U+0001 and \\0 into NUL, and neither is visible in a diff" if c0 else "")
        + (". U+0080 to U+009F is what a cp1252 round trip leaves of a glyph, "
           "and it is drawn as a box, a stray letter, or nothing at all" if c1 else "")
        + ".")
    return "ok", f"{n} source files {how}, none with a control character, C0 or C1"


@check("frontend", "a heading outline never skips a level")
def _heading_levels():
    """h1 to h3, on the page that explains how a bill becomes law.

    LAUNCH.md 7.3 recorded two of these and left them: learn.html went from
    its h1 to an h4, and the eleven topic pages went from h1 to h3 because
    the flow diagram's phase names were written at level 3 wherever the
    diagram happened to sit. A reader navigating by heading -- which is how
    somebody using a screen reader reads a long page -- met four labels at
    the wrong depth on the page most likely to be read by a class.

    Static HTML only, and deliberately: the record pages build their headings
    in app.js, so their file carries the hidden h1 and nothing else. This
    catches the pages written by build_pages.py, build_civics.py and
    build_town_pages.py, which is where every one of these came from.
    """
    site = Path("site")
    if not (site / "index.html").exists():
        return "skip", "site/index.html not built"
    files = sorted(site.glob("*.html")) + sorted(site.glob("learn/*.html"))
    towns = sorted(site.glob("town/*.html"))
    files += towns[:3] + towns[len(towns) // 2:len(towns) // 2 + 2]
    bad, n = [], 0
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        levels = [int(m.group(1)) for m in re.finditer(r"<h([1-6])[ >]", text)]
        if not levels:
            continue
        n += 1
        prev = 0
        for lv in levels:
            if prev and lv > prev + 1:
                bad.append(f"{f.relative_to(site).as_posix()}: h{prev} -> h{lv}")
                break
            prev = lv
    assert not bad, (
        f"{len(bad)} pages skip a heading level: " + "; ".join(bad[:4])
        + ". A level is not a size -- style the label and keep the depth.")
    return "ok", f"{n} pages, no skipped level"


@check("frontend", "a meeting is matched to one committee, in one term")
def _cmte_match():
    """tests/test_cmte_match.js, against app.js's own source.

    The committee page's Upcoming session block has to decide whether a
    scheduled meeting is this committee's, out of a row that names the
    committee and not the chamber -- and seven committee names belong to both
    chambers. The rule is name plus a bill from that committee's own list for
    that TERM, and the term half is what the first version got wrong: it
    collapsed every term into one set, so House Finance's CACR 1 of 2001
    would have vouched for a 2026 meeting about a different CACR 1.

    The test reads the function out of app.js by source text rather than
    keeping a copy, so it cannot pass against a version the browser does not
    run.
    """
    import subprocess, sys
    f = Path("tests/test_cmte_match.js")
    if not f.exists():
        return "skip", "tests/test_cmte_match.js not here"
    if not Path("site/committee/H34.json").exists():
        return "skip", "the committee records are not built yet"
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return "skip", "node is not on PATH"
    r = _run([node, str(f)], capture_output=True, text=True)
    assert r.returncode == 0, (r.stdout or r.stderr).strip()[-400:]
    n = sum(1 for ln in r.stdout.splitlines() if "[ ok ]" in ln)
    return "ok", f"{n} cases, including both chambers' Finance"


@check("frontend", "a committee page's Upcoming session shows its own chamber's sittings, on a bill both chambers list")
def _cmte_match_chamber():
    """House Judiciary's executive session on SB 519, 30 September 2026 at
    10:00 in GP 230, was on Senate Judiciary's page.

    cmteUpcoming matched a scheduled row on the committee's name and on a bill
    from the committee's own list for the term, and a bill that crosses is on
    both chambers' lists: SB 519 is Senate Judiciary's and House Judiciary's.
    home.json's row named no chamber, so nothing else could tell them apart.
    Replayed over every day of 2025-2026, 719 sittings were shown on the
    other chamber's page, on 384 days; on the day this was found, three --
    that one and House Ways and Means' two on SB 542, on Senate Ways and
    Means's page.

    tests/test_cmte_match.js runs the rule on the built committee records and
    skips without them; this runs it on two records written here, so it holds
    under --code. The function is read out of app.js by source text, as that
    test reads it.
    """
    node = shutil.which("node") or shutil.which("node.exe")
    js = Path("src/pages/app.js")
    if not (node and js.exists()):
        return "skip", "app.js or node is not here"
    m = re.search(r"function cmteUpcoming\(c\)\{[\s\S]*?\n\}", _source(js))
    assert m, "cmteUpcoming is not in app.js"
    tmp = Path(tempfile.mkdtemp(prefix="gr-cmteup-"))
    try:
        (tmp / "fn.js").write_text(m.group(0), encoding="utf-8")
        (tmp / "go.js").write_text(r"""
const fs = require("fs");
let UPCOMING = null;
eval(fs.readFileSync("./fn.js", "utf8"));
const H10 = {code: "H10", name: "Judiciary", chamber: "H",
             bills: {"2025-2026": [{id: "SB519"}, {id: "HB88"}]}};
const S10 = {code: "S10", name: "Judiciary", chamber: "S",
             bills: {"2025-2026": [{id: "SB519"}]}};
const row = {date: "2026-09-30", time: "10:00", bill: "SB519", term: "2025-2026",
             committee: "Judiciary", what: "executive session", venue: "GP 230"};
const out = {};
UPCOMING = [Object.assign({body: "H"}, row)];
out.house = cmteUpcoming(H10).map(u => u.bill);
out.senate = cmteUpcoming(S10).map(u => u.bill);
UPCOMING = [Object.assign({body: "S"}, row)];
out.house_of_senate = cmteUpcoming(H10).map(u => u.bill);
out.senate_of_senate = cmteUpcoming(S10).map(u => u.bill);
process.stdout.write(JSON.stringify(out));
""", encoding="utf-8")
        r = _run([node, "go.js"], cwd=tmp, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, (r.stdout or r.stderr).strip()[-300:]
        got = json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    want = {"house": ["SB519"], "senate": [], "house_of_senate": [], "senate_of_senate": ["SB519"]}
    assert got == want, (
        f"House Judiciary's sitting on SB 519 of 30 September 2026 lands as {got}; wanted {want}: "
        "a bill both chambers' committees list does not say whose sitting it is, and the row's "
        "chamber does")
    return "ok", ("House Judiciary's sitting on SB 519 is on House Judiciary's page and not on "
                  "Senate Judiciary's, which lists SB 519 too")


def _tdz_suspects(js):
    """A const or let read earlier in its function than the line declaring it.

    Legal-looking, syntactically perfect, and fatal: const sits in the temporal
    dead zone until its own line runs, so a read above it throws and takes the
    whole function with it. That is how render() died and the bill list went
    blank on a page that otherwise loaded fine -- node --check passes, the tags
    balance, the site builds, and nothing here executed the script.

    Lines defining a function are skipped: a closure may mention a name
    declared after it, because it runs later.
    """
    js = _strip_js_comments(js)
    out = []
    for fm in re.finditer(r"\bfunction\s+(\w+)\s*\([^)]*\)\s*\{", js):
        name, i = fm.group(1), fm.end()
        depth, j = 1, i
        while j < len(js) and depth:
            depth += (js[j] == "{") - (js[j] == "}")
            j += 1
        lines, d = [], 0
        for ln in js[i:j - 1].splitlines():
            lines.append((d, ln))
            d += ln.count("{") + ln.count("(") - ln.count("}") - ln.count(")")
        decl = {}
        for k, (d, ln) in enumerate(lines):
            m = re.match(r"\s*(?:const|let)\s+(\w+)\s*=", ln) if d == 0 else None
            if m and m.group(1) not in decl:
                decl[m.group(1)] = k
        for var, dk in decl.items():
            for k, (d, ln) in enumerate(lines[:dk]):
                if d == 0 and "=>" not in ln and "function" not in ln \
                        and re.search(rf"\b{re.escape(var)}\b", ln):
                    out.append(f"{name}(): '{var}' read at line {k + 1}, "
                               f"declared at {dk + 1}")
                    break
    return out


@check("frontend", "the page's script loads and render() draws")
def _runs():
    """Actually execute it.

    Everything else about bills.html is read rather than run: the tags balance,
    the syntax parses, the palette is right, the site builds around it. All of
    that was green on a page whose render() threw on its first line and left
    the bill list blank.

    So this loads the script in node against a DOM stub, hands it two bills and
    calls render(). It does not prove the page looks right -- nothing here can
    -- but it proves the code path that draws every bill actually runs.
    """
    f, stub = Path("src/pages/bills.html"), Path("tests/dom_stub.js")
    if not f.exists():
        f = Path("site/bills.html")
    if not f.exists():
        return "skip", "bills.html not here or in site/"
    if not shutil.which("node"):
        return "skip", "node is not installed"
    if not stub.exists():
        return "skip", "dom_stub.js not here"
    # The script is app.js now. The inline form is still read, so this keeps
    # working against an older checkout of the page.
    ext = f.parent / "app.js"
    js = (ext.read_text(encoding="utf-8") if ext.exists()
          else "\n".join(re.findall(r"<script>(.*?)</script>",
                                    f.read_text(encoding="utf-8"), re.S)))
    assert js.strip(), f"no script in {ext if ext.exists() else f}"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(js), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub),
                                      encoding="utf-8")
        (root / "go.js").write_text("""
require("./stub.js");
const src = require("fs").readFileSync("./page.js", "utf8");
let scope;
try { scope = (0, eval)(src +
    "; ({render, IDX, renderDetail, serviceLine, attendanceBlock, recordTerms, getMeta:()=>META, setMeta:(m)=>{META=m;}, queryGroups, expand, groupWeight, searchHint, indexAdd, whyListed, looseness, readShort, spelling, wordsAdd, pairCode, matchScore, yearOf, dkey, VERS, VPICK, VMODE, verKey, hasVersionIndex, setTerm:(t)=>{term=t;}, setFocused:(x)=>{focused=x;}, getFocused:()=>focused, getQuery:()=>query});"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message);
            process.exit(1); }
scope.IDX.length = 0;
scope.IDX.push({id:"HB1442",n:"HB 1442",title:"a bill",status:"Passed one chamber",
  kind:"active",committees:["House Finance"],topic:"Insurance",sponsor:"Nelson, Jodi",
  sponsor_label:"Rep. Jodi Nelson (R)",term:"2026",year:"2026",hay:"hb1442"});
try { scope.render(); } catch (e) {
  console.log("RENDER " + e.constructor.name + ": " + e.message); process.exit(1); }
const listHtml = document.querySelector("#results").innerHTML;

// The arrow in a card's corner leads to the standalone page -- no JavaScript,
// its own address. In the search list that is useful. On the focused view it
// is not drawn at all: the reader is already on a detail page for that bill,
// and a corner link to another one reads as a link to where they are.
scope.setFocused("HB1442");
try { scope.render(); } catch (e) {
  console.log("RENDER focused " + e.constructor.name + ": " + e.message);
  process.exit(1); }
const focusHtml = document.querySelector("#results").innerHTML;
scope.setFocused(null);
// THE NUMBER IS THE LINK (C5, 10 October 2026): a card's number and year lead
// to the bill's own page, where the corner arrow did. The bill's own page is
// its record head, with no card number leading to where the reader is.
if (/class="cnum" href=/.test(focusHtml)) {
  console.log("ARROW: the focused view still draws the card's number as a link. It "
              + "points at the standalone page for the same bill, which from a reader's "
              + "seat is the page they are already on"); process.exit(1); }
if (!/<a class="cnum" href="bill[/]2026[/]hb1442" translate="no">HB 1442/.test(listHtml)) {
  console.log("ARROW: the search list drew no link to a standalone page");
  process.exit(1); }
// The tooltip promised "no JavaScript" until the standalone page became this
// same app with one bill open. It is the only place a member of the public
// was told that, and it sat on every card in the list.
if (/title="[^"]*(no JavaScript|without JavaScript)/i.test(listHtml)) {
  console.log("ARROW: the tooltip still promises the page needs no JavaScript, "
    + "which it has since it became a shell for this renderer");
  process.exit(1); }
try { scope.render(); } catch (e) {
  console.log("RENDER unfocused " + e.constructor.name + ": " + e.message);
  process.exit(1); }

// The search box, in both of the places it appears.
//
// On the list, typing narrows the list -- no key to press, which is what a
// search box over a list should do.
const box = document.querySelector("#q");
if (!(box._on.input || []).length) {
  console.log("SEARCH: nothing listens to the search box"); process.exit(1); }
box.value = "insurance";
box.fire("input");
if (scope.getQuery() !== "insurance") {
  console.log("SEARCH: typing on the list view did not run the search");
  process.exit(1); }
box.value = ""; box.fire("input");

// On one bill's own view it must not. The reader is reading that bill, and
// running the search takes it off the screen, so it waits to be told: the
// Return key, or the button beside the box.
scope.setFocused("HB1442");
try { scope.render(); } catch (e) {
  console.log("RENDER refocus " + e.constructor.name + ": " + e.message);
  process.exit(1); }
box.value = "hb1442";
box.fire("input");
if (!scope.getFocused()) {
  console.log("SEARCH: typing in the box left the bill the reader was reading");
  process.exit(1); }
if (scope.getQuery() === "hb1442") {
  console.log("SEARCH: the half-typed query was run before it was confirmed");
  process.exit(1); }
box.fire("keydown", {key: "Enter"});
if (scope.getFocused()) {
  console.log("SEARCH: Return did not confirm the search and leave the bill");
  process.exit(1); }
if (scope.getQuery() !== "hb1442") {
  console.log("SEARCH: Return left the bill without running the search");
  process.exit(1); }

// And the button, which is the same thing for anyone not using a keyboard.
const go = document.querySelector("#qgo");
if (!(go._on.click || []).length) {
  console.log("SEARCH: the search button does nothing"); process.exit(1); }
scope.setFocused("HB1442");
try { scope.render(); } catch (e) {
  console.log("RENDER rerefocus " + e.constructor.name + ": " + e.message);
  process.exit(1); }
box.value = "insurance";
box.fire("input");
go.fire("click");
if (scope.getFocused() || scope.getQuery() !== "insurance") {
  console.log("SEARCH: the search button did not run the search");
  process.exit(1); }
scope.setFocused(null); box.value = ""; go.fire("click");

// And the inside of a card, which render() alone never touches. Every bill on
// the site sat on "Loading..." with its data already fetched, because
// renderDetail threw on its first use of a const declared further down -- and
// nothing here had ever called it.
var detail = {
  next_step:"Passed one chamber", status_source:"General Court docket",
  notes:[], stages:[{label:"House Committee",text:"It was introduced."}],
  narrative:"It was introduced.",
  events:[{date:"2026-03-06",type:"floor",body:"H",cancelled:false,
           raw:"Ought to Pass: MA RC 214-119 03/06/2026",action:"Ought to Pass",
           motion:"MA",vote_kind:"RC",yeas:"214",nays:"119",
           cite:"HJ 7, page 55",cite_url:"https://gc.nh.gov/hj7.pdf"}],
  rollcalls:[{question:"Ought to Pass",date:"2026-03-06",body:"H",yeas:214,nays:119,
              passed:true,vote_kind:"RC",amendment:"2026-0503h",threshold_needed:167,
              tally:{R:{Yea:200,Nay:12},D:{Yea:14,Nay:107}},
              members:[{n:"Rep. Jodi Nelson (R)",p:"R",v:"Yea",s:"nelson, jodi"}]}],
  // Two proceedings that differ in one field. The first has an end the chair
  // announced; the second has one the clustering guessed. They used to draw
  // the same range, which made the guess as strong a claim as the quotation
  // on 3,896 of the 5,283 placed proceedings.
  stations:[{state:"located",bill:"HB1442",kind:"public hearing",tolerance:30,
             start:150,end:900,video_id:"VID1",watch:"https://youtu.be/VID1",
             start_stated:true,end_stated:true,date:"2026-02-03",time:"10:00"},
            {state:"located",bill:"HB1442",kind:"executive session",tolerance:30,
             start:1500,end:2400,video_id:"VID3",watch:"https://youtu.be/VID3",
             start_stated:true,end_stated:false,date:"2026-02-10",time:"13:00"}],
  reports:[{majority_recommendation:"OUGHT TO PASS",minority_recommendation:null,
            source:"House Calendar 9, 2026",
            date:"2026-02-24",dated:"signed",cite:"HC 9",
            cite_url:"https://gc.nh.gov/hc9.pdf",
            reports:[{side:"Committee",author:"Rep. Jodi Nelson",committee:"Commerce",
                      text:"Consistent with RSA 91-A:4.",vote_yeas:19,vote_nays:0}]},
           // A divided report where the MAJORITY wants the bill killed and the
           // MINORITY wants it passed. The colours used to come from which side
           // won, so this row rendered the kill green and the pass red -- the
           // reader's shorthand for "good news" attached to the wrong motion on
           // 1,248 of 2,637 chips.
           {majority_recommendation:"INEXPEDIENT TO LEGISLATE",
            minority_recommendation:"OUGHT TO PASS",
            source:"House Calendar 11, 2026",
            // Dated only from the day the calendar was printed, because no
            // docket line cites HC 11. The page has to say which of the two
            // dates it is showing rather than presenting both as the same.
            date:"2026-03-13",dated:"printed",cite:"HC 11",cite_url:"",
            reports:[{side:"Majority",author:"Rep. A",committee:"Commerce",
                      text:"Against it.",vote_yeas:11,vote_nays:9},
                     {side:"Minority",author:"Rep. B",committee:"Commerce",
                      text:"For it."}]},
           // The Senate's own written report, from the General Court's
           // database. It has to be headed "Senate", cite the Senate's
           // calendar rather than the long source string naming the database,
           // and show its amendment. The written path was hardcoded to
           // "House", which put every one of 1,254 Senate reports under a
           // House committee's name.
           {majority_recommendation:"OUGHT TO PASS WITH AMENDMENT",
            minority_recommendation:"", body:"S",
            source:"Senate committee report, released 2026-05-13",
            date:"2026-05-12",dated:"signed",cite:"SC 18A",
            cite_url:"https://gc.nh.gov/sc18a.pdf",
            reports:[{side:"Committee",author:"Senator Debra Altschiller",
                      committee:"Judiciary",vote_yeas:5,vote_nays:0,
                      amendment:"2026-1219s",
                      text:"The committee heard that the federal rule is settled."}]},
           // And one of the 350 that record a recommendation and no reasoning.
           // An empty paragraph under a heading reads as a bug; saying the
           // report gives no reasoning is the fact.
           {majority_recommendation:"OUGHT TO PASS",
            minority_recommendation:"", body:"S",
            source:"Senate committee report, released 2026-06-02",
            date:"2026-06-01",dated:"printed",cite:"",cite_url:"",
            reports:[{side:"Committee",author:"Senator Tara Reardon",
                      committee:"Finance",vote_yeas:4,vote_nays:1,
                      amendment:"",text:""}]}],
  // The Senate's shape: one report, a vote, no minority, and no written
  // reasoning anywhere -- 1,531 of them, and the only report at all on 319
  // bills, which the tab used to answer with "not loaded yet".
  docket_reports:[{date:"2026-04-16",dated:"signed",body:"S",
                   committee:"Senate Commerce",side:"",
                   recommendation:"REFERRED TO INTERIM STUDY",
                   vote_yeas:5,vote_nays:0,amendment:"2026-1201s",
                   new_title:false,cite:"SC 14",cite_url:""}],
  // Why a committee that has already reported reports again.
  report_actions:[{before:"2026-03-13",date:"2026-03-05",
                   text:"Recommit (Rep. Berry): MA VV 03/05/2026"}],
  sponsors:[{name:"Nelson, Jodi",party:"R",chamber:"H",prime:true,
             display_full:"Rep. Jodi Nelson (R - Rock 13)"}],
  documents:[{label:"Bill text",url:"https://gc.nh.gov/x.pdf",kind:"text"}],
  amendments:[{num:"2026-0503h",kind:"Committee Amendment",where:"committee",
               date:"2026-02-11",body:"H",adopted:true,vote_kind:"VV",mover:"",
               proposed_by:"the Committee on Commerce",
               text:"Amend RSA 91-A:4 by replacing [the old text] the new.",
               source:"HC010.pdf",targets:["RSA 91-A:4"],supersedes:[]}],
  billtext:{version:"AS AMENDED BY THE HOUSE",title:"AN ACT x",analysis:"A summary.",
            body:"Be it Enacted: Amend RSA 91-A:4.",
            in_text:[{num:"2026-0503h",short:"503h",date:"5Mar2026"}],chars:40},
  // THE VERSION APPARATUS WAS DEAD CODE IN THIS HARNESS. hasVersionIndex is
  // false unless the record carries nver > 1 or namd, renderVersions returns
  // "" the moment it is, and no fixture here set either -- so the picker, the
  // bars, the count line and the whole diff view were never rendered once by
  // any check, under --code or the full run. The only guard was a source-text
  // check on app.js, which opens no version file and would have stayed green
  // through any change to their shape. Found while planning to change exactly
  // that shape, which would otherwise have shipped blind.
  nver:2, namd:1,
  rsa:{"RSA 91-A:4":"https://gc.nh.gov/rsa/html/VI/91-A/91-A-4.htm"}};
if (typeof scope.renderDetail !== "function") {
  console.log("renderDetail is not reachable from the harness"); process.exit(1); }

// A bill number resolves WITHIN the selected term. HB1 exists in every
// biennium, and finding the first row with that number across the whole index
// served the 2025 bill's history under the 2023 bill's heading -- the card
// read "filed 2023" and the body read "introduced on February 20, 2025".
if (typeof scope.yearOf === "function" && typeof scope.setTerm === "function") {
  const savedIdx = scope.IDX.slice();
  scope.IDX.length = 0;
  scope.IDX.push({id:"HB1", n:"HB 1", year:2026, term:"2025-2026", title:"the new one",
                  status:"In committee", kind:"active", nrc:0, committee:"", topic:"",
                  last_action:"2026-02-01", votedays:[]},
                 {id:"HB1", n:"HB 1", year:2024, term:"2023-2024", title:"the old one",
                  status:"Killed", kind:"done", nrc:0, committee:"", topic:"",
                  last_action:"2024-02-01", votedays:[]});
  scope.setTerm("2023-2024");
  if (scope.yearOf("HB1") !== "2024") {
    console.log("yearOf ignored the selected term: got " + scope.yearOf("HB1")
                + " for HB1 in 2023-2024"); process.exit(1); }
  const oldKey = scope.dkey("HB1");
  scope.setTerm("2025-2026");
  if (scope.yearOf("HB1") !== "2026") {
    console.log("yearOf did not follow the term back: got " + scope.yearOf("HB1"));
    process.exit(1); }
  if (scope.dkey("HB1") === oldKey) {
    console.log("the detail cache key is the same in both terms, so switching "
                + "term serves the other bill's record"); process.exit(1); }
  scope.IDX.length = 0;
  savedIdx.forEach(x => scope.IDX.push(x));
  scope.setTerm(null);
}
// Length alone does not prove a branch ran: the tabs and panes are ~1,600
// characters of markup before a single field is read, so a renderDetail that
// silently dropped every body would still clear the threshold below. Each
// fixture therefore names sentences only its own branches can produce.
// "want" is required in both views; "wantFocused" only in the expanded one,
// because the bill text section is the one thing the collapsed card omits.
var fixtures = [
  // Colour follows the motion, not the side that carried it. The fixture's
  // second report has the majority moving Inexpedient to Legislate and the
  // minority moving Ought to Pass, so these two strings can only appear if the
  // chip is coloured by what was moved.
  {name:"full", d:detail,
   // The one chip, the record's capitals in Title Case (components.js
   // titleWords; the component plan's step 3, 9 October 2026).
   want:['class="chip cstat s-done">Inexpedient to Legislate',
         'class="chip cstat s-law">Ought to Pass',
         // Each report says when, and whether that is the day the committee
         // signed or the day the calendar carrying it was printed.
         "Feb 24, 2026",
         "as printed",
         // The Senate's report is drawn at all, coloured by its motion, and
         // says why there is no reasoning under it.
         'class="chip cstat s-study">Referred to Interim Study',
         "Senate Commerce",
         // The Senate's report carries the same three-part heading as the
         // House's -- who, by what vote, for what motion -- rather than a
         // bare tally, and its amendment is a fact of its own rather than
         // part of the footnote explaining what is missing.
         '<span class="secsub">Committee</span>',
         "Amendment 2026-1201s",
         "not on the site; this is what the docket records",
         // The Senate's written report is headed by its own chamber and cites
         // the Senate's calendar, not the database it was read out of.
         "Senate Judiciary",
         // In words, as the House's "House Calendar 14" is (17 October 2026).
         '<a href="https://gc.nh.gov/sc18a.pdf" rel="noopener">Senate Calendar 18A</a>',
         "Senator Debra Altschiller",
         "Amendment 2026-1219s.",
         "the federal rule is settled",
         // And a report with no reasoning says so instead of leaving a space.
         "gives no reasoning",
         // And what happened between the two House reports.
         "Between these reports the docket",
         // The tab counts what the tab draws: three written blocks and the
         // Senate's one. It used to count only the written ones.
         // Shortened from "Committee reports": six labels wrapped onto four
         // rows on a 289px card, and this was the longest of them.
         "Reports (6)",
         // Votes counts d.rollcalls, which the pane draws, not b.nrc, which
         // omits procedural and voice votes. The Hearings tab lists a bill's
         // sittings and counts the ones with a RECORDING, which is why its
         // number can be absent on a term that has none -- it was headed
         // "Videos" until 17 September, over entries that for fifteen terms
         // all read "No recording exists". The fixture has one roll call and
         // two recorded stations. (This is JavaScript: a # here is a syntax
         // error, and was.)
         "Votes (1)",
         // Videos since 19 November 2026 (the owner).
         "Videos (2)",
         // A start and an end, and nothing else. Both stations here start at a
         // boundary the chair announced, so neither carries the one word that
         // marks an inference. The Hearings tab is one player and a playlist
         // (10 November 2026): the first recording's moments are under the
         // player, and the second is a row of the playlist, drawn when chosen.
         // Each moment a play button, named for what it is (19 November 2026).
         'aria-label="Play from 00:02:30, where it starts"',
         'aria-label="Play from 00:15:00, where it ends"',
         'data-vwpick="h1"'],
   // THE VERSION PANE IS ONLY DRAWN WHEN THE CARD IS OPEN, so these belong in
   // wantFocused and not in want. Asserting them in both is how this first
   // failed: the collapsed card renders 13,898 characters of perfectly good
   // markup with no version pane in it, which is correct.
   wantFocused:[
         // THE VERSION PANE, every branch of it, asserted by the sentences
         // only its own code can produce.
         //
         // THE BARS ARE GONE and so are the three assertions that named them:
         // 'class="vseq"', 'class="vstop"' and "70 words out, 180 in" were
         // here for about two hours. They asserted a proportional band drawn
         // between each pair of versions, which was asked to come out as
         // clutter in front of the amendment itself. The picker is the row of
         // buttons in every case now, where it used to be the fallback for a
         // version with no word count.
         'class="vpick"',
         'data-ver=',
         // The count line carries both figures, and names the version
         // compared AGAINST rather than the one being shown -- "+180 -180
         // words against the version before" is what a wrong lookup produces
         // and it reads perfectly plausibly. Asserted as two fragments
         // because the template wraps between "against" and the title, so the
         // rendered markup has a newline and six spaces in the middle of the
         // sentence and no single substring spans it.
         'class="vcount">+180',
         "70 words against",
         "As Introduced</span>"]},
  // A bill with nothing on it yet. The fixture above populates every field, so
  // it only ever runs the arm of each ternary that HAS data -- and every one
  // of those has an else. That is what most bills look like early in a
  // session, and nothing here had ever drawn one.
  {name:"empty", d:{next_step:"Introduced"},
   want:["No roll call votes on this bill",
         "No hearing or meeting is on record for this bill",
         "No committee report on file",
         "No sponsors on file"]},
  // Amendments filed, text not read in yet. This is the only way to reach the
  // middle arm of the bill text block: the section is behind a
  // focused===b.id guard that ALSO requires text or amendments, so the arm
  // for "neither" is unreachable and is not asserted anywhere.
  {name:"amendments only",
   d:{next_step:"Introduced", amendments:detail.amendments},
   want:[], wantFocused:["site yet, but the amendments to it have"]},
  // A report the House Calendar printed under another bill's heading, as
  // report_check.py corrects it: the committee's filed text with a note that
  // says so, or no text and a note saying why. 2021 HB 365's majority report
  // was HB 197's. The second must not also claim the report gave no reasons.
  {name:"misprinted report",
   d:{next_step:"Introduced",
      reports:[{majority_recommendation:"INEXPEDIENT TO LEGISLATE",
                minority_recommendation:"OUGHT TO PASS",
                source:"House Calendar 12, 2021", date:"2021-02-19",
                dated:"printed", cite:"HC 12", cite_url:"",
                reports:[{side:"Majority", author:"Rep. Dave Testerman",
                          committee:"Criminal Justice and Public Safety",
                          text:"HB365 seeks to authorize federal agents to enforce New Hampshire laws.",
                          vote_yeas:17, vote_nays:4,
                          note:"House Calendar 12, 2021 printed HB 197's report here. This is the report as the committee filed it with the Clerk, dated February 8, 2021."},
                         {side:"Minority", author:"Rep. David Meuse",
                          committee:"Criminal Justice and Public Safety", text:"",
                          note:"House Calendar 12, 2021 printed HB 81's report here. The committee's own copy of this report is not in the record here, so no reasoning is shown for it."}]}]},
   want:["printed HB 197's report here", "as the committee filed it with the Clerk",
         "dated February 8, 2021", "HB365 seeks to authorize federal agents",
         "printed HB 81's report here", "no reasoning is shown for it"],
   // Not the day the dump says it was released, which came after House
   // Calendar 12 had printed the report.
   wantNot:["gives no reasoning", "February 23"]},
  // A bill the House did not introduce, as build_site_v2 writes HB 273 of
  // 2017: its docket's two rows, the second a notice with its reason; no
  // station; and a status read from the House Journal. The list of docket
  // lines shows the notice and why, the Hearings tab says the docket noticed
  // a meeting where it draws none, and the status page is not called the
  // page the status is taken from -- that page says IN COMMITTEE.
  {name:"docket notice",
   d:{next_step:"Not introduced", status_source:"House Journal",
      events:[{date:"2016-12-30", text:"Introduced 01/04/2017 and referred to "
                 +"Executive Departments and Administration", routine:false},
              {date:"2017-01-04", text:"Public Hearing: 01/10/2017 01:30 PM LOB 306",
               routine:false, notice:true,
               row_note:"A notice, for a bill the House did not introduce. No record "
                 +"on this site says whether it was held."}],
      documents:[{label:"Bill status page", kind:"status",
                  url:"https://gc.nh.gov/bill_status/legacy/bs2016/Bill_status.aspx"}]},
   want:["Public Hearing: 01/10/2017 01:30 PM LOB 306",
         "A notice, for a bill the House did not introduce.",
         "The docket gave notice of a meeting on this bill",
         "the status shown here is read from the House Journal instead"],
   wantNot:["No hearing or meeting is on record for this bill",
            "the General Court's page saying where the bill stands"]},
  // And the same documents under a status the status page did give.
  {name:"status from the status page",
   d:{next_step:"Introduced", status_source:"General Court bill status page",
      documents:[{label:"Bill status page", kind:"status",
                  url:"https://gc.nh.gov/bill_status/legacy/bs2016/Bill_status.aspx"}]},
   want:["the General Court's page saying where the bill stands",
         "No hearing or meeting is on record for this bill"],
   wantNot:["read from the House Journal instead"]}
];

// BOTH ways a detail can be drawn, on EVERY shape of bill. The expanded view
// runs code the collapsed one never touches -- and a template that reads a
// const declared further down does not throw until something makes it
// evaluate. Testing only the collapsed view passed a page that broke the
// moment a bill was opened.
// THE INDEX THE VERSION PANE READS, which arrives by fetch on a real page and
// therefore never arrives here: dom_stub's fetch answers every request with an
// empty array. Without it renderVersions stops at "Loading the versions..."
// and nothing below that line is ever exercised. Hand-made rather than read
// off disk, because this has to run under --code with no data present.
//
// The numbers are chosen so every branch draws: two versions so there is a
// step, a word count on both so the bars are SIZED (without one the picker
// falls back to a flat row of buttons and the sequence is skipped), and an
// added and a removed figure so the bar has two segments and a sentence.
//
// AND IT IS AN ERROR, NOT A SKIP, if the harness cannot reach them. VERS and
// verKey are not automatically in scope: the eval above returns a named object
// literal, so anything missing from that list is simply undefined here. The
// first version of this guard read `if (scope.VERS && ...)` and quietly did
// nothing when they were absent -- the assertions then failed with "drew
// 16,241 chars but not class=vseq", which points at the renderer and not at
// the harness. A dependency that goes missing has to say so.
if (!scope.VERS || typeof scope.verKey !== "function") {
  console.log("the harness cannot reach VERS/verKey, so the version pane "
              + "cannot be exercised -- add them to the eval's export list");
  process.exit(1); }
{
  scope.VERS[scope.verKey(scope.IDX[0])] = {
    versions: [{title:"As Introduced", date:"2026-01-07", words:1200,
                text_url:"/versions/2026/HB1442.0.txt"},
               {title:"As Amended by the House", date:"2026-03-11", words:1310,
                text_url:"/versions/2026/HB1442.1.txt"}],
    steps: [{from:0, to:1, added:180, removed:70,
             url:"/versions/2026/HB1442.0-1.json"}],
    amendments: [{num:"2026-0503h"}]};
}

for (var fi = 0; fi < fixtures.length; fi++) {
  for (var pass = 0; pass < 2; pass++) {
    var fx = fixtures[fi];
    var mode = fx.name + "/" + (pass ? "focused" : "collapsed");
    try { scope.setFocused && scope.setFocused(pass ? "HB1442" : null); }
    catch (_) {}
    try {
      var html = scope.renderDetail(scope.IDX[0], fx.d);
      if (!html || html.length < 500) {
        console.log("RENDERDETAIL (" + mode + ") produced "
                    + (html ? html.length : 0) + " chars");
        process.exit(1); }
      var want = (fx.want || []).concat(pass ? (fx.wantFocused || []) : []);
      // Words a reader sees may be split by tags -- a tab's count is a badge
      // since 14 October 2026, "Reports" then (6) in spans -- so a wanted
      // phrase is looked for in the markup and in its text.
      var bare = html.replace(/<[^>]+>/g, "");
      for (var wi = 0; wi < want.length; wi++) {
        if (html.indexOf(want[wi]) < 0 && bare.indexOf(want[wi]) < 0) {
          console.log("RENDERDETAIL (" + mode + ") drew " + html.length
                      + " chars but not " + JSON.stringify(want[wi]));
          process.exit(1); }
      }
      var never = fx.wantNot || [];
      for (var ni = 0; ni < never.length; ni++) {
        if (html.indexOf(never[ni]) >= 0) {
          console.log("RENDERDETAIL (" + mode + ") drew "
                      + JSON.stringify(never[ni]) + ", which it must not here");
          process.exit(1); }
      }
    } catch (e) {
      console.log("RENDERDETAIL (" + mode + ") " + e.constructor.name + ": "
                  + e.message);
      process.exit(1); }
  }
}

// A member who sat in both chambers is told apart from one who did not, in
// the order they sat, and a member of one chamber gets no line at all.
var both = scope.serviceLine({service:[{chamber:"H",spans:[[2013,2014],[2025,2025]]},
                                       {chamber:"S",spans:[[2015,2016]]}]});
if (both.indexOf("Votes on record") < 0
    || both.indexOf('<span class="svc">House 2013&ndash;2014, 2025</span> &middot; '
                    + '<span class="svc">Senate 2015&ndash;2016</span>') < 0) {
  console.log("SERVICELINE drew " + JSON.stringify(both)); process.exit(1); }
if (scope.serviceLine({service:[{chamber:"H",spans:[[2019,2026]]}]}) !== ""
    || scope.serviceLine({}) !== "") {
  console.log("SERVICELINE drew a line for a member of one chamber"); process.exit(1); }

// Attendance, for the term the page shows and for every term together. A
// rounded 100% beside an absence is a figure contradicting itself; presiding
// and a declared conflict of interest are named, not counted as missed; what
// was missed is one number, not split into excused and not excused (the
// person's choice of 24 September); and one term draws no total.
var att = {"2023-2024": {chambers:"H", days:33, attended:32, roll_calls:300, voted:299,
                         presided:0, conflict:0, excused:0, not_excused:1, no_vote:0},
           "2025-2026": {chambers:"H", days:33, attended:28, roll_calls:591, voted:51,
                         presided:287, conflict:0, excused:146, not_excused:107, no_vote:0}};
var a1 = scope.attendanceBlock(att, "2023-2024").replace(/\\s+/g, " ");
var a2 = scope.attendanceBlock(att, "2025-2026").replace(/\\s+/g, " ");
var a3 = scope.attendanceBlock({"2011-2012": {chambers:"H", days:45, attended:45,
    roll_calls:538, voted:525, presided:0, conflict:2, excused:6, not_excused:5, no_vote:0}},
    "2011-2012").replace(/\\s+/g, " ");
var a4 = scope.attendanceBlock({"2011-2012": {chambers:"H", days:45, attended:45,
    roll_calls:538, voted:400, presided:125, conflict:2, excused:6, not_excused:5, no_vote:0}},
    "2011-2012").replace(/\\s+/g, " ");
var aw = [[a1, "<b>Days</b> attended 32 of 33 in 2023&ndash;2024 (97%) &middot; absent 1"],
          [a1, "voted on 299 of 300 in 2023&ndash;2024 (99%) &middot; missed 1</p>"],
          [a1, "<b>All 2 terms</b> attended 60 of 66 days (91%)"],
          [a2, "voted on 51 and presided over 287 of 591 in 2025&ndash;2026 (57%) &middot; missed 253</p>"],
          [a2, "when the House held at least one roll call"],
          [a2, "voted on or presided over any roll call that day"],
          [a3, "voted on 525 and declared a conflict of interest on 2 of 538 in 2011&ndash;2012 (98%) "
               + "&middot; missed 11</p>"],
          [a3, "voted on or declared a conflict of interest on any roll call that day"],
          [a4, "voted on 400, presided over 125 and declared a conflict of interest on 2 of 538"],
          [a4, "voted on, presided over or declared a conflict of interest on any roll call"]];
for (var ai = 0; ai < aw.length; ai++) {
  if (aw[ai][0].indexOf(aw[ai][1]) < 0) {
    console.log("ATTENDANCE drew " + JSON.stringify(aw[ai][0]) + " without "
                + JSON.stringify(aw[ai][1])); process.exit(1); } }
if (/xcused/.test(a1 + a2 + a3)) {
  console.log("ATTENDANCE split what was missed into excused and not excused: " + a2);
  process.exit(1); }
var one = scope.attendanceBlock({"2025-2026": att["2025-2026"]}, "2025-2026");
if (/All \\d+ terms/.test(one) || scope.attendanceBlock({}, "2025-2026") !== ""
    || scope.attendanceBlock(undefined, "") !== "") {
  console.log("ATTENDANCE drew a total for one term, or a block for a member with no roll calls");
  process.exit(1); }
// A member whose only ballots of a term were on rules questions has votes
// with no bill year. Their term comes from the roll call, as the Votes tab
// files it; without it the page had no term and drew the note with no figures.
var meta0 = scope.getMeta();
scope.setMeta({terms: ["2001-2002", "2015-2016"]});
var rts = scope.recordTerms("member", {sponsored: [], votes: [{d: "1/3/2001", b: null,
    q: "House Rule 30", v: "Nay", k: "2001-H-2", y: ""}]});
scope.setMeta(meta0);
if (rts.join() !== "2001-2002") {
  console.log("RECORDTERMS gave a member whose one vote was on a rules question the terms "
              + JSON.stringify(rts) + ", not the term the vote was cast in"); process.exit(1); }

// WHAT A SEARCH IS READ AS, from the cases measured on 14 September: words
// with no subject do not have to match, a phrase is one idea in the record's
// own wording, a plural finds its singular, and a hyphen is a space.
var qg = function (q) { return scope.queryGroups(q).map(function (g) { return g.alts; }); };
var guns = qg("bills about guns");
if (guns.length !== 1 || guns[0].indexOf("firearm") < 0) {
  console.log("SEARCH: 'bills about guns' read as " + JSON.stringify(guns)); process.exit(1); }
var funding = qg("public education funding");
if (funding.length !== 1 || funding[0].indexOf("adequate education") < 0) {
  console.log("SEARCH: 'public education funding' read as " + JSON.stringify(funding)); process.exit(1); }
var rentals = qg("short-term rentals");
if (rentals.length !== 1 || rentals[0].indexOf("short term rental") < 0) {
  console.log("SEARCH: 'short-term rentals' read as " + JSON.stringify(rentals)); process.exit(1); }
if (qg("the law").length !== 2) {
  console.log("SEARCH: a search of nothing but skipped words searched for nothing"); process.exit(1); }
if (qg("zoning")[0].indexOf("tenant") >= 0 || qg("pfas")[0].indexOf("water") >= 0) {
  console.log("SEARCH: zoning or pfas is grouped with a different subject again"); process.exit(1); }
// The second pass, reading the bills each search returned. A word keeps its
// own group ("wage", not "wagering"), a short word does not borrow a longer
// entry ("rates" is not "ratepayer"), a name matches only as a whole word,
// and a synonym only as itself or with an ending ("alien", not "alienation").
if (scope.expand("wage").indexOf("wagering") >= 0 || scope.expand("rates").indexOf("ratepayer") >= 0) {
  console.log("SEARCH: 'wage' or 'rates' expands into another subject's group"); process.exit(1); }
var bill = function (t, s, c) { return {hayT: t, hayS: s || "", hayC: c || ""}; };
var bail = scope.queryGroups("bail")[0], imm = scope.queryGroups("immigration")[0];
if (scope.groupWeight(bill("hb1 relative to hunting licenses", "bailey, ann"), bail) > 0) {
  console.log("SEARCH: 'bail' matched a sponsor named Bailey"); process.exit(1); }
// And no name at all (17 October 2026): a sponsor's whole name, first or
// last, matches nothing; the same word in a title still does.
var wade = bill("hb21 relative to housing", "alice wade");
if (scope.queryGroups("alice wade").some(function (g) { return scope.groupWeight(wade, g) > 0; })
    || scope.groupWeight(wade, scope.queryGroups("alice")[0]) > 0
    || scope.groupWeight(bill("hb22 relative to the alice peck day hospital", "jo smith"), scope.queryGroups("alice")[0]) !== 3) {
  console.log("SEARCH: a sponsor's name matches their bill, or a title that says the word no longer does"); process.exit(1); }
if (scope.groupWeight(bill("hb2 relative to parental alienation"), imm) > 0
    || scope.groupWeight(bill("hb3 relative to aliens residing in new hampshire"), imm) !== 3) {
  console.log("SEARCH: a synonym matched inside another word, or missed its plural"); process.exit(1); }
var ev = scope.queryGroups("electric vehicles")[0];
if (scope.groupWeight(bill("hb4 relative to hunting from a vehicle", "", "science, technology and energy"), ev) > 0) {
  console.log("SEARCH: a synonym matched a committee's name"); process.exit(1); }
// The third pass (1 October): a word the table of public words owns is read
// whole, a short word takes a plural and no other ending, an apostrophe typed
// on a phone is an apostrophe, and the line under the box says what the
// titles were searched for without repeating the word typed.
var tr = scope.queryGroups("trans");
if (tr.length !== 1 || !tr[0].exact || tr[0].alts.indexOf("gender identity") < 0
    || scope.groupWeight(bill("hb5 relative to the transfer of state owned real property", "", "house transportation"), tr[0]) > 0
    || scope.groupWeight(bill("hb6 relative to gender identity information on drivers' licenses"), tr[0]) !== 3) {
  console.log("SEARCH: 'trans' is read as the start of transfer or transportation, or misses gender identity"); process.exit(1); }
var aiq = scope.queryGroups("ai")[0];
if (scope.groupWeight(bill("hb7 making school building aid program funds nonlapsing"), aiq) > 0
    || scope.groupWeight(bill("hb8 relative to the use of artificial intelligence by state agencies"), aiq) !== 3) {
  console.log("SEARCH: 'ai' matched 'aid', or missed artificial intelligence"); process.exit(1); }
var carq = scope.queryGroups("cars")[0];
if (scope.groupWeight(bill("hb9 relative to rental car coverage"), carq) !== 3
    || scope.groupWeight(bill("hb10 relative to health care and identification cards"), carq) > 0) {
  console.log("SEARCH: 'cars' missed 'car', or matched 'care' or 'card'"); process.exit(1); }
var curly = scope.queryGroups("driver’s license"), straight = scope.queryGroups("driver's license");
if (JSON.stringify(curly) !== JSON.stringify(straight)
    || !curly.every(function (g) { return scope.groupWeight(bill("hb11 relative to driver’s license suspension"), g) > 0
                                          && scope.groupWeight(bill("hb12 relative to driver's license suspension"), g) > 0; })) {
  console.log("SEARCH: a curly apostrophe is not read as a straight one, in the search or in a title"); process.exit(1); }
if (scope.queryGroups("legalize")[0].alts.indexOf("legaliz") < 0
    || scope.queryGroups("probate")[0].alts.indexOf("probat") >= 0
    || scope.queryGroups("appropriate")[0].alts.indexOf("appropriat") >= 0) {
  console.log("SEARCH: 'legalize' does not reach legalizing, or 'probate' reaches probation, or 'appropriate' appropriations"); process.exit(1); }
var hint = scope.searchHint(scope.queryGroups("lgbtq"),
  [bill("hb6 relative to gender identity information on drivers' licenses"), bill("hb13 relative to state recognition of biological sex")]);
if (/lgbtq/.test(hint) || hint.indexOf("also listing bills that say: ") !== 0
    || hint.indexOf("gender identity") < 0 || hint.indexOf("biological sex") < 0 || /puberty/.test(hint)) {
  console.log("SEARCH: the line under the box does not say which of the bills' words 'lgbtq' found them by, and only those: " + hint); process.exit(1); }
var hg = scope.searchHint(scope.queryGroups("guns"), [bill("hb14 relative to extreme risk protection orders")]);
if (hg.indexOf("also matching: firearm, weapon") !== 0 || hg.indexOf("; then bills that say: ") < 0
    || hg.indexOf("risk protection order") < hg.indexOf("; then ")) {
  console.log("SEARCH: the line under the box does not put a word's own group before the table's terms: " + hg); process.exit(1); }
if (scope.searchHint(scope.queryGroups("xyzzy"), []) !== "") {
  console.log("SEARCH: the line under the box says something about a word nothing stands for"); process.exit(1); }
// The fourth pass (1 October, from the review of the third): a word for an
// attitude is not a subject, a plural reaches the table only as the table
// spells it, a plus sign and a bracket are marks.
var one = function (q) { var g = scope.queryGroups(q); return g.length === 1 ? g[0] : {}; };
if (one("hormone therapy ban").word !== "hormone therapy" || one("anti trans").word !== "trans"
    || one("lgbtq+ rights").word !== "lgbtq rights" || one("287(g)").word !== "287g") {
  console.log("SEARCH: 'ban', 'anti', a plus sign or a bracket is still read as a word a bill must have"); process.exit(1); }
if (one("weeds").exact || one("pots").exact || !one("weed").exact) {
  console.log("SEARCH: the plural of a word the table owns is read as the table's word: 'weeds' is the plant"); process.exit(1); }
if (scope.groupWeight(bill("hb15 defining biostimulants and vitamin hormone products"), one("hormones")) !== 3) {
  console.log("SEARCH: 'hormones' no longer finds a title that says 'hormone'"); process.exit(1); }
// THE BILLS' OWN WORDS: the topic, the analysis and the text, and why.
var tb = function (id, t, topic) { var b = bill(t); b.id = id; b.term = "T"; b.topic = topic || ""; return b; };
if (!scope.indexAdd("T", {v: 1, ids: ["HB1", "HB2", "HB3", "HB4"],
      w: {lavatory: [0, 20], rent: [27], abortion: [78]}, p: {"biological sex": [5]}})
    || scope.indexAdd("T", {v: 2, ids: []}) || scope.indexAdd("T", null)) {
  console.log("SEARCH: a search index of this version is refused, or one of another is taken"); process.exit(1); }
var h1 = tb("HB1", "hb1 permitting classification of individuals under certain circumstances");
var h2 = tb("HB2", "hb2 relative to a registry of the monthly rent charged", "Housing");
var h3 = tb("HB3", "hb3 relative to the rights of conscience of medical professionals", "Welfare/Medicare/Medicaid");
var h4 = tb("HB4", "hb4 relative to the rights of conscience of medical professionals");
var bath = one("bathroom"), abo = one("abortion");
if (!scope.groupWeight(h1, bath) || scope.groupWeight(h2, bath)
    || scope.whyListed(h1, [bath]) !== "text says: lavatory and biological sex") {
  console.log("SEARCH: 'bathroom' does not list the bill whose text says lavatory and biological sex, or lists the one that says lavatory alone, or does not say why: "
              + scope.whyListed(h1, [bath])); process.exit(1); }
if (scope.groupWeight(h1, one("lavatory")) <= 0 || scope.groupWeight(tb("HB2", "hb2 x"), scope.queryGroups("rent")[0]) !== 2.5
    || scope.whyListed(tb("HB2", "hb2 x"), scope.queryGroups("rent")) !== "in the bill's text") {
  console.log("SEARCH: a word a bill's text is about does not find the bill, or does not say it is the text"); process.exit(1); }
if (scope.groupWeight(h4, abo) !== 2.5 || scope.whyListed(h4, [abo]) !== "in the bill's analysis"
    || scope.groupWeight(tb("HB9", "hb9 x"), abo)) {
  console.log("SEARCH: a word in a bill's analysis does not find it, or finds a bill of another id"); process.exit(1); }
var housing = scope.queryGroups("housing"), medicaid = scope.queryGroups("medicaid");
if (scope.whyListed(h2, housing) !== "topic: Housing" || scope.groupWeight(h3, medicaid[0])
    || scope.groupWeight(h2, scope.queryGroups("affordable housing")[0])) {
  console.log("SEARCH: a typed word that is the topic's name does not list the topic's bills, or a topic naming three subjects lists for one, or a phrase is answered by a topic"); process.exit(1); }
if (scope.looseness(tb("HBX", "hb20 relative to housing"), housing) >= scope.looseness(h2, housing)
    || scope.looseness(h2, housing) >= scope.looseness(tb("HB2", "hb2 x"), scope.queryGroups("rent"))) {
  console.log("SEARCH: the order is not the word in the title, then the topic, then the text"); process.exit(1); }
// WHERE A WORD THIS FILE SUPPLIED MAY BE FOUND, and what two weak findings
// make together (the second review, 1 October). Posting = place in ids * 20,
// + 10 in the analysis, + the weight.
// The pairs (WORDS THAT STAND TOGETHER, 2 October): HB13's analysis says
// "car insurance" in those words; HB18's says "insurance" and, further on,
// "car"; HB19's text says "custody of children", which is custody beside
// child once the words that carry no subject are out.
if (!scope.indexAdd("V", {v: 1, ids: ["HB10", "HB11", "HB12", "HB13", "HB18", "HB19"],
      w: {gun: [7], insurance: [57, 37, 37], custody: [107]}, p: {"risk protection order": [26]},
      b: ["", "", "", scope.pairCode("car", "insurance"), "", scope.pairCode("custody", "child")]})) {
  console.log("SEARCH: a second term's search index is refused"); process.exit(1); }
var vb = function (id, t, topic, s) { var b = bill(t, s); b.id = id; b.term = "V"; b.topic = topic || ""; return b; };
var all = function (b, gs) { return gs.every(function (g) { return scope.groupWeight(b, g) > 0; }); };
var gc = one("gun control");
if (scope.groupWeight(vb("HB10", "hb10 establishing the speed enforcement and awareness fund"), gc)
    || !scope.groupWeight(vb("HB11", "hb11 relative to orders of protection"), gc)
    || scope.whyListed(vb("HB11", "hb11 relative to orders of protection"), [gc]) !== "text says: risk protection order"
    || scope.groupWeight(vb("HB10", "hb10 x"), scope.queryGroups("gun")[0]) !== 2.5) {
  console.log("SEARCH: a single word the table supplied ('gun', for 'gun control') lists a bill whose text alone has it (radar guns), or a phrase of the table no longer does, or the reader's own word is no longer read in the text"); process.exit(1); }
var ci = scope.queryGroups("car insurance");
if (all(vb("HB12", "hb12 relative to health care provider networks"), ci)
    || !all(vb("HB13", "hb13 relative to rental car coverage"), ci)
    || all(vb("HB14", "hb14 relative to health care billing", "Insurance"), ci)) {
  console.log("SEARCH: 'car insurance' lists a bill with 'care' in its title and 'insurance' only in its analysis or its topic, or no longer lists one with 'car' in its title whose analysis says 'car insurance'"); process.exit(1); }
// Two words found apart are not a bill (2 October): "small claims" listed a
// tariff credit for small businesses whose text says "approved claims".
var cc = scope.queryGroups("child custody");
if (all(vb("HB18", "hb18 relative to car registration fees"), ci)
    || !all(vb("HB19", "hb19 relative to parenting plans for a child"), cc)
    || !all(vb("HB19", "hb19 relative to children"), scope.queryGroups("children custody"))
    || all(vb("HB19", "hb19 relative to labor"), scope.queryGroups("labor custody"))) {
  console.log("SEARCH: in a search of several words, a word found only in a bill's analysis or text is counted where it does not stand beside another word of the search ('car' in the title, 'insurance' elsewhere in the analysis), or is not counted where it does ('custody of children')"); process.exit(1); }
// A stale file, from before the pairs: the search lists less, never more.
scope.indexAdd("W", {v: 1, ids: ["HB13"], w: {insurance: [17]}, p: {}});
var stale = bill("hb13 relative to rental car coverage"); stale.id = "HB13"; stale.term = "W";
if (all(stale, ci)) {
  console.log("SEARCH: with a search index that has no pairs, a word in the analysis is still counted beside a word of the title"); process.exit(1); }
var pt = scope.queryGroups("property taxes");
if (!all(vb("HB15", "hb15 requiring the assessment of real property", "Taxes - Local"), pt)
    || scope.whyListed(vb("HB15", "hb15 requiring the assessment of real property", "Taxes - Local"), pt) !== "topic: Taxes - Local"
    || all(vb("HB16", "hb16 relative to rights in private roads", "Civil Actions"), scope.queryGroups("civil rights"))
    || all(vb("HB17", "hb17 relative to notice of death affidavits", "Property - Real and Personal"), pt)) {
  console.log("SEARCH: in a search of several words a topic must be that word and nothing else, with the other words in the title: 'property taxes' and the topic Taxes, not 'civil rights' and Civil Actions"); process.exit(1); }
if (scope.groupWeight(bill("hb18 relative to election officers", "lucy weed"), one("weeds"))
    || scope.groupWeight(bill("hb19 relative to the sale of knives"), one("knife")) !== 3
    || scope.groupWeight(bill("hb20 relative to the welfare of a child"), one("children")) !== 3) {
  console.log("SEARCH: 'weeds' is read as a sponsor named Weed, or 'knife' does not find 'knives', or 'children' 'child'"); process.exit(1); }
var ta = scope.queryGroups("transgender athlete ban"), tas = scope.queryGroups("transgender athletes");
if (ta.length !== 1 || ta[0].word !== "transgender athlete" || !ta[0].with
    || JSON.stringify(ta[0].alts.slice(2)) !== JSON.stringify(tas[0].alts.slice(1))) {
  console.log("SEARCH: 'transgender athlete' is not read as the table's 'transgender athletes'"); process.exit(1); }
// A SEARCH THAT LISTS NOTHING. Nothing is read again by itself (the second
// review): a misspelt word is OFFERED as the word it sounds like, and only
// once the words every bill uses say that it is not one.
var rs = [h1, h2, tb("HB5", "hb5 relative to medicaid eligibility"), tb("HB6", "hb6 relative to medicare supplements"),
          tb("HB7", "hb7 relative to special education complaints"),
          tb("HB8", "hb8 enabling the treasurer to invest with certain funds"),
          tb("HB9", "hb9 relative to pistol permits")];
var listed = function (q, rows) { var g = scope.readShort(scope.queryGroups(q), rows);
  return rows.filter(function (b) { return all(b, g); }).length; };
if (listed("medicade", rs) || listed("incest", rs) || listed("wiith", rs) || !listed("medicaid", rs)) {
  console.log("SEARCH: a word no bill here has is read as another word by itself, and its bills listed"); process.exit(1); }
var sp0 = scope.spelling(scope.queryGroups("medicade"), rs);
if (!sp0 || !sp0.need || sp0.q || scope.spelling(scope.queryGroups("medicaid"), rs)) {
  console.log("SEARCH: a word is offered before the words every bill uses are known, or one is offered for a search that finds bills"); process.exit(1); }
if (scope.wordsAdd({v: 2, words: "incest"}) || scope.wordsAdd({v: 1, words: ""}) || scope.wordsAdd(null)
    || !scope.wordsAdd({v: 1, n: 3, words: "incest pistillate special"})) {
  console.log("SEARCH: a words file of another version or with nothing in it is taken, or a good one refused"); process.exit(1); }
var md = scope.spelling(scope.queryGroups("medicade"), rs);
if (!md || md.q !== "medicaid" || md.n !== 1 || md.read.length !== 1 || md.read[0].join(">") !== "medicade>medicaid") {
  console.log("SEARCH: 'medicade' is not offered as Medicaid, the word it sounds like and not the one it is a letter from: " + JSON.stringify(md)); process.exit(1); }
if (scope.spelling(scope.queryGroups("incest"), rs)) {
  console.log("SEARCH: 'incest', a word the bills use, is offered as another word ('invest')"); process.exit(1); }
if (scope.spelling(scope.queryGroups("wiith"), rs)) {
  console.log("SEARCH: a word is offered as one the search skips ('with')"); process.exit(1); }
var pl = scope.spelling(scope.queryGroups("pistal"), rs);
if (!pl || pl.q !== "pistol" || scope.spelling(scope.queryGroups("pistil"), rs)) {
  console.log("SEARCH: 'pistal' is not offered as 'pistol', or 'pistil', the start of a word the bills use, is"); process.exit(1); }
if (scope.spelling(scope.queryGroups("haiti"), rs.concat([tb("HB21", "hb21 relative to hate crimes")]))) {
  console.log("SEARCH: a short word two letters from another is offered as it ('haiti' as 'hate')"); process.exit(1); }
// Two letters, as the start of a word: only in a term where the search as
// typed lists nothing, and decided term by term, so that searching more
// terms never lists fewer of one term's bills. The term that lists something
// has "ed" as a word of a title: until 17 October 2026 it was a sponsor named
// Ed, and a name now lists nothing.
var u1 = bill("hb1 naming the ed smith special olympics field"), u2 = bill("hb2 relative to special education aid");
u1.id = "HB1"; u1.term = "U"; u2.id = "HB2"; u2.term = "U";
var both = rs.concat([u1, u2]), se = scope.readShort(scope.queryGroups("special ed"), both);
if (!all(rs[4], se) || !all(u1, se) || all(u2, se) || all(rs[4], scope.queryGroups("special ed"))
    || listed("special ed", both) < listed("special ed", rs)) {
  console.log("SEARCH: 'special ed' does not read 'ed' as the start of a word in the term where it lists nothing, or does where it lists something, or lists fewer bills over two terms than over one"); process.exit(1); }
console.log("ok");
""", encoding="utf-8")
        r = _run(["node", "go.js"], cwd=root, capture_output=True,
                           text=True, timeout=90)
        assert r.returncode == 0, (r.stdout + r.stderr).strip().splitlines()[0][:150]
        return "ok", ("loaded in node, drew a bill and rendered its detail "
                      "on four shapes of bill, collapsed and focused")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("frontend", "every station state the builder emits has a branch on the page")
def _states_covered():
    """The states build_site_v2 can produce, against the states bills.html draws.

    This exists because of a specific failure. renderHearings tested `located`
    and `approximate` in one if/else chain and then opened a SECOND chain with
    `if (whole_video)`, so a station that matched the first chain fell through
    the second to its `s.video_id` catch-all, which overwrote the inner it had
    just built. Separately, the builder emitted `stated` and `floor_stated`,
    which matched no branch at all. Between them, 5,453 stations carried a real
    timestamp that the page replaced with "the moment was not identified" --
    the site drew 742 of the 6,195 timestamps it held, and every check passed.

    Two halves, because either alone would have missed it: the states must be
    covered, and the chain must be a single chain.
    """
    b = _paths.locate("build_site_v2.py")
    stn = _paths.locate("stations.py")
    hr = _paths.locate("hearing_reports.py")
    page, h = page_source()
    if not (b.exists() and stn.exists() and hr.exists() and h):
        return "skip", "build_site_v2.py, stations.py, hearing_reports.py or bills.html not here"
    src = _source(b) + _source(stn) + _source(hr)

    emitted = set(re.findall(r'"state":\s*"(\w+)"', src))
    emitted |= set(re.findall(r'\["state"\]\s*=\s*"(\w+)"', src))
    emitted |= set(re.findall(r'"state",\s*"(\w+)"', src))
    # Ternaries: "state": "stated" if said else state -- the else arm is a
    # variable holding one of these, set just above.
    emitted |= set(re.findall(r'state,\s*start\s*=\s*"(\w+)"', src))
    assert emitted, "no station states found in build_site_v2.py or stations.py"

    # hearingPlace (the recorded states' one chain, on `st`) and hearingCard.
    drawn = set(re.findall(r'(?:s\.state|\bst)\s*===\s*"(\w+)"', page))
    assert drawn, "no state tests found in bills.html"

    # novideo and prestream mean there is nothing to play; the page handles
    # prestream by name and novideo by falling through to its final else.
    missing = sorted(emitted - drawn - {"novideo"})
    assert not missing, ("the builder emits " + ", ".join(missing)
                         + " and the page draws no branch for it")

    # One chain. A second `if (s.state===...)` after the first restarts the
    # else-ladder and lets a later catch-all overwrite an earlier match.
    opens = [m.start() for m in re.finditer(r'(?<!else )if\s*\(st\s*===', page)]
    assert len(opens) <= 1, (f"{len(opens)} separate if-chains test s.state; a "
                             "station matching an earlier chain is overwritten "
                             "by the catch-all in a later one")
    return "ok", f"{len(emitted)} states emitted, all drawn, one chain"


@check("frontend", "the Summary's How It Got Here and story mark the glossary's terms for their popovers, "
                   "once, and never inside a link")
def _summary_glossary_marked():
    """The owner, 10 November 2026: "the summary does not appear to have
    tooltips for things like roll call or voice vote". glossPass marks the
    first use of each term the glossary holds (a data-term span, which
    components.js turns into the popover), across How It Got Here and then the
    story, never inside a link and never a second time."""
    d = dict(_SUMMARY_VOTES["d"])
    d["journey"] = {"steps": [
        {"date": "2025-04-10", "body": "S", "mark": "p", "act": "passed", "text": "Passed on a voice vote"},
        {"date": "2025-05-01", "body": "H", "mark": "x", "act": "killed", "text": "Killed on a roll call, 16–8"},
        {"date": "2025-05-02", "body": "H", "mark": "p", "act": "passed", "text": "Ought to Pass on a voice vote"},
        {"date": "2025-05-03", "body": "H", "mark": "p", "act": "passed", "text": "Sent to interim study"},
    ]}
    d["stages"] = [{"label": "On the House Floor", "text":
                    "On April 10, 2025 the House voted on a roll call 16–8, then killed it on a voice vote. "
                    "It was Inexpedient to Legislate and the consent calendar took it up."}]
    html = _app_js("(() => { const S = " + json.dumps({"b": _SUMMARY_VOTES["b"], "d": d})
                   + "; return scope.renderSummary(S.b, S.d, null); })()", names=("renderSummary",))
    if html is None:
        return "skip", "node or app.js is not here"
    marks = re.findall(r'<span data-term="([^"]+)">([^<]*)</span>', html)
    keys = [k for k, _w in marks]
    assert len(keys) == len(set(keys)), f"a term is marked twice: {keys}"
    for k in ("VV", "RC", "OTP", "IS", "ITL", "CC"):
        assert k in keys, f"{k} is not marked in the Summary: {keys}"
    # The first use is the one marked: the journey's voice vote, not the story's.
    assert html.index('data-term="VV"') < html.index('class="story"'), "the voice vote marked is not the first"
    assert not re.search(r'<a [^>]*>[^<]*<span data-term', html), "a term is marked inside a link"
    return "ok", "roll call, voice vote, interim study and the rest marked at their first use, none twice, none in a link"


@check("frontend", "no const is read before the line that declares it")
def _tdz():
    js, f = page_source()
    if not f:
        return "skip", "bills.html not here or in site/"
    assert js.strip(), "no script found for bills.html"
    bad = _tdz_suspects(js)
    assert not bad, "; ".join(bad[:3])
    return "ok", "checked every function in app.js"


@check("frontend", "your town's places.json is the town pages' own facts, and the pages that use it carry it")
def _your_town():
    """The header's Your town (12 October 2026) reads site/places.json, which
    build_town_pages writes beside the pages. Every row is a page that was
    built, every member it names has a page, and the Learn pages carry the
    slots find.js fills; and find.js keeps the slug and nothing else."""
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    shared, _base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    d = json.loads((site / "places.json").read_text(encoding="utf-8"))
    places, people = d["places"], d["people"]
    # Silence is not success: a file of no places is a picker with nothing in it.
    assert places, "places.json has no towns"
    towns = {p.stem for p in (site / "town").glob("*.html")}
    assert {p["s"] for p in places} == towns, \
        "places.json and the town pages name different places"
    for p in places:
        assert p["u"] == f"/town/{p['s']}", f"{p['s']}: its address is {p['u']}"
        for m in p["m"]:
            assert m in people and (site / "legislator" / f"{m}.html").exists(), \
                f"{p['s']} names {m}, who has no page"
    # Finding Your Representatives is a how-to guide now, at /guides/ (civics.
    # HOW_TO, 17 October 2026); held where it is, so the box is not let off
    # by a page that moved.
    for page, kind in (("your-representatives", "reps"), ("county-government", "county"),
                       ("city-and-town-government", "town")):
        f = site / ("guides" if page == "your-representatives" else "learn") / f"{page}.html"
        if f.exists():
            assert f'data-yt="{kind}"' in f.read_text(encoding="utf-8"), \
                f"learn/{page} lost its Your town box"
    js = _source(_paths.locate("src/pages/find.js"))
    keeps = re.findall(r"localStorage\.setItem\(([^,]+),([^)]+)\)", js)
    # The town's slug, and the reader's language from Settings (i18n.py, 23
    # October 2026), which is a code ("en", "es") and says nothing of where
    # they live.
    assert keeps == [("YT.key", "s"), ('"gr-lang"', "sel.value")], \
        f"find.js keeps something other than the place's slug and the language: {keeps}"
    return "ok", (f"{len(places)} places, each a built town page, naming "
            f"{len(people)} members who each have a page; find.js keeps only the slug")


@check("frontend", "the Sponsor filter lists a chosen member's own bills first, then the bills they "
       "co-sponsored")
def _sponsor_prime_first():
    """The person, 12 October 2026: "selecting sponsor in the bill search
    filter shows the prime sponsored bills by the selected rep first and then
    the bills they cosponsor". build_site_v2 writes each bill's co-sponsors
    as `cosp`, by the name the filter groups on; app.js matches a sponsor on
    either and puts primeChosen bills first, under two headings. Since Alice's
    8 November 2026 it matches the prime sponsor alone unless "Include
    co-sponsored bills" is ticked (withCosp). The prime sponsor is read
    through spKey (the requests search, 12 November 2026): the name alone for
    a sponsor with a member page or a party, and for one with neither -- the
    surnames the bills before 1999 print -- the name and the seat, so two
    people of one surname are two choices."""
    src = _source("src/pages/build_site_v2.py")
    assert 'row["cosp"] = _cosp' in src and "person_name(s_.get(\"name\")" in src, \
        "the index rows no longer carry their co-sponsors"
    app = _source("src/pages/app.js")
    assert 'if(k==="sponsor")return withCosp&&b.cosp?[spKey(b),...b.cosp]:[spKey(b)];' in app, \
        "the Sponsor filter does not match the prime sponsor alone, or co-sponsors as well when asked"
    assert "rows=rows.filter(primeChosen).concat(rows.filter(b=>!primeChosen(b)))" in app \
        and "const primeChosen=b=>sel.sponsor.has(spKey(b));" in app \
        and '"Prime sponsored":"Co-sponsored"' in app, "a chosen sponsor's own bills are not listed first"
    assert "if(!n||b.sponsor_slug||b.sponsor_party||b.sponsor_person)return n;" in app, \
        "a sponsor with a member page is no longer their name alone in the Sponsor filter"
    assert 'row["sponsor_person"] = 1' in src and "past_roster_shared_names" in src, \
        "a 1989-1998 sponsor the General Court's record names is no longer keyed on the person"
    assert 'SEAT_RE.exec(b.sponsor_label||"")' in app, \
        "a sponsor left as printed no longer keeps the seat in the Sponsor filter"
    return "ok", "co-sponsors in the index; a chosen sponsor's prime bills first, then co-sponsored"


@check("build", "a member's page names a feed exactly where build_feeds writes one")
def _member_feed_links():
    """build_feeds wrote a feed for 406 sitting members and no page linked one,
    so the only way to a member's feed was already knowing its address.

    The page is written first, so it cannot look for the file: both builders
    ask shell.member_followable, the member's counterpart of still_moving. Three
    members: one with votes, one with nothing on record, and one the roster
    counts a vote for that the member's file does not carry -- a site built in
    pieces -- whose page links a feed and so must get one, empty or not.
    """
    here = Path(".").resolve()
    need = ("build_legislator_pages.py", "build_feeds.py", "bills.html")
    absent = [f for f in need if not _paths.locate(f).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    root = Path(tempfile.mkdtemp(prefix="gr-memberfeed-"))
    try:
        site = root / "site"
        (site / "legislators").mkdir(parents=True)
        shutil.copy2(here / "src/pages/bills.html", site / "bills.html")
        _bill_index_write(site, [{"id": "HB9999", "n": "HB 9999", "year": 2023,
                                  "term": "2023-2024", "title": "nobody's bill"}])
        members = [
            {"id": "100", "name": "Voter, Vera", "display": "Rep. Vera Voter",
             "chamber": "H", "district_label": "Rock 1", "slug": "vera-voter-rock-1",
             "n_votes": 2, "n_sponsored": 0},
            {"id": "200", "name": "Newcomer, Ned", "display": "Rep. Ned Newcomer",
             "chamber": "H", "district_label": "Rock 2", "slug": "ned-newcomer-rock-2",
             "n_votes": 0, "n_sponsored": 0},
            {"id": "300", "name": "Partial, Pat", "display": "Rep. Pat Partial",
             "chamber": "H", "district_label": "Rock 3", "slug": "pat-partial-rock-3",
             "n_votes": 1, "n_sponsored": 0}]
        (site / "legislators.json").write_text(json.dumps(members), encoding="utf-8")
        (site / "legislators" / "100.json").write_text(json.dumps({"votes": [
            {"d": "3/6/2026", "b": "HB1", "q": "Ought to Pass", "v": "Yea"},
            {"d": "3/5/2026", "b": "HB2", "q": "Inexpedient to Legislate", "v": "Nay"}]}),
            encoding="utf-8")
        (site / "legislators" / "300.json").write_text(json.dumps({"votes": []}),
                                                         encoding="utf-8")
        for script in ("build_legislator_pages.py", "build_feeds.py"):
            r = _run([sys.executable, _paths.script(script), "--site", "site",
                      "--base", "https://x.test"],
                     cwd=root, capture_output=True, text=True, timeout=120)
            assert r.returncode == 0, f"{script}: " + (r.stderr or r.stdout).strip()[-200:]
        seen = {}
        for m in members:
            page = (site / "legislator" / f"{m['slug']}.html").read_text(encoding="utf-8")
            links = f'href="/feed/legislator/{m["id"]}.xml"' in page
            wrote = (site / "feed" / "legislator" / f"{m['id']}.xml").exists()
            assert links == wrote, (
                f"member {m['id']}: the page " + ("names a feed that was not written"
                                                  if links else "does not name its feed"))
            seen[m["id"]] = links
        assert seen == {"100": True, "200": False, "300": True}, (
            f"feeds named for {seen}; wanted the members with a vote or a sponsorship "
            "on the roster (100 and 300) and not the one with neither (200)")
        return "ok", ("a feed named and written for the member with votes and for the one the "
                      "roster counts, neither for the member with nothing on record")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "every bill, legislator and town is one static link from a page a crawler can reach")
def _directory_pages():
    """build_indexes.py, added 13 September: the bill list and the legislator
    search are drawn by script, so a bill page was reachable from the sitemap,
    four homepage links and nothing else, the 406 legislator pages from the town
    pages only, and the town pages from nothing."""
    here = Path(".").resolve()
    if not _paths.locate("build_indexes.py").exists():
        return "skip", "build_indexes.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        site = root / "site"
        (site / "idx").mkdir(parents=True)
        (site / "town").mkdir()
        rows = {"2025-2026": [{"id": "HB1", "n": "HB 1", "year": 2025, "term": "2025-2026",
                               "title": "the budget", "status": "Signed into law"},
                              {"id": "SB2", "n": "SB 2", "year": 2026, "term": "2025-2026",
                               "title": "a second bill", "status": "Killed"}],
                "1989-1990": [{"id": "HB7", "n": "HB 7", "year": 1989, "term": "1989-1990",
                               "title": "an old bill", "status": ""}],
                # The term of requests, as build_lsrs.py writes it: rows
                # marked `lsr`, each with its own page (the "address") until it
                # is a bill (then "moved_to").
                "2027-requests": [{"id": "LSR20270001", "n": "LSR 2027-0001", "year": 2027,
                                   "term": "2027-requests", "title": "a request",
                                   "status": "Filed as a request", "lsr": True,
                                   "address": "request/2027-0001"},
                                  {"id": "LSR20270002", "n": "LSR 2027-0002", "year": 2027,
                                   "term": "2027-requests", "title": "a filed request",
                                   "status": "Introduced as HB 45", "lsr": True,
                                   "address": "request/2027-0002", "moved_to": "bill/2027/hb45"},
                                  # Retired when filing was complete (build_lsrs.retire):
                                  # to the sponsor's page, or the requests' search.
                                  {"id": "LSR20270003", "n": "LSR 2027-0003", "year": 2027,
                                   "term": "2027-requests", "title": "never filed",
                                   "status": "Filed as a request", "lsr": True,
                                   "address": "request/2027-0003",
                                   "moved_to": "legislator/jane-doe-hills-12"},
                                  {"id": "LSR20270004", "n": "LSR 2027-0004", "year": 2027,
                                   "term": "2027-requests", "title": "never filed, no sponsor",
                                   "status": "Filed as a request", "lsr": True,
                                   "address": "request/2027-0004",
                                   "moved_to": "bills?term=2027-requests"}]}
        for term, r in rows.items():
            (site / "idx" / f"{term}.json").write_text(json.dumps(r), encoding="utf-8")
        (site / "meta.json").write_text(json.dumps(
            {"requests": {"term": "2027-requests", "label": "2027 Bill Requests",
                          "n": 1, "withdrawn": 0}}), encoding="utf-8")
        (site / "legislators.json").write_text(json.dumps([
            {"id": "1", "name": "Doe, Jane", "chamber": "H", "party": "Democratic",
             "county": "Hillsborough", "district": "12", "slug": "jane-doe-hills-12",
             "display_plain": "Rep. Jane Doe", "email": "jane@x.test"}]), encoding="utf-8")
        (site / "towns.json").write_text(json.dumps({
            "Concord": [{"county": "Merrimack", "ward": "1"}, {"county": "Merrimack", "ward": "2"}],
            "Acworth": [{"county": "Sullivan", "ward": "0"}]}), encoding="utf-8")
        for slug in ("concord-ward-1", "concord-ward-2", "acworth"):
            (site / "town" / f"{slug}.html").write_text("<p>town</p>", encoding="utf-8")
        shutil.copy(here / "src/pages/bills.html", site / "bills.html")
        (site / "sitemap.xml").write_text("<urlset>\n</urlset>\n", encoding="utf-8")
        r = _run([sys.executable, _paths.script("build_indexes.py"), "--site", "site",
                  "--base", "https://x.test"], cwd=root, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-300:]
        bills = (site / "directory" / "bills-2025-2026.html").read_text(encoding="utf-8")
        assert 'href="bill/2025/hb1"' in bills and 'href="bill/2026/sb2"' in bills, "a bill is not linked"
        assert "<title>Every bill of the 2025\u20132026 term | Granite Record</title>" in bills
        assert 'og:type" content="website"' in bills and "CollectionPage" in bills
        people = (site / "directory" / "legislators.html").read_text(encoding="utf-8")
        assert 'href="legislator/jane-doe-hills-12"' in people and "jane@x.test" not in people
        towns = (site / "directory" / "towns.html").read_text(encoding="utf-8")
        for slug in ("concord-ward-1", "concord-ward-2", "acworth"):
            assert f'href="town/{slug}"' in towns, f"town page {slug} is not linked"
        hub = (site / "directory.html").read_text(encoding="utf-8")
        assert "directory/bills-1989-1990" in hub and "directory/towns" in hub
        # A REQUEST LINKS ITS OWN PAGE, NEVER bill/2027/lsr...: all 241 links
        # on /directory/bills-2027-requests answered 404 (the audit of 2
        # October 2026) because the list wrote bill/2027/lsr20270001 for every
        # row and build_bill_pages.py builds no page for a request. Since 8
        # November every request has its own page (build_request_pages), so
        # each row links it -- or, once the request is a bill, the bill -- and
        # the lead says so. The list is named as the bill search's term picker
        # names it, and the requests are not counted among the terms of bills.
        reqs = (site / "directory" / "bills-2027-requests.html").read_text(encoding="utf-8")
        assert "LSR 2027-0001" in reqs and "bill/2027/lsr" not in reqs, (
            "the list of requests links a bill page for a request, and no builder writes one")
        assert '<a href="request/2027-0001">LSR 2027-0001</a>' in reqs, (
            "a request's row in the directory does not link the request's own page")
        assert '<a href="bill/2027/hb45">LSR 2027-0002</a>' in reqs and "request/2027-0002" not in reqs, (
            "a request now a bill is not linked to its bill, or still links its old address")
        # THE LEAD SAYS NO MORE THAN WHERE THEY ARE SEARCHED (the owner, 14
        # November 2026: "just let the pages speak for themselves"): the
        # rows' links say the rest, retired requests' included.
        assert ('4 requests, by number. <a href="bills?term=2027-requests">The bill search</a> '
                "lists them with their sponsors.") in reqs, (
            "the list of requests' lead is not the count and the link to the bill search")
        for said in ("has its own page", "has no page", "forwards to", "numbered bill"):
            assert said not in reqs, f"the list of requests' lead explains too much: {said!r}"
        assert '<a href="legislator/jane-doe-hills-12">LSR 2027-0003</a>' in reqs \
            and '<a href="bills?term=2027-requests">LSR 2027-0004</a>' in reqs, (
            "a retired request's row does not link where its address forwards")
        assert "<title>2027 Bill Requests | Granite Record</title>" in reqs \
            and "<h1>2027 Bill Requests</h1>" in reqs, (
            "the list of requests is not titled as the term picker names it "
            "(meta.json's requests.label)")
        assert 'href="bills?term=2027-requests"' in reqs, (
            "the list of requests does not lead to the one page that holds them")
        assert ">2027 Bill Requests</a>" in hub and ">2027-requests<" not in hub, (
            "the directory names the requests by their raw key")
        assert "all 2 terms from 1989" in hub, (
            "the directory counts the requests as a term of bills")
        sm = (site / "sitemap.xml").read_text(encoding="utf-8")
        assert sm.count("<loc>") == 6, sm
        # THE ROUTE IS TWO HOPS NOW, AND THE POINT IS THE ROUTE. The footer
        # linked the directory directly until 18 September, when the owner
        # moved that link to the Data page -- in a grey band it was one of
        # four and could not say what it was for. What this check is actually
        # for is that a crawler with no JavaScript can still reach every
        # record, so it follows the chain instead of naming one page: the
        # footer must link the Data page, and the Data page must link the
        # directory. Asserting the old shape would have made a deliberate
        # change look like a regression.
        foot = (here / "src/pages/chrome.py").read_text(encoding="utf-8")
        assert 'href="data.html"' in foot, (
            "the footer does not link the Data page, which is now the route "
            "to the directory and so to every record")
        exports = _source(_paths.locate("build_exports.py"))
        assert 'href="directory.html"' in exports, (
            "the Data page does not link the directory, so nothing static "
            "reaches the per-record lists and a crawler sees no bills")
        return "ok", ("bills by term, legislators and towns linked statically, sitemapped, footer "
                      "links them; each request linked to its own page, or to its bill once it is "
                      "one, under a lead that only names the bill search")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("frontend", "no page promises a feed for a bill that has none")
def _feed_promises():
    """On 13 September feeds narrowed to bills still moving, and the home page
    went on saying "Every bill has its own feed too, linked from its page,
    along with one per committee and one per subject" while the Learn page said
    "Every bill, member and committee has an RSS feed" -- neither true, and a
    reader who went looking would have found nothing on the page to click."""
    import inline_js as IJ
    for f, stale in (("build_pages.py", "Every bill has its own feed"),
                     ("civics.py", "Every bill, member and committee has an RSS feed")):
        # The file and its scripts, in inline/ since 20 November 2026.
        text = _paths.locate(f).read_text(encoding="utf-8") + "".join(
            p.read_text(encoding="utf-8") for n, p in IJ.files().items() if n.split(".")[0] == Path(f).stem)
        assert stale not in text, f"{f} still says: {stale}"
    return "ok", "home and Learn say only bills still moving have feeds"


@check("frontend", "the status box without JavaScript says what the scripted one says")
def _status_box_parity():
    """The homepage status box is drawn twice: in Python for readers without
    JavaScript and for crawlers, and again by HOME_JS. On 13 September the
    person set what it should read, and the Python copy had no last floor
    session, no count of hearings and no date -- so it could not say a stale
    summary was stale."""
    import inline_js as IJ
    # The builder and its scripts, in inline/ since 20 November 2026.
    src = _source(_paths.locate("build_pages.py")) + "".join(_source(p) for n, p in IJ.files().items() if n.split(".")[0] == "build_pages")
    py = src[src.find("static_state = \"\""):][:3200]
    js = src[src.find("else if(_state)_state.innerHTML="):][:2400]
    # SINCE 16 SEPTEMBER THE SERVER'S COPY WINS. Both are still written -- the
    # script's is what a page with no built box would get -- but the script
    # draws only where the server drew nothing, because the two disagreed on
    # screen when home.json came from the browser's cache: 39 hearings in the
    # HTML, 4 in the script's box.
    assert '_state.querySelector(".statebox")' in src, (
        "HOME_JS no longer defers to the box build_pages.py rendered, so a "
        "cached home.json can overwrite a fresh page")
    # THE FORTNIGHT'S MEETING COUNT IS NOT IN THIS LIST ANY MORE. It was, and
    # this check is what noticed it going: on 19 September the person asked for
    # it off the status box, because it is a fact about the calendar rather
    # than about the state of the General Court, and the calendar is on the
    # same page saying it better. All three renderers of it went in the same
    # edit -- the built copy, HOME_JS's _meetline and the clock block that
    # counted the days off the total -- so there is nothing left for the two
    # copies to disagree about. What this check is for is the pair drifting
    # apart, and a line removed from both is not drift.
    # NOR THE LAST SESSION DAY (the owner, 19 November 2026): the House and
    # Senate recordings under the box name it already. Gone from both copies
    # in one edit, so neither may bring it back alone.
    assert "state.last" not in js and "state.last" not in py, (
        "the status box draws \"Last Session Day\" again; the owner took it off "
        "on 19 November 2026 (the recordings under it name the day)")
    for what, needle_py, needle_js in (
            # The date is kept hidden for the stale warning since the person
            # asked for no "Summary Updated" line (25 October 2026).
            ("the summary's date", 'data-updated="{esc(S.get("updated")', 'data-updated="${esc(S.updated'),
            ("the stale warning", "stale_days", "S.stale_days")):
        assert needle_js in js, f"HOME_JS no longer draws {what}"
        assert needle_py in py, f"the server-rendered status box lost {what}"
    return "ok", "the summary's date and stale warning in both copies; no last session day in either"


@check("frontend", "tab strips keep the keyboard's place and a page opens on its own first tab")
def _tab_keyboard():
    """Three defects found reading app.js on 12 September. An arrow key clicked
    the next tab, the click redrew the strip, and focus fell to <body> -- every
    press lost the keyboard's place, on every tabbed view. PAGE_TAB outlived the
    page it belonged to, so a committee opened after a member's Votes tab drew
    nothing. And the version picker declared role="tablist" with no tabs."""
    js = _source("src/pages/app.js")
    handler = js[js.find('e.key==="ArrowLeft"'):][:900]
    assert "next.click()" in handler and ".focus()" in handler and \
        handler.find("next.click()") < handler.find("(fresh||next).focus()"), \
        "the arrow-key handler focuses before the redraw, which destroys the tab"
    open_page = js[js.find("function openPage("):][:800]
    assert "PAGE_TAB=0" in open_page.replace(" ", ""), "openPage does not reset PAGE_TAB"
    assert 'class="vpick" role="tablist"' not in js, "the version picker is a tablist with no tabs"
    # That focus survives a redraw is run now, not read: _focus_survives,
    # below, puts focus on a control and draws through each renderer.
    assert "const repaint=" in js, "app.js has no repaint()"
    assert 'id="ptab_${i}" aria-controls="ppane"' in js and 'aria-labelledby="ptab_${PAGE_TAB}"' in js, \
        "member and committee tabs are not tied to their panel"
    return "ok", "an arrow key focuses after the redraw, the tab resets per page, the picker is a group"


# tabStrip in node: one tab, and two (the commit of 14 November 2026 that gave a request's lone
# Summary no strip pasted two of its lines into the member and committee strip as well).
_TAB_STRIP_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8") + "; ({tabStrip})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const out = {};
for (const [k, tabs] of [["one", [["Votes", 12]]], ["two", [["Votes", 12], ["Bills", 3]]]]) {
  try { out[k] = s.tabStrip(tabs); } catch (e) { out[k] = "THREW " + e.constructor.name + ": " + e.message; }
}
console.log("@@" + JSON.stringify(out));
"""


@check("frontend", "a member's or committee's tab strip of one tab draws, and of two draws both")
def _tab_strip_single():
    """Commit 6c6ee490 (14 November 2026) left two lines of the request page's strip in app.js's
    tabStrip, the member and committee pages' strip: an unused `const pane` and a line that read
    an undefined `b` whenever a page had one tab, so such a page threw instead of drawing. Run
    in node: one tab draws one tab button and two draw two, neither throwing."""
    got = _node_app(_TAB_STRIP_HARNESS)
    if got is None:
        return "skip", "node, app.js or the DOM stub is not here"
    bad = [f"{k}: {v[:160]}" for k, v in got.items() if v.startswith("THREW")]
    assert not bad, "tabStrip threw: " + "; ".join(bad)
    n = {k: v.count('role="tab"') for k, v in got.items()}
    assert n == {"one": 1, "two": 2}, f"tab buttons drawn: {n}"
    assert 'class="tabs" role="tablist"' in got["one"], got["one"][:200]
    return "ok", "a strip of one tab draws its one tab and a strip of two its two, in node"


# The harness of _focus_survives, run in node beside page.js (app.js) and
# stub.js (dom_stub.js). A raw string: the selectors it compares carry
# backslashes.
_FOCUS_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
globalThis.CSS = {escape: s => String(s).replace(/["\\|#.:\[\]]/g, "\\$&")};
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({focusKey, refocus, render, renderPage, renderFacets, IDX, setPage:(p)=>{PAGE=p;}, setMeta:(m)=>{META=m;}})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
// A control, as focusKey reads one: its tag, id, data attributes, classes,
// the card it is in, and whether it is inside what a redraw replaces.
const body = document.body;
const live = {};                       // selector -> the controls it matches now
document.querySelectorAll = sel => live[sel] || [];
function ctl(tag, o) {
  o = o || {};
  return {tagName: tag.toUpperCase(), id: o.id || "", dataset: o.data || {},
    classList: o.classes || [], focused: 0, isConnected: true,
    getAttribute: k => (o.attrs || {})[k] ?? null,
    closest: q => q === "#results,#facets" ? (o.outside ? null : {})
      : q === ".card[data-id]" ? (o.card ? {dataset: {id: o.card}} : null) : null,
    focus() { this.focused++; document.activeElement = this; }};
}
const out = {keys: {}};
const kinds = {
  tab: ctl("button", {id: "tab_HB2_1", data: {t: "1"}, classes: ["tab"], card: "HB2"}),
  facet: ctl("input", {data: {f: "topic"}, attrs: {value: "Education"}}),
  head: ctl("button", {classes: ["chead"], card: "HB2"}),
  legend: ctl("button", {data: {seg: "HB2|0|R-Yea"}, classes: ["lrow"], card: "HB2"}),
  term: ctl("select", {data: {pf: "term"}}),
  group: ctl("button", {data: {g: "committee"}, classes: ["fhead"]}),
  more: ctl("button", {data: {more: "1"}, classes: ["link"]}),
  search: ctl("input", {id: "q", outside: true}),
};
for (const [k, e] of Object.entries(kinds)) { const key = s.focusKey(e); out.keys[k] = key && key.sel; }
out.none = [s.focusKey(null), s.focusKey(body)];

// Each renderer, with focus on a control it is about to replace. The slot the
// renderer writes is a stand-in whose innerHTML, when set, does what a
// browser does: the old control is gone, focus is on <body>, and a copy of
// the control is in its place.
function through(name, draw, slot, old) {
  const key = s.focusKey(old);
  const fresh = ctl("x");
  live[key.sel] = [old];
  document.activeElement = old;
  const real = document.querySelector(slot), find = document.querySelector;
  const box = Object.create(real, {innerHTML: {get() { return real.innerHTML; },
    set(v) { real.innerHTML = v; if (document.activeElement === old) document.activeElement = body;
             live[key.sel] = [fresh]; }}});
  document.querySelector = q => q === slot ? box : find.call(document, q);
  try { draw(); out[name] = {refocused: fresh.focused, active: document.activeElement === fresh}; }
  catch (e) { out[name] = "THREW " + e.message; }
  delete live[key.sel];
  document.querySelector = find;
}
s.setMeta({terms: ["2025-2026"], committee_codes: {}, topics: []});
s.IDX.length = 0;
s.IDX.push({id: "HB1442", n: "HB 1442", title: "a bill", status: "Passed", kind: "active",
  committees: ["House Finance"], topic: "Insurance", sponsor: "Nelson, Jodi", term: "2026",
  year: "2026", hay: "hb1442"});
through("render", () => s.render(), "#results", kinds.head);
through("renderFacets", () => s.renderFacets(), "#facets", kinds.facet);
through("render, of a filter", () => s.render(), "#facets", kinds.group);
s.setPage({kind: "committee", data: {code: "H34", name: "Finance", chamber: "H", bills: [],
  sessions: [], members: []}, terms: ["2025-2026"], term: "2025-2026", status: ""});
through("renderPage", () => s.renderPage(), "#results", kinds.term);
// Focus the redraw did not take is left where it is.
s.setPage(null);
const kept = kinds.search; document.activeElement = kept;
live["#q"] = [ctl("x")];
s.render();
out.kept = document.activeElement === kept && live["#q"][0].focused === 0;
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("frontend", "a bill's own page starts at the top, stays on the bill at its skip link, and leaves "
                   "by a link to the bill search with the words of a search run from it")
def _bill_page_start_and_exit():
    """The audit of 2 October 2026, S7 and S14, and what the review of their
    fixes found.

    S7. app.js put focus in the bill search box on load, on the search page
    and on every bill's own page: on /bill/2025/hb2 the first Tab press went
    to the box's button, so "Skip to this bill" and the nav were behind the
    starting point. The box takes focus only where there is no bill named.

    AND THE SKIP LINK STAYS ON THE BILL. That made "Skip to this bill" the
    first Tab stop on 33,717 pages, and pressing it left for the bill search:
    a link to a place on the page fires popstate with no state, which the
    handler took for "back to the list", and on a bill's own page going back
    to the list is leaving the page. The handler does nothing where only the
    fragment moved, or where the address is still a bill's own.

    S14. "Back to bill search" was a button that called history.back(). Opened
    directly, a bill's page left the site; reached from a member's page, it
    went back to the member. It is a link to /bills, and a plain click goes
    back in history only where back is the search: in the search itself,
    where the bill was opened over the list, or on a bill's own page when the
    referrer is this site's /bills and there is a page behind it in the tab.

    AND WHERE THE ADDRESS OPENED THE BILL, IT DRAWS THE LIST. /bills#2025/HB2
    -- the home page's Latest activity and the calendar link to it -- pushed
    nothing, so in the search back was the home page, or nothing in a new tab.
    There the click shows the list in place.

    AND A SEARCH RUN FROM A BILL'S OWN PAGE TAKES ITS WORDS. It left for
    /bills with an empty box and wrote the search onto the bill's own entry
    in history. It goes to /bills?q=, with the term where the picker beside
    the box names one that is not the newest; and Return on the list writes
    the search into the list's address, which is run here, not read.
    """
    js, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and stub.exists() and node):
        return "skip", "app.js, dom_stub.js or node is not here"
    src = _source(js)
    boxes = re.findall(r'^[ \t]*(.*\$\("#q"\)\.focus\(\);)[ \t]*$', src, re.M)
    onload = [b for b in boxes if "e.detail" not in b and "preventDefault" not in b]
    assert onload == ['if(!window.GR_BILL)$("#q").focus();'], (
        f"the bill search box is focused as the page loads by {onload}: on a bill's own "
        "page that puts the skip link and the nav behind the starting point")
    assert src.count("history.back();") == 1 and \
        "if(backIsSearch()){e.preventDefault();history.back();}" in src, (
            "something in app.js calls history.back() without asking backIsSearch(): "
            "back is wherever the reader came from, which a label naming a place cannot promise")
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(src), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        (root / "go.js").write_text(_HEARD_PRELUDE + r"""
load("render, IDX, backIsSearch, addressed, focusBill, setFocused:(x)=>{focused=x;},"
  + " getFocused:()=>focused, setMeta:(m)=>{META=m;}, setTerm:(t)=>{term=t;}");
const out = {};
s.setMeta({terms: ["2025-2026", "2003-2004"], committee_codes: {}, topics: []});
s.IDX.length = 0;
s.IDX.push({id: "HB1442", n: "HB 1442", title: "a bill", status: "Passed", kind: "active",
  committees: [], topic: "", sponsor: "", term: "2025-2026", year: "2026", hay: "hb1442"});
s.setTerm("2025-2026");
s.setFocused("HB1442"); s.render();
out.back = (/<a [^>]*data-back="1"[^>]*>/.exec(document.querySelector("#results").innerHTML) || [""])[0];
const at = (standalone, referrer, length, state) => { window.GR_STANDALONE = standalone;
  document.referrer = referrer; history.length = length; history.state = state || null;
  return s.backIsSearch(); };
out.is = {
  inSearch: at(false, "", 1, {focus: "HB1442"}),
  inSearchByItsAddress: at(false, "https://x/", 2, null),
  inSearchAtAPlaceOnIt: at(false, "", 3, null),
  fromSearch: at(true, "https://x/bills?q=budget", 2),
  fromSearchHtml: at(true, "https://x/bills.html", 3),
  newTab: at(true, "https://x/bills", 1),
  direct: at(true, "", 1),
  fromMember: at(true, "https://x/legislator/jane-doe", 4),
  fromElsewhere: at(true, "https://example.org/bills", 2),
  fromABill: at(true, "https://x/bills/x", 2),
};

// THE SKIP LINK, AND BACK AND FORWARD. Each is what the browser does to the
// address, then the popstate it fires.
out.pop = {};
// A bill's own page; "Skip to this bill" moves the fragment and nothing else.
place("/bill/2026/hb1442", null, true); s.setFocused("HB1442");
location.hash = "#results"; pop(null); out.pop.skipOwn = seen();
// The same on a tab's address, and back from it to an entry of another tab.
place("/bill/2026/hb1442/votes", null, true); s.setFocused("HB1442");
location.hash = "#results"; pop(null); out.pop.skipOwnTab = seen();
place("/bill/2026/hb1442/text", null, true); s.setFocused("HB1442");
go("/bill/2026/hb1442/votes"); pop(null); out.pop.backOwnTab = seen();
// The search, a bill its address opened: the skip link there.
place("/bills#2026/HB1442", null, false); s.setFocused("HB1442");
location.hash = "#results"; pop(null); out.pop.skipByAddress = seen();
// The search, a bill opened over the list: the skip link, then back to the
// entry that opened the bill, then back to the list.
place("/bill/2026/hb1442", {focus: "HB1442"}, false); s.setFocused("HB1442");
location.hash = "#results"; pop(null); out.pop.skipOverList = seen();
location.hash = ""; pop({focus: "HB1442"}); out.pop.backToItsEntry = seen();
go("/bills"); pop(null); out.pop.backToList = seen();
// A bill's own page, reloaded after it was opened from the search: Back
// reaches the search's entry without a load, and the page loads it as it is,
// words and term, not bare /bills (the review of 7 November 2026).
location.replace = u => { location.href = "replace " + u; };
// The tab's own storage, for this one case: the list loaded is told it is
// Back, so it opens where the reader stood (restorePlace; the second review).
const ss = {};
globalThis.sessionStorage = {getItem: k => (k in ss ? ss[k] : null), setItem: (k, v) => { ss[k] = String(v); },
                             removeItem: k => { delete ss[k]; }};
place("/bill/2026/hb1442", null, true); s.setFocused("HB1442");
go("/bills?q=budget&term=all"); pop(null); out.pop.reloadedBack = seen();
out.reloadedPlace = ss["gr.back"] || null;
delete globalThis.sessionStorage;
// And opened for real, by the card's arrow: the skip link has to name the
// address the bill was given, or pressing it is a journey to another page;
// and name the list's again once the bill is left.
const skip = document.querySelector("a.skip");
skip.setAttribute = (k, v) => { if (k === "href") skip.href = v; };
place("/bills", null, false); s.setFocused(null);
s.focusBill("HB1442");
out.opened = {wrote: wrote.slice(), skip: skip.href};
location.hash = "#results"; pop(null);
out.opened.atSkip = s.getFocused();
go("/bills"); pop(null);
out.opened.left = {skip: skip.href, focused: s.getFocused()};

// "BACK TO BILL SEARCH", clicked.
const back = q => q === "[data-back]" ? {} : null;
const pressed = (path, state, standalone, referrer, ev) => {
  place(path, state, standalone); document.referrer = referrer || ""; history.length = 2;
  s.setFocused("HB1442");
  const e = click(back, ev);
  return Object.assign(seen(), {prevented: e.prevented});
};
out.click = {
  byAddress: pressed("/bills#2026/HB1442", null, false, "https://x/"),
  // ...and over a search: its words are the list's (the reviews of 7 November 2026).
  byAddressWithWords: pressed("/bills?q=budget#2026/HB1442", null, false, "https://x/"),
  overList: pressed("/bill/2026/hb1442", {focus: "HB1442"}, false),
  ownFromMember: pressed("/bill/2026/hb1442", null, true, "https://x/legislator/jane-doe"),
  ownFromSearch: pressed("/bill/2026/hb1442", null, true, "https://x/bills?q=budget"),
  newTabOfIt: pressed("/bills#2026/HB1442", null, false, "", {ctrlKey: true}),
  // Over the list, but at a place on the bill: the entry is the fragment's.
  overListAtAPlace: pressed("/bill/2026/hb1442#results", null, false),
};
out.click.overListAtAPlace.skip = skip.href;

// A SEARCH, RUN WITH RETURN in the box.
const box = document.querySelector("#q");
const run = (words, path, state, standalone, open, term) => {
  place(path, state, standalone); s.setFocused(open); s.setTerm(term || "2025-2026");
  box.value = words; box.fire("keydown", {key: "Enter"});
  return seen();
};
out.search = {
  own: run("housing aid", "/bill/2026/hb1442", null, true, "HB1442"),
  ownOlderTerm: run("housing", "/bill/2003/hb1", null, true, "HB1", "2003-2004"),
  ownNoWords: run("", "/bill/2026/hb1442", null, true, "HB1442"),
  overList: run("housing", "/bill/2026/hb1442", {focus: "HB1442"}, false, "HB1442"),
  list: run("HB 2", "/bills", null, false, null),
};
process.stdout.write("\n@@" + JSON.stringify(out));
""", encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js did not run under node: " + (r.stderr or r.stdout or "")[-300:])
        got = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    # The trail's first step, Bills, since 10 October 2026 (the record head,
    # C6), where "Back to bill search" was above the card.
    assert got["back"] == '<a href="/bills" data-back="1">', (
        "\"Back to bill search\" is drawn as " + (got["back"] or "nothing")
        + ": it must be a link to /bills, which is where its label says it goes")
    want = {"inSearch": True, "inSearchByItsAddress": False, "inSearchAtAPlaceOnIt": False,
            "fromSearch": True, "fromSearchHtml": True, "newTab": False,
            "direct": False, "fromMember": False, "fromElsewhere": False, "fromABill": False}
    assert got["is"] == want, (
        "back is taken for the bill search where it is not, or not where it is: "
        + "; ".join(f"{k}: {got['is'].get(k)}" for k, v in want.items() if got["is"].get(k) != v))

    def off(group, want):
        return [f"{k}: {got[group].get(k)}, not {v}" for k, v in want.items()
                if got[group].get(k) != v]

    stay = {"href": "HERE", "wrote": [], "focused": "HB1442"}
    # Back to the list writes nothing: the browser has put the list's own
    # address back, and a /bills pushed over it lost the search's words and
    # the bill's entry for Forward (the laptop's test of 7 November 2026).
    bad = off("pop", {"skipOwn": stay, "skipOwnTab": stay, "backOwnTab": stay,
                      "skipByAddress": stay, "skipOverList": stay, "backToItsEntry": stay,
                      "backToList": {"href": "HERE", "wrote": [], "focused": None},
                      "reloadedBack": {"href": "replace /bills?q=budget&term=all", "wrote": [],
                                       "focused": "HB1442"}})
    assert not bad, (
        "a link to a place on the page, or back from one, leaves the bill or draws the "
        "list over it (the skip link is the first Tab stop on every bill's page): "
        + "; ".join(bad[:3]))
    assert got.get("reloadedPlace") == "1", (
        "a reloaded bill page, then Back: the list it loads is not told it is Back "
        f"(gr.back is {got.get('reloadedPlace')!r}), so it opens at its top, not where the "
        "reader stood in it")
    # A list of no words holds none in its entry, so nothing is written over
    # it before the bill's entry is pushed (THE LIST'S WORDS IN ITS OWN ENTRY).
    opened = {"wrote": ["push /bill/2026/hb1442"], "skip": "/bill/2026/hb1442#results",
              "atSkip": "HB1442", "left": {"skip": "/bills#results", "focused": None}}
    assert got["opened"] == opened, (
        "a bill opened over the list, and left again: the skip link must name the address "
        f"the page is at each time, and pressing it must leave the bill open: {got['opened']}")
    bad = off("click", {
        "byAddress": {"href": "HERE", "wrote": ["push /bills"], "focused": None, "prevented": 1},
        "byAddressWithWords": {"href": "HERE", "wrote": ["push /bills?q=budget"], "focused": None,
                               "prevented": 1},
        "overList": {"href": "HERE", "wrote": ["back"], "focused": "HB1442", "prevented": 1},
        "ownFromMember": {"href": "HERE", "wrote": [], "focused": "HB1442", "prevented": 0},
        "ownFromSearch": {"href": "HERE", "wrote": ["back"], "focused": "HB1442", "prevented": 1},
        "newTabOfIt": {"href": "HERE", "wrote": [], "focused": "HB1442", "prevented": 0},
        "overListAtAPlace": {"href": "HERE", "wrote": ["push /bills"], "focused": None,
                             "prevented": 1, "skip": "/bills#results"}})
    assert not bad, (
        "\"Back to bill search\", clicked, does not go to the search: where the address "
        "opened the bill it must draw the list, where the list is behind it go back, and "
        "anywhere else be the link it is: " + "; ".join(bad[:3]))
    bad = off("search", {
        "own": {"href": "/bills?q=housing%20aid", "wrote": [], "focused": "HB1442"},
        "ownOlderTerm": {"href": "/bills?term=2003-2004&q=housing", "wrote": [], "focused": "HB1"},
        "ownNoWords": {"href": "/bills", "wrote": [], "focused": "HB1442"},
        "overList": {"href": "HERE", "wrote": ["push /bills", "replace /bills?q=housing"],
                     "focused": None},
        "list": {"href": "HERE", "wrote": ["replace /bills?q=HB+2"], "focused": None}})
    assert not bad, (
        "a search run with Return loses its words or writes them onto the wrong address: "
        + "; ".join(bad[:3]))
    return "ok", ("the search box takes focus on load only where no bill is named; the skip "
                  "link and back from it leave the bill as it is, in 6 cases; \"Back to bill "
                  "search\" goes back only where back is the search and draws the list where "
                  "the address opened the bill; a search run from a bill's page keeps its "
                  "words and its term")


@check("frontend", "focus survives every redraw: the control that had it has it again, through each of the three renderers")
def _focus_survives():
    """The audit of 2 October 2026, S1. A redraw replaces the element that has
    focus, and focus fell to <body>: after a facet's checkbox, a card's
    header, a filter group's head, a legend row, the Term and Status selects
    of a member's or a committee's page, and any tab opened with Enter, Space
    or a click, the next Tab press started from the top of the record.
    repaint() restored four kinds of control and only on the redraws that
    went through it.

    render(), renderPage() and renderFacets() each take the key of the control
    that has focus (focusKey) before they draw and give focus back to the
    control with that key (refocus) after. This runs them, in node: a control
    of each kind is given a key that names it and nothing else; each renderer,
    with focus on a control it then replaces, leaves focus on the copy; "Show
    more" is given no key, because what a reader wants after it is the rows it
    brought, where its own handler puts focus (_review_of_audit_fixes); and
    focus on something the redraw does not replace -- the search box while
    the list narrows -- is not moved.
    """
    js, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and stub.exists() and node):
        return "skip", "app.js, dom_stub.js or node is not here"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(js)), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        (root / "go.js").write_text(_FOCUS_HARNESS, encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js did not run under node: " + (r.stderr or r.stdout or "")[-300:])
        got = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    want = {"tab": "#tab_HB2_1",
            "facet": 'input[data-f="topic"][value="Education"]',
            "head": '.card[data-id="HB2"] button.chead',
            "legend": '.card[data-id="HB2"] button[data-seg="HB2\\|0\\|R-Yea"]',
            "term": 'select[data-pf="term"]',
            "group": 'button[data-g="committee"]',
            "more": None, "search": None}
    assert got["keys"] == want, (
        "a control is not keyed by what names it: "
        + "; ".join(f"{k}: {got['keys'].get(k)!r}, not {v!r}"
                    for k, v in want.items() if got["keys"].get(k) != v))
    assert got["none"] == [None, None], "nothing focused, or <body>, is given a key"
    lost = [k for k in ("render", "renderFacets", "render, of a filter", "renderPage")
            if got.get(k) != {"refocused": 1, "active": True}]
    assert not lost, (
        "a redraw leaves focus on <body>: " + "; ".join(f"{k} -> {got.get(k)}" for k in lost))
    assert got["kept"], (
        "a redraw moved focus that it had not taken: the search box loses the "
        "keyboard while the list narrows under it")
    return "ok", ("a tab, a facet's checkbox, a card's header, a legend row, a select and a "
                  "filter's head are each keyed and refocused through render(), renderPage() "
                  "and renderFacets(); Show more is given no key, and focus a redraw "
                  "did not take is not moved")


# The harness of _chip_drawn, run in node beside page.js (app.js) and stub.js
# (dom_stub.js): six bills whose chips are the six words and a stage, listed
# by status, filtered, and as a member's or a committee's page lists them.
_CHIP_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({render, renderFacets, billPane, IDX, sel, setMeta:(m)=>{META=m;}, setTerm:(t)=>{term=t;}, setSort:(x)=>{sortBy=x;sortChosen=true;}, setPage:(p)=>{PAGE=p;}})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
s.setMeta({terms: ["2025-2026"], committee_codes: {}, topics: []});
const row = (id, kind, status, chip) => ({id, n: id, title: "a bill", kind, status, chip,
  committees: [], topic: "", sponsor: "", term: "2025-2026", year: 2026, passage: "",
  votedays: [], nrc: 0, last_action: ""});
s.IDX.length = 0;
s.IDX.push(row("HB1", "veto", "Vetoed, override failed", "Died"),
           row("HB2", "done", "Killed", "Died"),
           row("HB3", "active", "Laid on the table", "Tabled"),
           row("HB4", "active", "In committee", "In committee"),
           row("HB5", "done", "Withdrawn prior to introduction", "Withdrawn"),
           row("HB6", "law", "Signed into law", "Became Law"),
           row("HB7", "veto", "Vetoed, awaiting an override vote", "Vetoed"),
           row("HB8", "study", "Referred for interim study", "Interim Study"));
s.setTerm("2025-2026");
s.setSort("status");
const out = {};
try {
  s.render(); out.list = document.querySelector("#results").innerHTML;
  s.renderFacets(); out.facets = document.querySelector("#facets").innerHTML;
  s.sel.status.add("Died"); s.render(); out.died = document.querySelector("#results").innerHTML;
  s.sel.status.clear();
  s.setPage({kind: "committee", status: ""});
  out.pane = s.billPane(s.IDX.slice(), n => String(n));
  s.setPage({kind: "committee", status: "Died"});
  out.paneDied = s.billPane(s.IDX.slice(), n => String(n));
} catch (e) { out.threw = e.constructor.name + ": " + e.message; }
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("frontend", "a bill's card, the Status filter, the status grouping and a record page's "
                   "Bill status select never say how the bill ended: the card the chip's word, "
                   "the filter, the grouping and the select its category")
def _chip_drawn():
    """The chip is the six words of 5 October 2026 and a still-moving bill's
    stage (build_site_v2.chip_word); the status -- "Killed", "Vetoed,
    override failed" -- is the record's, and the card does not print it. This
    runs app.js in node: each card's chip is its word, coloured by the word,
    so a veto that stood is Died in Died's colour; the Status filter offers
    the categories of 8 October 2026 (the person: one In Progress, then
    Passed, Tabled, Interim Study and Died, and Withdrawn and Vetoed) -- it
    offered the six words first and then each stage until then; ticking Died
    lists the killed bill and the veto that stood; Sort by status heads the
    two with Died; and a member's or a committee's select, labelled "Bill
    status", offers the same categories in the same order and filters by
    them -- the person's "Same categories" of the same evening, where it
    offered the words as the filter did. Those two lines, the filter's and
    the select's, are the ones here the person changed;
    _bill_status_select_categories holds the rest of the select."""
    js, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and stub.exists() and node):
        return "skip", "app.js, dom_stub.js or node is not here"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(js)), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        (root / "go.js").write_text(_CHIP_HARNESS, encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js did not run under node: " + (r.stderr or r.stdout or "")[-300:])
        got = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert "threw" not in got, f"drawing the chips threw {got['threw']}"
    bad = []
    chips = re.findall(r'<span class="chip chip-m cstat ?([^"]*)">([^<]*)</span>', got["list"])
    # Tabled in the yellow of the rail's pause (8 October 2026: graphite at
    # first, then the person's yellow), and a stage still moving in slate blue
    # from the same evening, so the two are not one ink.
    want = {("s-done", "Died"), ("s-table", "Tabled"), ("s-active", "In Committee"),
            ("s-done", "Withdrawn"), ("s-law", "Became Law"), ("s-veto", "Vetoed"),
            ("s-study", "Interim Study")}
    if set(chips) != want or len(chips) != 8:
        bad.append(f"the cards' chips are {sorted(set(chips))} ({len(chips)}), not {sorted(want)}")
    for ending in ("Killed", "Vetoed, override failed", "Laid on the table",
                   "Withdrawn prior to introduction", "Signed into law",
                   "Referred for interim study", "Vetoed, awaiting an override vote"):
        if f">{ending}<" in got["list"] or f">{ending}\n" in got["list"]:
            bad.append(f"the list prints the ending {ending!r}")
    heads = re.findall(r'<h2 class="grp">([^<]*?)\s*<span>(\d+)</span>', got["list"])
    if ("Died", "2") not in [(h.strip(), c) for h, c in heads]:
        bad.append(f"Sort by status does not head the two that died 'Died 2': {heads}")
    offered = re.findall(r'data-f="status" value="([^"]*)"', got["facets"])
    if offered != ["In Progress", "Passed", "Tabled", "Interim Study", "Died", "Withdrawn",
                   "Vetoed"]:
        bad.append(f"the Status filter offers {offered}")
    if re.search(r'data-f="chip"', got["facets"]):
        bad.append("the Status filter still offers the chip's words")
    if re.search(r'data-f="kind"', got["facets"]):
        bad.append("the Status filter still filters on the kind")
    listed = re.findall(r'class="card[^"]*" data-id="([^"]*)"', got["died"])
    if sorted(listed) != ["HB1", "HB2"]:
        bad.append(f"ticking Died lists {listed}")
    # The search's categories since the person's "Same categories" of 8
    # October 2026; the six words first and then the stages until then.
    opts = re.findall(r'<option value="([^"]*)"', got["pane"])
    if opts != ["", "In Progress", "Passed", "Tabled", "Interim Study", "Died", "Withdrawn",
                "Vetoed"]:
        bad.append(f"a record page's Status select offers {opts}")
    shown = re.findall(r'class="card[^"]*" data-id="([^"]*)"', got["paneDied"])
    if sorted(shown) != ["HB1", "HB2"]:
        bad.append(f"a record page's Status select, on Died, shows {shown}")
    # "BILL STATUS", NOT "STATUS": on a legislator's page the select sits under
    # the member's own name and facts, and "Status: Died" there reads as the
    # member's.
    label = re.search(r'<label>([^<]*?)\s*<select data-pf="status"', got["pane"])
    if not label or label.group(1).strip() != "Bill status":
        bad.append(f"a record page's select is labelled {label and label.group(1).strip()!r}, "
                   "not 'Bill status'")
    assert not bad, "; ".join(bad)
    return "ok", ("each card says its word in its word's colour, the filter and a record "
                  "page's select offer the seven categories, and Died lists the killed bill and "
                  "the veto that stood")


@check("data", "every bill of every term the built site lists is filed under one of the "
               "Status filter's categories by its chip's word or its kind")
def _status_categories_built():
    """_status_categories over the built site's own rows rather than the
    pairs written down on 8 October 2026 (_STATUS_REAL_PAIRS): every
    (chip, kind) that site/idx carries, for every term meta.json names and
    the requests, through app.js's statusCat. Each is to be decided by its
    word or its kind, never by the last line, and filed where
    _STATUS_CATEGORY says; a word this file does not know -- a stage the
    General Court names tomorrow -- fails here, so that the person decides
    which category it is in before a reader finds it in the wrong one. A
    request has no chip and is in none. On 8 October: 33,717 bills, 13
    pairs, none reaching the last line."""
    rows = _site_bills()
    if rows is None:
        return "skip", "site is not built"
    from collections import Counter
    pairs = Counter((r.get("chip"), r.get("kind") or "") for r in rows if r.get("chip"))
    bills = sum(pairs.values())
    unknown = sorted({c for c, _k in pairs if c not in _STATUS_CATEGORY})
    got = _node_app(_STATUSCAT_HARNESS, {"pairs.json": json.dumps(sorted(pairs)),
                                         "words.json": "[]"})
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    assert "threw" not in got, f"statusCat threw {got['threw']}"
    bad = [f"{len(unknown)} chip word(s) no category is written down for here: {unknown[:4]}"
           ] if unknown else []
    for chip, kind, cat, by_word, by_kind in got["pairs"]:
        n = pairs[(chip, kind)]
        if not (by_word or by_kind):
            bad.append(f"{n:,} bill(s) with the chip {chip!r} ({kind or 'no kind'}) are filed "
                       f"by statusCat's last line, as {cat!r}")
        elif chip in _STATUS_CATEGORY and cat != _STATUS_CATEGORY[chip]:
            bad.append(f"{n:,} bill(s) with the chip {chip!r} are filed under {cat!r}, not "
                       f"{_STATUS_CATEGORY[chip]!r}")
    assert not bad, "; ".join(bad[:6])
    return "ok", (f"{bills:,} bills of the built site, {len(pairs)} pairs of chip and kind, "
                  "each filed by its word or its kind")


# The bill search as bills.html runs it, in node: meta.json and three terms'
# rows answered from the fixture, the address from argv[2], and then the
# reader's steps -- a status ticked, a type ticked, Sort by status, another
# term, All Terms, the requests, a number -- each read off the count line, the
# filters and the list.
_SEARCH_GROUPS_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
const FIX = JSON.parse(fs.readFileSync("./fixture.json", "utf8"));
globalThis.fetch = async (u) => { const p = decodeURIComponent(new URL(u).pathname);
  if (!(p in FIX)) return { ok: false, status: 404, statusText: "Not Found",
                            json: async () => { throw new Error("404"); } };
  return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(FIX[p])) }; };
const ticks = async (n) => { for (let i = 0; i < n; i++) await new Promise(r => setImmediate(r)); };
location.search = process.argv[2] || "";
const box = document.querySelector("#q"); box.disabled = true;
// Each write to the count, which is a live region: a sentence written over
// the same sentence can be read out again.
const countEl = document.querySelector("#count");
let countText = "", countWrites = 0;
Object.defineProperty(countEl, "textContent", {get() { return countText; },
  set(v) { countText = String(v); countWrites++; }});
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({render, sel, getTerm: () => term, setQuery: (q) => { query = q; },"
  + " more: () => { SHOWN += PAGE_SIZE; render(true); }})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const $ = (q) => document.querySelector(q);
const look = () => {
  const f = $("#facets").innerHTML, r = $("#results").innerHTML;
  const opts = (key) => [...f.matchAll(new RegExp('<input type="checkbox" data-f="' + key
    + '" value="([^"]*)"[^>]*>\\s*<span>([\\s\\S]*?)</span>\\s*<span class="c">([\\d,]+)</span>', "g"))]
    .map(m => [m[1], m[2].replace(/\s+/g, " ").trim(), +m[3].replace(/,/g, "")]);
  return {count: $("#count").textContent, status: opts("status"), type: opts("type"),
    whole: [...f.matchAll(/<button class="fhead" data-g="([^"]+)"[\s\S]*?<div class="fbody( whole)?"/g)]
      .filter(m => m[2]).map(m => m[1]),
    ticked: [...f.matchAll(/data-f="([^"]+)" value="([^"]*)" checked/g)].map(m => m[1] + "=" + m[2]),
    groups: [...f.matchAll(/data-g="([^"]+)"/g)].map(m => m[1]),
    labels: [...f.matchAll(/data-g="([^"]+)"\s*aria-expanded="[^"]*"><span>([^<]*)<\/span>/g)]
      .map(m => [m[1], m[2]]),
    heads: [...r.matchAll(/<h2 class="grp">([^<]*?)\s*<span>([\d,]+)<\/span>/g)]
      .map(m => [m[1].trim(), +m[2].replace(/,/g, "")]),
    cards: [...r.matchAll(/<article class="card[^"]*" data-id="([^"]+)"/g)].map(m => m[1])};
};
(async () => {
  for (let i = 0; i < 400 && box.disabled !== false; i++) await ticks(1);
  if (box.disabled !== false) { console.log("app.js never finished loading the fixture"); process.exit(1); }
  const out = {year: $("#year").innerHTML, arrived: {status: [...s.sel.status], type: [...s.sel.type]}};
  try {
    out.start = look();
    const clear = () => { Object.values(s.sel).forEach(x => x.clear()); };
    clear(); s.render(); out.none = look();
    let w = countWrites; s.render(); s.render(); s.render(); out.rewritesWhole = countWrites - w;
    s.sel.status.add("In Progress"); s.render(); out.progress = look();
    w = countWrites; s.render(); s.render(); out.rewritesNarrowed = countWrites - w;
    clear(); s.sel.type.add("CACR"); s.render(); out.cacr = look();
    s.sel.status.add("Died"); s.render(); out.cacrDied = look();
    clear();
    const so = $("#sort"); so.value = "status"; so.fire("change"); out.byStatus = look();
    // The list drawn to its end a page at a time, and then narrowed by a
    // status and by a type: each heading's number is the whole result's,
    // every time.
    for (let i = 0; i < 10; i++) s.more();
    out.byStatusMore = look();
    s.sel.status.add("Passed"); s.render(); out.byStatusPassed = look();
    s.sel.status.clear(); s.sel.type.add("HB"); s.render(); out.byStatusHB = look();
    clear();
    so.value = "num"; so.fire("change");
    const ys = $("#year");
    const term = async (t) => { ys.value = t; ys.fire("change"); await ticks(40); return look(); };
    out.older = await term("2023-2024");
    // A category ticked where no bill of the term is in it: still on offer.
    s.sel.status.add("Tabled"); s.render(); out.olderTicked = look(); s.sel.status.clear();
    s.render();
    out.all = await term("all");
    out.requests = await term("2027-requests");
    // A status ticked in a term with statuses, carried into the requests.
    s.sel.status.add("Passed"); s.render(); out.requestsTicked = look(); s.sel.status.clear();
    s.render();
    // All Terms with the requests already fetched: the terms' bills alone.
    out.allAfterRequests = await term("all");
    await term("2025-2026");
    box.value = "HB 2"; box.fire("input"); await ticks(20); out.number = look();
  } catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + (e.stack || "").split("\n")[1]; }
  process.stdout.write("\n@@" + JSON.stringify(out));
})().catch(e => { console.log("RUN " + e.message); process.exit(1); });
"""


def _search_groups_fixture(passed=0):
    """meta.json, two terms and the requests, for _SEARCH_GROUPS_HARNESS:
    every chip the current term can carry while its session sits, and an
    earlier term with no bill still moving, tabled, withdrawn or vetoed, nor
    sent to interim study. `passed` more laws in the current term, HB 100 on,
    make its list longer than the hundred cards drawn at first. One bill was
    voted on the floor and changes RSA 91-A:4: the statute filter, Laws
    Changed (RSA) since 26 October 2026, is drawn in the Floor Vote Day
    filter's place (the person, 11 October 2026)."""
    def row(bid, kind, chip, term="2025-2026", status=None):
        return {"id": bid, "n": re.sub(r"^([A-Z]+)", r"\1 ", bid), "title": "a bill",
                "kind": kind, "status": status or chip, "chip": chip, "committees": [],
                "committee": "", "topic": "", "sponsor": "", "term": term,
                "year": int(term[-4:]), "passage": "", "votedays": [], "nrc": 0,
                "last_action": ""}
    now = [dict(row("HB1", "law", "Became Law", status="Signed into law"),
                votedays=["2026-03-05"], rsa=["91-A", "91-A:4"]),
           row("HB2", "done", "Died", status="Killed"),
           row("HB3", "active", "Tabled", status="Laid on the table"),
           row("HB4", "active", "In committee"),
           row("HB5", "active", "Re-referred to committee"),
           row("SB6", "active", "Passed, awaiting the governor"),
           row("CACR7", "adopted", "Passed both chambers, goes to the voters in November 2026"),
           row("CACR8", "adopted", "Passed both chambers, not ratified by the voters"),
           row("HR9", "adopted", "Adopted by the House"),
           row("SR10", "adopted", "Adopted by the Senate"),
           row("HCR11", "adopted", "Adopted by both chambers"),
           row("SCR12", "done", "Died", status="Killed"),
           row("SB13", "study", "Interim Study", status="Referred for interim study"),
           row("HB14", "veto", "Vetoed", status="Vetoed, awaiting an override vote"),
           row("HB15", "done", "Withdrawn"),
           row("HJR16", "law", "Became Law", status="Signed into law"),
           row("PET17", "done", "Died", status="Killed"),
           row("SSHB18", "law", "Became Law", status="Signed into law"),
           row("HCO19", "done", "Died", status="Refused introduction"),
           row("ZZ20", "done", "Died", status="Killed")] \
        + [row(f"HB{100 + i}", "law", "Became Law", status="Signed into law")
           for i in range(passed)]
    old = [row("HB1", "law", "Became Law", "2023-2024", "Signed into law"),
           row("HB2", "done", "Died", "2023-2024", "Killed"),
           row("SB3", "veto", "Died", "2023-2024", "Vetoed, override failed")]
    req = [{"id": f"LSR2027000{i}", "n": f"LSR 2027-000{i}", "year": 2027, "title": "a request",
            "sponsor": "", "body": body, "committee": "", "committees": [], "topic": "",
            "kind": "", "status": status, "term": "2027-requests", "lsr": True,
            "last_action": "", "nrc": 0, "votedays": []}
           for i, body, status in ((1, "HB", "Requested"), (2, "SB", "Requested"),
                                   (3, "HB", "Filed"))]
    meta = {"terms": ["2025-2026", "2023-2024"], "topics": [], "committee_codes": {},
            "requests": {"term": "2027-requests", "label": "2027 Bill Requests"}}
    return {"/meta.json": meta, "/idx/2025-2026.json": now, "/idx/2023-2024.json": old,
            "/idx/2027-requests.json": req}


@check("frontend", "the bill search's Status filter offers the categories a bill of the term "
                   "is in, in the person's order and their chips' colours, a Bill Type filter "
                   "offers each kind of measure by its letters and name, and Sort by status "
                   "heads the list with the categories")
def _status_and_type_filters():
    """The person, 8 October 2026: one In Progress to tick for the bills that
    have not concluded, separate from Passed, Tabled, Interim Study and Died;
    Withdrawn and Vetoed their own; and "a way to sort by bill type like
    sorting between HB, SB, HR, SR, HCR, SCR, CACR". And their answer the
    same evening, "Hide at zero": a category no bill of the term is in is
    not offered, the order stays fixed, and a box someone has ticked stays
    so it can be unticked. Until then In Progress, Passed, Tabled, Interim
    Study and Died were offered in every term, an ended one's In Progress
    and Tabled at none, and this check held that; that is the line here the
    person changed. Run in node over a fixture term carrying every chip a
    sitting session can, an earlier term with no bill moving, tabled,
    withdrawn, vetoed or at interim study, and the requests. Held: the Status
    filter's options, their order and each one's chip class, and their
    counts adding up to the term's; ticking In Progress lists the stages,
    the bill awaiting the governor (In Progress, the person confirmed that
    evening) and the amendment going to the voters, and nothing else; the
    Bill Type filter's options in the person's order with their names, a
    code with none shown as its letters, ticking CACR listing the two
    amendments, and the two filters together; Sort by status heading the
    list with the categories in order and their counts; the earlier term
    offering Passed and Died alone, and Tabled, ticked there, at none in its
    place between them; the requests offering no status and their types by
    what each asks for -- and, where a status ticked in another term is
    carried into them, the Status filter with that tick on it alone, at
    none, so the empty list can be undone where it was done (the review of
    8 October 2026); the Status and Bill Type filters shown whole, never in
    a box that scrolls (the review: a phone's 210px showed six of the
    current term's seven kinds), and Laws Changed with them since 26 October
    2026, whose offers, six at most, would be cut off there just the same;
    every filter headed in Title Case, Floor
    Vote Day among them (decided 8 October); and ?status= and ?type= in the
    address ticking the filters, a chip's own word read as its category."""
    fx = _search_groups_fixture()
    got = _node_app(_SEARCH_GROUPS_HARNESS, {"fixture.json": json.dumps(fx)},
                    args=("?status=Became%20Law&status=in%20committee&status=constructor"
                          "&type=cacr&type=zz9",))
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    assert "threw" not in got, f"the bill search threw {got['threw']}"
    bad = []
    if sorted(got["arrived"]["status"]) != ["In Progress", "Passed"] \
            or got["arrived"]["type"] != ["CACR"]:
        bad.append(f"?status=Became Law&status=in committee&status=constructor&type=cacr"
                   f"&type=zz9 ticks {got['arrived']}, not Passed and In Progress, and CACR")
    n = got["none"]
    total = len(fx["/idx/2025-2026.json"])
    want_status = [("In Progress", 4), ("Passed", 6), ("Tabled", 1), ("Interim Study", 1),
                   ("Died", 6), ("Withdrawn", 1), ("Vetoed", 1)]
    if [(v, c) for v, _lab, c in n["status"]] != want_status:
        bad.append(f"the Status filter offers {[(v, c) for v, _l, c in n['status']]}, "
                   f"not {want_status}")
    classes = {v: re.search(r'class="chip ([^"]*)"', lab) for v, lab, _c in n["status"]}
    want_cls = {"In Progress": "s-active", "Passed": "s-law", "Tabled": "s-table",
                "Interim Study": "s-study", "Died": "s-done", "Withdrawn": "s-done",
                "Vetoed": "s-veto"}
    for v, cls in want_cls.items():
        m = classes.get(v)
        if not m or m.group(1) != cls:
            bad.append(f"{v} is painted {m and m.group(1)!r}, not {cls!r}")
    if sum(c for _v, _l, c in n["status"]) != total:
        bad.append(f"the Status filter's counts add to {sum(c for _v, _l, c in n['status'])}, "
                   f"not the term's {total}")
    want_type = [("HB", "House Bill", 7), ("SB", "Senate Bill", 2), ("HR", "House Resolution", 1),
                 ("SR", "Senate Resolution", 1), ("HCR", "House Concurrent Resolution", 1),
                 ("SCR", "Senate Concurrent Resolution", 1),
                 ("CACR", "Constitutional Amendment Concurrent Resolution", 2),
                 ("HJR", "House Joint Resolution", 1), ("HCO", "House Concurrent Order", 1),
                 ("PET", "Petition", 1), ("SSHB", "Special Session House Bill", 1),
                 ("ZZ", "", 1)]
    seen = [(v, re.sub(r"<[^>]+>", " ", lab).replace(v, "", 1).strip(), c)
            for v, lab, c in n["type"]]
    if seen != want_type:
        bad.append(f"the Bill Type filter offers {seen}, not {want_type}")
    if any('class="tcode"' not in lab for _v, lab, _c in n["type"]):
        bad.append("a Bill Type option does not set its letters apart (tcode)")
    groups = n["groups"]
    if "type" not in groups or groups.index("type") != groups.index("status") + 1:
        bad.append(f"the filters run {groups}: Bill Type is not beside Status")
    labels = dict(n["labels"])
    if labels.get("status") != "Status" or labels.get("type") != "Bill Type":
        bad.append(f"the two filters are headed {labels.get('status')!r} and "
                   f"{labels.get('type')!r}, not 'Status' and 'Bill Type'")
    # THE STATUTE FILTER REPLACES THE FLOOR VOTE DAY FILTER (the person, 11
    # October 2026: "Eventually we will replace the session day filter on
    # bill search for the RSA search"). Headed Laws Changed (RSA) since the
    # person's note of 26 October 2026 ("it should still be easily
    # understandable"; _laws_changed_offers holds the rest of it).
    if "voteday" in labels:
        bad.append("the Floor Vote Day filter is still drawn; the Laws Changed (RSA) filter "
                   "replaces it")
    if labels.get("rsa") != "Laws Changed (RSA)":
        bad.append(f"the statute filter is headed {labels.get('rsa')!r}, not 'Laws Changed (RSA)'")
    lower = [lab for _g, lab in n["labels"] if any(w[:1].islower() for w in lab.split())]
    if lower:
        bad.append(f"a filter's heading is not in Title Case: {lower}")
    if sorted(got["progress"]["cards"]) != ["CACR7", "HB4", "HB5", "SB6"]:
        bad.append(f"In Progress lists {got['progress']['cards']}, not the two stages, the "
                   "bill awaiting the governor and the amendment going to the voters")
    if sorted(got["cacr"]["cards"]) != ["CACR7", "CACR8"]:
        bad.append(f"CACR lists {got['cacr']['cards']}")
    if got["cacrDied"]["cards"] != ["CACR8"]:
        bad.append(f"CACR and Died together list {got['cacrDied']['cards']}, not the amendment "
                   "the voters turned down")
    heads = [tuple(h) for h in got["byStatus"]["heads"]]
    if heads != want_status:
        bad.append(f"Sort by status heads the list {heads}, not {want_status}")
    older = [(v, c) for v, _l, c in got["older"]["status"]]
    if older != [("Passed", 1), ("Died", 2)]:
        bad.append(f"a term whose bills passed or died offers {older}, not Passed 1 and Died 2: "
                   "a category no bill is in is not offered (the person: \"Hide at zero\")")
    ot = got["olderTicked"]
    if [(v, c) for v, _l, c in ot["status"]] != [("Passed", 1), ("Tabled", 0), ("Died", 2)] \
            or "status=Tabled" not in ot["ticked"]:
        bad.append(f"Tabled ticked in a term with no bill tabled offers "
                   f"{[(v, c) for v, _l, c in ot['status']]}, ticked {ot['ticked']}: not "
                   "Tabled at none in its place, to be unticked")
    allv = [v for v, _l, _c in got["all"]["status"]]
    if allv != _STATUS_CATS:
        bad.append(f"All Terms offers {allv}")
    # THE REQUESTS' STATUS FILTER (the owner, 13 November 2026): Requested and
    # Filed, each in its chip's class and counted; and no Committee filter,
    # which no request has a committee to fill.
    rq = got["requests"]
    if [(v, c) for v, _l, c in rq["status"]] != [("Requested", 2), ("Filed", 1)]:
        bad.append(f"the requests' Status filter offers {[(v, c) for v, _l, c in rq['status']]}, "
                   "not Requested 2 and Filed 1")
    rcls = {v: (re.search(r'class="chip ([^"]*)"', lab) or [None, None])[1] for v, lab, _c in rq["status"]}
    if rcls != {"Requested": "s-active", "Filed": "s-law"}:
        bad.append(f"the requests' statuses are painted {rcls}")
    if "committee" in rq["groups"]:
        bad.append("the requests are offered a Committee filter, though no request has a committee")
    if "committee" not in n["groups"]:
        bad.append("a term of bills is no longer offered a Committee filter")
    rt = got["requestsTicked"]
    if "status=Passed" not in rt["ticked"] or [(v, c) for v, _l, c in rt["status"]] \
            != [("Requested", 2), ("Filed", 1), ("Passed", 0)]:
        bad.append(f"Passed ticked and carried into the requests is not on offer to untick, "
                   f"alone: the filters are {rt['groups']}, offering {rt['status']}, ticked "
                   f"{rt['ticked']}")
    if sorted(n["whole"]) != ["rsa", "status", "type"]:
        bad.append(f"the filters shown whole are {n['whole']}, not Status, Bill Type and Laws "
                   "Changed")
    if [(v, c) for v, _l, c in got["requests"]["type"]] != [("HB", 2), ("SB", 1)]:
        bad.append(f"the requests' Bill Type filter offers {got['requests']['type']}")
    assert not bad, "; ".join(bad)
    return "ok", ("the Status filter offers the seven in order, painted, adding to the term; "
                  "Bill Type offers twelve kinds by letters and name; the two filter alone and "
                  "together; Sort by status heads with the categories; an earlier term offers "
                  "only the two its bills are in, and a ticked one at none; All Terms, the "
                  "requests and an address each get what is theirs")


# A card opened far down the list, pressed as a reader presses its title: the
# page's own click listeners are kept (the stub drops document's), and a
# title is a target whose closest(".card .ctitle") is the card's head.
_CARD_KEEPS_PLACE_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
const FIX = JSON.parse(fs.readFileSync("./fixture.json", "utf8"));
globalThis.fetch = async (u) => { const p = decodeURIComponent(new URL(u).pathname);
  if (!(p in FIX)) return { ok: false, status: 404, statusText: "Not Found", text: async () => "",
                            json: async () => { throw new Error("404"); } };
  return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(FIX[p])) }; };
const ticks = async (n) => { for (let i = 0; i < n; i++) await new Promise(r => setImmediate(r)); };
const L = {};
document.addEventListener = (t, f) => { (L[t] = L[t] || []).push(f); };
location.search = process.argv[2] || "";
const box = document.querySelector("#q"); box.disabled = true;
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({render, sel, getShown: () => SHOWN, setQuery: (q) => { query = q; },"
  + " isOpen: (id) => openCards.has(id), more: () => { SHOWN += PAGE_SIZE; render(true); }})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const $ = (q) => document.querySelector(q);
const cards = () => [...$("#results").innerHTML.matchAll(/<article class="card[^"]*" data-id="([^"]+)"/g)]
  .map(m => m[1]);
const press = (id) => {
  const card = {dataset: {id}, querySelector: () => null, closest: () => null};
  const head = {closest: (q) => q === ".card" ? card : null};
  const target = {closest: (q) => q === ".card .ctitle" ? head : null, dataset: {}, tagName: "SPAN"};
  for (const f of (L.click || [])) {
    try { f({target, button: 0, preventDefault() {}, stopPropagation() {}}); } catch (_) {}
  }
};
const look = () => ({n: cards().length, shown: s.getShown()});
(async () => {
  for (let i = 0; i < 400 && box.disabled !== false; i++) await ticks(1);
  if (box.disabled !== false) { console.log("app.js never finished loading the fixture"); process.exit(1); }
  const out = {};
  const ys = $("#year");
  const term = async (t) => { ys.value = t; ys.fire("change"); await ticks(40); };
  try {
    for (const [name, t] of [["bills", "2025-2026"], ["requests", "2027-requests"]]) {
      await term(t);
      Object.values(s.sel).forEach(x => x.clear()); s.setQuery(""); s.render();
      const o = {first: look()};
      s.more(); s.more();
      o.drawn = look();
      const ids = cards(), id = ids[39];
      o.id = id;
      press(id); await ticks(20);
      o.opened = Object.assign(look(), {open: s.isOpen(id), there: cards().includes(id)});
      press(id); await ticks(20);
      o.closed = Object.assign(look(), {open: s.isOpen(id), there: cards().includes(id)});
      s.render(); o.redrawn = look();
      s.setQuery(t === "2027-requests" ? "2027-0001" : "HB 1"); s.render(); o.searched = look();
      s.setQuery(""); s.render(); o.cleared = look();
      out[name] = o;
    }
  } catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + (e.stack || "").split("\n")[1]; }
  process.stdout.write("\n@@" + JSON.stringify(out));
})().catch(e => { console.log("RUN " + e.message); process.exit(1); });
"""


@check("frontend", "a card opened or closed far down the bill search keeps the list where it was: "
                   "the cards drawn stay drawn and the page does not jump back to the first "
                   "twenty-five; a new search still starts at them")
def _card_open_keeps_the_list():
    """The owner, 16 November 2026, on the live site: opening a request card
    flashed the footer, and opening one further down "will jump back to
    LSR-0025". Every redraw went through render() with no argument, which set
    the list back to its first page (PAGE_SIZE, 25 since 25 October), so the
    card opened at the fortieth place left the list, the page shrank under the
    reader for a frame (the footer), and the scroll was clamped to the last
    card of the first page. render() now takes the first page again only for
    a list that is not the one it last drew. Run in node over the search
    fixture made long (sixty more laws and sixty requests): seventy-five cards
    drawn, the fortieth pressed open and pressed shut, for the term's bills
    and for the requests -- the seventy-five stay, the card stays among them
    and opens and shuts; a plain redraw keeps them too; a search starts at
    twenty-five, and so does clearing it."""
    fx = _search_groups_fixture(passed=60)
    req = fx["/idx/2027-requests.json"]
    base = dict(req[0])
    fx["/idx/2027-requests.json"] = [dict(base, id=f"LSR2027{i:04d}", n=f"LSR 2027-{i:04d}",
                                          body="HB" if i % 2 else "SB")
                                     for i in range(1, 61)]
    got = _node_app(_CARD_KEEPS_PLACE_HARNESS, {"fixture.json": json.dumps(fx)})
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    assert "threw" not in got, f"the harness threw: {got['threw']}"
    bad = []
    for name in ("bills", "requests"):
        o = got[name]
        if o["first"]["n"] != 25 or o["drawn"]["n"] < 41:
            bad.append(f"{name}: {o['first']['n']} cards at first and {o['drawn']['n']} after two "
                       "pages more (the fixture is too short to open a card at the fortieth place)")
            continue
        n = o["drawn"]["n"]
        if not (o["opened"]["open"] and o["opened"]["there"] and o["opened"]["n"] == n):
            bad.append(f"{name}: opening {o['id']} at the fortieth place left {o['opened']['n']} of "
                       f"{n} cards (open: {o['opened']['open']}, still listed: {o['opened']['there']})")
        if o["closed"]["open"] or not o["closed"]["there"] or o["closed"]["n"] != n:
            bad.append(f"{name}: closing {o['id']} left {o['closed']['n']} of {n} cards "
                       f"(open: {o['closed']['open']}, still listed: {o['closed']['there']})")
        if o["redrawn"]["n"] != n:
            bad.append(f"{name}: a plain redraw left {o['redrawn']['n']} of {n} cards")
        if o["searched"]["shown"] != 25 or o["cleared"]["shown"] != 25:
            bad.append(f"{name}: a new search did not start again at the first page "
                       f"(shown {o['searched']['shown']}, then {o['cleared']['shown']} cleared)")
    assert not bad, "; ".join(bad)
    return "ok", (f"{got['bills']['drawn']['n']} bills and {got['requests']['drawn']['n']} requests "
                  "drawn; the fortieth of each opened and closed by its title with every card still "
                  "drawn, a plain redraw keeping them, and a search and its clearing starting again at 25")


@check("frontend", "sorted by Status, each heading's number is how many of the whole list are "
                   "in that category, the number the Status filter beside it gives, however "
                   "few of the cards are drawn yet")
def _status_heads_full_totals():
    """The person, 8 October 2026, "Full totals": when sorting by Status,
    each heading's number is the count of that category in the whole result,
    not of the cards loaded so far -- "Passed 686", matching the sidebar. It
    was counted over the cards on screen, so the first hundred of the
    2025-2026 term (one In Progress, then Passed) headed its 686 "Passed 99".
    Run in node over _search_groups_fixture with 130 more laws, 150 bills in
    the term: the first page drawn (PAGE_SIZE cards, 25 since the phone audit
    of 25 October 2026) is headed In Progress 4 and Passed 136, the list
    drawn to its end every category with the same numbers, and each is the
    Status filter's own count for it; and narrowed, by Passed ticked and by
    HB, each heading is still the sidebar's number. A heading of a thousand
    or more carries its separator, as the filter's count does."""
    fx = _search_groups_fixture(passed=130)
    got = _node_app(_SEARCH_GROUPS_HARNESS, {"fixture.json": json.dumps(fx)})
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    assert "threw" not in got, f"the bill search threw {got['threw']}"
    bad = []
    side = {v: c for v, _l, c in got["byStatus"]["status"]}
    first = [tuple(h) for h in got["byStatus"]["heads"]]
    js = _source("src/pages/app.js")
    page = re.search(r"^const PAGE_SIZE = (\d+);", js, re.M)
    n = int(page.group(1)) if page else 0
    assert 4 < n < 150, f"the list's page is {n} cards; this fixture needs between 5 and 149"
    if first != [("In Progress", 4), ("Passed", 136)] or len(got["byStatus"]["cards"]) != n:
        bad.append(f"the first {n} of 150 are headed {first} over "
                   f"{len(got['byStatus']['cards'])} cards, not In Progress 4 and Passed 136 "
                   f"over {n}: a heading counts the cards drawn, not the list")
    if len(got["byStatusMore"]["cards"]) != 150:
        bad.append(f"Show more ten times drew {len(got['byStatusMore']['cards'])} of 150 cards")
    more = [tuple(h) for h in got["byStatusMore"]["heads"]]
    want = [("In Progress", 4), ("Passed", 136), ("Tabled", 1), ("Interim Study", 1),
            ("Died", 6), ("Withdrawn", 1), ("Vetoed", 1)]
    if more != want:
        bad.append(f"drawn to its end the list is headed {more}, not {want}")
    differ = [(h, c, side.get(h)) for h, c in more if side.get(h) != c]
    if differ:
        bad.append(f"a heading and the Status filter disagree (heading, its number, the "
                   f"filter's): {differ}")
    for k, what in (("byStatusPassed", "Passed ticked"), ("byStatusHB", "HB ticked")):
        side_k = {v: c for v, _l, c in got[k]["status"]}
        heads = [tuple(h) for h in got[k]["heads"]]
        wrong = [(h, c, side_k.get(h)) for h, c in heads if side_k.get(h) != c]
        if not heads or wrong:
            bad.append(f"with {what} the headings {heads} are not the filter's numbers: {wrong}")
    if [tuple(h) for h in got["byStatusPassed"]["heads"]] != [("Passed", 136)]:
        bad.append(f"Passed ticked is headed {got['byStatusPassed']['heads']}, not Passed 136")
    if not re.search(r"<span>\$\{\(grpN\[grpOf\(b\)\]\|\|0\)\.toLocaleString\(\)\}</span>", js):
        bad.append("a heading's number is not written with toLocaleString: \"Passed 12873\" "
                   "beside the filter's \"12,873\" on All Terms")
    assert not bad, "; ".join(bad)
    return "ok", (f"the first {n} of 150 are headed In Progress 4 and Passed 136, the whole "
                  "list each category by the filter's own number, narrowed or not")


# THE LAWS CHANGED FILTER (app.js rsaGroup; the person, 26 October 2026), in
# node: the bill search as bills.html runs it over _rsa_fixture, the address
# from argv[2], and the reader's steps -- the group opened by its head, the box
# typed in, the arrow keys, Return, Escape, Tab, leaving the box, an offer
# pressed, Clear and Clear all filters, the term picker -- each read off the
# group, its list, the line under the box, the status line, the box's own
# attributes, value, caret and focus, the cards, the address and every file
# asked for. The clicks go through app.js's own document listeners, and the
# typing through #facets', where the box is heard. The box is one element, as
# the stub has one per id; each time the panel is drawn it is drawn anew as a
# browser draws it (the review of 26 October 2026, which found a caret and a
# press that failed silently in Chromium and passed here): its value, list,
# note and attributes from the markup, the status line empty, the caret at the
# start, and the focus gone from anything in the panel until app.js puts it
# back -- refocus finds the box by its id. Where the panel draws no box, there
# is none to find. argv[3] picks the run: "" the reader's steps; "slow"
# laws/chapters.json held until words are typed, the names arriving under them
# mid-word; "slowshut" the same with the panel shut before they arrive;
# "failonce" laws/chapters.json failing once and the group opened again;
# "terms" the term picker, the address naming the requests.
_RSA_GROUP_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
const FIX = JSON.parse(fs.readFileSync("./fixture.json", "utf8"));
const ASKED = [];
const MODE = process.argv[3] || "";
let release = () => {}, releaseIdx = () => {};
const held = new Promise(r => { release = r; }), heldIdx = new Promise(r => { releaseIdx = r; });
let failNext = MODE === "failonce" ? 1 : 0, failHeads = failNext;
globalThis.fetch = async (u) => { const p = decodeURIComponent(new URL(u).pathname); ASKED.push(p);
  // A file asked for again and again, as a failure asked for anew on every
  // drawing would be: said, rather than left to run into node's timeout.
  const n = ASKED.filter(x => x === p).length;
  if (n > 25) { process.stdout.write("\n@@" + JSON.stringify({runaway: p + " was asked for " + n + " times"}));
    process.exit(0); }
  if (MODE.startsWith("slow") && p === "/laws/chapters.json") await held;
  if (MODE === "terms" && p === "/idx/2025-2026.json") await heldIdx;
  if (p === "/laws/headings.json" && failHeads > 0) { failHeads--;
    return { ok: false, status: 503, statusText: "Unavailable", json: async () => { throw new Error("503"); } }; }
  if (p === "/laws/chapters.json" && failNext > 0) { failNext--;
    return { ok: false, status: 503, statusText: "Unavailable", json: async () => { throw new Error("503"); } }; }
  if (!(p in FIX)) return { ok: false, status: 404, statusText: "Not Found",
                            json: async () => { throw new Error("404"); } };
  return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(FIX[p])) }; };
const ticks = async (n) => { for (let i = 0; i < n; i++) await new Promise(r => setImmediate(r)); };
// Timers: each run in a task of its own after the one that set it, as a
// browser runs them -- not at once, as the stub runs them -- or, HOLD, a
// pause in typing kept waiting, so that what Return or leaving the box does
// before it ends can be seen.
let HOLD = false, TID = 1;
const PENDING = new Map(), SOON = new Map();
globalThis.setTimeout = (f, ms) => { const id = TID++;
  if (HOLD && ms > 0) PENDING.set(id, f);
  else { SOON.set(id, f); setImmediate(() => { if (SOON.delete(id)) try { f(); } catch (e) {} }); }
  return id; };
globalThis.clearTimeout = (id) => { PENDING.delete(id); SOON.delete(id); };
globalThis.CSS = globalThis.CSS || {escape: (x) => String(x)};
location.search = process.argv[2] || "";
history.replaceState = (st, t, u) => { const i = u.indexOf("?");
  location.search = i < 0 ? "" : u.slice(i).replace(/#.*$/, ""); };
// The document's listeners, as a browser keeps them: one of each, and one
// added {once: true} gone once it is heard.
const DOCON = {};
document.addEventListener = (t, f, o) => { const l = DOCON[t] = DOCON[t] || [];
  if (!l.some(x => x.f === f)) l.push({f, once: !!(o && o.once)}); };
const fire = (t, ev) => { for (const x of [...(DOCON[t] || [])]) {
  if (x.once) DOCON[t].splice(DOCON[t].indexOf(x), 1); try { x.f(ev); } catch (e) {} } };
const q = document.querySelector("#q"); q.disabled = true;
// #facets, an element of the stub's whose innerHTML can be watched.
const fx = Object.create(document.createElement("div"));
const qs0 = document.querySelector.bind(document);
document.querySelector = (x) => (x === "#facets" ? fx : qs0(x));
const rb = document.getElementById("rsabox"), ro = document.getElementById("rsaoffers");
const rn = document.getElementById("rsanote"), rs = document.getElementById("rsasay");
const ATTR = {};
rb.id = "rsabox"; rb.tagName = "INPUT"; rb.inFacets = true;
rb.setAttribute = (k, v) => { ATTR[k] = String(v); };
rb.removeAttribute = (k) => { delete ATTR[k]; };
rb.getAttribute = (k) => (k in ATTR ? ATTR[k] : null);
rb.selectionStart = rb.selectionEnd = 0;
rb.setSelectionRange = (a, b) => { rb.selectionStart = a; rb.selectionEnd = b; };
let ACTIVE = document.body;
Object.defineProperty(document, "activeElement", {get: () => ACTIVE, configurable: true});
rb.focus = () => { ACTIVE = rb; };
rb.closest = (x) => (x === "#results,#facets" ? fx : null);
let BOXED = false, DRAWS = 0;
const byId = document.getElementById.bind(document), qsa = document.querySelectorAll.bind(document);
document.getElementById = (id) => (!BOXED && ["rsabox", "rsaoffers", "rsanote", "rsasay"].includes(id) ? null : byId(id));
// The groups' heads as drawn, each to be focused.
const HEADS = () => [...FXH.matchAll(/<button class="fhead" data-g="([^"]+)"/g)]
  .map(m => ({g: m[1], tagName: "BUTTON", inFacets: true, focus() { ACTIVE = this; }}));
document.querySelectorAll = (x) => (x === "#rsabox" ? (BOXED ? [rb] : []) : x === "#facets .fhead" ? HEADS() : qsa(x));
const unesc = (h) => h.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, "<")
  .replace(/&gt;/g, ">").replace(/&amp;/g, "&");
let FXH = "";
Object.defineProperty(fx, "innerHTML", {get: () => FXH, set(v) { FXH = String(v); DRAWS++;
  const box = /<input class="sbox" id="rsabox"[^>]*>/.exec(v);
  BOXED = !!box;
  // The box drawn anew with the focus in it says it is left, as Chromium's does.
  const had = ACTIVE === rb;
  if (ACTIVE && ACTIVE.inFacets) ACTIVE = document.body;
  if (had) fx.fire("focusout", {target: rb});
  if (!box) return;
  const at = (k) => (new RegExp("\\s" + k + '="([^"]*)"').exec(box[0]) || [])[1];
  rb.value = unesc(at("value") || ""); rb.selectionStart = rb.selectionEnd = 0;
  for (const k of Object.keys(ATTR)) delete ATTR[k];
  for (const k of ["aria-expanded", "aria-activedescendant"]) if (at(k) !== undefined) ATTR[k] = at(k);
  const ul = /<ul class="rsaoffers"([^>]*)>([\s\S]*?)<\/ul>/.exec(v) || ["", "", ""];
  ro.innerHTML = ul[2]; ro.hidden = /\shidden/.test(ul[1]);
  const p = /<p class="fnone" id="rsanote"([^>]*)>([\s\S]*?)<\/p>/.exec(v) || ["", " hidden", ""];
  rn.textContent = unesc(p[2]); rn.hidden = /\shidden/.test(p[1]);
  rs.textContent = ""; }});
const shell = document.querySelector(".shell");
let SHUT = false;
shell.classList = {toggle() {}, add() {}, remove() {}, contains: (c) => SHUT && c === "nofacets"};
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8") + "; ({render, sel})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const $ = (x) => document.querySelector(x);
const elsewhere = {tagName: "BUTTON", inFacets: true};       // Clear, or the next control in the panel
const outside = {tagName: "A"};                                // somewhere off the panel
const next = {tagName: "A", inFacets: true};                   // the control after the box, where Tab goes
// A click on something whose closest(`sel`) is `hit`: from a pointer, or
// (detail 0) from the keyboard.
const press = (sel, hit, detail = 1) => fire("click", {target: {dataset: {}, closest: (x) => x === sel ? hit : null},
  detail, button: 0, preventDefault() {}, stopPropagation() {}});
const pressId = (id) => fire("click", {target: {id, dataset: {}, closest: () => null}, detail: 1, button: 0,
  preventDefault() {}, stopPropagation() {}});
const text = (h) => unesc(h.replace(/<[^>]+>/g, "").replace(/&middot;/g, "·")).replace(/\s+/g, " ").trim();
const offers = (html) => [...(html || "").matchAll(/<li\b([^>]*)>([\s\S]*?)<\/li>/g)]
  .map(m => { const at = (k) => (new RegExp("\\s" + k + '="([^"]*)"').exec(m[1]) || [])[1];
    return {id: at("id"), role: at("role"), a: at("data-rsapick"), on: at("aria-selected"), text: text(m[2])}; });
const look = () => {
  const f = fx.innerHTML, g = (/<div class="fgroup[^"]*"><button class="fhead" data-g="rsa"[\s\S]*$/.exec(f) || [""])[0];
  const r = $("#results").innerHTML;
  return {group: g, label: (/data-g="rsa"\s*aria-expanded="[^"]*"><span>([^<]*)<\/span>/.exec(f) || [])[1] || null,
    boxed: BOXED, line: text((/<p class="frsa">([\s\S]*?)<\/p>/.exec(g) || ["", ""])[1]),
    why: text((/<p class="fnone">([\s\S]*?)<\/p>/.exec(g) || ["", ""])[1]),
    links: [...g.matchAll(/<a href="([^"]*)">([^<]*)<\/a>/g)].map(m => [m[1], m[2]]),
    offers: BOXED ? offers(ro.innerHTML) : [], drawn: offers((/<ul class="rsaoffers"[^>]*>([\s\S]*?)<\/ul>/.exec(g) || ["", ""])[1]),
    note: !BOXED || rn.hidden ? "" : rn.textContent, say: BOXED ? rs.textContent : "", attrs: {...ATTR},
    value: rb.value, caret: [rb.selectionStart, rb.selectionEnd],
    focus: ACTIVE === rb ? "box" : ACTIVE === elsewhere ? "elsewhere" : ACTIVE === outside ? "outside"
      : ACTIVE === next ? "next" : ACTIVE && ACTIVE.g ? "head:" + ACTIVE.g : "none", groups: HEADS().map(h => h.g),
    rsa: [...s.sel.rsa], address: location.search,
    cards: [...r.matchAll(/<article class="card[^"]*" data-id="([^"]+)"/g)].map(m => m[1]),
    count: $("#count").textContent, asked: ASKED.filter(p => p === "/laws/chapters.json").length,
    heads: ASKED.filter(p => p === "/laws/headings.json").length, draws: DRAWS};
};
// Typing: the box focused, the caret after the last letter.
const type = async (t) => { ACTIVE = rb; rb.value = t; rb.selectionStart = rb.selectionEnd = t.length;
  fx.fire("input", {target: rb}); await ticks(10); return look(); };
const key = async (k) => { let stopped = false;
  fx.fire("keydown", {target: rb, key: k, stopPropagation() { stopped = true; }}); await ticks(10);
  return stopped; };
// The box left for `to`: the focus goes, then the box hears it.
const leave = async (to) => { ACTIVE = to; fx.fire("focusout", {target: rb}); await ticks(10); return look(); };
// Tab, as a browser works it: its keydown heard, then the focus moved on
// from wherever that left it -- from the box, to the control after it; from
// anywhere else, to the top of the page -- and the box told it is left.
const tab = async () => { fx.fire("keydown", {target: rb, key: "Tab", stopPropagation() {}}); await ticks(10);
  ACTIVE = ACTIVE === rb ? next : document.body; fx.fire("focusout", {target: rb}); await ticks(10); return look(); };
// A press of the mouse, held a moment and let go, as Chromium works one: on
// `hit` (its closest(`sel`)), on the control whose id is `id`, or on nothing.
// The press, the focus leaving the box -- for what was pressed, or for the
// page (`to`, an offer taking no focus) -- and what that set going run while
// the button is held down; then the release, and in the same task its click,
// which lands on what was pressed only if that has not moved by then, and
// otherwise on the page around it. Where the list under the box shut, or the
// panel was drawn anew, between the press and its click, the click is lost,
// as it was in Chromium (the review of 26 October 2026: Clear did not
// clear). Says whether it moved.
const click = async (sel, hit, id, to) => {
  const shown = ro.hidden, d0 = DRAWS;
  fire("pointerdown", {target: {}});
  ACTIVE = to || (id || hit ? elsewhere : document.body); fx.fire("focusout", {target: rb});
  await ticks(10);
  fire("pointerup", {target: {}});
  const moved = ro.hidden !== shown || DRAWS !== d0;
  if (moved || !(id || sel)) press(null, null); else if (id) pressId(id); else press(sel, hit);
  await ticks(10);
  return moved;
};
// Another filter's checkbox, `v` of Status, ticked with the mouse from the
// box: the press takes the focus, then the release, its click and the change
// it makes -- the list narrowed and drawn again -- all before anything the
// box set going on being left is run.
const tickStatus = async (v) => {
  fire("pointerdown", {target: {}});
  ACTIVE = elsewhere; fx.fire("focusout", {target: rb}); await ticks(10);
  fire("pointerup", {target: {}});
  const cb = {dataset: {f: "status"}, value: v, checked: true, closest: () => null};
  fire("click", {target: cb, detail: 1, button: 0, preventDefault() {}, stopPropagation() {}});
  fire("change", {target: cb});
  await ticks(10); return look();
};
// The panel drawn again, as ticking and unticking a status draws it.
const redraw = () => { s.sel.status.add("Died"); s.render(); s.sel.status.clear(); s.render(); return look(); };
const term = async (t) => { $("#year").fire("change", {target: {value: t}}); await ticks(40); return look(); };
const head = async () => { press("#facets .fhead", {dataset: {g: "rsa"}}); await ticks(30); return look(); };
(async () => {
  for (let i = 0; i < 400 && q.disabled !== false; i++) await ticks(1);
  if (q.disabled !== false) { console.log("app.js never finished loading the fixture"); process.exit(1); }
  const out = {};
  try {
    s.render(); out.shut = look();
    if (MODE === "terms") {
      // Arrived on the requests, then the current term; a law chosen there,
      // then the requests, All Terms and the requests again.
      out.reqArrive = look();
      // The current term chosen, and the list drawn again while its rows are
      // on their way (a letter typed in the search box draws it), then the
      // rows let in.
      $("#year").fire("change", {target: {value: "2025-2026"}}); await ticks(5);
      s.render(); out.reqLoading = look(); releaseIdx(); await ticks(40);
      out.reqThenNow = look();
      await head(); await type("91-A"); await key("Enter"); out.nowChosen = look();
      out.reqChosen = await term("2027-requests");
      press("[data-rsapick]", {dataset: {rsapick: ""}}); await ticks(10); out.reqCleared = look();
      out.allOpen = await term("all");
      out.all404 = await type("404");
      // A term of bills that say no law: the fixture's earlier one.
      await term("2025-2026"); await type("91-A"); await key("Enter"); out.oldChosen = await term("2023-2024");
      process.stdout.write("\n@@" + JSON.stringify(out)); return;
    }
    s.sel.status.add("Passed"); s.render(); s.sel.status.clear(); s.render(); out.others = look();
    out.opened = await head();
    if (MODE.startsWith("slow")) {
      out.waiting = await type("right to kn");
      if (MODE === "slowshut") SHUT = true;
      const before = DRAWS; release(); await ticks(30); out.arrived = look(); out.redrawn = DRAWS - before;
      process.stdout.write("\n@@" + JSON.stringify(out)); return;
    }
    if (MODE === "failonce") {
      out.failed = await type("right to know"); out.failedAgain = await type("governmental");
      out.headsFailed = await type("540:"); out.headsFailedAgain = await type("540:2");
      await head(); out.reshut = look(); out.reopened = await head();
      out.retried = await type("right to know"); out.headsRetried = await type("540:");
      process.stdout.write("\n@@" + JSON.stringify(out)); return;
    }
    for (const t of ["91", "9", "RSA 91a", "RSA chapter 91-a", "right to know", "right to kn", "governmental records",
                     "criminal code", "crimes", "unlicensed insurers", "preliminary", "revised statutes",
                     "insurance department", "elections", "tenant", "housing", "tax", "21-", "210-", "21", "6",
                     "540:", "91-A:", "91-A:4-A", "194", "91-A:99", "404", "dog licensing", "xyzzy"])
      out["t:" + t] = await type(t);
    await type("21-"); await key("Enter"); out.enterDash = look();
    await type("540:"); await key("ArrowUp"); out.up = look(); await key("ArrowDown"); out.wrap = look();
    out.tab = await tab();
    await type("tax"); out.leftOut = await leave(outside);
    await type("91"); await key("ArrowDown"); out.down = look();
    await key("Enter"); out.chosen = look();
    await type("404"); await key("Enter"); out.enter404 = look();
    await type("91"); out.escStopped = await key("Escape"); out.esc = look();
    out.escAgain = await key("Escape");
    await type("tax"); await key("Escape"); out.escTyped = look();
    await type("tax"); out.tabTyped = await tab();
    await type("91-A:4"); await key("Enter"); out.section = look();
    // Clear, by a finger or the mouse, then from the keyboard.
    ACTIVE = elsewhere; press("[data-rsapick]", {dataset: {rsapick: ""}}); await ticks(10); out.cleared = look();
    await type("91-A"); await key("Enter");
    ACTIVE = elsewhere; press("[data-rsapick]", {dataset: {rsapick: ""}}, 0); await ticks(10); out.clearedKeys = look();
    // An offer pressed with the mouse, which takes no focus of its own.
    await type("tenant");
    out.pressedMoved = await click("[data-rsapick]", {dataset: {rsapick: "540"}}, null, document.body);
    out.pressed = look();
    await type("194-g"); await key("Enter"); out.unnamed = look();
    await type("91"); await key("Enter"); out.enter91 = look();
    out.retyped = await type("91");
    await type("540:"); await key("Enter"); out.colon = look();
    // Emptied: after the pause; on Return before it; on leaving before it.
    out.emptied = await type("");
    await type("91-A"); await key("Enter"); HOLD = true; await type(""); await key("Enter"); out.emptiedReturn = look();
    await type("91-A"); await key("Enter"); await type(""); out.emptiedLeft = await leave(outside);
    HOLD = false; PENDING.clear();
    // Clear all filters, with words in the box.
    await type("91-A"); await key("Enter"); await type("tax"); pressId("clear"); await ticks(10); out.clearAll = look();
    // Another filter ticked: "None of these bills".
    s.sel.status.add("Died"); s.render(); out.narrowed = await type("540"); s.sel.status.clear(); s.render();
    // Tabled ticked, whose one bill changes none of the Criminal Code.
    s.sel.status.add("Tabled"); s.render(); out.codeNarrowed = await type("criminal code");
    s.sel.status.clear(); s.render();
    // The mouse: a press on the chosen line's Clear, and on Clear all
    // filters, held while the list is open under words typed; one on nothing.
    await type("91-A"); await key("Enter"); await type("tax");
    out.mouseClearMoved = await click("[data-rsapick]", {dataset: {rsapick: ""}}); out.mouseClear = look();
    await type("91-A"); await key("Enter"); await type("tax");
    out.mouseAllMoved = await click(null, null, "clear"); out.mouseAll = look();
    await type("91-A"); await key("Enter"); await type("tax"); await click(null, null); out.mouseNothing = look();
    // Words given way to the chosen number, then the panel drawn again.
    await type("tax"); await key("Escape"); out.escRedrawn = redraw();
    await type("tax"); await leave(outside); out.leftRedrawn = redraw();
    // Spaces over a chosen law: after the pause, and left before it.
    out.spaces = await type("   ");
    await type("91-A"); await key("Enter"); HOLD = true; await type("   "); out.spacesLeft = await leave(outside);
    HOLD = false; PENDING.clear();
    // A number typed whole and the box left, with nothing chosen and over a
    // law chosen; and one no bill changes.
    await type("91-A"); out.numLeft = await leave(outside);
    await type("540"); out.numOverLeft = await leave(outside);
    press("[data-rsapick]", {dataset: {rsapick: ""}}); await ticks(10);
    await type("91"); out.num91Left = await leave(outside);
    // The same by Tab, with nothing chosen and over a law chosen.
    await type("91-A"); out.numTab = await tab();
    await type("540"); out.numOverTab = await tab();
    // A press whose release never reaches the page (a menu opened over it),
    // then words typed and the box left.
    fire("pointerdown", {target: {}}); await ticks(10);
    await type("tax"); out.stuckLeft = await leave(outside);
    // "540" typed with Died ticked, none of whose bills change it, the box
    // left by a press on nothing; then Died unticked, and a click elsewhere,
    // which is not the box's to answer.
    press("[data-rsapick]", {dataset: {rsapick: ""}}); await ticks(10);
    s.sel.status.add("Died"); s.render(); await type("540"); await click(null, null);
    s.sel.status.clear(); s.render(); press(null, null); await ticks(10); out.clickAfter = look();
    // Numbers no RSA number is shaped like.
    out.odd1234 = await type("1234"); out.oddSec = await type("91-A:4:5");
    // A number typed whole, the box left by ticking a status none of whose
    // bills change it, with nothing chosen and over a law chosen.
    press("[data-rsapick]", {dataset: {rsapick: ""}}); await ticks(10);
    await type("91-A"); out.numTicked = await tickStatus("Withdrawn"); s.sel.status.clear(); s.render();
    await type("91-A"); await key("Enter"); await type("540");
    out.numOverTicked = await tickStatus("Withdrawn"); s.sel.status.clear(); s.render();
    // "91-A" typed, the panel drawn again with the focus kept in the box,
    // then "tax" typed and Tab: what the box read as it was drawn anew is
    // not taken for the words.
    press("[data-rsapick]", {dataset: {rsapick: ""}}); await ticks(10);
    await type("91-A"); s.render(); await ticks(10); await type("tax"); out.staleTab = await tab();
    // What is pressed is what is chosen, whatever number the box read as it
    // was left (the review of 26 October 2026): a section pressed after
    // "91-A:", and Clear and Clear all pressed after "540" typed over 91-A.
    press("[data-rsapick]", {dataset: {rsapick: ""}}); await ticks(10);
    await type("91-A:"); await click("[data-rsapick]", {dataset: {rsapick: "91-A:4"}}, null, document.body);
    out.secPressed = look();
    press("[data-rsapick]", {dataset: {rsapick: ""}}); await ticks(10);
    await type("91-A"); await key("Enter"); await type("540");
    await click("[data-rsapick]", {dataset: {rsapick: ""}}); out.clearPressed = look();
    await type("91-A"); await key("Enter"); await type("540");
    await click(null, null, "clear"); out.clearAllPressed = look();
    // A press that brings no click (a right button), the box come back to,
    // its words replaced and left by Tab: the number read at the press is
    // not taken for the words typed since.
    press("[data-rsapick]", {dataset: {rsapick: ""}}); await ticks(10);
    await type("91-A"); fire("pointerdown", {target: {}}); ACTIVE = elsewhere;
    fx.fire("focusout", {target: rb}); await ticks(10);
    await type("tax"); out.noClickTab = await tab();
  } catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + (e.stack || "").split("\n")[1]; }
  process.stdout.write("\n@@" + JSON.stringify(out));
})().catch(e => { console.log("RUN " + e.message); process.exit(1); });
"""


def _rsa_fixture(chapters=True):
    """_search_groups_fixture, and the laws its bills change: HB 1 RSA 91-A:4
    and 91-A:4-a, HB 4 91-A:2 and 540:2, HB 5 540:1 and 651:2, SB 6 597:1 and
    a chapter of its own writing, 194-G, that the Laws pages do not have yet,
    HB 2 21-J and 210, HB 3 21 and 210, HR 9 415 and 204-C, and seven bills a
    tax law each; and the Criminal Code, Title LXII, as the bills of
    seventeen terms of nineteen change it: seven of its chapters, each by a
    different number of bills -- 644 by seven, 631 six, 651 five, 639 four,
    633 three, RSA 625 itself two (625:9) and 637 one -- so that its six most
    changed, in that order, are not its first six by number. With
    `chapters`, their list, laws/chapters.json, as build_rsa.build_indexes
    writes it: 91-A by its name, the name it is known by and its topic; 91,
    91-B and 404, which no bill changes; 91, opening Title VI, with a topic
    of its own, Elections; 540 with the topic Housing, and 204-C, Housing
    Finance Authority, with the word in its name; 625, Preliminary, known as
    the Criminal Code, as the real list has it, opening Title LXII, whose 626
    no bill changes, and 597, of another title with the same topic; 406-B,
    known as the Uniform Unlicensed Insurers Act, in a
    title 400-A opens and 415 shares; 624, known as the Revised Statutes
    Annotated, which no bill changes, alone in its title as in the real list;
    and laws/headings.json, the sections' headings, but not 91-A:4-a's, a
    section a bill writes anew."""
    fx = _search_groups_fixture()
    changes = {"HB1": ["91-A", "91-A:4", "91-A:4-a"], "HB4": ["91-A", "91-A:2", "540", "540:2"],
               "HB5": ["540", "540:1", "651", "651:2"], "SB6": ["194-G", "194-G:1", "597", "597:1"],
               "HB2": ["21-J", "21-J:1", "210", "210:1"], "HB3": ["21", "21:2", "210", "210:1"],
               "HR9": ["415", "415:6", "204-C", "204-C:1"]}
    tax = {"SB13": "72", "HB14": "77-A", "HB15": "77-E", "HJR16": "78-A", "PET17": "79-A", "SSHB18": "83-F",
           "HCO19": "84-A"}
    code = {"HB5": ["644", "631", "639", "633", "625"], "CACR7": ["644", "631", "651", "639", "633", "625"],
            "CACR8": ["644", "631", "651", "639", "633"], "SR10": ["644", "631", "651", "639"],
            "HCR11": ["644", "631", "651"], "SCR12": ["644", "631"], "ZZ20": ["644", "637"]}
    for b in fx["/idx/2025-2026.json"]:
        if b["id"] in changes:
            b["rsa"] = changes[b["id"]]
        if b["id"] in tax:
            b["rsa"] = [tax[b["id"]], tax[b["id"]] + ":1"]
        for ch in code.get(b["id"], []):
            b["rsa"] = b.get("rsa", []) + [ch, ch + (":9" if ch == "625" else ":1")]
    if chapters:
        crimes = ["Crimes, Criminal Procedure and Corrections"]
        fx["/laws/chapters.json"] = {
            "91-A": ["Access to Governmental Records and Meetings", "VI", 9, False,
                     ["right-to-know law"], ["Right to Know"], 1],
            "91": ["Eligibility to Hold Public Office; Removal", "VI", 4, False, [], ["Elections"], 0],
            "91-B": ["Records Kept by Towns", "VI", 2, False, [], [], 0],
            "404": ["Dog Licensing", "XXX", 3, False, [], [], 0],
            "540": ["Actions Against Tenants", "LV", 20, False, [], ["Housing"], 0],
            "204-C": ["Housing Finance Authority", "XVII", 30, False, [], ["Housing"], 0],
            "624": ["Repeals and Revisions", "LXI", 3, False, ["Revised Statutes Annotated"], [], 0],
            "625": ["Preliminary", "LXII", 9, False, ["Criminal Code"], crimes, 0],
            "626": ["General Principles", "LXII", 8, False, [], crimes, 0],
            "631": ["Assault and Related Offenses", "LXII", 4, False, [], crimes, 0],
            "633": ["Interference with Freedom", "LXII", 9, False, [], crimes, 0],
            "637": ["Theft", "LXII", 14, False, [], crimes, 0],
            "639": ["Offenses Against the Family", "LXII", 9, False, [], crimes, 0],
            "644": ["Breaches of the Peace and Related Offenses", "LXII", 22, False, [], crimes, 0],
            "651": ["Sentences", "LXII", 56, False, [], crimes, 2],
            "597": ["Bail and Recognizances", "LIX", 40, False, [], crimes, 0],
            "400-A": ["Insurance Department", "XXXVII", 40, False, [], ["Insurance"], 0],
            "406-B": ["Unauthorized Insurance", "XXXVII", 9, False, ["Uniform Unlicensed Insurers Act"],
                      ["Insurance"], 0],
            "415": ["Accident and Health Insurance", "XXXVII", 30, False, [], ["Insurance"], 0],
            "21": ["Statutory Construction", "I", 63, False, [], [], 0],
            "21-J": ["Department of Revenue Administration", "I", 88, False, [], [], 0],
            "210": ["Fur-Bearing Animals", "XVIII", 34, False, [], [], 0],
            "72": ["Persons and Property Liable to Taxation", "V", 80, False, [], [], 0],
            "77-A": ["Business Profits Tax", "V", 30, False, [], [], 0],
            "77-E": ["Business Enterprise Tax", "V", 20, False, [], [], 0],
            "78-A": ["Tax on Meals and Rooms", "V", 30, False, ["Meals"], [], 0],
            "79-A": ["Current Use Taxation", "V", 30, False, [], [], 0],
            "83-F": ["Utility Property Tax", "V", 10, False, [], [], 0],
            "84-A": ["Real Estate Transfer Tax", "V", 10, False, [], [], 0]}
        fx["/laws/headings.json"] = [["91-A:2", "Meetings Open to Public."],
                                     ["91-A:4", "Minutes and Records Available for Public  Inspection."],
                                     ["540:1", "Applicability."], ["540:2", "Termination of Tenancy."]]
    return fx


def _rsa_run(chapters=True, address="", mode=""):
    got = _node_app(_RSA_GROUP_HARNESS, {"fixture.json": json.dumps(_rsa_fixture(chapters))},
                    args=(address, mode))
    if got is not None:
        assert "threw" not in got, f"the bill search threw {got['threw']}"
        assert "runaway" not in got, (f"{got.get('runaway')}: a list that fails is asked for again on "
                                      "every drawing of the panel, not once for each opening of the group")
    return got


def _offered(r):
    return [x["text"] for x in r["offers"]]


@check("frontend", "the bill search's Laws Changed (RSA) filter offers, as its box is typed in, "
                   "the chapters and sections the term's bills change -- by number, by a "
                   "section, by the words of a chapter's name or the name it is known by -- "
                   "each with its name or heading and how many bills it would list, six at most, "
                   "never a chapter no bill changes, and no pills of bare numbers")
def _laws_changed_offers():
    """The person, 26 October 2026: "The RSA (Statute) filter on the bills
    page is formatted a bit confusingly at the moment as it's a bit unclear
    what the most changed by these bills section means and those don't seem
    to have any particular meaning. It's more of a power user filter for folks
    who know a specific chapter of law they want to search for bills that
    change it, but it should still be easily understandable." The group was
    headed RSA (Statute) and drew ten pills of bare chapter numbers and counts
    under "Most changed by these bills:". Held, over _rsa_fixture in node: the
    group headed Laws Changed (RSA), its box asking for "Like 91-A, or a few
    words" -- not "a name", which under the Sponsor filter read as a person's
    (the review of 26 October 2026) -- and no longer than the 29 characters
    that fit the box at 1280 ("A number like 91-A, or a few words" lost its
    last word there); no pill and nothing offered
    until something is typed; "91", "9", "RSA 91a" and "RSA chapter 91-a"
    offer RSA 91-A with its name and its two bills, and not 91 or 91-B, which
    no bill changes; "21" offers RSA 21 first, the number typed, then 210,
    which more bills change, and 21-J; "6" six of the seven chapters
    beginning with it, the most changed; "21-" 21-J alone, the chapters whose
    number begins with exactly that (the review: "1-" offered 189 and 198
    after 1-A), and Return there chooses nothing and says nothing against
    it; and "210-", where no bill changes a 210-A and two change 210, says so
    of a number begun rather than that no bill changes RSA 210; "governmental
    records" (91-A's name), "right to know" (the name it is known by), "right
    to kn" on the way to it, and "tenant" (540's name) offer theirs;
    "housing" RSA 204-C by its name above 540 by its topic, though more bills
    change 540; "tax" six of the seven tax laws; "540:" the sections of 540
    the bills change, each with its heading, and the chapter after them, named
    once; "91-A:4-A" the section 91-A:4-a, which has no heading; a chapter of
    a bill's own writing, 194-G, offered by its number without a name;
    "91-A:99", a section no bill changes, its chapter offered under a line
    that says so; "criminal code", the name RSA 625 is known by -- its
    title's, the Criminal Code -- the six chapters of the title the bills
    change most, the most first: 625 among them, as it is one of those six
    here, and not 637, the seventh, nor 626, which none changes, nor 597,
    Bail, of another title (the review: where a bill changed 625, as in
    seventeen terms of nineteen, it was offered alone; and where none did,
    "No bill ... changes RSA 625, Preliminary" was said while bills changed
    the code); with Tabled ticked, whose one bill changes none of it, "None
    of these bills changes the Criminal Code."; "crimes", the topic of the
    code's chapters and of 597, the six of them most changed, the most first;
    "preliminary", the name of RSA 625 itself, RSA 625 alone. Where nothing a
    bill changes fits, one
    line and nothing offered: a number names the chapter typed ("404", RSA
    404, Dog Licensing, which no bill of the term changes); words name no
    law, "No bill in the 2025–2026 term changes a law whose name has “dog
    licensing” in it." -- the law of the whole list they fitted best was
    named, and on real data "students" named RSA 110-E and "driving" RSA
    287-G (the review) -- and so do "unlicensed insurers", the name RSA
    406-B is known by, which does not open its title; "revised statutes",
    the name RSA 624 is known by, which is all of its title; "insurance
    department", RSA 400-A's own name, which opens its title; and
    "elections", RSA 91's topic, which opens its title too: the title's rule
    is for a name a title's first chapter is known by, and for no other, or
    they would offer 415 or 91-A, or name a title. And "1234" and
    "91-A:4:5", numbers no RSA number is shaped like, "RSA numbers look like
    91-A or 91-A:4.", where they were asked for a chapter's number as if they
    had typed words. And the box a combobox: role, aria-controls and
    aria-expanded on it, every offer an option; the down arrow puts
    aria-activedescendant on the first and marks it, the up arrow from none
    on the last, and they wrap; the status line counts them, and is emptied
    when Tab, Escape or leaving the box shuts the list (it went on saying "6
    laws match"); Escape shuts the list and goes no further, so
    the phone's panel stays open, and with the list shut goes on to the
    document -- as the address box does (_addr_suggest)."""
    got = _rsa_run()
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    bad = []
    o = got["opened"]
    if o["label"] != "Laws Changed (RSA)":
        bad.append(f"the group is headed {o['label']!r}, not 'Laws Changed (RSA)'")
    if re.search(r"Most changed|frsapick|class=\"pill", o["group"]) or o["drawn"]:
        bad.append("the opened group, nothing typed, still draws pills or offers: "
                   + o["group"][:300])
    box = re.search(r'<input class="sbox" id="rsabox"[^>]*>', o["group"])
    box = box.group(0) if box else ""
    for want in ('role="combobox"', 'aria-controls="rsaoffers"', 'aria-autocomplete="list"',
                 'placeholder="Like 91-A, or a few words"',
                 'aria-label="A law’s RSA number, like 91-A, or a few words from its name"'):
        if want not in box:
            bad.append(f"the box is not {want}: {box[:300]}")
    ph = re.search(r'placeholder="([^"]*)"', box)
    if not ph or len(ph.group(1)) > 29:
        bad.append(f"the box's placeholder {ph and ph.group(1)!r} is longer than the 29 characters that "
                   "fit it at 1280")
    if 'id="rsaoffers" role="listbox"' not in o["group"]:
        bad.append("the list under the box is not a listbox named rsaoffers")
    name = "Access to Governmental Records and Meetings"
    a91 = ["RSA 91-A, " + name + " 2 bills"]
    tax = ["RSA 72, Persons and Property Liable to Taxation 1 bill", "RSA 77-A, Business Profits Tax 1 bill",
           "RSA 77-E, Business Enterprise Tax 1 bill", "RSA 78-A, Tax on Meals and Rooms 1 bill",
           "RSA 79-A, Current Use Taxation 1 bill", "RSA 83-F, Utility Property Tax 1 bill"]
    code = ["RSA 644, Breaches of the Peace and Related Offenses 7 bills",
            "RSA 631, Assault and Related Offenses 6 bills", "RSA 651, Sentences 5 bills",
            "RSA 639, Offenses Against the Family 4 bills",
            "RSA 633, Interference with Freedom 3 bills", "RSA 625, Preliminary 2 bills"]
    want = {"91": a91, "9": a91, "RSA 91a": a91, "RSA chapter 91-a": a91, "right to know": a91,
            "right to kn": a91, "governmental records": a91, "criminal code": code, "6": code, "crimes": code,
            "preliminary": ["RSA 625, Preliminary 2 bills"],
            "tenant": ["RSA 540, Actions Against Tenants 2 bills"],
            "housing": ["RSA 204-C, Housing Finance Authority 1 bill", "RSA 540, Actions Against Tenants 2 bills"],
            "tax": tax,
            "21-": ["RSA 21-J, Department of Revenue Administration 1 bill"],
            "21": ["RSA 21, Statutory Construction 1 bill", "RSA 210, Fur-Bearing Animals 2 bills",
                   "RSA 21-J, Department of Revenue Administration 1 bill"],
            "540:": ["RSA 540:1, Applicability 1 bill", "RSA 540:2, Termination of Tenancy 1 bill",
                     "RSA 540, Actions Against Tenants 2 bills"],
            "91-A:": ["RSA 91-A:2, Meetings Open to Public 1 bill",
                      "RSA 91-A:4, Minutes and Records Available for Public Inspection 1 bill",
                      "RSA 91-A:4-a 1 bill"] + a91,
            "91-A:4-A": ["RSA 91-A:4-a 1 bill"] + a91,
            "194": ["RSA 194-G 1 bill"]}
    for t, rows in want.items():
        r = got["t:" + t]
        if _offered(r) != rows:
            bad.append(f"{t!r} offers {_offered(r)}, not {rows}")
        elif any(x["role"] != "option" for x in r["offers"]) or r["attrs"].get("aria-expanded") != "true":
            bad.append(f"{t!r}: an offer is not an option, or the box does not say the list is open")
        elif r["note"]:
            bad.append(f"{t!r} offers and says {r['note']!r} as well")
    none = {"404": "No bill in the 2025–2026 term changes RSA 404, Dog Licensing.",
            "210-": "No bill in the 2025–2026 term changes a law whose number begins “210-”."}
    for t in ("dog licensing", "unlicensed insurers", "revised statutes", "insurance department", "elections",
              "xyzzy"):
        none[t] = f"No bill in the 2025–2026 term changes a law whose name has “{t}” in it."
    odd = "RSA numbers look like 91-A or 91-A:4."
    for t, r, line in [(t, got["t:" + t], line) for t, line in none.items()] + [
            ("criminal code, Tabled ticked", got["codeNarrowed"], "None of these bills changes the Criminal Code."),
            ("1234", got["odd1234"], odd), ("91-A:4:5", got["oddSec"], odd)]:
        if r["offers"] or r["note"] != line or r["attrs"].get("aria-expanded") != "false":
            bad.append(f"{t!r} offers {_offered(r)} and says {r['note']!r}, not nothing and {line!r}")
    ed = got["enterDash"]
    if ed["rsa"] or _offered(ed) != want["21-"] or ed["note"]:
        bad.append(f"'21-' and Return chose {ed['rsa']}, offering {_offered(ed)} and saying {ed['note']!r}: "
                   "nothing to choose, and nothing to say against the 21-J it offers")
    s99 = got["t:91-A:99"]
    if _offered(s99) != a91 or s99["note"] != f"No bill in the 2025–2026 term changes RSA 91-A:99, in {name}.":
        bad.append(f"'91-A:99', a section no bill changes, offers {_offered(s99)} and says "
                   f"{s99['note']!r}, not its chapter under a line that says no bill changes it")
    if got["t:9"]["say"] != "1 law matches; the down arrow chooses it." \
            or got["t:tax"]["say"] != "6 laws match; the down arrow chooses one.":
        bad.append(f"the status line says {got['t:9']['say']!r} for one offer and {got['t:tax']['say']!r} "
                   "for six")
    d = got["down"]
    if d["attrs"].get("aria-activedescendant") != "rsaoffers-0" \
            or [x["on"] for x in d["offers"]] != ["true"] or d["offers"][0]["id"] != "rsaoffers-0":
        bad.append(f"the down arrow does not put the box on the first offer: {d['attrs']}, "
                   f"{d['offers']}")
    up, wrap, tab = got["up"], got["wrap"], got["tab"]
    if up["attrs"].get("aria-activedescendant") != "rsaoffers-2" \
            or [x["on"] for x in up["offers"]] != ["false", "false", "true"] \
            or wrap["attrs"].get("aria-activedescendant") != "rsaoffers-0":
        bad.append(f"the arrow keys do not wrap: up from none is {up['attrs']}, then down "
                   f"{wrap['attrs']}")
    for k, r in (("Tab", tab), ("leaving the box", got["leftOut"]), ("Escape", got["esc"])):
        if r["offers"] or r["attrs"].get("aria-expanded") != "false" or r["say"]:
            bad.append(f"{k} leaves the list open or the status line saying something: {_offered(r)}, "
                       f"{r['attrs']}, {r['say']!r}")
    e = got["esc"]
    if not got["escStopped"] or "aria-activedescendant" in e["attrs"] or got["escAgain"]:
        bad.append(f"Escape on the open list stopped there {got['escStopped']}, the box {e['attrs']}; "
                   f"on the list shut, stopped there {got['escAgain']}, keeping the phone's panel open")
    assert not bad, "; ".join(bad[:6])
    return "ok", ("headed Laws Changed (RSA), no pills; 91, 9, RSA 91a and RSA chapter 91-a, right "
                  "to know and governmental records offer RSA 91-A by name with its two bills, 540 "
                  "by its name, its topic and its sections by heading, tax six of seven; criminal "
                  "code its title's six most changed chapters, or the title named; 21- the lettered "
                  "chapters alone; 91-A:99 and 404 named as typed, and words that find no law a "
                  "bill changes said in one line naming none; 1234 as no RSA number's shape; the "
                  "arrow keys, Tab and Escape work the list")


@check("frontend", "a law chosen in the Laws Changed filter -- by Return, by the arrow keys, by a "
                   "press, a section typed or named in the address -- lists the bills that change "
                   "it, under a line that names it, with the way to read it and Clear, the box "
                   "always saying what is chosen; a law no bill changes is never chosen")
def _laws_changed_chosen():
    """The line under the box was "Bills that change RSA 91-A · Read the
    statute · Clear": the number alone. Since the person's note of 26 October
    2026 it names the chapter ("Bills that change RSA 91-A, Access to
    Governmental Records and Meetings"), a section as in its chapter. Held,
    over _rsa_fixture in node: "91", the down arrow and Return choose RSA
    91-A, list HB 1 and HB 4 and say so, with the link to /laws/91-a and
    Clear, put ?rsa=91-A in the address, and leave the keyboard in the box
    after its last letter; "404" and Return, a chapter no bill changes,
    choose nothing and keep what was chosen; "91" and Return, where RSA 91-A
    is offered and no bill changes RSA 91, choose nothing, keep the offer and
    say why, until the box is typed in again; "91-A:4" and Return choose the
    section and list HB 1; "540:" and Return, no section begun, choose RSA
    540; Clear lists every bill again, and puts the keyboard back in the box
    only when it was pressed from the keyboard -- tapped, it is not, nor is an
    offer pressed (the review: a phone's keyboard came up over the bills just
    chosen) -- and an offer pressed with the mouse is taken, the list staying
    as it is until its click is heard; 194-G, a chapter the Laws pages do not have,
    is chosen without a name and without a link to a page there is not; and
    ?rsa=91-A:4 in the address arrives with the section chosen, named, and HB
    1 listed. And the box says what is chosen (the review of 26 October 2026:
    emptied, it showed nothing chosen while ?rsa=91-A listed 29 bills):
    emptied, the law goes, with its address, after the pause in typing, on
    Return before it, and on leaving the box before it, the focus left where
    the reader went, and a box of spaces is an emptied box; words that chose
    nothing give way to the chosen law's number on Escape and on leaving the
    box, and stay given way when the panel is drawn again; Clear all filters
    empties it. A number typed whole and the box left is chosen, as Return
    chooses it -- "91-A", and "540" over 91-A -- and "91", which no bill
    changes, is not (the review: "91-A" left by a tap read 91-A over a list it
    did not filter); left by ticking Withdrawn, none of whose bills changes
    either, it is chosen still, the number read as the box lost the focus
    and not from the list the tick's click and change had narrowed before the
    box was heard to be left (the final review: "91-A" read on with no badge
    and no line, and "540" over 91-A gave way to 91-A) -- and only as it was
    left: "91-A" typed and the panel drawn again with the focus kept in the
    box, then "tax" and Tab, chooses nothing; the focus stays
    where the reader sent it: left by Tab,
    the law is chosen with the keyboard still in the box, so that Tab goes on
    from there to the control after it (the review: chosen once the focus had
    gone on, the drawing took that control away and the focus fell to the
    page), and words left by Tab give way there too. With the list open under
    words typed, the chosen line's Clear and Clear all filters pressed with
    the mouse, held and let go, do what they say: the list stays as it is
    until the press's click is heard (the review: it shut under the pointer
    between press and release, and the click was lost); a press on nothing
    shuts it once let go; a press whose release never reached the page
    holds nothing after it -- the box left later is left at once (the
    review: a flag the release cleared stayed set) -- and the click a press
    waited for is the only one the box answers. And with
    another filter ticked, a law no bill of those changes is said as "None of
    these bills changes ..."."""
    got = _rsa_run()
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    bad = []
    name = "Access to Governmental Records and Meetings"
    c = got["chosen"]
    if c["rsa"] != ["91-A"] or c["cards"] != ["HB1", "HB4"] \
            or c["line"] != f"Bills that change RSA 91-A, {name} · Read the law · Clear" \
            or c["links"] != [["/laws/91-a", "Read the law"]] or c["drawn"] \
            or not c["count"].startswith("2 of ") or "rsa=91-A" not in c["address"]:
        bad.append(f"91, down and Return: chose {c['rsa']}, listing {c['cards']} ({c['count']!r}) "
                   f"under {c['line']!r} {c['links']}, offering {c['drawn']}, at {c['address']!r}")
    if c["focus"] != "box" or c["value"] != "91-A" or c["caret"] != [4, 4]:
        bad.append(f"after Return the box reads {c['value']!r}, the focus {c['focus']}, the caret at "
                   f"{c['caret']}: not in the box after its last letter")
    if '<span class="badge">1</span>' not in c["group"]:
        bad.append("the chosen law is not counted on the group's head")
    e = got["enter404"]
    if e["rsa"] != ["91-A"] or e["note"] != "No bill in the 2025–2026 term changes RSA 404, Dog Licensing.":
        bad.append(f"404 and Return chose {e['rsa']} and said {e['note']!r}: a law no bill "
                   "changes is not to be chosen, and the line says why")
    sc = got["section"]
    if sc["rsa"] != ["91-A:4"] or sc["cards"] != ["HB1"] \
            or sc["line"] != f"Bills that change RSA 91-A:4, in {name} · Read the law · Clear" \
            or sc["links"] != [["/laws/91-a#s4", "Read the law"]]:
        bad.append(f"91-A:4 and Return: chose {sc['rsa']} listing {sc['cards']} under "
                   f"{sc['line']!r} {sc['links']}")
    cl, ck = got["cleared"], got["clearedKeys"]
    if cl["rsa"] or "Bills that change" in cl["group"] or len(cl["cards"]) < 20 or cl["focus"] == "box":
        bad.append(f"Clear tapped left {cl['rsa']} chosen, {len(cl['cards'])} cards, the focus {cl['focus']}: "
                   "the box focused brings a phone's keyboard up")
    if ck["rsa"] or ck["focus"] != "box":
        bad.append(f"Clear from the keyboard left {ck['rsa']} chosen, the focus {ck['focus']}, not in the box")
    p = got["pressed"]
    if got["pressedMoved"] or p["rsa"] != ["540"] or p["cards"] != ["HB4", "HB5"] \
            or p["line"] != "Bills that change RSA 540, Actions Against Tenants · Read the law · Clear" \
            or p["focus"] == "box":
        bad.append(f"RSA 540 pressed with the mouse (the list moved under it {got['pressedMoved']}): chose "
                   f"{p['rsa']} listing {p['cards']} under {p['line']!r}, the focus {p['focus']}")
    u = got["unnamed"]
    if u["rsa"] != ["194-G"] or u["cards"] != ["SB6"] or u["line"] != "Bills that change RSA 194-G · Clear" \
            or u["links"]:
        bad.append(f"194-G, which the Laws pages do not have: chose {u['rsa']} listing {u['cards']} "
                   f"under {u['line']!r} {u['links']}")
    e91, r91 = got["enter91"], got["retyped"]
    if e91["rsa"] != ["194-G"] or _offered(e91) != ["RSA 91-A, " + name + " 2 bills"] \
            or e91["note"] != ("No bill in the 2025–2026 term changes RSA 91, Eligibility to Hold "
                               "Public Office; Removal.") or r91["note"]:
        bad.append(f"91 and Return, which no bill changes: chose {e91['rsa']}, offering "
                   f"{_offered(e91)} and saying {e91['note']!r}, and typed again {r91['note']!r}")
    co = got["colon"]
    if co["rsa"] != ["540"] or co["cards"] != ["HB4", "HB5"]:
        bad.append(f"540: and Return chose {co['rsa']} listing {co['cards']}, not RSA 540")
    for k, how in (("emptied", "after the pause in typing"), ("emptiedReturn", "on Return before the pause"),
                   ("emptiedLeft", "on leaving the box before the pause")):
        r = got[k]
        if r["rsa"] or "rsa=" in r["address"] or len(r["cards"]) < 20 or r["value"]:
            bad.append(f"the box emptied, {how}: still chose {r['rsa']} at {r['address']!r}, "
                       f"{len(r['cards'])} cards, the box {r['value']!r}")
    if got["emptiedLeft"]["focus"] != "outside":
        bad.append(f"the box emptied and left, the focus was taken back to {got['emptiedLeft']['focus']}")
    for k, how in (("escTyped", "Escape"), ("tabTyped", "Tab")):
        r = got[k]
        if r["value"] != "91-A" or r["rsa"] != ["91-A"] or r["offers"]:
            bad.append(f"'tax' typed over RSA 91-A, then {how}: the box reads {r['value']!r} with "
                       f"{r['rsa']} chosen, offering {_offered(r)}")
    if got["tabTyped"]["focus"] != "next":
        bad.append(f"'tax' typed over RSA 91-A and Tab: the focus went to {got['tabTyped']['focus']}, not on")
    ca = got["clearAll"]
    if ca["rsa"] or ca["value"] or len(ca["cards"]) < 20:
        bad.append(f"Clear all filters left {ca['rsa']} chosen and the box reading {ca['value']!r}")
    n = got["narrowed"]
    if n["note"] != "None of these bills changes RSA 540, Actions Against Tenants." or n["offers"]:
        bad.append(f"540 typed with Died ticked says {n['note']!r} offering {_offered(n)}")
    for k, what in (("mouseClear", "the chosen line's Clear"), ("mouseAll", "Clear all filters")):
        r = got[k]
        if got[k + "Moved"] or r["rsa"] or "rsa=" in r["address"] or len(r["cards"]) < 20:
            bad.append(f"'tax' typed over RSA 91-A, the list open, and {what} pressed with the mouse: the "
                       f"list shut under the pointer before its click {got[k + 'Moved']}, and {r['rsa']} is still "
                       f"chosen at {r['address']!r} -- the click lost")
    mn = got["mouseNothing"]
    if mn["offers"] or mn["value"] != "91-A" or mn["rsa"] != ["91-A"]:
        bad.append(f"a press on nothing, let go, left the list {_offered(mn)} and the box {mn['value']!r}: "
                   "the box is not left once the press is over")
    for k, how in (("escRedrawn", "Escape"), ("leftRedrawn", "leaving the box")):
        r = got[k]
        if r["value"] != "91-A" or r["rsa"] != ["91-A"]:
            bad.append(f"'tax' typed over RSA 91-A, {how}, then the panel drawn again: the box reads "
                       f"{r['value']!r}, chosen {r['rsa']} -- the words came back over the law")
    for k, how in (("spaces", "after the pause"), ("spacesLeft", "left before the pause")):
        r = got[k]
        if r["rsa"] or "rsa=" in r["address"] or r["value"].strip():
            bad.append(f"spaces typed over RSA 91-A, {how}: still chose {r['rsa']} at {r['address']!r}, the "
                       f"box {r['value']!r}")
    nl, no, n91 = got["numLeft"], got["numOverLeft"], got["num91Left"]
    if nl["rsa"] != ["91-A"] or "rsa=91-A" not in nl["address"] or nl["value"] != "91-A" \
            or nl["line"] != f"Bills that change RSA 91-A, {name} · Read the law · Clear" \
            or nl["cards"] != ["HB1", "HB4"] or nl["focus"] != "outside":
        bad.append(f"'91-A' typed and the box left: chose {nl['rsa']} at {nl['address']!r}, the box "
                   f"{nl['value']!r} under {nl['line']!r}, listing {nl['cards']}, the focus {nl['focus']}")
    if no["rsa"] != ["540"] or no["value"] != "540":
        bad.append(f"'540' typed over RSA 91-A and the box left: chose {no['rsa']}, the box {no['value']!r}")
    if n91["rsa"] or "rsa=" in n91["address"] or n91["value"] != "91":
        bad.append(f"'91', which no bill changes, typed and the box left: chose {n91['rsa']}, the box "
                   f"{n91['value']!r}")
    for k, t, want in (("numTab", "91-A", ["HB1", "HB4"]), ("numOverTab", "540 over RSA 91-A", ["HB4", "HB5"])):
        r = got[k]
        if r["cards"] != want or r["value"] != t.split()[0] or r["focus"] != "next":
            bad.append(f"'{t}' typed and Tab: listing {r['cards']}, the box {r['value']!r}, the focus "
                       f"{r['focus']} -- not on to the control after the box")
    sl, ca2 = got["stuckLeft"], got["clickAfter"]
    if sl["offers"] or sl["value"] != "540":
        bad.append(f"after a press whose release never reached the page, 'tax' typed and the box left: the "
                   f"list {_offered(sl)}, the box {sl['value']!r} -- the box not left")
    if ca2["rsa"]:
        bad.append(f"'540' typed with Died ticked, the box left by a press, Died unticked and a click elsewhere: "
                   f"chose {ca2['rsa']} -- the box answered a click that was not its own")
    for k, t, line in (("numTicked", "91-A", f"RSA 91-A, {name}"),
                       ("numOverTicked", "540 over RSA 91-A", "RSA 540, Actions Against Tenants")):
        r, a = got[k], t.split()[0]
        if r["rsa"] != [a] or f"rsa={a}" not in r["address"] or "status=Withdrawn" not in r["address"] \
                or r["value"] != a or r["line"] != f"Bills that change {line} · Read the law · Clear" \
                or '<span class="badge">1</span>' not in r["group"] or r["focus"] == "box":
            bad.append(f"'{t}' typed and the box left by ticking Withdrawn, none of whose bills changes it: "
                       f"chose {r['rsa']} at {r['address']!r}, the box {r['value']!r} under {r['line']!r}, "
                       f"the focus {r['focus']} -- the number read again from the list the tick narrowed")
    for k, want, what in (("secPressed", ["91-A:4"], "'91-A:' typed and section 91-A:4 pressed"),
                          ("clearPressed", [], "'540' typed over 91-A and the line's Clear pressed"),
                          ("clearAllPressed", [], "'540' typed over 91-A and Clear all filters pressed")):
        if got[k]["rsa"] != want:
            bad.append(f"{what}: chose {got[k]['rsa']}, not {want} -- the number the box read as it was "
                       "left was taken over what was pressed")
    nc = got["noClickTab"]
    if nc["rsa"] or nc["value"] != "tax":
        bad.append(f"'91-A' typed, a press with no click, then 'tax' and Tab: chose {nc['rsa']}, the box "
                   f"{nc['value']!r} -- the number read at the press outlived the words typed since")
    st = got["staleTab"]
    if st["rsa"] or st["value"] != "tax":
        bad.append(f"'91-A' typed, the panel drawn again with the focus kept in the box, then 'tax' and Tab: "
                   f"chose {st['rsa']}, the box {st['value']!r} -- the number read as the box was drawn anew "
                   "outlived it")
    a = _rsa_run(address="?rsa=91-a:4")
    sh, op = a["shut"], a["opened"]
    if sh["rsa"] != ["91-A:4"] or sh["cards"] != ["HB1"] or '<span class="badge">1</span>' not in sh["group"] \
            or op["line"] != f"Bills that change RSA 91-A:4, in {name} · Read the law · Clear":
        bad.append(f"?rsa=91-a:4 arrives with {sh['rsa']} listing {sh['cards']}, and the group "
                   f"opened says {op['line']!r}")
    assert not bad, "; ".join(bad[:6])
    return "ok", ("RSA 91-A chosen by the arrow keys and Return, 91-A:4 typed and from the address, "
                  "540 pressed and as 540:, each listing its bills under its name; 404 and 91 are "
                  "not chosen, and say why; Clear and an emptied box list them all; words left give "
                  "way to the chosen number; 194-G is chosen unnamed and unlinked; a number typed "
                  "whole is chosen on leaving, by Tab going on from the box or by ticking a status "
                  "none of whose bills change it; Clear and an offer pressed "
                  "with the mouse over the open list do what they say, the box focused only from the "
                  "keyboard")


@check("frontend", "the Laws Changed filter is decided for the term on the list: no box in the "
                   "bill requests, which have no text, and a law chosen elsewhere named there with "
                   "why it lists none; switching from the requests to a term draws it")
def _laws_changed_terms():
    """The review of 26 October 2026: in 2027 Bill Requests, "91-A" or "right
    to know" said "No bill request for 2027 changes RSA 91-A, Access to
    Governmental Records and Meetings." -- while no request carries the laws
    it changes, having no text, and two of them are plainly about it. And
    whether the filter was drawn was decided once, of the first term loaded,
    so a page opened on ?term=2027-requests had none in the term it was
    switched to. Held, over _rsa_fixture in node, the address naming the
    requests: no group there; the current term chosen, and the list drawn
    again while its bills are on their way, as a letter typed in the search
    box draws it, the group once they arrive (what is known of a term is
    asked again as its bills arrive: kept for the term alone, the answer
    given before they came hid the filter for the rest of the visit); RSA
    91-A chosen and the requests chosen again, the group drawn with its line,
    "A bill request has no text yet, so the laws it would change are not
    known.", no box and no "No bill request"; Clear takes it, and the group,
    away, the keyboard put on the head of the filter above it rather than
    left on nothing (the review of 26 October 2026: it fell to the page);
    All Terms draws the box, and a law no bill changes is "No bill
    across all terms changes ..."; and a term of bills none of which says
    the laws it changes (none on the site; the fixture's earlier term) says
    "Which laws these bills change is not known." under the law chosen."""
    got = _rsa_run(address="?term=2027-requests", mode="terms")
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    bad = []
    if got["reqArrive"]["label"] is not None:
        bad.append("the requests draw a Laws Changed filter, with nothing in them to find")
    if got["reqThenNow"]["label"] != "Laws Changed (RSA)":
        bad.append("arrived on the requests and switched to the current term, the list drawn again "
                   "while its bills were on their way, there is no Laws Changed filter once they are "
                   "here")
    if got["nowChosen"]["rsa"] != ["91-A"]:
        bad.append(f"91-A and Return in the current term chose {got['nowChosen']['rsa']}")
    r = got["reqChosen"]
    why = "A bill request has no text yet, so the laws it would change are not known."
    if r["label"] != "Laws Changed (RSA)" or r["boxed"] or r["why"] != why \
            or r["line"] != "Bills that change RSA 91-A, Access to Governmental Records and Meetings · " \
                            "Read the law · Clear" or "No bill request" in r["group"] or r["cards"]:
        bad.append(f"RSA 91-A chosen, then the requests: the group {r['label']!r}, a box {r['boxed']}, "
                   f"saying {r['why']!r} and {r['line']!r}, listing {r['cards']}")
    rc = got["reqCleared"]
    if rc["rsa"] or rc["label"] is not None:
        bad.append(f"Clear in the requests left {rc['rsa']} and the group {rc['label']!r}")
    elif not rc["groups"] or rc["focus"] != "head:" + rc["groups"][-1]:
        bad.append(f"Clear in the requests took the group away and left the focus on {rc['focus']}, not "
                   f"on the head of the filter above it ({rc['groups'][-1:]})")
    a = got["all404"]
    if not got["allOpen"]["boxed"] or a["note"] != "No bill across all terms changes RSA 404, Dog Licensing.":
        bad.append(f"All Terms: a box {got['allOpen']['boxed']}, and 404 says {a['note']!r}")
    o = got["oldChosen"]
    if o["boxed"] or o["why"] != "Which laws these bills change is not known." or o["rsa"] != ["91-A"]:
        bad.append(f"RSA 91-A chosen, then a term whose bills say no law: a box {o['boxed']}, saying "
                   f"{o['why']!r}, chosen {o['rsa']}")
    assert not bad, "; ".join(bad)
    return "ok", ("no box in the requests, a law chosen there named with why it lists none; the "
                  "filter back on switching to a term; across all terms said so")


@check("frontend", "the Laws Changed filter fetches the Laws pages' list of chapters only when its "
                   "group is opened, and once, and their sections' headings only when a colon is "
                   "typed; without the list it still offers and filters by number, says in words "
                   "that names cannot be looked up, and asks again when the group is opened again")
def _laws_changed_names_fetch():
    """laws/chapters.json is 150 KB, and /bills is kept light on a phone (the
    phone-speed work of 25 October 2026: a filter group is drawn only when it
    is open). Held, over _rsa_fixture in node: the list drawn, a filter ticked
    and drawn again, nothing fetched while the group is shut; opened, the
    file is fetched, once, however much is typed after; laws/headings.json,
    1.1 MB, not fetched for anything typed until a colon, then once. Words
    typed before the names arrive say "Looking up the laws' names…", and
    once they are here are offered, the status line counting them, and the
    caret where it was in the box drawn anew (the review of 26 October 2026:
    "right to kn" became "ZZright to kn" in Chromium) -- unless the panel was
    shut meanwhile, when nothing is drawn. With the file not there (a 404):
    "91" still offers RSA 91-A and its two bills, without a name; "540:" its
    sections by number; words say "The laws' names could not be loaded. Type
    a chapter's number, like 91-A."; and "91-A" and Return lists HB 1 and HB 4
    under "Bills that change RSA 91-A", with its link and Clear. And a file
    that fails once is not asked for again on every letter typed, but is when
    the group is shut and opened again, and its names are then offered (the
    review: one failure kept them away until a reload); the headings the
    same, the sections offered by number meanwhile."""
    got = _rsa_run()
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    bad = []
    if got["shut"]["asked"] or got["others"]["asked"]:
        bad.append(f"laws/chapters.json was fetched {got['others']['asked']} time(s) with the group "
                   "shut")
    if got["opened"]["asked"] != 1 or got["unnamed"]["asked"] != 1:
        bad.append(f"laws/chapters.json was fetched {got['opened']['asked']} time(s) when the group "
                   f"opened and {got['unnamed']['asked']} by the end, not once")
    if got["t:21"]["heads"] or got["t:540:"]["heads"] != 1 or got["unnamed"]["heads"] != 1:
        bad.append(f"laws/headings.json was fetched {got['t:21']['heads']} time(s) before a colon was "
                   f"typed, {got['t:540:']['heads']} once one was and {got['unnamed']['heads']} by the end")
    w = _rsa_run(mode="slow")
    wa, ar = w["waiting"], w["arrived"]
    a91 = ["RSA 91-A, Access to Governmental Records and Meetings 2 bills"]
    if wa["offers"] or wa["note"] != "Looking up the laws’ names…" or _offered(ar) != a91 \
            or ar["note"] or ar["say"] != "1 law matches; the down arrow chooses it." or ar["asked"] != 1:
        bad.append(f"words typed before the names arrive say {wa['note']!r} offering "
                   f"{_offered(wa)}; once they arrive {_offered(ar)}, {ar['note']!r}, the status line "
                   f"{ar['say']!r}")
    if ar["focus"] != "box" or ar["caret"] != [11, 11] or ar["value"] != "right to kn":
        bad.append(f"the names arriving under 'right to kn' left the box reading {ar['value']!r}, the "
                   f"focus {ar['focus']}, the caret at {ar['caret']}, not after the last letter")
    z = _rsa_run(mode="slowshut")
    if z["redrawn"]:
        bad.append(f"the names arriving with the panel shut drew it {z['redrawn']} time(s)")
    f = _rsa_run(chapters=False)
    if _offered(f["t:91"]) != ["RSA 91-A 2 bills"] \
            or _offered(f["t:540:"]) != ["RSA 540:1 1 bill", "RSA 540:2 1 bill", "RSA 540 2 bills"]:
        bad.append(f"without the names 91 offers {_offered(f['t:91'])} and 540: {_offered(f['t:540:'])}, "
                   "not RSA 91-A and 540's sections by number")
    if f["t:right to know"]["note"] != ("The laws’ names could not be loaded. Type a "
                                        "chapter’s number, like 91-A."):
        bad.append(f"without the names, words say {f['t:right to know']['note']!r}")
    c = f["chosen"]
    if c["rsa"] != ["91-A"] or c["cards"] != ["HB1", "HB4"] \
            or c["line"] != "Bills that change RSA 91-A · Read the law · Clear":
        bad.append(f"without the names 91, down and Return chose {c['rsa']} listing {c['cards']} "
                   f"under {c['line']!r}")
    o = _rsa_run(mode="failonce")
    if o["failedAgain"]["asked"] != 1 or not o["failedAgain"]["note"].startswith("The laws’ names could not"):
        bad.append(f"a failed list was asked for {o['failedAgain']['asked']} time(s) as words were typed, "
                   f"saying {o['failedAgain']['note']!r}")
    if o["retried"]["asked"] != 2 or _offered(o["retried"]) != a91:
        bad.append(f"the group shut and opened again after a failure: the list asked for "
                   f"{o['retried']['asked']} time(s), 'right to know' offering {_offered(o['retried'])}")
    hf, hr = o["headsFailedAgain"], o["headsRetried"]
    if hf["heads"] != 1 or _offered(o["headsFailed"])[0] != "RSA 540:1 1 bill" or hr["heads"] != 2 \
            or _offered(hr)[0] != "RSA 540:1, Applicability 1 bill":
        bad.append(f"the headings failing once: asked {hf['heads']} time(s) as more was typed, offering "
                   f"{_offered(o['headsFailed'])}; the group opened again, asked {hr['heads']} time(s), "
                   f"offering {_offered(hr)}")
    assert not bad, "; ".join(bad)
    return "ok", ("nothing fetched until the group opens, then laws/chapters.json once, the headings "
                  "once a colon is typed; words typed before the names arrive are offered when they "
                  "do, the caret kept; without them RSA 91-A is offered and chosen by number, and a "
                  "failure is asked again when the group opens again")


# A member's or a committee's Bills tab as billPane draws it, in node: the
# rows from rows.json, and the select set to each value in turn.
_BILL_STATUS_SELECT_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({billPane, setPage: (p) => { PAGE = p; }})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const rows = JSON.parse(fs.readFileSync("./rows.json", "utf8"));
const out = {};
try {
  for (const st of ["", "Passed", "In Progress", "Died", "Tabled"]) {
    s.setPage({kind: "member", status: st, terms: [], term: "", data: null});
    out[st || "Any"] = s.billPane(rows.slice(), n => n + " bills");
  }
} catch (e) { out.threw = e.constructor.name + ": " + e.message; }
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("frontend", "a member's or a committee's Bill status select offers the bill search's "
                   "categories, in its order, only those a bill of the tab is in, each painted "
                   "in its chip's colours, and filters by them")
def _bill_status_select_categories():
    """The person, 8 October 2026, "Same categories": the "Bill status"
    dropdown on a committee's and a member's page (app.js billPane, its rows
    the index's or build_committees' chip and kind) offers what the search's
    Status filter does -- the same categories, in the same order, hidden at
    zero -- painted as in the search. It offered each chip's word, Became
    Law and Adopted by the House and every stage a choice of its own. Run in
    node over a tab of eight bills with no bill tabled or vetoed. Held: Any
    and then In Progress, Passed, Interim Study, Died and Withdrawn, Tabled
    and Vetoed not offered; each option carrying its category's chip class
    (CATCLASS, as the sidebar paints it) and Any none; each reading its
    category and how many of the tab's bills are in it, "Passed (2)", as the
    sidebar gives each its number (23 October 2026: it read the category
    alone), and Any no number, as the Votes tab's; Passed listing the law
    and the adopted resolution, each card keeping its own word; In Progress
    the bill in committee and the one awaiting the governor; Died the bill
    killed and the veto that stood; the select itself in the chosen
    category's class and in none on Any; and Tabled, chosen on another tab
    (PAGE.status is the page's), still offered in its place and selected,
    at "(0)", with an empty list, so the select says why the list is empty. And in
    app.css: each class the select can carry painted with its chip's own
    ground and ink, and Any's option in the page's."""
    def row(bid, kind, chip, status=None):
        return {"id": bid, "n": re.sub(r"^([A-Z]+)", r"\1 ", bid), "title": "a bill",
                "kind": kind, "status": status or chip, "chip": chip, "committees": [],
                "committee": "", "topic": "", "sponsor": "", "term": "2025-2026",
                "year": 2026, "passage": "", "votedays": [], "nrc": 0, "last_action": ""}
    rows = [row("HB1", "law", "Became Law", "Signed into law"),
            row("HR2", "adopted", "Adopted by the House"),
            row("HB3", "active", "In committee"),
            row("SB4", "active", "Passed, awaiting the governor"),
            row("HB5", "study", "Interim Study", "Referred for interim study"),
            row("HB6", "done", "Died", "Killed"),
            row("HB7", "veto", "Died", "Vetoed, override failed"),
            row("HB8", "done", "Withdrawn")]
    got = _node_app(_BILL_STATUS_SELECT_HARNESS, {"rows.json": json.dumps(rows)})
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    assert "threw" not in got, f"billPane threw {got['threw']}"
    cls_of = {"In Progress": "s-active", "Passed": "s-law", "Tabled": "s-table",
              "Interim Study": "s-study", "Died": "s-done", "Withdrawn": "s-done",
              "Vetoed": "s-veto"}

    def read(html):
        sel = re.search(r'<select data-pf="status"([^>]*)>(.*?)</select>', html, re.S)
        opts = []
        for m in re.finditer(r'<option value="([^"]*)"([^>]*)>([^<]*)</option>',
                             sel.group(2) if sel else ""):
            c = re.search(r'class="([^"]*)"', m.group(2))
            opts.append((m.group(1), c.group(1) if c else "", "selected" in m.group(2),
                         m.group(3).strip()))
        own = re.search(r'class="([^"]*)"', sel.group(1)) if sel else None
        cards = re.findall(r'<article class="card[^"]*" data-id="([^"]*)"', html)
        chips = re.findall(r'<span class="chip chip-m cstat ?[^"]*">([^<]*)</span>', html)
        return {"opts": opts, "own": own.group(1) if own else "", "cards": cards,
                "chips": chips, "note": re.search(r'<p class="src">(\d+) bills</p>', html)}
    bad = []
    a = read(got["Any"])
    want = ["", "In Progress", "Passed", "Interim Study", "Died", "Withdrawn"]
    if [o[0] for o in a["opts"]] != want:
        bad.append(f"Any offers {[o[0] for o in a['opts']]}, not {want}: not the search's "
                   "categories, in its order, hidden at zero")
    n_of = {"In Progress": 2, "Passed": 2, "Interim Study": 1, "Died": 2, "Withdrawn": 1}
    for v, c, _s, text in a["opts"]:
        if v and (c != cls_of.get(v) or text != f"{v} ({n_of.get(v)})"):
            bad.append(f"the option {v!r} reads {text!r} in {c!r}, not {v} ({n_of.get(v)}) in "
                       f"{cls_of.get(v)!r}")
        if not v and (c or text != "Any"):
            bad.append(f"the first option is {text!r} in {c!r}, not Any in the page's ink")
    if a["own"]:
        bad.append(f"the select on Any is painted {a['own']!r}")
    if len(a["cards"]) != len(rows) or not a["note"] or a["note"].group(1) != str(len(rows)):
        bad.append(f"Any lists {a['cards']}")
    # A card's chip is the short word since 10 October 2026 (D18).
    for st, ids, chips in (("Passed", ["HB1", "HR2"], ["Became Law", "Adopted by House"]),
                           ("In Progress", ["HB3", "SB4"],
                            ["In Committee", "To the Governor"]),
                           ("Died", ["HB6", "HB7"], ["Died", "Died"]),
                           ("Tabled", [], [])):
        r = read(got[st])
        if r["cards"] != ids:
            bad.append(f"{st} lists {r['cards']}, not {ids}")
        if r["chips"] != chips:
            bad.append(f"under {st} the cards say {r['chips']}, not their own words {chips}")
        if r["own"] != cls_of[st]:
            bad.append(f"the select on {st} is painted {r['own']!r}, not {cls_of[st]!r}")
        chosen = [o[0] for o in r["opts"] if o[2]]
        if chosen != [st]:
            bad.append(f"the select on {st} has {chosen} selected")
        if not r["note"] or r["note"].group(1) != str(len(ids)):
            bad.append(f"the note under {st} says {r['note'] and r['note'].group(0)!r}")
    tabled = read(got["Tabled"])["opts"]
    t = [o[0] for o in tabled]
    if t != ["", "In Progress", "Passed", "Tabled", "Interim Study", "Died", "Withdrawn"]:
        bad.append(f"Tabled chosen on another tab, with no bill tabled here, offers {t}: not "
                   "in its place, so the select cannot say why the list is empty")
    if [o[3] for o in tabled if o[0] == "Tabled"] != ["Tabled (0)"]:
        bad.append(f"Tabled chosen elsewhere reads {[o[3] for o in tabled if o[0] == 'Tabled']}, "
                   "not 'Tabled (0)'")
    css = re.sub(r"/\*.*?\*/", "", _source("src/pages/app.css"),
                 flags=re.S)
    rules = {sel_.strip(): body for sel_, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)}
    for c in sorted(set(cls_of.values())):
        chip = rules.get(f".{c}", "")
        mine = rules.get(f".bfilt select.{c}", "")
        decl = lambda b: sorted(x.strip().replace(" ", "") for x in b.split(";") if x.strip())
        if not chip or decl(mine) != decl(chip):
            bad.append(f".bfilt select.{c} is {mine!r}, not its chip's {chip!r}")
    plain = rules.get(".bfilt option:not([class])", "").replace(" ", "")
    if "background:var(--paper)" not in plain or "color:var(--ink)" not in plain:
        bad.append(f"Any's option is not in the page's ground and ink: {plain!r}")
    assert not bad, "; ".join(bad[:8])
    return "ok", ("the select offers the search's categories a bill of the tab is in, each in "
                  "its chip's class with its count, filters by them with each card keeping its "
                  "word, is painted by its choice, and keeps a choice made elsewhere at none")


# The Votes tabs' words and keys (the audit of 25 October 2026, S1), in node:
# a member's Find box, a ring's legend, the full record and a card with no
# names.
_VOTES_WORDS_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
globalThis.fetch = async () => ({ok: true, status: 200, json: async () => ({H: [], S: []}),
  text: async () => "{}"});
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({renderMemberVotes, renderVotes, donut, fullRecord, fullOpen, IDX, LOADED,"
  + "   setRCX: v => { RCX = v; }, setPage: p => { PAGE = p; },"
  + "   setMeta: m => { META = Object.assign(META || {}, m); }})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const fx = JSON.parse(fs.readFileSync("./fx.json", "utf8"));
const out = {find: {}};
try {
  s.setRCX({});
  s.setMeta({terms: ["2025-2026"]});
  // The bills' index as the site writes it, a bill's own page title in `n`.
  s.IDX.length = 0; s.LOADED.add("2025-2026");
  fx.rows.forEach(r => { r.hayT = [r.id, r.n, r.title].join(" ").toLowerCase().replace(/-/g, " ");
                         r.hayC = ""; s.IDX.push(r); });
  for (const q of fx.finds) {
    s.setPage({kind: "member", terms: ["2025-2026"], term: "2025-2026", data: fx.member,
               vfilter: "", vside: "", vq: q, vopen: {}, vshow: 0});
    out.find[q] = (s.renderMemberVotes(fx.member).match(/<td class="d"/g) || []).length;
  }
  out.ring = s.donut("HB1", 0, fx.card);
  s.fullOpen.add("HB1|0");
  out.full = s.fullRecord("HB1", 0, fx.card);
  out.cards = s.renderVotes({id: "HB1"}, {rollcalls: fx.unnamed});
} catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + (e.stack || "").split("\n")[1]; }
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("frontend", "a member's Votes tab finds a bill by its page's own number (\"HB 282-FN\") or the "
                   "number alone; a roll call's legend keys each row by its party's colour; the full "
                   "record says Yes and No; a voice or division vote says it has no names in one line")
def _votes_words_and_keys():
    """The audit of 25 October 2026 (S1), approved by the owner:

    - On a legislator's Votes tab, typing "HB 282-FN" -- the bill page's own
      title -- or a bare "282" gave "0 of 591". A suffix (FN, A, LOCAL, L, in
      any run) is no part of the number a vote is filed under, and a number
      alone finds that number of any kind of bill, and not a number it is
      the start or the end of. Words are still words: "local" is not taken
      for a suffix.
    - The full voting record said "Republican Yea" under a legend that says
      "Republican -- Yes": Yes and No throughout.
    - The ring is green (Yes) and salmon (No), and the legend's swatches were
      the parties' red, blue and purple, keying nothing in the ring. The audit
      made each row's swatch its side's colour. THE OWNER REVERSED THAT on the
      walk of the release candidate (30 October 2026): "the roll call vote
      legend doesn't show as blue and red or purple by party; instead it
      colors them red and green by the yes or no vote, like division votes".
      Each row's swatch is its party's colour (PARTY_COLOR: R red, D blue, I
      and L purple), never the side's, and the side stays in words.
    - "Decided on a voice vote. There is no count and no record of how
      individual members voted", or a division's two sentences, on every such
      card under a head that names the kind of vote: one line, "No record of
      how each member voted."
    """
    vote = lambda n, b, q="": {"k": f"2026-H-{n}", "d": f"3/{n}/2026", "b": b, "y": "2026",
                               "q": q, "v": "Yea"}
    member = {"party_code": "D", "service": [{"b": "H"}],
              "votes": [vote(1, "HB282"), vote(2, "SB282"), vote(3, "HB2820"), vote(4, "HB28"),
                        vote(5, "HB1282", "Local option")]}
    # Matched as the bill search matches (the owner, 7 November 2026), over the index's rows.
    finds = {"HB 282-FN": 1, "HB 282": 1, "SB282": 1,
             # A bare number is a word to the bill search, as it is on /bills: SB 282, HB 282
             # and the HB 2820 whose number it begins (the owner, 7 November 2026).
             "282": 3, "HB 28": 1, "local": 1,
             "HB 999-FN": 0}
    rows = [{"id": b, "n": n, "title": t, "term": "2025-2026", "year": 2026}
            for b, n, t in (("HB282", "HB 282-FN", "relative to a thing"),
                            ("SB282", "SB 282", "relative to another"),
                            ("HB2820", "HB 2820", "relative to a third"),
                            ("HB28", "HB 28", "relative to a fourth"),
                            ("HB1282", "HB 1282-L", "the local option program"))]
    m = lambda i, p, v: {"n": f"Rep. M{i} ({p})", "s": f"m{i}", "p": p, "v": v}
    card = {"yeas": 3, "nays": 4, "passed": False, "body": "H", "date": "2026-03-01",
            "tally": {"R": {"Yea": 2, "Nay": 1}, "D": {"Nay": 3}, "I": {"Yea": 1}},
            "members": [m(1, "R", "Yea"), m(2, "R", "Yea"), m(3, "R", "Nay"), m(4, "D", "Nay"),
                        m(5, "D", "Nay"), m(6, "D", "Nay"), m(7, "I", "Yea")]}
    unnamed = [{"question": "Ought to Pass", "date": "2026-03-01", "body": "H", "vote_kind": "VV",
                "passed": True},
               {"question": "Ought to Pass", "date": "2026-03-02", "body": "H", "vote_kind": "DV",
                "yeas": 200, "nays": 150, "passed": True},
               {"question": "Ought to Pass", "date": "2026-03-03", "body": "S", "vote_kind": "DV",
                "passed": False}]
    got = _node_app(_VOTES_WORDS_HARNESS, {"fx.json": json.dumps(
        {"member": member, "finds": list(finds), "card": card, "unnamed": unnamed,
         "rows": rows})})
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    assert "threw" not in got, f"the Votes tabs threw {got['threw']}"
    bad = [f"Find {q!r} lists {got['find'].get(q)} of the member's votes, not {n}"
           for q, n in finds.items() if got["find"].get(q) != n]
    rows = re.findall(r'<span class="sw" style="background:([^"]*)"></span>\s*<span>([^<]*?) — (Yes|No)',
                      got["ring"])
    if len(rows) != 4:
        bad.append(f"the ring's legend has {len(rows)} party rows, not 4: {rows}")
    party_bg = {"Republican": "var(--rep)", "Democrat": "var(--dem)", "Independent": "var(--ind)"}
    for bg, party, side in rows:
        if bg != party_bg.get(party):
            bad.append(f"{party} — {side} is keyed {bg}, not its party's colour {party_bg.get(party)}")
    if {r[1] for r in rows} != {"Republican", "Democrat", "Independent"}:
        bad.append(f"the legend no longer names the parties in words: {rows}")
    heads = re.findall(r"<h3>([^<]*)</h3>", got["full"])
    if [h for h in heads if re.search(r"\b(?:Yea|Nay)\b", h)] or \
            "Republican Yes — 2" not in heads or "Democrat No — 3" not in heads:
        bad.append(f"the full record's columns are not headed Yes and No: {heads}")
    notes = re.findall(r'<p class="note"[^>]*>([^<]*)</p>', got["cards"])
    if notes.count("No record of how each member voted.") != 3 or \
            re.search(r"Decided on a|individual members|total count", got["cards"]):
        bad.append(f"a voice or division vote's card does not say it has no names in the one "
                   f"line: {notes}")
    assert not bad, "; ".join(bad[:6])
    return "ok", (f"{len(finds)} searches find what they name, suffix or none; four legend rows "
                  "keyed by party; Yes and No in the full record; one line on three unnamed votes")


# A member's Votes tab, searched as the bill search is (the owner, 7 November
# 2026), in node: the bills' index set by hand, then each way of asking.
_VOTES_SEARCH_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
globalThis.fetch = async () => ({ok: false, status: 404, text: async () => "", json: async () => null});
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({renderMemberVotes, voteAddress, voteAddressRead, matches, IDX, LOADED, landingTerm,"
  + "   setTab: n => { PAGE_TAB = n; },"
  + "   setRCX: v => { RCX = v; }, setPage: p => { PAGE = p; }, getPage: () => PAGE,"
  + "   setQuery: q => { query = q; }, setTerm: t => { term = t; },"
  + "   setMeta: m => { META = Object.assign(META || {}, m); }})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const fx = JSON.parse(fs.readFileSync("./fx.json", "utf8"));
const norm = x => String(x || "").toLowerCase().replace(/-/g, " ");
s.IDX.length = 0;
fx.rows.forEach(r => { r.hayT = norm([r.id, r.n, r.title].join(" ")); r.hayC = ""; s.IDX.push(r); });
s.setRCX({});
s.setMeta({terms: ["2025-2026", "2023-2024"]});
["2025-2026", "2023-2024"].forEach(t => s.LOADED.add(t));
const out = {}, fake = {u: null};
globalThis.history = {state: null, pushState() {}, replaceState(a, b, u) { fake.u = u; globalThis.location.search = (u.split("?")[1] ? "?" + u.split("?")[1] : ""); }};
const page = extra => s.setPage(Object.assign({kind: "member", terms: ["2025-2026", "2023-2024"],
  term: "2025-2026", data: fx.member, vfilter: "", vside: "", vq: "", vtopic: "", vall: false,
  vopen: {}, vshow: 0}, extra));
const bills = h => [...new Set([...h.matchAll(/bill\/(\d{4})\/([a-z]+\d+)(?:\.html)?(?=[\"#?])/g)].map(m => m[2].toUpperCase()))].sort();
try {
  for (const [k, extra] of Object.entries(fx.cases)) {
    page(extra); const h = s.renderMemberVotes(fx.member);
    out[k] = {bills: bills(h), rows: (h.match(/<td class="d"/g) || []).length,
              count: (/id="vcount">\s*([\d,]+ of [\d,]+)/.exec(h) || [])[1] || "",
              empty: /No recorded vote matches/.test(h), clear: /data-vclear/.test(h),
              scope: /data-vall=/.test(h)};
  }
  // What /bills lists for the same words, from the same functions.
  s.setTerm("2025-2026"); s.setQuery("marijuana");
  out.billsList = s.IDX.filter(b => s.matches(b)).map(b => b.id).sort();
  // The address.
  page({vq: "housing", vtopic: "Housing", vall: true}); s.voteAddress(); out.addr = fake.u;
  page({}); s.voteAddress(); out.addrBare = fake.u;
  globalThis.location.search = "?q=rent%20a&topic=Education%20-%20General&term=all";
  page({}); s.voteAddressRead(); const p = s.getPage();
  out.read = [p.vq, p.vtopic, p.vall];
  globalThis.location.search = "";
  // A member-elect: the requests term first. The Votes tab's address opens on
  // the newest term with votes, every term still answers there, and the
  // requests term alone says no votes (dry run 16, 10 November 2026).
  s.setMeta({requests: {term: "2027-2028", year: 2027}});
  const ts = ["2027-2028", "2025-2026", "2023-2024"];
  s.setTab(2); out.landVotes = s.landingTerm("member", ts);
  s.setTab(0); out.landBills = s.landingTerm("member", ts);
  page({terms: ts, term: "2027-2028", vall: true});
  out.reqAll = (s.renderMemberVotes(fx.member).match(/<td class="d"/g) || []).length;
  page({terms: ts, term: "2027-2028"});
  out.reqNone = /No votes: a request/.test(s.renderMemberVotes(fx.member));
  s.setMeta({requests: null});
} catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + (e.stack || "").split("\n")[1]; }
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("frontend", "a member's Votes tab is searched by the bill search's own matcher (a number, "
                   "words and their synonyms), filtered by the bill search's topics, combined with "
                   "the other filters, scoped to the term or every term, kept in the address, and "
                   "says plainly when nothing matches")
def _member_votes_search():
    """The owner, 7 November 2026: "a search box: a bill number or words
    ('marijuana', 'affordable housing') ... with the bill search's own
    matching, never a second matcher" and "a topic filter using the site's
    existing broad topic categories", on a legislator's Votes tab; the term
    shown, "every term" one click away; the address keeps the search.

    It fails if the tab matches by a test of its own (it must list exactly
    the bills /bills lists for the same words -- a vote on a bill the title
    of which says "cannabis" is found by "marijuana" because the bill search's
    synonyms say so); if "HB 1" finds HB 10 or misses HB 1; if the topic
    filter, the vote and side filters and the words do not narrow together; if
    the term shown is not the scope until every term is asked for; if the
    address does not carry ?q=, ?topic= and ?term=all both ways; or if an
    empty result is not said in words with a way to clear it."""
    vote = lambda n, b, y, v="Yea": {"k": f"{y}-H-{n}", "d": f"3/{n}/{y}", "b": b, "y": str(y),
                                     "q": "Ought to Pass", "v": v}
    rows = [{"id": b, "n": re.sub(r"^([A-Z]+)", r"\1 ", b), "title": t, "term": term_,
             "year": int(term_[:4]), "topic": tp}
            for b, t, term_, tp in (
                ("HB1", "relative to the legalization of cannabis", "2025-2026", "Crimes"),
                ("HB10", "relative to affordable housing", "2025-2026", "Housing"),
                ("HB11", "relative to housing vouchers", "2025-2026", "Housing"),
                ("SB4", "relative to school lunches", "2025-2026", "Education"),
                ("HB1", "relative to the state budget", "2023-2024", "State Government"),
                ("HB77", "relative to affordable housing zoning", "2023-2024", "Housing"))]
    member = {"party_code": "D", "service": [{"b": "H"}],
              "votes": [vote(1, "HB1", 2025), vote(2, "HB10", 2025, "Nay"), vote(3, "HB11", 2025),
                        vote(4, "SB4", 2025), vote(5, "HB1", 2023), vote(6, "HB77", 2023)]}
    cases = {"all": {}, "number": {"vq": "HB 1"}, "synonym": {"vq": "marijuana"},
             "words": {"vq": "affordable housing"}, "topic": {"vtopic": "Housing"},
             "both": {"vtopic": "Housing", "vq": "vouchers"},
             "vote": {"vtopic": "Housing", "vfilter": "nay"},
             "none": {"vq": "zzzzqqq"}, "nonetopic": {"vtopic": "Education", "vq": "housing"},
             "everyone": {"vall": True}, "everynumber": {"vall": True, "vq": "HB 1"},
             "everywords": {"vall": True, "vq": "affordable housing"},
             "everytopic": {"vall": True, "vtopic": "Housing"}}
    got = _node_app(_VOTES_SEARCH_HARNESS, {"fx.json": json.dumps(
        {"member": member, "rows": rows, "cases": cases})})
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    assert "threw" not in got, f"the Votes tab threw {got['threw']}"
    want = {"all": ["HB1", "HB10", "HB11", "SB4"], "number": ["HB1"], "synonym": ["HB1"],
            "words": ["HB10"], "topic": ["HB10", "HB11"], "both": ["HB11"], "vote": ["HB10"],
            "none": [], "nonetopic": [],
            "everyone": ["HB1", "HB10", "HB11", "HB77", "SB4"], "everynumber": ["HB1"],
            "everywords": ["HB10", "HB77"], "everytopic": ["HB10", "HB11", "HB77"]}
    rows_n = {"all": 4, "number": 1, "synonym": 1, "words": 1, "topic": 2, "both": 1, "vote": 1,
              "none": 0, "nonetopic": 0, "everyone": 6, "everynumber": 2, "everywords": 2,
              "everytopic": 3}
    for k, w in want.items():
        assert got[k]["bills"] == w and got[k]["rows"] == rows_n[k], (
            f"{k}: {got[k]['bills']} / {got[k]['rows']} rows, not {w} / {rows_n[k]}")
    assert got["number"]["count"] == "1 of 4" and got["everyone"]["count"] == "6 of 6", (
        f"the count line is not 'n of m': {got['number']['count']}, {got['everyone']['count']}")
    assert got["synonym"]["bills"] == [b for b in got["billsList"] if b == "HB1"] \
        and got["billsList"] == ["HB1"], (
        "the tab does not list the bills /bills lists for the same words: "
        f"{got['synonym']['bills']} against {got['billsList']}")
    assert got["none"]["empty"] and got["none"]["clear"] and got["nonetopic"]["empty"] \
        and not got["all"]["empty"], "an empty result is not said in words, with a way to clear it"
    assert got["all"]["scope"], "a member of two terms has no way to ask for every term"
    assert got["addr"] and "q=housing" in got["addr"] and "topic=Housing" in got["addr"] \
        and "term=all" in got["addr"], f"the address does not keep the search: {got['addr']}"
    assert got["addrBare"] and "?" not in got["addrBare"], (
        f"a search cleared still leaves its address: {got['addrBare']}")
    assert got["read"] == ["rent a", "Education - General", True], (
        f"the address is not read back into the search: {got['read']}")
    assert got["landVotes"] == "2025-2026" and got["landBills"] == "2027-2028", (
        "a member-elect's Votes address does not open on the newest term with votes, or the "
        f"page itself no longer opens on the requests: {got['landVotes']}, {got['landBills']}")
    assert got["reqAll"] == 6 and got["reqNone"], (
        f"on the requests term, every term lists {got['reqAll']} of 6 votes, or the term alone "
        "does not say a request is not voted on")
    return "ok", ("a number, a synonym and words found by the bill search's own matcher, a topic "
                  "and the vote filter narrowing with them, the term or every term, the address "
                  "kept and read back, and an empty result said plainly; a member-elect's Votes "
                  "address opens on the newest term with votes")


# A member's two bills tabs and a committee's, as renderMemberBills and
# renderCommitteeBills draw them, in node: the index rows from rows.json,
# and the Bill status select set to each value in turn.
_BILL_STATUS_NOTE_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({renderMemberBills, renderCommitteeBills, IDX, setPage: (p) => { PAGE = p; }})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const fx = JSON.parse(fs.readFileSync("./fx.json", "utf8"));
s.IDX.length = 0; fx.rows.forEach(r => s.IDX.push(r));
const out = {};
const page = (kind, status, data) => s.setPage({kind, status, terms: ["2025-2026"],
  term: "2025-2026", data, vfilter: "", vparty: "", vshow: 0});
try {
  for (const st of ["", "Withdrawn", "Died"]) {
    page("member", st, fx.member);
    out["prime|" + st] = s.renderMemberBills(fx.member, true);
    out["co|" + st] = s.renderMemberBills(fx.member, false);
    for (const [k, c] of Object.entries(fx.committees)) {
      page("committee", st, c);
      out[k + "|" + st] = s.renderCommitteeBills(c);
    }
  }
} catch (e) { out.threw = e.constructor.name + ": " + e.message; }
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("frontend", "under a member's or a committee's Bill status select, the note says how "
                   "many of the tab's bills it lists -- 24 of 137 -- and never the bills listed "
                   "as the whole of the record")
def _bill_status_note_counts_the_tab():
    """The note under the Bill status select (app.js billPane, its sentence
    renderMemberBills' and renderCommitteeBills') was given the bills listed
    alone, so narrowed it said what was not true of the record: "24 bills
    referred to this committee in 2025-2026" under Passed beside a tab
    reading "Bills (137)", and -- once a choice made on one tab was kept on
    another, the person's "Same categories" of 8 October 2026 -- "0 bills
    co-sponsored in 2025-2026" under Withdrawn beside "Co-sponsored (37)"
    (the review of 8 October 2026). Narrowed it says "24 of 137 bills", as
    the search's count says "31 of 2,243 bills" once something narrows it;
    with Any, the tab's own count alone. Run in node over a member with three
    bills prime sponsored (one withdrawn) and two co-sponsored (none), a
    committee of five (two died), one of a single bill and one of 1,001 (all
    but one died), with Any, Withdrawn and Died chosen. Held: each note's
    leading words, the cards under it as many as it says it lists, and the
    thousands separated."""
    def row(bid, kind, chip, status=None):
        return {"id": bid, "n": re.sub(r"^([A-Z]+)", r"\1 ", bid), "title": "a bill",
                "kind": kind, "status": status or chip, "chip": chip, "committees": [],
                "committee": "", "topic": "", "sponsor": "", "term": "2025-2026",
                "year": 2026, "passage": "", "votedays": [], "nrc": 0, "last_action": ""}
    rows = [row("HB1", "law", "Became Law", "Signed into law"),
            row("HB2", "done", "Died", "Killed"),
            row("HB3", "done", "Withdrawn"),
            row("HB4", "law", "Became Law", "Signed into law"),
            row("HB5", "study", "Interim Study", "Referred for interim study"),
            row("SB6", "done", "Died", "Killed")] \
        + [row(f"HB{1000 + i}", "done", "Died", "Killed") for i in range(1000)]
    ref = lambda ids: [{"id": i, "term": "2025-2026"} for i in ids]
    member = {"sponsored": [{"bill": b, "term": "2025-2026", "prime": p}
                            for b, p in (("HB1", True), ("HB2", True), ("HB3", True),
                                         ("HB4", False), ("HB5", False))]}
    committees = {"five": {"bills": {"2025-2026": ref(["HB1", "HB2", "HB4", "HB5", "SB6"])}},
                  "one": {"bills": {"2025-2026": ref(["HB4"])}},
                  "big": {"bills": {"2025-2026": ref(["HB1"] + [f"HB{1000 + i}"
                                                                 for i in range(1000)])}}}
    got = _node_app(_BILL_STATUS_NOTE_HARNESS,
                    {"fx.json": json.dumps({"rows": rows, "member": member,
                                            "committees": committees})})
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    assert "threw" not in got, f"a bills tab threw {got['threw']}"
    want = {
        "prime|": ("3 bills prime sponsored in 2025\u20132026.", 3),
        "prime|Withdrawn": ("1 of 3 bills prime sponsored in 2025\u20132026.", 1),
        "prime|Died": ("1 of 3 bills prime sponsored in 2025\u20132026.", 1),
        "co|": ("2 bills co-sponsored in 2025\u20132026.", 2),
        "co|Withdrawn": ("0 of 2 bills co-sponsored in 2025\u20132026.", 0),
        "co|Died": ("0 of 2 bills co-sponsored in 2025\u20132026.", 0),
        "five|": ("5 bills referred to this committee in 2025\u20132026.", 5),
        "five|Withdrawn": ("0 of 5 bills referred to this committee in 2025\u20132026.", 0),
        "five|Died": ("2 of 5 bills referred to this committee in 2025\u20132026.", 2),
        "one|": ("1 bill referred to this committee in 2025\u20132026.", 1),
        "one|Died": ("0 of 1 bill referred to this committee in 2025\u20132026.", 0),
        "big|": ("1,001 bills referred to this committee in 2025\u20132026.", 1001),
        "big|Died": ("1,000 of 1,001 bills referred to this committee in 2025\u20132026.", 1000),
    }
    bad = []
    for k, (words, n) in want.items():
        html = got.get(k, "")
        note = re.search(r'<p class="src">(.*?)</p>', html, re.S)
        said = re.sub(r"\s+", " ", note.group(1)).strip() if note else None
        if not said or not said.startswith(words):
            bad.append(f"{k or 'Any'} says {said!r}, not {words!r}")
        cards = len(re.findall(r'<article class="card[^"]*" data-id=', html))
        if cards != n:
            bad.append(f"{k} lists {cards} cards under a note of {n}")
    assert not bad, "; ".join(bad[:8])
    return "ok", ("narrowed, the note says how many of the tab's bills it lists (1 of 3, 0 of 2, "
                  "1,000 of 1,001), and with Any the tab's own count, the cards as many")


@check("frontend", "the bill search always says how many bills it lists -- the term's whole "
                   "count with nothing narrowing it -- and its term picker says All Terms")
def _search_count_always():
    """The person, 8 October 2026: "The bill search should always show what
    number of bills are currently matching the search, even if there are no
    filters to show the total number of bills for that term, and it also
    prevents the best match from shifting when you search." The count was
    empty until something narrowed the list (A COUNT THAT SAYS N OF N SAYS
    NOTHING, app.js, now THE COUNT IS ALWAYS THERE); nothing held that, so
    nothing here is relaxed. Held, in node over _search_groups_fixture: the
    list with nothing narrowing it says "20 bills in the 2025–2026 term", a
    filter "4 of 20 bills in the 2025–2026 term", another term its own
    whole count, All Terms "23 bills across all terms", a number search "1
    matching in the 2025–2026 term", and the requests "3 bill requests for
    2027" -- they said nothing until something narrowed them, which the
    review of 8 October 2026 read as short of "always" -- and All Terms
    opened after the requests still "23 bills across all terms": the
    requests are no term's, and with them fetched All Terms listed them too,
    the always-said count then 302 over the real one. And the count, a live
    region, is not written again with the sentence it already says: render()
    runs for each hundred rows scrolled to, a card opened, the Sort, and the
    same sentence written over itself can be read out each time. And the
    picker's first option is "All Terms", in the Title Case of the terms
    under it."""
    fx = _search_groups_fixture()
    got = _node_app(_SEARCH_GROUPS_HARNESS, {"fixture.json": json.dumps(fx)})
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    assert "threw" not in got, f"the bill search threw {got['threw']}"
    want = {"start": "20 bills in the 2025–2026 term", "none": "20 bills in the 2025–2026 term",
            "progress": "4 of 20 bills in the 2025–2026 term",
            "older": "3 bills in the 2023–2024 term", "all": "23 bills across all terms",
            "requests": "3 bill requests for 2027", "allAfterRequests": "23 bills across all terms",
            "number": "1 matching in the 2025–2026 term"}
    bad = [f"{k}: {got[k]['count']!r}, not {v!r}" for k, v in want.items()
           if got[k]["count"] != v]
    for k, what in (("rewritesWhole", "with nothing narrowing the list"),
                    ("rewritesNarrowed", "with a filter ticked")):
        if got[k]:
            bad.append(f"the count is written {got[k]} more time(s) {what} with the sentence it "
                       "already says: a live region, read out again")
    opts = re.findall(r'<option value="([^"]*)">([^<]*)</option>', got["year"])
    if not opts or opts[0] != ("all", "All Terms"):
        bad.append(f"the term picker's first option is {opts[:1]}, not All Terms")
    assert not bad, "the count line says " + "; ".join(bad)
    return "ok", ("the count is the term's whole count with nothing narrowing it, n of N when "
                  "something does, across all terms on All Terms and for the requests, written "
                  "only when it changes, and the picker says All Terms")


@check("frontend", "the Sort sits before the count, under the term picker and exactly as wide "
                   "as it at every width and text size, and nothing else sets either's width")
def _sort_beside_count():
    """The person, 8 October 2026: "The best match/sort by should be to the
    left of the number of matching bills ... and the width of the dropdown
    boxes for the term selector and sort by should be the same size." The
    Sort followed the count, so the count arriving with the first letter
    typed pushed it along the row. Held, from the files: in bills.html the
    Sort's label and select come before the count, which comes before the
    search hint, in the one .qhint row; in app.css #year and #sort take one
    width from one custom property, defined once, and no other rule -- at any
    width, in any media query -- gives either a width of its own (the phone's
    #year{width:100%} was one); and the row holds the Sort at its start while
    the count, never wider than the Sort leaves it, wraps under itself beside
    it. Measured in Chrome on 8 October from 1366 to 360: both 172px, the
    Sort not moving when a search is typed, and no sideways scroll.
    THE ONE WIDTH IN REM, decided the same evening: "the selects' shared
    width in rem rather than px, so it grows with text-only zoom while both
    stay equal". This check held it in pixels until then, which is the line
    here that moved. Measured in Chrome with the browser's text at 24px: both
    258px at 1366, 768 and 375, and no sideways scroll. That left the count
    61px beside the Sort at 375, six lines tall, so where the room beside the
    Sort (--room) is under 8em the count takes a line of its own under it:
    held here as the count's cap, max(var(--room), calc((8em - var(--room))
    * N)), and the room defined from --pickw wherever the row is.
    And what the search read (#synhint) is not a line of its own whatever
    the room: from 1024px up "also matching: education, student, teacher,
    classroom" fits after the count, and as a line of its own it pushed the
    list down 28px at the first synonym typed (the review of 8 October).
    ON A PHONE, since 8 November 2026 (Alice): the box first, the term
    picker and the Sort beside each other in equal halves, the count on a
    line of its own and what the search read under it -- one wrapping row
    in which .qline and .qhint lay out nothing, held by _search_polish. What
    is held here still holds there: the two take one width, nothing gives
    either a width of its own, and the Sort comes before the count."""
    html = _source("src/pages/bills.html")
    css = _source("src/pages/app.css")
    bad = []
    hint = re.search(r'<div class="qhint">(.*?)</div>', html, re.S)
    if not hint:
        return "FAIL", "bills.html has no .qhint row"
    row = re.sub(r"<!--.*?-->", "", hint.group(1), flags=re.S)
    order = [m.group(0) for m in re.finditer(
        r'<label for="sort"|<select id="sort"|<span id="count"|<span id="synhint"', row)]
    if order != ['<label for="sort"', '<select id="sort"', '<span id="count"',
                 '<span id="synhint"']:
        bad.append(f"the .qhint row runs {order}: the Sort is not before the count")
    flat = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rules = re.findall(r"([^{}]+)\{([^{}]*)\}", flat)
    shared = [(sel_, body) for sel_, body in rules
              if re.fullmatch(r"\s*#year\s*,\s*#sort\s*", sel_)]
    if len(shared) != 1 or not re.search(r"(?:^|;)\s*width:var\(--pickw\)", shared[0][1]):
        bad.append(f"#year and #sort do not share one width rule: {shared}")
    defs = re.findall(r"--pickw\s*:\s*([^;}]+)", flat)
    if len(defs) != 1 or not re.fullmatch(r"\d+(?:\.\d+)?rem", defs[0].strip()):
        bad.append(f"--pickw is defined {defs}: once, in rem, is one width at every size that "
                   "grows with the reader's text")
    # The pages build_pages writes (body.pg) carry no term picker and no Sort,
    # so what their block says of #year sizes nothing on the bill search.
    for sel_, body in rules:
        if not re.search(r"#(?:year|sort)\b", sel_) or "body.pg" in sel_ \
                or re.fullmatch(r"\s*#year\s*,\s*#sort\s*", sel_):
            continue
        if re.search(r"(?:^|;)\s*(?:min-|max-)?width\s*:", body):
            bad.append(f"{sel_.strip()} sets a width of its own: {body.strip()[:80]}")
    q = [(sel_, body) for sel_, body in rules if sel_.strip() == ".qhint"]
    if not any("align-items:flex-start" in b.replace(" ", "") for _s, b in q):
        bad.append("the .qhint row does not hold the Sort at its top: a count that wraps "
                   "would move it")
    room = [re.search(r"--room\s*:\s*([^;]+)", b) for _s, b in q]
    room = [m.group(1).strip() for m in room if m]
    if not room or not all(re.fullmatch(r"calc\(100% - var\(--pickw\) - var\(--sp-\d+\)\)", r)
                           for r in room):
        bad.append(f"the room beside the Sort (--room) is not what the Sort leaves of its row: "
                   f"{room}")
    c = [body for sel_, body in rules if sel_.strip() == ".qhint #count"]
    held = [b for b in c if "max-width" in b]
    if not held or not all(
            re.search(r"max-width:max\(var\(--room\),\s*"
                      r"calc\(\(8em - var\(--room\)\) \* \d+\)\)", b)
            for b in held):
        bad.append("the count is not held to the room the Sort leaves it, or to a line of its "
                   f"own under 8em of room: {c}")
    h = [body for sel_, body in rules if sel_.strip() == ".qhint #synhint"]
    if not h or any(re.search(r"flex:\s*\d+\s+\d+\s+100%|flex-basis:\s*100%", b) for b in h):
        bad.append(f"what the search read is a line of its own at every width: {h}")
    assert not bad, "; ".join(bad)
    return "ok", ("the Sort comes before the count, #year and #sort share --pickw, in rem, and "
                  "nothing else sizes either, and the count keeps beside the Sort while 8em fits")


@check("frontend", "the district map draws its borders as chains, not one path per arc, so no bend "
       "leaves a white notch and no empty sliver ring is stroked as a speck")
def _map_borders_chained():
    """The owner, 8 November 2026: white dots along some district borders on
    the State House map. The county line (and the town and district meshes)
    were written as one subpath per arc, 456 for the county line alone: a butt
    cap has no join, so every bend where two arcs meet had a notch on its
    outside, through which the white casing under the line showed, and the
    source's zero-area sliver rings were stroked as black specks. chainD in
    map.js writes arcs that meet end to end as one chain (and drops a ring
    that encloses nothing); meshD and outlineD must use it. Read in map.js,
    and chainD is run in node on arcs that meet at a bend."""
    import subprocess
    js = _source("src/pages/map.js")
    bad = []
    for fn in ("meshD", "outlineD"):
        m = re.search(r"function " + fn + r"\(.*?\n(?=function |/\*)", js, re.S)
        assert m, f"map.js has no {fn}"
        if "chainD(" not in m.group(0) or 'map(p=>p[0]+" "+p[1]).join("L")' in m.group(0):
            bad.append(f"{fn} writes one subpath per arc, not chainD's chains")
    m = re.search(r"function chainD\(M,ids\)\{.*?\n  return d;\}", js, re.S)
    assert m, "map.js has no chainD"
    prog = (m.group(0) + """
const M={ARCS:[[[0,0],[10,0]],[[10,10],[10,0]],[[10,10],[20,10]],[[50,50],[51,51],[50,52],[50,50]]]};
console.log(chainD(M,[0,1,2,3]));""")
    r = subprocess.run(["node", "-e", prog], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60)
    if r.returncode or r.stdout.strip() != "M0 0L10 0L10 10L20 10":
        bad.append(f"chainD did not join arcs end to end and drop the empty ring: {r.stdout.strip()} {r.stderr[-200:]}")
    assert not bad, "; ".join(bad)
    return "ok", "meshD and outlineD write chains; chainD joins arcs at a bend and drops an empty ring"


# ---- the components, one answer in each language (9 October 2026) -----------------
#
# The component plan's C1 and C2, approved by the person on 9 October 2026:
# src/pages/components.py for the builders and src/pages/components.js,
# published as site/components.js and loaded in the head of every page, before
# app.js, find.js and any page's own script, with the same helpers under the
# same names, each in its language's case (date_words is dateWords). Two
# things keep them one. Every harness here that runs a page's script in node
# runs components.js first, as the page does (_with_components). And
# _components_agree runs every helper in both languages on each case in
# tests/components_cases.json and compares the answers byte for byte, which
# replaced the separate checks the person chip, clock() and the dates each had.



@check("frontend", "no harness hands node components.js on a command line, which Windows "
                   "refuses past 32,767 characters")
def _no_components_on_a_command_line():
    """components.js with its words passed 32,767 characters on 10 October
    2026, and three checks that ran it with `node -e` stopped with "The
    filename or extension is too long" -- an ERROR, not a finding, and only
    on Windows. They run it from a file (_node_file). A harness that builds
    its program from _components_js() and hands it to `-e` is caught here,
    before the file grows past the limit under it again."""
    bad = []
    for f in _suite_files():
        src = _source(f).split("\n")
        for i, line in enumerate(src):
            if re.search(r'\[\s*node\s*,\s*"-e"', line):
                before = "\n".join(src[max(0, i - 30):i])
                if "_components_js()" in before or "_with_components(" in before:
                    bad.append(f"{f.name}:{i + 1}")
    assert not bad, ("these run components.js with node -e, which Windows refuses once the "
                     "file is past 32,767 characters; use _node_file: " + ", ".join(bad))
    return "ok", "every harness that runs components.js runs it from a file"


@check("frontend", "a press on a bill card's head opens it wherever the card sits, a tab panel "
                   "with tabindex included, and a press on a control inside the head does not")
def _card_background_in_a_tab_panel():
    """THE CARDS THAT WOULD NOT OPEN (the owner's walk of dry run 8, 8 November
    2026). On a member's or a committee's page the cards sit in a tab panel
    with tabindex="0", and cardBackground's test for a control looked past the
    head to that panel, so only the title opened a card there. This runs the
    function from app.js in node on a small tree of fake elements."""
    node = shutil.which("node") or shutil.which("node.exe")
    js = Path("src/pages/app.js")
    if not node or not js.exists():
        return "skip", "node or app.js is not here"
    m = re.search(r"(?ms)^function cardBackground\(e\)\{.*?^\}", _source(js))
    assert m, "app.js has no function cardBackground(e){...}; this check reads it by that name"
    prog = r"""
function El(tag, cls, attrs, parent){this.tag=tag;this.cls=cls?cls.split(" "):[];
  this.attrs=attrs||{};this.parent=parent||null;}
// The selectors cardBackground uses: comma lists, tags, .class, [attr],
// :not(.class), and one descendant step.
function one(el, s){
  const m=/^([a-z]*)((?:\.[a-z-]+|:not\(\.[a-z-]+\)|\[[a-z-]+\])*)$/.exec(s);
  if(!m)throw new Error("selector this harness cannot read: "+s);
  if(m[1]&&el.tag!==m[1])return false;
  for(const p of m[2].match(/\.[a-z-]+|:not\(\.[a-z-]+\)|\[[a-z-]+\]/g)||[]){
    if(p[0]==="."){if(!el.cls.includes(p.slice(1)))return false;}
    else if(p[0]===":"){if(el.cls.includes(p.slice(6,-1)))return false;}
    else if(!(p.slice(1,-1) in el.attrs))return false;}
  return true;}
function matches(el, sel){return sel.split(",").some(alt=>{
  const parts=alt.trim().split(/\s+/);
  if(!one(el, parts[parts.length-1]))return false;
  if(parts.length===1)return true;
  for(let a=el.parent;a;a=a.parent)if(one(a, parts[0]))return true;
  return false;});}
El.prototype.closest=function(sel){for(let n=this;n;n=n.parent)if(matches(n,sel))return n;return null;};
El.prototype.contains=function(o){for(let n=o;n;n=n.parent)if(n===this)return true;return false;};
const window={getSelection:()=>""};
""" + m.group(0) + r"""
const pane=new El("div","pane",{tabindex:"0"});
const card=new El("article","card",{},pane);
const head=new El("div","chead",{},card);
const title=new El("button","ctitle",{},head);
head.querySelector=()=>title;
const meta=new El("div","cmeta",{},head);
const link=new El("a","",{href:"x"},meta);
const got={
  meta: cardBackground({target:meta,button:0})===title,
  head: cardBackground({target:head,button:0})===title,
  link: cardBackground({target:link,button:0})===null,
  right: cardBackground({target:meta,button:2})===null};
console.log(JSON.stringify(got));
"""
    r = _node_file(node, prog, capture_output=True, timeout=60)
    assert r.returncode == 0, f"cardBackground did not run in node: {(r.stderr or '')[-400:]}"
    got = json.loads(r.stdout.strip().splitlines()[-1])
    wrong = [k for k, ok in got.items() if not ok]
    assert not wrong, ("cardBackground in a tab panel with tabindex: wrong for "
                       + ", ".join(wrong) + " (meta and head should open the card; a link "
                       "inside the head and a right press should not)")
    return "ok", "a press on a card's head opens it inside a tabindex panel; its links still win"


@check("frontend", "a bill on a record page is a component: its card's number, a row's number or "
                   "a mention, never a link of its own")
def _bill_links_are_components():
    """THE BILL IN THREE SIZES (the component plan's step 4: "a check fails any bill link
    without a component class"). On the pages this branch draws -- a member's, a
    committee's, a bill's own and a session day -- every link to a bill's page is one of
    the three: a card's number (cnum), a row's (brnum) or a mention in running words
    (bmention), so a bill drawn some fourth way, with its own words for the number and the
    year, is caught where it is written. The Calendar's rows (cbn, the hubs' component)
    and the trail are the others' and are left to them."""
    allowed = {"cnum", "brnum", "bmention", "cbn"}
    shared, _base, _ran, _days = _fixture_site_shared()
    pages = {k: json.dumps(v, ensure_ascii=False) for k, v in _fixture_drawn().items()
             if k.split("#")[0].startswith(("legislator/", "committee/", "bill/"))}
    for p in sorted((shared / "site" / "session").rglob("*.html")):
        pages[p.relative_to(shared / "site").as_posix()] = p.read_text(encoding="utf-8")
    bad, n = [], 0
    for k, text in pages.items():
        text = text.replace('\\"', '"')
        for m in re.finditer(r'<a\b([^>]*)\bhref="(?:/)?bill/\d{4}/[a-z0-9]+(?:\.html)?"', text):
            n += 1
            cls = set((re.search(r'class="([^"]*)"', m.group(1)) or [None, ""])[1].split())
            if not cls & allowed:
                bad.append(f"{k}: {m.group(0)[:90]}")
    assert n, "no link to a bill was found on the fixture's record pages"
    assert not bad, f"{len(bad)} bill links that are no component: " + "; ".join(bad[:5])
    return "ok", f"{n:,} links to a bill on {len(pages)} record pages and tabs, each a component's"


@check("frontend", "a browser's translation leaves the record's own words alone: bill text, "
                   "statutes, the Constitution, the analysis, titles, docket lines and names")
def _record_not_translated():
    """The person, 23 October 2026, on Granite Record in other languages: "I
    wouldn't want the bill text to be mistranslated". The first step is to
    tell the translators already built into Chrome, Edge and Safari what not
    to touch -- translate="no", which they honour -- so a reader can translate
    the explanations around the record and still read the record as it was
    written: the bill's text, its amendments and its official analysis, the
    statutes and the Constitution, bill numbers and titles, the clerk's docket
    lines and the record's own motion wording, and people's names (Hope,
    Faith, Mark and June are names here, not words). A role or an office
    inside a name's chip is translated (translate="yes"). Every place that
    draws one of these is held here, and every chip drawn by hand."""
    want = {
        "src/pages/app.js": ['<div class="antext" translate="no">', '<div class="billbody" translate="no">',
                             '<p translate="no">${brackets(rsa(esc(x.text)))}</p>',
                             '<span class="w"><span translate="no">${esc(e.text||"")}</span>',
                             'In the record: <span translate="no">${esc(rc.mrec)}</span>',
                             '<div class="m" translate="no">${esc(m.n)}',
                             'line:`<span translate="no">${esc(b.title)}</span>`',
                             '<span class="docraw" translate="no">'],
        "src/pages/components.js": ['class="cnum" href="${esc(c.href)}" translate="no">',
                                    'class="ctitle" translate="no">', 'class="brtitle" translate="no">',
                                    'class="bmention" href="${esc(href)}" translate="no">',
                                    'class="psent" href="legislator/${esc(slug)}" translate="no">',
                                    '<span class="mchip p-${esc(code)}" translate="no">',
                                    '<i translate="yes">'],
        "src/pages/components.py": ['class="ctitle" translate="no">', 'class="brtitle" translate="no">',
                                    '<span class="mchip p-{esc(code)}" translate="no">',
                                    '<i translate="yes">'],
        "src/pages/build_rsa.py": ['<div class="rs-text" translate="no">'],
        "src/pages/constitution_tab.py": ['<div class="rs-text" translate="no">'],
        "src/pages/build_bill_pages.py": ['<p class="sx-title" translate="no">',
                                          '<div class="sx-docket" translate="no">'],
        "src/pages/chrome.py": ['<a class="brand" href="{to("index.html")}"{brand_cur} translate="no">'],
    }
    missing = [f"{f}: {w}" for f, ws in want.items()
               for w in ws if w not in Path(f).read_text(encoding="utf-8")]
    assert not missing, "record text a translator may now rewrite: " + "; ".join(missing)
    # A chip drawn by hand, anywhere a page is written, says it too. The
    # suite's own modules are not where a page is written: their chips are
    # samples a check feeds a page (they were in preflight.py, outside src/,
    # until 16 November 2026).
    loose = []
    for f in (sorted(Path("src").rglob("*.py")) + sorted(Path("src/pages").glob("*.js"))
              + sorted(Path("src").glob("*/inline/*.js"))):
        if _in_suite(f):
            continue
        for m in re.finditer(r'<span class="mchip[^"]*"(?:\s+[^>]*)?>', f.read_text(encoding="utf-8")):
            if 'translate="no"' not in m.group(0):
                loose.append(f"{f.name}: {m.group(0)[:60]}")
    assert not loose, "a person's chip a translator may rewrite: " + "; ".join(loose[:6])
    return "ok", (f"{sum(len(w) for w in want.values())} places and every hand-drawn chip "
                  "carry translate=\"no\"")


# The harness of _same_number_one_bill: app.js as the bill search, two bills
# of one number in two terms (rows.json, records.json beside it), the page
# opened at process.argv[2] ("?q=HB703", or with a term), All Terms chosen --
# unless that address names a bill after a "#", which it opens as it stands --
# and then the steps in process.argv[3]: "click:<year>" (a result's number,
# clicked as a reader clicks it), "back" (to the list), "forward:<year>" and
# "pop:<year>" (history, to the entry focusBill pushed for that year's bill),
# "search:<words>" (typed in the box, then Return), "gloss:<year>" (a click
# on the words of a glossary tooltip in the head of that year's bill, open)
# and "look:<year>" (nothing done: the bill the address opened). After each,
# what the page drew, the address it pushed, what it asked for, the bill
# whose Cite and Report row (#pageacts) is up and what the picker reads, as
# JSON.
_SAME_NUMBER_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
const rows = JSON.parse(fs.readFileSync("./rows.json", "utf8"));
const recs = JSON.parse(fs.readFileSync("./records.json", "utf8"));
const terms = [...new Set(rows.map(r => r.term))].sort().reverse();
const [, , start, steps] = process.argv;
// A start beginning "!" stays in the term its address names, and does not
// choose All Terms first: its other term's index is not yet asked for.
const keepTerm = start.startsWith("!");
const [qs, named = ""] = (keepTerm ? start.slice(1) : start).split("#");
location.pathname = "/bills"; location.search = qs; location.hash = named ? "#" + named : "";
location.href = "https://x/bills" + (keepTerm ? start.slice(1) : start);
// THE CITE AND REPORT ROW (focusActions): fetched from the bill's own page,
// which says whose it is, and put before the results; the stub's
// getElementById would otherwise hand back a row for any id, and none would
// ever be fetched.
let acts = null;
const byId = document.getElementById.bind(document);
document.getElementById = id => (id === "pageacts" ? acts : byId(id));
document.importNode = n => { const r = document.createElement("div"); r.bill = n.bill;
  r.remove = () => { if (acts === r) acts = null; }; return r; };
document.querySelector("#results").before = r => { acts = r; };
const docOn = {}, winOn = {};
document.addEventListener = (t, f) => (docOn[t] = docOn[t] || []).push(f);
globalThis.addEventListener = (t, f) => (winOn[t] = winOn[t] || []).push(f);
const pushed = [], entries = [];
// THE HISTORY AS A BROWSER KEEPS IT (the reviews of 7 November 2026): a
// stack of entries, each its address and state; a push drops what was ahead
// of it, a replace rewrites the entry stood on, and Back and Forward move
// along it and put that entry's address back, words and all.
// The entry the page loads at may hold a state already (a fourth argument):
// a list's words, as a reload keeps them.
const startState = process.argv[4] ? JSON.parse(process.argv[4]) : null;
history.state = startState;
const stack = [{u: location.pathname + location.search, s: startState}];
let at = 0;
const put = e => { const p = new URL(e.u, "https://x"); location.pathname = p.pathname;
  location.search = p.search; history.state = e.s; };
history.pushState = (s, _t, u) => { pushed.push(String(u));
  entries.push({u: String(u), s, from: location.pathname + location.search});
  stack.splice(at + 1); stack.push({u: String(u), s}); at = stack.length - 1; put(stack[at]); };
// A record held on its way (clickslow), let go by "release": the reader who
// opens a bill and goes Back before its record arrives.
const holding = new Set(), waiting = [];
// A replace sets the entry's state as well as its address, as a browser's
// does: the list keeps its words in its entry (focusBill).
history.replaceState = (s, _t, u) => { if (u) { const p = new URL(String(u), "https://x");
  location.pathname = p.pathname; location.search = p.search;
  stack[at] = {u: p.pathname + p.search, s}; } else stack[at] = {u: stack[at].u, s};
  history.state = s; };
// A term's index held on its way (holdidx), let go by "release": the picker
// turned with a bill open, and Back before the term's bills have arrived.
let holdIdx = false;
// ...or refused (failidx), until "okidx".
let failIdx = false;
let asked = [];
const ok = v => ({ok: true, status: 200, json: async () => v, text: async () =>
  typeof v === "string" ? v : JSON.stringify(v)});
globalThis.fetch = async u => { const p = new URL(u, "https://x").pathname.replace(/\.html$/, ""); asked.push(p);
  if (p === "/meta.json") return ok({terms, topics: [...new Set(rows.map(r => r.topic))].sort()});
  const m = /^\/idx\/(.+)\.json$/.exec(p);
  if (m && terms.includes(decodeURIComponent(m[1])) && failIdx) throw new TypeError("Failed to fetch");
  if (m && terms.includes(decodeURIComponent(m[1]))) {
    const idx = () => ok(rows.filter(r => r.term === decodeURIComponent(m[1])));
    return holdIdx ? new Promise(res => waiting.push(() => res(idx()))) : idx(); }
  if (p in recs) { const page = () => ok('<script type="application/json" id="gr-data">' + JSON.stringify(recs[p]) + "</script>");
    return holding.has(p) ? new Promise(res => waiting.push(() => res(page()))) : page(); }
  return {ok: false, status: 404, statusText: "Not Found", json: async () => { throw new Error(p + " 404"); },
          text: async () => ""}; };
globalThis.DOMParser = class { parseFromString(h) {
  const m = /id="gr-data">([\s\S]*?)<\/script>/.exec(h);
  const bill = m ? String(JSON.parse(m[1]).title).split("-")[0] : "";
  return {getElementById: id => (!m ? null : id === "gr-data" ? {textContent: m[1]}
                                 : id === "pageacts" ? {bill} : null),
          querySelector: () => null}; } };
const ticks = async n => { for (let i = 0; i < n; i++) await new Promise(r => setImmediate(r)); };
const errs = []; process.on("unhandledRejection", e => errs.push(String((e && e.message) || e)));
// A plain left click on a result's number: the target is the link, inside
// the card whose data-id is the bare number, as cardHtml draws them.
const click = year => { const row = rows.find(r => String(r.year) === year);
  const card = {dataset: {id: row.id}};
  const link = {getAttribute: k => (k === "href" ? `bill/${year}/${row.id.toLowerCase()}.html` : null),
                closest: s => (s === ".card" ? card : null), dataset: {}};
  const target = {dataset: {}, closest: s => (s === "a.cnum" ? link : null), getAttribute: () => null};
  (docOn.click || []).forEach(f => f({target, button: 0, metaKey: false, ctrlKey: false, shiftKey: false,
                                      altKey: false, preventDefault(){}, stopPropagation(){}})); };
// A click on the words of a glossary tooltip, as components.js arm() draws
// one in a bill's head: span.termpop inside span.term[data-term="FN"], in the
// open card; and on a card's Bill Text tab. Its closest() matches the
// selectors a handler asks of it -- tags, ids, classes, [attr] and
// [attr="v"], :not(), descendants and lists -- up the chain, as a browser's
// would; any other selector (a child or sibling combinator) matches nothing.
const node = (tag, cls, attrs, up) => { const n = {tag, cls, attrs, up};
  const ds = {}; for (const [k, v] of Object.entries(attrs))
    if (k.startsWith("data-")) ds[k.slice(5).replace(/-(\w)/g, (_, c) => c.toUpperCase())] = v;
  n.el = {tagName: tag.toUpperCase(), id: attrs.id || "", dataset: ds, textContent: "",
          getAttribute: k => (k in attrs ? attrs[k] : null), classList: {contains: c => cls.includes(c)},
          closest: s => { for (let p = n; p; p = p.up) if (s.split(",").some(x => under(p, x.trim()))) return p.el;
                          return null; }};
  return n; };
// "A B": the node is B, and some node above it is A.
function under(n, s) {
  const parts = s.split(/\s+/);
  if (parts.some(x => /[>+~]/.test(x)) || !fits(n, parts[parts.length - 1])) return false;
  let k = parts.length - 2;
  for (let p = n.up; p && k >= 0; p = p.up) if (fits(p, parts[k])) k--;
  return k < 0;
}
function fits(n, s) {
  const nots = []; s = s.replace(/:not\(([^)]*)\)/g, (_, x) => (nots.push(x), ""));
  if (!s || /[\s>+~:]/.test(s)) return false;
  const tag = /^[a-z][a-z0-9]*/i.exec(s);
  if (tag && tag[0].toLowerCase() !== n.tag) return false;
  for (const c of s.match(/\.[\w-]+/g) || []) if (!n.cls.includes(c.slice(1))) return false;
  for (const i of s.match(/#[\w-]+/g) || []) if (n.attrs.id !== i.slice(1)) return false;
  for (const a of s.match(/\[[^\]]+\]/g) || []) { const [k, v] = a.slice(1, -1).split("=");
    if (!(k in n.attrs) || (v !== undefined && n.attrs[k] !== v.replace(/^["']|["']$/g, ""))) return false; }
  return !nots.some(x => fits(n, x.trim()));
}
const gloss = year => { const row = rows.find(r => String(r.year) === year);
  const res = node("div", [], {id: "results"}, null);
  const card = node("div", ["card", "focus", "open"], {"data-id": row.id}, res);
  const h1 = node("h1", ["rh1"], {}, node("div", ["rhead"], {}, card));
  const pop = node("span", ["termpop"], {id: "gr-term-1", role: "tooltip"},
                   node("span", ["term"], {"data-term": "FN"}, h1));
  const target = node("b", [], {}, pop).el;
  (docOn.click || []).forEach(f => f({target, button: 0, detail: 1, metaKey: false, ctrlKey: false,
                                      shiftKey: false, altKey: false, preventDefault(){}, stopPropagation(){}})); };
// The open card's Bill Text tab (data-t="6"), as cardHtml draws its tabs.
const textTab = year => { const row = rows.find(r => String(r.year) === year);
  const card = node("div", ["card", "focus", "open"], {"data-id": row.id}, node("div", [], {id: "results"}, null));
  const target = node("button", ["tab"], {"data-t": "6", role: "tab"}, node("div", ["tabs"], {}, card)).el;
  (docOn.click || []).forEach(f => f({target, button: 0, detail: 1, metaKey: false, ctrlKey: false,
                                      shiftKey: false, altKey: false, preventDefault(){}, stopPropagation(){}})); };
(async () => {
  try { (0, eval)(fs.readFileSync("./page.js", "utf8")); }
  catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
  await ticks(40);
  const year = document.querySelector("#year");
  if (!named && !keepTerm) { year.value = "all"; year.fire("change", {target: year}); await ticks(60); }
  const init = {search: location.search, box: document.querySelector("#q").value, path: location.pathname};
  const out = [];
  for (const step of steps.split(",")) {
    asked = []; const was = pushed.length;
    const [what, y] = step.split(":");
    let replayed = null, backTo = null;
    if (what === "click") click(y);
    else if (what === "clickslow") { holding.add(`/bill/${y}/${rows.find(r => String(r.year) === y).id.toLowerCase()}`);
      click(y); }
    else if (what === "release") { holding.clear(); holdIdx = false; waiting.splice(0).forEach(f => f()); }
    else if (what === "holdidx") holdIdx = true;
    else if (what === "failidx") failIdx = true;
    else if (what === "okidx") failIdx = false;
    // A facet ticked (tick:topic=Insurance) and an order chosen (sort:recent),
    // each as its control's change event hands it over.
    else if (what === "tick") { const [f, v] = y.split("=");
      (docOn.change || []).forEach(g => g({target: {dataset: {f}, checked: true, value: v}})); }
    else if (what === "sort") { const so = document.querySelector("#sort"); so.value = y;
      so.fire("change", {target: so}); }
    else if (what === "back") { if (at > 0) at--; backTo = stack[at].u; put(stack[at]);
      (winOn.popstate || []).forEach(f => f({state: history.state})); }
    else if (what === "forward" || what === "pop") { const row = rows.find(r => String(r.year) === y);
      // The entry focusBill pushed for that bill, as the browser hands it back.
      const want = `/bill/${y}/${row.id.toLowerCase()}`;
      let k = stack.length - 1; while (k >= 0 && !stack[k].u.endsWith(want)) k--;
      replayed = k >= 0;
      if (k >= 0) { at = k; put(stack[k]); }
      else { location.pathname = want; history.state = {focus: row.id, term: row.term}; }
      (winOn.popstate || []).forEach(f => f({state: history.state})); }
    else if (what === "search") { const q = document.querySelector("#q"); q.value = y;
      q.fire("keydown", {key: "Enter"}); }
    // Words typed into the box and not run, and the term picker turned.
    // Typing waits as a reader does for the list to be drawn: the box draws
    // when the typing pauses (QWAIT_ALL, 400 ms).
    else if (what === "type") { const q = document.querySelector("#q"); q.value = y;
      q.fire("input", {target: q}); await new Promise(r => setTimeout(r, 450)); }
    // ...or not: the next step comes before the list is drawn again.
    else if (what === "typefast") { const q = document.querySelector("#q"); q.value = y;
      q.fire("input", {target: q}); }
    else if (what === "term") { year.value = y; year.fire("change", {target: year}); }
    else if (what === "gloss") gloss(y);
    else if (what === "text") textTab(y);
    await ticks(60);
    out.push({step, html: document.querySelector("#results").innerHTML, pushed: pushed.slice(was), asked,
              acts: acts && acts.bill || "", pick: year.value, replayed,
              search: location.search, box: document.querySelector("#q").value, backTo,
              path: location.pathname, count: String((document.querySelector("#count") || {}).textContent || ""),
              sort: (document.querySelector("#sort") || {}).value});
  }
  process.stdout.write("\n@@" + JSON.stringify({out, errs, init}));
})().catch(e => { console.log("RUN " + e.message); process.exit(1); });
"""


@check("frontend", "two bills of one number in two terms stay two: with All Terms chosen, the "
                   "bill opened -- by a click, Back or Forward, a search then Back, an address "
                   "-- is drawn whole as itself: its head, its record, its address, its Cite "
                   "row, in either order, whichever term's index arrived first; and a glossary "
                   "tooltip leaves the term alone")
def _same_number_one_bill():
    """THE OWNER'S HB 703 (6 November 2026). With All Terms chosen, HB 703
    is two bills: 2020's on prescription drugs (Rep. Edward Butler, Chapter 4
    of 2020) and 2025's on school meals (Rep. Hope Damon). The list knows a
    bill by its number, and with every term in the index the number named
    both: clicking the "(2020)" result opened 2025's bill at
    /bill/2025/hb703, and with 2019-2020's index arrived first the head was
    2025's over 2020's record, rail and summary, with no Testify -- what the
    owner saw. focusBill now opens the bill in the term of the link clicked,
    holding the reader's own until the bill is closed.

    THE SAME PAGE BY OTHER ROADS (that day's review). A search typed with
    the bill open, then Back to it, and an address naming the bill with a
    search it is not in, drew the first HB 703 of the index over the bill's
    record: render found the open bill by its number alone where the list
    did not hold it, and now finds it as yearOf does. The words of a
    glossary tooltip in its head set the term to "FN", since the term
    buttons' handler took anything with a data-term, and the tooltip's
    mark has one; it takes the buttons now. And history taken straight from
    one HB 703 to the other, by the Back button's list of pages, kept the
    first's Cite and Report row: focusActions kept it under the number, and
    keeps it under the year and number now. A record that arrived after the
    reader had gone Back was stored under the key the term then gave the
    number -- the other bill's -- so the other bill, opened next, drew its
    head over the first one's record: openBill keeps the key it asked with.
    And the Bill Text tab asked for the versions of the first bill of the
    number in the index, not the one drawn.

    Run in node over two rows of one number, each with its own record, each
    marked in what the head draws (the row's title and sponsor), what the
    body draws (the record's title, narrative and first event) and what its
    own page's Cite and Report row is: with All Terms chosen, a click on
    each result in both orders, from the newest term's index first and from
    the older's, Back to the list between them, and Forward to an entry
    pushed for the older bill; a search typed and Back to the bill; the
    address of each bill with a search for another; a click in a glossary
    tooltip in each bill's head; Back from one bill to the other, by the
    entry focusBill pushed; a record held until the reader has gone Back,
    then the other bill opened; and each bill's Bill Text tab. Every step
    must draw the bill opened and none of the other, its own Cite row, push
    that bill's own address where it was clicked and ask for that bill's
    record and versions only, never an index of no term; the tooltip must
    leave the picker as it was; Back and a search must draw the list, both
    bills in it where it names them, with no record and no Cite row over
    it."""
    built = _fixture_site_shared()[0] / "site"
    row0 = json.loads((built / "idx" / "2025-2026.json").read_text(encoding="utf-8"))[0]
    page = (built / "bill" / str(row0["year"]) / f"{row0['id'].lower()}.html").read_text(encoding="utf-8")
    rec0 = json.loads(re.search(r'id="gr-data">(.*?)</script>', page, re.S).group(1))
    marks = {"2025": "MEALS", "2020": "DRUG"}
    rows, recs = [], {}
    # Each its own topic, so two can be ticked and both bills still drawn.
    for year, term, n, sponsor, topic in (("2025", "2025-2026", "HB 703-FN-A-LOCAL", "Hope Damon", "Education"),
                                          ("2020", "2019-2020", "HB 703-FN", "Edward Butler", "Insurance")):
        mk = marks[year]
        rows.append(dict(row0, id="HB703", n=n, year=int(year), term=term,
                         title=f"{mk}-ROW title", sponsor=sponsor, topic=topic,
                         sponsor_label=f"Rep. {sponsor} {mk}-ROW"))
        events = [dict(e, text=f"{mk}-REC event {i}") for i, e in enumerate(rec0.get("events") or [])] \
            or [{"date": f"{year}-01-03", "text": f"{mk}-REC event 0", "routine": False}]
        # nver 2: each has an index of versions to ask for (hasVersionIndex)
        recs[f"/bill/{year}/hb703"] = dict(rec0, id="HB703", year=int(year), term=term,
                                           title=f"{mk}-REC title", narrative=f"{mk}-REC narrative",
                                           events=events, nver=2)
    files = {"rows.json": json.dumps(rows), "records.json": json.dumps(recs)}
    terms = {r["term"] for r in rows}
    plans = (("?q=HB703", "click:2020,back,click:2025"),
             ("?q=HB703", "click:2025,back,click:2020,back,forward:2020"),
             ("?term=2019-2020&q=HB703", "click:2025,back,click:2020"),
             # A search typed with the bill open, then Back to the bill: the
             # bill is not in the list the search drew (the review of 6
             # November 2026, which found the owner's page this way).
             ("?q=HB703", "click:2020,search:HB1,pop:2020"),
             ("?term=2019-2020&q=HB703", "click:2025,search:HB1,pop:2025"),
             # An address naming the bill, and a search it is not in.
             ("?q=HB1&term=all#2020/HB703", "look:2020"),
             ("?q=HB1&term=all#2025/HB703", "look:2025"),
             # The words of a glossary tooltip in the open bill's head.
             ("?q=HB703", "click:2020,gloss:2020,back,click:2025,gloss:2025"),
             # History taken straight from one to the other, as the Back
             # button's list of pages takes it.
             ("?q=HB703", "click:2025,search:HB703,click:2020,pop:2025"),
             ("?term=2019-2020&q=HB703", "click:2020,search:HB703,click:2025,pop:2020"),
             # A record that arrives after the reader went Back, then the
             # other bill opened: the owner's page on a slow connection (the
             # reviews of 6 November 2026).
             ("?q=HB703", "clickslow:2020,back,release,click:2025"),
             ("?term=2019-2020&q=HB703", "clickslow:2025,back,release,click:2020"),
             # The Bill Text tab asks for the open bill's versions.
             ("?q=HB703", "click:2020,text:2020,back,click:2025,text:2025"),
             ("?term=2019-2020&q=HB703", "click:2025,text:2025"),
             # Back keeps the search, and Forward the bill (the laptop's
             # test of 7 November 2026).
             ("?q=HB+703&term=all", "click:2020,back,forward:2020,back"),
             # Words typed with the bill open and never run: Back draws the
             # list's own search, and the box says it (that night's review).
             ("?q=HB703", "click:2020,type:zzz,back"),
             # Back twice, past the bill, from a later list of another
             # search in another term: the first list, its words and its
             # term, as its own entry names them.
             ("?q=HB703", "click:2020,search:HB1,term:2019-2020,back,back"),
             ("?term=2019-2020&q=HB703", "click:2020,search:HB1,term:all,back,back,forward:2020"),
             # The picker turned with the bill open, then Back: the term
             # chosen is still the reader's (THE OPEN BILL KEEPS ITS OWN TERM).
             ("?q=HB703", "click:2020,term:2025-2026,back"),
             # The second review of 7 November 2026. A term only held while
             # the bill was open -- the later list's, turned with no bill open
             # -- gives way to the first list's own on Back twice.
             ("?q=HB703", "click:2020,search:HB1,term:2025-2026,back,back"),
             # Every topic ticked, and the order chosen, are the list's after
             # Back as before it: the second of two was lost. No words, so the
             # topics are what draws the list (a number searched for is drawn
             # whatever is ticked).
             ("?topic=Insurance&topic=Education&sort=recent", "click:2020,back,forward:2020,back"),
             # A list of no words, and words typed on a list and not run, are
             # in no address: Back twice, past a later search, draws them,
             # not the later search's.
             ("", "click:2020,search:HB1,back,back"),
             ("", "type:HB703,click:2020,search:HB1,back,back"),
             # The third review: the words an entry holds follow the box
             # after Back -- changed, or emptied, then Forward and Back -- and
             # are not the words of before.
             ("", "type:HB703,click:2020,back,type:HB 703,forward:2020,back"),
             ("?q=HB703", "click:2020,back,type:,forward:2020,back"),
             # Words typed, and a bill clicked before the list is drawn again:
             # the box's words are the ones the list was left with.
             ("", "typefast:HB 703,click:2020,back"),
             # An order chosen with the bill open is the list's after Back;
             # one chosen on a later list, and a facet ticked there, are not
             # the first list's after Back twice.
             ("?q=HB703", "click:2020,sort:recent,back"),
             ("?q=HB703", "click:2020,search:HB1,sort:recent,back,back"),
             ("?q=HB703", "click:2020,search:HB703,tick:topic=Education,back,back"))
    bad, steps = [], 0
    from urllib.parse import parse_qs, urlsplit
    for start, plan in plans:
        run = _node_app(_SAME_NUMBER_HARNESS, files=files, args=(start, plan))
        if run is None:
            return "skip", "app.js, dom_stub.js or node is not here"
        if run["errs"]:
            bad.append(f"from {start}, {plan}: left unhandled: {run['errs'][:2]}")
        pick, open_bill, held = None, bool(re.search(r"#\d{4}/", start)), None
        # The page loaded takes every filter and the order its address names,
        # as Back does: each topic of two, not the first alone.
        named_q = parse_qs(start.lstrip("!").split("#")[0].lstrip("?"))
        loaded_q = parse_qs(run["init"]["search"].lstrip("?"))
        for k in ("topic", "status", "sort"):
            if sorted(named_q.get(k, [])) != sorted(loaded_q.get(k, [])):
                bad.append(f"from /bills{start}: the page loaded with {k} {loaded_q.get(k, [])}, "
                           f"where its address named {named_q.get(k, [])}")
        # The words each list was left with, by its address: what Back to it
        # puts in the box where its address names none.
        left, prev, held_sort = {}, run["init"], None
        for got in run["out"]:
            steps += 1
            # A list is left by a click on a bill, or by Forward to one.
            if got["step"].partition(":")[0] in ("click", "clickslow", "forward", "pop") \
                    and prev.get("path") == "/bills":
                left["/bills" + prev["search"]] = prev["box"]
            prev = got
            what, _, y = got["step"].partition(":")
            html, where = got["html"], f"from /bills{start}, {plan}, at {got['step']}"
            # Back to an entry focusBill pushed is that bill, opened again.
            to_bill = re.match(r"/bill/(\d{4})/", got.get("backTo") or "")
            if what == "back" and to_bill:
                what, y = "backbill", to_bill.group(1)
            if what in ("type", "typefast", "term", "sort", "tick"):
                # The picker turned with a bill open chooses the term the
                # list is in once the bill is closed, by Back as by anything;
                # and so does an order chosen there.
                if what == "term" and open_bill:
                    held = y
                if what == "sort" and open_bill:
                    held_sort = y
                pick = got["pick"]
                continue
            open_bill = what not in ("back", "search", "release")
            for p in got["asked"]:
                m = re.match(r"/idx/(.+)\.json$", p)
                if m and m.group(1) not in terms:
                    bad.append(f"{where}: asked for {p}, the index of no term")
            if what in ("back", "search", "release"):
                chose, held = held, None
                if what == "back" and chose and chose != "all":
                    # Back in the term the reader chose with the bill open:
                    # that term's bill alone, and the picker on it.
                    own = next(r for r in rows if r["term"] == chose)
                    gone = next(m for k, m in marks.items() if k != str(own["year"]))
                    if f"{marks[str(own['year'])]}-ROW" not in html or f"{gone}-ROW" in html:
                        bad.append(f"{where}: Back after the picker was turned to {chose} with the bill "
                                   "open does not draw that term's list")
                    if got["pick"] != chose:
                        bad.append(f"{where}: the picker reads {got['pick']!r}, not the {chose!r} chosen")
                    pick = got["pick"]
                    continue
                both = what in ("back", "release") or y.upper() == "HB703"
                if both and not all(f"{m}-ROW" in html for m in marks.values()):
                    bad.append(f"{where}: the list of both bills is not drawn again under All Terms")
                if any(f"{m}-REC" in html for m in marks.values()):
                    bad.append(f"{where}: a bill's record is still drawn over the list")
                if got["acts"]:
                    bad.append(f"{where}: the {got['acts']} bill's Cite and Report row is still up")
                # BACK KEEPS THE SEARCH (the laptop's test of 7 November
                # 2026): the list's own address, put back by the browser,
                # stays, words and all; nothing is pushed over it, so Forward
                # still reaches the bill; and the box says the words it names.
                if what == "back":
                    wants = parse_qs(urlsplit(got["backTo"] or "").query)
                    if held_sort:
                        # the order chosen with the bill open, in the list's
                        # address after Back
                        wants["sort"], held_sort = [held_sort], None
                    wq = wants.get("q", [None])[0]
                    wt = wants.get("term", [None])[0]
                    has = parse_qs(got["search"].lstrip("?"))
                    if got["pushed"]:
                        bad.append(f"{where}: Back pushed {got['pushed']} over the list's own "
                                   "address, and Forward is lost")
                    # The whole of it: its words, its term, every filter
                    # ticked and the order chosen, each as often as named.
                    if {k: sorted(v) for k, v in has.items()} != {k: sorted(v) for k, v in wants.items()}:
                        bad.append(f"{where}: Back left the address at {got['search']!r}, where the "
                                   f"list's own was {got['backTo']!r}")
                    if wq is not None and got["box"] != wq:
                        bad.append(f"{where}: the box reads {got['box']!r} under a list of {wq!r}")
                    elif wq is None and got["backTo"] in left and got["box"] != left[got["backTo"]]:
                        bad.append(f"{where}: the box reads {got['box']!r} under a list left with "
                                   f"{left[got['backTo']]!r}")
                    if wt is not None and got["pick"] != wt:
                        bad.append(f"{where}: the picker reads {got['pick']!r} under a list of the "
                                   f"{wt!r} term")
                pick = got["pick"]
                continue
            other = next(o for o in marks if o != y)
            # A bill whose record is still on its way draws its head alone;
            # one on its Bill Text tab draws the versions where the record was.
            want = ("ROW",) if what in ("clickslow", "text") else ("ROW", "REC")
            for part in ("ROW", "REC"):
                if part in want and f"{marks[y]}-{part}" not in html:
                    bad.append(f"{where}: the {y} bill's {'head' if part == 'ROW' else 'record'} "
                               "is not drawn")
                if f"{marks[other]}-{part}" in html:
                    bad.append(f"{where}: the {other} bill's {'head' if part == 'ROW' else 'record'} "
                               "is drawn")
            if what != "clickslow" and got["acts"] != marks[y]:
                bad.append(f"{where}: the Cite and Report row up is "
                           f"{got['acts'] or 'none'}'s, not the {y} bill's ({marks[y]})")
            if what in ("click", "clickslow") and not (len(got["pushed"]) == 1
                                                       and got["pushed"][0].endswith(f"/bill/{y}/hb703")):
                bad.append(f"{where}: pushed {got['pushed']}, not /bill/{y}/hb703")
            if what in ("forward", "pop") and not got["replayed"]:
                bad.append(f"{where}: no entry was pushed for the {y} bill to go back to")
            if what == "text" and (f"/versions/{y}/HB703.json" not in got["asked"]
                                   or f"/versions/{other}/HB703.json" in got["asked"]):
                bad.append(f"{where}: the Bill Text tab asked for {[p for p in got['asked'] if 'versions' in p]}, "
                           f"not /versions/{y}/HB703.json")
            if what == "gloss" and got["pick"] != pick:
                bad.append(f"{where}: the picker reads {got['pick']!r}, not {pick!r}")
            if f"/bill/{other}/hb703" in got["asked"]:
                bad.append(f"{where}: asked for the {other} bill's record: {got['asked']}")
            pick = got["pick"]
    # THE TERM ASKED FOR ONCE (the second review of 7 November 2026): in the
    # newest term, 2025's bill open, the picker turned to 2019-2020 and Back
    # before its index has arrived. The picker and Back both want it; it is
    # fetched once, and its bill drawn once, as on a list that never waited.
    held = _node_app(_SAME_NUMBER_HARNESS, files=files,
                     args=("!?q=HB703", "click:2025,holdidx,term:2019-2020,back,release"))
    plain = _node_app(_SAME_NUMBER_HARNESS, files=files, args=("!?term=2019-2020&q=HB703", "click:2020,back"))
    if held and plain:
        steps += len(held["out"])
        if held["errs"]:
            bad.append(f"the term held on its way: left unhandled: {held['errs'][:2]}")
        idx = [p for got in held["out"] for p in got["asked"] if p == "/idx/2019-2020.json"]
        if len(idx) != 1:
            bad.append(f"the picker turned with the bill open, then Back before 2019-2020's index "
                       f"arrived: it was asked for {len(idx)} times, not once")
        last, once = held["out"][-1]["html"], plain["out"][-1]["html"]
        if last.count("DRUG-ROW title") != once.count("DRUG-ROW title") or "MEALS-ROW" in last:
            bad.append(f"the picker turned with the bill open, then Back before 2019-2020's index "
                       f"arrived: its bill is drawn {last.count('DRUG-ROW title')} times, where a list "
                       f"that never waited draws it {once.count('DRUG-ROW title')}"
                       + (", with 2025's beside it" if "MEALS-ROW" in last else ""))
        if held["out"][-1]["pick"] != "2019-2020":
            bad.append(f"the picker reads {held['out'][-1]['pick']!r} after Back, not the 2019-2020 chosen")
        # While it waits, the list says so, and draws no list of the bills
        # that happen to be here (the third review): "Not in the 2019-2020
        # term", or "0 bills", of a term that has them.
        waiting = next(g for g in held["out"] if g["step"] == "back")
        if not waiting["count"].startswith("loading 2019-2020") or "loading 2019-2020" not in waiting["html"] \
                or "ROW" in waiting["html"] or "Not in the" in waiting["html"]:
            bad.append(f"Back before 2019-2020's index arrived draws {waiting['html'][:120]!r} under "
                       f"{waiting['count']!r}, not that it is loading")
    # A TERM THAT FAILS IS NOT LEFT LOADING, and is asked for again: Back
    # while its index is refused draws what there is, and the picker turned
    # to it once it answers fetches it and draws its bill.
    failed = _node_app(_SAME_NUMBER_HARNESS, files=files,
                       args=("!?q=HB703", "click:2025,failidx,term:2019-2020,back,okidx,term:2019-2020"))
    if failed:
        steps += len(failed["out"])
        after = next(g for g in failed["out"] if g["step"] == "back")
        if after["count"].startswith("loading"):
            bad.append(f"Back while 2019-2020's index was refused leaves {after['count']!r} up")
        last = failed["out"][-1]
        if "/idx/2019-2020.json" not in last["asked"] or "DRUG-ROW" not in last["html"]:
            bad.append("2019-2020's index, refused once, is not asked for again when the picker is turned "
                       f"to it: asked {last['asked']}")
    # A PAGE LOADED AT A LIST'S OWN ENTRY takes the words the entry holds,
    # as a bill reloaded, then Back, loads it (the third review).
    kept = _node_app(_SAME_NUMBER_HARNESS, files=files, args=("", "release", json.dumps({"words": "HB703"})))
    if kept and kept["init"]["box"] != "HB703":
        bad.append(f"a page loaded at a list's entry holding the words 'HB703' reads {kept['init']['box']!r}")
    # NOTHING LEFT TO TRY IS NOT OFFERED: a search that finds nothing, in All
    # Terms with no filter, offers neither; in one term, another term; with a
    # topic ticked, the topic's removal too.
    for start, says, never in (("?q=QQZZQQ", (), ("Try removing", "a different term")),
                               ("!?q=QQZZQQ", ("Try a different term.",), ("removing a filter",)),
                               ("!?q=QQZZQQ&topic=Insurance", ("Try removing a filter, or a different term.",), ())):
        none_ = _node_app(_SAME_NUMBER_HARNESS, files=files, args=(start, "type:QQZZQQ"))
        if none_:
            h = none_["out"][-1]["html"]
            if "No bills match" not in h or any(s not in h for s in says) or any(s in h for s in never):
                bad.append(f"from /bills{start}, nothing found says {re.sub('<[^>]+>', ' ', h)[:160]!r}")
    assert not bad, f"{len(bad)} wrong:\n  " + "\n  ".join(bad[:8])
    return "ok", (f"HB 703 of 2020 and of 2025 under All Terms: {steps} steps over {len(plans) + 1} "
                  "orders -- clicks, Back, Forward, a search typed then Back, an address with "
                  "another search, a glossary tooltip, a jump from one to the other, a record "
                  "arriving after Back, the Bill Text tab -- each drawing, pushing and fetching "
                  "only the bill opened, its Cite row its own, Back drawing both again")


@check("data", "every versioned bill's print sheet composes, and its marked text reads back to "
               "the current version and to the introduced one")
def _print_sheet_on_the_record():
    """The sheet on every bill the built site has versions of: each composed
    with every setting on, without an error; ticked, its clean text prints
    every word of the current version, however long (HB 2 of 2025's 107,482
    among them: the person, 10 October 2026, "it should print the full
    length text"); and its marked text -- every change numbered by the
    amendment that made it -- read without its struck words is the current
    version and without its inserted words the introduced one, word for word. That is the reading `git blame` gives a
    file, and these two ends are what make it a reading of the record rather
    than a drawing of one. 1,031 bills on 9 October 2026, in about thirty
    seconds."""
    node = shutil.which("node") or shutil.which("node.exe")
    site = Path("site")
    if not (site / "versions").is_dir():
        return "skip", "no site/versions built"
    if not node:
        return "skip", "node is not on PATH"
    go = r"""
require("./stub.js");
const fs = require("fs"), path = require("path");
const {GRPrint: G} = (0, eval)(fs.readFileSync("./page.js", "utf8") + "\n;({GRPrint})");
const site = process.argv[2];
const recOf = (year, id) => {
  const h = fs.readFileSync(path.join(site, "bill", year, id.toLowerCase() + ".html"), "utf8");
  let m = /<script type="application\/json" id="gr-data">([\s\S]*?)<\/script>/.exec(h);
  if (m) return JSON.parse(m[1]);
  m = /<meta name="gr-data" content="([^"]+)"/.exec(h);
  return JSON.parse(fs.readFileSync(path.join(site, m[1].replace(/^\//, "")), "utf8"));
};
const words = ts => ts.filter(t => t.w !== "¶").map(t => t.w).join(" ");
let n = 0; const bad = [];
for (const year of fs.readdirSync(path.join(site, "versions")))
  for (const f of fs.readdirSync(path.join(site, "versions", year))) {
    if (!/^[A-Z]+\d+\.json$/.test(f)) continue;
    const id = f.slice(0, -5), ix = JSON.parse(fs.readFileSync(path.join(site, "versions", year, f), "utf8"));
    if ((ix.versions || []).length < 2) continue;
    try {
      const files = {};
      for (const v of ix.versions) {
        const u = v.blocks_url || v.text_url, p = path.join(site, u.replace(/^\//, ""));
        const x = u.endsWith(".json") ? JSON.parse(fs.readFileSync(p, "utf8")) : fs.readFileSync(p, "utf8");
        files[u] = x.blocks || x;
      }
      const d = recOf(year, id);
      const toks = ix.versions.map(v => G.text.tokens(files[v.blocks_url || v.text_url]));
      const B = G.text.blame(toks, G.text.joinSteps(d, ix).map(s => s.tag));
      if (words(B.doc.filter(t => t.st !== "del")) !== words(toks[toks.length - 1])
          || words(B.doc.filter(t => t.st !== "add")) !== words(toks[0]))
        bad.push(year + "/" + id + ": the marked text does not read back");
      const st = G.defaults(); st.names = 1; st.sec.text = 1;
      const ctx = {url: "https://graniterecord.org/bill/" + year + "/" + id.toLowerCase(),
        today: "2026-10-09", versions: {ix, files}};
      G.sheet(d, null, ctx, st);
      // ticked, the text prints whole: the clean text's words, every one
      st.text = "clean";
      const html = (G.sheet(d, null, ctx, st).split('<div class="ps-text">')[1] || "").split("</section>")[0];
      const drawn = html.replace(/<[^>]+>/g, " ").replace(/&[a-z]+;|&#\d+;/g, "x").split(/\s+/).filter(Boolean).length;
      if (drawn !== toks[toks.length - 1].filter(t => t.w !== "\u00b6").length)
        bad.push(year + "/" + id + ": ticked, the clean text prints " + drawn + " of "
          + toks[toks.length - 1].filter(t => t.w !== "\u00b6").length + " words");
    } catch (e) { bad.push(year + "/" + id + ": " + e.message); }
    n++;
  }
process.stdout.write("\n@@" + JSON.stringify({n, bad}));
"""
    root = Path(tempfile.mkdtemp(prefix="gr-print-data-"))
    try:
        js = _source("src/pages/app.js") + "\n;\n" + \
            _source("src/pages/print.js")
        (root / "page.js").write_text(_with_components(js), encoding="utf-8")
        (root / "stub.js").write_text(_source("tests/dom_stub.js"), encoding="utf-8")
        (root / "go.js").write_text(go, encoding="utf-8")
        r = _run([node, "--max-old-space-size=4096", "go.js", str(site.resolve())], cwd=root,
                 capture_output=True, text=True, timeout=600)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "the print sheet did not run over the built site: " + (r.stderr or r.stdout or "")[-400:])
        got = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert got["n"] > 0, "no versioned bill was read"
    assert not got["bad"], f"{len(got['bad'])} of {got['n']}: " + "; ".join(got["bad"][:6])
    return "ok", (f"{got['n']} versioned bills: every sheet composed, every clean text printed "
                  "whole, every marked text read back to its current and its introduced version")


_VW_CLEAR_JS = r"""
const src = %s;
const grab = re => { const m = src.match(re); if (!m) throw new Error("not in app.js: " + re); return m[0]; };
const code = [/function vwStrip\(box\)\{[\s\S]*?\n\}/, /function vwClearStrip\(el\)\{[\s\S]*?\n\}/].map(grab).join("\n");
const moved = [];
const window = { scrollBy: (x, y) => moved.push(y) };
const strip = { sticky: true, getBoundingClientRect: () => ({ bottom: 45 }) };
const tab = { closest: s => s === "[role=tablist]" ? strip : null };
const pane = { getAttribute: () => "sstab-videos" };
const document = { getElementById: id => id === "sstab-videos" ? tab : null };
const getComputedStyle = el => ({ position: el.sticky ? "sticky" : "static" });
const clear = new Function("window", "document", "getComputedStyle", code + "\nreturn vwClearStrip;")(
  window, document, getComputedStyle);
const slot = top => ({ getBoundingClientRect: () => ({ top }), matches: () => false,
  querySelector: () => null, closest: s => s === "[role=tabpanel]" ? pane : null });
const out = {};
clear(slot(0)); out.under = moved.splice(0);
clear(slot(60)); out.clear = moved.splice(0);
strip.sticky = false; clear(slot(0)); out.unstuck = moved.splice(0);
console.log("@@" + JSON.stringify(out));
"""


@check("frontend", "a recording the address names is landed on clear of the tab strip that stays "
       "at the top of the window", needs=())
def _vw_lands_clear_of_strip():
    """The walk of 31 October 2026: arriving at /committee/ss57/videos#v-...
    or /session/house/videos#v-..., vwLand brought the view to the top of the
    window and 45 to 49px of it went under the page's tab strip, which stays
    there, at 1280 and at 390. vwClearStrip moves the page down by what the
    strip covers, and only that: run here on a view under the strip, one
    clear of it, and one under a strip that does not stay."""
    js = Path("src/pages/app.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and node):
        return "skip", "app.js or node is not here"
    src = _source(js)
    land = re.search(r"function vwLand\(slot\)\{[\s\S]*?\n\}", src)
    assert land and re.search(r"scrollIntoView\(\{block:\"start\"\}\);\s*vwClearStrip\(slot\);", land.group(0)), (
        "vwLand no longer clears the tab strip after bringing the view to the top")
    root = Path(tempfile.mkdtemp())
    try:
        t = root / "go.js"
        t.write_text(_VW_CLEAR_JS % json.dumps(src), encoding="utf-8")
        r = _run([node, str(t)], capture_output=True, text=True, timeout=60)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert r.returncode == 0 and "@@" in (r.stdout or ""), (r.stderr or r.stdout or "")[-400:]
    got = json.loads(r.stdout.rsplit("@@", 1)[1])
    assert got == {"under": [-45], "clear": [], "unstuck": []}, (
        f"the view under the strip, clear of it, and under one that does not stay moved {got}; "
        "want -45px, nothing, nothing")
    return "ok", "a view 45px under the strip is moved 45px down; one clear of it, or under a strip that scrolls, is not moved"


@check("build", "a roll call on no bill is drawn on its session day from its card, with its "
                "parties and members, as a roll call on a bill is")
def _nobill_ring_on_session_day():
    """The person's rule for the Votes tab (23 October 2026: "The two
    displays should not be structured differently from each other") holds
    on the session day too. A roll call on a bill names its bill's record
    and its card there (data-bill, data-card), and app.js draws the bill
    page's ring and party rows from it; a roll call on no bill named
    nothing, so the 21 May 2026 reprimand vote, 288-54 by roll call, was a
    ring of two counts that told a screen reader it was a division (the
    preview, 23 October 2026). It names its term's nobill/<term>.json card
    now. Read off the fixture: every such slot leads to a card that has its
    members, and app.js reads that record as it reads a bill's."""
    shared, _base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    rx = re.compile(r'<div class="svote" data-vote="\d+" data-bill="nobill/([^"]+)" '
                    r'data-card="(\d+)"')
    found = []
    for f in sorted((site / "session").rglob("*.html")):
        for m in rx.finditer(f.read_text(encoding="utf-8", errors="replace")):
            found.append((f.relative_to(site).as_posix(), m.group(1), int(m.group(2))))
    assert found, "no session day draws a roll call on no bill from its card"
    for where, term, i in found:
        nb = site / "nobill" / f"{term}.json"
        assert nb.is_file(), f"{where} names nobill/{term}.json, which the build did not write"
        cards = json.loads(nb.read_text(encoding="utf-8")).get("rollcalls") or []
        assert i < len(cards) and cards[i].get("members"), (
            f"{where}: card {i} of nobill/{term}.json has no members to draw")
    app = _source(_paths.locate("src/pages/app.js"))
    assert "(nb?nobillRecord:billRecord)(key,drawSessionVotes)" in app, (
        "app.js's session-day ring does not read a term's record of roll calls on no bill")
    return "ok", f"{len(found)} roll calls on no bill on the fixture's session days, each from its card"


# The harness of _session_rings_one_bill: a session day of two bills, HB1
# with two roll calls and HB2 with one, whose records are held back until the
# harness lets each come. A raw string: the record's markup carries a slash.
_SESSION_RINGS_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
window.GR_STATIC = true;
const slots = [["HB1", 0, 0], ["HB1", 1, 1], ["HB2", 2, 0]].map(([b, n, c]) => {
  const at = {"data-vote": String(n), "data-bill": "2026/" + b, "data-card": String(c)};
  const s = {b, n, reads: 0, writes: 0, _h: "", getAttribute: k => (k in at ? at[k] : null)};
  Object.defineProperty(s, "innerHTML", {get() { s.reads++; return s._h; },
                                         set(v) { s.writes++; s._h = String(v); }});
  return s; });
document.querySelectorAll = q => (q === ".svote[data-vote]" ? slots : []);
const count = {yeas: 2, nays: 1, passed: true};
document.getElementById("sessvotes").textContent = JSON.stringify([count, count, count]);
const card = () => Object.assign({tally: {R: {Yea: 2}, D: {Nay: 1}}, members: [
  {n: "A", p: "R", v: "Yea"}, {n: "B", p: "R", v: "Yea"}, {n: "C", p: "D", v: "Nay"}]}, count);
const recs = {"/bill/2026/hb1": {rollcalls: [card(), card()]}, "/bill/2026/hb2": {rollcalls: [card()]}};
const asked = [], release = {};
globalThis.fetch = u => { const path = new URL(u).pathname; asked.push(path);
  return new Promise(ok => { release[path] = () => ok({ok: true, status: 200, text: async () =>
    '<script type="application/json" id="gr-data">' + JSON.stringify(recs[path]) + "</script>"}); }); };
globalThis.DOMParser = class { parseFromString(h) {
  const m = /id="gr-data">([\s\S]*?)<\/script>/.exec(h);
  return {getElementById: id => (id === "gr-data" && m ? {textContent: m[1]} : null),
          querySelector: () => null}; } };
const ticks = async n => { for (let i = 0; i < n; i++) await new Promise(r => setImmediate(r)); };
const seen = () => slots.map(s => { const o = [s.b, s.reads, s.writes]; s.reads = s.writes = 0; return o; });
(async () => {
  try { (0, eval)(fs.readFileSync("./page.js", "utf8")); }
  catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
  const out = {asked: asked.slice(), first: seen()};
  release["/bill/2026/hb2"](); await ticks(20); out.hb2 = seen();
  release["/bill/2026/hb1"](); await ticks(20); out.hb1 = seen();
  out.rings = slots.map(s => /data-seg="/.test(s._h));
  process.stdout.write("\n@@" + JSON.stringify(out));
})().catch(e => { console.log("RUN " + e.message); process.exit(1); });
"""


@check("frontend", "a session day draws a bill's rings again when that bill's record comes, "
                   "and leaves every other bill's alone")
def _session_rings_one_bill():
    """The phone audit of 25 October 2026 (M7): a session day of 29 bills
    fetched each bill's record to draw its roll calls with the Votes tab's
    own ring, and redrew all 40 rings each time one arrived -- reading back
    and rewriting every ring for every record, which froze a mid-range phone
    for seconds (23.8 s of the main thread's long tasks on the House's 11
    March 2026, with the CPU slowed four times; 7.2 s since). billRecord tells
    its callback which record came, and drawSessionVotes draws that bill's
    rings alone.

    Run in node over a day of two bills, HB1 with two roll calls and HB2
    with one, their records held back: on load every ring is drawn from the
    counts and each record asked for once; when HB2's comes only HB2's ring
    is read or written, and drawn from its members; when HB1's comes, only
    HB1's two."""
    got = _node_app(_SESSION_RINGS_HARNESS)
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    bad = []
    if sorted(got["asked"]) != ["/bill/2026/hb1", "/bill/2026/hb2"]:
        bad.append(f"the day asked for {got['asked']}, not each bill's record once")
    if any(w != 1 for _b, _r, w in got["first"]):
        bad.append(f"on load not every ring was drawn once from its counts: {got['first']}")
    for came, rows in (("HB2", got["hb2"]), ("HB1", got["hb1"])):
        other = [r for r in rows if r[0] != came and (r[1] or r[2])]
        own = [r for r in rows if r[0] == came and not r[2]]
        if other:
            bad.append(f"{came}'s record coming redrew another bill's ring: {other}")
        if own:
            bad.append(f"{came}'s record coming did not redraw its own ring: {own}")
    if got["rings"] != [True, True, True]:
        bad.append(f"the rings are not drawn from the records' members: {got['rings']}")
    assert not bad, "; ".join(bad)
    return "ok", ("a record coming redraws its own bill's rings and reads no other's; every "
                  "ring drawn from the counts first and from its record after")


@check("frontend", "every link that leaves the site carries the outside-link mark, says it opens a "
                   "new tab, and opens one, whoever wrote it")
def _outside_links():
    """The person's D20 (8 October 2026): outside links open in a new tab,
    generally, and keep their mark. The mark was drawn by class (a.out), so a
    link written without the class left the site unmarked -- the RSA chapters
    on a bill, the General Court's pages from the Calendar, a town's own
    website, the footer's credit -- and four writers put the arrow in as text
    instead. Now app.css marks a link by its address, with the words a screen
    reader says; find.js, which every page runs, opens such a link in a new
    tab at the moment it is followed, so a link app.js draws after the page
    has loaded is reached too; and no writer puts the arrow in as text, which
    would draw it twice. The one arrow left is the list card's corner link to
    the bill's own page (an inside link, which D17 replaces with the number)."""
    css = Path("src/pages/app.css")
    find = Path("src/pages/find.js")
    if not css.exists() or not find.exists():
        return "skip", "app.css or find.js is not here"
    text = _source(css)
    rule = re.search(r':is\(a\[href\^="https:"\],a\[href\^="http:"\]\):not\(\[href\^='
                     r'"https://graniterecord\.org"\]\)::after\{([^}]*)\}', text)
    assert rule, "app.css does not mark a link that leaves the site by its address"
    assert 'content:"\\2197" / " (opens in a new tab)"' in rule.group(1) \
        and rule.group(1).find('content:"\\2197";') < rule.group(1).find("/"), (
        "the outside-link mark does not say it opens a new tab, or has no plain arrow to "
        "fall back on in a browser that cannot read the words")
    bad = []
    for name, src in _front_sources():
        for m in re.finditer(r"&#8599;|\\u2197|↗|&nearr;", src):
            line = src[src.rfind("\n", 0, m.start()) + 1:src.find("\n", m.start())]
            if line.lstrip().startswith(("#", "//", "*", "/*")) or "Open the standalone page" in line:
                continue
            bad.append(f"{name}:{_line_of(src, m.start())} {line.strip()[:60]}")
    assert not bad, ("an arrow written as text beside a link, which app.css now draws itself: "
                     + "; ".join(bad[:6]))
    # NOTHING TAKES THE MARK OFF, AND NOTHING KEEPS A LINK IN THE TAB. A later
    # rule giving a link's ::after no content, or hiding it, unmarks every
    # outside link it reaches; and a link that names its own target is one
    # find.js leaves alone. The review of 8 October 2026 did both and this
    # passed them. The list card's corner arrow is an inside link's, drawn by
    # .detail's own text, and is not an ::after.
    for ctx, sel, body, ln in _css_rules(text):
        if "::after" not in sel or not re.search(r"(?:^|[\s,>+~(])a(?:[.:\[#]|::|$|[\s,)])", sel):
            continue
        if any(c.startswith("@media print") for c in ctx):
            continue
        for k, v in _css_decls(body):
            if (k == "content" and re.fullmatch(r"none|normal|[\"']\s*[\"']", v.strip())) \
                    or (k == "display" and v.strip() == "none"):
                bad.append(f"app.css:{ln} {sel[:60]} takes the outside-link mark off ({k}: {v})")
    for name, src in _front_sources():
        for m in re.finditer(r"target\s*=\s*\\?[\"'](?:_self|_top|_parent)\\?[\"']|"
                             r"setAttribute\(\s*[\"']target[\"']\s*,\s*[\"'](?:_self|_top|_parent)",
                             src):
            line = src[src.rfind("\n", 0, m.start()) + 1:src.find("\n", m.start())]
            if line.lstrip().startswith(("#", "//", "*", "/*")):
                continue
            bad.append(f"{name}:{_line_of(src, m.start())} keeps a link in the tab: "
                       f"{line.strip()[:60]}")
    assert not bad, ("an outside link that is not marked or does not open a new tab: "
                     + "; ".join(bad[:6]))
    js = _source(find)
    fn = re.search(r"function leavesSite\(a,here\)\{.*?\n\}", js, re.S)
    hook = re.search(r'document\.addEventListener\("click",function\(e\)\{\s*var a=e\.target&&'
                     r'e\.target\.closest&&e\.target\.closest\("a\[href\]"\);\s*if\(!leavesSite\(a,'
                     r'location\.host\)\|\|a\.getAttribute\("target"\)\)return;\s*a\.setAttribute\('
                     r'"target","_blank"\);', js)
    assert fn and hook, "find.js does not open a link that leaves the site in a new tab"
    cases = [("https://gc.nh.gov/rsa/html/674.htm", True), ("http://www.goffstownnh.gov/", True),
             ("https://graniterecord.org/bills.html", False), ("https://127.0.0.1:8000/x", False),
             ("mailto:a@b.c", False), ("tel:+16032713125", False)]
    node = shutil.which("node") or shutil.which("node.exe")
    if node:
        prog = (fn.group(0) + "\nconst C=" + json.dumps([c for c, _w in cases])
                + ";\nprocess.stdout.write(JSON.stringify(C.map(h=>{const u=new URL(h);"
                "return leavesSite({protocol:u.protocol,host:u.host},'127.0.0.1:8000');})));")
        r = _run([node, "-e", prog], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, "leavesSite() would not run: " + (r.stderr or "")[-300:]
        got = json.loads(r.stdout)
        off = [h for (h, w), g in zip(cases, got) if g != w]
        assert not off, f"leavesSite() is wrong about {off}"
    return "ok", ("app.css marks every link that leaves the site by its address and says it "
                  "opens a new tab; find.js opens it in one"
                  + (f", right about {len(cases)} addresses" if node else "")
                  + "; no writer puts the arrow in as text")


# The harness of _filters_drawn_when_seen, after _HEARD_PRELUDE: the bill
# search on a phone (the 60em query matching), its filter panel's writes
# counted, through typing with the panel shut and open and the window widened.
_FILTERS_SEEN_HARNESS = r"""
const mq = {matches: true, heard: [], addEventListener(t, f) { this.heard.push(f); }};
globalThis.matchMedia = q => (/59\.9375em/.test(q) ? mq : {matches: false, addEventListener() {}});
const cl = new Set();
document.querySelector(".shell").classList = {add: x => cl.add(x), remove: x => cl.delete(x),
  contains: x => cl.has(x), toggle: (x, on) => { const v = on === undefined ? !cl.has(x) : !!on;
    v ? cl.add(x) : cl.delete(x); return v; }};
let drawn = 0, fh = "";
const fx = {scrollTop: 0, hidden: false, querySelectorAll: () => [],
  get innerHTML() { return fh; }, set innerHTML(v) { drawn++; fh = String(v); }};
const find = document.querySelector;
document.querySelector = q => (q === "#facets" ? fx : find.call(document, q));
const ftb = document.getElementById("ftoggle"), badge = {textContent: "", hidden: true};
ftb.querySelector = q => (q === ".badge" ? badge : null);
load("render, IDX, sel, PAGE_SIZE, setMeta:(m)=>{META=m;}, setTerm:(t)=>{term=t;}");
s.setMeta({terms: ["2025-2026"], committee_codes: {}, topics: ["Housing"]});
s.setTerm("2025-2026");
s.IDX.length = 0;
for (let i = 1; i <= 120; i++) s.IDX.push({id: "HB" + i, n: "HB " + i, title: "a bill", status: "Passed",
  kind: "active", committees: ["House Finance"], committee: "House Finance", topic: "Housing",
  sponsor: "", term: "2025-2026", year: "2025", hayT: "hb" + i + " a bill", hayC: "house finance"});
const out = {size: s.PAGE_SIZE};
const toggle = () => click(q => (q === "#ftoggle" ? ftb : null));
const step = (name, f) => { const was = drawn; f(); out[name] = {drawn: drawn - was, badge: badge.textContent}; };
step("shut", () => { s.sel.topic.add("Housing"); s.render(); });
out.cards = (document.querySelector("#results").innerHTML.match(/<article class="card/g) || []).length;
step("opened", toggle);
step("typedOpen", () => s.render());
step("closed", toggle);
step("typedShut", () => s.render());
step("widened", () => { mq.matches = false; mq.heard.forEach(f => f({matches: false})); });
step("typedWide", () => s.render());
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("frontend", "the bill search draws its filter panel only where it can be seen, and a "
                   "page of 25 to 50 cards at a time")
def _filters_drawn_when_seen():
    """The phone audit of 25 October 2026 (S8): the bill list lagged about a
    second a letter on a phone, because render() drew a hundred cards and,
    behind a Filters button nobody had pressed, the whole filter panel --
    every bill of the term counted again for each group -- on every letter.
    Typing "housing" at a phone's pace with the CPU slowed four times held
    the page 6.5 seconds; 2.2 since.

    Run in node with the 60em query matching, as on a phone: typing with the
    panel shut draws only the Filters button's badge; the button opening it
    draws the panel as it stands, and typing then draws it again; shut again,
    typing leaves it; the window widened past 60em draws it, and typing then
    does too. And the list draws PAGE_SIZE cards, between 25 and 50."""
    got = _node_app(_HEARD_PRELUDE + _FILTERS_SEEN_HARNESS)
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    want = {"shut": 0, "opened": 1, "typedOpen": 1, "closed": 0, "typedShut": 0,
            "widened": 1, "typedWide": 1}
    drew = {k: got[k]["drawn"] for k in want}
    bad = []
    if drew != want:
        bad.append(f"the filter panel was drawn {drew} times, not {want}")
    if got["shut"]["badge"] != "1":
        bad.append(f"with the panel shut the Filters button's badge says {got['shut']['badge']!r}, "
                   "not the 1 filter ticked")
    if not 25 <= (got["size"] or 0) <= 50 or got["cards"] != got["size"]:
        bad.append(f"the list's page is {got['size']} cards and {got['cards']} were drawn, "
                   "not one page of 25 to 50")
    assert not bad, "; ".join(bad)
    return "ok", (f"the panel drawn only open or wide, the badge kept with it shut; "
                  f"{got['size']} cards a page")


@check("frontend", "the Calendar page works in a DOM: selecting a day, the views, the filters, the address, the keyboard and the preview")
def _calendar_in_a_dom():
    """The page's own script, run on the page's own markup.

    dom_stub.js answers every query with a blank element, which is right for
    loading app.js and useless for a calendar: nothing here can be checked
    against a DOM that holds nothing. So this carries a small real one --
    _CAL_DOM parses the markup this site writes, answers the selectors the
    script uses, captures and bubbles events, moves focus, keeps history and
    lets the check move the clock by hand -- and runs the copy of the script
    the fixture's week page carries, on that page's markup, as a reader would
    meet it.

    It opens the tab on the reader's today, which is not the build's; selects
    a day in the next week and wants the address, the heading, the list and
    one step of history to follow, and Back to undo it; switches to the week
    and the day; ticks and unticks the boxes above the schedule, picks one
    committee and a chamber, and puts it all back with one control; redraws
    with focus on a card and wants focus back on that card;
    walks the grid with the arrow keys and Page Down into the next month;
    and rests the pointer on a day for 499 and then 501 milliseconds, moves
    to the next day, presses Escape, leaves the grid, tabs to a day and taps
    one, wanting the preview to do what the page says it does. An address
    carrying a day, a view and a filter opens on them.

    Added after the review of 24 September: the rest of the page -- the
    citation's four forms, the canonical link, the og tags, the structured
    data and the skip link -- names the week shown, not the week the page was
    loaded as; the week's arrows, head and foot, keep focus on the arrow
    pressed, or give it to the heading where that arrow is gone; the month's
    name, a live region, is written only when the month changes; focus that
    leaves the grid takes a pending preview with it, and a day clicked does
    not open its own preview again; and on a phone a month arrow or an arrow
    key opens the folded month without making that the reader's default,
    while folding over another month shows the selected week.

    Added after the recheck of 25 September, on a DOM that now scrolls when
    it is told where things are: Enter on a week's arrow, head or foot,
    leaves that arrow on the screen, while a click still brings the day into
    view; a day that moves under a pointer that has not moved does not open
    its preview, and a preview still waiting when a day is clicked goes with
    the click; and a week whose month file fails is named wherever the page
    names a week -- heading, title, canonical link, citation -- with a panel
    that says which week it could not load and links it.

    Rewritten for the person's requests of 25 September 2026. The boxes in
    the kinds' colours are the filter, Study Committee starts unticked and
    is remembered in this browser, and a committee asked for by name shows
    whatever that box says. Moving about the calendar keeps the reader on
    /calendar with the state in the query -- a week, a day only where it is
    not the one the week opens on, a view only where it is not the list,
    filters only where a new reader's differ -- pushing a step of history
    for a week, a day or a view and replacing it for a filter; and this
    opens such an address sent to somebody, reloads one in the same
    browser, goes Back to a week's own page from the first move off it,
    opens a link in the hash form written until that day and wants it
    written into the query, keeps the file's own name where the page was
    reached by it, and keeps the day the Day view is reading when a filter
    changes the day its week opens on. Every time it prints reads 9:00 AM.
    """
    node = _cal_node()
    if not node:
        return "skip", "node is not on PATH"
    if not Path("src/pages/bills.html").exists():
        return "skip", "bills.html is not here"
    root = Path(tempfile.mkdtemp(prefix="gr-caldom-"))
    try:
        site, _w, _o, _u, _m = _cal_fixture(root)
        (root / "minidom.js").write_text(_CAL_DOM, encoding="utf-8")
        (root / "drive.js").write_text(_CAL_DRIVE, encoding="utf-8")
        r = _run([node, str(root / "drive.js"), str(site)], capture_output=True, text=True,
                 timeout=120)
        out = (r.stdout or "") + (r.stderr or "")
        assert r.returncode == 0 and out.strip().endswith("OK"), out.strip()[-1500:]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", out.strip().splitlines()[-2]

# The reader, for _calendar_in_a_dom.
_CAL_DRIVE = r"""const {makeWorld, runPage}=require("./minidom.js");
const fs=require("fs"), vm=require("vm"), path=require("path");
const SITE=process.argv[2], fails=[];
const ok=(c,m)=>{ if(!c) fails.push(m); };
const NB=String.fromCharCode(160);
// The file a server gives for an address: Cloudflare Pages answers /calendar
// with calendar.html whatever the query, and a week's own address with its file.
function fileFor(p){ p=p.replace(/^\//,""); return p==="calendar"||p==="calendar.html"?"calendar.html":p.replace(/(\.html)?$/,".html"); }
function world(page,pathname,o){
  const text=fs.readFileSync(path.join(SITE,page),"utf8");
  const a=text.indexOf('<div id="results">'), s=text.indexOf("<script>",a), e=text.indexOf("</script>",s);
  const W=makeWorld(Object.assign({today:[2026,3,11], path:pathname,
    files:(url)=>{ const f=path.join(SITE,url.replace(/^\//,"")); return fs.existsSync(f)?fs.readFileSync(f,"utf8"):null; }},o||{}));
  // The parts of the page outside the calendar that name its week: the
  // head's canonical link, og tags and structured data, the shell's skip
  // link, and the citation under the page.
  const head=W.doc.createElement("head"); W.doc.documentElement.appendChild(head);
  head.innerHTML=(text.match(/<link rel="canonical"[^>]*>|<meta (?:name|property)="[^"]*"[^>]*>|<script type="application\/ld\+json">[\s\S]*?<\/script>/g)||[]).join("");
  const res=text.slice(a,s);
  W.doc.body.innerHTML=(text.match(/<a class="skip"[^>]*>[^<]*<\/a>/)||[""])[0]+res
    // Cite this page: under the week's heading since 25 October 2026, so in
    // the slice above; before, the row above the heading (Follow's row), and
    // before that the section at the foot.
    +(res.includes('class="pageacts"')?"":
      (text.match(/<div class="pageacts"[^>]*><details class="pcite">[\s\S]*?<\/details><\/div>/)
      ||text.match(/<section class="citewrap">[\s\S]*?<\/section>/)||[""])[0]);
  W.run=async()=>{ runPage(W,text,SITE,s,text.slice(s+8,e));
    await W.settle(); W.advance(700); await W.settle(); };
  const D=W.doc;
  W.$=(id)=>D.getElementById(id); W.Q=(s,r)=>(r||D).querySelector(s); W.QA=(s,r)=>(r||D).querySelectorAll(s);
  // The meetings the schedule shows: its cards, and in the Week view the
  // entries that stand for them (one a card, named as the card is).
  W.keys=()=>W.QA(".calmeet",W.$("calview")).map(m=>m.getAttribute("data-date")+"|"+W.Q(".calcmte",m).textContent)
    .concat(W.QA(".wke",W.$("calview")).map(m=>m.getAttribute("data-date")+"|"+W.Q(".wkc",m).textContent));
  W.sel=()=>{ const g=W.Q('td[aria-selected="true"]',W.$("cmgrid")); return g&&g.getAttribute("data-d"); };
  W.view=(v)=>W.QA("[data-view]",W.$("calbar")).find(b=>b.getAttribute("data-view")===v);
  W.addr=()=>W.G.location.pathname+W.G.location.search+W.G.location.hash;
  W.box=(v)=>W.QA('input[name="cat"]',W.$("calcats")).find(i=>i.value===v);
  W.ticked=()=>W.QA('input[name="cat"]',W.$("calcats")).filter(i=>i.checked).map(i=>i.value).join();
  W.tick=async(v,on)=>{ const b=W.box(v); b.checked=on; b.dispatchEvent(W.ev("change")); await W.settle(); };
  W.step=async()=>{ await W.settle(); W.advance(700); await W.settle(); };
  return W;
}
// A reload: the same address opened again, in the same browser's storage.
function reload(W,o){ const L=W.G.location;
  return world(fileFor(L.pathname),L.pathname,Object.assign({search:L.search,hash:L.hash,store:W.store},o||{})); }
const CLOCK=new RegExp("^\\d{1,2}:\\d\\d"+NB+"(AM|PM)(–\\d{1,2}:\\d\\d"+NB+"(AM|PM))?$");
(async()=>{
  // ---- the tab, on the reader's today ----
  const W=world("calendar.html","/calendar"), D=W.doc, $=W.$, Q=W.Q, QA=W.QA;
  const statik=W.keys();
  await W.run();
  const C=W.win.GRCAL;
  ok(!$("calside").hidden && !$("calbar").hidden && !$("calcats").hidden && $("calapp").classList.contains("on"),
     "the month, the filters and the boxes did not come up");
  ok(Q(".calkey").hidden, "the key a reader without script is given is still shown beside the boxes");
  ok(W.sel()==="2026-03-11", "the tab did not open on the reader's today: "+W.sel());
  ok((Q('td[aria-current="date"]',$("cmgrid"))||{getAttribute:()=>null}).getAttribute("data-d")==="2026-03-11", "today is not aria-current=date");
  ok(QA("tr.cmsel td",$("cmgrid")).map(t=>t.getAttribute("data-d")).join()===[0,1,2,3,4,5,6].map(i=>C.addDays("2026-03-09",i)).join(),
     "the band is not Monday, March 9 to Sunday, March 15");
  ok(W.ticked()==="hearing,exec,work,conf,floor,date", "a new reader's boxes: "+W.ticked());
  // STUDY COMMITTEES ARE OFF FOR A NEW READER: the page's own list, less the
  // Commission on Aging's two cards.
  const plain=statik.filter(k=>!/Aging/.test(k));
  ok(plain.length===5 && W.keys().join()===plain.join(), "the list the script draws is not the page's own less the study committee: "+W.keys());
  ok($("wkcount").textContent==="5 of 6 meetings shown. 1 study committee meeting is hidden.", "the count reads "+$("wkcount").textContent);
  // AND THE WAY TO SHOW THEM, beside that one line (18 October 2026).
  ok(!$("calshowst").hidden, "Show them is not beside the line that says study committee meetings are hidden");
  ok($("calreset").hidden, "the reset control shows over a new reader's own filters");
  ok(QA(".caladd",$("calview")).length===5, "add-to-calendar on "+QA(".caladd",$("calview")).length+" cards, not the 5 shown that sat");
  ok($("cmprev").getAttribute("aria-disabled")==="true", "the month before the calendar's first is offered");
  const c10=Q('td[data-d="2026-03-10"]',$("cmgrid")), c13=Q('td[data-d="2026-03-13"]',$("cmgrid"));
  ok(QA(".cmdots i",c10).map(i=>i.className).join()==="k-hearing,k-exec", "10 March's dots: "+QA(".cmdots i",c10).map(i=>i.className));
  ok(!QA(".cmdots i",c13).length, "a study committee's day has a dot while its box is unticked");
  ok(QA(".cdrel",$("calview")).map(r=>r.textContent).join()===",,today,tomorrow,in 2 days", "the days' relative words: "+QA(".cdrel",$("calview")).map(r=>r.textContent));
  // MONDAY TO FRIDAY IN THE LIST TOO: Friday, whose one meeting is a study
  // committee's, stays and says what it holds, with Show them, as the Week
  // view's column does; the week's line has the count (18 October 2026; the
  // words, the R2 polish batch, 30 October 2026).
  const fri=Q('.calday[data-d="2026-03-13"]',$("calview"));
  ok(fri && Q(".calempty",fri) && /^Study committee meetings only\. Show them/.test(Q(".calempty",fri).textContent)
     && Q(".calshowday",Q(".calempty",fri)),
     "the list drops a weekday the filters emptied, or does not say why it is empty: "+(fri&&fri.textContent));
  ok(W.addr()==="/calendar" && W.G.history.length===1, "opening the tab wrote an address: "+W.addr());
  // EVERY TIME AS A READER SAYS IT, on the cards and on the items inside them.
  const times=QA(".caltime",$("calview")).map(t=>t.textContent);
  ok(times.length && times.every(t=>CLOCK.test(t)) && times.indexOf("10:00"+NB+"AM–1:00"+NB+"PM")>=0,
     "a card's time does not read in the twelve-hour clock: "+JSON.stringify(times));
  // ---- another week, and back ----
  const h0=W.G.history.length;
  Q('td[data-d="2026-03-18"]',$("cmgrid")).click(); await W.step();
  ok(W.addr()==="/calendar?week=2026-W12", "a day in another week, the one it opens on, is at "+W.addr());
  ok(W.G.history.length===h0+1, "choosing a day is not one step of history");
  ok(Q(".calhead h1").textContent==="The Week of March 16–20, 2026", "the heading: "+Q(".calhead h1").textContent);
  ok(W.keys().join()==="2026-03-18|House Judiciary,2026-03-18|Senate Finance", "the week of 16 March lists "+W.keys());
  ok((Q(".calday.calsel",$("calview"))||{getAttribute:()=>null}).getAttribute("data-d")==="2026-03-18", "the list does not mark the day chosen");
  ok(QA(".calhead .wknav a").map(a=>a.getAttribute("href")).join()==="/calendar,/calendar,/calendar/2026-W13",
     "the arrows: "+QA(".calhead .wknav a").map(a=>a.getAttribute("href")));
  // The rest of the page names the week shown, by its own page's address,
  // which is what is indexed: the citation's four forms, the canonical link,
  // og:url; and the skip link stays on this page.
  const named=()=>({cite:QA(".pcite dd").map(d=>d.textContent).join(" | "),
    canon:Q('link[rel="canonical"]').getAttribute("href"), og:Q('meta[property="og:url"]').getAttribute("content"),
    ogt:Q('meta[property="og:title"]').getAttribute("content"), ld:Q('script[type="application/ld+json"]').textContent,
    skip:Q("a.skip").getAttribute("href"), days:QA(".pcite .citeday").length});
  let nm=named();
  ok(nm.canon==="https://graniterecord.org/calendar/2026-W12" && nm.og===nm.canon && nm.ogt==="The Week of March 16–20, 2026"
     && /“The Week of March 16–20, 2026\.” Granite Record, https:\/\/graniterecord\.org\/calendar\/2026-W12\. Accessed/.test(nm.cite)
     && /@misc\{calendar-2026-W12,/.test(nm.cite) && !/9–15 March|calendar,|\/calendar\./.test(nm.cite)
     && /"@id":"https:\/\/graniterecord\.org\/calendar\/2026-W12"/.test(nm.ld) && !/9–15 March/.test(nm.ld) && nm.days===4,
     "another week's page still names the week it was loaded as: "+JSON.stringify(nm));
  ok(nm.skip==="/calendar?week=2026-W12#results", "the skip link leaves the week shown: "+nm.skip);
  // The address is drawn again whole, as shell.cite_url draws it: a break
  // after the site's slash and after "calendar/", and the last part kept
  // whole with what follows it -- MLA's and Chicago's stop, APA's nothing,
  // BibTeX's "},".
  const drawnAs=(u,last)=>QA(".pcite .citeurl").map(x=>x.innerHTML).join(" | ")===
    [".","",".","},"].map(a=>u+'<span class="citetail">'+last+a+"</span>").join(" | ");
  ok(drawnAs("https://graniterecord.org/<wbr>calendar/<wbr>","2026-W12"),
     "another week's address in the citation is not drawn as shell.cite_url draws it: "
     +QA(".pcite .citeurl").map(u=>u.innerHTML).join(" | "));
  // A day that is not the one its week opens on is named in the address.
  Q('td[data-d="2026-03-19"]',$("cmgrid")).click(); await W.step();
  ok(W.addr()==="/calendar?week=2026-W12&day=2026-03-19" && W.G.history.length===h0+2, "a day chosen is at "+W.addr());
  W.G.history.back(); await W.step();
  ok(W.addr()==="/calendar?week=2026-W12" && W.sel()==="2026-03-18", "Back did not return to 18 March: "+W.addr()+" "+W.sel());
  W.G.history.back(); await W.step();
  ok(W.sel()==="2026-03-11" && W.addr()==="/calendar" && Q(".calhead h1").textContent==="The Week of March 9–14, 2026", "Back did not return to 11 March");
  nm=named();
  ok(nm.canon==="https://graniterecord.org/calendar" && /“The Week of March 9–14, 2026\.” Granite Record, https:\/\/graniterecord\.org\/calendar\. Accessed/.test(nm.cite)
     && /@misc\{calendar,/.test(nm.cite) && nm.skip==="/calendar#results", "Back did not name this week again: "+JSON.stringify(nm));
  ok(drawnAs("https://graniterecord.org/<wbr>","calendar"),
     "back on this week, its address in the citation is not drawn as shell.cite_url draws it: "
     +QA(".pcite .citeurl").map(u=>u.innerHTML).join(" | "));
  // THE ARROWS KEEP FOCUS. The week after, from the head's arrows, then This
  // week from the foot's: the same arrow in the new ones, and the heading
  // where that arrow is gone. Each is a week on the calendar's own address.
  const arrow=(where,cls)=>Q(where+" a."+cls);
  arrow(".calhead .wknav","wknext").focus(); arrow(".calhead .wknav","wknext").click(); await W.step();
  ok(W.addr()==="/calendar?week=2026-W12" && D.activeElement===arrow(".calhead .wknav","wknext"),
     "The week after dropped focus, or left the calendar's address: "+W.addr()+" "+D.activeElement.tagName+"."+D.activeElement.className);
  ok(W.sel()==="2026-03-18", "The week after did not open the week on its first sitting: "+W.sel());
  arrow(".calhead .wknav","wkhere").focus(); arrow(".calhead .wknav","wkhere").click(); await W.step();
  ok(W.sel()==="2026-03-11" && W.addr()==="/calendar?week=2026-W11" && !arrow(".calhead .wknav","wkhere")
     && D.activeElement===Q(".calhead h1") && Q(".calhead h1").getAttribute("tabindex")==="-1",
     "This week, which is gone on this week, dropped focus: it is on "+D.activeElement.tagName+"."+D.activeElement.className+" at "+W.addr());
  arrow(".calhead .wknav","wknext").focus(); arrow(".calhead .wknav","wknext").click(); await W.step();
  ok(D.activeElement===arrow(".calhead .wknav","wknext"), "the head's The week after dropped focus");
  arrow(".calhead .wknav","wkprev").focus(); arrow(".calhead .wknav","wkprev").click(); await W.step();
  ok(W.sel()==="2026-03-11" && D.activeElement===arrow(".calhead .wknav","wkprev"), "The week before dropped focus");
  // ---- the week, the day ----
  W.view("week").click(); await W.settle();
  // MONDAY TO FRIDAY, beside the month (9 October 2026): a column a day,
  // each the day's meetings in brief, and a Saturday whose one meeting is
  // hidden is no column.
  const wcols=QA(".wkcol",$("calview"));
  ok(wcols.map(c=>Q(".wkday",c).getAttribute("data-d")).join()==="2026-03-09,2026-03-10,2026-03-11,2026-03-12,2026-03-13"
     && QA(".wkdn",$("calview")).map(x=>x.textContent).join()==="Monday,Tuesday,Wednesday,Thursday,Friday",
     "the week is not Monday to Friday: "+wcols.map(c=>Q(".wkday",c).getAttribute("data-d")));
  ok(!QA("table",$("calview")).length && !QA(".calmeet",$("calview")).length && QA(".wke",$("calview")).length===5,
     "the week is still whole cards in a table of hours, or not one entry a meeting shown");
  ok(W.keys().sort().join()===plain.slice().sort().join(), "the week at a glance does not hold the week's cards: "+W.keys());
  ok(Q(".wkempty",wcols[0]).textContent==="No meetings"
     && /^Study committee meetings only\. Show them/.test(Q(".wkempty",wcols[4]).textContent),
     "an empty column does not say why: "+[Q(".wkempty",wcols[0]),Q(".wkempty",wcols[4])].map(x=>x&&x.textContent));
  ok(wcols[2].getAttribute("aria-current")==="date" && Q(".wkdd",wcols[2]).textContent==="Mar 11 · Today",
     "today is not marked in the week: "+Q(".wkdd",wcols[2]).textContent);
  ok(QA(".wkt",$("calview")).every(t=>/^\d{1,2}:\d\d (AM|PM)$/.test(t.textContent)), "an entry's time is not as a reader says it");
  ok(W.addr()==="/calendar?week=2026-W11&view=week", "the address does not say Week: "+W.addr());
  // An entry with no page to lead to -- a conference's -- opens its day,
  // the card in full and given the focus.
  const conf=QA(".wke",$("calview")).find(e=>/conference/.test(Q(".wkc",e).textContent));
  ok(conf && Q(".wkgo",conf).tagName==="BUTTON", "the conference's entry is not a button into its day");
  if(conf){ Q(".wkgo",conf).click(); await W.settle(); }
  // NO DAY VIEW (the owner's walk of dry run 9, 8 November 2026): the entry
  // opens the list at its day, that meeting open and focused, the rest shut.
  ok(!W.view("day") && W.view("list").getAttribute("aria-pressed")==="true" && W.sel()==="2026-03-11"
     && D.activeElement.tagName==="SUMMARY" && /conference/.test(D.activeElement.textContent)
     && QA(".calmeet",$("calview")).filter(m=>m.open).length===1, "the conference's entry did not open it in the list: "
     +W.addr()+" "+D.activeElement.tagName);
  ok(!/view=day/.test(W.addr()), "the list's address still says the Day view: "+W.addr());
  // ---- the boxes ----
  // SHOW THEM ticks Study Committee as a reader's tick does (18 October 2026).
  $("calshowst").click(); await W.settle();
  ok(W.box("study").checked && W.store.get("gr.calendar.showstudy")==="1" && $("calshowst").hidden
     && W.keys().some(k=>/Commission on Aging/.test(k)) && D.activeElement===W.box("study"),
     "Show them does not show the study committees, remember it, go, and leave the focus on the box: "+W.ticked());
  await W.tick("study",false);
  const hb=W.G.history.length;
  await W.tick("study",true);
  ok(W.store.get("gr.calendar.showstudy")==="1", "ticking Study Committee is not remembered");
  ok(W.keys().some(k=>/2026-03-13\|Commission on Aging/.test(k)) && $("wkcount").textContent==="6 meetings this week.",
     "Study Committee ticked: "+$("wkcount").textContent+" "+W.keys());
  ok(QA(".cmdots i",Q('td[data-d="2026-03-13"]',$("cmgrid"))).map(i=>i.className).join()==="k-study", "a study committee's dot is not its colour");
  ok(!$("calreset").hidden && W.addr()==="/calendar?week=2026-W11&kinds=hearing,exec,work,conf,floor,study,date"
     && W.G.history.length===hb, "a box is not in the address, or took a step of history: "+W.addr());
  await W.tick("study",false);
  ok(W.store.get("gr.calendar.showstudy")==="0" && W.keys().join()===plain.join() && $("calreset").hidden && W.addr()==="/calendar?week=2026-W11",
     "Study Committee unticked again: "+W.addr());
  // A DAY OF STUDY COMMITTEES ALONE, in the Day view, says what it holds and
  // never "matches the filters", which no reader had set; the month's cell
  // says it to a screen reader; and the day's own Show them shows them, as
  // the week line's does (the R2 polish batch, 30 October 2026).
  W.view("list").click(); await W.settle();
  Q('td[data-d="2026-03-13"]',$("cmgrid")).click(); await W.step();
  const d13=Q('.calday[data-d="2026-03-13"]',$("calview")), e13=d13&&Q(".calempty",d13);
  ok(W.sel()==="2026-03-13" && e13 && /^Study committee meetings only\. Show them/.test(e13.textContent)
     && !/matches the filters/.test($("calview").textContent) && Q(".calshowday",e13),
     "a day of study committees alone in the Day view: "+(d13&&d13.textContent));
  const n13=Q(".sr",Q('td[data-d="2026-03-13"]',$("cmgrid")));
  ok(n13 && /Friday, March 13, 2026, study committee meetings only/.test(n13.textContent),
     "the month's cell of a study committees' day: "+(n13&&n13.textContent));
  if(e13&&Q(".calshowday",e13)){ Q(".calshowday",e13).click(); await W.settle(); }
  ok(W.box("study").checked && W.store.get("gr.calendar.showstudy")==="1"
     && W.keys().some(k=>/2026-03-13\|Commission on Aging/.test(k)),
     "a day's Show them does not tick the box and draw the day's study committee: "+W.keys());
  ok(D.activeElement && D.activeElement.tagName==="SUMMARY" && /Commission on Aging/.test(D.activeElement.textContent),
     "a day's Show them leaves the focus off the meeting it shows: "+(D.activeElement&&D.activeElement.tagName));
  await W.tick("study",false);
  Q('td[data-d="2026-03-11"]',$("cmgrid")).click(); await W.step();
  W.view("list").click(); await W.settle();
  ok(W.store.get("gr.calendar.showstudy")==="0" && W.keys().join()===plain.join() && W.addr()==="/calendar?week=2026-W11",
     "the Day view's Show them left the list as it was not: "+W.addr());
  await W.tick("exec",false);
  ok(!W.keys().some(k=>/House Commerce/.test(k)) && W.keys().some(k=>/House Judiciary/.test(k)) && $("wkcount").textContent==="4 of 6 meetings shown. 1 study committee meeting is hidden.",
     "Executive Session unticked: "+$("wkcount").textContent+" "+W.keys()+" -- a committee that also heard bills stays");
  ok(!QA(".cmdots i",Q('td[data-d="2026-03-12"]',$("cmgrid"))).length, "the grid's dots do not follow the boxes");
  ok(W.addr()==="/calendar?week=2026-W11&kinds=hearing,work,conf,floor,date", "the address: "+W.addr());
  await W.tick("exec",true);
  await W.tick("floor",false);
  ok(!W.keys().some(k=>/House Session Day/.test(k)) && $("wkcount").textContent==="4 of 6 meetings shown. 1 study committee meeting is hidden.", "Session Day unticked: "+W.keys());
  await W.tick("floor",true);
  // ---- the side: a committee by name, a chamber, the search ----
  $("cpfind").dispatchEvent(W.ev("focus",{bubbles:false})); await W.settle();
  $("cpfind").value="jud"; $("cpfind").dispatchEvent(W.ev("input")); await W.settle();
  const box=QA("input",$("cplist")).find(i=>i.value==="House Judiciary");
  ok(box && QA("input",$("cplist")).length===1, "the picker does not find House Judiciary alone: "+QA("input",$("cplist")).map(i=>i.value));
  if(box){ box.checked=true; box.dispatchEvent(W.ev("change")); await W.settle(); }
  ok(W.keys().join()==="2026-03-10|House Judiciary", "one committee lists "+W.keys());
  ok(!$("pickhint").hidden && QA(".cpchip",$("cpchosen")).length===1, "a committee chosen is not a chip, or its hint is not said");
  ok(W.addr()==="/calendar?week=2026-W11&committee=House+Judiciary", "the chosen committee is not in the address: "+W.addr());
  await W.tick("hearing",false);
  ok(W.keys().join()==="2026-03-10|House Judiciary", "a committee chosen went with one of its two kinds unticked");
  await W.tick("exec",false);
  ok(!W.keys().length && $("wkcount").textContent==="None of the 6 meetings this week match.", "the boxes do not narrow a committee chosen: "+W.keys());
  await W.tick("hearing",true); await W.tick("exec",true);
  Q('[data-body="S"]',$("wkfilter")).click(); await W.settle();
  ok(!W.keys().length && $("wkcount").textContent==="None of the 6 meetings this week match.", "House Judiciary under the Senate: "+$("wkcount").textContent);
  ok(W.addr()==="/calendar?week=2026-W11&chamber=senate&committee=House+Judiciary", "the chamber in the address: "+W.addr());
  $("calreset").click(); await W.settle();
  ok(W.keys().join()===plain.join() && $("calreset").hidden && W.store.get("gr.calendar.showstudy")==="0"
     && W.addr()==="/calendar?week=2026-W11" && W.ticked()==="hearing,exec,work,conf,floor,date" && $("pickhint").hidden
     && Q('[data-body=""]',$("wkfilter")).getAttribute("aria-pressed")==="true",
     "Reset filters does not put a new reader's filters back: "+W.addr()+" "+W.ticked());
  ok(D.activeElement.getAttribute("data-view")==="list", "focus is not on the view switch after Reset filters");
  // A STUDY COMMITTEE ASKED FOR BY NAME shows with its box unticked: chosen,
  // or found by the search.
  $("cpfind").value="aging"; $("cpfind").dispatchEvent(W.ev("input")); await W.settle();
  const ag=QA("input",$("cplist")).find(i=>i.value==="Commission on Aging");
  if(ag){ ag.checked=true; ag.dispatchEvent(W.ev("change")); await W.settle(); }
  ok(ag && W.keys().join()==="2026-03-13|Commission on Aging,2026-03-14|Commission on Aging" && $("wkcount").textContent==="1 of 6 meetings shown."
     && !W.box("study").checked, "a study committee chosen with its box unticked: "+W.keys()+" / "+$("wkcount").textContent);
  $("calreset").click(); await W.settle();
  $("wkfind").value="aging"; $("wkfind").dispatchEvent(W.ev("input")); W.advance(200); await W.settle();
  ok(W.keys().join()==="2026-03-13|Commission on Aging,2026-03-14|Commission on Aging" && /q=aging/.test(W.addr()),
     "a study committee found by the search with its box unticked: "+W.keys()+" at "+W.addr());
  $("calreset").click(); await W.settle();
  ok($("wkfind").value==="" && W.keys().join()===plain.join(), "Reset filters left the search in place");
  // ---- the month's name is a live region, and is said once ----
  const mt=$("cmtitle"), tc=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(require("./minidom.js").E.prototype),"textContent");
  let said=0;
  Object.defineProperty(mt,"textContent",{configurable:true, get(){ return tc.get.call(this); }, set(v){ said++; tc.set.call(this,v); }});
  Q('[data-body="H"]',$("wkfilter")).click(); await W.settle(); Q('[data-body=""]',$("wkfilter")).click(); await W.settle();
  Q('td[data-d="2026-03-12"]',$("cmgrid")).click(); await W.step();
  ok(said===0, "the month's name, a live region, was written "+said+" times while the month did not change");
  $("cmnext").click(); await W.settle(); $("cmprev").click(); await W.settle();
  ok(said===2 && mt.textContent==="March 2026", "turning the month did not name it: "+said+" "+mt.textContent);
  delete mt.textContent;
  Q('td[data-d="2026-03-11"]',$("cmgrid")).click(); await W.step();
  // ---- a redraw keeps focus on the card that holds it ----
  const keep=QA(".calmeet",$("calview"))[0], kk=keep.getAttribute("data-date")+"|"+keep.getAttribute("data-cmte");
  Q("summary",keep).focus();
  await W.tick("conf",false);
  const f=D.activeElement;
  ok(f.tagName==="SUMMARY" && f.parentNode!==keep && f.parentNode.getAttribute("data-date")+"|"+f.parentNode.getAttribute("data-cmte")===kk,
     "focus was lost when the panel was drawn again");
  await W.tick("conf",true);
  // ---- the keyboard ----
  const t=Q('td[tabindex="0"]',$("cmgrid"));
  ok(t && t.getAttribute("data-d")==="2026-03-11" && QA('td[tabindex="0"]',$("cmgrid")).length===1, "the grid's one tab stop is not the selected day");
  t.focus(); t.dispatchEvent(W.ev("keydown",{key:"ArrowRight"})); await W.settle();
  ok(D.activeElement.getAttribute("data-d")==="2026-03-12", "ArrowRight");
  D.activeElement.dispatchEvent(W.ev("keydown",{key:"ArrowDown"})); await W.settle();
  ok(D.activeElement.getAttribute("data-d")==="2026-03-19" && W.sel()==="2026-03-11", "ArrowDown moves focus a week and selects nothing");
  D.activeElement.dispatchEvent(W.ev("keydown",{key:"PageDown"})); await W.step();
  ok($("cmtitle").textContent==="April 2026" && D.activeElement.getAttribute("data-d")==="2026-04-05", "Page Down: "+$("cmtitle").textContent+" "+D.activeElement.getAttribute("data-d"));
  D.activeElement.dispatchEvent(W.ev("keydown",{key:"Enter"})); await W.step();
  ok(W.sel()==="2026-04-05" && W.keys().join()==="2026-04-01|House Education", "Enter does not select 5 April's week: "+W.keys());
  ok(W.addr()==="/calendar?week=2026-W14&day=2026-04-05", "a day chosen by the keyboard is at "+W.addr());
  ok(D.activeElement.getAttribute("data-d")==="2026-04-05", "Enter took focus out of the grid");
  ok($("cmnext").getAttribute("aria-disabled")==="true", "the month after the calendar's last is offered");
  // ---- the preview ----
  D.dispatchEvent(W.ev("keydown",{key:"Escape"})); D.activeElement.blur();
  const cell=(d)=>Q(`td[data-d="${d}"]`,$("cmgrid"));
  Q(".cmn",cell("2026-04-01")).dispatchEvent(W.ev("pointerover",{pointerType:"mouse"}));
  W.advance(499); ok($("calpeek").hidden, "the preview opens before half a second's rest");
  W.advance(2); ok(!$("calpeek").hidden && /Wednesday, April 1/.test($("calpeek").textContent) && /Education/.test($("calpeek").textContent), "no preview after half a second: "+$("calpeek").textContent);
  ok((Q(".pkt",$("calpeek"))||{textContent:""}).textContent==="10:00"+NB+"AM", "the preview's time is not a reader's: "+$("calpeek").textContent);
  Q(".cmn",cell("2026-04-02")).dispatchEvent(W.ev("pointerover",{pointerType:"mouse"}));
  ok(!$("calpeek").hidden, "the preview closed on the way to the next day");
  W.advance(81); ok(/Thursday, April 2/.test($("calpeek").textContent), "the preview does not follow the pointer");
  D.dispatchEvent(W.ev("keydown",{key:"Escape"})); ok($("calpeek").hidden, "Escape does not put the preview away");
  Q(".cmn",cell("2026-04-01")).dispatchEvent(W.ev("pointerover",{pointerType:"mouse"})); W.advance(501);
  ok(!$("calpeek").hidden, "another day does not bring it back");
  $("cmgrid").dispatchEvent(W.ev("pointerleave",{bubbles:false})); W.advance(200);
  ok($("calpeek").hidden, "leaving the grid does not close the preview");
  const tap=cell("2026-04-03");
  tap.dispatchEvent(W.ev("pointerdown",{pointerType:"touch"})); tap.dispatchEvent(W.ev("pointerover",{pointerType:"touch"}));
  tap.focus(); tap.click(); await W.settle(); W.advance(900);
  ok($("calpeek").hidden, "a touch opened a preview");
  ok(W.sel()==="2026-04-03", "a tap does not select the day");
  const kf=cell("2026-03-31"); kf.focus(); W.advance(499);
  ok($("calpeek").hidden, "focus shows the preview sooner than the pointer does");
  W.advance(2);
  ok(!$("calpeek").hidden && kf.getAttribute("aria-describedby")==="calpeek", "focus on a day does not show its preview");
  // Focus that leaves the grid before the half second takes its preview
  // with it, rather than leaving one to open beside nothing.
  $("wkfind").focus(); ok($("calpeek").hidden, "focus leaving the grid left the preview open");
  // The last preview shown was the pointer's, as it is for a reader who
  // used the mouse before the keyboard: then only the pending one is left.
  Q(".cmn",cell("2026-04-01")).dispatchEvent(W.ev("pointerover",{pointerType:"mouse"})); W.advance(501);
  $("cmgrid").dispatchEvent(W.ev("pointerleave",{bubbles:false})); W.advance(200);
  const k2=cell("2026-03-30"); k2.focus(); W.advance(200); $("wkfind").focus(); W.advance(600);
  ok($("calpeek").hidden && !QA('[aria-describedby="calpeek"]',$("cmgrid")).length,
     "tabbing through the grid left a preview to open after focus had gone");
  // A day chosen with the mouse is on the panel; the focus its new cell is
  // given does not open its preview again.
  const mc=cell("2026-04-02");
  mc.dispatchEvent(W.ev("pointerover",{pointerType:"mouse"})); mc.focus(); mc.click(); await W.settle(); W.advance(900);
  ok(W.sel()==="2026-04-02" && $("calpeek").hidden, "a clicked day's preview came back half a second after the click");
  // A DAY THAT MOVES UNDER A STILL POINTER IS NOT POINTED AT. The click
  // scrolls the list, the sticky month moves up a row, and the browser says
  // the pointer, which has not moved, is over another day: pointerover there
  // at the very spot of the press. Its preview does not open; a real move
  // into it, reported before the move itself, does.
  const at=(x,y)=>({pointerType:"mouse",clientX:x,clientY:y});
  cell("2026-04-01").dispatchEvent(W.ev("pointerover",at(300,420)));
  cell("2026-04-01").dispatchEvent(W.ev("pointermove",at(300,420)));
  cell("2026-04-01").dispatchEvent(W.ev("pointerdown",at(300,420)));
  cell("2026-04-01").focus(); cell("2026-04-01").click(); await W.settle();
  cell("2026-03-31").dispatchEvent(W.ev("pointerover",at(300,420))); W.advance(900);
  ok(W.sel()==="2026-04-01" && $("calpeek").hidden,
     "a day that moved under a still pointer after a click opened its preview: "+$("calpeek").textContent);
  cell("2026-03-31").dispatchEvent(W.ev("pointerover",at(300,452))); W.advance(501);
  ok(!$("calpeek").hidden && /Tuesday, March 31/.test($("calpeek").textContent),
     "a real move into a day no longer opens its preview: "+$("calpeek").textContent);
  $("cmgrid").dispatchEvent(W.ev("pointerleave",{bubbles:false})); W.advance(200);
  // And a preview still waiting when a day is clicked is cancelled with it.
  cell("2026-03-30").dispatchEvent(W.ev("pointerover",at(120,420))); W.advance(200);
  cell("2026-04-03").dispatchEvent(W.ev("pointerdown",at(160,420)));
  cell("2026-04-03").focus(); cell("2026-04-03").click(); await W.settle(); W.advance(900);
  ok(W.sel()==="2026-04-03" && $("calpeek").hidden, "a preview waiting when a day was clicked opened after the click: "+$("calpeek").textContent);
  // ---- the reader's today, not the build's ----
  const W2=world("calendar.html","/calendar",{today:[2026,3,18]});
  await W2.run();
  ok(W2.sel()==="2026-03-18" && W2.Q(".calhead h1").textContent==="The Week of March 16–20, 2026"
     && W2.keys().join()==="2026-03-18|House Judiciary,2026-03-18|Senate Finance", "a reader a week after the build is not shown their own week: "+W2.sel());
  ok(W2.Q('td[aria-current="date"]',W2.$("cmgrid")).getAttribute("data-d")==="2026-03-18", "today is the build's, not the reader's");
  ok(W2.Q('link[rel="canonical"]').getAttribute("href")==="https://graniterecord.org/calendar/2026-W12"
     && /^“The Week of March 16–20, 2026\.” Granite Record, https:\/\/graniterecord\.org\/calendar\/2026-W12\./.test(W2.QA(".pcite dd")[0].textContent),
     "the tab shows the reader's week and cites the build's: "+W2.QA(".pcite dd")[0].textContent);
  ok(W2.addr()==="/calendar", "the tab opened on the reader's week wrote an address: "+W2.addr());
  // THE DAY A WEEK OPENS ON IS ITS FIRST SITTING THE FILTERS SHOW. That
  // reader goes back to the week of 9 March, which opens on the 10th. With
  // hearings and votes unticked its first shown is the 11th: in the list
  // the mark follows, and the address still names no day; in the Day view
  // the day being read stays, and the address names it. Either way a reload
  // opens what was on the screen.
  const prev2=W2.Q(".calhead .wknav a.wkprev"); prev2.focus(); prev2.click(); await W2.step();
  ok(W2.sel()==="2026-03-10" && W2.addr()==="/calendar?week=2026-W11", "the week before opens on "+W2.sel()+" at "+W2.addr());
  await W2.tick("hearing",false); await W2.tick("exec",false);
  ok(W2.sel()==="2026-03-11" && W2.addr()==="/calendar?week=2026-W11&kinds=work,conf,floor,date",
     "the list's mark did not follow the filters to the first day they show: "+W2.sel()+" at "+W2.addr());
  const R3=reload(W2,{today:[2026,3,18]}); await R3.run();
  ok(R3.sel()==="2026-03-11" && R3.addr()===W2.addr(), "a reload after a filter opened "+R3.sel()+" at "+R3.addr());
  await W2.tick("hearing",true); await W2.tick("exec",true);
  ok(W2.sel()==="2026-03-10", "the mark did not come back with the boxes: "+W2.sel());
  // ---- a phone: the month folds to the week, and only the fold's own button is remembered ----
  const W4=world("calendar.html","/calendar",{narrow:true});
  await W4.run();
  const side4=W4.$("calside");
  ok(side4.classList.contains("folded"), "a phone does not open on the selected week alone");
  W4.$("cmnext").click(); await W4.settle();
  ok(!side4.classList.contains("folded") && !W4.store.has("gr.calendar.fold"), "a month arrow's unfolding was remembered as the reader's choice");
  ok(W4.addr()==="/calendar", "turning the month moved the reader to another address: "+W4.addr());
  W4.$("cmfold").click(); await W4.settle();
  ok(side4.classList.contains("folded") && W4.store.get("gr.calendar.fold")==="1"
     && W4.$("cmtitle").textContent==="March 2026" && W4.QA("tr.cmsel td",W4.$("cmgrid")).length===7,
     "folding while another month is shown does not show the selected week: "+W4.$("cmtitle").textContent);
  W4.store.delete("gr.calendar.fold");
  const t4=W4.Q('td[tabindex="0"]',W4.$("cmgrid")); t4.focus(); t4.dispatchEvent(W4.ev("keydown",{key:"ArrowDown"})); await W4.settle();
  ok(!side4.classList.contains("folded") && !W4.store.has("gr.calendar.fold"), "an arrow key's unfolding was remembered as the reader's choice");
  // ---- a key on an arrow keeps the arrow in view; a click shows the day ----
  // The head's arrows near the top of a long page, the foot's far down it,
  // and the day chosen between them.
  const L=(el)=>el.matches(".calhead .wknav a")?150:el.matches(".calend")?3000
    :el.matches(".calday.calsel")?1400:undefined;
  const W5=world("calendar.html","/calendar",{layout:L});
  await W5.run();
  const seen5=(el)=>{ const r=el.getBoundingClientRect(); return r.top>=0 && r.bottom<=800; };
  const press=async(el)=>{ el.focus(); el.dispatchEvent(W5.ev("click",{button:0,detail:0})); await W5.step(); };
  await press(W5.Q(".calhead .wknav a.wknext"));
  ok(W5.addr()==="/calendar?week=2026-W12" && W5.doc.activeElement===W5.Q(".calhead .wknav a.wknext")
     && seen5(W5.doc.activeElement),
     "Enter on the head's The week after scrolled it off the screen: top "+W5.doc.activeElement.getBoundingClientRect().top);
  await press(W5.Q(".calhead .wknav a.wkprev"));
  ok(W5.addr()==="/calendar?week=2026-W11" && W5.doc.activeElement===W5.Q(".calhead .wknav a.wkprev")
     && seen5(W5.doc.activeElement),
     "Enter on the head's The week before scrolled it off the screen: top "+W5.doc.activeElement.getBoundingClientRect().top);
  const nx5=W5.Q(".calhead .wknav a.wknext"); nx5.focus(); nx5.click(); await W5.step();
  ok(W5.Q(".calday.calsel",W5.$("calview")).getBoundingClientRect().top===0,
     "a click on The week after no longer brings the day chosen into view");
  // ---- a month file that does not load ----
  // The address moves to the week asked for, and so does everything that
  // names it: the heading, the tab's title, the canonical link and the
  // citation. The panel says which week it could not load, and links it;
  // with no days to go by, the week is on its Monday.
  const W6=world("calendar.html","/calendar",{files:(url)=>/\/calendar\/data\/2026-/.test(url)?null
    :(fs.existsSync(path.join(SITE,url.replace(/^\//,"")))?fs.readFileSync(path.join(SITE,url.replace(/^\//,"")),"utf8"):null)});
  await W6.run();
  const n6=W6.Q(".calhead .wknav a.wknext"); n6.focus(); n6.dispatchEvent(W6.ev("click",{button:0,detail:0}));
  await W6.step();
  const said6=W6.Q("p.calempty",W6.$("calview")), link6=said6&&W6.Q("a",said6);
  ok(W6.addr()==="/calendar?week=2026-W12" && W6.Q(".calhead h1").textContent==="The Week of March 16–20, 2026"
     && W6.doc.title==="The Week of March 16–20, 2026 | Granite Record"
     && W6.Q('link[rel="canonical"]').getAttribute("href")==="https://graniterecord.org/calendar/2026-W12"
     && /“The Week of March 16–20, 2026\.” Granite Record, https:\/\/graniterecord\.org\/calendar\/2026-W12\./.test(W6.QA(".pcite dd")[0].textContent),
     "a week whose file failed is at "+W6.addr()+" under the heading "+W6.Q(".calhead h1").textContent
       +", canonical "+W6.Q('link[rel="canonical"]').getAttribute("href"));
  ok(W6.Q(".calhead p.src").textContent==="The meetings of this week could not be loaded here."
     && W6.$("wkcount").textContent==="The meetings could not be loaded.",
     "the lead and the count of a week that did not load: "+W6.Q(".calhead p.src").textContent+" / "+W6.$("wkcount").textContent);
  ok(said6 && said6.textContent==="The week of March 16–20, 2026 could not be loaded here. Open it on its own page."
     && link6 && link6.getAttribute("href")==="/calendar/2026-W12",
     "the panel of a week that did not load says "+(said6&&said6.textContent));
  // ---- an address sent to somebody: a week, a day, a view and a box ----
  const W3=world("calendar.html","/calendar",{search:"?week=2026-W10&day=2026-03-03&view=day&kinds=hearing"});
  await W3.run();
  ok(W3.sel()==="2026-03-03" && !W3.view("day") && W3.view("list").getAttribute("aria-pressed")==="true" && W3.ticked()==="hearing"
     && W3.keys().join()==="2026-03-03|House Commerce" && W3.Q(".calhead h1").textContent==="The Week of March 2–6, 2026",
     "a shared address does not open on its week, day, view and box: "+W3.sel()+" "+W3.keys());
  // An address that asked for the Day view lands on the list at that day.
  ok(W3.addr()==="/calendar?week=2026-W10&day=2026-03-03&kinds=hearing" && W3.G.history.length===1,
     "a shared address that asked for the Day view did not land on the list: "+W3.addr());
  // The shell wrote the skip link for /calendar, which from here is another
  // page: it follows the address.
  ok(W3.Q("a.skip").getAttribute("href").replace("&view=day","")==="/calendar?week=2026-W10&day=2026-03-03&kinds=hearing#results",
     "the skip link of a shared address leaves it: "+W3.Q("a.skip").getAttribute("href"));
  // A fragment that is not a state -- the skip link's, reloaded -- is kept.
  const W3b=world("calendar.html","/calendar",{search:"?week=2026-W12",hash:"#results"});
  await W3b.run();
  ok(W3b.addr()==="/calendar?week=2026-W12#results" && W3b.sel()==="2026-03-18", "a reload after the skip link: "+W3b.addr()+" "+W3b.sel());
  // ---- reloading ----
  // The same address opened again, in the same browser: the same week, day,
  // view and filters, and the address as it was.
  const W7=world("calendar.html","/calendar");
  await W7.run();
  W7.Q('td[data-d="2026-03-19"]',W7.$("cmgrid")).click(); await W7.step();
  W7.view("week").click(); await W7.settle();
  await W7.tick("study",true);
  W7.Q('[data-body="H"]',W7.$("wkfilter")).click(); await W7.settle();
  const before=W7.addr(), R=reload(W7);
  await R.run();
  ok(before==="/calendar?week=2026-W12&day=2026-03-19&view=week&kinds=hearing,exec,work,conf,floor,study,date&chamber=house",
     "the address before the reload: "+before);
  ok(R.addr()===before && R.sel()==="2026-03-19" && R.view("week").getAttribute("aria-pressed")==="true"
     && R.ticked()==="hearing,exec,work,conf,floor,study,date" && R.Q('[data-body="H"]',R.$("wkfilter")).getAttribute("aria-pressed")==="true"
     && R.keys().join()===W7.keys().join() && R.Q(".calhead h1").textContent==="The Week of March 16–20, 2026",
     "a reload does not open what was on the screen: "+R.addr()+" "+R.sel()+" "+R.keys());
  // And Back after a reload is the browser's own: the calendar reads it.
  // The Study Committee box, once ticked, is this browser's choice too: the
  // plain tab opens with it ticked, and the reset control can take it off.
  const R2=world("calendar.html","/calendar",{store:W7.store});
  await R2.run();
  ok(R2.ticked()==="hearing,exec,work,conf,floor,study,date" && !R2.$("calreset").hidden && R2.$("wkcount").textContent==="6 meetings this week.",
     "the Study Committee box is not remembered in this browser: "+R2.ticked());
  // ---- a link written before 25 September ----
  // In a week's own page's hash: it opens what it showed, and is written
  // into the query in place, as one entry of history.
  const W8=world("calendar/2026-W10.html","/calendar/2026-W10",{hash:"#d=2026-03-03&v=day&what=hearing"});
  await W8.run();
  ok(W8.sel()==="2026-03-03" && W8.view("list").getAttribute("aria-pressed")==="true" && W8.ticked()==="hearing,floor,date"
     && W8.keys().join()==="2026-03-03|House Commerce", "an old address does not open on its day, view and filter: "+W8.ticked()+" "+W8.keys());
  ok(W8.addr()==="/calendar?week=2026-W10&kinds=hearing,floor,date" && W8.G.history.length===1,
     "an old address is not written into the query: "+W8.addr());
  // On the tab, naming another week and who was meeting.
  const W9=world("calendar.html","/calendar",{hash:"#d=2026-03-18&v=week&who=standing,floor"});
  await W9.run();
  ok(W9.sel()==="2026-03-18" && W9.view("week").getAttribute("aria-pressed")==="true" && W9.ticked()==="hearing,exec,work,conf,floor,date"
     && W9.keys().join()==="2026-03-18|House Judiciary,2026-03-18|Senate Finance"
     && W9.addr()==="/calendar?week=2026-W12&day=2026-03-18&view=week",
     "an old address on the tab: "+W9.addr()+" "+W9.keys());
  // ---- a week's own page, and the first move from it ----
  // /calendar/2026-W10 is the week's own address: it opens on its own week
  // and keeps its address; the first move goes to the calendar's own, and
  // Back returns to it.
  const WA=world("calendar/2026-W10.html","/calendar/2026-W10");
  await WA.run();
  ok(WA.sel()==="2026-03-03" && WA.addr()==="/calendar/2026-W10" && WA.Q("a.skip").getAttribute("href")==="/calendar/2026-W10#results",
     "a week's own page does not open on its week at its own address: "+WA.sel()+" "+WA.addr());
  const na=WA.Q(".calhead .wknav a.wknext"); na.focus(); na.click(); await WA.step();
  ok(WA.addr()==="/calendar?week=2026-W11" && WA.sel()==="2026-03-11" && WA.G.history.length===2,
     "the first move from a week's own page is at "+WA.addr());
  WA.G.history.back(); await WA.step();
  ok(WA.addr()==="/calendar/2026-W10" && WA.sel()==="2026-03-03" && WA.Q(".calhead h1").textContent==="The Week of March 2–6, 2026"
     && WA.keys().join()==="2026-03-03|House Commerce", "Back to a week's own page: "+WA.addr()+" "+WA.sel());
  // Reached by its file's name, as a preview served from the folder has it,
  // the calendar keeps to that name, so a reload there finds the page.
  const WB=world("calendar/2026-W10.html","/calendar/2026-W10.html");
  await WB.run();
  const nb=WB.Q(".calhead .wknav a.wknext"); nb.focus(); nb.click(); await WB.step();
  ok(WB.addr()==="/calendar.html?week=2026-W11", "a page reached by its file's name moved to "+WB.addr());
  // ---- the skip link's step in the history ----
  // A fragment is a step of history too. Back from it leaves the address
  // what it was, so nothing is drawn again: the month the reader had paged
  // to stays.
  WA.$("cmnext").click(); await WA.settle();
  WA.G.history.pushState(null,"",WA.G.location.pathname+WA.G.location.search+"#results");
  WA.Q(".calhead .wknav a.wknext").click(); await WA.step();
  WA.$("cmnext").click(); await WA.settle();
  const shown=WA.keys().join();
  WA.G.history.pushState(null,"",WA.G.location.pathname+WA.G.location.search+"#results");
  WA.G.history.back(); await WA.step();
  ok(WA.$("cmtitle").textContent==="April 2026" && WA.keys().join()===shown, "Back from the skip link drew the calendar again: "+WA.$("cmtitle").textContent);
  if(fails.length){ console.log(fails.join("\n")); process.exit(1); }
  console.log("the tab, a week's own page, a phone and shared, old and reloaded addresses: 3 views, the seven boxes and the side's filters, Back, reloading, the week named in the citation, canonical and skip link, focus on the arrows and after a redraw, the arrows kept in view after a key, 6 keys, the fold, the preview's timings and a day moved under a still pointer, and a month file that failed");
  console.log("OK");
})().catch(e=>{ console.log(fails.join("\n")); console.log("THREW "+e.stack); process.exit(2); });
"""


@check("frontend", "an interim study report's chip on the Reports tab is green where it recommends future "
       "legislation, red where it does not, and plain where it makes no recommendation")
def _interim_report_chip_colours():
    """The person's walk of the preview (30 October 2026). The chips were
    coloured by the motion's words (app.js RECCOLOUR), and none of an
    interim study report's matched, so every one was plain. Each wording
    the calendars and the docket use (build_site_v2.INTERIM_WORDS, the
    clerks' misspelt "Without Recomendation", 2014's "No Recommendation") is
    put to recColour in node, beside the motions whose colours must not
    move."""
    cases = [("RECOMMENDED FOR FUTURE LEGISLATION", "s-law"),
             ("Recommended for Future Legislation", "s-law"),
             ("NOT RECOMMENDED FOR FUTURE LEGISLATION", "s-done"),
             ("Not Recommended for Future Legislation", "s-done"),
             ("WITHOUT RECOMMENDATION", ""), ("Without Recomendation", ""), ("No Recommendation", ""),
             # As the clerks varied it (src/parse/interim_statements.py).
             ("RECOMMENDED FOR FURTHER LEGISLATION", "s-law"), ("NOT RECOMMENDED FOR LEGISLATION", "s-done"),
             ("NOT RECOMMENDED FOR FURTHER LEGISLATION", "s-done"),
             ("NOT RECOMMENDED FOR FUTURE RECOMMENDATION", "s-done"),
             ("OUGHT TO PASS", "s-law"), ("INEXPEDIENT TO LEGISLATE", "s-done"), ("INTERIM STUDY", "s-study"),
             ("RE-REFER TO COMMITTEE", "s-study")]
    got = _app_js("[" + ",".join(f"scope.recColour({json.dumps(w)})" for w, _ in cases) + "]",
                  names=("recColour",))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    bad = [f"{w!r} is {g!r}, not {want!r}" for (w, want), g in zip(cases, got) if g != want]
    assert not bad, "; ".join(bad)
    return "ok", f"{len(cases)} recommendations coloured: an interim report's three, and the motions as before"


@check("frontend", "a bill's tabs head their sections one way: an h2 in the serif at --t-h3, Title Case, "
       "as Summary's and a vote's are, with the capital label only inside a section")
def _bill_panes_one_heading():
    """The cohesion audit of 30 October 2026 (I-1): a bill's tabs drew five
    looks for one level. Summary's sections were 19px serif in Title Case,
    Reports' and the bill text's 20px capitals, Sponsors' capitals with a
    bare count, Documents' a 14px sans label with no h2 above it, and
    Related's 16px sans in sentence case. Each pane's sections are now an
    h2.sech, drawn as Summary's .w4h and a vote's .rcq are.

    Read three ways: the three rules agree in app.css; every h2 the panes'
    renderers write, from renderReports to renderRelated, is a .sech; and
    Documents, drawn in node, opens with one.

    THE SPONSORS ARE THE SUMMARY'S FIRST SECTION since 19 November 2026 (the
    owner), under its .w4h "Sponsors", each chamber's names an h3.spch set
    smaller than it."""
    css = _source("src/pages/app.css")
    won = {}
    for at, sel, body, _l in _css_rules(css):
        if at:
            continue
        for part in (x.strip() for x in re.split(r",(?![^()]*\))", sel)):
            won.setdefault(part, {}).update(dict(_css_decls(body)))
    bad = []
    for sel in (".sech", ".w4h", ".rcq"):
        d = won.get(sel, {})
        font = d.get("font", "")
        size = d.get("font-size") or (re.search(r"var\(--t-[\w-]+\)", font) or [None])[0]
        fam = d.get("font-family") or (re.search(r"var\(--(?:serif|sans)\)", font) or [None])[0]
        weight = d.get("font-weight") or (font.split()[0] if font else None)
        if (size, fam, weight) != ("var(--t-h3)", "var(--serif)", "600") or d.get("text-transform") != "none":
            bad.append(f"{sel} is {size} {fam} {weight}, text-transform {d.get('text-transform')}, "
                       "not --t-h3 serif 600 as typed")
    app = _source("src/pages/app.js")
    a, z = app.find("function renderReports("), app.find("function renderRelated(")
    z = app.find("\n}\n", z)
    assert -1 < a < z, "app.js has no renderReports or renderRelated"
    heads = re.findall(r"<h2(?:\s[^>]*)?>", app[a:z])
    plain = [h for h in heads if not re.search(r'class="[^"]*\bsech\b', h)]
    if not heads:
        bad.append("the bill panes' renderers write no h2 at all")
    if plain:
        bad.append(f"{len(plain)} of the panes' {len(heads)} h2s are not .sech: {plain[:3]}")
    if re.search(r'<h3 class="[^"]*\bdocgrp\b', app):
        bad.append("Documents heads its groups with a 14px label again, and no h2 above it")
    # Nothing more particular restyles them: a rule on the pane headings'
    # own classes or old selectors sets their margins and nothing more.
    for at, sel, body, _l in _css_rules(css):
        if at:
            continue
        d = dict(_css_decls(body))
        for part in (x.strip() for x in re.split(r",(?![^()]*\))", sel)):
            if re.search(r"(?:\.spgrp|\.docgrp|\.rephead (?:h2|h3|\.sech)|\.rl-g (?:h2|\.sech)|\.btsec > (?:h2|\.sech)"
                         r"|\.pane (?:> )?h2)$", part) and {"font", "font-size", "text-transform"} & set(d):
                bad.append(f"{part} sets {sorted({'font', 'font-size', 'text-transform'} & set(d))}, over .sech")
    # A label under "Bill Text" is smaller than "Bill Text".
    under = [d for sel, d in won.items() if sel.startswith(".btsec :is(") and "h3.amdsec" in sel]
    if not under or under[0].get("font-size") != "var(--t-ui)":
        bad.append("the labels under Bill Text (THE BILL, FISCAL IMPACT, HOW IT GOT HERE) are not --t-ui, "
                   "under a heading at --t-h3")
    sps = ('{sponsors: [{name: "A", chamber: "H", label: "Rep. A", prime: true}, '
           '{name: "B", chamber: "S", label: "Sen. B"}]}')
    drawn = _app_js(
        f'[scope.renderSummary({{id: "HB1"}}, {sps}), '
        'scope.renderDocuments({id: "HB1"}, {documents: [{kind: "text", label: "Bill text", '
        'url: "https://example.org/x.pdf"}]})]',
        names=("renderSummary", "renderDocuments"))
    if drawn is not None:
        summ, docs = drawn
        first = re.search(r"<h[1-6][^>]*>", docs)
        if not first or not re.match(r'<h2 class="[^"]*\bsech\b', first.group(0)):
            bad.append(f"Documents opens with {first.group(0) if first else 'no heading'}, not an h2.sech")
        sheads = re.findall(r"<h[1-6][^>]*>[^<]*", summ)
        if not (sheads[:3] == ['<h2 class="w4h">Sponsors', '<h3 class="spch">Representatives ',
                              '<h3 class="spch">Senators '] and summ.index('id="sponsors"') < summ.index("spch")):
            bad.append(f"the Summary does not open with Sponsors and its chambers under it: {sheads[:3]}")
    spch = won.get(".spch", {})
    if not re.match(r"600 var\(--t-ui\)/[\d.]+ var\(--sans\)", spch.get("font", "")):
        bad.append(f".spch is {spch.get('font')!r}, not a 600 --t-ui sans heading under the --t-h3 .w4h")
    assert not bad, "; ".join(bad[:6])
    return "ok", (f"{len(heads)} h2s in the bill panes, every one .sech, as Summary's and a vote's"
                  + ("" if drawn is None else "; Documents drawn opening with one, the Summary with "
                     "Sponsors and its chambers' h3s under it"))


@check("frontend", "a bill's Testify button counts the Senate's hearings, and says testimony may open again "
       "only while one chamber has heard it")
def _testify_box_senate():
    """The audit of 25 October 2026 (M2): the House's hearings are "public
    hearing" and the Senate's "hearing", and app.js's testifyBox read the
    House's word alone. SB 406 of 2026, heard by Senate Finance on 13 January,
    said testimony "has not opened yet"; CACR 13, heard in both chambers, that
    it "opens again" in the other; HB 282 named its House hearing of January
    and not the Senate's of 23 April. The box became the Testify button in
    the record head's row the same day (the person, 25 October 2026), and
    testifyButton holds to all of it: it is drawn in node for a bill of the
    sitting term (sittingTerm's own answer, so this holds in any year), its
    hearings either side of every possible today. A bill that has ended is
    told its hearing has passed and nothing of another chamber, and a bill of
    an earlier term has no button. workers/follow reads the Senate's word too;
    its case is tests/follow/mail.test.js's.

    The bill is a moving one as the site has it since the review of 25 October
    2026 (testifyMoving): its index row's kind "active", and a rail with the
    House ahead. The ended one has no kind, and its rail is crossed."""
    got = _app_js("""(() => {
  const term = scope.sittingTerm(new Date());
  const st = (what, when, body, committee) => ({what, when, body, committee});
  const moving = {rail: [{stop: "Introduced", mark: "p"}, {stop: "Senate", mark: "h"}, {stop: "House", mark: "-"},
                         {stop: "Governor", mark: "-"}, {stop: "Law", mark: "-"}]};
  const box = (stations, journey = moving, t = term, row = {n: "SB 406", kind: "active"}) =>
    scope.testifyButton({term: t, stations, journey}, row);
  return {
    senate: box([st("hearing", "2000-01-13", "S", "Finance")]),
    both: box([st("public hearing", "2000-01-21", "H", "Judiciary"),
               st("hearing", "2000-04-23", "S", "Judiciary")]),
    ahead: box([st("public hearing", "2000-01-21", "H", "Judiciary"),
                st("hearing", "2999-04-23", "S", "Judiciary")]),
    none: box([st("executive session", "2000-01-21", "H", "Judiciary")]),
    ended: box([st("hearing", "2000-01-13", "S", "Finance")],
               {rail: [{stop: "Introduced", mark: "p"}, {stop: "Senate", mark: "x"}]}, term, {n: "SB 406"}),
    old: box([st("hearing", "2999-01-13", "S", "Finance")], moving, "1999-2000"),
    // passed by the Senate and in the House now, unheard there
    inHouse: box([st("hearing", "2000-01-13", "S", "Finance")],
                 {rail: [{stop: "Introduced", mark: "p"}, {stop: "Senate", mark: "p"}, {stop: "House", mark: "h"},
                         {stop: "Governor", mark: "-"}, {stop: "Law", mark: "-"}]}),
    // and on the House's table, the owner's second case of the same line
    tabledInHouse: box([st("hearing", "2000-01-13", "S", "Finance")],
                 {rail: [{stop: "Introduced", mark: "p"}, {stop: "Senate", mark: "p"}, {stop: "House", mark: "t"},
                         {stop: "Governor", mark: "-"}, {stop: "Law", mark: "-"}]}),
  };
})()""", names=("testifyButton", "sittingTerm"))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    said = {k: " ".join(re.sub(r"<[^>]+>", " ", v).split()) for k, v in got.items()}
    assert "has not opened yet" not in said["senate"] and \
        "have closed as of January 13, 2000" in said["senate"], (
            f"a bill heard only by a Senate committee is told: {said['senate']!r}")
    # the other chamber named, for a Senate bill the House (the owner, 6 November 2026)
    assert "They may open again if the bill goes to the House and the House holds its own public " \
        "hearing." in said["senate"], (
        f"a bill heard in one chamber is no longer told testimony may open again in the other: {said['senate']!r}")
    assert "have closed as of April 23, 2000" in said["both"] and "open again" not in said["both"], (
        f"a bill heard in both chambers is told: {said['both']!r}")
    assert "The public hearing on SB 406 is scheduled for" in said["ahead"] \
        and "Senate Judiciary Committee" in said["ahead"] \
        and "gc.nh.gov/remotecommittee/senate.aspx" in got["ahead"] \
        and 'class="testify tlive"' in got["ahead"], (
            f"a Senate hearing still to come does not open the Senate's form: {said['ahead']!r}")
    assert "has not opened yet" in said["none"], f"a bill with no hearing is told: {said['none']!r}"
    assert "have closed as of" in said["ended"] and "open again" not in said["ended"], (
        f"a bill whose rail has ended is told: {said['ended']!r}")
    # in the House already, unheard there: the owner's shorter line (6 November 2026)
    assert "They may open again if the House holds its own public hearing." in said["inHouse"] \
        and "goes to" not in said["inHouse"], f"a Senate bill now in the House is told: {said['inHouse']!r}"
    assert "They may open again if the House holds its own public hearing." in said["tabledInHouse"] \
        and "goes to" not in said["tabledInHouse"], (
        f"a Senate bill on the House's table is told: {said['tabledInHouse']!r}")
    assert got["old"] == "", "a bill of an earlier term has a Testify button"
    return "ok", ("a Senate hearing is a public hearing, past or ahead; \"may open again\" only while one "
                  "chamber has heard it; an ended bill and an earlier term as before")


@check("frontend", "a bill opened from the search gets one Testify, its own term's, which a redraw leaves "
                   "open and which goes with the row when the list comes back")
def _testify_from_the_search():
    """The review of 25 October 2026. focusActions draws a bill's row when it
    is opened from the search: it fetches the bill's own page for Cite and the
    feed, mounts Follow, Print, Share and Report, and Testify. Its Testify was
    looked up by number alone, so on /bills?term=2023-2024, then 2025-2026 and
    HB 104, the heading read "HB 104-FN" and the pane "then the bill, HB 104",
    the earlier term's label; the next redraw, with the right row, drew the
    button again and shut the pane a reader had opened. The check that held
    it read only that focusActions' text named mountTestify, and a call that
    passed no record, which takes Testify off every bill opened from the
    search, got through it.

    So focusActions is run in node, against a page of nodes that answer
    getElementById and querySelector as a browser does for these, a fetch
    that answers at once with the bill's page, and an index holding HB 104 in
    the sitting term and in the one before it, the earlier first, with the
    sitting term's record already loaded (the usual case: the record comes
    before the page focusActions asks for). It must draw ONE Testify, live,
    after Follow, saying the sitting term's "HB 104-FN"; render()'s redraw,
    with the right row or with the earlier term's (render's own fallback
    finds by number), must leave that same button, so an open pane stays
    open; and dropFocusActions, the list coming back, must take the row away
    with Testify in it, leaving none on the page."""
    got = _app_js("""(() => {
  const N = (tag) => {
    const n = {tagName: tag, id: "", className: "", dataset: {}, hidden: false, children: [], parentNode: null,
      _html: "",
      get innerHTML() { return this._html; }, set innerHTML(v) { this._html = String(v); },
      get firstChild() { return this.children[0] || null; },
      get nextSibling() { const p = this.parentNode; return p ? p.children[p.children.indexOf(this) + 1] || null : null; },
      classList: {add(c) { n.className = (n.className + " " + c).trim(); },
                  remove(c) { n.className = n.className.split(/\\s+/).filter(x => x !== c).join(" "); },
                  contains(c) { return n.className.split(/\\s+/).includes(c); }},
      insertBefore(c, ref) { c.remove(); c.parentNode = this;
        const i = ref ? this.children.indexOf(ref) : -1;
        if (i < 0) this.children.push(c); else this.children.splice(i, 0, c); return c; },
      appendChild(c) { return this.insertBefore(c, null); },
      remove() { const p = this.parentNode; if (p) { p.children.splice(p.children.indexOf(this), 1); this.parentNode = null; } },
      before(c) { this.parentNode.insertBefore(c, this); },
      all() { return this.children.flatMap(c => [c, ...c.all()]); },
      querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
      querySelectorAll(sel) {
        const m = /^([#.])([\\w-]+)$/.exec(sel);
        if (!m) return [];
        return this.all().filter(x => m[1] === "#" ? x.id === m[2] : x.className.split(/\\s+/).includes(m[2]));
      },
      getAttribute() { return null; }, setAttribute() {},
    };
    return n;
  };
  const body = N("body"), results = N("div");
  results.id = "results";
  body.appendChild(results);
  document.getElementById = id => body.all().find(x => x.id === id) || null;
  document.querySelector = sel => body.querySelector(sel);
  document.querySelectorAll = sel => body.querySelectorAll(sel);
  document.createElement = tag => N(tag);
  document.importNode = n => n;
  // The bill's own page as shell.py writes its row: Cite, and the feed.
  globalThis.DOMParser = class { parseFromString() {
    const acts = N("div"), cite = N("details");
    acts.id = "pageacts"; acts.className = "pageacts"; cite.className = "pcite";
    acts.appendChild(cite);
    return {getElementById: id => id === "pageacts" ? acts : null,
            querySelector: sel => /rss/.test(sel) ? {getAttribute: () => "/feeds/bill.xml"} : null};
  } };
  // A fetch that answers at once, so the row is drawn before this returns.
  const now = v => (v && v.now) ? v : {now: true, then(f) { return now(f(v)); }, catch() { return this; }};
  const asked = [];
  globalThis.fetch = url => { asked.push(url); return now({ok: true, text: () => "<html></html>"}); };
  const sitting = scope.sittingTerm(new Date());
  const first = +sitting.slice(0, 4), before = `${first - 2}-${first - 1}`;
  // The earlier one ended; the sitting term's is still moving, so the row
  // that decides is the one whose kind the button follows (testifyMoving).
  const older = {id: "HB104", n: "HB 104", term: before, year: first - 2, title: "the earlier one", kind: "done"};
  const ours = {id: "HB104", n: "HB 104-FN", term: sitting, year: first, title: "this one", kind: "active"};
  scope.IDX.length = 0;
  scope.IDX.push(older, ours);
  scope.setTerm(sitting);
  scope.setFocused("HB104");
  const moving = {rail: [{stop: "Introduced", mark: "p"}, {stop: "House", mark: "h"}, {stop: "Senate", mark: "-"},
                         {stop: "Governor", mark: "-"}, {stop: "Law", mark: "-"}]};
  const d = {term: sitting, journey: moving,
             stations: [{what: "public hearing", when: "2999-01-13", body: "H", committee: "Housing"}]};
  scope.detail[scope.dkey("HB104")] = d;
  scope.focusActions("HB104");
  const row = document.getElementById("pageacts");
  const kids = row ? row.children.map(k => k.id || k.className) : [];
  const drawn = body.querySelectorAll(".testifyin");
  const one = drawn[0] || null;
  scope.mountTestify(ours, d);
  const keptRight = body.querySelectorAll(".testifyin")[0] === one;
  scope.mountTestify(older, d);
  const keptOlder = body.querySelectorAll(".testifyin")[0] === one;
  const afterRedraw = body.querySelectorAll(".testifyin").length;
  scope.dropFocusActions();
  return {asked, kids, count: drawn.length, html: one ? one.innerHTML : "", cls: one ? one.className : "",
          keptRight, keptOlder, afterRedraw,
          rowLeft: !!document.getElementById("pageacts"), left: body.querySelectorAll(".testifyin").length};
})()""", names=("focusActions", "dropFocusActions", "mountTestify", "sittingTerm", "IDX", "detail", "dkey",
                 "setTerm:(t)=>{term=t;}", "setFocused:(x)=>{focused=x;}"))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    said = " ".join(re.sub(r"<[^>]+>", " ", got["html"]).split())
    assert got["asked"] and got["asked"][0].endswith("/bill/2025/hb104"), (
        f"focusActions did not ask for the bill's own page: {got['asked']}")
    assert got["count"] == 1, f"a bill opened from the search has {got['count']} Testify buttons in its row"
    assert got["kids"] == ["pcite", "followbox", "testifyin tliverow", "reportbox"], (
        f"the row of a bill opened from the search reads {got['kids']}")
    assert got["html"].startswith('<details class="testify tlive">'), (
        f"the Testify of a bill opened from the search, its hearing ahead, is not live: {got['html'][:160]!r}")
    lp = " ".join(re.sub(r"<[^>]+>", " ", (re.search(r'<div class="testifypane">(.*)</div></details>',
                                                      got["html"], re.S) or [None, ""])[1]).split())
    assert lp.startswith("The public hearing on HB 104-FN is scheduled for") and lp.endswith(
        "House Housing Committee HB 104-FN") and "HB 104 " not in lp, (
        f"the Testify of the sitting term's HB 104 names another term's bill: {said!r}")
    assert got["keptRight"] and got["keptOlder"] and got["afterRedraw"] == 1, (
        "a redraw drew Testify again in the row of a bill opened from the search, which shuts a pane the "
        f"reader opened (kept with the right row: {got['keptRight']}, with the earlier term's: {got['keptOlder']})")
    assert not got["rowLeft"] and got["left"] == 0, (
        f"the list came back and left {got['left']} Testify on the page (the row: {got['rowLeft']})")
    return "ok", ("one live Testify after Follow, \"The public hearing on HB 104-FN\" with 2023's HB 104 first "
                  "in the index; a redraw with either row leaves it; gone with the row")


@check("frontend", "Testify tells a bill that can no longer be heard so: never \"has not opened yet\" or "
                   "\"opens again\" once it has stopped moving or its term has stopped sitting, and a hearing "
                   "still to come is never one that has passed")
def _testify_when_it_cannot_open():
    """The review of 25 October 2026 read every one of the 2,243 records of
    the sitting term on the preview. testifyButton took a bill to have ended
    only where its rail's last mark was a check or a cross, and 46 were told
    what could not happen: HR 17, which died on the table unheard (its rail
    ends in the pause, "t"), and HR 48, adopted, whose rail is empty, that
    testimony "opens once a public hearing is scheduled"; 44 others -- HR 38,
    CACR 1, 4, 20 and 22, HCR 1, 14 and 16 among them -- that "It opens again
    if the bill is scheduled for a hearing in the other chamber", though they
    could not be heard again, an HR has no other chamber, and the term had
    stopped sitting on 19 August.

    It asks now what the site already asks to say a bill has stopped moving
    (testifyMoving): the record's session_over before New Hampshire's today;
    then the index row's kind, "active" alone still moving, the row that
    mountTestify chooses for the record's own term; then, where no row says,
    the rail. "It opens again" only for a bill still moving whose rail has
    another chamber not yet decided. Each of the review's shapes is drawn
    here, through mountTestify where the row is the index's, so that the row
    it chooses is the one that decides:

      HR 17, [Introduced p, House t], kind done: "did not open"; and with no
        row, by its rail alone, the same -- the pause is a bill on the table
        and a bill that died there alike, so it does not say "moving".
      A CACR, [House x, Senate -, Voters -], heard: passed, no "opens again";
        the same with no row, by its rail alone.
      An HCR, [House p, Senate -], its passage ending in a cross: passed, no
        "opens again".
      HR 48, adopted, an empty rail: "did not open"; and with no row at all.
      An HCR whose session_over has passed, its row still "active" (an index
        a night old): no "opens again", and unheard, "did not open"; with
        session_over still ahead, the same bill is told it opens again.
      An HR still moving, heard: passed, and no other chamber named.
      SB 403, sent to interim study by the Senate that heard it (kind
        "study", which Follow keeps followable): passed, no "opens again".
      An HB still moving, heard by the House alone, whose rail has the
        Senate's check already: passed, no "opens again".
      With no row, a rail crossed anywhere: ended, whatever ring it has.
      An HB still moving, heard by the House, the Senate ahead: "opens again";
        and with no row, by a rail with the ring on the Senate, the same.
      An HB on the House's table while the session sits, heard, its row
        "active" and its rail the pause: the row decides, "opens again".
      A bill that has stopped moving with a hearing still on its record
        ahead (withdrawn after it was noticed): no live button, and "did not
        open", since nothing will be heard.

    The preview's 2,243 records of the sitting term, read again with this on
    26 October 2026, each with the row mountTestify picks: 2,218 told their
    hearing has passed and nothing more, 25 that testimony did not open (HR 17,
    HR 48, HB 1786, the resolutions adopted unheard, the withdrawn bills),
    none "opens again" and none "not opened yet"; and the same with every row
    taken away, by the rails alone.

    AND A HEARING STILL TO COME IS NEVER ONE THAT HAS PASSED (the same
    review). The live button looked its form up by the station's body alone,
    so a hearing ahead whose body was neither H nor S fell through to the shut
    button and could be named as the hearing that "has passed". A hearing's
    chamber is now its body, or the chamber whose word the station uses
    ("public hearing" the House's, "hearing" the Senate's): one ahead with no
    body, or a body of neither, is the live button with that chamber's form,
    and the passed sentence names only a day that has gone."""
    got = _app_js("""(() => {
  const term = scope.sittingTerm(new Date());
  const st = (what, when, body) => ({what, when, body, committee: "Judiciary"});
  const R = (...marks) => ({rail: marks.map(([stop, mark]) => ({stop, mark}))});
  const heardH = [st("public hearing", "2000-01-21", "H")];
  // The index as mountTestify reads it: rows of the sitting term.
  const rows = {
    HR17: {id: "HR17", n: "HR 17", term, kind: "done", chip: "Died", passage: "Hxx"},
    CACR4: {id: "CACR4", n: "CACR 4", term, kind: "done", chip: "Died", passage: "Hx--x"},
    HCR14: {id: "HCR14", n: "HCR 14", term, kind: "done", chip: "Died", passage: "Hp--x"},
    HR48: {id: "HR48", n: "HR 48", term, kind: "adopted", chip: "Adopted by the House", passage: ""},
    HCR9: {id: "HCR9", n: "HCR 9", term, kind: "active", chip: "Passed one chamber", passage: "Hph--"},
    HR5: {id: "HR5", n: "HR 5", term, kind: "active", chip: "In committee", passage: "Hh-"},
    HB7: {id: "HB7", n: "HB 7", term, kind: "active", chip: "Passed one chamber", passage: "Hph--"},
    HB9: {id: "HB9", n: "HB 9", term, kind: "active", chip: "Tabled", passage: "Hh---"},
    HB11: {id: "HB11", n: "HB 11", term, kind: "done", chip: "Withdrawn", passage: "Hx--x"},
    SB403: {id: "SB403", n: "SB 403", term, kind: "study", chip: "Interim Study", passage: "Sx--x"},
    HB13: {id: "HB13", n: "HB 13", term, kind: "active", chip: "Passed both chambers", passage: "Hpp--"},
  };
  scope.IDX.length = 0;
  Object.values(rows).forEach(r => scope.IDX.push(r));
  // mountTestify into a row of its own, handed the number alone, as
  // focusActions hands it; what it drew comes back.
  const acts = () => {
    const kids = [];
    return {kids, querySelector(sel) {
      if (sel === ".testifyin") return kids.find(k => /testifyin/.test(k.className || "")) || null;
      return null; },
      insertBefore(n) { n.remove = () => kids.splice(kids.indexOf(n), 1); kids.push(n); },
      get firstChild() { return kids[0] || null; }};
  };
  const mount = (id, d) => {
    const a = acts(), was = document.getElementById;
    document.getElementById = x => x === "pageacts" ? a : was(x);
    try { scope.mountTestify({id, n: id}, Object.assign({term}, d)); } finally { document.getElementById = was; }
    return a.kids.map(k => k.innerHTML).join("");
  };
  const bare = (d, n) => scope.testifyButton(Object.assign({term}, d), {n});
  const hcr9 = (stations, over) => Object.assign({stations,
    journey: R(["Introduced", "p"], ["House", "p"], ["Senate", "h"])}, over ? {session_over: over} : {});
  return {
    hr17: mount("HR17", {stations: [], journey: R(["Introduced", "p"], ["House", "t"])}),
    // With no row, by the rail alone: the pause is a bill on the table and a
    // bill that died there alike, so it is not taken to be moving; the ring
    // of a bill in a chamber now is.
    hr17Bare: bare({stations: [], journey: R(["Introduced", "p"], ["House", "t"])}, "HR 17"),
    movingBare: bare({stations: heardH, journey: R(["Introduced", "p"], ["House", "p"], ["Senate", "h"],
                                                   ["Governor", "-"], ["Law", "-"])}, "HB 7"),
    cacr4: mount("CACR4", {stations: heardH,
      journey: R(["Introduced", "p"], ["House", "x"], ["Senate", "-"], ["Voters", "-"])}),
    cacrBare: bare({stations: heardH,
      journey: R(["Introduced", "p"], ["House", "x"], ["Senate", "-"], ["Voters", "-"])}, "CACR 4"),
    hcr14: mount("HCR14", {stations: heardH, journey: R(["Introduced", "p"], ["House", "p"], ["Senate", "-"])}),
    hr48: mount("HR48", {stations: [], journey: {}}),
    hr48Bare: bare({stations: [], journey: {rail: []}}, "HR 48"),
    overHeard: mount("HCR9", hcr9(heardH, "2000-08-19")),
    overUnheard: mount("HCR9", hcr9([], "2000-08-19")),
    sitting: mount("HCR9", hcr9(heardH, "2999-08-19")),
    hr5: mount("HR5", {stations: heardH, journey: R(["Introduced", "p"], ["House", "h"])}),
    hb7: mount("HB7", {stations: heardH, journey: R(["Introduced", "p"], ["House", "p"], ["Senate", "h"],
                                                    ["Governor", "-"], ["Law", "-"])}),
    // On the House's table while the session sits: its rail's pause says
    // nothing either way, and its row says it is still moving.
    tabled: mount("HB9", {stations: heardH, journey: R(["Introduced", "p"], ["House", "t"], ["Senate", "-"],
                                                       ["Governor", "-"], ["Law", "-"])}),
    // Sent to interim study by the Senate that heard it: Follow keeps a
    // study followable (shell.still_moving), but it is not heard again.
    sb403: mount("SB403", {stations: [st("hearing", "2000-01-21", "S")],
      journey: R(["Introduced", "p"], ["Senate", "s"], ["House", "-"], ["Governor", "-"], ["Law", "x"])}),
    // Still moving, heard by the House alone, and the Senate has passed it
    // already (back in the House to concur): the Senate will not hear it.
    hb13: mount("HB13", {stations: heardH, journey: R(["Introduced", "p"], ["House", "p"], ["Senate", "p"],
                                                      ["Governor", "-"], ["Law", "-"])}),
    // With no row, a rail with a cross on it has ended, whatever ring it
    // also carries.
    crossedBare: bare({stations: heardH, journey: R(["Introduced", "p"], ["House", "h"], ["Senate", "-"],
                                                    ["Governor", "-"], ["Law", "x"])}, "HB 15"),
    // Withdrawn after its hearing was noticed: the station is still ahead.
    endedAhead: mount("HB11", {stations: [st("public hearing", "2999-04-23", "H")],
                               journey: R(["Introduced", "p"], ["House", "x"])}),
    // A hearing ahead whose body names neither chamber.
    noBody: mount("HB7", {stations: [st("hearing", "2999-04-23", "")], journey: R(["Introduced", "p"])}),
    jointBody: mount("HB7", {stations: [st("public hearing", "2000-01-21", "H"), st("public hearing", "2999-04-23", "J")],
                             journey: R(["Introduced", "p"])}),
    april: scope.dateWords("2999-04-23", "day"),
  };
})()""", names=("testifyButton", "sittingTerm", "mountTestify", "IDX", "dateWords"))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    said = {k: " ".join(re.sub(r"<[^>]+>", " ", v).replace("&rsquo;", "’").split()) for k, v in got.items()}
    did_not = "Online testimony did not open for this bill: it had no public hearing."
    passed = "Online testimony submissions for this bill have closed as of January 21, 2000."
    again = "They may open again if"
    for name in ("hr17", "hr17Bare", "hr48", "hr48Bare", "overUnheard", "endedAhead"):
        assert did_not in said[name] and "not opened yet" not in said[name], (
            f"{name}, which can no longer be heard and never was, is told: {said[name]!r}")
        assert 'class="testify toff"' in got[name], f"{name}'s Testify is not greyed: {got[name][:120]!r}"
    for name in ("cacr4", "cacrBare", "hcr14", "overHeard", "hr5", "sb403", "hb13", "crossedBare"):
        assert passed in said[name] and again not in said[name], (
            f"{name}, which cannot be heard in another chamber, is told: {said[name]!r}")
    for name in ("sitting", "hb7", "movingBare", "tabled"):
        assert passed in said[name] and again in said[name], (
            f"{name}, still moving with the other chamber ahead, is not told testimony may open again there: "
            f"{said[name]!r}")
    # THE OWNER'S TWO LINES (6 November 2026): a bill already in the other
    # chamber, unheard there (its stop "h"), is told only of that chamber's
    # hearing; one that has not reached it ("-") that it must go there first
    for name in ("sitting", "hb7", "movingBare"):
        assert "They may open again if the Senate holds its own public hearing." in said[name] \
            and "goes to" not in said[name], (
            f"{name}, in the Senate already and unheard there, is told: {said[name]!r}")
    assert "They may open again if the bill goes to the Senate and the Senate holds its own public " \
        "hearing." in said["tabled"], f"a bill that has not reached the Senate is told: {said['tabled']!r}"
    for name, url in (("noBody", "gc.nh.gov/remotecommittee/senate.aspx"),
                      ("jointBody", "gc.nh.gov/house/committees/remotetestimony/")):
        h = got[name]
        assert 'class="testify tlive"' in h, (
            f"{name}, a hearing still to come whose body is not H or S, is not live: {h[:160]!r}")
        assert "has passed" not in said[name] and f"The public hearing on HB 7 is scheduled for {got['april']}" \
            in said[name] and url in h, (
                f"{name}, a hearing ahead whose body is not H or S, is told: {said[name]!r}")
    return "ok", ("HR 17 and HR 48 \"did not open\", by their rows and by their rails; a CACR, an HCR, an HR "
                  "and a term past its session_over not told \"opens again\", a moving bill with the other "
                  "chamber ahead told it; an ended bill's hearing ahead not live; a hearing ahead with no "
                  "body, or a body of neither chamber, live with its word's chamber's form")


@check("frontend", "Testify counts a public hearing on a proposed amendment, which the House holds on a "
                   "bill already heard and no station stands for")
def _testify_hears_an_amendment():
    """The review of 26 October 2026. The House's docket line "Public Hearing
    on non-germane Amendment # 2026-0422h: 02/03/2026 11:20 am GP234" is a
    public hearing on the bill, and the House's online sign-in takes
    positions for it -- 1,904 for HB 1560-FN's -- but no station stands for
    it, and testifyButton read the stations alone. On 21 bills of 2025-2026
    the greyed pane named the wrong last hearing (CACR 12's "Mar 9, 2026",
    where its Summary has 1,820 signed in on April 15), and staged as the
    nightly had them, HB 1560-FN on 30 January, CACR 12 on 13 April and SB 56
    on 20 April were greyed as passed with a hearing days away. app.js's
    testifyHearings reads them from the record's events.

    Run in node on the shape of HB 1560-FN of 2026 -- its own House hearing
    on 27 January, then one on a proposed non-germane amendment on 3 February
    -- at a moment named for each case:

      30 JANUARY: live, "Testify until Feb 3", the House's form, its pane
        "The public hearing on a proposed non-germane amendment (2026-0422h)
        to HB 1560-FN is scheduled for Tuesday, February 3 at 11:20 AM in
        Granite Place 234", and the committee that has the bill to choose.
      5 FEBRUARY: greyed, its last public hearing Feb 3, 2026.
      CACR 12's, at 03:00 pm in "SH Reps Hall" after hearings in both
        chambers: live on 13 April "at 3:00 PM in Representatives' Hall, State
        House", and after it, its last public hearing Apr 15, 2026.
      A LINE THE DOCKET CALLED OFF (called_off): no hearing; on 30 January
        the bill's hearing has passed, on Jan 27.
      SB 210 of 2025's "Public Hearing on Amendment # 2025-2318h: 05/27/2025
        ...", entered on 21 May: the hearing is the line's day, the 27th.
      A ROW A PERSON CORRECTED (date_as_recorded): the corrected day.
      A HOUSE STATION ALREADY AT THAT DAY AND TIME: one hearing, not two.
      TWO ON ONE DAY, the amendment's first (09:30, the bill's own at 10:00):
        the pane names the first.

    THE COMMITTEE THAT HAS THE BILL THAT DAY (the review of 26 October
    2026). The committee to choose was the record's house_committee, the
    bill's first House referral, and the House's form lists the bill under
    the committee holding the hearing. Staged on the preview, HB 71-FN on 14
    March 2025 named Education Policy and Administration for Finance's
    hearing of the 17th, and HB 524-FN on 27 October 2025 Health, Human
    Services and Elderly Affairs for Ways and Means' of the 29th (5,441
    signed in). So, on their shapes:

      HB 524-FN, referred to Ways and Means on 6 March 2025, which held its
        executive session at 10:00 on 29 October in GP 159, the hearing on
        2025-3021h at 10:10 in the same room: "House Ways and Means
        Committee". With a second meeting that day, of another committee in
        another room nearer the time and listed first, the line's room
        decides, not the order; with two that day, neither in the line's
        room, the nearer time; a Senate committee's meeting that day, in the
        line's room at its time, is not the House's; with no referral on the
        record, that day's meeting alone says Ways and Means; and with
        neither, the last House meeting before the day, which a station of
        the floor, naming the chamber, is not. The record has Ways and
        Means' meeting alone that day: the others are made up to test the
        choice.
      HB 71-FN, referred to Education Policy and Administration and, on 6
        February 2025, to Finance, Finance meeting on the 17th: "House
        Finance Committee". The record dates Education Policy and
        Administration's executive session 27 January; the fixture puts it
        on 6 February, the referral's day, to test the tie. So with no
        Finance meeting on the record, the referral alone says Finance, a
        referral and a meeting on one day taken as the referral, since the
        committee meets before the House sends the bill on; and a referral
        dated the hearing's own day, with no meeting that day, is one. A row
        citing the Senate's journal or its calendar, one the docket called
        off, one naming no committee ("Rereferred to Committee"), one dated
        after the hearing, or one to interim study, is not a House referral;
        a row re-referring it to a committee by name is. No row of the
        sitting term is a referral on the day of a hearing, a row of the
        Senate's calendar naming a committee, a referral called off or a
        re-referral by name: those cases are made up to hold the rule. And a
        House hearing whose station names no committee is given the same:
        Finance, not the first referral.
      HB 197-FN, its rows as the record has them: introduced on 8 January
        2025 and referred to Executive Departments and Administration, and
        the same day "Vacated and Referred to Finance (Rep. C. McGuire): MA
        VV 01/08/2025": "House Finance Committee" -- the later of the day's
        two referrals, and the committee's name alone, not what the line
        says after it. Its hearing of 23 January is Finance's on the record;
        the fixture leaves that station's committee off, so that with no
        meeting before it the referrals decide.
      A 12:30 PM LINE, HB 1199-FN's "02/03/2026 12:30 pm SH Representatives
        Hall": "at 12:30 PM in Representatives' Hall, State House", not
        "24:30" -- the noon hour is the one wrap of the line's clock no
        other case runs."""
    got = _app_js("""(() => {
  const moving = {rail: [{stop: "Introduced", mark: "p"}, {stop: "House", mark: "h"}, {stop: "Senate", mark: "-"},
                         {stop: "Governor", mark: "-"}, {stop: "Law", mark: "-"}]};
  const row = {id: "HB1560", n: "HB 1560-FN", kind: "active"};
  const own = {what: "public hearing", when: "2026-01-27", time: "10:40", body: "H", committee: "Transportation",
               venue: "GP 232"};
  const exec = {what: "executive session", when: "2026-02-10", time: "10:00", body: "H", committee: "Transportation"};
  const ev = (date, text, more) => Object.assign({date, text, routine: false}, more || {});
  const amd = "Public Hearing on non-germane Amendment # 2026-0422h: 02/03/2026 11:20 am GP234";
  const rec = (events, stations) => ({term: "2025-2026", house_committee: "Transportation", senate_committee: "",
    journey: moving, stations: stations || [own, exec],
    events: [ev("2026-01-27", "Public Hearing: 01/27/2026 10:40 am GP 232")].concat(events)});
  const at = (d, iso, r) => scope.testifyButton(d, r || row, new Date(iso));
  const hb1300 = {term: "2025-2026", house_committee: "Commerce and Consumer Affairs", journey: moving,
    stations: [{what: "public hearing", when: "2026-01-20", time: "10:00", body: "H", committee: "Commerce and Consumer Affairs", venue: "GP 158"}],
    events: [ev("2026-01-20", "Public Hearing on non-germane Amendment # 2026-0093h: 01/20/2026 09:30 am GP 158")]};
  const same = {term: "2025-2026", house_committee: "Commerce and Consumer Affairs", journey: moving,
    stations: [{what: "public hearing", when: "2026-01-20", time: "10:15", body: "H", committee: "Commerce and Consumer Affairs", venue: "GP 158"}],
    events: [ev("2026-01-20", "Public Hearing on non-germane Amendment # 2026-0093h: 01/20/2026 10:15 am GP 158")]};
  const sb210 = {term: "2025-2026", house_committee: "Education Policy and Administration", journey: moving,
    stations: [{what: "hearing", when: "2025-02-11", time: "13:00", body: "S", committee: "Education", venue: "SH 100"}],
    events: [ev("2025-05-21", "Public Hearing on Amendment # 2025-2318h: 05/27/2025 10:00 am LOB 205-207")]};
  // CACR 12 of 2026: heard by Senate Finance, then House Ways and Means, then
  // in the afternoon in Representatives' Hall on a proposed amendment.
  const cacr12 = {term: "2025-2026", house_committee: "Ways and Means", senate_committee: "Finance",
    journey: {rail: [{stop: "Introduced", mark: "p"}, {stop: "Senate", mark: "p"}, {stop: "House", mark: "h"},
                     {stop: "Voters", mark: "-"}]},
    stations: [{what: "hearing", when: "2026-01-27", time: "13:15", body: "S", committee: "Finance", venue: "SH 103"},
               {what: "public hearing", when: "2026-03-09", time: "10:45", body: "H", committee: "Ways and Means",
                venue: "GP 159"}],
    events: [ev("2026-04-15", "Public Hearing on non-germane Amendment # 2026-1134h: 04/15/2026 03:00 pm SH Reps Hall")]};
  // THE COMMITTEE THAT HAS THE BILL THAT DAY. A House journal's row carries
  // its citation, as the record's do.
  const hj = (date, text) => ev(date, text, {cite: "HJ 7, page 57"});
  const H = (what, when, time, committee, venue) => ({what, when, time, body: "H", committee, venue});
  const HHS = "Health, Human Services and Elderly Affairs";
  // HB 524-FN of 2025-2026: its own hearing in HHS, sent to Ways and Means on
  // 6 March, Ways and Means' executive session at 10:00 on 29 October in GP
  // 159 and the hearing on 2025-3021h at 10:10 there.
  const hb524 = (stations, referred) => ({term: "2025-2026", house_committee: HHS,
    senate_committee: "Health and Human Services", journey: moving,
    stations: [H("public hearing", "2025-02-12", "10:30", HHS, "LOB 301-303"),
               {what: "floor debate", when: "2025-03-06", time: null, body: null, committee: "House"}].concat(stations),
    events: [hj("2025-01-09", "Introduced (in recess of) 01/09/2025 and referred to " + HHS)]
      .concat(referred === false ? [] : [hj("2025-03-06", "Referred to Ways and Means 03/06/2025")])
      .concat([ev("2025-10-29", "==CANCELLED== Public Hearing on non-germane Amendment # 2025-2982h: 10/29/2025 10:10 am GP159",
                  {called_off: true}),
               ev("2025-10-29", "Public Hearing on non-germane Amendment # 2025-3021h: 10/29/2025 10:10 am GP 159")])});
  const wmExec = H("executive session", "2025-10-29", "10:00", "Ways and Means", "GP 159");
  const r524 = {id: "HB524", n: "HB 524-FN", kind: "active"};
  // HB 71-FN of 2025-2026: heard and reported by Education Policy and
  // Administration, passed and sent to Finance on 6 February, the hearing on
  // 2025-0555h at 1:00 pm on 17 March in LOB 210-211, Finance's executive
  // session there at 1:15. The record dates Education Policy and
  // Administration's executive session 27 January; this puts it on 6
  // February, the referral's day, to test the tie. `sentOn` moves the
  // referral to Finance to another day.
  const EPA = "Education Policy and Administration";
  const mdy = iso => iso.slice(5, 7) + "/" + iso.slice(8, 10) + "/" + iso.slice(0, 4);
  const hb71 = (stations, more, sentOn = "2025-02-06") => ({term: "2025-2026", house_committee: EPA,
    senate_committee: "Judiciary", journey: moving,
    stations: [H("public hearing", "2025-01-22", "09:30", EPA, "LOB 205-207"),
               H("executive session", "2025-02-06", "09:00", EPA, "LOB 205-207")].concat(stations),
    events: [hj("2025-01-08", "Introduced 01/08/2025 and referred to " + EPA),
             hj(sentOn, "Referred to Finance " + mdy(sentOn))].concat(more || [],
            [ev("2025-03-17", "Public Hearing on non-germane Amendment # 2025-0555h: 03/17/2025 01:00 pm LOB 210-211")])});
  const r71 = {id: "HB71", n: "HB 71-FN", kind: "active"};
  // HB 197-FN of 2025-2026, its rows as the record has them: introduced on 8
  // January and referred to Executive Departments and Administration, then
  // the same day vacated from it and referred to Finance, the line going on
  // after the name. Its hearing of 23 January is Finance's on the record;
  // here that station names no committee, so that with no meeting before it
  // the two referrals of one day decide.
  const hb197 = {term: "2025-2026", house_committee: "Finance", senate_committee: "", journey: moving,
    stations: [H("public hearing", "2025-01-23", "10:00", "", "LOB 210-211")],
    events: [ev("2025-01-08", "Introduced 01/08/2025 and referred to Executive Departments and Administration",
                {cite: "HJ 2, page 10"}),
             ev("2025-01-08", "Vacated and Referred to Finance (Rep. C. McGuire): MA VV 01/08/2025", {cite: "HJ 2"}),
             ev("2025-01-23", "Public Hearing: 01/23/2025 10:00 am LOB 210-211")]};
  // HB 1199-FN of 2026: the hearing on 2026-0340h at 12:30 pm in the House
  // chamber, the committee's executive session there at the same time.
  const hb1199 = {term: "2025-2026", house_committee: "Fish and Game and Marine Resources",
    senate_committee: "Energy and Natural Resources", journey: moving,
    stations: [H("public hearing", "2026-01-28", "11:45", "Fish and Game and Marine Resources", "GP 153"),
               H("executive session", "2026-02-03", "12:30", "Fish and Game and Marine Resources",
                 "SH Representatives Hall")],
    events: [ev("2026-02-03", "Public Hearing on non-germane Amendment # 2026-0340h: 02/03/2026 12:30 pm SH Representatives Hall")]};
  return {
    hb524: at(hb524([wmExec]), "2025-10-27T16:00:00Z", r524),
    // The other committee's meeting, nearer the time, listed first: the
    // line's room decides, not the order.
    hb524Rooms: at(hb524([H("work session", "2025-10-29", "10:10", HHS, "LOB 301-303"), wmExec]),
                   "2025-10-27T16:00:00Z", r524),
    // Two committees meet that day, neither in the line's room (Ways and
    // Means' moved out of GP 159 for this): the nearer time decides.
    hb524Times: at(hb524([H("work session", "2025-10-29", "13:00", HHS, "LOB 301-303"),
                          H("executive session", "2025-10-29", "10:00", "Ways and Means", "LOB 202-204")]),
                   "2025-10-27T16:00:00Z", r524),
    // A Senate committee's meeting that day, in the line's room at its very
    // time, is not a House committee's.
    hb524Senate: at(hb524([wmExec, {what: "executive session", when: "2025-10-29", time: "10:10", body: "S",
                                    committee: "Health and Human Services", venue: "GP 159"}]),
                    "2025-10-27T16:00:00Z", r524),
    hb524Met: at(hb524([wmExec], false), "2025-10-27T16:00:00Z", r524),
    // A station of the chamber's floor, which names the chamber, is no
    // committee's meeting.
    hb524Before: at(hb524([H("public hearing", "2025-03-18", "10:30", "Ways and Means", "LOB 202-204"),
                           H("consent calendar", "2025-10-01", null, "House", null)], false),
                    "2025-10-27T16:00:00Z", r524),
    hb71: at(hb71([H("work session", "2025-02-14", "10:00", "Finance", "LOB 210-211"),
                   H("executive session", "2025-03-17", "13:15", "Finance", "LOB 210-211")]), "2025-03-14T16:00:00Z", r71),
    hb71Sent: at(hb71([]), "2025-03-14T16:00:00Z", r71),
    hb71NotTheHouse: at(hb71([], [ev("2025-03-10", "HB 71 is vacated from Finance and referred to Judiciary; (In recess 03/10/2025)",
                                     {cite: "SJ 9"}),
                                  ev("2025-03-11", "Rereferred to Committee, MA, VV; 03/11/2025"),
                                  ev("2025-03-12", "Committee Report: Referred to Interim Study, 03/12/2025; Vote 5-0; CC"),
                                  ev("2025-03-12", "==CANCELLED== Referred to Ways and Means 03/12/2025",
                                     {cite: "HJ 9", row_note: "A cancellation.", called_off: true}),
                                  ev("2025-03-13", "Committee Report: Referred to Ways and Means 03/13/2025; Vote 5-0",
                                     {cite: "SC 12"}),
                                  hj("2025-03-20", "Referred to Ways and Means 03/20/2025")]), "2025-03-14T16:00:00Z", r71),
    // Referred to Finance on the day of the hearing itself, no meeting that
    // day: the referral, not the last meeting before it.
    hb71OnTheDay: at(hb71([], [], "2025-03-17"), "2025-03-14T16:00:00Z", r71),
    // Re-referred to a committee by name: that committee.
    hb71Rereferred: at(hb71([], [hj("2025-03-10", "Rereferred to Ways and Means 03/10/2025")]),
                       "2025-03-14T16:00:00Z", r71),
    hb197: at(hb197, "2025-01-21T17:00:00Z", {id: "HB197", n: "HB 197-FN", kind: "active"}),
    // A House hearing whose station names no committee (HR 18's of 2025
    // did), after the referral: the committee that has the bill that day.
    hb71Nameless: at(hb71([H("public hearing", "2025-03-17", "13:00", "", "LOB 210-211")]), "2025-03-14T16:00:00Z", r71),
    hb1199: at(hb1199, "2026-02-01T17:00:00Z", {id: "HB1199", n: "HB 1199-FN", kind: "active"}),
    cacr12: at(cacr12, "2026-04-13T17:00:00Z", {id: "CACR12", n: "CACR 12", kind: "active"}),
    cacr12After: at(cacr12, "2026-04-16T17:00:00Z", {id: "CACR12", n: "CACR 12", kind: "active"}),
    before: at(rec([ev("2026-02-03", amd)]), "2026-01-30T17:00:00Z"),
    after: at(rec([ev("2026-02-03", amd)]), "2026-02-05T17:00:00Z"),
    called: at(rec([ev("2026-02-03", amd, {row_note: "A cancellation.", called_off: true})]), "2026-01-30T17:00:00Z"),
    sb210: at(sb210, "2025-05-23T17:00:00Z", {id: "SB210", n: "SB 210", kind: "active"}),
    corrected: at(rec([ev("2026-02-04", amd, {date_as_recorded: "2026-02-03"})]), "2026-02-04T03:00:00Z"),
    same: at(same, "2026-01-21T17:00:00Z", {id: "HB1300", n: "HB 1300", kind: "active"}),
    twoOneDay: at(hb1300, "2026-01-19T17:00:00Z", {id: "HB1300", n: "HB 1300", kind: "active"}),
    days: [scope.dateWords("2026-02-03", "day"), scope.dateWords("2026-02-03", "long")],
  };
})()""", names=("testifyButton", "dateWords"))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    flat = lambda h: " ".join(re.sub(r"<[^>]+>", " ", h).replace("&rsquo;", "’").split())
    pane = lambda h: flat((re.search(r'<div class="testifypane">(.*?)</div></details>', h, re.S) or [None, ""])[1])
    summ = lambda h: flat((re.search(r"<summary>(.*?)</summary>", h, re.S) or [None, ""])[1])
    vals = lambda h: [flat(x) for x in re.findall(r"<li>(.*?)</li>", h, re.S)]
    before = got["before"]
    assert before.startswith('<details class="testify tlive">') and summ(before) == "Testify until Feb 3", (
        "HB 1560-FN on 30 January, its hearing on a proposed amendment on 3 February, is not live: "
        f"{summ(before)!r} {pane(before)[:160]!r}")
    want = ("The public hearing on a proposed non-germane amendment (2026-0422h) to HB 1560-FN is scheduled for "
            f"{got['days'][0]} at 11:20 AM in Granite Place 234. Public testimony is open until midnight the "
            "day of the hearing.")
    assert pane(before).startswith(want), f"HB 1560-FN's live pane on 30 January reads {pane(before)!r}"
    assert vals(before) == [got["days"][1], "House Transportation Committee", "HB 1560-FN"] \
        and 'href="https://gc.nh.gov/house/committees/remotetestimony/"' in before, (
            f"HB 1560-FN's live pane gives {vals(before)} to choose, not the House's hearing of 3 February")
    after = got["after"]
    assert after.startswith('<details class="testify toff">') and pane(after) == (
        "Online testimony submissions for this bill have closed as of February 3, 2026. They may open again "
        "if the bill goes to the Senate and the Senate holds its own public hearing."), (
            f"HB 1560-FN on 5 February names another hearing as its last: {pane(after)!r}")
    assert summ(got["cacr12"]) == "Testify until Apr 15" and pane(got["cacr12"]).startswith(
        "The public hearing on a proposed non-germane amendment (2026-1134h) to CACR 12 is scheduled for "
        "Wednesday, April 15 at 3:00 PM in Representatives' Hall, State House.") \
        and vals(got["cacr12"]) == ["Wednesday, April 15, 2026", "House Ways and Means Committee", "CACR 12"], (
            f"CACR 12 on 13 April, its hearing on a proposed amendment at 3 p.m. on the 15th, reads "
            f"{summ(got['cacr12'])!r}: {pane(got['cacr12'])[:220]!r} {vals(got['cacr12'])}")
    assert pane(got["cacr12After"]) == "Online testimony submissions for this bill have closed as of " \
        "April 15, 2026.", f"CACR 12 after its hearing of 15 April reads {pane(got['cacr12After'])!r}"
    assert got["called"].startswith('<details class="testify toff">') \
        and "have closed as of January 27, 2026." in pane(got["called"]), (
            f"a hearing on an amendment the docket called off is counted: {pane(got['called'])!r}")
    assert got["sb210"].startswith('<details class="testify tlive">') and summ(got["sb210"]) == "Testify until May 27" \
        and pane(got["sb210"]).startswith("The public hearing on a proposed amendment (2025-2318h) to SB 210 is "
                                          "scheduled for Tuesday, May 27 at 10:00 AM in Legislative Office "
                                          "Building 205-207."), (
            f"SB 210's hearing on an amendment, its row entered on 21 May for the 27th, reads "
            f"{summ(got['sb210'])!r}: {pane(got['sb210'])[:200]!r}")
    assert summ(got["corrected"]) == "Testify until Feb 4", (
        f"a row a person corrected to 4 February keeps the clerk's day: {summ(got['corrected'])!r}")
    assert pane(got["same"]) == "Online testimony submissions for this bill have closed as of January 20, 2026. " \
        "They may open again if the bill goes to the Senate and the Senate holds its own public hearing.", (
            f"a House station and the line for it, one hearing, are counted as two: {pane(got['same'])!r}")
    assert " at 9:30 AM in Granite Place 158." in pane(got["twoOneDay"]) \
        and pane(got["twoOneDay"]).startswith("The public hearing on a proposed non-germane amendment (2026-0093h)"), (
            f"of two hearings on one day the pane does not name the first: {pane(got['twoOneDay'])[:200]!r}")
    # THE COMMITTEE THAT HAS THE BILL THAT DAY
    for name, day, cmte, num, said in (
            ("hb524", "Wednesday, October 29, 2025", "House Ways and Means Committee", "HB 524-FN",
             "that day's Ways and Means meeting in its room, and its referral"),
            ("hb524Rooms", "Wednesday, October 29, 2025", "House Ways and Means Committee", "HB 524-FN",
             "the meeting in the line's room, over another committee's nearer the time and listed first"),
            ("hb524Times", "Wednesday, October 29, 2025", "House Ways and Means Committee", "HB 524-FN",
             "the meeting nearer the line's time, of two that day in neither the line's room"),
            ("hb524Senate", "Wednesday, October 29, 2025", "House Ways and Means Committee", "HB 524-FN",
             "the House's meeting that day, not a Senate committee's in the line's room at its time"),
            ("hb524Met", "Wednesday, October 29, 2025", "House Ways and Means Committee", "HB 524-FN",
             "that day's Ways and Means meeting, with no referral on the record"),
            ("hb524Before", "Wednesday, October 29, 2025", "House Ways and Means Committee", "HB 524-FN",
             "the last House meeting before the day, Ways and Means', not the floor's, with nothing that day "
             "or referred"),
            ("hb71", "Monday, March 17, 2025", "House Finance Committee", "HB 71-FN",
             "Finance's meeting that day, and its referral"),
            ("hb71Sent", "Monday, March 17, 2025", "House Finance Committee", "HB 71-FN",
             "the referral to Finance, on the day of the last meeting of the committee it left"),
            ("hb71NotTheHouse", "Monday, March 17, 2025", "House Finance Committee", "HB 71-FN",
             "the House's referral, not a row of the Senate's journal or calendar, a row naming no committee, "
             "one called off or one after the day"),
            ("hb71OnTheDay", "Monday, March 17, 2025", "House Finance Committee", "HB 71-FN",
             "the referral dated the hearing's own day"),
            ("hb71Rereferred", "Monday, March 17, 2025", "House Ways and Means Committee", "HB 71-FN",
             "a re-referral to a committee by name"),
            ("hb197", "Thursday, January 23, 2025", "House Finance Committee", "HB 197-FN",
             "the later of a day's two referrals, its name alone"),
            ("hb71Nameless", "Monday, March 17, 2025", "House Finance Committee", "HB 71-FN",
             "the referral, for a House hearing whose station names no committee")):
        h = got[name]
        assert h.startswith('<details class="testify tlive">') and vals(h) == [day, cmte, num], (
            f"{name}: the committee to choose is not {cmte!r}, from {said}: {vals(h)} {pane(h)[:120]!r}")
    assert pane(got["hb71Nameless"]).startswith("The public hearing on HB 71-FN is scheduled for Monday, March 17 "
                                                "at 1:00 PM"), f"HB 71-FN's own hearing reads {pane(got['hb71Nameless'])!r}"
    assert pane(got["hb71"]).startswith("The public hearing on a proposed non-germane amendment (2025-0555h) to "
                                        "HB 71-FN is scheduled for Monday, March 17 at 1:00 PM in Legislative "
                                        "Office Building 210-211."), f"HB 71-FN's live pane reads {pane(got['hb71'])!r}"
    # A CASE NAMED FOR A REAL RECORD IS THE REAL THING, OR SAYS IT IS NOT
    # (the review of 26 October 2026). This check's words had HB 71-FN
    # referred to Finance on the day its executive session in Education
    # Policy and Administration "is also dated": that is the fixture's tie,
    # and the record dates the session 27 January. Its words and the
    # fixture's both say so.
    import inspect
    src = inspect.getsource(_testify_hears_an_amendment)
    words = [" ".join(x.split()) for x in (_testify_hears_an_amendment.__doc__ or "",
             src[src.index('_app_js("""'):src.index('""", names=')].replace("//", " "))]
    assert all("executive session is also dated" not in w and "to test the tie" in w
               and "The record dates Education Policy and Administration's executive session 27 January" in w
               for w in words), (
            "this check's words or its HB 71-FN fixture no longer say that the fixture's executive session of "
            "6 February is moved there to test the tie, the record's being on 27 January")
    # A 12:30 PM LINE
    assert pane(got["hb1199"]).startswith(
        "The public hearing on a proposed non-germane amendment (2026-0340h) to HB 1199-FN is scheduled for "
        "Tuesday, February 3 at 12:30 PM in Representatives' Hall, State House. Public testimony is open") \
        and vals(got["hb1199"]) == ["Tuesday, February 3, 2026", "House Fish and Game and Marine Resources Committee",
                                    "HB 1199-FN"], (
            f"HB 1199-FN's hearing at 12:30 pm on 3 February reads {pane(got['hb1199'])[:200]!r} {vals(got['hb1199'])}")
    return "ok", ("HB 1560-FN live on 30 January for its hearing on a proposed amendment of 3 February, and "
                  "passed on Feb 3 after it; a line called off, none; SB 210's on the line's day, a corrected "
                  "row on the person's; one hearing where a station stands for the line; two on one day in "
                  "order; HB 524-FN's and HB 71-FN's committee the one that has the bill that day, Ways and "
                  "Means and Finance, by the room, the time, the House's meetings and the House's referrals; "
                  "HB 197-FN's the later of a day's two referrals, Finance; HB 1199-FN's at 12:30 PM")


_AMENDMENT_LINK_HARNESS = r"""
require("./stub.js");
// The window's listeners, kept so that the page's own can be fired: the
// stub's window drops them.
const ON = {};
globalThis.addEventListener = (t, f) => { (ON[t] = ON[t] || []).push(f); };
const src = require("fs").readFileSync("./page.js", "utf8");
const scope = (0, eval)(src + "; ({testifyButton, renderVersions, verKey, VERS, VTEXT, amendmentAsked, "
  + "seekAmendment, AMENDMENT_HASH, AMENDMENT_FOUND, IDX, openTab})");
// SB 575 of 2026's two amendments heard on 4 May, as the version index lists
// a bill's amendments, by day and length, and the head of each text; listed
// first, a committee of conference's report whose head names the second
// after its own number.
const T = {
  "/versions/2026/SB575.a0.txt": "June 2, 2026 2026-2109-CofC 08/07 Committee of Conference Report on SB 575 ... that the "
    + "House recede from amendment 2026-1715h and adopt the following",
  "/versions/2026/SB575.a1.txt": "Rep. Ladd, Graf. 4 April 23, 2026 2026-1708h 05/09 Amendment to SB 575 Amend the bill by",
  "/versions/2026/SB575.a2.txt": "Rep. Ladd, Graf. 4 April 23, 2026 2026-1715h 05/09 Amendment to SB 575 Amend the bill by",
};
const asked = [];
globalThis.fetch = async u => {
  const p = new URL(u).pathname; asked.push(p);
  return T[p] === undefined ? {ok: false, status: 404, text: async () => ""} : {ok: true, status: 200, text: async () => T[p]};
};
const b = {id: "SB575", year: 2026, term: "2025-2026"};
const ix = {versions: [{title: "Introduced", date: "12/10/2025 09:00:00", text_url: "/versions/2026/SB575.0.txt"}],
  steps: [], amendments: Object.keys(T).map((u, j) => ({date: ["06/02/2026 12:00:00", "04/23/2026 10:00:00",
    "04/23/2026 10:05:00"][j], chars: T[u].length, text_url: u}))};
const moving = {rail: [{stop: "Introduced", mark: "p"}, {stop: "Senate", mark: "p"}, {stop: "House", mark: "h"}]};
const hb1560 = more => Object.assign({term: "2025-2026", house_committee: "Transportation", journey: moving,
  stations: [{what: "public hearing", when: "2026-01-27", time: "10:40", body: "H", committee: "Transportation",
              venue: "GP 232"}],
  events: [{date: "2026-02-03", routine: false,
            text: "Public Hearing on non-germane Amendment # 2026-0422h: 02/03/2026 11:20 am GP234"}]}, more || {});
const row = {id: "HB1560", n: "HB 1560-FN", kind: "active"};
const at = new Date("2026-01-30T16:00:00Z");
(async () => {
  const out = {};
  out.linked = scope.testifyButton(hb1560({id: "HB1560", year: 2026, namd: 1, nver: 1}), row, at);
  out.byRow = scope.testifyButton(hb1560({namd: 1, nver: 1}), Object.assign({year: 2026}, row), at);
  out.none = scope.testifyButton(hb1560({id: "HB1560", year: 2026, nver: 1}), row, at);
  out.hash = ["amendment-2026-0422h", "amendment-1715h", "amendment-", "2026/HB1560", "rep-2026-H-290"]
    .map(h => scope.AMENDMENT_HASH.test(h));
  const k = scope.verKey(b);
  scope.VERS[k] = ix;
  const seek = async said => {
    for (const u of Object.keys(T)) { delete scope.VTEXT[u]; delete scope.AMENDMENT_FOUND[u]; }
    asked.length = 0;
    scope.amendmentAsked(b, said);
    await scope.seekAmendment(k);
    return {asked: asked.slice(), html: scope.renderVersions(b, {nver: 1, namd: 3}),
            open: Object.keys(T).filter(u => typeof scope.VTEXT[u] === "string")};
  };
  out.second = await seek("amendment-2026-1715h");
  out.first = await seek("amendment-2026-1708h");
  out.yearless = await seek("amendment-1715h");
  out.missing = await seek("amendment-2026-9999h");
  out.notOne = await seek("2026/SB575");
  // THE TAB'S OWN ADDRESS: the link followed while the Bill Text tab is the
  // address moves only the fragment, and the page reads it on "hashchange",
  // on a bill's own page (GR_BILL) and nowhere else.
  scope.IDX.push({id: "SB575", n: "SB 575", year: 2026, term: "2025-2026"});
  const follow = async (bill, hash) => {
    for (const u of Object.keys(T)) { delete scope.VTEXT[u]; delete scope.AMENDMENT_FOUND[u]; }
    delete scope.openTab.SB575;
    scope.amendmentAsked(b, "");
    if (bill) window.GR_BILL = bill; else delete window.GR_BILL;
    location.hash = hash;
    (ON.hashchange || []).forEach(f => f({}));
    for (let i = 0; i < 50; i++) await new Promise(r => setImmediate(r));
    return {tab: scope.openTab.SB575 || null, open: Object.keys(T).filter(u => scope.AMENDMENT_FOUND[u])};
  };
  out.followed = await follow("2026/SB575", "#amendment-2026-1715h");
  out.offPage = await follow("", "#amendment-2026-1715h");
  out.notAmendment = await follow("2026/SB575", "#2026/SB575");
  process.stdout.write("\n@@" + JSON.stringify(out));
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


@check("frontend", "Testify's amendment number opens that amendment on the Bill Text tab: "
                   "/bill/<year>/<bill>/text#amendment-<number>, open and brought into view")
def _testify_amendment_link():
    """The person, 26 October 2026: "the amendment number should link to open
    it on the bill text tab". The live pane of a hearing on a proposed
    amendment names it -- "a proposed non-germane amendment (2026-0422h) to
    HB 1560-FN" -- and the number is a link to
    bill/2026/hb1560/text#amendment-2026-0422h: the Bill Text tab, its
    address since 14 September, at that amendment. Nothing on the site
    linked an amendment there before, and the tab had no way to open one from
    an address: it lists a bill's amendments by day and length, "Amendment of
    January 30, 2026", each opened by pressing it, and its version index does
    not carry their numbers. The number is in each amendment's own text, the
    first of its shape near the top, so app.js reads the texts in turn until
    the one whose first number is the one named, opens it alone, and brings
    it into view once the version's text above it has come.

    Held in node on HB 1560-FN's pane of 30 January and on SB 575 of 2026's
    two amendments heard on 4 May, listed after a committee of conference's
    report whose head names the second after its own number:
      THE LINK: the number, and only it, links there, with the bill's year and
        id from the record or else its index row, and the pane reads as it
        did; with no amendments on the tab (namd), the number is words alone.
      THE ADDRESS: "amendment-<number>", with or without its year; a bill's
        own fragment and a session day's report are not one.
      THE TAB: asked for 2026-1715h, the third text is opened and given the
        address's id, after reading the report and the first, which stay
        shut. The first, read no further than it; the second by its number
        without the year; a number none carries opens nothing and adds no
        id; and no fragment, nothing.
      THE PAGE: a bill's own page whose fragment is an amendment's is still
        that bill's, opens on the tab the path names and asks for the
        amendment; the same link followed on the tab's own address reads the
        new fragment -- the page's own "hashchange" listener fired, on SB
        575's page, turns to the Bill Text tab and opens 2026-1715h, and off a
        bill's page, or with a fragment that is no amendment's, does nothing
        (the review of 26 October 2026: a check of the handler's body alone
        passed with the listener bound to another event) -- and every redraw
        brings a found one into view, below
        the tab strip the page holds at the top of the window -- brought to
        the very top, its "Amendment of" line and its text's first were
        under the strip on the preview."""
    got = _node_app(_AMENDMENT_LINK_HARNESS)
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    flat = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h.replace("&nbsp;", " "))).strip()
    link = '(<a href="bill/2026/hb1560/text#amendment-2026-0422h">2026-0422h</a>)'
    for name in ("linked", "byRow"):
        h = got[name]
        assert link in h and h.count("<a href=\"bill/") == 1, f"{name}: the pane's amendment is not linked: {h[:600]}"
        assert "The public hearing on a proposed non-germane amendment (2026-0422h) to HB 1560-FN is scheduled " \
               "for Tuesday, February 3 at 11:20" in flat(h), f"{name}: the pane reads {flat(h)[:200]!r}"
    assert "amendment-2026-0422h" not in got["none"] and "(2026-0422h) to HB 1560-FN" in got["none"], (
        "a bill with no amendment on its Bill Text tab links the number anyway")
    assert got["hash"] == [True, True, False, False, False], f"the addresses read as an amendment's: {got['hash']}"
    a = [f"/versions/2026/SB575.a{j}.txt" for j in range(3)]
    s = got["second"]
    assert s["open"] == [a[2]] and s["asked"] == a, (
        f"asked for 2026-1715h, the tab read {s['asked']} and opened {s['open']}")
    assert re.search(r'<li id="amendment-2026-1715h"><button class="link"\s+data-vamd="[^"]*\|2">'
                     r'Amendment of Apr 23, 2026</button>[\s\S]*?<pre class="vtext">[^<]*2026-1715h', s["html"]) \
        and s["html"].count('<pre class="vtext">') == 1 and s["html"].count(' id="amendment-') == 1, (
            f"the second amendment heard is not the one open and addressed: {s['html'][-900:]}")
    assert got["first"]["open"] == [a[1]] and got["first"]["asked"] == a[:2] \
        and 'id="amendment-2026-1708h"' in got["first"]["html"], got["first"]
    assert got["yearless"]["open"] == [a[2]] and 'id="amendment-1715h"' in got["yearless"]["html"], got["yearless"]
    for name in ("missing", "notOne"):
        assert not got[name]["open"] and " id=\"amendment-" not in got[name]["html"], (name, got[name])
    assert not got["notOne"]["asked"], "with no amendment in the address the tab read amendments anyway"
    assert got["followed"] == {"tab": "6", "open": [a[2]]}, (
        "the link followed on the Bill Text tab's own address, its hashchange, did not turn to the tab and open "
        f"2026-1715h: {got['followed']}")
    for name in ("offPage", "notAmendment"):
        assert got[name] == {"tab": None, "open": []}, f"{name}: a hashchange that names no amendment of a bill's " \
            f"own page turned a tab or opened an amendment: {got[name]}"
    app = _source("src/pages/app.js")
    for need, what in (
            ('const h=said&&!(window.GR_BILL&&(AMENDMENT_HASH.test(said)||VOTE_HASH.test(said)))?said:(window.GR_BILL||"");',
             "a bill's own page whose fragment is an amendment's (or a vote's) is still that bill's"),
            ("if(t===\"6\"&&row){amendmentAsked(row,said);needVersions(row);}",
             "the Bill Text tab's address asks for the amendment its fragment names"),
            ("  jumpToTab();\n  jumpToAmendment();\n", "a redraw brings the amendment into view"),
            ('const held=strip&&getComputedStyle(strip).position==="sticky"?strip.getBoundingClientRect().height:0;\n'
             "  window.scrollTo(0,Math.max(0,li.getBoundingClientRect().top+window.scrollY-held-16));",
             "the amendment is brought into view below the tab strip a bill's page holds at the top"),
            ("  });\n  seekAmendment(key);\n}", "the version index's arrival looks for the amendment")):
        assert need in app, f"app.js: {what} no longer"
    return "ok", ("HB 1560-FN's 2026-0422h links to its Bill Text tab; SB 575's second amendment opened by its "
                  "number, alone, past a report naming it; by number without its year; none for a number "
                  "none carries; the bill's page, the tab's own address and the redraw read it")


_BILL_TEXT_AMD_HARNESS = r"""
require("./stub.js");
const src = require("fs").readFileSync("./page.js", "utf8");
const scope = (0, eval)(src + "; ({renderVersions, verKey, VERS, VTEXT, VMODE})");
const b = {id: "HB9", year: 2026, term: "2025-2026"};
const A = j => "/versions/2026/HB9.a" + j + ".txt";
const head = (n, w) => "Rep. Ames, Ches. 13 February 3, 2026 " + n + " 05/08 " + w + " to HB 9 Amend RSA 91-A:2, II and RSA 999:1 by";
// The index lists amendments by the day each was filed, not the docket's order.
const ix = {
  versions: [
    {title: "As Introduced", date: "01/05/2026 10:00:00", text_url: "/versions/2026/HB9.0.txt"},
    {title: "As Amended", date: "03/05/2026 10:00:00", text_url: "/versions/2026/HB9.1.txt",
     blocks_url: "/versions/2026/HB9.1.blocks.json"}],
  steps: [],
  amendments: [
    {date: "02/01/2026 10:00:00", chars: 90, text_url: A(0), num: "2026-0003s"},
    {date: "02/02/2026 10:00:00", chars: 91, text_url: A(1), num: "2026-0002h"},
    {date: "02/03/2026 10:00:00", chars: 92, text_url: A(2), num: "2026-0001h"},
    {date: "02/04/2026 10:00:00", chars: 93, text_url: A(3), num: "2026-9999h"},
    {date: "02/05/2026 10:00:00", chars: 94, text_url: A(4)}],
  rsa: {"RSA 91-A:2": "/laws/91-a#s2"}};
const facts = [
  {num: "2026-0001h", kind: "Committee Amendment", adopted: true, mover: "", vote_kind: "VV", date: "2026-02-10"},
  {num: "2026-0002h", kind: "Floor Amendment", adopted: false, mover: "Rep. Ames", vote_kind: "RC", date: "2026-02-10"},
  {num: "2026-0003s", kind: "Amendment", adopted: null, mover: "", vote_kind: "", date: "2026-02-11"},
  {num: "2026-0004s", kind: "Floor Amendment", adopted: true, mover: "Sen. Birdsell", vote_kind: "VV",
   date: "2026-02-12", text: "Amend RSA 91-A:2 by"},
  {num: "2026-0005s", kind: "Committee Amendment", adopted: null, mover: "", vote_kind: "", date: ""}];
scope.VERS[scope.verKey(b)] = ix;
const T = {};
[head("2026-0003s", "Amendment"), head("2026-0002h", "Floor Amendment"), head("2026-0001h", "Amendment"),
 head("2026-9999h", "Amendment"), "February 5, 2026 no number printed Amendment"].forEach((t, j) => { T[A(j)] = t; });
Object.assign(scope.VTEXT, T);
scope.VTEXT["/versions/2026/HB9.1.blocks.json"] = [
  {k: "ln", runs: [["", "Nothing under "], ["add", "RSA 91-A:2, II"], ["cut", " and RSA 999:1"], ["", " here."]]}];
scope.VTEXT["/versions/2026/HB9.1.txt"] = "plain RSA 91-A:2";
const out = {};
out.facts = scope.renderVersions(b, {nver: 2, namd: 5, amendments: facts, rsa: {}});
out.bare = scope.renderVersions(b, {nver: 2, namd: 5, rsa: {}});
// the text view as plain text, and the changes view as a runs excerpt
const ix2 = Object.assign({}, ix, {steps: [{from: 0, to: 1, added: 1, removed: 0,
  runs_url: "/versions/2026/HB9.0-1.json"}]});
scope.VERS[scope.verKey(b)] = ix2;
scope.VMODE[scope.verKey(b)] = "changes";
scope.VTEXT["/versions/2026/HB9.0-1.json"] = [["=", "see RSA 91-A:2 here"], ["+", "new RSA 91-A:2"]];
out.runs = scope.renderVersions(b, {nver: 2, namd: 5, rsa: {}});
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("frontend", "the Bill Text tab sets each amendment's number, whether it carried and whether the committee "
                   "or the floor moved it beside it, from the docket and only where the docket says, and links "
                   "the statutes cited in a version's text and an amendment's to their law pages")
def _bill_text_amendment_facts():
    """The owner's walk of a test build, 8 November 2026: on a bill's Bill
    Text tab, "for each amendment: its number, whether it was only proposed or
    was adopted, and whether it came from the committee or from the floor",
    and the RSA links the law pages have. The tab listed "Amendment of <day>"
    and its length, and a version's text and an amendment's carried no link
    (only the bill's own record was linked, in the document drawn when a bill
    has no version history).

    Held in node on a bill of three amendments and a docket-only fourth:
      THE NUMBER: the button says "Amendment 2026-0001h" where the index
        (build_version_links.py) gives the number; where it gives none the
        button still says "Amendment of <day>", and nothing is attributed.
      THE DOCKET'S WORDS: Committee and Adopted, Floor and Rejected (the
        word renderBillText's chips use for a failed amendment), the mover,
        the day and how it was decided; a docket line that says only
        "Amendment" gets no origin chip and one with no outcome no outcome
        chip; a number the docket does not name gets no chip at all.
      THE ORDER: the docket's, with the unnamed after it.
      THE DOCKET-ONLY ONE: listed, its facts beside it, "Its text is not on
        file here", its text opened where the record has it.
      THE LINKS: a citation in the full text (blocks, added and removed
        runs, or plain), in the changes excerpt and in an amendment's text is
        a link to /laws/<chapter>#s<section>; one the index does not name
        stays words; and no definition pop-up is drawn (the text does not
        say which chapter's definitions a passage is read under)."""
    got = _node_app(_BILL_TEXT_AMD_HARNESS)
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    h = got["facts"]
    item = lambda n: re.search(r'<li id="amendment-%s">[\s\S]*?</li>' % re.escape(n), h)
    for n in ("2026-0001h", "2026-0002h", "2026-0003s", "2026-9999h", "2026-0004s"):
        assert item(n), f"amendment {n} is not listed with its number: {h[-1500:]}"
    a = item("2026-0001h").group(0)
    assert "Committee Amendment 2026-0001h</button>" in a and ">Committee</span>" not in a and ">Adopted</span>" in a \
        and "Feb 10, 2026 · Voice Vote" in a, f"the committee's adopted amendment: {a[:700]}"
    f = item("2026-0002h").group(0)
    assert "Floor Amendment 2026-0002h</button>" in f and ">Floor</span>" not in f and ">Rejected</span>" in f and "Rep. Ames · Feb 10, 2026 · Roll Call" in f \
        and ">Adopted<" not in f, f"the floor's rejected amendment: {f[:700]}"
    p = item("2026-0003s").group(0)
    assert "class=\"chip" not in p and ">Amendment 2026-0003s</button>" in p, f"a docket line that says only 'Amendment' with no outcome drew a chip: {p[:500]}"
    u = item("2026-9999h").group(0)
    assert "class=\"chip" not in u and "Mar" not in u, f"an amendment the docket does not name drew facts: {u[:500]}"
    d4 = item("2026-0004s").group(0)
    assert "Floor Amendment 2026-0004s</span>" in d4 and ">Floor</span>" not in d4 and ">Adopted</span>" in d4 and "Sen. Birdsell" in d4 \
        and "<details" in d4 and '<a href="/laws/91-a#s2" class="rsa">RSA 91-A:2</a>' in d4, \
        f"the docket-only amendment: {d4[:700]}"
    assert "Amendment of Feb 5, 2026</button>" in h, "an amendment with no number lost its day label"
    order = [m.group(1) for m in re.finditer(r'<li id="amendment-([^"]+)">', h)]
    assert order == ["2026-0001h", "2026-0002h", "2026-0003s", "2026-9999h", "2026-0004s", "2026-0005s"], (
        f"the docket's order is not kept, the unnamed after it: {order}")
    d5 = item("2026-0005s").group(0)
    assert "Committee Amendment 2026-0005s</span>" in d5 and "Adopted" not in d5 and "Rejected" not in d5 \
        and "Its text is not on file here" in d5, f"the docket-only amendment with no text: {d5[:500]}"
    # THE LINKS
    assert h.count('<a href="/laws/91-a#s2" class="rsa">RSA 91-A:2</a>') >= 6 and "/laws/999" not in h, (
        "the statutes of the full text or of the amendments are not linked, or an unknown one is")
    assert '<ins class="vins"><a href="/laws/91-a#s2" class="rsa">RSA 91-A:2</a>, II</ins>' in h, (
        "a citation in an added run is not linked in the document")
    assert "data-for=" not in h and "rs-tm" not in h, "a definition pop-up was drawn in a bill's text"
    bare = got["bare"].split("The Amendments Themselves")[-1]
    assert ">Amendment 2026-0001h</button>" in bare and 'class="chip' not in bare, (
        "with no docket row the tab attributed an origin or an outcome")
    assert 'class="rsa">RSA 91-A:2</a> here' in got["runs"] and '<ins>new <a href="/laws/91-a#s2" class="rsa">RSA 91-A:2' \
        in got["runs"], f"the changes excerpt does not link a citation: {got['runs'][600:1300]}"
    return "ok", ("an amendment is its number with the docket's committee or floor and adopted or rejected, "
                  "nothing where the docket says none; the statutes in its text and the versions' are links")


@check("frontend", "Testify takes a hearing a Senate committee's report dates apart from the docket as the "
                   "docket's one hearing, and never as one ahead")
def _testify_report_dated():
    """The review of 26 October 2026. A Senate committee's hearing report
    that gives a day the docket has no Senate hearing of the bill on stands
    on a station of its own (build_site_v2.report_station: dated_by
    "report", docket_heard the days the docket does record), shown as the
    person decided on 24 September, neither date corrected to the other.
    testifyHearings read it as a second hearing, and on 14 bills of the
    sitting term the greyed pane said "its last public hearing was" the
    report's day, where the docket records one hearing on another: SB 76's
    "Jan 30, 2025", its Hearings tab saying "The docket records no Senate
    hearing of this bill on this day; it records one on January 14, 2025".
    And with no time and no room, nothing kept such a station from being the
    live hearing ahead. Run in node:

      SB 76'S SHAPE, the docket's hearing on 14 January 2025 and the report's
        station on the 30th naming it: on 5 February, "its public hearing was
        Jan 14, 2025", no "last"; and on the 20th, between the two days, not
        live -- the hearing has passed.
      HB 183'S SHAPE, the House's hearing on 24 January 2025 and a report's
        station on 2 April where the docket has no Senate hearing: counted,
        "its last public hearing was Apr 2, 2025" once it has gone; but on 30
        March not live for it -- a report is filed after the hearing, so a
        day it gives that is still to come is not a sign-in that is open."""
    got = _app_js("""(() => {
  const moving = {rail: [{stop: "Introduced", mark: "p"}, {stop: "Senate", mark: "h"}, {stop: "House", mark: "-"},
                         {stop: "Governor", mark: "-"}, {stop: "Law", mark: "-"}]};
  const report = (when, docket) => ({when, time: null, what: "hearing", committee: "Children and Family Law",
    body: "S", venue: null, video_id: "", state: "novideo", dated_by: "report", docket_heard: docket});
  const sb76 = {term: "2025-2026", senate_committee: "Children and Family Law", journey: moving,
    stations: [{what: "hearing", when: "2025-01-14", time: "10:00", body: "S", committee: "Children and Family Law",
                venue: "SH 103"}, report("2025-01-30", ["2025-01-14"]),
               {what: "floor debate", when: "2025-02-13", time: null, body: null, committee: "Senate"}]};
  const hb183 = {term: "2025-2026", house_committee: "Executive Departments and Administration",
    senate_committee: "Executive and Administration",
    journey: {rail: [{stop: "Introduced", mark: "p"}, {stop: "House", mark: "p"}, {stop: "Senate", mark: "h"},
                     {stop: "Governor", mark: "-"}, {stop: "Law", mark: "-"}]},
    stations: [{what: "public hearing", when: "2025-01-24", time: "10:00", body: "H",
                committee: "Executive Departments and Administration", venue: "LOB 306-308"},
               Object.assign(report("2025-04-02", []), {committee: "Executive and Administration"})]};
  const sb = {id: "SB76", n: "SB 76", kind: "active"}, hb = {id: "HB183", n: "HB 183", kind: "active"};
  return {
    sb76: scope.testifyButton(sb76, sb, new Date("2025-02-05T17:00:00Z")),
    sb76Between: scope.testifyButton(sb76, sb, new Date("2025-01-20T17:00:00Z")),
    hb183: scope.testifyButton(hb183, hb, new Date("2025-04-10T16:00:00Z")),
    hb183Ahead: scope.testifyButton(hb183, hb, new Date("2025-03-30T16:00:00Z")),
  };
})()""", names=("testifyButton",))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    flat = lambda h: " ".join(re.sub(r"<[^>]+>", " ", h).replace("&rsquo;", "’").split())
    pane = lambda h: flat((re.search(r'<div class="testifypane">(.*?)</div></details>', h, re.S) or [None, ""])[1])
    for name, said in (
            ("sb76", "Online testimony submissions for this bill have closed as of January 14, 2025."),
            ("sb76Between", "Online testimony submissions for this bill have closed as of January 14, 2025."),
            ("hb183", "Online testimony submissions for this bill have closed as of April 2, 2025."),
            ("hb183Ahead", "Online testimony submissions for this bill have closed as of January 24, 2025.")):
        h = got[name]
        assert h.startswith('<details class="testify toff">'), (
            f"{name}: a day a committee's report gives is taken as a hearing ahead: {pane(h)[:200]!r}")
        assert pane(h).startswith(said), f"{name}'s pane says {pane(h)!r}, not {said!r}"
    return "ok", ("SB 76's report-dated sitting the docket's one hearing, Jan 14, 2025, no \"last\"; HB 183's, "
                  "where the docket has no Senate hearing, counted once it has gone and never live ahead")


@check("frontend", "a testimony deadline is Concord's and a day's name the reader's, and each place that "
                   "reads the reader's clock points to where nhDay says why")
def _testify_two_clocks():
    """The review of 25 October 2026: the site has two "todays". Testify asks
    New Hampshire's (nhDay), since the online sign-in closes at midnight in
    Concord wherever the reader is; a committee's Upcoming (app.js
    calendarBlock), the home page's Coming up and Latest Activity
    (build_pages HOME_JS), the Calendar (build_calendar WEEK_JS) and what
    retires on a day (components.js, data-until) ask the reader's, since
    "today", "tomorrow" and "this week" are words about the reader's own
    calendar -- and their comments stated that rule, the opposite one, with
    nothing to say the difference was meant. A later "unify the clocks" would
    break one or the other. nhDay's comment says why there are two, naming
    each of the five, and each of the five points back to it.

    BUT data-until NAMES NO DAY (the review of 26 October 2026). It hides a
    member-elect from the day they take office, an event in Concord of the
    same kind as a testimony deadline, and it reads the reader's clock by the
    choice of 16 October 2026 (the members-elect), not because a day's name is
    the reader's. nhDay's comment filed it under that rule and then forbade
    making the clocks one, which would forbid a change that may be right
    there. So the rule names the four places that say a day's name, and
    data-until is named apart, as the reader's clock by that choice, which
    nothing forbids revisiting; components.js says the same."""
    js = _source("src/pages/app.js")
    head = js[js.index("// NEW HAMPSHIRE'S DAY, NOT THE READER'S"):js.index("function nhDay(")]
    flat = " ".join(c.strip("/ ").strip() for c in head.splitlines())
    assert "TWO CLOCKS, ON PURPOSE" in flat, "nhDay's comment no longer says there are two clocks on purpose"
    for named in ("A DEADLINE IS CONCORD'S", "A DAY'S NAME IS THE READER'S", "calendarBlock", "HOME_JS",
                  "build_calendar", "data-until", "not to be made one"):
        assert named in flat, f"nhDay's comment no longer says {named!r}"
    rule = flat[flat.index("A DAY'S NAME IS THE READER'S"):flat.index("not to be made one")]
    assert "data-until" not in rule and "components.js" not in rule, (
        "nhDay's comment files data-until, which names no day, under \"a day's name is the reader's\" and "
        "forbids making its clock Concord's")
    at = flat.index("data-until")
    apart = flat[max(0, at - 300):at + 500]
    assert "16 October 2026" in apart and "names no day" in apart, (
        "nhDay's comment does not name data-until apart, as the reader's clock by the choice of 16 October "
        "2026 and not a day's name")
    cj = _source("src/pages/components.js")
    cnote = " ".join(cj[cj.index("// WHAT RETIRES ON A DAY"):cj.index("function day(){")].replace("//", " ").split())
    assert "not because a day's name is the reader's" in cnote, (
        "components.js's data-until says it reads the reader's clock as a day's name does")
    pointer = "TWO CLOCKS, ON PURPOSE"
    places = (("src/pages/app.js", "const today=new Date(); today.setHours(0,0,0,0);\n  const when=d=>{"),
              ("src/pages/inline/build_pages.home.js", "const latRel=(d,now)=>{"),
              ("src/pages/inline/build_pages.home.js",
               "const now=new Date(); now.setHours(0,0,0,0);\n    const dow=now.getDay()"),
              ("src/pages/inline/build_calendar.js", "var now=new Date(), TODAY=iso("),
              ("src/pages/components.js", "function day(){\n    var d=new Date();"))
    for f, anchor in places:
        text = Path(f).read_text(encoding="utf-8")
        assert text.count(anchor) == 1, f"{f} no longer reads the reader's clock at {anchor[:40]!r}"
        before = " ".join(text[max(0, text.index(anchor) - 400):text.index(anchor)].replace("//", " ").split())
        assert pointer in before and "nhDay" in before, (
            f"{f} reads the reader's clock at {anchor[:40]!r} with no pointer to nhDay's TWO CLOCKS")
    return "ok", ("nhDay says why the two clocks differ, and the five places on the reader's clock point to it; "
                  "data-until named apart, the reader's clock by the choice of 16 October 2026")


@check("frontend", "on /bills, the term picker changed while a bill is open keeps that bill, its record and "
                   "its row until it is closed, offers filters in the term chosen meanwhile, and closing the "
                   "bill takes that term once")
def _picker_keeps_the_open_bill():
    """The review of 25 October 2026, a fault older than Testify: on /bills,
    2023-2024's HB 104 open, the term picker turned to 2025-2026 and a tab
    pressed redrew the card as 2025-2026's HB 104 under the old bill's row --
    Cite still /bill/2023/hb104 -- and a live Testify for HB 104-FN in it. The
    picker's change handler took the term at once and drew nothing, which its
    comment says is so that the record is not swapped; the next redraw found
    the bill by its number in the new term, and dkey looked its record up
    there.

    The handler holds the choice while a bill is open (heldTerm) and fetches
    that term's bills; unfocus takes it when the bill is closed, which a
    search or an offer taken from the open bill does first, lets it go, and
    forgets the open bill's cards and tabs. A bill's own page has no picker
    (staticChromeDown hides it), so nothing there reads the held term.

    The review of 26 October 2026 found three parts of that could each be
    taken out with this check passing, and one regression: the offers under
    the box (billOffers) were counted and chosen in the open bill's term and
    landed in the held one -- "Topic Housing 62" listing 117 bills, "House
    Special Committee on Housing" none. So, run here in node with the
    handler's own text out of app.js, an index holding HB 104 and housing
    bills in both terms, and a fetch that records what it is asked for:

      the picker turned with 2023-2024's HB 104 open: the bill, its record and
        the redraw stay 2023-2024's, and 2025-2026's bills are asked for;
      the offers for "housing" meanwhile: 2025-2026's topic and committee,
        with 2025-2026's counts, and the open bill still looked up in its own;
      the bill closed: the list is 2025-2026's, nothing is held any more, and
        the old bill's open card and tab are forgotten;
      then the picker turned back to 2023-2024 with no bill open, and a bill
        opened and closed: the list stays 2023-2024's."""
    js = _source("src/pages/app.js")
    start = js.index('ys.addEventListener("change",e=>{')
    end = js.index("Promise.all(want.map(ensureTerm)).then(render);});", start) + len(
        "Promise.all(want.map(ensureTerm)).then(render);}")
    handler = js[start + len('ys.addEventListener("change",'):end]
    # The handler is a closure over the index's load, which names the terms;
    # it is evaluated where app.js's own bindings are (a direct eval in the
    # scope _app_js builds), with the two terms this index holds. Escaped
    # twice: once as the eval's string, once inside _app_js's own literal.
    change = "change:eval(" + json.dumps(
        '(()=>{const terms=["2025-2026","2023-2024"];return ' + handler + ";})()") + ")"
    got = _app_js("""(() => {
  const row = (id, n, term, title, kind, topic, committee) => ({id, n, term, year: +term.slice(5), title, kind,
    topic, committee, committees: [committee]});
  const older = row("HB104", "HB 104", "2023-2024", "the earlier one", "done", "Housing",
                    "House Special Committee on Housing");
  const newer = row("HB104", "HB 104-FN", "2025-2026", "the newer one", "active", "Housing", "House Housing");
  scope.IDX.length = 0;
  scope.IDX.push(older, newer,
    row("HB5", "HB 5", "2023-2024", "a", "done", "Housing", "House Special Committee on Housing"),
    row("HB7", "HB 7", "2025-2026", "b", "active", "Housing", "House Housing"),
    row("HB9", "HB 9", "2025-2026", "c", "active", "Housing", "House Commerce"),
    row("HB11", "HB 11", "2025-2026", "d", "active", "Taxation", "House Ways and Means"));
  // The terms' bills, asked for and never answered: what was asked is the
  // point, and render is not run again behind this.
  const asked = [];
  scope.setEnsure(t => { asked.push(t); return new Promise(() => {}); });
  scope.setTerm("2023-2024");
  scope.setFocused("HB104");
  scope.openCards.add("HB104");
  scope.openTab.HB104 = "votes";
  scope.detail["2024/HB104"] = {term: "2023-2024", stations: [], journey: {}};
  scope.detail["2026/HB104"] = {term: "2025-2026", stations: [], journey: {}};
  scope.change({target: {value: "2025-2026"}});
  const fetched = asked.slice();
  const held = {term: scope.getTerm(), key: scope.dkey("HB104"), focused: scope.getFocused(),
                held: scope.getHeld()};
  const offers = scope.billOffers("housing").map(o => [o.key, o.v, o.n]);
  const keptOwn = {term: scope.getTerm(), key: scope.dkey("HB104")};
  let drew = "";
  try { scope.render(); drew = document.querySelector("#results").innerHTML; } catch (e) { drew = "RENDER " + e.message; }
  scope.unfocus(0);
  const after = {term: scope.getTerm(), focused: scope.getFocused(), key: scope.dkey("HB104"),
                 held: scope.getHeld(), open: scope.openCards.has("HB104"), tab: scope.openTab.HB104 || null};
  // Again: the picker turned back with no bill open, then a bill opened and
  // closed. Nothing is held from before to be taken again.
  scope.change({target: {value: "2023-2024"}});
  scope.setFocused("HB104");
  scope.unfocus(0);
  return {fetched, held, offers, keptOwn, drew: drew.includes("the earlier one") && !drew.includes("the newer one"),
          after, again: {term: scope.getTerm(), held: scope.getHeld()}};
})()""", names=("render", "unfocus", "billOffers", "IDX", "detail", "dkey", "openCards", "openTab",
                "setTerm:(t)=>{term=t;}", "getTerm:()=>term", "setFocused:(x)=>{focused=x;}",
                "getFocused:()=>focused", "getHeld:()=>heldTerm", "setEnsure:(f)=>{ensureTerm=f;}",
                json.dumps(change)[1:-1]))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    assert got["held"] == {"term": "2023-2024", "key": "2024/HB104", "focused": "HB104", "held": "2025-2026"}, (
        f"the picker turned while 2023-2024's HB 104 was open swaps the bill under the reader: {got['held']}")
    assert got["fetched"] == ["2025-2026"], (
        f"the picker turned while a bill is open does not fetch the chosen term's bills: {got['fetched']}")
    assert got["drew"], "a redraw after the picker turned drew another term's HB 104 in the open bill's place"
    assert sorted(got["offers"]) == [["committee", "House Housing", 2], ["topic", "Housing", 3]], (
        "with 2023-2024's HB 104 open and the picker on 2025-2026, the offers for \"housing\" are not "
        f"2025-2026's, where taking one lands: {got['offers']}")
    assert got["keptOwn"] == {"term": "2023-2024", "key": "2024/HB104"}, (
        f"working out the offers left the open bill looked up in the held term: {got['keptOwn']}")
    assert got["after"] == {"term": "2025-2026", "focused": None, "key": "2026/HB104", "held": None,
                            "open": False, "tab": None}, (
        f"closing the bill did not take the term the picker chose, once, and forget the old bill's cards: "
        f"{got['after']}")
    assert got["again"] == {"term": "2023-2024", "held": None}, (
        f"a term the picker chose earlier was taken again when a later bill was closed: {got['again']}")
    # No other place reads the held term: the picker is not on a bill's own
    # page, the only place takeOffer and submitSearch leave for /bills.
    for fn in ("function submitSearch(", "function takeOffer("):
        body = js[js.index(fn):js.index("\n}\n", js.index(fn))]
        assert "heldTerm" not in body, (
            f"{fn[9:-1]} reads the held term where no picker can have chosen one; unfocus takes it")
    return "ok", ("2023-2024's HB 104 stays open, its record 2024/HB104, with the picker on 2025-2026 and its "
                  "bills asked for; the offers 2025-2026's; closed, the list is 2025-2026's, nothing held, the "
                  "old cards forgotten; turned back with no bill open, a later close keeps 2023-2024")


@check("frontend", "Follow's, Cite's and Testify's panes, opened below the fold, are brought into view")
def _panes_into_view():
    """The webinar's phone check (16 October 2026): on a phone with the action
    row near the foot of the screen, Follow's pane opened at y=842 of 812 and
    the press seemed to do nothing. app.js's toggle listener now hands the
    record panes to paneInView, which moves the window only when some of the
    pane is out of sight, and again when the email box lengthens Follow's.
    Testify's pane joined them when it came into the row (the person, 25
    October 2026): live, it is the tallest of the three on a phone, 380px
    at 390px wide."""
    js = _source("src/pages/app.js").replace("\r\n", "\n")
    assert "function paneInView(p){" in js and "if(h&&(r.bottom>h||r.top<0))" in js, (
        "app.js has no paneInView, or it moves the window when the pane is already in sight")
    flat = re.sub(r"\s+", "", js)
    assert 'd.classList.contains("follow")||d.classList.contains("pcite")||d.classList.contains("testify")' in flat \
        and 'paneInView(d.querySelector(".followpane,.citebody,.testifypane"));' in flat, (
            "opening Follow, Cite or Testify no longer brings its pane into view")
    assert 'paneInView(box.querySelector(".followpane"));' in js, (
        "the email box lengthens Follow's pane past the fold and nothing brings it back")
    return "ok", "the three panes, on opening, and Follow's again when its email box arrives"


@check("frontend", "no page the build writes asks YouTube for anything before a person presses Play: "
                   "no frame, image, script or style of YouTube's, and every recording a still on a "
                   "button")
def _nothing_from_youtube():
    """The privacy page's promise ("a player only loads if you press play"),
    held over every page of the fixture's build since the Videos views (26
    October 2026) put a still at the top of a committee's, a chamber's and a
    study committee's pages: no <iframe> at all, no tag of any kind whose
    address is YouTube's, its images' (ytimg) or its video servers', and every
    data-embed -- the still app.js turns into the player when pressed -- on a
    <button>. A script's text is left out: app.js and a page's inline script
    write the player when asked, and the checks of the players hold them."""
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    shared, _base, _ran, _days = _fixture_site_shared()
    bad, stills, pages = [], 0, 0
    for f in sorted((shared / "site").rglob("*.html")):
        text = re.sub(r"(<script\b[^>]*>).*?</script>", r"\1</script>",
                      f.read_text(encoding="utf-8", errors="replace"), flags=re.S | re.I)
        pages += 1
        rel = f.relative_to(shared / "site").as_posix()
        if re.search(r"<iframe\b", text, re.I):
            bad.append(f"{rel} carries a frame")
        for tag in re.findall(r"<(?:img|script|link|source|video|audio|embed|object)\b[^>]*>", text, re.I):
            if re.search(r"youtube|ytimg|googlevideo", tag, re.I):
                bad.append(f"{rel}: {tag[:80]}")
        for name in re.findall(r"<(\w+)\b[^>]*\sdata-embed=", text):
            stills += 1
            if name.lower() != "button":
                bad.append(f"{rel}: a still on a <{name}>")
    assert pages, "the fixture's build wrote no page, so this read nothing"
    assert not bad, "a page asks YouTube for something before Play: " + "; ".join(bad[:6])
    return "ok", f"{pages} pages; {stills} stills, each a button; nothing of YouTube's before Play"


@check("frontend", "a committee's Videos tab behaves as a reader uses it: a recording that plays is "
                   "kept through a redraw, an address naming a recording or a meeting of another term "
                   "turns to it, Back and Forward bring the tab back, and a row, Show all, the skip link "
                   "and Share do what they say")
def _committee_videos_behaviour():
    """The second review of the Videos tab (29 October 2026) reverted each
    piece of the tab's behaviour in turn and found preflight passed without
    it: renderPage's kept pane, the landing on #v-<id>, a row's click, the
    keyboard sent to Play, Show all, the skip link, the meeting's link, Share
    keeping #v-, tabAddress keeping the fragment, showDay naming its tab,
    recordTerms taking the recordings' terms, the list's place through a
    redraw. Each is driven here as the page drives it, in node over app.js
    with the page's own listeners, and so are the fixes that review asked
    for: a meeting of another term reached by its address (showDay turns to
    its term), Back and Forward reading the tab from the path again
    (popstate), the Videos tab turned to again naming what it shows
    (vwBackTo), and a term holding only recordings opening on them
    (landingTab)."""
    items = lambda vid, kind, start, state, bill="HB1442", term="2025-2026": [{
        "bill": bill, "n": bill[:2] + " " + bill[2:], "title": "a title", "year": int(term[5:]),
        "term": term, "kind": kind, "video_id": vid, "start": start, "state": state, "time": "10:00",
        "venue": "LOB 302"}]
    sess = lambda date, its, term="2025-2026": {"date": date, "term": term, "video_id": its[0]["video_id"],
                                                "items": its}
    rec = lambda i, d, term="2025-2026": {"id": i, "date": d, "term": term}
    cmte = {"code": "H43", "name": "Commerce", "chamber": "H", "bills": {"2025-2026": []},
            "sessions": [sess("2026-02-10", items("VID4", "executive session", 300, "stated")),
                         sess("2026-02-03", items("VID1", "public hearing", 150.0, "stated"))],
            "recordings": [rec("NEW1", "2026-02-24"), rec("VID4", "2026-02-10"), rec("VID1", "2026-02-03")]}
    # And a term before: House Public Works and Highways' 5 May 2021.
    two = dict(cmte, bills={"2025-2026": [], "2021-2022": []},
               sessions=cmte["sessions"] + [sess("2021-05-05", items("OLD21", "public hearing", 60, "stated",
                                                                       "HB100", "2021-2022"), "2021-2022")],
               recordings=cmte["recordings"] + [rec("OLD21", "2021-05-05", "2021-2022")])
    # House Rules: one bill of 1997-1998, and recordings of 2025-2026 alone.
    rules = {"code": "H23", "name": "Rules", "chamber": "H", "sessions": [],
             "bills": {"1997-1998": [{"id": "HR1", "n": "HR 1", "title": "rules", "year": 1997}]},
             "recordings": [rec("RUL1", "2026-03-01")]}
    harness = _HEARD_PRELUDE + r"""
load("renderPage, recordTerms, tabAddress, openPage, addressed, getFocused: () => null,"
  + " setPage: (p) => { PAGE = p; }, getPage: () => PAGE, setTab: (t) => { PAGE_TAB = t; },"
  + " getTab: () => PAGE_TAB, setUp: (u) => { UPCOMING = u; }, getView: () => VVIEW");
const fx = JSON.parse(fs.readFileSync("./fx.json", "utf8"));
const results = document.querySelector("#results");
const stubQuery = results.querySelector;
// THE PAGE'S ELEMENTS BY ID, as a browser finds them in what was drawn: a
// day's fold where the drawing carries its id, or one a test stands up.
const byId = {};
document.getElementById = (id) => byId[id] || (results.innerHTML.includes(`id="${id}"`)
  ? {id, tagName: "DETAILS", open: false, classList: {contains: () => false, add() {}, remove() {}},
     scrollIntoView() {}} : null);
const tick = async () => { for (let i = 0; i < 8; i++) await new Promise((r) => setImmediate(r)); };
const record = (c) => JSON.parse(JSON.stringify(c));
globalThis.fetch = async (u) => { const f = String(u).match(/committee\/(\w+)\.json$/);
  const body = f ? record(fx[f[1]]) : /home\.json$/.test(String(u)) ? {upcoming: []} : [];
  return {ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body)}; };
const page = (c, extra) => { const terms = s.recordTerms("committee", c);
  return Object.assign({kind: "committee", data: record(c), terms, term: terms[0], status: "", vfilter: "",
    vside: "", vq: "", vopen: {}, vshow: 0, bshow: 0, mshow: 0, vid: ""}, extra || {}); };
const show = (path, c, tab, extra) => { go(path); s.setPage(page(c, extra)); s.setTab(tab); s.renderPage(); };
const chosen = () => (s.getView() || {}).chosen;
const marked = (id) => results.innerHTML.includes(`data-vwpick="${id}" aria-current="true"`);
const at = () => location.pathname + location.search + location.hash;
const fire = (t, ev) => (heard.window[t] || []).forEach((f) => f(ev || {state: null}));
const out = {};
(async () => {
  try {
    s.setUp([]);
    // (a) A RECORDING THAT PLAYS IS KEPT: renderPage draws what is above the
    // pane and leaves the pane, its frame in it, where it is.
    show("/committee/H43/videos", fx.H43, 2);
    const box = {dataset: {vwkey: "H43|2025-2026"}, querySelector: (q) => q === "iframe" ? {} : null};
    const pane = {parentNode: results, before: "", insertAdjacentHTML(w, h) { this.before = w + " " + h; },
      querySelector: (q) => q === ".vw" ? box : null};
    results.querySelector = (q) => q === "#ppane" ? pane : null;
    results.firstChild = pane;
    results.innerHTML = "THE PANE, PLAYING";
    s.renderPage();
    out.kept = {html: results.innerHTML, before: pane.before.startsWith("beforebegin "),
                tabs: /role="tab"[^>]*>Videos/.test(pane.before)};
    results.querySelector = stubQuery; delete results.firstChild;
    // (l) THE LIST KEEPS ITS PLACE through a drawing of the same list.
    const oldList = {scrollTop: 300, closest: (q) => q === ".vw" ? {dataset: {vwkey: "H43|2025-2026"}} : null};
    const newList = {scrollTop: 0};
    results.innerHTML = "OLD";
    results.querySelector = (q) => results.innerHTML === "OLD" ? (q === ".vwlist" ? oldList : null)
      : q === ".vw" ? {dataset: {vwkey: "H43|2025-2026"}, querySelector: () => newList} : null;
    s.renderPage();
    out.scroll = newList.scrollTop;
    results.querySelector = stubQuery;
    // (b) AN ADDRESS NAMING ANOTHER TERM'S RECORDING, the page loaded at it:
    // that term, the Videos tab, the row chosen; and then this term's, named
    // by the address changing (hashchange).
    go("/committee/two/videos#v-OLD21");
    s.openPage("committee", "two"); await tick();
    out.deep = {term: s.getPage().term, tab: s.getTab(), chosen: chosen(), marked: marked("OLD21")};
    go("/committee/two/videos#v-VID4"); fire("hashchange"); await tick();
    out.hash = {term: s.getPage().term, tab: s.getTab(), chosen: chosen(), marked: marked("VID4")};
    // (#4) A MEETING OF ANOTHER TERM, its address opened afresh: its term.
    go("/committee/two/sessions#day-2021-05-05");
    s.openPage("committee", "two"); await tick();
    out.day = {term: s.getPage().term, tab: s.getTab(), drawn: results.innerHTML.includes('id="day-2021-05-05"')};
    // (j) A DAY ASKED FOR ON ANOTHER TAB: the Meetings tab, and the address names it.
    show("/committee/H43#day-2026-02-03", fx.H43, 0);
    out.dayTab = {tab: s.getTab(), at: at()};
    // (c, d) A ROW: a click with a key held is the link's; a plain one chooses
    // in place, the row marked, the detail its own, the address its, and the
    // keyboard on Play, where nothing has played.
    show("/committee/H43/videos", fx.H43, 2);
    const n = {focus: 0, made: 0, removed: 0, set: []};
    const stub = {focus() { n.focus += 1; }, click() { n.played = 1; }};
    const player = {insertAdjacentHTML() { n.made += 1; }, remove() {}, scrollIntoView() {},
      querySelector: (q) => q === ".pstub" ? stub : null};
    const det = {innerHTML: ""};
    const view = {querySelector: (q) => q === ".vwplay iframe" ? null : q === ".vwplay" ? player
      : q === ".vwdetin" ? det : q === ".vwsay" ? {textContent: ""} : null,
      querySelectorAll: (q) => q === ".vwlist a[aria-current]" ? [{removeAttribute() { n.removed += 1; }}] : []};
    const row = {dataset: {vwpick: "VID4"}, closest: (q) => q === ".vw" ? view : null,
      setAttribute(k, v) { n.set.push(k + "=" + v); }};
    const pick = (q) => q === "a[data-vwpick]" ? row : null;
    const held = click(pick, {ctrlKey: true});
    out.held = {prevented: held.prevented, made: n.made, set: n.set.length};
    const plain = click(pick);
    out.row = {prevented: plain.prevented, made: n.made, removed: n.removed, set: n.set, focus: n.focus,
               vid: s.getPage().vid, detail: det.innerHTML.includes("HB 1442"), at: at()};
    // (e) SHOW ALL, a phone's rest of a recording's bills: shown, the keyboard on the first it brought.
    const list = {cls: [], classList: {add(c) { list.cls.push(c); }},
      querySelector: (q) => q === ".vwrest a" ? {focus() { list.focused = 1; }} : null};
    byId.vwbills = list;
    click((q) => q === "[data-vwall]" ? {getAttribute: (k) => k === "aria-controls" ? "vwbills" : null,
      dataset: {vwall: "bills"}, remove() { list.gone = 1; }} : null);
    out.all = {cls: list.cls, focused: !!list.focused, gone: !!list.gone};
    delete byId.vwbills;
    // (f) THE SKIP LINK: the keyboard to the chosen row.
    const cur = document.querySelector('.vwlist a[aria-current="true"]');
    cur.focus = () => { out.skipped = 1; }; cur.closest = () => null;
    out.skip = click((q) => q === "a[data-vwskip]" ? {} : null).prevented;
    // (h) SHARE keeps #v-, and drops a fragment that only scrolls.
    const st = {textContent: ""};
    navigator.share = undefined; navigator.clipboard = undefined;
    const share = (href) => { location.href = href; location.hash = href.slice(href.indexOf("#"));
      click((q) => q === "[data-share]" ? {parentNode: {querySelector: () => st}} : null); return st.textContent; };
    out.share = [share("https://x/committee/H43/videos#v-VID4"), share("https://x/committee/H43/sessions#day-2026-02-03")];
    // (i) tabAddress keeps the fragment where asked, and only there.
    go("/committee/H43/sessions#v-abc"); wrote.length = 0;
    s.tabAddress("videos", true); s.tabAddress("videos");
    out.tabAddress = wrote.splice(0);
    // (g) THE MEETING'S LINK under the player: the Meetings tab at that day.
    show("/committee/H43/videos#v-VID1", fx.H43, 2);
    const meet = click((q) => q === "a[data-vwday],a[data-vwgo]" ? {dataset: {vwday: "2026-02-03"},
      getAttribute: (k) => k === "href" ? "/committee/H43/sessions#day-2026-02-03" : null} : null);
    out.meet = {prevented: meet.prevented, tab: s.getTab(), at: at(),
                open: results.innerHTML.includes('id="day-2026-02-03" open')};
    // (#5) BACK, to the Videos tab's address the Meetings tab had replaced: the tab
    // and its recording; and Forward again.
    go("/committee/H43/videos#v-VID4"); fire("popstate");
    out.back = {tab: s.getTab(), chosen: chosen(), marked: marked("VID4")};
    go("/committee/H43/sessions#day-2026-02-03"); fire("popstate");
    out.forward = s.getTab();
    // (#6) THE VIDEOS TAB TURNED TO AGAIN names what it shows; the newest it
    // shows when nothing was chosen is left unnamed.
    show("/committee/H43/videos#v-VID4", fx.H43, 2);
    const tab = (i) => click((q) => q === "[data-pt]" ? {dataset: {pt: String(i)}} : null);
    tab(0); tab(2);
    out.again = {at: at(), chosen: chosen()};
    show("/committee/H43/videos", fx.H43, 2); tab(0); tab(2);
    out.newest = at();
    // (#10) A TERM HOLDING ONLY RECORDINGS opens on them; one with bills or
    // meetings on Bills.
    go("/committee/rules"); s.openPage("committee", "rules"); await tick();
    out.rules = {tab: s.getTab(), term: s.getPage().term, at: at()};
    go("/committee/H43"); s.openPage("committee", "H43"); await tick();
    out.commerce = {tab: s.getTab(), at: at()};
    // (k) The recordings' terms are the page's.
    out.terms = s.recordTerms("committee", fx.rules);
  } catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + (e.stack || "").slice(0, 400); }
  process.stdout.write("\n@@" + JSON.stringify(out));
})();
"""
    got = _node_app(harness, {"fx.json": json.dumps({"H43": cmte, "two": two, "rules": rules})})
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    assert "threw" not in got, "the Videos tab's behaviour could not be driven: " + got["threw"]
    assert got["kept"] == {"html": "THE PANE, PLAYING", "before": True, "tabs": True}, (
        f"renderPage draws the pane again while a recording plays in it, or not what is above it: {got['kept']}")
    assert got["scroll"] == 300, f"the list's place is lost when the page is drawn again: {got['scroll']}"
    assert got["deep"] == {"term": "2021-2022", "tab": 2, "chosen": "OLD21", "marked": True}, (
        f"an address naming another term's recording does not open on it: {got['deep']}")
    assert got["hash"] == {"term": "2025-2026", "tab": 2, "chosen": "VID4", "marked": True}, (
        f"the address changed to a recording of another term does not turn to it: {got['hash']}")
    assert got["day"] == {"term": "2021-2022", "tab": 1, "drawn": True}, (
        f"a meeting of another term, its address opened afresh, is not found: {got['day']}")
    assert got["dayTab"] == {"tab": 1, "at": "/committee/H43/sessions#day-2026-02-03"}, (
        f"a day asked for on the Bills tab does not open the Meetings tab, named in the address: {got['dayTab']}")
    assert got["held"] == {"prevented": 0, "made": 0, "set": 0}, (
        f"a row clicked with a key held is not left to open its own address: {got['held']}")
    assert got["row"] == {"prevented": 1, "made": 1, "removed": 1, "set": ["aria-current=true"], "focus": 1,
                          "vid": "VID4", "detail": True, "at": "/committee/H43/videos#v-VID4"}, (
        f"a row clicked is not chosen in place, the keyboard on Play: {got['row']}")
    assert got["all"] == {"cls": ["vwopen"], "focused": True, "gone": True}, (
        f"Show all does not show the rest of the bills and take the keyboard to it: {got['all']}")
    assert got["skip"] == 1 and got.get("skipped") == 1, "the skip link does not take the keyboard to the chosen row"
    assert got["share"] == ["Copy this address: https://x/committee/H43/videos#v-VID4",
                            "Copy this address: https://x/committee/H43/sessions"], (
        f"Share does not keep the recording, or keeps a fragment that only scrolls: {got['share']}")
    assert got["tabAddress"] == ["replace /committee/H43/videos#v-abc", "replace /committee/H43/videos"], (
        f"tabAddress does not keep the fragment where asked, and only there: {got['tabAddress']}")
    assert got["meet"] == {"prevented": 1, "tab": 1, "at": "/committee/H43/sessions#day-2026-02-03",
                           "open": True}, f"the meeting's link under the player does not open it: {got['meet']}"
    assert got["back"] == {"tab": 2, "chosen": "VID4", "marked": True} and got["forward"] == 1, (
        f"Back and Forward do not bring back the tab the address names: {got['back']}, then {got['forward']}")
    assert got["again"] == {"at": "/committee/H43/videos#v-VID4", "chosen": "VID4"} and \
        got["newest"] == "/committee/H43/videos", (
            f"the Videos tab turned to again does not name what it shows: {got['again']}, {got['newest']}")
    assert got["rules"] == {"tab": 2, "term": "2025-2026", "at": "/committee/rules/videos"} and \
        got["commerce"] == {"tab": 0, "at": "/committee/H43"}, (
            f"a term holding only recordings does not open on them, or one with bills does: "
            f"{got['rules']}, {got['commerce']}")
    assert got["terms"] == ["2025-2026", "1997-1998"], f"the recordings' terms are not the page's: {got['terms']}"
    return "ok", ("a playing recording kept through a redraw, the list in its place; #v- and #day- of "
                  "another term turn to it; Back and Forward bring the tab back; a row chosen in place, "
                  "the keyboard on Play, a held key left to the link; Show all, the skip link, Share, "
                  "tabAddress and the meeting's link as they say; the tab turned to again names its "
                  "recording; a term of recordings alone opens on them")


@check("frontend", "the bill search can be filtered by the prime sponsor's party, as recorded for the bill's "
                   "term, and the options add up to the list")
def _search_party_filter():
    """The owner, 8 November 2026: a Sponsor filter by party (Republican,
    Democrat, other as the record has them). The index row's `sponsor_party`
    is the party the roster gives the sponsor for the bill's own term
    (build_site_v2); app.js's `party` facet (partyOfSponsor) puts every bill
    under exactly one name -- "Party not on file" for a bill naming no
    sponsor -- so the counts add up, and a ticked party keeps only its
    bills."""
    rows = [{"id": f"HB{i}", "term": "2025-2026", "sponsor": f"P{i}", "sponsor_party": p}
            for i, p in enumerate("RRRDDI", 1)] + [{"id": "HB9", "term": "2025-2026", "sponsor": ""},
                                                    {"id": "HB10", "term": "2025-2026", "sponsor": "Q",
                                                     "sponsor_party": "L"}]
    harness = _HEARD_PRELUDE + r"""
load("setIdx: (r) => { IDX = r; }, matches, sel, facetVals, partyOfSponsor");
const rows = JSON.parse(fs.readFileSync("./rows.json", "utf8"));
const out = {};
try {
  s.setIdx(rows);
  out.of = rows.map(b => s.partyOfSponsor(b));
  const n = () => rows.filter(b => s.matches(b)).map(b => b.id);
  out.all = n().length;
  s.sel.party.add("Democrat"); out.dem = n();
  s.sel.party.add("Republican"); out.demrep = n().length;
  s.sel.party.clear(); s.sel.party.add("Party not on file"); out.none = n();
} catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + (e.stack || "").slice(0, 300); }
process.stdout.write("\n@@" + JSON.stringify(out));
"""
    got = _node_app(harness, {"rows.json": json.dumps(rows)})
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    assert "threw" not in got, "the party filter would not run: " + got["threw"]
    assert got["of"] == ["Republican"] * 3 + ["Democrat"] * 2 + ["Independent", "Party not on file", "Libertarian"], (
        f"a bill is not under its sponsor's party as recorded: {got['of']}")
    assert got["all"] == 8 and got["dem"] == ["HB4", "HB5"] and got["demrep"] == 5 and got["none"] == ["HB9"], (
        f"a ticked party does not keep exactly its bills: {got}")
    src = _source("src/pages/app.js")
    assert 'fgroup("party",' not in src and 'data-f="party"' in src and '"party"]' in src, (
        "the party is not a choice inside the Sponsor group, or not kept in the address")
    # The Sponsor group draws the party choice inside itself, after its
    # co-sponsorship box, and its badge counts a party ticked.
    h2 = _HEARD_PRELUDE + r"""
load("fgroup, sel, openGroups");
const out = {};
try {
  s.sel.party.add("Democrat");
  const extra = '<div class="fsub" id="x">PARTYBOX</div>';
  out.html = s.fgroup("sponsor", "Sponsor", ["Ann"], {Ann: 1}, true, null, null, extra, s.sel.party.size);
} catch (e) { out.threw = e.constructor.name + ": " + e.message; }
process.stdout.write("\n@@" + JSON.stringify(out));
"""
    g2 = _node_app(h2, {})
    assert g2 is not None and "threw" not in g2, f"the Sponsor group would not draw: {g2}"
    html = g2["html"]
    assert html.index('id="cosp"') < html.index("PARTYBOX") < html.index("</div></div>"), (
        "the party choice is not inside the Sponsor group after its co-sponsorship box")
    assert '<span class="badge">1</span>' in html, "the Sponsor badge does not count a ticked party"
    return "ok", "bills fall under their sponsor's party as recorded, and a ticked party keeps exactly its bills"


@check("frontend", "the Sponsor filter matches only the bills a person PRIME sponsored unless the reader "
                   "ticks \"Include co-sponsored bills\", which is off by default")
def _sponsor_filter_prime_only():
    """Alice, 8 November 2026: "Sorting by sponsor in the filter should allow
    you to check off whether to include co-sponsorships, by default it should
    only be prime sponsored bills." It had matched the prime sponsor or any
    co-sponsor, always (facetVals: [b.sponsor, ...b.cosp])."""
    rows = [{"id": "HB1", "term": "2025-2026", "sponsor": "Ann Lee", "cosp": ["Bo Ray"]},
            {"id": "HB2", "term": "2025-2026", "sponsor": "Bo Ray", "cosp": ["Ann Lee"]},
            {"id": "HB3", "term": "2025-2026", "sponsor": "Cy Fox"}]
    harness = _HEARD_PRELUDE + r"""
load("setIdx: (r) => { IDX = r; }, matches, sel, setCosp: (v) => { withCosp = v; }");
const rows = JSON.parse(fs.readFileSync("./rows.json", "utf8"));
const out = {};
try {
  s.setIdx(rows);
  const n = () => rows.filter(b => s.matches(b)).map(b => b.id);
  s.sel.sponsor.add("Ann Lee"); out.off = n();
  s.setCosp(true); out.on = n();
} catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + (e.stack || "").slice(0, 300); }
process.stdout.write("\n@@" + JSON.stringify(out));
"""
    got = _node_app(harness, {"rows.json": json.dumps(rows)})
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    assert "threw" not in got, "the Sponsor filter would not run: " + got["threw"]
    assert got["off"] == ["HB1"] and got["on"] == ["HB1", "HB2"], (
        f"a sponsor chosen keeps not exactly their prime bills (off) and prime plus co-sponsored (ticked): {got}")
    src = _source("src/pages/app.js")
    assert 'id="cosp"' in src and "Include co-sponsored bills" in src, "the Sponsor filter has no co-sponsor checkbox"
    return "ok", "a chosen sponsor keeps their prime bills; co-sponsored ones only when ticked"


@check("frontend", "no empty state says the General Court sits only from January to June")
def _sits_mostly_january_to_june():
    """"The General Court sits from January to June", on a committee's empty
    Upcoming session, the Calendar's empty week and the home page's empty
    Coming up, while the home page said both chambers sat until veto day in
    August (the survey of 7 October 2026). Both sat on 19 August 2026, and
    the House into the autumn or winter in nine of the twelve years
    2015-2026. It sits MOSTLY from January to June: every page's source that
    says when it sits says that. The home page's Coming up no longer says it
    at all (the owner's choice of 26 October 2026: the rail says what is
    scheduled), so two sources do."""
    files = [_paths.locate("app.js"), _paths.locate("find.js")] + sorted(_paths.code_files("build_*.py")) + [
        _paths.locate("civics.py")] + sorted(Path("src/pages/inline").glob("build_*.js"))
    said, bare = [], []
    for f in files:
        if not f or not Path(f).exists():
            continue
        flat = re.sub(r"\s+", " ", re.sub(r'"\s*\n\s*"', "", Path(f).read_text(encoding="utf-8")))
        bare += [Path(f).name for _ in re.finditer(r"sits from January to June", flat)]
        said += [Path(f).name for _ in re.finditer(r"sits mostly from January to June", flat)]
    assert not bare, "these still say the General Court sits from January to June: " + ", ".join(bare)
    assert sorted(said) == ["app.js", "build_calendar.py"], (
        "the two empty states that say when the General Court sits are " + ", ".join(said))
    return "ok", "the committee page and the Calendar's week say \"mostly\"; the home page says neither"


@check("frontend", "a member's page says the figures follow the term only beside a term picker")
def _term_line_with_picker():
    """The audit of 25 October 2026 (S7): a member of one term has no term
    picker, and their page still said "The figures, bills and votes follow
    the term." -- of a control that was not there. app.js in node draws a
    member page with one term and with two: the line only with the picker."""
    m = {"id": "905", "name": "Spillane, James", "chamber": "H", "seat": "3024", "district": "2",
         "county": "Rockingham", "display_full": "Rep. James Spillane (R - Rock 2)",
         "towns": ["Deerfield"], "bills": [], "votes": []}
    got = _app_js("[1, 2].map(n => (scope.setPage({kind: 'member', data: " + json.dumps(m)
                  + ", terms: ['2025-2026', '2023-2024'].slice(0, n), term: '2025-2026'}), "
                  "scope.renderMember(" + json.dumps(m) + ")))",
                  names=("renderMember", "setPage: x => (PAGE = x)"))
    if got is None:
        return "skip", "node, app.js or the stub is not here"
    one, two = got
    line = "follow the term"
    assert line not in one and '<select data-pf="term">' not in one, (
        "a member of one term is told the figures follow a term picker the page does not draw")
    assert line in two and '<select data-pf="term">' in two, (
        "a member of two terms lost the picker or the line beside it")
    return "ok", "the line beside the picker, and neither on a page of one term"


@check("frontend", "a member's page offers their bill requests for the next session as a term, opens "
       "on it when they have any and on their newest term when they have none")
def _member_requests():
    """Alice, 7 November 2026: a member's page opens its term picker on the
    new term and lists their requests as its bills until the bills are
    introduced -- number, title, House or Senate, filed or withdrawn -- with
    one line on what a request is; a member with none opens on 2025-2026
    (B4). build_lsrs names who has requests in meta.requests.by_slug; the
    page lists the requests whose sponsor_slug is theirs."""
    req = {"term": "2027-requests", "label": "2027 Bill Requests", "year": 2027, "n": 3,
           "withdrawn": 1, "by_slug": {"jodi-nelson": 2}}
    meta = {"terms": ["2025-2026", "2023-2024"], "requests": req}

    def lsr(num, title, slug, withdrawn=False):
        return {"id": f"LSR2027{num}", "n": f"LSR 2027-{num}", "year": 2027, "title": title,
                "sponsor": "x", "sponsor_label": "x", "sponsor_slug": slug, "body": "HB",
                "body_label": "House bill", "committee": "", "committees": [], "topic": "",
                "kind": "", "status": "Withdrawn" if withdrawn else "Filed as a request",
                "withdrawn": withdrawn, "term": "2027-requests", "lsr": True,
                "votedays": [], "last_action": ""}
    idx = [lsr("0002", "relative to data centers.", "jodi-nelson"),
           lsr("0007", "relative to school buses.", "jodi-nelson", True),
           lsr("0009", "relative to ferries.", "someone-else")]

    def member(slug):
        return {"id": "905", "slug": slug, "name": "Nelson, Jodi", "chamber": "H", "district": "2",
                "county": "Rockingham", "display_full": "Rep. Jodi Nelson (R - Rock 2)",
                "towns": [], "sponsored": [{"id": "HB1", "term": "2025-2026", "prime": True}],
                "votes": [], "term_figures": {}, "attendance": {}}
    later = dict(meta, terms=["2027-2028", "2025-2026", "2023-2024"])
    js = ("scope.setMeta(" + json.dumps(meta) + "), scope.setIdx(" + json.dumps(idx) + "), "
          "(() => { const m = " + json.dumps(member("jodi-nelson")) + "; const terms = "
          "scope.recordTerms('member', m); scope.setPage({kind: 'member', data: m, terms, "
          "term: terms[0]}); return scope.renderMemberBills(m, true); })(), "
          "scope.addLoaded('2027-requests'), "
          "['jodi-nelson', 'pat-none'].map(s => { const m = " + json.dumps(member("x"))
          + "; m.slug = s; const terms = scope.recordTerms('member', m); "
          "scope.setPage({kind: 'member', data: m, terms, term: terms[0]}); "
          "return {terms, prime: scope.renderMemberBills(m, true), co: scope.renderMemberBills(m, false), "
          "votes: scope.renderMemberVotes(m), picker: scope.termControl()}; })"
          ".concat([(() => { scope.setMeta(" + json.dumps(later) + "); const m = "
          + json.dumps(member("jodi-nelson")) + "; m.sponsored.push({id: 'HB5', term: '2027-2028', "
          "prime: true}); return {terms: scope.recordTerms('member', m)}; })()])")
    got = _app_js(js, names=("recordTerms", "renderMemberBills", "renderMemberVotes", "termControl",
                             "setPage: x => (PAGE = x)", "setMeta: x => (META = x)",
                             "setIdx: x => (IDX = x)", "addLoaded: t => LOADED.add(t)"))
    if got is None:
        return "skip", "node, app.js or the stub is not here"
    has, none, jan = got
    # The page is drawn before the requests are fetched: it says so, not "none".
    src = _source("src/pages/app.js")
    assert "Loading the bill requests" in src and "if(!LOADED.has(META.requests.term))" in src, (
        "a member's requests term says there are none before the list has come")
    # The member's own file, as build_site_v2 writes it, carries the slug the
    # page finds their requests by (the review of 8 November 2026: it did
    # not, and no member was offered a request).
    assert '"slug": row["slug"],' in _source("src/pages/members.py"), (
        "build_site_v2 writes no slug into a member's own file, which the page reads")
    assert jan["terms"][:3] == ["2027-2028", "2027-requests", "2025-2026"], (
        f"once 2027-2028 is published a member is offered {jan['terms']}: their bills of that "
        "term first, then the requests")
    assert has["terms"][0] == "2027-requests" and "2025-2026" in has["terms"], (
        f"a member with requests is offered {has['terms']}: the requests term first")
    assert '<option value="2027-requests" selected>2027 Bill Requests</option>' in has["picker"], (
        f"the picker does not name the requests term by its label: {has['picker'][:300]!r}")
    p = has["prime"]
    assert 'data-id="LSR20270002"' in p and 'data-id="LSR20270007"' in p \
        and 'LSR20270009' not in p, f"the member's requests are not theirs alone: {p[-400:]!r}"
    assert "Requests, not bills yet." in p and "numbered 2027 bill" in p and "2 filed for 2027, 1 of them withdrawn" in p, (
        f"the requests' one line is not there: {p[:400]!r}")
    assert "only its prime sponsor" in has["co"] and "not voted on" in has["votes"], (
        "the co-sponsored or Votes tab does not say why a request term has nothing there")
    assert none["terms"][0] == "2025-2026" and "2027-requests" not in none["terms"], (
        f"a member with no requests is offered {none['terms']}: it should open on 2025-2026 (B4)")
    return "ok", ("a member with requests opens on '2027 Bill Requests' and lists their two, one "
                  "withdrawn, with the line on what a request is; one with none opens on 2025-2026")


@check("frontend", "On the record carries no Introduced row and no LSR row")
def _on_the_record_rows():
    """"Remove the LSR number and the Introduced date from On the record" (the
    person, 7 October 2026, F14): the rail and How it got here carry the
    introduction, and the LSR number is the drafting office's reference.
    app.js's factsTable is drawn in node for a bill whose record carries both
    facts, and the panel holds its other rows and neither of those."""
    d = {"facts": {"date_introduced": "01/08/2025", "lsr": "2025-0123"},
         "subject": "Criminal Justice", "subject_source": "general court",
         "chapter": "160", "year": "2025", "house_committee": "Judiciary",
         "journey": {"steps": [{"date": "2025-02-13", "body": "H", "act": "passed",
                                "mark": "p", "text": "Passed on a voice vote"}]}}
    b = {"id": "HB57", "term": "2025-2026", "year": 2025, "status": "Signed into law",
         "topic": "Criminal Justice"}
    # THE ON THE RECORD BOX IS GONE (the person, 8 October 2026: "Remove the
    # ON THE RECORD box"; option E, 10 October 2026): what it carried is in
    # the record head's facts, How It Got Here or under the analysis, and
    # none of them carries the LSR or an Introduced row.
    assert "function factsTable(" not in _source("src/pages/app.js"), (
        "app.js still draws the On the record box")
    got = _app_js("[scope.billHead(" + json.dumps(b) + ", " + json.dumps(d) + "), "
                  "scope.renderSummary(" + json.dumps(b) + ", " + json.dumps(d) + ")]",
                  names=("billHead", "renderSummary"))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    head, summary = got
    heads = re.findall(r"<dt>([^<]*)</dt>", head)
    assert heads and "Subject" in heads, f"the head lost facts it keeps: {heads}"
    assert "Introduced" not in heads and "LSR" not in heads and \
        "2025-0123" not in head + summary, (
            f"the bill's head or summary still carries {[h for h in heads if h in ('Introduced', 'LSR')]}")
    return "ok", f"the head holds {', '.join(heads)}, and no Introduced or LSR row"


@check("frontend", "a bill's trail ends on its number, and its term opens the search on that term")
def _bill_trail_term_search():
    """The person, 10 October 2026: "Bills > 2025-2026 Term > HB 396-FN".
    The term led to the term's directory index, which most readers will not
    use, and the trail ended on the kind of measure ("House Bill"). billHead
    is drawn in node: the trail is Bills, the term opening /bills?term=, and
    the bill's own number, unlinked."""
    b = {"id": "HB396", "n": "HB 396-FN", "term": "2025-2026", "year": 2025,
         "status": "In committee"}
    got = _app_js("scope.billHead(" + json.dumps(b) + ", null)", names=("billHead",))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    trail = re.search(r'<nav class="rtrail"[^>]*><ol>(.*?)</ol></nav>', got, re.S)
    assert trail, "the bill's head has no trail"
    items = re.findall(r"<li[^>]*>(.*?)</li>", trail.group(1), re.S)
    assert len(items) == 3, f"the trail has {len(items)} steps, not 3: {items}"
    assert re.search(r'href="[^"]*bills\?term=2025-2026"', items[1]) and "Term" in items[1], (
        f"the term does not open the search on its term: {items[1]}")
    assert "directory/bills-" not in got, "the term still leads to the directory index"
    assert "<a" not in items[2] and "HB 396" in items[2], (
        f"the trail does not end on the bill's number: {items[2]}")
    return "ok", "Bills > 2025\u20132026 Term (the search on that term) > HB 396-FN"


@check("frontend", "the Bill Text tab opens on the current version in full text")
def _bill_text_opens_whole():
    """"Bill Text tab opens on the current version, in full text" (the person,
    7 October 2026, F15), not on what the last amendment changed. A bill of
    three printings, the last two compared, is drawn in node with nothing yet
    chosen: the newest printing is the one pressed, Full text is the view
    pressed, and what the pane asks for is that printing's text, not the
    comparison. Choosing What changed still shows it."""
    ix = {"versions": [{"title": "As Introduced", "date": "2025-01-08",
                        "text_url": "/versions/2025/HB57/v0.txt"},
                       {"title": "Amended by the House", "date": "2025-02-13",
                        "text_url": "/versions/2025/HB57/v1.txt"},
                       {"title": "Amended by the Senate", "date": "2025-05-22",
                        "text_url": "/versions/2025/HB57/v2.txt"}],
          "steps": [{"from": 0, "to": 1, "added": 4, "removed": 1,
                     "runs_url": "/versions/2025/HB57/s1.json"},
                    {"from": 1, "to": 2, "added": 9, "removed": 3,
                     "runs_url": "/versions/2025/HB57/s2.json"}],
          "amendments": []}
    b = {"id": "HB57", "year": 2025, "term": "2025-2026"}
    expr = ("(() => { const k = scope.verKey(" + json.dumps(b) + "); scope.VERS[k] = "
            + json.dumps(ix) + "; const first = scope.renderVersions(" + json.dumps(b)
            + ", {nver: 3}); scope.VMODE[k] = 'changes'; const asked = scope.renderVersions("
            + json.dumps(b) + ", {nver: 3}); return [scope.VMODE_FIRST, first, asked]; })()")
    got = _app_js(expr, names=("renderVersions", "verKey", "VERS", "VMODE", "VMODE_FIRST"))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    first_mode, first, asked = got
    assert first_mode == "text", f"the Bill Text tab opens on {first_mode!r}"
    pressed = re.findall(r'<button class="vbtn sel"[^>]*>([^<]*)<', first)
    assert pressed == ["Amended by the Senate"], f"the tab opens on the printing {pressed}"
    assert re.search(r'<button class="vtog sel" data-vmode="[^"|]*\|text">Full text</button>', first) \
        and not re.search(r'class="vtog sel" data-vmode="[^"]*\|changes"', first), (
            "the tab does not open on Full text")
    assert "Loading the text" in first and "Loading what changed" not in first, (
        "the tab asks for the comparison before the reader has asked for it")
    assert re.search(r'class="vtog sel" data-vmode="[^"]*\|changes"', asked) \
        and "Loading what changed" in asked, "What changed no longer shows the comparison"
    # A RULE THE DOCUMENT DRAWS IN CHARACTERS stays one line (the look of 7
    # October 2026): with Full text first, a phone showed the rule under a
    # bill's sponsors -- 65 box-drawing dashes -- wrapped onto three lines.
    # The shapes the Court's blocks files hold, and two lines that are not one.
    lines = ["─" * 65, "-" * 65, "- " * 74 + "-", "_" * 40, ". " * 80,
             "SPONSORS:\tRep. Meuse, Rock. 37", "---"]
    cls = _app_js("[" + ",".join("scope.vblkClass({k:'ln'}," + json.dumps(t) + ")"
                                 for t in lines) + "]", names=("vblkClass",))
    if cls is not None:
        want = ["vblk vblk-ln vrule"] * 5 + ["vblk vblk-ln"] * 2
        assert cls == want, f"the rule lines are classed {cls}"
    # And it asks for no width of its own (8 October 2026): its characters
    # had been the least the bill page would draw at, 151px past a 768px
    # window.
    assert re.search(r"\.vblk\.vrule\{white-space:nowrap;overflow:hidden;width:0;min-width:100%\}",
                     _source("src/pages/app.css")), (
        "a rule line may still wrap, or its width widens the page")
    return "ok", ("the newest printing, in full text; What changed one press away; a rule "
                  "drawn in characters kept to one line")


@check("build", "email following is on previews only until the About page says what it keeps")
def _follow_email():
    """workers/follow/ and functions/api/follow/ (the person's accounts of 11
    October 2026). Every follow endpoint answers 404 without FOLLOW_DB, so the
    database bound is the switch. Previews bind it, to test sign-ups; the
    production environment may bind it only once the About page carries the
    "Email updates." paragraph and no longer says the site keeps no email
    addresses -- the About page and go-live go together, as
    EMAIL_FOLLOW_CHECKLIST.md asks. The Follow pane offers email only where
    the sign-up answers and the record is in tonight's current.json, so a
    production page shows the RSS pane alone. tests/follow/ is run whole by
    _follow_tests, below."""
    if not Path("workers/follow").is_dir():
        return "skip", "no workers/follow here"
    import tomllib
    envs = tomllib.loads(_source("wrangler.toml")).get("env", {})
    def binds(env):
        return any(d.get("binding") == "FOLLOW_DB" for d in envs.get(env, {}).get("d1_databases", []))
    assert binds("preview"), "previews do not bind FOLLOW_DB, so sign-ups cannot be tested"
    # THE PAGES SAY IT ONCE THE BINDING IS THERE (22 October 2026). The file
    # holds both texts, the one before go-live and the one after, chosen by
    # whether production binds the database (_follow_privacy_gated checks
    # each), so the test is that the after text exists: until then, read as
    # "no email addresses" not in the file, it failed the go-live itself.
    about = _source("src/pages/build_exports.py")
    assert "Email updates." in about or not binds("production"), \
        "production binds FOLLOW_DB while the Data page has no text for email updates"
    # ... and the sender's address with it: with the database bound and no
    # MAIL_FROM, every sign-up was told "on its way" and sent nothing.
    pvars = envs.get("production", {}).get("vars", {})
    assert "@" in str(pvars.get("MAIL_FROM", "")) and pvars.get("FEEDBACK_URL"), \
        "production's vars have no MAIL_FROM or FEEDBACK_URL for email following"
    app = _source("src/pages/app.js")
    assert '"/api/follow/count"' in app and '"/changes/current.json"' in app, \
        "the Follow pane offers email without asking whether this deployment can take it"
    key = re.search(r'FOLLOW_SITEKEY="([^"]+)"', app)
    readme = _source("workers/follow/README.md")
    assert key and key.group(1) in readme, "app.js's Turnstile site key is not the one README.md records"
    return "ok", (f"previews bind FOLLOW_DB, production {'does' if binds('production') else 'does not'}; "
                  "the Follow pane asks before it offers email")


@check("frontend", "the Follow panel says a sign-up was taken in a pane of its own, sends once, "
                   "resets the check only for a new request, and folds RSS only under email")
def _follow_panel_states():
    """The person, 18 October 2026, after testing the panel: "once you click
    submit for your email, the display doesn't look like much happened if
    anything because only the text below it changes, and the Cloudflare
    verification reloads when you click submit so it looks like your email
    request didn't actually go through even when it did. By RSS should be
    under a drop-down within the pop-up for following with email as the
    default following method."

    tests/test_follow_panel.js draws the panel from app.js on a small real
    tree (dom_stub.js answers every question with an empty element, so
    nothing asked of it can be wrong) and presses it, with the endpoints and
    Turnstile stubbed. Held, each case failing if its part is undone:

      email first, and the feed in a closed "Follow by RSS instead"
      disclosure under it -- but where the sign-up does not answer or
      tonight's list does not name the record, the feed is the pane, open,
      with its address and Copy the address, never behind a disclosure with
      nothing else beside it;
      while sending, the button says Sending... and is disabled, the form is
      busy, and three presses send one request;
      a sign-up taken hides the form and shows Check your email, a heading
      with the keyboard on it, the address, what to do with the email, and
      Daily or Weekly in the manage page's words -- and it stays;
      Turnstile is neither reset nor drawn again on a sign-up taken, and no
      widget is in view beside the confirmation;
      a refusal keeps what was typed, is drawn as a refusal, gives the
      button back and resets the check once, and the retry goes with the new
      token; Turnstile's own codes are named; an address that is not one
      sends nothing and resets nothing;
      Enter it again brings the form back with its address under the
      keyboard and a fresh check;
      the disclosure opens inside the pane without shutting it, a press
      elsewhere in the pane does not fold it, and a press outside still shuts
      Follow, as opening Cite does.

    And the confirmation's words for how often are manage.js's own, so the
    page that changes the choice later says it the same way."""
    js, stub, harness = Path("src/pages/app.js"), Path("tests/dom_stub.js"), Path("tests/test_follow_panel.js")
    absent = [str(p) for p in (js, stub, harness) if not p.exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    app = _source(js)
    manage = Path("functions/api/follow/manage.js")
    if manage.exists():
        hints = dict(re.findall(r'radio\("frequency", "(daily|weekly)", freq, "[^"]+", "([^"]+)"\)',
                                _source(manage)))
        told = re.search(r"const FOLLOW_OFTEN=\{daily:\"([^\"]+)\",\s*weekly:\"([^\"]+)\"\}", app)
        assert told and set(hints) == {"daily", "weekly"}, \
            "app.js's FOLLOW_OFTEN or manage.js's How often hints are not where this check reads them"
        assert (told.group(1), told.group(2)) == (hints["daily"], hints["weekly"]), (
            f"the confirmation says how often as {told.groups()}, the manage page as "
            f"{(hints['daily'], hints['weekly'])}")
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return "skip", "node is not on PATH"
    root = Path(tempfile.mkdtemp(prefix="gr-followpanel-"))
    try:
        (root / "page.js").write_text(_with_components(app), encoding="utf-8")
        r = _run([node, str(harness.resolve()), str(root / "page.js"), str(stub.resolve())],
                 cwd=root, capture_output=True, text=True, timeout=120)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    said = (r.stdout or "").strip().splitlines()
    try:
        out = json.loads(said[-1]) if said else {}
    except ValueError:
        out = {}
    assert "cases" in out, "the panel's states did not run: " + ((r.stderr or r.stdout or "").strip()[-400:])
    assert r.returncode == 0 and not out["fail"], "the Follow panel:\n    " + "\n    ".join(out["fail"][:8])
    assert len(out["cases"]) >= 9, f"only {len(out['cases'])} of the panel's cases ran"
    return "ok", (f"{len(out['cases'])} cases: email first with RSS folded (open where email is not "
                  "offered), Sending... and one request, Check your email with no reset, a refusal "
                  "kept and reset once, Enter it again")


_REPORT_TAB_JS = r"""
const { validate } = await import(%s);
const src = %s;
const grab = re => { const m = src.match(re); if (!m) throw new Error("not in app.js: " + re); return m[0]; };
const code = [/const BILL_TABS=\{[^}]*\};/, /const MEMBER_TABS=\{[^}]*\};/, /const COMMITTEE_TABS=\{[^}]*\};/,
  /const TAB_PATH=.*;/, /const ownSlug=.*;/, /const isTabSlug=.*;/,
  /function reportPath\(\)\{[\s\S]*?\n\}/, /const REPORT_TABS=new Set\(\[[\s\S]*?\]\);/].map(grab).join("\n");
const location = { pathname: "" };
const [reportPath, REPORT_TABS] = new Function("location",
  code + "\nreturn [reportPath, REPORT_TABS];")(location);
const base = { field: "status", note: "the date is wrong", build: "", elapsed: 9000 };
const out = [];
// Each address with the label its open tab shows, sent as app.js sends it.
for (const [record, paths] of [
    ["bill:2026/HB1", [["/bill/2026/hb1", "Summary"], ["/bill/2026/hb1.html", "Summary"],
                       ["/bill/2026/hb1/votes", "Votes (12)"], ["/bill/2026/hb1/text/", "Bill Text"],
                       ["/bill/2026/hb1/hearings", "Hearings (2)"], ["/bill/2026/hb1/related", "Related (3)"]]],
    ["committee:H05", [["/committee/H05", "Bills (40)"], ["/committee/H05/sessions", "Meetings (9)"],
                       ["/committee/H05/videos", "Videos (7)"], ["/committee/H05/bills", "Bills (40)"]]],
    ["committee:S03-1989", [["/committee/S03-1989", "Bills (1,204)"], ["/committee/S03-1989/videos", "Videos (1)"]]],
    ["study:ss1451", [["/committee/ss1451", "Meetings (4)"], ["/committee/ss1451/bills", "Bills (2)"],
                      ["/committee/ss1451/videos", "Videos (3)"]]]]) {
  for (const [p, label] of paths) {
    location.pathname = p;
    const url = reportPath();
    const name = label.replace(/\s*\([\d.,\s']+\)\s*$/, "");
    const tab = REPORT_TABS.has(name) ? name : "";
    const got = validate({ ...base, record, url, tab });
    out.push([record, p, url, got !== null, tab, got ? got.tab : null]);
  }
}
// A bill's page loaded before its Hearings tab was renamed still sends Videos.
location.pathname = "/bill/2026/hb1/videos";
const old = validate({ ...base, record: "bill:2026/HB1", url: reportPath(), tab: "Videos" });
out.push(["bill:2026/HB1", location.pathname, reportPath(), old !== null, "Videos", old ? old.tab : null]);
location.pathname = "/legislator/jane-doe-hills-12/votes";
out.push(["member", location.pathname, reportPath(), null, "", null]);
console.log("@@" + JSON.stringify(out));
"""


@check("build", "a report is sent from the record's own address whatever tab is open, and "
       "report.js takes it", needs=())
def _report_from_any_tab():
    """A tab writes its name into the address (app.js tabAddress), and a
    report sent from any tab but the first named /bill/2026/hb1/votes, which
    report.js does not take: the reader was thanked and the report dropped
    (30 October 2026). app.js's own reportPath, with its tab
    maps, is run here on every tab of a bill, a committee and a member,
    and report.js's validate must take each."""
    js, fn = Path("src/pages/app.js"), Path("functions/api/report.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and fn.exists() and node):
        return "skip", "app.js, report.js or node is not here"
    root = Path(tempfile.mkdtemp())
    try:
        t = root / "go.mjs"
        t.write_text(_REPORT_TAB_JS % (json.dumps(fn.resolve().as_uri()),
                                       json.dumps(_source(js))), encoding="utf-8")
        r = _run([node, str(t)], capture_output=True, text=True, timeout=60)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert r.returncode == 0 and "@@" in (r.stdout or ""), (r.stderr or r.stdout or "")[-400:]
    rows = json.loads(r.stdout.rsplit("@@", 1)[1])
    bad = [f"{p} sent as {u} for {rec}" for rec, p, u, ok, _t, _s in rows if ok is False]
    assert not bad, "report.js refuses a report from a tab: " + "; ".join(bad[:4])
    member = [u for rec, p, u, ok, _t, _s in rows if rec == "member"]
    assert member == ["/legislator/jane-doe-hills-12"], f"a member's Votes tab sent {member}"
    # AND THE TAB IT WAS SENT FROM (the walk of 31 October 2026): a
    # committee's and a study committee's Videos tab sent tab "", and a bill's
    # old Videos is stored as its Hearings, a committee's Videos as Videos.
    unnamed = [p for rec, p, u, ok, t, _s in rows if ok and not t]
    assert not unnamed, f"a report from these tabs names no tab: {unnamed}"
    stored = {(rec.split(":")[0], p.rstrip("/").rsplit("/", 1)[-1]): s for rec, p, u, ok, t, s in rows if ok}
    assert stored.get(("bill", "videos")) == "Hearings" and stored.get(("bill", "hearings")) == "Hearings", (
        "a bill's Hearings tab, by its old name or its new, is not stored as Hearings")
    assert stored.get(("committee", "videos")) == "Videos" and stored.get(("study", "videos")) == "Videos", (
        "a committee's or a study committee's Videos tab is not stored as Videos")
    return "ok", (f"{len(rows)} addresses, every tab's report sent from its record's own address, "
                  "naming the tab it was sent from")


REPORT_BOX_TEST = r"""
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { onRequest } from %s;
const require = createRequire(import.meta.url);
require("./stub.js");
const on = {};
document.addEventListener = (t, f) => { (on[t] = on[t] || []).push(f); };
let env = {};
let calls = 0;
// The page's fetch, wired to the Function itself: what the box shows is what
// report.js answers, not a status this test made up.
globalThis.fetch = async (url, opts = {}) => {
  if (url !== "/api/report")
    return { ok: true, status: 200, json: async () => ({}), text: async () => "" };
  calls++;
  return onRequest({ env, request: new Request("https://graniterecord.org/api/report", {
    method: opts.method, body: opts.body,
    headers: { ...opts.headers, "Origin": "https://graniterecord.org" } }) });
};
try { (0, eval)(readFileSync("./page.js", "utf8")); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
// A page may carry other submit listeners (the votes page's form has its
// own); a browser hands the event to every one, in order, so the test does.
if ((on.submit || []).length < 1) {
  console.log("nothing listens for the report box being sent"); process.exit(1); }
globalThis.setTimeout = () => 0;    // the six-second give-up never fires here
Object.assign(location, { pathname: "/legislator/adam-schroadter",
  hostname: "graniterecord.org", origin: "https://graniterecord.org" });
const page = { fetch: async () => new Response('<script>window.GR_MEMBER="377020";</script>') };
async function send(note) {
  const st = { textContent: "", innerHTML: "" }, btn = { disabled: false };
  const box = { dataset: { rkind: "member", rref: "377020" } };
  const form = { dataset: { opened: String(Date.now() - 9000) },
    elements: { note: { value: note }, field: { value: "other" }, website: { value: "" } },
    closest: s => s === ".reportform" ? form : s === ".report" ? box : null,
    querySelector: s => s === ".reportstate" ? st : btn };
  const sent = { target: form, preventDefault() {} };
  await Promise.all(on.submit.map(f => f(sent)));
  return { st, left: form.elements.note.value };
}
const fail = [];
// The project's own address, never a person's, with the reader's words kept
// and the reason in words a reader can use.
const offered = (x, why) => x.st.innerHTML.includes("mailto:contact@graniterecord.org") &&
  x.st.innerHTML.includes(why) && x.left !== "" &&
  !/Thank you/.test(x.st.textContent + x.st.innerHTML);
const SAVE = "could not save it just now", FULL = "taking no more reports just now";
let rows = 0;
const good = { DB: { prepare: () => ({ bind: () => ({ first: async () => 1,
  run: async () => { rows++; } }) }) } };
const boom = async () => { throw new Error("D1_ERROR"); };
env = { ASSETS: page };
if (!offered(await send("No database is bound here."), SAVE)) fail.push("no database: no email offered");
env = { ASSETS: page, DB: { prepare: () => ({ bind: () => ({ first: async () => 1, run: boom }) }) } };
if (!offered(await send("The insert throws here."), SAVE)) fail.push("the insert throws: no email offered");
// The day's ceiling already reached: the count's statement returns no row.
// Until 24 September this answered 204 and the box said thank you.
env = { ASSETS: page, DB: { prepare: () => ({ bind: () => ({ first: async () => null,
  run: async () => { rows++; } }) }) } };
const full = await send("The day is already at its ceiling.");
if (!offered(full, FULL) || rows !== 0)
  fail.push("a full day: no email offered, or a row stored: " +
            JSON.stringify({ text: full.st.textContent, html: full.st.innerHTML, rows }));
env = { ASSETS: page, DB: good.DB };
const ok = await send("The district shown is out of date.");
if (!(ok.st.textContent.startsWith("Thank you") && ok.left === "" && rows === 1))
  fail.push("a kept report from a former member's page was not thanked and cleared: " +
            JSON.stringify({ text: ok.st.textContent, html: ok.st.innerHTML, rows }));
if (calls !== 4) fail.push(`the box posted ${calls} times for 4 sends`);
console.log(fail.length ? "FAILED: " + fail.join("; ") : "ALL OK");
process.exit(fail.length ? 1 : 0);
"""


@check("build", "a report the site could not keep offers the reader the email address, not thanks")
def _report_box_fallback():
    """The box on the page and the Function behind it, run together in node.

    The box offers the email address with the reader's words filled in only
    when the reply is not a success, and until 24 September the Function
    answered 204 when no database was bound or the database refused the
    write. A storage failure thanked the reader for a report nobody would
    read. This posts from app.js's own submit handler, on a former member's
    page with no seat number in its address, into report.js's own onRequest:
    with no database and with a throwing insert the box must offer the email
    address and keep the words; with a working one it must say thank you.

    A day already at its ceiling was the same fault in another place: 204,
    and thanks, for every report after the five hundredth. It answers 429 now
    and the box must offer the address for it too, saying the site is taking
    no more reports rather than that it could not save one.
    """
    fn, app, stub = Path("functions/api/report.js"), Path("src/pages/app.js"), Path("tests/dom_stub.js")
    absent = [str(p) for p in (fn, app, stub) if not p.exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    node = shutil.which("node")
    if not node:
        return "skip", "node is not on PATH"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(app)), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        t = root / "t.mjs"
        t.write_text(REPORT_BOX_TEST % json.dumps(fn.resolve().as_uri()), encoding="utf-8")
        r = _run([node, str(t)], capture_output=True, text=True, cwd=root)
        assert r.returncode == 0 and "ALL OK" in r.stdout, (r.stdout + r.stderr).strip()[-400:]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("no database, a failed insert and a full day each offer the email "
                  "address with the words kept; a stored report from "
                  "/legislator/adam-schroadter is thanked")


@check("data", "no page but the search page opens with the hidden heading \"New Hampshire bills\"")
def _sr_heading():
    """bills.html carries a visually hidden <h1>New Hampshire bills</h1>, and
    every page built from it inherits the line unless shell.page is told
    otherwise. The bill pages were told on the 11th; the 406 member pages, the
    committee pages and the committees index were not, so a screen reader
    opening Rep. Aboul Khan's page heard "New Hampshire bills" as its first
    heading and the member's name as its second. Read from the built pages:
    a bill page from every year, and every other page built from the
    template."""
    site = Path("site")
    if not (site / "bills.html").exists():
        return "skip", "no site built"
    line = '<h1 class="sr">New Hampshire bills</h1>'
    pages = [p for p in site.glob("*.html") if p.name != "bills.html"]
    for sub in ("legislator", "committee", "learn", "town"):
        pages += sorted((site / sub).glob("*.html"))
    for d in sorted((site / "bill").glob("*")):
        pages += sorted(d.glob("*.html"))[:3]
    bad = [str(p.relative_to(site)) for p in pages
           if line in p.read_text(encoding="utf-8", errors="replace")]
    assert not bad, (f"{len(bad)} of {len(pages)} pages still open with it: "
                     + ", ".join(bad[:4]))
    return "ok", f"{len(pages):,} pages, each with its own first heading"


@check("frontend", "a report with no reasoning says what it does record: the recommendation, the vote, both or neither")
def _report_no_reasons_says_what():
    """The Reports tab said "This report records the recommendation and the
    vote, and gives no reasoning" of every report with no text, and HB 1547
    of 2010's interim study statement records a recommendation and no vote
    (the manager, 29 October 2026). app.js's reportNoReasons names what is
    there, and renderReports asks it with the report's own recommendation and
    tally."""
    got = _app_js("[[true,true],[true,false],[false,true],[false,false]].map(a => scope.reportNoReasons(...a))",
                  names=("reportNoReasons",))
    if got is None:
        return "skip", "node, app.js or tests/dom_stub.js is not here"
    assert got == ["This report records the recommendation and the vote, and gives no reasoning.",
                   "This report records the recommendation, and gives no reasoning.",
                   "This report records the vote, and gives no reasoning.",
                   "This report gives no reasoning."], got
    src = _source("src/pages/app.js")
    assert "reportNoReasons(!!rec,!!committeeTally(e))" in src, (
        "renderReports no longer asks reportNoReasons with the report's recommendation and tally")
    assert "records the\n             recommendation and the vote" not in src, (
        "the fixed sentence is back in renderReports")
    return "ok", "both, the recommendation alone, the vote alone and neither each read as what the report records"


# A HEAD THAT HAS GROWN PAST THE FIRST READ (29 October 2026). _one_head
# reads the first 16,384 bytes of each of some 38,000 pages to find the end of
# its head. The election worker's guide carries a HowTo of 10,962 bytes in
# its structured data, and its head ended at byte 16,408: the R1 dry run
# (153) held the night on it although the page was right. Only a page whose
# head has not ended in the first read is read on, to HEAD_MOST, so the
# night still reads 16 KB of nearly every page.
HEAD_MOST = 262144


def _head_bytes(path, first, most=None):
    """The first `first` bytes of `path`, or, where no </head> ends in them,
    on to `most` (HEAD_MOST) bytes or the file's end."""
    most = HEAD_MOST if most is None else most
    with open(path, "rb") as fh:
        raw = fh.read(first)
        if b"</head>" not in raw and len(raw) == first and most > first:
            raw += fh.read(most - first)
    return raw


@check("frontend", "a page's head is read to its end however long it has grown, up to "
       "HEAD_MOST, and only such a page is read past the first 16 KB")
def _head_bytes_read_on():
    """_one_head's reading, without a built site: a head ending at byte
    16,408 (the election worker's guide on 29 October 2026) is read to its
    end; a head that ends early costs one 16 KB read; a page with no head end
    in HEAD_MOST bytes stops there."""
    d = Path(tempfile.mkdtemp(prefix="heads_"))
    try:
        body = b"<p>" + b"x" * 40000 + b"</p></body></html>"
        long_head = b"<html><head><title>t</title>" + b"<!--" + b"h" * 16360 + b"-->" + b"</head><body>" + body
        short_head = b"<html><head><title>t</title></head><body>" + body
        endless = b"<html><head><title>t</title>" + b"y" * 300000
        for name, data in (("long", long_head), ("short", short_head), ("endless", endless)):
            (d / f"{name}.html").write_bytes(data)
        assert long_head.find(b"</head>") > 16384, "the long head ends inside the first read"
        got = _head_bytes(d / "long.html", 16384)
        assert b"</head>" in got and len(got) > 16384, (
            "a head ending past byte 16,384 is not read to its end")
        got = _head_bytes(d / "short.html", 16384)
        assert len(got) == 16384, f"a head that ended early was read on ({len(got):,} bytes)"
        got = _head_bytes(d / "endless.html", 16384)
        assert len(got) == HEAD_MOST and b"</head>" not in got, (
            "a page with no head end was not read to HEAD_MOST and stopped")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return "ok", (f"a head ending at byte {long_head.find(b'</head>'):,} is read to its end, "
                  f"a short one costs 16 KB, a page with none stops at {HEAD_MOST:,}")


@check("frontend", "a page says what it is once, and says where it lives")
def _one_head():
    """Exactly one title, one description and one canonical per page.

    shell.page() builds a head that begins with the viewport meta and
    substitutes it into bills.html -- which left the template's own <title>
    in place, so every generated page carried two. Browsers show the first;
    a crawler may take either.

    THE HEAD, AND NOT THE PAGE (2 October 2026). This read every page whole,
    1.4 GB, to look at its first 6,000 characters -- and 700 of the 38,028
    pages have a head longer than that: 7,655 characters on CACR 23 of 2000,
    whose title and description are long. A second canonical link past
    character 6,000 of those was never seen, and nothing said so. Now the
    first HEAD_BYTES of a page are read, the tags are counted in its first
    6,000 characters as before AND on to the end of its head, and a page
    whose head does not end in what was read fails by name.
    """
    HEAD_BYTES = 16384              # the longest head was 7,665 bytes on 2 October 2026
    site = Path("site")
    if not site.exists():
        return "skip", "site is not built"
    bad, n = [], 0
    for p in sorted(site.rglob("*.html")):
        raw = _head_bytes(p, HEAD_BYTES)
        # A line's end is one character however the file writes it, as it was
        # when the page was read as text: the built pages end their lines
        # with two here, and counting both put the 6,000th character a line's
        # worth of characters early for every line before it.
        h = raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
        end = h.find("</head>")
        if len(raw) == HEAD_BYTES and len(h) < 6000:
            # Three bytes to a character and more: read it as it always was.
            h = p.read_text(encoding="utf-8", errors="replace")
            end = h.find("</head>")
        n += 1
        if end < 0 and len(raw) >= HEAD_BYTES:
            bad.append(f"{p.relative_to(site)}'s head does not end in its first "
                       f"{len(raw):,} bytes, so its tags were not all read (raise "
                       "HEAD_MOST in _head_bytes if a head has really grown that long)")
            continue
        h = h[:max(6000, end + len("</head>"))]
        for what, pat in (("title", r"<title>"),
                          ("description", r'<meta name="description"'),
                          ("canonical", r'<link rel="canonical"')):
            c = len(re.findall(pat, h))
            if c > 1:
                bad.append(f"{p.relative_to(site)} has {c} {what} tags")
            elif c == 0 and what == "title":
                bad.append(f"{p.relative_to(site)} has no title")
        if len(bad) > 12:
            break
    assert not bad, (f"{len(bad)} page(s) name themselves more than once, or have "
                     "a head that was not read to its end: " + "; ".join(bad[:4]))
    return "ok", f"{n:,} pages, one head each, each read to its end"


@check("frontend", "a bill whose printed line names nobody says its sponsors are the General Court's record")
def _unprinted_sponsor_note():
    """1991 HCR 13 and HR 19 print "INTRODUCED BY: REFERRED TO:" and no name, and are named
    from the General Court's sponsor record (text_sponsors.unprinted). Every other sponsor
    of that term was read off the bill's own line, and the page says so of them; these say
    where theirs came from instead.

    AND A BILL OF 1989-1998 SAYS WHERE ITS NAMES WERE READ, AND NO MORE (the owner, 14 November
    2026: "not necessary to get into that fine of detail and just let the pages speak for
    themselves"). The note had grown sentences on how the General Court's sponsor record placed
    a name (past_roster.py), on the Manual for the General Court and on the roll calls of those
    years, and called names "matched to one member who voted that term" of years with no named
    roll call here. Held: a mixed bill (1997 HB 455), one whose names were all placed (1989 HB
    553) and one that places none (1995 HB 174) each say exactly "As named on the sponsor line
    of the bill's text, where the first name is the prime sponsor." and none of "Named roll
    calls", "Manual", "voted that term" or "prints only a surname"; a bill of 1999-2022 (a 2005
    HB 1 here) keeps its note exactly, "A name without a party is shown as the text prints it"
    with it."""
    placed = ('{name: "Richard Dolan", chamber: "H", label: "Rep. Richard Dolan (Rock 12)", '
              'member_id: "375990", employee: "375990", matched: "General Court sponsor record", '
              'source: "bill text", as_printed: "Rep. Dolan, Rock 12"}')
    got = _app_js(
        '[scope.renderSponsors({id: "HCR13"}, {sponsors: [{name: "Michael Hill", '
        'chamber: "H", label: "Rep. Michael Hill", prime: true, unprinted: true, '
        'source: "General Court sponsor record"}]}), '
        'scope.renderSponsors({id: "HB1"}, {term: "2005-2006", sponsors: [{name: "Vartanian", chamber: "H", '
        'label: "Rep. Vartanian (Rock 20)", prime: true, source: "bill text"}]}), '
        'scope.renderSponsors({id: "HB455"}, {term: "1997-1998", sponsors: [{name: "Christie", chamber: "H", '
        'label: "Rep. Christie (Rock 22)", prime: true, source: "bill text", member_id: "", '
        'as_printed: "Rep. Christie, Rock 22"}, ' + placed + ', {name: "John Anthony Simmons", '
        'chamber: "H", label: "Rep. John Anthony Simmons (Rock 25)", member_id: "", '
        'employee: "376049", matched: "General Court sponsor record", source: "bill text"}]}), '
        'scope.renderSponsors({id: "HB553"}, {term: "1989-1990", sponsors: [Object.assign(' + placed
        + ', {prime: true})]}), '
        'scope.renderSponsors({id: "HB174"}, {term: "1995-1996", sponsors: [{name: "Christie", chamber: "H", '
        'label: "Rep. Christie (Rock 22)", prime: true, source: "bill text", member_id: "", '
        'as_printed: "Rep. Christie, Rock 22"}]})]',
        names=("renderSponsors",))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    record, text, mixed, placed_only, none_placed = got
    notes = lambda h: [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", n)).replace("&rsquo;", "’").strip()
                       for n in re.findall(r'<p class="note"[^>]*>(.*?)</p>', h, re.S)]
    line = "As named on the sponsor line of the bill's text, where the first name is the prime sponsor."
    for what, h in (("a mixed 1989-1998 bill (1997 HB 455)", mixed),
                    ("a 1989-1998 bill whose names were all placed (1989 HB 553)", placed_only),
                    ("a 1989-1998 bill that places no name (1995 HB 174)", none_placed)):
        more = [w for w in ("Named roll calls", "Manual", "voted that term", "prints only a surname") if w in h]
        assert notes(h) == [line] and not more, (
            f"{what} says more than where its names were read: {notes(h)}" + (f", with {more}" if more else ""))
    assert "names no" in record and "sponsor record" in record \
        and "As named on the sponsor line" not in record, (
        "a bill whose line names nobody does not say its sponsors are the General Court's "
        "record: " + re.sub(r"\s+", " ", record)[-240:])
    assert notes(text) == [line + " A name without a party is shown as the text prints it: it could not be "
                                  "matched to one member who voted that term."], (
        "a bill of 1999-2022 named off its own line lost its note, or gained the record's, or lost \"A name "
        f"without a party is shown as the text prints it\": {notes(text)}")
    return "ok", ("the record's names say so; a line's names keep their own note; a 1989-1998 bill, its "
                  "names placed, mixed or not, says where they were read and no more; 1999-2022 keep "
                  "'without a party'")


@check("build", "members-elect on the pages: each one linked goes to their own member's page, a "
                "new person to none, and the line is on the own page of each re-elected or "
                "returning member and of nobody else")
def _elect_pages_link_own():
    """The plan's check 2, for the pages (the person's decisions of 16 October
    2026). On the fixture's election with the person's file: every link
    inside an element carrying data-elect -- on the town pages, the Officials
    tab and the My Town card -- goes to the page of the member the file
    names, that page's GR_MEMBER the file's id, and every member the file
    links is linked somewhere; Pat Newell, new and cross-nominated, is drawn
    on the neutral chip with both letters and never as a link -- on the
    Members-Elect tab as the Legislators tab's chip, "Rep.-elect Pat Newell
    (R/D - Rock 32)", with NEW beside it, in each of its two views (the
    owner's walks of 7 and 8 November 2026); and the one
    line -- "Elected November 3, 2026, for Rockingham district 6. Takes
    office December 2, 2026." -- is on the own page of Jodi Nelson, Debra
    Altschiller, Michael Vose and the John Smith the person's file names
    (900002), each naming the race's own county and district (Vose's is
    district 6, where his former seat was 5), and on no other page: not on
    the other John Smith's (900003), nor on any sitting member's the list
    does not name. app.js draws the same line from GR_ELECT, and only for
    the member it names, and heads a returning member's page with the title
    GR_ELECT gives, "Rep.-elect". And a place's "e" is its own races."""
    absent = _elect_absent()
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    w, _o, doc, _said = _elect_built()
    ws = w / "site"
    want = {}
    for key, r in doc["races"].items():
        for e in r["elected"]:
            if e.get("s"):
                want[e["s"]] = (str(e["id"]), key)
    assert {s: k for s, (_i, k) in want.items() if s.startswith(("michael-vose", "john-smith"))} \
        == {"michael-vose-rock-5": "H|Rockingham|6", "john-smith-rock-3": "H|Rockingham|13"} \
        and len(want) == 4, f"the fixture's file links {want}, not the four the check is about"
    bad, linked = [], set()

    def member_of(slug):
        f = ws / "legislator" / f"{slug}.html"
        m = re.search(r'window\.GR_MEMBER=("[^"]*")', f.read_text(encoding="utf-8")) \
            if f.exists() else None
        return json.loads(m.group(1)) if m else None
    sources = {f.relative_to(ws).as_posix(): f.read_text(encoding="utf-8")
               for f in ws.rglob("*.html")}
    card = _elect_card(ws / "places.json", ws / "places.json")
    if card is not None:
        sources.update({f"(My Town card) {s}": h for s, h in card["with"].items()})
    for rel, text in sources.items():
        for a, b in _elect_blocks(text):
            for slug in re.findall(r'href="/?legislator/([a-z0-9-]+?)(?:\.html)?"', text[a:b]):
                linked.add(slug)
                if slug not in want:
                    bad.append(f"{rel} links a member-elect to {slug}, which the file names for "
                               "nobody")
                elif member_of(slug) != want[slug][0]:
                    bad.append(f"{rel} links a member-elect to {slug}, the page of "
                               f"{member_of(slug)}, not {want[slug][0]}")
        if re.search(r"<a\b[^>]*>(?:(?:Rep|Sen)\.-elect )?Pat Newell", text):
            bad.append(f"{rel} links Pat Newell, a new person")
    if set(want) - linked:
        bad.append(f"never linked: {sorted(set(want) - linked)}")
    newell = ('<span class="mchip p-X" translate="no">Pat Newell <span class="mtag">(R/D)</span></span>')
    for rel in ("town/brentwood.html", "town/danville.html", "town/fremont.html"):
        if newell not in sources[rel]:
            bad.append(f"{rel} does not draw Pat Newell on the neutral chip with both letters")
    # The Members-Elect tab draws the Legislators tab's chip, with a title and
    # the district, and the word beside it (the owner's walks of 7 and 8
    # November 2026), in each of its two views.
    tab = re.findall(r'<span class="mchip p-X" translate="no">Rep\.-elect Pat Newell <span class="mtag">'
                     r'\(R/D - Rock \d+\)</span></span> <span class="elkind" translate="yes">New</span>',
                     sources["officials.html"])
    if len(tab) != 2:
        bad.append(f"officials.html draws Pat Newell {len(tab)} times on the neutral chip with both "
                   "letters and his district, NEW beside it, not once in each of the tab's two views")
    # Members-Elect beside Legislators (the owner's walk of 8 November 2026):
    # My Town, Legislators, Members-Elect, then the rest.
    strip = re.findall(r'role="tab" id="tab-([a-z-]+)" data-pane="\1"', sources["officials.html"])
    if strip[:3] != ["my-town", "legislators", "members-elect"]:
        bad.append(f"officials.html's tabs run {strip}: Members-Elect is not right of Legislators")
    words = {"H|Rockingham|13": "Rockingham district 13", "H|Rockingham|6": "Rockingham district 6",
             "S|24": "Senate District 24"}
    lines = {}
    for f in (ws / "legislator").glob("*.html"):
        t = f.read_text(encoding="utf-8")
        line = re.findall(r'<p class="elline" data-elect data-until="2026-12-02">(.*?)</p>', t)
        g = re.findall(r"window\.GR_ELECT=(\{[^{}]*\});", t)
        if line or g or "data-elect" in t:
            lines[f.stem] = (line, [json.loads(x) for x in g])
    if set(lines) != set(want):
        bad.append(f"the line is on {sorted(lines)}, not on {sorted(want)}")
    for slug, (line, g) in lines.items():
        mid, key = want.get(slug, ("", ""))
        # A returning member's page is the member-elect's (13 November 2026):
        # the line a new member-elect's page has, the seat in the sentence above it.
        if slug in ("michael-vose-rock-5", "john-smith-rock-3"):
            ok = (line == ["Elected November 3, 2026. Takes office December 2, 2026."]
                  and len(g) == 1 and g[0].get("mode") == "returning"
                  # The title the page is headed with (16 November 2026).
                  and g[0].get("title") == "Rep.-elect"
                  and g[0].get("where") == "Member-elect of the New Hampshire House of "
                  f"Representatives, {words.get(key).replace(' district', '')}."
                  and {k: v for k, v in g[0].items() if k in ("id", "key", "election", "takes_office")}
                  == {"id": mid, "key": key, "election": "2026-11-03", "takes_office": "2026-12-02"})
        else:
            ok = (line == [f"Elected November 3, 2026, for {words.get(key)}. Takes office "
                           "December 2, 2026."]
                  and g == [{"id": mid, "key": key, "election": "2026-11-03",
                             "takes_office": "2026-12-02"}])
        if not ok:
            bad.append(f"{slug}'s page says {line} and hands app.js {g}")
    for p in json.loads((ws / "places.json").read_text(encoding="utf-8"))["places"]:
        own = [f"H|{h[0]}|{h[1]}" for h in p["h"]] + ([f"S|{p['sd']}"] if p.get("sd") else [])
        if p.get("e") != own:
            bad.append(f"places.json gives {p['s']} the races {p.get('e')}, not its own {own}")
    vose = {"id": "900001", "name": "Vose, Michael", "chamber": "H", "former": True,
            "display_full": "Rep. Michael Vose (R - Rock 5)", "party": "R"}
    smith = dict(vose, id="900003", name="Smith, John", display_full="Rep. John Smith (R - Rock 20)")
    g = json.dumps({"id": "900001", "key": "H|Rockingham|6", "election": "2026-11-03",
                    "takes_office": "2026-12-02"})
    got = _app_js("[(window.GR_ELECT=" + g + ", scope.renderMemberHead(" + json.dumps(vose) + ")), "
                  "scope.renderMemberHead(" + json.dumps(smith) + "), "
                  "(delete window.GR_ELECT, scope.renderMemberHead(" + json.dumps(vose) + "))]",
                  names=("renderMemberHead",))
    if got is not None:
        line = ('<p class="elline" data-elect data-until="2026-12-02">Elected November 3, 2026, '
                "for Rockingham district 6. Takes office December 2, 2026.</p>")
        if [line in h for h in got] != [True, False, False]:
            bad.append("app.js draws the line on the member's page "
                       f"{[line in h for h in got]}: wanted on Vose's with GR_ELECT naming him, "
                       "not on another member's, and not without GR_ELECT")
    assert not bad, "; ".join(bad)
    return "ok", (f"{len(linked)} members-elect linked, each to their own page; Pat Newell "
                  "unlinked on the neutral chip; the line on the four own pages and no other, in "
                  "the race's own words"
                  + (", and app.js draws it only for the member named" if got is not None else ""))


# map.js mounted on dom_stub.js's element, its data never arriving: what is
# held is the markup mount() writes and the api it returns before any data.
_MAP_TOGGLE_JS = r"""
require("./stub.js");
globalThis.fetch = () => new Promise(() => {});
const G = require("./map.js");
function mount(opts) {
  const root = document.createElement("div");
  const api = G.mount(root, opts);
  return { html: root.innerHTML, api };
}
const out = { labels: G.LABELS, def: G.DEFAULT_LABELS };
const a = mount({});
out.plain = { html: a.html, labels: a.api.labels() };
a.api.setLabels("none"); out.afterNone = a.api.labels();
a.api.setLabels("numbers"); out.afterNumbers = a.api.labels();
a.api.setLabels("bogus"); out.afterBogus = a.api.labels();
const b = mount({ labels: "numbers" });
out.numbers = { html: b.html, labels: b.api.labels() };
out.bogus = mount({ labels: "bogus" }).api.labels();
console.log(JSON.stringify(out));
"""


@check("frontend", "the district map's label toggle offers town names, district numbers and no "
                   "labels, as one group of radio buttons, with town names chosen first")
def _map_label_toggle():
    """The person, 9 October 2026: "Toggle to switch between viewing district
    numbers, town names, and no labels for the interactive map with the default
    being town names."

    map.js mounted in node: the three modes in map.js's LABELS, in the order
    drawn, with the words drawn; DEFAULT_LABELS "names"; the toggle written as
    native radio buttons sharing one name inside a radiogroup labelled for a
    screen reader, so arrow keys move within it and it is read as "1 of 3",
    with only Town names checked on a plain mount and only District numbers
    when a page asks for them; a mode a page names that is not one of the
    three falls back to town names; and setLabels() changes the mode to each
    of the three and refuses anything else.
    """
    if not shutil.which("node"):
        return "skip", "node is not installed"
    js, stub = Path("src/pages/map.js"), Path("tests/dom_stub.js")
    if not (js.exists() and stub.exists()):
        return "skip", "map.js or dom_stub.js is not in this directory"
    root = Path(tempfile.mkdtemp(prefix="gr-map-"))
    try:
        for name, text in (("map.js", _source(js)),
                           ("stub.js", _source(stub)),
                           ("toggle.js", _MAP_TOGGLE_JS)):
            (root / name).write_text(text, encoding="utf-8")
        r = _run(["node", "toggle.js"], cwd=root, capture_output=True, text=True, timeout=60)
        said = (r.stdout or "").strip().splitlines()
        assert r.returncode == 0 and said, (
            "map.js did not mount under node: " + ((r.stderr or r.stdout or "").strip()[-300:]))
        out = json.loads(said[-1])
    finally:
        shutil.rmtree(root, ignore_errors=True)

    want = [["names", "Town names"], ["numbers", "District numbers"], ["none", "No labels"]]
    assert out["labels"] == want, f"map.js's LABELS are {out['labels']}, not {want}"
    assert out["def"] == "names", f"the default is {out['def']!r}, not town names"

    def toggle(html):
        m = re.search(r'<div class="gmseg" role="radiogroup" aria-label="Labels on the map">'
                      r'(.*?)</div>', html, re.S)
        assert m, "mount() writes no radiogroup labelled \"Labels on the map\""
        radios = re.findall(r'<input type="radio" name="([^"]+)" value="([^"]+)"( checked)?>'
                            r'<span>([^<]+)</span>', m.group(1))
        assert len({n for n, _, _, _ in radios}) == 1, \
            "the label toggle's radio buttons do not share one name, so they are not one group"
        return [[v, w] for _, v, _, w in radios], [v for _, v, c, _ in radios if c]

    drawn, checked = toggle(out["plain"]["html"])
    assert drawn == want, f"the toggle draws {drawn}, not {want}"
    assert checked == ["names"], f"a plain mount checks {checked}, not town names alone"
    assert out["plain"]["labels"] == "names", f"a plain mount's mode is {out['plain']['labels']!r}"
    _, checked = toggle(out["numbers"]["html"])
    assert checked == ["numbers"] and out["numbers"]["labels"] == "numbers", (
        f"a mount asking for numbers checks {checked} and is in {out['numbers']['labels']!r}")
    assert out["bogus"] == "names", f"a mode that is not one of the three gives {out['bogus']!r}"
    assert (out["afterNone"], out["afterNumbers"], out["afterBogus"]) == ("none", "numbers", "numbers"), (
        "setLabels() went none, numbers, bogus -> "
        f"{out['afterNone']}, {out['afterNumbers']}, {out['afterBogus']}")
    return "ok", "Town names, District numbers, No labels: one radio group, town names chosen"


# map.js mounted in node on the map's data built from the tracked files, as
# _elect_map_panels mounts it: the legend and the line under it on State House
# with "Floterial districts" off, then on, then on State Senate.
_MAP_LEGEND_JS = r"""
require("./stub.js");
globalThis.CSS = { escape: s => String(s) };
document.createElementNS = (ns, t) => document.createElement(t);
const fs = require("fs");
const G = require("./map.js");
function held() {
  const e = document.createElement("div"), q = {};
  e.querySelector = sel => (q[sel] = q[sel] || held());
  e.style.setProperty = () => {};
  return e;
}
(async () => {
  const T = JSON.parse(fs.readFileSync("./data.json", "utf8"));
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => T });
  const root = held();
  const api = G.mount(root, { labels: "none", zoom: false, layers: ["base", "senate", "exec", "cong"] });
  await api.ready;
  const say = () => [root.querySelector(".gmleg").innerHTML, root.querySelector(".gmexplain").innerHTML];
  const out = { off: say() };
  root.querySelector(".gmfloin").checked = true; api.setLabels("none"); out.on = say();
  api.setLayer("senate"); out.senate = say();
  process.stdout.write("\n@@" + JSON.stringify(out));
})().catch(e => { console.error(String(e && e.stack || e)); process.exit(1); });
"""


@check("frontend", "the district map is its legend and no paragraph under it, but for what a "
                   "floterial district is while they are drawn, and its four kinds of district "
                   "are two by two on a phone")
def _map_legend_words():
    """The audit of 25 October 2026: on a phone the map began 470 to 540px
    below its heading, after a box of instructions, the controls, the legend
    and a 72-word paragraph under it -- what two colours mean, what a
    floterial district is, that a name shows when chosen, that colour is not
    population. The legend stays and the paragraph goes, but for its one
    sentence on floterial districts, said only while "Floterial districts"
    is ticked and the frames it explains are drawn.

    map.js mounted in node on the map's data built from the tracked files
    (_map_data): the legend names the parties with nothing under it; ticked,
    the legend's frame and the floterial sentence; on State Senate, nothing
    under the legend again. And map.css lays the four kinds of district out
    two by two below 600px, not three and one."""
    css = _source("src/pages/map.css")
    phone = re.search(r"@media \(max-width:37\.5em\)\{(.*?)\n\}", css, re.S)
    assert phone and re.search(r"\.gm \.gmseg:has\(> label:nth-child\(4\):last-child\)"
                               r"\{grid-template-columns:repeat\(2,1fr\)\}", phone.group(1)), (
        "map.css does not lay four kinds of district out two by two on a phone")
    if not shutil.which("node"):
        return "skip", "node is not installed (map.css read: four kinds two by two on a phone)"
    data = _map_data()
    if data is None:
        return "skip", "the geometry, the district files or the officials file is not here"
    root = Path(tempfile.mkdtemp(prefix="gr-maplegend-"))
    try:
        (root / "stub.js").write_text(_source("tests/dom_stub.js"),
                                      encoding="utf-8")
        (root / "map.js").write_text(_with_components(
            _source("src/pages/map.js")), encoding="utf-8")
        (root / "data.json").write_text(json.dumps(data), encoding="utf-8")
        (root / "go.js").write_text(_MAP_LEGEND_JS, encoding="utf-8")
        r = _run(["node", "go.js"], cwd=root, capture_output=True, text=True, encoding="utf-8",
                 timeout=120)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "map.js would not draw its legend in node: " + (r.stderr or r.stdout or "")[-300:])
        out = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    flo = ("A floterial district (neighboring districts that elect extra members together) is "
           "framed in its members&rsquo; party.")
    bad = []
    for when, (leg, under) in out.items():
        if 'class="sw p-R"' not in leg or 'class="sw p-D"' not in leg:
            bad.append(f"{when}: the legend does not name both parties")
        if under != (flo if when == "on" else ""):
            bad.append(f"{when}: under the legend is {under[:120]!r}")
    if "Floterial district, framed" not in out["on"][0] or "Floterial district, framed" in out["off"][0]:
        bad.append("the legend's floterial frame is not drawn only while they are")
    assert not bad, "; ".join(bad)
    return "ok", ("the legend alone on State House and State Senate; the floterial sentence and "
                  "frame only while ticked; four kinds two by two on a phone")


@check("frontend", "the district map's labels never overlap, in any of its three modes (the "
                   "label rule run in node on the real geometry)")
def _map_labels_never_overlap():
    """tests/test_map_labels.js loads map.js in node and lays out the labels of
    every layer in every mode -- Town names, District numbers, No labels --
    over the whole state and twelve places at four zooms each, in the map's
    box at 1366, 768 and 375 pixels wide, and in Town names with a town and
    its district chosen too: some three thousand layouts, on the map's data
    built here from the tracked files.

    Held: no two labels overlap (the chosen district's tag among them); no
    town name lies outside the view or under the zoom buttons; a mode draws
    only its own kind of label and No labels draws none. And what the design
    says each mode shows: the five Executive Council and two US House numbers
    at full view at every width; no State House number at full view, where
    they cannot all fit (the person, 8 October: only when "all numbers can be
    displayed without overlapping"); town names at full view; and Manchester's
    wards numbered, and named, within eight presses of +, so neither rule
    leaves the state's largest city unlabelled at every zoom.
    """
    if not shutil.which("node"):
        return "skip", "node is not installed"
    js, harness = Path("src/pages/map.js"), Path("tests/test_map_labels.js")
    if not (js.exists() and harness.exists()):
        return "skip", "map.js or tests/test_map_labels.js is not in this directory"
    data = _map_data()
    if data is None:
        return "skip", "the geometry, the district files or the officials file is not here"
    root = Path(tempfile.mkdtemp(prefix="gr-maplabels-"))
    try:
        (root / "district_map.json").write_text(json.dumps(data), encoding="utf-8")
        r = _run(["node", str(harness.resolve()), str(js.resolve()), str(root / "district_map.json")],
                 cwd=root, capture_output=True, text=True, timeout=240)
        said = (r.stdout or "").strip().splitlines()
        assert r.returncode == 0 and said, (
            "the label rule did not run: " + ((r.stderr or r.stdout or "").strip()[-300:]))
        out = json.loads(said[-1])
    finally:
        shutil.rmtree(root, ignore_errors=True)

    assert out["layouts"] >= 2000, f"only {out['layouts']} layouts were run"
    assert not out["overlaps"], "labels overlap:\n    " + "\n    ".join(out["overlaps"][:8])
    assert not out["outside"], "labels drawn off the view:\n    " + "\n    ".join(out["outside"][:8])
    assert not out["wrongKind"], "labels of the wrong kind:\n    " + "\n    ".join(out["wrongKind"][:8])
    full, bad = out["full"], []
    for w in ("660", "734", "341"):
        for layer, mode, ok, what in (
                ("exec", "numbers", lambda n: n == 5, "all five"),
                ("cong", "numbers", lambda n: n == 2, "both"),
                ("base", "numbers", lambda n: n == 0, "none"),
                ("base", "names", lambda n: n >= 8, "at least eight"),
                ("base", "none", lambda n: n == 0, "none")):
            n = full.get(f"{w} {layer} {mode}")
            if n is None or not ok(n):
                bad.append(f"{layer} in {mode} at full view in a {w}px box shows {n}, not {what}")
    for k, presses in out["manchester"].items():
        if presses is None:
            bad.append(f"Manchester's wards are never labelled ({k}) within eight presses")
    assert not bad, "\n  ".join(bad)
    return "ok", (f"{out['layouts']:,} layouts, none overlapping; Manchester's wards numbered "
                  f"after {out['manchester'].get('660 numbers')} presses and named after "
                  f"{out['manchester'].get('660 names')} at 1366")


@check("frontend", "the district map keeps the state's outline on every layer, through any number "
                   "of switches between State House and State Senate")
def _map_keeps_the_outline():
    """tests/test_map_outline.js loads map.js in node on the real geometry and
    switches layers fifty times in turn. The owner, 11 November 2026: the map
    outline disappeared on the switch from State House to State Senate -- the
    outline was the county lines, drawn on two layers only. Held: every layer
    gets the heavy line (casing and line) with a path, the same state edge on
    every layer but the two that draw the county lines, and none is lost on a
    later switch.
    """
    if not shutil.which("node"):
        return "skip", "node is not installed"
    js, harness = Path("src/pages/map.js"), Path("tests/test_map_outline.js")
    if not (js.exists() and harness.exists()):
        return "skip", "map.js or tests/test_map_outline.js is not in this directory"
    data = _map_data()
    if data is None:
        return "skip", "the geometry, the district files or the officials file is not here"
    root = Path(tempfile.mkdtemp(prefix="gr-mapoutline-"))
    try:
        (root / "district_map.json").write_text(json.dumps(data), encoding="utf-8")
        r = _run(["node", str(harness.resolve()), str(js.resolve()), str(root / "district_map.json")],
                 cwd=root, capture_output=True, text=True, timeout=120)
        said = (r.stdout or "").strip().splitlines()
        assert r.returncode == 0 and said, (
            "the outline check did not run: " + ((r.stderr or r.stdout or "").strip()[-300:]))
        out = json.loads(said[-1])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert out["switches"] >= 50 and len(out["layers"]) >= 2, "the check switched too few layers"
    assert not out["missing"], "a layer draws no state outline:\n    " + "\n    ".join(out["missing"][:8])
    assert not out["drifted"], "a layer's outline is not the state's:\n    " + "\n    ".join(out["drifted"][:8])
    return "ok", f"{len(out['layers'])} layers, {out['switches']} switches, the state's outline on each"


# map.js required in node on the map's data: every layer's heavy line (edgeLines: the white
# casing and the line over it) and every county's outline when it is chosen (outlineD), as
# the d each path is drawn with.
_MAP_COUNTY_LINES_JS = r"""
const G = require(process.argv[2]);
const T = JSON.parse(require("fs").readFileSync(process.argv[3], "utf8"));
const M = G.model(T), out = {layers: {}, counties: {}};
for (const [lk] of G.LAYERS) out.layers[lk] = G.edgeLines(M, lk);
for (const c of Object.keys(T.layers.county.f)) out.counties[c] = G.outlineD(M, "county", c);
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("frontend", "the district map's county line, its white casing and the state's edge are "
                   "drawn only where two counties meet or the state ends, and every county line "
                   "the geometry has is drawn")
def _map_county_line_where_counties_meet():
    """The owner, 16 November 2026: the district map "still has additional
    white lines where there shouldn't be" -- between Concord and Bow, both
    Merrimack. NH GRANIT's outlines of two neighbouring towns do not always
    meet, and a county is its towns dissolved, so the gap between them stayed
    in the county as a ring the county uses once, as it uses the state's
    edge; the county line and its white casing were drawn round four of them
    (Bow and Concord, Concord and Hopkinton, Franklin and Northfield,
    Claremont and Newport: 12 segments on every layer), as the county line
    on the State House and the towns and as the state's edge on the rest.
    build_district_map.lines_of leaves the rims of a gap between towns of
    one county out of the county line ("lines"), and map.js draws from it.

    Measured here against the committed geometry and nothing else. Its
    county lines: an arc two counties share; the state's own edge, which is
    the piece the arcs the counties use once make that spans the widest box,
    with any piece whose box lies outside that one (an island); and the rim
    of a gap between towns of two counties, a piece used by two counties,
    which runs along their county line. The rim of a gap between towns of
    one county, a piece one county alone uses, is none. Held, with map.js
    run in node on the map's data: every segment of the State House's and
    the towns' heavy line lies on a county line, every segment of every other
    layer's on the state's edge, and every segment of a county's outline when
    it is chosen on a county line of that county; and the State House's line
    draws every segment of the county lines and every other layer's every
    segment of the state's edge, so none is moved or lost. Skipped without
    node or the tracked files."""
    if not shutil.which("node"):
        return "skip", "node is not installed"
    js = Path("src/pages/map.js")
    data = _map_data()
    if data is None or not js.exists():
        return "skip", "map.js, the geometry, the district files or the officials file is not here"
    root = Path(tempfile.mkdtemp(prefix="gr-mapcounty-"))
    try:
        (root / "go.js").write_text(_MAP_COUNTY_LINES_JS, encoding="utf-8")
        (root / "district_map.json").write_text(json.dumps(data), encoding="utf-8")
        r = _run(["node", str(root / "go.js"), str(js.resolve()), str(root / "district_map.json")],
                 cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "map.js would not draw the county lines in node: " + (r.stderr or r.stdout or "")[-300:])
        drawn = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    geom = json.loads(_source("generated/district_geometry.json"))
    arcs = []
    for a in geom["arcs"]:
        p = [(a[0], a[1])]
        for i in range(2, len(a), 2):
            p.append((p[-1][0] + a[i], p[-1][1] + a[i + 1]))
        arcs.append(p)

    def users(lk):
        u = {}
        for fid, f in geom["layers"][lk]["f"].items():
            for ring in f["r"]:
                for r_ in ring:
                    u.setdefault(r_ if r_ >= 0 else ~r_, []).append(fid)
        return u
    cu, tu = users("county"), users("towns")
    once = [a for a in geom["layers"]["county"]["m"] if len(cu[a]) == 1]
    up = {}

    def top(q):
        while up.setdefault(q, q) != q:
            q = up[q]
        return q
    for a in once:
        up[top(arcs[a][0])] = top(arcs[a][-1])
    pieces = {}
    for a in once:
        pieces.setdefault(top(arcs[a][0]), []).append(a)

    def box(ids):
        pts = [q for a in ids for q in arcs[a]]
        return (min(x for x, _ in pts), min(y for _, y in pts), max(x for x, _ in pts), max(y for _, y in pts))
    edge = max(pieces.values(), key=lambda ids: (box(ids)[2] - box(ids)[0]) * (box(ids)[3] - box(ids)[1]))
    eb, state, rims, gaps = box(edge), set(edge), set(), []
    for ids in pieces.values():
        b = box(ids)
        if ids is edge:
            continue
        if not (eb[0] <= b[0] and eb[1] <= b[1] and b[2] <= eb[2] and b[3] <= eb[3]):
            state.update(ids)
        elif len({cu[a][0] for a in ids}) > 1:
            rims.update(ids)
        else:
            gaps.append(ids)
    lines = {a for a, cs in cu.items() if len(set(cs)) == 2} | state | rims

    def segs(ids):
        return {tuple(sorted((p, q))) for a in ids for p, q in zip(arcs[a], arcs[a][1:]) if p != q}

    def drawn_segs(d):
        out = set()
        for sub in d.split("M")[1:]:
            pts = [tuple(int(float(v)) for v in xy.split()) for xy in sub.split("L")]
            out |= {tuple(sorted((p, q))) for p, q in zip(pts, pts[1:]) if p != q}
        return out
    on_line, on_edge = segs(lines), segs(state)
    gap_of = {sg: ids for ids in gaps for sg in segs(ids)}
    strays, n = {}, 0
    for lk, heavy in drawn["layers"].items():
        for cls, d in heavy:
            got = drawn_segs(d)
            assert got, f"the {lk} layer's {cls} draws nothing"
            n += len(got)
            want = on_line if lk in ("base", "towns") else on_edge
            strays.update({(f"the {lk} layer's {cls}", sg): 1 for sg in got - want})
            lost = want - got
            assert not lost, (f"the {lk} layer's {cls} leaves out {len(lost)} segments of the "
                              f"{'county lines' if want is on_line else 'state' + chr(39) + 's edge'}, "
                              f"e.g. {sorted(lost)[:2]}")
    for c, d in drawn["counties"].items():
        got = drawn_segs(d)
        n += len(got)
        own = segs(a for a in lines if c in cu[a] and cu[a].count(c) == 1)
        strays.update({(f"{c} County's outline", sg): 1 for sg in got - own})
    if strays:
        said = {}
        for where, sg in strays:
            ids = gap_of.get(sg, [])
            towns = sorted({t for a in ids for t in tu.get(a, [])}) or ["no gap known"]
            k = f"{where}: inside {sorted({cu[a][0] for a in ids}) or '?'} ({' and '.join(towns)})"
            said[k] = said.get(k, 0) + 1
        raise AssertionError(f"{len(strays)} segments of the county line, its casing, the state's edge "
                             "or a county's outline lie on no county line: "
                             + "; ".join(f"{v} {k}" for k, v in list(said.items())[:6]))
    return "ok", (f"{n:,} drawn segments on {len(drawn['layers'])} layers and {len(drawn['counties'])} "
                  f"counties' outlines, each on a county line; the {len(on_line):,} segments of the "
                  f"county lines all drawn, and the {len(on_edge):,} of the state's edge; the rims of "
                  f"{len(gaps)} gaps between towns of one county drawn on none")


@check("data", "the district map's published file is the committed geometry, with every "
               "district filled from the roster's party")
def _map_published():
    """The night's site/district_map.json, read against what it was made from,
    each side read here rather than through build_district_map.py: its
    geometry the committed file's, byte for byte by digest and in its arcs and
    layers; every district's fill the letters of the parties of the members
    site/legislators.json seats there (a floterial's members by
    site/districts.json's floterial codes) or of the councillor or
    representative corrections/officials.json names; and map.js and map.css
    the copies of src/pages/'s.
    """
    pub, geo = Path("site/district_map.json"), Path("generated/district_geometry.json")
    legs, dist = Path("site/legislators.json"), Path("site/districts.json")
    if not all(p.exists() for p in (pub, geo, legs, dist)):
        return "skip", "site/district_map.json and what it is made from are not all here"
    import hashlib
    d = json.loads(pub.read_text(encoding="utf-8"))
    gb = geo.read_bytes()
    g = json.loads(gb)
    assert d["_geometry"] == hashlib.sha256(gb).hexdigest() and d["arcs"] == g["arcs"] \
        and d["layers"] == g["layers"], (
        "site/district_map.json was not built from generated/district_geometry.json as it stands")
    code = {"Belknap": "BE", "Carroll": "CA", "Cheshire": "CH", "Coos": "CO", "Grafton": "GR",
            "Hillsborough": "HI", "Merrimack": "ME", "Rockingham": "RO", "Strafford": "ST",
            "Sullivan": "SU"}
    flo = {f"{code[h['county']]}{h['district']}" for t in json.loads(dist.read_text(encoding="utf-8")).values()
           for w in t.values() for h in w["house"] if h["floterial"]}
    seen = {}
    roster = json.loads(legs.read_text(encoding="utf-8"))
    for m in roster if isinstance(roster, list) else roster.values():
        if m.get("chamber") == "H":
            c = f"{code[m['county']]}{int(m['district'])}"
            k = ("float", c) if c in flo else ("base", c)
        else:
            k = ("senate", str(int(m["district"])))
        seen.setdefault(k, set()).add(str(m.get("party") or "X")[:1].upper())
    off = _officials_now()
    for lk, office in (("exec", "council"), ("cong", "us_house")):
        for num, o in off[office]["districts"].items():
            if o.get("name"):
                seen[(lk, str(int(num)))] = {str(o.get("party") or "X")[:1].upper()}
    wrong = []
    for lk in ("base", "float", "senate", "exec", "cong"):
        for fid in g["layers"][lk]["f"]:
            ps = seen.get((lk, fid), set())
            want = "".join(x for x in "RDI" if x in ps) + "".join(sorted(ps - set("RDI")))
            if d["fill"][lk].get(fid) != want:
                wrong.append(f"{lk} {fid}: {d['fill'][lk].get(fid)!r}, the record {want!r}")
    assert not wrong, f"{len(wrong)} districts filled otherwise than the record: " + "; ".join(wrong[:6])
    # map.js without its comments, as every script is published (strip_js.py,
    # 23 October 2026); map.css as it is.
    import strip_js
    site_js, site_css = Path("site/map.js"), Path("site/map.css")
    assert site_js.exists() and site_js.read_bytes().decode("utf-8") == strip_js.published(
        "map.js", Path("src/pages/map.js").read_bytes().decode("utf-8")), \
        "site/map.js is not src/pages/map.js without its comments"
    assert site_css.exists() and site_css.read_bytes() == Path("src/pages/map.css").read_bytes(), \
        "site/map.css is not src/pages/map.css"
    vac = sum(1 for v in d["fill"]["base"].values() if not v)
    return "ok", (f"{sum(len(v) for v in d['fill'].values())} districts filled as the roster "
                  f"and officials.json have them; {vac} base districts with every seat vacant")


@check("frontend", "the bill search opens on the 2027 bill requests from the day after the election, and "
       "until the new term's bills are introduced in January, not when they are first published")
def _search_opens_on_requests_after_the_election():
    """The owner, 11 November 2026: /bills opens on the bill requests (meta.json's requests) from
    the day after the general election -- the Tuesday after the first Monday in November of the year
    before the requests' own -- and before it on the current term as always. The rule is app.js's
    requestsFirst, by Concord's day (nhDay). It ended when meta.json's newest term was the requests'
    own session, which is from Organization Day, as the first bills are numbered; the owner, 17
    November 2026: requests "do not become bills until the first session in January when they are
    introduced" -- so it holds through December, while the new term is published and none of the
    requests is introduced on a day of their own year (meta.requests.introduced_in_session), an
    Organization Day resolution of the December before not counting. An address that names a term
    still wins (wantedTerm), and the address a list writes leaves out the term it opens on
    (defaultTerm), so Back and a pasted link agree."""
    got = _app_js("""(() => {
  const R = {term: "2027-requests", label: "2027 Bill Requests", year: 2027, n: 302, withdrawn: 4};
  const M = (over = {}) => Object.assign({terms: ["2025-2026", "2023-2024"], requests: R}, over);
  const at = (iso, m = M()) => ({first: scope.requestsFirst(m, new Date(iso)),
                                 want: scope.wantedTerm(m, new Date(iso)),
                                 dflt: scope.defaultTerm(m, new Date(iso))});
  return {
    electionDays: [2026, 2027, 2028, 2030, 2032].map(y => scope.electionDayOf(y)),
    eve: at("2026-11-03T04:00:00Z"),            // 11 p.m. on 2 November in Concord
    day: at("2026-11-03T20:00:00Z"),            // election day itself
    after: at("2026-11-04T06:00:00Z"),          // 1 a.m. on the 4th in Concord
    june: at("2027-06-15T16:00:00Z"),
    published: at("2026-12-10T16:00:00Z", M({terms: ["2027-2028", "2025-2026"]})),
    organized: at("2026-12-10T16:00:00Z", M({terms: ["2027-2028", "2025-2026"],
      requests: Object.assign({}, R, {introduced: 3, introduced_in_session: 0})})),
    introduced: at("2027-01-08T16:00:00Z", M({terms: ["2027-2028", "2025-2026"],
      requests: Object.assign({}, R, {introduced: 300, introduced_in_session: 297})})),
    older: at("2029-01-08T16:00:00Z", M({terms: ["2029-2030", "2027-2028"]})),
    noneStand: at("2026-12-10T16:00:00Z", M({requests: Object.assign({}, R, {n: 4})})),
    noRequests: at("2026-12-10T16:00:00Z", {terms: ["2025-2026"]}),
  };
})()""", names=("requestsFirst", "wantedTerm", "defaultTerm", "electionDayOf", "nhDay"))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    assert got["electionDays"] == ["2026-11-03", "2027-11-02", "2028-11-07", "2030-11-05", "2032-11-02"], (
        f"the Tuesday after the first Monday in November is read as {got['electionDays']}")
    for k in ("eve", "day"):
        assert not got[k]["first"] and got[k]["want"] == got[k]["dflt"] == "2025-2026", (
            f"{k}: before the day after the election the search opens on {got[k]}")
    for k in ("after", "june"):
        assert got[k]["first"] and got[k]["want"] == got[k]["dflt"] == "2027-requests", (
            f"{k}: from the day after the election the search opens on {got[k]}")
    for k in ("published", "organized"):
        assert got[k]["first"] and got[k]["want"] == got[k]["dflt"] == "2027-requests", (
            f"{k}: with 2027-2028 published and no request introduced in 2027 the search opens on "
            f"{got[k]}")
    assert not got["introduced"]["first"] and got["introduced"]["want"] == "2027-2028", (
        f"once the requests' bills are introduced in January the search opens on the term: "
        f"{got['introduced']}")
    assert not got["older"]["first"] and got["older"]["want"] == "2029-2030", (
        f"requests of an older session than the newest term are never opened first: {got['older']}")
    assert got["noneStand"]["want"] == "2025-2026" and got["noRequests"]["want"] == "2025-2026", (
        f"with no request standing the search opens on the term: {got['noneStand']} {got['noRequests']}")
    return "ok", ("opens on the requests from 4 November 2026, not before; through December with "
                  "2027-2028 published and Organization Day's resolutions introduced; not once the "
                  "requests' bills are introduced in January")


@check("frontend", "a topic left on is dropped where the list has no topics, said in the count line, and "
       "any one filter can be removed on its own")
def _topic_dropped_on_the_requests():
    """The webinar, 11 November 2026: a topic chosen on a past term hid every 2027 bill request (they
    carry no topic yet), and only "clear all" removed it. dropEmptyTopics takes the filter off where
    the term's rows say no topic at all, topicNote says so after the count, and a topic (or committee)
    ticked where the list has none stays on offer in its group, at none, to be unticked on its own."""
    got = _app_js("""(() => {
  scope.setState("2025-2026", {terms: ["2025-2026"], requests: {term: "2027-requests", year: 2027, n: 2,
    withdrawn: 0, label: "2027 Bill Requests"}},
    [{id: "HB1", term: "2025-2026", topic: "Housing"}, {id: "HB2", term: "2025-2026", topic: "Taxes"},
     {id: "LSR 2027-0001", lsr: true, term: "2027-requests"}, {id: "LSR 2027-0002", lsr: true, term: "2027-requests"}]);
  const out = {};
  scope.sel.topic.add("Housing"); scope.sel.committee.add("Finance");
  scope.dropEmptyTopics();
  out.kept = [...scope.sel.topic]; out.keptNote = scope.topicNote();
  scope.setState("2027-requests");
  scope.dropEmptyTopics();
  out.dropped = [...scope.sel.topic]; out.note = scope.topicNote();
  out.committee = [...scope.sel.committee];
  scope.setState("2025-2026");
  out.back = scope.topicNote();
  // a topic ticked where none is offered (an old address) is listed, at none
  scope.setState("2027-requests");
  scope.sel.topic.add("Housing"); scope.sel.committee.add("Finance");
  scope.renderFacets();
  out.facets = document.querySelector("#facets").innerHTML;
  return out;
})()""", names=("dropEmptyTopics", "topicNote", "sel", "renderFacets",
                "setState: (t, m, rows) => { term = t; if (m) META = m; if (rows) IDX = rows; }"))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    assert got["kept"] == ["Housing"] and got["keptNote"] == "", (
        f"a topic is kept on a term whose bills have topics: {got['kept']} {got['keptNote']!r}")
    assert got["dropped"] == [] and "the topic filter was removed" in got["note"] \
        and "bill requests have no topics yet" in got["note"], (
        f"a topic is dropped where the list has none, and the count says so: {got['dropped']} {got['note']!r}")
    assert got["committee"] == ["Finance"], f"only the topic is dropped: {got['committee']}"
    assert got["back"] == "", f"the note stays with the list it was said of: {got['back']!r}"
    for what in ("Housing", "Finance"):
        assert re.search(r'data-f="[a-z]+"\s+value="%s" checked' % what, got["facets"]), (
            f"{what}, ticked where the list has none, is not offered to be unticked on its own")
    return "ok", "dropped on the requests, said in the count, and a stray topic or committee can be unticked"


@check("frontend", "the Topic filter has the Sponsor filter's search box: typing narrows the topic names (any case, "
       "anywhere in the name), counts stay right, a ticked topic stays listed")
def _topic_filter_search_box():
    """Stage 1 of the topics plan (12 November 2026). fgroup's searchable branch draws the Topic group's
    #tbox as it draws the Sponsor group's #sbox. Nothing typed lists every topic as before; "ealth" lists
    the two topics with it in the name, with their counts; a ticked topic stays in the list whatever is
    typed; a word no topic has says No match; the Sponsor box is still its own."""
    got = _app_js("""(() => {
  scope.setState("2025-2026", {terms: ["2025-2026"], committee_codes: {}, topics: ["Health", "Housing", "Mental Health", "Taxes"]},
    [{id: "HB1", term: "2025-2026", topic: "Health", sponsor: "A"}, {id: "HB2", term: "2025-2026", topic: "Health", sponsor: "A"},
     {id: "HB3", term: "2025-2026", topic: "Mental Health", sponsor: "B"}, {id: "HB4", term: "2025-2026", topic: "Housing", sponsor: "B"},
     {id: "HB5", term: "2025-2026", topic: "Taxes", sponsor: "B"}]);
  const out = {};
  const draw = () => { scope.renderFacets(); return document.querySelector("#facets").innerHTML; };
  out.all = draw();
  scope.setTopic("EALTH"); out.typed = draw();
  scope.sel.topic.add("Taxes"); out.ticked = draw();
  scope.sel.topic.clear();
  scope.setTopic("zzz"); out.none = draw();
  return out;
})()""", names=("renderFacets", "sel", "setState: (t, m, rows) => { term = t; if (m) META = m; if (rows) IDX = rows; }",
                "setTopic: (v) => { topicFilter = v; }"))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    topics = lambda h: re.findall(r'data-f="topic"\s+value="([^"]*)"', h)
    assert '<input class="sbox" id="tbox"' in got["all"] and 'id="sbox"' in got["all"], (
        "the Topic group has no search box beside the Sponsor group's")
    assert topics(got["all"]) == ["Health", "Housing", "Mental Health", "Taxes"], (
        f"with nothing typed the Topic list is whole: {topics(got['all'])}")
    assert topics(got["typed"]) == ["Health", "Mental Health"], (
        f"'EALTH' (any case, anywhere in the name) lists {topics(got['typed'])}")
    assert re.search(r'value="Health".*?<span class="c">2</span>', got["typed"], re.S), "a topic's count is lost while typing"
    assert topics(got["ticked"]) == ["Health", "Mental Health", "Taxes"], (
        f"a ticked topic leaves the list when it does not match: {topics(got['ticked'])}")
    assert topics(got["none"]) == [] and "No match" in got["none"], "a word no topic has is not said to match nothing"
    return "ok", "the box narrows the topics, counts hold, a ticked topic stays"


@check("frontend", "each filter's search box stays in view while its list scrolls: the box is its group's list's "
       "own child, sticky at the top of that scrolling box, solid, and the Sponsor list's chamber heads stick "
       "under it")
def _filter_boxes_stay_in_view():
    """The owner, 19 November 2026: scrolled down the Topics list, its box had scrolled away. A group's list
    scrolls inside its own box (.fbody: a max-height and overflow-y:auto), so app.css holds the box sticky at
    that box's top (.fbody > .sbox: position sticky, top 0, a background of its own and the gap under it painted
    over, so no option shows through), and the Sponsor list's House and Senate heads (.sphead) stick under it,
    at the box's height and gap, on a solid background. In node, the Topic, Tags and Sponsor groups, open, each
    draw their box as the first thing in their list's box (a sponsor's chosen pills apart), where the rule
    reaches it; a box wrapped in anything else would scroll away again."""
    css = _source(Path("src/pages/app.css"))
    body = re.search(r"\n\.fbody\{([^}]*)\}", css)
    assert body and "overflow-y:auto" in body[1] and "max-height" in body[1], (
        "a filter group's list (.fbody) no longer scrolls inside its own box; the sticky box would need the "
        "panel's scroll instead")
    rule = re.search(r"\n\.fbody > \.sbox\{([^}]*)\}", css)
    assert rule, "app.css has no rule holding a filter's box (.fbody > .sbox) in view"
    r = re.sub(r"\s+", "", rule[1])
    assert "position:sticky" in r and re.search(r"(^|;)top:0(;|$)", r), (
        f"the filter box is not sticky at the top of its list: {rule[1]!r}")
    assert re.search(r"background(-color)?:", r) and "box-shadow:0var(--sp-3)0var(--paper)" in r, (
        f"the sticky box lets the options show through it or through the gap under it: {rule[1]!r}")
    sbox = re.search(r"\n\.sbox\{([^}]*)\}", css)
    assert sbox and "height:32px" in sbox[1] and "margin-bottom:var(--sp-3)" in sbox[1], (
        "the box's height or gap moved: the Sponsor list's heads stick at 32px and --sp-3 below its top")
    head = re.search(r"\n\.sphead\{([^}]*)\}", css)
    h = re.sub(r"\s+", "", head[1]) if head else ""
    assert "position:sticky" in h and "top:calc(32px+var(--sp-3))" in h and "background:var(--paper)" in h, (
        f"the Sponsor list's chamber heads do not stick under the box on a solid ground: {h!r}")
    got = _app_js("(() => {" + _TAGS_HARNESS + """
  ROWS.forEach((b, i) => { b.sponsor = i % 2 ? "Ann Lee" : "Sam Senn";
    b.sponsor_label = i % 2 ? "Rep. Ann Lee (R - Rock 3)" : "Sen. Sam Senn (R - SD4)"; b.sponsor_party = "R"; });
  scope.setState("2025-2026", META_T, ROWS);
  scope.setTagWords(TAGS, WORDS);
  scope.setRoster("2025-2026", []);
  ["topic", "tag", "sponsor"].forEach(k => scope.openGroups.add(k));
  scope.sel.sponsor.add("Ann Lee");
  scope.renderFacets();
  const h = document.querySelector("#facets").innerHTML;
  const out = {};
  for (const k of ["topic", "tag", "sponsor"]) {
    const g = group(h, k) || "";
    const b = g.slice(g.indexOf('<div class="fbody'));
    out[k] = b.replace(/^<div class="fbody[^"]*"\\s*>/, "").replace(/^<div class="chosen">[\\s\\S]*?<\\/span><\\/div>/, "").slice(0, 60);
  }
  return out;
})()""", names=_TAGS_NAMES + ("setRoster: (t, m) => { SP_ROSTER[t] = m; }",))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    for k, box in (("topic", "tbox"), ("tag", "gbox"), ("sponsor", "sbox")):
        assert got[k].startswith(f'<input class="sbox" id="{box}"'), (
            f"the {k} group's box is not the first thing in its list's box, where the sticky rule holds it: "
            f"{got[k]!r}")
    return "ok", ("the box sticks at the top of each list's own scrolling box (Topic, Tags, Sponsor), solid with its "
                  "gap painted; the Sponsor list's chamber heads stick under it")


# THE SPONSOR PICKER'S HARNESS (the owner, 19 November 2026): six members of 2025-2026 as
# site/sponsors/<term>.json gives them (sponsor_roster.py), one of them gone, two with no bill, and four
# bills naming them as prime sponsor and co-sponsor; and a bill of 2023-2024 by somebody else.
_PICKER_HARNESS = r"""
  const META_P = {terms: ["2025-2026", "2023-2024"], committee_codes: {}, topics: []};
  const ROSTER = [
    {k: "Joe Gone", l: "Rep. Joe Gone (D - Belk 6)", c: "H", p: "D", o: "gone, joe", t: ["Gilford"], f: 1},
    {k: "Ann Lee", l: "Rep. Ann Lee (R - Rock 3)", c: "H", p: "R", o: "lee, ann", t: ["Rye"]},
    {k: "Nancy Murphy", l: "Rep. Nancy Murphy (D - Hills 12)", c: "H", p: "D", o: "murphy, nancy", t: ["Bedford"]},
    {k: "Zed Quiet", l: "Rep. Zed Quiet (R - Belk 6)", c: "H", p: "R", o: "quiet, zed", t: ["Gilford"]},
    {k: "Amy Able", l: "Sen. Amy Able (D - SD9)", c: "S", p: "D", o: "able, amy", t: ["Keene"]},
    {k: "Sam Senn", l: "Sen. Sam Senn (R - SD4)", c: "S", p: "R", o: "senn, sam", t: ["Dover"]}];
  const bill = (id, sp, lab, party, cosp, term) => ({id, n: id.replace(/^HB/, "HB "), year: +(term || "2025").slice(0, 4),
    term: term || "2025-2026", title: "a bill", sponsor: sp, sponsor_label: lab, sponsor_party: party,
    sponsor_slug: sp.toLowerCase().replace(/ /g, "-"), cosp, topic: "", committee: "", committees: [], votedays: [],
    status: "Killed", chip: "Died", kind: "done", last_action: "", nrc: 0, hayT: id.toLowerCase(), hayC: ""});
  const ROWS_P = [
    bill("HB1", "Nancy Murphy", "Rep. Nancy Murphy (D - Hills 12)", "D", ["Ann Lee", "Sam Senn"]),
    bill("HB2", "Nancy Murphy", "Rep. Nancy Murphy (D - Hills 12)", "D", ["Joe Gone"]),
    bill("HB3", "Joe Gone", "Rep. Joe Gone (D - Belk 6)", "D", ["Nancy Murphy"]),
    bill("HB4", "Sam Senn", "Sen. Sam Senn (R - SD4)", "R", ["Ann Lee"]),
    bill("HB9", "Old Hand", "Rep. Old Hand (R - Coos 1)", "R", [], "2023-2024")];
  const rows = h => [...h.matchAll(/<label class="fopt sprow([^"]*)"><input type="checkbox" data-f="sponsor"\s+value="([^"]*)"[^>]*>\s*<span class="spn">([\s\S]*?)<\/span>\s*<span class="c"([^>]*)>([\d,]+)<\/span>/g)]
    .map(m => ({k: m[2], cls: m[1], text: m[3].replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim(), title: m[4], n: +m[5].replace(/,/g, ""), html: m[0]}));
  const heads = h => [...h.matchAll(/<div class="sphead" data-ch="([^"]*)">/g)].map(m => m[1]);
"""
_PICKER_NAMES = ("renderFacets", "sel", "matches", "openGroups", "IDX: () => IDX", "ALLT: ALL_TERMS",
                 "setState: (t, m, rows) => { term = t; if (m) META = m; if (rows) IDX = rows; "
                 "for (const k in SP_LABELS) delete SP_LABELS[k]; for (const t2 of (m || META).terms) noteSponsors(t2, IDX.filter(b => b.term === t2)); }",
                 "setBox: (v) => { sponsorFilter = v; }", "setCosp: (v) => { withCosp = v; }",
                 "setRoster: (t, m) => { SP_ROSTER[t] = m; }", "setTerm: (t) => { term = t; }")


@check("frontend", "the Sponsor filter lists the term's members as their chips, House then Senate, each once by "
       "surname, with their bill counts equal to what ticking them lists, prime or with co-sponsorships; a member "
       "who left is named Former in their place; typing narrows by name, town or district")
def _sponsor_picker_lists_the_term():
    """The owner, 19 November 2026: "a dropdown list of the sitting term's State Representatives and Senators
    that you can scroll and type into", each row "the member's chip ... with their bill count beside it". On the
    harness's six members and four bills, the Sponsor group open in 2025-2026 with nothing typed lists all six
    once, under a House head and then a Senate head (roster-listings-separate-the-chambers), each chamber by
    surname with the members at none after the rest under the rule, greyed; each row is the member's chip
    (.mchip in their party's colour) and the count is exactly the bills the filter then lists for them alone,
    prime sponsorships by default and with "Include co-sponsored bills" ticked prime and co-sponsored together,
    each part on the count's hover. Joe Gone, who left, is "Former Rep. Joe Gone" in his place among the House,
    with no mark of any other kind and no group of his own (treat-former-members-the-same). Typing narrows the
    list by a part of a name, a town of the district or the district; a ticked member stays listed whatever is
    typed. All Terms lists nobody until a name is typed. A term with no file lists the people its bills name, a
    co-sponsor the bills give no chamber under a head of their own, never in a chamber."""
    got = _app_js("(() => {" + _PICKER_HARNESS + """
  const out = {};
  scope.setState("2025-2026", META_P, ROWS_P);
  scope.setRoster("2025-2026", ROSTER);
  scope.openGroups.add("sponsor");
  const draw = () => { scope.renderFacets(); return document.querySelector("#facets").innerHTML; };
  const listed = k => { scope.sel.sponsor.clear(); scope.sel.sponsor.add(k);
    const n = scope.IDX().filter(b => scope.matches(b)).length; scope.sel.sponsor.clear(); return n; };
  for (const cosp of [false, true]) {
    scope.setCosp(cosp);
    const h = draw(), rs = rows(h);
    out[cosp ? "cosp" : "prime"] = {heads: heads(h), rows: rs.map(r => [r.k, r.n, r.cls.trim(), r.title]),
      filtered: Object.fromEntries(rs.map(r => [r.k, listed(r.k)])),
      gone: (rs.find(r => r.k === "Joe Gone") || {}).html || "", texts: rs.map(r => r.text),
      chips: rs.map(r => (/<span class="mchip p-([A-Z])"/.exec(r.html) || [])[1] || "")};
  }
  scope.setCosp(false);
  for (const [k, v] of [["town", "bedf"], ["district", "belk 6"], ["senate", "sd9"], ["name", "SENN"]]) {
    scope.setBox(v); out[k] = rows(draw()).map(r => r.k); }
  scope.sel.sponsor.add("Nancy Murphy"); scope.setBox("senn"); out.ticked = rows(draw()).map(r => r.k);
  scope.sel.sponsor.clear(); scope.setBox("");
  scope.setTerm(scope.ALLT); const all = draw(); out.allTerms = [rows(all).length, heads(all).length];
  scope.setBox("murphy"); out.allTyped = ([...draw().matchAll(/data-f="sponsor"\\s+value="([^"]*)"/g)].map(m => m[1]));
  scope.setBox("");
  scope.setState("2025-2026", META_P, ROWS_P);
  scope.setRoster("2025-2026", []);
  const fb = draw(); out.fallback = {heads: heads(fb), rows: rows(fb).map(r => [r.k, r.text])};
  return out;
})()""", names=_PICKER_NAMES)
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    p, c = got["prime"], got["cosp"]
    keys = [r[0] for r in p["rows"]]
    assert sorted(keys) == sorted(["Joe Gone", "Ann Lee", "Nancy Murphy", "Zed Quiet", "Amy Able", "Sam Senn"]) \
        and len(keys) == len(set(keys)), f"the picker does not list every member of the term once: {keys}"
    assert p["heads"] == ["H", "S"], f"the chambers are not the House and then the Senate: {p['heads']}"
    assert keys == ["Joe Gone", "Nancy Murphy", "Ann Lee", "Zed Quiet", "Sam Senn", "Amy Able"], (
        f"not each chamber by surname, those with prime bills first and those at none after: {keys}")
    assert [r[2] for r in p["rows"]] == ["", "", "off fzero", "off", "", "off fzero"], (
        f"the members at none are not greyed after a rule: {[r[2] for r in p['rows']]}")
    assert p["chips"] == ["D", "D", "R", "R", "R", "D"], f"a row is not the member's chip in their party: {p['chips']}"
    for mode in (p, c):
        bad = [(k, n, mode["filtered"][k]) for k, n, _, _ in mode["rows"] if n != mode["filtered"][k]]
        assert not bad, f"a count is not the bills the filter then lists (member, count, listed): {bad}"
    assert dict((r[0], r[1]) for r in p["rows"]) == {"Joe Gone": 1, "Nancy Murphy": 2, "Ann Lee": 0, "Zed Quiet": 0,
                                                      "Sam Senn": 1, "Amy Able": 0}, p["rows"]
    assert dict((r[0], r[1]) for r in c["rows"]) == {"Joe Gone": 2, "Nancy Murphy": 3, "Ann Lee": 2, "Zed Quiet": 0,
                                                      "Sam Senn": 2, "Amy Able": 0}, c["rows"]
    assert [r[0] for r in c["rows"]] == ["Joe Gone", "Ann Lee", "Nancy Murphy", "Zed Quiet", "Sam Senn", "Amy Able"], (
        f"with co-sponsorships the order does not follow their counts: {[r[0] for r in c['rows']]}")
    tip = dict((r[0], r[3]) for r in c["rows"])
    assert 'title="2 prime, 1 co-sponsored"' in tip["Nancy Murphy"] and not any(r[3] for r in p["rows"]), (
        f"the parts of a count are not on its hover with co-sponsorships, or are without: {tip['Nancy Murphy']!r}")
    assert p["texts"][0] == "Former Rep. Joe Gone (D - Belk 6)" and p["texts"][1] == "Rep. Nancy Murphy (D - Hills 12)", (
        f"a member who left is not named Former, in his place: {p['texts'][:2]}")
    gone = re.sub(r">[^<]*<", "><", p["gone"]).lower()
    assert "former" not in gone and "badge" not in gone and "left" not in gone, (
        f"a member who left carries a mark beyond his name: {p['gone']}")
    assert got["town"] == ["Nancy Murphy"] and got["district"] == ["Joe Gone", "Zed Quiet"] \
        and got["senate"] == ["Amy Able"] and got["name"] == ["Sam Senn"], (
        f"typing a town, a district or a name: {got['town']}, {got['district']}, {got['senate']}, {got['name']}")
    assert got["ticked"] == ["Nancy Murphy", "Sam Senn"], f"a ticked member leaves the list when typing: {got['ticked']}"
    assert got["allTerms"] == [0, 0] and got["allTyped"] == ["Nancy Murphy"], (
        f"All Terms lists members with nothing typed, or not the one typed: {got['allTerms']}, {got['allTyped']}")
    fb = got["fallback"]
    assert fb["heads"] == ["H", "S", "X"] and [k for k, _ in fb["rows"]] == [
        "Joe Gone", "Nancy Murphy", "Sam Senn", "Ann Lee"], (
        f"with no file, the people the bills name, a co-sponsor of no known chamber under a head of their own: {fb}")
    return "ok", ("six members once each, House then Senate by surname, zeros greyed after a rule; counts equal the "
                  "filter's lists, prime 2/1/1 and with co-sponsorships 3/2/2/2; Former Rep. Joe Gone in his place; "
                  "a town, a district, a name narrow it; All Terms waits for a name; no file lists the bills' people")


@check("frontend", "every filter in use is a pill above the results with an × that takes that one off, and Clear all "
       "for two or more; one kept into a term it matches nothing in is kept and muted; where filters that each "
       "list something list nothing together, the ones in the way are marked")
def _filters_in_use_bar():
    """The owner, 19 November 2026: "selected filters should be easily viewable and should have an x mark next to
    them to deselect them ... more centralized for all filters". On the picker's harness: nothing ticked draws no
    bar; a bill type, a sponsor and "Include co-sponsored bills" ticked draw three pills, each saying which filter
    it is and what, each with a button "Remove filter: ..." keyed to it, then Clear all; one filter, no Clear all.
    The term changed to one the sponsor filed nothing in keeps the filter ticked and draws its pill muted (none),
    titled, with the line saying a dashed filter matches nothing in the term. Two filters that each list bills
    and together none (a Democrat's party and a Republican sponsor) are each outlined (fblock) with how many the
    list would hold without it. A pill's × takes that filter off and the bar is drawn again; Clear all takes
    them all. With FBAR_PLACE "facets" the bar heads the panel instead. app.css wraps the pills, and a long one
    wraps inside itself, so a phone never scrolls sideways."""
    css = _source(Path("src/pages/app.css"))
    bar = re.search(r"\n\.fbar\{([^}]*)\}", css)
    pill = re.search(r"\n\.fpill\{([^}]*)\}", css)
    assert bar and "flex-wrap:wrap" in bar[1] and pill and "max-width:100%" in pill[1] \
        and "overflow-wrap:anywhere" in pill[1], "the filters' pills do not wrap, or a long one can push the page sideways"
    assert re.search(r"\n\.fpill\.none\{[^}]*dashed", css), "a filter matching nothing in the term is not drawn dashed"
    got = _app_js("(() => {" + _PICKER_HARNESS + """
  const out = {};
  const bar = () => document.getElementById("fbar");
  const pills = h => [...h.matchAll(/<span class="pill fpill([^"]*)"(?: title="([^"]*)")?><span class="fv">([\\s\\S]*?)<\\/span>(?:<span class="sr">[^<]*<\\/span>)?<button type="button" class="fx" data-unfilter="([^"]*)" data-v="([^"]*)" aria-label="([^"]*)">/g)]
    .map(m => ({cls: m[1].trim(), title: m[2] || "", text: m[3].replace(/<[^>]+>/g, ""), k: m[4], v: m[5], aria: m[6]}));
  scope.setState("2025-2026", META_P, ROWS_P);
  scope.setRoster("2025-2026", ROSTER);
  scope.render(); out.empty = [bar().innerHTML, bar().hidden];
  scope.sel.type.add("HB"); scope.sel.sponsor.add("Nancy Murphy"); scope.setCosp(true);
  scope.render(); const h = bar().innerHTML;
  out.three = pills(h); out.clear = /data-fclear="1">Clear all</.test(h); out.hidden = bar().hidden;
  scope.unfilter("type", "HB", false); out.afterX = [[...scope.sel.type], pills(bar().innerHTML).map(p => p.k)];
  scope.unfilter("cosp", "1", false); out.one = [pills(bar().innerHTML).map(p => p.k), /Clear all/.test(bar().innerHTML)];
  scope.setTerm("2023-2024"); scope.render(); const t = bar().innerHTML;
  out.term = [pills(t), [...scope.sel.sponsor], /A dashed filter matches no bills in the 2023.2024 term/.test(t)];
  scope.setTerm("2025-2026"); scope.sel.sponsor.clear(); scope.sel.sponsor.add("Sam Senn"); scope.sel.party.add("Democrat");
  scope.render(); const o = bar().innerHTML;
  out.stuck = [pills(o), scope.IDX().filter(b => scope.matches(b)).length, /No bill matches all of these together/.test(o)];
  scope.clearFilters(false); out.cleared = [Object.values(scope.sel).reduce((n, s) => n + s.size, 0), bar().hidden];
  scope.sel.sponsor.add("Nancy Murphy"); scope.setPlace("facets"); scope.render(); scope.renderFacets();
  out.panel = [document.querySelector("#facets").innerHTML.slice(0, 40), bar().hidden];
  return out;
})()""", names=_PICKER_NAMES + ("render", "unfilter", "clearFilters", "setPlace: (p) => { FBAR_PLACE = p; }"))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    assert got["empty"] == ["", True], f"a bar is drawn with nothing ticked: {got['empty']}"
    three = got["three"]
    assert [(p["k"], p["v"], p["text"]) for p in three] == [
        ("type", "HB", "Bill type: House Bill"), ("sponsor", "Nancy Murphy", "Sponsor: Nancy Murphy (D - Hills 12)"),
        ("cosp", "1", "Co-sponsored bills included")] and not got["hidden"], f"the pills drawn: {three}"
    assert [p["aria"] for p in three] == ["Remove filter: Bill type: House Bill",
                                          "Remove filter: Sponsor: Nancy Murphy (D - Hills 12)",
                                          "Remove filter: Co-sponsored bills included"], [p["aria"] for p in three]
    assert got["clear"] and got["one"] == [["sponsor"], False], (
        f"Clear all is not there for three, or is there for one: {got['clear']}, {got['one']}")
    assert got["afterX"] == [[], ["sponsor", "cosp"]], f"a pill's × does not take its filter off alone: {got['afterX']}"
    pills, kept, said = got["term"]
    assert kept == ["Nancy Murphy"] and len(pills) == 1 and pills[0]["cls"] == "none" \
        and pills[0]["title"] == "Matches no bills in the 2023–2024 term" and said, (
        f"a sponsor kept into a term she filed nothing in: kept {kept}, pill {pills}, said {said}")
    pills, n, said = got["stuck"]
    assert n == 0 and said and sorted((p["k"], p["cls"], p["title"]) for p in pills) == [
        ("party", "fblock", "Without this, 1 bill matches"), ("sponsor", "fblock", "Without this, 3 bills match")], (
        f"two filters that list nothing together: {pills}, {n} listed, said {said}")
    assert got["cleared"] == [0, True], f"Clear all leaves filters or the bar: {got['cleared']}"
    assert got["panel"][0].startswith('<div class="fbar"') and got["panel"][1], (
        f"FBAR_PLACE 'facets' does not put the bar at the panel's top instead: {got['panel']}")
    return "ok", ("no bar with nothing ticked; three pills with their own × and Clear all, one without; a sponsor kept "
                  "into 2023-2024 muted and said; Democrat with a Republican sponsor both outlined (1 and 3 without); "
                  "Clear all clears; the panel's top on 'facets'")



# THE TAGS' HARNESS: four tags, five bills and the words that lead to them, as meta.json and the index rows
# carry them (tag_rules.site_meta, build_site_v2.site_tagging), for the checks of the tags on the pages.
_TAGS_HARNESS = r"""
  const TAGS = [{id: "office-attorney-general", name: "Attorney General", group: "Offices",
                 definition: "Bills whose text gives the Attorney General a duty or a power."},
                {id: "artificial-intelligence", name: "Artificial intelligence and data centers", group: "Technology",
                 definition: "Bills about artificial intelligence."},
                {id: "mental-health", name: "Mental health", group: "Health", definition: "Bills about mental health."},
                {id: "excavation-tax", name: "Excavation tax", group: "Taxes", definition: "Bills about the excavation tax."}];
  const WORDS = {"attorney general": "tag:office-attorney-general", "ai": "tag:artificial-intelligence",
                 "deepfake": "tag:artificial-intelligence", "mental health": "tag:mental-health",
                 "gravel tax": "tag:excavation-tax", "excavation tax": "tag:excavation-tax", "earthwork": "tag:excavation-tax",
                 "weed": "topic:Cannabis", "pot": "topic:Cannabis"};
  const META_T = {terms: ["2025-2026"], committee_codes: {}, topics: ["Cannabis", "Crimes", "Health"],
                  tags: TAGS, tag_words: WORDS};
  const norm = s => String(s || "").toLowerCase().replace(/-/g, " ");
  const ROWS = [
    {id: "HB1", n: "HB 1", year: 2025, term: "2025-2026", title: "relative to the consumer protection bureau",
     topic: "Crimes", tags: [0], committee: "House Judiciary"},
    {id: "HB2", n: "HB 2", year: 2025, term: "2025-2026", title: "relative to hemp products", topic: "Cannabis",
     committee: "House Commerce"},
    {id: "HB3", n: "HB 3", year: 2025, term: "2025-2026", title: "regulating chatbots", topic: "Crimes",
     tags: [1, 0, 2], committee: "House Commerce"},
    {id: "HB4", n: "HB 4", year: 2025, term: "2025-2026", title: "relative to the attorney general",
     topic: "Crimes", committee: "House Judiciary"},
    {id: "HB5", n: "HB 5", year: 2025, term: "2025-2026", title: "relative to removal of earth", topic: "Health",
     tags: [3], committee: "House Ways and Means"},
    {id: "HB6", n: "HB 6", year: 2025, term: "2025-2026", title: "relative to earthworkmanship standards",
     topic: "Health", committee: "House Commerce"}];
  ROWS.forEach(b => { b.hayT = norm([b.id, b.n, b.title].join(" ")); b.hayC = norm(b.committee); });
  const group = (h, k) => { const i = h.indexOf('data-g="' + k + '"'); if (i < 0) return null;
    const j = h.indexOf('<div class="fgroup', i); return h.slice(i, j < 0 ? undefined : j); };
  const opts = (h, k) => [...String(h || "").matchAll(new RegExp('data-f="' + k + '"\\s+value="([^"]*)"', "g"))].map(m => m[1]);
"""
_TAGS_NAMES = ("renderFacets", "sel", "matches", "cardHtml", "renderRelated", "setTagWords", "filtersFromAddress",
               "addressList", "openGroups",
               "setState: (t, m, rows) => { term = t; if (m) META = m; if (rows) IDX = rows; }",
               "setTopic: (v) => { topicFilter = v; }", "setG: (v) => { tagFilter = v; }",
               "setQ: (q) => { query = q; }", "setPlace: (p) => { TAGS_PLACE = p; }",
               "setFocused: (f) => { focused = f; }")


@check("frontend", "a bill's tags are searches on its own page alone -- at its foot, or at the end of its History "
                   "tab, as TAGS_PLACE says -- and the Tags filter lists them with a box that finds one by its "
                   "words; no card, list or head shows a tag")
def _tags_on_the_bill_page_and_filter():
    """The owner, 17 November 2026: "I don't want tags to be distracting to the layout as additional visual clutter
    and more of a helpful search tool, so maybe they could be listed at the bottom of a page or in a certain section
    tab like history". On the harness's tags (as meta.json carries them): the bill's own page ends with "Related
    searches", each tag by the registry's name to /bills on All Terms with it ticked and its definition on the
    hover, and nothing else said of it; with TAGS_PLACE "history" the History tab ends with them instead, on the
    bill's own page and not on a card opened in a list; a list card, the head and an untagged bill show none. The
    Tags group follows Topic, closed, every carried tag by name with its count; its box finds a tag by name or by
    a word that leads to it (an ask it never shows); a ticked tag stays listed and is counted on the group's badge;
    the Topic box finds a topic by a word that leads to it ("weed", Cannabis). Two tags are either, a tag and a topic
    both. ?tag= ticks a tag meta.json has and opens the group, and the list writes it back. With no tags in meta.json
    none of this draws anything."""
    got = _app_js("(() => {" + _TAGS_HARNESS + """
  scope.setState("2025-2026", META_T, ROWS);
  scope.setTagWords(TAGS, WORDS);
  const out = {};
  const facets = () => { scope.renderFacets(); return document.querySelector("#facets").innerHTML; };
  const all = facets();
  out.order = [...all.matchAll(/data-g="(\\w+)"/g)].map(m => m[1]);
  out.tags = opts(group(all, "tag"), "tag");
  out.closed = /data-g="tag"\\s+aria-expanded="false"/.test(all) && /<div class="fbody" hidden><input class="sbox" id="gbox"/.test(group(all, "tag"));
  out.counts = [...group(all, "tag").matchAll(/value="([^"]*)" ><span title="([^"]*)">([^<]*)<\\/span>\\s*<span class="c">(\\d+)/g)].map(m => m.slice(1));
  scope.setG("INTELL"); out.byName = opts(group(facets(), "tag"), "tag");
  scope.setG("deepf"); const ask = group(facets(), "tag"); out.byAsk = opts(ask, "tag"); out.askShown = /deepf/.test(ask.replace(/value="deepf"/, ""));
  scope.setG("zzz"); out.none = group(facets(), "tag").includes("No match");
  scope.sel.tag.add("excavation-tax"); scope.setG("intell"); const tk = group(facets(), "tag");
  out.ticked = opts(tk, "tag"); out.badge = (tk.match(/<span class="badge">(\\d+)<\\/span>/) || [])[1] || "";
  scope.setG(""); scope.sel.tag.clear();
  scope.setTopic("weed"); out.topicWeed = opts(group(facets(), "topic"), "topic"); scope.setTopic("");
  const ids = () => ROWS.filter(b => scope.matches(b)).map(b => b.id);
  scope.sel.tag.add("office-attorney-general"); out.oneTag = ids();
  scope.sel.tag.add("excavation-tax"); out.twoTags = ids();
  scope.sel.topic.add("Health"); out.tagAndTopic = ids();
  scope.sel.tag.clear(); scope.sel.topic.clear();
  scope.filtersFromAddress(new URLSearchParams("tag=mental-health&tag=no-such-tag"));
  out.address = [...scope.sel.tag]; out.opened = scope.openGroups.has("tag");
  let wrote = ""; history.replaceState = (s, t, u) => { wrote = String(u); };
  scope.addressList(); out.written = wrote;
  scope.sel.tag.clear();
  const rec = {term: "2025-2026", tags: [{id: "artificial-intelligence", name: "x", why: "T:chatbot"}]};
  scope.setFocused("HB3");
  out.foot = scope.cardHtml(ROWS[2], true);
  out.footNone = scope.cardHtml(ROWS[3], true);
  out.card = scope.cardHtml(ROWS[2], false);
  scope.setPlace("history");
  out.histPage = scope.renderRelated(ROWS[2], [], rec);
  out.histFoot = scope.cardHtml(ROWS[2], true);
  scope.setFocused(null);
  out.histCard = scope.renderRelated(ROWS[2], [], rec);
  scope.setPlace("foot");
  scope.setTagWords([], {});
  out.offFacets = facets();
  scope.setFocused("HB3");
  out.offFoot = scope.cardHtml(ROWS[2], true);
  return out;
})()""", names=_TAGS_NAMES)
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    ti = got["order"].index("topic") if "topic" in got["order"] else -1
    assert ti >= 0 and got["order"][ti + 1:ti + 2] == ["tag"], f"the Tags group does not follow Topic: {got['order']}"
    assert got["closed"], "the Tags group is not closed, with its box first, until it is opened"
    assert got["tags"] == ["artificial-intelligence", "office-attorney-general", "excavation-tax", "mental-health"], (
        f"the Tags group's options, by name: {got['tags']}")
    want = {"office-attorney-general": "2", "artificial-intelligence": "1", "mental-health": "1", "excavation-tax": "1"}
    for tid, title, name, n in got["counts"]:
        reg = {"office-attorney-general": "Attorney General", "artificial-intelligence": "Artificial intelligence and data centers",
               "mental-health": "Mental health", "excavation-tax": "Excavation tax"}
        assert name == reg[tid] and title.startswith("Bills ") and n == want[tid], (
            f"{tid} is drawn as {name!r} ({title!r}, {n}): the registry's name, its definition and its count")
    assert got["byName"] == ["artificial-intelligence"], f"'INTELL' in the box lists {got['byName']}"
    assert got["byAsk"] == ["artificial-intelligence"] and not got["askShown"], (
        f"a word that leads to a tag lists it, and is never shown: {got['byAsk']}, shown {got['askShown']}")
    assert got["none"], "a word that is no tag's does not say No match"
    assert "excavation-tax" in got["ticked"] and got["badge"] == "1", (
        f"a ticked tag leaves the list, or the badge does not count it: {got['ticked']}, badge {got['badge']!r}")
    assert got["topicWeed"] == ["Cannabis"], f"'weed' in the Topic box lists {got['topicWeed']}"
    assert got["oneTag"] == ["HB1", "HB3"] and got["twoTags"] == ["HB1", "HB3", "HB5"] and got["tagAndTopic"] == ["HB5"], (
        f"one tag {got['oneTag']}, two {got['twoTags']}, a tag and a topic {got['tagAndTopic']}")
    assert got["address"] == ["mental-health"] and got["opened"], f"?tag= ticks {got['address']}, opens {got['opened']}"
    assert "tag=mental-health" in got["written"], f"the list's address leaves the tag out: {got['written']!r}"
    foot = re.search(r'<section class="tagfoot" aria-label="Related searches"><h2 class="tagfh">Related searches</h2>'
                     r'<ul class="taglinks">(.*?)</ul></section></article>$', got["foot"])
    assert foot, "the bill's own page does not end with its tags as searches"
    links = re.findall(r'<li><a href="([^"]*)" title="([^"]*)">([^<]*)</a></li>', foot.group(1))
    assert [(h, n) for h, _t, n in links] == [
        ("/bills?term=all&amp;tag=artificial-intelligence", "Artificial intelligence and data centers"),
        ("/bills?term=all&amp;tag=office-attorney-general", "Attorney General"),
        ("/bills?term=all&amp;tag=mental-health", "Mental health")], f"the searches: {links}"
    assert re.sub(r'<li><a href="[^"]*" title="[^"]*">[^<]*</a></li>', "", foot.group(1)) == "", (
        "the list says something of a tag beyond its name and its definition")
    assert all(t.startswith("Bills ") for _h, t, _n in links), "a link's hover is not the registry's definition"
    for what in ("footNone", "card"):
        assert "tagfoot" not in got[what] and "Attorney General" not in got[what], f"{what} shows a tag"
    assert "T:chatbot" not in got["histPage"], "the page prints the evidence that attached a tag"
    assert got["histPage"].endswith('<section class="rl-g tagsec"><h2 class="sech">Related Searches</h2><ul class="taglinks">'
                                    + foot.group(1) + "</ul></section>"), "History does not end with the searches"
    assert "tagfoot" not in got["histFoot"] and "tagsec" not in got["histCard"], (
        "with TAGS_PLACE history the foot still lists them, or a list's card does")
    assert 'data-g="tag"' not in got["offFacets"] and "tagfoot" not in got["offFoot"], (
        "with no tags in meta.json the filter or the page draws something")
    return "ok", ("the bill's own page ends with its 3 searches (or History does), name and definition only; no "
                  "card, head or untagged bill shows one; the Tags group by name with counts, found by a word it "
                  "never shows, a ticked tag kept and badged; weed finds Cannabis; ?tag= read and written")


@check("frontend", "a tag's words find its bills, built in and never shown: the whole search or one word of it that "
                   "a tag's name, ask or synonym leads to lists that tag's bills (or a topic's) below the bills "
                   "whose titles say it; the offers name the tag; the header search's matcher does the same",
       needs=("build_pages",))
def _tags_in_search(BP):
    """The owner, 17 November 2026: tags "may replace the synonym matching system by having those sorts of synonyms
    built in but not displayed or at least minimally intrusive". On the harness's tags, with the search box's own
    reading (groupsFor, matches, whyListed, sortRows, searchHint, billOffers): "weed" lists the bill filed under
    Cannabis, and says so as a topic is said; "gravel tax" the bill tagged Excavation tax whose title says "removal
    of earth"; "attorney general", one phrase, the bill whose title says it first and the two tagged bills after
    it, their cards saying nothing of the tag and the line under the box no word that led there; "earthwork" the
    bill whose title has a longer word it begins before the tagged one, as a bill the table found comes after
    every bill with the reader's own word; and a tag's word stands for the whole search only -- "earthwork
    removal" and "ai commerce" list nothing, where the title had the other word. The offers say "All bills tagged Attorney
    General" and "All bills with the topic Cannabis", counted. With no tags in meta.json none of these finds more
    than the words do. And billmatch.js published with tags hands find.js setTagWords, after which the header
    search reads "gravel tax" as the tag's phrase."""
    got = _app_js("(() => {" + _TAGS_HARNESS + """
  scope.setState("2025-2026", META_T, ROWS);
  const out = {};
  const run = q => { scope.setQ(q); scope.setSort("best"); const gs = scope.groupsFor(q);
    return {ids: scope.sortRows(ROWS.filter(b => scope.matches(b))).map(b => b.id),
            why: ROWS.filter(b => scope.matches(b)).map(b => scope.whyListed(b, gs)).filter(Boolean),
            hint: scope.searchHint(gs, ROWS)}; };
  out.off = {weed: run("weed").ids, ag: run("attorney general").ids, gravel: run("gravel tax").ids};
  scope.setTagWords(TAGS, WORDS);
  for (const q of ["weed", "gravel tax", "attorney general", "earthwork", "earthwork removal", "ai", "excavat",
                   "ai commerce"])
    out[q] = run(q);
  const offer = q => scope.billOffers(q).map(o => [o.key, o.v, o.n, o.html]);
  out.offAg = offer("attorney general"); out.offWeed = offer("weed"); out.offExc = offer("excavat");
  return out;
})()""", names=_TAGS_NAMES + ("groupsFor", "whyListed", "sortRows", "searchHint", "billOffers",
                              "setSort: (s) => { sortBy = s; }"))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    assert got["weed"]["ids"] == ["HB2"] and got["weed"]["why"] == ["topic: Cannabis"], (
        f"'weed': {got['weed']}")
    assert got["gravel tax"]["ids"] == ["HB5"] and got["gravel tax"]["why"] == [], f"'gravel tax': {got['gravel tax']}"
    ag = got["attorney general"]
    assert ag["ids"] == ["HB4", "HB1", "HB3"], f"'attorney general' lists {ag['ids']}: the title's first, then the tag's"
    assert ag["why"] == [] and not re.search(r"attorney|tag", ag["hint"], re.I), (
        f"a card or the line under the box says what led to a tag: {ag['why']} / {ag['hint']!r}")
    assert got["earthwork"]["ids"] == ["HB6", "HB5"], (
        f"'earthwork' lists {got['earthwork']['ids']}: the reader's own word first, then the tag's bill")
    assert got["earthwork removal"]["ids"] == [], (
        f"'earthwork removal' lists {got['earthwork removal']['ids']}: a tag's word stands for the whole search only")
    assert got["ai"]["ids"] == ["HB3"], f"'ai': {got['ai']['ids']}"
    assert got["excavat"]["ids"] == [], f"the start of a tag's word lists its bills: {got['excavat']['ids']}"
    assert got["ai commerce"]["ids"] == [], (
        f"'ai commerce' lists {got['ai commerce']['ids']}: a tag's word stands for the whole search only")
    assert got["off"] == {"weed": [], "ag": ["HB4"], "gravel": []}, f"with no tags the words find {got['off']}"
    assert ["tag", "office-attorney-general", 2, "All bills tagged <b>Attorney General</b>"] in got["offAg"], (
        f"'attorney general' offers {got['offAg']}")
    assert ["topic", "Cannabis", 1, "All bills with the topic <b>Cannabis</b>"] in got["offWeed"], (
        f"'weed' offers {got['offWeed']}")
    assert any(o[:2] == ["tag", "excavation-tax"] for o in got["offExc"]), f"'excavat' offers {got['offExc']}"
    # The header search's matcher, as billmatch.js carries it on a site with tags.
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return "ok", "the bill search reads a tag's words; node is not here for the header's matcher"
    src = BP.bill_matcher_js(_source("src/pages/app.js"), tags=True)
    prog = ("globalThis.window=globalThis;\n" + src + "\nconst A=window.GR_BILLMATCH;\n"
            "const g0=A.queryGroups('gravel tax').map(g=>[g.word,g.to||'']);\n"
            "A.setTagWords([{id:'excavation-tax',name:'Excavation tax',definition:'x.'}],"
            "{'gravel tax':'tag:excavation-tax'});\n"
            "const g1=A.queryGroups('gravel tax').map(g=>[g.word,g.to||'']);\n"
            "console.log('@@'+JSON.stringify({g0,g1}));\n")
    r = _node_file(node, prog, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and "@@" in r.stdout, "billmatch.js with tags: " + (r.stderr or r.stdout)[-300:]
    hm = json.loads(r.stdout.rsplit("@@", 1)[1])
    assert hm["g0"] == [["gravel", ""], ["tax", ""]] and hm["g1"] == [["gravel tax", "tag:excavation-tax"]], (
        f"the header's matcher: before {hm['g0']}, after setTagWords {hm['g1']}")
    # And find.js hands it meta.json's words, as a page without app.js loads the two.
    root = Path(tempfile.mkdtemp())
    try:
        (root / "stub.js").write_text(_source("tests/dom_stub.js"), encoding="utf-8")
        (root / "page.js").write_text(_with_components(src + "\n" + _source("src/pages/find.js")), encoding="utf-8")
        files = {"/meta.json": {"terms": ["2025-2026"], "topics": [],
                                "tags": [{"id": "excavation-tax", "name": "Excavation tax", "definition": "x."}],
                                "tag_words": {"gravel tax": "tag:excavation-tax"}},
                 "/idx/2025-2026.json": [{"id": "HB5", "n": "HB 5", "year": 2025, "term": "2025-2026",
                                          "title": "relative to removal of earth", "tags": [0]}]}
        (root / "files.json").write_text(json.dumps(files), encoding="utf-8")
        (root / "go.js").write_text(
            'require("./stub.js");\nconst fs = require("fs"), vm = require("vm");\n'
            'const files = JSON.parse(fs.readFileSync("./files.json", "utf8"));\n'
            'globalThis.fetch = async (u) => { const p = decodeURIComponent(new URL(u).pathname);\n'
            '  return p in files ? {ok: true, status: 200, json: async () => files[p]}\n'
            '    : {ok: false, status: 404, json: async () => { throw new Error("404"); }}; };\n'
            'vm.runInThisContext(fs.readFileSync("./page.js", "utf8"), {filename: "page.js"});\n'
            '(async () => { await vm.runInThisContext("findBillsLoad")();\n'
            '  const A = vm.runInThisContext("FBILLS").api;\n'
            '  console.log("@@" + JSON.stringify(A.queryGroups("gravel tax").map(g => [g.word, g.to || ""])));\n'
            '})().catch(e => { console.log("RUN " + (e && e.stack || e)); process.exit(1); });\n', encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=120)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert r.returncode == 0 and "@@" in r.stdout, "find.js with tags: " + (r.stdout + r.stderr)[-300:]
    fj = json.loads(r.stdout.rsplit("@@", 1)[1])
    assert fj == [["gravel tax", "tag:excavation-tax"]], f"find.js does not hand the header its tag words: {fj}"
    return "ok", ("weed -> the Cannabis topic's bill; gravel tax -> the tagged bill; attorney general -> the title's "
                  "bill, then the tag's two, nothing said of the tag; offers name and count it; none of it without "
                  "tags; the header's matcher reads the tag's phrase once find.js hands it the words")


# APP.JS IS ITS PARTS (20 November 2026, the refactor's finding 6). app.js is
# written from the files in src/pages/app/, joined in the order of their names
# (app_parts.py), and stays in the repository: everything that reads it reads
# the joined file. Who may name the parts, each with its reason; a module of
# the suite plants trees of its own and is not read.
APP_PARTS_READERS = {
    "app_parts.py": "writes app.js from them, and carries an edit made in app.js back",
    "build_inputs.py": "leaves them out of what a build is made from: the build reads app.js",
    "front_end.py": "refuses the fast path while app.js is not its parts, so that a part edited is "
                    "never left out of the site without a word",
}


@check("files", "app.js is its parts in src/pages/app/, joined in order; a billmatch part is one "
                "BILLMATCH region whole; and nothing but app_parts.py reads a part", needs=("app_parts",))
def _app_js_is_its_parts(AP):
    """app.js is made of its parts (app_parts.py): app.js's own first line,
    its stamp, then each file of src/pages/app/ in the order of its name.
    The build, the fast path, the search index and every check read app.js,
    the joined file, and never a part. Held:

      on a planted tree: app.js that is its parts is said to be; a part
      edited is found, by its line, until app.js is written, which keeps the
      stamp line and writes nothing a second time; an edit made in app.js
      goes back into the part that holds it (--split), and --split refuses,
      writing nothing, where a part's first line is gone from app.js; a
      part misnamed, a billmatch part that is not one region whole, a
      marker in another part and a first line found twice are each named;
      here: the parts are right and app.js is their join;
      no code file but APP_PARTS_READERS imports app_parts or names the
      parts' folder in its code (its docstrings aside), so no builder reads a
      part on its own.
    """
    import ast

    from pf_core import _parsed
    stamp = b"// GRANITE_VERSION: 2026-01-02.3\n"
    planted = {"010-a.js": b"const A=1;\n",
               "020-billmatch-b.js": b"// BILLMATCH:BEGIN -- b\nfunction b(){return A;}\n// BILLMATCH:END\n",
               "030-c.js": b"// C, the last\nconst C=3;\n"}
    tmp = Path(tempfile.mkdtemp(prefix="gr-parts-"))
    try:
        (tmp / AP.FOLDER).mkdir(parents=True)
        for n, t in planted.items():
            (tmp / AP.FOLDER / n).write_bytes(t)
        app, last = tmp / AP.APP, tmp / AP.FOLDER / "030-c.js"
        app.write_bytes(stamp + b"".join(planted.values()))
        assert AP.stale(tmp) is None and AP.faults(tmp) == [], (
            f"a planted app.js that is its parts: {AP.stale(tmp)} {AP.faults(tmp)}")
        last.write_bytes(b"// C, the last\nconst C=4;\n")
        why = AP.stale(tmp)
        assert why and "line 7" in why, f"a part edited and app.js not written is said as {why!r}"
        assert AP.write(tmp) and app.read_bytes().startswith(stamp) and b"C=4" in app.read_bytes() \
            and AP.stale(tmp) is None and not AP.write(tmp), (
            "writing app.js did not put the edited part in after its stamp line, once")
        app.write_bytes(app.read_bytes().replace(b"C=4", b"C=5"))
        assert AP.stale(tmp) and AP.split(tmp) == ["030-c.js"] and b"C=5" in last.read_bytes() \
            and AP.stale(tmp) is None, "an edit made in app.js did not go back into its part"
        app.write_bytes(app.read_bytes().replace(b"// C, the last", b"// C"))
        try:
            AP.split(tmp)
            raise AssertionError("--split cut app.js where a part's first line was gone from it")
        except ValueError:
            pass
        assert b"C=5" in last.read_bytes() and b"// C, the last" in last.read_bytes(), \
            "a refused --split wrote a part"
        (tmp / AP.FOLDER / "020-billmatch-b.js").write_bytes(b"// BILLMATCH:BEGIN\nfunction b(){}\n")
        (tmp / AP.FOLDER / "010-a.js").write_bytes(b"// C, the last\n// BILLMATCH:END\n")
        (tmp / AP.FOLDER / "x.js").write_bytes(b"const X=0;\n")
        said = " | ".join(AP.faults(tmp))
        for want in ("x.js: a part is named", "020-billmatch-b.js: a billmatch part is one",
                     "010-a.js:2: a BILLMATCH marker outside", "found 2 times"):
            assert want in said, f"the planted faults are said as {said!r}, without {want!r}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = AP.faults()
    assert not bad, "the parts of app.js: " + "; ".join(bad[:4])
    why = AP.stale()
    assert why is None, why
    regions = [p.name for p in AP.parts() if AP.BILLMATCH in p.name]
    assert regions, "no part of app.js is a BILLMATCH region: site/billmatch.js would be cut from nothing"

    def code_strings(tree):
        prose = {id(d.body[0].value) for d in ast.walk(tree)
                 if isinstance(d, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                 and d.body and isinstance(d.body[0], ast.Expr) and isinstance(d.body[0].value, ast.Constant)}
        return [d.value for d in ast.walk(tree) if isinstance(d, ast.Constant)
                and isinstance(d.value, str) and id(d) not in prose]
    suite = (_paths.ROOT / "src" / "checks" / "suite").resolve()
    folder = AP.FOLDER.rstrip("/")
    readers = {}
    for f in _paths.code_files("*.py"):
        if f.resolve().parent == suite:
            continue
        tree = _parsed(f)
        if any(isinstance(n, ast.Import) and any(a.name == "app_parts" for a in n.names)
               or isinstance(n, ast.ImportFrom) and n.module == "app_parts" for n in ast.walk(tree)) \
                or any(s.rstrip("/") == folder or (folder + "/") in s for s in code_strings(tree)):
            readers[f.name] = f
    unknown = sorted(set(readers) - set(APP_PARTS_READERS))
    assert not unknown, ("these read app.js's parts, which only app_parts.py may: " + ", ".join(unknown)
                         + ". Read app.js, which is the parts joined, or say in APP_PARTS_READERS why not.")
    gone = sorted(set(APP_PARTS_READERS) - set(readers))
    assert not gone, "APP_PARTS_READERS names modules that do not read the parts: " + ", ".join(gone)
    return "ok", (f"app.js is its {len(AP.parts())} parts, {len(regions)} of them the BILLMATCH regions "
                  f"site/billmatch.js is cut from; read by {', '.join(sorted(readers))} alone; and on a "
                  "planted tree a part edited, an edit in app.js and five faults are each found")