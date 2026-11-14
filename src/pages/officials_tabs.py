#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-10.18
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
import i18n as I

from components import date_words, pchip, until_attrs
from build_town_pages import tel, maillink, weblink
from build_members_elect import KEY_RE, STATUSES, elect_status, race_order, read_officials

E = lambda s: _html.escape(str(s or ""), quote=True)  # noqa: E731


# THE TABS IN ANOTHER LANGUAGE (the person, 25 October 2026: "Start on the
# Officials page and My Town in Spanish"). Every function takes `lang`, last
# and "en" unless given, and English is drawn exactly as it was. The page's
# own words are I.say() calls. The file's own words -- what an office is
# ("about"), a title, an office, a department's or a court's or a county's
# name -- are the person's, in corrections/officials.json, which nothing here
# writes; their translations are catalog entries keyed off.<group>.<their
# first words> and keeping the English they were made from (data_words), so a
# sentence the person edits is said in English, marked so, until its
# translation catches up. A person's name is never translated.
def data_key(group, en):
    """The catalog key of one of the file's own words or sentences."""
    return f"off.{group}.{I.slug_words(en, n=8, cap=60)}"


def said(lang, group, en):
    """One of the file's own words or sentences, in `lang`, as markup: the
    English escaped as it always was; its translation; or, where it has none
    current, the English marked as English."""
    en = str(en or "")
    if lang == I.DEFAULT or not en:
        return E(en)
    got = I.say_piece(lang, data_key(group, en), en)
    return E(got) if got is not None else f'<span lang="en">{E(en)}</span>'


def said_text(lang, group, en):
    """The same as plain text, for a heading or a label that is escaped
    where it is put: the English where there is no translation (the miss is
    kept for preflight all the same)."""
    en = str(en or "")
    if lang == I.DEFAULT or not en:
        return en
    got = I.say_piece(lang, data_key(group, en), en)
    return en if got is None else got


def data_words(off=None):
    """[(key, English, where)] of every word and sentence of the file's own
    that a tab says, for i18n.code_words: the list a translation answers."""
    if off is None:
        off = read_officials()
    out = []

    def add(group, en, where):
        if isinstance(en, str) and en.strip():
            out.append((data_key(group, en), en, f"the officials file, {where}"))
    for k in ("governor", "council", "us_senate", "us_house", "secretary_of_state", "treasurer",
              "attorney_general", "department_heads", "county"):
        for p in (off.get(k) or {}).get("about") or []:
            add("about", p, f"{k}.about")
    j = off.get("judicial") or {}
    for p in j.get("about") or []:
        add("about", p, "judicial.about")
    sc, su, cc = (j.get("supreme_court") or {}, j.get("superior_court") or {},
                  j.get("circuit_court") or {})
    for p in sc.get("about") or []:
        add("about", p, "judicial.supreme_court.about")
    add("about", (sc.get("chief") or {}).get("text"), "judicial.supreme_court.chief")
    add("about", cc.get("about"), "judicial.circuit_court.about")
    for c in (sc, su, cc):
        add("court", c.get("name"), "judicial")
    for r in [*(sc.get("justices") or []), *(su.get("justices") or [])]:
        add("title", r.get("title"), "judicial justices")
    for r in su.get("justices") or []:
        t = (r.get("title") or "Justice").strip()
        if t not in ("Justice", "Chief Justice"):
            add("title", re.sub(r"Justice", "Justices", t, count=1), "judicial superior_court")
    for r in (off.get("department_heads") or {}).get("departments") or []:
        if (r.get("name") or "").strip():
            add("dept", r.get("department"), "department_heads")
            add("title", r.get("title"), "department_heads")
    for _k, t in COUNTY_OFFICES:
        add("office", t, "officials_tabs.COUNTY_OFFICES")
    add("office", "Commissioner", "officials_tabs.county")
    for name, c in ((off.get("county") or {}).get("counties") or {}).items():
        add("county", (c or {}).get("name"), f"county.counties.{name}")
        for r in [*((c or {}).get("commissioners") or {}).values(),
                  *[(c or {}).get(k) or {} for k, _t in COUNTY_OFFICES]]:
            add("office", (r or {}).get("office"), f"county.counties.{name}")
    return out

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


def how(rec, dc_word=None, lang="en"):
    """How to reach one official: the phone, the Washington phone, the
    email and their own site, each a line, as many as the record holds."""
    if dc_word is None:
        dc_word = I.say(lang, "off.in_washington", "in Washington")
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


def who(rec, seat="", lang="en", partisan=True):
    """One official: the chip, the seat under it, then how to reach them,
    and who takes the office next where the record names a successor. A
    record with no name is a vacancy where it says so (vacant), and draws
    nothing where it does not. `partisan` False for an office drawn with no
    party, so that no successor's party is said either."""
    name = (rec.get("name") or "").strip()
    if not name:
        return vacant(rec, seat, lang, partisan)
    return (f'<li class="ofwho">{person(name, rec.get("party"))}'
            + (f'<span class="ofseat">{E(seat)}</span>' if seat else "")
            + how(rec, lang=lang) + successor(rec, lang) + "</li>")


# A SEAT THAT IS EMPTY, SAID SO (the owner's word through the manager
# session, 5 November 2026, for the Strafford County commissioner who
# resigned mid-term). The hand file's record of the office keeps its name
# empty and says, under "vacant", the day the seat fell empty and the page
# that says so:
#
#     "2": {"name": "", "office": "County Commissioner, District 2", ...,
#           "vacant": {"since": "2026-10-30", "source": "https://...",
#                      "read": "2026-11-06"}}
#
# The row is a dashed box reading Vacant -- a dashed outline is what says
# vacant on the seat chart too, and it is not a chip, which is a person's --
# with the seat, the day and the source
# under it, and the successor's line where the record names one. No name is
# drawn for an empty seat: who left it is the source's to say. On the day
# the successor takes office, build_members_elect.officials_on makes them the
# holder, and a record with a name is never drawn as vacant, so a "vacant"
# left in it says nothing. A vacancy with no day or no source stops the
# build: the page would say a seat is empty on nobody's word.
def vacant(rec, seat="", lang="en", partisan=True):
    """The row of an empty seat, or "" where the record does not say it is one."""
    v = rec.get("vacant")
    if (rec.get("name") or "").strip() or not isinstance(v, dict):
        return ""
    since, src = str(v.get("since") or ""), str(v.get("source") or "").strip()
    office = rec.get("office") or seat
    if not src:
        raise SystemExit(f"corrections/officials.json: the vacancy of {office!r} names no source, "
                         "the page that says the seat is empty")
    try:
        day = datetime.date.fromisoformat(since) if re.fullmatch(r"\d{4}-\d\d-\d\d", since) else None
    except ValueError:
        day = None
    if day is None:
        raise SystemExit(f"corrections/officials.json: the vacancy of {office!r} is dated {since!r}, "
                         "not a day written YYYY-MM-DD")
    link = source_link(src) or E(src)
    return ('<li class="ofwho ofvac"><span class="ofvacant">'
            + E(I.say(lang, "off.vacant", "Vacant")) + "</span>"
            + (f'<span class="ofseat">{E(seat)}</span>' if seat else "")
            + '<ul class="ofhow"><li>'
            + I.say(lang, "off.vacant_since", "Vacant since {day}.", day=E(date_words(day, "full", lang)))
            + "</li><li>" + I.say(lang, "off.source", "Source: {source}", source=link) + "</li></ul>"
            + successor(rec, lang, partisan) + "</li>")


def successor(rec, lang="en", partisan=None):
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
    there is no "elect" left to draw. `partisan` says whether the office
    is drawn with a party where the record cannot: an empty seat has no
    holder's party to go by (vacant)."""
    e = rec.get("elect")
    if not isinstance(e, dict):
        return ""
    name = (e.get("name") or "").strip()
    if not name or name == (rec.get("name") or "").strip():
        return ""
    if partisan is None:
        partisan = bool(rec.get("party"))
    party = str(e.get("party") or "").strip().upper() if partisan else ""
    said = f"{name} ({party})" if ONE_PARTY.match(party) or BOTH.match(party) else name
    takes = e.get("takes_office")
    return (f'<span class="ofseat"{until_attrs(takes, None)}>'
            + I.say(lang, "off.takes_office", "{who} takes office {day}.", who=E(said),
                    day=E(date_words(takes, "full", lang)))
            + "</span>")


def section(sid, title, people, why="", source="", lang="en"):
    """One office: its heading in the margin, the people, what the office
    is, and where the names were read."""
    if not people:
        return ""
    return framed(sid, title, f'<ul class="ofwhos">{"".join(people)}</ul>', why, source, lang)


def framed(sid, title, inner, why="", source="", lang="en"):
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
            + (f'<p class="ofsrc">{I.say(lang, "off.source", "Source: {source}", source=source)}</p>'
               if source else "")
            + "</div></section>")


def source_link(url):
    """The page the names were read from, by its host. A source the file
    writes as a sentence rather than an address is not a link."""
    url = str(url or "").strip()
    if not re.fullmatch(r"https?://\S+", url):
        return ""
    return weblink(url, where(url).split("/")[0])


FIND_TOWN = '<a href="officials.html#my-town">Find your town</a>.'


def find_town(lang="en"):
    """FIND_TOWN in `lang`."""
    return ('<a href="officials.html#my-town">' + I.say(lang, "off.find_town", "Find your town")
            + "</a>.")


def abouts(lang, rec, drop=None):
    """What an office is, the record's "about" sentences, in `lang`, less
    any sentence `drop` (a pattern) finds in the words shown: the English, or
    its translation, which is looked up by the whole English as it always
    was, so a translation stays current."""
    out = []
    for p in rec.get("about") or []:
        if drop is None:
            out.append(said(lang, "about", p))
            continue
        got = said_text(lang, "about", p)
        kept = " ".join(s for s in re.split(r"(?<=[.!?])\s+", got) if not drop.search(s))
        if not kept:
            continue
        out.append(E(kept) if lang == I.DEFAULT or got != p else f'<span lang="en">{E(kept)}</span>')
    return " ".join(out)


# JOINT BALLOT, SAID ONCE (the audit of 25 October 2026, S7). The Executive
# Branch tab opens with how the legislature elects the Secretary of State and
# the State Treasurer (CHOSEN_BY_LEGISLATURE), and each of their cards said
# it again from the hand-kept file -- "The Secretary is elected by a joint
# session of the House and Senate." The cards leave out the sentence that
# says it, in English and in the translation alike; the file is the
# person's, and keeps it.
JOINT_SAID = re.compile(r"\bjoint session\b|\bsesi[oó]n conjunta\b", re.I)


def federal(off, lang="en"):
    """US Senate, then US House, each member with the party and how to
    reach them, and the page the names were read from."""
    us = off.get("us_senate") or {}
    uh = off.get("us_house") or {}
    sen = [who(s, lang=lang) for s in us.get("seats") or []]
    house = [who(r, I.say(lang, "off.district", "District {d}", d=d), lang)
             for d, r in sorted((uh.get("districts") or {}).items(), key=lambda kv: int(kv[0]))]
    parts = [
        section("us-senate", I.say(lang, "off.us_senate", "US Senate"), [p for p in sen if p],
                abouts(lang, us), source_link(us.get("source")), lang),
        section("us-house", I.say(lang, "off.us_house", "US House"), [p for p in house if p],
                I.say(lang, "off.us_house_why", "New Hampshire elects two members of the US "
                      "House, one from each congressional district. Which is yours?")
                + " " + find_town(lang),
                source_link(uh.get("source")) or source_link(uh.get("official_url")), lang),
    ]
    body = "".join(parts)
    if not body:
        return ""
    checked = off.get("_checked")
    return body + ('<p class="ofsrcs">'
                   + I.say(lang, "off.fed_checked", "Kept by hand, each name with the page it was "
                           "read from; checked {day}.", day=E(_long(checked, lang)))
                   + "</p>" if checked else "")


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


def executive(off, has_page=None, lang="en"):
    """The Executive Branch tab (named Statewide Officials until 17 October
    2026): the line on the two officers the legislature chooses, the
    Governor, the Executive Council, the Secretary of State, the State
    Treasurer and the Attorney General, and then the heads of the executive
    departments. `has_page` says whether the site has a page for a member's
    address, for a department head the site already draws (see head())."""
    body = statewide(off, lang)
    depts = departments(off, has_page, lang)
    if not body and not depts:
        return ""
    line = I.say(lang, "off.kept", "Kept by hand, each name with the page it was read from")
    if off.get("_checked") and body:
        line += I.say(lang, "off.exec_checked", "; the Governor and the Council checked {day}",
                      day=E(_long(off["_checked"], lang)))
    read = {(off.get(k) or {}).get("read") for k in ("secretary_of_state", "treasurer",
                                                     "attorney_general")
            if (off.get(k) or {}).get("name")} - {None}
    if len(read) == 1:
        line += I.say(lang, "off.three_read", ". The Secretary of State, the State Treasurer and "
                      "the Attorney General were read on {day}",
                      day=E(_long(next(iter(read)), lang)))
    dh = off.get("department_heads") or {}
    if depts and dh.get("read"):
        line += I.say(lang, "off.depts_read", ". The department heads were read from each "
                      "department&rsquo;s own site on {day}", day=E(_long(dh["read"], lang)))
    chosen = I.say(lang, "off.chosen", "The Secretary of State and the State Treasurer are "
                   "elected by the legislature, the House and Senate together, by joint ballot "
                   "(New Hampshire Constitution, Part Second, Article 67).")
    return (f'<div class="ofintro"><p class="ofwhy">{E(chosen)}</p></div>'
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


def departments(off, has_page=None, lang="en"):
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
        dname = said_text(lang, "dept", r.get("department"))
        dept = weblink(r.get("official_url"), dname) or E(dname)
        rows.append(f'<tr><td>{dept}</td><td>{head(r, has_page)}'
                    f'<span class="ofk">{said(lang, "title", r.get("title"))}</span></td></tr>')
    if not rows:
        return ""
    table = ('<table class="ofdepts"><thead><tr><th scope="col">'
             + I.say(lang, "off.th_dept", "Department") + '</th><th scope="col">'
             + I.say(lang, "off.th_head", "Head") + "</th></tr></thead><tbody>"
             + "".join(rows) + "</tbody></table>")
    listed = weblink(dh.get("official_url"),
                     I.say(lang, "off.agency_list", "the state’s list of agencies"))
    return framed("departments", I.say(lang, "off.dept_heads", "Department Heads"), table,
                  abouts(lang, dh),
                  I.say(lang, "off.dept_src", "each department&rsquo;s own site, linked from its "
                        "name")
                  + (I.say(lang, "off.dept_listed", "; the departments are those on {listed}",
                           listed=listed) if listed else ""), lang)


def statewide(off, lang="en"):
    """The Governor, the Executive Council, the Secretary of State, the
    State Treasurer and the Attorney General: the Executive Branch tab's
    offices, before its department heads."""
    g = off.get("governor") or {}
    c = off.get("council") or {}
    parts = [section("governor", I.say(lang, "off.governor", "Governor"),
                     [who(g, lang=lang)] if g.get("name") else [], abouts(lang, g), "", lang)]
    council = [who(r, I.say(lang, "off.district", "District {d}", d=d), lang)
               for d, r in sorted((c.get("districts") or {}).items(), key=lambda kv: int(kv[0]))]
    parts.append(section("council", I.say(lang, "off.council", "Executive Council"),
                         [p for p in council if p],
                         abouts(lang, c) + " "
                         + I.say(lang, "off.which_district", "Which district is yours?") + " "
                         + find_town(lang), source_link(c.get("source")), lang))
    titles = {"secretary_of_state": I.say(lang, "off.sos", "Secretary of State"),
              "treasurer": I.say(lang, "off.treasurer", "State Treasurer"),
              "attorney_general": I.say(lang, "off.ag", "Attorney General")}
    for key, title in titles.items():
        r = off.get(key) or {}
        if not r.get("name"):
            continue
        # The source line where the record's source is a page of its own
        # office, as the drawing has it; the Attorney General's is the
        # office's site, already under the name.
        src = r.get("source") if r.get("source") and r.get("source") != r.get("official_url") \
            else ""
        parts.append(section(key.replace("_", "-"), title, [who(r, lang=lang)],
                             abouts(lang, r, JOINT_SAID if key != "attorney_general" else None),
                             source_link(src), lang))
    return "".join(parts)


def judicial(off, lang="en"):
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
        bio = weblink(r.get("official_url"), I.say(lang, "off.bio", "Biography"))
        people.append(f'<li class="ofwho">{person(name)}<span class="ofseat">'
                      f'{said(lang, "title", r.get("title"))}</span>'
                      + (f'<ul class="ofhow"><li>{bio}</li></ul>' if bio else "") + "</li>")
    chief = sc.get("chief") or {}
    why = " ".join([abouts(lang, sc), said(lang, "about", chief.get("text"))]).strip()
    # A label's apostrophe as the character: weblink escapes its label.
    told = weblink(chief.get("source"), I.say(lang, "off.announcement",
                                              "the Judicial Branch’s announcement")) \
        if chief.get("text") else ""
    src = source_link(sc.get("source"))
    parts.append(section("supreme-court",
                         said_text(lang, "court", sc.get("name"))
                         or I.say(lang, "off.supreme", "Supreme Court"), people, why,
                         (I.say(lang, "off.src_and", "{src}, and {told}", src=src, told=told)
                          if src and told else src + told), lang))
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
        mark = f' <span class="ofk">{said(lang, "title", title)}</span>' \
            if title == "Chief Justice" else ""
        groups.setdefault(key, []).append(f'<li><span class="ofname">{E(name)}</span>{mark}</li>')
    inner = ""
    for key, rows in groups.items():
        if key != "Justice":
            inner += (f'<p class="ofsub">'
                      f'{said(lang, "title", re.sub(r"Justice", "Justices", key, count=1))}</p>')
        inner += f'<ul class="ofnames">{"".join(rows)}</ul>'
    parts.append(framed("superior-court",
                        said_text(lang, "court", su.get("name"))
                        or I.say(lang, "off.superior", "Superior Court"), inner, "",
                        source_link(su.get("source")), lang))
    judges = weblink(cc.get("judges_url"), I.say(lang, "off.court_page", "the court’s own page"))
    if judges:
        parts.append(framed("circuit-court",
                            said_text(lang, "court", cc.get("name"))
                            or I.say(lang, "off.circuit", "Circuit Court"),
                            f'<p class="ofline">{said(lang, "about", cc.get("about"))} '
                            + I.say(lang, "off.judges_on", "Its judges are listed on {judges}.",
                                    judges=judges) + "</p>", "", "", lang))
    body = "".join(parts)
    if not body:
        return ""
    about = "".join(f'<p class="ofwhy">{said(lang, "about", p)}</p>' for p in j.get("about") or [])
    return ((f'<div class="ofintro">{about}</div>' if about else "") + body
            + '<p class="ofsrcs">'
            + (I.say(lang, "off.judicial_read", "Kept by hand, each name with the Judicial "
                     "Branch&rsquo;s page it was read from; read {day}.",
                     day=E(_long(j["read"], lang))) if j.get("read") else
               I.say(lang, "off.judicial_kept", "Kept by hand, each name with the Judicial "
                     "Branch&rsquo;s page it was read from."))
            + "</p>")


# THE ROSTER'S ELECTION, IN THE TENSE OF THE DAY (17 October 2026). The line
# under the county roster said "Most of these seats are on the November 2026
# ballot", typed, and would have said it after the vote. The roster is the
# 2025-2026 one, so its seats were on the ballot of the general election of
# 2026, and the line says so before that day and after it; whether the list
# has been read again since is the source line's "read".
ROSTER_ELECTION = datetime.date(2026, 11, 3)


def ballot_line(today, lang="en"):
    """The sentence under the county roster about its election."""
    on = date_words(ROSTER_ELECTION, "full", lang)
    if today <= ROSTER_ELECTION:
        return I.say(lang, "off.ballot_on", "Most of these seats are on the ballot on {day}.",
                     day=on)
    return I.say(lang, "off.ballot_was", "Most of these seats were on the ballot on {day}; "
                 "this is the roster read before it.", day=on)


def county(off, legs, today=None, lang="en"):
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
    about = "".join(f'<p class="ofwhy">'
                    f'{said(lang, "about", p).replace(" -- ", "&thinsp;&mdash;&thinsp;")}</p>'
                    for p in co.get("about") or [])
    parts = []
    for name in sorted(counties):
        c = counties[name] or {}
        people = [who(r, I.say(lang, "off.commissioner_d", "Commissioner, District {d}", d=d)
                      if d.isdigit() else said_text(lang, "office", r.get("office") or "Commissioner"),
                      lang)
                  for d, r in sorted((c.get("commissioners") or {}).items(),
                                     key=lambda kv: (not kv[0].isdigit(), kv[0].zfill(3)))]
        for key, title in COUNTY_OFFICES:
            r = c.get(key)
            if r and (r.get("name") or r.get("vacant")):
                # The neutral roles carry no party, whatever a file says, and
                # nor does whoever takes one next.
                people.append(who({**r, "party": ""},
                                  said_text(lang, "office", r.get("office") or title), lang,
                                  partisan=False))
        people = [p for p in people if p]
        n = reps.get(name, 0)
        listed = ('<a href="officials.html#legislators">'
                  + I.say(lang, "off.by_county_link", "by county in Legislators") + "</a>")
        conv = ((I.say(lang, "off.conv_one", "Its county convention is the county&rsquo;s {n} "
                       "sitting state representative, listed {listed}.", n=n, listed=listed)
                 if n == 1 else
                 I.say(lang, "off.conv", "Its county convention is the county&rsquo;s {n} sitting "
                       "state representatives, listed {listed}.", n=n, listed=listed))
                if n else "")
        title = (said_text(lang, "county", c.get("name")) if c.get("name")
                 else I.say(lang, "off.county_name", "{name} County", name=name))
        parts.append(section("county-" + re.sub(r"[^a-z]+", "-", name.lower()).strip("-"),
                             title, people, conv, "", lang))
    src = ""
    if co.get("as_of"):
        src = ('<p class="ofsrcs">'
               + I.say(lang, "off.roster_src", "Kept by hand, read from the Secretary of "
                       "State&rsquo;s county roster for 2025&ndash;2026, dated {day}",
                       day=E(_long(co["as_of"], lang)))
               + (I.say(lang, "off.read_on", "; read {day}", day=E(_long(co["read"], lang)))
                  if co.get("read") else "")
               + ". " + ballot_line(build_date.today() if today is None else today, lang) + "</p>")
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


def presiding(officers, legs, today, lang="en"):
    """The presiding officers serving on the build's day, each the member's
    own chip with the office as its role: the Speaker, the Deputy Speaker and
    the Senate President, from site/officers.json (read off the journals),
    never typed. A member it names who is not on today's roster is left out
    rather than drawn without a page."""
    by_id = {str(m.get("id")): m for m in legs}
    roles = {"Speaker": I.say(lang, "off.role.speaker", "Speaker"),
             "Deputy Speaker": I.say(lang, "off.role.deputy", "Deputy Speaker"),
             "Senate President": I.say(lang, "off.role.president", "Senate President")}
    rows = []
    for o in officers or []:
        role = ROLE.get(o.get("office"))
        if not role or not (str(o.get("from") or "") <= today < str(o.get("to") or "9999")):
            continue
        m = by_id.get(str(o.get("id")))
        if m and (o.get("b") or "") == (m.get("chamber") or ""):
            rows.append((list(ROLE).index(o["office"]), pchip({**m, "role": roles[role]})))
    if not rows:
        return ""
    rows.sort()
    # THE CHIPS ALONE (the owner's walk of 7 November 2026): the sentence
    # under them -- "The Speaker presides over the House, and the Deputy
    # Speaker sometimes in the Speaker's place; the Senate President presides
    # over the Senate." -- said what each chip's own role already says.
    return ('<section class="ofpres" aria-labelledby="of-presiding">'
            '<h3 id="of-presiding">' + I.say(lang, "off.presiding", "Presiding Officers")
            + '</h3><div class="ofchips">' + "".join(c for _i, c in rows) + "</div>"
            "</section>")


# THE MEMBERS-ELECT TAB LIKE THE LEGISLATORS TAB (the owner's walks of 7
# and 8 November 2026). Each member-elect is the Legislators tab's own chip,
# with a title and a district -- "Rep.-elect Kristine Trow (D - Rock 13)",
# "Sen.-elect David Rochefort (R - SD1)", the owner's choice of "Rep.-elect"
# (since the walk of dry run 8, 8 November 2026, "Rep. “Elect” Kristine Trow",
# the quotation marks inside the chip) -- and beside it, outside it, one word
# for who they are (the walk of dry run 7, through the laptop manager).
#
# THE WORD IS build_members_elect.elect_status's, the one classification the
# list, its counts and its filter share (the owner, 12 November 2026):
#
#   INCUMBENT     serving now in the chamber they were elected to (a sitting
#                 member elected to another district of the same chamber is
#                 one: the owner's four kinds have no "new district")
#   RETURNING     served before and is not serving now: an earlier term, or
#                 the term now ending until they left it partway through
#   NEW CHAMBER   their most recent service was in the other chamber
#   NEW           nobody the roster, the former members or the bills before
#                 1999 name
#   PRIOR SERVICE NOT ON RECORD
#                 the record cannot say (elect_status says when)
#
# The chamber a member sat in last is their roster or former.json row's. A
# member the file links but whose row is not in `people` gets no word rather
# than a guessed one.
def kind_words(kind, lang="en"):
    """The word for an elect_kind(), in `lang`; "" for none."""
    return {"returning": I.say(lang, "elect.kind.returning", "Returning"),
            "incumbent": I.say(lang, "elect.kind.incumbent", "Incumbent"),
            "chamber": I.say(lang, "elect.kind.chamber", "New chamber"),
            "new": I.say(lang, "elect.kind.new", "New"),
            "unsure": I.say(lang, "elect.kind.unsure", "Prior service not on record")}.get(kind, "")


# A name's last word is its surname but for these, which follow one.
NAME_SUFFIX = re.compile(r",?\s+(?:Jr|Sr|II|III|IV)\.?$", re.I)
# The party a member-elect's letter stands for, in the roster's words, which
# build_pages.party_word says in the page's language.
PARTY_OF = {"R": "Republican", "D": "Democrat", "I": "Independent", "L": "Libertarian"}


def elect_kind(e, key, by_id=None):
    """Which of kind_words' words a member-elect carries: elect_status's, from
    the file's `k` and `u` and the row `by_id` holds for a member it links
    (the roster's for a sitting member, former.json's for a former one). ""
    where the file or the rows cannot say."""
    row = (by_id or {}).get(str(e.get("id") or "")) if e.get("id") else None
    return elect_status(e, key, row)


def elect_word(e, key, by_id=None, lang="en"):
    """The word beside a member-elect's chip, as its own label outside the
    chip (the walk of 8 November 2026: inside it, the chip wrapped to two
    lines where the Legislators tab's is one); "" for none. The one that
    says the record cannot say carries what it means as its title."""
    kind = elect_kind(e, key, by_id)
    w = kind_words(kind, lang)
    if not w:
        return ""
    why = (' title="' + E(I.say(lang, "elect.unsure_why", "The record has a sponsor of the same "
                                "surname from this county before 1999, when bills carried no member "
                                "number, and cannot say whether it is the same person.")) + '"'
           if kind == "unsure" else "")
    return f' <span class="elkind" translate="yes"{why}>{E(w)}</span>'


def elect_chip(e, key, lang="en"):
    """One member-elect as the site's person chip, the Legislators tab's: the
    title, the name, and the party and district in the chip's tag, the
    cross-nominated on the neutral chip with both letters and no letter
    where none was printed (as components.elect_race draws them), linked
    only where the file links them. No contact detail; the word for who
    they are is elect_word's, beside it."""
    from build_site_v2 import district_tag
    m = KEY_RE.match(key)
    p = str(e.get("p") or "")
    if m.group(3):
        title, where = I.say(lang, "elect.title_sen", "Sen. “Elect”"), district_tag("S", m.group(3))
    else:
        title = I.say(lang, "elect.title_rep", "Rep. “Elect”")
        where = district_tag("H", m.group(2), county=m.group(1))
    tag = " - ".join(x for x in (p, where) if x)
    return pchip({"party_code": p if len(p) == 1 else "X",
                  "display_full": f'{title} {e.get("n") or ""}' + (f" ({tag})" if tag else ""),
                  # A new person's provisional page ("e", build_elect_pages.py)
                  # where they have one, as components.elect_race draws it;
                  # never another member's record. The tab once read only
                  # the member's id and slug, and so linked none of the new
                  # (13 November 2026: 0 of 165 on the dry run).
                  "slug": e.get("s") if e.get("id") and e.get("s")
                          else (e.get("e") if e.get("k") == "new" else "") or ""})


def elect_party(e):
    """The column a member-elect is listed in: the party's letter, "+" for
    more than one (R/D), "" for none printed."""
    p = str(e.get("p") or "")
    return p if len(p) == 1 else "+" if p else ""


def elect_party_words(code, n, lang="en"):
    """A column's or a total's name: "Democrats", "Republican"; "More than
    one party" for the cross-nominated, "Party not on file" for none."""
    from build_pages import party_word
    if code == "+":
        return I.say(lang, "elect.party_more", "More than one party")
    return party_word(PARTY_OF.get(code, code) if code else "Party not on file", lang,
                      plural=n != 1)


def elect_kind_line(won_keys, by_id, lang="en"):
    """THE KINDS, COUNTED (the owner's walk of dry run 8, 8 November 2026): one
    chamber's members-elect by the word each chip carries, from elect_kind
    itself and so never a second classification -- "230 incumbent &middot; 24
    returning &middot; 4 new chamber &middot; 100 new". `won_keys` is
    [(member-elect, race key)]; a member the rows cannot place has no word
    and is not counted; "" where none has one."""
    n = {}
    for e, k in won_keys:
        kind = elect_kind(e, k, by_id)
        if kind:
            n[kind] = n.get(kind, 0) + 1
    return " &middot; ".join(f"{n[kind]} {E(kind_words(kind, lang)).lower()}"
                             for kind in STATUSES if n.get(kind))


def elect_totals(races, lang="en", by_id=None):
    """THE SEATS AT THE TOP (the owner's walk of 7 November 2026, C): the
    Legislators tab's "Who holds the seats", for the members-elect -- each
    chamber's members-elect by party, the cross-nominated apart and a
    letter each ("R/D"), then the seats not final, then any with nobody on
    file -- as a bar on a wide screen and as one short line on a phone
    ("House 279 D &middot; 99 R &middot; 19 not final"). Drawn as
    build_pages.static_bar draws the roster's, in its classes."""
    out = []
    for ch, sen in (("S", True), ("H", False)):
        rs = [r for k, r in races.items() if bool(KEY_RE.match(k).group(3)) == sen]
        if not rs:
            continue
        seats = sum(r.get("seats") or 0 for r in rs)
        won = [e for r in rs for e in r.get("elected") or []]
        nf = sum(r.get("not_final") or 0 for r in rs)
        left = max(seats - len(won) - nf, 0)
        one, more = {}, {}
        for e in won:
            p = str(e.get("p") or "")
            (one if len(p) <= 1 else more)[p] = (one if len(p) <= 1 else more).get(p, 0) + 1
        # The parties largest first, as the roster's; then the
        # cross-nominations, each by its letters; then no party printed.
        groups = ([(p, n, elect_party_words(p, n, lang), "seg-" + p)
                   for p, n in sorted(one.items(), key=lambda kv: (-kv[1], kv[0])) if p]
                  + [(p, n, p, "seg-X") for p, n in sorted(more.items())]
                  + ([("", one[""], elect_party_words("", one[""], lang), "seg-X")]
                     if one.get("") else []))
        if nf:
            groups.append(("nf", nf, I.say(lang, "elect.nf_short", "Not final"), "seg-NF"))
        if left:
            groups.append(("none", left, I.say(lang, "elect.none_short", "No one on file"), "seg-V"))
        name = (I.say(lang, "comp.senate", "Senate") if sen else I.say(lang, "comp.house", "House"))
        segs = "".join(f'<span class="pseg {c}" style="width:{100 * n / (seats or 1):.4f}%" '
                       f'title="{E(w)}: {n}"></span>' for _p, n, w, c in groups)
        legend = "".join(f'<span><span class="pdot {c}"></span>{E(w)} <b>{n}</b></span>'
                         for _p, n, w, c in groups)
        said = (I.say(lang, "elect.won_nf", "{won} of {seats} seats elected, {nf} not final",
                      won=len(won), seats=seats, nf=nf) if nf else
                I.say(lang, "elect.won", "{won} of {seats} seats elected", won=len(won), seats=seats))
        # On a phone, a party's letter for the eye and its name for a screen
        # reader; a cross-nomination's letters, which are its name here; and
        # the rest in words.
        def bit(p, n, w):
            if p == "nf":
                return I.say(lang, "elect.n_not_final", "{n} not final", n=n)
            if p == "none":
                return I.say(lang, "elect.n_none", "{n} with no one on file", n=n)
            if not p:
                return f"{n} {E(w).lower()}"
            if len(p) > 1:
                return f"{n} {E(p)}"
            return f'{n} <span aria-hidden="true">{E(p)}</span><span class="sr">{E(w)}</span>'
        # Each count whole on its line, as build_pages.short_bar's: on a
        # narrow phone the House's can take two lines, breaking between counts.
        # The line is the block's last part, under the bar: a phone shows the
        # bar and the line, a wider screen the bar, its line and its legend
        # (the walk of 8 November 2026: a chart on a phone as well).
        short = " &middot; ".join(f'<span class="csb">{bit(p, n, w)}</span>' for p, n, w, _c in groups)
        out.append(f'<div class="comp"><div class="compline"><b>{E(name)}</b>'
                   f'<span class="statemeta">{said}</span></div><div class="pbar2">{segs}</div>'
                   f'<div class="plegend">{legend}</div>'
                   f'<p class="compshort"><b>{E(name)}</b> {short}</p></div>')
    if not out:
        return ""
    # The kinds, one line a chamber, under the bars (the walk of dry run 8).
    kinds = ""
    for sen in (True, False):
        line = elect_kind_line([(e, k) for k, r in races.items() if bool(KEY_RE.match(k).group(3)) == sen
                                for e in r.get("elected") or []], by_id, lang)
        if line:
            name = I.say(lang, "comp.senate", "Senate") if sen else I.say(lang, "comp.house", "House")
            kinds += f'<p class="elkinds"><b>{E(name)}</b> {line}</p>'
    return ('<div class="comp-wrap comp-top"><h2>'
            + I.say(lang, "elect.who_won", "Who won the seats") + "</h2>"
            + "".join(out) + kinds + elect_nf_list(races, lang) + "</div>")


def elect_nf_list(races, lang="en"):
    """THE SEATS NOT FINAL, LISTED, under "Who won the seats" (the walk of 8
    November 2026: By district went, and "Result not final -- a recount was
    requested" had to stay where a reader of either view finds it): a fold
    like the vacancies' on the Legislators tab, "19 seats not final, in 16
    districts", opening on each district, the Senate's first. "" where every
    result is final."""
    nf = [(k, races[k]) for k in sorted(races, key=race_order) if races[k].get("not_final")]
    if not nf:
        return ""
    n, d = sum(r["not_final"] for _k, r in nf), len(nf)
    head = (I.say(lang, "elect.nf_list_one", "{n} seat not final", n=n) if n == 1 else
            I.say(lang, "elect.nf_list_one_d", "{n} seats not final, in one district", n=n) if d == 1 else
            I.say(lang, "elect.nf_list", "{n} seats not final, in {d} districts", n=n, d=d))
    every = all(r.get("recount") for _k, r in nf)
    why = ("" if not every else
           I.say(lang, "elect.recount_one", "A recount was requested.") if d == 1 else
           I.say(lang, "elect.recount_each", "A recount was requested in each."))

    def where(k, r):
        m = KEY_RE.match(k)
        name = (I.say(lang, "map.tag_senate", "Senate District {n}", n=E(m.group(3))) if m.group(3) else
                I.say(lang, "comp.county_district", "{county} District {district}",
                      county=E(m.group(1)), district=E(m.group(2))))
        return ('<div class="mem">' + name
                + (" " + I.say(lang, "comp.n_seats", "— {n} seats", n=r["not_final"])
                   if r["not_final"] > 1 else "")
                + (" " + I.say(lang, "elect.recount", "&mdash; a recount was requested")
                   if r.get("recount") and not every else "") + "</div>")
    return ('<details class="vac elnfl"><summary>' + head + "</summary>"
            + (f'<p class="note" style="margin-top:8px">{why}</p>' if why else "")
            + '<div class="grid">' + "".join(where(k, r) for k, r in nf) + "</div></details>")


def elect_sortname(e, by_id):
    """(surname, given name) to list a member-elect by: the roster's own
    "Surname, Given" where the file links them to a member it holds -- so
    Rebecca Perkins Kwoka is under P, as on the Legislators tab -- and
    otherwise the name's last word, a suffix aside ("William Lawrence,
    Jr." is a Lawrence)."""
    row = by_id.get(str(e.get("id") or "")) if e.get("id") else None
    if row and "," in str(row.get("name") or ""):
        last, first = str(row["name"]).split(",", 1)
        return last.strip().lower(), first.strip().lower()
    words = NAME_SUFFIX.sub("", str(e.get("n") or "").strip()).split()
    return (words[-1].lower(), " ".join(words[:-1]).lower()) if words else ("", "")


def elect_not_final(rows, lang="en"):
    """The districts of a list of races whose results are not final, said
    once: "Result not final in District 13 (2 seats) and District 14 -- a
    recount was requested", or "" where every result is final."""
    nf = [(d, r) for d, r in rows if r.get("not_final")]
    if not nf:
        return ""
    where = [I.say(lang, "off.district", "District {d}", d=E(d))
             + (" (" + I.say(lang, "off.seats", "{n} seats", n=r["not_final"]) + ")"
                if r["not_final"] > 1 else "") for d, r in nf]
    listed = (where[0] if len(where) == 1 else
              I.say(lang, "lf.and", "{a} and {b}", a=", ".join(where[:-1]), b=where[-1]))
    return ('<p class="elnf"><b>' + I.say(lang, "elect.not_final", "Result not final") + "</b> "
            + I.say(lang, "elect.nf_in", "in {where}", where=listed) + _recount(nf, lang) + "</p>")


def _recount(nf, lang="en"):
    """" -- a recount was requested", or "... in each" of several districts,
    where every one of them had one asked for; "" otherwise."""
    if not all(r.get("recount") for _d, r in nf):
        return ""
    return " " + (I.say(lang, "elect.recount", "&mdash; a recount was requested") if len(nf) == 1
                  else I.say(lang, "elect.recounts", "&mdash; a recount was requested in each"))


def elect_nf_count(rows, lang="en"):
    """A chamber's results not final, counted, for the view by name, which
    lists people and so cannot show a seat with nobody in it: "Result not
    final for 19 seats in 16 districts -- a recount was requested in each.
    Who won the seats lists them, and By county." "" where all are final."""
    nf = [(d, r) for d, r in rows if r.get("not_final")]
    if not nf:
        return ""
    n, d = sum(r["not_final"] for _d, r in nf), len(nf)
    count = (I.say(lang, "elect.nf_one", "for {n} seat", n=n) if n == 1 else
             I.say(lang, "elect.nf_seats_one", "for {n} seats in one district", n=n) if d == 1 else
             I.say(lang, "elect.nf_seats", "for {n} seats in {d} districts", n=n, d=d))
    return ('<p class="elnf"><b>' + I.say(lang, "elect.not_final", "Result not final") + "</b> "
            + count + _recount(nf, lang) + ". "
            + I.say(lang, "elect.nf_named", "Who won the seats lists them, and By county.") + "</p>")


def members_elect(elect, today, lang="en", people=None, towns=None):
    """THE MEMBERS-ELECT TAB (the person's decisions of 16 October 2026):
    who November's election sent to the General Court, for the weeks before
    they sit -- the approved sentence; then each chamber's seats by party
    and the seats not final, listed (elect_totals); then the members-elect
    two ways, as the Legislators tab lists its members (the owner's walks of
    7 and 8 November 2026): by last name, in a column for each party; and by
    county, both chambers, each county's results not final named in it. A
    view by district, each race whole, went on the walk of 8 November as
    the other two's double. Drawn from site/members_elect.json (`elect`,
    from build_members_elect.for_pages) and never beside the roster, which
    stays on the Legislators tab as who holds each seat; so no "Serving
    now" here. Over the lists a search box and three filters (status, party,
    chamber: elect_controls), written hidden for the script to show, over
    items that carry what they read; `towns` ({race key: [towns]}) lets a
    town's name find its members-elect. `people`, the sitting and former members, gives a linked
    member's surname for the order, the chamber they sit or sat in for
    their word, and the county the Legislators tab lists each Senate
    district under; nothing of theirs is drawn. No contact detail: a
    member-elect holds no office yet. "" where there is no file, and the
    tab is then not drawn at all.

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
    count_words = I.say(lang, "off.sos_count", "the Secretary of State&rsquo;s count")
    by = (f'<a href="{E(src)}" rel="noopener">{count_words}</a>' if src else count_words)
    tab = ('<a href="officials.html#legislators">'
           + I.say(lang, "off.leg_tab", "Legislators tab") + "</a>")
    intro = ('<div class="ofintro"><p class="ofwhy">'
             + I.say(lang, "off.elect_intro", "Elected {day}, by {by}. They take office on "
                     "{takes}; until then the {tab} lists who holds each seat.",
                     day=E(date_words(election, "full", lang)), by=by,
                     takes=E(date_words(takes, "full", lang)), tab=tab)
             + "</p></div>")

    # Each race once, in the file's order: the Senate by district, then the
    # House by county and district -- [(key, district, race)].
    senate, house = [], {}
    for k in sorted(races, key=race_order):
        m = KEY_RE.match(k)
        if m.group(3):
            senate.append((k, m.group(3), races[k]))
        else:
            house.setdefault(m.group(1), []).append((k, m.group(2), races[k]))
    by_id = {str(p.get("id")): p for p in people or [] if p.get("id")}

    def item(tag, cls, e, k):
        """One member-elect in a list: the chip, then the word beside it; the
        item "elown" where a saved town's "Your rep" may mark it, as
        components.elect_race's (find.js, ytMark). It carries what the
        search and the filters read (elect_attrs), and says nothing more
        to a page read without the script."""
        own = bool(e.get("own") and e.get("id") and e.get("s"))
        names = " ".join(c for c in (cls, "elown" if own else "") if c)
        attrs = elect_attrs(e, k, by_id, (towns or {}).get(k))
        return ((f'<{tag} class="{names}"{attrs}>' if names else f"<{tag}{attrs}>")
                + elect_chip(e, k, lang) + elect_word(e, k, by_id, lang) + f"</{tag}>")

    def won(rows):
        return [(k, e) for k, _d, r in rows for e in r.get("elected") or []]

    sen_name, house_name = I.say(lang, "comp.senate", "Senate"), I.say(lang, "comp.house", "House")
    # BY LAST NAME: each chamber on its own, a column for each party, largest
    # first, A to Z by surname and then by given name, as alpha_block lists
    # the roster. The chamber's heading carries the address the tab's
    # chambers had (/officials#of-elect-house), in the pane a reader is shown
    # first, so a link made to it still lands on the House's members-elect.
    def by_name(rows, heading, hid):
        ms = won(rows)
        groups = {}
        for k, e in ms:
            groups.setdefault(elect_party(e), []).append((k, e))
        cols = []
        # A tie goes to a party, then to the cross-nominated, then to no
        # party printed.
        for code, pm in sorted(groups.items(),
                               key=lambda kv: (-len(kv[1]), {"+": 1, "": 2}.get(kv[0], 0), kv[0])):
            pm.sort(key=lambda ke: (elect_sortname(ke[1], by_id), race_order(ke[0])))
            # Why a group is "More than one party" (the owner's walk of dry run 8,
            # 8 November 2026), said as the results print it.
            why = ('<p class="note">' + I.say(
                lang, "elect.party_more_why", "They were on the ballot with two party labels, "
                "as the Secretary of State&rsquo;s results print them; the site will show the "
                "party the General Court records for them once it does.") + "</p>"
                   if code == "+" else "")
            cols.append(f'<section class="pcol"><h3>{E(elect_party_words(code, len(pm), lang))} '
                        f'&mdash; {len(pm)}</h3>{why}<ol class="seatlist rlist elroll">'
                        + "".join(item("li", "seatrow", e, k) for k, e in pm) + "</ol></section>")
        return (f'<h2 id="{hid}">{heading} &mdash; {len(ms)}</h2>'
                + elect_nf_count([(d, r) for _k, d, r in rows], lang)
                + ('<div class="partycols">' + "".join(cols) + "</div>" if cols else ""))

    by_last =((by_name(senate, sen_name, "of-elect-senate") if senate else "")
               + (by_name([x for rows in house.values() for x in rows], house_name, "of-elect-house")
                  if house else ""))
    # BY COUNTY, BOTH CHAMBERS, as the Legislators tab's By county lists its
    # members (build_pages' roster(), the walk of 8 November 2026): each
    # county shut until asked for, the counties A to Z, the members by
    # district and then by name, a county's results not final counted in its
    # summary and named inside it. A House race names its county. A Senate
    # race names a district and no county, and a district crosses county
    # lines, so its members-elect are under the county the Legislators tab
    # lists that district under -- the roster's county for the senator who
    # holds it now -- and under "Not on file", as there, where nobody does.
    # The chambers' headings carry the addresses By district's had
    # (/officials#of-eld-house), which land here now that it has gone.
    sd_county = {str(p.get("district") or ""): p.get("county") for p in people or []
                 if str(p.get("chamber") or "")[:1] == "S" and not p.get("former") and p.get("county")}
    not_on_file = I.say(lang, "lf.not_on_file", "Not on file")

    def by_county(groups, heading, hid):
        """[(county, [(key, district, race)])] -> the chamber's counties."""
        parts = []
        for c, rows in sorted(groups.items(), key=lambda cr: (cr[0] == "", cr[0])):
            ms = sorted(((d, k, e) for k, d, r in rows for e in r.get("elected") or []),
                        key=lambda x: (int(x[0]), elect_sortname(x[2], by_id)))
            nf = sum(r.get("not_final") or 0 for _k, _d, r in rows)
            parts.append(
                f'<details class="cgrp"><summary><span>{E(c or not_on_file)}</span>'
                f'<span class="ccount">{len(ms)}</span>'
                + ('<span class="ccnf">' + I.say(lang, "elect.n_not_final", "{n} not final", n=nf)
                   + "</span>" if nf else "")
                + '<span class="caret">&#9656;</span></summary><div class="grid elroll">'
                + "".join(item("div", "mem", e, k) for _d, k, e in ms) + "</div>"
                + elect_not_final([(d, r) for _k, d, r in rows], lang) + "</details>")
        n_ = sum(len(won(rows)) for rows in groups.values())
        return f'<h2 id="{hid}">{heading} &mdash; {n_}</h2>' + "".join(parts)

    county_parts = []
    if senate:
        sen_groups = {}
        for k, d, r in senate:
            # A district nobody holds goes last, under "Not on file".
            sen_groups.setdefault(sd_county.get(d) or "", []).append((k, d, r))
        county_parts.append(by_county(sen_groups, sen_name, "of-eld-senate"))
    if house:
        county_parts.append(by_county(house, house_name, "of-eld-house"))
    n = elect_count(elect)
    views = f"""<section class="roster elroster">
<div class="rtabs" role="tablist" aria-label="{I.say(lang, "elect.arrange", "How to arrange the members-elect")}" hidden>
  <button type="button" role="tab" id="tab-elast" data-pane="pane-elast"
    aria-controls="pane-elast" aria-selected="true">{I.say(lang, "roster.by_last", "By last name")}</button>
  <button type="button" role="tab" id="tab-ecounty" data-pane="pane-ecounty"
    aria-controls="pane-ecounty" aria-selected="false">{I.say(lang, "roster.by_county", "By county")}</button>
</div>
<div class="rpane" id="pane-elast" role="tabpanel" aria-labelledby="tab-elast">
<p class="src">{(I.say(lang, "elect.all_one", "{n} member-elect, by surname.", n=n) if n == 1 else
                 I.say(lang, "elect.all", "All {n} members-elect, by surname, each chamber on its own.",
                       n=f"{n:,}"))}</p>
{by_last}
</div>
<div class="rpane" id="pane-ecounty" role="tabpanel" aria-labelledby="tab-ecounty">
{"".join(county_parts)}
</div>
</section>"""
    return (f'<div class="elpane" data-elect{until_attrs(takes, today)}>' + intro
            + elect_totals(races, lang, by_id)
            + elect_controls([(k, e) for k, r in races.items() for e in r.get("elected") or []],
                             by_id, lang)
            + views + ELECT_FILTER_JS + "</div>")


# THE SEARCH AND THE FILTERS (the owner, 12 November 2026: "a search function
# for the member's elect page and ... sort by returning, incumbent, new, and
# new chamber"). Written into the page hidden and shown by its script, as the
# view strip is, so a page read without the script is the plain lists and no
# controls that do nothing. The boxes are the site's .bfilt row (a member's
# Votes tab, a committee's calendar); the search matches as the site's header
# search does (find.js) -- every word typed must be in the person's name, in
# the name on their own page, county, district or towns, accents folded; a
# word under five letters must start a word; rep, sen and their long forms
# are a title and left out of the match; a number names a district ("merr 5"
# is Merrimack 5 and not 15, "ward 5" is the ward) -- and the three selects
# choose the status elect_status gives, the party the roster lists them
# under, and the chamber. Each item carries what is read, as data-st,
# data-p, data-ch and data-hay (name | district words | towns); matching is
# by those and never by a name alone.
def elect_attrs(e, key, by_id, towns=None):
    """The data-* an item carries for the filter: its status, its party
    column's letter ("-" for none), its chamber, and the words a search
    reads -- "name | district words | towns" in lower case with accents off.
    The name is the ballot's and, where the file links the person to a
    member, the record's too, first name first (the name their own page
    shows)."""
    import unicodedata
    m = KEY_RE.match(key)
    st = elect_kind(e, key, by_id)
    where = (f"senate district {m.group(3)} senate {m.group(3)} sd{m.group(3)} sd {m.group(3)}"
             if m.group(3) else
             f"{m.group(1)} district {m.group(2)} {m.group(1)} {m.group(2)}")
    name = str(e.get("n") or "")
    row = by_id.get(str(e.get("id"))) if e.get("id") else None
    if row and str(row.get("name") or "").strip():
        last, _, first = str(row["name"]).partition(",")
        rec = f"{first.strip()} {last.strip()}".strip()
        if rec.lower() != name.lower():
            name += " " + rec
    hay = unicodedata.normalize("NFKD", " | ".join([name, where, " ".join(towns or [])]))
    hay = "".join(c for c in hay if not unicodedata.combining(c)).lower()
    return (f' data-st="{st}" data-p="{E(elect_party(e) or "-")}" '
            f'data-ch="{"S" if m.group(3) else "H"}" data-hay="{E(hay)}"')


def elect_controls(won, by_id, lang="en"):
    """The search box and the three selects, written hidden, over the lists.
    `won` is [(race key, member-elect)]. Each option says how many it holds,
    plainly; the script says how many are shown."""
    if not won:
        return ""
    st, party, chamber = {}, {}, {}
    for k, e in won:
        w = elect_kind(e, k, by_id)
        if w:
            st[w] = st.get(w, 0) + 1
        c = elect_party(e) or "-"
        party[c] = party.get(c, 0) + 1
        ch = "S" if KEY_RE.match(k).group(3) else "H"
        chamber[ch] = chamber.get(ch, 0) + 1
    n = len(won)

    def opts(first, rows):
        return (f'<option value="">{E(first)} ({n:,})</option>'
                + "".join(f'<option value="{E(v)}">{E(w)} ({c:,})</option>' for v, w, c in rows))
    st_rows = [(v, kind_words(v, lang), st[v]) for v in STATUSES if st.get(v)]
    party_rows = [(c, elect_party_words("" if c == "-" else c, party[c], lang), party[c])
                  for c in sorted(party, key=lambda c: (-party[c], {"+": 1, "-": 2}.get(c, 0), c))]
    ch_rows = [(c, I.say(lang, "comp.senate", "Senate") if c == "S" else
                I.say(lang, "comp.house", "House"), chamber[c]) for c in ("S", "H") if chamber.get(c)]
    return (f'<div class="bfilt elfilter" role="search" hidden data-n="{n}" '
            f'data-some="{E(I.say(lang, "elect.f_some", "Showing {n} of {m} members-elect", n="{n}", m="{m}"))}" '
            f'data-none="{E(I.say(lang, "elect.f_none", "No member-elect matches that."))}">'
            f'<label>{I.say(lang, "elect.f_search", "Search")}'
            f'<input type="search" class="elq" autocomplete="off" '
            f'placeholder="{E(I.say(lang, "elect.f_ph", "Name, town or district"))}"></label>'
            f'<label>{I.say(lang, "elect.f_status", "Status")}'
            f'<select class="elst">{opts(I.say(lang, "elect.f_all", "All"), st_rows)}</select></label>'
            f'<label>{I.say(lang, "elect.f_party", "Party")}'
            f'<select class="elpa">{opts(I.say(lang, "elect.f_all", "All"), party_rows)}</select></label>'
            f'<label>{I.say(lang, "elect.f_chamber", "Chamber")}'
            f'<select class="elch">{opts(I.say(lang, "elect.f_both", "Both"), ch_rows)}</select></label>'
            f'<p class="count elcount" role="status" aria-live="polite"></p></div>')


ELECT_FILTER_JS = """<script>
(function(){
// electMatch is the whole of the matching, so a test can run it alone: an
// item {st, p, ch, hay} against what was typed and chosen; every word typed
// must be in hay ("names | district words | towns"), accents folded. As
// find.js does: a word under five letters starts a word, and rep, sen and
// the long forms are a title, left out (a member's page may say Rep. of one
// who is a senator-elect). A number is a district: with
// the word before it ("merr 5", "sd 8", "senate district 8") it is that
// district's number, alone it is any district's, after "ward" it is a ward
// of a town; a word with a digit in it ("sd8") is a whole word.
function fold(s){s=String(s==null?"":s).toLowerCase();
  return s.normalize?s.normalize("NFD").replace(/[\\u0300-\\u036f]/g,""):s;}
var TITLE={rep:1,"rep.":1,representative:1,sen:1,"sen.":1,senator:1};
function startsWord(h,w){
  if(w.length>=5)return h.indexOf(w)>=0;
  for(var i=h.indexOf(w);i>=0;i=h.indexOf(w,i+1))
    if(!i||!/[a-z0-9]/.test(h.charAt(i-1)))return true;
  return false;
}
function pairAt(t,pre,n,exact){
  for(var i=0;i+1<t.length;i++)
    if((exact?t[i]===pre:t[i].indexOf(pre)===0)&&t[i+1]===n)return true;
  return false;
}
function electMatch(it,q,st,p,ch){
  if(st&&it.st!==st)return false;
  if(p&&it.p!==p)return false;
  if(ch&&it.ch!==ch)return false;
  var raw=fold(q).split(/\\s+/).filter(Boolean),w=[];
  for(var i=0;i<raw.length;i++)
    if(!Object.prototype.hasOwnProperty.call(TITLE,raw[i]))w.push(raw[i]);
  var parts=it.hay.split(" | "),
      dist=(parts.length>2?parts[1]:it.hay).split(" "),
      town=(parts.length>2?parts.slice(2).join(" "):it.hay).split(" ");
  for(var j=0;j<w.length;j++){
    var x=w[j];
    if(/^[0-9]+$/.test(x)){
      var b=j&&!/[0-9]/.test(w[j-1])?w[j-1]:"";
      if(b==="ward"){if(!pairAt(town,"ward",x,true))return false;}
      else if(!pairAt(dist,b||"district",x,!b))return false;
    }else if(/[0-9]/.test(x)){
      if(dist.indexOf(x)<0)return false;
    }else if(!startsWord(it.hay,x))return false;
  }
  return true;
}
if(typeof window!=="undefined")window.electMatch=electMatch;
var bar=document.querySelector(".elfilter");
if(!bar)return;
var panel=bar.parentNode, box=bar.querySelector(".elq"), say=bar.querySelector(".elcount");
var sels={st:bar.querySelector(".elst"),p:bar.querySelector(".elpa"),ch:bar.querySelector(".elch")};
// Every member-elect is in both views; the counts are read from the first.
var rows=[].slice.call(panel.querySelectorAll("[data-st]")).map(function(el){
  return {el:el,st:el.dataset.st,p:el.dataset.p,ch:el.dataset.ch,hay:el.dataset.hay||""};});
var once=rows.filter(function(r){return !!r.el.closest("#pane-elast");});
// A heading's count and a county's: kept as written, and drawn as what is
// shown while a search or a filter is on.
var heads=[].slice.call(panel.querySelectorAll("h2[id^=of-el],.pcol h3")).map(function(h){
  var m=/^(.*?\\s\\u2014\\s)([0-9,]+)$/.exec(h.textContent);
  return m?{h:h,pre:m[1],all:m[2],col:h.parentNode.className==="pcol"?h.parentNode:null,
            s:/senate/.test(h.id||"")}:null;}).filter(Boolean);
var cgrps=[].slice.call(panel.querySelectorAll("details.cgrp")).map(function(d){
  var n=d.querySelector(".ccount");
  return {d:d,n:n,all:n?n.textContent:"",open:d.open};});
function seen(box){return box.querySelectorAll("[data-st]:not(.elout)").length;}
function apply(){
  var q=box.value,st=sels.st.value,p=sels.p.value,ch=sels.ch.value,
      on=!!(q.trim()||st||p||ch),n=0;
  rows.forEach(function(r){r.el.classList.toggle("elout",!electMatch(r,q,st,p,ch));});
  once.forEach(function(r){if(!r.el.classList.contains("elout"))n++;});
  heads.forEach(function(x){
    var c=x.col?seen(x.col):once.filter(function(r){
      return !r.el.classList.contains("elout")&&(r.ch==="S")===x.s;}).length;
    if(x.col)x.col.classList.toggle("elout",!c);
    x.h.textContent=on?x.pre+c:x.pre+x.all;
  });
  cgrps.forEach(function(g){
    var c=seen(g.d);
    g.d.classList.toggle("elout",!c);
    if(g.n)g.n.textContent=on?c:g.all;
    g.d.open=on?c>0:g.open;
  });
  say.textContent=!on?"":n?bar.dataset.some.replace("{n}",n).replace("{m}",bar.dataset.n)
    :bar.dataset.none;
}
["input","change"].forEach(function(t){
  [box,sels.st,sels.p,sels.ch].forEach(function(c){c.addEventListener(t,apply);});});
bar.hidden=false;
})();
</script>"""


def elect_count(elect):
    """How many members-elect the file names, for the tab's label: the
    winners drawn, not the seats, so a race not final counts none."""
    return sum(len(r.get("elected") or []) for r in ((elect or {}).get("races") or {}).values())


def _long(iso, lang="en"):
    """"September 9, 2026", the site's long date."""
    import components
    return components.date_words(str(iso or "")[:10], "full", lang)
