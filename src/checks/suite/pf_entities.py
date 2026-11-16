#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.3
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


def _world(root, PE):
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
