#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-10.6
"""
The Officials page's tabs that are not the legislators' (Polish 3, the
person's feedback of 9 October 2026, item 4, and the decisions of that day):
Federal Delegation, Executive Branch, Judicial Branch and County Officials,
and the Presiding Officers at the head of the Legislators tab; and, between a
general election and Organization Day, Members-Elect (16 October 2026).

    import officials_tabs as OT
    OT.federal(off), OT.executive(off, has_page), OT.judicial(off)
    OT.county(off, legs), OT.presiding(officers, legs)
    OT.members_elect(elect, today), OT.elect_count(elect)

THE EXECUTIVE BRANCH AND THE JUDICIAL BRANCH (the person's approval of 17
October 2026: "rename the tab Executive Branch with the note; add a thin
Judicial Branch tab (Supreme and Superior Court listed, Circuit Court by
link); add commissioners compactly inside Executive Branch, kept by hand for
now"). Statewide Officials became Executive Branch, under one line saying
that two of its officers are chosen by the legislature, and gained a compact
table of the department heads; Judicial Branch is new. Both read
officials.json's department_heads and judicial, which carry the page each
name was read from and the day it was read, as the file's other records do.

Each returns the panel's inner markup, or "" where the file holds nothing to
draw, and build_pages.officials_page() puts them into the page beside My
Town and Legislators, which are build_pages' own. Nothing here is fetched
and nothing is written: every name is corrections/officials.json's, the
person's hand-kept file (read, never written, and read only through
build_members_elect.read_officials, which puts a successor in office on the
day the file gives -- 23 October 2026), or the build's own
legislators.json and officers.json -- or, on the Members-Elect tab, the
build's site/members_elect.json, as build_members_elect.for_pages reads it.

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

import datetime
import html as _html
import re

import build_date

from components import date_words, elect_race, pchip, until_attrs
from build_town_pages import tel, maillink, weblink
from build_members_elect import KEY_RE, race_order

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
    """One official: the chip, the seat under it, then how to reach them,
    and who takes the office next where the record names a successor."""
    name = (rec.get("name") or "").strip()
    if not name:
        return ""
    return (f'<li class="ofwho">{person(name, rec.get("party"))}'
            + (f'<span class="ofseat">{E(seat)}</span>' if seat else "")
            + how(rec) + successor(rec) + "</li>")


def successor(rec):
    """ONE LINE UNDER A HOLDER WHOSE SUCCESSOR IS NOT IN OFFICE YET (the
    person's approval of 23 October 2026): "B. Successor (D) takes office
    January 7, 2027." -- in words true of an office won at the polls and of
    one filled by appointment alike. The party only where the holder's is
    drawn, so a sheriff's successor carries none, as the sheriff does not;
    and data-until, so a page built the night before and read on the day
    says nothing of a day that has come. "" where the record names no
    successor, or names the holder again: a holder re-elected is still the
    holder, and nothing on the page changes. On the day,
    build_members_elect.officials_on has made the successor the holder, and
    there is no "elect" left to draw."""
    e = rec.get("elect")
    if not isinstance(e, dict):
        return ""
    name = (e.get("name") or "").strip()
    if not name or name == (rec.get("name") or "").strip():
        return ""
    party = str(e.get("party") or "").strip().upper() if rec.get("party") else ""
    said = f"{name} ({party})" if ONE_PARTY.match(party) or BOTH.match(party) else name
    takes = e.get("takes_office")
    return (f'<span class="ofseat"{until_attrs(takes, None)}>{E(said)} takes office '
            f'{E(date_words(takes, "full"))}.</span>')


def section(sid, title, people, why="", source=""):
    """One office: its heading in the margin, the people, what the office
    is, and where the names were read."""
    if not people:
        return ""
    return framed(sid, title, f'<ul class="ofwhos">{"".join(people)}</ul>', why, source)


def framed(sid, title, inner, why="", source=""):
    """A section's frame around markup of its own: the heading in the
    margin, then the markup, what it is and where it was read. A compact
    table or list of names goes in the same frame as an office's chips, so
    the tab reads as one column of sections."""
    if not inner:
        return ""
    return (f'<section class="ofsec" aria-labelledby="of-{sid}">'
            f'<h3 class="ofsech" id="of-{sid}">{E(title)}</h3><div class="ofsecb">'
            + inner
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


# TWO OF THE BRANCH'S OFFICERS ARE CHOSEN BY THE LEGISLATURE (17 October
# 2026). The tab is named for the branch, and a reader who knows the
# Secretary of State and the Treasurer are not on the ballot would otherwise
# ask why they are under it. The Constitution's Part Second, Article 67 is
# the article that says so; Article 68, which was named beside it in the
# brief, is where the state's records are kept, read that day on nh.gov's
# copy of the Constitution, so only 67 is cited. Cited by its number and not
# quoted: the Constitution's text is not yet on this disk.
CHOSEN_BY_LEGISLATURE = ("The Secretary of State and the State Treasurer are elected by the "
                         "legislature, the House and Senate together, by joint ballot "
                         "(New Hampshire Constitution, Part Second, Article 67).")


def executive(off, has_page=None):
    """The Executive Branch tab (named Statewide Officials until 17 October
    2026): the line on the two officers the legislature chooses, the
    Governor, the Executive Council, the Secretary of State, the State
    Treasurer and the Attorney General, and then the heads of the executive
    departments. `has_page` says whether the site has a page for a member's
    address, for a department head the site already draws (see head())."""
    body = statewide(off)
    depts = departments(off, has_page)
    if not body and not depts:
        return ""
    line = "Kept by hand, each name with the page it was read from"
    if off.get("_checked") and body:
        line += f"; the Governor and the Council checked {E(_long(off['_checked']))}"
    read = {(off.get(k) or {}).get("read") for k in ("secretary_of_state", "treasurer",
                                                     "attorney_general")
            if (off.get(k) or {}).get("name")} - {None}
    if len(read) == 1:
        line += (". The Secretary of State, the State Treasurer and the Attorney General "
                 f"were read on {E(_long(next(iter(read))))}")
    dh = off.get("department_heads") or {}
    if depts and dh.get("read"):
        line += (". The department heads were read from each department&rsquo;s own site "
                 f"on {E(_long(dh['read']))}")
    return (f'<div class="ofintro"><p class="ofwhy">{E(CHOSEN_BY_LEGISLATURE)}</p></div>'
            + body + depts + f'<p class="ofsrcs">{line}.</p>')


def head(rec, has_page=None):
    """A department head's name: the site's chip, linked to their page,
    where the record names a member page the site has -- a former member of
    the General Court -- and their plain name otherwise. The chip is the
    neutral one, as a sheriff's is: the office is not a party's, whatever
    party the person sat for (the person's rule for county officers, 9
    October 2026)."""
    name = (rec.get("name") or "").strip()
    slug = str(rec.get("member") or "").strip()
    if slug and has_page and has_page(slug):
        return pchip({"display_full": name, "party_code": "X", "slug": slug})
    return f'<span class="ofname">{E(name)}</span>'


def departments(off, has_page=None):
    """THE DEPARTMENT HEADS, COMPACTLY (17 October 2026): a table of each
    executive department, linked to its own site, beside its head and the
    head's title, from officials.json's department_heads. A record with no
    name -- a department whose site named nobody on the pages read -- draws
    no row, rather than a row that says nothing."""
    dh = off.get("department_heads") or {}
    rows = []
    for r in dh.get("departments") or []:
        if not (r.get("name") or "").strip():
            continue
        dept = weblink(r.get("official_url"), r.get("department")) or E(r.get("department"))
        rows.append(f'<tr><td>{dept}</td><td>{head(r, has_page)}'
                    f'<span class="ofk">{E(r.get("title"))}</span></td></tr>')
    if not rows:
        return ""
    table = ('<table class="ofdepts"><thead><tr><th scope="col">Department</th>'
             '<th scope="col">Head</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>")
    listed = weblink(dh.get("official_url"), "the state’s list of agencies")
    return framed("departments", "Department Heads", table,
                  E(" ".join(dh.get("about") or [])),
                  "each department&rsquo;s own site, linked from its name"
                  + (f"; the departments are those on {listed}" if listed else ""))


def statewide(off):
    """The Governor, the Executive Council, the Secretary of State, the
    State Treasurer and the Attorney General: the Executive Branch tab's
    offices, before its department heads."""
    g = off.get("governor") or {}
    c = off.get("council") or {}
    parts = [section("governor", "Governor", [who(g)] if g.get("name") else [],
                     E(" ".join(g.get("about") or [])))]
    council = [who(r, f"District {d}") for d, r in sorted((c.get("districts") or {}).items(),
                                                          key=lambda kv: int(kv[0]))]
    parts.append(section("council", "Executive Council", [p for p in council if p],
                         E(" ".join(c.get("about") or [])) + " Which district is yours? "
                         + FIND_TOWN, source_link(c.get("source"))))
    for key, title in (("secretary_of_state", "Secretary of State"),
                       ("treasurer", "State Treasurer"),
                       ("attorney_general", "Attorney General")):
        r = off.get(key) or {}
        if not r.get("name"):
            continue
        # The source line where the record's source is a page of its own
        # office, as the drawing has it; the Attorney General's is the
        # office's site, already under the name.
        src = r.get("source") if r.get("source") and r.get("source") != r.get("official_url") \
            else ""
        parts.append(section(key.replace("_", "-"), title, [who(r)],
                             E(" ".join(r.get("about") or [])), source_link(src)))
    return "".join(parts)


def judicial(off):
    """THE JUDICIAL BRANCH TAB, THIN (17 October 2026): the Supreme Court's
    justices, each on the neutral chip with their title and their page on
    the Judicial Branch's site, as the Executive Branch draws its officers;
    the Superior Court's justices as a compact list of names, its chief
    marked, which is what the court's own page gives; and the Circuit Court
    as one line linking to the court's own list of judges, which is long and
    changes. Everything from officials.json's judicial, and nothing said
    that its pages do not say."""
    j = off.get("judicial") or {}
    sc, su, cc = (j.get("supreme_court") or {}, j.get("superior_court") or {},
                  j.get("circuit_court") or {})
    parts = []
    people = []
    for r in sc.get("justices") or []:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        bio = weblink(r.get("official_url"), "Biography")
        people.append(f'<li class="ofwho">{person(name)}<span class="ofseat">{E(r.get("title"))}</span>'
                      + (f'<ul class="ofhow"><li>{bio}</li></ul>' if bio else "") + "</li>")
    chief = sc.get("chief") or {}
    why = " ".join([E(" ".join(sc.get("about") or [])), E(chief.get("text"))]).strip()
    # A label's apostrophe as the character: weblink escapes its label.
    told = weblink(chief.get("source"), "the Judicial Branch’s announcement") \
        if chief.get("text") else ""
    src = source_link(sc.get("source"))
    parts.append(section("supreme-court", sc.get("name") or "Supreme Court", people, why,
                         src + (f", and {told}" if src and told else told)))
    # The Superior Court: the justices, the chief marked, then each other
    # title the page lists (its senior justices on active status) under a
    # line of its own.
    groups = {}
    for r in su.get("justices") or []:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        title = (r.get("title") or "Justice").strip()
        key = "Justice" if title in ("Justice", "Chief Justice") else title
        mark = f' <span class="ofk">{E(title)}</span>' if title == "Chief Justice" else ""
        groups.setdefault(key, []).append(f'<li><span class="ofname">{E(name)}</span>{mark}</li>')
    inner = ""
    for key, rows in groups.items():
        if key != "Justice":
            inner += f'<p class="ofsub">{E(re.sub(r"Justice", "Justices", key, count=1))}</p>'
        inner += f'<ul class="ofnames">{"".join(rows)}</ul>'
    parts.append(framed("superior-court", su.get("name") or "Superior Court", inner, "",
                        source_link(su.get("source"))))
    judges = weblink(cc.get("judges_url"), "the court’s own page")
    if judges:
        parts.append(framed("circuit-court", cc.get("name") or "Circuit Court",
                            f'<p class="ofline">{E(cc.get("about"))} Its judges are listed on '
                            f"{judges}.</p>"))
    body = "".join(parts)
    if not body:
        return ""
    about = "".join(f'<p class="ofwhy">{E(p)}</p>' for p in j.get("about") or [])
    return ((f'<div class="ofintro">{about}</div>' if about else "") + body
            + '<p class="ofsrcs">Kept by hand, each name with the Judicial Branch&rsquo;s page it '
            + (f"was read from; read {E(_long(j['read']))}." if j.get("read") else "was read from.")
            + "</p>")


# THE ROSTER'S ELECTION, IN THE TENSE OF THE DAY (17 October 2026). The line
# under the county roster said "Most of these seats are on the November 2026
# ballot", typed, and would have said it after the vote. The roster is the
# 2025-2026 one, so its seats were on the ballot of the general election of
# 2026, and the line says so before that day and after it; whether the list
# has been read again since is the source line's "read".
ROSTER_ELECTION = datetime.date(2026, 11, 3)


def ballot_line(today):
    """The sentence under the county roster about its election."""
    on = date_words(ROSTER_ELECTION, "full")
    if today <= ROSTER_ELECTION:
        return f"Most of these seats are on the ballot on {on}."
    return f"Most of these seats were on the ballot on {on}; this is the roster read before it."


def county(off, legs, today=None):
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
    # The file writes a dash as two hyphens, as a plain-text file does; the
    # page sets it as the site's dash.
    about = "".join(f'<p class="ofwhy">{E(p).replace(" -- ", "&thinsp;&mdash;&thinsp;")}</p>'
                    for p in co.get("about") or [])
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
               + ". " + ballot_line(build_date.today() if today is None else today) + "</p>")
    return (f'<div class="ofintro">{about}</div>' if about else "") + "".join(parts) + src


def count(off, which):
    """How many people a tab names, for its label."""
    if which == "federal":
        return (len([s for s in (off.get("us_senate") or {}).get("seats") or [] if s.get("name")])
                + len([r for r in ((off.get("us_house") or {}).get("districts") or {}).values()
                       if r.get("name")]))
    if which == "executive":
        n = 1 if (off.get("governor") or {}).get("name") else 0
        n += len([r for r in ((off.get("council") or {}).get("districts") or {}).values()
                  if r.get("name")])
        n += len([k for k in ("secretary_of_state", "treasurer", "attorney_general")
                  if (off.get(k) or {}).get("name")])
        n += len([r for r in (off.get("department_heads") or {}).get("departments") or []
                  if (r.get("name") or "").strip()])
        return n
    if which == "judicial":
        j = off.get("judicial") or {}
        return sum(len([r for r in (j.get(c) or {}).get("justices") or []
                        if (r.get("name") or "").strip()])
                   for c in ("supreme_court", "superior_court"))
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


def members_elect(elect, today):
    """THE MEMBERS-ELECT TAB (the person's decisions of 16 October 2026):
    who November's election sent to the General Court, for the weeks before
    they sit -- the approved sentence, then the Senate, then the House by
    county and district, each race as components.elect_race draws it on a
    town page. Drawn from site/members_elect.json alone (`elect`, from
    build_members_elect.for_pages) and never beside the roster, which stays
    on the Legislators tab as who holds each seat; so no "Serving now" here.
    No contact detail: a member-elect holds no office yet. "" where there is
    no file, and the tab is then not drawn at all.

    The whole tab carries data-elect and retires on the day they take
    office, the panel's own content as well as the panel: the tab strip's
    script shows a panel by its address, and the content's own data-until
    keeps a page read after that day empty even then."""
    races = (elect or {}).get("races") or {}
    if not races:
        return ""
    election, takes = elect.get("election"), elect.get("takes_office")
    src = next((s for s in elect.get("sources") or []
                if re.fullmatch(r"https?://\S+", str(s or ""))), "")
    by = (f'<a href="{E(src)}" rel="noopener">the Secretary of State&rsquo;s count</a>' if src
          else "the Secretary of State&rsquo;s count")
    intro = (f'<div class="ofintro"><p class="ofwhy">Elected {E(date_words(election, "full"))}, '
             f'by {by}. They take office on {E(date_words(takes, "full"))}; until then the '
             '<a href="officials.html#legislators">Legislators tab</a> lists who holds each '
             'seat.</p></div>')

    def row(n, r):
        seats = r.get("seats") or 0
        return (f'<li class="elrow"><span class="elseat">District {E(n)} <small>{seats} '
                f'seat{"" if seats == 1 else "s"}</small></span>'
                f'<div class="elwho">{elect_race(r)}</div></li>')
    senate, house = [], {}
    for k in sorted(races, key=race_order):
        m = KEY_RE.match(k)
        if m.group(3):
            senate.append(row(m.group(3), races[k]))
        else:
            house.setdefault(m.group(1), []).append(row(m.group(2), races[k]))
    parts = [intro]
    if senate:
        parts.append('<section class="ofsec" aria-labelledby="of-elect-senate">'
                     '<h3 class="ofsech" id="of-elect-senate">State Senate</h3>'
                     f'<div class="ofsecb"><ul class="elrows">{"".join(senate)}</ul></div></section>')
    if house:
        parts.append('<section class="ofsec" aria-labelledby="of-elect-house">'
                     '<h3 class="ofsech" id="of-elect-house">State House</h3><div class="ofsecb">'
                     + "".join(f'<h4 class="elcounty">{E(c)} County</h4>'
                               f'<ul class="elrows">{"".join(rows)}</ul>'
                               for c, rows in house.items())
                     + "</div></section>")
    return f'<div class="elpane" data-elect{until_attrs(takes, today)}>' + "".join(parts) + "</div>"


def elect_count(elect):
    """How many members-elect the file names, for the tab's label: the
    winners drawn, not the seats, so a race not final counts none."""
    return sum(len(r.get("elected") or []) for r in ((elect or {}).get("races") or {}).values())


def _long(iso):
    """"September 9, 2026", the site's long date."""
    import components
    return components.date_words(str(iso or "")[:10], "full")
