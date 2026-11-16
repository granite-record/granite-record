#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.1
"""
preflight's checks of the model of people, offices, terms, districts and elections
(src/lib/entities.py): its shapes and rules, and the offices and kinds of district the state's
settings give (the refactor's design of 16 November 2026, step 1).

A module of its own, because the model is of no one area: it will read the people's, the
officials', the districts', the officers' and the members-elect's files. This module uses pf_core
and itself, and no other area's module.
"""

import ast
import copy
import json
import re

import _paths

from pf_core import (_parsed, check)


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
