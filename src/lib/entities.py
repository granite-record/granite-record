#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.1
"""
One model of the people, offices, terms, districts and elections the site's files describe:
the shape of each kind of record, and the rules a model holds to.

    import entities as EN
    EN.KINDS                         # the eight kinds, in the order a model is written
    EN.SHAPES                        # the shape of each
    EN.problems(model)               # every way a model breaks a shape or a rule, as sentences
    EN.offices()                     # the state's offices, as office records, from its settings

NOTHING BUILDS OR READS A MODEL YET (the design of 16 November 2026, step 1): these are its
shapes and its rules, which preflight holds on a model made up there, and the offices and kinds
of district the state's settings give.

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
  contest    a race of one election for an office in a district
  candidacy  one candidate in a contest

PARTY AND SEAT BELONG TO A TENURE, never to a person, so a label is the seat held then. A
mid-term change is two tenures of one seat, each dated where its record dates it.

IDS COME FROM THE FILES, NEVER A COUNTER (the owner's rules, 16 November 2026). A person's id is
the General Court's number where it gives one (site/data/people.json's person number, chosen by
src/lib/people.py's rule), a gr- id where the register (generated/gr_ids.json) has issued one --
by a person's run, never the night -- and nothing at all for a member-elect until the General
Court numbers them: their tenure and candidacy carry person null. Nothing is linked by a name.
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

Standard library only. Nothing here reads or writes a file, or asks the network.
"""

import datetime
import json
import re
from pathlib import Path

FORMAT = 1
KINDS = ("person", "office", "district", "place", "term", "tenure", "contest", "candidacy")

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
CONTEST = r"^\d{4}-\d{2}-\d{2}\.[a-z]+\.[a-z0-9:-]+\.[a-z0-9-]+$"
CANDIDACY = r"^\d{4}-\d{2}-\d{2}\.[a-z]+\.[a-z0-9:-]+\.[a-z0-9-]+\.[a-z0-9-]+$"


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


def contest_id(day, stage, office, where):
    return f"{day}.{stage}.{office}.{where}"


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
            "gc_employee_number": {"type": "string", "pattern": DIGITS},
            "member_id": {"type": "string", "pattern": DIGITS},
            "printed": _S,
            "party": _S,
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
    for xid, x in CA.items():
        c = C.get(x.get("contest"))
        if c is None:
            out.append(f"candidacy {xid} is in contest {x.get('contest')}, which is not in the model")
            continue
        if x.get("person") is not None and x["person"] not in P:
            out.append(f"candidacy {xid} names person {x['person']}, who is not in the model")
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
