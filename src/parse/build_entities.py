#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.2
"""
The model of people, offices, terms, districts and elections, written to data/entities/ from
the files on disk (src/lib/entities.py says what the model is).

    python3 src/parse/build_entities.py                 # data/entities/, and what it holds
    python3 src/parse/build_entities.py --check         # build it and give today's files back
                                                        #   from it; writes nothing
    python3 src/parse/build_entities.py --root DIR --out DIR
                                                        # read another tree's files, write elsewhere

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

and writes data/entities/ (the build's data folder, never site/: nothing here is published).
preflight holds that each of today's files is a view of the model, byte for byte but for the
line ends a machine writes (rebuilt() below): a model that cannot give a file back has lost
something. What it cannot give back is said: careers.json's ballot counts, which are the roll
calls'.

IDS, DATES AND LINKS by the owner's rules (entities.py): the General Court's number where it
gives one; a gr- id only where the register issued one for that very record (gr_register.py
--offices, a person's run); no id for a member-elect until the General Court numbers them; a
date only where a record states one; nothing linked by a name. A holder in the hand file is
linked to a person only by the hand file's own entry (its "member" page address).

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
    """A file that will not read, or a record the model cannot place: the step stops and says."""


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
            if len(nums) > 1 and len(chambers) > 1:
                raise Refused(f"{CAREERS} {key}, {term}: {len(nums)} numbers in {len(chambers)} "
                              "chambers, and nothing says which number sat in which")
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
            raise Refused(f"{ROSTER} {mid} ({r.get('name')}): no person of people.json holds "
                          "this id, or its chamber is unknown")
        ts = by_key.get((p["person"], office, term)) or []
        if len(ts) > 1:
            raise Refused(f"{ROSTER} {mid}: {len(ts)} numbers of {p['person']} sat in {office} "
                          f"in {term}, which is two people")
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
            raise Refused(f"the hand file's {_dotted(path)} names a successor in a place the model "
                          "does not know as an office's: add it to build_entities.SLOTS")
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
    pages (FIRST_OFFICES; the design's question 3, 19 records on 16 November 2026) whom the hand
    file links to no General Court record -- no "member" page of theirs -- and for whom the
    register has issued no id. Who gr_register.py --offices would give a gr- id, in the hand
    file's order; reads only the hand file and the register, and writes nothing."""
    settings = settings or ST.SETTINGS
    report = {"unplaced": [], "disagreements": [], "not_rebuilt": []}
    doc = _hand(root)
    _o, tenures, _l = hand_offices(root, settings, {}, register, report)
    names = {o["office"]: o["name"] for o in EN.offices(settings)}
    out = []
    for t in tenures:
        if t["office"] not in FIRST_OFFICES or t.get("person") or (t.get("holder") or {}).get("member"):
            continue
        rec = (t.get("holder") or {})
        read = rec.get("read") or doc.get("_checked") or "?"
        out.append({"tenure": t["tenure"], "office": t["office"], "name": t["printed"],
                    "evidence": f"{'Takes' if t.get('from') else 'Holds'} the office of {names[t['office']]} in "
                                f"the officials' hand file at {_dotted(t['slot']['path'])} (read {read}"
                                + (f", from {t['from']}" if t.get("from") else "") + "), which links them "
                                "to no General Court record: no member page and no person number. A "
                                "shared name is not a link."})
    return out


# ---- the chair's offices --------------------------------------------------------------------

def officer_tenures(root, settings, by_mid):
    """site/officers.json's tenures, each of the office its name is in the settings."""
    doc = _read(root, OFFICERS)
    by_name = {(o["name"], o.get("code")): o["office"] for o in EN.offices(settings) if o["scope"] == "chamber"}
    out = []
    for r in doc.get("officers") or []:
        office = by_name.get((r.get("office"), r.get("b")))
        if office is None:
            raise Refused(f"{OFFICERS} names an office the settings do not list: {r.get('office')!r} "
                          f"of {r.get('b')!r}")
        mid = str(r["id"])
        p = by_mid.get(mid)
        t = {"tenure": f"officers:{office}:{r['from']}:{mid}", "office": office,
             "term": proceedings.term_on(r["from"]), "person": p["person"] if p else None,
             "member_id": mid, "printed": r["name"], "title": r["title"], "kind": r["kind"],
             "from": r["from"], "to": r["to"], "keys": {"ballot_sort": r["s"]},
             "files": [OFFICERS], "source": r["source"]}
        out.append(t)
    return out


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
            raise Refused(f"{COUNTY_ROSTER} names an office the model does not know: {r.get('office')!r}")
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


# ---- the model ------------------------------------------------------------------------------

def build(root=".", settings=None):
    """(model, layouts, report) from the files under `root`. Refused where one it needs is not
    there or will not read, or holds a record the model cannot place."""
    root = Path(root)
    settings = settings or ST.SETTINGS
    missing = [n for n in NEEDED if not (root / n).is_file()]
    if missing:
        raise Refused("not here: " + ", ".join(missing))
    report = {"unplaced": [], "not_rebuilt": [f"{CAREERS}: each record's votes, a count of ballots, "
                                              "which are the roll calls' and not this model's"],
              "disagreements": []}
    register = None
    rp = root / REGISTER
    if rp.is_file():
        import gr_ids as GR
        register = GR.load_register(rp)
    persons, tenures, by_mid, roster_term = people_and_service(root, settings, report)
    by_page = {p["page"]: p for p in persons if p.get("page")}
    hand_off, hand_ten, layout = hand_offices(root, settings, by_page, register, report)
    county_ten, county_diff, n_county = county_roster(root, hand_ten)
    off_ten = officer_tenures(root, settings, by_mid)
    contests, cands, elect_ten, elect_layout = members_elect(root, settings, by_mid)
    districts, places = districts_and_places(root, settings)
    gr_people = []
    for t in hand_ten:
        if t["person"] and re.match(EN.GR, t["person"]) and t["person"] not in {g["person"] for g in gr_people}:
            gr_people.append({"person": t["person"], "granite_id": t["person"], "name": t["printed"]})
    all_ten = tenures + hand_ten + county_ten + off_ten + elect_ten
    meta = _read(root, META)
    term_names = set(meta.get("terms") or []) | {t["term"] for t in all_ten if t.get("term")} | \
        {c["term"] for c in contests if c.get("term")}
    model = {"person": persons + gr_people, "office": EN.offices(settings) + hand_off,
             "district": districts, "place": places, "term": terms_of(term_names), "tenure": all_ten,
             "contest": contests, "candidacy": cands}
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
    read = [n for n in NEEDED + (ELECT, REGISTER, COUNTY_ROSTER) if (root / n).is_file()]
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
            "disagreements": report["disagreements"]}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--root", default=".", help="the tree whose files are read (default: here)")
    ap.add_argument("--out", default=None, help=f"where the model goes (default: ROOT/{OUT.as_posix()})")
    ap.add_argument("--check", action="store_true",
                    help="build the model and give today's files back from it; write nothing")
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
    if report["problems"]:
        print(f"REFUSED: the model breaks {len(report['problems'])} rule(s):", file=sys.stderr)
        for p in report["problems"][:20]:
            print(f"  {p}", file=sys.stderr)
        return 1
    for line in report["unplaced"]:
        print(f"  WARNING: {line}")
    for d in report["disagreements"]:
        print(f"  disagree: {d['where']}: {d['says']}; {d['other']}")
    print(f"  {len(report['disagreements'])} place(s) where today's files disagree "
          f"({report['county_seats_compared']} county seats compared); fixed none")
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
