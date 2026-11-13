#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.31
"""
An address for every sitting legislator, and the sitemap entries for them.

    python3 src/pages/build_legislator_pages.py --site site

/legislator/joseph-guthrie-rock-15.html is this site's search page with one
member open -- the same app.js, the same cards, the same roll call table as a
bill's page, drawing site/legislators/<id>.json.

It was once a page rendered here in Python: its own markup, its own
stylesheet, its own vote table, and no site header at all. It looked unlike
every other page on the site because it was written by different code, which is
the same problem the bill pages had and was fixed the same way.

WHAT A MEMBER'S PAGE ANSWERS

Which bills they put their name to, prime and co-sponsored, filterable by term
and outcome; every roll call they are recorded in, filterable by how they voted;
the district they sit for and the towns in it, ward by ward where a city is
split between members. Between a general election and Organization Day, a
member the election sent back -- sitting or returning -- also has one line
saying so under their name, from site/members_elect.json alone (the person's
decisions of 16 October 2026); nobody else's page says anything about it.

Writes site/legislator/<slug>.html and appends them to sitemap.xml. Each page
names the member's feed in its head, on the test build_feeds writes it on.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import re
import unicodedata

import build_date
import shell as S
import structured as LD
from build_members_elect import for_pages as members_elect
from components import ELECT_KEY, elect_line
# A town page's slug and address, from the builder that writes them.
from build_town_pages import slug as town_slug, town_path

E = S.E


def person_slug(m):
    """A stable, readable address: "joseph-guthrie-rock-15".

    Name plus seat, because two members share a name often enough to matter --
    Sen. Pat Long and Rep. Patrick Long sit at the same time -- and a bare name
    would give one of them the other's page.
    """
    name = m.get("display_plain") or m.get("name") or ""
    if "," in name:
        last, first = [x.strip() for x in name.split(",", 1)]
        name = f"{first} {last}"
    name = re.sub(r"^(Rep\.|Sen\.)\s*", "", name).strip()
    seat = (m.get("district_label") or "").strip()
    if not seat:
        seat = f"{m.get('chamber','')}-{m.get('district','')}"
    raw = f"{name} {seat}"
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", raw.lower())).strip("-")


def describe(m, rec=None):
    """The sentence a search engine shows under the link. rec is the member's
    own JSON, whose service names each chamber of a page that joins two."""
    # THE SEAT ONCE. display_full already carries it -- "Rep. Aboul Khan (R -
    # Rock 30)" -- and the seat was appended again, so all 406 of these read
    # "(R - Rock 30) Rock 30." in a search result. The places come straight
    # after the name, because they are what a person searching a
    # representative's name is usually checking.
    who = m.get("display_full") or m.get("display") or m.get("name") or ""
    if not (m.get("display_full") or "") and m.get("district_label"):
        who = f"{who} ({m['district_label']})"
    body = "Senate" if m.get("chamber") == "S" else "House of Representatives"
    # Ward 2 before Ward 10, which the roster's own order does not give.
    towns = sorted(m.get("towns") or [],
                   key=lambda t: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", t)])
    # PAST TENSE FOR SOMEBODY WHO NO LONGER SERVES, and no towns: the roster
    # carries none for them, and the town map is today's, so "represents" would
    # be wrong twice over.
    #
    # The years are the record's rather than the career's -- roll calls here
    # begin in 1999, so somebody first sworn in before that appears from the
    # year the evidence starts. List the terms the record covers and leave the
    # wording plain: the case is rare enough that a sentence of hedging costs
    # the reader more than the imprecision does.
    #
    # EACH CHAMBER ITS OWN YEARS, where the page joins two (the deep walk of 6
    # November 2026). A member who sat in both and has left has one page, the
    # later chamber's, with every chamber's votes (build_site_v2.
    # former_movers), and the record's span under the page's chamber read
    # "Sen. Jeb Bradley (R - SD3) served in the New Hampshire Senate, 1999 to
    # 2024" of a senator whose 1999-2002 were in the House. The years are the
    # page's own "Votes on record" line's: member_links.service, years with a
    # roll call in that chamber.
    both = _chambers_served(rec)
    if m.get("former") and both:
        lead = f"{who} served in the New Hampshire {both}."
    elif m.get("former"):
        yrs = _served_years(m)
        lead = (f"{who} served in the New Hampshire {body}"
                + (f", {yrs}." if yrs else "."))
    elif towns:
        # "and 1 more" hides a name in the space it takes to say so.
        shown = towns if len(towns) <= 7 else towns[:6]
        more = len(towns) - len(shown)
        places = (", ".join(shown[:-1]) + " and " + shown[-1] if len(shown) > 1 and not more
                  else ", ".join(shown) + (f" and {more} more" if more else ""))
        lead = f"{who} represents {places} in the New Hampshire {body}."
    else:
        lead = f"{who}, New Hampshire {body}."
    text = (f"{lead} Bills sponsored and every recorded roll call vote, from the "
            "General Court's own records.")
    # A clip at a word, not a slice: [:300] would cut a word in half the day a
    # member represented enough towns to reach it.
    return S.clip(text, 300)


def _chambers_served(rec):
    """"House of Representatives, 1999 to 2002, and Senate, 2009 to 2024": each
    chamber of a page that joins two, in the order it was first sat in, with
    the years it has a recorded roll call (the member's own service, as
    member_links.service writes it: [{"chamber": "H", "spans": [[1999,
    2002]]}, ...]). "" for a page of one chamber, or none on record."""
    svc = [c for c in ((rec or {}).get("service") or [])
           if c.get("chamber") in ("H", "S") and c.get("spans")]
    if len({c["chamber"] for c in svc}) < 2:
        return ""
    def years(spans):
        # "1999 to 2002, 2009 to 2014 and 2017 to 2018": one "and", at the end.
        said = [str(a) if a == b else f"{a} to {b}" for a, b in spans]
        return said[0] if len(said) == 1 else ", ".join(said[:-1]) + " and " + said[-1]
    return ", and ".join(
        f"{'Senate' if c['chamber'] == 'S' else 'House of Representatives'}, {years(c['spans'])}"
        for c in svc)


def _served_years(m):
    """"2013 to 2026", the span of the RECORD this site holds for a member.

    The span of the RECORD, which is not always the span of the service: roll
    calls here begin in 1999 and bills in 1989, so somebody who took their seat
    in 1985 and left in 2002 appears from 1999. The wording stays plain: the
    case is rare enough that a sentence of hedging costs the reader more than
    the imprecision does. The one place it is still worth avoiding is
    structured data, which asserts a startDate as fact with no prose around
    it; structured.person says so.

    One year where both ends fall in it, because "2026 to 2026" reads as a
    fault rather than as a fact.
    """
    s = m.get("served") or {}
    a, b = str(s.get("first") or "")[-4:], str(s.get("last") or "")[-4:]
    if not (a.isdigit() and b.isdigit()):
        return ""
    return a if a == b else f"{a} to {b}"


def heading(m):
    """The member's name as their own page heads it, and as its title and
    link card give it: "Former Rep. Michael Gunski (R - Hills 6)" for somebody
    who has left.

    THE WORD JOINS THE HONORIFIC, as the person settled it in September: a
    legislator who has left is written "Former Rep. David Smith", in the name
    itself and never as a chip, badge or pill beside it, on their own page and
    in search results -- and nowhere else, so a roll call, a sponsor list or a
    committee roster names them exactly as it names a sitting member, and
    nothing says why they left. The honorific is the record's own, the office
    they last held under it. A name with no honorific ("Member #377204") is
    left as it is, and the page's line under it keeps saying "Former member".
    app.js's formerName heads the page the same way.
    """
    who = m.get("display_full") or m.get("display") or m.get("name") or ""
    return f"Former {who}" if m.get("former") and re.match(r"(Rep|Sen)\. ", who) else who


# The honorific in full, as the roster's own title field gives it.
HONORIFIC_FULL = {"Rep.": "Representative", "Sen.": "Senator"}


def head_name(m):
    """The heading at the top of the member's own page: heading() with the
    honorific in full -- "Representative James Spillane (R - Rock 2)",
    "Senator Sharon Carson (R - SD14)", "Former Representative Michael
    Gunski (R - Hills 6)" -- as the person asked on 9 October 2026 ("Member
    pages should list their title along with their name at the top like
    Senator Sharon Carson or Representative James Spillane"). app.js's
    fullTitle draws the page's heading the same way. The page's title and
    link card keep heading()'s short form, as every list does."""
    return re.sub(r"^(Former )?(Rep\.|Sen\.) ",
                  lambda g: f"{g.group(1) or ''}{HONORIFIC_FULL[g.group(2)]} ", heading(m))


# How many of a member's bills and votes the plain page lists: the newest,
# with the count of the rest. The longest-serving members filed over a
# thousand bills and cast tens of thousands of votes; the page app.js draws
# pages through them all, and so does the JSON linked below.
STATIC_BILLS, STATIC_VOTES = 200, 100


def elected_pages(elect):
    """{(id, slug): race key} for each member-elect the members-elect file
    links to a page: a sitting member re-elected, or a former member
    returning. A new person has no page and is not here.

    ONE LINE ON THEIR OWN PAGE, AND ONLY THEIRS (the person's decisions of 16
    October 2026). The file names the id and the page together only on a
    certain match, so the line goes on the page that is both -- never on
    another record of the same name -- and says nothing on any other page:
    a sitting member who is not on the list is not said to be anything."""
    out = {}
    for key, race in ((elect or {}).get("races") or {}).items():
        for e in race.get("elected") or []:
            if e.get("k") in ("sitting", "former") and e.get("id") and e.get("s"):
                out[(str(e["id"]), str(e["s"]))] = key
    return out


def elected_info(elect):
    """{(id, slug): {"key", "k", "p"}} for the same members as elected_pages,
    with the file's own word for who they are (`k`: "sitting" or "former")
    and the party letter the results print."""
    out = {}
    for key, race in ((elect or {}).get("races") or {}).items():
        for e in race.get("elected") or []:
            if e.get("k") in ("sitting", "former") and e.get("id") and e.get("s"):
                out[(str(e["id"]), str(e["s"]))] = {"key": key, "k": e["k"], "p": e.get("p") or ""}
    return out


def elect_where(key):
    """'Hillsborough 16' for the House, 'Senate District 8' for the Senate,
    from a race key ('H|Hillsborough|16', 'S|8'): elect_district's words for
    a race, as the provisional pages say them."""
    m = ELECT_KEY.fullmatch(str(key or ""))
    if not m:
        return ""
    return f"Senate District {m.group(3)}" if m.group(3) else f"{m.group(1)} {m.group(2)}"


def elect_mode(m, info):
    """How a member the election sent back is drawn on their own page, from the
    file's word and the record the page is for:

      "returning"  a former member elected again (the file says `former`, and
                   the record being drawn is former.json's): the page is the
                   member-elect's, in the form of a new member-elect's, with
                   their earlier service kept below it;
      "chamber"    a sitting member elected to the other chamber (Rep. for
                   Hills 30, elected Senator): still titled by the seat they
                   hold now, with the election shown beside it;
      ""           anyone else, the re-elected: the page as it was, with the
                   one line.

    All of it exists only while the members-elect file does, which ends on
    the day they take office (build_members_elect.for_pages)."""
    if not info:
        return ""
    if info["k"] == "former" and m.get("former"):
        return "returning"
    if info["k"] == "sitting" and not m.get("former") \
            and str(m.get("chamber") or "")[:1].upper() != info["key"].split("|")[0]:
        return "chamber"
    return ""


def elect_member_name(m):
    """'Benjamin Baroody' from the record's own label ('Rep. Benjamin Baroody'),
    with no honorific: the name as the provisional pages head a member-elect."""
    plain = str(m.get("display_plain") or m.get("display_full") or "").split(" (")[0]
    return re.sub(r"^(Rep|Sen)\. ", "", plain).strip()


def elect_back(m, info):
    """What a member-elect's own page is told besides the line, or None where
    it is drawn as before: {"mode", "name", "party", "where", "head"}. `where`
    is the sentence a provisional page says ("Member-elect of the New
    Hampshire House of Representatives, Hillsborough 16."), `head` the page's
    title ("Benjamin Baroody (D), member-elect")."""
    mode = elect_mode(m, info)
    if not mode:
        return None
    name = elect_member_name(m)
    return {"mode": mode, "name": name, "party": info["p"],
            "where": f"Member-elect of the {CHAMBER_WORDS[info['key'].split('|')[0]]}, "
                     f"{elect_where(info['key'])}.",
            "head": f"{name} ({info['p']}), member-elect" if info["p"] else f"{name}, member-elect"}


def town_pages(site):
    """{slug: address} of every town page build_town_pages writes: one for
    each town and ward site/districts.json holds."""
    f = site / "districts.json"
    d = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    return {town_slug(t, w): town_path(t, w) for t, wards in d.items() for w in wards}


def towns_linked(towns, pages):
    """{town: address} for each of a member's towns that has a page (the
    audit of 25 October 2026, S6). The roster writes a ward "Concord Ward
    3", which is its page's slug in words; a place it spells otherwise than
    the district maps ("Atk. & Gilmanton Academy Gt") has no page by that
    name, and is left as words rather than linked to a page that is not
    there."""
    return {t: pages[town_slug(t, "0")] for t in towns if town_slug(t, "0") in pages}


CHAMBER_WORDS = {"H": "New Hampshire House of Representatives", "S": "New Hampshire Senate"}
# Not indexed until the General Court numbers the person and the page is
# their regular one (Alice, B2, 7 November 2026).
ELECT_ROBOTS = '<meta name="robots" content="noindex,follow">'


def elect_district(p):
    """'Sullivan 7' for the House, 'Senate District 2' for the Senate."""
    return (f"Senate District {p['district']}" if p.get("chamber") == "S"
            else f"{p.get('county')} {p.get('district')}")


def elect_body(p, doc, reqs, req_meta, places, today):
    """A new member-elect's provisional page (build_elect_pages.py): the name
    as the ballot prints it, party, district and towns, when they were
    elected and take office, and their requests for the next session. No
    contact detail, no votes, no seat and no committees: none is published
    for them until the General Court numbers them, when this becomes their
    regular page."""
    took = today >= doc["takes_office"]
    party = f" ({E(p['party'])})" if p.get("party") else ""
    # The plain record's look, shown with script too ("shown"; app.css hides
    # a .static-rec under html.js otherwise), and its own id: this page is
    # GR_STATIC, and "static-rec" is the fallback plainRecord rewrites.
    out = ['<div class="static-rec shown" id="elect-rec">',
           f"<h1>{E(p['name'])}{party}</h1>",
           # From the day they take office they are members, not members-elect.
           f"<p>{'Member' if took else 'Member-elect'} of the "
           f"{CHAMBER_WORDS.get(p.get('chamber'), 'General Court')}, {E(elect_district(p))}.</p>",
           f"<p>Elected {E(S.date_words(doc['election'], 'full'))}. "
           + (f"Took office {E(S.date_words(doc['takes_office'], 'full'))}."
              if took else f"Takes office {E(S.date_words(doc['takes_office'], 'full'))}.")
           + "</p>"]
    towns = p.get("towns") or []
    if towns:
        out.append('<ul class="sx-facts"><li><b>Represents:</b> ' + ", ".join(
            f'<a href="{E(places[t])}">{E(t)}</a>' if t in places else E(t) for t in towns)
            + "</li></ul>")
    # Earlier service the person confirmed by hand (hand "prior"): the seat as
    # it was labelled then and its terms, with no link, since no page of a
    # member is theirs.
    pr = p.get("prior")
    if pr:
        out.append('<ul class="sx-facts"><li><b>Earlier service:</b> ' + E(pr.get("seat") or "")
                   + ", " + ", ".join(E(t) for t in pr.get("terms") or []) + "</li></ul>")
    out.append("<p>Their seat, committees and record are added here as the General Court "
               "publishes them.</p>")
    if reqs:
        label = (req_meta or {}).get("label") or "Bill Requests"
        out.append(f"<h2>{E(label)}</h2>"
                   # Alice's two sentences, as the bill search says them.
                   "<p><b>Requests, not bills yet.</b> Each is a member&rsquo;s request to have "
                   "a bill drafted: a title and a sponsor, nothing more, until it is filed as a "
                   f"numbered {E(str((req_meta or {}).get('year') or ''))} bill. Some are "
                   "withdrawn first.</p><ul>" + "".join(
                       f"<li>{E(r.get('n'))}: {E(r.get('title'))} ({E(r.get('body_label') or '')})"
                       f" &mdash; {E(r.get('status') or '')}</li>" for r in reqs) + "</ul>"
                   + (f'<p><a href="/bills?term={E(req_meta["term"])}">All {E(label)}</a></p>'
                      if (req_meta or {}).get("term") else ""))
    srcs = doc.get("sources") or []
    out.append("<h2>Sources</h2><ul><li>The election results: the New Hampshire Secretary of "
               "State" + "".join(f', <a href="{E(u)}" rel="noopener">{E(u)}</a>' for u in srcs[:1])
               + "</li></ul></div>")
    return "".join(out)


def write_elect_pages(site, out, t, base, written_slugs, pages_of_towns, today):
    """Each new member-elect's provisional page, from site/elect_pages.json:
    noindex and out of the sitemap until numbered (B2). A slug a member's page
    was written at this run is not overwritten. Returns how many."""
    f = site / "elect_pages.json"
    if not f.is_file():
        return 0
    doc = json.loads(f.read_text(encoding="utf-8"))
    meta = json.loads((site / "meta.json").read_text(encoding="utf-8")) \
        if (site / "meta.json").is_file() else {}
    req_meta = meta.get("requests") or {}
    rows = []
    if req_meta.get("term") and (site / "idx" / f"{req_meta['term']}.json").is_file():
        rows = json.loads((site / "idx" / f"{req_meta['term']}.json").read_text(encoding="utf-8"))
    n = 0
    for p in doc.get("pages") or []:
        slug = p["slug"]
        if slug in written_slugs:
            continue
        path = f"/legislator/{slug}.html"
        reqs = [r for r in rows if r.get("sponsor_slug") == slug]
        places = towns_linked(p.get("towns") or [], pages_of_towns)
        who = f"{p['name']}" + (f" ({p['party']})" if p.get("party") else "")
        if today < doc["takes_office"]:
            who += ", member-elect"
        page = S.page(t, path=path, base=base, title=f"{who} | Granite Record",
                      og_title=who, og_image="og-legislator.png",
                      og_alt="Granite Record: legislators and their voting records",
                      description=(f"{p['name']}, elected to the {CHAMBER_WORDS.get(p.get('chamber'), 'General Court')} "
                                   f"for {elect_district(p)} on {S.date_words(doc['election'], 'full')}."),
                      globals={"GR_STATIC": True}, noscript="",
                      skip_label="Skip to this member-elect", nav_current="officials.html",
                      sr_title="")
        page = page.replace('<div id="results"></div>',
                            f'<div id="results">{elect_body(p, doc, reqs, req_meta, places, today)}</div>', 1)
        page = page.replace('<link rel="canonical"', ELECT_ROBOTS + '\n<link rel="canonical"', 1)
        assert ELECT_ROBOTS in page, f"{path}: the template has no canonical link to put noindex before"
        (out / f"{slug}.html").write_text(S.clean_links(page), encoding="utf-8")
        n += 1
    return n


def last_vote_day(rec):
    """The ISO day of the member's latest recorded vote, from their own JSON
    (its "d" is M/D/YYYY), or None where they have none: the day their page's
    record last changed, for the citation's date (shell.cited)."""
    best = ""
    for x in (rec or {}).get("votes") or []:
        d = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", str(x.get("d") or ""))
        if d:
            best = max(best, f"{d.group(3)}-{int(d.group(1)):02d}-{int(d.group(2)):02d}")
    return best or None


def static_record(m, rec, elected="", places=None, back=None):
    """THE MEMBER'S RECORD IN THE PAGE ITSELF, for a reader with no
    JavaScript (the SEO review of 12 October 2026; shell.page's static).
    It replaced a <noscript> line saying the page needs JavaScript. m is the
    roster's row, rec the member's own JSON (legislators/<id>.json), which
    the page app.js draws reads too. `elected` is the member-elect's line
    (components.elect_line) where the member is one, under the heading,
    which is left as it is until they take office. `places` is towns_linked's
    {town: address}, each town in it a link to its page. `back` is
    elect_back's, for a former member elected again or a member elected to the
    other chamber: the first is headed as a new member-elect's page is, its
    earlier seat kept below; the second keeps its heading and says the
    election beside it."""
    rec = rec or {}
    yrs = _served_years(m) if m.get("former") else ""
    titled = heading(m).startswith("Former ")
    back = back or {}
    returning = back.get("mode") == "returning"
    if returning:
        # Word for word the new member-elect's page (elect_body): the name and
        # party, "Member-elect of the ..., district.", the election's line.
        out = ['<div class="static-rec" id="static-rec">',
               f"<h1>{E(back['name'])}" + (f" ({E(back['party'])})" if back.get("party") else "")
               + "</h1>", f"<p>{E(back['where'])}</p>"]
        if elected:
            out.append(elected)
        out.append(f"<p>Earlier seat: {E(m.get('display_full') or m.get('display') or '')}</p>")
        elected = ""
    else:
        out = ['<div class="static-rec" id="static-rec">', f"<h1>{E(head_name(m))}</h1>"]
        if back.get("mode") == "chamber":
            out.append(f"<p>{E(back['where'])}</p>")
    if m.get("former"):
        out.append(f"<p>{E('On record ' + yrs + '. ') if yrs else ''}This page is their "
                   "record in the New Hampshire General Court; it is not a current "
                   "directory entry.</p>" if titled else
                   "<p>Former member of the New Hampshire General Court"
                   f"{E(', ' + yrs) if yrs else ''}. This page is their record; it is "
                   "not a current directory entry.</p>")
    if elected:
        out.append(elected)
    facts = []
    towns = m.get("towns") or []
    if towns and not m.get("former"):
        places = places or {}
        facts.append("<b>Represents:</b> " + ", ".join(
            f'<a href="{E(places[t])}">{E(t)}</a>' if t in places else E(t) for t in towns))
    if m.get("committees") and not m.get("former"):
        facts.append(f"<b>Committees:</b> {E(', '.join(m['committees']))}")
    c = rec.get("counts") or {}
    if c:
        facts.append("<b>Recorded roll call votes:</b> " + E(", ".join(
            f"{k} {v:,}" for k, v in c.items() if isinstance(v, int))))
    if rec.get("n_sponsored"):
        facts.append(f"<b>Bills sponsored:</b> {rec['n_sponsored']:,}"
                     + (f", {rec['n_prime']:,} as prime sponsor" if rec.get("n_prime") else ""))
    if facts:
        out.append('<ul class="sx-facts">' + "".join(f"<li>{x}</li>" for x in facts) + "</ul>")
    sp = sorted(rec.get("sponsored") or [], key=lambda x: (str(x.get("year") or ""),
                                                            str(x.get("bill") or "")), reverse=True)
    if sp:
        out.append("<h2>Bills Sponsored</h2><ul>" + "".join(
            f'<li><a href="bill/{E(str(x.get("year")))}/{E(str(x.get("bill", "")).lower())}">'
            f'{E(x.get("n") or x.get("bill") or "")} ({E(str(x.get("year")))})</a>'
            + (f": {E(x['title'])}" if x.get("title") else "")
            + (" (prime sponsor)" if x.get("prime") else "") + "</li>"
            for x in sp[:STATIC_BILLS] if x.get("year") and x.get("bill")) + "</ul>"
            + (f"<p>And {len(sp) - STATIC_BILLS:,} earlier bills.</p>" if len(sp) > STATIC_BILLS else ""))
    vs = rec.get("votes") or []
    if vs:
        def vote(x):
            on = (f'<a href="bill/{E(str(x["y"]))}/{E(str(x["b"]).lower())}">{E(x["b"])}</a>'
                  if x.get("b") and x.get("y") else E(x.get("b") or ""))
            # "8/19/2026" as the site writes a date: "August 19, 2026".
            d = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", x.get("d") or "")
            iso = (f"{d.group(3)}-{int(d.group(1)):02d}-{int(d.group(2)):02d}" if d
                   else (x.get("d") or "")[:10])
            try:
                when = S.date_words(iso, "full")
            except (ValueError, TypeError):
                when = x.get("d") or ""
            return (f"{E(when)}: {on}{', ' if on else ''}{E(x.get('q') or '')}"
                    f" &mdash; {E(x.get('v') or '')}")
        out.append("<h2>Recent Votes</h2><ul>"
                   + "".join(f"<li>{vote(x)}</li>" for x in vs[:STATIC_VOTES]) + "</ul>"
                   + (f"<p>And {len(vs) - STATIC_VOTES:,} earlier votes.</p>"
                      if len(vs) > STATIC_VOTES else ""))
    links = [f'<a href="/legislators/{E(str(m.get("id", "")))}.json">This page&rsquo;s data as JSON</a>']
    if m.get("url"):
        links.append(f'<a href="{E(m["url"])}" rel="noopener">This member on the General Court&rsquo;s site</a>')
    out.append("<h2>Sources</h2><ul>" + "".join(f"<li>{x}</li>" for x in links) + "</ul>")
    out.append("</div>")
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site = Path(a.site)
    legs = json.loads((site / "legislators.json").read_text(encoding="utf-8"))
    # AND THE MEMBERS WHO LEFT MID-TERM. build_site_v2.former_roster writes
    # them to their own file rather than into the roster, because a dozen
    # builders read the roster to mean "who serves now". They get a page by
    # the same code as everyone else -- same shell, same slug, same JSON --
    # so a reader who follows a sponsor's name from a bill they filed this
    # term arrives at their voting record instead of at plain text.
    former = json.loads((site / "former.json").read_text(encoding="utf-8")) \
        if (site / "former.json").exists() else []
    out = site / "legislator"
    out.mkdir(parents=True, exist_ok=True)
    t = S.template(site)
    # The members-elect, while there are any, by the page each is linked to.
    elect = members_elect(site)
    elected = elected_pages(elect)
    info = elected_info(elect)
    today = build_date.today().isoformat()
    n_elected = 0
    pages = town_pages(site)

    def own(m):
        """The member's own JSON, which app.js draws their page from."""
        f = site / "legislators" / f"{m.get('id')}.json"
        try:
            return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
        except ValueError:
            return {}

    urls, written, n_former = [], 0, 0
    for m in [*legs, *former]:
        slug = m.get("slug") or person_slug(m)
        path = f"/legislator/{slug}.html"
        # "Former Rep. ..." for a member who has left: heading() says why.
        who = heading(m)
        mid = str(m.get("id") or "")
        # Their own JSON, read once: the static record draws from it, and the
        # description names each chamber of a joined page from its service.
        rec = own(m)
        # THE MEMBER'S FEED, WHERE ONE IS WRITTEN: their recorded votes and the
        # bills they sponsored. build_feeds once wrote one for each of the 406
        # and no page named any, so the only way to one was
        # already knowing its address. A feed reader given this page finds it
        # here, as it finds a bill's. build_feeds runs after this step, so
        # there is no file to look for: shell.member_followable is the test
        # both use. Titled as the feed titles itself.
        named = m.get("display") or m.get("name") or f"Member #{mid}"
        feed = (f'<link rel="alternate" type="application/rss+xml" '
                f'title="{E(named)} — Granite Record" '
                f'href="/feed/legislator/{E(mid)}.xml">'
                if S.member_followable(m) else "")
        # A MEMBER-ELECT'S ONE LINE (16 October 2026), in the plain page and,
        # through GR_ELECT, in the page app.js draws (renderMemberHead), which
        # draws it only for this id: a reader who goes on from here to another
        # member within the page is not shown this member's line there.
        race = elected.get((mid, slug))
        n_elected += race is not None
        back = elect_back(m, info.get((mid, slug)))
        returning = bool(back) and back["mode"] == "returning"
        # A returning member's page is a member-elect's, in the form of a new
        # one's (elect_body): its line has no "for <district>", the sentence
        # above it says the seat. Everyone else's keeps the line as it was.
        line = (elect_line(None if returning else race, elect["election"],
                           elect["takes_office"], today) if race else "")
        also = ({"GR_ELECT": {"id": mid, "key": race, "election": elect["election"],
                              "takes_office": elect["takes_office"],
                              **({k: back[k] for k in ("mode", "name", "party", "where")}
                                 if back else {})}} if race else {})
        about = ""
        if returning:
            who = back["head"]
            ch = info[(mid, slug)]["key"].split("|")[0]
            about = (f"{back['name']}, elected to the {CHAMBER_WORDS[ch]} for "
                     f"{elect_where(race)} on {S.date_words(elect['election'], 'full')}.")
        # Their towns' pages, for the line app.js draws under the name and
        # the static record alike; a former member's page names no towns.
        places = {} if m.get("former") else towns_linked(m.get("towns") or [], pages)
        if places:
            also["GR_TOWNS"] = places
        (out / f"{slug}.html").write_text(S.clean_links(S.page(
            t, path=path, base=a.base,
            title=f"{who} | Granite Record",
            # The member's name and seat and nothing after it: "-- New Hampshire
            # General Court" in a link card read as the General Court's own page.
            og_title=who, og_image="og-legislator.png",
            og_alt="Granite Record: legislators and their voting records",
            description=about if returning else describe(m, rec), alternate=feed,
            changed=last_vote_day(rec),
            # Name, office, chamber, party, district. Not email or telephone:
            # structured.py says why.
            jsonld=LD.person(m, a.base, S.canon(path)),
            # GR_FORMER tells app.js to say, on this page and nowhere else,
            # that the member no longer serves -- and to leave out the contact
            # details, which belonged to the office. It says nothing about why
            # they left, and nothing anywhere else on the site marks them:
            # in a roll call or a sponsor list they are named exactly as a
            # sitting member is.
            globals={"GR_MEMBER": str(m.get("id", "")), "GR_STANDALONE": True,
                     **({"GR_FORMER": True} if m.get("former") else {}), **also},
            static=static_record(m, rec, line, places, back), skip_label="Skip to this member",
            # Without this the template's marker stays on Bills, and all 406
            # member pages told a screen reader they were Bills.
            nav_current="officials.html",
            # And the template's hidden "New Hampshire bills" <h1> went, as
            # the first heading, before the member's own -- which the page
            # draws (and its noscript carries), so the hidden one is removed
            # rather than renamed: two headings saying one name is worse.
            sr_title="")),
            encoding="utf-8")
        urls.append(a.base + S.canon(path))
        written += 1
        n_former += bool(m.get("former"))

    assert written or not legs, (
        "no legislator page was written, and legislators.json holds "
        f"{len(legs)}. That is a run that failed, not a roster that emptied.")
    # THE NEW MEMBERS-ELECT'S PROVISIONAL PAGES (build_elect_pages.py), after
    # every member's: noindex and left out of `urls`, so not in the sitemap,
    # until the person is numbered (Alice, B2).
    n_elect = write_elect_pages(site, out, t, a.base,
                                {(m.get("slug") or person_slug(m)) for m in [*legs, *former]},
                                pages, today)
    if n_elect:
        print(f"  {n_elect} provisional pages for new members-elect (noindex, not in the sitemap)")
    # SILENCE IS NOT SUCCESS: a members-elect file that links members to
    # pages, and pages none of which took the line, is a mismatch to see.
    if elected:
        print(f"  members-elect: the line on {n_elected} of the {len(elected)} pages the file "
              "links a member-elect to")
        if n_elected < len(elected):
            missing = sorted(f"{i} ({s})" for i, s in elected
                             if not any(str(m.get("id") or "") == i
                                        and (m.get("slug") or person_slug(m)) == s
                                        for m in [*legs, *former]))
            print("  members-elect: no page here for " + ", ".join(missing[:8]))

    # sitemap.xml is written by build_bill_pages.py, which runs first, and
    # this adds to it rather than replacing it. THROUGH shell.sitemap_merge,
    # AS THE OTHER BUILDERS ADD THEIRS (the sitemap audit, 16 October 2026):
    # the test here was whether an address appeared anywhere in the file's
    # text, which takes /legislator/x as listed wherever /legislator/x-y is,
    # and nothing ever took out the page of a member this run no longer
    # writes. Every member's page is written on every run, current and
    # former alike, so this run owns /legislator whole.
    added, dropped = S.sitemap_merge(site, a.base, urls, "/legislator")
    if added or dropped:
        print(f"sitemap.xml: {added} added, {dropped} no longer written taken out")

    total = sum(p.stat().st_size for p in out.glob("*.html"))
    print(f"{written} legislator pages -> {out}/  ({total/1e6:.1f} MB)"
          + (f"; {n_former} of them members who left mid-term, whose votes and "
             "sponsorships were plain text before" if n_former else ""))
    print("\nEach page is bills.html with one member open, drawn by app.js "
          "from the\nsame JSON the search page reads. Somebody searching a "
          "member's name finds\ntheir voting record, and it is the same record "
          "the rest of the site draws.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
