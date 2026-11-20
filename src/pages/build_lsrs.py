#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.30
"""
Next session's bill requests, as a term the bill search can open.

    python3 src/pages/build_lsrs.py --site site

WHAT AN LSR IS

Before a bill exists it is a Legislative Service Request: a member tells the
Office of Legislative Services what they want drafted, and the office gives it
a number like 2027-0001. It carries a title and a prime sponsor and nothing
else -- no text, no committee, no hearing, no number of its own -- until it is
drafted and filed, at which point it becomes HB 1234 and this site's ordinary
machinery picks it up. Some are withdrawn before that happens and never become
anything.

So this is the earliest public signal of what the next session will be about,
and it is the reason the person asked for it on 18 September: "viewing LSRs
that have been filed officially which are for next term and just have the
title and prime sponsor right now ... It should be replaced by the actual 2027
term bills once the full text is available and they've been officially filed,
and should be listed between All terms and the current term in the term
selector, and the 2025-2026 term (Current term) should be the default until
the bills for next term are fully available."

The default was settled the other way on 30 September: the site opens on
2027-2028 from its first bill, because the General Court publishes bills in
batches and the first arrives with others. That is what the newest-term rule
already does, so nothing holds 2025-2026 first.

WHAT THIS WRITES

  site/idx/<year>-requests.json the rows, in the shape idx/<term>.json uses,
                                so the bill search reads them with the code it
                                already has rather than a second path
  site/meta.json                one key merged in: "requests", which names the
                                term, its label, its year and how many there are

THE YEAR IS THE REQUESTS' OWN (18 October 2026). It was two literals, "2027-
requests" and "2027 Bill Requests", and app.js said "for 2027", so the requests
for 2028, filed from September 2027, would have been listed as 2027's. The
year is the newest session the requests name, and only that session's are
listed: by the time the next session's are filed, the older ones are bills or
withdrawn, and each bill is in its own term.

MERGING INTO meta.json, WHICH ANOTHER BUILDER OWNS

build_site_v2.py writes meta.json. This reads it and adds one key, the way
build_indexes.py appends to a sitemap.xml that build_bill_pages.py wrote --
the same pattern and the same requirement, which is that this step runs AFTER
the one that writes the file. build_all.py orders it; the assert below is what
catches the day somebody reorders them, because a silently missing key would
show as the option simply not being there.

The rows carry no committee and no status kind, because an LSR has neither,
so the Committee facet is correct to show nothing for this term. The Status
facet is not empty: a request's status is its own word (Requested, Filed,
Introduced or Withdrawn, REQUESTED/FILED/INTRODUCED/WITHDRAWN below), which
app.js's REQ_STATUS takes as a category. Every request not yet a bill carries
a topic (`topic_by` "title", with_topics below): the one request_topics reads
from its title, or Miscellaneous where the title does not say enough (the
owner, 14 November 2026), which the Topic facet lists and a card does not
print.

A REQUEST STAYS A REQUEST UNTIL IT IS INTRODUCED (the owner, 17 November 2026:
"Officially LSRs do not become bills until the first session in January when
they are introduced and referred to committees ... Text and co-sponsors are
gradually added"). Filed -- its text public, which is when its bill is
numbered -- it keeps its own page and its card, now with its text where the
night has read it (request_text: the Bill Text tab, its card's, and its file in
the data API), and says the number it was filed as; only once its bill's
docket says it was introduced (introduced_days) does it read Introduced, its
rail's last stop reached, and its address forward to the bill's page.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import datetime
import json
import re
import unicodedata

def requests_term(year):
    """(the requests' term key, the term picker's label) for a session year:
    ("2027-requests", "2027 Bill Requests")."""
    return f"{year}-requests", f"{year} Bill Requests"


def session_of(r):
    """A request's session year as a number: its own, or its number's
    (2027-0001 is 2027's); None where it gives neither."""
    s = str(r.get("session") or "").strip()
    if s.isdigit():
        return int(s)
    m = LSR_NO.match(str(r.get("lsr") or "").strip())
    return int(m.group(1)) if m else None


def newest_session(lsrs):
    """(the newest session the requests name, that session's requests, how
    many of an older session were left out)."""
    years = [session_of(r) for r in lsrs]
    year = max((y for y in years if y), default=None)
    mine = [r for r, y in zip(lsrs, years) if y == year]
    return year, mine, len(lsrs) - len(mine)

# What the General Court's own search calls each body, spelled out. A reader
# who has not met these two-letter forms should not have to learn them to read
# a card.
BODY = {"HB": "House bill request", "SB": "Senate bill request",
        "CACR": "Constitutional amendment request",
        "HR": "House resolution request", "SR": "Senate resolution request",
        "HCR": "House concurrent resolution request",
        "SCR": "Senate concurrent resolution request",
        "HJR": "House joint resolution request",
        "SJR": "Senate joint resolution request"}


# A name folded to the letters in it, so that "Aboul-Hosn, Nadia" and
# "Nadia Aboul-Hosn" fold the same, and a middle initial on one side and not
# the other does not decide whether a sponsor gets their page.
def _fold(s):
    return re.sub(r"[^a-z]", "", str(s or "").lower())


def roster(site, collected="collected", year=None):
    """{folded name: (label, slug)} for the sitting members.

    The source names a sponsor "Ellen Read" and nothing more. The roster has
    her party, her seat and her page, and a request is filed by somebody
    sitting now, so the label the roster carries is the right one for it.
    A name that matches nothing is left as it was typed rather than guessed
    at -- a wrong member on a bill is the error this site fixes first.
    """
    p = site / "legislators.json"
    if not p.exists():
        return {}
    out = {}
    for m in json.loads(p.read_text(encoding="utf-8")):
        # "Abbas, Daryl" -- surname first, and there are no separate first and
        # last fields on the roster to read instead; every one of the 406 has
        # them as None. The LSR source writes "Daryl Abbas", so the comma is
        # what turns one into the other.
        name = (m.get("name") or "").strip()
        if "," not in name:
            continue
        last, first = (x.strip() for x in name.split(",", 1))
        if not (first and last):
            continue
        key = _fold(f"{first} {last}")
        # A name two sitting members share cannot be resolved from a name
        # alone, so neither gets the label rather than one of them getting
        # the other's.
        out[key] = None if key in out else (m.get("display") or m.get("name"),
                                            m.get("slug"))
    # AND THE NEW MEMBERS-ELECT, WHO HAVE A PROVISIONAL PAGE (Alice, 7 November
    # 2026; build_elect_pages.py): matched "by name only where certain" -- the
    # same folded name, the request's chamber theirs (the third field, which
    # rows_from holds a request to), and nobody else of the name, sitting,
    # former or elect. Anything less stays unlinked, as before.
    ep = site / "elect_pages.json"
    if ep.exists():
        fj = site / "former.json"
        gone = set()
        for m in (json.loads(fj.read_text(encoding="utf-8")) if fj.exists() else []):
            last, _, first = str(m.get("name") or "").partition(",")
            gone.add(_fold(f"{first} {last}"))
        titled = elect_window(site)
        for p in json.loads(ep.read_text(encoding="utf-8")).get("pages") or []:
            key = _fold(p.get("name"))
            party = f" ({p['party']})" if p.get("party") else ""
            title = f"{elect_title(p.get('chamber'))} " if titled else ""
            out[key] = None if (key in out or key in gone) else (
                f"{title}{p.get('name')}{party}", p.get("slug"), p.get("chamber"))
    # AND, ONCE THE ROSTER IS THE NEW TERM'S, THE MEMBERS OF THE TERM BEFORE
    # WHO ARE NOT ON IT (departed; the rehearsal of 17 November 2026). Their
    # requests were the old roster's to match until the New term run; after
    # it the roster no longer has them, a withdrawn request of theirs matched
    # nobody, and not_returning, which decides by slug, kept it as
    # "Withdrawn". Matched as a sitting member is -- the same folded name, and
    # nobody else of it -- and drawn by name and party, never the seat they
    # left (person_chip's rule for a former member). A name a sitting member
    # or a member-elect already has is theirs, as it was before the turn.
    seen = set()
    for m in departed(site, collected, year):
        key = _fold(first_last(m.get("name")))
        if not key or key in out and key not in seen:
            continue
        party = f" ({m['party_code']})" if len(str(m.get("party_code") or "")) == 1 else ""
        out[key] = None if key in seen else (f"{first_last(m.get('name'))}{party}", m.get("slug"))
        seen.add(key)
    return out


def departed(site, collected="collected", year=None):
    """The members of the term the newest election ended who are not on the
    roster, once the roster is the new term's (election_races says when):
    site/former.json's rows whose record holds that term, each with its page.
    [] before the turn, or where no results say which term is coming -- and
    for requests of a session `year` other than the elected term's first:
    the requests for 2028, filed from September 2027, are sitting members'
    alone, and a name of theirs that only someone gone in 2026 shares must
    not link to that person's page."""
    _races, turned, term, _why = election_races(site, collected)
    if not turned or year is not None and str(year) != term[:4]:
        return []
    import build_members_elect as BME
    before = BME.term_before(term)
    fj, lp = site / "former.json", site / "legislators.json"
    sitting = {m.get("slug") for m in (json.loads(lp.read_text(encoding="utf-8"))
                                       if lp.exists() else [])}
    return [m for m in (json.loads(fj.read_text(encoding="utf-8")) if fj.exists() else [])
            if m.get("slug") and m["slug"] not in sitting
            and before in ((m.get("served") or {}).get("terms") or [])]


# "Rep. " or "Sen. " before a name, which a label carries and a name does not,
# and a member-elect's "Rep. “Elect”" (elect_title).
_TITLE = re.compile("^(?:Rep|Sen)\\.\\s*(?:“Elect”\\s*)?")


def elect_title(chamber):
    """A member-elect's title, by the chamber they were elected to -- "Rep.
    “Elect”", "Sen. “Elect”" -- in the words
    build_legislator_pages.elect_title gives the search and their own page
    (the i18n keys elect.title_rep and elect.title_sen)."""
    import i18n
    return (i18n.say("en", "elect.title_sen", "Sen. “Elect”") if chamber == "S"
            else i18n.say("en", "elect.title_rep", "Rep. “Elect”"))


def elect_window(site):
    """Whether a request's member-elect sponsor is drawn under their title:
    from the election until the day they take office, which the members-elect
    file gives (site/members_elect.json, else site/elect_pages.json, each
    "takes_office"), by the build's day. False where neither is there."""
    import build_date
    for name in ("members_elect.json", "elect_pages.json"):
        p = Path(site) / name
        try:
            day = str((json.loads(p.read_text(encoding="utf-8")) or {}).get("takes_office") or "")
        except (OSError, ValueError, AttributeError):
            continue
        if day:
            return build_date.today().isoformat() < day
    return False


def page_names(site):
    """{slug: the name that person's own page prints, first name first}: a
    sitting or former member's display name without its title ("Rep. James
    Creighton" -> "James Creighton", whom the request list calls "Jim
    Creighton"), a member-elect's the name their provisional page is under.
    with_sponsor_names gives a request the name of the page its sponsor
    links to."""
    out = {}
    for n in ("legislators.json", "former.json"):
        p = site / n
        for m in (json.loads(p.read_text(encoding="utf-8")) if p.exists() else []):
            name = _TITLE.sub("", str(m.get("display_plain") or "")).strip() or first_last(m.get("name"))
            if m.get("slug") and name:
                out.setdefault(m["slug"], name)
    ep = site / "elect_pages.json"
    pages = (json.loads(ep.read_text(encoding="utf-8")).get("pages") or []) if ep.exists() else []
    for p in pages:
        if p.get("slug") and str(p.get("name") or "").strip():
            out.setdefault(p["slug"], str(p["name"]).strip())
    return out


def label_name(label):
    """A sponsor's label as the name in it, the title and the party taken off:
    "Rep. Ellen Read (D)" -> "Ellen Read", "Lee C. Nyquist (D)" -> "Lee C. Nyquist",
    and a member-elect's "Rep. “Elect” Colin Mitchell (R)" -> "Colin Mitchell"."""
    return _TITLE.sub("", re.sub(r"\s*\([^()]*\)\s*$", "", str(label or ""))).strip()


# A name's words as the bill search reads them (app.js hintWords): accents off
# (the combining marks U+0300 to U+036F, after NFD), lower case, an apostrophe,
# straight or curly, dropped, and split on anything not a letter or a figure.
_MARKS = re.compile("[%s-%s]" % (chr(0x300), chr(0x36F)))
_APOSTROPHES = re.compile("['%s%s]" % (chr(0x2018), chr(0x2019)))


def _words(s):
    """The words of a name as the search splits them: "W. Packy Campbell" and
    "W Packy Campbell" are the same words, "Mary-Jane Smith" and "Maryjane
    Smith" are not."""
    s = _APOSTROPHES.sub("", _MARKS.sub("", unicodedata.normalize("NFD", str(s or ""))).lower())
    return [w for w in re.split(r"[^a-z0-9]+", s) if w]


# NAMES THE ROSTER'S WHOLE-NAME MATCH MISSES (13 November 2026). The source
# writes "Lee Nyquist" where the results print "Lee C. Nyquist", "Jim" for
# "James", and a winner of a race still being recounted is on no roster and has
# no page of their own yet. The owner's rule: "as accurate as possible and not
# guess if we aren't confident." So a second step, run only where the roster
# found nobody, matches a request to a WINNER of the latest general election
# in the request's own chamber, and only where nothing else could be meant.
#
# NICKNAMES: each set is names that are one first name, and a pair is added
# only with the request that needs it. The one here is Benjamin Baroody's: the
# list names him "Benjamin Baroody" and the results "Ben Baroody" (three
# requests on 13 November 2026, the only ones on the list any pair decides).
# A name that serves two (Pat: Patrick, Patricia; Chris; Sam) is never added,
# because a table entry is a certainty and those are not.
NICKNAMES = [{"ben", "benjamin"}]
_SUFFIX = {"jr", "sr", "ii", "iii", "iv"}

# FORMS OF ONE PERSON'S NAME THE OWNER CONFIRMED (18 November 2026): LSR
# 2027-0708 is filed by "Samuel Hoehn", the results print the Coos 1
# member-elect "Sam Hoehn", and the owner said "Yes, same person". Sam serves
# two names, so NICKNAMES never tables it; the owner's word ties this one
# person's two forms, and it lives in her hand file, which no script writes.
NAME_FORMS = _paths.ROOT / "corrections" / "name_forms.json"


def name_forms(path=None):
    """{folded form: the form it is matched under} from corrections/
    name_forms.json; {} where there is no file. An entry lacking a field the
    file's _how names, or naming less than a whole name, stops the build:
    the file is a person's word, and a half-written word is not one."""
    p = Path(path) if path else NAME_FORMS
    if not p.exists():
        return {}
    out = {}
    for e in json.loads(p.read_text(encoding="utf-8")).get("forms") or []:
        missing = [k for k in ("form", "is", "said", "by", "on", "evidence") if not e.get(k)]
        assert not missing, f"{p}: an entry lacks {', '.join(missing)}: {e}"
        assert _parts(e["form"]) and _parts(e["is"]), f"{p}: not a whole name: {e}"
        out[_fold(e["form"])] = e["is"]
    return out


def _parts(name):
    """(first, middles, last), each folded, for a name written first-last
    ("Lee C. Nyquist"); None where it has fewer than two words. A suffix
    (Jr., III) is not a surname."""
    toks = [t for t in (_fold(w) for w in re.split(r"[\s,]+", str(name or ""))) if t]
    while len(toks) > 2 and toks[-1] in _SUFFIX:
        toks.pop()
    return (toks[0], toks[1:-1], toks[-1]) if len(toks) >= 2 else None


def first_last(name):
    """'Nelson, Jodi' -> 'Jodi Nelson'; a name already first-last as it is."""
    last, sep, first = str(name or "").partition(",")
    return f"{first.strip()} {last.strip()}".strip() if sep else str(name or "").strip()


def same_first(a, b):
    """The same first name: equal, or a pair in NICKNAMES. An initial is only
    ever equal to itself."""
    return a == b or any(a in g and b in g for g in NICKNAMES)


def compatible(req, win):
    """(whether a request's sponsor can be this winner, whether the whole name
    is the same). Same surname; a first name equal or a NICKNAMES pair; a
    middle name only where one side has none and the other's is an initial, or
    where they are equal. Anything else is not compatible, never 'close'."""
    a, b = _parts(req), _parts(win)
    if not (a and b):
        return False, False
    if _fold(req) == _fold(win):
        return True, True
    if a[2] != b[2] or not same_first(a[0], b[0]):
        return False, False
    ma, mb = a[1], b[1]
    if ma and mb:
        ok = ma == mb
    else:
        ok = all(len(m) == 1 for m in ma + mb)
    return ok, False


def election_winners(results, drawn, pages, people, titled=False):
    """[{name, party, chamber, race, slug, label}] for every winner the results
    name as elected, in a race final or not (a recount does not change the
    party on the ballot), and the page each links to.

    `results` is collected/election_<year>.json's document, `drawn`
    members_elect.json's races, `pages` elect_pages.json's pages and `people`
    the sitting and former members. A winner's PAGE, first found of: the member
    the step or the owner matched (members_elect's "s"); the provisional page
    of a new member-elect; and, for a House winner drawn in neither (a race not
    final), the one sitting or former member of the same county whose name is
    compatible. A winner with none links nowhere and still carries the party
    they ran under. A tie (elected not True) names nobody.

    AND THE NAME THEIR MEMBER'S RECORD IS UNDER (17 November 2026), as
    "names", beside the ballot's: only where the step or the owner matched the
    winner to a sitting or former member ("s"). The ballot printed "Jeff
    Goley"; the owner matched him to member 460, "Goley, Jeffrey"; and his
    request is filed as "Jeffrey Goley", which matched nobody, because a short
    form is never taken on a name alone (NICKNAMES). That record ties the two.

    `titled` (elect_window): a member-elect's label carries their title, "Rep.
    “Elect” Jeff Goley (D)" (the owner, 17 November 2026) -- a winner
    the members-elect file draws as new or as a former member returning, or one
    with a provisional page; never one who sits now."""
    by_slug = {m.get("slug"): m for m in people if m.get("slug")}
    out = []
    for key, race in sorted((results.get("races") or {}).items()):
        ch = key.split("|")[0]
        county = key.split("|")[1] if ch == "H" else ""
        mine = {e.get("n"): e for e in (drawn.get(key) or {}).get("elected") or []}
        pg = {p.get("name"): p for p in pages if p.get("race") == key}
        for c in race.get("candidates") or []:
            if c.get("elected") is not True or not c.get("name"):
                continue
            name = c["name"]
            e = mine.get(name) or {}
            party = (e.get("p") or "").upper()
            if not party and str(c.get("party") or "").upper() in ("R", "D", "I", "L"):
                party = str(c["party"]).upper()
            slug = e.get("s") or (pg.get(name) or {}).get("slug") or ""
            if not slug and ch == "H" and not e:
                hits = [m for m in people
                        # former.json spells a county short ("Straf"), the roster in full.
                        if str(m.get("county") or "x").lower() != "x"
                        and county.lower().startswith(str(m["county"]).lower())
                        and m.get("slug") and compatible(first_last(m.get("name")), name)[0]]
                slug = hits[0]["slug"] if len(hits) == 1 else ""
            names = [name]
            rec = first_last((by_slug.get(e.get("s")) or {}).get("name")) if e.get("s") else ""
            if rec and _fold(rec) != _fold(name):
                names.append(rec)
            elect = e.get("k") in ("new", "former") or (not e and name in pg)
            title = f"{elect_title(ch)} " if titled and elect else ""
            out.append({"name": name, "party": party, "chamber": ch, "race": key,
                        "slug": slug, "label": title + (f"{name} ({party})" if party else name),
                        "names": names})
    return out


def winner_finder(winners):
    """find(name, body) -> (label, slug, chamber) or None: the winner of the
    request's own chamber the sponsor certainly is.

    CERTAIN means: exactly one winner of that chamber is compatible and either
    the whole name is the same, or no other winner of the chamber shares their
    surname and first initial (so "James Q. Smith" is not settled by "James
    Smith" while a "John Smith" also won). Two winners of the same whole name are
    nobody. A winner's names are the ballot's and the one their member's record
    is under (election_winners' "names").

    A CONSTITUTIONAL AMENDMENT REQUEST, which either chamber may file (no
    chamber; 17 November 2026): the one winner of either chamber whose whole
    name it is, and nobody where two are; never by an initial or a short form.
    rows_from asks only where no sitting member or member-elect has the name."""
    def names(w):
        return w.get("names") or [w["name"]]

    def find(name, body):
        ch = chamber_of(body)
        if not _parts(name):
            return None
        if not ch:
            same = [w for w in winners if any(_fold(n) == _fold(name) for n in names(w))]
            return (same[0]["label"], same[0]["slug"], same[0]["chamber"]) if len(same) == 1 else None
        pool = [w for w in winners if w["chamber"] == ch]
        ok = []
        for w in pool:
            said = [compatible(name, n) for n in names(w)]
            good, exact = any(g for g, _ in said), any(x for _, x in said)
            if good:
                ok.append((w, exact))
        exact = [w for w, x in ok if x]
        if len(exact) == 1:
            w = exact[0]
        elif len(ok) == 1 and not exact:
            w = ok[0][0]
            f, _m, last = _parts(name)
            if any(x is not w and _parts(x["name"])[2] == last
                   and _parts(x["name"])[0][:1] == f[:1] for x in pool if _parts(x["name"])):
                return None
        else:
            return None
        return (w["label"], w["slug"], w["chamber"])
    return find


def load_winners(site, collected):
    """(winners, what to say): election_winners for the newest results in
    `collected`, or ([], why) where there are none to read."""
    import build_members_elect as BME
    path = BME.newest_results(collected)
    if path is None:
        return [], f"no election results in {collected}/: no sponsor is matched to a winner"
    try:
        results = BME.read_results(path)
    except BME.Refused as e:
        return [], f"{path} refused ({e}): no sponsor is matched to a winner"

    def rd(n, default):
        f = Path(site) / n
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else default
    people = (rd("legislators.json", []) or []) + (rd("former.json", []) or [])
    # The races as the members-elect file has them, and from Organization Day,
    # when it retires, as election_races works them out again: a winner the
    # file linked keeps that link on 2 December.
    drawn, _turned, _term, _why = election_races(site, collected)
    ws = election_winners(results, drawn or {},
                          (rd("elect_pages.json", {}) or {}).get("pages") or [], people,
                          titled=elect_window(site))
    return ws, f"{len(ws)} winners of {path.name} to match a sponsor to, where the roster has nobody"


def party_of(label):
    """The party letter a sponsor's label ends with -- "Rep. Ellen Read (D)", a
    member-elect's "Jane Doe (R)" -- or "" where the label has none (a sponsor
    who matched nobody is not given one). The roster's label is the one place
    a sitting member's and a member-elect's party are both written, so this is
    read from it, as the card does (app.js cardSponsor), never from the name."""
    m = re.search(r"\(([A-Z])\)\s*$", str(label or ""))
    return m.group(1) if m else ""


def chamber_of(body):
    """H or S for a request's kind (HB, SR, HCR ...); None for a
    constitutional amendment request, which either chamber may file."""
    b = str(body or "").upper()
    return None if b.startswith("CA") else (b[:1] if b[:1] in ("H", "S") else None)


LSR_NO = re.compile(r"^(\d{4})-(\d+)$")


def became_bills(bills, lsrs):
    """{request number: "HB 45"} for the requests that are bills now.

    A request that is drafted and introduced keeps its number as the bill's
    LSR: 2027-0001 becomes whatever bill carries LSR 2027-0001. fetch_lsrs
    marks a request that leaves its list withdrawn, because the list alone
    cannot tell a withdrawal from an introduction, and in December and
    January that would have put "Withdrawn" on every request introduced in
    that time. The bills can tell: data/bills.json is {term: {bill: record}},
    and a record's lsr_year and lsr_num are the request's year and number --
    matched as integers, the list padding "0001" where the bills write none.
    """
    return {num: re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", bid)
            for num, (bid, _rec) in request_bills(bills, lsrs).items()}


def request_bills(bills, lsrs):
    """{request number: (bill, its record)} for the requests that are bills
    now, matched as became_bills says: became_bills and filed_days both read
    this, so the day a request is dated by is its own bill's."""
    want = set()
    for r in lsrs:
        m = LSR_NO.match(str(r.get("lsr") or "").strip())
        if m:
            want.add((m.group(1), int(m.group(2))))
    if not want:
        return {}
    have = {}
    for byb in (bills or {}).values():
        for bid, rec in byb.items():
            y, n = str(rec.get("lsr_year") or ""), str(rec.get("lsr_num") or "")
            if n.isdigit() and (y, int(n)) in want:
                have[(y, int(n))] = (bid, rec)
    return {f"{y}-{n:04d}": b for (y, n), b in have.items()}


# A day as a bill's record writes made_bill.
ISO_DAY = re.compile(r"^\d{4}-\d\d-\d\d$")


def introduced_days(site, bills_of, year, today):
    """{request number: "YYYY-MM-DD"} for the requests whose bill was
    introduced on or before `today` (A REQUEST STAYS A REQUEST UNTIL IT IS
    INTRODUCED): the Introduced stop of the bill's own rail in the bill
    search's rows for the requests' term (site/idx/<term>.json, which
    build_site_v2 writes before this runs: index_rail's ["Ip", day], the day
    the bill's introduction row states, _j_introduced), where it carries a day
    and that day has come. A bill whose docket only plans it -- "To Be
    Introduced 01/06/2027 and referred to ...", which no introduction reader
    takes -- has no day there, and is not introduced yet. `bills_of` is
    {request number: (bill, record)} (request_bills)."""
    from terms import term_of_year
    f = Path(site) / "idx" / f"{term_of_year(int(year))}.json"
    try:
        rows = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []
    except (OSError, ValueError):
        rows = []
    rail = {r.get("id"): r.get("rail") for r in rows if isinstance(r, dict)}
    out = {}
    for num, (bid, _rec) in (bills_of or {}).items():
        stops = rail.get(bid) or []
        first = stops[0] if stops and isinstance(stops[0], (list, tuple)) else []
        day = str(first[1]) if len(first) > 1 and str(first[0]) == "Ip" else ""
        if ISO_DAY.match(day) and day <= str(today):
            out[num] = day
    return out


def filed_days(bills, lsrs):
    """{request number: "YYYY-MM-DD"} for the requests that are bills now
    whose bill's record gives the day it was made one: "made_bill", the
    General Court's database's Legislation.DateLSRBill, which
    fetch_status_db.py reads into bill_status.json and build_data.py keeps on
    the bill (the owner's approval, 15 November 2026, for the day Filed is
    dated by). A record with no day, or with anything that is not a day,
    gives none, and its Filed stop stays reached and undated."""
    out = {}
    for num, (_bid, rec) in request_bills(bills, lsrs).items():
        day = str(rec.get("made_bill") or "").strip()
        if not ISO_DAY.match(day):
            continue
        try:
            datetime.date.fromisoformat(day)
        except ValueError:
            continue
        out[num] = day
    return out


def route(body):
    """The stops a request's bill will pass once it is introduced, in order,
    for its page's rail (Alice, 11 November 2026: the page is a bill's with
    the parts that do not exist yet left quiet): the chamber it starts in,
    then the other, the Governor and Law; a resolution of one chamber has
    that chamber and whether it is adopted; a concurrent resolution has two
    chambers and no Governor; a constitutional amendment goes to the voters,
    and its kind does not say which chamber it starts in, so none is named.
    These are build_site_v2.journey_rail's own routes, by the kind the
    request names."""
    b = str(body or "").upper()
    first = {"H": "House", "S": "Senate"}.get(b[:1])
    other = {"House": "Senate", "Senate": "House"}.get(first)
    if b.startswith("CA"):
        return ["Voters"]
    if not first:
        return []
    if b in ("HR", "SR"):
        return [first, "Adopted"]
    if b in ("HCR", "SCR"):
        return [first, other]
    return [first, other, "Governor", "Law"]


# WHAT A REQUEST'S STATUS SAYS (the owner, 13 November 2026: "Status can be
# added as a filter ... for Requested and Filed (when they publish the draft
# text), and I believe most bills are introduced on the same day"). Requested:
# no bill yet. Filed: the request's bill exists, which is when its text is
# public -- the General Court's list has no field for the draft text, and a
# request becomes a bill when it is introduced, so the bill's existence is the
# fact there is (or the source's own "filed", once it gives one). Withdrawn:
# as the source says. The words are the owner's, and the card, the filter and
# the request page's rail all use them.
# AND INTRODUCED (the owner, 17 November 2026: requests "do not become bills
# until the first session in January when they are introduced"): the third of
# her stages (14 November: "requested, filed, and introduced"), reached when
# the request's bill's docket says it was introduced (introduced_days). Filed
# is also the request whose text the list links before any bill of it is on
# file: the text is public.
REQUESTED, FILED, INTRODUCED, WITHDRAWN = "Requested", "Filed", "Introduced", "Withdrawn"

# THE TEXT, ONCE IT IS PUBLIC (the owner, 17 November 2026: "Once the
# co-sponsors and sponsor have signed off, the bill text shows as a PDF on the
# lsr search page"). The night fetches each text the list links and reads it
# (fetch_lsrs.py --texts and --read-texts) into this folder, a .txt a request;
# the request's page and card and its file in the data API read it through
# request_text. fetch_lsrs.TEXTS names the same folder.
REQUEST_TEXTS = Path("archive/lsr_text")


def request_text(num, folder=None):
    """The text the night read off request `num`'s PDF ("2027-0001"), as
    pdftotext -layout set it, with the margin every line shares taken off,
    trailing spaces and page breaks gone and no two blank lines in a row; ""
    where none is on file. Read by machine: the PDF is the document."""
    try:
        raw = (Path(folder or REQUEST_TEXTS) / f"{num}.txt").read_text(encoding="utf-8",
                                                                        errors="replace")
    except OSError:
        return ""
    lines = [ln.rstrip() for ln in raw.replace("\f", "\n").splitlines()]
    pad = min((len(ln) - len(ln.lstrip()) for ln in lines if ln.strip()), default=0)
    out = []
    for ln in lines:
        if ln.strip():
            out.append(ln[pad:])
        elif out and out[-1]:
            out.append("")
    return "\n".join(out).strip()

# WHAT AN ABBREVIATION IN A REQUEST'S NUMBER STANDS FOR (the owner, 13
# November 2026: "LSR stands for Legislative service request if you can add
# that as a tooltip"). New Hampshire's shape stays here: meta.requests carries
# it, and the page writers read it from there.
ABBR = {"LSR": "Legislative Service Request"}


def rail_stops(r):
    """A request's own rail, three stops, as the row carries it (`rail`) for
    its card and its page to draw with the bill's rail component
    (components.rail_html, railHtml) -- the card's since the owner's word of
    15 November 2026: "adding the rail on the card", as a bill's card has one.

    The three stops (Alice, 12 November 2026, from a phone screenshot where the
    bill's six stops ran into one another: "a separate rail for the requests
    with Requested, Filed meaning the text is publicly available, and
    Introduced"): Requested, always reached -- a withdrawn request was still
    requested (the owner, the same morning: "Request being withdrawn should
    still show request as green but filed as red"); Filed, reached once the
    bill's text is public, and the cross where the request was withdrawn
    instead; Introduced, which a request reaches when its bill is introduced,
    the day its address starts to forward to the bill's page (below).

    THE DAYS. Filed carries the day the text became public where the row has
    it ("filed", "YYYY-MM-DD"): the day the request's bill was made one, which
    rows_from takes from the bill's record (filed_days: made_bill, the General
    Court's database's Legislation.DateLSRBill, the owner's approval of 15
    November 2026), or the source row's own "filed" once the source gives one.
    Requested carries none: the list gives no day a request was made, and the
    General Court's public database gives "True" where the day it was entered
    would be (DateLSREntered). A stop with no day shows none, never a guess.

    INTRODUCED IS REACHED NOW (the owner, 17 November 2026; A REQUEST STAYS A
    REQUEST UNTIL IT IS INTRODUCED): a request stays one until its bill is
    introduced, so its card and its page show the stop reached, dated by the
    day its bill's introduction row states ("introduced_on", introduced_days),
    the day its address starts to forward to the bill's page."""
    gone = bool(r.get("withdrawn"))
    filed = r.get("filed") and not gone
    day = r["filed"] if filed and isinstance(r["filed"], str) and r["filed"][:1].isdigit() else ""
    intro = "" if gone else str(r.get("introduced_on") or "")
    # WHAT THE RAIL SAYS TO A READER WHO HEARS IT, OR HOVERS (its aria-label and
    # title): a stop not reached yet is "not yet" -- the bill rail's "never
    # reached" is said of a stop a finished bill never got to, and a request is
    # still on its way (15 November 2026, seen on the preview of the cards).
    return [
        {"stop": REQUESTED, "mark": "p", "say": "made"},
        {"stop": FILED, "mark": "x" if gone else ("p" if filed else "-"),
         **({"date": day} if day else {}),
         "say": "Withdrawn" if gone else ("Text public" if filed else "not yet")},
        {"stop": INTRODUCED, "mark": "p" if intro else "-", **({"date": intro} if intro else {}),
         "say": INTRODUCED if intro else "never reached" if gone else "not yet"}]


def title_key(title):
    """A title as it is compared for History: case, spacing and final
    punctuation set aside, and nothing else (the owner, 13 November 2026:
    "certain matches only"). No fuzzy match."""
    t = re.sub(r"\s+", " ", str(title or "").strip().lower())
    return re.sub(r"[\s.,;:!?]+$", "", t)


def earlier_bills(site, terms, limit=25):
    """{title key: [the bills of that title, newest first]} from the bill
    search's own rows (site/idx/<term>.json, as build_site_v2 wrote them), for
    the terms meta.json names. Each is {"id", "n", "year", "term", "word",
    "cls"}: its number, year, the word its card says (components.card_word
    of the chip) and the class that colours that chip. A bill
    with no title says nothing, and a title is kept for at most `limit`
    bills."""
    import components as C
    out = {}
    for t in terms or []:
        f = Path(site) / "idx" / f"{t}.json"
        if not f.is_file():
            continue
        for b in json.loads(f.read_text(encoding="utf-8")):
            k = title_key(b.get("title"))
            if not k or b.get("lsr"):
                continue
            chip = b.get("chip") or b.get("status") or ""
            ch = C.WORDBOOK["chips"]
            # The chip's class as the bill card draws it (app.js chipCls).
            cls = (ch["chip"].get(chip) or ch.get("by_status", {}).get(b.get("status") or "")
                   or ch["kind"].get(b.get("kind") or "") or "")
            out.setdefault(k, []).append({
                "id": b.get("id"), "n": b.get("n") or b.get("id"), "year": b.get("year"),
                "term": b.get("term") or t, "word": C.card_word(chip, b.get("passage") or ""),
                "cls": cls})
    for v in out.values():
        v.sort(key=lambda x: (str(x["term"]), str(x["n"])), reverse=True)
        del v[limit:]
    return out


def history_of(title, year, earlier):
    """The bills of a session before `year` whose title is this request's, by
    title_key, newest term first; [] where there is none (no History)."""
    if not earlier:
        return []
    return [b for b in earlier.get(title_key(title), [])
            if str(b.get("term") or "")[:4].isdigit() and int(str(b["term"])[:4]) < int(year)]


def rows_from(lsrs, who, became=None, year=None, winners=None, earlier=None, filed_on=None,
              introduced_on=None, texts=None, forms=None):
    """The rows of idx/<year>-requests.json and the sponsor names that matched
    nobody. `became` (became_bills) names each request's bill; `year` is the
    session they are listed under (newest_session); `winners`
    (election_winners) settle a sponsor the roster did not; `earlier`
    (earlier_bills) is what a request's History is read from; `filed_on`
    (filed_days) is the day each request's bill was made one;
    `introduced_on` (introduced_days) the day its bill was introduced, the
    one thing that forwards its address to the bill's page; `texts` the
    requests whose text the night has read (request_text), which carry
    "text_on_file" for their card's and their page's Bill Text tab;
    `forms` (name_forms) the owner's confirmed forms of a name: a sponsor
    written as one that matches nobody is matched as the other is, once,
    and a form not there matches only as it is written."""
    year = year or newest_session(lsrs)[0]
    find = winner_finder(winners) if winners else (lambda name, body: None)
    term, _label = requests_term(year)
    # The pages the winners of each whole name link to, a winner with none
    # counted as somebody else: a constitutional amendment request's member-
    # elect holds only where no other winner has their name (match, below).
    named = {}
    for i, w in enumerate(winners or []):
        for n in w.get("names") or [w["name"]]:
            named.setdefault(_fold(n), set()).add(w.get("slug") or f"#{i}")

    def match(name, body):
        """as_written, and where that finds nobody, the form the owner
        confirmed this one is (`forms`), matched by the same rules."""
        hit = as_written(name, body)
        other = (forms or {}).get(_fold(name)) if name and not hit else None
        return as_written(other, body) if other else hit

    def as_written(name, body):
        """(label, slug[, chamber]) for a sponsor's name, or None.

        A member-elect's match holds only for a request of their chamber -- or
        for a constitutional amendment request, which either chamber may file,
        where no winner of another page has the whole name (17 November 2026:
        CACR 2027-0646, Colin Mitchell's, matched nobody while his House
        requests were his). Where the roster has nobody, a winner of the
        election (winner_finder); for a constitutional amendment request only
        where no sitting member or member-elect has the name either."""
        hit = who.get(_fold(name))
        if hit and len(hit) > 2 and chamber_of(body) != hit[2]:
            if chamber_of(body) is not None or named.get(_fold(name), {hit[1]}) - {hit[1]}:
                hit = None
        if name and not hit and not (chamber_of(body) is None and _fold(name) in who):
            hit = find(name, body)
        return hit
    rows, unmatched = [], []
    for r in lsrs:
        num = str(r.get("lsr") or "").strip()
        if not num:
            continue
        m = LSR_NO.match(num)
        key = f"{m.group(1)}-{int(m.group(2)):04d}" if m else num
        bill = (became or {}).get(key, "")
        # Introduced only as a bill: the day its bill's docket says so.
        intro = (introduced_on or {}).get(key, "") if bill else ""
        # The text the list links, where it is the General Court's own (fetch_lsrs.gc_url).
        pdf = str(r.get("text_pdf") or "")
        pdf = pdf if pdf.startswith(("https://", "http://")) else ""
        body = str(r.get("body") or "").upper()
        name = str(r.get("sponsor") or "").strip()
        hit = match(name, body)
        if name and not hit:
            unmatched.append(name)
        # The co-sponsors, matched as the prime sponsor is (a name that
        # matches nobody is kept as the source gives it), for the request's
        # own page; a request with none carries no key.
        co = []
        for c in r.get("cosponsors") or []:
            c = str(c or "").strip()
            h = match(c, body)
            if c:
                co.append({"label": h[0] if h else c, "slug": h[1] if h else "", "name": c,
                           **({"party": party_of(h[0])} if h and party_of(h[0]) else {})})
        rows.append({
            "id": "LSR" + num.replace("-", ""),
            "n": "LSR " + num,
            "year": session_of(r) or year,
            "title": (r.get("title") or "").strip(),
            "sponsor": name,
            "sponsor_label": hit[0] if hit else name,
            "sponsor_slug": hit[1] if hit else "",
            # THE PARTY, which the bill search's Sponsor filter reads (12
            # November 2026: "party affiliation of returning or new members"):
            # a sitting member's and a member-elect's alike, from the label
            # the roster gave them. Absent where nobody matched, which the
            # filter says as "Party not on file".
            **({"sponsor_party": party_of(hit[0])} if hit and party_of(hit[0]) else {}),
            # The co-sponsors' names, as a bill's row has them (`cosp`), so
            # the Sponsor filter's "Include co-sponsored" reads a request as
            # it reads a bill. The source gives none today.
            **({"cosp": [c["name"] for c in co]} if co else {}),
            **({"cosponsors": co} if co else {}),
            "body": body,
            "body_label": BODY.get(body, body),
            "committee": "", "committees": [], "topic": "", "topic_by": "",
            # No status KIND: an LSR has not reached a stage the Status facet
            # names. The word on the card is the one fact there is about where
            # it stands.
            "kind": "",
            "status": (INTRODUCED if intro else FILED if bill else WITHDRAWN if r.get("withdrawn")
                       else FILED if r.get("filed") or pdf else REQUESTED),
            "status_stated": True,
            "withdrawn": bool(r.get("withdrawn")) and not bill,
            "term": term, "carried": False, "passage": "",
            "last_action": "", "nrc": 0, "votedays": [],
            "lsr": True,
            # "introduced" is the number of the bill the request was filed as
            # (the key's name is older than A REQUEST STAYS A REQUEST UNTIL IT
            # IS INTRODUCED); "introduced_on" the day that bill was introduced.
            **({"introduced": bill, "bill_at": bill_address(bill, session_of(r) or year)}
               if bill else {}),
            **({"introduced_on": intro} if intro else {}),
            # "filed": the text is public (true, or its day) -- the stop Filed
            # on the request's rail. The list carries nothing of the kind
            # yet; this passes it on when the source gives it. Else, once the
            # request is a bill, the day the bill was made one where its
            # record gives it (filed_on), and true where it does not; and
            # true where the list links its text (THE TEXT, ONCE IT IS PUBLIC).
            **({"filed": r["filed"]} if r.get("filed") else
               {"filed": (filed_on or {}).get(key) or True} if bill else
               {"filed": True} if pdf and not r.get("withdrawn") else {}),
            # The General Court's PDF of its text, and whether the night has
            # read it (the Bill Text tab of its card and its page).
            **({"text_pdf": pdf} if pdf else {}),
            **({"text_on_file": True} if key in (texts or ()) else {}),
            # HISTORY (the owner, 13 November 2026): an earlier bill, of any
            # term on the site, whose title is this request's.
            **({"history": h} if (h := history_of(r.get("title"), session_of(r) or year,
                                                  earlier)) else {}),
            # A REQUEST'S OWN PAGE (Alice, 8 November 2026): its address, from
            # the number this source gives it -- New Hampshire's shape stays
            # here, and the page writer reads only "address" and "moved_to".
            "address": REQUEST_ADDRESS.format(num=num),
            # Once its bill is introduced, its address forwards to the bill's
            # page; filed and not yet introduced, it keeps its own (A REQUEST
            # STAYS A REQUEST UNTIL IT IS INTRODUCED).
            **({"moved_to": bill_address(bill, session_of(r) or year)} if intro else {}),
        })
    for row in rows:
        row["rail"] = rail_stops(row)
    rows.sort(key=lambda x: x["n"])
    return rows, unmatched


def with_sponsor_names(rows, names):
    """EVERY NAME THE SITE PRINTS FOR A REQUEST'S SPONSOR (the pre-release
    review of 13 November 2026). The card's label and the page it links to may
    spell a sponsor otherwise than the list does -- "Lee C. Nyquist", the
    results' spelling, for "Lee Nyquist"; "James Creighton", his page's, for
    "Jim Creighton" -- and a name copied off either found none of their
    requests. Each row of rows_from gets those names as `sponsor_names`: its
    label's name, where the label is not the list's words, and the name on
    the page its slug points to (`names`, page_names), each once and only
    where the list's own spelling is not already it. "Already it" is the
    words the search reads (_words): a full stop is no difference, and a
    hyphen or a space is one ("Mary-Jane" is two words, "Maryjane" one). The
    bill search reads them beside `sponsor` (app.js sponsorNames). Returns
    how many rows got one; a row with none carries no key."""
    n = 0
    for r in rows:
        name = str(r.get("sponsor") or "")
        label = str(r.get("sponsor_label") or "")
        also = []
        for x in (label_name(label) if label != name else "",
                  (names or {}).get(r.get("sponsor_slug") or "", "")):
            if x and _words(x) != _words(name) and all(_words(x) != _words(y) for y in also):
                also.append(x)
        if name and also:
            r["sponsor_names"] = also
            n += 1
    return n


# Where a request's page is: /request/2027-0001, as a bill's is
# /bill/2026/hb1034.
REQUEST_ADDRESS = "request/{num}"

# THE DAY FILING FOR A SESSION IS COMPLETE, by the session's year, entered by
# a person when the General Court's list stops growing (Alice, 8 November
# 2026: "the remaining request pages retire, each forwarding to its prime
# sponsor's page"). Until it is entered, no request page retires.
FILING_COMPLETE = {}


def bill_address(bill, year):
    """'HB 45' of 2027 -> 'bill/2027/hb45', the bill's own page."""
    return f"bill/{year}/{str(bill).replace(' ', '').lower()}"


def retire(rows, year, today):
    """From the day filing is complete (FILING_COMPLETE), each request still
    a request -- not a bill and not withdrawn -- forwards to its prime
    sponsor's page, or to the requests' list where the sponsor has none. A
    withdrawn request keeps its page, as a withdrawn bill does."""
    done = FILING_COMPLETE.get(int(year)) if year else None
    if not done or today < done:
        return 0
    n = 0
    for r in rows:
        # Not one filed (its bill numbered or its text public): it stays a
        # request until its bill is introduced, when it forwards to the bill.
        if not r.get("moved_to") and not r.get("withdrawn") and not r.get("filed"):
            r["moved_to"] = (f"legislator/{r['sponsor_slug']}" if r.get("sponsor_slug")
                             else f"bills?term={r['term']}")
            n += 1
    return n


def election_races(site, collected="collected", hand_path=None):
    """(races, turned, term, why) for the newest general election: its races
    as the members-elect step draws them ("races" of site/members_elect.json),
    whether the roster is the term it elected, that term, and what to say
    where it cannot be read.

    THE FILE RETIRES ON ORGANIZATION DAY (the rehearsal of 17 November 2026).
    members_elect.json is written only until 2 December 2026, and the night
    of 2 December brought back every withdrawn request of a member not
    returning as "Withdrawn", against the owner's rule of 12 November
    (not_returning). So while the file is there its races are read; from
    Organization Day, while the roster is still the term the election ended,
    the same races are worked out again from the same results, hand file and
    roster (build_members_elect.members_elect, as build_elect_pages calls it
    outside the window); and once the roster is the new term's (site/
    meta.json's newest term is the results' own) there are none to read --
    `turned`, and the roster itself says who came back (departed)."""
    import build_date
    import build_members_elect as BME
    site = Path(site)

    def rd(name, default):
        p = site / name
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default
    try:
        path = BME.newest_results(collected)
        results = BME.read_results(path) if path else None
        term = str((results or {}).get("term") or "")
        terms = (rd("meta.json", {}) or {}).get("terms") or []
        if term and terms and terms[0] == term:
            return None, True, term, ""
        if (site / "members_elect.json").is_file():
            doc = rd("members_elect.json", {}) or {}
            return doc.get("races") or {}, False, str(doc.get("term") or term), ""
        if not results or not terms or terms[0] != BME.term_before(term):
            return None, False, term, ""
        today = build_date.today()
        if today <= datetime.date.fromisoformat(results["election"]):
            return None, False, term, ""
        hand, _note = BME.read_hand(Path(hand_path or BME.HAND_DEFAULT), results["election"])
        races, _report = BME.members_elect(results, rd("legislators.json", []),
                                           rd("former.json", []), rd("districts.json", {}),
                                           hand, today.isoformat())
        return races, False, term, ""
    except (BME.Refused, OSError, ValueError, KeyError) as e:
        return None, False, "", (f"WARNING: the newest election's races could not be read "
                                 f"({type(e).__name__}: {e}): no withdrawn request is dropped "
                                 "as a member's not returning")


def not_returning(site, collected="collected", hand_path=None, year=None):
    """({slug: why}, {slug: why not decided}) for the sitting members, from
    the 2026 election's results (site/members_elect.json, build_members_elect).

    Alice, 12 November 2026: "Bills that were requested by members before the
    election but the members lost reelection can be removed without being
    labeled as withdrawn." After an election the General Court drops the
    requests of members who are not coming back, and the list alone cannot
    say why a request left it.

    BY IDENTITY, NEVER BY NAME. A sitting member is not returning when their
    own race is decided (nothing not_final, nothing held) and their slug is
    not among the slugs of that election's winners (each elected entry of a
    sitting member carries "s"). Lost, retired, or ran for another office:
    the file does not say which and the rule does not need it. A name check
    flags 169 standing requests falsely (nicknames, spellings), so none is
    made here. A member whose race is not decided, or is in no race the file
    lists, is not decided: the second dict, and their requests are left as
    they are.

    AND FROM ORGANIZATION DAY, WHEN THE FILE RETIRES (election_races; the
    rehearsal of 17 November 2026): the same races, worked out again, while
    the roster is still the term the election ended; and once the roster is
    the new term's, each member of the term before who is not on it
    (departed), by their page's slug -- the roster is then the record of who
    came back, and every race is decided."""
    lp = site / "legislators.json"
    if not lp.exists():
        return {}, {}
    races, turned, term, _why = election_races(site, collected, hand_path)
    if turned:
        return {m["slug"]: f"not on the {term} roster"
                for m in departed(site, collected, year)}, {}
    if races is None:
        return {}, {}
    won = {e.get("s") for r in races.values() for e in r.get("elected") or []
           if e.get("s")}
    gone, open_ = {}, {}
    for m in json.loads(lp.read_text(encoding="utf-8")):
        slug = m.get("slug")
        if not slug or slug in won:
            continue
        key = (f"H|{m.get('county')}|{m.get('district')}" if m.get("chamber") == "H"
               else f"S|{m.get('district')}")
        race = races.get(key)
        if race is None:
            open_[slug] = f"no race {key} in members_elect.json"
        elif race.get("not_final") or race.get("held"):
            open_[slug] = f"race {key} is not final"
        else:
            gone[slug] = f"not among the winners of {key}"
    return gone, open_


def drop_unreturned(rows, gone):
    """(kept rows, the rows dropped): a request that left the General Court's
    list (withdrawn, and not a bill) whose prime sponsor, identified by slug,
    is not returning is dropped -- no page, not counted, forwarded to the
    requests' list by build_pages.moved_requests. A request still on the
    list is never dropped, whatever its sponsor, and a withdrawn request of a
    returning member, or of a sponsor with no slug, is left as it is."""
    kept, dropped = [], []
    for r in rows:
        slug = r.get("sponsor_slug")
        (dropped if r.get("withdrawn") and slug and slug in gone else kept).append(r)
    return kept, dropped


def unreturned_of(requests, site, collected="collected", year=None):
    """(the requests of `requests` this step would drop as a member's not
    returning, what to say where that could not be worked out): for the
    night's guard on a list that loses many requests (nightly.take_lsrs; the
    nights of 19 and 20 November 2026, which refused the list for the 78
    requests the election took off it). `requests` are lsrs.json's rows that
    left the list, `site` a folder holding the site's legislators.json,
    former.json, meta.json and, while they are written, members_elect.json and
    elect_pages.json.

    THE SAME DECISION AS main's, never a second one: a sponsor's slug as main
    finds it (roster, the winners, the owner's name forms: rows_from), and
    who is not returning by that slug (not_returning, drop_unreturned). What
    main also passes rows_from -- the bills, the texts, the earlier titles --
    changes no sponsor's slug, and a request gone from the list that the
    docket files as a bill the night has already left out."""
    site = Path(site)
    if not (site / "legislators.json").is_file():
        return [], f"no roster in {site}"
    year = year or newest_session(requests)[0]
    winners, _said = load_winners(site, collected)
    rows, _unmatched = rows_from(requests, roster(site, collected, year), year=year,
                                 winners=winners, forms=name_forms())
    _r, _turned, _t, why = election_races(site, collected)
    gone, _undecided = not_returning(site, collected, year=year)
    _kept, dropped = drop_unreturned(rows, gone)
    ids = {r["n"] for r in dropped}
    return [r for r in requests if "LSR " + str(r.get("lsr") or "").strip() in ids], why


def with_topics(rows, bills):
    """Each request's initial topic, from its title (request_topics.py: the
    classifier the archived bills' topics came from, its title half only, learned
    from every term's official code), and Miscellaneous where the title gives
    none. Returns how many the title placed. Where there are no labelled bills
    to learn from, only the study and housing rules place one, and it is said;
    so is a night with no past tables, whose model knows the current term alone."""
    import request_topics
    model = request_topics.train_on(bills)
    if model is None:
        print("  no bill of the labelled term in data/bills.json: only the study and housing "
              f"rules place a request; the rest are {request_topics.MISC}")
    else:
        f = model["from"]
        print(f"  request topics learned from {f['current']:,} titles of the current term "
              f"(x{request_topics.CURRENT_WEIGHT}) and {f['archived']:,} archived titles with an "
              "official code" + ("" if f["archived"] else
                                  " -- no past tables here (db/past): the current term alone"))
    got = request_topics.assign(rows, model)
    return sum(n for t, n in got.items() if t != request_topics.MISC)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--src", default="lsrs.json")
    ap.add_argument("--bills", default="data/bills.json",
                    help="the bills, to tell a request that became one from a withdrawal")
    ap.add_argument("--collected", default="collected",
                    help="the election results, to match a sponsor to a winner")
    a = ap.parse_args()
    site, src = Path(a.site), Path(a.src)

    if not src.exists():
        print(f"  no {src} -- nothing to build. Run fetch_lsrs.py first.")
        return 0
    lsrs = json.loads(src.read_text(encoding="utf-8"))
    # SILENCE IS NOT SUCCESS. A source file that parsed to an empty list would
    # otherwise write an empty term, and the option would appear in the picker
    # naming nothing.
    assert isinstance(lsrs, list) and lsrs, f"{src} holds no requests"
    year, lsrs, older = newest_session(lsrs)
    assert year and lsrs, f"{src} names no session a request can be listed under"
    term, label = requests_term(year)

    bp = Path(a.bills)
    bills = json.loads(bp.read_text(encoding="utf-8")) if bp.exists() else {}
    became, days = became_bills(bills, lsrs), filed_days(bills, lsrs)
    import build_date
    today = build_date.today().isoformat()
    intro = introduced_days(site, request_bills(bills, lsrs), year, today)
    # The requests whose text the night has read, by the number as rows_from
    # keys it; the file is under the number as the list writes it.
    texts = {f"{m.group(1)}-{int(m.group(2)):04d}" for r in lsrs
             if (m := LSR_NO.match(str(r.get("lsr") or "").strip()))
             and request_text(str(r["lsr"]).strip())}
    winners, said = load_winners(site, a.collected)
    print(f"  {said}")
    meta0 = json.loads((site / "meta.json").read_text(encoding="utf-8")) if (site / "meta.json").exists() else {}
    rows, unmatched = rows_from(lsrs, roster(site, a.collected, year), became, year, winners,
                                earlier_bills(site, meta0.get("terms")), days, intro, texts,
                                name_forms())
    assert rows, "no request survived shaping, though the source had some"
    with_sponsor_names(rows, page_names(site))
    with_topics(rows, bills)
    _r, turned, _t, why = election_races(site, a.collected)
    if why:
        print(f"  {why}")
    gone, undecided = not_returning(site, a.collected, year=year)
    rows, dropped = drop_unreturned(rows, gone)
    assert rows, "every request was dropped as a not-returning member's"
    retired = retire(rows, year, today)
    idx = site / "idx"
    idx.mkdir(parents=True, exist_ok=True)
    # The previous session's file, if this is the night a new session's
    # requests replace it: meta.json names only the one written below, and a
    # file it does not name is one nothing links.
    for old in idx.glob("*-requests.json"):
        if old.name != f"{term}.json":
            old.unlink()
    (idx / f"{term}.json").write_text(json.dumps(rows, separators=(",", ":")),
                                      encoding="utf-8")

    mj = site / "meta.json"
    assert mj.exists(), ("meta.json is not written yet -- this step runs after "
                         "build_site_v2.py, which writes it")
    meta = json.loads(mj.read_text(encoding="utf-8"))
    # by_slug: each matched sponsor's slug and how many requests are theirs,
    # so a member's page knows to offer the requests term, and opens on it,
    # without asking for the list first (Alice, 7 November 2026).
    by_slug = {}
    for r in rows:
        if r["sponsor_slug"]:
            by_slug[r["sponsor_slug"]] = by_slug.get(r["sponsor_slug"], 0) + 1
    meta["requests"] = {"term": term, "label": label, "year": year, "n": len(rows),
                        "abbr": ABBR,
                        "withdrawn": sum(1 for r in rows if r["withdrawn"]),
                        # How many are bills introduced, and so forward to them.
                        "introduced": sum(1 for r in rows if r.get("introduced_on")),
                        # AND HOW MANY IN THE SESSION ITSELF, on a day of the
                        # requests' own year -- not Organization Day's
                        # resolutions, introduced and adopted the December
                        # before: the bill search opens on the requests until
                        # one is (app.js requestsFirst; the owner, 17 November
                        # 2026: bills "are introduced and referred to
                        # committees" at "the first session in January").
                        "introduced_in_session": sum(
                            1 for r in rows if str(r.get("introduced_on") or "")[:4] == str(year)),
                        "dropped": sorted(r["address"] for r in dropped),
                        "by_slug": dict(sorted(by_slug.items()))}
    mj.write_text(json.dumps(meta), encoding="utf-8")

    by = {}
    for r in rows:
        by[r["body"]] = by.get(r["body"], 0) + 1
    kinds = ", ".join(f"{k} {n}" for k, n in sorted(by.items(), key=lambda x: -x[1]))
    print(f"  {len(rows)} bill requests for {year} -> idx/{term}.json ({kinds})")
    if older:
        print(f"  {older} request(s) of an earlier session left out: bills or withdrawn by now")
    # Counted on the rows written, after the drops: one list, one count.
    misc_n = sum(1 for r in rows if r.get("topic") == "Miscellaneous")
    topic_n = sum(1 for r in rows if r.get("topic")) - misc_n
    print(f"  {topic_n} of {len(rows)} given a topic from the title; {misc_n} are Miscellaneous "
          "(the Topic filter lists them, a card prints none)")
    print(f"  {sum(1 for r in rows if r.get('history'))} of {len(rows)} have an earlier bill of "
          "the same title (History)")
    print(f"  {meta['requests']['withdrawn']} withdrawn; "
          f"{sum(1 for r in rows if r['sponsor_slug'])} sponsors matched to a member")
    also = [r for r in rows if r.get("sponsor_names")]
    if also:
        who = sorted({r["sponsor"] for r in also})
        print(f"  {len(also)} request(s) whose sponsor the card or their page names otherwise than "
              "the list, found by either name: " + ", ".join(who[:6]) + (" ..." if len(who) > 6 else ""))
    if dropped:
        print(f"  {len(dropped)} withdrawn request(s) of members not returning dropped, "
              "forwarding to the list"
              + (" (the roster says who came back)" if turned else "")
              + ": " + ", ".join(r["n"] for r in dropped))
    stuck = [r["n"] for r in rows if r["withdrawn"] and not r["sponsor_slug"]]
    stuck += [r["n"] for r in rows if r["withdrawn"] and r["sponsor_slug"] in undecided]
    if stuck:
        print(f"  {len(stuck)} withdrawn request(s) kept, the sponsor not identified or "
              "their race not decided: " + ", ".join(stuck))
    if became:
        print(f"  {len(became)} filed as bills, each marked with its bill; {len(days)} with the "
              f"day the bill was made one, on Filed; {len(intro)} introduced, its page forwarding "
              "to the bill's, the rest still requests until they are")
    linked = sum(1 for r in rows if r.get("text_pdf"))
    if linked or texts:
        print(f"  {linked} link their text on the General Court's list; {len(texts)} with the text "
              "read, for their Bill Text tab")
    if retired:
        print(f"  filing is complete: {retired} request page(s) retired, each forwarding to "
              "its prime sponsor's page")
    if unmatched:
        seen = sorted(set(unmatched))
        print(f"  {len(seen)} sponsor name(s) matched nobody on the roster: "
              + ", ".join(seen[:6]) + (" ..." if len(seen) > 6 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
