#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.9
"""
One model of the people, offices, terms, districts and elections the site's files describe:
the shape of each kind of record, the rules a model holds to, and the views that give today's
files back from it.

    import entities as EN
    EN.KINDS                         # the eight kinds, in the order a model is written
    EN.problems(model)               # every way a model breaks a shape or a rule, as sentences
    EN.load(folder), EN.write(model, folder, extra)
    EN.view_people(model)            # site/data/people.json's "people"
    EN.view_careers(model)           # generated/careers.json but its ballot counts
    EN.hand_file(model, path)        # a hand file as it is written (corrections/officials.json)
    EN.view_members_elect(model)     # site/members_elect.json, or None
    EN.view_districts(model, era)    # site/districts.json
    EN.view_officers(model)          # site/officers.json's "officers"
    EN.view_names(model)             # the search index's part: each confirmed form of a name
    EN.printed_tenures(doc, file)    # the seat each member held in each term, as its bills print it
    EN.party_letters("r&d")          # ("R", "D"): a printed party by the state's one table
    EN.resolve_district(EN.district_index(model), "house", "Belk 8", "2022")
                                     # "house:2022:belknap-8": any spelling, in an era, to its id

src/parse/build_entities.py writes the model to data/entities/ every night from the files on
disk. NOTHING READS IT YET (the design of 16 November 2026, phase A): preflight holds that each
of today's files above is a view of it, byte for byte, so that a reader moved onto it later
cannot change the site, and a model that cannot give a file back has lost something.
The readers moved onto it (phase B, one a commit, each proven to leave the site byte for byte
as it was) read its tenures through this module, from the files it is built from, since the
step that writes data/entities/ runs after them: build_members_elect.seat_history and
build_site_v2.printed_record read printed_tenures (18 November 2026).

THE KINDS. Every record is a JSON object whose first field is its id, named for its kind:

  person     a person: the General Court's numbers for them, their name, the site's ids and page
  office     an office, from the state's settings (src/lib/state_settings.json "offices") and the
             hand file's own offices (a department, a court)
  district   a district of one era, with its seats and its places; a floterial district says
             which districts it lies over
  place      a town, ward or unincorporated place, and the districts it lies in, by era
  term       a term of the legislature, with the days it runs
  tenure     a person (or a name, where no person is linked) holding an office: its district and
             seat, its term, party, the days the record states, and where the record says it
  contest    a race of one election for an office in a district; a primary is one party's,
             and carries the party
  candidacy  one candidate in a contest

PARTY AND SEAT BELONG TO A TENURE, never to a person, so a label is the seat held then. A
mid-term change is two tenures of one seat, each dated where its record dates it. A party is
kept as the file prints it ("party"), and read by the state's one table of parties
(state_settings.json "parties"; party_letters) into the letters it stands for ("parties"):
"R/D" is R and D, and a form the table does not know is read as nothing, never guessed.

IDS COME FROM THE FILES, NEVER A COUNTER (the owner's rules, 16 November 2026). A person's id is
the General Court's number where it gives one (site/data/people.json's person number, chosen by
src/lib/people.py's rule), a gr- id where the register (generated/gr_ids.json) has issued one --
by a person's run, never the night -- and nothing at all for a member-elect until the General
Court numbers them: their tenure and candidacy carry person null. Nothing is linked by a name
alone: a holder of an office the legislature does not fill is linked to a person by the owner's
word or by the rule of src/parse/office_links.py, which weighs more than the name, and the
tenure's "link" says which and on what. A member of 1989-1998 no people file holds is a person
too, under the General Court's number for them, marked by "files" and in no view of today's
files, so that a link to one is kept until their page exists.

A NAME HAS ITS FORMS (the owner's answer of 16 November 2026). A person the owner confirmed
goes by another form of their name -- Joe for Joseph -- carries it in "name_forms", with the
entry that confirmed it; view_names gives what a page would show ('Joseph "Joe" Pitre') and the
words the search finds them by.
A district's id carries its era ("house:2022:strafford-21"), because a district of one number
named other towns before 2022; a county is not redistricted, and its id has none
("county:belknap"). A place is its town and ward, lower case ("dover|1"; a town of no wards is
ward 0).

DATES ONLY WHERE A RECORD STATES ONE (the owner's rule on service dates). A tenure's from and to
are the record's days or absent; a holder whose successor is named carries no end, and the
successor's tenure begins on the day the hand file names. A term's days are the Constitution's
rule (Pt. 2, Art. 3), which proceedings.organization_day applies.

NO RECORD NAMES THE STATE except in its values: what is New Hampshire's -- the floterial and
multi-seat districts, the Executive Council, the House of 400, two-year terms, the officers the
legislature elects -- is data in state_settings.json, each with its article of the Constitution
where it has one (collected/constitution.json). The shapes below hold for any state.

Standard library only, and the state's settings (src/lib/state_settings.py) where no settings
are given. Nothing here reads a file but load() and the settings, writes one but write(), or asks
the network.
"""

import datetime
import json
import re
from pathlib import Path

FORMAT = 1
KINDS = ("person", "office", "district", "place", "term", "tenure", "contest", "candidacy")
FILES = {"person": "people.json", "office": "offices.json", "district": "districts.json",
         "place": "places.json", "term": "terms.json", "tenure": "tenures.json",
         "contest": "contests.json", "candidacy": "candidacies.json"}
# Not a kind: how a hand file lays its records out, so that it can be given back as written
# (hand_file). Each holder of an office in it is a tenure; this is the rest, with each
# holder's place marked {"$tenure": id}.
LAYOUTS = "layouts.json"
MANIFEST = "manifest.json"

# ---- ids --------------------------------------------------------------------------------

DIGITS = r"^\d+$"
DATE = r"^\d{4}-\d{2}-\d{2}$"
TERM = r"^\d{4}-\d{4}$"
# A General Court number (a PersonID or an employee number), a gr- id from the register, or
# people.py's provisional "s" number for someone the General Court numbers nowhere (nobody
# holds one; the owner's decision of 16 November 2026 retires it).
PERSON = r"^(?:\d{1,6}|gr-\d{4,}|s\d+)$"
GR = r"^gr-\d{4,}$"
OFFICE = r"^[a-z][a-z0-9-]*(?::[a-z0-9-]+)?$"
DISTRICT = r"^[a-z][a-z-]*:(?:\d{4}:)?[a-z0-9][a-z0-9-]*$"
PLACE = r"^[^|]+\|\d+$"
# The stage's word is the stage, and for a primary the party's too ("primary-r"), as the State
# Primary readers id their races (src/parse/parse_sos_primary_results.py).
CONTEST = r"^\d{4}-\d{2}-\d{2}\.[a-z]+(?:-[a-z]+)?\.[a-z0-9:-]+\.[a-z0-9-]+$"
CANDIDACY = r"^\d{4}-\d{2}-\d{2}\.[a-z]+(?:-[a-z]+)?\.[a-z0-9:-]+\.[a-z0-9-]+\.[a-z0-9-]+$"


def slug(text):
    """Lower case, letters and digits, a hyphen between: "Hillsborough" -> "hillsborough",
    "Kelly Ayotte" -> "kelly-ayotte", "r/d" -> "r-d"."""
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")


def place_id(town, ward):
    """A place's id: its town, lower case, and its ward ("0" for a town of none)."""
    return f"{' '.join(str(town).split()).lower()}|{ward}"


def district_id(kind, era, local):
    """'house', '2022', 'strafford-21' -> 'house:2022:strafford-21'; no era -> 'county:belknap'."""
    return f"{kind}:{era}:{local}" if era else f"{kind}:{local}"


def contest_id(day, stage, office, where, party=""):
    """A contest's id. Two parties' primaries for one office on one day are two contests, so a
    primary's carries its party as printed: ("2024-09-10", "primary", "us-house", "1", "r") ->
    "2024-09-10.primary-r.us-house.1"."""
    word = f"{stage}-{slug(party)}" if slug(party) else stage
    return f"{day}.{word}.{office}.{where}"


def candidacy_id(contest, printed, party):
    """A candidate's id in a contest: their name as printed, and their party where one is."""
    tail = slug(printed) + (f"-{slug(party)}" if slug(party) else "")
    return f"{contest}.{tail}"


# ---- the shapes ---------------------------------------------------------------------------
#
# Each is the small part of JSON Schema that schema/session.votes.json uses (type, pattern,
# enum, required, properties, additionalProperties, items), read by shape_problems below, so
# that the API can publish them as they are. A field not named is refused: a record says what
# its kind says, and a new field is a change to its shape here.

_S = {"type": "string"}
_SN = {"type": ["string", "null"]}
_INT = {"type": "integer"}
_BOOL = {"type": "boolean"}
_TRUE = {"enum": [True]}
_DAY = {"type": "string", "pattern": DATE}
_STRS = {"type": "array", "items": _S}
_NUMS = {"type": "array", "items": {"type": "string", "pattern": DIGITS}}
_LETTERS = {"type": "array", "items": {"type": "string", "pattern": r"^[A-Z]$"}}
_ANY = {}

SHAPES = {
    "person": {
        "required": ["person"],
        "properties": {
            "person": {"type": "string", "pattern": PERSON},
            "name": _SN,
            "gc_employee_numbers": _NUMS,
            "gc_person_ids": _NUMS,
            # The ids the site's own files use for them: a PersonID, or an employee number
            # where the roster gives none (build_data.py).
            "member_ids": _NUMS,
            "page": _SN,
            "provisional": _TRUE,
            "granite_id": {"type": "string", "pattern": GR},
            "replaced_by": {"type": "string", "pattern": PERSON},
            "split_from": _ANY,
            # What the General Court's roster says of a number of theirs, as
            # generated/careers.json keeps it: {number: {first, last, party, chamber,
            # person_id}}, the party as the roster prints it.
            "gc_roster": {"type": "object", "additionalProperties": {
                "type": "object", "additionalProperties": False,
                "properties": {k: _S for k in ("first", "last", "party", "chamber", "person_id")}}},
            # A person no people file holds, by the files they were read from (the members of
            # 1989-1998 the past roster names and no page shows): in no view of today's files.
            "files": _STRS,
            # The other forms of their name the owner confirmed (Joe for Joseph): the form, its
            # first name and the one of theirs it stands for, and the entry that confirmed it.
            "name_forms": {"type": "array", "items": {
                "type": "object", "required": ["name", "given", "of", "source"], "additionalProperties": False,
                "properties": {"name": _S, "given": _S, "of": _S, "source": _S}}},
        },
        "additionalProperties": False},
    "office": {
        "required": ["office", "name", "scope", "filled_by", "constitution", "source"],
        "properties": {
            "office": {"type": "string", "pattern": OFFICE},
            "name": _S,
            "scope": {"enum": ["statewide", "district", "county", "chamber"]},
            "district_kind": _S,
            "body": _S,
            "code": _S,
            "seats": _INT,
            "term_years": _INT,
            "filled_by": {"enum": ["election", "legislature", "chamber", "appointment", None]},
            "acting": _S,
            "constitution": _STRS,
            "of": _S,
            "department": _S,
            "title": _S,
            "official_url": _S,
            "source": _S,
        },
        "additionalProperties": False},
    "district": {
        # A county has no number, seats or places of its own: its offices say their seats, and
        # a place names its county.
        "required": ["district", "kind", "name", "source"],
        "properties": {
            "district": {"type": "string", "pattern": DISTRICT},
            "kind": _S,
            "era": {"type": "string", "pattern": r"^\d{4}$"},
            "name": _S,
            "county": _S,
            "number": _INT,
            "seats": _INT,
            "floterial": _BOOL,
            "floterial_over": {"type": "array", "items": {"type": "string", "pattern": DISTRICT}},
            "places": {"type": "array", "items": {"type": "string", "pattern": PLACE}},
            "keys": {"type": "object", "additionalProperties": _S},
            "source": _S,
        },
        "additionalProperties": False},
    "place": {
        "required": ["place", "town", "ward", "in", "source"],
        "properties": {
            "place": {"type": "string", "pattern": PLACE},
            "town": _S,
            "ward": {"type": "string", "pattern": DIGITS},
            "county": _SN,
            "in": {"type": "object", "additionalProperties": {
                "type": "array", "items": {"type": "string", "pattern": DISTRICT}}},
            "source": _S,
        },
        "additionalProperties": False},
    "term": {
        "required": ["term", "body", "from", "to", "source"],
        "properties": {
            "term": {"type": "string", "pattern": TERM},
            "body": _S,
            "from": _DAY,
            "to": _DAY,
            "source": _S,
        },
        "additionalProperties": False},
    "tenure": {
        # files: the files on disk it was read from. source: where the record itself says it
        # comes from, where it says (a journal's sentence), as it says it.
        "required": ["tenure", "office", "person", "files"],
        "properties": {
            "tenure": _S,
            "office": {"type": "string", "pattern": OFFICE},
            "district": {"type": ["string", "null"], "pattern": DISTRICT},
            # A seat within the district, where the record numbers it: a county
            # commissioner's district, a US Senate seat in the order the hand file lists them.
            "seat": _S,
            "term": {"type": "string", "pattern": TERM},
            "person": {"type": ["string", "null"], "pattern": PERSON},
            # How the person was linked, where it is not by the General Court's own number:
            # a hand entry's page address, or the register's id issued for this place.
            "linked_by": _S,
            # A holder of an office the legislature does not fill linked to a person of its
            # record (src/parse/office_links.py): by the rule, with each piece of evidence it
            # rests on in words, which the check works out again; or by the owner's hand file,
            # under her key and in her words, who may also say the holder is no one of the
            # record ("why") or not these people ("not"). For checking only: no page shows it.
            "link": {"type": "object", "required": ["by"], "additionalProperties": False, "properties": {
                "by": {"enum": ["rule", "owner"]},
                "key": _S, "evidence": _S, "why": _S, "not": _STRS,
                "name": _S, "middle": _S, "suffix": _S, "town": _S, "area": _S, "party": _S,
                "incompatible": _S}},
            "gc_employee_number": {"type": "string", "pattern": DIGITS},
            "member_id": {"type": "string", "pattern": DIGITS},
            "printed": _S,
            # The party as the file prints it, and the letters it stands for by the state's one
            # table of parties (party_letters), where the table reads every part of it.
            "party": _S,
            "parties": _LETTERS,
            "title": _S,
            "kind": _S,
            "from": _DAY,
            "to": _DAY,
            # On the roster of the site's newest term today (site/legislators.json).
            "sitting": _TRUE,
            "candidacy": {"type": "string", "pattern": CANDIDACY},
            # The rest of what a hand file says of the holder, as it says it.
            "holder": {"type": "object"},
            # Where in a hand file the record stands, and what of it is the office's.
            "slot": {"type": "object", "required": ["path", "order"], "additionalProperties": False,
                     "properties": {"path": {"type": "array"}, "order": _STRS,
                                    "kept": {"type": "object"}}},
            "keys": {"type": "object", "additionalProperties": _S},
            # The seat as a term's bills print it in their sponsor lines (printed_tenures): the
            # chamber, county and district as printed, and every name it is printed under.
            "sponsor_line": {"type": "object", "required": ["chamber", "county", "district", "names"],
                             "additionalProperties": False,
                             "properties": {"chamber": _S, "county": _S, "district": _S, "names": _STRS}},
            "files": _STRS,
            "source": _S,
        },
        "additionalProperties": False},
    "contest": {
        "required": ["contest", "election", "stage", "office", "district", "seats", "source"],
        "properties": {
            "contest": {"type": "string", "pattern": CONTEST},
            "election": _DAY,
            "stage": {"enum": ["general", "primary", "special"]},
            # A primary's party as the file prints it, and its letters by the state's one table:
            # a primary has one and no other stage has any (problems()).
            "party": _S,
            "parties": _LETTERS,
            "office": {"type": "string", "pattern": OFFICE},
            "district": {"type": ["string", "null"], "pattern": DISTRICT},
            "seats": _INT,
            "not_final": _INT,
            "held": _INT,
            "recount": _TRUE,
            "term": {"type": "string", "pattern": TERM},
            "takes_office": _DAY,
            "sources": _STRS,
            "keys": {"type": "object", "additionalProperties": _S},
            "source": _S,
        },
        "additionalProperties": False},
    "candidacy": {
        "required": ["candidacy", "contest", "printed", "person", "source"],
        "properties": {
            "candidacy": {"type": "string", "pattern": CANDIDACY},
            "contest": {"type": "string", "pattern": CONTEST},
            "printed": _S,
            "party": _S,
            "parties": _LETTERS,
            "elected": _BOOL,
            "person": {"type": ["string", "null"], "pattern": PERSON},
            "member_id": {"type": "string", "pattern": DIGITS},
            # What the members-elect rule says of a winner (build_members_elect.py): sitting,
            # former or new; re-elected to the seat they hold; a surname the bills of
            # 1989-1998 print, which the record cannot place; the earlier service the owner
            # confirmed.
            "status": {"enum": ["sitting", "former", "new"]},
            "own": _TRUE,
            "doubt": _TRUE,
            "prior": {"type": "object"},
            "keys": {"type": "object", "additionalProperties": _S},
            "source": _S,
        },
        "additionalProperties": False},
}


def _is(v, t):
    return {"object": isinstance(v, dict), "array": isinstance(v, list),
            "string": isinstance(v, str), "boolean": isinstance(v, bool), "null": v is None,
            "integer": isinstance(v, int) and not isinstance(v, bool)}[t]


def shape_problems(doc, shape, where):
    """Sentences for each way `doc` breaks `shape` (the subset above); [] where it holds."""
    out = []
    if "enum" in shape and not any(doc is e if isinstance(e, bool) or e is None else doc == e
                                   for e in shape["enum"]):
        return [f"{where} is {doc!r}, not one of {shape['enum']}"]
    if "type" in shape:
        types = shape["type"] if isinstance(shape["type"], list) else [shape["type"]]
        if not any(_is(doc, t) for t in types):
            return [f"{where} is a {type(doc).__name__}, not {'/'.join(types)}"]
    if isinstance(doc, str) and "pattern" in shape and not re.search(
            shape["pattern"].replace("$", r"\Z"), doc):
        out.append(f"{where} is {doc!r}, which is not of the form {shape['pattern']}")
    if isinstance(doc, dict):
        for k in shape.get("required", ()):
            if k not in doc:
                out.append(f"{where} has no {k}")
        props, extra = shape.get("properties", {}), shape.get("additionalProperties", True)
        for k, v in doc.items():
            if k in props:
                out += shape_problems(v, props[k], f"{where}.{k}")
            elif extra is False:
                out.append(f"{where} has a field its kind does not: {k}")
            elif isinstance(extra, dict):
                out += shape_problems(v, extra, f"{where}.{k}")
    if isinstance(doc, list) and "items" in shape:
        for i, v in enumerate(doc):
            out += shape_problems(v, shape["items"], f"{where}[{i}]")
    return out


def _day(s):
    try:
        return datetime.date.fromisoformat(s) if isinstance(s, str) and re.match(DATE, s) else None
    except ValueError:
        return None


# ---- the settings: what is the state's ----------------------------------------------------

def _settings(settings=None):
    if settings is not None:
        return settings
    import state_settings
    return state_settings.SETTINGS


def offices(settings=None):
    """The state's offices from its settings, as office records: each row of "offices", with
    the seats and term of a chamber of the legislature read from the legislature and term
    sections (said once there)."""
    s = _settings(settings)
    chambers = s["legislature"]["chambers"]
    out = []
    for row in s["offices"]:
        rec = {"office": row["office"], "name": row["name"], "scope": row["scope"]}
        for k in ("district_kind", "body", "code"):
            if row.get(k):
                rec[k] = row[k]
        if row.get("chamber"):
            rec["seats"] = chambers[row["chamber"]]["seats"]
            rec["term_years"] = s["term"]["length_years"]
        else:
            for k in ("seats", "term_years"):
                if row.get(k) is not None:
                    rec[k] = row[k]
        rec["filled_by"] = row.get("filled_by")
        if row.get("acting"):
            rec["acting"] = row["acting"]
        rec["constitution"] = list(row.get("constitution") or [])
        rec["source"] = "src/lib/state_settings.json offices: " + row["source"]
        out.append(rec)
    return out


def eras(settings=None):
    """{era: first term it fills}, oldest first."""
    s = _settings(settings)
    return {e: v["first_term"] for e, v in sorted(s["district_eras"].items())}


def era_of(term, settings=None):
    """The era of districts a term was elected under: the newest whose first term is not after
    it; None for a term before every era on file."""
    got = None
    for e, first in eras(settings).items():
        if str(term) >= first:
            got = e
    return got


def kind_has_eras(kind, settings=None):
    k = _settings(settings)["district_kinds"].get(kind)
    return bool(k) and k.get("eras", True) is not False


def party_letters(printed, settings=None):
    """The letters a party as a file prints it stands for, by the settings' one table of parties
    ("parties", which state_settings.party_letters reads): ("R",) for "r" or "Republican", ("R",
    "D") for "R/D" or "REP/DEM", () for none printed; None where the settings hold no table, or a
    part of what is printed is a form the table does not know."""
    table = _settings(settings).get("parties")
    if not table:
        return None
    import state_settings
    return state_settings.party_letters(printed, table)


# ---- the rules ----------------------------------------------------------------------------

def index(model):
    """{kind: {id: record}}."""
    return {k: {r[k]: r for r in model.get(k) or []} for k in KINDS}


def problems(model, settings=None, register=None):
    """Every way `model` ({kind: [records]}) breaks a shape or a rule, as sentences; [] is a
    model that holds. `register` is generated/gr_ids.json's, where it is to be held to."""
    s = _settings(settings)
    out = []
    for kind in KINDS:
        seen = set()
        for i, r in enumerate(model.get(kind) or []):
            key = r.get(kind) if isinstance(r, dict) else None
            out += shape_problems(r, SHAPES[kind], f"{kind} {key or i}")
            if key in seen:
                out.append(f"{kind} {key} is in the model twice")
            seen.add(key)
    ix = index(model)
    P, O, D, PL, T, TE, C, CA = (ix[k] for k in KINDS)

    # People: a gr- id is the register's, and a replaced person points at one who is there.
    issued = {e.get("id") for e in (register or {}).get("ids") or []} if register is not None else None
    for pid, p in P.items():
        if re.match(GR, str(pid)):
            if p.get("granite_id") != pid:
                out.append(f"person {pid} is a gr- id whose granite_id does not say so")
            if issued is not None and pid not in issued:
                out.append(f"person {pid} is a gr- id the register does not hold")
        if p.get("replaced_by") and p["replaced_by"] not in P:
            out.append(f"person {pid} is replaced by {p['replaced_by']}, who is not in the model")

    # Districts and places: each district's era is one the settings list; its places list it
    # back; a floterial district lies over the base districts of its places; a place lies in
    # one county, and in one district of each single-seat kind an era.
    era_list = set(eras(s))
    for did, d in D.items():
        if kind_has_eras(d.get("kind"), s):
            if d.get("era") not in era_list or not did.startswith(f"{d.get('kind')}:{d.get('era')}:"):
                out.append(f"district {did} carries no era the settings list ({sorted(era_list)})")
        elif d.get("era"):
            out.append(f"district {did} is of a kind that is not redrawn, and carries an era")
        for pl in d.get("places") or []:
            if pl not in PL:
                out.append(f"district {did} names place {pl}, which is not in the model")
            elif did not in (PL[pl].get("in") or {}).get(d.get("era") or "", []):
                out.append(f"district {did} names place {pl}, which does not name it back")
        if d.get("floterial"):
            base = sorted({b for pl in d.get("places") or [] for b in (PL.get(pl) or {}).get("in", {})
                           .get(d.get("era") or "", []) if b in D and D[b].get("kind") == d.get("kind")
                           and not D[b].get("floterial")})
            if sorted(d.get("floterial_over") or []) != base:
                out.append(f"district {did} is floterial over {d.get('floterial_over')}, and its "
                           f"places' own districts are {base}")
        elif d.get("floterial_over"):
            out.append(f"district {did} is not floterial and lies over {d['floterial_over']}")
    for pid, pl in PL.items():
        for era, dids in (pl.get("in") or {}).items():
            kinds = {}
            for did in dids:
                d = D.get(did)
                if d is None:
                    out.append(f"place {pid} lies in {did}, which is not in the model")
                    continue
                if pid not in (d.get("places") or []):
                    out.append(f"place {pid} lies in {did}, which does not name it")
                kinds.setdefault(d["kind"], []).append(d)
            for kind, ds in kinds.items():
                if len([x for x in ds if not x.get("floterial")]) != 1:
                    out.append(f"place {pid} lies in {len([x for x in ds if not x.get('floterial')])} "
                               f"{kind} districts of {era} that are not floterial, not one")
            counties = {d.get("county") for ds in kinds.values() for d in ds if d.get("county")}
            if len(counties) > 1:
                out.append(f"place {pid} lies in districts of {len(counties)} counties: {sorted(counties)}")
    # A spelling names one district of its kind in an era: "Belk 8" is Belknap 8 of 2022 and no
    # other.
    for (kind, era, said), ids in sorted(district_index(model).items(), key=lambda kv: str(kv[0])):
        if len(ids) > 1:
            out.append(f"the {kind} districts of {era or 'no era'} spell two of them {said!r}: {', '.join(ids)}")
    # Each kind's seats add up to its office's, era by era (the House of 400, a Senate of 24,
    # five councilors, two members of the US House).
    for kind, k in s["district_kinds"].items():
        office = O.get(k.get("office") or "")
        if not office or office.get("seats") is None:
            continue
        for era in sorted({d.get("era") for d in D.values() if d.get("kind") == kind}):
            n = sum(d["seats"] for d in D.values() if d.get("kind") == kind and d.get("era") == era)
            if n != office["seats"]:
                out.append(f"the {kind} districts of {era} hold {n} seats, and the office {office['office']} "
                           f"{office['seats']}")

    # Terms: real days, in order, each ending the day before the next begins.
    terms = sorted(T.values(), key=lambda t: t["term"])
    for t in terms:
        a, b = _day(t.get("from")), _day(t.get("to"))
        if a is None or b is None or a >= b:
            out.append(f"term {t['term']} runs from {t.get('from')} to {t.get('to')}")
    for t, u in zip(terms, terms[1:]):
        a, b = _day(t.get("to")), _day(u.get("from"))
        if a and b and b - a != datetime.timedelta(days=1):
            out.append(f"term {t['term']} ends {t['to']} and {u['term']} begins {u['from']}")

    # Tenures: what they name is in the model; the days are real and in order; a pending
    # member-elect is no one or a person the General Court numbers.
    for tid, t in TE.items():
        for field, table in (("office", O), ("district", D), ("term", T), ("person", P),
                             ("candidacy", CA)):
            v = t.get(field)
            if v is not None and v not in table:
                out.append(f"tenure {tid} names {field} {v}, which is not in the model")
        a, b = t.get("from"), t.get("to")
        for v in (a, b):
            if v is not None and _day(v) is None:
                out.append(f"tenure {tid} is dated {v}, which is no day")
        if a and b and _day(a) and _day(b) and _day(a) > _day(b):
            out.append(f"tenure {tid} runs from {a} to {b}")
        if t.get("candidacy") and t.get("person") is not None and not re.match(DIGITS, t["person"]):
            out.append(f"tenure {tid} is a member-elect's under {t['person']}: a member-elect has "
                       "no id until the legislature numbers them")
        if t.get("sitting") and not t.get("term"):
            out.append(f"tenure {tid} is sitting and names no term")
        out += _party_problems("tenure", tid, t, s)
        # A link says how it was made, once: the rule's names a person and what it rests on;
        # the owner's, her key, and her evidence where it names someone; never a person she
        # says the holder is not.
        lk = t.get("link")
        if lk:
            if t.get("linked_by"):
                out.append(f"tenure {tid} is linked two ways: {t['linked_by']}, and by the {lk.get('by')}")
            if lk.get("by") == "rule" and (not t.get("person") or not lk.get("name")):
                out.append(f"tenure {tid} is linked by the rule to no one, or on nothing")
            if lk.get("by") == "owner" and (not lk.get("key") or (t.get("person") and not lk.get("evidence"))
                                            or (not t.get("person") and not lk.get("why"))):
                out.append(f"tenure {tid} is the owner's, and says no key, or names someone with no "
                           "evidence, or no one with no reason")
            if t.get("person") and t["person"] in (lk.get("not") or []):
                out.append(f"tenure {tid} is linked to {t['person']}, whom the owner says it is not")
    # A MID-TERM CHANGE IS TWO TENURES OF ONE SEAT. Where both are dated they do not overlap
    # (a `to` is the day the next begins, as site/officers.json writes it); and no more sit at
    # once, or are elected to take it, than the district has seats.
    def one_seat(t):
        if t.get("seat"):
            return True
        if t.get("district"):
            return (D.get(t["district"]) or {}).get("seats", 1) == 1
        return (O.get(t["office"]) or {}).get("seats") == 1
    dated = {}
    for t in TE.values():
        if t.get("from") and t.get("to") and one_seat(t):
            dated.setdefault((t["office"], t.get("district"), t.get("seat")), []).append(t)
    for key, ts in sorted(dated.items(), key=lambda kv: str(kv[0])):
        ts = sorted(ts, key=lambda t: (t["from"], t["to"]))
        for x, y in zip(ts, ts[1:]):
            if y["from"] < x["to"]:
                out.append(f"tenures {x['tenure']} and {y['tenure']} of one seat overlap "
                           f"({x['from']} to {x['to']}, {y['from']} to {y['to']})")
    seats = {}
    for t in TE.values():
        if (t.get("district") or t.get("seat")) and (t.get("sitting") or t.get("candidacy")):
            seats.setdefault((t["office"], t.get("district"), t.get("seat"), t.get("term")), []).append(t)
    for (office, did, seat, term), ts in sorted(seats.items(), key=lambda kv: str(kv[0])):
        n = (D.get(did) or {}).get("seats", 1) if not seat else 1
        sitting = [t for t in ts if t.get("sitting")]
        if len(sitting) > n:
            out.append(f"{len(sitting)} tenures sit in {did or seat} for {term} and it has {n} seat(s)")
        pending = [t for t in ts if t.get("candidacy")]
        if len(pending) > n:
            out.append(f"{len(pending)} members-elect take {did or seat} for {term} and it has {n} seat(s)")

    # Contests and candidacies: a candidacy's contest is there, no more are elected than the
    # contest has seats, and each winner of a members-elect contest takes exactly one tenure
    # on the contest's day, as the same person.
    by_cand = {}
    for t in TE.values():
        if t.get("candidacy"):
            by_cand.setdefault(t["candidacy"], []).append(t)
    for cid, c in C.items():
        for field, table in (("office", O), ("district", D), ("term", T)):
            v = c.get(field)
            if v is not None and v not in table:
                out.append(f"contest {cid} names {field} {v}, which is not in the model")
        won = [x for x in CA.values() if x.get("contest") == cid and x.get("elected")]
        if len(won) > c.get("seats", 0):
            out.append(f"contest {cid} has {len(won)} elected for {c.get('seats')} seat(s)")
        # A primary is one party's: it carries the party, and its id's stage word says it; a
        # general or a special is every party's and carries none.
        word = cid.split(".")[1] if cid.count(".") >= 3 else ""
        if c.get("stage") == "primary":
            if not slug(c.get("party")):
                out.append(f"contest {cid} is a primary and names no party")
            elif word != f"primary-{slug(c['party'])}":
                out.append(f"contest {cid} is the primary of {c['party']!r}, and its id says {word!r}")
        elif c.get("party") or "-" in word:
            out.append(f"contest {cid} is a {c.get('stage')} and names a party")
        out += _party_problems("contest", cid, c, s)
    for xid, x in CA.items():
        c = C.get(x.get("contest"))
        if c is None:
            out.append(f"candidacy {xid} is in contest {x.get('contest')}, which is not in the model")
            continue
        if x.get("person") is not None and x["person"] not in P:
            out.append(f"candidacy {xid} names person {x['person']}, who is not in the model")
        out += _party_problems("candidacy", xid, x, s)
        if x.get("elected") and c.get("takes_office"):
            ts = by_cand.get(xid) or []
            if len(ts) != 1:
                out.append(f"candidacy {xid} won and takes {len(ts)} tenures, not one")
            for t in ts:
                if (t.get("from"), t.get("term"), t.get("person"), t.get("district")) != (
                        c["takes_office"], c.get("term"), x.get("person"), c.get("district")):
                    out.append(f"candidacy {xid}'s tenure {t['tenure']} is not the contest's seat, "
                               "day and term, or not the same person")
    return out


def _party_problems(kind, rid, r, settings):
    """A record's "parties" are the settings' table's reading of its printed party, exactly: its
    letters where the table reads every part, and none where it reads none or not all. Held only
    where the settings hold a table."""
    if not settings.get("parties"):
        return []
    want = party_letters(r.get("party"), settings) if r.get("party") else ()
    have = r.get("parties")
    if want and have != list(want):
        return [f"{kind} {rid} is of the party printed {r['party']!r}, which the table reads as "
                f"{list(want)}, and its parties are {have}"]
    if not want and have is not None:
        return [f"{kind} {rid} has parties {have}, and the table reads none in {r.get('party')!r}"]
    return []


# ---- loading and writing --------------------------------------------------------------------

def ordered(kind, rec):
    """`rec` with its fields in the order its kind's shape names them, any other after."""
    names = list(SHAPES[kind]["properties"])
    rank = {k: i for i, k in enumerate(names)}
    return {k: rec[k] for k in sorted(rec, key=lambda k: (rank.get(k, len(names)), k))}


def _lines(kind, records):
    """A JSON list with one record a line, its fields in its shape's order: small, and a diff
    reads as records."""
    if not records:
        return "[]"
    return "[\n" + ",\n".join(json.dumps(ordered(kind, r), ensure_ascii=False, separators=(",", ":"))
                              for r in records) + "\n]"


def write(model, folder, layouts=None, manifest=None):
    """Write `model` into `folder`: a file a kind (FILES), the layouts and the manifest, each
    {"format", "kind" or "what", ...}. LF line ends on every machine, so that two builds of one
    model are the same bytes anywhere. Returns {file name: bytes}."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    sizes = {}

    def put(name, text):
        p = folder / name
        tmp = p.with_suffix(p.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        tmp.replace(p)
        sizes[name] = p.stat().st_size

    for kind in KINDS:
        put(FILES[kind], '{"format":%d,"kind":%s,"records":%s}\n'
            % (FORMAT, json.dumps(kind), _lines(kind, model.get(kind) or [])))
    put(LAYOUTS, json.dumps({"format": FORMAT, "layouts": layouts or {}}, ensure_ascii=False,
                            indent=1) + "\n")
    if manifest is not None:
        put(MANIFEST, json.dumps(dict(manifest, sizes=dict(sorted(sizes.items()))),
                                 ensure_ascii=False, indent=1) + "\n")
    return sizes


def load(folder):
    """(model, layouts, manifest) from `folder` as write() left it; OSError or ValueError where
    a file is missing or will not read, for the caller to say."""
    folder = Path(folder)
    model = {}
    for kind in KINDS:
        doc = json.loads((folder / FILES[kind]).read_text(encoding="utf-8"))
        if doc.get("kind") != kind or doc.get("format") != FORMAT:
            raise ValueError(f"{folder / FILES[kind]} is not a file of {kind} records, format {FORMAT}")
        model[kind] = doc["records"]
    layouts = json.loads((folder / LAYOUTS).read_text(encoding="utf-8"))["layouts"]
    mp = folder / MANIFEST
    manifest = json.loads(mp.read_text(encoding="utf-8")) if mp.is_file() else None
    return model, layouts, manifest


# ---- a district's spellings ------------------------------------------------------------------
#
# ONE DISTRICT, MANY SPELLINGS, ONE ID WITH ITS ERA IN IT (the design's step 4). The files spell a
# district six ways and more -- the results' "H|Belknap|8", the elections' "belknap-8", the map's
# "BE8", "Belknap 8", the roster's "Belk 8", the legislature's county code with a number "01-8",
# a page address's "belk-8" -- and a district record carries each as a key (its "keys", from the
# state's settings), beside its name and its id. The table resolves any of them, in an era, to
# the one id: "Belk 8" in 2022 is house:2022:belknap-8, and in a term before every era on file it
# is no district the model holds, since the same words named other towns then.

def spelling(text):
    """A district's spelling as the table matches it: lower case, a full stop read as a space, one
    space between words, and every number without its leading zeros ("Carr 07", "carr. 7" and
    "CARR 7" are one; "01-08" is "1-8")."""
    s = " ".join(str(text or "").replace(".", " ").lower().split())
    return re.sub(r"\d+", lambda m: str(int(m.group())), s)


def district_spellings(d):
    """{form: spelling} of district record `d`: its name, its id's own part ("belknap-8"), each of
    its keys, and its number alone where a number names one district of its kind (a district in
    no county; a county's numbers repeat)."""
    out = {"name": d.get("name"), "id": d["district"].rsplit(":", 1)[-1]}
    out.update(d.get("keys") or {})
    if d.get("number") is not None and not d.get("county"):
        out["number"] = str(d["number"])
    return {f: str(v) for f, v in out.items() if v}


def district_index(model):
    """{(kind, era, spelling): [district ids]} of every district of the model by every spelling
    it has (district_spellings, each as spelling() matches it). A spelling under two ids is a
    problem of the model's (problems)."""
    out = {}
    for d in model.get("district") or []:
        for v in district_spellings(d).values():
            ids = out.setdefault((d["kind"], d.get("era"), spelling(v)), [])
            if d["district"] not in ids:
                ids.append(d["district"])
    return out


def resolve_district(index, kind, text, era):
    """The id of the district of `kind` the table spells `text` in `era` ("2022"; None for a kind
    that is not redrawn), or None: where it holds none so spelled, or two, or the era is one it
    holds no districts of -- a term before every era on file."""
    ids = index.get((kind, era, spelling(text)))
    return ids[0] if ids and len(ids) == 1 else None


# ---- the seat a term's bills print ----------------------------------------------------------

def printed_tenures(sponsors, file, settings=None):
    """[tenure, ...]: THE SEAT A MEMBER HELD IN A TERM, AS THE TERM'S BILLS PRINT IT. `sponsors`
    is text_sponsors.json as read ({term: {bill: [{"member_id", "name", "chamber", "county",
    "district", ...}]}}), the sponsor lines src/parse/text_sponsors.py read off each bill's own
    text, which carry the seat a sponsor held in the term the bill was filed; `file` is where it
    was read. One tenure a member, seat and term -- or, where text_sponsors placed a line on no
    one, a seat and term with no member -- holding the seat as printed ("sponsor_line": the
    chamber, county and district as the lines print them, and every name the lines print it
    under, in the file's order), its office the chamber's, and no person (build_entities gives
    the person and, where the term's era of districts is on file, the district). A member who
    sponsored nothing in a term has no tenure of it here; one printed at two seats has two. A
    line with no district, or in a chamber no office of the settings is coded for, is no seat:
    text_sponsors.py writes H, S or nothing, and a line of no chamber prints no district. The
    tenures come in the order the file first prints each, as the readers that read them have
    always met the lines: the seat of the term a session day names a member by
    (build_site_v2.printed_record) and the seats a member-elect's history is matched against
    (build_members_elect.seat_history), each with its own rule."""
    codes = {o["code"]: o["office"] for o in offices(settings)
             if o.get("code") and o.get("district_kind") in ("house", "senate")}
    out, by_id = [], {}
    for term, bills in (sponsors or {}).items():
        for rows in (bills or {}).values():
            for r in rows or []:
                if not r.get("district"):
                    continue
                chamber = r.get("chamber") or ""
                office = codes.get(chamber)
                if office is None:
                    continue
                mid, county, district = str(r.get("member_id") or ""), r.get("county") or "", str(r["district"])
                tid = f"printed:{term}:{mid}|{chamber}|{county}|{district}"
                t = by_id.get(tid)
                if t is None:
                    t = by_id[tid] = {"tenure": tid, "office": office, "term": term, "person": None}
                    if mid:
                        t["member_id"] = mid
                    t["sponsor_line"] = {"chamber": chamber, "county": county, "district": district,
                                         "names": []}
                    t["files"] = [file]
                    out.append(t)
                name = str(r.get("name") or "")
                if name not in t["sponsor_line"]["names"]:
                    t["sponsor_line"]["names"].append(name)
    return out


# ---- the views: today's files, from the model -----------------------------------------------

def _code(model):
    """{office: its chamber's letter} for the offices that have one."""
    return {o["office"]: o["code"] for o in model.get("office") or [] if o.get("code")}


def _careers_tenures(model):
    return [t for t in model.get("tenure") or [] if (t.get("keys") or {}).get("careers")]


def view_people(model):
    """site/data/people.json's "people" (src/lib/people.py's build), from the people and the
    tenures careers.json gives them: each person's chambers and first and last terms are their
    General Court numbers' tenures, and sitting is a tenure on today's roster."""
    code = _code(model)
    by_num, sitting = {}, set()
    for t in _careers_tenures(model):
        by_num.setdefault(t["gc_employee_number"], []).append(t)
    for t in model.get("tenure") or []:
        if t.get("sitting") and t.get("person"):
            sitting.add(t["person"])
    out = []
    for p in model.get("person") or []:
        if p.get("replaced_by"):
            e = {"person": p["person"], "replaced_by": p["replaced_by"]}
        elif re.match(GR, p["person"]) or p.get("files"):
            # An id of ours, or a person no people file holds (the members of 1989-1998 with no
            # page): today's file has neither.
            continue
        else:
            ts = [t for n in p.get("gc_employee_numbers") or [] for t in by_num.get(n, [])]
            terms = sorted({t["term"] for t in ts})
            e = {"person": p["person"], "name": p.get("name"),
                 "employee_numbers": list(p.get("gc_employee_numbers") or []),
                 "person_ids": list(p.get("gc_person_ids") or []),
                 "member_ids": list(p.get("member_ids") or []),
                 "page": p.get("page"),
                 "sitting": p["person"] in sitting,
                 "chambers": sorted({code[t["office"]] for t in ts}),
                 "first_term": terms[0] if terms else None,
                 "last_term": terms[-1] if terms else None}
            if p.get("provisional"):
                e["provisional"] = True
        if "split_from" in p:
            e["split_from"] = p["split_from"]
        out.append(e)
    return out


def view_careers(model):
    """generated/careers.json (src/parse/build_careers.py) but each record's "votes", a count of
    ballots, which belong to the roll calls and not to this model: every careers group from its
    tenures (keys.careers), and the roster's word on its lead number from the person who holds
    it (gc_roster)."""
    code = _code(model)
    roster = {}
    for p in model.get("person") or []:
        for n, r in (p.get("gc_roster") or {}).items():
            roster[n] = r
    groups = {}
    for t in _careers_tenures(model):
        groups.setdefault(t["keys"]["careers"], []).append(t)
    out = {}
    for key in sorted(groups):
        ts = groups[key]
        by_term = {}
        for t in ts:
            v = by_term.setdefault(t["term"], {"chambers": set(), "employee_nos": set()})
            v["chambers"].add(code[t["office"]])
            v["employee_nos"].add(t["gc_employee_number"])
        terms = sorted(by_term)
        gaps = [terms[i] for i in range(len(terms) - 1) if int(terms[i + 1][:4]) - int(terms[i][:4]) > 2]
        r = roster.get(key) or {}
        out[key] = {
            "by_term": {t: {"chambers": sorted(v["chambers"]), "employee_nos": sorted(v["employee_nos"])}
                        for t, v in sorted(by_term.items())},
            "chamber_last": r.get("chamber", ""),
            # careers.json gives no district for any term: the roster holds one, the last.
            "district_by_term": {},
            "employee_nos": sorted({t["gc_employee_number"] for t in ts}),
            "first": r.get("first", ""),
            "first_term": terms[0] if terms else "",
            "last": r.get("last", ""),
            "last_term": terms[-1] if terms else "",
            "named": bool(r.get("last")),
            "party": r.get("party", ""),
            "person_id": r.get("person_id", ""),
            "returned_after_a_gap": bool(gaps),
            "terms": terms,
        }
    return out


def _fill(x, tenures):
    """`x` with each {"$tenure": id} in it put back as the record that tenure stood for."""
    if isinstance(x, list):
        return [_fill(v, tenures) for v in x]
    if not isinstance(x, dict):
        return x
    if set(x) == {"$tenure"}:
        return _holder_record(tenures[x["$tenure"]], tenures)
    return {k: _fill(v, tenures) for k, v in x.items()}


def _holder_record(t, tenures):
    """A hand file's record of a holder, as written, from its tenure: the fields in the order
    the file has them, the office's kept as they were, the name and party as printed, and the
    successor under "elect" (the tenure whose place is this one's and "elect")."""
    slot = t["slot"]
    kept = slot.get("kept") or {}
    rec = {}
    for k in slot["order"]:
        if k == "elect":
            succ = tenures.get(t["tenure"] + ".elect")
            if succ is None:
                raise ValueError(f"tenure {t['tenure']} had a successor the model does not hold")
            rec[k] = _holder_record(succ, tenures)
        elif k == "takes_office":
            rec[k] = t["from"]
        elif k in kept:
            rec[k] = _fill(kept[k], tenures)
        elif k == "name":
            rec[k] = t["printed"]
        elif k == "party":
            rec[k] = t["party"]
        else:
            rec[k] = (t.get("holder") or {})[k]
    return rec


def hand_file(model, layouts, path):
    """The hand file `path` (corrections/officials.json) as it is written, parsed: its layout
    with each holder put back from their tenure. preflight compares it with the file, and every
    page's officials_on(day) with the same of the file."""
    tenures = {t["tenure"]: t for t in model.get("tenure") or []}
    return _fill(layouts[path], tenures)


def members_elect_contests(model):
    return [c for c in model.get("contest") or [] if c.get("source") == "site/members_elect.json"]


def view_members_elect(model, layouts=None):
    """site/members_elect.json (src/parse/build_members_elect.py), from its contests and their
    winners, in the order the file has them; None where the model holds none, as outside the
    weeks between the election and Organization Day there is no file. Its list of the results'
    addresses, one a spreadsheet read, is its layout's (each contest has them once)."""
    contests = members_elect_contests(model)
    if not contests:
        return None
    won = {}
    for x in model.get("candidacy") or []:
        if x.get("elected"):
            won.setdefault(x["contest"], []).append(x)
    first = contests[0]
    races = {}
    for c in contests:
        row = {"seats": c["seats"], "elected": [], "not_final": c.get("not_final", 0),
               "held": c.get("held", 0)}
        if c.get("recount"):
            row["recount"] = True
        for x in won.get(c["contest"], []):
            e = {"n": x["printed"], "p": x.get("party", "")}
            if "status" in x:
                e["k"] = x["status"]
            if x.get("member_id"):
                e["id"] = x["member_id"]
            keys = x.get("keys") or {}
            if "page" in keys:
                e["s"] = keys["page"]
            if x.get("own"):
                e["own"] = True
            if x.get("doubt"):
                e["u"] = True
            if "prior" in x:
                e["prior"] = x["prior"]
            if "elect_page" in keys:
                e["e"] = keys["elect_page"]
            row["elected"].append(e)
        races[c["keys"]["results"]] = row
    sources = ((layouts or {}).get(first["source"]) or {}).get("sources", first.get("sources") or [])
    return {"election": first["election"], "takes_office": first["takes_office"],
            "term": first["term"], "sources": list(sources), "races": races}


def view_districts(model, era):
    """site/districts.json (src/towns/parse_districts.py's combine): {town: {ward: {kind: number,
    "house": [{county, district, floterial, seats}]}}} for the places of `era`."""
    D = {d["district"]: d for d in model.get("district") or []}
    out = {}
    for pl in model.get("place") or []:
        dids = (pl.get("in") or {}).get(era)
        if not dids:
            continue
        row = {}
        house = []
        for did in dids:
            d = D[did]
            if d["kind"] == "house":
                house.append({"county": d["county"], "district": d["number"],
                              "seats": d["seats"], "floterial": d["floterial"]})
            else:
                row[d["kind"]] = d["number"]
        if house:
            house.sort(key=lambda x: (x["floterial"], x["district"]))
            row["house"] = house
        out.setdefault(pl["town"], {})[pl["ward"]] = row
    return out


def view_officers(model):
    """site/officers.json's "officers" (build_site_v2.build_officers): the tenures of the chair's
    offices it gave, in its order."""
    O = {o["office"]: o for o in model.get("office") or []}
    out = []
    for t in model.get("tenure") or []:
        if "site/officers.json" not in (t.get("files") or []):
            continue
        o = O[t["office"]]
        out.append({"b": o["code"], "office": o["name"], "title": t["title"], "name": t["printed"],
                    "id": t["member_id"], "s": t["keys"]["ballot_sort"], "from": t["from"],
                    "to": t["to"], "kind": t["kind"], "source": t["source"]})
    return out


def display_name(name, form):
    """A name with a confirmed form of its first name, the longer first and the other in quotes:
    ("Joseph Pitre", {"given": "Joe", "of": "Joseph"}) -> 'Joseph "Joe" Pitre'. A name whose
    first word is neither is given the form after it, in brackets."""
    given, of = str(form.get("given") or ""), str(form.get("of") or "")
    long_, short = (of, given) if len(of) >= len(given) else (given, of)
    words = str(name or "").split()
    if words and words[0].lower() in (given.lower(), of.lower()) and short:
        return " ".join([long_, f'"{short}"'] + words[1:])
    return f'{name} ("{given}")' if given else str(name or "")


def view_names(model):
    """{person: {"name", "display", "words"}}: what the search index will take from the model
    of each person who goes by a form of their name the owner confirmed (name_forms) -- the name
    a page would show, 'Joseph "Joe" Pitre', and the words that find them by every form, each
    form whole and its first name. A person with no confirmed form is not in it, so that today's
    search words are the model's for everyone else. Nothing reads it yet."""
    out = {}
    for p in model.get("person") or []:
        forms = p.get("name_forms") or []
        if not forms or p.get("replaced_by"):
            continue
        words = []
        for f in forms:
            for w in (f["name"], f["given"]):
                if w and w not in words:
                    words.append(w)
        out[p["person"]] = {"name": p.get("name"), "display": display_name(p.get("name"), forms[0]),
                            "words": words}
    return out
