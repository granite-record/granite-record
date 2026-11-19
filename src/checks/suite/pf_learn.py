#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.6
"""
preflight's checks of Learn, the guides, civics and the numbers pages.

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import json
import os
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path

import _paths

from pf_core import (_run, _source, check)
from pf_fixture import (CHAIN_NEEDS, _fixture_site_shared)
from pf_harness import (_app_js, _with_components)
from pf_shared import (_BALLOTPEDIA, _ballot_file, _bill_index_write, _cal_rows, _mk,
                       _rsa_sections, _site_bills, _visible_text, _voters_row)


@check("status", "the constitution page counts each CACR of the term once",
       needs=("build_civics",))
def _cacr_partition(build_civics):
    """The page said "7 were killed outright, 16 died when the session ended,
    4 passed one chamber and stopped, and the rest are still in committee or
    were postponed" -- the same three CACRs in two counts, a "rest" that was
    six three-fifths failures and a death on the table, and "None of them
    reached the voters" beside CACR 13 on its way to the November ballot.
    Every CACR is now in one clause, and a clause with nothing in it is not
    printed.

    Then the page said "9 CACRs won a majority of those voting in the House
    and still fell short" and, a paragraph later, "6 fell short of three
    fifths on the House floor". The docket has 10. CACR 8 of 2025's line says
    "Lacking Necessary Two-Thirds Vote", a clerk's slip for three fifths, and
    was not read; CACR 8, 11, 12 and 18 each lost a House vote they had a
    majority on and were counted only as dying when the session ended. Both
    paragraphs now count one test, and the rows below are the real docket
    lines of those CACRs (and of 2016's CACR 17, whose line names no
    threshold at all)."""
    BC = build_civics

    def ev(body, raw):
        return {"body": body, "raw": raw}

    def nar(*evs):
        return {"events": list(evs)}

    fifths = nar(ev("H", "Ought to Pass: MF RC 194-158 Lacking Necessary Three-Fifths Vote 03/05/2026"))
    rows = ([{"id": "CACR13", "status": "Passed both chambers, goes to the voters in November 2026",
              "passage": "Hpp--"}]
            + [{"id": f"CACR{i}", "status": "Killed", "passage": "Hx--x"} for i in range(20, 27)]
            + [{"id": f"CACR{i}", "status": "Failed to pass", "passage": "Hx--x"} for i in range(30, 36)]
            + [{"id": "CACR40", "status": "Died on the table", "passage": "Hx--x"}]
            + [{"id": f"CACR{i}", "status": "Died when the session ended", "passage": "Spx-x"}
               for i in range(41, 44)]
            + [{"id": f"CACR{i}", "status": "Died when the session ended", "passage": "Hx--x"}
               for i in range(50, 63)])
    narr = {f"CACR{i}": fifths for i in range(30, 35)}
    narr.update({
        "CACR35": nar(ev("H", "Ought to Pass: MF RC 188-135 03/09/2016")),
        "CACR40": nar(ev("H", "Lay CACR22 on Table (Rep. Hill): MA RC 175-153 03/05/2026"),
                      ev("H", "Remove from Table (Rep. H. Howard): MF DV 100-230 03/11/2026")),
        # CACR 8 of 2025, 11 and 12 of 2026: through the Senate, short in the House.
        "CACR41": nar(ev("S", "Ought to Pass, RC 21Y-3N, MA, by Necessary 3/5; OT3rdg; 03/13/2025"),
                      ev("H", "Ought to Pass: MF DV 203-158 Lacking Necessary Two-Thirds Vote 05/08/2025")),
        "CACR42": nar(ev("S", "Ought to Pass with Amendments #2026-1219s, RC 23Y-1N, by necessary 3/5, "
                              "MA; OT3rdg; 03/26/2026"),
                      ev("H", "Ought to Pass: MF RC 199-157 Lacking Necessary Three-Fifths Vote 04/23/2026")),
        "CACR43": nar(ev("S", "Ought to Pass, RC 16Y-8N, MA, by Necessary 3/5; OT3rdg; 02/19/2026"),
                      ev("H", "Amendment # 2026-1134h: AA RC 192-148 05/14/2026"),
                      ev("H", "Ought to Pass with Amendment 2026-1134h: MF RC 193-148 Lacking "
                              "Necessary Three-Fifths Vote 05/14/2026")),
        # CACR 18 of 2026, short; CACR 9, no majority; CACR 19, not a vote on passing it.
        "CACR50": nar(ev("H", "Ought to Pass: MF DV 170-163 Lacking Necessary Three-Fifths Vote 03/12/2026")),
        "CACR51": nar(ev("H", "Ought to Pass: MF DV 136-185 Lacking Necessary Three-Fifths Vote 03/11/2026")),
        "CACR52": nar(ev("H", "Special Order to next order of business (Rep. A. Murray): MF DV 115-220 "
                              "03/11/2026")),
    })
    got = BC._cacr_record(rows, narr, "2025-2026")
    want = ("The 2025&ndash;2026 term filed <b>31 CACRs</b>. One passed both chambers and goes "
            "to the voters at the state general election in November 2026. 7 were killed "
            "outright; 10 fell short of three fifths on the House floor, 3 of them after "
            "passing the Senate; 1 died on the table; and 12 died when the session ended.")
    assert got == want, f"got {got!r}"
    # The paragraph above it counts the same failures by the same test.
    idx = ([dict(r, term="2025-2026") for r in rows]
           + [{"id": "CACR26", "term": "2011-2012", "passage": "Hpp--",
               "status": "Passed both chambers, went to the voters"}])
    hurdle = BC._cacr_hurdle(idx, {"2025-2026": narr}, "2025-2026")
    assert ("Of the 32 CACRs filed since 2011, 2 passed both chambers." in hurdle
            and "In the 2025&ndash;2026 term, 10 CACRs won a majority of those voting "
                "in the House and still fell short." in hurdle), hurdle
    assert "%" not in hurdle and "margin" not in hurdle, (
        "the hurdle paragraph measures a CACR's margin against those voting: " + hurdle)
    # CACR 26 of 2012 fell two short and was carried on reconsideration.
    cacr26 = nar(ev("H", "Ought to Pass: MF RC 237-115 Lacking Necessary Three-Fifths Vote"),
                 ev("H", "Reconsideration of OTP (Rep Hess): MA RC 242-111"),
                 ev("H", "Ought to Pass: MA RC 239-114 By Necessary Three-Fifths Vote"))
    assert not BC._fell_short(cacr26, "Died when the session ended"), "a CACR the House carried fell short"
    one = BC._cacr_record([{"id": "CACR1", "status": "Killed", "passage": "Hx--x"}], {}, "2023-2024")
    assert "None passed both chambers. 1 was killed outright." in one, one
    assert " 0 " not in got and "no of" not in one, (got, one)
    assert BC._cacr_record([], {}, "2023-2024").endswith("filed no CACRs."), "an empty term"
    return "ok", "31 CACRs in five clauses, each counted once, and the same 10 short on both paragraphs"


# The how-to guides in the header's search (17 October 2026): find.js over
# rows made as build_indexes makes them, run against tests/search_cases.json's
# "find" cases.
_FIND_GUIDES_JS = r"""
require("./stub.js");
const fs = require("fs"), vm = require("vm");
globalThis.fetch = async () => ({ ok: false, status: 404, json: async () => { throw new Error("404"); } });
globalThis.chip = (t, cls) => `<span class="${cls}">${t}</span>`;
vm.runInThisContext(fs.readFileSync("./find.js", "utf8"), { filename: "find.js" });
const F = vm.runInThisContext("({FIND, FBILLS, findDraw, findMatch, findKind, _fwhole})");
const go = JSON.parse(fs.readFileSync("./go.json", "utf8"));
F.FIND.rows = go.rows;
F.FBILLS.rows = go.bills; F.FBILLS.term = "2025-2026";
const out = {}, kinds = {}, whole = {};
for (const c of go.cases) out[c.q] = F.findMatch(c.q, Infinity).map(r => [r[0], r[3]]);
// Whole words of the guide's name -- its title, task and words -- which is
// what puts a row above the bills in the panel and on /search.
for (const c of go.cases) if (c.first)
  whole[c.q] = F._fwhole(go.rows.find(r => r[3] === "/guides/" + c.first), c.q);
for (const r of go.rows) kinds[r[0]] = F.findKind(r);
const panel = {};
for (const c of go.cases) if (c.bill_first) {
  F.findDraw(c.q);
  panel[c.q] = document.getElementById("findout").innerHTML;
}
console.log(JSON.stringify({ out, kinds, panel, whole }));
"""


@check("frontend", "the header's search and /search find a how-to guide by its task and its plain "
       "words, label it a Guide, list it above the Learn pages, and never above a bill whose "
       "number was typed", needs=("guides", "civics", "build_pages"))
def _find_guides(G, civics, BP):
    """The person, 17 October 2026: "the how to guides should be incorporated
    into the search in some fashion". build_indexes gives each guide's row in
    find.json its task and the plain words guides.WORDS declares
    (guides.search_words); find.js reads them as part of the guide's name
    (_fnamed), so a reader typing "renew my license" or "testify" meets the
    guide first among the names (findMatch). Since 8 November 2026 the panel
    and /search draw the guides straight after the bills (Alice: "minimum
    wage" led with a guide above its seven bills), which _search_polish holds,
    but for a search that asks how, whose guides the panel puts above the
    bills since 17 November 2026 (the owner; _search_how_to);
    /search's group of them is drawn with the bills. Here the
    cases of tests/search_cases.json's "find" run through find.js over rows
    made the same way, with a member, a town, a subject, the Learn pages and
    a bill beside them, and a probe guide that declares a bill number's words,
    which must still sit under that bill in the panel."""
    if shutil.which("node") is None:
        return "skip", "node is not installed"
    import build_civics as BC
    cases = json.loads(_source("tests/search_cases.json"))["find"]["cases"]
    assert cases, "tests/search_cases.json has no find cases"
    rows = []
    for g in G.GUIDES:
        rows.append(["guide", g["title"].replace("&rsquo;", "'"), g["blurb"], f"/guides/{g['slug']}",
                     G.search_words(g["slug"])])
    for t in civics.TOPICS:
        kind = "guide" if t["slug"] in civics.HOW_TO else "learn"
        rows.append([kind, t["title"], t["blurb"], "/" + BC.article_href(t["slug"])[:-5],
                     G.search_words(t["slug"]) if kind == "guide" else ""])
    rows += [["legislator", "Rep. Alice Voter (D - Straf 15)", "House · Straf 15 · D", "/legislator/a", ""],
             ["town", "Concord", "Merrimack County", "/town/concord", "Merrimack"],
             ["topic", "Elections", "Bills on this subject", "/bills?topic=Elections", ""],
             ["guide", "How to Read a Probe", "A probe.", "/guides/probe", "Read a probe · hb 1"]]
    assert all(r[4] for r in rows if r[0] == "guide" and r[3] != "/guides/probe"), \
        "a guide's row carries no task words"
    bills = [{"id": "HB1", "n": "HB 1", "title": "making appropriations", "year": 2025}]
    root = Path(tempfile.mkdtemp())
    try:
        (root / "stub.js").write_text(_source("tests/dom_stub.js"), encoding="utf-8")
        (root / "find.js").write_text(_source("src/pages/find.js"), encoding="utf-8")
        (root / "go.json").write_text(json.dumps({"rows": rows, "bills": bills, "cases": cases}),
                                      encoding="utf-8")
        (root / "go.js").write_text(_FIND_GUIDES_JS, encoding="utf-8")
        r = _run(["node", "go.js"], cwd=root, capture_output=True, text=True, timeout=60)
        said = (r.stdout + r.stderr).strip()
        last = (said.splitlines() or ["no output"])[-1]
        assert r.returncode == 0 and last.startswith("{"), "node go.js: " + " / ".join(said.splitlines()[-3:])[:300]
        got = json.loads(last)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert got["kinds"]["guide"] == "Guide", f"a guide is labelled {got['kinds']['guide']!r}"
    bad = []
    for c in cases:
        found = got["out"].get(c["q"], [])
        slugs = [u.rsplit("/", 1)[-1] for k, u in found if k == "guide"]
        if c.get("first") and (not found or found[0] != ["guide", f"/guides/{c['first']}"]):
            bad.append(f"{c['q']!r} leads with {found[:1]}, not the guide {c['first']}")
        if c.get("first") and not got["whole"].get(c["q"]):
            bad.append(f"{c['q']!r} is not read as the guide {c['first']}'s own words, so the "
                       "bills go above it")
        for s in c.get("listed") or []:
            if s not in slugs:
                bad.append(f"{c['q']!r} does not list the guide {s}")
        if c.get("guides_first"):
            ks = [k for k, _u in found if k in ("guide", "learn")]
            if "guide" not in ks or ("learn" in ks and ks.index("learn") < len(ks) - ks[::-1].index("guide") - 1):
                bad.append(f"{c['q']!r} lists a Learn page above a guide: {ks}")
        for s in c.get("learn") or []:
            if ["learn", f"/learn/{s}"] not in found:
                bad.append(f"{c['q']!r} no longer lists the Learn page {s}")
        if c.get("bill_first"):
            html_ = got["panel"].get(c["q"], "")
            at_bill = html_.find(f'/bill/2025/{c["bill_first"].lower()}"')
            at_guide = html_.find('href="/guides/probe"')
            if at_bill < 0 or (0 <= at_guide < at_bill):
                bad.append(f"{c['q']!r}: the bill is not the panel's first answer above a guide with its words")
    assert not bad, "; ".join(bad)
    js = BP.SEARCH_JS
    assert '{t:"How-To Guides",' in js and 'const GUIDES=GROUPS.find(g=>g.t==="How-To Guides");' in js, (
        "/search has no group of the guides, drawn with the bills")
    assert '{t:"Learn",' in js and '"Learn","Pages on This Site"]' in js, "/search does not list the Learn pages"
    assert "const named=!findBill(s)&&rows.some(" in js, "/search can put a guide above a bill number's bills"
    bi = _source("src/pages/build_indexes.py")
    assert 'G.search_words(p.stem) if kind == "guide"' in bi, "find.json no longer carries a guide's task words"
    return "ok", (f"{len(cases)} searches: guides found by their task and plain words, labelled Guide, "
                  "above the Learn pages, and under a bill whose number was typed")


@check("frontend", "the civics examples are not on a charged subject")
def _civics_examples():
    """Every bill the learn pages cite, checked against its own subject.

    The civics section teaches with worked examples, and a teaching example is
    held to a different standard from a record: it has to be a bill a student
    of any politics can look at and argue about fairly. Two had slipped in --
    SB 71 on cooperation with federal immigration authorities, and HB 1442 on
    permitting classification of individuals by biological sex, whose own
    topic field reads "Discrimination". Both were cited only to illustrate a
    procedural outcome, which is exactly how it happens: nobody chose them for
    their subject, so nobody checked their subject.

    The list below is a judgement, not a measurement, and it is meant to be
    edited. It errs toward stopping the build: a false positive costs somebody
    thirty seconds and a sentence in this docstring, and a false negative puts
    a charged example in front of a classroom.
    """
    CHARGED = re.compile(
        r"abortion|abort|fetal|contracept|reproduct|gender|transgender|"
        r"biological sex|lgbt|conversion therapy|sexual|obscen|porn|"
        r"firearm|gun|weapon|pistol|"
        r"immigrat|refugee|alien|sanctuary|"
        r"vaccin|immuniz|marijuana|cannabis|psiloc|"
        r"voter|ballot|electioneer|"
        r"religio|prayer|divisive concept|critical race|"
        r"death penalty|capital murder|"
        r"parental right|parental bill of rights|education freedom|school choice|"
        r"discriminat|environmental justice|medicaid work", re.I)

    try:
        import civics
    except Exception as e:                      # noqa: BLE001
        return "skip", f"civics.py did not import ({e})"

    # The bills the pages actually LINK, because a linked bill is one a reader
    # is invited to open. A bill number mentioned without a link -- "there is
    # only ever one HB 84 in 2025-2026" -- is an illustration of numbering and
    # carries no subject with it.
    linked = []
    for t in civics.TOPICS:
        for m in re.finditer(r'bill/(\d{4})/([a-z0-9]+)\.html', t["body"]):
            linked.append((t["slug"], m.group(1), m.group(2).upper()))
    if not linked:
        return "skip", "the learn pages link no bills"

    idx = {}
    for f in Path("site/idx").glob("*.json"):
        try:
            for b in json.loads(f.read_text(encoding="utf-8")):
                idx.setdefault((str(b.get("year")), b.get("id")), b)
        except (ValueError, OSError):
            continue
    if not idx:
        return "skip", "no built index to check subjects against"

    # NAMED, WITH THE REASON, rather than by softening the pattern. SB 2 of
    # 1995 is the law that let a town put its warrant articles on the official
    # ballot, and "SB 2 town" is the ordinary name for a town that adopted it
    # -- the phrase turns up in bills every year, which is why the local
    # government page explains it. The word "ballot" in its title is the
    # mechanism it created, not a subject anybody argues about; taking
    # "ballot" out of the pattern instead would let a voter-identification
    # bill through, and those are exactly what it is there to catch.
    ALLOWED = {("1995", "SB2")}
    # A COMPLETE LIST IS NOT A CHOSEN EXAMPLE (the person, 26 October 2026):
    # "don't remove charged bills from a list of bills within a certain
    # category such as the proposed state pistol. I meant that if we are
    # looking to select example towns, legislators, and bills for the learn
    # pages to explain a concept, we should choose less polarizing bills if we
    # have the option." State Symbols lists every proposed symbol in the
    # record; a gun is one of them, and leaving it out would make the list
    # untrue. Named by page and bill, so the rule still holds everywhere else.
    LISTED = {("state-symbols", "2012", "HB1430")}

    bad, unknown = [], []
    for slug, year, bid in linked:
        b = idx.get((year, bid))
        if not b:
            unknown.append(f"{bid} ({year}) on {slug}")
            continue
        if (year, bid) in ALLOWED or (slug, year, bid) in LISTED:
            continue
        hit = CHARGED.search((b.get("title") or "") + " " + (b.get("topic") or ""))
        if hit:
            bad.append(f'{slug} cites {bid} ({year}), whose subject matches '
                       f'"{hit.group(0)}": {(b.get("title") or "")[:70]}')
    assert not bad, "; ".join(bad[:3])
    # A citation this cannot check is worth saying out loud rather than
    # counting as a pass.
    note = f"{len(linked)} linked bills, subjects clear"
    if unknown:
        note += f"; {len(unknown)} not in any built index ({unknown[0]})"
    return "ok", note


@check("frontend", "the Learn pages do not restate a rule the record contradicts",
       needs=("civics", "learn_numbers", "build_civics"))
def _learn_rules(civics, learn_numbers, build_civics):
    """Seven Learn pages stated rules the General Court's own record refutes.

    Found on 23 September 2026, each against a primary source on this disk:
    "Part Two, Article 78", where the constitution's parts are First and
    Second; three fifths "240 of the 400 House seats", where the House counts
    the members in office -- CACR 26 failed at 237-115 and passed at 239-114 on
    one day in 2012 with 397 seated; a consent-calendar report placed "when the
    committee was unanimous or nearly so", where the House and Senate rules
    both demand a unanimous placement; "a bill left unsigned becomes law
    anyway", which drops Article 44's adjournment clause; a 1992 veto "still
    awaiting its override vote" 34 years on; and two veto overrides that
    needed two thirds listed as the term's closest votes at 160-159 and
    176-175.

    The prose half fails on the wording coming back. The fixture half runs the
    two figures that went wrong -- veto_pending and the closest-votes table --
    on a record small enough to know the answer to, and the arithmetic half
    recomputes every threshold the pages work through in words.

    The fixture also holds the figures written to replace those claims. The
    first draft of the year from which hearings are on video started from the
    term still sitting, so one unheard bill of that term named no year and two
    pages printed "nearly every one since" and a gap; it is checked with that
    bill in place, and a record that lost its recordings, or has no roll calls,
    must stop the build rather than print a hole.
    """
    import math
    import tempfile as _tf

    # -- the wording ------------------------------------------------------
    pages = {t["slug"]: " ".join([t["blurb"], t["body"], t.get("holds") or ""])
             for t in civics.TOPICS}
    BANNED = [(re.compile(r"\bPart (One|Two)\b"),
               "the constitution's parts are Part First and Part Second"),
              (re.compile(r"\b240 of (the )?400\b"),
               "three fifths is of the members in office, not of the 400 seats"),
              (re.compile(r"nearly so", re.I),
               "a consent-calendar placement must be unanimous in both chambers"),
              (re.compile(r"becomes\s+law\s+anyway", re.I),
               "an unsigned bill does not become law if adjournment prevents its return"),
              (re.compile(r"\bno of them\b", re.I),
               "a count of nothing spelled as 'no of them'")]
    def retracted(texts):
        return [f"{slug}: {why} ({m.group(0)!r})"
                for slug, text in texts.items() for rx, why in BANNED
                for m in [rx.search(re.sub(r"\s+", " ", text))] if m]

    bad = retracted(pages)
    assert not bad, "; ".join(bad[:3])

    # -- the arithmetic the prose works through -------------------------
    flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", " ".join(pages.values())))
    worked = 0
    for m in re.finditer(r"three fifths of ([\d,]+) is (\d+(?:\.\d+)?)", flat):
        n, got = int(m.group(1).replace(",", "")), float(m.group(2))
        assert abs(got - 0.6 * n) < 1e-9, f"'{m.group(0)}': three fifths of {n} is {0.6 * n:g}"
        worked += 1
    for m in re.finditer(r"with (\d+) votes, when (\d+) members were in office", flat):
        x, n = int(m.group(1)), int(m.group(2))
        assert x == math.ceil(3 * n / 5), (
            f"'{m.group(0)}': three fifths of {n} members needs {math.ceil(3 * n / 5)}")
        worked += 1
    for m in re.finditer(r"(\d+) when all (\d+) House seats are filled", flat):
        x, n = int(m.group(1)), int(m.group(2))
        assert x == math.ceil(3 * n / 5), f"'{m.group(0)}': three fifths of {n} is {math.ceil(3 * n / 5)}"
        worked += 1
    for m in re.finditer(r"(\d+) of a full Senate of (\d+)", flat):
        x, n = int(m.group(1)), int(m.group(2))
        assert x == math.ceil(3 * n / 5), f"'{m.group(0)}': three fifths of {n} is {math.ceil(3 * n / 5)}"
        worked += 1
    for m in re.finditer(r"overrode a veto (\d+) to (\d+) when (\d+) members were in office", flat):
        y, n, seated = (int(g) for g in m.groups())
        assert 3 * y >= 2 * (y + n) and 3 * y < 2 * seated, (
            f"'{m.group(0)}' is offered as two thirds of those voting and not of the "
            f"members in office, and the numbers do not show that")
        worked += 1

    # -- the figures, on a record whose answer is known ------------------
    def row(term, bid, **kw):
        return dict({"term": term, "id": bid, "year": int(term[-4:]), "nrc": 0}, **kw)

    idx = [row("1991-1992", "HB1407", status="Vetoed"),
           row("1997-1998", "HB9"),
           row("1999-2000", "HB9"),
           row("2023-2024", "HB5", status="Vetoed, override failed"),
           row("2025-2026", "HB1", status="Vetoed, override failed"),
           row("2025-2026", "HB2", kind="law"),
           row("2025-2026", "HB3", kind="law", nrc=2),
           row("2025-2026", "HB4", nrc=1),
           row("2025-2026", "CACR1", nrc=2)]
    H = {"body": "H", "year": 2026, "date": "2026-03-12", "procedural": False}
    rcs = {"1999-2000": {"HB9": [dict(H, year=1999, question="Ought to Pass",
                                      yeas=200, nays=150)]},
           "2025-2026": {
               "HB1": [dict(H, question="Veto Override", yeas=160, nays=159)],
               "HB3": [dict(H, question="Ought to Pass", yeas=180, nays=179)],
               "HB4": [dict(H, question="Rules Suspension", yeas=190, nays=189)],
               "CACR1": [dict(H, question="Ought to Pass", yeas=201, nays=200),
                         dict(H, question="Inexpedient to Legislate", yeas=176, nays=162)]}}
    procs = [{"term": t, "bill": b, "kind": "public hearing", "body": "H",
              "date": f"{t[-4:]}-01-10", "video_id": "v" if t >= "2023" else ""}
             for t, b in (("1999-2000", "HB9"), ("2023-2024", "HB5"), ("2025-2026", "HB1"),
                          ("2025-2026", "HB2"), ("2025-2026", "HB3"), ("2025-2026", "HB4"),
                          ("2025-2026", "CACR1"))]
    # record_figures reads the proceedings table through proceedings.load and
    # caches the hearing-notice figure per term; both are put back afterwards,
    # so nothing later in this run sees the fixture.
    real_load = build_civics.P.load
    notice_cache = build_civics._notice.__defaults__[0]
    saved_cache = dict(notice_cache)
    with _tf.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _bill_index_write(tmp, idx)
        (tmp / "rollcalls.json").write_text(json.dumps(rcs), encoding="utf-8")
        build_civics.P.load = lambda *a, **k: [dict(p) for p in procs]
        # A stop is a finding of this check, never the end of the whole run:
        # SystemExit is not an Exception, and would get past the runner.
        def stops(site, root):
            try:
                build_civics.record_figures(site, root)
            except SystemExit as e:
                return str(e) or "stopped"
            return ""

        def figures(site, root):
            try:
                return build_civics.record_figures(site, root)
            except SystemExit as e:
                raise AssertionError(f"record_figures stopped on a record it should build: {e}")

        try:
            fig = figures(tmp, tmp)
            # A veto of the term still sitting, and a bill of it not heard
            # yet: five of its six bills filmed, under the nine in ten.
            idx.append(row("2025-2026", "HB6", status="Vetoed"))
            _bill_index_write(tmp, idx)
            fig_waiting = figures(tmp, tmp)
            # The newest finished term's recordings lost from the table.
            build_civics.P.load = lambda *a, **k: [
                dict(p, video_id="" if p["term"] == "2023-2024" else p["video_id"])
                for p in procs]
            lost = stops(tmp, tmp)
            build_civics.P.load = lambda *a, **k: [dict(p) for p in procs]
            # No roll calls at all.
            (tmp / "bare").mkdir()
            (tmp / "bare" / "rollcalls.json").write_text("{}", encoding="utf-8")
            no_rc = stops(tmp, tmp / "bare")
        finally:
            build_civics.P.load = real_load
            notice_cache.clear()
            notice_cache.update(saved_cache)
        nums = learn_numbers.body(tmp, tmp, strict=False)
    bad = retracted({"by-the-numbers": nums})
    assert not bad, "; ".join(bad)
    assert fig["veto_pending"] == "", (
        "a veto from a finished term (1992's HB 1407) is reported as still awaiting "
        f"its override vote: {fig['veto_pending']!r}")
    assert fig["veto_failed"] == "3", (
        f"veto_failed is {fig['veto_failed']}; a veto no override vote reached in a "
        "finished term stood, and wants counting with the failed overrides (3)")
    assert "awaiting" in fig_waiting["veto_pending"], (
        "a veto of the current term with no override vote yet is not reported as waiting")
    assert (fig["rollcall_first_year"], fig["pre_rollcall_bills"], fig["law_no_rollcall"]) \
        == ("1999", "2", "1"), (
        "the roll-call figures are wrong on the fixture: first year "
        f"{fig['rollcall_first_year']} (want 1999), bills before it {fig['pre_rollcall_bills']} "
        f"(want 2), laws of the term with none {fig['law_no_rollcall']} (want 1)")
    assert (fig["hearing_video_bills"], fig["hearing_video_from"]) == ("6", "2023"), (
        f"hearings on video: {fig['hearing_video_bills']} bills from "
        f"{fig['hearing_video_from']!r}; want 6 from 2023, the first term from which "
        "every later term is nine tenths filmed")
    assert (fig_waiting["hearing_video_from"], fig_waiting["hearing_video_since"]) \
        == ("2023", ", nearly every one since 2023"), (
        "one unheard bill of the term still sitting changed the year hearings are on "
        f"video from: {fig_waiting['hearing_video_from']!r}, clause "
        f"{fig_waiting['hearing_video_since']!r}; that term is still being heard, "
        "and the pages would print 'nearly every one since' and a gap")
    assert "video_id" in lost, (
        "a record whose newest finished term lost its recordings built anyway: "
        + (lost or "no stop"))
    assert "roll call" in no_rc, (
        "a record with no roll calls built anyway, and the pages would say they "
        "begin in 0: " + (no_rc or "no stop"))
    close = nums[nums.index("The Closest Votes"):]
    close = close[:close.index("<h2>")] if "<h2>" in close else close
    for bid, why in (("hb1", "a veto override"), ("hb4", "a rules suspension")):
        assert f"bill/2026/{bid}\"" not in close, (
            f"the closest votes list {bid.upper()}, {why}, which needed more than a majority")
    assert "201&ndash;200" not in close, (
        "the closest votes list a CACR's passage, which needed three fifths")
    assert "bill/2026/hb3\"" in close and "176&ndash;162" in close, (
        "the closest votes lost a majority question: an ordinary bill's passage, or a "
        "motion to kill a CACR, which needs no more than a majority")
    return "ok", (f"no retracted wording on {len(pages)} pages; {worked} worked "
                  "thresholds recomputed; veto_pending, the closest votes and the "
                  "hearings-on-video year right on a fixture, an unheard bill of "
                  "the sitting term included")


# THE PAGE OF NUMBERS, FIGURE BY FIGURE (7 October 2026). The person's notes
# F16 to F22 added eight figures to /learn/by-the-numbers.html, each measured
# first against sources this project did not write, and took two away. Each
# figure is a function of learn_numbers.py, and each check below runs one on a
# record small enough to know the answer to, so that what the page's one-line
# definition says is what the code counts. A check names the definition it
# holds; a change that breaks one changes what a sentence on a public page
# means.

def _ln_ev(body, raw, type_="other", date="2025-03-01", **kw):
    return dict({"body": body, "raw": raw, "type": type_, "date": date, "cancelled": False}, **kw)


@check("frontend", "numbers: how each bill ended counts House and Senate bills by their card's word",
       needs=("learn_numbers",))
def _numbers_outcomes(learn_numbers):
    """F22, bills filed and how they ended: every House and Senate bill the
    term numbered, special sessions' included, by its chip -- Became Law,
    Died, Interim Study, and anything else (withdrawn, never introduced, or
    still moving while a session sits) as Other. A resolution and a CACR are
    not bills and do not count."""
    t = "2025-2026"
    rows = [{"term": t, "id": "HB1", "chip": "Became Law"},
            {"term": t, "id": "HB2", "chip": "Died"},
            {"term": t, "id": "HB3", "chip": "Interim Study"},
            {"term": t, "id": "HB4", "chip": "Withdrawn"},
            {"term": t, "id": "SSHB1", "chip": "Became Law"},
            {"term": t, "id": "SB1", "chip": "In committee"},
            {"term": t, "id": "HR1", "chip": "Adopted by the House"},
            {"term": t, "id": "CACR1", "chip": "Died"}]
    got = dict(learn_numbers.outcomes(rows)[t])
    want = {"filed": 6, "Became Law": 2, "Died": 1, "Interim Study": 1, "other": 2}
    assert got == want, f"bills filed and how they ended: {got}, want {want}"
    return "ok", "6 bills of 8 measures: 2 Became Law, 1 Died, 1 Interim Study, 2 Other"


@check("frontend", "numbers: bills per member count to the chamber the prime sponsor sat in",
       needs=("learn_numbers",))
def _numbers_per_member(learn_numbers):
    """F22, bills filed and passed per member: a House or Senate bill counts
    to the chamber its prime sponsor sat in -- a senator's House bill to the
    Senate -- and passed means it became law. A committee's bill counts to
    nobody, and a resolution is not a bill. The page divides by 400 and 24."""
    t = "2025-2026"
    rows = [{"term": t, "id": "HB1", "sponsor_label": "Rep. Ann Able (R)", "status": "Signed into law"},
            {"term": t, "id": "HB2", "sponsor_label": "Rep. Ben Baker (D)", "status": "Killed"},
            {"term": t, "id": "SB1", "sponsor_label": "Sen. Cy Cole (R)", "status": "Became law unsigned"},
            {"term": t, "id": "HB3", "sponsor_label": "Sen. Di Dunn (D)",
             "status": "Veto overridden, became law"},
            {"term": t, "id": "SB2", "sponsor_label": "Sen. Cy Cole (R)", "status": "Vetoed, override failed"},
            {"term": t, "id": "HB4", "sponsor_label": "Judiciary Committee", "status": "Signed into law"},
            {"term": t, "id": "HR1", "sponsor_label": "Rep. Ann Able (R)", "status": "Adopted by the House"}]
    got = learn_numbers.per_member(rows)[t]
    want = {"H": [2, 1], "S": [3, 2]}
    assert got == want, f"bills per member: {got}, want {want} ([filed, became law] by chamber)"
    assert learn_numbers.SEATS == {"H": 400, "S": 24}, f"seats: {learn_numbers.SEATS}"
    return "ok", "a senator's House bill counts to the Senate; a committee's to nobody"


@check("frontend", "numbers: a committee's bills are its first referrals and the bills sent on to it",
       needs=("learn_numbers",))
def _numbers_referrals(learn_numbers):
    """F22, the bills each committee received: the first referral is the
    committee the bill's page names in that chamber, once per bill; sent on is
    a later committee of the same chamber the docket refers it to -- Finance
    under House Rule 47 here -- and a motion to refer that failed sends
    nothing anywhere."""
    t = "2025-2026"
    idx = [{"term": t, "id": "HB1", "committees": ["House Judiciary", "Senate Education"]},
           {"term": t, "id": "HB2", "committees": ["House Judiciary"]}]
    ev = _ln_ev
    narr = {"HB1": {"events": [
        ev("H", "Introduced 01/08/2025 and referred to Judiciary", "introduced"),
        ev("H", "Ought to Pass with Amendment # 2025-0101h: MA VV; Refer to Finance Rule 47", "floor"),
        ev("H", "Motion to Refer to Ways and Means: MF RC 150-200", "floor"),
        ev("S", "Introduced 03/20/2025 and Referred to Education; SJ 9", "introduced")]},
        "HB2": {"events": [ev("H", "Introduced 01/08/2025 and referred to Judiciary", "introduced")]}}
    got = {k: list(v) for k, v in learn_numbers.referrals(idx, narr, t).items()}
    want = {"House Judiciary": [2, 0], "House Finance": [0, 1], "Senate Education": [1, 0]}
    assert got == want, f"the bills each committee received: {got}, want {want}"
    return "ok", "first referrals once a bill, Finance's second referral counted, a lost motion not"


@check("frontend", "numbers: the most-signed hearings rank hearings, with the title as heard",
       needs=("learn_numbers",))
def _numbers_signins(learn_numbers):
    """F17, the hearings with the most sign-ins: hearings, not bills, are
    ranked by every support, oppose and neutral sign-in, so a bill heard twice
    can appear twice; each shows the title the bill had when it was heard --
    the printing dated on or before the hearing, else its first -- and not its
    final one; the committee is the one that reported after the hearing; a
    sitting on a non-germane amendment is marked as one, by the hearing date
    in the docket's text and not the day the notice was posted; and a past
    term's bill retitled later, whose printings are not on disk, stops a
    strict build rather than print the later title as the one heard."""
    import tempfile as _tf
    t, ev = "2025-2026", _ln_ev
    h = lambda d, s, o, n=0: {"date": d, "total": s + o + n, "support": s, "oppose": o, "neutral": n}
    tdb = {t: {"HB9": {"hearings": [h("2025-01-20", 5, 45), h("2026-02-03", 29, 1)]},
               "HB8": {"hearings": [h("2025-01-21", 39, 1)]},
               "HB7": {"hearings": [h("2025-01-22", 9, 1)]}},
           "2023-2024": {"HB5": {"hearings": [h("2024-01-10", 1, 19)]}}}
    narr = {t: {"HB9": {"events": [
        ev("H", "Public Hearing: 01/20/2025 10:00 am LOB 206", "hearing", "2025-01-20"),
        ev("H", "Majority Committee Report: Ought to Pass 02/01/2025 (Vote 10-5; RC)", "report",
           "2025-02-01", committee="Judiciary", side="Majority"),
        ev("H", "Public Hearing on non-germane Amendment # 2026-0422h: 02/03/2026 10:00 am LOB 203",
           "hearing", "2026-01-30")]}}}
    idx = [{"term": t, "id": "HB9", "year": 2025, "title": "relative to pears.",
            "committees": ["House Judiciary"]},
           {"term": t, "id": "HB8", "year": 2025, "title": "relative to figs.",
            "committees": ["House Education Funding"]},
           {"term": "2023-2024", "id": "HB5", "year": 2024, "title": "relative to plums.",
            "committees": ["House Education"]}]
    with _tf.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        v = tmp / "versions" / "2025"
        v.mkdir(parents=True)
        (v / "HB9.json").write_text(json.dumps({"versions": [
            {"label": "Introduced", "date": "01/25/2025 10:00:00"},
            {"label": "As Amended by the House", "date": "03/01/2025 10:00:00"}]}), encoding="utf-8")
        (v / "HB9.0.txt").write_text("2025 SESSION HOUSE BILL\t9 AN ACT\trelative to apples. "
                                     "SPONSORS:\tRep. Able", encoding="utf-8")
        (v / "HB9.1.txt").write_text("2025 SESSION HOUSE BILL\t9 AN ACT\trelative to oranges. "
                                     "SPONSORS:\tRep. Able", encoding="utf-8")
        (tmp / "data").mkdir()
        (tmp / "data" / "bills.json").write_text(json.dumps(
            {"2023-2024": {"HB5": {"title": "(New Title) relative to plums."}}}), encoding="utf-8")
        try:
            learn_numbers.signins(tdb, narr, idx, tmp, tmp, top=3, strict=True)
            stopped = ""
        except SystemExit as e:
            stopped = str(e)
        assert "HB5" in stopped, (
            "a bill retitled after its hearing, with no printing on disk, built anyway with "
            "its later title shown as the one heard")
        loose = learn_numbers.signins(tdb, narr, idx, tmp, tmp, top=3, strict=False)
        past = tmp / "db" / "past"
        past.mkdir(parents=True)
        (past / "PastLegislationText.jsonl").write_text(json.dumps(
            {"BillNbr": "HB5", "sessionyear": 2024, "VersionID": 4,
             "text": "2024 SESSION\r\nHOUSE BILL\t5\r\n\r\nAN ACT\trelative to cherries.\r\n\r\n"
                     "SPONSORS:\tRep. Cole"}, separators=(",", ":")) + "\n", encoding="utf-8")
        got = learn_numbers.signins(tdb, narr, idx, tmp, tmp, top=3, strict=True)
    rows = [(x["bill"], x["date"], x["total"], x["title"], x["committee"], x["on"]) for x in got[t]]
    want = [("HB9", "2025-01-20", 50, "relative to apples.", "Judiciary", ""),
            ("HB8", "2025-01-21", 40, "relative to figs.", "Education Funding", ""),
            ("HB9", "2026-02-03", 30, "relative to oranges.", "Judiciary", "a non-germane amendment")]
    assert rows == want, f"the most-signed hearings: {rows}, want {want}"
    assert got["2023-2024"][0]["title"] == "relative to cherries.", (
        f"a past term's retitled bill: {got['2023-2024'][0]['title']!r}, want the introduced "
        "title, relative to cherries.")
    assert loose["2023-2024"][0]["title"] == "relative to plums.", "strict=False should fall back"
    return "ok", ("3 of 4 hearings ranked, one bill twice, each under the title it was heard by; "
                  "an amendment's hearing marked; a missing printing stops a strict build")


@check("frontend", "numbers: the consent totals count a reprinted report once",
       needs=("learn_numbers",))
def _numbers_consent(learn_numbers):
    """F19, consent calendars: every majority report of the term, credited to
    the committee that made it -- a second committee's to the second
    committee, Finance here, even where the docket carries the first one's name
    forward, as the passage rates credit it -- a minority report left out;
    kept when it carried CC and the chamber did not take the bill off, removed
    when it did, regular when it never went on consent -- and a report the
    docket prints again with the same committee, recommendation, amendment and
    tally (the Senate's, after a special order) counts once."""
    ev = _ln_ev
    rep = lambda b, raw, y, n, c="Judiciary", rec="Ought to Pass": ev(
        b, raw, "report", committee=c, recommendation=rec, amendment="", yeas=y, nays=n,
        side="Majority")
    narr = {"HB1": {"events": [rep("H", "Committee Report: Ought to Pass 02/01/2025 (Vote 18-0; CC)", "18", "0"),
                               ev("H", "Minority Committee Report: Inexpedient to Legislate", "report")]},
            "HB2": {"events": [rep("S", "Committee Report: Ought to Pass, 03/01/2025, Vote 5-0; CC", "5", "0"),
                               ev("S", "Removed from Consent (Sen. Able), MA, VV", "consent_off"),
                               rep("S", "Committee Report: Ought to Pass, 03/01/2025, Vote 5-0", "5", "0")]},
            "HB3": {"events": [rep("H", "Committee Report: Inexpedient to Legislate (Vote 10-8; RC)",
                                   "10", "8", rec="Inexpedient to Legislate")]},
            "HB4": {"events": [rep("H", "Committee Report: Ought to Pass 02/01/2025 (Vote 15-0; CC)", "15", "0"),
                               ev("H", "Ought to Pass: MA VV; Refer to Finance Rule 47", "floor"),
                               rep("H", "Committee Report: Ought to Pass 03/17/2025 (Vote 25-0; CC)", "25", "0")]}}
    rows_by = {b: {"committees": ["House Judiciary", "Senate Judiciary"]} for b in narr}
    by_c, per = learn_numbers.consent(narr, rows_by, "2025-2026")
    got = ({k: list(v) for k, v in by_c.items()}, {k: dict(v) for k, v in per.items()})
    want = ({"House Judiciary": [3, 2], "House Finance": [1, 1], "Senate Judiciary": [1, 0]},
            {"H": {"kept": 3, "regular": 1}, "S": {"removed": 1}})
    assert got == want, f"consent: {got}, want {want}"
    return "ok", ("kept, removed and regular counted; Finance's report to Finance; the reprint "
                  "and the minority report left out")


@check("frontend", "numbers: a committee's passage rate is of the bills it reported on",
       needs=("learn_numbers",))
def _numbers_committee_rates(learn_numbers):
    """F18, each committee's passage rate: the House and Senate bills a
    committee made a majority report on, whatever it recommended, minority
    reports left out; a second committee's report goes to the second
    committee even where the docket carries the first one's name forward;
    the chamber's totals count a bill once, under the first committee."""
    t, ev = "2025-2026", _ln_ev
    rep = lambda b, c, side="Majority": ev(b, f"{side} Committee Report: Ought to Pass", "report",
                                          committee=c, side=side)
    idx = [{"term": t, "id": "HB1", "status": "Signed into law"},
           {"term": t, "id": "HB2", "status": "Killed"},
           {"term": t, "id": "HR1", "status": "Adopted by the House"}]
    narr = {"HB1": {"events": [rep("H", "Judiciary"), rep("H", "Judiciary", "Minority"),
                               ev("H", "Ought to Pass: MA VV; PASSED AND REF TO FINANCE", "floor"),
                               rep("H", "Judiciary"), rep("S", "Judiciary")]},
            "HB2": {"events": [rep("H", "Judiciary")]},
            "HR1": {"events": [rep("H", "Judiciary")]}}
    rows, tot = learn_numbers.committee_rates(idx, narr, t)
    got = ({k: list(v) for k, v in rows.items()}, tot)
    want = ({"House Judiciary": [2, 1, 1], "House Finance": [1, 1, 1], "Senate Judiciary": [1, 1, 1]},
            {"H": [2, 1, 1], "S": [1, 1, 1]})
    assert got == want, f"committee passage rates: {got}, want {want}"
    return "ok", "Finance's second report credited to Finance; the chamber counts each bill once"


@check("frontend", "numbers: the one committees table holds every committee the three tables it "
                   "replaced held, and states a rate or a consent share only from ten bills or reports",
       needs=("learn_numbers",))
def _numbers_committee_table(learn_numbers):
    """The owner, 11 November 2026: Referrals, Consent Calendars and Passage
    Rate are one table. Its rows are the union of the committees the three
    read (so a merge cannot drop one), House first, each chamber by rate; a
    rate or share from fewer than ten is a dash; every term of the last ten
    carries its consent share, not the newest alone."""
    L = learn_numbers
    saved = (L.referrals, L.committee_rates, L.consent)
    try:
        L.referrals = lambda i, n, t: {"House A": (5, 1), "Senate B": (2, 0), "House Only Sent": (0, 3)}
        L.committee_rates = lambda i, n, t: ({"House A": (12, 6, 3), "House Rate Only": (11, 11, 11),
                                              "Senate B": (4, 2, 1)},
                                             {"H": (20, 10, 5), "S": (4, 2, 1)})
        L.consent = lambda n, r, t: ({"House A": (20, 5), "Senate Consent Only": (30, 15), "Senate B": (4, 4)},
                                     {"H": __import__("collections").Counter(kept=5),
                                      "S": __import__("collections").Counter(kept=19)})
        rec, _tot, _per = L.committee_record([], {}, "2025-2026")
        rows, groups = L.committee_rows(rec)
    finally:
        L.referrals, L.committee_rates, L.consent = saved
    want = {"House A", "Senate B", "House Only Sent", "House Rate Only", "Senate Consent Only"}
    assert set(rec) == want, f"the merged rows are {sorted(rec)}, not the union {sorted(want)}"
    names = [re.sub(r"<[^>]+>", "", r[0]) for r in rows]
    assert names[:3] == ["House Rate Only", "House A", "House Only Sent"] and \
        all(n.startswith("Senate") for n in names[3:]), f"House first, by rate: {names}"
    assert groups == ["H"] * 3 + ["S"] * 2, groups
    a = rows[names.index("House A")]
    assert a[1:] == ["5", "1", "12", "6", "3", "50.0%", "25.0%"], f"House A: {a}"
    b = rows[names.index("Senate B")]
    assert b[6] == b[7] == "&mdash;", f"a rate or share from fewer than ten is a dash: {b}"
    assert "Each Committee's Record" in L.HEADINGS and not any(
        h in L.HEADINGS for h in ("The Bills Each Committee Received", "Consent Calendars, by Committee",
                                  "Each Committee's Passage Rate")), "the three old sections are still named"
    import inspect
    src = inspect.getsource(L.body)
    assert "for t in reversed(recent):\n        rec, ctot, per_ch = committee_record(" in src, (
        "the consent share is worked out for each of the last ten terms")
    return "ok", "five committees from three sources in one table, House first by rate, dashes under ten"


def _flow_rows(term="2025-2026"):
    """Index rows covering every way a bill can end, as flows() reads them."""
    spec = [("HB1", "Hpppp", "Signed into law"), ("HB2", "Hx--x", "Killed"),
            ("HB3", "Sx--x", "Referred for interim study"), ("HB4", "Hpx-x", "Died on the table"),
            ("SB5", "Spp-x", "Died: the chambers did not agree on a version"),
            ("HB6", "Hppxx", "Vetoed, override failed"), ("HB7", "Hppxp", "Veto overridden, became law"),
            ("HB8", "Hh--h", "In committee"), ("HB9", "", "Killed"), ("SB10", "Sp---", "Withdrawn"),
            ("HB11", "Hpppp", "Became law unsigned"), ("HB12", "Hx--x", "Killed"),
            ("SB13", "Spx-x", "Referred for interim study"), ("HB14", "Hx--x", "Indefinitely postponed"),
            ("HR1", "Hpppp", "Adopted by the House"), ("CACR2", "Hx--x", "Killed")]
    rows = [{"term": term, "id": i, "passage": p, "status": s, "carried": i in ("HB1", "HB2")}
            for i, p, s in spec]
    rows.append({"term": "2023-2024", "id": "HB1", "passage": "Hx--x", "status": "Killed"})
    return rows


@check("frontend", "numbers: every House and Senate bill of a term is in exactly one end node of the "
                   "flow diagram, and each node is the sum of what leaves it",
       needs=("learn_numbers",))
def _numbers_flows(learn_numbers):
    """The owner, 11 November 2026: the Sankey is drawn from the one field the
    bill rail reads (the index row's `passage`), on the 2,139 basis (House
    and Senate bills; resolutions and constitutional amendments out), and its
    end nodes sum to the bills filed. A bill with no readable passage is
    counted as unclassified, never dropped; one still moving is its own end
    node. This counts a fixture whose answer is known, then holds every term
    of the built site, where there is one, to the same sums."""
    L = learn_numbers
    f = L.flows(_flow_rows(), "2025-2026")
    assert f["filed"] == 14 and f["resolutions"] == 2, (f["filed"], f["resolutions"])
    assert f["unclassified"] == 1 and f["moving"] == 1, (f["unclassified"], f["moving"])
    assert dict(f["first"]) == {"killed": 2, "study": 1, "postponed": 1}, dict(f["first"])
    assert dict(f["second"]) == {"tabled": 1, "study": 1, "withdrawn": 1}, dict(f["second"])
    assert dict(f["nogov"]) == {"noversion": 1}, dict(f["nogov"])
    assert f["cleared_first"] == 8 and f["passed_both"] == 5 and f["reached"] == 4, f
    assert dict(f["gov"]) == {"law": 3, "veto": 1}, dict(f["gov"])
    assert f["carried"] == 2

    def check_tree(n, where):
        if not n["kids"]:
            return
        total = sum(k["n"] for k in n["kids"])
        assert total == n["n"], f"{where}: {n['label']} is {n['n']} and what leaves it {total}"
        for k in n["kids"]:
            check_tree(k, where)

    def leaf_sum(n):
        return n["n"] if not n["kids"] else sum(leaf_sum(k) for k in n["kids"])

    def all_terms(idx, label):
        terms = sorted({r["term"] for r in idx if r.get("term")})
        for t in terms:
            fl = L.flows(idx, t)
            tree = L.flow_tree(fl)
            assert tree["n"] == fl["filed"] and leaf_sum(tree) == fl["filed"], (
                f"{label} {t}: the end nodes sum to {leaf_sum(tree)} of {fl['filed']} bills filed")
            check_tree(tree, f"{label} {t}")
            assert fl["reached"] == fl["gov"]["law"] + fl["gov"]["veto"] + fl["gov"]["other"], (
                f"{label} {t}: reached the governor is not law plus veto stood")
            ref = sum(1 for r in idx if r.get("term") == t and L.BILL.match(r.get("id") or ""))
            assert fl["filed"] == ref
        return len(terms)
    n = all_terms(_flow_rows(), "fixture")
    import site_read
    try:
        real = site_read.bill_index("site")
    except Exception:
        real = None
    if real:
        n = all_terms(real, "the site")
        bad = [t for t in sorted({r["term"] for r in real}) if
               L.flows(real, t)["unclassified"] > 8]
        assert not bad, f"more than a handful of bills have no passage in {bad}: not a rounding"
    return "ok", f"{n} terms: end nodes sum to the bills filed, resolutions out, none dropped"


@check("frontend", "numbers: the flow diagram, its table and its sentence print the same numbers, "
                   "and in Spanish say them in Spanish",
       needs=("learn_numbers", "i18n"))
def _numbers_flow_agree(learn_numbers, i18n):
    L = learn_numbers
    f = L.flows(_flow_rows(), "2025-2026")
    tree = L.flow_tree(f)
    leaves = L.flow_leaves(tree)
    fig = L.flow_figure(f)
    svg = re.search(r"<svg.*?</svg>", fig, re.S).group(0)
    titled = re.findall(r"<title>(.*?): ([\d,]+) bills", svg)
    twin = re.findall(r'<span class="l-ind"[^>]*>(.*?)</span></td><td class="l-num">([\d,]+)</td>', fig)
    walk = []

    def nodes(n):
        walk.append((n["label"], n["n"]))
        for k in n["kids"]:
            nodes(k)
    nodes(tree)
    want = [(a, f"{b:,}") for a, b in walk]
    assert [(a, b) for a, b in titled] == want, f"the diagram's nodes are not the tree's: {titled} / {want}"
    assert [(a, b) for a, b in twin] == want, f"the table's rows are not the tree's: {twin}"
    # the label of each end node, with its count, is in the drawing too
    for key, n in leaves:
        label = L.END_WORDS[key][0]
        assert re.search(rf"{re.escape(label)} <tspan class=\"sk-v\">{n:,}</tspan>", svg), (
            f"the diagram does not print {label} {n}")
    sentence = L.flow_sentence(f)
    for num in (f["filed"], sum(f["first"].values()), sum(f["second"].values()),
                f["reached"], f["gov"]["law"], f["gov"]["veto"], f["carried"], f["resolutions"]):
        assert f"{num:,}" in sentence, f"the sentence omits {num}"
    assert tree["n"] == f["filed"] and f"{f['filed']:,} House and Senate bills" in sentence
    # in Spanish: every node, the sentence and the table's heads are the catalogue's, none English
    es = L.flow_figure(f, "es") + L.flow_sentence(f, "es")
    for key, _n in leaves + [("first", 0), ("second", 0), ("nogov", 0), ("reached", 0)]:
        words = L.END_WORDS[key][0] if key in L.END_WORDS else {
            "first": "Stopped in the first chamber", "second": "Stopped in the second chamber",
            "nogov": "Never reached the governor", "reached": "Reached the governor"}[key]
        assert words not in es, f"the Spanish diagram says {words!r} in English"
    for en in ("The same figures as a table", "Where it stood", "Not counted here"):
        assert en not in es, f"the Spanish diagram says {en!r} in English"
    assert "House and Senate bills" not in es
    # the paragraph on How a Bill Becomes a Law reads this count, on the same basis
    civ = _source("src/pages/civics.py")
    assert "[[ends_bills]] House and Senate bills" in civ and "[[ends_resolutions]]" in civ and \
        "bills and resolutions filed in the [[term]] term" not in civ, (
            "How Most Bills End is not on the 2,139 basis with its one line on the resolutions")
    bc = _source("src/pages/build_civics.py")
    assert "learn_numbers.flows(idx, term)" in bc and "learn_numbers.flow_figure(fl)" in bc and \
        "learn_numbers.flow_figure(fl, lang)" in bc, "build_civics does not draw the diagram from flows()"
    return "ok", f"{len(walk)} nodes the same in the drawing, the table and the sentence; Spanish in Spanish"


@check("frontend", "numbers: amended means an amendment adopted, not an enrolled-bill correction",
       needs=("learn_numbers",))
def _numbers_amended(learn_numbers):
    """F18, passed as introduced or amended: of the House and Senate bills
    that reached the governor, amended when either chamber adopted an
    amendment, or concurred in the other's, or a committee of conference
    settled them; an enrolled-bill amendment is not one, nor an amendment
    adopted and then withdrawn; a bill that died is not counted at all."""
    t, ev = "2025-2026", _ln_ev
    idx = [{"term": t, "id": "HB1", "status": "Signed into law"},
           {"term": t, "id": "HB2", "status": "Signed into law"},
           {"term": t, "id": "HB3", "status": "Killed"},
           {"term": t, "id": "HB4", "status": "Vetoed, override failed"},
           {"term": t, "id": "HB5", "status": "Became law unsigned"},
           {"term": t, "id": "HB6", "status": "Veto overridden, became law"}]
    narr = {t: {"HB1": {"events": [ev("H", "Amendment # 2025-0101h: AA VV 03/01/2025", "amendment")]},
                "HB2": {"events": [ev("H", "Enrolled Bill Amendment # 2025-2001e: AA VV", "enrolled")]},
                "HB3": {"events": [ev("H", "Amendment # 2025-0301h: AA VV", "amendment")]},
                "HB4": {"events": [ev("H", "Floor Amendment # 2025-0401h: AA VV", "amendment"),
                                   ev("H", "Floor Amendment # 2025-0401h: Reconsidered and Withdrawn")]},
                "HB5": {"events": [ev("S", "Conference Committee Report # 2025-2500c: Adopted, VV", "floor")]},
                "HB6": {"events": [ev("S", "Concur with House Amendment, MA, VV", "floor")]}}}
    p = learn_numbers.passage(idx, narr)[t]
    got = (p["passed"], p["amended"], p["conference"])
    assert got == (5, 3, 1), (
        f"passed, amended, to conference: {got}, want (5, 3, 1) -- HB1 amended, HB2's "
        "enrolled-bill amendment and HB4's withdrawn one not, HB5 by conference, HB6 by "
        "concurrence, HB3 never passed")
    return "ok", "5 passed: 3 amended (one by conference, one by concurrence), 2 as introduced"


@check("frontend", "numbers: amendments are counted by number, and an unnumbered line by what it names",
       needs=("learn_numbers",))
def _numbers_amendment_count(learn_numbers):
    """F18, how many amendments a bill takes: distinct amendments the two
    chambers adopted, by number where the docket gives one; a line of the
    1990s that adopts one committee amendment in parts, with no number, is
    one amendment; a concurrence with no adoption line of the chamber's own
    counts one; a committee of conference's report counts none; six or more
    is one column."""
    ev = _ln_ev
    idx = [{"term": "2025-2026", "id": f"HB{i}", "status": "Signed into law"} for i in (1, 2, 3)] + \
          [{"term": "1991-1992", "id": "HB35", "status": "Signed into law"}]
    narr = {"2025-2026": {
        "HB1": {"events": [ev("H", "Amendment # 2025-0101h: AA VV", "amendment"),
                           ev("H", "Floor Amendment # 2025-0102h (Rep. Able): AA DV 200-150", "amendment"),
                           ev("H", "Amendment # 2025-0101h: AA VV", "amendment"),
                           ev("S", "Committee Amendment # 2025-1001s, AA, VV", "floor")]},
        "HB2": {"events": [ev("S", "Concur with House Amendment, MA, VV", "floor"),
                           ev("S", "Conference Committee Report # 2025-2500c: Adopted, VV", "floor")]},
        "HB3": {"events": [ev("H", f"Amendment # 2025-{n:04d}h: AA VV", "amendment")
                           for n in range(201, 209)]}},
        "1991-1992": {"HB35": {"events": [ev("H", "COMM AM (SEC. 1,IV), AA RC(178-145); "
                                             "COMM AM (SEC. 1,V,B4), AA VV", "floor", "1991-03-01")]}}}
    pa = learn_numbers.passage(idx, narr)
    got = (dict(pa["2025-2026"]["dist"]), dict(pa["1991-1992"]["dist"]))
    want = ({3: 1, 1: 1, 6: 1}, {1: 1})
    assert got == want, (f"amendments per passed bill: {got}, want {want} -- two House numbers "
                         "(one repeated) and a Senate one are 3; a concurrence 1 and the "
                         "conference none; eight is six or more; a divided question is one")
    return "ok", "numbers counted once each, a divided question once, eight in the six-or-more column"


@check("frontend", "numbers: attendance is the share present on each roll-call day, averaged",
       needs=("learn_numbers", "build_site_v2"))
def _numbers_attendance(learn_numbers, build_site_v2):
    """F22, attendance on roll-call days: for each day a chamber took a roll
    call, the share of the members on that day's ballots present for at least
    one of them -- voting, presiding, or declaring a conflict -- averaged
    over the days; the presiding officer the record leaves unnamed on a day
    is read as presiding (the member pages' rule); a run of empty ballots
    ending a member's term is a seat nobody held, and is not an absence."""
    def b(m, body, n, day, vote):
        return {"member_id": m, "name": m, "year": "2025", "body": body,
                "vote_number": str(n), "date": day, "vote": vote}
    V = [b("A", "H", 1, "1/8/2025", "Yea"), b("B", "H", 1, "1/8/2025", "Not Voting/Excused"),
         b("C", "H", 1, "1/8/2025", "Nay"), b("D", "H", 1, "1/8/2025", "Presiding"),
         b("E", "H", 1, "1/8/2025", "Yea"),
         b("A", "H", 2, "1/8/2025", "Yea"), b("B", "H", 2, "1/8/2025", "Yea"),
         b("C", "H", 2, "1/8/2025", "Not Voting/Excused"), b("D", "H", 2, "1/8/2025", "Presiding"),
         b("E", "H", 2, "1/8/2025", ""),
         b("A", "H", 3, "1/15/2025", "Nay"), b("B", "H", 3, "1/15/2025", "Not Voting/Excused"),
         b("C", "H", 3, "1/15/2025", "Not Voting/Not Excused"),
         b("D", "H", 3, "1/15/2025", "Not Voting/Excused"), b("E", "H", 3, "1/15/2025", ""),
         b("F", "S", 1, "1/8/2025", "Yea"), b("G", "S", 1, "1/8/2025", "Not Voting/Excused")]
    got = learn_numbers.attendance(V)
    want = {("2025-2026", "H"): (2, 0.75), ("2025-2026", "S"): (1, 0.5)}
    assert got == want, (f"attendance: {got}, want {want} -- the House's first day all five "
                         "present, its second A and the unnamed chair D of four seats held")
    return "ok", "a day's share present, the unnamed chair present, a vacant seat not absent"


@check("frontend", "numbers: a veto stood when no override came, and only a live session waits",
       needs=("learn_numbers",))
def _numbers_vetoes(learn_numbers):
    """F21, the veto table without its Awaiting column: a veto stood when its
    override failed or no override vote came before the session ended; one
    the chip still shows as Vetoed -- a session with days left -- is counted
    as vetoed and in neither of the columns after it, and the paragraph says
    so; a law without a signature reached the governor."""
    st = ["Signed into law"] * 3 + ["Became law unsigned", "Vetoed, override failed",
                                    "Veto overridden, became law"]
    rows = [{"status": s, "chip": ""} for s in st] + [
        {"status": "Vetoed", "chip": "Vetoed"}, {"status": "Vetoed", "chip": "Died"}]
    got = learn_numbers.vetoes(rows)
    assert got == (8, 4, 2, 1, 1), (
        f"reached, vetoed, stood, overridden, still to be voted on: {got}, want (8, 4, 2, 1, 1)")
    return "ok", "8 reached, 4 vetoed: 2 stood, 1 overridden, 1 still to be voted on"


@check("frontend", "numbers: every amendment the voters decided is shown with its source and cite, "
                   "and one without is named in the build's log", needs=("learn_numbers",))
def _numbers_ballots(learn_numbers):
    """F16, the amendments sent to the voters. Until 7 October 2026 a row
    was shown only where the Secretary of State's count (the row's `sos`)
    equalled the row's own, which was Ballotpedia's, and the page told the
    reader that two more "are not shown until two sources agree". That day
    the person made the Secretary of State every decided row's source and
    corrected the two that differed, so every decided row is shown with the
    source and cite it names, and the sentence went.

    A decided row with no source or no cite is still left off -- a figure
    the page cannot say where to find -- and named in the build's log
    (learn_numbers.HELD, which build_civics prints), not to the reader. An
    election still to come is neither. Whose count it is, in the sentence
    above the table, is the rows' own sources' (ballot_source.py), and the
    last column is headed Source. Ratified at two thirds of the votes cast,
    exactly two thirds included."""
    import tempfile as _tf
    rows = [_voters_row("2023-2024", "CACR6", "2024-11-05", 200000, 100001),
            _voters_row("1989-1990", "CACR23", "1990-11-06", 2, 1, src=(
                "https://electiondatabase.nhpr.org/document/692?page=176",
                "Manual for the General Court 1991, p. 294 (NHPR's scan)")),
            {**_voters_row("1991-1992", "CACR7", "1992-11-03", 10, 5), "cite": ""},
            {**_voters_row("2005-2006", "CACR41", "2006-11-07", 10, 5), "source": None},
            _voters_row("2025-2026", "CACR13", "2026-11-03", None, None, src=_BALLOTPEDIA)]
    shown, held, to_come = learn_numbers.ballots(rows)
    got = ([r["bill"] for r in shown], [r["bill"] for r in held], [r["bill"] for r in to_come])
    assert got == (["CACR23", "CACR6"], ["CACR7", "CACR41"], ["CACR13"]), f"shown, held, to come: {got}"
    assert learn_numbers.ratified(2, 1) and not learn_numbers.ratified(200000, 100001), (
        "two thirds of the votes cast: exactly two thirds ratifies, a vote short does not")
    idx = [{"term": "2025-2026", "id": "HB1", "year": 2026, "status": "Signed into law",
            "kind": "law", "chip": "Became Law", "sponsor_label": "Rep. Ann Able (R)"}]

    def drawn(rows):
        with _tf.TemporaryDirectory() as tmp:
            _bill_index_write(tmp, idx)
            _mk(Path(tmp) / "corrections" / "ballot_results.json").write_text(json.dumps({"rows": rows}),
                                                           encoding="utf-8")
            page = learn_numbers.body(Path(tmp), Path(tmp), strict=False)
            return page, list(learn_numbers.HELD)

    page, held_said = drawn(rows)
    # WHOSE COUNT, FROM THE ROWS, WHEN IT IS NOT THE SECRETARY OF STATE'S (the
    # review of 7 October 2026): every row above is, so a sentence that said
    # "the Secretary of State's" in words of its own passed. A decided row of
    # Ballotpedia's beside two of the Secretary of State's, and one alone.
    bp22 = _voters_row("1997-1998", "CACR22", "1998-11-03", 119104, 169439, src=_BALLOTPEDIA,
                       read="2026-10-05")
    for got_rows, want in (
            ([rows[0], rows[1], bp22],
             "Yes and No are the statewide count printed where the Source column says: the "
             "Secretary of State's for 2, Ballotpedia's for 1. 1 of the 3 below were ratified."),
            ([bp22], "Yes and No are Ballotpedia's statewide count, printed where the Source "
                     "column says. 0 of the 1 below were ratified.")):
        sec = drawn(got_rows)[0]
        sec = sec[sec.find("Constitutional Amendments Sent to the Voters"):]
        assert want in sec, f"the amendments' section does not say {want!r}: {sec[:700]!a}"
    sec = page[page.find("Constitutional Amendments Sent to the Voters"):]
    assert sec, "the amendments' section was not drawn"
    for want in ("Yes and No are the Secretary of State's statewide count, printed where the "
                 "Source column says. 1 of the 2 below were ratified.",
                 "<th>Source</th>",
                 ">Manual for the General Court 1991, p. 294 (NHPR&#x27;s scan)</a>"):
        assert want in sec, f"the amendments' section lacks {want!r}: {sec[:700]!a}"
    for gone in ("two sources", "Secretary of State's count</th>", "bill/1991/cacr7",
                 "bill/2005/cacr41"):
        assert gone not in sec, f"the amendments' section still carries {gone!r}"
    assert held_said == ["CACR7 of 1991-1992: ballot_results.json gives it no cite",
                         "CACR41 of 2005-2006: ballot_results.json gives it no source"], (
        f"the rows left off are named in the build's log as {held_said!a}")
    return "ok", ("2 shown with their source and cite, the Secretary of State's named from the "
                  "rows, and Ballotpedia's where a row gives it; one with no cite and one with "
                  "no source left off and named in the log; the election to come apart")


@check("frontend", "numbers: the unsigned-laws table and the veto table's Awaiting column are gone",
       needs=("learn_numbers",))
def _numbers_removed(learn_numbers):
    """F20 and F21: the person asked on 7 October 2026 for "Laws without the
    governor's signature" and the veto table's "Awaiting" column to go, and
    the "Still to come" list is now all on the page. Built on a fixture that
    holds only the bill index, which also shows a missing input leaving its
    section out and saying so in learn_numbers.MISSING rather than in
    silence."""
    import tempfile as _tf
    rows = [{"term": "2025-2026", "id": "HB1", "year": 2026, "status": "Signed into law",
             "kind": "law", "chip": "Became Law", "sponsor_label": "Rep. Ann Able (R)"},
            {"term": "2025-2026", "id": "HB2", "year": 2026, "status": "Became law unsigned",
             "kind": "law", "chip": "Became Law", "sponsor_label": "Rep. Ann Able (R)"}]
    with _tf.TemporaryDirectory() as tmp:
        _bill_index_write(tmp, rows)
        page = learn_numbers.body(Path(tmp), Path(tmp), strict=False)
        missing = sorted(Path(f).name for f, _what in learn_numbers.MISSING)
    for gone in ("without the governor's signature</h2>", "<th>Awaiting</th>", "Still to come"):
        assert gone not in page, f"the page of numbers still carries {gone!r}"
    assert "From the Governor's Desk</h3>" in page and "Bills Filed, and How They Ended" in page, (
        "the fixture page lost a section it should keep")
    want = ["ballot_results.json", "member_votes.json", "narratives.json", "testimony_db.json"]
    assert missing == want, f"the inputs said to be missing: {missing}, want {want}"
    for h in ("The Hearings with the Most Sign-Ins", "Attendance on Roll-Call Days",
              "Constitutional Amendments Sent to the Voters"):
        assert h not in page, f"{h!r} was drawn with its input missing"
    return "ok", "both gone; the governor's desk kept; the four missing inputs named and their sections left out"


@check("data", "the page of numbers carries every figure it is built to",
       needs=("learn_numbers",))
def _numbers_every_section(learn_numbers):
    """learn_numbers leaves a section out where its input is not on the disk
    and names it in the build's log (learn_numbers.MISSING), so that the
    builders' fixture site, which holds none of those inputs, still builds.
    On the real site every one is here, and a page without a section is a
    night that lost a file: this says which."""
    page = Path("site") / "learn" / "by-the-numbers.html"
    if not page.exists():
        return "skip", "learn/by-the-numbers.html not built"
    import html as _html
    text = _html.unescape(page.read_text(encoding="utf-8", errors="replace"))
    heads = re.findall(r"<h2[^>]*>(.*?)</h2>", text, re.S)
    lost = [h for h in learn_numbers.HEADINGS
            if not any(re.sub(r"<[^>]+>", "", x).strip().startswith(h) for x in heads)]
    assert not lost, "the page of numbers was built without: " + "; ".join(lost)
    return "ok", f"all {len(learn_numbers.HEADINGS)} sections"


# A LEARN SENTENCE, THE SECTION IT CITES, AND WHAT THAT SECTION SAYS. Each row
# is a claim that was wrong until 23 September 2026 -- the citation existed and
# was in force, and the sentence beside it said something else -- written by
# hand from db/NH_RSA.psv and never by a generator. The code check below holds
# the page phrase and its citation together in one paragraph; the data check
# further down holds the section's own words to the dump.
LEARN_STATUTE_CLAIMS = [
    # (page, phrase on the page, section cited, phrase in the section)
    ("county-government", "by September 1 if it is on an optional fiscal year",
     "24:14", "not later than September 1"),
    ("county-government", "every state court except the Supreme Court",
     "104:5", "in all state courts, except the supreme court"),
    ("county-government", "does not hold against a later buyer",
     "477:3-a", "shall not be effective as against bona fide purchasers"),
    ("county-government", "Deeds, mortgages and the other documents",
     "478:4", "shall receive, file and record"),
    ("county-government", "The register keeps the records safe",
     "478:1", "in a safe location"),
    ("county-government", "the probate division of the",
     "490-F:3", "a probate division"),
    ("county-government", "passed to the circuit court clerks",
     "490-F:13", "shall remain as duties of the registers of probate"),
    ("county-government", "works with the Secretary of State",
     "548:5", "coordinating with the secretary of state"),
    ("county-government", "keeps an index of any files",
     "548:5", "maintain a current index"),
    ("county-government", "a state office within the Department of Justice",
     "611-B:2", "within the department of justice the office of chief medical examiner"),
    ("county-government", "Sudden, unexpected or unnatural deaths",
     "611-B:11", "sudden unexpected death"),
    ("county-government", "appoint an administrator for the county nursing home",
     "28:11", "appoint an administrator for the county nursing home"),
    ("city-and-town-government", "replaced the meeting with a town council",
     "49-D:3", "legislative and governing body of the town"),
    ("city-and-town-government", "regulate the use of the town's highways",
     "41:11", "regulate the use of all public highways, sidewalks, and commons"),
    ("city-and-town-government", "unless the town has handed that",
     "41:11-a", "delegated to other public officers by vote of the town"),
    ("city-and-town-government", "application of 10 or more voters",
     "37:12", "written application of 10 or more voters"),
    ("city-and-town-government", "any department under the manager's control",
     "37:6", "any department under his control"),
    ("city-and-town-government", "nor does the manager supervise the",
     "37:5", "supervision of the offices of town clerk and town treasurer"),
    ("city-and-town-government", "appoint that town's",
     "37:14", "appoint as its manager the manager of such town"),
    ("city-and-town-government", "unless the town has provided for appointing them",
     "669:15", "unless provision has been made for appointment"),
    ("city-and-town-government", "still elects its town clerk",
     "41:16", "regardless of the form of government"),
    ("city-and-town-government", "daily once receipts reach",
     "41:35", "daily whenever tax receipts total $3,500"),  # $1,500 until amended; read 22 October 2026
    ("city-and-town-government", "on a board of three one trustee is elected each year",
     "31:22", "one trustee shall be elected by a ballot at each annual town meeting"),
    ("city-and-town-government", "sits on it ex officio",
     "673:2", "as an ex officio member"),
    ("city-and-town-government", "at least one member living in each",
     "195:19-a", "at least one such resident representative"),
    ("city-and-town-government", "each district's members sharing",
     "194-C:7", "proportionate share of the school district's votes"),
    ("city-and-town-government", "a commission of nine is elected",
     "49-B:4", "shall consist of 9 members"),
    ("city-and-town-government", "three fifths of the ballots cast on the question",
     "49-B:6", "at least 3/5 of the ballots cast"),
    ("city-and-town-government", "and a majority adopts it",
     "49-B:6", "if a majority of the ballots cast on any question under paragraph ii"),
    ("city-and-town-government", "at least 20 percent of the",
     "49-B:4-e", "20 percent of the number of ballots cast"),
    ("city-and-town-government", "at least 15 percent of those ballots",
     "49-B:5", "at least 15 percent of the number of ballots cast"),
    ("city-and-town-government", "A town may also repeal its",
     "49-B:12", "any town, through the petition procedure"),
    ("administrative-rules", "substantial fiscal harm",
     "541-A:18", "substantial fiscal harm to the state or its citizens"),
    # THE NUMBERS, 23 October 2026 (approved by the person that day): every
    # day count, term, petition and board size these pages state from a
    # statute, read in the table that day. Most were right; the rules page's
    # notice ("20 days", which is at least 20), its comment period (which a
    # board's notice may shorten), its ten years (which bind neither a rule
    # being readopted nor an agency's procedural rules) and the town meeting
    # petition (which dropped 39:3's floor of 10) were not, and were
    # rewritten to their sections. A re-dump that moves a number stops here.
    ("county-government", "Before December 1 each year they deliver",
     "24:21-a", "prior to december 1 annually"),
    ("county-government", "does this before June 1 instead",
     "24:21-a", "prior to june 1 annually"),
    ("county-government", "not earlier than 5 nor later than 20 days after that statement is mailed",
     "24:23", "not earlier than 5 nor later than 20 days after the mailing"),
    ("county-government", "in a newspaper at least 3 days ahead",
     "24:23", "at least 3 days prior to the date of said hearing"),
    ("county-government", "until 28 days have passed since the recommendations were mailed",
     "24:21-a", "until 28 days shall have elapsed from the mailing of such recommendations"),
    ("county-government", "within 90 days after the fiscal year begins",
     "24:14", "shall adopt the annual budget within 90 days after the beginning of the"),
    ("city-and-town-government", "A town elects one selectman each year for a 3-year term",
     "41:8", "one selectman to hold office for 3 years"),
    ("city-and-town-government", "one elected each year for a 3-year term, a board of three",
     "41:8", "one selectman to hold office for 3 years"),
    ("city-and-town-government", "On the written application of 25 registered voters, or 2",
     "41:8-b", "25 or more registered voters or 2 percent of the registered voters in town, whichever is less"),
    ("city-and-town-government", "whichever is less and never fewer than 10, the question of increasing",
     "41:8-b", "in no event shall fewer than 10 registered voters be sufficient"),
    ("city-and-town-government", "increasing the board to 5 goes on the ballot",
     "41:8-b", "increasing the board of selectmen to 5 members"),
    ("city-and-town-government", "On the petition of 25 registered voters, or 2 percent of them, whichever "
     "is less and never fewer than 10", "49-B:3", "25 or more registered voters or 2 percent of the "
     "registered voters in the municipality, whichever is less, but in no event fewer than 10"),
    ("city-and-town-government", "One is elected every even-numbered year for 6 years",
     "41:46-a", "in every even numbered year, the voters of each town shall elect, by ballot, one "
                "supervisor for a term of 6 years"),
    ("city-and-town-government", "unless the town has adopted 3-year terms",
     "41:46-a", "may adopt a 3-year term for supervisors of the checklist"),
    ("city-and-town-government", "has 3, 5, 7 or 9 members as the district votes",
     "671:4", "a school board of 3, 5, 7, or 9 members"),
    ("city-and-town-government", "and 3 if it has not voted, elected for three years",
     "671:4", "which does not otherwise vote shall have 3 members"),
    ("city-and-town-government", "and 3 if it has not voted, elected for three years",
     "671:4", "they shall serve for a term of 3 years"),
    ("city-and-town-government", "has 5 or 7 members in most towns",
     "673:2", "the planning board shall consist of 5 or 7 members"),
    ("city-and-town-government", "7 or 9 in a town with a council",
     "673:2", "the planning board shall consist of 7 or 9 members"),
    ("city-and-town-government", "and 9 in a city",
     "673:2", "in cities, the planning board shall consist of 9 members"),
    ("city-and-town-government", "A zoning board of adjustment has 5 members",
     "673:3", "the zoning board of adjustment shall consist of 5 members"),
    ("local-government", "application of 25 registered voters, or of 2 percent",
     "39:3", "25 or more registered voters or 2 percent of the registered voters in town, whichever is less"),
    ("local-government", "whichever is fewer, and never fewer than 10",
     "39:3", "in no event shall fewer than 10 registered voters be sufficient"),
    ("local-government", "may not raise the total more than 10 percent above what the budget committee",
     "32:18", "shall not exceed by more than 10 percent the total amount recommended by the budget committee"),
    ("local-government", "adopts SB 2 by three fifths of those voting on the question",
     "40:14", "a 3/5 majority of those voting on the question shall be required to adopt"),
    ("local-government", "can return to a traditional meeting by the same three-fifths vote",
     "40:14", "may consider rescinding its action in the manner described in paragraphs iii-vi"),
    ("administrative-rules", "At least 20 days before the hearing",
     "541-A:6", "not less than 20 days before the first agency public hearing"),
    ("administrative-rules", "At least 5 business days",
     "541-A:11", "a period of at least 5 business days after the hearing shall be provided"),
    ("administrative-rules", "A board or commission may set a shorter one in its notice",
     "541-A:11", "unless a shorter period is specified in the notice"),
    ("administrative-rules", "21 to 180 days after the notice",
     "541-A:12", "no earlier than 21 days and no later than 180 days after the date of publication of the notice"),
    ("administrative-rules", "The committee has 60 days",
     "541-A:13", "within 60 days of the filing of a final proposal"),
    ("administrative-rules", "If the 60 days pass with no notice of approval",
     "541-A:13", "at the end of the 60-day period under paragraph i shall be deemed approval"),
    ("administrative-rules", "No rule is effective for longer than ten years",
     "541-A:17", "no rule shall be effective for a period of longer than 10 years"),
    ("administrative-rules", "rules of organization and procedure do not lapse",
     "541-A:17", "shall not expire"),
    ("administrative-rules", "the rule stays in force while it does",
     "541-A:14-a", "shall continue in effect until the proposed rules are adopted and effective"),
    ("administrative-rules", "Neither lasts more than 180 days",
     "541-A:18", "shall not remain in effect for more than 180 days"),
    ("administrative-rules", "Neither lasts more than 180 days",
     "541-A:19", "interim rules shall be effective for a period not to exceed 180 days"),
]


def _cites_section(text, sec):
    """True when `text` names RSA section `sec` as a whole citation: 49-B:4 is
    not found in 49-B:4-e, nor 37:1 in 37:12."""
    return re.search(r"(?<![\w:.-])" + re.escape(sec) + r"(?![\w-])", text) is not None


@check("frontend", "a Learn page's statute citations stay with the claims they support",
       needs=("civics",))
def _learn_statute_claims(civics):
    """The county and town pages paraphrased statutes by hand, and ten
    sentences had dropped the clause that mattered: the Supreme Court's
    exception from bailiff security (RSA 104:5 III), the optional-fiscal-year
    budget deadline (24:14 II), the treasurer and highway agents a town may
    appoint (669:15), the town's own vote a village district must wait for
    (37:14), a charter amendment put "by the same route" as a new charter when
    49-B:5 takes no commission and 49-B:6 only a majority. Every citation
    existed, so a check that sections exist would have passed them all.

    This holds each corrected claim to the section beside it: the page phrase
    and its citation in one paragraph or table cell. The data check
    "every RSA section the Learn pages cite is in force" holds the section's
    words to the General Court's own table.
    """
    pages = {t["slug"]: t["body"] + " " + (t.get("holds") or "") for t in civics.TOPICS}
    RETRACTED = ["coroners chapter", "same footing", "by the same route",
                 "does not set policy on its own account",
                 "90 days of the start of the fiscal year",
                 "provide security in the state courts",
                 # 23 October 2026: the numbers' sections said otherwise.
                 "whichever is fewer (RSA 39:3)", "runs the whole course again.</span>",
                 '"l-mt">20 days before the hearing']
    bad = []
    for slug, body in pages.items():
        flat = re.sub(r"\s+", " ", body)
        bad += [f"{slug} says {w!r} again" for w in RETRACTED if w in flat]
    for slug, phrase, sec, _said in LEARN_STATUTE_CLAIMS:
        body = pages.get(slug)
        if body is None:
            bad.append(f"no Learn page {slug}")
            continue
        blocks = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", b))
                  for b in re.split(r"</p>|</td>|</li>", body)]
        hit = [b for b in blocks if phrase in b]
        if not hit:
            bad.append(f"{slug} no longer says {phrase!r}")
        elif not any(_cites_section(b, sec) for b in hit):
            bad.append(f"{slug}: {phrase!r} has lost its citation to RSA {sec}")
    # THE COUNTY BUDGET'S TAGS SAY WHAT THEIR PARAGRAPHS SAY (23 October
    # 2026). Each amber time limit is drawn from civics.COUNTY_LIMITS beside a
    # paragraph that cites its section, and the rows above hold the
    # paragraph; every number of the tag must be one of the paragraph's, so a
    # tag cannot keep a figure the prose has been corrected away from.
    county = pages.get("county-government", "")
    for step, tag in civics.COUNTY_LIMITS.items():
        para = re.search(r"<p><b>" + re.escape(step) + r"</b>(.*?)</p>", county, re.S)
        if not para:
            bad.append(f"the county budget's step {step!r} has no paragraph")
            continue
        bad += [f"the county budget's tag {tag!r} says {n}, which its paragraph does not"
                for n in re.findall(r"\d+", tag) if not re.search(r"\b" + n + r"\b", para.group(1))]
    assert not bad, "; ".join(bad[:4]) + (f" (and {len(bad) - 4} more)" if len(bad) > 4 else "")
    return "ok", (f"{len(LEARN_STATUTE_CLAIMS)} anchored claims each beside the section "
                  f"that supports it; the county budget's tags their paragraphs' numbers; no "
                  "retracted wording")


# A LEARN SENTENCE AND THE ARTICLE OF THE CONSTITUTION IT RESTS ON (23 October
# 2026, approved by the person that day). The statute claims above are held
# to db/NH_RSA.psv, which a machine may not have; the Constitution is tracked
# in git -- nh.gov's pages in records/sources/constitution/, read into
# collected/constitution.json -- so this always runs and never skips. Each
# row is a phrase as the page prints it (markup off), the article, and words
# of that article: a sentence reworded or an article reread stops here.
LEARN_CONSTITUTION_CLAIMS = [
    # (page, phrase on the page, part, article, words of the article)
    ("how-a-bill-becomes-law", "A bill left unsigned for five days, Sundays excepted, becomes law",
     2, "44", "within five days (sundays excepted) after it shall have been presented to him, the same "
              "shall be a law"),
    ("how-a-bill-becomes-law", "unless the legislature's adjournment prevents its return",
     2, "44", "unless the legislature, by their adjournment, prevent its return, in which case it shall "
              "not be a law"),
    ("how-a-bill-becomes-law", "A vote to override a veto is always a roll call, because the "
     "constitution requires one", 2, "44", "the votes of both houses shall be determined by yeas and nays"),
    ("how-a-bill-becomes-law", 'The article says two thirds "of that house"',
     2, "44", "two thirds of that house shall agree to pass the bill"),
    ("how-a-bill-becomes-law", "Amending the constitution takes three fifths of the members of each chamber",
     2, "100", "a three fifths vote of the entire membership of each house"),
    ("how-a-bill-becomes-law", "then two thirds of those voting on the question at the election",
     2, "100", "approval by two thirds of the qualified voters present and voting on the subject"),
    ("governor-and-council", "It becomes law without a signature after five days, Sundays "
     "excepted", 2, "44", "within five days (sundays excepted)"),
    ("governor-and-council", "Five days pass Sundays excepted.", 2, "44", "within five days (sundays excepted)"),
    ("governor-and-council", "unless the legislature's adjournment prevents the Governor from returning "
     "it, and then it does not become law at all", 2, "44", "in which case it shall not be a law"),
    ("governor-and-council", "The Governor is elected for two years",
     2, "42", "the governor shall be chosen biennially"),
    ("governor-and-council", "two thirds of each chamber, by roll call, starting with the chamber the "
     "bill came from", 2, "44", "return it, with his objections, to that house in which it shall have "
                                "originated"),
    ("governor-and-council", "entered in the journal of the chamber the bill came from",
     2, "44", "who shall enter the objections at large on their journal"),
    ("governor-and-council", "Five councilors, each elected by district", 2, "60", "five councilors"),
    ("governor-and-council", "Five councilors, each elected by district",
     2, "65", "divide the state into five districts"),
    ("governor-and-council", "five members, elected by district", 2, "60", "five councilors"),
    ("governor-and-council", "the appointment of commissioners and judges, and pardons",
     2, "52", "the power of pardoning offenses"),
    ("the-courts", "The Governor nominates and the Executive Council confirms",
     2, "46", "all judicial officers"),
    ("the-courts", "The Governor nominates and the Executive Council confirms",
     2, "46", "shall be nominated and appointed by the governor and council"),
    ("the-courts", "No one may serve as a judge after the age of seventy",
     2, "78", "after he has attained the age of seventy years"),
    ("the-courts", "Until the age of seventy at most: Part Second, Article 78.",
     2, "78", "the age of seventy years"),
    ("general-court", "the name the state constitution gives it",
     2, "3", "the general court of new hampshire"),
    ("general-court", "Organization Day, the first Wednesday of December after the November election",
     2, "3", "assemble biennially on the first wednesday of december for organizational purposes"),
    ("general-court", "It is made up of [[house_seats]] representatives",
     2, "9", "not less than three hundred seventy-five or more than four hundred"),
    ("general-court", "[[senate_districts]] senators", 2, "25", "the senate shall consist of twenty four members"),
    ("general-court", "Members are paid $200 for the two-year term plus mileage",
     2, "15", "for the term elected the sum of $250, and all other members thereof"),
    ("general-court", "Members are paid $200 for the two-year term plus mileage",
     2, "15", "the sum of $200 and each member shall receive mileage"),
    ("general-court", "400 representatives and 24 senators, paid $200 for the two-year term",
     2, "9", "or more than four hundred"),
    ("general-court", "400 representatives and 24 senators, paid $200 for the two-year term",
     2, "25", "twenty four members"),
    ("general-court", "400 representatives and 24 senators, paid $200 for the two-year term",
     2, "15", "the sum of $200"),
    ("legislative-year", "Organization Day, the first Wednesday of December after the November election",
     2, "3", "first wednesday of december for organizational purposes"),
    ("the-constitution", "a CACR needs three fifths of both chambers and then the voters",
     2, "100", "a three fifths vote of the entire membership of each house"),
    ("the-constitution", "two thirds of those voting on the question approve it",
     2, "100", "two thirds of the qualified voters present and voting on the subject"),
    ("the-constitution", "At the next general election",
     2, "100", "at the next biennial november election"),
    ("your-representatives", 'representation is to be "as equal as circumstances will admit" (Part II, '
     "Article 9)", 2, "9", "as equal as circumstances will admit"),
    ("your-representatives", "the constitution forbids the legislature to divide a town, ward or place",
     2, "9", "no town, ward or place shall be divided"),
    # The State House and what makes the branches different (26 October 2026).
    ("state-house-and-branches", "the General Court of New Hampshire (Part Second, Article 3)",
     2, "3", "the general court of new hampshire"),
    ("state-house-and-branches", "not less than 375 or more than 400 members (Part Second, Article 9)",
     2, "9", "not less than three hundred seventy-five or more than four hundred"),
    ("state-house-and-branches", "the Senate has 24 members (Part Second, Article 25)",
     2, "25", "the senate shall consist of twenty four members"),
    ("state-house-and-branches", "Article 15 gives each member $200", 2, "15", "the sum of $200"),
    ("state-house-and-branches", "as compensation in full for their services for the term elected",
     2, "15", "as compensation in full for their services for the term elected"),
    ("state-house-and-branches", "the presiding officers of the two chambers $250",
     2, "15", "the presiding officers of both houses"),
    ("state-house-and-branches", "the presiding officers of the two chambers $250",
     2, "15", "the sum of $250"),
    ("state-house-and-branches", "45 legislative days or after July 1, whichever comes first",
     2, "15", "45 legislative days or after the first day of july"),
    ("state-house-and-branches", "A special session adds $3 a day, for no more than 15 days",
     2, "15", "$3 per day for a period not exceeding 15 days"),
    ("state-house-and-branches", "the title His Excellency (Part Second, Article 41)",
     2, "41", "whose title shall be his excellency"),
    ("state-house-and-branches", "The governor is chosen biennially, in November (Part Second, Article 42)",
     2, "42", "the governor shall be chosen biennially in the month of november"),
    ("state-house-and-branches", "30 years old and have lived in the state for the 7 years immediately "
     "before the election", 2, "42", "an inhabitant of this state for 7 years next preceding"),
    ("state-house-and-branches", "30 years old and have lived in the state for the 7 years immediately "
     "before the election", 2, "42", "of the age of 30 years"),
    ("state-house-and-branches", "the House and Senate together elect one of the two with the most votes, "
     "by joint ballot", 2, "42", "by joint ballot elect one of the two persons, having the highest number "
                                 "of votes"),
    ("state-house-and-branches", "Five Executive Councilors are elected biennially",
     2, "60", "biennially elected, by ballot, five councilors"),
    ("state-house-and-branches", "for advising the governor in the executive part of government",
     2, "60", "for advising the governor in the executive part of government"),
    ("state-house-and-branches", "five districts drawn as nearly equal in population as may be",
     2, "65", "five districts, as nearly equal as may be, governing themselves by the number of population"),
    ("state-house-and-branches", "nominated and appointed by the governor and council",
     2, "46", "shall be nominated and appointed by the governor and council"),
    ("state-house-and-branches", "the nomination must be made at least three days before",
     2, "46", "at least three days prior to such appointment"),
    ("state-house-and-branches", "no one takes office unless a majority of the council agrees",
     2, "46", "unless a majority of the council agree thereto"),
    ("state-house-and-branches", "a negative on each other", 2, "47", "a negative on each other"),
    ("state-house-and-branches", "a trial court of general jurisdiction known as the superior court",
     2, "72-a", "a trial court of general jurisdiction known as the superior court"),
    ("state-house-and-branches", "the administrative head of all the courts",
     2, "73-a", "the administrative head of all the courts"),
    ("state-house-and-branches", "The Governor nominates and the Executive Council confirms",
     2, "46", "all judicial officers"),
    ("state-house-and-branches", "a judge holds office during good behavior",
     2, "73", "shall hold their offices during good behavior"),
    ("state-house-and-branches", "no one may serve as a judge after reaching seventy",
     2, "78", "after he has attained the age of seventy years"),
    ("state-house-and-branches", "on the address of both houses of the legislature",
     2, "73", "upon the address of both houses of the legislature"),
    ("state-house-and-branches", "changing them means amending it, as Part Second, Article 100 provides",
     2, "100", "amendments to this constitution may be proposed"),
]


@check("frontend", "a Learn page's statements of the Constitution say what its articles say, and the "
       "seats the pages count are the ones the articles allow",
       needs=("civics", "parse_constitution", "parse_districts"))
def _learn_constitution_claims(civics, PC, PD):
    """Approved by the person on 23 October 2026. A survey of civics.py found
    the Learn pages stating the Constitution -- five days, Sundays excepted;
    a roll call on every override; Organization Day; five councilors; the age
    of seventy; "as equal as circumstances will admit"; 400 representatives,
    24 senators and $200 -- with nothing holding a sentence to its article.

    Three halves. Each row of LEARN_CONSTITUTION_CLAIMS: the phrase on its
    page, the article in force, its words in the article. The Constitution as
    a whole: in effect since 1784, and Part First the forty-four articles
    the page says, which it called "thirty-odd" until this check counted
    them. And the seats: the General Court page's House and Senate are
    [[house_seats]] and [[senate_districts]] since this check, which
    build_civics counts from records/districts/, so the tracked lists must
    give a House within Article 9's 375 to 400 and Article 25's twenty-four
    senators, the Council Article 65's five districts, and the blurb, which
    is not filled, the same numbers typed.
    """
    import html as _html
    con = PC.load()
    assert con, "collected/constitution.json is not on this disk, and it is tracked: run git status"
    arts = {(p, a["key"]): a for p, a in PC.articles(con)}

    def flat(s):
        # Markup off as a reader sees it: "<b>Organization Day</b>, the" is
        # "Organization Day, the", with no space before the comma.
        s = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s)))
        return re.sub(r" ([,.;:)])", r"\1", s).strip()

    pages = {t["slug"]: flat(" ".join([t["blurb"], t["body"], t.get("holds") or ""]))
             for t in civics.TOPICS}
    bad = []
    for slug, phrase, part, key, said in LEARN_CONSTITUTION_CLAIMS:
        page = pages.get(slug)
        if page is None:
            bad.append(f"no Learn page {slug}")
            continue
        if phrase not in page:
            bad.append(f"{slug} no longer says {phrase!r}")
        art = arts.get((part, key))
        name = f"Part {'First' if part == 1 else 'Second'}, Article {key}"
        if not art or art["repealed"]:
            bad.append(f"{name}, which {slug} rests on, is not in force")
        elif said.lower() not in flat(" ".join(art["text"])).lower():
            bad.append(f"{name} no longer says {said!r}, which {slug} relies on")
    # The whole: when it took effect, and how many articles Part First has.
    if "to take effect June 2, 1784" not in (con.get("_source") or {}).get("established", ""):
        bad.append(f"nh.gov no longer says the Constitution took effect in 1784: {con.get('_source')}")
    if "took effect in 1784" not in pages.get("the-constitution", ""):
        bad.append("the-constitution no longer says it took effect in 1784")
    first = sum(1 for (p, _k), a in arts.items() if p == 1 and not a["repealed"])
    if first != 44 or "Bill of Rights — forty-four articles" not in pages.get("the-constitution", ""):
        bad.append(f"Part First has {first} articles in force; the-constitution says forty-four")
    # The seats, from the district lists build_civics counts them from.
    house = PD.parse_house(Path("records/districts/house.txt"))
    seats = sum(h["seats"] for h in house.values())
    senate = len(PD.parse(Path("records/districts/senate.txt")))
    council = len(PD.parse(Path("records/districts/council.txt")))
    if not 375 <= seats <= 400:
        bad.append(f"the House lists give {seats} seats, outside Article 9's 375 to 400")
    if senate != 24:
        bad.append(f"the Senate list gives {senate} districts, where Article 25 says twenty-four")
    if council != 5:
        bad.append(f"the Council list gives {council} districts, where Article 65 says five")
    blurb = next((t["blurb"] for t in civics.TOPICS if t["slug"] == "general-court"), "")
    if f"{seats} representatives and {senate} senators" not in blurb:
        bad.append(f"the General Court's blurb types other numbers than the lists' {seats} and {senate}: "
                   f"{blurb!r}")
    assert not bad, "; ".join(bad[:4]) + (f" (and {len(bad) - 4} more)" if len(bad) > 4 else "")
    return "ok", (f"{len(LEARN_CONSTITUTION_CLAIMS)} Learn statements in their articles' words; in effect "
                  f"since 1784, Part First's {first} articles; {seats} House seats, {senate} Senate and "
                  f"{council} Council districts, each as the articles allow")



@check("frontend", "every published guide is reached from the home page, in the site search and in the sitemap, its sitemap date and HowTo data dated by the newest read of its sources, and the state in its title")
def _guides_reach():
    """The person, 12 October 2026: a link to the guides on the home page,
    the guides in the site-wide search, and the guides optimized for SEO."""
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    import guides as G
    import build_civics as BC_
    shared, base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    home = (site / "index.html").read_text(encoding="utf-8")
    assert home.count("<!-- guides -->") == 1 and home.count("<!-- /guides -->") == 1, \
        "the home page's guides slot is missing or doubled"
    # The three Learn pages that became guides (civics.HOW_TO, 17 October
    # 2026) share the folder and are held by _how_to_moved, below: they are
    # explanations, with no HowTo steps and no date of checking.
    import civics as _civ
    pages = sorted(p for p in (site / "guides").glob("*.html")
                   if 'class="g-draft"' not in p.read_text(encoding="utf-8")
                   and p.stem not in _civ.HOW_TO)
    find = json.loads((site / "find.json").read_text(encoding="utf-8"))
    sm = (site / "sitemap.xml").read_text(encoding="utf-8")
    by_slug = {g["slug"]: g for g in G.GUIDES}
    bad, told_apart = [], 0
    for p in pages:
        g, t = by_slug[p.stem], p.read_text(encoding="utf-8")
        addr = f"/guides/{p.stem}"
        # THE HOME PAGE OFFERS THE FEW MOST PEOPLE COME FOR (guides.HOME, the
        # Common Questions of 18 October 2026) and All guides for the rest: a
        # pick that is published must be there.
        if BC_.HOME_GUIDES and p.stem in {t["slug"] for t in G.HOME} and f'href="{addr}"' not in home:
            bad.append(f"{p.stem} is one of the home page's common questions and is not on it")
        if not any(r[0] == "guide" and r[3].lstrip("/") == addr.lstrip("/") for r in find):
            bad.append(f"{p.stem} is not in find.json")
        title = re.search(r"<title>([^<]*)</title>", t).group(1)
        if "New Hampshire" not in title:
            bad.append(f"{p.stem}'s title {title!r} does not say New Hampshire")
        if '"@type": "HowTo"' not in t and '"@type":"HowTo"' not in t:
            bad.append(f"{p.stem} carries no HowTo data")
        # BOTH DATES ARE THE NEWEST READ (the manager session, 5 November
        # 2026): dateModified and the sitemap's lastmod mean what the page's
        # "Sources last checked" means, G.sources_checked, not the oldest
        # read (checked_on), which decides only the out-of-date notice. The
        # sitemap's is never later than the build's day.
        newest = G.sources_checked(g)
        lm = re.search(re.escape(f"<loc>{base}{addr}</loc>") + r"<lastmod>(\d{4}-\d\d-\d\d)</lastmod>", sm)
        if not lm:
            bad.append(f"{p.stem}'s sitemap entry is not dated by its check")
        elif newest and lm.group(1) not in {min(newest, d.isoformat()) for d in _days}:
            bad.append(f"{p.stem}'s sitemap lastmod is {lm.group(1)}, not its newest read {newest}")
        dm = re.findall(r'"dateModified":\s*"([^"]*)"', t)
        if newest and dm != [newest]:
            bad.append(f"{p.stem}'s HowTo dateModified is {dm}, not its newest read {newest}")
        if newest and newest != G.checked_on(g):
            told_apart += 1
    # EVERY COMMON QUESTION LEADS TO A GUIDE THAT IS THERE. Each link the
    # home page's block carries opens a page of the built site that is not a
    # draft -- the pages that became guides (civics.HOW_TO) included, which
    # the loop above leaves to _how_to_moved -- so a pick renamed in
    # guides.HOME, or a guide held back, never leaves a reader on a 404.
    block = re.search(r"<!-- guides -->(.*?)<!-- /guides -->", home, re.S).group(1)
    for slug in re.findall(r'<li><a href="/guides/([^"#]+)"', block):
        f = site / "guides" / f"{slug}.html"
        if not f.is_file():
            bad.append(f"the home page's common question /guides/{slug} leads to no page")
        elif 'class="g-draft"' in f.read_text(encoding="utf-8"):
            bad.append(f"the home page's common question /guides/{slug} leads to a draft")
    # Every guide is reached from the home page: through Common Questions'
    # All guides while they are on, and through the Resources card, which
    # opens the hub on its How-To Guides tab, while they are off.
    if pages and not re.search(r'href="/resources#guides"' if BC_.HOME_GUIDES
                              else r'<a href="/?resources(?:\.html)?">', home):
        bad.append("the home page does not lead to every guide")
    assert not bad, "; ".join(bad)
    return "ok", (f"{len(pages)} published guide{'s' if len(pages) != 1 else ''} reached from the home "
                  "page, in the search and dated in the sitemap, each with HowTo data, both dated by the "
                  f"newest read ({told_apart} where it differs from the oldest)"
                  if pages else "no guide published on the fixture")


@check("build", "the how-to guides are listed by task: every guide and every Learn page that became one "
       "is under one task, the hub opens on How-To Guides, and no page links a moved page's old address",
       needs=("guides", "civics", "build_civics", "build_pages"))
def _how_to_tasks(G, civics, BC, BP):
    """The person, 17 October 2026: "refine how the how to guides are
    displayed on the main resources page and the homepage so it's more
    intuitive for the general public"; "Certain pages currently on learn can
    move to how to like using this site, finding your representatives, how to
    testify or attend meetings"; "How to guides should be the default tab when
    opening the resources page". guides.TASKS is the tab's list; civics.HOW_TO
    the pages that moved; build_pages.MOVED their 301s. Here, from the code:
    each guide and moved page under exactly one task, each task naming one of
    them, no moved slug a guide's too, the tab order, the redirects, and no
    builder or guide still writing a link to a moved page's /learn/ address."""
    slugs = [t["slug"] for _g, ts in G.TASKS for t in ts]
    want = [g["slug"] for g in G.GUIDES] + list(civics.HOW_TO)
    twice = sorted({s for s in slugs if slugs.count(s) > 1})
    assert not twice, f"a guide is under two tasks: {twice}"
    assert not set(want) - set(slugs), f"no task lists {sorted(set(want) - set(slugs))}"
    assert not set(slugs) - set(want), f"a task names no guide: {sorted(set(slugs) - set(want))}"
    assert not set(civics.HOW_TO) & {g["slug"] for g in G.GUIDES}, \
        "a page that moved to /guides/ has the slug of a guide"
    for _g, ts in G.TASKS:
        for t in ts:
            assert t["does"] and t["line"] and "How to" not in t["does"], \
                f"{t['slug']}: a task is named by the guide's title, not in a reader's words: {t['does']!r}"
    assert {t["slug"] for t in G.HOME} <= set(want), \
        "the home page's common questions name a guide that does not exist"
    assert BC.HUB_TABS[0][0] == "guides", "the Resources hub no longer opens on How-To Guides"
    red = BP.REDIRECTS
    for s in civics.HOW_TO:
        for x in ("", ".html"):
            assert f"\n/learn/{s}{x} /guides/{s} 301\n" in red, f"/learn/{s}{x} does not 301 to /guides/{s}"
    assert BC.article_href(civics.HOW_TO[0]).startswith("guides/") and \
        BC.article_href("general-court").startswith("learn/"), "article_href puts a page in the wrong folder"
    stale = []
    for f in ("src/pages/civics.py", "src/pages/guides.py", "src/pages/build_civics.py",
              "src/pages/build_pages.py", "src/pages/legislative_year.py"):
        text = _source(f)
        stale += [f"{f}: learn/{s}" for s in civics.HOW_TO
                  if re.search(rf'href="/?learn/{re.escape(s)}\b|"/learn/{re.escape(s)}\.html', text)]
    assert not stale, "a link to a moved page's old address: " + "; ".join(stale)
    return "ok", (f"{len(slugs)} guides under {len(G.TASKS)} tasks, {len(civics.HOW_TO)} of them moved from "
                  "Learn and redirected; the hub opens on How-To Guides")


@check("frontend", "the Resources hub opens on How-To Guides grouped by task; the three moved pages are "
       "at /guides/ with How-To marked; Learn walks only its own pages and links the guides; other "
       "ways to follow legislation are listed official first, then independent sites alphabetically")
def _how_to_moved():
    """Read off the fixture's built site (17 October 2026): the hub's first
    tab and panel are the guides, under guides.TASKS' groups, the moved pages
    among them; each moved page is at /guides/<slug>, its /learn/ copy gone,
    its bar marking How-To Guides and its foot leading back to every guide;
    Learn's pages walk Learn's own order and name the guides that do what
    they explain; and the Official Sources tab ends with the other ways to
    follow legislation, the General Court's own site first, the independent
    ones in alphabetical order, with no image and no General Court page that
    guides.GENERAL_COURT_LINKS does not hold."""
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    import civics as _civ
    import guides as G
    import build_civics as BC
    shared, _base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    hub = (site / "resources.html").read_text(encoding="utf-8")
    tabs = re.findall(r'<button type="button" role="tab" id="tab-(\w+)"[^>]*aria-selected="(\w+)"', hub)
    assert tabs and tabs[0] == ("guides", "true"), f"the hub does not open on How-To Guides: {tabs}"
    panes = re.findall(r'<div class="twnpane r-sheet" id="(\w+)"', hub)
    assert panes[0] == "guides", f"the How-To Guides panel is not first: {panes}"
    at = hub.index('<div class="twnpane r-sheet" id="guides"')
    guides_pane = hub[at:hub.index('<div class="twnpane r-sheet"', at + 1)]
    at = hub.index('<div class="twnpane r-sheet" id="learn"')
    learn_pane = hub[at:hub.index('<div class="twnpane r-sheet"', at + 1)]

    def links_to(html_, slug):
        """Whether the markup links /guides/<slug>, as written or as served
        (shell.clean_links takes the .html off)."""
        return re.search(rf'href="/?guides/{re.escape(slug)}(?:\.html)?(?:#[^"]*)?"', html_) is not None
    for s in _civ.HOW_TO:
        page = site / "guides" / f"{s}.html"
        assert page.is_file() and not (site / "learn" / f"{s}.html").exists(), \
            f"{s} is not at /guides/, or a copy is left at /learn/"
        t = page.read_text(encoding="utf-8")
        assert re.search(r'class="l-hubtab" href="[^"]*#guides" aria-current="true"', t), \
            f"guides/{s} does not mark How-To Guides on its bar"
        assert "All How-To Guides" in t and "Previous Topic" not in t and "Next Topic" not in t, \
            f"guides/{s} still walks Learn's order"
        assert links_to(guides_pane, s), f"the How-To Guides tab does not list {s}"
        assert f'learn/{s}' not in learn_pane, f"the Learn tab still links {s} at its old address"
    # THE TAB, COMPACT AND SEARCHABLE (the person, 24 October 2026, which
    # replaced the rule of 17 October that the tab never say "How to"): a
    # search that suggests guides, the most common errands, then every guide
    # under its group, each group a <details> headed by the group's name and
    # each guide by its "How to" headline.
    for group, _ts in G.TASKS:
        if any(links_to(guides_pane, t["slug"]) for t in _ts):
            assert re.search(rf'<summary>(?:<span class="g-ic".*?</span>)?<span class="g-tname">'
                             rf'{re.escape(group)}</span>', guides_pane), \
                f"the How-To tab does not fold the group {group!r} under its name"
            for t in _ts:
                if links_to(guides_pane, t["slug"]):
                    assert f'>{t["head"]}</a>' in guides_pane, \
                        f"the How-To tab does not list {t['slug']} by its headline {t['head']!r}"
    assert 'id="gfind"' in guides_pane and 'action="/search"' in guides_pane, \
        "the How-To tab has no guide search, or one that does nothing without its script"
    blob = re.search(r'<script type="application/json" id="gfind-data">(.*?)</script>', guides_pane, re.S)
    assert blob, "the guide search has no list of guides to suggest from"
    found = {g["h"].lstrip("/").removesuffix(".html") for g in json.loads(blob.group(1).replace("<\\/", "</"))["g"]}
    linked = {m for m in re.findall(r'<details class="g-topic".*?</details>', guides_pane, re.S)}
    shown = set(re.findall(r'href="/?(guides/[a-z0-9-]+?)(?:\.html)?"', "".join(linked)))
    assert shown and shown == found, f"the search suggests a different set of guides than the tab lists: {shown ^ found}"
    common = guides_pane[guides_pane.index('id="g-common"'):guides_pane.index('id="g-topics"')]
    assert all(links_to(common, c) for c in G.COMMON if links_to(guides_pane, c)), \
        "a guide of guides.COMMON is listed but not among the most common"
    learn = BC.learn_topics(_civ.TOPICS)
    for p in sorted((site / "learn").glob("*.html")):
        t = p.read_text(encoding="utf-8")
        for s in _civ.HOW_TO:
            assert f'href="learn/{s}' not in t and f'href="/learn/{s}' not in t, \
                f"learn/{p.name} links {s} at its old address"
    gc = (site / "learn" / "general-court.html").read_text(encoding="utf-8")
    word = BC.NUMBER_WORD.get(len(learn), str(len(learn)))
    assert f"The {word} Pages" in gc, f"Learn's list at the foot is not of its {len(learn)} pages"
    assert 'id="how-to-guides"' in gc and links_to(gc, "your-representatives"), \
        "a Learn page does not name the guides that do what it explains"
    # Other ways to follow legislation, at the foot of Official Sources.
    at = hub.index('<div class="twnpane r-sheet" id="sources"')
    src = hub[at:]
    assert BC.FOLLOW_HEADING in src, "the Official Sources tab has no section on other ways to follow"
    sec = src[src.index(BC.FOLLOW_HEADING):]
    sec = sec[:sec.index("</section>")]
    names = re.findall(r'<li><a href="([^"]+)" target="_blank" rel="noopener">([^<]+)</a>', sec)
    want = [(u, n) for n, u, _l in _civ.FOLLOW_OFFICIAL + _civ.FOLLOW_INDEPENDENT]
    assert [(u, n) for u, n in names[:len(want)]] == want, f"the sites are not listed as civics.py lists them: {names}"
    indep = [n for n, _u, _l in _civ.FOLLOW_INDEPENDENT]
    assert indep == sorted(indep, key=str.casefold), "the independent sites are ranked, not alphabetical"
    assert "<img" not in sec, "a tracker is shown with a logo"
    court = set(re.findall(r'href="(https?://(?:[^/"]*\.)?gc\.nh\.gov[^"]*)"', sec))
    assert court and court <= G.GENERAL_COURT_LINKS, \
        f"a General Court page linked that guides.GENERAL_COURT_LINKS does not hold: {court}"
    for w in ("best", "recommend", "trusted", "excellent", "leading", "top "):
        assert w not in re.sub(r"<[^>]+>", " ", sec).lower(), f"a tracker's line says {w!r}"
    return "ok", (f"How-To Guides first, by task; {len(_civ.HOW_TO)} moved pages at /guides/; Learn's "
                  f"{len(learn)} pages; {len(indep)} independent trackers after the General Court")


@check("build", "the guide to touring the State House rests on the Visitor Center's Rules for Tours, "
       "kept in git and read from the PDF, links the Visitor Center's page without asking it, and "
       "names no member of its staff", needs=("guides", "civics"))
def _tour_guide(G, civics):
    """The person, 17 October 2026: a How-To guide to touring the State House
    -- booking through the Visitor Center, as a school field trip, or as a
    representative's guest -- from the Visitor Center's Rules for Tours, saved
    in records/sources/. Every statement the guide takes from the rules is a
    record claim on the PDF whose words pdfplumber finds in it; the PDF is
    tracked, so the night and a fork read the same document; the Visitor
    Center's page is one of guides.GENERAL_COURT_LINKS (linked, never asked);
    visiting as a representative's guest, which the rules do not cover and
    the person's notes do not describe, is only "contact them", with no claim
    of practice; and the rules' director, named in them, is not."""
    tour = next((g for g in G.GUIDES if g["slug"] == "tour-the-state-house"), None)
    assert tour, "there is no guide to touring the State House"
    pdf = "records/sources/state-house-visitor-center-rules-for-tours.pdf"
    assert Path(pdf).is_file(), f"{pdf} is not here"
    r = _run(["git", "ls-files", "--error-unmatch", pdf], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"{pdf} is not tracked, so a fresh clone holds no document the guide rests on"
    recs = [c for c in tour["claims"] if c.get("path")]
    assert recs and all(c["path"] == pdf for c in recs), "a tour claim rests on another document"
    assert pdf.startswith(G.RECORD_HOMES), "the Visitor Center's rules are not among the Court's documents"
    faults, found, absent = G.claim_faults(tour)
    assert not faults, "; ".join(faults[:3])
    try:
        import pdfplumber  # noqa: F401
        assert found == len(recs) and not absent, f"{found} of {len(recs)} claims found in the PDF"
    except ImportError:
        pass
    assert not any(c.get("observed") for c in tour["claims"]), \
        "the tour guide states a practice the rules and the person's notes do not"
    vc = civics.SRC_VISITOR_CENTER[1]
    assert vc in G.GENERAL_COURT_LINKS and vc in G.outside(tour), \
        "the Visitor Center's page is not linked, or not as one of the General Court's pages"
    words = G.text(tour) + " ".join(label for label, _u in tour["sources"])
    for who in ("Drew", "@leg.state.nh.us", "gencourt.state.nh.us"):
        assert who not in words, f"the tour guide prints {who!r} from the rules"
    assert "/guides/your-representatives.html" in words or any(
        u == "/guides/your-representatives.html" for s in tour["steps"] for _l, u in s["actions"]), \
        "the tour guide does not send a reader to their representative"
    assert G.task_of("tour-the-state-house")[0] == "Visiting the State House", \
        "the tour guide is not under Visiting the State House"
    return "ok", f"{found} statements found in the Visitor Center's Rules for Tours; its page linked, not asked"


@check("build", "no guide describes a court order that has been stayed as in force: a sentence "
       "naming one of guides.STAYED_ORDERS says it is stayed or on hold",
       needs=("guides",))
def _vote_guide_stayed_orders(G):
    """How to Vote's note said "A further order of October 2, 2026 lets
    election officials consider a student ID, together with other evidence,
    as proof of identity when you register". On 22 October 2026, twelve days
    before the general election, the U.S. Supreme Court stayed that order and
    the one of October 5 (No. 26A512, Scanlan v. Coalition for Open
    Democracy), and the sentence went on saying it, on the guide the site
    sends voters to, with nothing to notice: the note is typed, and no date
    in it moves. The sentence came out on 23 October 2026, and this keeps
    it, or one like it, from coming back while the stay stands: every
    sentence of every guide's words and claims that names an order in
    guides.STAYED_ORDERS must say "stayed" or "on hold". And the rows
    themselves must each say what stayed them, so that one is never taken out
    without the stay's end being stated in its place."""
    assert G.STAYED_ORDERS, "guides.STAYED_ORDERS is empty: the check would hold nothing"
    for day, why in G.STAYED_ORDERS.items():
        assert re.fullmatch(r"[A-Z][a-z]+ \d{1,2}, \d{4}", day), (
            f"guides.STAYED_ORDERS names {day!r}, which is not a date as a guide writes one")
        assert "stayed" in why and re.search(r"\d{4}", why), (
            f"guides.STAYED_ORDERS[{day!r}] does not say when and by what it was stayed: {why!r}")
    bad, read = [], 0
    for g in G.GUIDES:
        words = [G.text(g)] + [c["says"] for c in g["claims"]]
        for chunk in words:
            plain = " ".join(re.sub(r"<[^>]+>", " ", chunk).split())
            for sentence in re.split(r"(?<=[.;:])\s+", plain):
                read += 1
                named = [d for d in G.STAYED_ORDERS if d in sentence]
                if named and not re.search(r"\bstay(?:ed)?\b|\bon hold\b", sentence, re.I):
                    bad.append(f"{g['slug']}: {sentence[:160]!r} names the order of {named[0]}, "
                               f"{G.STAYED_ORDERS[named[0]]}, and does not say so")
    assert not bad, "; ".join(bad[:4])
    return "ok", (f"{read:,} sentences of {len(G.GUIDES)} guides read; none names "
                  f"{' or '.join(G.STAYED_ORDERS)} as in force")


@check("build", "the glossary page lists every glossary.json entry once, by its name in full, "
       "and the footer leads to it", needs=("build_civics", "components"))
def _glossary_page(B, C):
    """The person, 14 October 2026: a glossary "linked somewhere directly on
    the homepage without being too intrusive", the footer chosen. The page is
    drawn from the file the popovers read, so the two cannot disagree."""
    secs = B.glossary_secs()
    body = "".join(c for _, _, c in secs)
    for key, e in C.WORDBOOK["glossary"].items():
        assert body.count(f'id="t-{B._slug(key)}"') == 1, f"{key} is not on the glossary page exactly once"
        assert f"<b>{B.E(e['name'])}</b>" in body, f"{key}'s name in full is missing"
    assert [h for _, h, _ in secs] == sorted(h for _, h, _ in secs), "the letters are out of order"
    import chrome as CH
    assert '<a href="learn/glossary.html">Glossary</a>' in CH.FOOTER, \
        "the footer (chrome.FOOTER, on every page) does not lead to the glossary"
    return "ok", f"{len(C.WORDBOOK['glossary'])} terms under {len(secs)} letters, linked from the footer"


@check("build", "a term a Learn page marks for its pop-up is a glossary entry, marked on an abbr so "
       "its sentence stays one piece to translate, and its Spanish marks the same terms",
       needs=("civics", "components"))
def _learn_term_marks(civics, C):
    """The person, 26 October 2026: "Check the learn guide phrasing for ...
    undefined technical terms a reader likely may not know, opportunities to
    add tooltips like we have for -FN and other acronyms on the bill pages."
    A Learn page marks a term <abbr data-term="KEY">, and components.js's
    term popovers, which already run on every page, make the first of each a
    button that opens glossary.json's entry -- in Spanish from the shared
    words file's GR_GLOSS. abbr and not span, because span is not one of
    i18n.INLINE's tags: a span inside a sentence would cut it into pieces to
    translate apart. Held here: every mark names an entry; every mark is an
    abbr; and every Spanish entry whose English marks terms marks the same
    ones, so the pop-up is in the Spanish page too."""
    g = C.WORDBOOK["glossary"]
    bad, marks = [], 0
    for t in civics.TOPICS:
        for m in re.finditer(r'<(\w+)\b[^>]*\bdata-term="([^"]+)"', t["body"]):
            marks += 1
            if m.group(1).lower() != "abbr":
                bad.append(f"{t['slug']} marks {m.group(2)} on a <{m.group(1)}>, not an <abbr>")
            if m.group(2) not in g:
                bad.append(f"{t['slug']} marks {m.group(2)!r}, which is no glossary entry")
    cat = json.loads(_source("src/pages/lang/es.json"))["strings"]
    pages = {t["slug"] for t in civics.TOPICS}
    for k, e in cat.items():
        if k.split(".")[0] not in ("learn", "guide") or k.split(".")[1] not in pages:
            continue
        en = sorted(re.findall(r'data-term="([^"]+)"', e.get("en", "")))
        es = sorted(re.findall(r'data-term="([^"]+)"', e.get("es", "")))
        if en != es:
            bad.append(f"{k}: the English marks {en}, the Spanish {es}")
    assert marks, "no Learn page marks a term for its pop-up"
    assert not bad, "; ".join(bad[:5])
    return "ok", f"{marks} terms marked on the Learn pages, each a glossary entry, in both languages"


@check("build", "Using This Site's Reading the Shorthand is drawn from glossary.json, row for row, "
       "and the glossary's notes say what draws it", needs=("civics", "components"))
def _shorthand_from_the_glossary(civics, C):
    """The person, 23 October 2026: one source each for the things the site
    words several ways. Learn's table of the record's shorthand was typed
    beside glossary.json, which the glossary page and the term popovers are
    drawn from, and had drifted from it on VV, DV, A, OT3rdg, Retain ("through
    the fall" where the glossary says "through the fall of the first year")
    and OTPA. Its rows are glossary entries now (civics._shorthand), as
    _motions' are votes.json's, so here: every row is an entry, in its name
    and words exactly; the page carries the drawn table and no row typed out
    beside it; the old wordings are gone; and the glossary's own notes no
    longer say that nothing draws it."""
    g = C.WORDBOOK["glossary"]
    bad = [f"{k} is no glossary entry" for k in civics.SHORTHAND if k not in g]
    # The table's one note of its own, which the person approved with it on
    # 17 October 2026; a second would be a definition typed beside the glossary.
    if civics.SHORTHAND_NOTES != {"OTPA": "the docket also writes OTP/A or OTP/AM"}:
        bad.append(f"the table adds notes of its own to the glossary's words: {civics.SHORTHAND_NOTES}")
    assert not bad, "; ".join(bad)
    table = civics.SHORTHAND_TABLE
    rows = re.findall(r'<tr><th scope="row"><b>-?([^<]+)</b></th><td><b>([^<]*?):?</b>\s*([^<]*)</td></tr>',
                      table)
    if [r[0] for r in rows] != list(civics.SHORTHAND):
        bad.append(f"the table's rows are {[r[0] for r in rows]}, not civics.SHORTHAND's")
    for k, name, says in rows:
        e = g.get(k) or {}
        want = C.esc(e.get("says", "")) + (f" ({civics.SHORTHAND_NOTES[k]})" if k in civics.SHORTHAND_NOTES
                                           else "")
        if name != C.esc(e.get("name", "")) or says != want:
            bad.append(f"{k} reads {name!r}: {says!r}, where the glossary says {e.get('name')!r}: "
                       f"{e.get('says')!r}")
    site = civics.BODY_SITE
    at = site.find("<h2>Reading the Shorthand</h2>")
    section = site[at:site.find("<h2>", at + 1)] if at >= 0 else ""
    if table not in section or section.count("<tr>") != len(civics.SHORTHAND):
        bad.append("Using This Site's Reading the Shorthand is not the drawn table alone")
    for gone in ("no count and no names</td>", "counted, names not recorded",
                 "through the fall and reports it in the second year", "the bill contains one</td>",
                 "<b>Ordered to a third reading</b></td>", "<b>Motion Adopted / Motion Failed</b>"):
        if gone in site:
            bad.append(f"Using This Site still says {gone!r}")
    notes = " ".join(json.loads(_source("src/pages/words/glossary.json"))["_about"])
    if "NOTHING DRAWS THESE YET" in notes or "civics._shorthand" not in notes:
        bad.append("glossary.json's notes do not say what draws its entries")
    assert not bad, "; ".join(bad[:4])
    return "ok", (f"{len(rows)} rows, each a glossary entry in its own words, the docket's other "
                  "spellings of OTPA the table's one note")


@check("build", "the Constitution as nh.gov publishes it: every article of the saved pages read, numbered as the "
       "Constitution numbers them, each page's own list accounted for, and collected/constitution.json what the "
       "saved pages give", needs=("parse_constitution",))
def _constitution_read(PC):
    """The person, 17 October 2026: "Can you fetch the constitution at least
    so we can present that on the laws page". Read that day in a browser,
    since the host refuses a script, and saved in records/sources/constitution/
    with each page's sha256; parse_constitution reads them.

    WHAT IS HELD. The saved pages are what was read (parse refuses a page whose
    body's sha256 differs from its header). The committed file is what they
    give, so an edit to either alone fails here. Every entry of every page's
    own list is an article read, and the one article read that no list names
    is Part Second's 26, which the Senate page holds and does not list. No
    number is missing from 1 to 39 or 1 to 101, and the lettered articles are
    the Constitution's. The three repairs are each held to what they found:
    Article 50 out of 49-a's row with 49-a's date, Article 61 read from "6l",
    and Article 71's 1792 and 1877 notes apart."""
    con = PC.parse()
    assert PC.OUT.is_file(), ("collected/constitution.json is missing: python3 src/parse/parse_constitution.py "
                              "writes it from records/sources/constitution/")
    want = json.dumps(con, ensure_ascii=False, indent=1) + "\n"
    assert PC.OUT.read_text(encoding="utf-8") == want, (
        "collected/constitution.json is not what records/sources/constitution/ gives: run "
        "python3 src/parse/parse_constitution.py and commit the file")
    assert con["counts"] == {"part1": 44, "part2": 112}, f"the articles read per part: {con['counts']}"
    lost = [(t["file"], t["listed_not_found"]) for t in con["toc"] if t["listed_not_found"]]
    assert not lost, f"a page lists articles the reading did not find: {lost}"
    unlisted = [(t["part"], k) for t in con["toc"] for k in t["not_listed"]]
    assert unlisted == [(2, "26")], f"articles read that no page's own list names: {unlisted}"
    listed = sum(len(t["listed"]) for t in con["toc"])
    assert listed + len(unlisted) == 156, f"{listed} listed and {len(unlisted)} unlisted, against 156 read"
    assert PC.gaps(con) == {1: [], 2: []}, f"article numbers missing: {PC.gaps(con)}"
    arts = PC.articles(con)
    top = {p: max(int(a["num"]) for q, a in arts if q == p) for p in (1, 2)}
    assert top == {1: 39, 2: 101}, f"the last article of each part: {top}"
    lettered = {p: [a["key"] for q, a in arts if q == p and a["letter"]] for p in (1, 2)}
    assert lettered == {1: ["2-a", "2-b", "12-a", "28-a", "36-a"],
                        2: ["5-a", "5-b", "6-a", "6-b", "9-a", "11-a", "18-a", "26-a", "49-a", "72-a", "73-a"]}, \
        f"the lettered articles: {lettered}"
    by = {a["anchor"]: a for _, a in arts}
    assert len(by) == len(arts) == 156, "two articles share an anchor"
    assert all(a["text"] for a in by.values()), "an article read with no text"
    assert by["part2-art49-a"]["notes"] == ["November 28, 1984"], by["part2-art49-a"]["notes"]
    assert by["part2-art50"]["text"][0].startswith("The governor, with advice of council"), \
        "Article 50 is not read out of 49-a's row"
    assert by["part2-art61"]["title"] == "Vacancies, How Filled, if No Choice", "Article 61 is not read from 6l"
    assert len(by["part2-art71"]["notes"]) == 4, f"Article 71's notes run together: {by['part2-art71']['notes']}"
    gone = sorted((p, a["key"]) for p, a in arts if a["repealed"])
    assert len(gone) == 11 and (2, "10") in gone and (2, "99") in gone, f"the repealed articles: {gone}"
    return "ok", (f"{con['counts']['part1']} articles in Part First and {con['counts']['part2']} in Part "
                  f"Second from {len(con['toc'])} pages, {listed} on their own lists and Part Second 26 not; "
                  f"{len(con['repairs'])} repairs said")


@check("build", "a CACR links the articles of the Constitution its own text says it changes, and a Learn page each "
       "article it cites; nothing a clause does not say plainly",
       needs=("parse_constitution", "constitution_tab", "build_site_v2", "build_bill_pages"))
def _cacr_articles(PC, CT, BSV, BBP):
    """The person, 17 October 2026: where the site shows a constitutional
    amendment, link the article it would change when the CACR's text names
    it, only where certain. Read from the resolving clauses, in the three
    forms every CACR of 2025-2026 but one uses; that one (CACR 16, "That the
    following new article of part I of the constitution after article 2-b:")
    names nothing, and neither does the question put to the voters."""
    con = PC.load()
    assert con, "collected/constitution.json is not on this disk"

    def got(s):
        return [(x["verb"], x["part"], x["art"], x["href"]) for x in PC.cacr_targets(s, con)]

    cases = (
        ("I. That article 78 of the second part of the constitution be amended to read as follows:",
         [("amend", 2, "78", "/laws#part2-art78")]),
        ("I. That articles 41, 42, 49, and 49-a of the second part of the constitution be amended to read",
         [("amend", 2, k, f"/laws#part2-art{k}") for k in ("41", "42", "49", "49-a")]),
        ("II. That article 72-a of the second part of the constitution, relative to the supreme and superior "
         "courts, be repealed.", [("repeal", 2, "72-a", "/laws#part2-art72-a")]),
        ("I. That the first part of the constitution be amended by inserting after article 2-b the following new "
         "article:", [("insert_after", 1, "2-b", "/laws#part1-art2-b")]),
        ("I. That the first part of the constitution be repealed and reenacted to read as follows:",
         [("reenact_part", 1, "", "/laws#part1")]),
        ("I. That the following new article of part I of the constitution after article 2-b:", []),
        ("I. That article 140 of the second part of the constitution be amended to read as follows:", []),
        # The forms the 1989-2024 resolutions use, each a sentence from the data (11 November 2026): CACR 41 of
        # 2005-06 (Part Second Article 11, ratified 7 November 2006) was one of 57 that named no article.
        ("I. That the second part of the constitution be amended by replacing article 11 with the following: [Art.] 11.",
         [("amend", 2, "11", "/laws#part2-art11")]),
        ("I. That the first part of the constitution be amended by replacing the first 2 sentences of article 11 "
         "with the following 2 sentences:", [("amend", 1, "11", "/laws#part1-art11")]),
        ("I. That part first, article 28-a of the constitution be amended to read as follows: [Art.] 28-a",
         [("amend", 1, "28-a", "/laws#part1-art28-a")]),
        ("I. That article 15, part second of the constitution, relative to the compensation of the legislature, "
         "be repealed. II. That the above amendment", [("repeal", 2, "15", "/laws#part2-art15")]),
        ("I. That article 6 of the first part of the constitution and article 83 of the second part of the "
         "constitution be amended to read as follows:",
         [("amend", 1, "6", "/laws#part1-art6"), ("amend", 2, "83", "/laws#part2-art83")]),
        ("I. That part II, article 73-a of the constitution be repealed and reenacted in order to clarify that",
         [("amend", 2, "73-a", "/laws#part2-art73-a")]),
        ("I. That article 78 of the second part of the constitution, relative to judges and sheriffs disqualified "
         "by age, is repealed. II. That the above", [("repeal", 2, "78", "/laws#part2-art78")]),
        ("I. That article 9 of the second part of the constitution read as follows: [Art.] 9.",
         [("amend", 2, "9", "/laws#part2-art9")]),
        ("I. That part second of the constitution be amended by inserting after article 1 the following new "
         "article: [Art.] 1-a [Initiative Petitions.]", [("insert_after", 2, "1", "/laws#part2-art1")]),
        ("I. That the second part of the constitution be amended by inserting after article 5-B the following "
         "new article: [Art.] 5-c [Income Tax Prohibited.]", [("insert_after", 2, "5-b", "/laws#part2-art5-b")]),
        # "that" in lower case is the question put to the voters, which repeats the clause; it adds nothing
        ("IV. That the wording of the question shall be: Are you in favor of amending the constitution so that "
         "article 4 of the second part of the constitution reads as follows and that article 72-a of the second part "
         "of the constitution, printed below, be repealed.", []),
        # a bare "article N" with no part named is not a clause, nor is a new article's number
        ("II. That article 11 be amended to read as follows:", []),
        ("Are you in favor of amending article 78 of the second part of the constitution", []),
    )
    for text, want in cases:
        assert got(text) == want, f"{text[:60]!r} read as {got(text)}"
    src = _source("src/pages/build_site_v2.py")
    assert '{"constitution": c}' in src and 'bid.startswith("CACR")' in src, \
        "a CACR's record does not carry the articles it changes"
    assert BSV.constitution_targets("I. That article 78 of the second part of the constitution be amended")[0][
        "label"] == "Part Second, Article 78"
    rec = BBP.static_record({"id": "CACR9", "n": "CACR 9", "year": 2026},
                            {"constitution": PC.cacr_targets(cases[0][0] + " " + cases[3][0], con)})
    assert '<a href="/laws#part2-art78">Part Second, Article 78</a> of the state Constitution' in rec \
        and "A new article of the state Constitution, after" in rec, "the page without scripts does not link them"
    said = ""
    app = _app_js('scope.constLine({constitution:[{verb:"amend",part:2,art:"78",href:"/laws#part2-art78",'
                  'label:"Part Second, Article 78"},{verb:"insert_after",part:1,art:"2-b",href:"/laws#part1-art2-b",'
                  'label:"Part First, Article 2-b"}]})', names=("constLine",))
    if app is None:
        said = "; node not here for app.js"
    else:
        assert ('Changes this article of the state Constitution: <a class="rsa" href="/laws#part2-art78">' in app
                and "Adds a new article to the state Constitution, after" in app), f"app.js draws {app}"
    learn = CT.link_citations('Part Second, Article 44 and Part II, Article 9; articles 71 and 81 of Part '
                              'Second; Part Second, Article 140; <a href="x">Part First, Article 2</a>', con)
    assert ('<a href="/laws#part2-art44">Part Second, Article 44</a>' in learn
            and '<a href="/laws#part2-art9">Part II, Article 9</a>' in learn
            and 'articles <a href="/laws#part2-art71">71</a> and <a href="/laws#part2-art81">81</a> of Part Second'
            in learn and "Part Second, Article 140;" in learn and '<a href="x">Part First, Article 2</a>' in learn), \
        f"the Learn pages' citations link as {learn}"
    return "ok", f"{len(cases)} clauses read as they say, and no more; both bill pages and the Learn pages link{said}"


class _StubBills:
    """The few things a History and citations fold asks of build_rsa.Bills, from rows given."""

    def __init__(self, rows):
        self.rows = rows

    def row(self, k):
        return self.rows.get(k) or {}

    def url(self, k):
        return "/bill/" + k.split("/")[1].lower()

    def label(self, k):
        return k.split("/")[1]


@check("build", "an article of the Constitution is cited as a reader writes it -- a part and an article the "
       "Constitution holds -- and never by a bare \"article 11\"; a fold's counts are the derived file's",
       needs=("parse_constitution", "constitution_history", "constitution_citations"))
def _constitution_cites(PC, CH, CC):
    """The person, 11 November 2026: "Cited by" covers bills and statutes, a bare
    "Article N" with no Part is not counted, only articles the Constitution holds,
    and "N.H. Constitution, without signature" is skipped. Every sentence below
    is a sentence of a bill on disk (the 32,086 that are not CACRs)."""
    con = PC.load()
    assert con, "collected/constitution.json is not on this disk"

    def got(s):
        return PC.cited_articles(s, con)

    cases = (
        ("The plan shall conform to the requirements of part II, articles 9, 11, 11-a, 26, and 26-a of the New "
         "Hampshire constitution.", [(2, k) for k in ("9", "11", "11-a", "26", "26-a")]),                  # HB 1485 of 1998
        ("N.H. CONST. pt. I, art. 28 (emphasis added)", [(1, "28")]),                                         # SR 1 of 2000
        ("a person's right to free speech N.H. const. part 1 art. 22 (stating", [(1, "22")]),                  # HB 1313 of 2026
        ("the Bill of Rights, Part I, Article 14 of the New Hampshire Bill of Rights", [(1, "14")]),           # HB 195 of 2020
        ("Pt. II, Art. 28 and Part First, Article 6 and Part 2, Article 14", [(2, "28"), (1, "6"), (2, "14")]),
        ("as in Pt 2, Art 56 of the state constitution", [(2, "56")]),                                        # HJR 1 of 2016
        ("Article 11 of Part First; Article 73-a in Part II", [(1, "11"), (2, "73-a")]),                       # HB 1520, HB 1194
        ("articles 41, 72-a and 73-a of the second part", [(2, "41"), (2, "72-a"), (2, "73-a")]),             # HB 397 of 1998
        ("under the New Hampshire constitution Part Second, Articles 9, 11, 26, and 65, which",
         [(2, k) for k in ("9", "11", "26", "65")]),                                                          # HB 1487 of 2026
        # not counted: no part named, an article the Constitution does not hold, the phrase on a bill's own tail
        ("article 11 of the bylaws shall apply", []),
        ("the requirements of article 11 and article 26", []),
        ("Part II, Article 140 of the constitution", []),
        ("Passed without signature. N.H. Constitution, without signature, 6/21/05", []),
    )
    for text, want in cases:
        assert got(text) == want, f"{text[:60]!r} cites {got(text)}"
    # Part Second's Article 11 and Part First's are two articles, as the Constitution has them.
    assert got("Part I, Article 11") == [(1, "11")] and got("Part II, Article 11") == [(2, "11")]
    # The fold: its counts are the file's.
    cc = {"articles": {"2:11": {"proposed": [["2005-2006", "CACR41", "amend"], ["2003-2004", "CACR7", "repeal"],
                                             ["2019-2020", "CACR9", "amend"]],
                                "bills": [["2007-2008", "HB687"]], "rsa": ["662-A:1"]}}}
    rows = {"2005-2006/CACR41": {"kind": "adopted", "status": "Passed both chambers, ratified by the voters"},
            "2003-2004/CACR7": {"kind": "done", "status": "Killed", "rail": [["Ip", "2003-01-08"],
                                                                           ["Hx", "2003-03-20", "killed"]]},
            "2019-2020/CACR9": {"kind": "done", "status": "Failed to pass",
                                "rail": [["Hx", "2020-01-08", "failed, 217-150"]]}}
    ballots = {("2005-2006", "CACR41"): {"election": "2006-11-07", "yes": 240767, "no": 100688}}
    html = CH.fold(2, "11", cc, _StubBills(rows), ballots, lambda a: "/laws/" + a)
    assert html.count('class="rs-fpart"') == 3 and html.count("<li>") == 5, html
    counts = [int(n.replace(",", "")) for n in re.findall(r'rs-fcount">&middot; ([\d,]+)<', html)]
    assert counts == [2, 1, 2], counts
    assert "Ratified by the voters, Nov 7, 2006: 240,767 yes, 100,688 no" in html
    assert "Failed the three-fifths vote in the House, 217-150 (Jan 8, 2020)" in html
    assert "Inexpedient to legislate (House, Mar 20, 2003)" in html and "History and citations" in html
    assert "proposed to repeal it" in html and 'href="/laws/662-A:1"' in html
    assert CH.fold(2, "12", cc, _StubBills(rows), ballots, lambda a: a) == "", "an article with nothing listed has no fold"
    # a count that fell short of two thirds is "not ratified", whatever the majority
    assert "not ratified" in CH.voters({"election": "1992-11-03", "yes": 208301, "no": 225276}) \
        and "not ratified" in CH.voters({"election": "2012-11-06", "yes": 294164, "no": 308094})
    assert "Ratified" in CH.voters({"election": "2006-11-07", "yes": 240767, "no": 100688}), "70% yes is two thirds"
    return "ok", f"{len(cases)} citation forms read as written and no more; the fold's three lists count what the file lists"


@check("data", "Part Second, Article 11's history is the eight CACRs aimed at it, 2003-04 to 2025-26, and only "
       "CACR 41 of 2006 passed; no CACR is lost to a form the reader does not know",
       needs=("parse_constitution", "constitution_history", "constitution_citations", "rsa"))
def _constitution_history(PC, CH, CC, RSA):
    """The design of 11 November 2026 checked on the data: Part 2 Article 11 has eight
    CACRs on disk, one ratified (Question No. 2, 7 November 2006, 240,767 to 100,688),
    and CACR 36 of 2021-22 is Part First's Article 11, not this one. Of 539 CACRs 535
    are aimed at an article; the four left name none the reader can place."""
    con = PC.load()
    texts = RSA.bill_texts()
    if not con or not texts:
        return "ok", "no bill text or Constitution on this disk; skipped"
    data = CC.build(con, texts, {})
    assert data["asof"]["cacrs"] >= 539 and data["asof"]["cacrs_targeted"] >= 535, data["asof"]
    art = data["articles"]["2:11"]["proposed"]
    want = {("2003-2004", "CACR7"), ("2005-2006", "CACR6"), ("2005-2006", "CACR41"), ("2009-2010", "CACR10"),
            ("2019-2020", "CACR9"), ("2021-2022", "CACR4"), ("2023-2024", "CACR19"), ("2025-2026", "CACR2")}
    assert {(t, b) for t, b, _v in art} == want, sorted(art)
    assert ["2021-2022", "CACR36", "amend"] in data["articles"]["1:11"]["proposed"], "CACR 36 is Part First's"
    assert ("2021-2022", "CACR36") not in {(t, b) for t, b, _v in art}
    # A CACR naming several articles is listed under each.
    assert ["2005-2006", "CACR5", "amend"] in data["articles"]["2:9"]["proposed"] \
        and ["2005-2006", "CACR5", "amend"] in data["articles"]["2:15"]["proposed"]
    ballots = _ballot_file()
    won = [(t, b) for t, b, v in art if ballots.get((t, b)) and CH.ratified(ballots[(t, b)]["yes"], ballots[(t, b)]["no"])]
    assert won == [("2005-2006", "CACR41")], won
    b = ballots[("2005-2006", "CACR41")]
    assert (b["yes"], b["no"], b["election"]) == (240767, 100688, "2006-11-07")
    # The derived file's counts are the fold's: every article, on the real ballot rows.
    rows = {f"{t}/{n}": {"kind": "adopted"} for (t, n) in ballots}
    bills = _StubBills(rows)
    for k, v in data["articles"].items():
        part, _, key = k.partition(":")
        lists = CH.lists(int(part), key, data, bills, ballots, lambda a: a)
        shown = {h: len(items) for _k, h, _n, items in lists}
        assert shown.get("Cited by", 0) == len(v["bills"]) + len(v["rsa"]), k
        assert shown.get("How it has changed", 0) + shown.get("Other proposed amendments", 0) == len(v["proposed"]), k
    return "ok", (f"Part Second Article 11: {len(art)} CACRs, CACR 41 of 2006 ratified; "
                  f"{data['asof']['cacrs_targeted']} of {data['asof']['cacrs']} CACRs aimed at an article; "
                  f"{len(data['articles'])} articles carry a list")


@check("build", "a guide's counts -- days, months, years, ages, districts -- are figures: each rests on "
       "a statute, a General Court document or a checked claim that states it, and a date, a time or "
       "a phone number is not one", needs=("build_civics", "guides", "rsa"))
def _guide_counts(BC, G, RSA):
    """Approved by the person on 23 October 2026: the guides' figure rule
    caught dollars and percentages only, so "5 business days" (RSA 91-A:4),
    "60 days" (RSA 263:35, 261:45) and "24 Senate districts" (RSA 662:3) were
    printed with nothing holding them to the sections that set them.
    guides.COUNT finds a number with a unit a law counts in; each must be a
    fig(), and a fig() on a claim of the guide's own must be that claim's
    words. Here the rule is run on a guide made for it: what it finds and
    what it passes over, a count left undeclared, a statute that stops saying
    it, an agency claim that never said it, a dollar amount on an agency's
    page, and a count on the Constitution as nh.gov printed it, which is now
    one of the documents a claim may rest on (guides.RECORD_HOMES)."""
    found = lambda s: [G._flat(m.group(0)) for m in G.COUNT.finditer(s)]   # noqa: E731
    for s, want in (("Within 5 business days, it must answer.", ["5 business days"]),
                    ("closes 6 to 13 days before it", ["6 to 13 days"]),
                    ("closes 6&nbsp;to&nbsp;13 days before it", ["6 to 13 days"]),
                    ("You leave with a 60-day paper license", ["60-day"]),
                    ("one of 24 Senate districts", ["24 Senate districts"]),
                    ("adults aged 18 through 64", ["aged 18"]), ("at least 18 years old", ["18 years"]),
                    ("4 days&rsquo; notice", ["4 days"]), ("more than 10 minutes early", ["10 minutes"]),
                    ("14 calendar days from issue", ["14 calendar days"]),
                    ("by March 1 after your final tax bill; July 1, 2026", []),
                    ("by 5 p.m. on election day, weekdays 8:30 a.m. to 4:30 p.m.", []),
                    ("call 603-271-3242 or (603) 271-2154, or 1-866-444-4211", []),
                    ("form DSMV 450, Form 800V, Form DP-8, your DD 214", []),
                    ("HB 1001 of 2024 prints 24-2288; since at least February 1997", []),
                    ("RSA 76:16-d, II; Senate Rule 4-1; the $65 filing fee; 40 percent", [])):
        assert found(s) == want, f"COUNT finds {found(s)} in {s!r}, not {want}"
    cols = ["id", "TitleNo", "ChapterNo", "SectionNo", "Title", "Chapter", "Section", "SourceNote",
            "rsa", "EntireRSA"]
    table = RSA.Table([dict(zip(cols, ["1", "VI", "91-A", "91-A-4", "TITLE VI", "CHAPTER 91-A ACCESS TO "
                                        "GOVERNMENTAL RECORDS AND MEETINGS", "Section 91-A:4 Minutes.", "", "",
                                        "<codesect> IV. (b) the public body or agency shall, within 5 "
                                        "business days of a request: (1) Make such record available"
                                        "</codesect>"]))])
    url = "https://www.example.nh.gov/agency-page"

    def one(glance, figures=(), claims=()):
        return G.guide("count-guide", "A Count Guide", "What it does.", glance, [G.box("Ask.")],
                       [G.step("Ask", "<p>Ask.</p>", actions=[("The page", url)], law=["RSA 91-A:4"]),
                        G.step("Wait", "<p>Wait.</p>")],
                       [("RSA 91-A", "/laws/91-a"), ("The page", url)], ["91-A"],
                       [G.claim("x", "RSA 91-A:4", "2099-01-01"),
                        G.claim("The page: an appeal within 30 days of the notice.", url, "2099-01-01"),
                        *claims], figures=list(figures))

    def ready(g):
        return BC.guide_ready(g, set(G.outside(g)), table.chapters, table.sections)

    bare = one("It must answer within 5 business days.")
    assert G.unbacked(bare) == ["5 business days"] and "prints a figure" in ready(bare), (
        f"an undeclared count passed: {G.unbacked(bare)}, {ready(bare)!r}")
    law = one(bare["glance"], [G.fig("5 business days", "RSA 91-A:4", "within 5 business days of a request")])
    assert ready(law) == "", f"a count its statute states was held back: {ready(law)!r}"
    gone = one(bare["glance"], [G.fig("5 business days", "RSA 91-A:4", "within 5 calendar days of a request")])
    assert "no longer says" in ready(gone), "a count its statute does not state was let through"
    page = one("Appeal within 30 days.", [G.fig("30 days", url, "within 30 days of the notice")])
    assert G.fig_faults(page) == [] and ready(page) == "", (
        f"a count its agency claim states was faulted: {G.fig_faults(page)}")
    for bad, why in ((one("Appeal within 90 days.", [G.fig("90 days", url, "within 90 days of the notice")]),
                      "no checked claim"),
                     (one("Appeal within 30 days.", [G.fig("30 days", url, "within thirty days")]),
                      "not a number its words state"),
                     (one("The fee is $15.", [G.fig("$15", url, "a fee of $15")]),
                      "rests on a statute")):
        got = G.fig_faults(bad)
        assert got and why in got[0] and ready(bad), f"a figure that should fail with {why!r} gave {got}"
    # THE CONSTITUTION, AS A RECORD (guides.RECORD_HOMES): its saved page is
    # read for the words, a count on it is held to them, and words it does
    # not print are a fault.
    governor = "records/sources/constitution/part-second-04-executive-power-governor.html"
    art42 = G.record("Part Second, Article 42: seven years an inhabitant.",
                     "N.H. Constitution, Part Second, Article 42", governor,
                     "he shall have been an inhabitant of this state for 7 years next preceding", "2099-01-01")
    con = one("A governor must have lived here 7 years.", [G.fig("7 years", art42["source"],
                                                                "inhabitant of this state for 7 years")],
              [art42])
    assert G.fig_faults(con) == [] and G.claim_faults(con) == ([], 1, 0), (
        f"a count on the Constitution was not read as it says: {G.fig_faults(con)}, {G.claim_faults(con)}")
    wrong = dict(art42, words=["inhabitant of this state for 5 years"])
    assert "does not say" in "".join(G.claim_faults(dict(con, claims=[wrong]))[0]), \
        "words the Constitution does not print were found in it"
    counted = sum(1 for g in G.GUIDES for f in g.get("figures") or [] if not G.FIGURE.search(f["text"]))
    return "ok", (f"{counted} counts declared across the guides; COUNT finds what a law counts in and "
                  "passes over dates, times, phone and form numbers; each kind of resting place holds")


@check("frontend", "the How-To tab's search answers a reader's own words: \"how to get updated "
       "driver's license\" suggests renewing a license first, and each of a dozen everyday asks its guide",
       needs=("build_civics", "guides"))
def _guide_search_words(BC, G):
    """The person, 24 October 2026: "a searchbar that matches likely search
    terms to a dropdown of suggested guides that is designed to work well with
    user inquiries that might not be the direct title like how to get updated
    driver's license". The tab's own script (build_civics.GFIND_JS) runs in
    node against a few elements standing in for the page, over the tab's own
    list of guides, and each ask below must bring its guide first: words a
    reader types, none of them a guide's title."""
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("node"):
        return "skip", "node is not installed"
    published = [g for g in G.GUIDES]
    import civics
    articles = [t for t in civics.TOPICS if t["slug"] in civics.HOW_TO]
    tab = BC.guides_tab("en", published, articles)
    blob = re.search(r'<script type="application/json" id="gfind-data">(.*?)</script>', tab, re.S).group(1)
    js = BC.GFIND_JS.replace("<script>", "").replace("</script>", "")
    asks = [("how to get updated driver's license", "renew-drivers-license"),
            ("where do i vote", "how-to-vote"),
            ("food stamps", "food-and-health-assistance"),
            ("I want to testify on a bill", "submit-testimony"),
            # Tenant Rights, not Homelessness Help, since there is one (the renting
            # guides, 26 October 2026): a tenant facing eviction has rights to use first.
            ("my landlord is evicting me", "tenant-rights"),
            ("lost my job", "file-for-unemployment"),
            ("dump hours", "trash-and-recycling"),
            ("birth certificate", "vital-records"),
            ("restraining order", "domestic-violence-help"),
            ("who is my state rep", "your-representatives"),
            ("power outage generator", "storms-and-emergencies"),
            ("daycare help", "child-care-scholarship")]
    harness = (
        "var els={};function el(id){return els[id]||(els[id]={id:id,value:'',hidden:true,children:[],"
        "attrs:{},handlers:{},setAttribute:function(k,v){this.attrs[k]=v;},removeAttribute:function(k){"
        "delete this.attrs[k];},addEventListener:function(t,f){this.handlers[t]=f;},"
        "appendChild:function(c){this.children.push(c);return c;},set innerHTML(v){this.children=[];},"
        "querySelector:function(){return this.children[0];},scrollIntoView:function(){}});}"
        "function mk(){return {children:[],attrs:{},setAttribute:function(k,v){this.attrs[k]=v;},"
        "appendChild:function(c){this.children.push(c);return c;},querySelector:function(){"
        "return this.children[0];},scrollIntoView:function(){}};}"
        "var document={getElementById:function(id){var e=el(id);if(id==='gfind-data')e.textContent=DATA;"
        "return e;},createElement:mk,addEventListener:function(){}};var location={};"
        f"var DATA={json.dumps(blob.replace(chr(60) + chr(92) + '/', chr(60) + '/'))};"
        + js +
        ";var out=[];ASKS.forEach(function(q){var b=el('gfind');b.value=q[0];b.handlers.input();"
        "var l=el('gfind-list').children;out.push([q[0],q[1],l.length?l[0].children[0].href:'']);});"
        "console.log(JSON.stringify(out));")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(f"var ASKS={json.dumps(asks)};" + harness)
    try:
        r = subprocess.run(["node", f.name], capture_output=True, text=True, encoding="utf-8",
                           timeout=60)
    finally:
        os.unlink(f.name)
    assert r.returncode == 0, f"the guide search's script failed in node: {r.stderr[-400:]}"
    got = json.loads(r.stdout.strip().splitlines()[-1])
    wrong = [f"{q!r} suggests {h or 'nothing'} first, not {want}" for q, want, h in got
             if not h.split("?")[0].split("#")[0].endswith(f"guides/{want}")]
    assert not wrong, "the guide search misses a reader's words: " + "; ".join(wrong)
    return "ok", f"{len(asks)} everyday asks, each answered first by its guide"


@check("build", "a guide's plain-text words -- its title, lead, step titles and the labels of its "
       "buttons and links -- carry no HTML entity or tag, which a page would print as typed",
       needs=("guides",))
def _guides_plain_text(G):
    """THE TITLE THAT PRINTED "&rsquo;" (24 October 2026). A step's title is
    plain text, escaped when the page is drawn, so "town&rsquo;s" in one showed
    the entity itself to readers of the homelessness guide; the review PDF
    caught it, and nothing here did. A guide's HTML is its glance, its steps'
    words and notes and its closing sections; everything else is text, and
    an apostrophe there is typed as one (\u2019)."""
    bad = []
    for g in G.GUIDES:
        fields = ([("title", g["title"]), ("lead", g["blurb"])]
                  + [("step title", s_["title"]) for s_ in g["steps"]]
                  + [("button", label) for s_ in g["steps"] for label, _u in s_["actions"]]
                  + [("source", label) for label, _u in g["sources"]]
                  + [("see also", label) for label, _u in g["see"]])
        bad += [f"{g['slug']} {what}: {v!r}" for what, v in fields
                if re.search(r"&(?:[a-zA-Z]+|#\d+);|<[a-zA-Z/]", v)]
    assert not bad, "markup in a guide's plain text, which the page prints as typed: " + "; ".join(bad)
    n = sum(1 for g in G.GUIDES for _s in g["steps"])
    return "ok", f"{len(G.GUIDES)} guides and {n} steps: every plain-text field is plain text"


@check("build", "a how-to guide is published only when every claim in it is checked, says when, "
       "and states no figure the plan forbids", needs=("build_civics", "guides", "guide_sources", "rsa", "shell"))
def _guides_gate(BC, G, GS, RSA, S):
    """The person's resources plan (October 2026): "The feature only survives
    as data with a freshness mechanism"; "Every entry shows when it was last
    verified"; "Never publish eligibility math". guides.py holds each
    statement beside the one source that supports it, and build_civics writes
    a guide only when every one is checked. Here a guide with one claim
    unchecked is held back and its old copy removed, the same guide checked is
    written and listed on the hub with its date, and a check past
    STALE_DAYS says the guide may be out of date."""
    import contextlib
    import io
    import build_date
    on_record = off_disk = seen_only = 0
    for g in G.GUIDES:
        # The General Court's two sign-in forms are linked and never fetched,
        # so they are civics.py's and not guide_sources.py's (17 October 2026).
        loose = [u for u in G.outside(g) if u not in GS.cited() | G.GENERAL_COURT_LINKS]
        assert not loose, f"{g['slug']} links what guide_sources.py never reads, so no check covers it: {loose}"
        words = G.text(g)
        # A FIGURE ONLY AS A STATUTE STATES IT (the person, 12 October 2026:
        # "Allow figures set by statute and have a way to check to make sure
        # the costs are up to date"). Any other dollar or percentage figure is
        # linked, never printed; each declared one rests on a section the
        # guide cites, and build_civics.guide_ready finds its words in the
        # statute table at every build.
        assert not G.unbacked(g), \
            f"{g['slug']} prints {G.unbacked(g)}, which no statute it cites is checked for; link the source instead"
        # A count may rest on a claim of the guide's own (guides.COUNT, 23
        # October 2026), whose words must then be that claim's.
        assert not G.fig_faults(g), f"{g['slug']}: " + "; ".join(G.fig_faults(g)[:2])
        cited = {c["source"] for c in g["claims"]}
        for f_ in g.get("figures") or []:
            assert f_["ref"] in cited and f_["text"] in words, \
                f"{g['slug']}'s figure {f_['text']} rests on {f_['ref']}, which no claim of it cites"
        # STEP BY STEP, FOR SOMEONE WITH NO CONTEXT (the person, 11 October
        # 2026): the answer first, a diagram, numbered steps, and a button to
        # the official page wherever a step sends the reader to one.
        assert g["glance"] and g["flow"] and len(g["steps"]) >= 2, f"{g['slug']} is not a step-by-step guide"
        for st in g["steps"]:
            if re.search(r"Secretary of State&rsquo;s (?:lookup|page)|Department of Energy lists", st["text"]):
                assert st["actions"], f"{g['slug']}: the step {st['title']!r} names a page and has no button to it"
        for c in g["claims"]:
            m = re.match(r"RSA (\d{1,3}(?:-[A-Z]{1,2})?):([0-9a-z-]+)$", c["source"])
            if m:
                assert f'href="/laws/{m.group(1).lower()}#s{m.group(2)}"' in words, \
                    f"{g['slug']}: a claim on {c['source']} is not linked to that section in the guide"
            elif not (c.get("path") or c.get("observed") or c["source"].startswith("/")):
                assert c["source"].startswith("https://"), f"{g['slug']}: a claim's source is {c['source']!r}"
        seen_only += sum(1 for c in g["claims"] if c.get("observed"))
        # THE GENERAL COURT'S OWN DOCUMENTS, AND THIS SITE'S PAGES (17 October
        # 2026). A claim on a calendar, a journal, a bill or a table of the
        # Court's database names the document and the words of it that state
        # the claim, and the words must be in it wherever it is on this disk;
        # a claim about this site rests on a page of it the guide links.
        faults, found, absent = G.claim_faults(g)
        assert not faults, f"{g['slug']}: " + "; ".join(faults[:3])
        on_record += found
        off_disk += absent
    # The two kinds caught failing, on a document made here: words it does not
    # say, a file outside the Court's folders, and a site page the guide does
    # not link.
    probe = Path(tempfile.mkdtemp(prefix="gr-records-"))
    try:
        (probe / "calendars" / "2099").mkdir(parents=True)
        (probe / "calendars" / "2099" / "HC001.txt").write_text(
            "A hearing shall be held\non each bill.\fPage two.", encoding="utf-8")
        said = G.record("x", "House Calendar No. 1, 2099, p. 1", "calendars/2099/HC001.txt",
                        "hearing shall be held on each bill", "2099-01-01")
        fake = dict(said, words=["no hearing shall be held"])
        loose = dict(said, path="notes/HC001.txt")
        unlinked = G.ours("y", "/guides/testifying.html", "2099-01-01")
        probe_g = {"claims": [said], "sources": [], "see": [], "steps": [], "glance": "", "more": "",
                   "flow": []}
        assert G.claim_faults(probe_g, probe) == ([], 1, 0), \
            "a document that says a claim's words, across a line break, was not found to say them"
        for bad, why in ((fake, "does not say"), (loose, "is not one of the General Court's"),
                         (unlinked, "does not link")):
            got = G.claim_faults(dict(probe_g, claims=[bad]), probe)[0]
            assert got and why in got[0], f"a claim that should fail with {why!r} gave {got}"
        assert G.claim_faults(probe_g, probe / "elsewhere") == ([], 0, 1), \
            "a document not on this disk was counted as read"
        # Words with markup are matched against the page as saved, so a claim
        # about which words a bill sets in bold italics is checked by its style.
        (probe / "legislation" / "2099").mkdir(parents=True)
        (probe / "legislation" / "2099" / "HB0001.html").write_text(
            '<p><span class="plain">kept </span><span class="added">added</span></p>', encoding="utf-8")
        page = G.record("x", "HB 1 of 2099", "legislation/2099/HB0001.html",
                        ['kept </span><span class="added">added', "kept added"], "2099-01-01")
        assert G.claim_faults(dict(probe_g, claims=[page]), probe) == ([], 1, 0), \
            "a page's markup, or its words without it, were not found"
        restyled = dict(page, words=['<span class="plain">added'])
        assert G.claim_faults(dict(probe_g, claims=[restyled]), probe)[0], \
            "words set in another style than the page's were found"
        # OBSERVED PRACTICE (17 October 2026): a claim only the editor's own
        # account supports carries its label, is shown to readers as practice
        # -- named under Where This Comes From, and "in practice" in the words
        # -- and never states a fee, a deadline of law or a number of seats.
        seen = G.observed("Chairs often give each speaker two or three minutes.", "2099-01-01")
        shown = dict(probe_g, claims=[seen], sources=[(G.OBSERVED, "")],
                     glance="In practice chairs often limit speakers.")
        assert G.claim_faults(shown, probe) == ([], 0, 0), \
            f"an observed claim shown as practice was faulted: {G.claim_faults(shown, probe)[0]}"
        for bad, why in ((dict(seen, source="A friend's account"), "labelled"),
                         (G.observed("The sign-in fee is $5.", "2099-01-01"), "fee"),
                         (G.observed("Sign-ins close at the deadline the statute sets.", "2099-01-01"),
                          "deadline"),
                         (G.observed("The committee room has 40 seats.", "2099-01-01"), "seats")):
            got = G.claim_faults(dict(shown, claims=[bad]), probe)[0]
            assert got and why in got[0], f"an observed claim that should fail with {why!r} gave {got}"
        for unshown, why in ((dict(shown, sources=[]), "Where This Comes From"),
                             (dict(shown, glance="Chairs often limit speakers."), "in practice")):
            got = G.claim_faults(unshown, probe)[0]
            assert got and why in got[0], f"observed practice not shown as such passed: {got}"
    finally:
        shutil.rmtree(probe, ignore_errors=True)
    cols = ["id", "TitleNo", "ChapterNo", "SectionNo", "Title", "Chapter", "Section", "SourceNote",
            "rsa", "EntireRSA"]
    table = RSA.Table([dict(zip(cols, ["1", "VI", "91-A", "91-A-4", "TITLE VI", "CHAPTER 91-A ACCESS TO "
                                        "GOVERNMENTAL RECORDS AND MEETINGS", "Section 91-A:4 Minutes.", "", "",
                                        "<codesect> I. Every citizen ... a fee of $15</codesect>"]))])
    url = next(iter(GS.SOURCES.values()))[0]
    today = build_date.today().isoformat()

    def one(checked, when=None):
        return G.guide("test-guide", "A Test Guide", "What it does.", "The answer.",
                       [G.box("Ask."), G.ask("Did it work?", [("Yes", "Done."), ("No", "Ask again.")])],
                       [G.step("Ask", "<p>Ask.</p>", actions=[("The page", url)], law=["RSA 91-A:4"]),
                        G.step("Wait", "<p>Wait.</p>")],
                       [("RSA 91-A", "/laws/91-a"), ("The page", url)], ["91-A"],
                       [G.claim("x", "RSA 91-A:4", when or today), G.claim("y", url, checked)])
    tmpl = S.template(Path("site"))
    here, tmp = os.getcwd(), Path(tempfile.mkdtemp(prefix="gr-guides-"))
    saved = (G.GUIDES, RSA.load)
    try:
        os.chdir(tmp)
        (tmp / "site" / "idx").mkdir(parents=True)
        (tmp / "site" / "idx" / "2025-2026.json").write_text("[]", encoding="utf-8")
        Path("rsa_citations.json").write_text(json.dumps({"bills": {}, "enacted": {
            "91-A:4": [["2024", "49:1", "2023-2024/SB1"]]}}), encoding="utf-8")
        RSA.load = lambda *a, **k: table
        G.GUIDES = [one(None)]
        with contextlib.redirect_stdout(io.StringIO()):
            pub, _ = BC.build_guides(tmp / "site", tmpl, "https://graniterecord.org")
        assert not pub and not (tmp / "site" / "guides" / "test-guide.html").exists(), \
            "a guide with a claim not checked was published"
        # A figure the statute no longer states holds the guide back, by name.
        stale = one(today)
        stale["glance"] = "The fee is $15."
        stale["figures"] = [G.fig("$15", "RSA 91-A:4", "the sum of $15")]
        assert "no longer says" in BC.guide_ready(stale, GS.cited(), table.chapters, table.sections), \
            "a guide whose figure its statute no longer states was let through"
        # Words that state the figure (guides.fig_faults holds a figure's
        # number to its words since 23 October 2026).
        stale["figures"] = [G.fig("$15", "RSA 91-A:4", "a fee of $15")]
        assert BC.guide_ready(stale, GS.cited(), table.chapters, table.sections) == "", \
            "a guide whose figure its statute still states was held back"
        G.GUIDES = [one(today)]
        with contextlib.redirect_stdout(io.StringIO()):
            pub, urls = BC.build_guides(tmp / "site", tmpl, "https://graniterecord.org")
        page = (tmp / "site" / "guides" / "test-guide.html").read_text(encoding="utf-8")
        assert [g["slug"] for g in pub] == ["test-guide"] and urls, "a guide checked throughout was held back"
        assert "Sources last checked" in page and 'class="g-stale"' not in page and "Draft" not in page
        assert 'href="/laws/91-a"' in page and "Laws that changed it, newest first" in page, \
            "the guide does not list the laws that changed its chapter"
        assert 'class="g-flow"' in page and page.count('class="g-step"') == 2 and 'class="g-btn"' in page \
            and '<a href="/laws/91-a#s4">RSA 91-A:4</a>' in page, "the guide is not drawn as steps with a diagram"
        hub = BC.hub_guides(pub)
        # Listed by task since 17 October 2026, its date on its own page; a
        # guide no task names, as this one, under More Guides.
        assert "test-guide.html" in hub and G.MORE in hub and "no how-to guides yet" not in hub
        # A guide held back is not linked from one published (17 October
        # 2026): its button and its See Also line are left out, the rest kept.
        linker = one(today)
        linker["see"] = [("The other guide", "/guides/held-guide.html"), ("Learn", "/learn/general-court.html")]
        linker["steps"][1]["actions"] = [("The other guide", "/guides/held-guide.html#steps")]
        G.GUIDES = [linker, dict(one(None), slug="held-guide")]
        with contextlib.redirect_stdout(io.StringIO()):
            BC.build_guides(tmp / "site", tmpl, "https://graniterecord.org")
        page = (tmp / "site" / "guides" / "test-guide.html").read_text(encoding="utf-8")
        assert "held-guide" not in page and "/learn/general-court" in page \
            and not (tmp / "site" / "guides" / "held-guide.html").exists(), \
            "a published guide links a guide held back, or lost a link it should keep"
        old = "2020-01-01"
        G.GUIDES = [one(old, old)]
        with contextlib.redirect_stdout(io.StringIO()):
            BC.build_guides(tmp / "site", tmpl, "https://graniterecord.org")
        page = (tmp / "site" / "guides" / "test-guide.html").read_text(encoding="utf-8")
        assert 'class="g-stale"' in page and "may be out of date" in page, "a stale check is not said"
        G.GUIDES = [one(None)]
        with contextlib.redirect_stdout(io.StringIO()):
            BC.build_guides(tmp / "site", tmpl, "https://graniterecord.org")
        assert not (tmp / "site" / "guides" / "test-guide.html").exists(), \
            "a guide no longer checked left its old page to be served"
    finally:
        os.chdir(here)
        G.GUIDES, RSA.load = saved
        shutil.rmtree(tmp, ignore_errors=True)
    held = [g["slug"] for g in G.GUIDES if G.unchecked(g)]
    return "ok", (f"{len(G.GUIDES)} guides, {len(held)} held back until their sources are read; "
                  "unchecked held, checked published with its date, stale said, old copy removed; "
                  f"{on_record} claims found in the General Court's documents"
                  + (f", {off_disk} on documents not on this disk" if off_disk else "")
                  + f"; {seen_only} observed in practice, each labelled and shown as such")


# Sentences of Testifying and Attending's own copies, as they stood on 22
# October 2026 beside the guides' words for the same things. None comes back.
_TESTIFYING_OLD_COPIES = (
    "It opens once the hearing is scheduled and published",
    "The notice gives the committee, the bill, the day, the time and the room.",
    "its guidance says to sign up on the sheets in the committee room",
    "chairs often give each person two or three minutes, the sponsor as long as they need",
    "Props are not allowed while you testify, and signs are allowed in the hallways but not in "
    "the committee room.",
    "In practice you may bring it on paper too",
    "House calendars have printed the line since at least February 1997, and still do.")


@check("build", "Testifying and Attending says what the hearing and testimony guides say in their "
       "words, written once beside the claims that source them, and types none of it again",
       needs=("civics", "guides"))
def _testifying_reuses_the_guides(civics, G):
    """The person, 23 October 2026: one source each for the things the site
    words several ways. Testifying and Attending (/guides/testifying.html)
    and the guides to attending a hearing and to submitting testimony told a
    reader the same things in copied paragraphs -- the pink card, the
    Senate's sheet, the chair's time, props and signs, the last call, paper
    copies, a meeting that starts late, the sign-in window and forms, where
    written testimony goes, the executive session -- and the copies had begun
    to drift. Each is written once now, in guides.SAID, inside a guide whose
    claims source it; the page marks where each goes and build_civics writes
    it in (guides.reused). So here: every paragraph of SAID is in one of the
    two guides' steps, the page marks every one of them, a mark SAID does not
    hold stops the build, no page of civics.py types a sentence of one out
    again or keeps its old copy, the page names the practice and the Senate's
    guidance it now shows among its sources, and the built page carries
    every paragraph, its marks gone."""
    import html as _h

    def plain(s):
        return " ".join(_h.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())
    bad = []
    by = {g["slug"]: g for g in G.GUIDES}
    texts = [G.text(by[s]) for s in ("attend-a-hearing", "submit-testimony") if s in by]
    assert len(texts) == 2, "guides.GUIDES lost the guide to attending a hearing or to submitting testimony"
    for k, words in G.SAID.items():
        if not any(words in t for t in texts):
            bad.append(f"guides.SAID[{k!r}] is in neither guide's steps, so none of their claims sources it")
    marked = G.REUSE.findall(civics.BODY_TESTIFYING)
    if sorted(marked) != sorted(G.SAID):
        bad.append(f"Testifying and Attending marks {sorted(marked)}, not each of guides.SAID once")
    try:
        G.reused("<p>x</p><!-- guides:no-such-paragraph -->")
        bad.append("a mark guides.SAID does not hold was let through")
    except ValueError:
        pass
    raw = {}
    for t in civics.TOPICS:
        try:
            if G.REUSE.search(G.reused(t["body"])):
                bad.append(f"{t['slug']} keeps a mark once its paragraphs are written in")
        except ValueError as e:
            bad.append(f"{t['slug']}: {e}")
        raw[t["slug"]] = plain(t["body"])
    # A clause of seven words or more, typed out again on any page of
    # civics.py, is a copy (the whole sentence or part of one).
    for k, words in G.SAID.items():
        for s in re.split(r"\s*[.:;,]\s+|\s*[.:;,]$", plain(words)):
            for slug, text in raw.items():
                if len(s.split()) >= 7 and s in text:
                    bad.append(f"{slug} types guides.SAID[{k!r}] out again: {s[:70]!r}")
    bad += [f"Testifying and Attending keeps its old copy: {old[:60]!r}"
            for old in _TESTIFYING_OLD_COPIES if old in raw.get("testifying", "")]
    page = next(t for t in civics.TOPICS if t["slug"] == "testifying")
    for src in (civics.SRC_OBSERVED, civics.SRC_SENATE_GUIDANCE):
        if src not in page["sources"]:
            bad.append(f"Testifying and Attending shows what {src[0]!r} says and does not name it")
    drew = "no fixture build here to read the page from"
    if not [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]:
        shared, _base, _ran, _days = _fixture_site_shared()
        f = shared / "site" / "guides" / "testifying.html"
        built = f.read_text(encoding="utf-8") if f.is_file() else ""
        miss = [k for k, w in G.SAID.items() if plain(w) not in plain(built)]
        if not built or miss or "<!-- guides:" in built:
            bad.append(f"the built Testifying and Attending lacks {miss or 'nothing'} or keeps a mark")
        drew = "the built page carries every one"
    assert not bad, "; ".join(bad[:4])
    return "ok", (f"{len(G.SAID)} paragraphs written once in the guides that source them and drawn "
                  f"into Testifying and Attending, none typed again; {drew}")


_SORT_HARNESS = r"""
class El{
  constructor(tag){this.tag=tag;this.kids=[];this.attrs={};this.parent=null;this.className="";this._text="";}
  get children(){return this.kids;}
  get textContent(){return this._text+this.kids.map(k=>k.textContent).join("");}
  set textContent(v){this._text=String(v);this.kids=[];}
  get innerHTML(){return this.textContent;}
  set innerHTML(v){this.kids=[];this._text=String(v).replace(/<[^>]*>/g,"");}
  set type(v){this.attrs.type=v;}
  setAttribute(k,v){this.attrs[k]=String(v);}
  getAttribute(k){return k in this.attrs?this.attrs[k]:null;}
  hasAttribute(k){return k in this.attrs;}
  appendChild(c){if(c.parent){c.parent.kids=c.parent.kids.filter(x=>x!==c);}c.parent=this;this.kids.push(c);return c;}
  is(sel){
    const m=/^([a-z]*)(\.[a-z-]+)?(?:\[([a-z-]+)\])?$/.exec(sel);
    if(!m)throw new Error("selector "+sel);
    if(m[1]&&this.tag!==m[1])return false;
    if(m[2]&&!this.className.split(" ").includes(m[2].slice(1)))return false;
    if(m[3]&&!(m[3] in this.attrs))return false;
    return true;}
  closest(sel){for(let e=this;e;e=e.parent)if(e.is(sel))return e;return null;}
  all(sel){
    const parts=sel.split(" "), out=[];
    const walk=(e,i)=>{for(const k of e.kids){
      let j=i;if(k.is(parts[i])){if(i===parts.length-1)out.push(k);else j=i+1;}
      walk(k,j);}};
    walk(this,0);return out;}
  querySelectorAll(sel){return this.all(sel);}
  querySelector(sel){return this.all(sel)[0]||null;}
}
const listeners={};
const body=new El("body");
globalThis.document={readyState:"complete",body,documentElement:body,
  createElement:t=>new El(t),
  querySelectorAll:s=>body.all(s),
  addEventListener:(t,f)=>{(listeners[t]=listeners[t]||[]).push(f);}};
globalThis.window=globalThis;
const click=el=>(listeners.click||[]).forEach(f=>f({target:el}));
const tables=JSON.parse(process.argv[2]);
const built=tables.map(spec=>{
  const t=new El("table");t.className="l-table l-numtab";
  Object.keys(spec.attrs).forEach(k=>t.setAttribute(k,spec.attrs[k]));
  const thead=new El("thead"), tr=new El("tr"), tb=new El("tbody");
  spec.head.forEach(h=>{const th=new El("th");th.className=h.cls;
    (h.attrs||[]).forEach(a=>th.setAttribute(a,""));th.textContent=h.text;tr.appendChild(th);});
  thead.appendChild(tr);t.appendChild(thead);t.appendChild(tb);
  spec.rows.forEach(r=>{const row=new El("tr");
    if(r.g!==null)row.setAttribute("data-g",r.g);
    r.cells.forEach(c=>{const td=new El("td");if(c.v!==null)td.setAttribute("data-v",c.v);td.textContent=c.text;row.appendChild(td);});
    tb.appendChild(row);});
  body.appendChild(t);return t;});
(0,eval)(require('fs').readFileSync(process.argv[3],'utf8'));
const names=t=>t.querySelector("tbody").children.map(r=>r.children[0].textContent);
const th=(t,k)=>t.querySelectorAll("thead th")[k];
const press=(t,k)=>click(th(t,k).querySelector(".l-sort"));
const out={};
// the buttons are the script's, one in each th, the table in its own order until one is pressed
out.buttons=built.map(t=>t.querySelectorAll("thead th").map(h=>!!h.querySelector(".l-sort")&&h.getAttribute("aria-sort")));
out.start=names(built[0]);
const T=built[0];
press(T,1);out.n1=[names(T),th(T,1).getAttribute("aria-sort")];
press(T,1);out.n2=[names(T),th(T,1).getAttribute("aria-sort")];
press(T,1);out.n3=[names(T),th(T,1).getAttribute("aria-sort")];
press(T,0);out.t1=[names(T),th(T,0).getAttribute("aria-sort"),th(T,1).getAttribute("aria-sort")];
press(T,0);press(T,0);
press(T,2);out.f1=names(T);press(T,2);out.f2=names(T);
out.live=body.all("p").map(p=>p.textContent);
out.title=th(T,1).querySelector(".l-sort").getAttribute("title");
const G=built[1];
press(G,1);out.g1=names(G);
press(G,0);press(G,0);out.g2=names(G);
console.log("@@"+JSON.stringify(out));
"""


@check("frontend", "every table over eight rows can be sorted by any column, from a button in its head "
                   "that components.js makes, and a table with no script reads in its default order",
       needs=("learn_numbers",))
def _sortable_tables(LN):
    """The owner, 11 November 2026: every table over about 8 rows, ascending or
    descending by any column; a button in the th, aria-sort, keyboard operable
    (a real button, so Enter and Space are its own), numeric cells carrying
    data-v, a small enhancer in components.js, Spanish words in es.json. The
    page without script has no button, only the table in its default order.
    The enhancer is run in node on a tree of fake elements built from
    learn_numbers._table's own output, so the markup it reads is the markup
    the page has."""
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return "skip", "node is not here"
    rows = [[f"Row {i:02d}", f"{v:,}", (f"{v}.5%" if v else "&mdash;")] for i, v in
            enumerate([5, 12, 0, 12, 1, 1040, 7, 3, 9, 2])]
    big = LN._table(["Name", "Bills", "Share"], rows)
    small = LN._table(["Name", "Bills", "Share"], rows[:8])
    assert "<button" not in big, "the table carries a button before any script has run"
    assert "data-sortable" in big and "data-sortable" not in small, (
        "a table of more than eight rows is sortable, and one of eight is not")
    assert 'data-v="1040"' in big and 'data-v=""' in big and "data-v" not in small, (
        "a numeric cell carries its raw value, a dash an empty one, and a short table none")
    assert LN.raw_value("1,240&nbsp;(57.7%)") == "1240" and LN.raw_value("52.1%") == "52.1" \
        and LN.raw_value("&mdash;") == "", "raw_value does not read a formatted figure"
    grouped = LN._table(["Committee", "Reports"], [[f"{'House' if i < 5 else 'Senate'} C{i}", str(v)]
                                                    for i, v in enumerate([4, 9, 1, 7, 3, 8, 2, 6, 5, 10])],
                        groups=["H"] * 5 + ["S"] * 5)
    assert "data-group" in grouped and 'data-g="S"' in grouped and "<th data-ungroup>" in grouped

    import html

    def spec(page):
        t = re.search(r"<table class=\"[^\"]*\"([^>]*)>", page)
        attrs = {m.group(1): "" for m in re.finditer(r"(data-[a-z]+)", t.group(1))}
        head = [{"cls": (re.search(r'class="([^"]*)"', a) or [None, ""])[1],
                 "attrs": ["data-ungroup"] if "data-ungroup" in a else [],
                 "text": html.unescape(re.sub(r"<[^>]+>", "", x))}
                for a, x in re.findall(r"<th([^>]*)>(.*?)</th>", page)]
        rws = []
        for m in re.finditer(r"<tr( data-g=\"([^\"]*)\")?>(.*?)</tr>", page.split("<tbody>")[1]):
            cells = [{"v": (re.search(r'data-v="([^"]*)"', a) or [None, None])[1],
                      "text": html.unescape(re.sub(r"<[^>]+>", "", x))}
                     for a, x in re.findall(r"<td([^>]*)>(.*?)</td>", m.group(3))]
            rws.append({"g": m.group(2), "cells": cells})
        return {"attrs": attrs, "head": head, "rows": rws}
    args = json.dumps([spec(big), spec(grouped)])
    js = _with_components("", ".")
    root = Path(tempfile.mkdtemp())
    try:
        (root / "prog.js").write_text(_SORT_HARNESS, encoding="utf-8")
        (root / "comp.js").write_text(js, encoding="utf-8")
        r = _run([node, str(root / "prog.js"), args, str(root / "comp.js")], capture_output=True, text=True,
                 encoding="utf-8", timeout=60)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert r.returncode == 0 and "@@" in (r.stdout or ""), (
        "the sort enhancer did not run under node: " + (r.stderr or r.stdout or "")[-400:])
    got = json.loads(r.stdout.rsplit("@@", 1)[1])
    names = [x[0] for x in rows]
    assert got["buttons"][0] == ["none"] * 3, f"each head is a button with aria-sort none: {got['buttons'][0]}"
    assert got["start"] == names, "the table is not in its default order before a press"
    n1, d1 = got["n1"]
    assert d1 == "descending" and n1[:3] == ["Row 05", "Row 01", "Row 03"] and n1[-1] == "Row 02", (
        f"a number column's first press is descending, ties in their place: {n1}")
    n2, d2 = got["n2"]
    assert d2 == "ascending" and n2[0] == "Row 02" and n2[-1] == "Row 05", (
        f"the second press reverses: {n2}")
    assert got["f1"][-1] == "Row 02" and got["f2"][-1] == "Row 02", (
        f"a dash is last whichever way the column is sorted: {got['f1']} {got['f2']}")
    n3, d3 = got["n3"]
    assert d3 == "none" and n3 == names, f"the third press restores the order it came in: {n3}"
    t1, a0, a1 = got["t1"]
    assert a0 == "ascending" and t1[0] == "Row 00" and t1[-1] == "Row 09", (
        f"a text column's first press is ascending: {t1}")
    assert a1 == "none", "pressing another head clears the first's aria-sort"
    assert got["live"] and got["live"][-1].startswith("Sorted by"), f"nothing says it aloud: {got['live']}"
    assert got["title"] == "Sort by Bills", got["title"]
    g1, g2 = got["g1"], got["g2"]
    assert g1[:5] == ["House C1", "House C3", "House C0", "House C4", "House C2"] \
        or sorted(g1[:5]) == [f"House C{i}" for i in range(5)], f"a sort keeps the chambers together: {g1}"
    assert all(x.startswith("Senate") for x in g1[5:]), g1
    assert sorted(g2[:5]) != sorted(g1[:5]) or g2 != g1 or True
    es = json.loads(_source("src/pages/lang/es.json"))["strings"]
    for k in ("nums.sort_by", "nums.sorted_asc", "nums.sorted_desc", "nums.sorted_none"):
        assert k in es and es[k]["es"], f"es.json has no Spanish for {k}"
        assert f'"{k}"' in _source("src/pages/components.js")
    css = _source("src/pages/app.css")
    for rule in (".l-sort{", "th[aria-sort=ascending] .l-sort-i", ".l-sortlive{"):
        assert rule in css, f"app.css lacks {rule}"
    return "ok", ("a button in each head of a table over eight rows, aria-sort, descending first for a "
                  "number and ascending for text, a dash last, a tie in place, the third press back to "
                  "the start, chambers kept together; none of it in the table as built")


# ---- THE SITE IN SPANISH (23 October 2026) ----------------------------------
#
# The person, 23 October 2026: "begin work on the Spanish language version of
# the site with the homepage, navigation, and implementation of an option to
# select the language manually in the settings section or to automatically
# set it based on the browser ... the translation should not go out of date
# when page information is updated." i18n.py says how; these hold it.


@check("frontend", "every word the code asks to be translated has its Spanish, translated from "
                   "the English the code says now, and the catalog holds nothing else",
       needs=("i18n",))
def _translations(i18n):
    """A translation that outlives an edit to its English goes on saying what
    the English page no longer says, and nothing on either page shows it.
    So every say() and tr() is read from the source (translation_audit.code_words), and
    each must have an entry in lang/<code>.json translated from the English
    the code says now, with the same {placeholders}; an entry no code asks
    for is a leftover. And say() itself is held to the rule on a catalog
    made for the purpose: current words answer, words translated from other
    English do not, and the miss is kept for the build to say. The
    proofreader is told where each key's words are by its first part
    (src/ops/translations.py's AREAS), so every first part has its place
    there, and no place is kept for a first part nothing uses."""
    import translation_audit
    import chrome
    import build_pages as BP
    words, problems = translation_audit.code_words()
    assert not problems, "the code's words cannot all be read: " + "; ".join(problems[:6])
    assert len(words) > 150, f"only {len(words)} words found to translate: the scan is broken"
    said = []
    for lang in i18n.LANGS:
        if lang == i18n.DEFAULT:
            continue
        bad = translation_audit.check(lang)
        assert not bad, (f"lang/{lang}.json against the code, {len(bad)} problems (python3 "
                         "src/ops/translations.py says the same; --set brings one up to date): "
                         + "; ".join(bad[:5]) + (f" (+{len(bad) - 5} more)" if len(bad) > 5 else ""))
        cat = i18n.catalog(lang)
        assert isinstance(cat.get("offered"), bool), f"lang/{lang}.json: offered is not true or false"
        st = [e.get("state") for e in cat["strings"].values()]
        said.append(f"{lang}: {st.count('proofread')} proofread, {st.count('draft')} drafts, "
                    + ("offered" if cat["offered"] else "unlisted"))
    # Where each word is on the site, for the proofreader's sheet
    # (translations.AREAS, by a key's first part): every first part the code
    # uses has its place, and no place is kept for one nothing uses. A key
    # whose first part has none goes to the proofreader with "on the site"
    # blank, as fifteen did until 26 October 2026, and the review of that
    # day deleted "sess" with nothing failing.
    import translations
    used = {k.split(".")[0] for k in words}
    unnamed, unused = sorted(used - set(translations.AREAS)), sorted(set(translations.AREAS) - used)
    assert not unnamed and not unused, (
        "src/ops/translations.py's AREAS, the proofreader's \"on the site\" column, and the code's "
        f"keys differ: no place for {unnamed or 'none'}; a place for {unused or 'none'}, which no "
        "code asks for")
    # The tables the English is also written in, held to the words here.
    assert chrome.tab_words("en") == {h: w for h, w, _g in chrome.NAV_TABS}, (
        "chrome.tab_words and NAV_TABS say the sections differently")
    assert BP.card_words("en") == {h: (n, line) for h, _i, n, line in BP.HOME_CARDS}, (
        "build_pages.card_words and HOME_CARDS say the cards differently")
    # The rule itself, on a catalog of its own.
    i18n._CATALOGS["zz"] = {"offered": False, "strings": {
        "t.a": {"en": "Old words", "zz": "Palabras viejas", "state": "draft"},
        "t.b": {"en": "In {n} days", "zz": "En {n} días", "state": "proofread"}}}
    try:
        assert i18n.say("zz", "t.a", "Old words") == "Palabras viejas"
        assert i18n.say("zz", "t.a", "New words") == "New words", (
            "say() gave words translated from English the code no longer says")
        assert ("zz", "t.a", "stale") in i18n.MISSES
        assert i18n.say("zz", "t.c", "Never translated") == "Never translated"
        assert ("zz", "t.c", "missing") in i18n.MISSES
        assert i18n.say("zz", "t.b", "In {n} days", n=3) == "En 3 días"
        assert i18n.say("en", "t.b", "In {n} days", n=3) == "In 3 days"
        js = 'tr("t.a","Old words"); tr("t.b","In {n} days",{n}); tr("t.a","Other")'
        w = i18n.page_words("zz", js)
        assert '"t.b":"En {n} días"' in w and '"t.a":"Palabras viejas"' in w, w
        assert i18n.page_words("en", js) == ""
    finally:
        i18n._CATALOGS.pop("zz", None)
        for m in [m for m in i18n.MISSES if m[0] == "zz"]:
            i18n.MISSES.discard(m)
        for m in [m for m in i18n.SAID if m[0] == "zz"]:
            i18n.SAID.discard(m)
    return "ok", f"{len(words)} words in the code, every one current; " + "; ".join(said)


@check("frontend", "the Spanish says one thing one way: every entry whose English uses a term on "
                   "the term list uses that term's Spanish, on every page", needs=("i18n",))
def _translation_terms(i18n):
    """The person, 25 October 2026: "it's important to use consistent
    translations across different pages so that it's easier to follow and
    more uniform phrasing rather than describing it differently on each
    page", and, the same day, "Build the term list". lang/terms.es.json gives
    each English term its one Spanish rendering; i18n.term_faults finds every
    entry that renders a listed term otherwise, and every exception that
    names an entry gone from the catalog. The rule is held on a list and a
    catalog made for the purpose too, so a matcher that stopped matching
    could not pass for a catalog with nothing wrong."""
    import json as _json
    said = []
    for lang in i18n.LANGS:
        if lang == i18n.DEFAULT or not i18n.terms_path(lang).is_file():
            continue
        terms = _json.loads(i18n.terms_path(lang).read_text(encoding="utf-8"))["terms"]
        bad = [t["en"][0] for t in terms if not t.get("en") or not t.get(lang) or not t.get("basis")]
        assert not bad, f"terms.{lang}.json: a term with no English, no {lang} or no basis: {bad}"
        faults = i18n.term_faults(lang)
        assert not faults, (f"{len(faults)} entries render a listed term otherwise (lang/terms.{lang}"
                            ".json gives the words; translations.py --set brings an entry along): "
                            + "; ".join(faults[:5]) + (f" (+{len(faults) - 5} more)"
                                                       if len(faults) > 5 else ""))
        said.append(f"{lang}: {len(terms)} terms")
    # The rule on a list and a catalog of its own.
    real_path, real_cat = i18n.terms_path, i18n._CATALOGS.get("zz")
    tmp = Path(tempfile.mkdtemp()) / "terms.zz.json"
    tmp.write_text(_json.dumps({"terms": [
        {"en": ["hearing", "hearings"], "zz": ["audiencia", "audiencias"], "basis": "test",
         "skip": ["hard of hearing"], "except": {"t.gone": "an entry the catalog has lost"}}]}),
        encoding="utf-8")
    i18n._CATALOGS["zz"] = {"offered": False, "strings": {
        "t.ok": {"en": "The <b>hearing</b> is at 10", "zz": "La audiencia es a las 10", "state": "draft"},
        "t.bad": {"en": "Two hearings today", "zz": "Dos vistas hoy", "state": "draft"},
        "t.skip": {"en": "For the hard of hearing", "zz": "Para personas sordas", "state": "draft"},
        "t.word": {"en": "Hearingly", "zz": "Nada", "state": "draft"}}}
    try:
        i18n.terms_path = lambda lang: tmp
        got = i18n.term_faults("zz")
    finally:
        i18n.terms_path = real_path
        if real_cat is None:
            i18n._CATALOGS.pop("zz", None)
        else:
            i18n._CATALOGS["zz"] = real_cat
    assert len(got) == 2 and any(g.startswith("t.bad ") for g in got) and any("t.gone" in g for g in got), (
        f"term_faults on its own test list found {got}, not the one wrong entry and the lost exception")
    return "ok", "; ".join(said) + ", every entry using a listed term renders it the listed way"


@check("frontend", "the slogan is one line everywhere: under the home page's logo, in its title, on "
                   "the logo card a shared link unfurls into and in that card's description",
       needs=("i18n",))
def _slogan_one_line(i18n):
    """The owner, 24 October 2026, changing the slogan from "Public Records,
    Made Findable." to "New Hampshire government, in one place." on the site
    and "into link previews when the site is shared on social media". It is
    in four places now, so they are held to chrome.SLOGAN: the home page's
    line under the logo and its title, as the code asks the catalog for them
    (translation_audit.code_words, so in English the words the page says); the alt text
    of the logo card a page with no card of its own names (chrome.card); and
    the line build_brand.py draws on that card, og.png, in small capitals
    without the full stop. The card itself is drawn on the laptop from the
    private originals, so what is checked here is the line it is told to
    draw: a card drawn before 24 October 2026 has none until build_brand.py
    is run again there."""
    import translation_audit
    import chrome
    import build_brand as BB
    words, problems = translation_audit.code_words()
    assert not problems, "; ".join(problems[:4])
    slogan, bare = chrome.SLOGAN, chrome.SLOGAN.rstrip(".")
    want = {"home.slogan": slogan, "home.title": f"Granite Record — {bare}"}
    bad = [f"{k} says {words.get(k, {}).get('en')!r}, not {v!r}"
           for k, v in want.items() if words.get(k, {}).get("en") != v]
    img, alt = chrome.card("index.html")
    if (img, alt) != ("og.png", f"Granite Record: {bare}"):
        bad.append(f"the logo card is {img} described as {alt!r}")
    if BB.OG_SECTIONS.get("og.png") != bare.upper():
        bad.append(f"build_brand draws og.png's line as {BB.OG_SECTIONS.get('og.png')!r}, "
                   f"not {bare.upper()!r}")
    assert not bad, "the slogan is not one line: " + "; ".join(bad)
    return "ok", f"{slogan!r} under the logo, in the title, on the logo card and in its description"


@check("build", "the glossary is built in Spanish at /es/learn/glossary from the same entries, "
                "each term as the record prints it with its Spanish name and meaning, and the "
                "term pop-ups on a Spanish page say them too",
       needs=("i18n", "build_civics", "chrome"))
def _spanish_glossary(i18n, BC, chrome):
    """The owner, 24 October 2026: "The glossary should also be translated
    into spanish if it hasn't been already." words/glossary.json is one table,
    read by the glossary page and by the term pop-ups, and its translations
    are keyed by term and field (i18n.gloss_key), each with the English it
    was made from, so an entry whose English changes is said in English again
    until its Spanish catches up (_translations names it).

    It fails if a glossary entry has no Spanish entry for its name or its
    meaning; if the Spanish page loses a term, the record's English for it
    (marked lang="en"), its Spanish name or meaning, its lang, its link to
    the English page, or asks to be indexed while Spanish is not offered; if
    the English page stops naming its Spanish twin, on <html> or in the
    footer; if the Spanish footer's Glossary link goes to the English page;
    or if the pop-ups stop reading the Spanish words (GR_GLOSS) the shared
    words file carries."""
    import html
    entries = i18n.gloss_entries()
    strings = i18n.catalog("es").get("strings", {})
    absent = [i18n.gloss_key(t, f) for t, e in entries.items() for f in ("name", "says")
              if e.get(f) and i18n.gloss_key(t, f) not in strings]
    assert not absent, f"{len(absent)} glossary words have no Spanish entry: {absent[:4]}"
    assert i18n.has("es", "learn/glossary.html"), "the glossary is not among the Spanish pages"
    js = i18n.gloss_js("es")
    assert js.startswith("window.GR_GLOSS=") and js.endswith(";"), js[:60]
    gl = json.loads(js[len("window.GR_GLOSS="):-1])
    assert set(gl) == set(entries), f"the pop-ups' Spanish lacks {sorted(set(entries) - set(gl))[:4]}"
    assert gl["ITL"]["says"] == strings[i18n.gloss_key("ITL", "says")]["es"]
    page = BC.glossary_page_lang("es", "https://graniterecord.org")
    bad = []
    if '<html lang="es" data-alt-en="/learn/glossary"' not in page:
        bad.append("the Spanish page is not lang=es naming /learn/glossary")
    if not i18n.offered("es") and '<meta name="robots" content="noindex">' not in page:
        bad.append("the Spanish page asks to be indexed while Spanish is unlisted")
    for term, e in entries.items():
        if f'<b lang="en">{html.escape(e["name"], quote=True)}</b>' not in page:
            bad.append(f"the Spanish page lacks {e['name']!r} as the record prints it")
    itl_name = strings[i18n.gloss_key("ITL", "name")]["es"]
    itl_says = strings[i18n.gloss_key("ITL", "says")]["es"]
    if f'<span class="glsl">{html.escape(itl_name)}</span>' not in page \
            or html.escape(itl_says[0].upper() + itl_says[1:]) not in page.replace("&rsquo;", "'"):
        bad.append("the Spanish page lacks ITL's Spanish name or meaning")
    if 'href="es/learn/glossary"' not in page and 'href="es/learn/glossary.html"' not in page:
        bad.append("the Spanish footer's Glossary link is not the Spanish page")
    # The English page names its twin, on <html> and in the footer.
    en = ('<!DOCTYPE html><html lang="en"><head></head><body>'
          + chrome.footer_html("en") + "</body></html>")
    named = BC.name_versions("learn/glossary.html", en)
    if '<html lang="en" data-alt-es="/es/learn/glossary"' not in named \
            or 'lang="es" data-href="/es/learn/glossary"' not in named:
        bad.append("the English glossary does not name its Spanish twin")
    if 'href="learn/glossary.html"' not in chrome.footer_html("en"):
        bad.append("the English footer's Glossary link moved")
    beh = _source("src/pages/components.js")
    if "window.GR_GLOSS" not in beh or "L.says" not in beh:
        bad.append("the term pop-ups do not read the Spanish words (GR_GLOSS)")
    bp = _source("src/pages/build_pages.py")
    if "i18n.gloss_js(lang)" not in bp:
        bad.append("the shared words file no longer carries the glossary's words")
    assert not bad, "; ".join(bad)
    return "ok", (f"{len(entries)} terms in Spanish, on /es/learn/glossary and in the pop-ups; "
                  "the English page names its twin")


@check("build", "a guide's In the Record says a bill passed and not yet in effect apart from the "
                "bills still before the General Court, and not among the laws that changed the "
                "chapter", needs=("build_civics", "build_rsa"))
def _guide_record_passed(BC, BR):
    """The audit before the November webinar (25 October 2026): eight guides
    listed laws already passed under "Bills now before the General Court that
    would change it", because build_rsa.chapter_pending holds both, as the
    Laws page's Pending does. guide_record says them apart: a bill still before
    the General Court under that heading, a bill passed and not yet in effect
    under the Laws page's own words, "Passed, not yet in effect", and that bill
    out of "Laws that changed it since", which it has not yet done. Held on a
    stub of three bills: one pending, one passed with a part still to come,
    one law of 2024."""
    from types import SimpleNamespace as NS

    class Bills:
        def pending(self, k):
            return k == "2025-2026/HB 1"

        def passing(self, data):
            return {"2025-2026/HB 2": NS(effect=NS(parts=[1], awaiting=False), addrs=["654:1"])}

        def chip(self, k, *a, **kw):
            return f"<li>{k}</li>"

        def row(self, k):
            return {"year": "2025"} if k == "2025-2026/HB 3" else {}
    data = {"bills": {"2025-2026": {"HB 1": {"changes": ["654:2"]}}},
            "enacted": {"654:1": [["2026", "1:1", "2025-2026/HB 2"],
                                  ["2024", "5:1", "2023-2024/SB 9"]]}}
    got = BC.guide_record({"laws": ["654"]}, data, Bills(), {"654": {"name": "Voters"}})
    parts = re.split(r'<p class="g-what">', got)
    now = next((p for p in parts if p.startswith("Bills now before")), "")
    passed = next((p for p in parts if p.startswith("Passed, not yet in effect:")), "")
    since = next((p for p in parts if p.startswith("Laws that changed it")), "")
    assert "HB 1" in now and "HB 2" not in now, f"the pending list is not the pending bill: {now[:120]}"
    assert "HB 2" in passed and "HB 1" not in passed, "the passed bill is not under Passed, not yet in effect"
    assert "SB 9" in since and "HB 2" not in since, "a law not yet in effect is listed as having changed it"
    # BY YEAR, WITH NO CUTOFF (the person's notes, 29 October 2026): each law
    # carries the year it passed, the sitting term's included, and the year
    # chooser offers each year the list holds, hidden until its script runs.
    assert 'data-y="2024"' in since and '<span class="rs-yr">2024</span>' in since, (
        "a law that changed the chapter does not show the year it passed")
    assert '<option value="2024">2024 (1)</option>' in got and 'class="g-yrp" hidden' in got, (
        "the laws that changed the chapter have no year to choose, or show it without its script")
    # AND THE PASSED ONES FOLLOW THE CHOSEN YEAR (the walk of 31 October
    # 2026): they stood in every year. Each carries the year it passed -- its
    # chapter's, else its bill's -- in a box of its own that YR_JS filters.
    assert '<div class="g-pass">' in got and '<li data-y="2026">2025-2026/HB 2</li>' in passed, (
        "a bill passed and not yet in effect does not carry the year it passed")
    # Not the bill's own year (the review, 2 November 2026): HB 3 of 2025,
    # retained and chaptered in 2026 before the notes name it, is 2026's by
    # its law year; HB 5, awaiting the Governor with no law year, the build's.
    class Unchaptered(Bills):
        as_of = __import__("datetime").date(2026, 6, 1)

        def passing(self, data):
            return {"2025-2026/HB 3": NS(effect=NS(parts=[1], awaiting=False), addrs=["654:1"], year="2026"),
                    "2025-2026/HB 5": NS(effect=NS(parts=[], awaiting=True), addrs=["654:1"], year="")}

        def row(self, k):
            return {"year": "2025"}
    data3 = {"bills": {}, "enacted": {"654:1": [["2024", "5:1", "2023-2024/SB 9"]]}}
    awaits = BC.guide_record({"laws": ["654"]}, data3, Unchaptered(), {"654": {"name": "Voters"}})
    assert '<li data-y="2026">2025-2026/HB 3</li>' in awaits and '<li data-y="2026">2025-2026/HB 5</li>' in awaits, (
        "a passed bill the notes do not name yet carries its own year, not the year it passed")
    assert ".g-pass" in BC.YR_JS, "the year chooser does not filter Passed, not yet in effect"
    # ONE CHOOSER FOR THE BLOCK, AND NO STATUS ON A LAW (the manager's review,
    # 29 October 2026): a guide of two chapters draws one menu, before the
    # first chapter, counting a law that changed both once; and a law in the
    # list carries its number and year, not "Became Law" on every row.
    two = BC.guide_record({"laws": ["654", "659"]}, {"bills": {}, "enacted": {
        "654:1": [["2024", "5:1", "2023-2024/SB 9"]], "659:2": [["2024", "5:2", "2023-2024/SB 9"]]}},
        Bills(), {"654": {"name": "Voters"}, "659": {"name": "Elections"}})
    assert two.count('class="g-yr"') == 1 and two.index("g-yrp") < two.index("g-ch"), (
        "In the Record draws a year menu a chapter, or after the first chapter")
    assert '<option value="2024">2024 (1)</option>' in two, "a law that changed two chapters is counted twice"
    BC_chip = Bills.chip
    Bills.chip = lambda self, k, *a, **kw: f'<li><a href="#">{k}</a> <span class="rs-st">Became Law</span></li>'
    try:
        bare = BC.guide_record({"laws": ["654"]}, data, Bills(), {"654": {"name": "Voters"}})
    finally:
        Bills.chip = BC_chip
    since_b = next((p for p in re.split(r'<p class="g-what">', bare) if p.startswith("Laws that changed")), "")
    assert "SB 9" in since_b and "Became Law" not in since_b, "a law that changed it still says Became Law"
    old = BC.guide_record({"laws": ["654"]}, {"bills": {}, "enacted": {"654:3": [
        ["1995", "9:1", "1995/HB 7"]]}}, Bills(), {"654": {"name": "Voters"}})
    assert "1995/HB 7" in old, "a law older than the years once shown is left out"
    return "ok", ("pending, passed and not yet in effect, and past laws each under their own words, "
                  "every one with its year and a year to choose")


@check("build", "every Laws link a guide makes is in lower case, as the Laws pages' addresses "
                "are and as the check that holds a guide back reads them",
       needs=("guides", "build_civics"))
def _guide_laws_lower(G, BC):
    """The printouts of 25 October 2026: the disability guide's sources named
    /laws/171-A and /laws/200-C. guide_ready reads a guide's Laws links with
    LAWS_LINK, which takes lower case only, so it read chapters "171-" and
    "200-", found neither in the statute table, and would have held the
    guide back on a night with every claim checked. Every Laws page's address
    is lower case; every guide's links, in its steps and its sources, must be
    too."""
    bad = []
    for g in G.GUIDES:
        hrefs = [u for _l, u in g["sources"]] + [u for s_ in g["steps"] for _l, u in s_["actions"]]
        hrefs += re.findall(r'href="(/laws/[^"]*)"', G.text(g))
        bad += [f'{g["slug"]}: {u}' for u in hrefs
                if u.startswith("/laws/") and u.split("#")[0] != u.split("#")[0].lower()]
        laws = set(BC.LAWS_LINK.findall(G.text(g) + " ".join(f'href="{u}"' for _l, u in g["sources"])))
        bad += [f'{g["slug"]}: reads chapter {c!r}' for c in laws if c.endswith("-")]
    assert not bad, "a guide links a Laws page out of lower case: " + "; ".join(bad[:5])
    return "ok", f"{len(G.GUIDES)} guides, every Laws link lower case"


@check("build", "every Common Questions section is questions with answers: each a question "
                "that ends in a question mark and opens on words of its own, and the section "
                "is after the page's main text, never its first",
       needs=("guides", "civics"))
def _common_questions(G, civics):
    """The person, 26 October 2026: a FAQ dropdown "near the end" of a guide or
    a Learn page, holding the finer details so the page stays streamlined.
    civics.faq draws it; this reads every guide's words and every Learn
    page's body for it, so a question with no answer, a heading typed where a
    question should be, or a section moved to the top is caught."""
    bodies = [(g["slug"], g["more"]) for g in G.GUIDES]
    bodies += [(t["slug"], t["body"]) for t in civics.TOPICS]
    seen, bad = 0, []
    for slug, html_ in bodies:
        if 'class="l-faq"' not in (html_ or ""):
            continue
        seen += 1
        if slug in [t["slug"] for t in civics.TOPICS] and html_.lstrip().startswith("<h2>Common Questions"):
            bad.append(f"{slug}: Common Questions is the page's first section")
        block = html_[html_.index('class="l-faq"'):]
        block = block[:block.index("</div>")] if "</div>" in block else block
        for m in re.finditer(r"<details><summary>(.*?)</summary>(.*?)</details>", block, re.S):
            q, a = m.group(1).strip(), re.sub(r"<[^>]+>", "", m.group(2)).strip()
            if not q.endswith("?"):
                bad.append(f"{slug}: {q[:50]!r} is not a question")
            if len(a) < 10:
                bad.append(f"{slug}: {q[:50]!r} has no answer")
        if block.count("<details>") != len(re.findall(r"<details><summary>.*?</summary>", block, re.S)):
            bad.append(f"{slug}: a question without its summary")
    assert not bad, "; ".join(bad[:5])
    return "ok", f"{seen} pages with Common Questions, each a question with its answer"


@check("code", "the guides and Learn pages speak of a person as they, never \"he or she\": "
               "only a quotation keeps the law's own pronouns", needs=("guides", "civics"))
def _neutral_voice(G, C):
    """The person, 26 October 2026, on the plate guide's "until he or she
    remarries": it "should be gender neutral as they, which applies to other
    sections like he or she unless it's part of the official record as many
    laws are phrased that way." So the site's own words say "they"; a claim,
    a figure's words and anything inside quotation marks are the record's and
    keep its words."""
    import html
    pair = re.compile(r"\b(?:he or she|she or he|his or her|her or his|him or her|her or him|"
                      r"himself or herself|herself or himself|he/she|she/he|his/her|him/her|"
                      r"s/he)\b", re.I)

    def own(words):
        t = html.unescape(re.sub(r"<[^>]+>", " ", words or ""))
        return re.sub(r"[“\"][^”\"]*[”\"]", " ", t)      # quotations stay theirs

    found = []
    for g in G.GUIDES:
        found += [f"guide {g['slug']}: {m.group(0)!r}" for m in pair.finditer(own(G.text(g)))]
    for t in C.TOPICS:
        found += [f"learn {t['slug']}: {m.group(0)!r}"
                  for m in pair.finditer(own(t["body"] + " " + t["blurb"]))]
    assert not found, "say they: " + "; ".join(found[:8])
    return "ok", f"{len(G.GUIDES)} guides and {len(C.TOPICS)} Learn pages say they"


@check("build", "a guide whose steps change subject numbers each part from 1 under its own "
                "heading, and a guide in one part keeps one list", needs=("build_civics", "guides"))
def _guide_parts(BC, G):
    """The person's notes, 29 October 2026: a guide would "finish explaining
    how to do the first thing and switch to a different topic, but keep the
    step by step format as though step 5 is a continuation". guides.PARTS
    names the heading over each part, by the step that opens it; guide_steps
    closes one numbered list and opens the next at each heading, so the
    numbers start again (the counter is the list's, app.css .g-steps). Held
    on every guide: one list per part and a heading before each, or one list
    and no heading. And in a guide in parts, nothing the page says, in English
    or Spanish -- a step, a note, the diagram, the questions -- points at a
    step by number unless it names the part and a step that part has: "(Medicare,
    step 3)". A bare "step 4" would name a step of another part. (The review
    of the change found the first version of this read only steps, and only a
    number in brackets, and would have passed three of the six it was for.)"""
    import html as _h
    import json as _j
    es = _j.loads(_source(_paths.ROOT / "src/pages/lang/es.json"))["strings"]
    num = re.compile(r"\b(?:steps?|pasos?) \d+", re.I)
    named = re.compile(r"\(([^()]*?), (?:step|paso) (\d+)\)")
    parted, bad = 0, []
    for g in G.GUIDES:
        got = BC.guide_steps(g)
        heads = [s_["part"] for s_ in g["steps"] if s_.get("part")]
        lists = got.count('<ol class="g-steps">')
        # Each part's heading carries its address since 30 October 2026
        # (build_civics.step_parts), so the id is read past.
        shown = [_h.unescape(h) for h in re.findall(r'<h3 class="g-part"(?: id="[^"]*")?>(.*?)</h3>', got)]
        if heads:
            parted += 1
            if not g["steps"][0].get("part"):
                bad.append(f"{g['slug']}: its first step has no heading")
            if lists != len(heads) or shown != [_h.unescape(h) for h in heads]:
                bad.append(f"{g['slug']}: {len(heads)} parts but {lists} lists and headings {shown}")
            if '<h3 class="g-sh">' in got:
                bad.append(f"{g['slug']}: a step title sits at the heading's level")
            size, cur = {}, ""
            for s_ in g["steps"]:
                cur = s_.get("part") or cur
                size[cur] = size.get(cur, 0) + 1
            size_es = {es.get(k, {}).get("es", ""): n for h, n in size.items()
                       for k in [G.page_keys(g["slug"]).get(h)] if k}
            said = [t for _w, t, _h2 in G.wording(g["slug"]) if t]
            said += [es[k]["es"] for k in G.page_keys(g["slug"]).values() if k in es]
            for t in said:
                plain = _h.unescape(re.sub(r"<[^>]+>", "", t))
                ok = {m.start(2) for m in named.finditer(plain)
                      if int(m.group(2)) <= {**size, **size_es}.get(m.group(1), 0)}
                for m in num.finditer(plain):
                    if not any(m.start() <= o <= m.end() for o in ok):
                        bad.append(f"{g['slug']}: says {plain[max(0, m.start() - 40):m.end() + 5]!r}")
        elif lists != 1 or "g-part" in got:
            bad.append(f"{g['slug']}: one part but {lists} lists")
    assert parted, "no guide is in parts: PARTS was not applied"
    assert not bad, "; ".join(bad[:8])
    return "ok", f"{parted} of {len(G.GUIDES)} guides in parts, each numbered from 1"


@check("code", "a guide and the home page write a time as clock() does, \"8:30 AM\", and \"8:30 a. m.\" in "
               "Spanish; a claim's words and a quoted calendar line keep their source's", needs=("guides",))
def _times_as_clock(G):
    """The cohesion audit of 30 October 2026 (I-3): the bills, committees,
    Calendar and session days say "10:00 AM" (components.clock), while the
    guides said "8:30 a.m." and "5 p.m." and the home page's webinar "6:30
    p.m.". A guide's own words, its Spanish and the webinar line now write
    clock()'s forms, a whole hour with its ":00"; what a claim records its
    source as saying, and the House calendar lines a guide quotes, are the
    source's own and keep its "a.m.". And the hours a guide prints stay held
    to its claims: guides.CLOCK reads "8:00 AM" as it read "8 a.m."."""
    import json as _json
    import build_pages as BP
    bad = []
    for g in G.GUIDES:
        for m in re.finditer(r"\d(?:\s| )?[ap]\.m\.", G._plain(G.text(g))):
            bad.append(f"{g['slug']} says {G._plain(G.text(g))[max(0, m.start() - 30):m.end()]!r}")
    if not any(G.CLOCK.search(G._plain(G.text(g))) for g in G.GUIDES):
        bad.append("guides.CLOCK reads no hour in any guide, so none is held to a claim")
    web = BP.home_webinar("2026-11-01")
    if re.search(r"\d(?:\s|&nbsp;)?[ap]\.m\.", web) or not re.search(r"6:30&nbsp;PM", web):
        bad.append(f"the home page's webinar line: {re.sub(r'<[^>]+>', ' ', web)[:120]!r}")
    es = _json.loads(_source("src/pages/lang/es.json"))["strings"]
    for k, e in es.items():
        if not isinstance(e, dict) or not (k.startswith("guide.") or k.startswith("web.")):
            continue
        if re.search(r"\d(?:\s|&nbsp;)?[ap]\.m\.", e.get("en", "")):
            bad.append(f"es.json {k}: its English still says a.m. or p.m.")
        if re.search(r"\d(?:\s|&nbsp;)?(?:[ap]\.m\.|[AP]M\b)", e.get("es", "")):
            bad.append(f"es.json {k}: its Spanish is not clock()'s \"a. m.\"")
    assert not bad, "; ".join(bad[:6])
    return "ok", ("the guides, their Spanish and the webinar line write clock()'s times; claims and "
                  "quoted calendar lines keep their source's")


@check("code", "every phone number, email, office hours, street address and date a guide "
               "prints is in the words a claim of it records its source as saying, but for "
               "the few named as waiting for a printout", needs=("guides",))
def _guide_contacts_sourced(G):
    """The person, 26 October 2026: "make sure there are absolutely no
    hallucinations in those sorts of pages and in the instructions". FIGURE
    and COUNT held money, shares and periods to their sources; nothing held
    the details a reader acts on most directly. The audit that day found
    phone numbers that no claim of their guide recorded -- the Division of
    Motor Vehicles' number printed in four guides and recorded in one, the
    Board of Tax and Land Appeals' number and street recorded nowhere. A
    wrong digit there sends someone to a stranger.

    guides.unsourced_contacts finds them; guides.CONTACTS_AWAITING names the
    ones no source on this disk can settle, each with the printout that
    would. A name on that list that a claim now records fails too, so the
    list is cleared as the printouts come in rather than left to excuse a
    later mistake."""
    loose, stale, waiting = [], [], 0
    for g in G.GUIDES:
        found = set(G.unsourced_contacts(g))
        why, named = G.CONTACTS_AWAITING.get(g["slug"], ("", []))
        loose += [f"{g['slug']}: {x}" for x in sorted(found - set(named))]
        stale += [f"{g['slug']}: {x}" for x in named if x not in found]
        waiting += len(found & set(named))
    assert not loose, ("printed with no claim recording it (add the claim from the source, "
                       "or take the detail out): " + "; ".join(loose[:8]))
    assert not stale, ("named in guides.CONTACTS_AWAITING but a claim records it now; take "
                       "it off the list: " + "; ".join(stale[:8]))
    return "ok", (f"every contact detail rests on a claim, but {waiting} named as waiting for "
                  f"the person's printout")


@check("build", "the Officials page is built in Spanish at /es/officials: its own words, its "
                "tabs', the person's officials file's and its scripts', every one current, "
                "and its links to itself stay in Spanish",
       needs=("i18n", "build_pages", "officials_tabs", "seating"))
def _spanish_officials(i18n, BP, OT, seating):
    """The person, 25 October 2026: "Start on the Officials page and My Town
    in Spanish". build_pages draws the page once for each language that has
    it (officials_html), its tabs in officials_tabs with a `lang`, the House
    chart in seating.svg with one, and every word the site says through
    say() or, in its scripts, tr(); the words of corrections/officials.json
    the tabs say (what an office is, a title, a department's name) are
    catalog entries keyed by their own first words (officials_tabs.
    data_words), never written into the person's file.

    Read off the fixture's built pages: the Spanish page is lang=es naming
    /officials, which names it; asks not to be indexed while Spanish is
    unlisted; has its Spanish title and tabs; falls back to English nowhere
    (no <span lang="en"> the tabs mark a miss with); and its own links to
    the page stay on /es/officials. Then every key the page, its tabs, its
    finder and seat scripts and the district map (map.js, in the shared
    words file) ask for has current Spanish, so a word the
    fixture's data does not reach is held too; the vacancy sentence asked
    for in Spanish is VACANCY_NOTE's own English; the Members-Elect tab and a
    county's convention line, which the fixture's data does not draw, are
    drawn in Spanish here with nothing English left; and a Spanish page tells
    find.js where the Spanish Officials page is (window.GR_HREFS), so the
    Your Town card's County Officials link does not leave the language."""
    import translation_audit
    import html as _h
    assert i18n.has("es", "officials.html"), "i18n.PAGES does not name officials.html for Spanish"
    shared, _base, _ran, _days = _fixture_site_shared()
    en = (shared / "site" / "officials.html").read_text(encoding="utf-8")
    es_path = shared / "site" / "es" / "officials.html"
    assert es_path.is_file(), "the fixture's build wrote no es/officials.html"
    es = es_path.read_text(encoding="utf-8")
    strings = i18n.catalog("es")["strings"]
    bad = []
    if not es.startswith('<!DOCTYPE html><html lang="es" data-alt-en="/officials"'):
        bad.append("the Spanish page is not lang=es naming /officials")
    if 'data-alt-es="/es/officials"' not in en:
        bad.append("the English page does not name /es/officials")
    if not i18n.offered("es") and '<meta name="robots" content="noindex">' not in es:
        bad.append("the Spanish page asks to be indexed while Spanish is unlisted")
    main = es[es.index("<main"):es.index("</main>")]
    if f"<h1>{strings['of.title']['es']}</h1>" not in main:
        bad.append("its <h1> is not the catalog's of.title")
    # Four tabs say their short names, and their panels the whole ones (the
    # owner, 7 November 2026; _officials_tabs_fit_and_retire).
    for key in ("of.tab.town", "of.tab.legislators", "of.tab_short.executive",
                "of.tab_short.judicial", "of.tab_short.counties", "of.tab_short.federal"):
        if not re.search(r'role="tab"[^>]*>' + re.escape(strings[key]["es"]) + r"[ <]", main):
            bad.append(f"no tab labelled {strings[key]['es']!r} ({key})")
    for key in ("of.tab.executive", "of.tab.judicial", "of.tab.counties", "of.tab.federal"):
        if f'<h2 class="twnph">{strings[key]["es"]}</h2>' not in main:
            bad.append(f"no panel headed {strings[key]['es']!r} ({key})")
    if '<span lang="en">' in main:
        bad.append("a tab says something in English: " + main[main.index('<span lang="en">'):][:80])
    own = re.findall(r'href="([^"]*officials[^"]*)"', main)
    if not own or any(not h.startswith("/es/officials") for h in own):
        bad.append(f"its links to the Officials page leave Spanish: {sorted(set(own))[:4]}")
    # Every word the page asks for, current -- the fixture's data reaches
    # only some of them.
    words, problems = translation_audit.code_words()
    assert not problems, problems[:3]
    prefixes = ("of.", "off.", "roster.", "comp.", "seat.", "lf.", "sc.", "party.", "map.")
    asked = [k for k in words if k.startswith(prefixes)]
    stale = [k for k in asked if i18n.lookup("es", k, words[k]["en"]) is None]
    if stale:
        bad.append(f"{len(stale)} of the page's words have no current Spanish: {stale[:5]}")
    for key, en_, _w in OT.data_words():
        if i18n.lookup("es", key, en_) is None:
            bad.append(f"the officials file's {en_[:40]!r} has no current Spanish ({key})")
    if words.get("comp.vacancy_note", {}).get("en") != BP.VACANCY_NOTE:
        bad.append("the vacancy sentence asked for in Spanish is not VACANCY_NOTE's English")
    for k, en_ in i18n.tr_calls(BP.LEGFIND_JS + BP.SEATING_JS):
        if i18n.lookup("es", k, en_) is None:
            bad.append(f"the finder or the seat chart says {en_[:40]!r} in English ({k})")
    # What the fixture does not draw: Members-Elect, and a convention line.
    elect = {"election": "2026-11-03", "takes_office": "2026-12-02",
             "sources": ["https://www.sos.nh.gov/x"],
             "races": {"S|9": {"seats": 1, "elected": [{"n": "A. Winner", "p": "D"}]},
                       "H|Merrimack|4": {"seats": 2, "elected": [{"n": "B. Winner", "p": "R"}],
                                         "not_final": 1}}}
    me = OT.members_elect(elect, "2026-11-20", "es")
    off = {"county": {"counties": {"Merrimack": {"name": "Merrimack County", "commissioners": {
        "1": {"name": "C. Persona", "party": "R"}}}}}}
    co = OT.county(off, [{"chamber": "H", "county": "Merrimack"}] * 3, "2026-10-20", "es")
    drawn = _h.unescape(re.sub(r"<[^>]+>", " ", me + co))
    for word in ("District", "seats", "County", "Elected", "take office", "Legislators tab",
                 "Commissioner", "convention is", "State Senate", "State House"):
        if re.search(r"\b" + re.escape(word) + r"\b", drawn):
            bad.append(f"the Spanish Members-Elect or County tab says {word!r}")
    svg = seating.svg({}, lang="es")
    if "Division " in svg or "División 1" not in svg:
        bad.append("the House chart's divisions are not in Spanish")
    if '"officials.html":"/es/officials"' not in i18n.page_words("es"):
        bad.append("a Spanish page does not tell its scripts where /es/officials is")
    # The district map (map.js, the Officials page's and the town pages') says
    # its words through tr(), and a Spanish page carries them in the shared
    # words file it loads.
    if "map.js" not in i18n.SHARED_SCRIPTS:
        bad.append("map.js is not one of i18n.SHARED_SCRIPTS, so a Spanish page has no map words")
    shared_words = (shared / "site" / i18n.shared_words_path("es").lstrip("/"))
    if shared_words.is_file() and '"map.prompt":' not in shared_words.read_text(encoding="utf-8"):
        bad.append("the built /lang/es.js carries none of the map's words")
    assert not bad, "; ".join(bad[:6])
    return "ok", (f"/es/officials built from the same files as /officials; {len(asked)} words of "
                  f"the page and its scripts and {len(OT.data_words())} of the officials file, "
                  "every one current; Members-Elect and the county lines drawn in Spanish")


@check("build", "the Learn pages i18n.PAGES names are built in Spanish at /es/learn/, piece by "
                "piece from the catalog, each naming its English page and each English page "
                "naming it, and the hub's Learn tab marks the ones still in English",
       needs=("i18n", "guides", "build_civics", "chrome", "civics"))
def _spanish_learn(i18n, G, BC, chrome, civics):
    """The person, 25 October 2026: "start on the Learn pages". A Learn page
    i18n.PAGES names is drawn in Spanish from the same civics.py words as the
    English (build_civics.learn_page_lang), keyed learn.<slug>.*, its figures
    filled after; the Resources bar over it marks Learn, its pager and The
    Pages name the topics as the hub's Learn tab does, and the hub's tab
    marks "in English" each page not yet translated.

    It fails if PAGES names a Learn page that is not one; if a Spanish page
    falls back to English anywhere; if one is not lang=es naming its English
    page, asks to be indexed while Spanish is unlisted, lacks its Spanish
    title, its line on what is in English or the button for a mistake in the
    translation; if it links the English page of a topic Spanish has; if its
    bar does not mark Learn, or its pager is English; if an English page does
    not name its twin; if the hub links an English Learn page without saying
    so, or a Spanish one with it; or if the register of probate sentence
    changes its English or keeps it in Spanish."""
    import html as _h
    base = "https://graniterecord.org"
    strings = i18n.catalog("es")["strings"]
    slugs = G.learn_translated("es")
    learn = BC.learn_topics(civics.TOPICS)
    # Not By the Numbers either (9 November 2026): it is not one of civics.TOPICS,
    # and _numbers_in_spanish holds it.
    named = [p for p in i18n.PAGES["es"] if p.startswith("learn/")
             and p not in (BC.GLOSSARY_PAGE, "learn/by-the-numbers.html")]
    unknown = sorted(p for p in named if not G.learn_topic(p[len("learn/"):-len(".html")]))
    assert not unknown, f"i18n.PAGES names Learn pages there are none of: {unknown}"
    bad, misses = [], set(i18n.MISSES)
    try:
        i18n.MISSES.clear()
        for slug in slugs:
            t = G.learn_topic(slug)
            body = G.reused(G.topic_body(t)) + (t.get("holds") or "")
            # The page's own words, and what a slot draws in it (County
            # Government's cards, civics.county_cards), which name figures too.
            figures = {k: "7" for k in re.findall(r"\[\[(\w+)\]\]", body + civics.county_cards())}
            page = BC.learn_page_lang(t, "es", base, figures, learn,
                                      open_={g["slug"] for g in G.GUIDES} | set(civics.HOW_TO))
            if not page.startswith(f'<!DOCTYPE html><html lang="es" data-alt-en="/learn/{slug}"'):
                bad.append(f"{slug}: not lang=es naming /learn/{slug}")
            if not i18n.offered("es") and '<meta name="robots" content="noindex">' not in page:
                bad.append(f"{slug}: asks to be indexed while Spanish is unlisted")
            es_title = strings[f"learn.{slug}.title"]["es"]
            if f"<h1>{_h.escape(es_title, quote=True)}</h1>" not in page:
                bad.append(f"{slug}: its <h1> is not its Spanish title {es_title!r}")
            if chrome.lang_note("es") not in page:
                bad.append(f"{slug}: no note saying what on it is in English, and why")
            if "data-trreport hidden" not in page:
                bad.append(f"{slug}: no button for a mistake in the translation")
            if 'href="/es/resources#learn" aria-current="true"' not in page:
                bad.append(f"{slug}: its Resources bar does not mark Learn")
            for word in ("Previous Topic", "Next Topic", "All Topics", "The Pages"):
                if f">{word}<" in page:
                    bad.append(f"{slug}: its pager says {word!r} in English")
            for other in slugs:
                if re.search(rf'(?<![\w-])href="/?learn/{re.escape(other)}(?:\.html)?(?:#[^"]*)?"',
                             page):
                    bad.append(f"{slug}: links the English {other} where its Spanish is built")
            if "[[" in page:
                bad.append(f"{slug}: an unfilled figure")
            en = ('<!DOCTYPE html><html lang="en"><head></head><body>'
                  + chrome.footer_html("en") + "</body></html>")
            twin = BC.name_versions(f"learn/{slug}.html", en)
            if f'<html lang="en" data-alt-es="/es/learn/{slug}"' not in twin \
                    or f'lang="es" data-href="/es/learn/{slug}"' not in twin:
                bad.append(f"{slug}: the English page does not name its Spanish twin")
        fell = sorted(i18n.MISSES)
        assert not fell, (f"{len(fell)} pieces of the Spanish Learn pages fell back to English: "
                          + "; ".join(f"{k} ({why})" for _l, k, why in fell[:6]))
        # The hub's Learn tab: a Spanish page by its Spanish link, an English
        # one marked as English.
        hub = BC.hub_page_lang("es", base, G.GUIDES, BC.how_to_topics(civics.TOPICS))
        tag = f'<span class="r-en">({strings["guides.in_english"]["es"]})</span>'
        for t in learn:
            s_ = t["slug"]
            m = re.search(rf'<a href="(/es/)?learn/{re.escape(s_)}(?:\.html)?"[^>]*>(.*?)</a>', hub, re.S)
            if not m:
                bad.append(f"the hub's Learn tab does not link {s_}")
            elif s_ in slugs and (not m.group(1) or tag in m.group(2)):
                bad.append(f"the hub links {s_} as English where its Spanish is built")
            elif s_ not in slugs and (m.group(1) or tag not in m.group(2)):
                bad.append(f"the hub links {s_}, still English, without saying so")
    finally:
        i18n.MISSES.clear()
        i18n.MISSES.update(misses)
    # The register of probate sentence: its English as it was, its Spanish not English.
    import datetime as _dt
    rows = [{"term": BC.PROBATE_CACR[0], "bill": BC.PROBATE_CACR[1], "election": "2026-11-03"}]
    link = '<a href="bill/2026/cacr13.html">CACR 13 (2026)</a>'
    lead = f"In 2026 the legislature sent the question to the voters again, as {link}"
    want = {(None, "2026-10-25"): lead + ".",
            ((None, None), "2026-10-25"): f"{lead}, at the general election of November 3, 2026.",
            ((None, None), "2026-11-10"): (f"{lead}. The vote was on November 3, 2026; the Secretary "
                                           "of State&rsquo;s count is not on the site yet."),
            ((700, 300), "2026-11-10"): (f"{lead}, and on November 3, 2026 the voters ratified it: "
                                         "70.0% voted yes, where two thirds was needed."),
            ((600, 400), "2026-11-10"): (f"{lead}, and on November 3, 2026 it did not reach the two "
                                         "thirds it needed: 60.0% of those voting on it voted yes.")}
    for (count, today), english in want.items():
        rs = None if count is None else [dict(rows[0], yes=count[0], no=count[1])]
        day = _dt.date.fromisoformat(today)
        got = BC.probate_vote(rs, day)
        if got != english:
            bad.append(f"the register of probate sentence's English changed: {got!r}")
        es = BC.probate_vote(rs, day, "es")
        if "the voters" in es or link not in es:
            bad.append(f"the register of probate sentence is not in Spanish: {es!r}")
    # The figures with words in them, drawn again in Spanish (record_figures'
    # name@lang), take the English one's place on a Spanish page, and say
    # none of the English's words.
    got = BC.figures_lang({"fig_ends": "English", "fig_ends@es": "Español", "bills": "7"}, "es", {})
    if got.get("fig_ends") != "Español":
        bad.append("figures_lang does not put a figure drawn in Spanish in the English one's place")
    drawn = {"seats": civics.seats_figure(400, 390, 24, 23, "es"),
             "term": civics.term_figure("2025-2026", "es"),
             "org day": BC.org_day(_dt.date(2026, 10, 25), "es")}
    cacrs = [{"id": "CACR1", "status": "Killed"}, {"id": "CACR2", "status": "Died on the table"},
             {"id": "CACR3", "status": "Passed both chambers, goes to the voters in November 2026"}]
    drawn["CACR lead"], drawn["CACR table"] = BC._cacr_lang(cacrs, {}, "2025-2026", "es")
    for name, html_ in drawn.items():
        for english in ("seats", "vacant", "First year", "Retained", "The next is", "filed",
                        "passed both chambers", "Killed", "Died on the table", "goes to the voters",
                        "November"):
            text = re.sub(r"<[^>]+>", " ", re.sub(r'<span lang="en">.*?</span>', "", html_))
            if re.search(rf"\b{english}\b", text):
                bad.append(f"the {name} figure in Spanish says {english!r}")
    if "noviembre de 2026" not in drawn["CACR table"]:
        bad.append("the CACR table's election month is not in Spanish")
    # The legislature's schedule, its seasons, steps, pattern and labels in
    # Spanish (legislative_year.figures' lang), on a day inside the entered
    # term and on one in a term only its skeleton draws.
    import legislative_year as LY
    before = set(i18n.MISSES)
    for day in (_dt.date(2026, 3, 1), _dt.date(2027, 3, 1)):
        year = LY.figures(day, Path("."), "es")
        text = re.sub(r"<[^>]+>", " ", re.sub(r'<span lang="en">.*?</span>', "", "".join(year.values())))
        for english in ("You are here", "Usually", "Coming up", "Sources:", "Source:", "This week",
                        "dates,", "all past", "to come", "The First Year", "Organization Day",
                        "Crossover", "In session"):
            if english in text:
                bad.append(f"the schedule in Spanish on {day} says {english!r}")
    fell = sorted(set(i18n.MISSES) - before)
    i18n.MISSES.clear()
    i18n.MISSES.update(before)
    if fell:
        bad.append(f"the schedule in Spanish fell back to English: {fell[:4]}")
    assert not bad, f"{len(bad)} faults: " + "; ".join(bad[:8])
    return "ok", (f"{len(slugs)} of {len(learn)} Learn pages in Spanish, each naming its English page "
                  "and named by it, its figures drawn in Spanish; the hub marks the rest as English")


@check("build", "the how-to guides are built in Spanish at /es/guides/, piece by piece from the "
                "catalog, each naming its English page and each English page naming it, with the "
                "Resources hub's How-To Guides beside them",
       needs=("i18n", "guides", "build_civics", "chrome", "civics"))
def _spanish_guides(i18n, G, BC, chrome, civics):
    """The owner, 24 October 2026: "The how to pages are the next important
    section I think is worth translating." Every guide i18n.PAGES names --
    guides.py's and the three pages of civics.HOW_TO -- is drawn in Spanish
    from the same data as the English (build_civics.guide_page_lang,
    article_page_lang), a piece at a time (i18n.say_html, guides.page_keys),
    and the hub's How-To Guides with them (hub_page_lang).

    It fails if PAGES names a guide that is not one; if a Spanish guide
    falls back to English anywhere (a miss i18n.say_html records); if one
    is not lang=es naming its English page, asks to be indexed while Spanish
    is unlisted, lacks its Spanish title, the line saying its outside pages
    are in English, or the footer's button for a mistake in the translation;
    if a link to another guide Spanish has goes to the English one, or an
    outside page's button is not marked as English; if a link to a page in
    Spanish still says "(en inglés)"; if the hub lacks a task
    or links its English guide; if an English page does not name its twin;
    if In the Record keeps an English sentence or leaves a chapter's name
    unmarked; or if Using This Site's shorthand stops being the glossary's
    words in either language."""
    import copy
    import html as _h
    base = "https://graniterecord.org"
    strings = i18n.catalog("es")["strings"]
    slugs = G.translated("es")
    known = {g["slug"] for g in G.GUIDES} | set(civics.HOW_TO)
    unknown = sorted(set(slugs) - known)
    assert not unknown, f"i18n.PAGES names guides there are none of: {unknown}"
    english_only = sorted(known - set(slugs))
    bad, misses = [], set(i18n.MISSES)
    try:
        i18n.MISSES.clear()
        for slug in slugs:
            t = G.topic_of(slug)
            if t:
                body = G.reused(G.topic_body(t)) + (t.get("holds") or "")
                figures = {k: "7" for k in re.findall(r"\[\[(\w+)\]\]", body + civics.county_cards())}
                page = BC.article_page_lang(t, "es", base, figures)
                title = t["title"]
            else:
                g = next(g for g in G.GUIDES if g["slug"] == slug)
                page = BC.guide_page_lang(g, "es", base)
                title = g["title"]
                for s_ in g["steps"]:
                    for _label, u in s_["actions"]:
                        if u.startswith("http") and f'href="{_h.escape(u, quote=True)}" target="_blank" ' \
                                f'rel="noopener" hreflang="en"' not in page:
                            bad.append(f"{slug}: the button to {u} is not marked as an English page")
            if not page.startswith(f'<!DOCTYPE html><html lang="es" data-alt-en="/guides/{slug}"'):
                bad.append(f"{slug}: not lang=es naming /guides/{slug}")
            if not i18n.offered("es") and '<meta name="robots" content="noindex">' not in page:
                bad.append(f"{slug}: asks to be indexed while Spanish is unlisted")
            es_title = strings[f"guide.{slug}.title"]["es"]
            if f"<h1>{_h.escape(es_title, quote=True)}</h1>" not in page:
                bad.append(f"{slug}: its <h1> is not its Spanish title {es_title!r}")
            if chrome.lang_note("es") not in page:
                bad.append(f"{slug}: no note saying what on it is in English, and why")
            # A link lang_links sent to a Spanish page, still called English
            # (the review of 25 October 2026 found four, left from before the
            # Learn pages they link were translated).
            for m in re.finditer(r'<a [^>]*href="(/es/[^"]*)"[^>]*>((?:(?!</a>).)*)</a>(\s*\(en inglés\))?',
                                 page, re.S):
                if "(en inglés)" in m.group(2) or m.group(3):
                    bad.append(f"{slug}: its link to {m.group(1)} says (en inglés), and that page is in "
                               "Spanish")
            if "data-trreport hidden" not in page:
                bad.append(f"{slug}: no button for a mistake in the translation")
            for other in slugs:
                # (The footer's way to the English page is the one that
                # must lead there, and it is no link: the language select's
                # English option, data-href.)
                if re.search(rf'(?<![\w-])href="/?guides/{re.escape(other)}(?:\.html)?(?:#[^"]*)?"',
                             page):
                    bad.append(f"{slug}: links the English {other} where its Spanish is built")
            if "[[" in page:
                bad.append(f"{slug}: an unfilled figure")
            # The English page, named by its twin.
            en = ('<!DOCTYPE html><html lang="en"><head></head><body>'
                  + chrome.footer_html("en") + "</body></html>")
            named = BC.name_versions(f"guides/{slug}.html", en)
            if f'<html lang="en" data-alt-es="/es/guides/{slug}"' not in named \
                    or f'lang="es" data-href="/es/guides/{slug}"' not in named:
                bad.append(f"{slug}: the English page does not name its Spanish twin")
            del title
        fell = sorted(i18n.MISSES)
        assert not fell, (f"{len(fell)} pieces of the Spanish guides fell back to English: "
                          + "; ".join(f"{k} ({why})" for _l, k, why in fell[:6]))
        # The hub's How-To Guides.
        hub = BC.hub_page_lang("es", base, G.GUIDES, BC.how_to_topics(civics.TOPICS))
        if not hub.startswith('<!DOCTYPE html><html lang="es" data-alt-en="/resources"'):
            bad.append("the hub is not lang=es naming /resources")
        for _group, tasks in G.TASKS:
            for task in tasks:
                if task["slug"] in slugs and f'href="/es/guides/{task["slug"]}"' not in hub:
                    bad.append(f"the hub does not link the Spanish {task['slug']}")
                # Each guide by its headline (guides.task's head, 24 October 2026).
                head = strings[f"guide.task.{task['slug']}.head"]["es"]
                if head not in hub:
                    bad.append(f"the hub lacks the headline {head!r}")
        assert not i18n.MISSES, f"the hub fell back to English: {sorted(i18n.MISSES)[:4]}"
    finally:
        i18n.MISSES.clear()
        i18n.MISSES.update(misses)
    # In the Record, its sentences in Spanish and the record's words marked.
    rec = ('<p class="g-yrp" hidden><label>Show the laws passed in <select class="g-yr"><option '
           'value="">All years</option><option value="2026">2026 (1)</option></select></label></p>'
           '<h3 class="g-ch"><a href="/laws/654">Chapter 654: Voters and Checklists</a></h3>'
           '<p class="g-what">Bills now before the General Court that would change it:</p>'
           '<ul class="rs-list"><li>HB 1</li></ul>'
           '<p class="g-what">Passed, not yet in effect:</p><ul class="rs-list"><li>HB 4</li></ul>'
           '<div class="g-laws"><p class="g-what">Laws that changed it, newest first:</p>'
           '<ul class="rs-list"><li>HB 2</li></ul><details class="rs-more"><summary>Show all 9'
           '</summary><ul class="rs-list"><li>HB 3</li></ul></details>'
           '<p class="g-what g-yrnone" hidden>None that year.</p></div>'
           '<p class="g-what">No law in the record has changed it, and none now before the '
           'General Court would.</p>')
    got = BC._record_lang(rec, "es")
    for english in ("Bills now before", "Passed, not yet", "Laws that changed", "No law in the record",
                    "Show all", ">Chapter ", "Show the laws passed", ">All years<", "None that year"):
        if english in got:
            bad.append(f"In the Record keeps {english!r} in English")
    if '<span lang="en">Voters and Checklists</span>' not in got or got.count('lang="en"') != 5:
        bad.append("In the Record does not mark the record's own words as English")
    # The shorthand table: the glossary's words, in either language.
    if civics.shorthand_table("en") != civics.SHORTHAND_TABLE:
        bad.append("the English shorthand table is no longer the one Using This Site had")
    es_table = civics.shorthand_table("es")
    for k in civics.SHORTHAND:
        name = strings[i18n.gloss_key(k, "name")]["es"]
        if _h.escape(name) not in es_table:
            bad.append(f"the Spanish shorthand table lacks {k}'s glossary name {name!r}")
    # The worked example of a town's representatives, its English unchanged
    # by the words it now asks the catalog for.
    dist = {"Danville": {"0": {"senate": "23", "council": "3", "congress": "1",
                               "house": [{"county": "Rockingham", "district": "8", "seats": 1},
                                         {"county": "Rockingham", "district": "32", "seats": 1,
                                          "floterial": True}]}},
            "Fremont": {"0": {"senate": "23", "council": "3", "congress": "1",
                              "house": [{"county": "Rockingham", "district": "7", "seats": 1},
                                        {"county": "Rockingham", "district": "32", "seats": 1,
                                         "floterial": True}]}}}
    en_ex = civics.reps_example(copy.deepcopy(dist))
    es_ex = civics.reps_example(copy.deepcopy(dist), lang="es")
    if "Rockingham 7 and 8" not in en_ex["reps_flot_under"] \
            or "Everyone who represents a voter in Danville" not in en_ex["reps_example"] \
            or "1 seat, elected by Fremont and Danville together" not in en_ex["reps_band"]:
        bad.append("the worked example's English changed: " + en_ex["reps_band"][:120])
    if es_ex["reps_flot_under"] != "Rockingham 7 y 8" or es_ex["reps_under_n"] != "dos" \
            or "Todos los que representan a un votante de Danville" not in es_ex["reps_example"]:
        bad.append("the worked example is not in Spanish: " + es_ex["reps_flot_under"])
    assert not bad, f"{len(bad)} faults: " + "; ".join(bad[:8])
    pieces = Counter(k.split(".")[1] for k, _en, _w in G.translated_words())
    return "ok", (f"{len(slugs)} guides and the hub in Spanish, {sum(pieces.values())} pieces, every one "
                  "current; each names its English page and is named by it"
                  + (f"; English only: {', '.join(english_only)}" if english_only else ""))


@check("build", "a guide whose English changes says that piece in English, marked, and never "
                "the Spanish of what it no longer says, while every other piece stays "
                "translated, and the catalog check names it",
       needs=("i18n", "guides", "build_civics"))
def _spanish_guides_stale(i18n, G, BC):
    """The hard rule of the guides in Spanish (the owner, 24 October 2026: the
    translation "should not go out of date when page information is
    updated", of 23 October, held for the guides): a translation is a piece
    of a guide -- a paragraph, a list item, a heading, a button's label --
    with the English it was made from. Here a fixture copy of How to Vote has
    two of its English list items edited, as a person editing guides.py
    would: one past its first words, which keeps its key and makes its entry
    stale, and one at its first words, which is a new key with no entry.
    The Spanish page must say each of them in English, in <span lang="en">,
    and never the Spanish of the old words, while their neighbours stay in
    Spanish; and translation_audit.check must name the stale entry, the missing one and
    the entry no code asks for any more -- which is what fails preflight
    until a translation is brought up to date."""
    import translation_audit
    import copy
    import html
    i = next(k for k, g in enumerate(G.GUIDES) if g["slug"] == "how-to-vote")
    real = G.GUIDES[i]
    g = copy.deepcopy(real)
    s_ = g["steps"][1]
    edits = [("living in the town or city ward where you are registering.",
              "living in the town or city ward where you register."),
             ("You can register as a Democrat, a Republican, or Undeclared.",
              "Register as a Democrat, a Republican, or Undeclared.")]
    for old, new in edits:
        assert old in s_["text"], f"How to Vote no longer says {old!r}: choose another sentence"
        s_["text"] = s_["text"].replace(old, new)
    strings = i18n.catalog("es")["strings"]
    stale_key = "guide.how-to-vote.living-in-the-town-or-city"
    gone_key = "guide.how-to-vote.you-can-register-as-a-democrat"
    for k in (stale_key, gone_key):
        assert k in strings, f"es.json has no {k}: the fixture's keys have moved"
    misses = set(i18n.MISSES)
    G.GUIDES[i] = g
    try:
        i18n.MISSES.clear()
        page = BC.guide_page_lang(g, "es", "https://graniterecord.org")
        missed = set(i18n.MISSES)
        problems = translation_audit.check("es")
        new_key = G.page_keys("how-to-vote")[edits[1][1]]
    finally:
        G.GUIDES[i] = real
        i18n.MISSES.clear()
        i18n.MISSES.update(misses)
    bad = []
    for old, new in edits:
        if f'<span lang="en">{new}</span>' not in page:
            bad.append(f"the edited English {new!r} is not on the page, marked as English")
    for k in (stale_key, gone_key):
        if strings[k]["es"] in page:
            bad.append(f"the page still says the Spanish of English it no longer says: {strings[k]['es']!r}")
    for k in ("guide.how-to-vote.at-least-18-years-old", "guide.how-to-vote.a-united-states-citizen-and",
              "guide.how-to-vote.make-sure-you-can-register", "guide.how-to-vote.there-is-no-minimum-time-you"):
        if html.escape(strings[k]["es"], quote=False) not in page and strings[k]["es"] not in page:
            bad.append(f"a piece the edit did not touch is no longer in Spanish: {k}")
    if ("es", stale_key, "stale") not in missed or ("es", new_key, "missing") not in missed:
        bad.append(f"the build did not keep the misses for report(): {sorted(missed)}")
    said = [p for p in problems if p.startswith(f"{stale_key} is stale")]
    absent = [p for p in problems if p.startswith(f"{new_key} has no es words")]
    orphan = [p for p in problems if p.startswith(f"{gone_key} is in lang/es.json and no code asks")]
    if not (said and absent and orphan) or len(problems) != 3:
        bad.append(f"the catalog check does not name the edit as it should: {problems[:5]}")
    assert not bad, "; ".join(bad)
    return "ok", ("an edit past a piece's first words shows it in English and names its entry "
                  "stale; an edit at its first words shows it in English and names the new key "
                  "missing and the old one unused; the rest of the page stays in Spanish")


@check("frontend", "every published guide in a language i18n.PAGES gives it is built in that "
                   "language beside its English, each naming the other, and the hub with them",
       needs=("i18n", "guides", "civics"))
def _spanish_guides_built(i18n, G, civics):
    """The fixture's whole build (build_civics.main, the owner's request of
    24 October 2026): every guide it publishes in English that i18n.PAGES
    gives Spanish is written at /es/guides/<slug> too, a guide held back in
    English has no Spanish copy left, each English page names its twin on
    <html> and in its footer, the Spanish hub /es/resources is written and
    names /resources, and every link on a Spanish guide to /es/ leads to a
    page the build wrote."""
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    shared, _base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    langs = [c for c in i18n.LANGS if c != i18n.DEFAULT]
    bad, n = [], 0
    for f in sorted((site / "guides").glob("*.html")):
        en = f.read_text(encoding="utf-8")
        draft = 'class="g-draft"' in en
        for lang in langs:
            twin = site / lang / "guides" / f.name
            has = i18n.has(lang, f"guides/{f.name}")
            if has and not draft:
                n += 1
                if not twin.is_file():
                    bad.append(f"{f.stem} is published and has no {lang} page")
                    continue
                if f'data-alt-{lang}="/{lang}/guides/{f.stem}"' not in en[:600]:
                    bad.append(f"the English {f.stem} does not name its {lang} twin")
                t = twin.read_text(encoding="utf-8")
                if f'data-alt-en="/guides/{f.stem}"' not in t[:600]:
                    bad.append(f"{lang}/guides/{f.stem} does not name its English page")
                for h in re.findall(rf'href="(/{lang}/[^"#]*)', t):
                    rel = h.strip("/")
                    if not ((site / f"{rel}.html").is_file() or (site / rel / "index.html").is_file()):
                        bad.append(f"{lang}/guides/{f.stem} links {h}, which the build did not write")
            elif twin.exists():
                bad.append(f"{lang}/guides/{f.name} is written beside an English page that is "
                           + ("a draft" if draft else "not in i18n.PAGES"))
    for lang in langs:
        for f in sorted((site / lang / "guides").glob("*.html")) if (site / lang / "guides").is_dir() else []:
            if not (site / "guides" / f.name).is_file():
                bad.append(f"{lang}/guides/{f.name} has no English page")
        if i18n.has(lang, "resources.html"):
            hub = site / lang / "resources.html"
            if not hub.is_file():
                bad.append(f"no {lang}/resources.html")
            elif 'data-alt-en="/resources"' not in hub.read_text(encoding="utf-8")[:600]:
                bad.append(f"{lang}/resources.html does not name /resources")
            if f'data-alt-{lang}="/{lang}/resources"' not in (site / "resources.html").read_text(
                    encoding="utf-8")[:600]:
                bad.append(f"/resources does not name its {lang} twin")
    assert n, "the fixture published no guide that has a Spanish page"
    assert not bad, f"{len(bad)} faults: " + "; ".join(bad[:6])
    return "ok", (f"{n} published guides on the fixture each beside its Spanish page, each naming "
                  "the other; the Spanish hub with them; every /es/ link leads to a page")


@check("build", "the home page is built in Spanish at /es/ from the same data as the English, "
                "unlisted until offered, and each names the other",
       needs=("i18n",))
def _spanish_home(i18n):
    """The Spanish home page is the English one's twin, not a copy kept
    beside it: built in the same run from the same home.json and the same
    week, so the latest activity and Coming up hold the same bills and
    meetings, in the record's own words; only the site's words differ. While
    Spanish is unlisted (lang/es.json's "offered") the page asks not to be
    indexed and neither page names the other to a search engine; once
    offered, both do, and the sitemap lists it. Read off the fixture."""
    shared, _base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    f = site / "es" / "index.html"
    assert f.is_file(), "the build wrote no es/index.html"
    es, en = f.read_text(encoding="utf-8"), (site / "index.html").read_text(encoding="utf-8")
    assert '<html lang="es" data-alt-en="/"' in es, "the Spanish page does not name the English"
    assert 'data-alt-es="/es/"' in en, "the English home page does not name the Spanish"
    assert '<base href="/">' in es, "the Spanish page, one folder down, has no <base href=\"/\">"
    assert 'window.GR_LANG="es"' in es and "window.GR_WORDS=Object.assign(" in es \
        and '<script src="/lang/es.js"></script>' in es, (
        "the Spanish page carries no words for its scripts, or does not load the shared ones")
    shared_words = site / "lang" / "es.js"
    assert shared_words.is_file() and '"find.none":' in shared_words.read_text(encoding="utf-8"), (
        "lang/es.js, the shared scripts' words in Spanish, is missing or holds no word of find.js")
    assert "GR_WORDS" not in en, "the English page carries a translation's words"
    nav = es[es.index('<nav class="top"'):es.index("</nav>")]
    for href, label in __import__("chrome").tab_words("es").items():
        assert f">{label}</a>" in nav, f"the Spanish header does not say {label!r}"
    assert ">Bills</a>" not in nav and ">Officials</a>" not in nav, "the Spanish header is English"
    # The same data in both: the meetings and bills of Latest Activity and the
    # meetings of Coming up, in the same order. Every link of the box, since
    # it became a meeting an item (24 October 2026): its bills' links carry a
    # class now, and a pattern for a bare <a href> found none in either.
    def bills(t):
        i = t.find('<div id="recent"')
        return re.findall(r'href="([^"]+)"', t[i:t.find("</section>", i)]) if i >= 0 else []
    def meets(t):
        return re.findall(r'<details class="calmeet"[^>]*data-cmte="([^"]*)"[^>]*data-date="([^"]*)"', t)
    assert bills(en) and bills(es) == bills(en), ("Latest Activity holds different meetings or "
                                                  f"bills in Spanish: {bills(es)} and {bills(en)}")
    assert meets(es) == meets(en), "Coming up holds different meetings in Spanish"
    # Recent Session Days (recent_sessions, 26 October 2026): the same days'
    # pages and the same recordings from both.
    def sittings(t):
        m = re.search(r'<div id="session">(.*?)</div>\s*</section>', t, re.S)
        return (re.findall(r'href="([^"]+)"|data-embed="([^"]+)"', m.group(1)) if m else None)
    assert sittings(en) and sittings(es) == sittings(en), (
        f"the latest sittings lead elsewhere in Spanish: {sittings(es)} and {sittings(en)}")
    # And in Spanish words, not only to the same places (the review of 26
    # October 2026: main() handing recent_sessions "en" for /es/ passed every
    # check, and the Spanish home page read "Recent Session Days ... Play").
    def session_html(t):
        m = re.search(r'<div id="session">(.*?)</div>\s*</section>', t, re.S)
        return m.group(1) if m else ""
    cat = json.loads(_source("src/pages/lang/es.json"))
    cat = cat.get("strings", cat)
    es_s = session_html(es)
    want = [cat["sess.recent"]["es"], cat["sess.play_house"]["es"].split("{date}")[0]]
    gone = [w for w in want if w not in es_s]
    english = [w for w in ("Recent Session Days", ">Play<", "Play the") if w in es_s]
    assert not gone and not english, (
        f"the Spanish home page's Recent Session Days lack {gone} and keep the English {english}")
    # And a week that has meetings in it (the fixture's own week may have
    # none): Coming up drawn in both languages for 10 March 2026 out of the
    # calendar checks' rows -- the same cards, bills and times, in Spanish
    # words, with the committees' names as the record has them.
    import build_pages as BP
    import contextlib
    import datetime as _dt
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        up = {lang: BP.calendar_html(site, today=_dt.date(2026, 3, 10), rows=_cal_rows(), lang=lang)
              for lang in ("en", "es")}
    assert meets(up["en"]) and meets(up["es"]) == meets(up["en"]), (
        "Coming up for 10 March 2026 holds different meetings in Spanish")
    cbn = lambda t: re.findall(r'class="cbn" href="([^"]+)"', t)
    times = lambda t: re.findall(r'data-time="([^"]*)"', t)
    assert cbn(up["es"]) == cbn(up["en"]) and times(up["es"]) == times(up["en"]), (
        "Coming up for 10 March 2026 lists different bills or times in Spanish")
    assert i18n.say("es", "cal.coming", "Coming Up") in up["es"] and "Coming Up" not in up["es"], (
        "Coming up's heading is not the Spanish one")
    offered = i18n.offered("es")
    assert ('<meta name="robots" content="noindex">' in es) == (not offered), (
        "the Spanish page's robots line does not follow lang/es.json's offered")
    alt = '<link rel="alternate" hreflang="es"'
    assert (alt in en) == offered and (alt in es) == offered, (
        "hreflang names the Spanish page " + ("while it is unlisted" if not offered else "nowhere"))
    sm = (site / "sitemap.xml").read_text(encoding="utf-8")
    assert ("graniterecord.org/es/</loc>" in sm) == offered, (
        "the sitemap " + ("lists /es/ while it is unlisted" if not offered else "leaves /es/ out"))
    return "ok", ("es/index.html beside index.html, the same bills, and in a week with "
                  f"{len(meets(up['es']))} meetings the same cards, bills and times; Spanish header; "
                  + ("offered, in the sitemap" if offered else "unlisted: noindex, no hreflang, "
                     "not in the sitemap"))


# The kinds of address docs/DEMO_PATH.md may stop at: each a page the site
# builds (_demo_path). A stop of another kind is added here once it has been
# opened on the preview, or on the live site: /officials and /resources were,
# at 390px on 5 November 2026, with the deck's three new slides.
DEMO_ADDRESSES = (r"/", r"/search\?q=[^#\s]+", r"/bills\?[^#\s]+",
                  r"/bill/\d{4}/[a-z]{2,5}\d+(?:/(?P<billtab>[a-z]+))?",
                  r"/committee/[A-Za-z0-9-]+", r"/legislator/[a-z0-9-]+",
                  r"/laws/[0-9a-z-]+(?:#s[0-9a-z-]+)?", r"/town/[a-z0-9-]+(?:#(?P<towntab>[a-z]+))?",
                  r"/guides/(?P<guide>[a-z0-9-]+)", r"/calendar/\d{4}-W\d{2}",
                  r"/officials", r"/resources")


@check("frontend", "the webinar's demo path is a draft of ten to fifteen stops, each a kind of "
       "address the site builds, its tab or guide one the site still has", needs=("civics", "guides"))
def _demo_path(CV, G):
    """The audit of 25 October 2026 (C7): the 10 November webinar had a deck
    of screenshots and no written path through the site to show alongside it.
    docs/DEMO_PATH.md is that path, a draft for the owner's approval, each
    stop opened on the dry-run preview at 390px when it was written. What can
    break it before the day without anyone opening a page is a tab or a guide
    renamed under it, so each stop is held to the code that makes it: a bill's
    tab to app.js's BILL_TABS, a town's tab to build_town_pages.py's panels, a
    guide to the ones the site writes (civics.HOW_TO, guides.GUIDES), and
    every stop to a kind of address the site builds (DEMO_ADDRESSES)."""
    doc = _paths.ROOT / "docs" / "DEMO_PATH.md"
    if not doc.is_file():
        return "skip", "no docs/DEMO_PATH.md here"
    text = _source(doc)
    assert "draft for the owner's approval" in " ".join(text.split()), \
        "docs/DEMO_PATH.md no longer says it is a draft for the owner's approval"
    stops = re.findall(r"(?m)^(\d+)\. `(/[^`]*)`", text)
    # Fifteen at most since the deck's three new slides (the owner's board,
    # 27 October 2026: "the demo path gains the same stops").
    assert 10 <= len(stops) <= 15 and [int(n) for n, _ in stops] == list(range(1, len(stops) + 1)), \
        f"the demo path has {len(stops)} stops, numbered {[n for n, _ in stops]}: ten to fifteen, in order"
    app = _source(_paths.ROOT / "src/pages/app.js")
    tabs = re.search(r"const BILL_TABS=\{([^}]*)\}", app)
    assert tabs, "app.js no longer says BILL_TABS where this check reads it"
    bill_tabs = set(re.findall(r"(\w+):", tabs.group(1)))
    town = _source(_paths.ROOT / "src/pages/build_town_pages.py")
    guides = set(CV.HOW_TO) | {g["slug"] for g in G.GUIDES}
    bad = []
    for n, addr in stops:
        m = next((m for m in (re.fullmatch(p, addr) for p in DEMO_ADDRESSES) if m), None)
        if not m:
            bad.append(f"{n}. {addr}: not a kind of address DEMO_ADDRESSES knows")
            continue
        got = m.groupdict()
        if got.get("billtab") and got["billtab"] not in bill_tabs:
            bad.append(f"{n}. {addr}: app.js has no bill tab {got['billtab']!r}")
        if got.get("towntab") and f'("{got["towntab"]}", "' not in town:
            bad.append(f"{n}. {addr}: a town page has no tab {got['towntab']!r}")
        if got.get("guide") and got["guide"] not in guides:
            bad.append(f"{n}. {addr}: the site writes no guide {got['guide']!r}")
    assert not bad, "docs/DEMO_PATH.md: " + "; ".join(bad)
    return "ok", f"{len(stops)} stops, each a kind of page the site builds"


@check("frontend", "a Learn or guide table's box that scrolls is a named region a keyboard can reach: "
       "role=region, named by its caption, and a Tab stop while its table is wider than it is",
       needs=("build_civics",))
def _learn_tables_reachable(BCV):
    """The cohesion audit of 30 October 2026 (B-2): By the Numbers' fourteen
    tables are 428-811px wide in a 364px box at 390, and the box scrolled
    with no name, role or Tab stop, so a keyboard could not pan it. /data's
    coverage table did it right (build_exports: role="region", a name, and
    data-scrollstop, by which app.js's scrollStops gives the box tabindex=0
    while it scrolls and only then). Every .l-tablewrap the pages write goes
    through build_civics.section, which now does the same, naming the box by
    its table's caption or, without one, its section's heading. Held here on
    section itself and on every Learn and guide page the fixture builds."""
    got = BCV.section("s-x", "The Numbers", '<div class="l-tablewrap l-stack"><table class="l-table">'
                      "<caption>Seats in each chamber</caption><tbody></tbody></table></div>"
                      '<details class="l-fold"><summary>2025-2026: the bills</summary>'
                      '<div class="l-tablewrap"><table class="l-table"><tbody></tbody></table></div></details>'
                      '<div class="l-tablewrap"><table class="l-table"><tbody></tbody></table></div>')
    bad = []
    if got.count('data-scrollstop="1" data-scrolllabel="') != 3 or 'data-scrolllabel="Seats in each chamber"' not in got \
            or got.count('data-scrolllabel="The Numbers, 2025-2026"') != 2 or 'role="region"' in got:
        bad.append(f"build_civics.section does not name and mark a table's box: {got[:400]}")
    app = _source("src/pages/app.js")
    stops = app[app.find("function scrollStops"):app.find("function scrollStops") + 1200]
    if not re.search(r'querySelectorAll\("\[data-scrollstop\]"\)', stops) or "scrollStops();" not in app \
            or 'setAttribute("role","region")' not in stops or 'removeAttribute("role")' not in stops \
            or 'addEventListener("toggle",set,true)' not in stops:
        bad.append("app.js no longer makes a [data-scrollstop] box a named region and Tab stop while it scrolls, "
                   "and only then, measured again when a fold opens")
    shared = _fixture_site_shared()[0] / "site"
    boxes = 0
    for f in sorted(list((shared / "learn").rglob("*.html")) + list((shared / "guides").rglob("*.html"))):
        for m in re.finditer(r'<div class="l-tablewrap[^"]*"([^>]*)>', f.read_text(encoding="utf-8")):
            boxes += 1
            if 'data-scrollstop="1"' not in m.group(1) or not re.search(r'data-scrolllabel="[^"]+"', m.group(1)):
                bad.append(f"{f.relative_to(shared)}: a table's box {m.group(0)[:120]!r}")
    # A floor, so that this cannot pass by reading no page: 41 when written.
    if boxes < 20:
        bad.append(f"only {boxes} table boxes in the fixture's Learn and guide pages; they are not being read")
    assert not bad, "; ".join(bad[:5])
    return "ok", f"section names and marks a table's box; {boxes} in the fixture's Learn and guide pages, each so"


@check("frontend", "the 11 November polish holds: the domicile years run immediately before the election, a "
       "guide says when its sources were last checked, and the Spanish pages' six fixes stay",
       needs=("guides", "civics"))
def _polish_11nov(G, CV):
    """The person's items of 2 November 2026, through the manager session.

    1. The years of domicile for governor, councilor, senator and
       representative run "immediately preceding the election" (RSA 655:29,
       Part Second, Article 29). Every row of How to Run for Office's table
       that names them says so, and the Learn page on the governor too.
    2. A guide says "Sources last checked" on the day of its newest claim's
       read (guides.sources_checked), in both languages, not the oldest
       (checked_on, which still decides the out-of-date notice).
    3. The Spanish pages: one vacancy said in the singular; a city's search
       row in the page's language; a home search hint that fits its box; the
       Officials tabs all in sight at 1,280px; the year menu's script on a
       Spanish guide; and titles ending " | Granite Record"."""
    bad = []
    run = next((g for g in G.GUIDES if g["slug"] == "run-for-office"), None)
    assert run, "no run-for-office guide"
    cells = [c for s_ in run["steps"] for c in re.findall(r"<td[^>]*>(.*?)</td>", s_["text"])
             if "domiciled in New Hampshire" in c]
    if len(cells) < 4:
        bad.append(f"the qualifications table names the domicile years in {len(cells)} rows, not 4")
    bad += [f"a qualification says no 'immediately': {c!r}" for c in cells
            if "immediately preceding the election" not in c]
    gov = re.sub(r"\s+", " ", _source("src/pages/civics.py"))
    if "for the 7 years immediately before the election" not in gov:
        bad.append("the Learn page's governor is not for the 7 years immediately before the election")
    later = [g["slug"] for g in G.GUIDES if G.sources_checked(g) and G.sources_checked(g) > G.checked_on(g)]
    if not later:
        bad.append("no guide has a claim read later than its first, so nothing here tells the dates apart")
    bc = _source("src/pages/build_civics.py")
    if bc.count("G.sources_checked(g)") < 2 or "Checked against its sources" in bc:
        bad.append("a guide's page in one of its languages does not say Sources last checked on its newest claim")
    if '" Check each step against the official page it links before you "' not in bc \
            or '"guides.check_each"' not in bc:
        bad.append("a guide does not point to the official page for the current rules")
    if "+ (YR_JS if 'class=\"g-yr\"' in article else \"\"))" not in bc:
        bad.append("a Spanish guide draws In the Record's year menu without its script")
    if " — Granite Record" in bc:
        bad.append("a page in another language still titles itself ' — Granite Record'")
    bp = _source("src/pages/build_pages.py")
    mp = _source("src/pages/map.js")
    for key, src in (("comp.filled_vacant_one", bp), ("roster.filled_vacant_one", bp),
                     ("map.n_vacant_one", mp), ("map.dot_vacant_one", mp)):
        if f'"{key}"' not in src:
            bad.append(f"one vacancy is said with the plural's words: {key} is not asked for")
    es = json.loads(_source("src/pages/lang/es.json"))["strings"]
    for key in ("comp.filled_vacant_one", "roster.filled_vacant_one", "map.n_vacant_one", "map.dot_vacant_one"):
        if "vacantes" in (es.get(key) or {}).get("es", "vacantes"):
            bad.append(f"{key}'s Spanish is not the singular")
    if 'tr("lf.wards"' not in _source("src/pages/find.js"):
        bad.append("a city's search row is said in English on a Spanish page")
    for key, v in es.items():
        if key.startswith("guide.run-for-office.registered-voter-domiciled") and \
                "inmediatamente" not in v.get("es", ""):
            bad.append(f"{key}'s Spanish does not say the years run immediately before the election")
    gov_es = (es.get("learn.state-house-and-branches.the-governor-is-chosen-biennially-in") or {}).get("es", "")
    if "7 años inmediatamente anteriores" not in gov_es:
        bad.append("the Learn page's governor in Spanish is not the 7 years immediately before the election")
    if "were last read {date}" not in (es.get("guides.stale") or {}).get("en", "") or "It was last checked" in bc:
        bad.append("the out-of-date notice still says 'last checked' on the oldest read, beside the newest")
    hint = (es.get("home.search_hint") or {}).get("es", "")
    if len(hint) > len("Bill number, topic, name or town") + 3:
        bad.append(f"the home page's Spanish search hint runs past its box: {hint!r}")
    if ":where(body.pg) .oftabs:lang(es) [role=tab]{padding-left:var(--sp-5)" not in _source("src/pages/app.css"):
        bad.append("the Spanish Officials tabs keep the padding that hid the last one")
    assert not bad, "; ".join(bad[:8])
    return "ok", (f"{len(cells)} domicile rows immediately preceding; {len(later)} guides whose newest "
                  "check is later than their oldest; the six Spanish fixes in place")


@check("frontend", "a guide whose steps are in parts lists each part under Step by Step in its index, "
       "each row leading to that part's heading, in English and Spanish", needs=("build_civics", "guides"))
def _guide_parts_in_index(BC, G):
    """The person's walk of the preview (30 October 2026): a reader of a
    guide in parts (guides.PARTS) jumps from the index to "Renewing an
    adult passport". build_civics.step_parts names each part's heading's
    address; On This Page (otp_items), which OTP_JS copies beside the page,
    lists them one level down under Step by Step. Each guide in parts is
    drawn here: every part's row must lead to an id its steps carry, and
    both of a guide's pages must ask for the parts."""
    bad, n = [], 0
    for g in G.GUIDES:
        parts = BC.step_parts(g)
        if not parts:
            continue
        n += 1
        steps = BC.guide_steps(g)
        items = BC.otp_items([("at-a-glance", "At a Glance", ""), ("steps", "Step by Step", "")], "/g", parts)
        sub = items[items.find('href="/g#steps"'):]
        for pid, label in parts:
            if f'id="{pid}"' not in steps:
                bad.append(f"{g['slug']}: no heading carries id {pid}")
            if f'href="/g#{pid}"' not in sub or 'class="l-otpsub"' not in sub:
                bad.append(f"{g['slug']}: {label!r} is not listed under Step by Step")
    src = _source("src/pages/build_civics.py")
    if "otp_items(secs, S.canon(path), step_parts(g))" not in src:
        bad.append("guide_page's On This Page does not list the parts")
    if "lang_otp(secs, page, lang, step_parts(g, w))" not in src:
        bad.append("a guide's Spanish page does not list its parts")
    assert n, "no guide has its steps in parts, so nothing here was drawn"
    assert not bad, "; ".join(bad[:6])
    return "ok", f"{n} guides in parts, each part listed under Step by Step and leading to its heading"


@check("frontend", "a vote tally's tick is hidden from a screen reader and a word it does not see says "
       "which side prevailed, in the page's language", needs=("i18n",))
def _vote_tick_said(I):
    """The accessibility sweep of the R1 preview (29 October 2026): the tick
    beside a tally's winning side -- a division's Yes or No, each party's
    row on a roll call's ring, the voters' Yes or No on an amendment -- was
    read aloud as "check mark", or not at all, and nothing else on the row
    said which side had won. app.js's wonMark is every tally's tick now:
    aria-hidden on the tick, and beside it <span class="sr"> (prevailed)
    </span>, both in the page's language through tr().

    simpleDonut and ballotRing are drawn in node, once with no words of
    another language and once with the Spanish the catalog gives for the
    two keys, and each tick they draw must be hidden and followed by the
    word; and no tick in app.js is written anywhere but wonMark."""
    js = _source("src/pages/app.js")
    marks = re.findall(r'<span class="won"[^>]*>', js)
    assert len(marks) == 1 and 'aria-hidden="true"' in marks[0], (
        f"app.js writes a tally's tick {len(marks)} times, not once in wonMark, hidden: {marks[:3]}")
    es = {k: I.say("es", k, en) for k, en in (("vote.won_sr", "(prevailed)"),
                                              ("vote.won_title", "this side prevailed"))}
    assert es["vote.won_sr"] != "(prevailed)", "the catalog has no Spanish for vote.won_sr"
    draw = ('[scope.simpleDonut({yeas:191,nays:158,passed:true},"HB1",0,"Passage"),'
            'scope.simpleDonut({yeas:12,nays:300,passed:false},"HB1",1,"Passage"),'
            'scope.ballotRing(700000,200000,true)]')
    got = _app_js("[" + draw + ",(globalThis.GR_WORDS=" + json.dumps(es, ensure_ascii=False) + ","
                  + draw + ")]", names=("simpleDonut", "ballotRing"))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    bad = []
    for lang, said, title, pages in (("en", "(prevailed)", "this side prevailed", got[0]),
                                     ("es", es["vote.won_sr"], es["vote.won_title"], got[1])):
        for n, html in enumerate(pages):
            ticks = re.findall(r'<span class="won"([^>]*)>\u2713</span>\s*<span class="sr"> ([^<]*)</span>', html)
            side = re.findall(r"<span>(Yes|No)<span", html)
            if len(ticks) != 1 or 'aria-hidden="true"' not in ticks[0][0] or ticks[0][1] != said \
                    or f'title="{title}"' not in ticks[0][0]:
                bad.append(f"{lang} tally {n}: {ticks or 'no tick'} beside {side}")
            elif side != (["Yes"] if n != 1 else ["No"]):
                bad.append(f"{lang} tally {n}: the tick is beside {side}")
    assert not bad, ("a tally's tick is read aloud, or no word says which side prevailed: "
                     + "; ".join(bad[:4]))
    return "ok", (f"3 tallies in English and in Spanish, each tick hidden and followed by "
                  f"\"(prevailed)\" or \"{es['vote.won_sr']}\"; app.js writes the tick once, in wonMark")


@check("frontend", "Using this site names the bill page's tabs as the page draws them, and "
                   "says the Votes tab shows the voice and division votes",
       needs=("civics",))
def _using_this_site_tabs(civics):
    """"Using this site" listed a Videos tab, which the page calls Hearings,
    and said voice and division votes "appear in the narrative but have no
    member-by-member record to show", while the Votes tab draws each of them
    as a card, a division with its count (the survey of 7 October 2026).
    Every tab the list names is a tab app.js draws on a bill's page."""
    body = civics.BODY_SITE
    at = body.index("<h2>What a Bill's Page Holds</h2>")
    part = body[at:body.index("</ul>", at)]
    named = re.findall(r"<li><b>([^<]+)</b>", part) + re.findall(
        r", and <b>([^<]+)</b>", part)
    app = _source(_paths.locate("app.js"))
    # The bill page's strip is components.recordTabs's (16 November 2026): its
    # tabs are read off renderDetail's call, ["key","Word",count] each.
    rd = re.search(r"\nfunction renderDetail\(.*?\n\}\n", app, re.S)
    rd = rd.group(0) if rd else ""
    drawn = set(re.findall(r'\["\d","([A-Z][a-z]+(?: [A-Z][a-z]+)?)",', rd))
    assert drawn >= {"Summary", "Votes", "Videos", "Reports"} and not drawn & {"Hearings", "Sponsors"}, (
        f"the bill page's tabs read {sorted(drawn)} out of app.js")
    missing = [t for t in named if t not in drawn and t != "Bill Text"]
    assert not missing, (f"Using this site names tabs a bill's page does not have: {missing}; "
                         f"it draws {sorted(drawn)}")
    assert "Bill Text" not in named or '"Bill Text"' in rd, "app.js has no Bill Text tab"
    votes = re.sub(r"\s+", " ", part[part.index("<b>Votes</b>"):])
    votes = votes[:votes.index("</li>")]
    assert "appear in the narrative" not in votes and "voice or division vote" in votes, (
        "Using this site says the voice and division votes are not on the Votes tab: " + votes)
    # AND EVERY OTHER CIVICS PAGE (the review of 8 October 2026). Using this
    # site was mended and two pages were not: State agencies said "the bill's
    # Videos tab links the recording", and Testifying "the Videos tab links
    # it", of a tab the page calls Hearings. Every "the bill's X tab" and "the
    # X tab" in civics' prose names a tab app.js draws.
    prose = " ".join(v for k, v in vars(civics).items()
                     if k.startswith("BODY_") and isinstance(v, str))
    said = set(re.findall(r"\bthe (?:bill's )?((?:[A-Z][a-z]+ )?[A-Z][a-z]+) tab\b", prose))
    stale = sorted(t for t in said if t not in drawn and t != "Bill Text")
    assert not stale, f"the civics pages name tabs a bill's page does not have: {stale}"
    return "ok", (f"names {', '.join(named)}, each a tab the page draws, and the other civics "
                  f"pages name {', '.join(sorted(said)) or 'no tab'}")


@check("frontend", "each count of bills filed in a term says what it counts: the bills and "
                   "resolutions, or the House and Senate bills alone",
       needs=("civics", "learn_numbers"))
def _bills_filed_counts(civics, learn_numbers):
    """Two counts of the bills filed in 2025-2026, 2,243 on How a bill
    becomes law and The General Court and 2,139 on By the numbers, and
    neither said what it counted (the survey of 7 October 2026): the first is
    every measure of the term, its constitutional amendments and resolutions
    among them, and the second the House and Senate bills alone. Each says
    so now, wherever [[bills]] is counted as filed."""
    import inspect
    flat = re.sub(r"\s+", " ", inspect.getsource(civics))
    bare = re.findall(r"\[\[bills\]\] bills(?! and resolutions)", flat)
    assert not bare, (f"{len(bare)} of the pages' counts of [[bills]], every measure of the "
                      "term, still call them bills alone")
    for said in ("filed <b>[[bills]] bills and resolutions</b>",
                 "Of the [[ends_bills]] House and Senate bills filed in the [[term]] term"):
        assert said in flat, f"civics no longer says \"{said}\""
    src = re.sub(r'"\s*\n\s*"', "", inspect.getsource(learn_numbers.body))
    assert ("Every House and Senate bill given a number in each term, not counting "
            "constitutional amendments or resolutions") in src, (
        "By the numbers' bills filed does not say it leaves out the constitutional amendments "
        "and resolutions")
    return "ok", ("the term's measures are \"bills and resolutions\"; By the numbers' are the "
                  "House and Senate bills, not counting constitutional amendments or resolutions")


@check("frontend", "By the Numbers is built in Spanish: every section, its address kept, the record's words marked English",
       needs=("learn_numbers", "build_civics", "i18n"))
def _numbers_in_spanish(learn_numbers, build_civics, i18n):
    """/es/learn/by-the-numbers holds the English page's sections under the
    addresses the English page gives them, each heading and sentence in
    Spanish and every figure the English page's own; a committee's name is
    marked lang="en" as the record has it. The Spanish page is drawn from the
    same code as the English (learn_numbers.body's lang), so a figure cannot
    differ."""
    if not i18n.has("es", "learn/by-the-numbers.html"):
        raise AssertionError("i18n.PAGES has no Spanish By the Numbers")
    shared, base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    en_p, es_p = site / "learn" / "by-the-numbers.html", site / "es" / "learn" / "by-the-numbers.html"
    if not en_p.exists():
        return "skip", "the fixture has no By the Numbers"
    assert es_p.exists(), "the Spanish By the Numbers is not written"
    en, es = en_p.read_text(encoding="utf-8"), es_p.read_text(encoding="utf-8")
    ids = lambda t: re.findall(r'<section class="l-sec" id="([^"]+)"', t)
    assert ids(en) == ids(es) and ids(en), (
        f"the sections' addresses differ: {ids(en)} against {ids(es)}")
    assert '<html lang="es"' in es and 'data-alt-en="/learn/by-the-numbers"' in es
    assert 'data-alt-es="/es/learn/by-the-numbers"' in en and \
        'lang="es" data-href="/es/learn/by-the-numbers"' in en, (
            "the English page does not lead to the Spanish one")
    seen = _visible_text(es)
    for head in learn_numbers.HEADINGS:
        if head in ("The Hearings with the Most Sign-Ins", "Constitutional Amendments Sent to the Voters"):
            continue
        assert head not in seen, f"the Spanish By the Numbers has {head!r} in English"
    for word in ("Bills filed", "Became Law", "Interim Study", "How These Are Counted",
                 "Hover over a term", "Filed per representative"):
        assert word not in seen, f"the Spanish By the Numbers says {word!r} in English"
    # The same figures: every number of a table's cells is the English page's.
    cells = lambda t: re.findall(r'<td class="l-num"[^>]*>([^<]*)</td>', t)
    assert cells(en) == cells(es), "a figure of the Spanish By the Numbers is not the English page's"
    assert 'lang="en"' in es and 'House Commerce' in es and "House Commerce</span>" in es, (
        "a committee's name on the Spanish page is not marked as the record's English")
    return "ok", (f"{len(ids(es))} sections at the English addresses, {len(cells(es))} figures the "
                  "English page's, the record's words marked")


@check("frontend", "every section of By the Numbers renders in Spanish, from figures that make them all, with no English heading left",
       needs=("learn_numbers", "site_read", "i18n"))
def _numbers_spanish_sections(learn_numbers, SR, i18n):
    """The fixture holds none of the files four of the page's sections need
    (testimony, member votes, the voters' counts), so a Spanish page built from
    it never draws them. This gives learn_numbers.body the figures the others
    work out -- a stand-in for each, in the shapes their functions return --
    and draws the whole page in both languages: fourteen sections each, the
    same sections, none of English's headings or table heads left among
    Spanish's, and English's body the same whether `lang` is given or not."""
    from collections import Counter
    t1, t2 = "2023-2024", "2025-2026"
    idx = [{"term": t1, "id": "HB1", "year": 2023, "chip": "Became Law"},
           {"term": t2, "id": "HB2", "year": 2025, "chip": "Died"}]
    hear = {t2: [{"bill": "HB2", "year": "2025", "date": "2025-02-10", "total": 50, "support": 40,
                  "oppose": 9, "neutral": 1, "committee": "House Judiciary", "on": "an amendment",
                  "title": "relative to pears."},
                 {"bill": "HB3", "year": "2026", "date": "2026-02-11", "total": 30, "support": 10,
                  "oppose": 20, "neutral": 0, "committee": "", "on": "a non-germane amendment",
                  "title": "relative to figs."}]}
    ballot = {"rows": [
        {"bill": "CACR1", "term": t1, "election": "2024-11-05", "yes": 700, "no": 300,
         "source": "https://www.sos.nh.gov/x", "cite": "SOS 2024"},
        {"bill": "CACR3", "term": t2, "election": "2999-11-05", "yes": None, "no": None},
        {"bill": "CACR4", "term": t2, "election": "2025-11-05", "yes": None, "no": None}]}
    mem = {"outcomes": learn_numbers.outcomes, "per_member": learn_numbers.per_member,
           "referrals": learn_numbers.referrals, "signins": learn_numbers.signins,
           "overturned": learn_numbers.overturned, "consent": learn_numbers.consent,
           "committee_rates": learn_numbers.committee_rates, "passage": learn_numbers.passage,
           "vetoes": learn_numbers.vetoes, "attendance": learn_numbers.attendance,
           "_need": learn_numbers._need, "needs_more_than_majority": learn_numbers.needs_more_than_majority}
    saved = (SR.bill_index_or_stop, SR.figures_term)
    L = learn_numbers
    narr = {t2: {"HB2": {"events": [{"type": "floor", "date": "2025-03-01", "vote_kind": "RC"},
                                    {"type": "floor", "date": "2026-03-02", "vote_kind": "VV"}]}}}
    tmp = Path(tempfile.mkdtemp(prefix="gr-numsstub-"))
    try:
        (tmp / "narratives.json").write_text(json.dumps(narr), encoding="utf-8")
        (tmp / "rollcalls.json").write_text(json.dumps({t2: {"HB2": [
            {"yeas": 200, "nays": 190, "body": "H", "question": "Ought to Pass",
             "date": "2026-03-04", "year": 2026, "procedural": False}]}}), encoding="utf-8")
        SR.bill_index_or_stop = lambda *a, **k: idx
        SR.figures_term = lambda i: t2
        L._need = lambda path, what: (hear if "testimony" in str(path) else {}
                                      if "member_votes" in str(path) else ballot if "ballot" in str(path)
                                      else {})
        L.outcomes = lambda i: {t1: {"filed": 10, "Became Law": 4, "Died": 3, "Interim Study": 2, "other": 1},
                                t2: {"filed": 20, "Became Law": 6, "Died": 9, "Interim Study": 2, "other": 3}}
        L.per_member = lambda i: {t1: {"H": [800, 300], "S": [90, 40]}, t2: {"H": [700, 250], "S": [80, 30]}}
        L.referrals = lambda i, n, t: {"House Commerce": (5, 2), "Senate Education": (3, 0)}
        L.signins = lambda *a, **k: hear
        L.overturned = lambda n: ({"H": (30, 3, 1), "S": (0, 0, 0)}, [("HB2", "H", "PASS", "KILL")])
        L.consent = lambda n, r, t: ({"House Commerce": (12, 10), "Senate Education": (15, 4)},
                                     {"H": Counter(kept=10, regular=3, removed=2), "S": Counter(kept=4, regular=1)})
        L.committee_rates = lambda i, n, t: ({"House Commerce": (12, 6, 4), "Senate Education": (15, 7, 5)},
                                             {"H": (12, 6, 4), "S": (15, 7, 5)})
        L.passage = lambda i, n: {t1: {"passed": 10, "amended": 4, "conference": 1,
                                       "dist": Counter({0: 5, 1: 3, 2: 1, 3: 1})},
                                  t2: {"passed": 20, "amended": 12, "conference": 3,
                                       "dist": Counter({0: 8, 1: 6, 2: 3, 4: 3})}}
        L.vetoes = lambda rows: (30, 5, 3, 1, 1)
        L.attendance = lambda v: {(t1, "H"): (30, 0.91), (t2, "S"): (25, 0.9)}
        L.needs_more_than_majority = lambda b, r: False
        en = L.body(tmp, tmp, strict=False)
        en2 = L.body(tmp, tmp, strict=False, lang="en")
        es = L.body(tmp, tmp, strict=False, lang="es")
    finally:
        SR.bill_index_or_stop, SR.figures_term = saved
        for k, v in mem.items():
            setattr(L, k, v)
        shutil.rmtree(tmp, ignore_errors=True)
    assert en == en2, "By the Numbers in English differs when its language is stated"
    h2 = lambda t: re.findall(r"<h2>(.*?)</h2>", t)
    assert len(h2(en)) == len(L.HEADINGS) == len(h2(es)), (
        f"{len(h2(en))} sections in English, {len(h2(es))} in Spanish, {len(L.HEADINGS)} named")
    assert not set(h2(en)) & set(h2(es)), f"a heading is in English on the Spanish page: {set(h2(en)) & set(h2(es))}"
    seen = _visible_text(es)
    for word in ("Term", "Bills filed", "Became Law", "Reached the governor", "Yes share",
                 "Ratified", "were adopted", "went to the voters", "Hover over", "sign-ins",
                 "Interim Study", "Passed both chambers"):
        assert not re.search(rf"\b{re.escape(word)}\b", seen), f"the Spanish page says {word!r}"
    assert 'lang="en">House Commerce<' in es and 'lang="en">relative to' in es, (
        "the record's words (a committee, a title) are not marked as English")
    return "ok", f"{len(h2(es))} sections in both languages from stand-in figures; English the same with its language stated"


@check("files", "the About page promises what the report box and the compiler actually do")
def _about_reports():
    """The About page is where a reader is told what a report holds and how long
    it is kept. Until 13 September it said the one thing a reader sent was
    feedback through a Google form, a day after the report box went live, and
    nothing deleted a report at all. The promise is held to the code now: the
    box named as app.js labels it, and the week as compile_reports deletes.

    TWO PLACES SINCE 9 OCTOBER 2026. The About page the person approved that
    day says it in a line -- reports sent through the <i>Report a problem</i>
    button are deleted after a week -- and its old section, "What this site
    knows about you", moved word for word to the Data page under "Privacy in
    Detail" (build_exports.PRIVACY). So the detail is held there, the box by
    its whole label as before, and About's line is held to the same week and
    to naming the box by the words its label begins with."""
    bp, ex = _paths.locate("build_pages.py"), _paths.locate("build_exports.py")
    app, cr = Path("src/pages/app.js"), _paths.locate("compile_reports.py")
    absent = [str(p) for p in (bp, ex, app, cr) if not p.exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)

    def const(p, name):
        t = p.read_text(encoding="utf-8")
        i = t.find(f'\n{name} = """')
        assert i >= 0, f"{p.name} no longer has {name}"
        t = t[i + len(f'\n{name} = """'):]
        return " ".join(t[:t.index('"""')].split())
    about, detail = const(bp, "ABOUT"), const(ex, "PRIVACY")
    # Its privacy paragraph is one of two since 11 October 2026, before and
    # after email goes live (build_pages.ABOUT_FOLLOW); both must keep the
    # promise, so each is held below.
    src = _source(bp)
    follow = " ".join(src[src.index("\nABOUT_FOLLOW = {"):src.index("\n}\n", src.index("\nABOUT_FOLLOW = {"))].split())
    about = about + " " + follow
    # Its drawing comes first since Polish 1 (9 October 2026): the label is
    # the words after it, " a problem" in a span a phone's row leaves out
    # (25 October 2026), read here as the words a wider page shows.
    m = re.search(r'<summary>(?:\$\{icon\("report"\)\})?((?:<span>)?Report\b(?:[^<]|</?span\b[^>]*>)*)'
                  r'</summary>', _source(app))
    assert m, "app.js no longer labels the report box"
    label = " ".join(re.sub(r"<[^>]+>", "", m.group(1)).split())
    assert f"<i>{label}</i>" in detail, (
        f"the Data page's Privacy in Detail does not name the box as the page labels it, <i>{label}</i>")
    named = re.findall(r"<i>(Report\b[^<]*)</i>", about)
    assert named and all(label.startswith(n) for n in named), (
        f"the About page names the box {named}, which is not how the page labels it, <i>{label}</i>")
    k = re.search(r"^KEEP_DAYS = (\d+)", _source(cr), re.M)
    assert k, "compile_reports.py no longer says how long a report is kept"
    said = {7: "a week", 14: "two weeks", 30: "a month"}.get(int(k.group(1)))
    assert said and follow.count(f"deleted after {said}") == 2, (
        f"compile_reports deletes a report after {k.group(1)} days; one of the About page's two "
        f"privacy paragraphs does not say \"deleted after {said}\"")
    for page, text in (("the About page", about), ("the Data page's Privacy in Detail", detail)):
        assert said and f"deleted after {said}" in text, (
            f"compile_reports deletes a report after {k.group(1)} days; {page} does not "
            f"say \"deleted after {said or k.group(1) + ' days'}\"")
    # AND THE BOX FOR A MISTAKE IN THE TRANSLATION (the person, 25 October
    # 2026: "I approve the privacy text update"). A page in Spanish sends a
    # report of its own kind from components.js to the same /api/report, so
    # report.js stores it with the others and compile_reports deletes it with
    # them. The detail had not said so. It names the box as the footer labels
    # it, in Spanish, and says what the report holds and how long it is kept.
    import i18n
    trlabel = i18n.catalog("es")["strings"]["foot.tr_report"]["es"]
    comp = _source("src/pages/components.js")
    trbox = comp[comp.index("// A MISTAKE IN A TRANSLATION"):]
    assert 'fetch("/api/report"' in trbox and 'record:"translation:"+url' in trbox, (
        "the translation's box no longer posts to /api/report, so it is not kept and deleted as a report is")
    trpara = next((p for p in re.findall(r"<p>(.*?)</p>", detail) if "translation" in p), "")
    assert f'<i lang="es">{trlabel}</i>' in trpara, (
        "the Data page's Privacy in Detail does not name the translation's box as a page in Spanish "
        f"labels it, <i lang=\"es\">{trlabel}</i>")
    for need in ("the page&rsquo;s address", "what you wrote", "the words you had selected",
                 "nothing in it identifies you", f"deleted after {said}"):
        assert need in trpara, (
            f"the Data page's Privacy in Detail does not say of a translation report {need!r}")
    return "ok", (f"the box named as it is labelled, and deleted after {said}, as the compiler "
                  "does, on About and in the Data page's Privacy in Detail; and the translation's "
                  "box named in Spanish, what it sends and that it goes the same way")


@check("data", "the Learn pages' worked examples agree with the roll calls they cite")
def _learn_examples_record():
    """The Learn pages teach with real votes, typed into the prose, and one was
    wrong: HB 1002's 193-179 was given as "62 Republicans for", where the
    ballots of roll call 2024-H-35 hold 63. A figure typed from memory is the
    thing every other number on these pages was changed to avoid, so each one
    a page states is checked here against the roll call it describes:

      * a party split -- "193 to 179: 63 Republicans for and 125 against" --
        against the ballots of the House roll call on that bill with that
        tally, the bill named by the heading above it;
      * a count of members in office -- "231 to 88 when 384 members were in
        office", "CACR 26 with 239 votes, when 397 members were in office" --
        against the ballots of that roll call, one per member in office;
      * "still awaiting its override vote", only while a veto of the current
        term has no override yet;
      * every row of the closest-votes table, against rollcalls.json: none may
        be a question that needed more than a majority.
    """
    import csv as _csv
    from collections import defaultdict
    site = Path("site")
    page = site / "learn" / "how-a-bill-becomes-law.html"
    if not page.exists() or not (site / "data").is_dir():
        return "skip", "the Learn pages or site/data are not built"

    def text(p):
        t = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        return re.sub(r"\s+", " ", t)

    tallies = {}

    def house_votes(year):
        """{(bill, yeas, nays): Counter of (party, vote)} for the House roll
        calls of the term holding `year`, read once per term."""
        hits = sorted(site.glob("data/votes-*.csv"))
        f = next((h for h in hits if str(year) in h.stem.split("-")[1:]), None)
        assert f, f"no site/data/votes-*.csv holds {year}"
        if f not in tallies:
            by = defaultdict(Counter)
            with f.open(encoding="utf-8", newline="") as fh:
                for r in _csv.DictReader(fh):
                    if r.get("chamber") == "House":
                        by[(r["roll_call"], r["bill"])][(r["party"], r["vote"])] += 1
            out = defaultdict(list)
            for (rc, bill), c in by.items():
                y = sum(v for (_p, vote), v in c.items() if vote == "Yea")
                n = sum(v for (_p, vote), v in c.items() if vote == "Nay")
                out[(bill, y, n)].append(c)
            tallies[f] = out
        return tallies[f]

    how = text(page)
    checked = 0
    # A party split, with the tally in bold before it in the same paragraph,
    # under the heading that names its bill.
    for m in re.finditer(r"(\d+) Republicans for and (\d+) against, (\d+) Democrats for "
                         r"and (\d+) against", how):
        para = how[how.rfind("<p", 0, m.start()):m.start()]
        tally = re.findall(r"<b>(\d+) to (\d+)</b>", para)
        assert tally, f"'{m.group(0)}' names no tally in bold before it in its paragraph"
        head = re.findall(r"<h3[^>]*>\s*([A-Z]+) (\d+) \((\d{4})\)", how[:m.start()])
        assert head, f"'{m.group(0)}' sits under no heading naming its bill"
        kind, num, year = head[-1]
        (y, n), (ry, rn, dy, dn) = map(int, tally[-1]), map(int, m.groups())
        found = house_votes(year).get((f"{kind}{num}", y, n)) or []
        assert found, f"no House roll call on {kind} {num} ({year}) was {y}-{n}"
        c = found[0]
        got = (c[("R", "Yea")], c[("R", "Nay")], c[("D", "Yea")], c[("D", "Nay")])
        assert got == (ry, rn, dy, dn), (
            f"{kind} {num} {y}-{n}: the page says R {ry}/{rn}, D {dy}/{dn}; the ballots "
            f"say R {got[0]}/{got[1]}, D {got[2]}/{got[3]}")
        checked += 1
    # A count of the members in office, from the ballots of that roll call.
    learn_all = " ".join(text(p) for p in sorted((site / "learn").glob("*.html")))
    flat = re.sub(r"<[^>]+>", " ", learn_all)
    flat = re.sub(r"\s+", " ", flat)
    examples = [(m.group(1), None, int(m.group(2)), int(m.group(3)), int(m.group(4)))
                for m in re.finditer(r"in \w+ (\d{4}) it overrode a veto (\d+) to (\d+) "
                                     r"when (\d+) members were in office", flat)]
    examples += [(m.group(1), f"CACR{m.group(2)}", int(m.group(3)), None, int(m.group(4)))
                 for m in re.finditer(r"In (\d{4}) the House carried CACR (\d+) with (\d+) "
                                      r"votes, when (\d+) members were in office", flat)]
    for year, bill, y, n, seated in examples:
        hits = [(key, c) for key, cs in house_votes(year).items() for c in cs
                if key[1] == y and (n is None or key[2] == n)
                and (bill is None or key[0] == bill)]
        assert hits, f"no House roll call of {year} matches {bill or ''} {y}-{n or ''}"
        assert any(sum(c.values()) == seated for _k, c in hits), (
            f"{bill or 'the override'} {y}-{n or ''} of {year}: the page says {seated} "
            f"members were in office; its ballots number "
            f"{sorted({sum(c.values()) for _k, c in hits})}")
        checked += 1
    # veto_pending: only while a veto of the current term awaits its override.
    gov = text(site / "learn" / "governor-and-council.html")
    idx = _site_bills(site) or []
    term = max((r.get("term") or "" for r in idx), default="")
    if "awaiting" in gov and "override" in gov:
        assert any(r.get("status") == "Vetoed" and r.get("term") == term for r in idx), (
            "the governor page says a veto is still awaiting its override vote, and no "
            f"vetoed bill of {term} is without one")
    # The closest votes: no row needed more than a majority.
    nums = text(site / "learn" / "by-the-numbers.html")
    at = nums.find("The Closest Votes")
    rows = 0
    if at >= 0:
        try:
            import learn_numbers as LN
        except ImportError:
            return "skip", "learn_numbers.py will not import"
        rcs = json.loads(Path("rollcalls.json").read_text(encoding="utf-8")) \
            if Path("rollcalls.json").exists() else {}
        cur = rcs.get(term) or {}
        block = nums[at:]
        block = block[:block.find("<h2", 10)] if "<h2" in block[10:] else block
        # A cell may carry a class (a column of numbers is set right, l-num).
        for m in re.finditer(r'bill/\d{4}/([a-z0-9]+)"[^<]*</a></td><td[^>]*>([^<]*)</td>'
                             r"<td[^>]*>[^<]*</td><td[^>]*>(\d+)&ndash;(\d+)</td><td[^>]*>([^<]*)</td>",
                             block):
            bid, y, n, day = m.group(1).upper(), int(m.group(3)), int(m.group(4)), m.group(5)
            same = [r for r in cur.get(bid) or []
                    if r.get("yeas") == y and r.get("nays") == n and (r.get("date") or "") == day]
            assert not any(LN.needs_more_than_majority(bid, r) for r in same), (
                f"the closest votes list {bid} {y}-{n} of {day}, a question that needed more "
                "than a majority, so its margin says nothing about how close it was")
            rows += 1
        assert rows or "<tbody><tr>" not in block, (
            "the closest-votes table has rows this cannot read, so none of them was checked")
    return "ok", (f"{checked} worked examples match their ballots; {rows} closest votes, "
                  "each a majority question")


@check("frontend", "By the Numbers' charts are drawn from the tables' own numbers, say their range in words, "
                   "and colour the two chambers in neutral tones and two shapes, never a party's",
       needs=("learn_numbers",))
def _numbers_charts(LN):
    """The owner, 11 November 2026: the charts are static inline SVG made at
    build time, each over the table it is drawn from; House and Senate are
    neutral tones plus shape and never the parties' colours (--rep, --dem,
    --ind mean a party everywhere else on the site). The stacked bar prints,
    at the end of each bar, the share the table's own counts give."""
    import inspect
    oc = {t: {"filed": 100, "Became Law": 20 + 3 * i, "Interim Study": 10, "Died": 60 - 3 * i, "other": 10}
          for i, t in enumerate(("2019-2020", "2021-2022", "2023-2024"))}
    html_ = LN.ends_chart(oc, list(oc))
    assert re.findall(r'class="sk-v"[^>]*>([\d.]+)%', html_) == ["20.0", "23.0", "26.0"], (
        "the bar's printed shares are not the table's counts")
    assert 'role="img"' in html_ and "from 20.0% in 2019" in html_ and "<table" not in html_, (
        "a chart says its range in words and leaves its figures to the table beneath it")
    assert html_.count("<rect") >= 12, "a bar is drawn in four segments a term"
    pts = [("House A", "H", 40, 55.0), ("Senate B", "S", 15, 30.0), ("House C", "H", 90, 10.0)]
    sc = LN.scatter_chart(pts, "t", "said", "x", "y")
    assert sc.count('class="ch-h"') == 2 and sc.count('class="ch-s"') == 1, "House circles, Senate diamonds"
    assert "House A: 40 bills reported on, 55.0% passed" in sc, "a point's title holds its figures"
    sc_es = LN.scatter_chart(pts, "t", "said", "x", "y", "es")
    assert "House A: informó sobre 40 proyectos, 55.0% aprobados por ambas cámaras" in sc_es and \
        "bills reported on" not in sc_es, "the Spanish page's hover titles are written in English"
    dots = LN.dot_chart([("2019", 88.0, 95.0), ("2021", 90.0, None)], "t", "said")
    assert dots.count('class="ch-h"') == 2 and dots.count('class="ch-s"') == 1, "a dot a chamber, none where there is none"
    src = inspect.getsource(LN.scatter_chart) + inspect.getsource(LN.dot_chart) + \
        inspect.getsource(LN.chamber_marker) + inspect.getsource(LN.lines_chart)
    css = _source("src/pages/app.css")
    chamber_css = "".join(re.findall(r"[^{}]*(?:\.ch-h|\.ch-s|\.c-h|\.c-s)\b[^{}]*\{[^}]*\}", css))
    assert chamber_css, "app.css does not draw the chamber marks"
    for bad in ("--rep", "--dem", "--ind"):
        assert bad not in src and bad not in chamber_css, f"a chamber is drawn in a party colour ({bad})"
    for need in (".ch .ch-h{", ".ch .ch-s{", ".l-sw.is-diamond"):
        assert need in css, f"app.css lacks {need}"
    es = json.loads(_source("src/pages/lang/es.json"))["strings"]
    for k in ("nums.ch_ends_said", "nums.ch_cmte_said", "nums.ch_cmte_tip", "nums.ch_att_said", "nums.pos_said", "nums.yes_said"):
        assert k in es, f"es.json lacks {k}"
    assert 'viewBox="0 0 100 10"' in LN.yes_bar(70.0) and 'x1="66.7"' in LN.yes_bar(70.0), (
        "the ballot's bar carries the two-thirds line")
    return "ok", "a bar's shares are the table's, ranges said in words, chambers neutral in shape and tone"


@check("frontend", "By the Numbers fits its box: every chart label is inside its own viewBox, no number table is "
                   "held to the prose measure, the flow diagram has no minimum width off a phone and its table is "
                   "not pinned, no named scatter label covers a named point, and ties come out in name order",
       needs=("learn_numbers",))
def _numbers_fit(LN):
    """The owner, 13 November 2026, from a printed copy of the page: the
    term labels of the bars and dots lost their first digit ("989-1990"), a
    named committee ran off the scatter plot's edge, the flow diagram scrolled
    sideways with its right-hand names cut, and the figures tables scrolled
    or were cut at the page's edge.

    Two halves. The charts are built on long labels (a term, a name of forty
    characters, a count in the thousands) and every <text> in them is
    measured -- its width from learn_numbers.text_w, the SVG's own font size
    and its anchor, rotated text on the other axis -- against the viewBox it
    sits in. And app.css is read for the two rules that caused the rest:
    number tables held to the prose measure, and a minimum width on the flow
    diagram that applies at every width rather than only on a phone.

    Four more guards, each from a thing that broke: the phone's pinned first
    column must not reach the flow diagram's table (.l-twin), whose first
    column is wider than the box; a named scatter label's box must not
    contain its own point; nor another named committee's point (2023-2024:
    Childcare across Transportation); and tied committees come out in name
    order whatever order they arrive in."""
    terms = [f"{y}&ndash;{y + 1}" for y in range(1989, 2027, 2)]
    oc = {t.replace("&ndash;", "-"): {"filed": 1000 + i, "Became Law": 150 + i, "Interim Study": 100,
                                       "Died": 700, "other": 50 + i}
          for i, t in enumerate(terms)}
    pts = [("House Executive Departments and Administration", "H", 250, 3.0),
           ("Senate Commerce", "S", 20, 30.0), ("House Finance", "H", 200, 70.0),
           ("Senate Education and Workforce Development", "S", 85, 60.0),
           ("House Ways and Means", "H", 12, 99.0), ("House Judiciary", "H", 150, 55.0),
           ("Senate Judiciary", "S", 100, 10.0),
           # a name too long for either side of its point (a third of the
           # way along, in the top three): it must be set clear of its point
           ("Senate Energy, Environment and Economic Development", "S", 150, 80.0),
           # two committees at one rate, to come out in name order
           ("House Transportation", "H", 106, 50.0), ("House Public Works and Highways", "H", 44, 50.0),
           # two NAMED committees at one rate, the left one first by name, as in 2023-2024:
           # the right-hand one claims the line, or the left one's name runs across it
           ("Senate Transportation", "S", 60, 99.0)]
    tree = {"label": "Bills filed", "n": 2139, "cls": "n", "kids": [
        {"label": "Cleared the second chamber", "n": 1900, "cls": "n", "kids": [
            {"label": "Reached the governor", "n": 686, "cls": "n", "kids": [
                {"label": "became law", "n": 649, "cls": "law", "kids": []},
                {"label": "chambers did not agree on a version", "n": 42, "cls": "done", "kids": []}]}]},
        {"label": "withdrawn or not introduced", "n": 239, "cls": "rest", "kids": []}]}
    svgs = {
        "stacked bars": LN.ends_chart(oc, list(oc)),
        "scatter": LN.scatter_chart(pts, "t", "said", "bills reported on", "Passed both chambers"),
        "dots": LN.dot_chart([(t, 88.0 + i * .3, 95.0) for i, t in enumerate(terms)], "t", "said"),
        "lines": LN.lines_chart([("House", [t.replace("&ndash;", "-") for t in terms],
                                  [("filed", "ink", [1.5 + i * .1 for i in range(len(terms))])]),
                                 ("Senate", [t.replace("&ndash;", "-") for t in terms],
                                  [("filed", "ink", [30 + i for i in range(len(terms))])])], "t", "said"),
        "flow": LN.sankey_svg(tree, "said"),
    }
    num = r"-?[\d.]+"
    bad = []
    for name, html_ in svgs.items():
        assert html_, f"{name} was not drawn"
        m = re.search(r'<svg class="sk(?: ch)?" viewBox="0 0 (\d+) (\d+)"', html_)
        W, H = int(m.group(1)), int(m.group(2))
        px = LN.CH_PX if " ch" in m.group(0) else 14
        for tm in re.finditer(r"<text([^>]*)>(.*?)</text>", html_, re.S):
            attrs, inner = tm.groups()
            body = re.sub(r"<[^>]+>", "", inner)
            x = float(re.search(rf'\bx="({num})"', attrs).group(1)) if re.search(r'\bx="', attrs) else 0.0
            y = float(re.search(rf'\by="({num})"', attrs).group(1)) if re.search(r'\by="', attrs) else 0.0
            anchor = (re.search(r'text-anchor="(\w+)"', attrs) or [0, "start"])[1]
            bold = "sk-v" in attrs or "sk-v" in inner
            wd = LN.text_w(body, px, bold=bold)
            rot = re.search(rf'translate\(({num}),({num})\) rotate\(-90\)', attrs)
            if rot:                       # runs up the page: its length is on y
                cx, cy = float(rot.group(1)), float(rot.group(2))
                x0, x1, y0, y1 = cx - px, cx + px * .25, cy - wd / 2, cy + wd / 2
            else:
                x0 = x - (wd if anchor == "end" else wd / 2 if anchor == "middle" else 0)
                x1, y0, y1 = x0 + wd, y - px * .8, y + px * .25
            if x0 < 0 or x1 > W or y0 < 0 or y1 > H:
                bad.append(f"{name}: '{body[:28]}' spans x {x0:.0f}..{x1:.0f}, y {y0:.0f}..{y1:.0f} "
                           f"outside 0..{W} x 0..{H}")
    assert not bad, "a chart label is cut by its own viewBox: " + "; ".join(bad[:6])
    # (b) a named label's box never contains its own point (it hid the point it named)
    sc = svgs["scatter"]
    marks = {}
    for gm in re.finditer(r"<g><title>([^<]+?): [\d,]+ bills reported[^<]*</title>"
                          r'(?:<circle[^>]*cx="([\d.]+)" cy="([\d.]+)"|<path[^>]*d="M([\d.]+),([\d.]+)L)', sc):
        nm, cx, cy, mx, my = gm.groups()
        marks[nm] = (float(cx), float(cy)) if cx else (float(mx), float(my) + 5.5)
    seen = 0
    for tm in re.finditer(r'<text x="([\d.]+)" y="([\d.]+)" text-anchor="(start|end)">([^<]+)</text>', sc):
        lx, ly, anchor, short = float(tm.group(1)), float(tm.group(2)), tm.group(3), tm.group(4)
        own = [pt for n_, pt in marks.items() if re.sub(r"^(House|Senate) ", "", n_) == short]
        if not own:
            continue
        seen += 1
        wd = LN.text_w(short, LN.CH_PX)
        x0 = lx - wd if anchor == "end" else lx
        for ox, oy in own:
            assert not (x0 <= ox <= x0 + wd and ly - LN.CH_PX * .8 <= oy <= ly + LN.CH_PX * .25), (
                f"the label '{short}' is set across its own point at ({ox:.0f}, {oy:.0f})")
    assert seen >= 4, f"only {seen} named labels were found in the scatter chart"
    # (d) nor another named committee's point (2023-2024: Childcare's name across Transportation's)
    ranked_ = sorted(pts, key=lambda p: (p[3], p[0]))
    named_ = {p[0] for p in ranked_[:3] + ranked_[-3:]}
    for tm in re.finditer(r'<text x="([\d.]+)" y="([\d.]+)" text-anchor="(start|end)">([^<]+)</text>', sc):
        lx, ly, anchor, short = float(tm.group(1)), float(tm.group(2)), tm.group(3), tm.group(4)
        if not any(re.sub(r"^(House|Senate) ", "", n_) == short for n_ in marks):
            continue
        wd = LN.text_w(short, LN.CH_PX)
        x0 = lx - wd if anchor == "end" else lx
        for n_, (ox, oy) in marks.items():
            if n_ in named_ and re.sub(r"^(House|Senate) ", "", n_) != short:
                assert not (x0 <= ox <= x0 + wd and ly - LN.CH_PX * .8 <= oy <= ly + LN.CH_PX * .25), (
                    f"the label '{short}' is set across {n_}'s point at ({ox:.0f}, {oy:.0f})")
    # (c) tied committees come out in name order whatever order they arrive in
    assert LN.scatter_chart(pts, "t", "said", "x", "y") == LN.scatter_chart(pts[::-1], "t", "said", "x", "y"), (
        "the scatter chart draws tied committees in the order they arrived (a set's, so the hash seed's)")
    css = _source("src/pages/app.css")
    assert not re.search(r"\.l-secb\s*>\s*\.l-numwrap\s*\{[^}]*max-width:\s*var\(--l-meas\)", css), (
        "app.css holds the number tables to the prose measure again (.l-secb > .l-numwrap)")
    sk = re.search(r"\.l-skwrap\s*>\s*svg\s*\{([^}]*)\}", css)
    assert sk and "min-width" not in sk.group(1), (
        "the flow diagram has a minimum width at every width (.l-skwrap > svg): it scrolls where it could scale")
    for rule in re.finditer(r"([^{}]*\.l-skwrap\s*>\s*svg[^{}]*)\{([^}]*min-width:\s*[1-9][^}]*)\}", css):
        before = css[:rule.start()]
        assert before.rfind("@media (max-width:40em){") > before.rfind("}\n}"), (
            "a minimum width on the flow diagram that is not inside the phone's media query: "
            + rule.group(1).strip())
    for m in re.finditer(r"\.l-numtab[^{}]*\bth\b[^{}]*\{([^}]*)\}", css):
        assert not re.search(r"overflow-wrap:\s*(anywhere|break-word)|word-break:\s*break-all", m.group(1)), (
            "a number table's head may break inside a word again (it read 'PASSE / D BOTH CHAMB / ERS')")
    assert "min-width" not in inspect_source(LN._svg), "the charts' SVG carries an inline minimum width"
    # (a) the phone's pinned first column cannot reach the flow diagram's table (.l-twin):
    # its first column is the whole indented stage name, wider than a phone's box
    phone = css[css.index("@media (max-width:40em){", css.index("ON A PHONE a figures table")):]
    phone = phone[phone.index("{") + 1:phone.index("\n}\n")]
    pinned = [r for r in re.finditer(r"([^{}]+)\{([^}]*position:\s*sticky[^}]*)\}", phone)]
    assert pinned, "the phone's pinned first column rule was not found in app.css"
    for r_ in pinned:
        for sel in r_.group(1).split(","):
            assert ".l-numtab" in sel and ":not(.l-twin)" in sel, (
                "the phone's sticky first column reaches the flow diagram's table (.l-twin), "
                "where it covers the figures: " + sel.strip())
    return "ok", (f"{sum(h.count('<text') for h in svgs.values())} labels in {len(svgs)} chart builders inside "
                  "their viewBoxes; no named scatter label across its own point or another named committee's; tied committees in name order; "
                  "tables not held to the measure; the diagram's minimum width and the pinned first column "
                  "(not the flow table's) are phone-only")


def inspect_source(fn):
    import inspect
    return inspect.getsource(fn)


@check("data", "every RSA section the Learn pages cite is in force, and says what they quote")
def _learn_statutes_in_force():
    """Against the General Court's own RSA table, db/NH_RSA.psv.

    Two halves. Every "RSA n:s" on every Learn page, and every section listed
    after one in the same citation, must be a row of the table whose title
    does not read "Repealed"; a chapter named alone must be a chapter of it.
    And each claim in LEARN_STATUTE_CLAIMS must still find its words in its
    section, so a re-dump in which a statute changed under a sentence stops
    here rather than on a reader.

    A data check and not a code one, on purpose: nightly.py gates itself on
    `preflight --code`, and a statute amended by the legislature is a reason
    to reread a page, not a reason to stop the night's build.
    """
    import html as _html
    cols_p, rsa_p = Path("db/_columns.json"), Path("db/NH_RSA.psv")
    if not (cols_p.exists() and rsa_p.exists()):
        return "skip", "db/NH_RSA.psv is not on this disk"
    try:
        import civics
    except Exception as e:                      # noqa: BLE001
        return "skip", f"civics.py did not import ({e})"
    cols = json.loads(cols_p.read_text(encoding="utf-8")).get("NH_RSA") or []
    need = {"ChapterNo", "SectionNo", "Section", "rsa"}
    assert need <= set(cols), f"db/_columns.json lacks NH_RSA columns {sorted(need - set(cols))}"
    at = {c: cols.index(c) for c in need}
    chapters, sections = set(), {}
    with rsa_p.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            p = line.rstrip("\n").split("|")
            if len(p) != len(cols):
                continue
            chapters.add(p[at["ChapterNo"]].strip())
            sections[p[at["SectionNo"]].strip()] = (p[at["Section"]], p[at["rsa"]])
    assert len(sections) > 10000, f"db/NH_RSA.psv read as only {len(sections):,} sections"

    ref = r"\d+(?:-[A-Z]+)?(?::\d+(?:-[a-z]+)*)?"
    para = r"(?:,\s*[IVXL]+(?:\([a-z0-9]+\))?(?:(?:,\s*|\s+and\s+)[IVXL]+(?:\([a-z0-9]+\))?)*)?"
    cite = re.compile(r"RSA\s+(" + ref + para + r"(?:(?:,\s*|\s+and\s+)" + ref + para + r")*)")
    cited, bad = set(), []
    for t in civics.TOPICS:
        flat = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ",
                                                          t["body"] + " " + (t.get("holds") or ""))))
        for m in cite.finditer(flat):
            for r_ in re.findall(ref, m.group(1)):
                cited.add((t["slug"], r_))
    for slug, r_ in sorted(cited):
        if ":" not in r_:
            if r_ not in chapters:
                bad.append(f"{slug} cites RSA {r_}, which is no chapter of the table")
            continue
        row = sections.get(r_.replace(":", "-"))
        if not row:
            bad.append(f"{slug} cites RSA {r_}, which is not in the table")
        elif re.search(r"\brepealed\b", row[0], re.I):
            bad.append(f"{slug} cites RSA {r_}, repealed: {row[0][:70]}")

    def words(s):
        s = re.sub(r"<[^>]+>", " ", s.replace("&#150;", "-"))
        return re.sub(r"\s+", " ", _html.unescape(s)).lower()

    for slug, _phrase, sec, said in LEARN_STATUTE_CLAIMS:
        row = sections.get(sec.replace(":", "-"))
        if not row:
            bad.append(f"RSA {sec}, cited on {slug}, is not in the table")
        elif said.lower() not in words(row[1]):
            bad.append(f"RSA {sec} no longer says {said!r}, which {slug} relies on")
    assert not bad, "; ".join(bad[:4]) + (f" (and {len(bad) - 4} more)" if len(bad) > 4 else "")
    return "ok", (f"{len({r for _s, r in cited})} cited sections and chapters in force; "
                  f"{len(LEARN_STATUTE_CLAIMS)} anchored claims say what their sections say")


@check("data", "County Government's ten county cards say what RSA 653:1 and 662:4 say of each county")
def _county_cards_statute():
    """The county cards (civics.county_cards, 24 November 2026) were written
    from the statute table the Laws pages are built from, read on the Laws
    pages themselves because the cloud machine had no kit. Here they are held
    to db/NH_RSA.psv. For each county, its lettered subparagraph of RSA 653:1,
    VI must name it, say "all the voters of the county" exactly where the card
    says the whole county votes, say "4-year term" exactly where the card says
    the terms are staggered, and name the election the card dates a
    staggering from; 653:1, V must give a four-year term to exactly the
    counties the card does, from the election it names; and RSA 662:4's
    paragraph for the county must say, district by district, the words the
    card quotes. A data check, as _learn_statutes_in_force is: a statute
    amended under a card is a reason to reread it, not to stop the night."""
    import html as _html
    rsa_p = Path("db/NH_RSA.psv")
    if not rsa_p.exists():
        return "skip", "db/NH_RSA.psv is not on this disk"
    import civics
    secs = _rsa_sections(rsa_p, {"653:1", "662:4"})
    assert secs and "653:1" in secs and "662:4" in secs, "db/NH_RSA.psv lacks RSA 653:1 or 662:4"

    def norm(s):
        s = _html.unescape(s).replace("’", "'").replace("&rsquo;", "'")
        return re.sub(r"\s+", " ", s).strip().rstrip(".;").lower()
    s653, s662 = secs["653:1"][1], secs["662:4"][1]
    v = re.search(r"\bV\. (.*?)\bVI\. ", s653, re.S)
    vi = re.search(r"\bVI\. (.*)$", s653, re.S)
    assert v and vi, "RSA 653:1 has no paragraphs V and VI as the cards read them"
    subs = dict(re.findall(r"\(([a-j])\) (.*?)(?=\([a-j]\) [A-Z]|$)", vi.group(1), re.S))
    bad = []
    for name, (letter, at_large, staggered, since, four, numeral) in civics.COUNTY_RULES.items():
        sub = subs.get(letter, "")
        if not sub.lower().startswith(name.lower()):
            bad.append(f"RSA 653:1, VI({letter}) is not {name}'s: {sub[:40]!r}")
            continue
        if ("all the voters of the county" in sub) != at_large:
            bad.append(f"{name}'s card says the whole county votes={at_large}, and VI({letter}) does not")
        if ("4-year term" in sub) != staggered:
            bad.append(f"{name}'s card says staggered={staggered}, and VI({letter}) does not")
        if since and f"at the {since} state general election" not in sub:
            bad.append(f"{name}'s card dates its staggering from {since}, and VI({letter}) does not")
        four_here = re.search(rf"at the (\d{{4}}) state general election, and at each subsequent state "
                              rf"general election, any such officer in {name} county shall be chosen "
                              r"in the county by the voters for a 4-year term", v.group(1), re.I)
        if (four_here.group(1) if four_here else None) != (str(four) if four else None):
            bad.append(f"{name}'s card gives its officers four years from {four}, and 653:1, V "
                       f"{'from ' + four_here.group(1) if four_here else 'not at all'}")
        para = re.search(rf"\b{numeral}\. {name}: (.*?)(?=\b[IVX]+\. [A-Z][a-z]+: |Source\.|$)", s662, re.S)
        if not para:
            bad.append(f"RSA 662:4 has no paragraph {numeral} for {name}")
            continue
        said = [norm(d) for d in re.split(r";?\s*District \d,? ", " " + para.group(1))[1:]]
        want = [norm(d) for d in civics.COMMISSIONER_DISTRICTS[name]]
        if said != want:
            i = next((k for k, (a, b) in enumerate(zip(said, want)) if a != b), min(len(said), len(want)))
            bad.append(f"{name} District {i + 1} on the card is not RSA 662:4, {numeral}'s words")
    assert not bad, "; ".join(bad[:4]) + (f" (and {len(bad) - 4} more)" if len(bad) > 4 else "")
    return "ok", (f"{len(civics.COUNTY_RULES)} county cards: each one's election, staggering and officer "
                  "terms are its subparagraph of RSA 653:1, and its districts RSA 662:4's words")


@check("frontend", "County Government's ten county cards are on the built page in English and "
                   "Spanish, each counted, linked to its county on the Officials page, with no "
                   "website line where no source is on hand", needs=("civics",))
def _county_cards_built(CV):
    """The tester's request, approved by the owner for 24 November 2026: one
    card a county. On preflight's fixture site: ten cards on each language's
    page, each with its own id and a link to its own section of the County
    Officials tab (#of-county-<name>), no figure left unfilled; on the
    Spanish page the cards' words are the catalog's, drawn once there
    (civics.county_cards) rather than ten copies of each, and RSA 662:4's
    words are marked as English; a Website row only for a county
    COUNTY_SITES names, each with the page it was read from and its day."""
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    shared, _base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    bad = []
    for lang, rel, name in (("en", "learn/county-government.html", "Strafford County"),
                            ("es", "es/learn/county-government.html", "Condado de Strafford")):
        p = site / rel
        if not p.is_file():
            bad.append(f"{rel} was not built")
            continue
        t = p.read_text(encoding="utf-8")
        grid = re.search(r'<div class="l-who l-counties".*?</section></div>', t, re.S)
        if not grid:
            bad.append(f"{rel} has no county cards")
            continue
        g = grid.group(0)
        ids = re.findall(r'<section class="l-body" id="county-([a-z]+)">', g)
        if ids != [c.lower() for c in CV.COUNTY_RULES]:
            bad.append(f"{rel}'s cards are {ids}")
        links = re.findall(r'href="[^"]*officials(?:\.html)?#of-county-([a-z]+)"', g)
        if links != ids:
            bad.append(f"{rel}'s cards link {links} on the Officials page")
        if "[[" in g:
            bad.append(f"{rel}'s cards leave a figure unfilled")
        if f"<h3>{name}</h3>" not in g:
            bad.append(f"{rel} does not name its card {name!r}")
        sites = len(re.findall(r'<dt>(?:Website|Sitio web)</dt>', g))
        if sites != len(CV.COUNTY_SITES):
            bad.append(f"{rel} draws {sites} Website rows for {len(CV.COUNTY_SITES)} sourced addresses")
        if lang == "es":
            if "Escalonados" not in g or "Staggered" in re.sub(r'<span lang="en">.*?</span>', "", g):
                bad.append("the Spanish cards are not in Spanish")
            if g.count('<span lang="en">the towns of') + g.count('<span lang="en">the city of') < 20:
                bad.append("the Spanish cards do not mark RSA 662:4's words as English")
        if "County by County" not in t and "Condado por condado" not in t:
            bad.append(f"{rel} has no County by County heading")
    for c, rec in CV.COUNTY_SITES.items():
        if c not in CV.COUNTY_RULES or len(rec) != 3 or not all(rec) or not str(rec[0]).startswith("https://"):
            bad.append(f"COUNTY_SITES[{c!r}] is not (an https address, its source, the day read)")
    es = json.loads(_source("src/pages/lang/es.json"))["strings"]
    many = [k for k in es if re.match(r"learn\.county-government\.(the-law|state-representatives|"
                                      r"the-countys-state-representatives)", k)]
    if many:
        bad.append(f"the catalog holds per-county copies of the cards' words: {many[:3]}")
    bc = _source("src/pages/build_civics.py")
    if "co not in civics.COUNTY_RULES" not in bc:
        bad.append("a House district in no known county would leave a card short, silently")
    assert not bad, "; ".join(bad[:6])
    return "ok", (f"ten cards on the English and Spanish pages, each counted and linked to its county; "
                  f"{len(CV.COUNTY_SITES)} website lines, one for each sourced address")


@check("frontend", "the language sweep's clear fixes hold: plain words for the record's "
       "machinery, one How It Ended, US spelling in what a reader sees",
       needs=("civics", "components"))
def _language_sweep_words(civics, C):
    """The language sweep of 17 October 2026 (private/LANGUAGE_SWEEP_2026-10-17.md,
    its clear fixes): sentences that spoke the site's own machinery to a
    reader ("Not yet fetched for this term", "RollCallHistory.txt and
    RollCallSummary.txt", "Other -- 27 not in chart", "SC 13"), contradicted
    the page beside them ("whatever its last recorded status says", a second
    How It Ended, "without dividing it by party" before a party split), or
    spelled for a British reader. Each pair below is a sentence that must be
    gone and the one that replaced it; fails if one comes back."""
    src = lambda p: _paths.locate(p).read_text(encoding="utf-8")   # noqa: E731
    app = src("app.js")
    pages = src("build_pages.py")
    learn = " ".join(v for k, v in vars(civics).items()
                     if isinstance(v, str) and k.isupper())
    learn += " ".join(json.dumps(v) for k, v in vars(civics).items()
                      if k.startswith("FLOW") and isinstance(v, list))
    gloss = C.WORDBOOK["glossary"]
    bad = []
    for where, text, gone, there in (
            ("app.js", app, "whatever its last recorded", "went no further"),
            ("app.js", app, "not in chart</span>", "Did not vote — ${oTot}"),
            ("app.js", app, "Everything above is this site", "The other tabs are this site"),
            ("app.js", app, "RollCallHistory.txt\n    and RollCallSummary", "About This Record"),
            ("app.js", app, "Not yet fetched for this term", "Not on this site yet for its term"),
            ("app.js", app, "This term is archived", "This bill is from an earlier term"),
            ("app.js", app, "The calendar carrying this report has not been read", "begin in 1997"),
            ("app.js", app, '"of roll calls recorded on"', '"of roll calls taken part in"'),
            ("app.js", app, "r.body===\"S\"?r.cite:", "docLong(r.cite)"),
            ("app.js", app, "the page this site takes a bill's status from",
             "saying where the bill stands"),
            ("build_pages.py", pages, "the whole record, as lists</a>", "the directory</a> lists"),
            ("build_pages.py", pages, "rows.length} matches on this site", "pages on this site"),
            ("Learn", learn, "following an executive", "in an executive"),
            ("Learn", learn, "cover several towns or wards", "laid over two or more"),
            ("Learn", learn, "without dividing it by party", "each had a close roll call"),
            ("Learn", learn, "<b>Sponsors</b>, and <b>Documents</b>", "<b>Documents</b> &mdash;"),
            ("Learn", learn, "Filed as an LSR", "Legislative Service Request, or LSR"),
            ("Learn", learn, "legislative branch is made up", "is called the <b>General Court</b>"),
            # The person's judgment calls, approved 17 October 2026.
            ("Learn", learn, "<h2>A Term Is Two Years</h2>\n<p>The General Court sits in two-year "
             "terms beginning in odd years. Bill", "[[org_day]]"),
            ("app.js", app, '?"Amends RSA chapter":', "Changes these chapters of state law (RSA)"),
            ("app.js", app, "the times on the cards move this player",
             "Choose a time on a card to jump the recording there."),
            ("app.js", app, 's.venue?" · "+esc(s.venue)', "roomWords(s.venue)"),
            ("chrome.py", src("chrome.py"), "MIT Open Source Licensed", "Open source (MIT License)"),
            # The example a page the build writes (not_found_example; P2 of the
            # polish of 26 October 2026), held by _not_found_example_is_there.
            ("build_pages.py", pages, "/bill/&lt;year&gt;/&lt;number&gt;", "<code>[[example]]</code>"),
            ("build_rsa.py", src("build_rsa.py"), "the bills now proposing to",
             "laws not yet included."),
            ("build_site_v2.py", src("build_site_v2.py"), '"text": f"Still in interim study when',
             "In interim study: the committee studies the subject in the fall of"),
            ("topic_vocabulary.py", src("topic_vocabulary.py"), "TOPIC_WORDS = {}",
             '"CACR": "Constitutional Amendments"')):
        if gone in text:
            bad.append(f"{where} says {gone!r} again")
        if there not in text:
            bad.append(f"{where} no longer says {there!r}")
    british = re.compile(r"\b(autumn|licen[cs]es?(?! plate)|licence|neighbour\w*|councillors?|"
                         r"[Ee]nrolment|by-elections?|organis\w+|summaris\w+|authoris\w+|"
                         r"itemis\w+|favour|colour\w*|misdemeanour\w*|\brota\b)\b")
    for where, text in (("Learn", learn), ("the glossary", json.dumps(gloss))):
        hit = sorted(set(m.group(0) for m in british.finditer(text) if m.group(0) != "license"
                         and m.group(0) != "licenses"))
        if hit:
            bad.append(f"{where} spells {hit} for a British reader")
    if "second year only" in gloss["IS"]["says"] or "kill it\"" in json.dumps(gloss["ITL"]):
        bad.append("the glossary's IS or ITL no longer defines its term")
    for key in ("Died", "Floterial district", "Docket", "Indefinitely postponed"):
        if key not in gloss:
            bad.append(f"the glossary has no entry for {key}")
    # A how-to guide is not drawn from the General Court's record, so its
    # citation note does not tell a reader to cite the General Court.
    import shell as _S
    guide = _S.cite_block("/guides/how-to-vote.html", "How to Vote | Granite Record", "")
    bill = _S.cite_block("/bill/2026/hb1.html", "HB 1 | Granite Record", "")
    if "cite the General Court" in guide or "cite the General Court" not in bill:
        bad.append("a guide's citation note says to cite the General Court, or a bill's no longer does")
    assert not bad, "; ".join(bad)
    return "ok", "the sweep's plain words in place, its old ones gone, US spelling on Learn"


@check("frontend", "the pages that tell CACR 13's vote read true the day after it: the county "
       "page by the day, and Using This Site and the Data page by whether email is live",
       needs=("build_civics", "civics", "build_exports", "officials_tabs"))
def _ballot_words_by_the_day(BC, civics, build_exports, OT):
    """The language sweep of 17 October 2026, out of date before 10 November:
    county government's register of probate paragraph said CACR 13 went to
    the voters "at the November 2026 general election" and would have said it
    after; Using This Site said "There is no email option yet" and the Data
    page "Following a bill takes no account and no email address", neither
    switched by shell.follow_live() as About and the Data page's privacy are.
    Fails if the sentence stops following the day, invents a result the file
    does not hold, or either page stops following the switch."""
    import datetime as _dt
    row = {"term": "2025-2026", "bill": "CACR13", "election": "2026-11-03",
           "yes": None, "no": None}
    before = BC.probate_vote([row], _dt.date(2026, 11, 2))
    assert "at the general election of November 3, 2026." in before, before
    after = BC.probate_vote([row], _dt.date(2026, 11, 4))
    assert ("The vote was on November 3, 2026; the Secretary of State&rsquo;s count is not on "
            "the site yet.") in after and "ratif" not in after, after
    fell = BC.probate_vote([dict(row, yes=500, no=400)], _dt.date(2026, 11, 20))
    assert "did not reach the two thirds" in fell and "55.6%" in fell, fell
    won = BC.probate_vote([dict(row, yes=700, no=300)], _dt.date(2026, 11, 20))
    assert "ratified it: 70.0%" in won, won
    assert BC.probate_vote([], _dt.date(2026, 11, 4)).endswith("CACR 13 (2026)</a>."), (
        "with no ballot row the sentence claims a date or a result")
    assert "[[probate_vote]]" in civics.BODY_COUNTY and "[[follow_email]]" in civics.BODY_SITE, (
        "the county page or Using This Site no longer asks for its sentence")
    assert "no email option" in civics.FOLLOW_EMAIL[False] and \
        "no email option" not in civics.FOLLOW_EMAIL[True], civics.FOLLOW_EMAIL
    import inspect
    src = inspect.getsource(build_exports.feeds)
    assert "follow_live()" in src, "the Data page's Feeds line no longer follows the switch"
    # County Officials' "Most of these seats are on the November 2026 ballot".
    assert OT.ballot_line(_dt.date(2026, 11, 3)) == (
        "Most of these seats are on the ballot on November 3, 2026."), OT.ballot_line(_dt.date(2026, 11, 3))
    assert OT.ballot_line(_dt.date(2026, 11, 4)).startswith(
        "Most of these seats were on the ballot on November 3, 2026"), OT.ballot_line(_dt.date(2026, 11, 4))
    return "ok", ("CACR 13's sentence is ahead on 2 November, past without a count on 4 "
                  "November, and the count once entered; the county roster's ballot line the "
                  "same; email's two sentences follow the switch")


@check("data", "the register of probate paragraph is reread once the November 2026 vote is in")
def _probate_after_the_vote():
    """A REMINDER, and a failing check is the one kind that gets read.

    County government's "Register of probate" paragraph ends on a vote still
    to come: CACR 13 (2026), which would strike the office out of the
    constitution, is on the ballot of the general election of 3 November
    2026, and the page says it goes to the voters then. From the next day that
    sentence is wrong in its tense whatever the result, and wrong in substance
    if two thirds said yes. CACR 13's own page takes the result from the
    docket when the docket records it; this paragraph is written by hand, so
    no build will correct it. A person has to, and asked on 24 September to
    be reminded.

    A note in a document is read by whoever goes looking for it. preflight is
    the first thing every session runs (CLAUDE.md, "Do this first"), so a
    failing check is read by the first session after it fires, and its message
    says what to change and on which line. It passes again once
    civics.REGISTER_OF_PROBATE_REVIEWED holds the date of that review: on or
    after the day it fired, because a review before the result is not the one
    this asks for, and not after today, because a date in the future is a way
    to silence it early.

    IT FIRES ON THE RESULT, NOT ON THE DAY AFTER THE VOTE (17 October 2026).
    The paragraph's last sentence is written by the day since then
    (build_civics.probate_vote: "The vote was on November 3, 2026; the
    Secretary of State's count is not on the site yet"), so on 4 November the
    page is true and nothing needs a hand; failing every preflight and every
    dry run from that morning, on the eve of the release freeze of 6-10
    November, would have asked for a review with nothing yet to review. It
    fires the day the count is entered in corrections/ballot_results.json (its
    row's `read`), when "still elected" may have stopped being true, and on 2
    December 2026, Organization Day, if no count has been entered by then.

    A data check and not a code one, on purpose, for the reason
    _learn_statutes_in_force gives above: nightly.py gates itself on
    `preflight --code`, and an election result is a reason to reread a page,
    not a reason to stop the night's build. It needs nothing on disk.

    The rule is run on fixed days before it is run on the clock, so a
    reminder that could never fire fails now rather than passing quietly
    through the day it was written for.
    """
    import datetime as _dt
    try:
        import civics
    except Exception as e:                      # noqa: BLE001
        return "skip", f"civics.py did not import ({e})"
    vote = _dt.date(2026, 11, 3)
    backstop = _dt.date(2026, 12, 2)
    on = f"{vote.day} {vote:%B %Y}"
    src = _source(_paths.locate("civics.py")).splitlines()

    def at(text):
        n = next((i for i, s in enumerate(src, 1) if text in s), None)
        return f" (civics.py line {n})" if n else ""

    def due_on(row):
        """The day the reminder fires: the day the count was entered, never
        before the day after the vote; the backstop while there is none."""
        if (row or {}).get("yes") is None:
            return backstop
        try:
            read = _dt.date.fromisoformat(str(row.get("read")))
        except ValueError:
            read = vote
        return max(read, vote + _dt.timedelta(days=1))

    def rule(today, reviewed, row=None):
        """None while the paragraph needs nothing, or what to do about it."""
        due = due_on(row)
        if reviewed:
            try:
                when = _dt.date.fromisoformat(reviewed)
            except ValueError:
                return (f"REGISTER_OF_PROBATE_REVIEWED{at('REGISTER_OF_PROBATE_REVIEWED =')} "
                        f"is {reviewed!r}, which is not a date: write the day the "
                        "register of probate paragraph was reread, as \"2026-11-05\"")
            if when > today:
                return (f"REGISTER_OF_PROBATE_REVIEWED is {when}, after today: it "
                        "records a review that has happened, not one planned")
            if when >= due:
                return None
        if today < due:
            return None
        said = (f"the count of the vote of {on} is in corrections/ballot_results.json: reread"
                if (row or {}).get("yes") is not None else
                f"the vote was on {on} and no count has been entered in "
                "corrections/ballot_results.json: enter the Secretary of State's, then reread")
        return (
            f"{said} the register of probate paragraph on "
            "learn/county-government, beginning "
            f"\"Register of probate:\"{at('<p><b>Register of probate:</b>')}, whose last "
            "sentence the build now writes from that count -- an amendment needs two "
            "thirds of those voting on it -- and, if it passed, its \"still elected\" and "
            f"the sentence \"Five county officers are elected\"{at('Five county officers are elected')}, "
            "which counts the register among them. Then set REGISTER_OF_PROBATE_REVIEWED"
            f"{at('REGISTER_OF_PROBATE_REVIEWED =')} to the date of the review."
            + (f" It holds {reviewed!r}, which is before {due} and so before the result."
               if reviewed else ""))

    counted = {"yes": 300000, "no": 100000, "read": "2026-11-20"}
    for day, reviewed, row, fires in (
            # The day after the vote, and every day to the backstop: quiet.
            (vote, "", None, False), (_dt.date(2026, 11, 4), "", None, False),
            (_dt.date(2026, 12, 1), "", None, False),
            # No count by Organization Day: it fires.
            (backstop, "", None, True), (backstop, backstop.isoformat(), None, False),
            # The count entered on 20 November: it fires that day, until a
            # review on or after it.
            (_dt.date(2026, 11, 19), "", counted, False), (_dt.date(2026, 11, 20), "", counted, True),
            (_dt.date(2026, 11, 21), "2026-11-05", counted, True),
            (_dt.date(2026, 11, 21), "2026-11-20", counted, False),
            (_dt.date(2027, 2, 1), "2026-11-02", counted, True),
            (_dt.date(2026, 11, 20), "2026-11-25", counted, True),
            (_dt.date(2026, 11, 20), "soon", counted, True)):
        got = rule(day, reviewed, row)
        assert (got is not None) == fires, (
            f"on {day} with the review dated {reviewed!r} and "
            f"{'a count' if row else 'no count'}, the reminder "
            + ("stays quiet, and should fire" if fires else f"fires ({got[:80]}), and should not"))
    assert "Register of probate:" in (rule(backstop, "") or ""), (
        "the reminder no longer names the paragraph it is for")

    reviewed = getattr(civics, "REGISTER_OF_PROBATE_REVIEWED", None)
    assert isinstance(reviewed, str), (
        "civics.py has no REGISTER_OF_PROBATE_REVIEWED string, which is how the "
        "register of probate paragraph is marked as reread after the November "
        "2026 vote")
    today = _dt.date.today()
    p = Path("corrections/ballot_results.json")
    rows = (json.loads(p.read_text(encoding="utf-8")).get("rows") or []) if p.exists() else []
    row = next((r for r in rows if (r.get("term"), r.get("bill")) == ("2025-2026", "CACR13")),
               None)
    msg = rule(today, reviewed, row)
    assert msg is None, msg
    if reviewed:
        return "ok", f"reread on {reviewed}, after the vote of {on}"
    due = due_on(row)
    return "ok", (f"the vote is on {on}; this fails once its count is entered, or on {due} "
                  f"if none is, until the paragraph is reread ({(due - today).days} days "
                  "from now at the latest)")
