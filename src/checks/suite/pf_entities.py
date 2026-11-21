#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.32
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

from pf_core import (_in_suite, _parsed, _run, _source, check)

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


@check("build", "a primary is one party's contest: it carries the party as printed and its letters, its "
       "id's stage word says it (\"primary-r\"), a general names none, and the State Primary readers' "
       "ids are the model's", needs=("entities",))
def _entity_primary_party(EN):
    """The elections display design of 19 November 2026 (the Model row of its section 1): the
    model's contest had a stage and no party, and two parties' primaries for one office on one
    day are two contests. On the state's own settings, two primaries for Congress 1 and the
    general beside them hold every rule; a primary with no party, a primary whose id names
    another party, a general naming a party and a primary's letters the table does not read are
    each seen. Then every race of collected/primary_<year>.json that carries an id has one of the
    model's shape whose stage word is its party's (the House and Senate ones carry none yet)."""
    offices = EN.offices(None)
    day, gen = "2024-09-10", "2024-11-05"
    r, d = EN.contest_id(day, "primary", "us-house", "1", "r"), EN.contest_id(day, "primary", "us-house", "1", "d")
    assert (r, EN.contest_id(gen, "general", "us-house", "1")) == (
        "2024-09-10.primary-r.us-house.1", "2024-11-05.general.us-house.1"), f"the ids: {r}"
    base = {"office": offices, "contest": [
        {"contest": r, "election": day, "stage": "primary", "party": "r", "parties": ["R"],
         "office": "us-house", "district": None, "seats": 1, "source": "m"},
        {"contest": d, "election": day, "stage": "primary", "party": "d", "parties": ["D"],
         "office": "us-house", "district": None, "seats": 1, "source": "m"},
        {"contest": EN.contest_id(gen, "general", "us-house", "1"), "election": gen, "stage": "general",
         "office": "us-house", "district": None, "seats": 1, "source": "m"}],
        "candidacy": [{"candidacy": EN.candidacy_id(r, "Russell Prescott", "r"), "contest": r,
                       "printed": "Russell Prescott", "party": "r", "parties": ["R"], "person": None,
                       "source": "m"}]}
    got = EN.problems(base)
    assert got == [], f"two primaries and a general that keep every rule broke some: {got[:4]}"

    def fault(what, i, change, words):
        m = copy.deepcopy(base)
        m["contest"][i].update(change)
        for k in [k for k, v in change.items() if v is None]:
            del m["contest"][i][k]
        said = EN.problems(m)
        assert any(words in s for s in said), f"{what} was not seen ({said[:3]})"

    fault("a primary with no party", 0, {"party": None, "parties": None}, "names no party")
    fault("a primary whose id names another party", 1, {"party": "r", "parties": ["R"]}, "its id says")
    fault("a general naming a party", 2, {"party": "r", "parties": ["R"]}, "names a party")
    fault("a primary's letters the table does not read so", 0, {"parties": ["D"]}, "which the table reads")
    ids, files = 0, sorted(Path("collected").glob("primary_*.json"))
    for p in files:
        doc = json.loads(p.read_text(encoding="utf-8"))
        for key, race in doc["races"].items():
            if "contest" not in race:
                continue
            ids += 1
            word = race["contest"].split(".")[1]
            assert re.match(EN.CONTEST, race["contest"]) and word == "primary-" + EN.slug(race["party"]), (
                f"{p.name} {key}: {race['contest']} is not the model's id of the {race['party']!r} primary")
            for c in race["candidates"]:
                assert re.match(EN.CANDIDACY, c["id"]), f"{p.name} {key}: {c['id']} is no candidacy id"
    if not files:
        return "skip", "the rule held; no collected/primary_<year>.json here to hold the readers' ids to"
    return "ok", (f"two primaries and a general hold, four faults each seen; {ids} primary races' ids "
                  f"in {len(files)} files are the model's")


@check("build", "a special election is a contest of stage special, its primary names it (\"for\") and is "
       "never a State Primary, its cause is a record's, and a recount's count and a write-in are a "
       "candidacy's", needs=("entities",))
def _entity_special_contest(EN):
    """The specials design of 19 November 2026 (A2, decision 3; the owner's "Yes to all 9"):
    contest gains "for" (a special's primary, pointing at its special), "cause" (a tie of the
    general that elected the term, with the resolution, or a vacancy; only where a record states
    it) and "recounted" (the recount's day); candidacy gains "votes", "first_count" and
    "write_in". On the state's own settings, a made-up special of 2026, its Democratic primary
    and the tied general it re-runs hold every rule and shape; a "for" on a general, a "for" at a
    contest that is no special, a cause of a kind no record gives and a cause with a field it does
    not have are each seen."""
    offices = EN.offices(None)
    sp = EN.contest_id("2026-03-10", "special", "house", "a-7")
    pr = EN.contest_id("2026-01-20", "primary", "house", "a-7", "d")
    gen = EN.contest_id("2024-11-05", "general", "house", "a-7")
    base = {"office": offices, "contest": [
        {"contest": gen, "election": "2024-11-05", "stage": "general", "office": "house", "district": None,
         "seats": 1, "source": "m"},
        {"contest": sp, "election": "2026-03-10", "stage": "special", "office": "house", "district": None,
         "seats": 1, "recounted": "2026-03-16",
         "cause": {"kind": "tie", "resolution": "House Resolution 9", "of": gen}, "source": "m"},
        {"contest": pr, "election": "2026-01-20", "stage": "primary", "party": "d", "parties": ["D"],
         "office": "house", "district": None, "seats": 1, "for": sp, "source": "m"}],
        "candidacy": [
            {"candidacy": EN.candidacy_id(sp, "Ann Example", "d"), "contest": sp, "printed": "Ann Example",
             "party": "d", "parties": ["D"], "elected": True, "votes": 880, "first_count": 879,
             "person": None, "source": "m"},
            {"candidacy": EN.candidacy_id(pr, "Ann Example", "d"), "contest": pr, "printed": "Ann Example",
             "party": "d", "parties": ["D"], "votes": 77, "write_in": True, "person": None, "source": "m"}]}
    got = EN.problems(base)
    assert got == [], f"a special, its primary and the tie it re-runs broke some rules: {got[:4]}"

    def fault(what, i, change, words):
        m = copy.deepcopy(base)
        m["contest"][i].update(change)
        said = EN.problems(m)
        assert any(words in s for s in said), f"{what} was not seen ({said[:3]})"

    fault("a general that names a contest it is for", 0, {"for": sp}, "names a contest it is for")
    fault("a primary for a contest that is no special", 2, {"for": gen}, "which is no special")
    fault("a cause of a kind no record gives", 1, {"cause": {"kind": "guess"}}, "not one of")
    fault("a cause with a field it does not have", 1, {"cause": {"kind": "tie", "who": "x"}},
          "a field its kind does not")
    return "ok", ("a special with its recount and the tie it re-runs, its primary "
                  "for it with a write-in, hold; four faults each seen")


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


# Sponsor lines of a made-up text_sponsors.json, as text_sponsors.py writes them: a member printed
# at one seat under two names and at a second seat in the same term, a line placed on no one, a
# senator in two terms, a member people.json does not hold, a line with no district and a
# committee's line of no chamber.
_PRINTED_DOC = {
    "2021-2022": {
        "HB1": [{"member_id": "3001", "name": "Smith", "chamber": "H", "county": "Rockingham", "district": "1"},
                {"member_id": "", "name": "Jones", "chamber": "H", "county": "", "district": "24"},
                {"member_id": "3002", "name": "Lee", "chamber": "S", "county": "", "district": "7"},
                {"member_id": "3003", "name": "Moe", "chamber": "H", "county": "Carroll", "district": ""},
                {"member_id": "", "name": "Rules Committee", "chamber": "", "county": "", "district": ""}],
        "HB2": [{"member_id": "3001", "name": "J. Smith", "chamber": "H", "county": "Rockingham", "district": "1"},
                {"member_id": "3001", "name": "Smith", "chamber": "H", "county": "Rockingham", "district": "2"}]},
    "2023-2024": {
        "SB1": [{"member_id": "3002", "name": "Lee", "chamber": "S", "county": "", "district": "7"},
                {"member_id": "3004", "name": "Poe", "chamber": "H", "county": "Belknap", "district": "8"}]}}


@check("build", "the model holds the seat each member held in each term as the term's bills print it: one tenure a member, seat and term, under every name printed, with the person and, in an era on file, the district",
       needs=("build_entities", "entities", "people"))
def _entities_printed_seats(BE, EN, PE):
    """THE SEAT A TERM'S BILLS PRINT, IN THE MODEL (the design of 16 November 2026, step 5: the
    seat-in-a-term readers read the tenure table). entities.printed_tenures reads
    text_sponsors.json's sponsor lines into one tenure a member, seat and term, in the order the
    file first prints each: a member printed at two seats in a term has two; a line placed on no
    one is a seat with no member; every name a seat is printed under is kept, in order; a line
    with no district, or of no chamber, is no seat. build_entities.printed_seats gives each the
    person people.json gives its member id, and the district only where the term's era of
    districts is on file (2021-2022's "Belknap 8" is not today's Belknap 8); build() puts them
    in the model on a made-up tree, every one shaped as a tenure; and with no file, none, said."""
    want = [("printed:2021-2022:3001|H|Rockingham|1", "3001", ["Smith", "J. Smith"], "501", None),
            ("printed:2021-2022:|H||24", None, ["Jones"], None, None),
            ("printed:2021-2022:3002|S||7", "3002", ["Lee"], "502", None),
            ("printed:2021-2022:3001|H|Rockingham|2", "3001", ["Smith"], "501", None),
            ("printed:2023-2024:3002|S||7", "3002", ["Lee"], "502", "senate:2022:7"),
            ("printed:2023-2024:3004|H|Belknap|8", "3004", ["Poe"], None, "house:2022:belknap-8")]
    plain = EN.printed_tenures(_PRINTED_DOC, "text_sponsors.json")
    assert [t["tenure"] for t in plain] == [w[0] for w in want], [t["tenure"] for t in plain]
    assert all(t["person"] is None and "district" not in t and t["files"] == ["text_sponsors.json"]
               for t in plain), plain
    tmp = Path(tempfile.mkdtemp(prefix="gr-printed-"))
    try:
        _copy_tracked(tmp, [n for n in TRACKED if n.startswith("records/")])
        settings = BE.ST.SETTINGS
        districts, _places = BE.districts_and_places(tmp, settings)
        report = {"notes": []}
        assert BE.printed_seats(tmp, settings, {}, districts, report) == [] and any(
            BE.SPONSORS in n for n in report["notes"]), "no text_sponsors.json, and the model was not told"
        (tmp / BE.SPONSORS).write_text(json.dumps(_PRINTED_DOC), encoding="utf-8")
        by_mid = {"3001": {"person": "501"}, "3002": {"person": "502"}}
        got = BE.printed_seats(tmp, settings, by_mid, districts, {"notes": []})
        seen = [(t["tenure"], t.get("member_id"), t["sponsor_line"]["names"], t["person"], t.get("district"))
                for t in got]
        assert seen == want, f"the printed seats are {seen}"
        assert got[0]["sponsor_line"] == {"chamber": "H", "county": "Rockingham", "district": "1",
                                          "names": ["Smith", "J. Smith"]}, got[0]
        assert {t["office"] for t in got} == {"house", "senate"}, {t["office"] for t in got}
        bad = [p for t in got for p in EN.shape_problems(t, EN.SHAPES["tenure"], t["tenure"])]
        assert not bad, bad
        # build() puts them in the model, on the made-up tree of the round trip.
        _world(tmp, PE)
        model, _layouts, report = BE.build(tmp)
        held = [t for t in model["tenure"] if t["tenure"].startswith("printed:")]
        assert [t["tenure"] for t in held] == [w[0] for w in want], [t["tenure"] for t in held]
        assert not [p for p in report["problems"] if "printed:" in p], report["problems"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", (f"{len(want)} seats of a made-up text_sponsors.json, in the file's order, two seats of one "
                  "member in a term two tenures, a line placed on no one a seat with no member, every name "
                  "kept; persons by member id; a district only in an era on file; in the model build() "
                  "makes, with no problem; no file, no seat, and said")


# The readers of the seat a member held in a term that read the model's tenures (the design's
# step 5), each through entities.printed_tenures: _entities_step_in_the_plan lets them import the
# shapes' module, and nothing else. build_site_v2's reader (printed_record) is members.py's since
# 20 November 2026, and build_site_v2 imports the shapes' module still, so both are here.
SEAT_READERS = {"build_members_elect.py", "build_site_v2.py", "members.py"}


def _model_swapped(EN, change):
    """A context in which entities.printed_tenures gives `change` of what it gives: a reader that
    reads the model's tenures answers by the changed ones, and one that reads the lines itself
    does not."""
    import contextlib

    @contextlib.contextmanager
    def swapped():
        real = EN.printed_tenures
        EN.printed_tenures = lambda *a, **k: change(copy.deepcopy(real(*a, **k)))
        try:
            yield
        finally:
            EN.printed_tenures = real
    return swapped()


@check("build", "the seats a member-elect's history is matched against are the model's: build_members_elect.seat_history reads the tenures of the seats a term's bills print, and keeps a member's as a race key",
       needs=("build_members_elect", "entities"))
def _seat_history_reads_the_model(BME, EN):
    """build_members_elect.seat_history (the seats each member printed as their own on each term's
    bills, which an election's surname-only winner is matched to a member by) reads
    entities.printed_tenures, the tenures build_entities puts in the model, rather than the
    sponsor lines (the design of 16 November 2026, step 5; byte-identical on D:/nh's files and the
    fixture site, 18 November 2026). On the made-up lines: a member printed at two seats in a term
    has both, a senator one a term, a line placed on no one and a line with no district are no
    member's. And it answers by the model: a tenure taken out of the model is a seat gone from the
    history, and a tenure put in is one there."""
    want = {"3001": {"2021-2022": ["H|Rockingham|1", "H|Rockingham|2"]},
            "3002": {"2021-2022": ["S|7"], "2023-2024": ["S|7"]},
            "3004": {"2023-2024": ["H|Belknap|8"]}}
    got = BME.seat_history(_PRINTED_DOC)
    assert got == want, f"seat_history gives {got}"
    assert list(got) == ["3001", "3002", "3004"], f"members out of the file's order: {list(got)}"

    def change(ts):
        ts = [t for t in ts if t.get("member_id") != "3004"]
        t = copy.deepcopy(ts[0])
        t.update(tenure="printed:2023-2024:3009|H|Coos|3", term="2023-2024", member_id="3009",
                 sponsor_line={"chamber": "H", "county": "Coos", "district": "3", "names": ["Roe"]})
        return ts + [t]
    with _model_swapped(EN, change):
        moved = BME.seat_history(_PRINTED_DOC)
    assert "3004" not in moved and moved.get("3009") == {"2023-2024": ["H|Coos|3"]}, (
        f"seat_history does not answer by the model's tenures: {moved}")
    return "ok", ("three members' seats from the model's tenures, two seats of one term both kept, a line of "
                  "no member none; a tenure taken out of the model and one put in each move the answer")


@check("build", "the seat of the term a session day names a member by is the model's where the term's bills print one: build_site_v2.printed_record reads the tenures of the seats a term's bills print",
       needs=("build_site_v2", "entities"))
def _printed_record_reads_the_model(B2, EN):
    """build_site_v2.printed_record -- term_seats' first source, the seat a term's bills print for
    a member, which a session day names them by and date_former_seats dates a former member's by
    (printed_seats) -- reads entities.printed_tenures, the tenures build_entities puts in the
    model, rather than the sponsor lines (the design of 16 November 2026, step 5; byte-identical
    on D:/nh's files and the fixture site, 18 November 2026). On the made-up lines and one more,
    a Smith placed on no one at the seat a Smith was placed on: one seat a member is `one`; a
    member at two seats in a term is in `two`; a seat printed under a surname placed on no one
    is `named`, unless a member of that surname was placed at it. And it answers by the model: a
    tenure taken out of the model and one put in each move `one`."""
    doc = copy.deepcopy(_PRINTED_DOC)
    doc["2021-2022"]["HB3"] = [{"member_id": "", "name": "Smith", "chamber": "H", "county": "Rockingham",
                                "district": "1"}]
    tmp = Path(tempfile.mkdtemp(prefix="gr-printed-record-"))
    try:
        f = tmp / "text_sponsors.json"
        f.write_text(json.dumps(doc), encoding="utf-8")
        one, two, named = B2.printed_record(f)
        assert one == {("2021-2022", "3002"): ("S", "", "7"), ("2023-2024", "3002"): ("S", "", "7"),
                       ("2023-2024", "3004"): ("H", "Belknap", "8")}, f"one: {one}"
        assert two == {("2021-2022", "3001")}, f"two: {two}"
        assert named == {("2021-2022", "H", "jones"): {("", "24")}}, f"named: {named}"
        assert B2.printed_seats(f) == one

        def change(ts):
            ts = [t for t in ts if t.get("member_id") != "3004"]
            t = copy.deepcopy(ts[0])
            t.update(tenure="printed:2023-2024:3009|H|Coos|3", term="2023-2024", member_id="3009",
                     sponsor_line={"chamber": "H", "county": "Coos", "district": "3", "names": ["Roe"]})
            return ts + [t]
        with _model_swapped(EN, change):
            moved = B2.printed_record(f)[0]
        assert ("2023-2024", "3004") not in moved and moved.get(("2023-2024", "3009")) == ("H", "Coos", "3"), (
            f"printed_record does not answer by the model's tenures: {moved}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("three one-seat members, one at two seats, one surname placed on no one, and a Smith's seat "
                  "not doubted by an unplaced Smith, from the model's tenures; a tenure taken out of the "
                  "model and one put in each move the answer")


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
    the officers), the members-elect, the town pages (site/places.json), the district map's data
    and the bulk downloads (site/data/people.json), which are the steps that write what it reads
    (the town pages and the map since the district table of step 4 resolves what they print);
    given data/entities as where it writes, and declaring its
    manifest; optional, because no page waits on a model nothing reads. And nothing reads it yet
    (phase A): no step of the plan names data/entities but it, and no code file but it, the shapes'
    module, src/ops/gr_register.py (which asks it only for the first offices' holders it links
    to no one) and the checks imports either or names the folder -- but the seat readers moved
    onto the model's tenures (SEAT_READERS, phase B), which import the shapes' module alone."""
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
    for before in ("parse_districts.py", "build_site_v2.py", "build_members_elect.py", "build_exports.py",
                   "build_town_pages.py", "build_district_map.py"):
        assert before in names and names.index(before) < i, f"build_entities.py runs before {before}"
    assert s.args[1:] == ["--out", "data/entities"] and [p.as_posix() for p in s.produces] == [
        "data/entities/manifest.json"] and s.optional and not s.network, (s.args, s.produces, s.optional)
    others = [x.name for x in steps if x is not s and any("data/entities" in str(a) for a in
                                                          list(x.args) + list(x.needs) + list(x.produces))]
    assert not others, f"steps besides the model's name data/entities: {others}"
    allowed = {"build_entities.py", "entities.py", "gr_register.py", "build_all.py"}
    # PHASE B (the design's step 5, 18 November 2026): a reader moved onto the model's tenures
    # reads them through the shapes' module (entities.printed_tenures), from the file the model
    # is built from, since the step that writes data/entities/ runs after it; never the folder.
    # And the margin (19 November 2026, src/pages/election_margin.py) takes a contest's and a
    # candidacy's id from the shapes' module, so that its ids are the model's; never the folder.
    # The specials reader (19 November 2026, src/parse/parse_sos_specials.py) writes its records in
    # the shapes' module's shapes and ids and holds each to its shape; never the folder.
    # The writer of site/districts.json (19 November 2026, src/towns/parse_districts.py) builds the
    # one district table and its view through the shapes' module (district_table, view_districts)
    # from the lists it reads; never the folder.
    moved = set(SEAT_READERS) | {"election_margin.py", "parse_sos_specials.py", "parse_districts.py"}
    readers = []
    for f in _paths.code_files("*.py"):
        if f.name in allowed or "suite" in f.parent.name:
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        if f.name in moved and "data/entities" not in t and not re.search(
                r"^\s*(?:import|from)\s+build_entities\b", t, re.M):
            continue
        if re.search(r"^\s*(?:import|from)\s+(?:entities|build_entities)\b", t, re.M) or "data/entities" in t:
            readers.append(f.name)
    assert not readers, f"these read the model, which nothing reads yet: {readers}"
    return "ok", (f"step {i + 1} of {len(steps)}, after the district table, the site data, the members-elect, "
                  "the town pages, the district map and the bulk downloads; --out data/entities, optional; no "
                  f"other step or code file reads it, and the {len(SEAT_READERS)} seat reader(s) moved onto its "
                  "tenures, and the margin's ids, read them through entities alone")


def _first_offices_unlinked(BE, root):
    """The first offices' holders and successors of the hand file whom the model built from
    `root` links to no person and names no member page for, worked out from its tenures here and
    not through gr_candidates."""
    model, _layouts, _report = BE.build(root)
    return sorted(t["tenure"] for t in model["tenure"] if BE.HAND in (t.get("files") or [])
                  and t["office"] in BE.FIRST_OFFICES and not t.get("person")
                  and not (t.get("holder") or {}).get("member")), model


@check("naming", "gr_register.py --offices offers a gr- id only to a first office's holder the model links to no one, leaves out every holder it links, offers nothing where it cannot say whom it links, issues nothing unless told, and never one id for a name two places share",
       needs=("gr_register", "gr_ids", "build_entities"))
def _gr_offices_dry_run(REG, GR, BE):
    """The design's question 3 (yes, 16 November 2026): a gr- id, by a person's run, for each
    holder and successor of the first offices with pages -- the Governor, the Council, Congress,
    the Secretary of State, the Treasurer, the Attorney General -- whom the model links to no
    person of the record. EVERY HOLDER THE MODEL LINKS IS LEFT OUT FIRST: on the files of 16
    November the hand file alone left Joseph D. Kenney, Luz Bay, Melanie Levesque and Jeanne
    Shaheen unlinked, and the dry run offered each an id, though the rule of office_links.py links
    all four to members. On a made-up tree with every file the model and its rule read
    (_link_world): the dry run lists exactly the holders the model links to no one (worked out
    here from its tenures) -- not the US senator the rule links to a member of 1991-1992 with no
    page, nor the US representative the hand file's member page links, nor the Governor, who holds
    the id the register issued for her place -- and leaves the register as it was, in memory and
    on disk; with --apply, on a copy, every id issued names its place and the register stays well
    formed. With the owner's hand file of links, a holder she links is left out and one she says is
    no one of the record is offered, with her words. A name two of the places share gets no id,
    since one person is one id and a name cannot say whether it is one person. And on _world,
    which lacks the rule's evidence, nothing is offered: gr_candidates refuses, and
    gr_register.py --offices says why, exits other than 0 and writes nothing."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-offices-"))
    try:
        import people as PE
        _link_world(tmp, PE)
        reg_path = tmp / "generated" / "gr_ids.json"
        disk = reg_path.read_bytes()
        reg = GR.load_register(reg_path)
        kept = json.dumps(reg, sort_keys=True)
        got = REG.offices(reg, "2026-11-16", apply=False, root=tmp)
        offered = [c["tenure"] for _n, c in got]
        want, model = _first_offices_unlinked(BE, tmp)
        T = {t["tenure"]: t for t in model["tenure"]}
        assert sorted(offered) == want == ["officials:council.districts.1", "officials:council.districts.1.elect",
                                           "officials:council.districts.2"], (
            f"the dry run offers {offered}, and the first offices' holders the model links to no one are {want}")
        assert T["officials:us_senate.seats.0"]["person"] == "370001" \
            and T["officials:us_senate.seats.0"]["link"]["by"] == "rule", "the rule did not link the US senator"
        assert json.dumps(reg, sort_keys=True) == kept and reg_path.read_bytes() == disk, "the dry run wrote"
        work = copy.deepcopy(reg)
        done = REG.offices(work, "2026-11-16", apply=True, root=tmp)
        new_ids = [e for e in work["ids"] if e not in reg["ids"]]
        assert len(new_ids) == sum(1 for n, _c in done if n) == 3 and GR.check_register(work) == [] and sorted(
            e["issued_for"] for e in new_ids) == want, "issued ids without their places, or for other places"
        assert reg_path.read_bytes() == disk, "offices() with apply wrote the register itself; only main() writes"
        # The owner's word: she links council 1's holder, and says its successor is no one of the record.
        owner = tmp / "corrections" / "officials_links.json"
        owner.write_text(json.dumps({"_checked": "2026-11-16", "links": {
            "executive-council|1|2025|Hal Held": {"person": "376002", "evidence": "made up"},
            "executive-council|1|2027|Ida Next": {"person": None, "why": "made up: a councilor never in the House"}}}),
            encoding="utf-8")
        got = REG.offices(reg, "2026-11-16", apply=False, root=tmp)
        assert [c["tenure"] for _n, c in got] == ["officials:council.districts.1.elect",
                                                  "officials:council.districts.2"], got
        assert "a councilor never in the House" in got[0][1]["evidence"], got[0][1]["evidence"]
        owner.unlink()
        # A name two places share: the councilor of district 2 again in the US House.
        hand = json.loads((tmp / "corrections" / "officials.json").read_text(encoding="utf-8"))
        hand["us_house"]["districts"]["2"] = {"name": "Ada Newcomb", "party": "R"}
        (tmp / "corrections" / "officials.json").write_text(json.dumps(hand, ensure_ascii=False, indent=2),
                                                            encoding="utf-8")
        got = REG.offices(reg, "2026-11-16", apply=False, root=tmp)
        names = [" ".join(c["name"].split()).lower() for _n, c in got]
        shared = {n for n in names if names.count(n) > 1}
        assert shared == {"ada newcomb"} and all((new is None) == (n in shared) for (new, _c), n in zip(got, names)), (
            "an id was offered for a name two places share, or none for a name one place has")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    tmp = Path(tempfile.mkdtemp(prefix="gr-offices-"))
    try:
        import people as PE
        _world(tmp, PE)
        reg_path = tmp / "generated" / "gr_ids.json"
        disk = reg_path.read_bytes()
        try:
            BE.gr_candidates(tmp, register=GR.load_register(reg_path))
        except BE.Refused as e:
            said = str(e)
        else:
            raise AssertionError("gr_candidates offered ids on a tree that lacks the rule's evidence")
        assert "not known here" in said and "the evidence is not all here" in said, said
        r = _run([sys.executable, str(_paths.script("gr_register.py")), "--offices", "--apply"],
                 cwd=tmp, capture_output=True, text=True, timeout=300)
        assert r.returncode != 0 and "No id offered and nothing written" in (r.stderr + r.stdout) \
            and reg_path.read_bytes() == disk, f"--offices --apply without the rule's evidence: {r.returncode} {(r.stderr or r.stdout)[-300:]}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("the made-up tree's three holders the model links to no one are offered, and the senator the "
                  "rule links, the representative a member page links and the Governor the register names are "
                  "not; her link leaves a holder out and her 'no one' keeps one in; a shared name gets no id; "
                  "nothing written but by --apply's copy; without the rule's evidence nothing is offered, and "
                  "the command says so")


@check("data", "on today's files gr_register.py --offices offers an id to no first office's holder the model links to a person of the record, and to every one it links to no one",
       needs=("gr_register", "gr_ids", "build_entities"))
def _gr_offices_today(REG, GR, BE):
    """The dry run of --offices on the files here, as a person runs it before issuing: every
    holder it offers is one the model built from the same files links to no one, and every holder
    and successor of the first offices that the model links to no one, and the register has
    issued no id for, is offered (worked out here from the model's tenures). Nothing is written:
    the register on disk is the same bytes after. Skipped where the model cannot be built here (a
    bare clone has no built site) or its rule could not run (its evidence not all here)."""
    missing = [n for n in BE.NEEDED if not Path(n).is_file()]
    if missing:
        return "skip", f"the files the model is built from are not here: {', '.join(missing)}"
    reg_path = Path("generated") / "gr_ids.json"
    disk = reg_path.read_bytes() if reg_path.is_file() else None
    reg = GR.load_register(reg_path) or {"format": 1, "ids": []}
    try:
        got = REG.offices(reg, "2026-11-16", apply=False, root=".")
    except BE.Refused as e:
        return "skip", f"the model cannot say here whom it links, so nothing is offered: {e}"
    want, model = _first_offices_unlinked(BE, ".")
    T = {t["tenure"]: t for t in model["tenure"]}
    offered = [c["tenure"] for _n, c in got]
    bad = [f"{x} ({T[x]['printed']}, linked to {T[x]['person']})" for x in offered if T[x].get("person")]
    assert not bad, f"--offices offers an id to holders the model links: {bad}"
    assert sorted(offered) == want, f"--offices offers {sorted(offered)}; the model links to no one {want}"
    assert (reg_path.read_bytes() if reg_path.is_file() else None) == disk, "the dry run wrote the register"
    linked = [t for t in model["tenure"] if BE.HAND in (t.get("files") or []) and t["office"] in BE.FIRST_OFFICES
              and t.get("person")]
    return "ok", (f"{len(offered)} first-office holders offered an id, each one the model links to no one; "
                  f"{len(linked)} it links left out (" + ", ".join(t["printed"] for t in linked) + ")")


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


# ---- the one table of parties (src/lib/state_settings.json "parties"; the design's step 3) -------

@check("build", "the state's one table of parties gives each party one letter, words and colours, reads every form the files print, and the model reads its parties by it",
       needs=("build_entities", "entities", "people", "state_settings"))
def _party_table(BE, EN, PE, ST):
    """The table (src/lib/state_settings.json "parties"), read by state_settings.party_letters
    and by the model through entities.party_letters. Held: its letters are single capitals, in
    its order once each, and none is the letter drawn where no party is on file; no form -- a
    spelling, a word -- stands for two letters; parties that share a stylesheet variable give it
    the same values. Every party the files print reads as the letters it stands for ("REP/DEM"
    is R and D, "d/r" D and R, "Republican" R) and a form the table does not know ("sgi", "u/d")
    as nothing, never as part of it. And on a made-up tree (_world) with one holder of a party
    printed in a form the table does not know: the model gives every tenure and candidacy whose
    party it reads the letters it stands for (the roster's "Republican" R, the members-elect's
    "R/D" R and D, the county roster's "REP" R), gives that holder none and says the form in its
    manifest; its rules catch a tenure whose letters are not its party's; and a sitting member
    whose roster and careers.json parties stand for different letters is a disagreement, and
    "Republican" against "r" is not."""
    t = ST.PARTIES
    letters = t["letters"]
    assert list(t["order"]) == list(letters) and all(re.fullmatch(r"[A-Z]", x) for x in letters), (
        f"the table's order {t['order']} is not its letters {list(letters)}, or a letter is not one capital")
    assert ST.PARTY_NONE.get("letter") and ST.PARTY_NONE["letter"] not in letters, ST.PARTY_NONE
    seen = {}
    for x, row in letters.items():
        for form in [x, *(row.get("spellings") or []), *(row.get(k) for k in ("name", "plural", "adjective",
                                                                               "party_name"))]:
            if form:
                assert seen.setdefault(str(form).lower(), x) == x, f"{form!r} stands for {seen[str(form).lower()]} and {x}"
    shades = {}
    for x, row in letters.items():
        c = row.get("colour") or {}
        for part in ("ink", "soft"):
            if c.get(part):
                got = {theme: (c.get(theme) or {}).get(part) for theme in ("light", "dark")}
                assert shades.setdefault(c[part], got) == got, f"{x} gives {c[part]} {got}, another party {shades[c[part]]}"
    for printed, want in (("r", ("R",)), ("Republican", ("R",)), ("REP/DEM", ("R", "D")), ("d/r", ("D", "R")),
                          ("r&d&l", ("R", "D", "L")), ("Democratic Party", ("D",)), ("I/D", ("I", "D")),
                          ("ind", ("I",)), ("", ()), ("sgi", None), ("u/d", None), ("UND", None)):
        assert ST.party_letters(printed) == want == EN.party_letters(printed), (
            f"{printed!r} reads as {ST.party_letters(printed)} (the model: {EN.party_letters(printed)}), not {want}")
    tmp = Path(tempfile.mkdtemp(prefix="gr-parties-"))
    try:
        _world(tmp, PE)
        hand = json.loads((tmp / "corrections" / "officials.json").read_text(encoding="utf-8"))
        hand["treasurer"] = {"office": "State Treasurer", "name": "Pat Purse", "party": "sgi"}
        (tmp / "corrections" / "officials.json").write_text(json.dumps(hand, ensure_ascii=False, indent=2),
                                                            encoding="utf-8")
        model, layouts, report = BE.build(tmp)
        assert not report["problems"], report["problems"][:3]
        T = {x["tenure"]: x for x in model["tenure"]}
        X = {x["candidacy"]: x for x in model["candidacy"]}
        for kind, recs in (("tenure", model["tenure"]), ("candidacy", model["candidacy"])):
            for r in recs:
                want = ST.party_letters(r["party"]) if r.get("party") else None
                assert r.get("parties") == (list(want) if want else None), (kind, r[kind], r.get("party"), r.get("parties"))
        ada = T["house:2025-2026:376001"]
        assert ada["party"] == "Republican" and ada["parties"] == ["R"] and ada.get("sitting"), ada
        assert X["2026-11-03.general.house.carroll-1.flo-back-r-d"]["parties"] == ["R", "D"]
        assert [x["parties"] for x in model["tenure"] if x["tenure"].startswith("county-roster:")] == [["R"]]
        assert "parties" not in T["officials:treasurer"] and report["parties"]["unread"] == {
            "sgi": ["officials:treasurer"]} and report["parties"]["read"]["R/D"] == "R/D", report["parties"]
        m = copy.deepcopy(model)
        next(x for x in m["tenure"] if x.get("party") == "Republican")["parties"] = ["D"]
        said = EN.problems(m)
        assert any("which the table reads as ['R'], and its parties are ['D']" in s for s in said), said[:3]
        persons = model["person"]
        sitting = [x for x in model["tenure"] if x.get("sitting") and x.get("gc_employee_number") == "376001"]
        assert sitting and BE.roster_party_disagreements(sitting, persons, ST.SETTINGS) == [], (
            "the roster's Republican and careers.json's R were read as two parties")
        p = next(x for x in persons if "376001" in (x.get("gc_roster") or {}))
        p["gc_roster"]["376001"]["party"] = "d"
        assert len(BE.roster_party_disagreements(sitting, persons, ST.SETTINGS)) == 1, (
            "a Republican on the roster whom careers.json calls d is no disagreement")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", (f"{len(letters)} parties and the letter for none, each form one letter's and each shared colour "
                  "one value; 'REP/DEM', 'd/r' and 'Republican' read, 'sgi' and 'u/d' left unread; the model "
                  "gives every party it reads its letters and says the form it cannot, its rules catch a wrong "
                  "letter, and the roster's party is compared by the table")


# EVERY COPY OF THE PARTY TABLE IN THE CODE, 16 November 2026 (stage0-code.md counted six in
# Python and three in JavaScript; these are every one a search of the code found, 26 then).
# Each moves onto the table a reader at a time, and off this list onto _PARTY_READERS below;
# until then each says what the table says, or is in _PARTY_DIFFERS below. (file, the name it is bound to there, how it is written, what it holds):
#   py     a dict literal bound to the name anywhere in the file: {letter: word} or {form: letter}
#   say    the dicts of say() calls in the function of that name: {word: say(lang, key, English)}
#   parts  the function's rows of (count, "er-<letter>", word)
#   js     an object literal `const NAME={...}` in the file's text (a builder's script in
#          inline/ included): LETTER:"word", LETTER:tr("key","word"), LETTER:[...] or "var(--ink)"
#   words  the English the translations file gives each of the table's keys
#   css    the stylesheet's party inks and tints in each theme, and every class that draws one
_PARTY_COPIES = (
    ("src/pages/parts.py", "party_word", "say", "name, adjective, plural, none"),
    ("src/pages/build_elections.py", "chamber_block", "parts", "adjective"),
    ("src/pages/app.js", "PARTY_NAME", "js", "name"),
    ("src/pages/app.js", "PARTY_WORD", "js", "name"),
    ("src/pages/app.js", "PARTY_COLOR", "js", "ink"),
    ("src/pages/map.js", "PARTY", "js", "adjective"),
    ("src/pages/map.js", "NOUN", "js", "name, plural"),
    ("workers/follow/mail.js", "PARTY_WORDS", "js", "name, plural"),
    ("src/pages/lang/es.json", "party.*", "words", "the English of each key"),
    ("src/pages/app.css", "party classes", "css", "ink, soft"),
    ("src/pages/map.css", "party classes", "css", "ink"),
)
# WHERE A COPY SAYS OTHER THAN THE TABLE TODAY: listed, and put right in none (the task of 16
# November 2026). Exactly these differ, so that a copy that drifts further is seen, and one put
# right comes off this list.
_PARTY_DIFFERS = frozenset({
    "src/pages/build_elections.py chamber_block: X is 'other or cross-nominated', the table's X 'Party not on file'",
    "src/pages/app.css party classes: X is drawn in --ind, the table's X in --ink-2",
    "workers/follow/mail.js PARTY_WORDS: X is 'member whose party is not on file', the table's X 'Party not on file'",
    "workers/follow/mail.js PARTY_WORDS: X is 'members whose party is not on file', the table's X says no plural",
})
# A copy written in a new place: a letter bound to a party's word, or a party's word to its letter.
_PARTY_COPY_LINE = re.compile(r"""\bR["']?\s*:\s*[^\n]{0,40}?["'](?:\{n\} )?Republican|["']republican["']\s*:\s*["']R["']""")


def _js_object(text, name):
    """The text inside `const NAME={...}`, its braces balanced; None where there is none."""
    m = re.search(r"\bconst\s+" + re.escape(name) + r"\s*=\s*\{", text)
    if not m:
        return None
    i, depth, quote = m.end(), 1, None
    while depth and i < len(text):
        ch = text[i]
        if quote:
            quote = None if ch == quote and text[i - 1] != "\\" else quote
        elif ch in "\"'`":
            quote = ch
        elif ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
        i += 1
    return text[m.end():i - 1]


def _js_entries(body):
    """[(key, value text)] of an object literal's body, split at its own commas."""
    out, depth, quote, start = [], 0, None, 0
    for i, ch in enumerate(body + ","):
        if quote:
            quote = None if ch == quote and body[i - 1:i] != "\\" else quote
        elif ch in "\"'`":
            quote = ch
        elif ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
        elif ch == "," and depth == 0:
            part = body[start:i].strip()
            if part:
                k, _, v = part.partition(":")
                out.append((k.strip().strip("\"'"), v.strip()))
            start = i + 1
    return out


def _party_copy_says(ST, path, name, how, holds):
    """[(letter, form, value)] a copy says, as _PARTY_COPIES describes it; a form is name, plural,
    adjective, party_name, spelling, letter, ink, soft or key:<form> (a key of the translations
    the copy says a word through)."""
    out = []
    if how in ("py", "say", "parts"):
        tree = _parsed(_paths.ROOT / path)
    if how == "py":
        found = [ast.literal_eval(n.value) for n in ast.walk(tree) if isinstance(n, ast.Assign)
                 and isinstance(n.value, ast.Dict) and any(isinstance(x, ast.Name) and x.id == name for x in n.targets)]
        assert len(found) == 1, f"{path} binds {name} to {len(found)} dicts, not one: the copy moved or was copied"
        for k, v in found[0].items():
            out.append((v, "spelling", k) if holds == "spelling" else (k, holds, v))
    elif how == "say":
        fn = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
        assert len(fn) == 1, f"{path} has {len(fn)} functions named {name}"
        keys = {key: (x, form) for x, row in ST.PARTY.items() for form, key in (row.get("words") or {}).items()}
        keys.update({key: (ST.PARTY_NONE["letter"], form) for form, key in (ST.PARTY_NONE.get("words") or {}).items()})
        for a in ast.walk(fn[0]):
            if isinstance(a, ast.Assign) and isinstance(a.value, ast.Dict):
                for k, v in zip(a.value.keys, a.value.values):
                    if isinstance(v, ast.Call) and len(v.args) >= 3 and all(isinstance(x, ast.Constant) for x in v.args[1:3]):
                        key, english = v.args[1].value, v.args[2].value
                        x, form = keys.get(key, ("?", key))
                        out += [(x, "key:" + form, key), (x, form, english)]
                        if x != ST.PARTY_NONE["letter"]:
                            out.append((x, "spelling", str(k.value).lower()))
    elif how == "parts":
        fn = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
        assert len(fn) == 1, f"{path} has {len(fn)} functions named {name}"
        for a in ast.walk(fn[0]):
            if isinstance(a, ast.Tuple) and len(a.elts) == 3 and all(isinstance(e, ast.Constant) for e in a.elts[1:]):
                m = re.fullmatch(r"er-([A-Z])", str(a.elts[1].value))
                if m:
                    x = m.group(1)
                    out.append((x, "name" if x == ST.PARTY_NONE["letter"] else holds, a.elts[2].value))
    elif how == "js":
        body = _js_object(_source(_paths.ROOT / path), name)
        assert body is not None, f"{path} has no `const {name}={{...}}`: the copy moved or went"
        forms = [f.strip() for f in holds.split(",")]
        for k, v in _js_entries(body):
            said = re.findall(r'tr\(\s*"([^"]+)"\s*,\s*"([^"]*)"', v) or [(None, s) for s in re.findall(r'"([^"]*)"', v)]
            for form, (key, english) in zip(forms, said):
                if form == "ink":
                    english = re.sub(r"^var\((--[\w-]+)\)$", r"\1", english)
                english = re.sub(r"^\{n\} ", "", english)
                out.append((k, form, english))
                if key and key.startswith("party."):
                    out.append((k, "key:" + form, key))
    elif how == "words":
        doc = json.loads(_source(_paths.ROOT / path))["strings"]
        rows = list(ST.PARTY.items()) + [(ST.PARTY_NONE["letter"], ST.PARTY_NONE)]
        for x, row in rows:
            for form, key in (row.get("words") or {}).items():
                out.append((x, form, (doc.get(key) or {}).get("en")))
    elif how == "css":
        css = re.sub(r"/\*.*?\*/", "", _source(_paths.ROOT / path), flags=re.S)
        for sel, decls in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            letters = set(re.findall(r"\.(?:p|pt|er)-([A-Z])\b", sel))
            for x in sorted(letters):
                for var in re.findall(r"var\((--[\w-]+)\)", decls):
                    if re.fullmatch(r"--(?:rep|dem|ind)(?:-soft)?|--ink-2", var):
                        out.append((x, "soft" if var.endswith("-soft") else "ink", var))
        for x, var in re.findall(r"--fill-([A-Z]):color-mix\(in srgb,var\((--[\w-]+)\)", css):
            out.append((x, "ink", var))
    return out


def _party_table_says(ST, x, form):
    """What the table says of letter `x` in `form`, or None."""
    row = ST.PARTY_NONE if x == ST.PARTY_NONE.get("letter") else ST.PARTY.get(x)
    if row is None:
        return None
    if form.startswith("key:"):
        return (row.get("words") or {}).get(form[4:])
    if form in ("ink", "soft"):
        return (row.get("colour") or {}).get(form)
    return row.get(form)


@check("files", "every copy of the party table in the code says what the state's one table says, but those listed as differing, and no new copy has been written",
       needs=("state_settings",))
def _party_copies_agree(ST):
    """THE PARTY MAP IS WRITTEN MANY TIMES (stage0-code.md: six times in Python and three in
    JavaScript, with no check holding them together); src/lib/state_settings.json's "parties" is
    now the one table, and the copies move onto it a reader at a time (_PARTY_READERS lists those
    that have, and _party_readers_read_the_table holds them). Until each does, every copy
    _PARTY_COPIES lists -- 26 of them on 16 November, the letter-to-word maps of the pages, the
    downloads and the fetchers, the word-to-letter maps, party_word and the elections' bar, the scripts' maps of
    words, inks and counts, the follow emails', the translations' English, and the stylesheets'
    inks and tints -- is read where it is, and each thing it says of a party is
    held to the table: the word, plural, adjective and party's own name, a spelling and the letter
    it stands for, the key a word is said through, the ink or tint a class draws it in, and the
    stylesheet's values for each in the light theme (and print) and the dark. What differs today
    is _PARTY_DIFFERS, put right in none: the elections' bar and its X (other or cross-nominated,
    drawn in the Independent's ink) where the table's X is 'Party not on file'; and the follow
    emails' own words for it. Exactly those differ (the first-letter rules, which took a U no
    table holds, read the table since 20 November 2026: _PARTY_READERS). And no copy is written
    where the list does not know one: a line binding R to a Republican word, or the word to R, in any code file, the workers' and the Functions' too,
    outside the suite and the tests, is one of the listed copies."""
    differs, said = set(), {}
    for path, name, how, holds in _PARTY_COPIES:
        label = f"{path} {name}"
        says = _party_copy_says(ST, path, name, how, holds)
        assert says, f"{label} says nothing of a party: the copy moved or went"
        said[label] = says
        look = ST.party_lookup()
        for x, form, value in says:
            if form == "letter":
                if x not in ST.PARTY and x != ST.PARTY_NONE.get("letter"):
                    differs.add(f"{label}: {x}, a letter the table does not hold")
                continue
            if form == "spelling":
                if look.get(str(value).lower()) != x:
                    differs.add(f"{label}: {value!r} stands for {x}, and the table reads it as {look.get(str(value).lower())}")
                continue
            want = _party_table_says(ST, x, form)
            if value != want and form in ("ink", "soft"):
                differs.add(f"{label}: {x} is drawn in {value}, the table's {x} in {want}")
            elif value != want:
                differs.add(f"{label}: {x} is {value!r}, the table's {x} {want!r}" if want is not None else
                            f"{label}: {x} is {value!r}, the table's {x} says no {form}")
    # The stylesheet's values for each ink and tint, theme by theme: the light (and print) and the
    # dark are the table's, and every block of them is one or the other.
    css = re.sub(r"/\*.*?\*/", "", _source(_paths.ROOT / "src/pages/app.css"), flags=re.S)
    want = {}
    for x, row in ST.PARTY.items():
        c = row.get("colour") or {}
        for part in ("ink", "soft"):
            if c.get(part):
                want[c[part]] = {theme: (c.get(theme) or {}).get(part) for theme in ("light", "dark")}
    blocks, cur = [], {}
    for var, value in re.findall(r"(--(?:rep|dem|ind)(?:-soft)?):(#[0-9A-Fa-f]{6})", css):
        if var in cur:
            blocks.append(cur)
            cur = {}
        cur[var] = value.upper()
    blocks.append(cur)
    themes = []
    for b in blocks:
        hit = [theme for theme in ("light", "dark") if all(want.get(v, {}).get(theme, "").upper() == value
                                                           for v, value in b.items())]
        assert hit and set(b) == set(want), f"app.css gives the party colours {b}, which are neither theme of the table's"
        themes.append(hit[0])
    assert themes[0] == "light" and "dark" in themes, f"app.css's party colours run {themes}"
    assert differs == _PARTY_DIFFERS, (
        "copies of the party table differ from it otherwise than listed: "
        + "; ".join(sorted(differs - _PARTY_DIFFERS)[:8])
        + ("; and these listed differences are gone (take them off _PARTY_DIFFERS): "
           + "; ".join(sorted(_PARTY_DIFFERS - differs)) if _PARTY_DIFFERS - differs else ""))
    # No copy the list does not know.
    expected = {}
    for path, name, how, holds in _PARTY_COPIES:
        if how in ("py", "js") and any(
                (form != "spelling" and x == "R" and isinstance(v, str) and "Republican" in v)
                or (form == "spelling" and x == "R" and str(v).lower() == "republican")
                for x, form, v in said[f"{path} {name}"]):
            expected[path] = expected.get(path, 0) + 1
    found = {}
    import inline_js as IJ
    # The builders' own scripts too, in inline/ since 20 November 2026.
    files = [f for f in list(_paths.code_files("*.py")) + list(_paths.code_files("*.js"))
             + sorted(IJ.files().values())
             + sorted((_paths.ROOT / "workers").rglob("*.js")) + sorted((_paths.ROOT / "functions").rglob("*.js"))
             if not _in_suite(f) and "tests" not in f.relative_to(_paths.ROOT).parts
             and "node_modules" not in f.parts]
    for f in files:
        n = len(_PARTY_COPY_LINE.findall(_source(f, errors="replace")))
        if n:
            found[f.relative_to(_paths.ROOT).as_posix()] = n
    assert found == expected, (
        "a copy of the party table the list does not know: "
        + ", ".join(f"{p} ({found.get(p, 0)} found, {expected.get(p, 0)} listed)"
                    for p in sorted(set(found) | set(expected)) if found.get(p, 0) != expected.get(p, 0))
        + ". Read state_settings.PARTY instead, or add it to _PARTY_COPIES")
    langs = {how for _p, _n, how, _h in _PARTY_COPIES}
    return "ok", (f"{len(_PARTY_COPIES)} copies ({len(langs)} ways of writing one) say what the table says but "
                  f"the {len(_PARTY_DIFFERS)} listed: the elections' bar and the emails' X and its ink; "
                  "app.css's inks and tints are the table's in both themes; no copy written anywhere the "
                  "list does not know")


# THE READERS THAT MOVED ONTO THE TABLE (the design's step 3, 19 November 2026). Each kept its own
# copy of the party table until then and is off _PARTY_COPIES now: (file, the name, the table's
# view it is bound to, that view's arguments). Each name is bound once, to that call of
# state_settings, and never written to after, so the table is the one source of what it says.
_PARTY_READERS = (
    ("src/pages/build_session_pages.py", "PARTY_WORD", "party_words", ("name",)),
    ("src/pages/build_site_v2.py", "PARTY_FULL", "party_words", ("name",)),
    ("src/pages/officials_tabs.py", "PARTY_OF", "party_words", ("name",)),
    ("src/pages/structured.py", "PARTY_NAME", "party_words", ("party_name",)),
    ("src/parse/build_data.py", "PARTY", "party_words", ("name",)),
    ("src/fetch/gc_db/fetch_members_db.py", "PARTY", "party_words", ("name",)),
    ("src/fetch/gc_db/fetch_committee_members_db.py", "PARTY", "party_words", ("name",)),
    ("src/pages/build_session_pages.py", "PARTY_LETTER", "party_lookup", ()),
    ("src/fetch/gc_web/fetch_rollcall_parties.py", "PARTY", "party_lookup", ()),
    ("src/pages/sponsors.py", "MANUAL_PARTY", "party_lookup", ()),
    ("src/parse/office_links.py", "PARTY_WORDS", "party_lookup", ()),
    ("src/pages/members.py", "PARTY_INITIALS", "party_initials", ()),
    ("src/parse/names.py", "PARTY_INITIALS", "party_initials", ()),
    ("src/parse/past_sponsors.py", "PARTY_INITIALS", "party_initials", ()),
)
# THE FIRST-LETTER RULES among them (20 November 2026): a label's party letter, a name's party
# tail, a ballot's party, kept where it is one of the letters the table has a word for. Until then
# each wrote "RDILU" in the file, a U no table holds and no file prints. Each rule's letters are
# PARTY_INITIALS, and no string in the file writes a run of the table's letters of its own.
_PARTY_RULES = ("src/pages/sponsors.py", "src/pages/members.py", "src/parse/names.py",
                "src/parse/past_sponsors.py")


def _party_rule_literals(tree, letters):
    """[(line, the string)] of the string constants in a parsed file that write `letters` (the
    table's, "RDIL") in a run of their own, as a first-letter rule once did ("RDILU", "[RDILU]")."""
    run = re.compile(r"[A-Z]*" + "".join(re.escape(x) for x in letters) + r"[A-Z]*")
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and letters and run.search(n.value)]


def _party_reader_faults(tree, name, fn, args):
    """What is wrong with `name`'s reading of the table in a parsed file: [] where the name is
    bound once, to ST.<fn>(*args), and never written to after (an item set, an update, a
    setdefault, a pop, a del); else the faults, in words."""
    faults, binds = [], []
    for n in ast.walk(tree):
        targets = (n.targets if isinstance(n, ast.Assign) else [n.target] if isinstance(n, (ast.AnnAssign, ast.AugAssign))
                   else n.targets if isinstance(n, ast.Delete) else [])
        for t in targets:
            if isinstance(t, ast.Name) and t.id == name:
                binds.append(n)
            elif isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == name:
                faults.append(f"line {n.lineno} writes into {name}")
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                and n.func.value.id == name and n.func.attr in ("update", "setdefault", "pop", "popitem", "clear")):
            faults.append(f"line {n.lineno} changes {name} ({n.func.attr})")
    if len(binds) != 1:
        faults.append(f"{name} is bound {len(binds)} times, not once")
    for b in binds:
        v = getattr(b, "value", None)
        ok = (isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and isinstance(v.func.value, ast.Name)
              and v.func.value.id == "ST" and v.func.attr == fn and not v.keywords
              and [a.value if isinstance(a, ast.Constant) else a for a in v.args] == list(args))
        if not ok:
            said = ast.unparse(v) if v is not None else type(b).__name__
            faults.append(f"line {b.lineno} binds {name} to {said[:60]}, not ST.{fn}({', '.join(map(repr, args))})")
    return faults


@check("files", "the readers that kept their own copy of the party table read the state's one table instead, and nothing else",
       needs=("state_settings",))
def _party_readers_read_the_table(ST):
    """THE PARTY TABLE IS READ, NOT COPIED (the design's step 3). The copies _PARTY_READERS names
    were dicts of their own until 19 November 2026; each is now bound to the table's view of it
    (state_settings.party_words, party_lookup), which gave the very dict the copy held, so the site
    did not change by a byte; and the three first-letter rules (_PARTY_RULES), which wrote "RDILU"
    until 20 November 2026, read state_settings.party_initials, the U dropped being a letter no
    file prints. Held: each name in its file is bound once, to that call, and never written into
    after; each rule reads its PARTY_INITIALS and writes no run of the letters of its own, and
    keeps R, L and an "(r)" tail and drops a U; and the views read the table they are given, so a
    reader follows the table and nothing else. Planted, each must be refused: the dict written back in place of the
    call, a second view, an item set into it, a view of another form; and a table whose
    Republican is planted under another word is read under that word."""
    for path, name, fn, args in _PARTY_READERS:
        faults = _party_reader_faults(_parsed(_paths.ROOT / path), name, fn, args)
        assert not faults, f"{path}: " + "; ".join(faults)
    # The first-letter rules take their letters from PARTY_INITIALS, and write none of their own.
    letters = ST.party_initials()
    assert letters == "".join(ST.party_words("name")) and letters, f"the table's initials are {letters!r}"
    for path in _PARTY_RULES:
        tree = _parsed(_paths.ROOT / path)
        own = _party_rule_literals(tree, letters)
        assert not own, f"{path} writes the party letters itself: " + "; ".join(f"line {n}: {s!r}" for n, s in own[:3])
        used = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "PARTY_INITIALS"
                and isinstance(n.ctx, ast.Load)]
        assert used, f"{path} binds PARTY_INITIALS and its rule does not read it"
    for planted in ('p = pc if pc in "RDILU" else ""\n', 'R = re.compile(r"\\([RDILU]\\)")\n',
                    'p = pc if pc in "RDIL" else ""\n'):
        assert _party_rule_literals(ast.parse(planted), letters), f"a rule writing its own letters was missed: {planted!r}"
    assert not _party_rule_literals(ast.parse('x = "Rep. Jodi Nelson (R - Rock 13)"\n'), letters)
    import build_site_v2 as B2
    import names as NM
    for s, want in (("Howard Pearl (r)", "Howard Pearl"), ("Nelson, Jodi(R) Rock. 13", "Jodi Nelson"),
                    ("Rep. Ann Lib (l - Graf 1)", "Ann Lib")):
        assert B2.person_name(s) == want, f"person_name({s!r}) is {B2.person_name(s)!r}, not {want!r}"
    kept = [B2.party_letter(x) for x in ("Republican", "l", "U", "C", "X", "")]
    assert kept == ["R", "L", "", "", "", ""], f"party_letter keeps {kept}"
    said = [NM.legislator({"name": "Doe, Jane", "chamber": "S", "party": p, "district": "4"}) for p in ("r", "u")]
    assert said == ["Sen. Jane Doe (R - SD4)", "Sen. Jane Doe (SD4)"], f"names.legislator says {said}"
    good = 'import state_settings as ST\nPARTY = ST.party_words("name")\nx = PARTY.get("R")\n'
    assert _party_reader_faults(ast.parse(good), "PARTY", "party_words", ("name",)) == []
    for planted in ('PARTY = {"R": "Republican", "D": "Democrat"}\n',
                    'PARTY = ST.party_words("name")\nPARTY = ST.party_words("name")\n',
                    'PARTY = ST.party_words("name")\nPARTY["R"] = "Grand Old Party"\n',
                    'PARTY = ST.party_words("name")\nPARTY.update(R="Grand Old Party")\n',
                    'PARTY = ST.party_words("plural")\n'):
        assert _party_reader_faults(ast.parse(planted), "PARTY", "party_words", ("name",)), (
            f"a planted copy was taken for a reader of the table: {planted!r}")
    table = copy.deepcopy(ST.PARTIES)
    table["letters"]["R"]["name"] = "Planted"
    table["letters"]["R"]["spellings"].append("planted")
    assert ST.party_words("name", table)["R"] == "Planted" and ST.party_lookup(table)["planted"] == "R", (
        "the table's views did not read the table they were given")
    assert ST.party_words("name") == {x: row["name"] for x, row in ST.PARTY.items() if row.get("name")}
    table["letters"]["C"]["name"] = "Constitution"
    assert ST.party_initials(table) == letters + "C", "the initials did not read the table they were given"
    return "ok", (f"{len(_PARTY_READERS)} readers bound once each to the table's view and never written into; "
                  f"the {len(_PARTY_RULES)} first-letter rules keep the table's {letters} and write no letters "
                  "of their own (a U is no party); five planted copies and three planted rules refused, and a "
                  "planted table read as planted")


# A NAME AS AN ADDRESS HAS ONE HOME (the refactor's finding 8, 20 November 2026): slugs.slug, and
# slugs.town_slug for a town's page key (src/lib/slugs.py, which the model takes slug from too). The copies that were only the rule are bound to it by
# import, by the name they had (file, that name, slugs' name); every other reader calls
# slugs.slug where it wrote the rule out. Each gave the same answer as the home on all 26,340
# real strings, 591 town-ward pairs and 2,563 member records it was run on.
_SLUG_READERS = (
    ("src/towns/parse_clerks_csv.py", "slug", "slug"),
    ("src/towns/build_places.py", "slug", "slug"),
    ("src/pages/build_district_map.py", "slug", "slug"),
    ("src/pages/build_feeds.py", "slug", "slug"),
    ("src/fetch/other/fetch_town_clerks.py", "slug", "town_slug"),
    ("src/pages/build_town_pages.py", "slug", "town_slug"),
)
# The rule written out, which only the home and these may write: each is another rule, said here.
_SLUG_OTHERS = {
    "src/ops/state_sources.py": "a source file's stem, not lowered and cut to 48 letters",
}
_SLUG_WRITTEN = re.compile(r"""\[\^a-z0-9\]\+['"]\s*,\s*['"]-['"]""")


def _slug_reader_faults(tree, name, home):
    """What is wrong with `name`'s binding to slugs.<home> in a parsed file; [] where none."""
    took = [n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == "slugs"
            and any(a.name == home and (a.asname or a.name) == name for a in n.names)]
    again = [n.lineno for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.Assign))
             and (getattr(n, "name", None) == name or any(isinstance(t, ast.Name) and t.id == name
                                                          for t in getattr(n, "targets", [])))
             and n.col_offset == 0]
    return ([] if took else [f"no `from slugs import {home}` binds {name}"]) + \
           [f"line {n} binds {name} again" for n in again]


@check("files", "a name is made an address by slugs.slug alone, and a town's page key by slugs.town_slug: "
                "the copies are bound to them and the rule is written out nowhere else")
def _slug_one_home():
    """A NAME AS AN ADDRESS, ONE HOME (finding 8 of stage0-code.md, "slug x6"). Lower case, letters
    and digits, one hyphen between: written out in fourteen files until 20 November 2026, and a town
    with its ward in two more; slugs.slug and slugs.town_slug now (src/lib/slugs.py, not the
    model's module: a module importing entities reads the model). Held: each copy
    _SLUG_READERS names is bound to the home by import and bound nowhere else in its file; no code
    file outside the suite and the tests writes the rule out (`re.sub(r"[^a-z0-9]+", "-", ...)`) but
    the home and _SLUG_OTHERS, each another rule said there; and the home's answers. A reader that
    folds accents first (election_town_rows, build_civics, a member's address in
    build_legislator_pages) folds and then calls the home, and parse_clerks keeps its own ward rule
    (a ward's leading zeros dropped) around it. Planted, each must be refused: the copy written back,
    a second binding, the rule inline."""
    import entities as EN
    import slugs as SL
    for path, name, home in _SLUG_READERS:
        faults = _slug_reader_faults(_parsed(_paths.ROOT / path), name, home)
        assert not faults, f"{path}: " + "; ".join(faults) + f" (read slugs.{home})"
    stray = []
    for f in _paths.code_files("*.py"):
        rel = f.relative_to(_paths.ROOT).as_posix()
        if _in_suite(f) or "tests" in f.relative_to(_paths.ROOT).parts or rel in _SLUG_OTHERS \
                or rel == "src/lib/slugs.py":
            continue
        stray += [f"{rel}:{i}" for i, line in enumerate(_source(f, errors="replace").splitlines(), 1)
                  if _SLUG_WRITTEN.search(line)]
    assert not stray, ("the slug rule written out again: " + ", ".join(stray[:8])
                       + ". Call slugs.slug, or say in _SLUG_OTHERS why it is another rule")
    for path in _SLUG_OTHERS:
        assert any(_SLUG_WRITTEN.search(l) for l in _source(_paths.ROOT / path).splitlines()), \
            f"{path} no longer writes its own: take it off _SLUG_OTHERS"
    said = [SL.slug(x) for x in ("Bean's Grant", "Kelly Ayotte", "r/d", "  Hart's Location ", None, "Wentworth's Loc.")]
    assert said == ["bean-s-grant", "kelly-ayotte", "r-d", "hart-s-location", "", "wentworth-s-loc"], said
    said = [SL.town_slug(t, w) for t, w in (("Manchester", "3"), ("Bean's Grant", "0"), ("Acworth", ""), ("Nashua", 9))]
    assert said == ["manchester-ward-3", "bean-s-grant", "acworth", "nashua-ward-9"], said
    assert EN.slug is SL.slug, "entities writes a slug of its own: it takes slugs.slug"
    for planted, name, home in (
            ('def slug(s):\n    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")\n', "slug", "slug"),
            ('from slugs import slug\ndef slug(s):\n    return s\n', "slug", "slug"),
            ('from slugs import slug\nslug = str.lower\n', "slug", "slug"),
            ('from slugs import slug\n', "slug", "town_slug")):
        assert _slug_reader_faults(ast.parse(planted), name, home), f"a copy of the slug rule was missed: {planted!r}"
    assert not _slug_reader_faults(ast.parse("from slugs import town_slug as slug\n"), "slug", "town_slug")
    for line in ('s = re.sub(r"[^a-z0-9]+", "-", town.lower()).strip("-")', "k = re.sub(r'[^a-z0-9]+', '-', t)"):
        assert _SLUG_WRITTEN.search(line), f"an inline copy was missed: {line}"
    assert not _SLUG_WRITTEN.search('re.sub(r"[^a-z0-9]+", " ", s)') and not _SLUG_WRITTEN.search('re.sub(r"[^a-z0-9]+", "_", s)')
    return "ok", (f"{len(_SLUG_READERS)} copies bound to slugs.slug and town_slug (entities' slug the same one), the rule written out "
                  f"nowhere else but {len(_SLUG_OTHERS)} other rule (state_sources' stem); the home's answers "
                  "held, and each planted copy refused")


# THE WORDS AFTER A NAME HAVE ONE HOME (the refactor's finding 8, 20 November 2026): names.SUFFIXES,
# a Jr., a Sr. and the numerals II to IV, lower case. Each of these wrote the list out until then
# and binds the home now, by the name it had (file, that name; None where the list was written
# inline and the test reads NM.SUFFIXES itself). Every read of each is a membership test, so the
# home being a frozenset where a copy was a set or a tuple changes no answer.
_SUFFIX_READERS = (
    ("src/ops/state_sources.py", "SUFFIXES"),
    ("src/parse/text_sponsors.py", "SUFFIXES"),
    ("src/pages/build_lsrs.py", "_SUFFIX"),
    ("src/pages/members.py", "_SUFFIX"),
    ("src/parse/past_roll.py", "SFX"),
    ("src/towns/town_boards.py", "SUFFIX"),
    ("src/ops/election_week.py", None),
    ("src/parse/parse_sos_offices.py", None),
    ("src/parse/officers.py", None),
)


def _suffix_literals(tree, words):
    """[line] of the sets, tuples, lists and frozensets of string constants in a parsed file that
    hold exactly `words`, ignoring case: the list written out again."""
    out = []
    for n in ast.walk(tree):
        elts = n.elts if isinstance(n, (ast.Set, ast.Tuple, ast.List)) else None
        if elts and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in elts) \
                and {e.value.lower() for e in elts} == set(words):
            out.append(n.lineno)
    return out


def _suffix_reader_faults(tree, name):
    """What is wrong with a reader's reading of names.SUFFIXES in a parsed file; [] where none."""
    home = "NM.SUFFIXES"
    if name is None:
        reads = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and ast.unparse(n) == home]
    else:
        binds = [n for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
        if len(binds) != 1 or ast.unparse(binds[0].value) != home:
            return [f"{name} is bound {len(binds)} times" + (f", to {ast.unparse(binds[0].value)}" if binds else "")
                    + f", not once to {home}"]
        reads = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load)]
    member = {id(c) for n in ast.walk(tree) if isinstance(n, ast.Compare)
              for op, c in zip(n.ops, n.comparators) if isinstance(op, (ast.In, ast.NotIn))}
    imported = any(isinstance(n, ast.Import) and any(a.name == "names" and a.asname == "NM" for a in n.names)
                   for n in tree.body)
    return ([] if imported else ["no `import names as NM`"]) + ([] if reads else [f"nothing reads {home}"]) + \
        [f"line {n.lineno} reads {name or home} otherwise than as `x in ...`" for n in reads if id(n) not in member]


@check("files", "a name's Jr., Sr. and numerals are names.SUFFIXES alone: each list that was written out "
                "reads it, and none is written again", needs=("names",))
def _name_suffixes_one_home(NM):
    """THE WORDS AFTER A NAME, ONE HOME (finding 8 of stage0-code.md, "suffix x7"). jr, sr, ii,
    iii and iv were written out as a list of their own in eight modules until 20 November 2026;
    names.SUFFIXES now. Held: each reader _SUFFIX_READERS names binds it once by its old name
    (or tests NM.SUFFIXES where the list was inline), and reads it only as `x in ...`, so a set or a
    tuple become a frozenset answers the same; no code file outside the suite and the tests writes
    the same five words as a list again. The longer lists are other rules and stay where they are:
    the Manuals' "2nd" and "3rd" (build_manual_seats, unh_measure), sponsor_roster's "v" and stops,
    parse_clerks' capitals and "V", and the patterns that read a suffix in place. Planted, each
    must be refused: the list written back, a second binding, a read that is not a test."""
    words = NM.SUFFIXES
    assert isinstance(words, frozenset) and words == {"jr", "sr", "ii", "iii", "iv"}, f"names.SUFFIXES is {words!r}"
    for path, name in _SUFFIX_READERS:
        faults = _suffix_reader_faults(_parsed(_paths.ROOT / path), name)
        assert not faults, f"{path}: " + "; ".join(faults) + " (read names.SUFFIXES)"
    stray = []
    for f in _paths.code_files("*.py"):
        rel = f.relative_to(_paths.ROOT).as_posix()
        if _in_suite(f) or "tests" in f.relative_to(_paths.ROOT).parts or rel == "src/parse/names.py":
            continue
        stray += [f"{rel}:{n}" for n in _suffix_literals(_parsed(f), words)]
    assert not stray, ("the name suffixes written out again: " + ", ".join(stray[:8])
                       + ". Read names.SUFFIXES")
    imp = "import names as NM\n"
    for planted, name in ((imp + 'SFX = {"jr", "sr", "ii", "iii", "iv"}\n', "SFX"),
                          (imp + "SFX = NM.SUFFIXES\nSFX = NM.SUFFIXES\n", "SFX"),
                          (imp + "SFX = NM.SUFFIXES\nx = sorted(SFX)\n", "SFX"),
                          ("SFX = NM.SUFFIXES\nx = 'jr' in SFX\n", "SFX"),
                          (imp + "x = '|'.join(NM.SUFFIXES)\n", None)):
        assert _suffix_reader_faults(ast.parse(planted), name), f"a copy of the suffixes was missed: {planted!r}"
    assert not _suffix_reader_faults(ast.parse(imp + "SFX = NM.SUFFIXES\nx = [w for w in y if w not in SFX]\n"), "SFX")
    assert _suffix_literals(ast.parse('x = w in ("JR", "SR", "II", "III", "IV")\n'), words) == [1]
    assert not _suffix_literals(ast.parse('S = {"jr", "sr", "ii", "iii", "iv", "2nd", "3rd"}\n'), words)
    return "ok", (f"{len(_SUFFIX_READERS)} readers take names.SUFFIXES, each read a membership test; the "
                  "five words written as a list nowhere else; each planted copy refused")


# ---- the one district table, with its eras and every spelling (the design's step 4) --------------

def _district_tree(root, BE, EN, PE, model):
    """_world's tree with the files the site prints districts from beside it, each true to the
    tracked district lists (`model`, their districts and places) but for one fault apiece: a town
    search placing Conway in Carroll 2 and Albany in a Senate district 99; a 2026 result giving
    Carroll 1 two seats and a town more, and Belknap 8 as not floterial; the map drawing Carroll 1
    on the floterial layer; a former member of 2023-2024 whose label and page address name two
    districts; a sitting member the site data gives another district than the roster does; and,
    of a term before every era on file, a 2020 result, a 2019-2020 sponsor and two former members
    whose service the file gives no term of or a term of 2019-2020, which are counted and resolve
    to nothing."""
    root = Path(root)
    _world(root, PE)
    conway = next(p for p in model["place"] if p["place"] == "conway|0")
    D = {d["district"]: d for d in model["district"]}
    of = {D[x]["kind"]: D[x] for x in conway["in"]["2022"]}
    sd, ec, cd = of["senate"]["number"], of["council"]["number"], of["congress"]["number"]
    put = lambda rel, doc: ((root / rel).parent.mkdir(parents=True, exist_ok=True),
                            (root / rel).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8"))
    (root / "site" / "districts.json").write_text(json.dumps(EN.view_districts(model, "2022"), indent=2,
                                                             sort_keys=True), encoding="utf-8")
    put("site/places.json", {"places": [
        {"s": "conway", "n": "Conway", "t": "Conway", "h": [["Carroll", 1, 0], ["Carroll", 2, 0]], "sd": sd,
         "ec": ec, "cd": cd, "m": ["ada-newcomb-carr-1"], "e": ["H|Carroll|1", f"S|{sd}"]},
        {"s": "albany", "n": "Albany", "t": "Albany", "h": [], "sd": 99, "m": [], "e": []}],
        "people": {"ada-newcomb-carr-1": ["Rep. Ada Newcomb (R - Carr 1)", "R"],
                   "cy-lund-sd-15": ["Sen. Cy Lund (R - SD15)", "R"]},
        "offices": {"ec": {str(ec): ["Hal Held", "R", ""]}, "cd": {str(cd): ["Cy Lund", "R", ""]}},
        "elect": {"election": "2026-11-03", "races": {"H|Carroll|1": {"seats": 3}}}})
    c1 = D["house:2022:carroll-1"]
    put("site/district_map.json", {
        "layers": {"base": {"f": {"CA1": {}, "BE1": {}}}, "float": {"f": {"BE8": {}, "CA1": {}}},
                   "senate": {"f": {str(sd): {}}}, "exec": {"f": {str(ec): {}}}, "cong": {"f": {str(cd): {}}}},
        "seats": {"CA1": c1["seats"], "BE1": D["house:2022:belknap-1"]["seats"], "BE8": D["house:2022:belknap-8"]["seats"]},
        "who": {"base|CA1": [{"n": "Rep. Ada Newcomb (R - Carr 1)"}]},
        "elect": {"election": "2026-11-03", "races": {"base|CA1": {"seats": c1["seats"]}}},
        "places": {"Conway": {"c": "Carroll", "w": {"0": ["CA1", None, str(sd), str(ec), str(cd)]}}}})
    towns = sorted({BE._town_ward(p) for p in model["place"] if p["place"] in c1["places"]})
    put("collected/election_2026.json", {"election": "2026-11-03", "term": "2027-2028", "races": {
        "H|Carroll|1": {"seats": 2, "floterial": False, "towns": towns + ["Madison"]},
        "H|Belknap|8": {"seats": D["house:2022:belknap-8"]["seats"], "floterial": False,
                        "towns": sorted({BE._town_ward(p) for p in model["place"]
                                         if p["place"] in D["house:2022:belknap-8"]["places"]})}}})
    put("collected/election_2020.json", {"election": "2020-11-03", "term": "2021-2022", "races": {
        "H|Carroll|9": {"seats": 1, "floterial": False, "towns": ["Nowhere"]}}})
    put("data/sponsors.json", {"2025-2026": {"HB1": [
        {"member_id": "11600", "chamber": "H", "label": "Rep. Ada Newcomb (R - Carr 1)"},
        {"member_id": "11700", "chamber": "S", "label": "Sen. Cy Lund (R - SD15)"}]},
        "2019-2020": {"HB2": [{"member_id": "1", "chamber": "H", "label": "Rep. Old Timer (D - Carr 9)"}]}})
    put("data/legislators.json", [{"id": "11600", "chamber": "H", "county_code": "02", "district": "1"},
                                  {"id": "11800", "chamber": "H", "county_code": "02", "district": "2"}])
    former = json.loads((root / "site" / "former.json").read_text(encoding="utf-8"))
    former += [{"id": "376040", "name": "Two, Way", "chamber": "H", "county": "Carroll", "district": "2",
                "district_label": "Carr 2", "slug": "way-two-carr-3", "served": {"terms": ["2023-2024"]}},
               {"id": "376041", "name": "Back, Then", "chamber": "H", "county": "Carroll", "district": "9",
                "district_label": "Carr 9", "slug": "then-back-carr-9", "served": {"terms": ["2019-2020"]}}]
    put("site/former.json", former)


@check("build", "the district table gives each district one id with its era in it and resolves every spelling the files use to it, and the step says each district the site prints that resolves to nothing or disagrees",
       needs=("build_entities", "entities", "people", "state_settings"))
def _district_table(BE, EN, PE, ST):
    """The design's step 4. A district's six spellings -- the results' H|Belknap|8, the elections'
    belknap-8, the map's BE8, the name Belknap 8, the roster's Belk 8 and the General Court's
    county code with a number, 01-8 -- and a page address's belk-8 are one id with its era in it,
    house:2022:belknap-8; the Senate's S|22, SD22, sd-22, Senate District 22 and 22 are
    senate:2022:22. Held on the tracked district lists (records/districts/): every district has the
    spellings of its kind, each resolves to it in its era and in none other (a term before every
    era on file reads as no district, never as today's of that number), and so do the forms the
    files print them in -- a full stop ("Belk. 8"), a padded number ("Carr 07", "H|Carroll|07",
    "01-08"), any case; no spelling names two districts, and a model where one does breaks a rule;
    the settings give every county the General Court's two-digit number, each once. And on a
    made-up tree with every file the site prints districts from (_district_tree), the step exits 0,
    writes only data/entities/, and its manifest resolves each spelling in the era of the term it is
    printed for and says each fault: the Senate district 99 that resolves to nothing; the town
    placed in a district that does not hold it; a result's seats, towns and floterial mark; the
    map's floterial layer drawing a district that is not; a former member's label and page address
    naming two districts; the site data's district for a sitting member against the roster's; and
    it counts the 2020 result, the 2019-2020 sponsor and former member as of an era not on file,
    resolving none of them."""
    S = ST.SETTINGS
    nums = S["county_numbers"]
    assert sorted(nums) == sorted(ST.COUNTIES) and all(re.fullmatch(r"\d\d", v) for v in nums.values()) \
        and len(set(nums.values())) == len(nums), f"the counties' numbers are not one two-digit number each: {nums}"
    tmp = Path(tempfile.mkdtemp(prefix="gr-districts-"))
    try:
        _copy_tracked(tmp, [n for n in TRACKED if n.startswith("records/")])
        districts, places = BE.districts_and_places(tmp, S)
        model = {"district": districts, "place": places}
        index = EN.district_index(model)
        want = {"house": {"results", "map", "label", "legislature", "slug"}, "senate": {"results", "label", "slug"}}
        for d in districts:
            forms = EN.district_spellings(d)
            assert want.get(d["kind"], set()) <= set(forms), f"{d['district']} has the spellings {sorted(forms)}"
            for form, said in forms.items():
                assert EN.resolve_district(index, d["kind"], said, d.get("era")) == d["district"], (
                    f"{d['district']}'s {form} {said!r} does not resolve to it")
                if d.get("era"):
                    assert EN.resolve_district(index, d["kind"], said, None) is None \
                        and EN.resolve_district(index, d["kind"], said, "2012") is None, (
                            f"{d['district']}'s {form} {said!r} resolves in an era the table does not hold")
        same = {"house:2022:belknap-8": ("H|Belknap|8", "belknap-8", "BE8", "Belknap 8", "Belk 8", "01-8",
                                         "belk-8", "Belk. 8", "BELK 08", "H|Belknap|08", "01-08", "be8"),
                "house:2022:carroll-7": ("Carr 07", "02-07", "CA07", "Carroll 07"),
                "senate:2022:22": ("S|22", "SD22", "sd-22", "Senate District 22", "22", "022")}
        for did, forms in same.items():
            for said in forms:
                assert EN.resolve_district(index, did.split(":")[0], said, "2022") == did, f"{said!r} is not {did}"
        assert EN.resolve_district(index, "house", "22", "2022") is None, "a bare number named a House district"
        assert not [p for p in EN.problems(dict(model, office=EN.offices(S))) if "spell two" in p]
        m = copy.deepcopy(model)
        next(d for d in m["district"] if d["district"] == "house:2022:belknap-2")["keys"]["label"] = "Belk 1"
        said = EN.problems(m)
        assert any("spell two of them 'belk 1'" in p for p in said), said[:3]
        # The step, on a made-up tree with every file the site prints districts from.
        shutil.rmtree(tmp)
        tmp.mkdir()
        _district_tree(tmp, BE, EN, PE, model)
        before = _tree_digest(tmp)
        r = _run([sys.executable, str(_paths.script("build_entities.py")), "--out", "data/entities"],
                 cwd=tmp, capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, f"build_entities.py exited {r.returncode}: {(r.stderr or r.stdout)[-600:]}"
        after = _tree_digest(tmp)
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        assert changed and all(k.startswith("data/entities/") for k in changed), (
            f"build_entities.py wrote outside data/entities/: {[k for k in changed if not k.startswith('data/entities/')]}")
        _model, _layouts, manifest = EN.load(tmp / "data" / "entities")
        dr = manifest["districts"]
        assert "districts:" in r.stdout and "WARNING: a senate district the table does not hold" in r.stdout, r.stdout[-800:]
        assert [x["where"] for x in dr["unresolved"]] == ["site/places.json albany"] and dr["unresolved_count"] == 1, dr["unresolved"]
        got = sorted((x["what"], x["where"]) for x in dr["disagreements"])
        assert got == sorted([
            ("a place in a district that does not hold it", "site/places.json conway"),
            ("a district's seats, two ways", "collected/election_2026.json H|Carroll|1"),
            ("a district's towns, two ways", "collected/election_2026.json H|Carroll|1"),
            ("a district floterial one way and not the other", "collected/election_2026.json H|Belknap|8"),
            ("a district floterial one way and not the other", "site/district_map.json layers.float.CA1"),
            ("one record whose spellings name two districts", "former member 376040"),
            ("one record whose spellings name two districts", "member 11800")]), got
        assert dr["printed"]["collected/election_2020.json"] == {"resolved": 0, "era not on file": 1, "unresolved": 0} \
            and dr["printed"]["data/sponsors.json"] == {"resolved": 2, "era not on file": 1, "unresolved": 0} \
            and dr["printed"]["site/former.json"] == {"resolved": 3, "era not on file": 4, "unresolved": 0}, dr["printed"]
        assert dr["printed"]["site/legislators.json"]["resolved"] == 6 and not dr["not_here"], (dr["printed"], dr["not_here"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(len(EN.district_spellings(d)) for d in districts)
    return "ok", (f"{len(districts)} districts of the tracked lists, {n:,} spellings, each resolving to its one id in its "
                  "era and in no other; Belk. 8, BELK 08, 01-08 and Carr 07 resolve as the files print them; a spelling "
                  "two districts share breaks a rule; on a made-up tree the step resolves every file the site prints "
                  "districts from, says the one that resolves to nothing and the seven disagreements, and counts "
                  "the terms before every era on file")


def _districts_read_plainly(PD, folder):
    """site/districts.json as parse_districts.combine wrote it before the district table (to 19
    November 2026): each list read and laid out town by town, here only to hold the table's view
    to it."""
    out = {}
    for kind in ("senate", "council", "congress"):
        if (folder / f"{kind}.txt").is_file():
            for num, entries in PD.parse(folder / f"{kind}.txt").items():
                for town, ward in entries:
                    out.setdefault(town, {}).setdefault(ward, {})[kind] = int(num)
    if (folder / "house.txt").is_file():
        for (county, num), rec in PD.parse_house(folder / "house.txt").items():
            for town, ward in rec["towns"]:
                out.setdefault(town, {}).setdefault(ward, {}).setdefault("house", []).append(
                    {"county": county, "district": int(num), "seats": rec["seats"], "floterial": rec["floterial"]})
        for wards in out.values():
            for v in wards.values():
                if "house" in v:
                    v["house"].sort(key=lambda x: (x["floterial"], x["district"]))
    return out


@check("files", "site/districts.json is written from the one district table, and is byte for byte what the district lists said before it",
       needs=("parse_districts", "entities"))
def _districts_json_is_the_tables_view(PD, EN):
    """THE DISTRICT TABLE IS THE ONE SOURCE OF site/districts.json (the model's design, step 4).
    parse_districts.combine, which the night runs to write it, reads the lists and returns the view
    of the newest era (entities.view_districts) of the one table (entities.district_table), the
    table the model is built on. Held: on the tracked lists (records/districts/) it is, byte for
    byte as the file is written, what the lists read plainly gave before the table (the town-by-
    town layout combine built until 19 November 2026); and a table planted to disagree -- one
    district given nine seats -- is what combine then returns, so nothing but the table writes it.
    And on a made-up folder of lists, the same."""
    folder = _paths.ROOT / "records" / "districts"
    quiet = lambda *a, **k: None  # noqa: E731
    got = json.dumps(PD.combine(folder, None, say=quiet), indent=2, sort_keys=True)
    assert got == json.dumps(_districts_read_plainly(PD, folder), indent=2, sort_keys=True), (
        "site/districts.json from the district table is not what the lists read plainly give")
    tmp = Path(tempfile.mkdtemp(prefix="gr-districts-json-"))
    try:
        (tmp / "house.txt").write_text("Belknap County District 1\nCenter Harbor, New Hampton\n"
                                       "Belknap County District 2 (2 seats)\nMeredith\n"
                                       "Belknap County District 3 (Floterial)\nCenter Harbor, Meredith\n",
                                       encoding="utf-8")
        (tmp / "senate.txt").write_text("District 2\nCenter Harbor, Meredith, New Hampton\n", encoding="utf-8")
        (tmp / "council.txt").write_text("District 1\nCenter Harbor, Meredith, New Hampton\n", encoding="utf-8")
        (tmp / "congress.txt").write_text("District 1\nCenter Harbor, Meredith, Dover-Ward 1\n", encoding="utf-8")
        made = PD.combine(tmp, None, say=quiet)
        assert json.dumps(made, sort_keys=True) == json.dumps(_districts_read_plainly(PD, tmp), sort_keys=True), made
        assert made["Meredith"]["0"]["house"] == [
            {"county": "Belknap", "district": 2, "seats": 2, "floterial": False},
            {"county": "Belknap", "district": 3, "seats": 1, "floterial": True}] and made["Dover"]["1"] == {
            "congress": 1}, made
        real = EN.district_table

        def planted(lists, settings=None):
            districts, places = real(lists, settings)
            for d in districts:
                if d["district"].endswith(":belknap-2"):
                    d["seats"] = 9
            return districts, places
        PD.EN.district_table = planted
        try:
            seats = [h["seats"] for h in PD.combine(tmp, None, say=quiet)["Meredith"]["0"]["house"]]
        finally:
            PD.EN.district_table = real
        assert seats == [9, 1], f"a table planted to give Belknap 2 nine seats wrote {seats}: combine has another source"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    towns = json.loads(got)
    return "ok", (f"{len(towns)} towns, {sum(len(w) for w in towns.values())} town-wards: the table's view of the "
                  "tracked lists is what they read plainly gave, byte for byte; a made-up folder too; and a "
                  "table planted with nine seats is what combine writes")


_RESULTS_2012 = ("collected/election_2016.json", "collected/election_2018.json", "collected/election_2020.json")


@check("files", "the district table's 2012 era is the House's and the Senate's districts as the 2016, 2018 and 2020 results lay them out, every race of the three agreeing with it, and the specials reader takes its era from the table",
       needs=("build_entities", "entities", "state_settings", "parse_sos_results", "parse_sos_specials"))
def _district_era_2012(BE, EN, ST, PSR, P):
    """THE 2012 LINES, IN THE ONE TABLE (the model's design, step 4, and decision 11: no table of
    the 2012 lines is on file, so the results of the generals held on them stand for it). The
    settings' district_eras hold "2012" (the terms 2013-2014 to 2021-2022) beside "2022", and the
    table builds its House and Senate districts from collected/election_2016.json,
    election_2018.json and election_2020.json (parse_districts.results_lists). Held on those
    tracked files: era_of gives each term its era; the era has 204 House districts of 400 seats
    and 24 Senate districts, and no Council or Congress; every race of each file resolves, by its
    results key, to one district of 2012 whose seats, floterial mark and towns are the race's (a
    place printed otherwise read by the era's "printed"); 2016's lack exactly Strafford's House
    races and the Senate; every place of 2012 is a place of today's lists; a former member's one
    district is read on the 2012 lines only where every term they served was on them (one who sat
    before them too, given "Hills 48", is of no era on file; one of 2015-2016 alone is a district
    the table does not hold, and said); and each "printed"
    entry is printed by one of the files, names a place of the lists, and is that place by
    parse_sos_results.place_key, a ward written Wd. Planted: a 2018 race laid out otherwise than
    2016's and 2020's leaves the era out, and says which; a file not there, too. And the specials
    reader takes a seat's era from the table: it binds no era of its own, and with the settings'
    2012 era planted to start in 2021-2022 it refuses the 2019 special it read before."""
    S = ST.SETTINGS
    assert [EN.era_of(t) for t in ("2011-2012", "2013-2014", "2021-2022", "2023-2024")] == [None, "2012", "2012", "2022"]
    spec = S["district_eras"]["2012"]
    assert list(spec["results"]) == list(_RESULTS_2012) and set(spec["kinds"]) == {"house", "senate"}, spec
    tmp = Path(tempfile.mkdtemp(prefix="gr-era-2012-"))
    try:
        _copy_tracked(tmp, [n for n in TRACKED if n.startswith("records/")] + list(_RESULTS_2012))
        said = []
        districts, places = BE.districts_and_places(tmp, S, said)
        assert not said, said
        of = {}
        for d in districts:
            of.setdefault((d["kind"], d.get("era")), []).append(d)
        house, senate = of.get(("house", "2012"), []), of.get(("senate", "2012"), [])
        assert len(house) == 204 and sum(d["seats"] for d in house) == 400 and len(senate) == 24, (
            len(house), sum(d["seats"] for d in house), len(senate))
        assert not of.get(("council", "2012")) and not of.get(("congress", "2012"))
        index = EN.district_index({"district": districts})
        PL = {p["place"]: p for p in places}
        printed = spec["printed"]
        used, keys = set(), {}
        for rel in _RESULTS_2012:
            races = json.loads((tmp / rel).read_text(encoding="utf-8"))["races"]
            keys[rel] = set(races)
            for key, race in races.items():
                kind = "senate" if key.startswith("S|") else "house"
                did = EN.resolve_district(index, kind, key, "2012")
                assert did, f"{rel} {key} is no district of the 2012 table"
                d = next(x for x in districts if x["district"] == did)
                used |= {t for t in race["towns"] if t in printed}
                theirs = {printed.get(t, t) for t in race["towns"]}
                mine = {BE._town_ward(PL[p]) for p in d["places"]}
                assert (race["seats"], bool(race.get("floterial")), theirs) == (d["seats"], bool(d.get("floterial")), mine), (
                    f"{rel} {key}: {race['seats']} seat(s), floterial {race.get('floterial')}, towns {sorted(theirs - mine)[:3]} "
                    f"against the table's {d['seats']}, {d.get('floterial')}, {sorted(mine - theirs)[:3]}")
        lack = keys[_RESULTS_2012[1]] - keys[_RESULTS_2012[0]]
        assert keys[_RESULTS_2012[1]] == keys[_RESULTS_2012[2]] and lack == {
            k for k in keys[_RESULTS_2012[1]] if k.startswith("S|") or k.startswith("H|Strafford|")}, sorted(lack)[:5]
        assert all("2022" in PL[p]["in"] for p in PL if "2012" in PL[p]["in"]), "a place of 2012 is not a place of the lists"
        names = {BE._town_ward(p) for p in places if "2022" in p["in"]}
        key = lambda s: re.sub(r"\bwd\b", "ward", PSR.place_key(s))  # noqa: E731
        for wrote, place in printed.items():
            assert wrote in used, f"the 2012 era's printed {wrote!r} is printed by none of the three files"
            assert place in names, f"the 2012 era's printed {wrote!r} names {place!r}, no place of the lists"
            assert key(wrote) == key(place), f"{wrote!r} and {place!r} are not one place by place_key"
        # A former member's one district, in the era of their last term only where every term
        # they served is of it: one who sat before the 2012 lines too is of no era on file.
        def former(i, terms, label):
            county, n = label.split()
            return {"id": i, "name": f"Member, {i}", "chamber": "H", "county": "Hillsborough", "district": n,
                    "district_label": label, "slug": f"m-{i}-hills-{n}", "served": {"terms": terms}}
        (tmp / "site").mkdir(exist_ok=True)
        (tmp / "site" / "former.json").write_text(json.dumps([
            former("1", ["2001-2002", "2015-2016"], "Hills 48"), former("2", ["2017-2018", "2019-2020"], "Hills 45"),
            former("3", ["2015-2016"], "Hills 48")]), encoding="utf-8")
        pr, missing = BE.printed_districts(tmp, S)
        dr = BE.district_report({"district": districts, "place": places}, pr, S, missing)
        assert dr["printed"]["site/former.json"] == {"resolved": 3, "era not on file": 3, "unresolved": 3} and {
            x["where"] for x in dr["unresolved"]} == {"site/former.json 3 Member, 3"}, (dr["printed"], dr["unresolved"])
        # Planted: a 2018 race laid out otherwise, and a file not there.
        doc = json.loads((tmp / _RESULTS_2012[1]).read_text(encoding="utf-8"))
        doc["races"]["H|Belknap|2"]["seats"] += 1
        (tmp / _RESULTS_2012[1]).write_text(json.dumps(doc), encoding="utf-8")
        said = []
        districts, _places = BE.districts_and_places(tmp, S, said)
        assert not [d for d in districts if d.get("era") == "2012"] and said == [
            "the districts of 2012 are left out: collected/election_2018.json H|Belknap|2 lays the district "
            "out otherwise than collected/election_2016.json"], said
        (tmp / _RESULTS_2012[1]).unlink()
        said = []
        BE.districts_and_places(tmp, S, said)
        assert said == ["the districts of 2012 are left out: collected/election_2018.json not here"], said
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # The specials reader binds no era of its own, and follows the table's.
    tree = _parsed(_paths.locate("parse_sos_specials.py"))
    own = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Assign)
           and any(isinstance(c, ast.Constant) and c.value in ("2012", "2013-2014") for c in ast.walk(n.value))]
    assert not own, f"parse_sos_specials.py binds an era of its own on line(s) {own}"
    from pf_elections import _sp_world
    root = Path(tempfile.mkdtemp(prefix="gr-era-specials-"))
    first = spec["first_term"]
    try:
        src, col = _sp_world(root)
        before = P.read_all(src, col)
        r9 = [c for c in before["contest"] if c["contest"] == "2019-10-08.special.house.rockingham-9"]
        assert r9 and r9[0]["district"] == "house:2012:rockingham-9" and not before.get("_refused"), r9
        spec["first_term"] = "2021-2022"
        planted = P.read_all(src, col)
    finally:
        spec["first_term"] = first
        shutil.rmtree(root, ignore_errors=True)
    refused = [r for r in planted.get("_refused") or [] if "rockingham-9" in r.get("file", "")]
    assert refused and "before every era of districts" in refused[0]["why"], planted.get("_refused")
    return "ok", (f"2012: {len(house)} House districts of 400 seats and {len(senate)} Senate, from the three results "
                  f"files, every race of each agreeing; {len(printed)} places printed otherwise, each one place by "
                  "place_key; a race planted otherwise and a file gone each leave the era out and say so; the "
                  "specials reader binds no era and refuses a 2019 seat when the table's 2012 era is planted later")


@check("data", "every district the site prints today resolves by the one district table to one id with its era, and where a file and the table disagree is listed",
       needs=("build_entities", "entities", "state_settings"))
def _districts_printed_today(BE, EN, ST):
    """The district table on the night's files (the design's step 4): data/entities/, as the build
    wrote it, read back, and every district spelling the files the site prints districts from
    give (build_entities.PRINTED: the roster and the site data's members, the former members, the
    members-elect, the town table, the town search, the district map, each election's results and
    the bills' sponsors) read again here and resolved by the model's district table in the era of
    the term it is printed for. Each one of an era the table holds resolves to one id; what the
    manifest says of them -- by file, and every disagreement -- is what reading them again gives,
    so the night's log said what is true. Where the General Court's county table (Counties.txt) is
    here, its numbers are the settings' county_numbers. A tree no build has run the model in, or
    one whose model was built before the district table, is skipped."""
    folder = Path("data") / "entities"
    if not (folder / EN.MANIFEST).is_file():
        return "skip", "no build has made data/entities/ here"
    model, _layouts, manifest = EN.load(folder)
    if "districts" not in (manifest or {}):
        return "skip", "data/entities/ was built before the district table (its manifest has no districts)"
    printed, missing = BE.printed_districts(".", ST.SETTINGS)
    got = BE.district_report(model, printed, ST.SETTINGS, missing)
    assert not got["unresolved_count"], (f"{got['unresolved_count']} district(s) the site prints resolve to none: "
                                         + "; ".join(f"{x['where']}: {x['says']}" for x in got["unresolved"][:5]))
    assert got == manifest["districts"], ("the manifest's districts are not what today's files give: rebuild the "
                                          "model (python3 src/parse/build_entities.py)")
    counties = Path("Counties.txt")
    said = ""
    if counties.is_file():
        theirs = {}
        for line in counties.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            parts = line.split("|")
            if len(parts) >= 2 and parts[0].strip().isdigit():
                theirs[parts[1].strip()] = parts[0].strip().zfill(2)
        assert theirs == ST.SETTINGS["county_numbers"], (
            f"Counties.txt numbers the counties {theirs}, the settings {ST.SETTINGS['county_numbers']}")
        said = "; Counties.txt's county numbers are the settings'"
    n = {k: sum(v[k] for v in got["printed"].values()) for k in ("resolved", "era not on file")}
    return "ok", (f"{n['resolved']:,} district spellings in {len(got['printed'])} files resolved to one id each, "
                  f"{n['era not on file']:,} of a term before every era on file; {got['disagreements_count']} "
                  f"disagreement(s), as the manifest lists{said}")
