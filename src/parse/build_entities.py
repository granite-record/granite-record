#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.5
"""
The model of people, offices, terms, districts and elections, written to data/entities/ from
the files on disk (src/lib/entities.py says what the model is).

    python3 src/parse/build_entities.py                 # data/entities/, and what it holds
    python3 src/parse/build_entities.py --check         # build it and give today's files back
                                                        #   from it; writes nothing
    python3 src/parse/build_entities.py --root DIR --out DIR
                                                        # read another tree's files, write elsewhere
    python3 src/parse/build_entities.py --check --links # and print the owner's list of officials

ONE WRITER, AND NOTHING READS IT YET (the design of 16 November 2026, phase A; the owner's yes
of that day). It reads, and never writes:

  site/data/people.json           the people, and every number the General Court uses for them
  generated/careers.json          every term each of them served, by employee number and chamber
  site/legislators.json           today's roster: who sits, in which district, for which party
  site/meta.json                  the terms the site describes; the newest is the roster's
  corrections/officials.json      the offices no General Court file names, and who holds each
  site/officers.json              who held the chair's offices, from the journals
  site/members_elect.json         November's winners until they sit, where the file is on disk
  records/districts/*.txt         the districts and their towns and wards
  generated/gr_ids.json           Granite Record's own ids, issued by a person's run
  collected/county_officials.json the county officers as the Secretary of State's roster read,
                                  only to say where it and the hand file differ
  generated/past_roster.json      the members of 1989-1998, and who of them has no page
  corrections/officials_links.json the owner's word on who an official is, where it is on disk
  LINK_EVIDENCE                   what the files say of every member an official might be
                                  (site/former.json, data/legislators.json, the General Court's
                                  member table in db/, past_members.json, member_party.json,
                                  text_sponsors.json, the Manual's returns, the ZIP codes' towns)

and writes data/entities/ (the build's data folder, never site/: nothing here is published).

THE OFFICIALS, LINKED TO THE RECORD (the design study "officials-links" and the owner's answers
of 16 November 2026). Each holder of an office the legislature does not fill -- the hand file's
holders and successors, the county roster's -- is linked to a person of the record where the
owner's hand file of links says who, or where the rule of src/parse/office_links.py settles it:
one person of the whole record answering to the name, by the same first name, one more
agreement and nothing that differs. The link is the tenure's "person", and its "link" says how
and on what; a member of 1989-1998 with no page is a person of the model, so a link to one is
kept. What the rule cannot settle is the owner's list, in the manifest ("links") and printed by
--links. Without every file of the pool, nobody is linked by the rule, and the step says so.
Town offices are not linked (the model holds none, and the owner's answer is none until a town
page shows them).
preflight holds that each of today's files is a view of the model, byte for byte but for the
line ends a machine writes (rebuilt() below): a model that cannot give a file back has lost
something. What it cannot give back is said: careers.json's ballot counts, which are the roll
calls'.

IDS, DATES AND LINKS by the owner's rules (entities.py): the General Court's number where it
gives one; a gr- id only where the register issued one for that very record (gr_register.py
--offices, a person's run); no id for a member-elect until the General Court numbers them; a
date only where a record states one; nothing linked by a name alone. A holder in the hand file
is linked to a person by the hand file's own entry (its "member" page address), by the owner's
hand file of links, or by the rule above, which weighs more than the name.

WHERE TODAY'S FILES DISAGREE it says so, in the manifest and on the night's log, and fixes
nothing: the county officers are kept twice (the hand file, which the pages read, and the
Secretary of State's roster as read in 2024), and it lists the seats they name differently.

Standard library only; no network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import datetime
import hashlib
import json
import re
import tempfile
import time

import build_date
import entities as EN
import proceedings
import state_settings as ST

OUT = Path("data") / "entities"
PEOPLE = "site/data/people.json"
CAREERS = "generated/careers.json"
ROSTER = "site/legislators.json"
META = "site/meta.json"
# THE OFFICIALS' HAND FILE HAS ONE READER (the person's approval of 23 October 2026), and this
# reads it through that reader, build_members_elect.read_officials, on a day before every
# successor's, so as to hold every holder and every successor as the file writes them. This is
# how a record says it came from there; no path to the file is named here.
HAND = "corrections/officials.json, through read_officials"
OFFICERS = "site/officers.json"
ELECT = "site/members_elect.json"
DISTRICTS = "records/districts"
DISTRICTS_JSON = "site/districts.json"
REGISTER = "generated/gr_ids.json"
COUNTY_ROSTER = "collected/county_officials.json"
# What the build reads that it cannot do without; the members-elect file is there only between
# the election and Organization Day, and the county roster is read only to compare.
NEEDED = (PEOPLE, CAREERS, ROSTER, META, OFFICERS)

# THE OFFICIALS LINKED TO THE RECORD (the design study "officials-links" and the owner's answers
# of 16 November 2026; src/parse/office_links.py is the rule). The owner's own word on a holder,
# in a hand file of hers beside the officials' one, keyed by office, area, year and the name as
# printed: read when it is there, said when it is not, never written here.
OFFICIALS_LINKS = "corrections/officials_links.json"
# The 1989-1998 members no people file holds: persons of the model, so that a link to one is kept
# until their page exists (the owner's answer 8).
PAST_ROSTER = "generated/past_roster.json"
# What the pool of people an official might be is read from: every file that says something of a
# member -- a name, a middle initial, a home town, a party, a county, a term served. Without all of
# them a difference could go unseen, so a night that lacks one links nobody by the rule, and says.
FORMER = "site/former.json"
MEMBERS = "data/legislators.json"
GC_MEMBERS = "db/Legislators.psv"
GC_COLUMNS = "db/_columns.json"
PAST_MEMBERS = "past_members.json"
MEMBER_PARTY = "member_party.json"
SPONSORS = "text_sponsors.json"
MANUAL_SEATS = "generated/manual_seats.json"
STREETS = "collected/nh_streets.json"
LINK_EVIDENCE = (FORMER, MEMBERS, GC_MEMBERS, GC_COLUMNS, PAST_MEMBERS, MEMBER_PARTY, SPONSORS,
                 PAST_ROSTER, MANUAL_SEATS, STREETS)
# The files a holder may come from to be linked by the rule: the official ones the model reads
# holders from. A secondary source (NHPR's results) is never one, and is not read.
OFFICIAL = (HAND, COUNTY_ROSTER)

# What a record of the hand file keeps when a successor takes it: the office's, as
# build_members_elect.officials_on keeps them (its OFFICE_FIELDS), and whatever it holds inside it.
OFFICE_FIELDS = frozenset({"office", "scope", "about", "district", "title", "department"})

# WHERE THE HAND FILE'S HOLDERS ARE. Each path is the hand file's own keys ("*" any key, "#" a
# place in a list), and the office its record holds. A record with a name that none of these
# places, and which is not one of the named groups below, is said, because the model would not
# hold its holder.
SLOTS = (
    (("governor",), "governor"),
    (("council", "districts", "*"), "executive-council"),
    (("us_house", "districts", "*"), "us-house"),
    (("us_senate", "seats", "#"), "us-senate"),
    (("secretary_of_state",), "secretary-of-state"),
    (("treasurer",), "treasurer"),
    (("attorney_general",), "attorney-general"),
    (("department_heads", "departments", "#"), "department-head"),
    (("judicial", "supreme_court", "justices", "#"), "supreme-court-justice"),
    (("judicial", "superior_court", "justices", "#"), "superior-court-justice"),
    (("county", "counties", "*", "commissioners", "*"), "county-commissioner"),
    (("county", "counties", "*", "sheriff"), "sheriff"),
    (("county", "counties", "*", "county_attorney"), "county-attorney"),
    (("county", "counties", "*", "treasurer"), "county-treasurer"),
    (("county", "counties", "*", "register_of_deeds"), "register-of-deeds"),
    (("county", "counties", "*", "register_of_probate"), "register-of-probate"),
)
# Named groups that are not holders: a court is named, and so is a county.
NOT_HOLDERS = (("judicial", "*"), ("county", "counties", "*"))
# The first offices with pages (the design's question 3): a holder of one of these with no
# General Court number is who gr_register.py --offices would give a gr- id.
FIRST_OFFICES = ("governor", "executive-council", "us-house", "us-senate", "secretary-of-state",
                 "treasurer", "attorney-general")


class Refused(Exception):
    """A file the step needs that is not there or will not read: the step stops and says. What
    the model cannot place or hold is not a stop: it is said, and kept as the file has it where
    it can be (build)."""


def _read(root, rel, default=None):
    p = Path(root) / rel
    if not p.is_file():
        if default is not None:
            return default
        raise Refused(f"{rel} is not here")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise Refused(f"{rel} will not read as JSON ({e})")


def _hand(root):
    """The officials' hand file as its one reader gives it on a day before every successor's
    (HAND): every holder, and each successor still under "elect", as the file writes them."""
    import build_members_elect as BME
    try:
        return BME.read_officials(root=root, today=datetime.date.min)
    except OSError as e:
        raise Refused(f"the officials' hand file is not here ({e})")
    except ValueError as e:
        raise Refused(f"the officials' hand file will not read as JSON ({e})")
    except SystemExit as e:
        raise Refused(str(e))


def _match(path, pattern):
    return len(path) == len(pattern) and all(
        p == "*" and isinstance(k, str) or p == "#" and isinstance(k, int) or p == k
        for k, p in zip(path, pattern))


def _dotted(path):
    return ".".join(str(k) for k in path)


# ---- people and their terms ---------------------------------------------------------------

def people_and_service(root, settings, report):
    """(persons, tenures, numbers): the people of site/data/people.json, every term
    generated/careers.json gives each number, and today's roster's seats (site/legislators.json)
    on the newest term's tenures."""
    doc = _read(root, PEOPLE)
    careers = _read(root, CAREERS)
    roster = _read(root, ROSTER)
    meta = _read(root, META)
    offices = {o["code"]: o["office"] for o in EN.offices(settings) if o.get("district_kind") in ("house", "senate")}
    by_emp, by_mid = {}, {}
    persons = []
    for p in doc.get("people") or []:
        if p.get("replaced_by"):
            rec = {"person": str(p["person"]), "replaced_by": str(p["replaced_by"])}
        else:
            rec = {"person": str(p["person"]), "name": p.get("name"),
                   "gc_employee_numbers": [str(x) for x in p.get("employee_numbers") or []],
                   "gc_person_ids": [str(x) for x in p.get("person_ids") or []],
                   "member_ids": [str(x) for x in p.get("member_ids") or []],
                   "page": p.get("page")}
            if p.get("provisional"):
                rec["provisional"] = True
            for n in rec["gc_employee_numbers"]:
                by_emp[n] = rec
            for m in rec["member_ids"]:
                by_mid[m] = rec
        if "split_from" in p:
            rec["split_from"] = p["split_from"]
        persons.append(rec)

    # Every term careers.json gives a number: one tenure a number, chamber and term, under the
    # group careers.json made (keys.careers), which src/lib/people.py partly undoes.
    tenures, by_key = [], {}
    for key in sorted(careers):
        c = careers[key]
        for term, v in sorted((c.get("by_term") or {}).items()):
            nums, chambers = list(v.get("employee_nos") or []), list(v.get("chambers") or [])
            # A MEMBER WHO MOVED CHAMBER IN A TERM, under two numbers careers.json joins, is two
            # numbers in two chambers in one term, and nothing says which sat where. The model
            # gives each number each chamber, as careers.json and people.json do, and says so.
            if len(nums) > 1 and len(chambers) > 1:
                report["notes"].append(f"{CAREERS} {key}, {term}: {len(nums)} numbers in "
                                       f"{len(chambers)} chambers, and nothing says which sat "
                                       "where: each number is given each chamber, as the file does")
            for n in nums:
                for ch in chambers:
                    office = offices.get(ch)
                    if office is None:
                        raise Refused(f"{CAREERS} {key}, {term}: a chamber the settings do not "
                                      f"know ({ch!r})")
                    p = by_emp.get(n)
                    t = {"tenure": f"{office}:{term}:{n}", "office": office, "term": term,
                         "person": p["person"] if p else None, "gc_employee_number": n,
                         "keys": {"careers": key}, "files": [CAREERS]}
                    tenures.append(t)
                    by_key.setdefault((p["person"] if p else None, office, term), []).append(t)
        if any(c.get(f) for f in ("first", "last", "party", "chamber_last", "person_id")):
            holder = by_emp.get(key)
            if holder is None:
                report["unplaced"].append(f"{CAREERS} {key}: the roster's word on this number "
                                          "belongs to no person of people.json")
            else:
                holder.setdefault("gc_roster", {})[key] = {
                    "first": c.get("first", ""), "last": c.get("last", ""), "party": c.get("party", ""),
                    "chamber": c.get("chamber_last", ""), "person_id": c.get("person_id", "")}
        if c.get("district_by_term"):
            report["not_rebuilt"].append(f"{CAREERS} {key} gives districts by term, which the "
                                         "model does not read yet")

    # Today's roster: its members' tenures of the newest term sit, in the district and for the
    # party it gives. A sitting member with no vote yet has a tenure from the roster alone.
    terms = meta.get("terms") if isinstance(meta, dict) else None
    term = terms[0] if isinstance(terms, list) and terms else None
    if not term:
        raise Refused(f"{META} names no terms, so the roster's term is not known")
    era = EN.era_of(term, settings)
    for r in roster:
        mid = str(r.get("id"))
        p = by_mid.get(mid)
        office = offices.get(r.get("chamber"))
        if p is None or office is None:
            report["disagreements"].append({
                "what": "a sitting member the people file does not hold", "where": f"{ROSTER} {mid}",
                "says": f"{r.get('name')}, chamber {r.get('chamber')!r}",
                "other": f"{PEOPLE} gives that id to no person" if p is None else "no such chamber"})
            continue
        ts = by_key.get((p["person"], office, term)) or []
        if len(ts) > 1:
            # Two of the person's numbers voted in the chamber in the term (careers.json's
            # joining, under the moved-chamber note above). The roster's id is one of them where
            # it is an employee number; otherwise its seat is a tenure of its own (a PersonID is
            # never six digits, so its id is no number's), since nothing says which holds it.
            own = [t for t in ts if t.get("gc_employee_number") == mid]
            if len(own) == 1:
                ts = own
            else:
                report["notes"].append(f"{ROSTER} {mid}: {len(ts)} numbers of person {p['person']} "
                                       f"voted in the {office} in {term}; the seat the roster gives "
                                       "is a tenure of its own")
                ts = []
        if not ts:
            t = {"tenure": f"{office}:{term}:{mid}", "office": office, "term": term,
                 "person": p["person"], "files": []}
            tenures.append(t)
            ts = [t]
        t = ts[0]
        t["district"] = roster_district(r, era)
        t["member_id"] = mid
        t["party"] = str(r.get("party") or "")
        t["sitting"] = True
        t["files"] = t["files"] + [ROSTER]
    return persons, tenures, by_mid, term


def roster_district(r, era):
    if r.get("chamber") == "H":
        return EN.district_id("house", era, f"{EN.slug(r.get('county'))}-{int(r.get('district'))}")
    return EN.district_id("senate", era, str(int(r.get("district"))))


# ---- districts and places -----------------------------------------------------------------

def districts_and_places(root, settings):
    """(districts, places) from records/districts/*.txt, as parse_districts.combine reads them,
    of the era the settings give the files; and the counties, which are not redrawn."""
    import parse_districts as PD
    folder = Path(root) / DISTRICTS
    era = max(EN.eras(settings))
    kinds = settings["district_kinds"]
    districts, places = [], {}

    def place(town, ward):
        pid = EN.place_id(town, ward)
        return places.setdefault(pid, {"place": pid, "town": town, "ward": ward, "county": None,
                                       "in": {era: []}, "source": DISTRICTS})

    hp = folder / "house.txt"
    if not hp.is_file():
        raise Refused(f"{DISTRICTS}/house.txt is not here")
    for (county, num), rec in PD.parse_house(hp).items():
        k = kinds["house"]
        n = int(num)
        did = EN.district_id("house", era, f"{EN.slug(county)}-{n}")
        fill = {"county": county, "n": n, "county_abbr": ST.COUNTY_ABBR.get(county, county),
                "county_code": ST.COUNTY_CODE.get(county, "")}
        d = {"district": did, "kind": "house", "era": era, "name": k["name"].format(**fill),
             "county": county, "number": n, "seats": rec["seats"], "floterial": rec["floterial"],
             "places": [], "keys": {"results": k["results"].format(**fill), "map": k["map"].format(**fill),
                                    "label": k["label"].format(**fill)},
             "source": f"{DISTRICTS}/house.txt"}
        for town, ward in rec["towns"]:
            pl = place(town, ward)
            pl["in"][era].append(did)
            pl["county"] = county if pl["county"] in (None, county) else pl["county"]
            d["places"].append(pl["place"])
        districts.append(d)
    for kind in ("senate", "council", "congress"):
        k = kinds[kind]
        p = folder / Path(k["file"]).name
        if not p.is_file():
            raise Refused(f"{k['file']} is not here")
        for num, entries in PD.parse(p).items():
            n = int(num)
            did = EN.district_id(kind, era, str(n))
            d = {"district": did, "kind": kind, "era": era, "name": k["name"].format(n=n),
                 "number": n, "seats": 1, "places": []}
            if k.get("results"):
                d["keys"] = {"results": k["results"].format(n=n)}
            d["source"] = k["file"]
            for town, ward in entries:
                pl = place(town, ward)
                pl["in"][era].append(did)
                d["places"].append(pl["place"])
            districts.append(d)
    by_id = {d["district"]: d for d in districts}
    for d in districts:
        if d.get("floterial"):
            d["floterial_over"] = sorted({b for pl in d["places"] for b in places[pl]["in"][era]
                                          if by_id[b]["kind"] == "house" and not by_id[b]["floterial"]})
            d["keys"] = d.pop("keys")
            d["source"] = d.pop("source")
    for pl in places.values():
        pl["in"][era] = sorted(set(pl["in"][era]))
        pl["source"] = pl.pop("source")
    k = kinds["county"]
    for county in ST.COUNTIES:
        districts.append({"district": EN.district_id("county", None, EN.slug(county)), "kind": "county",
                          "name": k["name"].format(county=county),
                          "source": "src/lib/state_settings.json counties"})
    return districts, sorted(places.values(), key=lambda pl: (pl["town"], int(pl["ward"])))


# ---- the hand file's offices --------------------------------------------------------------

def hand_offices(root, settings, by_page, register, report):
    """(offices, tenures, layout) of corrections/officials.json: each holder a tenure (and a
    successor under "elect" a second tenure of the same seat, from the day it names), each
    department an office of its own, and the rest of the file the layout, with each holder's
    place marked."""
    doc = _hand(root)
    era = max(EN.eras(settings))
    base = {o["office"]: o for o in EN.offices(settings)}
    issued = {}
    for e in (register or {}).get("ids") or []:
        for place in (e["issued_for"] if isinstance(e.get("issued_for"), list) else [e.get("issued_for")]):
            if place:
                issued.setdefault(place.removesuffix(".elect"), []).append(e)
    offices, tenures, seen_dept = [], [], {}

    def where(office, path):
        """(district, seat) of a holder at `path`."""
        if office == "executive-council":
            return EN.district_id("council", era, str(int(path[2]))), None
        if office == "us-house":
            return EN.district_id("congress", era, str(int(path[2]))), None
        if office == "us-senate":
            return None, str(path[2] + 1)
        if office == "county-commissioner":
            return EN.district_id("county", None, EN.slug(path[2])), str(path[4])
        if base.get(office, {}).get("scope") == "county":
            return EN.district_id("county", None, EN.slug(path[2])), None
        return None, None

    def link(t, rec):
        """The person a hand entry links the holder to: the page address it names, as
        site/data/people.json gives that page; or the gr- id the register issued for this place
        and this name. Never a name alone."""
        page = rec.get("member")
        if page:
            p = by_page.get(f"/legislator/{page}")
            if p is None:
                report["disagreements"].append({
                    "what": "a hand link names a page no person has",
                    "where": f"the hand file's {_dotted(t['slot']['path'])}",
                    "says": f"member {page}", "other": f"{PEOPLE} gives that page to nobody"})
            else:
                t["person"], t["linked_by"] = p["person"], f"member /legislator/{page}"
                return
        for e in issued.get(t["tenure"].removesuffix(".elect"), []):
            if " ".join(str(e.get("named_as") or "").split()) == " ".join(str(rec.get("name")).split()):
                t["person"], t["linked_by"] = e["id"], f"{REGISTER} {e['id']}, issued for this place"
                return

    def holder(path, rec, office):
        tid = f"officials:{_dotted(path)}"
        district, seat = where(office, path)
        kept = {k: v for k, v in rec.items()
                if k != "elect" and (k in OFFICE_FIELDS or isinstance(v, (dict, list)))}
        t = {"tenure": tid, "office": office}
        if district:
            t["district"] = district
        if seat:
            t["seat"] = seat
        t["person"] = None
        t["printed"] = str(rec.get("name"))
        if "party" in rec:
            t["party"] = rec["party"]
        rest = {k: v for k, v in rec.items() if k not in kept and k not in ("name", "party", "elect")}
        if rest:
            t["holder"] = rest
        t["slot"] = {"path": list(path), "order": list(rec), "kept": kept}
        t["files"] = [HAND]
        link(t, rec)
        out = [t]
        e = rec.get("elect")
        if isinstance(e, dict):
            s = {"tenure": tid + ".elect", "office": office}
            if district:
                s["district"] = district
            if seat:
                s["seat"] = seat
            s["person"] = None
            s["printed"] = str(e.get("name"))
            if "party" in e:
                s["party"] = e["party"]
            if EN._day(e.get("takes_office")) is None:
                raise Refused(f"the hand file's {_dotted(path)}.elect takes office on "
                              f"{e.get('takes_office')!r}, which is no day")
            s["from"] = e["takes_office"]
            rest = {k: v for k, v in e.items() if k not in ("name", "party", "takes_office")}
            if rest:
                s["holder"] = rest
            s["slot"] = {"path": list(path) + ["elect"], "order": list(e)}
            s["files"] = [HAND]
            link(s, e)
            out.append(s)
        return out

    def office_of(office, path, rec):
        """The office record a holder at `path` holds: the settings' own, or a department's."""
        if office != "department-head":
            return office
        dept = str(rec.get("department") or "")
        oid = f"department-head:{EN.slug(dept)}"
        if oid not in seen_dept:
            b = base["department-head"]
            seen_dept[oid] = {"office": oid, "name": f"{rec.get('title')}, {dept}", "scope": b["scope"],
                              "seats": 1, "filled_by": b["filled_by"], "constitution": b["constitution"],
                              "of": "department-head", "department": dept, "title": str(rec.get("title")),
                              "source": f"{HAND} {_dotted(path)}"}
            if rec.get("official_url"):
                seen_dept[oid]["official_url"] = rec["official_url"]
            offices.append(seen_dept[oid])
        return oid

    def walk(x, path):
        if isinstance(x, list):
            return [walk(v, path + (i,)) for i, v in enumerate(x)]
        if not isinstance(x, dict):
            return x
        hit = next((o for pat, o in SLOTS if _match(path, pat)), None)
        if hit is None and "elect" in x:
            # Kept as written, so the file still comes back whole; said, so the place is added.
            report["unplaced"].append(f"the hand file's {_dotted(path)} names a successor in a place "
                                      "the model does not know as an office's: kept in the layout as "
                                      "written, with no tenure; add the place to build_entities.SLOTS")
            return json.loads(json.dumps(x))
        if hit is not None:
            ts = holder(path, x, office_of(hit, path, x))
            tenures.extend(ts)
            return {"$tenure": ts[0]["tenure"]}
        if "name" in x and path and not any(_match(path, pat) for pat in NOT_HOLDERS):
            report["unplaced"].append(f"the hand file's {_dotted(path)} has a name and is no office's "
                                      "holder the model knows: add it to build_entities.SLOTS")
        return {k: walk(v, path + (k,)) for k, v in x.items()}

    layout = walk(doc, ())
    return offices, tenures, layout


def gr_candidates(root=".", settings=None, register=None):
    """[{tenure, office, name, evidence}]: the holders and successors of the first offices with
    pages (FIRST_OFFICES; the design's question 3, 19 records on 16 November 2026) whom the model
    links to no person of the record, and for whom the register has issued no id. Who
    gr_register.py --offices would give a gr- id, in the hand file's order; writes nothing.

    EVERY HOLDER THE MODEL LINKS IS LEFT OUT BEFORE ANY ID IS OFFERED (16 November 2026). The
    model is built whole for it (build), so a holder is left out who is linked by the hand file's
    "member" page (or names one), by an id the register issued for the place, by the owner's hand
    file of links, or by the rule of src/parse/office_links.py: on the files of 16 November, Joseph
    D. Kenney, Luz Bay, Melanie Levesque and Jeanne Shaheen, whom the hand file alone left
    unlinked. A holder the owner says is no one of the record is offered one; a holder on her list
    to settle is offered one too, and takes a member's number if she links them later, the id
    staying as their alias (gr_ids.py). Refused where the model cannot be built, or where the rule
    could not run (its evidence not all here, or her file will not read): who it links is then not
    known, and an id once issued is never taken back."""
    settings = settings or ST.SETTINGS
    model, layouts, report = build(root, settings, register=register)
    lk = report.get("links") or {}
    if lk.get("rule_off"):
        raise Refused(f"who the model links is not known here ({lk['rule_off']}): no gr- id is offered "
                      "until it is, since an id once issued is never taken back")
    layout = layouts[HAND]
    names = {o["office"]: o["name"] for o in EN.offices(settings)}
    listed = {x["tenure"]: x for x in lk.get("listed") or []}
    out = []
    for t in model["tenure"]:
        if HAND not in (t.get("files") or []) or t["office"] not in FIRST_OFFICES:
            continue
        if t.get("person") or (t.get("holder") or {}).get("member"):
            continue
        rec = (t.get("holder") or {})
        read = rec.get("read") or layout.get("_checked") or "?"
        link = t.get("link") or {}
        why = (f"the owner's hand file of links says they are no one of the record ({link.get('why')})"
               if link.get("by") == "owner" else
               "the rule of 16 November 2026 links them to no one"
               + (f" (on the owner's list to settle: {listed[t['tenure']]['why']})" if t["tenure"] in listed else ""))
        out.append({"tenure": t["tenure"], "office": t["office"], "name": t["printed"],
                    "evidence": f"{'Takes' if t.get('from') else 'Holds'} the office of {names[t['office']]} in "
                                f"the officials' hand file at {_dotted(t['slot']['path'])} (read {read}"
                                + (f", from {t['from']}" if t.get("from") else "") + "), and the model links "
                                f"them to no person of the record: no member page, no person number, and "
                                f"{why}. A shared name is not a link."})
    return out


# ---- the chair's offices --------------------------------------------------------------------

def officer_tenures(root, settings, by_mid, report):
    """(tenures, offices): site/officers.json's tenures, each of the office its name is in the
    settings; an office the settings do not list is an office of its own, from the file, and
    said."""
    doc = _read(root, OFFICERS)
    by_name = {(o["name"], o.get("code")): o["office"] for o in EN.offices(settings) if o["scope"] == "chamber"}
    out, extra = [], {}
    for r in doc.get("officers") or []:
        office = by_name.get((r.get("office"), r.get("b")))
        if office is None:
            office = f"officer:{EN.slug(r.get('office'))}"
            if office not in extra:
                extra[office] = {"office": office, "name": str(r.get("office")), "scope": "chamber",
                                 "code": str(r.get("b")), "filled_by": None, "constitution": [],
                                 "source": f"{OFFICERS}, which names an office the settings do not list"}
                report["notes"].append(f"{OFFICERS} names an office the settings do not list, "
                                       f"{r.get('office')!r} of {r.get('b')!r}: an office of its own; "
                                       "add it to src/lib/state_settings.json offices")
        mid = str(r["id"])
        p = by_mid.get(mid)
        t = {"tenure": f"officers:{office}:{r['from']}:{mid}", "office": office,
             "term": proceedings.term_on(r["from"]), "person": p["person"] if p else None,
             "member_id": mid, "printed": r["name"], "title": r["title"], "kind": r["kind"],
             "from": r["from"], "to": r["to"], "keys": {"ballot_sort": r["s"]},
             "files": [OFFICERS], "source": r["source"]}
        out.append(t)
    return out, list(extra.values())


# ---- the members-elect ----------------------------------------------------------------------

def members_elect(root, settings, by_mid):
    """(contests, candidacies, tenures, layout) of site/members_elect.json, in its order; nothing
    where the file is not on disk, as outside the weeks between the election and Organization
    Day. Its layout is what the file says that is no record's: its list of the results'
    addresses, one for each spreadsheet read."""
    p = Path(root) / ELECT
    if not p.is_file():
        return [], [], [], None
    doc = _read(root, ELECT)
    era = EN.era_of(doc["term"], settings)
    contests, cands, tenures = [], [], []
    for key, race in doc["races"].items():
        parts = key.split("|")
        if parts[0] == "H":
            office, where = "house", f"{EN.slug(parts[1])}-{int(parts[2])}"
        elif parts[0] == "S":
            office, where = "senate", str(int(parts[1]))
        else:
            raise Refused(f"{ELECT} race {key!r} is of no chamber")
        did = EN.district_id(office, era, where)
        cid = EN.contest_id(doc["election"], "general", office, where)
        c = {"contest": cid, "election": doc["election"], "stage": "general", "office": office,
             "district": did, "seats": race["seats"], "not_final": race.get("not_final", 0),
             "held": race.get("held", 0)}
        if race.get("recount"):
            c["recount"] = True
        # The results' addresses, once each; the file's own list, one a spreadsheet read, is its
        # layout's.
        c.update({"term": doc["term"], "takes_office": doc["takes_office"],
                  "sources": list(dict.fromkeys(doc.get("sources") or [])), "keys": {"results": key},
                  "source": ELECT})
        contests.append(c)
        for e in race.get("elected") or []:
            xid = EN.candidacy_id(cid, e["n"], e.get("p"))
            mid = str(e["id"]) if e.get("id") else None
            person = by_mid[mid]["person"] if mid and mid in by_mid else None
            x = {"candidacy": xid, "contest": cid, "printed": e["n"], "party": e.get("p", ""),
                 "elected": True, "person": person}
            if mid:
                x["member_id"] = mid
            if "k" in e:
                x["status"] = e["k"]
            if e.get("own"):
                x["own"] = True
            if e.get("u"):
                x["doubt"] = True
            if "prior" in e:
                x["prior"] = e["prior"]
            keys = {}
            if "s" in e:
                keys["page"] = e["s"]
            if "e" in e:
                keys["elect_page"] = e["e"]
            if keys:
                x["keys"] = keys
            x["source"] = ELECT
            cands.append(x)
            t = {"tenure": f"elect:{xid}", "office": office, "district": did, "term": doc["term"],
                 "person": person}
            if mid:
                t["member_id"] = mid
            t.update({"printed": e["n"], "party": e.get("p", ""), "from": doc["takes_office"],
                      "candidacy": xid, "files": [ELECT]})
            tenures.append(t)
    return contests, cands, tenures, {"sources": list(doc.get("sources") or [])}


# ---- terms ----------------------------------------------------------------------------------

def terms_of(names):
    """A term record for every term from the first of `names` to the last, its days by the
    Constitution's rule (Pt. 2, Art. 3: the General Court organizes on the first Wednesday of
    December of the even year, and dissolves at 12:01 A.M. on that day two years on)."""
    out = []
    starts = [int(t[:4]) for t in names]
    for a in range(min(starts), max(starts) + 1, 2) if starts else ():
        t, b = f"{a}-{a + 1}", a + 1
        start = proceedings.organization_day(a - 1)
        end = proceedings.organization_day(b) - datetime.timedelta(days=1)
        out.append({"term": t, "body": "general-court", "from": start.isoformat(), "to": end.isoformat(),
                    "source": "Const. Pt. 2, Art. 3, as proceedings.organization_day applies it"})
    return out


# ---- where today's files disagree -----------------------------------------------------------

def county_roster(root, hand_tenures):
    """(tenures, disagreements, seats compared) of the county officers the Secretary of State's
    roster names (collected/county_officials.json, the 2024 winners as its day read them),
    against the hand file's holders, which the pages read.

    A SEAT KEPT TWICE. Where both name the same holder, the hand file's tenure is the one, and
    says it is in both files. Where they differ -- a vacancy filled since the roster's day --
    the roster's holder is a tenure of their own of the same seat, so the seat has two, the
    earlier and the current: a mid-term change as two tenures of one seat. Neither is dated:
    neither file gives the day one ended and the next began as a date (the hand file's note says
    it in words, which are not read for one). Which seats differ, and how, is said; none is
    changed."""
    roster = _read(root, COUNTY_ROSTER, default={})
    by_seat = {(t["office"], t.get("district"), t.get("seat")): t for t in hand_tenures
               if not t["tenure"].endswith(".elect")}
    offices = {"Sheriff": "sheriff", "County Attorney": "county-attorney", "County Treasurer":
               "county-treasurer", "Register of Deeds": "register-of-deeds", "Register of Probate":
               "register-of-probate", "County Commissioner": "county-commissioner"}
    tenures, out, n = [], [], 0
    for r in roster.get("officers") or []:
        office = offices.get(r.get("office"))
        if office is None:
            out.append({"what": "a county office the model does not know", "where": f"{COUNTY_ROSTER}",
                        "says": f"{r.get('county')} {r.get('office')}: {r.get('name')}",
                        "other": "compared with nothing, and held by no tenure"})
            continue
        county = str(r.get("county"))
        seat = str(r["district"]) if office == "county-commissioner" else None
        district = EN.district_id("county", None, EN.slug(county))
        where = f"{county} {r.get('office')}" + (f", district {seat}" if seat else "")
        n += 1
        mine = by_seat.get((office, district, seat))
        if mine is None:
            out.append({"what": "a county seat the roster names and the hand file does not",
                        "where": where, "says": f"{COUNTY_ROSTER}: {r.get('name')}",
                        "other": "the officials' hand file names no holder of it"})
        diffs = []
        if mine is not None:
            held = mine.get("holder") or {}
            for f, a, b in (("name", r.get("name"), mine.get("printed")),
                            ("town", r.get("domicile"), held.get("domicile")),
                            ("party", r.get("party"), held.get("party_as_printed"))):
                a, b = str(a or ""), str(b or "")
                if (a and b or f == "name") and a != b:
                    diffs.append(f"{f} {b!r} against {a!r}")
        if mine is not None and not diffs:
            mine["files"] = mine["files"] + [COUNTY_ROSTER]
            continue
        if diffs:
            note = (mine.get("holder") or {}).get("note")
            out.append({"what": "a county officer kept twice, differently", "where": where,
                        "says": f"the hand file's {_dotted(mine['slot']['path'])}: " + "; ".join(diffs),
                        "other": f"{COUNTY_ROSTER} (the Secretary of State's roster, read "
                                 f"{roster.get('_read_on')})" + (f"; the hand file's note: {note}" if note else "")})
        if mine is None or EN.slug(r.get("name")) != EN.slug(mine.get("printed")):
            t = {"tenure": f"county-roster:{EN.slug(county)}:{office}" + (f":{seat}" if seat else ""),
                 "office": office, "district": district}
            if seat:
                t["seat"] = seat
            t.update({"person": None, "printed": str(r.get("name")), "party": str(r.get("party") or ""),
                      "files": [COUNTY_ROSTER], "source": f"{r.get('source_url')}, read {r.get('read_on')}"})
            # The roster's town of residence and its day, which the officials' links weigh.
            held = {k: str(r[k]) for k in ("domicile", "read_on") if r.get(k)}
            if held:
                t["holder"] = held
            tenures.append(t)
    return tenures, out, n


def roster_party_disagreements(tenures, persons):
    """A sitting member whose roster party (site/legislators.json) and the party the General
    Court's roster gives their number in careers.json differ by their first letter."""
    roster = {n: r for p in persons for n, r in (p.get("gc_roster") or {}).items()}
    out = []
    for t in tenures:
        if t.get("sitting") and t.get("gc_employee_number") in roster:
            a = (t.get("party") or "")[:1].upper()
            b = (roster[t["gc_employee_number"]].get("party") or "")[:1].upper()
            if a and b and a != b:
                out.append({"what": "a sitting member's party, two ways", "where": t["tenure"],
                            "says": f"{ROSTER}: {t['party']}",
                            "other": f"{CAREERS}: {roster[t['gc_employee_number']]['party']}"})
    return out


# ---- the officials, linked to the record ---------------------------------------------------------
#
# THE RULE IS src/parse/office_links.py's; what is here is New Hampshire's side of it: who the
# pool of people is and what the files say of each, which tenures are holders of an office the
# legislature does not fill, the owner's hand file, and where the links go (each holder's tenure:
# "person" and "link"; the owner's list in the manifest). Town offices are not here: the model
# holds none, and the owner's answer 4 is that none is linked until a town page shows them.

def past_people(root, persons, report):
    """[person]: the members of 1989-1998 that generated/past_roster.json names and no person of
    site/data/people.json holds a number of, each under the number the roster gives them (its
    "person", the General Court's employee number), so that a link to one is kept until their
    page exists. They are in no view of today's files ("files" marks them)."""
    p = Path(root) / PAST_ROSTER
    if not p.is_file():
        report["notes"].append(f"{PAST_ROSTER} is not here: the members of 1989-1998 with no page "
                               "are not in the model, and no official can be linked to one")
        return []
    held = {n for x in persons for n in x.get("gc_employee_numbers") or []}
    taken = {x["person"] for x in persons}
    out, seen = [], {}
    for r in _read(root, PAST_ROSTER).get("rows") or []:
        num = str(r.get("person") or r.get("gc_employee_number") or "")
        # The roster's word that two of its numbers are one person: one person, under the
        # number met first, holding both.
        same = str(r.get("same_person_as_employee_number") or "")
        if not re.match(r"^\d+$", num) or num in held or same in held:
            continue
        if num in seen or same in seen:
            rec = seen.get(num) or seen[same]
            for n in (num, same):
                if n and n not in rec["gc_employee_numbers"]:
                    rec["gc_employee_numbers"].append(n)
                    seen[n] = rec
            continue
        if num in taken:
            report["notes"].append(f"{PAST_ROSTER} {num} is a number a person of {PEOPLE} goes by: "
                                   "kept out of the model")
            continue
        rec = {"person": num, "name": str(r.get("name") or ""),
               "gc_employee_numbers": [n for n in (num, same) if n], "files": [PAST_ROSTER]}
        for n in rec["gc_employee_numbers"]:
            seen[n] = rec
        out.append(rec)
    return out


def county_name(raw):
    """A county's name from a file's spelling of it ("Hills", "hillsborough", "Hills."); "" for
    none."""
    s = str(raw or "").strip().rstrip(".").lower()
    if not s:
        return ""
    if s in ST.COUNTY_LOOKUP:
        return ST.COUNTY_LOOKUP[s]
    hit = [c for c in ST.COUNTIES if s == c.lower() or (len(s) >= 4 and c.lower().startswith(s[:4]))]
    return hit[0] if len(hit) == 1 else ""


# An address in the State House or its offices, which says where a member works and not where
# they live (the General Court's member table gives one for a few members).
STATEHOUSE = re.compile(r"north main|state house|capitol st|north state st|legislative office|"
                        r"\blob\b|room \d", re.I)


def link_pool(root, model, roster_term, report):
    """(pool, missing): every person an official might be, with what the files on disk say of
    each -- {"key", "person", "kind", "label", "names", "middles", "sfx", "parties", "counties",
    "homes", "district_towns", "terms", "sources"} -- or (None, [the evidence files not here]).

    The pool is the model's people (site/data/people.json's and the 1989-1998 members with no
    page) and the members-elect the General Court has not numbered, who answer to a name as
    much as anyone (an official of their name is not linked while they do). Read as the
    study's people_index.py read them, 16 November 2026: the names every file spells, the middle
    initials the General Court's member table and the Manual's returns print, the home town of
    the member table's address where it is not the State House's, and of the Manual's returns;
    the parties and counties every file gives; the terms each served."""
    import build_members_elect as BME
    import office_links as OL
    root = Path(root)
    missing = [n for n in LINK_EVIDENCE if not (root / n).is_file()]
    if missing:
        return None, missing
    pool, by_mid, by_emp = {}, {}, {}

    def entry(key, person, kind, label):
        e = pool.get(key)
        if e is None:
            e = pool[key] = {"key": key, "person": person, "kind": kind, "label": label, "names": [],
                             "middles": set(), "sfx": set(), "parties": set(), "counties": set(),
                             "homes": set(), "district_towns": set(), "terms": set(), "sources": set()}
        return e

    def named(e, raw, middle=""):
        raw = " ".join(str(raw or "").split())
        if raw and raw not in e["names"]:
            e["names"].append(raw)
            rd, sfx = BME.readings(raw)
            e["sfx"] |= set(sfx)
            for _s, f in rd:
                e["middles"] |= OL.middle_initials(f)
        m = BME.fold(middle or "").strip()
        if m and m[0].isalpha():
            e["middles"].add(m[0].lower())

    # Towns: the municipalities the district lists name, and each ZIP code's towns (the Census
    # Bureau's street list), so that a postal name in an address reads as the town it is in, or
    # as unknown where a ZIP spans towns.
    muni = {re.sub(r"[^a-z ]", "", pl["town"].lower()).strip(): pl["town"] for pl in model.get("place") or []}
    zips = {}
    streets = _read(root, STREETS)
    col = {c: i for i, c in enumerate(streets.get("columns") or [])}
    for row in streets.get("rows") or []:
        zips.setdefault(str(row[col["zip"]])[:5], set()).add(row[col["town"]])

    def town_of(city, zipcode=""):
        c = re.sub(r"[^a-z ]", "", BME.fold(city or "").lower()).strip()
        if c in muni:
            return muni[c], "named"
        pre = [t for k, t in muni.items() if len(c) >= 6 and k.startswith(c)]
        if len(pre) == 1:
            return pre[0], "named (cut)"
        z = zips.get(str(zipcode or "")[:5])
        if z and len(z) == 1:
            return next(iter(z)), "zip"
        return "", ""

    def home(e, town, how, src):
        e["homes"].add(town)
        e["sources"].add(f"home {town}: {src} ({how})")

    # The model's people: today's people file, and the 1989-1998 members with no page.
    for p in model.get("person") or []:
        if p.get("replaced_by") or re.match(EN.GR, str(p["person"])):
            continue
        e = entry(p["person"], p["person"], "past" if p.get("files") else "record", p.get("name") or "")
        named(e, p.get("name"))
        for n in p.get("gc_employee_numbers") or []:
            by_emp[str(n)] = e
        for m in p.get("member_ids") or []:
            by_mid[str(m)] = e
        for m in p.get("gc_person_ids") or []:
            by_mid.setdefault(str(m), e)

    # The terms each number served, the roster's names and parties for it.
    for key, c in _read(root, CAREERS).items():
        for term, v in (c.get("by_term") or {}).items():
            for n in v.get("employee_nos") or []:
                if str(n) in by_emp:
                    by_emp[str(n)]["terms"].add(term)
        e = by_emp.get(str(key))
        if e is not None:
            if c.get("first") or c.get("last"):
                named(e, f"{c.get('first', '')} {c.get('last', '')}")
            e["parties"] |= OL.party_set(c.get("party"))

    # Today's roster and the former members': names, parties, counties, and the towns of a
    # sitting member's district.
    for rel, sitting in ((ROSTER, True), (FORMER, False)):
        for m in _read(root, rel):
            e = by_mid.get(str(m.get("id")))
            if e is None:
                continue
            named(e, m.get("name"))
            named(e, re.sub(r"^(?:Rep|Sen)\.\s+", "", str(m.get("display_plain") or "")))
            e["parties"] |= OL.party_set(m.get("party"))
            if county_name(m.get("county")):
                e["counties"].add(county_name(m.get("county")))
            if sitting:
                e["district_towns"] |= set(m.get("towns") or [])
                if roster_term:
                    e["terms"].add(roster_term)
    # The sitting members' file names each county with the General Court's code for it, which the
    # member table below gives alone ("06" is Hillsborough).
    counties = {}
    for m in _read(root, MEMBERS):
        code = str(m.get("county_code") or "")
        if code.isdigit() and county_name(m.get("county")):
            counties[int(code)] = county_name(m.get("county"))
        e = by_mid.get(str(m.get("id")))
        if e is None:
            continue
        named(e, f"{m.get('first', '')} {m.get('middle', '')} {m.get('last', '')}", m.get("middle"))
        addr = str(m.get("address") or "")
        parts = [a.strip() for a in addr.split(",")]
        if addr and not STATEHOUSE.search(addr) and len(parts) >= 3 and parts[-2] == ST.STATE_ABBREVIATION:
            town, how = town_of(parts[-3], parts[-1])
            if town:
                home(e, town, how, MEMBERS)

    # The General Court's member table, in the database dump: names with middle names, party,
    # county, and the city of an address that is not the State House's.
    lcols = _read(root, GC_COLUMNS).get("Legislators") or []
    for line in (root / GC_MEMBERS).read_text(encoding="utf-8", errors="replace").splitlines():
        f = line.split("|")
        if len(f) < len(lcols):
            continue
        r = dict(zip(lcols, f))
        e = by_mid.get(r.get("PersonID", "")) or by_emp.get(r.get("Employeeno", ""))
        if e is None:
            continue
        named(e, f"{r.get('FirstName', '')} {r.get('MiddleName', '')} {r.get('LastName', '')}", r.get("MiddleName"))
        e["parties"] |= OL.party_set(r.get("party"))
        code = str(r.get("countycode") or "")
        if code.isdigit() and int(code) in counties:
            e["counties"].add(counties[int(code)])
        city = str(r.get("city") or "").strip()
        if city and not STATEHOUSE.search(f"{r.get('Address', '')} {r.get('address2', '')}"):
            town, how = town_of(city, r.get("Zipcode"))
            if town:
                home(e, town, how, GC_MEMBERS)

    # The General Court's list of past members and its party list, by employee number.
    seat_re = re.compile(r"^(Rep|Sen)\.\s+(.*?)\((?:Dist\.\s*(\d+)|([A-Za-z]+)\.?\s*(\d+))\)\s*$")
    for emp, raw in _read(root, PAST_MEMBERS).items():
        e = by_emp.get(str(emp))
        m = seat_re.match(str(raw or ""))
        if e is None or not m:
            continue
        named(e, m.group(2))
        if m.group(4) and county_name(m.group(4)):
            e["counties"].add(county_name(m.group(4)))
    for emp, x in _read(root, MEMBER_PARTY).items():
        e = by_emp.get(str(emp))
        if e is not None:
            e["parties"] |= OL.party_set(x.get("party"))
            if county_name(x.get("county")):
                e["counties"].add(county_name(x.get("county")))

    # The seat and party each sponsor printed, by term, and so who held each seat: what joins
    # the Manual's returns, which print a full name and a town, to a person.
    seats = {}
    for term, bills in _read(root, SPONSORS).items():
        for rows in bills.values():
            for sp in rows or []:
                num = str(sp.get("member_id") or "")
                e = by_mid.get(num) or by_emp.get(num)
                if e is None:
                    continue
                e["parties"] |= OL.party_set(sp.get("party"))
                c = county_name(sp.get("county"))
                if c:
                    e["counties"].add(c)
                d = str(sp.get("district") or "").lstrip("0")
                ch = str(sp.get("chamber") or "")[:1]
                if d and ch:
                    k = (term, ch, c if ch == "H" else "", d)
                    if e not in seats.setdefault(k, []):
                        seats[k].append(e)
                e["terms"].add(term)
    for r in _read(root, PAST_ROSTER).get("rows") or []:
        num = str(r.get("person") or r.get("gc_employee_number") or "")
        e = by_emp.get(num) or by_emp.get(str(r.get("same_person_as_employee_number") or ""))
        if e is None:
            continue
        named(e, r.get("name"))
        e["terms"].add(r["term"])
        for s in r.get("seats") or []:
            c = county_name(s.get("county"))
            if c:
                e["counties"].add(c)
            d = str(s.get("district") or "").lstrip("0")
            k = (r["term"], r.get("chamber"), c if r.get("chamber") == "H" else "", d)
            if d and e not in seats.setdefault(k, []):
                seats[k].append(e)

    # The Manual's returns, 1989-1999: a full name, a town and a party for each seat's winner,
    # placed on the one person of that seat and term whose surname and first name fit (two of
    # one surname in one seat, the Syteks of Salem, are two people).
    for term, t in (_read(root, MANUAL_SEATS).get("terms") or {}).items():
        for ch, rows in (("H", t.get("house") or []), ("S", t.get("senate") or [])):
            for r in rows:
                if ch == "H" and r.get("status") not in ("elected", None):
                    continue
                c = county_name(r.get("county")) if ch == "H" else ""
                d = str(r.get("district") or "").lstrip("0")
                rd, _sfx = BME.readings(r.get("name") or "")
                fits = [e for e in seats.get((term, ch, c, d), [])
                        if any(s == ps and OL.relation(f, pf) in ("exact", "short", "loose")
                               for s, f in rd for n in e["names"] for ps, pf in BME.readings(n)[0])]
                if len(fits) != 1:
                    continue
                e = fits[0]
                named(e, r.get("name"))
                if r.get("town"):
                    town, how = town_of(r["town"])
                    if town:
                        home(e, town, how, f"{MANUAL_SEATS} {r.get('edition')}")
                e["parties"] |= OL.party_set(r.get("party"))

    # The members-elect: a numbered one serves the coming term; one the General Court has not
    # numbered is in the pool by their name, party, county and district's towns.
    D = {d["district"]: d for d in model.get("district") or []}
    PL = {pl["place"]: pl for pl in model.get("place") or []}
    contests = {c["contest"]: c for c in model.get("contest") or []}
    for x in model.get("candidacy") or []:
        c = contests.get(x.get("contest")) or {}
        if not x.get("elected"):
            continue
        if x.get("person"):
            e = pool.get(x["person"])
            if e is not None and c.get("term"):
                e["terms"].add(c["term"])
                e["parties"] |= OL.party_set(x.get("party"))
            continue
        e = entry(f"elect:{x['candidacy']}", None, "elect", x.get("printed") or "")
        named(e, x.get("printed"))
        e["parties"] |= OL.party_set(x.get("party"))
        d = D.get(c.get("district")) or {}
        if d.get("county"):
            e["counties"].add(d["county"])
        e["district_towns"] |= {PL[pl]["town"] for pl in d.get("places") or [] if pl in PL}
        if c.get("term"):
            e["terms"].add(c["term"])
    return list(pool.values()), []


def link_holders(model, settings, checked=""):
    """[(tenure, holder)]: every tenure of an office the legislature does not fill that the model
    holds from an official file -- the hand file's holders and successors, the county roster's
    -- with what the rule weighs of it: {"tenure", "key", "office", "printed", "party", "town",
    "area", "terms", "day"}. The area is the office's district (its towns, on the map of the
    term held where one is on file), its county, or "statewide"; the term is the one the record
    shows the office held in: a holder's on the day the hand file read them (`checked`, its
    _checked, where the record names none), a successor's from the day they take office, the
    roster's on its day."""
    import office_links as OL
    O = {o["office"]: o for o in model.get("office") or []}
    D = {d["district"]: d for d in model.get("district") or []}
    places = model.get("place") or []
    slugs = {EN.slug(c): c for c in ST.COUNTIES}
    out = []
    for t in model.get("tenure") or []:
        files = t.get("files") or []
        if not any(f in OFFICIAL for f in files) or t.get("office") in ("house", "senate"):
            continue
        o = O.get(t["office"]) or {}
        held = t.get("holder") or {}
        if t.get("from") and t["tenure"].endswith(".elect"):
            day = t["from"]
        else:
            day = held.get("read") or held.get("read_on") or checked
        term = proceedings.term_on(day) if EN._day(day) else ""
        did = t.get("district")
        d = D.get(did) or {}
        kind = d.get("kind")
        if o.get("scope") == "statewide" or (not did and o.get("scope") != "county"):
            area, where = {"kind": "statewide"}, "statewide"
        elif kind == "county":
            county = slugs.get(did.split(":")[-1], "")
            area = {"kind": "county", "county": county}
            where = EN.slug(county) + (f":{t['seat']}" if t.get("seat") else "")
        elif d:
            where = str(d.get("number") or did.split(":")[-1])
            era = EN.era_of(term, settings) if term else None
            if era and era == d.get("era"):
                towns = {}
                town_county = {}
                for pl in places:
                    if did in (pl.get("in") or {}).get(era, []):
                        towns[OL.town_key(pl["town"])] = pl["town"]
                        town_county[OL.town_key(pl["town"])] = pl.get("county")
                area = {"kind": "district", "id": did, "towns": towns, "town_county": town_county}
            else:
                area = {"kind": "unknown", "why": f"no map of the districts of {term or 'the term held'} on file"}
        else:
            area, where = {"kind": "unknown", "why": "the office's area is not on file"}, "unknown"
        out.append((t, {"tenure": t["tenure"], "office": t["office"], "printed": t.get("printed") or "",
                        "party": t.get("party") or held.get("party") or "", "town": held.get("domicile") or "",
                        "area": area, "terms": [term] if term else [], "day": day,
                        "key": OL.hand_key(t["office"], where, term[:4] if term else "", t.get("printed"))}))
    return out


def read_owner_links(root, report):
    """The owner's hand file of links (OFFICIALS_LINKS), as {"links": {key: entry}, "name_forms":
    {person: [entry]}, "checked"}; None where it is not there, which is said; and where it is
    there but will not read, or names a key or a person the model cannot take, that is said too
    (report "links_hand"), and an entry the model cannot take is left out. Read here and nowhere
    else; never written."""
    p = Path(root) / OFFICIALS_LINKS
    said = report.setdefault("links_hand", [])
    if not p.is_file():
        said.append(f"{OFFICIALS_LINKS} is not here: no link of the owner's is taken, and the rule's "
                    "stand alone")
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        said.append(f"{OFFICIALS_LINKS} will not read as JSON ({e}): nothing of it is taken, and "
                    "no official is linked by the rule tonight, since an entry of hers might refuse one")
        return {"links": {}, "name_forms": {}, "unreadable": True}
    links, forms = {}, {}
    for key, v in (doc.get("links") or {}).items():
        parts = str(key).split("|")
        if len(parts) != 4 or not all(x.strip() for x in parts) or not isinstance(v, dict):
            said.append(f"{OFFICIALS_LINKS} links {key!r}: not office|area|year|name with an entry; left out")
            continue
        if "person" not in v:
            said.append(f"{OFFICIALS_LINKS} links {key!r} says no person (a number, or null for no one); left out")
            continue
        if v["person"] is not None and not str(v.get("evidence") or "").strip():
            said.append(f"{OFFICIALS_LINKS} links {key!r} names a person with no evidence; left out")
            continue
        links[key] = v
    for person, rows in (doc.get("name_forms") or {}).items():
        good = [r for r in rows or [] if isinstance(r, dict) and str(r.get("name") or "").strip()
                and str(r.get("evidence") or "").strip()]
        if len(good) != len(rows or []):
            said.append(f"{OFFICIALS_LINKS} name_forms {person}: an entry with no name or no evidence; left out")
        if good:
            forms[str(person)] = good
    # Proposals put in her file for her to answer (the draft of 16 November 2026) are not hers
    # until she moves one into links.
    n = len(doc.get("proposed") or {})
    if n:
        said.append(f"{OFFICIALS_LINKS}: {n} proposal{'s' if n != 1 else ''} not yet hers (under proposed): "
                    "moving one into links takes it")
    return {"links": links, "name_forms": forms, "checked": doc.get("_checked")}


def link_officials(model, pool, owner, settings, report, checked=""):
    """Each holder of an office the legislature does not fill linked to a person, where the
    owner's hand file says who or the rule settles it: the tenure's "person", and its "link"
    saying how and on what. Returns the summary the manifest keeps -- what was linked, the
    owner's list (what the rule could not settle, by why, with each person who answers), the
    hand file's entries no holder of the model has yet -- and gives a person each form of their
    name the owner confirmed ("name_forms")."""
    import office_links as OL
    incompatible = set((settings.get("seat_incompatible") or {}).get("offices") or [])
    index = OL.by_surname(pool or [])
    by_person = {e["person"]: e for e in pool or [] if e.get("person")}
    P = {p["person"]: p for p in model.get("person") or []}
    holders = link_holders(model, settings, checked)
    entries = dict((owner or {}).get("links") or {})
    rule_off = pool is None or bool((owner or {}).get("unreadable"))
    made, listed, settled = [], [], []

    def form(person, row, source):
        p = P.get(person)
        if p is None:
            return
        # A form confirmed twice (a link and a name_forms entry) is kept once, under the first.
        forms = p.setdefault("name_forms", [])
        if row["name"] not in {f["name"] for f in forms}:
            forms.append({"name": row["name"], "given": row["given"], "of": row["of"], "source": source})

    for t, h in holders:
        entry = entries.pop(h["key"], None)
        if t.get("person"):
            # Linked already, by the hand file's member page or the register: that stands.
            if entry is not None and str(entry.get("person")) != str(t["person"]):
                report["disagreements"].append({
                    "what": "an official linked two ways", "where": h["key"],
                    "says": f"{t.get('linked_by')}: {t['person']}",
                    "other": f"{OFFICIALS_LINKS}: {entry.get('person')}"})
            made.append({"tenure": t["tenure"], "printed": h["printed"], "person": t["person"],
                         "by": t.get("linked_by") or "the hand file"})
            continue
        if entry is not None:
            if entry.get("person") is None:
                t["link"] = {"by": "owner", "key": h["key"], "why": str(entry.get("why") or "no one of the record")}
                if entry.get("not"):
                    t["link"]["not"] = [str(x) for x in entry["not"]]
                settled.append({"tenure": t["tenure"], "printed": h["printed"], "person": None})
                continue
            if str(entry["person"]) not in P:
                report["links_hand"].append(f"{OFFICIALS_LINKS} links {h['key']!r} names person "
                                            f"{entry['person']}, whom the model does not hold; not taken")
            else:
                t["person"] = str(entry["person"])
                t["link"] = {"by": "owner", "key": h["key"], "evidence": str(entry["evidence"])}
                e = by_person.get(t["person"])
                nf = OL.name_form(h["printed"], e) if e else None
                if nf:
                    form(t["person"], nf, f"{OFFICIALS_LINKS} {h['key']}")
                made.append({"tenure": t["tenure"], "printed": h["printed"], "person": t["person"], "by": "owner"})
                continue
        if rule_off:
            continue
        d = OL.decide(h, index, incompatible)
        if d["verdict"] == "link":
            t["person"] = str(d["person"])
            t["link"] = dict({"by": "rule"}, **d["evidence"])
            made.append({"tenure": t["tenure"], "printed": h["printed"], "person": t["person"], "by": "rule",
                         "on": ", ".join(d["agreements"])})
        elif d["verdict"] == "list":
            listed.append({"key": h["key"], "tenure": t["tenure"], "printed": h["printed"],
                           "kind": d["kind"], "why": d["why"], "answering": d["candidates"]})
    for person, rows in ((owner or {}).get("name_forms") or {}).items():
        e = by_person.get(person)
        if person not in P:
            report["links_hand"].append(f"{OFFICIALS_LINKS} name_forms names person {person}, whom the "
                                        "model does not hold; not taken")
            continue
        for row in rows:
            nf = OL.name_form(row["name"], e) if e else None
            if nf is None:
                report["links_hand"].append(f"{OFFICIALS_LINKS} name_forms {person}: {row['name']!r} is not "
                                            "a short form of a name of theirs; not taken")
                continue
            form(person, nf, f"{OFFICIALS_LINKS} name_forms {person}")
    waiting = sorted(entries)
    by = {}
    for m in made:
        how = m["by"] if m["by"] in ("rule", "owner") else "the officials' hand file or the register"
        by[how] = by.get(how, 0) + 1
    return {"rule": "src/parse/office_links.py",
            "holders": len(holders),
            "linked": dict(sorted(by.items())),
            "made": made,
            "owner_says_no_one": settled,
            "listed": listed,
            "listed_by_kind": {k: sum(1 for x in listed if x["kind"] == k)
                               for k in sorted({x["kind"] for x in listed})},
            "waiting": [f"{OFFICIALS_LINKS} {k}: no holder of the model has this key yet" for k in waiting],
            "rule_off": ("the evidence is not all here" if pool is None else
                         f"{OFFICIALS_LINKS} will not read") if rule_off else "",
            "not_linked": "town offices: the model holds none, and none is linked until a town page "
                          "shows them (the owner's answer of 16 November 2026)"}


def verify_links(model, pool, owner, settings, checked=""):
    """[sentences]: every link the model holds worked out again (office_links.verify) on `pool`,
    and every entry of the owner's that names a holder of the model taken as she wrote it."""
    import office_links as OL
    incompatible = set((settings.get("seat_incompatible") or {}).get("offices") or [])
    index = OL.by_surname(pool or [])
    entries = (owner or {}).get("links") or {}
    out = []
    for t, h in link_holders(model, settings, checked):
        link = t.get("link") or {}
        entry = entries.get(h["key"])
        if link.get("by") == "rule" and pool is None:
            out.append(f"tenure {t['tenure']} is linked by the rule, and its evidence is not all here to check it on")
            continue
        out += OL.verify(t, h, index, incompatible, entries, OFFICIAL)
        if entry is not None and not t.get("linked_by"):
            want = None if entry.get("person") is None else str(entry["person"])
            if t.get("person") != want:
                out.append(f"tenure {t['tenure']}: the owner's entry {h['key']} says {want}, and the model "
                           f"has {t.get('person')}")
        if link.get("by") == "owner" and link.get("not") and t.get("person") in link["not"]:
            out.append(f"tenure {t['tenure']} is linked to {t['person']}, whom the owner says it is not")
    return out


# ---- the model ------------------------------------------------------------------------------

def build(root=".", settings=None, register=None):
    """(model, layouts, report) from the files under `root`. Refused only where a file it needs
    is not there or will not read: what the model cannot place is kept as the file has it where
    it can be and said (report "unplaced" and "notes"), and a rule the model breaks is said
    (report "problems"), so that a model no page reads never stops a night; the model's check
    of the built site fails on a problem, and holds the night for a person. `register` is the
    register of gr- ids to build on where it is not root's REGISTER (gr_candidates passes the
    one it was given)."""
    root = Path(root)
    settings = settings or ST.SETTINGS
    missing = [n for n in NEEDED if not (root / n).is_file()]
    if missing:
        raise Refused("not here: " + ", ".join(missing))
    report = {"unplaced": [], "notes": [],
              "not_rebuilt": [f"{CAREERS}: each record's votes, a count of ballots, "
                              "which are the roll calls' and not this model's"],
              "disagreements": []}
    rp = root / REGISTER
    if register is None and rp.is_file():
        import gr_ids as GR
        register = GR.load_register(rp)
    persons, tenures, by_mid, roster_term = people_and_service(root, settings, report)
    by_page = {p["page"]: p for p in persons if p.get("page")}
    hand_off, hand_ten, layout = hand_offices(root, settings, by_page, register, report)
    county_ten, county_diff, n_county = county_roster(root, hand_ten)
    off_ten, off_extra = officer_tenures(root, settings, by_mid, report)
    contests, cands, elect_ten, elect_layout = members_elect(root, settings, by_mid)
    districts, places = districts_and_places(root, settings)
    gr_people = []
    for t in hand_ten:
        if t["person"] and re.match(EN.GR, t["person"]) and t["person"] not in {g["person"] for g in gr_people}:
            gr_people.append({"person": t["person"], "granite_id": t["person"], "name": t["printed"]})
    past = past_people(root, persons + gr_people, report)
    all_ten = tenures + hand_ten + county_ten + off_ten + elect_ten
    meta = _read(root, META)
    term_names = set(meta.get("terms") or []) | {t["term"] for t in all_ten if t.get("term")} | \
        {c["term"] for c in contests if c.get("term")}
    model = {"person": persons + gr_people + past, "office": EN.offices(settings) + hand_off + off_extra,
             "district": districts, "place": places, "term": terms_of(term_names), "tenure": all_ten,
             "contest": contests, "candidacy": cands}
    # The officials linked to the record, last, since the rule weighs every person the model
    # holds and every district's towns.
    owner = read_owner_links(root, report)
    pool, missing = link_pool(root, model, roster_term, report)
    if missing:
        report["notes"].append("no official is linked by the rule: " + ", ".join(missing)
                               + (" is" if len(missing) == 1 else " are") + " not here, and without "
                               "every file of the pool a difference could go unseen")
    report["links"] = link_officials(model, pool, owner, settings, report,
                                     checked=str(layout.get("_checked") or ""))
    # The term today's roster sits in, which the pool gives a sitting member: kept, so that the
    # check of the links builds the same pool again.
    report["links"]["roster_term"] = roster_term
    unnumbered = [{"what": "a member-elect linked to an id no person holds", "where": x["candidacy"],
                   "says": f"{ELECT}: id {x['member_id']}", "other": f"{PEOPLE} gives that id to nobody"}
                  for x in cands if x.get("member_id") and x.get("person") is None]
    report["disagreements"] = (report["disagreements"] + county_diff + unnumbered
                               + roster_party_disagreements(tenures, persons))
    report["county_seats_compared"] = n_county
    report["roster_term"] = roster_term
    report["problems"] = EN.problems(model, settings, register)
    layouts = {HAND: layout}
    if elect_layout is not None:
        layouts[ELECT] = elect_layout
    return model, layouts, report


# ---- today's files, given back ---------------------------------------------------------------

def _text(root, rel):
    """A file's text as read_text gives it, line ends as "\\n" whatever the machine wrote; None
    where it is not there."""
    p = Path(root) / rel
    return p.read_text(encoding="utf-8") if p.is_file() else None


def _first_difference(a, b):
    """Where two texts part, as a few characters of each."""
    i = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return f"at character {i:,}: the file has {a[max(0, i - 40):i + 60]!r}, the model {b[max(0, i - 40):i + 60]!r}"


def switch_days(doc, today):
    """The days on which officials_on is compared: today, and each day a successor takes office
    and the day before it."""
    days = {today}

    def walk(x):
        if isinstance(x, dict):
            e = x.get("elect")
            if isinstance(e, dict) and EN._day(e.get("takes_office")):
                d = EN._day(e["takes_office"])
                days.update({d, d - datetime.timedelta(days=1)})
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(doc)
    return sorted(days)


def rebuilt(model, layouts, root=".", today=None):
    """[(file, same, words)]: each of today's files the model is a view of, given back from it
    and compared with the file on disk, byte for byte but for the line ends a machine writes.
    A file not on disk is compared only where its absence says something (the members-elect)."""
    import build_members_elect as BME
    import parse_districts as PD
    root = Path(root)
    out = []

    def same(rel, want, got, what):
        if want is None:
            out.append((rel, None, "not on disk"))
        elif want == got:
            out.append((rel, True, what))
        else:
            out.append((rel, False, _first_difference(want, got)))

    t = _text(root, PEOPLE)
    if t is not None:
        doc = json.loads(t)
        view = EN.view_people(model)
        same(PEOPLE, t, json.dumps({"format": doc["format"], "what": doc["what"], "people": view},
                                   ensure_ascii=False, indent=1) + "\n",
             f"{len(view):,} entries, byte for byte under the file's own format and words")
    t = _text(root, CAREERS)
    if t is not None:
        doc = json.loads(t)
        want = {k: {f: v for f, v in r.items() if f != "votes"} for k, r in doc.items()}
        view = EN.view_careers(model)
        same(CAREERS, json.dumps(want, indent=1, sort_keys=True), json.dumps(view, indent=1, sort_keys=True),
             f"{len(view):,} records in its own form, all but each record's votes")
    # THE OFFICIALS' HAND FILE, THROUGH ITS ONE READER ON BOTH SIDES: as read_officials gives it
    # with every successor still named, and as it gives it, the model's copy put in a file of its
    # own, on today and on each side of every successor's day -- every page's view of it.
    if HAND in layouts:
        doc = _hand(root)
        got = EN.hand_file(model, layouts, HAND)
        a, b = json.dumps(doc, ensure_ascii=False), json.dumps(got, ensure_ascii=False)
        if a != b:
            out.append((HAND, False, "every holder and successor: " + _first_difference(a, b)))
        else:
            days = switch_days(doc, today or build_date.today())
            with tempfile.TemporaryDirectory(prefix="gr-model-") as d:
                mine = Path(d) / "hand.json"
                mine.write_text(b, encoding="utf-8")
                bad = [x for x in days
                       if json.dumps(BME.read_officials(root=root, today=x), ensure_ascii=False)
                       != json.dumps(BME.read_officials(mine, today=x), ensure_ascii=False)]
            out.append((HAND, not bad, f"every holder and successor field by field in its order, and as "
                        f"every page reads it on {len(days)} days (today and each side of every "
                        f"successor's day)" if not bad else f"the pages would read it otherwise on {bad}"))
    t = _text(root, ELECT)
    view = EN.view_members_elect(model, layouts)
    if t is None:
        out.append((ELECT, view is None, "not on disk, and the model holds no members-elect"
                    if view is None else "not on disk, and the model holds members-elect"))
    else:
        same(ELECT, t, json.dumps(view, ensure_ascii=False, separators=(",", ":")) if view else "",
             f"{len(view['races']) if view else 0} races, byte for byte")
    era = max(EN.eras())
    t = _text(root, DISTRICTS_JSON)
    view = EN.view_districts(model, era)
    if t is not None:
        same(DISTRICTS_JSON, t, json.dumps(view, indent=2, sort_keys=True),
             f"{sum(len(v) for v in view.values())} towns and wards, byte for byte")
    tracked = json.dumps(PD.combine(root / DISTRICTS, None, say=lambda *a: None), indent=2, sort_keys=True)
    same(f"{DISTRICTS}/*.txt", tracked, json.dumps(view, indent=2, sort_keys=True),
         "parse_districts.combine's table of the tracked lists, byte for byte")
    t = _text(root, OFFICERS)
    if t is not None:
        doc = json.loads(t)
        view = EN.view_officers(model)
        same(OFFICERS, t, json.dumps({"_about": doc["_about"], "officers": view}, separators=(",", ":")),
             f"{len(view)} tenures, byte for byte under the file's own words")
    return out


# ---- the step -------------------------------------------------------------------------------

def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def manifest(model, report, root):
    """What the model is, what it was built from (each file's sha256, so that a reader can tell
    a model built from other files), and what it could not hold or place. No clock's seconds:
    two builds of the same files on one stated day are the same bytes."""
    root = Path(root)
    read = [n for n in NEEDED + (ELECT, REGISTER, COUNTY_ROSTER) + LINK_EVIDENCE + (OFFICIALS_LINKS,)
            if (root / n).is_file()]
    read += sorted(p.relative_to(root).as_posix() for p in (root / DISTRICTS).glob("*.txt"))
    hand = json.dumps(_hand(root), ensure_ascii=False).encode("utf-8")
    return {"format": EN.FORMAT,
            "what": "The model of people, offices, terms, districts and elections "
                    "(src/lib/entities.py), written by src/parse/build_entities.py from the files "
                    "on disk; read by nothing yet. Each kind is a file of its records.",
            "built_on": build_date.today().isoformat(),
            "counts": {k: len(model[k]) for k in EN.KINDS},
            "read": {n: _sha(root / n) for n in read},
            # A file with one reader, by the sha256 of what the reader gave (its JSON, as
            # json.dumps writes it), since it is read through nothing else.
            "read_through": {HAND: hashlib.sha256(hand).hexdigest()},
            "not_rebuilt": report["not_rebuilt"],
            "unplaced": report["unplaced"],
            "notes": report["notes"],
            "problems": report["problems"],
            "disagreements": report["disagreements"],
            # Who the officials are in the record: what the rule and the owner linked, and the
            # owner's list of what the rule could not settle (src/parse/office_links.py).
            "links": report.get("links") or {},
            "links_hand": report.get("links_hand") or []}


def links_summary(report):
    """The lines the step prints of the officials' links: one of what was linked and what is on
    the owner's list, and one for the owner's hand file -- not here, or what of it was not taken."""
    lk = report.get("links") or {}
    if not lk:
        return []
    linked = lk.get("linked") or {}
    kinds = lk.get("listed_by_kind") or {}
    out = [f"officials: {lk.get('holders', 0)} holders; {sum(linked.values())} linked to the record ("
           + (", ".join(f"{n} by {how}" for how, n in linked.items()) or "none")
           + f"); {len(lk.get('listed') or [])} for the owner to settle ("
           + (", ".join(f"{n} {k}" for k, n in kinds.items()) or "none")
           + "): data/entities/manifest.json links, or --links"]
    # The file's absence and her proposals waiting are said; what of her file could not be taken
    # is a warning, for her to put right.
    for line in report.get("links_hand") or []:
        plain = line.endswith("the rule's stand alone") or line.endswith("moving one into links takes it")
        out.append(line if plain else f"WARNING: {line}")
    if lk.get("waiting"):
        out.append(f"{len(lk['waiting'])} entr{'y' if len(lk['waiting']) == 1 else 'ies'} of the owner's "
                   "name a holder the model does not hold yet: kept for when it does")
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--root", default=".", help="the tree whose files are read (default: here)")
    ap.add_argument("--out", default=None, help=f"where the model goes (default: ROOT/{OUT.as_posix()})")
    ap.add_argument("--check", action="store_true",
                    help="build the model and give today's files back from it; write nothing")
    ap.add_argument("--links", action="store_true",
                    help="also print the owner's list: each official the rule could not link, and why")
    a = ap.parse_args()
    t0 = time.perf_counter()
    try:
        model, layouts, report = build(a.root)
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    secs = time.perf_counter() - t0
    counts = ", ".join(f"{len(model[k]):,} {k}" for k in EN.KINDS)
    print(f"entities: {counts}")
    # WHAT IT CANNOT PLACE OR HOLD IS SAID, AND THE STEP GOES ON: nothing reads the model yet,
    # and build_all fails a night on any step that fails, so a rule broken by the files is a
    # warning here, in the manifest and on the night's check of the model, which holds it.
    for p in report["problems"][:20]:
        print(f"  WARNING: the model breaks a rule: {p}")
    if len(report["problems"]) > 20:
        print(f"  WARNING: and {len(report['problems']) - 20} more rule(s), in the manifest")
    for line in report["unplaced"] + report["notes"]:
        print(f"  WARNING: {line}")
    for d in report["disagreements"]:
        print(f"  disagree: {d['where']}: {d['says']}; {d['other']}")
    print(f"  {len(report['disagreements'])} place(s) where today's files disagree "
          f"({report['county_seats_compared']} county seats compared); fixed none")
    for line in links_summary(report):
        print(f"  {line}")
    if a.links:
        for x in (report.get("links") or {}).get("listed") or []:
            print(f"  for the owner: [{x['kind']}] {x['key']}: {x['why']}")
            for c in x["answering"]:
                print(f"      {c['person'] or c['key']} {c['who']} ({c['answers']}): "
                      + "; ".join(f"{k} {v}" for k, v in c["evidence"].items()))
    if a.check:
        bad = 0
        for rel, ok, words in rebuilt(model, layouts, a.root):
            print(f"  {rel}: {'same' if ok else 'not on disk' if ok is None else 'DIFFERENT'} -- {words}")
            bad += ok is False
        print(f"  built in {secs:.1f}s; nothing written")
        return 1 if bad else 0
    out = Path(a.out) if a.out else Path(a.root) / OUT
    sizes = EN.write(model, out, layouts, manifest(model, report, a.root))
    total = sum(sizes.values())
    print(f"  {len(sizes)} files, {total / 1024:,.0f} KB -> {out.as_posix()}/, "
          f"in {time.perf_counter() - t0:.1f}s; nothing reads it yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
