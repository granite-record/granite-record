#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.15
"""
preflight's checks of members-elect and election results.

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import _paths

from pf_core import (_in_suite, _parsed, _run, _source, _suite_files, check)
from pf_harness import (_app_js)
from pf_runner import (REMINDERS)
from pf_shared import (_ELECT_DEADLINE, _ELECT_FORMER, _ELECT_HAND, _ELECT_IN, _ELECT_PAGES,
                       _ELECT_TAG, _elect_absent, _elect_blocks, _elect_built, _elect_fixture,
                       _elect_pages, _elect_part, _elect_run, _officials_now)


@check("build", "a new member-elect gets a provisional page, noindex and with no id, at the roster's "
                "own address, and nobody else does; their requests are theirs only where certain")
def _elect_provisional():
    """Alice, 7 November 2026: pages for new members-elect now, "with just
    their name and district", no member id until the General Court assigns
    one, noindex until then (B2), kept past Organization Day (B3). The design
    is docs/design/requests-members/DESIGN.md, 3. What build_members_elect
    decides about each winner is its own and held by its own checks, so it is
    stood in for here by races of each kind."""
    import tempfile
    import build_elect_pages as EP
    import build_members_elect as BME
    import build_legislator_pages as LP
    import build_lsrs as L
    races = {
        "H|Rockingham|13": {"seats": 2, "elected": [
            {"n": "Jane Doe", "p": "D", "k": "new"},
            {"n": "Jodi Nelson", "p": "R", "k": "sitting", "id": "377001", "s": "jodi-nelson-rock-13"}]},
        "S|24": {"seats": 1, "elected": [{"n": "Pat Moore", "p": "R", "k": "new"}]},
        "H|Belknap|2": {"seats": 1, "elected": [{"n": "Lee Park", "p": "R", "k": "new"}]},
    }
    sitting = [{"id": "377001", "name": "Nelson, Jodi", "chamber": "H", "county": "Rockingham",
                "district": "13", "slug": "jodi-nelson-rock-13"},
               # Somebody already at the address Pat Moore's page would take.
               {"id": "377009", "name": "Moore, Patricia", "chamber": "S", "district": "24",
                "slug": "pat-moore-sd-24"}]
    districts = {"Hampton": {"0": {"house": [{"county": "Rockingham", "district": 13, "seats": 2}],
                                   "senate": 24}},
                 "Gilford": {"0": {"house": [{"county": "Belknap", "district": 2, "seats": 1}],
                                   "senate": 7}}}
    real = BME.members_elect
    BME.members_elect = lambda *a, **k: (races, {})
    day = "2026-12-02"
    try:
        got, said, moves = EP.pages({}, sitting, [], districts, {}, "2026-11-08", day, {})
        slugs = [p["slug"] for p in got]
        assert slugs == ["lee-park-belk-2", "jane-doe-rock-13"] and not moves, (
            f"provisional pages for {slugs}: one for each new person, none for a sitting member, "
            "and none at a member's address")
        assert not any("id" in p for p in got), "a provisional page carries an id"
        assert any("pat-moore-sd-24" in s for s in said), f"the address clash is not said: {said}"
        assert got[1]["towns"] == ["Hampton"], f"Jane Doe's towns read {got[1]['towns']}"
        # An old address that already answers with a 301 is taken too.
        got_m, _, _ = EP.pages({}, sitting, [], districts, {}, "2026-11-08", day,
                               {"/legislator/lee-park-belk-2": "377050"})
        assert "lee-park-belk-2" not in [p["slug"] for p in got_m], (
            "a provisional page is given an address that already answers with a 301")
        jane = {"id": "377100", "name": "Doe, Jane", "chamber": "H", "county": "Rockingham",
                "district": "13", "slug": "jane-doe-rock-13"}
        # Before Organization Day nobody is numbered: a sitting member of the
        # name and district is somebody else, whom the owner told apart (at
        # another address; at the same one it is a clash, said above).
        got0, _, m0 = EP.pages({}, sitting + [dict(jane, slug="jane-q-doe-rock-13")], [],
                               districts, {}, "2026-11-20", day, {})
        assert "jane-doe-rock-13" in [p["slug"] for p in got0] and not m0, (
            "before Organization Day a new member-elect lost their page to a sitting namesake")
        # Numbered at the same address: their regular page replaces it.
        got2, _, m2 = EP.pages({}, sitting + [jane], [], districts, {}, "2026-12-10", day, {})
        assert "jane-doe-rock-13" not in [p["slug"] for p in got2] and not m2, (
            "a member-elect the roster now carries at the same address still has a provisional page")
        # Numbered at another address: the provisional one answers with a 301.
        other = dict(jane, slug="jane-q-doe-rock-13")
        _, _, m3 = EP.pages({}, sitting + [other], [], districts, {}, "2026-12-10", day, {})
        assert m3 == {"/legislator/jane-doe-rock-13": "/legislator/jane-q-doe-rock-13"}, m3
        # And when the step comes to call them sitting, the owner's null match
        # still says they were new: still followed to their new address.
        races["H|Rockingham|13"]["elected"][0] = {"n": "Jane Doe", "p": "D", "k": "sitting",
                                                  "id": "377100", "s": "jane-q-doe-rock-13"}
        hand = {"matches": {"H|Rockingham|13": {"Jane Doe": None}}}
        _, _, m4 = EP.pages({}, sitting + [other], [], districts, hand, "2026-12-10", day, {})
        assert m4 == m3, f"a new person the step now calls sitting is not followed: {m4}"
        races["H|Rockingham|13"]["elected"][0] = {"n": "Jane Doe", "p": "D", "k": "new"}
    finally:
        BME.members_elect = real
    import build_pages as BPG
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "elect_pages.json").write_text(json.dumps({"moved": m3}), encoding="utf-8")
        red = BPG.redirects_file(d)
        assert "/legislator/jane-doe-rock-13 /legislator/jane-q-doe-rock-13 301\n" in red \
            and red.index("jane-doe-rock-13") < red.index("/legislator/:who/"), (
            "_redirects has no 301, ahead of the tab rewrites, for a provisional address moved")

    with tempfile.TemporaryDirectory() as d:
        site = Path(d)
        (site / "legislator").mkdir()
        (site / "idx").mkdir()
        doc = {"election": "2026-11-03", "takes_office": "2026-12-02", "sources": [],
               "pages": got}
        (site / "elect_pages.json").write_text(json.dumps(doc), encoding="utf-8")
        (site / "legislators.json").write_text(json.dumps(sitting), encoding="utf-8")
        (site / "meta.json").write_text(json.dumps({"requests": {
            "term": "2027-requests", "label": "2027 Bill Requests"}}), encoding="utf-8")
        # Requests matched by name only where certain: Jane Doe's House bill
        # is hers, a Senate request of the same name is not; and Lee Park's
        # constitutional amendment, which either chamber may file, is his,
        # since nobody else, sitting, elected or a winner, has his name (the
        # owner, 17 November 2026; _request_sponsor_cacr_and_record).
        who = L.roster(site)
        park = next(p["slug"] for p in got if p.get("name") == "Lee Park")
        rows, _ = L.rows_from([
            {"lsr": "2027-0010", "title": "relative to tides.", "sponsor": "Jane Doe", "body": "HB"},
            {"lsr": "2027-0011", "title": "relative to dunes.", "sponsor": "Jane Doe", "body": "SB"},
            {"lsr": "2027-0012", "title": "relative to lakes.", "sponsor": "Lee Park", "body": "CACR"},
            {"lsr": "2027-0013", "title": "relative to roads.", "sponsor": "Jodi Nelson", "body": "HB"}],
            who, year=2027)
        by = {r["n"]: r["sponsor_slug"] for r in rows}
        assert by == {"LSR 2027-0010": "jane-doe-rock-13", "LSR 2027-0011": "",
                      "LSR 2027-0012": park, "LSR 2027-0013": "jodi-nelson-rock-13"}, (
            f"the requests are matched {by}")
        (site / "idx" / "2027-requests.json").write_text(json.dumps(rows), encoding="utf-8")
        # The template every page is drawn from, as the build has it in site/.
        (site / "bills.html").write_text(_source("src/pages/bills.html"),
                                         encoding="utf-8")
        import shell
        try:
            n = LP.write_elect_pages(site, site / "legislator", shell.template(site), "https://x",
                                     {"jodi-nelson-rock-13"}, {}, "2026-12-03")
        except Exception as e:
            raise AssertionError(f"write_elect_pages: {type(e).__name__}: {e}")
        page = (site / "legislator" / "jane-doe-rock-13.html").read_text(encoding="utf-8")
        assert n == 2 and '<meta name="robots" content="noindex,follow">' in page, (
            "a provisional page is written without noindex")
        # Seen with script on: app.css hides a .static-rec under html.js
        # unless it is .shown, and the page was drawn blank so (the
        # screenshots of 8 November 2026). Since 16 November 2026 the page is
        # a member's head and tabs written into #results itself, which no
        # stylesheet rule hides (_elect_page_member_form holds what it says).
        assert '<div id="results"><header class="rhead rh-member rh-p' in page \
            and 'class="static-rec' not in page, (
            "a provisional page's record is not the head written into #results, which shows "
            "with script and without")
        assert "Took office December 2, 2026." in page and "LSR 2027-0010" in page \
            and "LSR 2027-0011" not in page and "GR_MEMBER" not in page, (
            "a provisional page after Organization Day does not say they took office, list their "
            "own request alone, or keeps a member id")
    return "ok", ("new people alone get a page, at the roster's address, never at a member's; "
                  "numbered at the same address the page gives way, at another only with a 301; "
                  "noindex, no id, their requests matched by name and chamber")


@check("build", "a member-elect whose name ends Jr., Sr. or a numeral is addressed with the suffix last, "
                "as the roster addresses a sitting one, and the first address answers with a 301")
def _elect_suffix_address():
    """Found 14 November 2026: two provisional addresses, jr-william-lawrence-belk-3 and
    jr-kevin-m-nugent-belk-4, live since 7 November. build_elect_pages.slug_of passed "William
    Lawrence, Jr." to member_slug, whose comma rule reads "Last, First", so the suffix came
    first. A sitting member's is andrew-christie-jr-rock-22. The suffix is moved to the end
    before member_slug; the first address answers with a 301 to the new one (and to the regular
    page once the roster numbers them); numbered_as passes over a suffix only one side has and
    does not match two that differ, as the members-elect matching (suffixes_agree) does."""
    import tempfile
    import build_elect_pages as EP
    import build_members_elect as BME
    import build_pages as BPG
    assert EP.suffix_last("William Lawrence, Jr.") == "William Lawrence Jr." and \
        EP.suffix_last("Kevin M. Nugent, III") == "Kevin M. Nugent III" and \
        EP.suffix_last("Lawrence, William") == "Lawrence, William" and \
        EP.suffix_last("Smith, Jr., John") == "Smith, Jr., John" and \
        EP.suffix_last("Jodi Nelson") == "Jodi Nelson", "suffix_last moves more or less than a trailing suffix"
    races = {
        "H|Belknap|3": {"seats": 1, "elected": [{"n": "William Lawrence, Jr.", "p": "R", "k": "new"}]},
        "H|Belknap|4": {"seats": 1, "elected": [{"n": "Kevin M. Nugent, Jr.", "p": "R", "k": "new"}]}}
    districts = {"Gilford": {"0": {"house": [{"county": "Belknap", "district": 3, "seats": 1},
                                             {"county": "Belknap", "district": 4, "seats": 1}],
                                   "senate": 7}}}
    real = BME.members_elect
    BME.members_elect = lambda *a, **k: (races, {})
    day = "2026-12-02"
    try:
        got, _said, moves = EP.pages({}, [], [], districts, {}, "2026-11-08", day, {})
        slugs = sorted(p["slug"] for p in got)
        assert slugs == ["kevin-m-nugent-jr-belk-4", "william-lawrence-jr-belk-3"], (
            f"a member-elect's suffix is not last in their address: {slugs}")
        assert moves == {"/legislator/jr-kevin-m-nugent-belk-4": "/legislator/kevin-m-nugent-jr-belk-4",
                         "/legislator/jr-william-lawrence-belk-3":
                         "/legislator/william-lawrence-jr-belk-3"}, (
            f"the first addresses do not answer with a 301 to the new ones: {moves}")
        # Numbered after Organization Day, the roster's own spelling (suffix on one side only):
        # the first address goes to the regular page, which is where the person is.
        reg = {"id": "377500", "name": "Lawrence, William", "chamber": "H", "county": "Belknap",
               "district": "3", "slug": "william-lawrence-belk-3"}
        _g, _s, m2 = EP.pages({}, [reg], [], districts, {}, "2026-12-10", day, {})
        assert m2.get("/legislator/jr-william-lawrence-belk-3") == "/legislator/william-lawrence-belk-3" \
            and m2.get("/legislator/william-lawrence-jr-belk-3") == "/legislator/william-lawrence-belk-3", (
            f"a Jr. whom the roster numbers without the suffix is not found: {m2}")
        # Two suffixes that differ are not a match.
        sr = dict(reg, name="Lawrence, William, Sr.")
        assert EP.numbered_as("William Lawrence, Jr.", "H", "Belknap", "3", [sr]) is None
        assert EP.numbered_as("William Lawrence, Jr.", "H", "Belknap", "3",
                              [dict(reg, name="Lawrence, William, Jr.")]) is not None
        assert EP.numbered_as("William Lawrence", "H", "Belknap", "3",
                              [dict(reg, name="Lawrence, William, Jr.")]) is not None
        assert EP.numbered_as("William Lawrence, Jr.", "H", "Belknap", "3", [reg]) is not None
        assert EP.numbered_as("Jodi Nelson", "H", "Belknap", "3", [reg]) is None
    finally:
        BME.members_elect = real
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "elect_pages.json").write_text(json.dumps({"moved": moves}), encoding="utf-8")
        red = BPG.redirects_file(d)
        assert "/legislator/jr-william-lawrence-belk-3 /legislator/william-lawrence-jr-belk-3 301\n" in red \
            and red.index("jr-william-lawrence-belk-3") < red.index("/legislator/:who/"), (
            "_redirects has no 301 for a member-elect's first address")
    return "ok", ("a member-elect's Jr. goes last in their address (william-lawrence-jr-belk-3); the "
                  "first address answers with a 301 to it, or to the regular page once numbered; "
                  "a suffix only one side has is passed over, two that differ do not match")


@check("build", "a provisional page gives way when the General Court numbers its person, by the members-elect "
                "step's own rule for a seat's sitting member, only once the site's newest term is theirs; "
                "and a number the owner gives by hand keeps the 301")
def _elect_numbered_by_seat_rule():
    """The task of 16 November 2026: an address "that redirects or gives way when the General
    Court numbers them". numbered_as asked for a name that folded to the roster's letter for letter,
    and on the live roster of 16 November 2026 the ballot's name for 71 of 206 re-elected members
    did not (55 by a middle initial alone: "David H. Watters", "Watters, David"), so a third of the
    new members would have kept a second page beside their regular one. Held:

    - numbered_as is the step's rule for a seat's sitting member (build_members_elect.auto_link's
      first): "Roy, Carryl" is "Carryl L. Roy", "Coker, Matthew" is "Matt Coker"; "Pete" is not
      "Peter"; of two members of one seat sharing a surname only the same first name; another seat's
      member never;
    - nobody is numbered until the site's newest term is the results' own, the roster then being
      the new term's (on 2 December with the old roster the page stays); with no term given, the
      day alone decides, as before;
    - numbered at another address, the provisional one answers with a 301 to the regular page;
    - a winner the owner matches by hand to their new number keeps that 301 too, once numbered,
      where the two addresses differ and the old one is nobody else's."""
    import build_elect_pages as EP
    import build_members_elect as BME
    roy = {"id": "380001", "name": "Roy, Carryl", "chamber": "S", "county": "", "district": "12",
           "slug": "carryl-roy-sd-12"}
    coker = {"id": "380002", "name": "Coker, Matthew", "chamber": "H", "county": "Hillsborough",
             "district": "5", "slug": "matthew-coker-hills-5"}
    pete = dict(coker, id="380003", name="Morency, Pete", slug="pete-morency-hills-5")
    haley = {"id": "380004", "name": "Carreau, Haley", "chamber": "H", "county": "Rockingham",
             "district": "13", "slug": "haley-carreau-rock-13"}
    jamie = dict(haley, id="380005", name="Carreau, Jamie", slug="jamie-carreau-rock-13")
    sitting = [roy, coker, pete, haley, jamie]
    for args, want in ((("Carryl L. Roy", "S", "", "12"), "380001"),
                       (("Matt Coker", "H", "Hillsborough", "5"), "380002"),
                       (("Peter Morency", "H", "Hillsborough", "5"), None),
                       (("Haley Carreau", "H", "Rockingham", "13"), "380004"),
                       (("Hal Carreau", "H", "Rockingham", "13"), None),
                       (("Carryl L. Roy", "S", "", "13"), None)):
        got = (EP.numbered_as(*args, sitting) or {}).get("id")
        assert got == want, f"numbered_as{args} is {got}, not {want}"
    results = {"election": "2026-11-03", "term": "2027-2028", "races": {}}
    districts = {"Nashua Ward 1": {"0": {"house": [], "senate": 12}}}
    new = {"S|12": {"seats": 1, "not_final": 0, "held": 0,
                    "elected": [{"n": "Carryl L. Roy", "p": "D", "k": "new"}]}}
    null = {"matches": {"S|12": {"Carryl L. Roy": None}}}
    moved = {"/legislator/carryl-l-roy-sd-12": "/legislator/carryl-roy-sd-12"}
    real = BME.members_elect
    try:
        BME.members_elect = lambda *a, **k: (json.loads(json.dumps(new)), {})
        runs = {label: EP.pages(results, [roy], [], districts, null, day, "2026-12-02", {},
                                roster_term=term)
                for label, day, term in (("old roster", "2026-12-10", "2025-2026"),
                                         ("new roster", "2026-12-10", "2027-2028"),
                                         ("no term", "2026-12-10", None),
                                         ("before the day", "2026-11-20", "2027-2028"))}
        # The owner's number, given by hand once the General Court has given one.
        by_hand = {"matches": {"S|12": {"Carryl L. Roy": "380001"}}}
        BME.members_elect = lambda *a, **k: ({"S|12": {"seats": 1, "not_final": 0, "held": 0, "elected": [
            {"n": "Carryl L. Roy", "p": "D", "k": "sitting", "id": "380001", "s": "carryl-roy-sd-12"}]}}, {})
        hand_new = EP.pages(results, [roy], [], districts, by_hand, "2026-12-10", "2026-12-02", {},
                            roster_term="2027-2028")
        hand_old = EP.pages(results, [roy], [], districts, by_hand, "2026-12-10", "2026-12-02", {},
                            roster_term="2025-2026")
    finally:
        BME.members_elect = real
    slugs = {k: [p["slug"] for p in v[0]] for k, v in runs.items()}
    assert slugs["old roster"] == ["carryl-l-roy-sd-12"] and not runs["old roster"][2], (
        f"numbered while the roster is still the old term's: {slugs['old roster']}, {runs['old roster'][2]}")
    assert slugs["before the day"] == ["carryl-l-roy-sd-12"] and not runs["before the day"][2], (
        "numbered before Organization Day")
    for k in ("new roster", "no term"):
        assert slugs[k] == [] and runs[k][2] == moved, (
            f"with {k}, Carryl L. Roy is not numbered as Roy, Carryl at carryl-roy-sd-12: {slugs[k]}, "
            f"{runs[k][2]}")
    assert hand_new[2] == moved and not hand_new[0], (
        f"a number the owner gave by hand loses the 301 from the provisional address: {hand_new[2]}")
    assert not hand_old[2], f"a number given by hand moves an address before the roster is new: {hand_old[2]}"
    return "ok", ("numbered by the step's own seat rule (a middle initial, a short form, the start of a "
                  "first name; not one letter more, not a namesake's first name), only once the newest "
                  "term is theirs; the provisional address answers with a 301, by the rule and by the "
                  "owner's hand alike")



# A NEW MEMBER-ELECT'S PAGE, FILLED IN (the owner, 16 November 2026: "members elect should have
# pages that are labeled as such with whatever information that is possible to fill out like
# district and whether they have filed any LSRs yet"). A made-up race of each kind the checks below
# need: a House race of four seats with one not final and a recount asked for, two of its winners
# new; a Senate race of one seat, recounted; and the results files they were read from.
_ME_URL = "https://www.sos.nh.gov/2026-general-election-results"
_ME_RESULTS = {"election": "2026-11-03", "term": "2027-2028", "_source": [
    {"file": "records/sources/2026-ge-house-belknap.xlsx", "url": _ME_URL, "saved": "2026-11-05"},
    {"file": "records/sources/2026-ge-house-carroll_1.xlsx", "url": _ME_URL, "saved": "2026-11-13"},
    {"file": "records/sources/2026-ge-state-senate-14-16.xlsx", "url": _ME_URL, "saved": "2026-11-07"},
    {"file": "records/sources/2026-ge-state-senate-17-18.xlsx", "url": _ME_URL, "saved": "2026-11-12"}],
    "races": {
        "H|Belknap|6": {"seats": 4, "floterial": False, "towns": ["Gilford"], "scatter": 3, "candidates": [
            {"name": "Ann Ames", "party": "d", "votes": 3492, "write_in": False, "elected": True},
            {"name": "Bob McLean", "party": "d", "votes": 3436, "write_in": False, "elected": True},
            {"name": "Cy Dow", "party": "r", "votes": 3353, "write_in": False, "elected": True},
            {"name": "Di Eck", "party": "d", "votes": 3283, "write_in": False, "elected": True},
            {"name": "Ed Fay", "party": "r", "votes": 3259, "write_in": False, "elected": False}]},
        "S|15": {"seats": 1, "floterial": False, "towns": ["Concord"], "scatter": 10, "recounted": True,
                 "candidates": [
                     {"name": "Gil Hart", "party": "d", "votes": 9000, "write_in": False, "elected": True},
                     {"name": "Hal Ito", "party": "r", "votes": 6990, "write_in": False, "elected": False}]}}}
# What build_members_elect.members_elect decides of them, stood in for: its own checks hold it.
_ME_RACES = {
    "H|Belknap|6": {"seats": 4, "not_final": 1, "held": 0, "recount": True, "elected": [
        {"n": "Ann Ames", "p": "D", "k": "sitting", "id": "377001", "s": "ann-ames-belk-6", "own": True},
        {"n": "Bob McLean", "p": "D", "k": "new"}, {"n": "Cy Dow", "p": "R", "k": "new"}]},
    "S|15": {"seats": 1, "not_final": 0, "held": 0, "elected": [{"n": "Gil Hart", "p": "D", "k": "new"}]}}
_ME_DISTRICTS = {"Gilford": {"0": {"house": [{"county": "Belknap", "district": 6, "seats": 4}],
                                   "senate": 7}},
                 "Concord": {"0": {"house": [], "senate": 15}}}


@check("build", "a new member-elect's provisional entry carries the race that elected them as a member's "
                "Elections tab has it, the race's seats not final, and the day its own results file was "
                "saved -- the county's House file, or the Senate file that holds the district")
def _elect_pages_result():
    """build_elect_pages.pages gives each page "result", build_member_elections.race_row -- the
    row a member's Elections tab is drawn from -- for the winner as drawn, with "nf", the seats of
    the race not final, where there are any; and "source", the results' address and the day the
    file the race was read from was saved: the county's House file, or the Senate file whose name
    holds the district (2026-ge-state-senate-14-16.xlsx holds 15), not the newest Senate file."""
    import build_elect_pages as EP
    import build_members_elect as BME
    real = BME.members_elect
    BME.members_elect = lambda *a, **k: (json.loads(json.dumps(_ME_RACES)), {})
    try:
        got, _said, _moves = EP.pages(_ME_RESULTS, [], [], _ME_DISTRICTS, {}, "2026-11-20",
                                      "2026-12-02", {})
    finally:
        BME.members_elect = real
    by = {p["slug"]: p for p in got}
    assert set(by) == {"bob-mclean-belk-6", "cy-dow-belk-6", "gil-hart-sd-15"}, (
        f"provisional pages for {sorted(by)}: the three new winners wanted")
    house = {"d": "2026-11-03", "k": "H|Belknap|6", "a": "r-h-belknap-6", "r": "won", "s": 4,
             "rq": 1, "of": 5, "nf": 1}
    want = {"bob-mclean-belk-6": dict(house, v=3436, pl=2), "cy-dow-belk-6": dict(house, v=3353, pl=3),
            # 9,000 of the 15,990 votes and 10 scattered: 56.2 per cent.
            "gil-hart-sd-15": {"d": "2026-11-03", "k": "S|15", "a": "r-s-15", "r": "won", "v": 9000,
                               "s": 1, "rc": 1, "pl": 1, "of": 2, "sh": 56.2}}
    for slug, row in want.items():
        assert by[slug].get("result") == row, (
            f"{slug}'s result is {by[slug].get('result')}, not the race's row {row}")
    saved = {s: (p.get("source") or {}).get("saved") for s, p in by.items()}
    assert saved == {"bob-mclean-belk-6": "2026-11-05", "cy-dow-belk-6": "2026-11-05",
                     "gil-hart-sd-15": "2026-11-07"}, (
        f"the race's own file's day is not the one given: {saved} (Senate District 15 is in the "
        "file of 14 to 16, saved 7 November; the newest Senate file, 17 to 18, was saved the 12th)")
    assert all((p.get("source") or {}).get("url") == _ME_URL for p in got), (
        "a page's source names no address for the results")
    assert not any("id" in p for p in got), "a provisional entry carries an id"
    # And where the results do not hold the person, nothing is made up.
    assert EP.race_result(_ME_RESULTS, "H|Belknap|6", _ME_RACES["H|Belknap|6"], "Nobody Here", {}) is None
    return "ok", ("each new member-elect's entry has the race's row as a member's Elections tab has it "
                  "(2nd of 5, 3,436 votes, a recount asked for and 1 seat not final; a recounted Senate "
                  "seat won with 56.2%) and the day of the race's own file, the Senate's by the "
                  "districts its name holds")


@check("build", "a new member-elect's provisional page is a member's page in the member-elect's form: the "
                "head a returning member-elect's is given, the district's towns, the election's line, "
                "their requests as a member's page lists them or that none is filed yet, the race as "
                "the Elections tab draws it with its seats not final and the source's day; a member "
                "who took office from that day", needs=("build_legislator_pages",))
def _elect_page_member_form(LP):
    """The owner, 16 November 2026: pages "labeled as such with whatever information that is
    possible to fill out like district and whether they have filed any LSRs yet", in the site's own
    components and words. build_legislator_pages.elect_body is held to:

    - the record's head (components.record_head) with the trail ending Member-elect, the name and
      party as the results print them under the member-elect's title spelled out ("Representative
      “Elect” Bob McLean (D)": the owner, 16 November 2026, "use their title as Rep. "Elect"
      Heather Denier instead of just their first name") and the bar in that party's ink -- the head app.js's
      renderMemberHead gives a returning member-elect, compared in node where it is here; the line
      saying what they were elected to and the district's towns, each to its page; the earlier
      service the owner confirmed; Cite this page and Share; no contact detail and no member id;
    - the election's line, and that their seat and record are added as the General Court
      publishes them;
    - the tabs: their requests as a member's page lists them (app.js lsrCardHtml's card, compared
      in node, its number to the request's own page), or "No bill requests filed for 2027 yet.";
      and the race as a member's Elections tab draws it (app.js electionRow, compared in node),
      the seats not final with "a recount was requested", and the source with its day;
    - from the day they take office: Representative or Senator in the trail, a member of the
      chamber, "Took office"."""
    path, base = "/legislator/bob-mclean-belk-6.html", "https://graniterecord.org"
    p = {"slug": "bob-mclean-belk-6", "name": "Bob McLean", "party": "D", "chamber": "H",
         "county": "Belknap", "district": "6", "race": "H|Belknap|6",
         "towns": ["Gilford", "Gilmanton", "Laconia Ward 2"],
         "result": {"d": "2026-11-03", "k": "H|Belknap|6", "a": "r-h-belknap-6", "r": "won", "v": 3436,
                    "s": 4, "rq": 1, "pl": 2, "of": 8, "nf": 1},
         "source": {"url": _ME_URL, "saved": "2026-11-05"}}
    doc = {"election": "2026-11-03", "takes_office": "2026-12-02"}
    meta = {"term": "2027-requests", "label": "2027 Bill Requests", "year": 2027}
    rail = [{"stop": "Requested", "mark": "p", "say": "made"}, {"stop": "Filed", "mark": "-", "say": "not yet"},
            {"stop": "Introduced", "mark": "-", "say": "not yet"}]
    row = {"id": "LSR20270090", "n": "LSR 2027-0090", "year": 2027, "title": "naming a section of Route 3.",
           "sponsor": "Bob McLean", "sponsor_label": "Bob McLean (D)", "sponsor_slug": p["slug"],
           "sponsor_party": "D", "body": "HB", "body_label": "House bill request", "committee": "",
           "committees": [], "topic": "Transportation", "topic_by": "title", "kind": "",
           "status": "Requested", "status_stated": True, "withdrawn": False, "term": "2027-requests",
           "carried": False, "passage": "", "last_action": "", "nrc": 0, "votedays": [], "lsr": True,
           "address": "request/2027-0090", "rail": rail}
    gone = dict(row, id="LSR20270091", n="LSR 2027-0091", status="Withdrawn", withdrawn=True,
                address="request/2027-0091", topic="Miscellaneous")
    places = {"Gilford": "/town/gilford", "Laconia Ward 2": "/town/laconia-ward-2"}
    before = LP.elect_body(p, doc, [row, gone], meta, places, "2026-11-20", path, base)
    none = LP.elect_body(p, doc, [], meta, places, "2026-11-20", path, base)
    after = LP.elect_body(p, doc, [], meta, places, "2026-12-03", path, base)
    sen = dict(p, slug="gil-hart-sd-15", name="Gil Hart", party="R/D", chamber="S", county="",
               district="15", race="S|15", towns=["Concord"], source={"url": _ME_URL, "saved": "2026-11-07"},
               result={"d": "2026-11-03", "k": "S|15", "a": "r-s-15", "r": "won", "v": 9000, "s": 1, "rc": 1,
                       "pl": 1, "of": 2, "sh": 56.2},
               prior={"terms": ["1993-1994", "1995-1996"], "seat": "Hillsborough 1"})
    senate = LP.elect_body(sen, doc, [], meta, {}, "2026-11-20", "/legislator/gil-hart-sd-15.html", base)
    trail = ('<nav class="rtrail" aria-label="Where this page is"><ol><li><a href="officials">Officials</a>'
             '</li><li aria-current="page">{}</li></ol></nav>')
    bad = []
    for what, ok in (
            ("the head is a member's, in the party's ink", '<header class="rhead rh-member rh-pD">' in before),
            ("the trail ends Member-elect", trail.format("Member-elect") in before),
            ("the heading is the member-elect's title and the name and party the results print",
             '<h1 class="rh1">Representative “Elect” Bob McLean (D)</h1>' in before),
            ("the line says what they were elected to, and the district's towns, each to its page",
             '<p class="rline">Member-elect of the New Hampshire House of Representatives, Belknap 6'
             '&nbsp;&middot; <a href="/town/gilford">Gilford</a>, Gilmanton and '
             '<a href="/town/laconia-ward-2">Laconia Ward 2</a></p>' in before),
            ("Cite this page and Share are in the head's actions",
             re.search(r'<div class="racts"><div class="pageacts" id="pageacts"><details class="pcite">'
                       r'.*?Cite this page.*?data-share', before, re.S) is not None),
            ("the election's line", '<p class="elline">Elected November 3, 2026. Takes office December 2, '
                                    '2026.</p>' in before),
            ("the seat and record are said to come as the General Court publishes them",
             "Their seat, committees and record are added here as the General Court publishes them."
             in before),
            ("the requests' tab, counted, and the Elections tab",
             '<button class="tab" role="tab" id="tab_elect_requests" aria-controls="pane_elect_requests" '
             'aria-selected="true" data-t="requests" data-sstab="">2027 Bill Requests<span class="tn">'
             '<span class="tnp"> (</span>2<span class="tnp">)</span></span></button>' in before
             and 'id="tab_elect_elections"' in before
             and 'data-base="/legislator/bob-mclean-belk-6"' in before),
            ("the requests in the member page's words, the withdrawn counted",
             "2 filed for 2027, 1 of them withdrawn.</p>" in before
             and "<b>Requests, not bills yet.</b>" in before),
            ("a request's number goes to its own page",
             '<span class="cnum" translate="no"><a href="request/2027-0090">LSR 2027-0090</a></span>' in before),
            ("none filed is said", '<p class="src">No bill requests filed for 2027 yet.</p>' in none
             and 'class="card' not in none and "Requests, not bills yet" not in none),
            ("the race as the Elections tab draws it",
             '<td class="v" data-l="Result">Elected, 2nd of 8</td>' in before
             and '<td class="o" data-l="Votes">3,436</td>' in before
             and '<a href="/elections/2026-11-03-general#r-h-belknap-6">Nov 3, 2026</a>' in before),
            ("the race's seats not final, and the recount",
             '<p class="elnf"><b>Result not final</b> for the last of the district&rsquo;s 4 seats &mdash; '
             'a recount was requested.</p>' in before),
            ("the source, its address and its day",
             f'read from its <a href="{_ME_URL}" rel="noopener">results file</a> saved November 5, 2026'
             in before),
            ("no contact detail and no member id",
             not any(w in before for w in ("mailto:", "<dt>Email", "GR_MEMBER", "legislators/"))),
            ("from the day they take office, a member who took office",
             trail.format("Representative") in after
             and '<h1 class="rh1">Representative Bob McLean (D)</h1>' in after
             and "Member of the New Hampshire House of Representatives, Belknap 6" in after
             and "Took office December 2, 2026." in after
             and "Member-elect" not in after and "Takes office" not in after),
            ("a Senate member-elect's line, and a cross-nomination on the neutral bar",
             '<header class="rhead rh-member rh-pX">' in senate and '<h1 class="rh1">Senator “Elect” Gil Hart (R/D)</h1>' in senate
             and "Member-elect of the New Hampshire Senate, Senate District 15&nbsp;&middot; Concord" in senate),
            ("a race of one seat gives the share, a recount's count says so",
             "Elected, 1st of 2 <span class=\"dim\">Recounted</span>" in senate
             and '9,000 <span class="dim">(56.2%)</span>' in senate
             and "Result not final" not in senate and "saved November 7, 2026" in senate),
            ("the earlier service the owner confirmed",
             "<dt>Earlier service</dt><dd>Hillsborough 1, 1993–1994, 1995–1996</dd>" in senate)):
        if not ok:
            bad.append(what)
    # THE MEMBER PAGE'S OWN PARTS, where node is here: the row app.js's electionRow draws, the card
    # lsrCardHtml draws (shut, its title the button that opens it, which a page built ahead draws
    # whole), and the head renderMemberHead gives a returning member-elect of the same race.
    ret = {"id": "900009", "name": "McLean, Bob", "chamber": "H", "former": True, "party": "D",
           "display_plain": "Rep. Bob McLean", "display_full": "Rep. Bob McLean (D - Belk 2)",
           "display": "Rep. Bob McLean (D)", "county": "Belknap", "district": "2",
           "slug": "bob-mclean-belk-2", "served": {"terms": ["2017-2018"]}, "attendance": {"2017-2018": {"days": 1}}}
    ge = {"id": "900009", "key": "H|Belknap|6", "election": "2026-11-03", "takes_office": "2999-01-01",
          "mode": "returning", "name": "Bob McLean", "party": "D", "title": "Rep. “Elect”",
          "where": "Member-elect of the New Hampshire House of Representatives, Belknap 6."}
    rows = [p["result"], sen["result"], dict(p["result"], r="open", fl=1, pl=None, of=None),
            {"d": "2024-11-05", "k": "H|Coos|7", "a": "r-h-coos-7", "r": "lost", "v": 12, "s": 2, "pl": 11, "of": 12}]
    js = ("[" + ", ".join(f"scope.electionRow({json.dumps(r)})" for r in rows)
          + f", scope.lsrCardHtml({json.dumps(row)}, ''), scope.lsrCardHtml({json.dumps(gone)}, ''), "
          f"(window.GR_ELECT={json.dumps(ge)}, scope.renderMemberHead({json.dumps(ret)}))]")
    got = _app_js(js, names=("electionRow", "lsrCardHtml", "renderMemberHead"))
    if got is not None:
        flat = lambda s: re.sub(r"\s+", " ", s).strip()
        for r, js_row in zip(rows, got[:4]):
            if flat(LP.election_row_html(r)) != flat(js_row):
                bad.append(f"the race's row is not electionRow's: {LP.election_row_html(r)!r} != {js_row!r}")
        for r, card in zip((row, gone), got[4:6]):
            shut = re.sub(r'<button type="button" class="ctitle" aria-expanded="false" translate="no">'
                          r'(.*?)</button>', r'<div class="ctitle" translate="no">\1</div>', card, flags=re.S)
            shut = re.sub(r'<div class="cbody" hidden>.*</div></article>$', "</article>", shut, flags=re.S)
            if LP.request_card(r) != shut:
                bad.append(f"the request's card is not lsrCardHtml's: {LP.request_card(r)!r} != {shut!r}")
        part = lambda h: tuple((m.group(0) if m else None) for m in (
            re.search(r'<header class="[^"]*">', h), re.search(r'<nav class="rtrail".*?</nav>', h, re.S),
            re.search(r'<div class="rtop">.*?</div>', h, re.S)))
        if part(before) != part(got[6]):
            bad.append(f"the head is not the one renderMemberHead gives a returning member-elect: "
                       f"{part(before)} != {part(got[6])}")
    assert not bad, "; ".join(bad)
    return "ok", ("the page is a member's in the member-elect's form: the head, the towns, the "
                  "election's line, the requests or that none is filed yet, the race with its seats not "
                  "final and the source's day, and a member who took office from the day"
                  + (", its row, cards and head the ones app.js draws" if got is not None
                     else " (node not here: the comparisons with app.js not made)"))


@check("build", "the elections page links a new winner to their provisional page, on the race's card and "
                "the election's map, only for the election the list is of; a member as before, and a "
                "namesake in another race to none", needs=("build_elections", "build_members_elect"))
def _elections_page_provisional(BE, BME):
    """The owner, 16 November 2026: member-elect pages, linked wherever a member-elect's name is
    printed. The elections page drew every new winner unlinked (Kurt Webber of Senate District 2,
    and 169 others, on 16 November), where the Officials tab and the town pages link them. Held:
    provisional() reads site/elect_pages.json under its own election; with_pages gives a new
    winner of that election and race their page's "e" and nobody else -- not a sitting member,
    not a new winner of the same name in another race; chip_slug links a member by id as before,
    a new winner to "e", anyone else to nothing; and on the fixture's election, build_elections.py
    links Pat Newell, new, on his race's card and the map's file, once a list names his page, and
    not where the list is another election's."""
    with tempfile.TemporaryDirectory() as d:
        site = Path(d)
        assert BE.provisional(site) == {}, "with no list, provisional reads one"
        (site / "elect_pages.json").write_text("{", encoding="utf-8")
        assert BE.provisional(site) == {}, "a list that will not read is read"
        (site / "elect_pages.json").write_text(json.dumps({"election": "2026-11-03", "pages": [
            {"slug": "bob-mclean-belk-6", "name": "Bob McLean", "race": "H|Belknap|6"}]}), encoding="utf-8")
        pages = BE.provisional(site)
    assert pages == {"2026-11-03": {("H|Belknap|6", "Bob McLean"): "bob-mclean-belk-6"}}, pages
    races = json.loads(json.dumps(_ME_RACES))
    races["H|Belknap|7"] = {"seats": 1, "not_final": 0, "held": 0, "elected": [
        {"n": "Bob McLean", "p": "R", "k": "new"}]}
    BE.with_pages(races, pages.get("2026-11-03"))
    six = {e["n"]: e for e in races["H|Belknap|6"]["elected"]}
    rows6 = BE.candidate_rows(_ME_RESULTS["races"]["H|Belknap|6"], six)
    rows7 = BE.candidate_rows({"seats": 1, "candidates": [
        {"name": "Bob McLean", "party": "r", "votes": 900, "write_in": False, "elected": True}]},
        {e["n"]: e for e in races["H|Belknap|7"]["elected"]})
    links6 = re.findall(r'href="legislator/([^"]+)"', rows6)
    assert links6 == ["ann-ames-belk-6", "bob-mclean-belk-6"], (
        f"Belknap 6's card links {links6}: the sitting member and the new winner with a page wanted, "
        "and not Cy Dow, who has none")
    assert "href=" not in rows7, "a new winner of the same name in another race is linked to a page"
    base_map = {"layers": {"base": {"f": {"BE6": 1, "BE7": 1}}, "float": {"f": {}},
                           "senate": {"f": {"15": 1}}}}
    who = BE.map_doc(base_map, races, {})["who"]
    assert [x.get("s") for x in who["base|BE6"]] == ["ann-ames-belk-6", "bob-mclean-belk-6", None] \
        and [x.get("s") for x in who["base|BE7"]] == [None], (
        f"the map's people link {who['base|BE6']} and {who['base|BE7']}")
    assert BE.chip_slug({"n": "Odd", "k": "sitting", "e": "x"}) == "" \
        and BE.chip_slug({"n": "Odd", "k": "former", "id": "1", "s": "odd-rock-1"}) == "odd-rock-1", (
        "chip_slug links a member to a provisional page, or a former member to none")
    # THE BUILD, on the fixture's election: Pat Newell, new, linked once a list names his page.
    if _elect_absent():
        return "skip", "not here: " + ", ".join(_elect_absent())
    root = Path(tempfile.mkdtemp(prefix="el_prov_"))
    try:
        site = _elect_fixture(root)
        if not (site / "district_map.json").exists():
            return "skip", "the fixture's build wrote no district_map.json"
        (root / "corrections").mkdir(exist_ok=True)
        (root / "corrections" / "members_elect.json").write_text(json.dumps(_ELECT_HAND), encoding="utf-8")
        got = {}
        for election in ("2026-11-03", "2024-11-05"):
            (site / "elect_pages.json").write_text(json.dumps({"election": election, "pages": [
                {"slug": "pat-newell-rock-32", "name": "Pat Newell", "race": "H|Rockingham|32"}]}),
                encoding="utf-8")
            r = _run([sys.executable, _paths.script("build_elections.py"), "--site", "site"], cwd=root,
                     capture_output=True, text=True, timeout=120, env={"GRANITE_BUILD_DATE": _ELECT_IN})
            assert r.returncode == 0, f"build_elections.py failed: {r.stderr[-600:]}"
            html = (site / "elections" / "2026-11-03-general.html").read_text(encoding="utf-8")
            card = re.search(r'id="' + re.escape(BE.race_id("H|Rockingham|32")) + r'".*?</article>', html, re.S)
            mp = json.loads((site / "elections" / "2026-11-03-map.json").read_text(encoding="utf-8"))
            got[election] = ('href="legislator/pat-newell-rock-32"' in (card.group(0) if card else ""),
                             [x.get("s") for v in mp["who"].values() for x in v if x["n"].startswith("Pat Newell")])
        assert got["2026-11-03"] == (True, ["pat-newell-rock-32"]), (
            f"with the list of his election, Pat Newell's card and map say {got['2026-11-03']}")
        assert got["2024-11-05"] == (False, [None]), (
            f"with a list of another election, Pat Newell is linked: {got['2024-11-05']}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("a new winner with a page is linked on the race's card and the map, a member as "
                  "before, a namesake in another race and a winner with no page not at all; on the "
                  "fixture, Pat Newell is linked by his election's list and not by another's")


@check("build", "members-elect: earlier service is settled by hand in the person's file (\"none\", or "
                "a confirmed record), and the Manuals' rosters clear a doubt a surname alone raises "
                "without ever linking anyone", needs=("build_members_elect",))
def _elect_prior_service(BME):
    """The owner, 13 November 2026 (Zoe Hill, W. Gordon Allen, Tom Stewart).

    - earlier_names reads the Manuals' elected members beside the sponsors: a
      surname printed alone in a term the Manual names the surname's members in
      takes their first names, so a winner of a different first name has no
      doubt; the same full name in the same county is still the doubt; a term
      the Manual marks measuring_only, a row not elected and a surname the
      Manual lacks in the term change nothing;
    - read_hand reads "prior" and refuses an entry that is not "none" or a
      record with terms, a seat and evidence;
    - apply_prior: "none" takes off the doubt (New); a record makes the status
      Returning and carries terms and seat and nothing else (no evidence, no
      employee number), and a name that is no new winner is said."""
    bad = []
    sp = {"1993-1994": {"HB1": [{"name": "Hill", "chamber": "H", "county": "Grafton"},
                                {"name": "Lowe", "chamber": "H", "county": "Grafton"}]}}
    man = {"terms": {
        "1993-1994": {"house": [
            {"county": "Grafton", "district": "1", "name": "Richard L. Hill", "status": "elected"},
            {"county": "Grafton", "district": "2", "name": "Zed Lowe", "status": "lost"},
            {"county": "Grafton", "district": "3", "name": "Anna Pierce", "status": "elected"}],
            "senate": [{"district": "5", "name": "Jon Sloan", "status": "elected"}]},
        "1999-2000": {"measuring_only": True, "house": [
            {"county": "Grafton", "district": "1", "name": "Zoe Hill", "status": "elected"}]}}}
    races = {"H|Grafton|15": {"elected": [{"n": "Zoe Hill", "k": "new"}, {"n": "Rick Hill", "k": "new"},
                                           {"n": "Richard Hill", "k": "new"},
                                           {"n": "Pat Lowe", "k": "new"}, {"n": "Ann Pierce", "k": "new"},
                                           {"n": "Anna Pierce", "k": "new"}]},
             "S|5": {"elected": [{"n": "Jo Sloan", "k": "new"}, {"n": "Jon Sloan", "k": "new"}]}}
    only = BME.earlier_names(sp)
    both = BME.earlier_names(sp, manual=man)
    import copy
    r1, r2 = copy.deepcopy(races), copy.deepcopy(races)
    BME.earlier_service(r1, only)
    BME.earlier_service(r2, both)
    flag = lambda rs: sorted(e["n"] for r in rs.values() for e in r["elected"] if e.get("u"))
    if flag(r1) != ["Pat Lowe", "Richard Hill", "Rick Hill", "Zoe Hill"]:
        bad.append(f"from the bills alone {flag(r1)}: every Hill and Lowe (a surname alone) wanted")
    # Hill: Richard L. is the Manual's -> Zoe cleared, Rick (short form of Richard) and Richard stay;
    # Lowe: the Manual's Lowe lost, so the surname alone stays a doubt; Pierce and Sloan: the
    # Manual's full names are the doubt, a different first name is not.
    if flag(r2) != ["Ann Pierce", "Anna Pierce", "Jon Sloan", "Pat Lowe", "Richard Hill", "Rick Hill"]:
        bad.append(f"with the Manuals {flag(r2)}")
    if ("hill", "H", "grafton") in BME.earlier_names({}, manual={"terms": {
            "1999-2000": man["terms"]["1999-2000"]}}):
        bad.append("a term marked measuring_only is read")
    # The person's file.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "members_elect.json"
        ok = {"2026-11-03": {"prior": {
            "H|Hillsborough|30": {"W. Gordon Allen": {
                "gc_employee_number": "375802", "terms": ["1993-1994", "1995-1996"],
                "seat": "Hillsborough 1", "evidence": ["the Manuals"]}},
            "H|Hillsborough|41": {"Tom Stewart": {"none": True, "evidence": ["not Thomas R. Stewart"]}},
            "H|Grafton|15": {"Zoe Hill": "none"}}}}
        f.write_text(json.dumps(ok), encoding="utf-8")
        hand, _ = BME.read_hand(f, "2026-11-03")
        if set(hand["prior"]) != {"H|Hillsborough|30", "H|Hillsborough|41", "H|Grafton|15"}:
            bad.append(f"read_hand reads prior {hand['prior']}")
        for worse in ({"X": {"Y": {"none": True}}}, {"X": {"Y": {"none": True, "evidence": []}}},
                      {"X": {"Y": {"none": False, "evidence": ["e"]}}},
                      {"X": {"Y": {"terms": ["1993"], "seat": "a", "evidence": ["e"]}}},
                      {"X": {"Y": {"terms": ["1993-1994"], "seat": "a"}}},
                      {"X": {"Y": "maybe"}}, {"X": "none"}):
            f.write_text(json.dumps({"2026-11-03": {"prior": worse}}), encoding="utf-8")
            try:
                BME.read_hand(f, "2026-11-03")
                bad.append(f"read_hand accepts prior {worse}")
            except BME.Refused:
                pass
    rs = {"H|Hillsborough|30": {"elected": [{"n": "W. Gordon Allen", "k": "new", "u": True}]},
          "H|Hillsborough|41": {"elected": [{"n": "Tom Stewart", "k": "new", "u": True}]},
          "H|Grafton|15": {"elected": [{"n": "Zoe Hill", "k": "new", "u": True}]}}
    lost = BME.apply_prior(rs, dict(hand["prior"], **{"H|Nowhere|1": {"Nobody": "none"}}))
    st = {e["n"]: BME.elect_status(e, k, None) for k, r in rs.items() for e in r["elected"]}
    if st != {"W. Gordon Allen": "returning", "Tom Stewart": "new", "Zoe Hill": "new"}:
        bad.append(f"statuses after the person's entries: {st}")
    allen = rs["H|Hillsborough|30"]["elected"][0]
    if allen.get("prior") != {"terms": ["1993-1994", "1995-1996"], "seat": "Hillsborough 1"} \
            or "id" in allen or "s" in allen or "u" in allen or "evidence" in json.dumps(rs) \
            or "375802" in json.dumps(rs):
        bad.append(f"the record carried to the file is {allen}")
    if lost != [("H|Nowhere|1", "Nobody")]:
        bad.append(f"a name that is no new winner is not said: {lost}")
    assert not bad, "; ".join(bad)
    return "ok", ("the Manuals clear a surname alone only for a different first name and never "
                  "link; \"none\" gives New, a confirmed record Returning with terms and seat only")


# A made-up hand file for _officials_successor: every holder and successor
# here is invented. The Governor and a councillor change hands on 7 January,
# a House seat and a Senate seat on 3 January, another councillor is
# re-elected, and a county commissioner and a sheriff change hands too.
_SUCCESSOR_DAY = "2027-01-07"
_SUCCESSOR_FILE = {
    "_checked": "2026-11-20",
    "governor": {"office": "Governor of New Hampshire", "scope": "statewide",
                 "about": ["Signs or vetoes legislation."], "name": "Ann Before", "party": "R",
                 "phone": "(603) 555-0101", "email": "ann@gov.example.org",
                 "official_url": "https://gov.example.org/",
                 "contact_url": "https://gov.example.org/contact-ann",
                 "source": "https://gov.example.org/",
                 "elect": {"name": "Bea After", "party": "D", "official_url": "https://gov.example.org/",
                           "source": "https://sos.example.org/results", "read": "2026-11-20",
                           "takes_office": _SUCCESSOR_DAY}},
    "council": {"office": "Executive Council", "scope": "district", "about": ["Five councilors."],
                "official_url": "https://council.example.org/",
                "source": "https://council.example.org/",
                "districts": {
                    "1": {"name": "Cal Before", "party": "R", "phone": "(603) 555-0104",
                          "official_url": "https://council.example.org/district-1",
                          "elect": {"name": "Dee After", "party": "D",
                                    "official_url": "https://council.example.org/district-1",
                                    "source": "https://sos.example.org/results",
                                    "takes_office": _SUCCESSOR_DAY}},
                    "2": {"name": "Eve Again", "party": "D", "phone": "",
                          "official_url": "https://council.example.org/district-2",
                          "elect": {"name": "Eve Again", "party": "D",
                                    "official_url": "https://council.example.org/district-2",
                                    "source": "https://sos.example.org/results",
                                    "takes_office": _SUCCESSOR_DAY}}}},
    "us_house": {"office": "United States House of Representatives", "scope": "district",
                 "about": ["Two members."], "official_url": "https://house.example.org/",
                 "source": "https://house.example.org/",
                 "districts": {"1": {"name": "Fay Before", "party": "D", "phone": "(603) 555-0102",
                                     "phone_dc": "(202) 555-0102",
                                     "official_url": "https://fay.house.example.org",
                                     "elect": {"name": "Gus After", "party": "R",
                                               "official_url": "https://gus.house.example.org",
                                               "source": "https://sos.example.org/results",
                                               "takes_office": "2027-01-03"}}}},
    "us_senate": {"office": "United States Senate", "scope": "statewide",
                  "about": ["Two senators."], "official_url": "https://senate.example.org/",
                  "source": "https://senate.example.org/",
                  "seats": [{"name": "Hal Stays", "party": "D", "phone": "(603) 555-0105"},
                            {"name": "Ida Before", "party": "D", "phone": "(603) 555-0103",
                             "official_url": "https://ida.senate.example.org",
                             "elect": {"name": "Jo After", "party": "R",
                                       "source": "https://sos.example.org/results",
                                       "takes_office": "2027-01-03"}}]},
    "county": {"office": "County Officers", "scope": "county", "about": ["Ten counties."],
               "counties": {"Belknap": {
                   "name": "Belknap County", "official_url": "",
                   "commissioners": {"1": {
                       "name": "Kit Before", "office": "County Commissioner, District 1",
                       "district": "1", "party": "R", "phone": "(603) 555-0106", "source": "a roster",
                       "elect": {"name": "Lu After", "party": "D", "source": "the next roster",
                                 "takes_office": _SUCCESSOR_DAY}}},
                   "sheriff": {"name": "Mo Before", "office": "Sheriff", "phone": "",
                               "source": "a roster",
                               "elect": {"name": "Ned After", "party": "R",
                                         "source": "the next roster",
                                         "takes_office": _SUCCESSOR_DAY}}}}},
}


@check("frontend", "a successor in corrections/officials.json is the holder from the day they take "
                   "office and not before, on every page that draws the office",
       needs=("build_members_elect", "officials_tabs", "build_town_pages", "build_district_map"))
def _officials_successor(BME, OT, BT, BDM):
    """The person's approval of 23 October 2026: a record of the hand file
    may name its successor under "elect", with the day they take office, and
    from that day, by the build's own day, every page draws them as the
    holder, so nobody has to edit the file on the day.

    On a made-up file (_SUCCESSOR_FILE) in a folder of its own, read as the
    pages read it (build_members_elect.read_officials): the day before, each
    record is the file's, its successor beside it, and the Officials page's
    tabs say under the holder who takes the office and when -- the party
    only where the holder's is drawn, nothing beside a holder re-elected,
    and data-until, for a page read on the day; each record by its own day,
    so Congress turns on 3 January and the Governor later; from the day,
    the successor is the holder on the Executive Branch, Federal Delegation
    and County Officials tabs, on a town page's Representatives tab and in
    the district map's seats, with nothing of the predecessor's carried over
    and what the record says of the office kept; and the file is not
    written. A successor with no name, no day, or a successor of its own
    stops the reader, before its day too. And the real file's successors
    still to take office, where it names any, each name the page they were
    read from, and an official_url where their record has one."""
    import datetime as _dt
    import html as _html
    import build_date
    root = Path(tempfile.mkdtemp(prefix="gr-officials-"))
    try:
        f = root / "officials.json"
        f.write_text(json.dumps(_SUCCESSOR_FILE), encoding="utf-8")
        raw = f.read_bytes()
        # The day before Congress turns, the day before the Governor does,
        # the Governor's day, and long after.
        before, mid = _officials_now(f, "2027-01-02"), _officials_now(f, "2027-01-06")
        on, after = _officials_now(f, _SUCCESSOR_DAY), _officials_now(f, _dt.date(2027, 6, 1))
        assert f.read_bytes() == raw, "reading the hand file changed it"
        assert _officials_now(f) == _officials_now(f, build_date.today()), (
            "the reader's day is not the build's")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    snap = json.dumps(_SUCCESSOR_FILE, sort_keys=True)
    BME.officials_on(_SUCCESSOR_FILE, _SUCCESSOR_DAY)
    assert json.dumps(_SUCCESSOR_FILE, sort_keys=True) == snap, "officials_on changed the file it read"

    # The records, by the day.
    g = before["governor"]
    assert g["name"] == "Ann Before" and g["elect"]["name"] == "Bea After", (
        f"the day before, the Governor is {g.get('name')!r}")
    assert mid["us_house"]["districts"]["1"]["name"] == "Gus After" and \
        mid["us_senate"]["seats"][1]["name"] == "Jo After" and mid["governor"]["name"] == "Ann Before", (
            "each record does not turn on its own day: Congress on 3 January, the Governor on 7")
    assert before["us_house"]["districts"]["1"]["name"] == "Fay Before", (
        "the day before Congress turns, its successor is already the holder")
    want = {"office": "Governor of New Hampshire", "scope": "statewide",
            "about": ["Signs or vetoes legislation."], "name": "Bea After", "party": "D",
            "official_url": "https://gov.example.org/", "source": "https://sos.example.org/results",
            "read": "2026-11-20"}
    assert on["governor"] == want, (
        f"on the day the Governor's record is {on['governor']}, not the successor's own fields "
        "over the office's")
    assert after == on, "a successor whose day has passed is not simply the holder"
    c1, c2 = on["council"]["districts"]["1"], on["council"]["districts"]["2"]
    assert c1["name"] == "Dee After" and "phone" not in c1 and "elect" not in c1, c1
    assert c2["name"] == "Eve Again" and "elect" not in c2, c2
    h = on["us_house"]["districts"]["1"]
    assert (h["name"], h["official_url"]) == ("Gus After", "https://gus.house.example.org") \
        and "phone" not in h and "phone_dc" not in h, f"the predecessor's ways to reach them carried over: {h}"
    s = on["us_senate"]["seats"]
    assert s[0]["name"] == "Hal Stays" and s[1] == {"name": "Jo After", "party": "R",
                                                    "source": "https://sos.example.org/results"}, s
    k = on["county"]["counties"]["Belknap"]
    assert (k["commissioners"]["1"]["name"], k["commissioners"]["1"]["office"],
            k["commissioners"]["1"]["district"]) == ("Lu After", "County Commissioner, District 1", "1"), (
        "a commissioner's successor did not keep the office's own fields")

    # The Officials page's tabs.
    line = '<span class="ofseat" data-until="{d}">{n} takes office {w}.</span>'
    ex_b, ex_o = OT.executive(mid), OT.executive(on)
    assert "Gus After (R) takes office" not in OT.federal(mid), (
        "a successor already in office is still said to take it")
    for n, d, w in (("Bea After (D)", _SUCCESSOR_DAY, "January 7, 2027"),
                    ("Dee After (D)", _SUCCESSOR_DAY, "January 7, 2027")):
        assert line.format(n=n, d=d, w=w) in ex_b, f"the day before, Executive Branch does not say {n} takes office"
    assert "Ann Before" in ex_b and "Eve Again (D) takes office" not in ex_b, (
        "the holder is not drawn, or a holder re-elected is said to take office again")
    assert "Bea After" in ex_o and "Ann Before" not in ex_o and "takes office" not in ex_o and \
        "Cal Before" not in ex_o, "on the day, Executive Branch still draws a predecessor or a successor's line"
    fed_b, fed_o = OT.federal(before), OT.federal(on)
    assert line.format(n="Gus After (R)", d="2027-01-03", w="January 3, 2027") in fed_b and \
        line.format(n="Jo After (R)", d="2027-01-03", w="January 3, 2027") in fed_b, (
            "the day before, Federal Delegation does not say who takes the seats")
    assert "Gus After" in fed_o and "Fay Before" not in fed_o and "555-0102" not in fed_o and \
        "Ida Before" not in fed_o, "on the day, Federal Delegation still draws a predecessor"
    co_b, co_o = OT.county(before, [], "2027-01-02"), OT.county(on, [], _SUCCESSOR_DAY)
    assert line.format(n="Lu After (D)", d=_SUCCESSOR_DAY, w="January 7, 2027") in co_b and \
        line.format(n="Ned After", d=_SUCCESSOR_DAY, w="January 7, 2027") in co_b, (
            "the county's successors are not said, or a sheriff's carries a party")
    assert '<span class="mchip p-X" translate="no">Ned After</span>' in co_o and "Mo Before" not in co_o, (
        "on the day the sheriff is not the successor, on the neutral chip")

    # A town page's Representatives tab, and the district map's seats.
    dist = {"council": 1, "congress": 1, "house": []}
    tp_b, tp_o = ("".join(BT.representatives_sections(dist, [], d)) for d in (before, on))
    for old, new in (("Ann Before", "Bea After"), ("Cal Before", "Dee After"),
                     ("Fay Before", "Gus After"), ("Ida Before", "Jo After")):
        assert _html.escape(old) in tp_b and new not in tp_b, f"the day before, a town page lacks {old}"
        assert _html.escape(new) in tp_o and old not in tp_o, f"on the day, a town page lacks {new}"
    for d, ec, cd in ((before, ("Cal Before", "R"), ("Fay Before", "D")),
                      (on, ("Dee After", "D"), ("Gus After", "R"))):
        w = BDM.who_sits([], d, {})
        got = ((w["exec|1"][0]["n"], w["exec|1"][0]["p"]), (w["cong|1"][0]["n"], w["cong|1"][0]["p"]))
        assert got == (ec, cd), f"the map's seats are {got}, not {(ec, cd)}"

    # A successor that will not read stops the reader, before its day too.
    for bad, said in (({"party": "D", "takes_office": _SUCCESSOR_DAY}, "names nobody"),
                      ("Bea After", "names nobody"),
                      ({"name": "X"}, "no day"), ({"name": "X", "takes_office": "2027-1-7"}, "YYYY-MM-DD"),
                      ({"name": "X", "takes_office": "2027-02-30"}, "YYYY-MM-DD"),
                      ({"name": "X", "takes_office": _SUCCESSOR_DAY,
                        "elect": {"name": "Y", "takes_office": "2029-01-04"}}, "of its own")):
        try:
            BME.officials_on({"governor": {"name": "Ann Before", "elect": bad}}, "2026-12-01")
        except SystemExit as e:
            assert said in str(e) and "governor" in str(e), f"{bad!r} stops the reader saying {e}"
        else:
            raise AssertionError(f"a successor {bad!r} does not stop the reader")

    # The real file's successors still to come each name their page, and
    # an address where their record has one: nothing of the holder's is
    # carried over, so one left out would be missing from the day they
    # take office, and this says so before it.
    pending = []

    def walk(x, where):
        if isinstance(x, dict):
            if isinstance(x.get("elect"), dict):
                pending.append((where, x, x["elect"]))
            for key, v in x.items():
                walk(v, f"{where}.{key}" if where else key)
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{where}[{i}]")
    walk(_officials_now(), "")
    unsourced = [w for w, _r, e in pending if not str(e.get("source") or "").strip()]
    assert not unsourced, ("corrections/officials.json names a successor without the page it was "
                           "read from: " + ", ".join(unsourced))
    unaddressed = [w for w, r, e in pending if str(r.get("official_url") or "").strip()
                   and not str(e.get("official_url") or "").strip()]
    assert not unaddressed, ("corrections/officials.json names a successor with no official_url "
                             "where the holder's record has one, and none is carried over: "
                             + ", ".join(unaddressed))
    return "ok", ("on a made-up file, each successor the holder from their own day and not the "
                  "day before, on the Officials tabs, a town page and the map, with nothing of the "
                  "predecessor's carried over; one line before the day; a successor with no name or "
                  f"day refused; the real file names {len(pending)} successor(s) to come, each "
                  "with its source and address")


@check("frontend", "an empty seat in corrections/officials.json is drawn Vacant, with its day, its source "
                   "and who takes it next, in English and Spanish, until its successor's day",
       needs=("build_members_elect", "officials_tabs"))
def _officials_vacant_seat(BME, OT):
    """The owner's word through the manager session, 5 November 2026: a
    Strafford County commissioner resigned mid-term, and a record with no
    name drew nothing, so the county showed two commissioners and said
    nothing of the third. A record whose name is empty and which says
    "vacant", with its day and its source, is a dashed Vacant chip with the
    seat, "Vacant since <day>.", the source and the successor's line --
    the party where the office is drawn with one, none for a sheriff. A
    record with no name and no "vacant" still draws nothing, as before. A
    vacancy with no source, or no day, stops the build. From the successor's
    day (build_members_elect.officials_on) they are the holder and nothing
    says vacant. And every vacancy the real file names draws."""
    import datetime as _dt
    import html as _html
    src = "https://www.co.example.nh.us/notice"
    seat2 = {"name": "", "office": "County Commissioner, District 2", "district": "2", "party": "",
             "vacant": {"since": "2026-10-30", "source": src, "read": "2026-11-06"},
             "elect": {"name": "Bea After", "party": "D", "source": "https://sos.example.org/results",
                       "takes_office": "2027-01-06"}}
    doc = {"county": {"counties": {"Strafford": {
        "name": "Strafford County",
        "commissioners": {"1": {"name": "Ann Holder", "office": "County Commissioner, District 1",
                                "district": "1", "party": "R"},
                          "2": seat2,
                          "3": {"name": "", "office": "County Commissioner, District 3", "district": "3"}},
        "sheriff": {"name": "", "office": "Sheriff",
                    "vacant": {"since": "2026-10-01", "source": src, "read": "2026-11-06"},
                    "elect": {"name": "Cy After", "party": "R", "source": "https://sos.example.org/results",
                              "takes_office": "2027-01-06"}}}}}}
    snap = json.dumps(doc, sort_keys=True)

    def tab(d, lang="en"):
        return OT.county(d, [], _dt.date(2026, 11, 20), lang)

    def plain(h):
        return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()
    bad = []
    en = tab(BME.officials_on(doc, "2026-11-20"))
    rows = re.findall(r'<li class="ofwho ofvac">(.*?)</li></ul>(.*?)</li>', en, re.S)
    if len(rows) != 2:
        bad.append(f"two vacancies draw {len(rows)} Vacant rows")
    t = plain(en)
    for want in ("Vacant Commissioner, District 2 Vacant since October 30, 2026.",
                 "Source: co.example.nh.us", "Bea After (D) takes office January 6, 2027.",
                 "Vacant Sheriff Vacant since October 1, 2026.", "Cy After takes office January 6, 2027."):
        if want not in t:
            bad.append(f"the County Officials tab does not say {want!r}")
    if "Cy After (R)" in t:
        bad.append("a sheriff's successor is drawn with a party")
    if "District 3" in t:
        bad.append("a record with no name and no vacancy draws a row")
    if 'class="ofvacant"' not in en or "Ann Holder" not in t:
        bad.append("the Vacant box, or the holder beside it, is missing")
    if re.search(r'class="mchip[^"]*"[^>]*>(?:Vacant|Vacante)<', en):
        bad.append("an empty seat is drawn as a person's chip")
    es = plain(tab(BME.officials_on(doc, "2026-11-20"), "es"))
    if "Vacante desde el 30 de octubre de 2026." not in es or "Vacante" not in es:
        bad.append("the Spanish tab does not say Vacante desde el 30 de octubre de 2026.")
    on = plain(tab(BME.officials_on(doc, "2027-01-06")))
    if "Vacant" in on or "Bea After" not in on or "Cy After" not in on:
        bad.append("on the successors' day the seats still say Vacant, or the successors are not the holders")
    for broken, said in (({"since": "2026-10-30"}, "no source"), ({"source": src}, "YYYY-MM-DD"),
                         ({"since": "2026-02-30", "source": src}, "YYYY-MM-DD")):
        try:
            OT.vacant({"name": "", "office": "Sheriff", "vacant": broken})
        except SystemExit as e:
            if said not in str(e):
                bad.append(f"a vacancy {broken!r} stops the build saying {e}")
        else:
            bad.append(f"a vacancy {broken!r} does not stop the build")
    if json.dumps(doc, sort_keys=True) != snap:
        bad.append("drawing the tab changed the file it read")
    css = _source("src/pages/app.css")
    if not re.search(r"\.ofvacant\{[^}]*border:1px dashed", css):
        bad.append("the Vacant box is not dashed")
    # The real file's vacancies, if it names any, each draw.
    real, n = _officials_now(), 0
    for c in ((real.get("county") or {}).get("counties") or {}).values():
        for r in [*((c or {}).get("commissioners") or {}).values(),
                  *[(c or {}).get(k) or {} for k, _t in OT.COUNTY_OFFICES]]:
            if isinstance((r or {}).get("vacant"), dict) and not (r.get("name") or "").strip():
                n += 1
                try:
                    OT.vacant(r)
                except SystemExit as e:
                    bad.append(str(e))
    assert not bad, "; ".join(bad[:6])
    return "ok", ("on a made-up county, an empty seat drawn Vacant with its day, source and successor, "
                  "a sheriff's successor with no party, in English and Spanish, the holder on the "
                  f"successor's day, a vacancy with no source or day refused; the real file names {n}")


@check("files", "corrections/officials.json has one reader, build_members_elect.read_officials, "
                "and nothing reads the retired corrections/status/officials.txt",
       needs=("build_members_elect", "build_pages", "build_site_v2"))
def _officials_one_reader(BME, BP, B):
    """The person's approval of 23 October 2026. Every page that names who
    holds an office of the hand file reads the file through one function,
    build_members_elect.read_officials, which puts a successor in office on
    their day -- so no page can show a holder another page has replaced.
    Read off the code of every code folder, preflight aside (it lays the
    file out in its fixtures, and reads it through _officials_now): no
    string but read_officials' own module's names the file as a path, and
    none takes that module's OFFICIALS or officials_on to read it another
    way; and the Officials page, the town pages, the district map and the
    officers' hand entries each call read_officials.

    AND THE SECOND COPY IS GONE. corrections/status/officials.txt held the
    Governor and the Council a second time, for a home page block that never
    drew because the file was never filled in; the person retired it the same
    day. It is not there, no code or kit list names it, build_site_v2 takes
    no --officials and writes no Council or Governor into home.json's
    composition, and the home page's script draws neither."""
    import ast
    import inspect
    import types
    path_name = re.compile(r"^(?:corrections[/\\])?officials\.json$")
    retired = "officials" + ".txt"
    named, other_way, txt = [], [], []
    calls, imported = {}, set()
    for f in _paths.code_files("*.py"):
        if _in_suite(f):
            continue
        tree = _parsed(f)
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and n.body and isinstance(n.body[0], ast.Expr)
                and isinstance(n.body[0].value, ast.Constant) and isinstance(n.body[0].value.value, str)}
        mine = f.name == "build_members_elect.py"
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs:
                if path_name.match(n.value.strip()) and not mine:
                    named.append(f"{f.name}:{n.lineno}")
                if retired in n.value:
                    txt.append(f"{f.name}:{n.lineno}")
            elif not mine and isinstance(n, ast.ImportFrom) and n.module == "build_members_elect":
                if any(a.name in ("OFFICIALS", "officials_on") for a in n.names):
                    other_way.append(f"{f.name}:{n.lineno}")
                if any(a.name == "read_officials" for a in n.names):
                    imported.add(f.name)
            elif not mine and isinstance(n, ast.Attribute) and n.attr in ("OFFICIALS", "officials_on"):
                other_way.append(f"{f.name}:{n.lineno}")
            elif isinstance(n, ast.Call) and (getattr(n.func, "id", None) == "read_officials"
                                              or getattr(n.func, "attr", None) == "read_officials"):
                calls[f.name] = calls.get(f.name, 0) + 1
    assert not named, ("corrections/officials.json is named as a path outside its one reader, "
                       "build_members_elect.read_officials: " + ", ".join(named))
    assert not other_way, ("the hand file is read around read_officials, through its module's "
                           "OFFICIALS or officials_on: " + ", ".join(other_way))
    readers = ("build_pages.py", "build_town_pages.py", "build_district_map.py", "officers.py")
    # Called, and the module's own: src/towns/build_places.py has a
    # read_officials of its own, for the towns' officials.
    missing = [r for r in readers if not calls.get(r) or r not in imported]
    assert not missing, f"these no longer read the hand file through read_officials: {missing}"
    own = "\n".join(_source(f) for f in _suite_files())
    assert ('Path("corrections/' + 'officials.json").read_text') not in own, (
        "preflight reads the hand file itself, where a page reads it through read_officials")
    # The retired file.
    assert not Path("corrections/status/" + retired).exists(), (
        f"corrections/status/{retired} is back: the person retired it on 23 October 2026")
    assert not txt, f"code names the retired corrections/status/{retired}: " + ", ".join(txt)
    for f in ("cloud_kit.json", "build_all.py", "nightly.py"):
        if Path(f).exists():
            assert retired not in Path(f).read_text(encoding="utf-8"), f"{f} names {retired}"
    assert '"--officials"' not in inspect.getsource(B.parse_args), (
        "build_site_v2 still takes --officials")
    comp, _vac = B.build_composition(types.SimpleNamespace(districts=str(Path(
        tempfile.gettempdir()) / "gr-no-such-districts.json")), {})
    assert set(comp) == {"H", "S", "vacancies"}, (
        f"home.json's composition carries {sorted(set(comp) - {'H', 'S', 'vacancies'})} besides the chambers")
    for gone in ("C.council", "C.governor", 'getElementById("composition")', "Who holds office</h2>"):
        assert gone not in BP.HOME_JS, f"the home page's script still draws {gone!r}"
    assert 'id="composition"' not in _source(BP.__file__), (
        "the home page still writes the composition block's empty box")
    return "ok", (f"{len(readers)} readers of the hand file, each through read_officials, and no "
                  f"other path to it; corrections/status/{retired} gone, named nowhere, and the "
                  "home page's Council and Governor with it")


@check("files", "the officials are due a reading a week after each general election, and the "
                "reminder says so on those days and on no others",
       needs=("build_members_elect", "legislative_year"))
def _officials_recheck_rule(BME, LY):
    """The person's approval of 23 October 2026: after a general election
    the hand file's names may be a term out of date and nothing else says
    so. build_members_elect.recheck_due is the rule _officials_rechecked
    holds the real file to, as one of the REMINDERS that warn on the night
    and never hold it: quiet until a week after the vote (RECHECK_AFTER);
    from then, due while _checked is dated before that week was out, is no
    day, or is after today -- a date to come is a way to silence it early.
    Run on fixed days here, the code half, so a rule that could never fire
    fails now rather than passing quietly through the day it was written
    for; the general election by its rule, the Tuesday after the first
    Monday of November in an even year."""
    import datetime as _dt
    D = _dt.date
    assert BME.last_general_election(D(2026, 11, 4)) == D(2026, 11, 3) and \
        BME.last_general_election(D(2026, 11, 3)) == D(2024, 11, 5), (
            "the last general election before 4 November 2026 is not the 3rd, or before the 3rd "
            "not 5 November 2024")
    # One rule in two modules, which must not part: the schedule page's
    # (legislative_year, a page builder) and this one's, in src/parse/,
    # which a page builder may import and not the other way round.
    parted = [y for y in range(2024, 2052, 2) if BME.general_election(y) != LY.general_election(y)]
    assert not parted, f"build_members_elect and legislative_year date the general election of {parted} apart"
    e28 = BME.general_election(2028)
    for day, checked, due in (
            (D(2026, 10, 23), "2026-09-09", False),       # the 2024 vote's week long past
            (D(2026, 10, 23), "2024-11-11", True),        # read in 2024's week of the count
            (D(2026, 11, 3), "2026-09-09", False),        # election day
            (D(2026, 11, 9), "2026-09-09", False),        # the count's week: nothing asked
            (D(2026, 11, 10), "2026-09-09", True),        # a week on: due
            (D(2026, 11, 10), "2026-11-10", False),       # read that day
            (D(2026, 11, 12), "2026-11-05", True),        # read in the count's week
            (D(2026, 11, 12), "2026-11-11", False),
            (D(2027, 6, 1), "2026-11-10", False),
            (D(2027, 6, 1), "2026-09-09", True),
            (D(2026, 11, 12), "2026-11-20", True),        # a date to come
            (D(2026, 11, 12), "soon", True), (D(2026, 11, 12), "", True),
            (D(2026, 11, 12), None, True),
            (e28 + _dt.timedelta(days=6), "2026-11-10", False),
            (e28 + _dt.timedelta(days=7), "2026-11-10", True)):
        said = BME.recheck_due(checked, day)
        assert bool(said) == due, (f"on {day} with _checked {checked!r} the reminder "
                                   + (f"fires ({said[:90]})" if said else "stays quiet")
                                   + (", and should not" if said else ", and should fire"))
    said = BME.recheck_due("2026-09-09", D(2026, 11, 10))
    assert "November 3, 2026" in said and "November 10, 2026" in said and '"elect"' in said, said
    assert "after today" in BME.recheck_due("2026-11-20", D(2026, 11, 12))
    assert "_officials_rechecked" in REMINDERS, (
        "_officials_rechecked is not among the REMINDERS, which warn on the night and never hold it")
    return "ok", ("quiet until a week after each general election, then due until _checked is "
                  "on or after that day; a date to come or no date is due too")


@check("data", "the officials in corrections/officials.json are read again once a general "
               "election has had a week", needs=("build_members_elect",))
def _officials_rechecked(BME):
    """A REMINDER, the register of probate paragraph's kind
    (_probate_after_the_vote), on the rule _officials_recheck_rule holds:
    from a week after a general election, the hand file's _checked must be a
    day on or after that week's end. A data check and one of the REMINDERS:
    on the night it warns, on its own Healthchecks check, and never holds
    the site, because a list to read again is no reason to stop it; and on
    the laptop it is read by the first session after it fires."""
    import build_date
    checked = _officials_now().get("_checked")
    today = build_date.today()
    said = BME.recheck_due(checked, today)
    assert not said, said
    year = today.year - today.year % 2
    nxt = next(BME.general_election(y) + BME.RECHECK_AFTER for y in (year, year + 2)
               if BME.general_election(y) + BME.RECHECK_AFTER > today)
    return "ok", (f"_checked is {checked}; this fails from {nxt}, a week after the next general "
                  "election, until the offices are read again")


@check("build", "the elections page shows every count as the results file has it, Elected only "
       "where the members-elect rule says a seat is final, a link only where that rule links, "
       "no private reason, no word of a projection, and a printed total the towns contradict "
       "said so", needs=("build_elections", "build_members_elect"))
def _elections_page(BE, BME):
    """src/pages/build_elections.py (the owner's word of 7 November 2026:
    official results only). On a copy of the fixture with its made-up
    election (tests/election_fixture.json: a tie, a write-in winner, a
    cross-nomination, a recount asked for, a held winner) and the person's
    file the members-elect checks use:

    - every candidate's count on the page is the results file's, race by race;
    - "Elected" marks exactly the winners build_members_elect.members_elect
      returns, on the build's day -- none before the recount deadline, the
      tie's two never, Danville's not while its recount is asked for (which
      reads "Result not final -- a recount was requested"), the held winner
      never;
    - a candidate links to a member page only where that function gave an
      id and a slug;
    - the person's private reasons are nowhere in what was written;
    - no projection, call or "leading" is on the page;
    - the pages are in the sitemap;
    - and a Totals note of the reader's (Grafton 9, 2026) puts the printed
      total and the towns' sum on its race's card."""
    if _elect_absent():
        return "skip", "not here: " + ", ".join(_elect_absent())
    root = Path(tempfile.mkdtemp(prefix="el_"))
    try:
        site = _elect_fixture(root)
        res = json.loads((root / "collected" / "election_2026.json").read_text(encoding="utf-8"))
        (root / "corrections").mkdir(exist_ok=True)
        hand_p = root / "corrections" / "members_elect.json"
        legs = json.loads((site / "legislators.json").read_text(encoding="utf-8"))
        former = json.loads((site / "former.json").read_text(encoding="utf-8"))
        dist = json.loads((site / "districts.json").read_text(encoding="utf-8"))
        if not (site / "district_map.json").exists():
            return "skip", "the fixture's build wrote no district_map.json"
        for day, hand in ((_ELECT_IN, _ELECT_HAND), ("2026-11-10", _ELECT_HAND)):
            hand_p.write_text(json.dumps(hand), encoding="utf-8")
            r = _run([sys.executable, _paths.script("build_elections.py"), "--site", "site"],
                     cwd=root, capture_output=True, text=True, timeout=120,
                     env={"GRANITE_BUILD_DATE": day})
            assert r.returncode == 0, f"build_elections.py failed on {day}: {r.stderr[-600:]}"
            page = site / "elections" / "2026-11-03-general.html"
            assert page.exists() and (site / "elections" / "index.html").exists() and \
                (site / "elections" / "2026-11-03-map.json").exists(), (
                    f"build_elections wrote {sorted(p.name for p in (site / 'elections').glob('*'))}")
            html = page.read_text(encoding="utf-8")
            want, _rep = BME.members_elect(res, legs, former, dist,
                                           BME.read_hand(hand_p, "2026-11-03")[0], day)
            for key, race in res["races"].items():
                m = re.search(r'<article class="er-race" id="' + re.escape(BE.race_id(key))
                              + r'".*?</article>', html, re.S)
                assert m, f"{day}: no card for {key}"
                card = m.group(0)
                rows = re.findall(r'<li class="er-row">(.*?)</li>', card, re.S)
                got = {}
                for row in rows:
                    name = re.sub(r"<[^>]+>", "", row.split('<span class="er-n">')[0])
                    name = re.sub(r"\s*\([A-Z/]*\)\s*|\s*write-in\s*|\s*Elected\s*|\s*Tied for the last seat\s*",
                                  " ", name).strip()
                    n = int(re.search(r'<span class="er-n">([\d,]+)', row).group(1).replace(",", ""))
                    got[name] = (n, "Elected</span>" in row, re.search(r'href="legislator/([^"]+?)(?:\.html)?"', row))
                held = set((hand["2026-11-03"].get("held") or {}).get(key) or {})
                assert {k: v[0] for k, v in got.items()} == {c["name"]: c["votes"] for c in race["candidates"]
                                                             if c["name"] not in held}, (
                    f"{day}, {key}: the page's counts {got} are not the results file's, less any held winner")
                elected = {e["n"]: e for e in want[key]["elected"]}
                assert {BME.reading_order(k) for k, v in got.items() if v[1]} == set(elected), (
                    f"{day}, {key}: Elected on {sorted(k for k, v in got.items() if v[1])}; the "
                    f"members-elect rule says {sorted(elected)}")
                for k, v in got.items():
                    e = elected.get(BME.reading_order(k))
                    should = e["s"] if e and e.get("id") and e.get("s") else None
                    assert (v[2].group(1) if v[2] else None) == should, (
                        f"{day}, {key}: {k} links to {v[2] and v[2].group(1)}; the rule says {should}")
            if day == "2026-11-10":
                assert "Elected</span>" not in html, (
                    "before the recount deadline a race reads Elected though none was recounted")
            else:
                dan = re.search(r'id="' + BE.race_id("H|Rockingham|8") + r'".*?</article>', html, re.S).group(0)
                assert "Result not final" in dan and "a recount was requested" in dan, (
                    "Danville's race, its recount asked for, does not say so")
                # A held winner's name and count are not drawn anywhere: they would say who won.
                for p in (site / "elections").iterdir():
                    assert "Sam Wright" not in p.read_text(encoding="utf-8"), (
                        f"the held winner is named on {p.name}")
                # The tie: both marked so, no seat to either, and Closest Races says tied.
                tie = re.search(r'id="' + BE.race_id("S|23") + r'".*?</article>', html, re.S).group(0)
                assert tie.count("Tied for the last seat") == 2 and "Elected</span>" not in tie, (
                    "Senate 23's tie is not drawn as a tie")
                assert "tied for the last seat" in html, "Closest Races does not say Senate 23 is tied"
                # A cross-nominated winner fills the map with both parties, never one.
                mp = json.loads((site / "elections" / "2026-11-03-map.json").read_text(encoding="utf-8"))
                assert mp["fill"]["float"].get("RO32") == "RD", (
                    f"Pat Newell (r/d) fills Rockingham 32 as {mp['fill']['float'].get('RO32')!r}")
                # Each chamber's bar adds up to its seats.
                for name, keys in (("Senate", [k for k in res["races"] if k.startswith("S|")]),
                                   ("House", [k for k in res["races"] if k.startswith("H|")])):
                    lab = re.search(r'aria-label="State ' + name + r': ([^"]*)"', html).group(1)
                    total = sum(int(x) for x in re.findall(r"(\d+) ", lab))
                    assert total == sum(want[k]["seats"] for k in keys), (
                        f"the State {name} bar says {lab!r}, which is not its {sum(want[k]['seats'] for k in keys)} seats")
            for w in ("PRIVATE-NOT-FINAL", "PRIVATE-HELD"):
                assert all(w not in p.read_text(encoding="utf-8") for p in (site / "elections").iterdir()), (
                    f"a private reason, {w}, reached the elections pages")
            low = re.sub(r"<[^>]+>", " ", html).lower()
            for w in ("projected", "projection", "leading", "too close to call", "race call", "unofficial"):
                assert w not in low, f"the official page says {w!r}"
        sm = (site / "sitemap.xml").read_text(encoding="utf-8")
        assert "/elections/2026-11-03-general" in sm and "/elections/" in sm, (
            "the elections pages are not in the sitemap, and check_site would refuse them")
        # The reader's note of a printed total that leaves out a town.
        note = ("2026-ge-house-grafton.xlsx, sheet 'rgrafrep', row 50: the file's Totals cell is "
                "=SUM(B47:B48), which leaves out Orange; read as the towns add up: Ella V. Barrett's "
                "column, 1,240, where the Totals say 1,152")
        fake = {"_notes": [note], "_source": [{"file": "records/sources/2026-ge-house-grafton.xlsx"}]}
        race = {"seats": 1, "towns": ["Orange"], "candidates": [
            {"name": "Ella V. Barrett", "party": "d", "votes": 1240, "write_in": False, "elected": True}]}
        card = BE.race_card("H|Grafton|9", race, {"seats": 1, "elected": [], "not_final": 1},
                            fake, BE.totals_notes(fake), "2026-11-03")
        assert "prints 1,152" in card and "add up to 1,240" in card and "leaves out Orange" in card, (
            f"Grafton 9's printed total and the towns' sum are not both on its card: {card}")
        return "ok", (f"{len(res['races'])} races on 20 and 10 November: counts the file's, Elected the "
                      "rule's, the tie, the recount, the held winner unseen, a cross-nomination striped, "
                      "the bars adding up, Grafton 9's total said")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# A MEMBER'S ELECTIONS TAB (the owner's design of 10 November 2026; src/pages/
# build_member_elections.py). A small made-up roster and two made-up elections,
# so that every rule is held without a built site.

def _mel_member(mid, last, first, chamber, county, district, kind="sitting", terms=None):
    """A roster row in the shape build_site_v2 writes legislators.json and
    former.json, as much of it as the matching reads."""
    abbr = county[:4]
    row = {"id": mid, "name": f"{last}, {first}", "chamber": chamber, "county": county,
           "county_abbr": abbr, "district": district, "party": "R", "slug": f"{first}-{last}".lower(),
           "display_full": f"Rep. {first} {last} (R - {abbr} {district})"}
    if kind == "former":
        row.update({"former": True, "served": {"first": "1/4/2023", "last": "11/6/2024",
                                               "terms": terms or ["2023-2024"]}})
    return row


def _mel_world():
    """(sitting, former, districts, results 2024, results 2026) of the made-up
    court: Rockingham 1 to 4 (3 with two seats) and Senate 5 and 6."""
    def dist(h, sen):
        return {"0": {"house": [{"county": "Rockingham", "district": h[0], "floterial": False,
                                 "seats": h[1]}], "senate": sen}}
    districts = {"Alpha": dist((1, 1), 5), "Beta": dist((2, 1), 5), "Gamma": dist((3, 2), 6),
                 "Delta": dist((4, 1), 6)}
    sitting = [_mel_member("1001", "Hart", "Ann", "H", "Rockingham", "1"),
               _mel_member("1002", "Moss", "Dee", "H", "Rockingham", "2"),
               _mel_member("1003", "Ives", "Fay", "H", "Rockingham", "3"),
               _mel_member("1004", "Beck", "Ida", "S", "Rockingham", "5"),
               _mel_member("1005", "None", "Zed", "H", "Rockingham", "4"),
               _mel_member("1006", "Kay", "Joe", "S", "Rockingham", "6"),
               _mel_member("1007", "Pike", "Nan", "H", "Rockingham", "4")]
    former = [_mel_member("2001", "Lowe", "Bob", "H", "Rockingham", "1", "former"),
              _mel_member("2002", "Ford", "Ed", "H", "Rockingham", "2", "former", ["2025-2026"]),
              _mel_member("2003", "Young", "Carl", "H", "Rockingham", "4", "former"),
              _mel_member("2004", "Old", "Olly", "H", "Rockingham", "1", "former", ["2001-2002"])]

    def cand(name, votes, elected, party="r", wi=False):
        return {"name": name, "party": party, "votes": votes, "write_in": wi, "elected": elected}

    def race(seats, towns, cands, scatter=0, **more):
        return {"seats": seats, "floterial": False, "towns": towns, "candidates": cands,
                "scatter": scatter, **more}
    r24 = {"election": "2024-11-05", "term": "2025-2026", "races": {
        "H|Rockingham|1": race(1, ["Alpha"], [cand("Ann Hart", 2000, True), cand("Bob Lowe", 1500, False),
                                              cand("Carl Young", 100, False), cand("Olly Old", 50, False)], 10),
        "H|Rockingham|3": race(2, ["Gamma"], [cand("Fay Ives", 3000, True), cand("Ida Beck", 2900, True),
                                              cand("Hal Orr", 800, False)]),
        "H|Rockingham|4": race(1, ["Delta"], [cand("Nan Pike", 700, True), cand("Quin Zane", 650, False)],
                               recounted=True)}}
    r26 = {"election": "2026-11-03", "term": "2027-2028", "races": {
        "H|Rockingham|2": race(1, ["Beta"], [cand("Dee Moss", 3000, True), cand("Ed Ford", 2900, False)]),
        "S|5": race(1, ["Alpha", "Beta"], [cand("Ida Beck", 9000, True), cand("Rob Cole", 8000, False)]),
        "S|6": race(1, ["Gamma", "Delta"], [cand("Joe Kay", 5000, None), cand("Kim Lu", 5000, None)])}}
    return sitting, former, districts, r24, r26


@check("build", "a member's Elections tab: a win by the elections page's own matching, a loss only on "
       "the same name and a seat held the term before or after, every other candidate left off and "
       "listed, a race not final or tied said so, the owner's matches settling either way, one row "
       "to an election, no tab for a member with no race, and both chambers on one tab",
       needs=("build_member_elections", "build_members_elect", "build_elections"))
def _member_elections_rows(BMEL, BME, BE):
    sitting, former, districts, r24, r26 = _mel_world()
    roster = BMEL.Roster(sitting, former, ["2025-2026", "2023-2024"])
    got = {}
    reports = []
    for res, today, hand in (
            (r24, "2026-11-10", {"matches": {"H|Rockingham|3": {"Ida Beck": "1004"}}, "not_final": {},
                                 "held": {}, "party": {}, "recount_deadline": "2024-11-13"}),
            (r26, "2026-11-10", {"matches": {}, "not_final": {"H|Rockingham|2": {"recount": True}},
                                 "held": {}, "party": {}, "recount_deadline": "2026-11-06"})):
        races_me, _rep = BME.members_elect(res, sitting, former, districts, hand, today)
        people = BME.People(sitting, former, BME.ballot_of(res))
        rows, rep = BMEL.election_rows(res["election"], res, races_me, hand, roster, people)
        for mid, rs in rows.items():
            got.setdefault(mid, []).extend(rs)
        reports += rep
    def one(mid, day):
        return next(r for r in got[mid] if r["d"] == day)
    # A win: the elections page's matching; the share of every vote cast, scatter in it.
    a = one("1001", "2024-11-05")
    assert (a["r"], a["v"], a["pl"], a["of"], a["sh"], a["a"], a["k"]) == (
        "won", 2000, 1, 4, 54.6, BE.race_id("H|Rockingham|1"), "H|Rockingham|1"), f"a win: {a}"
    # A loss matched with certainty: the same name, the seat held in 2023-2024.
    b = one("2001", "2024-11-05")
    assert (b["r"], b["pl"], b["sh"]) == ("lost", 2, 41.0), f"a certain loss: {b}"
    # A loss left off, and why: another district, and a seat held too long ago.
    assert "2003" not in got and "2004" not in got, "a loss with no certain match was shown"
    why = {(d, n): (near, w) for d, k, n, near, w in reports}
    assert "Rockingham 4" in why[("2024-11-05", "Carl Young")][1] and "2003" in why[("2024-11-05", "Carl Young")][0], (
        f"the report does not say Carl Young has another seat: {why.get(('2024-11-05', 'Carl Young'))}")
    assert "2001-2002" in why[("2024-11-05", "Olly Old")][1], "the report does not say Olly Old's seat is too old"
    assert ("2024-11-05", "Hal Orr") not in why and ("2024-11-05", "Quin Zane") not in why, (
        "a candidate nobody could be was listed for the owner")
    # A race of two seats gives no share; the owner's match for Ida Beck's House race shows it.
    f = one("1003", "2024-11-05")
    assert (f["r"], f["pl"], f["of"], "sh" in f) == ("won", 1, 3, False), f"a two-seat race: {f}"
    i24 = one("1004", "2024-11-05")
    assert i24["k"] == "H|Rockingham|3" and i24["r"] == "won", f"the owner's match was not taken: {i24}"
    # A senator with a House race: both chambers on one tab, newest first once sorted.
    i26 = one("1004", "2026-11-03")
    assert i26["k"] == "S|5" and i26["r"] == "won", f"the senator's Senate race: {i26}"
    srt = BMEL.sort_rows(got["1004"])
    assert [r["k"] for r in srt] == ["S|5", "H|Rockingham|3"], f"the order: {[r['k'] for r in srt]}"
    # Not final, with a recount asked for: the member, the loser the rule is certain of, both open.
    d = one("1002", "2026-11-03")
    e = one("2002", "2026-11-03")
    assert (d["r"], d.get("rq"), e["r"], e.get("rq")) == ("open", 1, "open", 1), f"not final: {d} {e}"
    # A recounted race says so.
    p = one("1007", "2024-11-05")
    assert p["r"] == "won" and p.get("rc") == 1, f"a recounted race: {p}"
    # A tie: the member is shown, as tied.
    k = one("1006", "2026-11-03")
    assert k["r"] == "tie", f"a tie: {k}"
    # A member with no race on file has no row, so no tab; the others have a row each election.
    assert "1005" not in got, "a member with no race got a row"
    for mid, rs in got.items():
        assert len({r["d"] for r in rs}) == len(rs), f"{mid} has two rows in one election"
    # The owner's null keeps a certain loss off; her id shows an uncertain one.
    hand = {"matches": {"H|Rockingham|1": {"Bob Lowe": None, "Carl Young": "2003"}}, "not_final": {},
            "held": {}, "party": {}, "recount_deadline": "2024-11-13"}
    races_me, _rep = BME.members_elect(r24, sitting, former, districts, hand, "2026-11-10")
    rows, _rep2 = BMEL.election_rows("2024-11-05", r24, races_me, hand, roster,
                                     BME.People(sitting, former, BME.ballot_of(r24)))
    assert "2001" not in rows and rows["2003"][0]["r"] == "lost", (
        "the owner's matches did not settle a loss either way")
    # A held winner is on no row and takes no share from the rest.
    hand = {"matches": {}, "not_final": {}, "held": {"H|Rockingham|1": {"Ann Hart": "private"}},
            "party": {}, "recount_deadline": "2024-11-13"}
    races_me, _rep = BME.members_elect(r24, sitting, former, districts, hand, "2026-11-10")
    rows, _rep2 = BMEL.election_rows("2024-11-05", r24, races_me, hand, roster,
                                     BME.People(sitting, former, BME.ballot_of(r24)))
    assert "1001" not in rows and all("sh" not in r and "pl" not in r for r in rows["2001"]), (
        "a race with a held winner gave a share or a place")
    return "ok", (f"{sum(len(v) for v in got.values())} rows for {len(got)} members: a win, a certain "
                  "loss, two left off and listed, not final, a recount, a tie, both chambers, no "
                  "tab for a member with no race")


@check("build", "a member's Elections tab draws each race as the elections page's own card "
       "(build_elections.race_card, not a copy), headed by the election's day linked to the race, "
       "the member's row alone marked, a race not final with a recount asked for still saying so",
       needs=("build_member_elections", "build_members_elect", "build_elections"))
def _member_elections_cards(BMEL, BME, BE):
    """The owner, 18 November 2026: the tab "replacing it with the same chart layout"
    the elections pages draw. Ida Beck (1004) has two races, the 2026 Senate race not
    final with a recount asked for; each row's card is race_card's own with the
    member's row marked er-me, and app.js draws the cards, not the table."""
    sitting, former, districts, r24, r26 = _mel_world()
    roster = BMEL.Roster(sitting, former, ["2025-2026", "2023-2024"])
    got = {}
    for res, hand in (
            (r24, {"matches": {"H|Rockingham|3": {"Ida Beck": "1004"}}, "not_final": {},
                   "held": {}, "party": {}, "recount_deadline": "2024-11-13"}),
            (r26, {"matches": {}, "not_final": {"S|5": {"recount": True}},
                   "held": {}, "party": {}, "recount_deadline": "2026-11-06"})):
        races_me, _rep = BME.members_elect(res, sitting, former, districts, hand, "2026-11-10")
        rows, _rep2 = BMEL.election_rows(res["election"], res, races_me, hand, roster,
                                         BME.People(sitting, former, BME.ballot_of(res)))
        for mid, rs in rows.items():
            for r in rs:
                want = BE.race_card(r["k"], res["races"][r["k"]], races_me[r["k"]], res,
                                    BE.totals_notes(res), res["election"], hand,
                                    mine=BE.same_name(roster.members[mid]["name"]), anchor=False)
                assert r.get("c") == want, f"{mid} {r['d']}: the tab's card is not race_card's"
                got.setdefault(mid, []).append(r)
    assert got, "no member has a row on the made-up court"
    for mid, rs in got.items():
        for r in rs:
            marked = re.findall(r'<li class="er-row er-me">(.*?)</li>', r["c"])
            assert len(marked) == 1 and BE.same_name(roster.members[mid]["name"]) in marked[0], (
                f"{mid} {r['d']}: {len(marked)} rows marked, not the member's own one")
            assert r["c"].startswith('<article class="er-race">'), (
                f"{mid}: the tab's card keeps the elections page's anchor")
    beck = BMEL.sort_rows(got["1004"])
    assert [(r["d"], r["k"]) for r in beck] == [("2026-11-03", "S|5"), ("2024-11-05", "H|Rockingham|3")], (
        f"Ida Beck's two races: {[(r['d'], r['k']) for r in beck]}")
    assert "Result not final" in beck[0]["c"] and "a recount was requested" in beck[0]["c"] \
        and "Result not final" not in beck[1]["c"], "the card of a race not final lost its recount line"
    # The elections page's own card is as it was: anchored, no row marked.
    page = BE.race_card("S|5", r26["races"]["S|5"], {}, r26, {}, "2026-11-03")
    assert page.startswith('<article class="er-race" id="r-s-5" data-towns="alpha | beta">') \
        and not re.search(r"\ber-me(?![\w-])", page), f"the elections page's card changed: {page[:120]}"
    # app.js draws the cards, newest first, each headed by its day linked to the race.
    html = _app_js("scope.renderMemberElections(" + json.dumps({"elections": beck}) + ")",
                   names=("renderMemberElections",))
    if html is None:
        return "skip", "node, app.js or the stub is not here (the cards were proven in Python)"
    heads = re.findall(r'<article class="er-race"><p class="er-when"><a href="([^"]+)">', html)
    assert heads == ["/elections/2026-11-03-general#r-s-5",
                     "/elections/2024-11-05-general#r-h-rockingham-3"], f"the cards' heads: {heads}"
    assert '<div class="er-cards">' in html and "<table" not in html and len(re.findall(r"\ber-me(?![\w-])", html)) == 2 \
        and "a recount was requested" in html, (f"the tab is not the two cards, each with its row marked: cards={'<div class=\"er-cards\">' in html} table={'<table' in html} marks={len(re.findall(r'er-me(?![\w-])', html))} recount={'a recount was requested' in html}")
    for want in ("The general elections on file in which this member is recorded",
                 "appears only where the name and the district match", "Secretary of State"):
        assert want in html, f"the tab lost its note: {want!r}"
    return "ok", (f"{sum(len(v) for v in got.values())} cards for {len(got)} members, each race_card's "
                  "own with the member's row alone marked; Ida Beck's two drawn newest first under "
                  "their days, the recount line kept, both notes kept, no table")


# THE ELECTIONS BEFORE 2024 (10 November 2026; branch dec/results-2016-2022). The
# Secretary of State's files for 2016-2022 print a surname for a House
# candidate, "Scatter" for the write-ins nobody named, no day, a Recount row
# or a BLC column for a recount; 2016 has no Strafford House file and no State
# Senate; and the 2012 districts' table is on no disk, so 2016-2020 are held
# to none. These checks hold that on made-up files, which need no saved ones.

def _legacy_book(path, rows):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    wb.save(path)


@check("build", "the results reader reads the 2016-2022 layout (a surname for a candidate, Scatter, a "
                "Recount row, a named w-in, a mistyped District, a results page with a cell holding two "
                "rows), holds an election with no district table to none and says so, and lists a county "
                "and the Senate that are not on file instead of filling them",
       needs=("parse_sos_results",))
def _elect_older_layout(PSR):
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        return "skip", "openpyxl is not installed"
    root = Path(tempfile.mkdtemp(prefix="gr-sos-old-"))
    try:
        d = root / PSR.SOURCES
        d.mkdir(parents=True)
        title = ["State of New Hampshire - 2018 General Election"]
        _legacy_book(d / "2018-ge-house-belknap.xlsx", [
            title, ["State Representatives - BELKNAP County"], [],
            ["District No. 1 (1)", "Gray, r", "Hale ,d", "Scatter"],
            ["Alpha", 100, 90, 1], ["Beta", 50, 70, None], ["TOTALS", 150, 160, 1], [],
            ["Distict No. 2 (1)", "Cole, r", "Dunn, d", "Scatter"],
            ["Gamma", 300, 301, 2], ["Recount", 303, 301]])
        _legacy_book(d / "2018-ge-house-carroll.xlsx", [
            title, ["State Representative - CARROLL County"], [],
            ["District No. 1 (1)", "Eve, r", "Fox w-in", "Scatter"], ["Delta", 10, 3, 0]])
        try:
            PSR.read_all(root, 2018, None)
            raise AssertionError("a year with eight counties not on file was read without partial")
        except PSR.Refused as e:
            assert "no 2018 House results" in str(e), f"refused, but not for the counties: {e}"
        doc = PSR.read_all(root, 2018, None, partial=True)
        races = doc["races"]
        assert sorted(races) == ["H|Belknap|1", "H|Belknap|2", "H|Carroll|1"], f"races: {sorted(races)}"
        b1, b2, c1 = races["H|Belknap|1"], races["H|Belknap|2"], races["H|Carroll|1"]
        assert b1["surnames"] and b1["seats"] == 1 and b1["towns"] == ["Alpha", "Beta"], f"belknap 1: {b1}"
        assert [(c["name"], c["votes"], c["elected"]) for c in b1["candidates"]] == [
            ("Gray", 150, False), ("Hale", 160, True)], f"belknap 1's count: {b1['candidates']}"
        assert b1["scatter"] == 1, f"a blank Scatter cell was not read as none: {b1['scatter']}"
        assert b2.get("recounted") and [(c["name"], c["votes"], c["elected"]) for c in b2["candidates"]] == [
            ("Cole", 303, True), ("Dunn", 301, False)], f"the Recount row was not the count: {b2}"
        assert any("one letter off District" in n for n in doc["_notes"]), "the mistyped District was not said"
        fox = next(c for c in c1["candidates"] if c["name"] == "Fox")
        assert fox["write_in"] and fox["votes"] == 3 and fox["party"] == "", f"a named w-in: {fox}"
        assert doc["_notes"][0].startswith("The districts of 2018 are the 2012 districts"), (
            "an election held to no district table did not say so first")
        assert doc["_not_on_file"] == {"counties": [c.title() for c in PSR.COUNTIES
                                                    if c not in ("belknap", "carroll")],
                                       "senate": True}, f"not on file: {doc['_not_on_file']}"
        assert any(n.startswith("Not on file: the State Senate") for n in doc["_notes"]), (
            "the missing Senate was not in the notes")
        # The text goes round again as the committed file does.
        assert json.loads(PSR.dumps(doc))["_not_on_file"] == doc["_not_on_file"], "dumps dropped what is not on file"
        # A results page whose cell holds two rows is two rows (2018 Strafford).
        html = root / "page.html"
        html.write_text("<table><tr><td><p>TOTALS</p><p>District No. 19 (1)FL</p></td>"
                        "<td><p>2,215</p><p>Coleman, r</p></td><td><p>&nbsp;</p></td></tr>"
                        "<tr><td colspan=3><p>State of New Hampshire - 2018 General Election</p></td></tr></table>"
                        "<table><tr><td><p>State of New Hampshire - 2018 General Election</p></td></tr>"
                        "<tr><td><p>Dover</p></td><td><p>1,000</p></td></tr></table>", encoding="utf-8")
        got = PSR.html_sheets(html)
        assert got[0][1][:2] == [["TOTALS", 2215, None], ["District No. 19 (1)FL", "Coleman, r", None]], (
            f"a fused cell was not split: {got[0][1][:2]}")
        assert got[1][1] == [["Dover", 1000]], f"the second table's repeated title was kept: {got[1][1]}"
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("surnames, Scatter, a Recount row, a w-in and a mistyped District read; no table said; "
                  "eight counties and the Senate listed as not on file; a fused page cell split")


@check("build", "an election before the latest on file is final by rule, a recount in its results still "
                "saying so, a tie still not final and the owner's marks still holding; the latest "
                "election is judged as ever, by the recount deadline",
       needs=("build_members_elect", "build_elections"))
def _elect_settled_rule(BME, BE):
    def race(seats, cands, **more):
        return {"seats": seats, "floterial": False, "towns": ["Alpha"], "scatter": 0, "surnames": True,
                "candidates": [{"name": n, "party": "r", "votes": v, "write_in": False, "elected": e}
                               for n, v, e in cands], **more}
    res = {"election": "2018-11-06", "term": "2019-2020", "races": {
        "H|Belknap|1": race(1, [("Gray", 150, True), ("Hale", 100, False)]),
        "H|Belknap|2": race(1, [("Cole", 303, True), ("Dunn", 301, False)], recounted=True),
        "H|Belknap|3": race(1, [("Ives", 10, None), ("Jay", 10, None)]),
        "H|Belknap|4": race(1, [("Kay", 9, True), ("Lee", 5, False)])}}
    empty = {"matches": {}, "not_final": {"H|Belknap|4": {"recount": True}}, "held": {}, "party": {},
             "recount_deadline": None}
    nf = lambda races: {k: (len(v["elected"]), v["not_final"], v.get("recount")) for k, v in races.items()}
    open_, _r = BME.members_elect(res, [], [], None, empty, "2026-11-10")
    assert nf(open_) == {"H|Belknap|1": (0, 1, None), "H|Belknap|2": (1, 0, None),
                         "H|Belknap|3": (0, 1, None), "H|Belknap|4": (0, 1, True)}, (
        f"with no deadline and not settled, only the recounted race is final: {nf(open_)}")
    shut, rep = BME.members_elect(res, [], [], None, empty, "2026-11-10", settled=True)
    assert nf(shut) == {"H|Belknap|1": (1, 0, None), "H|Belknap|2": (1, 0, None),
                        "H|Belknap|3": (0, 1, None), "H|Belknap|4": (0, 1, True)}, (
        f"settled: every race final but the tie and the owner's mark: {nf(shut)}")
    assert rep["pending"] == "" and open_ and BME.recount_open("2026-11-10", None, "2018-11-06"), (
        "settled still says a recount deadline is pending")
    assert BE.settled_in([("2018-11-06", 0, 0), ("2020-11-03", 0, 0)], "2018-11-06") and \
        not BE.settled_in([("2018-11-06", 0, 0), ("2020-11-03", 0, 0)], "2020-11-03"), (
        "settled_in is not 'before the latest on file'")
    assert BE.mapped("2022-11-08") and BE.mapped("2026-11-03") and not BE.mapped("2020-11-03"), (
        "an election held on the 2012 districts was given a map")
    assert BME.on_this_map("2021-2022", 2020) and not BME.on_this_map("2021-2022", 2022) and \
        BME.on_this_map("2023-2024", 2022) and BME.on_this_map("2023-2024", 2024), (
        "a seat in a term on the old districts counted for an election on the new")
    # The page of such an election: no map, what is not on file said, no deadline spoken of.
    res["_not_on_file"] = {"counties": ["Strafford"], "senate": True}
    body = BE.page_body("2018-11-06", res, shut, rep, empty, Path("site"), [], True)
    assert "ermap" not in body and "There is no map here" not in body and "no map here" in body, (
        "an election on the 2012 districts was drawn a map, or not told why it has none")
    assert "Strafford County" in body and "the State Senate results" in body and \
        "some not on file" in body, "what is not on file is not said on the page"
    assert "long past" in body and "Result not final" in body and "No deadline" not in body, (
        "the settled election's page speaks of a recount deadline, or hides its tie")
    assert "State Senate</h4>" not in body and "Senate</button>" not in body, "a Senate tab with no races"
    return "ok", ("settled: a race final unless tied or held by the owner; unsettled: only a recounted "
                  "race; no map for 2012's districts, what is not on file said; no seat carried "
                  "across 2022")


@check("build", "a winner printed as a surname is linked by the seat held in the term the election elected "
                "(or, where nobody printed it, the term before and a vote in the term after), a loss only "
                "by the surname, the seat, the party and no twin in the race, never across the 2022 "
                "redistricting",
       needs=("build_member_elections", "build_members_elect"))
def _member_elections_surnames(BMEL, BME):
    sponsors = {
        "2021-2022": {"HB1": [{"member_id": "3001", "chamber": "H", "county": "Rockingham", "district": "1"},
                              {"member_id": "3002", "chamber": "H", "county": "Rockingham", "district": "2"}]},
        "2019-2020": {"HB9": [{"member_id": "3003", "chamber": "H", "county": "Rockingham", "district": "1"},
                              {"member_id": "3005", "chamber": "H", "county": "Rockingham", "district": "2"},
                              {"member_id": "3007", "chamber": "H", "county": "Rockingham", "district": "5"},
                              {"member_id": "3008", "chamber": "H", "county": "Rockingham", "district": "4"}]}}
    hist = BME.seat_history(sponsors)
    assert hist["3001"] == {"2021-2022": ["H|Rockingham|1"]}, f"seat_history: {hist['3001']}"
    history = {"seats": hist, "served": {"3008": ["2021-2022"]}}
    former = [_mel_member("3001", "Hart", "Ann", "H", "Rockingham", "1", "former", ["2021-2022"]),
              _mel_member("3002", "Moss", "Dee", "H", "Rockingham", "2", "former", ["2021-2022"]),
              _mel_member("3003", "Lowe", "Bob", "H", "Rockingham", "1", "former", ["2019-2020"]),
              _mel_member("3005", "Pike", "Nan", "H", "Rockingham", "2", "former", ["2019-2020"]),
              _mel_member("3007", "Kay", "Joe", "H", "Rockingham", "5", "former", ["2019-2020"]),
              _mel_member("3008", "Ward", "Sam", "H", "Rockingham", "4", "former", ["2021-2022"])]
    def race(cands):
        return {"seats": 1, "floterial": False, "towns": ["Alpha"], "scatter": 0, "surnames": True,
                "candidates": [{"name": n, "party": p, "votes": v, "write_in": False, "elected": e}
                               for n, p, v, e in cands]}
    res = {"election": "2020-11-03", "term": "2021-2022", "races": {
        "H|Rockingham|1": race([("Hart", "r", 500, True), ("Lowe", "d", 400, False)]),
        "H|Rockingham|2": race([("Moss", "r", 500, True), ("Pike", "r", 400, False)]),
        "H|Rockingham|4": race([("Ward", "r", 500, True), ("Zed", "d", 400, False)])}}
    hand = {"matches": {}, "not_final": {}, "held": {}, "party": {}, "recount_deadline": None}
    races, _rep = BME.members_elect(res, [], former, None, hand, "2026-11-10", True, history)
    ids = {k: [e.get("id") for e in v["elected"]] for k, v in races.items()}
    assert ids == {"H|Rockingham|1": ["3001"], "H|Rockingham|2": ["3002"], "H|Rockingham|4": ["3008"]}, (
        f"the winners were not linked by the seat held: {ids}")
    # A winner with no history, and a member whose last term is another, is not linked by surname alone.
    far = [_mel_member("3001", "Hart", "Ann", "H", "Rockingham", "1", "former", ["2019-2020"])]
    races, _rep = BME.members_elect(res, [], far, None, hand, "2026-11-10", True,
                                    {"seats": {}, "served": {}})
    assert all(not e.get("id") for v in races.values() for e in v["elected"]), (
        "a surname alone linked a winner to a member who held no such seat")
    roster = BMEL.Roster([], former, ["2025-2026"], history)
    people = BME.People([], former, BME.ballot_of(res))
    races, _rep = BME.members_elect(res, [], former, None, hand, "2026-11-10", True, history)
    rows, rep = BMEL.election_rows("2020-11-03", res, races, hand, roster, people)
    assert rows["3001"][0]["r"] == "won" and rows["3005"][0]["r"] == "lost", (
        f"Pike held Rockingham 2 the term before and filed under the party: {rows.get('3005')}")
    assert "3003" not in rows, "Lowe, a Democrat, was matched to Bob Lowe, a Republican"
    assert "3007" not in rows, "a member of another seat was matched by surname"
    # The twin in the race: a second candidate of the surname leaves the loss to the owner.
    res["races"]["H|Rockingham|2"]["candidates"].append(
        {"name": "Pike Jr.", "party": "r", "votes": 5, "write_in": False, "elected": False})
    rows, rep = BMEL.election_rows("2020-11-03", res, races, hand, roster, people)
    assert "3005" not in rows, "a loss was matched with a second candidate of the surname in the race"
    # 2022: the term before was on the old districts, so its seat is no evidence.
    res22 = {"election": "2022-11-08", "term": "2023-2024", "races": {
        "H|Rockingham|5": race([("Moss", "r", 500, True), ("Kay", "r", 400, False)])}}
    races22, _rep = BME.members_elect(res22, [], former, None, hand, "2026-11-10", True, history)
    rows, rep = BMEL.election_rows("2022-11-08", res22, races22, hand, roster, people)
    assert "3007" not in rows, "a seat held on the 2012 districts was matched to a race of 2022's"
    return "ok", ("winners linked by the seat held, a loss by surname, seat and party, a twin, a missing "
                  "history and the 2022 redistricting each leaving it to the owner")


@check("build", "the elections steps say so loudly when the seat history's inputs (text_sponsors.json, "
                "past_sponsors.json, generated/careers.json) are missing or empty, naming each file and "
                "the rows they could not link, and say nothing when all are there",
       needs=("build_members_elect",))
def _elect_history_gaps(BME):
    root = Path(tempfile.mkdtemp(prefix="gr-hist-"))
    try:
        paths = [root / "text_sponsors.json", root / "past_sponsors.json", root / "careers.json"]
        gaps = BME.history_gaps(*paths)
        assert len(gaps) == 3 and all("is missing" in g for g in gaps), f"missing files not named: {gaps}"
        line = BME.gap_line(gaps, 7, "winner(s)")
        assert line.startswith("WARNING") and "text_sponsors.json is missing" in line and \
            "careers.json is missing" in line and " 7 winner(s)" in line, f"the line: {line}"
        for p in paths:
            p.write_text("{}", encoding="utf-8")
        assert all("is empty" in g for g in BME.history_gaps(*paths)), "empty files passed quietly"
        for p in paths:
            p.write_text('{"a": 1}', encoding="utf-8")
        assert BME.history_gaps(*paths) == [] and BME.gap_line([], 3, "winner(s)") == "", (
            "files that are there were reported")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", "missing and empty inputs named with the count unlinked; present ones silent"


@check("build", "a member's Elections tab is drawn in the member's own file from the built elections "
       "page: each row's link is a real race on a built elections page, only a member with a row has "
       "the key, and a rerun leaves nothing stale",
       needs=("build_member_elections", "build_members_elect", "build_elections"))
def _member_elections_built(BMEL, BME, BE):
    if _elect_absent():
        return "skip", "not here: " + ", ".join(_elect_absent())
    root = Path(tempfile.mkdtemp(prefix="mel_"))
    try:
        site = _elect_fixture(root)
        if not (site / "district_map.json").exists() or not (site / "legislators").is_dir():
            return "skip", "the fixture's build wrote no district_map.json or legislators/"
        (root / "corrections").mkdir(exist_ok=True)
        (root / "corrections" / "members_elect.json").write_text(json.dumps(_ELECT_HAND), encoding="utf-8")
        # The three former members the fixture adds have no file of their own.
        for m in _ELECT_FORMER:
            (site / "legislators" / f"{m['id']}.json").write_text(json.dumps({"id": m["id"]}), encoding="utf-8")
        env = {"GRANITE_BUILD_DATE": _ELECT_IN}
        for script in ("build_elections.py", "build_member_elections.py"):
            r = _run([sys.executable, _paths.script(script), "--site", "site"] + (
                ["--report", "reports/elections_uncertain.md"] if script == "build_member_elections.py" else []),
                cwd=root, capture_output=True, text=True, timeout=300, env=env)
            assert r.returncode == 0, f"{script} failed: {(r.stderr or r.stdout)[-600:]}"
        page = (site / "elections" / "2026-11-03-general.html").read_text(encoding="utf-8")
        ids = set(re.findall(r'<article class="er-race" id="([^"]+)"', page))
        withkey = {}
        for f in (site / "legislators").glob("*.json"):
            doc = json.loads(f.read_text(encoding="utf-8"))
            if doc.get("elections"):
                withkey[f.stem] = doc["elections"]
        assert withkey, "no member's file has an elections list on the fixture"
        for mid, rows in withkey.items():
            assert [r["d"] for r in rows] == sorted((r["d"] for r in rows), reverse=True), (
                f"{mid}: not newest first")
            for r in rows:
                assert r["a"] in ids and r["a"] == BE.race_id(r["k"]), (
                    f"{mid}: {r['a']} is no race card on the built {r['d']} page")
                assert (site / "elections" / f"{r['d']}-general.html").exists(), (
                    f"{mid}: {r['d']} has no built elections page")
        # Jodi Nelson sat for Rockingham 13 and was re-elected; the fixture's own sitting member.
        won = {mid for mid, rows in withkey.items() if any(r["r"] == "won" for r in rows)}
        assert won, "no member won a race on the fixture"
        written = (root / "reports" / "elections_uncertain.md")
        assert written.exists(), "the owner's list of uncertain races was not written"
        # A rerun is the same; and with no results there is no key anywhere.
        before = {f.stem: f.read_bytes() for f in (site / "legislators").glob("*.json")}
        r = _run([sys.executable, _paths.script("build_member_elections.py"), "--site", "site"],
                 cwd=root, capture_output=True, text=True, timeout=300, env=env)
        assert r.returncode == 0 and before == {f.stem: f.read_bytes() for f in (site / "legislators").glob("*.json")}, (
            "a rerun changed the members' files")
        (root / "collected" / "election_2026.json").unlink()
        r = _run([sys.executable, _paths.script("build_member_elections.py"), "--site", "site"],
                 cwd=root, capture_output=True, text=True, timeout=300, env=env)
        assert r.returncode == 0, f"with no results: {(r.stderr or r.stdout)[-400:]}"
        assert not any("elections" in json.loads(f.read_text(encoding="utf-8"))
                       for f in (site / "legislators").glob("*.json")), (
            "a member's file kept an elections list after the results were gone")
        return "ok", (f"{len(withkey)} members' files on the fixture, every link a race card on the "
                      "built page, newest first, a rerun the same, none left once the results go")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "election week's helper drafts from what the steps print, proposes only what the "
       "step could not be sure of, places the recount schedule's races, reads a statewide count "
       "only, waits and finishes as it should, asks nobody and writes only logs/",
       needs=("election_week", "build_members_elect"))
def _election_week_helper(EW, BME):
    """src/ops/election_week.py (29 October 2026): the routine work around
    saving the Secretary of State's files, which stays a person's. Its
    drafts are read off build_members_elect.say_report's own printing, so a
    change to that printing that the drafter no longer reads fails here, not
    on election night. And the review's cases: a NOT LINKED line proposes
    its one member only where the step could not be sure of a first name,
    never a rival or another county's; the recount schedule's phrasings --
    "Rockingham 13", "29F", "SD 9", "Districts 12 and 13", a withdrawn one,
    a time -- are placed, or listed, never dropped; a sheet of county blocks
    gives no statewide count without a statewide row; check waits, finishes,
    runs once more for a new upload, and does not finish on a step that
    showed nobody; and it asks nobody and writes only logs/."""
    import contextlib
    import io
    report = {"unlinked": [("H|Coos|5", "Peter Morency",
                            "the first name fits only as the start of the sitting member's, by "
                            "three letters or one letter more: Rep. Pete Morency (R - Coos 5) "
                            "[8401] sits for Coos 5"),
                           ("H|Hillsborough|12", "Pat Long",
                            "another candidate on the ballot answers to the name of the sitting "
                            "member: Rep. Patrick Long [123]: rivals"),
                           ("H|Merrimack|9", "Pat Smith", "two members: Rep. A [1]; Rep. B [2]")],
              "new": [("H|Hillsborough|10", "Marty Jack", BME.NEW)],
              "short": [("H|Coos|5", 1, 0, 0, 0, True)], "notes": ["a note"], "pending": ""}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        BME.say_report(report, Path("corrections/members_elect.json"), "2026-11-03")
    rows = EW.step_rows(buf.getvalue())
    assert [len(rows[k]) for k in ("NOT LINKED", "NEW", "DO NOT ADD UP", "NOTES")] == [3, 1, 1, 1], (
        f"the drafter no longer reads build_members_elect's report: {rows}")
    roster = [("733", "Jack, Martin", "H", "Hillsborough", "10", "sitting"),
              ("9", "Jack, Other", "H", "Coos", "1", "sitting")]
    d = EW.draft_matches(rows, "2026-11-03", roster)
    m, ev = d["2026-11-03"]["matches"], d["_evidence"]
    assert m == {"H|Coos|5": {"Peter Morency": "8401"}, "H|Hillsborough|12": {"Pat Long": None},
                 "H|Merrimack|9": {"Pat Smith": None}, "H|Hillsborough|10": {"Marty Jack": None}}, (
        f"the drafted matches (a rival's id is never proposed): {m}")
    assert "Martin Jack [733]" in ev["H|Hillsborough|10"]["Marty Jack"] and \
        "Other" not in ev["H|Hillsborough|10"]["Marty Jack"], (
        f"a NEW name's same-surname member of its county is not named to check: {ev}")
    races = {k: {} for k in ("H|Hillsborough|12", "H|Hillsborough|13", "H|Hillsborough|40",
                             "H|Rockingham|13", "H|Merrimack|29", "H|Strafford|18", "S|24", "S|9")}
    sched = ("9:00 AM State Representative, Hillsborough County District 12 (Hudson)\n"
             "1:00 PM Hillsborough County, District No. 40 - State Representatives\n"
             "9:00 AM State Senate District 24\nRockingham 13 (Raymond, Stratham)\n"
             "Merrimack 29F\nSD 9\nHillsborough County Districts 12 and 13\n"
             "Hillsborough County District 12, 2 seats\nStrafford 18 recount WITHDRAWN\n"
             "2:00 PM Grafton Dist. 99\nTuesday, November 10\n")
    draft, unplaced = EW.draft_recounts(sched, races, "2026-11-09", "2026-11-06", "2026-11-03")
    assert sorted(draft["2026-11-03"]["not_final"]) == sorted(k for k in races if k != "H|Strafford|18") \
        and draft["2026-11-03"]["recount_deadline"] == "2026-11-06" and \
        unplaced == ["Strafford 18 recount WITHDRAWN", "2:00 PM Grafton Dist. 99"], (
            f"the recount draft: {sorted(draft['2026-11-03']['not_final'])} {unplaced}")
    root = Path(tempfile.mkdtemp(prefix="ew_"))
    here = Path.cwd()
    try:
        import openpyxl
    except ImportError:
        openpyxl = None
    try:
        if openpyxl is not None:
            def book(name, rows):
                wb = openpyxl.Workbook()
                ws = wb.active
                for r in rows:
                    ws.append(r)
                wb.save(root / name)
                return root / name
            head = [["Question No. 1"], [], ["Town", "Yes", "No", "Blank", "Overvotes"],
                    ["Concord", 9000, 3000, 800, 2]]
            c = EW.question_count(book("one.xlsx", head + [["TOTALS", 14000, 5500, 1200, 3]]))
            assert (c["yes"], c["no"], c["blank"], c["over"]) == (14000, 5500, 1200, 3), c
            row = EW.draft_cacr(c, "https://www.sos.nh.gov/x", "CACR13", "2026-11-05")
            assert row["two_thirds"]["ratified"] and row["row"]["yes"] == 14000, row
            blocks = [["Question No. 1"]]
            for county, (y, n) in (("Belknap", (10, 5)), ("Sullivan", (7, 3))):
                blocks += [[county + " County"], ["Town", "Yes", "No"], ["A", y, n], ["Totals", y, n]]
            for name, rows_, want in (("blocks.xlsx", blocks, None),
                                      ("state.xlsx", blocks + [["State Totals", 17, 8]], (17, 8))):
                try:
                    got = EW.question_count(book(name, rows_))
                    got = (got["yes"], got["no"])
                except SystemExit:
                    got = None
                assert got == want, f"{name}: a county's total read as the state's, or none: {got}"
        # check(), its steps stubbed: waits, finishes, runs again for a new
        # upload, and does not finish on a step that showed nobody.
        src = root / "records" / "sources"
        src.mkdir(parents=True)
        os.chdir(root)
        names = [f"2026-ge-house-{c}.xlsx" for c in EW.PSR.COUNTIES]
        for n in names[:-1]:
            (src / n).write_bytes(n.encode())
        (src / "2026-ge-constitutional-question.xlsx").write_bytes(b"q")
        asked, said = [], {"step": "members-elect: x\n  wrote site/members_elect.json"}
        was = EW.run
        EW.run = lambda args: (asked.append(Path(str(args[0])).name),
                               (0, said["step"] if "members" in str(args[0]) else "wrote x"))[1]
        try:
            assert EW.check("2026", "https://x") == 0 and not asked, "it ran a step on 10 of 11"
            (src / names[-1]).write_bytes(b"z")
            (src / "2026-ge-state-senate-district-1-24.xlsx").write_bytes(b"s")
            part = src / "2026-ge-house-coos (1).xlsx.crdownload"
            part.write_bytes(b"")
            assert not EW.status("2026")[1], "it went on with a download still in progress"
            part.unlink()
            EW.check("2026", "https://x")
            assert asked == ["parse_sos_results.py", "build_members_elect.py"], (
                f"all eleven and a question's file saved, it ran {asked}")
            EW.check("2026", "https://x")
            assert len(asked) == 2, "done, it ran the steps again"
            (src / f"2026-ge-house-{EW.PSR.COUNTIES[0]}_1.xlsx").write_bytes(b"recount")
            said["step"] = "members-elect: none shown -- the day is not the window's"
            assert EW.check("2026", "https://x") == 1 and len(asked) == 4, (
                "a later upload did not run the steps, or a step that showed nobody was done")
            EW.check("2026", "https://x")
            assert len(asked) == 6, "a step that showed nobody was taken for done"
            assert "showed nobody" in (root / "logs" / "election_week.md").read_text(encoding="utf-8")
        finally:
            EW.run = was
    finally:
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)
    code = Path(_paths.script("election_week.py")).read_text(encoding="utf-8")
    assert not re.search(r"urlopen|urllib\.request|requests\.|http\.client|socket", code), (
        "election_week.py asks the network")
    logs = set(re.findall(r'^([A-Z_]+) = LOGS / "[^"]+"', code, re.M))
    written = set(re.findall(r"(\w+)\.write_(?:text|bytes)\(", code))
    assert len(logs) >= 6 and written <= logs and "open(" not in code.replace("pdfplumber.open(", ""), (
        f"election_week.py writes something not in logs/: {sorted(written - logs)}")
    return "ok", ("drafts read off say_report, a rival never proposed, the schedule's phrasings "
                  "placed or listed, a statewide count only, check's states, logs/ only")


@check("build", "members-elect: \"Your rep\" tags only a member re-elected to the seat they hold "
                "-- the file's own, the item both renderers mark elown, and find.js's rule that "
                "turns the tag off on every other link in a block",
       needs=("build_members_elect",))
def _elect_own_seat(BME):
    """The owner, 7 November 2026, on the walk of dry run 4: with a town saved
    in the header, find.js's ytMark tags every link to one of its members'
    pages "Your rep" or "Your senator", and a members-elect block is links
    to pages. Derry's Rockingham 13 tagged Charles Foote alone of its eight
    winners, which is right; Antrim's State Senate district 8 tagged Jim
    Creighton "Your rep", a representative of Hillsborough 30 elected to the
    Senate, which is not. Her rule: keep the tag on a member re-elected to
    their own seat; take it off where the person is elected to another
    seat, and off anyone not now holding that seat; the same on the
    Members-Elect tab and the map, which draw the same block.

    On the fixture's election, `own` is on Jodi Nelson (Rockingham 13) and
    Debra Altschiller (Senate 24) alone, each re-elected to the seat they
    hold, and not on a sitting member the person's file takes to be the
    winner of another seat, nor on a former member or anyone new. Both
    renderers mark such a winner's item elown, and only where it is linked
    (tests/components_cases.json, held to one answer by _components_agree).
    And ytMark turns the tag off on every link in a block but an elown
    item's, after the rules that set it."""
    absent = _elect_absent()
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    root = Path(tempfile.mkdtemp(prefix="gr-elect-own-"))
    try:
        site = _elect_fixture(root)
        # A sitting member of another seat, Hillsborough 30, added to this
        # copy of the fixture's roster, whom the person's file says won
        # Rockingham 32: elected to another seat, as Creighton was.
        lp = site / "legislators.json"
        sitting = json.loads(lp.read_text(encoding="utf-8"))
        other = _elect_rep("990017", "Creighton", "James", "Hillsborough", 30)
        lp.write_text(json.dumps(sitting + [other]), encoding="utf-8")
        assert BME.seat_of(other) == "H|Hillsborough|30"
        hand = {"2026-11-03": {"recount_deadline": _ELECT_DEADLINE,
                               "matches": {"H|Rockingham|32": {"Pat Newell": str(other["id"])}}}}
        code, out, doc = _elect_run(root, _ELECT_IN, hand=hand)
        assert code == 0 and doc, f"the step wrote no file on {_ELECT_IN}: {out[-300:]}"
        own = sorted((k, e["n"]) for k, r in doc["races"].items() for e in r["elected"]
                     if "own" in e)
        assert own == [("H|Rockingham|13", "Jodi Nelson"), ("S|24", "Debra Altschiller")], (
            f"'own' is on {own}: it is for a sitting member re-elected to the seat they hold, "
            "and only them")
        moved = [e for e in doc["races"]["H|Rockingham|32"]["elected"] if e["n"] == "Pat Newell"]
        assert moved and moved[0]["k"] == "sitting" and moved[0].get("id") == str(other["id"]) \
            and "own" not in moved[0], (
            f"a sitting member elected to another seat is drawn as {moved}: linked, and not own")
        assert all(e.get("own") is True for r in doc["races"].values() for e in r["elected"]
                   if "own" in e), "'own' is written as something other than true"
    finally:
        shutil.rmtree(root, ignore_errors=True)
    import components as C
    foote = {"n": "Charles Foote", "p": "R", "k": "sitting", "id": "10691",
             "s": "charles-foote-rock-13", "own": True}
    creighton = {"n": "Jim Creighton", "p": "R", "k": "sitting", "id": "9917",
                 "s": "james-creighton-hills-30"}
    html = C.elect_race({"seats": 2, "elected": [foote, creighton]})
    assert re.findall(r'<li class="elown"><span class="mchip p-R" translate="no"><a href="'
                      r'legislator/([a-z0-9-]+)"', html) == ["charles-foote-rock-13"] \
        and html.count("elown") == 1, f"the block marks {html!r}: only Foote's item is elown"
    assert "elown" not in C.elect_race({"seats": 1, "elected": [dict(foote, s="")]}), (
        "an item with no link is marked elown")
    fj = _source("src/pages/find.js")
    mark = re.search(r"function ytMark\(p\)\{(.*?)\n\}", fj, re.S)
    off = '".ellist > li:not(.elown) a::after{content:none !important}"'
    # The Members-Elect tab's lists by name and by county (the owner's walk
    # of 7 November 2026): the same chips, in a party's column or a county's
    # grid, the list .elroll and its items li or div.
    off_roll = '".elroll > :not(.elown) a::after{content:none !important}"'
    assert mark and off in mark.group(1) and off_roll in mark.group(1), (
        "ytMark does not turn the tag off on the members-elect lists' other links")
    # The rules reach every place the winners are drawn: each link sits in an
    # item of a list they key on -- elect_race's own, round each race's chips
    # on the town page's block and the map's panel, and the Officials tab's
    # two views, which have no .elect round them (the review of 7 November
    # 2026; By district went on the walk of 8 November) -- and the item is
    # elown for Foote, re-elected to his own seat, and for nobody else, in
    # every view.
    import officials_tabs as OT
    elect = {"election": "2026-11-03", "takes_office": "2026-12-02", "races": {
        "S|8": {"seats": 1, "not_final": 0, "held": 0, "elected": [creighton]},
        "H|Rockingham|13": {"seats": 2, "not_final": 0, "held": 0, "elected": [foote]}}}
    for where, page, n in (("the Officials tab", OT.members_elect(elect, "2026-11-20"), 4),
                           ("a town page's block", C.elect_block(
                               [["", elect["races"]["S|8"]], ["", elect["races"]["H|Rockingham|13"]]],
                               "2026-11-03", "2026-12-02", "2026-11-20"), 2)):
        marks = _elect_marks(page)
        outside = [s for s, lst, _o in marks if lst is None]
        if len(marks) != n or outside:
            raise AssertionError(f"on {where}, {len(outside)} of {len(marks)} winners' links (of {n} "
                                 f"drawn) are outside a list ytMark's rules reach: {outside}")
        wrong = [(s, lst, o) for s, lst, o in marks if o != (s == foote["s"])]
        if wrong:
            raise AssertionError(f"on {where}, an item is elown where it should not be, or not "
                                 f"where it should: {wrong}")
    body = mark.group(1)
    for rule in (off, off_roll):
        assert body.index(rule) > body.index('tr("yt.your_rep","Your rep")') \
            and body.index(rule) > body.index('tr("yt.your_senator","Your senator")'), (
            "ytMark's rule taking the tag off comes before the rules that set it")
    return "ok", ("own on Nelson and Altschiller alone, not on a sitting member elected to "
                  "another seat; the renderers mark only a linked own winner elown, in a town "
                  "page's block and in each of the Officials tab's two views; ytMark takes the "
                  "tag off every other link in a block or a list")


def _elect_marks(page):
    """Each member's link in `page`, as (slug, the list it is in, whether its
    item is elown): the list the link's nearest ancestor of class ellist or
    elroll, and the item that list's child the link is inside -- the two
    things ytMark's rules key on. The list is None for a link in neither."""
    from html.parser import HTMLParser
    out = []

    class Walk(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            href = str(a.get("href") or "")
            if tag == "a" and href.startswith("legislator/"):
                cls = [set(str(c or "").split()) for _t, c in self.stack]
                at = next((i for i in range(len(cls) - 1, -1, -1) if cls[i] & {"ellist", "elroll"}),
                          None)
                slug = href[len("legislator/"):].removesuffix(".html")
                out.append((slug, None, None) if at is None or at + 1 >= len(cls) else
                           (slug, " ".join(sorted(cls[at] & {"ellist", "elroll"})),
                            "elown" in cls[at + 1]))
            if tag not in ("br", "hr", "img", "input", "link", "meta", "wbr"):
                self.stack.append((tag, a.get("class")))

        def handle_endtag(self, tag):
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    break
    Walk().feed(page)
    return out


@check("build", "members-elect: each winner's status -- incumbent, returning, new chamber, new, and "
                "prior service not on record -- is worked out from the record by member id, "
                "never from a name", needs=("build_members_elect",))
def _elect_status(BME):
    """The owner's four words of 12 November 2026 and the fifth for where the
    record cannot say, on rows built here: INCUMBENT serving now in the
    chamber; RETURNING served before and is not serving now (an earlier
    term, or the term now ending left partway through, as a member who
    resigned mid-term and was elected again); NEW CHAMBER most recent service the
    other chamber, sitting or last; NEW nobody; UNSURE a former member with no
    term on file, or a new person whose surname the bills before 1999 print
    for the same chamber and county (the Senate: district). A person is
    found by the row of their id; a row of the same name under another id is
    nobody's, and a sponsor with a member number is already named."""
    bad = []
    rows = {"1": {"chamber": "H"}, "2": {"chamber": "S"},
            "3": {"chamber": "H", "served": {"terms": ["2019-2020", "2023-2024"]}},
            "4": {"chamber": "H", "served": {"terms": ["2025-2026"]}},
            "5": {"chamber": "H", "served": {"terms": []}},
            "6": {"chamber": "S", "served": {"terms": ["2013-2014"]}},
            "7": {"chamber": "H", "served": {"terms": ["2023-2024"]}, "name": "Burt, Ann"},
            "8": {"chamber": "S", "name": "Burt, Ann"}}
    H, S = "H|Coos|1", "S|8"
    want = [  # (the entry, its race, the row's id, the status)
        ({"k": "sitting", "id": "1"}, H, "incumbent"),
        ({"k": "sitting", "id": "1"}, S, "chamber"),
        ({"k": "sitting", "id": "2"}, H, "chamber"),
        ({"k": "sitting", "id": "2"}, S, "incumbent"),
        ({"k": "former", "id": "3"}, H, "returning"),
        ({"k": "former", "id": "3"}, S, "chamber"),
        ({"k": "former", "id": "4"}, H, "returning"),  # left the term now ending partway
        ({"k": "former", "id": "5"}, H, "unsure"),
        ({"k": "former", "id": "6"}, H, "chamber"),
        ({"k": "former", "id": "6"}, S, "returning"),
        ({"k": "new"}, H, "new"),
        ({"k": "new", "u": True}, H, "unsure"),
        ({"k": "sitting", "id": "99"}, H, ""),     # no row: no word, no guess
        ({"k": "former", "id": "99"}, H, ""),
        ({"k": "sitting"}, H, ""),
        ({"k": "returning", "id": "1"}, H, ""),    # a kind the file does not use
    ]
    for e, key, st in want:
        got = BME.elect_status(e, key, rows.get(str(e.get("id"))) if e.get("id") else None)
        if got != st:
            bad.append(f"{e} in {key}: {got!r}, not {st!r}")
    # By id and never by name: two rows of one name, and the entry's id picks the row.
    a = BME.elect_status({"k": "former", "id": "7"}, H, rows["7"])
    b = BME.elect_status({"k": "sitting", "id": "8"}, H, rows["8"])
    if (a, b) != ("returning", "chamber"):
        bad.append(f"two Ann Burts by their ids are {(a, b)}")
    if set(BME.STATUSES) != {"returning", "incumbent", "chamber", "new", "unsure"}:
        bad.append(f"the statuses are {BME.STATUSES}")
    # The doubt: a surname, a chamber and a county (a Senate district), on a bill before 1999
    # that names no member.
    sp = {"1993-1994": {"HB1": [{"name": "Smith", "chamber": "H", "county": "Coos", "district": "2"},
                                {"name": "Jones", "chamber": "S", "county": "", "district": "5"},
                                {"name": "Brown", "chamber": "H", "county": "Coos", "member_id": "77"}]},
          "2001-2002": {"HB2": [{"name": "Green", "chamber": "H", "county": "Coos"}]}}
    got = BME.earlier_names(sp)
    if set(got) != {("smith", "H", "coos"), ("jones", "S", "5")}:
        bad.append(f"the earlier surnames are {sorted(got)}: not Smith of Coos and Jones of Senate "
                   "5 only (Brown names a member, Green is of 2001)")
    races = {"H|Coos|2": {"elected": [{"n": "Pat Smith", "k": "new"}, {"n": "Cy Green", "k": "new"},
                                      {"n": "Bo Brown", "k": "new"},
                                      {"n": "Dee Smith", "k": "former", "id": "3"}]},
             "H|Grafton|3": {"elected": [{"n": "Al Smith", "k": "new"}]},
             "S|5": {"elected": [{"n": "Ann Jones", "k": "new"}]},
             "S|6": {"elected": [{"n": "Jo Jones", "k": "new"}]}}
    n = BME.earlier_service(races, got)
    flagged = sorted(e["n"] for r in races.values() for e in r["elected"] if e.get("u"))
    if n != 2 or flagged != ["Ann Jones", "Pat Smith"]:
        bad.append(f"{n} flagged, {flagged}: only Pat Smith (Coos) and Ann Jones (Senate 5), "
                   "and no member the record names")
    # THE FIRST NAMES (13 November 2026). A sponsor the General Court's record placed on a
    # person is "Frank Allen"; one printed with an initial is "F. Riley"; one with a surname
    # alone says nothing. A winner whose first name plainly differs from every one printed or
    # placed at that surname and county has no doubt; the same first name, a short form, an
    # initial that begins it, or no first name on the old row is still the doubt.
    sp2 = {"1993-1994": {"HB1": [{"name": "Frank Allen", "chamber": "H", "county": "Coos"},
                                 {"name": "Mary Allen", "chamber": "H", "county": "Coos"},
                                 {"name": "F. Riley", "chamber": "H", "county": "Coos"},
                                 {"name": "Robert Hale", "chamber": "H", "county": "Coos"},
                                 {"name": "Pierce", "chamber": "H", "county": "Coos"}]}}
    got2 = BME.earlier_names(sp2)
    if got2.get(("allen", "H", "coos")) != {"Frank", "Mary"} or got2.get(("pierce", "H", "coos")) != {""}:
        bad.append(f"the first names kept are {got2}")
    races2 = {"H|Coos|3": {"elected": [
        {"n": "Denise Allen", "k": "new"},        # not Frank, not Mary: cleared
        {"n": "Frank Allen", "k": "new"},         # the same first name: the doubt stays
        {"n": "Fran Allen", "k": "new"},          # a prefix of Frank: stays
        {"n": "Dee Riley", "k": "new"},           # D against the initial F.: cleared
        {"n": "Fred Riley", "k": "new"},          # F.: stays
        {"n": "Bob Hale", "k": "new"},            # a short form of Robert: stays
        {"n": "Ann Pierce", "k": "new"},          # the old row has no first name: stays
        {"n": "Sam Lowe", "k": "new"}]}}          # a surname nobody printed: no doubt
    n2 = BME.earlier_service(races2, got2)
    flagged2 = sorted(e["n"] for e in races2["H|Coos|3"]["elected"] if e.get("u"))
    if flagged2 != ["Ann Pierce", "Bob Hale", "Fran Allen", "Frank Allen", "Fred Riley"] or n2 != 5:
        bad.append(f"{n2} flagged by first names, {flagged2}")
    assert not bad, "\n  ".join(bad)
    return "ok", ("five statuses by the row of the id, the doubt by surname, chamber and county, "
                  "cleared only by a first name that plainly differs")


@check("build", "members-elect: what the rule cannot be certain of goes to the person, never "
                "to a page", needs=("build_members_elect",))
def _elect_rule(BME):
    """The failure cases of the matching rule (private/MEMBERS_ELECT_PLAN.md),
    each sent to the report and never linked: a sitting member of that name in
    another seat where the ballot was not read; a Jr. and a Sr. on the two
    sides; a former member with no county, or of another county; two of a
    surname in one seat, where the first names must be equal and a short
    form does not do; a surname of two words read as one ("St. Clair" is not
    "Clair"); a first name that fits only as the start of the other's by
    three letters or by one letter more (Joelle for Joe, Pat for Patricia,
    Louis for Louise), in the seat or out of it; a former member who fits
    only by a short form (Bob for Robert: the person's rule says the same
    name, 16 October 2026); two former records that answer to one name; and
    two winners taken to one member. And what is certain links: the seat's
    member under a short form member_links.SHORT lists, the name either way
    round, a suffix on both sides or -- since the person's widening of 17
    October 2026 -- on one side only, a former representative elected to a
    Senate district in the county he sat for. _elect_widened holds the
    widenings on the 2024 names."""
    sitting = [
        {"id": "s1", "name": "Nelson, Jodi", "chamber": "H", "county": "Rockingham",
         "district": "13", "slug": "jodi-nelson-rock-13"},
        {"id": "s2", "name": "Mannion, William", "chamber": "H", "county": "Hillsborough",
         "district": "1", "slug": "william-mannion-hills-1"},
        {"id": "s3", "name": "Mannion, Dennis", "chamber": "H", "county": "Hillsborough",
         "district": "1", "slug": "dennis-mannion-hills-1"},
        {"id": "s4", "name": "Perkins Kwoka, Rebecca", "chamber": "S", "county": "Rockingham",
         "district": "24", "slug": "rebecca-perkins-kwoka-sd-24"},
        {"id": "s5", "name": "Sabourin dit Choinière, Matt", "chamber": "H",
         "county": "Hillsborough", "district": "1", "slug": "matt-sabourin-hills-1"},
        # Two the review of 16 October 2026 found taking a stranger's first
        # name by its first letters: Rep. Joe Alexander, Rep. Louise Andrus.
        {"id": "s6", "name": "Alexander, Joe", "chamber": "H", "county": "Coos",
         "district": "1", "slug": "joe-alexander-coos-1"},
        {"id": "s7", "name": "Andrus, Louise", "chamber": "H", "county": "Belknap",
         "district": "5", "slug": "louise-andrus-belk-5"}]
    former = [
        # As former.json writes 953 of its counties: the abbreviation.
        {"id": "f6", "name": "Kittredge, Mac", "chamber": "H", "county": "Belk",
         "district": "2", "slug": "mac-kittredge-belk-2"},
        {"id": "f1", "name": "Clegg, Robert", "chamber": "H", "county": "Rockingham",
         "district": "3", "slug": "robert-clegg-rock-3"},
        {"id": "f2", "name": "Roberge, Sheila", "chamber": "S", "county": "", "district": "9",
         "slug": "sheila-roberge-sd-9"},
        {"id": "f3", "name": "Barnes, Jr., John", "chamber": "H", "county": "Rockingham",
         "district": "8", "slug": "john-barnes-rock-8"},
        {"id": "f4", "name": "Clair, Charlie", "chamber": "H", "county": "Rockingham",
         "district": "9", "slug": "charlie-clair-rock-9"},
        {"id": "f5", "name": "St. Clair, Charlie", "chamber": "H", "county": "Belknap",
         "district": "5", "slug": "charlie-st-clair-belk-5"},
        # Patricia Cote and Donna Sytek, whose pages "Pat Cote" and "Don
        # Sytek" reached by the first three letters (the review of 16
        # October 2026); and one person's two records under two spellings,
        # as member_links.py tells of the Longs, which no rule may choose
        # between.
        {"id": "f7", "name": "Cote, Patricia", "chamber": "H", "county": "Rock",
         "district": "9", "slug": "patricia-cote-rock-9"},
        {"id": "f8", "name": "Sytek, Donna", "chamber": "H", "county": "Rockingham",
         "district": "4", "slug": "donna-sytek-rock-4"},
        {"id": "f9", "name": "Long, Pat", "chamber": "S", "county": "Hillsborough",
         "district": "20", "slug": "pat-long-sd-20"},
        {"id": "f10", "name": "Long, Patrick", "chamber": "H", "county": "Hills",
         "district": "23", "slug": "patrick-long-hills-23"}]

    def town(county, n, senate):
        return {"0": {"senate": senate, "house": [
            {"county": county, "district": n, "floterial": False, "seats": 2}]}}
    districts = {"Raymond": town("Rockingham", 13, 24), "Bedford": town("Hillsborough", 1, 9),
                 "Berlin": town("Coos", 1, 1), "Laconia": town("Belknap", 5, 7)}
    races, clash = BME.races_on_file(districts)
    assert not clash and sorted(races) == sorted(
        ["H|Rockingham|13", "H|Hillsborough|1", "H|Coos|1", "H|Belknap|5", "S|24", "S|9",
         "S|1", "S|7"]), f"the races on file read as {sorted(races)} {clash}"
    people = BME.People(sitting, former)
    cases = [
        ("H|Rockingham|13", "Jodi Nelson", "s1", ""),
        ("H|Rockingham|13", "Nelson, Jodi", "s1", ""),
        # A suffix on one side only is passed over (17 October 2026), and a
        # move to another seat links only where the ballot was read.
        ("H|Rockingham|13", "Jodi Nelson Jr.", "s1", ""),
        ("S|24", "Jodi Nelson", None, "the ballot was not read"),
        ("H|Hillsborough|1", "William Mannion", "s2", ""),
        ("H|Hillsborough|1", "Dennis Mannion", "s3", ""),
        ("H|Hillsborough|1", "Bill Mannion", None, "only by a short form"),
        ("H|Coos|1", "Joe Alexander", "s6", ""),
        ("H|Coos|1", "Joseph Alexander", "s6", ""),
        ("H|Coos|1", "Joelle Alexander", None, "only as the start"),
        ("H|Belknap|5", "Louise Andrus", "s7", ""),
        ("H|Belknap|5", "Louis Andrus", None, "only as the start"),
        ("H|Rockingham|13", "Bob Clegg", None, "only by a short form"),
        ("H|Rockingham|13", "Pat Cote", None, "only by a short form"),
        ("H|Rockingham|13", "Patricia Cote", "f7", ""),
        ("H|Rockingham|13", "Don Sytek", None, "only by a short form"),
        ("H|Rockingham|13", "Donna Sytek", "f8", ""),
        ("H|Hillsborough|1", "Patrick Long", None, "2 former members of that name, 1 of them"),
        ("S|24", "Robert Clegg", "f1", ""),
        ("H|Coos|1", "Robert Clegg", None, "sat in Rockingham"),
        ("S|9", "Sheila Roberge", None, "no county on record"),
        ("H|Rockingham|13", "John Barnes", "f3", ""),
        ("H|Rockingham|13", "John Barnes Jr.", "f3", ""),
        ("H|Rockingham|13", "John Barnes Sr.", None, "Jr. or Sr. on each side"),
        ("H|Rockingham|13", "Charlie St. Clair", None, "sat in Belknap"),
        ("H|Belknap|5", "Charlie St. Clair", "f5", ""),
        ("S|24", "Rebecca Perkins Kwoka", "s4", ""),
        ("H|Hillsborough|1", "Matt Sabourin dit Choiniere", "s5", ""),
        ("H|Belknap|5", "Mac Kittredge", "f6", ""),
        ("H|Rockingham|13", "Pat Newell", None, BME.NEW),
    ]
    bad = []
    for key, name, mid, why in cases:
        p, said = BME.auto_link(key, name, people, races)
        if (p or {}).get("id") != mid or (why and why not in said):
            bad.append(f"{name} in {key}: {(p or {}).get('id')} ({said!r}), not {mid} ({why!r})")
    # Two winners taken to one member: neither is linked, and both are named.
    results = {"races": {"H|Rockingham|13": {"seats": 2, "candidates": [
        {"name": "Jodi Nelson", "party": "r", "votes": 9, "elected": True},
        {"name": "J. Nelson", "party": "r", "votes": 8, "elected": True}]}}}
    hand = {"matches": {"H|Rockingham|13": {"J. Nelson": "s1"}}, "not_final": {}, "held": {},
            "recount_deadline": _ELECT_DEADLINE}
    got, report = BME.members_elect(results, sitting, former, districts, hand, _ELECT_IN)
    drawn = got["H|Rockingham|13"]["elected"]
    if any("id" in e or e["k"] != "new" for e in drawn) or \
            sorted(n for _k, n, _w in report["unlinked"]) != ["J. Nelson", "Jodi Nelson"]:
        bad.append(f"two winners taken to one member: drawn {drawn}, named {report['unlinked']}")
    assert not bad, f"{len(bad)} of the rule's cases: " + "; ".join(bad)
    return "ok", (f"{len(cases)} names, each linked only where certain and otherwise put to the "
                  "person with why; two winners taken to one member, neither linked")


def _elect_rep(mid, sur, first, county, n, chamber="H"):
    """A sitting member's roster row, as much of it as the rule reads."""
    return {"id": mid, "name": f"{sur}, {first}", "chamber": chamber, "county": county,
            "district": str(n), "slug": f"{first}-{sur}-{n}".lower()}


@check("build", "members-elect: the person's three widenings of 17 October 2026 link the 2024 "
                "winners they were made for, and still not Joelle for Joe, Louis for Louise, Pat "
                "Long, Patrick N. Long or a move the ballot does not settle",
       needs=("build_members_elect",))
def _elect_widened(BME):
    """The 2024 test (score_members_elect) left 24 winners the record knew
    for the person, and on 17 October 2026 the person widened the rule for
    three kinds of them. Each case here is a real 2024 winner with the
    sitting member's real id and seat as of that Election Day, so undoing a
    widening fails on the names it was made for:

      1. a Jr., Sr. or numeral on one side only is passed over: Thackston
         III, Tierney Jr., Melvin Sr., Kaczynski Jr., each re-elected to
         their own seat;
      2. for the seat's own sitting member, a first name of four letters or
         more that the other runs on from by two or more: Chris Herbert,
         Greg Hill, Doug Thomas -- and never three letters (Joelle Alexander
         is not Rep. Joe Alexander) or one letter more (Louis Andrus is not
         Rep. Louise Andrus), and never for a member of another seat;
      3. a sitting member who ran for another seat, on the exact name, the
         one sitting member of it, from the House to another district of
         their own county or to the Senate, with no other candidate on the
         ballot answering to them: three senators-elect and seven
         representatives-elect. Not Pat Long, elected senator, whose record
         says Patrick; not the first-term Patrick N. Long, because "Pat Long"
         was on the same ballot; not a move to another county, a senator's
         move, or a name a former member answers to as well.

    Joelle Alexander, Louis Andrus, the senator (a stand-in id), the former
    namesake and the moves to another county or seat are made up; the rest
    are the 2024 ballot's. Two different suffixes, one on each side, are
    _elect_rule's John Barnes Sr."""
    sitting = [
        _elect_rep("6938", "Thackston", "Dick", "Cheshire", 12),
        _elect_rep("8023", "Tierney", "James", "Coos", 1),
        _elect_rep("8419", "Melvin", "Charles", "Rockingham", 20),
        _elect_rep("915", "Kaczynski", "Thomas", "Strafford", 5),
        _elect_rep("856", "Herbert", "Christopher", "Hillsborough", 24),
        _elect_rep("943", "Hill", "Gregory", "Merrimack", 2),
        _elect_rep("907", "Thomas", "Douglas", "Rockingham", 16),
        _elect_rep("9165", "Alexander", "Joe", "Hillsborough", 29),
        _elect_rep("9920", "Andrus", "Louise", "Merrimack", 5),
        _elect_rep("10614", "Rochefort", "David", "Grafton", 1),
        _elect_rep("488", "McConkey", "Mark", "Carroll", 8),
        _elect_rep("5686", "McGough", "Tim", "Hillsborough", 12),
        _elect_rep("10577", "Brown", "Richard", "Carroll", 3),
        _elect_rep("10748", "Germana", "Nicholas", "Cheshire", 1),
        _elect_rep("10620", "Sellers", "John", "Grafton", 18),
        _elect_rep("9134", "Wilhelm", "Matthew", "Hillsborough", 40),
        _elect_rep("10666", "Corcoran", "Travis", "Hillsborough", 44),
        _elect_rep("502", "Boehm", "Ralph", "Hillsborough", 14),
        _elect_rep("9919", "Berry", "Ross", "Hillsborough", 39),
        _elect_rep("540", "Long", "Patrick", "Hillsborough", 23),
        _elect_rep("s24", "Altschiller", "Debra", "Rockingham", 24, chamber="S")]
    linked = [
        # 1. A suffix on one side only.
        ("H|Cheshire|12", "Dick H. Thackston III", "6938"),
        ("H|Coos|1", "James W. Tierney Jr.", "8023"),
        ("H|Rockingham|20", "Charles R. Melvin Sr.", "8419"),
        ("H|Strafford|5", "Thomas L. Kaczynski Jr.", "915"),
        # 2. The start of the first name, four letters or more, own seat.
        ("H|Hillsborough|24", "Chris Herbert", "856"),
        ("H|Merrimack|2", "Greg Hill", "943"),
        ("H|Rockingham|16", "Doug Thomas", "907"),
        ("H|Hillsborough|29", "Joe Alexander", "9165"),
        ("H|Merrimack|5", "Louise Andrus", "9920"),
        # 3. A move from the House, on the exact name.
        ("S|1", "David Rochefort", "10614"),
        ("S|3", "Mark McConkey", "488"),
        ("S|11", "Tim McGough", "5686"),
        ("H|Carroll|8", "Richard R. Brown", "10577"),
        ("H|Cheshire|15", "Nicholas Germana", "10748"),
        ("H|Grafton|10", "John Sellers", "10620"),
        ("H|Hillsborough|21", "Matthew B. Wilhelm", "9134"),
        ("H|Hillsborough|28", "Travis Corcoran", "10666"),
        ("H|Hillsborough|38", "Ralph G. Boehm", "502"),
        ("H|Hillsborough|44", "Ross Berry", "9919")]
    # The ballot: those winners, the two Longs, and Dylan Germana, elected in
    # Cheshire 1 the day Rep. Nicholas Germana moved out of it -- a surname
    # on the ballot twice, which is not a rival where the first names part.
    ballot = [(k, n) for k, n, _m in linked] + [
        ("S|20", "Pat Long"), ("H|Hillsborough|26", "Patrick N. Long"),
        ("H|Cheshire|1", "Dylan Germana")]
    refused = [
        ("H|Hillsborough|29", "Joelle Alexander", "only as the start"),
        ("H|Merrimack|5", "Louis Andrus", "only as the start"),
        ("H|Hillsborough|5", "Chris Herbert", "by a short form or its start"),
        ("S|20", "Pat Long", "by a short form or its start"),
        ("H|Hillsborough|26", "Patrick N. Long", "another candidate on the ballot answers"),
        ("H|Rockingham|5", "Ross Berry", "in another county"),
        ("H|Rockingham|20", "Debra Altschiller", "a sitting senator")]
    keys = {k for k, *_x in linked + refused}
    races = {k: {"counties": {k.split("|")[1]} if k.startswith("H|") else set()} for k in keys}
    people = BME.People(sitting, [], ballot)
    bad = []
    for key, name, mid in linked:
        p, why = BME.auto_link(key, name, people, races)
        if (p or {}).get("id") != mid:
            bad.append(f"{name} in {key} is not linked to {mid}: {why}")
    for key, name, said in refused:
        p, why = BME.auto_link(key, name, people, races)
        if p or said not in why:
            bad.append(f"{name} in {key}: {(p or {}).get('id')} ({why!r}), not refused for "
                       f"{said!r}")
    # A former member who answers to the name as well: the move is then the
    # person's to settle, as a returning namesake might be the winner.
    namesake = [{"id": "f1", "name": "Sellers, John", "chamber": "H", "county": "Grafton",
                 "district": "9", "slug": "john-sellers-graf-9"}]
    p, why = BME.auto_link("H|Grafton|10", "John Sellers",
                           BME.People(sitting, namesake, ballot), races)
    if p or "a former member answers to it too" not in why:
        bad.append(f"John Sellers with a former namesake: {(p or {}).get('id')} ({why!r})")
    assert not bad, f"{len(bad)} of the widened rule's cases: " + "; ".join(bad)
    return "ok", (f"{len(linked)} real 2024 winners linked by the widened rule; {len(refused) + 1} "
                  "kept for the person, Joelle Alexander, Louis Andrus and both Longs among them")


# THE 2024 ELECTION, READ AND SCORED (17 October 2026). The plan said to
# measure the matching rule on 2024 first, against something this project
# did not make, and the person saved the Secretary of State's 2024 results in
# records/sources/ to make that possible. Two checks, each run only where
# what it reads is on disk: the files read again must be the committed
# collected/election_2024.json, and the rule, run as of that Election Day,
# must link no winner to anyone but the person who took the seat. On 17
# October 2026: 424 winners, 293 linked and every one right, none wrong, 131
# left for the person -- 106 new, 24 the record knew, 1 who never sat. The
# same day the person widened the rule for three kinds of the 24
# (_elect_widened), and it links 310, still none wrong: 114 left, 7 of them
# the record knew.

@check("build", "the ballot questions: every card's rule is its kind's, the county files sum to the "
                "totals shown, 2022's Question No. 2 and 2026's are the Secretary of State's counts, "
                "no card says a school district adopted or failed anything, and the flip numbers are "
                "the least number of voters",
       needs=("build_elections", "parse_sos_questions"))
def _ballot_questions(BE, PSQ):
    """The ballot-question cards (stage 0 of the elections work, 11 November
    2026). Held to collected/ballot_questions.json and
    corrections/ballot_results.json, both tracked; where the spreadsheets are
    on disk, the file is read again from them."""
    qp, bp = Path("collected/ballot_questions.json"), Path("corrections/ballot_results.json")
    if not qp.exists() or not bp.exists():
        return "skip", "not here: collected/ballot_questions.json or corrections/ballot_results.json"
    doc = json.loads(qp.read_text(encoding="utf-8"))
    els = doc["elections"]
    # the committed file is what the saved spreadsheets say, where they are here
    if all((Path("records/sources") / s["file"]).exists() for s in doc["_source"]):
        r = _run([sys.executable, _paths.script("parse_sos_questions.py"), "--check"],
                 capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, f"parse_sos_questions --check: {(r.stdout or '') + (r.stderr or '')}"
    # every county adds up to the statewide figure, except the one the page says disagrees
    for day, qs in els.items():
        for q in qs:
            yes = sum(v[0] for v in q["counties"].values())
            no = sum(v[1] for v in q["counties"].values())
            assert len(q["counties"]) == 10, f"{day} {q['label']}: {len(q['counties'])} counties"
            if q.get("county_sum"):
                assert q["county_sum"] == [yes, no], f"{day} {q['label']}: county_sum is not the counties'"
                assert [yes, no] != [q["yes"], q["no"]]
            else:
                assert (yes, no) == (q["yes"], q["no"]), (
                    f"{day} {q['label']}: the counties add up to {yes}, {no}, the total says "
                    f"{q['yes']}, {q['no']}")
    q22 = {q["number"]: q for q in els["2022-11-08"]}
    assert (q22[2]["yes"], q22[2]["no"], q22[2]["kind"]) == (178339, 347838, "convention"), q22[2]
    q26 = {q["number"]: q for q in els["2026-11-03"]}
    assert (q26[2]["yes"], q26[2]["no"], q26[2]["kind"], q26[2].get("measure")) == (
        356374, 249144, "local_cap", "HB 1300"), q26[2]
    assert q26[2]["counties"]["Belknap"] == [18946, 10690] and q26[2]["counties"]["Sullivan"] == [10575, 7912]
    # the CACR rows the corrections file holds agree with the spreadsheets, but for the one
    # place the Secretary of State's own files disagree (2026, read from its summary)
    rows = json.loads(bp.read_text(encoding="utf-8"))["rows"]
    for day, qs in els.items():
        for q in qs:
            if q["kind"] != "cacr":
                continue
            mine = [r for r in rows if r["election"] == day and r["label"] == q["label"]]
            assert len(mine) == 1 and (mine[0]["yes"], mine[0]["no"]) == (q["yes"], q["no"]), (
                f"{day} {q['label']}: corrections/ballot_results.json and the spreadsheet differ")
    # the rule on each card comes from its kind
    banned = re.compile(r"\b(adopted|failed|passed|ratified|rejected|approved)\b", re.I)
    for day in els:
        cards = BE.question_cards(day, bp, qp)
        assert len(cards) == len(els[day]), f"{day}: {len(cards)} cards for {len(els[day])} questions"
        for c in cards:
            html_ = BE.ballot_block([c], Path("nowhere"), {})
            text = re.sub(r"<[^>]+>", " ", html_)
            rule = BE.question_rule(c)
            if c["kind"] == "cacr":
                assert "two thirds" in rule and "Article 100)" in rule, rule
                assert "3/5" not in text and "majority" not in re.sub(r"\s+", " ", rule)
                assert "Ratified" in text or "Not ratified" in text
            elif c["kind"] == "convention":
                assert "majority of the qualified voters" in rule and "Article 100(b)" in rule, rule
                assert "two thirds" not in text and "3/5" not in text, text
                assert "Approved" in text or "Not approved" in text
            else:
                assert "3/5 majority of the voters voting in the municipalities and wards" in rule, rule
                assert "RSA 32:5-i" in rule and "two thirds" not in text, text
                assert not banned.search(text.replace("approve the question", "")), (
                    f"a local tax cap card names an outcome: {banned.search(text).group(0)}")
                assert "decides nothing" in text and "voter would have" not in text \
                    and "voters would have" not in text, text
            if c["kind"] != "local_cap":
                assert "would have had to vote the other way" in text, text
    # the least number of voters that changes the result, by counting
    two = BE.two_thirds
    maj = lambda y, n: y > n
    for y, n in [(0, 5), (5, 0), (7, 3), (2, 1), (3, 3), (4, 2), (9, 4), (13, 7), (30, 61), (66, 33), (67, 33), (10, 11)]:
        want = 0
        while two(y, n) == two(*((y - want, n + want) if two(y, n) else (y + want, n - want))):
            want += 1
            if want > y + n:
                break
        assert BE.flip_two_thirds(y, n) == want, (y, n, BE.flip_two_thirds(y, n), want)
        want = 0
        while maj(y, n) == maj(*((y - want, n + want) if maj(y, n) else (y + want, n - want))):
            want += 1
            if want > y + n:
                break
        assert BE.flip_majority(y, n) == want, (y, n, BE.flip_majority(y, n), want)
    assert (BE.flip_two_thirds(329157, 194291), BE.flip_two_thirds(365359, 198791),
            BE.flip_two_thirds(452307, 237221), BE.flip_majority(178339, 347838)) == (
        19809, 10741, 7379, 84750)
    return "ok", ("ballot questions: " + ", ".join(f"{d}: {len(q)}" for d, q in els.items()))


@check("build", "members-elect: the results reader refuses a write-in winner the file does not "
                "name, and reads a county's later upload in place of the earlier",
       needs=("parse_sos_results",))
def _elect_reader_decisions(PSR):
    """The person's decisions of 17 October 2026 about parse_sos_results,
    held without the saved files. A write-in winner the file does not name
    is refused, not guessed: the scattered write-ins reaching the last
    seat's votes is refused, one short of it is read, and a race whose file
    counts none is read (and flagged by read_all, which _elect_2024_read_again
    holds on Hillsborough 12). A recount's re-download replaces the county's
    file: of a county's two uploads the later by the Secretary of State's
    number is read and the earlier named, the unnumbered first of all; two
    under one number are refused. (The third decision, that a printed
    floterial mark the towns contradict is flagged and decides nothing, is
    held on the four 2024 files that print one wrong, by
    _elect_2024_read_again's comparison of _notes.)"""
    cands = [{"name": "Ann Ames", "party": "r", "votes": 100, "write_in": False},
             {"name": "Bo Bell", "party": "d", "votes": 90, "write_in": False}]
    try:
        PSR.elect(cands, 1, "a race", scatter=100)
        raise AssertionError("scattered write-ins as many as the winner's 100 votes were read, "
                             "where an unnamed write-in may have won")
    except PSR.Refused as e:
        assert "may have won" in str(e), f"refused, but not for the write-ins: {e}"
    for scatter in (99, None):
        got = PSR.elect(cands, 1, "a race", scatter=scatter)
        assert [c["elected"] for c in got] == [True, False], (
            f"with scatter {scatter} the count does not elect Ann Ames: {got}")
    root = Path(tempfile.mkdtemp(prefix="gr-sos-files-"))
    try:
        d = root / PSR.SOURCES
        d.mkdir(parents=True)
        names = [f"2024-ge-house-{c}_0.xls" for c in PSR.COUNTIES if c not in ("belknap",
                                                                                   "hillsborough")]
        names += ["2024-ge-house-belknap.xls", "2024-ge-house-belknap_0.xlsx",
                  "2024-ge-house-hillsborough_7.xls", "2024-ge-house-hillsborough_8.xls",
                  "2024-ge-state-senate-district-1-24_4.xls"]
        for n in names:
            (d / n).write_bytes(b"")
        got = PSR.source_files(root, 2024)
        assert got["house"]["hillsborough"].name == "2024-ge-house-hillsborough_8.xls" and \
            got["house"]["belknap"].name == "2024-ge-house-belknap_0.xlsx", (
            f"the later uploads are not the ones read: {got['house']}")
        pairs = sorted((a.name, b.name) for a, b in got["replaced"])
        assert pairs == [("2024-ge-house-belknap.xls", "2024-ge-house-belknap_0.xlsx"),
                         ("2024-ge-house-hillsborough_7.xls", "2024-ge-house-hillsborough_8.xls")], (
            f"the files replaced are said as {pairs}")
        (d / "2024-ge-house-hillsborough_8.xlsx").write_bytes(b"")
        try:
            PSR.source_files(root, 2024)
            raise AssertionError("two Hillsborough files under one number, _8, were read")
        except PSR.Refused as e:
            assert "under one number" in str(e), f"refused, but not for the number: {e}"
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("write-ins the file does not name, as many as the last seat's votes, refused; "
                  "a county's later upload read in place of its earlier, two under one number "
                  "refused")


@check("build", "members-elect: the results reader reads the recount laid out as a row of "
                "RECOUNT <name> cells and a row of figures (2026 Rockingham 25), never as "
                "candidates, and refuses what it cannot tie to the candidate above",
       needs=("parse_sos_results",))
def _elect_reader_recount_under_town(PSR):
    """The third recount layout, held on a fixture of the file's shape
    (13 November 2026): a first header of four candidates and Write-Ins, the
    town's counts, a row of "RECOUNT <name, party>" with the spacing the file
    has, the recount's figures; then a continuation header with no Write-Ins
    label, the town's counts with the write-ins, a row of RECOUNT names with a
    bare RECOUNT over the write-ins, and the figures. The recounts are read, a
    candidate is never named RECOUNT, the first count stays beside them, and
    each way the layout can fail to tie is refused with its row."""
    import datetime as dt
    head = [["State of New Hampshire - 2026 STATE GENERAL ELECTION"],
            ["State Representatives - ROCKINGHAM County"], ["November 03, 2026"]]
    N = None

    def sheet(**over):
        rows = {
            "h1": ["District No. 25 (3)", "Ann Ames, d", "Bo Bell, d", "Cy Cole, r", "Di Dunn, r",
                   N, "Write-Ins"],
            "t1": ["Salem", 10, 20, 30, 40, N, N],
            "r1": [N, "RECOUNT  Ann Ames, d", "RECOUNT Bo Bell, d", "RECOUNT    Cy Cole, r",
                   "RECOUNT  Di Dunn, r", N, N],
            "f1": [N, 11, 21, 31, 41, N, N],
            "h2": [N, "Ed Eld, r", "Flo Fox, r", N, N, N, N],
            "t2": ["Salem", 50, 60, N, N, N, 7],
            "r2": [N, "RECOUNT Ed Eld, r", "RECOUNT   Flo Fox, r", N, N, N, "RECOUNT"],
            "f2": [N, 51, 61, N, N, N, 5]}
        rows.update(over)
        return head + list(rows.values())

    def read(rows):
        was = PSR.sheets
        PSR.sheets = lambda p: [("s", rows)]
        try:
            return PSR.read_house(Path("2026-ge-house-rockingham_1.xlsx"), "rockingham",
                                  dt.date(2026, 11, 3))
        finally:
            PSR.sheets = was

    seats, flo, d = read(sheet())[25]
    assert seats == 3, seats
    got = {c["name"]: (c["votes"], c["elected"]) for c in d["candidates"]}
    assert got == {"Ann Ames": (11, False), "Bo Bell": (21, False), "Cy Cole": (31, False),
                   "Di Dunn": (41, True), "Ed Eld": (51, True), "Flo Fox": (61, True)}, got
    assert d["recounted"] is True and d["scatter"] == 5 and d["towns"] == ["Salem"], d
    assert not any("RECOUNT" in c["name"].upper() for c in d["candidates"]), d["candidates"]
    firsts = {r["candidate"]: r["votes"] for r in d["town_rows"]
              if r["count_kind"] == "first" and r["row_kind"] == "candidate"}
    assert firsts["Ann Ames"] == 10 and firsts["Flo Fox"] == 60, firsts
    assert not any(r["in_race_count"] for r in d["town_rows"] if r["count_kind"] == "first"
                   and r["row_kind"] == "candidate"), "a first count is counted in the race"

    def refused(why, rows, *words):
        try:
            read(rows)
        except PSR.Refused as e:
            assert all(w in str(e) for w in words), f"{why}: refused, but not for it: {e}"
            return
        raise AssertionError(f"{why}: read, where it must be refused")
    r1 = sheet()[3 + 2]
    refused("a name that is not the candidate above it",
            sheet(r1=[N, "RECOUNT Bo Bell, d", "RECOUNT Ann Ames, d", "RECOUNT Cy Cole, r",
                      "RECOUNT Di Dunn, r", N, N]), "not the candidate above", "row 6")
    refused("a party that is not the candidate's",
            sheet(r1=[N, "RECOUNT Ann Ames, r"] + r1[2:]), "not the candidate above")
    refused("a name in a column that does not line up",
            sheet(r1=[N, N, "RECOUNT Ann Ames, d", "RECOUNT Bo Bell, d", "RECOUNT Cy Cole, r",
                      "RECOUNT Di Dunn, r", N]), "row 6")
    refused("a bare RECOUNT over a candidate's column",
            sheet(r1=[N, "RECOUNT", "RECOUNT Bo Bell, d", "RECOUNT Cy Cole, r",
                      "RECOUNT Di Dunn, r", N, N]), "bare RECOUNT")
    refused("a candidate with no recount cell",
            sheet(r1=[N, "RECOUNT Ann Ames, d", "RECOUNT Bo Bell, d", "RECOUNT Cy Cole, r", N, N,
                      N]), "no RECOUNT cell")
    refused("a bare RECOUNT over a column the header named nothing in",
            sheet(r2=[N, "RECOUNT Ed Eld, r", "RECOUNT Flo Fox, r", "RECOUNT", N, N,
                      "RECOUNT"]), "names no candidate or count")
    refused("no row of figures", sheet()[:3 + 3], "row 6", "no row of figures")
    refused("a blank row where the figures belong", sheet(f1=[N] * 7), "no row of figures")
    refused("a figure missing", sheet(f1=[N, 11, 21, N, 41, N, N]), "no figure in column 4")
    refused("a figure under no RECOUNT cell", sheet(f1=[N, 11, 21, 31, 41, 9, N]),
            "under no RECOUNT cell")
    refused("a figures row naming another town", sheet(f1=["Hampton", 11, 21, 31, 41, N, N]),
            "Hampton")
    refused("a bare RECOUNT with no figure under it", sheet(f2=[N, 51, 61, N, N, N, N]),
            "bare RECOUNT")
    refused("a text figure", sheet(f1=[N, 11, 21, "31", 41, N, N]), "where a count belongs")
    two = sheet()
    two.insert(3 + 2, ["Hampton", 1, 2, 3, 4, N, N])
    refused("a block of more than one town", two, "does not sit directly under the one town")
    apart = sheet()
    apart.insert(3 + 2, [N] * 7)
    refused("a RECOUNT row that is not directly under the town row", apart,
            "does not sit directly under the one town")

    # THE COUNT'S OWN LABEL (17 November 2026; 2026 Rockingham 13, Derry): the
    # first block's write-ins recounted under a cell "RECOUNT Write-Ins", and no
    # write-ins after it. Read as that column's recount; another count's label
    # over it, or the label over a candidate's column, is refused.
    named = dict(t1=["Salem", 10, 20, 30, 40, N, 3],
                 r1=[N, "RECOUNT  Ann Ames, d", "RECOUNT Bo Bell, d", "RECOUNT    Cy Cole, r",
                     "RECOUNT  Di Dunn, r", N, "RECOUNT Write-Ins"],
                 f1=[N, 11, 21, 31, 41, N, 4],
                 t2=["Salem", 50, 60, N, N, N, N], r2=[N, "RECOUNT Ed Eld, r", "RECOUNT   Flo Fox, r",
                                                      N, N, N, N],
                 f2=[N, 51, 61, N, N, N, N])
    seats, flo, d = read(sheet(**named))[25]
    got = {c["name"]: c["votes"] for c in d["candidates"]}
    assert got == {"Ann Ames": 11, "Bo Bell": 21, "Cy Cole": 31, "Di Dunn": 41, "Ed Eld": 51,
                   "Flo Fox": 61}, got
    assert d["recounted"] is True and d["scatter"] == 4, d
    assert not any("WRITE" in c["name"].upper() for c in d["candidates"]), d["candidates"]
    refused("another count's label over the write-ins",
            sheet(**dict(named, r1=named["r1"][:6] + ["RECOUNT Undervotes"])),
            "not a candidate's column", "row 6")
    refused("the write-ins label over a candidate's column",
            sheet(**dict(named, r1=[N, "RECOUNT Write-Ins"] + named["r1"][2:])), "row 6")
    return "ok", ("a row of RECOUNT names and a row of figures read as the recount of the "
                  "candidates above, never as new candidates; a RECOUNT naming the write-ins "
                  "read only over the write-ins; each way to mis-tie it refused")


@check("build", "members-elect: the Senate is read whole (2024's one file) or in parts (2026's "
                "fifteen, named for their districts), each part's later upload in place of its "
                "earlier; a gap, an overlap or a file holding other than its name is refused",
       needs=("parse_sos_results", "election_week"))
def _elect_senate_parts(PSR, EW):
    """THE SENATE IN PARTS (5 November 2026). The Secretary of State published
    2024's Senate results as one file, -district-1-24, and 2026's as fifteen:
    -1 to -9, -10-11, -12-13, -14-16, -17-18, -19-21 and -22-24. The reader
    takes either; election_week counts the Senate as one of its eleven files
    only once every district is held. Names and merges only: the files are
    empty here, and read_senate is not asked."""
    split = [f"2026-ge-state-senate-{n}.xlsx" for n in range(1, 10)] + [
        f"2026-ge-state-senate-{s}.xlsx" for s in ("10-11", "12-13", "14-16", "17-18", "19-21",
                                                    "22-24")]
    spans = [PSR.senate_span(n) for n in split]
    assert spans[0] == (1, 1) and spans[11] == (14, 16) and \
        PSR.senate_span("2024-ge-state-senate-district-1-24_4.xls") == (1, 24) and \
        PSR.senate_span("2026-ge-state-senate-14-16_2.xlsx") == (14, 16), (
        f"the names are not read for their districts: {spans[:2]}, {spans[11]}")
    for no in ("2026-ge-state-senate.xlsx", "2026-ge-state-senate-1-.xlsx",
               "2026-ge-us-senator-summary.xlsx", "2026-ge-executive-council-1.xlsx"):
        assert PSR.senate_span(no) is None, f"{no} was read as a State Senate file"
    root = Path(tempfile.mkdtemp(prefix="gr-sos-senate-"))
    was = os.getcwd()
    try:
        d = root / PSR.SOURCES
        d.mkdir(parents=True)
        for n in [f"2026-ge-house-{c}.xlsx" for c in PSR.COUNTIES] + split + [
                "2026-ge-state-senate-14-16_1.xlsx", "2026-ge-us-senator-summary.xlsx"]:
            (d / n).write_bytes(b"")
        got = PSR.source_files(root, 2026)
        names = [p.name for p in got["senate"]]
        assert len(names) == 15 and "2026-ge-state-senate-14-16_1.xlsx" in names and \
            "2026-ge-state-senate-14-16.xlsx" not in names, f"the parts read are {names}"
        assert [(a.name, b.name) for a, b in got["replaced"]] == [
            ("2026-ge-state-senate-14-16.xlsx", "2026-ge-state-senate-14-16_1.xlsx")], (
            f"the part replaced is said as {got['replaced']}")
        os.chdir(root)
        lines, complete, latest = EW.status("2026")
        assert lines[0].startswith("11 of 11") and \
            "2026-ge-state-senate-14-16_1.xlsx" in {p.name for p in latest}, (
            f"election_week with every part saved: {lines[:2]}")
        for name, why in (("2026-ge-state-senate-15.xlsx", "more than one saved file"),
                          ("2026-ge-state-senate-district-1-24.xlsx", "more than one saved file")):
            (d / name).write_bytes(b"")
            try:
                PSR.source_files(root, 2026)
                raise AssertionError(f"{name} beside the fifteen parts was read")
            except PSR.Refused as e:
                assert why in str(e), f"{name}: refused, but not for the overlap: {e}"
            (d / name).unlink()
        for p in d.glob("2026-ge-state-senate-14-16*"):
            p.unlink()
        try:
            PSR.source_files(root, 2026)
            raise AssertionError("the Senate was read without districts 14 to 16")
        except PSR.Refused as e:
            assert "district(s) 14, 15, 16" in str(e), f"refused, but not for the gap: {e}"
        lines, complete, _latest = EW.status("2026")
        assert lines[0].startswith("10 of 11") and not complete and \
            any("not saved yet for district(s) 14, 15, 16" in x for x in lines), (
            f"election_week with a part missing: {lines}")
    finally:
        os.chdir(was)
        shutil.rmtree(root, ignore_errors=True)
    rec = {"candidates": []}
    merged = PSR.senate_merged([("2026-ge-state-senate-1.xlsx", {1: rec}),
                                ("2026-ge-state-senate-14-16.xlsx", {14: rec, 15: rec, 16: rec})])
    assert sorted(merged) == [1, 14, 15, 16], f"merged {sorted(merged)}"
    for read, why in (([("2026-ge-state-senate-14-16.xlsx", {14: rec, 16: rec})], "its name says"),
                      ([("2026-ge-state-senate-14-16.xlsx", {14: rec, 15: rec, 16: rec, 17: rec})],
                       "its name says"),
                      ([("2026-ge-state-senate-1.xlsx", {1: rec}),
                        ("2026-ge-state-senate-1_2.xlsx", {1: rec})], "in both")):
        try:
            PSR.senate_merged(read)
            raise AssertionError(f"{[n for n, _ in read]} merged")
        except PSR.Refused as e:
            assert why in str(e), f"refused, but not as it should be: {e}"
    return "ok", ("2024's one Senate file and 2026's fifteen parts read for their districts, a "
                  "part's later upload in place of its earlier; an overlap, a gap and a file "
                  "holding other than its name refused, and election_week counts the Senate "
                  "once every district is saved")


@check("build", "members-elect: what the 2026 files write differently from 2024's is read, "
                "each odd cell flagged and nothing looser taken -- the day in words, a write-in "
                "named before its word, a Totals formula that leaves out a town, N/A for "
                "write-ins, a named write-in's empty cell, a place spelt whole or shortened",
       needs=("parse_sos_results",))
def _elect_2026_layout(PSR):
    """THE 2026 FILES, AS READ ON 5 NOVEMBER 2026. Each rule here was met in
    the Secretary of State's own 2026 files (src/parse/parse_sos_results.py
    names where), and each is held to its narrow case: the near miss beside
    it is still refused. No file is opened; Block is fed rows, and a formula
    as an .xlsx would give it."""
    import datetime
    day = datetime.date(2026, 11, 3)
    for v in ("November 03, 2026", "NOVEMBER 03, 2026", "November 3, 2026"):
        assert PSR.as_day(v) == day, f"{v!r} read as {PSR.as_day(v)}"
    for v in ("Nov 03, 2026", "3 November 2026", "November 03 2026", "11/03/2026", "Novembr 03, 2026"):
        assert PSR.as_day(v) is None, f"{v!r} was read as a day: {PSR.as_day(v)}"
    for v, name in (("WRITE-IN   Kathy DesRoches", "Kathy DesRoches"),
                    ("Amanda Allen       WRITE-IN", "Amanda Allen"),
                    ("Desiree McLaughlin                  WRITE-IN", "Desiree McLaughlin")):
        m = PSR.WRITE_IN.match(v)
        assert m and (m.group("name") or m.group("after")).strip() == name, f"{v!r}: {m}"
    for v in ("Write-Ins", "Amanda Allen", "Amanda WRITE-IN Allen"):
        assert not PSR.WRITE_IN.match(v), f"{v!r} was read as a named write-in"
    assert PSR.place_key("Thompson & Meserve's Purchase") == \
        PSR.place_key("Thompson & Mes's Purchase"), "the Purchase spelt whole is not the table's"
    assert PSR.one_place("Thompson & Meserve's", "Thompson & Mes's Purchase") and \
        PSR.one_place("Newfield", "Newfields") and not PSR.one_place("Thompson", "Thompson & "
                                                                     "Mes's Purchase") and \
        not PSR.one_place("Meserve's Purchase", "Thompson & Mes's Purchase"), (
        "a place shortened by more than its last word, or from the front, was taken")

    fake = Path(tempfile.gettempdir()) / "gr-sos-formulas-not-a-file.xlsx"
    key = str(fake.resolve())

    def block(rows, totals, ents, formula=None):
        PSR._FORMULAS[key] = {("s", totals[0], c): f for c, f in (formula or {}).items()}
        b = PSR.Block(ents, "the block", source=(fake, "s"))
        b.rows = [(t, r, f"f, sheet 's', row {n}") for n, t, r in rows]
        b.totals = (totals[1], f"f, sheet 's', row {totals[0]}") if totals else None
        return b

    cand = [{"name": "Ella", "party": "d", "write_in": False, "col": 1, "recount": None},
            {"name": "Brad", "party": "r", "write_in": False, "col": 2, "recount": None}]
    towns = [(47, "Canaan", ["Canaan", 1077, 653]), (48, "Dorchester", ["Dorchester", 75, 105]),
             (49, "Orange", ["Orange", 88, 63])]
    try:
        b = block(towns, (50, ["Totals", 1152, 821]), cand, {1: "=SUM(B47:B48)", 2: "=SUM(C47:C49)"})
        out = b.read(None)
        assert sum(v[0][0] for v in out.values()) == 1240 and len(b.notes) == 1 and \
            "leaves out Orange" in b.notes[0], f"the short Totals formula: {b.notes}"
        for formula, totals, why in (({1: "=SUM(B47:B49)"}, 1152, "covers every town"),
                                     ({1: "=SUM(C47:C48)"}, 1152, "another column"),
                                     ({1: "=SUM(B46:B48)"}, 1152, "a row that is no town"),
                                     ({1: "=SUM(B47:B48)"}, 1150, "not the towns it names"),
                                     ({}, 1152, "no formula, as an .xls")):
            try:
                block(towns, (50, ["Totals", totals, 821]), cand, formula).read(None)
                raise AssertionError(f"a Totals of {totals} with {formula} ({why}) was read")
            except PSR.Refused as e:
                assert "adds up to 1,240" in str(e), f"{why}: refused, but not as it should be: {e}"
        meta = cand + [{"meta": "scatter", "col": 3, "recount": None}]
        b = block([(29, "Merrimack", ["Merrimack", 6318, 6543, "N/A"])], None, meta)
        out = b.read(None)
        assert out["Merrimack"][2][0] is None and "N/A" in b.notes[0], f"N/A for write-ins: {out}"
        try:
            block([(29, "Merrimack", ["Merrimack", "N/A", 6543, 0])], None, meta).read(None)
            raise AssertionError("a candidate's N/A was read")
        except PSR.Refused as e:
            assert "where a count belongs" in str(e), f"a candidate's N/A: {e}"
        wi = cand + [{"name": "Desiree McLaughlin", "party": "", "write_in": True, "col": 3,
                      "recount": None}]
        wards = [(9, "Franklin Ward 1", ["Franklin Ward 1", 505, 418, None]),
                 (10, "Franklin Ward 2", ["Franklin Ward 2", 491, 433, 46]),
                 (11, "Franklin Ward 3", ["Franklin Ward 3", 575, 504, 45])]
        b = block(wards, (12, ["Totals", 1571, 1355, 91]), wi)
        out = b.read(None)
        assert out["Franklin Ward 1"][2][0] == 0 and any("empty cell" in n for n in b.notes), (
            f"the named write-in's empty cell the Totals account for: {out}")
        for totals, why in ((["Totals", 1571, 1355, None], "no Totals for the column"),
                            (["Totals", 1571, 1355, 92], "Totals that do not add up")):
            try:
                block(wards, (12, totals), wi).read(None)
                raise AssertionError(f"a named write-in's empty cell was read with {why}")
            except PSR.Refused as e:
                assert "empty" in str(e) or "adds up" in str(e), f"{why}: {e}"
        try:
            block([(9, "Franklin Ward 1", ["Franklin Ward 1", 505, 418, None])], None, wi).read(None)
            raise AssertionError("a one-town district's empty write-in cell was read")
        except PSR.Refused as e:
            assert "no Totals row accounts for it" in str(e), f"one town: {e}"
    finally:
        PSR._FORMULAS.pop(key, None)
    return "ok", ("the day in words, a write-in named either side of its word, a Totals formula "
                  "short of one town, N/A for write-ins, a named write-in's empty cell the Totals "
                  "account for, and a place spelt whole or shortened by its last word, read and "
                  "flagged; each near miss refused")


@check("build", "members-elect: the results page's address reaches /members_elect.json -- the "
                "reader writes --url into each _source, refuses one that is not https, and the "
                "step says so when the results name no address",
       needs=("parse_sos_results",))
def _elect_results_address(PSR):
    """README's The data says /members_elect.json carries "the address of
    the Secretary of State's results it was read from", and the Officials
    tab links "the Secretary of State's count" to it. build_members_elect
    takes it from each _source's url, and parse_sos_results wrote None there
    every time: the rehearsal of election week on 23 October 2026, the 2024
    count shifted to 2026, wrote a file whose "sources" was [], and the tab's
    link could never be drawn. The reader takes --url now. Held here: the
    _source entry carries the address given, and None without one; the
    reader refuses an address that is not https before it reads a file; and
    on the fixture's election the step writes the address into "sources",
    and with none says under NOTES that the file names no address."""
    absent = _elect_absent()
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    url = "https://www.sos.nh.gov/2026-general-election-results"
    root = Path(tempfile.mkdtemp(prefix="gr-elect-url-"))
    try:
        f = root / "records" / "sources" / "2026-ge-house-belknap.xls"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"stand-in")
        got = PSR.described(f, root, "2026-11-05", url)
        assert got["url"] == url and got["file"] == "records/sources/2026-ge-house-belknap.xls", (
            f"the reader's _source entry, given --url, is {got}")
        assert PSR.described(f, root, "2026-11-05")["url"] is None, (
            "the reader's _source entry names an address it was not given")
        r = _run([sys.executable, _paths.script("parse_sos_results.py"), "--year", "2026",
                  "--url", "http://www.sos.nh.gov/", "--districts", str(root / "none.json")],
                 cwd=root, capture_output=True, text=True, timeout=120)
        said = (r.stderr or "").strip().splitlines()
        assert r.returncode != 0 and said and "is not an https address" in said[-1], (
            "the reader takes an http address for the results: " + " / ".join(said[-2:]))
        assert not (root / "collected").exists(), "the reader wrote a file on a refused --url"
    finally:
        shutil.rmtree(root, ignore_errors=True)
    root = Path(tempfile.mkdtemp(prefix="gr-elect-url-step-"))
    try:
        _elect_fixture(root)
        results = root / "collected" / "election_2026.json"
        r = json.loads(results.read_text(encoding="utf-8"))
        for s in r["_source"]:
            s["url"] = url
        results.write_text(json.dumps(r), encoding="utf-8")
        code, out, doc = _elect_run(root, _ELECT_IN, hand=_ELECT_HAND)
        assert code == 0 and doc and doc["sources"] == [url], (
            f"with the address in _source the file's sources are {doc and doc['sources']}")
        assert "names no address" not in out, "the step says no address is named when one is"
        for s in r["_source"]:
            s["url"] = None
        results.write_text(json.dumps(r), encoding="utf-8")
        code, out, doc = _elect_run(root, _ELECT_IN, hand=_ELECT_HAND)
        assert code == 0 and doc and doc["sources"] == [], (
            f"with no address the file's sources are {doc and doc['sources']}")
        assert "names no address" in _elect_part(out, "NOTES"), (
            "the step is silent about results that name no address: " + out[-300:])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("--url written into each _source, an http address refused before any file is "
                  "read; the address in /members_elect.json's sources, and its absence said")


@check("data", "members-elect: the Secretary of State's 2024 results, read again, are "
               "collected/election_2024.json -- every column at the file's own Totals, every "
               "race at the district table's seats and towns", needs=("parse_sos_results",))
def _elect_2024_read_again(PSR):
    """parse_sos_results reads the saved spreadsheets and refuses a layout it
    does not recognise; this holds what it reads today to what was
    committed, so that a saved file changed since, or a reader changed in a
    way that reads them differently, is caught before a page draws it. And
    every race elects exactly its seats, which is the count the results
    file is for."""
    committed, table = Path("collected/election_2024.json"), Path("site/districts.json")
    missing = [p.as_posix() for p in (committed, table) if not p.exists()]
    if missing:
        return "skip", ("not here: " + ", ".join(missing)
                        + " -- the results are held to a built site's district table")
    try:
        doc = PSR.read_all(".", 2024, json.loads(table.read_text(encoding="utf-8")))
    except PSR.Unreadable as e:
        return "skip", str(e)
    except PSR.Refused as e:
        if not any(Path("records/sources").glob("2024-ge-*")):
            return "skip", "the 2024 results files are not in records/sources/"
        raise AssertionError(f"the reader refuses the saved 2024 files: {e}")
    diff = PSR.differences(doc, json.loads(committed.read_text(encoding="utf-8")))
    assert not diff, (f"collected/election_2024.json is not what the saved files say "
                      f"({len(diff)}): " + "; ".join(diff[:6]))
    short = [k for k, r in doc["races"].items()
             if sum(c["elected"] is True for c in r["candidates"]) != r["seats"]]
    assert not short, f"races whose winners are not their seats: {short[:6]}"
    return "ok", PSR.summary(doc) + f" {len(doc.get('_notes') or [])} flagged in _notes."


@check("build", "election town rows: the tie-out holds a column to the file's Totals, a race to its "
                "candidates' towns and its places to its towns, and the tables read back as written",
       needs=("election_town_rows",))
def _town_rows_tie_out_logic(ETR):
    """The tie-out is the check on the readers, so it is held to the cases it
    exists for: a consistent pair of tables passes, and each of a Totals row
    that disagrees with its towns, a race total that is not its towns' sum
    and a place the race does not name is reported, with its file and row.
    The tables are written to text and read back without a change."""
    def row(place, cand, votes, kind="candidate", at=5):
        cid = f"k.{cand}"
        return {"row_id": f"{cid}@{place}.first", "contest_id": "k", "candidate_id": cid,
                "count_kind": "first", "block_header_row": 4, "district_key": "H|X|1",
                "place": place, "place_district_table": place, "candidate": cand, "party": "d",
                "row_kind": kind, "in_race_count": True, "votes": votes, "source_file": "f.xls",
                "source_row": at, "source_sha256": "0" * 64}
    rows = [row("A", "Ann", 10), row("B", "Ann", 5, at=6),
            row("A", "scatter", 1, "write_ins_scattered"),
            row("B", "scatter", 2, "write_ins_scattered", 6)]
    totals = [{"contest_id": "k", "candidate_id": "k.Ann", "count_kind": "first",
               "block_header_row": 4, "district_key": "H|X|1", "candidate": "Ann",
               "row_kind": "candidate", "blc_adjusted": False, "printed_total": 15,
               "source_file": "f.xls", "source_sheet": "s", "source_row": 7}]
    races = {"H|X|1": {"seats": 1, "towns": ["A", "B"], "scatter": 3,
                       "candidates": [{"name": "Ann", "party": "d", "votes": 15}]}}
    table = {"H|X|1": {"seats": 1, "towns": ["A", "B"]}}
    ok = ETR.tie_out(rows, totals, races, table)
    assert not ok["disagreements"], ok["disagreements"]
    assert ok["checks"]["a column's towns sum to the file's Totals"]["held"] == 1, ok["checks"]
    bad = ETR.tie_out(rows, [dict(totals[0], printed_total=14)], races, None)
    assert [d["check"] for d in bad["disagreements"]] == [
        "a column's towns sum to the file's Totals"], bad["disagreements"]
    assert "row 7" in bad["disagreements"][0]["where"], bad["disagreements"]
    moved = ETR.tie_out(rows, totals, {"H|X|1": dict(races["H|X|1"], towns=["A"], candidates=[
        {"name": "Ann", "party": "d", "votes": 16}])}, table)
    assert {d["check"] for d in moved["disagreements"]} == {
        "a candidate's towns sum to the race's total", "a race's places are its towns"}, (
        moved["disagreements"])
    off = ETR.tie_out(rows, totals, races, {"H|X|1": {"seats": 1, "towns": ["A", "C"]}})
    assert [d["check"] for d in off["disagreements"]] == [
        "a race's places are the district table's"], off["disagreements"]
    back = ETR.from_csv(ETR.to_csv(rows, ["row_id", "in_race_count", "votes", "source_row"]))
    assert [r["votes"] for r in back] == [10, 5, 1, 2] and back[0]["in_race_count"] is True
    assert ETR.slug("Wendy Chase") == "wendy-chase" and ETR.slug("Kathy DesRoches") == "kathy-desroches"
    return "ok", "a Totals row, a race total and a place that disagree are each reported with their row"


@check("data", "election town rows: collected/election_town_rows_<year>.csv is what the saved "
               "files say, and collected/election_tieout.json is what they tie out to -- every "
               "disagreement the files have with themselves recorded, none corrected",
       needs=("parse_sos_results", "election_town_rows"))
def _town_rows_read_again(PSR, ETR):
    """Stage 1 of the elections plan (12 November 2026): the Secretary of
    State's town and ward rows, kept beside the race totals. Two halves. The
    committed tables, tied out against the committed results files and the
    printed Totals, give what collected/election_tieout.json records -- so a
    table edited by hand, or a disagreement that appears or goes, is a change
    to read, not a silent one. And where the saved files are on disk (and the
    district table, for 2022 on), reading them again writes the same tables."""
    years = (2016, 2018, 2020, 2022, 2024, 2026)
    recorded = json.loads(ETR.TIEOUT.read_text(encoding="utf-8"))
    table = Path("site/districts.json")
    districts = json.loads(table.read_text(encoding="utf-8")) if table.is_file() else None
    held_to_table = "a race's places are the district table's"
    lines, again = [], []
    for y in years:
        paths = (ETR.town_path(y), ETR.totals_path(y), Path(f"collected/election_{y}.json"))
        gone = [p.as_posix() for p in paths if not p.is_file()]
        assert not gone, f"not committed: {', '.join(gone)}"
        rows = ETR.from_csv(paths[0].read_text(encoding="utf-8"))
        totals = ETR.from_csv(paths[1].read_text(encoding="utf-8"))
        races = json.loads(paths[2].read_text(encoding="utf-8"))["races"]
        now = ETR.tie_out(rows, totals, races, None)
        want = recorded.get(str(y))
        assert want is not None, f"collected/election_tieout.json says nothing of {y}"
        now["checks"].pop(held_to_table, None)
        said = {k: v for k, v in want["checks"].items() if k != held_to_table}
        assert (now["checks"], now["disagreements"], now["kinds"]) == (
            said, want["disagreements"], want["kinds"]), (
            f"{y}: the committed tables tie out to something other than "
            "collected/election_tieout.json records")
        assert (len(rows), len(totals)) == (want["town_rows"], want["printed_totals"]), y
        assert not want["checks"].get(held_to_table, {}).get("disagree"), (
            f"{y}: a race whose places are not the district table's")
        lines.append(f"{y}: {len(rows):,} rows, {len(want['disagreements'])} disagreement(s)")
        if sorted(Path("records/sources").glob(f"{y}-*")) and (
                y < PSR.TABLE_SINCE or districts is not None):
            try:
                doc = PSR.read_all(".", y, districts if y >= PSR.TABLE_SINCE else None,
                                   partial=True)
            except PSR.Unreadable as e:
                return "skip", str(e)
            r2, t2 = ETR.tables(doc, PSR.BME.general_election(y))
            assert ETR.to_csv(r2, ETR.TOWN_COLUMNS) == paths[0].read_text(encoding="utf-8"), (
                f"{y}: collected/{paths[0].name} is not what the saved files say")
            assert ETR.to_csv(t2, ETR.TOTAL_COLUMNS) == paths[1].read_text(encoding="utf-8"), (
                f"{y}: collected/{paths[1].name} is not what the saved files say")
            again.append(y)
    return "ok", ("; ".join(lines) + ("; read again from the saved files: "
                                      + ", ".join(map(str, again)) if again else
                                      "; the saved files or the district table are not here, so "
                                      "only the committed tables were tied out"))


# THE OTHER OFFICES' RESULTS (17 November 2026; the model's step 6, the
# elections plan's stages 4 and 5): src/parse/parse_sos_offices.py reads the
# Secretary of State's Governor and US Senator files into
# collected/election_offices_<year>.json, and nothing on the site reads them
# yet. These checks hold the reader to made-up files, the committed files to
# the saved ones, and the pages to not reading them.

def _offices_book(path, rows, sheet="Sheet"):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    for r in rows:
        ws.append(r)
    wb.save(path)


def _offices_statewide_world(root, summary_fix=None, county_fix=None, drop=None):
    """A made-up 2026 Governor: a summary file and ten county files, each
    county two towns, Bob Baker ahead. `summary_fix(rows)` and
    `county_fix(county, rows)` change the rows before they are saved;
    `drop` leaves a county's file out."""
    import state_settings as ST
    src = Path(root) / "records" / "sources"
    src.mkdir(parents=True, exist_ok=True)
    title = [[None, "State of New Hampshire - General Election"], ["NOVEMBER 03, 2026", "Governor"]]
    summary = title + [["Summary By Counties", "Ann Able, d", "Bob Baker, r", None, "Write-Ins"]]
    totals = [0, 0, 0]
    for n, c in enumerate(ST.COUNTIES):
        towns = [[f"{c} Town A", 10 + n, 20 + n, None, 1], [f"{c} Town B", 5, 6, None, 0]]
        # Sullivan prints its candidates the other way round, and by surname.
        head = ([f"{c.upper()} COUNTY", "Baker, r", "Able, d", "Write-Ins"] if c == "Sullivan"
                else [f"{c.upper()} COUNTY", "Ann Able, d", "Bob Baker, r", None, "Write-Ins"])
        if c == "Sullivan":
            towns = [[t[0], t[2], t[1], t[4]] for t in towns]
        sums = [sum(t[k] or 0 for t in towns) for k in range(1, len(head))]
        rows = title + [head] + towns + [["TOTALS", *sums]]
        if county_fix:
            rows = county_fix(c, rows)
        a, b, w = (sums[1], sums[0], sums[2]) if c == "Sullivan" else (sums[0], sums[1], sums[3])
        summary.append([c, a, b, None, w])
        totals = [totals[0] + a, totals[1] + b, totals[2] + w]
        if c != drop:
            _offices_book(src / f"2026-ge-governor-{c.lower()}.xlsx", rows, f"{c.lower()} gov")
    summary.append(["TOTALS", totals[0], totals[1], 0, totals[2]])
    if summary_fix:
        summary = summary_fix(summary)
    _offices_book(src / "2026-ge-governor-summary.xlsx", summary, "summary gov")


@check("build", "other offices' results: the statewide reader matches a county's columns to the "
                "summary's by name and party, records every Totals and county row that disagrees "
                "with the places under it, and refuses what it cannot read",
       needs=("parse_sos_offices",))
def _offices_statewide_logic(PSO):
    """The reader of the Governor's and US Senator's files, on made-up 2026
    files (a summary and ten county files; the 2016-2024 workbook is the same
    blocks in one file). Consistent files tie out with nothing recorded, a
    county printing its columns in another order and by surname is matched to
    the summary's; a county's row in the summary that is not its file's
    Totals, and a Totals row that is not its towns' sum, are each recorded
    with the file and row; a missing county, a column that matches no
    candidate, and towns that would elect another candidate are refused."""
    with tempfile.TemporaryDirectory() as tmp:
        _offices_statewide_world(tmp)
        doc = PSO.read_year(tmp, 2026)
        race = doc["races"]["governor"]
        assert [(c["name"], c["elected"]) for c in race["candidates"]] == [
            ("Ann Able", False), ("Bob Baker", True)], race["candidates"]
        assert len(race["places"]) == 20 and race["count_from"] == "the summary's Totals", race
        sull = [p for p in race["places"] if p[0] == "Sullivan"][0]
        assert sull[2] == [10 + 9, 20 + 9, 1], f"Sullivan's columns not matched by name: {sull}"
        tied = PSO.tie_out(PSO.plain(doc))
        assert not tied["disagreements"], tied["disagreements"]
        assert tied["checks"]["a county's row in the summary is its block's Totals"]["held"] == 30
        assert "United States Senator" in doc.get("_not_on_file", []), doc.get("_not_on_file")

    def off_by(rows, row, col, n):
        rows[row][col] += n
        return rows
    with tempfile.TemporaryDirectory() as tmp:
        # Belknap's row in the summary (row 4) prints one vote more for Ann Able,
        # and its TOTALS one more too, so the summary still adds up.
        _offices_statewide_world(tmp, summary_fix=lambda r: off_by(off_by(r, 3, 1, 1), 13, 1, 1))
        tied = PSO.tie_out(PSO.plain(PSO.read_year(tmp, 2026)))
        checks = sorted({d["check"] for d in tied["disagreements"]})
        assert checks == ["a county's row in the summary is its block's Totals",
                          "a race's count is its places' sum"], tied["disagreements"]
        assert "2026-ge-governor-summary.xlsx, sheet 'summary gov', row 4" in \
            tied["disagreements"][0]["where"], tied["disagreements"][0]
    with tempfile.TemporaryDirectory() as tmp:
        # Coos's TOTALS (row 6 of its file) print one write-in more than its towns.
        _offices_statewide_world(tmp, county_fix=lambda c, r: off_by(r, 5, 4, 1)
                                 if c == "Coos" else r)
        tied = PSO.tie_out(PSO.plain(PSO.read_year(tmp, 2026)))
        sums = [d for d in tied["disagreements"]
                if d["check"] == "a column's places sum to the file's Totals"]
        assert len(sums) == 1 and "2026-ge-governor-coos.xlsx, sheet 'coos gov', row 6" in \
            sums[0]["where"], tied["disagreements"]
    refused = {}
    for name, kw in {
            "no county": {"drop": "Grafton"},
            "unknown column": {"county_fix": lambda c, r: [r[0], r[1], [r[2][0], "Ann Able, d",
                                                                        "Carl Cole, r", None,
                                                                        "Write-Ins"], *r[3:]]
                               if c == "Merrimack" else r},
            "another winner": {"county_fix": lambda c, r: off_by(off_by(r, 3, 1, 900), 5, 1, 900)
                               if c == "Hillsborough" else r}}.items():
        with tempfile.TemporaryDirectory() as tmp:
            _offices_statewide_world(tmp, **kw)
            try:
                PSO.read_year(tmp, 2026)
            except PSO.Refused as e:
                refused[name] = str(e)
    assert set(refused) == {"no county", "unknown column", "another winner"}, refused
    assert "Grafton" in refused["no county"], refused
    assert "Carl Cole" in refused["unknown column"] and "2026-ge-governor-merrimack.xlsx" in \
        refused["unknown column"], refused
    assert "elects someone other" in refused["another winner"], refused
    assert PSO.ends_with("Colin Van Ostern", "Van Ostern") and PSO.ends_with(
        "Raymond C. Peeples Jr.", "Peeples") and not PSO.ends_with("Ann Able", "Ble")
    assert PSO.parties_agree("lib", "l") and not PSO.parties_agree("d", "r")
    return "ok", ("ten county files matched to the summary (one by surname, in another order); a "
                  "county row and a Totals row that disagree each recorded with their file and "
                  "row; a missing county, an unknown column and another winner refused")


def _offices_council_book(path, fix=None):
    """A made-up 2020 Executive Council workbook: a sheet a district, Ann
    Able ahead in each; `fix(n, rows)` changes a district's rows."""
    import openpyxl
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for n in range(1, 6):
        towns = [[f"Town {n}A", 30 + n, 20, 1], [f"Town {n}B", 10, 5, 0]]
        rows = [["State of New Hampshire - General Election"],
                [f"Executive Council - District No. {n}"],
                ["November 3, 2020", "Ann Able, r", "Bob Baker, d", "Scatter"],
                *towns, ["Totals", *[sum(t[k] for t in towns) for k in (1, 2, 3)]]]
        if fix:
            rows = fix(n, rows)
        ws = wb.create_sheet(f"council {n}")
        for r in rows:
            ws.append(r)
    wb.save(path)


@check("build", "other offices' results: the district reader reads Congress and the Council a "
                "district a sheet, holds a file to the districts its name says, records a Totals "
                "row its towns do not make, reads a recount's column, and refuses the rest",
       needs=("parse_sos_offices",))
def _offices_district_logic(PSO):
    """The reader of the Representative in Congress's and Executive
    Councilor's files, on made-up ones: 2020's one Council workbook of five
    sheets, and 2026's one file a district. A race's count is its towns' sum;
    a Totals row that disagrees is recorded with its row, and refused where
    the printed figure would elect someone else; a recount's column is the
    count read; a workbook that holds other districts than its name says, a
    sheet of another election's day and a count in a column no header names
    are refused; a district with no file is listed as not on file."""
    src = lambda tmp: Path(tmp) / "records" / "sources"  # noqa: E731

    def doc_of(fix=None, name="2020-executive-council-district-1-5.xlsx"):
        with tempfile.TemporaryDirectory() as tmp:
            src(tmp).mkdir(parents=True)
            _offices_council_book(src(tmp) / name, fix)
            return PSO.read_year(tmp, 2020)
    doc = doc_of()
    keys = [k for k in doc["races"]]
    assert keys == [f"executive-council|{n}" for n in range(1, 6)], keys
    r1 = doc["races"]["executive-council|1"]
    assert [(c["name"], c["votes"], c["elected"]) for c in r1["candidates"]] == [
        ("Ann Able", 41, True), ("Bob Baker", 25, False)] and r1["scatter"] == 1, r1
    assert r1["contest"] == "2020-11-03.general.executive-council.1", r1["contest"]
    assert not PSO.tie_out(PSO.plain(doc))["disagreements"]
    assert "Representative in Congress" in doc["_not_on_file"], doc["_not_on_file"]

    def bump(district, col, by):
        def fix(n, rows):
            if n == district:
                rows[-1][col] += by
            return rows
        return fix
    tied = PSO.tie_out(PSO.plain(doc_of(bump(3, 2, 1))))
    assert [d["check"] for d in tied["disagreements"]] == [
        "a column's places sum to the file's Totals"], tied["disagreements"]
    assert "sheet 'council 3', row 6" in tied["disagreements"][0]["where"], tied
    refused = {}

    def recount(n, rows):
        if n == 2:
            rows[2] = rows[2][:2] + ["RECOUNT"] + rows[2][2:]
            for r in rows[3:-1]:
                r.insert(2, r[1] - 1)
            rows[-1].insert(2, rows[-1][1] - 2)
        return rows
    r2 = doc_of(recount)["races"]["executive-council|2"]
    assert r2.get("recounted") and r2["candidates"][0]["votes"] == 42 - 2, r2
    assert r2["columns"][:2] == ["Ann Able, r", "Ann Able, r (recount)"], r2["columns"]
    for name, kw in {
            "another winner": {"fix": bump(4, 2, 40)},
            "another district": {"fix": lambda n, r: [r[0], ["Executive Council - District "
                                                             "No. 4"], *r[2:]] if n == 5 else r},
            "another day": {"fix": lambda n, r: [r[0], r[1], ["November 8, 2016", *r[2][1:]],
                                                 *r[3:]] if n == 1 else r},
            "stray count": {"fix": lambda n, r: [*r[:3], r[3] + [None, 7], *r[4:]]
                            if n == 1 else r}}.items():
        try:
            doc_of(**kw)
        except PSO.Refused as e:
            refused[name] = str(e)
    assert set(refused) == {"another winner", "another district", "another day",
                            "stray count"}, refused
    assert "elect different people" in refused["another winner"], refused
    assert "district 4 twice" in refused["another district"], refused
    assert "2016-11-08" in refused["another day"], refused
    assert "which no header names" in refused["stray count"], refused
    with tempfile.TemporaryDirectory() as tmp:
        src(tmp).mkdir(parents=True)
        _offices_book(src(tmp) / "2026-ge-congressional-district-2.xlsx", [
            ["State of New Hampshire - General Election"], ["Congressional District 2"],
            ["NOVEMBER 03, 2026", "Ann Able, d", "Bob Baker, r", None, "Write-Ins"],
            ["Acworth", 5, 4, None, 0], ["Albany", 3, 1, None, 1], ["TOTALS", 8, 5, 0, 1]])
        doc = PSO.read_year(tmp, 2026)
    assert list(doc["races"]) == ["us-house|2"], list(doc["races"])
    assert "Representative in Congress, district 1" in doc["_not_on_file"], doc["_not_on_file"]
    assert doc["races"]["us-house|2"]["candidates"][0]["elected"] is True
    return "ok", ("five districts read from one workbook and one from its own file; a Totals row "
                  "that disagrees recorded with its row, a recount's column read, another winner, "
                  "a district twice, another day and a stray count refused, a district with no "
                  "file listed")


def _offices_county_book(path, fix1=None, fix2=None, county="BELKNAP"):
    """A made-up 2026 county offices file: a sheet of Sheriff, Attorney and
    commissioners at large side by side, and a sheet of commissioner
    districts under their banner, district 3 marked No Election. `fix1` and
    `fix2` change each sheet's rows."""
    import openpyxl
    title = [[None, "State of New Hampshire - 2026 STATE GENERAL ELECTION"],
             [None, f"{county} County Offices"]]
    one = title + [
        ["NOVEMBER 03, 2026", "SHERIFF", None, "ATTORNEY", None, None, "County Commissioners"],
        [None, "Ann Able, r&d", "Write-Ins", "Bob Baker, d", "Carl Cole, r", "Write-Ins",
         "Gus Gray, d", "Hal Hart, d", "Write-Ins"],
        ["Town A", 50, 1, 30, 20, 0, 40, 35, 1], ["Town B", 40, 0, 25, 22, 1, 30, 33, 0],
        ["Town C", 20, 2, 9, 12, 0, 15, 14, 0],
        ["TOTALS", 110, 3, 64, 54, 1, 85, 82, 1]]
    two = title + [
        [None, "County Commissioners"],
        ["NOVEMBER 03, 2026", "District 1", None, None, "District 2", None, "District 3"],
        [None, "Dan Dee, r", "Eve Eck, d", "Write-Ins", "Fay Fox, r", "Write-Ins", "No Election"],
        ["Town A", 30, 25, 0, None, None, None], ["Town B", None, None, None, 41, 2, None],
        ["Town C", 18, 20, 1, None, None, None], ["TOTALS", 48, 45, 1, 41, 2, 0]]
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows, fix in (("Sheriff Attorney", one, fix1), ("Commissioner", two, fix2)):
        ws = wb.create_sheet(name)
        for r in (fix(rows) if fix else rows):
            ws.append(r)
    wb.save(path)


@check("build", "other offices' results: the county reader splits a sheet of offices side by "
                "side into races by their labels, reads a commissioner district's own towns, "
                "lists a district marked No Election, keeps an at-large race's count with no "
                "winner, and refuses a race it cannot settle alone",
       needs=("parse_sos_offices",))
def _offices_county_logic(PSO):
    """The reader of the county offices, on a made-up 2026 file. Offices
    printed side by side are one race each, by the label over their columns;
    a commissioner district's race is the towns that print a count under it;
    a district marked No Election is listed and read as no race; the
    commissioners of an at-large race keep their count and no one is marked
    elected, the file printing no number of seats. A Totals cell that
    disagrees is recorded with its row; a race the reader cannot settle --
    a write-in the file does not name who may have won, a place's empty cell
    the Totals leave room for -- is refused alone and listed; a No Election
    mark among a race's candidates, and a sheet titled for another county,
    refuse the file."""
    src = lambda tmp: Path(tmp) / "records" / "sources"  # noqa: E731

    def doc_of(**kw):
        with tempfile.TemporaryDirectory() as tmp:
            src(tmp).mkdir(parents=True)
            _offices_county_book(src(tmp) / "2026-ge-county-offices-belknap.xlsx", **kw)
            return PSO.read_year(tmp, 2026)
    doc = doc_of()
    races = doc["races"]
    assert sorted(races) == ["county-attorney|Belknap", "county-commissioner|Belknap",
                             "county-commissioner|Belknap|1", "county-commissioner|Belknap|2",
                             "sheriff|Belknap"], sorted(races)
    assert [(c["name"], c["party"], c["votes"], c["elected"])
            for c in races["county-attorney|Belknap"]["candidates"]] == [
        ("Bob Baker", "d", 64, True), ("Carl Cole", "r", 54, False)], races["county-attorney|Belknap"]
    d1 = races["county-commissioner|Belknap|1"]
    assert [p[1] for p in d1["places"]] == ["Town A", "Town C"] and d1["seats"] == 1, d1
    assert d1["contest"] == "2026-11-03.general.county-commissioner.belknap-1", d1["contest"]
    assert [p[1] for p in races["county-commissioner|Belknap|2"]["places"]] == ["Town B"]
    large = races["county-commissioner|Belknap"]
    assert large["seats"] is None and all(c["elected"] is None for c in large["candidates"]), large
    assert doc.get("_no_election") == [{"race": "county-commissioner|Belknap|3", "where": (
        "2026-ge-county-offices-belknap.xlsx, sheet 'Commissioner', row 5"),
        "says": "No Election"}], doc.get("_no_election")
    assert "the county offices of Carroll, Cheshire, Coos, Grafton, Hillsborough, Merrimack, "\
        "Rockingham, Strafford, Sullivan" in doc["_not_on_file"], doc["_not_on_file"]
    assert not PSO.tie_out(PSO.plain(doc))["disagreements"]

    def cell(sheet_row, col, value):
        def fix(rows):
            rows = [list(r) for r in rows]
            rows[sheet_row][col] = value
            return rows
        return fix
    tied = PSO.tie_out(PSO.plain(doc_of(fix2=cell(8, 1, 49))))
    assert [d["where"] for d in tied["disagreements"]] == [
        "2026-ge-county-offices-belknap.xlsx, sheet 'Commissioner', row 9"], tied["disagreements"]
    alone = doc_of(fix1=cell(4, 2, 120))
    assert [r["race"] for r in alone.get("_refused", [])] == ["sheriff|Belknap"] and \
        "write-ins the file does not name" in alone["_refused"][0]["why"], alone.get("_refused")
    assert "county-attorney|Belknap" in alone["races"], "a refused race took its neighbours"
    room = doc_of(fix1=cell(5, 4, None))
    assert [r["race"] for r in room.get("_refused", [])] == ["county-attorney|Belknap"] and \
        "short of the Totals" in room["_refused"][0]["why"], room.get("_refused")
    refused = {}
    for name, kw in {"mark among candidates": {"fix2": cell(4, 2, "No Election")},
                     "another county": {"county": "CARROLL"}}.items():
        try:
            doc_of(**kw)
        except PSO.Refused as e:
            refused[name] = str(e)
    assert set(refused) == {"mark among candidates", "another county"}, refused
    assert "No Election" in refused["mark among candidates"], refused
    assert "CARROLL County Offices" in refused["another county"], refused
    quiet = doc_of(fix2=cell(4, 6, None))
    assert quiet["_no_election"][0]["says"] == "no candidate and no count", quiet["_no_election"]
    # A lone 0 under a district the place is not in (2016's Rockingham, Hampton).
    lone = doc_of(fix2=cell(6, 1, 0))
    assert [p[1] for p in lone["races"]["county-commissioner|Belknap|1"]["places"]] == [
        "Town A", "Town C"], lone["races"]["county-commissioner|Belknap|1"]["places"]
    assert any("Town B prints only a 0" in n for n in lone["_notes"]), lone["_notes"]
    return "ok", ("offices side by side split by their labels, a district's own towns read, No "
                  "Election listed, an at-large race left unmarked, a Totals cell recorded, two "
                  "races refused alone and a mark among candidates and another county refused")


@check("data", "other offices' results: collected/election_offices_<year>.json is what the saved "
               "files say, and collected/election_offices_tieout.json is what it ties out to -- "
               "every disagreement the files have with themselves recorded, none corrected",
       needs=("parse_sos_offices",))
def _offices_read_again(PSO):
    """The committed files, tied out again from what they hold, give what
    the tie-out file records, so a file edited by hand or a disagreement that
    appears or goes is a change to read, not a silent one. And where every
    file a year's _source names is on disk, reading them again writes the
    same document (the registry of downloads' page and day aside: it is on
    the person's computer, not in a checkout)."""
    recorded = json.loads(PSO.TIEOUT.read_text(encoding="utf-8"))
    lines, again = [], []
    for y in PSO.YEARS:
        path = PSO.out_path(y)
        assert path.is_file(), f"not committed: {path.as_posix()}"
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert PSO.tie_out(doc) == recorded.get(str(y)), (
            f"{y}: {path.as_posix()} ties out to something other than "
            f"{PSO.TIEOUT.as_posix()} records")
        for key, race in doc["races"].items():
            won = sum(c["elected"] is True for c in race["candidates"])
            assert race["seats"] is None or won == race["seats"] or any(
                c["elected"] is None for c in race["candidates"]), (
                f"{y} {key}: {won} elected for {race['seats']} seat(s)")
        lines.append(f"{y}: {len(doc['races'])} races, "
                     f"{len(recorded[str(y)]['disagreements'])} disagreement(s)")
        if all(Path(s["file"]).is_file() for s in doc["_source"]):
            try:
                now = PSO.plain(PSO.read_year(".", y))
            except PSO.PSR.Unreadable as e:
                return "skip", str(e)
            assert PSO.same_but_days(now, doc), (
                f"{y}: {path.as_posix()} is not what the saved files say: run "
                "python3 src/parse/parse_sos_offices.py --all --check")
            again.append(y)
    return "ok", ("; ".join(lines) + ("; read again from the saved files: "
                                      + ", ".join(map(str, again)) if again else
                                      "; the saved files are not here, so only the committed "
                                      "files were tied out"))


@check("files", "other offices' results: nothing on the site reads collected/election_offices_*"
                ".json or the reader that writes them yet -- readers only, until the pages are "
                "decided",
       needs=("parse_sos_offices",))
def _offices_read_by_nothing(PSO):
    """The model's step 6 is readers only (reports/refactor/design-model-
    2026-11-16.md, section 3): the pages come later, each its own change.
    Read off every code file of the code folders and the site's scripts, the
    suite aside: no Python file imports parse_sos_offices or names its files
    in a string, and no script names them; the reader's own files are the
    only ones that do. The State Primary's reader of the same offices
    (parse_sos_primary_offices) reads with its rules, a reader too, and no
    page: _primaries_read_by_nothing holds that nothing reads it."""
    import ast
    own = {Path(PSO.__file__).resolve(),
           Path(PSO.__file__).with_name("parse_sos_primary_offices.py").resolve()}
    hits = []
    for f in _paths.code_files("*.py"):
        if _in_suite(f) or f.resolve() in own:
            continue
        for n in ast.walk(_parsed(f)):
            if isinstance(n, ast.Import) and any(a.name == "parse_sos_offices" for a in n.names):
                hits.append(f"{f.name}:{n.lineno} imports parse_sos_offices")
            elif isinstance(n, ast.ImportFrom) and n.module == "parse_sos_offices":
                hits.append(f"{f.name}:{n.lineno} imports from parse_sos_offices")
            elif isinstance(n, ast.Constant) and isinstance(n.value, str) and (
                    "election_offices" in n.value or "parse_sos_offices" in n.value):
                hits.append(f"{f.name}:{n.lineno} names {n.value[:60]!r}")
    # versions.json is the stamps' list, written by inventory.py and ignored by git.
    scripts = [f for pat in ("*.js", "*.json", "*.yml") for f in _paths.code_files(pat)
               if f.name != "versions.json"]
    for f in scripts:
        text = _source(f, errors="replace")
        if "election_offices" in text or "parse_sos_offices" in text:
            hits.append(f"{f.name} names them")
    assert not hits, "something reads the other offices' results: " + "; ".join(hits[:8])
    return "ok", (f"no code file but the reader names collected/election_offices_* or imports "
                  f"parse_sos_offices ({len(scripts)} scripts and every Python file read)")


@check("build", "State Primary results: the House and Senate reader reads each party's primary as its "
                "own race -- an empty cell under a candidate is none, a Totals row's empty cell no "
                "figure, the nominees the most votes as many as the seats, a tie or what the unnamed "
                "write-ins could take left unsettled -- holds each race to the year's general "
                "election, and lists a file it cannot read instead of guessing",
       needs=("parse_sos_primary_results",))
def _primary_reader_reads(P):
    """parse_sos_primary_results (19 November 2026: every official's whole
    election record, primaries included) on a fixture of two parties' House
    files, one refused, and a 2018-style Senate sheet read alone."""
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        return "skip", "openpyxl is not installed"
    import datetime
    PSR = P.PSR
    # The rule, alone: the most votes as many as the seats, none with no votes,
    # a tie for the last place null, and a nominee the unnamed write-ins could
    # displace null.
    marks = [c["nominated"] for c in P.nominate(
        [{"name": "a", "votes": 9}, {"name": "b", "votes": 5}, {"name": "c", "votes": 5},
         {"name": "d", "votes": 0}], 2, "x", 0)]
    assert marks == [True, None, None, False], f"a tie for the last of two places: {marks}"
    marks = [c["nominated"] for c in P.nominate(
        [{"name": "a", "votes": 9}, {"name": "b", "votes": 4}], 2, "x", 3)]
    assert marks == [True, True], f"3 unnamed votes cannot displace 4 or 9: {marks}"
    marks = [c["nominated"] for c in P.nominate(
        [{"name": "a", "votes": 9}, {"name": "b", "votes": 4}], 2, "x", 8)]
    assert marks == [True, None], f"8 unnamed votes could take the place 4 holds, not 9's: {marks}"
    marks = [c["nominated"] for c in P.nominate([{"name": "a", "votes": 4}], 1, "x", 4)]
    assert marks == [None], f"4 unnamed votes could displace a nominee of 4: {marks}"
    root = Path(tempfile.mkdtemp(prefix="gr-sos-primary-"))
    try:
        d = root / PSR.SOURCES
        d.mkdir(parents=True)
        (root / "collected").mkdir()
        (root / "collected" / "election_2024.json").write_text(json.dumps({"races": {
            "H|Belknap|1": {"seats": 1, "floterial": False, "towns": ["Alpha", "Beta"]},
            "H|Belknap|2": {"seats": 2, "floterial": True, "towns": ["Gamma"]}}}), encoding="utf-8")
        day = datetime.date(2024, 9, 10)

        def book(name, county_line, rows, title="State of New Hampshire - 2024 Primary Election"):
            _legacy_book(d / name, [[title], [county_line], [day], *rows])
        book("2024-sp-house-belknap-democratic.xlsx",
             "State Representatives - BELKNAP County - Democratic", [
                 ["District No. 1 (1)", "Ann Ash, d", "Bo Birch, d", "Cy Cole, r", "Write-Ins",
                  "Overvotes", "Undervotes"],
                 ["Alpha", 100, 90, None, 1, 0, 5], ["Betta", 50, 40, 2, 0, 0, 3],
                 ["Totals", 150, 130, None, 1, 0, 8],
                 ["District No. 2 (2)", "Di Dunn, d", "Ed Eve, r", "WRITE-IN Flo Fay", "Write-Ins",
                  "Overvotes", "Undervotes"],
                 ["Gamma", 40, 30, 30, 3, 0, 1]])
        book("2024-sp-house-belknap-republican_1.xlsx",
             "State Representatives - BELKNAP County - Republican", [
                 ["District No. 1 (1)", "Ann Ash, d", "Gil Gray, r", "Write-Ins", "Overvotes",
                  "Undervotes"],
                 ["Alpha", 2, None, 5, 0, 1], ["Beta", None, None, 0, 0, 1],
                 ["Totals", 2, None, 5, 0, 2],
                 ["District No. 2 (2)", "Ed Eve, r", "Write-Ins", "Overvotes", "Undervotes"],
                 ["Gamma", None, 4, 0, 1]])
        # An earlier upload of the same name, replaced by the later (_1).
        shutil.copy(d / "2024-sp-house-belknap-republican_1.xlsx",
                    d / "2024-sp-house-belknap-republican_0.xlsx")
        book("2024-sp-house-carroll-democratic.xlsx",
             "State Representatives - CARROLL County - Democratic",
             [["District No. 1 (1)", "Hy Hale, d"], ["Delta", 3]],
             title="State of New Hampshire - 2024 General Election")
        doc = P.read_year(root, 2024)
        races = doc["races"]
        assert sorted(races) == ["D|H|Belknap|1", "D|H|Belknap|2", "R|H|Belknap|1",
                                 "R|H|Belknap|2"], f"races: {sorted(races)}"

        def got(k):
            return [(c["name"], c["party"], c["votes"], c["nominated"]) for c in races[k]["candidates"]]
        d1 = races["D|H|Belknap|1"]
        assert d1["towns"] == ["Alpha", "Beta"] and d1["party"] == "d", f"D 1's towns: {d1}"
        assert got("D|H|Belknap|1") == [("Ann Ash", "d", 150, True), ("Bo Birch", "d", 130, False),
                                        ("Cy Cole", "r", 2, False)], f"D 1: {got('D|H|Belknap|1')}"
        assert d1["printed_totals"] == 5, (
            f"the Totals row held {d1['printed_totals']} figures, not the five it prints")
        assert got("D|H|Belknap|2") == [("Di Dunn", "d", 40, True), ("Ed Eve", "r", 30, None),
                                        ("Flo Fay", "", 30, None)], f"D 2: {got('D|H|Belknap|2')}"
        assert races["D|H|Belknap|2"]["floterial"] is True, "the general's floterial was not written"
        assert got("R|H|Belknap|1") == [("Ann Ash", "d", 2, None), ("Gil Gray", "r", 0, False)], (
            f"R 1: five unnamed write-ins could have outpolled Ash's two: {got('R|H|Belknap|1')}")
        r2 = races["R|H|Belknap|2"]
        assert r2.get("open") == 2 and got("R|H|Belknap|2") == [("Ed Eve", "r", 0, False)], f"R 2: {r2}"
        notes = doc["_notes"]
        for words in ("'Betta', read as Beta", "empty cell(s) under a candidate, read as none",
                      "replaces 2024-sp-house-belknap-republican_0.xlsx",
                      "whether one of them was nominated is not in the file"):
            assert any(words in n for n in notes), f"not said: {words!r}"
        assert [r["file"] for r in doc["_refused"]] == ["2024-sp-house-carroll-democratic.xlsx"], (
            f"the general's title in a primary file was not refused and listed: {doc.get('_refused')}")
        assert [s["file"] for s in doc["_source"]] == [
            "records/sources/2024-sp-house-belknap-democratic.xlsx",
            "records/sources/2024-sp-house-belknap-republican_1.xlsx"], f"sources: {doc['_source']}"
        assert json.loads(P.dumps(doc))["races"] == races, "dumps did not go round"
        # A race the general election does not hold as the primary has it is refused alone.
        (root / "collected" / "election_2024.json").write_text(json.dumps({"races": {
            "H|Belknap|1": {"seats": 2, "floterial": False, "towns": ["Alpha", "Beta"]},
            "H|Belknap|2": {"seats": 2, "floterial": True, "towns": ["Gamma"]}}}), encoding="utf-8")
        again = P.read_year(root, 2024)
        assert sorted(again["races"]) == ["D|H|Belknap|2", "R|H|Belknap|2"] and sorted(
            r.get("race") for r in again["_refused"] if r.get("race")) == [
            "D|H|Belknap|1", "R|H|Belknap|1"], f"seats unlike the general's: {again.get('_refused')}"
        # A Senate sheet of 2018: a title one letter off, a minus sign for none,
        # and the places nobody voted in named in a note under the Totals.
        _legacy_book(d / "senate.xlsx", [
            ["New Hampshire Primary Election - September 11, 2018"],
            ["State Sente District No. 1 - Democratic"],
            [None, "Ash, d", "Bly, r", "Scatter"], ["Alpha", 10, "−", 1], ["Totals", 10, "−", 1],
            [], ["No votes cast: Beta; Gamma,"], ["Delta"]])
        said = []
        s = P.read_senate(d / "senate.xlsx", P.Primary(2018, "democratic"), True, (1, 1), said)
        assert s[1]["towns"] == ["Alpha"] and s[1]["no_votes"] == ["Beta", "Gamma", "Delta"], (
            f"the note's places: {s[1].get('no_votes')}")
        assert [(c["name"], c["votes"], c["nominated"]) for c in s[1]["candidates"]] == [
            ("Ash", 10, True), ("Bly", 0, False)], f"the Senate count: {s[1]['candidates']}"
        assert any("one letter off" in n for n in said), f"the mistyped title was not said: {said}"
        try:
            P.read_senate(d / "senate.xlsx", P.Primary(2018, "republican"), True, (1, 1), [])
            raise AssertionError("a Democratic district read as the Republican primary's")
        except PSR.Refused as e:
            assert "another party's primary" in str(e), f"refused, but not for the party: {e}"
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("an empty cell none and a Totals' empty cell no figure; nominees, a tie and what the "
                  "unnamed write-ins could take; the general's towns, seats and floterial; a later "
                  "upload, a refused file listed, a race refused alone; a 2018 Senate sheet's note of "
                  "places and its mistyped title")


@check("data", "State Primary results: collected/primary_<year>.json is what the saved files say, "
               "each race's nominees no more than its seats and every unsettled one said",
       needs=("parse_sos_primary_results",))
def _primary_read_again(P):
    """Where every file a year's document read, or refused, is on disk,
    reading them again writes the same document (the days the files were
    saved aside: a checkout does not keep them)."""
    lines, again = [], []
    for y in P.YEARS:
        path = P.out_path(y)
        assert path.is_file(), f"not committed: {path.as_posix()}"
        doc = json.loads(path.read_text(encoding="utf-8"))
        unsettled = 0
        for key, race in doc["races"].items():
            won = sum(c["nominated"] is True for c in race["candidates"])
            # The at-large commissioners of 2016-2022 print no number of seats.
            assert race["seats"] is None or won <= race["seats"], (
                f"{y} {key}: {won} nominated for {race['seats']} seat(s)")
            if any(c["nominated"] is None for c in race["candidates"]):
                unsettled += 1
                assert any(f"{key}: " in n and "not settled" in n for n in doc.get("_notes") or []), (
                    f"{y} {key}: a nominee left unsettled and not said")
        lines.append(f"{y}: {len(doc['races'])} races, {unsettled} unsettled, "
                     f"{len(doc.get('_refused') or [])} refused")
        files = [Path(s["file"]) for s in doc["_source"]] + [
            P.SOURCES / r["file"] for r in doc.get("_refused") or []]
        if files and all(f.is_file() for f in files):
            try:
                now = P.read_year(".", y)
            except P.PSR.Unreadable as e:
                return "skip", str(e)
            assert P.same_but_days(now, doc), (
                f"{y}: {path.as_posix()} is not what the saved files say: run "
                "python3 src/parse/parse_sos_primary_results.py --all --check")
            again.append(y)
    return "ok", ("; ".join(lines) + ("; read again from the saved files: " + ", ".join(map(str, again))
                                      if again else "; the saved files are not here, so only the "
                                      "committed files were held to their seats"))


@check("files", "State Primary results: nothing on the site reads collected/primary_*.json or the "
                "readers that write them yet -- readers only, until the elections display is decided",
       needs=("parse_sos_primary_results",))
def _primaries_read_by_nothing(P):
    """As _offices_read_by_nothing has it for the general's other offices:
    no Python file of the code folders but the primary readers imports them
    or names their files in a string (a docstring that names them is no
    reader), and no script names them."""
    import ast
    own = {Path(P.__file__).resolve(), Path(P.__file__).with_name("parse_sos_primary_offices.py").resolve()}
    mods = ("parse_sos_primary_results", "parse_sos_primary_offices")
    hits = []
    for f in _paths.code_files("*.py"):
        if _in_suite(f) or f.resolve() in own:
            continue
        tree = _parsed(f)
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and n.body and isinstance(n.body[0], ast.Expr)
                and isinstance(n.body[0].value, ast.Constant)}
        for n in ast.walk(tree):
            if id(n) in docs:
                continue
            if isinstance(n, ast.Import) and any(a.name in mods for a in n.names):
                hits.append(f"{f.name}:{n.lineno} imports a primary reader")
            elif isinstance(n, ast.ImportFrom) and n.module in mods:
                hits.append(f"{f.name}:{n.lineno} imports from a primary reader")
            elif isinstance(n, ast.Constant) and isinstance(n.value, str) and (
                    "primary_20" in n.value or "primary_<year>" in n.value
                    or any(m in n.value for m in mods)):
                hits.append(f"{f.name}:{n.lineno} names {n.value[:60]!r}")
    scripts = [f for pat in ("*.js", "*.json", "*.yml") for f in _paths.code_files(pat)
               if f.name != "versions.json"]
    for f in scripts:
        text = _source(f, errors="replace")
        if re.search(r"primary_(?:20\d\d|<year>)|parse_sos_primary", text):
            hits.append(f"{f.name} names them")
    assert not hits, "something reads the State Primary results: " + "; ".join(hits[:8])
    return "ok", (f"no code file but the readers names collected/primary_* or imports them "
                  f"({len(scripts)} scripts and every Python file read)")


@check("build", "State Primary results: the other offices' reader reads each party's primary for "
                "Governor and Senator (the summary and every county's towns), Congress and the "
                "Council, and the county offices, as the general's reader does -- an empty cell "
                "none, a summary's empty Totals its counties' rows, 2018's day at the end of the "
                "State's title, a sheet with no day -- and lists a file of another party refused",
       needs=("parse_sos_primary_offices",))
def _primary_offices_reader_reads(PO):
    """parse_sos_primary_offices on a fixture: a 2024 Republican Governor
    workbook (a summary and ten counties' sheets, one printing no day), a
    2018 Democratic Congress sheet, a 2024 county offices sheet of two races,
    and a Congress file whose title is the other party's."""
    try:
        import openpyxl
    except ImportError:
        return "skip", "openpyxl is not installed"
    import datetime
    PSR, PSO = PO.PSR, PO.PSO
    root = Path(tempfile.mkdtemp(prefix="gr-sos-primary-offices-"))
    try:
        d = root / PSR.SOURCES
        d.mkdir(parents=True)
        day = datetime.date(2024, 9, 10)
        heads = ["Al Ash, r", "Bo Bly, r", "Cy Cole, d", "Write-Ins", "Overvotes", "Undervotes"]
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sum Gov"
        for r in ([None, "State of New Hampshire - Primary Election"], [day, "Governor - Republican"],
                  ["Summary By Counties", *heads],
                  *[[c, 10, 5, 1 if c == "Belknap" else None, 1, 0, 2] for c in PSO.COUNTIES],
                  ["TOTALS", 100, 50, None, 10, 0, 20]):
            ws.append(r)
        for c in PSO.COUNTIES:
            ws = wb.create_sheet(f"{c} Gov")
            cole = 1 if c == "Belknap" else None
            for r in ([None, "State of New Hampshire - Primary Election"],
                      [None if c == "Coos" else day, "Governor - Republican"],
                      [f"{c} County", *heads], [f"{c} Town", 10, 5, cole, 1, 0, 2],
                      ["TOTALS", 10, 5, cole, 1, 0, 2]):
                ws.append(r)
        wb.save(d / "2024-sp-governor-republican_2.xlsx")
        _legacy_book(d / "2024-sp-county-offices-belknap-republican_1.xlsx", [
            ["State of New Hampshire - 2024 Primary Election"], ["Belknap County Offices - Republican"],
            [day, "Sheriff", None, None, None, "Attorney"],
            [None, "Bill Wright, r", "Write-Ins", "Overvotes", "Undervotes", "Keith Cormier, d",
             "Write-Ins", "Overvotes", "Undervotes"],
            ["Alton", 100, 1, 0, 3, None, 5, 0, 90], ["Barnstead", 50, 0, 0, 1, 2, 1, 0, 40],
            ["TOTALS", 150, 1, 0, 4, 2, 6, 0, 130]])
        _legacy_book(d / "2024-sp-congressional-district-2-democratic_4.xlsx", [
            ["State of New Hampshire - Primary Election"], ["Congressional District 2 - Republican"],
            [day, "Ann Ash, d", "Write-Ins"], ["Alpha", 5, 0]])
        _legacy_book(d / "2018-sp-congressional-district-1-democratic_0.xlsx", [
            ["New Hampshire Primary Election - September 11, 2018"],
            ["Congressional District 1 Democratic"],
            # 2018's Congress prints no party after a name; and the minus sign.
            [None, "Di Dunn", "Ed Eve, r", "Scatter"], ["Alpha", 30, "−", 2],
            ["Beta", 20, None, 1], ["Totals", 50, None, 3]])
        races, read, notes, refused, bad = PO.read_year(root, 2024)
        assert sorted(races) == ["R|county-attorney|Belknap", "R|governor", "R|sheriff|Belknap"], (
            f"races: {sorted(races)}")

        def got(r):
            return [(c["name"], c["votes"], c["nominated"]) for c in r["candidates"]]
        gov = races["R|governor"]
        assert got(gov) == [("Al Ash", 100, True), ("Bo Bly", 50, False), ("Cy Cole", 1, False)], (
            f"the Governor: {got(gov)}")
        assert gov["contest"] == "2024-09-10.primary-r.governor.statewide" and gov["party"] == "r", (
            f"the Governor's contest: {gov['contest']}")
        assert gov["printed_totals"] > 0 and not bad, f"tie-out: {gov['printed_totals']}, {bad}"
        for words in ("print no figure for Cy Cole, d; read as its counties' rows, 1",
                      "prints no day; read as the primary of 2024-09-10"):
            assert any(words in n for n in notes), f"not said: {words!r}"
        assert got(races["R|sheriff|Belknap"]) == [("Bill Wright", 150, True)], (
            f"the Sheriff: {got(races['R|sheriff|Belknap'])}")
        att = races["R|county-attorney|Belknap"]
        assert got(att) == [("Keith Cormier", 2, None)] and att["scatter"] == 6, (
            f"two votes against six the file does not name: {got(att)}")
        assert any("R|county-attorney|Belknap: Keith Cormier not settled" in n for n in notes), (
            "the unsettled nominee was not said")
        assert [r["file"] for r in refused] == ["2024-sp-congressional-district-2-democratic_4.xlsx"], (
            f"the other party's title was not refused and listed: {refused}")
        assert [p.name for p in read] == ["2024-sp-governor-republican_2.xlsx",
                                          "2024-sp-county-offices-belknap-republican_1.xlsx"], (
            f"read: {[p.name for p in read]}")
        races, read, notes, refused, bad = PO.read_year(root, 2018)
        assert got(races["D|us-house|1"]) == [("Di Dunn", 50, True), ("Ed Eve", 0, False)], (
            f"2018's Congress: {races}")
        assert races["D|us-house|1"]["contest"] == "2018-09-11.primary-d.us-house.1", (
            races["D|us-house|1"]["contest"])
        assert any("'Di Dunn', whose party the file leaves out" in n for n in notes), (
            "a name with no party was not said")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("a Governor workbook of ten counties tied to its summary, an empty Totals read as the "
                  "counties' rows and a sheet with no day said; 2018's Congress, its day in the State's "
                  "title; two county offices side by side, one left unsettled and said; another party's "
                  "file refused and listed")


@check("data", "members-elect: on the 2024 election, as of its own day, the matching rule links "
               "no winner to anyone but the person who took the seat",
       needs=("score_members_elect",))
def _elect_2024_scored(SME):
    """score_members_elect builds the record as it stood on 5 November 2024
    -- sitting, everyone who voted that year; former, everyone who voted
    before; each at the seat they held then -- runs build_members_elect's
    rule on the 2024 results, and holds every link to the 2025-2026 roll
    calls. A link to anyone but the person who took the seat fails: a
    stranger's record under a member-elect's name is worse than a missing
    link (the person's rule, 16 October 2026). And fewer links than the
    widened rule made fails too -- silence is not success: 310 of 424 on
    17 October 2026, 293 before the person's widening that day, and each of
    the 17 it added by name, so that undoing one of the three fails on the
    winners it was made for. Pat Long and Patrick N. Long, the two the
    widening must not reach, must stay unlinked."""
    miss = SME.absent(".", 2024)
    if miss:
        return "skip", "not here: " + ", ".join(miss)
    s = SME.score(".", 2024)
    wrong = [f"{r['race']} {r['name']} -> {r['link_name']} [{r['link']}], the seat went to "
             f"{r['truth_name']} [{r['truth']}]" for r in s["wrong"]]
    assert not wrong, f"{len(wrong)} winner(s) linked to somebody else: " + "; ".join(wrong[:5])
    # A LINK THE ROLL CALLS CANNOT CONFIRM IS NOT A LINK SHOWN RIGHT (17
    # October 2026): none on 2024, so one appearing is a change to read by
    # hand (python3 src/parse/score_members_elect.py names it).
    unread = [f"{r['race']} {r['name']} -> [{r['link']}]: {r['why_truth']}" for r in s["unverified"]]
    assert not unread, (f"{len(unread)} link(s) the next term's roll calls cannot confirm: "
                        + "; ".join(unread[:5]))
    assert len(s["correct"]) >= 310, (
        f"only {len(s['correct'])} of the 2024 winners link (310 on 17 October 2026, after the "
        "person's widening): the rule links less than it did")
    # THE WIDENING'S 17, BY NAME (17 October 2026): four by a suffix on one
    # side, three by the start of the first name, ten moves from the House.
    right = {(r["race"], r["name"]) for r in s["correct"]}
    widened = [
        ("H|Cheshire|12", "Dick H. Thackston III"), ("H|Coos|1", "James W. Tierney Jr."),
        ("H|Rockingham|20", "Charles R. Melvin Sr."), ("H|Strafford|5", "Thomas L. Kaczynski Jr."),
        ("H|Hillsborough|24", "Chris Herbert"), ("H|Merrimack|2", "Greg Hill"),
        ("H|Rockingham|16", "Doug Thomas"),
        ("S|1", "David Rochefort"), ("S|3", "Mark McConkey"), ("S|11", "Tim McGough"),
        ("H|Carroll|8", "Richard R. Brown"), ("H|Cheshire|15", "Nicholas Germana"),
        ("H|Grafton|10", "John Sellers"), ("H|Hillsborough|21", "Matthew B. Wilhelm"),
        ("H|Hillsborough|28", "Travis Corcoran"), ("H|Hillsborough|38", "Ralph G. Boehm"),
        ("H|Hillsborough|44", "Ross Berry")]
    lost = [f"{n} ({k})" for k, n in widened if (k, n) not in right]
    assert not lost, (f"{len(lost)} of the 17 winners the widening of 17 October 2026 linked are "
                      "not linked rightly now: " + ", ".join(lost))
    longs = [f"{r['name']} -> [{r['link']}]" for k in ("correct", "wrong", "unverified")
             for r in s[k] if r["name"] in ("Pat Long", "Patrick N. Long")]
    assert not longs, ("a Long is linked by the rule, which must leave both to the person (the "
                       "two Patrick Longs of member_links.py): " + "; ".join(longs))
    left = sum(len(s[k]) for k in ("unlinked_known", "unlinked_new", "unlinked_unread"))
    return "ok", (f"{len(s['correct'])} linked, every one to the person who took the seat "
                  f"({s['kinds']['sitting']} sitting, {s['kinds']['former']} returning); "
                  f"{left} left for the person, {len(s['unlinked_known'])} of them people the "
                  "record knew; none wrong")


@check("build", "members-elect on the pages: nothing drawn on 2 December, before the election or "
                "once the term is theirs, even from a file left behind; every element drawn "
                "carries the day it retires", needs=("build_members_elect",))
def _elect_pages_retire(BME):
    """The plan's check 3, for the pages (the person's decisions of 16 October
    2026: a block retires itself on 2 December). Every element the fixture's
    pages draw with data-elect carries data-until="2026-12-02" and is not
    hidden on 20 November. The pages hold the step's window themselves
    (build_members_elect.for_pages), so a file a build left behind is not
    drawn by a page builder run on its own: the four builders run on 2
    December over the site with the file still in it draw no data-elect,
    no tab, no "e" or "elect" in places.json, none in the map's file and no
    GR_ELECT, and say why -- and the site they leave is, byte for byte but
    the file itself, the site the same builders leave on that day with no
    file at all. And for_pages, on the same file, gives it to the
    pages on 20 November and 1 December and not on the election day, in
    October, on 2 December, in January, once site/meta.json's newest term is
    2027-2028, or with no meta.json; a file that will not read stops it."""
    import contextlib
    import io
    absent = _elect_absent()
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    w, o, doc, _said = _elect_built()
    bad = []
    for f in sorted((w / "site").rglob("*.html")):
        t = f.read_text(encoding="utf-8")
        for a, b in _elect_blocks(t):
            head = _ELECT_TAG.match(t, a).group(0)
            if 'data-until="2026-12-02"' not in head or re.search(r"\shidden\b", head):
                bad.append(f"{f.relative_to(w / 'site').as_posix()}: {head[:120]}")
    root = Path(tempfile.mkdtemp(prefix="gr-elect-gone-"))
    bare = Path(tempfile.mkdtemp(prefix="gr-elect-none-"))
    saved = os.environ.get("GRANITE_BUILD_DATE")
    try:
        # THE PROOF THE PERSON ASKED FOR: on 2 December the site built with
        # the last file still in it is the site built with none, byte for
        # byte, but for the file itself -- every page, places.json and the
        # map's file.
        shutil.copytree(w, root, dirs_exist_ok=True)
        shutil.copytree(o, bare, dirs_exist_ok=True)
        site = root / "site"
        said = _elect_pages(root, "2026-12-02")
        _elect_pages(bare, "2026-12-02")
        if said.count("is not drawn -- the build's day, 2026-12-02, is on or after "
                      "Organization Day") != len(_ELECT_PAGES):
            bad.append("the builders dated 2 December do not each say why the file is not drawn")
        left = [f.relative_to(site).as_posix() for f in site.rglob("*.html")
                if re.search(r"data-elect|GR_ELECT", f.read_text(encoding="utf-8"))]
        places = json.loads((site / "places.json").read_text(encoding="utf-8"))
        if left or "elect" in places or any("e" in p for p in places["places"]) \
                or "elect" in json.loads((site / "district_map.json").read_text(encoding="utf-8")):
            bad.append(f"drawn on 2 December from a file left behind: {left[:6]}, places.json "
                       f"{'elect' in places}, the map's file")
        mine = {f.relative_to(site).as_posix(): f.read_bytes() for f in site.rglob("*")
                if f.is_file()}
        none = {f.relative_to(bare / "site").as_posix(): f.read_bytes()
                for f in (bare / "site").rglob("*") if f.is_file()}
        differ = sorted(k for k in set(mine) | set(none)
                        if k != "members_elect.json" and mine.get(k) != none.get(k))
        if differ:
            bad.append(f"on 2 December the site built with the last file in it differs from the "
                       f"site built with none: {differ[:6]}")
        meta_p = site / "meta.json"
        meta = json.loads(meta_p.read_text(encoding="utf-8"))

        def shown(day, terms=None, no_meta=False):
            os.environ["GRANITE_BUILD_DATE"] = day
            if no_meta:
                meta_p.unlink()
            else:
                meta_p.write_text(json.dumps(dict(meta, terms=terms or meta["terms"])),
                                  encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                got = BME.for_pages(site)
            return got is not None and got["races"] == doc["races"]
        got = {label: shown(*args) for label, args in (
            ("20 November", ("2026-11-20",)), ("1 December", ("2026-12-01",)),
            ("the election day", ("2026-11-03",)), ("October", ("2026-10-16",)),
            ("2 December", ("2026-12-02",)), ("January", ("2027-01-06",)),
            ("2027-2028 the newest term", ("2026-11-20", ["2027-2028"] + meta["terms"])),
            ("no meta.json", ("2026-11-20", None, True)))}
        want = {k: k in ("20 November", "1 December") for k in got}
        if got != want:
            bad.append(f"for_pages draws the file {[k for k, v in got.items() if v]}, wanted on "
                       f"{[k for k, v in want.items() if v]}")
        meta_p.write_text(json.dumps(meta), encoding="utf-8")
        os.environ["GRANITE_BUILD_DATE"] = "2026-11-20"
        (site / "members_elect.json").write_text("{not json", encoding="utf-8")
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                BME.for_pages(site)
            bad.append("a file that will not read is drawn from, or passed over in silence")
        except SystemExit as e:
            if "will not read" not in str(e):
                bad.append(f"a file that will not read stops for_pages saying {e}")
    finally:
        if saved is None:
            os.environ.pop("GRANITE_BUILD_DATE", None)
        else:
            os.environ["GRANITE_BUILD_DATE"] = saved
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(bare, ignore_errors=True)
    assert not bad, "; ".join(bad)
    return "ok", ("every element drawn retires on 2 December; on that day a file left behind is "
                  f"drawn nowhere, each builder says why, and the site's {len(none):,} files are "
                  "the site built with no file, byte for byte; drawn on 20 November and 1 "
                  "December, not on the election day, in October, in January, once the term is "
                  "theirs or with no meta.json; a file that will not read stops the page")
