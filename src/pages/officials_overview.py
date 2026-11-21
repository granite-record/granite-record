#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.2
"""
The Officials overview: the page the Officials section opens on (the owner's
choice of draft A, 21 November 2026; the mock is the helpers' draft-a.html).
Who holds power in New Hampshire, answered at a glance -- the Legislature as
seat bars, then a block for each branch (Executive, Federal delegation,
Judicial, County, State agencies, Elections), each with its people as the
site's one person chip and a link to its tab -- with the district map beside
the Legislature and a "Find your town" box at the top, whose list and panel
are find.js's (the town panel, which My Town became that day).

    import officials_overview as OV
    OV.overview(lang, comp=C, elect=elect, officers=officers, legs=legs,
                off=off, today=today, facts=chrome.row_facts(),
                elections=OV.elections_on_file(collected))

Nothing here is fetched and nothing is written. Every number is counted from
the build's own inputs, never typed: the chambers from home.json's
composition, the members-elect from site/members_elect.json (as
build_members_elect.for_pages reads it), the presiding officers from
officers.json, every other office from corrections/officials.json as
build_members_elect.read_officials gives it on the build's day, and the
elections from the results files on disk.

THE INCOMING LEGISLATURE LEADS BETWEEN THE ELECTION AND THE DAY IT SITS (the
owner, 21 November 2026: "The overview can switch to showing the new
legislature numbers after election results come in ... but make it clear
that it's the incoming class of legislators", and "There should be a smaller
summary of the previous legislative distribution compared to the incoming
classes numbers"). leads_incoming() decides it from the data and the build's
day alone: while there is a members-elect file with races in it and its
take-office day has not come, the Legislature's lead bars are the incoming
House and Senate, headed as the incoming legislature with the day it takes
office, and the chambers as they sit follow on a thin bar each. Outside that
window the chambers as they sit lead, and there is no incoming block. The
incoming block carries data-elect and retires by the reader's own clock on
the day, as every member-elect block does (components.until_attrs).

AN OFFICE WON ON 3 NOVEMBER (the owner, 21 November 2026: "Governor-elect
makes sense along with Executive Councilor-elect"). Where the hand file's
record of an office has an `elect` -- a successor not yet in office -- the
successor is drawn under the holder as "<office>-elect" with the day they
take office; where it has a `reelected` record naming the holder, the holder
is said to have been re-elected on its day. Nothing is said where the file
says neither: no Governor-elect is ever made up (office_next).
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import re

import i18n as I
import officials_tabs as OT
from components import UNTIL_DAY, date_words, until_attrs
from parts import weblink

E = OT.E


def leads_incoming(elect, today):
    """Whether the incoming legislature leads the overview: a members-elect
    file with races in it, whose take-office day is a day and has not come
    by `today` (the build's day, "YYYY-MM-DD" or a date)."""
    races = (elect or {}).get("races") or {}
    takes = str((elect or {}).get("takes_office") or "")[:10]
    day = str(today or "")[:10]
    return bool(races) and bool(UNTIL_DAY.fullmatch(takes)) and bool(UNTIL_DAY.fullmatch(day)) \
        and day < takes


# The office as a successor is titled before they take it, in the site's
# spelling of the office ("Executive Councilor", as the Learn pages write it).
# Written out a call each, so the catalog's checks read every key and its
# English from the source.
def elect_title(office, lang="en"):
    """"Executive Councilor-elect", in `lang`."""
    if office == "governor":
        return I.say(lang, "of.ov.elect.governor", "Governor-elect")
    if office == "council":
        return I.say(lang, "of.ov.elect.council", "Executive Councilor-elect")
    if office == "us_senate":
        return I.say(lang, "of.ov.elect.us_senate", "US Senator-elect")
    return I.say(lang, "of.ov.elect.us_house", "US Representative-elect")


def office_next(rec, office, lang="en"):
    """(what to add beside the holder, a row to draw under them) for one
    office's record: "Re-elected November 3, 2026" where its `reelected`
    names the holder; the successor's own row, "<office>-elect; takes office
    <day>", where its `elect` names somebody else; ("", "") where it says
    neither. A re-election with no day, or naming somebody other than the
    holder, says nothing: the page says only what the record says."""
    rec = rec or {}
    holder = (rec.get("name") or "").strip()
    again = rec.get("reelected")
    beside = ""
    if isinstance(again, dict) and holder and (again.get("name") or "").strip() == holder \
            and UNTIL_DAY.fullmatch(str(again.get("election") or "")[:10]):
        beside = I.say(lang, "of.ov.reelected", "Re-elected {day}",
                       day=E(date_words(again["election"], "full", lang)))
    nxt = rec.get("elect")
    row = ""
    if isinstance(nxt, dict):
        name = (nxt.get("name") or "").strip()
        takes = str(nxt.get("takes_office") or "")[:10]
        if name and name != holder and UNTIL_DAY.fullmatch(takes):
            row = (f'<li class="ovnext"{until_attrs(takes, None)}>'
                   + OT.person(name, nxt.get("party") if rec.get("party") else "")
                   + '<span class="k">' + I.say(lang, "of.ov.elect_takes", "{office}; takes office {day}",
                                                office=E(elect_title(office, lang)),
                                                day=E(date_words(takes, "full", lang)))
                   + "</span></li>")
    return beside, row


def holder_row(rec, office, seat="", lang="en"):
    """One office's holder as the overview lists them: the chip, the seat
    beside it and anything the record adds (office_next), then the
    successor's row. "" for a record with no name."""
    name = (rec.get("name") or "").strip()
    if not name:
        return ""
    beside, row = office_next(rec, office, lang)
    k = " &middot; ".join(x for x in (E(seat) if seat else "", beside) if x)
    return (f'<li>{OT.person(name, rec.get("party"))}'
            + (f'<span class="k">{k}</span>' if k else "") + "</li>" + row)


def _filled(x, lang):
    """"382 of 400 seats filled, 18 vacant", as build_pages.static_bar says it."""
    if x.get("vacant") == 1:
        return I.say(lang, "comp.filled_vacant_one", "{sitting} of {seats} seats filled, {vacant} "
                     "vacant", sitting=x["sitting"], seats=x["seats"], vacant=x["vacant"])
    if x.get("vacant"):
        return I.say(lang, "comp.filled_vacant", "{sitting} of {seats} seats filled, {vacant} "
                     "vacant", sitting=x["sitting"], seats=x["seats"], vacant=x["vacant"])
    return I.say(lang, "comp.filled", "{sitting} of {seats} seats filled",
                 sitting=x.get("sitting"), seats=x.get("seats"))


def _chamber_name(ch, lang):
    return I.say(lang, "comp.senate", "Senate") if ch == "S" else I.say(lang, "comp.house", "House")


def sitting_bars(comp, lang="en"):
    """Both chambers as they sit, a full bar each, Senate first."""
    out = []
    for ch in ("S", "H"):
        x = (comp or {}).get(ch)
        groups = OT.sitting_groups(x, lang)
        if groups:
            out.append(OT.comp_block(_chamber_name(ch, lang), _filled(x, lang), groups,
                                     x.get("seats"), lang))
    return f'<div class="ovch">{"".join(out)}</div>' if out else ""


def incoming_bars(elect, lang="en"):
    """Both incoming chambers, a full bar each, Senate first."""
    races = (elect or {}).get("races") or {}
    out = []
    for ch in ("S", "H"):
        got = OT.elect_chamber(races, ch, lang)
        if not got:
            continue
        said = (I.say(lang, "elect.won_nf", "{won} of {seats} seats elected, {nf} not final",
                      won=len(got["won"]), seats=got["seats"], nf=got["nf"]) if got["nf"] else
                I.say(lang, "elect.won", "{won} of {seats} seats elected", won=len(got["won"]),
                      seats=got["seats"]))
        out.append(OT.comp_block(_chamber_name(ch, lang), said, got["groups"], got["seats"], lang))
    return f'<div class="ovch">{"".join(out)}</div>' if out else ""


def presiding_chips(officers, legs, today, lang="en"):
    """The presiding officers on the build's day, as the Legislators tab
    draws them (officials_tabs.presiding), without its section."""
    html = OT.presiding(officers, legs, today, lang)
    m = re.search(r'<div class="ofchips">(.*)</div></section>$', html, re.S)
    return m.group(1) if m else ""


def legislature(comp, elect, officers, legs, today, lang="en", facts=None):
    """The Legislature block: the incoming chambers, then the chambers as they
    sit, smaller, while the incoming legislature leads (leads_incoming); the
    chambers as they sit alone otherwise; the presiding officers; and the
    ways to the lists.

    ONE MARKUP FOR WHO SITS, IN OR OUT OF THE WINDOW. The chambers as they
    sit are the same block either way (.ovsitting, full bars and legends);
    the incoming block before them, and the "Serving until then" over them,
    carry data-elect and retire on the day, and app.css draws the sitting
    block small -- thin bars and one short line a chamber -- only while the
    incoming block is shown. So the page with the members-elect, its
    data-elect taken out, is the page without them, as every page's must be
    (_elect_pages_never_sitting), and a page read on the day by a reader's
    clock goes back to the sitting chambers at full size on its own."""
    facts = facts or {}
    incoming = leads_incoming(elect, today)
    parts = []
    if incoming:
        takes, election = elect["takes_office"], elect.get("election")
        until = until_attrs(takes, today)
        parts.append(
            f'<div class="ovincoming" data-elect{until}>'
            + '<h3 class="ovinh">' + I.say(lang, "of.ov.incoming", "The incoming legislature") + "</h3>"
            + '<p class="statemeta ovwhen">'
            + (I.say(lang, "of.ov.incoming_when", "Elected {election}; takes office {takes}.",
                     election=E(date_words(election, "full", lang)),
                     takes=E(date_words(takes, "full", lang)))
               if UNTIL_DAY.fullmatch(str(election or "")[:10]) else
               I.say(lang, "of.ov.incoming_takes", "Takes office {takes}.",
                     takes=E(date_words(takes, "full", lang))))
            + "</p>" + incoming_bars(elect, lang) + "</div>"
            + f'<h3 class="ovnowh" data-elect{until}>'
            + I.say(lang, "of.ov.sitting_until", "Serving until then") + "</h3>")
    bars = sitting_bars(comp, lang)
    if bars:
        parts.append(f'<div class="ovsitting">{bars}</div>')
    chips = presiding_chips(officers, legs, today, lang)
    if chips:
        parts.append('<h3>' + I.say(lang, "off.presiding", "Presiding Officers") + "</h3>"
                     f'<div class="ovpeople">{chips}</div>')
    more = [f'<a href="officials.html#legislators">'
            + I.say(lang, "of.ov.all_legislators", "All {n} legislators", n=f"{len(legs):,}") + "</a>"]
    if incoming:
        more.append('<a href="officials.html#members-elect" data-elect'
                    f'{until_attrs(elect["takes_office"], today)}>'
                    + I.say(lang, "nav.row.officials.members-elect", "Members-elect") + "</a>")
    if facts.get("former"):
        more.append('<a href="directory/former-legislators.html">'
                    + I.say(lang, "nav.row.officials.former", "Former members") + "</a>")
    return section("leg", I.say(lang, "of.ov.legislature", "Legislature"),
                   "officials.html#legislators",
                   "".join(parts) + f'<p class="ovmore">{"".join(more)}</p>')


def section(sid, title, href, inner, extra=""):
    """One block of the overview: a ruled heading that links its tab, then
    its contents. "" for a block with nothing in it."""
    if not inner:
        return ""
    head = f'<a href="{E(href)}">{E(title)}</a>' if href else E(title)
    return (f'<section class="ovsec ov{sid}{extra}" aria-labelledby="ov-{sid}">'
            f'<h2 id="ov-{sid}">{head}</h2>{inner}</section>')


def _more(href, words):
    return f'<p class="ovmore"><a href="{E(href)}">{words}</a></p>'


def executive(off, lang="en"):
    g = off.get("governor") or {}
    c = (off.get("council") or {}).get("districts") or {}
    parts = []
    gov = holder_row(g, "governor", "", lang)
    if gov:
        parts.append("<h3>" + I.say(lang, "off.governor", "Governor") + "</h3>"
                     f'<ul class="ovlist">{gov}</ul>')
    rows = "".join(holder_row(r, "council", I.say(lang, "off.district", "District {d}", d=d), lang)
                   for d, r in sorted(c.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0))
    if rows:
        parts.append("<h3>" + I.say(lang, "off.council", "Executive Council") + "</h3>"
                     f'<ul class="ovlist">{rows}</ul>')
    titles = (("secretary_of_state", I.say(lang, "off.sos", "Secretary of State")),
              ("treasurer", I.say(lang, "off.treasurer", "State Treasurer")),
              ("attorney_general", I.say(lang, "off.ag", "Attorney General")))
    others = "".join(f'<li>{OT.person(r["name"])}<span class="k">{E(t)}</span></li>'
                     for k, t in titles for r in [off.get(k) or {}] if (r.get("name") or "").strip())
    if others:
        parts.append("<h3>" + I.say(lang, "of.ov.other_officers", "Other state officers") + "</h3>"
                     f'<ul class="ovlist">{others}</ul>')
    if not parts:
        return ""
    n = OT.count(off, "executive")
    return section("exe", I.say(lang, "nav.row.officials.executive", "Executive"),
                   "officials.html#executive",
                   "".join(parts) + _more("officials.html#executive", I.say(
                       lang, "of.ov.all_in", "All {n} in {tab}", n=n,
                       tab=I.say(lang, "nav.row.officials.executive", "Executive"))))


def federal(off, lang="en"):
    seats = (off.get("us_senate") or {}).get("seats") or []
    house = (off.get("us_house") or {}).get("districts") or {}
    parts = []
    sen = "".join(holder_row(r, "us_senate", "", lang) for r in seats)
    if sen:
        parts.append("<h3>" + I.say(lang, "off.us_senate", "US Senate") + "</h3>"
                     f'<ul class="ovlist">{sen}</ul>')
    rep = "".join(holder_row(r, "us_house", I.say(lang, "off.district", "District {d}", d=d), lang)
                  for d, r in sorted(house.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0))
    if rep:
        parts.append("<h3>" + I.say(lang, "off.us_house", "US House") + "</h3>"
                     f'<ul class="ovlist">{rep}</ul>')
    if not parts:
        return ""
    return section("fed", I.say(lang, "of.ov.federal", "Federal delegation"), "officials.html#federal",
                   "".join(parts) + _more("officials.html#federal", I.say(
                       lang, "of.ov.phones", "Phone numbers and offices")))


def judicial(off, lang="en"):
    j = off.get("judicial") or {}
    sc, su, cc = (j.get("supreme_court") or {}, j.get("superior_court") or {},
                  j.get("circuit_court") or {})
    parts = []
    sup = "".join(f'<li>{OT.person(r["name"])}<span class="k">{OT.said(lang, "title", r.get("title"))}'
                  "</span></li>" for r in sc.get("justices") or [] if (r.get("name") or "").strip())
    if sup:
        parts.append("<h3>" + E(OT.said_text(lang, "court", sc.get("name"))
                                or I.say(lang, "off.supreme", "Supreme Court")) + "</h3>"
                     f'<ul class="ovlist">{sup}</ul>')
    names = [r for r in su.get("justices") or [] if (r.get("name") or "").strip()]
    chief = next((r for r in names if (r.get("title") or "") == "Chief Justice"), None)
    if names:
        rest = len(names) - (1 if chief else 0)
        parts.append("<h3>" + E(OT.said_text(lang, "court", su.get("name"))
                                or I.say(lang, "off.superior", "Superior Court")) + "</h3>"
                     + (f'<ul class="ovlist"><li>{OT.person(chief["name"])}<span class="k">'
                        f'{OT.said(lang, "title", "Chief Justice")}</span></li></ul>' if chief else "")
                     + '<p class="ovnote">'
                     + ((I.say(lang, "of.ov.other_justices_one", "and 1 other justice") if rest == 1 else
                         I.say(lang, "of.ov.other_justices", "and {n} other justices", n=rest))
                        if chief else
                        I.say(lang, "of.ov.justices", "{n} justices", n=rest)) + "</p>")
    judges = weblink(cc.get("judges_url"), I.say(lang, "off.court_page", "the court’s own page"))
    if judges:
        parts.append("<h3>" + E(OT.said_text(lang, "court", cc.get("name"))
                                or I.say(lang, "off.circuit", "Circuit Court")) + "</h3>"
                     + "<p>" + I.say(lang, "off.judges_on", "Its judges are listed on {judges}.",
                                     judges=judges) + "</p>")
    if not parts:
        return ""
    n = OT.count(off, "judicial")
    return section("jud", I.say(lang, "nav.row.officials.judicial", "Judicial"), "officials.html#judicial",
                   "".join(parts) + _more("officials.html#judicial", I.say(
                       lang, "of.ov.all_in", "All {n} in {tab}", n=n,
                       tab=I.say(lang, "nav.row.officials.judicial", "Judicial"))))


def county(off, lang="en"):
    """The counties: how many officers they elect, their commissioners by
    party on a bar with the roster's day stated (the owner, 21 November
    2026: "County commissioners stay on the overview, as drawn, with the
    roster's date stated"), each county by name, and how many of their
    offices change hands on the day the next roster's officers take office."""
    co = off.get("county") or {}
    counties = co.get("counties") or {}
    if not counties:
        return ""
    groups = {}
    nxt = {}
    for c in counties.values():
        for r in (c.get("commissioners") or {}).values():
            if not (r.get("name") or "").strip():
                continue
            p = str(r.get("party") or "").upper()
            k = p if OT.ONE_PARTY.match(p) else "both" if OT.BOTH.match(p) else ""
            groups[k] = groups.get(k, 0) + 1
        for r in [*(c.get("commissioners") or {}).values(),
                  *[c.get(k) or {} for k, _t in OT.COUNTY_OFFICES]]:
            e = r.get("elect")
            if isinstance(e, dict) and (e.get("name") or "").strip() \
                    and (e.get("name") or "").strip() != (r.get("name") or "").strip() \
                    and UNTIL_DAY.fullmatch(str(e.get("takes_office") or "")[:10]):
                nxt[e["takes_office"][:10]] = nxt.get(e["takes_office"][:10], 0) + 1
    total = sum(groups.values())
    words = {k: (OT.elect_party_words(k, n, lang) if k not in ("both", "") else
                 I.say(lang, "of.ov.both_parties", "Both parties&rsquo; nominations") if k == "both"
                 else OT.elect_party_words("", n, lang))
             for k, n in groups.items()}
    order = sorted((k for k in groups if k not in ("both", "")), key=lambda k: (-groups[k], k)) \
        + [k for k in ("both", "") if k in groups]
    segs = [(k, groups[k], words[k], "seg-" + k if k not in ("both", "") else "seg-V") for k in order]
    n_off = OT.count(off, "county")
    parts = ['<p>' + I.say(lang, "of.ov.county_lead", "{c} counties, {n} elected officers.",
                           c=len(counties), n=n_off) + "</p>"]
    if total:
        legend = "".join(f'<span><span class="pdot {c}"></span>{w} <b>{n}</b></span>'
                         for _k, n, w, c in segs)
        bar = "".join(f'<span class="pseg {c}" style="width:{100 * n / total:.4f}%" '
                      f'title="{re.sub(r"<[^>]+>", "", w)}: {n}"></span>' for _k, n, w, c in segs)
        parts.append('<div class="compline"><h3>' + I.say(lang, "of.ov.commissioners",
                                                         "County commissioners")
                     + f'</h3><span class="statemeta">{total}</span></div>'
                     f'<div class="pbar2">{bar}</div><div class="plegend">{legend}</div>')
        if co.get("as_of"):
            parts.append('<p class="ovnote">' + I.say(
                lang, "of.ov.roster_day", "As the Secretary of State&rsquo;s county roster of {day} "
                "lists them.", day=E(date_words(co["as_of"], "full", lang))) + "</p>")
    names = "".join(
        f'<li><a href="officials.html#of-county-{re.sub(r"[^a-z]+", "-", n.lower()).strip("-")}">'
        f'{E(n)}</a></li>' for n in sorted(counties))
    parts.append(f'<ul class="ovcols">{names}</ul>')
    for day, n in sorted(nxt.items()):
        parts.append(f'<p class="ovnote"{until_attrs(day, None)}>'
                     + (I.say(lang, "of.ov.county_next_one", "1 county office changes hands on {day}.",
                              day=E(date_words(day, "full", lang))) if n == 1 else
                        I.say(lang, "of.ov.county_next", "{n} county offices change hands on {day}.",
                              n=n, day=E(date_words(day, "full", lang))))
                     + "</p>")
    return section("cty", I.say(lang, "nav.row.officials.counties", "County"), "officials.html#counties",
                   "".join(parts) + _more("officials.html#counties", I.say(
                       lang, "of.ov.all_in", "All {n} in {tab}", n=n_off,
                       tab=I.say(lang, "nav.row.officials.counties", "County"))))


def agencies(off, lang="en"):
    """STATE AGENCIES, A BLOCK OF ITS OWN (the owner, 21 November 2026): the
    executive departments by name, each linked to its own site; who heads
    each is on the Executive tab."""
    deps = [r for r in (off.get("department_heads") or {}).get("departments") or []
            if (r.get("department") or "").strip()]
    if not deps:
        return ""
    rows = "".join(
        "<li>" + (weblink(r.get("official_url"), OT.said_text(lang, "dept", r["department"]))
                  or E(OT.said_text(lang, "dept", r["department"]))) + "</li>"
        for r in sorted(deps, key=lambda r: r["department"]))
    return section("age", I.say(lang, "of.ov.agencies", "State agencies"), "officials.html#of-departments",
                   '<p class="ovnote">' + I.say(lang, "of.ov.agencies_lead", "The executive departments; "
                                                "who heads each is under Executive.") + "</p>"
                   f'<ul class="ovcols">{rows}</ul>'
                   + _more("officials.html#of-departments", I.say(lang, "off.dept_heads",
                                                                  "Department Heads")))


def elections_on_file(collected):
    """[(election day, whether it has State Senate races)], newest first, of
    every results file under `collected`, as build_elections reads them (a
    page is built for each). [] where there are none."""
    import build_members_elect as BME
    out = []
    for p in sorted(Path(collected).glob("election_*.json")):
        if not BME.RESULTS_RE.match(p.name):
            continue
        try:
            doc = BME.read_results(p)
        except BME.Refused:
            continue
        out.append((doc["election"], any(str(k).startswith("S|") for k in doc.get("races") or {})))
    return sorted(out, reverse=True)


def elections(items, lang="en"):
    if not items:
        return ""
    links = "".join(
        f'<a href="elections/{E(day)}-general.html" hreflang="en">'
        + I.say(lang, "of.ov.general", "{year} general election", year=day[:4])
        + "<span>" + E(date_words(day, "full", lang))
        + ("" if senate else ". " + I.say(lang, "of.ov.house_only", "House races only"))
        + "</span></a>" for day, senate in items)
    return section("ele", I.say(lang, "nav.row.officials.elections", "Elections"), "elections/index.html",
                   "<p>" + I.say(lang, "of.ov.elections_lead", "Official results of each general "
                                 "election on file, race by race, from the Secretary of State.")
                   + f'</p><div class="ovyears">{links}</div>')


def town_box(lang="en"):
    """"Find your town": a box find.js makes a combobox whose list is the
    site's own (ytFindMount), written disabled for the script to enable --
    a page read without it has the list of every town and ward instead."""
    return (
        '<div class="ovtown" id="ovtown">'
        '<form class="ovtform" role="search" action="directory/towns.html">'
        '<label for="ovq" class="ovtl">' + I.say(lang, "off.find_town", "Find your town") + "</label>"
        '<div class="ovtrow"><div class="ovtbox">'
        f'<input id="ovq" type="search" autocomplete="off" placeholder="'
        + I.say(lang, "of.ov.town_ph", "Your town or city") + '" disabled></div>'
        '<button type="submit" class="ovgo" disabled>'
        + I.say(lang, "of.ov.show", "Show my officials") + "</button></div></form>"
        '<div class="ovyours" hidden><b></b><button type="button" class="ovgo" data-ytshow>'
        + I.say(lang, "of.ov.show", "Show my officials") + "</button>"
        '<button type="button" class="ytopen link">' + I.say(lang, "of.ov.change", "Change") + "</button></div>"
        "<noscript><p>" + I.say(lang, "of.ov.town_noscript", "Every town and ward has a page, listed in "
                                "<a href=\"directory/towns.html\">every town and ward</a>.") + "</p></noscript>"
        "</div>")


def map_block(lang="en"):
    return section(
        "map", I.say(lang, "of.map", "The Map"), "",
        '<p class="ovnote">' + I.say(lang, "of.ov.map_how", "Choose a district to see who represents it.")
        + '</p><div class="ofmapbox" id="ofmap"></div>'
        + '<noscript><p class="note">' + I.say(
            lang, "of.map_noscript", "The map needs JavaScript. Every town&rsquo;s districts\nare on its "
            "own page, listed in <a href=\"/directory/towns\">every town and\nward</a>.") + "</p></noscript>")


def overview(lang="en", comp=None, elect=None, officers=None, legs=(), off=None, today="",
             facts=None, elections_list=()):
    """The overview's markup, inside its panel."""
    off = off or {}
    today = str(today)[:10]
    grid = "".join([
        legislature(comp, elect, officers, list(legs), today, lang, facts),
        map_block(lang),
        executive(off, lang),
        federal(off, lang),
        judicial(off, lang),
        county(off, lang),
        agencies(off, lang),
        elections(list(elections_list) if (facts or {}).get("elections", True) else [], lang),
    ])
    return town_box(lang) + f'<div class="ovgrid">{grid}</div>'
