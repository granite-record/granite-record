#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.16
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

The rows carry no committee and no status kind, because an LSR has neither.
That is not missing data, and those two facets are correct to show nothing
for this term. A row carries a topic only where request_topics reads one from
its title (`topic_by` "title", with_topics below), which is why the Topic
facet of this term says "(from the title)"; the rest carry none.
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


def roster(site):
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
        for p in json.loads(ep.read_text(encoding="utf-8")).get("pages") or []:
            key = _fold(p.get("name"))
            party = f" ({p['party']})" if p.get("party") else ""
            out[key] = None if (key in out or key in gone) else (
                f"{p.get('name')}{party}", p.get("slug"), p.get("chamber"))
    return out


# "Rep. " or "Sen. " before a name, which a label carries and a name does not.
_TITLE = re.compile(r"^(?:Rep|Sen)\.\s*")


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
    "Rep. Ellen Read (D)" -> "Ellen Read", "Lee C. Nyquist (D)" -> "Lee C. Nyquist"."""
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


def election_winners(results, drawn, pages, people):
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
    they ran under. A tie (elected not True) names nobody."""
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
            out.append({"name": name, "party": party, "chamber": ch, "race": key,
                        "slug": slug, "label": f"{name} ({party})" if party else name})
    return out


def winner_finder(winners):
    """find(name, body) -> (label, slug, chamber) or None: the winner of the
    request's own chamber the sponsor certainly is.

    CERTAIN means: exactly one winner of that chamber is compatible and either
    the whole name is the same, or no other winner of the chamber shares their
    surname and first initial (so "James Q. Smith" is not settled by "James
    Smith" while a "John Smith" also won). Two winners of the same whole name are
    nobody. A constitutional amendment request (no chamber) is never resolved
    here."""
    def find(name, body):
        ch = chamber_of(body)
        if not ch or not _parts(name):
            return None
        pool = [w for w in winners if w["chamber"] == ch]
        ok = []
        for w in pool:
            good, exact = compatible(name, w["name"])
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
    ws = election_winners(results, (rd("members_elect.json", {}) or {}).get("races") or {},
                          (rd("elect_pages.json", {}) or {}).get("pages") or [], people)
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
                have[(y, int(n))] = re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", bid)
    return {f"{y}-{n:04d}": b for (y, n), b in have.items()}


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
REQUESTED, FILED, WITHDRAWN = "Requested", "Filed", "Withdrawn"

# WHAT AN ABBREVIATION IN A REQUEST'S NUMBER STANDS FOR (the owner, 13
# November 2026: "LSR stands for Legislative service request if you can add
# that as a tooltip"). New Hampshire's shape stays here: meta.requests carries
# it, and the page writers read it from there.
ABBR = {"LSR": "Legislative Service Request"}


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


def rows_from(lsrs, who, became=None, year=None, winners=None, earlier=None):
    """The rows of idx/<year>-requests.json and the sponsor names that matched
    nobody. `year` is the session they are listed under (newest_session);
    `winners` (election_winners) settle a sponsor the roster did not;
    `earlier` (earlier_bills) is what a request's History is read from."""
    year = year or newest_session(lsrs)[0]
    find = winner_finder(winners) if winners else (lambda name, body: None)
    term, _label = requests_term(year)
    rows, unmatched = [], []
    for r in lsrs:
        num = str(r.get("lsr") or "").strip()
        if not num:
            continue
        m = LSR_NO.match(num)
        bill = (became or {}).get(f"{m.group(1)}-{int(m.group(2)):04d}" if m else num, "")
        body = str(r.get("body") or "").upper()
        name = str(r.get("sponsor") or "").strip()
        hit = who.get(_fold(name))
        # A member-elect's match holds only for a request of their chamber.
        if hit and len(hit) > 2 and chamber_of(body) != hit[2]:
            hit = None
        if name and not hit:
            hit = find(name, body)
        if name and not hit:
            unmatched.append(name)
        # The co-sponsors, matched as the prime sponsor is (a name that
        # matches nobody is kept as the source gives it), for the request's
        # own page; a request with none carries no key.
        co = []
        for c in r.get("cosponsors") or []:
            c = str(c or "").strip()
            h = who.get(_fold(c))
            if h and len(h) > 2 and chamber_of(body) != h[2]:
                h = None
            if c and not h:
                h = find(c, body)
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
            "status": (FILED if bill else WITHDRAWN if r.get("withdrawn")
                       else FILED if r.get("filed") else REQUESTED),
            "status_stated": True,
            "withdrawn": bool(r.get("withdrawn")) and not bill,
            "term": term, "carried": False, "passage": "",
            "last_action": "", "nrc": 0, "votedays": [],
            "lsr": True,
            **({"introduced": bill} if bill else {}),
            # "filed": the text is public (true, or its day) -- the stop Filed
            # on the request's rail. The list carries nothing of the kind
            # yet; this passes it on when the source gives it.
            **({"filed": r["filed"]} if r.get("filed") else {"filed": True} if bill else {}),
            # HISTORY (the owner, 13 November 2026): an earlier bill, of any
            # term on the site, whose title is this request's.
            **({"history": h} if (h := history_of(r.get("title"), session_of(r) or year,
                                                  earlier)) else {}),
            # A REQUEST'S OWN PAGE (Alice, 8 November 2026): its address, from
            # the number this source gives it -- New Hampshire's shape stays
            # here, and the page writer reads only "address" and "moved_to".
            "address": REQUEST_ADDRESS.format(num=num),
            # Once it is a bill, its address forwards to the bill's page.
            **({"moved_to": bill_address(bill, session_of(r) or year)} if bill else {}),
        })
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
        if not r.get("moved_to") and not r.get("withdrawn"):
            r["moved_to"] = (f"legislator/{r['sponsor_slug']}" if r.get("sponsor_slug")
                             else f"bills?term={r['term']}")
            n += 1
    return n


def not_returning(site):
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
    they are."""
    ep, lp = site / "members_elect.json", site / "legislators.json"
    if not (ep.exists() and lp.exists()):
        return {}, {}
    races = (json.loads(ep.read_text(encoding="utf-8")).get("races")) or {}
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


def with_topics(rows, bills):
    """Each request's initial topic, from its title (request_topics.py: the
    classifier the archived bills' topics came from, its title half only).
    Returns how many got one; the rest keep none. Where there are no labelled
    bills to learn from, none is given, and it is said."""
    import request_topics
    model = request_topics.train_on(bills)
    if model is None:
        print("  no bill of the labelled term in data/bills.json: no request is given a topic")
        return 0
    return sum(request_topics.assign(rows, model).values())


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
    became = became_bills(json.loads(bp.read_text(encoding="utf-8")) if bp.exists() else {},
                          lsrs)
    winners, said = load_winners(site, a.collected)
    print(f"  {said}")
    meta0 = json.loads((site / "meta.json").read_text(encoding="utf-8")) if (site / "meta.json").exists() else {}
    rows, unmatched = rows_from(lsrs, roster(site), became, year, winners,
                                earlier_bills(site, meta0.get("terms")))
    assert rows, "no request survived shaping, though the source had some"
    with_sponsor_names(rows, page_names(site))
    topic_n = with_topics(rows, json.loads(bp.read_text(encoding="utf-8")) if bp.exists() else {})
    gone, undecided = not_returning(site)
    rows, dropped = drop_unreturned(rows, gone)
    assert rows, "every request was dropped as a not-returning member's"
    import build_date
    retired = retire(rows, year, build_date.today().isoformat())
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
    print(f"  {topic_n} of {len(rows)} given a topic from the title (marked so; "
          "the rest have none)")
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
              "forwarding to the list: " + ", ".join(r["n"] for r in dropped))
    stuck = [r["n"] for r in rows if r["withdrawn"] and not r["sponsor_slug"]]
    stuck += [r["n"] for r in rows if r["withdrawn"] and r["sponsor_slug"] in undecided]
    if stuck:
        print(f"  {len(stuck)} withdrawn request(s) kept, the sponsor not identified or "
              "their race not decided: " + ", ".join(stuck))
    if became:
        print(f"  {len(became)} introduced as bills, each marked with its bill, its page "
              "forwarding to the bill's")
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
