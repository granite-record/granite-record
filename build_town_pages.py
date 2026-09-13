#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.10
"""
A page per town and ward: everyone who represents the people who live there.

    python3 build_town_pages.py --site site --base https://graniterecord.org

Writes site/town/<slug>.html for each of the 320 town-wards, and adds them to
sitemap.xml.

WHY A PAGE AND NOT ONLY THE LOOKUP

The legislators page already answers "who are my representatives" in place:
pick a town, pick a ward, see the House and Senate seats. What it cannot do is
be linked to, shared, printed or found in a search -- and "who represents
Concord Ward 3" is exactly the question somebody types into a search engine.

It also stopped at the General Court. A resident has an executive councillor,
a member of the US House and two US senators as well, and the district
numbers for all of them were already on this disk in site/districts.json and
had never been shown.

WHAT IS DERIVED AND WHAT IS DECLARED

The districts are derived: districts/council.txt, congress.txt, senate.txt and
house.txt are the maps, and parse_districts.py turns them into a town-ward
lookup that includes the floterial districts the General Court's own file
leaves out.

The people are not. State legislators come from the roster the rest of the
site uses. The Governor, the five councillors, the two US representatives and
the two senators come from officials.json, which is edited by hand and which
no generator writes -- a name against an office is a claim about a real
person, and it should come from somebody who checked. Where a name is blank
the page names the office, gives the reader their district and links to the
official directory, which is correct and does not go stale.
"""

import argparse
import datetime as dt
import json
import re
from pathlib import Path

import shell as S

E = S.E


def slug(town, ward):
    s = re.sub(r"[^a-z0-9]+", "-", town.lower()).strip("-")
    return f"{s}-ward-{ward}" if ward and ward != "0" else s


def where(town, ward, wards):
    return f"{town}, Ward {ward}" if len(wards) > 1 else town


def chip(m):
    p = (m.get("party") or "X")[:1].upper()
    return f'<span class="mchip p-{E(p)}">{E(m.get("display_full") or m.get("name") or "")}</span>'


def off_row(who, how, seat=""):
    """One official: who they are on the left, how to reach them on the right.

    NOT a middle-dot string. These rows were built as `name &middot; email
    &middot; phone`, which DESIGN.md names as a default to avoid and which at
    360px wrapped three facts into a ribbon with no shape. The two halves are
    two cells now, and the stylesheet stacks them on a phone.
    """
    return ('<li class="offrow"><span class="offwho">' + who
            + (f'<span class="offseat">{seat}</span>' if seat else "")
            + '</span>'
            + ('<span class="offhow">' + "".join(how) + '</span>' if how else "")
            + '</li>')


def member_block(members, empty, seat=""):
    """The people in a seat, each with a way to reach them."""
    if not members:
        return f'<p class="note">{E(empty)}</p>'
    out = []
    for m in members:
        link = (f'<a href="/legislator/{E(m["slug"])}">'
                f'{E(m.get("display_full") or m.get("name"))}</a>'
                if m.get("slug") else E(m.get("display_full") or m.get("name")))
        p = (m.get("party") or "X")[:1].upper()
        how = []
        if m.get("email"):
            how.append(f'<a href="mailto:{E(m["email"])}">{E(m["email"])}</a>')
        if m.get("phone"):
            how.append(f'<span class="offtel">{E(m["phone"])}</span>')
        out.append(off_row(f'<span class="mchip p-{E(p)}">{link}</span>',
                           how, seat))
    return '<ul class="offlist">' + "".join(out) + "</ul>"


def tel(num):
    """A number that dials, on the device most readers are holding.

    These were plain text. A town clerk's number on a town page is the single
    most likely thing on this site to be tapped, and tapping it did nothing.
    """
    digits = re.sub(r"[^0-9]", "", num or "")
    if len(digits) == 10:
        digits = "1" + digits
    if len(digits) < 11:
        return f'<span class="offtel">{E(num)}</span>'
    return f'<a class="offtel" href="tel:+{digits}">{E(num)}</a>'


def weblink(url, label=None):
    """An outward link labelled with where it goes.

    "official page" told a reader nothing about which page; the host does, and
    it is what they would read off the address bar anyway. The arrow is this
    site's mark for a link that leaves it.
    """
    if not url:
        return ""
    host = re.sub(r"^https?://(?:www\.)?", "", url).rstrip("/").split("/")[0]
    return (f'<a href="{E(url)}" rel="noopener">{E(label or host)}'
            " &#8599;</a>")


MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def election_line(raw):
    """"11/03/2026-STATE GENERAL ELECTION" as a date in a heading.

    Returns the parenthetical for the section title: "November 3rd". The year
    is added only when it is not this one, because a reader looking at a page
    in 2026 does not need to be told that November is in 2026 and does need
    to be told when it is not.

    It says "Next Election" only while the date is ahead of the build. After
    that it says "Election on file": a heading still promising "next" in
    December would be wrong about the one thing the section is for.
    """
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*-\s*(.+)$", raw or "")
    if not m:
        return ""
    mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not 1 <= mm <= 12:
        return ""
    today = dt.date.today()
    when = f"{MONTHS[mm - 1]} {ordinal(dd)}"
    if yy != today.year:
        when += f", {yy}"
    ahead = (yy, mm, dd) >= (today.year, today.month, today.day)
    return f"{'Next Election' if ahead else 'Election on file'}: {when}"


def ward_picker(town, ward, wards):
    """The other wards of this town, behind the one you are in.

    Dover has six wards and eleven representatives; a resident of ward 2 is
    shown ward 2, which is the whole point of these pages. But the question
    after "who represents me" is often "and who represents the rest of the
    town", and the only way to ask it was to go back to the finder and pick
    Dover again.

    A disclosure with links inside, not a <select>: a select needs script to
    navigate and hands a screen reader options with no addresses, where these
    are plain links that work with the keyboard and with no JavaScript at
    all. The ward you are in is in the list and is not a link.
    """
    if len(wards) < 2:
        return ""
    rows = []
    # wards is the dict districts.json keys by ward, so the order is the
    # file's and Ward 10 sorts before Ward 2 as text. Numeric, the way the
    # loop that writes these pages already sorts them.
    for w in sorted(wards, key=lambda x: int(x) if str(x).isdigit() else 0):
        name = f"Ward {E(str(w))}"
        if str(w) == str(ward):
            rows.append(f'<span class="wpthis" aria-current="page">{name}'
                        f'</span>')
        else:
            rows.append(f'<a href="{E(slug(town, w))}.html">{name}</a>')
    return (f'<details class="wardpick"><summary><span class="wpnow">Ward '
            f'{E(str(ward))}</span><span class="wpcue">{len(wards)} wards in '
            f'{E(town)}</span><span class="chev">&#9656;</span></summary>'
            f'<nav class="wplist" aria-label="Wards of {E(town)}">'
            + "".join(rows) + '</nav></details>')


def office_block(title, holder, fallback_url, note=""):
    """One office this site does not track: what it is, who holds it if we
    were told, and the official page either way."""
    holder = holder or {}
    name = (holder.get("name") or "").strip()
    url = (holder.get("official_url") or "").strip() or fallback_url
    if name:
        p = (holder.get("party") or "X")[:1].upper()
        link = (f'<a href="{E(url)}" rel="noopener">{E(name)}</a>'
                if url else E(name))
        who = f'<span class="mchip p-{E(p)}">{link}</span>'
        how = []
        if holder.get("phone"):
            how.append(tel(holder["phone"]))
        if holder.get("phone_dc"):
            how.append(tel(holder["phone_dc"]) + " (Washington)")
        if holder.get("email"):
            how.append(f'<a href="mailto:{E(holder["email"])}">'
                       f'{E(holder["email"])}</a>')
        if url:
            how.append(weblink(url))
        row = off_row(who, how)
    else:
        # NOT AN APOLOGY AND NOT AN EMPTY SPACE. The district is the useful
        # half of the answer and it is known; the name is the half this site
        # was not told, and the office's own directory is where it is right.
        row = off_row(f'<a href="{E(url)}" rel="noopener">'
                      "who holds this seat, on the official directory</a>", [])
    # THE NOTE GOES UNDER THE NAME. Asked for, and it is the right way round:
    # the heading says which office, the row says who holds it, and the note
    # says what the office does. A reader who came to find out who their
    # councillor is should not have to read three sentences about the Council
    # to get to the name; a reader who wants to know what the Council does has
    # it immediately after.
    return ((f'<h3 class="offh">{E(title)}</h3>' if title else "")
            + '<ul class="offlist">' + row + "</ul>"
            + (f'<p class="note">{E(note)}</p>' if note else ""))


def state_house(dist, legs, body):
    """The representatives, after the senator: more seats, smaller district."""
    house = dist.get("house") or []
    for h in house:
        who = [m for m in legs
               if m.get("chamber") == "H"
               and (m.get("county") or "") == h.get("county")
               and str(m.get("district") or "") == str(h.get("district"))]
        seats = h.get("seats")
        head = (f'{E(h.get("county",""))} district {h.get("district")}'
                + (f' &middot; {seats} seat{"s" if seats and seats > 1 else ""}'
                   if seats else ""))
        body.append(f'<h3 class="offh">House &mdash; {head}</h3>')
        if h.get("floterial"):
            body.append('<p class="note">A floterial district overlays several '
                        'towns that each already elect their own '
                        'representative, and elects additional members across '
                        'the combined population. You are represented by '
                        'both.</p>')
        body.append(member_block(who, "No sitting member is matched to this "
                                      "district."))
    if not house:
        body.append('<p class="note">No House district is on file for this '
                    'ward.</p>')


def build(town, ward, wards, dist, legs, off, base, tmpl):
    """One town, highest office to lowest, with the vote at the top.

    THE ORDER IS THE POINT. This page used to open with the General Court,
    because the General Court is what the rest of the site is about -- and a
    reader who comes to a page called "who represents me" is not reading an
    index of this site's coverage. They are looking up their own government,
    and it runs Governor, Council, Congress, Senate, House, town hall. What
    they came for most often is simpler still and used to be two thirds of the
    way down: where do I vote, when, and who do I ring about it.
    """
    label = where(town, ward, wards)
    loc = (off.get("_local") or {}).get(slug(town, ward)) or {}
    town_off = (off.get("_offices") or {}).get(slug(town, "0")) or {}
    body = [f'<h1 class="offtitle">{E(label)}</h1>',
            ward_picker(town, ward, wards),
            '<p class="lead">Everyone elected to represent the people who live '
            'here, and how to reach them.</p>']

    # ---- the vote, first --------------------------------------------------
    if loc or town_off:
        rows = []
        if loc.get("polling_place"):
            hours = loc.get("state_hours") or ""
            rows.append(off_row(
                E(loc["polling_place"]),
                [f'<span class="offwhen">{E(hours)}</span>'] if hours else [],
                "Where you vote"))
        # A TOWN THAT VOTES IN MORE THAN ONE PLACE, BEHIND ONE LINE. Eight of
        # them -- Berlin, Derry, Farmington, Goffstown, Hudson, Merrimack,
        # Salem and Walpole -- are one town in the district file this site's
        # pages are named after and several voting wards on the Secretary of
        # State's list, so there is no ward for this page to be about and no
        # way to ask the reader which is theirs.
        #
        # Four addresses in a row was the first answer and it is three
        # addresses too many: a reader wants one. So the number is stated and
        # the list is behind it, which is the same shape as the chapter list
        # on a bill and the filter panel on a phone -- the answer first, the
        # rest on request.
        by_ward = loc.get("polling_by_ward") or []
        site_url = town_off.get("website") or loc.get("website") or ""
        if site_url:
            rows.append(off_row(weblink(site_url), [], "Town website"))
        if loc.get("clerk"):
            how = []
            if loc.get("phone"):
                how.append(tel(loc["phone"]))
            if loc.get("email"):
                how.append(f'<a href="mailto:{E(loc["email"])}">'
                           f'{E(loc["email"])}</a>')
            rows.append(off_row(
                f'<span class="mchip">{E(loc["clerk"])}</span>', how,
                "Town or city clerk"))
        if by_ward:
            inner = []
            for w in by_ward:
                hours = w.get("state_hours") or ""
                inner.append(off_row(
                    E(w.get("polling_place") or ""),
                    [f'<span class="offwhen">{E(hours)}</span>']
                    if hours else [],
                    f'Ward {E(w.get("ward"))}'))
            rows.append(
                '<li class="offrow offwards"><details class="wards">'
                f'<summary>{E(town)} votes in {len(by_ward)} places, by '
                'ward &mdash; show them</summary>'
                '<ul class="offlist">' + "".join(inner) + "</ul></details></li>")
        if rows:
            when = election_line(loc.get("election", ""))
            body.append('<h2 class="offsec">How to Vote'
                        + (f' <span class="offwhen">({E(when)})</span>'
                           if when else "")
                        + "</h2>")
            body.append('<ul class="offlist">' + "".join(rows) + "</ul>")
            if not loc.get("polling_place") and not loc.get("polling_by_ward"):
                # The Secretary of State's own list is blank here, as it is
                # for 109 of its 331 rows.
                body.append('<p class="note">The Secretary of State\'s list '
                            'has no polling place recorded for here. The town '
                            'clerk above is who to ask.</p>')

    # ---- the state executive ----------------------------------------------
    body.append('<h2 class="offsec">Executive Branch</h2>')
    g = off.get("governor", {})
    body.append(office_block("Governor of New Hampshire", g,
                             g.get("official_url", ""),
                             " ".join(g.get("about") or [])))
    cd = dist.get("council")
    if cd:
        c = off.get("council", {})
        body.append(office_block(
            f"Executive Council \u2014 district {cd}",
            (c.get("districts") or {}).get(str(cd)),
            c.get("official_url", ""),
            " ".join(c.get("about") or [])))

    # ---- the federal delegation -------------------------------------------
    body.append('<h2 class="offsec">Federal Delegation</h2>')
    us = off.get("us_senate", {})
    body.append('<h3 class="offh">US Senate</h3>')
    seats = us.get("seats") or []
    if seats:
        # No per-seat heading. Both are elected by the whole state and both
        # represent this town, so the names are what tells them apart --
        # senate.gov lists them in seniority order and calling one "senior"
        # here would be reading more into that order than it states.
        rows = [office_block("", seat, us.get("official_url", ""))
                for seat in seats]
        body.append(re.sub(r"</ul><ul class=\"offlist\">", "", "".join(rows)))
    else:
        body.append(office_block("", {}, us.get("official_url", "")))
    # Under the names, the same way round as every other office here.
    if us.get("about"):
        body.append(f'<p class="note">{E(" ".join(us["about"]))}</p>')
    gd = dist.get("congress")
    if gd:
        u = off.get("us_house", {})
        body.append(office_block(
            f"US House \u2014 New Hampshire district {gd}",
            (u.get("districts") or {}).get(str(gd)),
            u.get("official_url", ""),
            " ".join(u.get("about") or [])))

    # ---- the General Court, senator before representative -----------------
    body.append('<h2 class="offsec">Legislative Branch</h2>')
    sd = dist.get("senate")
    if sd:
        who = [m for m in legs if m.get("chamber") == "S"
               and str(m.get("district") or "") == str(sd)]
        body.append(f'<h3 class="offh">Senate &mdash; district {sd}</h3>')
        body.append(member_block(who, "No sitting senator is matched to this "
                                      "district."))
    state_house(dist, legs, body)

    # ---- the town's own offices -------------------------------------------
    # NHDOT's "City and Town Officials of the State of New Hampshire",
    # September 2025, parsed by parse_officials.py: 1,414 named offices across
    # all 234 municipalities the directory covers. A city's wards share one
    # selectboard, so these are looked up by the town's slug and not the
    # ward's -- a ward elects a councillor, and the town is what the board
    # governs.
    if town_off.get("officials"):
        body.append(f'<h2 class="offsec">{E(town)} Officials</h2>')
        rows = []
        for o in town_off["officials"]:
            how = []
            if o.get("phone"):
                how.append(tel(o["phone"]))
            if o.get("email"):
                how.append(f'<a href="mailto:{E(o["email"])}">'
                           f'{E(o["email"])}</a>')
            rows.append(off_row(f'<span class="mchip">{E(o["name"])}</span>',
                                how, E(o.get("position") or "")))
        body.append('<ul class="offlist">' + "".join(rows) + "</ul>")
        how = []
        if town_off.get("phone"):
            how.append(tel(town_off["phone"]))
        if town_off.get("email"):
            how.append(f'<a href="mailto:{E(town_off["email"])}">'
                       f'{E(town_off["email"])}</a>')
        if town_off.get("website"):
            how.append(weblink(town_off["website"]))
        if town_off.get("mailing") or how:
            body.append('<ul class="offlist">'
                        + off_row(E(town_off.get("mailing") or town),
                                  how, "Town offices")
                        + "</ul>")
        body.append('<p class="note">Source: DoT directory of city and town '
                    'officials lists, as of September 2025. Check official '
                    'town website for up-to-date information.</p>')

    body.append('<p class="srcs">Source: NH General Court, Secretary of '
                'State, DoT Municipal Directory</p>')

    path = f"/town/{slug(town, ward)}.html"
    desc = (f"Who represents {label}: state representatives, state senator, "
            "executive councillor, US representative, US senators and the "
            "governor, with how to reach each of them.")
    p = S.page(tmpl, path=path, base=base,
               title=S.title_of(f"Who represents {label}"),
               og_title=f"Who represents {label}",
               description=desc, globals={"GR_STATIC": True},
               noscript="", skip_label="Skip to the page", sr_title="",
               nav_current="legislators.html")
    return p.replace('<div id="results"></div>',
                     '<div id="results"><div class="officials">'
                     + "".join(body) + "</div></div>", 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--officials", default="officials.json")
    ap.add_argument("--local", default="town_clerks.json",
                    help="clerks and polling places, if parsed")
    ap.add_argument("--offices", default="town_officials.json",
                    help="the town's own officials, if parsed")
    a = ap.parse_args()

    site = Path(a.site)
    districts = json.loads((site / "districts.json").read_text(encoding="utf-8"))
    legs = json.loads((site / "legislators.json").read_text(encoding="utf-8"))
    if isinstance(legs, dict):
        legs = list(legs.values())
    off = json.loads(Path(a.officials).read_text(encoding="utf-8"))
    # The clerk and the polling place, if they have been fetched. One file for
    # all 331 towns and wards, keyed by the same slug the pages are named
    # after. Absent is the normal state until somebody runs the fetch, and
    # absent means the section is not drawn rather than drawn empty.
    local = Path(a.local)
    if local.exists():
        try:
            off["_local"] = json.loads(local.read_text(encoding="utf-8"))
            print(f"  local offices: {len(off['_local'])} towns from {local}")
        except ValueError as e:
            print(f"  local offices: {local} did not parse ({e}); skipped")
    else:
        print(f"  local offices: {local} is not on disk, so the clerk and "
              "polling place section is not drawn")
    # The same contract as --local: absent means the section is not drawn
    # rather than drawn empty.
    offices = Path(a.offices)
    if offices.exists():
        try:
            off["_offices"] = json.loads(offices.read_text(encoding="utf-8"))
            n = sum(len(v.get("officials") or [])
                    for v in off["_offices"].values())
            print(f"  town officials: {len(off['_offices'])} municipalities, "
                  f"{n} named offices from {offices}")
        except ValueError as e:
            print(f"  town officials: {offices} did not parse ({e}); skipped")
    else:
        print(f"  town officials: {offices} is not on disk, so the "
              "\"who runs\" section is not drawn")
    tmpl = S.template(site)

    out = site / "town"
    out.mkdir(parents=True, exist_ok=True)
    urls, n = [], 0
    for town in sorted(districts):
        wards = districts[town]
        for ward in sorted(wards, key=lambda w: int(w) if w.isdigit() else 0):
            page = build(town, ward, wards, wards[ward], legs, off,
                         a.base, tmpl)
            (out / f"{slug(town, ward)}.html").write_text(page,
                                                          encoding="utf-8")
            urls.append(a.base + S.canon(f"/town/{slug(town, ward)}.html"))
            n += 1

    # Silence is not success.
    if not n:
        raise SystemExit("No town pages were written. Is site/districts.json "
                         "built? parse_districts.py writes it.")

    named = sum(1 for k, v in off.items()
                if isinstance(v, dict) and (v.get("name") or "").strip())
    for k in ("council", "us_house"):
        named += sum(1 for d in (off.get(k, {}).get("districts") or {}).values()
                     if (d.get("name") or "").strip())
    named += sum(1 for s in (off.get("us_senate", {}).get("seats") or [])
                 if (s.get("name") or "").strip())
    print(f"{n:,} town-ward pages -> {out}/")
    print(f"  {named} of 10 other offices name who holds them; the rest link "
          "to the official directory")

    # Appended rather than replaced: rewriting it here would drop every other
    # URL on the site.
    sm = site / "sitemap.xml"
    if sm.exists():
        text = sm.read_text(encoding="utf-8")
        add = "".join(f"<url><loc>{E(u)}</loc></url>\n" for u in urls
                      if E(u) not in text)
        if add:
            sm.write_text(text.replace("</urlset>", add + "</urlset>"),
                          encoding="utf-8")
            print(f"  {len(add.splitlines())} added to sitemap.xml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
