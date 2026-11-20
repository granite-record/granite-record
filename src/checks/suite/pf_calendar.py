#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.4
"""
preflight's checks of the calendar.

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import csv
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

import _paths

from pf_core import (_run, _source, check)
from pf_fixture import (CHAIN_NEEDS, _fixture_site_shared, _fixture_site_whole)
from pf_harness import (_components_js, _node_file, _with_components)
from pf_shared import (CAL_TODAY, INLINE_BODY, _CAL_DOM, _DOCS_H, _DOCS_HC, _DOCS_HC35, _DOCS_S,
                       _DOCS_SC29, _DOCS_SJ, _braced, _cal_fixture, _cal_node, _cal_rows,
                       _cite_plain, _docs_fixture, _docs_page, _docs_turn, _docs_write_old,
                       _front_sources, _line_of, _visible_text)


@check("build", "every builder runs end to end on a fixture site")
def _chain():
    """The check that would have caught the worst bug of the session.

    Importing a module and calling its pure functions never enters main(), so
    build_site_v2.py lost sixty-four lines of its loading code and every check
    here stayed green until a real build failed. This builds a four-bill project
    in the system temp directory and runs the whole chain over it, in
    build_all's order, then check_site: nothing touches the real site, nothing
    touches the network.

    IT NEVER RAN AT ALL FOR MOST OF ITS LIFE, and a check that does not run is
    worse than none. Its decorator sat stacked on _proceedings_table, from the
    repository's first commit, so this name ran that function twice and this
    one not at all -- while its feed assertion was the reason a page could not
    link a feed that was never written.

    A fixture has to carry what each builder reads, or the chain fails on the
    fixture rather than on the code: build_pages wants app.css, app.js and
    bills.html in src/pages/ under its working directory and copies assets/
    beside the pages, and later builders want a committee list, a district map
    and the offices file. All ten run.
    """
    here = Path(".").resolve()
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    root = Path(tempfile.mkdtemp())
    try:
        base, steps = _fixture_site_whole(root)
        # The district map's file, script and stylesheet (9 October 2026):
        # published by the night, though no page mounts the map yet.
        dm = json.loads((root / "site" / "district_map.json").read_text(encoding="utf-8"))
        assert dm["places"] and dm["fill"]["base"] and dm["arcs"], \
            "build_district_map wrote a district_map.json with nothing in it"
        # map.js as the site publishes every script, without its comments
        # (strip_js.py, 23 October 2026); map.css as it is.
        import strip_js
        src_js = (here / "src/pages/map.js").read_bytes().decode("utf-8")
        assert (root / "site" / "map.js").read_bytes().decode("utf-8") == strip_js.strip(src_js), \
            "site/map.js is not src/pages/map.js without its comments"
        assert (root / "site" / "map.css").read_bytes() == (here / "src/pages/map.css").read_bytes(), \
            "site/map.css is not src/pages/map.css"
        # llms.txt (24 September): it exists, says the one thing that must
        # never move -- this is not the General Court's official record --
        # and the example bill address it gives is a page that was built.
        llms = (root / "site" / "llms.txt").read_text(encoding="utf-8")
        assert llms.startswith("# Granite Record"), "llms.txt lost its title"
        assert "not the General Court's official record" in llms, \
            "llms.txt no longer says the site is not the official record"
        ex = re.search(re.escape(base) + r"/bill/(\d{4})/([a-z0-9]+)", llms)
        assert ex and (root / "site" / "bill" / ex.group(1) / f"{ex.group(2)}.html").exists(), \
            "llms.txt gives an example bill address that was not built"
        # And (12 October 2026: AI assistants should find "trustworthy
        # sources" here) it names the Laws and Resources and says how to read
        # the record, and robots.txt welcomes every crawler but keeps /api/.
        assert f"{base}/laws" in llms and f"{base}/resources" in llms and "## How to read the record" in llms, \
            "llms.txt does not name the Laws and Resources or say how to read the record"
        robots = (root / "site" / "robots.txt").read_text(encoding="utf-8")
        assert "User-agent: *\nAllow: /\nDisallow: /api/\n" in robots and "Sitemap:" in robots, robots
        # Every bill page that advertises a feed has one. The records moved
        # inside the pages on 9 September and build_feeds went on reading the
        # old side files, so 5,436 pages linked a feed nobody wrote -- and this
        # chain passed, because all.xml was still produced.
        sys.path.insert(0, str(here))
        import site_read as SR
        # A per-bill feed is written for the term still sitting, and a page
        # links one only where it was written. Closed terms stopped getting
        # them when the 1989-2016 histories arrived: 22,840 files that could
        # never gain an item, on a deployment near a file limit.
        # A RETIRED FEED IS UNLINKED ON PURPOSE. A concluding bill gets one
        # final update saying how it ended and then retires, so a bill that
        # concluded in the sitting term keeps its feed, carrying that closing
        # item -- for the people already subscribed, who would otherwise get a
        # 404 and never learn the bill had finished -- while its page stops
        # offering one, because only a bill still moving can be followed.
        #
        # The guard keeps its teeth in the direction that matters. A page
        # linking a feed nobody wrote is still a failure, and that is the
        # defect this check was written for: 5,436 pages once advertised a feed
        # build_feeds had stopped producing. What is now allowed is exactly the
        # other direction, and only where the bill's own record says it has
        # concluded in the term still sitting.
        # AN IN-PAGE LINK THAT NAMES ITS OWN PAGE, AND LANDS ON A REAL ID.
        #
        # These pages are built from bills.html, which sets <base href="/">, so
        # href="#s-vetoes" resolves against the BASE and sends the reader to
        # the home page. _links_resolve will not catch that: it urldefrags
        # every href before resolving, so a bare fragment reads as the site
        # root and passes while every entry in a contents rail is wrong.
        # footer_nav's docstring records the same trap springing once already,
        # with "../learn.html". On this page folded into the head of each page
        # on 9 October 2026 (the component plan); its list is the one held here.
        #
        # The second half is the slower version of the same failure. The ids
        # are DERIVED from the headings, so a heading reworded in civics.py
        # changes its slug; if the pass that collects them and the pass that
        # writes the hrefs ever come apart, the link dies silently on a page
        # nobody is watching. Checking that the id exists is what makes
        # deriving them safe enough to prefer over sixty-two hand-written ones.
        learn = sorted((root / "site" / "learn").glob("*.html"))
        assert learn, "the chain built no learn pages for the contents check"
        n_toc = 0
        for f in learn:
            page = f.read_text(encoding="utf-8", errors="replace")
            ids = set(re.findall(r'id="([^"]+)"', page))
            want = f"learn/{f.stem}"
            for nav in re.findall(r'<nav class="l-otpb".*?</nav>', page, re.S):
                for href in re.findall(r'href="([^"]*)"', nav):
                    path, _, frag = href.partition("#")
                    assert path == want, (
                        f"{f.name}: a contents link says href={href!r}. It must "
                        f"name its own page ({want!r}) -- these pages carry "
                        "<base href=\"/\">, so a bare fragment goes to the "
                        "home page and every link check still passes")
                    assert frag and frag in ids, (
                        f"{f.name}: the contents link {href!r} points at an id "
                        "that is not on the page")
                    n_toc += 1
        assert n_toc, ("no learn page carries an On this page list, so nothing here "
                       "was actually checked")
        # EVERY PAGE, NOT ONLY LEARN (23 October 2026). The Data page's On
        # this page list was written href="#downloads", and every entry went
        # to the home page; a committee page's meeting dates did the same from
        # app.js. So every built page that carries <base href="/"> is swept for
        # a bare fragment outside its scripts -- the skip link excepted, which
        # find.js takes by its id -- and the scripts that draw pages may not
        # write one either (app.js dayHref names the page, as skipHere does).
        bare = []
        for f in sorted((root / "site").rglob("*.html")):
            page = f.read_text(encoding="utf-8", errors="replace")
            if '<base href="/">' not in page:
                continue
            body = re.sub(r"<script\b.*?</script>", "", page, flags=re.S)
            for m in re.finditer(r'<a\b[^>]*\bhref="#[^"]*"[^>]*>', body):
                if 'class="skip"' not in m.group(0):
                    bare.append(f"{f.relative_to(root / 'site')}: {m.group(0)[:80]}")
        assert not bare, ("a page that carries <base href=\"/\"> links a bare fragment, "
                          "which goes to the home page: " + "; ".join(bare[:5]))
        for js in sorted(Path("src/pages").glob("*.js")) + sorted(Path("src/pages/inline").glob("*.js")):
            hit = re.search(r'href=\\?"#\$\{', js.read_text(encoding="utf-8"))
            assert not hit, (f"{js.name} writes a link to a bare fragment, href=\"#${{...}}: "
                             "under <base href=\"/\"> it goes to the home page")
        # THE LEARN HUB'S OLD ADDRESS IS A REDIRECT NOW (decision 128): /learn and
        # /learn.html go to /resources, which _redirects says and no file
        # shadows, and the hub is where the redirect lands.
        red = (root / "site" / "_redirects").read_text(encoding="utf-8")
        for old in ("/learn", "/learn.html"):
            assert f"\n{old} /resources 301\n" in red, f"_redirects does not send {old} to /resources"
        assert not (root / "site" / "learn.html").exists(), (
            "a learn.html is in the site, where the redirect to /resources should answer")
        # AND THE LEGISLATORS PAGE IS OFFICIALS (decision 127): /legislators and
        # /legislators.html go to /officials, no file shadows them, and no rule
        # reaches the members' data under /legislators/ or their pages.
        for old in ("/legislators", "/legislators.html"):
            assert f"\n{old} /officials 301\n" in red, f"_redirects does not send {old} to /officials"
        # A PATTERN, that is: one renamed member's old address sent to the
        # new one (build_pages.MOVED) reaches that page and no other.
        assert not any(ln.split()[0].startswith(("/legislators/", "/legislator/"))
                       and ln.split()[-1] == "301" and re.search(r"[:*]", ln.split()[0])
                       for ln in red.splitlines() if ln.strip()
                       and not ln.startswith("#")), (
            "a redirect pattern reaches the members' data or pages")
        assert not (root / "site" / "legislators.html").exists() and \
            (root / "site" / "officials.html").exists(), (
            "a legislators.html is in the site, or no officials.html, where /officials should answer")
        hub = (root / "site" / "resources.html").read_text(encoding="utf-8")
        for pid in ("learn", "guides", "sources"):
            assert f'id="tab-{pid}"' in hub and f'<div class="twnpane r-sheet" id="{pid}"' in hub, (
                f"the Resources hub has no {pid} tab")
        # THE LEARN TAB COUNTS WHAT ITS PANEL LINKS (16 October 2026): it read
        # "Learn (14)" over sixteen links when the glossary and Laws came in
        # after the count was typed as the topics plus one.
        said = re.search(r'id="tab-learn"[^>]*>Learn <span class="r-n">\((\d+)\)</span>', hub)
        # The Learn panel to the next one, whichever follows it: How-To Guides
        # comes first since 17 October 2026.
        at = hub.index('<div class="twnpane r-sheet" id="learn"')
        pane = hub[at:hub.find('<div class="twnpane r-sheet"', at + 1)]
        linked = len(set(re.findall(r'<a href="([^"]+)"', pane)))
        assert said and int(said.group(1)) == linked, (
            f"the Learn tab says {said.group(1) if said else 'no count'} over a panel of "
            f"{linked} pages")

        # COMING UP ON THE BUILT HOME PAGE IS THE BUILD DATE'S WEEK: no day
        # before the build date or after that week's Sunday, and every day in
        # between that the fixture's proceedings.csv holds a sitting on. The
        # fixture's hearing is dated three days from the clock, so from Monday
        # to Thursday it is on the rail and from Friday it is next week's and
        # must not be. _coming_up_is_this_week draws it for fixed dates.
        import build_calendar as BC
        import proceedings as _P
        from datetime import date as _date, timedelta as _td
        # FROM SATURDAY, NEXT WEEK (D13, 8 October 2026): built on a Saturday
        # or a Sunday the rail is the coming Monday's week, whole.
        built = _date.fromisoformat(json.loads((root / "site" / "home.json").read_text(
            encoding="utf-8"))["generated"])
        if built.weekday() >= 5:
            built = built + _td(days=7 - built.weekday())
        wk_end = built + _td(days=6 - built.weekday())
        homepage = (root / "site" / "index.html").read_text(encoding="utf-8",
                                                            errors="replace")
        # COMING UP'S OWN DAYS, in its own section: Latest Activity's days are
        # .calday blocks too since 24 October 2026, and every one is past.
        cal_at = homepage.find('<section class="cal"')
        coming = homepage[cal_at:homepage.find("</section>", cal_at)] if cal_at >= 0 else ""
        rail = re.findall(r'class="calday" data-d="([^"]+)"', coming)
        stray = [d for d in rail if not built.isoformat() <= d <= wk_end.isoformat()]
        assert not stray, (
            f"the built home page's Coming up shows {stray}, outside the week "
            f"it was built for ({built} to {wk_end})")
        week = BC.weeks_from(_P.load(root / "proceedings.csv")).get(
            BC.week_key(built)) or {}
        due = sorted(d for d in week if d >= built.isoformat() and week[d])
        # AND A DAY OF THE WEEK'S KEY DATES (the owner, 24 October 2026: the
        # election days, town meeting day, organization day "would show up
        # under the coming up section when they are within that week's
        # days"; build_pages.calendar_html). A day on the rail with no
        # sitting is one only if it holds a key date's card (.calkd). Held to
        # sittings alone, this failed every night from Saturday 31 October
        # 2026, when the rail's week took in Election Day, 3 November, and
        # stopped the night at preflight on main and dev alike.
        block = dict(re.findall(r'class="calday" data-d="([^"]+)"(.*?)(?=class="calday" data-d=|\Z)',
                                coming, re.S))
        keyed = [d for d in rail if d not in due and 'class="calkd"' in block.get(d, "")]
        assert rail == sorted(set(due) | set(keyed)), (
            f"the built home page's Coming up shows {rail} for the week {built} to "
            f"{wk_end}: sitting days missing from it {sorted(set(due) - set(rail))}, "
            f"days on it with neither a sitting nor a key date "
            f"{sorted(set(rail) - set(due) - set(keyed))}")
        # A SITTING DAY CARRIES ITS SITTING. A key date's day is on the rail
        # whatever it holds, so the day being there no longer says the
        # meeting card is: 4 November is a key date and a sitting day both.
        unmet = [d for d in due if '<details class="calmeet"' not in block.get(d, "")]
        assert not unmet, (
            f"the built home page's Coming up draws {unmet} without the fixture's "
            f"sitting on it")

        idx = SR.bill_index(root / "site")
        current = max((b.get("term") or "" for b in idx), default="")
        kind_of = {(str(b.get("year")), str(b.get("id")).upper()):
                   (b.get("term") or "", b.get("kind") or "") for b in idx}
        retired = 0
        for year, bid, rec in SR.records(root / "site"):
            page = (root / "site" / "bill" / year / f"{bid.lower()}.html").read_text(
                encoding="utf-8", errors="replace")
            fx = root / "site" / "feed" / "bill" / year / f"{bid.lower()}.xml"
            links = f'/feed/bill/{year}/{bid.lower()}.xml"' in page
            assert not (links and not fx.exists()), (
                f"{bid} of {year}: the page links a feed that was not written")
            if fx.exists() and not links:
                term, kind = kind_of.get((year, bid.upper()), ("", ""))
                assert term == current and kind not in ("active", "study"), (
                    f"{bid} of {year}: the page has a feed it does not link, "
                    f"and the bill is not a concluded one of {current} "
                    f"(term {term!r}, kind {kind!r}) -- so the feed is an "
                    "orphan rather than a retired one")
                retired += 1
        # And a member's page, in the pipeline's own order: the pages are
        # written before the feeds, so this is where naming a feed the feed
        # builder then skips would show.
        members = json.loads((root / "site" / "legislators.json").read_text(encoding="utf-8"))
        named = 0
        for m in members:
            page = (root / "site" / "legislator" / f"{m['slug']}.html").read_text(
                encoding="utf-8", errors="replace")
            links = f'href="/feed/legislator/{m["id"]}.xml"' in page
            wrote = (root / "site" / "feed" / "legislator" / f"{m['id']}.xml").exists()
            assert links == wrote, (
                f"member {m['id']}: the page " + ("names a feed that was not written"
                                                  if links else "does not name its feed"))
            named += links
        # And a committee's, since 14 September: the Follow control reads the
        # feed a page names, so a page naming one that was not written offers a
        # dead link, and one that does not name its feed offers nothing.
        for cp in sorted((root / "site" / "committee").glob("*.html")):
            page = cp.read_text(encoding="utf-8", errors="replace")
            links = f'href="/feed/committee/{cp.stem}.xml"' in page
            wrote = (root / "site" / "feed" / "committee" / f"{cp.stem}.xml").exists()
            assert links == wrote, (
                f"committee {cp.stem}: the page " + ("names a feed that was not written"
                                                     if links else "does not name its feed"))
        # THE CARD A SHARED LINK UNFURLS INTO, THE SITEMAP'S DATES AND THE TABS'
        # ADDRESSES (14 September). A bill page and a member page each name their
        # own section's wide card; a bill's card title says what the bill is and
        # not "New Hampshire General Court"; lastmod is a date; and the tab slugs
        # app.js reads are exactly the ones _redirects serves.
        import build_pages as BP
        bhead = next((root / "site" / "bill").rglob("*.html")).read_text(
            encoding="utf-8", errors="replace")
        assert 'og-bill.png"' in bhead and 'content="summary_large_image"' in bhead, (
            "a bill page's link card is not the bills section's wide card")
        ogt = re.search(r'property="og:title" content="([^"]*)"', bhead).group(1)
        assert "General Court" not in ogt and ":" in ogt, f"a bill's link card is titled {ogt!r}"
        if members:
            mhead = (root / "site" / "legislator" / f"{members[0]['slug']}.html").read_text(
                encoding="utf-8", errors="replace")
            assert 'og-legislator.png"' in mhead, "a member page's link card is not the legislators card"
        sm = (root / "site" / "sitemap.xml").read_text(encoding="utf-8")
        assert re.search(r"<lastmod>\d{4}-\d{2}-\d{2}</lastmod>", sm), "the sitemap carries no dates"
        red = (root / "site" / "_redirects").read_text(encoding="utf-8")
        js = (here / "src/pages/app.js").read_text(encoding="utf-8")
        for name, slugs in (("BILL_TABS", BP.BILL_TAB_SLUGS), ("MEMBER_TABS", BP.MEMBER_TAB_SLUGS),
                            ("COMMITTEE_TABS", BP.COMMITTEE_TAB_SLUGS)):
            got = re.search(r"const " + name + r"=\{([^}]*)\}", js)
            keys = set(re.findall(r"(\w+):", got.group(1))) if got else set()
            assert keys == set(slugs), f"app.js {name} {sorted(keys)} and build_pages {slugs} disagree"
            assert all(f"/{s} " in red for s in slugs), f"_redirects does not serve every {name} slug"
        # What a stylesheet asks for is a request too, and check_site reads only
        # the pages' own href and src. The nav's mark and, since 13 September,
        # the home page's lockup are CSS masks: a mask whose file is missing is
        # drawn as nothing, silently, and the heading above the search box would
        # be an empty band. And that heading is still its words to anything that
        # cannot see it.
        for css in ("app.css",):
            p = root / "site" / css
            if not p.exists():
                continue
            for ref in sorted(set(re.findall(r"url\((/[^)\s\"']+)\)", p.read_text(encoding="utf-8")))):
                assert (root / "site" / ref.lstrip("/")).exists(), (
                    f"{css} asks for {ref}, which the build did not put in the site")
        home = (root / "site" / "index.html").read_text(encoding="utf-8", errors="replace")
        assert '<h1 class="lockup"><span>Granite Record</span></h1>' in home, (
            "the home page's heading is not the lockup with its name kept as text")
        # EVERY SITTING DAY CAN BE REACHED, AND NOTHING LEADS TO ONE THAT IS
        # NOT THERE (the audit of 2 October 2026, B3). Of 1,563 sitting pages
        # 62 had a link from anything but the sitting beside them. What must
        # hold of the built site: each chamber's list in the directory links
        # every page that chamber has and no other; the directory names both
        # lists; session/days.json, which app.js asks before it links a
        # vote's date, is the pages on disk; each page leads up to its
        # chamber's list, and to its week only where the calendar wrote that
        # week; and the home page hands its script only days that have a page.
        sess = root / "site" / "session"
        # Dated pages only, and not a morning page (build_live_session's
        # is_morning, its marker in the page's head): a sitting still to come
        # is in no list. NOT YET EXERCISED: the chain has no live step until
        # workers/live/PATCHES.md 5 is applied, so no morning page reaches it;
        # _live_session holds the step on its own.
        import build_live_session as _BLS
        on_disk = {b: sorted(p.stem for p in (sess / b).glob("*.html")
                             if re.fullmatch(r"\d{4}-\d\d-\d\d", p.stem) and not _BLS.is_morning(p))
                   for b in ("H", "S")}
        assert all(on_disk.values()), f"the chain built no sitting pages for a chamber: {on_disk}"
        listed = json.loads((sess / "days.json").read_text(encoding="utf-8"))
        assert {b: listed.get(b) for b in ("H", "S")} == on_disk, (
            f"session/days.json lists {listed} and the pages on disk are {on_disk}: "
            "app.js links a vote's date to the days this file names")
        # And its roll calls are the "rc-<key>" ids those pages carry, each at
        # its own page (the preview check of 25 October 2026): app.js links
        # "#rc-<key>" only where this says a page draws one.
        ids_on_disk = {"H": {}, "S": {}}
        hub = (root / "site" / "directory.html").read_text(encoding="utf-8")
        weeks = {p.stem for p in (root / "site" / "calendar").glob("*-W*.html")}
        n_up = 0
        for b, name, lst in (("H", "House", "sessions-house"), ("S", "Senate", "sessions-senate")):
            page = (root / "site" / "directory" / f"{lst}.html").read_text(encoding="utf-8")
            got = sorted(re.findall(rf'href="session/{b}/(\d{{4}}-\d\d-\d\d)"', page))
            assert got == on_disk[b], (
                f"/directory/{lst} links {got} and the {name}'s pages are {on_disk[b]}")
            assert f'href="directory/{lst}">Every {name} session day</a>' in hub, (
                f"the directory does not link the list of {name} session days")
            for d in on_disk[b]:
                day = (sess / b / f"{d}.html").read_text(encoding="utf-8")
                for rid in re.findall(r'\bid="rc-([^"]+)"', day):
                    ids_on_disk[b].setdefault(rid, d)
                # THE RECORD HEAD'S TRAIL (C6, 10 October 2026), where the
                # line above the heading was; the week on the Calendar is in
                # the line between the previous and next days.
                up = re.findall(r'<div class="wkpage sesspage"><header class="rhead rh-day">'
                                r'<nav class="rtrail"[^>]*>(.*?)</nav>', day, re.S)
                # The week is the pager's, between the previous and next
                # days ("The Week of ...", build_session_pages.pager).
                mid = re.findall(r'<nav class="wknav[^"]*" aria-label="Other session days">'
                                 r'(.*?)</nav>', day, re.S)
                import proceedings as _PR
                _t = _PR.vote_term(d[:4], d)
                assert len(up) == 1 and f'href="session/{ {"H": "house", "S": "senate"}[b]}?term={_t}#day-{d}"' in up[0], (
                    f"session/{b}/{d} does not lead up to the {name}'s page of session "
                    "days, at its term, in a line above its heading")
                assert f'id="y{d[:4]}"' in page, (
                    f"/directory/{lst} has no heading for {d[:4]}, which "
                    f"session/{b}/{d} leads to")
                y, w, _ = _date.fromisoformat(d).isocalendar()
                wk = f"{y}-W{w:02d}"
                assert mid and (f'href="calendar/{wk}"' in mid[0]) == (wk in weeks), (
                    f"session/{b}/{d} {'does not link' if wk in weeks else 'links'} "
                    f"its week on the Calendar, {wk}, which the calendar "
                    f"{'wrote' if wk in weeks else 'did not write'}")
                n_up += wk in weeks
                # Previous on the left and next on the right, as before.
                navs = re.findall(r'<nav class="wknav[^"]*" aria-label="Other session days">(.*?)</nav>',
                                  day, re.S)
                order = re.findall(r'class="(wkprev|wknext)"', navs[0]) if navs else None
                assert len(navs) == 2 and order == sorted(order, reverse=True), (
                    f"session/{b}/{d}: its nav reads {order}")
        assert listed.get("rc") == ids_on_disk, (
            f"session/days.json names the roll calls {listed.get('rc')} and the pages carry "
            f"rc- ids for {ids_on_disk}: a member's Votes tab links \"#rc-<key>\" where this "
            "file says a page draws one")
        # RECENT SESSION DAYS (build_pages.recent_sessions, 26 October 2026):
        # each player's date leads to its sitting's page, and to no day
        # without one; and each player is a Play button until pressed.
        handed = re.search(r'<div id="session">(.*?)</div>\s*</section>', homepage, re.S)
        assert handed, "the home page has no Recent Session Days"
        linked = re.findall(r'href="/?session/([HS])/(\d{4}-\d\d-\d\d)"', handed.group(1))
        for b, d in linked:
            assert d in on_disk.get(b, []), (
                f"the home page links the sitting {b}/{d}, which has no page")
        assert linked, (
            "the home page's Recent Session Days dates none of its players to their pages, "
            "though the fixture's newest recorded sitting has a page: " + handed.group(1)[:200])
        assert handed.group(1).count('class="pstub"') >= len(linked) \
            and "<iframe" not in handed.group(1), (
                "a sitting on the home page is not a Play button, or a player is loaded before "
                "Play is pressed: " + handed.group(1)[:300])
        # EVERY LANDMARK HAS A NAME, AND EVERY TABLE A HEADER CELL (the audit
        # of 2 October 2026, M6 and M7). A Learn article carries three navs
        # and a week of the Calendar four, and the one on every page had no
        # label; the bill search row was outside every landmark; the home
        # page's activity and the Learn pages' two-column tables had no header
        # cell at all, so a screen reader was given a grid with nothing to say
        # what a column is, or no table. Over every page the chain built.
        unnamed, headless, n_nav, n_tab = [], [], 0, 0
        for f in sorted((root / "site").rglob("*.html")):
            page = INLINE_BODY.sub(r"\1", f.read_text(encoding="utf-8", errors="replace"))
            rel = f.relative_to(root / "site").as_posix()
            for tag in re.findall(r"<nav\b[^>]*>", page):
                n_nav += 1
                if "aria-label=" not in tag and "aria-labelledby=" not in tag:
                    unnamed.append(f"{rel}: {tag[:60]}")
            for tab in re.findall(r"<table\b.*?</table>", page, re.S):
                # The Calendar's month is a grid its script fills, days and
                # headings both; what is in the markup is its empty frame.
                if re.match(r'<table\b[^>]*\brole="grid"', tab):
                    continue
                n_tab += 1
                if not re.search(r"<th\b", tab):
                    headless.append(f"{rel}: {' '.join(tab.split())[:70]}")
                # A table that is all data, as the exports page's coverage
                # is: every row of its body opens with the cell that heads it.
                if 'class="cov"' in tab:
                    body = tab[tab.index("<tbody"):]
                    trs = re.findall(r"<tr>\s*<(t[hd])\b([^>]*)>", body)
                    if not trs or any(t != "th" or 'scope="row"' not in a for t, a in trs):
                        headless.append(f"{rel}: a term of the coverage table does not head its row")
            if 'class="searchrow"' in page:
                assert re.search(r'<div class="searchrow" role="search" aria-label="[^"]+"(?: hidden)?>',
                                 page), (
                    f"{rel}: the bill search row is not a named search landmark")
            if 'id="facets"' in page:
                assert re.search(r'<aside class="facets" id="facets" aria-label="[^"]+">', page), (
                    f"{rel}: the filters are an aside with no name")
        assert n_nav and not unnamed, (
            f"{len(unnamed)} navs with no name: " + "; ".join(unnamed[:4]))
        assert n_tab and not headless, (
            f"{len(headless)} tables with no header cell: " + "; ".join(headless[:4]))
        r = _run([sys.executable, _paths.script("check_site.py"),
                            "--site", "site", "--base", base],
                           cwd=root, capture_output=True, text=True, timeout=120)
        bad = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("x ")]
        assert not bad, "check_site: " + "; ".join(bad)[:140]
        return "ok", (f"{steps} builders in build_all's order, then check_site, on a "
                      f"4-bill fixture; every bill and member page names only feeds that exist "
                      f"({named} of {len(members)} members have one)")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "every page names its own address with a slash after the domain")
def _addresses_have_slash():
    """1,670 pages cited "https://graniterecord.orgsession/H/2026-05-21".

    build_calendar and build_session_pages passed shell.page a path without its
    leading slash, and every place the page states its own address is the
    domain joined to that path: the "Cite this page" block a reader pastes into
    their own work, the canonical link, og:url, the structured data -- and,
    through the builder's own join, 1,669 sitemap entries. It went live on
    18 September and was found on the 24th. Every link check here passed,
    because every one of them read an href, and none of these is one:
    preflight only asked that a canonical link be PRESENT, and check_site took
    the base off a sitemap entry and then lstrip'd the slash, which was the
    fault, away.

    So this reads each of those addresses off every page of the fixture site
    and wants the base followed by "/". It also plants the stale and the
    malformed entries a builder rebuilt on its own would once have left in
    sitemap.xml, reruns the calendar and the House's sitting days, and wants
    them gone -- with the Senate's entry, which the House run does not own,
    left where it was.
    """
    import html as _html
    here = Path(".").resolve()
    absent = [x for x in CHAIN_NEEDS + ["build_calendar.py", "shell.py"]
              if not _paths.locate(x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    sys.path.insert(0, str(here))
    import shell as S
    import build_calendar as BC
    try:
        S.address("https://graniterecord.org", "session/H/2026-05-21.html")
    except AssertionError:
        pass
    else:
        raise AssertionError("shell.address joined a path with no leading slash "
                             "instead of refusing it")
    root = Path(tempfile.mkdtemp())
    try:
        base, _steps = _fixture_site_whole(root)
        site = root / "site"
        want = base + "/"
        at_base = re.compile(re.escape(base) + r'[^\s"<,}&]*')
        bad, seen = [], Counter()
        for p in sorted(site.rglob("*.html")):
            rel = p.relative_to(site).as_posix()
            t = p.read_text(encoding="utf-8", errors="replace")
            found = [("canonical", u) for u in
                     re.findall(r'<link rel="canonical" href="([^"]*)"', t)]
            found += [("og:url", u) for u in
                      re.findall(r'<meta property="og:url" content="([^"]*)"', t)]
            for block in re.findall(r'<dl class="citeforms">(.*?)</dl>', t, re.S):
                # shell.cite_url offers a break after each slash with <wbr>,
                # which is no character: the address is read without them.
                found += [("citation", u) for u in
                          at_base.findall(_html.unescape(_cite_plain(block)))]
            for ld in re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S):
                found += [("structured data", u) for u in at_base.findall(ld)]
            for what, u in found:
                seen[what] += 1
                if not u.startswith(want):
                    bad.append(f"{rel}: {what} {u}")
            if rel.startswith(("calendar", "session/")) and found:
                seen[rel.split("/")[0].replace(".html", "")] += 1
        assert not bad, (f"{len(bad)} addresses with no slash after {base}: "
                         + "; ".join(bad[:4]))
        # Silence is not success: a fixture with no calendar or sitting day
        # would pass this without having looked at the pages that broke.
        for need in ("calendar", "session", "citation", "structured data"):
            assert seen[need], f"the fixture site gave this check no {need} to read"

        # The current week at both its addresses, one page to index.
        # The week of the day that build ran on -- or, across a midnight that
        # ends a week, whichever of the two the calendar was written in.
        keys = [BC.week_key(d) for d in _fixture_site_shared()[3]]
        key = next((k for k in keys if (site / "calendar" / f"{k}.html").exists()), keys[0])
        copy = site / "calendar" / f"{key}.html"
        assert copy.exists(), (
            f"calendar/{key}.html was not written: the dated address of the "
            "current week is left to whatever an earlier build put there")
        ct = copy.read_text(encoding="utf-8", errors="replace")
        assert f'<link rel="canonical" href="{base}/calendar">' in ct, (
            f"calendar/{key}.html does not name /calendar as the page it copies")
        assert f'href="/calendar/{key}#results"' in ct, (
            f"calendar/{key}.html's skip link leaves the page it is on")
        sm = site / "sitemap.xml"
        text = sm.read_text(encoding="utf-8")
        locs = re.findall(r"<loc>([^<]*)</loc>", text)
        assert all(u.startswith(want) for u in locs), (
            "sitemap entries with no slash after the domain: "
            + ", ".join(u for u in locs if not u.startswith(want))[:200])
        assert f"<loc>{base}/calendar/{key}</loc>" not in text, (
            f"the sitemap lists calendar/{key}, a copy of /calendar")

        # Writers merge, and take out what they no longer write.
        stale = [base + "calendar", base + "/calendar/1999-W01",
                 base + "session/H/1999-01-05", base + "/session/H/1999-01-05"]
        other = base + "/session/S/1999-01-05"
        sm.write_text(text.replace("</urlset>", "".join(
            f"<url><loc>{u}</loc></url>\n" for u in stale + [other]) + "</urlset>"),
            encoding="utf-8")
        for script, args in (("build_session_pages.py", []), ("build_calendar.py", [])):
            r = _run([sys.executable, _paths.script(script), "--site", "site",
                      "--base", base, *args],
                     cwd=root, capture_output=True, text=True, timeout=180)
            assert r.returncode == 0, f"{script} rerun: " + (r.stderr or r.stdout)[-200:]
        after = sm.read_text(encoding="utf-8")
        left = [u for u in stale if f"<loc>{u}</loc>" in after]
        assert not left, "a rebuilt builder left its stale sitemap entries: " + ", ".join(left)
        assert f"<loc>{other}</loc>" in after, (
            "the House's sitting days took out a Senate entry it does not own")
        again = re.findall(r"<loc>([^<]*)</loc>", after)
        assert sorted(again) == sorted(locs + [other]), (
            "rebuilding the calendar and the sitting days changed sitemap entries "
            "they did not plant: "
            + ", ".join(sorted(set(again) ^ set(locs + [other])))[:200])
        return "ok", (f"{seen['canonical']} canonical links, {seen['citation']} citation "
                      f"addresses, {seen['structured data']} structured-data ids and "
                      f"{len(locs)} sitemap entries, all {want}...; the current week's "
                      "copy names /calendar, and stale entries are taken out")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# The reader, for _calendar_documents: the section's own script, run on the
# section a build wrote, in _calendar_in_a_dom's DOM (_CAL_DOM).
_CD_DRIVE = r"""const {makeWorld, runPage}=require("./minidom.js");
const fs=require("fs"), vm=require("vm"), path=require("path");
const SITE=process.argv[2], fails=[];
const ok=(c,m)=>{ if(!c) fails.push(m); };
const text=fs.readFileSync(path.join(SITE,"calendar.html"),"utf8");
const IX=JSON.parse(fs.readFileSync(path.join(SITE,"calendar","documents.json"),"utf8"));
// The page's two scripts: the Calendar's own, which _calendar_in_a_dom runs
// as the first after the results, and then the section's.
const r=text.indexOf('<div id="results">'), s1=text.indexOf("<script>",r), e1=text.indexOf("</script>",s1),
      s2=text.indexOf("<script>",e1), e2=text.indexOf("</script>",s2);
const a=text.indexOf('<section class="cdocs"'), e=text.indexOf("</section>",a)+10;
function world(files){
  const W=makeWorld({today:[2026,3,11], path:"/calendar", files});
  W.doc.body.innerHTML=text.slice(a,e);
  W.asked=[];
  // start() runs the section's script and returns before the list has come;
  // run() waits for it.
  W.start=()=>runPage(W,text,SITE,s2,text.slice(s2+8,e2));
  W.run=async()=>{ W.start(); await W.settle(); };
  W.$=(id)=>W.doc.getElementById(id);
  W.opts=(id)=>W.$(id).querySelectorAll("option").map(o=>o.textContent);
  W.choose=async(id,v)=>{ const s=W.$(id); s.value=v; s.dispatchEvent(W.ev("change")); await W.settle(); };
  return W;
}
const served=(url)=>url==="/calendar/documents.json"?JSON.stringify(IX):null;
const set=(id)=>IX.sets.find(s=>s.id===id);
const years=(id)=>Object.keys(set(id).years).sort().reverse();
const addr=(id,doc)=>/^https:/.test(doc[1])?doc[1]:IX.base[set(id).chamber]+doc[1];
(async()=>{
  ok(s1>0&&s2>e1&&a>0&&a<s1, "the page does not carry the section before the Calendar's script and the section's script after it");
  // ---- as written, before any script: links, and the row hidden ----
  const P=world(served), $=P.$;
  ok($("cdpick").hidden && !$("cdyears").hidden, "without script the pickers are shown, or the years are not");
  ok(P.opts("cdset").length===1 && P.opts("cdyear").length===1 && P.opts("cddoc").length===1
     && !$("cdset").disabled && !$("cdyear").disabled && !$("cddoc").disabled,
     "as written, the three pickers are not one choice each -- a kind could be chosen that nothing can follow until the list comes -- or are disabled, and Tab would pass them");
  const first=IX.sets.find(s=>Object.keys(s.years).length), y0=years(first.id)[0], d0=first.years[y0][0];
  ok($("cdopen").getAttribute("href")===addr(first.id,d0), "the button is not a link to the newest "+first.one+" as written");

  // ---- the list arrives ----
  await P.run();
  const C=P.win.GRDOCS;
  ok(!$("cdpick").hidden && $("cdyears").hidden, "with script the pickers did not take the years' place");
  ok(P.opts("cdset").join()===IX.sets.filter(s=>Object.keys(s.years).length).map(s=>s.name).join(), "the first picker offers "+P.opts("cdset"));
  ok($("cdset").value===first.id && $("cdyear").value===y0 && P.opts("cdyear").join()===years(first.id).join(),
     "it does not open on the first set's newest year: "+$("cdset").value+" "+$("cdyear").value+" of "+P.opts("cdyear"));
  ok(P.opts("cddoc").join("|")===first.years[y0].map(d=>d[0]).join("|"), "the documents offered are not that year's, in order: "+P.opts("cddoc").join("|"));
  ok($("cdopen").getAttribute("href")===addr(first.id,d0), "the button's address after the list came: "+$("cdopen").getAttribute("href"));
  ok($("cdopen").getAttribute("aria-label")==="Open the PDF: "+first.one+", "+d0[0]+", at the General Court" && $("cdopen").textContent==="Open the PDF",
     "the button's name does not begin with the words it shows and name the document: "+$("cdopen").getAttribute("aria-label"));
  // NOBODY ASKED: the list came because the section was near, so the live
  // region says nothing. It speaks once a picker is changed.
  ok($("cdstat").textContent==="", "the list arrived with nobody in the section and the status line, a live region, said: "+$("cdstat").textContent);
  ok($("cdnow").textContent===first.one+", "+d0[0], "the document chosen is not said whole under the pickers: "+$("cdnow").textContent);

  // ---- a year, then a document: the button follows, nothing else moves ----
  const y1=years("hc")[1];
  await P.choose("cdyear",y1);
  ok($("cdset").value==="hc" && $("cdyear").value===y1 && $("cddoc").value==="0"
     && $("cdopen").getAttribute("href")===addr("hc",set("hc").years[y1][0]), "choosing "+y1+" did not show its newest document");
  ok(new RegExp("^\\d+ House Calendars? for "+y1).test($("cdstat").textContent), "after a year was chosen the status line reads "+$("cdstat").textContent);
  await P.choose("cdyear",y0);
  await P.choose("cddoc","1");
  ok($("cdopen").getAttribute("href")===addr("hc",set("hc").years[y0][1]) && $("cddoc").value==="1", "choosing the second document did not move the button to it");
  ok($("cdnow").textContent==="House Calendar, "+set("hc").years[y0][1][0], "the document chosen, said whole, did not follow the picker: "+$("cdnow").textContent);
  ok(P.G.location.pathname==="/calendar" && P.hist.length===1, "a picker moved the page");

  // ---- another set keeps the year where it has it, and takes its newest where it has not ----
  await P.choose("cdset","sc");
  ok($("cdyear").value===y0 && P.opts("cdyear").join()===years("sc").join() && $("cddoc").value==="0"
     && $("cdopen").getAttribute("href")===addr("sc",set("sc").years[y0][0]), "Senate Calendars did not keep "+y0+": "+$("cdyear").value);
  await P.choose("cdset","hj");
  const lone=years("hj").find(y=>!set("sj").years[y]);
  ok(lone, "the fixture has no year the House journals have and the Senate's have not");
  await P.choose("cdyear",lone);
  ok($("cdopen").getAttribute("href")===addr("hj",set("hj").years[lone][0]), "House Journals of "+lone+": "+$("cdopen").getAttribute("href"));
  await P.choose("cdset","sj");
  const ys=years("sj");
  ok($("cdyear").value===ys[0] && $("cdopen").getAttribute("href")===addr("sj",set("sj").years[ys[0]][0]),
     "a year the set does not have did not fall back to its newest: "+$("cdyear").value);
  // Every address the pickers can reach is one the index holds whole.
  const held=new Set(IX.sets.flatMap(s=>Object.values(s.years).flat().map(d=>addr(s.id,d))));
  for(const s of IX.sets) for(const y of Object.keys(s.years)) s.years[y].forEach((d,i)=>{
    const st=C.state(IX,s.id,y,i); ok(st.href===addr(s.id,d) && held.has(st.href), "state() made an address for "+s.id+" "+y+" "+i+": "+st.href); });
  ok(C.state(IX,"nothing","1066",99).set.id===first.id, "a set the index does not have is not answered with the first");

  // ---- no link under the week's name down to the section (F11, 7 October 2026) ----
  ok(!/cdjump/.test(text), "the week's heading still links down to the Calendars & Journals");

  // ---- a reader in a picker while the list is on its way is told, and then told what came ----
  const A=world(served);
  A.start();
  ok(A.opts("cdset").length===1 && A.$("cdstat").textContent==="", "before the list has come the first picker offers more than the button opens, or the status line speaks");
  A.$("cdset").focus();
  ok(A.$("cdstat").textContent==="Loading the list of documents.", "a reader who reached a picker before the list did is told: "+A.$("cdstat").textContent);
  await A.settle();
  ok(/^\d+ House Calendars? for \d{4}/.test(A.$("cdstat").textContent) && A.opts("cdset").length===IX.sets.filter(s=>Object.keys(s.years).length).length,
     "and when it came: "+A.$("cdstat").textContent+" / "+A.opts("cdset"));
  // A link under the pickers is not a picker: reaching it brings the list and says nothing.
  const L=world(served);
  L.start();
  L.$("cdocs").querySelector(".cdlatest a").focus();
  ok(L.$("cdstat").textContent==="", "a focus on a link under the pickers wrote a line above it: "+L.$("cdstat").textContent);
  await L.settle();
  ok(L.opts("cdyear").length>1 && L.$("cdstat").textContent==="", "the list did not come for a reader at the links, or was announced to one who touched no picker");

  // ---- a list that will not load leaves the links; a reader who was in the pickers is told ----
  const F=world(()=>null);
  await F.run();
  ok(F.$("cdpick").hidden && !F.$("cdyears").hidden, "a failed fetch left the pickers up, or the years hidden");
  ok(F.$("cdstat").textContent==="", "a failed fetch nobody asked for says: "+F.$("cdstat").textContent);
  const F2=world(()=>null);
  F2.start();
  F2.$("cdyear").focus();
  await F2.settle();
  ok(F2.$("cdpick").hidden && !F2.$("cdyears").hidden && /could not be loaded/.test(F2.$("cdstat").textContent),
     "a reader in a picker when the list failed is told: "+F2.$("cdstat").textContent);
  const E=world((url)=>url==="/calendar/documents.json"?JSON.stringify({base:{},sets:[]}):null);
  await E.run();
  ok(E.$("cdpick").hidden && !E.$("cdyears").hidden, "an empty list left the pickers up");

  if(fails.length){ console.log(fails.join("\n")); process.exit(1); }
  console.log("OK");
})().catch(e=>{ console.log(e&&e.stack||e); process.exit(1); });
"""


@check("frontend", "the calendar's document picker links only addresses the General Court's own list gave, leaves out an address held back or in error, and works without script")
def _calendar_documents():
    """Calendars and journals as PDFs, under the Calendar page's schedule.

    Asked for on 1 October 2026: pickers in a row -- the kind, the year, the
    document -- and a button that opens the General Court's PDF. The page
    links the General Court's own addresses and hosts nothing, so what can go
    wrong is all about WHICH address, and whether there is one:

      - ONLY RECORDED ADDRESSES. A file's name follows no rule, and guessing
        at names is what got this project's address blocked. Every address in
        the index, the section and the list page is, byte for byte, one
        archive/queue.csv holds; the script's own state() cannot make another.
      - WHAT IS HELD BACK IS NOT LINKED: a withheld row, a row whose address
        answered with an error, a row with no address, and an address that
        is not the General Court's. The section says how many in one line;
        the list page names them. A night's new row, listed and not yet
        fetched, IS linked, and a row written twice is linked once.
      - THE PAGE SAYS ONLY WHAT THE RECORD HOLDS (the review of 1 October).
        "Not linked here", and how many were asked for, never that the
        General Court "does not serve" them: 42 of the 45 were never asked.
        "The newest listed here", not "the newest", of a list as old as the
        queue. The file's name, not "as the General Court names it". And a
        document is under the year of its date only where it has one; the
        page says how many have none.
      - TWO DOCUMENTS THAT SHARE ONE LOCAL FILE are both in the picker, each
        at its own address, and neither takes the date that file prints.
      - LABELS AND ORDER. A name is shown as the General Court wrote it; one
        that states no date gains the date its own text prints: a calendar's
        masthead, where it carries the document's own number and not a
        stray date above it, or a Senate journal's sitting -- one sitting's,
        never the first of a year's bound together. Newest first, an undated
        new number above the dated one before it.
      - ONCE, UNDER ITS OWN DATE'S YEAR: a December document filed under the
        next year is under its own, and one listed in two years is there
        once, at the address of its own year's list.
      - WITHOUT SCRIPT the section is the newest of each kind and every year
        as a link to the list page, the row of pickers hidden; the list page
        links every document. Both files survive month_files()'s pruning of
        calendar/data/ and the list page is in the sitemap after
        sitemap_merge has taken stale weeks out.
      - THE SCRIPT, in node on the page a build wrote: it opens where the
        General Court's does, a year and a set refill what follows them, a
        year the set does not have falls back to its newest, nothing moves
        the page, and a list that will not load leaves the links. Until the
        list comes each picker holds the one choice the button opens. The
        status line, a live region, speaks only to a reader who has reached
        a picker: not when the list arrives for a section that is merely
        near, which on a short week is as the page loads.
      - ONE ROW THAT FITS. The three pickers and the button are one row, and
        the row's minimums fit the schedule's column where it is narrowest:
        at 1024px, beside the month, less a scrollbar. As first written they
        needed 679px of a 652px row and the button stood 27px past its box,
        which only a browser showed. At 700px and under they stack, 44px tall
        with 16px text, so a phone does not zoom the page on focus.
      - THE DOCUMENT CHOSEN IS SAID WHOLE AT EVERY WIDTH, on a row of its own
        under the pickers: the document picker is 243px at 1024px and 346px
        at its widest, and a closed one cuts off the longer names -- about
        167 of the 4,320 at 1024px, measured in Chrome.
      - A LIST THAT OUGHT TO BE HERE AND IS NOT FAILS THE BUILD. A queue with
        a byte-order mark is read; one that is here and yields nothing, or
        is missing from a folder the kit filled, stops build_calendar before
        it writes anything, where it used to take the section off every week
        and exit zero.
    """
    import contextlib
    import datetime as _dt
    import html as _h
    import io
    import build_calendar as BC
    import calendar_documents as CD
    import shell as S
    if not Path("src/pages/bills.html").exists():
        return "skip", "bills.html is not here"
    # ---- the stylesheet: one row, and it fits ----
    css = _source("src/pages/app.css")
    at = css.find("/* THE GENERAL COURT'S OWN CALENDARS AND JOURNALS, AS PDFs")
    assert at > css.find("/* THE CALENDAR, AS A CALENDAR") > 0, (
        "app.css has no rules for the Calendars & Journals section in the calendar's region")
    mine = css[at:css.index("/* HOW THE DAY BEGAN.", at)]
    row = _braced(mine, ".cdpick{")
    cols = re.search(r"grid-template-columns:minmax\(([\d.]+)rem,1fr\) ([\d.]+)rem "
                     r"minmax\(([\d.]+)rem,2fr\) auto;", row)
    assert cols and "gap:var(--sp-4) var(--sp-5)" in row and "padding:var(--sp-6)" in row, (
        "the pickers are not one row of kind, year, document and the button, 12px apart "
        "in a 16px box")
    side = re.search(r"\.calapp\.on\{display:grid;grid-template-columns:clamp\((\d+)px", css)
    assert side, "the month's column has no width to take from the schedule's"
    # Open the PDF measured 131px in Chrome on 1 October 2026; 140 allows for
    # another face. Three 12px gaps, the box's 16px sides and its 1px edges.
    need = round(sum(float(x) for x in cols.groups()) * 16) + 140 + 3 * 12 + 2 * 16 + 2
    have = 1024 - 2 * 24 - 15 - int(side.group(1)) - 32
    assert need <= have, (
        f"the pickers' row needs {need}px and the schedule's column has {have}px at 1024px, "
        "beside the month: the button would stand past its box")
    stacked = _braced(mine, "@media (max-width:43.75em){")
    assert ".cdpick{grid-template-columns:minmax(0,1fr)" in stacked \
        and ".cdf select{min-height:44px;font-size:var(--t-ui)}" in stacked \
        and ".cdopen{min-height:44px}" in stacked \
        and ".cdnow,.cdopen{grid-column:auto;grid-row:auto}" in stacked, (
        "at 700px and under the pickers do not stack 44px tall with 16px text, with the "
        "document chosen said whole between them and the button")
    now = _braced(mine, ".cdnow{")
    assert "display:none" not in now and "grid-column:1 / -1" in now and "grid-row:2" in now \
        and ".cdopen{grid-column:4;grid-row:1}" in mine and not re.search(
            r"\.cdnow\{[^}]*display:none", mine), (
        "the document chosen is not said whole on a row of its own under the pickers at "
        "every width: a closed picker cuts a long name off at 1024px and at 1440px alike")
    assert need <= 701 - 2 * 12 - 15, (
        f"the row needs {need}px and a 701px screen, the narrowest it is one row on, has "
        f"{701 - 2 * 12 - 15}px")
    assert ".cdpick[hidden],.cdyears[hidden]{display:none}" in mine, (
        "the pickers have a display of their own and no rule that keeps them hidden "
        "without script")
    root = Path(tempfile.mkdtemp(prefix="gr-cdocs-"))
    try:
        H = "https://gc.nh.gov/house/calendars_journals/viewer.aspx?fileName="
        SN = "https://gc.nh.gov/senate/calendars_journals/viewer.aspx?fileName="
        apos = "SJ 07 February 14, 2023 - Governor&#39;s Budget Address.pdf"
        # chamber, kind, year, name, address, local file, state, attempts, error, fetched
        rows = [
            ("H", "calendar", "2026", "HC 33.pdf", H + "calendars%5C2026%5CHC%2033.pdf",
             r"calendars\2026\HC033.pdf", "wanted", "0", "", ""),
            ("H", "calendar", "2026", "HC 32.pdf", H + "calendars%5C2026%5CHC%2032.pdf",
             r"calendars\2026\HC032.pdf", "held", "0", "", ""),
            ("H", "calendar", "2026", "No30 August 14 2026.pdf",
             H + "calendars%5C2026%5CNo30%20August%2014%202026.pdf",
             r"calendars\2026\HC030.pdf", "held", "0", "", ""),
            ("H", "calendar", "2026", "HC 31.pdf", "https://example.org/HC31.pdf",
             r"calendars\2026\HC031.pdf", "held", "0", "", ""),
            ("H", "calendar", "2026", "No 02 December 12 2025.pdf",
             H + "calendars%5C2026%5CNo%2002%20December%2012%202025.pdf",
             r"calendars\2026\HC002.pdf", "held", "0", "", ""),
            ("H", "calendar", "2025", "No 51 November 21 2025.pdf",
             H + "calendars%5C2025%5CNo%2051%20November%2021%202025.pdf",
             r"calendars\2025\HC051.pdf", "held", "0", "", ""),
            ("H", "journal", "2010", "Daily Journal No 25 11-30-11 Final.pdf",
             H + "journals%5C2010%5CDaily%20Journal%20No%2025%2011-30-11%20Final.pdf",
             r"journals\2010\HJ025.pdf", "held", "0", "", ""),
            ("H", "journal", "2011", "Daily Journal No 25 11-30-11 Final.pdf",
             H + "journals%5C2011%5CDaily%20Journal%20No%2025%2011-30-11%20Final.pdf",
             r"journals\2011\HJ025.pdf", "held", "0", "", ""),
            ("H", "journal", "2026", "HJ 16 August 19, 2026.pdf",
             H + "journals%5C2026%5CHJ%2016%20August%2019%2C%202026.pdf",
             r"journals\2026\HJ 16 August 19, 2026.pdf", "held", "0", "", ""),
            ("S", "calendar", "2026", "SC 29.pdf", SN + "Calendars%5C2026%5CSC%2029.pdf",
             r"calendars_senate\2026\SC029.pdf", "held", "0", "", ""),
            ("S", "calendar", "2026", "No 28 August 20 2026.pdf",
             SN + "Calendars%5C2026%5CNo%2028%20August%2020%202026.pdf",
             r"calendars_senate\2026\SC028.pdf", "held", "0", "", ""),
            ("S", "calendar", "2008", "09B.pdf", SN + "Calendars%5C2008%5C09B.pdf",
             r"calendars_senate\2008\SC009B.pdf", "withheld", "2", "", ""),
            ("S", "calendar", "2007", "SC 24.pdf", SN + "Calendars%5C2007%5CSC%2024.pdf",
             r"calendars_senate\2007\SC024.pdf", "held", "0", "", ""),
            ("S", "calendar", "2007", "SC 24 (2).pdf", SN + "Calendars%5C2007%5CSC%2024%20(2).pdf",
             r"calendars_senate\2007\SC024.pdf", "held", "0", "", ""),
            ("S", "journal", "2023", apos,
             SN + "Journals%5C2023%5CSJ%2007%20February%2014%2C%202023%20-%20"
                  "Governor%26%2339%3Bs%20Budget%20Address.pdf",
             r"journals_senate\2023\SJ 07.pdf", "wanted", "1",
             "HTTPError: HTTP Error 500: Internal Server Error", ""),
            ("S", "journal", "2026", "SJ 15.pdf", SN + "Journals%5C2026%5CSJ%2015.pdf",
             r"journals_senate\2026\SJ 15.pdf", "held", "0", "", ""),
            ("S", "journal", "2026", "SJ 14 June 4, 2026.pdf",
             SN + "Journals%5C2026%5CSJ%2014%20June%204%2C%202026.pdf",
             r"journals_senate\2026\SJ 14 June 4, 2026.pdf", "held", "0", "", ""),
            ("S", "journal", "2018", "SPJ 2018 - Verbatim.pdf",
             SN + "Journals%5C2018%5CSPJ%202018%20-%20Verbatim.pdf",
             r"journals_senate\2018\SPJ 2018 - Verbatim.pdf", "held", "0", "", ""),
            ("S", "calendar", "2010", "43.pdf", SN + "Calendars%5C2010%5C43.pdf",
             r"calendars_senate\2010\SC043.pdf", "held", "0", "", ""),
            ("S", "calendar", "2008", "44.pdf", SN + "Calendars%5C2008%5C44.pdf",
             r"calendars_senate\2008\SC044.pdf", "held", "0", "", ""),
            # The same row again, as a queue written twice would hold it: one
            # address is one document, and it has no date to be told apart by.
            ("S", "calendar", "2008", "44.pdf", SN + "Calendars%5C2008%5C44.pdf",
             r"calendars_senate\2008\SC044.pdf", "held", "0", "", ""),
            # A row with no address: not linked, and never asked for.
            ("H", "journal", "2026", "HJ 17.pdf", "",
             r"journals\2026\HJ 17.pdf", "wanted", "0", "", ""),
        ]
        q = root / "queue.csv"
        with q.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["chamber", "kind", "year", "name", "url", "path", "state",
                        "attempts", "error", "bytes", "fetched"])
            for r in rows:
                w.writerow(list(r[:9]) + ["1", r[9]])
        # The text beside seven of the PDFs, as extract_calendar_text leaves
        # it: a House masthead, a Senate one, the one file two listed
        # documents share, a Senate journal's sitting, a year's sittings
        # bound as one journal, a Senate calendar that opens with a stray
        # date above its masthead (as 82 of 2010's do), and one whose
        # masthead carries another issue's number (2008's "44" prints No. 1).
        for rel, text in (
                ("calendars/2026/HC032.txt",
                 "HOUSE RECORD\nVol. 48      Concord, N.H.      Friday, September 4, 2026"
                 "      No. 32\n"),
                ("calendars_senate/2026/SC029.txt",
                 "                                        September 3, 2026\n"
                 "                                        No. 29\nSENATE CALENDAR\n"),
                ("calendars_senate/2007/SC024.txt",
                 "                                        June 7, 2007\n"
                 "                                        No. 24\nSENATE CALENDAR\n"),
                ("journals_senate/2026/SJ 15.txt",
                 "SENATE JOURNAL 15\n\nThe Senate met at 10:00 a.m.          August 19, 2026\n"
                 "The Chaplain offered the prayer.\n"),
                ("journals_senate/2018/SPJ 2018 - Verbatim.txt",
                 "The Senate met at 10:00 a.m.          January 3, 2018\nThe prayer.\n\n"
                 "The Senate met at 10:00 a.m.          January 18, 2018\nThe prayer.\n"),
                ("calendars_senate/2010/SC043.txt",
                 "April 29, 2010\n"
                 "                                        November 23, 2010\n"
                 "                                        No. 43\nSENATE CALENDAR\n"),
                ("calendars_senate/2008/SC044.txt",
                 "                                        December 4, 2008\n"
                 "                                        No. 1\nSENATE CALENDAR\n")):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
        today = _dt.date(2026, 10, 1)
        docs, left = CD.read(q, root=root, today=today)
        recorded = {r[4] for r in rows if r[4]}
        # A QUEUE SAVED WITH A BYTE-ORDER MARK IS THE SAME QUEUE. Read as plain
        # UTF-8 its first column was not "chamber", nothing was linked, and
        # the section left every week's page.
        bom = root / "queue_bom.csv"
        bom.write_bytes(b"\xef\xbb\xbf" + q.read_bytes())
        assert CD.read(bom, root=root, today=today) == (docs, left) and docs, (
            "a queue with a byte-order mark is not read as the same queue")
        assert CD.rows(root / "no_such_queue.csv") == []

        # ---- what is linked, and what is not ----
        by = CD.by_set(docs)
        got = {sid: {y: [d.label for d in ds] for y, ds in ys.items()} for sid, ys in by.items()}
        dash = "—"
        want = {
            "hc": {"2026": ["HC 33", f"HC 32 {dash} September 4, 2026", "No30 August 14 2026"],
                   "2025": ["No 02 December 12 2025", "No 51 November 21 2025"]},
            "hj": {"2026": ["HJ 16 August 19, 2026"],
                   "2011": ["Daily Journal No 25 11-30-11 Final"]},
            "sc": {"2026": [f"SC 29 {dash} September 3, 2026", "No 28 August 20 2026"],
                   "2010": [f"43 {dash} November 23, 2010"], "2008": ["44"],
                   "2007": ["SC 24", "SC 24 (2)"]},
            "sj": {"2026": [f"SJ 15 {dash} August 19, 2026", "SJ 14 June 4, 2026"],
                   "2018": ["SPJ 2018 - Verbatim"]},
        }
        assert got == want, f"the picker's sets, years, labels and order read as {got}"
        assert [list(v) for v in got.values()] == [list(v) for v in want.values()], (
            "a set's years are not newest first")
        assert all(d.url in recorded and d.url.startswith("https://gc.nh.gov/") for d in docs), (
            "a document is linked at an address the queue does not hold")
        assert len({d.url for d in docs}) == len(docs), "two documents share one address"
        twice = [d for d in docs if d.name.startswith("Daily Journal No 25")]
        assert len(twice) == 1 and "journals%5C2011%5C" in twice[0].url, (
            "a document listed under two years is not shown once, at its own year's address")
        pair = by["sc"]["2007"]
        assert not any(d.date for d in pair) and pair[0].url != pair[1].url, (
            "two documents sharing one local file took that file's date, or one address")
        # NOT LINKED, AND WHETHER IT WAS EVER ASKED FOR: the last of each.
        assert sorted(left) == [("hc", "2026", "HC 31", False), ("hj", "2026", "HJ 17", False),
                                ("sc", "2008", "09B", True),
                                ("sj", "2023", _h.unescape(apos[:-4]), True)], (
            f"left out: {left}")
        assert CD.left_out_line(left) == ("4 documents the General Court lists are not "
                                         "linked here."), CD.left_out_line(left)
        assert CD.left_out_line(left[:1]) == ("1 document the General Court lists is not "
                                             "linked here.") and CD.left_out_line([]) == ""
        assert CD.left_out_why(left) == (
            "Of these, 2 answered with an error when this site asked for them and 2 were "
            "set aside without being asked for."), CD.left_out_why(left)
        asked_, not_ = [o for o in left if o.asked], [o for o in left if not o.asked]
        assert CD.left_out_why(asked_[:1]) == "It answered with an error when this site asked for it." \
            and CD.left_out_why(asked_) == "Each answered with an error when this site asked for it." \
            and CD.left_out_why(not_[:1]) == "It was set aside without being asked for." \
            and CD.left_out_why(not_) == "They were set aside without being asked for." \
            and CD.left_out_why([]) == "", "what is said of the documents not linked"
        said = " ".join((CD.left_out_line(left), CD.left_out_why(left), CD.block_html(docs, left),
                         " ".join(CD.list_body(docs, left)))).lower()
        for claim in ("does not serve", "not served", "unserved", "as the general court names"):
            assert claim not in said, (
                f"the page says {claim!r}, which the queue does not bear out: 42 of the 45 "
                "documents left out on 1 October were never asked for, and the newest "
                "document's file name is not the General Court's label for it")
        for name, iso in (("No 32 September 4 2026", "2026-09-04"),
                          ("No13aFebruary 21 2025", "2025-02-21"),
                          ("No 18 March31 2023", "2023-03-31"),
                          ("No 17 February 29 (AMENDMENTS) 2008", "2008-02-29"),
                          ("No 22 March 27 and 28 2007 Amendments", "2007-03-27"),
                          ("HJ No 25 06-25-1997", "1997-06-25"),
                          ("Daily Journal No 2 1-7-09-Convening Day Final", "2009-01-07"),
                          ("Daily Journal No 25 11-30-11 Final", "2011-11-30"),
                          ("SJ 14 June 4, 2026", "2026-06-04"),
                          ("No 01 January 04 1012", ""), ("SJ 16 May 8, 208", ""),
                          ("No 41 Octobet 26 2023", ""), ("No 100 1997", ""), ("HC 32", ""),
                          ("No 19-19A April 26 2018 - Combined", "2018-04-26")):
            assert CD.name_date(name, 2027) == iso, (
                f"{name!r} states {CD.name_date(name, 2027) or 'no date'}, not {iso or 'none'}")

        # ---- a file's other suffixes leave its label, never its address ----
        for name, label in (("SC 36.tagged.pdf", "SC 36"),
                            ("Daily Journal No 22 9-5-07 Veto Day Final.doc.pdf",
                             "Daily Journal No 22 9-5-07 Veto Day Final"),
                            ("HC 33.DOCX.pdf", "HC 33"), ("No30 August 14 2026.pdf", "No30 August 14 2026"),
                            ("hb0001_final.pdf", "hb0001_final"), ("63", "63"),
                            ("Tagged.pdf", "Tagged"), ("SC 36.tagged", "SC 36.tagged")):
            assert CD.clean(name) == label, f"{name!r} is labelled {CD.clean(name)!r}, not {label!r}"
        assert CD.number_of("SC 36.tagged.pdf") == CD.number_of("SC 36.pdf"), (
            "SC 36.tagged is numbered apart from SC 36")
        tagged = docs[0]._replace(label=CD.clean("SC 36.tagged.pdf"),
                                  url=docs[0].url.rsplit("%5C", 1)[0] + "%5CSC%2036.tagged.pdf")
        t_ix = CD.index([tagged])
        t_doc = t_ix["sets"][0]["years"][next(iter(t_ix["sets"][0]["years"]))][0]
        assert t_doc[0] == "SC 36" and CD.address(t_ix, CD.CHAMBER[tagged.set], t_doc) == tagged.url, (
            f"SC 36.tagged is listed as {t_doc[:2]}, not 'SC 36' at its recorded address")

        # ---- the index: every address whole, and none made ----
        ix = CD.index(docs)
        assert ix["base"] == {"H": H, "S": SN}, f"the viewer prefixes read as {ix['base']}"
        assert sorted(ix) == ["base", "sets"], (
            f"the index holds {sorted(ix)}: a date of its making makes it a new file every "
            "day, for the deploy to send again unchanged")
        flat = [(s["chamber"], d) for s in ix["sets"] for ds in s["years"].values() for d in ds]
        assert not [d[0] for _ch, d in flat if re.search(r"(?i)\.(?:pdf|tagged|docx?)$", d[0])], (
            "a label still ends in a file's suffix: "
            + ", ".join(d[0] for _ch, d in flat if re.search(r"(?i)\.(?:pdf|tagged|docx?)$", d[0])))
        assert len(flat) == len(docs) and {CD.address(ix, ch, d) for ch, d in flat} == \
            {d.url for d in docs}, "the index's addresses are not the documents' own"
        assert all(not d[1].startswith("https://") and "%5C" in d[1] for _ch, d in flat), (
            "the index does not store each address as the part after its chamber's prefix")
        assert [s["id"] for s in ix["sets"]] == ["hc", "hj", "sc", "sj"] and \
            [s["name"] for s in ix["sets"]] == ["House Calendars", "House Journals",
                                               "Senate Calendars", "Senate Journals"], (
            "the first picker's four kinds are not the four asked for, in order")
        odd = CD.index([docs[0]._replace(url="https://gc.nh.gov/house/elsewhere/HC33.pdf")]
                       + docs[1:])
        assert CD.address(odd, "H", odd["sets"][0]["years"]["2026"][0]) == \
            "https://gc.nh.gov/house/elsewhere/HC33.pdf", (
            "an address that does not begin with its chamber's prefix is not kept whole")

        # ---- the section and the list page, as markup ----
        # ---- the list's age: told from the newest listed, where it has a date ----
        assert CD.newest(docs, "hc").name == "HC 33" and CD.newest_date(docs, "hc") == "2026-09-04" \
            and CD.newest_date(docs) == "2026-09-04" and CD.newest([], "hc") is None
        assert CD.behind(docs, today, BC.CD_STALE_DAYS) is None, (
            "a list whose newest House Calendar has no date yet is called behind: a night's "
            "new short name would warn on every run")
        dated = [d for d in docs if d.name != "HC 33"]
        assert CD.behind(dated, today, BC.CD_STALE_DAYS) == ("2026-09-04", 27) \
            and CD.behind(dated, _dt.date(2026, 9, 20), BC.CD_STALE_DAYS) is None \
            and CD.behind([], today, BC.CD_STALE_DAYS) is None, (
            "a list whose newest House Calendar is 27 days old is not called behind, or one "
            "16 days old is")

        # ---- a list that ought to be here and is not is a failed build ----
        assert BC.documents_problem(docs, queue=q) == ""
        assert "no calendar or journal could be read" in BC.documents_problem([], queue=q), (
            "a queue that is on disk and yields nothing does not fail the build")
        gone = root / "no_such_queue.csv"
        assert BC.documents_problem([], queue=gone, kit=False) == "", (
            "a bare folder with no queue cannot be built at all")
        assert "filled from the kit" in BC.documents_problem([], queue=gone, kit=True), (
            "a folder the kit filled, without the queue the kit carries, does not fail the build")
        kit = Path("cloud_kit.json")
        assert not kit.exists() or '"archive/queue.csv"' in _source(kit), (
            "cloud_kit.json no longer carries archive/queue.csv, which the pickers are built from")

        block = CD.block_html(docs, left)
        assert CD.block_html([], []) == "", "a section is drawn with nothing to link"
        hrefs = re.findall(r'href="([^"]*)"', block)
        out = [_h.unescape(h) for h in hrefs if not h.startswith("/calendar/documents")]
        assert out and all(h in recorded for h in out), (
            f"the section links an address the queue does not hold: {out}")
        assert block.count('<section class="cdocs" id="cdocs"') == 1 \
            and '<form class="cdpick" id="cdpick" hidden>' in block, (
            "the section is not one section whose pickers are emitted hidden")
        assert block.count('aria-labelledby="cdhead"') == 1, (
            "the form is named by the section's heading too: two landmarks with one name")
        assert block.count("<option") == 3 and '<option value="hc" selected>House Calendars</option>' \
            in block, ("as written the pickers offer more than the one document the button "
                       "opens: a kind chosen before the list comes cannot be followed")
        assert '<h3 class="cdsub" id="cdnew">The newest listed here</h3>' in block, (
            "the four links are not headed as the newest LISTED: the list is as old as the "
            "queue, and on 1 October its newest House Calendar was 27 days old")
        # A CALENDAR OR JOURNAL OPENS IN A NEW TAB, marked as going out (the
        # person, 7 October 2026, F12): the newest listed, the picker's button
        # and every document on the list page.
        assert not hasattr(CD, "jump_html"), (
            "calendar_documents still writes the link down from the week's name (F11)")
        listed_page = " ".join(CD.list_body(docs, left))
        to_docs = []
        for m in re.finditer(r'<a [^>]*>', block + listed_page):
            h = re.search(r'href="([^"]*)"', m.group(0))
            if h and _h.unescape(h.group(1)) in recorded:
                to_docs.append(m.group(0))
        assert to_docs, "the section and the list page link no document"
        bare = [a for a in to_docs if not ('target="_blank"' in a and 'rel="noopener"' in a
                                           and re.search(r'class="(?:[^"]* )?out\b', a))]
        assert not bare, (f"{len(bare)} of {len(to_docs)} links to a calendar or journal open "
                          f"in the same tab or carry no outside-link mark: {bare[:2]}")
        # A session day's page links its own journal the same way.
        sp = _source(_paths.locate("build_session_pages.py"))
        jl = re.search(r'<a class="jpdf[^"]*"[^>]*>', sp)
        assert jl and 'target="_blank"' in jl.group(0) and 'rel="noopener"' in jl.group(0) \
            and re.search(r'class="(?:[^"]* )?out\b', jl.group(0)), (
            "a session day's journal PDF opens in the same tab or carries no outside-link "
            f"mark: {jl.group(0) if jl else 'no jpdf link'}")
        for sid, label, url in (("hc", "HC 33", rows[0][4]),
                                ("hj", "HJ 16 August 19, 2026", rows[8][4]),
                                ("sc", f"SC 29 {dash} September 3, 2026", rows[9][4]),
                                ("sj", f"SJ 15 {dash} August 19, 2026", rows[15][4])):
            assert (f'<span class="cdset">{CD.ONE[sid]}</span> <a class="out" '
                    f'href="{_h.escape(url)}" target="_blank" rel="noopener">'
                    f'{_h.escape(label)} (PDF)</a>') in block, (
                f"the newest {CD.ONE[sid]} is not a link in the section that opens a new tab")
        for sid, ys in want.items():
            for y in ys:
                assert f'<a href="/calendar/documents#{sid}-{y}">{y}</a>' in block, (
                    f"without script there is no link to {CD.MANY[sid]} of {y}")
        # BOTH OPEN A NEW TAB NOW (F12, 7 October 2026): the section, and the
        # cards' links to the same PDFs (_calendar_document_links).
        assert 'target="_blank"' in block, (
            "the section opens a PDF in the same tab; the cards' links to the same PDFs do not")
        assert '<p class="cdleft">4 documents the General Court lists are not linked here.</p>' in block
        for i, lab in (("cdset", "Calendar or journal"), ("cdyear", "Year"), ("cddoc", "Document")):
            assert f'<label for="{i}">{lab}</label><select id="{i}">' in block, (
                f"the {lab} picker has no visible label of its own")
        heading, lead, body = CD.list_body(docs, left)
        assert body.count(' rel="noopener">') == len(docs) and all(
            f'href="{_h.escape(d.url)}"' in body for d in docs), (
            "the list page does not link every document once")
        notlinked = body.split('<h2 id="notlinked">Listed by the General Court and not linked here')
        assert len(notlinked) == 2, "the list page has no section for what is not linked"
        for name in ("09B", "HC 31", "HJ 17", "Governor&#x27;s Budget Address",
                     "Of these, 2 answered with an error when this site asked for them and 2 "
                     "were set aside without being asked for."):
            assert name in notlinked[1], f"the list page does not say {name!r} of what is not linked"
        # What the list page says of itself: the name, the year and how far it reaches.
        undated = sum(1 for d in docs if not d.date)
        assert undated == 5, f"{undated} of the fixture's documents have no date"
        assert lead.startswith("16 documents, 2007 to 2026, each a link to the General "
                               "Court&rsquo;s own file, under that file&rsquo;s name."), lead[:120]
        assert ("Each is under the year of its date, newest first; the 5 with no date known "
                "are under the year the General Court lists them for.") in lead, (
            "the list page says a document is under the year of its date and does not say "
            "how many have no date and are under the General Court's list year")
        assert CD.sources(docs) == [("House", "https://gc.nh.gov/house/calendars_journals/"),
                                    ("Senate", "https://gc.nh.gov/senate/calendars_journals/")] \
            and all(any(u.startswith(page) for u in recorded) for _n, page in CD.sources(docs)), (
            "the General Court's own pages are not the folders its recorded addresses are in")
        assert ("The latest date on a document here is September 4, 2026; anything published "
                "since is on the General Court&rsquo;s own pages for "
                '<a href="https://gc.nh.gov/house/calendars_journals/" rel="noopener">the House</a> '
                'and <a href="https://gc.nh.gov/senate/calendars_journals/" rel="noopener">'
                "the Senate</a>.") in lead, (
            "the list page does not say how far the list reaches and where a newer document is")
        assert "no date known" not in CD.list_lead([d for d in docs if d.date]), (
            "a list whose every document has a date speaks of ones that have none")
        assert body.startswith('<p class="src"><a href="/calendar/documents#hc">House Calendars</a>'
                               ' &middot; <a href="/calendar/documents#hj">House Journals</a>') \
            and "/calendar/documents#" not in lead, (
            "the links down to the four kinds are not a line of their own under the lead: "
            "at its end they ran on from its links out to the General Court's pages")
        assert body.count("<details") == sum(len(v) for v in want.values()) \
            and body.count("<details class=\"cdyear\" id=") == body.count("<details") \
            and body.count(" open>") == 4, "a year is not a <details>, the newest of each set open"

        # ---- a build: the pages, the two files, the sitemap ----
        site = root / "site"
        site.mkdir()
        shutil.copy(Path("src/pages/bills.html"), site / "bills.html")
        (site / "components.js").write_text(_components_js(), encoding="utf-8", newline="\n")
        base = "https://graniterecord.org"
        (site / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset>\n'
            f"<url><loc>{base}/calendar/1999-W01</loc></url>\n</urlset>\n", encoding="utf-8")
        cal_today = _dt.date(*CAL_TODAY)
        weeks = BC.weeks_from(_cal_rows(), names={})
        BC.every_week(weeks, cal_today)
        order = sorted(weeks)
        urls = []
        with contextlib.redirect_stdout(io.StringIO()):
            for i, k in enumerate(order):
                BC.week_page(site, base, k, weeks, order, i, {}, {}, {}, urls, cal_today,
                             set(), study=True, picker=block)
            size = BC.documents_files(site, base, docs, left, urls)
            BC.month_files(site, weeks, order, {}, {}, {}, cal_today)
        S.sitemap_merge(site, base, urls, "/calendar")
        assert size and (site / "calendar" / "documents.json").is_file(), (
            "calendar/documents.json is not beside the week pages after month_files() "
            "pruned calendar/data/")
        assert json.loads((site / "calendar" / "documents.json").read_text(
            encoding="utf-8")) == json.loads(json.dumps(ix)), (
            "calendar/documents.json is not the index")
        sm = (site / "sitemap.xml").read_text(encoding="utf-8")
        assert f"<loc>{base}/calendar/documents</loc>" in sm and "1999-W01" not in sm \
            and "documents.json" not in sm, (
            "the list page is not in the sitemap after the stale weeks came out, or the "
            "index went in")
        here = BC.week_key(cal_today)
        pages = {"calendar.html": "/calendar", f"calendar/{here}.html": f"/calendar/{here}",
                 f"calendar/{order[0]}.html": f"/calendar/{order[0]}"}
        for f, addr in pages.items():
            t = (site / f).read_text(encoding="utf-8")
            assert t.count('<section class="cdocs" id="cdocs"') == 1 and block in t, (
                f"{f} does not carry the section once, as written")
            main_ = t[t.index('<div class="calmain">'):]
            assert main_.index('class="calend"') < main_.index('<section class="cdocs"') \
                < main_.index('id="calpeek"'), f"{f}: the section is not under the schedule's arrows"
            # NO SUMMARY AND NO LINK DOWN UNDER THE WEEK'S NAME (the person, 7
            # October 2026, F11): the PDFs are the last block of the column.
            head = t[t.index('<div class="calhead">'):t.index('<div class="calside"')]
            assert "cdjump" not in head and "as PDFs" not in head \
                and "appears once a day" not in head and " sittings on " not in head, (
                f"{f}: the week's heading still carries the summary or the link down: {head[:300]}")
            # CITE THIS PAGE UNDER THE WEEK'S LINE (the audit of 25 October
            # 2026, S9), once, not alone above the heading; naming the week
            # at the address both copies of this week name as theirs.
            cite = head.find('<div class="pageacts" id="pageacts">')
            assert t.count('class="pcite"') == 1 and \
                head.find('<p class="src">') < cite < head.find('<nav class="wknav"'), (
                f"{f}: Cite this page is not under the week's line, once, above its arrows")
            canon = re.search(r'<link rel="canonical" href="([^"]+)"', t).group(1)
            assert canon in _cite_plain(head[cite:]), (
                f"{f}: the citation does not name the week at {canon}")
        lp = (site / "calendar" / "documents.html").read_text(encoding="utf-8")
        assert body in lp and f'<link rel="canonical" href="{base}/calendar/documents">' in lp \
            and "<h1>Calendars and Journals of the General Court</h1>" in lp, (
            "the list page was not written with its body, its heading and its own address")
        assert lp.count('class="pcite"') == 1 and lp.find(lead) < lp.find(
            '<div class="pageacts" id="pageacts">') < lp.find(body), (
            "the list page's Cite this page is not under its line, once")
        bare = (root / "bare")
        bare.mkdir()
        shutil.copy(Path("src/pages/bills.html"), bare / "bills.html")
        with contextlib.redirect_stdout(io.StringIO()):
            BC.week_page(bare, base, order[0], weeks, order, 0, {}, {}, {}, [], cal_today,
                         set(), study=True)
            assert BC.documents_files(bare, base, [], [], []) == 0
        t = (bare / "calendar" / f"{order[0]}.html").read_text(encoding="utf-8")
        assert "cdocs" not in t and "cdjump" not in t and t.count("<script>(function(){") == 1 \
            and not (bare / "calendar" / "documents.html").exists(), (
            "a build with no list still draws the section, its link or its script")

        # ---- the script, on that page ----
        node = _cal_node()
        if not node:
            return "ok", (f"{len(docs)} documents linked at recorded addresses, {len(left)} "
                          "left out and named; node is not on PATH, so the script was not run")
        (root / "minidom.js").write_text(_CAL_DOM, encoding="utf-8")
        (root / "drive.js").write_text(_CD_DRIVE, encoding="utf-8")
        r = _run([node, str(root / "drive.js"), str(site)], capture_output=True, text=True,
                 timeout=120)
        said = ((r.stdout or "") + (r.stderr or "")).strip()
        assert r.returncode == 0 and said.endswith("OK"), said[-1500:]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", (f"{len(docs)} documents linked at recorded addresses, each once under its "
                  f"own year; {len(left)} left out and named; the pickers run on the page a "
                  "build wrote")


@check("build", "the listing of calendars and journals takes each index page at its own word: "
       "four requests, the page's own folder and names, nothing built from a pattern, and "
       "nothing at all from a page that has changed shape or an address that says no",
       needs=("fetch_calendar_archive",))
def _documents_listing(CA):
    """fetch_calendar_archive.py --listing, which GitHub's night runs so that
    the Calendar page's picker is not weeks behind: the queue was last read
    on 13 September, and on 1 October House Calendar No 35 was not in it.

    Driven on the saved Senate pages and their House twins (the block's
    header says which is which), through a get() that answers as the page
    does. No request leaves here.

      - the saved pages read as they were served: kind, year, 39 and 63
        documents, the selected one, and the link's folder and file;
      - an ordinary night is four requests, a GET and one postback a
        chamber, each postback carrying the page's own hidden state and one
        change, LISTING_PAUSE apart and as long before the first; what is
        new is added in the page's
        order with the General Court's label, at the viewer address made of
        the page's own folder and the page's own name -- SC 29's is the one
        the laptop recorded; a name's entities are read; nothing on file
        moves, and a row on file gains its label;
      - at the turn of a year it is eight, whichever way the page answers a
        change of kind, and never more; a new year's journal list that the
        page answers with HTTP 500 is taken as none posted yet, and written
        down as unanswered, only where it is the chamber's last list, none
        is on file for it and the year's calendars were read -- and a 500
        to any other list, a dropped connection or a refusal stops the read
        as before;
      - a page whose link names another year, that shows a list nobody asked
        for, that marks nothing selected, or that has no link, stops the read
        with nothing written; so do a request that fails, a budget spent and
        a lost lock; a 403 or the firewall's page is recorded as a refusal;
      - judge() refuses a list that came back short or empty, one not read,
        an older year only, a lost or moved row, and an address the page did
        not give; and lets through one document gone and a new year's empty
        list. Short is counted against what the page listed when it was last
        installed, so a document gone on an earlier night is not counted
        again, and the limit is pinned on both sides: two of twenty and
        three of thirty pass, three of twenty and four of thirty do not, and
        of four it is the second that stops it;
      - main(): --out writes the queue and the listing and installs nothing;
        without it the list is judged and installed, or left alone; with a
        refusal standing, or on a laptop that has stood down, --listing and
        --discover stop before any request; and there the drain writes its
        own file and never the night's.
    """
    import contextlib
    import datetime
    import http.client
    import io
    import time
    import types
    import urllib.error
    import urllib.parse
    import refusal
    pages, rows = _docs_fixture(CA)
    saved = (refusal.MARK, refusal.LOCK, refusal.STANDDOWN, CA.ROOT, CA.QUEUE, CA._get,
             CA.time, CA.today, sys.argv)
    saved_env = os.environ.get("GITHUB_ACTIONS")
    tmp = Path(tempfile.mkdtemp(prefix="gr-listing-"))
    asked, slept, paused_at = [], [], []
    clock = {"jump": 0.0}

    def server(pages, fail=None, leaves_year=False, newest="2026"):
        def get(url, data=None, timeout=60):
            ch = "H" if "/house/" in url else "S"
            f = dict(urllib.parse.parse_qsl((data or b"").decode(), keep_blank_values=True))
            kind, year, target = "calendar", newest, ""
            if data is not None:
                assert f.get("__VIEWSTATE") and f.get("__EVENTVALIDATION") and \
                    f.get("__EVENTARGUMENT") == "", "a postback without the page's own state"
                kind = "journal" if "Journal" in f[CA.SEL_KIND] else "calendar"
                target = f["__EVENTTARGET"]
                # The page has been seen to leave the year behind when the
                # kind changes (fetch_journals.py): answered both ways.
                year = newest if leaves_year and target == CA.SEL_KIND else f[CA.SEL_YEAR]
            asked.append((ch, "GET" if data is None else "POST", kind, year,
                          target.rsplit("$", 1)[-1]))
            a = (fail or {}).get(len(asked))
            if isinstance(a, BaseException):
                raise a
            return a if isinstance(a, bytes) else pages[f"{ch} {kind} {year}"].encode("utf-8")
        return get

    class Held:
        ok = True

        def still(self):
            return self.ok

    def read(pages, day=(2026, 10, 2), held=None, on_file=None, **kw):
        del asked[:], slept[:], paused_at[:]
        clock["jump"] = 0.0
        CA._get = server(pages, **kw)
        with contextlib.redirect_stdout(io.StringIO()):
            return CA.listing(held or Held(), day=datetime.date(*day), on_file=on_file)

    def stops(pages, **kw):
        try:
            read(pages, **kw)
        except CA.Stop as e:
            return e.code, e.why
        return None, "it read every list"

    def main(*argv):
        del asked[:], slept[:], paused_at[:]
        sys.argv = ["fetch_calendar_archive.py", *argv]
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                rc = CA.main()
            except SystemExit as e:
                rc = e.code
        return rc, out.getvalue()

    try:
        refusal.MARK, refusal.LOCK = tmp / "archive" / "refused.json", tmp / "archive" / ".lock"
        refusal.STANDDOWN = tmp / "archive" / "runs-in-the-cloud.json"
        CA.ROOT, CA.QUEUE = tmp / "archive", tmp / "archive" / "queue.csv"
        os.environ.pop("GITHUB_ACTIONS", None)
        # Each pause is written down with how many requests had been made
        # when it was taken: `paused_at`.
        CA.time = types.SimpleNamespace(
            sleep=lambda s: (slept.append(s), paused_at.append(len(asked))),
            strftime=time.strftime, time=lambda: time.time() + clock["jump"])
        CA.today = lambda: datetime.date(2026, 10, 2)

        # The saved pages, as served.
        st = CA.shown(pages["S calendar 2026"])
        assert (st["kind"], st["year"], len(st["docs"]), st["doc"], st["link"]) == (
            "SenateCalendar", "2026", 39, "SC 29.pdf", "Calendars\\2026\\SC 29.pdf"), st
        assert st["docs"][0] == ("SC 29.pdf", "No 29 September 3 2026") and \
            st["years"][0] == "2026" and st["years"][-1] == "1998", (st["docs"][0], st["years"])
        st = CA.shown(pages["S calendar 2025"])
        assert (st["kind"], st["year"], len(st["docs"]), st["doc"], st["link"]) == (
            "SenateCalendar", "2025", 63, "No 48 December 30 2025.pdf",
            "Calendars\\2025\\No 48 December 30 2025.pdf"), st

        # An ordinary night: four requests, paced, one change each.
        lists, n = read(pages)
        assert n == 4 and asked == [
            ("H", "GET", "calendar", "2026", ""), ("H", "POST", "journal", "2026", "ddlCalJourn"),
            ("S", "GET", "calendar", "2026", ""), ("S", "POST", "journal", "2026", "ddlCalJourn")], asked
        assert len(slept) == 4 and all(
            0.85 * CA.LISTING_PAUSE <= s <= 1.15 * CA.LISTING_PAUSE for s in slept) and \
            CA.LISTING_PAUSE >= 4, f"the listing's requests were {slept} seconds apart"
        # A pause before each request, the first as well: the night asks this
        # address for the bill requests a moment before the listing starts.
        assert paused_at == [0, 1, 2, 3], (
            "the listing did not pause before each of its requests, the first among them: "
            f"its pauses came after {paused_at} requests")
        assert [(li["chamber"], li["kind"], li["year"], li["directory"], len(li["documents"]))
                for li in lists] == [
            ("H", "calendar", "2026", "calendars\\2026\\", 7),
            ("H", "journal", "2026", "journals\\2026\\", 2),
            ("S", "calendar", "2026", "Calendars\\2026\\", 39),
            ("S", "journal", "2026", "Journals\\2026\\", 2)], lists
        new, added = CA.merged(rows, lists)
        rec = {"read": "2026-10-02T04:20:00", "requests": n, "lists": lists}
        assert CA.judge(rows, new, rec) == "", CA.judge(rows, new, rec)
        assert [(r["chamber"], r["kind"], r["name"], r["label"], r["state"]) for r in added] == [
            ("H", "calendar", "HC 35.pdf", "No 35 September 25 2026", "wanted"),
            ("H", "calendar", "HC 34.pdf", "No 34 September 18 2026", "wanted"),
            ("H", "calendar", "HC 33.pdf", "No 33 September 11 2026", "wanted"),
            ("S", "calendar", "SC 29.pdf", "No 29 September 3 2026", "wanted")], added
        by = {CA._key(r): r for r in new}
        hc35 = by[("H", "calendar", "2026", "HC 35.pdf")]
        sc29 = by[("S", "calendar", "2026", "SC 29.pdf")]
        assert hc35["url"] == _DOCS_HC35 and \
            Path(hc35["path"]) == Path("calendars") / "2026" / "HC035.pdf", hc35
        assert sc29["url"] == _DOCS_SC29 and \
            Path(sc29["path"]) == Path("calendars_senate") / "2026" / "SC029.pdf", sc29
        assert [r["name"] for r in new if (r["chamber"], r["kind"], r["year"]) ==
                ("H", "calendar", "2026")] == [d for d, _ in _DOCS_HC] and new[0] is hc35, \
            "what is new is not at the head of its list, in the page's order"
        was = [CA._key(r) for r in rows]
        assert [CA._key(r) for r in new if CA._key(r) in set(was)] == was, \
            "the rows on file changed their order"
        assert all(by[CA._key(r)][f] == r[f] for r in rows for f in r), \
            "a row on file was changed"
        assert by[("H", "calendar", "2026", "HC 32.pdf")]["label"] == "No 32 September 4 2026", \
            "a row on file did not gain the label the page shows for it"
        assert CA.news(rows, new) == "4 new: House Calendar 3, Senate Calendar 1" and \
            CA.news(new, new) == "nothing new", CA.news(rows, new)

        # A name's entities are read: the address asks for the apostrophe.
        odd = dict(pages)
        odd["S journal 2026"] = _docs_page(
            CA, pages["S calendar 2026"], _DOCS_S, "SenateJournal", st["years"], "2026",
            [("SJ 16 Governor&#39;s Address.pdf", "SJ 16 Governor&#39;s Address")] + _DOCS_SJ,
            "Journals\\2026\\SJ 16 Governor&#39;s Address.pdf")
        lists, _ = read(odd)
        new, added = CA.merged(rows, lists)
        r = next(r for r in added if r["kind"] == "journal")
        assert r["name"] == "SJ 16 Governor's Address.pdf" and r["label"] == "SJ 16 Governor's Address" \
            and r["url"].endswith("Journals%5C2026%5CSJ%2016%20Governor%27s%20Address.pdf") \
            and CA.judge(rows, new, {"lists": lists}) == "", r

        # The turn of a year: both years' lists, eight requests, whichever
        # way the page answers a change of kind.
        yw = CA.years_wanted
        ys = ["2027", "2026", "2025"]
        assert yw(ys[1:], datetime.date(2026, 10, 2)) == ["2026"] and \
            yw(ys[1:], datetime.date(2026, 1, 31)) == ["2026", "2025"] and \
            yw(ys[1:], datetime.date(2026, 2, 1)) == ["2026"] and \
            yw(ys[1:], datetime.date(2025, 12, 30)) == ["2026", "2025"] and \
            yw(ys, datetime.date(2026, 11, 27)) == ["2027", "2026"] and \
            yw(ys, datetime.date(2027, 2, 1)) == ["2027"] and yw(["1998"], datetime.date(2026, 1, 1)) \
            == ["1998"], "the years read on a day are not the newest, and the one before it only at the turn"
        for leaves in (False, True):
            lists, n = read(pages, day=(2026, 1, 9), leaves_year=leaves)
            got = sorted((li["chamber"], li["kind"], li["year"]) for li in lists)
            assert n == 8 == CA.LISTING_MOST == len(got) and got == sorted(
                (c, k, y) for c in "HS" for k in ("calendar", "journal") for y in ("2025", "2026")), (n, got)
            assert [a[4] for a in asked if a[0] == "H"] == ["", "ddlYears", "ddlCalJourn", "ddlYears"], asked
            new, _ = CA.merged(rows, lists)
            assert CA.judge(rows, new, {"lists": lists}) == ""

        # A YEAR WITH NO JOURNALS YET. The Senate's page answers HTTP 500, not
        # an empty list, for a year it has no journals for (discover()'s own
        # note of 1998-2002). When 2027's lists open, that is each chamber's
        # last request, every night until a journal is posted.
        hc = _DOCS_HC
        years = st["years"]
        turn = _docs_turn(CA, pages)
        filed = {(r["chamber"], r["kind"], r["year"]) for r in rows}

        def no(code=500):
            return urllib.error.HTTPError("u", code, "Server Error", {}, None)
        lists, n = read(turn, day=(2026, 12, 10), on_file=filed, newest="2027",
                        fail={4: no(), 8: no()})
        silent = [(li["chamber"], li["kind"], li["year"]) for li in lists if li.get("unanswered")]
        assert n == 8 and len(lists) == 8 and silent == [
            ("H", "journal", "2027"), ("S", "journal", "2027")], (n, silent)
        assert all(li["unanswered"] == 500 and not li["documents"] and not li["directory"]
                   for li in lists if li.get("unanswered")) and not refusal.MARK.exists()
        rec = {"lists": lists}
        new, added = CA.merged(rows, lists)
        assert CA.judge(rows, new, rec) == "" and sorted(
            (r["year"], r["name"]) for r in added)[-2:] == [("2027", "HC 1.pdf"),
                                                          ("2027", "SC 1.pdf")], added
        assert CA.unanswered(rec) == ["the House Journal list for 2027",
                                      "the Senate Journal list for 2027"], CA.unanswered(rec)
        # In February only the new year is read: two requests a chamber.
        lists, n = read(turn, day=(2027, 2, 3), on_file=filed, newest="2027",
                        fail={2: no(), 4: no()})
        assert n == 4 and [bool(li.get("unanswered")) for li in lists] == [
            False, True, False, True] and CA.judge(
                rows, CA.merged(rows, lists)[0], {"lists": lists}) == "", (n, lists)
        # And nothing else is taken for "none yet": not where nobody said
        # what is on file; not with a journal of that year on file; not a
        # 500 to a calendar list, or to the journals of the year before; not
        # a dropped connection; not a refusal; and not where the year's
        # calendar list was itself empty.
        for what, kw, code_want, said in (
                ("with nothing said of what is on file",
                 dict(fail={4: no()}), 1, "the request for the House Journal list for 2027 failed"),
                ("with a journal of that year on file",
                 dict(fail={4: no()}, on_file=filed | {("H", "journal", "2027")}), 1,
                 "the request for the House Journal list for 2027 failed"),
                ("answered to a calendar list",
                 dict(fail={2: no()}, on_file=filed), 1,
                 "the request for the House Calendar list for 2026 failed"),
                ("answered to the journals of the year before",
                 dict(fail={3: no()}, on_file=filed), 1,
                 "the request for the House Journal list for 2026 failed"),
                ("a connection dropped",
                 dict(fail={4: http.client.RemoteDisconnected("closed")}, on_file=filed), 1,
                 "the request for the House Journal list for 2027 was not answered"),
                ("a refusal", dict(fail={4: no(403)}, on_file=filed), 2,
                 "the General Court refused a request")):
            refusal.MARK.unlink(missing_ok=True)
            got = stops(turn, day=(2026, 12, 10), newest="2027", **kw)
            assert got == (code_want, said), (
                f"a year's journal list not answered, {what}: {got}")
        refusal.MARK.unlink(missing_ok=True)
        bare = dict(turn, **{"H calendar 2027": _docs_page(
            CA, pages["S calendar 2026"], _DOCS_H, "Calendar", ["2027"] + years, "2027", [], "")})
        got = stops(bare, day=(2026, 12, 10), newest="2027", on_file=filed, fail={4: no()})
        assert got[0] == 1 and len(asked) == 4, (
            "a journal list not answered was taken for none yet, of a year whose calendar "
            f"list had nothing in it either: {got}")
        got = stops(pages, fail={1: no()}, on_file=set())
        assert got == (1, "the request for the House index page failed"), got
        # judge() holds the same line, on a record that says otherwise.
        lists, _ = read(turn, day=(2026, 12, 10), on_file=filed, newest="2027",
                        fail={4: no(), 8: no()})

        def unanswered_as(ch, kind, year):
            return [dict(li, documents=[], directory="", unanswered=500)
                    if (li["chamber"], li["kind"], li["year"]) == (ch, kind, year) else li
                    for li in lists]
        for forged, about in (
                (unanswered_as("S", "journal", "2026"), "the Senate Journal list for 2026"),
                (unanswered_as("H", "calendar", "2027"), "the House Calendar list for 2027"),
                ([li for li in lists if (li["chamber"], li["kind"], li["year"]) !=
                  ("S", "calendar", "2027")], "the Senate Journal list for 2027")):
            why = CA.judge(rows, CA.merged(rows, forged)[0], {"lists": forged})
            assert why.startswith(about + " was not answered"), (about, why)

        # A page that has changed shape stops the read where it is.
        bad = dict(pages)
        bad["H calendar 2026"] = _docs_page(CA, pages["S calendar 2026"], _DOCS_H, "Calendar",
                                            years, "2026", hc, "calendars\\2025\\HC 35.pdf")
        assert stops(bad)[0] == 1 and len(asked) == 1, "a link naming another year's folder was believed"
        bad["H calendar 2026"] = _docs_page(CA, pages["S calendar 2026"], _DOCS_H, "Calendar",
                                            years, "2026", hc, "calendars\\2026\\HC 34.pdf")
        assert stops(bad)[0] == 1, "a link naming another document than the one selected was believed"
        bad["H calendar 2026"] = pages["H calendar 2026"].replace(
            'href="viewer.aspx?fileName=', 'href="open.aspx?doc=')
        assert stops(bad)[0] == 1 and len(asked) == 1, "a page with no View PDF File link was read"
        bad["H calendar 2026"] = pages["H calendar 2026"].replace(
            'selected="selected" value="Calendar"', 'value="Calendar"')
        code, why = stops(bad)
        assert code == 1 and "which list it shows" in why, (code, why)
        bad["H calendar 2026"] = _docs_page(
            CA, pages["S calendar 2026"], _DOCS_H, "Calendar", years, "2026",
            hc[:1] + [("..\\journals\\HC 36.pdf", "No 36")] + hc[1:], "calendars\\2026\\HC 35.pdf")
        code, why = stops(bad)
        assert code == 1 and "not a file name" in why, (
            "a document named as a path into another folder was written down", code, why)
        bad = dict(pages)
        bad["H journal 2026"] = pages["H calendar 2026"]
        code, why = stops(bad)
        assert code == 1 and "not the list asked for" in why and len(asked) == 2, (code, why, asked)
        bad["H journal 2026"] = "<html><body>Server Error in '/' Application.</body></html>"
        assert stops(bad)[0] == 1 and len(asked) == 2 and not refusal.MARK.exists()

        # An address that says no: recorded, and nothing more is asked.
        for answer, code_want, noted in (
                (urllib.error.HTTPError("u", 403, "Forbidden", {}, None), 2, True),
                (b"<h1>Web Page Blocked</h1> Attack ID: 9", 2, True),
                (urllib.error.HTTPError("u", 500, "Server Error", {}, None), 1, False),
                (http.client.RemoteDisconnected("closed"), 1, False),
                (urllib.error.URLError(ConnectionResetError(10054, "reset")), 1, False)):
            refusal.MARK.unlink(missing_ok=True)
            code, why = stops(pages, fail={2: answer})
            assert code == code_want and len(asked) == 2 and refusal.MARK.exists() == noted, (
                f"{answer!r}: status {code}, {len(asked)} requests, refusal recorded "
                f"{refusal.MARK.exists()}")
            assert "Forbidden" not in why and "Blocked" not in why, \
                f"the reason carries the server's own words: {why}"
        # With one on file nothing is asked; nor without the lock; nor past the budget.
        refusal.MARK.write_text(json.dumps({"at": "t", "epoch": 0, "where": "x"}),
                                encoding="utf-8")
        assert stops(pages) == (2, "a refusal is on file") and not asked
        refusal.MARK.unlink()
        gone = Held()
        gone.ok = False
        assert stops(pages, held=gone)[0] == 3 and not asked, "it asked without the lock"
        CA._get = server(pages)
        del asked[:]

        def late(url, data=None, timeout=60, real=server(pages)):
            clock["jump"] += CA.LISTING_BUDGET + 1
            return real(url, data, timeout)
        CA._get = late
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                CA.listing(Held(), day=datetime.date(2026, 10, 2))
            raise AssertionError("a listing past its time budget went on asking")
        except CA.Stop as e:
            assert e.code == 1 and len(asked) == 1 and str(CA.LISTING_BUDGET) in e.why, (e.why, asked)
        clock["jump"] = 0.0
        # It runs under the night's lock, after the day's files: five minutes
        # and one request's timeout is the most it may add to the time the
        # night spends asking, which refusal.NIGHT_WINDOWS allows an hour for.
        assert CA.LISTING_BUDGET <= 300, f"the listing may take {CA.LISTING_BUDGET} seconds"

        # judge(): what may replace the list on file.
        lists, _ = read(pages)
        good, _ = CA.merged(rows, lists)
        rec = {"lists": lists}

        def with_list(key, docs, folder):
            """Tonight's lists with one of them replaced."""
            ch, kind, year = key.split()
            return [dict(li, documents=[{"name": n, "label": lab} for n, lab in docs],
                         directory=f"{folder}\\{year}\\" if docs else "")
                    if (li["chamber"], li["kind"], li["year"]) == (ch, kind, year) else li
                    for li in lists]
        short = with_list("H calendar 2026", hc[:4], "calendars")
        why = CA.judge(rows, CA.merged(rows, short)[0], {"lists": short})
        assert why == "the House Calendar list for 2026 came back without 3 of the 4 documents on file", why
        served = CA.shown(pages["S calendar 2026"])["docs"]
        one = with_list("S calendar 2026", served[:-1], "Calendars")
        new, _ = CA.merged(rows, one)
        block = [r["name"] for r in new if (r["chamber"], r["kind"], r["year"]) ==
                 ("S", "calendar", "2026")]
        assert CA.judge(rows, new, {"lists": one}) == "" and len(block) == 39 and \
            block[0] == "SC 29.pdf" and block[-1] == served[-1][0], \
            "one document gone from a list of 38 stopped the list, or dropped its row"
        empty = with_list("S journal 2026", [], "Journals")
        why = CA.judge(rows, CA.merged(rows, empty)[0], {"lists": empty})
        assert why == "the Senate Journal list for 2026 came back empty, with 2 documents on file", why
        opened = lists + [{"chamber": "H", "kind": "journal", "year": "2027", "directory": "",
                           "read": "t", "documents": []}]
        assert CA.judge(rows, CA.merged(rows, opened)[0], {"lists": opened}) == "", \
            "a new year's list with nothing in it yet, and nothing on file, was refused"
        assert CA.judge(rows, good, {"lists": lists[:3]}) == "the Senate Journal list was not read"
        older = [dict(li, year="2025") if li["kind"] == "journal" and li["chamber"] == "S" else li
                 for li in lists]
        assert CA.judge(rows, rows, {"lists": older}) == \
            "the Senate Journal list for 2026 was not read", CA.judge(rows, rows, {"lists": older})
        assert CA.judge(rows, [], rec) == "the list came back empty"
        assert CA.judge(rows, good, {}) == "nothing records which lists were read"
        lost = [r for r in good if r["name"] != "HC 32.pdf"]
        assert CA.judge(rows, lost, rec) == f"1 of the {len(rows)} documents on file is not in it"
        moved = [dict(r, url=r["url"] + "x") if r["name"] == "HC 32.pdf" else r for r in good]
        assert CA.judge(rows, moved, rec) == "it changes the address or the path of a document on file"
        built = [dict(r, url=r["url"].replace("HC%2035", "No%2035%20September%2025%202026"))
                 if r["name"] == "HC 35.pdf" else r for r in good]
        assert CA.judge(rows, built, rec) == "it adds an address the General Court's page did not give"
        extra = good + [dict(good[0], name="HC 36.pdf")]
        assert CA.judge(rows, extra, rec) == "it adds a document no list read tonight names"
        held = [dict(r, state="held") if r["name"] == "HC 35.pdf" else r for r in good]
        assert CA.judge(rows, held, rec) == "it adds a document as already fetched"
        assert CA.judge(rows, good + [good[0]], rec) == "it names a document twice"

        # THE LIMIT, PINNED ON BOTH SIDES. Nothing held LIST_GONE_MOST to its
        # value: the one short list above drops three of four, and 0.60 for
        # 0.10 passed every check here.
        one_row = next(r for r in rows if (r["chamber"], r["kind"], r["year"]) ==
                       ("H", "journal", "2026"))
        others = [r for r in rows if (r["chamber"], r["kind"], r["year"]) !=
                  ("H", "journal", "2026")]
        hj = CA.SOURCES[("H", "journal")][0] + CA.VIEWER

        def journals(n):
            """n House journals of 2026 on file, newest first: (names, the queue)."""
            names = [f"HJ {i:02d} March {i}, 2026.pdf" for i in range(n, 0, -1)]
            return names, others + [
                dict(one_row, name=x, path=f"journals\\2026\\{x}",
                     url=hj + urllib.parse.quote(f"journals\\2026\\{x}", safe="")) for x in names]

        def tonight(names):
            return with_list("H journal 2026", [(x, x[:-4]) for x in names], "journals")

        def says(was, names, last=None, **kw):
            li = tonight(names)
            return CA.judge(was, CA.merged(was, li)[0], {"lists": li}, last, **kw)
        for on_file, gone, passes in ((20, 2, True), (20, 3, False), (30, 3, True),
                                      (30, 4, False), (4, 1, True), (4, 2, False)):
            names, was = journals(on_file)
            why = says(was, names[gone:])
            assert why == ("" if passes else "the House Journal list for 2026 came back "
                           f"without {gone} of the {on_file} documents on file"), (
                f"{gone} of {on_file} documents gone from a list: {why or 'let through'}")
        # COUNTED AGAINST THE LAST READ, NOT AGAINST THE FILE. A row never
        # leaves the queue, so against the file every document the page had
        # ever dropped counted again each night: with three gone on earlier
        # nights, the same list as last night was refused for ever.
        names, was = journals(20)
        last = {"read": "t", "lists": tonight(names[3:])}
        assert says(was, names[3:]) == \
            "the House Journal list for 2026 came back without 3 of the 20 documents on file"
        assert says(was, names[3:], last) == "" and \
            CA.shortfall(was, {"lists": tonight(names[3:])}, last) == [], (
                "a list the same as it was when last read is short of the documents that "
                "had left it before: " + says(was, names[3:], last))
        assert says(was, names[4:], last) == "", "one more gone, of seventeen, stopped the list"
        why = says(was, names[6:], last)
        assert why == ("the House Journal list for 2026 came back without 3 of the 17 "
                       "documents it listed when it was last read"), why
        assert [(k, len(g), of, since) for k, g, of, since in CA.shortfall(
            was, {"lists": tonight(names[6:])}, last)] == [(("H", "journal", "2026"), 3, 17, True)]
        # What the night passes once the same answer has come night after
        # night lets a short list through, and never an empty one.
        assert says(was, names[6:], last, shorter=True) == ""
        assert says(was, [], last, shorter=True) == \
            "the House Journal list for 2026 came back empty, with 20 documents on file"
        # A record of the last read that is not one counts against the file.
        for junk in (None, {}, {"stopped": "x"}, {"lists": "x"}, [1], {"lists": [{"year": 1}]}):
            assert says(was, names[3:], junk).endswith("3 of the 20 documents on file"), junk

        # main(), for the night: --out writes both files and installs nothing.
        _docs_write_old(CA.QUEUE, rows)
        before = CA.QUEUE.read_bytes()
        CA._get = server(pages)
        out = tmp / "scratch" / "queue.csv"
        out.parent.mkdir()
        rc, said = main("--listing", "--out", str(out))
        listed = json.loads((out.parent / CA.LISTED_NAME).read_text(encoding="utf-8"))
        assert rc == 0 and len(asked) == 4 and CA.QUEUE.read_bytes() == before and \
            not CA.listed_file().exists() and not refusal.LOCK.exists(), (rc, said[-300:])
        assert listed["requests"] == 4 and len(listed["lists"]) == 4 and \
            listed["lists"][0]["documents"][0] == {"name": "HC 35.pdf",
                                                   "label": "No 35 September 25 2026"}, listed
        got = CA.read_rows(out)
        assert CA.judge(CA.read_rows(CA.QUEUE), got, listed) == "" and \
            len(got) == len(rows) + 4 and "label" in got[0], "what --out wrote is not the list"
        # Under a lock that is somebody else's it does not run at all.
        refusal.LOCK.write_text("99999999", encoding="utf-8")
        rc, said = main("--listing", "--out", str(out))
        assert rc == 3 and not asked, (rc, asked)
        refusal.LOCK.unlink()
        rc, said = main("--listing", "--chamber", "H")
        assert rc == 2 and not asked and "all four lists" in said, (rc, said[-200:])
        # main() says what is on file: a new year's journal lists that the
        # page does not answer for are written down as that, and stop nothing.
        CA.today = lambda: datetime.date(2026, 12, 10)
        CA._get = server(turn, fail={4: no(), 8: no()}, newest="2027")
        rc, said = main("--listing", "--out", str(out))
        listed = json.loads((out.parent / CA.LISTED_NAME).read_text(encoding="utf-8"))
        assert rc == 0 and len(asked) == 8 and \
            [li.get("unanswered") for li in listed["lists"]].count(500) == 2 and \
            "no answer for the House Journal list for 2027" in said, (rc, said[-400:])
        assert CA.judge(CA.read_rows(CA.QUEUE), CA.read_rows(out), listed) == ""
        CA.today = lambda: datetime.date(2026, 10, 2)

        # By hand, where this machine keeps its own list: judged, then installed.
        CA._get = server({**pages, "H calendar 2026": _docs_page(
            CA, pages["S calendar 2026"], _DOCS_H, "Calendar", years, "2026", hc[:4],
            "calendars\\2026\\HC 35.pdf")})
        rc, said = main("--listing")
        assert rc == 1 and "Not installed" in said and CA.QUEUE.read_bytes() == before, (rc, said[-300:])
        CA._get = server(pages)
        rc, said = main("--listing")
        assert rc == 0 and len(CA.read_rows(CA.QUEUE)) == len(rows) + 4 and \
            CA.listed_file().exists(), (rc, said[-300:])
        rc, said = main("--status")
        assert rc == 0 and "last read" in said and not asked, said[-200:]

        # A refusal on file, or a laptop that has stood down: no request.
        refusal.MARK.write_text(json.dumps({"at": "t", "epoch": time.time(), "where": "x",
                                            "why": "403"}), encoding="utf-8")
        for flag in ("--listing", "--discover"):
            rc, said = main(flag)
            assert rc == 2 and not asked and "refused" in said, (
                f"{flag} was not stopped by a standing refusal (exit {rc})")
        refusal.MARK.unlink()
        refusal.STANDDOWN.write_text('{"since": "2026-09-26T09:00:00"}', encoding="utf-8")
        for flag in ("--listing", "--discover"):
            rc, said = main(flag)
            assert rc == refusal.STOOD_DOWN and not asked and "GitHub runs it" in said, (
                f"{flag} ran on a laptop that has stood down (exit {rc}): {said[-200:]}")
        # There the drain's state goes to the laptop's own file, the night's
        # list is not written, and both are read as one; a row drops out of
        # the laptop's file once the night's list says the same.
        assert CA.list_is_the_nights()
        # The stand-down that counts is the one beside the queue: a queue in
        # a folder of its own -- every test's, _calendar_drain's among them --
        # is never the night's because the machine running it has stood down.
        CA.QUEUE = tmp / "elsewhere" / "queue.csv"
        assert not CA.list_is_the_nights(), \
            "a queue in another folder was taken for the night's because this machine has stood down"
        CA.QUEUE = tmp / "archive" / "queue.csv"
        mine = CA.load_queue()
        listed_bytes = CA.QUEUE.read_bytes()
        want = next(r for r in mine if r["name"] == "HC 35.pdf")
        want.update(state="held", bytes="182000", fetched="2026-10-02T21:10:00")
        CA.save_queue(mine)
        kept = CA.read_rows(CA.fetched_file())
        assert CA.QUEUE.read_bytes() == listed_bytes and [r["name"] for r in kept] == ["HC 35.pdf"] \
            and kept[0]["state"] == "held", "the stood-down drain wrote the night's list, or kept more than it changed"
        again = next(r for r in CA.load_queue() if r["name"] == "HC 35.pdf")
        assert (again["state"], again["bytes"], again["fetched"]) == (
            "held", "182000", "2026-10-02T21:10:00"), again
        CA.write_rows(CA.QUEUE, CA.load_queue())        # the night's list catches up
        CA.save_queue(CA.load_queue())
        assert CA.read_rows(CA.fetched_file()) == [], "a row the night's list agrees with stayed in the laptop's file"
        # And on GitHub's own machine a copy of that file stands nothing down.
        os.environ["GITHUB_ACTIONS"] = "true"
        assert not CA.list_is_the_nights()
        os.environ.pop("GITHUB_ACTIONS", None)
        refusal.STANDDOWN.unlink()
        assert not CA.list_is_the_nights()
        mine = CA.load_queue()
        mine[0]["attempts"] = "1"
        CA.save_queue(mine)
        assert CA.read_rows(CA.QUEUE)[0]["attempts"] == "1", \
            "a machine that keeps its own list did not write it"
    finally:
        (refusal.MARK, refusal.LOCK, refusal.STANDDOWN, CA.ROOT, CA.QUEUE, CA._get, CA.time,
         CA.today, sys.argv) = saved
        if saved_env is None:
            os.environ.pop("GITHUB_ACTIONS", None)
        else:
            os.environ["GITHUB_ACTIONS"] = saved_env
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("four requests a night and eight at the turn of a year, one change each, "
                  f"{CA.LISTING_PAUSE:g}s apart and as long before the first; addresses from "
                  "the page's own folder and names; a new year's journal list not answered is "
                  "none yet, and nothing else is; a changed page, a refusal, a short or empty "
                  "list and a moved row all leave the list as it was, short being counted "
                  "against the last read; a stood-down laptop never writes it")


@check("frontend", "a meeting takes the General Court's colour for its kind, a study committee its own, and the week carries the key")
def _meet_kind_colours():
    """Work sessions, conferences and the floor were all orange.

    The General Court's schedule, which staff read every week, colours a
    hearing blue, a meeting green, an executive session orange and a
    committee of conference red (fetch_schedule.py quotes the legend). The
    calendar here gave a hearing gold and an executive session teal, and
    every other kind fell to a catch-all bar in --st-study orange -- so 55
    committees of conference and 60 floor sittings, and every work session,
    wore the colour that means executive session there. No page carried a key.

    STUDY AND STATUTORY COMMITTEES ARE THEIR OWN COLOUR since 25 September
    2026. They were green with the work sessions, as the General Court's
    schedule has them, until the person asked for the two not to be grouped:
    the colours became the Calendar's filter, and one box can no longer mean
    both. So this now wants them in k-study, on its own --cal-study token,
    with the other five as they were.

    KEY DATES ARE THE SEVENTH COLOUR in the key since 24 October 2026 (the
    owner: "those dates should show up on the calendar page too under a
    separate meeting type in the key"): k-date, on --cal-date, last in the
    key and the boxes. Not a kind of meeting, so no kind in the record maps
    to it; its chip, key, dot, bars and box are held here as the six are.

    This holds each kind that occurs in the record to its class, each class
    to a chip rule, a bar rule, a key rule, a grid dot, a preview bar and a
    box in app.css, each drawn from its own --cal- token; the key to every
    class, in the order of the Calendar's boxes and named in title case; and
    a built week to the key and the boxes.
    """
    import build_pages as BP
    want = {"public hearing": "k-hearing", "hearing": "k-hearing",
            "executive session": "k-exec", "work session": "k-meet",
            "subcommittee work session": "k-meet",
            "full committee work session": "k-meet",
            "study committee": "k-study", "statutory committee": "k-study",
            "committee of conference": "k-conf", "floor debate": "k-floor"}
    got = {k: BP.MEET_KIND.get(k, ("", ""))[1] for k in want}
    assert got == want, ("meeting kinds take the wrong colour: "
                         + ", ".join(f"{k} is {got[k]!r}, not {want[k]!r}"
                                     for k in want if got[k] != want[k]))
    css = _source("src/pages/app.css")
    tok = {"k-hearing": "hear", "k-exec": "exec", "k-meet": "meet",
           "k-conf": "conf", "k-floor": "floor", "k-study": "study", "k-date": "date"}
    for cls, t in tok.items():
        for rule in (rf"\.chip\.{cls}\{{[^}}]*var\(--cal-{t}\)",
                     rf"\.calmix \.{cls}\{{background:var\(--cal-{t}\)\}}",
                     rf"\.calkey \.{cls}\{{background:var\(--cal-{t}\)\}}",
                     rf"\.cmdots \.{cls}\{{background:var\(--cal-{t}\)\}}",
                     rf"\.pkbar \.{cls}\{{background:var\(--cal-{t}\)\}}",
                     rf"\.wkbar \.{cls}\{{background:var\(--cal-{t}\)\}}",
                     rf"\.calcat\.{cls}\{{--cat:var\(--cal-{t}\)\}}"):
            assert re.search(rule, css), (
                f"app.css has no rule matching {rule!r}: the {cls} colour is "
                "not drawn from its own --cal- token")
    assert re.search(r"\.calmix \.k-other\{background:var\(--edge\)\}", css), (
        "a kind the table does not name borrows a colour instead of the neutral edge")
    legend = [c for c, _w in BP.MEET_LEGEND]
    assert legend == list(tok), f"the key names {legend}, not {list(tok)}, in that order"
    names = [w for _c, w in BP.MEET_LEGEND]
    assert names == ["Public Hearing", "Executive Session", "Work Session",
                     "Committee of Conference", "Session Day", "Study Committee",
                     "Important Dates"], (
        f"the key's names are {names}: one per kind, work sessions and study "
        "committees apart, and the key dates last, in title case")

    import contextlib
    import datetime as _dt
    import io
    import build_calendar as BC
    here = Path(".").resolve()
    if not (here / "src/pages/bills.html").exists():
        return "skip", "bills.html is not here"
    rows = [{"term": "2025-2026", "bill": "HB1", "body": "H", "kind": k,
             "date": "2026-03-05", "time": t, "committee": c, "venue": ""}
            for k, t, c in (("floor debate", "", ""),
                            ("committee of conference", "", ""),
                            ("subcommittee work session", "10:00", "Commerce"))]
    rows.append({"study": True, "bill": "", "kind": "statutory committee",
                 "date": "2026-03-05", "time": "13:00",
                 "committee": "Commission on Aging", "venue": "", "note": ""})
    weeks = BC.weeks_from(rows, names={})
    order = sorted(weeks)
    tmp = Path(tempfile.mkdtemp(prefix="gr-kinds-"))
    try:
        site = tmp / "site"
        site.mkdir()
        shutil.copy(here / "src/pages/bills.html", site / "bills.html")
        with contextlib.redirect_stdout(io.StringIO()):
            BC.week_page(site, "https://graniterecord.org", order[0], weeks, order, 0,
                         {}, {}, {}, [], _dt.date(2026, 9, 24), set())
        t = (site / "calendar" / f"{order[0]}.html").read_text(encoding="utf-8")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    key = re.search(r'<ul class="calkey"[^>]*>(.*?)</ul>', t)
    assert key, "a week's page carries no key to its colours for a reader without script"
    assert re.findall(r'<i class="(k-[a-z]+)"', key.group(1)) == list(tok), (
        "the key is not the seven colours in the boxes' order")
    boxes = re.findall(r'<label class="calcat (k-[a-z]+)"><input type="checkbox" name="cat" '
                       r'value="([a-z]+)"( checked)?><span class="cbx" aria-hidden="true">'
                       r'</span>([^<]*)</label>', t)
    assert [(c, w) for c, _v, _on, w in boxes] == list(BP.MEET_LEGEND), (
        f"the row of boxes is {boxes}: one per colour, each labelled as the key names it")
    assert '<fieldset class="calcats" id="calcats" hidden>' in t, (
        "the row of boxes is not written hidden for the script to show")
    bars = re.findall(r'<span class="calmix" aria-hidden="true">(.*?)</span>', t)
    seen = set(re.findall(r'<i class="(k-[a-z]+)"></i>', "".join(bars)))
    assert seen == {"k-floor", "k-conf", "k-meet", "k-study"}, (
        f"a floor sitting, a conference, a work session and a statutory "
        f"committee drew bars {sorted(seen)}")
    # Title case, as the boxes are (the person, 25 September 2026).
    chip = re.search(r'<span class="chip calkind (k-[a-z]+)">Statutory Committee</span>', t)
    assert chip and chip.group(1) == "k-study", (
        "a statutory committee's chip does not wear the study committees' colour")
    return "ok", (f"{len(want)} kinds on six colours and the key dates on a seventh, each from its own token, "
                  "study committees apart from work sessions, and the key and the boxes on the week")


@check("frontend", "every week from the first to the last has a page, and the arrows step one week")
def _calendar_every_week():
    """"The week after" 15-21 June 2026 went to 17-23 August.

    build_calendar wrote a page only for a week that held a sitting, and each
    page's arrows went to the neighbouring PAGE -- so out of session the arrow
    labelled "The week after" jumped eight weeks, and /calendar/2026-W30 was a
    404. A reader cannot tell a week that was skipped from one that was quiet.

    This gives two sittings nine weeks apart and a build date a month after
    the second, writes every week, and wants a page for each ISO week in the
    span with its arrows on the weeks either side of it, the current week's
    arrow on /calendar, and an empty week saying so rather than standing blank.
    """
    import contextlib
    import datetime as _dt
    import io
    import build_calendar as BC
    here = Path(".").resolve()
    if not (here / "src/pages/bills.html").exists():
        return "skip", "bills.html is not here"
    rows = [{"term": "2025-2026", "bill": b, "body": "H", "kind": "public hearing",
             "date": d, "time": "10:00", "committee": "Commerce", "venue": "LOB 302"}
            for b, d in (("HB1", "2026-06-16"), ("HB2", "2026-08-18"))]
    today = _dt.date(2026, 9, 24)
    weeks = BC.weeks_from(rows)
    added = BC.every_week(weeks, today)
    order = sorted(weeks)
    assert order[0] == "2026-W25" and order[-1] == BC.week_key(today), (
        f"the weeks run {order[0]} to {order[-1]}, not 2026-W25 to "
        f"{BC.week_key(today)}")
    mondays = [_dt.date.fromisocalendar(int(k[:4]), int(k[6:]), 1) for k in order]
    gaps = [f"{a} to {b}" for a, b, x, y in zip(order, order[1:], mondays, mondays[1:])
            if (y - x).days != 7]
    assert not gaps, "the weeks skip: " + ", ".join(gaps)
    assert added == len(order) - 2, (
        f"{added} weeks were added between two that hold sittings, of "
        f"{len(order) - 2}")

    def addr(k):
        return "/calendar" if k == BC.week_key(today) else f"/calendar/{k}"

    tmp = Path(tempfile.mkdtemp(prefix="gr-weeks-"))
    try:
        site = tmp / "site"
        site.mkdir()
        shutil.copy(here / "src/pages/bills.html", site / "bills.html")
        urls = []
        with contextlib.redirect_stdout(io.StringIO()):
            for i, k in enumerate(order):
                BC.week_page(site, "https://graniterecord.org", k, weeks, order, i,
                             {}, {}, {}, urls, today, set())
        for i, k in enumerate(order):
            f = site / "calendar" / f"{k}.html"
            assert f.exists(), f"calendar/{k}.html was not written"
            t = f.read_text(encoding="utf-8")
            nxt = re.findall(r'class="wknext" href="([^"]+)"', t)
            prv = re.findall(r'class="wkprev" href="([^"]+)"', t)
            if i + 1 < len(order):
                assert nxt and set(nxt) == {addr(order[i + 1])}, (
                    f"{k}: Next Week goes to {nxt}, not {addr(order[i + 1])}")
            if i:
                assert prv and set(prv) == {addr(order[i - 1])}, (
                    f"{k}: Previous Week goes to {prv}, not {addr(order[i - 1])}")
        quiet = (site / "calendar" / "2026-W30.html").read_text(encoding="utf-8")
        assert "No meetings are on the record for this week." in quiet, (
            "an empty week that is over does not say nothing was on")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", (f"{len(order)} weeks from {order[0]} to {order[-1]}, {added} of "
                  "them empty, each a page with its arrows on the weeks beside it")


@check("frontend", "a week's page lists every weekday, and a weekend day only when something is on it")
def _calendar_every_weekday():
    """Live /calendar for 21-27 September 2026 showed Wednesday and Thursday.

    build_calendar kept only the days that held a meeting, so Monday, Tuesday
    and Friday were simply not there and a quiet day could not be told from a
    missing one. This writes a week with a Wednesday and a Saturday sitting
    and another with only a Wednesday, and wants Monday to Friday on both --
    each empty one marked and saying "No meetings scheduled." -- the Saturday
    on the first only, no Sunday on either, and the week's script leaving the
    empty days alone under a filter that matches nothing.

    That last part looked, until 24 September 2026, for ".calday:not(.calnone)"
    in the old filter's source. The Calendar page's script decides which days
    its list draws in listDates, from the month files, so it is run instead:
    the rule it held is the same, and now it is held by what the script does.
    """
    import contextlib
    import datetime as _dt
    import io
    import build_calendar as BC
    here = Path(".").resolve()
    if not (here / "src/pages/bills.html").exists():
        return "skip", "bills.html is not here"
    rows = [{"term": "2025-2026", "bill": b, "body": "H", "kind": "public hearing",
             "date": d, "time": "10:00", "committee": "Commerce", "venue": "LOB 302"}
            for b, d in (("HB1", "2026-01-14"), ("HB2", "2026-01-17"),
                         ("HB3", "2026-01-21"))]
    today = _dt.date(2026, 9, 24)
    weeks = BC.weeks_from(rows)
    order = sorted(weeks)
    tmp = Path(tempfile.mkdtemp(prefix="gr-weekdays-"))
    try:
        site = tmp / "site"
        site.mkdir()
        shutil.copy(here / "src/pages/bills.html", site / "bills.html")
        with contextlib.redirect_stdout(io.StringIO()):
            for i, k in enumerate(order):
                BC.week_page(site, "https://graniterecord.org", k, weeks, order, i,
                             {}, {}, {}, [], today, set())
        want = {"2026-W03": (["2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15",
                              "2026-01-16", "2026-01-17"], {"2026-01-14", "2026-01-17"}),
                "2026-W04": (["2026-01-19", "2026-01-20", "2026-01-21", "2026-01-22",
                              "2026-01-23"], {"2026-01-21"})}
        for k, (dates, busy) in want.items():
            t = (site / "calendar" / f"{k}.html").read_text(encoding="utf-8")
            got = re.findall(r'<div class="calday( calnone)?" data-d="([^"]+)"', t)
            assert [d for _e, d in got] == dates, (
                f"{k} lists {[d for _e, d in got]}, not {dates}")
            for empty, d in got:
                assert bool(empty) == (d not in busy), (
                    f"{k}: {d} is {'marked empty' if empty else 'not marked empty'}")
            assert t.count("No meetings scheduled.") == len(dates) - len(busy), (
                f"{k}: an empty weekday does not say it has no meetings")
            # THE WEEK IS NAMED BY THE DAYS IT SHOWS (9 October 2026): Monday
            # to Friday, and to the Saturday where one holds a sitting.
            name = {"2026-W03": "January 12–17, 2026", "2026-W04": "January 19–23, 2026"}[k]
            assert f"<h1>The Week of {name}</h1>" in t, (
                f"{k} is not headed The Week of {name}: "
                f"{re.search(r'<h1>[^<]*</h1>', t).group(0)}")
        node = shutil.which("node") or shutil.which("node.exe")
        if node:
            with contextlib.redirect_stdout(io.StringIO()):
                BC.month_files(site, weeks, order, {}, {}, {}, today)
            go = tmp / "days.js"
            go.write_text("globalThis.document={getElementById:function(){return null;}};\n"
                          + _with_components(BC.WEEK_JS) + r"""
const C=globalThis.GRCAL, j=JSON.parse(require("fs").readFileSync(process.argv[2],"utf8")), days={};
Object.keys(j.days).forEach(d=>days[d]=C.parseDay(j.days[d]));
const wk=[0,1,2,3,4,5,6].map(i=>C.addDays("2026-01-12",i)), wk2=wk.map(d=>C.addDays(d,7));
const none=Object.assign(C.defaults(),{cats:[],picks:["nobody"]});
process.stdout.write(JSON.stringify([C.listDates(wk,days,C.defaults()),C.listDates(wk,days,none),
  C.weekCols(wk,days,C.defaults()),C.weekCols(wk2,days,C.defaults()),C.weekCols(wk,days,none)]));
""", encoding="utf-8")
            r = _run([node, str(go), str(site / "calendar" / "data" / "2026-01.json")],
                     capture_output=True, text=True, timeout=60)
            assert r.returncode == 0, (r.stdout or r.stderr).strip()[-300:]
            every, empty, cols, cols2, cols0 = json.loads(r.stdout)
            assert every == want["2026-W03"][0], (
                f"the script's list of 12-18 January draws {every}, the page {want['2026-W03'][0]}")
            # Every weekday stays under a filter matching nothing -- an empty
            # one saying so, a busy one saying what is hidden (9 October
            # 2026) -- and the Saturday, which shows nothing, goes.
            assert empty == ["2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15", "2026-01-16"], (
                "under a filter matching nothing the script's list keeps "
                f"{empty}: Monday to Friday, and no weekend day, stay")
            # AND THE WEEK VIEW: Monday to Friday, the Saturday only where it
            # holds a sitting the filters show, never a Sunday that holds none.
            assert cols == want["2026-W03"][0] and cols2 == want["2026-W04"][0] \
                and cols0 == want["2026-W03"][0][:5], (
                f"the Week view's days are {cols}, {cols2} and, under a filter matching "
                f"nothing, {cols0}: Monday to Friday, and a weekend day only when it shows something")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("Monday to Friday on every week, in the list and the Week view, empty ones "
                  "saying so; a Saturday only where it holds a sitting, and the week named "
                  "by the days it shows")


# The words the pagers and the floor said until 9 October 2026, as code wrote
# them: a line of a builder, a script or a words file that writes one again
# fails _pager_labels. Comments may still quote them, as history.
_PAGER_GONE = ("&lsaquo; The week before", "The week after &rsaquo;", ">This week</a>",
               "The session day before</a>", "The session day after &rsaquo;",
               '"See next week"', "Last Floor Session", '"Floor Session"',
               'floor:"Floor sessions"')


@check("frontend", "the pagers say This Week, Previous Week, Next Week, Previous and Next "
                   "Session Day and Previous and Next Day, and the floor is Session Day, in "
                   "Title Case wherever the site writes them")
def _pager_labels():
    """The person, 9 October 2026: "Session day should be Session Day, This
    week should be This Week, The week before should be Previous Week, The
    week after should be Next Week".

    The Calendar's pager said "‹ The week before", "This week" and "The week
    after ›"; a session day's said "The session day before" and "The session
    day after"; the home page's Coming up said "See next week" for the same
    page the Calendar calls Next Week, and "Last Floor Session"; and the floor
    was "House floor" on its card, under a chip and a box saying "Floor
    Session". This holds every place that writes them: no builder, script or
    words file writes an old one (_PAGER_GONE); a week's page, the Calendar's
    script, a session day's pager and Coming up say the new ones, each pager
    with where it leads under it (a week's short name, a session day's date);
    and the floor is "House Session Day", with no chip to say Session Day
    again, under the key's "Session Day".
    """
    import contextlib
    import datetime as _dt
    import io
    import build_calendar as BC
    import build_pages as BP
    import build_session_pages as SP
    if not Path("src/pages/bills.html").exists():
        return "skip", "bills.html is not here"
    bad = []
    files = (sorted(Path("src/pages").glob("*.py")) + sorted(Path("src/pages").glob("*.js"))
             + sorted(Path("src/pages").glob("*.html")) + sorted(Path("src/pages/words").glob("*.json"))
             + sorted(Path("src/pages/inline").glob("*.js")))
    for f in files:
        for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if ln.strip().startswith(("#", "//", "*")):
                continue
            bad += [f"{f.name}:{i} {g}" for g in _PAGER_GONE if g in ln]
    assert len(files) > 20 and not bad, (
        f"{len(bad)} lines still write a label the person retired: " + "; ".join(bad[:6]))
    assert ("k-floor", "Session Day") in BP.MEET_LEGEND, f"the key names the floor {BP.MEET_LEGEND}"

    root = Path(tempfile.mkdtemp(prefix="gr-pagers-"))
    try:
        site, _w, _o, _u, _m = _cal_fixture(root)
        # A week's page: the week of 16 March, with this week before it and
        # an empty week after.
        t = (site / "calendar" / "2026-W12.html").read_text(encoding="utf-8")
        navs = re.findall(r'<nav class="wknav[^"]*" aria-label="Other weeks">(.*?)</nav>', t)
        want = ('<a class="wkprev" href="/calendar"><span class="wkpw">&lsaquo; Previous Week</span>'
                '<span class="wkpd">Mar 9–14, 2026</span></a>'
                '<a class="wkhere" href="/calendar">This Week</a>'
                '<a class="wknext" href="/calendar/2026-W13"><span class="wkpw">Next Week &rsaquo;</span>'
                '<span class="wkpd">Mar 23–27, 2026</span></a>')
        assert navs == [want] and t.count('<hr class="calend">') == 1, f"the week of 16 March's pager (one, at the top) or the rule under the list: {navs}"
        assert "<h1>The Week of March 16–20, 2026</h1>" in t and \
            "<title>The Week of March 16–20, 2026 | Granite Record</title>" in t, (
            "the week's heading or title is not The Week of March 16–20, 2026")
        # The page's script, which draws the same pager and the Day view's.
        lean = re.search(r"<script>(\(function\(\)\{.*?)</script>", t, re.S).group(1)
        for w in ("Previous Week", "Next Week", ">This Week<", "Previous Day", "Next Day",
                  '"The Week of "'):
            assert w in lean, f"the Calendar's script does not write {w!r}"
        for w in ("The week before", "The week after", ">This week<", '"The week of "+label;'):
            assert w not in lean, f"the Calendar's script still writes {w!r}"
        # The floor's card, on the week and in Coming up: named, with no chip.
        wk11 = (site / "calendar.html").read_text(encoding="utf-8")
        floor = re.search(r'<details class="calmeet"[^>]*data-who="floor"[^>]*>.*?</summary>', wk11, re.S)
        assert floor and '<span class="calcmte">House Session Day</span>' in floor.group(0) \
            and "calkind" not in floor.group(0), (
            f"the floor's card is not House Session Day without a chip: {floor and floor.group(0)}")
        with contextlib.redirect_stdout(io.StringIO()):
            up = BP.calendar_html(site, today=_dt.date(2026, 3, 11), rows=_cal_rows())
        assert '<span class="calcmte">House Session Day</span>' in up and "calkind k-floor" not in up \
            and '<p class="calmore calall"><a href="calendar.html">See the full calendar</a></p>' in up, (
            "Coming up does not name the floor House Session Day, or does not end with See the "
            f"full calendar (D13): {re.search(r'<p class=.calmore calall.>.*?</p>', up)}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    # A session day's pager: the days either side by their dates, and its
    # week on the Calendar between them by the name the Calendar gives it.
    nav = "".join(SP.pager("H", "2026-02-19", "2026-02-12", "2026-03-05",
                           {"2026-W08": "February 16–20, 2026"}))
    got = re.sub(r'href="[^"]*"', 'href=""', nav)
    assert got == ('<a class="wkprev" href=""><span class="wkpw">&lsaquo; Previous Session Day</span>'
                   '<span class="wkpd">Thursday, February 12, 2026</span></a>'
                   '<a class="wkhere" href="">The Week of February 16–20, 2026</a>'
                   '<a class="wknext" href=""><span class="wkpw">Next Session Day &rsaquo;</span>'
                   '<span class="wkpd">Thursday, March 5, 2026</span></a>'), (
        f"a session day's pager reads {nav}")
    assert "".join(SP.pager("H", "2024-02-15", "", "2024-02-22", {})).count("<a ") == 1, (
        "a session day before the Calendar's first week links a week, or its first day a day before it")
    return "ok", (f"{len(files)} builders, scripts and words files write none of the old "
                  "labels; a week's page and the Calendar's script, a session day's pager "
                  "and Coming up say the new ones, and the floor is House Session Day")


@check("frontend", "study and statutory committees are on the calendar, named, and off until a reader ticks them")
def _calendar_study_committees():
    """The week of 21 September 2026 showed two sittings; the database held nine.

    proceedings.csv is keyed on bills, so the calendar drew bill business
    only, while its description said "Every hearing". Seven study and
    statutory committee meetings that week -- the Road Toll commission, the
    HHS Oversight Committee, the Commission on Aging -- were in db/ and read
    by nothing. The one study committee that was on it, HB 1763's on
    2 September, read "House -- committee not recorded".

    This writes a small copy of the two database files, and wants: the
    meetings read as rows in the database's own words, title-cased and
    labelled study or statutory from CommitteeStatus; a cancelled one marked,
    and not offered for anybody's calendar; the docket's committee-less row
    for the bill named from the committee the bill set up and folded into its
    meeting's card; the week page carrying a Study Committee box and a
    description that no longer says "Every"; and the box's memory wrapped so
    a blocked storage leaves the page whole.

    CHANGED ON 25 SEPTEMBER 2026, at the person's word: the box starts
    unticked ("each one is selected on by default aside from study
    committees"), and the page no longer says under its key which copy of the
    database the meetings came from ("you can remove the explanation"). So
    this wants the box off, and that sentence gone from the page -- the build
    still prints which copy it read.
    """
    import contextlib
    import datetime as _dt
    import io
    import build_calendar as BC
    here = Path(".").resolve()
    if not (here / "src/pages/bills.html").exists():
        return "skip", "bills.html is not here"

    def det(cid, year, bill, name, status):
        f = [""] * 28
        f[0], f[1], f[4], f[7], f[17] = cid, year, bill, name, status
        return "|".join(f)

    tmp = Path(tempfile.mkdtemp(prefix="gr-statstud-"))
    try:
        db = tmp / "db"
        db.mkdir()
        (db / "StatStudDetails.psv").write_text("\n".join([
            det("1740", "2026", "HB1763", "COMMITTEE TO STUDY SITING AND MAINTENANCE "
                "RULES REGARDING CERTAIN INTELLECTUAL AND DEVELOPMENTAL DISABILITY "
                "(IDD) AND ACQUIRED BRAIN DISORDER (ABD) COMMUNITY RESIDENCES",
                "Active Chaptered Study Committee"),
            det("62", "1969", "", "COMMITTEE ON LEGISLATOR ORIENTATION",
                "Active Statutory Committee"),
            det("9", "1991", "", "A REPEALED BOARD", "Repealed")]) + "\n",
            encoding="utf-8")
        (db / "StatStudMeetings.psv").write_text("\n".join([
            "|3023|1740|09/02/2026 10:00:00|GP Room 230  Regular Meeting||",
            "|3056|62|09/22/2026 10:00:00|SH Room 122-123  Regular Meeting||",
            "==CANCELLED==|3057|62|09/24/2026 13:00:00|==CANCELLED==SH Room 100  "
            "Regular Meeting||",
            "|3058|9|09/23/2026 10:00:00|LOB 101  Regular Meeting||",
            "|12|62|01/11/1993 10:00:00|RM103, ST||",
            # Venues the copy ran together, as it holds them: one the
            # General Court's schedule has, one only a printed notice has,
            # one neither has; a Teams passcode; and a type label of two
            # words that used to leave "Public" on the place.
            "|3080|62|09/30/2026 14:00:00|DHHSBrown BuildingConference Room 468129 "
            "Pleasant StreetConcord, NH  03301 Organizational Meeting||",
            "|3081|62|10/05/2026 10:00:00|NH Hospital Association125 Airport "
            "RdConcord, NH  Regular Meeting||",
            "|3082|62|10/06/2026 10:00:00|NH Fire Academy98 Smokey Bear Blvd., "
            "Classroom 1Concord, NH  Regular Meeting||",
            "|3083|62|10/07/2026 10:00:00|Dept of Justice, 1 Granite Place South, "
            "Concord, NH or Teams Meeting ID: 279 737 604 573 Passcode: zKPHQY "
            "Regular Meeting||",
            "|3084|62|10/08/2026 10:00:00|Claremont Savings Bank Community Center, "
            "152 South Street, Claremont Public Hearing||"]) + "\n", encoding="utf-8")
        (tmp / "schedule_pages").mkdir()
        (tmp / "schedule_pages" / "_events.json").write_text(json.dumps({"d": json.dumps([
            {"title": "COMMITTEE ON LEGISLATOR ORIENTATION : DHHS\r\nBrown Building\r\n"
                      "Conference Room 468\r\n129 Pleasant Street\r\nConcord, NH  03301",
             "start": "2026-09-30T14:00:00", "url": "eventDetails.aspx?event=3080&et=2"},
            # The same number at another time is another meeting: not taken.
            {"title": "COMMITTEE ON LEGISLATOR ORIENTATION : Somewhere Else, 1 Main Street",
             "start": "2026-10-06T09:00:00", "url": "eventDetails.aspx?event=3082&et=2"}])}),
            encoding="utf-8")
        (tmp / "meetings.json").write_text(json.dumps([
            {"date": "2026-10-05", "committee": "Committee on Legislator Orientation",
             "venue": "NH Hospital Association, 125 Airport Rd. Concord", "room": "",
             "bill": "", "noticed": "2026-09-18", "calendar": "2026/HC033"},
            {"date": "2026-10-05", "committee": "Committee on Legislator Orientation",
             "venue": "NH Hospital Assoc- iation, 125 Airport Rd.", "room": "",
             "bill": "", "noticed": "2026-09-11", "calendar": "2026/HC032"}]),
            encoding="utf-8")
        (db / "_manifest.json").write_text(json.dumps(
            {"StatStudMeetings": {"fetched": "2026-09-08T20:45:43"}}), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as said:
            rows, names, fetched = BC.statstud(tmp)
        assert fetched == "2026-09-08", f"the copy's date read as {fetched!r}"
        assert "1 study/statutory meetings left out" in said.getvalue(), (
            "a meeting of a committee labelled neither study nor statutory was "
            "not reported as left out")
        got = {(r["date"], r["committee"], r["kind"], r["time"], r["venue"]) for r in rows}
        orient = "Committee on Legislator Orientation"
        long = ("Committee to Study Siting and Maintenance Rules Regarding Certain "
                "Intellectual and Developmental Disability (IDD) and Acquired Brain "
                "Disorder (ABD) Community Residences")
        stat = "statutory committee"
        want = {("2026-09-02", long, "study committee", "10:00", "GP Room 230"),
                ("2026-09-22", orient, stat, "10:00", "SH Room 122-123"),
                ("2026-09-24", orient, "cancelled", "13:00", "SH Room 100"),
                # A VENUE THE COPY RAN TOGETHER IS NEVER PRINTED AS STORED:
                # "Room 468129" is Room 468 at 129 Pleasant Street. The
                # schedule's own text for that meeting where it has it; the
                # earliest printed notice that reads as a place; else none.
                ("2026-09-30", orient, stat, "14:00",
                 "DHHS, Brown Building, Conference Room 468, 129 Pleasant Street, "
                 "Concord, NH 03301"),
                ("2026-10-05", orient, stat, "10:00",
                 "NH Hospital Association, 125 Airport Rd. Concord"),
                ("2026-10-06", orient, stat, "10:00", ""),
                # Nor a passcode, a link or an email address.
                ("2026-10-07", orient, stat, "10:00", ""),
                ("2026-10-08", orient, stat, "10:00",
                 "Claremont Savings Bank Community Center, 152 South Street, Claremont")}
        assert got == want, (f"the database copy read as {sorted(got - want)}; "
                             f"missing {sorted(want - got)}")
        assert "Public hearing." in {r["note"] for r in rows}, (
            "a public hearing's type is not read whole")
        for v, ok in (("GP Room 230", "GP Room 230"), ("REMOTE Room 000", "Remote"),
                      ("McLane Middleton, 900 Elm Street, Manchester",
                       "McLane Middleton, 900 Elm Street, Manchester"),
                      ("BEAKingsman Room, 100 Main Street, Concord", ""),
                      # Room 1 at 125 Airport Road, with the break lost.
                      ("Foundation for Healthy Communities, Room 1125 Airport "
                       "Road, Concord", ""),
                      ("Department of Education, NH Room, 330 21 South Fruit Street", "")):
            assert BC.place(v) == ok, f"the venue {v!r} reads as {BC.place(v)!r}"
        assert BC.committee_name("COMMISSION TO STUDY THE USE OF OHRVS IN NEW "
                                 "HAMPSHIRE") == ("Commission to Study the Use of "
                                                  "OHRVs in New Hampshire")

        docket = {"term": "2025-2026", "bill": "HB1763", "body": "H",
                  "kind": "study committee", "date": "2026-09-02", "time": "",
                  "committee": "", "venue": ""}
        weeks = BC.weeks_from([docket] + rows, names=names)
        day = weeks["2026-W36"]["2026-09-02"]
        # No chamber in the key: the docket's row carries the BILL's chamber
        # and the database copy's none, and keyed on either they were two.
        one = BC.P.Meet("2026-09-02", "", long, "")
        assert list(day) == [one], (
            f"HB 1763's study committee on 2 September is {list(day)}, not one "
            "card under the committee's own name")
        assert {(r["time"], r["venue"]) for r in day[one]} == {
            ("10:00", "GP Room 230")}, "the docket's row did not take its meeting's time and room"

        site = tmp / "site"
        site.mkdir()
        shutil.copy(here / "src/pages/bills.html", site / "bills.html")
        order = sorted(weeks)
        with contextlib.redirect_stdout(io.StringIO()):
            for i, k in enumerate(order):
                BC.week_page(site, "https://graniterecord.org", k, weeks, order, i,
                             {}, {}, {}, [], _dt.date(2026, 9, 24), set(), study=True)
        t = (site / "calendar.html").read_text(encoding="utf-8")
        assert re.search(r'<label class="calcat k-study"><input type="checkbox" name="cat" '
                         r'value="study"><span class="cbx"', t), (
            "the week has no Study Committee box, or it starts ticked")
        assert "as copied on" not in t and "calsrc" not in t and "come from the General" not in t, (
            "the week still says which copy of the database its study committees came from")
        desc = re.search(r'name="description" content="([^"]*)"', t).group(1)
        assert "Every" not in desc and "study and statutory" in desc, (
            f"the description reads {desc!r}")
        cards = re.findall(r'<details class="calmeet"([^>]*)>', t)
        assert len(cards) == 2 and all('data-study=""' in c for c in cards), (
            f"this week's study committee cards are {cards}")
        assert sum('data-cancelled=""' in c for c in cards) == 1, (
            "the cancelled meeting is not marked cancelled")
        assert ">1 bill<" not in t and "(1 bill)" not in t, (
            "a meeting with no bill before it is counted as one bill")
        # A CANCELLED MEETING IS NOT A SITTING. The week of 13 January 2025
        # said "22 sittings on 5 days" with the Opioid Abatement commission's
        # cancelled meeting among the 22. This week holds one meeting that
        # sat and one that was cancelled, on two days. The week's lead says
        # no count at all now (F11, the person, 7 October 2026); the script's
        # count below is the one that leaves the cancelled meeting out.
        lead = re.search(r'<p class="src">([^<]*)</p>', t).group(1)
        assert lead == "", f"a week with a sitting still has a summary over it: {lead!r}"
        node = shutil.which("node") or shutil.which("node.exe")
        if node:
            # THE SCRIPT'S OWN COUNT over the two cards the page carries, one
            # that sat and one that was cancelled. It ran the old filter
            # script against two stand-in elements until 24 September 2026;
            # the Calendar page's script counts in tally() and countLine(),
            # off the cards' own attributes, so those run on the page's cards.
            go = tmp / "week.js"
            go.write_text("globalThis.document={getElementById:function(){return null;}};\n"
                          + _with_components(BC.WEEK_JS) + r"""
const C=globalThis.GRCAL, t=require("fs").readFileSync(process.argv[2],"utf8");
const view=t.slice(t.indexOf('<div class="calview"'),t.indexOf('<hr class="calend"'));
const cards=(view.match(new RegExp('<details class="cal'+'meet"[\\s\\S]*?</details>','g'))||[]).map(C.parseCard);
const on=Object.assign(C.defaults(),{cats:C.CATS.slice()});
process.stdout.write(C.countLine(C.tally(cards,on),"this week")+" | "
  +C.countLine(C.tally(cards,C.defaults()),"this week"));
""", encoding="utf-8")
            r = _run([node, str(go), str(site / "calendar.html")], capture_output=True,
                     text=True, encoding="utf-8", timeout=60)
            assert r.returncode == 0, (r.stdout or r.stderr).strip()[-300:]
            assert r.stdout == "1 meeting this week. | 1 study committee meeting is hidden.", (
                f"the week script counts {r.stdout!r} with one meeting cancelled, with the "
                "study committees shown and then as a new reader sees the week")
        js = BC.WEEK_JS
        assert re.search(r"try\{\s*if\(localStorage\.getItem", js) and \
            re.search(r"try\{\s*localStorage\.setItem", js), (
                "the toggle's memory is not wrapped in try/catch; a browser that "
                "blocks storage would stop the week's script")
        assert 'm.hasAttribute("data-cancelled")' in js, (
            "a cancelled meeting is offered for the reader's own calendar")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("three meetings read from the copy, named and labelled; a "
                  "cancelled one marked; HB 1763's row folded into its "
                  "committee's card; the box, off, no note of the copy, and a true description")


@check("frontend", "the built week hides the study committees as the script does, says how many "
       "once a week with the way to show them, and each card leads to its committee's page")
def _calendar_study_hidden_once():
    """The person, 17 October 2026: the calendar does not show study and
    statutory committees by default, because of the clutter. Until 18
    October the box started unticked but only the script hid the cards: the
    week's own HTML carried every one, so a reader without script, and
    everyone for the moment before it ran, saw them all; and with the script
    nearly every weekday said "4 study committee meetings are hidden."

    Here, over the database copy's shape: an active committee's meeting
    carries its page (build_calendar.study_page) and its card leads into the
    meeting there, an archived one's leads nowhere; the built week opens
    with the checkbox and the one line, a day of study committees alone
    says "Study committee meetings only." with a label for that box, and
    app.css hides the cards while the box is unticked; the script's day says
    the same, with its own "Show them", and its week line keeps the count,
    with "Show them" beside it while there is one (the R2 polish batch, 30
    October 2026, where a day said "No meetings shown.")."""
    import contextlib
    import datetime as _dt
    import io
    import build_calendar as BC
    here = Path(".").resolve()
    if not (here / "src/pages/bills.html").exists():
        return "skip", "bills.html is not here"

    def det(cid, name, status):
        f = [""] * 28
        f[0], f[1], f[7], f[17] = cid, "2020", name, status
        return "|".join(f)
    tmp = Path(tempfile.mkdtemp(prefix="gr-statstud-once-"))
    try:
        db = tmp / "db"
        db.mkdir()
        (db / "StatStudDetails.psv").write_text("\n".join([
            det("1451", "STATE COMMISSION ON AGING", "Active Statutory Committee"),
            det("44", "VETERANS HOME STUDY", "Archived Chaptered Study Committee")]) + "\n",
            encoding="utf-8")
        (db / "StatStudMeetings.psv").write_text("\n".join([
            "|5001|1451|10/12/2026 10:00:00|LOB Room 101  Regular Meeting||",
            "|5002|44|10/14/2026 13:00:00|LOB Room 102  Regular Meeting||"]) + "\n",
            encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            rows, names, _f = BC.statstud(tmp)
        page = {r["committee"]: r.get("page") for r in rows}
        assert page == {"State Commission on Aging": "committee/ss1451.html",
                        "Veterans Home Study": ""}, (
            f"the meetings' pages read as {page}: an active committee's is not its own, or an "
            "archived one, which has no page, was given one")
        bill = {"term": "2025-2026", "bill": "HB1", "body": "H", "kind": "hearing",
                "date": "2026-10-13", "time": "10:00", "committee": "Finance", "venue": "LOB 210"}
        weeks = BC.weeks_from([bill] + rows, names=names)
        site = tmp / "site"
        site.mkdir()
        shutil.copy(here / "src/pages/bills.html", site / "bills.html")
        order = sorted(weeks)
        with contextlib.redirect_stdout(io.StringIO()):
            for i, k in enumerate(order):
                BC.week_page(site, "https://graniterecord.org", k, weeks, order, i,
                             {}, {}, {}, [], _dt.date(2026, 10, 12), set(), study=True)
        t = (site / "calendar.html").read_text(encoding="utf-8")
        view = t[t.index('<div class="calview" id="calview">'):t.index('<hr class="calend"')]
        cards = re.findall(r'<details class="calmeet"[^>]*>.*?</details>', view, re.S)
        aging = [c for c in cards if "State Commission on Aging" in c]
        vets = [c for c in cards if "Veterans Home Study" in c]
        assert aging and 'href="committee/ss1451#day-2026-10-12"' in aging[0], (
            "the commission's card does not lead into its meeting on its own page: "
            + (aging[0][-300:] if aging else "no card"))
        assert vets and "committee/ss" not in vets[0], (
            "an archived committee's card links a page nobody writes")
        # ONCE A WEEK: the box, then the one line, then the days.
        assert view.startswith('<div class="calview" id="calview">'
                               '<input type="checkbox" class="calst" id="calst" aria-labelledby="calstl">'
                               '<p class="calstline"><span class="cs-off">2 study committee '
                               'meetings are hidden.</span>'), (
            "the built week does not open with the box and the one line counting its study "
            "committee meetings: " + view[:240])
        assert '<label for="calst" id="calstl"><span class="cs-off">Show them</span>' in view, (
            "the built week's line has no way to show them")
        days = re.findall(r'<div class="calday[^"]*" data-d="([^"]+)">(.*?)(?=<div class="calday|$)',
                          view, re.S)
        alone = {d for d, h in days if BC.STUDY_ONLY in h}
        assert BC.STUDY_ONLY == ('<p class="calempty calstonly">Study committee meetings only. '
                                 '<label for="calst">Show them</label></p>'), (
            "a built day of study committees alone does not say what it holds, with the box's "
            "own label to show them: " + BC.STUDY_ONLY)
        css = (here / "src/pages/app.css").read_text(encoding="utf-8")
        assert re.search(r"\.calstonly label\{|,\.calstonly label[,{]", css), (
            "the built day's Show them is not drawn as the week line's is, in the link colour")
        assert alone == {"2026-10-12", "2026-10-14"}, (
            f"the days of study committees alone that say nothing is shown are {sorted(alone)}; "
            "a day with a hearing on it must not say so")
        rest = view[view.index("</p>") + len("</p>"):]
        assert "is hidden." not in rest and "are hidden." not in rest, (
            "a day of the built week still says how many study committee meetings it hides")
        css = (here / "src/pages/app.css").read_text(encoding="utf-8")
        assert re.search(r'\.calst:not\(:checked\) ~ \.calday \.calmeet\[data-who="study"\]', css) \
            and re.search(r"\.calst:checked ~ \.calday \.calstonly", css), (
                "app.css no longer hides the built week's study committee cards while its box is "
                "unticked, or shows the day's 'Study committee meetings only.' while it is ticked")
        assert '<button type="button" class="calshowst" id="calshowst" hidden>' in t, (
            "the Calendar's bar has no Show them for the script to show")
        js = BC.WEEK_JS
        assert "showst.hidden=!(tl&&tl.study)" in js and 'value="study"]' in js, (
            "the script does not show Show them while study committee meetings are hidden, "
            "or it does not tick the box")
        node = shutil.which("node") or shutil.which("node.exe")
        if node:
            go = tmp / "week.js"
            go.write_text("globalThis.document={getElementById:function(){return null;}};\n"
                          + _with_components(BC.WEEK_JS) + r"""
const C=globalThis.GRCAL, t=require("fs").readFileSync(process.argv[2],"utf8");
const view=t.slice(t.indexOf('<div class="calview"'),t.indexOf('<hr class="calend"'));
const cards=(view.match(new RegExp('<details class="cal'+'meet"[\\s\\S]*?</details>','g'))||[]).map(C.parseCard);
const st=cards.filter(c=>c.who==="study");
process.stdout.write(JSON.stringify({day:C.emptyWords(st.slice(0,1),C.defaults()),
  html:C.emptyHtml(st.slice(0,1),C.defaults()),
  week:C.countLine(C.tally(cards,C.defaults()),"this week"),
  alone:C.countLine(C.tally(st,C.defaults()),"this week")}));
""", encoding="utf-8")
            r = _run([node, str(go), str(site / "calendar.html")], capture_output=True,
                     text=True, encoding="utf-8", timeout=60)
            assert r.returncode == 0, (r.stdout or r.stderr).strip()[-300:]
            got = json.loads(r.stdout)
            assert got["day"] == "Study committee meetings only.", (
                f"the script's day of study committees alone says {got['day']!r}")
            assert got["html"] == ('Study committee meetings only. <button type="button" '
                                   'class="calshowday">Show them<span class="sr"> (the study '
                                   'committee meetings)</span></button>'), (
                f"the script's day of study committees alone has no Show them: {got['html']!r}")
            assert got["alone"] == "2 study committee meetings are hidden.", (
                "a week of study committees alone speaks of a filter nobody set: "
                + repr(got["alone"]))
            assert got["week"] == "1 of 3 meetings shown. 2 study committee meetings are hidden.", (
                f"the script's week line says {got['week']!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("an active committee's card leads into its meeting on its page; the built week "
                  "hides the study cards behind one line and a box, a day of them alone says "
                  "so with Show them, and the script counts them once with Show them")


@check("frontend", "a calendar card links the calendar that first printed its notice, and a sitting its own journal")
def _calendar_document_links():
    """No calendar card and none of 1,601 sitting pages linked a source PDF.

    The addresses were on disk all along: archive/queue.csv names the viewer
    address of every calendar and journal fetched, and meetings.json names
    the calendar each notice was printed in. The traps are both about WHICH
    document. A notice is reprinted week after week, so the link is the
    calendar that printed it first. And a sitting's journal is found by the
    number its own rows cite, never by its date: the December organization
    day opens the next year's numbering while a December session in an odd
    year does not, so "HJ 19" of 17 December 2025 is filed under 2025 and a
    date-based rule would have sent it to 2026's.

    This writes a queue and a meetings.json and wants the earliest notice
    linked, a number answered only where the file's own date agrees, an
    ambiguous number answering nothing, and the card drawing the link.
    """
    import html as _h
    import build_calendar as BC
    import build_pages as BP
    import build_site_v2 as B2
    tmp = Path(tempfile.mkdtemp(prefix="gr-docs-"))
    try:
        V = "https://gc.nh.gov/house/calendars_journals/viewer.aspx?fileName="
        q = tmp / "queue.csv"
        rows = [("H", "journal", "2025", "HJ 19 December 17, 2025.pdf",
                 V + "journals%5C2025%5CHJ%2019", r"journals\2025\HJ 19 December 17, 2025.pdf"),
                ("H", "journal", "2026", "HJ 16 August 19, 2026.pdf",
                 V + "journals%5C2026%5CHJ%2016", r"journals\2026\HJ 16 August 19, 2026.pdf"),
                ("S", "journal", "2026", "SJ 15.pdf",
                 V + "journals%5C2026%5CSJ%2015", r"journals_senate\2026\SJ 15.pdf"),
                ("H", "journal", "2012", "HJ 5 March 1, 2012.pdf",
                 V + "journals%5C2012%5CHJ%205", r"journals\2012\HJ 5 March 1, 2012.pdf"),
                ("H", "calendar", "2026", "HC 29.pdf", V + "calendars%5C2026%5CHC%2029.pdf",
                 r"calendars\2026\HC029.pdf"),
                ("H", "calendar", "2026", "HC 32.pdf", V + "calendars%5C2026%5CHC%2032.pdf",
                 r"calendars\2026\HC032.pdf")]
        with q.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["chamber", "kind", "year", "name", "url", "path", "state",
                        "attempts", "error", "bytes", "fetched"])
            for r in rows:
                w.writerow(list(r) + ["held", "0", "", "1", "2026-09-08"])
        jk = B2.journal_keys_from_queue(str(q))
        assert set(jk) == {"HJ 19 2025", "HJ 16 2026", "SJ 15 2026"}, (
            f"journal keys read as {sorted(jk)}: 2025 on, keyed by number and folder year")
        assert B2.journal_url("2025-12-17", "HJ 19", jk).endswith("HJ%2019"), (
            "a December session in an odd year is not found in its own year's journals")
        assert B2.journal_url("2026-08-19", "HJ 16", jk).endswith("HJ%2016")
        assert B2.journal_url("2026-08-20", "HJ 16", jk) == "", (
            "a sitting was linked to a journal whose own name gives another date")
        assert B2.journal_url("2026-08-19", "SJ 15", jk).endswith("SJ%2015"), (
            "a journal whose name states no date is not found by its number and series")
        assert B2.journal_url("2026-08-19", "", jk) == ""

        mj = tmp / "meetings.json"
        mj.write_text(json.dumps([
            {"date": "2026-09-25", "committee": "Solid Waste Working Group", "bill": "",
             "calendar": "2026/HC032", "noticed": "2026-09-04"},
            {"date": "2026-09-25", "committee": "Solid Waste Working Group", "bill": "",
             "calendar": "2026/HC029", "noticed": "2026-08-07"},
            {"date": "2026-09-24", "committee": "Commerce", "bill": "HB1753",
             "calendar": "2026/HC032", "noticed": "2026-09-04"}]), encoding="utf-8")
        notices = BC.first_notices(mj)
        assert notices[1].get(("2026-09-25", "solid waste working group")) == "HC 29 2026", (
            f"a reprinted notice links {notices[1]}, not the calendar that printed it first")
        weeks = BC.weeks_from([
            {"term": "2025-2026", "bill": "HB1753", "body": "H", "kind": "executive session",
             "date": "2026-09-24", "time": "10:30", "committee": "Commerce", "venue": "GP 228"},
            {"study": True, "bill": "", "kind": "statutory committee", "date": "2026-09-25",
             "time": "09:30", "committee": "Solid Waste Working Group", "venue": "NHDES"},
            {"term": "2025-2026", "bill": "HB9", "body": "H", "kind": "floor debate",
             "date": "2026-08-19", "time": "", "committee": "", "venue": ""}], names={})
        cal_urls = B2.calendar_keys_from_queue(str(q))
        docs, n_cal, n_jnl = BC.doc_links(weeks, cal_urls, notices, jk,
                                          {("H", "2026-08-19"): "HJ 16"})
        assert docs.get(BP.Meet("2026-09-24", "H", "Commerce", "")) == [
            ("House Calendar 32", V + "calendars%5C2026%5CHC%2032.pdf")], docs
        assert docs.get(BP.Meet("2026-09-25", "", "Solid Waste Working Group", "")) == [
            ("House Calendar 29", V + "calendars%5C2026%5CHC%2029.pdf")], docs
        assert docs.get(BP.Meet("2026-08-19", "H", "House floor", ""),
                        [("", "")])[0][0] == "House Journal 16", docs
        assert (n_cal, n_jnl) == (2, 1), (n_cal, n_jnl)
        key = BP.Meet("2026-09-24", "H", "Commerce", "")
        page, _m = BP.cal_days({key.date: [key]}, {key: weeks["2026-W39"][key.date][key]},
                               {}, {}, {}, lambda d: (d, ""), _h.escape, docs=docs)
        # In a new tab and marked as going out (F12, 7 October 2026).
        assert f'<a class="out" href="{_h.escape(V)}calendars%5C2026%5CHC%2032.pdf" ' \
               'target="_blank" rel="noopener">House Calendar 32 (PDF)</a>' in page, (
                   "the card does not draw its notice's link, in a new tab")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("the first notice linked, journals found by number with their "
                  "own date agreeing, and the link drawn on the card")


@check("calendar", "a study or statutory meeting links the recording named for it, and no other")
def _study_recordings():
    """A meeting with no bill has no page to lead to, so its card leads to its
    recording: the one of its own day whose committee's words and the
    meeting's mostly agree both ways. Measured on the recordings of September
    2026: the Long Range Capital Planning and Utilization Committee and the
    Joint Committee on Tax Expenditure Review of 28 September take theirs;
    "JLCAR Administrative Rules" is the Administrative Rules committee;
    "House Education" does not take a long oversight committee's name that
    contains the word; the House Special Committee on COVID Response Efficacy
    fits nothing; a recording already on a bill's sitting is that sitting's;
    a meeting after the build takes nothing; and two rows of one name are one
    meeting held twice in the database, and share it. The card draws the
    link; a card with none draws nothing."""
    import html as _h
    import build_calendar as BC
    import build_pages as BP

    def meet(date, name):
        return {"study": True, "bill": "", "kind": "statutory committee", "date": date,
                "time": "10:00", "committee": name, "venue": "LOB 101", "note": ""}

    def vids(date, *pairs):
        return {date: [(v, f"{t} ({date})", BC._rec_words(t)) for v, t in pairs]}
    oversight = "Legislative Oversight Committee for the Education Improvement and Assessment Program"
    rows = [meet("2026-09-28", "Long Range Capital Planning and Utilization Committee"),
            meet("2026-09-28", "Joint Committee on Tax Expenditure Review"),
            meet("2026-10-15", "Administrative Rules"),
            meet("2026-09-25", oversight),
            meet("2026-09-18", "Fiscal Committee"), meet("2026-09-18", "Fiscal Committee"),
            meet("2026-11-16", "Long Range Capital Planning and Utilization Committee")]
    videos = {}
    for d in (vids("2026-09-28", ("uJJBjxFc4jI", "Long Range Capital Planning and Utilization "
                                                 "Committee"),
                   ("XFczMcnO4RM", "Joint Committee on Tax Expenditure Review")),
              vids("2026-10-15", ("kn9s8YRu8VA", "JLCAR Administrative Rules")),
              vids("2026-09-25", ("aaaaaaaaaaa", "House Education"),
                   ("PiFmlIP7qOE", "House Special Committee on COVID Response Efficacy")),
              vids("2026-09-18", ("bbbbbbbbbbb", "Fiscal Committee"),
                   ("qYTXGQYaj8k", "Fiscal Committee")),
              vids("2026-11-16", ("4LN-zepbriM", "Long Range Capital Planning and Utilization "
                                                 "Committee"))):
        videos.update(d)
    linked, unmatched = BC.study_recordings(rows, videos, {"bbbbbbbbbbb"}, "2026-10-20")
    got = [(r["date"], r["committee"][:20], r.get("video_id", "")) for r in rows]
    assert got == [("2026-09-28", "Long Range Capital P", "uJJBjxFc4jI"),
                   ("2026-09-28", "Joint Committee on T", "XFczMcnO4RM"),
                   ("2026-10-15", "Administrative Rules", "kn9s8YRu8VA"),
                   ("2026-09-25", oversight[:20], ""),
                   ("2026-09-18", "Fiscal Committee", "qYTXGQYaj8k"),
                   ("2026-09-18", "Fiscal Committee", "qYTXGQYaj8k"),
                   ("2026-11-16", "Long Range Capital P", "")], got
    assert {t for _d, t in unmatched} == {"House Education (2026-09-25)",
                                          "House Special Committee on COVID Response Efficacy "
                                          "(2026-09-25)"}, unmatched
    weeks = BC.weeks_from(rows[:1] + [meet("2026-09-29", "Fiscal Committee")], names={})
    for date, name, want in (("2026-09-28", rows[0]["committee"], True),
                             ("2026-09-29", "Fiscal Committee", False)):
        key = BP.Meet(date, "", name, "")
        wk = BC.week_key(__import__("datetime").date.fromisoformat(date))
        page, _m = BP.cal_days({date: [key]}, {key: weeks[wk][date][key]}, {}, {}, {},
                               lambda d: (d, ""), _h.escape)
        has = 'href="https://www.youtube.com/watch?v=uJJBjxFc4jI"' in page and \
            "The recording, on YouTube</a>" in page
        assert has == want, (name, page[-400:])
    return "ok", ("recordings found by day and by committee both ways; none borrowed from a "
                  "bill's sitting, guessed between two committees, or given ahead of the meeting")


@check("frontend", "a House and a Senate committee of one name are two cards, each linking its own page, and a committee of conference is one bill's")
def _calendar_chambers():
    """Fifty calendar cards were two chambers' committees drawn as one.

    build_pages.meeting_key grouped a day's rows on the committee's name
    alone, and six names belong to both chambers. So 28 January 2025's
    "Finance" card held House Finance's 11:00 work session on HB 519 in LOB
    210-211 and Senate Finance's hearings on SB 64, 113, 114 and 117 in SH
    103, and the calendar carried 50 such cards, data-body "H S". The link to
    the committee's page was keyed the same way, so the second committee of
    a name overwrote the first: 168 single-chamber cards -- House Judiciary
    on 15 January 2025 among them -- linked to the Senate committee's page.
    The Calendar page's picker listed "Judiciary" once, and picking it showed
    both. Found by two reviewers on 25 September 2026, and live on the home
    page's Coming up, which shares the helpers.

    A committee of conference was keyed the same way and wrong the other way
    round: one "Committee of conference" card a day held every bill's
    conference in the building, while the Senate docket's notice of SB 14's
    conference, which names no committee, reached the calendar under Senate
    Judiciary's name and link. House Rule 50 says the conferees on a bill
    meet jointly, and each bill's conference is noticed on its own docket at
    its own time, so it is one card per bill per day, both chambers'.

    This draws those days from rows written here and holds the grouping, the
    names, the chambers, the links, the picker's list, the home rail and --
    in node, where it is on PATH -- the page script's picker to it.
    """
    import contextlib
    import datetime as _dt
    import io
    import build_calendar as BC
    import build_pages as BP
    here = Path(".").resolve()
    if not (here / "src/pages/bills.html").exists():
        return "skip", "bills.html is not here"
    M = BP.Meet

    def r(d, bill, body, kind, time, cmte, venue=""):
        return {"term": "2025-2026", "bill": bill, "body": body, "kind": kind,
                "date": d, "time": time, "committee": cmte, "venue": venue}
    rows = [
        r("2025-01-28", "HB519", "H", "work session", "11:00", "Finance", "LOB 210-211"),
        r("2025-01-28", "SB64", "S", "public hearing", "13:15", "Finance", "SH 103"),
        r("2025-01-28", "SB113", "S", "public hearing", "13:30", "Finance", "SH 103"),
        r("2025-01-15", "HB88", "H", "public hearing", "13:00", "Judiciary", "LOB 206-208"),
        # SB 14's conference from the Senate docket, carrying Senate
        # Judiciary's name, and from its recording with no name or time.
        r("2025-06-16", "SB14", "S", "committee of conference", "12:00", "Judiciary", "SH 100"),
        r("2025-06-16", "SB14", "S", "committee of conference", "", ""),
        r("2025-06-16", "HB2", "H", "committee of conference", "", ""),
        r("2025-06-16", "HB1", "H", "committee of conference", "", ""),
        # One House conference in the floor index twice and nowhere timed, as
        # HB 1709's on 26 May 2026 is: a video of five bills' conferences
        # and one of its own. Its card listed the bill twice, "2 bills".
        r("2025-06-17", "HB1709", "H", "committee of conference", "", ""),
        r("2025-06-17", "HB1709", "H", "committee of conference", "", ""),
        # Senate Judiciary sat that day too, on a House bill.
        r("2025-06-16", "HB400", "S", "public hearing", "10:00", "Judiciary", "SH 100"),
        # A statutory committee: the database copy's row has no chamber and
        # the docket's carries the bill's. One committee, one card.
        {"study": True, "bill": "", "kind": "statutory committee", "date": "2025-06-16",
         "time": "09:00", "committee": "Commission on Aging", "venue": "GP 230",
         "note": "Regular meeting.", "body": ""},
        r("2025-06-16", "HB1763", "H", "study committee", "", "Commission on Aging"),
    ]
    weeks = BC.weeks_from(rows, names={})
    jan = BC.in_order(weeks["2025-W05"]["2025-01-28"])
    assert jan == [M("2025-01-28", "H", "Finance", ""), M("2025-01-28", "S", "Finance", "")], (
        f"House and Senate Finance on 28 January are keyed {jan}")
    june = weeks["2025-W25"]["2025-06-16"]
    order = BC.in_order(june)
    want = [M("2025-06-16", "", "Commission on Aging", ""), M("2025-06-16", "S", "Judiciary", ""),
            M("2025-06-16", "", BP.CONFERENCE, "SB14"), M("2025-06-16", "", BP.CONFERENCE, "HB1"),
            M("2025-06-16", "", BP.CONFERENCE, "HB2")]
    assert order == want, f"16 June is keyed {order}"
    assert {x["bill"] for x in june[want[1]]} == {"HB400"}, (
        "SB 14's conference was drawn as a sitting of Senate Judiciary")
    assert [(x["time"], x["venue"]) for x in june[want[2]]] == [("12:00", "SH 100")], (
        f"SB 14's conference card holds {june[want[2]]}: its notice and its "
        "recording are one sitting, listed once, at the notice's time")
    assert len(june[want[0]]) == 2, "the statutory committee was split by the docket row's chamber"
    twice = weeks["2025-W25"]["2025-06-17"]
    assert list(twice) == [M("2025-06-17", "", BP.CONFERENCE, "HB1709")] \
        and len(twice[list(twice)[0]]) == 1, (
            f"HB 1709's conference, recorded twice and timed nowhere, is {dict(twice)}: "
            "one sitting, listed once")

    tmp = Path(tempfile.mkdtemp(prefix="gr-chambers-"))
    try:
        site = tmp / "site"
        site.mkdir()
        shutil.copy(here / "src/pages/bills.html", site / "bills.html")
        (site / "components.js").write_text(_components_js(here), encoding="utf-8", newline="\n")
        (site / "committees.json").write_text(json.dumps([
            {"code": "H34", "name": "Finance", "chamber": "H"},
            {"code": "S07", "name": "Finance", "chamber": "S"},
            {"code": "H10", "name": "Judiciary", "chamber": "H"},
            {"code": "S10", "name": "Judiciary", "chamber": "S"}]), encoding="utf-8")
        code = BP.committee_codes(site)
        assert code == {("H", "finance"): "H34", ("S", "finance"): "S07",
                        ("H", "judiciary"): "H10", ("S", "judiciary"): "S10"}, code
        today = _dt.date(2025, 1, 28)
        BC.every_week(weeks, today)
        wk = sorted(weeks)
        with contextlib.redirect_stdout(io.StringIO()):
            for i, k in enumerate(wk):
                BC.week_page(site, "https://graniterecord.org", k, weeks, wk, i,
                             {}, {}, code, [], today, set())
            BC.month_files(site, weeks, wk, {}, {}, code, today)

        def cards(page):
            t = (site / page).read_text(encoding="utf-8")
            t = t[t.index('<div class="calview" id="calview">'):t.index('<hr class="calend"')]
            out = {}
            for m in re.finditer(r'<details class="calmeet"([^>]*)>(.*?)</details>', t, re.S):
                a = dict(re.findall(r' data-([a-z]+)="([^"]*)"', m.group(1)))
                name = re.search(r'<span class="calcmte">([^<]*)</span>', m.group(2)).group(1)
                # The address the host serves since 12 October 2026 (shell.clean_links).
                link = re.search(r'href="committee/([A-Za-z0-9]+)(?:\.html)?#day-', m.group(2))
                out[name] = dict(a, link=link.group(1) if link else "",
                                 items=len(re.findall(r'<a class="cbn"', m.group(2))), html=m.group(2))
            return out
        c05, c03, c25 = cards("calendar.html"), cards("calendar/2025-W03.html"), cards("calendar/2025-W25.html")
        got = {n: (c["body"], c["link"], c["bills"]) for n, c in c05.items()}
        assert got == {"House Finance": ("H", "H34", "HB519"),
                       "Senate Finance": ("S", "S07", "SB113 SB64")}, (
            f"28 January 2025 draws {got}: two committees, each under its own "
            "chamber's name and linking its own chamber's page")
        assert (c03.get("House Judiciary") or {}).get("link") == "H10", (
            f"House Judiciary on 15 January links {c03}, not committee/H10")
        sj = c25.get("Senate Judiciary") or {}
        assert sj.get("link") == "S10" and sj.get("bills") == "HB400" and sj.get("kinds") == "hearing", (
            f"Senate Judiciary on 16 June is {sj}")
        conf = {n: c for n, c in c25.items() if n.startswith(BP.CONFERENCE)}
        assert sorted(conf) == ["Committee of conference on HB 1", "Committee of conference on HB 1709",
                                "Committee of conference on HB 2",
                                "Committee of conference on SB 14"], sorted(c25)
        for n, c in conf.items():
            assert c["body"] == "H S" and c.get("pick") == BP.CONFERENCE and not c["link"] \
                and c["items"] == 1 and c["who"] == "standing", (
                    f"{n}: data-body {c['body']!r}, data-pick {c.get('pick')!r}, link "
                    f"{c['link']!r}, {c['items']} bills listed -- a conference is both "
                    "chambers', one bill's, and no committee's page")
        sb14 = conf["Committee of conference on SB 14"]
        # The room in words since 25 October 2026 (S7): the clerk's "SH 100" is
        # "State House 100" on the card and in the entry it adds to a calendar.
        assert sb14.get("time") == "12:00" and sb14.get("venue") == "State House 100" \
            and "(2 bills)" not in sb14["html"], f"SB 14's conference card: {sb14}"
        hb1709 = conf["Committee of conference on HB 1709"]
        assert '<span class="calcount">1 bill</span>' in hb1709["html"] \
            and "2 bills" not in hb1709["html"], (
                f"HB 1709's conference card counts its two recordings as two bills: {hb1709['html']}")
        joint = [n for c_ in (c03, c05, c25) for n, c in c_.items()
                 if " " in c["body"] and not n.startswith(BP.CONFERENCE)]
        assert not joint, f"cards drawn for both chambers that are not a conference: {joint}"
        assert "Commission on Aging" in c25 and "pick" not in c25["Commission on Aging"], sorted(c25)

        names = json.loads((site / "calendar" / "data" / "committees.json").read_text(encoding="utf-8"))
        for n in (["House Finance", "standing", "H"], ["Senate Finance", "standing", "S"],
                  ["House Judiciary", "standing", "H"], ["Senate Judiciary", "standing", "S"],
                  ["Committee of conference", "standing", "H S"]):
            assert n in names, f"the picker's list has no {n}: {names}"
        bare = [n for n in names if n[0] in ("Finance", "Judiciary")
                or n[0].startswith(BP.CONFERENCE + " on")]
        assert not bare, f"the picker lists {bare}, which name no one committee"

        # The home page's Coming up, drawn by the same helpers.
        for day, want_rail in ((_dt.date(2025, 1, 28), {"house finance": "H34", "senate finance": "S07"}),
                               (_dt.date(2025, 6, 16), {"senate judiciary": "S10"})):
            with contextlib.redirect_stdout(io.StringIO()):
                page = BP.calendar_html(site, today=day, rows=rows)
            rail = {m.group(1): (re.search(r'href="committee/([A-Za-z0-9]+)\.html', m.group(2)) or [None, ""])[1]
                    for m in re.finditer(r'<details class="calmeet"[^>]*? data-cmte="([^"]*)"[^>]*>(.*?)</details>',
                                         page, re.S)}
            for k, v in want_rail.items():
                assert rail.get(k) == v, f"Coming up on {day}: {rail}"
            assert not any(k in rail for k in ("finance", "judiciary")), (
                f"Coming up on {day} still draws a committee without its chamber: {rail}")

        node = _cal_node()
        if not node:
            return "ok", ("two Finances and two Judiciaries kept apart, each linking its own "
                          "page; conferences one a bill; node not on PATH, so the picker was not run")
        (tmp / "minidom.js").write_text(_CAL_DOM, encoding="utf-8")
        (tmp / "drive.js").write_text(_CAL_CHAMBER_DRIVE, encoding="utf-8")
        rr = _run([node, str(tmp / "drive.js"), str(site)], capture_output=True, text=True, timeout=120)
        out = (rr.stdout or "") + (rr.stderr or "")
        assert rr.returncode == 0 and out.strip().endswith("OK"), out.strip()[-1500:]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("House and Senate Finance on 28 January 2025 are two cards linking H34 and "
                  "S07; House Judiciary links H10; SB 14's conference is one card, both "
                  "chambers', and not Senate Judiciary's; the picker lists each and picks one")


@check("frontend", "a calendar card counts each bill once, however many items it has that day")
def _calendar_counts_bills():
    """House Housing on 21 January 2025 heard eight bills and voted on five
    of them after, and its card said "(13 bills)" over the eight it listed.

    build_pages.cal_days counted the day's rows, and a bill heard and then
    voted on is two rows: 250 of the 1,883 cards on the Calendar, in its
    month files and on the home page's Coming up stated more bills than they
    held -- House Election Law the same day "(8 bills)" over four, House
    Commerce on 18 February 2026 "(53 bills)" over 37. app.js's
    calendarBlock, the committee page's Upcoming session, counted the same
    way; and the week's lead counted a bill once a day, so HB 511, heard by
    Criminal Justice on the 22nd and voted on the 24th, was two of the bills
    the week "covered" -- 33 of 98 weeks' leads overstated. The rows below
    are proceedings.csv's own for those days. (The week's lead counts
    nothing since 7 October 2026, F11: the person had the summary removed.)

    The items stay as they are -- each in its own slot, HB 60 under the
    hearing and again under the executive session -- and only the count
    changes. Run on the card, the week page, the month file, the home rail
    and, where node is on PATH, calendarBlock.
    """
    import contextlib
    import datetime as _dt
    import html as _h
    import io
    import build_calendar as BC
    import build_pages as BP
    here = Path(".").resolve()
    if not (here / "src/pages/bills.html").exists():
        return "skip", "bills.html is not here"

    def r(d, bill, kind, time, cmte, venue):
        return {"term": "2025-2026", "bill": bill, "body": "H", "kind": kind,
                "date": d, "time": time, "committee": cmte, "venue": venue}
    H, E, X = "public hearing", "executive session", "LOB 210-211"
    rows = [r("2025-01-21", b, k, t, "Housing", X) for b, k, t in (
        ("HB60", H, "10:00"), ("HB60", E, "10:00"), ("HB351", H, "11:00"),
        ("HB351", E, "11:00"), ("HB65", H, "11:30"), ("HB309", H, "13:00"),
        ("HB309", E, "13:00"), ("HB296", H, "13:30"), ("HB342", H, "14:00"),
        ("HB444", H, "14:30"), ("HB444", E, "14:30"), ("HB399", H, "15:00"),
        ("HB399", E, "15:00"))]
    rows += [r("2025-01-21", b, k, t, "Election Law", "LOB 306-308") for b, k, t in (
        ("HB67", H, "10:20"), ("HB261", H, "10:50"), ("HB261", E, "10:50"),
        ("HB340", H, "11:00"), ("HB160", H, "11:30"), ("HB160", E, "11:45"),
        ("HB340", E, "11:45"), ("HB67", E, "11:45"))]
    rows += [r("2025-01-22", "HB511", H, "15:30", "Criminal Justice and Public Safety", "LOB 301-303"),
             r("2025-01-24", "HB511", E, "08:00", "Criminal Justice and Public Safety", "LOB 301-303")]
    weeks = BC.weeks_from(rows, names={})

    def card(html, name):
        for m in re.finditer(r'<details class="calmeet"[^>]*>(.*?)</details>', html, re.S):
            if f'<span class="calcmte">{name}</span>' in m.group(1):
                c = m.group(1)
                return (re.search(r'<span class="calcount">([^<]*)</span>', c).group(1),
                        len(re.findall(r'<a class="cbn"', c)))
        return None

    day = weeks["2025-W04"]["2025-01-21"]
    html, _m = BP.cal_days({"2025-01-21": BC.in_order(day)}, day, {}, {}, {},
                           lambda d: (d, ""), _h.escape)
    assert card(html, "House Housing") == ("(8 bills)", 13), (
        f"House Housing on 21 January 2025 is {card(html, 'House Housing')}: "
        "wanted '(8 bills)' over its thirteen items")
    assert card(html, "House Election Law") == ("(4 bills)", 8), (
        f"House Election Law on 21 January 2025 is {card(html, 'House Election Law')}")

    tmp = Path(tempfile.mkdtemp(prefix="gr-calcount-"))
    try:
        site = tmp / "site"
        site.mkdir()
        shutil.copy(here / "src/pages/bills.html", site / "bills.html")
        today = _dt.date(2025, 1, 21)
        BC.every_week(weeks, today)
        wk = sorted(weeks)
        with contextlib.redirect_stdout(io.StringIO()):
            for i, k in enumerate(wk):
                BC.week_page(site, "https://graniterecord.org", k, weeks, wk, i,
                             {}, {}, {}, [], today, set())
            BC.month_files(site, weeks, wk, {}, {}, {}, today)
        page = (site / "calendar.html").read_text(encoding="utf-8")
        assert card(page, "House Housing") == ("(8 bills)", 13), (
            f"the week page's House Housing is {card(page, 'House Housing')}")
        lead = re.search(r'<p class="src">([^<]*)</p>', page).group(1)
        assert lead == "", f"a week with sittings still has a summary over it: {lead!r}"
        month = json.loads((site / "calendar" / "data" / "2025-01.json").read_text(encoding="utf-8"))
        assert card(month["days"]["2025-01-21"], "House Housing") == ("(8 bills)", 13), (
            "the month file's House Housing is "
            f"{card(month['days']['2025-01-21'], 'House Housing')}")
        assert month["weeks"]["2025-W04"]["lead"] == "", month["weeks"]["2025-W04"]
        with contextlib.redirect_stdout(io.StringIO()):
            rail = BP.calendar_html(site, today=today, rows=rows)
        assert card(rail, "House Housing") == ("(8 bills)", 13), (
            f"Coming up's House Housing is {card(rail, 'House Housing')}")
        assert "13 bills" not in rail and "(8 bills)" in rail, "Coming up still counts items"

        node = _cal_node()
        js, stub = here / "src/pages/app.js", here / "tests/dom_stub.js"
        if not (node and js.exists() and stub.exists()):
            return "ok", ("House Housing says (8 bills) over its thirteen items on the card, the "
                          "week, the month file and Coming up; node not on PATH, so calendarBlock "
                          "was not run")
        up = [{"date": x["date"], "time": x["time"], "bill": x["bill"], "term": x["term"],
               "committee": x["committee"], "what": x["kind"], "venue": x["venue"]}
              for x in rows if x["committee"] == "Housing"]
        (tmp / "page.js").write_text(_with_components(js.read_text(encoding="utf-8")), encoding="utf-8")
        (tmp / "stub.js").write_text(stub.read_text(encoding="utf-8"), encoding="utf-8")
        (tmp / "up.json").write_text(json.dumps(up), encoding="utf-8")
        (tmp / "go.js").write_text("""
require("./stub.js");
const fs = require("fs");
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8") + "; ({calendarBlock});"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const h = s.calendarBlock(JSON.parse(fs.readFileSync("./up.json", "utf8")), "Upcoming session");
process.stdout.write(JSON.stringify({count: (h.match(/<span class="calcount">([^<]*)<\\/span>/) || [])[1] || "",
  items: (h.match(/<a class="cbn"/g) || []).length}));
""", encoding="utf-8")
        rr = _run([node, "go.js"], cwd=tmp, capture_output=True, text=True, timeout=60)
        assert rr.returncode == 0, (rr.stdout or rr.stderr).strip()[-300:]
        got = json.loads(rr.stdout)
        assert got == {"count": "8 bills", "items": 13}, (
            f"a committee page's Upcoming session draws House Housing as {got}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("House Housing on 21 January 2025 says (8 bills) over its thirteen items on the "
                  "card, the week, the month file, Coming up and a committee page")


@check("frontend", "every time the Calendar, Coming up and a committee's Upcoming session print reads 9:00 AM, alike in all three renderers")
def _calendar_clock():
    """"I'd also prefer if times were listed with AM and PM instead of 13:00."

    The person, 25 September 2026. A time is printed by three renderers --
    build_pages.cal_days for the week pages, the month files and the home
    page's Coming up; the Calendar page's own script for the week at a
    glance and the preview; app.js's calendarBlock for a committee page --
    and all three tell it with the component clock(), components.py's in
    Python and components.js's in the browser, which _components_agree holds
    to one answer (noon is 12:00 PM, midnight 12:00 AM, and anything that is
    not a time comes back as it was). This holds the Calendar's script to
    that one rather than a copy of its own, a span to 10:00 AM-12:15 PM, and
    the time each entry of the week at a glance starts. Then it reads what the fixture's
    pages print and wants every time in that form, while the record's own
    "13:30" stays in data-time and data-last, where the script and the
    add-to-calendar links read it.
    """
    import contextlib
    import datetime as _dt
    import html as _h
    import io
    import build_pages as BP
    nb = "\u00a0"
    # clock() itself is a component, held to one answer in Python and in the
    # browser, these times among its cases, by _components_agree.
    assert BP.clock_span("10:00", "12:15") == f"10:00{nb}AM\u201312:15{nb}PM" \
        and BP.clock_span("09:00", "09:00") == f"9:00{nb}AM", BP.clock_span("10:00", "12:15")
    shape = re.compile(r"^\d{1,2}:\d\d" + nb + r"(AM|PM)(\u2013\d{1,2}:\d\d" + nb + r"(AM|PM))?$")
    if not Path("src/pages/bills.html").exists():
        return "skip", "bills.html is not here"
    root = Path(tempfile.mkdtemp(prefix="gr-calclock-"))
    try:
        site, _w, _o, _u, _m = _cal_fixture(root)
        texts = {"the week page": (site / "calendar.html").read_text(encoding="utf-8")}
        for f in sorted((site / "calendar" / "data").glob("2026-*.json")):
            texts[f"calendar/data/{f.name}"] = "".join(
                json.loads(f.read_text(encoding="utf-8"))["days"].values())
        with contextlib.redirect_stdout(io.StringIO()):
            texts["Coming up"] = BP.calendar_html(site, today=_dt.date(2026, 3, 10), rows=_cal_rows())
        seen = 0
        for where, t in texts.items():
            printed = [_h.unescape(x) for x in re.findall(r'<span class="caltime">([^<]*)</span>', t)]
            bad = [x for x in printed if not shape.match(x)]
            assert printed and not bad, f"{where} prints a time as {bad or 'nothing'}"
            seen += len(printed)
            stamps = re.findall(r' data-(?:time|last)="([^"]*)"',
                                "".join(re.findall(r'<details class="calmeet"[^>]*>', t)))
            assert stamps and all(re.fullmatch(r"\d\d:\d\d", x) for x in stamps), (
                f"{where}'s cards no longer carry the record's own time for the script: {stamps[:4]}")
        assert f"10:00{nb}AM\u20131:00{nb}PM" in texts["the week page"], (
            "House Judiciary's hearing at 10:00 and vote at 13:00 are not one span, 10:00 AM-1:00 PM")
        node = _cal_node()
        js, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
        if not (node and js.exists() and stub.exists()):
            return "ok", f"{seen} times in three kinds of page; node not on PATH, so the scripts were not run"
        import build_calendar as BC
        (root / "page.js").write_text(_with_components(_source(js)),
                                      encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        (root / "week.js").write_text(_with_components(BC.WEEK_JS), encoding="utf-8")
        up = [{"date": "2026-03-10", "time": t, "bill": b, "term": "2025-2026", "committee": "Judiciary",
               "what": k, "venue": "LOB 206"}
              for b, k, t in (("HB1", "public hearing", "10:00"), ("HB2", "executive session", "13:00"))]
        (root / "up.json").write_text(json.dumps(up), encoding="utf-8")
        (root / "go.js").write_text("""
require("./stub.js");
const fs = require("fs");
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8") + "; ({calendarBlock});"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
// The Calendar's script in a world of its own, with no page for its second half.
const vm = require("vm"), ctx = vm.createContext({document: {getElementById: () => null}, URLSearchParams});
vm.runInContext(fs.readFileSync("./week.js", "utf8"), ctx);
const W = ctx.GRCAL;
const h = s.calendarBlock(JSON.parse(fs.readFileSync("./up.json", "utf8")), "Upcoming session");
const card = (t) => '<details class="cal' + 'meet" data-date="2026-03-10" data-cmte="x" data-time="' + t
  + '" data-kinds="hearing"><summary><span class="calcmte">X</span></summary></details>';
process.stdout.write(JSON.stringify({own: W.clock !== vm.runInContext("clock", ctx),
  hours: ["00:00", "09:30", "12:00", "13:15", "23:59"].map(t =>
    (/<span class="wkt">([^<]*)<\\/span>/.exec(W.entryHtml(W.parseCard(card(t)))) || [])[1]),
  block: [...h.matchAll(/<span class="caltime">([^<]*)<\\/span>/g)].map(m => m[1])}));
""", encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert r.returncode == 0, (r.stdout or r.stderr).strip()[-300:]
        out = json.loads(r.stdout)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert not out["own"], ("the Calendar page's script tells the time with a clock() of its "
                            "own, not components.js's")
    assert out["hours"] == [f"12:00{nb}AM", f"9:30{nb}AM", f"12:00{nb}PM", f"1:15{nb}PM",
                            f"11:59{nb}PM"], (
        f"the week at a glance says its entries start at {out['hours']}")
    assert out["block"] == [f"10:00{nb}AM\u20131:00{nb}PM", f"10:00{nb}AM", f"1:00{nb}PM"], (
        f"a committee page's Upcoming session prints {out['block']}")
    return "ok", (f"{seen} times printed on the week page, its month files and Coming up, all "
                  "as a reader says them, the record's own in data-time; the Calendar's script "
                  "and a committee page tell the time with components.js's clock()")


# The page's own picker, for _calendar_chambers, on _CAL_DOM.
_CAL_CHAMBER_DRIVE = r"""const {makeWorld, runPage}=require("./minidom.js");
const fs=require("fs"), vm=require("vm"), path=require("path");
const SITE=process.argv[2], fails=[];
const ok=(c,m)=>{ if(!c) fails.push(m); };
async function open(page,pathname,o){
  const text=fs.readFileSync(path.join(SITE,page),"utf8");
  const a=text.indexOf('<div id="results">'), s=text.indexOf("<script>",a), e=text.indexOf("</script>",s);
  const W=makeWorld(Object.assign({today:[2025,1,28], path:pathname,
    files:(url)=>{ const f=path.join(SITE,url.replace(/^\//,"")); return fs.existsSync(f)?fs.readFileSync(f,"utf8"):null; }},o||{}));
  W.doc.body.innerHTML=text.slice(a,s);
  runPage(W,text,SITE,s,text.slice(s+8,e));
  await W.settle(); W.advance(700); await W.settle();
  W.$=(id)=>W.doc.getElementById(id); W.Q=(q,r)=>(r||W.doc).querySelector(q); W.QA=(q,r)=>(r||W.doc).querySelectorAll(q);
  W.keys=()=>W.QA(".calmeet",W.$("calview")).map(m=>W.Q(".calcmte",m).textContent);
  W.find=async(v)=>{ const f=W.$("cpfind"); f.dispatchEvent(W.ev("focus",{bubbles:false})); await W.settle();
    f.value=v; f.dispatchEvent(W.ev("input")); await W.settle(); return W.QA("label.cpopt",W.$("cplist")); };
  return W;
}
(async()=>{
  const W=await open("calendar.html","/calendar");
  ok(W.keys().join()==="House Finance,Senate Finance", "28 January 2025 lists "+W.keys());
  const fin=await W.find("finance");
  ok(fin.map(l=>W.Q("input",l).value).join()==="House Finance,Senate Finance",
     "the picker finds "+fin.map(l=>W.Q("input",l).value)+" for Finance, not each chamber's");
  ok(fin.every(l=>!W.Q(".cpwho",l)), "a committee whose name says its chamber is labelled with it again");
  const h=fin.map(l=>W.Q("input",l)).find(i=>i.value==="House Finance");
  if(h){ h.checked=true; h.dispatchEvent(W.ev("change")); await W.settle(); }
  ok(W.keys().join()==="House Finance" && /committee=House\+Finance/.test(W.G.location.search),
     "picking House Finance shows "+W.keys()+" at "+W.G.location.search);
  if(h){ h.checked=false; h.dispatchEvent(W.ev("change")); await W.settle(); }
  const co=await W.find("conference");
  ok(co.length===1 && W.Q("input",co[0]).value==="Committee of conference"
     && (W.Q(".cpwho",co[0])||{textContent:""}).textContent==="House and Senate",
     "the committees of conference are not one entry, said to be both chambers': "+co.map(l=>l.textContent));
  const J=await open("calendar.html","/calendar",{search:"?week=2025-W25&day=2025-06-16&committee=Committee+of+conference"});
  ok(J.keys().join()==="Committee of conference on SB 14,Committee of conference on HB 1,Committee of conference on HB 2,"
     +"Committee of conference on HB 1709",
     "picking the committees of conference shows "+J.keys());
  // A link written before 25 September, in the hash of the week's own page.
  const S=await open("calendar/2025-W25.html","/calendar/2025-W25",{hash:"#d=2025-06-16&c=Senate+Judiciary"});
  ok(S.keys().join()==="Senate Judiciary", "picking Senate Judiciary on 16 June shows "+S.keys());
  if(fails.length){ console.log(fails.join("\n")); process.exit(1); }
  console.log("the picker lists House and Senate Finance apart, picks one, and holds the conferences as one");
  console.log("OK");
})().catch(e=>{ console.log(fails.join("\n")); console.log("THREW "+e.stack); process.exit(2); });
"""


# ---- one date formatter in each language (8 October 2026) -------------------------
#
# The person chose month first (D6 of the polish plan): "May 21, 2026", and
# "10:00 AM" for a time. The site wrote its own dates in twelve forms from six
# formatters in the builders and four in app.js; components.py's date_words()
# and components.js's dateWords() are the one of each now. These are the ways a
# formatter has been written here, so a new one is caught where it is written
# rather than on a page: a strftime or a format spec with a month or a
# weekday in it, a day number written before a month, a month list indexed to
# write one, and the browser's own toLocaleDateString, which wrote "Wed 7 Oct"
# in one reader's browser and "Wed, Oct 7" in another's. What is left out is
# named with its reason.
_DATE_EXEMPT = {
    # Not a date in the site's voice: what a parser reads, a machine's
    # format, a citation's style.
    "shell.py": ("def cite_day", "CITE_MONTHS"),
    "build_feeds.py": ("def rfc822",),
    "app.js": ("function citeDay", "CITE_MONTHS"),
    # The moment the data was rebuilt, in the reader's own clock and zone,
    # which only the browser has: month first, as dateWords writes a day.
    # (The home page's floor-session titles, "August 19th, 2026", were the
    # other exception until 25 October 2026: the audit's M8 retired them.)
    # In the page's locale since 23 October 2026 (window.GR_LOCALE, i18n.py).
    "chrome.py": ('.toLocaleDateString(window.GR_LOCALE||"en-US",{year:"numeric",month:"long",day:"numeric"})',),
    # A month and its year ("October 2026") over the month's grid: not a day.
    "build_calendar.py": ('monthWords(m){ return MONTH[',),
}
_DATE_IDIOMS = (
    (r"strftime\(\s*[\"'][^\"']*%[aAbB]", "a strftime that writes a month or a weekday"),
    (r"\{[^{}]*:%[aAbB][^{}]*\}", "a format spec that writes a month or a weekday"),
    (r"\{[\w.\[\]()]*\.day\}\s*(?:&nbsp;)?\s*\{", "a day number written before a month"),
    (r"toLocaleDateString\(", "the browser's own date format"),
    # Any list of months, by whatever name (the review of 8 October 2026 wrote
    # MONTH_NAMES[d.getMonth()] and the narrower name list passed it).
    (r"\b(?:[A-Z_]*MON[A-Z_]*|\w*[Mm]onths?\w*)\[[^\]]+\]\s*\+?\s*[\"'`]?\s*\+?\s*[\"' ]",
     "a month list indexed to write a date"),
    (r"getDate\(\)\s*\+\s*[\"'`]", "a day number written before a month"),
    # A date in figures, "2/19/2026", which reads two ways (the review of
    # 8 October 2026 wrote one with an f-string and this passed it).
    (r"strftime\(\s*[\"'][^\"']*%-?[mdYy]\s*/\s*%-?[mdYy]", "a date written in figures"),
    (r"\{[^{}]*(?:\.month|\[5:7\]|\.day|\[8:10\])[^{}]*\}\s*/\s*\{", "a date written in figures"),
    (r"getMonth\(\)\s*\+\s*1\s*\)?\s*\+\s*[\"'`]\s*/", "a date written in figures"),
)


@check("frontend", "every date the site writes is month first, from the components' one "
                   "formatter in each language, and no builder or script writes one any "
                   "other way")
def _one_date_formatter():
    """The formatter is a component: components.py's date_words() and
    date_span(), and components.js's dateWords() and dateSpan(), which
    _components_agree holds to one answer on every form (long, full, medium,
    short, day, wkd) across a leap day, the turns of the year and of a month,
    and what is not a date, with the person's words among its cases. This
    holds the rest: the home page's script and the Calendar's, which ran
    without app.js and so carried a copy, carry none now, every page loading
    components.js in its head before them; narrative.py's strftime, which
    writes the bills' stories, says what date_words' full form says; nothing
    in a builder, app.js, components.js or find.js formats a date another way
    (_DATE_IDIOMS, less _DATE_EXEMPT and the formatter itself, between its
    DATEWORDS markers); and the fixture site's pages, as a reader without
    script gets them, carry no date written day first but a citation's."""
    import datetime as _dt
    import html as _h
    import components as C
    import build_pages as BP
    import build_calendar as BC
    days = ["2026-02-19", "2024-02-29", "2026-01-01", "2025-12-31", "2026-05-21",
            "2026-09-04", "2026-10-07", "1989-01-04", "2026-11-03"]

    # The two scripts that carried a copy carry none.
    for what, js in (("the home page's script", BP.HOME_JS), ("the Calendar's script", BC.WEEK_JS)):
        own = [w for w in ("function dateWords", "function dateSpan", "DW_MONTHS=", "DW_DAYS=",
                           "__DATEWORDS__") if w in js]
        assert not own, (f"{what} carries a date formatter of its own ({', '.join(own)}); "
                         "the page loads components.js's before it")

    # The stories' own formatter, which narrative.py keeps: the same words.
    try:
        import narrative as N
        for d in days:
            x = _dt.datetime.strptime(d, "%Y-%m-%d")
            assert x.strftime(N.MONTH) == C.date_words(d, "full"), (
                f"narrative.py writes {x.strftime(N.MONTH)!r} where date_words writes "
                f"{C.date_words(d, 'full')!r}")
    except ImportError:
        pass

    # Nothing else writes one.
    bad = []
    for name, src in _front_sources():
        text = src
        for keep in _DATE_EXEMPT.get(name, ()):
            for m in list(re.finditer(re.escape(keep), text)):
                # The exempt line, or the exempt function to its end.
                end = text.find("\n\n", m.start()) if keep.startswith(("def ", "function ")) \
                    else text.find("\n", m.start())
                text = text[:m.start()] + " " * ((end if end > 0 else len(text)) - m.start()) \
                    + text[(end if end > 0 else len(text)):]
        # The formatter itself, in each language, between its markers.
        if name in ("components.js", "components.py"):
            mark = "//" if name.endswith(".js") else "#"
            a = text.find(mark + " DATEWORDS:START")
            if a >= 0:
                b = text.find(mark + " DATEWORDS:END", a)
                text = text[:a] + " " * (b - a) + text[b:]
        for pat, what in _DATE_IDIOMS:
            for m in re.finditer(pat, text):
                line = text[text.rfind("\n", 0, m.start()) + 1:text.find("\n", m.start())]
                if line.lstrip().startswith(("#", "//", "*")):
                    continue
                bad.append(f"{name}:{_line_of(text, m.start())} {what}: {line.strip()[:70]}")
    assert not bad, (f"{len(bad)} dates written outside the formatter: " + "; ".join(bad[:8])
                     + (f" (+{len(bad) - 8} more)" if len(bad) > 8 else ""))
    scanned = [name for name, _t in _front_sources()]
    assert "components.js" in scanned and "components.py" in scanned, (
        f"the scan for dates written another way does not read the components: {scanned[:6]}")

    # And the pages, as a reader without script is given them.
    day_first = re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?(?:\s|&nbsp;)+(?:January|February|March|"
                           r"April|May|June|July|August|September|October|November|December|"
                           r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\b")
    figures = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b(?:19|20)\d\d-[01]\d-[0-3]\d\b")
    shared, _base, _ran, _days = _fixture_site_shared()
    seen, found = 0, []
    for f in sorted((shared / "site").rglob("*.html")):
        t = f.read_text(encoding="utf-8", errors="replace")
        # A citation keeps its own style (MLA's "24 Sept. 2026"); a bill's
        # own text and the docket's lines are the General Court's words.
        t = re.sub(r'<div class="pageacts".*?</dl>|<span class="citeday[^"]*">.*?</span>|'
                   r"<!--.*?-->|<script\b.*?</script>|<style\b.*?</style>|<pre\b.*?</pre>|"
                   # sx-docket: the docket's own words in a page's plain record
                   # (static_record, 12 October 2026), as the page app.js draws
                   # quotes them.
                   r'<div class="(?:billbody|docket|sx-docket)".*?</div>', " ", t, flags=re.S)
        seen += 1
        # A tag is a boundary, not a space: "SC 9</span>...<span>Mar 10" is
        # two things, not "9 Mar".
        for m in day_first.finditer(_h.unescape(re.sub(r"<[^>]+>", " | ", t))):
            found.append(f"{f.relative_to(shared / 'site')}: {m.group(0)!r}")
        # Nor a date in figures, "2026-09-17" or "8/19/2026", but the docket's
        # own line under a bill on the home page (.actw), which is the clerk's
        # words, and an address or a file's name in <code>. The review of
        # 8 October 2026 found About's "Last measured 2026-09-17" and By the
        # numbers' closest votes dated "2025-04-17" here.
        t2 = re.sub(r'<span class="actw">.*?</span>|<code\b.*?</code>', " ", t, flags=re.S)
        for m in figures.finditer(_h.unescape(re.sub(r"<[^>]+>", " | ", t2))):
            found.append(f"{f.relative_to(shared / 'site')}: {m.group(0)!r}")
    assert seen > 20, f"only {seen} pages in the fixture site"
    assert not found, (f"{len(found)} dates written day first on the fixture's pages: "
                       + "; ".join(found[:8]))
    return "ok", ("the home and Calendar scripts carry no formatter of their own; the "
                  "stories' strftime agrees with date_words; no other formatter in "
                  f"{len(_front_sources())} builders and scripts; no day written first "
                  f"on {seen} fixture pages")


@check("frontend", "the Calendar page is a month, filters and three views over a week that reads whole without script")
def _calendar_page_shape():
    """The person's description of 24 September 2026, as markup and files.

    "A calendar on the left side of the page showing the full month ... select
    days to view the schedule of on the main panel which change their
    configuration depending on if you have list, week, or day selected ... You
    should be able to toggle between viewing all meetings including study
    committees, just standing committee meetings, public hearings, meetings for
    a specific committee, or any combination of those."

    Two rules keep it honest, and this holds both. THE PAGE IS WHOLE WITHOUT
    SCRIPT: the week is still the list it was, and every control is emitted
    hidden, so nobody meets one that does nothing. AND THERE IS ONE RENDERER:
    a reader who moves to another week is shown cards out of
    calendar/data/<month>.json, and those are build_pages.cal_days's cards,
    byte for byte the ones that week's own page carries -- the script arranges
    them and never draws one. The cards say who is meeting and what kinds of
    sitting they hold, which is what the grid, the preview and the filters
    read. The page's copy of the script carries none of the strings the
    other calendar checks count in a page's text, or it would be counted as
    a card, a link or an empty day.
    """
    import build_calendar as BC
    if not Path("src/pages/bills.html").exists():
        return "skip", "bills.html is not here"
    root = Path(tempfile.mkdtemp(prefix="gr-calshape-"))
    try:
        site, weeks, order, urls, (n_months, n_cards) = _cal_fixture(root)
        t = (site / "calendar.html").read_text(encoding="utf-8")
        app = re.search(r'<div class="wkpage calapp" id="calapp"([^>]*)>', t)
        assert app, "the week's page has no calendar frame"
        attrs = dict(re.findall(r' data-([a-z]+)="([^"]*)"', app.group(1)))
        assert attrs == {"week": "2026-W11", "here": "2026-W11",
                         "first": order[0], "last": order[-1]}, (
            f"the frame tells the script {attrs}")
        # Hidden without script, all of it.
        for frag in ('<div class="calside" id="calside" hidden>',
                     '<div class="calbar" id="calbar" hidden>',
                     '<fieldset class="calcats" id="calcats" hidden>',
                     '<div class="calpeek" id="calpeek" role="tooltip" hidden>',
                     '<button type="button" class="calreset" id="calreset" hidden>'):
            assert frag in t, f"not emitted hidden: {frag}"
        # THE COLOURS ARE THE FILTER (25 September 2026): a row of boxes, one
        # per kind in its colour, every one ticked but Study Committee; down
        # the side only the search, the chamber and the committees by name.
        # The "who" and "what" questions and the quick choices are gone.
        for legend in ("Only these committees", "Chamber"):
            assert f"<legend>{legend}</legend>" in t, f"no fieldset with the legend {legend!r}"
        for gone in ("Who is meeting", "What kind of committee meeting", 'data-quick=',
                     'name="who"', 'name="what"', "calsrc", "Show everything"):
            assert gone not in t, f"the week's page still carries {gone!r}"
        boxes = re.findall(r'<input type="checkbox" name="cat" value="([a-z]+)"( checked)?>', t)
        # KEY DATES, THE SEVENTH (24 October 2026), on for a new reader.
        assert boxes == [("hearing", " checked"), ("exec", " checked"), ("work", " checked"),
                         ("conf", " checked"), ("floor", " checked"), ("study", ""),
                         ("date", " checked")], (
            f"the row of boxes is {boxes}: seven, every one on but Study Committee")
        assert re.search(r'<legend class="sr">[^<]+</legend><div class="calcatrow">', t), (
            "the row of boxes has no name for a screen reader to give the group")
        assert '<ul class="calkey" aria-label="What the colors mean">' in t, (
            "a reader without script is given no key to the colours")
        assert '<p class="calhint" id="pickhint" hidden>' in t, (
            "the committees chosen by name do not say they are still shown in the kinds ticked")
        views = re.findall(r'<button type="button" data-view="([a-z]+)" aria-pressed="([a-z]+)">', t)
        assert views == [("list", "true"), ("week", "false")], (
            f"the view switch is {views}")
        assert 'id="wkcount" role="status" aria-live="polite"' in t, "the count is not announced politely"
        assert '<table class="cmgrid" id="cmgrid" role="grid" aria-labelledby="cmtitle">' in t, (
            "the month is not a grid labelled by its month")
        # The week, whole, in the page.
        body = t[t.index('<div class="calview" id="calview">'):t.index('<hr class="calend"')]
        cards = re.findall(r'<details class="calmeet"[^>]*>', body)
        assert len(cards) == 7, f"the week of 9 March lists {len(cards)} cards, not 7"
        # The language the week's hyphens:auto needs to hyphenate a committee's
        # name rather than split it (_calendar_layout).
        assert re.search(r'<html lang="en"', t), "the week's page does not say its language"
        who_of = {re.search(r'data-cmte="([^"]*)"', c).group(1): (
            re.search(r'data-who="([^"]*)"', c).group(1),
            re.search(r'data-kinds="([^"]*)"', c).group(1)) for c in cards}
        assert who_of["house judiciary"] == ("standing", "hearing exec"), who_of
        assert who_of["house session day"] == ("floor", "floor"), who_of.get("house session day")
        assert who_of["committee of conference on hb 3"] == ("standing", "conf"), who_of
        # Two cards of the commission, the one that met and the one cancelled:
        # both study, the one that met drawn in the study committees' colour.
        aging = sorted((re.search(r'data-date="([^"]*)"', c).group(1),
                        re.search(r'data-who="([^"]*)"', c).group(1),
                        re.search(r'data-kinds="([^"]*)"', c).group(1))
                       for c in cards if 'data-cmte="commission on aging"' in c)
        assert aging == [("2026-03-13", "study", "study"), ("2026-03-14", "study", "other")], aging
        # The script the page carries.
        js = re.search(r"<script>(\(function\(\)\{.*?)</script>", t, re.S)
        assert js, "the week's page carries no calendar script"
        lean = js.group(1)
        assert not re.search(r"^\s*//", lean, re.M), "the page's copy of the script keeps its comments"
        for bad in ('<details class="calmeet"', "No meetings scheduled.", 'class="wknext" href=',
                    'class="wkprev" href=', 'class="wkhere" href='):
            assert bad not in lean, (f"the page's script spells {bad!r}, which the other "
                                     "calendar checks count in a page's text")
        node = _cal_node()
        if node:
            f = root / "lean.js"
            f.write_text(lean, encoding="utf-8")
            r = _run([node, "--check", str(f)], capture_output=True, text=True)
            assert r.returncode == 0, "node --check: " + r.stderr.strip()[:200]

        # The month files.
        data = site / "calendar" / "data"
        assert sorted(p.name for p in data.iterdir()) == [
            "2026-03.json", "2026-04.json", "committees.json"], sorted(p.name for p in data.iterdir())
        assert n_months == 2, n_months
        m3 = json.loads((data / "2026-03.json").read_text(encoding="utf-8"))
        m4 = json.loads((data / "2026-04.json").read_text(encoding="utf-8"))
        days = {**m3["days"], **m4["days"]}
        want = []
        d = BC.datetime.date.fromisocalendar(2026, int(order[0][6:]), 1)
        end = BC.datetime.date.fromisocalendar(2026, int(order[-1][6:]), 7)
        while d <= end:
            want.append(d.isoformat())
            d += BC.datetime.timedelta(days=1)
        assert sorted(days) == want, "the month files do not hold every day from the first week to the last"
        assert "No meetings scheduled." in days["2026-03-15"], "an empty Sunday has no words for the Day view"
        for k in order:
            page = (site / "calendar" / f"{k}.html") if k != "2026-W11" else (site / "calendar.html")
            pt = page.read_text(encoding="utf-8")
            pv = pt[pt.index('<div class="calview" id="calview">'):pt.index('<hr class="calend"')]
            mon = BC.datetime.date.fromisocalendar(2026, int(k[6:]), 1)
            dates = [(mon + BC.datetime.timedelta(days=i)).isoformat() for i in range(7)]
            from_files = [c for x in dates
                          for c in re.findall(r'<details class="calmeet"[\s\S]*?</details>', days[x])]
            on_page = re.findall(r'<details class="calmeet"[\s\S]*?</details>', pv)
            assert from_files == on_page, (f"{k}: the month files' cards are not the week page's "
                                           f"({len(from_files)} against {len(on_page)})")
            import html as _h
            wk = (m3["weeks"].get(k) or m4["weeks"].get(k))
            h1 = _h.unescape(re.search(r"<h1>The Week of ([^<]*)</h1>", pt).group(1))
            lead = re.search(r'<p class="src">([^<]*)</p>', pt).group(1)
            assert wk and wk["label"] == h1, f"{k}: the month file calls the week {wk}, the page {h1!r}"
            assert wk["lead"] == lead, f"{k}: the month file's lead is not the page's"
            # The pager's short name, which Previous Week and Next Week say
            # under them, is the month file's too.
            for cls, near in (("wkprev", -1), ("wknext", 1)):
                said = re.search(rf'class="{cls}" href="[^"]*"><span class="wkpw">[^<]*</span>'
                                 r'<span class="wkpd">([^<]*)</span>', pt)
                nk = order[order.index(k) + near] if 0 <= order.index(k) + near < len(order) else None
                if nk:
                    nw = m3["weeks"].get(nk) or m4["weeks"].get(nk)
                    assert said and nw and _h.unescape(said.group(1)) == nw["short"], (
                        f"{k}: the pager names {nk} {said and said.group(1)!r}, its month file "
                        f"{nw and nw['short']!r}")
        names = json.loads((data / "committees.json").read_text(encoding="utf-8"))
        assert ["House Judiciary", "standing", "H"] in names and ["Senate Finance", "standing", "S"] in names \
            and ["Commission on Aging", "study", ""] in names and ["House Session Day", "floor", "H"] in names \
            and ["Committee of conference", "standing", "H S"] in names, names
        # Writers merge what they own: a month file this run did not write goes.
        (data / "1999-01.json").write_text("{}", encoding="utf-8")
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            BC.month_files(site, weeks, order, {}, {}, {}, BC.datetime.date(*CAL_TODAY))
        assert not (data / "1999-01.json").exists(), "a stale month file was left beside the rest"
        assert all("/calendar/data" not in u for u in urls), "a data file went into the sitemap"
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", (f"frame, boxes, side filters, view switch and grid emitted hidden; {n_cards} cards "
                  f"in {n_months} month files, byte for byte the week pages' own")


@check("frontend", "the calendar's filters combine, and the list, the week, the day, the grid and the preview agree")
def _calendar_core():
    """The script's reasoning, run in node over cards a build wrote.

    Everything the page decides -- which cards a filter keeps, what the count
    says, which days the list draws, which days the week has columns for and
    what each entry says, which dots a day of the month carries and what its
    name says, what the preview lists, what the address holds -- is a plain
    function in WEEK_JS's first half. This loads that half against the
    fixture's month files and holds each to the rule it implements:

      one box per kind of meeting, every one on but Study Committee for a
      new reader; a card holding several kinds matches if any is ticked and
      stays whole; the floor is Session Day and a study or statutory
      committee is Study Committee, whatever kind of meeting either held;
      work sessions and study committees are two boxes; committees picked
      by name show only those committees, still narrowed by the boxes, and a
      committee asked for by name -- picked, or found by the search -- shows
      with Study Committee unticked; a cancelled meeting is shown and never
      counted; an empty weekday is drawn under any filter, a busy day the
      filters emptied is not, and a weekend day only when something shown is
      on it, in the list and in the week, whose columns are Monday to Friday
      otherwise (9 October 2026) and whose entries are the cards in brief --
      the time a reader says, the name, the bills, the kinds as the bar and
      in words for a screen reader -- leading where the card leads or else
      into the Day view; an empty column says why; the Day view steps over
      an empty weekend; the grid starts on Monday, bands the selected week, marks today
      and the past, and its dots and names agree with the entries; the
      preview stops at five, says how many more and gives its times as a
      reader says them; and the query round-trips, while an address from
      before 25 September is read into the same boxes.

    Until 25 September 2026 this held "who" and "what" as two questions and
    the two quick choices that set them; the person replaced both with the
    row of boxes, and the rules above are the ones the page now keeps.
    """
    node = _cal_node()
    if not node:
        return "skip", "node is not on PATH"
    import build_calendar as BC
    if not Path("src/pages/bills.html").exists():
        return "skip", "bills.html is not here"
    root = Path(tempfile.mkdtemp(prefix="gr-calcore-"))
    try:
        site, _w, _o, _u, _m = _cal_fixture(root)
        data = site / "calendar" / "data"
        prog = root / "core.js"
        prog.write_text("globalThis.document={getElementById:function(){return null;}};\n"
                        + _with_components(BC.WEEK_JS) + _CAL_CORE_TEST, encoding="utf-8")
        r = _run([node, str(prog), str(data / "2026-03.json"), str(data / "2026-04.json")],
                 capture_output=True, text=True, timeout=120)
        out = (r.stdout or "") + (r.stderr or "")
        assert r.returncode == 0 and out.strip().endswith("OK"), out.strip()[-1500:]
        # A WEEK'S NAME FROM ITS KEY, which the heading uses when the week's
        # month file did not come, and the pager's short name for it: the
        # same words week_facts gives every week's own page with nothing on
        # its weekend -- Monday to Friday (9 October 2026) -- across month
        # ends and a year's.
        labels, d = {}, BC.datetime.date(2024, 12, 23)
        while d <= BC.datetime.date(2028, 1, 10):
            k = BC.week_key(d)
            facts = BC.week_facts(k, {k: {d.isoformat(): {}}}, BC.datetime.date(2026, 3, 11))
            labels[k] = [facts["label"], facts["short"]]
            assert facts["label"] == BC.span_words(d, d + BC.datetime.timedelta(days=4)), (
                f"{k} is named {facts['label']!r}, not Monday to Friday")
            d += BC.datetime.timedelta(days=7)
        (root / "labels.json").write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")
        prog2 = root / "labels.js"
        prog2.write_text("globalThis.document={getElementById:function(){return null;}};\n"
                         + _with_components(BC.WEEK_JS) + r"""
const C=globalThis.GRCAL, want=JSON.parse(require("fs").readFileSync(process.argv[2],"utf8"));
const bad=Object.keys(want).filter(k=>C.weekLabel(k)!==want[k][0]||C.weekLabel(k,"medium")!==want[k][1])
  .map(k=>k+": "+C.weekLabel(k)+" / "+C.weekLabel(k,"medium")+" | "+want[k].join(" / "));
console.log(bad.length?bad.slice(0,5).join("\n"):"OK "+Object.keys(want).length);
""", encoding="utf-8")
        r2 = _run([node, str(prog2), str(root / "labels.json")], capture_output=True,
                  text=True, encoding="utf-8", timeout=60)
        assert r2.returncode == 0 and r2.stdout.startswith("OK"), (
            "the script names a week otherwise than its page does: "
            + ((r2.stdout or "") + (r2.stderr or "")).strip()[-600:])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", out.strip().splitlines()[-2]


_CAL_CORE_TEST = r"""
const C=globalThis.GRCAL, fs=require("fs"), fails=[];
const ok=(c,m)=>{ if(!c) fails.push(m); };
const days={};
process.argv.slice(2).forEach(f=>{ const j=JSON.parse(fs.readFileSync(f,"utf8"));
  Object.keys(j.days).forEach(d=>days[d]=C.parseDay(j.days[d])); });
const week=[...Array(7).keys()].map(i=>C.addDays("2026-03-09",i));
const all=[].concat(...week.map(d=>days[d].cards));
const F=(o)=>Object.assign(C.defaults(),o);
const ON=F({cats:C.CATS.slice()});
const names=(f)=>all.filter(e=>C.matches(e,f)).map(e=>e.name).sort();
const count=(f)=>C.countLine(C.tally(all,f),"this week");
const NB="\u00a0";
ok(all.length===7, "the week of 9 March parses to "+all.length+" cards");
const jud=all.find(e=>e.name==="House Judiciary");
ok(jud && jud.kinds.join()==="hearing,exec" && jud.who==="standing" && jud.body==="H" && jud.bills.join()==="HB1 HB2".split(" ").join(),
   "House Judiciary's card reads as "+JSON.stringify(jud&&{k:jud.kinds,w:jud.who,b:jud.body,bills:jud.bills}));
const aging=all.filter(e=>e.name==="Commission on Aging");
ok(aging.length===2 && aging.every(e=>e.who==="study") && aging[0].kinds.join()==="study" && aging[1].kinds.join()==="other",
   "the Commission on Aging's cards read as "+JSON.stringify(aging.map(e=>({w:e.who,k:e.kinds}))));
// ---- the boxes ----
ok(C.CATS.join()==="hearing,exec,work,conf,floor,study,date" && C.defaults().cats.join()==="hearing,exec,work,conf,floor,date",
   "the boxes, and the ones a new reader starts with: "+C.CATS+" / "+C.defaults().cats);
// WHICH BOX A CARD ANSWERS TO: work sessions and study committees apart; a
// study committee is Study Committee whatever it held; a kind the table does
// not name is one of a committee's other meetings, under Work Session.
const cat=(who,kinds)=>C.catsOf({who,kinds}).join();
ok(cat("standing",["meet"])==="work" && cat("study",["study"])==="study" && cat("study",["other"])==="study"
   && cat("study",["hearing"])==="study" && cat("floor",["floor"])==="floor" && cat("standing",["other"])==="work"
   && cat("standing",["hearing","exec","meet"])==="hearing,exec,work" && cat("standing",["conf"])==="conf"
   && cat("standing",[])==="work",
   "a card answers to the wrong box: "+[cat("standing",["meet"]),cat("study",["study"]),cat("study",["hearing"]),cat("standing",["other"])]);
ok(count(F({}))==="5 of 6 meetings shown. 1 study committee meeting is hidden.", "a new reader's week: "+count(F({})));
ok(names(F({})).join()==="Committee of conference on HB 3,House Commerce,House Judiciary,House Session Day,Senate Finance",
   "a new reader's week holds "+names(F({})));
ok(count(ON)==="6 meetings this week.", "every box ticked: "+count(ON));
ok(names(F({cats:["hearing"]})).join()==="House Judiciary,Senate Finance",
   "Public Hearing alone keeps "+names(F({cats:["hearing"]}))+" -- the floor answers to its own box");
ok(names(F({cats:["exec"]})).join()==="House Commerce,House Judiciary", "Executive Session alone keeps "+names(F({cats:["exec"]})));
ok(names(F({cats:["floor"]})).join()==="House Session Day", "Session Day alone keeps "+names(F({cats:["floor"]})));
ok(names(F({cats:["conf"]})).join()==="Committee of conference on HB 3", "Committee of Conference alone keeps "+names(F({cats:["conf"]})));
ok(names(F({cats:["study"]})).join()==="Commission on Aging,Commission on Aging" && count(F({cats:["study"]}))==="1 of 6 meetings shown.",
   "Study Committee alone keeps "+names(F({cats:["study"]}))+" and counts "+count(F({cats:["study"]})));
ok(count(F({cats:["work"]}))==="None of the 6 meetings this week match. 1 study committee meeting is hidden.", "Work Session alone, in a week of none: "+count(F({cats:["work"]})));
// An entry holding two kinds stays while either is ticked, and whole.
ok(names(F({cats:["hearing","work","conf","floor"]})).join()==="Committee of conference on HB 3,House Judiciary,House Session Day,Senate Finance"
   && count(F({cats:["hearing","work","conf","floor"]}))==="4 of 6 meetings shown. 1 study committee meeting is hidden.",
   "Executive Session unticked keeps "+names(F({cats:["hearing","work","conf","floor"]})));
// Committees by name: only those, still in the kinds ticked, and a study
// committee asked for by name whatever its box says.
ok(names(F({picks:["House Judiciary"]})).join()==="House Judiciary", "one committee picked: "+names(F({picks:["House Judiciary"]})));
ok(names(F({picks:["Commission on Aging"]})).join()==="Commission on Aging,Commission on Aging"
   && count(F({picks:["Commission on Aging"]}))==="1 of 6 meetings shown.",
   "a study committee picked with Study Committee unticked: "+names(F({picks:["Commission on Aging"]}))+" / "+count(F({picks:["Commission on Aging"]})));
ok(names(F({picks:["Commission on Aging"],cats:[]})).length===2, "a picked study committee is hidden by the other boxes");
ok(names(F({picks:["House Judiciary"],cats:["floor","study"]})).length===0 && names(F({picks:["House Judiciary"],cats:["exec"]})).join()==="House Judiciary",
   "the boxes do not narrow a committee picked");
ok(names(F({picks:["House Judiciary","Commission on Aging"],cats:["hearing"]})).join()==="Commission on Aging,Commission on Aging,House Judiciary",
   "two committees picked, one a study committee: "+names(F({picks:["House Judiciary","Commission on Aging"],cats:["hearing"]})));
ok(names(F({picks:["Committee of conference"]})).join()==="Committee of conference on HB 3",
   "the committees of conference are not picked under one name: "+names(F({picks:["Committee of conference"]})));
ok(names(F({body:"S",picks:["House Judiciary"]})).length===0 && names(F({body:"H",picks:["House Judiciary"]})).join()==="House Judiciary",
   "a chamber plus a committee");
ok(count(F({body:"S",picks:["House Judiciary"]}))==="None of the 6 meetings this week match.", count(F({body:"S",picks:["House Judiciary"]})));
ok(names(F({body:"H"})).join()==="Committee of conference on HB 3,House Commerce,House Judiciary,House Session Day"
   && names(Object.assign(F({body:"H"}),{cats:C.CATS.slice()})).indexOf("Commission on Aging")<0,
   "the House alone: "+names(F({body:"H"}))+" -- a conference is both chambers', a study committee neither's");
// The search: a bill, a committee, and a study committee found by name.
ok(names(F({q:"hb 4"})).join()==="House Commerce" && names(F({q:"judic"})).join()==="House Judiciary", "the bill and committee search");
ok(names(F({q:"aging"})).join()==="Commission on Aging,Commission on Aging" && names(F({q:"hb 4",cats:["hearing"]})).length===0,
   "the search: a study committee found by name with its box unticked, and a bill in an unticked kind: "+names(F({q:"aging"})));
ok(C.countLine({total:1,shown:0,seen:0},"this week")==="The one meeting this week does not match.", "one sitting, none shown");
ok(C.countLine(C.tally(days["2026-03-11"].cards,F({})),"on "+C.dayWords("2026-03-11"))==="2 meetings on Wednesday, March 11.",
   "the Day view's count: "+C.countLine(C.tally(days["2026-03-11"].cards,F({})),"on "+C.dayWords("2026-03-11")));
ok(C.narrowed(F({}))===0 && C.narrowed(ON)===1 && C.narrowed(F({cats:["hearing"],q:"x"}))===2
   && C.narrowed(F({cats:["exec","hearing","work","floor","conf","date"]}))===0
   && C.narrowed(F({cats:["exec","hearing","work","floor","conf"]}))===1,
   "how far the filters are from a new reader's");
ok(C.sideOn(F({}))===0 && C.sideOn(F({cats:[],body:"H"}))===1 && C.sideOn(F({picks:["x"],q:"y"}))===2,
   "the side's own count takes in the boxes above the schedule");
// ---- the list's days ----
const none=F({cats:[],picks:["Nobody"]});
ok(C.listDates(week,days,F({})).join()==="2026-03-09,2026-03-10,2026-03-11,2026-03-12,2026-03-13",
   "a new reader's list draws "+C.listDates(week,days,F({}))+" -- Monday to Friday, Friday's study committee hidden and said to be");
ok(C.listDates(week,days,ON).join()==="2026-03-09,2026-03-10,2026-03-11,2026-03-12,2026-03-13,2026-03-14",
   "every box ticked, the list draws "+C.listDates(week,days,ON));
ok(C.listDates(week,days,none).join()==="2026-03-09,2026-03-10,2026-03-11,2026-03-12,2026-03-13",
   "under a filter matching nothing the list does not keep Monday to Friday alone: "+C.listDates(week,days,none));
// ---- the week at a glance: Monday to Friday, and a weekend day that holds something ----
const cols=C.weekCols(week,days,ON);
ok(cols.join()==="2026-03-09,2026-03-10,2026-03-11,2026-03-12,2026-03-13,2026-03-14",
   "every box ticked, the week's columns are "+cols+" -- Monday to Friday and the Saturday that holds a meeting");
ok(C.weekCols(week,days,F({})).join()==="2026-03-09,2026-03-10,2026-03-11,2026-03-12,2026-03-13",
   "a Saturday whose one meeting is a study committee's is a column for a new reader: "+C.weekCols(week,days,F({})));
ok(C.weekCols(week,days,none).length===5 && C.weekCols(week,days,F({}),"2026-03-15").join().endsWith("2026-03-13,2026-03-15"),
   "under a filter matching nothing the week is not Monday to Friday, or a Sunday the reader chose is no column");
// An entry is its card in brief, read off the card: the time a reader says
// it, the name, the bills; the kinds as the bar and, for a screen reader, in
// words; a cancelled meeting says so; and it leads where the card leads.
const E=(e)=>C.entryHtml(e);
const ej=E(jud);
ok(/^<li class="wke" data-date="2026-03-10" data-cmte="house judiciary"><button type="button" class="wkgo" data-open="2026-03-10\|house judiciary">/.test(ej)
   && ej.indexOf('<span class="wkbar" aria-hidden="true"><i class="k-hearing"></i><i class="k-exec"></i></span>')>=0
   && ej.indexOf('<span class="wkt">10:00'+NB+'AM</span><span class="wkc">House Judiciary</span><span class="wkn">2 bills</span>')>=0
   && ej.indexOf('<span class="sr">, Public Hearing, Executive Session</span>')>=0,
   "House Judiciary's entry: "+ej);
const fl=all.find(e=>e.who==="floor"), ef=E(fl);
ok(fl && fl.name==="House Session Day" && ef.indexOf('<span class="wkc">House Session Day</span><span class="wkn">1 bill</span>')>=0
   && ef.indexOf('class="wkt"')<0 && ef.indexOf('<i class="k-floor"></i>')>=0 && ef.indexOf('<span class="sr">, ')<0,
   "the floor's entry is not House Session Day, untimed, with no chip to say it again: "+ef);
const off=E(aging[1]);
ok(/<span class="wkc">Commission on Aging<\/span><span class="wkn">Cancelled<\/span>/.test(off) && !/Cancelled<\/span><span class="sr">/.test(off),
   "a cancelled meeting's entry: "+off);
const linked=C.parseCard(jud.html.replace("</div></details>",'<p class="calmore caldocs"><a class="out" href="https://gc/x.pdf">HC 9 (PDF)</a></p>'
  +'<p class="calmore"><a href="committee/H05.html#day-2026-03-10">This meeting on the House Judiciary page</a></p></div></details>'));
ok(/<li class="wke"[^>]*><a class="wkgo" href="committee\/H05\.html#day-2026-03-10"><span class="wkbar"/.test(E(linked)),
   "an entry whose card leads to its committee's page at that day does not: "+E(linked));
// What an empty column says. A day of study committees alone says what it
// holds, with no count: their count is the week's line's (18 October 2026;
// the words, the R2 polish batch, 30 October 2026).
ok(C.emptyWords([],F({}))==="No meetings" && C.emptyWords([aging[0]],F({}))==="Study committee meetings only."
   && C.emptyWords([aging[0],aging[0]],F({}))==="Study committee meetings only."
   && C.emptyWords([aging[0]],F({cats:[],q:"x"}))==="1 meeting is hidden by the filters."
   && C.emptyWords([jud,aging[0]],F({cats:[]}))==="2 meetings are hidden by the filters.",
   "an empty column's words: "+[C.emptyWords([],F({})),C.emptyWords([aging[0]],F({})),C.emptyWords([jud,aging[0]],F({cats:[]}))]);
ok(/^Study committee meetings only\. <button type="button" class="calshowday">Show them<span class="sr">/.test(C.emptyHtml([aging[0]],F({})))
   && C.emptyHtml([aging[0]],F({cats:[],q:"x"}))==="1 meeting is hidden by the filters."
   && C.emptyHtml([aging[0]],ON).indexOf("button")<0
   && C.emptyHtml([aging[0]],F({body:"H"})).indexOf("button")<0,
   "Show them is on a day of study committees alone and only there: "+C.emptyHtml([aging[0]],F({})));
ok(C.countLine({total:3,shown:0,seen:0,study:3},"this week")==="3 study committee meetings are hidden."
   && C.countLine({total:1,shown:0,seen:0,study:1},"this week")==="1 study committee meeting is hidden."
   && C.countLine({total:3,shown:0,seen:0,study:2},"this week")==="None of the 3 meetings this week match. 2 study committee meetings are hidden."
   && C.countLine({total:0,shown:0,seen:0,study:0},"this week")==="No meetings this week.",
   "a week of study committees alone speaks of a filter nobody set: "+C.countLine({total:3,shown:0,seen:0,study:3},"this week"));
// The Day view steps over a weekend with nothing on it, and not over one that holds something.
ok(C.stepDay("2026-03-13",1,days)==="2026-03-14" && C.stepDay("2026-03-14",1,days)==="2026-03-16"
   && C.stepDay("2026-03-16",-1,days)==="2026-03-14" && C.stepDay("2026-03-23",-1,days)==="2026-03-20"
   && C.stepDay("2026-03-20",1,days)==="2026-03-23" && C.stepDay("2026-03-10",-1,days)==="2026-03-09",
   "the Day view's steps: "+[C.stepDay("2026-03-13",1,days),C.stepDay("2026-03-14",1,days),C.stepDay("2026-03-23",-1,days)]);
// ---- the day a week opens on ----
// Today where the week holds it; else its first sitting the filters show,
// so a week whose Monday is a study commission's alone does not open on a
// day showing nothing; else its first sitting; else its Monday.
const agingDay={head:"",cards:[aging[0]]}, judDay={head:"",cards:[jud]};
const two={"2026-03-09":agingDay,"2026-03-10":judDay};
ok(C.firstDay("2026-W11",two,"2026-01-05","2026-01-05","2026-12-27",F({}))==="2026-03-10"
   && C.firstDay("2026-W11",two,"2026-01-05","2026-01-05","2026-12-27",ON)==="2026-03-09"
   && C.firstDay("2026-W11",two,"2026-01-05","2026-01-05","2026-12-27")==="2026-03-09"
   && C.firstDay("2026-W11",{"2026-03-09":agingDay},"2026-01-05","2026-01-05","2026-12-27",F({}))==="2026-03-09"
   && C.firstDay("2026-W11",two,"2026-03-12","2026-01-05","2026-12-27",F({}))==="2026-03-12"
   && C.firstDay("2026-W11",{},"2026-01-05","2026-01-05","2026-12-27",F({}))==="2026-03-09",
   "the day a week opens on: "+C.firstDay("2026-W11",two,"2026-01-05","2026-01-05","2026-12-27",F({})));
// ---- the clock ----
const clocks={"09:05":"9:05 AM","9:30":"9:30 AM","00:30":"12:30 AM","12:00":"12:00 PM","12:15":"12:15 PM",
  "13:30":"1:30 PM","23:59":"11:59 PM","":"","TBA":"TBA","24:00":"24:00"};
const badClock=Object.keys(clocks).filter(t=>C.clock(t)!==clocks[t].replace(/ (AM|PM)$/,NB+"$1"));
ok(!badClock.length, "the clock: "+badClock.map(t=>JSON.stringify(t)+" is "+JSON.stringify(C.clock(t))).join(", "));
// ---- the grid ----
const g=C.gridHtml({view:"2026-03",sel:"2026-03-10",focus:"2026-03-10",today:"2026-03-11",
  first:"2026-03-02",last:"2026-04-05",days,f:F({})});
const tr=g.split("<tr").slice(1);
ok(/<th scope="col"><span aria-hidden="true">Mo</.test(g) && /<th scope="col"><span aria-hidden="true">Su<\/span><span class="sr">Sunday<\/span><\/th><\/tr>/.test(g),
   "the grid does not run Monday to Sunday");
ok(tr.length===7 && tr.slice(1).every(r=>(r.match(/role="gridcell"/g)||[]).length===7), "the grid is not rows of seven");
ok(C.monthRows("2026-03").every(r=>C.weekday(r[0])===0 && C.weekday(r[6])===6) && C.monthRows("2026-03")[0][0]==="2026-02-23",
   "a month's rows do not start on a Monday");
const band=tr.filter(r=>/^ class="cmrow cmsel"/.test(r));
ok(band.length===1 && /data-d="2026-03-09"/.test(band[0]) && /data-d="2026-03-15"/.test(band[0]), "the selected week is not one band");
ok((g.match(/aria-selected="true"/g)||[]).length===1 && /data-d="2026-03-10" tabindex="0" aria-selected="true"/.test(g), "the selected day");
ok(/data-d="2026-03-11" tabindex="-1" aria-selected="false" aria-current="date"/.test(g), "today is not aria-current=date");
ok(/class="cmday cmpast" data-d="2026-03-09"/.test(g) && /class="cmday cmpast cmpick" data-d="2026-03-10"/.test(g)
   && /class="cmday" data-d="2026-03-12"/.test(g), "the past is not greyed, or the future is");
ok(/data-d="2026-02-23"[^>]*aria-disabled="true"/.test(g), "a day before the calendar's first is offered");
const cellOf=(h,d)=>{ const m=new RegExp('data-d="'+d+'"[^>]*>(.*?)</td>').exec(h); return m&&m[1]; };
ok(/<i class="k-hearing"><\/i><i class="k-exec"><\/i><\/span><span class="sr">Tuesday, March 10, 2026, 2 meetings</.test(cellOf(g,"2026-03-10")),
   "10 March in the grid: "+cellOf(g,"2026-03-10"));
ok(/cmdots" aria-hidden="true"><\/span><span class="sr">Friday, March 13, 2026, study committee meetings only</.test(cellOf(g,"2026-03-13")),
   "a study committee's day for a new reader: "+cellOf(g,"2026-03-13"));
const gOn=C.gridHtml({view:"2026-03",sel:"2026-03-10",focus:"2026-03-10",today:"2026-03-11",first:"2026-03-02",last:"2026-04-05",days,f:ON});
ok(/cmdots" aria-hidden="true"><i class="k-study"><\/i><\/span><span class="sr">Friday, March 13, 2026, 1 meeting</.test(cellOf(gOn,"2026-03-13")),
   "a study committee's dot: "+cellOf(gOn,"2026-03-13"));
ok(/cmdots" aria-hidden="true"><\/span><span class="sr">Saturday, March 14, 2026, no meetings, 1 cancelled</.test(cellOf(gOn,"2026-03-14")),
   "a cancelled meeting's day: "+cellOf(gOn,"2026-03-14"));
ok(/Monday, March 9, 2026, no meetings/.test(cellOf(g,"2026-03-09")), "an empty day: "+cellOf(g,"2026-03-09"));
const g2=C.gridHtml({view:"2026-03",sel:"2026-03-10",focus:"2026-03-10",today:"2026-03-11",first:"2026-03-02",last:"2026-04-05",days,f:F({cats:["study"]})});
ok(!/data-d="2026-03-10"[^>]*><span class="cmn" aria-hidden="true">10<\/span><span class="cmdots" aria-hidden="true"><i/.test(g2), "the grid's dots do not follow the boxes");
ok(C.barsOf([{kinds:["other"]},{kinds:["study"]},{kinds:["floor"]},{kinds:["conf"]},{kinds:["meet"]},{kinds:["exec"]},{kinds:["hearing"]}]).join()
   ==="hearing,exec,meet,conf,floor,study,other", "the grid's dots are not in the order of the boxes");
// ---- the preview ----
const many={head:"",cards:[...Array(7).keys()].map(i=>Object.assign({},jud,{name:"C"+i,time:"0"+(i+1)+":00"}))};
const p=C.peekHtml("2026-03-10",{days:{"2026-03-10":many},f:F({})},5);
ok((p.match(/<li>/g)||[]).length===5 && /and 2 more/.test(p), "the preview is not capped at five with the rest counted: "+p);
ok(p.indexOf('<span class="pkt">1:00'+NB+'AM</span>')>=0 && !/<span class="pkt">0/.test(p), "the preview's times are not a reader's: "+p);
ok(/<em>cancelled<\/em>/.test(C.peekHtml("2026-03-14",{days,f:ON},5)), "the preview does not mark a cancelled meeting");
ok(/<p class="pkmore">Study committee meetings only\.<\/p>/.test(C.peekHtml("2026-03-13",{days,f:F({})},5)), "a day whose one meeting is hidden: "+C.peekHtml("2026-03-13",{days,f:F({})},5));
ok(/<p class="pkmore">1 meeting is hidden by the filters\.<\/p>/.test(C.peekHtml("2026-03-13",{days,f:F({cats:[],q:"x"})},5)), "a day the reader's own filter emptied: "+C.peekHtml("2026-03-13",{days,f:F({cats:[],q:"x"})},5));
ok(/Nothing is scheduled/.test(C.peekHtml("2026-03-09",{days,f:F({})},5)), "an empty day's preview");
// ---- the address: the query ----
const s=F({v:"week",cats:["hearing","exec"],body:"H",picks:["Health, Human Services and Elderly Affairs"],q:"HB 1"});
const qs=C.writeQuery(s,"2026-W11","2026-03-10"), back=C.readQuery(qs);
ok(qs==="?week=2026-W11&day=2026-03-10&view=week&kinds=hearing,exec&chamber=house&committee=Health,+Human+Services+and+Elderly+Affairs&q=HB+1",
   "the query is written as "+qs);
ok(back && back.week==="2026-W11" && back.d==="2026-03-10" && back.v==="week" && back.cats.join()==="hearing,exec"
   && back.body==="H" && back.picks[0]==="Health, Human Services and Elderly Affairs" && back.q==="HB 1", "the query does not round-trip: "+JSON.stringify(back));
ok(C.writeQuery(F({}),"2026-W11","")==="?week=2026-W11", "a new reader's filters are written into the address: "+C.writeQuery(F({}),"2026-W11",""));
ok(C.writeQuery(ON,"2026-W11","")==="?week=2026-W11&kinds=hearing,exec,work,conf,floor,study,date"
   && C.writeQuery(F({cats:[]}),"2026-W11","")==="?week=2026-W11&kinds=", "the boxes in the address: "+C.writeQuery(ON,"2026-W11",""));
ok(C.readQuery("?week=2026-W11&kinds=").cats.length===0 && C.readQuery("?week=2026-W11&kinds=study,study,nonsense").cats.join()==="study",
   "an empty or a doubled list of boxes read back wrong");
ok(C.readQuery("")===null && C.readQuery("?utm_source=x")===null && C.readQuery("?week=2026-W99")===null
   && C.readQuery("?week=2025-W53")===null && C.readQuery("?week=2026-W53").week==="2026-W53"
   && C.readQuery("?week=2026-w11").week==="2026-W11" && C.readQuery("?day=2026-02-30")===null
   && C.readQuery("?chamber=Senate").body==="S" && C.readQuery("?chamber=x")===null && C.readQuery("?view=month")===null,
   "the query reads what is not a week, a day, a view or a chamber");
ok(C.isWeek("2026-W01") && !C.isWeek("2026-W00") && C.isDay("2028-02-29") && !C.isDay("2026-02-29"), "weeks and days that are not");
// ---- the address as it was written before 25 September ----
const old=C.readHash("#d=2026-03-10&v=week&who=standing&what=hearing%2Cexec&b=H&c=Health%2C+Human+Services+and+Elderly+Affairs&q=HB+1");
ok(old && old.d==="2026-03-10" && old.v==="week" && old.cats.join()==="hearing,exec,date" && old.body==="H"
   && old.picks[0]==="Health, Human Services and Elderly Affairs" && old.q==="HB 1", "an old address reads as "+JSON.stringify(old));
ok(C.readHash("#d=2026-03-10&what=hearing").cats.join()==="hearing,floor,date"
   && C.readHash("#d=2026-03-10&who=standing,study,floor").cats.join()==="hearing,exec,work,conf,floor,study,date"
   && C.readHash("#d=2026-03-10&who=floor").cats.join()==="floor,date" && C.readHash("#d=2026-03-10").cats===undefined,
   "an old address's who and what do not come across as the boxes that answer them");
ok(C.readHash("#results")===null, "the skip link's #results reads as a state");
const bad=C.readHash("#d=2026-02-30&v=day");
ok(bad && bad.d===undefined && bad.v==="list" && C.readHash("#d=2026-02-30")===null
   && C.readHash("#d=2026-13-01")===null && C.readHash("#d=2028-02-29").d==="2028-02-29",
   "a day the calendar does not have is read out of the address: "+JSON.stringify(bad));
// ---- dates and keys ----
ok(C.weekKey("2026-12-31")==="2026-W53" && C.weekKey("2027-01-03")==="2026-W53" && C.weekKey("2027-01-04")==="2027-W01"
   && C.weekKey("2025-12-29")==="2026-W01" && C.keyMonday("2026-W01")==="2025-12-29", "ISO weeks across a year's end");
ok(C.stepKey("2026-03-11","ArrowUp")==="2026-03-04" && C.stepKey("2026-03-11","Home")==="2026-03-09"
   && C.stepKey("2026-03-11","End")==="2026-03-15" && C.stepKey("2026-01-31","PageDown")==="2026-02-28"
   && C.stepKey("2026-03-11","PageUp",true)==="2025-03-11", "the grid's keys");
ok(C.relWord("2026-03-12","2026-03-11")==="tomorrow" && C.relWord("2026-03-25","2026-03-11")==="in 14 days"
   && C.relWord("2026-03-26","2026-03-11")==="" && C.relWord("2026-03-10","2026-03-11")==="", "the relative day words");
if(fails.length){ console.log(fails.join("\n")); process.exit(1); }
console.log("7 cards: the seven boxes alone and together, picks and the search with Study Committee off, the list's days, the week's columns and entries, the Day view's steps, the clock, the grid's cells and dots, the preview, the query and the old hash");
console.log("OK");
"""


@check("frontend", "the home page's Coming up is this week, the week the Calendar tab shows")
def _coming_up_is_this_week():
    """Coming up drew a fortnight under a comment saying it drew a week.

    Its comment said the rail was "the Calendar tab's own unit, so the rail
    and the page it links to agree". It was not: it read home.json's fourteen
    days and stopped at the seventh DATE that had a meeting, so on Wednesday
    23 September 2026 it ran to 7 October and seven of its nine cards were in
    other weeks. In session a second limit bit first -- home.json keeps
    eighty bill rows and a January day holds 138 -- so the rail stopped
    partway through one day while calendar.html showed the whole week. It
    also held committee rows only, where the week page holds the floor. A
    note under it said "N more bills sit in the fortnight beyond these" about
    rows the cap had dropped from the day already shown.

    Nothing checked the window, so nothing noticed. This draws the rail for
    four fixed days -- a Monday, a Thursday, a Saturday and a Sunday, the one
    getDay() calls 0 -- out of rows written here, and holds it to the week
    build_calendar draws: from today to Sunday, every sitting in that span,
    the floor included, a hundred bills on one day and all of them shown;
    from Saturday the next week's, whole and named Next Week (D13, the
    person, 8 October 2026, item 120); and the rail ending with "See the
    full calendar" (item 118), where it once counted next week. Then it runs
    HOME_JS's own block in node against a stub page, because the build is
    read for days after it is made and it is the script that keeps the rail
    to the READER's week. _chain holds the built fixture home page to it too.
    """
    import contextlib
    import datetime as _dt
    import io
    import build_pages as BP
    import build_calendar as BC

    def rows_for(today, weekdays_only=False):
        rows = []
        for k in range(-3, 12):
            d = today + _dt.timedelta(days=k)
            if weekdays_only and d.weekday() > 4:
                continue
            rows.append({"term": "2025-2026", "bill": f"HB{200 + k}", "body": "H",
                         "kind": "public hearing", "date": d.isoformat(),
                         "time": "10:00", "committee": "Commerce",
                         "venue": "LOB 302"})
        if weekdays_only:
            return rows
        # PAST THE OLD CAP: a hundred bills in one sitting, where home.json
        # kept eighty rows for the whole fortnight.
        for i in range(100):
            rows.append({"term": "2025-2026", "bill": f"SB{i + 1}", "body": "S",
                         "kind": "executive session", "date": today.isoformat(),
                         "time": f"{9 + i // 12:02d}:{(i % 12) * 5:02d}",
                         "committee": "Judiciary", "venue": "SH 100"})
        # A FLOOR SITTING, which carries no committee: the Calendar tab shows
        # it, and the rail's old source dropped every one.
        rows.append({"term": "2025-2026", "bill": "HB9", "body": "H",
                     "kind": "floor debate", "date": today.isoformat(),
                     "time": "", "committee": "", "venue": ""})
        return rows

    tmp = Path(tempfile.mkdtemp(prefix="gr-comingup-"))
    try:
        checked = 0
        for today in (_dt.date(2026, 9, 21), _dt.date(2026, 9, 24),
                      _dt.date(2026, 9, 26), _dt.date(2026, 9, 27)):
            rows = rows_for(today)
            with contextlib.redirect_stdout(io.StringIO()):
                page = BP.calendar_html(tmp, today=today, rows=rows)
            ahead = today.weekday() >= 5
            start = BC.monday(today) + _dt.timedelta(days=7) if ahead else today
            sun = BC.monday(start) + _dt.timedelta(days=6)
            t, s = start.isoformat(), sun.isoformat()
            shown = re.findall(r'class="calday" data-d="([^"]+)"', page)
            wide = [d for d in shown if not t <= d <= s]
            assert not wide, (
                f"built on {today:%a %d %b}, Coming up shows {wide}, outside "
                f"its week ({t} to {s}) -- the rail is the Calendar tab's "
                "week, not a fortnight, and from Saturday the next")
            name = re.search(r'<p class="calwk"><span class="chip">([^<]+)</span> <span>([^<]+)</span>',
                             page)
            assert name and name.group(1) == ("Next Week" if ahead else "This Week"), (
                f"built on {today:%a %d %b}, Coming up's week is named "
                f"{name.group(1) if name else 'nothing'}")
            # The same sittings the Calendar tab's week holds from its first
            # day on: read through the same function, so the two cannot differ.
            week = BC.weeks_from(rows).get(BC.week_key(start)) or {}
            want = {(k.date, BP.card_name(k).lower()) for d in week if d >= t
                    for k in week[d]}
            got = set(re.findall(
                r'<details class="calmeet"[^>]*? data-cmte="([^"]*)"[^>]*? '
                r'data-date="([^"]*)"', page))
            got = {(d, c) for c, d in got}
            assert got == want, (
                f"built on {today:%a %d %b}, Coming up and the Calendar tab's "
                f"week disagree: only on the rail {sorted(got - want)}, only "
                f"on the week page {sorted(want - got)}")
            if not ahead:
                assert "House Session Day" in page, (
                    "a floor sitting this week is on the Calendar tab and not in "
                    "Coming up, named as the Calendar names it")
                n_sb = len(set(re.findall(r'bills#SB(\d+)"', page)))
                assert n_sb == 100, (
                    f"one sitting of 100 bills shows {n_sb} of them in Coming up: "
                    "the rail is capped again, and cuts a day short")
            line = re.search(r'<p class="calmore calall">(.*?)</p>', page)
            assert line and line.group(1) == '<a href="calendar.html">See the full calendar</a>', (
                f"built on {today:%a %d %b}, Coming up does not end with See the "
                f"full calendar: {line.group(1) if line else 'nothing'!r}")
            assert "fortnight" not in page, (
                "Coming up still speaks of a fortnight, and it shows one week")
            checked += 1

        # A SATURDAY WITH THE WEEK'S BUSINESS OVER: the rail is next week's,
        # named Next Week with its weekdays, never read as the week gone (D13).
        sat = _dt.date(2026, 9, 26)
        with contextlib.redirect_stdout(io.StringIO()):
            page = BP.calendar_html(tmp, today=sat,
                                    rows=rows_for(sat, weekdays_only=True))
        days = re.findall(r'class="calday" data-d="([^"]+)"', page)
        assert days and days[0] >= "2026-09-28" and days[-1] <= "2026-10-04", (
            f"on a Saturday Coming up draws {days}, not next week's days")
        assert '<span class="chip">Next Week</span> <span>Sep 28 – Oct 2, 2026</span>' in page, (
            "on a Saturday Coming up does not name next week and its weekdays: "
            + page[:300])
        # AND A WEEKDAY WITH THE WEEK'S BUSINESS OVER says so, and offers the
        # full calendar.
        fri = _dt.date(2026, 10, 2)
        with contextlib.redirect_stdout(io.StringIO()):
            page = BP.calendar_html(tmp, today=fri,
                                    rows=[r for r in rows_for(fri, weekdays_only=True)
                                          if r["date"] < fri.isoformat()])
        assert "calday" not in page and "rest of this week" in page \
            and "See the full calendar" in page, (
                "an empty rest of the week does not say so and offer the calendar: "
                + page[:300])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # --- and in the reader's clock, which is what keeps it there ------------
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return "ok", (f"{checked} build dates; node is not on PATH, so HOME_JS's "
                      "own week was not run")
    m = re.search(r"\(function\(\)\{\s*const now=new Date\(\);.*?\n  \}\)\(\);",
                  BP.HOME_JS, re.S)
    # COMING UP'S OWN DAYS: Latest Activity's are .calday blocks too, all past,
    # and this block would retire every one of them (24 October 2026).
    assert m and ".cal .calday[data-d]" in m.group(0), (
        "HOME_JS has no block reading Coming up's own .calday[data-d] in the reader's clock")
    span = [(_dt.date(2026, 9, 20) + _dt.timedelta(days=k)).isoformat()
            for k in range(16)]
    for reader, days, want_kept in (
            ("2026-09-21", span, span[1:8]),     # a Monday: the whole week
            ("2026-09-24", span, span[4:8]),     # a Thursday: to Sunday
            ("2026-09-26", span, span[8:15]),    # a Saturday: next week (D13)
            ("2026-09-27", span, span[8:15]),    # a Sunday: next week
            ("2026-09-27", span[8:], span[8:15]),  # a Sunday, next week built
            ("2026-09-26", span[:7], [])):       # a Saturday, this week built
        y, mo, d = map(int, reader.split("-"))
        prog = _components_js() + "\n" + (
            "const R=Date;class D extends R{constructor(...a){a.length?super(...a)"
            f":super({y},{mo - 1},{d},15,30);}}static now(){{return new D().getTime();}}}}"
            "globalThis.Date=D;"
            "const mk=d=>({dataset:{d},gone:false,rel:{textContent:''},"
            "remove(){this.gone=true;},querySelector(s){return s==='.cdrel'?this.rel:null;}});"
            f"const days={json.dumps(days)}.map(mk);"
            "const calall={outerHTML:'<p class=\"calmore calall\">NEXT</p>'};"
            "const cal={innerHTML:'',querySelector(s){return s==='.calall'?calall:null;}};"
            "globalThis.document={querySelectorAll(s){return s==='.cal .calday[data-d]'?days:[];},"
            "querySelector(s){return s==='.cal'?cal:null;}};\n"
            + m.group(0) + "\n"
            "process.stdout.write(JSON.stringify({kept:days.filter(e=>!e.gone)"
            ".map(e=>e.dataset.d),labels:days.filter(e=>!e.gone).map(e=>e.rel.textContent),"
            "cal:cal.innerHTML}));")
        r = _node_file(node, prog, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, ("HOME_JS's Coming up block would not run: "
                                   + (r.stderr or "")[-300:])
        got = json.loads(r.stdout)
        assert got["kept"] == want_kept, (
            f"read on {reader}, HOME_JS keeps {got['kept']} of the rail; this "
            f"week from that day is {want_kept}")
        assert all(x for x in got["labels"]), (
            f"read on {reader}, a day in Coming up has no relative label: "
            f"{got['labels']}")
        if not want_kept:
            assert "this week" in got["cal"] and "NEXT" in got["cal"], (
                "when the reader's week has nothing left, HOME_JS must say so "
                "and keep the line to the full calendar: " + got["cal"][:200])
    return "ok", (f"{checked} build dates and 6 reading dates: today to Sunday, "
                  "uncapped, the floor included; from Saturday next week, named so; "
                  "the full calendar offered")


@check("frontend", "the home page's Coming up leaves the special study committees to the Calendar and keeps a standing committee's interim study")
def _coming_up_without_study_committees():
    """"Study committee meetings should not be in 'Coming up'" (the person,
    7 October 2026, F1), and the same day which: a special committee a bill
    set up to study something -- "Committee to Study Siting and Maintenance
    Rules Regarding Certain Intellectual and Developmental Disability (IDD)
    and Acquired Brain Disorder (ABD) Community Residences" -- is left off;
    a standing committee's interim study sessions stay.

    The rail is drawn for a Monday out of rows written here: a statutory
    committee's meeting as the database copy gives it, a study committee's
    sitting on a bill as the docket files it, and a standing committee's
    work session on a bill held for interim study, this week and next. The
    rail holds the standing committee alone; a week of study committees
    alone is an empty week on the rail, which says no House or Senate
    committee meeting is scheduled rather than that nothing is (the audit of
    25 October 2026, M8), and says only that (the owner's choice of 26
    October 2026: not when the General Court sits), and whose chip and
    sentence name the same week when HOME_JS reads a weekend's build on a
    weekday (the preview check of the same day); and the Calendar's own week
    still holds them all.
    """
    import contextlib
    import datetime as _dt
    import io
    import build_pages as BP
    import build_calendar as BC
    monday = _dt.date(2026, 9, 21)

    def study(d, name):
        return {"study": True, "bill": "", "kind": "study committee", "date": d,
                "time": "10:00", "committee": name, "venue": "LOB 205",
                "body": "", "term": "", "note": "Regular meeting."}

    def docket_study(d, bill):
        return {"term": "2025-2026", "bill": bill, "body": "H", "kind": "study committee",
                "date": d, "time": "", "committee": f"Committee to Study {bill}", "venue": ""}

    def interim(d, bill):
        return {"term": "2025-2026", "bill": bill, "body": "H",
                "kind": "full committee work session", "date": d, "time": "10:00",
                "committee": "Education Funding", "venue": "GP 232"}

    long_name = ("Committee to Study Siting and Maintenance Rules Regarding Certain "
                 "Intellectual and Developmental Disability (IDD) and Acquired Brain "
                 "Disorder (ABD) Community Residences")
    rows = [study("2026-09-23", long_name), docket_study("2026-09-24", "HB1099"),
            interim("2026-09-23", "HB1288"),
            # Next week: one standing sitting and two study committees.
            interim("2026-09-29", "HB1579"), study("2026-09-30", long_name),
            study("2026-10-01", "Commission on Aging")]
    tmp = Path(tempfile.mkdtemp(prefix="gr-comingup-study-"))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            page = BP.calendar_html(tmp, today=monday, rows=rows)
        assert "Committee to Study" not in page and 'data-who="study"' not in page \
            and "Commission on Aging" not in page, (
                "Coming up still draws a special study or statutory committee: "
                + ", ".join(re.findall(r'class="calcmte">([^<]*)<', page)))
        cards = re.findall(r'<details class="calmeet"[^>]*? data-cmte="([^"]*)"', page)
        assert cards == ["house education funding"], (
            f"Coming up's cards are {cards}: a standing committee's interim study "
            "session belongs on it")
        line = re.search(r'<p class="calmore calall">(.*?)</p>', page)
        assert line and "See the full calendar" in line.group(1), (
            "the line under Coming up is not the full calendar: "
            + (line.group(1) if line else "no line"))
        # A WEEK OF STUDY COMMITTEES ALONE is a week with no meeting on the
        # rail. Drawn with no key dates (events=[]): the week of 21 September
        # 2026 holds the Senate's filing period, which the rail shows as its
        # own line (_coming_up_key_dates), and this is about meetings.
        with contextlib.redirect_stdout(io.StringIO()):
            empty = BP.calendar_html(tmp, today=monday, rows=[r for r in rows if r.get("study")
                                                              or r["kind"] == "study committee"],
                                     events=[])
        assert "calday" not in empty and "rest of this week" in empty, (
                "a week of study committees alone still draws a day in Coming up: "
                + empty[:300])
        # AND IT DOES NOT SAY "NOTHING" (the audit of 25 October 2026, M8):
        # the study committees are meeting, on the Calendar. It says what the
        # rail holds and does not -- the chambers' own meetings -- this week,
        # from a Saturday next week, and in the reader's clock (HOME_JS).
        with contextlib.redirect_stdout(io.StringIO()):
            sat = BP.calendar_html(tmp, today=_dt.date(2026, 9, 26),
                                   rows=[r for r in rows if r.get("study")
                                         or r["kind"] == "study committee"], events=[])
        said = {"this week": empty, "next week": sat}
        want = {"this week": "No House or Senate committee meetings are scheduled for the "
                             "rest of this week.",
                "next week": "No House or Senate committee meetings are scheduled next week."}
        for k, page_ in said.items():
            assert "Nothing" not in page_ and want[k] in page_, (
                f"a {k} of study committees alone does not say that no House or Senate "
                f"committee meeting is scheduled: {page_[:300]}")
        assert ('tr("cal.none_else","No more House or Senate committee meetings are scheduled '
                'this week.")' in BP.HOME_JS and "Nothing else is scheduled" not in BP.HOME_JS
                and "sits mostly" not in BP.HOME_JS and "cal.season" not in BP.HOME_JS), (
                    "HOME_JS's empty rest of the week says other words than the built rail's")
        # AND ITS SENTENCE NAMES THE WEEK THE CHIP DOES, IN THE READER'S CLOCK
        # (the preview check of 25 October 2026). The preview, built on Sunday
        # 25 October with no House or Senate meeting in the week of the 26th,
        # read from the Monday on as "This Week" over "No House or Senate
        # committee meetings are scheduled next week.": HOME_JS renamed the
        # chip from data-mon and could not reach the sentence. That rail is
        # built here, in both languages, and HOME_JS's block run on it in
        # node for a reader on the Sunday, the Monday, the Wednesday and the
        # Friday: the chip and the note must read as a build made on the
        # reader's own day draws them.
        import html as _html
        import i18n
        node = shutil.which("node") or shutil.which("node.exe")
        blk = re.search(r"\(function\(\)\{\s*const now=new Date\(\);.*?\n  \}\)\(\);",
                        BP.HOME_JS, re.S)
        assert blk, "HOME_JS has no block saying Coming up's week in the reader's clock"

        def rail(t):
            """(data-mon, the chip, the note's first sentence, the note) of a
            built empty rail, as text; the sentence None where it is not an
            element of its own."""
            mon = re.search(r'<section class="cal" data-mon="([^"]+)"', t)
            chip = re.search(r'<p class="calwk"><span class="chip">([^<]+)</span>', t)
            note = re.search(r'<p class="note">(.*?)</p>', t, re.S)
            assert mon and chip and note, f"an empty Coming up has no week, chip or note: {t[:300]}"
            first = re.search(r'<span class="calnomeet">([^<]*)</span>', note.group(1))
            text = lambda h: " ".join(_html.unescape(re.sub(r"<[^>]+>", "", h)).split())
            return (mon.group(1), _html.unescape(chip.group(1)),
                    _html.unescape(first.group(1)) if first else None, text(note.group(1)))

        built = _dt.date(2026, 10, 25)
        ran = 0
        for lang in ("en", "es"):
            with contextlib.redirect_stdout(io.StringIO()):
                page = BP.calendar_html(tmp, today=built, rows=[], events=[], lang=lang)
            mon, chip, first, note = rail(page)
            assert first and note.startswith(first), (
                f"{lang}: an empty Coming up's sentence on its week is not an element of its "
                f"own, so HOME_JS cannot say it again with the chip: {page[:400]}")
            # AND IT IS THE NOTE'S ONLY SENTENCE (the owner's choice of 26
            # October 2026, B): "The General Court sits mostly from January
            # to June, and committees meet on bills from the fall filing
            # period onwards." stood after it, in both languages, on an
            # empty rail with next week empty too, as here.
            assert note == first and "January" not in page and "enero" not in page, (
                f"{lang}: an empty Coming up says more than that no meeting is scheduled: "
                f"{note!r}")
            if not node:
                continue
            words = i18n.words_js(lang, BP.HOME_JS) if lang != "en" else ""
            for reader in (built + _dt.timedelta(days=k) for k in (0, 1, 3, 5)):
                with contextlib.redirect_stdout(io.StringIO()):
                    want = rail(BP.calendar_html(tmp, today=reader, rows=[], events=[], lang=lang))
                prog = _components_js() + "\n" + (
                    "const R=Date;class D extends R{constructor(...a){a.length?super(...a)"
                    f":super({reader.year},{reader.month - 1},{reader.day},15,30);}}"
                    "static now(){return new D().getTime();}}globalThis.Date=D;"
                    f"globalThis.window=globalThis;window.GR_LANG={json.dumps(lang)};{words}\n"
                    # components.js has a chip() of its own: the stub's names are its own.
                    f"const stubChip={{textContent:{json.dumps(chip)}}},"
                    f"stubNone={{textContent:{json.dumps(first)}}};"
                    f"const stubCal={{innerHTML:'',dataset:{{mon:{json.dumps(mon)}}},"
                    "querySelector(s){return s==='.calwk .chip'?stubChip"
                    ":s==='.calnomeet'?stubNone:null;}};"
                    "globalThis.document={querySelectorAll(){return [];},"
                    "querySelector(s){return s==='.cal'?stubCal:null;}};\n"
                    + blk.group(0) + "\n"
                    "process.stdout.write(JSON.stringify({chip:stubChip.textContent,"
                    "none:stubNone.textContent,cal:stubCal.innerHTML}));")
                r = _node_file(node, prog, capture_output=True, text=True, timeout=60)
                assert r.returncode == 0, ("HOME_JS's Coming up block would not run on an empty "
                                           "rail: " + (r.stderr or "")[-300:])
                got = json.loads(r.stdout)
                seen = (mon, got["chip"], got["none"], got["none"] + note[len(first):])
                assert seen == want, (
                    f"{lang}: Coming up built empty on {built:%a %d %b} and read on "
                    f"{reader:%a %d %b} shows {seen[1]!r} over {seen[3]!r}; built that day it "
                    f"is {want[1]!r} over {want[3]!r}")
                assert got["cal"] == "", (
                    f"{lang}: HOME_JS redrew an empty Coming up read on {reader:%a %d %b}")
                ran += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # They stay on the Calendar: the week it draws holds all three of this week's.
    week = BC.weeks_from(rows, names={}).get(BC.week_key(monday)) or {}
    held = sorted(BP.meeting_who(k.name, rs) for day in week.values() for k, rs in day.items())
    assert held == ["standing", "study", "study"], (
        f"the Calendar's week holds {held}: the study committees left Coming up only")
    assert BP.home_week(week) and all(
        BP.meeting_who(k.name, rs) != "study" for day in BP.home_week(week).values()
        for k, rs in day.items()), "home_week keeps a study committee"
    # SILENCE IS NOT SUCCESS: a reader's day that never ran would pass above.
    assert ran in (0, 8), f"HOME_JS ran on {ran} of the 8 readers' days of an empty rail"
    return "ok", ("a statutory committee and a docket's study committee off the rail, a "
                  "standing committee's interim study on it, an empty rail's note its one "
                  "sentence in both languages, and all three still on the Calendar's week; "
                  + (f"an empty rail's chip and sentence agree in the reader's clock, {ran} "
                     "readers' days in two languages" if ran else
                     "node is not on PATH, so the empty rail was not read in the reader's clock"))


@check("frontend", "the Calendar's month shows six weeks, the days of the months either side greyed and chosen like any other")
def _calendar_month_six_weeks():
    """"Month view: show the neighbouring months' days, slightly greyed", as a
    desktop calendar does (the person, 7 October 2026, F10). The month drew
    only the weeks its own days fall in, so it showed a day or two of the
    months either side, none at all for a month that begins on a Monday and
    ends on a Sunday (February 2027), and changed height month to month. The
    Calendar's own monthRows is run in node over every month from 2025 to
    2028: six weeks from the Monday on or before the 1st, every day once; and
    gridHtml draws February 2027 in six rows, its neighbours' days marked
    cmout (the grey) and none of them disabled inside the calendar's range."""
    import build_calendar as BC
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return "skip", "node is not on PATH"
    root = Path(tempfile.mkdtemp(prefix="gr-calmonth-"))
    try:
        (root / "week.js").write_text(_with_components(BC.WEEK_JS), encoding="utf-8")
        (root / "go.js").write_text(r"""
const fs = require("fs"), vm = require("vm");
const ctx = vm.createContext({document: {getElementById: () => null}, URLSearchParams});
vm.runInContext(fs.readFileSync("./week.js", "utf8"), ctx);
const C = ctx.GRCAL, out = {bad: [], months: 0};
for (let y = 2025; y <= 2028; y++) for (let m = 1; m <= 12; m++) {
  const k = y + "-" + String(m).padStart(2, "0"), rows = C.monthRows(k), flat = [].concat(...rows);
  const first = k + "-01";
  const ok = rows.length === 6 && rows.every(r => r.length === 7 && C.weekday(r[0]) === 0)
    && flat[0] <= first && C.addDays(flat[0], 7) > first
    && flat.every((d, i) => i === 0 || d === C.addDays(flat[i - 1], 1))
    && flat.filter(d => d.slice(0, 7) === k).length === new Date(y, m, 0).getDate();
  if (!ok) out.bad.push(k + ": " + JSON.stringify(rows.map(r => r[0])));
  out.months++;
}
const g = C.gridHtml({view: "2027-02", sel: "2027-02-10", focus: "2027-02-10", today: "2027-02-10",
  first: "2025-01-06", last: "2028-12-31", days: {}, f: C.defaults()});
out.rows = (g.match(/<tr class="cmrow/g) || []).length;
out.out = (g.match(/class="cmday[^"]*cmout[^"]*"/g) || []).length;
out.off = (g.match(/aria-disabled="true"/g) || []).length;
process.stdout.write(JSON.stringify(out));
""", encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, "the Calendar's script would not run: " + (r.stderr or "")[-300:]
        got = json.loads(r.stdout)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert not got["bad"], f"months that are not six whole weeks from a Monday: {got['bad'][:3]}"
    assert got["rows"] == 6 and got["out"] == 14 and got["off"] == 0, (
        f"February 2027 is drawn in {got['rows']} rows with {got['out']} days of March greyed "
        f"and {got['off']} disabled; six rows, the fourteen days of March in grey, none disabled")
    # AND THE GREY SAYS "ANOTHER MONTH" (the look of 7 October 2026). The
    # neighbours' days took the same grey as the month's own past days, so a
    # past month could not be told from them. The month's own days are tiles
    # on the card's surface and the neighbours' are on the page; the band, the
    # hover and the chosen day are written after the neighbours' rule, at the
    # same weight, so they still win.
    css = _source("src/pages/app.css")
    tile = re.search(r"\.cmgrid td\{[^}]*background:var\(--surface\)\}", css)
    out = css.find(".cmgrid td.cmout{background:none}")
    assert tile and out > tile.start(), (
        "the month's own days and its neighbours' are drawn on the same ground")
    for later in (".cmgrid td:hover{", ".cmrow.cmsel td{", ".cmgrid td.cmpick{"):
        assert css.find(later) > out, f"{later} is written before the neighbours' ground, which beats it"
    return "ok", (f"{got['months']} months each six weeks from the Monday on or before the 1st; "
                  "February 2027 in six rows with March's first fourteen days greyed, off the "
                  "month's tiles")


@check("frontend", "the Calendar is built in Spanish beside the English, week by week, and English gains only the way to it",
       needs=("build_calendar", "calendar_documents", "i18n"))
def _calendar_in_spanish(BC, CD, i18n):
    """/es/calendar and every week's page under /es/calendar/, with a month
    file of its own (es/calendar/data/), the frame, controls and sentences in
    Spanish and the cards as build_pages.cal_days draws them in it; the
    footer's language list and <html>'s data-alt lead each version to the
    other, and the header's Calendar tab leads Spanish pages to the Spanish
    Calendar. Nothing the site wrote is left in English on the Spanish page
    outside what is marked lang="en"; the English pages differ from before
    only by data-alt-es and the footer's link to the Spanish version."""
    import translation_audit
    if not i18n.has("es", "calendar.html"):
        raise AssertionError("i18n.PAGES has no Spanish Calendar")
    shared, base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    if not (site / "calendar.html").exists():
        return "skip", "the fixture has no Calendar"
    en_weeks = sorted(p.name for p in (site / "calendar").glob("2*.html"))
    es_weeks = sorted(p.name for p in (site / "es" / "calendar").glob("2*.html"))
    assert en_weeks and en_weeks == es_weeks, (
        f"English has {len(en_weeks)} week pages and Spanish {len(es_weeks)}: "
        f"{sorted(set(en_weeks) ^ set(es_weeks))[:5]}")
    assert (site / "es" / "calendar.html").exists(), "the Spanish Calendar's own page is missing"
    en_m = sorted(p.name for p in (site / "calendar" / "data").glob("2*.json"))
    es_m = sorted(p.name for p in (site / "es" / "calendar" / "data").glob("2*.json"))
    assert en_m and en_m == es_m, f"month files: English {len(en_m)}, Spanish {len(es_m)}"
    es = (site / "es" / "calendar.html").read_text(encoding="utf-8")
    en = (site / "calendar.html").read_text(encoding="utf-8")
    assert '<html lang="es"' in es and 'data-alt-en="/calendar"' in es, (
        "the Spanish Calendar does not name its English version on <html>")
    assert 'data-alt-es="/es/calendar"' in en and \
        'lang="es" data-href="/es/calendar"' in en, (
            "the English Calendar does not lead to the Spanish one: <html>'s data-alt-es and "
            "the footer's language list")
    assert 'lang="en" data-href="/calendar"' in es, (
        "the Spanish Calendar's footer does not lead back to the English one")
    assert 'window.GR_LANG="es"' in es and "calp.prev_week" in es, (
        "the Spanish Calendar carries no words for its script (i18n.page_words)")
    # THE HEADER'S TAB. A Spanish page's Calendar tab leads to the Spanish one.
    home = (site / "es" / "index.html").read_text(encoding="utf-8")
    assert 'href="/es/calendar.html"' in home or 'href="/es/calendar"' in home, (
        "the header on a Spanish page still leads to the English Calendar")
    assert 'class="calmore calall"><a href="es/calendar"' in home, (
        "Coming up's 'See the full calendar' on the Spanish home page leads to the English Calendar")
    # THE ENGLISH PAGES GAINED NOTHING BUT THE WAY TO THE SPANISH ONES: a
    # week's page with that way taken out is the week's page as it was, which
    # is what build_calendar.week_page writes when `alts` is empty.
    # Names of the Calendar's own words that must not stand on a Spanish page
    # outside lang="en": every "calp." word of the code, in English.
    words, _p = translation_audit.code_words()
    english = [w["en"] for k, w in words.items() if k.startswith("calp.")
               and len(w["en"].split()) >= 3 and "{" not in w["en"] and "&" not in w["en"]]
    seen = _visible_text(es)
    left = [w for w in english if w in seen]
    assert not left, f"the Spanish Calendar says in English: {left[:4]}"
    for lead in ("Skip to the schedule", "Filter the calendar", "Previous Week", "Both chambers",
                 "Study committee meetings only"):
        assert lead not in seen, f"the Spanish Calendar's {lead!r} is in English"
    assert "La semana del" in seen and "lunes" in seen and "viernes" in seen, (
        "the Spanish Calendar's heading and days are not in Spanish")
    # The week's own days, in Spanish: "lunes, 16 de febrero".
    d = BC.datetime.date(2026, 2, 16)
    assert BC.day_words(d.isoformat(), BC.datetime.date(2026, 1, 1), "es") == (
        "lunes, 16 de febrero", ""), BC.day_words(d.isoformat(), BC.datetime.date(2026, 1, 1), "es")
    assert BC.day_words("2026-02-11", BC.datetime.date(2026, 2, 10), "es")[1] == "mañana"
    assert BC.span_words(d, d + BC.datetime.timedelta(days=4), lang="es") == "16–20 de febrero de 2026"
    # Each Spanish month file is the English one's, its cards in Spanish.
    one = en_m[len(en_m) // 2]
    je = json.loads((site / "calendar" / "data" / one).read_text(encoding="utf-8"))
    js = json.loads((site / "es" / "calendar" / "data" / one).read_text(encoding="utf-8"))
    assert list(je["days"]) == list(js["days"]) and list(je["weeks"]) == list(js["weeks"]), (
        f"{one}: the Spanish month holds other days or weeks than the English")
    assert any(v["label"] != js["weeks"][k]["label"] for k, v in je["weeks"].items()), (
        f"{one}: the Spanish month names its weeks as the English does")
    # The English script and picker are the English ones, to the byte; the
    # Spanish are the English with each pair put over it, once.
    assert BC.week_js("en") is BC.WEEK_JS and CD.picker_js("en") is CD.PICKER_JS, (
        "the English Calendar's scripts are not WEEK_JS and PICKER_JS as written")
    assert BC.week_js("es") != BC.WEEK_JS and "tr(\"calp.prev_week\"" in BC.week_js("es")
    assert CD.picker_js("es") != CD.PICKER_JS and 'tr("calp.cd_open"' in CD.picker_js("es")
    return "ok", (f"{len(es_weeks)} week pages and {len(es_m)} month files in Spanish, each the "
                  "English's counterpart, its words Spanish and the record's marked; English leads to it")


# components.js first, as the page loads it and with no window, as every
# harness here loads it; then the page's language and words, as the head
# carries them, and the script.
_CAL_ES_BEFORE = "globalThis.document={getElementById:function(){return null;}};\n"
_CAL_ES_AFTER = 'globalThis.window=globalThis; globalThis.GR_LANG="es";\n'

_CAL_ES_CHECK = r"""
const C=globalThis.GRCAL, fs=require("fs"), fails=[];
const ok=(c,m)=>{ if(!c) fails.push(m); };
const eq=(a,b,m)=>{ if(a!==b) fails.push(m+": "+JSON.stringify(a)+" is not "+JSON.stringify(b)); };
eq(C.dayWords("2026-02-16"),"lunes, 16 de febrero","a day");
eq(C.weekLabel("2026-W08"),"16–20 de febrero de 2026","a week");
eq(C.weekLabel("2026-W08","medium"),"16–20 feb. 2026","a week, short");
eq(C.relWord("2026-02-17","2026-02-16"),"mañana","tomorrow");
eq(C.relWord("2026-02-16","2026-02-16"),"hoy","today");
eq(C.relWord("2026-02-19","2026-02-16"),"en 3 días","in days");
const T=(total,shown,seen,study)=>({total:total,shown:shown,seen:seen,study:study});
const wk=tr("calp.where_week","this week");
eq(C.countLine(T(5,5,5,0),wk),"5 reuniones esta semana.","a count");
eq(C.countLine(T(1,1,1,0),wk),"1 reunión esta semana.","one meeting");
eq(C.countLine(T(0,0,0,0),wk),"No hay reuniones esta semana.","no meetings");
eq(C.countLine(T(5,3,3,0),wk),"3 de 5 reuniones se muestran.","some shown");
eq(C.countLine(T(4,0,0,0),wk),"Ninguna de las 4 reuniones esta semana coincide.","none match");
eq(C.countLine(T(5,3,3,2),wk),"3 de 5 reuniones se muestran. 2 reuniones de comités de estudio están ocultas.","study hidden");
eq(C.countLine(T(3,0,0,3),wk),"3 reuniones de comités de estudio están ocultas.","study alone");
eq(C.emptyWords([],C.defaults()),"No hay reuniones","an empty day");
const cards=JSON.parse(fs.readFileSync(process.argv[2],"utf8")), en=JSON.parse(fs.readFileSync(process.argv[3],"utf8"));
const names=(j)=>[].concat(...Object.keys(j.days).map(d=>C.parseDay(j.days[d]).cards.map(e=>e.name))).sort();
const a=names(cards), b=names(en);
ok(a.length>0 && a.length===b.length,"a month's cards parse the same in Spanish: "+a.length+" and "+b.length);
// A session day and a conference are named in the page's words; a committee's name is the record's.
const said=(n)=>/^(Día de sesión|Comité de conferencia)/.test(n), wrote=(n)=>/^(House Session Day|Senate Session Day|Committee of conference)/.test(n);
const ra=a.filter(n=>!said(n)), rb=b.filter(n=>!wrote(n));
ok(ra.length===rb.length && ra.every((n,i)=>n===rb[i]),"a committee's name is not read as the record has it in Spanish too: "+JSON.stringify(ra.filter((n,i)=>n!==rb[i]).slice(0,3)));
const grid=C.gridHtml({view:"2026-03",sel:"2026-03-09",focus:"2026-03-09",today:"2026-03-09",first:"2026-01-05",last:"2026-12-31",days:{},f:C.defaults()});
ok(/aria-hidden="true">Lu<\/span><span class="sr">lunes<\/span>/.test(grid),"the grid's head is Lu, lunes...");
ok(/sábado/.test(grid)&&/domingo/.test(grid),"the grid names Saturday and Sunday");
const cell=C.cellHtml("2026-03-09",{first:"2026-01-05",last:"2026-12-31",days:{},f:C.defaults(),view:"2026-03",today:"2026-03-09",sel:"2026-03-09",focus:"2026-03-09"});
ok(/lunes, 9 de marzo de 2026, cargando/.test(cell),"a day's name for a screen reader: "+cell.slice(-160));
console.log(fails.length?fails.join("\n"):"OK");
"""


@check("frontend", "the Calendar's script says its dates, counts and sentences in Spanish, and reads a Spanish card as it reads an English one",
       needs=("build_calendar", "i18n"))
def _calendar_script_in_spanish(BC, i18n):
    """WEEK_JS in node with the page's language set to Spanish and the words
    the page would carry (i18n.words_js over week_js("es")): a day, a week and
    a count in Spanish; a card drawn by cal_days in Spanish -- its committee's
    name marked lang="en" -- is read as the English card is; and the grid names
    its days in Spanish. The English script is held by the checks above it."""
    node = _cal_node()
    if not node:
        return "skip", "node is not on PATH"
    if not Path("src/pages/bills.html").exists():
        return "skip", "bills.html is not here"
    root = Path(tempfile.mkdtemp(prefix="gr-calspanish-"))
    try:
        site, weeks, order, _u, _m = _cal_fixture(root)
        import datetime as _dt
        import contextlib
        import io
        today = _dt.date(*CAL_TODAY)
        with contextlib.redirect_stdout(io.StringIO()):
            BC.month_files(site, weeks, order, {}, {}, {}, today, lang="es")
        js = BC.week_js("es")
        words = i18n.words_js("es", js)
        prog = root / "es.js"
        prog.write_text(_CAL_ES_BEFORE + _components_js() + "\n" + _CAL_ES_AFTER + words + "\n" + js
                        + _CAL_ES_CHECK, encoding="utf-8")
        r = _run([node, str(prog), str(site / "es" / "calendar" / "data" / "2026-03.json"),
                  str(site / "calendar" / "data" / "2026-03.json")],
                 capture_output=True, text=True, encoding="utf-8", timeout=120)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        assert r.returncode == 0 and out.endswith("OK"), out[-1800:]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", "a day, a week, six counts and the grid said in Spanish; a Spanish card parsed as the English one"


@check("build", "the Senate calendar fetch saves a PDF or nothing, and stops when told no",
       needs=("fetch_senate_calendars",))
def _senate_calendars(SC):
    """664 calendars of 1998-2008 are still 'wanted' from a single 403.

    This script shipped with none of the safety the other fetchers have: no
    lock, so it could run beside the lane as a second worker at the address
    that has blocked this project twice; no refusal check, so it would have run
    straight through one; no reading of an error, so a 403 counted the same as
    a missing document; and a 2.5-second delay.

    Two failure modes are specific to fetching PDFs and are what this covers.

    A BLOCK PAGE IS NOT A CALENDAR and arrives with HTTP 200. Saved, it sits in
    calendars_senate/ named SC012.pdf, is counted as held for good, and
    extract_vetoes reads it for veto messages it does not contain.

    A TRUNCATED FILE IS WORSE THAN NO FILE. The loop wrote straight into the
    final name with copyfileobj, so a run interrupted mid-document left half a
    PDF that `local.exists()` skipped on every later run. Absent gets asked
    again; half does not.
    """
    import refusal
    here = Path(".").resolve()
    root = Path(tempfile.mkdtemp())
    try:
        # Atomic: no .part survives, and the bytes are the bytes.
        f = root / "2007" / "SC001.pdf"
        SC.write_atomically(f, b"%PDF-1.4 real calendar")
        assert f.read_bytes() == b"%PDF-1.4 real calendar"
        assert not list(f.parent.glob("*.part")), "a part file was left behind"

        # The guards the download loop applies, asserted on the same inputs it
        # sees. A body that is not a PDF is never written under a .pdf name.
        assert b"%PDF-1.4 ...".startswith(b"%PDF")
        assert not b"<html>Web Page Blocked</html>".startswith(b"%PDF")
        blocked = b"<h1>Web Page Blocked</h1> Attack ID: 1234"
        assert refusal.classify(
            body=blocked[:4000].decode("utf-8", "replace")) == "refused"

        # One reading of an error, the same as every other fetcher's.
        import http.client
        import urllib.error
        for e, want in [
                (urllib.error.HTTPError("u", 403, "no", {}, None), "refused"),
                (urllib.error.HTTPError("u", 429, "slow", {}, None), "refused"),
                (urllib.error.HTTPError("u", 404, "nf", {}, None), "missing"),
                (http.client.RemoteDisconnected("closed"), "dropped"),
                (urllib.error.URLError(ConnectionResetError(10054, "reset")),
                 "dropped")]:
            assert refusal.classify(e) == want, (e, refusal.classify(e), want)

        # The pace is the lane's, not the 2.5 seconds this ran at when it met
        # the 403.
        src = _source(_paths.locate("fetch_senate_calendars.py"))
        m = re.search(r'"--delay".*?default=([\d.]+)', src, re.S)
        assert m and float(m.group(1)) >= 15, (
            "the Senate calendar delay is back under 15 seconds: " + str(m and m.group(1)))
        for needed in ("refusal.check(", "refusal.hold(", "refusal.classify(",
                       "write_atomically(", "--budget"):
            assert needed in src, f"fetch_senate_calendars lost {needed}"
        return "ok", ("atomic write, a non-PDF and the block page both refused, "
                      "403/429/reset read the one way, 20s pace")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "the calendar drain runs under the lane and leaves its lock alone",
       needs=("fetch_calendar_archive",))
def _calendar_drain(CA):
    """The 664 Senate calendars of 1998-2008 are drained by this script, in the lane.

    It kept archive/.lock by hand: exit if a lock was under an hour old, delete
    it if older, and unlink it unconditionally when done. The lane touches its
    lock every minute, so queued in the lane the drain exited 1 at once, which
    stops the whole queue; and had it run, it would have deleted the lane's
    lock on the way out.

    It also recognised a refusal by searching error text, so a 403 needed a
    second 403 to stop it, a reset at connect time was not a refusal at all,
    and the firewall's block page served with HTTP 200 would have been saved
    as a PDF and marked held for good.

    Driven through main() on fake answers, so refusal.check() and
    refusal.hold() are the ones the lane will meet. Nothing asks the network
    and archive/ is never opened.
    """
    import contextlib
    import http.client
    import io
    import time
    import types
    import urllib.error
    import refusal

    saved = (refusal.MARK, refusal.LOCK, CA.ROOT, CA.QUEUE, CA._get, CA.time,
             sys.argv)
    tmps = []
    PDF = b"%PDF-1.4 a calendar"

    def run(answers, n=2, lock=None):
        tmp = Path(tempfile.mkdtemp())
        tmps.append(tmp)
        CA.ROOT, CA.QUEUE = tmp, tmp / "queue.csv"
        refusal.MARK, refusal.LOCK = tmp / "refused.json", tmp / ".lock"
        rows = [{"chamber": "S", "kind": "calendar", "year": "2007",
                 "name": f"d{i}.pdf", "url": f"https://example.invalid/{i}",
                 "path": str(tmp / "out" / f"SC{i:03}.pdf"), "state": "wanted",
                 "attempts": "0", "error": "", "bytes": "", "fetched": ""}
                for i in range(n)]
        CA.save_queue(rows)
        if lock is not None:
            refusal.LOCK.write_text(str(lock), encoding="utf-8")
        answers, asked = iter(answers), []

        def fake(url, data=None, timeout=60):
            asked.append(url)
            a = next(answers)
            if isinstance(a, BaseException):
                raise a
            return a
        CA._get = fake
        sys.argv = ["fetch_calendar_archive.py", "--chamber", "S", "--kind",
                    "calendar", "--budget", str(n), "--delay", "1"]
        # stderr too: the foreign-lock case prints hold()'s real warning, and
        # "archive/.lock is held" in preflight's output would read as true.
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            try:
                rc = CA.main()
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 1
        return rc, CA.load_queue(), asked

    try:
        CA.time = types.SimpleNamespace(sleep=lambda s: None, time=time.time,
                                        strftime=time.strftime)
        # Under the lane: the lock names this process's parent.
        rc, rows, asked = run([PDF, PDF], lock=os.getppid())
        assert rc == 0, f"under the lane the drain exited {rc}"
        assert all(r["state"] == "held" for r in rows)
        assert refusal.LOCK.exists() and \
            refusal.LOCK.read_text().strip() == str(os.getppid()), \
            "the drain removed the lane's lock"
        # Somebody else's lock: no request, their lock untouched, status 3.
        rc, rows, asked = run([PDF], n=1, lock=99999999)
        assert rc == 3 and not asked, (rc, asked)
        assert refusal.LOCK.read_text().strip() == "99999999"
        # One 403 ends it, is recorded, and the status says so.
        rc, rows, asked = run([urllib.error.HTTPError("u", 403, "no", {}, None), PDF])
        assert rc == 2 and len(asked) == 1 and refusal.MARK.exists(), (rc, asked)
        # The block page with HTTP 200 is not a calendar.
        rc, rows, asked = run([b"<h1>Web Page Blocked</h1> Attack ID: 9", PDF])
        assert rc == 2 and not Path(rows[0]["path"]).exists(), rc
        # Two dropped connections, the first a reset at connect time.
        rc, rows, asked = run([urllib.error.URLError(ConnectionResetError(10054, "r")),
                               PDF, http.client.RemoteDisconnected("x"), PDF], n=4)
        assert rc == 2 and len(asked) == 3, (rc, asked)
        # A broken page twice stops the run non-zero, so the lane stops too.
        rc, rows, asked = run([b"<html>Server Error in '/'</html>"] * 2)
        assert rc == 1 and not refusal.MARK.exists(), rc
        src = _source(_paths.locate("fetch_calendar_archive.py"))
        assert "LOCK.unlink" not in src and "LOCK.write_text" not in src, \
            "fetch_calendar_archive manages archive/.lock by hand again"
        return "ok", ("runs under the lane's lock and leaves it; one 403, the "
                      "block page and two drops each stop it with status 2")
    finally:
        (refusal.MARK, refusal.LOCK, CA.ROOT, CA.QUEUE, CA._get, CA.time,
         sys.argv) = saved
        for t in tmps:
            shutil.rmtree(t, ignore_errors=True)


@check("build", "only /calendar is in the sitemap: every week's page is written noindex,follow and "
       "left out, an earlier build's week addresses are taken out, and /calendar is indexable",
       needs=("build_calendar", "check_site"))
def _calendar_weeks_noindex(BC, CS):
    """The person, 17 October 2026: one link to the calendar, /calendar,
    which opens on the current week, is the page search engines list, not
    each week. It replaced the rule of 16 October that listed a week once it
    held a meeting (the sitemap audit's third finding), so a week with a
    meeting and one without are both held here. Each week's page, the
    current week's dated copy included, carries noindex,follow and keeps its
    canonical; /calendar carries no robots line. A sitemap an earlier build
    wrote with week addresses in it keeps none after the merge, and
    check_site finds nothing on the calendar to call unlisted or contrary."""
    import contextlib
    import datetime as _dt
    import io
    import shell as S
    root = Path(tempfile.mkdtemp(prefix="gr-wknoindex-"))
    try:
        site, weeks, order, urls, _m = _cal_fixture(root)
        today = _dt.date(*CAL_TODAY)
        here = BC.week_key(today)
        base = "https://graniterecord.org"
        meets = {k: bool(BC.week_facts(k, weeks, today)["meets"]) for k in order}
        assert here in order and any(meets.values()) and not all(meets.values()), (
            f"the fixture lacks the current week, a week with a meeting or one without: {meets}")
        assert urls == [base + "/calendar"], f"the week pages listed {urls}, not /calendar alone"
        robots = re.compile(r'<meta name="robots" content="([^"]*)"')
        for k in order:
            page = site / "calendar" / f"{k}.html"
            assert page.is_file(), f"calendar/{k}.html was not written"
            head = page.read_text(encoding="utf-8").split("</head>")[0]
            said = robots.findall(head)
            assert said == ["noindex,follow"], f"calendar/{k}.html's robots lines are {said}"
            want = base + ("/calendar" if k == here else f"/calendar/{k}")
            assert f'<link rel="canonical" href="{want}">' in head, (
                f"calendar/{k}.html lost its canonical link to {want}")
        head = (site / "calendar.html").read_text(encoding="utf-8").split("</head>")[0]
        assert not robots.search(head) and f'<link rel="canonical" href="{base}/calendar">' in head, (
            "/calendar carries a robots line or no canonical of its own")
        # An earlier build's sitemap, which listed every week with a meeting.
        (site / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset>\n'
            + "".join(f"<url><loc>{base}/calendar/{k}</loc></url>\n" for k in order)
            + f"<url><loc>{base}/bills</loc></url>\n</urlset>\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            S.sitemap_merge(site, base, urls, "/calendar")
        locs = re.findall(r"<loc>([^<]*)</loc>", (site / "sitemap.xml").read_text(encoding="utf-8"))
        cal = sorted(u for u in locs if u.startswith(base + "/calendar"))
        assert cal == [base + "/calendar"] and base + "/bills" in locs, (
            f"after the merge the sitemap's calendar addresses are {cal}")
        errors, warnings = [], []
        with contextlib.redirect_stdout(io.StringIO()):
            CS.pages_listed(site, locs, base + "/", errors, warnings)
        assert not [e for e in errors if "calendar" in e], f"check_site refuses the calendar: {errors}"
        errors = []
        with contextlib.redirect_stdout(io.StringIO()):
            CS.pages_listed(site, locs + [f"{base}/calendar/{order[0]}"], base + "/", errors, warnings)
        assert any("ask not to be indexed" in e for e in errors), (
            f"check_site passes a sitemap listing a noindex week: {errors}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", (f"{len(order)} week pages noindex,follow ({sum(meets.values())} with a meeting), "
                  "none listed after the merge; /calendar listed and indexable")
