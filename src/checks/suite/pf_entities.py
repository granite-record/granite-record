#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.6
"""
preflight's checks of the model of people, offices, terms, districts and elections
(src/lib/entities.py, written by src/parse/build_entities.py into data/entities/).

A module of its own, because the model is of no one area: it reads the people's, the officials',
the districts', the officers' and the members-elect's files, and is held to give each back
(the refactor's design of 16 November 2026, steps 1 and 2). This module uses pf_core and itself,
and no other area's module.
"""

import ast
import copy
import datetime
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

import _paths

from pf_core import (_parsed, _run, check)

TRACKED = ("generated/careers.json", "corrections/officials.json", "generated/gr_ids.json",
           "collected/county_officials.json", "records/districts/house.txt",
           "records/districts/senate.txt", "records/districts/council.txt",
           "records/districts/congress.txt")


def _tree_digest(root):
    """{relative path: sha256} of every file under `root`."""
    root = Path(root)
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _copy_tracked(root, names=TRACKED):
    """The repository's own copies of `names` laid into `root`."""
    for rel in names:
        dest = Path(root) / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_paths.ROOT / rel, dest)


def _people_file(PE, root, careers, legislators=(), former=(), db_rows=()):
    """site/data/people.json for a tree, as src/lib/people.py makes it: the real writer, over
    the tree's careers and roster and a roster view of `db_rows` [(PersonID, Employeeno)]."""
    root = Path(root)
    (root / "db").mkdir(parents=True, exist_ok=True)
    (root / "db" / "_columns.json").write_text(json.dumps(
        {"Legislators": ["PersonID", "LastName", "FirstName", "Employeeno"]}), encoding="utf-8")
    (root / "db" / "Legislators.psv").write_text("".join(f"{p}|N|F|{e}\n" for p, e in db_rows),
                                                 encoding="utf-8")
    (root / "site" / "data").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(exist_ok=True)
    (root / "site" / "legislators.json").write_text(json.dumps(list(legislators)), encoding="utf-8")
    (root / "site" / "former.json").write_text(json.dumps(list(former)), encoding="utf-8")
    (root / "data" / "member_votes.json").write_text("[]", encoding="utf-8")
    (root / "data" / "sponsors.json").write_text("{}", encoding="utf-8")
    people, _report = PE.build(root / "site", root / "data", root / "db", careers, None)
    PE.write(people, root / "site" / "data")
    return people


def _careers_record(terms, first="", last="", party="", chamber="", person_id=""):
    """A careers.json record as build_careers.py writes one: {term: (chamber, number)}."""
    nums = sorted({n for _ch, n in terms.values()})
    ts = sorted(terms)
    return {"by_term": {t: {"chambers": [terms[t][0]], "employee_nos": [terms[t][1]]} for t in ts},
            "chamber_last": chamber, "district_by_term": {}, "employee_nos": nums, "first": first,
            "first_term": ts[0], "last": last, "last_term": ts[-1], "named": bool(last), "party": party,
            "person_id": person_id,
            "returned_after_a_gap": any(int(b[:4]) - int(a[:4]) > 2 for a, b in zip(ts, ts[1:])),
            "terms": ts, "votes": 7}


def _world(root, PE, careers_extra=None):
    """A made-up tree for the model to be proved on, every file it reads in the shape its writer
    gives it: two sitting representatives in one seat and a sitting member with no vote yet; a
    senator who sat in the House before, and an unnamed number of 1999; the chair's offices; a
    hand file with a successor, a holder linked by a member's page, a holder who only shares a
    member's name, a place the register issued an id for and one it issued to someone else; a
    county seat the Secretary of State's roster names another holder of; and members-elect, new
    and returning. The district lists are the repository's own (their seats must be the House's
    400)."""
    root = Path(root)
    _copy_tracked(root, [n for n in TRACKED if n.startswith("records/")])
    careers = {
        "376001": _careers_record({"2023-2024": ("H", "376001"), "2025-2026": ("H", "376001")},
                                  "Ada", "Newcomb", "R", "H", "11600"),
        "376002": _careers_record({"2025-2026": ("H", "376002")}, "Bo", "Hart", "d", "H"),
        "209001": _careers_record({"2019-2020": ("H", "376003"), "2025-2026": ("S", "209001")},
                                  "Cy", "Lund", "R", "S", "11700"),
        "201723": _careers_record({"1999-2000": ("S", "201723")}),
    }
    careers.update(careers_extra or {})
    (root / "generated").mkdir(parents=True, exist_ok=True)
    (root / "generated" / "careers.json").write_text(json.dumps(careers, indent=1, sort_keys=True),
                                                     encoding="utf-8")
    legislators = [
        {"id": "11600", "name": "Newcomb, Ada", "chamber": "H", "party": "Republican",
         "county": "Carroll", "district": "1", "slug": "ada-newcomb-carr-1"},
        {"id": "11700", "name": "Lund, Cy", "chamber": "S", "party": "Republican",
         "county": "Merrimack", "district": "15", "slug": "cy-lund-sd-15"},
        {"id": "11800", "name": "Moe, Di", "chamber": "H", "party": "Democrat",
         "county": "Carroll", "district": "1", "slug": "di-moe-carr-1"}]
    former = [{"id": "376002", "name": "Hart, Bo", "chamber": "H", "slug": "bo-hart-carr-1", "former": True}]
    people = _people_file(PE, root, careers, legislators, former,
                          [("11600", "376001"), ("11700", "209001"), ("11800", "376004")])
    (root / "site" / "meta.json").write_text(json.dumps({"terms": ["2025-2026", "2023-2024"]}),
                                             encoding="utf-8")
    (root / "site" / "officers.json").write_text(json.dumps({
        "_about": "made up",
        "officers": [
            {"b": "H", "office": "Speaker of the House", "title": "Speaker", "name": "Newcomb",
             "id": "11600", "s": "newcomb, ada", "from": "2024-12-04", "to": "2026-12-02",
             "kind": "elected", "source": "a journal, made up"},
            {"b": "S", "office": "President of the Senate", "title": "President", "name": "Lund",
             "id": "11700", "s": "lund, cy", "from": "2024-12-04", "to": "2026-12-02",
             "kind": "elected", "source": "a journal, made up"}]}, separators=(",", ":")),
        encoding="utf-8")
    (root / "site" / "members_elect.json").write_text(json.dumps({
        "election": "2026-11-03", "takes_office": "2026-12-02", "term": "2027-2028",
        "sources": ["https://results.example/2026", "https://results.example/2026"],
        "races": {
            "S|15": {"seats": 1, "elected": [{"n": "Cy Lund", "p": "R", "k": "sitting", "id": "11700",
                                              "s": "cy-lund-sd-15", "own": True}],
                     "not_final": 0, "held": 0},
            "H|Carroll|1": {"seats": 3, "elected": [
                {"n": "Ada Newcomb", "p": "R", "k": "sitting", "id": "11600", "s": "ada-newcomb-carr-1",
                 "own": True},
                {"n": "Ed New", "p": "D", "k": "new", "u": True},
                {"n": "Flo Back", "p": "R/D", "k": "new", "prior": {"terms": ["1995-1996"], "seat": "Carroll 1"},
                 "e": "flo-back-carr-1"}], "not_final": 0, "held": 0, "recount": True},
            "H|Carroll|2": {"seats": 2, "elected": [], "not_final": 2, "held": 0}}},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (root / "corrections").mkdir(exist_ok=True)
    (root / "corrections" / "officials.json").write_text(json.dumps({
        "_README": ["made up"], "_checked": "2026-11-10",
        "governor": {"office": "Governor", "scope": "statewide", "name": "Gail Gov", "party": "R",
                     "phone": "1", "about": ["leads"]},
        "council": {"office": "Executive Council", "about": ["five"], "districts": {
            "1": {"name": "Hal Held", "party": "R",
                  "elect": {"name": "Ida Next", "party": "D", "source": "results", "takes_office": "2027-01-06"}},
            "2": {"name": "Ada Newcomb", "party": "R"}}},
        "us_house": {"office": "United States House", "districts": {
            "1": {"name": "Cy Lund", "party": "R", "member": "cy-lund-sd-15", "member_evidence": "made up"}}},
        "department_heads": {"office": "Heads", "departments": [
            {"department": "Agriculture", "title": "Commissioner", "name": "Cy Lund",
             "member": "cy-lund-sd-15", "member_evidence": "made up"}]},
        "county": {"office": "County Officers", "counties": {"Carroll": {
            "name": "Carroll", "official_url": "",
            "sheriff": {"name": "Kim Now", "office": "Sheriff", "domicile": "Conway", "note": "filled a vacancy"},
            "commissioners": {"1": {"name": "Lu Same", "office": "County Commissioner", "district": "1",
                                    "party": "R", "party_as_printed": "REP"}}}}}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "generated" / "gr_ids.json").write_text(json.dumps({"format": 1, "ids": [
        {"id": "gr-0001", "named_as": "Gail Gov", "issued": "2026-11-16", "evidence": "made up",
         "employee_number": "", "issued_for": "officials:governor"},
        {"id": "gr-0002", "named_as": "Someone Else", "issued": "2026-11-16", "evidence": "made up",
         "employee_number": "", "issued_for": "officials:council.districts.1"}]}, indent=1),
        encoding="utf-8")
    (root / "collected").mkdir(exist_ok=True)
    (root / "collected" / "county_officials.json").write_text(json.dumps({"_read_on": "2024-12-05", "officers": [
        {"county": "Carroll", "office": "Sheriff", "name": "Max Before", "domicile": "Ossipee",
         "party": "REP", "source_url": "https://roster.example", "read_on": "2024-12-05"},
        {"county": "Carroll", "office": "County Commissioner", "district": "1", "name": "Lu Same",
         "domicile": "", "party": "REP", "source_url": "https://roster.example", "read_on": "2024-12-05"}]}),
        encoding="utf-8")
    return people


def _hand_as_written(BE, EN, BME, model, layouts, path):
    """The officials' hand file at `path`, as written, against the model's copy of it: the same
    JSON field by field in its order, and officials_on of each the same on today and on each
    side of every successor's day. (The step reads the file through read_officials alone; the
    suite may read it as it is.)"""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    got = EN.hand_file(model, layouts, BE.HAND)
    a, b = json.dumps(doc, ensure_ascii=False), json.dumps(got, ensure_ascii=False)
    assert a == b, "the officials' hand file as written is not the model's: " + BE._first_difference(a, b)
    import build_date
    days = BE.switch_days(doc, build_date.today())
    bad = [d for d in days if json.dumps(BME.officials_on(doc, d), ensure_ascii=False)
           != json.dumps(BME.officials_on(got, d), ensure_ascii=False)]
    assert not bad, f"officials_on of the hand file and of the model differ on {bad}"
    return len(days)


@check("build", "each kind of record has a shape, and the model's rules catch every record that breaks one",
       needs=("entities",))
def _entity_shapes(EN):
    """The eight kinds (src/lib/entities.py), held on a model made up here: a model that keeps
    every rule passes, and each of these is seen -- a district of a redrawn kind with no era in
    its id, a tenure of a district the model does not hold, two dated tenures of one seat that
    overlap, more members sitting in a district than it has seats, a member-elect under an id of
    ours (no id until the General Court numbers them), a winner who takes no seat, a party on a
    person (party belongs to a tenure), a day that is no day, a floterial district over the wrong
    districts, a term that does not follow the one before, seats that do not add up to the
    office's, a gr- person the register does not hold, and a person twice. A mid-term change as
    two tenures of one seat, each dated where its record dates it, is a model that holds."""
    settings = {
        "legislature": {"chambers": {"house": {"seats": 3}}}, "term": {"length_years": 2},
        "offices": [
            {"office": "house", "name": "House", "chamber": "house", "code": "H", "scope": "district",
             "district_kind": "house", "filled_by": "election", "constitution": [], "source": "made up"},
            {"office": "speaker", "name": "Speaker", "code": "H", "scope": "chamber", "seats": 1,
             "filled_by": "chamber", "constitution": [], "source": "made up"}],
        "district_kinds": {"house": {"office": "house"}, "county": {"eras": False}},
        "district_eras": {"2022": {"first_term": "2023-2024"}}}
    offices = EN.offices(settings)
    base = {
        "person": [{"person": "11600", "name": "Ada Newcomb", "gc_employee_numbers": ["376001"]},
                   {"person": "376002", "name": "Bo Hart"}],
        "office": offices,
        "district": [
            {"district": "house:2022:a-1", "kind": "house", "era": "2022", "name": "A 1", "county": "A",
             "number": 1, "seats": 2, "floterial": False, "places": ["x|0"], "source": "made up"},
            {"district": "house:2022:a-2", "kind": "house", "era": "2022", "name": "A 2", "county": "A",
             "number": 2, "seats": 1, "floterial": True, "floterial_over": ["house:2022:a-1"],
             "places": ["x|0"], "source": "made up"},
            {"district": "county:a", "kind": "county", "name": "A County", "source": "made up"}],
        "place": [{"place": "x|0", "town": "X", "ward": "0", "county": "A",
                   "in": {"2022": ["house:2022:a-1", "house:2022:a-2"]}, "source": "made up"}],
        "term": [{"term": "2025-2026", "body": "b", "from": "2024-12-04", "to": "2026-12-01", "source": "m"},
                 {"term": "2027-2028", "body": "b", "from": "2026-12-02", "to": "2028-12-05", "source": "m"}],
        "tenure": [
            # A mid-term change: the seat of A 2 held to 25 March, and from then by another.
            {"tenure": "t1", "office": "house", "district": "house:2022:a-2", "term": "2025-2026",
             "person": "376002", "party": "R", "to": "2026-03-25", "files": ["m"]},
            {"tenure": "t2", "office": "house", "district": "house:2022:a-2", "term": "2025-2026",
             "person": "11600", "party": "D", "from": "2026-03-25", "sitting": True, "files": ["m"]},
            {"tenure": "t3", "office": "speaker", "person": "11600", "from": "2024-12-04",
             "to": "2026-12-02", "files": ["m"]},
            {"tenure": "t4", "office": "speaker", "person": "376002", "from": "2026-12-02", "files": ["m"]},
            {"tenure": "t5", "office": "house", "district": "house:2022:a-1", "term": "2027-2028",
             "person": None, "printed": "Ed New", "from": "2026-12-02",
             "candidacy": "2026-11-03.general.house.a-1.ed-new-d", "files": ["m"]}],
        "contest": [{"contest": "2026-11-03.general.house.a-1", "election": "2026-11-03", "stage": "general",
                     "office": "house", "district": "house:2022:a-1", "seats": 2, "term": "2027-2028",
                     "takes_office": "2026-12-02", "source": "m"}],
        "candidacy": [{"candidacy": "2026-11-03.general.house.a-1.ed-new-d", "contest": "2026-11-03.general.house.a-1",
                       "printed": "Ed New", "party": "D", "elected": True, "person": None, "source": "m"}],
    }
    reg = {"format": 1, "ids": []}
    got = EN.problems(base, settings, reg)
    assert got == [], f"a model that keeps every rule broke some: {got[:4]}"

    def fault(what, change, words):
        m = copy.deepcopy(base)
        change(m)
        said = EN.problems(m, settings, reg)
        assert any(words in s for s in said), f"{what} was not seen ({said[:3]})"

    def tenure(m, tid):
        return next(t for t in m["tenure"] if t["tenure"] == tid)

    fault("a district of a redrawn kind with no era in its id",
          lambda m: m["district"][0].update(district="house:a-1"), "carries no era")
    fault("a tenure of a district the model does not hold",
          lambda m: tenure(m, "t1").update(district="house:2022:a-9"), "which is not in the model")
    fault("two dated tenures of one seat that overlap",
          lambda m: tenure(m, "t1").update(to="2026-04-01", **{"from": "2025-01-01"}) or
          tenure(m, "t2").update(to="2026-12-01"), "of one seat overlap")
    fault("more sitting in a district than its seats",
          lambda m: tenure(m, "t1").update(sitting=True), "sit in house:2022:a-2")
    fault("a member-elect under an id of ours",
          lambda m: (tenure(m, "t5").update(person="gr-0001"),
                     m["person"].append({"person": "gr-0001", "granite_id": "gr-0001"})),
          "no id until the legislature numbers them")
    fault("a winner who takes no seat", lambda m: m["tenure"].remove(tenure(m, "t5")), "takes 0 tenures")
    fault("a party on a person", lambda m: m["person"][0].update(party="R"), "a field its kind does not")
    fault("a day that is no day", lambda m: tenure(m, "t3").update(to="2026-02-30"), "which is no day")
    fault("a floterial district over the wrong districts",
          lambda m: m["district"][1].update(floterial_over=[]), "is floterial over")
    fault("a term that does not follow the one before",
          lambda m: m["term"][1].update(**{"from": "2026-12-09"}), "and 2027-2028 begins")
    fault("seats that do not add up to the office's",
          lambda m: m["district"][0].update(seats=5), "hold 6 seats")
    fault("a gr- person the register does not hold",
          lambda m: m["person"].append({"person": "gr-0009", "granite_id": "gr-0009"}),
          "the register does not hold")
    fault("a person twice", lambda m: m["person"].append(dict(m["person"][0])), "in the model twice")
    return "ok", ("a model that keeps every rule, a mid-term change as two dated tenures of one seat "
                  "among them, passes; thirteen faults are each seen, from a district id with no era "
                  "to a member-elect under an id of ours")


@check("files", "New Hampshire's offices and district kinds are data in the state's settings, and each article of the Constitution they name is one on file",
       needs=("entities", "state_settings", "parse_districts"))
def _entity_settings(EN, ST, PD):
    """Step 1 of the model's design: what is the state's, as values in src/lib/state_settings.json
    and in no record's shape. Held against the files on disk: every office the settings list has
    its fields, and each article it names is in collected/constitution.json; the House is the
    legislature's 400 seats, which records/districts/house.txt adds up to and Pt. 2, Art. 9 bounds
    (not less than 375 nor more than 400); it has multi-seat and floterial districts (Art. 11);
    the Senate is 24 single districts (Arts. 25, 26); the Executive Council five, elected every
    two years (Arts. 60, 65); a term is two years and the Governor's too (Art. 42); the Secretary
    of State and the Treasurer are the legislature's to elect (Art. 67); the county officers of
    Art. 71 are elected; and every district era names the term it first fills. And
    src/lib/entities.py, the shapes, names neither the state, its legislature, a county nor a
    host anywhere but in its prose."""
    con = json.loads((_paths.ROOT / "collected" / "constitution.json").read_text(encoding="utf-8"))
    on_file = {}
    for part in con["parts"]:
        for div in part.get("divisions") or [part]:
            for a in div.get("articles") or []:
                on_file[f"Pt. {part['part']}, Art. {a['key']}"] = " ".join(a.get("text") or [])
    s = ST.SETTINGS
    offices = {o["office"]: o for o in EN.offices(s)}
    named = [c for o in s["offices"] for c in o.get("constitution") or []] + \
            [c for k in s["district_kinds"].values() for c in k.get("constitution") or []]
    assert named and not [c for c in named if c not in on_file], (
        "the settings name articles the Constitution on file does not hold: "
        + ", ".join(sorted({c for c in named if c not in on_file})))
    for o in s["offices"]:
        missing = [k for k in ("office", "name", "scope", "filled_by", "constitution", "source") if k not in o]
        assert not missing, f"office {o.get('office')} has no {missing}"
        assert o["filled_by"] in ("election", "legislature", "chamber", "appointment", None), o
    house = PD.parse_house(_paths.ROOT / "records" / "districts" / "house.txt")
    seats = sum(v["seats"] for v in house.values())
    assert offices["house"]["seats"] == s["legislature"]["chambers"]["house"]["seats"] == seats == 400, (
        f"the House: settings {offices['house']['seats']}, house.txt {seats}")
    assert "not less than three hundred seventy-five or more than four hundred" in on_file["Pt. 2, Art. 9"]
    assert any(v["seats"] > 1 for v in house.values()) and any(v["floterial"] for v in house.values()) \
        and s["district_kinds"]["house"].get("multi_seat") and s["district_kinds"]["house"].get("overlay") == "floterial" \
        and "floterial" in on_file["Pt. 2, Art. 11"], "the House's multi-seat and floterial districts"
    senate = PD.parse(_paths.ROOT / "records" / "districts" / "senate.txt")
    assert offices["senate"]["seats"] == len(senate) == 24 and "twenty four" in on_file["Pt. 2, Art. 25"]
    council = PD.parse(_paths.ROOT / "records" / "districts" / "council.txt")
    ec = offices["executive-council"]
    assert ec["seats"] == len(council) == 5 and ec["term_years"] == 2 and ec["filled_by"] == "election" \
        and "five councilors" in on_file["Pt. 2, Art. 60"] and "biennially" in on_file["Pt. 2, Art. 60"], ec
    assert s["term"]["length_years"] == 2 == offices["governor"]["term_years"] \
        and "biennially" in on_file["Pt. 2, Art. 42"]
    for o in ("secretary-of-state", "treasurer"):
        assert offices[o]["filled_by"] == "legislature" and "Pt. 2, Art. 67" in offices[o]["constitution"], o
    assert "joint ballot" in on_file["Pt. 2, Art. 67"]
    for o in ("sheriff", "county-attorney", "county-treasurer", "register-of-deeds", "register-of-probate"):
        assert offices[o]["filled_by"] == "election" and "Pt. 2, Art. 71" in offices[o]["constitution"], o
    for era, v in s["district_eras"].items():
        assert re.match(r"^\d{4}$", era) and re.match(r"^\d{4}-\d{4}$", v["first_term"]) and v.get("source"), era
    for kind, k in s["district_kinds"].items():
        assert not k.get("office") or k["office"] in offices, f"district kind {kind} names no office"
    # The shapes name nothing of the state but in prose.
    tree = _parsed(_paths.locate("entities.py"))
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    words = [s["state"]["name"], s["legislature"]["name"], s["source_hosts"]["legislature"]] + list(ST.COUNTIES)
    said = sorted({w for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                   and id(n) not in docs for w in words if w.lower() in n.value.lower()})
    assert not said, f"src/lib/entities.py names {said} outside its prose: the state's are its settings'"
    return "ok", (f"{len(s['offices'])} offices and {len(s['district_kinds'])} district kinds in the settings, "
                  f"{len(set(named))} articles of the Constitution named and each on file; the House's "
                  f"{seats} seats, the Senate's {len(senate)}, the Council's {len(council)} agree with the "
                  "district files; the shapes name nothing of the state")


@check("build", "the model built from the tracked files gives back careers.json but its ballot counts, the hand file of officials as written and as every page reads it on each successor's day, and the district table, byte for byte",
       needs=("build_entities", "entities", "people", "build_members_elect", "parse_districts"))
def _entities_give_back_the_tracked_files(BE, EN, PE, BME, PD):
    """Phase A of the model (the design of 16 November 2026): each of today's files is a view of
    it. These are the tracked ones, so this holds in a bare clone: generated/careers.json (all
    but each record's votes, a count of ballots, which belong to the roll calls),
    corrections/officials.json as written, field by field in its order, and officials_on of it
    on today and on each side of every successor's day, and the district table
    parse_districts.combine makes of records/districts/. The built files the model also reads
    are stood in for here -- site/data/people.json made by src/lib/people.py itself from the
    tracked careers.json, an empty roster -- and given back too. A careers record, a hand-file
    record and a district each changed in the model are each seen."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-entities-"))
    try:
        _copy_tracked(tmp)
        careers = json.loads((tmp / "generated" / "careers.json").read_text(encoding="utf-8"))
        _people_file(PE, tmp, careers)
        (tmp / "site" / "meta.json").write_text(json.dumps({"terms": ["2025-2026"]}), encoding="utf-8")
        (tmp / "site" / "officers.json").write_text('{"_about":"x","officers":[]}', encoding="utf-8")
        model, layouts, report = BE.build(tmp)
        assert not report["problems"], f"the model breaks its rules: {report['problems'][:4]}"
        assert not report["unplaced"], f"records the model does not place: {report['unplaced'][:3]}"
        got = {rel: (ok, words) for rel, ok, words in BE.rebuilt(model, layouts, tmp)}
        bad = {rel: words for rel, (ok, words) in got.items() if ok is False}
        assert not bad, "a tracked file is not given back: " + "; ".join(f"{r}: {w[:300]}" for r, w in bad.items())
        for rel in ("generated/careers.json", BE.HAND, "records/districts/*.txt",
                    "site/data/people.json", "site/officers.json"):
            assert got.get(rel, (None,))[0] is True, f"{rel} was not compared: {got.get(rel)}"
        assert len(EN.view_careers(model)) == len(careers), "careers.json's records are not all given back"
        _hand_as_written(BE, EN, BME, model, layouts, tmp / "corrections" / "officials.json")
        # A model that has lost something is seen.
        for what, change, rel in (
                ("a careers term", lambda m: m["tenure"].pop(0), "generated/careers.json"),
                ("a holder's phone", lambda m: next(t for t in m["tenure"] if t["tenure"] == "officials:governor")
                 ["holder"].update(phone="0"), BE.HAND),
                ("a district's seats", lambda m: next(d for d in m["district"] if d["kind"] == "house")
                 .update(seats=99), "records/districts/*.txt")):
            m = copy.deepcopy(model)
            change(m)
            seen = {r: ok for r, ok, _w in BE.rebuilt(m, layouts, tmp)}
            assert seen[rel] is False, f"a model that lost {what} still gave {rel} back"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", (f"careers.json's {len(careers):,} records (all but votes), the officials' hand file as written "
                  "and as officials_on gives it on each side of every successor's day, the district table and "
                  "the stand-in people.json given back byte for byte; a lost term, phone or seat count each seen")


@check("build", "build_entities.py writes the model of a made-up tree into data/entities/ and nothing else, every file it read is a view of it, and no one is linked by a name",
       needs=("build_entities", "entities", "people", "gr_ids", "build_members_elect"))
def _entities_round_trip(BE, EN, PE, GR, BME):
    """The night's step on a tree made up here (_world), run as build_all runs it: it writes
    data/entities/ and changes no other file of the tree; and site/data/people.json,
    generated/careers.json, corrections/officials.json (as written and on each side of its
    successor's day), site/members_elect.json, site/districts.json's table and site/officers.json
    each come back from what it wrote, byte for byte. And the owner's rules, each on a record of
    the tree: a new member-elect has no person until the General Court numbers them, and a
    returning one has theirs; a holder the hand file links by a member's page has that member's
    person, and a holder who only shares a member's name has none; the gr- id the register
    issued for a place is that place's holder's under the name it was issued to, and an id
    issued for a place under another name is no one's; a county seat the roster names another
    holder of is two tenures of that seat; a successor's tenure begins on the day the hand file
    names and its holder's names no end; a sitting member with no vote yet sits by the roster
    alone. A model that has lost a sitting member, a member-elect's mark, a successor's day or an
    officer's last day is seen to be."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-entities-"))
    try:
        _world(tmp, PE)
        before = _tree_digest(tmp)
        r = _run([sys.executable, str(_paths.script("build_entities.py")), "--out", "data/entities"],
                 cwd=tmp, capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, f"build_entities.py exited {r.returncode}: {(r.stderr or r.stdout)[-600:]}"
        after = _tree_digest(tmp)
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        assert changed and all(k.startswith("data/entities/") for k in changed), (
            f"build_entities.py wrote outside data/entities/: {[k for k in changed if not k.startswith('data/entities/')]}")
        model, layouts, manifest = EN.load(tmp / "data" / "entities")
        assert EN.problems(model, None, GR.load_register(tmp / "generated" / "gr_ids.json")) == []
        got = BE.rebuilt(model, layouts, tmp)
        bad = [(rel, w) for rel, ok, w in got if ok is not True]
        assert not bad, "a file of the tree is not given back: " + "; ".join(f"{r}: {w[:300]}" for r, w in bad)
        _hand_as_written(BE, EN, BME, model, layouts, tmp / "corrections" / "officials.json")
        T = {t["tenure"]: t for t in model["tenure"]}
        X = {x["candidacy"]: x for x in model["candidacy"]}
        P = {p["person"]: p for p in model["person"]}
        new = X["2026-11-03.general.house.carroll-1.ed-new-d"]
        back = X["2026-11-03.general.house.carroll-1.ada-newcomb-r"]
        assert new["person"] is None and T[f"elect:{new['candidacy']}"]["person"] is None, (
            "a new member-elect was given a person before the General Court numbered them")
        assert back["person"] == "11600" == T[f"elect:{back['candidacy']}"]["person"], back
        dept = T["officials:department_heads.departments.0"]
        assert dept["person"] == "11700" and "member" in dept["linked_by"], dept
        assert T["officials:us_house.districts.1"]["person"] == "11700", T["officials:us_house.districts.1"]
        assert T["officials:council.districts.2"]["person"] is None, (
            "a holder who only shares a member's name was linked to them")
        gov = T["officials:governor"]
        assert gov["person"] == "gr-0001" and P["gr-0001"]["granite_id"] == "gr-0001", gov
        assert T["officials:council.districts.1"]["person"] is None, (
            "an id issued for a place under another name was put on its holder")
        sheriff = [t for t in model["tenure"] if t["office"] == "sheriff"]
        assert sorted(t["printed"] for t in sheriff) == ["Kim Now", "Max Before"] \
            and len({(t["district"], t.get("seat")) for t in sheriff}) == 1, sheriff
        assert any(d["where"] == "Carroll Sheriff" for d in manifest["disagreements"]), manifest["disagreements"]
        succ = T["officials:council.districts.1.elect"]
        assert succ["from"] == "2027-01-06" and "to" not in T["officials:council.districts.1"], succ
        moe = T["house:2025-2026:11800"]
        assert moe.get("sitting") and moe["files"] == ["site/legislators.json"], moe
        # A model that has lost something is seen, file by file.
        for what, change, rel in (
                ("a sitting member", lambda m: next(t for t in m["tenure"] if t.get("sitting")).pop("sitting"),
                 "site/data/people.json"),
                ("a member-elect's mark", lambda m: next(x for x in m["candidacy"] if x.get("own")).pop("own"),
                 "site/members_elect.json"),
                ("a successor's day", lambda m: next(t for t in m["tenure"] if t["tenure"].endswith(".elect"))
                 .update(**{"from": "2027-01-07"}), BE.HAND),
                ("an officer's last day", lambda m: next(t for t in m["tenure"] if "site/officers.json" in t["files"])
                 .update(to="2026-12-03"), "site/officers.json")):
            m = copy.deepcopy(model)
            change(m)
            seen = {r: ok for r, ok, _w in BE.rebuilt(m, layouts, tmp)}
            assert seen[rel] is False, f"a model that lost {what} still gave {rel} back"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", (f"data/entities/ written and no other file of the tree changed; {len(got)} files given back "
                  "byte for byte; a new member-elect has no person, a page link and a register id issued for "
                  "the place link and a shared name does not; a county seat kept twice is two tenures; four "
                  "losses each seen")


@check("build", "build_entities.py says what the model cannot place or hold and goes on, and every file still comes back",
       needs=("build_entities", "entities", "people"))
def _entities_say_and_go_on(BE, EN, PE):
    """A model no page reads must not stop a night: build_all records a failed step, optional or
    not, and check_site fails the night on it. On a made-up tree (_world) holding each thing the
    model cannot place or hold -- a member who moved chamber within a term under two numbers
    careers.json joins (two numbers in two chambers, one term), a sitting member's id no person
    holds, a chair's office the settings do not list, a successor in a place of the hand file no
    rule knows, a county office the model does not know, and a House of 401 seats, which breaks
    a rule -- the script exits 0, writes data/entities/ and nothing else, and its manifest says
    each; every file it reads still comes back byte for byte; and the rule broken is in the
    manifest and in the model's own problems, on which the night's check of the model fails."""
    moved = {"by_term": {"2025-2026": {"chambers": ["H", "S"], "employee_nos": ["209009", "376009"]}},
             "chamber_last": "S", "district_by_term": {}, "employee_nos": ["209009", "376009"],
             "first": "Gus", "first_term": "2025-2026", "last": "Mover", "last_term": "2025-2026",
             "named": True, "party": "R", "person_id": "", "returned_after_a_gap": False,
             "terms": ["2025-2026"], "votes": 3}
    tmp = Path(tempfile.mkdtemp(prefix="gr-entities-"))
    try:
        _world(tmp, PE, {"376009": moved})
        roster = json.loads((tmp / "site" / "legislators.json").read_text(encoding="utf-8"))
        roster.append({"id": "99999", "name": "Ghost, Al", "chamber": "H", "party": "Republican",
                       "county": "Carroll", "district": "1", "slug": "al-ghost-carr-1"})
        (tmp / "site" / "legislators.json").write_text(json.dumps(roster), encoding="utf-8")
        off = json.loads((tmp / "site" / "officers.json").read_text(encoding="utf-8"))
        off["officers"].append({"b": "H", "office": "Majority Leader of the House", "title": "Majority Leader",
                                "name": "Hart", "id": "376002", "s": "hart, bo", "from": "2025-01-01",
                                "to": "2026-12-02", "kind": "term", "source": "made up"})
        (tmp / "site" / "officers.json").write_text(json.dumps(off, separators=(",", ":")), encoding="utf-8")
        hand = json.loads((tmp / "corrections" / "officials.json").read_text(encoding="utf-8"))
        hand["lieutenant"] = {"office": "Made up", "name": "Lu Tenant",
                              "elect": {"name": "Next One", "takes_office": "2027-01-06"}}
        (tmp / "corrections" / "officials.json").write_text(json.dumps(hand, indent=2), encoding="utf-8")
        cr = json.loads((tmp / "collected" / "county_officials.json").read_text(encoding="utf-8"))
        cr["officers"].append({"county": "Carroll", "office": "County Surveyor", "name": "Sy Vey"})
        (tmp / "collected" / "county_officials.json").write_text(json.dumps(cr), encoding="utf-8")
        house = tmp / "records" / "districts" / "house.txt"
        text = house.read_text(encoding="utf-8")
        assert "Belknap County District 1\n" in text, "house.txt's first district is not as this check knows it"
        house.write_text(text.replace("Belknap County District 1\n", "Belknap County District 1 (2 seats)\n", 1),
                         encoding="utf-8")
        before = _tree_digest(tmp)
        r = _run([sys.executable, str(_paths.script("build_entities.py")), "--out", "data/entities"],
                 cwd=tmp, capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, f"build_entities.py stopped ({r.returncode}): {(r.stderr or r.stdout)[-600:]}"
        after = _tree_digest(tmp)
        assert all(k.startswith("data/entities/") for k in set(before) ^ set(after) | {
            k for k in before if before[k] != after.get(k)}), "build_entities.py wrote outside data/entities/"
        model, layouts, manifest = EN.load(tmp / "data" / "entities")
        said = json.dumps(manifest)
        for what, words in (("the member who moved chamber", "nothing says which sat where"),
                            ("the chair's office the settings do not list", "Majority Leader of the House"),
                            ("the successor in an unknown place", "lieutenant names a successor"),
                            ("the id no person holds", "Ghost, Al"),
                            ("the county office the model does not know", "County Surveyor"),
                            ("the House of 401", "hold 401 seats")):
            assert words in said, f"the manifest does not say {what}"
        assert any("401" in p for p in EN.problems(model)), "the House of 401 broke no rule of the model's"
        mover = sorted((t["office"], t["gc_employee_number"]) for t in model["tenure"]
                       if t.get("keys", {}).get("careers") == "376009")
        assert mover == [("house", "209009"), ("house", "376009"), ("senate", "209009"), ("senate", "376009")], mover
        bad = [(rel, w) for rel, ok, w in BE.rebuilt(model, layouts, tmp) if ok is not True]
        assert not bad, "a file is not given back: " + "; ".join(f"{r_}: {w[:300]}" for r_, w in bad)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("a moved member's two numbers, a sitting id no one holds, an unlisted office, a successor "
                  "in an unknown place, an unknown county office and a House of 401 seats are each said, "
                  "the step exits 0 and writes only data/entities/, and every file still comes back; the "
                  "broken rule is the model's problem, for the night's check")


@check("pipeline", "build_all builds the model last, after every step whose files it reads, into data/entities/ alone, and nothing reads it yet",
       needs=("build_all",))
def _entities_step_in_the_plan(build_all):
    """The step (the design's step 2): after the district table, the site data (the roster and
    the officers), the members-elect and the bulk downloads (site/data/people.json), which are
    the steps that write what it reads; given data/entities as where it writes, and declaring its
    manifest; optional, because no page waits on a model nothing reads. And nothing reads it yet
    (phase A): no step of the plan names data/entities but it, and no code file but it, the shapes'
    module, src/ops/gr_register.py (which asks it only for the hand file's holders) and the
    checks imports either or names the folder."""
    class A:
        key = None
        session = "2026"
        base = "https://graniterecord.org"
        archive = "nh-archive"
    steps = build_all.plan(A())
    names = [s.args[0] for s in steps]
    assert names.count("build_entities.py") == 1, "build_all runs build_entities.py other than once"
    i = names.index("build_entities.py")
    s = steps[i]
    for before in ("parse_districts.py", "build_site_v2.py", "build_members_elect.py", "build_exports.py"):
        assert before in names and names.index(before) < i, f"build_entities.py runs before {before}"
    assert s.args[1:] == ["--out", "data/entities"] and [p.as_posix() for p in s.produces] == [
        "data/entities/manifest.json"] and s.optional and not s.network, (s.args, s.produces, s.optional)
    others = [x.name for x in steps if x is not s and any("data/entities" in str(a) for a in
                                                          list(x.args) + list(x.needs) + list(x.produces))]
    assert not others, f"steps besides the model's name data/entities: {others}"
    allowed = {"build_entities.py", "entities.py", "gr_register.py", "build_all.py"}
    readers = []
    for f in _paths.code_files("*.py"):
        if f.name in allowed or "suite" in f.parent.name:
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^\s*(?:import|from)\s+(?:entities|build_entities)\b", t, re.M) or "data/entities" in t:
            readers.append(f.name)
    assert not readers, f"these read the model, which nothing reads yet: {readers}"
    return "ok", (f"step {i + 1} of {len(steps)}, after the district table, the site data, the members-elect "
                  "and the bulk downloads; --out data/entities, optional; no other step or code file reads it")


@check("naming", "gr_register.py --offices lists the first offices' holders the hand file links to no General Court record, issues nothing unless told, and never one id for a name two places share",
       needs=("gr_register", "gr_ids", "build_entities"))
def _gr_offices_dry_run(REG, GR, BE):
    """The design's question 3 (yes, 16 November 2026): a gr- id, by a person's run, for each
    holder and successor of the first offices with pages -- the Governor, the Council, Congress,
    the Secretary of State, the Treasurer, the Attorney General -- whom the hand file links to no
    General Court record. On the tracked hand file and register: the dry run lists exactly those
    (worked out here from the file, independently: each such record with no member page) and
    leaves the register as it was, in memory and on disk; a name two of the places share gets no
    id, since one person is one id and a name cannot say whether it is one person; with --apply,
    on a copy, every id issued names its place, and the register stays well formed. Run on the
    made-up register of _world, an id issued for a place is found by the place and the name."""
    reg_path = _paths.ROOT / "generated" / "gr_ids.json"
    disk = reg_path.read_bytes()
    reg = GR.load_register(reg_path) or {"format": 1, "ids": []}
    kept = json.dumps(reg, sort_keys=True)
    doc = json.loads((_paths.ROOT / "corrections" / "officials.json").read_text(encoding="utf-8"))
    want = []
    for key in ("governor", "secretary_of_state", "treasurer", "attorney_general"):
        want.append((f"officials:{key}", doc[key]))
    for key, sub in (("council", "districts"), ("us_house", "districts"), ("us_senate", "seats")):
        items = doc[key][sub].items() if isinstance(doc[key][sub], dict) else enumerate(doc[key][sub])
        for k, rec in items:
            want.append((f"officials:{key}.{sub}.{k}", rec))
            if isinstance(rec.get("elect"), dict):
                want.append((f"officials:{key}.{sub}.{k}.elect", rec["elect"]))
    issued_for = {p for e in reg.get("ids") or [] for p in
                  (e["issued_for"] if isinstance(e.get("issued_for"), list) else [e.get("issued_for")])}
    want = sorted(t for t, rec in want if not rec.get("member") and t not in issued_for)
    got = REG.offices(reg, "2026-11-16", apply=False, root=_paths.ROOT)
    assert sorted(c["tenure"] for _n, c in got) == want, (
        f"the dry run lists {sorted(c['tenure'] for _n, c in got)}, and the hand file's unlinked first offices "
        f"are {want}")
    assert json.dumps(reg, sort_keys=True) == kept and reg_path.read_bytes() == disk, "the dry run wrote"
    names = [" ".join(c["name"].split()).lower() for _n, c in got]
    shared = {n for n in names if names.count(n) > 1}
    assert all((new is None) == (" ".join(c["name"].split()).lower() in shared) for new, c in got), (
        "an id was offered for a name two places share, or none for a name one place has")
    work = copy.deepcopy(reg)
    done = REG.offices(work, "2026-11-16", apply=True, root=_paths.ROOT)
    new_ids = [e for e in work["ids"] if e not in reg["ids"]]
    assert len(new_ids) == sum(1 for n, _c in done if n) and GR.check_register(work) == [] and all(
        e["issued_for"].startswith("officials:") for e in new_ids), "issued ids without their places"
    assert reg_path.read_bytes() == disk, "offices() with apply wrote the register itself; only main() writes"
    tmp = Path(tempfile.mkdtemp(prefix="gr-entities-"))
    try:
        import people as PE
        _world(tmp, PE)
        cands = BE.gr_candidates(tmp, register=GR.load_register(tmp / "generated" / "gr_ids.json"))
        # The Governor holds the id issued for that place under her name; the holder of
        # district 1 is not the one gr-0002 was issued to; district 2's shares a member's name,
        # which links nobody; the member of the US House is linked by the hand file's member
        # page, and needs none.
        assert [c["tenure"] for c in cands] == ["officials:council.districts.1",
                                                "officials:council.districts.1.elect",
                                                "officials:council.districts.2"], cands
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", (f"{len(got)} holders of the first offices listed, as the hand file's own unlinked records; "
                  f"{len(shared)} name(s) two places share held back for a person; nothing written by the "
                  f"dry run; with --apply every id names its place")


@check("data", "the model the build wrote (data/entities/) gives back today's people, careers, officials, members-elect, district table and officers, byte for byte",
       needs=("build_entities", "entities", "gr_ids", "build_members_elect"))
def _entities_give_back_today(BE, EN, GR, BME):
    """The model's proof on the night's files (the design's step 2): data/entities/, as
    build_entities.py wrote it in the build, is read back, still keeps every rule, was built from
    the files on disk now (the sha256 of each it read, in its manifest), and gives back
    site/data/people.json, generated/careers.json but its ballot counts,
    corrections/officials.json as written and as every page reads it on today and each side of
    every successor's day, site/members_elect.json (or none, outside the weeks it is shown),
    site/districts.json and site/officers.json, each byte for byte but for the line ends a
    machine writes. A build that ran the step and has no model fails here; a tree no build has
    run in is skipped."""
    folder = Path("data") / "entities"
    if not (folder / EN.MANIFEST).is_file():
        record = Path("site") / "build.json"
        if not record.is_file():
            return "skip", "no build has run here: no data/entities/ and no site/build.json"
        steps = json.loads(record.read_text(encoding="utf-8")).get("steps") or []
        mine = [x for x in steps if "as one model" in str(x.get("step"))]
        assert not mine, f"the build ran the model's step and there is no data/entities/: {mine[0]}"
        return "skip", "the last build here did not run the model's step (site/build.json names none)"
    model, layouts, manifest = EN.load(folder)
    moved = [n for n, sha in (manifest.get("read") or {}).items()
             if not Path(n).is_file() or hashlib.sha256(Path(n).read_bytes()).hexdigest() != sha]
    hand = json.dumps(BME.read_officials(today=datetime.date.min), ensure_ascii=False).encode("utf-8")
    if (manifest.get("read_through") or {}).get(BE.HAND) != hashlib.sha256(hand).hexdigest():
        moved.append(BE.HAND)
    assert not moved, ("data/entities/ was built from other files than these, which have changed since: "
                       + ", ".join(moved) + ". Run python3 src/parse/build_entities.py")
    register = GR.load_register(Path("generated") / "gr_ids.json")
    said = EN.problems(model, None, register)
    assert not said, f"the model breaks {len(said)} rule(s): " + "; ".join(said[:4])
    got = BE.rebuilt(model, layouts, ".")
    bad = [(rel, w) for rel, ok, w in got if ok is False]
    assert not bad, "today's files are not views of the model: " + "; ".join(f"{r}: {w[:400]}" for r, w in bad)
    _hand_as_written(BE, EN, BME, model, layouts, Path("corrections") / "officials.json")
    shown = [rel for rel, ok, _w in got if ok]
    return "ok", (f"{', '.join(shown)} given back from the model of {manifest.get('built_on')} "
                  f"({sum(manifest.get('counts', {}).values()):,} records); "
                  f"{len(manifest.get('disagreements') or [])} place(s) where the files disagree, as the manifest lists")


# ---- the officials linked to the record (src/parse/office_links.py) ----------------------------

def _pool_person(person, names, kind="record", mid="", party="", county=(), homes=(), terms=(), sfx=(),
                 dtowns=()):
    """One person of a pool as build_entities.link_pool gives them."""
    return {"key": person, "person": None if kind == "elect" else person, "kind": kind, "label": names[0],
            "names": list(names), "middles": set(mid), "sfx": set(sfx),
            "parties": set(party) if isinstance(party, (list, tuple)) else ({party} if party else set()),
            "counties": set(county), "homes": set(homes), "district_towns": set(dtowns), "terms": set(terms)}


def _link_fixture_pool():
    """The people of the rule's fixtures, each as the files on disk gave them on 16 November 2026
    (build_entities.link_pool over D:/nh): names, middle initials, parties, counties, home towns
    and terms served. The two Patrick Longs of Manchester; Rep. Benjamin T. Bartlett of
    Nottingham; Thomas Stewart of 1993-1994 and the member-elect Tom Stewart (the owner, 13
    November: two people); Sen. Richard Green and the member-elect Rich Green (the owner, 7
    November: two people); Joseph D. Kenney of Wakefield and the two other Kenneys; Roger R.
    Berube, who voted in 2017-2018; Omer Ahern; Toni Pappas of 1989-1990 and Christopher Pappas;
    David M. Scanlan."""
    P = _pool_person
    return [
        P("540", ["Pat Long", "Long, Pat", "Patrick T. Long", "Long, Patrick"], mid="t", party="D",
          county=["Hillsborough"], homes=["Manchester"], terms=["2007-2008", "2025-2026", "2027-2028"]),
        P("11177", ["Patrick Long", "Long, Patrick", "Patrick N Long"], mid="n", party="D",
          county=["Hillsborough"], homes=["Manchester"], terms=["2025-2026", "2027-2028"]),
        P("10683", ["Benjamin Bartlett", "Bartlett, Benjamin", "Benjamin T Bartlett"], mid="t", party="R",
          county=["Rockingham"], homes=["Nottingham"], terms=["2023-2024"]),
        P("375950", ["Thomas Stewart", "Stewart, Thomas"], kind="past", county=["Hillsborough"],
          terms=["1993-1994"]),
        P("elect:2026-11-03.general.house.hillsborough-41.tom-stewart-d", ["Tom Stewart"], kind="elect",
          party="D", county=["Hillsborough"], terms=["2027-2028"]),
        P("209050", ["Richard Green", "Green, Richard"], party="R", terms=["2003-2004", "2005-2006"]),
        P("elect:2026-11-03.general.house.hillsborough-9.rich-green-d", ["Rich Green"], kind="elect",
          party="D", county=["Hillsborough"], terms=["2027-2028"]),
        P("376013", ["Joseph Kenney", "Kenney, Joseph", "Joseph D. Kenney"], mid="d", party=["D", "R"],
          county=["Carroll"], homes=["Wakefield"],
          terms=["1995-1996", "1997-1998", "1999-2000", "2001-2002", "2003-2004", "2005-2006", "2007-2008"]),
        P("9231", ["Cam Kenney", "Kenney, Cam", "Cam E. Kenney"], mid="e", party="D", county=["Strafford"],
          homes=["Durham"], terms=["2019-2020", "2021-2022", "2023-2024"]),
        P("376484", ["Bettie Kenney", "Kenney, Bettie"], party="R", county=["Carroll"], terms=["2003-2004"]),
        P("436", ["Roger Berube", "Berube, Roger", "Roger R. Berube"], mid="r", party=["D", "R"],
          county=["Strafford"], homes=["Somersworth"], terms=["1995-1996", "2015-2016", "2017-2018"]),
        P("376424", ["Omer Ahern", "Ahern, Omer"], party="R", county=["Grafton"], terms=["2003-2004"]),
        P("331371", ["Toni Pappas", "Pappas, Toni"], kind="past", party="R", county=["Hillsborough"],
          homes=["Manchester"], terms=["1989-1990"]),
        P("376509", ["Christopher Pappas", "Pappas, Christopher"], party="D", county=["Hillsborough"],
          terms=["2003-2004", "2005-2006"]),
        P("371377", ["David Scanlan", "Scanlan, David", "David M. Scanlan"], mid="m", party="R",
          county=["Grafton"], terms=["1999-2000", "2005-2006"]),
    ]


def _link_holder(OL, office, printed, party="", town="", area=None, terms=("2025-2026",), where="statewide"):
    """A holder as build_entities.link_holders gives one."""
    area = area or {"kind": "statewide"}
    return {"tenure": f"t:{printed}", "office": office, "printed": printed, "party": party, "town": town,
            "area": area, "terms": list(terms), "day": "", "key": OL.hand_key(office, where, terms[0][:4], printed)}


def _county(name):
    return {"kind": "county", "county": name}


@check("build", "an official is linked to a person of the record only by the rule of 16 November 2026: the Longs, the Bartletts, Stewart and Green never join, Kenney links, and every way a link can stop holding is caught",
       needs=("office_links",))
def _entity_link_rule(OL):
    """The rule of src/parse/office_links.py (the design study "officials-links" and the owner's
    answers of 16 November 2026), on people as the files on disk give them (_link_fixture_pool).
    Fixtures that hold for good: the two Patrick Longs of Manchester, both Democrats of
    Hillsborough County who sat together, never join -- a holder named Patrick Long or Pat Long
    is two people answering, and either Long weighed against the other differs by the middle
    initial; Benjamin S. Bartlett is never Rep. Benjamin T. Bartlett (the middle initials
    differ: listed as such); Tom Stewart is never Thomas Stewart and Rich Green never Richard
    Green (the owner's answers of 13 and 7 November: a short form, and a member-elect of the very
    name); Joseph D. Kenney, councilor for District 1, links to Rep. and Sen. Joseph D. Kenney of
    Wakefield, on the middle initial, Wakefield in the district and the party. And the owner's
    answers: a missing middle initial blocks nothing (Toni Pappas links on her town and party)
    and an agreeing one is no evidence (David M. Scanlan, with no other agreement, is hers to
    settle); a short form is hers (Chris for Christopher); Roger R. Berube as a register of
    deeds while he sat (Art. 95) and Omer C. Ahern Jr. against an Omer Ahern with no suffix are
    hers. Then the check: Kenney's link, worked out again, holds, and fails on a new member-elect
    of the name, a party that now differs, a seat in the term the office was held, the owner's
    word that the holder is no one of the record or not him, a secondary source, a short form
    taken for a link, and evidence that reads otherwise than the link kept it. And Joe Pitre is
    a form of Joseph Pitre's name, which a link the owner confirms gives him (the tree check
    holds what the model makes of it)."""
    pool = _link_fixture_pool()
    ix = OL.by_surname(pool)
    inc = {"executive-council", "us-house", "us-senate", "secretary-of-state", "register-of-deeds", "sheriff"}
    H = lambda *a, **k: _link_holder(OL, *a, **k)  # noqa: E731
    council1 = {"kind": "district", "id": "council:2022:1", "towns": {"wakefield": "Wakefield", "ossipee": "Ossipee"},
                "town_county": {"wakefield": "Carroll", "ossipee": "Carroll"}}

    def verdict(h, index=ix):
        return OL.decide(h, index, inc)

    # Kenney links, on the evidence the study read.
    kenney = H("executive-council", "Joseph D. Kenney", "R", area=council1, where="1")
    d = verdict(kenney)
    assert d["verdict"] == "link" and d["person"] == "376013", f"Kenney did not link: {d}"
    ev = d["evidence"]
    assert ev["middle"] == "D = D" and ev["area"] == "Wakefield in council:2022:1" \
        and ev["party"] == "R among D/R" and ev["incompatible"] == "no seat in 2025-2026", ev
    # The Longs: a holder of either name is two people answering; each weighed against the other
    # differs by the middle initial.
    for printed in ("Patrick Long", "Pat Long", "Patrick N. Long"):
        d = verdict(H("county-commissioner", printed, "D", "Manchester", _county("Hillsborough"), where="hillsborough:1"))
        assert d["verdict"] == "list" and "2 people answer" in d["why"], f"{printed}: {d}"
    for me, other in (("540", "11177"), ("11177", "540")):
        alone = OL.by_surname([p for p in pool if p["key"] != me])
        mine = next(p for p in pool if p["key"] == me)
        d = verdict(H("county-treasurer", next(n for n in mine["names"] if "." in n or n.count(" ") == 2),
                      "D", "Manchester", _county("Hillsborough")), alone)
        assert d["verdict"] == "list" and d["kind"] == "middle initial", f"the Longs joined ({me} to {other}): {d}"
    # The Bartletts.
    d = verdict(H("sheriff", "Benjamin S. Bartlett", "R", "Newport", _county("Sullivan")))
    assert d["verdict"] == "list" and d["kind"] == "middle initial", f"the Bartletts: {d}"
    # Stewart and Green: a member-elect of the very name, and a short form.
    for printed, past in (("Tom Stewart", "375950"), ("Rich Green", "209050")):
        d = verdict(H("county-commissioner", printed, "D", "", _county("Hillsborough")))
        assert d["verdict"] == "list" and "2 people answer" in d["why"], f"{printed}: {d}"
        d = verdict(H("county-commissioner", printed, "D", "", _county("Hillsborough")),
                    OL.by_surname([p for p in pool if p["kind"] != "elect"]))
        assert d["verdict"] == "list" and d["kind"] == "short form" \
            and [c["person"] for c in d["candidates"]] == [past], f"{printed}: {d}"
    # The owner's answers, and the study's other cases.
    d = verdict(H("county-commissioner", "Toni Pappas", "R", "Manchester", _county("Hillsborough")))
    assert d["verdict"] == "link" and d["person"] == "331371" and d["agreements"] == ["town", "party"], d
    d = verdict(H("secretary-of-state", "David M. Scanlan"))
    assert d["verdict"] == "list" and d["why"] == "too little evidence", f"a middle initial alone linked: {d}"
    d = verdict(H("us-house", "Chris Pappas", "D"))
    assert d["verdict"] == "list" and d["kind"] == "short form", d
    d = verdict(H("register-of-deeds", "Roger R. Berube", "", "", _county("Strafford"), ("2017-2018",)))
    assert d["verdict"] == "list" and "a seat the office forbids (a seat in 2017-2018)" in d["why"], d
    d = verdict(H("county-commissioner", "Omer C. Ahern Jr.", "R", "", _county("Grafton")))
    assert d["verdict"] == "list" and d["why"] == "a Jr. or Sr. on one side only", d
    # The check: Kenney's link worked out again.
    d = verdict(kenney)
    tenure = {"tenure": "officials:council.districts.1", "person": "376013", "files": ["officials"],
              "link": dict({"by": "rule"}, **d["evidence"])}
    official = ("officials",)

    def problems(t=tenure, h=kenney, pl=pool, owner=None):
        return OL.verify(t, h, OL.by_surname(pl), inc, owner or {}, official)
    assert problems() == [], problems()
    faults = (
        ("a new member-elect of the name", dict(pl=pool + [_pool_person(
            "elect:x", ["Joseph Kenney"], kind="elect", party="R", county=["Carroll"], terms=["2027-2028"])]),
         "2 people answer"),
        ("a party that now differs", dict(pl=[dict(p, parties={"D"}) if p["key"] == "376013" else p for p in pool]),
         "the party differs"),
        ("a seat in the term the office was held",
         dict(pl=[dict(p, terms=p["terms"] | {"2025-2026"}) if p["key"] == "376013" else p for p in pool]),
         "breaks the seat rule"),
        ("the owner's word that he is no one of the record",
         dict(owner={kenney["key"]: {"person": None, "why": "two people"}}), "is no one of the record"),
        ("the owner's word that he is not this person",
         dict(owner={kenney["key"]: {"person": "376013", "evidence": "x", "not": ["376013"]}}), "says it is not"),
        ("a secondary source", dict(t=dict(tenure, files=["records/sources/nhpr/general.csv"])), "NHPR"),
        ("a short form taken for a link", dict(h=dict(kenney, printed="Joe Kenney")), "by a short form"),
        ("evidence that reads otherwise", dict(t=dict(tenure, link=dict(tenure["link"], area="Ossipee in council:2022:1"))),
         "the area was"),
    )
    for what, change, words in faults:
        said = problems(**change)
        assert any(words in s for s in said), f"{what} was not caught: {said}"
    # A confirmed short form is a form of the name; the person's own first name is none.
    pitre = _pool_person("647", ["Joseph Pitre", "Pitre, Joseph", "Joseph A. Pitre"], mid="a")
    nf = OL.name_form("Joe Pitre", pitre)
    assert nf == {"name": "Joe Pitre", "given": "Joe", "of": "Joseph"} and OL.name_form("Joseph Pitre", pitre) is None, nf
    return "ok", ("Kenney links on D = D, Wakefield in the district and the party; the Longs, the Bartletts, "
                  "Stewart and Green never join; Toni Pappas links with no middle initial, Scanlan's alone does "
                  f"not; a short form, Art. 95 and a lone Jr. go to the owner; {len(faults)} ways a link stops "
                  "holding are each caught; Joe Pitre is a form of Joseph Pitre's name")


@check("files", "the offices that bar a seat in the House and Senate are the state's setting, each one Pt. 2, Art. 95 names, and the rule names nothing of the state",
       needs=("entities", "state_settings"))
def _entity_seat_rule_setting(EN, ST):
    """The rule's fifth condition is the state's (src/lib/state_settings.json seat_incompatible),
    read from the Constitution on file: Pt. 2, Art. 95 bars a judge, the secretary, the treasurer
    of the state, the attorney-general, a register of deeds, a sheriff and a member of Congress
    from a seat in the senate or house, and a member of the council too. Each office the setting
    names is an office of the settings, each is in the article's words, it bars a seat in the
    two chambers and no more, and src/parse/office_links.py, the rule, names neither the state,
    its legislature, a county nor a host anywhere but in its prose."""
    con = json.loads((_paths.ROOT / "collected" / "constitution.json").read_text(encoding="utf-8"))
    art = ""
    for part in con["parts"]:
        for div in part.get("divisions") or [part]:
            for a in div.get("articles") or []:
                if part["part"] == 2 and str(a.get("key")) == "95":
                    art = " ".join(a.get("text") or []).lower()
    assert "have a seat in the senate, or house of representatives" in art, "Pt. 2, Art. 95 is not on file as read"
    s = ST.SETTINGS["seat_incompatible"]
    offices = {o["office"] for o in EN.offices(ST.SETTINGS)}
    assert s["constitution"] == ["Pt. 2, Art. 95"] and s["with"] == ["house", "senate"] and s.get("source"), s
    words = {"executive-council": "member of the council", "us-house": "members of congress",
             "us-senate": "members of congress", "secretary-of-state": "secretary",
             "treasurer": "treasurer of the state", "attorney-general": "attorney-general",
             "supreme-court-justice": "judge of any court", "superior-court-justice": "judge of any court",
             "sheriff": "sheriff", "register-of-deeds": "register of deeds"}
    assert sorted(s["offices"]) == sorted(words), f"the setting names {sorted(s['offices'])}"
    for o in s["offices"]:
        assert o in offices and words[o] in art, f"{o} is not an office of the settings, or not in Art. 95's words"
    tree = _parsed(_paths.locate("office_links.py"))
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    named = [ST.SETTINGS["state"]["name"], ST.SETTINGS["legislature"]["name"],
             ST.SETTINGS["source_hosts"]["legislature"]] + list(ST.COUNTIES)
    said = sorted({w for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                   and id(n) not in docs for w in named if w.lower() in n.value.lower()})
    assert not said, f"src/parse/office_links.py names {said} outside its prose: the state's are the caller's"
    return "ok", (f"{len(s['offices'])} offices bar a seat in the House and Senate, each in Art. 95's words and "
                  "each an office of the settings; the rule names nothing of the state")


def _link_world(root, PE):
    """_world's tree with every file the pool of people is read from, and four holders more in its
    hand file of officials: a Carroll treasurer, "Bo M. Hart" of Conway, whom the member table
    gives the middle initial M and the town (the rule links him); a US senator, "Gus Old", a
    senator of 1991-1992 with no page (the rule links him, and the link is kept); a Carroll
    register of deeds, "Joe Pike", a short form of Rep. Joseph Pike's name (the owner's to
    settle); and _world's councilor for District 2, "Ada Newcomb", who shares the name of a member
    sitting now (a seat the office forbids) and lives in Conway, in District 1 (the area
    differs too)."""
    root = Path(root)
    pike = {"376020": _careers_record({"2021-2022": ("H", "376020")}, "Joseph", "Pike", "R", "H")}
    _world(root, PE, pike)
    hand = json.loads((root / "corrections" / "officials.json").read_text(encoding="utf-8"))
    hand["us_senate"] = {"office": "United States Senate", "seats": [{"name": "Gus Old", "party": "D"}]}
    carroll = hand["county"]["counties"]["Carroll"]
    carroll["treasurer"] = {"name": "Bo M. Hart", "office": "County Treasurer", "domicile": "Conway"}
    carroll["register_of_deeds"] = {"name": "Joe Pike", "office": "Register of Deeds", "domicile": "Conway"}
    (root / "corrections" / "officials.json").write_text(json.dumps(hand, ensure_ascii=False, indent=2),
                                                         encoding="utf-8")
    cols = ["PersonID", "LastName", "FirstName", "Employeeno", "MiddleName", "LegislativeBody", "Active",
            "seatno", "countycode", "District", "party", "Expr1", "Address", "address2", "city", "Zipcode",
            "Expr2", "EMailAddress", "GenderCode", "SecretaryID", "database"]
    (root / "db" / "_columns.json").write_text(json.dumps({"Legislators": cols}), encoding="utf-8")

    def row(**k):
        return "|".join(str(k.get(c, "")) for c in cols) + "\n"
    (root / "db" / "Legislators.psv").write_text(
        row(PersonID="11600", LastName="Newcomb", FirstName="Ada", Employeeno="376001", countycode="02", party="R",
            Address="1 Main St", city="Conway", Zipcode="03818")
        + row(PersonID="11700", LastName="Lund", FirstName="Cy", Employeeno="209001", countycode="07", party="R",
              Address="State House, Room 1", city="Concord", Zipcode="03301")
        + row(LastName="Hart", FirstName="Bo", Employeeno="376002", MiddleName="M.", countycode="02", party="d",
              Address="2 Elm St", city="Conway", Zipcode="03818")
        + row(LastName="Pike", FirstName="Joseph", Employeeno="376020", MiddleName="Q.", countycode="02", party="R",
              Address="3 Oak St", city="Conway", Zipcode="03818"), encoding="utf-8")
    (root / "data" / "legislators.json").write_text(json.dumps([
        {"id": "11600", "first": "Ada", "middle": "", "last": "Newcomb", "county_code": "02", "county": "Carroll",
         "address": "1 Main St, Conway, NH, 03818"},
        {"id": "11700", "first": "Cy", "middle": "", "last": "Lund", "county_code": "07", "county": "Merrimack",
         "address": "NH"}]), encoding="utf-8")
    (root / "past_members.json").write_text(json.dumps({"370001": "Sen. Old, Gus(Dist. 03)"}), encoding="utf-8")
    (root / "member_party.json").write_text(json.dumps(
        {"370001": {"county": "", "district": "03", "party": "D", "source": "1991-S3"}}), encoding="utf-8")
    (root / "text_sponsors.json").write_text("{}", encoding="utf-8")
    (root / "generated" / "past_roster.json").write_text(json.dumps({"format": 1, "rows": [
        {"term": "1991-1992", "chamber": "S", "person": "370001", "gc_employee_number": "370001",
         "name": "Gus Old", "seats": [{"county": "", "district": "3"}]}]}), encoding="utf-8")
    (root / "generated" / "manual_seats.json").write_text(json.dumps({"terms": {}}), encoding="utf-8")
    (root / "collected" / "nh_streets.json").write_text(json.dumps(
        {"columns": ["zip", "town"], "rows": [["03818", "Conway"]]}), encoding="utf-8")


# The owner's hand file of links, as the tree of _entity_links_on_a_tree has her write it.
_OWNER_LINKS = {
    "_README": ["made up"], "_checked": "2026-11-16",
    "links": {
        # Her word over the rule's: the treasurer the rule links is someone else.
        "county-treasurer|carroll|2025|Bo M. Hart": {"person": None, "not": ["376002"],
                                                     "why": "two people: made up"},
        # A short form she confirms.
        "register-of-deeds|carroll|2025|Joe Pike": {"person": "376020", "evidence": "made up"},
        # A past winner the model does not hold yet.
        "executive-council|5|2019|Debora B. Pignatelli": {"person": "203025", "evidence": "made up"},
    },
    "name_forms": {"11600": [{"name": "Adaline Newcomb", "evidence": "made up"}],
                   "11700": [{"name": "Cyrus Lund", "evidence": "made up"}]},
    "proposed": {"us-house|1|2025|Chris Pappas": {"person": "376509", "evidence": "a proposal, not yet hers"}},
}


@check("build", "build_entities.py links the officials of a made-up tree into data/entities/ alone: by the rule where it holds, to a person with no page too, by the owner's hand file over the rule when it is there, and says when it is not",
       needs=("build_entities", "entities", "people", "office_links", "state_settings"))
def _entity_links_on_a_tree(BE, EN, PE, OL, ST):
    """The night's step on a made-up tree with every file the pool of people is read from
    (_link_world), run as build_all runs it, twice. Without the owner's hand file of links, it
    says the file is not here (on its output and in the manifest), links the Carroll treasurer
    by the rule (the middle initial M, his town of Conway, his county), links the senator to a
    member of 1991-1992 with no page, who is a person of the model in no view of today's files,
    and lists the short form and the councilor who only shares the name of a member sitting now
    (Art. 95 forbids it, and her area differs). With the file, her word is taken over the rule's:
    the treasurer is no one of the
    record, the short form she confirmed is linked and gives the person the form of the name
    ('Joseph "Joe" Pike', found by Joe), a form of a name she lists is kept and one that is no
    form of theirs is said, an entry for a holder the model does not hold yet waits, and her
    proposals are not taken. Each time it writes data/entities/ and nothing else, every file it
    read comes back byte for byte, the model keeps every rule, and every link worked out again
    holds -- and a rule's link put on the holder she said is someone else is caught."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-links-"))
    try:
        _link_world(tmp, PE)
        runs = {}
        for name, owner in (("alone", None), ("hers", _OWNER_LINKS)):
            hand = tmp / "corrections" / "officials_links.json"
            if owner is None:
                hand.unlink(missing_ok=True)
            else:
                hand.write_text(json.dumps(owner, indent=1), encoding="utf-8")
            shutil.rmtree(tmp / "data" / "entities", ignore_errors=True)
            before = _tree_digest(tmp)
            r = _run([sys.executable, str(_paths.script("build_entities.py")), "--out", "data/entities"],
                     cwd=tmp, capture_output=True, text=True, timeout=300)
            assert r.returncode == 0, f"build_entities.py exited {r.returncode}: {(r.stderr or r.stdout)[-600:]}"
            after = _tree_digest(tmp)
            changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
            assert changed and all(k.startswith("data/entities/") for k in changed), (
                f"build_entities.py wrote outside data/entities/: {[k for k in changed if not k.startswith('data/entities/')]}")
            model, layouts, manifest = EN.load(tmp / "data" / "entities")
            assert EN.problems(model) == [], EN.problems(model)[:3]
            bad = [(rel, w) for rel, ok, w in BE.rebuilt(model, layouts, tmp) if ok is not True]
            assert not bad, "a file of the tree is not given back: " + "; ".join(f"{a}: {w[:200]}" for a, w in bad)
            report = {"notes": [], "links_hand": []}
            pool, missing = BE.link_pool(tmp, model, manifest["links"]["roster_term"], report)
            assert pool is not None, missing
            said = BE.verify_links(model, pool, BE.read_owner_links(tmp, report), ST.SETTINGS,
                                   layouts[BE.HAND].get("_checked"))
            assert said == [], said
            runs[name] = (model, manifest, r.stdout, pool, layouts)
        model, manifest, out, pool, layouts = runs["alone"]
        T = {t["tenure"]: t for t in model["tenure"]}
        P = {p["person"]: p for p in model["person"]}
        assert "corrections/officials_links.json is not here" in out and any(
            "is not here" in x for x in manifest["links_hand"]), "the hand file's absence is not said"
        bo = T["officials:county.counties.Carroll.treasurer"]
        assert bo["person"] == "376002" and bo["link"]["by"] == "rule" and bo["link"]["middle"] == "M = M" \
            and bo["link"]["town"] == "Conway = Conway", bo
        gus = T["officials:us_senate.seats.0"]
        assert gus["person"] == "370001" and P["370001"].get("files") == ["generated/past_roster.json"] \
            and not P["370001"].get("page") and "370001" not in {p["person"] for p in EN.view_people(model)}, gus
        listed = {x["tenure"]: x for x in manifest["links"]["listed"]}
        ada = listed["officials:council.districts.2"]
        assert listed["officials:county.counties.Carroll.register_of_deeds"]["kind"] == "short form" \
            and ada["why"] == "a seat the office forbids (a seat in 2025-2026)" \
            and ada["answering"][0]["evidence"]["area"] == "differ: Conway not in council:2022:2", listed
        assert T["officials:council.districts.2"]["person"] is None, "a holder who only shares a member's name was linked"
        model, manifest, out, pool, layouts = runs["hers"]
        T = {t["tenure"]: t for t in model["tenure"]}
        P = {p["person"]: p for p in model["person"]}
        bo = T["officials:county.counties.Carroll.treasurer"]
        assert bo["person"] is None and bo["link"] == {"by": "owner", "key": "county-treasurer|carroll|2025|Bo M. Hart",
                                                      "why": "two people: made up", "not": ["376002"]}, bo
        pike = T["officials:county.counties.Carroll.register_of_deeds"]
        assert pike["person"] == "376020" and pike["link"]["by"] == "owner", pike
        assert P["376020"]["name_forms"] == [{"name": "Joe Pike", "given": "Joe", "of": "Joseph",
                                              "source": "corrections/officials_links.json register-of-deeds|carroll|2025|Joe Pike"}]
        assert [f["name"] for f in P["11600"]["name_forms"]] == ["Adaline Newcomb"] and not P["11700"].get("name_forms")
        # The search index's part: the name a page would show, and the words that find him.
        names = EN.view_names(model)
        assert names["376020"] == {"name": "Joseph Pike", "display": 'Joseph "Joe" Pike',
                                   "words": ["Joe Pike", "Joe"]} and "11700" not in names, names
        said = " ".join(manifest["links_hand"])
        assert "'Cyrus Lund' is not a short form" in said and "1 proposal" in said, manifest["links_hand"]
        assert manifest["links"]["waiting"] == [
            "corrections/officials_links.json executive-council|5|2019|Debora B. Pignatelli: no holder of the model "
            "has this key yet"], manifest["links"]["waiting"]
        assert "us-house|1|2025|Chris Pappas" not in json.dumps(manifest["links"]["made"]), "a proposal was taken"
        # A rule's link on the holder she said is someone else is caught.
        m = copy.deepcopy(model)
        alone = {x["tenure"]: x for x in runs["alone"][0]["tenure"]}
        t = next(t for t in m["tenure"] if t["tenure"] == "officials:county.counties.Carroll.treasurer")
        t["person"], t["link"] = "376002", dict(alone[t["tenure"]]["link"])
        said = BE.verify_links(m, pool, BE.read_owner_links(tmp, {"links_hand": []}), ST.SETTINGS, "2026-11-10")
        assert any("is no one of the record" in s for s in said), said
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("without her file: said, the treasurer linked by the rule on M = M and Conway, the senator to a "
                  "member of 1991-1992 with no page, the short form and the shared name listed; with it: her word "
                  "over the rule's, a confirmed Joe gives 'Joseph \"Joe\" Pike', a waiting entry and a proposal "
                  "left; data/entities/ alone written, every file given back, every link holds")


@check("data", "every official the built model links to a person of the record holds the rule worked out again on today's files, and the owner's word is taken as she wrote it",
       needs=("build_entities", "entities", "office_links", "state_settings"))
def _entity_links_hold(BE, EN, OL, ST):
    """The check of the officials' links on the night's model (src/parse/office_links.verify):
    data/entities/, as build_entities.py wrote it in the build, read back; the pool of people
    built again from the files on disk now; and every link the rule made worked out again -- it
    fails when the person is no longer the only one who answers to the name (a new member-elect
    of it), when any piece of evidence reads otherwise than the link kept it, when a seat the
    office forbids is on the record (Pt. 2, Art. 95), when the owner's hand file of links says
    the holder is someone else or no one, and when the holder's file is not an official one (NHPR's
    results never are). Every entry of hers that names a holder of the model is taken as she wrote
    it, and the manifest's count of what was linked is the model's. A tree no build has run the
    model in is skipped."""
    folder = Path("data") / "entities"
    if not (folder / EN.MANIFEST).is_file():
        return "skip", "no build has made data/entities/ here"
    model, layouts, manifest = EN.load(folder)
    links = (manifest or {}).get("links") or {}
    if not links:
        return "skip", "data/entities/ was built before the officials were linked (its manifest has no links)"
    report = {"notes": [], "links_hand": []}
    owner = BE.read_owner_links(".", report)
    pool, missing = BE.link_pool(".", model, links.get("roster_term"), report)
    rule = [t for t in model["tenure"] if (t.get("link") or {}).get("by") == "rule"]
    held = [t for t in model["tenure"] if t.get("link")]
    if pool is None:
        assert not rule, (f"{len(rule)} officials are linked by the rule, and the files they were weighed on are "
                          f"not here to check them: {', '.join(missing)}")
        return "skip", f"no official is linked by the rule here, and the pool's files are not all here: {', '.join(missing)}"
    said = BE.verify_links(model, pool, owner, ST.SETTINGS, str(layouts.get(BE.HAND, {}).get("_checked") or ""))
    assert not said, f"{len(said)} link(s) no longer hold: " + "; ".join(said[:4])
    made = links.get("made") or []
    assert sum(1 for m in made if m["by"] == "rule") == len(rule), (
        f"the manifest says {sum(1 for m in made if m['by'] == 'rule')} links by the rule, and the model holds {len(rule)}")
    return "ok", (f"{len(rule)} officials linked by the rule and {len(held) - len(rule)} by the owner's word, each "
                  f"worked out again on today's files; {len(links.get('listed') or [])} on her list")
