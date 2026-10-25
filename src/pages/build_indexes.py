#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-13.23
"""
The whole record as plain lists: every bill of every term, every sitting
legislator, every town -- each a link a person or a crawler can follow.

    python3 src/pages/build_indexes.py --site site --base https://graniterecord.org

WHY

The site has 33,683 bill pages, 406 legislator pages and 320 town pages, and
almost nothing linked to them without JavaScript:

  - the bill list is drawn by app.js from idx/<term>.json, so bills.html ships
    an empty <div id="results">. A bill page was reachable from the sitemap,
    four homepage links, and nothing else. Bill pages link no other bill.
  - /legislators draws its results after a reader types. The page held zero
    links to a legislator's page.
  - the town pages had no index at all, and no static inbound link.

A search engine finds a page by following links to it; a sitemap tells it the
page exists and not that anything thinks it matters. A reader with JavaScript
off, or a screen reader user who wants a list rather than a search box, had no
way to walk the record either. So:

    /directory                    the hub: every list below
    /directory/bills-2025-2026    one per term, every bill with its title and status
    /directory/legislators        every sitting member, by chamber, surname first
    /directory/towns              every town and ward page, by county

Built from the same files the pages are (idx/<term>.json, legislators.json,
towns.json, the town pages on disk), through shell.page(), so each has the
site's own head, title, canonical address and chrome, and nothing drawn by
script. Appended to sitemap.xml the way every other builder does.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import html as _h
import json
import re
from collections import defaultdict
from urllib.parse import quote_plus

import bill_order as BO
import guides as G
import officials_tabs as OT
import shell as S
import structured as LD
from build_members_elect import read_officials

# THE KINDS RUN IN THE SITE'S ORDER, bill_order's: House bills, House
# resolutions, House concurrent resolutions, CACRs, then the Senate's, then the
# joint resolutions, and any other kind after those, alphabetically. This page
# kept an order of its own (HB, SB, CACR, HCR, ...) after bills.html, the
# committee and member lists and the downloads had all come to share one, so a
# reader moving from the bill search to the directory found the Senate's bills
# in second place here and fifth everywhere else. Asked for on 24 September.
KIND_NAME = {"HB": "House bills", "SB": "Senate bills", "CACR": "Constitutional amendments",
             "HCR": "House concurrent resolutions", "SCR": "Senate concurrent resolutions",
             "HJR": "House joint resolutions", "SJR": "Senate joint resolutions",
             "HR": "House resolutions", "SR": "Senate resolutions", "PET": "Petitions",
             "LSR": "Requests"}


def kind_of(bid):
    m = re.match(r"([A-Z]+)(\d+)", bid)
    return (m.group(1), int(m.group(2))) if m else (bid, 0)


def write(site, base, path, title, description, heading, lead, body, urls, nav="directory.html"):
    html = S.page(S.template(site), path=path, base=base, title=title, description=description,
                  og_title=heading, globals={"GR_STATIC": True}, noscript="",
                  skip_label="Skip to the list", sr_title="", og_type="website",
                  # The template marks Bills as the page you are on. A list of bills
                  # is under Bills and a list of legislators under Legislators; the
                  # hub and the towns are under neither, and name themselves.
                  nav_current=nav,
                  jsonld=LD.listing(heading, description, base, S.canon(path)))
    html = html.replace('<div id="results"></div>',
                        f'<div id="results"><div class="clist dirlist"><h1>{S.E(heading)}</h1>'
                        f'<p class="src">{lead}</p>{body}</div></div>', 1)
    assert '<div class="clist dirlist">' in html, f"{path}: the template has no results slot"
    out = site / path.lstrip("/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(S.clean_links(html), encoding="utf-8")
    urls.append(base + S.canon(path))


def requests_label(site):
    """{term: label} for the term that holds requests and not bills.

    build_lsrs.py writes idx/2027-requests.json beside the terms and names it
    in meta.json's "requests": the term's key and "2027 Bill Requests", which
    is what the bill search's term picker calls it. Read from there, so the
    lists and the picker call it one thing.
    """
    mj = site / "meta.json"
    try:
        req = json.loads(mj.read_text(encoding="utf-8")).get("requests") or {}
    except (ValueError, OSError):
        req = {}
    return {req["term"]: req.get("label") or req["term"]} if req.get("term") else {}


def bills_page(site, base, term, rows, urls, label=""):
    """One term's list. `label` is given for the term of requests.

    A REQUEST HAS NO PAGE, SO ITS NUMBER IS NOT A LINK. Every row was written
    as a link to bill/<year>/<id>, and build_bill_pages.py builds no page for
    a request: the 241 links on /directory/bills-2027-requests all answered
    404 (the audit of 2 October 2026). The bill list has always known it --
    an LSR's card there carries no link to a page of its own. A row marked
    `lsr` is its number as text; the list says where the requests can be
    searched, which is the one page that holds them.
    """
    groups = defaultdict(list)
    for r in rows:
        groups[kind_of(r["id"])[0]].append(r)
    order = ([k for k in BO.KIND_ORDER if k in groups]
             + sorted(k for k in groups if k not in BO.KIND_ORDER))
    body = []
    for k in order:
        items = sorted(groups[k], key=lambda r: BO.bill_key(r["id"]))
        body.append(f'<h2 id="{S.E(k.lower())}">{S.E(KIND_NAME.get(k, k))} '
                    f'<span class="dircount">{len(items):,}</span></h2><ul class="dirbills">')
        for r in items:
            num = S.E(r.get("n") or r["id"])
            if not r.get("lsr"):
                href = S.canon(f"bill/{r.get('year')}/{r['id'].lower()}.html")
                num = f'<a href="{S.E(href)}">{num}</a>'
            # THE CHIP'S WORD, as the bill list's card says it
            # (build_site_v2.chip_word): Died, not how it died, which is on
            # the bill's own page. A request has no chip, and its status --
            # "Filed as a request" -- is the word.
            word = r.get("chip") or r.get("status") or ""
            status = f' <span class="dirstatus">{S.E(word)}</span>' if word else ""
            body.append(f'<li>{num} '
                        f'{S.E((r.get("title") or "").strip())}{status}</li>')
        body.append("</ul>")
    jump = " &middot; ".join(f'<a href="{S.canon("/directory/bills-" + term + ".html")}#{k.lower()}">'
                             f'{S.E(KIND_NAME.get(k, k))}</a>' for k in order)
    if label:
        write(site, base, f"/directory/bills-{term}.html",
              f"{label} | Granite Record",
              f"All {len(rows):,} requests for bills filed so far for the next session of "
              "the New Hampshire General Court, by request number, with each one's title.",
              label,
              f"{len(rows):,} requests, by number. A request has no page of its own "
              "until it is filed as a bill; "
              f'<a href="{S.E(S.canon("bills.html") + "?term=" + quote_plus(term))}">'
              "the bill search lists them</a> with their sponsors.",
              "".join(body), urls, nav="bills.html")
        return len(rows)
    write(site, base, f"/directory/bills-{term}.html",
          f"Every bill of the {term} term | Granite Record",
          f"All {len(rows):,} bills and resolutions of the {term} New Hampshire General Court "
          "term, by number, with each one's title and where it ended.",
          f"Every bill of {term}",
          f"{len(rows):,} bills and resolutions, by number. {jump}",
          "".join(body), urls, nav="bills.html")
    return len(rows)


def legislators_page(site, base, legs, urls, former=0):
    by = {"H": [], "S": []}
    for m in legs:
        by.get(m.get("chamber"), by["H"]).append(m)
    body = []
    for ch, name in (("S", "Senate"), ("H", "House of Representatives")):
        people = sorted(by[ch], key=lambda m: (m.get("name") or "").lower())   # "Abbas, Daryl"
        body.append(f'<h2 id="{ch.lower()}">{name} <span class="dircount">{len(people)}</span></h2>'
                    '<ul class="dirpeople">')
        for m in people:
            href = S.canon(f"legislator/{m['slug']}.html")
            where = (f"District {m.get('district')}" if ch == "S"
                     else f"{m.get('county') or ''} {m.get('district') or ''}".strip())
            body.append(f'<li><a href="{S.E(href)}">{S.E(m.get("display_plain") or m.get("label") or m.get("name"))}</a>'
                        f' <span class="dirstatus">{S.E(m.get("party") or "")}, {S.E(where)}</span></li>')
        body.append("</ul>")
    write(site, base, "/directory/legislators.html",
          "Every sitting legislator | Granite Record",
          f"All {len(legs)} sitting members of the New Hampshire House and Senate, with party "
          "and district, each linked to their votes and sponsored bills.",
          "Every sitting legislator",
          f"{len(by['S'])} senators and {len(by['H'])} representatives, by surname. "
          f'<a href="{S.canon("officials.html")}">Search by town or name</a> instead'
          + (f', or see <a href="{S.canon("directory/former-legislators.html")}">former '
             "legislators</a>." if former else "."),
          "".join(body), urls, nav="officials.html")
    return len(legs)


def former_page(site, base, urls):
    """Every former member with a page of their own (the SEO review of 12
    October 2026: 77 of their pages had no link to them from anywhere, and 83
    more one). Named as the record names them -- "Former" is said on a
    member's own page and in search results and nowhere else -- under a
    heading that says what the list is; each with their chamber, seat and the
    years the record holds them."""
    fm = site / "former.json"
    people = [m for m in (json.loads(fm.read_text(encoding="utf-8")) if fm.exists() else [])
              if m.get("slug") and (site / "legislator" / f"{m['slug']}.html").exists()]
    if not people:
        return 0
    by = {"H": [], "S": []}
    for m in people:
        by.get(m.get("chamber"), by["H"]).append(m)
    body = []
    for ch, name in (("S", "Senate"), ("H", "House of Representatives")):
        rows = sorted(by[ch], key=lambda m: (m.get("name") or "").lower())
        if not rows:
            continue
        body.append(f'<h2 id="{ch.lower()}">{name} <span class="dircount">{len(rows)}</span></h2>'
                    '<ul class="dirpeople">')
        for m in rows:
            terms = (m.get("served") or {}).get("terms") or []
            span = f"{terms[0].split('-')[0]}\u2013{terms[-1].split('-')[1]}" if terms else ""
            seat = m.get("district_label") or ""
            body.append(f'<li><a href="{S.E(S.canon("legislator/" + m["slug"] + ".html"))}">'
                        f'{S.E(m.get("display_plain") or m.get("name"))}</a> <span class="dirstatus">'
                        f'{S.E(", ".join(x for x in (m.get("party") or "", seat, span) if x))}</span></li>')
        body.append("</ul>")
    write(site, base, "/directory/former-legislators.html",
          "Former legislators | Granite Record",
          f"{len(people):,} former members of the New Hampshire House and Senate on record since "
          "1999, with party, seat and years, each linked to their votes and sponsored bills.",
          "Former legislators",
          f"{len(by['S'])} former senators and {len(by['H']):,} former representatives with a "
          "recorded roll call vote since 1999, by surname.",
          "".join(body), urls, nav="officials.html")
    return len(people)


def towns_page(site, base, towns, urls):
    pages = {p.stem for p in (site / "town").glob("*.html")}
    by_county = defaultdict(list)
    seen = set()
    for town, seats in sorted(towns.items()):
        county = (seats[0].get("county") if seats else "") or "Other"
        wards = sorted({s.get("ward") or "0" for s in seats}, key=lambda w: int(w) if w.isdigit() else 0)
        base_slug = re.sub(r"[^a-z0-9]+", "-", town.lower()).strip("-")
        links = []
        for w in wards:
            slug = f"{base_slug}-ward-{w}" if w and w != "0" else base_slug
            if slug in pages and slug not in seen:
                seen.add(slug)
                label = town if w in ("", "0") else f"Ward {w}"
                links.append(f'<a href="{S.E(S.canon("town/" + slug + ".html"))}">{S.E(label)}</a>')
        if links:
            by_county[county].append(links[0] if len(links) == 1 else
                                     f'{S.E(town)}: ' + ", ".join(links))
    body = []
    for county in sorted(by_county):
        body.append(f'<h2>{S.E(county)} County <span class="dircount">{len(by_county[county])}</span></h2>'
                    '<ul class="dirtowns">' + "".join(f"<li>{x}</li>" for x in by_county[county]) + "</ul>")
    missing = sorted(pages - seen)
    if missing:
        body.append('<h2>Other</h2><ul class="dirtowns">' + "".join(
            f'<li><a href="{S.E(S.canon("town/" + s + ".html"))}">{S.E(s.replace("-", " ").title())}</a></li>'
            for s in missing) + "</ul>")
    write(site, base, "/directory/towns.html",
          "Every town and ward | Granite Record",
          "Every New Hampshire town, city and ward, by county, each linked to the "
          "legislators who represent it.",
          "Every town and ward",
          f"{len(pages)} pages, by county: who represents each place, with contact details.",
          "".join(body), urls)
    return len(pages)


def sessions_pages(site, base, urls):
    """/directory/sessions-house and /directory/sessions-senate: every day a
    chamber sat, by year, each linked to its page. Returns {body: how many}.

    A PAST SITTING COULD BE REACHED ONLY FROM THE SITTING NEXT TO IT. Of the
    791 House and 772 Senate days with a page, 32 and 30 had a link from
    anything but another sitting, all from a 2025-2026 week of the Calendar
    (the audit of 2 October 2026, B3): a day in 2019 was hundreds of presses
    of "The sitting before" away, the header search does not hold them, and
    this directory listed bills, members, towns and committees. The sitemap
    named all 1,563, so a search engine found them and a reader did not.

    THE DAYS build_session_pages.py WRITES, asked of it (sittings) and not
    read off the disk: that step runs after this one, so on a machine that
    starts empty there is nothing there yet. Newest first, as the terms are.
    What each day's line says is the sitting page's own opening count.

    No narratives.json, no lists, and it says so: the sitting pages are built
    from that file and their step stops without it, so a list here would
    link pages nothing is going to write.
    """
    import session_days
    if not Path(session_days.NARRATIVES).exists():
        print(f"  no {session_days.NARRATIVES} here, so no lists of session "
              "days: there are no session day pages to list")
        return {}
    import build_session_pages as BSP
    days = session_days.load()
    built, _later = BSP.sittings(days)
    out = {}
    for ch in ("H", "S"):
        mine = [k for k in built if k[0] == ch]
        if not mine:
            continue
        name = BSP.CHAMBER[ch]
        by_year = defaultdict(list)
        for k in mine:
            by_year[k[1][:4]].append(k)
        years = sorted(by_year, reverse=True)
        body = []
        for y in years:
            body.append(f'<h2 id="y{y}">{y} <span class="dircount">{len(by_year[y])}</span></h2>'
                        '<ul class="dirdays">')
            for k in sorted(by_year[y], reverse=True):
                day = days[k]
                n, b = len(day.items), len(day.bills)
                body.append(
                    f'<li><a href="{S.E(S.canon(f"session/{ch}/{k[1]}.html"))}">'
                    f'{S.E(BSP.words(k[1]))}</a> <span class="dirstatus">'
                    f'{n:,} action{"" if n == 1 else "s"} on {b:,} bill{"" if b == 1 else "s"}'
                    '</span></li>')
            body.append("</ul>")
        path = "/" + BSP.DAYS_LIST[ch]
        jump = " &middot; ".join(f'<a href="{S.canon(path)}#y{y}">{y}</a>' for y in years)
        write(site, base, path,
              f"Every {name} session day | Granite Record",
              f"All {len(mine):,} days the New Hampshire {name} sat on the record, "
              f"{years[-1]} to {years[0]}, each linked to what it did that day.",
              f"Every {name} session day",
              f"{len(mine):,} days the {name} sat, newest first, each with what it did "
              f"to bills that day. {jump}",
              "".join(body), urls, nav="calendar.html")
        out[ch] = len(mine)
    return out


# THE OFFICIALS PAGE'S TABS IN THE SEARCH, ONE ROW EACH (the audit of 25
# October 2026, M3: the Governor, the US Senators and the councilors were not
# found). Each is its tab's name, a line saying what it holds, its address on
# /officials, and the offices it draws as the words it is asked for by; the
# names of the people on it are added from the file the page is built from
# (officials_rows). Offices and names only: a department's name would put the
# Executive Branch above the bills for "health" or "education", and the bare
# "House" and "Senate" the federal tab above every search for the state's.
OFFICIAL_TABS = (
    ("federal", "Federal Delegation", "Officials · New Hampshire's US Senators and Representatives",
     "Congress Congressional US Senator US Senators US Representative US Representatives"),
    ("executive", "Executive Branch", "Officials · The Governor, the Executive Council and the "
     "department heads",
     "Governor Executive Council Councilor Councilors Councillor Secretary of State "
     "State Treasurer Attorney General Department Heads Commissioner Commissioners"),
    ("judicial", "Judicial Branch", "Officials · The justices of the Supreme Court and the "
     "Superior Court", "Supreme Court Superior Court Circuit Court Courts Justice Justices "
     "Judge Judges"),
    ("counties", "County Officials", "Officials · Each county's commissioners, sheriff, county "
     "attorney, treasurer and registers",
     "County Commissioner County Commissioners Sheriff Sheriffs County Attorney Treasurer "
     "Register of Deeds Register of Probate"),
)


def officials_rows(off):
    """find.json's four rows for the Officials page's tabs of officials, from
    `off`, corrections/officials.json as build_members_elect.read_officials
    gives it on the build's day -- the people each tab draws (officials_tabs)
    -- with each person's name among its words, so "ayotte" finds the
    Executive Branch and "shaheen" the Federal Delegation. A tab the file
    names nobody on is left out, as the page leaves out its panel."""
    def at(d, *keys):
        """d[k1][k2]..., {} where any step is missing."""
        for k in keys:
            d = d.get(k) if isinstance(d, dict) else None
        return d or {}

    def names(recs):
        return [str(r.get("name") or "").strip() for r in recs
                if isinstance(r, dict) and str(r.get("name") or "").strip()]
    people = {
        "federal": names(list(at(off, "us_senate").get("seats") or [])
                         + list(at(off, "us_house", "districts").values())),
        "executive": names([off.get("governor")] + list(at(off, "council", "districts").values())
                           + [off.get(k) for k in ("secretary_of_state", "treasurer",
                                                   "attorney_general")]
                           + list(at(off, "department_heads").get("departments") or [])),
        "judicial": names(list(at(off, "judicial", "supreme_court").get("justices") or [])
                          + list(at(off, "judicial", "superior_court").get("justices") or [])),
        "counties": names([r for c in at(off, "county", "counties").values()
                           for r in list(at(c, "commissioners").values())
                           + [at(c, k) for k, _t in OT.COUNTY_OFFICES]]),
    }
    # A county's name is a word of its tab too ("hillsborough sheriff").
    counties = names(at(off, "county", "counties").values())
    return [["page", name, what, S.canon("officials.html") + "#" + tab,
             " · ".join([words, *(counties if tab == "counties" else []), *people[tab]])]
            for tab, name, what, words in OFFICIAL_TABS if people[tab]]


def find_index(site, legs, towns):
    """site/find.json: everything the header search can answer instantly.

    One box that finds a legislator, a committee, a town or a page, so that
    "Litchfield" offers the town and Rep. Melissa Litchfield together. Bills
    are NOT in it -- 33,683 rows is a megabyte and a half, and the bill search
    already exists -- so the box hands anything it does not recognise to that
    search, which is one page load away.

    Small on purpose: 406 members, the committees, every town and ward, and the
    fixed pages. The box fetches it once, the first time somebody opens it.

    Each row is [kind, name, detail, address, extra search words]. A list rather
    than an object per row because this file is fetched by a phone: the keys
    would be a third of it. A former member's row carries a sixth: the year
    they last sat, which is how the box orders them among themselves. A
    committee no longer on the General Court's list carries the same sixth,
    the year it last sat, and a seventh, the years its page gives.

    FORMER MEMBERS AND SUBJECTS ARE IN IT, asked for on 18 September in these
    words: "Search bar should also list former legislators in the results, but
    prioritize to the most recent bills and current legislators before listing
    former ones", and "typing things like education should list both education
    policy and education funding as well as the committees". Measured before
    it was done, because 1,785 more rows is not free: the file goes from 91 KB
    to 331 KB, and from 17 KB to 58 KB over the wire, which is what a reader
    pays. Once, when they first open the box, and never on a page load.
    """
    rows = []
    for m in legs:
        where = m.get("district_label") or m.get("county") or ""
        rows.append(["legislator", m.get("display_full") or m.get("name") or "",
                     " · ".join(x for x in (
                         "Senate" if m.get("chamber") == "S" else "House",
                         where, m.get("party") or "") if x),
                     S.canon(f"legislator/{m.get('slug')}.html"),
                     " ".join(str(x) for x in (m.get("last"), m.get("first"),
                                               m.get("county"), m.get("email"))
                              if x)])
    cm = site / "committees.json"
    for c in (json.loads(cm.read_text(encoding="utf-8")) if cm.exists() else []):
        if not c.get("code"):
            continue
        # A name the committee carried before is a word to find it by: a
        # reader typing "Corrections and Criminal Justice" off a 1995 bill is
        # looking for H26.
        row = ["committee", c.get("name") or c["code"],
               ("Senate" if str(c.get("chamber", "")).upper().startswith("S")
                else "House") + " committee",
               S.canon(f"committee/{c['code']}.html"),
               " ".join(x for x in [c.get("chair") or "",
                                    *(c.get("formerly") or [])] if x)]
        # A COMMITTEE THAT NO LONGER SITS SAYS SO, AND WAITS ITS TURN (the
        # person, 16 October 2026: "There should be some indicator of former
        # committees that are no longer meeting like the special committee on
        # housing that turned into the standing committee ... so those aren't
        # prioritized in the search results"). build_committees decides it --
        # off the General Court's list today and its record ending before the
        # term now sitting -- and writes the years into the committee's own
        # JSON, which it builds before this step; a retired committee's row
        # carries the year it last sat, as a former member's does (the box
        # orders by it), and the years its page gives.
        cf = site / "committee" / f"{c['code']}.json"
        try:
            gone = (json.loads(cf.read_text(encoding="utf-8")).get("archived") or {}) \
                if cf.exists() else {}
        except ValueError:
            gone = {}
        years = str(gone.get("years") or "")
        last = [int(y) for y in re.findall(r"\b(?:19|20)\d\d\b", years)]
        if last:
            row += [max(last), years]
        # ITS EARLIER NAMES, AS A LIST (the person, 16 October 2026: "A
        # committee should say formerly if it's an old name"). They are in the
        # search words above already, which is how "housing" finds Criminal
        # Justice and Public Safety, once State Institutions and Housing; the
        # list is what lets the row say so when an old name is what matched.
        if c.get("formerly"):
            row += [None] * (7 - len(row)) + [list(c["formerly"])]
        rows.append(row)
    # THE STATUTORY AND STUDY COMMITTEES (18 October 2026), each its own kind
    # -- the General Court's class, "statutory" or "study" -- with its kind from
    # its name and the year it was set up as its line, read off the list
    # build_study_committees writes before this step. find.js ranks them after
    # the standing committees (_fstudy), as the person asked on 17 October.
    sc = site / "study_committees.json"
    for c in (json.loads(sc.read_text(encoding="utf-8")) if sc.exists() else []):
        rows.append([c["class"], c["name"],
                     c["kind"] + (f", set up in {c['year']}" if c.get("year") else ""),
                     S.canon(str(c["page"]).lstrip("/")),
                     "statutory" if c["class"] == "statutory" else "study"])
    pages = {p.stem for p in (site / "town").glob("*.html")}
    for town, seats in sorted(towns.items()):
        county = (seats[0].get("county") if seats else "") or ""
        stem = re.sub(r"[^a-z0-9]+", "-", town.lower()).strip("-")
        wards = sorted({s.get("ward") or "0" for s in seats},
                       key=lambda w: int(w) if str(w).isdigit() else 0)
        where = (county + " County" if county else "") or "New Hampshire"
        # A CITY, ONCE, ABOVE ITS WARDS (the audit of 25 October 2026, M4:
        # "Concord" listed ten rows each called a Town, Concord, Ward 1 to
        # Concord, Ward 10). A city has no page of its own, only its wards',
        # so its one row opens the Officials page's town finder on it, which
        # lists its wards; each ward's row is a Ward.
        warded = [w for w in wards if w not in ("", "0") and f"{stem}-ward-{w}" in pages]
        if stem not in pages and len(warded) > 1:
            rows.append(["town", town, f"{len(warded)} wards · {where}",
                         S.canon("officials.html") + "?town=" + quote_plus(town), county])
        for w in wards:
            slug = f"{stem}-ward-{w}" if w and w != "0" else stem
            if slug not in pages:
                continue
            rows.append(["town" if w in ("", "0") else "ward",
                         town if w in ("", "0") else f"{town}, Ward {w}",
                         where, S.canon(f"town/{slug}.html"), county])
    # The people who appear in the record and hold no seat now. Named the way
    # the person asked for on 18 September -- "Former Rep. David Smith" rather
    # than "Rep. David Smith" with "former" in a box beside it -- and never
    # flagged beyond that word: a member who has left is listed like any
    # other, just later.
    fm = site / "former.json"
    for m in (json.loads(fm.read_text(encoding="utf-8")) if fm.exists() else []):
        if not m.get("slug"):
            continue
        terms = (m.get("served") or {}).get("terms") or []
        span = f"{terms[0].split('-')[0]}–{terms[-1].split('-')[1]}" if terms else ""
        last = re.search(r"(\d{4})", (m.get("served") or {}).get("last") or "")
        rows.append(["former",
                     "Former " + (m.get("display_plain") or m.get("name") or ""),
                     " · ".join(x for x in (
                         "Senate" if m.get("chamber") == "S" else "House",
                         m.get("district_label") or "", span) if x),
                     S.canon(f"legislator/{m['slug']}.html"),
                     " ".join(str(x) for x in (m.get("county_abbr"), m.get("party"))
                              if x),
                     int(last.group(1)) if last else 0])
    # The subjects the bill search facets by, so that typing one arrives at
    # the bills rather than at nothing. meta.json is where the bill search
    # reads them from, so there is one list and it cannot drift.
    mj = site / "meta.json"
    for t in (json.loads(mj.read_text(encoding="utf-8")).get("topics") or []
              if mj.exists() else []):
        rows.append(["topic", t, "Bills on this subject",
                     S.canon("bills.html") + "?topic=" + quote_plus(t), ""])
    # THE HOW-TO GUIDES AND THE LEARN PAGES (the person, 12 October 2026:
    # "add them to the search system so you could search for them site
    # wide"). Read off the pages build_civics wrote, by their own title and
    # description, so a guide is findable the night it is published and a
    # draft -- which says so on its face -- never is.
    for kind, folder in (("guide", "guides"), ("learn", "learn")):
        for p in sorted((site / folder).glob("*.html")):
            if p.stem in ("index", "404"):
                continue
            html_ = p.read_text(encoding="utf-8", errors="replace")
            if 'class="g-draft"' in html_:
                continue
            t = re.search(r'<meta property="og:title" content="([^"]*)"', html_)
            dsc = re.search(r'<meta name="description" content="([^"]*)"', html_)
            if not t:
                continue
            name = re.sub(r"\s*\|\s*Granite Record$", "", _h.unescape(t.group(1)))
            # A GUIDE IS FOUND BY ITS TASK TOO (the person, 17 October 2026:
            # "the how to guides should be incorporated into the search in
            # some fashion"): its fifth field is the task in a reader's words
            # and the plain words it declares (guides.search_words), which
            # find.js reads as part of its name.
            words = G.search_words(p.stem) if kind == "guide" else ""
            rows.append([kind, name, _h.unescape(dsc.group(1)) if dsc else "",
                         S.canon(f"{folder}/{p.name}"), words])
    # A PAGE'S WORDS, after its line: what a reader types for it, read as
    # part of its name (find.js, _fnamed), so that these lead the bills. The
    # Officials page is what a reader asking for their own member types (the
    # audit of 25 October 2026, M3: "my senator" and "who is my state rep"
    # found nothing, and "my rep" members whose names begin "My"); the Laws
    # and the Calendar, in the header, were not in the search at all.
    for name, path, what, words in (
            ("Bill search", "bills.html", "Every bill since 1989", ""),
            ("Officials", "officials.html", "Who represents your town, and the sitting roster",
             "my senator · my representative · my rep · state rep · who is my"),
            ("Laws", "laws.html", "New Hampshire's statutes, the RSAs, chapter by chapter",
             "RSA statutes"),
            ("Calendar", "calendar.html", "Hearings and sessions, day by day", ""),
            ("Committees", "committees.html", "Every committee and what it did", ""),
            # The chambers' session days, beside the committees as on their
            # page (build_full_sessions.py, 10 October 2026).
            ("House Session Days", "session/house.html", "Every day the whole House sat, term by term", ""),
            ("Senate Session Days", "session/senate.html", "Every day the whole Senate sat, term by term", ""),
            ("Resources", "resources.html", "How New Hampshire's government works", ""),
            ("The data, as tables", "data.html", "Every table as CSV", ""),
            ("The whole record, as lists", "directory.html", "Plain lists of every page", ""),
            ("About this site", "about.html", "How it is made, and by whom", "")):
        rows.append(["page", name, what, S.canon(path), words])
    # The tabs of officials, from the file the Officials page reads, through
    # its one reader; without the file, none (the page draws no such tab).
    try:
        rows += officials_rows(read_officials())
    except (OSError, ValueError):
        pass
    (site / "find.json").write_text(json.dumps(rows, separators=(",", ":")),
                                    encoding="utf-8")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site, base = Path(a.site), a.base.rstrip("/")
    urls = []

    terms = sorted((p.stem for p in (site / "idx").glob("*.json")), reverse=True)
    counts, linked = {}, 0
    named = requests_label(site)
    for term in terms:
        rows = json.loads((site / "idx" / f"{term}.json").read_text(encoding="utf-8"))
        rows = rows if isinstance(rows, list) else rows.get("bills", [])
        counts[term] = bills_page(site, base, term, rows, urls, label=named.get(term, ""))
        linked += sum(1 for r in rows if not r.get("lsr"))
    n_terms = len([t for t in terms if t not in named])
    legs = json.loads((site / "legislators.json").read_text(encoding="utf-8"))
    assert all(m.get("slug") for m in legs), "a legislator has no slug in legislators.json"
    n_former = former_page(site, base, urls)
    n_leg = legislators_page(site, base, legs, urls, former=n_former)
    towns = json.loads((site / "towns.json").read_text(encoding="utf-8"))
    n_town = towns_page(site, base, towns, urls)
    n_days = sessions_pages(site, base, urls)
    found = find_index(site, legs, towns)
    print(f"  find.json: {len(found):,} rows for the header search "
          f"({(site / 'find.json').stat().st_size / 1024:.0f} KB)")

    hub = ['<h2>Bills, by term</h2><ul class="dirterms">']
    hub += [f'<li><a href="{S.canon("directory/bills-" + t + ".html")}">'
            f'{S.E(named.get(t, t))}</a> '
            f'<span class="dircount">{counts[t]:,}</span></li>' for t in terms]
    hub += ["</ul>", '<h2>People and places</h2><ul class="dirterms">',
            f'<li><a href="{S.canon("directory/legislators.html")}">Every sitting legislator</a> '
            f'<span class="dircount">{n_leg}</span></li>',
            (f'<li><a href="{S.canon("directory/former-legislators.html")}">Former legislators</a> '
             f'<span class="dircount">{n_former:,}</span></li>' if n_former else ""),
            f'<li><a href="{S.canon("directory/towns.html")}">Every town and ward</a> '
            f'<span class="dircount">{n_town}</span></li>',
            f'<li><a href="{S.canon("committees.html")}">Every committee</a></li>',
            f'<li><a href="{S.canon("session/house.html")}">House Session Days</a> and '
            f'<a href="{S.canon("session/senate.html")}">Senate Session Days</a></li>',
            f'<li><a href="{S.canon("resources.html")}">Resources</a></li>',
            f'<li><a href="{S.canon("data.html")}">The data, as tables</a></li></ul>']
    if n_days:
        import build_session_pages as BSP
        # The Senate and the House under their own names, the Senate first,
        # as the list of sitting legislators has them.
        hub += ['<h2>Session days</h2><ul class="dirterms">']
        hub += [f'<li><a href="{S.canon(BSP.DAYS_LIST[ch])}">Every {BSP.CHAMBER[ch]} '
                f'session day</a> <span class="dircount">{n_days[ch]:,}</span></li>'
                for ch in ("S", "H") if ch in n_days]
        hub += ["</ul>"]
    write(site, base, "/directory.html", "The whole record, as lists | Granite Record",
          # The terms of bills: the requests are a list here and not a term,
          # and counted as one this said "all 20 terms" of a record of 19.
          f"Every bill of all {n_terms} terms from 1989, every sitting legislator and every "
          "town in New Hampshire, as plain lists of links.",
          "The whole record, as lists",
          "The same record the search draws, as plain lists: nothing to type, "
          "nothing that needs JavaScript.", "".join(hub), urls)

    # THROUGH shell.sitemap_merge, AS THE OTHER BUILDERS ADD THEIRS (the
    # sitemap audit, 16 October 2026): the test here was whether an address
    # appeared anywhere in the file's text, which takes an address as listed
    # wherever a longer one starting with it is, and nothing ever took out a
    # list this run no longer writes -- the session days' two, which it
    # leaves unwritten where narratives.json is not here. Every list is
    # written on every run, so this run owns /directory whole.
    added, dropped = S.sitemap_merge(site, base, urls, "/directory")
    if added or dropped:
        print(f"  sitemap.xml: {added} added, {dropped} no longer written taken out")
    links = linked + n_leg + n_town + sum(n_days.values())
    print(f"{len(urls)} directory pages -> {site / 'directory'}, {links:,} links to record pages")
    print(f"  {n_terms} terms of bills, {n_leg} legislators, {n_town} towns and wards"
          + (f", {n_days.get('H', 0):,} House and {n_days.get('S', 0):,} Senate "
             "session days" if n_days else "")
          + "".join(f"; {counts[t]:,} of the {label} listed without a link, as a request "
                    "has no page" for t, label in named.items() if t in counts))
    empty = [t for t, n in counts.items() if not n]
    assert not empty, f"a term index listed no bills: {empty}"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
