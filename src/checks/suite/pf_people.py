#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.12
"""
preflight's checks of sponsors, members and officials.

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import csv
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

import _paths

from pf_core import (_in_suite, _run, _source, check, imp)
from pf_fixture import (CHAIN_NEEDS, _built_site_prepare, _built_site_run, _fixture_site_shared)
from pf_harness import (_app_js, _node_app, _with_components)
from pf_shared import (SPONSOR_HONORIFIC, _STATUSCAT_HARNESS, _STATUS_CATEGORY,
                       _STATUS_REAL_PAIRS, _elect_strip, _officials_now)


@check("files", "a new member gets their number by the rule with nobody's help, the register wins, and no two people ever share one")
def _person_rule():
    """The owner's conditions for person numbers (30 October 2026), and the
    register's promise, held on a record made up here, so they hold whatever
    tonight's data is:

      a new member with a PersonID      is numbered by it, the same night,
                                        and not marked provisional
      a new member with only an employee number   is numbered by that
      a new member with neither         gets one made here ("s" and the site
                                        id), marked provisional
      a member who gains a PersonID     keeps the number the register issued
                                        them: the register wins over the rule
      a number someone already holds    is never given to a second person,
                                        whether the register holds it or
                                        another newcomer took it tonight
      an issued person tonight's record lacks   is reported, never dropped
                                        in silence

    and what is published holds no number twice (people.check_unique)."""
    import tempfile
    sys.path.insert(0, str(_paths.locate("people.py").parent))
    import people as PE

    def world(d, roster, careers_, votes, legs=()):
        (d / "db").mkdir(exist_ok=True)
        (d / "site" / "legislators").mkdir(parents=True, exist_ok=True)
        (d / "data").mkdir(exist_ok=True)
        (d / "db" / "_columns.json").write_text(json.dumps(
            {"Legislators": ["PersonID", "LastName", "FirstName", "Employeeno"]}))
        (d / "db" / "Legislators.psv").write_text("".join(f"{p}|N|F|{e}\n" for p, e in roster))
        (d / "site" / "legislators.json").write_text(json.dumps(list(legs)))
        (d / "site" / "former.json").write_text("[]")
        (d / "data" / "sponsors.json").write_text("{}")
        (d / "data" / "member_votes.json").write_text(json.dumps([{"member_id": m} for m in votes]))
        return {e: {"by_term": {"2027-2028": {"chambers": [ch], "employee_nos": [e]}},
                    "employee_nos": [e], "first": e, "last": "Newcomb"} for e, ch in careers_}

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        # 376003's PersonID, 11602, is already issued to someone else.
        careers = world(d, [("11600", "376001"), ("11602", "376003")],
                        [("376001", "H"), ("376002", "H"), ("376003", "S")],
                        ["11600", "376002", "11602", "99"],
                        [{"id": "11600", "name": "Newcomb, Ada", "slug": "ada-newcomb-hills-1"}])
        reg = {"format": 1, "people": [{"person": "11602", "numbers": ["376777"]}]}
        assert not PE.check_register(reg), PE.check_register(reg)
        people, rep = PE.build(d / "site", d / "data", d / "db", careers, reg)
        by = {p["person"]: p for p in people}
        got = {
            "a PersonID": "11600" in by and not by["11600"].get("provisional"),
            "only an employee number": "376002" in by and not by["376002"].get("provisional"),
            "neither": (by.get("s99") or {}).get("provisional") is True,
            "a number the register holds": any(c["person"] == "11602" for c in rep["clashes"])
                                           and not any("376003" in (p.get("employee_numbers") or [])
                                                       for p in people),
            "an issued person missing tonight": rep["missing_issued"] == ["11602"],
        }
        assert all(got.values()), "the rule does not hold for: " + ", ".join(k for k, v in got.items() if not v)
        assert not PE.check_unique(people), PE.check_unique(people)

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        # 376002 was issued under its employee number; tonight the roster
        # gives it a PersonID, 11605, and the register still wins. And two
        # newcomers whose roster rows share a PersonID, 11610, take it once.
        careers = world(d, [("11605", "376002"), ("11610", "376010"), ("11610", "376011")],
                        [("376002", "H"), ("376010", "H"), ("376011", "S")],
                        ["11605", "376010", "376011"])
        reg = {"format": 1, "people": [{"person": "376002", "numbers": ["376002"]}]}
        people, rep = PE.build(d / "site", d / "data", d / "db", careers, reg)
        persons = [p["person"] for p in people]
        assert "376002" in persons and "11605" not in persons, \
            f"the register did not win over the rule: {persons}"
        assert persons.count("11610") == 1 and len(rep["clashes"]) == 1, \
            f"a number was given twice in one night: {persons}, {rep['clashes']}"
        assert not PE.check_unique(people), PE.check_unique(people)
    assert PE.check_unique([{"person": "1", "employee_numbers": ["376001"]},
                            {"person": "2", "employee_numbers": ["376001"]}]), \
        "check_unique let two people share an employee number"
    for bad in ({"people": [{"person": "s99", "numbers": ["m99"]}]},
                {"people": [{"person": "376003", "numbers": ["376777"]}]},
                {"people": [{"person": "11600", "numbers": []}]},
                {"people": [{"person": "1", "numbers": ["376001"]}, {"person": "2", "numbers": ["376001"]}]},
                []):
        assert PE.check_register(bad), f"check_register passed a malformed register: {bad}"
    return "ok", ("a new member is numbered by their PersonID (11600), else their employee number "
                  "(376002), else one made here and provisional (s99); the register wins over a "
                  "PersonID found later (376002 stays); a number already held, by the register or "
                  "by another newcomer the same night, is refused (11602, 11610); an issued person "
                  "missing tonight is reported; and the checks of uniqueness and of the register's "
                  "shape catch what they should")


@check("files", "only a person's run writes the register of person numbers, and it is well formed")
def _person_register():
    """generated/person_numbers.json holds the person numbers the public data
    API publishes (docs/design/api/DESIGN.md, 2.5; the owner's decision of 30
    October 2026, Q14). Other sites store those numbers, so one issued is
    never moved or reissued, and the only writer is src/ops/person_numbers.py
    --issue, which a person runs. The nightly reads it. Two things are held
    here: no other code file writes it, by any of the shapes the hand-made
    files' check reads, and what is there is well formed (no number held by
    two people, no person issued twice)."""
    REG = "person_numbers.json"
    # And the hand links beside it, which no code writes at all.
    stem = r"(?<![\w-])(?:person_numbers|person_links)\.json"
    HELD = re.compile(r'^[ \t]*([A-Za-z_]\w*)[ \t]*(?::[^=\n]*)?=[^=\n][^\n]*' + stem, re.M)

    def writes(src):
        if re.search(r'open\s*\([^)]*' + stem + r'[^)]*["\'][wax]', src) or \
           re.search(stem + r'[^\n]{0,60}\.write_(?:text|bytes)', src):
            return True
        for held in set(HELD.findall(src)):
            n = re.escape(held)
            if re.search(r'\b%s\s*\.\s*(?:write_text|write_bytes)\s*\('
                         r'|\b%s\s*\.\s*open\s*\(\s*(?:mode\s*=\s*)?["\'][wax]'
                         r'|\bopen\s*\(\s*%s\s*,\s*(?:mode\s*=\s*)?["\'][wax]'
                         r'|\b(?:os\.replace|os\.rename|shutil\.(?:copy\w*|move))'
                         r'\s*\([^)\n]*,\s*%s\s*\)' % (n, n, n, n), src):
                return True
        return False

    for text, w in (('open("generated/person_numbers.json", "w")', True),
                    ('Path("generated/person_numbers.json").write_text(t)', True),
                    ('REG = Path("generated") / "person_numbers.json"\nREG.write_text(t)', True),
                    ('R = "generated/person_numbers.json"\nos.replace(tmp, R)', True),
                    ('def f(register="generated/person_numbers.json"):\n    reg = load(register, None)', False),
                    ('json.loads(Path("generated/person_numbers.json").read_text())', False)):
        assert writes(text) == w, f"the register's reader reads {text!r} as " + ("no write" if w else "a write")
    bad = []
    for f in _paths.code_files("*.py"):
        # The writer, and this file, whose cases above name it on purpose.
        if f.name == "person_numbers.py" or _in_suite(f):
            continue
        if writes(f.read_text(encoding="utf-8", errors="replace")):
            bad.append(f.name)
    assert not bad, "these write the register of person numbers or its hand links, which " \
                    "only person_numbers.py --issue (the register) and a person (the links) " \
                    "may: " + ", ".join(bad)
    links = _paths.ROOT / "generated" / "person_links.json"
    if links.exists():
        sys.path.insert(0, str(_paths.locate("people.py").parent))
        import people as PE
        try:
            PE.load_links(links)
        except SystemExit as e:
            raise AssertionError(f"person_links.json is not well formed: {e}")
    reg = _paths.ROOT / "generated" / REG
    if not reg.exists():
        return "ok", ("no other code file writes it; no register issued yet, so every person is "
                      "numbered by the rule each night")
    sys.path.insert(0, str(_paths.locate("person_numbers.py").parent))
    import person_numbers as PN
    now = json.loads(reg.read_text(encoding="utf-8"))
    problems = PN.check_register(now)
    assert not problems, "the register is not well formed: " + "; ".join(problems[:5])
    # ONLY EVER ADDED TO. Against dev's copy, where there is one: every person
    # issued there is still here, holding at least the numbers it held, or
    # retired with replaced_by. A number moved or a person deleted fails.
    r = _run(["git", "show", "origin/dev:generated/person_numbers.json"],
             capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        then = {e["person"]: e for e in json.loads(r.stdout).get("people") or []}
        here = {e["person"]: e for e in now.get("people") or []}
        moved = []
        for p_, e in then.items():
            h = here.get(p_)
            if h is None:
                moved.append(f"{p_} is gone")
            elif not h.get("replaced_by") and not set(e.get("numbers") or []) <= set(h.get("numbers") or []):
                moved.append(f"{p_} lost a number")
        assert not moved, "the register is only ever added to, and against dev's: " + "; ".join(moved[:5])
    return "ok", "no other code file writes it, and it is well formed"


@check("build", "a member's On Record line covers the 1989-1998 terms the sponsor record places "
                "them in, by chamber, as the TERM picker does: app.js and the static page agree",
       needs=("build_legislator_pages", "build_site_v2"))
def _on_record_covers_the_nineties(LP, B):
    """Found on the release candidate's preview (13 November 2026): the page offered 1991-1992 to
    1998 in its TERM picker and said "ON RECORD: House, 1999-2024". The years since 1999 are the
    terms attendance is counted in, consecutive ones joined and a term with no roll call a gap
    (the owner's rule for the 1990s, applied after 1999 on 15 November 2026: 289 of the 2,192
    people with roll calls have such a gap, David Meader's "1999-2020" two), or each chamber's
    own where a service list joins two. The terms before 1999 are
    added to the chamber the sponsor record gives (`past_terms`, member_links.earlier_terms from
    the sponsored bills the picker lists), and join it, or another 1990s term, only where the
    terms run into each other: a term the record lacks between a 1990s run and the rest is
    shown as a gap, never bridged. The votes lines stay roll calls', 1999 on.

    - a House member with 1990s terms and roll calls: the terms that run into the roll calls join
      them, the others stand as their own runs ("House, 1991-1992, 1995-2024"), never one span
      across a term the record lacks;
    - a member with a 1990s Senate term and later House service: each chamber its own span;
    - a member with none is as before;
    - app.js's line and the static page's say the same years;
    - A TERM WHOSE BILLS ARE ALL THE RECORD'S OWN ROWS (past_sponsors.filled: a chamber, no seat,
      no `matched`), as Donna Sytek's of 1997-1998 are, a term she was Speaker: bill_sponsor_list
      gave only the printed rows a chamber, and her line read "House, 1989-1996, 1999-2000" beside
      a TERM picker offering 1997-1998 (the review before the release of 16 November 2026). Now
      earlier_terms holds the term, and app.js, record_spans, the static sentence and the
      description join it ("1989-2000"); the chamber is the one the term's Manual seats them in
      (sponsor_record_chambers), else the row's own, which is their last seat, and the build says
      how many the Manual seated, that it read none, or how many rows it seats in another
      chamber than their own (sponsor_record_said), never falling back in silence;
    - A TERM THE MANUAL SEATS THEM IN WITH NO BILL (manual_seats; the owner, 14 November 2026,
      for Francis Vincent's "House, 1989-1992, 1995-2000", whom the 1993 Manual seats at
      Strafford 14): a gap the Manual closes closes in app.js, record_spans, the static sentence
      and the description; a member with no bill before 1999 whom the Manual seats starts in
      the 1990s; a doubtful row, a full name another number shares and a seat in a county the
      member's record never names count for nothing, and are said; build_legislators writes
      past_terms with them and manual_terms with them alone."""
    import re
    from collections import defaultdict
    ML = imp("member_links")
    bad = []
    att = lambda *ts: {t: {"days": 1} for t in ts}
    # Every term from a to b, each counted in attendance: the record of a member who sat throughout.
    run = lambda a, b: [f"{y}-{y + 1}" for y in range(a, b, 2)]
    base = {"chamber": "H", "party": "D", "county": "Hillsborough", "district": "39",
            "display_plain": "Rep. Pat Example", "display_full": "Rep. Pat Example (D - Hills 39)",
            "display": "Rep. Pat Example (D)", "slug": "pat-example-hills-39", "towns": [],
            "committees": []}
    house = dict(base, id="800001", attendance=att(*run(1999, 2025)),
                 past_terms={"H": ["1991-1992", "1995-1996", "1997-1998"]})
    mover = dict(base, id="800002", slug="sam-mover-hills-1", attendance=att(*run(2001, 2009)),
                 past_terms={"S": ["1993-1994"]})
    plain = dict(base, id="800003", slug="al-plain-hills-2", attendance=att(*run(2011, 2025)))
    adj = dict(base, id="800005", slug="ad-jacent-hills-3", attendance=att(*run(1999, 2025)),
               past_terms={"H": ["1997-1998"]})
    far = dict(base, id="800006", slug="fa-gap-hills-4", attendance=att(*run(2003, 2011)),
               past_terms={"H": ["1989-1990"]})
    # A TERM WITH NO ROLL CALL AFTER 1999 IS A GAP TOO (15 November 2026): two runs, never 1999-2012.
    gaps = dict(base, id="800010", slug="ga-ps-hills-5",
                attendance=att("1999-2000", "2001-2002", "2003-2004", "2009-2010", "2011-2012"))
    cases = {"house": (house, "House, 1991–1992, 1995–2024"),
             "adjacent": (adj, "House, 1997–2024"),
             "gap": (far, "House, 1989–1990, 2003–2010"),
             "mover": (mover, "Senate, 1993–1994 · House, 2001–2008"),
             "plain": (plain, "House, 2011–2024"),
             "plain gap": (gaps, "House, 1999–2004, 2009–2012")}
    if ML.earlier_terms([{"term": "1991-1992", "ch": "S"}, {"term": "1993-1994", "ch": "S"},
                         {"term": "2001-2002", "ch": "H"}, {"term": "1995-1996"}]) \
            != {"S": ["1991-1992", "1993-1994"]}:
        bad.append("earlier_terms: only the pre-1999 terms the sponsor record placed, with a chamber")
    # THE RECORD'S OWN ROWS, filed as the build files them (bill_sponsor_list). Dee Speaker's
    # 1989-1996 bills print her and their sponsor rows place her (`matched`); her 1997-1998
    # resolutions are the record's alone, as Donna Sytek's are. Robin Mover's one 1995-1996 bill
    # is the record's own row with the chamber of her last seat, the Senate, and the term's
    # Manual seats her in the House.
    sid, own = "800008", {"source": B.PSP.SOURCE, "seat_source": B.PSP.SOURCE}
    row = lambda **kw: dict({"member_id": sid, "employee": sid, "name": "Dee Speaker",
                             "chamber": "H", "prime": True}, **kw)
    printed = row(source="bill text", matched=B.PAST_ROSTER_MATCH)
    sponsors = {"1989-1990": {"HB41": [printed]}, "1991-1992": {"HB40": [printed]},
                "1993-1994": {"HB108": [printed]},
                "1995-1996": {"HB124": [printed], "HR52": [row(**own, member_id="800009",
                                                              employee="377001",
                                                              name="Robin Mover", chamber="S")]},
                "1997-1998": {"HR22": [row(**own)], "HR50": [row(**own)]}}
    manual = {"terms": {"1995-1996": {"edition": "1995", "senate": [], "house": [
        {"name": "Robin Mover", "county": "Merrimack", "district": "4", "status": "elected",
         "district_check": "clean"}]}}}
    seated = B.sponsor_record_chambers(
        sponsors, table=manual, people=B.PSP.People([], {"377001": {"name": "Mover, Robin",
                                                                     "chamber": "S"}}))
    if seated != {("377001", "1995-1996"): "H"}:
        bad.append(f"sponsor_record_chambers does not seat Robin Mover where the 1995 Manual "
                   f"does: {seated}")
    # Never in silence: what main() prints of the answer (sponsor_record_said).
    said_seated, said_none = B.sponsor_record_said(sponsors, seated), B.sponsor_record_said(sponsors, {})
    if len(said_seated) != 2 or "1 member-terms" not in said_seated[0] \
            or "1 1989-1998 row(s)" not in said_seated[1] \
            or "still name the row's own chamber" not in said_seated[1] \
            or said_none != ["  sponsors: no Manual seat list read; every 1989-1998 row of the "
                             "General Court's sponsor record keeps its own chamber"] \
            or B.sponsor_record_said({}, {}) != []:
        bad.append(f"the build does not say what the Manual seated, that none was read, or a row "
                   f"seated in another chamber: {said_seated} {said_none}")

    def filed(chambers):
        out = defaultdict(list)
        for term, rows in sponsors.items():
            for bid in rows:
                B.bill_sponsor_list(bid, {"designation": bid, "title": "a resolution"}, term[:4],
                                    term, "2025-2026", sponsors, {}, {}, {}, out, {},
                                    record_chambers=chambers)
        return out
    sponsored = filed(seated)
    earlier = ML.earlier_terms(sponsored[sid])
    if earlier != {"H": ["1989-1990", "1991-1992", "1993-1994", "1995-1996", "1997-1998"]}:
        bad.append(f"earlier_terms leaves out a term whose bills are the sponsor record's own "
                   f"rows: {earlier}")
    if ML.earlier_terms(sponsored["800009"]) != {"H": ["1995-1996"]} \
            or ML.earlier_terms(filed(None)["800009"]) != {"S": ["1995-1996"]}:
        bad.append("a row of the record does not take the term's Manual's chamber, else its own: "
                   f"{ML.earlier_terms(sponsored['800009'])}, "
                   f"{ML.earlier_terms(filed(None)['800009'])}")
    dee = dict(base, id=sid, slug="dee-speaker-rock-26", former=True, party="R",
               county="Rockingham", district="26", display_plain="Rep. Dee Speaker",
               display_full="Rep. Dee Speaker (R - Rock 26)", display="Rep. Dee Speaker (R)",
               attendance=att("1999-2000"), served={"first": "12/2/1998", "last": "12/6/2000"},
               past_terms=earlier)
    # THE TERMS THE MANUAL SEATS THEM IN (manual_seats; the owner, 14 November 2026). Frances
    # Gapp's bills skip 1993-1994, the term the 1993 Manual seats her at Strafford 14, as
    # Francis Vincent's do; Nell Newby has no bill before 1999 and the 1995 and 1997 Manuals
    # seat her. Only those two count. Left out: Dana Doubt's row is not read cleanly; Terry
    # Twin's two numbers are seated at two seats; Chris Common's full name is another
    # number's too; Fran Faraway's seat is in a county her record never names; Sam Sena's
    # is in a Senate his record has nowhere; Bill Billy's bills of that term print the House.
    clean = lambda name, county, d: {"name": name, "county": county, "district": d,
                                     "status": "elected", "district_check": "clean"}
    sen = lambda name, d: {"name": name, "district": d, "status": "elected"}
    mtable = {"terms": {
        "1991-1992": {"edition": "1991", "house": [], "senate": [sen("Sam Sena", "5")]},
        "1993-1994": {"edition": "1993", "senate": [], "house": [
            clean("Frances C. Gapp", "Strafford", "14"), clean("Chris Common", "Cheshire", "2"),
            clean("Fran Faraway", "Hillsborough", "9"),
            dict(clean("Dana Doubt", "Merrimack", "3"), district_check="marks differ from seats")]},
        "1995-1996": {"edition": "1995", "senate": [sen("Bill Billy", "9")], "house": [
            clean("Nell Newby", "Belknap", "4"), clean("Terry Twin", "Rockingham", "2"),
            clean("Teresa Twin", "Rockingham", "3")]},
        "1997-1998": {"edition": "1997", "senate": [], "house": [clean("Nell Newby", "Belknap", "4")]}}}
    gc = {"377101": ("Gapp, Frances", "Straf", "H"), "377102": ("Newby, Nell", "Belk", "H"),
          "377103": ("Doubt, Dana", "Merr", "H"), "377104": ("Common, Chris", "Ches", "H"),
          "377105": ("Common, Chris", "Ches", "H"), "377106": ("Faraway, Fran", "Coos", "H"),
          "377107": ("Twin, Terry", "Rock", "H"), "377108": ("Twin, Teresa", "Rock", "H"),
          "377109": ("Sena, Sam", "Graf", "H"), "377110": ("Billy, Bill", "", "S")}
    mpeople = B.PSP.People([], {e: {"name": n, "chamber": ch} for e, (n, _c, ch) in gc.items()})
    page = lambda e: dict(base, id=e, name=gc[e][0], slug=f"m-{e}", county="", district="1")
    mpages = {e: page(e) for e in ("377101", "377102", "377103", "377104", "377106", "377107",
                                   "377109", "377110")}
    mpages["377110"].update(chamber="S")
    mpages["377101"].update(former=True, display_plain="Rep. Frances Gapp",
                            display_full="Rep. Frances Gapp (D - Straf 14)",
                            display="Rep. Frances Gapp (D)", county="Strafford")
    mpages["377102"].update(display_plain="Rep. Nell Newby", display_full="Rep. Nell Newby (D - Belk 4)",
                            display="Rep. Nell Newby (D)", county="Belknap")
    mspons = {"377101": [{"term": t, "ch": "H"} for t in ("1989-1990", "1991-1992", "1995-1996",
                                                          "1997-1998")],
              "377110": [{"term": "1995-1996", "ch": "H"}]}
    mseats, mleft = B.manual_seats(mpages, {"377107": ["377108"]}, mspons, {}, table=mtable,
                                   people=mpeople, counties={e: c for e, (_n, c, _h) in gc.items()})
    if mseats != {"377101": {"H": ["1993-1994"]}, "377102": {"H": ["1995-1996", "1997-1998"]}}:
        bad.append(f"manual_seats does not count a term the Manual seats a member in without "
                   f"doubt, and only that: {mseats}")
    if sorted((p, k) for p, _t, k, _w in mleft) != [
            ("377103", "doubtful"), ("377104", "perhaps another person"),
            ("377106", "perhaps another person"), ("377107", "doubtful"),
            ("377109", "perhaps another person"), ("377110", "perhaps another person")]:
        bad.append(f"manual_seats does not leave out a doubtful row, two seats, a shared full "
                   f"name, another county, a chamber the record has nowhere and a chamber the "
                   f"term's bills contradict, saying so: {mleft}")
    if B.manual_said({}, [(None, None, "unread", "x")]) != [
            "  members: no Manual seat list read; the 1989-1998 terms on record are their bills' alone"]:
        bad.append("the build does not say that no Manual seat list was read")
    # The member's own file, as build_legislators writes it: past_terms the bills' and the
    # Manual's together, manual_terms the Manual's alone.
    import contextlib
    import io
    import shutil
    import tempfile
    mroot = Path(tempfile.mkdtemp(prefix="gr-manual-"))
    try:
        (mroot / "legislators").mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
            B.build_legislators(mroot, {"377102": mpages["377102"]}, {}, {}, set(),
                                {"377101": [dict(x, bill="HR1", n="HR 1", title="", year=x["term"][:4],
                                                 prime=True) for x in mspons["377101"]]},
                                {}, {}, {"377101": mpages["377101"]}, None, None, manual=mseats)
        mfile = {e: json.loads((mroot / "legislators" / f"{e}.json").read_text(encoding="utf-8"))
                 for e in ("377101", "377102")}
    finally:
        shutil.rmtree(mroot, ignore_errors=True)
    if (mfile["377101"].get("past_terms"), mfile["377101"].get("manual_terms"),
            mfile["377102"].get("past_terms"), mfile["377102"].get("manual_terms")) != (
            {"H": ["1989-1990", "1991-1992", "1993-1994", "1995-1996", "1997-1998"]},
            {"H": ["1993-1994"]}, {"H": ["1995-1996", "1997-1998"]},
            {"H": ["1995-1996", "1997-1998"]}):
        bad.append("build_legislators does not write the Manual's terms into past_terms, and "
                   f"alone into manual_terms: {[(e, f.get('past_terms'), f.get('manual_terms')) for e, f in mfile.items()]}")
    gapp = dict(mpages["377101"], attendance=att("1999-2000"),
                served={"first": "1/6/1999", "last": "12/6/2000"},
                past_terms=mfile["377101"].get("past_terms"))
    newby = dict(mpages["377102"], attendance=att("1999-2000"),
                 past_terms=mfile["377102"].get("past_terms"))
    got = _app_js("[" + ", ".join(f"scope.renderMemberHead({json.dumps(m)})"
                                  for m in [*(m for m, _ in cases.values()), dee, gapp, newby])
                  + "]", names=("renderMemberHead",))

    def words(h):
        t = re.sub(r"<[^>]+>", " ", h).replace("&ndash;", "–").replace("&middot;", "·")
        return re.sub(r"[\s ]+", " ", t.replace("&nbsp;", " "))
    for i, (name, (m, want)) in enumerate(cases.items()):
        stat = words(LP.static_record(m, m))
        if name.startswith("plain"):
            if "On record:" in stat:
                bad.append("a member with no earlier terms gained a static On record line")
        elif f"On record: {want}" not in stat:
            bad.append(f"{name}: the static page does not say {want!r}: {stat[:300]!r}")
        if got is not None:
            app = words(got[i])
            if f"On Record {want}" not in app:
                bad.append(f"{name}: app.js does not say {want!r}: {app[:300]!r}")
    # NEVER ONE SPAN ACROSS A TERM THE RECORD LACKS (the coordinator, 13 November 2026: 76 of 355
    # people have one between their 1990s terms and their roll calls, 39 of them 3 to 14).
    fgap = dict(far, former=True, served={"first": "1/9/2003", "last": "12/1/2010"}, id="800007")
    if "On record 1989 to 1990 and 2003 to 2010" not in words(LP.static_record(fgap, fgap)):
        bad.append("a former member's sentence bridges a gap: " + words(LP.static_record(fgap, fgap))[:200])
    # A former member's sentence covers the same years, and the page that joins two chambers
    # names each with its own.
    gone = dict(mover, former=True, served={"first": "1/9/2002", "last": "12/1/2008"}, id="800004")
    if "On record 1993 to 1994 and 2001 to 2008" not in words(LP.static_record(gone, gone)):
        bad.append("a former member's static sentence does not start at the earlier term")
    said = LP.describe(gone, gone).replace("House of Representatives", "House")
    if "Senate, 1993 to 1994, and House, 2001 to 2008" not in said:
        bad.append(f"a former member's description does not name each chamber's years: {said!r}")
    # Dee Speaker, whose 1997-1998 is the record's own rows: one run, 1989 to 2000, everywhere.
    if got is not None and "On Record House, 1989–2000" not in words(got[len(cases)]):
        bad.append("app.js does not join a term of the record's own rows: "
                   + words(got[len(cases)])[:300])
    if LP.record_spans(dee, dee) != [{"chamber": "H", "spans": [[1989, 2000]]}]:
        bad.append(f"record_spans does not join a term of the record's own rows: "
                   f"{LP.record_spans(dee, dee)}")
    if "On record 1989 to 2000. This page" not in words(LP.static_record(dee, dee)):
        bad.append("the static sentence does not join a term of the record's own rows: "
                   + words(LP.static_record(dee, dee))[:200])
    if "served in the New Hampshire House of Representatives, 1989 to 2000." \
            not in LP.describe(dee, dee):
        bad.append(f"the description does not join a term of the record's own rows: "
                   f"{LP.describe(dee, dee)!r}")
    # Gapp, whose gap the 1993 Manual closes, and Newby, whom the Manual alone puts in the 1990s.
    for who, m, line, spans, plain in (
            ("a gap the Manual closes", gapp, "House, 1989–2000", [[1989, 2000]],
             "On record 1989 to 2000. This page"),
            ("a member the Manual alone puts in the 1990s", newby, "House, 1995–2000",
             [[1995, 2000]], "On record: House, 1995–2000")):
        i = len(cases) + (1 if m is gapp else 2)
        if got is not None and f"On Record {line}" not in words(got[i]):
            bad.append(f"app.js, {who}: {words(got[i])[:300]}")
        if LP.record_spans(m, m) != [{"chamber": "H", "spans": spans}]:
            bad.append(f"record_spans, {who}: {LP.record_spans(m, m)}")
        if plain not in words(LP.static_record(m, m)):
            bad.append(f"the static page, {who}: {words(LP.static_record(m, m))[:200]}")
    if "served in the New Hampshire House of Representatives, 1989 to 2000." \
            not in LP.describe(gapp, gapp):
        bad.append(f"the description, a gap the Manual closes: {LP.describe(gapp, gapp)!r}")
    # (status, words), as main() unpacks every check's answer: a bare None read as an ERROR on
    # the night of 13 November 2026, though the single runs called it a pass.
    assert not bad, "; ".join(bad)
    return "ok", ("1990s terms join the span since 1999 only where they run into it, else stand "
                  "as their own runs; a 1990s Senate term keeps its chamber; app.js and the "
                  "static page say the same; a member with none is as before; a term whose "
                  "bills are all the sponsor record's own rows counts, in the chamber its "
                  "Manual seats them in, else the row's, and joins: \"House, 1989–2000\"; the "
                  "build says what the Manual seated, or that it read none; a term the Manual "
                  "seats them in with no bill closes a gap or starts the line in the 1990s, "
                  "and a doubtful or shared seat counts for nothing")


@check("build", "members-elect: every new member-elect with a page is linked to it on the Officials "
                "tab; a returning member's page is the member-elect's, a new-chamber member's is "
                "headed as the other chamber's with the seat held now beside it, and both end the "
                "day the term is theirs",
       needs=("officials_tabs", "build_legislator_pages", "build_members_elect"))
def _elect_returning_pages(OT, LP, BME):
    """The owner, 13 November 2026: new members-elect had pages and the tab
    linked none of them (0 of 165: elect_chip read only the id and slug a
    member has); a returning member's page was titled by the seat they left
    ("Former Rep. Benjamin Baroody (D - Hills 39)"); both are held here.

    - elect_chip links a "k": "new" winner to their "e" (the provisional page),
      a member by id and slug as before, and a new winner with no page to none;
    - elect_back: "returning" only for a former member the file says is former
      and whose row is former.json's; "chamber" for a sitting member elected to
      the other chamber; nothing for the re-elected;
    - app.js's renderMemberHead on each: the returning member headed as a new
      member-elect is (name and party under the title, "Representative-elect
      Michael Vose (R)", the sentence, the election's line with no
      "for <district>"), the earlier seat kept in the facts and no "Former
      Representative"; the new-chamber member keeps the seat they hold with the
      sentence beside it; both gone once the reader's day is the day they take
      office, on another member's page and without GR_ELECT;
    - the review before the release of 16 November 2026: the returning page's
      plain record carries the years on record app.js draws (the 25 returning
      pages had none), the bar beside a returning member's heading is in the
      ink of the party they were elected under (Maria Perez's "(D)" was drawn
      in the Independent ink of her record), and a provisional page writes its
      earlier terms with an en dash."""
    bad = []
    key = "H|Hillsborough|42"
    lee = {"n": "Lee C. Nyquist", "p": "D", "k": "new", "e": "lee-c-nyquist-hills-42"}
    if 'href="/legislator/lee-c-nyquist-hills-42' not in OT.elect_chip(lee, key) \
            and 'href="legislator/lee-c-nyquist-hills-42' not in OT.elect_chip(lee, key):
        bad.append(f"the tab's chip for a new member-elect with a page is not linked: "
                   f"{OT.elect_chip(lee, key)!r}")
    if "href=" in OT.elect_chip({"n": "No Page", "p": "D", "k": "new"}, key):
        bad.append("a new member-elect with no page is linked")
    if "href=" in OT.elect_chip({"n": "Odd", "p": "D", "k": "sitting", "e": "x"}, key):
        bad.append("a member is linked to a provisional page")
    vose = {"id": "900001", "name": "Vose, Michael", "chamber": "H", "former": True,
            "display_plain": "Rep. Michael Vose", "display_full": "Rep. Michael Vose (R - Rock 5)",
            "display": "Rep. Michael Vose (R)", "party": "R", "county": "Rockingham",
            "district": "5", "slug": "michael-vose-rock-5",
            "served": {"terms": ["2017-2018"]}, "attendance": {"2017-2018": {"days": 1}}}
    # Maria Perez: elected as a Democrat, on the record as an Independent.
    perez = dict(vose, id="900002", name="Perez, Maria", party="I", party_code="I",
                 display_plain="Rep. Maria Perez", display_full="Rep. Maria Perez (I - Hills 43)",
                 display="Rep. Maria Perez (I)", county="Hillsborough", district="43",
                 slug="maria-perez-hills-43")
    creighton = {"id": "9917", "name": "Creighton, James", "chamber": "H", "party": "Republican",
                 "county": "Hillsborough", "district": "30", "display_plain": "Rep. James Creighton",
                 "display_full": "Rep. James Creighton (R - Hills 30)", "slug": "james-creighton-hills-30",
                 "towns": [], "committees": []}
    inc = dict(creighton, id="5", name="Doe, Jo", display_plain="Rep. Jo Doe",
               display_full="Rep. Jo Doe (R - Hills 30)", slug="jo-doe-hills-30")
    infos = {"vose": {"key": "H|Rockingham|6", "k": "former", "p": "R"},
             "creighton": {"key": "S|8", "k": "sitting", "p": "R"},
             "inc": {"key": "H|Hillsborough|30", "k": "sitting", "p": "R"},
             "perez": {"key": "H|Hillsborough|43", "k": "former", "p": "D"}}
    back = {n: LP.elect_back(m, infos[n]) for n, m in
            (("vose", vose), ("creighton", creighton), ("inc", inc), ("perez", perez))}
    if (back["vose"] or {}).get("mode") != "returning" \
            or (back["creighton"] or {}).get("mode") != "chamber" or back["inc"] is not None:
        bad.append(f"elect_back says {[(n, (b or {}).get('mode')) for n, b in back.items()]}: "
                   "returning, chamber and none wanted")
    elif back["vose"]["head"] != "Michael Vose (R), member-elect" or back["vose"]["where"] != (
            "Member-elect of the New Hampshire House of Representatives, Rockingham 6.") \
            or back["creighton"]["where"] != "Member-elect of the New Hampshire Senate, Senate District 8."             or (back["vose"].get("title"), back["creighton"].get("title")) != ("Rep.-elect", "Sen.-elect"):
        bad.append(f"elect_back words: {back['vose']} {back['creighton']}")
    if LP.elect_back(dict(vose, former=False), infos["vose"]) is not None:
        bad.append("a file's former member drawn on a record that is not former.json's gets the "
                   "returning form")
    base = {"election": "2026-11-03", "takes_office": "2026-12-02"}

    def g(name, mem, far=False):
        # The reader's clock is the real one: a day far ahead is "before they
        # take office", a day long past is "after".
        d = {"id": mem["id"], "key": infos[name]["key"], **base,
             **{k: back[name][k] for k in ("mode", "name", "party", "where", "title")}}
        # The page goes back by "until", the day after they take office (the owner, 25
        # November 2026).
        return dict(d, takes_office="2999-01-01" if far else "2000-01-01",
                    until="2999-01-02" if far else "2000-01-02")
    line = "Elected November 3, 2026. Takes office December 2, 2026."
    exprs = [
        # 0 the returning member, 1 the same once the day has come, 2 with no GR_ELECT,
        # 3 another member's page with Vose's GR_ELECT, 4 new-chamber, 5 that on a gone day
        "(window.GR_ELECT=" + json.dumps(g("vose", vose, far=True)) + ", scope.renderMemberHead("
        + json.dumps(vose) + "))",
        "(window.GR_ELECT=" + json.dumps(g("vose", vose)) + ", scope.renderMemberHead("
        + json.dumps(vose) + "))",
        "(delete window.GR_ELECT, scope.renderMemberHead(" + json.dumps(vose) + "))",
        "(window.GR_ELECT=" + json.dumps(g("vose", vose, far=True)) + ", scope.renderMemberHead("
        + json.dumps(dict(vose, id="1")) + "))",
        "(window.GR_ELECT=" + json.dumps(g("creighton", creighton, far=True))
        + ", scope.renderMemberHead(" + json.dumps(creighton) + "))",
        "(window.GR_ELECT=" + json.dumps(g("creighton", creighton)) + ", scope.renderMemberHead("
        + json.dumps(creighton) + "))",
        # 6 a returning member elected under another party than the record's, 7 her page without
        # GR_ELECT
        "(window.GR_ELECT=" + json.dumps(g("perez", perez, far=True)) + ", scope.renderMemberHead("
        + json.dumps(perez) + "))",
        "(delete window.GR_ELECT, scope.renderMemberHead(" + json.dumps(perez) + "))",
        # 8 the returning member with no span on record, only the days they served
        "(window.GR_ELECT=" + json.dumps(g("vose", vose, far=True)) + ", scope.renderMemberHead("
        + json.dumps(dict(vose, attendance={}, served={"first": "1/4/2017", "last": "12/5/2018"}))
        + "))"]
    got = _app_js("[" + ", ".join(exprs) + "]", names=("renderMemberHead",))
    if got is not None:
        ret, gone, plain, other, cham, cgone, pret, pplain, rbare = got
        said = back["vose"]["where"]
        for what, ok in (
                ("the returning page says the seat of the member-elect", said in ret),
                ("the returning page has the new member-elect's election line, no district",
                 "Elected November 3, 2026. Takes office" in ret and "for Rockingham" not in ret),
                ("the returning page leaves out the directory-entry note while it shows, and "
                 "the former form brings it back",
                 "not a current directory entry" not in ret and "not a current directory entry" in gone),
                ("the returning page keeps the earlier seat", "Earlier seat" in ret
                 and "Rep. Michael Vose (R - Rock 5)" in ret),
                ("the returning page is not titled Former Representative",
                 "Former Representative" not in ret and "Michael Vose (R)" in ret),
                # TITLED AS A MEMBER-ELECT (the owner, 16 November 2026: "use their title as
                # Rep. "Elect" Heather Denier instead of just their first name"), spelled out
                # as a member's page spells its title.
                ("the returning page is headed with the member-elect's title",
                 '<h1 class="rh1">Representative-elect Michael Vose (R)</h1>' in ret
                 and '<h1 class="rh1">Former Representative Michael Vose' in gone),
                ("the returning page is Member-elect in its trail", "Member-elect" in ret),
                ("once the day is theirs the page is the former member's as before",
                 said not in gone and "Former Representative Michael Vose" in gone),
                ("without GR_ELECT the page is the former member's",
                 "Former Representative Michael Vose" in plain and said not in plain),
                ("another member's page is told nothing of Vose's election",
                 said not in other and "Elected November 3" not in other),
                # HEADED AS THE OTHER CHAMBER'S MEMBER-ELECT (the owner, 17 November 2026: 'link
                # the new member pages as Sen. "Elect" Laura Telerski for the title but connect it
                # to their house record as well'), the seat held now on the line, by its office.
                ("the new-chamber member is headed as the Senate's member-elect and keeps the "
                 "seat they hold on the line",
                 '<h1 class="rh1">Senator-elect James Creighton (R)</h1>' in cham
                 and "Representative for Hillsborough District&nbsp;30" in cham),
                ("the new-chamber member's page is theirs again with the day",
                 "Representative James Creighton" in cgone and not re.search(r"\b(?:Rep\.|Sen\.|Representative|Senator)-elect\b", cgone)
                 and "Representative for" not in cgone),
                ("the new-chamber member has the sentence beside it",
                 back["creighton"]["where"] in cham),
                ("the new-chamber member's election line names the district",
                 "Elected November 3, 2026, for Senate District 8." in cham),
                ("the new-chamber member's sentence is gone with the day",
                 back["creighton"]["where"] not in cgone),
                ("the returning page keeps the years on record, and the years of their "
                 "service where the record gives no span",
                 "<dt>On Record</dt><dd>House, 2017&ndash;2018</dd>" in ret
                 and "<dt>On Record</dt><dd>2017 to 2018</dd>" in rbare),
                # The heading says the party she was elected under, and its bar is that
                # party's ink; the earlier seat keeps the record's own label.
                ("a returning member elected under another party is drawn in its ink",
                 "Representative-elect Maria Perez (D)" in pret and "rh-pD" in pret and "rh-pI" not in pret
                 and "Rep. Maria Perez (I - Hills 43)" in pret),
                ("without the election her page keeps the record's party",
                 "rh-pI" in pplain and "rh-pD" not in pplain)):
            if not ok:
                bad.append(what)
    # The plain page, for a reader without script: the same form, with the years app.js gives
    # (the review before the release of 16 November 2026: the 25 returning pages had none).
    until = LP.until_attrs("2026-12-03", "2026-11-20")
    plain_html = LP.static_record(vose, vose, LP.elect_line(None, "2026-11-03", "2026-12-02",
                                                           "2026-11-20", "2026-12-03"), {},
                                  back["vose"], until)
    for want in ("<h1>Representative-elect Michael Vose (R)</h1>", f"<p>{back['vose']['where']}</p>", line,
                 "<p>Earlier seat: Rep. Michael Vose (R - Rock 5)</p>",
                 "<li><b>On record:</b> House, 2017–2018</li>"):
        if want not in plain_html:
            bad.append(f"the plain page lacks {want!r}")
    # And where the record gives no span, the years of their service, as app.js falls back to.
    bare = dict(vose, attendance={}, served={"first": "1/4/2017", "last": "12/5/2018"})
    if "<li><b>On record:</b> 2017 to 2018</li>" not in LP.static_record(bare, bare, "", {},
                                                                          back["vose"], until):
        bad.append("the plain page of a returning member with no span on record gives no years")
    # THE FACT IS THE MEMBERS-ELECT FILE'S (_elect_pages_never_sitting): drawn inside what carries
    # data-elect and the day it retires, the list itself where it holds nothing else, so the page
    # once that is taken out is the former member's, whose sentence carries the years.
    counted = dict(vose, counts={"Yea": 3})
    with_counts = LP.static_record(counted, counted, "", {}, back["vose"], until)
    for name, html in (("alone", plain_html), ("beside the roll call counts", with_counts)):
        if "On record:" in _elect_strip(html) or not re.search(
                r'<(?:ul|li)\b[^>]*\sdata-elect data-until="2026-12-03"[^>]*>(?:<li>)?<b>On record:</b> '
                r'House, 2017–2018</li>', html):
            bad.append(f"the plain returning page's On record fact, {name}, is not inside what "
                       f"carries data-elect and its day: {html[:400]}")
    if "Recorded roll call votes:</b> Yea 3" not in _elect_strip(with_counts):
        bad.append("taking the members-elect file's fact out takes the roll call counts with it")
    if "not a current directory entry" in plain_html:
        bad.append("the plain page of a returning member-elect says it is not a current directory entry")
    if "Former Representative" in plain_html:
        bad.append("the plain page of a returning member is headed Former Representative")
    cham_html = LP.static_record(creighton, {}, "", {}, back["creighton"])
    if "<h1>Senator-elect James Creighton (R)</h1>" not in cham_html \
            or back["creighton"]["where"] not in cham_html \
            or "<p>Serving now: Rep. James Creighton (R - Hills 30)</p>" not in cham_html:
        bad.append("the plain page of a new-chamber member is not headed as the Senate's member-elect, "
                   "or lacks the sentence or the seat they hold now")
    # A former member's page offers their requests, as a sitting member's: the
    # requests term first when they have any (build_lsrs' by_slug).
    req = {"term": "2027-requests", "label": "2027 Bill Requests", "year": 2027, "n": 1,
           "withdrawn": 0, "by_slug": {"michael-vose-rock-5": 1}}
    row = {"id": "LSR20270003", "n": "LSR 2027-0003", "year": 2027, "title": "relative to roads.",
           "sponsor": "x", "sponsor_label": "x", "sponsor_slug": "michael-vose-rock-5", "body": "HB",
           "body_label": "House bill", "committee": "", "committees": [], "topic": "", "kind": "",
           "status": "Filed as a request", "withdrawn": False, "term": "2027-requests", "lsr": True,
           "votedays": [], "last_action": ""}
    fm = dict(vose, sponsored=[{"id": "HB1", "term": "2017-2018", "prime": True}], votes=[],
              term_figures={}, attendance={})
    js = ("scope.setMeta(" + json.dumps({"terms": ["2025-2026"], "requests": req}) + "), scope.setIdx("
          + json.dumps([row]) + "), scope.addLoaded('2027-requests'), (() => { const m = "
          + json.dumps(fm) + "; const terms = scope.recordTerms('member', m); scope.setPage({kind: "
          "'member', data: m, terms, term: terms[0]}); return {terms, "
          "prime: scope.renderMemberBills(m, true)}; })()")
    fr = _app_js(js, names=("recordTerms", "renderMemberBills", "setPage: x => (PAGE = x)",
                            "setMeta: x => (META = x)", "setIdx: x => (IDX = x)",
                            "addLoaded: t => LOADED.add(t)"))
    if fr is not None and (fr["terms"][0] != "2027-requests"
                           or 'data-id="LSR20270003"' not in fr["prime"]):
        bad.append(f"a returning member's page does not open on the requests: {fr['terms']}")
    # A provisional page shows the requests it is matched to, and a returning
    # or new member-elect's earlier service where the person confirmed it.
    p = {"slug": "w-gordon-allen-hills-30", "name": "W. Gordon Allen", "party": "R", "chamber": "H",
         "county": "Hillsborough", "district": "30", "race": "H|Hillsborough|30", "towns": [],
         "prior": {"terms": ["1993-1994", "1995-1996"], "seat": "Hillsborough 1"}}
    body = LP.elect_body(p, dict(base, sources=[]), [dict(row, sponsor_slug=p["slug"])],
                         {"label": "2027 Bill Requests", "year": 2027, "term": "2027-requests"},
                         {}, "2026-11-20")
    # Each term as a reader sees one, with an en dash (components.term_words): W. Gordon Allen's
    # read "1993-1994, 1995-1996, 1997-1998", the hand file's keys. A fact of the page's head
    # since 16 November 2026, when the page became a member's (_elect_page_member_form).
    if "LSR 2027-0003" not in body or \
            "<dt>Earlier service</dt><dd>Hillsborough 1, 1993–1994, 1995–1996</dd>" not in body:
        bad.append(f"a provisional page does not show its requests and earlier service: {body[:300]}")
    assert not bad, "; ".join(bad)
    return "ok", ("the tab links every new member-elect with a page; a returning member's page is "
                  "the member-elect's with the earlier seat kept and its years on record on the "
                  "plain page as in app.js, its bar in the elected party's ink; a new-chamber "
                  "member's headed as the Senate's member-elect with its seat held now beside it, "
                  "both end with the day; requests show on the former's "
                  "and the provisional page, its earlier terms with an en dash"
                  + ("" if got is not None else " (node not here for the page's script)"))


@check("build", "a sitting member elected to the other chamber is that chamber's member-elect, Sen.-elect "
                "Laura Telerski, joined to the record they sit under now: on the Members-Elect "
                "tab, in the search in place of their own row until the day they take office, and on "
                "their page", needs=("build_indexes", "officials_tabs", "build_legislator_pages"))
def _elect_other_chamber_joined(BI, OT, LP):
    """The owner, 17 November 2026: 'You should link the new member pages as Sen. "Elect" Laura
    Telerski for the title but connect it to their house record as well.' Laura Telerski sits for
    Hillsborough 11 and was elected to the Senate for District 13; the General Court numbers her as a
    senator when its roster turns, and until then the record she has is her House one. Held, the
    build's day stated:

      - the Officials page's Members-Elect tab: "Sen.-elect Laura Telerski (D - SD13)", linked to
        her House page;
      - the search (find_index): one row of the kind "elect", "Sen.-elect Laura Telerski (D -
        SD13)", "Senate · SD13 · Democrat", leading to her House page, her House row's words and seat
        among its words and that row carried whole with the day she takes office -- and her own row
        not beside it; a member re-elected to their own seat, and one elected to another seat of
        their own chamber, keep their rows; from that day, by the build's day her own row is back,
        and by the reader's day from a find.json built before it (find.js findNow);
      - her page: headed "Senator-elect Laura Telerski (D)" (elect_back's title spelled out), the
        sentence of her election and the seat she holds now beside it, on the plain page and in
        app.js's renderMemberHead, which is her House record's head again once the day is hers."""
    import contextlib
    import io
    root = Path(tempfile.mkdtemp(prefix="gr-elect-chamber-"))
    saved = os.environ.get("GRANITE_BUILD_DATE")
    me = {"n": "Laura Telerski", "p": "D", "k": "sitting", "id": "9117", "s": "laura-telerski-hills-11"}

    def race(*won):
        return {"seats": len(won), "not_final": 0, "held": 0, "elected": list(won)}
    legs = [{"display_full": f"Rep. {f} {l} (D - Hills {d})", "chamber": "H", "district_label": f"Hills {d}",
             "party": "Democrat", "slug": f"{f.lower()}-{l.lower()}-hills-{d}", "last": l, "first": f,
             "county": "Hillsborough", "email": f"{f}.{l}@x"}
            for f, l, d in (("Laura", "Telerski", 11), ("Kathy", "Staub", 25), ("Jo", "Moves", 12))]
    try:
        site = root / "site"
        site.mkdir()
        (site / "elect_pages.json").write_text(json.dumps(
            {"election": "2026-11-03", "takes_office": "2026-12-02", "sources": [], "pages": [], "moved": {}}),
            encoding="utf-8")
        (site / "members_elect.json").write_text(json.dumps(
            {"election": "2026-11-03", "takes_office": "2026-12-02", "term": "2027-2028", "sources": [],
             "races": {"S|13": race(me),
                       "H|Hillsborough|25": race({"n": "Kathy Staub", "p": "D", "k": "sitting", "id": "1",
                                                  "s": "kathy-staub-hills-25", "own": True}),
                       "H|Hillsborough|30": race({"n": "Jo Moves", "p": "D", "k": "sitting", "id": "2",
                                                  "s": "jo-moves-hills-12"})}}), encoding="utf-8")
        (site / "meta.json").write_text(json.dumps({"terms": ["2025-2026"], "topics": []}), encoding="utf-8")
        (site / "former.json").write_text("[]", encoding="utf-8")
        got = {}
        for day in ("2026-11-20", "2026-12-02", "2026-12-03"):
            os.environ["GRANITE_BUILD_DATE"] = day
            with contextlib.redirect_stdout(io.StringIO()):
                got[day] = [r for r in BI.find_index(site, legs, {}) if r[0] in ("legislator", "elect")]
    finally:
        if saved is None:
            os.environ.pop("GRANITE_BUILD_DATE", None)
        else:
            os.environ["GRANITE_BUILD_DATE"] = saved
        shutil.rmtree(root, ignore_errors=True)
    hers = "legislator/laura-telerski-hills-11"
    own = ["legislator", "Rep. Laura Telerski (D - Hills 11)", "House · Hills 11 · Democrat", hers,
           "Telerski Laura Hillsborough Laura.Telerski@x"]
    # Organization Day's night is the day before's (the owner, 25 November 2026: "wait until
    # December 3rd to switch to the new titles"); the day after is hers.
    assert got["2026-12-02"] == got["2026-11-20"], f"her rows on Organization Day: {got['2026-12-02']}"
    before, after = got["2026-11-20"], got["2026-12-03"]
    mine = [r for r in before if r[3] == hers]
    assert mine == [["elect", "Sen.-elect Laura Telerski (D - SD13)", "Senate · SD13 · Democrat", hers,
                     "Laura Telerski Telerski Laura Hillsborough Laura.Telerski@x Hills 11 "
                     "member-elect sen-elect senator-elect", "2026-12-03", own]], (
        f"her rows in the search before she takes office: {mine}")
    assert [r[0] for r in before if r[3] != hers] == ["legislator", "legislator"] and \
        [r[0] for r in after] == ["legislator"] * 3 and [r for r in after if r[3] == hers] == [own], (
        f"the other members' rows, or hers from the day she takes office: {before} {after}")
    if shutil.which("node"):
        tmp = Path(tempfile.mkdtemp(prefix="gr-elect-chamber-js-"))
        try:
            (tmp / "stub.js").write_text(_source("tests/dom_stub.js"), encoding="utf-8")
            (tmp / "find.js").write_text(_with_components(_source("src/pages/find.js")), encoding="utf-8")
            (tmp / "go.js").write_text(
                'require("./stub.js");\nconst src = require("fs").readFileSync("./find.js", "utf8");\n'
                'const s = (0, eval)(src + "; ({findNow})");\n'
                f'const rows = {json.dumps(before)};\n'
                'process.stdout.write("@@" + JSON.stringify([s.findNow(rows, "2026-12-02"), '
                's.findNow(rows, "2026-12-03")]));\n', encoding="utf-8")
            r = _run(["node", "go.js"], cwd=tmp, capture_output=True, text=True, timeout=60)
            assert r.returncode == 0 and "@@" in r.stdout, (r.stderr or r.stdout)[-300:]
            eve, day = json.loads(r.stdout.rsplit("@@", 1)[1])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        assert [x for x in eve if x[3] == hers] == mine and [x for x in day if x[3] == hers] == [own], (
            f"by the reader's day her row is {[x for x in day if x[3] == hers]}")
    # The Members-Elect tab.
    chip = OT.elect_chip(me, "S|13")
    assert "Sen.-elect Laura Telerski" in chip and f'legislator/laura-telerski-hills-11"' in chip, chip
    # Her page: the plain one and app.js's head.
    m = {"id": "9117", "name": "Telerski, Laura", "chamber": "H", "party": "Democrat", "county": "Hillsborough",
         "district": "11", "display_plain": "Rep. Laura Telerski", "display_full": "Rep. Laura Telerski (D - Hills 11)",
         "slug": "laura-telerski-hills-11", "towns": ["Nashua Ward 3"], "committees": []}
    back = LP.elect_back(m, {"key": "S|13", "k": "sitting", "p": "D"})
    assert back and back["mode"] == "chamber" and back["title"] == "Sen.-elect" \
        and back["name"] == "Laura Telerski", back
    plain = LP.static_record(m, {}, "", {}, back)
    for want in ("<h1>Senator-elect Laura Telerski (D)</h1>",
                 "<p>Member-elect of the New Hampshire Senate, Senate District 13.</p>",
                 "<p>Serving now: Rep. Laura Telerski (D - Hills 11)</p>", "Nashua Ward 3"):
        assert want in plain, f"her plain page lacks {want!r}: {plain[:500]}"

    def ge(far):
        return {"id": "9117", "key": "S|13", "election": "2026-11-03",
                "takes_office": "2999-01-01" if far else "2000-01-01",
                "until": "2999-01-02" if far else "2000-01-02",
                **{k: back[k] for k in ("mode", "name", "party", "where", "title")}}
    heads = _app_js("[" + ", ".join(f"(window.GR_ELECT={json.dumps(ge(far))}, scope.renderMemberHead("
                                    f"{json.dumps(m)}))" for far in (True, False)) + "]",
                    names=("renderMemberHead",))
    if heads is not None:
        now, gone = heads
        assert '<h1 class="rh1">Senator-elect Laura Telerski (D)</h1>' in now \
            and "Representative for Hillsborough District&nbsp;11" in now and back["where"] in now, now[:900]
        assert not re.search(r"\b(?:Rep\.|Sen\.|Representative|Senator)-elect\b", gone) and "Representative Laura Telerski" in gone \
            and back["where"] not in gone, gone[:600]
    return "ok", ("the tab, the search's one row in place of hers (back by the build's and the reader's "
                  "day she takes office) and her page all Sen.-elect Laura Telerski, joined to her House "
                  "record and its seat; a member re-elected, or elected within the House, as before"
                  + ("" if heads is not None else "; node not here for the page's script"))


@check("build", "a legislator's search description names the seat once and the places first",
       needs=("build_legislator_pages",))
def _legislator_description(BL):
    """All 406 read "Rep. Aboul Khan (R - Rock 30) Rock 30." under the link
    until 13 September: display_full carries the seat and it was appended again."""
    m = {"display_full": "Rep. Michael Aron (R - Sull 8)", "district_label": "Sull 8", "chamber": "H",
         "towns": ["Acworth", "Claremont Ward 10", "Claremont Ward 2", "Croydon", "Goshen",
                   "Langdon", "Lempster", "Newport", "Unity"]}
    d = BL.describe(m)
    assert d.count("Sull 8") == 1, d
    assert d.startswith("Rep. Michael Aron (R - Sull 8) represents Acworth, Claremont Ward 2, "
                        "Claremont Ward 10,"), d
    assert "and 3 more" in d, d
    seven = dict(m, towns=m["towns"][:7])
    assert "more" not in BL.describe(seven) and " and Lempster in" in BL.describe(seven), BL.describe(seven)
    return "ok", "seat once, places first, wards in number order"


# The members for _former_heading: Michael Gunski as former.json carries him,
# a representative who left in 2021; Jeb Bradley's Senate record joined to his
# House years, as member_links joins a sitting member's two numbers, so the
# office he last held is the Senate; a member the record could not name; and
# Jodi Nelson, who sits.
_FORMER_HEADING_MEMBERS = {
    "former": [
        {"id": "9180", "name": "Gunski, Michael", "chamber": "H", "party": "R",
         "party_code": "R", "county": "Hillsborough", "county_abbr": "Hills",
         "district": "6", "district_label": "Hills 6", "display_plain": "Rep. Michael Gunski",
         "display": "Rep. Michael Gunski (R)", "display_full": "Rep. Michael Gunski (R - Hills 6)",
         "slug": "michael-gunski-hills-6", "former": True, "towns": [], "email": "",
         "served": {"first": "1/2/2019", "last": "6/24/2021",
                    "terms": ["2019-2020", "2021-2022"]}},
        {"id": "36", "name": "Bradley, Jeb", "chamber": "S", "party": "R",
         "party_code": "R", "county": "Carroll", "county_abbr": "Carr", "district": "3",
         "district_label": "SD3", "display_plain": "Sen. Jeb Bradley",
         "display": "Sen. Jeb Bradley (R)", "display_full": "Sen. Jeb Bradley (R - SD3)",
         "slug": "jeb-bradley-sd-3", "former": True, "towns": [], "email": "",
         "served": {"first": "1/28/1999", "last": "10/10/2024"},
         "member_ids": ["36", "374827"],
         "service": [{"chamber": "H", "spans": [[1999, 2002]]},
                     {"chamber": "S", "spans": [[2009, 2024]]}]},
        {"id": "377204", "name": "Member #377204", "chamber": "H",
         "display_plain": "Member #377204", "display": "Member #377204",
         "display_full": "Member #377204", "slug": "member-377204", "former": True,
         "towns": [], "email": "", "served": {"first": "1/4/2023", "last": "6/1/2023"}},
    ],
    "sitting": [
        {"id": "10440", "name": "Nelson, Jodi", "chamber": "H", "party": "R",
         "party_code": "R", "county": "Rockingham", "county_abbr": "Rock",
         "district": "13", "district_label": "Rock 13", "display_plain": "Rep. Jodi Nelson",
         "display": "Rep. Jodi Nelson (R)", "display_full": "Rep. Jodi Nelson (R - Rock 13)",
         "slug": "jodi-nelson-rock-13", "towns": ["Derry"], "n_votes": 0,
         "n_sponsored": 0},
    ],
}

# app.js's own drawing of each member's heading, and of the chip every list
# draws them with.
def _in_full(name):
    """"Former Rep. Michael Gunski" -> "Former Representative Michael
    Gunski": the heading at the top of a member's own page (9 October 2026)."""
    return re.sub(r"^(Former )?(Rep|Sen)\. ",
                  lambda g: (g.group(1) or "") + {"Rep": "Representative",
                                                   "Sen": "Senator"}[g.group(2)] + " ", name)


_FORMER_HEADING_JS = r"""
require("./stub.js");
const fs = require("fs");
const M = JSON.parse(fs.readFileSync("./members.json", "utf8"));
const scope = (0, eval)(fs.readFileSync("./app.js", "utf8") + ";({renderMemberHead, pchip})");
const out = {};
for (const m of [...M.former, ...M.sitting])
  out[m.id] = {head: scope.renderMemberHead(m), chip: scope.pchip(m)};
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("build", "a former member's own page is named \"Former Rep.\" or \"Former Sen.\" and "
                "headed with the title in full, and nothing else names them so",
       needs=("build_legislator_pages",))
def _former_heading(BL):
    """The person settled it in September: a legislator who has left is
    written "Former Rep. David Smith" -- the word joining the honorific, in
    the name itself, never a chip, badge or pill beside it -- in exactly two
    places, their own page and search results. Search did (find.json); the
    page's heading read "Rep. Michael Gunski (R - Hills 6)" with "Former
    member · on record 2019 to 2021" in a line under it.

    So app.js's heading, and the title, link card and no-script heading
    build_legislator_pages writes, now read "Former Rep. Michael Gunski (R -
    Hills 6)", and the line under it gives only the years. The honorific is
    the record's own, the office last held: a senator whose record carries
    House years is "Former Sen.". A member the record could not name keeps
    "Member #377204" and the line keeps "Former member". A sitting member is
    untouched, and so is the chip every roll call, sponsor list and roster
    draws a member with. Nothing on the page says why anybody left.

    THE HEADING SPELLS THE TITLE OUT (the person, 9 October 2026: "Member
    pages should list their title along with their name at the top like
    Senator Sharon Carson or Representative James Spillane"). The heading at
    the top of the page, app.js's and the no-script one, reads "Former
    Representative Michael Gunski (R - Hills 6)" and, for a sitting member,
    "Representative Jodi Nelson (R - Rock 13)"; the title, the link card and
    search keep "Former Rep." and "Rep.", as every list does. The word still
    joins the honorific.
    """
    here = Path(".").resolve()
    need = ("build_legislator_pages.py", "bills.html", "app.js", "dom_stub.js")
    absent = [f for f in need if not _paths.locate(f).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    M = _FORMER_HEADING_MEMBERS
    want = {"9180": "Former Rep. Michael Gunski (R - Hills 6)",
            "36": "Former Sen. Jeb Bradley (R - SD3)",
            "377204": "Member #377204",
            "10440": "Rep. Jodi Nelson (R - Rock 13)"}
    years = {"9180": "2019 to 2021", "36": "1999 to 2024", "377204": "2023"}
    root = Path(tempfile.mkdtemp(prefix="gr-former-"))
    try:
        site = root / "site"
        site.mkdir()
        shutil.copy2(here / "src/pages/bills.html", site / "bills.html")
        (site / "legislators.json").write_text(json.dumps(M["sitting"]), encoding="utf-8")
        (site / "former.json").write_text(json.dumps(M["former"]), encoding="utf-8")
        r = _run([sys.executable, _paths.script("build_legislator_pages.py"), "--site", "site",
                  "--base", "https://x.test"], cwd=root, capture_output=True, text=True,
                 timeout=120)
        assert r.returncode == 0, "build_legislator_pages.py: " + (r.stderr or r.stdout).strip()[-200:]
        pages = {m["id"]: (site / "legislator" / f"{m['slug']}.html").read_text(encoding="utf-8")
                 for m in M["former"] + M["sitting"]}
        drawn = None
        if shutil.which("node"):
            for f, text in (("app.js", _with_components(
                                (here / "src/pages/app.js").read_text(encoding="utf-8"), here)),
                            ("stub.js", (here / "tests/dom_stub.js").read_text(encoding="utf-8")),
                            ("members.json", json.dumps(M)), ("go.js", _FORMER_HEADING_JS)):
                (root / f).write_text(text, encoding="utf-8")
            r = _run(["node", "go.js"], cwd=root, capture_output=True, text=True, timeout=60)
            assert r.returncode == 0 and "@@" in (r.stdout or ""), (
                "app.js did not draw the heads under node: " + (r.stderr or r.stdout or "")[-300:])
            drawn = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)

    def between(text, a, b):
        i = text.find(a)
        return text[i + len(a):text.find(b, i + len(a))] if i >= 0 else None

    bad = []
    for mid, name in want.items():
        page = pages[mid]
        plain = re.sub(r"^Former ", "", name)
        got = {"title": between(page, "<title>", "</title>"),
               "link card": between(page, 'property="og:title" content="', '"'),
               # The plain record a reader without scripts reads (static_record,
               # which replaced the <noscript> block on 12 October 2026).
               "no-script heading": between(between(page, '<div class="static-rec" id="static-rec">',
                                                    "</div>") or "", "<h1>", "</h1>")}
        want_of = {"title": f"{name} | Granite Record", "link card": name,
                   "no-script heading": _in_full(name)}
        bad += [f"member {mid}'s {k} reads {got[k]!r}, not {want_of[k]!r}"
                for k in got if got[k] != want_of[k]]
        # Nothing else on the built page changes: the search description and
        # the structured data still name them as the record does.
        desc = between(page, '<meta name="description" content="', '"') or ""
        if not desc.startswith(plain):
            bad.append(f"member {mid}'s search description begins {desc[:60]!r}")
        ld = between(page, '<script type="application/ld+json">', "</script>") or ""
        if '"name":"Former ' in ld.replace('": "', '":"'):
            bad.append(f"member {mid}'s structured data calls them Former in the name")
        ns = between(page, '<div class="static-rec" id="static-rec">', "</div>") or ""
        if mid in years:
            if years[mid] not in ns:
                bad.append(f"member {mid}'s no-script page lost the years {years[mid]}")
            if ("Former member" in ns) != (not name.startswith("Former ")):
                bad.append(f"member {mid}'s no-script line says 'Former member' "
                           + ("twice over the heading" if name.startswith("Former ")
                              else "nowhere, and its heading cannot"))
    assert not bad, "; ".join(bad[:3])

    if drawn is None:
        return "ok", ("the built title, link card and no-script heading, the title in full "
                      "in the heading (node not here to draw app.js's)")
    for mid, name in want.items():
        head = drawn[mid]["head"]
        # Read as a reader reads it: the party and seat are a span of their
        # own (.ptag), kept whole where the heading wraps.
        # THE RECORD HEAD (C6, 10 October 2026), as the approved prototype
        # draws it: the title in full and the name in the heading, as the
        # person wrote them ("Senator Sharon Carson"), and the party and seat
        # in words on the line under it; the years in the facts, or in the
        # note under the head of a member the record could not name.
        h1 = re.sub(r"<[^>]+>", "", between(head, '<h1 class="rh1">', "</h1>") or "")
        if h1 != re.sub(r"\s+\([^()]*\)$", "", _in_full(name)):
            bad.append(f"app.js heads member {mid} {h1!r}, not {_in_full(name)!r}")
        import html as _html
        said = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", head)))
        if "(R - " in name and "Republican" not in (between(head, '<p class="rline">', "</p>") or ""):
            bad.append(f"the line under member {mid}'s heading does not name the party: {said[:200]!r}")
        if mid in years:
            # The first and the last year on record, whether as one span or,
            # for a member who sat in both chambers, the record's own spans
            # by chamber ("House, 1999–2002 · Senate, 2009–2024").
            if not all(y in said for y in years[mid].split(" to ")):
                bad.append(f"app.js's head of member {mid} lost the years: {said[:300]!r}")
            if ("Former member" in said) != (not name.startswith("Former ")):
                bad.append(f"app.js's head of member {mid} reads {said[:300]!r}")
        elif 'class="rnote"' in head:
            bad.append(f"app.js marks sitting member {mid} as former")
        # The chip is how a roll call, a sponsor list and a roster draw them.
        chip = drawn[mid]["chip"]
        # Its words, read as a reader reads them: the party and district are a
        # span of their own (pchip's .mtag, so a chip that wraps keeps them whole).
        said = re.sub(r"<[^>]+>", "", chip)
        if "Former" in said or re.sub(r"^Former ", "", name) not in said:
            bad.append(f"the chip for member {mid} reads {chip!r}")
        why = re.findall(r"\b(died|deceased|death|resign\w*|retire\w*|defeat\w*|lost)\b",
                         head, re.I)
        if why:
            bad.append(f"member {mid}'s heading says why they left: {why}")
    assert not bad, "; ".join(bad[:3])
    return "ok", ("\"Former Rep.\" and \"Former Sen.\" (the office last held) in the title and "
                  "link card, \"Former Representative\" and \"Former Senator\" in the headings, "
                  "the years in the line under it; a sitting member headed \"Representative\"; "
                  "an unnamed member and every chip as they were")


@check("narrative", "a past member's label gives up their name and district",
       needs=("past_members",))
def _past_member_label(past_members):
    """Real options from the General Court's own list of everyone who served.

    Two of these break the obvious parse. "Battles(-Peirce), Marjorie(Rock.
    18)" carries a parenthesis inside the SURNAME, so the district has to be
    read from the last bracket rather than the first -- a non-greedy match
    calls that member's district "-Peirce". And "Barnes, Jr., John(Dist. 17)"
    carries a suffix, so the name is not two comma-separated fields.

    A senator has a district and no county; a representative has both.
    """
    q = past_members.parse
    assert q("Rep. Vartanian, Elsie(Rock. 20)") == {
        "name": "Vartanian, Elsie", "chamber": "H", "county": "Rock",
        "district": "20", "party": ""}
    assert q("Sen. Blaisdell, Clesson(Dist. 10)") == {
        "name": "Blaisdell, Clesson", "chamber": "S", "county": "",
        "district": "10", "party": ""}
    assert q("Rep. Battles(-Peirce), Marjorie(Rock. 18)")["district"] == "18"
    assert q("Rep. Battles(-Peirce), Marjorie(Rock. 18)")["name"] == \
        "Battles(-Peirce), Marjorie"
    assert q("Sen. Barnes, Jr., John(Dist. 17)")["name"] == "Barnes, Jr., John"
    assert q("Rep. Albert, Russell(Straf 01)")["district"] == "01", \
        "a leading zero is how former_members.json writes a district"
    # No party is ever invented. The list does not carry one, and a member
    # named only from here votes without a party letter rather than with a
    # guessed one.
    assert all(q(s)["party"] == "" for s in (
        "Rep. Vartanian, Elsie(Rock. 20)", "Sen. Barnes, Jr., John(Dist. 17)"))
    assert q("not a legislator") == {}
    return "ok", "six real labels, two of which break the obvious parse"


@check("narrative", "a sponsor row gives up its bill, its LSR and its title",
       needs=("fetch_sponsors_by_member",))
def _sponsor_rows(fetch_sponsors_by_member):
    """Real markup from byAnyMember.aspx, kept because it is not what it looks like.

    Rendered, that page is a four-column table. In the HTML the four fields
    are DIVs inside a single <td>, and a parser written from the rendered
    shape finds nothing at all -- which is exactly what the first draft of
    this one did. The header row carries the same four divs, so rows are
    keyed on the presence of a billinfo link rather than on position.

    The LSR is the point of the whole route: Pastid is the LSR with the
    session year stuck on the end, so HB750 of 1989 joins data/bills.json on
    lsr_num 1171 rather than on a guess at which "Rep. Allard" is meant.
    """
    page = (
        '<table><tr><td><div class="container"><div class="row">'
        '<div class="col-sm-2 font-weight-bold">Year</div>'
        '<div class="col-sm-2 font-weight-bold">Bill #</div>'
        '<div class="col-sm-2 font-weight-bold">Status</div>'
        '<div class="col-sm font-weight-bold">Title</div>'
        '</div></div></td></tr>'
        '<tr><td><div class="container"><div class="row">'
        '<div class="col-sm-2">\n    1989\n</div>'
        '<div class="col-sm-2"><a href="billinfo.aspx?sy=1989&amp;'
        'Pastid=11711989&amp;id=99999" class="link-primary">HB750\n</a></div>'
        '<div class="col-sm-2">&nbsp;SIGNED BY GOVERNOR</div>'
        '<div class="col-sm"><b>title:</b>&nbsp;(New Title) establishing a '
        'redevelopment commission relative to Pease Air  Force Base.</div>'
        '</div></div></td></tr></table>')
    rows = fetch_sponsors_by_member.parse_rows(page)
    assert len(rows) == 1, f"{len(rows)} rows; the header must not parse as a bill"
    r = rows[0]
    assert r["bill"] == "HB750", r
    assert r["year"] == "1989", r
    assert r["lsr"] == "1171", ("Pastid is the LSR with the year on the end, "
                                "and the LSR is the join key: " + repr(r))
    assert r["status"] == "SIGNED BY GOVERNOR", r
    assert r["title"].startswith("(New Title) establishing"), r
    assert "title:" not in r["title"], r
    return "ok", "one row, header skipped, LSR 1171 off the link"


@check("data", "a solved voter is one person, and nobody else's")
def _solved_voters():
    """member_party.json pins 38 voters by constraint rather than by roster.

    The method is measured in fetch_rollcall_parties.solve: 286 people whose
    answer was already known were hidden and it returned 286 right and 0
    wrong. This is the standing guard on the file that came out of it, because
    the failure it would cause is silent -- one member's ballots filed under
    another's name, which is the same failure "every voter in the record is
    one person" exists to catch, arriving from a different direction.

    Two things must hold. A solved entry must not claim a person the General
    Court's own list already names -- if it does, one of the two is wrong and
    the roster is the better witness. And no two employeenos may claim the
    same name and district, because that is two people wearing one identity.
    """
    f = Path("member_party.json")
    if not f.exists():
        return "skip", "no member_party.json"
    party = json.loads(f.read_text(encoding="utf-8"))
    solved = {k: v for k, v in party.items() if v.get("source") == "solved"}
    if not solved:
        return "ok", "nothing solved"
    try:
        import past_members
        roster = past_members.roster()
    except Exception:
        roster = {}
    clash = [k for k in solved if k in roster]
    assert not clash, (
        f"{len(clash)} solved voter(s) are already named by the General "
        f"Court's own list, which is the better witness: {clash[:4]}")
    seen = {}
    dupe = []
    for mid, rec in solved.items():
        key = (str(rec.get("name", "")).lower(),
               str(rec.get("district", "")).lstrip("0"))
        if key in seen:
            dupe.append(f"{seen[key]} and {mid} both claim {key}")
        seen[key] = mid
    assert not dupe, ("two member numbers claim one person: " + "; ".join(dupe[:3]))
    return "ok", f"{len(solved)} solved voters, each one person and only theirs"


@check("build", "the directory of former members and the site search give a member the years their "
                "page's On Record line does, the 1989-1998 terms included, not only the roll "
                "calls' (Donna Sytek: 1989-2000, not 1999-2000)",
       needs=("build_legislator_pages", "build_indexes"))
def _former_directory_years_are_the_pages(BL, BI):
    """The owner, 14 November 2026: the directory read "Rep. Donna Sytek R, Rock 26, 1999-2000"
    beside a page that says "House, 1989-2000". The directory and the site search took the
    first and last of `served.terms`, which are the roll calls', and the page's line is
    build_legislator_pages.record_spans over the member's own file and `past_terms`. Both now
    ask record_spans, so a member's years are one rule."""
    import tempfile
    sytek = {"id": "365809", "slug": "donna-sytek-rock-26", "name": "Sytek, Donna",
             "chamber": "H", "party": "R", "district_label": "Rock 26",
             "display_plain": "Rep. Donna Sytek",
             "served": {"first": "1/28/1999", "last": "7/12/2000", "terms": ["1999-2000"]},
             "past_terms": {"H": ["1989-1990", "1991-1992", "1993-1994", "1995-1996",
                                  "1997-1998"]}}
    gap = {"id": "1001", "slug": "gap-person-rock-1", "name": "Person, Gap", "chamber": "H",
           "party": "D", "district_label": "Rock 1", "display_plain": "Rep. Gap Person",
           "served": {"first": "1/1/2003", "last": "6/1/2004", "terms": ["2003-2004"]},
           "past_terms": {"H": ["1989-1990"]}}
    both = {"id": "1002", "slug": "both-person-rock-2", "name": "Person, Both", "chamber": "H",
            "party": "R", "district_label": "Rock 2", "display_plain": "Rep. Both Person",
            "served": {"first": "1/1/1999", "last": "6/1/2000", "terms": ["1999-2000"]},
            "past_terms": {"S": ["1995-1996"]}}
    plain = {"id": "1003", "slug": "plain-person-rock-3", "name": "Person, Plain", "chamber": "H",
             "party": "R", "district_label": "Rock 3", "display_plain": "Rep. Plain Person",
             "served": {"terms": ["2011-2012", "2015-2016"], "last": "6/1/2016"}}
    people = [sytek, gap, both, plain]
    root = Path(tempfile.mkdtemp(prefix="gr-fdir-"))
    try:
        site = root / "site"
        (site / "legislator").mkdir(parents=True)
        (site / "legislators").mkdir()
        for m in people:
            (site / "legislator" / f"{m['slug']}.html").write_text("x", encoding="utf-8")
        # Each member's own file, as the page reads it: attendance by term.
        att = {"365809": ["1999-2000"], "1001": ["2003-2004"], "1002": ["1999-2000"],
               "1003": ["2011-2012", "2015-2016"]}
        for m in people:
            (site / "legislators" / f"{m['id']}.json").write_text(json.dumps(
                {**m, "attendance": {t: {} for t in att[m["id"]]}}), encoding="utf-8")
        (site / "former.json").write_text(json.dumps(people), encoding="utf-8")
        BI.former_page(site, "https://x", [])
        page = next(site.rglob("former-legislators.html")).read_text(encoding="utf-8")
        found = {r[3].rsplit("/", 1)[-1].removesuffix(".html"): r[2]
                 for r in BI.find_index(site, [], {}) if r and r[0] == "former"}
    finally:
        shutil.rmtree(root, ignore_errors=True)
    pairs = re.findall(r'<a href="[^"]*">([^<]*)</a> <span class="dirstatus">([^<]*)<', page)
    lines = dict(pairs)
    assert lines.get("Rep. Donna Sytek") == "R, Rock 26, 1989–2000", (
        f"Sytek's directory line is not her page's House, 1989–2000: {lines}")
    assert lines.get("Rep. Gap Person") == "D, Rock 1, 1989–1990, 2003–2004", (
        f"a term the record lacks is bridged, or the 1990s term is lost: {lines}")
    # A term with no roll call after 1999 is a gap too (15 November 2026): 2013-2014 is not his.
    assert lines.get("Rep. Plain Person") == "R, Rock 3, 2011–2012, 2015–2016", (
        f"a member with no 1990s term bridges the term with no roll call: {lines}")
    # A 1990s Senate term and later House service: each chamber its own years, as the page's
    # line has it ("House, 1999–2000 · Senate, 1995–1996"), under each chamber's list.
    assert ("Rep. Both Person", "R, Rock 2 · House 1999–2000 · Senate 1995–1996") in pairs and         ("Sen. Both Person", "Senate 1995–1996 · House 1999–2000") in pairs, (
        f"a member whose 1990s term was in the other chamber: {pairs}")
    assert found.get("donna-sytek-rock-26") == "House · Rock 26 · 1989–2000", found
    assert found.get("gap-person-rock-1") == "House · Rock 1 · 1989–1990, 2003–2004", found
    assert found.get("plain-person-rock-3") == "House · Rock 3 · 2011–2012, 2015–2016", found
    # And the page itself, which is where the years come from.
    assert BL.on_record_text(sytek, {"attendance": {"1999-2000": {}}}) == "House, 1989–2000", (
        BL.on_record_text(sytek, {"attendance": {"1999-2000": {}}}))
    # The directory's own words claim nothing the record does not: not "since 1999".
    src = _source(_paths.locate("build_indexes.py"))
    assert "since 1999" not in src, "the directory still says the record begins in 1999"
    return "ok", ("a former member's directory line and search entry give the page's own years: "
                  "Sytek 1989–2000, a gap kept as a gap, a 1990s Senate term under its chamber, "
                  "and a term with no roll call after 1999 a gap too")


@check("frontend", "the Executive Branch tab says the legislature elects two of its officers "
                   "once, in its note, in English and in Spanish", needs=("officials_tabs",))
def _joint_ballot_once(OT):
    """The audit of 25 October 2026 (S7): the tab's note says the Secretary of
    State and the State Treasurer are elected by joint ballot, and each of
    their cards said it again from corrections/officials.json ("elected by a
    joint session"). The cards leave that sentence out (JOINT_SAID), in the
    translation too, and keep the rest of what the file says of the office;
    the file itself is the person's and is not changed. Fails if a card says
    it again, if the note goes, or if a card loses its other sentences."""
    off = OT.read_officials()
    if not (off.get("secretary_of_state") or {}).get("about"):
        return "skip", "corrections/officials.json has no Secretary of State to read"
    said = {}
    for lang, joint, kept in (("en", r"\bjoint\b", "oversees all state elections"),
                              ("es", r"\bconjunta\b", "supervisa todas las elecciones")):
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", OT.executive(off, lang=lang)))
        n = len(re.findall(joint, text, re.I))
        assert n == 1, f"the Executive Branch tab ({lang}) says how the two are elected {n} times"
        note = re.search(r'<p class="ofwhy">(.*?)</p>', OT.executive(off, lang=lang), re.S)
        assert note and re.search(joint, note.group(1), re.I), (
            f"the tab's note ({lang}) no longer says how the legislature elects them")
        assert kept in text, f"the Secretary of State's card ({lang}) lost what the office does"
        said[lang] = n
    # A card with nothing of the kind keeps every sentence, and a sentence
    # the pattern finds is the only one left out.
    rec = {"about": ["One. The Secretary is elected by a joint session of the House and Senate. Two."]}
    assert OT.abouts("en", rec, OT.JOINT_SAID) == "One. Two.", OT.abouts("en", rec, OT.JOINT_SAID)
    assert OT.abouts("en", rec) == "One. The Secretary is elected by a joint session of the House " \
                                   "and Senate. Two."
    return "ok", "joint ballot said once, in the note, in English and Spanish; the cards keep the rest"


@check("frontend", "the Executive Branch's department heads and the Judicial Branch's justices "
                   "are corrections/officials.json's, each with the page it was read from and "
                   "the day it was read")
def _officials_heads_and_judges():
    """The person's approval of 17 October 2026: the commissioners compactly
    inside Executive Branch, a thin Judicial Branch tab -- the Supreme and
    Superior Courts listed, the Circuit Court by link -- both kept by hand.
    In the hand file (corrections/officials.json, which no builder writes:
    _record_untouched): every named department head and every justice carries
    an https source and the ISO day it was read, a department head its
    department's site, and a record with no name says why it has none; the
    Supreme Court's note about its Chief Justice has its source too, and the
    Circuit Court its own list of judges. On the fixture's built page: every
    named head in the Executive Branch's table with its department linked to
    its site, no row for a nameless one; every Supreme Court justice on the
    neutral chip with their page; every Superior Court justice as a plain
    name; the Circuit Court's line linking to its list; and each tab's count
    the people it names. And a head the record ties to a member's page is
    that member's chip, neutral, where the build has the page, and a plain
    name where it has not."""
    import officials_tabs as OT
    import html as _html
    off = _officials_now()
    dh = (off.get("department_heads") or {}).get("departments") or []
    j = off.get("judicial") or {}
    sup = (j.get("supreme_court") or {}).get("justices") or []
    sop = (j.get("superior_court") or {}).get("justices") or []
    cc = j.get("circuit_court") or {}
    url = re.compile(r"https://\S+")
    day = re.compile(r"\d{4}-\d{2}-\d{2}")
    named = [r for r in dh if (r.get("name") or "").strip()]
    assert len(named) >= 15, f"the hand file names {len(named)} department heads"
    assert len(sup) >= 4 and len(sop) >= 15, (
        f"the hand file names {len(sup)} Supreme Court and {len(sop)} Superior Court justices")
    bad = []
    for where, r in ([("department_heads", r) for r in named]
                     + [("supreme_court", r) for r in sup] + [("superior_court", r) for r in sop]):
        if not url.fullmatch(r.get("source") or ""):
            bad.append(f"{where}: {r.get('name')} has no page it was read from")
        if not day.fullmatch(r.get("read") or ""):
            bad.append(f"{where}: {r.get('name')} has no day it was read")
    for r in dh:
        if not url.fullmatch(r.get("official_url") or ""):
            bad.append(f"department_heads: {r.get('department')} has no site")
        if r not in named and not (r.get("unread") or "").strip():
            bad.append(f"department_heads: {r.get('department')} has no name and no reason why")
    chief = (j.get("supreme_court") or {}).get("chief") or {}
    if chief.get("text") and not (url.fullmatch(chief.get("source") or "")
                                  and day.fullmatch(chief.get("read") or "")):
        bad.append("the Supreme Court's note on its Chief Justice has no source or day")
    if not (url.fullmatch(cc.get("judges_url") or "") and day.fullmatch(cc.get("read") or "")):
        bad.append("the Circuit Court has no list of judges or no day it was read")
    assert not bad, "; ".join(bad)
    shared, _base, _ran, _days = _fixture_site_shared()
    page = (shared / "site" / "officials.html").read_text(encoding="utf-8")

    def pane(pid):
        i = page.index(f'<div class="twnpane" id="{pid}" role="tabpanel"')
        k = page.find('<div class="twnpane"', i + 1)
        return page[i:k if k > 0 else len(page)]
    exe, jud = pane("executive"), pane("judicial")
    table = re.search(r'<table class="ofdepts">.*?</table>', exe, re.S)
    assert table, "the Executive Branch draws no table of department heads"
    rows = re.findall(r"<tr><td>(.*?)</td><td>(.*?)</td></tr>", table.group(0), re.S)
    assert len(rows) == len(named), f"the table has {len(rows)} rows for {len(named)} named heads"
    for (dept, who), r in zip(rows, named):
        assert (f'href="{_html.escape(r["official_url"])}"' in dept
                and _html.escape(r["department"]) in dept), (
            f"{r['department']} is not linked to its site in its row")
        assert _html.escape(r["name"]) in who and _html.escape(r["title"]) in who, (
            f"{r['name']}, {r['title']}, is not in {r['department']}'s row")
    for r in sup:
        assert re.search(r'<span class="mchip p-X" translate="no">' + re.escape(_html.escape(r["name"])) + "</span>",
                         jud) and f'href="{_html.escape(r["official_url"])}"' in jud, (
            f"Justice {r['name']} is not on the neutral chip with their page")
    for r in sop:
        assert f'<span class="ofname">{_html.escape(r["name"])}</span>' in jud, (
            f"Justice {r['name']} of the Superior Court is not on the Judicial Branch tab")
    assert f'href="{_html.escape(cc["judges_url"])}"' in jud, (
        "the Circuit Court's line does not link to the court's own list of judges")
    for pid, name in (("executive", "Executive"), ("judicial", "Judicial")):
        n = OT.count(off, pid)
        assert re.search(rf'id="tab-{pid}"[^>]*>{name} <span class="ofn">\({n:,}\)</span>', page), (
            f"the {name} tab does not count its {n}")
    assert n == len(sup) + len(sop), f"Judicial Branch counts {n} for {len(sup) + len(sop)} justices"
    # A head the site has a page for is that member's chip, neutral; drawn
    # plain where the build has no such page.
    tied = [r for r in named if r.get("member")]
    for r in tied:
        chip = f'<span class="mchip p-X" translate="no"><a href="legislator/{_html.escape(r["member"])}">'
        assert chip in OT.executive(off, lambda s: True), f"{r['name']} is not their member chip"
        assert chip not in OT.executive(off, lambda s: False), (
            f"{r['name']} is linked to a member page the build does not have")
    return "ok", (f"{len(named)} department heads and {len(sup) + len(sop)} justices, each with "
                  f"its page and its day; {len(dh) - len(named)} nameless heads undrawn and "
                  f"said why; the Circuit Court by its own list; {len(tied)} head drawn as "
                  "the member the site has")


@check("frontend", "a member who has left is led up through the list of those who have, and a "
                   "sitting member's towns each link their page where one is written",
       needs=("build_legislator_pages",))
def _member_signposts(BLP):
    """The audit of 25 October 2026, S6: a former member's trail led to
    Officials, which lists only sitting members, and now goes through
    /directory/former-legislators (build_indexes.former_page); and the towns
    under a member's name were words beside a page for each of them.
    towns_linked links a town by its page's slug and leaves a place the
    roster spells otherwise than the district maps -- "Atk. & Gilmanton
    Academy Gt" beside the map's "Atk. & Gil. Academy Grant" -- as words."""
    assert '"/directory/former-legislators.html"' in _source("src/pages/build_indexes.py"), "build_indexes no longer writes /directory/former-legislators"
    site = Path(tempfile.mkdtemp(prefix="gr-towns-"))
    try:
        (site / "districts.json").write_text(json.dumps(
            {"Concord": {"3": {}, "4": {}}, "Berlin": {"0": {}},
             "Atk. & Gil. Academy Grant": {"0": {}}}), encoding="utf-8")
        pages = BLP.town_pages(site)
    finally:
        shutil.rmtree(site, ignore_errors=True)
    towns = ["Berlin", "Concord Ward 3", "Atk. & Gilmanton Academy Gt"]
    places = BLP.towns_linked(towns, pages)
    assert places == {"Berlin": "/town/berlin", "Concord Ward 3": "/town/concord-ward-3"}, places
    sitting = {"id": "9", "chamber": "H", "district": "15", "county": "Merrimack",
               "display_full": "Rep. Ann Doe (D - Merr 15)", "towns": towns}
    rec = BLP.static_record(sitting, {}, "", places)
    assert ('<b>Represents:</b> <a href="/town/berlin">Berlin</a>, <a href="/town/concord-ward-3">'
            'Concord Ward 3</a>, Atk. &amp; Gilmanton Academy Gt</li>') in rec, rec[:400]
    gone = {"id": "1", "former": True, "chamber": "H",
            "display_full": "Rep. Michael Gunski (R - Hills 6)"}
    gone_s = {"id": "2", "former": True, "chamber": "S",
              "display_full": "Sen. Jeb Bradley (R - SD3)"}
    got = _app_js("[(window.GR_TOWNS=" + json.dumps(places) + ", scope.renderMemberHead("
                  + json.dumps(sitting) + ")), scope.renderMemberHead(" + json.dumps(gone) + "), "
                  "(delete window.GR_TOWNS, scope.renderMemberHead(" + json.dumps(sitting) + ")), "
                  "scope.renderMemberHead(" + json.dumps(gone_s) + ")]",
                  names=("renderMemberHead",))
    if got is None:
        return "ok", "the towns are linked in Python; node is not here to draw the head"
    here, left, bare, left_s = got
    trail = lambda h: re.search(r'<nav class="rtrail"[^>]*><ol>(.*?)</ol>', h).group(1)
    # THE LAST STEP IS THE OFFICE ALONE (the owner, 26 October 2026): the
    # step before it says Former Legislators, so "Former Representative"
    # there said "former" twice. The heading keeps "Former Representative".
    for h, office in ((left, "Representative"), (left_s, "Senator")):
        assert trail(h) == ('<li><a href="officials">Officials</a></li><li><a href="directory/'
                            'former-legislators">Former Legislators</a></li><li aria-current="page">'
                            f'{office}</li>'), trail(h)
    assert '<h1 class="rh1">Former Representative Michael Gunski</h1>' in left, (
        "a former member's heading no longer says Former: " + left[:300])
    assert "former-legislators" not in trail(here), trail(here)
    assert ('<a href="/town/berlin">Berlin</a>, <a href="/town/concord-ward-3">Concord Ward 3</a> '
            'and Atk. &amp; Gilmanton Academy Gt</p>') in here, re.sub(r"\s+", " ", here)[:500]
    assert "/town/" not in bare and "Berlin, Concord Ward 3 and Atk." in bare, (
        "with no GR_TOWNS the towns are not left as words")
    return "ok", ("a former member's trail is Officials, Former Legislators, Representative (or "
                  "Senator); a sitting member's towns link /town/berlin and /town/concord-ward-3, and a "
                  "place spelled otherwise stays words")


@check("session", "a name the record misspells links where a person's spelling says whom it means",
       needs=("spellings", "build_session_pages", "build_site_v2"))
def _record_misspelling(SP, BSP, V2):
    """The person, 10 October 2026: "Rep. Poloszaj" on HB 1689 is
    Representative Tom Ploszaj, misspelled in the official record. No
    matcher guesses at a near name; member_corrections.json's "spellings"
    says it, and both matchers -- the session day's (Members.slug) and the
    bill story's (mover_member) -- look the name up as the roster spells it,
    under every rule an ordinary name meets. Without the entry it stays
    words. A key for the other chamber does not apply."""
    root = Path(tempfile.mkdtemp(prefix="gr-spell-"))
    try:
        cf = root / "member_corrections.json"
        cf.write_text(json.dumps({"members": {}, "spellings": {
            "_what": "ignored", "H|Poloszaj": {"means": "Ploszaj", "why": "the record's typo"}}}),
            encoding="utf-8")
        table = SP.load(cf)
        assert table == {("H", "poloszaj"): "Ploszaj"}, table
        assert SP.respell("H", "Tom Poloszaj", table) == "Tom Ploszaj"
        assert SP.respell("S", "Poloszaj", table) == "Poloszaj", "a House spelling read in the Senate"
        assert SP.load(root / "missing.json") == {}
        (root / "legislators.json").write_text(json.dumps([
            {"id": 7, "slug": "tom-ploszaj-belk-1", "name": "Ploszaj, Tom", "chamber": "H",
             "label": "Rep. Tom Ploszaj (R - Belk 1)"}]), encoding="utf-8")
        m = BSP.Members(root)
        m.spellings = {}
        assert m.slug("H", "Poloszaj") is None, "linked with no spelling on file"
        m.spellings = table
        assert m.slug("H", "Poloszaj") == "tom-ploszaj-belk-1"
        assert m.respelled[("H", "Poloszaj", "Ploszaj")] == 1, m.respelled
        legs = {"7": {"chamber": "H", "name": "Ploszaj, Tom", "slug": "tom-ploszaj-belk-1",
                      "party_code": "R", "district": "1", "county": "Belknap"}}
        keep = list(V2._SPELLINGS)
        try:
            V2._SPELLINGS[:] = [{}]
            assert V2.mover_member("Rep. Poloszaj", "H", legs) is None
            V2._SPELLINGS[:] = [table]
            got = V2.mover_member("Rep. Poloszaj", "H", legs)
        finally:
            V2._SPELLINGS[:] = keep
        assert got and got["slug"] == "tom-ploszaj-belk-1", got
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", "Poloszaj links to Ploszaj on a session day and in a bill's story only with the spelling on file"


@check("build", "the sponsor fetch files an answer under the member it asked for",
       needs=("fetch_sponsors_by_member",))
def _sponsor_fetch(S):
    """A postback is a conversation, and this one can answer about somebody else.

    fetch_legislation had to be taught that a page can be the wrong bill. The
    same mistake here is worse: byAnyMember.aspx is one address answering
    about whichever member the session last selected, so an answer arriving
    for the previous member would file one legislator's whole career under
    another's name -- and --parse would then report it as fact, with no
    symptom anywhere. There is no bill number in the answer to check against,
    only the page's own selected <option> and checked radio, so those are
    what every answer is checked against before it is written.

    "unverified" is the case that matters most and is the easiest to get
    wrong: markup that states neither must not be read as agreement. It is
    saved -- a page that cost a request is never thrown away -- but it is
    counted apart, and it is the condition a sweep refuses to start on.

    No request leaves here; a fake server stands in, because this address has
    blocked us twice and the guard cannot be tested against it without being
    the problem it guards against.
    """
    import http.client
    import urllib.error
    import refusal
    # THE JOIN THE SCORE IS BUILT ON. --probe is only worth its twelve
    # requests because it compares the answers against data/sponsors.json,
    # which came from the General Court's database; that comparison is made on
    # a surname, and the two sides write a member differently -- byAnyMember
    # gives "Rep. Vartanian, Elsie(Rock. 20)" and the database gives
    # "Vartanian, Elsie". The first draft returned "repvartanian" against
    # "vartanian", which would have scored zero on every member and pointed at
    # the row parser instead. Found before a single page was fetched, and kept
    # here because a silent zero is the worst possible outcome for a check
    # whose whole job is to tell you whether the parser works.
    for a, b in [("Rep. Vartanian, Elsie(Rock. 20)", "Vartanian, Elsie"),
                 ("Sen. Barnes, Jr., John(Dist. 17)", "Barnes, John"),
                 ("Rep. McGough, Tim(Hills. 12)", "Tim McGough")]:
        assert S.surname(a) == S.surname(b) != "", (a, S.surname(a), b, S.surname(b))
    assert S.term_of("1989") == "1989-1990" and S.term_of("2026") == "2025-2026"
    root = Path(tempfile.mkdtemp())
    saved = (os.getcwd(), S.get, S.time.sleep)
    asked = []
    try:
        os.chdir(root)
        S.time.sleep = lambda s: None

        def answer(mid="100", mode_value="0", *, select=True, radio=True):
            """One postback's markup: the tokens, the list, the radio pair."""
            opt = (f'<option value="{mid}" selected="selected">Vartanian, '
                   'Elsie</option>' if select else
                   f'<option value="{mid}">Vartanian, Elsie</option>')
            return (
                '<input type="hidden" name="__VIEWSTATE" value="fresh" />'
                '<input type="hidden" name="__EVENTVALIDATION" value="ev" />'
                '<select name="ctl00$pageBody$lstMembers">' + opt +
                '<option value="200">Other, Someone</option></select>'
                '<input type="radio" name="ctl00$pageBody$rdoPrime" '
                f'value="{mode_value}"' + (' checked="checked"' if radio else '')
                + ' /><table><tr><td><div class="container"><div class="row">'
                '<div class="col-sm-2">1989</div>'
                '<div class="col-sm-2"><a href="billinfo.aspx?sy=1989&amp;'
                'Pastid=11711989">HB750</a></div>'
                '<div class="col-sm-2">SIGNED BY GOVERNOR</div>'
                '<div class="col-sm"><b>title:</b> relative to things.</div>'
                '</div></div></td></tr></table>')

        def server(answers):
            def op(url, data=None, timeout=90):
                asked.append(url)
                a = answers.pop(0)
                if isinstance(a, Exception):
                    raise a
                return a
            return op

        # The form's own markup gives up the list and the hidden fields.
        form_page = answer()
        assert ("100", "Vartanian, Elsie") in S.members(form_page)
        assert S.tokens(form_page)["__VIEWSTATE"] == "fresh"
        assert S.selected_member(form_page) == "100"
        assert S.checked_mode(form_page) == "0"

        form = {"__VIEWSTATE": "old", "__EVENTVALIDATION": "old"}
        # The member asked for: saved, and the answer's fresh tokens kept.
        S.get = server([answer("100", "0")])
        what, form, _why = S.fetch_member("100", "prime", form, 0)
        assert what == "saved", what
        assert S.page_path("100", "prime").exists()
        assert form["__VIEWSTATE"] == "fresh", "the fresh tokens were dropped"
        assert S.parse_rows(S.load("100", "prime"))[0]["lsr"] == "1171"
        # And never asked for twice.
        n = len(asked)
        assert S.fetch_member("100", "prime", form, 0)[0] == "cached"
        assert len(asked) == n, "a cached answer was asked for again"

        # ANOTHER MEMBER'S LIST: not written, under either name.
        S.get = server([answer("200", "0")])
        assert S.fetch_member("101", "prime", form, 0)[0] == "wrong member"
        assert not S.page_path("101", "prime").exists()
        assert not S.page_path("200", "prime").exists()
        # The other radio: the co-sponsored list is not the prime one.
        S.get = server([answer("102", "1")])
        assert S.fetch_member("102", "prime", form, 0)[0] == "wrong mode"
        assert not S.page_path("102", "prime").exists()
        S.get = server([answer("102", "1")])
        assert S.fetch_member("102", "co", form, 0)[0] == "saved"

        # SAYS NEITHER: saved, counted apart, and the condition a sweep
        # refuses to start on -- not silently treated as the right member.
        S.get = server([answer("103", "0", select=False, radio=False)])
        what, form, why = S.fetch_member("103", "prime", form, 0)
        assert what == "unverified", what
        assert S.page_path("103", "prime").exists(), "a paid-for answer was lost"
        assert "selected member" in why and "checked mode" in why, why
        assert S.selected_member(S.load("103", "prime")) is None, (
            "the sweep guard reads this page as checkable when it is not")

        # The refusals, read the one way every fetcher reads them.
        for a, want in [
                ("<h1>Web Page Blocked</h1> Attack ID: 1234", "refused"),
                (urllib.error.HTTPError("u", 403, "no", {}, None), "refused"),
                (urllib.error.HTTPError("u", 429, "slow", {}, None), "refused"),
                (urllib.error.HTTPError("u", 503, "busy", {}, None), "refused"),
                (http.client.RemoteDisconnected("closed"), "dropped"),
                (urllib.error.URLError(ConnectionResetError(10054, "reset")),
                 "dropped"),
                (TimeoutError("read timed out"), "dropped"),
                (urllib.error.HTTPError("u", 500, "err", {}, None), "stale"),
                (urllib.error.HTTPError("u", 404, "nf", {}, None), "missing"),
                ("is neither a DataColumn nor a DataRelation", "error page")]:
            S.get = server([a])
            mid = f"9{len(asked)}"
            got = S.fetch_member(mid, "prime", form, 0)[0]
            assert got == want, f"{a!r} read as {got}, not {want}"
            assert not S.page_path(mid, "prime").exists(), (
                f"a {want} answer was saved as a member's list")

        # A refusal on file stops it before the request, and is left as it is
        # rather than overwritten with this run's name.
        refusal.note("somebody else", "a refusal from another run")
        before, n = refusal.MARK.read_text(encoding="utf-8"), len(asked)
        assert S.fetch_member("300", "prime", form, 0)[0] == "halted"
        assert len(asked) == n, "a request went out with a refusal on file"
        assert refusal.MARK.read_text(encoding="utf-8") == before
        refusal.MARK.unlink()

        # The lane that holds archive/.lock gone: nothing asked.
        class Gone:
            def still(self):
                return False
        S.HOLD, n = Gone(), len(asked)
        assert S.fetch_member("301", "prime", form, 0)[0] == "halted"
        assert len(asked) == n
        S.HOLD = None
        return "ok", ("right member saved once, another member's list and the "
                      "wrong radio refused, unverified kept apart, block page/"
                      "403/429/503/reset/timeout stop it")
    finally:
        os.chdir(saved[0])
        S.get, S.time.sleep = saved[1], saved[2]
        S.HOLD = None
        shutil.rmtree(root, ignore_errors=True)


@check("naming", "a member who changed chamber keeps both chambers' votes, and two people who share a name stay two",
       needs=("member_links", "build_site_v2"))
def _member_links(member_links, build_site_v2):
    """member_links.links on the shapes the real files have, then build_legislators on its answer.

    A member who moves between the House and the Senate is given a new number,
    and until 13 September a page showed one chamber's votes: Sen. Cindy
    Rosenwald's carried 1,399 of her 4,218. careers.json had already shown what
    joining on the name does -- it merged two different Rep. Patrick Longs and
    missed Sen. Pat Long -- so the join asks for the name, the party, the ground
    and the time, and a case short of any of them stays apart. The members here
    are the real cases, their rows cut down to what the rule reads, beside three
    made-up ones that must not join: a party change, a seat in another county,
    and two earlier numbers that both fit.
    """
    ML, B = member_links, build_site_v2

    def row(mid, name, label, party, body, day, n=1):
        return {"member_id": mid, "name": name, "label": label, "party": party, "body": body,
                "year": day.split("/")[2], "vote_number": str(n), "bill": "HB1",
                "question": "Ought to Pass", "date": day, "vote": "Yea"}

    def seat(town, ward, senate, county, district):
        return {town: {ward or "0": {"senate": senate,
                                     "house": [{"county": county, "district": district}]}}}

    districts = {}
    for d in (seat("Nashua", "3", 13, "Hillsborough", 6), seat("Milford", "", 11, "Hillsborough", 43),
              seat("Bedford", "", 9, "Hillsborough", 7), seat("Stratham", "", 24, "Rockingham", 19)):
        districts.update(d)
    districts["Manchester"] = {
        "3": {"senate": 20, "house": [{"county": "Hillsborough", "district": 23}]},
        "7": {"senate": 18, "house": [{"county": "Hillsborough", "district": 26}]}}

    def member(mid, last, first, chamber, party, town, ward=""):
        return {"id": mid, "last": last, "first": first, "name": f"{last}, {first}",
                "chamber": chamber, "party_code": party, "party": party, "district": "1",
                "county": "Hillsborough", "town_seats": [{"town": town, "ward": ward}]}

    roster = [member("9406", "Rosenwald", "Cindy", "S", "D", "Nashua", "3"),
              member("11463", "Long", "Pat", "S", "D", "Manchester", "3"),
              member("11177", "Long", "Patrick", "H", "D", "Manchester", "7"),
              member("423", "Daniels", "Gary", "H", "R", "Milford"),
              member("10698", "Murphy", "Keith", "S", "R", "Bedford"),
              member("5001", "Example", "Ann", "S", "R", "Stratham"),
              member("6001", "Sample", "Sam", "S", "D", "Stratham"),
              member("7001", "Twin", "Tom", "S", "R", "Stratham")]
    rows = [
        row("9406", "Rosenwald, Cindy", "Sen. Cindy Rosenwald (D - SD13)", "D", "S", "3/7/2019"),
        row("9406", "Rosenwald, Cindy", "Sen. Cindy Rosenwald (D - SD13)", "D", "S", "2/5/2020", 2),
        row("515", "Rosenwald, Cindy", "Rosenwald, Cindy(D) Hillsborough 30", "D", "H", "1/12/2017"),
        row("515", "Rosenwald, Cindy", "Rosenwald, Cindy(D) Hillsborough 30", "D", "H", "5/3/2018", 2),
        # Sen. Pat Long, the Hillsborough 23 number he held until 2024, and the
        # other Rep. Patrick Long, who sits for Hillsborough 26 while he sits
        # in the Senate and so voted on a day he did.
        row("11463", "Long, Pat", "Sen. Pat Long (D - SD20)", "D", "S", "2/13/2025"),
        row("540", "Long, Patrick", "Long, Patrick(D) Hillsborough 23", "D", "H", "5/23/2024"),
        row("11177", "Long, Patrick", "Rep. Patrick Long (D - Hills 26)", "D", "H", "2/13/2025"),
        # House, the Senate, and the House again under the first number.
        row("423", "Daniels, Gary", "Rep. Gary Daniels (R - Hills 43)", "R", "H", "3/4/2013"),
        row("423", "Daniels, Gary", "Rep. Gary Daniels (R - Hills 43)", "R", "H", "5/1/2014", 2),
        row("423", "Daniels, Gary", "Rep. Gary Daniels (R - Hills 43)", "R", "H", "2/12/2025", 3),
        row("923", "Daniels, Gary", "Daniels, Gary(R)  11", "R", "S", "1/8/2015"),
        row("923", "Daniels, Gary", "Daniels, Gary(R)  11", "R", "S", "6/2/2016", 2),
        # Keith Murphy's House seat was also held by Kelleigh Murphy: same
        # surname, party and seat, a different first name.
        row("10698", "Murphy, Keith", "Sen. Keith Murphy (R - SD16)", "R", "S", "1/5/2023"),
        row("638", "Murphy, Keith", "Murphy, Keith(R) Hillsborough 07", "R", "H", "5/1/2018"),
        row("377152", "Murphy, Kelleigh", "Murphy, Kelleigh(R) Hills 07", "R", "H", "1/10/2013"),
        row("5001", "Example, Ann", "Sen. Ann Example (R - SD24)", "R", "S", "3/1/2023"),
        row("5002", "Example, Ann", "Example, Ann(D) Rockingham 19", "D", "H", "3/1/2019"),
        row("6001", "Sample, Sam", "Sen. Sam Sample (D - SD24)", "D", "S", "3/1/2023"),
        row("6002", "Sample, Sam", "Sample, Sam(D) Coos 04", "D", "H", "3/1/2019"),
        row("7001", "Twin, Tom", "Sen. Tom Twin (R - SD24)", "R", "S", "3/1/2023"),
        row("7002", "Twin, Tom", "Twin, Tom(R) Rockingham 19", "R", "H", "3/1/2015"),
        row("7003", "Twin, Thomas", "Twin, Thomas(R) Rock 19", "R", "H", "3/1/2019")]
    by = {}
    for r in rows:
        by.setdefault(r["member_id"], []).append(r)

    linked, missed = ML.links(roster, by, districts)
    assert linked == {"9406": ["515"], "11463": ["540"], "423": ["923"], "10698": ["638"]}, (
        f"joined {linked}; wanted Rosenwald, Pat Long, Daniels and Keith Murphy each to "
        "their one earlier number, and nobody else")
    why = {}
    for r in missed:
        why.setdefault(r["member"], []).extend(r["why"])
    assert set(why) == {"5001", "6001", "7001"}, f"left apart with a reason: {sorted(why)}"
    assert why["5001"][0].startswith("party") and why["6001"][0].startswith("ground"), why
    assert all(w.startswith("more than one") for w in why["7001"]) and len(why["7001"]) == 2, why

    # A SITTING MEMBER WITH NO VOTE YET (25 November 2026): the roster that turns on
    # Organization Day seats a representative elected to the Senate under a new number weeks
    # before its first roll call. Laura Telerski's House number voted in the newest term and
    # joins her Senate number; a namesake whose number last voted in 2017-2018 waits for the
    # member's own first vote; one of another party stays apart with the reason; and the
    # members above join as they did.
    fresh = [member("990201", "Telerski", "Laura", "S", "D", "Nashua", "3"),
             member("990202", "Olden", "Ann", "S", "D", "Nashua", "3"),
             member("990203", "Other", "Ed", "S", "D", "Nashua", "3")]
    more = {**by, "9117": [row("9117", "Telerski, Laura", "Rep. Laura Telerski (D - Hills 11)", "D",
                               "H", "3/5/2026")],
            "8800": [row("8800", "Olden, Ann", "Olden, Ann(D) Hillsborough 06", "D", "H", "5/3/2018")],
            "8801": [row("8801", "Other, Ed", "Rep. Ed Other (R - Hills 6)", "R", "H", "3/5/2026")]}
    joined, apart = ML.links(roster + fresh, more, districts)
    assert joined == {**linked, "990201": ["9117"]}, (
        f"with three members who have not voted yet, joined {joined}: wanted the four above and "
        "Telerski's Senate number to her House one, and nobody else")
    said = {r["member"]: r["why"] for r in apart if r["member"].startswith("9902")}
    assert set(said) == {"990203"} and said["990203"][0].startswith("party"), (
        f"members with no vote yet left apart: {said}; wanted Ed Other alone, for his party")

    root = Path(tempfile.mkdtemp(prefix="gr-links-"))
    try:
        (root / "legislators").mkdir()
        legs = {m["id"]: m for m in roster}
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            B.build_legislators(root, legs, by, {}, set(), {}, {}, linked)
        read = lambda mid: json.loads((root / "legislators" / f"{mid}.json").read_text(encoding="utf-8"))
        r = read("9406")
        assert [v["k"] for v in r["votes"]] == ["2020-S-2", "2019-S-1", "2018-H-2", "2017-H-1"], (
            "Rosenwald's page does not carry both chambers' votes, newest first: "
            + str([v["k"] for v in r["votes"]]))
        assert r["member_ids"] == ["9406", "515"] and sum(r["counts"].values()) == 4, r.get("member_ids")
        assert r["service"] == [{"chamber": "H", "spans": [[2017, 2018]]},
                                {"chamber": "S", "spans": [[2019, 2020]]}], r["service"]
        assert read("423")["service"] == [{"chamber": "H", "spans": [[2013, 2014], [2025, 2025]]},
                                          {"chamber": "S", "spans": [[2015, 2016]]}], read("423")["service"]
        other = read("11177")
        assert [v["k"] for v in other["votes"]] == ["2025-H-1"] and "member_ids" not in other \
            and "service" not in other, "Rep. Patrick Long (Hills 26) was given somebody else's votes"
        index = {m["id"]: m for m in json.loads((root / "legislators.json").read_text(encoding="utf-8"))}
        assert index["9406"]["n_votes"] == 4 and index["11177"]["n_votes"] == 1, (
            "the index counts one number's votes")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("4 real chamber changers joined, Rep. Patrick Long and Kelleigh Murphy kept apart, and a "
                  "party change, another county and two fitting numbers left for a person; a senator "
                  "with no vote yet joined to the House number that voted in the newest term, a namesake "
                  "of 2017-2018 left to wait for a vote, another party apart; the member "
                  "files carry both chambers newest first")


def _turned_roster_fixture(root):
    """The fixture project, its builders still to run, with the roster turned as Organization
    Day turns it, the way tests/rehearse_turn.py fakes one: the members 2025-2026 sat with are
    data/frozen/2025-2026/legislators.json, as build_data writes it once the roster installed is
    another House (freeze_term.own_roster_terms, which reads the day files written here), and
    data/legislators.json is the next House. Returns (base, the builders, their four rows)."""
    here = Path(".").resolve()
    base, steps = _built_site_prepare(here, root)

    def leg(mid, last, first, ch, district, party="R", towns=(), committees=(), seat=""):
        tag = f"SD{district}" if ch == "S" else f"Rock {district}"
        return {"id": mid, "last": last, "first": first, "name": f"{last}, {first}", "chamber": ch,
                "party": {"R": "Republican", "D": "Democrat"}[party], "party_code": party,
                "county": "Rockingham", "county_abbr": "Rock", "district": district,
                "label": f"{'Sen.' if ch == 'S' else 'Rep.'} {first} {last} ({party} - {tag})",
                "email": f"{first.lower()}.{last.lower()}@gc.nh.gov", "url": "",
                "towns": list(towns), "committees": list(committees), "title": "", "seat": seat,
                "phone": ""}
    d = root / "data"
    nelson, altschiller = json.loads((d / "legislators.json").read_text(encoding="utf-8"))
    vose_h = leg("377300", "Vose", "Michael", "H", "5", towns=["Brentwood"])
    example_was = leg("377301", "Example", "Pat", "H", "6", party="D", towns=["Brentwood"],
                      committees=["Commerce"])
    vose_s = leg("990103", "Vose", "Michael", "S", "23", towns=["Brentwood", "Fremont", "Danville"])
    example = leg("377301", "Example", "Pat", "H", "7", party="D", towns=["Fremont"],
                  committees=["Commerce"])
    newell = leg("990104", "Newell", "Pat", "H", "32", towns=["Danville"], committees=["Commerce"],
                 seat="1005")
    then = [nelson, altschiller, vose_h, example_was]
    now = [altschiller, vose_s, example, newell]
    (d / "frozen" / "2025-2026").mkdir(parents=True)
    (d / "frozen" / "2025-2026" / "legislators.json").write_text(json.dumps(then), encoding="utf-8")
    (d / "legislators.json").write_text(json.dumps(now), encoding="utf-8")
    votes = json.loads((d / "member_votes.json").read_text(encoding="utf-8"))
    for m in (vose_h, example_was):
        votes.append({"member_id": m["id"], "name": m["name"], "party": m["party_code"],
                      "label": f"{m['name']}({m['party_code']}) Rock {m['district']}",
                      "year": "2026", "body": "H", "vote_number": "310", "bill": "HB1442",
                      "question": "Ought to Pass", "date": "2026-03-06", "vote": "Yea"})
    (d / "member_votes.json").write_text(json.dumps(votes), encoding="utf-8")
    # The seat table as the Sunday fetch left it before the turn, and the committee's listing.
    (d / "committee_members.json").write_text(json.dumps({"H43": [
        {"id": m["id"], "name": m["name"], "party": m["party"], "party_code": m["party_code"],
         "district": m["district"], "county_code": "08", "chamber": "H", "sequence": i,
         "sitting": True, "seat_active": True} for i, m in enumerate((nelson, example_was))]}),
        encoding="utf-8")
    (root / "committees.json").write_text(json.dumps({"House": [
        {"name": "Commerce", "chair": "Pat Example", "vice_chair": "", "clerk": ""}]}),
        encoding="utf-8")
    # The day files freeze_term.own_roster_terms reads: the session's docket (2026), the
    # term's freeze with its roster, and the roster installed since, which is another House.
    (root / "Docket.txt").write_text("2026|0503|3/6/2026 11:12:00 AM|HB1442|H|Ought to Pass|x\n",
                                     encoding="utf-8")
    fz = root / "frozen" / "2025-2026"
    (fz / "day").mkdir(parents=True)
    (fz / "manifest.json").write_text("{}", encoding="utf-8")

    def txt(rows):
        return "".join(f"{m['id']}|{m['name'].split(', ')[0]}|{m['name'].split(', ')[-1]}||"
                       f"{m['chamber']}|||{m['district']}|{m['party_code']}||||||\n" for m in rows)
    (fz / "day" / "legislators.txt").write_text(txt(then), encoding="utf-8")
    (root / "legislators.txt").write_text(txt(now), encoding="utf-8")
    return base, steps, {"nelson": nelson, "vose": vose_s, "example": example, "newell": newell}


@check("build", "the night the roster turns, built on the fixture: a member not returning is Former Rep. "
                "on their own page and in the search, and named as they sat on their bills and votes; "
                "one re-elected to another seat keeps their record, the old address answering; one "
                "elected to the Senate under a new number has one page with both chambers, the House "
                "page's address answering; a new member is on the committee the roster names",
       needs=("build_site_v2", "build_pages", "freeze_term"))
def _turned_roster_built(B, BP, FT):
    """The owner, 25 November 2026: "making sure to transition currently serving members that
    are not returning as Former Rep. on their pages". On Organization Day the General Court's
    roster seats the next House; the fixture is built here the night it does
    (_turned_roster_fixture): of the four members of 2025-2026, Rep. Jodi Nelson did not
    return, Sen. Debra Altschiller was re-elected to her seat, Rep. Pat Example to another
    district (Rockingham 6 to 7), and Rep. Michael Vose to the Senate under a new number, with
    no vote under it yet; Rep. Pat Newell is new. Every builder is run, as build_all runs them,
    and the pages are read:

      Nelson    "Former Rep. Jodi Nelson (R - Rock 13)" on her own page, "Former
                Representative ..." heading it, and "Former Rep." in the search, as the owner
                settled (treat-former-members-the-same); on her bill and its roll call she is
                "Rep. Jodi Nelson" as she sat, linked to her page, and nowhere marked; in the
                Former members list, and not among the Legislators or on her committee;
      Example   one page, at the new seat's address, with his vote of 2026; the old address a
                301 to it (members.turned_addresses);
      Vose      one page, the Senate number's, carrying the House number's vote
                (member_links, A SITTING MEMBER WITH NO VOTE YET), no "Former Rep." page beside
                it, and the House page's address a 301 to it; his vote of 2026 still "Rep.";
      Newell    a page, his work email, floor seat and committee as the roster gives them, and a
                place on Commerce, which the roster names for him and the seat table, the
                Sunday fetch's, does not yet (build_committees, A MEMBER THE SEAT TABLE HAS NO
                ROW FOR YET); Altschiller's page where it was, no 301 from it."""
    import re as _re
    here = Path(".").resolve()
    missing = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if missing or not (here / "src/pages/bills.html").exists():
        return "skip", f"not here: {', '.join(missing) or 'src/pages/bills.html'}"
    root = Path(tempfile.mkdtemp(prefix="gr-turnedroster-"))
    try:
        base, steps, who = _turned_roster_fixture(root)
        assert FT.own_roster_terms(root) == ["2025-2026"], (
            f"the fixture's roster has not turned for freeze_term: {FT.own_roster_terms(root)}")
        _built_site_run(root, steps)
        site = root / "site"
        read = lambda p: (site / p).read_text(encoding="utf-8")
        load = lambda p: json.loads(read(p))
        former = {m["id"]: m for m in load("former.json")}
        legs = {m["id"]: m for m in load("legislators.json")}
        assert sorted(former) == ["377204"] and former["377204"].get("slug") == "jodi-nelson-rock-13", (
            f"the former members are {sorted(former)}: wanted Nelson alone, at her address")
        assert sorted(legs) == ["377207", "377301", "990103", "990104"], sorted(legs)
        page = read("legislator/jodi-nelson-rock-13.html")
        title = _re.search(r"<title>(.*?)</title>", page).group(1)
        heads = _re.findall(r"<h1[^>]*>(.*?)</h1>", page, _re.S)
        assert title == "Former Rep. Jodi Nelson (R - Rock 13) | Granite Record" and \
            heads == ["Former Representative Jodi Nelson (R - Rock 13)"] and "GR_FORMER=true" in page, (
            title, heads)
        find = load("find.json")
        rows = {(r[0], r[3]) : r[1] for r in find if r and r[0] in ("legislator", "former", "elect")}
        assert rows == {("former", "legislator/jodi-nelson-rock-13"): "Former Rep. Jodi Nelson",
                        ("legislator", "legislator/debra-altschiller-sd-24"):
                            "Sen. Debra Altschiller (D - SD24)",
                        ("legislator", "legislator/michael-vose-sd-23"): "Sen. Michael Vose (R - SD23)",
                        ("legislator", "legislator/pat-example-rock-7"): "Rep. Pat Example (D - Rock 7)",
                        ("legislator", "legislator/pat-newell-rock-32"):
                            "Rep. Pat Newell (R - Rock 32)"}, f"the search's members are {rows}"
        idx = {r["id"]: r for r in load("idx/2025-2026.json")}
        assert (idx["HB1442"].get("sponsor_label"), idx["HB1442"].get("sponsor_slug")) == (
            "Rep. Jodi Nelson (R - Rock 13)", "jodi-nelson-rock-13"), (
            "HB 1442's sponsor is not named as she sat, at her page", idx["HB1442"])
        bill = read("bill/2026/hb1442.html")
        ballots = set(_re.findall(r'"n": "((?:Former )?(?:Rep|Sen)\. [^"]+)"', bill))
        assert {"Rep. Jodi Nelson (R)", "Rep. Michael Vose (R)", "Rep. Pat Example (D)"} <= ballots and \
            not any(b.startswith("Former") or b.startswith("Sen. Michael") for b in ballots), (
            f"HB 1442's roll call names its members {sorted(ballots)}: wanted each as they sat")
        assert "legislator/jodi-nelson-rock-13" in read("directory/former-legislators.html"), (
            "Nelson is not in the Former members list")
        officials = read("officials.html")
        assert "jodi-nelson-rock-13" not in officials and all(
            f"legislator/{m['slug']}" in officials for m in legs.values()), (
            "the Legislators tab does not list the four sitting members alone")
        vose, example = legs["990103"], legs["377301"]
        assert vose.get("member_ids") == ["990103", "377300"] and \
            vose.get("moved_from") == ["/legislator/michael-vose-rock-5"] and \
            [v["k"] for v in load("legislators/990103.json")["votes"]] == ["2026-H-310"], (
            "Vose's Senate page does not carry his House number's record", vose)
        assert not (site / "legislator" / "michael-vose-rock-5.html").exists(), (
            "Vose's House number has a page of its own beside his Senate one")
        assert example.get("slug") == "pat-example-rock-7" and \
            example.get("moved_from") == ["/legislator/pat-example-rock-6"] and \
            [v["k"] for v in load("legislators/377301.json")["votes"]] == ["2026-H-310"], example
        assert "moved_from" not in legs["377207"] and "moved_from" not in former["377204"], (
            "an address that did not move answers with a 301")
        redirects = set(read("_redirects").splitlines())
        for old, new in (("michael-vose-rock-5", "michael-vose-sd-23"),
                         ("pat-example-rock-6", "pat-example-rock-7")):
            want = {f"/legislator/{old} /legislator/{new} 301",
                    f"/legislator/{old}/votes /legislator/{new}/votes 301"}
            assert want <= redirects, f"_redirects does not move /legislator/{old}: {want - redirects}"
        assert not any(r.startswith(("/legislator/debra-altschiller", "/legislator/jodi-nelson"))
                       for r in redirects), "a page that stayed is moved"
        cmte = load("committee/H43.json")
        names = sorted(m.get("label") for m in cmte.get("members") or [])
        assert names == ["Rep. Pat Example (D - Rock 7)", "Rep. Pat Newell (R - Rock 32)"], (
            f"Commerce lists {names}: wanted the two the roster seats on it, Newell with no row yet")
        # What the General Court publishes of a new member after Organization Day -- the work
        # email, the floor seat, the committees -- reaches their row and their own file.
        new = legs["990104"]
        assert (new.get("email"), new.get("seat"), new.get("committees")) == (
            "pat.newell@gc.nh.gov", "1005", ["Commerce"]) and \
            load("legislators/990104.json").get("email") == "pat.newell@gc.nh.gov" and \
            (site / "legislator" / "pat-newell-rock-32.html").exists(), (
            f"the new member's row and page: {new}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("the fixture built with the roster turned: Nelson Former Rep. on her page and in the "
                  "search, named as she sat on HB 1442 and its roll call, in Former members, off the "
                  "Legislators tab and her committee; Example at Rock 7 with his record, Rock 6 a 301; "
                  "Vose one Senate page with his House vote, Rock 5 a 301, no Former page; Newell's "
                  "page, email, seat and committee, and on Commerce with no seat row; Altschiller "
                  "where she was")


# THE ELECTION OF THE SWITCH'S FIXTURE (25 November 2026), made up over the fixture's own districts
# (pf_fixture._built_site_prepare): Rockingham 13, two seats over Raymond and Stratham; Rockingham 6,
# 7 and 8, one town each, under the floterial Rockingham 32; Senate districts 24 and 23. Of the
# roster of 2025-2026 (_switch_fixture): Jodi Nelson loses Rockingham 13; Debra Altschiller is
# re-elected to SD24; Pat Example, of Rockingham 6, wins Rockingham 7; Michael Vose, a
# Representative for Rockingham 5, wins SD23. New: Ann Other and Hal Burns (Rockingham 13), Ruth
# Gale (Rockingham 6) and Pat Newell (Rockingham 32), each with a provisional page; Dana Ricard
# (Rockingham 8), whose race the hand file holds not final, with none. And a former member elected
# again: Sam Holt, Representative for Rockingham 11 in 2023-2024, wins Rockingham 9 (Kingston, of
# SD23, which _switch_fixture adds to the district table) as the ballot prints him, "Sam J. Holt".
def _sw_race(towns, seats, *cands, floterial=False):
    return {"seats": seats, "floterial": floterial, "towns": list(towns), "scatter": 0,
            "candidates": [{"name": n, "party": p, "votes": v, "write_in": False, "elected": won}
                           for n, p, v, won in cands]}


_SW_RESULTS = {
    "_source": [{"url": "https://www.sos.nh.gov/elections/election-results", "saved": "2026-11-05"}],
    "election": "2026-11-03", "term": "2027-2028", "races": {
        "S|24": _sw_race(["Raymond", "Stratham"], 1, ("Debra Altschiller", "d", 900, True),
                         ("Tom Brandt", "r", 800, False)),
        "S|23": _sw_race(["Brentwood", "Danville", "Fremont", "Kingston"], 1,
                         ("Michael Vose", "r", 700, True), ("Lee Rourke", "d", 600, False)),
        "H|Rockingham|9": _sw_race(["Kingston"], 1, ("Sam J. Holt", "r", 340, True),
                                   ("Ida Lane", "d", 300, False)),
        "H|Rockingham|13": _sw_race(["Raymond", "Stratham"], 2, ("Ann Other", "d", 500, True),
                                    ("Hal Burns", "r", 480, True), ("Jodi Nelson", "r", 470, False)),
        "H|Rockingham|6": _sw_race(["Brentwood"], 1, ("Ruth Gale", "d", 300, True)),
        "H|Rockingham|7": _sw_race(["Fremont"], 1, ("Pat Example", "d", 310, True)),
        "H|Rockingham|8": _sw_race(["Danville"], 1, ("Dana Ricard", "d", 320, True)),
        "H|Rockingham|32": _sw_race(["Brentwood", "Danville", "Fremont"], 1,
                                    ("Pat Newell", "r", 330, True), floterial=True)}}
_SW_HAND = {"2026-11-03": {"recount_deadline": "2026-11-13",
                           "matches": {"H|Rockingham|32": {"Pat Newell": None}},
                           "not_final": {"H|Rockingham|8": {"recount": True}}}}
# Their requests for 2027, one each, as the General Court's list names them.
_SW_LSRS = [{"lsr": f"2027-{n}", "session": 2027, "body": body, "title": f"relative to item {n}.",
             "sponsor": who, "withdrawn": False, "cosponsors": []}
            for n, body, who in (("0001", "HB", "Jodi Nelson"), ("0002", "HB", "Pat Example"),
                                 ("0003", "SB", "Michael Vose"), ("0004", "HB", "Pat Newell"),
                                 ("0005", "HB", "Dana Ricard"), ("0006", "SB", "Debra Altschiller"),
                                 ("0007", "HB", "Sam Holt"))]
# Where each day's site is read: the 2025-2026 page of each, and the page their record is on once
# the roster has turned (Example's at the seat he won, Vose's at the Senate number's).
_SW_PAGES = {"nelson": ("jodi-nelson-rock-13", "jodi-nelson-rock-13"),
             "altschiller": ("debra-altschiller-sd-24", "debra-altschiller-sd-24"),
             "example": ("pat-example-rock-6", "pat-example-rock-7"),
             "vose": ("michael-vose-rock-5", "michael-vose-sd-23"),
             "holt": ("sam-holt-rock-11", "sam-holt-rock-9")}


def _switch_fixture(root, turned=False):
    """The fixture project, its builders still to run, on the election above (_SW_RESULTS, the
    person's file _SW_HAND, the requests _SW_LSRS): the roster of 2025-2026 -- Nelson (Rockingham
    13), Altschiller (SD24), Vose (Rockingham 5) and Example (Rockingham 6), each with a vote of
    2026, and a former member, Sam Holt (Rockingham 11), with a vote of 2024 -- or, `turned`, the
    roster Organization Day turns it to, as tests/rehearse_turn.py fakes one
    (_turned_roster_fixture's way): that roster frozen, and the next House installed, every
    winner numbered but Dana Ricard, Vose under a new Senate number, and Holt under his own
    (people.py: a member who returns to a chamber gets their old number back). Returns (base, the
    builders, in build_all's order, the members-elect steps and the requests' among them)."""
    here = Path(".").resolve()
    base, steps = _built_site_prepare(here, root)
    # KINGSTON, Rockingham 9 of SD23, which Holt wins.
    dp = root / "site" / "districts.json"
    dist = json.loads(dp.read_text(encoding="utf-8"))
    dist["Kingston"] = {"0": {"congress": 1, "council": 3, "senate": 23, "house": [
        {"county": "Rockingham", "district": 9, "floterial": False, "seats": 1}]}}
    dp.write_text(json.dumps(dist), encoding="utf-8")
    # And an address recorded for Holt's page (generated/moved_addresses.json, keep_moved): the
    # one it had before its seat was put right, answered with a 301 wherever his page is.
    (root / "generated").mkdir(exist_ok=True)
    (root / "generated" / "moved_addresses.json").write_text(
        json.dumps({"/legislator/sam-holt-rock-12": "377310"}), encoding="utf-8")

    def leg(mid, last, first, ch, district, party="R", towns=(), committees=(), seat=""):
        tag = f"SD{district}" if ch == "S" else f"Rock {district}"
        return {"id": mid, "last": last, "first": first, "name": f"{last}, {first}", "chamber": ch,
                "party": {"R": "Republican", "D": "Democrat"}[party], "party_code": party,
                "county": "Rockingham", "county_abbr": "Rock", "district": district,
                "label": f"{'Sen.' if ch == 'S' else 'Rep.'} {first} {last} ({party} - {tag})",
                "email": f"{first.lower()}.{last.lower()}@gc.nh.gov", "url": "",
                "towns": list(towns), "committees": list(committees), "title": "", "seat": seat,
                "phone": ""}
    d = root / "data"
    nelson, altschiller = json.loads((d / "legislators.json").read_text(encoding="utf-8"))
    vose_h = leg("377300", "Vose", "Michael", "H", "5", towns=["Brentwood"])
    example_was = leg("377301", "Example", "Pat", "H", "6", party="D", towns=["Brentwood"],
                      committees=["Commerce"])
    then = [nelson, altschiller, vose_h, example_was]
    votes = json.loads((d / "member_votes.json").read_text(encoding="utf-8"))
    for m in (vose_h, example_was):
        votes.append({"member_id": m["id"], "name": m["name"], "party": m["party_code"],
                      "label": f"{m['name']}({m['party_code']}) Rock {m['district']}",
                      "year": "2026", "body": "H", "vote_number": "310", "bill": "HB1442",
                      "question": "Ought to Pass", "date": "2026-03-06", "vote": "Yea"})
    # The former member: a vote of 2024 under his own number, at the seat he held then.
    votes.append({"member_id": "377310", "name": "Holt, Sam", "party": "R",
                  "label": "Holt, Sam(R) Rockingham 11", "year": "2024", "body": "H",
                  "vote_number": "310", "bill": "HB1442", "question": "Inexpedient to Legislate",
                  "date": "2024-03-06", "vote": "Yea"})
    (d / "member_votes.json").write_text(json.dumps(votes), encoding="utf-8")
    (d / "committee_members.json").write_text(json.dumps({"H43": [
        {"id": m["id"], "name": m["name"], "party": m["party"], "party_code": m["party_code"],
         "district": m["district"], "county_code": "08", "chamber": "H", "sequence": i,
         "sitting": True, "seat_active": True} for i, m in enumerate((nelson, example_was))]}),
        encoding="utf-8")
    (root / "committees.json").write_text(json.dumps({"House": [
        {"name": "Commerce", "chair": "Pat Example", "vice_chair": "", "clerk": ""}]}),
        encoding="utf-8")
    (root / "collected").mkdir(exist_ok=True)
    (root / "collected" / "election_2026.json").write_text(json.dumps(_SW_RESULTS), encoding="utf-8")
    (root / "corrections").mkdir(exist_ok=True)
    (root / "corrections" / "members_elect.json").write_text(json.dumps(_SW_HAND), encoding="utf-8")
    (root / "lsrs.json").write_text(json.dumps(_SW_LSRS), encoding="utf-8")
    if turned:
        now = [altschiller, leg("990103", "Vose", "Michael", "S", "23",
                                towns=["Brentwood", "Danville", "Fremont", "Kingston"]),
               leg("377310", "Holt", "Sam", "H", "9", towns=["Kingston"]),
               leg("377301", "Example", "Pat", "H", "7", party="D", towns=["Fremont"],
                   committees=["Commerce"]),
               leg("990104", "Newell", "Pat", "H", "32", towns=["Brentwood", "Danville", "Fremont"]),
               leg("990105", "Other", "Ann", "H", "13", party="D", towns=["Raymond", "Stratham"]),
               # The General Court's own spelling of the ballot's "Hal Burns", which the
               # members-elect step's rule does not take for him (three letters): on a roster
               # that has turned, nothing but the roster says who sits.
               leg("990106", "Burns", "Harold", "H", "13", towns=["Raymond", "Stratham"]),
               leg("990107", "Gale", "Ruth", "H", "6", party="D", towns=["Brentwood"])]
        (d / "frozen" / "2025-2026").mkdir(parents=True)
        (d / "frozen" / "2025-2026" / "legislators.json").write_text(json.dumps(then), encoding="utf-8")
        (d / "legislators.json").write_text(json.dumps(now), encoding="utf-8")
        (root / "Docket.txt").write_text("2026|0503|3/6/2026 11:12:00 AM|HB1442|H|Ought to Pass|x\n",
                                         encoding="utf-8")
        fz = root / "frozen" / "2025-2026"
        (fz / "day").mkdir(parents=True)
        (fz / "manifest.json").write_text("{}", encoding="utf-8")

        def txt(rows):
            return "".join(f"{m['id']}|{m['name'].split(', ')[0]}|{m['name'].split(', ')[-1]}||"
                           f"{m['chamber']}|||{m['district']}|{m['party_code']}||||||\n" for m in rows)
        (fz / "day" / "legislators.txt").write_text(txt(then), encoding="utf-8")
        (root / "legislators.txt").write_text(txt(now), encoding="utf-8")
    else:
        (d / "legislators.json").write_text(json.dumps(then), encoding="utf-8")
    # The members-elect steps after the site data and the requests' before the pages, and each
    # request's page after the legislator pages, as build_all runs them. Each is held to the site's
    # meta.json, which every day has: what they write comes and goes with the day.
    extra = {"build_site_v2.py": [("build_elect_pages.py", ["--site", "site"], "site/meta.json"),
                                  ("build_members_elect.py", ["--site", "site"], "site/meta.json"),
                                  ("build_lsrs.py", ["--site", "site"], "site/meta.json")],
             "build_legislator_pages.py": [("build_request_pages.py",
                                            ["--site", "site", "--base", base], "site/meta.json")]}
    out = []
    for s in steps:
        out.append(s)
        out += extra.get(s[0], [])
    return base, out


@check("code", "the day after Organization Day is the switch day, by the rule for Organization Day; "
               "who the election moved is decided by identity, a member not returning only where their "
               "race is decided, the same people the requests drop; and the switch lasts until the "
               "roster itself turns",
       needs=("build_members_elect", "build_lsrs", "proceedings"))
def _seat_changes_rule(BME, L, P):
    """proceedings.switch_day is organization_day and a day (3 December 2026, 6 December 2028, 4
    December 2030; none for an odd year), the one day every switch reads. build_members_elect.
    seat_changes, over races as members_elect draws them: a sitting member among no race's
    winners is leaving only where their own seat's race is decided -- not one with a seat not
    final, one held by hand, or no race at all -- and one among another race's winners moved
    there, the other chamber's included; re-elected to their own seat, nothing. The leaving are
    build_lsrs.not_returning's, on the same races (its own rule for the requests). And seat_switch
    switches nothing before the day, once the roster has turned (roster_terms), or for a site
    whose newest term is neither the one the election ended nor its own; and it holds through a
    New term run that comes before the roster turns, so no night flips a member back."""
    import datetime as dt
    assert (P.switch_day(2026), P.switch_day(2028), P.switch_day(2030), P.switch_day(2027)) == (
        dt.date(2026, 12, 3), dt.date(2028, 12, 7), dt.date(2030, 12, 5), None), (
        "switch_day is not the day after Organization Day", P.switch_day(2026), P.switch_day(2028))
    assert all(P.switch_day(y) - P.organization_day(y) == dt.timedelta(days=1) for y in range(1990, 2100, 2))
    row = lambda i, ch, county, d, slug: {"id": i, "name": f"M{i}, A", "chamber": ch, "county": county,  # noqa: E731
                                          "district": d, "slug": slug}
    sitting = [row("1", "H", "Rockingham", "13", "a-rock-13"), row("2", "H", "Rockingham", "13", "b-rock-13"),
               row("3", "H", "Rockingham", "6", "c-rock-6"), row("4", "H", "Rockingham", "5", "d-rock-5"),
               row("5", "H", "Rockingham", "8", "e-rock-8"), row("6", "H", "Belknap", "2", "f-belk-2"),
               row("7", "S", "", "24", "g-sd-24"), row("8", "H", "Coos", "1", "h-coos-1")]
    won = lambda i, s: {"n": "x", "p": "R", "k": "sitting", "id": i, "s": s}  # noqa: E731
    races = {"H|Rockingham|13": {"seats": 2, "not_final": 0, "held": 0,
                                 "elected": [won("1", "a-rock-13"), {"n": "New", "k": "new"}]},
             "H|Rockingham|6": {"seats": 1, "not_final": 0, "held": 0, "elected": [{"n": "N", "k": "new"}]},
             "H|Rockingham|7": {"seats": 1, "not_final": 0, "held": 0, "elected": [won("3", "c-rock-6")]},
             "S|23": {"seats": 1, "not_final": 0, "held": 0, "elected": [won("4", "d-rock-5")]},
             "H|Rockingham|8": {"seats": 1, "not_final": 1, "held": 0, "elected": []},
             "H|Belknap|2": {"seats": 1, "not_final": 0, "held": 1, "elected": []},
             "S|24": {"seats": 1, "not_final": 0, "held": 0, "elected": [won("7", "g-sd-24")]},
             "H|Coos|2": {"seats": 2, "not_final": 0, "held": 0, "elected": [
                 {"n": "F", "p": "D", "k": "former", "id": "9", "s": "f-coos-3"},
                 {"n": "Unlinked", "p": "R", "k": "former"}]}}
    got = BME.seat_changes(races, sitting)
    assert got == {"leaving": {"2": "H|Rockingham|13"},
                   "moved": {"3": "H|Rockingham|7", "4": "S|23"},
                   "returning": {"9": "H|Coos|2"}}, (
        f"seat_changes says {got}: wanted 2 leaving (lost a decided race); 3 to Rockingham 7 and 4 "
        "to the Senate; 1 and 7 re-elected; 5 not final, 6 held and 8 in no race undecided; the "
        "former member 9 returning for Coos 2, and a former winner linked to no record nobody")
    with tempfile.TemporaryDirectory() as d:
        site = Path(d)
        (site / "legislators.json").write_text(json.dumps(sitting), encoding="utf-8")
        (site / "members_elect.json").write_text(json.dumps(
            {"election": "2026-11-03", "takes_office": "2026-12-02", "term": "2027-2028",
             "races": races}), encoding="utf-8")
        gone, undecided = L.not_returning(site, str(site / "no-results"))
    assert set(gone) == {sitting[1]["slug"]} and set(undecided) == {"e-rock-8", "f-belk-2", "h-coos-1"}, (
        f"the requests' rule disagrees: {gone} {undecided}")
    # NOTHING SWITCHES BEFORE THE DAY, NOR ONCE THE ROSTER OR THE SITE IS THE NEW TERM'S.
    root = Path(tempfile.mkdtemp(prefix="gr-seatrule-"))
    was = os.getcwd()
    try:
        (root / "collected").mkdir()
        (root / "collected" / "election_2026.json").write_text(json.dumps(_SW_RESULTS), encoding="utf-8")
        os.chdir(root)
        districts = {"Raymond": {"0": {"senate": 24, "house": [{"county": "Rockingham", "district": 13,
                                                                "seats": 2}]}}}
        args = ([], [], districts)
        none = {label: BME.seat_switch(*args, today=day, newest=newest, roster_terms=terms)
                for label, day, newest, terms in (
                    ("2 December", "2026-12-02", "2025-2026", ()),
                    ("the roster turned", "2026-12-03", "2025-2026", ("2025-2026",)),
                    ("the roster turned after a New term run", "2026-12-04", "2027-2028",
                     ("2025-2026",)),
                    ("a site two terms on", "2026-12-03", "2029-2030", ()))}
        # The New term run can come before the General Court's roster turns: the switch holds.
        on = {label: BME.seat_switch(*args, today="2026-12-03", newest=newest, roster_terms=())
              for label, newest in (("3 December", "2025-2026"),
                                    ("a New term run, the roster not turned", "2027-2028"))}
    finally:
        os.chdir(was)
        shutil.rmtree(root, ignore_errors=True)
    assert all(v is None for v in none.values()) and all(
        v and v["day"] == "2026-12-03" and v["term"] == "2027-2028" and v["leaving"] == {}
        and v["moved"] == {} and v["returning"] == {} and v["took"] == "2026-12-02"
        for v in on.values()), (
        f"seat_switch on the days and the turns: {none}, switched {on}")
    return "ok", ("switch_day is Organization Day and a day, every even year from 1990 to 2098; one "
                  "lost in a decided race leaving, two moved, one to the Senate, the not final, the "
                  "held and the raceless undecided, as the requests' own rule has them, and a former "
                  "member elected again returning; nothing "
                  "switched on 2 December, once the roster turned or for a site two terms on, and "
                  "the switch held through a New term run until the roster turns")


# What the switch's check reads of a page of the fixture's site, as the reader gets it.
def _sw_page(site, slug):
    p = site / "legislator" / f"{slug}.html"
    if not p.exists():
        return None
    t = p.read_text(encoding="utf-8")
    title = re.search(r"<title>(.*?)</title>", t)
    return {"title": title.group(1) if title else "",
            "h1": re.findall(r"<h1[^>]*>(.*?)</h1>", t, re.S),
            "former": "GR_FORMER=true" in t,
            "elect": "GR_ELECT" in t or "data-elect" in re.sub(r"<footer>.*?</footer>", "",
                                                                 re.sub(r"<header.*?</header>", "", t,
                                                                        flags=re.S), flags=re.S)}


@check("build", "the seats change hands on the site on 3 December, the day after Organization Day, by "
                "date: on 1 and 2 December the members-elect and the old titles; from 3 December a "
                "member not returning is Former on their page, in the search and in Former members, "
                "one re-elected to another seat or to the Senate drawn at it, the members-elect gone, "
                "every record as it was; and the night the roster turns changes none of it",
       needs=("build_site_v2", "freeze_term"))
def _seat_switch_by_day(B, FT):
    """The owner, 25 November 2026: "I would say wait until December 3rd to switch to the new
    titles since the swearing in ceremony happens on the morning of December 2nd". The fixture's
    election (_SW_RESULTS) is built four times as build_all builds it, every builder run, the day
    stated: 1 December, 2 December (Organization Day, whose night publishes before the members are
    sworn in), 3 December (proceedings.switch_day), each on the roster of 2025-2026, and 4
    December with the roster turned (_switch_fixture). Read on each, side by side:

      1 and 2 December, the same: the members-elect file (until 3 December) and its blocks, every
        one carrying data-until="2026-12-03"; Nelson, Example and Vose on their pages, titles and
        search rows as they sit; Nelson not among the Former members; the requests' members-elect
        Rep.-elect and Sen.-elect;
      3 December: no members-elect file and nothing drawn of it; site/seat_switch.json; Nelson
        "Former Rep. Jodi Nelson (R - Rock 13)" on her page (GR_FORMER, her own file the former
        member's), "Former Rep." in the search, in Former members, her request "Jodi Nelson (R)";
        Example "Rep. Pat Example (D - Rock 7)" and Vose "Sen. Michael Vose (R - SD23)" on their
        pages and in the search and their requests' chips, at their pages' addresses;
        Altschiller as she was; Newell's provisional page and request "Rep."; Dana Ricard, of a
        race not final, as before; and legislators.json still the roster's four, so the census
        and every list of who holds a seat are the old roster's, HB 1442's sponsor and roll call
        naming each as they sat;
      4 December, the roster turned: every title, heading, search row (but the address, which the
        roster's turn moves with a 301), Former members row and request label of the four as on 3
        December, Nelson's own file key for key and the heads app.js draws from the four's files
        the same, and no members-elect block or seat_switch.json; and Harold Burns, as the General
        Court spells the ballot's "Hal Burns" (a name the members-elect step does not take for
        his), a member: from the turn the roster alone says who sits. And a member-elect's head
        (app.js, GR_ELECT) lasts until its "until", whatever its takes_office.

    AND A FORMER MEMBER ELECTED AGAIN (the manager's word of 25 November 2026, under the owner's
    "switch to the new titles" on 3 December): Sam Holt, Rockingham 11 in 2023-2024, elected for
    Rockingham 9 as "Sam J. Holt". On 1 and 2 December a member-elect on his former member's page
    ("Sam Holt (R), member-elect"), in the search as one, in Former members, his request "Rep.-elect
    Sam J. Holt (R)"; from 3 December a member at the seat he won -- "Rep. Sam Holt (R - Rock 9)" on
    his page and its title, not former, "Took office December 2, 2026.", his own file the seat's
    with no email, no feed named; the search's member row; off Former members; his request "Rep.
    Sam Holt (R)", the record's name, its chip the seat's -- at his page's address; and the night
    the roster seats him under his own number the same words at the seat's own address, the day he
    took office no longer said, the old address a 301 to it, and the one recorded for his former
    page (generated/moved_addresses.json) as well."""
    here = Path(".").resolve()
    missing = [x for x in CHAIN_NEEDS + ["build_members_elect.py", "build_elect_pages.py",
                                         "build_lsrs.py", "build_request_pages.py"]
               if not _paths.locate(x).exists()]
    if missing or not (here / "src/pages/bills.html").exists():
        return "skip", f"not here: {', '.join(missing) or 'src/pages/bills.html'}"
    days = {"1 Dec": ("2026-12-01", False), "2 Dec": ("2026-12-02", False),
            "3 Dec": ("2026-12-03", False), "turned": ("2026-12-04", True)}
    seen = {}
    roots = []
    try:
        for label, (day, turned) in days.items():
            root = Path(tempfile.mkdtemp(prefix="gr-seatswitch-"))
            roots.append(root)
            _base, steps = _switch_fixture(root, turned)
            if turned:
                assert FT.own_roster_terms(root) == ["2025-2026"], (
                    f"the fixture's roster has not turned for freeze_term: {FT.own_roster_terms(root)}")
            _built_site_run(root, steps, env={**os.environ, "GRANITE_BUILD_DATE": day})
            site = root / "site"
            load = lambda p: json.loads((site / p).read_text(encoding="utf-8"))  # noqa: E731
            pick = 1 if turned else 0
            find = load("find.json")
            requests = {r["n"][4:]: r for r in load("idx/2027-requests.json")}
            heads = {}
            for n in requests:
                f = site / "request" / f"{n}.html"
                h = f.read_text(encoding="utf-8") if f.exists() else ""
                m = re.search(r'<dl class="rfacts">.*?</dl>', h, re.S)
                heads[n] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(0) if m else "")).strip()
            blocks = sorted({u for f in site.rglob("*.html")
                             for u in re.findall(r'data-elect data-until="([\d-]+)"',
                                                 re.sub(r"<header.*?</header>|<footer>.*?</footer>", "",
                                                        f.read_text(encoding="utf-8"), flags=re.S))})
            seen[label] = {
                "elect_file": load("members_elect.json").get("until")
                if (site / "members_elect.json").exists() else None,
                "switch_file": (site / "seat_switch.json").exists(),
                "blocks": blocks,
                "pages": {k: _sw_page(site, v[pick]) for k, v in _SW_PAGES.items()},
                "files": {k: {x: load(f"legislators/{mid}.json").get(x)
                              for x in ("former", "chamber", "district", "display_full", "email",
                                        "towns", "committees")}
                          for k, mid in (("nelson", "377204"), ("example", "377301"),
                                         ("vose", "990103" if turned else "377300"),
                                         ("holt", "377310"))},
                "find": {r[3]: r[:3] for r in find if r and r[0] in ("legislator", "former", "elect")},
                "former_list": (site / "directory/former-legislators.html").exists() and
                               "legislator/jodi-nelson-rock-13" in
                               (site / "directory/former-legislators.html").read_text(encoding="utf-8"),
                "former_holt": (site / "directory/former-legislators.html").exists() and
                               "legislator/sam-holt" in
                               (site / "directory/former-legislators.html").read_text(encoding="utf-8"),
                "holt_took": "Took office December 2, 2026." in (
                    site / "legislator" / f"{_SW_PAGES['holt'][pick]}.html").read_text(encoding="utf-8"),
                "holt_feed": "/feed/legislator/377310.xml" in (
                    site / "legislator" / f"{_SW_PAGES['holt'][pick]}.html").read_text(encoding="utf-8"),
                "roster": sorted(m["id"] for m in load("legislators.json")),
                "requests": {n: (r["sponsor_label"], r["sponsor_slug"]) for n, r in requests.items()},
                "heads": heads,
                "hb1442": {r["id"]: r for r in load("idx/2025-2026.json")}["HB1442"].get("sponsor_label"),
                "ballots": sorted(set(re.findall(r'"n": "((?:Former )?(?:Rep|Sen)\. [^"]+)"',
                                                 (site / "bill/2026/hb1442.html").read_text(encoding="utf-8")))),
                "redirects": sorted(r for r in (site / "_redirects").read_text(encoding="utf-8").splitlines()
                                    if r.startswith("/legislator/") and " 301" in r
                                    and "/:" not in r and "*" not in r),
                "provisional": _sw_page(site, "pat-newell-rock-32"),
                "burns": _sw_page(site, "harold-burns-rock-13") if turned else None,
                "nelson_file": {k: v for k, v in load("legislators/377204.json").items()
                                if k not in ("elections", "up")},
                "own_files": {k: load(f"legislators/{mid}.json")
                              for k, mid in (("nelson", "377204"), ("example", "377301"),
                                             ("vose", "990103" if turned else "377300"),
                                             ("altschiller", "377207"), ("holt", "377310"))},
            }
    finally:
        for r in roots:
            shutil.rmtree(r, ignore_errors=True)
    d1, d2, d3, dt = (seen[k] for k in ("1 Dec", "2 Dec", "3 Dec", "turned"))
    bad = []
    # ORGANIZATION DAY IS THE DAY BEFORE'S (the request pages' heads aside, which carry the day).
    same = [k for k in d1 if k not in ("heads", "own_files", "nelson_file")]
    if any(d1[k] != d2[k] for k in same) or any(
            c not in d2["heads"][n] for n, c in (("2027-0001", "Rep. Jodi Nelson (R - Rock 13)"),
                                                 ("2027-0002", "Rep. Pat Example (D - Rock 6)"),
                                                 ("2027-0003", "Sen.-elect Michael Vose (R)"))):
        bad.append("2 December is not 1 December: " + "; ".join(
            f"{k}: {d1[k]!r} -> {d2[k]!r}" for k in d1 if d1[k] != d2[k])[:900])
    if d1["elect_file"] != "2026-12-03" or d1["blocks"] != ["2026-12-03"] or d1["switch_file"]:
        bad.append(f"1 December's members-elect: file until {d1['elect_file']}, blocks {d1['blocks']}, "
                   f"seat_switch.json {d1['switch_file']}")
    # THE DAY AFTER: the members-elect gone, the switch made.
    if d3["elect_file"] is not None or d3["blocks"] or not d3["switch_file"]:
        bad.append(f"3 December's members-elect: file {d3['elect_file']}, blocks {d3['blocks']}, "
                   f"seat_switch.json {d3['switch_file']}")
    want3 = {
        "nelson": ("Former Rep. Jodi Nelson (R - Rock 13) | Granite Record",
                   "Former Representative Jodi Nelson (R - Rock 13)", True),
        "altschiller": ("Sen. Debra Altschiller (D - SD24) | Granite Record",
                        "Senator Debra Altschiller (D - SD24)", False),
        "example": ("Rep. Pat Example (D - Rock 7) | Granite Record",
                    "Representative Pat Example (D - Rock 7)", False),
        "vose": ("Sen. Michael Vose (R - SD23) | Granite Record",
                 "Senator Michael Vose (R - SD23)", False)}
    for label, day in (("3 December", d3), ("the turned night", dt)):
        for who, (title, h1, former) in want3.items():
            p = day["pages"][who]
            if not p or (p["title"], p["h1"], p["former"]) != (title, [h1], former) or p["elect"]:
                bad.append(f"{label}: {who}'s page is {p}, not {title!r} / {h1!r}")
    was = {"nelson": "Rep. Jodi Nelson (R - Rock 13)", "example": "Rep. Pat Example (D - Rock 6)",
           "vose": "Rep. Michael Vose (R - Rock 5)"}
    for who, label in was.items():
        p = d1["pages"][who]
        if not p or p["title"] != f"{label} | Granite Record" or p["former"]:
            bad.append(f"1 December: {who}'s page is {p}, not {label!r} as they sit")
    # THEIR OWN FILES, WHICH app.js DRAWS THE PAGE FROM: the former member's, and the seat won.
    f3 = d3["files"]
    if not f3["nelson"].get("former") or f3["nelson"].get("email") or f3["nelson"].get("towns") \
            or (f3["example"].get("district"), f3["example"].get("display_full")) != (
                "7", "Rep. Pat Example (D - Rock 7)") \
            or (f3["vose"].get("chamber"), f3["vose"].get("district"), f3["vose"].get("committees")) != (
                "S", "23", []):
        bad.append(f"3 December's own files: {[(k, {x: v.get(x) for x in ('former', 'chamber', 'district', 'display_full', 'email')}) for k, v in f3.items()]}")
    if d1["files"]["nelson"].get("former") or d1["files"]["example"].get("district") != "6":
        bad.append("1 December's own files already switched")
    # THE SEARCH: the same rows on 3 December and the night the roster turns, but the address the
    # turn moves.
    rows3 = {tuple(v): k for k, v in d3["find"].items()}
    rowst = {tuple(v): k for k, v in dt["find"].items()}
    for row, addr in (
            (("former", "Former Rep. Jodi Nelson", "House · Rock 13 · 2023–2026"),
             "legislator/jodi-nelson-rock-13"),
            (("legislator", "Sen. Debra Altschiller (D - SD24)", "Senate · SD24 · Democrat"),
             "legislator/debra-altschiller-sd-24"),
            (("legislator", "Rep. Pat Example (D - Rock 7)", "House · Rock 7 · Democrat"),
             "legislator/pat-example-rock-6"),
            (("legislator", "Sen. Michael Vose (R - SD23)", "Senate · SD23 · Republican"),
             "legislator/michael-vose-rock-5")):
        if rows3.get(row) != addr:
            bad.append(f"3 December's search has no row {row} at {addr}: {sorted(rows3)[:12]}")
        if row not in rowst:
            bad.append(f"the turned night's search has no row {row}: {sorted(rowst)[:12]}")
    if any(v[1].startswith("Former") for k, v in d1["find"].items() if "nelson" in k):
        bad.append("1 December's search already says Former Rep.")
    if not d3["former_list"] or not dt["former_list"] or d1["former_list"]:
        bad.append(f"Former members lists Nelson on 1 Dec {d1['former_list']}, 3 Dec "
                   f"{d3['former_list']}, turned {dt['former_list']}")
    # A FORMER MEMBER ELECTED AGAIN: a member-elect until 3 December, a member from it, and the
    # same words the night the roster seats him, at the seat's own address.
    hp = {k: seen[k]["pages"]["holt"] for k in ("1 Dec", "3 Dec", "turned")}
    if not hp["1 Dec"] or hp["1 Dec"]["title"] != "Sam Holt (R), member-elect | Granite Record" \
            or not hp["1 Dec"]["former"]:
        bad.append(f"1 December: Holt's page is {hp['1 Dec']}")
    for k in ("3 Dec", "turned"):
        p = hp[k]
        if not p or (p["title"], p["h1"], p["former"]) != (
                "Rep. Sam Holt (R - Rock 9) | Granite Record", ["Representative Sam Holt (R - Rock 9)"],
                False) or p["elect"]:
            bad.append(f"{k}: Holt's page is {p}, not a member's at Rock 9")
    if (d1["holt_took"], d3["holt_took"], dt["holt_took"], d3["holt_feed"], dt["holt_feed"]) != (
            False, True, False, False, True):
        bad.append(f"Holt's page says he took office on 1 Dec {d1['holt_took']}, 3 Dec "
                   f"{d3['holt_took']}, turned {dt['holt_took']}, and names a feed on 3 Dec "
                   f"{d3['holt_feed']}, turned {dt['holt_feed']}")
    fh = d3["files"]["holt"]
    if fh.get("former") or not d1["files"]["holt"].get("former") or (
            fh.get("chamber"), fh.get("district"), fh.get("display_full"), fh.get("email"),
            fh.get("towns"), fh.get("committees")) != (
            "H", "9", "Rep. Sam Holt (R - Rock 9)", "", ["Kingston"], []):
        bad.append(f"Holt's own file: 1 Dec {d1['files']['holt']}, 3 Dec {fh}")
    hrow = ("legislator", "Rep. Sam Holt (R - Rock 9)", "House · Rock 9 · Republican")
    if rows3.get(hrow) != "legislator/sam-holt-rock-11" or rowst.get(hrow) != "legislator/sam-holt-rock-9" \
            or (d1["find"].get("legislator/sam-holt-rock-11") or [""])[0] != "elect" \
            or any(v[0] == "former" for day in (d3, dt) for k, v in day["find"].items() if "sam-holt" in k):
        bad.append(f"Holt in the search: 1 Dec {[v for k, v in d1['find'].items() if 'sam-holt' in k]}, "
                   f"3 Dec {[(k, v) for k, v in d3['find'].items() if 'sam-holt' in k]}, turned "
                   f"{[(k, v) for k, v in dt['find'].items() if 'sam-holt' in k]}")
    if (d1["former_holt"], d3["former_holt"], dt["former_holt"]) != (True, False, False):
        bad.append(f"Former members lists Holt on 1 Dec {d1['former_holt']}, 3 Dec "
                   f"{d3['former_holt']}, turned {dt['former_holt']}")
    # Each page's own address, as _redirects writes it before its other forms (.html, a slash, a tab).
    holt301 = {k: sorted(r for r in seen[k]["redirects"]
                         if re.fullmatch(r"/legislator/sam-holt[a-z0-9-]* /legislator/[a-z0-9-]+ 301", r))
               for k in ("1 Dec", "3 Dec", "turned")}
    if holt301["1 Dec"] != ["/legislator/sam-holt-rock-12 /legislator/sam-holt-rock-11 301"] \
            or holt301["3 Dec"] != holt301["1 Dec"] or holt301["turned"] != [
                "/legislator/sam-holt-rock-11 /legislator/sam-holt-rock-9 301",
                "/legislator/sam-holt-rock-12 /legislator/sam-holt-rock-9 301"]:
        bad.append(f"Holt's old addresses: {holt301}")
    # THE ROSTER STAYS THE ROSTER until it turns, and the records name each as they sat.
    if d3["roster"] != sorted(["377204", "377207", "377300", "377301"]):
        bad.append(f"3 December's legislators.json holds {d3['roster']}: wanted the roster's four")
    for label, day in (("1 Dec", d1), ("3 Dec", d3), ("turned", dt)):
        if day["hb1442"] != "Rep. Jodi Nelson (R - Rock 13)" or not {
                "Rep. Jodi Nelson (R)", "Rep. Michael Vose (R)", "Rep. Pat Example (D)"} <= set(day["ballots"]) \
                or any(b.startswith(("Former", "Sen. Michael")) for b in day["ballots"]):
            bad.append(f"{label}: HB 1442 names {day['hb1442']} and {day['ballots']}")
    # THE REQUESTS: the labels and their pages' chips.
    want_req = {
        "1 Dec": {"2027-0001": ("Rep. Jodi Nelson (R)", "jodi-nelson-rock-13"),
                  "2027-0002": ("Rep. Pat Example (D)", "pat-example-rock-6"),
                  "2027-0003": ("Sen.-elect Michael Vose (R)", "michael-vose-rock-5"),
                  "2027-0004": ("Rep.-elect Pat Newell (R)", "pat-newell-rock-32"),
                  "2027-0005": ("Dana Ricard (D)", ""),
                  "2027-0006": ("Sen. Debra Altschiller (D)", "debra-altschiller-sd-24"),
                  "2027-0007": ("Rep.-elect Sam J. Holt (R)", "sam-holt-rock-11")},
        "3 Dec": {"2027-0001": ("Jodi Nelson (R)", "jodi-nelson-rock-13"),
                  "2027-0002": ("Rep. Pat Example (D)", "pat-example-rock-6"),
                  "2027-0003": ("Sen. Michael Vose (R)", "michael-vose-rock-5"),
                  "2027-0004": ("Rep. Pat Newell (R)", "pat-newell-rock-32"),
                  "2027-0005": ("Dana Ricard (D)", ""),
                  "2027-0006": ("Sen. Debra Altschiller (D)", "debra-altschiller-sd-24"),
                  "2027-0007": ("Rep. Sam Holt (R)", "sam-holt-rock-11")}}
    for label in ("1 Dec", "3 Dec"):
        if seen[label]["requests"] != want_req[label]:
            bad.append(f"{label}'s requests read {seen[label]['requests']}")
    chips = {"2027-0001": ("Rep. Jodi Nelson (R - Rock 13)", "Jodi Nelson (R)"),
             "2027-0002": ("Rep. Pat Example (D - Rock 6)", "Rep. Pat Example (D - Rock 7)"),
             "2027-0003": ("Sen.-elect Michael Vose (R)", "Sen. Michael Vose (R - SD23)"),
             "2027-0007": ("Rep.-elect Sam J. Holt (R)", "Rep. Sam Holt (R - Rock 9)")}
    for n, (before, after) in chips.items():
        if before not in d1["heads"][n] or after not in d3["heads"][n] or after not in dt["heads"][n]:
            bad.append(f"request {n}'s chip: 1 Dec {d1['heads'][n]!r}, 3 Dec {d3['heads'][n]!r}, "
                       f"turned {dt['heads'][n]!r}")
    # The turned night's labels, the text of 3 December's: the slugs are the pages' now.
    if {n: v[0] for n, v in dt["requests"].items() if n != "2027-0004"} != \
            {n: v[0] for n, v in d3["requests"].items() if n != "2027-0004"}:
        bad.append(f"the turned night's request labels are not 3 December's: {dt['requests']}")
    # NEW MEMBERS: Newell's provisional page a member's from 3 December; at the turn his own.
    pn = d3["provisional"]
    if not pn or pn["title"] != "Pat Newell (R) | Granite Record" or (d1["provisional"] or {}).get(
            "title") != "Pat Newell (R), member-elect | Granite Record":
        bad.append(f"Newell's provisional page: 1 Dec {d1['provisional']}, 3 Dec {pn}")
    # NELSON'S OWN FILE ON 3 DECEMBER IS THE ONE THE TURN WRITES, key for key.
    a, b = d3["nelson_file"], dt["nelson_file"]
    differ = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    if differ:
        bad.append(f"Nelson's own file on 3 December and the turned night differs in {differ}: "
                   + ", ".join(f"{k} {a.get(k)!r} / {b.get(k)!r}" for k in differ)[:500])
    # A MEMBER THE ROSTER'S TURN SEATS IS NOBODY'S TO SWITCH: the General Court's "Burns, Harold",
    # whom the members-elect step does not take for the ballot's "Hal Burns", sits.
    if not dt["burns"] or dt["burns"]["former"] or not dt["burns"]["title"].startswith("Rep. Harold Burns"):
        bad.append(f"the turned night's Harold Burns: {dt['burns']}")
    # THE HEADS app.js DRAWS FROM THE OWN FILES, the same on 3 December and the turned night; and
    # a member-elect's head lasts until GR_ELECT's "until", not its takes_office.
    order = ("nelson", "example", "vose", "altschiller")
    ge = {"id": "377204", "key": "H|Rockingham|13", "election": "2026-11-03",
          "takes_office": "2000-01-01", "until": "2999-01-02", "mode": "returning",
          "name": "Jodi Nelson", "party": "R", "title": "Rep.-elect",
          "where": "Member-elect of the New Hampshire House of Representatives, Rockingham 13."}
    js = _app_js("[" + ", ".join(f"scope.renderMemberHead({json.dumps(day['own_files'][w])})"
                                 for day in (d3, dt) for w in order)
                 + f", (window.GR_ELECT={json.dumps(ge)}, "
                   f"scope.renderMemberHead({json.dumps(d3['own_files']['nelson'])}))]",
                 names=("renderMemberHead",))
    if js is not None:
        h1 = lambda h: re.sub(r"<[^>]+>", "", " ".join(re.findall(r'<h1 class="rh1">(.*?)</h1>', h)))  # noqa: E731
        words = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r'href="[^"]*"', "", h))).strip()  # noqa: E731
        for i, who in enumerate(order):
            a, b = words(js[i]), words(js[len(order) + i])
            if a != b:
                at = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
                bad.append(f"app.js draws {who}'s head otherwise on the turned night: ...{a[max(0, at - 60):at + 80]!r} "
                           f"/ ...{b[max(0, at - 60):at + 80]!r}")
        # The heading is the name and title; the seat and its towns are on the line under it.
        if [h1(js[i]) for i in range(len(order))] != [
                "Former Representative Jodi Nelson", "Representative Pat Example",
                "Senator Michael Vose", "Senator Debra Altschiller"] \
                or "Rockingham District&nbsp;7" not in js[1] or "Senate District&nbsp;23" not in js[2] \
                or "House, 2026" not in words(js[2]):
            bad.append(f"app.js's heads on 3 December: {[words(js[i])[:200] for i in range(len(order))]}")
        if h1(js[-1]) != "Representative-elect Jodi Nelson (R)":
            bad.append(f"a member-elect's head with until ahead and takes_office past: {h1(js[-1])!r}")
        # Holt's head, from his own file: a member's at Rock 9 on 3 December and the turned night,
        # the day he took office said on the first alone.
        jh = _app_js("[" + ", ".join(f"scope.renderMemberHead({json.dumps(day['own_files']['holt'])})"
                                     for day in (d3, dt)) + "]", names=("renderMemberHead",))
        if jh is None or [h1(x) for x in jh] != ["Representative Sam Holt"] * 2 \
                or not all("Rockingham District&nbsp;9" in x for x in jh) \
                or "Took office December 2, 2026." not in words(jh[0]) or "Took office" in words(jh[1]) \
                or any("Former" in words(x) for x in jh):
            bad.append(f"app.js's heads for Holt: {[words(x)[:240] for x in jh or []]}")
    # THE ADDRESSES THE TURN MOVES, answered.
    for old, new in (("pat-example-rock-6", "pat-example-rock-7"), ("michael-vose-rock-5", "michael-vose-sd-23")):
        if f"/legislator/{old} /legislator/{new} 301" not in dt["redirects"]:
            bad.append(f"the turned night does not answer /legislator/{old}: {dt['redirects']}")
    if any(r.startswith(("/legislator/pat-example", "/legislator/michael-vose", "/legislator/jodi-nelson"))
           for r in d3["redirects"]):
        bad.append(f"3 December moves an address: {d3['redirects']}")
    assert not bad, "; ".join(bad)
    return "ok", ("1 and 2 December the same, the members-elect until 3 December; on 3 December "
                  "Nelson Former Rep. on her page, in the search and in Former members, Example at "
                  "Rock 7 and Vose at SD23 on theirs and their requests' chips, Holt, a former member "
                  "elected again, a member at Rock 9 and off Former members, the members-elect gone, "
                  "legislators.json the roster's four and HB 1442 naming each as they sat; the turned "
                  "night every title, search row, Former row and request label the same, its 301s "
                  "covering the three addresses it moves")


@check("naming", "a bill text's sponsor line is read as each era prints it, and a surname is a member only where one fits",
       needs=("text_sponsors", "build_site_v2"))
def _text_sponsors(text_sponsors, build_site_v2):
    """text_sponsors.py, 14 September: the sponsors of every term before 2023, read off
    the sponsor line of the bill's own text and matched to members who cast a roll call.

    Every line below was printed on a saved page -- 1989's "of Merrimack Dist. 4", the
    comma form from 1994, "Barnes, Jr.", "Muns, C", and the 2022 line that ran on into
    the next heading. The members are a roll call record in miniature, and each rule is
    the one the module states: an initial decides between two of a name, then the House
    county, then the district; a label naming another county refuses a match (Rep.
    Wendy Chase's label reads Belknap 5 and her bills print Strafford 18); an unnamed
    "Member #" is nobody; and the text never replaces a sponsor the database gave.
    """
    T = text_sponsors
    lines = {
        "Rep. Millard of Merrimack Dist. 4; Sen. Preston of Dist. 23":
            [("H", "Millard", "Merrimack", "4"), ("S", "Preston", "", "23")],
        "Rep. W. Riley of Cheshire Dist. 5": [("H", "W. Riley", "Cheshire", "5")],
        "Sen. Barnes, Jr., Dist 17; F. King, Dist 1":
            [("S", "Barnes", "", "17"), ("S", "F. King", "", "1")],
        "Rep. M. Fuller Clark, Rock 36; Rep. Guay, Coos 6":
            [("H", "M. Fuller Clark", "Rockingham", "36"), ("H", "Guay", "Coos", "6")],
        "Rep. Muns, C, Rock. 29": [("H", "C Muns", "Rockingham", "29")],
        "Sen. Watters, Dist 4 commission: Resources, Recreation and Development":
            [("S", "Watters", "", "4")],
    }
    for line, want in lines.items():
        got = [(p["chamber"], " ".join(p["words"]), p["county"], p["district"])
               for p in T.split(line)]
        assert got == want, f"{line!r} was read as {got}"
    assert T.split("Sen. Barnes, Jr., Dist 17")[0]["suffix"] == "Jr."
    assert T.split("Sen. Watters, Dist 4 commission: Resources")[0]["printed"] == \
        "Sen. Watters, Dist 4", "the heading the line ran into is kept as part of the sponsor"

    def row(mid, name, label, body, year, party):
        return {"member_id": mid, "name": name, "label": label, "body": body,
                "year": year, "party": party}
    sat = T.Sat([
        row("1", "Riley, William", "Riley, William(D) Ches 05", "H", "1999", "D"),
        row("2", "Riley, Ann", "Riley, Ann(R) Hills 12", "H", "1999", "R"),
        row("3", "Chase, Wendy", "Chase, Wendy(D) Belknap 05", "H", "2021", "D"),
        row("4", "Smith, John", "Smith, John(R) Rock 04", "H", "2021", "R"),
        row("5", "Smith, Jane", "Smith, Jane(D) Rock 09", "H", "2021", "D"),
        row("6", "Member #408966", "Member #408966", "H", "2021", ""),
        row("7", "Barnes, Jr., John", "Barnes, Jr., John(R)  17", "S", "2009", "R"),
    ])

    def who(term, line):
        m, _why = sat.resolve(term, T.split(line)[0])
        return m["id"] if m else None
    cases = [
        ("1999-2000", "Rep. W. Riley, Ches 5", "1", "an initial decides between two of a name"),
        ("1999-2000", "Rep. A. Riley, Hills 12", "2", "an initial decides between two of a name"),
        ("1999-2000", "Rep. Riley, Ches 5", "1", "the county decides between two of a name"),
        ("1999-2000", "Rep. Riley, Graf 5", None, "neither Riley sat for Grafton"),
        ("2021-2022", "Rep. Chase, Straf. 18", None, "the only Chase's label names another county"),
        ("2021-2022", "Rep. Smith, Rock. 9", "5", "the district decides within one county"),
        ("2021-2022", "Rep. Belanger, Rock. 9", None, "nobody of the name, and a Member # is nobody"),
        ("2009-2010", "Sen. Barnes, Jr., Dist 17", "7", "a suffix is not part of the surname"),
        ("2019-2020", "Rep. W. Riley, Ches 5", None, "he cast no roll call that term"),
        ("1999-2000", "Sen. Riley, Dist 5", None, "no Riley voted in the Senate"),
    ]
    for term, line, want, why in cases:
        assert who(term, line) == want, f"{term} {line!r} placed on {who(term, line)}: {why}"
    rec = T.record(0, T.split("Rep. W. Riley, Ches 5")[0], sat.resolve("1999-2000", T.split("Rep. W. Riley, Ches 5")[0])[0])
    assert (rec["name"], rec["party"], rec["prime"], rec["source"]) == ("William Riley", "D", True, "bill text"), rec
    bare = T.record(1, T.split("Rep. C. Brown, Graf. 14")[0], None)
    assert (bare["name"], bare["party"], bare["member_id"], bare["prime"]) == ("C. Brown", "", "", False), bare

    # On the bill's page, a sponsor read off its text keeps the seat the text printed
    # and links to the member's page as they sit now: 2023 HB 25's "Rep. McConkey,
    # Carr. 8" is not "Sen. Mark McConkey (R - SD3)" under the heading Representatives.
    from collections import defaultdict
    B = build_site_v2
    legs = {"8": {"id": "8", "name": "McConkey, Mark", "chamber": "S", "party_code": "R",
                  "district": "3", "county": "Carroll", "county_abbr": "Carr"}}
    mc = T.Sat([row("8", "McConkey, Mark", "Sen. Mark McConkey (R - SD3)", "H", "2024", "R")])
    sp_line = T.split("Rep. McConkey, Carr. 8")[0]
    text_rec = T.record(0, sp_line, mc.resolve("2023-2024", sp_line)[0])
    got = B.bill_sponsor_list("HB25", {"designation": "HB 25", "title": "capital improvements"}, "2023",
                              "2023-2024", "2025-2026", {"2023-2024": {"HB25": [text_rec]}}, legs,
                              {B.sort_name("McConkey, Mark"): legs["8"]},
                              {B.name_key("McConkey, Mark"): legs["8"]}, defaultdict(list),
                              {"8": {("2023-2024", "H"), ("2025-2026", "S")}})[0]
    assert got["display_full"] == "Rep. Mark McConkey (R - Carr 8)", (
        f"a sponsor read off the text is labelled {got['display_full']!r}, not the seat the text printed")
    assert got["slug"] == "mark-mcconkey-sd-3", f"and links {got['slug']!r}, not the member's page"

    import tempfile as _tf
    with _tf.TemporaryDirectory() as tmp:
        p = Path(tmp) / "text_sponsors.json"
        p.write_text(json.dumps({"2023-2024": {"CACR1": [{"name": "Moffett"}, {"name": "Adjutant"}],
                                               "HB25": [{"name": "McConkey"}]},
                                 "2021-2022": {"HB115": [{"name": "Suzanne Smith"}]}}), encoding="utf-8")
        sponsors = {"2023-2024": {"CACR1": [{"name": "Michael Moffett"}], "HB25": []}}
        n = T.merge_into(sponsors, p)
        assert sponsors["2023-2024"]["CACR1"] == [{"name": "Michael Moffett"}], (
            "the bill text replaced a sponsor list the database gave")
        assert n == 2 and sponsors["2023-2024"]["HB25"] and sponsors["2021-2022"]["HB115"], (
            f"{n} bills gained sponsors; wanted the two the database names nobody for")
    return "ok", ("six eras of sponsor line; initial, county and district decide in that order; "
                  "another county refuses; the database's own list is never replaced")


@check("naming", "sponsors.csv seats a sponsor where the bill's page does",
       needs=("text_sponsors",))
def _sponsors_csv_seat(text_sponsors):
    """The database files six senators of 2023-2024 under chamber H, and
    build_site_v2 corrects the seat from the bill's own printed line
    (TS.seat_into) while build_exports.sponsors only merged -- so sponsors.csv
    listed Donna Soucy, Jeb Bradley and four more as House members on 878 rows
    of 443 bills whose pages say Senate, on the page that promises a download
    and a page cannot disagree.

    Both builders take both steps, and the download is built on a fixture:
    2023 CACR 10's database row says H and its text prints "Sen. Soucy, Dist
    18"; the current term keeps its roster's seat whatever the text says.

    What this holds is that the two agree, not that the seat is right: 35
    more rows of the six, on 15 bills with no printed seat seat_into can use
    (see build_exports.sponsors), still say House on the page and here."""
    here = Path(".").resolve()
    for f in ("build_site_v2.py", "build_exports.py"):
        src = _source(_paths.locate(f)) if _paths.locate(f).exists() else ""
        if not src:
            return "skip", f"{f} not here"
        for step in ("TS.merge_into(", "TS.seat_into("):
            assert step in src, (f"{f} does not call {step[:-1]}, so its sponsors are "
                                 "not the ones the other builder publishes")
    root = Path(tempfile.mkdtemp())
    try:
        (root / "data").mkdir()
        (root / "out").mkdir()
        w = lambda p, o: (root / p).write_text(json.dumps(o), encoding="utf-8")
        w("data/bills.json", {"2023-2024": {"CACR10": {}}, "2025-2026": {"HB1": {}}})
        w("data/sponsors.json", {
            "2023-2024": {"CACR10": [{"member_id": "", "name": "Donna Soucy",
                                      "label": "Donna Soucy (D)", "party": "D",
                                      "chamber": "H", "prime": True,
                                      "source": "bill status page"}]},
            "2025-2026": {"HB1": [{"member_id": "8", "name": "Mark McConkey",
                                   "label": "Mark McConkey (R)", "party": "R",
                                   "chamber": "S", "prime": True,
                                   "source": "sponsor file"}]}})
        w("text_sponsors.json", {
            "2023-2024": {"CACR10": [{"name": "Donna Soucy", "chamber": "S",
                                      "county": "", "district": "18",
                                      "as_printed": "Sen. Soucy, Dist 18"}]},
            "2025-2026": {"HB1": [{"name": "Mark McConkey", "chamber": "H",
                                   "county": "Carroll", "district": "8",
                                   "as_printed": "Rep. McConkey, Carr. 8"}]}})
        r = _run([sys.executable, "-c",
                  "import sys; sys.path.insert(0, sys.argv[1]); import _paths; "
                  "from pathlib import Path; import build_exports as BE; "
                  "BE.sponsors(Path('out'), 'data')", str(here)],
                 cwd=root, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, (r.stderr or r.stdout)[-300:]
        with (root / "out" / "sponsors.csv").open(encoding="utf-8", newline="") as fh:
            got = {(x["term"], x["bill"]): x["chamber"] for x in csv.DictReader(fh)}
        assert got.get(("2023-2024", "CACR10")) == "S", (
            f"sponsors.csv puts Sen. Soucy in chamber {got.get(('2023-2024', 'CACR10'))!r}; "
            "the bill prints \"Sen. Soucy, Dist 18\" and its page says Senate")
        assert got.get(("2025-2026", "HB1")) == "S", (
            "the current term's seat was taken from the text over its own roster")
        return "ok", "both builders merge and seat; a 2023-2024 senator is S, the current term keeps its roster"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _ps_row(year, lsr, seq, emp, prime=False, withdrawn=False):
    """One PastSponsors row, as past_sponsors.read_view gives it."""
    return {"SessionYear": str(year), "lsr": str(lsr), "LSRSequenceNo": str(seq),
            "employeeNo": emp, "PrimeSponsor": "1" if prime else "0",
            "SignedOff": "False" if withdrawn else "True", "DateSignedOff": "",
            "SponsorWithdrawn": "True" if withdrawn else "False"}


@check("naming", "2023-2024's sponsors are the General Court's own record where each bill prints the same people, and the page's where it does not",
       needs=("text_sponsors", "build_site_v2"))
def _past_sponsors_2023(text_sponsors, build_site_v2):
    """past_sponsors.py, 26 September. The bill status page 2023-2024's sponsor lists came
    from made Rep. Mark Paige the prime sponsor of 2023 HB 32 and Rep. Terry Roy the only
    sponsor of 2024 HB 1713; both bills print "Rep. Shurtleff, Merr. 15" first, and the
    General Court's own sponsor record, PastSponsors, marks employee 376628 -- Steve
    Shurtleff -- prime on both. It left him off 29 bills, listed a Rep. Dawn Johnson on
    2023 HB 104 whom neither the record nor the bill names, and carried no id for 5,900
    of its 10,310 names.

    WHAT IS REAL HERE AND WHAT IS NOT. The bills, their stored LSRs, the employee numbers
    on them and the printed sponsor lines are the General Court's -- HB 10's, HB 1429's
    and CACR 9's lines cut short to the sponsors a rule needs -- and so are the status
    page's rows, less some of their fields. The PersonIDs are stand-ins, each the last four
    figures of the employee number (Mark Paige's is really 9942), and the ballots are
    written under them. HB 11 is made up, to put Rep. Hoell's surname in the term's record
    (377088 is not his number), and so is 2011 SR 5's LSR.

    The record is joined by the bill's own stored LSR -- never by the number, which would
    give 2011 SR 5 somebody else's -- and an employee number reaches a member through the
    legislators table's PersonID, or stands for itself where the table has none. A row no
    status-page row pairs with takes its party from the member's ballots that term:
    Shurtleff is D, and Kimberly Abare, on CACR 9, R. The chamber is the one the bill
    prints, then the ballots', and the status page's last, because the status page files
    Sens. Gendreau and Bradley (CACR 9) and Soucy (SR 9, which has no page) under the
    House. Employee 377080 is Rep. Lorrie J. Carey (member_corrections.json) and links to
    her own page; while the ballots named H. Robert Menear of Strafford 25, until
    26 September, the row was shown as printed and linked to nobody, and a row paired
    that way still is. 2023 HB 10 prints Rep. Hoell where the record lists Mark Alliegro,
    and Hoell is a member in his own right, so that bill disagrees and is published as
    its page prints it."""
    import past_sponsors as PSP
    from collections import defaultdict
    B = build_site_v2
    bills = {"2023-2024": {"HB32": {"lsr_year": "2023", "lsr_num": "0069"},
                           "HB1713": {"lsr_year": "2024", "lsr_num": "3166"},
                           "HB1429": {"lsr_year": "2024", "lsr_num": "2293"},
                           "HB10": {"lsr_year": "2023", "lsr_num": "0093"},
                           "HB104": {"lsr_year": "2023", "lsr_num": "0170"},
                           "HB11": {"lsr_year": "2023", "lsr_num": "0094"},
                           "CACR9": {"lsr_year": "2023", "lsr_num": "0900"},
                           "SR9": {"lsr_year": "2023", "lsr_num": "1067"}},
             "2011-2012": {"SR5": {"lsr_year": "2011", "lsr_num": "1234"}}}
    ps = [_ps_row(2023, 69, 1, "376628", True), _ps_row(2023, 69, 2, "409042"),
          _ps_row(2023, 69, 3, "408930"), _ps_row(2023, 69, 4, "377778"),
          _ps_row(2023, 69, 5, "376862"),
          _ps_row(2024, 3166, 1, "376628", True), _ps_row(2024, 3166, 2, "408925"),
          _ps_row(2024, 2293, 1, "409129", True), _ps_row(2024, 2293, 5, "377080"),
          _ps_row(2023, 93, 1, "375453", True), _ps_row(2023, 93, 8, "408987"),
          _ps_row(2023, 94, 1, "377088", True),
          _ps_row(2023, 170, 1, "407144", True), _ps_row(2023, 170, 4, "408927", withdrawn=True),
          _ps_row(2023, 170, 6, "376991"), _ps_row(2023, 170, 9, "218745"),
          _ps_row(2023, 900, 1, "218760", True), _ps_row(2023, 900, 3, "218755"),
          _ps_row(2023, 900, 4, "209078"), _ps_row(2023, 900, 13, "376628"),
          _ps_row(2023, 900, 16, "409060"),
          _ps_row(2023, 1067, 1, "209091", True), _ps_row(2023, 1067, 10, "209096"),
          _ps_row(2011, 1234, 1, "209027", True)]
    pl = [{"SessionYear": "2011", "LSR": "1234", "CondensedBillNo": "SR6"}]
    legs = [{"Employeeno": e, "PersonID": p, "LastName": l, "FirstName": f, "LegislativeBody": b}
            for e, p, l, f, b in [("409042", "9042", "Paige", "Mark", "H"),
                                  ("408930", "8930", "Levesque", "Cassandra", "H"),
                                  ("377778", "7778", "Edgar", "Michael", "H"),
                                  ("376862", "6862", "Schuett", "Dianne", "H"),
                                  ("408925", "8925", "Roy", "Terry", "H"),
                                  ("409129", "9129", "Mazur", "Lisa", "H"),
                                  ("375453", "5453", "Packard", "Sherman", "H"),
                                  ("408987", "8987", "Alliegro", "Mark", "H"),
                                  ("377088", "7088", "Hoell", "J.R.", "H"),
                                  ("407144", "7144", "Moffett", "Michael", "H"),
                                  ("408927", "8927", "Hobson", "Deb", "H"),
                                  ("376991", "6991", "Notter", "Jeanine", "H"),
                                  ("218745", "8745", "Gannon", "Bill", "S"),
                                  ("218760", "8760", "Abbas", "Daryl", "S"),
                                  ("218755", "8755", "Gendreau", "Carrie", "S"),
                                  ("209078", "9078", "Bradley", "Jeb", "S"),
                                  ("209091", "9091", "Watters", "David", "S"),
                                  ("209096", "9096", "Soucy", "Donna", "S")]]
    # Shurtleff, Abare and Carey have no PersonID, so their ballots are cast under the
    # employee number itself, as on the real file.
    votes = [{"member_id": v, "name": n, "label": lab, "year": "2024", "body": b, "party": p}
             for v, n, lab, b, p in [
                 ("376628", "Shurtleff, Steve", "Shurtleff, Steve(D) Merrimack 15", "H", "D"),
                 ("377080", "Carey, Lorrie J.", "Carey, Lorrie J.(D) Merrimack 1", "H", "D"),
                 ("409060", "Abare, Kimberly", "Abare, Kimberly(R) Hillsborough 1", "H", "R"),
                 ("9042", "Paige, Mark", "Paige, Mark(D) Rockingham 11", "H", "D"),
                 ("8930", "Levesque, Cassandra", "Levesque, Cassandra(D) Strafford 4", "H", "D"),
                 ("7778", "Edgar, Michael", "Edgar, Michael(D) Rockingham 29", "H", "D"),
                 ("6862", "Schuett, Dianne", "Schuett, Dianne(D) Merrimack 12", "H", "D"),
                 ("8925", "Roy, Terry", "Roy, Terry(R) Rockingham 31", "H", "R"),
                 ("9129", "Mazur, Lisa", "Mazur, Lisa(R) Hillsborough 44", "H", "R"),
                 ("5453", "Packard, Sherman", "Packard, Sherman(R) Rockingham 16", "H", "R"),
                 ("8987", "Alliegro, Mark", "Alliegro, Mark(R) Grafton 7", "H", "R"),
                 ("7088", "Hoell, J.R.", "Hoell, J.R.(R) Merrimack 27", "H", "R"),
                 ("7144", "Moffett, Michael", "Moffett, Michael(R) Merrimack 4", "H", "R"),
                 ("6991", "Notter, Jeanine", "Notter, Jeanine(R) Hillsborough 12", "H", "R"),
                 ("8745", "Gannon, Bill", "Gannon, Bill(R)  23", "S", "R"),
                 ("8760", "Abbas, Daryl", "Abbas, Daryl(R)  22", "S", "R"),
                 ("8755", "Gendreau, Carrie", "Gendreau, Carrie(R)  01", "S", "R"),
                 ("9078", "Bradley, Jeb", "Bradley, Jeb(R)  03", "S", "R"),
                 ("9091", "Watters, David", "Watters, David(D)  04", "S", "D"),
                 ("9096", "Soucy, Donna", "Soucy, Donna(D)  18", "S", "D")]]
    people = PSP.People(legs, {}, votes, [])
    printed = {"HB32": "Rep. Shurtleff, Merr. 15; Rep. M. Paige, Rock. 11; Rep. Levesque, Straf. 4; "
                       "Rep. Edgar, Rock. 29; Rep. Schuett, Merr. 12",
               "HB1713": "Rep. Shurtleff, Merr. 15; Rep. Roy, Rock. 31",
               "HB1429": "Rep. Mazur, Hills. 44; Rep. Carey, Merr. 1",
               "HB10": "Rep. Packard, Rock. 16; Rep. Hoell, Merr. 27",
               "HB11": "Rep. Hoell, Merr. 27",
               "HB104": "Rep. Moffett, Merr. 4; Rep. Notter, Hills. 12; Sen. Gannon, Dist 23",
               "CACR9": "Sen. Abbas, Dist 22; Sen. Gendreau, Dist 1; Sen. Bradley, Dist 3; "
                        "Rep. Shurtleff, Merr. 15; Rep. Abare, Hills. 1"}
    status = {"2023-2024": {
        "HB32": [{"member_id": "409042", "name": "Mark Paige", "party": "D", "prime": True},
                 {"member_id": "377778", "name": "Michael Edgar", "party": "D"},
                 {"member_id": "", "name": "Dianne Schuett", "party": "D"},
                 {"member_id": "408930", "name": "Cassandra Levesque", "party": "D"}],
        "HB1713": [{"member_id": "408925", "name": "Terry Roy", "party": "R", "prime": True}],
        "HB1429": [{"member_id": "409129", "name": "Lisa Mazur", "party": "R", "chamber": "H",
                    "prime": True}],
        "HB104": [{"member_id": "407144", "name": "Michael Moffett", "prime": True},
                  {"member_id": "376991", "name": "Jeanine Notter"},
                  {"member_id": "", "name": "Bill Gannon", "chamber": "S"},
                  {"member_id": "", "name": "Dawn Johnson"}],
        # The status page's chamber for three sitting senators: H.
        "CACR9": [{"member_id": "", "name": "Daryl Abbas", "party": "R", "chamber": "S",
                   "prime": True},
                  {"member_id": "", "name": "Carrie Gendreau", "party": "R", "chamber": "H"},
                  {"member_id": "", "name": "Jeb Bradley", "party": "R", "chamber": "H"}],
        "SR9": [{"member_id": "", "name": "David Watters", "party": "D", "chamber": "S",
                 "prime": True},
                {"member_id": "", "name": "Donna Soucy", "party": "D", "chamber": "H"}]}}
    joined, tally = PSP.join(bills, ps, pl)
    assert "SR5" not in joined.get("2011-2012", {}) and \
        tally["bills whose LSR PastLegislation files under another number"] == 1, (
        "a bill was joined to an LSR PastLegislation files under another bill number")
    doc = PSP.build(bills, status, people, joined,
                    line_of=lambda term, bid, _b: printed.get(bid))
    t = doc["2023-2024"]

    def pub(bid):
        return [(r["name"], r["prime"], r["member_id"]) for r in t[bid].get("publish") or []]

    def row(bid, emp, doc_=None):
        got = [r for r in (doc_ or t)[bid].get("publish") or () if r["employee"] == emp]
        assert len(got) == 1, f"{bid} publishes employee {emp} {len(got)} times"
        return got[0]
    assert t["HB32"]["page"] == "agrees" and pub("HB32") == [
        ("Steve Shurtleff", True, "376628"), ("Mark Paige", False, "9042"),
        ("Cassandra Levesque", False, "8930"), ("Michael Edgar", False, "7778"),
        ("Dianne Schuett", False, "6862")], f"2023 HB 32 publishes {pub('HB32')}"
    assert pub("HB1713") == [("Steve Shurtleff", True, "376628"), ("Terry Roy", False, "8925")], (
        f"2024 HB 1713 publishes {pub('HB1713')}")
    # THE PARTY OF A ROW THE STATUS PAGE LEFT OFF is the one the member's ballots carry that
    # term: 30 such rows went out with none, and the page's party count and chips with them.
    s = row("HB32", "376628")
    assert (s["party"], s["label"]) == ("D", "Rep. Steve Shurtleff (D - Merr 15)"), (
        f"2023 HB 32's prime was published as {s['label']!r}, party {s['party']!r}")
    assert t["CACR9"]["page"] == "agrees" and (
        row("CACR9", "409060")["party"], row("CACR9", "376628")["party"]) == ("R", "D"), (
        f"2023 CACR 9 publishes Abare's party as {row('CACR9', '409060')['party']!r} and "
        f"Shurtleff's as {row('CACR9', '376628')['party']!r}")
    # THE CHAMBER IS THE PRINTED ONE, then the ballots': the status page's H for a senator
    # is last, and on SR 9, which has no page, the ballots come first.
    ch = [(r["name"], r["chamber"]) for r in t["CACR9"]["publish"]]
    assert [c for _n, c in ch] == ["S", "S", "S", "H", "H"], (
        f"2023 CACR 9 publishes the chambers {ch}: Gendreau and Bradley are senators")
    assert row("SR9", "209096")["chamber"] == "S" and t["SR9"]["page"] == "no page", (
        "Sen. Donna Soucy was published in the House on 2023 SR 9, which has no page")
    # 377080 IS REP. LORRIE J. CAREY and is linked like anyone else. A row paired only by
    # elimination at another seat is still shown as printed: it was hers, while the site's
    # record of the number named H. Robert Menear of Strafford 25.
    c = row("HB1429", "377080")
    assert (c["member_id"], c["name"], c["party"], c["chamber"], c.get("unlinked")) == (
        "377080", "Lorrie J. Carey", "D", "H", None), f"377080 was published as {c}"
    menear = [dict(v, name="Menear, H. Robert", label="Menear, H. Robert(D) Straf 25")
              if v["member_id"] == "377080" else v for v in votes]
    old = PSP.build(bills, status, PSP.People(legs, {}, menear, []), joined,
                    line_of=lambda term, bid, _b: printed.get(bid))["2023-2024"]
    c0 = row("HB1429", "377080", old)
    assert (c0["member_id"], c0["name"], c0.get("county"), c0.get("district")) == (
        "", "Carey", "Merrimack", "1") and c0.get("unlinked"), (
        f"a row paired only by elimination at another seat was published as {c0}: wanted "
        "Carey, Merrimack 1, as printed and unlinked")
    assert t["HB10"]["page"] == "differs" and not t["HB10"].get("publish"), (
        "2023 HB 10 prints Rep. Hoell where the record lists Mark Alliegro, and it was "
        f"taken as {t['HB10']['page']}")
    assert [n for n, _p, _i in pub("HB104")] == ["Michael Moffett", "Jeanine Notter", "Bill Gannon"], (
        f"2023 HB 104 publishes {pub('HB104')}: the withdrawn Hobson or the status page's "
        "Dawn Johnson reached it")
    page_list = [{"member_id": "7088", "name": "J.R. Hoell", "source": "bill text"}]
    merged = {k: {b: list(v) for b, v in bs.items()} for k, bs in status.items()}
    took = PSP.merge(merged, doc, {"2023-2024": {"HB10": page_list}})
    assert merged["2023-2024"]["HB10"] == page_list and took["page"] == 1, (
        "a bill the record and its page disagree on did not take the page's list")
    assert merged["2023-2024"]["HB32"][0]["name"] == "Steve Shurtleff", "the merge left HB 32 as it was"

    # On the page: Shurtleff first, prime, with his party, and a link to his own page; Rep.
    # Lorrie J. Carey linked to hers and filed under her, like any other sponsor.
    people_ = {"376628": {"id": "376628", "name": "Shurtleff, Steve", "chamber": "H",
                          "party": "D", "county": "Merrimack", "district": "15",
                          "slug": "steve-shurtleff-merr-15"},
               "377080": {"id": "377080", "name": "Carey, Lorrie J.", "chamber": "H",
                          "party": "D", "county": "Merrimack", "district": "1",
                          "slug": "lorrie-j-carey-merr-1"}}
    sponsored = defaultdict(list)
    sp = B.bill_sponsor_list("HB32", {"designation": "HB 32", "title": "a bill"}, "2023",
                             "2023-2024", "2025-2026", merged, people_, {}, {}, sponsored)
    assert sp[0]["prime"] and sp[0]["slug"] == "steve-shurtleff-merr-15" \
        and sp[0]["party"] == "D", (
        f"2023 HB 32's first sponsor is {sp[0].get('name')} ({sp[0].get('slug')!r}), "
        f"party {sp[0].get('party')!r}")
    merged["2023-2024"]["HB1429"] = t["HB1429"]["publish"]
    sp = B.bill_sponsor_list("HB1429", {"designation": "HB 1429", "title": "a bill"}, "2024",
                             "2023-2024", "2025-2026", merged, people_, {}, {}, sponsored)
    c = [s for s in sp if s.get("employee") == "377080"][0]
    assert c["slug"] == "lorrie-j-carey-merr-1" and any(
        x["bill"] == "HB1429" for x in sponsored.get("377080") or ()), (
        f"employee 377080's sponsorship of 2024 HB 1429 links {c['slug']!r} and is filed under "
        f"{[k for k, v in sponsored.items() if any(x['bill'] == 'HB1429' for x in v)]}: "
        "wanted Rep. Lorrie J. Carey's page")
    here = Path(".").resolve()
    for f in ("build_site_v2.py", "build_exports.py"):
        src = _paths.locate(f).read_text(encoding="utf-8") if _paths.locate(f).exists() else ""
        assert not src or "PSP.merge_into(" in src, (
            f"{f} does not call past_sponsors.merge_into, so its 2023-2024 sponsors are not "
            "the ones the other builder publishes")
    return "ok", ("HB 32 and HB 1713 prime Shurtleff, D; Abare R on CACR 9; Gendreau, Bradley "
                  "and Soucy in the Senate; 377080 linked as Rep. Lorrie J. Carey; the record's "
                  "list where the page agrees, the page's where not; joined by the stored LSR")


@check("naming", "a senator printed as Rep. is the senator the sponsor record names, never a representative of the surname",
       needs=("text_sponsors",))
def _senators_printed_as_rep(text_sponsors):
    """A House seat is always printed with its county; "Rep. Boyce, Dist 4" is Sen. Robert
    Boyce, and read as a Rep. it went to Rep. Laurie Boyce on 2001 HB 428 and 2003
    HB 1360 -- as 2001 SB 84's O'Neil, 2002 HB 1301's Johnson and 2003 HB 1242's Kenney
    went to representatives of those names. Such a piece is placed on a senator only where
    the General Court's sponsor record lists them live on that bill at the district
    printed -- Carl Johnson is printed at Dist 3 in 2001-2002 while his roll-call label
    says 2 -- and otherwise stays as printed: 1999-2000's record lacks Sen. Larsen on
    HB 1594. Every line is the one the page prints."""
    T = text_sponsors
    import past_sponsors as PSP

    def row(mid, name, label, body, year, party):
        return {"member_id": mid, "name": name, "label": label, "body": body,
                "year": year, "party": party}
    sat = T.Sat([
        row("376310", "Boyce, Laurie", "Boyce, Laurie(R) Belk 05", "H", "2001", "R"),
        row("376310", "Boyce, Laurie", "Boyce, Laurie(R) Belk 05", "H", "2003", "R"),
        row("209042", "Boyce, Robert", "Boyce, Robert(R)  04", "S", "2001", "R"),
        row("209042", "Boyce, Robert", "Boyce, Robert(R)  04", "S", "2003", "R"),
        row("205015", "Johnson, Carl", "Johnson, Carl(R)  02", "S", "2002", "R"),
        row("376236", "Johnson, Nancy", "Johnson, Nancy(R) Graf 13", "H", "2002", "R"),
        row("209046", "O'Neil, Daniel", "O'Neil, Daniel(D)  18", "S", "2001", "D"),
        row("376259", "O'Neil, Michael", "O'Neil, Michael(R) Rock 15", "H", "2001", "R"),
        row("209049", "Kenney, Joseph", "Kenney, Joseph(R)  03", "S", "2003", "R"),
        row("376484", "Kenney, Bettie", "Kenney, Bettie(D) Straf 6", "H", "2003", "D"),
        row("205035", "Larsen, Sylvia", "Larsen, Sylvia(D)  15", "S", "2000", "D"),
        row("376400", "Larsen, Ann", "Larsen, Ann(R) Hills 7", "H", "2000", "R"),
    ])
    lines = [
        ("2001-2002", "HB428", "Rep. Mirski, Graf 12; Rep. Phinizy, Sull 7; Rep. Dudley, Graf 14; "
                               "Sen. Roberge, Dist 9; Rep. Boyce, Dist 4"),
        ("2003-2004", "HB1360", "Rep. Souza, Hills 51; Sen. Martel, Dist 18; Rep. Boyce, Dist 4"),
        ("2001-2002", "SB84", "Sen. Pignatelli, Dist 13; Sen. O'Hearn, Dist 12; Rep. O'Neil, Dist 18"),
        ("2001-2002", "HB1301", "Rep. Hopper, Hills 5; Sen. Boyce, Dist 4; Rep. Johnson, Dist 3"),
        ("2001-2002", "HB1439", "Rep. Wendelboe, Belk 2; Sen. Johnson, Dist 3; Sen. Boyce, Dist 4"),
        ("2003-2004", "HB1242", "Rep. Kurk, Hills 48; Sen. Odell, Dist 8; Rep. Kenney, Dist 3"),
        ("1999-2000", "HB1594", "Rep. Flora, Hills 15; Rep. Larsen, Dist 15; Sen. Disnard, Dist 8"),
    ]
    rec = {"HB428": ["209042"], "HB1360": ["209042"], "SB84": ["209046"],
           "HB1301": ["209042", "205015"], "HB1439": ["205015", "209042"],
           "HB1242": ["209049"], "HB1594": []}
    joined = {}
    for term, bid, _line in lines:
        joined.setdefault(term, {})[bid] = {
            "lsr": "", "rows": [{"employee": e, "sequence": i + 5, "prime": False,
                                 "withdrawn": False} for i, e in enumerate(rec[bid])]}
    got, _tally, _ = T.build({}, sat, sponsor_record=(joined, PSP.People([], {})), lines=lines)

    def who(term, bid, name):
        r = [x for x in got[term][bid] if x["as_printed"].startswith(f"Rep. {name}, Dist")][0]
        return r["member_id"], r["chamber"]
    want = [("2001-2002", "HB428", "Boyce", ("209042", "S")),
            ("2003-2004", "HB1360", "Boyce", ("209042", "S")),
            ("2001-2002", "SB84", "O'Neil", ("209046", "S")),
            ("2001-2002", "HB1301", "Johnson", ("205015", "S")),
            ("2003-2004", "HB1242", "Kenney", ("209049", "S")),
            ("1999-2000", "HB1594", "Larsen", ("", "H"))]
    for term, bid, name, w in want:
        assert who(term, bid, name) == w, (
            f"{term} {bid} 'Rep. {name}, Dist' placed on {who(term, bid, name)}, wanted {w}")
    # The district is a real test: without the page that prints Johnson at Dist 3 that
    # term, his label's 2 does not match, and he is left as printed.
    got2, _t, _ = T.build({}, sat, sponsor_record=(joined, PSP.People([], {})),
                          lines=[x for x in lines if x[1] != "HB1439"])
    r = [x for x in got2["2001-2002"]["HB1301"] if x["as_printed"].startswith("Rep. Johnson")][0]
    assert r["member_id"] == "", "a senator was placed at a district nothing printed for them"
    # No sponsor record at all: nobody is placed, and no representative either.
    got3, _t, _ = T.build({}, sat, sponsor_record=None, lines=lines[:1])
    r = [x for x in got3["2001-2002"]["HB428"] if x["as_printed"].startswith("Rep. Boyce")][0]
    assert r["member_id"] == "", f"'Rep. Boyce, Dist 4' went to {r['member_id']} with no record"
    return "ok", ("Boyce twice, O'Neil, Johnson (at the district that term's bills print) and "
                  "Kenney placed on the senator; never on a representative; Larsen left as printed")


@check("naming", "a sponsor printed before 1999 is placed on a person only where the bill's own sponsor rows settle it",
       needs=("text_sponsors",))
def _pre_1999_sponsors_placed(text_sponsors):
    """past_roster.py, 13 November 2026. A bill of 1989-1998 prints "Rep. Guay, Coos 6". The
    General Court's sponsor record for that bill (PastSponsors, by its stored LSR) holds
    its sponsors' employee numbers, and past_members.json names each number. A printed
    sponsor takes the number only where the bill's OWN rows settle it: the surname fits one
    number (an initial or first name printed before it picks one of two), nothing else.
    A misprint, two numbers of a surname with nothing to choose, and a number no list names
    stay exactly as printed. The employee number is the General Court's, in `employee`;
    the party is none; the id is a member's only where a later roll call was cast under
    that number."""
    T = text_sponsors
    import past_roster as PR
    import past_sponsors as PSP
    pm = {"372001": {"name": "Guay, Roland", "chamber": "H"},
          "372002": {"name": "Lawton, Dennis", "chamber": "H"},
          "372003": {"name": "Lawton, Ruth", "chamber": "H"},
          "372004": {"name": "Buckley, Anne", "chamber": "H"},
          "205001": {"name": "Blaisdell, Clesson", "chamber": "S"},
          "372005": {"name": "Dykstra (SEE Emp #375839), Leona", "chamber": "H"},
          "372006": {"name": "Barnes, Jr., John", "chamber": "H"}}
    people = PSP.People([], pm)
    sat = T.Sat([{"member_id": "372001", "name": "Guay, Roland J.", "label": "Guay, Roland(R) Coos 06",
                  "body": "H", "year": "1999", "party": "R"}])
    lines = [("1993-1994", "HB1", "Rep. Guay, Coos 6; Rep. D. Lawton, Hills 4; Rep. Buckly, Graf 2; "
                                  "Rep. Blaisdell, Dist 10; Rep. Nobody, Ches 3"),
             ("1993-1994", "HB2", "Rep. Lawton, Hills 4; Rep. R. Lawton, Hills 5; Rep. Dykstra, Rock 1; "
                                  "Rep. Barnes, Jr., Merr 2")]
    rows = lambda *emps: {"lsr": "", "rows": [{"employee": e, "sequence": i, "prime": i == 0,
                                               "withdrawn": False} for i, e in enumerate(emps)]}
    joined = {"1993-1994": {"HB1": rows("372001", "372002", "372004", "205001", "372099"),
                            "HB2": rows("372002", "372003", "372005", "372006")}}
    got, tally, _ = T.build({}, sat, sponsor_record=(joined, people), lines=lines)
    h1 = {r["as_printed"].split(",")[0]: r for r in got["1993-1994"]["HB1"]}
    h2 = got["1993-1994"]["HB2"]
    g = h1["Rep. Guay"]
    assert (g["name"], g["employee"], g["member_id"], g["party"]) == ("Roland J. Guay", "372001", "372001", ""), \
        f"a number a later roll call was cast under keeps the member's own name and id: {g}"
    d = h1["Rep. D. Lawton"]
    assert (d["name"], d["employee"], d["member_id"]) == ("Dennis Lawton", "372002", ""), \
        f"an initial that fits one of two Lawtons did not place D. Lawton: {d}"
    assert "employee" not in h2[0] and h2[0]["name"] == "Lawton", \
        f"a bare surname two numbers fit was placed: {h2[0]}"
    assert h2[1]["employee"] == "372003" and h2[1]["name"] == "Ruth Lawton", h2[1]
    b = h1["Rep. Buckly"]
    assert "employee" not in b and b["name"] == "Buckly" and b["member_id"] == "", \
        f"a misprint was matched by a guess: {b}"
    s = h1["Rep. Blaisdell"]
    assert (s["chamber"], s["employee"], s["name"]) == ("S", "205001", "Clesson Blaisdell") \
        and s["as_printed"].startswith("Rep. Blaisdell"), \
        f"a senator printed as Rep. with a Senate district is not shown as one: {s}"
    assert "employee" not in h1["Rep. Nobody"], "a surname on no row of the bill was placed"
    assert h2[2]["name"] == "Leona Dykstra" and h2[3]["name"] == "John Barnes Jr.", \
        f"the General Court's spelling of a name was not kept: {h2[2]['name']!r}, {h2[3]['name']!r}"
    assert PR.split_label("Dykstra (SEE Emp #375839), Leona")[3] == "375839"
    for r in [*h1.values(), *h2]:
        assert not r.get("party"), f"a party before 1999: {r}"
        assert not str(r.get("member_id") or "").startswith("gr-") and not str(r.get("employee") or "").startswith("gr-")
    # The same lines with no sponsor record place nobody.
    got0, _t, _ = T.build({}, sat, sponsor_record=None, lines=lines)
    assert not any(r.get("employee") for rs in got0["1993-1994"].values() for r in rs), \
        "a sponsor was placed with no sponsor record"
    # A shared full name between two numbers is reported, so the filter can tell them apart.
    two = {"HB1": [{"matched": PR.MATCHED, "employee": "1", "name": "Frank Allen"}],
           "HB2": [{"matched": PR.MATCHED, "employee": "2", "name": "Frank Allen"},
                   {"matched": PR.MATCHED, "employee": "3", "name": "Mary Allen"}]}
    assert PR.shared_names(two) == {"Frank Allen"}, PR.shared_names(two)
    return "ok", ("a unique surname, an initial between two Lawtons and a senator printed as Rep. are placed "
                  "on the General Court's name and number; a misprint, an unsettled surname and a surname "
                  "off the bill stay as printed; no party; no gr- id in either field")


@check("naming", "a Granite Record id (gr-) and a General Court employee number are never written into each other's field",
       needs=("gr_ids", "gr_register"))
def _gr_ids_apart(GR, REG):
    """gr_ids.py, 13 November 2026 (the owner: "distinguish the IDs assigned by Granite Record from the
    official ones so that the two don't get mixed up"). The General Court's employee number is digits
    only and is a person's key wherever the General Court supplies one; Granite Record's id is gr- and
    a serial, made here only for a person the record names with no number. They live in separate fields
    (`gc_employee_number`, `granite_id`) of every table that shows an identifier. Held on fixtures, each
    a mistake the check must see: a gr- id in the employee-number field, or an employee number in the id
    field; a digits-only number no list of the General Court's names; a person keyed by a gr- id whose
    official number is known; an id the register does not hold. And the register: ids never reissued,
    renumbered or deleted, a number found later the one change an entry may take."""
    ok = {"gc_employee_number": "373027", "granite_id": "", "person": "373027", "name": "A"}
    gr = {"gc_employee_number": "", "granite_id": "gr-0001", "person": "gr-0001", "name": "B"}
    reg = {"format": 1, "ids": [{"id": "gr-0001", "named_as": "B", "issued": "2026-11-13",
                                 "evidence": "x", "employee_number": ""}]}
    assert GR.check_rows([ok, gr], known={"373027"}, reg=reg) == [], GR.check_rows([ok, gr], {"373027"}, reg)
    cases = [
        ("a gr- id in the employee-number field", dict(ok, gc_employee_number="gr-0001")),
        ("an employee number in the id field", dict(gr, granite_id="373027")),
        ("digits only and not the General Court's", dict(ok, gc_employee_number="999998", person="999998")),
        ("an employee number that is not digits", dict(ok, gc_employee_number="37302X")),
        ("both set", dict(ok, granite_id="gr-0001")),
        ("neither set", dict(ok, gc_employee_number="")),
        ("an official number, keyed by a gr- id", dict(ok, person="gr-0001")),
        ("an id the register does not hold", dict(gr, granite_id="gr-0009", person="gr-0009")),
        ("an alias the register does not hold", dict(ok, granite_id_aliases=["gr-0044"])),
    ]
    for what, row in cases:
        assert GR.check_rows([row], known={"373027"}, reg=reg), f"not seen: {what}"
    found = {"format": 1, "ids": [dict(reg["ids"][0], employee_number="373027")]}
    assert GR.check_rows([dict(gr, gc_employee_number="", person="gr-0001")], reg=found), \
        "a person keyed by a gr- id whose official number the register has since found was not seen"
    assert not GR.check_rows([dict(ok, granite_id_aliases=["gr-0001"])], known={"373027"}, reg=found), \
        "the official number as key and the gr- id as its alias was refused"
    # The register's shape.
    assert GR.check_register(reg) == [] and GR.check_register({"format": 1, "ids": []}) == []
    for what, bad in (("a digits-only id", {"ids": [{"id": "373027", "named_as": "x"}]}),
                      ("an id twice", {"ids": [dict(reg["ids"][0]), dict(reg["ids"][0])]}),
                      ("an id nobody holds", {"ids": [{"id": "gr-0001", "named_as": ""}]}),
                      ("out of order", {"ids": [{"id": "gr-0002", "named_as": "x"}, {"id": "gr-0001", "named_as": "y"}]}),
                      ("a gr- id as the employee number", {"ids": [dict(reg["ids"][0], employee_number="gr-0002")]}),
                      ("a number held twice", {"ids": [dict(reg["ids"][0], employee_number="5"),
                                                       {"id": "gr-0002", "named_as": "z", "employee_number": "5"}]})):
        assert GR.check_register(bad), f"a register with {what} was called well formed"
    # Append-only against an earlier copy.
    two = {"ids": [reg["ids"][0], {"id": "gr-0002", "named_as": "C", "issued": "2026-11-14"}]}
    assert GR.check_only_grows(reg, two) == [] and GR.check_only_grows(reg, found) == []
    assert GR.check_only_grows(two, reg), "an id deleted from the register was not seen"
    renamed = {"ids": [dict(reg["ids"][0], named_as="Someone else")]}
    assert GR.check_only_grows(reg, renamed), "an id reissued to another person was not seen"
    assert GR.check_only_grows(found, {"ids": [dict(found["ids"][0], employee_number="373028")]}), \
        "a recorded number changed was not seen"
    assert GR.check_only_grows(found, reg), "a recorded number removed was not seen"
    # The writer: serials in order, never reused, a number found never over another.
    r = {"format": 1, "ids": []}
    a = REG.issue(r, "Jane Doe", "no number in any list", "2026-11-13")
    b = REG.issue(r, "John Roe", "no number in any list", "2026-11-13")
    assert (a, b) == ("gr-0001", "gr-0002") and GR.check_register(r) == [], (a, b)
    REG.found(r, "gr-0001", "373027")
    try:
        REG.found(r, "gr-0001", "373028")
        raise AssertionError("a recorded number was changed")
    except SystemExit:
        pass
    try:
        REG.found(r, "gr-0002", "gr-0001")
        raise AssertionError("a gr- id was recorded as an employee number")
    except SystemExit:
        pass
    assert GR.is_gr("gr-0001") and not GR.is_gr("373027") and GR.looks_official("373027") \
        and not GR.looks_official("gr-0001")
    return "ok", ("a gr- id in the employee-number field, an employee number in the id field, a digits-only "
                  "number no General Court list names, a gr- key for a person with an official number, and "
                  "a register that loses, renumbers or reissues an id are each seen; a number found later "
                  "is the one change an entry takes")


@check("files", "only a person's run writes the register of Granite Record ids; it is well formed and only ever grows",
       needs=("gr_ids",))
def _gr_register_files(GR):
    """generated/gr_ids.json holds the ids this site made for people the General Court gives no number
    (gr_ids.py). Like generated/person_numbers.json it is only ever added to and never rewritten by the
    nightly: no code file writes it but src/ops/gr_register.py, by any of the shapes the person-number
    register's check reads. What is there is well formed, and against the copy git holds (HEAD, and
    origin/dev where it has one) every id is still there, issued to the same name on the same day,
    with any official number it held."""
    stem = r"(?<![\w-])gr_ids\.json"
    HELD = re.compile(r'^[ \t]*([A-Za-z_]\w*)[ \t]*(?::[^=\n]*)?=[^=\n][^\n]*' + stem, re.M)

    def writes(src):
        if re.search(r'open\s*\([^)]*' + stem + r'[^)]*["\'][wax]', src) or \
           re.search(stem + r'[^\n]{0,60}\.write_(?:text|bytes)', src):
            return True
        for held in set(HELD.findall(src)):
            n = re.escape(held)
            if re.search(r'\b%s\s*\.\s*(?:write_text|write_bytes)\s*\('
                         r'|\b%s\s*\.\s*open\s*\(\s*(?:mode\s*=\s*)?["\'][wax]'
                         r'|\bopen\s*\(\s*%s\s*,\s*(?:mode\s*=\s*)?["\'][wax]'
                         r'|\b(?:os\.replace|os\.rename|shutil\.(?:copy\w*|move))'
                         r'\s*\([^)\n]*,\s*%s\s*\)' % (n, n, n, n), src):
                return True
        return False

    for text, w in (('open("generated/gr_ids.json", "w")', True),
                    ('Path("generated/gr_ids.json").write_text(t)', True),
                    ('REGISTER = Path("generated/gr_ids.json")\nREGISTER.write_text(t)', True),
                    ('def f(path="generated/gr_ids.json"):\n    reg = load(path, None)', False),
                    ('json.loads(Path("generated/gr_ids.json").read_text())', False)):
        assert writes(text) == w, f"the register's reader reads {text!r} as " + ("no write" if w else "a write")
    bad = []
    for f in _paths.code_files("*.py"):
        # The writer, the module that names the path, and this file, whose cases name it on purpose.
        if f.name in ("gr_register.py", "gr_ids.py") or _in_suite(f):
            continue
        if writes(f.read_text(encoding="utf-8", errors="replace")):
            bad.append(f.name)
    assert not bad, "these write the register of Granite Record ids, which only " \
                    "src/ops/gr_register.py may: " + ", ".join(bad)
    reg = _paths.ROOT / "generated" / "gr_ids.json"
    assert reg.exists(), "generated/gr_ids.json is not here: the register is tracked, even when empty"
    now = json.loads(reg.read_text(encoding="utf-8"))
    problems = GR.check_register(now)
    assert not problems, "the register is not well formed: " + "; ".join(problems[:5])
    compared = []
    for ref in ("HEAD", "origin/dev"):
        r = _run(["git", "show", f"{ref}:generated/gr_ids.json"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            lost = GR.check_only_grows(json.loads(r.stdout), now)
            assert not lost, f"the register is only ever added to, and against {ref}'s: " + "; ".join(lost[:5])
            compared.append(ref)
    return "ok", (f"no other code file writes it; well formed; {len(now['ids'])} id(s); "
                  + (f"nothing lost or moved against {' and '.join(compared)}" if compared
                     else "no committed copy to compare with yet"))


@check("data", "the 1989-1998 table and the sponsor rows keep the General Court's numbers and Granite Record's ids "
       "in their own fields, and name only numbers the General Court's lists name")
def _past_roster_data():
    """generated/past_roster.json (build_past_roster.py) and the sponsors text_sponsors.json places on a
    person: every employee number is digits only and one the General Court's own files name (PastSponsors,
    its list of members, its legislators table); no gr- id is in an employee-number or member-id field; no
    person with an official number is keyed by a gr- id; every gr- id is in the register. Skips where the
    table or the General Court's files are not on this disk."""
    import gr_ids as GR
    p = Path("generated/past_roster.json")
    if not p.exists():
        return "skip", "no generated/past_roster.json here (python3 src/parse/build_past_roster.py --apply)"
    doc = json.loads(p.read_text(encoding="utf-8"))
    reg = GR.load_register()
    known = None
    ps, pm, lg = Path("db/past/PastSponsors.psv"), Path("past_members.json"), Path("db/Legislators.psv")
    if ps.exists() and pm.exists():
        known = {l.split("|")[3].strip() for l in ps.read_text(encoding="utf-8").splitlines() if l.count("|") >= 4}
        known |= set(json.loads(pm.read_text(encoding="utf-8")))
    bad = GR.check_rows(doc["rows"], known=known, reg=reg)
    assert not bad, "the 1989-1998 table: " + "; ".join(bad[:5])
    ts = Path("text_sponsors.json")
    n = 0
    if ts.exists():
        for term, bills in json.loads(ts.read_text(encoding="utf-8")).items():
            for bid, recs in bills.items():
                for r in recs:
                    if r.get("employee") or str(r.get("member_id") or "").startswith("gr-"):
                        n += 1
                        row = {"gc_employee_number": r.get("employee") or "", "granite_id": "",
                               "person": r.get("employee") or "", "name": f"{term} {bid} {r.get('name')}"}
                        assert not GR.check_rows([row], known=known), f"{term} {bid}: {GR.check_rows([row], known=known)}"
                        assert not GR.is_gr(r.get("member_id")), \
                            f"{term} {bid}: a gr- id in the member-id field of {r.get('name')}"
    return "ok", (f"{len(doc['rows']):,} person-terms and {n:,} placed sponsors: every employee number "
                  f"digits only{' and named by a General Court list' if known else ''}; "
                  f"{len(reg['ids']) if reg else 0} gr- id(s) in the register")


@check("build", "the 1989-1998 table has one row a person a term a chamber, with the General Court's number and name, "
       "the printed seat and no party",
       needs=("build_past_roster", "past_roster", "past_sponsors"))
def _past_roster_table(BPR, PR, PSP):
    """build_past_roster.py, 13 November 2026. From the sponsor route alone: a person with a live sponsor row
    on a bill of the term has a row in the chamber the bill printed (else the list of members', marked so);
    the seats are the ones the bills printed, most-printed first; the name is the General Court's; the
    employee number is in gc_employee_number and granite_id is empty; no party; a withdrawn sponsor is not a
    row; a number no list names has a row with no name. Coverage is people against 400 and 24."""
    pm = {"1": {"name": "Guay, Roland", "chamber": "H"}, "2": {"name": "Blaisdell, Clesson", "chamber": "S"},
          "3": {"name": "Dykstra (SEE Emp #9), Leona", "chamber": "H"}}
    people = PSP.People([], pm)
    live = lambda e, w=False: {"employee": e, "sequence": 0, "prime": False, "withdrawn": w}
    joined = {"1993-1994": {"HB1": {"lsr": "", "rows": [live("1"), live("2"), live("3"), live("4"), live("5", True)]},
                            "HB2": {"lsr": "", "rows": [live("1")]}}}
    M = PR.MATCHED
    text = {"1993-1994": {"HB1": [{"employee": "1", "matched": M, "chamber": "H", "county": "Coos", "district": "6"},
                                  {"employee": "2", "matched": M, "chamber": "S", "county": "", "district": "10"}],
                          "HB2": [{"employee": "1", "matched": M, "chamber": "H", "county": "Coos", "district": "6"}]}}
    rows = BPR.rows_of(joined, text, people, voters={"2"}, terms=("1993-1994",))
    by = {r["person"]: r for r in rows}
    assert sorted(by) == ["1", "2", "3", "4"], f"people with a live sponsor row: {sorted(by)}"
    g = by["1"]
    assert (g["chamber"], g["name"], g["gc_employee_number"], g["granite_id"], g["bills"], g["bills_printed"]) == \
        ("H", "Roland Guay", "1", "", 2, 2) and g["seats"] == [{"county": "Coos", "district": "6", "bills": 2}], g
    assert by["2"]["chamber"] == "S" and by["2"]["voted_since_1999"] and not g["voted_since_1999"], by["2"]
    assert by["3"]["chamber_source"].startswith("the list of members") and by["3"]["seats"] == [] \
        and by["3"]["same_person_as_employee_number"] == "9" and by["3"]["name"] == "Leona Dykstra", by["3"]
    assert by["4"]["name"] == "" and by["4"]["chamber"] == "", "a number no list names has a row with no name"
    assert not any("party" in r for r in rows), "a party before 1999"
    import gr_ids as GR
    assert GR.check_rows(rows, reg={"ids": []}) == []
    cov = BPR.coverage(rows, terms=("1993-1994",))["1993-1994"]
    assert cov["H"] == {"people": 2, "of_seats": 400, "with_a_printed_seat": 1, "districts_printed": 1,
                        "roll_only": 0, "nameless": 0} and cov["S"]["people"] == 1 \
        and cov["S"]["of_seats"] == 24 and cov["no_chamber"] == 1, cov
    return "ok", ("a row a person, term and chamber; the General Court's number and name; the seats the bills "
                  "printed; chamber from the list marked as that; no party; coverage against 400 and 24")


@check("naming", "a printed sponsor two numbers fit is settled only on the term's own official seat list, and otherwise "
       "stays as printed",
       needs=("past_roster", "past_sponsors", "text_sponsors"))
def _past_roster_settle(PR, PSP, T):
    """past_roster.settle, 13 November 2026. The owner's rule: "as accurate as possible and not guess if we
    aren't confident". "Rep. Torr of Strafford Dist. 6" and "Sen. Torr of Dist. 21" on one bill, with Ann Torr
    and Franklin Torr both among its sponsors, are told apart by the seat the Manual for the General Court
    gives each in THAT term (past_members.json holds one, later seat a number). A line goes to a candidate
    only if (1) each candidate's full name -- the General Court's first name and surname, an initial never
    enough -- joins exactly one person in the term's seat list, read without doubt; (2) exactly one
    candidate's seat there is the printed chamber and seat and every other's is known and different;
    (3) that number is of the printed chamber. Each shape below must stay as printed."""
    pm = {"1": {"name": "Torr, Ann", "chamber": "H"}, "2": {"name": "Torr, Franklin", "chamber": "S"},
          "3": {"name": "Torr, Franklin", "chamber": "H"},
          "4": {"name": "Hill, Douglas", "chamber": "H"}, "5": {"name": "Hill, Michael", "chamber": "H"},
          "6": {"name": "Hill, M.", "chamber": "H"}}
    people = PSP.People([], pm)
    term = "1989-1990"

    def row(name, county, district, line, check="clean"):
        return {"county": county, "district": district, "name": name, "town": "", "party": "", "votes": 1,
                "status": "elected", "district_check": check, "seats": 1, "edition": "1989", "line": line,
                "printed": name}

    def sen(name, district, line):
        return {"district": district, "name": name, "page_name": name.upper(), "town": "", "party": "",
                "votes": 1, "agreement": "exact", "status": "elected", "edition": "1989",
                "returns_line": line, "page_line": line + 1, "printed": name, "note": ""}

    def table(house, senate, measuring=False):
        return {"format": 1, "terms": {term: {"edition": "1989", "measuring_only": measuring,
                                              "house": house, "senate": senate}}}

    ann, frank = row("Ann M. Torr", "Strafford", "6", 108916), sen("Franklin G. Torr", "21", 94370)
    full = table([ann], [frank])
    rows = lambda *e: [{"employee": x, "sequence": i, "prime": i == 0, "withdrawn": False} for i, x in enumerate(e)]
    line = lambda s: T.split(s)[0]
    got = lambda s, rs, tb: PR.settle(line(s), rs, people, term, tb)

    # one candidate matches and the other's seat is known and differs -> settled, both ways round
    for printed, want in (("Sen. Torr of Dist. 21", "2"), ("Rep. Torr of Strafford Dist. 6", "1")):
        assert PR.place(line(printed), rows("1", "2"), people)[0] == PR.AMBIGUOUS
        st, emp, why = got(printed, rows("1", "2"), full)
        assert (st, emp) == (PR.SETTLED, want), f"{printed!r}: {st} {emp} {why}"
        assert "line 108916" in why and "line 94370" in why and "1989 edition" in why, why
    # the other candidate's seat unknown (no one of that name in the list) -> left
    st, emp, why = got("Sen. Torr of Dist. 21", rows("1", "2"), table([], [frank]))
    assert (st, emp) == (PR.AMBIGUOUS, None) and "not known" in why, (st, emp, why)
    # ... or only known by a row the OCR left in doubt (marks differ from seats) -> left
    st, emp, why = got("Sen. Torr of Dist. 21", rows("1", "2"),
                       table([row("Ann M. Torr", "Strafford", "6", 1, "marks differ from seats")], [frank]))
    assert st == PR.AMBIGUOUS and "not known" in why, (st, why)
    # both match the printed seat -> left
    two = table([row("Douglas E. Hill", "Cheshire", "14", 10), row("Michael Hill", "Cheshire", "14", 11)], [])
    st, emp, why = got("Rep. Hill of Cheshire Dist. 14", rows("4", "5"), two)
    assert (st, emp) == (PR.AMBIGUOUS, None) and "more than one" in why, (st, why)
    # while two Hills in two seats are told apart
    apart = table([row("Douglas E. Hill", "Cheshire", "14", 10), row("Michael Hill", "Merrimack", "14", 11)], [])
    assert got("Rep. Hill of Cheshire Dist. 14", rows("4", "5"), apart)[:2] == (PR.SETTLED, "4")
    assert got("Rep. Hill of Merrimack Dist. 14", rows("4", "5"), apart)[:2] == (PR.SETTLED, "5")
    # an initial only is not enough: the General Court's "M." Hill joins no one, so Douglas Hill's seat
    # matching the printed one does not settle a line the unknown M. Hill might be on
    st, emp, why = got("Rep. Hill of Cheshire Dist. 14", rows("4", "6"), apart)
    assert (st, emp) == (PR.AMBIGUOUS, None), (st, emp, why)
    #   ... and the list's own initial ("D. Hill") is no full name either
    ini = table([row("D. Hill", "Cheshire", "14", 10), row("Michael Hill", "Merrimack", "14", 11)], [])
    assert got("Rep. Hill of Merrimack Dist. 14", rows("4", "5"), ini)[0] == PR.AMBIGUOUS
    # the other chamber's number: Franklin Torr's House number on a Senate line is reported, not settled
    st, emp, why = got("Sen. Torr of Dist. 21", rows("3", "1"), full)
    assert (st, emp) == (PR.AMBIGUOUS, None) and "House" not in why and "H-chamber" in why, (st, emp, why)
    # two people of one full name in the term's list -> the join is not certain -> left
    dup = table([ann, row("Ann Torr", "Coos", "2", 5)], [frank])
    assert got("Sen. Torr of Dist. 21", rows("1", "2"), dup)[0] == PR.AMBIGUOUS
    # a printed seat nobody of the candidates holds -> left; a line with no seat -> left
    assert got("Rep. Torr of Strafford Dist. 9", rows("1", "2"), full)[0] == PR.AMBIGUOUS
    assert got("Rep. Torr", rows("1", "2"), full)[0] == PR.AMBIGUOUS
    # no table, or a table of 1999-2000 (measuring only) -> nothing settled
    assert got("Sen. Torr of Dist. 21", rows("1", "2"), None)[0] == PR.AMBIGUOUS
    assert got("Sen. Torr of Dist. 21", rows("1", "2"), table([ann], [frank], measuring=True))[0] == PR.AMBIGUOUS
    # and through the build: the table settles the line, the evidence travels with the record, and with no
    # table the line stays exactly as printed
    sat = T.Sat([])
    joined = {term: {"HB1": {"lsr": "", "rows": rows("1", "2")}}}
    lines = [(term, "HB1", "Rep. Torr of Strafford Dist. 6; Sen. Torr of Dist. 21")]
    on, tally, _ = T.build({}, sat, sponsor_record=(joined, people), lines=lines, seat_table=full)
    off, _t, _ = T.build({}, sat, sponsor_record=(joined, people), lines=lines, seat_table=None)
    assert [r["employee"] for r in on[term]["HB1"]] == ["1", "2"], on[term]["HB1"]
    assert all("settled_by" in r and r["matched"] == PR.MATCHED for r in on[term]["HB1"])
    assert not any(r.get("employee") for r in off[term]["HB1"]), off[term]["HB1"]
    assert tally["1989-1998 printed sponsors settled against the bill's own sponsor rows"] == 2
    return "ok", ("settled: one candidate's seat is the printed one and the other's is known and differs; left as "
                  "printed: the other's seat unknown or in doubt, both matching, an initial only, the other "
                  "chamber's number, a repeated full name, a seat nobody holds, a line with no seat, no table")


@check("data", "the Manual's seat table has the shape its builder writes, and its House returns are read as the "
       "builder reads them",
       needs=("build_manual_seats",))
def _manual_seats_table(B):
    """build_manual_seats.py, 13 November 2026. Fixture lines first, each a thing the OCR does: a full stop for
    a comma, a mark turned into another character, a seat count read as a letter, a district whose marks do not
    equal its seats (not clean, so no decision rests on it). Then the committed generated/manual_seats.json,
    where it is on this disk: six editions, each term with its House rows and the 24 districts of the Senate,
    every row with its edition and line, the mid-term caveat in the file, and nothing a county that is not
    one of the ten."""
    lines = ["BELKNAP COUNTY",
             "District No. 1 (Meredith)(2)",
             "*David M. Lawton, Meredith, r 1,329",
             "♦Thomas J. Boriso, Meredith, r 1 ,292",
             "Mary Warner, Center Harbor, d 687",
             "District No. 2 (Tilton)(1)",
             "William Joscelyn, Tilton, d 629",
             "Heber Feener, Tilton, ind&r 383",
             "CHESHIRE COUNTY",
             "District No. 1 (Alstead)(l)",
             "♦Jeffrey C. Miller. r. Walpole 1 ,382",
             "District No. 2 (Chesterfield)d)",
             "*Ann Pratt, Chesterfield, d 100"]
    rows, ds = B.parse_house(lines, "1989", 1, len(lines))
    by = {(d["county"], d["district"]): d for d in ds}
    assert by[("Belknap", "1")]["check"] == "clean" and by[("Cheshire", "1")]["check"] == "clean", by
    assert by[("Belknap", "2")]["check"] == "marks differ from seats", "a district with no mark read as clean"
    assert by[("Cheshire", "2")]["check"] == "seats unreadable", "a lone letter was read as a seat count"
    got = {(r["county"], r["district"], r["name"]): r for r in rows}
    assert set(got) == {("Belknap", "1", "David M. Lawton"), ("Belknap", "1", "Thomas J. Boriso"),
                        ("Cheshire", "1", "Jeffrey C. Miller"), ("Cheshire", "2", "Ann Pratt")}, sorted(got)
    miller = got[("Cheshire", "1", "Jeffrey C. Miller")]
    assert (miller["town"], miller["party"], miller["line"], miller["edition"]) == ("Walpole", "r", 11, "1989"), miller
    assert B.seats_of("District No. 13 (Derry)(ll)") == 11 and B.seats_of("District No. 1 (X)(l)") == 1 \
        and B.seats_of("District No. 1 (Barnstead)O)") is None and B.seats_of("District No. 1 (Y)0)") is None
    assert B.district_no("District No. 1 1 (Alexandria, Canaan)(3)") == "11" \
        and B.district_no("District No. I (Center Harbor)(l)") == "1"
    # the same name, by what a decision may rely on
    assert B.names_agree("Ann M. Torr", "Ann Torr") and not B.names_agree("A. Torr", "Ann Torr")
    p = Path("generated/manual_seats.json")
    if not p.exists():
        return "ok", "fixtures only: generated/manual_seats.json is not on this disk (src/parse/build_manual_seats.py --apply)"
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert doc["format"] == 1 and "start of a term" in doc["mid_term_changes_not_shown"], "the mid-term caveat is gone"
    assert sorted(doc["editions"]) == sorted(B.EDITIONS), sorted(doc["editions"])
    assert sorted(doc["terms"]) == sorted(t for t, _e in B.EDITIONS.values()), sorted(doc["terms"])
    need = {"county", "district", "name", "town", "party", "votes", "status", "district_check", "seats",
            "edition", "line", "printed"}
    for term, t in doc["terms"].items():
        assert t["measuring_only"] == (term in B.MEASURING_ONLY), term
        assert t["edition"] == B.EDITIONS_BY_TERM[term], term
        for r in t["house"]:
            assert need <= set(r), f"{term}: a House row lacks {sorted(need - set(r))}: {r}"
            assert r["county"] in B.COUNTIES and r["edition"] == t["edition"] and isinstance(r["line"], int), r
            assert r["status"] in ("elected", "unreadable", "mark garbled, count agrees"), r
        senate = {s["district"]: s for s in t["senate"]}
        assert sorted(senate, key=int) == [str(i) for i in range(1, 25)] and len(t["senate"]) == 24, \
            f"{term}: the Senate is not 24 districts once each"
        for s in t["senate"]:
            assert s["edition"] == t["edition"] and s["status"] in ("elected", "sources differ", "returns only", "unreadable"), s
        assert sum(1 for r in t["house"] if r["status"] == "elected") >= 300, f"{term}: far fewer than 400 House rows"
    assert doc["coverage"] == B.coverage(doc["terms"]), "the coverage table is not the table's own count"
    return "ok", (f"the OCR's full stop for a comma, a changed mark, a letter for a seat count and a district "
                  f"whose marks differ from its seats are each read as the builder reads them; the committed "
                  f"table has {len(doc['editions'])} editions, 24 Senate districts a term, edition and line on "
                  f"every row, and the mid-term caveat")


@check("build", "the House call of the roll is a second source: a name is placed on a number only where one of the "
       "term's sponsors fits it and the seat does not contradict",
       needs=("past_roll", "build_past_roster", "past_sponsors"))
def _past_roll_second_source(ROLL, BPR, PSP):
    """past_roll.py, 13 November 2026. The roll names every House seat, in the OCR's spelling. A name is
    placed on an employee number only where exactly one person who sponsored in that term has the roll's
    surname and first name (the same name or a short form, never a bare prefix) and their printed
    seats do not contradict the roll's. The name two sponsors fit, the one whose bills printed another
    district, a spelling the OCR damaged and a member who sponsored nothing are NOT placed -- a name found
    once on the whole list of members is counted and not used. Placed on a person with no row of the term
    (impossible by this rule, kept for the day it is relaxed) it would add a row from the roll alone; placed
    on one with a row it adds the volume and says whether a printed seat could be compared. No party."""
    pm = {"1": {"name": "Guay, Roland", "chamber": "H"}, "2": {"name": "Hale, Robert", "chamber": "H"},
          "3": {"name": "Hale, Rachel", "chamber": "H"}, "4": {"name": "Dube, Paul", "chamber": "H"},
          "5": {"name": "Lyman, L. Randy", "chamber": "H"}, "6": {"name": "Nonspon, Ann", "chamber": "H"}}
    people = PSP.People([], pm)
    seat = lambda c, d: [{"county": c, "district": d, "bills": 1}]
    rows = [{"term": "1997-1998", "chamber": "H", "person": e, "name": n, "seats": s}
            for e, n, s in (("1", "Roland Guay", seat("Coos", "6")), ("2", "Robert Hale", seat("Graf", "2")),
                            ("3", "Rachel Hale", []), ("4", "Paul Dube", seat("Hillsborough", "14")))]
    who = ROLL.pool(rows, people, "1997-1998")
    every = ROLL.everyone_of(people)
    en = lambda name, c, d: {"name": name, "county": c, "district": d}
    cases = [("Roland J. Guay", "Coos", "6", ("placed", "1")),
             ("Roland Guay", "Coos", "7", ("seat differs", "1")),     # his bills printed Coos 6
             ("Bob Hale", "Graf", "2", ("placed", "2")),              # Bob is a short form of Robert
             ("R. Hale", "Graf", "2", ("none", None)),                # an initial is no first name here
             ("Rober Hale", "Graf", "2", ("none", None)),             # a bare prefix is not Robert
             ("Paul Dubo", "Hillsborough", "14", ("none", None)),     # the OCR's spelling
             ("Ann Nonspon", "Coos", "1", ("list only", "6")),        # on the list, sponsored nothing
             ("Pat Nobody", "Coos", "1", ("none", None))]
    for name, c, d, want in cases:
        got = ROLL.place(en(name, c, d), who, every)
        assert got == want, f"{name!r} at {c} {d}: {got}, not {want}"
    assert ROLL.place(en("Rachel Hale", "Graf", "9"), who, every) == ("placed", "3"), \
        "a sponsor with no printed seat is placed on the name alone"
    # Merged into a table: a placed name adds the volume to a row of the term and says what it was checked against.
    got = {"journalofhouseof1997newh.csv": [(en("Roland J. Guay", "Coos", "6"), "placed", "1"),
                                            (en("Rachel Hale", "Graf", "9"), "placed", "3"),
                                            (en("Roland Guay", "Coos", "7"), "seat differs", "1"),
                                            (en("Paul Dubo", "Hillsborough", "14"), "none", None)]}
    full = BPR.rows_of({"1997-1998": {"HB1": {"lsr": "", "rows": [
        {"employee": e, "sequence": 0, "prime": False, "withdrawn": False} for e in "1234"]}}},
        {"1997-1998": {"HB1": [{"employee": "1", "matched": "General Court sponsor record", "chamber": "H",
                                "county": "Coos", "district": "6"}]}}, people, set(), terms=("1997-1998",))
    merged, clash, loose = BPR.add_roll(full, got, people, set())
    g = next(r for r in merged if r["person"] == "1")
    assert g["roll"] == [{"volume": 1997, "county": "Coos", "district": "6",
                          "seat_checked_against_a_printed_seat": True}], g
    r3 = next(r for r in merged if r["person"] == "3")
    assert r3["roll"][0]["seat_checked_against_a_printed_seat"] is False, r3
    assert len(clash) == 1 and clash[0]["gc_employee_number"] == "1" and len(loose) == 1, (clash, loose)
    assert not any("party" in r for r in merged), "a party before 1999"
    return "ok", ("placed on the term's one sponsor of that surname and first name (or short form), a seat "
                  "that contradicts, an OCR spelling, a bare prefix and a non-sponsor left unplaced")


@check("naming", "a sponsor row is a person or a committee: no heading, no seat on its own, no figure in a name",
       needs=("text_sponsors",))
def _sponsor_rows_are_people(text_sponsors):
    """The sponsor line is read as the pages type it, and they type it loosely. Each line
    below is one a saved page prints, and each produced a row that was not a person:
    1991 HCR 13's prime sponsor was "REFERRED TO"; "Rep. Putnam; Rock 15" made a sponsor
    called "Rock 15"; "Rep. McGough, Hill 18" one called "Hill 18 McGough"; "Sen.
    Francoeur, Dsit 14" one called "Dsit 14 Francoeur"; and 1999 HB 398's comma for a
    semicolon lost Rep. Ronald Nowe -- "Rep. M. Nowe" before him is Mary Lou Nowe, who
    later filed as Flayhan, and stays as printed. 2005 HB 64's "Rep. Rep. A. Tilton" made
    a sponsor called "Rep. A. Tilton", whom no roll call names; she is Rep. Anna Tilton. A
    committee that introduced a bill stays the committee. A line that names nobody is
    named from the General Court's sponsor record, marked as that."""
    T = text_sponsors
    import past_sponsors as PSP
    lines = {
        "Rep. Rep. A. Tilton, Ches 6; Rep. Foster, Hills 10":
            [("H", "A. Tilton", "Cheshire", "6"), ("H", "Foster", "Hillsborough", "10")],
        "Rep. M. Nowe, Rock 4; Rep. G. Katsakiores, Rock 13, Rep. R. Nowe, Rock 3; Rep. Rose, Ches 13":
            [("H", "M. Nowe", "Rockingham", "4"), ("H", "G. Katsakiores", "Rockingham", "13"),
             ("H", "R. Nowe", "Rockingham", "3"), ("H", "Rose", "Cheshire", "13")],
        "Rep. Putnam; Rock 15": [("H", "Putnam", "Rockingham", "15")],
        "Sen. Russman, Dist 19; Rep. Battles, Rock 18; Rock 18; Rep. Putnam, Rock 15":
            [("S", "Russman", "", "19"), ("H", "Battles", "Rockingham", "18"),
             ("H", "Putnam", "Rockingham", "15")],
        "Rep. McGough, Hill 18; Rep. Batula, Hills 18":
            [("H", "McGough", "Hillsborough", "18"), ("H", "Batula", "Hillsborough", "18")],
        "Sen. Francoeur, Dsit 14; Sen. Flanders, Dist 7": [("S", "Francoeur", "", "14"),
                                                           ("S", "Flanders", "", "7")],
        "Sen. Pignatelli, Dist 13; Sen. Wheeler, Dit 21": [("S", "Pignatelli", "", "13"),
                                                           ("S", "Wheeler", "", "21")],
        "Rep. J. Bradley; Carr 8, Rep. MacGillivray, Hills 21":
            [("H", "J. Bradley", "Carroll", "8"), ("H", "MacGillivray", "Hillsborough", "21")],
        "Sen. Hollingworth, Dist; 23": [("S", "Hollingworth", "", "23")],
        "Rep. Kidder of Merimack Dist. 2": [("H", "Kidder", "Merrimack", "2")],
        "Sen. Torr of Dist. 21; Rep. Torr Strafford Dist. 6":
            [("S", "Torr", "", "21"), ("H", "Torr", "Strafford", "6")],
        "Rep. Hall of Hillsborough, Dist. 16": [("H", "Hall", "Hillsborough", "16")],
        "Rep. Dickinson. Carr 4; Sen. Clegg. Dist 14; Rep. Mock Carr 3; Rep. D. Welch Rock 18":
            [("H", "Dickinson", "Carroll", "4"), ("S", "Clegg", "", "14"),
             ("H", "Mock", "Carroll", "3"), ("H", "D. Welch", "Rockingham", "18")],
        "Rep. Syracusa, Rock 33; Rep. Hunt, Chest 10; Rep. Burnham,Ches 8":
            [("H", "Syracusa", "Rockingham", "33"), ("H", "Hunt", "Cheshire", "10"),
             ("H", "Burnham", "Cheshire", "8")],
        "Rep. Taylor, Staf 11; Rep. Alger, Graft 9; Rep. Giordano, Rcok 26; Rep. Levesque, Straff. 4":
            [("H", "Taylor", "Strafford", "11"), ("H", "Alger", "Grafton", "9"),
             ("H", "Giordano", "Rockingham", "26"), ("H", "Levesque", "Strafford", "4")],
        "Sen. Pignatelli, Dist 13; Sen. Squires, Sen. Larsen, Dist. 15; Dist 12":
            [("S", "Pignatelli", "", "13"), ("S", "Squires", "", "12"), ("S", "Larsen", "", "15")],
        "Rep. J. Tilton, Rep. Shurtleff, Merr 10; Merr 6":
            [("H", "J. Tilton", "Merrimack", "6"), ("H", "Shurtleff", "Merrimack", "10")],
        # "Gray" is one letter from "Graf", and a first draft of the seat reader took Sen.
        # James Gray for a seat printed on its own and dropped him from 305 sponsor lines.
        "Sen. Gray, Dist 6; Sen. Murphy, Dist 16": [("S", "Gray", "", "6"), ("S", "Murphy", "", "16")],
        "Rep. Vaillancourt, Hills 44; Rep; Foster, Hills 10":
            [("H", "Vaillancourt", "Hillsborough", "44"), ("H", "Foster", "Hillsborough", "10")],
        "REFERRED TO": [],
        "Judiciary Committee": [("", "Judiciary Committee", "", "")],
    }
    seatish = re.compile(r"^(?:[A-Za-z]+\.?\s*)?\d+$|^(?:dist|district|dsit|dit)$", re.I)
    for line, want in lines.items():
        got = [(p["chamber"], " ".join(p["words"]), p["county"], p["district"])
               for p in T.split(line)]
        assert got == want, f"{line!r} was read as {got}"
        for _c, name, _co, _d in got:
            assert not re.search(r"\d", name) and "REFERRED" not in name.upper() \
                and not seatish.match(name) and not SPONSOR_HONORIFIC.search(name), (
                f"{line!r} made a sponsor called {name!r}")
    # The line that names nobody: its sponsors come from the record, marked so.
    joined = {"1991-1992": {"HCR13": {"lsr": "1991-1217", "rows": [
        {"employee": "373290", "sequence": 1, "prime": True, "withdrawn": False}]}}}
    people = PSP.People([], {"373290": {"name": "Hill, Michael", "chamber": "H"}})
    got, _t, _ = T.build({}, T.Sat([]), sponsor_record=(joined, people),
                         lines=[("1991-1992", "HCR13", "REFERRED TO"),
                                ("1999-2000", "HB1500", "Judiciary Committee")])
    hcr = got["1991-1992"]["HCR13"]
    assert [(r["name"], r["prime"], r["member_id"], r["source"], r.get("unprinted")) for r in hcr] \
        == [("Michael Hill", True, "", PSP.SOURCE, True)], f"1991 HCR 13 names {hcr}"
    com = got["1999-2000"]["HB1500"]
    assert [r["name"] for r in com] == ["Judiciary Committee"], (
        f"1999 HB 1500, introduced by the Judiciary Committee, names {[r['name'] for r in com]}")
    return "ok", (f"{len(lines)} printed lines, each a person or a committee; a line naming "
                  "nobody named from the record and marked so")


@check("frontend", "the Legislators tab's Presiding Officers are their chips alone, with no "
                   "sentence under them, in English and in Spanish", needs=("officials_tabs",))
def _presiding_chips_alone(OT):
    """The owner's walk of 7 November 2026: the sentence under the Presiding
    Officers -- "The Speaker presides over the House, and the Deputy Speaker
    sometimes in the Speaker's place; the Senate President presides over the
    Senate." -- goes, in both languages. Each chip's role says the office.
    Drawn for a Speaker and a Senate President serving on the day: the
    section holds its heading and the chips, and nothing else; its catalog
    entry is gone with it."""
    legs = [{"id": "35", "name": "Carson, Sharon", "chamber": "S", "party": "R",
             "slug": "sharon-carson-sd-14", "display_full": "Sen. Sharon Carson (R - SD14)"},
            {"id": "9", "name": "Packard, Sherman", "chamber": "H", "party": "R",
             "slug": "sherman-packard-rock-16", "display_full": "Rep. Sherman Packard (R - Rock 16)"}]
    officers = [{"office": "President of the Senate", "id": "35", "b": "S", "from": "2024-12-04"},
                {"office": "Speaker of the House", "id": "9", "b": "H", "from": "2024-12-04"}]
    bad = []
    for lang in ("en", "es"):
        html = OT.presiding(officers, legs, "2026-11-08", lang)
        body = re.fullmatch(r'<section class="ofpres" aria-labelledby="of-presiding"><h3 '
                            r'id="of-presiding">[^<]+</h3><div class="ofchips">(.*)</div></section>',
                            html, re.S)
        if not body or body.group(1).count('class="mchip') != 2:
            bad.append(f"in {lang}, the Presiding Officers are {html[:300]!r}: their heading and "
                       "two chips, and nothing under them")
        if re.search(r"\bpresides?\b", re.sub(r"<[^>]+>", "", html), re.I):
            bad.append(f"in {lang}, a sentence about who presides is back beside the chips")
    cat = json.loads(_source("src/pages/lang/es.json"))["strings"]
    if "off.presiding_why" in cat:
        bad.append("es.json still carries off.presiding_why, the sentence that went")
    assert not bad, "\n  ".join(bad)
    return "ok", "the Speaker and the Senate President as chips, with no sentence under them, in both languages"


def _officials_read(P, pdf):
    """(every office the directory lists, as (town, name, phone, e-mail,
    position) in its own order; the rows restream() changed; whether an
    earlier run's parse answered).

    THE PARSE IS KEPT BETWEEN RUNS (2 October 2026). pdfplumber takes ten
    seconds over the directory's 31 pages to give the answer it gave the run
    before, and reading only the four rows' pages would have dropped what the
    check holds the whole document to: exactly four rows re-read, and no half
    address anywhere. So the answer is kept, in the system temp directory --
    not in the project, where logs/ is sent to the bucket -- under a digest
    of everything it depends on: the PDF's bytes, parse_officials.py's bytes
    (its stamp is among them, and so is an edit that forgot the stamp), and
    the versions of pdfplumber, of pdfminer underneath it and of Python.
    Change any of them and the directory is read again. A kept answer that
    will not load, or is not this shape, is not used.
    """
    import hashlib
    import pdfplumber
    try:
        import pdfminer
        miner = str(getattr(pdfminer, "__version__", ""))
    except Exception:
        miner = ""
    h = hashlib.sha256()
    for part in (pdf.read_bytes(), Path(P.__file__).read_bytes(),
                 f"pdfplumber {pdfplumber.__version__}, pdfminer {miner}, "
                 f"python {sys.version.split()[0]}".encode("utf-8")):
        h.update(hashlib.sha256(part).digest())
    key = h.hexdigest()
    kept = Path(tempfile.gettempdir()) / "granite-record-preflight" / "officials.json"
    try:
        doc = json.loads(kept.read_text(encoding="utf-8"))
        if doc["key"] == key and all(len(r) == 5 and all(isinstance(c, str) for c in r)
                                     for r in doc["rows"]) \
                and all(isinstance(s, str) for s in doc["restreamed"]):
            return [tuple(r) for r in doc["rows"]], list(doc["restreamed"]), True
    except (OSError, ValueError, KeyError, TypeError):
        pass
    towns, _notes, _raw, restreamed = P.read(pdf)
    rows = [(t, o["name"], o["phone"], o["email"], o["position"])
            for t, r in towns.items() for o in r["officials"]]
    try:
        kept.parent.mkdir(parents=True, exist_ok=True)
        part = kept.with_name(f"{kept.name}.{os.getpid()}")
        part.write_text(json.dumps({"key": key, "rows": rows, "restreamed": restreamed}),
                        encoding="utf-8")
        os.replace(part, kept)
    except OSError:
        pass                    # not kept: the next run reads the directory again
    return rows, restreamed, False


@check("files", "the officials directory reads as printed where a cell runs into the next")
def _officials_restream():
    """Four rows of NHDOT's directory print text wider than its cell.

    pdfplumber threaded the overflow into the next column a character at a
    time, and all four were published: Grace Ruelle's address as
    "t g1ruelle@eastkingstonnh.gov", Sutton's as "t.t o4wnadmin@sutton-nh.org",
    Hooksett's councillor as "yR)andall Lapierre" and Somersworth's deputy
    mayor as "MDaayvoer Witham". parse_officials.restream reads such a row in
    the PDF's own order. This reads the directory itself -- it is in git --
    and holds the four rows to what the PDF prints.
    """
    pdf = Path("records/sources/nh-municipal-officials-2025-09-01.pdf")
    if not pdf.exists():
        return "skip", "the NHDOT directory is not in records/sources/"
    try:
        import pdfplumber                                    # noqa: F401
    except Exception:
        return "skip", "pdfplumber is not installed"
    P = imp("parse_officials")
    if P is None:
        return "skip", "parse_officials.py does not import"
    listed, restreamed, kept = _officials_read(P, pdf)
    rows = {(t, name): {"phone": phone, "email": email, "position": pos}
            for t, name, phone, email, pos in listed}
    want = {("East Kingston", "Grace Ruelle"): ("603-642-8406 ext 1", "gruelle@eastkingstonnh.gov",
                                                "Town Administrator"),
            ("Sutton", "Julia Jones"): ("603-927-2400 ext. 4", "townadmin@sutton-nh.org",
                                        "Town Administrator"),
            ("Hooksett", "Randall Lapierre"): ("603-341-8311", "rlapierre@hooksett.org",
                                               "City Councilor, District 6 (Secretary)"),
            ("Somersworth", "Dave Witham"): ("", "dwitham@somersworthnh.gov",
                                             "Town Councilor, At-Large, Deputy Mayor")}
    bad = []
    for k, (phone, email, pos) in want.items():
        o = rows.get(k)
        if not o or (o["phone"], o["email"], o["position"]) != (phone, email, pos):
            bad.append(f"{k[0]}'s {k[1]} reads {o and (o['phone'], o['email'], o['position'])}")
    if len(restreamed) != len(want):
        bad.append(f"{len(restreamed)} rows re-read, not {len(want)}: {restreamed}")
    half = [f"{t}: {o['email']!r}" for (t, _), o in rows.items()
            if "@" in o["email"] and not P.EMAIL_OK.match(o["email"])]
    if half:
        bad.append("half an address and half something else: " + ", ".join(half))
    assert not bad, "\n  ".join(bad)
    return "ok", ("four overflowing rows read as printed, and no half-address left"
                  + (" (the parse kept from an earlier run of this parser on this PDF)"
                     if kept else ""))


@check("data", "every town page links real addresses and dialable numbers, and names no second clerk")
def _town_pages_built():
    """The built town pages, held to what the builder now writes.

    Before 23 September: 175 mailto links that were not addresses, on 132
    pages; 28 dial links carrying an extension's digits into the number; 30
    pages naming two clerks and 6 labelling an administrator "Town
    Administrator/ Town Clerk".

    A data check, not a files one, on purpose: site/ is build output, and
    nightly.py gates itself on preflight --code. As a files check it failed
    --code on every page built before this code, which stopped the nightly
    before build_all -- the one step that would have rebuilt the pages. The
    builder's own behaviour is held under --code by the build checks above.
    """
    pages = sorted(Path("site/town").glob("*.html"))
    if not pages:
        return "skip", "site/town is not built"
    P = imp("parse_officials")
    if P is None:
        return "skip", "parse_officials.py does not import"
    import html as _html
    bad = []
    for f in pages:
        h = f.read_text(encoding="utf-8")
        for m in re.findall(r'href="mailto:([^"]*)"', h):
            if not P.EMAIL_OK.match(_html.unescape(m)):
                bad.append(f"{f.name}: mailto {m!r}")
        for t in re.findall(r'href="tel:([^"]*)"', h):
            if not re.fullmatch(r"\+1\d{10}(?:;ext=\d+)?", t):
                bad.append(f"{f.name}: tel {t!r}")
        seats = re.findall(r'<span class="offseat">([^<]*)</span>', h)
        if seats.count("Town or city clerk") > 1:
            bad.append(f"{f.name}: {seats.count('Town or city clerk')} clerk rows")
        for s in seats:
            if s != "Town or city clerk" and re.search(r"\b(?:town|city) clerk\b", s, re.I):
                bad.append(f"{f.name}: NHDOT's {s!r} beside the Secretary of State's clerk")
    assert not bad, (
        f"{len(bad)} problems on the built town pages -- rebuild them with "
        "build_town_pages.py:\n  " + "\n  ".join(bad[:12]))
    return "ok", (f"{len(pages)} pages, every mailto an address, every tel "
                  "dialable, no second clerk")


def _elect_tab_case():
    """A members-elect file with one of each thing the Members-Elect tab has
    to say, and the members the file links to (the owner's walks of 7 and 8
    November 2026): a sitting senator re-elected to her seat whose roster
    surname is two words (Perkins Kwoka, after Lane, as the roster lists
    her), a sitting representative elected to the Senate (Creighton, NEW
    CHAMBER), a former representative elected to the Senate (Lane, NEW
    CHAMBER), a former senator returning (Chandley, RETURNING), a sitting
    representative elected to another House district (Burt, INCUMBENT),
    the new, a winner of two nominations, a winner with no party printed, a
    "Jr." (Lawrence, after Kline), a race with two seats not final on a
    recount, a seat with nobody on file, a county of two districts whose
    lower one's member sorts last by name (Young, Rockingham 6, before Foote
    and Trow of 13 by county), and the sitting senators whose roster county
    the Legislators tab lists each Senate district under (district 9 has
    none, so "Not on file")."""
    rep = lambda n, p, **k: {"n": n, "p": p, "k": "new", **k}  # noqa: E731
    elect = {"election": "2026-11-03", "takes_office": "2026-12-02", "term": "2027-2028",
             "sources": ["https://www.sos.nh.gov/x"], "races": {
                 "S|8": {"seats": 1, "not_final": 0, "held": 0, "elected": [
                     {"n": "Jim Creighton", "p": "R", "k": "sitting", "id": "9917",
                      "s": "james-creighton-hills-30"}]},
                 "S|9": {"seats": 1, "not_final": 0, "held": 0, "elected": [
                     {"n": "Rachel Lane", "p": "D", "k": "former", "id": "2003",
                      "s": "rachel-lane-hills-1"}]},
                 "S|11": {"seats": 1, "not_final": 0, "held": 0, "elected": [
                     {"n": "Shannon E. Chandley", "p": "D", "k": "former", "id": "2002",
                      "s": "shannon-chandley-sd-11"}]},
                 "S|21": {"seats": 1, "not_final": 0, "held": 0, "elected": [
                     {"n": "Rebecca Perkins Kwoka", "p": "D", "k": "sitting", "id": "1001",
                      "s": "rebecca-perkins-kwoka-sd-21", "own": True}]},
                 "H|Belknap|6": {"seats": 4, "not_final": 0, "held": 0, "elected": [
                     rep("Pat Both", "R/D"), rep("Lee Nobody", ""),
                     rep("William Lawrence, Jr.", "D"), rep("Karen Kline", "D")]},
                 "H|Coos|1": {"seats": 2, "not_final": 0, "held": 0, "elected": [
                     {"n": "Ann Burt", "p": "R", "k": "sitting", "id": "3003", "s": "ann-burt-coos-3"}]},
                 "H|Rockingham|6": {"seats": 1, "not_final": 0, "held": 0, "elected": [rep("Zoe Young", "D")]},
                 "H|Rockingham|13": {"seats": 4, "not_final": 2, "held": 0, "recount": True,
                                     "elected": [rep("Kristine Trow", "D"),
                                                 {"n": "Charles Foote", "p": "R", "k": "sitting",
                                                  "id": "10691", "s": "charles-foote-rock-13",
                                                  "own": True}]}}}
    people = [  # the roster's rows, and former.json's (former: true)
        {"id": "1001", "name": "Perkins Kwoka, Rebecca", "chamber": "S", "district": "21",
         "county": "Rockingham"},
        {"id": "9917", "name": "Creighton, James", "chamber": "H", "district": "30",
         "county": "Hillsborough"},
        {"id": "10691", "name": "Foote, Charles", "chamber": "H", "district": "13", "county": "Rockingham"},
        {"id": "3003", "name": "Burt, Ann", "chamber": "H", "district": "3", "county": "Coos"},
        {"id": "5008", "name": "Ward, Ruth", "chamber": "S", "district": "8", "county": "Sullivan"},
        {"id": "5011", "name": "Keeper, Kim", "chamber": "S", "district": "11", "county": "Hillsborough"},
        {"id": "2002", "name": "Chandley, Shannon", "chamber": "S", "district": "11",
         "county": "Hillsborough", "former": True,
         "served": {"terms": ["2017-2018", "2019-2020", "2023-2024"]}},
        {"id": "2003", "name": "Lane, Rachel", "chamber": "H", "district": "1", "county": "Strafford",
         "former": True, "served": {"terms": ["2021-2022"]}}]
    return elect, people


@check("frontend", "the Members-Elect tab lists its people as the Legislators tab lists its "
                   "members -- by last name and by county, both chambers, each the Legislators "
                   "tab's chip with its word beside it -- under the seats each party won and the "
                   "seats not final, in English and in Spanish", needs=("officials_tabs",))
def _elect_tab_like_legislators(OT):
    """The owner's walks of 7 and 8 November 2026, for this tab.

    THE CHIP. Each member-elect is the Legislators tab's chip, the one
    component, with a title and a district: "Rep.-elect Kristine Trow (D -
    Rock 13)", "Sen.-elect Jim Creighton (R - SD8)" (the owner, walk of dry
    run 8: the quotation marks inside the chip). Linked only where the file links them; the
    cross-nominated on the neutral chip with both letters, and no letter
    where none was printed; no contact detail. Beside it and outside it,
    one word for who they are, build_members_elect.elect_status's (the
    owner, 12 November 2026): INCUMBENT (sitting in the chamber), RETURNING
    (served before and not serving now), NEW CHAMBER (their latest service
    the other chamber), NEW.

    THE TWO VIEWS, as the Legislators tab's (By district went on the walk of
    8 November): by last name, each chamber apart under its count and a
    column for each party, largest first, A to Z by surname -- the roster's
    own surname for a member the file links, so Perkins Kwoka is under P,
    and a suffix aside, so Lawrence, Jr. is under L; and by county, both
    chambers, each county shut until asked, A to Z, its members by district
    and then by name, its results not final counted in its summary and
    named inside it. The Senate's districts are under the county the
    Legislators tab lists each under -- the roster's county for the senator
    who holds it -- and "Not on file" last where nobody does. The view by
    name says how many seats are not final and where they are named. The
    chambers' headings carry the addresses the tab's chambers had:
    #of-elect-* in By last name, and By district's #of-eld-* in By county.

    THE SEATS AT THE TOP: each chamber's members-elect by party, the
    cross-nominated by their letters, the seats not final and the seats with
    nobody on file apart -- a bar, and one short line under it for a phone;
    then the seats not final, listed in a fold.

    And the strip's script (build_pages.SEATING_JS) wires this tab's strip
    as it does the roster's, each showing its own panes and no other's, and
    opens the view holding what the address names; run in node where it is
    installed. Each strip is written hidden and shown by the script, so a
    page read without it has its views under their headings and no buttons
    that do nothing. And the Spanish: no word of the tab in English, in any
    case, in its text or in what it says only to a screen reader or on
    hover (aria-label, title)."""
    import html as _h
    import shutil as _sh
    elect, people = _elect_tab_case()
    bad = []
    page = OT.members_elect(elect, "2026-11-20", "en", people)
    plain = lambda s: re.sub(r"\s+", " ", _h.unescape(re.sub(  # noqa: E731
        r"<[^>]+>", " ", re.sub(r"<script>.*?</script>", " ", s, flags=re.S)))).strip()
    want = {  # who -> (the chip's class, linked, tag, word)
        "Rep.-elect Kristine Trow": ("p-D", None, "D - Rock 13", "New"),
        "Rep.-elect Charles Foote": ("p-R", "charles-foote-rock-13", "R - Rock 13", "Incumbent"),
        "Sen.-elect Jim Creighton": ("p-R", "james-creighton-hills-30", "R - SD8", "New chamber"),
        "Sen.-elect Rachel Lane": ("p-D", "rachel-lane-hills-1", "D - SD9", "New chamber"),
        "Sen.-elect Shannon E. Chandley": ("p-D", "shannon-chandley-sd-11", "D - SD11", "Returning"),
        "Sen.-elect Rebecca Perkins Kwoka": ("p-D", "rebecca-perkins-kwoka-sd-21", "D - SD21",
                                             "Incumbent"),
        "Rep.-elect Ann Burt": ("p-R", "ann-burt-coos-3", "R - Coos 1", "Incumbent"),
        "Rep.-elect Pat Both": ("p-X", None, "R/D - Belk 6", "New"),
        "Rep.-elect Lee Nobody": ("p-X", None, "Belk 6", "New"),
    }
    for who, (cls, slug, tag, kind) in want.items():
        inner = (f'<a href="legislator/{slug}">{_h.escape(who)} <span class="mtag">({tag})</span></a>'
                 if slug else f'{_h.escape(who)} <span class="mtag">({tag})</span>')
        # The chip is the Legislators tab's, nothing inside it but the name
        # and tag; the word is beside it, outside it.
        drawn = (f'<span class="mchip {cls}" translate="no">{inner}</span>'
                 f' <span class="elkind" translate="yes">{kind}</span>')
        if page.count(drawn) != 2:
            bad.append(f"{who} is drawn {page.count(drawn)} times as {drawn!r}: once in each view")
    if "<i " in page:
        bad.append("a word is drawn inside a member-elect's chip")
    # Where the rows cannot say who someone is -- a sitting or former member
    # with no row, or none for their id, or a kind the file does not use --
    # no word: the walk asked to say so rather than guess.
    rows_by_id = {str(p["id"]): p for p in people}
    for e in ({"k": "sitting", "id": "4040"}, {"k": "former", "id": "4040"}, {"k": "sitting"},
              {"k": "returning", "id": "1001"}):
        if OT.elect_kind(e, "H|Coos|1", rows_by_id) or OT.elect_word(e, "H|Coos|1", rows_by_id):
            bad.append(f"a member-elect the rows cannot place gets a word: {e}")
    links = re.findall(r'<a href="legislator/([^"]+)"', page)
    if sorted(set(links)) != sorted(s for _c, s, _t, _k in want.values() if s) or len(links) != 12:
        bad.append(f"the tab links {sorted(set(links))} ({len(links)}): only the six the file "
                   "links, once in each view")
    if re.search(r"mailto:|tel:|@", page):
        bad.append("a contact detail is on the Members-Elect tab")
    # Written hidden, for the strip's script to show (without it, the three
    # views under their headings and no buttons that do nothing).
    strip = re.search(r'<div class="rtabs" role="tablist" aria-label="([^"]+)" hidden>(.*?)</div>',
                      page, re.S)
    tabs = re.findall(r'id="(tab-[a-z]+)" data-pane="(pane-[a-z]+)"\s+aria-controls="\2" '
                      r'aria-selected="(true|false)">([^<]+)<', strip.group(2) if strip else "")
    if [(t, p, s, w) for t, p, s, w in tabs] != [
            ("tab-elast", "pane-elast", "true", "By last name"),
            ("tab-ecounty", "pane-ecounty", "false", "By county")]:
        bad.append(f"the views' strip is {tabs}")
    at = {p: page.find(f'<div class="rpane" id="{p}" role="tabpanel" aria-labelledby="tab-{p[5:]}">')
          for p in ("pane-elast", "pane-ecounty")}
    if -1 in at.values() or sorted(at.values()) != list(at.values()) or "edist" in page:
        bad.append(f"the two panes are not there in order, or By district is still drawn: {at}")
        return "FAIL", "; ".join(bad)
    last, county = page[at["pane-elast"]:at["pane-ecounty"]], page[at["pane-ecounty"]:]
    # Each view opens at the level of the tab's own headings, so a reader
    # moving by heading in either meets its chambers as the tab's parts, not
    # as parts of "Who won the seats" (the review of 8 November).
    firsts = [(re.search(r"<h([1-6])\b", v) or [None, None])[1] for v in (last, county)]
    if firsts != ["2", "2"] or "<h4" in page:
        bad.append(f"the views' first headings are h{firsts}")
    # The chips' parts wrap inside the chip in these lists; the word beside
    # it is drawn as a chip's role is; and a strip written hidden stays
    # hidden until its script shows it (app.css).
    css = _source("src/pages/app.css")
    if ":where(body.pg) .elroll .mchip{flex-wrap:wrap" not in css \
            or ":where(body.pg) .rtabs[hidden]{display:none}" not in css \
            or not re.search(r":where\(body\.pg\) \.elkind\{[^}]*text-transform:uppercase", css) \
            or not all(re.search(r":where\(body\.pg\) " + re.escape(sel) + r"\{grid-template-columns:"
                                 r"repeat\(auto-(?:fit|fill),minmax\(min\(100%,34rem\),1fr\)\)\}", css)
                       for sel in (".elroster .partycols", ".grid.elroll")):
        bad.append("app.css does not let a member-elect's chip wrap its parts, draw the word "
                   "beside it in columns wide enough for both, or keep a hidden strip hidden")
    # By last name.
    cols = re.findall(r'<section class="pcol"><h3>([^<]+)</h3>(?:<p class="note">[^<]*</p>)?<ol class="seatlist rlist elroll">(.*?)</ol>',
                      last, re.S)
    got = [(_h.unescape(h), re.findall(r'translate="no">(?:<a [^>]+>)?(?:Rep|Sen)\.-elect ([^<]+?) <', b))
           for h, b in cols]
    if got != [("Democrats — 3", ["Shannon E. Chandley", "Rachel Lane", "Rebecca Perkins Kwoka"]),
               ("Republican — 1", ["Jim Creighton"]),
               ("Democrats — 4", ["Karen Kline", "William Lawrence, Jr.", "Kristine Trow", "Zoe Young"]),
               ("Republicans — 2", ["Ann Burt", "Charles Foote"]),
               ("More than one party — 1", ["Pat Both"]),
               ("Party not on file — 1", ["Lee Nobody"])]:
        bad.append(f"by last name, the columns are {got}")
    if not (re.search(r'<h2 id="of-elect-senate">Senate &mdash; 4</h2>', last)
            and re.search(r'<h2 id="of-elect-house">House &mdash; 8</h2><p class="elnf"><b>Result not '
                          r'final</b> for 2 seats in one district &mdash; a recount was requested\. '
                          r'Who won the seats lists them, and By county\.</p>', last)):
        bad.append("by last name, the chambers are not headed with their counts and the "
                   "addresses #of-elect-senate and #of-elect-house, or the House does not say its "
                   "seats not final")
    # By county: both chambers by county, under By district's old addresses.
    sen = county[:county.find('id="of-eld-house"')]
    if not re.search(r'<h2 id="of-eld-senate">Senate &mdash; 4</h2><details class="cgrp">', county) \
            or not re.search(r'<h2 id="of-eld-house">House &mdash; 8</h2><details class="cgrp">', county):
        bad.append("by county, the chambers are not headed with their counts and By district's "
                   "addresses #of-eld-senate and #of-eld-house")
    summary = (r'<details class="cgrp"><summary><span>([^<]+)</span><span class="ccount">(\d+)</span>'
               r'((?:<span class="ccnf">[^<]+</span>)?)<span class="caret">')
    senate_by = [(c, n, plain(f), re.findall(r'Sen\.-elect ([^<]+?) <', g)) for (c, n, f), g in zip(
        re.findall(summary, sen), re.split(r'<details class="cgrp">', sen)[1:])]
    if senate_by != [("Hillsborough", "1", "", ["Shannon E. Chandley"]),
                     ("Rockingham", "1", "", ["Rebecca Perkins Kwoka"]),
                     ("Sullivan", "1", "", ["Jim Creighton"]),
                     ("Not on file", "1", "", ["Rachel Lane"])]:
        bad.append(f"by county, the Senate is {senate_by}: each district under its sitting "
                   "senator's county, A to Z, and one nobody holds last under Not on file")
    sums = [(c, n, plain(f)) for c, n, f in re.findall(summary, county[len(sen):])]
    if sums != [("Belknap", "4", ""), ("Coos", "1", ""), ("Rockingham", "3", "2 not final")]:
        bad.append(f"by county, the House's counties are {sums}")
    # By district and then by name: Young (6) before Foote and Trow (13).
    house_by = county[len(sen):]
    rock = house_by[house_by.find("<span>Rockingham</span>"):]
    if not re.search(r'</div><p class="elnf"><b>Result not final</b> in District 13 \(2 seats\) '
                     r'&mdash; a recount was requested</p></details>', rock) or re.findall(
            r'(?:Rep|Sen)\.-elect ([^<]+?) <', rock) != ["Zoe Young", "Charles Foote", "Kristine Trow"]:
        bad.append("by county, Rockingham does not list Young (6), then Foote and Trow (13), and "
                   "name District 13's two seats not final")
    # The seats at the top, and under them the seats not final, listed: the
    # walk of 8 November took By district, where each district said it.
    top = page[:page.find('<section class="roster')]
    if not top.startswith('<div class="elpane" data-elect') or top.find('<p class="ofwhy">') > top.find(
            '<div class="comp-wrap comp-top"><h2>Who won the seats</h2>') or "comp-top" not in top:
        bad.append("the seats each party won are not between the tab's sentence and its lists")
    if '<details class="vac elnfl"><summary>2 seats not final, in one district</summary><p class="note" ' \
       'style="margin-top:8px">A recount was requested.</p><div class="grid"><div class="mem">' \
       'Rockingham District 13 — 2 seats</div></div></details></div>' not in top:
        bad.append("under Who won the seats, the seats not final are not listed: Rockingham "
                   "District 13, 2 seats, a recount requested")
    # Each chamber's phone line is its block's last part, under its bar.
    blocks = re.findall(r'<div class="comp"><div class="compline">.*?<div class="pbar2">.*?</div>'
                        r'<div class="plegend">.*?</div>(?:<p class="statemeta"[^>]*>.*?</p>)?'
                        r'<p class="compshort">.*?</p></div>', top, re.S)
    if len(blocks) != 2:
        bad.append(f"{len(blocks)} of the two chambers' blocks end in their phone line, under the bar")
    short = [plain(re.sub(r'<span class="sr">[^<]*</span>', "", s))
             for s in re.findall(r'<p class="compshort">(.*?)</p>', top)]
    if short != ["Senate 3 D · 1 R",
                 "House 4 D · 2 R · 1 R/D · 1 party not on file · 2 not final · 1 with no one on file"]:
        bad.append(f"the phone's lines are {short}")
    if re.findall(r'<p class="compshort">.*?</p>', top) and not re.search(
            r'3 <span aria-hidden="true">D</span><span class="sr">Democrats</span>', top):
        bad.append("a phone line's party letter does not carry the party's name for a screen reader")
    # The kinds counted, a line a chamber, from the chips' own classification
    # (the walk of dry run 8), and the sentence under "More than one party".
    kinds = [plain(k) for k in re.findall(r"<p class=\"elkinds\">(.*?)</p>", top)]
    if kinds != ["Senate 1 returning · 1 incumbent · 2 new chamber", "House 2 incumbent · 6 new"] \
            or "new district" in page.lower():
        bad.append(f"the kinds counted under Who won the seats are {kinds}, or the word new district is drawn")
    if "party labels, as the Secretary of State’s results print them" not in plain(last):
        bad.append("the cross-nominated group does not say why it is one")
    house = top[top.rfind('<div class="comp">'):top.find('<details class="vac elnfl">')]
    segs = re.findall(r'<span class="pseg (seg-[A-Z]+)" style="width:([\d.]+)%" title="([^"]+)"', house)
    if [(c, round(float(w)), _h.unescape(t)) for c, w, t in segs] != [
            ("seg-D", 36, "Democrats: 4"), ("seg-R", 18, "Republicans: 2"), ("seg-X", 9, "R/D: 1"),
            ("seg-X", 9, "Party not on file: 1"), ("seg-NF", 18, "Not final: 2"),
            ("seg-V", 9, "No one on file: 1")] or \
            "8 of 11 seats elected, 2 not final" not in house:
        bad.append(f"the House's bar is {segs}")
    # In Spanish, none of the tab's own words in English, in any case, in its
    # text or in what it says only to a screen reader or on hover (aria-label,
    # title).
    es_page = OT.members_elect(elect, "2026-11-20", "es", people)
    es = plain(es_page) + " " + " ".join(_h.unescape(v) for v in re.findall(
        r'\b(?:title|aria-label)="([^"]*)"', es_page))
    for word in ("Rep.-elect", "Sen.-elect", "Incumbent", "Returning", "Prior service", "Search", "Status",
                 "New district", "New chamber", "New",
                 "By last name", "By county", "Who won the seats", "not final", "seats elected",
                 "More than one party", "no one on file", "lists them", "members-elect",
                 "Democrats", "Republicans", "District", "Party not on file", "Not on file",
                 "How to arrange", "A recount was requested"):
        if re.search(r"(?<![\w.-])" + re.escape(word) + r"(?![\w-])", es, re.I):
            bad.append(f"the Spanish tab says {word!r}")
    # The strip's script, on two strips at once.
    node = _sh.which("node")
    if node:
        import build_pages as BP
        js = re.search(r"<script>(.*)</script>", BP.SEATING_JS, re.S).group(1)
        def harness(hash_):
            return r"""
var panes={},bars=[],scrolled=null,listeners={};
function el(id){return panes[id]||(panes[id]={id:id,hidden:false,
  contains:function(x){return !!x&&(x===this||x.pane===id);}});}
function bar(ids){var tabs=ids.map(function(p){var h={};return {dataset:{pane:p},attrs:{},
  setAttribute:function(k,v){this.attrs[k]=v;},addEventListener:function(k,f){h[k]=f;},
  click:function(){h.click();},focus:function(){document.activeElement=this;}};});
  var b={tabs:tabs,hidden:true,querySelectorAll:function(){return tabs;},addEventListener:function(){}};
  bars.push(b);ids.forEach(el);return b;}
var heads={"of-eld-house":{pane:"pane-ecounty",scrollIntoView:function(){scrolled="of-eld-house";}}};
var document={activeElement:null,getElementById:function(id){return panes[id]||heads[id]||null;},
  querySelector:function(){return null;},querySelectorAll:function(s){return s===".rtabs"?bars:[];}};
var location={hash:""" + json.dumps(hash_) + r""",pathname:"/officials",search:""},replaced=[];
var history={replaceState:function(s,t,u){replaced.push(u);location.hash=u.slice(u.indexOf("#"));}};
var addEventListener=function(k,f){(listeners[k]=listeners[k]||[]).push(f);};
var roster=bar(["pane-last","pane-county","pane-seat"]),elect=bar(["pane-elast","pane-ecounty"]);
""" + js + r"""
function shown(){return Object.keys(panes).filter(function(k){return !panes[k].hidden;}).sort().join(",");}
var a=shown(); elect.tabs[1].click(); var b=shown(); roster.tabs[2].click(); var c=shown();
elect.tabs[0].click(); location.hash="#of-eld-house";
(listeners.hashchange||[]).forEach(function(f){f();}); var d=shown();
console.log(JSON.stringify([a,b,c,d,String(scrolled),bars.map(function(x){return x.hidden;}).join(","),
  replaced.join(" ")]));
"""
        import subprocess as _sp
        for hash_, want_ in (("", ["pane-elast,pane-last", "pane-ecounty,pane-last",
                                   "pane-ecounty,pane-seat", "pane-ecounty,pane-seat",
                                   "of-eld-house", "false,false", ""]),
                             # an old By district address, at arrival, opens By county; By
                             # last name picked then names itself, so a reload opens it
                             ("#of-eld-house", ["pane-ecounty,pane-last", "pane-ecounty,pane-last",
                                                "pane-ecounty,pane-seat", "pane-ecounty,pane-seat",
                                                "of-eld-house", "false,false", "/officials#pane-elast"]),
                             # #pane-edist and #tab-edist become the view's own id: the view
                             # itself, not a heading in it
                             ("#pane-ecounty", ["pane-ecounty,pane-last", "pane-ecounty,pane-last",
                                                "pane-ecounty,pane-seat", "pane-ecounty,pane-seat",
                                                "of-eld-house", "false,false", "/officials#pane-elast"])):
            out = _sp.run([node, "-e", harness(hash_)], capture_output=True, text=True, timeout=60)
            if out.returncode != 0 or (out.stdout.strip() or "[]")[:1] != "[" or json.loads(
                    out.stdout) != want_:
                bad.append(f"the strips' script, on the roster's and the members-elect's, with the "
                           f"address {hash_!r}: {(out.stdout or out.stderr).strip()[:300]}")
    assert not bad, "\n  ".join(bad)
    return "ok", ("each member-elect the Legislators tab's chip with its word beside it, linked "
                  "as the file links them; by last name in party columns, by county for both "
                  "chambers with what is not final; the seats by party at the top, a bar and a "
                  "line for a phone, and the seats not final listed; Spanish throughout"
                  + ("; both strips switch their own panes and open the view an address names"
                     if node else " (node absent: the strips' script not run)"))


@check("build", "a member-elect is titled Rep.-elect or Sen.-elect (Representative-elect and "
                "Senator-elect in a page's heading), and no source file writes the title the "
                "old way, Elect in quotation marks", needs=("officials_tabs", "build_legislator_pages",
                                                         "build_lsrs", "sponsor_roster", "i18n"))
def _elect_title_hyphenated(OT, BLP, LS, SR, I):
    """The owner, 20 November 2026: "You can change the Rep. "Elect" Alice
    Wade back to the standard format of Rep.-elect Alice Wade since I hadn't
    realized the hyphenated version appears to be the traditional format."
    Her choice of 16 November had put the word Elect in quotation marks.

    The title as each place that writes it gives it: the Members-Elect tab's
    chip (officials_tabs.elect_chip), the search's rows and their own page
    (build_legislator_pages.elect_title, and elect_heading spelling it out),
    a request's card and chip (build_lsrs.elect_title), the honorific read
    back off it (build_lsrs.label_name, sponsor_roster.chamber_of, and in
    app.js fullTitle, spChamber and cardSponsor, run in node where it is
    installed), and the Spanish, "Rep. electo/a", the catalog's own adjective
    for a member-elect ("Miembro electo"), current for the new English.

    And so the old form cannot come back through a default, a pattern or a
    catalog entry: no file git tracks under src/, workers/, functions/ or
    words/ carries Elect after an opening quotation mark, as the character,
    as a backslash-u escape or as an HTML entity, in any case, in English or in the
    Spanish that mirrored it. The patterns are built here from their parts,
    so this file is read by the same test."""
    bad = []
    rep, sen = "Rep.-elect", "Sen.-elect"
    got = {"BLP.elect_title": (BLP.elect_title("H"), BLP.elect_title("S")),
           "build_lsrs.elect_title": (LS.elect_title("H"), LS.elect_title("S"))}
    for where, pair in got.items():
        if pair != (rep, sen):
            bad.append(f"{where} gives {pair!r}, not {(rep, sen)!r}")
    heads = (BLP.elect_heading(rep, "Heather Deiner", "D"), BLP.elect_heading(sen, "Laura Telerski", "D"))
    if heads != ("Representative-elect Heather Deiner (D)", "Senator-elect Laura Telerski (D)"):
        bad.append(f"the headings read {heads!r}")
    if LS.label_name(rep + " Colin Mitchell (R)") != "Colin Mitchell":
        bad.append(f"label_name reads {LS.label_name(rep + ' Colin Mitchell (R)')!r}")
    if (SR.chamber_of(rep + " Colin Mitchell (R)"), SR.chamber_of(sen + " Kurt Webber (D)")) != ("H", "S"):
        bad.append("sponsor_roster.chamber_of does not read the chamber off the title")
    chips = {lang: (OT.elect_chip({"n": "Pat Newell", "p": "D", "k": "new"}, "H|Belknap|6", lang),
                    OT.elect_chip({"n": "Kurt Webber", "p": "D", "k": "new"}, "S|2", lang))
             for lang in ("en", "es")}
    if not (">Rep.-elect Pat Newell <" in chips["en"][0] and ">Sen.-elect Kurt Webber <" in chips["en"][1]):
        bad.append(f"the Members-Elect tab's chips read {chips['en']!r}")
    if not (">Rep. electo/a Pat Newell <" in chips["es"][0] and ">Sen. electo/a Kurt Webber <" in chips["es"][1]):
        bad.append(f"the Spanish tab's chips read {chips['es']!r}")
    es = (I.say("es", "elect.title_rep", rep), I.say("es", "elect.title_sen", sen))
    if es != ("Rep. electo/a", "Sen. electo/a"):
        bad.append(f"the Spanish titles are {es!r}: lang/es.json's entry is not current for the English")
    js = _app_js('[scope.fullTitle("Sen.-elect Laura Telerski (D)"), scope.fullTitle("Former Rep. Jane Doe"),'
                 ' scope.spChamber("Rep.-elect Colin Mitchell (R)"), scope.spChamber("Sen.-elect Kurt Webber (D)"),'
                 ' scope.cardSponsor({sponsor_label: "Rep.-elect Colin Mitchell (R)"}).display_full]',
                 names=("fullTitle", "spChamber", "cardSponsor"))
    if js is not None and js != ["Senator-elect Laura Telerski (D)", "Former Representative Jane Doe",
                                 "H", "S", "Rep.-elect Colin Mitchell (R)"]:
        bad.append(f"app.js reads the title as {js!r}")
    # The old form, built from its parts: the opening quotation mark, its
    # escape and its entities, each before "elect".
    olds = [chr(0x201C) + "elect", "\\" + "u201celect", "&" + "ldquo;elect", "&" + "#8220;elect",
            "&" + "#x201c;elect"]
    out = _run(["git", "ls-files", "--", "src", "workers", "functions", "words"],
               capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        return "skip", "git would not list the tracked files, so the sources were not read"
    texts = (".py", ".js", ".mjs", ".json", ".html", ".css", ".md", ".txt", ".toml", ".yml", ".yaml")
    read = 0
    for name in out.stdout.splitlines():
        if not name.endswith(texts) or not Path(name).is_file():
            continue
        text = _source(name, errors="replace").lower()
        read += 1
        for i, line in enumerate(text.splitlines(), 1):
            if any(o in line for o in olds):
                bad.append(f"{name}:{i} writes the title the old way")
    assert read, "no tracked source file was read"
    assert not bad, "\n  ".join(bad)
    return "ok", (f"Rep.-elect and Sen.-elect on the tab's chip, the search's rows, a request's card "
                  f"and their own page, spelled out Representative-elect and Senator-elect in its "
                  f"heading, and the chamber read back off them in Python"
                  + (" and in app.js" if js is not None else " (node absent: app.js not run)")
                  + f"; Rep. electo/a and Sen. electo/a in Spanish; none of {read} tracked source "
                  f"files under src/, workers/, functions/ and words/ writes Elect in quotation marks")


@check("frontend", "the Members-Elect tab has a search box and filters by status, party and "
                   "chamber, with each count said, written hidden for the script to show; the "
                   "plain lists are the page without it", needs=("officials_tabs",))
def _elect_search_filter(OT):
    """The owner, 12 November 2026: "a search function for the member's elect
    page and ... sort by returning, incumbent, new, and new chamber". On the
    fixture of the tab: the row is the site's .bfilt, written hidden; each
    item carries data-st, data-p, data-ch and data-hay and a page without
    the script has the lists as they were; each select's options count what
    they choose; and the script, run in node on the items the page really
    carries, matches by what is typed (every word, accents folded: a name, a
    county, a district, a town) and what is chosen, and says how many are
    shown and fixes the headings' counts. A second fixture of near districts
    (Merr 5 and 15, SD1 and SD18, Hills 4 and 40, an invented ward) proves
    that a number finds its district only, titles and town names before a
    number, the record name, apostrophes and a pasted chip."""
    import html as _h
    import shutil as _sh
    elect, people = _elect_tab_case()
    towns = {"H|Rockingham|13": ["Hampton", "Hampton Falls"], "H|Belknap|6": ["Gilford"]}
    page = OT.members_elect(elect, "2026-11-20", "en", people, towns)
    bad = []
    bar = re.search(r'<div class="bfilt elfilter" role="search" hidden data-n="12" [^>]*>(.*?)</div>',
                    page, re.S)
    if not bar:
        return "FAIL", "the search row is not written hidden over the lists"
    opts = {m[0]: re.findall(r'<option value="([^"]*)">([^<]*)</option>', m[1])
            for m in re.findall(r'<select class="(el[a-z]+)">(.*?)</select>', bar.group(1))}
    if opts.get("elst") != [("", "All (12)"), ("returning", "Returning (1)"),
                            ("incumbent", "Incumbent (3)"), ("chamber", "New chamber (2)"),
                            ("new", "New (6)")]:
        bad.append(f"the status options are {opts.get('elst')}")
    if opts.get("elch") != [("", "Both (12)"), ("S", "Senate (4)"), ("H", "House (8)")]:
        bad.append(f"the chamber options are {opts.get('elch')}")
    if opts.get("elpa") != [("", "All (12)"), ("D", "Democrats (7)"), ("R", "Republicans (3)"),
                            ("+", "More than one party (1)"), ("-", "Party not on file (1)")]:
        bad.append(f"the party options are {opts.get('elpa')}")
    if 'type="search"' not in bar.group(1) or "Name, town or district" not in bar.group(1):
        bad.append("the box does not ask for a name, a town or a district")
    if re.search(r'class="[^"]*\belout\b', page):
        bad.append("an item is drawn already filtered out")
    per = re.findall(r'<(?:li|div) class="(?:seatrow|mem)[^"]*" data-st="([a-z]*)" data-p="([^"]*)" '
                     r'data-ch="([SH])" data-hay="([^"]*)">', page)
    if len(per) != 24:
        bad.append(f"{len(per)} items carry their data, not 12 in each of the two views")
    last = page[:page.find('id="pane-ecounty"')]
    items = [{"st": a, "p": b, "ch": c, "hay": d} for a, b, c, d in re.findall(
        r'<(?:li|div) class="(?:seatrow|mem)[^"]*" data-st="([a-z]*)" data-p="([^"]*)" '
        r'data-ch="([SH])" data-hay="([^"]*)">', last)]
    if len(items) != 12 or not any("hampton" in i["hay"] for i in items):
        bad.append(f"the first view carries {len(items)} items, with the towns of a race in their words")
    node = _sh.which("node")
    script = re.search(r"<script>(.*?)</script>", page, re.S)
    if not script:
        return "FAIL", "; ".join(bad + ["the page carries no script for the controls"])
    if node:
        import subprocess as _sp
        harness = r"""
var ITEMS=""" + json.dumps(items) + r""";
function el(o){var e=Object.assign({c:new Set(),ls:{}},o);
  e.classList={toggle:function(n,f){if(f===undefined)f=!e.c.has(n);if(f)e.c.add(n);else e.c.delete(n);},
               contains:function(n){return e.c.has(n);}};
  e.addEventListener=function(t,f){(e.ls[t]=e.ls[t]||[]).push(f);};
  e.fire=function(t){(e.ls[t]||[]).forEach(function(f){f();});};
  return e;}
var cells=ITEMS.map(function(i,n){return el({dataset:{st:i.st,p:i.p,ch:i.ch,hay:i.hay},
  closest:function(s){return s==="#pane-elast"?this:null;}});});
var box=el({value:""}),st=el({value:""}),pa=el({value:""}),ch=el({value:""}),say=el({textContent:""});
var h2s=[el({id:"of-elect-senate",textContent:"Senate — 4",parentNode:{className:""}}),
         el({id:"of-elect-house",textContent:"House — 8",parentNode:{className:""}})];
var bar=el({dataset:{some:"Showing {n} of {m} members-elect",none:"No member-elect matches that.",n:"12"},
  querySelector:function(s){return {".elq":box,".elst":st,".elpa":pa,".elch":ch,".elcount":say}[s];}});
var panel={querySelectorAll:function(s){return s==="[data-st]"?cells:s.indexOf("h2")===0?h2s:[];}};
bar.parentNode=panel;
var window={};
var document={querySelector:function(s){return s===".elfilter"?bar:null;}};
""" + script.group(1) + r"""
function names(){return cells.map(function(c,i){return c.c.has("elout")?null:ITEMS[i].hay.split(" district")[0];})
  .filter(Boolean);}
function go(q,s,p,c){box.value=q;st.value=s;pa.value=p;ch.value=c;box.fire("input");
  return {n:names(),say:say.textContent,h:h2s.map(function(h){return h.textContent;})};}
var out={};
out.all=go("","","","");
out.returning=go("","returning","","");
out.incumbent=go("","incumbent","","");
out.chamber=go("","chamber","","");
out.new=go("","new","","");
out.hampton=go("hampton","","","");
out.sd8=go("sd8","","","");
out.rock13=go("rock 13","","","");
out.two=go("kwoka rebecca","","","");
out.none=go("chandley","incumbent","","");
out.sd=go("","","D","S");
out.nop=go("","","-","");
out.both=go("","","+","");
out.fold=window.electMatch({st:"new",p:"D",ch:"H",hay:"matt sabourin dit choiniere"},"CHOINIÈRE","","","");
out.no=window.electMatch({st:"new",p:"D",ch:"H",hay:"jodi nelson"},"nelsen","","","");
out.back=go("","","","");
console.log(JSON.stringify(out));
"""
        r = _sp.run([node, "-e", harness], capture_output=True, text=True, encoding="utf-8",
                    timeout=60)
        if r.returncode != 0 or not r.stdout.strip().startswith("{"):
            bad.append(f"the script did not run in node: {(r.stderr or r.stdout).strip()[:400]}")
        else:
            o = json.loads(r.stdout)
            # `hay` begins with the name: the first word says who it is.
            def who(v):
                return sorted(x.split(" ")[0] for x in v["n"])
            want = {"returning": ["shannon"], "incumbent": ["ann", "charles", "rebecca"],
                    "chamber": ["jim", "rachel"],
                    "new": ["karen", "kristine", "lee", "pat", "william", "zoe"],
                    "hampton": ["charles", "kristine"], "sd8": ["jim"],
                    "rock13": ["charles", "kristine"], "two": ["rebecca"], "none": [],
                    "sd": ["rachel", "rebecca", "shannon"], "nop": ["lee"], "both": ["pat"]}
            for k, w in want.items():
                got = who(o[k])
                if got != w:
                    bad.append(f"search/filter {k!r} shows {got}, not {w}")
            if len(o["all"]["n"]) != 12 or o["all"]["say"] != "" or o["back"]["say"] != "" \
                    or o["all"]["h"] != ["Senate — 4", "House — 8"]:
                bad.append(f"with nothing asked, the list is not whole and silent: {o['all']}")
            if o["incumbent"]["say"] != "Showing 3 of 12 members-elect" or o["none"]["say"] != \
                    "No member-elect matches that.":
                bad.append(f"the count said is {o['incumbent']['say']!r} / {o['none']['say']!r}")
            if o["incumbent"]["h"] != ["Senate — 1", "House — 2"]:
                bad.append(f"the headings' counts under a filter are {o['incumbent']['h']}")
            if o["fold"] is not True or o["no"] is not False:
                bad.append("accents are not folded, or a near name matches: "
                           f"{o['fold']} {o['no']}")
        # A DISTRICT IS A NUMBER, AND A NAME IS THE ONE ON THEIR PAGE (the
        # review of 14 November 2026: "merr 5" found Merr 15, 19, 25 and 30
        # and not Merr 5, "senate district 8" found SD8, 13, 15 and 18, and
        # "james creighton" found nobody -- the ballot says Jim). Beside the
        # fixture's districts stand Merr 15, SD18, Hills 40 and a ward (towns
        # invented here: Nashbury, Dunmere); each query must find that
        # district's member only. And a title before a number names the
        # chamber ("sen 8"), a town or a surname before a number is that
        # town's ward or the district ("trow 13", "creighton 8"), a county
        # before "district" is that county's (SD1 takes in a town named
        # Carroll and is not "carroll 1"), a curly apostrophe finds the name
        # a straight one spells, and the chip pasted whole finds its person.
        import copy as _cp
        el2 = _cp.deepcopy(elect)
        race = lambda *names: {"seats": len(names), "not_final": 0, "held": 0,  # noqa: E731
                               "elected": [{"n": n, "p": "D", "k": "new"} for n in names]}
        el2["races"].update({"S|1": race("Tom Onesen"), "S|18": race("Una Eighteen"),
                             "H|Merrimack|5": race("Mia Five"),
                             "H|Merrimack|15": race("Ned Fifteen", "Sean O'Rorke"),
                             "H|Hillsborough|4": race("Hal Four"), "H|Hillsborough|40": race("Ivy Forty"),
                             "H|Grafton|2": race("Gus Ward"), "H|Strafford|9": race("Dot Nine")})
        page2 = OT.members_elect(el2, "2026-11-20", "en", people,
                                 {**towns, "H|Merrimack|15": ["Nashbury Ward 5"],
                                  "H|Merrimack|5": ["Dunmere", "Maple Hill", "Quillan's Loc."],
                                  # Real place names put in SD1 only to test the
                                  # matching (a county's name, an apostrophe, a
                                  # city's ward); Dot's race has another ward
                                  # of Dover and an invented city's.
                                  "S|1": ["Carroll", "Hart's Location", "Dover Ward 1"],
                                  "H|Strafford|9": ["Dover Ward 3", "Nashbury Ward 1"]})
        last2 = page2[:page2.find('id="pane-ecounty"')]
        items2 = [{"st": a, "p": b, "ch": c, "hay": d} for a, b, c, d in re.findall(
            r'<(?:li|div) class="(?:seatrow|mem)[^"]*" data-st="([a-z]*)" data-p="([^"]*)" '
            r'data-ch="([SH])" data-hay="([^"]*)">', last2)]
        asks = {"merr 5": ["mia"], "merrimack 5": ["mia"], "hills 4": ["hal"],
                "hillsborough 40": ["ivy"], "sd 8": ["jim"], "sd8": ["jim"],
                "senate district 8": ["jim"], "sd 1": ["tom"], "sd1": ["tom"],
                "senate district 1": ["tom"], "district 5": ["mia"], "5": ["mia"],
                "nashbury ward 5": ["ned", "sean"], "nashbury 5": ["ned", "sean"],
                "ward 5": ["ned", "sean"], "rock 13": ["charles", "kristine"],
                "sen 1": ["tom"], "senator 1": ["tom"], "sen. 1": ["tom"], "sen 8": ["jim"],
                "rep 1": ["ann"], "rep 8": [], "rep 5": ["mia"],
                "trow 13": ["kristine"], "creighton 8": ["jim"], "hampton 13": ["charles", "kristine"],
                "carroll district 1": [], "carroll 1": [], "carr 1": [], "coos district 1": ["ann"],
                "dover ward 1": ["tom"], "dover 1": ["tom"], "dover ward 5": [],
                "merrimack district 15": ["ned", "sean"], "hills district 15": [],
                "o’rorke": ["sean"], "o'rorke": ["sean"], "o rorke": ["sean"], "ororke": ["sean"],
                "hart’s location": ["tom"], "harts loc.": ["tom"],
                "Sen.-elect Jim Creighton (R - SD8)": ["jim"],
                "Rep.-elect Sean O’Rorke (D - Merr 15)": ["sean"],
                "james creighton": ["jim"], "jim creighton": ["jim"], "rep creighton": ["jim"],
                "representative creighton": ["jim"], "sen. creighton": ["jim"],
                "senator james creighton": ["jim"], "rep nobody": ["lee"], "rep Una": ["una"],
                "han": [], "hamp": ["charles", "kristine"],
                # a full name or a two-word town ending in a county's word or "ward"
                "gus ward 2": ["gus"], "maple hill 5": ["mia"], "maple hill district 5": ["mia"],
                "dover ward 3": ["dot"], "nashbury ward 1": ["dot"],
                # the chip's party letter, alone or as a pair, and an initial
                "creighton r": ["jim"], "(R - SD8)": ["jim"],
                "Rep.-elect Pat Both (R/D - Belk 6)": ["pat"], "J. Creighton": ["jim"],
                # a title before "district" names the chamber
                "senator district 1": ["tom"], "rep district 1": ["ann"],
                "sen district 8": ["jim"], "rep district 8": [],
                # "Loc." is read as the word
                "quillans location": ["mia"], "quillan’s loc.": ["mia"], "r": ["charles", "kristine", "rachel", "rebecca", "sean", "zoe"]}
        h2 = r"""
var window={},document={querySelector:function(){return null;}};
""" + script.group(1) + r"""
var ITEMS=""" + json.dumps(items2) + r""",ASKS=""" + json.dumps(list(asks)) + r""",out={};
ASKS.forEach(function(q){out[q]=ITEMS.filter(function(i){return window.electMatch(i,q,"","","");})
  .map(function(i){return i.hay.split(" | ")[0].split(" ")[0];}).sort();});
console.log(JSON.stringify(out));
"""
        r2 = _sp.run([node, "-e", h2], capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert r2.returncode == 0 and r2.stdout.strip().startswith("{"), \
            f"the district script did not run in node: {(r2.stderr or r2.stdout).strip()[:400]}"
        o2 = json.loads(r2.stdout)
        for q, w in asks.items():
            if o2[q] != w:
                bad.append(f"the search {q!r} shows {o2[q]}, not {w}")
        # A SEARCH FOR A DISTRICT NOT FINAL SAYS SO, AND THE LIST'S LINE GOES
        # (the review of 14 November 2026: "merr 5", a recount pending, drew
        # "No member-elect matches that." over an empty list, and "All 408
        # members-elect..." stayed above "Senate - 0"). A race not final has
        # nobody to find, so the bar carries them (data-nf). Here Merrimack 5
        # (a recount) and Senate 14 (none) are not final; each answers its
        # own search with its sentence; a search that finds no race says what
        # it always said; a search that finds members, or any status or party
        # chosen, is not answered with it; and the counting line is out while
        # a search is on and back when it is cleared.
        el3 = _cp.deepcopy(elect)
        el3["races"].update({"H|Merrimack|5": {"seats": 1, "not_final": 1, "held": 0, "recount": True,
                                               "elected": []},
                             "S|14": {"seats": 1, "not_final": 1, "held": 0, "elected": []}})
        page3 = OT.members_elect(el3, "2026-11-20", "en", people, towns)
        bar3 = re.search(r'<div class="bfilt elfilter" role="search" hidden data-n="12" ([^>]*)>', page3)
        nf3 = re.search(r'data-nf="([^"]*)"', bar3.group(1)) if bar3 else None
        if not nf3:
            bad.append("the search row carries no data-nf for the races not final")
        elif 'class="src elall"' not in page3:
            bad.append("the line counting the whole list has no handle for the script")
        else:
            last3 = page3[:page3.find('id="pane-ecounty"')]
            items3 = [{"st": a, "p": b, "ch": c, "hay": d} for a, b, c, d in re.findall(
                r'<(?:li|div) class="(?:seatrow|mem)[^"]*" data-st="([a-z]*)" data-p="([^"]*)" '
                r'data-ch="([SH])" data-hay="([^"]*)">', last3)]
            h3 = r"""
var ITEMS=""" + json.dumps(items3) + r""";
function el(o){var e=Object.assign({c:new Set(),ls:{}},o);
  e.classList={toggle:function(n,f){if(f===undefined)f=!e.c.has(n);if(f)e.c.add(n);else e.c.delete(n);},
               contains:function(n){return e.c.has(n);}};
  e.addEventListener=function(t,f){(e.ls[t]=e.ls[t]||[]).push(f);};
  e.fire=function(t){(e.ls[t]||[]).forEach(function(f){f();});};
  return e;}
var cells=ITEMS.map(function(i){return el({dataset:{st:i.st,p:i.p,ch:i.ch,hay:i.hay},
  closest:function(s){return s==="#pane-elast"?this:null;}});});
var box=el({value:""}),st=el({value:""}),pa=el({value:""}),ch=el({value:""}),say=el({textContent:""});
var line=el({});
var bar=el({dataset:{some:"Showing {n} of {m} members-elect",none:"No member-elect matches that.",n:"12",
  nf:""" + json.dumps(_h.unescape(nf3.group(1))) + r"""},
  querySelector:function(s){return {".elq":box,".elst":st,".elpa":pa,".elch":ch,".elcount":say}[s];}});
var panel={querySelectorAll:function(s){return s==="[data-st]"?cells:s===".elall"?[line]:[];}};
bar.parentNode=panel;
var window={};
var document={querySelector:function(s){return s===".elfilter"?bar:null;}};
""" + script.group(1) + r"""
function go(q,s,p,c){box.value=q;st.value=s;pa.value=p;ch.value=c;box.fire("input");
  return {say:say.textContent,line:line.c.has("elout")};}
console.log(JSON.stringify({a:go("merr 5","","",""),b:go("sd 14","","",""),c:go("merr 6","","",""),
  d:go("rock 13","","",""),e:go("merr 5","new","",""),f:go("","","",""),g:go("merr 5","","","S")}));
"""
            r3 = _sp.run([node, "-e", h3], capture_output=True, text=True, encoding="utf-8", timeout=60)
            assert r3.returncode == 0 and r3.stdout.strip().startswith("{"), \
                f"the not-final script did not run in node: {(r3.stderr or r3.stdout).strip()[:400]}"
            o3 = json.loads(r3.stdout)
            none_ = "No member-elect matches that."
            want3 = {"a": "Merrimack District 5's result is not final: a recount was requested.",
                     "b": "Senate District 14's result is not final.", "c": none_, "e": none_, "g": none_}
            for k, w in want3.items():
                if o3[k]["say"] != w:
                    bad.append(f"a search for a district not final ({k}) says {o3[k]['say']!r}, not {w!r}")
            if not o3["d"]["say"].startswith("Showing "):
                bad.append(f"a search that finds members says {o3['d']['say']!r}")
            if not (o3["a"]["line"] and o3["d"]["line"]) or o3["f"]["line"]:
                bad.append("the line counting the whole list is not out while a search is on and back "
                           f"when it is cleared: {o3['a']['line']} {o3['d']['line']} {o3['f']['line']}")
    # Spanish: the row's words, none in English.
    es = OT.members_elect(elect, "2026-11-20", "es", people, towns)
    row = re.search(r'<div class="bfilt elfilter".*?</div>', es, re.S).group(0)
    blob = _h.unescape(re.sub(r"<[^>]+>", " ", row) + " " + " ".join(
        re.findall(r'(?:placeholder|data-some|data-none)="([^"]*)"', row)))
    for word in ("Search", "Status", "Party", "Chamber", "All", "Both", "Returning", "Incumbent",
                 "Name, town", "members-elect", "Showing"):
        if re.search(r"(?<![\w.-])" + re.escape(word) + r"(?![\w-])", blob):
            bad.append(f"the Spanish search row says {word!r}")
    # With nobody, no row is drawn at all.
    if OT.elect_controls([], {}):
        bad.append("a tab of nobody draws a search row")
    assert not bad, "\n  ".join(bad)
    return "ok", ("a search row written hidden, counts in every option, items carrying data-st, "
                  "-p, -ch and -hay; node: status, party, chamber, name, county, district, "
                  "town and accents, headings recounted, the count said; and on a fixture of near "
                  "districts, a number finds its district only (county, sd, senate district, "
                  "ward, a town or surname before it), a title before a number names the "
                  "chamber, a record name, a curly apostrophe and a pasted chip find the person"
                  if node else "the row and the items (node absent: the script not run)")


@check("naming", "a past bill no other source names a sponsor for takes the General "
                 "Court's sponsor record, with the record's chamber and no seat of today's",
       needs=("text_sponsors", "build_site_v2"))
def _past_sponsors_fill(text_sponsors, B):
    """past_sponsors.py's fill, 1 October 2026: every past term outside
    MERGED takes the record's list for a bill that has no sponsor in
    data/sponsors.json and none read off its text -- and for no other bill.

    HB 104 of 1993 has no saved page; PastSponsors lists four people on its
    LSR, 1993-0062, and marks Betsy McKinney prime. HB 128 of that year prints
    "Rep. Crotty of Hills 43; Rep. Christie of Rock 22", and keeps them.

    A FILLED ROW CARRIES THE RECORD'S CHAMBER AND NOTHING OF TODAY. Sherman
    Packard co-sponsored HB 104 and is the roster's Rep. Sherman Packard (R -
    Rock 16); the 1993 row is linked to his page and drawn "Rep. Sherman
    Packard", with no seat, because the record holds none, and no party of
    its own, because no ballot of 1993-1994 exists to take one from. (The
    build gives it his page's party where every record of him gives that one
    -- early_party, the owner's decision of 15 November 2026, held by the
    check after this one; none is passed here.) A number the site has nobody
    under stays a name: William Boucher, Thomas Colantuono.

    The merge fills only a bill with no list at the moment it merges, never
    the merged term, never the current one.
    """
    import past_sponsors as PSP
    from collections import defaultdict as _dd
    T = text_sponsors
    bills = {
        "1993-1994": {
            "HB104": {"bill": "HB104", "lsr_year": "1993", "lsr_num": "62"},
            "HB128": {"bill": "HB128", "lsr_year": "1993", "lsr_num": "132"}},
        "2023-2024": {"HB32": {"bill": "HB32", "lsr_year": "2023", "lsr_num": "0170"}},
        "2025-2026": {"HB1": {"bill": "HB1", "lsr_year": "2025", "lsr_num": "0001"}}}
    # PastSponsors.psv lines 46539-46542 and 46644-46645, and one row each for
    # the two terms that are never filled.
    ps = [_ps_row(1993, 62, 1, "360347"), _ps_row(1993, 62, 2, "202341"),
          _ps_row(1993, 62, 3, "331314", prime=True), _ps_row(1993, 62, 4, "375453"),
          _ps_row(1993, 132, 1, "374900"), _ps_row(1993, 132, 2, "374595", prime=True),
          _ps_row(2023, 170, 1, "376628", prime=True),
          _ps_row(2025, 1, 1, "375453", prime=True)]
    pl = [{"SessionYear": "1993", "LSR": "62", "CondensedBillNo": "HB104"},
          {"SessionYear": "1993", "LSR": "132", "CondensedBillNo": "HB128"}]
    # db/Legislators.psv, past_members.json and data/member_votes.json, for
    # the four numbers on LSR 1993-0062.
    legs = [{"PersonID": "425", "Employeeno": "375453", "LastName": "Packard",
             "FirstName": "Sherman", "LegislativeBody": "H"},
            {"PersonID": "970", "Employeeno": "331314", "LastName": "McKinney",
             "FirstName": "Betsy", "LegislativeBody": "H"}]
    members = {"360347": {"name": "Boucher, William", "chamber": "H"},
               "202341": {"name": "Colantuono, Thomas", "chamber": "S"}}
    votes = [{"member_id": "425", "name": "Packard, Sherman", "party": "R", "year": "2026",
              "body": "H", "label": "Rep. Sherman Packard (R - Rock 16)"},
             {"member_id": "970", "name": "McKinney, Betsy", "party": "R", "year": "1999",
              "body": "H", "label": "McKinney, Betsy(R) Rockingham 05"}]
    roster = [{"id": "425", "name": "Packard, Sherman", "last": "Packard",
               "first": "Sherman", "chamber": "H"}]
    people = PSP.People(legs, members, votes, roster)
    joined, _tally = PSP.join(bills, ps, pl)
    named = {"1993-1994": {"HB128": [{"name": "Crotty", "source": T.SOURCE}]}}
    doc = PSP.build(bills, {}, people, joined, named=named, current="2025-2026",
                    line_of=lambda *_a: None)
    fill = doc["1993-1994"]["HB104"].get("fill") or []
    assert [(r["name"], r["prime"], r["member_id"], r["chamber"], r["party"])
            for r in fill] == [
        ("Betsy McKinney", True, "970", "H", ""), ("William Boucher", False, "", "H", ""),
        ("Thomas Colantuono", False, "", "S", ""),
        ("Sherman Packard", False, "425", "H", "")], fill
    assert all(r["source"] == PSP.SOURCE and r["seat_source"] == PSP.SOURCE
               and not r["prime_inferred"] for r in fill), fill
    assert [r["label"] for r in fill] == [
        "Rep. Betsy McKinney", "Rep. William Boucher", "Sen. Thomas Colantuono",
        "Rep. Sherman Packard"], [r["label"] for r in fill]
    assert "fill" not in doc["1993-1994"]["HB128"], (
        "a bill whose own text names its sponsors was given the record's list")
    assert "fill" not in doc["2023-2024"]["HB32"], (
        "a bill of the merged term was given a list to fill with")
    assert "fill" not in (doc.get("2025-2026") or {}).get("HB1", {}), (
        "a bill of the current term was given a list to fill with")
    assert not any("seat_source" in r for r in doc["2023-2024"]["HB32"].get("publish") or ()), (
        "a row of the merged term says its seat is the record's")

    text_rows = [{"name": "Crotty", "source": T.SOURCE}]
    sponsors = {"1993-1994": {"HB128": list(text_rows)}}
    took = PSP.merge(sponsors, doc, {})
    assert took["filled"] == 1 and [r["name"] for r in sponsors["1993-1994"]["HB104"]] == [
        "Betsy McKinney", "William Boucher", "Thomas Colantuono", "Sherman Packard"], took
    assert sponsors["1993-1994"]["HB128"] == text_rows, "the fill went over a bill's own list"
    mine = [{"name": "Somebody Else"}]
    had = {"1993-1994": {"HB104": list(mine)}}
    assert PSP.merge(had, doc, {})["filled"] == 0 and had["1993-1994"]["HB104"] == mine, (
        "a bill that already has a sponsor took the record's list")
    none = {}
    assert not PSP.merge(none, doc, {}, fill=False)["filled"] and "1993-1994" not in none
    # A list to fill with that turned up under the merged term is not merged:
    # that term's lists are the record's or the page's, by its own rule.
    stray = {"2023-2024": {"HB999": {"fill": [{"name": "Somebody"}]}}}
    into = {}
    assert not PSP.merge(into, stray, {})["filled"] and not (into.get("2023-2024") or {}).get(
        "HB999"), "a fill was merged into the merged term"

    # ONE NUMBER LISTED TWICE IS ONE SPONSOR, AND A LIST WITH NO PRIME MARKED
    # TAKES ITS FIRST. PastSponsors.psv's rows for LSR 2003-1217 (HB 3 of
    # 2003: employee 209058, Sen. Robert Clegg, on rows 2 and 8, and the prime
    # on row 3) and for LSR 1990-9065 (HR 65 of 1990: two rows, neither prime).
    more = {"2003-2004": {"HB3": {"bill": "HB3", "lsr_year": "2003", "lsr_num": "1217"}},
            "1989-1990": {"HR65": {"bill": "HR65", "lsr_year": "1990", "lsr_num": "9065"}},
            "2025-2026": bills["2025-2026"]}
    ps2 = [_ps_row(2003, 1217, n, emp, prime=(n == 3)) for n, emp in enumerate(
        ("375941", "209058", "370346", "372821", "374470", "375649", "209040", "209058",
         "209050", "209015"), 1)] + [_ps_row(1990, 9065, 1, "363283"),
                                     _ps_row(1990, 9065, 2, "360628")]
    pl2 = [{"SessionYear": "2003", "LSR": "1217", "CondensedBillNo": "HB3"},
           {"SessionYear": "1990", "LSR": "9065", "CondensedBillNo": "HR65"}]
    who = {"375941": ("Whalley, Michael", "H"), "209058": ("Clegg, Robert", "S"),
           "370346": ("Chandler, Gene", "H"), "372821": ("Kurk, Neal", "H"),
           "374470": ("Weyler, Kenneth", "H"), "375649": ("Wheeler, Robert", "H"),
           "209040": ("Eaton, Thomas", "S"), "209050": ("Green, Richard", "S"),
           "209015": ("D'Allesandro, Lou", "S"), "363283": ("Scamman, W. Douglas", "H"),
           "360628": ("Chambers, Mary", "H")}
    people2 = PSP.People([], {k: {"name": n, "chamber": c} for k, (n, c) in who.items()},
                         [], [])
    joined2, _tally = PSP.join(more, ps2, pl2)
    doc2 = PSP.build(more, {}, people2, joined2, named={}, current="2025-2026",
                     line_of=lambda *_a: None)
    hb3 = doc2["2003-2004"]["HB3"]["fill"]
    assert [r["employee"] for r in hb3] == [
        "370346", "375941", "209058", "372821", "374470", "375649", "209040", "209050",
        "209015"], f"HB 3 of 2003's filled list: {[r['employee'] for r in hb3]}"
    assert [r["prime"] for r in hb3] == [True] + [False] * 8 and not any(
        r["prime_inferred"] for r in hb3), hb3
    hr65 = doc2["1989-1990"]["HR65"]["fill"]
    assert [(r["employee"], r["prime"], r["prime_inferred"]) for r in hr65] == [
        ("363283", True, True), ("360628", False, False)], (
        "HR 65 of 1990, which the record marks no prime on, is filled as "
        f"{[(r['employee'], r['prime'], r['prime_inferred']) for r in hr65]}")

    # A FILLED LIST OF 1999-2000 SAYS IT MAY BE SHORT (past_sponsors.SHORT_TERMS),
    # on the bill's page; no other term's does, and no list from another source.
    filled_row = [{"name": "Eugene Gagnon", "seat_source": PSP.SOURCE}]
    note = B.record_notes({}, None, "", filled_row, "1999-2000", "HCR34")
    assert len(note) == 1 and "may not be complete" in note[0] and "1999" in note[0], note
    assert B.record_notes({}, None, "", filled_row, "1993-1994", "HB104") == []
    assert B.record_notes({}, None, "", [{"name": "Somebody", "source": T.SOURCE}],
                          "1999-2000", "HB25") == []
    assert "1999-2000" in PSP.SHORT_TERMS and not set(PSP.SHORT_TERMS) & set(PSP.MERGED)

    # On the page: linked to his own page, and nothing of today's seat.
    people_ = {"425": {"id": "425", "name": "Packard, Sherman", "chamber": "H",
                       "party": "R", "party_code": "R", "county": "Rockingham",
                       "county_abbr": "Rock", "district": "16",
                       "slug": "sherman-packard-rock-16"}}
    sponsored = _dd(list)
    sp = B.bill_sponsor_list("HB104", {"designation": "HB 104", "title": "a bill"}, "1993",
                             "1993-1994", "2025-2026", sponsors, people_, {}, {}, sponsored)
    packard = [s for s in sp if s.get("employee") == "375453"][0]
    assert (packard["display_full"], packard["district_label"], packard["party"]) == (
        "Rep. Sherman Packard", "", ""), (
        f"a 1993 sponsor is drawn {packard['display_full']!r}, with today's party or seat")
    assert packard["slug"] and any(x["bill"] == "HB104" for x in sponsored.get("425") or ()), (
        "the row is not linked to the member its employee number is")
    assert sp[0]["prime"] and sp[0]["display_full"] == "Rep. Betsy McKinney", sp[0]
    # The same row without the mark is the roster's, which is what the mark
    # is for: today's seat on a bill of 1993.
    bare = {"1993-1994": {"HB104": [{k: v for k, v in r.items() if k != "seat_source"}
                                    for r in sponsors["1993-1994"]["HB104"]]}}
    sp = B.bill_sponsor_list("HB104", {"designation": "HB 104", "title": "a bill"}, "1993",
                             "1993-1994", "2025-2026", bare, people_, {}, {}, _dd(list))
    assert [s for s in sp if s.get("employee") == "375453"][0]["display_full"] == (
        "Rep. Sherman Packard (R - Rock 16)")
    here = Path(".").resolve()
    for f in ("build_site_v2.py", "build_exports.py"):
        src = _source(_paths.locate(f)) if _paths.locate(f).exists() else ""
        if src:
            a, b = src.find("TS.merge_into("), src.find("PSP.merge_into(")
            assert 0 <= a < b, (f"{f} merges the sponsor record before the bills' own "
                                "printed lists, so a filled list would stand where a "
                                "bill's text names its sponsors")
    return "ok", ("1993 HB 104 filled from the record, McKinney prime, Packard linked and "
                  "drawn with no seat of today, and no party with no record of his passed; "
                  "HB 128 keeps its printed "
                  "sponsors; nothing merged over a list, the merged term or the "
                  "current one; HB 3 of 2003 lists Sen. Clegg once, HR 65 of 1990 "
                  "takes its first name as prime and says so, and a filled list of "
                  "1999-2000 says it may be short")


@check("data", "a bill is filled from the sponsor record only where nothing else names "
               "its sponsors, and a filled row carries no seat of today's")
def _past_sponsors_filled_data():
    """past_sponsors.json's "fill" lists against the two files that outrank
    them: no bill with a sponsor in data/sponsors.json or in text_sponsors.json
    carries one, none is of the merged term or the current one, and every row
    is a named person marked as the record's, with one prime at most.

    And on the built site, where it is here: 1993 HB 104 lists the record's
    four, Betsy McKinney prime, and Rep. Sherman Packard, each with no seat
    of the present day -- and, since the owner's decision of 15 November 2026,
    with the party their page gives where every record of them gives that one
    party (build_site_v2.early_party), so "Rep. Sherman Packard (R)": a name
    and at most a party letter, never a seat.
    """
    p, bp = Path("past_sponsors.json"), Path("data/bills.json")
    if not (p.exists() and bp.exists()):
        return "skip", "no past_sponsors.json or data/bills.json here"
    import past_sponsors as PSP
    doc = json.loads(p.read_text(encoding="utf-8"))
    current = max(json.loads(bp.read_text(encoding="utf-8")))
    load = lambda f: json.loads(Path(f).read_text(encoding="utf-8")) if Path(f).exists() else {}
    named, given = load("text_sponsors.json"), load("data/sponsors.json")
    by_term, rows, bad = Counter(), 0, []
    linked = Counter()
    for term, bb in doc.items():
        for bid, e in bb.items():
            fill = e.get("fill")
            if not fill:
                continue
            by_term[term] += 1
            if term in PSP.MERGED or term == current:
                bad.append(f"{bid} of {term} is filled, in a term that is never filled")
            if (named.get(term) or {}).get(bid) or (given.get(term) or {}).get(bid):
                bad.append(f"{bid} of {term} is filled and another source names its sponsors")
            if sum(1 for r in fill if r.get("prime")) != 1:
                bad.append(f"{bid} of {term} has "
                           f"{sum(1 for r in fill if r.get('prime'))} primes")
            # The record marks the prime; where it marks none the first name
            # is taken and says so, and on no other bill.
            marked = any(s.get("prime") for s in e.get("sponsors") or ())
            if any(r.get("prime_inferred") for r in fill) == marked:
                bad.append(f"{bid} of {term}: the record "
                           f"{'marks' if marked else 'does not mark'} a prime and the "
                           "filled list says otherwise")
            emps = [r.get("employee") for r in fill if r.get("employee")]
            if len(emps) != len(set(emps)):
                bad.append(f"{bid} of {term} lists one employee number twice")
            for r in fill:
                rows += 1
                linked[term] += bool(r.get("member_id"))
                if not r.get("name") or r.get("source") != PSP.SOURCE or (
                        r.get("seat_source") != PSP.SOURCE) or r.get("district") or (
                        SPONSOR_HONORIFIC.search(r.get("name") or "")):
                    bad.append(f"{bid} of {term}: {r.get('name')!r} {r.get('label')!r}")
    assert not bad, f"{len(bad)} filled lists break the rule, e.g. {bad[:5]}"
    said = f"{sum(by_term.values()):,} bills filled across {len(by_term)} terms, {rows:,} names"
    import site_read
    hb104 = site_read.one("site", 1993, "HB104")
    # While it is one of the filled: the day its page is saved, its own
    # printed line names its sponsors and this bill stops being the example.
    if hb104 is not None and ((doc.get("1993-1994") or {}).get("HB104") or {}).get("fill"):
        sp = hb104.get("sponsors") or []
        got = [(s.get("display_full"), bool(s.get("prime"))) for s in sp]
        # A name and at most the page's party letter (early_party); a seat would
        # be "(R - Rock 26)" or "(Rock 26)", which no filled row may carry.
        bare = lambda d: re.sub(r" \([A-Z]\)$", "", d or "")
        seated = [d for d, _ in got if not re.fullmatch(r"(?:Rep|Sen)\. [^()]+(?: \([A-Z]\))?", d or "")]
        assert got and bare(got[0][0]) == "Rep. Betsy McKinney" and got[0][1] \
            and "Rep. Sherman Packard" in [bare(d) for d, p in got if not p] and not seated, (
            f"1993 HB 104's page lists {got}: the record names McKinney prime and "
            "Packard, with no seat of a later term (a party letter their page gives is allowed)")
        said += "; 1993 HB 104 drawn from it, Packard with no seat of today's"
    return "ok", said


@check("frontend", "a member's bills passed are the bill search's Passed, word for word",
       needs=("member_figures",))
def _member_figures_passed(MF):
    """The person, 9 October 2026, v7: "'bills filed' counts every bill
    filed, prime and co-sponsor together; 'bills passed' the same". Passed
    is the bill search's category (app.js statusCat), so member_figures
    ports it; here both run over every (chip, kind) the nineteen terms carry
    (_STATUS_REAL_PAIRS) and every word a chip can say (_STATUS_CATEGORY),
    and must agree. And the term's figures for a member's real rows: Speaker
    Packard's 2025-2026, 17 bills put his name to (4 as prime sponsor),
    of which HB 10, HB 1000, HB 1774 and SB 562 became law (chapters 74, 3,
    242 and 265 in the database's Legislation table) and HR 42 was adopted
    by the House (Ought to Pass, 308-11, 5 March 2026)."""
    pairs = sorted(set(_STATUS_REAL_PAIRS) | {(c, "") for c in _STATUS_CATEGORY}
                   | {(c, k) for c in _STATUS_CATEGORY for k in ("active", "done", "law")})
    got = _node_app(_STATUSCAT_HARNESS, {"pairs.json": json.dumps(pairs), "words.json": "[]"})
    bad = []
    if got is not None:
        assert "threw" not in got, f"statusCat threw {got['threw']}"
        for chip, kind, cat, _w, _k in got["pairs"]:
            mine = MF.status_category({"chip": chip, "kind": kind})
            if mine != cat:
                bad.append(f"{chip!r} ({kind or 'no kind'}): app.js says {cat!r}, "
                           f"member_figures {mine!r}")
    rows = {("2025-2026", b): {"chip": c, "kind": k} for b, c, k in (
        ("HB10", "Became Law", "law"), ("HB1000", "Became Law", "law"),
        ("HB1323", "Died", "done"), ("HB1324", "Died", "done"), ("HB148", "Died", "veto"),
        ("HB1643", "Died", "veto"), ("HB1774", "Became Law", "law"), ("HB1804", "Died", "done"),
        ("HB188", "Died", "done"), ("HB450", "Died", "done"), ("HB452", "Interim Study", "study"),
        ("HB453", "Died", "done"), ("HR42", "Adopted by the House", "adopted"),
        ("SB191", "Interim Study", "study"), ("SB263", "Died", "done"),
        ("SB562", "Became Law", "law"), ("SB631", "Died", "done"))}
    prime = {"HB10", "HB1000", "HB188", "HB450"}
    sponsored = [{"term": t, "bill": b, "prime": b in prime} for t, b in rows]
    att = {"2025-2026": {"chambers": "H", "days": 33, "attended": 28, "roll_calls": 591,
                         "voted": 51, "presided": 287, "conflict": 0, "excused": 146,
                         "not_excused": 107, "no_vote": 0}}
    f = MF.term_figures(sponsored, att, rows)["2025-2026"]
    want = {"bills_filed": 17, "bills_passed": 5, "became_law": 4, "adopted": 1, "ratified": 0,
            "prime": 4, "prime_passed": 2, "cosponsored": 13, "cosponsored_passed": 3,
            "session_days": 33, "days_attended": 28, "roll_calls": 591,
            "roll_calls_recorded": 338}
    if f != want:
        bad.append(f"Speaker Packard's 2025-2026: {f}")
    old = MF.term_figures([{"term": "1993-1994", "bill": "HB142", "prime": True}], {},
                          {("1993-1994", "HB142"): {"chip": "Became Law", "kind": "law"}})
    if old["1993-1994"]["session_days"] is not None:
        bad.append("a term before the roll calls says a zero where the record says nothing")
    assert not bad, "; ".join(bad[:6])
    return "ok", (f"{len(pairs)} chip words and kinds filed alike by app.js and member_figures"
                  if got is not None else "app.js or node is not here; the figures alone")
