#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.5
"""
The General Court's week, one page per week.

    python3 build_calendar.py --site site --base https://graniterecord.org

WHY PAGES AND NOT A FETCH

The home page showed a fixed fortnight and there was no way to look at any
other week. Asked for on 18 September: "the calendar can be more of a week to
week thing where you can tap back and forth to view all the hearings and
sessions this week, next week, the previous week, etc."

The first attempt shipped a JSON file per week and a script to page through
them. That was the wrong shape twice over. The card a reader sees is drawn by
build_pages.cal_days, in Python, from the grouping meeting_key defines -- so a
script paging through JSON would have needed a SECOND renderer drawing
something that merely looked like the first, which is the mistake this
repository keeps a check under. And a site of files on a CDN can simply have
the weeks as files: the arrows become links, every week is an address a reader
can send to somebody, and the whole thing works with no script at all.

  site/calendar.html            the current week, which is what the tab opens
  site/calendar/2026-W38.html   every other week, one file each

WHAT IS ON A WEEK

Every proceedings.csv row with a date, read through proceedings.py like
everything else: committee hearings, executive and work sessions, and the
floor. Floor rows carry no committee -- which is exactly why sitting days were
nowhere on this site, since every listing is keyed on one -- so they are given
"House floor" or "Senate floor" and take an entry of their own beside the
committees that sat around them.

ONE ENTRY PER COMMITTEE PER DAY, which is meeting_key's rule and not this
file's: a committee that holds a hearing in the morning and an executive
session after it has had one working day. The card carries a chip per kind and
a divided colour bar, and its body lists the day's items in order with the time
and room each was set for.

WHAT IS NOT HERE. proceedings.csv is keyed on bills, so this shows bill
business only. The General Court's own schedule also lists study committees,
boards and commissions sitting with no bill before them -- the Assessing
Standards Board, the Mount Washington Commission -- and none of those appear.
"""

import argparse
import datetime
import json
from collections import OrderedDict, defaultdict
from pathlib import Path

import build_pages as BP
import proceedings
import shell as S
import structured as LD

# From 2025: the current term and the one before it. Everything earlier is in
# the record and reachable through a bill or a committee, but nobody pages a
# calendar back to 1998 and sixty-odd files is enough to carry the arrows.
FROM = "2025-01-01"

DAYNAME = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()
MONTH = ("January February March April May June July August September "
         "October November December").split()

FLOOR = {"H": "House floor", "S": "Senate floor"}


def week_key(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def monday(d):
    return d - datetime.timedelta(days=d.isoweekday() - 1)


def span_words(a, b):
    """21-27 September 2026, or 29 September - 5 October 2026."""
    if a.month == b.month:
        return f"{a.day}–{b.day} {MONTH[b.month - 1]} {b.year}"
    if a.year == b.year:
        return (f"{a.day} {MONTH[a.month - 1]} – "
                f"{b.day} {MONTH[b.month - 1]} {b.year}")
    return (f"{a.day} {MONTH[a.month - 1]} {a.year} – "
            f"{b.day} {MONTH[b.month - 1]} {b.year}")


def href_for(key, today):
    """Where a week lives. The current one is the tab's own page."""
    return "calendar.html" if key == week_key(today) else f"calendar/{key}.html"


def collect(site):
    """{week: {date: {meeting_key: [rows]}}}, plus the lookups a card needs."""
    titles, years = {}, {}
    idx = site / "idx"
    if idx.exists():
        for f in idx.glob("*.json"):
            try:
                rows = json.loads(f.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            for b in rows:
                if b.get("id"):
                    titles[b["id"]] = b.get("title") or ""
                    years[b["id"]] = b.get("year")

    code = {}
    cf = site / "committees.json"
    if cf.exists():
        try:
            for c in json.loads(cf.read_text(encoding="utf-8")):
                if c.get("name") and c.get("code"):
                    code[c["name"].strip().lower()] = c["code"]
        except (ValueError, OSError):
            pass

    weeks = defaultdict(lambda: defaultdict(OrderedDict))
    for r in proceedings.load():
        date = (r.get("date") or "")[:10]
        if date < FROM:
            continue
        try:
            d = datetime.date.fromisoformat(date)
        except ValueError:
            continue
        cmte = (r.get("committee") or "").strip()
        if not cmte:
            cmte = FLOOR.get((r.get("body") or "").strip().upper(), "")
            if not cmte:
                continue
        row = {"date": date, "time": (r.get("time") or "").strip(),
               "bill": r.get("bill") or "", "committee": cmte,
               "what": (r.get("kind") or "").strip(),
               "venue": (r.get("venue") or "").strip()}
        weeks[week_key(d)][date].setdefault(BP.meeting_key(row), []).append(row)
    return weeks, titles, years, code


def week_page(site, base, key, weeks, order, at, titles, years, code, urls, today):
    days_raw = weeks[key]
    dated = [d for d in days_raw if days_raw[d]]
    first = monday(datetime.date.fromisoformat(min(dated) if dated
                                               else min(days_raw)))
    last = first + datetime.timedelta(days=6)
    label = span_words(first, last)

    def when(d):
        x = datetime.date.fromisoformat(d)
        off = (x - today).days
        rel = ("today" if off == 0 else "tomorrow" if off == 1
               else f"in {off} days" if 0 < off < 14 else "")
        return f"{DAYNAME[x.weekday()]} {x.day} {MONTH[x.month - 1]}", rel

    meets, days = {}, OrderedDict()
    for date in sorted(dated):
        for k, rows in days_raw[date].items():
            meets[k] = rows
        days[date] = sorted(
            days_raw[date],
            key=lambda k: (min((r["time"] or "~") for r in days_raw[date][k]), k[1]))

    # level=2: the h1 of this page is the week itself, so a day is the
    # section under it. On the home page the days sit under "Coming up"
    # and stay h3.
    body, _missing = BP.cal_days(days, meets, titles, years, code, when, S.E,
                                 level=2)

    n = sum(len(v) for v in days.values())
    bills = len({(r["date"], r["bill"]) for rows in meets.values()
                 for r in rows if r["bill"]})

    nav = []
    if at > 0:
        nav.append(f'<a class="wkprev" href="{S.canon(href_for(order[at - 1], today))}">'
                   f'&lsaquo; The week before</a>')
    here = week_key(today)
    if key != here and here in order:
        nav.append(f'<a class="wkhere" href="{S.canon("calendar.html")}">This week</a>')
    if at < len(order) - 1:
        nav.append(f'<a class="wknext" href="{S.canon(href_for(order[at + 1], today))}">'
                   f'The week after &rsaquo;</a>')

    if n:
        lead = (f"{n} sitting{'' if n == 1 else 's'} on {len(days)} "
                f"day{'' if len(days) == 1 else 's'}, covering {bills:,} "
                f"bill{'' if bills == 1 else 's'}. A committee appears once a day, "
                "however many times it sat; open one for its items in order.")
    else:
        lead = ("Nothing sat this week. The General Court sits from January to "
                "June, and committees meet on bills from the autumn filing "
                "period onwards.")

    path = href_for(key, today)
    html = S.page(S.template(site), path=path, base=base,
                  title=f"The week of {label} | Granite Record",
                  description=("Every hearing, work session, executive session and "
                               f"floor sitting of the New Hampshire General Court, "
                               f"{label}."),
                  og_title=f"The week of {label}",
                  globals={"GR_STATIC": True}, noscript="",
                  skip_label="Skip to the week", sr_title="", og_type="website",
                  nav_current="calendar.html",
                  jsonld=LD.listing(f"The week of {label}",
                                    f"The General Court's business, {label}.",
                                    base, S.canon(path)))
    block = ('<div id="results"><div class="wkpage">'
             f'<h1>The week of {S.E(label)}</h1>'
             f'<p class="src">{lead}</p>'
             f'<nav class="wknav" aria-label="Other weeks">{"".join(nav)}</nav>'
             f'{body}'
             f'<nav class="wknav wkfoot" aria-label="Other weeks">{"".join(nav)}</nav>'
             "</div></div>")
    html = html.replace('<div id="results"></div>', block, 1)
    assert '<div class="wkpage">' in html, f"{path}: the template has no results slot"
    out = site / path.lstrip("/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    urls.append(base + S.canon(path))
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site, base = Path(a.site), a.base.rstrip("/")

    weeks, titles, years, code = collect(site)
    # SILENCE IS NOT SUCCESS: no weeks is a Calendar tab pointing at nothing,
    # and a build that said so only by printing a zero.
    assert weeks, f"no proceedings dated {FROM} or later; the calendar would be empty"

    today = datetime.date.today()
    here = week_key(today)
    if here not in weeks:
        # Out of session the current week holds nothing, and the tab still has
        # to open on it rather than on whenever the House last sat.
        weeks[here][today.isoformat()] = OrderedDict()
    order = sorted(weeks)

    urls, total = [], 0
    for i, key in enumerate(order):
        total += week_page(site, base, key, weeks, order, i,
                           titles, years, code, urls, today)

    sm = site / "sitemap.xml"
    if sm.exists():
        text = sm.read_text(encoding="utf-8")
        add = "".join(f"<url><loc>{S.E(u)}</loc></url>\n" for u in urls
                      if S.E(u) not in text)
        if add:
            sm.write_text(text.replace("</urlset>", add + "</urlset>"),
                          encoding="utf-8")
            print(f"  {len(add.splitlines())} added to sitemap.xml")

    print(f"  {len(order)} weeks -> calendar.html and calendar/ "
          f"({total:,} sittings; {here} is this week)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
