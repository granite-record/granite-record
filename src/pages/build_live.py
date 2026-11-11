#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.12
"""
Live Now's page and its schedule (the live layer's design, sections 1.2 and
1.4), written by the night beside the Calendar and from the Calendar's own
reading of the week:

    site/live/schedule.json   today and the next four weekdays, each meeting
                              with the Calendar's own card, byte for byte
    site/live.html            /live, with today's meetings already in it
    site/live.js, live.css    Live Now's script and its own rules (src/pages/)

    python3 src/pages/build_live.py --site site [--today 2027-01-07]

THE CARDS ARE THE CALENDAR'S. Each meeting is drawn by build_pages.cal_days
from build_calendar.collect's weeks -- the same grouping, the same renderer --
and its card is lifted out of that day's block, so /live and the Calendar
cannot disagree about a meeting. Nothing here draws a card of its own.

EACH ROW'S `match`: the stems a stream's title must begin with to be that
meeting's, by the Worker's own stem (live_gen.stem): the card's name ("house
finance"), the committee's name without its chamber ("finance"), and the
title stems its past recordings in collected/videos/ carried. A floor row
matches "house session" or "senate session" alone (live_gen.SESSION_TITLE).

THE PAGE NEVER WAITS. live.html is whole without script: today's cards, both
channels, and a <noscript> line. live.js adds what was live when the Worker
last looked. No request leaves the page at build time; nothing here asks the
network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

from terms import term_of_year as term_of  # noqa: E402,F401

import argparse
import csv
import datetime
import json
import re
import shutil

import build_calendar as BC
import build_date
import build_pages as BP
import live_gen as LG
import shell as S

AHEAD = 4                  # weekdays after today
# LINKED IS THE OWNER'S SWITCH (workers/live/SWITCH_ON.md, step 5): whether the
# home page's line and the header search's row lead to /live, and whether it
# is indexable. /live is built either way; while False it is noindex and out
# of the sitemap (10 November 2026), and a run takes out any line or row an
# earlier run put in.
LINKED = False
ROBOTS = '<meta name="robots" content="noindex">'
# The home page's slot, as build_pages.home_body leaves it (PATCHES.md 2),
# and the whole line this fills it with, matched together so a second run
# replaces the first's.
HOME_SLOT = '<p class="lv-home" hidden data-day=""></p>'
HOME_LINE = re.compile(r'<p class="lv-home"[^>]*>.*?</p>', re.S)
# A count dated for another day is taken off the line by the reader's own
# clock, so a missed night never shows yesterday's meetings as today's, and
# the home page asks nothing for it.
HOME_JS = ('<script>(function(){var p=document.currentScript.parentNode,'
           'd=new Intl.DateTimeFormat("en-CA",{timeZone:"America/New_York"}).format(new Date());'
           'if(p.getAttribute("data-day")!==d){var c=p.querySelector(".lv-count");if(c)c.remove();}})();'
           '</script>')
FIND_WORDS = "live stream streaming watch video hearing now today"
SCHEDULE = Path("live") / "schedule.json"
PAGE = "live.html"
ADDRESS = "/live.html"
CARD = re.compile(r'<details class="calmeet".*?</details>', re.S)
HREF = re.compile(r'href="/?(committee/[A-Za-z0-9]+)(?:\.html)?(?:#[^"]*)?"')


def nh_today():
    """New Hampshire's day: the stated one (build_date), or the clock's in
    US Eastern time, worked out from the rule rather than from zoneinfo,
    which needs the tzdata package on Windows. The machine's own date is not
    it: a nightly started after 00:00 UTC (19:00 EST) is a day ahead, and
    would write the next day's pages (the build review, 5 November 2026).
    Daylight time runs from 02:00 local on the second Sunday of March (07:00
    UTC) to 02:00 local on the first Sunday of November (06:00 UTC)."""
    when = build_date.stated()
    if when:
        return when.date()
    u = build_date.utcnow()

    def sunday(month, nth):
        d = datetime.date(u.year, month, 1)
        return d + datetime.timedelta(days=(6 - d.weekday()) % 7, weeks=nth - 1)
    utc = datetime.timezone.utc
    start = datetime.datetime.combine(sunday(3, 2), datetime.time(7), utc)
    end = datetime.datetime.combine(sunday(11, 1), datetime.time(6), utc)
    return (u + datetime.timedelta(hours=-4 if start <= u < end else -5)).date()


def weekdays(today, n):
    out, d = [today], today
    while len(out) < n + 1:
        d += datetime.timedelta(days=1)
        if d.weekday() < 5:
            out.append(d)
    return out


def past_stems(root=Path(".")):
    """{canonical committee: {title stems}} from every video index (proceedings.video_indexes)."""
    import build_manifest as BM
    import proceedings
    out = {}
    for p in proceedings.video_indexes(root):
        with p.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                c = (row.get("parsed_committee") or "").strip()
                if c and row.get("title"):
                    out.setdefault(BM.canon(c), set()).add(LG.stem(row["title"]))
    return out


def kind_of(key, rows):
    if key.name in BC.FLOOR.values():
        return "floor"
    if BP.is_conference(key):
        return "conference"
    if any(r.get("study") for r in rows):
        return "study"
    return "standing"


def match_of(key, rows, kind, history):
    chamber = "".join(BP.card_bodies(key, rows))
    if kind == "floor":
        return [{"H": "house session", "S": "senate session"}[c] for c in chamber if c in "HS"]
    if kind == "conference":
        return [LG.stem(f"committee of conference on {key.bill}")] if key.bill else []
    # The committee page's hook takes its stems from the same function
    # (live_hook.stems, design section 1.6), so /live and the page agree.
    import live_hook
    return live_hook.stems(key.chamber, key.name, history)


def schedule(site, today, weeks=None, history=None):
    """live/schedule.json's content."""
    if weeks is None:
        study_rows, _names, _fetched = BC.statstud()
        weeks, titles, years, code = BC.collect(site, study_rows)
    else:
        weeks, titles, years, code = weeks
    history = past_stems() if history is None else history
    days, nxt = {}, None
    for d in weekdays(today, AHEAD):
        iso = d.isoformat()
        day = (weeks.get(BC.week_key(d)) or {}).get(iso) or {}
        rows = []
        for key in BC.in_order(day):
            html, _missing = BP.cal_days({iso: [key]}, day, titles, years, code,
                                         lambda dd: BC.day_words(dd, today), S.E, level=3)
            card = CARD.search(html)
            meet = day[key]
            kind = kind_of(key, meet)
            chamber = "".join(BP.card_bodies(key, meet))
            if kind == "floor":
                # The day's dated address (the owner retired /session/<B>/today
                # on 30 October 2026): the record's page, or from live/session
                # the morning page. A later day's is not written yet.
                href = f"/session/{chamber[:1]}/{iso}" if d == today else None
            else:
                h = HREF.search(card.group(0) if card else "")
                href = f"/{h.group(1)}" if h else None
            rows.append({"id": f"{chamber}|{key.name}|{key.bill or ''}|{iso}", "chamber": chamber, "kind": kind,
                         "name": BP.card_name(key), "href": href, "card": card.group(0) if card else "",
                         "match": match_of(key, meet, kind, history)})
        days[iso] = rows
        if nxt is None and d > today and rows:
            nxt = {"date": iso, "name": rows[0]["name"]}
    return {"built": today.isoformat(), "tz": "America/New_York", "days": days, "next": nxt,
            "bills": bill_years(site, today)}


def bill_years(site, today):
    """{term: {year: [bill id]}} for the sitting term and the newest the site has.

    A BILL'S PAGE IS UNDER ITS OWN YEAR, the year it was introduced, not the
    year of the day it is voted on: a 2025 bill carried over and voted in 2026
    is /bill/2025/hb1, and CACR 13 of 2026 is /bill/2026/cacr13. So the page
    maps a roll call's bill to its page through the term's own index (the
    rows build_site_v2 writes to idx/<term>.json), never through the sitting's
    year; a bill the index does not hold is printed without a link, because a
    wrong link is worse than none (build_session_pages.bill_href).
    """
    site = Path(site)
    try:
        terms = json.loads((site / "meta.json").read_text(encoding="utf-8")).get("terms") or []
    except (OSError, ValueError, AttributeError):
        return {}
    terms = [t for t in terms if isinstance(t, str) and re.fullmatch(r"\d{4}-\d{4}", t)]
    out = {}
    for t in sorted({term_of(today.year), max(terms, default="")} & set(terms)):
        try:
            rows = json.loads((site / "idx" / f"{t}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        by = {}
        for r in rows:
            if isinstance(r, dict) and r.get("id") and r.get("year"):
                by.setdefault(str(r["year"]), []).append(str(r["id"]).upper())
        out[t] = {y: sorted(set(v)) for y, v in sorted(by.items())}
    return out


def page_body(sched, today):
    iso = today.isoformat()
    rows = sched["days"].get(iso) or []
    cards = "".join(f'<li class="lv-meet">{r["card"]}</li>' for r in rows if r["card"])
    channels = ('<p class="lv-channels">The streams are the General Court\'s own, on YouTube: '
                f'<a href="https://www.youtube.com/channel/{LG_CHANNEL("H")}/streams" rel="noopener">House</a> and '
                f'<a href="https://www.youtube.com/channel/{LG_CHANNEL("S")}/streams" rel="noopener">Senate</a>.</p>')
    return ('<div class="clist lvpage"><h1>Live Now</h1>'
            '<p id="live-now-status" class="lv-status"></p>'
            '<noscript><p class="lv-status">Live status needs this page\'s script; today\'s meetings are below.</p></noscript>'
            '<div id="live-now-streams" class="lv-streams"></div>'
            '<div id="live-now-votes" class="lv-sessions" hidden></div>'
            '<h2 id="live-now-scheduled-h" hidden>Scheduled to stream today</h2><ul id="live-now-scheduled" class="lv-list" hidden></ul>'
            '<h2 id="live-now-cal-h">On today\'s calendar</h2>'
            + (f'<ul id="live-now-today" class="lv-today">{cards}</ul>' if cards
               else '<p id="live-now-today" class="calempty">No meetings scheduled.</p>')
            + '<ul id="live-now-nostream" class="lv-list" hidden></ul>'
            '<h2 id="live-now-earlier-h" hidden>Earlier today</h2><ul id="live-now-earlier" class="lv-list" hidden></ul>'
            + channels
            + f'<script type="application/json" id="live-schedule">{json.dumps(sched, ensure_ascii=False).replace("</", "<\\/")}</script>'
            '<script src="live.js" defer></script></div>')


def styled(html):
    """The page with live.css linked after the site's own stylesheet."""
    return html.replace("</head>", '<link rel="stylesheet" href="live.css">\n</head>', 1)


def LG_CHANNEL(c):
    return LG.channels()[c]


def write(site, base, today):
    site = Path(site)
    sched = schedule(site, today)
    (site / SCHEDULE).parent.mkdir(parents=True, exist_ok=True)
    (site / SCHEDULE).write_text(json.dumps(sched, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    html = S.page(S.template(site), path=ADDRESS, base=base, title="Live Now | Granite Record",
                  description="Which House and Senate meetings are streaming now, with today's calendar.",
                  og_title="Live Now", globals={"GR_STATIC": True}, noscript="", skip_label="Skip to the list",
                  sr_title="", og_type="website", nav_current=ADDRESS.lstrip("/"), cite=False)
    html = html.replace('<div id="results"></div>', f'<div id="results">{page_body(sched, today)}</div>', 1)
    assert 'id="live-now-streams"' in html, f"{PAGE}: the template has no results slot"
    # NOT EASY TO STUMBLE ON BEFORE IT IS PUBLIC (the owner, 10 November 2026):
    # while LINKED is off the page asks not to be indexed, as the requests'
    # pages do, and is left out of the sitemap below.
    if not LINKED:
        html = html.replace('<link rel="canonical"', ROBOTS + '\n<link rel="canonical"', 1)
        assert ROBOTS in html, f"{PAGE}: the template has no canonical link to put noindex before"
    (site / PAGE).write_text(S.clean_links(styled(html)), encoding="utf-8")
    for f in ("live.js", "live.css"):
        shutil.copyfile(_paths.locate(f"src/pages/{f}"), site / f)
    # IN THE SITEMAP once the owner switches it on (LINKED), as every builder
    # lists its own pages (the release session, applying PATCHES.md 1, 2
    # November 2026): a page that asks to be indexed and is not listed stops
    # the night in check_site. Until then it is noindex and unlisted, and the
    # merge with no address takes out any entry an earlier run put in.
    S.sitemap_merge(site, base, [base.rstrip("/") + S.canon(ADDRESS)] if LINKED else [], "/live")
    link_home(site, sched, today)
    # THE HEADER SEARCH'S ROW (PATCHES.md 3, by the release session's plan of
    # 5 November 2026): build_indexes writes find.json before this step, when
    # /live is not on disk, so this step puts its own row in.
    S.find_merge(site, ["page", "Live Now",
                        "Which House and Senate meetings are streaming now, with today's calendar.",
                        S.canon(PAGE), FIND_WORDS] if LINKED else None, S.canon(PAGE))
    return sched


def home_line(sched, today):
    """The home page's Live Now line for `today` (design section 1.5): the
    link, and the day's meeting count from the schedule this step wrote;
    "Live Now" alone on a day with none."""
    n = len((sched.get("days") or {}).get(today.isoformat()) or [])
    count = (f'<span class="lv-count"> — {n} meeting{"s" if n != 1 else ""} today</span>'
             if n else "")
    return (f'<p class="lv-home" data-day="{today.isoformat()}"><a href="{S.canon(PAGE)}">Live Now</a>'
            f"{count}{HOME_JS}</p>")


def link_home(site, sched, today):
    """Fill the home page's slot (PATCHES.md 2): build_pages, which runs
    before the Calendar and so before this step, leaves it empty, and this
    puts the day's line in, or the empty slot back while LINKED is off.
    English home only. Returns whether index.html changed; False where it
    has no slot (a build without the patch)."""
    f = Path(site) / "index.html"
    if not f.exists():
        return False
    html = f.read_text(encoding="utf-8")
    if not HOME_LINE.search(html):
        return False
    new = HOME_LINE.sub(lambda _m: home_line(sched, today) if LINKED else HOME_SLOT, html, count=1)
    if new == html:
        return False
    f.write_text(new, encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    # dest="day": preflight's _build_date_stated reads any `.today` on the
    # build's path as asking the clock, and this one is the reader's.
    ap.add_argument("--today", dest="day", help="the day to write for, YYYY-MM-DD (default: the build's)")
    a = ap.parse_args()
    today = datetime.date.fromisoformat(a.day) if a.day else nh_today()
    sched = write(a.site, a.base, today)
    n = sum(len(v) for v in sched["days"].values())
    print(f"live: {PAGE} and {SCHEDULE.as_posix()}, {n} meetings over {len(sched['days'])} days "
          f"({len(sched['days'].get(today.isoformat()) or [])} today)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
