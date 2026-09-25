#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-13.5
"""
The whole record as plain lists: every bill of every term, every sitting
legislator, every town -- each a link a person or a crawler can follow.

    python3 build_indexes.py --site site --base https://graniterecord.org

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

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote_plus

import bill_order as BO
import shell as S
import structured as LD

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
             "HR": "House resolutions", "SR": "Senate resolutions", "PET": "Petitions"}


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
    out.write_text(html, encoding="utf-8")
    urls.append(base + S.canon(path))


def bills_page(site, base, term, rows, urls):
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
            href = S.canon(f"bill/{r.get('year')}/{r['id'].lower()}.html")
            status = f' <span class="dirstatus">{S.E(r["status"])}</span>' if r.get("status") else ""
            body.append(f'<li><a href="{S.E(href)}">{S.E(r.get("n") or r["id"])}</a> '
                        f'{S.E((r.get("title") or "").strip())}{status}</li>')
        body.append("</ul>")
    jump = " &middot; ".join(f'<a href="{S.canon("/directory/bills-" + term + ".html")}#{k.lower()}">'
                             f'{S.E(KIND_NAME.get(k, k))}</a>' for k in order)
    write(site, base, f"/directory/bills-{term}.html",
          f"Every bill of the {term} term | Granite Record",
          f"All {len(rows):,} bills and resolutions of the {term} New Hampshire General Court "
          "term, by number, with each one's title and where it ended.",
          f"Every bill of {term}",
          f"{len(rows):,} bills and resolutions, by number. {jump}",
          "".join(body), urls, nav="bills.html")
    return len(rows)


def legislators_page(site, base, legs, urls):
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
          f'<a href="{S.canon("legislators.html")}">Search by town or name</a> instead.',
          "".join(body), urls, nav="legislators.html")
    return len(legs)


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
    they last sat, which is how the box orders them among themselves.

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
        rows.append(["committee", c.get("name") or c["code"],
                     ("Senate" if str(c.get("chamber", "")).upper().startswith("S")
                      else "House") + " committee",
                     S.canon(f"committee/{c['code']}.html"), c.get("chair") or ""])
    pages = {p.stem for p in (site / "town").glob("*.html")}
    for town, seats in sorted(towns.items()):
        county = (seats[0].get("county") if seats else "") or ""
        stem = re.sub(r"[^a-z0-9]+", "-", town.lower()).strip("-")
        wards = sorted({s.get("ward") or "0" for s in seats},
                       key=lambda w: int(w) if str(w).isdigit() else 0)
        for w in wards:
            slug = f"{stem}-ward-{w}" if w and w != "0" else stem
            if slug not in pages:
                continue
            rows.append(["town", town if w in ("", "0") else f"{town}, Ward {w}",
                         (county + " County" if county else "") or "New Hampshire",
                         S.canon(f"town/{slug}.html"), county])
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
    for name, path, what in (
            ("Bill search", "bills.html", "Every bill since 1989"),
            ("Legislators", "legislators.html", "The sitting roster, by town or name"),
            ("Committees", "committees.html", "Every committee and what it did"),
            ("How New Hampshire works", "learn.html", "The Learn pages"),
            ("The data, as tables", "data.html", "Every table as CSV"),
            ("The whole record, as lists", "directory.html", "Plain lists of every page"),
            ("About this site", "about.html", "How it is made, and by whom")):
        rows.append(["page", name, what, S.canon(path), ""])
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
    counts = {}
    for term in terms:
        rows = json.loads((site / "idx" / f"{term}.json").read_text(encoding="utf-8"))
        rows = rows if isinstance(rows, list) else rows.get("bills", [])
        counts[term] = bills_page(site, base, term, rows, urls)
    legs = json.loads((site / "legislators.json").read_text(encoding="utf-8"))
    assert all(m.get("slug") for m in legs), "a legislator has no slug in legislators.json"
    n_leg = legislators_page(site, base, legs, urls)
    towns = json.loads((site / "towns.json").read_text(encoding="utf-8"))
    n_town = towns_page(site, base, towns, urls)
    found = find_index(site, legs, towns)
    print(f"  find.json: {len(found):,} rows for the header search "
          f"({(site / 'find.json').stat().st_size / 1024:.0f} KB)")

    hub = ['<h2>Bills, by term</h2><ul class="dirterms">']
    hub += [f'<li><a href="{S.canon("directory/bills-" + t + ".html")}">{t}</a> '
            f'<span class="dircount">{counts[t]:,}</span></li>' for t in terms]
    hub += ["</ul>", '<h2>People and places</h2><ul class="dirterms">',
            f'<li><a href="{S.canon("directory/legislators.html")}">Every sitting legislator</a> '
            f'<span class="dircount">{n_leg}</span></li>',
            f'<li><a href="{S.canon("directory/towns.html")}">Every town and ward</a> '
            f'<span class="dircount">{n_town}</span></li>',
            f'<li><a href="{S.canon("committees.html")}">Every committee</a></li>',
            f'<li><a href="{S.canon("learn.html")}">How New Hampshire works</a></li>',
            f'<li><a href="{S.canon("data.html")}">The data, as tables</a></li></ul>']
    write(site, base, "/directory.html", "The whole record, as lists | Granite Record",
          f"Every bill of all {len(terms)} terms from 1989, every sitting legislator and every "
          "town in New Hampshire, as plain lists of links.",
          "The whole record, as lists",
          "The same record the search draws, as plain lists: nothing to type, "
          "nothing that needs JavaScript.", "".join(hub), urls)

    sm = site / "sitemap.xml"
    if sm.exists():
        text = sm.read_text(encoding="utf-8")
        add = "".join(f"<url><loc>{S.E(u)}</loc></url>\n" for u in urls if S.E(u) not in text)
        sm.write_text(text.replace("</urlset>", add + "</urlset>"), encoding="utf-8")
    links = sum(counts.values()) + n_leg + n_town
    print(f"{len(urls)} directory pages -> {site / 'directory'}, {links:,} links to record pages")
    print(f"  {len(terms)} terms of bills, {n_leg} legislators, {n_town} towns and wards")
    empty = [t for t, n in counts.items() if not n]
    assert not empty, f"a term index listed no bills: {empty}"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
