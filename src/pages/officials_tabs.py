#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-10.1
"""
The Officials page's tabs that are not the legislators' (Polish 3, the
person's feedback of 9 October 2026, item 4, and the decisions of that day):
Federal Delegation, Statewide Officials and County Officials, and the
Presiding Officers at the head of the Legislators tab.

    import officials_tabs as OT
    OT.federal(off), OT.statewide(off), OT.county(off, legs), OT.presiding(officers, legs)

Each returns the panel's inner markup, or "" where the file holds nothing to
draw, and build_pages.officials_page() puts them into the page beside My
Town and Legislators, which are build_pages' own. Nothing here is fetched
and nothing is written: every name is corrections/officials.json's, the
person's hand-kept file (read, never written), or the build's own
legislators.json and officers.json.

THE APPROVED DRAWING is the prototype of 9 October
(private/design/polish/proto/officials.html; "Statewide Officials: good",
v5), and the words are its: each office a section with its heading in the
margin, the people as the one person chip with the party letter where a
source states one, how to reach them under each chip, what the office is
after the names (answer before explanation), and the page the names were
read from. Outside links are plain links: app.css marks one by its address
and find.js opens it in a new tab.

THE COUNTY OFFICERS, as the person decided on 9 October 2026: a
commissioner carries the party the Secretary of State's roster prints, and a
commissioner who won both nominations (R/D, D/R) is drawn on the neutral
grey chip with both letters; the sheriff, the county attorney, the treasurer
and the two registers carry no party, as a Secretary of State does not.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import html as _html
import re

from components import pchip
from build_town_pages import tel, maillink, weblink

E = lambda s: _html.escape(str(s or ""), quote=True)  # noqa: E731

# A party a source states, as its letter; anything else is no party.
ONE_PARTY = re.compile(r"^[RDIL]$")
# Both nominations won: "R/D" or "D/R". Drawn neutral, both letters said.
BOTH = re.compile(r"^[RD]/[RD]$")

# The county officers after the commissioners, in the roster's order.
COUNTY_OFFICES = (("sheriff", "Sheriff"), ("county_attorney", "County Attorney"),
                  ("treasurer", "County Treasurer"), ("register_of_deeds", "Register of Deeds"),
                  ("register_of_probate", "Register of Probate"))


def person(name, party=""):
    """One official as the one person chip: the party's bar and its letter
    where the party is one, the neutral bar with both letters where it is
    R/D, and the neutral bar with no letter where none is recorded."""
    party = str(party or "").strip().upper()
    if ONE_PARTY.match(party):
        return pchip({"display_full": f"{name} ({party})", "party_code": party})
    if BOTH.match(party):
        return pchip({"display_full": f"{name} ({party})", "party_code": "X"})
    return pchip({"display_full": name, "party_code": "X"})


def where(url):
    """"council.nh.gov/district-1": the address as a reader would read it."""
    return re.sub(r"^https?://(?:www\.)?", "", str(url or "")).rstrip("/")


def phone(num):
    """A number that dials, as the town pages write one (build_town_pages.tel),
    without their row's class: this page's stylesheet does not carry it."""
    return tel(num).replace(' class="offtel"', "", 1)


def how(rec, dc_word="in Washington"):
    """How to reach one official: the phone, the Washington phone, the
    email and their own site, each a line, as many as the record holds."""
    out = []
    if rec.get("phone"):
        out.append(f"<li>{phone(rec['phone'])}</li>")
    if rec.get("phone_dc"):
        out.append(f'<li>{phone(rec["phone_dc"])} <span class="ofk">{E(dc_word)}</span></li>')
    if maillink(rec.get("email")):
        out.append(f'<li class="ofmail">{maillink(rec.get("email"))}</li>')
    site = weblink(rec.get("official_url"), where(rec.get("official_url")))
    if site:
        out.append(f"<li>{site}</li>")
    return f'<ul class="ofhow">{"".join(out)}</ul>' if out else ""


def who(rec, seat=""):
    """One official: the chip, the seat under it, then how to reach them."""
    name = (rec.get("name") or "").strip()
    if not name:
        return ""
    return (f'<li class="ofwho">{person(name, rec.get("party"))}'
            + (f'<span class="ofseat">{E(seat)}</span>' if seat else "")
            + how(rec) + "</li>")


def section(sid, title, people, why="", source=""):
    """One office: its heading in the margin, the people, what the office
    is, and where the names were read."""
    if not people:
        return ""
    return (f'<section class="ofsec" aria-labelledby="of-{sid}">'
            f'<h3 class="ofsech" id="of-{sid}">{E(title)}</h3><div class="ofsecb">'
            f'<ul class="ofwhos">{"".join(people)}</ul>'
            + (f'<p class="ofwhy">{why}</p>' if why else "")
            + (f'<p class="ofsrc">Source: {source}</p>' if source else "")
            + "</div></section>")


def source_link(url):
    """The page the names were read from, by its host. A source the file
    writes as a sentence rather than an address is not a link."""
    url = str(url or "").strip()
    if not re.fullmatch(r"https?://\S+", url):
        return ""
    return weblink(url, where(url).split("/")[0])


FIND_TOWN = '<a href="officials.html#my-town">Find your town</a>.'


def federal(off):
    """US Senate, then US House, each member with the party and how to
    reach them, and the page the names were read from."""
    us = off.get("us_senate") or {}
    uh = off.get("us_house") or {}
    sen = [who(s) for s in us.get("seats") or []]
    house = [who(r, f"District {d}") for d, r in sorted((uh.get("districts") or {}).items(),
                                                         key=lambda kv: int(kv[0]))]
    parts = [
        section("us-senate", "US Senate", [p for p in sen if p],
                E(" ".join(us.get("about") or [])), source_link(us.get("source"))),
        section("us-house", "US House", [p for p in house if p],
                "New Hampshire elects two members of the US House, one from each "
                "congressional district. Which is yours? " + FIND_TOWN,
                source_link(uh.get("source")) or source_link(uh.get("official_url"))),
    ]
    body = "".join(parts)
    if not body:
        return ""
    checked = off.get("_checked")
    return body + (f'<p class="ofsrcs">Kept by hand, each name with the page it was read '
                   f"from; checked {E(_long(checked))}.</p>" if checked else "")


def statewide(off):
    """The Governor, the Executive Council, the Secretary of State, the
    State Treasurer and the Attorney General."""
    g = off.get("governor") or {}
    c = off.get("council") or {}
    parts = [section("governor", "Governor", [who(g)] if g.get("name") else [],
                     E(" ".join(g.get("about") or [])))]
    council = [who(r, f"District {d}") for d, r in sorted((c.get("districts") or {}).items(),
                                                          key=lambda kv: int(kv[0]))]
    parts.append(section("council", "Executive Council", [p for p in council if p],
                         E(" ".join(c.get("about") or [])) + " Which district is yours? "
                         + FIND_TOWN, source_link(c.get("source"))))
    read = set()
    for key, title in (("secretary_of_state", "Secretary of State"),
                       ("treasurer", "State Treasurer"),
                       ("attorney_general", "Attorney General")):
        r = off.get(key) or {}
        if not r.get("name"):
            continue
        if r.get("read"):
            read.add(r["read"])
        # The source line where the record's source is a page of its own
        # office, as the drawing has it; the Attorney General's is the
        # office's site, already under the name.
        src = r.get("source") if r.get("source") and r.get("source") != r.get("official_url") \
            else ""
        parts.append(section(key.replace("_", "-"), title, [who(r)],
                             E(" ".join(r.get("about") or [])), source_link(src)))
    body = "".join(parts)
    if not body:
        return ""
    line = "Kept by hand, each name with the page it was read from"
    if off.get("_checked"):
        line += f"; the Governor and the Council checked {E(_long(off['_checked']))}"
    if len(read) == 1:
        line += (". The Secretary of State, the State Treasurer and the Attorney General "
                 f"were read on {E(_long(next(iter(read))))}")
    return body + f'<p class="ofsrcs">{line}.</p>'


def county(off, legs):
    """Each county's elected officers: its three commissioners, then its
    sheriff, county attorney, treasurer and two registers; and its county
    convention, the county's state representatives, counted from the roster."""
    co = off.get("county") or {}
    counties = co.get("counties") or {}
    if not counties:
        return ""
    reps = {}
    for m in legs:
        if m.get("chamber") == "H" and m.get("county"):
            reps[m["county"]] = reps.get(m["county"], 0) + 1
    about = "".join(f'<p class="ofwhy">{E(p)}</p>' for p in co.get("about") or [])
    parts = []
    for name in sorted(counties):
        c = counties[name] or {}
        people = [who(r, f"Commissioner, District {d}" if d.isdigit() else
                      r.get("office") or "Commissioner")
                  for d, r in sorted((c.get("commissioners") or {}).items(),
                                     key=lambda kv: (not kv[0].isdigit(), kv[0].zfill(3)))]
        for key, title in COUNTY_OFFICES:
            r = c.get(key)
            if r and r.get("name"):
                # The neutral roles carry no party, whatever a file says.
                people.append(who({**r, "party": ""}, r.get("office") or title))
        people = [p for p in people if p]
        n = reps.get(name, 0)
        conv = (f'Its county convention is the county&rsquo;s {n} sitting state '
                f'representative{"" if n == 1 else "s"}, listed '
                f'<a href="officials.html#legislators">by county in Legislators</a>.'
                if n else "")
        parts.append(section("county-" + re.sub(r"[^a-z]+", "-", name.lower()).strip("-"),
                             c.get("name") or f"{name} County", people, conv))
    src = ""
    if co.get("as_of"):
        src = (f'<p class="ofsrcs">Kept by hand, read from the Secretary of State&rsquo;s '
               f'county roster for 2025&ndash;2026, dated {E(_long(co["as_of"]))}'
               + (f"; read {E(_long(co['read']))}" if co.get("read") else "")
               + ". Most of these seats are on the November 2026 ballot.</p>")
    return (f'<div class="ofintro">{about}</div>' if about else "") + "".join(parts) + src


def count(off, which):
    """How many people a tab names, for its label."""
    if which == "federal":
        return (len([s for s in (off.get("us_senate") or {}).get("seats") or [] if s.get("name")])
                + len([r for r in ((off.get("us_house") or {}).get("districts") or {}).values()
                       if r.get("name")]))
    if which == "statewide":
        n = 1 if (off.get("governor") or {}).get("name") else 0
        n += len([r for r in ((off.get("council") or {}).get("districts") or {}).values()
                  if r.get("name")])
        n += len([k for k in ("secretary_of_state", "treasurer", "attorney_general")
                  if (off.get(k) or {}).get("name")])
        return n
    if which == "county":
        n = 0
        for c in ((off.get("county") or {}).get("counties") or {}).values():
            n += len([r for r in (c.get("commissioners") or {}).values() if r.get("name")])
            n += len([k for k, _t in COUNTY_OFFICES if (c.get(k) or {}).get("name")])
        return n
    return 0


# The presiding offices as a chip's role, in the person's words (item 10:
# "Senate President", "the same kind of indicator as the Speaker").
ROLE = {"Speaker of the House": "Speaker", "Deputy Speaker of the House": "Deputy Speaker",
        "President of the Senate": "Senate President"}


def presiding(officers, legs, today):
    """The presiding officers serving on the build's day, each the member's
    own chip with the office as its role: the Speaker, the Deputy Speaker and
    the Senate President, from site/officers.json (read off the journals),
    never typed. A member it names who is not on today's roster is left out
    rather than drawn without a page."""
    by_id = {str(m.get("id")): m for m in legs}
    rows = []
    for o in officers or []:
        role = ROLE.get(o.get("office"))
        if not role or not (str(o.get("from") or "") <= today < str(o.get("to") or "9999")):
            continue
        m = by_id.get(str(o.get("id")))
        if m and (o.get("b") or "") == (m.get("chamber") or ""):
            rows.append((list(ROLE).index(o["office"]), pchip({**m, "role": role})))
    if not rows:
        return ""
    rows.sort()
    return ('<section class="ofpres" aria-labelledby="of-presiding">'
            '<h3 id="of-presiding">Presiding Officers</h3>'
            '<div class="ofchips">' + "".join(c for _i, c in rows) + "</div>"
            '<p class="ofwhy">The Speaker presides over the House, and the Deputy Speaker '
            "sometimes in the Speaker&rsquo;s place; the Senate President presides over "
            "the Senate.</p></section>")


def _long(iso):
    """"September 9, 2026", the site's long date."""
    import components
    return components.date_words(str(iso or "")[:10], "full")
