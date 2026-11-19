#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-19.1
"""
A town page's Elections tab (the owner, 19 November 2026: "Town pages should
also have an elections tab organized by election and year which should
eventually include municipal elections"). build_town_pages.py draws it; this
module reads the results and says what each town's ballot held.

WHAT IT READS, and decides nothing about who won:
  collected/election_town_rows_<year>.csv   the State House and State Senate
                                            races' town and ward rows
  collected/election_<year>.json            those races' outcomes, through
                                            build_members_elect.members_elect,
                                            the one rule the elections page
                                            and the member tab draw by
  collected/election_offices_<year>.json    Governor, US Senate, Congress, the
                                            Executive Council and the county
                                            offices, with every town's count
  collected/primary_<year>.json             the State Primary (no town's count
                                            is on file: the race's own count,
                                            said so)
  collected/specials.json                   the special elections (the district's
                                            count: the Secretary of State's page
                                            gives none by town)
and, to link a candidate to a member's page, the member tab's own rows
(build_member_elections.build).

ONE PAGE, ITS OWN COUNTS. A town or a ward page is shown the rows the
Secretary of State's files print for that town or that ward, never a
neighbour's or the district's. A city whose page is one page and whose rows
are by ward (none today) is the sum of its wards' rows. A printed place is
read to the district table's town by its spelling there, by "Ward"/"Wd"/
" - Ward", or by the eight known short forms of the unincorporated places
(place_of); a place read to no town is counted by main and drawn nowhere.

A WARD PAGE FROM 2022 ON. A city's wards were drawn again for the 2022 lines,
and a ward's name across a redistricting is no proof of the same voters (the
elections design's decision 13, approved 19 November 2026), so a ward page
shows the elections held on the lines its districts are drawn on (WARDS_SINCE)
and says so in one line. A town's own ground does not move, so a town page
shows every election on file.

THE ORDER (the owner's request): a heading for each year, newest first; within
a year the general, then the state primary, then each special election, by
day, newest first. Within an election the offices as a ballot gives them:
Governor, US Senate, Congress, the Executive Council, the State Senate, the
State House (each district, the floterial after the town's own), then the
county offices.

WHO WON IS THE RACE'S, NEVER THE TOWN'S. "Won the race" marks the race's
winner as the elections page decides it (members_elect for the House and the
Senate; the offices file's most votes, a tie unsettled, for the rest); the
town's own leader is only the top row. No margin is shown: the race's would
read as the town's, and the town's lead is not the result. Each race links
to its card on the elections page where that page draws it (the House and the
Senate).

A MEMBER'S CHIP LINKS only where the member's own Elections tab carries the
same race (the certain rule, build_member_elections), and a winner's where
the elections page links it; anyone else is named and not linked.

MUNICIPAL ELECTIONS. No source is on hand. When one is, a town's own contests
(entities.contest_id with the town as the district, e.g.
2027-03-09.general.selectboard.hanover, the design's section 4) are one more
kind of election entry here, under their year; nothing is drawn for them
until then.

Nothing here asks the network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import csv
import json
import re
from collections import defaultdict

import build_members_elect as BME
import components as C

E = C.esc
YEARS_RE = re.compile(r"^election_town_rows_(\d{4})\.csv$")
OFFICES = "election_offices_{year}.json"
RESULTS = "election_{year}.json"
TOWN_ROWS = "election_town_rows_{year}.csv"
# The first general election held on the lines today's district table, and so
# each ward page, is drawn on (decision 13, above).
WARDS_SINCE = 2022

# The offices in a ballot's order; the State Senate and House between the
# Council and the county, as a town's ballot prints them.
OFFICE_ORDER = ("president", "governor", "us-senate", "us-house", "executive-council", "S", "H",
                "sheriff", "county-attorney", "county-treasurer", "register-of-deeds",
                "register-of-probate", "county-commissioner")
OFFICE_NAME = {"president": "President", "governor": "Governor", "us-senate": "US Senate",
               "us-house": "US House", "executive-council": "Executive Council",
               "S": "State Senate", "H": "State House", "sheriff": "Sheriff",
               "county-attorney": "County Attorney", "county-treasurer": "County Treasurer",
               "register-of-deeds": "Register of Deeds", "register-of-probate": "Register of Probate",
               "county-commissioner": "County Commissioner"}
COUNTS = ("undervotes", "overvotes", "write_ins_scattered")
PARTY_WORD = {"D": "Democratic", "R": "Republican", "L": "Libertarian"}


# ------------------------------------------------------------------ places ---

WARD_RE = re.compile(r"^(.*?)\s*(?:-\s*)?\b(?:ward|wd\.?)\s*(\d+)$", re.I)
# The short forms the files print for a word of an unincorporated place's name.
SHORT = {"gt": "grant", "pur": "purchase", "loc": "location", "wd": "ward"}


def _tokens(name):
    s = str(name or "").lower().replace("&", " and ")
    s = re.sub(r"'s\b|’s\b", "", s)
    return [SHORT.get(t, t) for t in re.findall(r"[a-z0-9]+", s)]


def _fits(printed, table):
    """Whether the printed words are the table's, each the other's word or a
    short form of it ("Thomp." of "Thompson", "Gilm." of "Gil.")."""
    a, b = _tokens(printed), _tokens(table)
    if len(a) + 1 == len(b) and b[-1] in ("grant", "purchase", "location"):
        b = b[:-1]   # 2026's "Thompson & Meserve's", with no "Purchase"
    return len(a) == len(b) and all(x == y or x.startswith(y) or y.startswith(x)
                                    for x, y in zip(a, b))


class Places:
    """The district table's towns and wards ({town: {ward: ...}}, site/
    districts.json), and the one reading of a printed place onto them."""

    def __init__(self, districts):
        self.wards = {t: set(w) for t, w in districts.items()}
        self.memo = {}

    def place_of(self, printed, spelt=""):
        """(town, ward) of the district table for a place as a file prints it,
        ward "0" for a whole town, or None where it is no town of the table or
        could be more than one. `spelt` is the town rows' own reading
        (place_district_table), where the year has one."""
        key = (printed, spelt)
        if key not in self.memo:
            self.memo[key] = self._place_of(printed, spelt)
        return self.memo[key]

    def _place_of(self, printed, spelt):
        for name in (spelt, printed):
            name = " ".join(str(name or "").split())
            if not name:
                continue
            if name in self.wards:
                return (name, "0")
            m = WARD_RE.match(name)
            if m and m.group(1) in self.wards:
                town, ward = m.group(1), str(int(m.group(2)))
                return (town, ward) if ward in self.wards[town] else (town, "0") \
                    if self.wards[town] == {"0"} else None
        fit = [t for t in self.wards if _fits(printed, t)]
        return (fit[0], "0") if len(fit) == 1 else None

    def page_of(self, place):
        """The page a place's rows belong to: its own, or, for a town drawn as
        one page whose file prints it by ward, the town's."""
        if place is None:
            return None
        town, ward = place
        return place if ward in self.wards.get(town, ()) else None


# ----------------------------------------------------------------- reading ---

def years_on_file(collected):
    return sorted({int(m.group(1)) for p in Path(collected).glob("election_town_rows_*.csv")
                   for m in [YEARS_RE.match(p.name)] if m}, reverse=True)


def read_town_rows(path):
    """{race key: {"place": {(printed, spelt): {candidate: votes, ...}}}} of a
    town rows file: the rows the race's own count is made of (in_race_count),
    the scattered write-ins under "write_ins_scattered"; the other counts of
    ballots are not a candidate's and are left out."""
    out = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["in_race_count"] != "true":
                continue
            if r["row_kind"] in ("candidate", "write_in_named"):
                who = r["candidate"]
            elif r["row_kind"] == "write_ins_scattered":
                who = "write_ins_scattered"
            else:
                continue
            out[r["district_key"]][(r["place"], r["place_district_table"])][who] += int(r["votes"])
    return out


def office_columns(race):
    """[(column index, candidate's name or a count's word)] of an offices
    race's place rows: each candidate's column, its recount's where the file
    prints one (the race's count is the recount's), and the scattered
    write-ins'."""
    cols = race.get("columns") or []
    label = {(f"{c['name']}, {c['party']}" if c.get("party") else c["name"]): c["name"]
             for c in race["candidates"]}
    label["write_ins_scattered"] = "write_ins_scattered"
    out = {}
    for i, col in enumerate(cols):
        base, recount = (col[:-len(" (recount)")], True) if col.endswith(" (recount)") else (col, False)
        if base in label and (recount or label[base] not in out):
            out[label[base]] = i
    return sorted((i, who) for who, i in out.items())


def office_key_parts(key):
    """("county-commissioner", "Belknap", "1") of "county-commissioner|Belknap|1"."""
    parts = key.split("|")
    return parts[0], (parts[1] if len(parts) > 1 else ""), (parts[2] if len(parts) > 2 else "")


def office_name(key, race):
    office, a, b = office_key_parts(key)
    word = OFFICE_NAME.get(office, office.replace("-", " ").title())
    if office in ("us-house", "executive-council"):
        return f"{word}, District {a}"
    if office == "county-commissioner":
        return f"{a} County Commissioner" + (f", District {b}" if b else "")
    if a and office in OFFICE_NAME:
        # "Grafton County Sheriff", "Grafton County Attorney": the county once.
        return f"{a} County {word[len('County '):] if word.startswith('County ') else word}"
    return word


def house_name(key, floterial):
    parts = key.split("|")
    if parts[0] == "S":
        return f"State Senate, District {parts[1]}"
    return f"State House, {parts[1]} {parts[2]}" + (" (floterial)" if floterial else "")


def order_of(key):
    """A race's place on the ballot: its office (OFFICE_ORDER), then its
    county and district; a State House district the town elects alone before
    a floterial over it falls out of the numbers' order only by chance, so
    the floterial is put last by the caller."""
    parts = key.split("|")
    office = parts[0]
    rank = OFFICE_ORDER.index(office) if office in OFFICE_ORDER else len(OFFICE_ORDER)
    num = [int(p) for p in parts[1:] if p.isdigit()]
    words = [p for p in parts[1:] if not p.isdigit()]
    return (rank, words, num)


# ------------------------------------------------------------- the ledger ---

class Ledger:
    """Every election on file, by the page each place's rows belong to:
    {(town, ward): [election, ...]}, each election
    {"day", "stage": general|primary|special, "party" (a primary's),
     "whole": True where the counts are the race's and not the town's,
     "races": [race, ...]} and each race
    {"key", "name", "seats", "href", "not_final", "recount", "page" (a
     special's Secretary of State page), "cands": [{"name", "party", "votes",
     "write_in", "won": True|False|None, "slug"}], "scatter"}."""

    def __init__(self, districts):
        self.places = Places(districts)
        self.by_page = defaultdict(dict)   # page -> {(day, stage, party): election}
        self.unread = defaultdict(set)     # printed place -> {source}

    def election(self, page, day, stage, party="", whole=False):
        k = (day, stage, party)
        got = self.by_page[page].get(k)
        if got is None:
            got = self.by_page[page][k] = {"day": day, "stage": stage, "party": party,
                                           "whole": whole, "races": []}
        return got

    def page(self, printed, spelt, source):
        p = self.places.page_of(self.places.place_of(printed, spelt))
        if p is None:
            self.unread[printed].add(source)
        return p

    def for_page(self, town, ward):
        """The page's elections in the tab's order (sort_elections)."""
        return sort_elections(list(self.by_page.get((town, ward), {}).values()))


def sort_elections(elections):
    """Newest year first; within a year the general, the state primary (its
    parties in letter order), then the specials newest first; each
    election's races in the ballot's order."""
    stage = {"general": 0, "primary": 1, "special": 2}
    out = sorted(elections, key=lambda e: (-int(e["day"][:4]), stage.get(e["stage"], 3),
                                          -int(e["day"].replace("-", ""))))
    for e in out:
        # A primary's races by its party's ballot first: a voter takes one.
        e["races"].sort(key=lambda r: (r.get("ballot", ""),
                                       -int(r["day"].replace("-", "")) if r.get("day") else 0,
                                       order_of(r["key"])[0], bool(r.get("floterial")),
                                       order_of(r["key"])[1:]))
    return out


def _cands(race_cands, votes, won_of, slug_of):
    """The town's rows of a race: each candidate the town's rows count, with
    the town's votes, the race's outcome (won_of) and a member's page (slug_of)."""
    out = []
    for c in race_cands:
        if c["name"] not in votes:
            continue
        out.append({"name": c["name"], "party": str(c.get("party") or ""),
                    "votes": votes[c["name"]], "write_in": bool(c.get("write_in")),
                    "won": won_of(c), "slug": slug_of(c)})
    out.sort(key=lambda c: (-c["votes"], c["name"]))
    return out


def add_house_senate(ledger, year, rows, results, races_me, hand, links, held_of):
    """The State House and Senate races of one general election, each town's
    own counts from its rows (read_town_rows), the outcome members_elect's."""
    day = results["election"]
    for key, places in rows.items():
        race = (results.get("races") or {}).get(key)
        if race is None:
            continue
        me = races_me.get(key) or {"seats": race["seats"], "elected": []}
        held = held_of(key)
        drawn = {e["n"]: e for e in me.get("elected") or []}
        by_page = defaultdict(lambda: defaultdict(int))
        for (printed, spelt), counts in places.items():
            p = ledger.page(printed, spelt, f"{year} town rows")
            if p is None:
                continue
            for who, n in counts.items():
                by_page[p][who] += n
        for p, votes in by_page.items():
            if p[1] != "0" and year < WARDS_SINCE:
                continue
            def won_of(c, drawn=drawn):
                if c.get("elected") is None:
                    return None
                return BME.reading_order(c["name"]) in drawn

            def slug_of(c, drawn=drawn, key=key):
                e = drawn.get(BME.reading_order(c["name"])) if c.get("elected") is True else None
                if e and e.get("id") and e.get("s"):
                    return e["s"]
                if e and e.get("k") == "new" and e.get("e"):
                    return e["e"]
                return links.get((day, "general", "", key, c["name"]), "")
            cands = _cands([c for c in race["candidates"]
                            if BME.reading_order(c["name"]) not in held], votes, won_of, slug_of)
            if not cands:
                continue
            ledger.election(p, day, "general")["races"].append({
                "key": key, "name": house_name(key, race.get("floterial")),
                "floterial": bool(race.get("floterial")), "seats": race["seats"],
                "href": f"/elections/{day}-general#" + race_anchor(key),
                "not_final": bool(me.get("not_final")), "recount": bool(me.get("recount")),
                "held": bool(held), "cands": cands,
                "unopposed": len(race["candidates"]) <= race["seats"],
                "scatter": votes.get("write_ins_scattered", 0)})


def race_anchor(key):
    """The race's card's id on the elections page (build_elections.race_id)."""
    return "r-" + re.sub(r"[^A-Za-z0-9]+", "-", key).strip("-").lower()


def add_offices(ledger, year, doc, final):
    """Every other office of one general election, each town's own counts
    from the race's place rows; the winner the file's most votes, shown as
    won only once the election's results are final (`final`)."""
    day = doc["election"]
    for key, race in (doc.get("races") or {}).items():
        cols = office_columns(race)
        by_page = defaultdict(lambda: defaultdict(int))
        for row in race.get("places") or []:
            p = ledger.page(row[1], "", f"{year} {key.split('|')[0]}")
            if p is None:
                continue
            for i, who in cols:
                v = row[2][i]
                if isinstance(v, int):
                    by_page[p][who] += v
        for p, votes in by_page.items():
            if p[1] != "0" and year < WARDS_SINCE:
                continue
            cands = _cands(race["candidates"], votes,
                           lambda c: (None if c.get("elected") is None else bool(c["elected"]))
                           if final else False, lambda c: "")
            if not cands:
                continue
            ledger.election(p, day, "general")["races"].append({
                "key": key, "name": office_name(key, race), "seats": race.get("seats"),
                "href": "", "not_final": not final, "recount": False, "held": False,
                "unopposed": isinstance(race.get("seats"), int)
                and len(race["candidates"]) <= race["seats"],
                "cands": cands, "scatter": votes.get("write_ins_scattered", 0)})


def add_primaries(ledger, doc, general_rows, offices_doc, links, county_of):
    """One State Primary: each party's race on a town's ballot, with the
    race's own count (no town's count is on file). A town votes in a
    district's primary where the same year's general counts it in that
    district (`general_rows`, `offices_doc`); a county office's where the
    town is of the county (`county_of`); a statewide office everywhere."""
    day = doc["election"]
    year = int(day[:4])
    members = defaultdict(set)   # race key of the general -> {page}
    for key, places in general_rows.items():
        for printed, spelt in places:
            p = ledger.places.page_of(ledger.places.place_of(printed, spelt))
            if p:
                members[key].add(p)
    for key, race in ((offices_doc or {}).get("races") or {}).items():
        for row in race.get("places") or []:
            p = ledger.places.page_of(ledger.places.place_of(row[1]))
            if p:
                members[key].add(p)
    every = {(t, w) for t, ws in ledger.places.wards.items() for w in ws}
    for pkey, race in (doc.get("races") or {}).items():
        party, gkey = pkey.split("|", 1)
        office = gkey.split("|")[0]
        if office in ("governor", "us-senate", "president"):
            pages = every
        elif gkey in members:
            pages = members[gkey]
        elif office in ("sheriff", "county-attorney", "county-treasurer", "register-of-deeds",
                        "register-of-probate"):
            county = gkey.split("|")[1]
            pages = {p for p in every if county_of.get(p) == county}
        else:
            continue
        ballot = party.upper()
        keep = [c for c in race.get("candidates") or []
                if str(c.get("party") or "").lower() in (party.lower(), "")]
        if not keep:
            continue
        hs = bool(BME.KEY_RE.match(gkey))
        name = house_name(gkey, race.get("floterial") in (True, "True")) if hs else office_name(gkey, race)
        cands = [{"name": c["name"], "party": str(c.get("party") or ""), "votes": c["votes"],
                  "write_in": bool(c.get("write_in")),
                  "most": c.get("nominated") is True,
                  "slug": links.get((day, "primary", ballot, gkey, c["name"]), "") if hs else ""}
                 for c in keep]
        cands.sort(key=lambda c: (-c["votes"], c["name"]))
        try:
            seats = int(race.get("seats")) if race.get("seats") is not None else None
        except (TypeError, ValueError):
            seats = None
        for p in pages:
            if p[1] != "0" and year < WARDS_SINCE:
                continue
            ledger.election(p, day, "primary", "", whole=True)["races"].append({
                "key": gkey, "ballot": ballot, "name": name, "party_word": PARTY_WORD.get(ballot, ballot),
                "floterial": race.get("floterial") in (True, "True"), "seats": seats, "href": "",
                "cands": cands, "scatter": int(race.get("scatter") or 0)})


def add_specials(ledger, specials, generals_rows, links):
    """Each special election and its primaries, on the page of every place
    the district counted in the general that elected the term (the district's
    own count: no town's is on file)."""
    for sp, cands, prims, page in specials:
        key = (sp.get("keys") or {}).get("results")
        term = sp.get("term") or ""
        if not key or not term[:4].isdigit():
            continue
        year = int(term[:4]) - 1
        places = (generals_rows.get(year) or {}).get(key) or {}
        pages = {ledger.places.page_of(ledger.places.place_of(pr, sp_)) for pr, sp_ in places}
        pages.discard(None)
        for contest, cs, stage, ballot in [(sp, cands, "special", "")] + [
                (q, qc, "special-primary", str(q.get("party") or "").upper()) for q, qc in prims]:
            day = contest["election"]
            rows = [{"name": x["printed"], "party": str(x.get("party") or ""), "votes": x["votes"],
                     "write_in": bool(x.get("write_in")),
                     "won": bool(x.get("elected")) if stage == "special" else False,
                     "most": False,
                     "slug": links.get((day, stage, ballot, key, x["printed"]), "")} for x in cs]
            rows.sort(key=lambda c: (-c["votes"], c["name"]))
            if stage == "special-primary" and rows:
                top = [c for c in rows if c["votes"] == rows[0]["votes"] and c["votes"] > 0]
                if len(top) == 1:
                    top[0]["most"] = True
            for p in pages:
                if p[1] != "0" and int(day[:4]) < WARDS_SINCE:
                    continue
                ledger.election(p, sp["election"], "special", "", whole=True)["races"].append({
                    "key": key, "ballot": ballot, "stage": stage, "day": day,
                    "name": house_name(key, False), "party_word": PARTY_WORD.get(ballot, ballot),
                    "seats": contest.get("seats") or 1, "href": "", "page": page,
                    "recounted": bool(contest.get("recounted")), "cands": rows, "scatter": 0})


def member_links(by_member, items, primaries, specials):
    """{(day, stage, ballot, race key, printed name): member's page} of every
    candidacy a member's own Elections tab carries (build_member_elections.
    build's rows), found again by the same functions that put it there and
    held to the tab's row: the same day, stage, ballot, race and votes."""
    import build_member_elections as BMEL
    have = defaultdict(set)
    for mid, rows in by_member.items():
        for r in rows:
            have[mid].add((r["d"], r.get("st") or "general", r.get("pp") or "", r["k"], r["v"]))
    out = {}

    def keep(m, at, c):
        if m and (at[0], at[1], at[2], at[3], c["votes"]) in have.get(m["id"], ()) and m.get("slug"):
            out[at + (c["name"],)] = m["slug"]
    for election, results, races_me, hand, roster in items:
        matches = hand.get("matches") or {}
        for key, race in (results.get("races") or {}).items():
            me = races_me.get(key) or {}
            drawn = {e["n"]: e for e in me.get("elected") or []}
            for c in race["candidates"]:
                keep(BMEL.member_for(c, key, race, election, drawn, matches.get(key) or {}, roster),
                     (election, "general", "", key), c)
    for day, doc, roster in primaries:
        for pkey, race in doc["races"].items():
            party, gkey = pkey.split("|", 1)
            if not BME.KEY_RE.match(gkey):
                continue
            r = BMEL.primary_race(race)
            for c in r["candidates"]:
                got, _why = roster.certain(c["name"], gkey, day, r, c.get("party"))
                keep(got[0] if got else None, (day, "primary", party.upper(), gkey), c)
    for sp, cands, prims, _page, roster in specials:
        key = (sp.get("keys") or {}).get("results")
        term = sp.get("term") or ""
        if not key or not term[:4].isdigit():
            continue
        cycle = int(term[:4]) - 1
        win = BMEL.special_window(term, cycle)
        for contest, cs, stage, ballot in [(sp, cands, "special", "")] + [
                (q, qc, "special-primary", str(q.get("party") or "").upper()) for q, qc in prims]:
            race = BMEL.special_race(contest, cs, None)
            for c in race["candidates"]:
                got, _why = roster.certain(c["name"], key, contest["election"], race, c.get("party"),
                                           window=win)
                keep(got[0] if got else None, (contest["election"], stage, ballot, key), c)
    return out


def load(site, collected, hand_path, today, sponsors=None):
    """(Ledger, words): every election on file, by page, and what main says
    of it. The House and Senate outcomes are members_elect's, read as the
    elections page reads them; a member's chip links as the member tab does."""
    import build_elections as BE
    import build_member_elections as BMEL
    site, collected = Path(site), Path(collected)
    sponsors = sponsors or BME.SPONSORS_DEFAULT
    districts = BME.load_json(site / "districts.json", "the district table")
    ledger = Ledger(districts)
    sitting = BME.load_json(site / "legislators.json", "the sitting roster")
    former = BME.load_json(site / "former.json", "the former members")
    meta = BME.load_json(site / "meta.json", "the site's meta.json, which names its terms")
    terms = meta.get("terms") if isinstance(meta, dict) else None
    history = BME.load_history(sponsors)
    roster = BMEL.Roster(sitting, former, terms if isinstance(terms, list) else [], history)
    by_member, _report, _days = BMEL.build(site, collected, hand_path, today, sponsors)
    items = BE.elections_on_file(collected)
    pages = BE.provisional(site)
    decided = {}
    for election, _p, results in items:
        races_me, _rep, hand = BE.decided(results, sitting, former, districts, hand_path, today,
                                          BE.settled_in(items, election), history)
        BE.with_pages(races_me, pages.get(election))
        decided[election] = (results, races_me, hand)
    primaries = BMEL.primaries_on_file(collected)
    specials = BMEL.specials_on_file(collected)
    links = member_links(by_member,
                         [(e, r, m, h, roster) for e, (r, m, h) in decided.items()],
                         [(d, doc, roster) for d, doc in primaries],
                         [s + (roster,) for s in specials])
    rows_by_year, offices_by_year, county_of = {}, {}, {}
    for year in years_on_file(collected):
        rows = read_town_rows(collected / TOWN_ROWS.format(year=year))
        rows_by_year[year] = rows
        results = next((r for e, (r, _m, _h) in decided.items() if int(e[:4]) == year), None)
        if results is not None:
            _r, races_me, hand = decided[results["election"]]
            add_house_senate(ledger, year, rows, results, races_me, hand, links,
                             lambda k, hand=hand: BE.held_names(hand, k))
            for key, places in rows.items():
                if key.startswith("H|"):
                    for printed, spelt in places:
                        p = ledger.places.page_of(ledger.places.place_of(printed, spelt))
                        if p:
                            county_of.setdefault(p, key.split("|")[1])
        off = collected / OFFICES.format(year=year)
        if off.is_file():
            doc = json.loads(off.read_text(encoding="utf-8"))
            offices_by_year[year] = doc
            election = doc["election"]
            hand = decided.get(election, (None, None, {}))[2]
            final = BE.settled_in(items, election) if items else True
            final = final or not BME.recount_open(today, hand.get("recount_deadline"), election)
            add_offices(ledger, year, doc, final)
    for day, doc in primaries:
        y = int(day[:4])
        add_primaries(ledger, doc, rows_by_year.get(y) or {}, offices_by_year.get(y), links, county_of)
    add_specials(ledger, specials, rows_by_year, links)
    pages_with = sum(1 for v in ledger.by_page.values() if v)
    words = (f"town elections: {pages_with} town and ward pages with an Elections tab, "
             f"{sum(len(v) for v in ledger.by_page.values())} elections on them; "
             f"{len(links)} candidacies linked to a member's page")
    if ledger.unread:
        words += ("; WARNING places read to no town, drawn nowhere: "
                  + ", ".join(f"{k} ({', '.join(sorted(v))})" for k, v in sorted(ledger.unread.items())))
    return ledger, words


# ----------------------------------------------------------------- drawing ---

def long_day(iso):
    """"2024-11-05" -> "5 November 2024"."""
    import datetime
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B')} {d.year}"


def cand_rows(race, primary=False):
    """The race's rows on this page, most votes first, in the elections
    page's row (build_elections.candidate_rows' markup): the chip, the votes
    and the share, a bar scaled to the most votes here. A share is of every
    vote cast in a race for one seat, the scattered write-ins included, and of
    the votes for the candidates listed in a race for more (the owner's rule
    of 19 November 2026); in an unopposed race the write-ins are a row of
    their own and every share is of all of it."""
    cands = race["cands"]
    seats = race.get("seats") or 0
    scatter = int(race.get("scatter") or 0)
    unopp = bool(race.get("unopposed"))
    counted = sum(c["votes"] for c in cands) + (scatter if seats == 1 or unopp else 0)
    top = max([c["votes"] for c in cands] + ([scatter] if unopp else []), default=0) or 1
    out = []
    for c in cands:
        p = str(c["party"] or "").upper()
        chipm = {"party_code": p if len(p) == 1 else "X",
                 "display_full": f'{c["name"]} ({p})' if p else c["name"], "slug": c.get("slug") or ""}
        share = f' <span>&middot; {100 * c["votes"] / counted:.1f}%</span>' if counted else ""
        bar = p[:1] if p[:1] in ("R", "D") else "X"
        mark = ""
        if primary:
            mark = " " + C.chip("Most votes") if c.get("most") else ""
        elif c.get("won") is True:
            mark = " " + C.chip("Won the race")
        elif c.get("won") is None:
            mark = " " + C.chip("Tied for the last seat")
        out.append('<li class="er-row"><span class="er-who">' + C.pchip(chipm)
                   + (' <span class="er-wi">write-in</span>' if c.get("write_in") else "") + mark
                   + f'</span><span class="er-n">{c["votes"]:,}{share}</span>'
                   f'<span class="er-b" aria-hidden="true"><i class="er-{bar}" '
                   f'style="width:{100 * c["votes"] / top:.1f}%"></i></span></li>')
    if unopp and scatter:
        share = f' <span>&middot; {100 * scatter / counted:.1f}%</span>' if counted else ""
        out.append('<li class="er-row er-wirow"><span class="er-who">Write-ins</span>'
                   f'<span class="er-n">{scatter:,}{share}</span>'
                   f'<span class="er-b" aria-hidden="true"><i class="er-X" '
                   f'style="width:{100 * scatter / top:.1f}%"></i></span></li>')
    return "".join(out)


def race_card(race, primary=False):
    """One race as the elections page's card, with a link to that card where
    the elections page draws the race."""
    seats = race.get("seats")
    meta = []
    if isinstance(seats, int) and seats > 1:
        meta.append(f"{seats} seats; each voter could choose up to {seats}")
    if race.get("unopposed"):
        meta.append("Unopposed")
    if race.get("recounted"):
        meta.append("Recounted")
    foot = ""
    if race.get("not_final"):
        foot += ('<p class="elnf"><b>Result not final</b>'
                 + (" &mdash; a recount was requested" if race.get("recount") else "") + "</p>")
    if race.get("held"):
        foot += '<p class="er-foot">A winner of this race is not shown here yet.</p>'
    link = (f'<a class="te-full" href="{E(race["href"])}">The whole race</a>' if race.get("href")
            else "")
    return (f'<article class="er-race te-race"><div class="er-hd"><h5>{E(race["name"])}</h5>{link}</div>'
            + (f'<p class="er-meta">{" &middot; ".join(E(m) for m in meta)}</p>' if meta else "")
            + f'<ul class="er-rows">{cand_rows(race, primary)}</ul>{foot}</article>')


def election_title(e):
    word = {"general": "General election", "primary": "State primary"}.get(e["stage"],
                                                                         "Special election")
    return f"{word}, {long_day(e['day'])}"


def election_html(e, label):
    """One election: its heading, a line where its counts are the race's and
    not the town's, then its races; a primary's under each party's ballot,
    a special's primaries under it."""
    head = f'<h4 class="te-el">{E(election_title(e))}</h4>'
    if e["stage"] == "general":
        return head + f'<div class="er-cards te-cards">{"".join(race_card(r) for r in e["races"])}</div>'
    # A PRIMARY OR A SPECIAL IS FOLDED under its heading: its counts are the whole
    # race's, the same on every page that votes in it, and a town's own general is
    # what the tab is for. The heading says how many races it holds.
    n = len(e["races"])
    out = [f'<details class="te-more"><summary>{head}<span class="te-n">{n} race'
           f'{"s" if n != 1 else ""}, the whole race&rsquo;s counts</span></summary>']
    if e["stage"] == "primary":
        out.append(f'<p class="note te-whole">Each count is the whole race&rsquo;s: {E(label)}&rsquo;s '
                   "own count of the primary is not on file yet.</p>")
        groups = defaultdict(list)
        for r in e["races"]:
            groups[r.get("ballot", "")].append(r)
        for ballot in sorted(groups):
            out.append(f'<h5 class="te-ballot">{E(PARTY_WORD.get(ballot, ballot))} ballot</h5>'
                       '<div class="er-cards te-cards">'
                       + "".join(race_card(r, primary=True) for r in groups[ballot]) + "</div>")
        return "".join(out) + "</details>"
    out.append('<p class="note te-whole">Each count is the whole district&rsquo;s: the Secretary '
               "of State&rsquo;s page of a special election gives none by town.</p>")
    for r in e["races"]:
        if r.get("stage") == "special-primary":
            out.append(f'<h5 class="te-ballot">{E(r["party_word"])} primary, {E(long_day(r["day"]))}</h5>')
        out.append(f'<div class="er-cards te-cards">{race_card(r, primary=r.get("stage") != "special")}</div>')
        if r.get("page") and r.get("stage") == "special":
            out.append(f'<p class="src"><a href="{E(r["page"])}">The Secretary of State&rsquo;s '
                       "page of this election</a></p>")
    return "".join(out) + "</details>"


def tab_cards(elections, label, ward_page=False):
    """The Elections tab's cards for build_town_pages.tabbed: a line saying
    whose counts these are, then a card for each year, newest first. [] where
    no election is on file for the page, so the tab is not drawn."""
    if not elections:
        return []
    years = defaultdict(list)
    for e in elections:
        years[e["day"][:4]].append(e)
    intro = (f"The elections on file in which {E(label)} voted, newest first. Each count of a "
             f"general election is {E(label)}&rsquo;s own, from the Secretary of State&rsquo;s "
             "results by town and ward; &ldquo;Won the race&rdquo; is the result across the whole "
             "district or state.")
    if ward_page:
        intro += (f" A ward&rsquo;s results start with {WARDS_SINCE}, the first election on "
                  "today&rsquo;s district lines: a ward of the same name before then may not "
                  "have been the same ground.")
    out = [f'<p class="note twnwide te-intro">{intro}</p>']
    for y in sorted(years, reverse=True):
        out.append(f'<section class="twnsec twnwide te-year"><h3 class="twnh">{E(y)}</h3>'
                   + "".join(election_html(e, label) for e in years[y]) + "</section>")
    return out
